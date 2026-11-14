#!/usr/bin/env python3
"""Place the port boards (M2 step 1): port-module (the module-side port board in every key board's rear bay).

Run with KiCad's Python (KiCad closed):
    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 tools/pcb_port.py [--force] [board ...]
Routing: tools/route_hub.sh port-module (places, routes and checks until clean).

port-module, 4 copper layers (user, 2026-11-14; as hub-conn: F parts and signals, In1 GND plane, In2 power and
signals, B signals). Seen from above, in the bay frame of tools/pcb_keys.py BAY (a along the rear edge, t rearwards
from the F-row cap line, origin on the bay centre line); KiCad x = 100 + a, y = 100 - t:
- outline a -15 .. 15, t FRONT .. 25 (the key board's rear edge), 1 mm fillets;
- two M2 holes at BAY["screws"] (off-centre: the board cannot go on turned round);
- J2, the 2x6 socket, on the UNDERSIDE over the key board's header (mirror rule in next.md: PinSocket flipped puts
  pin 1 on pin 1); checked here pad by pad against the bay header and holes of the three routed key boards;
- J1, the Amphenol 12401548E4-2A, mouth to the rear, origin RECEPTACLE_EDGE inside the rear edge (pcb_hub.py),
  midway between the screws; ESD arrays to its left and right, the regulator and the TVS at the +5V end of the
  header, pull-ups and the CS filter in the strip in front of the header. All SMD parts on top.
"""
import math
import os
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pcb_keys as pk  # noqa: E402
import pcb_hub as ph  # noqa: E402

FRONT = 1.5                      # front edge of the port board, t
REC_A = (pk.BAY["screws"][0][0] + pk.BAY["screws"][1][0]) / 2     # receptacle centre line: midway between the screws
HDR_PITCH = 2.54


def P(a, t):
    return 100.0 + a, 100.0 - t


def header_bay():
    """Bay coordinates of the key board's header pins: PinHeader_2x06 turned as pcb_keys.py places it, its box centred
    on BAY["header"]. Odd pins in the front row, pin 1 at the -a end."""
    hx, ht = pk.BAY["header"]
    return {str(n): (hx + (-(2.5) + (n - 1) // 2) * HDR_PITCH, ht + (-0.5 if n % 2 else 0.5) * HDR_PITCH) for n in range(1, 13)}


def check_key_boards(want):
    """The three key boards as they are on disk: their bay header pins and bay screws, brought into the bay frame by
    the two screw holes, must sit where this board has its socket pins and holes (seen from above, not mirrored)."""
    ok = True
    (aw, tw), (ae, te) = pk.BAY["screws"]
    for name in ("left", "right", "numpad"):
        b = pcbnew.LoadBoard(str(pk.HW / name / f"{name}.kicad_pcb"))
        j = next(f for f in b.GetFootprints() if f.GetValue() == "BAY")
        pads = {p.GetNumber(): (pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y)) for p in j.Pads()}
        holes = [(pcbnew.ToMM(f.GetPosition().x), pcbnew.ToMM(f.GetPosition().y)) for f in b.GetFootprints()
                 if "MountingHole" in str(f.GetFPID().GetLibItemName())]
        cx, cy = pads["5"]
        near = sorted(holes, key=lambda h: math.hypot(h[0] - cx, h[1] - cy))[:2]
        worst = None
        for hw, he in (near, near[::-1]):
            d = math.hypot(he[0] - hw[0], he[1] - hw[1])
            ea = ((he[0] - hw[0]) / d, (he[1] - hw[1]) / d)
            et = (ea[1], -ea[0])                    # rearwards: 90 degrees to the left of a, seen from above (y down)
            o = (hw[0] - aw * ea[0] - tw * et[0], hw[1] - aw * ea[1] - tw * et[1])
            err = max(math.hypot((x - o[0]) * ea[0] + (y - o[1]) * ea[1] - want[n][0],
                                 (x - o[0]) * et[0] + (y - o[1]) * et[1] - want[n][1]) for n, (x, y) in pads.items())
            err = max(err, abs(d - (ae - aw)))
            worst = err if worst is None else min(worst, err)
        print(f"bay of {name}: header pins and screws against the port board, worst offset {worst:.3f} mm")
        ok &= worst < 0.05
    return ok


def port_module(force):
    bd = ph.Hub("port-module", force)
    bd.b.SetCopperLayerCount(4)
    half = pk.BAY["width"] / 2
    c = [(-half, FRONT), (half, FRONT), (half, pk.REAR), (-half, pk.REAR)]
    r = 1.0
    for i, (a, t) in enumerate(c):                  # outline with 1 mm fillets
        (a2, t2) = c[(i + 1) % 4]
        ux, uy = (a2 - a) / math.hypot(a2 - a, t2 - t), (t2 - t) / math.hypot(a2 - a, t2 - t)
        bd.line(P(a + ux * r, t + uy * r), P(a2 - ux * r, t2 - uy * r))
        (a3, t3) = c[(i + 2) % 4]
        vx, vy = (a3 - a2) / math.hypot(a3 - a2, t3 - t2), (t3 - t2) / math.hypot(a3 - a2, t3 - t2)
        m = (a2 - (ux - vx) * r * (1 - math.sqrt(0.5)), t2 - (uy - vy) * r * (1 - math.sqrt(0.5)))
        bd.arc(P(a2 - ux * r, t2 - uy * r), P(*m), P(a2 + vx * r, t2 + vy * r))
    for a, t in pk.BAY["screws"]:
        x, y = P(a, t)
        bd.mech(pk.HOLE_FP, "H", x, y)
    # socket on the underside: flipped and turned so that pin n lands on header pin n
    want = header_bay()
    j2 = bd.by_value("BAY (socket)")
    bd.place(j2, *P(*want["1"]), 270, back=True)
    got = {n: (round(x - 100, 3), round(100 - y, 3)) for n, (x, y) in bd.pads(j2).items()}
    if any(math.hypot(got[n][0] - want[n][0], got[n][1] - want[n][1]) > 0.005 for n in want):
        bd.errors.append(f"socket pins are not over the header pins: {got}")
    if not check_key_boards(want):
        bd.errors.append("the key boards' bays do not match this board")
    # receptacle: mouth to the rear
    j1 = bd.by_value("USB-C 24P")
    bd.place(j1, *P(REC_A, pk.REAR - ph.RECEPTACLE_EDGE), 180)
    a1 = bd.pads(j1)["A1"]
    if abs(a1[1] - (100 - (pk.REAR - ph.RECEPTACLE_EDGE - 5.02))) > 0.01 or abs(a1[0] - (100 + REC_A + 2.75)) > 0.01:
        bd.errors.append("receptacle: the A row does not face the header")
    # the rest, by net: (prefix, nets, a, t, angle)
    for prefix, nets, a, t, angle in PARTS:
        bd.place(bd.sel(prefix, *nets), *P(a, t), angle)
    return bd


# a, t of each part's origin. Local x of the receptacle = REC_A - a: its A row carries, from -a to +a,
# SCK . +5V LED INT CS CC1 +5V MISO MOSI; the header carries +5V at -6.35, LED -3.81, +3V3 -1.27, INT / CS 1.27,
# MISO / MOSI 3.81, SCK 6.35.
PARTS = [
    ("U", ("INT", "LED_DIN", "CC1", "CC2"), -12.2, 13.9, 0),     # ESD array, CC2 comes round the receptacle's west end
    ("U", ("SCK", "MOSI", "MISO_CONN", "CS_CONN"), 7.3, 13.7, 0),
    ("U", ("+5V", "+3V3"), -11.5, 7.2, 0),                       # regulator beside the header's +5V pins
    ("D", ("+5V", "GND"), -9.0, 10.1, 0),                        # VBUS TVS
    ("C", ("+5V", "GND"), -11.5, 3.3, 0),
    ("C", ("+3V3", "GND"), -7.4, 3.3, 0),
    ("R", ("+3V3", "INT"), 0.0, 3.3, 0),                         # between header pins 5 (+3V3) and 7 (INT)
    ("R", ("+3V3", "CS"), 4.2, 3.3, 180),
    ("C", ("CS", "GND"), 8.2, 3.3, 180),
    ("R", ("CS_CONN", "CS"), 0.8, 11.1, 0),
    ("R", ("CC1", "GND"), -3.4, 11.1, 180),
    ("R", ("MISO", "MISO_CONN"), 5.0, 10.4, 0),
    ("R", ("CC2", "GND"), -8.0, 15.0, 90),
]

BUILD = {"port-module": port_module}


def main():
    names = [a for a in sys.argv[1:] if not a.startswith("--")] or list(BUILD)
    ok = True
    for name in names:
        ok &= BUILD[name]("--force" in sys.argv).save()
    sys.stdout.flush()
    os._exit(0 if ok else 1)


if __name__ == "__main__":
    main()
