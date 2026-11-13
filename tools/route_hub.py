#!/usr/bin/env python3
"""Route the hub boards (M2 step 2): hub-core, battery, hub-conn, chain-cap.

Run with KiCad's Python (KiCad closed), on a board fresh from tools/pcb_hub.py --force:
    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 tools/route_hub.py <board> [--passes 30]
One command that repeats until the check is clean: tools/route_hub.sh <board> [tries].

hub-core and battery (2 layers): everything by Freerouting, then GND pours on both sides.
chain-cap (2 layers): sixteen scripted lines, no autorouter (cap_copper).

hub-conn (4 layers; user, 2026-11-13): F parts and signals, In1 an unbroken GND plane, In2 power and signals, B signals.
The heavy copper is drawn here, locked, before the autorouter runs; the autorouter then adds the thin rest
(0.2 mm signals, 0.4 mm for the small branches of supply nets) on F, In2 and B and never on In1 (a power layer
in its input):
- chain seam (target pads on B): every pack line has a pad in the north row and one in the south row, in mirrored
  order, so no two of them can be joined on one layer between the rows. North pads go through a via to In2, south
  across the pad block between the columns, and down to B again; on B all ten ends then sit in one row and the
  pairs nest (PACK1 outermost), joined by five lanes south of the pads: the comb. A lane is closed in by the
  lanes around it, so each leaves through two vias and an In2 trunk to its pack column;
- pack column: entry vias, PACK copper to the ideal-diode FET's sources, VM to the priority FET, VBAT vias down to
  the VBAT bus on In2 (along the columns, then up to the battery switch);
- SYS node on F between the two switches, the bulk capacitors and the converter's input capacitors;
- VBUS_IN: bar at the host-port header, trunk on B under the header to the USB switch;
- converter, as the TPS552892 datasheet layout: VIN and VOUT copper from the strips to the capacitor row, PGND
  between them and out both ends of its strip to vias, SW1 / SW2 through the boot capacitors' pads to the inductor;
- +5V: vias at the output capacitors, a trunk on In2 to the three ports and the 220 uF, vias at each source switch;
- port VBUS: from the switch through vias to an In2 bar and the receptacle's two VBUS through-pins.
Before the autorouter: a GND via beside every SMD GND pad. After it: the In1 plane, GND pours on F, In2 and B, and
a small maze router (finish) for the handful of connections the autorouter leaves open on every run.
[check at the PCB review] AGND is not a separate island: pins 2, 5, 17 and the FSW / FB / COMP / EN parts go to the
In1 plane by their own vias, away from the power loop (the datasheet joins AGND and PGND at the VCC capacitor).
"""
import math
import os
import re
import subprocess
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pcb_hub as ph  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
JAR = Path.home() / "Documents/KiCad/10.0/3rdparty/plugins/app_freerouting_kicad-plugin/jar/freerouting-2.5.0.jar"
CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
mm, MM = pcbnew.FromMM, pcbnew.ToMM
F, I1, I2, B = pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu
ZONE_CLEARANCE, ZONE_MIN = 0.25, 0.2


class Cu:
    """Scripted copper on a placed board. Coordinates in KiCad mm."""

    def __init__(self, b):
        self.b = b
        self.fps = {f.GetReference(): f for f in b.GetFootprints()}
        self.count = 0

    def find(self, prefix, *nets):
        got = [r for r, f in self.fps.items() if r.rstrip("0123456789") == prefix
               and set(nets) <= {p.GetNetname().lstrip("/") for p in f.Pads()}]
        if len(got) != 1:
            sys.exit(f"{prefix} with nets {nets}: {got}")
        return got[0]

    def pad(self, ref, num):
        p = self.fps[ref].FindPadByNumber(num).GetPosition()
        return MM(p.x), MM(p.y)

    def mean(self, ref, *nums):
        pts = [self.pad(ref, n) for n in nums]
        return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)

    def net(self, name):
        n = self.b.FindNet(name) or self.b.FindNet("/" + name)
        if n is None:
            sys.exit(f"no net {name}")
        return n

    def track(self, net, pts, w, layer=F):
        net = self.net(net)
        for p, q in zip(pts, pts[1:]):
            if math.hypot(p[0] - q[0], p[1] - q[1]) < 1e-6:
                continue
            t = pcbnew.PCB_TRACK(self.b)
            t.SetStart(pcbnew.VECTOR2I(mm(p[0]), mm(p[1]))); t.SetEnd(pcbnew.VECTOR2I(mm(q[0]), mm(q[1])))
            t.SetWidth(mm(w)); t.SetLayer(layer); t.SetNet(net); t.SetLocked(True)
            self.b.Add(t)
            self.count += 1

    def via(self, net, x, y, d=0.8, drill=0.4):
        v = pcbnew.PCB_VIA(self.b)
        v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
        v.SetWidth(F, mm(d)); v.SetDrill(mm(drill)); v.SetNet(self.net(net)); v.SetLocked(True)
        self.b.Add(v)
        self.count += 1


# ---- hub-conn: the heavy copper ------------------------------------------------------------------------------------
LANE_Y = {5: 78.4, 4: 79.8, 3: 81.2, 2: 82.6, 1: 84.0}       # comb lanes on B, innermost pair nearest the pads
LANE_W, STUB_W, TRUNK_W = 1.2, 0.9, 1.2


def chain(c):
    """Chain seam target pads: vias, transfers, comb, trunks to the pack columns (see the header)."""
    j = c.find("J", "AUX_5V", "PACK1")
    pads = {p.GetNumber(): (MM(p.GetPosition().x), MM(p.GetPosition().y), p.GetNetname().lstrip("/")) for p in c.fps[j].Pads()}
    ys = sorted({round(v[1], 2) for v in pads.values()})
    if len(ys) != 2:
        sys.exit(f"chain pads: rows {ys}")
    y_n, y_s = ys
    ends = {}                                                   # pack -> x of its two ends in the south row
    for x, y, net in pads.values():
        north = abs(y - y_n) < 0.01
        if net == "GND":
            vy = y - 2.25 if north else y + 2.28
            c.track(net, [(x, y), (x, vy)], 0.5, B)
            c.via(net, x, vy, 0.6, 0.3)
        elif net == "AUX_5V":                                  # thin line: a via each, the autorouter joins them
            vy = y - 2.25 if north else y + 2.33
            c.track(net, [(x, y), (x, vy)], 0.5, B)
            c.via(net, x, vy, 0.6, 0.3)
        else:
            n = int(net[-1])
            if north:
                c.track(net, [(x, y), (x, y - 2.25)], STUB_W, B)
                c.via(net, x, y - 2.25)
                c.track(net, [(x, y - 2.25), (x + 1.27, y - 1.3), (x + 1.27, y_s + 3.43)], STUB_W, I2)
                c.via(net, x + 1.27, y_s + 3.43)
                c.track(net, [(x + 1.27, y_s + 3.43), (x + 1.27, LANE_Y[n])], STUB_W, B)
                ends.setdefault(n, []).append(x + 1.27)
            else:
                c.track(net, [(x, y), (x, LANE_Y[n])], STUB_W, B)
                ends.setdefault(n, []).append(x)
    for n, xs in ends.items():
        c.track(f"PACK{n}", [(min(xs), LANE_Y[n]), (max(xs), LANE_Y[n])], LANE_W, B)
    # exits: two vias on the lane, an In2 trunk along the lane's own y, then south into the column
    entry = {n: (ph.COL_X0 + ph.COL_W * col + ph.ST_ENTRY[0], ph.COL_Y0 + ph.ST_ENTRY[1]) for col, n in enumerate(ph.COL_PACK)}
    exit_x = {1: None, 2: 116.85, 3: 118.15, 4: 124.75, 5: 122.65}
    for n, (ex, ey) in entry.items():
        net, y = f"PACK{n}", LANE_Y[n]
        if n == 1:                                              # outermost lane: straight south on B
            c.track(net, [(ex, y), (ex, ey)], LANE_W, B)
        else:
            x = exit_x[n]
            if not min(ends[n]) < x - 0.55 and x + 0.55 < max(ends[n]):
                sys.exit(f"exit of PACK{n} is off its lane")
            c.via(net, x - 0.55, y); c.via(net, x + 0.55, y)
            path = [(x, y), (ex, y), (ex, ey)] if n != 5 else [(x, y), (138.5, y), (138.5, 84.5), (ex, 84.5), (ex, ey)]
            c.track(net, path, TRUNK_W, I2)                     # PACK5 steps round the mounting hole
        c.via(net, ex - 0.55, ey); c.via(net, ex + 0.55, ey)
    return entry


def stages(c, entry):
    """Pack columns: PACK to the ideal-diode FET, VM to the priority FET, VBAT down to the In2 bus."""
    bus_y = ph.COL_Y0 + ph.ST_VBAT_Y
    last = 0.0
    for col, n in enumerate(ph.COL_PACK):
        x0, pk_, vm = ph.COL_X0 + ph.COL_W * col, f"PACK{n}", f"VM{n}"
        ex, ey = entry[n]
        q = c.find("Q", f"IDG{n}", pk_)
        sx, sy = c.mean(q, "1", "2", "3")
        c.track(pk_, [(sx, ey), (sx, sy)], 2.6)
        tv = c.find("D", pk_, "GND")
        c.track(pk_, [c.pad(tv, "1"), (ex - 0.55, c.pad(tv, "1")[1]), (ex - 0.55, ey)], 1.0)
        d5, d8 = c.pad(q, "5"), c.pad(q, "8")
        vx = x0 + 10.9
        if n < 5:
            c.track(vm, [d5, d8], 1.2)
            q2 = c.find("Q", f"PG{n}", "VBAT")
            px, py = c.mean(q2, "1", "2", "3")
            c.track(vm, [(px, d5[1]), (px, py - 0.4)], 1.5)
            c.track("VBAT", [(vx, c.pad(q2, "5")[1] + 0.3), (vx, bus_y)], 2.0)
        else:
            c.track("VBAT", [d5, d8], 1.2)
            c.track("VBAT", [((d5[0] + d8[0]) / 2, d5[1]), (vx, d5[1] + 2.5), (vx, bus_y)], 2.0)
        for dx in (-1.05, 0.0, 1.05):
            c.via("VBAT", vx + dx, bus_y)
        last = max(last, vx)
    # VBAT bus on In2 along the columns, up to the battery switch
    q18 = c.find("Q", "QB_G", "SYS")
    sx, sy = c.pad(q18, "5")
    c.track("VBAT", [(last, bus_y), (86.9, bus_y), (86.9, sy)], 3.0, I2)
    c.track("VBAT", [(sx + 0.6, sy), (87.2, sy)], 2.2)
    for x, y in ((86.4, sy - 1.0), (86.4, sy), (86.4, sy + 1.0), (87.5, sy - 0.5), (87.5, sy + 0.5)):
        c.via("VBAT", x, y)


def sys_node(c):
    """USB switch, battery switch, bulk capacitors, trunk to the converter's input capacitors; VBUS_IN from the header."""
    ix, iy = ph.CONV
    q20, q18 = c.find("Q", "VBUS_IN", "SYS"), c.find("Q", "QB_G", "SYS")
    tx = 79.6
    c.track("SYS", [(tx, c.pad(q20, "5")[1] + 0.2), (tx, iy - 3.4)], 2.2)
    caps = sorted((r for r, f in c.fps.items() if r.startswith("C") and f.GetValue() == "47u"
                   and MM(f.GetPosition().y) < 80), key=lambda r: c.pad(r, "1")[1])
    (x2, y2), (x1, y1) = c.pad(caps[0], "1"), c.pad(caps[1], "1")
    c.track("SYS", [(x2, y2), (x1, y1), (tx - 0.6, y1)], 1.2)
    can = next(r for r, f in c.fps.items() if f.GetValue() == "220u" and "/SYS" in [p.GetNetname() for p in f.Pads()])
    c.track("SYS", [c.pad(can, "1"), (tx, c.pad(can, "1")[1])], 2.0)
    c.track("SYS", [(tx, c.pad(q18, "2")[1]), (c.pad(q18, "2")[0] - 0.45, c.pad(q18, "2")[1])], 1.5)
    gx, gy = c.pad(q18, "4")                      # its gate, the pin beside the three SYS pins: a stub south for the router
    c.track("QB_G", [(gx, gy), (gx, gy + 1.2)], 0.2)
    # converter input: bar along the capacitor row, neck from the VIN strip
    u = c.find("U", "FSW")
    c34 = min((r for r, f in c.fps.items() if r.startswith("C") and "/SYS" in [p.GetNetname() for p in f.Pads()]
               and abs(c.pad(r, "1")[1] - (iy - 3.4)) < 0.01), key=lambda r: c.pad(r, "1")[0])
    c.track("SYS", [(tx, iy - 3.4), c.pad(c34, "1")], 1.3)
    vx = c.pad(u, "7")[0]
    c.track("SYS", [(vx, iy - 1.4), (vx, iy - 3.2)], 0.25)
    # VBUS_IN
    j = c.find("J", "VBUS_IN", "CC1")
    ys = sorted(MM(p.GetPosition().y) for p in c.fps[j].Pads() if p.GetNetname() == "/VBUS_IN")
    px = c.pad(j, "1")[0]
    bx = 56.6
    c.track("VBUS_IN", [(bx, ys[0]), (bx, ys[-1])], 1.2)
    for y in ys:
        c.track("VBUS_IN", [(px, y), (bx, y)], 0.6)
    for y in (66.0, 67.2, 70.8, 72.0):
        c.via("VBUS_IN", bx, y)
    c.track("VBUS_IN", [(bx, 66.0), (bx, 72.0)], 1.2, B)
    qx, qy = c.mean(q20, "1", "2", "3")
    c.track("VBUS_IN", [(bx, 68.9), (80.7, 68.9)], 2.5, B)
    for x in (78.5, 79.6, 80.7):
        c.via("VBUS_IN", x, 68.9)
    c.track("VBUS_IN", [(78.5, 68.9), (80.7, 68.9)], 0.8)
    c.track("VBUS_IN", [(qx, qy - 0.35), (qx, 68.9)], 1.5)


def converter(c):
    ix, iy = ph.CONV
    u = c.find("U", "FSW")
    if not (c.pad(u, "7")[0] > ix > c.pad(u, "11")[0] and abs(c.pad(u, "9")[0] - ix) < 0.01):
        sys.exit("converter: VIN strip is not east of the VOUT strip")
    row = sorted((r for r, f in c.fps.items() if r.startswith("C") and abs(c.pad(r, "1")[1] - (iy - 3.4)) < 0.01
                  and MM(f.GetPosition().x) < 80), key=lambda r: c.pad(r, "1")[0])
    out = [r for r in row if c.fps[r].FindPadByNumber("1").GetNetname() == "/+5V"]
    # +5V: strips 11-13 to the capacitor row, bar, vias, In2 trunk
    c.track("+5V", [(c.pad(u, "12")[0], iy - 1.75), (c.pad(u, "12")[0], iy - 3.4)], 1.25)
    c.track("+5V", [c.pad(out[-1], "1"), c.pad(out[0], "1")], 1.3)
    vy = iy - 1.6
    c.track("+5V", [c.pad(out[0], "1"), (55.7, vy)], 2.2)
    for x in (54.6, 55.7, 56.8):
        c.via("+5V", x, vy)
    # PGND: north between the VIN and VOUT capacitors to a bar along their GND pads with a via row; south between the
    # boot capacitors to vias under the inductor
    y_g = min(c.pad(r, "2")[1] for r in row)
    c.track("GND", [(ix, iy - 1.4), (ix, iy - 2.3), (ix - 0.1, iy - 2.5)], 0.3)
    c.track("GND", [(ix - 0.1, iy - 2.5), (ix - 0.1, y_g)], 0.85)
    c.track("GND", [(c.pad(row[0], "2")[0], y_g), (c.pad(row[-1], "2")[0], y_g)], 1.3)
    for r in row:
        x, y = c.pad(r, "2")
        if y - y_g > 0.01:
            c.track("GND", [(x, y), (x, y_g)], 1.0)
    x = c.pad(row[0], "2")[0] - 0.7
    c.track("GND", [(x, y_g - 1.0), (c.pad(row[-1], "2")[0] + 0.6, y_g - 1.0)], 0.9)
    while x < c.pad(row[-1], "2")[0] + 0.7:
        c.via("GND", x, y_g - 1.0, 0.6, 0.3)
        x += 1.5
    c.track("GND", [(ix, iy + 1.4), (ix, iy + 4.5)], 0.3)
    c.track("GND", [(ix, iy + 4.5), (ix, iy + 11.2)], 0.9)
    for dy in (5.6, 7.0, 8.4, 9.8, 11.2):
        c.via("GND", ix, iy + dy, 0.6, 0.3)
    # switch nodes
    ind = c.find("L", "L1")
    for net, pin, cap, lpad in (("L1", "8", c.find("C", "BOOT1"), "1"), ("L2", "10", c.find("C", "BOOT2"), "2")):
        sx = c.pad(u, pin)[0]
        s = 1 if sx > ix else -1
        cx, cy = c.pad(cap, "2")
        if c.fps[cap].FindPadByNumber("2").GetNetname() != "/" + net or abs(cx - (ix + s * 0.96)) > 0.05:
            sys.exit(f"boot capacitor {cap}: pad 2 is not on {net} at the strip")
        lx, ly = c.pad(ind, lpad)
        if (lx - ix) * s < 1:
            sys.exit("inductor is turned the wrong way")
        c.track(net, [(sx, iy + 1.4), (sx, iy + 2.8)], 0.25)
        c.track(net, [(cx, cy), (ix + s * 1.9, iy + 5.5), (ix + s * 2.3, iy + 6.4)], 0.9)
    # VCC: pin 18 west to its capacitor
    vx, vy = c.pad(u, "18")
    c.track("VCC5", [(vx, vy + 0.1), (c.pad(c.find("C", "VCC5"), "1")[0] + 0.4, vy + 0.1)], 0.25)
    ax, ay = c.pad(u, "17")                       # GND pin beside it: its own via, north of the VCC track
    c.track("GND", [(ax, ay), (ix - 3.4, ay)], 0.2)
    c.via("GND", ix - 3.4, ay, 0.6, 0.3)
    # VCC capacitor: its GND pad to the plane at once
    cv = c.find("C", "VCC5")
    gx, gy = c.pad(cv, "2")
    c.track("GND", [(gx, gy), (gx, gy + 2.2), (gx + 1.1, gy + 2.2)], 0.8)
    c.via("GND", gx, gy + 2.2, 0.6, 0.3); c.via("GND", gx + 1.1, gy + 2.2, 0.6, 0.3)


def rail_5v(c):
    """+5V trunk on In2 to the 220 uF and the three ports; port VBUS to the receptacle."""
    iy = ph.CONV[1]
    ty = ph.TRUNK_Y
    ports = sorted(MM(f.GetPosition().x) for r, f in c.fps.items() if "MODULE PORT" in f.GetValue())
    c.track("+5V", [(55.7, iy - 1.6), (55.7, ty), (ports[-1] + 12.6, ty)], 3.0, I2)
    can = next(r for r, f in c.fps.items() if f.GetValue() == "220u" and "/+5V" in [p.GetNetname() for p in f.Pads()])
    cx, cy = c.pad(can, "1")
    c.track("+5V", [(63.0, ty), (63.0, cy - 2.2)], 2.4, I2)
    c.track("+5V", [(cx, cy), (63.0, cy - 2.2)], 2.0)
    for x in (61.8, 63.0, 64.2):
        c.via("+5V", x, cy - 2.2)
    for px in ports:
        p = next(r[-1] for r, f in c.fps.items() if "MODULE PORT" in f.GetValue() and abs(MM(f.GetPosition().x) - px) < 0.01
                 for r in [f.GetValue()])
        u, j, vb = c.find("U", f"REF_{p}"), c.find("J", f"SCK_{p}"), f"VBUS_{p}"
        ux, uy = c.mean(u, "2", "3", "4", "5")
        if ux < px + 10:
            sys.exit(f"port {p}: the source switch's input pins do not face east")
        bx = px + 13.2
        c.track("+5V", [(px + 12.2, ty), (px + 12.2, uy + 0.6)], 3.0, I2)
        for x, y in ((bx, uy - 0.55), (bx, uy + 0.55), (px + 12.2, uy)):       # EN and FLT, the pins above and below, leave east past them
            c.via("+5V", x, y)
        c.track("+5V", [(bx, uy - 0.55), (bx, uy + 0.55)], 0.8)
        c.track("+5V", [(bx, uy), (ux + 0.6, uy)], 1.5)
        x7, y7 = c.pad(u, "7")                                                # the fifth input pin, on the north side: its own via
        c.track("+5V", [(x7, y7), (x7, y7 - 0.6), (x7 + 0.65, y7 - 1.0)], 0.2)
        c.via("+5V", x7 + 0.65, y7 - 1.0, 0.6, 0.3)
        ox, oy = c.mean(u, "14", "15")
        c.track(vb, [(ox, oy), (px + 7.6, oy), (px + 6.6, oy + 1.0)], 0.7)     # slanted: CC2, the pin beside it, leaves west
        c.track(vb, [(px + 6.6, oy + 1.0), (px + 6.6, 135.8)], 1.2)
        gx, gy = c.pad(u, "12")
        c.track("GND", [(gx, gy), (gx + 0.85, gy)], 0.2)
        c.via("GND", *c.pad(u, "21"), 0.6, 0.3)                  # the GND pin between CC1 and CC2: to the exposed pad
        c.via(vb, px + 6.6, 134.6); c.via(vb, px + 6.6, 135.8)
        # In2 bar close in front of the A row (just clear of the locating peg), not further north: the band it covers
        # takes no via, and the A row's signals need theirs between the row and the ESD arrays
        by = c.pad(j, "A1")[1] + 5.02 - 5.6
        c.track(vb, [(px + 6.6, 135.8), (px + 6.6, by), (px + 1.2, by)], 1.0, I2)
        c.track(vb, [(px + 1.2, by), (px - 1.2, by)], 0.5, I2)
        for a, bb in (("A9", "B4"), ("A4", "B9")):
            tx, ty2 = c.pad(j, bb)
            c.track(vb, [(tx, by), (tx, ty2)], 0.5, I2)
            c.track(vb, [c.pad(j, a), (tx, ty2)], 0.3)
        receptacle(c, j, p)


def receptacle(c, j, p):
    """Module-port receptacle (Amphenol 12401548E4-2A), the pins the autorouter does not get out. x, y from its origin,
    y negative towards the board. A row (SMD, y -5.02) leaves north on top: a 1.3 mm stub out of every signal pad, and its
    three GND pads go south to the GND through-pins instead of to vias (a via north of the row shuts its neighbours in). B pins: the row at y -3.71 stands in front of
    the row at y -3.01 with 0.15 mm between neighbours, so of the rear row only the pins beside the two wide gaps get
    north (MOSI on the bottom, MISO on inner 2, SCK on the bottom, each a stub past the front row), and the two in the
    middle (LED data, CC2) leave south and go round the shell pin and the locating peg on the bottom."""
    ox, oy = c.pad(j, "A1")[0] + 2.75, c.pad(j, "A1")[1] + 5.02
    def at(x, y):
        return ox + x, oy + y
    for a, b_, x, y in (("A1", "B12", -2.8, -3.71), ("A12", "B1", 2.8, -3.71), ("B11", None, -2.4, -3.01), ("B8", None, -0.8, -3.01)):
        got = c.pad(j, b_ or a)
        if abs(got[0] - at(x, y)[0]) > 0.01 or abs(got[1] - at(x, y)[1]) > 0.01:
            sys.exit(f"receptacle {j}: pin {b_ or a} is not where the escape pattern expects it")
    c.track("GND", [c.pad(j, "A1"), c.pad(j, "B12")], 0.2)
    c.track("GND", [c.pad(j, "A12"), at(2.68, -4.5), at(2.68, -3.9)], 0.2)        # into B1's pad on the side away from the peg
    ax, ay = c.pad(j, "A3")
    c.track("GND", [(ax, ay), (ax, ay + 0.55), c.pad(j, "B12")], 0.2)
    for pad in ("A2", "A5", "A6", "A7", "A8", "A10", "A11"):                  # so that no neighbour's track closes a pad in
        x, y = c.pad(j, pad)
        c.track(c.fps[j].FindPadByNumber(pad).GetNetname(), [(x, y), (x, y - 1.3)], 0.2)
    c.track(f"MOSI_{p}", [at(-2.4, -3.01), at(-2.1, -3.35), at(-2.1, -4.6)], 0.2, B)
    c.track(f"MISO_{p}", [at(-1.6, -3.01), at(-1.9, -3.35), at(-1.9, -4.6)], 0.2, I2)
    c.track(f"SCK_{p}", [at(2.4, -3.01), at(2.1, -3.35), at(2.1, -4.6)], 0.2, B)
    c.track(f"CSO_{p}", [at(0.4, -3.71), at(0.4, -4.6)], 0.2, B)
    c.track(f"INTO_{p}", [at(-0.4, -3.71), at(-0.4, -4.6)], 0.2, B)
    c.track(f"LEDO_{p}", [at(-0.8, -3.01), at(-0.8, -2.1), at(-4.85, -2.1), at(-4.85, -5.6)], 0.2, B)
    c.track(f"CC2_{p}", [at(0.8, -3.01), at(0.8, -2.1), at(4.85, -2.1), at(4.85, -5.6)], 0.2, B)


def fanout(c):
    """A short stub straight out of every signal pad of the fine-pitch parts (SOT-363, VSSOP, WQFN), so that each pin
    keeps its way out when the autorouter fills the space round the part. NOT USED: with these stubs Freerouting does
    much worse (about 30 connections left open instead of 3 to 12)."""
    ends = [(t.GetNetname(), q.x, q.y) for t in c.b.GetTracks() if t.Type() != pcbnew.PCB_VIA_T for q in (t.GetStart(), t.GetEnd())]
    for ref, f in sorted(c.fps.items()):
        if not any(k in str(f.GetFPID().GetLibItemName()) for k in ("SOT-363", "VSSOP", "WQFN")):
            continue
        fc = f.GetPosition()
        for p in f.Pads():
            net, bb = p.GetNetname(), p.GetBoundingBox()
            w, h = MM(bb.GetWidth()), MM(bb.GetHeight())
            if not net or net == "GND" or net.startswith("unconnected") or not p.GetNumber() or min(w, h) > 0.7:
                continue
            if any(n == net and bb.GetLeft() <= x <= bb.GetRight() and bb.GetTop() <= y <= bb.GetBottom() for n, x, y in ends):
                continue                                        # already has scripted copper
            x, y = MM(p.GetPosition().x), MM(p.GetPosition().y)
            if w >= h:
                end = (x + math.copysign(w / 2 + 0.5, x - MM(fc.x)), y)
            else:
                end = (x, y + math.copysign(h / 2 + 0.5, y - MM(fc.y)))
            c.track(net, [(x, y), end], min(0.2, w, h))


def hub_conn_copper(b):
    c = Cu(b)
    entry = chain(c)
    stages(c, entry)
    sys_node(c)
    converter(c)
    rail_5v(c)
    return c.count                                # fanout(c) was tried here: Freerouting then leaves about 30 connections open


# ---- chain-cap: sixteen straight lines ---------------------------------------------------------------------------
def cap_copper(b):
    """Riser pin n to spring pin n, 9 mm apart. Every line has to pass one row of foreign pins: the riser's far row
    passes the riser's near row on F, the riser's near row passes the strip's near row on B, each through the 0.84 mm
    gap between two pads as a 0.4 mm neck 2.5 mm long (about 3 mOhm) between two 0.75 mm diagonals (pin 1's pad is square), 1.2 mm wide on the straight."""
    c = Cu(b)
    riser = next(r for r, f in c.fps.items() if "RISER" in f.GetValue())
    strip = next(r for r, f in c.fps.items() if "SPRING" in f.GetValue())
    far = max(c.pad(riser, str(n))[1] for n in range(1, 17))
    for n in range(1, 17):
        (x, yr), (xs, ys) = c.pad(riser, str(n)), c.pad(strip, str(n))
        if abs(x - xs) > 0.01 or yr - ys < 8:
            sys.exit(f"cap board: pin {n} of the strip is not straight behind the riser pin")
        net = f"LINE{n}"
        if abs(yr - far) < 0.01:
            y0, layer = yr, F
        else:
            y0, layer = ys + 5.08, B
            c.track(net, [(x, yr), (x, y0)], 1.2, layer)
        c.track(net, [(x, y0), (x + 1.27, y0 - 1.27)], 0.75, layer)
        c.track(net, [(x + 1.27, y0 - 1.27), (x + 1.27, y0 - 3.81)], 0.4, layer)
        c.track(net, [(x + 1.27, y0 - 3.81), (x, y0 - 5.08)], 0.75, layer)
        c.track(net, [(x, y0 - 5.08), (x, ys)], 1.2, layer)
    return c.count


# ---- autorouter ----------------------------------------------------------------------------------------------------
def keep_out(b, x0, y0, x1, y1, name):
    """Rule area (no tracks, no vias, all copper layers), KiCad units. The RT_ ones are for the router only and are
    taken off the board again after it has run."""
    z = pcbnew.ZONE(b)
    z.SetIsRuleArea(True)
    z.SetLayerSet(pcbnew.LSET.AllCuMask())
    z.SetZoneName(name)
    z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(True); z.SetDoNotAllowPads(False)
    z.SetDoNotAllowZoneFills(False); z.SetDoNotAllowFootprints(False)
    o = z.Outline()
    o.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        o.Append(int(x), int(y))
    b.Add(z)


def router_fences(b):
    """What the router does not know: KiCad's clearance to the receptacles' locating pegs and to the board edge."""
    for f in b.GetFootprints():
        if "MODULE PORT" in f.GetValue():
            for p in f.Pads():
                if p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                    c, r = p.GetPosition(), max(p.GetSize().x, p.GetSize().y) // 2 + mm(0.2)
                    keep_out(b, c.x - r, c.y - r, c.x + r, c.y + r, f"RT_PEG_{f.GetReference()}")
    e, d = b.GetBoardEdgesBoundingBox(), mm(0.25)
    keep_out(b, e.GetLeft(), e.GetTop(), e.GetRight(), e.GetTop() + d, "RT_EDGE")
    keep_out(b, e.GetLeft(), e.GetBottom() - d, e.GetRight(), e.GetBottom(), "RT_EDGE")
    keep_out(b, e.GetLeft(), e.GetTop(), e.GetLeft() + d, e.GetBottom(), "RT_EDGE")
    keep_out(b, e.GetRight() - d, e.GetTop(), e.GetRight(), e.GetBottom(), "RT_EDGE")


def drop_layer(text, layer):
    """Take a copper layer out of the router's input: its entry and every pad, via and keep-out shape on it. The vias
    keep their names, so KiCad still imports them as through vias. Tried first and not enough: a track keep-out over the
    layer (the router then places no via at all) and the layer as type power (it routes on it all the same)."""
    text, n = re.subn(r"\(layer %s\s+\(type signal\)\s+\(property\s+\(index \d+\)\s+\)\s+\)\s*" % re.escape(layer), "", text)
    if n != 1:
        sys.exit(f"DSN: layer entry of {layer} not found")
    heads = ("(shape ", "(keepout ", "(wire_keepout ", "(via_keepout ", "(plane ")
    while layer in text:
        i = text.find(layer)
        j = max(text.rfind(h, 0, i) for h in heads)
        if j < 0:
            sys.exit(f"DSN: {layer} outside a shape")
        depth, k = 0, j
        while True:
            depth += {"(": 1, ")": -1}.get(text[k], 0)
            k += 1
            if depth == 0:
                break
        text = text[:j] + text[k:]
    return text


def freeroute(b, name, passes, drop_gnd):
    work = ROOT / "build" / "route" / name
    work.mkdir(parents=True, exist_ok=True)
    dsn, ses = work / f"{name}.dsn", work / f"{name}.ses"
    if not pcbnew.ExportSpecctraDSN(b, str(dsn)):
        sys.exit("DSN export failed")
    if drop_gnd:                                    # GND is the plane's job: the router gets the net with one pin only,
        text = drop_layer(dsn.read_text(), "In1.Cu")   # and a board without In1 (see drop_layer)
        text = text.replace("(clearance 150)", "(clearance 160)")   # its 0.15 mm comes out a hair under KiCad's
        i = text.index("(net GND")
        depth, j = 0, i
        while True:
            depth += {"(": 1, ")": -1}.get(text[j], 0)
            j += 1
            if depth == 0:
                break
        pins = re.search(r"\(pins\s+(\S+)", text[i:j])
        dsn.write_text(text[:i] + f"(net GND (pins {pins.group(1).rstrip(')')}))" + text[j:])
    ses.unlink(missing_ok=True)
    with open(work / "freerouting.log", "w") as log:
        subprocess.run(["java", "-jar", str(JAR), "-de", str(dsn), "-do", str(ses), "-mp", str(passes),
                        "--gui.enabled=false"], stdout=log, stderr=subprocess.STDOUT, timeout=3300)
    if not ses.exists():
        sys.exit(f"Freerouting wrote no session file; see build/route/{name}/freerouting.log")
    if not pcbnew.ImportSpecctraSES(b, str(ses)):
        sys.exit("SES import failed")


# ---- ground ----------------------------------------------------------------------------------------------------------
def gnd_vias(b):
    """A GND via beside every SMD GND pad on the top side (in the pad for an exposed pad), tied to it by a short track."""
    gnd = b.FindNet("GND")
    edge = b.GetBoardEdgesBoundingBox()
    segs, dots, boxes = [], [], []
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            dots.append((t.GetPosition().x, t.GetPosition().y, t.GetWidth(F) // 2, t.GetNetname()))
        else:
            segs.append((t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y, t.GetWidth() // 2, t.GetNetname(), t.GetLayer()))
    for f in b.GetFootprints():
        for p in f.Pads():
            bb = p.GetBoundingBox()
            smd = p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD
            if smd and not (p.IsOnLayer(F) or p.IsOnLayer(B)):
                continue                                        # paste-only apertures
            boxes.append((bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom(), p.GetNetname(),
                          (F if p.IsOnLayer(F) else B) if smd else None, (f.GetReference(), p.GetNumber(), bb.GetLeft(), bb.GetTop())))

    def seg_d(x, y, s):
        vx, vy = s[2] - s[0], s[3] - s[1]
        t = max(0.0, min(1.0, ((x - s[0]) * vx + (y - s[1]) * vy) / (vx * vx + vy * vy or 1)))
        return math.hypot(s[0] + t * vx - x, s[1] + t * vy - y)

    def box_d(x, y, bx):
        return math.hypot(max(bx[0] - x, 0, x - bx[2]), max(bx[1] - y, 0, y - bx[3]))

    def via_ok(x, y, r, own, near):
        if not (edge.GetLeft() + mm(0.6) < x < edge.GetRight() - mm(0.6) and edge.GetTop() + mm(0.6) < y < edge.GetBottom() - mm(0.6)):
            return False
        ns, nd, nb = near
        if any(s[5] != "GND" and seg_d(x, y, s) < r + s[4] + mm(0.2) for s in ns):
            return False
        if any(math.hypot(d[0] - x, d[1] - y) < r + d[2] + mm(0.25) for d in nd):
            return False
        return not any(bx[6] != own and box_d(x, y, bx) < r + mm(0.2) for bx in nb)

    def path_ok(x0, y0, x1, y1, r, own, near):
        ns, nd, nb = near
        for q in (0.15, 0.3, 0.45, 0.6, 0.75, 0.9):
            x, y = x0 + (x1 - x0) * q, y0 + (y1 - y0) * q
            if any(s[5] != "GND" and s[6] == F and seg_d(x, y, s) < r + s[4] + mm(0.16) for s in ns):
                return False
            if any(d[3] != "GND" and math.hypot(d[0] - x, d[1] - y) < r + d[2] + mm(0.16) for d in nd):
                return False
            if any(bx[6] != own and bx[4] != "GND" and bx[5] in (F, None) and box_d(x, y, bx) < r + mm(0.16) for bx in nb):
                return False
        return True

    added, missed = 0, []
    for f in b.GetFootprints():
        if f.IsFlipped():
            continue
        for p in f.Pads():
            if p.GetNetname() != "GND" or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD or not p.IsOnLayer(F):
                continue
            bb = p.GetBoundingBox()
            c = p.GetPosition()
            w, h = bb.GetWidth(), bb.GetHeight()
            reach = max(w, h) / 2 + mm(4.6)
            near = ([s for s in segs if seg_d(c.x, c.y, s) < reach + s[4]], [d for d in dots if math.hypot(d[0] - c.x, d[1] - c.y) < reach + mm(1)],
                    [bx for bx in boxes if box_d(c.x, c.y, bx) < reach])
            pb = (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom())
            if any(d[3] == "GND" and box_d(d[0], d[1], pb) < mm(0.05) for d in near[1]) or \
                    any(s[5] == "GND" and s[6] == F and min(box_d(s[0], s[1], pb), box_d(s[2], s[3], pb)) < 1 for s in near[0]):
                continue                                        # scripted copper already ties this pad to a via
            spot = None
            own = (f.GetReference(), p.GetNumber(), bb.GetLeft(), bb.GetTop())
            if min(w, h) > mm(0.95) and w * h > mm(1.5) * mm(1.0) and f.GetReference()[0] in "UD" and via_ok(c.x, c.y, mm(0.3), own, near):
                spot = (c.x, c.y)                               # exposed pad: via in the pad
            else:
                tw = min(mm(0.4), max(mm(0.2), min(w, h)))
                for dist in (0.9, 1.2, 1.5, 1.9, 2.4, 3.0, 3.6, 4.2):
                    for ang in range(0, 360, 15):
                        dx, dy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
                        x = c.x + int(dx * (w / 2 + mm(dist))) if abs(dx) > 0.01 else c.x
                        y = c.y + int(dy * (h / 2 + mm(dist))) if abs(dy) > 0.01 else c.y
                        if via_ok(x, y, mm(0.3), own, near) and path_ok(c.x, c.y, x, y, tw // 2, own, near):
                            spot = (x, y)
                            break
                    if spot:
                        break
                if spot:
                    t = pcbnew.PCB_TRACK(b)
                    t.SetStart(c); t.SetEnd(pcbnew.VECTOR2I(int(spot[0]), int(spot[1])))
                    t.SetWidth(tw); t.SetLayer(F); t.SetNet(gnd); t.SetLocked(True)
                    b.Add(t)
                    segs.append((c.x, c.y, int(spot[0]), int(spot[1]), tw // 2, "GND", F))
            if spot is None:
                missed.append(f"{f.GetReference()}.{p.GetNumber()}")
                continue
            v = pcbnew.PCB_VIA(b)
            v.SetPosition(pcbnew.VECTOR2I(int(spot[0]), int(spot[1])))
            v.SetWidth(F, mm(0.6)); v.SetDrill(mm(0.3)); v.SetNet(gnd); v.SetLocked(True)
            b.Add(v)
            dots.append((int(spot[0]), int(spot[1]), mm(0.3), "GND"))
            added += 1
    print(f"GND vias at SMD pads: {added}" + (f"; no room at {' '.join(missed)} (left to the finishing pass)" if missed else ""))
    return [tuple(m.split(".")) for m in missed]


def gnd_pours(b, layers, solid=()):
    box = b.GetBoardEdgesBoundingBox()
    for layer in layers:
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
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_NEVER if layer in solid else pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        b.Add(z)


# ---- finishing: a small maze router for what the autorouter leaves open ------------------------------------------
CELL = 0.1                       # grid, mm
T_W, T_CLR = 0.2, 0.15           # track it draws, clearance it keeps (plus 0.4 of a cell for the grid's own error)
RIPUP = False                    # rip-up and retry is written (finish) but off: on hub-conn it tore up the tracks round the
                                 # stack connector and ended with more open connections than it began with (9 -> 18)


def seg_seg(a, b_):
    """Smallest distance between two segments (x1, y1, x2, y2)."""
    def pt(px, py, s_):
        vx, vy = s_[2] - s_[0], s_[3] - s_[1]
        t = max(0.0, min(1.0, ((px - s_[0]) * vx + (py - s_[1]) * vy) / (vx * vx + vy * vy or 1e-12)))
        return math.hypot(s_[0] + t * vx - px, s_[1] + t * vy - py)
    d1 = (a[2] - a[0]) * (b_[1] - a[1]) - (a[3] - a[1]) * (b_[0] - a[0])
    d2 = (a[2] - a[0]) * (b_[3] - a[1]) - (a[3] - a[1]) * (b_[2] - a[0])
    d3 = (b_[2] - b_[0]) * (a[1] - b_[1]) - (b_[3] - b_[1]) * (a[0] - b_[0])
    d4 = (b_[2] - b_[0]) * (a[3] - b_[1]) - (b_[3] - b_[1]) * (a[2] - b_[0])
    if d1 * d2 < 0 and d3 * d4 < 0:
        return 0.0
    return min(pt(a[0], a[1], b_), pt(a[2], a[3], b_), pt(b_[0], b_[1], a), pt(b_[2], b_[3], a))


def finish(b, pcb, name, extra=()):
    """Close the connections KiCad's DRC still lists as open. Lee / A* on a 0.1 mm grid (0.05 mm for gaps under 6 mm)
    over F, In2 and B (never In1),
    0.2 mm tracks and 0.6 / 0.3 vias, obstacles taken from the board as it is (other nets' tracks, vias, pads, holes,
    board edge, each grown by half a track plus the clearance); the net's own copper is free ground. One connection
    at a time, each seeing the ones before it; the search area grows when a first try finds nothing. With RIPUP (off,
    see there) the autorouter's own tracks would stop counting as obstacles in a last try and those in the way be
    taken out. Zones are ignored: they are refilled afterwards. What it cannot close stays open for the next try of
    tools/route_hub.sh.
    `extra`: (ref, pad) of GND pads that got no via; each is taken to the nearest GND via."""
    import heapq
    import json
    rpt = ROOT / "build" / "kicad-check" / f"{name}-finish.json"
    subprocess.run([CLI, "pcb", "drc", "--severity-all", "--format", "json", "-o", str(rpt), str(pcb)], capture_output=True)
    todo = json.loads(rpt.read_text())["unconnected_items"]
    gv = [t.GetPosition() for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T and t.GetNetname() == "GND"]
    extra = list(extra)
    for u in todo:                                  # a GND pad that only its pour island holds: same cure
        for it in u["items"][:2]:
            m = re.match(r"Pad (\S+) \[GND\] of (\S+) on F\.Cu", it["description"])
            if m and any("Zone" in o["description"] for o in u["items"][:2]) and (m.group(2), m.group(1)) not in extra:
                extra.append((m.group(2), m.group(1)))
    for ref, num in extra:
        p = b.FindFootprintByReference(ref).FindPadByNumber(num).GetPosition()
        if any(math.hypot(q.x - p.x, q.y - p.y) < mm(0.6) for q in gv):
            continue
        q = min(gv, key=lambda q: math.hypot(q.x - p.x, q.y - p.y))
        todo.append({"items": [{"description": f"Pad {num} [GND] of {ref} on F.Cu", "pos": {"x": MM(p.x), "y": MM(p.y)}},
                               {"description": "Via [GND] drop", "pos": {"x": MM(q.x), "y": MM(q.y)}}]})
    layers = (F, I2, B)
    lname = {"F.Cu": 0, "In2.Cu": 1, "B.Cu": 2}
    edge = b.GetBoardEdgesBoundingBox()
    ex0, ey0, ex1, ey1 = MM(edge.GetLeft()) + 0.45, MM(edge.GetTop()) + 0.45, MM(edge.GetRight()) - 0.45, MM(edge.GetBottom()) - 0.45

    def lay(d):
        m = re.search(r"on (F\.Cu|In2\.Cu|B\.Cu)", d)
        return (0, 1, 2) if ("PTH" in d or d.startswith("Via") or not m) else (lname[m.group(1)],)

    def solve(net, a, z, margin, soft, cs):
        grow_t, grow_v = T_W / 2 + T_CLR + 0.4 * cs, 0.3 + T_CLR + 0.4 * cs
        (ax, ay), (zx, zy) = (a["pos"]["x"], a["pos"]["y"]), (z["pos"]["x"], z["pos"]["y"])
        gx0, gy0 = max(ex0, min(ax, zx) - margin), max(ey0, min(ay, zy) - margin)
        gx1, gy1 = min(ex1, max(ax, zx) + margin), min(ey1, max(ay, zy) + margin)
        nx, ny = int((gx1 - gx0) / cs) + 1, int((gy1 - gy0) / cs) + 1
        blocked = [bytearray(nx * ny) for _ in layers]
        own = [bytearray(nx * ny) for _ in layers]
        vblock = bytearray(nx * ny)

        def stamp(arr, kind, g, grow):
            if kind == "seg":
                x1, y1, x2, y2, r = g
                r += grow
                if r <= 0:
                    return
                i0, i1 = max(0, int((min(x1, x2) - r - gx0) / cs)), min(nx - 1, int((max(x1, x2) + r - gx0) / cs) + 1)
                j0, j1 = max(0, int((min(y1, y2) - r - gy0) / cs)), min(ny - 1, int((max(y1, y2) + r - gy0) / cs) + 1)
                vx, vy = x2 - x1, y2 - y1
                l2 = vx * vx + vy * vy or 1e-12
                rr = r * r
                for j in range(j0, j1 + 1):
                    y = gy0 + j * cs
                    row = j * nx
                    for i in range(i0, i1 + 1):
                        x = gx0 + i * cs
                        t = ((x - x1) * vx + (y - y1) * vy) / l2
                        t = 0.0 if t < 0 else 1.0 if t > 1 else t
                        dx, dy = x1 + t * vx - x, y1 + t * vy - y
                        if dx * dx + dy * dy <= rr:
                            arr[row + i] = 1
            else:
                l, t, r_, bt = g[0] - grow, g[1] - grow, g[2] + grow, g[3] + grow
                if r_ <= l or bt <= t:
                    return
                i0, i1 = max(0, int(math.ceil((l - gx0) / cs))), min(nx - 1, int((r_ - gx0) / cs))
                j0, j1 = max(0, int(math.ceil((t - gy0) / cs))), min(ny - 1, int((bt - gy0) / cs))
                for j in range(j0, j1 + 1):
                    for i in range(i0, i1 + 1):
                        arr[j * nx + i] = 1

        def item(kind, g, on, n, extra_=0.0):
            if kind == "seg":
                if max(g[0], g[2]) + 1.5 < gx0 or min(g[0], g[2]) - 1.5 > gx1 or max(g[1], g[3]) + 1.5 < gy0 or min(g[1], g[3]) - 1.5 > gy1:
                    return
            elif g[2] + 1.5 < gx0 or g[0] - 1.5 > gx1 or g[3] + 1.5 < gy0 or g[1] - 1.5 > gy1:
                return
            for k in on:
                if n == net:                                    # free ground only where a new track stays inside the old copper:
                    if kind == "box" or g[4] - T_W / 2 > 0.02:  # pads, vias, wide tracks; a thin track is no ground and no obstacle
                        stamp(own[k], kind, g, -T_W / 2)
                else:
                    stamp(blocked[k], kind, g, grow_t + extra_)
            if n != net:
                stamp(vblock, kind, g, grow_v + extra_)

        for t in b.GetTracks():
            n = t.GetNetname()
            if soft and n != net and not t.IsLocked():
                continue
            if t.Type() == pcbnew.PCB_VIA_T:
                p, r = t.GetPosition(), MM(t.GetWidth(F)) / 2
                item("seg", (MM(p.x), MM(p.y), MM(p.x), MM(p.y), r), (0, 1, 2), n)
            elif t.GetLayer() in layers:
                item("seg", (MM(t.GetStart().x), MM(t.GetStart().y), MM(t.GetEnd().x), MM(t.GetEnd().y), MM(t.GetWidth()) / 2),
                     (layers.index(t.GetLayer()),), n)
        for f in b.GetFootprints():
            for p in f.Pads():
                bb = p.GetBoundingBox()
                g = (MM(bb.GetLeft()), MM(bb.GetTop()), MM(bb.GetRight()), MM(bb.GetBottom()))
                att = p.GetAttribute()
                if att == pcbnew.PAD_ATTRIB_SMD:
                    if p.IsOnLayer(F) or p.IsOnLayer(B):
                        item("box", g, (0,) if p.IsOnLayer(F) else (2,), p.GetNetname())
                else:
                    item("box", g, (0, 1, 2), p.GetNetname() if att == pcbnew.PAD_ATTRIB_PTH else "-", 0.2 if att == pcbnew.PAD_ATTRIB_NPTH else 0.0)

        def cell(x, y):
            return min(nx - 1, max(0, int(round((x - gx0) / cs)))), min(ny - 1, max(0, int(round((y - gy0) / cs))))

        def ok(k, i, j):
            c = j * nx + i
            return own[k][c] or not blocked[k][c]
        (si, sj), (ti, tj) = cell(ax, ay), cell(zx, zy)
        goal = {(k, ti, tj) for k in lay(z["description"])}
        for gx, gy, gl in z.get("also", ()):                    # any other pad of the net will do as well
            if gx0 <= gx <= gx1 and gy0 <= gy <= gy1:
                goal |= {(k, *cell(gx, gy)) for k in gl}
        tij = sorted({(g_[1], g_[2]) for g_ in goal})
        drop = z["description"].endswith("drop")                # a GND pad: the first spot where a via fits will do
        heap, cost, prev = [], {}, {}
        for k in lay(a["description"]):
            cost[(k, si, sj)] = 0.0
            heapq.heappush(heap, (0.0, k, si, sj))
        end = None
        while heap:
            _, k, i, j = heapq.heappop(heap)
            if (k, i, j) in goal or drop and k == 0 and not vblock[j * nx + i] and abs(i - si) + abs(j - sj) > 6:
                end = (k, i, j)
                break
            c0 = cost[(k, i, j)]
            steps = []
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                i2, j2 = i + di, j + dj
                if not (0 <= i2 < nx and 0 <= j2 < ny):
                    continue
                free = ok(k, i2, j2) or (k, i2, j2) in goal
                if free and di and dj and not (ok(k, i2, j) and ok(k, i, j2)):
                    free = False
                if free:
                    steps.append(((k, i2, j2), 1.414 if di and dj else 1.0))
            c = j * nx + i
            if not vblock[c] or own[0][c] and own[1][c] and own[2][c]:
                steps += [((k2, i, j), 40.0) for k2 in (0, 1, 2) if k2 != k and (ok(k2, i, j) or (k2, i, j) in goal)]
            for nb, w in steps:
                c1 = c0 + w
                if c1 < cost.get(nb, 1e18):
                    cost[nb] = c1
                    prev[nb] = (k, i, j)
                    h = min(max(abs(nb[1] - i_), abs(nb[2] - j_)) + 0.414 * min(abs(nb[1] - i_), abs(nb[2] - j_)) for i_, j_ in tij)
                    heapq.heappush(heap, (c1 + h, *nb))
        if end is None:
            return None
        path = [end]
        while path[-1] in prev:
            path.append(prev[path[-1]])
        path.reverse()
        pts = [(path[0][0], ax, ay)] + [(k, gx0 + i * cs, gy0 + j * cs) for k, i, j in path]
        if drop and end not in goal:
            dropped = [(pts[-1][1], pts[-1][2])]
        else:
            dropped = []
            if (end[1], end[2]) == (ti, tj):
                pts.append((path[-1][0], zx, zy))
            else:                                               # ended on another pad of the net: to its centre
                gx, gy = min(((gx, gy) for gx, gy, _ in z["also"]), key=lambda q: math.hypot(q[0] - pts[-1][1], q[1] - pts[-1][2]))
                pts.append((path[-1][0], gx, gy))
        segs, vias, run = [], [], [pts[0]]
        for q in pts[1:]:
            if q[0] != run[-1][0]:                              # layer change: a via, unless a through pad or a via stands there
                x, y = run[-1][1], run[-1][2]
                segs += [(run[0][0], p_[1], p_[2], q_[1], q_[2]) for p_, q_ in zip(run, run[1:])]
                c = int((y - gy0) / cs + 0.5) * nx + int((x - gx0) / cs + 0.5)
                if not (own[0][c] and own[1][c] and own[2][c]):
                    vias.append((x, y))
                run = [(q[0], x, y), q] if (q[1], q[2]) != (x, y) else [q]
            elif len(run) > 1 and abs((q[1] - run[-1][1]) * (run[-1][2] - run[-2][2]) - (q[2] - run[-1][2]) * (run[-1][1] - run[-2][1])) < 1e-9:
                run[-1] = q                                     # same direction: one segment
            else:
                run.append(q)
        segs += [(run[0][0], p_[1], p_[2], q_[1], q_[2]) for p_, q_ in zip(run, run[1:])]
        return segs, vias + dropped

    done = 0
    for u in todo:
        a, z = u["items"][0], u["items"][1]
        if "Zone" in a["description"] or "Zone" in z["description"]:
            continue
        net = re.search(r"\[(.+?)\]", a["description"]).group(1)
        smd = [it for it in (a, z) if re.match(r"Pad \S+ \[", it["description"])]
        if len(smd) == 1 and net != "GND":                      # a lone SMD pad against the rest of its net: start at the pad,
            a, z = smd[0], dict(z if smd[0] is a else a)        # and any other pad of the net is as good an end as the one DRC names
            z["also"] = [(MM(p.GetPosition().x), MM(p.GetPosition().y), (0, 1, 2) if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH else (0,))
                         for f in b.GetFootprints() for p in f.Pads()
                         if p.GetNetname() == net and (p.IsOnLayer(F) or p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH)
                         and math.hypot(MM(p.GetPosition().x) - a["pos"]["x"], MM(p.GetPosition().y) - a["pos"]["y"]) > 0.05]
        got, how = None, ""
        gap = math.hypot(a["pos"]["x"] - z["pos"]["x"], a["pos"]["y"] - z["pos"]["y"])
        tries = ((5.0, False, CELL), (14.0, False, CELL), (30.0, False, CELL)) + (((8.0, True, CELL), (20.0, True, CELL)) if RIPUP else ())
        if gap < 6:                                             # a short gap in a tight spot: the fine grid first
            tries = ((2.5, False, CELL / 2),) + tries
        for margin, soft, cs in tries:
            got = solve(net, a, z, margin, soft, cs)
            if got:
                how = " after rip-up" if soft else ""
                break
        where = f"{net} ({a['pos']['x']:.1f}, {a['pos']['y']:.1f}) - ({z['pos']['x']:.1f}, {z['pos']['y']:.1f})"
        if not got:
            print(f"  finish: NO PATH for {where}")
            continue
        segs, vias = got
        ripped = 0
        if how:
            for t in list(b.GetTracks()):
                if t.IsLocked() or t.GetNetname() == net:
                    continue
                if t.Type() == pcbnew.PCB_VIA_T:
                    p, r = t.GetPosition(), MM(t.GetWidth(F)) / 2
                    q = (MM(p.x), MM(p.y), MM(p.x), MM(p.y))
                    hit = any(seg_seg(q, s_[1:]) < r + T_W / 2 + T_CLR + 0.01 for s_ in segs) or \
                        any(math.hypot(q[0] - x, q[1] - y) < r + 0.3 + 0.26 for x, y in vias)
                elif t.GetLayer() in layers:
                    k, r = layers.index(t.GetLayer()), MM(t.GetWidth()) / 2
                    q = (MM(t.GetStart().x), MM(t.GetStart().y), MM(t.GetEnd().x), MM(t.GetEnd().y))
                    hit = any(s_[0] == k and seg_seg(q, s_[1:]) < r + T_W / 2 + T_CLR + 0.01 for s_ in segs) or \
                        any(seg_seg(q, (x, y, x, y)) < r + 0.3 + T_CLR + 0.01 for x, y in vias)
                else:
                    hit = False
                if hit:
                    b.Remove(t)
                    ripped += 1
        cu = Cu(b)
        for k, x1, y1, x2, y2 in segs:
            cu.track(net, [(x1, y1), (x2, y2)], T_W, layers[k])
        for x, y in vias:
            cu.via(net, x, y, 0.6, 0.3)
        done += 1
        print(f"  finish: {where}: {len(segs)} segments, {len(vias)} vias{how}" + (f", {ripped} autorouted items taken out" if ripped else ""))
    return done


def drop_violators(b, pcb, name):
    """Take out the autorouter's tracks that KiCad's DRC reports for clearance (it squeezes past a pad now and then);
    finish() then draws the connection again."""
    import json
    rpt = ROOT / "build" / "kicad-check" / f"{name}-finish.json"
    subprocess.run([CLI, "pcb", "drc", "--severity-all", "--format", "json", "-o", str(rpt), str(pcb)], capture_output=True)
    lid = {"F.Cu": F, "In2.Cu": I2, "B.Cu": B}
    grave = []
    for v in json.loads(rpt.read_text())["violations"]:
        if v["severity"] != "error" or v["type"] not in ("clearance", "hole_clearance", "copper_edge_clearance", "shorting_items", "tracks_crossing"):
            continue
        for it in v["items"]:
            m = re.match(r"Track \[(.+?)\] on (\S+), length ([0-9.]+) mm", it["description"])
            if not m or m.group(2) not in lid:
                continue
            for t in b.GetTracks():
                if t.Type() == pcbnew.PCB_VIA_T or t.IsLocked() or t.GetNetname() != m.group(1) or t.GetLayer() != lid[m.group(2)]:
                    continue
                if abs(MM(t.GetLength()) - float(m.group(3))) < 0.0006 and min(
                        math.hypot(MM(q.x) - it["pos"]["x"], MM(q.y) - it["pos"]["y"]) for q in (t.GetStart(), t.GetEnd())) < MM(t.GetLength()) + 0.01:
                    grave.append(t)
    seen = set()
    for t in grave:
        key = (t.GetStart().x, t.GetStart().y, t.GetEnd().x, t.GetEnd().y, t.GetLayer())
        if key not in seen:
            seen.add(key)
            b.Remove(t)
    if seen:
        print(f"  finish: {len(seen)} autorouted segments with a clearance error removed")
    return len(seen)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    name = args[0]
    if "--finish" in sys.argv:                      # on a routed board: only the finishing pass
        pcb = Path(os.environ.get("HUB_PCB", ROOT / "hardware" / name / f"{name}.kicad_pcb"))
        b = pcbnew.LoadBoard(str(pcb))
        fill = [CLI, "pcb", "drc", "--refill-zones", "--save-board", "-o", str(ROOT / "build" / "kicad-check" / f"{name}-fill.rpt"), str(pcb)]
        for _ in range(5):
            n = drop_violators(b, pcb, name) + finish(b, pcb, name)
            if not n:
                break
            pcbnew.SaveBoard(str(pcb), b)
            subprocess.run(fill, capture_output=True)
        sys.stdout.flush()
        os._exit(0)
    passes = next((sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--passes"), "30")
    pcb = ROOT / "hardware" / name / f"{name}.kicad_pcb"
    b = pcbnew.LoadBoard(str(pcb))
    if len(b.GetTracks()):
        sys.exit(f"{pcb.name} already has tracks; re-run tools/pcb_hub.py --force {name} first")
    four = name == "hub-conn"
    if name == "chain-cap":
        print(f"{name}: {cap_copper(b)} scripted segments")
        pcbnew.SaveBoard(str(pcb), b)
        sys.stdout.flush()
        os._exit(0)
    if four:
        print(f"{name}: {hub_conn_copper(b)} scripted segments and vias")
        gnd_vias(b)                                 # before the router, so that it leaves them their room
        router_fences(b)
    if "--no-route" not in sys.argv:
        freeroute(b, name, passes, drop_gnd=four)   # (a second run from its own result starts over: no gain)
    on_plane = [t for t in b.GetTracks() if t.Type() != pcbnew.PCB_VIA_T and t.GetLayer() == I1]
    if on_plane:
        print(f"WARNING {len(on_plane)} tracks on the GND plane layer")
    for z in [z for z in b.Zones() if z.GetZoneName().startswith("RT_")]:
        b.Remove(z)                                 # only for the router; KiCad's own hole rules take over
    for v in b.GetTracks():                         # imported vias take the net class drill: 0.4 mm in a 0.6 mm via
        if v.Type() == pcbnew.PCB_VIA_T and not v.IsLocked() and v.GetWidth(F) < mm(0.7):
            v.SetDrill(mm(0.3))
    thin = [t for t in b.GetTracks() if t.Type() != pcbnew.PCB_VIA_T and t.GetWidth() < mm(0.15)]
    for t in thin:                                  # the router necks a few stubs down below the board's minimum
        t.SetWidth(mm(0.15))
    missed = []
    if four:
        missed = gnd_vias(b)                        # pads that had no room before
        gnd_pours(b, (F, I1, I2, B))
    else:
        gnd_pours(b, (F, B))
    fill = [CLI, "pcb", "drc", "--refill-zones", "--save-board", "-o", str(ROOT / "build" / "kicad-check" / f"{name}-fill.rpt"), str(pcb)]
    pcbnew.SaveBoard(str(pcb), b)
    subprocess.run(fill, capture_output=True)
    for _ in range(5 if four and "--no-route" not in sys.argv else 0):      # what the autorouter left open or got wrong
        dropped = drop_violators(b, pcb, name)
        if dropped:
            pcbnew.SaveBoard(str(pcb), b)
            subprocess.run(fill, capture_output=True)
        closed = finish(b, pcb, name, missed)
        if closed:
            pcbnew.SaveBoard(str(pcb), b)
            subprocess.run(fill, capture_output=True)
        if not dropped and not closed:
            break
    print(f"{name}: {len(b.GetTracks())} segments and vias in all")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
