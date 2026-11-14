"""Wireless variant of the numpad shell, PREVIEW ONLY (M3b sessions 1 and 3, user decisions 2026-11-14).
Superseded for the numpad by mech/case/pod_case.py (the real parts, CASE_VARIANT=pod); still the hub carrier's preview.

Envelopes, not printable parts: the battery rail along the rear edge (27 mm deep since session 3: the power board
is 48 x 22 mm) and the outer side (19 mm), 4 x AA, the power board behind the bay, the radio pod (30 x 50.7 mm, from
the bay rearwards over the rail to 2.5 mm inside the rail's rear face) with its module and service port.
Run in the FreeCAD GUI on top of the shell that mech/case/build_case.py made:

    doc = App.openDocument("build/case/numpad/numpad-case.FCStd")
    exec(open("mech/case/pod_preview.py").read())

With the hub section open instead (build/mech/hub/hub-section.FCStd, document "hub_section") the same script draws
the carrier and the pod above the core board (objects RADIO_*).

Numbers are in the shell's frame (x to the right, y to the rear, z up from the desk) and repeat tools/pcb_pod.py
(POD_REAR, MOD_A, USB_A, PW, CAR_*); nothing here is read by another script. The real parts come with the shell
step of M3b (rail joint to the tray, cell contacts, lids, the lowered lid under the pod).
"""
import FreeCAD as App
import Part

V = App.Vector
RAIL_SIDE, RAIL_REAR, RAIL_H = 19.0, 27.0, 19.0     # side leg: AA 14.5 + 2 x 2.0 wall + air; rear leg: 22 mm board + walls
AA_D, AA_L, AA_PITCH = 14.5, 50.5, 52.0
POWER_BOARD = (48.0, 22.0, 1.6)
POD = (30.0, 50.7, 1.6)             # a -15 .. 15, t 1.5 .. 52.2 in the bay frame
MODULE = (10.6, 15.6, 2.05)         # MDBT50Q-1MV2, antenna end on the pod's rear edge, 2.7 mm from its east edge
USB_C = (8.94, 9.8, 3.2)            # GCT USB4085, mouth 2.51 mm beyond the pod's rear edge = the rail's rear face
CAN = (6.3, 5.8)                    # the power board's 47 uF can, the tallest part under the pod


def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def add(doc, name, shape, colour, transparency=0):
    o = doc.addObject("Part::Feature", name)
    o.Shape = shape
    o.ViewObject.ShapeColor = colour
    o.ViewObject.Transparency = transparency
    return o


def clear(doc, prefixes):
    for o in list(doc.Objects):
        if o.Name.startswith(prefixes):
            doc.removeObject(o.Name)


def preview(doc):
    tray = doc.getObject("tray").Shape.BoundBox
    port = doc.getObject("port").Shape.BoundBox
    clear(doc, ("POD_", "RAIL_", "OPT_"))
    x1, y0, y1 = tray.XMax, tray.YMin, tray.YMax
    zc = 2.0 + AA_D / 2
    cells = [Part.makeCylinder(AA_D / 2, AA_L, V(x1 + RAIL_SIDE / 2, y0 + 2.0 + i * AA_PITCH, zc), V(0, 1, 0)) for i in range(3)]
    cells.append(Part.makeCylinder(AA_D / 2, AA_L, V(tray.XMin + 2.0, y1 + 2.0 + AA_D / 2, zc), V(1, 0, 0)))   # rear, front lane
    s = cells[0]
    for c in cells[1:]:
        s = s.fuse(c)
    rail = box(x1, x1 + RAIL_SIDE, y0, y1 + RAIL_REAR, 0, RAIL_H).fuse(box(tray.XMin, x1, y1, y1 + RAIL_REAR, 0, RAIL_H))
    green = (0.1, 0.7, 0.3)
    add(doc, "RAIL_cells_4xAA", s, green)
    add(doc, "RAIL_envelope", rail, green, 75)
    pb = POWER_BOARD
    px0, py1 = x1 + RAIL_SIDE - 2.0 - 0.3 - pb[0], y1 + RAIL_REAR - 2.0 - 0.5      # east end at the corner, rear edge at the wall
    board = box(px0, px0 + pb[0], py1 - pb[1], py1, 4.0, 4.0 + pb[2]).cut(      # front-east corner cut away (pcb_pod.NOTCH)
        box(px0 + 32.5, px0 + pb[0], py1 - pb[1], py1 - 15.4, 4.0, 4.0 + pb[2]))
    add(doc, "RAIL_power_board", board, (0.1, 0.5, 0.2))
    add(doc, "RAIL_side_contact_room", box(x1 + 2.0, x1 + RAIL_SIDE - 2.0, y0 + 2.0 + 3 * AA_L, y0 + 2.0 + 3 * AA_L + 9.0, 2.0, 16.5), (0.9, 0.5, 0.1), 60)
    add(doc, "RAIL_lead_connector", box(px0 + 35.8, px0 + 47.8, py1 - 6.9, py1 - 0.3, 5.6, 9.9), (0.9, 0.9, 0.9))
    add(doc, "RAIL_power_can", Part.makeCylinder(CAN[0] / 2, CAN[1], V(px0 + 17.5, py1 - 4.5, 4.0 + pb[2])), (0.3, 0.3, 0.3))
    add(doc, "RAIL_power_switch", box(px0 + 26.4, px0 + 34.6, py1 - 0.1, py1 + 4.1, 5.6, 9.2), (0.8, 0.2, 0.2))
    z = port.ZMax - 3.26          # top of the bay board (the wired port's receptacle is 3.26 mm high)
    cx = (port.XMin + port.XMax) / 2
    front = port.YMin
    rear = front + POD[1]
    add(doc, "POD_board", box(cx - 15, cx + 15, front, rear, z - POD[2], z), (0.95, 0.75, 0.1))
    m = MODULE
    add(doc, "POD_radio_module", box(cx + 7.0 - m[0] / 2, cx + 7.0 + m[0] / 2, rear - m[1], rear, z, z + m[2]), (0.9, 0.9, 0.2))
    u = USB_C
    add(doc, "POD_service_usb_c", box(cx - 9.0 - u[0] / 2, cx - 9.0 + u[0] / 2, rear + 2.51 - u[1], rear + 2.51, z, z + u[2]), (0.7, 0.7, 0.75))
    add(doc, "POD_lead_connector", box(cx - 11.7, cx - 5.3, front + 25.5, front + 37.5, z, z + 2.0), (0.9, 0.9, 0.9))
    for n in ("tilt4", "tilt7", "cover", "port"):
        if doc.getObject(n):
            doc.getObject(n).ViewObject.Visibility = False
    doc.recompute()
    App.Console.PrintMessage(
        f"pod preview: module {tray.XLength + RAIL_SIDE:.1f} x {tray.YLength + RAIL_REAR:.1f} mm (was {tray.XLength:.1f} x {tray.YLength:.1f}); "
        f"rail top {RAIL_H:.1f}, pod underside {z - POD[2]:.2f}, can top {4.0 + pb[2] + CAN[1]:.1f}; "
        f"pod rear edge {y1 + RAIL_REAR - rear:.2f} mm inside the rail's rear face\n")


def hub_preview(doc):
    """Carrier on the core board's expansion header and the pod above it, pointing to the front (tools/pcb_pod.py CAR_*)."""
    clear(doc, ("RADIO_",))
    core = doc.getObject("core").Shape.BoundBox
    zc = core.ZMax + 11.04                              # carrier underside: 8.5 mm socket + 2.54 mm header body
    out = [(-52.0, 32.5), (-24.5, 32.5), (-24.5, 38.0), (-26.6, 38.0), (-26.6, 52.5), (-52.0, 52.5)]
    wire = Part.makePolygon([V(x, y, zc) for x, y in out + out[:1]])
    add(doc, "RADIO_carrier", Part.Face(wire).extrude(V(0, 0, 1.6)), (0.1, 0.5, 0.2))
    zp = zc + 1.6 + 11.04
    cx, cy = -39.5, 55.5
    add(doc, "RADIO_pod", box(cx - 15, cx + 15, cy - 52.2, cy - 1.5, zp, zp + 1.6), (0.95, 0.75, 0.1))
    add(doc, "RADIO_pod_module", box(cx - 7.0 - 5.3, cx - 7.0 + 5.3, cy - 52.2, cy - 52.2 + 15.6, zp + 1.6, zp + 3.65), (0.9, 0.9, 0.2))
    doc.recompute()
    shell = doc.getObject("shell_outline").Shape.BoundBox
    App.Console.PrintMessage(f"radio preview: module top {zp + 3.65 - core.ZMax:.1f} mm above the core board; "
                             f"the plain shell tube ends {shell.ZMax - core.ZMax:.1f} mm above it\n")


if App.ActiveDocument.getObject("tray"):
    preview(App.ActiveDocument)
elif App.ActiveDocument.getObject("core"):
    hub_preview(App.ActiveDocument)
