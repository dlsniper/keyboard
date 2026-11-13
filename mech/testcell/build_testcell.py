"""ASA test cell: two MX switches at their real relative position (R_QUOTE, R_RSHIFT).

Run (from repo root):
  /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd mech/testcell/build_testcell.py

Layout convention (layout/keys.json): x right, y towards the user (down the page),
rot positive = clockwise seen from above.  Mapping: X_fc = x - x_mid, Y_fc = -(y - y_mid)
(so rear/north = +Y, top view matches the keyboard), rotation about +Z = -rot (CCW positive).
Key-local u = right, v = north; world = centre + R(-rot)*(u,v).
"""
import os, json, math, itertools
import FreeCAD as App, Part, Mesh, MeshPart

# ---------------- parameters ----------------
ROOT = os.getcwd()
OUT = os.path.join(ROOT, "mech", "testcell")
KEYS_JSON = os.path.join(ROOT, "layout", "keys.json")
MODULE = "right"; KEY_IDS = ["R_QUOTE", "R_RSHIFT"]
PITCH = 19.05
MARGIN = 7.0; CORNER_R = 3.0
PLATE_T = 1.5; PCB_T = 1.6
BOSS_D = 6.5; BOSS_BOTTOM = -5.0; BOSS_INSET = 4.5
INSERT_D = 3.2; INSERT_DEPTH = 4.2
CUTOUT = 14.0; CUTOUT_CLR = 0.1
CENTER_D = 4.0; PIN_D = 1.75; HOT_D = 3.0; HOLE_CLR = 0.2
PIN_X = 5.08
HOT_POS = [(-3.81, 2.54), (2.54, 5.08)]
LED_W = 3.4; LED_H = 3.0; LED_CLR = 0.1; LED_POS = (0.0, -4.7)
SCREW_D = 2.2
BOSS_CLEAR_MIN = 2.0
PCB_Z0 = BOSS_BOTTOM; PCB_Z1 = BOSS_BOTTOM - PCB_T

# ---------------- input ----------------
data = json.load(open(KEYS_JSON))
print("convention:", data["convention"])
keys = {k["id"]: k for k in data["modules"][MODULE]["keys"]}
ks = [keys[i] for i in KEY_IDS]
xm = sum(k["x"] for k in ks) / 2; ym = sum(k["y"] for k in ks) / 2
V = App.Vector
cells = []
for k in ks:
    cells.append(dict(id=k["id"], w=k["w"], cx=k["x"] - xm, cy=-(k["y"] - ym), th=-k["rot"]))
    print("key %s local centre (%.3f, %.3f) layout rot %.3f -> FreeCAD rot %.3f deg CCW" %
          (k["id"], cells[-1]["cx"], cells[-1]["cy"], k["rot"], -k["rot"]))

def w2(c, u, v):
    t = math.radians(c["th"])
    return (c["cx"] + u*math.cos(t) - v*math.sin(t), c["cy"] + u*math.sin(t) + v*math.cos(t))

def rect_face(c, u, v, w, h, z=0.0):
    t = math.radians(c["th"])
    pts = [w2(c, u+a*w/2, v+b*h/2) for a, b in ((-1,-1),(1,-1),(1,1),(-1,1))]
    return Part.Face(Part.makePolygon([V(x, y, z) for x, y in pts] + [V(pts[0][0], pts[0][1], z)]))

def circ_face(x, y, d, z=0.0):
    return Part.Face(Part.Wire(Part.makeCircle(d/2, V(x, y, z))))

# ---------------- outline ----------------
xs, ys = [], []
for c in cells:
    f = rect_face(c, 0, 0, c["w"]*PITCH, PITCH)
    for p in f.Vertexes: xs.append(p.X); ys.append(p.Y)
x0, x1, y0, y1 = min(xs)-MARGIN, max(xs)+MARGIN, min(ys)-MARGIN, max(ys)+MARGIN
print("outline x[%.3f,%.3f] y[%.3f,%.3f] size %.3f x %.3f" % (x0, x1, y0, y1, x1-x0, y1-y0))

def slab(z0, z1):
    b = Part.makeBox(x1-x0, y1-y0, z1-z0, V(x0, y0, z0))
    return b.makeFillet(CORNER_R, [e for e in b.Edges if abs(e.Vertexes[0].Z - e.Vertexes[1].Z) > 1e-6])

def prism(face, z0, z1):
    f = face.copy(); f.translate(V(0, 0, z0 - f.BoundBox.ZMin))
    return f.extrude(V(0, 0, z1 - z0))

# ---------------- 2D features (faces at z=0) ----------------
cut_faces = [rect_face(c, 0, 0, CUTOUT+CUTOUT_CLR, CUTOUT+CUTOUT_CLR) for c in cells]
feat = []  # (cell index, name, face)
for i, c in enumerate(cells):
    feat.append((i, "centre", circ_face(*w2(c, 0, 0), CENTER_D+HOLE_CLR)))
    for s in (-1, 1):
        feat.append((i, "pin%+d" % s, circ_face(*w2(c, s*PIN_X, 0), PIN_D+HOLE_CLR)))
    for j, (u, v) in enumerate(HOT_POS):
        feat.append((i, "hot%d" % j, circ_face(*w2(c, u, v), HOT_D+HOLE_CLR)))
    feat.append((i, "led", rect_face(c, LED_POS[0], LED_POS[1], LED_W+LED_CLR, LED_H+LED_CLR)))
edge_feats = [("cutout%d" % i, f) for i, f in enumerate(cut_faces)] + [("k%d_%s" % (i, n), f) for i, n, f in feat]

# ---------------- bosses ----------------
def boss_ok(p):
    d = circ_face(p[0], p[1], BOSS_D)
    return min(d.distToShape(f)[0] for _, f in edge_feats)

corners = [(x0+BOSS_INSET, y0+BOSS_INSET, "x", "y"), (x1-BOSS_INSET, y0+BOSS_INSET, "x", "y"),
           (x1-BOSS_INSET, y1-BOSS_INSET, "x", "y"), (x0+BOSS_INSET, y1-BOSS_INSET, "x", "y")]
bosses = []
for (bx, by, _, _) in corners:
    m = boss_ok((bx, by))
    if m >= BOSS_CLEAR_MIN:
        bosses.append((bx, by)); continue
    best = None
    sx = 1 if bx < (x0+x1)/2 else -1; sy = 1 if by < (y0+y1)/2 else -1
    for k in range(1, 4000):
        for cand in ((bx + sx*0.1*k, by), (bx, by + sy*0.1*k)):
            lim_x = x0+BOSS_INSET <= cand[0] <= x1-BOSS_INSET
            lim_y = y0+BOSS_INSET <= cand[1] <= y1-BOSS_INSET
            if lim_x and lim_y and boss_ok(cand) >= BOSS_CLEAR_MIN:
                best = cand; break
        if best: break
    assert best, "no boss position passes"
    print("BOSS MOVED: (%.3f,%.3f) clearance %.3f -> (%.3f,%.3f), slid %.1f mm along outline edge" %
          (bx, by, m, best[0], best[1], math.hypot(best[0]-bx, best[1]-by)))
    bosses.append(best)
print("boss centres:", [(round(a, 3), round(b, 3)) for a, b in bosses])

# ---------------- plate ----------------
plate = slab(-PLATE_T, 0)
for f in cut_faces:
    plate = plate.cut(prism(f, -PLATE_T-1, 1))
for bx, by in bosses:
    plate = plate.fuse(Part.makeCylinder(BOSS_D/2, -PLATE_T-BOSS_BOTTOM, V(bx, by, BOSS_BOTTOM)))
for bx, by in bosses:
    plate = plate.cut(Part.makeCylinder(INSERT_D/2, INSERT_DEPTH, V(bx, by, BOSS_BOTTOM)))
plate = plate.removeSplitter()

# ---------------- pcb ----------------
pcb = slab(PCB_Z1, PCB_Z0)
for i, n, f in feat:
    pcb = pcb.cut(prism(f, PCB_Z1-1, PCB_Z0+1))
for bx, by in bosses:
    pcb = pcb.cut(Part.makeCylinder(SCREW_D/2, PCB_T+2, V(bx, by, PCB_Z1-1)))
pcb = pcb.removeSplitter()

# ---------------- assertions ----------------
print("---- checks ----")
for bi, (bx, by) in enumerate(bosses):
    d = circ_face(bx, by, BOSS_D)
    worst = min(((d.distToShape(f)[0], n) for n, f in edge_feats))
    print("boss %d clearance to nearest cutout/hole edge: %.3f mm (%s)" % (bi, worst[0], worst[1]))
    assert worst[0] >= BOSS_CLEAR_MIN - 1e-6
web = cut_faces[0].distToShape(cut_faces[1])[0]
print("min plate web between the two switch cutouts: %.3f mm" % web)
mn = min(((a[2].distToShape(b[2])[0], a[1], b[1]) for a, b in itertools.combinations(feat, 2) if a[0] != b[0]))
print("min distance between pcb holes of different keys: %.3f mm (%s vs %s)" % mn)
for n, s in (("plate", plate), ("pcb", pcb)):
    print("%s: valid=%s solids=%d shells=%d volume=%.2f mm3 bbox=%s" %
          (n, s.isValid(), len(s.Solids), len(s.Shells), s.Volume, s.BoundBox))
    assert s.isValid() and len(s.Solids) == 1

# ---------------- outputs ----------------
doc = App.newDocument("testcell")
for n, s in (("plate", plate), ("pcb", pcb)):
    doc.addObject("Part::Feature", n).Shape = s
doc.recompute()
doc.saveAs(os.path.join(OUT, "testcell.FCStd"))
plate.exportStep(os.path.join(OUT, "testcell-plate.step"))
pcb.exportStep(os.path.join(OUT, "testcell-pcb.step"))
pp = plate.copy(); pp.rotate(V(0,0,0), V(1,0,0), 180)   # top face on Z=0, bosses up
pc = pcb.copy(); pc.translate(V(0, 0, -PCB_Z1))
for n, s in (("plate", pp), ("pcb", pc)):
    m = MeshPart.meshFromShape(Shape=s, LinearDeflection=0.02, AngularDeflection=0.2, Relative=False)
    m.write(os.path.join(OUT, "testcell-%s.stl" % n))
    print("stl %s zmin=%.3f zmax=%.3f" % (n, s.BoundBox.ZMin, s.BoundBox.ZMax))
print("done")
