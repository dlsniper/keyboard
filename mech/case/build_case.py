"""Key-module shell (M3 step 1): tray, port-bay cover, spacers and fit-print pieces for one key module.

Run (from the repo root; numpad is the default, CASE_MODULE=left|right|numpad picks another):
  /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd mech/case/build_case.py
Input: build/case/<name>.json, written by tools/case_dump.py (KiCad's Python) from layout/keys.json, the routed key
board and the plate. Re-run case_dump.py after a key board is placed again.
Output: build/case/<name>/ (report.txt, <name>-case.FCStd, STEP of the assembly, STL per printed part and fit piece).
In the FreeCAD GUI (MCP: execute_python_file) the same code fills the document "case_<name>" with coloured parts.

Frame: X = KiCad x - centre, Y = -(KiCad y - centre) (rear = +Y for an unrotated module), Z = 0 on the desk side of
the tray (feet not counted). The bay parts are built in the bay frame (a along the rear edge, t rearwards from the
F-row cap line; tools/pcb_keys.py BAY) and placed with it, so a rotated rear strip (left, right) needs no change.

Stack, from the desk up: floor, cavity for the back-side parts, key board on bosses (heat-set M2 inserts) and
posts, printed spacers, plate; tray wall to just above the plate. Port bay: the port board stands PORT_GAP above
the key board on its 2x6 header, on two printed sleeves; one long M2 screw at each bay hole goes through cover
pillar, port board, sleeve and key board into the tray's insert. The cover carries the cable opening and prints
upside down without supports.
"""
import json
import math
import os

import FreeCAD as App
import Part
import MeshPart

V = App.Vector
ROOT = os.getcwd()
NAME = os.environ.get("CASE_MODULE", "numpad")
VARIANT = os.environ.get("CASE_VARIANT", "wired")      # "pod" = the wireless variant (spec 2b): output in build/case/<name>-pod/

# ---------------- parameters (mm) ----------------
FLOOR = 2.4            # tray floor
CAVITY = 4.0           # under the key board: SOIC-28W 2.65, 1210 capacitor 2.5, hotswap socket 1.85, header tails 1.4
PCB_T = 1.6
PLATE_T = 1.6
WALL = 2.4
CLEAR = 0.3            # board and plate to the wall, all round
LIP = 1.0              # wall top above the plate top (hides the FR4 edge; caps stay 5 mm above it)
BOSS_D = 6.4           # Ruthex RX-M2x4 insert: 3.2 mm hole, 1.6 mm of ASA round it
INSERT_D = 3.2
INSERT_DEPTH = 5.2     # from the boss top (insert 4.0 + screw run-out)
POST_D = 4.0           # support posts under the key field
POST_GAP = 0.2         # posts end this far under the board (the bosses carry it)
POST_CLEAR = 0.7       # post to any pad
SPACER_D = 5.0         # printed sleeve between board and plate
SCREW_D = 2.3
FOOT_D = 8.4           # 3M Bumpon SJ5302 (7.9 x 2.2 mm) recess
FOOT_DEPTH = 0.4
FOOT_INSET = 10.0
PORT_GAP = 11.04       # key board top to port board underside: 2.54 mm header body + 8.5 mm socket (check on parts)
PORT_T = 1.6
REC_A = -1.25          # receptacle centre line in the bay (tools/pcb_port.py REC_A)
REC_W, REC_H, REC_L = 8.94, 3.26, 7.3      # USB-C receptacle shell on the port board (check on the Amphenol part)
COVER_TOP = 1.6
COVER_AIR = 0.6        # above the receptacle
SKIRT_A = (-17.3, -15.3)   # cover side wall in the bay frame: overlaps the plate's notch edge (a = -16.5)
SKIRT_T = (0.45, 1.25)     # cover front wall: between the F-row caps (t = 0) and the port board (t = 1.5)
SKIRT_GAP = 0.3        # skirts end this far above the plate
PLUG_W, PLUG_H = 13.5, 7.5     # cable opening: lets a 12.35 x 6.5 mm USB-C overmould in
PILLAR_D0, PILLAR_D1 = 4.6, 6.4    # cover pillar on the port board / under the cover top
HEAD_D, HEAD_H = 4.2, 2.2      # M2 socket head recess
TILT = (4.0, 7.0)      # negative tilt: screwed-on front foot bars, swappable (user, 2026-11-14); flat = no bar
BUMP_H = 2.2           # Bumpon height: the bar's underside is the desk plane less its own Bumpons
BAR_DEPTH = 18.0
BAR_UNDER = 3.0        # ASA under the bar screw's head (M2 x 6 into an insert set from below)
FOOT_INSERT = 4.6      # insert hole from the tray's underside, in a boss that ends POST_GAP under the board
# ---- wireless variant (CASE_VARIANT=pod; user decisions 2026-11-14, spec 2b "Shell")
RAIL_SIDE, RAIL_REAR, RAIL_H = 19.0, 27.0, 19.0    # battery rail: outer side leg, rear leg, top (one piece with the tray)
RAIL_WALL, RAIL_FLOOR = 2.0, 2.0
AA_D, AA_LMAX, AA_LMIN = 14.5, 50.5, 49.2
POCKET_W = 15.0
PLATE = (11.2, 12.0, 0.51)     # Keystone 5201 (coil spring, 10.5 mm high) / 5223 (button, dome 1.4): build/ds/contacts/
SLOT, RIB, WINDOW, BACK = 0.6, 0.7, 7.0, 1.0       # plate slot, retaining rib in front of it, opening for the spring, wall behind
SPRING_COL, SPRING_ONE, DOME = 3.75, 4.5, 1.4      # spring height with cells of full length: column (a spring at each end), rear cell
PB = (48.0, 22.0)              # power board (tools/pcb_pod.py PW, NOTCH, NOTCH_W, POWER_HOLES): u from its west end, v from its rear edge
PB_OUT = [(0, 0), (48, 0), (48, 15.4), (32.5, 15.4), (32.5, 22), (4, 22), (4, 9), (0, 9)]
PB_HOLES = [(6.8, 19.3), (20.0, 20.2)]
PB_POSTS = [(3.0, 4.0), (15.0, 3.0), (38.0, 3.4), (46.0, 3.4), (46.0, 12.5)]    # under the plugs and the east end, clear of through-hole tails
PB_Z = 6.0                     # board underside: 4 mm bosses on the rail floor take a whole M2 insert
PB_TALL = [("can", 12.75, 22.25, 0.9, 8.1, 5.8), ("lead", 35.8, 47.8, 0.1, 6.7, 8.5), ("pack", -0.5, 12.1, 0.5, 9.0, 7.0), ("conv", 21.0, 30.0, 11.0, 16.0, 2.1)]
SW_U, SW_SLOT = 28.5, (8.0, 3.4)   # slide switch centre on the board's rear edge, slot in the rear wall (check on the C&K part)
POD_T1 = 52.19                 # pod rear edge in the bay frame (tools/pcb_pod.py POD_REAR)
POD_USB_A, POD_MOD_A = -9.0, 7.0
USB_SHELL = (8.94, 3.2, 2.51)  # GCT USB4085: width, height above the pod, shell beyond the pod's rear edge (flush with the rail's rear face)
DECK = 16.5                    # rail walls under the pod: 2.5 mm under its underside (through-hole tails)
LID_Z, LID_T, LID_EDGE, GROOVE = 17.2, 1.6, 1.0, 0.7    # sliding lids: seat, body, edge flange in the groove, groove depth in the walls
HOOD_X0 = -22.9                # cover's west end over the rail in the bay frame: room for the lead's plug beside the pod
CAP_Z = (6.5, 17.5)    # keycap envelope above the plate top (for the picture and the clash checks only)

Z_BOARD = FLOOR + CAVITY
Z_BTOP = Z_BOARD + PCB_T
Z_PLATE = Z_BTOP + 5.0 - PLATE_T       # plate top 5.0 above the board top (Cherry MX)
Z_PTOP = Z_PLATE + PLATE_T
Z_WALL = Z_PTOP + LIP
Z_PORT = Z_BTOP + PORT_GAP
Z_PORT_TOP = Z_PORT + PORT_T
Z_COVER_IN = max(Z_PORT_TOP + REC_H + COVER_AIR, Z_PORT_TOP + REC_H / 2 + PLUG_H / 2)   # the plug's overmould is taller than the receptacle
Z_COVER = Z_COVER_IN + COVER_TOP


def log(s):
    App.Console.PrintMessage(s + "\n")


def build(name):
    d = json.load(open(os.path.join(ROOT, "build", "case", name + ".json")))
    xs = [c[0] for c in d["corners"]]; ys = [c[1] for c in d["corners"]]
    xc, yc = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    c = lambda p: V(p[0] - xc, -(p[1] - yc), 0)

    def poly(pts, z=0.0):
        vs = [V(p.x, p.y, z) for p in pts]
        return Part.Face(Part.makePolygon(vs + [vs[0]]))

    def prism(face, z0, z1):
        f = face.copy(); f.translate(V(0, 0, z0))
        return f.extrude(V(0, 0, z1 - z0))

    def cyl(p, dia, z0, z1):
        return Part.makeCylinder(dia / 2, z1 - z0, V(p.x, p.y, z0))

    # ---- outlines
    core = poly([c(p) for p in d["corners"]]).makeOffset2D(-d["fillet"], join=2)
    board_f = core.makeOffset2D(d["fillet"])
    cavity_f = core.makeOffset2D(d["fillet"] + CLEAR)
    outer_f = core.makeOffset2D(d["fillet"] + CLEAR + WALL)
    holes = [c(h) for h in d["holes"]]
    plate_holes = [c(h) for h in d["plate"]["holes"]]
    bay = d["bay"]
    b0 = c(bay["origin"])
    ua = V(bay["a"][0], -bay["a"][1], 0); ut = V(bay["t"][0], -bay["t"][1], 0)
    B = lambda a, t: b0 + ua * a + ut * t
    bay_screws = [B(*s) for s in ((-11.5, 20.0), (9.0, 20.0))]
    for s in bay_screws:
        assert min((s - h).Length for h in holes) < 0.02, "bay screw is not on a key board hole"
    FAR = 400.0

    # ---- board, plate, port board, caps (reference solids)
    board = prism(board_f, Z_BOARD, Z_BTOP)
    for h in holes:
        board = board.cut(cyl(h, 2.2, Z_BOARD - 1, Z_BTOP + 1))
    plate = prism(poly([c(p) for p in d["plate"]["outline"]]), Z_PLATE, Z_PTOP)
    cuts = [prism(poly([c(p) for p in q]), Z_PLATE - 1, Z_PTOP + 1) for q in d["plate"]["cuts"]]
    cuts += [cyl(h, d["plate"]["hole_d"], Z_PLATE - 1, Z_PTOP + 1) for h in plate_holes]
    plate = plate.cut(Part.makeCompound(cuts))
    pa0, pa1, pt0, pt1 = bay["port"]
    port = prism(poly([B(pa0, pt0), B(pa1, pt0), B(pa1, pt1), B(pa0, pt1)]), Z_PORT, Z_PORT_TOP)
    rec = prism(poly([B(REC_A - REC_W / 2, pt1 - REC_L), B(REC_A + REC_W / 2, pt1 - REC_L), B(REC_A + REC_W / 2, pt1),
                      B(REC_A - REC_W / 2, pt1)]), Z_PORT_TOP, Z_PORT_TOP + REC_H)
    hdr = prism(poly([B(-7.7, 4.4), B(7.7, 4.4), B(7.7, 9.6), B(-7.7, 9.6)]), Z_BTOP, Z_PORT)
    port = Part.makeCompound([port, rec, hdr])
    caps = []
    for k in d["keys"]:
        if k["kind"] != "switch":
            continue
        w, h = k["w"] * 19.05 - 1.05, k["h"] * 19.05 - 1.05
        box = Part.makeBox(w, h, CAP_Z[1] - CAP_Z[0], V(-w / 2, -h / 2, Z_PTOP + CAP_Z[0]))
        box.rotate(V(0, 0, 0), V(0, 0, 1), -k["rot"]); box.translate(c((k["x"], k["y"])))
        caps.append(box)
    caps = Part.makeCompound(caps)

    # ---- tray
    tray = prism(outer_f, 0, Z_WALL).cut(prism(cavity_f, FLOOR, Z_WALL + 1))
    inside = prism(outer_f, 0, Z_WALL)
    for h in holes:
        tray = tray.fuse(cyl(h, BOSS_D, FLOOR - 0.1, Z_BOARD).common(inside))
    # support posts at key cell corners, clear of every pad and of the bosses
    pads_b = [(c(p), p[3]) for f in d["footprints"] for p in f["pads"] if f["back"] or p[2] > 0]
    boxes = []
    for f in d["footprints"]:
        if f["back"] and f["pads"]:
            ps = [c(p) for p in f["pads"]]
            boxes.append((min(p.x for p in ps), max(p.x for p in ps), min(p.y for p in ps), max(p.y for p in ps)))
    cand = {}
    for k in d["keys"]:
        for sx in (-1, 1):
            for sy in (-1, 1):
                t = math.radians(-k["rot"])
                u, v = sx * k["w"] * 9.525, sy * k["h"] * 9.525
                p = c((k["x"], k["y"])) + V(u * math.cos(t) - v * math.sin(t), u * math.sin(t) + v * math.cos(t), 0)
                cand[(round(p.x), round(p.y))] = p
    def free(p, m):
        if not core.isInside(p, 0.01, True):
            return False
        if any((p - q).Length - s / 2 < m for q, s in pads_b) or any((p - h).Length < m + BOSS_D / 2 for h in holes):
            return False
        return not any(x0 - m < p.x < x1 + m and y0 - m < p.y < y1 + m for x0, x1, y0, y1 in boxes)
    aa = lambda p: (p - b0).dot(ua)
    tt = lambda p: (p - b0).dot(ut)
    posts = [p for p in cand.values() if free(p, POST_D / 2 + POST_CLEAR)]
    # two of the front-most spots become bosses with an insert from below: the tilt bar (later the tent base) screws there
    t_front = min(tt(c(p)) for p in d["corners"])
    bbx = board_f.BoundBox
    grid = [V(bbx.XMin + i, bbx.YMin + j, 0) for i in range(int(bbx.XLength) + 1) for j in range(int(bbx.YLength) + 1)]
    wide = [p for p in grid if tt(p) < t_front + 16.0 and free(p, BOSS_D / 2 + 0.5)]
    foot_boss = [min(wide, key=lambda p: (round(aa(p)), tt(p))), max(wide, key=lambda p: (round(aa(p)), -tt(p)))]
    assert aa(foot_boss[1]) - aa(foot_boss[0]) > 30.0, "no two places for the tilt bar inserts"
    posts = [p for p in posts if all((p - q).Length > POST_D / 2 + BOSS_D / 2 for q in foot_boss)]
    for p in posts:
        tray = tray.fuse(cyl(p, POST_D, FLOOR - 0.1, Z_BOARD - POST_GAP))
    for p in foot_boss:
        tray = tray.fuse(cyl(p, BOSS_D, FLOOR - 0.1, Z_BOARD - POST_GAP)).cut(cyl(p, INSERT_D, -1, FOOT_INSERT))
    for h in holes:
        tray = tray.cut(cyl(h, INSERT_D, Z_BOARD - INSERT_DEPTH, Z_BOARD + 1))
    cen = V(0, 0, 0)
    feet = []
    for p in d["corners"]:
        q = c(p); n = cen - q; n.normalize()
        feet.append(q + n * (FOOT_INSET * math.sqrt(2)))
    tray0 = tray
    if VARIANT == "pod":
        ob = outer_f.BoundBox
        rx1, ry1 = ob.XMax + RAIL_SIDE, ob.YMax + RAIL_REAR
        feet = [V(ob.XMin + FOOT_INSET, ob.YMin + FOOT_INSET, 0), V(rx1 - FOOT_INSET, ob.YMin + FOOT_INSET, 0),
                V(ob.XMin + FOOT_INSET, ry1 - FOOT_INSET, 0), V(rx1 - FOOT_INSET, ry1 - FOOT_INSET, 0)]
    for q in feet:
        tray = tray.cut(cyl(q, FOOT_D, -1, FOOT_DEPTH))
    tray = tray.removeSplitter()

    # ---- tilt bars: tray on its rear Bumpons, the bar under the front; the bar's underside is parallel to the desk
    t_rear = max(tt(q) for q in feet)
    a0, a1 = aa(foot_boss[0]) - 9.0, aa(foot_boss[1]) + 9.0
    if VARIANT == "pod":
        a1 = aa(V(rx1, 0, 0))                    # the bar runs on under the side leg of the rail
    t0, t1 = min(tt(p) for p in foot_boss) - BAR_DEPTH / 2, max(tt(p) for p in foot_boss) + BAR_DEPTH / 2
    bar_f = poly([B(a0, t0), B(a1, t0), B(a1, t1), B(a0, t1)]).common(
        outer_f if VARIANT != "pod" else poly([V(ob.XMin, ob.YMin, 0), V(rx1, ob.YMin, 0), V(rx1, ry1, 0), V(ob.XMin, ry1, 0)]).makeOffset2D(-5.7, join=2).makeOffset2D(5.7))
    bars = {}
    for ang in TILT:
        k_ = math.tan(math.radians(ang))
        zz = lambda t: -(t_rear - t) * k_
        prof = [B(a0 - 5, t0 - 5) + V(0, 0, 1), B(a0 - 5, t1 + 5) + V(0, 0, 1), B(a0 - 5, t1 + 5) + V(0, 0, zz(t1 + 5)),
                B(a0 - 5, t0 - 5) + V(0, 0, zz(t0 - 5))]
        keep = Part.Face(Part.makePolygon(prof + [prof[0]])).extrude(ua * (a1 - a0 + 10))
        bar = prism(bar_f, -80, 0).common(keep)
        for p in foot_boss:
            bar = bar.cut(cyl(p, SCREW_D, -90, 1)).cut(cyl(p, HEAD_D, -90, -BAR_UNDER))
        for q in feet:
            bar = bar.cut(cyl(q, FOOT_D + 1.2, -(BUMP_H + 0.5), 1))
        bars[f"tilt{ang:.0f}"] = (bar.removeSplitter(), -zz(min(tt(p) for p in foot_boss)))

    # ---- bay cover
    half = lambda a0, t0: poly([B(a0, t0), B(FAR, t0), B(FAR, FAR), B(a0, FAR)])
    region = outer_f.common(half(SKIRT_A[0], SKIRT_T[0]))
    void = cavity_f.common(half(SKIRT_A[1], SKIRT_T[1]))
    ring = region.cut(cavity_f)
    z_skirt = Z_PTOP + SKIRT_GAP
    cover = prism(region, z_skirt, Z_COVER).cut(prism(void, z_skirt - 1, Z_COVER_IN)).cut(prism(ring, z_skirt - 1, Z_WALL))
    for s in bay_screws:
        cover = cover.fuse(Part.makeCone(PILLAR_D0 / 2, PILLAR_D1 / 2, Z_COVER_IN - Z_PORT_TOP + 0.1, V(s.x, s.y, Z_PORT_TOP)))
    for s in bay_screws:
        cover = cover.cut(cyl(s, SCREW_D, Z_PORT_TOP - 1, Z_COVER + 1)).cut(cyl(s, HEAD_D, Z_COVER - HEAD_H, Z_COVER + 1))
    zc = Z_PORT_TOP + REC_H / 2
    win = Part.makeBox(PLUG_W, 12.0, PLUG_H, V(REC_A - PLUG_W / 2, pt1 - 3.0, zc - PLUG_H / 2))
    win = win.makeFillet(2.0, [e for e in win.Edges if abs(e.tangentAt(e.FirstParameter).y) > 0.99])
    ang = math.degrees(math.atan2(ua.y, ua.x))
    win.rotate(V(0, 0, 0), V(0, 0, 1), ang); win.translate(b0)
    cover = cover.cut(win).removeSplitter()

    # ---- small printed parts
    tube = lambda p, dia, z0, z1: cyl(p, dia, z0, z1).cut(cyl(p, SCREW_D, z0 - 1, z1 + 1))
    spacers = Part.makeCompound([tube(h, SPACER_D, Z_BTOP, Z_PLATE) for h in plate_holes])
    sleeves = Part.makeCompound([tube(s, PILLAR_D0, Z_BTOP, Z_PORT) for s in bay_screws])

    # ---- fit-print pieces (cut from the tray)
    bb = tray.BoundBox
    fit_bay = tray.common(prism(poly([B(-24, -8), B(FAR, -8), B(FAR, FAR), B(-24, FAR)]), -1, 60))
    q = c(d["corners"][0])
    n = cen - q; n.normalize()                    # front outer corner: a 38 mm square reaching 4 mm outside the board corner
    p0, p1 = q - n * (4 * math.sqrt(2)), q + n * (34 * math.sqrt(2))
    fit_front = tray.common(Part.makeBox(abs(p1.x - p0.x), abs(p1.y - p0.y), 60, V(min(p0.x, p1.x), min(p0.y, p1.y), -1)))

    parts = {"tray": tray, "cover": cover, "spacers": spacers, "sleeves": sleeves}
    parts.update({k_: v[0] for k_, v in bars.items()})
    refs = {"board": board, "plate": plate, "port": port, "caps": caps}
    fits = {"fit-bay": fit_bay, "fit-front": fit_front}
    extra = []
    if VARIANT == "pod":
        import importlib.util
        spec = importlib.util.spec_from_file_location("pod_case", os.path.join(ROOT, "mech", "case", "pod_case.py"))
        pc = importlib.util.module_from_spec(spec); spec.loader.exec_module(pc)
        extra = pc.build(dict(globals(), **locals()), parts, refs, fits)

    # ---- report
    rep = []
    bb = parts["tray"].BoundBox
    rep.append(f"{name}: tray {bb.XLength:.1f} x {bb.YLength:.1f} x {bb.ZLength:.1f} mm; cover top at {Z_COVER:.2f}, "
               f"plate top {Z_PTOP:.2f}, cap tops about {Z_PTOP + CAP_Z[1]:.1f}")
    rep.append(f"levels: board {Z_BOARD:.2f}-{Z_BTOP:.2f}, plate {Z_PLATE:.2f}-{Z_PTOP:.2f}, wall top {Z_WALL:.2f}, "
               f"port board {Z_PORT:.2f}-{Z_PORT_TOP:.2f}, receptacle axis {zc:.2f}")
    rep.append(f"{len(holes)} bosses with inserts from the top ({len(plate_holes)} through the plate, 2 in the bay), 2 with inserts from below "
               f"for the tilt bar, {len(posts)} support posts, 4 feet")
    rep.append(f"screws: plate M2 x {PLATE_T + (Z_PLATE - Z_BTOP) + PCB_T + 4:.1f} for a full insert (M2 x 10); "
               f"bay M2 x {(Z_COVER - HEAD_H - Z_PORT_TOP) + PORT_T + PORT_GAP + PCB_T + 4:.1f} for a full insert (M2 x 22)")
    rep.append("tilt bars (M2 x 6 into 2 inserts set from below): " + ", ".join(f"{k_} {v[1]:.1f} mm at the screws" for k_, v in bars.items()))
    rep.append(f"spacers {Z_PLATE - Z_BTOP:.2f} mm, bay sleeves {PORT_GAP:.2f} mm")
    bad = 0
    pairs = [("tray", tray, "board", board), ("tray", tray, "plate", plate), ("tray", tray, "port", port),
             ("cover", cover, "port", port), ("cover", cover, "plate", plate), ("cover", cover, "caps", caps),
             ("cover", cover, "tray", tray), ("cover", cover, "board", board), ("cover", cover, "sleeves", sleeves),
             ("spacers", spacers, "plate", plate), ("spacers", spacers, "board", board), ("tray", tray, "caps", caps)]
    pairs += [(k_, v[0], "tray", parts["tray"]) for k_, v in bars.items()]
    if VARIANT == "pod":
        pairs = [(na, parts.get(na, a), nb, parts.get(nb, refs.get(nb, b))) for na, a, nb, b in pairs] + extra[0]
        rep += extra[1]
    for na, a, nb, b in pairs:
        vol = a.common(b).Volume
        if vol > 0.01:
            bad += 1
            rep.append(f"CLASH {na} / {nb}: {vol:.2f} mm3")
    rep.append(f"clash checks: {len(pairs)} pairs, {bad} clashes")
    for n_, s in list(parts.items()) + list(fits.items()):
        rep.append(f"  {n_}: valid {s.isValid()}, volume {s.Volume / 1000:.1f} cm3")
    return parts, refs, fits, rep


COLOURS = {"tray": (0.25, 0.27, 0.30), "cover": (0.85, 0.45, 0.10), "spacers": (0.9, 0.8, 0.1), "sleeves": (0.9, 0.8, 0.1),
           "board": (0.05, 0.35, 0.15), "plate": (0.75, 0.70, 0.50), "port": (0.10, 0.45, 0.25), "caps": (0.85, 0.85, 0.88), "tilt4": (0.85, 0.45, 0.10), "tilt7": (0.6, 0.3, 0.1)}


def main():
    parts, refs, fits, rep = build(NAME)
    out = os.path.join(ROOT, "build", "case", NAME + ("-pod" if VARIANT == "pod" else ""))
    os.makedirs(out, exist_ok=True)
    for r in rep:
        log(r)
    open(os.path.join(out, "report.txt"), "w").write("\n".join(rep) + "\n")
    dn = "case_" + NAME + ("_pod" if VARIANT == "pod" else "")
    if dn in App.listDocuments():
        App.closeDocument(dn)
    doc = App.newDocument(dn)
    for n_, s in list(parts.items()) + list(refs.items()):
        o = doc.addObject("Part::Feature", n_); o.Shape = s
        if App.GuiUp:
            o.ViewObject.ShapeColor = COLOURS.get(n_, (0.5, 0.5, 0.55))
            if n_ == "caps":
                o.ViewObject.Transparency = 60
    doc.recompute()
    if App.GuiUp:
        import FreeCADGui as Gui
        Gui.ActiveDocument.ActiveView.viewIsometric(); Gui.SendMsgToActiveView("ViewFit")
        return
    for n_, s in list(parts.items()) + list(fits.items()):
        MeshPart.meshFromShape(Shape=s, LinearDeflection=0.05, AngularDeflection=0.3).write(os.path.join(out, f"{NAME}-{n_}.stl"))
    Part.makeCompound(list(parts.values()) + list(refs.values())).exportStep(os.path.join(out, f"{NAME}-case.step"))
    doc.saveAs(os.path.join(out, f"{NAME}-case.FCStd"))


main()
