"""Pose options for the user's decisions (M3 session 4): tent angle, palm rest depth / height / top shape.

Preview only (envelopes, no joints). Run in the FreeCAD GUI through the MCP (execute_python_file) with the documents
case_left and case_right open (mech/case/build_case.py); fills the document "pose_options". The parts themselves
are built by mech/case/pose_case.py.
"""
import json
import math
import os

import FreeCAD as App
import Part

V = App.Vector
ROOT = "/Users/florin/projects/personal/keyboard"
FEET = 1.8             # Bumpon standing out of its recess


def module(name):
    d = json.load(open(os.path.join(ROOT, "build", "case", name + ".json")))
    xs = [c[0] for c in d["corners"]]; ys = [c[1] for c in d["corners"]]
    xc, yc = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    c = lambda p: V(p[0] - xc, -(p[1] - yc), 0)
    doc = App.getDocument("case_" + name)
    shp = Part.makeCompound([doc.getObject(n).Shape for n in ("tray", "caps", "cover", "plate")])
    keys = {k["id"]: c((k["x"], k["y"])) for k in d["keys"]}
    return dict(d=d, P=[c(p) for p in d["corners"]], shp=shp, tray=doc.getObject("tray").Shape, keys=keys)


def tent(m, ang, outer_sign, lift=0.0):
    """Module turned about its outer bottom edge (parallel to Y) by ang; returns (assembly, base wedge, f(point) -> height)."""
    bb = m["tray"].BoundBox
    x0 = bb.XMin if outer_sign < 0 else bb.XMax
    cen = (m["P"][0] + m["P"][1] + m["P"][2] + m["P"][3]) * 0.25
    q = [p + (p - cen) * (3.6 / (p - cen).Length) for p in m["P"]]
    wedge = Part.Face(Part.makePolygon(q + [q[0]])).extrude(V(0, 0, -120))
    rot = ang * (1 if outer_sign > 0 else -1)
    out = []
    for s in (m["shp"].copy(), wedge):
        s.rotate(V(x0, 0, 0), V(0, 1, 0), rot); s.translate(V(0, 0, lift + 3.0))
        out.append(s)
    out[1] = out[1].common(Part.makeBox(900, 900, 200, V(-450, -450, 0)))
    h = lambda p, z: lift + 3.0 + abs(p.x - x0) * math.sin(math.radians(ang)) + z * math.cos(math.radians(ang))
    return out[0], out[1], h


def palm(m, depth, height, shape):
    """Palm rest envelope in front of the left tray: rear edge along the tray's front, sides straight to the front."""
    P = m["P"]
    e = P[3] - P[0]; e.normalize()
    n = V(e.y, -e.x, 0)
    if n.y > 0:
        n = n * -1
    a, b = P[0] + n * 3.2 - e * 2.7, P[3] + n * 3.2 + e * 2.7
    fwd = V(0, -1, 0) * (1 / abs(n.y))
    foot = Part.Face(Part.makePolygon([a, b, b + fwd * depth, a + fwd * depth, a])).extrude(V(0, 0, 60))
    D, H = depth, height
    if shape == "ramp":
        prof = [(0, H), (D - 8, H - 6 * (D - 8) / D), (D - 2.5, H - 8.5), (D, H - 14)]
    elif shape == "level":
        prof = [(0, H)] + [(D - 8 + 8 * math.sin(t), H - 8 + 8 * math.cos(t)) for t in [i * math.pi / 16 for i in range(9)]]
    else:                                         # pillow: highest at 40 % of the depth
        prof = []
        for i in range(25):
            s = D * i / 24
            z = H - 3.0 * ((s - 0.4 * D) / (0.4 * D)) ** 2 if s < 0.4 * D else H - (H - 8.0) * ((s - 0.4 * D) / (0.6 * D)) ** 2
            prof.append((s, z))
    pts = [a - e * 30 + n * s + V(0, 0, z) for s, z in [(0, 0)] + prof + [(D, 0)]]
    return Part.Face(Part.makePolygon(pts + [pts[0]])).extrude(e * ((b - a).Length + 60)).common(foot)


def main():
    if "pose_options" in App.listDocuments():
        App.closeDocument("pose_options")
    L, R = module("left"), module("right")
    doc = App.newDocument("pose_options")
    wl, wr = L["tray"].BoundBox, R["tray"].BoundBox
    dx = wl.XMax - wr.XMin + 20.0

    def add(group, name, shape, colour, at):
        s = shape.copy(); s.translate(at)
        o = doc.addObject("Part::Feature", name); o.Shape = s
        o.ViewObject.ShapeColor = colour
        group.addObject(o)

    grey, orange, wood = (0.55, 0.57, 0.6), (0.85, 0.45, 0.10), (0.35, 0.55, 0.75)
    rows = [("TENT_5", 5, False), ("TENT_7", 7, False), ("TENT_10", 10, False), ("TENT_7_LEVEL", 7, True), ("TENT_5_LEVEL", 5, True)]
    for i, (gn, ang, level) in enumerate(rows):
        g = doc.addObject("App::DocumentObjectGroup", gn)
        rise = lambda m: m["tray"].BoundBox.XLength * math.sin(math.radians(ang))
        lift = rise(R) - rise(L) if level else 0.0
        la, lb, lh = tent(L, ang, -1, lift)
        ra, rb, rh = tent(R, ang, +1)
        at = V(0, 260.0 * i, 0)
        add(g, gn + "_left", la, grey, at); add(g, gn + "_left_base", lb, orange, at)
        add(g, gn + "_right", ra, grey, at + V(dx, 0, 0)); add(g, gn + "_right_base", rb, orange, at + V(dx, 0, 0))
        f, j = lh(L["keys"]["L_F"], 30.5), rh(R["keys"]["R_J"], 30.5)
        print(f"{gn}: split edge of the tray {lift + rise(L) + 3:.0f} (left) / {rise(R) + 3:.0f} (right) mm above the desk; cap tops at F {f:.0f}, "
              f"at J {j:.0f}; highest cap about {max(lift + rise(L), rise(R)) + 33.5:.0f}; left base lifted {lift:.0f}")
    flat = L["shp"].copy(); flat.translate(V(0, 0, FEET))
    sets = [("PALM_DEPTH", [(70, 22, "pillow"), (85, 22, "pillow"), (100, 22, "pillow")]),
            ("PALM_SHAPE", [(85, 22, "ramp"), (85, 22, "pillow"), (85, 22, "level")]),
            ("PALM_HEIGHT", [(85, 18, "pillow"), (85, 22, "pillow"), (85, 26, "pillow")])]
    for i, (gn, opts) in enumerate(sets):
        g = doc.addObject("App::DocumentObjectGroup", gn)
        for j, (dp, hh, sh) in enumerate(opts):
            at = V(200.0 * j, -330.0 * (i + 1), 0)
            add(g, f"{gn}_{j + 1}_tray", flat, grey, at)
            p = palm(L, dp, hh, sh); p.translate(V(0, 0, FEET))
            add(g, f"{gn}_{j + 1}_{sh}_{dp}x{hh}", p, wood, at)
    doc.recompute()
    import FreeCADGui as Gui
    Gui.ActiveDocument.ActiveView.viewIsometric(); Gui.SendMsgToActiveView("ViewFit")
    print("keys:", [k for k in L["keys"] if k in ("L_F", "L_A", "L_G")], [k for k in R["keys"] if k in ("R_J", "R_H")])


main()
