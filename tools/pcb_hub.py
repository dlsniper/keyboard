#!/usr/bin/env python3
"""Place the hub boards (M2 step 1): hub-core, hub-conn, battery. Outline, footprints, nets, holes, rules.

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

    def outline(self, y_front):
        c = [K(-g.BOARD / 2, y_front), K(g.BOARD / 2, y_front), K(g.BOARD / 2, g.BOARD / 2), K(-g.BOARD / 2, g.BOARD / 2)]
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
        ports = " || ".join(f"A.memberOfFootprint('{r}')" for r, c in self.comps.items() if "MODULE PORT" in c["value"])
        (d / f"{self.name}.kicad_dru").write_text(DRU + (DRU_PORTS.format(ports=ports) if ports else ""))
        p = d / f"{self.name}.kicad_pro"
        pro = json.loads(p.read_text())
        pro.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rules", {}).update(pk.RULES)
        pro.setdefault("net_settings", {})["classes"] = [pk.DEFAULT_CLASS, pk.POWER_CLASS, pk.GND_CLASS]
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


def hub_conn(force):
    bd = Hub("hub-conn", force)
    bd.outline(-g.BOARD / 2)
    for x, y in g.MOUNT_XY:
        bd.hole(x, y)
    bd.fix(bd.by_value("STACK"), *g.STACK_XY, angle=90)
    bd.fix(bd.by_value("J_USB"), *g.JUSB_XY, angle=90, by="box")
    turn = targets(bd, bd.by_value("CHAIN"))
    for p, x in zip("ABC", g.PORT_X):
        bd.fix(bd.by_value(f"MODULE PORT {p}"), x, -g.BOARD / 2 + RECEPTACLE_EDGE, by="origin")    # opening towards the front edge
    edges = (-45.5, -14.0, 14.0, 45.5)
    for i, p in enumerate("ABC"):
        bd.pack(bd.group(f"port{p}"), (edges[i] + 0.2, edges[i + 1] - 0.2, -37.5, -18.5))
    left = (-46.0, 2.0, -17.5, 37.0)
    for name in ("misc", "pack1", "pack2", "pack3", "pack4", "pack5", "sense", "switch"):
        bd.pack(bd.group(name), left)
    bd.pack(bd.group("conv"), (3.0, 46.0, -17.5, 36.5))
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


BUILD = {"hub-core": hub_core, "hub-conn": hub_conn, "battery": battery}


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
    for bd in boards.values():
        ok &= bd.save()
    sys.stdout.flush()
    os._exit(0 if ok else 1)


if __name__ == "__main__":
    main()
