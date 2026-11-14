#!/usr/bin/env python3
"""Route a placed key board (M2 step 2).

Run with KiCad's Python, KiCad closed, after tools/pcb_keys.py (which must have left the board without tracks):
    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 tools/route_keys.py left
Then: tools/pcb_check.sh left   (DRC with schematic parity)

1. The key field is routed by this script, the same pattern in every key cell (coordinates below are in the key's
   own frame: x east, y south, mm from the switch centre; everything is on the back except the columns):
   - switch pad 2 -> diode anode, straight north-south at x = 6.9;
   - ROW: diode cathode -> row trunk at y = ROW_Y, west-east through the row;
   - COL: switch pad 1 -> via at COL_VIA -> front side, down the column along the cell borders;
   - the LED's 100 n sits between the LED and the diode, its +5V pad 1.5 mm from the LED's VDD pad (since M2
     session 9; it was west of the LED on 9.5 mm of track), its GND pad on its own via (CAP_VIA, north of it, added after the strip router);
   - LED data: DOUT (east) -> between the 100 n's pads -> under the diode (between its pads) -> DIN (west) of the
     next key; at the end of a row it returns west along RET_Y and enters the next row's first key;
   - +5V_LED, 0.8 mm: entry point IN_5V west of the LED -> south of the LED window -> 100 n -> LED, and from the
     100 n under the diode to the next key's entry point; the rows are joined by a 1 mm bus along the outer edge;
   - GND: LED -> via (GND_VIA), 100 n -> via (CAP_VIA); the ground itself is the pour on both sides.
   Stabilised keys: row trunk and return line dip south of the stabiliser's wire holes.
   The rows always start at the west end (LED chain west to east), so the +5V bus runs along the west board edge
   (outer edge on `left` and `numpad`, split edge on `right`) and the bottom row's riser along the east edge.
   A tall key that sits half a pitch south of its row (numpad +): the four lines step south in the gap west of it
   (STEP). Column links that the plain pattern cannot make (a long sideways run, a key of another column in
   between) are searched on the front side against the real holes, windows, vias and tracks (col_options).
2. `--strip`: the rear strip (expander, pull-ups, rail switch, headers) and its links to the field are left to
   Freerouting with the field locked (work files in build/route/<name>/).
3. GND pours on both sides, refilled and saved through kicad-cli; reference texts moved off pads and each
   other (tools/silk_keys.py).
The strip router's result differs from run to run: if tools/pcb_check.sh reports an open net, place and route again.
"""
import math
import os
import re
import subprocess
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
import silk_keys  # noqa: E402
from pcb_keys import PITCH, REAR, ROOT, frame, meet, rot  # noqa: E402

JAR = Path.home() / "Documents/KiCad/10.0/3rdparty/plugins/app_freerouting_kicad-plugin/jar/freerouting-2.5.0.jar"
CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
ZONE_CLEARANCE, ZONE_MIN = 0.25, 0.25

W_SIG, W_GND, W_5V, W_BUS = 0.25, 0.4, 0.8, 1.0
ROW_Y, ROW_DIP = 8.2, 10.7           # row trunk; south of a stabiliser's lower holes
RET_Y, RET_DIP = 8.9, 11.4           # LED data return line
WRAP_Y = 7.2                         # +5V south of the LED window
COL_VIA = (-9.1, -2.54)
COL_YS = (9.4, 10.9, 8.0, 12.0)      # where a column steps sideways between two rows (upper key's frame): first that clears the stabiliser holes
STAB_HOLES = ((11.94, 8.22, 2.0), (11.94, -6.99, 1.53))   # x (both signs), y, radius in the key's frame
GND_VIA = (-4.7, 3.16)
DIODE_CH, DIODE_5V = 3.7, 4.7        # the two lanes between the diode's pads
CAP_CH = 4.2                         # where LED data comes in from the west
IN_5V = (-6.9, 5.24)                 # where +5V_LED enters a cell from the west (the 100 n's pad until session 9)
CAP_VIA = (0.38, 1.06)               # GND via of the 100 n: east and north of its GND pad, in line with the switch's east peg
                                     # hole. Put in after the strip router (stitch): drawn before it, the router left row
                                     # links open on every run (it takes the rows down the front-side lanes beside that hole)
BUS_X = 1.8                          # +5V bus: mm inside the outer board edge
FEED_T = REAR - 2.5                  # +5V feed from the rail switch: along the rear edge of the strip (`left`: switch mid-strip)
FEED_NEAR = 16.9                     # ... or just behind the bulk capacitor where the switch is at the bus end (`right`, `numpad`)
FEED_LANE = {"left": FEED_T}
COL_LANES = (-9.1, -9.7, -10.3, -10.9, -11.5, -12.1, -8.5, -7.9, -7.3)   # long sideways column runs, y in the lower key's frame
COL_MID = (-8.0, 8.0)                # column passing through a key of another column: x in that key's frame
# A tall key half a pitch south of its west neighbour a: where each line turns (a's frame) and comes down (the tall key's frame)
STEP = {"data": ((9.2, 7.9), (-8.0, 0.225)), "v5": ((8.3, 8.1), (-9.0, 0.325)), "row": (-10.05, 0.775),
        "ret": (6.1, (-10.65, 1.675))}

mm = pcbnew.FromMM
F, B = pcbnew.F_Cu, pcbnew.B_Cu


class Router:
    def __init__(self, board, keys, inner_sign, origin, phi, lines, feed_t=FEED_T):
        self.b, self.inner, self.origin, self.phi, self.lines = board, inner_sign, origin, phi, lines
        self.feed_t, self._obs, self._dip, self.why = feed_t, None, {}, None
        self.keys = [k for k in keys if k["kind"] == "switch"]
        self.fp = {}                                            # key id -> {"SW": fp, "D": fp, "LED": fp, "CL": fp}
        for fp in board.GetFootprints():
            ref = fp.GetReference()
            kind = ref.rstrip("0123456789")
            if kind in ("SW", "D", "LED") and fp.HasField("KeyID") and fp.GetFieldText("KeyID"):
                self.fp.setdefault(fp.GetFieldText("KeyID"), {})[kind] = fp
        for parts in self.fp.values():
            if "LED" in parts:
                parts["CL"] = board.FindFootprintByReference("CL" + parts["LED"].GetReference()[3:])
        self.count = 0

    # geometry ----------------------------------------------------------------------------------
    @staticmethod
    def P(k, x, y):
        dx, dy = rot(x, y, k["rot"])
        return k["x"] + dx, k["y"] + dy

    def local(self, k, pad):
        p = pad.GetPosition()
        return rot(pcbnew.ToMM(p.x) - k["x"], pcbnew.ToMM(p.y) - k["y"], -k["rot"])

    def pad(self, k, kind, num):
        pad = self.fp[k["id"]][kind].FindPadByNumber(num)
        return self.local(k, pad), pad.GetNet()

    def track(self, net, pts, width, layer=B):
        for p, q in zip(pts, pts[1:]):
            if math.hypot(q[0] - p[0], q[1] - p[1]) < 0.005:
                continue
            t = pcbnew.PCB_TRACK(self.b)
            t.SetStart(pcbnew.VECTOR2I(mm(p[0]), mm(p[1])))
            t.SetEnd(pcbnew.VECTOR2I(mm(q[0]), mm(q[1])))
            t.SetWidth(mm(width)); t.SetLayer(layer); t.SetNet(net); t.SetLocked(True)
            self.b.Add(t)
            self.count += 1

    def via(self, net, p, size=0.6, drill=0.3):
        v = pcbnew.PCB_VIA(self.b)
        v.SetPosition(pcbnew.VECTOR2I(mm(p[0]), mm(p[1])))
        v.SetWidth(pcbnew.F_Cu, mm(size)); v.SetDrill(mm(drill)); v.SetNet(net); v.SetLocked(True)
        self.b.Add(v)
        self.count += 1

    @staticmethod
    def stab(k):
        return k["stab"] and k["w"] >= k["h"]

    def dipped(self, k):
        """A stabilised key's lines dip south of its holes in one piece, unless the stabiliser holes of a key in
        the next row are in the way there (`right`: Enter above Shift); then they come back up between its own
        two holes and the middle of the cell is as on any key."""
        if not self.stab(k):
            return False
        if k["id"] not in self._dip:
            self._dip[k["id"]] = all(self.clear([self.P(k, -15.3, y), self.P(k, 15.3, y)], 0.4) for y in (ROW_DIP, RET_DIP))
        return self._dip[k["id"]]

    def lane(self, k, y, dip, grow=0.0):
        """West-to-east line through a key's cell at y, dipping to `dip` under a stabiliser."""
        hw = k["w"] * PITCH / 2
        if self.stab(k):
            a, m = 14.6 + grow, 9.0 - grow
            mid = [(-a, dip), (a, dip)] if self.dipped(k) else [(-a, dip), (-m - 1.0, dip), (-m, y), (m, y), (m + 1.0, dip), (a, dip)]
            return [(-hw, y), (-a - 1.0, y)] + mid + [(a + 1.0, y), (hw, y)]
        return [(-hw, y), (hw, y)]

    @staticmethod
    def join(pts, more):
        """Append the next cell's points; where the two cells do not quite meet (0.45-1.5 mm), one shared point
        instead of a kink, so that parallel lines stay parallel across the border."""
        if pts and more and 0.45 < math.hypot(more[0][0] - pts[-1][0], more[0][1] - pts[-1][1]) < 1.5:
            pts[-1] = ((pts[-1][0] + more[0][0]) / 2, (pts[-1][1] + more[0][1]) / 2)
            more = more[1:]
        pts += more

    def clear(self, pts, gap):
        """True if the polyline keeps `gap` from every stabiliser hole."""
        for k in self.keys:
            if not k["stab"]:
                continue
            turn = -90 if k["h"] > k["w"] else 0               # as placed: the large holes of a vertical one are east
            for hx, hy, hr in STAB_HOLES:
                for sx in (-1, 1):
                    dx, dy = rot(sx * hx, hy, k["rot"] + turn)
                    c = (k["x"] + dx, k["y"] + dy)
                    for p, q in zip(pts, pts[1:]):
                        vx, vy = q[0] - p[0], q[1] - p[1]
                        t = max(0.0, min(1.0, ((c[0] - p[0]) * vx + (c[1] - p[1]) * vy) / (vx * vx + vy * vy or 1)))
                        if math.hypot(p[0] + t * vx - c[0], p[1] + t * vy - c[1]) < hr + gap:
                            return False
        return True

    def step(self, a, b):
        """True if b, a's east neighbour in the row, is a tall key half a pitch south of the row (STEP)."""
        dx, dy = rot(b["x"] - a["x"], b["y"] - a["y"], -a["rot"])
        if b["h"] <= 1 or abs(dy) < 3.0:
            return False
        if abs(dy - PITCH / 2) > 0.1 or abs(dx - PITCH) > 0.1 or a["rot"] != b["rot"]:
            print(f"WARNING {a['id']} -> {b['id']}: the step pattern is drawn for a key one pitch east, half a pitch south")
        return True

    def front_ok(self, net, pts, width=W_SIG):
        """True if a front-side polyline keeps the board rules from every hole, LED window, via, front track of
        another net and the board edge (sampled every 0.15 mm, a little more than the rules ask)."""
        if self._obs is None:
            holes, wins = [], []
            for fp in self.b.GetFootprints():
                for pad in fp.Pads():
                    d = pcbnew.ToMM(pad.GetDrillSize().x)
                    if d > 0:
                        q = pad.GetPosition()
                        cu = pcbnew.ToMM(pad.GetBoundingBox().GetWidth()) if pad.GetNetCode() else 0
                        holes.append((pcbnew.ToMM(q.x), pcbnew.ToMM(q.y), max(d, cu) / 2))
                if fp.GetReference().startswith("LED"):
                    q = fp.GetPosition()
                    wins.append((pcbnew.ToMM(q.x), pcbnew.ToMM(q.y), fp.GetOrientationDegrees()))
            self._obs = holes, wins
        holes, wins = self._obs
        name = net.GetNetname()
        vias, segs = [], []
        for t in self.b.GetTracks():
            if t.GetNetname() == name:
                continue
            if t.Type() == pcbnew.PCB_VIA_T:
                vias.append((pcbnew.ToMM(t.GetPosition().x), pcbnew.ToMM(t.GetPosition().y)))
            elif t.GetLayer() == F:
                segs.append((pcbnew.ToMM(t.GetStart().x), pcbnew.ToMM(t.GetStart().y), pcbnew.ToMM(t.GetEnd().x),
                             pcbnew.ToMM(t.GetEnd().y), pcbnew.ToMM(t.GetWidth()) / 2))
        h = width / 2
        for p, q in zip(pts, pts[1:]):
            ln = math.hypot(q[0] - p[0], q[1] - p[1])
            for i in range(int(ln / 0.15) + 2):
                f = min(1.0, i * 0.15 / ln) if ln else 0.0
                x, y = p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f
                self.why = f"({x:.1f}, {y:.1f})"
                if any(n[0] * x + n[1] * y > d - 0.4 - h for n, d in self.lines.values()):
                    return False
                if any(math.hypot(x - hx, y - hy) < hr + 0.3 + h for hx, hy, hr in holes):
                    return False
                if any(math.hypot(x - vx, y - vy) < 0.3 + 0.22 + h for vx, vy in vias):
                    return False
                for wx, wy, wa in wins:
                    if abs(x - wx) < 4 and abs(y - wy) < 4:
                        lx, ly = rot(x - wx, y - wy, wa)
                        if abs(lx) < 1.7 + 0.35 + h and abs(ly) < 1.5 + 0.35 + h:
                            return False
                for x1, y1, x2, y2, hw in segs:
                    vx, vy = x2 - x1, y2 - y1
                    t = max(0.0, min(1.0, ((x - x1) * vx + (y - y1) * vy) / (vx * vx + vy * vy or 1)))
                    if math.hypot(x1 + t * vx - x, y1 + t * vy - y) < hw + h + 0.22:
                        return False
        return True

    def rows(self, field):
        out = {}
        for k in self.keys:
            out.setdefault(k[field], []).append(k)
        return {r: sorted(ks, key=lambda k: k["x"]) for r, ks in sorted(out.items())}

    # the pattern -------------------------------------------------------------------------------
    def cell(self, k):
        P = lambda x, y: self.P(k, x, y)
        (sx, sy), n_net = self.pad(k, "SW", "2")
        (ax, ay), _ = self.pad(k, "D", "2")
        self.track(n_net, [P(ax, sy), P(ax, ay)], W_SIG)
        (cx, cy), row = self.pad(k, "D", "1")
        self.track(row, [P(cx, cy), P(cx, ROW_DIP if self.dipped(k) else ROW_Y)], W_SIG)
        (px, py), col = self.pad(k, "SW", "1")
        self.track(col, [P(px, py), P(*COL_VIA)], W_SIG)
        self.via(col, P(*COL_VIA))
        if "LED" not in self.fp[k["id"]]:
            return
        (gx, gy), gnd = self.pad(k, "CL", "2")
        (lx, ly), _ = self.pad(k, "LED", "1")
        self.track(gnd, [P(*GND_VIA), P(lx - 1.2, ly), P(lx, ly)], W_GND)
        self.via(gnd, P(*GND_VIA))
        (vx, vy), v5 = self.pad(k, "CL", "1")
        (ex, ey), _ = self.pad(k, "LED", "3")
        # up at ex + 1.7, not further east: the strip router needs the gap to the diode for its via onto the row trunk
        self.track(v5, [P(*IN_5V), P(IN_5V[0], WRAP_Y), P(ex + 1.7, WRAP_Y), P(ex + 1.7, vy), P(vx, vy)], W_5V)
        self.track(v5, [P(ex, ey), P(ex + 1.7, ey)], W_5V)

    def row_trunks(self):
        for ks in self.rows("row").values():
            pts, net = [], None
            for i, k in enumerate(ks):
                (cx, _), net = self.pad(k, "D", "1")
                yk = ROW_DIP if self.dipped(k) else ROW_Y
                ln = self.lane(k, ROW_Y, ROW_DIP)
                ln = [p for p in ln if p[0] < cx] + [(cx, yk)] + [p for p in ln if p[0] > cx]
                if i == 0:
                    ln = [p for p in ln if p[0] >= cx]
                if i == len(ks) - 1 or self.step(k, ks[i + 1]):
                    ln = [p for p in ln if p[0] <= cx]
                if i and self.step(ks[i - 1], k):
                    ln = [STEP["row"], (STEP["row"][0], ROW_Y)] + ln[1:]
                self.join(pts, [self.P(k, *p) for p in ln])
            self.track(net, pts, W_SIG)

    def col_path(self, a, b, ya):
        """Plain column link: down a's border to ya, straight across to b's border, down to b's via."""
        mid = self.P(a, COL_VIA[0], ya)
        ml = rot(mid[0] - b["x"], mid[1] - b["y"], -b["rot"])        # that point in the lower key's frame
        return [self.P(a, *COL_VIA), mid, self.P(b, COL_VIA[0], ml[1]), self.P(b, *COL_VIA)]

    def col_options(self, a, b):
        """Shapes for a column link the plain pattern does not make, in the order they are tried. The lanes come
        first and the columns are taken west to east, so that runs side by side nest without crossing."""
        loc = lambda k, p: rot(p[0] - k["x"], p[1] - k["y"], -k["rot"])
        for yb in COL_LANES:                                    # a's border extended to a lane along b's rear cell edge
            y0, y1 = loc(b, self.P(a, COL_VIA[0], 0.0))[1], loc(b, self.P(a, COL_VIA[0], 1.0))[1]
            t = (yb - y0) / (y1 - y0)
            if t > COL_VIA[1] + 1.0:
                yield [self.P(a, *COL_VIA), self.P(a, COL_VIA[0], t), self.P(b, COL_VIA[0], yb), self.P(b, *COL_VIA)]
        for ya in COL_YS:
            yield self.col_path(a, b, ya)
        between = [k for k in self.keys if a["prow"] < k["prow"] < b["prow"]]
        if between:                                             # through the cell of a key in the row(s) between
            c = ((a["x"] + b["x"]) / 2, (a["y"] + b["y"]) / 2)
            m = min(between, key=lambda k: math.hypot(k["x"] - c[0], k["y"] - c[1]))
            for xm in COL_MID:
                for ya in COL_YS:
                    for ym in COL_YS:
                        p1 = self.P(a, COL_VIA[0], ya)
                        p3 = self.P(m, xm, ym)
                        yield [self.P(a, *COL_VIA), p1, self.P(m, xm, loc(m, p1)[1]), p3,
                               self.P(b, COL_VIA[0], loc(b, p3)[1]), self.P(b, *COL_VIA)]

    def columns(self):
        later = []
        for ks in self.rows("col").values():
            ks = sorted(ks, key=lambda k: k["row"])
            for a, b in zip(ks, ks[1:]):
                _, net = self.pad(a, "SW", "1")
                for ya in COL_YS:
                    pts = self.col_path(a, b, ya)
                    if self.clear(pts, 0.5):
                        break
                if math.hypot(pts[2][0] - pts[1][0], pts[2][1] - pts[1][1]) < 1.25 * PITCH and self.front_ok(net, pts):
                    self.track(net, pts, W_SIG, F)
                else:                                           # a long run sideways, or something in the way
                    later.append((a, b, net))
        for a, b, net in later:                                 # after the plain ones, so that these see them
            stops = []
            for n, pts in enumerate(self.col_options(a, b)):
                if self.front_ok(net, pts):
                    self.track(net, pts, W_SIG, F)
                    print(f"column {net.GetNetname()} {a['id']} -> {b['id']}: option {n}")
                    break
                stops.append(self.why)
            else:
                print(f"WARNING column {net.GetNetname()} {a['id']} -> {b['id']}: no clear path, left open; blocked at {' '.join(stops)}")

    def leds(self):
        leds = sorted((k for k in self.keys if k.get("led") is not None), key=lambda k: k["led"])
        prow = self.rows("prow")
        for a, b in zip(leds, leds[1:]):
            (ox, oy), net = self.pad(a, "LED", "4")
            (ix, iy), _ = self.pad(b, "LED", "2")
            out = [(ox, oy), (ox + 0.85, oy), (ox + 1.1, DIODE_CH)]
            into = [(-5.6, CAP_CH), (ix - 1.6, iy), (ix, iy)]
            if a["prow"] == b["prow"] and self.step(a, b):
                (ta, tb) = STEP["data"]
                pts = [self.P(a, *p) for p in out + [(ta[0], DIODE_CH), ta]] + [self.P(b, *p) for p in [tb, (tb[0], CAP_CH)] + into]
            elif a["prow"] == b["prow"]:
                pts = [self.P(a, *p) for p in out + [(7.7, DIODE_CH)]] + [self.P(b, *p) for p in [(-8.0, CAP_CH)] + into]
            else:                                               # end of a row: back west along the return line
                ks = prow[a["prow"]]
                ya = RET_DIP if self.dipped(a) else RET_Y
                pts = [self.P(a, *p) for p in out + [(8.3, DIODE_CH), (8.9, DIODE_CH + 0.6), (8.9, ya)]]
                for j, k in reversed(list(enumerate(ks))):
                    ln = [p for p in reversed(self.lane(k, RET_Y, RET_DIP, 0.7)) if k is not a or p[0] < 8.9]
                    if j and self.step(ks[j - 1], k):           # north in the gap west of the tall key
                        ln = ln[:-1] + [(STEP["ret"][1][0], RET_Y), STEP["ret"][1]]
                    if j < len(ks) - 1 and self.step(k, ks[j + 1]):
                        ln = [(STEP["ret"][0], RET_Y)] + [p for p in ln if p[0] < STEP["ret"][0]]
                    self.join(pts, [self.P(k, *p) for p in ln])
                pts.append(self.P(ks[0], -ks[0]["w"] * PITCH / 2 - 0.5, RET_Y))
                xw = -b["w"] * PITCH / 2 - 0.5
                sb = rot(pts[-1][0] - b["x"], pts[-1][1] - b["y"], -b["rot"])
                if sb[0] > xw + 0.3:                            # the next row starts further west: along the row gap first,
                    pts.append(self.P(b, xw, sb[1]))            # not across that key's corner
                pts += [self.P(b, *p) for p in [(xw, CAP_CH - 1.4), (xw + 1.4, CAP_CH)] + into]
            self.track(net, pts, W_SIG)
        tp = next((f for f in self.b.GetFootprints() if f.GetReference().startswith("TP")
                   and f.Pads()[0].GetNetname().endswith("LED_DOUT")), None)
        if tp:                                                  # test pad behind the last LED
            a = leds[-1]
            (ox, oy), net = self.pad(a, "LED", "4")
            tx, ty = self.local(a, tp.Pads()[0])
            self.track(net, [self.P(a, *p) for p in [(ox, oy), (ox + 0.85, oy), (ox + 1.1, DIODE_CH), (8.3, DIODE_CH),
                                                     (tx, ty)]], W_SIG)
        # +5V_LED: along each row, then the bus along the west edge
        taps = []
        for ks in prow.values():
            ks = [k for k in ks if "LED" in self.fp[k["id"]]]
            for a, b in zip(ks, ks[1:]):
                (ex, ey), net = self.pad(a, "CL", "1")
                vx, vy = IN_5V
                if self.step(a, b):
                    (ta, tb) = STEP["v5"]
                    mid = [self.P(a, ta[0], DIODE_5V), self.P(a, *ta), self.P(b, *tb), self.P(b, tb[0], vy)]
                else:
                    mid = [self.P(a, 7.7, DIODE_5V), self.P(b, vx - 1.5, vy)]
                self.track(net, [self.P(a, ex, ey), self.P(a, ex + 0.5, DIODE_5V)] + mid + [self.P(b, vx, vy)], W_5V)
            _, net = self.pad(ks[0], "CL", "1")
            vx, vy = IN_5V
            taps.append((self.P(ks[0], vx, vy), net, ks[0]))
        wn, wd = self.lines["outer" if self.inner > 0 else "inner"]
        straight = abs(wn[1]) < 1e-9
        if straight:                                            # the drawn edge (with its line width), as `left` was routed
            wd = -pcbnew.ToMM(self.b.GetBoardEdgesBoundingBox().GetLeft())
        bus = (wn, wd - BUS_X)
        ends = []
        for p, net, k in taps:                                  # straight west; along the key's own row where the edge is slanted
            if straight:
                e = (-bus[1], p[1])
            else:
                u = rot(-1, 0, k["rot"])
                lam = (bus[1] - wn[0] * p[0] - wn[1] * p[1]) / (wn[0] * u[0] + wn[1] * u[1])
                e = (p[0] + u[0] * lam, p[1] + u[1] * lam)
            ends.append(e)
            self.track(net, [p, e], W_5V)
        net = taps[0][1]
        # feed: rail switch output and bulk capacitor -> along the feed lane of the strip -> down the bus
        at, st, ft = self.at, self.st, self.feed_t
        sx = lambda q: self.inner * rot(pcbnew.ToMM(q.x) - self.origin[0], pcbnew.ToMM(q.y) - self.origin[1], -self.phi)[0]
        sgn = lambda v: 1 if v >= 0 else -1
        nr, dr = self.lines["rear"]
        top = meet(bus, (nr, dr - REAR + ft))
        self.track(net, [top, max(ends, key=lambda e: e[1])], W_BUS)
        sw = next(f for f in self.b.GetFootprints() if "TPS22918" in f.GetValue())
        outs = sorted((st(p) for p in sw.Pads() if p.GetNetname() == net.GetNetname()), key=lambda q: q[1])
        bulk = max((p for f in self.b.GetFootprints() if f.GetReference()[0] == "C" and not f.GetReference().startswith("CL")
                    for p in f.Pads() if p.GetNetname() == net.GetNetname()), key=lambda p: p.GetBoundingBox().GetHeight())
        sc, tc = st(bulk)
        s6, t6 = outs[0]
        sd = s6 + 2.4 * sgn(s6 - sx(sw.GetPosition()))          # the output pin's column, clear of the package
        small = []                                              # the rail's small capacitor(s): up to the lane, 1.4 mm beside the pad column
        for f in self.b.GetFootprints():
            for p in f.Pads():
                if f.GetReference()[0] == "C" and not f.GetReference().startswith("CL") and p.GetNetname() == net.GetNetname() \
                        and p.GetPosition() != bulk.GetPosition():
                    s2, t2 = st(p)
                    small.append((s2, t2, s2 + 1.4 * sgn(s2 - sx(f.GetPosition()))))
        s0 = self.inner * rot(top[0] - self.origin[0], top[1] - self.origin[1], -self.phi)[0]
        stops = {sc, sd}
        stops |= {sr for _, _, sr in small if not min(stops | {s0}) <= sr <= max(stops | {s0})}
        self.track(net, [top] + [at(v, ft) for v in sorted(stops, key=lambda v: abs(v - s0))], W_BUS)
        self.track(net, [at(sd, ft), at(sd, t6), at(s6, t6)], W_BUS)
        self.track(net, [at(s6, t6), at(*outs[-1])], 0.5)
        self.track(net, [at(sc, ft), at(sc, tc)], W_BUS)
        for s2, t2, sr in small:
            self.track(net, [at(s2, t2), at(sr, t2), at(sr, ft)], 0.5)

    def at(self, s, t):
        """Strip frame (as tools/pcb_keys.py place_strip): s from the outer board edge, t rearwards from the cap line."""
        dx, dy = rot(self.inner * s, -t, self.phi)
        return self.origin[0] + dx, self.origin[1] + dy

    def st(self, pad):
        p = pad.GetPosition()
        v = rot(pcbnew.ToMM(p.x) - self.origin[0], pcbnew.ToMM(p.y) - self.origin[1], -self.phi)
        return self.inner * v[0], -v[1]

    def row_risers(self):
        """The bottom row to the expander on the front side (the strip router does not find this one): from a via at
        the east end of its trunk to the inner edge, north along it, west between the F-row caps and the bay header,
        to a via in front of the expander pin. The other rows are near enough for the strip router; a scripted
        riser for each of them (tried: lanes behind the bay header) fences the expander in on the front side.
        Along the east edge: the split edge on `left` and `numpad`, the outer edge on `right`."""
        n, d = self.lines["inner" if self.inner > 0 else "outer"]
        nr, dr = self.lines["rear"]
        rows = self.rows("row")
        for i, r in enumerate(sorted(rows, reverse=True)[:1]):
            k = rows[r][-1]
            (cx, _), net = self.pad(k, "D", "1")
            off, lane = 0.7, 0.6
            v0 = self.P(k, cx, ROW_DIP if self.dipped(k) else ROW_Y)
            lead = [v0] + ([self.P(k, 14.6, ROW_DIP), self.P(k, 15.6, ROW_Y)] if self.dipped(k) else [])   # back up, clear of the front holes
            u, q = rot(1, 0, k["rot"]), lead[-1]
            lam = (d - off - n[0] * q[0] - n[1] * q[1]) / (n[0] * u[0] + n[1] * u[1])
            p1 = (q[0] + u[0] * lam, q[1] + u[1] * lam)
            p2 = meet((n, d - off), (nr, dr - REAR + lane))
            pad = next(p for f in self.b.GetFootprints() if "MCP23S17" in f.GetValue() for p in f.Pads()
                       if p.GetNetname() == net.GetNetname())
            sp, tp = self.st(pad)
            p4 = self.at(sp, tp - 2.2)
            if not self.front_ok(net, lead + [p1, p2, self.at(sp, lane), p4]):
                print(f"WARNING riser {net.GetNetname()}: not clear on the front side, check DRC")
            self.track(net, lead + [p1, p2, self.at(sp, lane), p4], W_SIG, F)
            self.via(net, v0)
            self.via(net, p4)
            self.track(net, [p4, self.at(sp, tp)], W_SIG)

    def pullups(self):
        """Where the pull-ups have their +3V3 pads at the rear (`right`): the +3V3 link along the row, and a fan from
        each signal pad to its pin in the expander's rear pin row. The strip router left these open, run after run."""
        pins = {p.GetNetname(): p for f in self.b.GetFootprints() if "MCP23S17" in f.GetValue() for p in f.Pads()}
        rail = []
        for f in self.b.GetFootprints():
            pads = {p.GetNetname(): p for p in f.Pads()}
            if f.GetValue() != "10k" or "/+3V3" not in pads or len(pads) != 2:
                continue
            v, (name, sig) = pads.pop("/+3V3"), next(iter(pads.items()))
            (s1, t1), (s2, t2) = self.st(v), self.st(sig)
            if t1 < t2 + 0.5:
                continue
            rail.append((s1, t1, v.GetNet()))
            pin = pins.get(name)
            if pin is None:
                continue
            (sp, tp), (_, tc) = self.st(pin), self.st(pin.GetParentFootprint())
            if tp > tc:
                self.track(sig.GetNet(), [self.at(s2, t2), self.at(sp, tp + 1.5), self.at(sp, tp)], W_SIG)
        rail.sort()
        for (sa, ta, net), (sb, tb, _) in zip(rail, rail[1:]):
            self.track(net, [self.at(sa, ta), self.at(sb, tb)], 0.3)

    def decouple(self):
        """Expander VDD and VSS pins straight to the 100 n in front of them (tools/pcb_keys.py place_strip)."""
        xy = lambda p: (pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y))
        caps = [p for f in self.b.GetFootprints() if f.GetValue() == "100n" and not f.GetReference().startswith("CL")
                for p in f.Pads()]
        for f in self.b.GetFootprints():
            if "MCP23S17" not in f.GetValue():
                continue
            for num in ("9", "10"):
                pin = f.FindPadByNumber(num)
                near = min((c for c in caps if c.GetNetname() == pin.GetNetname()), key=lambda c: math.dist(xy(c), xy(pin)))
                if math.dist(xy(near), xy(pin)) > 5.0:
                    print(f"WARNING {f.GetReference()} pin {num}: no 100 n within 5 mm")
                    continue
                self.track(pin.GetNet(), [xy(pin), xy(near)], W_GND)

    def field(self):
        for k in self.keys:
            self.cell(k)
        self.row_trunks()
        self.columns()
        self.leds()
        self.row_risers()
        self.pullups()
        self.decouple()


def freeroute(b, name, passes):
    work = ROOT / "build" / "route" / name
    work.mkdir(parents=True, exist_ok=True)
    dsn, ses = work / f"{name}.dsn", work / f"{name}.ses"
    if not pcbnew.ExportSpecctraDSN(b, str(dsn)):
        sys.exit("DSN export failed")
    # GND in the key field is the pours' job (a via in every cell): the router only ties the strip's GND pads together,
    # otherwise it wires every key's ground through the field
    text = dsn.read_text()
    i = text.index("(net GND")
    depth, j = 0, i
    while True:
        depth += {"(": 1, ")": -1}.get(text[j], 0)
        j += 1
        if depth == 0:
            break
    dsn.write_text(text[:i] + re.sub(r"\b(?:CL|LED)\d+-\d+\s*", "", text[i:j]) + text[j:])
    ses.unlink(missing_ok=True)
    with open(work / "freerouting.log", "w") as log:
        subprocess.run(["java", "-jar", str(JAR), "-de", str(dsn), "-do", str(ses), "-mp", passes,
                        "--gui.enabled=false"], stdout=log, stderr=subprocess.STDOUT, timeout=3000)
    if not ses.exists():
        sys.exit(f"Freerouting wrote no session file; see build/route/{name}/freerouting.log")
    if not pcbnew.ImportSpecctraSES(b, str(ses)):
        sys.exit("SES import failed")


def led_windows(b):
    """Rule area (no tracks, no vias) over every LED window plus 0.25 mm: a router does not see the cut-outs."""
    hx, hy = 3.4 / 2 + 0.25, 3.0 / 2 + 0.25
    for fp in b.GetFootprints():
        if not fp.GetReference().startswith("LED"):
            continue
        a = -math.radians(fp.GetOrientationDegrees())
        c = fp.GetPosition()
        z = pcbnew.ZONE(b)
        z.SetIsRuleArea(True)
        z.SetLayerSet(pcbnew.LSET.AllCuMask())
        z.SetZoneName(f"WIN_{fp.GetReference()}")
        z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowPads(False)
        z.SetDoNotAllowZoneFills(False); z.SetDoNotAllowFootprints(False)
        o = z.Outline()
        o.NewOutline()
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            x, y = sx * hx, sy * hy
            o.Append(int(c.x + mm(x * math.cos(a) - y * math.sin(a))), int(c.y + mm(x * math.sin(a) + y * math.cos(a))))
        b.Add(z)


def stitch(b):
    """A GND via beside every GND pad of the strip's SMD parts, so the back pour's pieces there reach the front pour,
    and beside every key LED's 100 n (at CAP_VIA where that spot is free, else the nearest free spot)."""
    gnd = b.FindNet("GND")
    segs = [(t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y, t.GetWidth() // 2, t.GetNetname())
            for t in b.GetTracks() if t.Type() != pcbnew.PCB_VIA_T]
    dots = [(t.GetPosition().x, t.GetPosition().y, mm(0.4), t.GetNetname()) for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
    boxes = []
    for f in b.GetFootprints():
        for p in f.Pads():
            bb = p.GetBoundingBox()
            boxes.append((bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom(), p.GetNetname() if p.GetNetCode() else "-"))

    def free(x, y, r, own):
        for x1, y1, x2, y2, w, n in segs:
            vx, vy = x2 - x1, y2 - y1
            t = max(0.0, min(1.0, ((x - x1) * vx + (y - y1) * vy) / (vx * vx + vy * vy or 1)))
            if n != "GND" and math.hypot(x1 + t * vx - x, y1 + t * vy - y) < r + w + mm(0.25):
                return False
        for vx, vy, vr, n in dots:
            if math.hypot(vx - x, vy - y) < r + vr + mm(0.3):
                return False
        for l, tp, rt, bt, n in boxes:
            if (l, tp, rt, bt) != own and (n != "GND" or r > mm(0.25)) and l - r - mm(0.3) < x < rt + r + mm(0.3) and tp - r - mm(0.3) < y < bt + r + mm(0.3):
                return False
        return True

    added = 0
    for f in b.GetFootprints():
        ref = f.GetReference()
        if ref.rstrip("0123456789") in ("LED", "SW", "D", "ST", "H", "TP") or not f.IsFlipped():
            continue
        for p in f.Pads():
            if p.GetNetname() != "GND":
                continue
            bb = p.GetBoundingBox()
            own = (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom())
            c = p.GetPosition()
            done = False
            first = []
            if ref.startswith("CL"):                            # the key's "north" is from the +5V pad to the GND pad
                q = f.FindPadByNumber("1").GetPosition()
                n = ((c.x - q.x) / math.hypot(c.x - q.x, c.y - q.y), (c.y - q.y) / math.hypot(c.x - q.x, c.y - q.y))
                first = [(c.x + mm(CAP_VIA[1]) * n[0] - mm(CAP_VIA[0]) * n[1], c.y + mm(CAP_VIA[1]) * n[1] + mm(CAP_VIA[0]) * n[0])]
            for dist in (0, 1.4, 1.7, 2.0, 2.4):
                for ang in range(0, 360, 30):
                    if dist == 0 and (ang or not first):
                        continue
                    x = c.x + mm(dist * math.cos(math.radians(ang))) if dist else first[0][0]
                    y = c.y + mm(dist * math.sin(math.radians(ang))) if dist else first[0][1]
                    if free(x, y, mm(0.3), own) and all(free(c.x + (x - c.x) * q, c.y + (y - c.y) * q, mm(0.2), own) for q in (0.25, 0.5, 0.75)):
                        t = pcbnew.PCB_TRACK(b)
                        t.SetStart(c); t.SetEnd(pcbnew.VECTOR2I(int(x), int(y)))
                        t.SetWidth(mm(W_GND)); t.SetLayer(B); t.SetNet(gnd)
                        b.Add(t)
                        v = pcbnew.PCB_VIA(b)
                        v.SetPosition(pcbnew.VECTOR2I(int(x), int(y)))
                        v.SetWidth(pcbnew.F_Cu, mm(0.6)); v.SetDrill(mm(0.3)); v.SetNet(gnd)
                        b.Add(v)
                        dots.append((int(x), int(y), mm(0.4), "GND"))
                        added += 1
                        done = True
                        break
                if done:
                    break
            if not done:
                print(f"WARNING no room for a GND via at {ref} pad {p.GetNumber()}")
    print(f"GND stitching vias in the strip: {added}")


def gnd_pours(b):
    box = b.GetBoardEdgesBoundingBox()
    for layer in (F, B):
        z = pcbnew.ZONE(b)
        z.SetLayer(layer)
        z.SetNet(b.FindNet("GND"))
        z.SetZoneName(f"GND_{b.GetLayerName(layer)}")
        o = z.Outline()
        o.NewOutline()
        for x, y in ((box.GetLeft(), box.GetTop()), (box.GetRight(), box.GetTop()),
                     (box.GetRight(), box.GetBottom()), (box.GetLeft(), box.GetBottom())):
            o.Append(x, y)
        z.SetLocalClearance(mm(ZONE_CLEARANCE)); z.SetMinThickness(mm(ZONE_MIN))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(mm(0.25)); z.SetThermalReliefSpokeWidth(mm(0.4))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        b.Add(z)


def main():
    import json
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    name = args[0]
    pcb = ROOT / "hardware" / name / f"{name}.kicad_pcb"
    b = pcbnew.LoadBoard(str(pcb))
    if len(b.GetTracks()):
        sys.exit(f"{pcb.name} already has tracks; re-run tools/pcb_keys.py {name} --force first")
    keys, inner_sign, (lines, _, origin, phi, _) = frame(name)
    r = Router(b, keys, inner_sign, origin, phi, lines, FEED_LANE.get(name, FEED_NEAR))
    r.field()
    print(f"{name}: key field, {r.count} locked segments and vias")
    led_windows(b)
    if "--strip" in sys.argv:
        freeroute(b, name, next((sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--passes"), "30"))
    # vias the strip router left without a track on the other side
    ends = {}
    for t in b.GetTracks():
        if t.Type() != pcbnew.PCB_VIA_T:
            for p in (t.GetStart(), t.GetEnd()):
                ends.setdefault((p.x, p.y), set()).add(t.GetLayer())
    grave = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T and not t.IsLocked() and t.GetNetname() != "GND"
             and len(ends.get((t.GetPosition().x, t.GetPosition().y), ())) < 2]
    # the switch-to-diode nets are complete from the field pattern: what the strip router adds there is a stub
    grave += [t for t in b.GetTracks() if not t.IsLocked() and re.search(r"/N_R\d+C\d+$", t.GetNetname())]
    for t in grave:
        b.Remove(t)
    for t in b.GetTracks():                         # the strip router now and then leaves a short piece thinner than the
        if t.Type() != pcbnew.PCB_VIA_T and not t.IsLocked() and t.GetWidth() < mm(0.15):      # 0.15 mm the board allows
            t.SetWidth(mm(0.15))
    if "--no-pours" not in sys.argv:
        stitch(b)
        gnd_pours(b)
    moved, stuck = silk_keys.tidy(b, lines)
    print(f"{name}: silkscreen, {len(moved)} references moved" + (f"; NO ROOM for {' '.join(stuck)}" if stuck else ""))
    fill = [CLI, "pcb", "drc", "--refill-zones", "--save-board", "-o", str(ROOT / "build" / "kicad-check" / f"{name}-fill.rpt"), str(pcb)]
    pcbnew.SaveBoard(str(pcb), b)
    subprocess.run(fill, capture_output=True)
    if "--strip" in sys.argv:
        # What the strip router left open or drew too close (M2 session 9: with the 100 n in front of the expander it
        # leaves one to five row links open on most runs): the hub boards' finishing pass, tools/route_hub.py finish()
        import route_hub as rh
        rh.T_CLR = 0.2                              # the key boards' clearance
        for _ in range(5):
            dropped = rh.drop_violators(b, pcb, name)
            if dropped:
                pcbnew.SaveBoard(str(pcb), b)
                subprocess.run(fill, capture_output=True)
                b = pcbnew.LoadBoard(str(pcb))      # a board that had tracks removed gives no track list any more
            closed = rh.finish(b, pcb, name)
            if closed:
                pcbnew.SaveBoard(str(pcb), b)
                subprocess.run(fill, capture_output=True)
                b = pcbnew.LoadBoard(str(pcb))
            if not dropped and not closed:
                break
    print(f"{name}: {len(b.GetTracks())} segments and vias in all")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
