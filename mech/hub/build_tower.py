"""Hub tower under the core section: connector section, battery module, base, seam test pair (M3 session 6).

  HUB_SCREWS=standoff|long HUB_MAGNETS=diag|sides|three /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd mech/hub/build_tower.py
  HUB_OPTIONS=1 ... (or exec in the GUI): document "hub_tower_options", the variants side by side
  output: build/mech/hub/tower/ (STL as printed, report.txt; read its last line, freecadcmd exits 0 on an exception);
  GUI document "hub_tower" (whole tower, the core section and the radio lid from build_core.py)

Numbers: mech/hub/hub_geom.py. Helpers and the core section come from build_core.py (imported, its main() does not run).

Seams. Pin seams (base / battery module / connector section; the chain's 16 spring pins push them apart): the lower side has
build_core's band and lip with the key, the upper side the board's four insert bosses (the lip has gaps for their bridges).
Magnets (HUB_MAGNETS, g.PIN_SHELVES): the lid's rear-wall pair does not hold here (hold() prints why), so
  diag   one shelf mid-way on the east wall, one in the rear-west corner: only the east one overhangs the battery board
  sides  rev 8: mid-way on both side walls; both overhang the board, which then goes in under one of them
  three  east wall and both rear corners
Screwed seam core / connector: the lip is the inner half of the wall (hub-conn is 108 mm in a 110 mm tower: nothing may
stand inside the wall above it). How the core's screws meet hub-conn's screws, which are right under them (HUB_SCREWS):
  standoff  hub-conn is held by four M2 hex standoffs (stud down into the inserts); the core's bosses stand on them and
            the core's screws end in them. hub-conn stays down when the core is pulled off the 2x25 stack connector.
  long      four M2 x 25 through core board, boss, a loose printed sleeve and hub-conn into the inserts; with the screws
            out nothing holds hub-conn
hub-conn goes in from the top with the host port board on it: the rear wall has a slot, open to the seam, for the
receptacle (the core section closes it).
"""
import os
import sys

import FreeCAD as App
import Part

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "/Users/florin/projects/personal/keyboard/mech/hub"
sys.path.insert(0, HERE)
for _m in ("hub_geom", "build_core"):
    sys.modules.pop(_m, None)
import hub_geom as g  # noqa: E402
import build_core as bc  # noqa: E402
from build_core import BAND, SHELF_D, SHELF_L, SHELF_T, XI, XO, YF, YR, V, box, cyl, fuse, prism_xz, prism_yz, rect, tube  # noqa: E402

OUT = os.path.join(HERE, "..", "..", "build", "mech", "hub", "tower")
N_BATT = bc.N_BATT
LV = g.levels(N_BATT)
M = g.MAGNET
COL = dict(bc.COL, pin=(0.85, 0.7, 0.2), holder=(0.05, 0.05, 0.05))
W_ABOVE = 2.0       # N, estimate: what stands on the upper battery seam (connector and core sections, boards, lid)


def wb(wall, a0, a1, d0, d1, z0, z1):
    """Box on a wall: a along it, d inwards from its inner face."""
    if wall == "rear":
        return box(a0, a1, YR - d1, YR - d0, z0, z1)
    if wall == "front":
        return box(a0, a1, YF + d0, YF + d1, z0, z1)
    if wall == "east":
        return box(XI - d1, XI - d0, a0, a1, z0, z1)
    return box(-XI + d0, -XI + d1, a0, a1, z0, z1)


def wedge(wall, a0, a1, z):
    """45 degree wedge under a shelf whose underside is at z."""
    dz = [(0, z), (SHELF_D, z), (0, z - SHELF_D)]
    if wall == "rear":
        return prism_yz([(YR - d, zz) for d, zz in dz], a0, a1)
    sx = 1 if wall == "east" else -1
    return prism_xz([(sx * (XI - d), zz) for d, zz in dz], a0, a1)


def magnet_xy(wall, c):
    d = 0.7 + M[1] / 2
    return {"rear": (c, YR - d), "east": (XI - d, c), "west": (-XI + d, c)}[wall]


def hold(shelves):
    """Least ratio of holding to lifting moment about the four wall edges: the pins lift at CHAIN_PADS_XY, the magnets
    (g.MAGNET_PULL each, an estimate) and the weight above hold."""
    px, py = g.CHAIN_PADS_XY
    f = 16 * g.PIN_FORCE
    out = {}
    for edge, lever in (("rear", lambda x, y: g.REAR_Y - y), ("front", lambda x, y: y - g.FRONT_Y),
                        ("east", lambda x, y: XO - x), ("west", lambda x, y: x + XO)):
        h = W_ABOVE * lever(0, g.AXIS_Y) + sum(g.MAGNET_PULL * lever(*magnet_xy(w, c)) for w, c in shelves)
        out[edge] = h / (f * lever(px, py))
    return out


def band_lip(z, gaps):
    band = box(-XI, XI, YF, YR, z - 4 - BAND, z).cut(Part.makeLoft([rect(0, z - 4 - BAND), rect(BAND, z - 4)], True))
    band = band.cut(box(-XI + BAND, XI - BAND, YF + BAND, YR - BAND, z - 4.01, z + 1))
    c = g.LIP_CLR
    lip = box(-XI + c, XI - c, YF + c, YR - c, z, z + g.LIP_H).cut(box(-XI + BAND, XI - BAND, YF + BAND, YR - BAND, z - 1, z + 3))
    lip = lip.fuse(box(g.KEY_X - g.KEY_W / 2, g.KEY_X + g.KEY_W / 2, YF + c - g.KEY_D, YF + c, z, z + g.LIP_H))
    for q in gaps:
        lip = lip.cut(q)
    return band.fuse(lip)


def pin_lower(z, shelves, zfloor=None, gaps=()):
    """Lower side of a pin seam at z. Returns (solid, pockets to cut, magnets)."""
    gaps, add, pockets, magnets = list(gaps), [], [], []
    for wall, c in shelves:
        a0, a1 = c - SHELF_L / 2, c + SHELF_L / 2
        gaps.append(wb(wall, a0 - 0.3, a1 + 0.3, -1, SHELF_D + 0.3, z, z + 5))                 # the upper shelf comes down to the seam
        add.append(wb(wall, a0, a1, 0, SHELF_D, z - SHELF_T, z))
        add.append(wedge(wall, a0, a1, z - SHELF_T) if zfloor is None else wb(wall, a0, a1, 0, SHELF_D, zfloor - 0.01, z - SHELF_T))
        zp = z - g.SKIN - M[2] - 0.4
        pockets.append(wb(wall, c - M[0] / 2 - g.POCKET_CLR, c + M[0] / 2 + g.POCKET_CLR, 0.4, SHELF_D + 1, zp, z - g.SKIN))
        magnets.append(wb(wall, c - M[0] / 2, c + M[0] / 2, 0.7, 0.7 + M[1], z - g.SKIN - M[2], z - g.SKIN))
    for x, y in g.MOUNT_XY:                                                        # the board bosses' bridges to the wall
        sx = 1 if x > 0 else -1
        gaps.append(box(min(x, sx * (XI + 1)), max(x, sx * (XI + 1)), y - g.BOSS_D / 2 - 0.3, y + g.BOSS_D / 2 + 0.3, z, z + 5))
    return fuse([band_lip(z, gaps)] + add), pockets, magnets


def pin_upper(z, shelves, zb):
    """Upper side of a pin seam at z, board bottom at zb. Returns (solid, cuts, magnets)."""
    c = g.LIP_CLR
    cuts = [box(g.KEY_X - g.KEY_W / 2 - g.KEY_CLR, g.KEY_X + g.KEY_W / 2 + g.KEY_CLR, YF + c - g.KEY_D - g.KEY_CLR, YF + 0.1, z - 1, z + g.LIP_H + g.KEY_CLR)]
    add, magnets = [], []
    for wall, cc in shelves:
        add.append(wb(wall, cc - SHELF_L / 2, cc + SHELF_L / 2, 0, SHELF_D, z, z + SHELF_T))
        cuts.append(wb(wall, cc - M[0] / 2 - g.POCKET_CLR, cc + M[0] / 2 + g.POCKET_CLR, 0.4, SHELF_D + 1, z + g.SKIN, z + g.SKIN + M[2] + 0.4))
        magnets.append(wb(wall, cc - M[0] / 2, cc + M[0] / 2, 0.7, 0.7 + M[1], z + g.SKIN, z + g.SKIN + M[2]))
    for x, y in g.MOUNT_XY:
        sx = 1 if x > 0 else -1
        add.append(cyl(g.BOSS_D, x, y, z, zb))
        add.append(box(min(x, sx * (XI + 0.5)), max(x, sx * (XI + 0.5)), y - g.BOSS_D / 2, y + g.BOSS_D / 2, z, zb))
        cuts.append(cyl(g.INSERT[0], x, y, zb - g.INSERT[1] - 0.01, zb + 0.01))
    return fuse(add), cuts, magnets


def finish(s, cuts):
    for q in cuts:
        s = s.cut(q)
    return s.removeSplitter()


def pcb(x0, x1, y0, y1, z):
    s = box(x0, x1, y0, y1, z, z + g.T_PCB)
    for x, y in g.MOUNT_XY:
        s = s.cut(cyl(2.2, x, y, z - 1, z + 3))
    return s


def base(shelves):
    z1 = g.BASE_H
    top, pockets, magnets = pin_lower(z1, shelves, zfloor=g.BASE_FLOOR)
    s = tube(0, z1).fuse(box(-XO, XO, g.FRONT_Y, g.REAR_Y, 0, g.BASE_FLOOR)).fuse(top)
    feet = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * (XO - g.FOOT_IN), g.AXIS_Y + sy * (XO - g.FOOT_IN)
            pockets.append(cyl(g.FOOT[0], x, y, -1, g.FOOT[1]))
            feet.append(cyl(g.FOOT[0] - 0.6, x, y, g.FOOT[1] - g.FOOT[2], g.FOOT[1]))
    return finish(s, pockets), {"magnets": (Part.makeCompound(magnets), "magnet"), "feet": (Part.makeCompound(feet), "part")}


def module(i, shelves):
    zb = LV[f"battery{i}"]
    z0, z1, zt = zb - g.SKIRT, zb - g.SKIRT + g.PITCH, zb + g.T_PCB
    up, cuts, m1 = pin_upper(z0, shelves, zb)
    top, pockets, m2 = pin_lower(z1, shelves)
    s = finish(tube(z0, z1).fuse(up).fuse(top), cuts + pockets)
    hx, hy = g.HOLDER_XY
    rx, ry = g.CHAIN_RISER_XY
    px, py = g.CHAIN_PADS_XY
    zc = zt + g.RISER_SPACE
    cx, cy = (rx + px) / 2, (ry + py) / 2
    refs = {"board": (pcb(-47, 47, -47, 47, zb), "board"),
            "holder": (box(hx - g.HOLDER[0] / 2, hx + g.HOLDER[0] / 2, hy - g.HOLDER[1] / 2, hy + g.HOLDER[1] / 2, zt, zt + g.HOLDER[2]), "holder"),
            "chain": (Part.makeCompound([box(rx - 10.16, rx + 10.16, ry - 2.54, ry + 2.54, zt, zc),
                                         box(cx - g.CAP_BOARD[0] / 2, cx + g.CAP_BOARD[0] / 2, cy - g.CAP_BOARD[1] / 2, cy + g.CAP_BOARD[1] / 2, zc, zc + g.T_PCB),
                                         box(px - 10.16, px + 10.16, py - 2.54, py + 2.54, zc + g.T_PCB, zb + g.PITCH - g.TARGET_H),     # pins as pressed
                                         box(px - 10.16, px + 10.16, py - 2.54, py + 2.54, zb - g.TARGET_H, zb)]), "pin"),
            "magnets": (Part.makeCompound(m1 + m2), "magnet")}
    return s, refs


def connector(shelves, screws):
    zb, z1 = LV["conn"], LV["core"] - g.SPLIT
    z0, zt = zb - g.SKIRT, zb + g.T_PCB
    up, cuts, magnets = pin_upper(z0, shelves, zb)
    lip = box(-XI - g.RAB_T, XI + g.RAB_T, YF - g.RAB_T, YR + g.RAB_T, z1, z1 + g.RAB_H).cut(box(-XI, XI, YF, YR, z1 - 1, z1 + 3))
    lip = lip.cut(box(g.KEY_X - g.KEY_W / 2 - g.KEY_CLR, g.KEY_X + g.KEY_W / 2 + g.KEY_CLR, YF - 2, YF + 1, z1, z1 + 3))
    zc = zt + g.USBC[2] / 2
    for x in g.PORT_X:
        cuts.append(box(x - g.PORT_CUT[0] / 2, x + g.PORT_CUT[0] / 2, g.FRONT_Y - 1, YF + 0.01, zc - g.PORT_CUT[1] / 2, zc + g.PORT_CUT[1] / 2))
    zu = zt + g.UP_STANDOFF
    rx, (rw, rd, rh) = g.UP_REC_X, g.USB4085
    cuts.append(box(rx - rw / 2 - 0.3, rx + rw / 2 + 0.3, YR - 0.01, g.REAR_Y + 1, zu + g.T_PCB - 0.3, z1 + 5))        # host port slot, open to the seam
    s = finish(tube(z0, z1).fuse(up).fuse(lip), cuts)
    sx_, sy_ = g.STACK_XY
    jx, jy = g.JUSB_XY
    px, py = g.CHAIN_PADS_XY
    parts, refs = {"connector-section": s}, {}
    refs["board"] = (pcb(-g.CONN_X, g.CONN_X, g.CONN_FRONT, g.CONN_REAR, zb), "board")
    refs["parts"] = (Part.makeCompound(
        [box(sx_ - 32.0, sx_ + 32.0, sy_ - g.ESQ_W / 2, sy_ + g.ESQ_W / 2, zt, zt + g.ESQ_BODY_H), box(sx_ - 31.75, sx_ + 31.75, sy_ - 1.6, sy_ + 1.6, zt - g.ESQ_TAIL, zb),
         cyl(g.CAN[0], 30, 0, zt, zt + g.CAN[1]), box(jx - 3.2, jx + 3.2, jy - 9.1, jy + 9.1, zt, zt + 4.05),
         box(px - 10.16, px + 10.16, py - 2.54, py + 2.54, zb - g.TARGET_H, zb)]
        + [box(x - g.USBC[0] / 2, x + g.USBC[0] / 2, g.CONN_FRONT - g.USBC_NOSE, g.CONN_FRONT - g.USBC_NOSE + g.USBC[1], zt, zt + g.USBC[2]) for x in g.PORT_X]), "part")
    refs["usb_port"] = (Part.makeCompound(
        [box(g.UP_X[0], g.UP_X[1], g.UP_Y[0], g.UP_Y[1], zu, zu + g.T_PCB), box(rx - rw / 2, rx + rw / 2, g.REAR_Y - rd, g.REAR_Y, zu + g.T_PCB, zu + g.T_PCB + rh)]
        + [cyl(4.0, x, y, zt, zu) for x, y in g.UP_MOUNT_XY]), "pod")
    refs["magnets"] = (Part.makeCompound(magnets), "magnet")
    if screws == "standoff":
        refs["standoffs"] = (Part.makeCompound([bc.hexagon(g.STANDOFF[0], x, y, zt, zt + g.STANDOFF[1]).fuse(cyl(2.0, x, y, zt - g.STANDOFF[2], zt)) for x, y in g.MOUNT_XY]), "pin")
    else:
        x, y = g.MOUNT_XY[0]
        parts["sleeve"] = cyl(g.BOSS_D, x, y, zt, z1).cut(cyl(g.M2_CLEAR, x, y, zt - 1, z1 + 1))
        refs["sleeves"] = (Part.makeCompound([cyl(g.BOSS_D, x, y, zt, z1).cut(cyl(g.M2_CLEAR, x, y, zt - 1, z1 + 1)) for x, y in g.MOUNT_XY[1:]]), "loose")
    return parts, refs


def test_pair(shelves):
    """Two low rings with one pin seam between them and a bar with a hole at the pins' place in each: lift by the upper
    hole, hang weight on the lower one."""
    px, py = g.CHAIN_PADS_XY
    bar = lambda z0, z1: box(px - 4, px + 4, YF - 0.01, YR + 0.01, z0, z1).cut(cyl(5.0, px, py, z0 - 1, z1 + 1))  # noqa: E731
    ends = [box(px - 4.3, px + 4.3, y0, y0 + 4, 0, 5) for y0 in (YF - 1, YR - 3)]
    top, pockets, m1 = pin_lower(0, shelves, gaps=ends)
    low = tube(-10, 0).fuse(top).common(box(-XO, XO, g.FRONT_Y, g.REAR_Y, -10, 5)).fuse(bar(-10, -7))
    up, cuts, m2 = pin_upper(0, shelves, g.SKIRT)
    return {"seam-test-lower": finish(low, pockets), "seam-test-upper": finish(tube(0, 8).fuse(up).fuse(bar(0, 3)), cuts)}, m1 + m2


def clashes(items):
    """items {name: (shape, is_ref)}: every pair except ref / ref."""
    out, names = [], list(items)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            (sa, ra), (sb, rb) = items[a], items[b]
            if (ra and rb) or not sa.BoundBox.intersect(sb.BoundBox):
                continue
            v = sa.common(sb).Volume
            if v > 0.05:
                out.append(f"CLASH {a} / {b}: {v:.2f} mm3")
    return out, len(names)


def show(doc, name, shape, col, dx=0.0):
    o = doc.addObject("Part::Feature", name.replace("-", "_"))
    s = shape.copy()
    s.translate(V(dx, 0, 0))
    o.Shape = s
    if getattr(o, "ViewObject", None):
        o.ViewObject.ShapeColor = COL[col]
        o.ViewObject.Transparency = {"shell": 35, "lid": 70}.get(col, 0)


def tower(screws, magnets):
    """Everything from the base to the lid. Returns items {name: (shape, colour, is_ref)} and the printed parts."""
    shelves = g.PIN_SHELVES[magnets]
    items, prints = {}, {}
    s, refs = base(shelves)
    items["base"] = (s, "shell", False)
    prints["base"] = s
    items.update({f"base_{k}": (v[0], v[1], True) for k, v in refs.items()})
    for i in range(N_BATT, 0, -1):
        s, refs = module(i, shelves)
        items[f"battery{i}-module"] = (s, "shell", False)
        prints["battery-module"] = s
        items.update({f"battery{i}_{k}": (v[0], v[1], True) for k, v in refs.items()})
    parts, refs = connector(shelves, screws)
    prints.update(parts)
    items.update({k: (v, "loose" if k == "sleeve" else "shell", False) for k, v in parts.items()})
    items.update({f"conn_{k}": (v[0], v[1], True) for k, v in refs.items()})
    parts, refs, _ = bc.build()
    items.update({k: (v, "lid" if k.startswith("lid") else "loose" if k == "carrier-sleeve" else "shell", False) for k, v in parts.items()})
    items.update({f"core_{k}": (v[0], v[1], True) for k, v in refs.items()})
    return items, prints


def main():
    report = []
    os.makedirs(OUT, exist_ok=True)
    options = bool(os.environ.get("HUB_OPTIONS"))
    screws, magnets = os.environ.get("HUB_SCREWS", "standoff"), os.environ.get("HUB_MAGNETS", "diag")
    for name, sh in list(g.PIN_SHELVES.items()) + [("as the lid (rear wall only)", tuple(("rear", x) for x in g.SHELF_X))]:
        h = hold(sh)
        report.append(f"hold, magnets {name}: " + ", ".join(f"{k} edge {v:.2f}" for k, v in h.items()) + f"  (least {min(h.values()):.2f}; under 1 the seam opens; "
                      f"pins {16 * g.PIN_FORCE:.1f} N, {g.MAGNET_PULL:.0f} N a pair and {W_ABOVE:.0f} N of weight are estimates)")
    if options:
        if App.listDocuments().get("hub_tower_options"):
            App.closeDocument("hub_tower_options")
        doc = App.newDocument("hub_tower_options")
        for i, name in enumerate(g.PIN_SHELVES):
            s, refs = module(1, g.PIN_SHELVES[name])
            pre = f"M{i + 1}_{name}__"
            show(doc, pre + "module", s, "shell", 150.0 * i)
            for k, v in refs.items():
                show(doc, pre + k, v[0], v[1], 150.0 * i)
        core = bc.build()[0]["core-section"]
        for i, name in enumerate(("standoff", "long")):
            parts, refs = connector(g.PIN_SHELVES[magnets], name)
            pre, dx = f"S{i + 1}_{name}__", 150.0 * (i + len(g.PIN_SHELVES))
            show(doc, pre + "core_section", core, "lid", dx)
            show(doc, pre + "core_board", box(-47, 47, g.CORE_FRONT_Y, 47, LV["core"], LV["core"] + g.T_PCB), "board", dx)
            for k, v in parts.items():
                show(doc, pre + k, v, "loose" if k == "sleeve" else "shell", dx)
            for k, v in refs.items():
                show(doc, pre + k, v[0], v[1], dx)
        doc.recompute()
    else:
        if App.listDocuments().get("hub_tower"):
            App.closeDocument("hub_tower")
        doc = App.newDocument("hub_tower")
        items, prints = tower(screws, magnets)
        for k, (s, col, _) in items.items():
            show(doc, k, s, col)
        tp, tm = test_pair(g.PIN_SHELVES[magnets])
        for k, s in tp.items():
            show(doc, k, s, "shell", 150.0)
        show(doc, "seam_test_magnets", Part.makeCompound(tm), "magnet", 150.0)
        doc.recompute()
        bad, n = clashes({k: (s, r) for k, (s, _, r) in items.items()})
        b2, _ = clashes({k: (s, False) for k, s in tp.items()})
        bad += b2
        zb = LV["battery1"]
        east = max((XI - SHELF_D for w, _ in g.PIN_SHELVES[magnets] if w == "east"), default=XI)
        west = max((XI - SHELF_D for w, _ in g.PIN_SHELVES[magnets] if w == "west"), default=XI)
        report.append(f"screws {screws}, magnets {magnets}, {N_BATT} battery modules: base 0 .. {g.BASE_H:.1f}, battery module {g.PITCH:.1f} mm, "
                      f"connector section {LV['conn'] - g.SKIRT:.1f} .. {LV['core'] - g.SPLIT:.1f} ({LV['core'] - g.SPLIT - LV['conn'] + g.SKIRT:.1f} mm)")
        report.append(f"battery board (94 mm) between the shelves: opening {east + west:.1f} mm; goes in {max(0.0, 47 - east) + 0.3:.1f} mm off centre"
                      + (", under the west shelf first" if west < 47 else "") + f"; holder to the west shelf when shifted: {(-g.HOLDER[0] / 2 + g.HOLDER_XY[0]) - (47 - east + 0.3) + west:.2f} mm" * (west < 47))
        if screws == "standoff":
            report.append(f"core screws: M2 x {g.T_PCB + g.SPLIT + 3:.0f} into M2 x {g.STANDOFF[1]:.0f} + {g.STANDOFF[2]:.0f} standoffs (stud {g.STANDOFF[2] - g.T_PCB:.1f} mm in the insert); battery boards M2 x 5")
        else:
            report.append(f"core screws: M2 x {g.T_PCB + g.SPLIT + g.STANDOFF[1] + g.T_PCB + 4:.0f} (M2 x 25) through core board, boss, sleeve and hub-conn; battery boards M2 x 5")
        report.append(f"host receptacle top {LV['conn'] + g.T_PCB + g.UP_STANDOFF + g.T_PCB + g.USB4085[2] - (LV['core'] - g.SPLIT):+.2f} mm against the core seam; "
                      f"stack tails end {g.ESQ_TAIL - g.T_PCB - g.SKIRT:.2f} mm under the connector section's seam (base floor is {g.BASE_H - g.BASE_FLOOR:.1f} mm under it)")
        for k, s in list(prints.items()) + list(tp.items()):
            s = s.copy()
            s.translate(V(0, 0, -s.BoundBox.ZMin))
            s.exportStl(os.path.join(OUT, k + ".stl"))
            bb = s.BoundBox
            report.append(f"  {k}.stl: {bb.XLength:.1f} x {bb.YLength:.1f} x {bb.ZLength:.1f} mm, {s.Volume / 1000:.1f} cm3")
        report += bad
        report.append(f"{n} solids checked, {len(bad)} clashes")
    for line in report:
        App.Console.PrintMessage(line + "\n")
    open(os.path.join(OUT, "options.txt" if options else "report.txt"), "w").write("\n".join(report) + "\n")


main()
