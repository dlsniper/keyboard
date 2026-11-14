#!/usr/bin/env python3
"""Place the hub boards (M2 step 1): hub-core, hub-conn, battery, chain-cap. Outline, footprints, nets, holes, rules.

Run with KiCad's Python (KiCad closed):
    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 tools/pcb_hub.py [--force] [board ...]
`--force` overwrites a board that already has tracks.

Positions that the case shares come from mech/hub/hub_geom.py (also read by the FreeCAD section, mech/hub/build_hub.py):
board size, screw holes, stack connector, chain riser and target pads, module ports, Pico, buttons, expansion header.
Hub coordinates (x right, y to the rear, origin on the tower axis) map to KiCad as (100 + x, 100 - y).

Fixed parts are placed by name; everything else is packed, group by group, into a zone of the board. The group
is the symbol field `Group` written by tools/sch_hub.py (port A-C, pack 1-5, sense, switch, conv, misc). The
packing is a first, DRC-clean placement: the power stage and the port clusters are arranged for routing in the
routing session. All SMD parts are on the top side; only the chain's target pads are underneath.

Mating checks done here (the script stops if one fails):
- stack 2x25: the same footprint, place and turn on core and connector layer (stack-through ESQ, both on top);
- chain 2x8: target pad n under the connector layer and under each battery board sits over pin n of the spring-pin
  strip on the cap board (a PinHeader_2x08 pattern at CHAIN_PADS_XY);
- the three Pico spring pins sit on TP2, TP3, TP6 as drawn in KiCad's RaspberryPi_Pico_W_SMD footprint.
"""
import json
import math
import os
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mech" / "hub"))
import hub_geom as g  # noqa: E402
import pcb_keys as pk  # noqa: E402

X0 = Y0 = 100.0
GAP = 0.5            # between packed parts' bounding boxes
STEP = 0.5
RECEPTACLE_EDGE = 4.7   # receptacle origin to the board edge [check] Amphenol 12401548E4-2A drawing
CLASS_OF = {"GND": "Ground", "/+5V": "Power", "/SYS": "Power", "/VBAT": "Power", "/VBUS*": "Power", "/PACK*": "Power",
            "/VM*": "Power", "/L1": "Power", "/L2": "Power", "/CELL+": "Power"}

# hub-conn is a 4-layer board (user, 2026-11-13): F parts and signals, In1 GND plane, In2 power and signals, B signals.
# Its heavy copper is drawn by tools/route_hub.py; the classes below are what the autorouter uses for the thin rest.
# battery: the pack lines carry up to the fuse's 5 A, doubled on two pins.
CLASSES = {
    "hub-conn": [dict(pk.DEFAULT_CLASS, clearance=0.15, track_width=0.2),
                 dict(pk.POWER_CLASS, clearance=0.15, track_width=0.4), dict(pk.GND_CLASS, clearance=0.15)],
    "battery": [pk.DEFAULT_CLASS, dict(pk.POWER_CLASS, track_width=1.5, via_diameter=1.0, via_drill=0.5), pk.GND_CLASS],
    "chain-cap": [pk.DEFAULT_CLASS, dict(pk.POWER_CLASS, track_width=1.2), pk.GND_CLASS],
}
CLASSES["port-module"] = CLASSES["hub-conn"]        # 4 layers too (tools/pcb_port.py)
CLASSES["usb-port"] = CLASSES["hub-conn"]
CLASS_OF["/+3V3"] = "Power"
CLASS_OF["/AUX_5V"] = "Power"
CLASS_OF["/LINE*"] = "Power"


DRU = """(version 1)
# Written by tools/pcb_hub.py. Footprint-inherent exceptions to the board-wide rules.
(rule "pads of one footprint follow its land pattern"
  (condition "A.Type == 'Pad' && B.Type == 'Pad' && A.Parent == B.Parent")
  (constraint clearance (min 0.13mm)))
(rule "spring pins stand under the Pico"
  (condition "A.Reference == 'TP*' || B.Reference == 'TP*'")
  (constraint courtyard_clearance (min -100mm)))
"""
# Amphenol 12401548E4-2A: 0.4 mm holes in 0.65 mm pads on a staggered 0.8 mm grid, as its drawing asks (to clear with JLCPCB at the order)
# GCT USB4085 (usb-port): 0.4 mm holes on a 0.85 mm pitch, 0.45 mm hole to hole: the same exception
DRU_PORTS = """(rule "module port receptacle pins"
  (condition "{ports}")
  (constraint annular_width (min 0.1mm))
  (constraint hole_to_hole (min 0.2mm))
  (constraint edge_clearance (min 0.2mm)))
"""


def K(x, y):
    return X0 + x, Y0 - y


def turn(x, y, angle, back):
    """Footprint-local point to its offset from the footprint position: mirrored on the back, then turned by
    `angle` (KiCad's sense, counter-clockwise seen from above, y down). Checked against real placements below."""
    if back:
        y = -y          # what pcbnew does for Flip(left-right) followed by SetOrientationDegrees (seen on placed pads)
    a = math.radians(angle)
    return x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a)


def local_pads(fpid):
    fp = pk.load_fp(fpid)
    return {p.GetNumber(): (pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y)) for p in fp.Pads() if p.GetNumber()}


def measure(fpid, angle, back):
    """Bounding box (pads, courtyard, fab; no text) of a footprint put at 0, 0: returns (x0, y0, x1, y1), pad centre.
    Computed, not by flipping a loose footprint: Flip() on a footprint that is not on a board crashes pcbnew."""
    fp = pk.load_fp(fpid)
    bb = fp.GetBoundingBox(False)
    c = [pcbnew.ToMM(v) for v in (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom())]
    pts = [turn(x, y, angle, back) for x in (c[0], c[2]) for y in (c[1], c[3])]
    box = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
    pp = [turn(x, y, angle, back) for x, y in local_pads(fpid).values()]
    return box, ((min(p[0] for p in pp) + max(p[0] for p in pp)) / 2, (min(p[1] for p in pp) + max(p[1] for p in pp)) / 2)


class Hub(pk.Board):
    def __init__(self, name, force):
        super().__init__(name, force)
        self.taken = []          # rectangles (x0, y0, x1, y1) in KiCad mm that packed parts must avoid
        self.errors = []

    def place(self, ref, x, y, angle=0.0, back=False):
        fp = super().place(ref, x, y, angle, back)
        if self.comps[ref].get("dnp"):
            fp.SetDNP(True)
        return fp

    def by_value(self, text):
        got = [r for r, c in self.comps.items() if text in c["value"]]
        if len(got) != 1:
            sys.exit(f"{self.name}: part with value '{text}': {got}")
        return got[0]

    def fix(self, ref, hx, hy, angle=0.0, back=False, by="pads", keep=True):
        """Part at hub coordinates: its pad pattern's centre (by='pads'), bounding-box centre ('box') or origin ('origin')."""
        box, pc = measure(self.comps[ref]["fp"], angle, back)
        cx, cy = {"pads": pc, "box": ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), "origin": (0.0, 0.0)}[by]
        x, y = K(hx, hy)
        self.place(ref, x - cx, y - cy, angle, back)
        if keep and not back:
            self.taken.append((x - cx + box[0] - GAP, y - cy + box[1] - GAP, x - cx + box[2] + GAP, y - cy + box[3] + GAP))
        return self.placed[ref]

    def hole(self, hx, hy):
        x, y = K(hx, hy)
        self.mech(pk.HOLE_FP, "H", x, y)
        self.taken.append((x - 3.0, y - 3.0, x + 3.0, y + 3.0))       # screw head and boss

    def outline(self, y_front, x1=g.BOARD / 2, y_rear=g.BOARD / 2):
        c = [K(-x1, y_front), K(x1, y_front), K(x1, y_rear), K(-x1, y_rear)]
        for a, b in zip(c, c[1:] + c[:1]):
            self.line(a, b)

    def pack(self, refs, zone):
        """Bottom-left fill of `refs` (largest first) into zone = hub (x0, x1, y0, y1), from the rear towards the front."""
        zx0, zy0 = K(zone[0], zone[3])
        zx1, zy1 = K(zone[1], zone[2])
        sized = []
        for ref in refs:
            box, _ = measure(self.comps[ref]["fp"], 0, False)
            sized.append((ref, box))
        for ref, box in sorted(sized, key=lambda s: -(s[1][2] - s[1][0]) * (s[1][3] - s[1][1])):
            w, h = box[2] - box[0] + GAP, box[3] - box[1] + GAP
            spot, y = None, zy0
            while spot is None and y + h <= zy1 + 1e-6:
                x = zx0
                while x + w <= zx1 + 1e-6:
                    hit = [t for t in self.taken if x < t[2] and x + w > t[0] and y < t[3] and y + h > t[1]]
                    if not hit:
                        spot = (x, y)
                        break
                    x = max(t[2] for t in hit) + 1e-3
                y += STEP
            if spot is None:
                self.errors.append(f"{ref} does not fit in zone {zone}")
                continue
            x, y = spot
            self.place(ref, x + GAP / 2 - box[0], y + GAP / 2 - box[1])
            self.taken.append((x, y, x + w, y + h))

    def put(self, ref, x, y, angle=0.0, pad=None):
        """Part at KiCad x, y by its origin, or by one of its pads when `pad` is given; its box is kept free."""
        box, _ = measure(self.comps[ref]["fp"], angle, False)
        if pad is not None:
            dx, dy = turn(*local_pads(self.comps[ref]["fp"])[pad], angle, False)
            x, y = x - dx, y - dy
        self.place(ref, x, y, angle)
        self.taken.append((x + box[0] - GAP / 2, y + box[1] - GAP / 2, x + box[2] + GAP / 2, y + box[3] + GAP / 2))
        return x, y

    def sel(self, prefix, *nets, placed=False):
        """The one part with this reference prefix that has all of these nets."""
        got = [r for r, c in self.comps.items() if r.rstrip("0123456789") == prefix
               and set(nets) <= {n.lstrip("/") for n in c["nets"].values()} and (placed or r not in self.placed)]
        if len(got) != 1:
            sys.exit(f"{self.name}: {prefix} with nets {nets}: {got}")
        return got[0]

    def vals(self, group, value, net):
        return sorted((r for r, c in self.comps.items() if c["fields"].get("Group") == group and c["value"] == value
                       and "/" + net in c["nets"].values()), key=lambda r: int(r[1:]))

    def pack_k(self, refs, zones, gap=GAP, gap_ic=None):
        """Fill `refs` (largest first) into the first of `zones` (KiCad x0, y0, x1, y1) that has room, row by row;
        a part that fits nowhere as it lies is tried turned by 90 degrees."""
        sized = [(ref, measure(self.comps[ref]["fp"], 0, False)[0]) for ref in refs]
        gap_rc = gap
        for ref, box0 in sorted(sized, key=lambda s: -(s[1][2] - s[1][0]) * (s[1][3] - s[1][1])):
            spot = None
            gap = gap_ic if gap_ic and ref[0] in "QUD" else gap_rc      # small-pitch parts need room for their tracks and vias
            for angle in (0, 90):
                box = box0 if angle == 0 else measure(self.comps[ref]["fp"], 90, False)[0]
                w, h = box[2] - box[0] + gap, box[3] - box[1] + gap
                for zx0, zy0, zx1, zy1 in zones:
                    y = zy0
                    while spot is None and y + h <= zy1 + 1e-6:
                        x = zx0
                        while x + w <= zx1 + 1e-6:
                            hit = [t for t in self.taken if x < t[2] and x + w > t[0] and y < t[3] and y + h > t[1]]
                            if not hit:
                                spot = (x, y)
                                break
                            x = max(t[2] for t in hit) + 1e-3
                        y += STEP
                    if spot:
                        break
                if spot:
                    break
            if spot is None:
                self.errors.append(f"{ref} does not fit in {zones}")
                continue
            x, y = spot
            self.place(ref, x + gap / 2 - box[0], y + gap / 2 - box[1], angle)
            self.taken.append((x, y, x + w, y + h))

    def group(self, name):
        return [r for r, c in self.comps.items() if c["fields"].get("Group") == name and r not in self.placed]

    def pads(self, ref):
        return {p.GetNumber(): (round(pcbnew.ToMM(p.GetPosition().x), 3), round(pcbnew.ToMM(p.GetPosition().y), 3))
                for p in self.placed[ref].Pads() if p.GetNumber()}

    def save(self):
        missing = sorted(set(self.comps) - set(self.placed))
        if missing:
            self.errors.append(f"not placed: {missing}")
        pcbnew.SaveBoard(str(self.path), self.b)
        d = pk.HW / self.name
        ports = " || ".join(f"A.memberOfFootprint('{r}')" for r, c in self.comps.items() if "12401548" in c["fp"] or "USB4085" in c["fp"])
        (d / f"{self.name}.kicad_dru").write_text(DRU + (DRU_PORTS.format(ports=ports) if ports else ""))
        p = d / f"{self.name}.kicad_pro"
        pro = json.loads(p.read_text())
        pro.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rules", {}).update(pk.RULES)
        pro.setdefault("net_settings", {})["classes"] = [pk.DEFAULT_CLASS, pk.POWER_CLASS, pk.GND_CLASS]
        if self.name in CLASSES:
            pro["net_settings"]["classes"] = CLASSES[self.name]
        pro["net_settings"]["netclass_patterns"] = [{"netclass": c, "pattern": n} for n, c in CLASS_OF.items()]
        p.write_text(json.dumps(pro, indent=2) + "\n")
        print(f"{self.name}: {len(self.placed)} schematic parts + {self.extra} holes placed")
        for e in self.errors:
            print("ERROR", self.name, e)
        return not self.errors


def strip_pattern():
    """Pin n -> KiCad x, y of the spring-pin strip on the cap board: a PinHeader_2x08 pattern, top side, at CHAIN_PADS_XY."""
    fpid = "Connector_PinHeader_2.54mm:PinHeader_2x08_P2.54mm_Vertical"
    _, pc = measure(fpid, 90, False)
    x, y = K(*g.CHAIN_PADS_XY)
    return {n: (round(x - pc[0] + turn(*q, 90, False)[0], 3), round(y - pc[1] + turn(*q, 90, False)[1], 3))
            for n, q in local_pads(fpid).items()}


def targets(bd, ref):
    """Chain target pads on the underside, turned so that pad n is over strip pin n (tested on the placed footprint)."""
    want = strip_pattern()
    fpid = bd.comps[ref]["fp"]
    x, y = K(*g.CHAIN_PADS_XY)
    for angle in (90, 270):
        _, pc = measure(fpid, angle, True)
        got = {n: (x - pc[0] + turn(*q, angle, True)[0], y - pc[1] + turn(*q, angle, True)[1]) for n, q in local_pads(fpid).items()}
        if all(abs(got[n][0] - want[n][0]) < 0.01 and abs(got[n][1] - want[n][1]) < 0.01 for n in want):
            bd.fix(ref, *g.CHAIN_PADS_XY, angle=angle, back=True)
            if bd.pads(ref) != want:
                bd.errors.append(f"chain target pads are not over the strip pins: {bd.pads(ref)} / {want}")
            return angle
    bd.errors.append("chain target pads: no turn puts pad n over strip pin n")


def pico_tp(bd, ref):
    """KiCad x, y of TP2, TP3, TP6 under the placed Pico footprint (from the stock Pico W SMD footprint, same outline)."""
    smd = pk.load_fp("Module:RaspberryPi_Pico_W_SMD")
    sp = {p.GetNumber(): (pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y)) for p in smd.Pads()}
    cx = sum(sp[n][0] for n in ("1", "20", "21", "40")) / 4
    cy = sum(sp[n][1] for n in ("1", "20", "21", "40")) / 4
    if not (sp["1"][0] < cx and sp["1"][1] < cy and sp["40"][0] > cx and sp["20"][1] > cy):
        sys.exit("Pico W SMD footprint: unexpected pin arrangement")
    p = bd.pads(ref)
    ex = ((p["40"][0] - p["1"][0]) / 17.78, (p["40"][1] - p["1"][1]) / 17.78)
    ey = ((p["20"][0] - p["1"][0]) / 48.26, (p["20"][1] - p["1"][1]) / 48.26)
    out = {}
    for tp in ("TP2", "TP3", "TP6"):
        fx, fy = sp[tp][0] - cx + 8.89, sp[tp][1] - cy + 24.13            # in the THT footprint's frame (origin = pin 1)
        out[tp] = (p["1"][0] + ex[0] * fx + ey[0] * fy, p["1"][1] + ex[1] * fx + ey[1] * fy)
    return out


def hub_core(force):
    bd = Hub("hub-core", force)
    bd.outline(g.CORE_FRONT_Y)
    for x, y in g.CORE_XY:
        bd.hole(x, y)
    bd.fix(bd.by_value("STACK"), *g.STACK_XY, angle=90)
    bd.fix(bd.by_value("EXPANSION"), *g.EXP_XY, angle=90)
    pico = bd.by_value("Pico 2 W")
    bd.fix(pico, *g.PICO_XY, angle=270)                    # USB end towards +x, antenna end towards the -x wall
    p = bd.pads(pico)
    if not p["1"][0] > p["20"][0]:
        bd.errors.append("Pico: USB end is not towards +x")
    tps = pico_tp(bd, pico)
    for tp, (x, y) in tps.items():
        bd.fix(bd.by_value(f"Pico {tp}"), x - X0, Y0 - y, by="origin")
    usb_x = max(x for x, _ in tps.values()) - X0
    for (name, x), text in zip(g.BUTTONS, ("POWER (", "RESET (", "BOOT (")):
        bd.fix(bd.by_value(text), x, g.BUTTON_PLUG_Y, angle=180)       # XH latch wall towards the rear, wires leave to the front
    bd.pack(bd.group("misc"), (-40.0, 40.0, -19.5, -6.0))
    print(f"hub-core: Pico centre {g.PICO_XY}, spring pins at hub x, y: "
          + ", ".join(f"{t} ({x - X0:.2f}, {Y0 - y:.2f})" for t, (x, y) in tps.items()) + f"; USB end at x = {usb_x:.1f}")
    return bd


# ---- hub-conn arrangement (M2 session 5). KiCad mm; the same numbers are read by tools/route_hub.py. ----------------
CONV = (66.7, 94.8)                 # TPS552892, turned 180: VIN strip east, VOUT west, capacitor row north, inductor south
COL_X0, COL_W, COL_Y0, COL_Y1 = 81.0, 13.1, 86.0, 113.4      # five pack-input columns
COL_PACK = (3, 2, 1, 4, 5)          # pack input in each column, west to east (order set by the chain comb, route_hub.py)
ST_ENTRY = (10.2, 1.4)              # in a column: PACK vias; the SO-8 below them, the priority FET below that, VBAT vias
ST_VBAT_Y = 15.3
STAGE_GAP_IC = 0.5        # more shuts a supervisor's GND pin in (no room for its via)
TRUNK_Y = 114.5                     # +5V trunk on In2, west to east in front of the pack columns
PLUG_ZONE = (64.3, 60.0, 70.6, 77.5)                         # the host-port cable plug slides in here: no parts


def stage(bd, col, n):
    """One pack input, top to bottom: TVS and entry vias, ideal-diode FET (source north) with its controller, priority FET, VBAT."""
    x0, y0 = COL_X0 + COL_W * col, COL_Y0
    bd.put(bd.sel("D", f"PACK{n}", "GND"), x0 + 3.4, y0 + 1.5, 180)
    bd.put(bd.sel("Q", f"IDG{n}", f"PACK{n}"), x0 + 10.2, y0 + 6.5, 270)
    bd.put(bd.sel("U", f"CPL{n}"), x0 + 2.6, y0 + 6.8, 270)
    bd.put(bd.sel("C", f"CPH{n}"), x0 + 5.9, y0 + 6.8, 90)
    if n < 5:
        bd.put(bd.sel("Q", f"PG{n}", "VBAT"), x0 + 10.9, y0 + 12.4, 270)
    bd.taken += [(x0 + 4.9, y0, x0 + COL_W, y0 + 2.9),                                    # PACK copper and vias
                 (x0 + 8.6, y0 + 13.6, x0 + COL_W, y0 + ST_VBAT_Y + 1.1)]                 # VBAT copper and vias
    bleed = [r for r in bd.group(f"pack{n}") if f"/BLD{n}" in bd.comps[r]["nets"].values()]    # goes to the rear, beside its FET
    bd.pack_k([r for r in bd.group(f"pack{n}") if r not in bleed], [(x0 + 0.2, y0 + 0.2, x0 + COL_W - 0.1, COL_Y1)], gap_ic=STAGE_GAP_IC)


def port(bd, p, px):
    """Module port: ESD arrays and series resistors behind the receptacle, buffer behind them, source switch at its east side."""
    bd.fix(bd.by_value(f"MODULE PORT {p}"), px - X0, -g.BOARD / 2 + RECEPTACLE_EDGE, by="origin")
    bd.put(bd.sel("U", f"SCK_{p}", f"CSO_{p}"), px - 3.4, 131.6, 90)        # 4.3 mm behind the A row: its signals need their vias there
    bd.put(bd.sel("U", f"CC1_{p}", f"INTO_{p}"), px + 3.4, 131.6, 90)
    for i, net in enumerate((f"SCKB_{p}", f"MOSIB_{p}", f"CSB_{p}", f"INT_{p}", f"LEDB_{p}")):
        bd.put(bd.sel("R", net), px - 4.6 + 2.3 * i, 127.0, 90)
    bd.put(bd.sel("U", f"SCKB_{p}"), px - 1.0, 120.3, 90)
    bd.put(bd.sel("U", f"REF_{p}"), px + 9.9, 131.5, 180)
    bd.taken += [(px + 5.8, 131.2, px + 7.6, 136.6), (px + 11.6, 130.3, px + 13.8, 132.7),      # VBUS and +5V copper and vias
                 (px + 10.1, 127.9, px + 12.0, 129.4)]
    side = [(px + 5.6, 123.5, px + 13.9, 146.4), (px - 13.9, 116.4, px + 13.9, 137.0), (px - 13.9, 137.0, px - 5.6, 146.4)]
    bd.pack_k(bd.group(f"port{p}"), side, gap=0.9)


def hub_conn(force):
    bd = Hub("hub-conn", force)
    bd.b.SetCopperLayerCount(4)
    bd.outline(g.CONN_FRONT, g.CONN_X, g.CONN_REAR)       # 108 x 108 since the tower grew (user, 2026-11-14); parts stay where they were
    for x, y in g.MOUNT_XY + g.UP_MOUNT_XY:               # the last two carry the host port board's standoffs
        bd.hole(x, y)
    bd.fix(bd.by_value("STACK"), *g.STACK_XY, angle=90)
    bd.fix(bd.by_value("J_USB"), *g.JUSB_XY, angle=90, by="box")
    turn = targets(bd, bd.by_value("CHAIN"))
    bd.taken += [PLUG_ZONE, (111.5, 66.6, 133.0, 68.2), (111.5, 73.6, 133.0, 76.4)]     # plug; chain via rows north and south
    # 5 V converter, as the TPS552892 datasheet's layout: capacitors at the VIN and VOUT strips with PGND between them,
    # inductor on the other side with the boot capacitors at the switch strips, VCC capacitor at its pin
    ix, iy = CONV
    bd.put(bd.sel("U", "FSW"), ix, iy, 180)
    bd.put(bd.sel("L", "L1"), ix, iy + 8.5, 180)
    for ref, dx in zip(bd.vals("conv", "100n", "SYS") + bd.vals("conv", "10u", "SYS") + bd.vals("conv", "47u", "SYS")[:2],
                       (1.3, 3.4, 6.2, 9.7)):
        bd.put(ref, ix + dx, iy - 3.4, 90, pad="1")
    for ref, dx in zip(bd.vals("conv", "100n", "+5V") + bd.vals("conv", "22u", "+5V"), (-1.5, -4.3, -7.8, -11.3)):
        bd.put(ref, ix + dx, iy - 3.4, 90, pad="1")
    bd.put(bd.sel("C", "BOOT1"), ix + 2.0, iy + 3.15, 180)
    bd.put(bd.sel("C", "BOOT2"), ix - 2.0, iy + 3.15, 0)
    bd.put(bd.sel("C", "VCC5"), ix - 6.5, iy + 0.3, 180)
    bd.put(bd.sel("R", "FSW"), ix + 5.95, iy - 1.2, 0)
    bd.put(bd.sel("R", "CONV_EN", "GND"), ix + 5.95, iy + 1.0, 0)
    bd.put(bd.sel("R", "CONV_EN", "SYS"), ix + 5.95, iy + 3.2, 180)
    bd.taken += [(53.5, iy - 2.6, 57.9, iy - 0.9), (53.5, 85.9, 78.2, 87.6)]              # +5V vias; PGND vias
    bd.pack_k(bd.group("conv")[:0] + [r for r in bd.group("conv") if bd.comps[r]["value"] not in ("47u", "220u")],
              [(53.7, iy - 0.8, 58.0, 113.0), (53.7, iy + 13.0, 78.0, 113.0)])
    # USB and battery switches around the SYS node, bulk capacitors beside it
    c35, c45 = bd.vals("conv", "220u", "SYS")[0], bd.vals("conv", "220u", "+5V")[0]
    bd.put(c35, 73.0, 81.2, 180)
    c31, c32 = bd.vals("conv", "47u", "SYS")[2:]
    bd.put(c31, 74.3, 74.6, 180)
    bd.put(c32, 74.3, 70.9, 180)
    bd.put(bd.sel("Q", "VBUS_IN", "SYS"), 79.0, 74.0, 270)
    bd.put(bd.sel("Q", "QB_G", "SYS"), 83.5, 81.5, 0)
    bd.put(c45, 59.5, 128.0, 180)
    bd.taken += [(78.2, 67.4, 81.0, 92.2), (84.8, 79.8, 88.6, 83.2), (60.8, 124.9, 65.2, 126.6),
                 (53.5, 61.5, 57.5, 76.5)]                                                # SYS trunk, VBUS_IN vias; VBAT; C45 vias; VBUS_IN bar
    for col, n in enumerate(COL_PACK):
        stage(bd, col, n)
    for p, x in zip("ABC", g.PORT_X):
        port(bd, p, X0 + x)
    rear = [(81.5, 62.4, 111.3, 79.4), (89.5, 79.4, 111.3, 85.7), (133.3, 62.4, 146.6, 76.6), (112.0, 62.4, 133.0, 66.3),
            (70.8, 62.4, 78.0, 68.8), (58.5, 108.0, 78.0, 113.3),
            (COL_X0 + 2 * COL_W + 0.3, 103.5, COL_X0 + 3 * COL_W - 0.2, COL_Y1), (COL_X0 + 4 * COL_W + 0.3, 103.5, 146.5, COL_Y1)]
    for name in ("switch", "misc", "sense", "pack2", "pack3", "pack4", "pack5"):      # of the packs only the bleeders are left
        bd.pack_k(bd.group(name), rear, gap=0.85, gap_ic=1.6)            # room between the small parts for the autorouter
    print(f"hub-conn: chain target pads turned {turn} deg, on the underside")
    return bd


def battery(force):
    bd = Hub("battery", force)
    bd.outline(-g.BOARD / 2)
    for x, y in g.MOUNT_XY:
        bd.hole(x, y)
    bd.fix(bd.by_value("4xAA"), *g.HOLDER_XY, by="box")
    bd.fix(bd.by_value("CHAIN UP"), *g.CHAIN_RISER_XY, angle=90)
    turn = targets(bd, bd.by_value("CHAIN DOWN"))
    bd.fix(bd.by_value("MF-LSMF500"), -2.0, 21.0, by="box")
    print(f"battery: chain target pads turned {turn} deg, on the underside")
    return bd


def chain_cap(force):
    """Cap board of the chain seam: on the battery board's riser, carries the spring-pin strip. Same x, y as the tower."""
    bd = Hub("chain-cap", force)
    (w, h), cx, cy = g.CAP_BOARD, g.CHAIN_RISER_XY[0], (g.CHAIN_RISER_XY[1] + g.CHAIN_PADS_XY[1]) / 2
    c = [K(cx - w / 2, cy - h / 2), K(cx + w / 2, cy - h / 2), K(cx + w / 2, cy + h / 2), K(cx - w / 2, cy + h / 2)]
    for a, b in zip(c, c[1:] + c[:1]):
        bd.line(a, b)
    bd.fix(bd.by_value("RISER"), *g.CHAIN_RISER_XY, angle=90)
    bd.fix(bd.by_value("SPRING PINS"), *g.CHAIN_PADS_XY, angle=90)
    if bd.pads(bd.by_value("SPRING PINS")) != strip_pattern():
        bd.errors.append("spring pins are not where the target pads expect them")
    return bd


BUILD = {"hub-core": hub_core, "hub-conn": hub_conn, "battery": battery, "chain-cap": chain_cap}


def main():
    names = [a for a in sys.argv[1:] if not a.startswith("--")] or list(BUILD)
    ok, boards = True, {}
    for name in names:
        boards[name] = BUILD[name]("--force" in sys.argv)
    if "hub-core" in boards and "hub-conn" in boards:
        a = boards["hub-core"].pads(boards["hub-core"].by_value("STACK"))
        b = boards["hub-conn"].pads(boards["hub-conn"].by_value("STACK"))
        if a != b:
            boards["hub-core"].errors.append("stack: core and connector layer pins are not above each other")
        else:
            print("stack 2x25: pin n above pin n on core and connector layer")
    if "hub-conn" in boards and "battery" in boards:
        a = boards["hub-conn"].pads(boards["hub-conn"].by_value("CHAIN"))
        b = boards["battery"].pads(boards["battery"].by_value("CHAIN DOWN"))
        print("chain 2x8: target pads identical under connector layer and battery board:", a == b)
        ok &= a == b
    if "battery" in boards and "chain-cap" in boards:
        same = boards["battery"].pads(boards["battery"].by_value("CHAIN UP")) == boards["chain-cap"].pads(boards["chain-cap"].by_value("RISER"))
        print("chain 2x8: cap board holes over the riser pins of the battery board:", same)
        ok &= same
    for bd in boards.values():
        ok &= bd.save()
    sys.stdout.flush()
    os._exit(0 if ok else 1)


if __name__ == "__main__":
    main()
