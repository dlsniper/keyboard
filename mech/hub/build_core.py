"""Hub tower, core section: shell, lid and the radio (carrier hub-radio + pod), M3 session 5.

  HUB_HEIGHT=lid|section|ring HUB_SUPPORT=shelf|tab /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd mech/hub/build_core.py
  HUB_OPTIONS=1 ... (or exec in the GUI): document "hub_core_options", the variants side by side
  output: build/mech/hub/core/ (STL as printed, report.txt); GUI document "hub_core"

Numbers: mech/hub/hub_geom.py. The section model of the whole stack stays mech/hub/build_hub.py.

Shell (rev 8's seam concept, redrawn for the 114 mm tower): the core section is a ring of wall from SPLIT under the
core board (screwed seam to the connector section: bosses with through holes at the board's four screws) up to the lid
seam, LID_SEAM above the board's top. The lip stands on a 1.4 mm band of the wall (rev 8's lip had nothing under it).
Lid magnets: two shelves on the rear wall behind the core board, each on a 45 degree wedge (FDM).

Where the pod's extra height comes from (HUB_HEIGHT):
  lid      the core section is the same with and without the radio; the radio comes with a deeper lid
  section  the core section itself is taller, one flat lid
  ring     a ring between the core section and the flat lid
What carries the carrier (HUB_SUPPORT):
  shelf    a shelf on the west wall under the carrier's west edge with an open pocket for an M2 nut, and a loose printed
           sleeve with a nut pocket standing on the core board under the east screw; nothing overhangs the core board
  tab      (board change) the carrier grows a tab to the core board's west-rear screw and stands there on a standoff
The pod's far end (it points to the front, 32 mm past its screws) rests on a horn on the west wall.
"""
import math
import os
import sys

import FreeCAD as App
import Part

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "/Users/florin/projects/personal/keyboard/mech/hub"
sys.path.insert(0, HERE)
import hub_geom as g  # noqa: E402

V = App.Vector
OUT = os.path.join(HERE, "..", "..", "build", "mech", "hub", "core")
N_BATT = 2
XO, XI = g.OUTSIDE / 2, g.OUTSIDE / 2 - g.WALL
YF, YR = g.FRONT_Y + g.WALL, g.REAR_Y - g.WALL          # inner faces of the front and rear walls
ZC = g.levels(N_BATT)["core"]
ZT = ZC + g.T_PCB                                        # core board top: the heights below are measured from it
BAND = g.LIP_T + g.LIP_CLR                               # 1.4: wall band that carries the lip
SHELF_T = g.SKIN + g.MAGNET[2] + 0.4 + g.SHELF_FLOOR     # 3.6
SHELF_D = g.MAGNET[1] + 2 * g.POCKET_CLR + 0.4           # 11.0
SHELF_L = g.MAGNET[0] + 2 * g.POCKET_CLR + 2.4           # 23.0
Z_CAR = ZT + g.BAY_GAP                                   # carrier underside
Z_POD = Z_CAR + g.T_PCB + g.BAY_GAP                      # pod underside
Z_NEED = Z_POD + g.T_PCB + g.POD_TOP + g.RADIO_AIR       # roof underside with the radio
COL = dict(shell=(0.8, 0.8, 0.85), lid=(0.55, 0.6, 0.8), loose=(0.9, 0.5, 0.1), board=(0.1, 0.45, 0.2), part=(0.25, 0.25, 0.28),
           pod=(0.95, 0.75, 0.1), magnet=(0.7, 0.1, 0.1))


def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def cyl(d, x, y, z0, z1):
    return Part.makeCylinder(d / 2, z1 - z0, V(x, y, z0))


def prism_xz(pts, y0, y1):
    return Part.Face(Part.makePolygon([V(x, y0, z) for x, z in pts + pts[:1]])).extrude(V(0, y1 - y0, 0))


def prism_yz(pts, x0, x1):
    return Part.Face(Part.makePolygon([V(x0, y, z) for y, z in pts + pts[:1]])).extrude(V(x1 - x0, 0, 0))


def prism_xy(pts, z0, z1):
    return Part.Face(Part.makePolygon([V(x, y, z0) for x, y in pts + pts[:1]])).extrude(V(0, 0, z1 - z0))


def hexagon(af, x, y, z0, z1):
    r = af / 2 / math.cos(math.radians(30))
    return prism_xy([(x + r * math.cos(math.radians(60 * i)), y + r * math.sin(math.radians(60 * i))) for i in range(6)], z0, z1)


def fuse(shapes):
    s = shapes[0]
    for o in shapes[1:]:
        s = s.fuse(o)
    return s


def tube(z0, z1):
    return box(-XO, XO, g.FRONT_Y, g.REAR_Y, z0, z1).cut(box(-XI, XI, YF, YR, z0 - 1, z1 + 1))


def rect(i, z):
    p = [V(-XI + i, YF + i, z), V(XI - i, YF + i, z), V(XI - i, YR - i, z), V(-XI + i, YR - i, z)]
    return Part.makePolygon(p + p[:1])


def seam_top(z, gaps):
    """Lower side of a magnet seam at z: band on the wall (chamfered underneath), lip, key, rear shelves on wedges.
    Returns (solid to add, pockets to cut, magnets)."""
    band = box(-XI, XI, YF, YR, z - 4 - BAND, z).cut(Part.makeLoft([rect(0, z - 4 - BAND), rect(BAND, z - 4)], True))
    band = band.cut(box(-XI + BAND, XI - BAND, YF + BAND, YR - BAND, z - 4.01, z + 1))
    c = g.LIP_CLR
    lip = box(-XI + c, XI - c, YF + c, YR - c, z, z + g.LIP_H).cut(box(-XI + BAND, XI - BAND, YF + BAND, YR - BAND, z - 1, z + 3))
    lip = lip.fuse(box(g.KEY_X - g.KEY_W / 2, g.KEY_X + g.KEY_W / 2, YF + c - g.KEY_D, YF + c, z, z + g.LIP_H))
    add, pockets, magnets = [band, lip], [], []
    for cx in g.SHELF_X:
        x0, x1 = cx - SHELF_L / 2, cx + SHELF_L / 2
        add.append(box(x0, x1, YR - SHELF_D, YR, z - SHELF_T, z))
        add.append(prism_yz([(YR, z - SHELF_T), (YR - SHELF_D, z - SHELF_T), (YR, z - SHELF_T - SHELF_D)], x0, x1))
        gaps = gaps + [box(x0 - 0.3, x1 + 0.3, YR - 3, YR + 1, z, z + 5)]          # the upper shelf comes down to the seam
        zp = z - g.SKIN - g.MAGNET[2] - 0.4
        pockets.append(box(cx - g.MAGNET[0] / 2 - g.POCKET_CLR, cx + g.MAGNET[0] / 2 + g.POCKET_CLR, YR - SHELF_D - 1, YR - 0.4, zp, z - g.SKIN))
        magnets.append(box(cx - g.MAGNET[0] / 2, cx + g.MAGNET[0] / 2, YR - 0.7 - g.MAGNET[1], YR - 0.7, z - g.SKIN - g.MAGNET[2], z - g.SKIN))
    s = fuse(add)
    for q in gaps:
        s = s.cut(q)
    return s, pockets, magnets


def seam_bottom(z, z_fill):
    """Upper side of a magnet seam at z: key notch (to cut), rear shelves, filled up to z_fill where that is nearer than
    a 45 degree wedge (lids are printed roof down). Returns (solid to add, cuts, magnets)."""
    c = g.LIP_CLR
    cuts = [box(g.KEY_X - g.KEY_W / 2 - g.KEY_CLR, g.KEY_X + g.KEY_W / 2 + g.KEY_CLR, YF + c - g.KEY_D - g.KEY_CLR, YF + 0.1, z - 1, z + g.LIP_H + g.KEY_CLR)]
    add, magnets = [], []
    for cx in g.SHELF_X:
        x0, x1 = cx - SHELF_L / 2, cx + SHELF_L / 2
        add.append(box(x0, x1, YR - SHELF_D, YR, z, z + SHELF_T))
        w = prism_yz([(YR, z + SHELF_T), (YR - SHELF_D, z + SHELF_T), (YR, z + SHELF_T + SHELF_D)], x0, x1)
        add.append(w.common(box(x0, x1, YR - SHELF_D, YR, z, z_fill)))
        cuts.append(box(cx - g.MAGNET[0] / 2 - g.POCKET_CLR, cx + g.MAGNET[0] / 2 + g.POCKET_CLR, YR - SHELF_D - 1, YR - 0.4, z + g.SKIN, z + g.SKIN + g.MAGNET[2] + 0.4))
        magnets.append(box(cx - g.MAGNET[0] / 2, cx + g.MAGNET[0] / 2, YR - 0.7 - g.MAGNET[1], YR - 0.7, z + g.SKIN, z + g.SKIN + g.MAGNET[2]))
    return fuse(add), cuts, magnets


def lid(z, rim):
    s = box(-XO, XO, g.FRONT_Y, g.REAR_Y, z, z + rim + g.LID_ROOF).cut(box(-XI, XI, YF, YR, z - 1, z + rim))
    add, cuts, magnets = seam_bottom(z, z + rim + 0.1)
    s = s.fuse(add)
    for q in cuts:
        s = s.cut(q)
    return s.removeSplitter(), magnets


def H(a, t):
    return g.CAR_XY[0] - a, g.CAR_XY[1] - t


def build(height="lid", support="shelf", radio=True):
    """Returns parts {name: shape}, refs {name: (shape, colour)}, report lines."""
    parts, refs, rep = {}, {}, []
    z0 = ZC - g.SPLIT
    z1 = ZT + g.LID_SEAM
    need = Z_NEED - (z1 + g.LID_RIM)                   # extra height for the radio
    if height == "section":
        z1 += need
    px0, px1 = H(g.POD_A, 0)[0], H(-g.POD_A, 0)[0]     # pod west / east edge
    py0, py1 = H(0, g.POD_T[1])[1], H(0, g.POD_T[0])[1]  # pod front end (its rear edge) / rear end in the tower
    pod_gap = [box(-XI - 0.01, px0 + 1.5, py0 - 2, py1 + 2, Z_POD - 4.0, Z_POD + 20)] if radio else []   # no band / lip beside the pod
    # ---- core section
    top, pockets, magnets = seam_top(z1, pod_gap if height == "section" else [])
    sec = tube(z0, z1).fuse(top)
    cuts = list(pockets)
    c = g.LIP_CLR
    # screwed seam to the connector section (M3 session 6): a rabbet in the wall's inner half takes that section's lip (hub-conn fills
    # the tower, so nothing may stand inside the wall there); the rabbet is left out over the key's width (rib in a gap of the lip)
    ri = g.RAB_T + g.RAB_CLR
    zr = z0 + g.RAB_H + g.RAB_CLR
    rab = box(-XI - ri, XI + ri, YF - ri, YR + ri, z0 - 1, zr).fuse(Part.makeLoft([rect(-ri, zr), rect(0, zr + ri)], True))   # 45 degrees above: printable
    rab = rab.cut(box(-XI, XI, YF, YR, z0 - 2, z0 + 5))
    cuts.append(rab.cut(box(g.KEY_X - g.KEY_W / 2, g.KEY_X + g.KEY_W / 2, YF - 2, YF + 1, z0 - 2, z0 + 5)))
    cuts.append(box(g.UP_REC_X - g.USB4085[0] / 2 - 0.3, g.UP_REC_X + g.USB4085[0] / 2 + 0.3, YR - 1, g.REAR_Y + 1, z0 - 1, z0 + g.HOST_NOTCH))  # host receptacle's top
    for x, y in g.CORE_XY:                              # bosses under the board, fused to the side wall; the screw passes through
        sx = 1 if x > 0 else -1
        sec = sec.fuse(cyl(g.BOSS_D, x, y, z0, ZC)).fuse(box(min(x, sx * (XI + 0.5)), max(x, sx * (XI + 0.5)), y - g.BOSS_D / 2, y + g.BOSS_D / 2, z0, ZC))
        cuts.append(cyl(g.M2_CLEAR, x, y, z0 - 1, ZC + 1))
    zb = ZC + g.PITCH - 0.65 - g.UB_BODY[2] / 2 - 1.0   # button centre (build_hub.py)
    buttons = []
    for name, x in g.BUTTONS:
        cuts.append(box(x - g.UB_CUT / 2, x + g.UB_CUT / 2, g.FRONT_Y - 1, YF + BAND + 0.1, zb - g.UB_CUT / 2, zb + g.UB_CUT / 2))
        buttons.append(box(x - g.UB_BODY[0] / 2, x + g.UB_BODY[0] / 2, g.FRONT_Y, g.FRONT_Y + g.UB_BODY[1], zb - g.UB_BODY[2] / 2, zb + g.UB_BODY[2] / 2))
        buttons.append(box(x - g.UB_BEZEL / 2, x + g.UB_BEZEL / 2, g.FRONT_Y - 1.4, g.FRONT_Y, zb - g.UB_BEZEL / 2, zb + g.UB_BEZEL / 2))
        buttons.append(box(x - 4.95, x + 4.95, g.BUTTON_PLUG_Y - 2.9, g.BUTTON_PLUG_Y + 2.9, ZT, ZT + 7.0))
    # ---- reference solids
    px, py = g.PICO_XY
    zp = ZT + g.PICO_UNDER
    ex, ey = g.EXP_XY
    sx_, sy_ = g.STACK_XY
    refs["core_board"] = (box(-g.BOARD / 2, g.BOARD / 2, g.CORE_FRONT_Y, g.BOARD / 2, ZC, ZT), "board")
    refs["core_parts"] = (Part.makeCompound(buttons + [
        box(sx_ - 32.0, sx_ + 32.0, sy_ - g.ESQ_W / 2, sy_ + g.ESQ_W / 2, ZT, ZT + g.ESQ_BODY_H),
        box(px - 25.4, px + 25.4, py + 8.89 - 1.27, py + 8.89 + 1.27, ZT, zp), box(px - 25.4, px + 25.4, py - 8.89 - 1.27, py - 8.89 + 1.27, ZT, zp),
        box(ex - 6.35, ex + 6.35, ey - 2.54, ey + 2.54, ZT, ZT + (g.BAY_GAP if radio else 8.5))]), "part")
    refs["pico"] = (box(px - g.PICO[0] / 2, px + g.PICO[0] / 2, py - g.PICO[1] / 2, py + g.PICO[1] / 2, zp, zp + g.PICO[2] + 2.1), "board")
    if radio:
        out = list(g.CAR_OUT)
        if support == "tab":
            out = [(-52.0, 32.5), (-50.5, 32.5), (-50.5, 16.0), (-39.5, 16.0), (-39.5, 32.5)] + out[1:]
        car = prism_xy(out, Z_CAR, Z_CAR + g.T_PCB)
        hx0, hx1 = H(7.7, 0)[0], H(-7.7, 0)[0]
        hy0, hy1 = H(0, 9.6)[1], H(0, 4.4)[1]
        refs["carrier"] = (car, "board")
        zt_pod = Z_POD + g.T_PCB
        mx = H(7.0, 0)[0]
        ux = H(-9.0, 0)[0]
        pod = [box(px0, px1, py0, py1, Z_POD, zt_pod),
               box(hx0, hx1, hy0, hy1, Z_CAR + g.T_PCB, Z_POD),                                  # bay header and socket
               box(mx - 5.3, mx + 5.3, py0 + 0.3, py0 + 0.3 + 15.6, zt_pod, zt_pod + 2.05),       # radio module, antenna end to the front
               box(ux - 4.47, ux + 4.47, py0 - g.USB4085_OVER, py0 - g.USB4085_OVER + 9.8, zt_pod, zt_pod + g.POD_TOP),
               box(ux - 4.47, ux + 4.47, py0 + 0.5, py0 + 8.0, Z_POD - 1.6, Z_POD),               # its through-hole tails
               box(H(-5.3, 0)[0], H(-11.7, 0)[0], H(0, 39.0)[1], H(0, 27.0)[1], zt_pod, zt_pod + 2.0)]
        screws = [H(a, t) for a, t in g.BAY_SCREWS]                                               # west, east
        pod += [cyl(4.6, x, y, Z_CAR + g.T_PCB, Z_POD).cut(cyl(2.3, x, y, Z_CAR, Z_POD + 1)) for x, y in screws]   # the modules' bay sleeves
        refs["pod"] = (Part.makeCompound(pod), "pod")
        (qx, qy), (wx, wy) = screws                                # a = -11.5 is the east one in the tower
        if support == "shelf":
            # shelf under the carrier's west edge: ends 0.3 mm outside the core board's edge; narrower beside the bay header's tails
            e1, e2 = -g.BOARD / 2 - 0.3, hx0 - 0.7
            th = 3.5
            sh = prism_xz([(-XI - 0.01, Z_CAR), (e1, Z_CAR), (e1, Z_CAR - th), (-XI - 0.01, Z_CAR - th - (XI + e1))], out[0][1] - 0.5, hy0 - 1.5)
            sh = sh.fuse(prism_xz([(-XI - 0.01, Z_CAR), (e2, Z_CAR), (e2, Z_CAR - th), (-XI - 0.01, Z_CAR - th - (XI + e2))], hy0 - 1.5, out[-1][1] + 0.5))
            sec = sec.fuse(sh)
            cuts += [hexagon(g.NUT[0], wx, wy, Z_CAR - g.NUT[1] - 0.2, Z_CAR + 1), cyl(g.M2_CLEAR, wx, wy, Z_CAR - 8, Z_CAR + 1)]
            prop = cyl(6.0, qx, qy, ZT, Z_CAR).cut(cyl(g.M2_CLEAR, qx, qy, ZT - 1, Z_CAR + 1)).cut(hexagon(g.NUT[0], qx, qy, Z_CAR - g.NUT[1] - 0.2, Z_CAR + 1))
            parts["carrier-sleeve"] = prop
            rep.append(f"carrier: shelf on the west wall to x = {e1:.1f} / {e2:.1f} (core board edge {-g.BOARD / 2:.1f}), top {g.BAY_GAP:.2f} above the core board; "
                       f"M2 nut pocket at ({wx:.1f}, {wy:.1f}); nut sleeve {g.BAY_GAP:.2f} mm on the core board at ({qx:.1f}, {qy:.1f}); "
                       f"screws M2 x {2 * g.T_PCB + g.BAY_GAP + g.NUT[1]:.1f} (M2 x 16) through pod, bay sleeve and carrier")
        else:
            mxy = g.CORE_XY[1] if g.CORE_XY[1][0] < 0 and g.CORE_XY[1][1] > 0 else (-g.HOLE_X, 20.0)
            refs["standoff"] = (cyl(4.0, mxy[0], mxy[1], ZT, Z_CAR), "loose")
            rep.append(f"carrier: tab to the core board's screw at {mxy}, on an M2 standoff {g.BAY_GAP:.2f} mm (11 mm + washer); "
                       f"tab edge {px - g.PICO[0] / 2 - (-39.5):.1f} mm from the Pico's antenna end; hub-radio is placed and routed again")
        # horn under the pod's west edge near its far end, behind the antenna area
        hy = (py0 + 6.0, py0 + 18.0)
        hx = px0 + 3.0
        zh = Z_POD - 0.1
        horn = prism_xz([(-XI - 0.01, zh), (hx, zh), (hx, ZT + 9.0), (-XI - 0.01, ZT + 9.0 - (XI + hx))], *hy)
        if height != "section":
            horn = horn.cut(box(-XI - 1, -XI + g.LIP_CLR, hy[0] - 1, hy[1] + 1, z1, zh + 1))      # the lid's (ring's) wall passes outside it
        sec = sec.fuse(horn)
        rep.append(f"pod: x {px0:.1f} .. {px1:.1f} ({px0 + XI:.2f} mm from the west wall), y {py0:.2f} .. {py1:.2f}, underside {Z_POD - ZT:.2f}, "
                   f"USB-C shell top {Z_POD + g.T_PCB + g.POD_TOP - ZT:.2f} above the core board; horn under its west edge y {hy[0]:.1f} .. {hy[1]:.1f}, {hx - px0:.1f} mm wide")
    for q in cuts:
        sec = sec.cut(q)
    parts["core-section"] = sec.removeSplitter()
    refs["magnets"] = (Part.makeCompound(magnets), "magnet")
    # ---- lid(s), ring
    zl = z1
    if radio and height == "ring":
        top, pockets, mg = seam_top(z1 + need, pod_gap)
        add, cuts, mg2 = seam_bottom(z1, z1 + need)
        ring = tube(z1, z1 + need).fuse(top).fuse(add)
        for q in pockets + cuts:
            ring = ring.cut(q)
        parts["ring"] = ring.common(box(-XO, XO, g.FRONT_Y, g.REAR_Y, z1, z1 + need + 5)).removeSplitter()
        zl = z1 + need
    rim = g.LID_RIM + (need if radio and height == "lid" else 0)
    name = "lid-radio" if radio and height == "lid" else "lid"
    parts[name], mg = lid(zl, rim)
    top_z = zl + rim + g.LID_ROOF
    rep.insert(0, f"height {height}, support {support}, radio {radio}: section {z0 - ZT:.1f} .. {z1 - ZT:.1f} from the core board's top ({z1 - z0:.1f} mm), "
               f"lid rim {rim:.1f} + roof {g.LID_ROOF:.1f}; room above the core board {top_z - g.LID_ROOF - ZT:.1f} mm; tower top at {top_z:.1f} mm with {N_BATT} battery modules")
    return parts, refs, rep


def clashes(parts, refs):
    out = []
    names = list(parts) + list(refs)
    shp = {**parts, **{k: v[0] for k, v in refs.items()}}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if a in refs and b in refs:
                continue
            if not shp[a].BoundBox.intersect(shp[b].BoundBox):
                continue
            v = shp[a].common(shp[b]).Volume
            if v > 0.05:
                out.append(f"CLASH {a} / {b}: {v:.2f} mm3")
    return out


def show(doc, prefix, parts, refs, dx=0.0):
    for k, s in list(parts.items()) + [(k, v[0]) for k, v in refs.items()]:
        o = doc.addObject("Part::Feature", (prefix + k).replace("-", "_"))
        s = s.copy()
        s.translate(V(dx, 0, 0))
        o.Shape = s
        if getattr(o, "ViewObject", None):
            col = refs[k][1] if k in refs else ("lid" if k.startswith(("lid", "ring")) else "loose" if k == "carrier-sleeve" else "shell")
            o.ViewObject.ShapeColor = COL[col]
            o.ViewObject.Transparency = 70 if col == "lid" else 35 if col == "shell" else 0


def main():
    report = []
    os.makedirs(OUT, exist_ok=True)
    if os.environ.get("HUB_OPTIONS"):
        if App.listDocuments().get("hub_core_options"):
            App.closeDocument("hub_core_options")
        doc = App.newDocument("hub_core_options")
        for i, (prefix, kw) in enumerate((("H1_deep_lid__", dict(height="lid")), ("H2_tall_section__", dict(height="section")),
                                          ("H3_ring__", dict(height="ring")), ("S2_tab__", dict(height="lid", support="tab")),
                                          ("W_wired__", dict(radio=False)))):
            parts, refs, rep = build(**kw)
            show(doc, prefix, parts, refs, 150.0 * i)
            report += [prefix] + rep + clashes(parts, refs)
        doc.recompute()
    else:
        height, support = os.environ.get("HUB_HEIGHT", "lid"), os.environ.get("HUB_SUPPORT", "shelf")
        if App.listDocuments().get("hub_core"):
            App.closeDocument("hub_core")
        doc = App.newDocument("hub_core")
        parts, refs, rep = build(height, support)
        bad = clashes(parts, refs)
        wired, wrefs, wrep = build(height, support, radio=False)
        bad += ["wired: " + b for b in clashes(wired, wrefs)]
        if "lid-radio" in parts:
            parts["lid"] = wired["lid"]                 # the flat lid for a hub without the radio
            refs["flat_lid_hidden"] = refs.pop("magnets")
        show(doc, "", {k: v for k, v in parts.items() if k != "lid" or "lid-radio" not in parts}, {k: v for k, v in refs.items() if k != "flat_lid_hidden"})
        doc.recompute()
        report += rep + wrep[:1] + bad
        for k, s in parts.items():
            s = s.copy()
            if k.startswith("lid"):
                s.rotate(V(0, g.AXIS_Y, s.BoundBox.ZMax), V(1, 0, 0), 180)     # printed roof down
            s.translate(V(0, 0, -s.BoundBox.ZMin))
            s.exportStl(os.path.join(OUT, k + ".stl"))
            bb = s.BoundBox
            report.append(f"  {k}.stl: {bb.XLength:.1f} x {bb.YLength:.1f} x {bb.ZLength:.1f} mm, {s.Volume / 1000:.1f} cm3")
        report.append(f"{len(bad)} clashes")
    for line in report:
        App.Console.PrintMessage(line + "\n")
    open(os.path.join(OUT, "options.txt" if os.environ.get("HUB_OPTIONS") else "report.txt"), "w").write("\n".join(report) + "\n")


if globals().get("__name__") != "build_core":       # build_tower.py imports this file for its helpers and build()
    main()
