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
   - LED data: DOUT (east) -> under the diode (between its pads) -> under the next key's 100 n -> DIN (west);
     at the end of a row it returns west along RET_Y and enters the next row's first key;
   - +5V_LED, 0.8 mm: 100 n -> south of the LED window -> LED -> under the diode -> next key's 100 n;
     the rows are joined by a 1 mm bus along the outer board edge;
   - GND: 100 n -> via -> LED; the ground itself is the pour on both sides.
   Stabilised keys: row trunk and return line dip south of the stabiliser's wire holes.
2. `--strip`: the rear strip (expander, pull-ups, rail switch, headers) and its links to the field are left to
   Freerouting with the field locked (work files in build/route/<name>/).
3. GND pours on both sides, refilled and saved through kicad-cli.
"""
import math
import os
import re
import subprocess
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
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
CAP_CH = 4.2                         # the lane between the 100 n's pads
BUS_X = 1.8                          # +5V bus: mm inside the outer board edge
FEED_T = REAR - 2.5                  # +5V feed from the rail switch: along the rear edge of the strip

mm = pcbnew.FromMM
F, B = pcbnew.F_Cu, pcbnew.B_Cu


class Router:
    def __init__(self, board, keys, inner_sign, origin, phi, lines):
        self.b, self.inner, self.origin, self.phi, self.lines = board, inner_sign, origin, phi, lines
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

    def lane(self, k, y, dip, grow=0.0):
        """West-to-east line through a key's cell at y, dipping to `dip` under a stabiliser."""
        hw = k["w"] * PITCH / 2
        if self.stab(k):
            a = 14.6 + grow
            return [(-hw, y), (-a - 1.0, y), (-a, dip), (a, dip), (a + 1.0, y), (hw, y)]
        return [(-hw, y), (hw, y)]

    def clear(self, pts, gap):
        """True if the polyline keeps `gap` from every stabiliser hole."""
        for k in self.keys:
            if not k["stab"]:
                continue
            turn = 90 if k["h"] > k["w"] else 0
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
        self.track(row, [P(cx, cy), P(cx, ROW_DIP if self.stab(k) else ROW_Y)], W_SIG)
        (px, py), col = self.pad(k, "SW", "1")
        self.track(col, [P(px, py), P(*COL_VIA)], W_SIG)
        self.via(col, P(*COL_VIA))
        if "LED" not in self.fp[k["id"]]:
            return
        (gx, gy), gnd = self.pad(k, "CL", "2")
        (lx, ly), _ = self.pad(k, "LED", "1")
        self.track(gnd, [P(gx, gy), P(*GND_VIA), P(lx - 1.2, ly), P(lx, ly)], W_GND)
        self.via(gnd, P(*GND_VIA))
        (vx, vy), v5 = self.pad(k, "CL", "1")
        (ex, ey), _ = self.pad(k, "LED", "3")
        self.track(v5, [P(vx, vy), P(vx, WRAP_Y), P(ex + 1.7, WRAP_Y), P(ex + 1.7, ey), P(ex, ey)], W_5V)

    def row_trunks(self):
        for ks in self.rows("row").values():
            pts, net = [], None
            for i, k in enumerate(ks):
                (cx, _), net = self.pad(k, "D", "1")
                yk = ROW_DIP if self.stab(k) else ROW_Y
                ln = self.lane(k, ROW_Y, ROW_DIP)
                ln = [p for p in ln if p[0] < cx] + [(cx, yk)] + [p for p in ln if p[0] > cx]
                if i == 0:
                    ln = [p for p in ln if p[0] >= cx]
                if i == len(ks) - 1:
                    ln = [p for p in ln if p[0] <= cx]
                pts += [self.P(k, *p) for p in ln]
            self.track(net, pts, W_SIG)

    def columns(self):
        for ks in self.rows("col").values():
            ks = sorted(ks, key=lambda k: k["row"])
            for a, b in zip(ks, ks[1:]):
                _, net = self.pad(a, "SW", "1")
                for ya in COL_YS:
                    mid = self.P(a, COL_VIA[0], ya)
                    ml = rot(mid[0] - b["x"], mid[1] - b["y"], -b["rot"])    # that point in the lower key's frame
                    pts = [self.P(a, *COL_VIA), mid, self.P(b, COL_VIA[0], ml[1]), self.P(b, *COL_VIA)]
                    if self.clear(pts, 0.5):
                        break
                else:
                    print(f"WARNING column {net.GetNetname()} {a['id']} -> {b['id']}: no clear step, check DRC")
                self.track(net, pts, W_SIG, F)

    def leds(self):
        leds = sorted((k for k in self.keys if k.get("led") is not None), key=lambda k: k["led"])
        prow = self.rows("prow")
        for a, b in zip(leds, leds[1:]):
            (ox, oy), net = self.pad(a, "LED", "4")
            (ix, iy), _ = self.pad(b, "LED", "2")
            out = [(ox, oy), (ox + 1.9, oy), (ox + 2.15, DIODE_CH)]
            into = [(-5.6, CAP_CH), (ix - 1.6, iy), (ix, iy)]
            if a["prow"] == b["prow"]:
                pts = [self.P(a, *p) for p in out + [(7.7, DIODE_CH)]] + [self.P(b, *p) for p in [(-8.0, CAP_CH)] + into]
            else:                                               # end of a row: back west along the return line
                ks = prow[a["prow"]]
                ya = RET_DIP if self.stab(a) else RET_Y
                pts = [self.P(a, *p) for p in out + [(8.3, DIODE_CH), (8.9, DIODE_CH + 0.6), (8.9, ya)]]
                for k in reversed(ks):
                    ln = self.lane(k, RET_Y, RET_DIP, 0.7)
                    pts += [self.P(k, *p) for p in reversed(ln) if k is not a or p[0] < 8.9]
                pts.append(self.P(ks[0], -ks[0]["w"] * PITCH / 2 - 0.5, RET_Y))
                xw = -b["w"] * PITCH / 2 - 0.5
                pts += [self.P(b, *p) for p in [(xw, CAP_CH - 1.4), (xw + 1.4, CAP_CH)] + into]
            self.track(net, pts, W_SIG)
        tp = next((f for f in self.b.GetFootprints() if f.GetReference().startswith("TP")
                   and f.Pads()[0].GetNetname().endswith("LED_DOUT")), None)
        if tp:                                                  # test pad behind the last LED
            a = leds[-1]
            (ox, oy), net = self.pad(a, "LED", "4")
            tx, ty = self.local(a, tp.Pads()[0])
            self.track(net, [self.P(a, *p) for p in [(ox, oy), (ox + 1.9, oy), (ox + 2.15, DIODE_CH), (8.3, DIODE_CH),
                                                     (tx, ty)]], W_SIG)
        # +5V_LED: along each row, then the bus along the outer edge
        taps = []
        for ks in prow.values():
            ks = [k for k in ks if "LED" in self.fp[k["id"]]]
            for a, b in zip(ks, ks[1:]):
                (ex, ey), net = self.pad(a, "LED", "3")
                (vx, vy), _ = self.pad(b, "CL", "1")
                self.track(net, [self.P(a, ex + 1.7, ey), self.P(a, ex + 2.45, DIODE_5V), self.P(a, 7.7, DIODE_5V),
                                 self.P(b, vx - 1.5, vy), self.P(b, vx, vy)], W_5V)
            (vx, vy), net = self.pad(ks[0], "CL", "1")
            taps.append((self.P(ks[0], vx, vy), net))
        box = self.b.GetBoardEdgesBoundingBox()
        edge = pcbnew.ToMM(box.GetLeft() if self.inner > 0 else box.GetRight())
        bus = edge + self.inner * BUS_X
        for p, net in taps:
            self.track(net, [p, (bus, p[1])], W_5V)
        net = taps[0][1]
        # feed: rail switch output and bulk capacitor -> along the rear edge of the strip -> down the bus
        at = lambda s, t: (self.origin[0] + rot(self.inner * s, -t, self.phi)[0], self.origin[1] + rot(self.inner * s, -t, self.phi)[1])
        def st(pad):
            p = pad.GetPosition()
            v = rot(pcbnew.ToMM(p.x) - self.origin[0], pcbnew.ToMM(p.y) - self.origin[1], -self.phi)
            return self.inner * v[0], -v[1]
        x0, x1 = at(0, FEED_T)[0], at(1, FEED_T)[0]
        top = at((bus - x0) / (x1 - x0), FEED_T)
        self.track(net, [top, (bus, max(p[1] for p, _ in taps))], W_BUS)
        sw = next(f for f in self.b.GetFootprints() if "TPS22918" in f.GetValue())
        outs = sorted((st(p) for p in sw.Pads() if p.GetNetname() == net.GetNetname()), key=lambda q: q[1])
        bulk = max((p for f in self.b.GetFootprints() if f.GetReference()[0] == "C" and not f.GetReference().startswith("CL")
                    for p in f.Pads() if p.GetNetname() == net.GetNetname()), key=lambda p: p.GetBoundingBox().GetHeight())
        sc, tc = st(bulk)
        s6, t6 = outs[0]
        self.track(net, [top, at(sc, FEED_T), at(s6 + 2.4, FEED_T), at(s6 + 2.4, t6), at(s6, t6)], W_BUS)
        self.track(net, [at(s6, t6), at(*outs[-1])], 0.5)
        self.track(net, [at(sc, FEED_T), at(sc, tc)], W_BUS)
        for f in self.b.GetFootprints():                        # the rail's small capacitor(s): up to the feed, 1.4 mm west of the pad column
            for p in f.Pads():
                if f.GetReference()[0] == "C" and not f.GetReference().startswith("CL") and p.GetNetname() == net.GetNetname() \
                        and p.GetPosition() != bulk.GetPosition():
                    s2, t2 = st(p)
                    self.track(net, [at(s2, t2), at(s2 - 1.4, t2), at(s2 - 1.4, FEED_T)], 0.5)

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
        Written for `left` (inner edge east)."""
        n, d = self.lines["inner"]
        nr, dr = self.lines["rear"]
        rows = self.rows("row")
        for i, r in enumerate(sorted(rows, reverse=True)[:1]):
            k = rows[r][-1]
            (cx, _), net = self.pad(k, "D", "1")
            off, lane = 0.7, 0.6
            v0 = self.P(k, cx, ROW_DIP if self.stab(k) else ROW_Y)
            lead = [v0] + ([self.P(k, 14.6, ROW_DIP), self.P(k, 15.6, ROW_Y)] if self.stab(k) else [])   # back up, clear of the front holes
            u, q = rot(1, 0, k["rot"]), lead[-1]
            lam = (d - off - n[0] * q[0] - n[1] * q[1]) / (n[0] * u[0] + n[1] * u[1])
            p1 = (q[0] + u[0] * lam, q[1] + u[1] * lam)
            p2 = meet((n, d - off), (nr, dr - REAR + lane))
            pad = next(p for f in self.b.GetFootprints() if "MCP23S17" in f.GetValue() for p in f.Pads()
                       if p.GetNetname() == net.GetNetname())
            sp, tp = self.st(pad)
            p4 = self.at(sp, tp - 2.2)
            self.track(net, lead + [p1, p2, self.at(sp, lane), p4], W_SIG, F)
            self.via(net, v0)
            self.via(net, p4)
            self.track(net, [p4, self.at(sp, tp)], W_SIG)

    def field(self):
        for k in self.keys:
            self.cell(k)
        self.row_trunks()
        self.columns()
        self.leds()
        self.row_risers()


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
    """A GND via beside every GND pad of the strip's SMD parts, so the back pour's pieces there reach the front pour."""
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
        if ref.rstrip("0123456789") in ("CL", "LED", "SW", "D", "ST", "H", "TP") or not f.IsFlipped():
            continue
        for p in f.Pads():
            if p.GetNetname() != "GND":
                continue
            bb = p.GetBoundingBox()
            own = (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom())
            c = p.GetPosition()
            done = False
            for dist in (1.4, 1.7, 2.0, 2.4):
                for ang in range(0, 360, 30):
                    x = c.x + mm(dist * math.cos(math.radians(ang)))
                    y = c.y + mm(dist * math.sin(math.radians(ang)))
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
    r = Router(b, keys, inner_sign, origin, phi, lines)
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
    for t in grave:
        b.Remove(t)
    if "--no-pours" not in sys.argv:
        stitch(b)
        gnd_pours(b)
    pcbnew.SaveBoard(str(pcb), b)
    print(f"{name}: {len(b.GetTracks())} segments and vias in all")
    sys.stdout.flush()
    subprocess.run([CLI, "pcb", "drc", "--refill-zones", "--save-board", "-o", str(ROOT / "build" / "kicad-check" / f"{name}-fill.rpt"),
                    str(pcb)], capture_output=True)
    os._exit(0)


if __name__ == "__main__":
    main()
