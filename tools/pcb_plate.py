#!/usr/bin/env python3
"""Switch plates (M2 step 4): hardware/plate-<name>/plate-<name>.kicad_pcb for left, right, numpad.

Run with KiCad's Python (it needs pcbnew), after the key board exists:
    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 tools/pcb_plate.py [left right numpad]
Options: `--field-only` (variant without the rear strip, for comparison), `--dump` (also write the geometry to
build/plate/<name>.json for the FreeCAD preview), `--check` (checks only, nothing written).

A plate is FR4 with no copper: an outline, cut-outs and holes, all generated (a changed layout is a re-run):
- outline: the key board's own (tools/pcb_keys.py `frame`), with the port bay cut away to the inner edge (the port
  board stands on the key board there and is taller than the plate);
- per key a square switch cut-out (CUTOUT, Cherry MX: 14.0 mm; the M0 test cell's 14.1 mm was an FDM figure) at the
  position and angle from layout/keys.json; per stabilised key two Cherry cut-outs with the wire notch;
- a slot over the spare-pin header, an opening at the dial (provisional until the dial board's mounting, M3);
- M2 holes on the key board's holes (read from the key board: the case may move them at M3, then re-run).
Checked against the routed key board, and the script stops on a failure: every switch footprint under its cut-out
(position and angle), every stabiliser's holes under its cut-outs with the wire notch on the large-hole side, the
plate inside the key board's outline, every front-side part of the key board under an opening, the port board clear
of the plate, and the webs between cut-outs.
"""
import json
import math
import os
import subprocess
import sys

import pcbnew

import pcb_keys as K
from pcb_keys import rot, vec, mm

THICKNESS = 1.6          # user, 2026-11-14 (options UI); the spec's 1.5 mm is not a stock thickness
CUTOUT = 14.0            # Cherry MX plate cut-out
CUT_R = 0.5              # inside corner radius: a 1 mm router bit
PLATE_Z = 5.0            # top of the plate above the top of the key board (Cherry MX)
STAB_X = 11.938          # 2u to 2.75u
STAB = ((-3.5, -5.73), (3.5, -5.73), (3.5, 6.97), (1.75, 6.97), (1.75, 8.2), (-1.75, 8.2), (-1.75, 6.97), (-3.5, 6.97))
BAY_CLEAR = 1.5          # plate edge to the port board, sideways
BAY_T0 = 0.5             # the notch's front edge, behind the F-row cap line (the port board starts at 1.5)
PORT = (-15.0, 15.0, 1.5, 25.0)      # the port board in the bay frame (tools/pcb_port.py)
FIELD_T = 0.5            # --field-only: rear edge this far behind the cap line
DIAL = 17.0              # square opening at the dial (provisional)
SLOT_W = 3.6             # slot over the spare-pin header
WEB_MIN = 1.2            # least FR4 between two cut-outs
EDGE_MIN = 1.5           # least FR4 between a cut-out and the outline
HOLE_D = 2.2


# ---- small geometry ---------------------------------------------------------------------------
def fillet(corners):
    """corners: [(point, radius)] of a closed polygon (convex or concave corners). Returns [(p, m, q)] arcs."""
    out, n = [], len(corners)
    for i, (p, r) in enumerate(corners):
        a, c = corners[i - 1][0], corners[(i + 1) % n][0]
        d1 = (a[0] - p[0], a[1] - p[1]); d2 = (c[0] - p[0], c[1] - p[1])
        l1, l2 = math.hypot(*d1), math.hypot(*d2)
        d1 = (d1[0] / l1, d1[1] / l1); d2 = (d2[0] / l2, d2[1] / l2)
        half = math.acos(max(-1, min(1, d1[0] * d2[0] + d1[1] * d2[1]))) / 2
        t = r / math.tan(half)
        if t > min(l1, l2) / 2 + 1e-6:
            sys.exit(f"fillet {r} does not fit at {p}")
        bis = (d1[0] + d2[0], d1[1] + d2[1]); bl = math.hypot(*bis)
        m = r / math.sin(half) - r
        out.append(((p[0] + d1[0] * t, p[1] + d1[1] * t), (p[0] + bis[0] / bl * m, p[1] + bis[1] / bl * m),
                    (p[0] + d2[0] * t, p[1] + d2[1] * t)))
    return out


def polyline(arcs, n=6):
    """The filleted shape as points, every arc sampled n times."""
    out = []
    for p, m_, q in arcs:
        ax, ay, bx, by, cx, cy = *p, *m_, *q
        d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
        ox = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
        oy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
        a0, a1 = math.atan2(ay - oy, ax - ox), math.atan2(cy - oy, cx - ox)
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi       # a fillet turns by less than 180 degrees
        r = math.hypot(ax - ox, ay - oy)
        out += [(ox + r * math.cos(a0 + da * i / n), oy + r * math.sin(a0 + da * i / n)) for i in range(n + 1)]
    return out


def seg_dist(p, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]
    l2 = vx * vx + vy * vy
    u = 0 if l2 == 0 else max(0, min(1, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / l2))
    return math.hypot(p[0] - a[0] - u * vx, p[1] - a[1] - u * vy)


def poly_dist(A, B):
    """Least distance between two polygons that do not cross (vertex to edge, both ways)."""
    best = 1e9
    for P, Q in ((A, B), (B, A)):
        for p in P:
            for i in range(len(Q)):
                best = min(best, seg_dist(p, Q[i - 1], Q[i]))
    return best


def within(poly, p):
    hit = False
    for i in range(len(poly)):
        a, b = poly[i - 1], poly[i]
        if (a[1] > p[1]) != (b[1] > p[1]) and p[0] < a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1]):
            hit = not hit
    return hit


def circle(c, d, n=12):
    return [(c[0] + d / 2 * math.cos(2 * math.pi * i / n), c[1] + d / 2 * math.sin(2 * math.pi * i / n)) for i in range(n)]


# ---- the plate --------------------------------------------------------------------------------
def key_board(name):
    """What the plate needs from the routed key board: switch and stabiliser footprints, holes, front-side parts."""
    b = pcbnew.LoadBoard(str(K.HW / name / f"{name}.kicad_pcb"))
    sw, st, holes, front = [], [], [], []
    for fp in b.GetFootprints():
        ref, item = fp.GetReference(), str(fp.GetFPID().GetLibItemName())
        xy = (pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y))
        pads = [((pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y)), pcbnew.ToMM(p.GetDrillSize().x))
                for p in fp.Pads()]
        if item.startswith("Stabilizer"):
            st.append(pads)
        elif item == K.HOLE_FP[1]:
            holes.append(xy)
        elif ref.startswith("SW"):
            sw.append((ref, xy, fp.GetOrientationDegrees()))
        elif not fp.IsFlipped():
            front.append((ref, fp.GetValue(), [p for p, _ in pads]))
    return sw, st, holes, front


def build(name, field_only):
    keys, inner_sign, (lines, corners, origin, phi, front_rot) = K.frame(name)
    at, sb = K.strip_frame(lines, origin, phi, inner_sign)
    sw, st, kb_holes, front = key_board(name)
    n_rear, d_rear = lines["rear"]
    errors = []

    # outline. corners come as front x outer, outer x rear, rear x inner, inner x front
    if field_only:
        rear = (n_rear, d_rear - K.REAR + FIELD_T)
        shape = [(corners[0], K.FILLET), (K.meet(lines["outer"], rear), K.FILLET), (K.meet(rear, lines["inner"]), K.FILLET),
                 (corners[3], K.FILLET)]
    else:
        s1 = sb - K.BAY["width"] / 2 - BAY_CLEAR
        shape = [(corners[0], K.FILLET), (corners[1], K.FILLET), (at(s1, K.REAR), 2.0), (at(s1, BAY_T0), 1.5),
                 (K.meet((n_rear, d_rear - K.REAR + BAY_T0), lines["inner"]), 1.5), (corners[3], K.FILLET)]
    outline = fillet(shape)
    edge = polyline(outline)

    # cut-outs: (kind, key id, [(point, radius)])
    cuts = []
    def framed(k, pts, turn=0.0):
        return [((k["x"] + rot(*rot(px, py, turn), k["rot"])[0], k["y"] + rot(*rot(px, py, turn), k["rot"])[1]), CUT_R)
                for px, py in pts]
    h = CUTOUT / 2
    for k in keys:
        if k["kind"] == "encoder":
            cuts.append(("dial", k["id"], framed(k, ((-DIAL / 2, -DIAL / 2), (DIAL / 2, -DIAL / 2), (DIAL / 2, DIAL / 2), (-DIAL / 2, DIAL / 2)))))
            continue
        cuts.append(("switch", k["id"], framed(k, ((-h, -h), (h, -h), (h, h), (-h, h)))))
        if k["stab"]:
            turn = -90.0 if k["h"] > k["w"] else 0.0            # as the footprint: turned for a tall key
            for side in (-1, 1):
                cuts.append(("stab", k["id"], framed(k, [(px + side * STAB_X, py) for px, py in STAB], turn)))
    if not field_only:
        for ref, value, pads in front:
            if value == "SPARE":
                (ax, ay), (bx, by) = pads[0], pads[-1]
                ln = math.hypot(bx - ax, by - ay)
                ux, uy = (bx - ax) / ln, (by - ay) / ln
                e, w = 1.27 + 0.5, SLOT_W / 2
                cuts.append(("slot", ref, [((ax - ux * e + s * -uy * w, ay - uy * e + s * ux * w) if end == 0 else
                                            (bx + ux * e + s * -uy * w, by + uy * e + s * ux * w), 1.0)
                                           for end, s in ((0, 1), (1, 1), (1, -1), (0, -1))]))
    shapes = [(kind, kid, fillet(pts)) for kind, kid, pts in cuts]
    polys = [(kind, kid, polyline(arcs)) for kind, kid, arcs in shapes]

    # holes: the key board's, where the plate has material round them
    holes = [p for p in kb_holes if within(edge, p) and min(seg_dist(p, edge[i - 1], edge[i]) for i in range(len(edge))) >= 2.0]

    # ---- checks against the key board
    cut_of = {kid: pts for kind, kid, pts in cuts if kind == "switch"}
    centre = lambda pts: (sum(p[0][0] for p in pts) / len(pts), sum(p[0][1] for p in pts) / len(pts))
    by_pos = {kid: centre(pts) for kid, pts in cut_of.items()}
    rot_of = {k["id"]: k["rot"] for k in keys}
    for ref, xy, ang in sw:
        kid, d = min(((kid, math.hypot(c[0] - xy[0], c[1] - xy[1])) for kid, c in by_pos.items()), key=lambda v: v[1])
        da = (ang + rot_of[kid] + 180) % 360 - 180               # footprints sit at -rot
        if d > 0.01 or abs(da) > 0.01:
            errors.append(f"{ref}: nearest cut-out {kid} is {d:.3f} mm / {da:.3f} deg off")
    if len(sw) != len(cut_of):
        errors.append(f"{len(sw)} switches on the key board, {len(cut_of)} cut-outs")
    stab_polys = [pts for kind, _, pts in polys if kind == "stab"]
    if len(stab_polys) != 2 * len(st):
        errors.append(f"{len(st)} stabilisers on the key board, {len(stab_polys)} cut-outs")
    for pads in st:
        for side in (-1, 1):
            pair = sorted(pads, key=lambda p: p[1])              # by drill: two small, two large
            small, large = pair[:2], pair[2:]
            # the two holes of one side: nearest small to each large
            lg = large[0 if side < 0 else 1][0]
            smh = min(small, key=lambda p: abs(math.hypot(p[0][0] - lg[0], p[0][1] - lg[1]) - 15.21))[0]
            mid = ((lg[0] + smh[0]) / 2, (lg[1] + smh[1]) / 2)
            poly = min(stab_polys, key=lambda q: math.hypot(sum(p[0] for p in q) / len(q) - mid[0], sum(p[1] for p in q) / len(q) - mid[1]))
            if not (within(poly, mid) and within(poly, ((mid[0] + lg[0]) / 2, (mid[1] + lg[1]) / 2))):
                errors.append(f"stabiliser holes at {mid[0]:.1f}, {mid[1]:.1f} are not under a cut-out")
                continue
            far_l = max(math.hypot(p[0] - lg[0], p[1] - lg[1]) for p in poly)
            far_s = max(math.hypot(p[0] - smh[0], p[1] - smh[1]) for p in poly)
            box = [min(p[0] for p in poly), max(p[0] for p in poly), min(p[1] for p in poly), max(p[1] for p in poly)]
            cx, cy = (box[0] + box[1]) / 2, (box[2] + box[3]) / 2
            # the notch end is the far end from the bounding box centre's small-hole side
            if not math.hypot(lg[0] - cx, lg[1] - cy) < math.hypot(smh[0] - cx, smh[1] - cy) + 2.0 or far_l > far_s:
                errors.append(f"stabiliser at {mid[0]:.1f}, {mid[1]:.1f}: the wire notch is not on the large-hole side")
    for p in edge:
        if not K.inside(lines, p, -0.01):
            errors.append(f"plate outline point {p[0]:.2f}, {p[1]:.2f} is outside the key board")
    port = [at(sb + inner_sign * a, t) for a, t in ((PORT[0], PORT[2]), (PORT[1], PORT[2]), (PORT[1], PORT[3]), (PORT[0], PORT[3]))]
    if any(within(edge, p) for p in port) or poly_dist(port, edge) < 0.99:
        errors.append(f"port board is {poly_dist(port, edge):.2f} mm from the plate")
    for ref, value, pads in front:
        for p in pads:
            if within(edge, p) and not any(within(q, p) for _, _, q in polys):
                errors.append(f"{ref} ({value}) stands on the key board's front side under the plate at {p[0]:.1f}, {p[1]:.1f}")
                break
    web, margin = (1e9, ""), (1e9, "")
    items = polys + [("hole", f"{p[0]:.0f},{p[1]:.0f}", circle(p, HOLE_D)) for p in holes]
    for i, (ka, ia, A) in enumerate(items):
        for kb, ib, B in items[i + 1:]:
            if abs(A[0][0] - B[0][0]) < 45 and abs(A[0][1] - B[0][1]) < 45:
                d = poly_dist(A, B)
                if d < web[0] and not (ka == kb == "stab" and ia == ib and d > 20):
                    web = (d, f"{ka} {ia} / {kb} {ib}")
        d = poly_dist(A, edge)
        if d < margin[0]:
            margin = (d, f"{ka} {ia}")
        if not all(within(edge, p) for p in A):
            errors.append(f"{ka} {ia} is not inside the plate")
    if web[0] < WEB_MIN:
        errors.append(f"web {web[0]:.2f} mm between {web[1]}")
    if margin[0] < EDGE_MIN:
        errors.append(f"only {margin[0]:.2f} mm between {margin[1]} and the outline")
    info = (f"{sum(1 for c in cuts if c[0] == 'switch')} switch cut-outs, {len(stab_polys)} stabiliser cut-outs, "
            f"{sum(1 for c in cuts if c[0] in ('slot', 'dial'))} other openings, {len(holes)} of {len(kb_holes)} holes; "
            f"least web {web[0]:.2f} mm ({web[1]}), least edge margin {margin[0]:.2f} mm ({margin[1]})")
    geom = {"outline": edge, "cuts": [q for _, _, q in polys], "holes": holes, "hole_d": HOLE_D, "port": port,
            "board": [list(c) for c in corners], "thickness": THICKNESS, "plate_z": PLATE_Z}
    return outline, shapes, holes, errors, info, geom, at


def write(name, outline, shapes, holes, at, variant):
    proj = f"plate-{name}"
    d = K.HW / proj
    d.mkdir(exist_ok=True)
    b = pcbnew.CreateEmptyBoard()
    b.GetDesignSettings().SetBoardThickness(mm(THICKNESS))
    def draw(arcs):
        for i, (p, m_, q) in enumerate(arcs):
            for kind, pts in (("arc", (p, m_, q)), ("line", (q, arcs[(i + 1) % len(arcs)][0]))):
                s = pcbnew.PCB_SHAPE(b)
                if kind == "arc":
                    s.SetShape(pcbnew.SHAPE_T_ARC); s.SetArcGeometry(vec(*pts[0]), vec(*pts[1]), vec(*pts[2]))
                else:
                    s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetStart(vec(*pts[0])); s.SetEnd(vec(*pts[1]))
                s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1))
                b.Add(s)
    draw(outline)
    for _, _, arcs in shapes:
        draw(arcs)
    for i, (x, y) in enumerate(holes):
        fp = K.load_fp(K.HOLE_FP)
        fp.SetReference(f"H{i + 1}")
        fp.Reference().SetVisible(False)
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        b.Add(fp)
        fp.SetPosition(vec(x, y))
    pcbnew.SaveBoard(str(d / f"{proj}.kicad_pcb"), b)
    pro = d / f"{proj}.kicad_pro"
    data = json.loads(pro.read_text()) if pro.exists() else {"meta": {"filename": pro.name, "version": 3}}
    data.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rules", {}).update(K.RULES)
    pro.write_text(json.dumps(data, indent=2) + "\n")
    return d / f"{proj}.kicad_pcb"


def main():
    names = [a for a in sys.argv[1:] if not a.startswith("--")] or ["left", "right", "numpad"]
    field_only, status = "--field-only" in sys.argv, 0
    for name in names:
        outline, shapes, holes, errors, info, geom, at = build(name, field_only)
        print(f"plate-{name}{' (field only)' if field_only else ''}: {info}")
        for e in errors:
            print("ERROR", e)
        status |= bool(errors)
        if "--dump" in sys.argv:
            out = K.ROOT / "build" / "plate"
            out.mkdir(parents=True, exist_ok=True)
            (out / f"{name}{'-field' if field_only else ''}.json").write_text(json.dumps(geom))
        if errors or "--check" in sys.argv or field_only:
            continue
        path = write(name, outline, shapes, holes, at, field_only)
        rep = K.ROOT / "build" / "kicad-check" / f"plate-{name}-drc.json"
        rep.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([str(K.CLI), "pcb", "drc", "--severity-all", "--format", "json", "-o", str(rep), str(path)],
                       capture_output=True)
        v = json.loads(rep.read_text())
        kinds = sorted({x["type"] for x in v["violations"]})
        print(f"  DRC: {sum(1 for x in v['violations'] if x['severity'] == 'error')} errors, "
              f"{sum(1 for x in v['violations'] if x['severity'] != 'error')} warnings {kinds}")
        status |= any(x["severity"] == "error" for x in v["violations"])
    sys.stdout.flush()
    os._exit(status)          # pcbnew's objects crash Python's final garbage collection


if __name__ == "__main__":
    main()
