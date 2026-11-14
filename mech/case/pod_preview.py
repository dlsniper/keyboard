"""Wireless variant of the numpad shell, PREVIEW ONLY (M3b session 1, user decisions 2026-11-14).

Envelopes, not printable parts: the battery rail along the rear edge and the outer (right) side, 4 x AA, the power
board behind the bay, the radio pod's module and service port on the bay board. Run in the FreeCAD GUI on top of the
shell that mech/case/build_case.py made:

    doc = App.openDocument("build/case/numpad/numpad-case.FCStd")
    exec(open("mech/case/pod_preview.py").read())

Numbers are in the shell's frame (x to the right, y to the rear, z up from the desk). The real parts come with the
shell step of M3b (rail joint to the tray, cell contacts, lids); nothing here is read by another script.
"""
import FreeCAD as App
import Part

V = App.Vector
RAIL = 19.0            # rail width and height: AA 14.5 mm + 2 x 2.0 mm wall + air
AA_D, AA_L, AA_PITCH = 14.5, 50.5, 52.0
POWER_BOARD = (48.0, 14.0, 1.6)     # provisional: two converters in a 15 mm wide channel
POD_MODULE = (10.5, 15.5, 2.0)      # nRF52840 module (MDBT50Q class)
USB_C = (8.94, 7.3, 3.2)            # 16-pin USB 2.0 receptacle, mouth to the rear


def preview(doc):
    tray = doc.getObject("tray").Shape.BoundBox
    port = doc.getObject("port").Shape.BoundBox
    for o in list(doc.Objects):
        if o.Name.startswith(("POD_", "RAIL_", "A_", "B_", "C_", "R4", "U_", "S6", "L_", "S_")):
            doc.removeObject(o.Name)

    def add(name, shape, colour, transparency=0):
        o = doc.addObject("Part::Feature", name)
        o.Shape = shape
        o.ViewObject.ShapeColor = colour
        o.ViewObject.Transparency = transparency
        return o

    def cell(p, axis):
        return Part.makeCylinder(AA_D / 2, AA_L, V(*p), V(*axis))

    x1, y0, y1 = tray.XMax, tray.YMin, tray.YMax
    zc = 2.0 + AA_D / 2
    cells = [cell((x1 + RAIL / 2, y0 + 2.0 + i * AA_PITCH, zc), (0, 1, 0)) for i in range(3)]   # outer side
    cells.append(cell((tray.XMin + 2.0, y1 + RAIL / 2, zc), (1, 0, 0)))                         # rear
    s = cells[0]
    for c in cells[1:]:
        s = s.fuse(c)
    rail = Part.makeBox(RAIL, tray.YLength + RAIL, RAIL, V(x1, y0, 0)).fuse(
        Part.makeBox(tray.XLength, RAIL, RAIL, V(tray.XMin, y1, 0)))
    green = (0.1, 0.7, 0.3)
    add("RAIL_cells_4xAA", s, green)
    add("RAIL_envelope", rail, green, 75)
    pb = POWER_BOARD
    add("RAIL_power_board", Part.makeBox(pb[0], pb[1], pb[2], V(port.XMin, y1 + 2.5, 4.0)), (0.1, 0.5, 0.2))
    z = port.ZMax - 3.26          # top of the bay board (the wired port's receptacle is 3.26 mm high)
    m = POD_MODULE
    add("POD_radio_module", Part.makeBox(m[0], m[1], m[2], V(port.XMax - m[0] - 2.0, port.YMin + 2.0, z)), (0.9, 0.9, 0.2))
    u = USB_C
    add("POD_service_usb_c", Part.makeBox(u[0], u[1], u[2], V(port.XMin + 4.0, port.YMax - u[1], z)), (0.7, 0.7, 0.75))
    for n in ("tilt4", "tilt7"):
        if doc.getObject(n):
            doc.getObject(n).ViewObject.Visibility = False
    doc.recompute()
    App.Console.PrintMessage(
        f"pod preview: rail {RAIL:.0f} mm wide and high; module {tray.XLength + RAIL:.1f} x {tray.YLength + RAIL:.1f} mm "
        f"(was {tray.XLength:.1f} x {tray.YLength:.1f}); rail top {RAIL:.1f}, bay board top {z:.2f} "
        f"(service port {z - RAIL:.2f} mm above the rail)\n")


preview(App.ActiveDocument)
