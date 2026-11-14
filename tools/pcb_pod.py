#!/usr/bin/env python3
"""Place the three wireless boards of spec section 2b (M3b session 3): pod, pod-power, hub-radio.

Run with KiCad's Python:
    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 tools/pcb_pod.py [--force] [board ...]
Routing: tools/route_hub.sh pod | pod-power | hub-radio (places, routes and checks until clean).
`--check` on routed boards: antenna keep-out of the pod free of copper on every layer, mating pins again.

pod, 4 copper layers (F parts and signals, In1 GND plane, In2 and B signals), 30 x 50.7 mm (user, 2026-11-14: straight
to the rear, over the battery rail). Bay frame of tools/pcb_keys.py BAY as the port board (a along the rear edge,
t rearwards from the F-row cap line; KiCad x = 100 + a, y = 100 - t):
- outline a -15 .. 15, t 1.5 .. POD_REAR; the key board ends at t 25, the tray's rear wall at 27.7, the rail's rear
  face (27 mm rail) at 54.7; the board ends 2.51 mm inside that face so that the USB-C shell ends flush with it;
- two M2 holes at BAY["screws"], the 2x6 socket J1 on the UNDERSIDE over the key board's header (checked against
  the three routed key boards, as the port board);
- U1 (MDBT50Q-1MV2) with its antenna end on the rear edge, 2.7 mm from the east edge (the pads of its east column
  leave eastwards); the footprint's own rule area keeps copper out under the antenna on every layer;
- J3 (USB-C service port) at the rear edge, west; its ESD array and the CC resistors in front of it;
- J2 (lead to the power board) on the west side over the rail, mouth to the west: the lead drops past the board
  edge into the rail;
- crystal, decoupling, USB regulator parts and series resistors in three rows in front of the module;
- over the bay: level shifter, debug header, reset button, status LED. All SMD parts on top.

pod-power, 4 copper layers, 48 x 22 mm (user: rear leg of the rail 27 mm deep), own frame: KiCad x 100 .. 148 from
the west end, y 100 (rear wall of the rail) .. 122 (front, towards the tray). West end: pack plug J1 (mouth to the
west, into the wiring channel beside the rear cell), fuse, reverse FET, 47 uF can; slide switch on the rear edge
(actuator through the rail's rear wall); 3.3 V converter east, 5 V converter and LED rail cap front middle,
lead J2 (vertical: plugged from above) rear east. The front-east corner (15.5 x 6.6 mm) is cut away: on the numpad the
three side cells and their contact end there. The front-west corner (4 x 13 mm) is cut away too: the rear cell's
spring contact and its wall stand there (found at the shell step: the lane was 3.9 mm short). Two M2 holes on the front edge (the east end rests on printed posts).

hub-radio, 2 layers, in hub coordinates (pcb_hub.K): socket J1 on the UNDERSIDE over hub-core's expansion header
(checked pad by pad against the routed hub-core), bay header J2 and two M2 holes as a key board's bay, turned by
180 degrees: the pod points to the FRONT of the tower (its rear end would hit the rear wall the other way), above
the Pico; the carrier itself stays behind the Pico and steps round the stack connector.
"""
import math
import os
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pcb_keys as pk  # noqa: E402
import pcb_hub as ph  # noqa: E402
import pcb_port as pp  # noqa: E402

USB_OVER = ph.g.USB4085_OVER          # shell beyond the board edge
RAIL_REAR_T = 54.7                    # rear face of the 27 mm rail in the bay frame (tray rear wall at 27.7)
POD_FRONT, POD_REAR = pp.FRONT, RAIL_REAR_T - USB_OVER - 0.01
HALF = pk.BAY["width"] / 2
MOD_IN = 0.3                          # module body inside the rear edge (review: its length tolerance is +0.2 mm)
MOD_A, MOD_T = 7.0, POD_REAR - 7.8 - MOD_IN   # module origin: body 10.6 x 15.6, antenna end on the rear edge
USB_A = -9.0                          # service port centre line
PW = (48.0, 22.0)                     # power board
# carrier in the hub: bay frame turned by 180 degrees, hub x = CAR_X - a, hub y = CAR_Y - t
CAR_X, CAR_Y = -39.5, 55.5
CAR_OUT = [(-52.0, 32.5), (-24.5, 32.5), (-24.5, 38.0), (-26.6, 38.0), (-26.6, 52.5), (-52.0, 52.5)]   # hub x, y


def P(a, t):
    return 100.0 + a, 100.0 - t


def rounded(bd, c, r=1.0):
    """Closed outline through the KiCad points c with fillets of r."""
    k = len(c)
    for i in range(k):
        (ax, ay), (bx, by), (cx, cy) = c[i], c[(i + 1) % k], c[(i + 2) % k]
        ux, uy = (bx - ax) / math.hypot(bx - ax, by - ay), (by - ay) / math.hypot(bx - ax, by - ay)
        vx, vy = (cx - bx) / math.hypot(cx - bx, cy - by), (cy - by) / math.hypot(cx - bx, cy - by)
        bd.line((ax + ux * r, ay + uy * r), (bx - ux * r, by - uy * r))
        q = r * (1 - math.sqrt(0.5))
        bd.arc((bx - ux * r, by - uy * r), (bx - (ux - vx) * q, by - (uy - vy) * q), (bx + vx * r, by + vy * r))


def pick(bd, prefix, value, *nets):
    got = [r for r, c in bd.comps.items() if r.rstrip("0123456789") == prefix and r not in bd.placed
           and (value is None or c["value"] == value) and set(nets) <= {n.lstrip("/") for n in c["nets"].values()}]
    same = {(bd.comps[r]["value"], tuple(sorted(n.lstrip("/") for n in bd.comps[r]["nets"].values()))) for r in got}
    if not got or len(same) != 1:               # several are fine when they are the same part on the same nets
        sys.exit(f"{bd.name}: {prefix} {value} with nets {nets}: {got}")
    return sorted(got, key=lambda r: int(r.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")))[0]


def mate(bd, ref, want, back, tol=0.01):
    """Place a pin header / socket so that every pin n lands on want[n] (KiCad mm): the angle is found, not assumed."""
    loc = ph.local_pads(bd.comps[ref]["fp"])
    for angle in (0, 90, 180, 270):
        if all(math.hypot(want["1"][0] + ph.turn(*loc[n], angle, back)[0] - want[n][0],
                          want["1"][1] + ph.turn(*loc[n], angle, back)[1] - want[n][1]) < tol for n in want):
            bd.place(ref, *want["1"], angle, back=back)
            got = bd.pads(ref)
            if any(math.hypot(got[n][0] - want[n][0], got[n][1] - want[n][1]) > tol for n in want):
                bd.errors.append(f"{ref}: placed pins are not on the mating pins")
            return angle
    bd.errors.append(f"{ref}: no orientation puts its pins on the mating pins (mirrored?)")


def place_all(bd, parts, to):
    for prefix, value, nets, x, y, angle in parts:
        bd.place(pick(bd, prefix, value, *nets), *to(x, y), angle)


# ---- pod -----------------------------------------------------------------------------------------------------------
# prefix, value (None = any), nets, a, t, angle
POD_PARTS = [
    ("U", "USBLC6-2SC6", (), USB_A, 41.5, 0),
    ("R", "5.1k", ("CC1",), -1.5, 45.5, 0),
    ("R", "5.1k", ("CC2",), -1.5, 47.3, 0),
    # row in front of the module (its front pad row is at t = MOD_T - 7.15): crystal at pins 17 / 18, decoupling at 28 / 30
    ("C", "12p", ("XL1",), 0.4, 34.6, 180),                         # review: crystal pads left and right of pins 17 / 18,
    ("Y", None, (), 4.2, 34.6, 0),                                  # XL1 west, XL2 east, no crossing
    ("C", "12p", ("XL2",), 8.0, 34.6, 0),
    ("C", "100n", ("+3V3",), 11.3, 34.6, 0),
    ("R", "2.2", (), -3.6, 30.5, 0),
    ("R", "27", ("USB_DP",), -1.7, 32.6, 0),
    ("R", "27", ("USB_DN",), 1.6, 32.6, 0),
    ("C", "100n", ("VBAT_SENSE",), 5.0, 32.6, 0),
    ("C", "10u", ("+3V3",), 9.2, 32.5, 0),
    ("C", "10u", ("VBUS_NRF",), 12.9, 32.5, 0),
    ("R", "1k", ("HUB_DET",), -0.3, 30.5, 0),
    ("R", "100k", ("INT",), 3.0, 30.5, 0),
    ("R", "100k", ("CS",), 6.3, 30.5, 0),
    ("R", "33", ("MOSI",), 9.6, 30.5, 0),
    ("R", "33", ("SCK",), 12.9, 30.5, 0),
    # over the bay
    ("U", "74AHCT1G125", (), -2.0, 24.3, 0),
    ("C", "100n", ("+5V",), -1.5, 27.1, 180),                       # review: at the level shifter's supply pin 5
    ("R", "100k", ("LED_3V3",), 2.2, 25.2, 0),
    ("R", "100", ("LED_Y",), 2.2, 23.4, 0),
    ("SW", None, (), -9.5, 12.8, 0),
    ("J", "SWD", (), 0.5, 13.9, 0),
    ("D", None, (), 9.5, 11.5, 0),
    ("R", "1k", ("STATUS",), 9.5, 13.5, 0),
]


def pod(force):
    bd = ph.Hub("pod", force)
    bd.b.SetCopperLayerCount(4)
    rounded(bd, [P(-HALF, POD_FRONT), P(HALF, POD_FRONT), P(HALF, POD_REAR), P(-HALF, POD_REAR)])
    for a, t in pk.BAY["screws"]:
        bd.mech(pk.HOLE_FP, "H", *P(a, t))
    want = pp.header_bay()
    mate(bd, bd.by_value("BAY (socket)"), {n: P(*at) for n, at in want.items()}, back=True)
    if not pp.check_key_boards(want):
        bd.errors.append("the key boards' bays do not match this board")
    u1 = bd.by_value("MDBT50Q")
    bd.place(u1, *P(MOD_A, MOD_T), 0)
    pads = bd.pads(u1)
    if not (pads["1"][1] < pads["15"][1] and abs((100 - POD_REAR) - (P(MOD_A, MOD_T)[1] - 7.8 - MOD_IN)) < 0.02):
        bd.errors.append("module: the antenna end is not on the rear edge")
    j3 = bd.by_value("USB4085")
    bd.place(j3, 100 + USB_A + 2.975, 100 - POD_REAR + 8.61 - USB_OVER, 180)      # origin = pin A1; the mouth is 8.61 mm behind it
    a1, a12 = bd.pads(j3)["A1"], bd.pads(j3)["A12"]
    if abs((a1[0] + a12[0]) / 2 - (100 + USB_A)) > 0.01 or bd.pads(j3)["B1"][1] > a1[1]:
        bd.errors.append("USB-C: not on its centre line or its mouth is not to the rear")
    j2 = bd.by_value("LEAD")
    bd.place(j2, *P(-8.5, 33.0), 270)
    if not bd.pads(j2)["MP"][0] < bd.pads(j2)["1"][0]:
        bd.errors.append("lead connector: mouth is not to the west")
    place_all(bd, POD_PARTS, P)
    return bd


def antenna_clear(name="pod"):
    """On the routed pod: no track, via or zone copper inside the module's antenna rule area, on any copper layer."""
    b = pcbnew.LoadBoard(str(pk.HW / name / f"{name}.kicad_pcb"))
    u = next(f for f in b.GetFootprints() if "MDBT50Q" in f.GetValue())
    areas = [z.GetBoundingBox() for z in u.Zones() if z.GetIsRuleArea()]
    big = max(areas, key=lambda r: r.GetWidth() * r.GetHeight())
    edge = b.GetBoardEdgesBoundingBox()
    x0, x1 = max(big.GetLeft(), edge.GetLeft()), min(big.GetRight(), edge.GetRight())
    y0, y1 = max(big.GetTop(), edge.GetTop()), min(big.GetBottom(), edge.GetBottom())
    bad = 0
    for t in b.GetTracks():
        bb = t.GetBoundingBox()
        if bb.GetLeft() < x1 and bb.GetRight() > x0 and bb.GetTop() < y1 and bb.GetBottom() > y0:
            bad += 1
    box = pcbnew.SHAPE_POLY_SET()
    box.NewOutline()
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        box.Append(int(x), int(y))
    filled = 0
    for z in b.Zones():
        if z.GetIsRuleArea():
            continue
        for layer in z.GetLayerSet().CuStack():
            poly = pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(layer))
            poly.BooleanIntersection(box)
            if poly.Area() > 0:
                filled += 1
    pads = sum(1 for f in b.GetFootprints() if f is not u for p in f.Pads()
               if x0 < p.GetPosition().x < x1 and y0 < p.GetPosition().y < y1)
    layers = b.GetCopperLayerCount()
    mm = pcbnew.ToMM
    print(f"{name}: antenna keep-out {mm(x1 - x0):.1f} x {mm(y1 - y0):.2f} mm at the rear edge, {layers} copper layers: "
          f"{bad} tracks / vias, {filled} zone fills, {pads} foreign pads inside")
    return bad == 0 and filled == 0 and pads == 0


# ---- pod-power -----------------------------------------------------------------------------------------------------
U2_XY = (123.0, 113.5)
U1_XY = (139.6, 111.0)
NOTCH_W = (104.0, 109.0)    # front-west corner cut away (user, 2026-11-14): the rear cell's spring and its wall (4 x 13 mm)
NOTCH = (132.5, 115.4)      # front-east corner cut away: the side cells' last cell and its contact end there (numpad)
# prefix, value, nets, KiCad x, y, angle
POWER_PARTS = [
    ("F", None, (), 107.5, 113.5, 0),                               # BAT+ pad to the west
    ("Q", None, (), 113.6, 113.5, 180),                             # drain (fuse side) to the west
    ("D", None, (), 113.6, 117.0, 0),
    ("R", "100k", ("GATE",), 113.6, 119.6, 0),
    ("C", "47u", (), 117.5, 104.5, 0),
    # 3.3 V converter: U1 turned by 180 degrees: VIN / GND / EN / MODE pins to the west, SW / VOS to the east
    ("U", "TPS629210", (), *U1_XY, 180),
    ("C", "10u", ("VPACK",), 136.8, 110.5, 90),                     # input capacitor across pins 6 / 5
    ("L", "2.2u", (), 143.9, 111.3, 0),
    ("C", "22u", ("+3V3",), 141.6, 107.95, 180),                   # review: output capacitor at the GND / SW end, GND pad beside pin 5
    ("R", "27.4k", (), 138.6, 113.9, 0),
    ("R", "1.65M", (), 133.8, 106.2, 0),                            # cut-off divider in a column beside the enable pin
    ("R", "330k", (), 133.8, 108.0, 0),
    ("C", "100n", ("EN_3V3",), 133.8, 109.8, 0),
    ("R", "2.55M", (), 130.4, 106.2, 0),
    ("JP", None, (), 127.0, 106.25, 0),                            # 0.75 mm to the rear: the input capacitor moved up
    # 5 V converter: VIN capacitor above pins 12 / 13, output capacitors below pins 7 / 8, inductor on the strips' side
    ("U", "TPS630701", (), *U2_XY, 0),
    ("C", "10u", ("VPACK",), 125.5, 108.85, 0),                     # bulk input capacitor, moved up and east for the 0603
    ("C", "10u", ("VPACK",), 122.78, 110.77, 180),                  # review 1: 0603 across pins 12 / 13 (VIN) and 15 (GND), EN (14) leaves between its pads
    ("L", "1.5u", (), 127.3, 113.5, 270),                           # pad 1 (L1 side) to the rear, as the strips lie
    ("C", "22u", ("+5V_RAW",), 125.43, 117.1, 0),
    ("C", "22u", ("+5V_RAW",), 125.43, 119.65, 0),
    ("C", "10u", ("+5V_RAW",), 121.6, 116.23, 180),                   # review 1: the 0603 output capacitor under pins 5 / 7 / 8
    ("C", "100n", ("VAUX",), 119.4, 114.1, 180),
    ("R", "100k", ("PS",), 119.4, 112.3, 0),
    ("R", "100k", ("EN_5V_F", "GND"), 119.7, 110.4, 0),
    ("R", "1k", ("EN_5V",), 116.3, 110.4, 0),
    ("U", "TPS2553", (), 130.2, 118.3, 0),                          # LED rail cap, in front of the inductor
    ("R", "49.9k", (), 130.2, 121.0, 0),
    ("C", "100n", ("+5V_RAW",), 130.4, 114.9, 90),                  # review 15: at the TPS2553's IN pin (pad 1 towards pin 1)
    ("C", "10u", ("+5V_LED",), 133.6, 113.3, 90),
    ("R", "2.2M", (), 147.0, 109.6, 90),
    ("R", "680k", (), 147.0, 112.8, 90),
    ("TP", None, ("VPACK",), 116.9, 116.8, 0),
    ("TP", None, ("GND",), 116.6, 119.4, 0),
    ("TP", None, ("+3V3",), 110.0, 116.9, 0),                           # review: 0.75 mm from the Zener's VPACK pad (was 0.15)
    ("TP", None, ("+5V_LED",), 110.6, 119.5, 0),
]
POWER_HOLES = [(106.8, 119.3), (120.0, 120.2)]


def pod_power(force):
    bd = ph.Hub("pod-power", force)
    for c in bd.comps.values():                 # KiCad writes a "/" in a pin name as {slash} in the net of an open pin
        c["nets"] = {k: v.replace("/", "{slash}") if v.startswith("unconnected-(") else v for k, v in c["nets"].items()}
    bd.b.SetCopperLayerCount(4)
    rounded(bd, [(100.0, 100.0), (100.0 + PW[0], 100.0), (100.0 + PW[0], NOTCH[1]), NOTCH, (NOTCH[0], 100.0 + PW[1]),
                 (NOTCH_W[0], 100.0 + PW[1]), NOTCH_W, (100.0, NOTCH_W[1])])
    for x, y in POWER_HOLES:
        bd.mech(pk.HOLE_FP, "H", x, y)
    j1 = pick(bd, "J", "PACK")
    bd.place(j1, 109.25, 103.5, 270)                                # mouth on the west edge
    sw = bd.by_value("ON / OFF")
    bd.place(sw, 130.5, 102.15, 180)                                # body face on the rear edge, actuator beyond it
    if not (bd.pads(sw)["3"][0] < bd.pads(sw)["1"][0] and bd.pads(sw)["1"][1] < 103):
        bd.errors.append("slide switch is not on the rear edge")
    bd.place(pick(bd, "J", "LEAD"), 141.8, 103.4, 0)                # rear east corner, plugged from above
    place_all(bd, POWER_PARTS, lambda x, y: (x, y))
    return bd


# ---- hub-radio -----------------------------------------------------------------------------------------------------
def hub_core_expansion():
    b = pcbnew.LoadBoard(str(pk.HW / "hub-core" / "hub-core.kicad_pcb"))
    j = next(f for f in b.GetFootprints() if "EXPANSION" in f.GetValue())
    return {p.GetNumber(): (round(pcbnew.ToMM(p.GetPosition().x), 3), round(pcbnew.ToMM(p.GetPosition().y), 3)) for p in j.Pads()}


def hub_radio(force):
    bd = ph.Hub("hub-radio", force)
    c = [ph.K(x, y) for x, y in CAR_OUT]
    for a, b in zip(c, c[1:] + c[:1]):
        bd.line(a, b)

    def H(a, t):                                    # bay frame, turned by 180 degrees, to KiCad
        return ph.K(CAR_X - a, CAR_Y - t)
    for a, t in pk.BAY["screws"]:
        bd.mech(pk.HOLE_FP, "H", *H(a, t))
    mate(bd, bd.by_value("EXPANSION"), hub_core_expansion(), back=True)
    mate(bd, bd.by_value("BAY"), {n: H(*at) for n, at in pp.header_bay().items()}, back=False)
    bd.place(pick(bd, "C", "10u"), *ph.K(-38.25, 35.5), 0)
    g = ph.g
    pod_x = (CAR_X - HALF, CAR_X + HALF)
    pod_y = (CAR_Y - POD_REAR, CAR_Y - POD_FRONT)
    inner = (-g.OUTSIDE / 2 + g.WALL, g.OUTSIDE / 2 - g.WALL, g.FRONT_Y + g.WALL, g.REAR_Y - g.WALL)
    print(f"hub-radio: pod above the carrier at hub x {pod_x[0]:.1f} .. {pod_x[1]:.1f}, y {pod_y[0]:.1f} .. {pod_y[1]:.1f}; "
          f"tower inside x {inner[0]:.0f} .. {inner[1]:.0f}, y {inner[2]:.0f} .. {inner[3]:.0f}")
    if not (inner[0] < pod_x[0] and pod_x[1] < inner[1] and inner[2] < pod_y[0] and pod_y[1] < inner[3]):
        bd.errors.append("the pod does not fit inside the tower")
    return bd


BUILD = {"pod": pod, "pod-power": pod_power, "hub-radio": hub_radio}


def main():
    names = [a for a in sys.argv[1:] if not a.startswith("--")] or list(BUILD)
    ok = True
    if "--check" in sys.argv:
        ok = antenna_clear()
    else:
        for name in names:
            bd = BUILD[name]("--force" in sys.argv)
            for ref, fp in bd.placed.items():       # a library footprint's own datasheet link is not the symbol's (parity)
                fp.SetField("Datasheet", bd.comps[ref]["fields"].get("Datasheet", ""))
            ok &= bd.save()
    sys.stdout.flush()
    os._exit(0 if ok else 1)


if __name__ == "__main__":
    main()
