"""Pose parts of an alpha half (M3 session 4; user decisions 2026-11-14, spec 2a): palm rest, the tilt bars for under
it, tent bases (short, and long for use with the palm rest). Called by build_case.py for left and right, both variants.

Frame: the tray's (Z = 0 its underside). Everything hangs under or in front of the tray.
- palm: PALM_D deep in front of the tray, pillow top (highest PALM_H above the tray's underside at PALM_PEAK of the
  depth), sides straight to the front, a TONGUE thick tongue under the tray's front screwed into the two tilt-bar
  inserts (M2 x 8, the same two screws). Underside TONGUE below the tray's. Two inserts from below near its front.
- tiltp4 / tiltp7: bar under the palm rest's front edge, screwed into those two inserts; the tray stays on its rear feet.
- tent5 / tent7: wedge under the tray, turned about the outer bottom edge. Four M2 x 6 from below into the tray's
  inserts through access bores. Its underside carries the tray's feet pattern and two inserts at BAR_ALT beside the
  tray's (the access bores are where the tray's own would be), so the tray's tilt bars (they have both hole pairs)
  screw under it. left is lifted so both split edges stand at one height (user).
  Open frame (WIN_EDGE wide rim), not a solid wedge.
- tent5-long / tent7-long: the same under tray and palm rest, stepped by TONGUE; front screws M2 x 10 through base and
  tongue. Underside: the tray's rear feet, the palm rest's front feet and its two inserts (the tiltp bars fit).
Print: bases desk face down (STL is laid flat), palm rest standing on its outer end (STL is turned), bars top face down.
"""
import json
import math
import os

import FreeCAD as App
import Part

V = App.Vector
TENT = (5.0, 7.0)      # tent angles, a base for each (user, 2026-11-14)
T_MIN = 5.0            # base thickness at the outer edge: a whole insert from below
PALM_D, PALM_H, PALM_FRONT, PALM_PEAK = 100.0, 26.0, 8.0, 0.4      # user, 2026-11-14: 100 mm deep, 26 mm high, pillow
PALM_REAR = 3.0        # the top at the tray stands this far under the highest point
PALM_GAP = 0.4         # palm rest to the tray's front wall
TONGUE = 3.0
HEAD_LOW = 1.4         # head recess in the tongue (1.6 mm of ASA stays; a socket head stands 0.8 out, less than a Bumpon)
PALM_FOOT = 12.0       # palm rest feet and inserts from its edges
PALM_INS = 30.0
EDGE_R = 3.0
WIN_EDGE = 18.0        # tent base: a frame this wide stays round the open middle (feet, inserts and screws are all in it)


def build(E, parts, refs):
    name, pod = E["name"], E["VARIANT"] == "pod"
    poly, prism, cyl, B, aa, tt, ua = E["poly"], E["prism"], E["cyl"], E["B"], E["aa"], E["tt"], E["ua"]
    foot_boss, rear_boss, feet, under, alt = E["foot_boss"], E["rear_boss"], E["feet"], E["under"], E["bar_alt"]
    SCREW_D, HEAD_D, INSERT_D, FOOT_INSERT = E["SCREW_D"], E["HEAD_D"], E["INSERT_D"], E["FOOT_INSERT"]
    FOOT_D, FOOT_DEPTH, BUMP_H, BAR_UNDER = E["FOOT_D"], E["FOOT_DEPTH"], E["BUMP_H"], E["BAR_UNDER"]
    OUT = E["R"] if pod else E["outer_f"]
    Q = E["Rq"] if pod else E["Tq"]
    cen, t_rear, D, H = E["cen"], E["t_rear"], PALM_D, PALM_H
    rep, new = [], {}

    # ---- palm rest
    F0, F3 = Q[0], Q[3]                           # the outline's front corners: outer, inner
    e = F3 - F0; L = e.Length; e.normalize()
    n = V(e.y, -e.x, 0)
    if n.dot(F0 - cen) < 0:
        n = n * -1
    fwd = V(0, 1 if n.y > 0 else -1, 0) * (1 / abs(n.y))      # sides straight to the front; fwd * s is s in front of the tray
    A, Bp = F0 + n * PALM_GAP, F3 + n * PALM_GAP
    big = poly([A - fwd * 12, Bp - fwd * 12, Bp + fwd * D, A + fwd * D]).makeOffset2D(-8.0, join=2).makeOffset2D(8.0)
    palm_f = big.common(poly([A, Bp, Bp + fwd * (D + 5), A + fwd * (D + 5)]))
    sp = PALM_PEAK * D
    zp = lambda s: H - PALM_REAR * ((s - sp) / sp) ** 2 if s < sp else H - (H - PALM_FRONT) * ((s - sp) / (D - sp)) ** 2
    o = A - e * 40
    pts = [o + n * (D * i / 24) + V(0, 0, zp(D * i / 24)) for i in range(25)]
    bs = Part.BSplineCurve(); bs.interpolate(pts)
    low = [o + n * D + V(0, 0, -TONGUE), o + V(0, 0, -TONGUE)]
    wire = Part.Wire(Part.__sortEdges__([bs.toShape()] + Part.makePolygon([pts[-1], low[0], low[1], pts[0]]).Edges))
    body = Part.Face(wire).extrude(e * (L + 80)).common(prism(palm_f, -TONGUE, 60))
    edges = "square"
    try:                                          # round the top's side and front edges
        top = max((f for f in body.Faces if f.CenterOfMass.z > 5 and abs(f.normalAt(*f.Surface.parameter(f.CenterOfMass)).z) > 0.3),
                  key=lambda f: f.Area)
        ed = [x for x in top.Edges if not all(abs((v.Point - A).dot(n)) < 0.01 for v in x.Vertexes)]
        r = body.makeFillet(EDGE_R, ed)
        if r.isValid() and r.Volume > 0.9 * body.Volume:
            body, edges = r, f"rounded {EDGE_R:.0f} mm"
    except Exception as ex:
        edges = f"square (fillet failed: {ex})"
    a0, a1, t1 = E["a0"], E["a1"], E["t1"]
    tl = min(tt(q) for q in Q) - 40
    band = poly([B(a0, tl), B(a1, tl), B(a1, t1), B(a0, t1)])
    palm = body
    for f in (band.common(OUT), band.common(poly([F0 - n, F3 - n, Bp + n, A + n]))):
        palm = palm.fuse(prism(f, -TONGUE, 0))
    for p in foot_boss:
        palm = palm.cut(cyl(p, SCREW_D, -9, 1)).cut(cyl(p, HEAD_D, -9, -TONGUE + HEAD_LOW))
    for q in feet:                                # the tray's front Bumpons stay on, in holes of the tongue
        palm = palm.cut(cyl(q, FOOT_D + 1.2, -9, 1))
    pf = [A + fwd * PALM_FOOT + e * PALM_FOOT, Bp + fwd * PALM_FOOT - e * PALM_FOOT,
          A + fwd * (D - PALM_FOOT) + e * PALM_FOOT, Bp + fwd * (D - PALM_FOOT) - e * PALM_FOOT]
    pi = [A + fwd * (D - PALM_FOOT) + e * PALM_INS, Bp + fwd * (D - PALM_FOOT) - e * PALM_INS]
    for q in pf:
        palm = palm.cut(cyl(q, FOOT_D, -TONGUE - 1, -TONGUE + FOOT_DEPTH))
    for p in pi:
        palm = palm.cut(cyl(p, INSERT_D, -TONGUE - 1, -TONGUE + FOOT_INSERT))
    palm = palm.removeSplitter()
    new["palm"] = palm
    flat = palm.copy(); flat.rotate(V(0, 0, 0), V(0, 1, 0), 90 if F0.x < cen.x else -90)       # outer end down
    E["FLAT"]["palm"] = flat
    bb = palm_f.BoundBox
    rep.append(f"palm rest: {bb.XLength:.1f} wide, {D:.0f} deep, top {H - PALM_REAR:.0f} at the tray, {H:.0f} at {sp:.0f} mm, {PALM_FRONT:.0f} at the "
               f"front (above the tray's underside; its own underside {TONGUE:.0f} lower), edges {edges}; tongue {TONGUE:.0f} mm, M2 x 8 into "
               f"the tilt-bar inserts; flat on the desk the tray's front stands {TONGUE:.0f} mm higher ({math.degrees(math.atan(TONGUE / (t_rear - t1))):.1f} deg)")

    # ---- tilt bars under the palm rest's front edge (the tray on its rear feet)
    barp_f = poly([A + fwd * (D - 22) + e * 4, Bp + fwd * (D - 22) - e * 4, Bp + fwd * (D - 1) - e * 4, A + fwd * (D - 1) + e * 4]).common(palm_f)
    am = min(aa(q) for q in Q) - 100
    for ang in E["TILT"]:
        k = math.tan(math.radians(ang))
        zz = lambda t: -(t_rear - t) * k
        ta, tb = tl - D - 80, t_rear + 5
        pr = [B(am, ta) + V(0, 0, 1), B(am, tb) + V(0, 0, 1), B(am, tb) + V(0, 0, zz(tb)), B(am, ta) + V(0, 0, zz(ta))]
        bar = prism(barp_f, -200, -TONGUE).common(Part.Face(Part.makePolygon(pr + [pr[0]])).extrude(ua * 700))
        for p in pi:
            bar = bar.cut(cyl(p, SCREW_D, -210, 1)).cut(cyl(p, HEAD_D, -210, -TONGUE - BAR_UNDER))
        for q in pf[2:]:
            bar = bar.cut(cyl(q, FOOT_D + 1.2, -TONGUE - BUMP_H - 0.5, 1))
        new[f"tiltp{ang:.0f}"] = bar.removeSplitter()
        rep.append(f"tiltp{ang:.0f}: {-zz(tt(pi[0])) - TONGUE:.1f} / {-zz(tt(pi[1])) - TONGUE:.1f} mm at its screws (M2 x 6)")

    # ---- tent bases
    left_like = F0.x < cen.x                      # outer side at -X
    xo = OUT.BoundBox.XMin if left_like else OUT.BoundBox.XMax
    sg = 1 if left_like else -1
    ext = {}
    for m in ("left", "right"):
        cs = json.load(open(os.path.join(E["ROOT"], "build", "case", m + ".json")))["corners"]
        ext[m] = max(c[0] for c in cs) - min(c[0] for c in cs)
    width = OUT.BoundBox.XLength
    rear_feet = sorted(feet, key=tt)[2:]
    step = prism(poly([B(a0 - 0.3, tl), B(a1 + 0.3, tl), B(a1 + 0.3, t1 + 0.3), B(a0 - 0.3, t1 + 0.3)]), -TONGUE, 1).fuse(prism(big, -TONGUE, 1))
    def window(face, lim):                        # the open middle of a base: face less its rim, between two lines, corners rounded
        f = face.makeOffset2D(-WIN_EDGE, join=2).common(poly(lim)).Faces[0]
        return prism(f.makeOffset2D(-6.0, join=2).makeOffset2D(6.0), -400, 5)
    tA, tB = max(tt(p) for p in foot_boss + alt) + 10, min(tt(p) for p in rear_boss) - 10
    wide = lambda ta, tb: [B(am, ta), B(am + 800, ta), B(am + 800, tb), B(am, tb)]
    win_short = window(OUT, wide(tA, tB))
    win_long = window(OUT, wide(max(tA, t1 + 8), tB)).fuse(
        window(big, [A + fwd * 8 - e * 50, Bp + fwd * 8 + e * 50, Bp + fwd * (D - 26) + e * 50, A + fwd * (D - 26) - e * 50]))
    for ang in TENT:
        tan = math.tan(math.radians(ang))
        lift = (max(ext.values()) - ext[name]) * tan
        for long in (False, True):
            T0 = T_MIN + lift + (TONGUE if long else 0)
            def to_desk(s, back=False):           # the tray's underside plane -> the desk plane under the base (and back)
                s = s.copy()
                if back:
                    s.translate(V(0, 0, T0)); s.rotate(V(xo, 0, 0), V(0, 1, 0), -sg * ang)
                else:
                    s.rotate(V(xo, 0, 0), V(0, 1, 0), sg * ang); s.translate(V(0, 0, -T0))
                return s
            w = prism(OUT, -300, 0)
            if long:
                w = w.fuse(prism(big, -300, 0)).cut(step)
            w = w.common(to_desk(Part.makeBox(3000, 3000, 600, V(-1500, -1500, 0)))).cut(win_long if long else win_short)
            assert len(w.Solids) == 1, "tent base fell apart"
            for p in under:
                zt = -TONGUE if long and p in foot_boss else 0.0
                w = w.cut(cyl(p, SCREW_D, zt - BAR_UNDER - 1, 1)).cut(cyl(p, HEAD_D + 0.6, -300, zt - BAR_UNDER))
            ft, ins = (rear_feet + pf[2:], pi) if long else (feet, alt)
            cutters = [cyl(q, FOOT_D, -1, FOOT_DEPTH) for q in ft] + [cyl(p, INSERT_D, -1, FOOT_INSERT) for p in ins]
            w = w.cut(to_desk(Part.makeCompound(cutters))).removeSplitter()
            nm = f"tent{ang:.0f}" + ("-long" if long else "")
            new[nm] = w
            E["FLAT"][nm] = to_desk(w, back=True)
            if not long:
                rep.append(f"tent{ang:.0f}: {T0:.1f} mm at the outer edge (lift {lift:.1f}), {T0 + width * tan:.1f} at the split edge; long form "
                           f"{TONGUE:.0f} more; highest cap about {(T0 + width * tan) * math.cos(math.radians(ang)) + 30.5 + 1.8:.0f} above the desk")
    parts.update(new)
    tray = parts["tray"]
    pairs = [(k, s, "tray", tray) for k, s in new.items() if not k.startswith("tiltp")]
    pairs += [(k, s, "palm", palm) for k, s in new.items() if k.startswith("tiltp") or k.endswith("long")]
    pairs += [("palm", palm, "caps", refs["caps"])]
    return pairs, rep
