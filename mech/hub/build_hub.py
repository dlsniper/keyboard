"""Hub tower section, rev 9 (M2 session 4): boards, connectors, tall parts and standoff positions, to prove the
heights and positions the hub boards are placed with. Not the case: shells, lips, magnets and the lid are M3
(rev 8's script, archive/rev8/mech/hub/build_hub.py, is the starting point for them).

All numbers come from mech/hub/hub_geom.py, which tools/pcb_hub.py reads too. The .FCStd is a build output.
Run:  /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd mech/hub/build_hub.py
It prints the clearances it checks and exits 1 if one is negative.
"""
import os
import sys

import FreeCAD as App
import Part

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "/Users/florin/projects/personal/keyboard/mech/hub"
sys.path.insert(0, HERE)
import hub_geom as g  # noqa: E402

OUT = os.path.join(HERE, "..", "..", "build", "mech", "hub")
N_BATT = 2
COL = dict(board=(0.1, 0.45, 0.2), conn=(0.15, 0.15, 0.15), part=(0.6, 0.6, 0.65), pin=(0.85, 0.7, 0.2),
           holder=(0.05, 0.05, 0.05), shell=(0.8, 0.8, 0.85), pico=(0.1, 0.5, 0.3), boss=(0.9, 0.5, 0.1))


def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, App.Vector(x0, y0, z0))


def cbox(cx, cy, sx, sy, z0, z1):
    return box(cx - sx / 2, cx + sx / 2, cy - sy / 2, cy + sy / 2, z0, z1)


def cyl(d, x, y, z0, z1):
    return Part.makeCylinder(d / 2, z1 - z0, App.Vector(x, y, z0))


doc = App.newDocument("hub")
shapes = {}


def add(name, shape, col, transparency=0):
    o = doc.addObject("Part::Feature", name)
    o.Shape = shape
    if hasattr(o, "ViewObject") and o.ViewObject:
        o.ViewObject.ShapeColor = COL[col]
        o.ViewObject.Transparency = transparency
    shapes[name] = shape
    return shape


def board(name, z, holes, y0=-g.BOARD / 2, x1=g.BOARD / 2, y1=g.BOARD / 2):
    s = box(-x1, x1, y0, y1, z, z + g.T_PCB)
    for x, y in holes:
        s = s.cut(cyl(2.2, x, y, z - 1, z + g.T_PCB + 1))
        add(f"{name}_standoff_{int(x)}_{int(y)}", cyl(5.0, x, y, z - 6.0, z), "boss")   # insert boss under the board (M3 shapes it)
    return add(name, s, "board")


def esq(name, z):
    """ESQ socket on a board's top, tails below."""
    x, y = g.STACK_XY
    add(f"{name}_esq", cbox(x, y, 2.54 * 25 + 0.51, g.ESQ_W, z + g.T_PCB, z + g.T_PCB + g.ESQ_BODY_H), "conn")
    add(f"{name}_esq_tails", cbox(x, y, 2.54 * 25, 3.2, z + g.T_PCB - g.ESQ_TAIL, z), "pin")


lv = g.levels(N_BATT)
top = g.T_PCB
checks = []

# ---- battery modules ------------------------------------------------------------------------------------------------
for i in range(1, N_BATT + 1):
    z = lv[f"battery{i}"]
    n = f"battery{i}"
    board(n, z, g.MOUNT_XY)
    add(f"{n}_holder", cbox(*g.HOLDER_XY, g.HOLDER[0], g.HOLDER[1], z + top, z + top + g.HOLDER[2]), "holder")
    rx, ry = g.CHAIN_RISER_XY
    px, py = g.CHAIN_PADS_XY
    zc = z + top + g.RISER_SPACE                                    # cap board bottom
    add(f"{n}_riser", cbox(rx, ry, 20.32, 5.08, z + top, zc), "pin")
    add(f"{n}_cap_board", cbox((rx + px) / 2, (ry + py) / 2, g.CAP_BOARD[0], g.CAP_BOARD[1], zc, zc + top), "board")
    tip = zc + top + g.POGO_FREE
    add(f"{n}_spring_pins", cbox(px, py, 20.32, 5.08, zc + top, tip), "pin", 40)
    target = z + g.PITCH - g.TARGET_H                               # target disc face under the board above
    checks.append((f"{n}: chain spring pins compressed (stroke {g.POGO_STROKE})", tip - target, g.POGO_STROKE - (tip - target)))
    checks.append((f"{n}: holder top to the board above", z + g.PITCH - (z + top + g.HOLDER[2]), None))
    checks.append((f"{n}: cap board front edge to the holder (y)", (ry + py) / 2 - g.CAP_BOARD[1] / 2 - (g.HOLDER_XY[1] + g.HOLDER[1] / 2), None))
    add(f"{n}_targets", cbox(px, py, 20.32, 5.08, z - g.TARGET_H, z), "pin")

# ---- connector layer ------------------------------------------------------------------------------------------------
z = lv["conn"]
board("conn", z, g.MOUNT_XY, y0=g.CONN_FRONT, x1=g.CONN_X, y1=g.CONN_REAR)
esq("conn", z)
# host port board in the rear strip, on two standoffs; cable header at its front edge, hub-conn's header at JUSB_XY
zu = z + top + g.UP_STANDOFF
add("usbport_board", box(g.UP_X[0], g.UP_X[1], g.UP_Y[0], g.UP_Y[1], zu, zu + top), "board")
rx, (rw, rd, rh) = g.UP_REC_X, g.USB4085
add("usbport_receptacle", box(rx - rw / 2, rx + rw / 2, g.REAR_Y - rd, g.REAR_Y, zu + top, zu + top + rh), "part")
for i, (x, y) in enumerate(g.UP_MOUNT_XY):
    add(f"usbport_standoff_{i}", cyl(4.0, x, y, z + top, zu), "boss")
gx, gy = g.UP_GH_XY
add("usbport_header", cbox(gx, gy - 0.4, 17.0, 4.05, zu + top, zu + top + 4.05), "conn")
add("usbport_plug", box(gx - 7.5, gx + 7.5, gy - 9.5, gy - 2.45, zu + top + 0.3, zu + top + 3.8), "conn", 40)
jx, jy = g.JUSB_XY
add("conn_usb_header", cbox(jx, jy, 6.4, 18.2, z + top, z + top + 4.05), "conn")
add("conn_usb_plug", box(jx + 3.2, jx + 10.5, jy - 7.5, jy + 7.5, z + top + 0.3, z + top + 3.8), "conn", 40)
checks.append(("usb-port: board front edge to the stack socket (y)", g.UP_Y[0] - (g.STACK_XY[1] + g.ESQ_W / 2), None))
checks.append(("usb-port: board rear edge to the rear wall", (g.REAR_Y - g.WALL) - g.UP_Y[1], None))
checks.append(("usb-port: board rear edge to the receptacle mouth flush with the wall's outer face: left of the 0.05 mm allowed",
               0.05 - abs(g.REAR_Y - g.UP_Y[1] - g.USB4085_OVER), None))
checks.append(("usb-port: plug top to the core board's expansion header pins (z, 3 mm pins)", (g.GAP - 3.0) - (g.UP_STANDOFF + top + 3.8), None))
checks.append(("usb-port: standoff to the receptacle's shell lug (x)", 8.0 - 2.31 - (4.325 + 0.45), None))
add("conn_targets", cbox(*g.CHAIN_PADS_XY, 20.32, 5.08, z - g.TARGET_H, z), "pin")
for p, x in zip("ABC", g.PORT_X):
    add(f"conn_port_{p}", box(x - g.USBC[0] / 2, x + g.USBC[0] / 2, -g.BOARD / 2 - g.USBC_NOSE, -g.BOARD / 2 - g.USBC_NOSE + g.USBC[1],
                              z + top, z + top + g.USBC[2]), "part")
add("conn_can", cyl(g.CAN[0], 30, 0, z + top, z + top + g.CAN[1]), "part")          # tallest part; place is the PCB script's
checks.append(("conn: 220 uF can to the core board", g.GAP - g.CAN[1], None))
checks.append(("conn: ESQ tails below the board, to battery 1's cap board top (not above each other; z only)",
               (z - (g.ESQ_TAIL - top)) - (lv["battery1"] + top + g.RISER_SPACE + top), None))

# ---- core layer -----------------------------------------------------------------------------------------------------
zc = lv["core"]
board("core", zc, g.CORE_XY, y0=g.CORE_FRONT_Y)
esq("core", zc)
checks.append(("stack: core tails inside the connector layer's socket", (g.ESQ_TAIL - top) - (g.GAP - g.ESQ_BODY_H), None))
checks.append(("stack: board gap minus socket body (core rests above the socket)", g.GAP - g.ESQ_BODY_H, None))
px, py = g.PICO_XY
zp = zc + top + g.PICO_UNDER
add("pico", cbox(px, py, g.PICO[0], g.PICO[1], zp, zp + g.PICO[2]), "pico")
for sy in (-1, 1):
    add(f"pico_socket_{sy}", cbox(px, py + sy * 8.89, 50.8, 2.54, zc + top, zc + top + 8.5), "conn")
add("pico_spring_pins", cbox(px + 24.3, py, 1.9, 3.9, zc + top, zp), "pin")
comp = g.SPRING_FREE - g.PICO_UNDER
checks.append((f"core: Pico spring pins compressed (stroke {g.SPRING_STROKE})", comp, g.SPRING_STROKE - comp))
ex, ey = g.EXP_XY
add("core_expansion", cbox(ex, ey, 12.7, 5.08, zc + top, zc + top + 8.5), "conn")
checks.append(("core: expansion header to the stack socket (x)", (g.STACK_XY[0] - (2.54 * 25 + 0.51) / 2) - (ex + 6.35), None))
checks.append(("core: Pico rear edge to the stack socket (y)", (g.STACK_XY[1] - g.ESQ_W / 2) - (py + g.PICO[1] / 2), None))
zb = zc + g.PITCH - 0.65 - g.UB_BODY[2] / 2 - 1.0            # [rev8] buttons at the top of the core wall
front = g.FRONT_Y
for name, x in g.BUTTONS:
    add(f"button_{name}", box(x - g.UB_BODY[0] / 2, x + g.UB_BODY[0] / 2, front, front + g.UB_BODY[1], zb - g.UB_BODY[2] / 2, zb + g.UB_BODY[2] / 2), "part")
    add(f"plug_{name}", cbox(x, g.BUTTON_PLUG_Y, 9.9 if name == "power" else 7.4, 5.75, zc + top, zc + top + 7.0), "conn")
checks.append(("core: button body back to the core board front edge (y)", g.CORE_FRONT_Y - (front + g.UB_BODY[1]), None))
checks.append(("core: button underside above the module-port receptacles (z)", (zb - g.UB_BODY[2] / 2) - (z + top + g.USBC[2]), None))
bz = [n for n, _ in g.BUTTONS]
checks.append(("core: gap between the reset and boot buttons (x)", g.BUTTONS[2][1] - g.BUTTONS[1][1] - g.UB_BODY[0], None))

# ---- shell, as a plain tube for scale -------------------------------------------------------------------------------
h = zc + g.PITCH + 2.0
tube = cbox(0, g.AXIS_Y, g.OUTSIDE, g.OUTSIDE, 0, h).cut(cbox(0, g.AXIS_Y, g.OUTSIDE - 2 * g.WALL, g.OUTSIDE - 2 * g.WALL, 2.0, h + 1))
add("shell_outline", tube, "shell", 85)

# ---- interference: every pair of solids except those that are meant to touch -----------------------------------------
solids = {k: v for k, v in shapes.items() if k != "shell_outline" and "standoff" not in k}
names = sorted(solids)
bad = []
for i, a in enumerate(names):
    for b in names[i + 1:]:
        if not solids[a].BoundBox.intersect(solids[b].BoundBox):
            continue
        v = solids[a].common(solids[b]).Volume
        if v > 0.5:
            allowed = ("esq" in a and "esq" in b) or ("esq_tails" in a + b and a.split("_")[0] == b.split("_")[0]) \
                or ("spring" in a + b and ("targets" in a + b or "pico" in a + b)) \
                or ("spring" in a + b and min(len(a), len(b)) <= 8) \
                or ("plug" in a + b and "header" in a + b) or ("usbport" in a and "usbport" in b)      # pins drawn at free length reach into the board they press on
            if not allowed:
                bad.append((a, b, round(v, 1)))

report = []


def say(text):
    """freecadcmd swallows print when piped: the report also goes to build/mech/hub/hub-section.txt."""
    report.append(text)
    App.Console.PrintMessage(text + "\n")


os.makedirs(OUT, exist_ok=True)
say(f"hub section, {N_BATT} battery modules: height to the top of the core section {h:.1f} mm")
for k, zz in lv.items():
    say(f"  {k}: board bottom at z = {zz:.2f}")
fail = False
for text, value, margin in checks:
    flag = "" if value >= 0 and (margin is None or margin >= 0) else "   <-- FAIL"
    fail |= bool(flag)
    say(f"  {text}: {value:.2f} mm" + (f" (left before bottoming: {margin:.2f})" if margin is not None else "") + flag)
for a, b, v in bad:
    say(f"  CLASH {a} / {b}: {v} mm3")
doc.recompute()
doc.saveAs(os.path.join(OUT, "hub-section.FCStd"))
Part.export([o for o in doc.Objects], os.path.join(OUT, "hub-section.step"))
say("wrote " + os.path.normpath(os.path.join(OUT, "hub-section.FCStd")) + " and .step")
open(os.path.join(OUT, "hub-section.txt"), "w").write("\n".join(report) + "\n")
if fail or bad:
    sys.exit(1)
