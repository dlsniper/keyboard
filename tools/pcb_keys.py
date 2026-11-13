#!/usr/bin/env python3
"""Place a key board (M2 step 1): outline, footprints and nets from layout/keys.json and the schematic.

Run with KiCad's Python (it needs pcbnew):
    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 tools/pcb_keys.py left
`--force` overwrites a board that already has tracks (routing is lost).

What it does, all from data (a changed layout or decision is a re-run):
- reads the schematic's netlist (kicad-cli), loads every footprint, sets nets and the schematic link (parity);
- per key: hotswap socket footprint at the key centre (front side; the socket itself is on the back), and on the
  back the LED (reverse mount, window south of the switch, as the M0 test cell), the matrix diode east of the LED
  and the LED's 100 n west of it; stabiliser holes for keys of 2u and more;
- board outline with straight edges (user, 2026-11-13): outer, front (parallel to the bottom row), inner (along
  the split) and rear (parallel to the F-row chord, REAR mm behind the caps: the full-width rear strip);
- rear strip: port bay at the inner end (2x6 header on the FRONT side, pins up, user 2026-11-13), expander,
  LED rail switch, passives, spare header; provisional M2 holes (user: place now, the case may move them at M3);
- writes the board-house rules (D6: JLCPCB, they assemble; all SMD parts on the back) into the .kicad_pro.

Mirror rule for mated headers (M1 review): the lower board carries a PinHeader footprint on its top side, the
upper board a PinSocket footprint on its BOTTOM side. KiCad's 2-row PinSocket footprints have the columns
swapped against PinHeader, so flipped to the bottom they put pin 1 on pin 1. Any other arrangement (socket on a
top side, entered from below, or two boards face to face) needs one footprint mirrored by hand and a check.
BAY below is the frozen bay geometry; the port board (and later pods) must use the same numbers.
"""
import json
import math
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parent.parent
HW = ROOT / "hardware"
KICAD = Path("/Applications/KiCad/KiCad.app/Contents")
CLI = KICAD / "MacOS" / "kicad-cli"
STOCK = KICAD / "SharedSupport" / "footprints"
PROJECT_LIBS = {
    "keyboard": HW / "lib" / "keyboard.pretty",
    "Switch_Keyboard_Hotswap_Kailh": HW / "lib" / "kiswitch" / "Switch_Keyboard_Hotswap_Kailh.pretty",
    "Mounting_Keyboard_Stabilizer": HW / "lib" / "kiswitch" / "Mounting_Keyboard_Stabilizer.pretty",
}

# ---- parameters (mm) ----------------------------------------------------------------------------
PITCH = 19.05
CAP_GAP = 1.05          # keycap = cell - 1.05 (layout/keys.json convention)
MARGIN_SIDE = 4.0       # outer and inner edge, beyond the caps
MARGIN_FRONT = 6.0      # front edge: room for the M2 holes
REAR = 25.0             # rear strip depth behind the F-row caps
FILLET = 3.0
LED_AT = (0.0, 4.7)     # as mech/testcell (window south of the switch)
DIODE_AT = (6.9, 4.2)   # east of the LED, long axis north-south, anode north (towards socket pad 2)
CAP_AT = (-6.9, 4.2)    # the LED's 100 n, west of it
TP_AT = (0.0, 8.3)      # LED_DOUT test pad, in the last LED's cell
STAB_FP = ("Mounting_Keyboard_Stabilizer", "Stabilizer_Cherry_MX_2.00u")   # Cherry: same spacing for 2u-2.75u
HOLE_FP = ("MountingHole", "MountingHole_2.2mm_M2")
# Port bay, frozen: local frame (a along the rear edge towards the inner end, t rearwards from the F-row cap
# line), origin on the bay centre line. Port board about 30 x 25 mm; its receptacle looks out of the rear edge.
BAY = {"width": 30.0, "header": (0.0, 7.0), "screws": ((-11.5, 20.0), (9.0, 20.0))}

# D6 (user, 2026-11-13): JLCPCB makes and assembles. Their 2-layer limits with margin.
RULES = {"min_clearance": 0.15, "min_track_width": 0.15, "min_via_diameter": 0.5, "min_via_annular_width": 0.13,
         "min_through_hole_diameter": 0.3, "min_hole_to_hole": 0.5, "min_hole_clearance": 0.25,
         "min_copper_edge_clearance": 0.3, "min_silk_clearance": 0.0}
DEFAULT_CLASS = {"name": "Default", "clearance": 0.2, "track_width": 0.25, "via_diameter": 0.6, "via_drill": 0.3,
                 "priority": 2147483647, "schematic_color": "rgba(0, 0, 0, 0.000)", "pcb_color": "rgba(0, 0, 0, 0.000)",
                 "bus_width": 12, "wire_width": 6, "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1,
                 "diff_pair_width": 0.2, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25}

mm = pcbnew.FromMM


def vec(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def rot(dx, dy, deg):
    """Offset (dx, dy) in a frame turned `deg` clockwise seen from above (y down)."""
    a = math.radians(deg)
    return dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)


# ---- schematic ----------------------------------------------------------------------------------
def read_netlist(sch):
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "n.xml"
        subprocess.run([str(CLI), "sch", "export", "netlist", "--format", "kicadxml", "-o", str(out), str(sch)],
                       check=True, capture_output=True)
        root = ET.parse(out).getroot()
    comps = {}
    for c in root.find("components"):
        props = {p.get("name"): p.get("value") for p in c.findall("property")}
        fields = {f.get("name"): f.text or "" for f in c.findall("fields/field")
                  if f.get("name") not in ("Footprint", "Datasheet", "Description")}
        comps[c.get("ref")] = {"value": c.findtext("value"), "fp": c.findtext("footprint"), "fields": fields,
                               "uuid": c.findtext("tstamps"), "key": fields.get("KeyID"), "nets": {},
                               "no_bom": "exclude_from_bom" in props, "no_pos": "exclude_from_board" in props}
    for net in root.find("nets"):
        for node in net.findall("node"):
            comps[node.get("ref")]["nets"][node.get("pin")] = net.get("name")
    return comps


def load_fp(fpid):
    lib, name = fpid.split(":", 1) if isinstance(fpid, str) else fpid
    path = PROJECT_LIBS.get(lib, STOCK / f"{lib}.pretty")
    fp = pcbnew.FootprintLoad(str(path), name)
    if fp is None:
        sys.exit(f"footprint not found: {lib}:{name}")
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


class Board:
    def __init__(self, name, force):
        self.name = name
        self.path = HW / name / f"{name}.kicad_pcb"
        old = self.path.read_text() if self.path.exists() else ""
        if ("(segment" in old or "(via" in old or "(zone" in old) and not force:
            sys.exit(f"{self.path.name} has tracks or zones; --force would discard the routing")
        # always a fresh board (2 layers, 1.6 mm: KiCad's defaults); emptying a loaded one upsets the Python bindings
        self.b = pcbnew.CreateEmptyBoard()
        self.comps = read_netlist(self.path.with_suffix(".kicad_sch"))
        self.nets, self.placed, self.extra = {}, {}, 0

    def net(self, name):
        if name not in self.nets:
            ni = pcbnew.NETINFO_ITEM(self.b, name)
            self.b.Add(ni)
            self.nets[name] = ni
        return self.nets[name]

    def _put(self, fp, x, y, angle, back):
        self.b.Add(fp)
        fp.SetPosition(vec(x, y))
        if back:
            fp.Flip(vec(x, y), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetOrientationDegrees(angle)

    def place(self, ref, x, y, angle=0.0, back=False):
        """Schematic part `ref` at x, y; angle in KiCad's sense (counter-clockwise seen from above)."""
        c = self.comps[ref]
        if ref in self.placed:
            sys.exit(f"{ref} placed twice")
        fp = load_fp(c["fp"])
        fp.SetReference(ref)
        fp.SetValue(c["value"])
        fp.SetPath(pcbnew.KIID_PATH(c["uuid"] if c["uuid"].startswith("/") else "/" + c["uuid"]))
        for fname, text in c["fields"].items():                # symbol fields, hidden (schematic parity, BOM)
            fp.SetField(fname, text)
            fp.GetField(fname).SetVisible(False)
        bom = pcbnew.FP_EXCLUDE_FROM_BOM                         # the symbol decides, not the library footprint
        fp.SetAttributes(fp.GetAttributes() | bom if c["no_bom"] else fp.GetAttributes() & ~bom)
        if ref.startswith(("LED", "CL", "D")) and c["key"] or ref.startswith("CL"):
            fp.Reference().SetVisible(False)                   # under-key parts: no room for silk; the fab layer names them
        for pad in fp.Pads():
            n = c["nets"].get(pad.GetNumber())
            if n:
                pad.SetNet(self.net(n))
        self._put(fp, x, y, angle, back)
        self.placed[ref] = fp
        return fp

    def mech(self, fpid, prefix, x, y, angle=0.0):
        """Board-only footprint (holes): not in the schematic."""
        fp = load_fp(fpid)
        self.extra += 1
        fp.SetReference(f"{prefix}{self.extra}")
        fp.Reference().SetVisible(False)
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        self._put(fp, x, y, angle, False)
        return fp

    def pad_xy(self, ref, pad):
        p = self.placed[ref].FindPadByNumber(pad).GetPosition()
        return pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)

    def find(self, prefix, *nets):
        """Unplaced parts with this reference prefix whose pins sit on exactly these nets (netlist names end with them)."""
        out = []
        for ref, c in self.comps.items():
            if ref in self.placed or ref.rstrip("0123456789") != prefix:
                continue
            have = sorted(n.lstrip("/") for n in c["nets"].values())
            if have == sorted(nets):
                out.append(ref)
        return sorted(out, key=lambda r: int(r[len(prefix):]))

    def by_key(self, prefix, key):
        got = [r for r, c in self.comps.items() if c["key"] == key and r.rstrip("0123456789") == prefix]
        if len(got) != 1:
            sys.exit(f"{prefix} for key {key}: {got}")
        return got[0]

    def line(self, p, q, layer=pcbnew.Edge_Cuts, width=0.1):
        s = pcbnew.PCB_SHAPE(self.b)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(vec(*p)); s.SetEnd(vec(*q))
        s.SetLayer(layer); s.SetWidth(mm(width))
        self.b.Add(s)

    def arc(self, p, m, q):
        s = pcbnew.PCB_SHAPE(self.b)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(vec(*p), vec(*m), vec(*q))
        s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(mm(0.1))
        self.b.Add(s)


# ---- geometry -----------------------------------------------------------------------------------
def cap_corners(k):
    w, h = k["w"] * PITCH - CAP_GAP, k["h"] * PITCH - CAP_GAP
    return [(k["x"] + ox, k["y"] + oy) for ox, oy in (rot(sx * w / 2, sy * h / 2, k["rot"])
                                                        for sx in (-1, 1) for sy in (-1, 1))]


def hull(points):
    pts = sorted(set(points))
    def half(seq):
        h = []
        for p in seq:
            while len(h) >= 2 and (h[-1][0] - h[-2][0]) * (p[1] - h[-2][1]) - (h[-1][1] - h[-2][1]) * (p[0] - h[-2][0]) <= 0:
                h.pop()
            h.append(p)
        return h[:-1]
    return half(pts) + half(reversed(pts))


def support(points, n, margin):
    """Line n.p = d just outside all points, moved out by margin."""
    return n, max(p[0] * n[0] + p[1] * n[1] for p in points) + margin


def meet(l1, l2):
    (a, b), e = l1
    (c, d), f = l2
    det = a * d - b * c
    return (e * d - b * f) / det, (a * f - e * c) / det


def outline(keys, inner_sign):
    """Four straight edges. inner_sign = +1 if the split (inner) edge is on the +x side (left), -1 on `right`."""
    pts = [p for k in keys for p in cap_corners(k)]
    frow = sorted((k for k in keys if k["prow"] == 0), key=lambda k: k["x"])
    brow = [k for k in keys if k["prow"] == max(q["prow"] for q in keys)]
    phi = math.degrees(math.atan2(frow[-1]["y"] - frow[0]["y"], frow[-1]["x"] - frow[0]["x"]))
    front_rot = sum(k["rot"] for k in brow) / len(brow)
    # inner edge: the longest convex-hull edge that faces the split
    h = hull(pts)
    best = None
    for i, p in enumerate(h):
        q = h[(i + 1) % len(h)]
        ln = math.hypot(q[0] - p[0], q[1] - p[1])
        n = ((q[1] - p[1]) / ln, -(q[0] - p[0]) / ln)
        if sum(n[0] * c[0] + n[1] * c[1] for c in pts) / len(pts) > n[0] * p[0] + n[1] * p[1]:
            n = (-n[0], -n[1])
        if n[0] * inner_sign > 0.8 and (best is None or ln > best[0]):
            best = (ln, n)
    rear = support(pts, rot(0, -1, phi), 0.0)                 # the F-row cap line; the board edge is REAR behind it
    lines = {"outer": support(pts, (-inner_sign, 0), MARGIN_SIDE), "rear": (rear[0], rear[1] + REAR),
             "inner": support(pts, best[1], MARGIN_SIDE), "front": support(pts, rot(0, 1, front_rot), MARGIN_FRONT)}
    order = ["outer", "rear", "inner", "front"]
    corners = [meet(lines[order[i - 1]], lines[order[i]]) for i in range(4)]   # outer/front... each: previous x this
    origin = meet(lines["outer"], rear)                        # strip frame origin: cap line at the outer board edge
    return lines, corners, origin, phi, front_rot


def draw_outline(bd, corners):
    n = len(corners)
    cut = []
    for i, p in enumerate(corners):
        a, c = corners[i - 1], corners[(i + 1) % n]
        d1 = (a[0] - p[0], a[1] - p[1]); d2 = (c[0] - p[0], c[1] - p[1])
        l1, l2 = math.hypot(*d1), math.hypot(*d2)
        d1 = (d1[0] / l1, d1[1] / l1); d2 = (d2[0] / l2, d2[1] / l2)
        half = math.acos(max(-1, min(1, d1[0] * d2[0] + d1[1] * d2[1]))) / 2
        t = FILLET / math.tan(half)
        bis = (d1[0] + d2[0], d1[1] + d2[1]); bl = math.hypot(*bis)
        m = FILLET / math.sin(half) - FILLET
        cut.append(((p[0] + d1[0] * t, p[1] + d1[1] * t), (p[0] + bis[0] / bl * m, p[1] + bis[1] / bl * m),
                    (p[0] + d2[0] * t, p[1] + d2[1] * t)))
    for i, (p, m, q) in enumerate(cut):
        bd.arc(p, m, q)
        bd.line(q, cut[(i + 1) % n][0])


def inside(lines, p, margin):
    return all(n[0] * p[0] + n[1] * p[1] <= d - margin for n, d in lines.values())


# ---- placement ----------------------------------------------------------------------------------
def place_keys(bd, keys):
    errors = []
    leds = sorted((k for k in keys if k.get("led") is not None and k["kind"] == "switch"), key=lambda k: k["led"])
    for k in keys:
        if k["kind"] != "switch":
            continue
        x, y, r = k["x"], k["y"], k["rot"]
        at = lambda off: (x + rot(*off, r)[0], y + rot(*off, r)[1])
        north = lambda p: rot(p[0] - x, p[1] - y, -r)          # board point back into the key frame
        bd.place(bd.by_key("SW", k["id"]), x, y, -r)
        if k["stab"]:
            bd.mech(STAB_FP, "ST", x, y, -r + (90 if k["h"] > k["w"] else 0))
        d = bd.by_key("D", k["id"])
        bd.place(d, *at(DIODE_AT), -r + 90, back=True)
        if north(bd.pad_xy(d, "2"))[1] > north(bd.pad_xy(d, "1"))[1]:      # anode (pad 2) must be the north pad
            bd.placed[d].SetOrientationDegrees(-r + 270)
        if not north(bd.pad_xy(d, "2"))[1] < north(bd.pad_xy(d, "1"))[1]:
            errors.append(f"{d}: anode is not north")
    for i, k in enumerate(leds):
        x, y, r = k["x"], k["y"], k["rot"]
        at = lambda off: (x + rot(*off, r)[0], y + rot(*off, r)[1])
        led = bd.by_key("LED", k["id"])
        fp = bd.place(led, *at(LED_AT), -r, back=True)
        # turn the LED so that DIN (2) looks at the previous LED and DOUT (4) at the next one
        prev, nxt = leds[i - 1] if i else None, leds[i + 1] if i + 1 < len(leds) else None
        def cost():
            c = 0.0
            for pad, other in (("2", prev), ("4", nxt)):
                if other:
                    px, py = bd.pad_xy(led, pad)
                    c += math.hypot(px - other["x"], py - other["y"])
            return c
        c0 = cost()
        fp.SetOrientationDegrees(-r + 180)
        if cost() > c0:
            fp.SetOrientationDegrees(-r)
        cap = "CL" + led[3:]
        bd.place(cap, *at(CAP_AT), -r + 90, back=True)
        # self-check: LED centre where the test cell has the window
        cx, cy = pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y)
        if math.hypot(cx - at(LED_AT)[0], cy - at(LED_AT)[1]) > 0.001 or not fp.IsFlipped():
            errors.append(f"{led}: not at the window on the back")
    last = leds[-1]
    tp = bd.find("TP", "LED_DOUT")
    if tp:
        bd.place(tp[0], last["x"] + rot(*TP_AT, last["rot"])[0], last["y"] + rot(*TP_AT, last["rot"])[1], 0, back=True)
    return errors


def place_strip(bd, lines, origin, phi, inner_sign, keys):
    """Rear strip. Local frame: s along the rear edge from the outer board edge towards the split, t rearwards."""
    def at(s, t):
        dx, dy = rot(inner_sign * s, -t, phi)
        return origin[0] + dx, origin[1] + dy
    A = -phi                                                    # KiCad angle of the strip's s axis
    # bay: as far towards the split as the 30 mm wide port board fits
    half = BAY["width"] / 2
    sb = 400.0
    while not all(inside(lines, at(sb + e * half, t), 1.5) for e in (-1, 1) for t in (1.0, REAR - 2.0)):
        sb -= 0.5
        if sb < half:
            sys.exit("the port bay does not fit in the rear strip")
    hx, ht = BAY["header"]
    j1 = bd.find("J", *(["+5V", "+5V", "GND", "GND", "LED_DIN", "+3V3", "SPARE", "INT", "CS", "MISO", "MOSI", "SCK"]))[0]
    # 2x6 header, long axis along s, on the FRONT side (pins up); centred on the bay centre line
    fp = bd.place(j1, *at(sb + hx, ht), A + 90)
    c = fp.GetBoundingBox(False).Centre()
    want = at(sb + hx, ht)
    fp.Move(vec(want[0] - pcbnew.ToMM(c.x), want[1] - pcbnew.ToMM(c.y)))
    for a, t in BAY["screws"]:
        bd.mech(HOLE_FP, "H", *at(sb + a, t))
    # expander(s), outwards of the bay, long axis along s
    s = sb - 33.0
    chips = sorted(r for r in bd.comps if r.startswith("U") and "MCP23S17" in bd.comps[r]["value"])
    first_chip = s
    for u in chips:
        bd.place(u, *at(s, 9.0), A + 90, back=True)
        n_reset = f"RESET_{u}"
        col = s - 13.5
        for ref, t in ((bd.find("C", "+3V3", "GND")[0], 5.0), (bd.find("R", "+3V3", n_reset)[0], 8.0), (bd.find("C", "GND", n_reset)[0], 11.0)):
            bd.place(ref, *at(col, t), A, back=True)
        last_chip = s
        s -= 36.0
    # column (and dial) pull-ups in a row behind the first chip(s)
    pull = sorted((r for r, c in bd.comps.items() if r not in bd.placed and r.startswith("R") and c["value"] == "10k"
                   and "+3V3" in [n.lstrip("/") for n in c["nets"].values()]), key=lambda r: int(r[1:]))
    for i, r in enumerate(pull):
        bd.place(r, *at(first_chip + 8.0 - i * 2.6, 19.5), A + 90, back=True)
    # LED rail switch and its parts, outwards of the last chip
    s = last_chip - 22.0
    bd.place(next(r for r in bd.comps if "TPS22918" in bd.comps[r]["value"]), *at(s, 8.0), A, back=True)
    bd.place(bd.find("C", "+5V_LED", "GND")[-1] if len(bd.find("C", "+5V_LED", "GND")) > 1 else bd.find("C", "+5V_LED", "GND")[0],
             *at(s, 14.0), A, back=True)
    rest = [r for r in ("C", "R") for r in bd.find(r, "+5V", "GND") + bd.find(r, "+5V_LED", "GND") + bd.find(r, "GND", "LED_CT")
            + bd.find(r, "GND", "LED_EN")]
    for i, r in enumerate(rest):
        bd.place(r, *at(s - 7.0, 5.0 + 3.0 * i), A, back=True)
    # spare-pin header on the front side, long axis along s
    j2 = next(r for r, c in bd.comps.items() if r.startswith("J") and c["value"] == "SPARE")
    fp = bd.place(j2, *at(s - 20.0, 10.0), A + 90)
    c = fp.GetBoundingBox(False).Centre()
    want = at(s - 20.0, 10.0)
    fp.Move(vec(want[0] - pcbnew.ToMM(c.x), want[1] - pcbnew.ToMM(c.y)))
    # 220 R in front of the first LED: in the strip behind that key
    first = min((k for k in keys if k.get("led") is not None), key=lambda k: k["led"])
    r220 = bd.find("R", "LED_D0", "LED_DIN")[0]
    fx, fy = first["x"] - origin[0], first["y"] - origin[1]
    s_first = inner_sign * rot(fx, fy, -phi)[0]
    bd.place(r220, *at(s_first, 4.0), A, back=True)
    # provisional M2 holes: three in the strip
    for sh in (7.0, sb - 19.5, (7.0 + sb - 19.5) / 2):
        bd.mech(HOLE_FP, "H", *at(sh, 19.0))
    return sb


def front_holes(bd, lines, corners, front_rot, inner_sign):
    """Two provisional M2 holes in the front margin, 3 mm from the front edge, 12 mm in from the side edges."""
    n, d = lines["front"]
    u = rot(1, 0, front_rot)
    for corner, sgn in ((corners[0], inner_sign), (corners[3], -inner_sign)):   # front-outer, inner-front
        x, y = corner[0] + u[0] * 12.0 * sgn - n[0] * 3.0, corner[1] + u[1] * 12.0 * sgn - n[1] * 3.0
        bd.mech(HOLE_FP, "H", x, y)


DRU = """(version 1)
# Written by tools/pcb_keys.py. Two places where the footprint itself is closer than the board-wide rule:
# the reverse-mount LED's pads sit 0.25 mm from its own window, and the MX socket's hole is 0.44 mm from the
# switch's locating-peg hole (fixed by the switch; every hotswap board has it).
(rule "LED window to its own pads"
  (condition "A.Type == 'Pad' && A.memberOfFootprint('LED*')")
  (constraint edge_clearance (min 0.2mm)))
(rule "MX switch holes"
  (condition "A.memberOfFootprint('SW*') && B.memberOfFootprint('SW*')")
  (constraint hole_to_hole (min 0.4mm)))
"""


def write_rules(name):
    (HW / name / f"{name}.kicad_dru").write_text(DRU)
    p = HW / name / f"{name}.kicad_pro"
    pro = json.loads(p.read_text())
    pro.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rules", {}).update(RULES)
    pro.setdefault("net_settings", {})["classes"] = [DEFAULT_CLASS]
    p.write_text(json.dumps(pro, indent=2) + "\n")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        sys.exit(__doc__)
    name = args[0]
    mod = json.loads((ROOT / "layout" / "keys.json").read_text())["modules"][name]
    keys = mod["keys"]
    inner_sign = -1 if name == "right" else 1
    bd = Board(name, "--force" in sys.argv)
    lines, corners, origin, phi, front_rot = outline([k for k in keys if k["kind"] == "switch"], inner_sign)
    # corners come as front x outer, outer x rear, rear x inner, inner x front
    draw_outline(bd, corners)
    errors = place_keys(bd, keys)
    sb = place_strip(bd, lines, origin, phi, inner_sign, keys)
    front_holes(bd, lines, corners, front_rot, inner_sign)
    missing = sorted(set(bd.comps) - set(bd.placed))
    if missing:
        errors.append(f"not placed: {missing}")
    for ref, fp in bd.placed.items():
        p = fp.GetPosition()
        if not inside(lines, (pcbnew.ToMM(p.x), pcbnew.ToMM(p.y)), 1.0):
            errors.append(f"{ref} is outside the outline")
    pcbnew.SaveBoard(str(bd.path), bd.b)
    write_rules(name)
    xs, ys = [c[0] for c in corners], [c[1] for c in corners]
    print(f"{name}: {len(bd.placed)} schematic parts + {bd.extra} board-only (stabilisers, holes); "
          f"outline {max(xs) - min(xs):.1f} x {max(ys) - min(ys):.1f} mm bounding box, "
          f"rear strip at {phi:.2f} deg, front edge at {front_rot:.2f} deg, bay centre {sb:.1f} mm from the outer edge")
    print("corners:", ", ".join(f"({x:.2f}, {y:.2f})" for x, y in corners))
    for e in errors:
        print("ERROR", e)
    # leave without interpreter shutdown: pcbnew's objects crash Python's final garbage collection (segfault, macOS crash dialog)
    sys.stdout.flush()
    os._exit(1 if errors else 0)


if __name__ == "__main__":
    main()
