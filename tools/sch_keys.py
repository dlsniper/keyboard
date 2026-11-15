#!/usr/bin/env python3
"""Capture the key boards (left, right, numpad) and the module-side port board (port-module).

Spec: plans/keyboard.md sections 1 and 2 ("Wire plan", bay header table, "Key board circuit").
Everything per key comes from layout/keys.json (matrix row/col, LED order); nothing is hard-coded.

Key board: MX hotswap switch + Schottky diode (BAT43W) per key (column -> switch -> anode, cathode -> row),
MCP23S17 expander(s) (SOIC-28) wired to the spec table, 10 k column pull-ups, SK6812MINI-E chain
behind a TPS22918 load switch (+5V -> +5V_LED), 2x6 bay header, spare-pin header; `right` also has
J_DIAL to the dial board (same 5-pin pin-out as hardware/dial).
Port board (module side): 24-pin USB-C receptacle wired per the module column of the wire plan,
Rd on CC1/CC2, 3.3 V LDO from VBUS, CS RC filter, 2x6 socket mating the bay header.

Placement, stubs, labels and the net-label wiring live in tools/schlib.py. The script always
rewrites its four schematics (idempotent: UUIDs are normalised), then runs the netlist self-check.

Run:   .venv/bin/python tools/sch_keys.py            (generate + verify)
Check: .venv/bin/python tools/sch_keys.py --verify   (verify the files on disk only)
ERC:   tools/kicad-check.sh
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import schlib

HW = schlib.ROOT / "hardware"
KEYS = schlib.ROOT / "layout" / "keys.json"
G = schlib.G
schlib.HIDDEN_PROPS = schlib.HIDDEN_PROPS + ("KeyID",)

FP_R = "Resistor_SMD:R_0805_2012Metric_Pad1.20x1.40mm_HandSolder"
FP_C = "Capacitor_SMD:C_0805_2012Metric_Pad1.18x1.45mm_HandSolder"
FP_C1210 = "Capacitor_SMD:C_1210_3225Metric_Pad1.33x2.70mm_HandSolder"
FP_D = "Diode_SMD:D_SOD-123"
FP_MCP = "Package_SO:SOIC-28W_7.5x17.9mm_P1.27mm"
FP_LED = "LED_SMD:LED_SK6812MINI-E_3.2x2.8mm_P1.5mm_ReverseMount"
FP_TPS = "keyboard:TI_SOT-23-6_DBV0006A"
FP_LDO = "Package_TO_SOT_SMD:SOT-23-5"
FP_HDR2 = "Connector_PinHeader_2.54mm:PinHeader_2x06_P2.54mm_Vertical"
FP_SOCK2 = "Connector_PinSocket_2.54mm:PinSocket_2x06_P2.54mm_Vertical"
FP_TP = "TestPoint:TestPoint_Pad_D1.5mm"
FP_DIAL = "Connector_JST:JST_GH_SM05B-GHS-TB_1x05-1MP_P1.25mm_Horizontal"  # as hardware/dial J901
FP_USBC24 = "Connector_USB:USB_C_Receptacle_Amphenol_12401548E4-2A"

# ---- spec: plans/keyboard.md section 2 "Key board circuit" and section 1 bay table ----------------
GPA = [f"GPA{i}" for i in range(8)]
GPB = [f"GPB{i}" for i in range(8)]
MCP_PIN = {**{f"GPB{i}": str(1 + i) for i in range(8)}, **{f"GPA{i}": str(21 + i) for i in range(8)},
           "VDD": "9", "VSS": "10", "CS": "11", "SCK": "12", "SI": "13", "SO": "14", "A0": "15", "A1": "16",
           "A2": "17", "RESET": "18", "INTB": "19", "INTA": "20"}


def rng(names, lo, hi):
    return names[lo:hi + 1]


# per board: chips [(ref, address, {role: [pins]})]; roles col/row take the pins in matrix order
SPEC = {
    "left": {"chips": [("U1", 0, {"col": rng(GPA, 0, 6), "row": rng(GPB, 0, 5), "en": ["GPB7"], "spare": ["GPA7", "GPB6"]})]},
    "numpad": {"chips": [("U1", 1, {"col": rng(GPA, 0, 3), "row": rng(GPB, 0, 5), "en": ["GPB7"],
                                    "spare": rng(GPA, 4, 7) + ["GPB6"]})]},
    "right": {"chips": [("U1", 2, {"col": rng(GPA, 0, 7) + rng(GPB, 0, 2), "dial": ["GPB3", "GPB4"],
                                   "spare": rng(GPB, 5, 7)}),
                        ("U2", 3, {"row": rng(GPA, 0, 5), "en": ["GPB7"], "spare": rng(GPA, 6, 7) + rng(GPB, 0, 6)})]},
}
BAY = {1: "+5V", 2: "+5V", 3: "GND", 4: "LED_DIN", 5: "+3V3", 6: "SPARE", 7: "INT", 8: "CS",
       9: "MISO", 10: "MOSI", 11: "GND", 12: "SCK"}
# J_DIAL = hardware/dial J901 pin-out (1 SW_ROW, 2 ENC_A, 3 GND, 4 ENC_B, 5 SW_COL)
DIAL_NETS = {"1": "ROW{r}", "2": "DIAL_A", "3": "GND", "4": "DIAL_B", "5": "COL{c}"}
# module receptacle (wire plan, module column), both lanes of each pair tied
RECEPTACLE = {"SCK": ["B11", "A11"], "GND": ["B10", "A10", "A1", "B1", "A12", "B12", "SH"], "MOSI": ["A2", "B2"],
              "MISO_CONN": ["A3", "B3"], "CS_CONN": ["A6", "B6"], "INT_CONN": ["A7", "B7"], "LED_DIN": ["A8", "B8"],
              "+5V": ["A4", "A9", "B4", "B9"], "CC1": ["A5"], "CC2": ["B5"]}


def load_modules():
    mods = json.loads(KEYS.read_text())["modules"]
    out = {}
    for name, m in mods.items():
        rows, cols = m["matrix"]["rows"], m["matrix"]["cols"]
        sw, dial, seen = [], None, {}
        for k in m["keys"]:
            r, c = k["row"], k["col"]
            if not (0 <= r < rows and 0 <= c < cols):
                sys.exit(f"{k['id']}: matrix position {r},{c} outside {rows}x{cols}")
            if (r, c) in seen:
                sys.exit(f"{k['id']} and {seen[(r, c)]} share matrix position {r},{c}")
            seen[(r, c)] = k["id"]
            if k["kind"] == "switch":
                sw.append(k)
            elif k["kind"] == "encoder":
                dial = k
            else:
                sys.exit(f"{k['id']}: unknown kind {k['kind']}")
        leds = sorted((k for k in sw if k["led"] is not None), key=lambda k: k["led"])
        if [k["led"] for k in leds] != list(range(len(leds))):
            sys.exit(f"{name}: LED indices are not 0..n-1")
        out[name] = {"rows": rows, "cols": cols, "switches": sorted(sw, key=lambda k: (k["row"], k["col"])),
                     "leds": leds, "dial": dial}
    return out


def key_refs(k):
    return f"SW{k['row'] + 1}{k['col'] + 1:02d}", f"D{k['row'] + 1}{k['col'] + 1:02d}"


def hotswap_fp(k):
    u = max(k["w"], k["h"])
    return (f"Switch_Keyboard_Hotswap_Kailh:SW_Hotswap_Kailh_MX_{u:.2f}u"
            + ("_90deg" if k["h"] > k["w"] else ""))


class Sheet:
    def __init__(self):
        self.parts, self.flags, self.notes = [], [], []
        self.nr = self.nc = 0

    def part(self, *a):
        self.parts.append(a)

    def r(self, value, n1, n2, pos, tol="1%"):
        self.nr += 1
        self.part(f"R{self.nr}", "Device:R", value, FP_R, pos, {"1": n1, "2": n2}, {"Tolerance": tol})

    def c(self, value, n1, n2, pos, fp=FP_C, v="16V"):
        self.nc += 1
        self.part(f"C{self.nc}", "Device:C", value, fp, pos, {"1": n1, "2": n2}, {"Voltage": v, "Dielectric": "X7R"})


class Strip:
    """Vertical two-pin passives in a wrapped row."""
    def __init__(self, x, y, width, pitch=8, height=14):
        self.x0, self.x, self.y, self.w, self.p, self.h = x, x, y, width, pitch, height

    def next(self):
        if self.x + self.p > self.x0 + self.w:
            self.x, self.y = self.x0, self.y + self.h
        pos = (self.x, self.y)
        self.x += self.p
        return pos

    def bottom(self):
        return self.y + self.h


def bay_header(s, pos, ref="J1"):
    s.part(ref, "Connector_Generic:Conn_02x06_Odd_Even", "BAY", FP_HDR2, pos,
           {str(p): n for p, n in BAY.items()}, {"MPN": "generic 2x6 2.54 mm pin header"})


def build_key_board(name, mod):
    spec = SPEC[name]
    s = Sheet()
    rows, cols = mod["rows"], mod["cols"]
    # ---- key matrix block ------------------------------------------------------------------
    CW, CH, X0, Y0 = 18, 9, 8, 8
    for k in mod["switches"]:
        r, c = k["row"], k["col"]
        sw, d = key_refs(k)
        n = f"N_R{r}C{c}"
        ox, oy = X0 + c * CW, Y0 + r * CH
        s.part(sw, "Switch:SW_Push", k["id"], hotswap_fp(k), (ox + 9, oy + 1), {"1": f"COL{c}", "2": n},
               {"KeyID": k["id"], "MPN": "Kailh CPG151101S11 hotswap socket"})
        s.part(d, "Device:D", "BAT43W", FP_D, (ox + 9, oy + 5), {"1": f"ROW{r}", "2": n},
               {"KeyID": k["id"], "MPN": "Schottky, SOD-123: BAT43W (VF 0.33 V max at 2 mA)"})
    y = Y0 + rows * CH + 4
    # ---- LED chain block -----------------------------------------------------------------------
    LW, LH, per_row = 28, 12, 8
    nl = len(mod["leds"])
    for i, k in enumerate(mod["leds"]):
        din = "LED_D0" if i == 0 else f"LED_CH{i}"
        dout = "LED_DOUT" if i == nl - 1 else f"LED_CH{i + 1}"
        ox, oy = X0 + (i % per_row) * LW, y + (i // per_row) * LH
        s.part(f"LED{i + 1}", "LED:SK6812MINI-E", "SK6812MINI-E", FP_LED, (ox + 10, oy + 3),
               {"1": "GND", "2": din, "3": "+5V_LED", "4": dout}, {"KeyID": k["id"], "MPN": "SK6812MINI-E"})
        s.part(f"CL{i + 1}", "Device:C", "100n", FP_C, (ox + 21, oy + 3), {"1": "+5V_LED", "2": "GND"},
               {"Voltage": "16V", "Dielectric": "X7R"})
    y += ((nl + per_row - 1) // per_row) * LH + 4
    # ---- expanders -----------------------------------------------------------------------------
    chip_x = 24
    spare_nets = []
    chip_pos = {}
    for ref, addr, roles in spec["chips"]:
        pins = {}
        for i, p in enumerate(roles.get("col", [])):
            pins[p] = f"COL{i}"
        for i, p in enumerate(roles.get("row", [])):
            pins[p] = f"ROW{i}"
        for p, n in zip(roles.get("dial", []), ("DIAL_A", "DIAL_B")):
            pins[p] = n
        for p in roles.get("en", []):
            pins[p] = "LED_EN"
        for p in roles["spare"]:
            pins[p] = f"SP_{ref}_{p}"
            spare_nets.append(pins[p])
        if len(pins) != 16:
            sys.exit(f"{name} {ref}: {len(pins)} of 16 expander I/O pins assigned")
        if len(roles.get("col", [])) not in (0, cols) or len(roles.get("row", [])) not in (0, rows):
            sys.exit(f"{name} {ref}: spec table and keys.json matrix size {rows}x{cols} disagree")
        t = {MCP_PIN[p]: n for p, n in pins.items()}
        t.update({MCP_PIN["VDD"]: "+3V3", MCP_PIN["VSS"]: "GND", MCP_PIN["CS"]: "CS", MCP_PIN["SCK"]: "SCK",
                  MCP_PIN["SI"]: "MOSI", MCP_PIN["SO"]: "MISO", MCP_PIN["RESET"]: f"RESET_{ref}",
                  MCP_PIN["INTA"]: "INT", MCP_PIN["INTB"]: None})
        for b in range(3):
            t[MCP_PIN[f"A{b}"]] = "+3V3" if addr >> b & 1 else "GND"
        s.part(ref, "keyboard:MCP23S17-E_SO", "MCP23S17-E/SO", FP_MCP, (chip_x, y + 11), t,
               {"MPN": "Microchip MCP23S17-E/SO", "KeyID": f"addr {addr}"})
        chip_pos[ref] = chip_x
        chip_x += 46
    # ---- connectors ----------------------------------------------------------------------------
    bay_header(s, (chip_x + 10, y + 8))
    spare_pins = ["SPARE", "+3V3", "GND"] + spare_nets
    s.part("J2", f"Connector_Generic:Conn_01x{len(spare_pins):02d}", "SPARE", f"Connector_PinHeader_2.54mm:PinHeader_1x{len(spare_pins):02d}_P2.54mm_Vertical",
           (chip_x + 44, y + 11), {str(i + 1): n for i, n in enumerate(spare_pins)}, {"MPN": "generic 1xN 2.54 mm pin header"})
    cx = chip_x + 62
    if name == "right":
        d = mod["dial"]
        s.part("J3", "Connector_Generic:Conn_01x05", "J_DIAL", FP_DIAL, (cx, y + 8),
               {p: n.format(r=d["row"], c=d["col"]) for p, n in DIAL_NETS.items()}, {"MPN": "JST SM05B-GHS-TB"})
    s.part("TP1", "Connector:TestPoint", "LED_DOUT", FP_TP, (cx + (22 if name == "right" else 0), y + 8), {"1": "LED_DOUT"}, {})
    # ---- passives, LED rail --------------------------------------------------------------------
    py = y + 30
    s.part("U10", "keyboard:TPS22918DBV", "TPS22918", FP_TPS, (24, py + 5),
           {"1": "+5V", "2": "GND", "3": "LED_EN", "4": "LED_CT", "5": "+5V_LED", "6": "+5V_LED"},
           {"MPN": "TI TPS22918DBVR"})
    st = Strip(50, py + 2, 200)
    s.c("1u", "+5V", "GND", st.next(), v="16V")
    s.c("10u", "+5V_LED", "GND", st.next(), v="16V")
    s.c("100u", "+5V_LED", "GND", st.next(), fp=FP_C1210, v="10V")
    s.c("1n", "LED_CT", "GND", st.next())
    s.r("220", "LED_DIN", "LED_D0", st.next())
    s.r("100k", "LED_EN", "GND", st.next())
    for ref, addr, roles in spec["chips"]:
        s.c("100n", "+3V3", "GND", st.next())
        s.r("10k", "+3V3", f"RESET_{ref}", st.next())
        s.c("100n", f"RESET_{ref}", "GND", st.next())
    for c in range(cols):
        s.r("10k", "+3V3", f"COL{c}", st.next())
    if name == "right":
        for n in ("DIAL_A", "DIAL_B"):
            s.r("10k", "+3V3", n, st.next())
    fy = st.bottom() + 2
    s.flags = [("#FLG01", "+5V", (24, fy)), ("#FLG02", "+3V3", (32, fy)), ("#FLG03", "GND", (40, fy))]
    ymax = fy + 6
    s.notes = [((X0, ymax),
                f"{name} key board, generated by tools/sch_keys.py from layout/keys.json ({len(mod['switches'])} switches, {nl} LEDs). "
                "Diode anode to the switch (column side), cathode on the row net. LED rail +5V_LED is switched by the TPS22918 (expander LED_EN, 100k pull-down).\n"
                "LED_CT 1n: about 2.5 ms rise, inrush about 0.2 A into the rail's bulk. 220 R in front of the first LED (DIN must not exceed the LED rail by 0.5 V when the rail is off).\n"
                "Matrix diodes are Schottky: a 1N4148 at 0.3 mA leaves the column above the expander's 0.2 VDD input-low limit. "
                "INTA of every chip is wired to INT (firmware sets open drain before enabling interrupts; pull-up on the port board); INTB unused."
                + ("\nJ_DIAL pin-out matches hardware/dial J901: 1 ROW, 2 DIAL_A, 3 GND, 4 DIAL_B, 5 COL (the dial push key is a matrix key on the dial board)." if name == "right" else ""))]
    width = max(X0 + max(cols * CW, per_row * LW), cx + 40) + 6
    height = ymax + 10
    return s, width, height


def build_port_board():
    s = Sheet()
    nets = {}
    for net, pins in RECEPTACLE.items():
        for p in pins:
            nets[p] = net
    s.part("J1", "keyboard:USB_C_Receptacle_24P", "USB-C 24P (module)", FP_USBC24, (24, 30),
           nets, {"MPN": "Amphenol 12401548E4-2A (24-pin, horizontal, hybrid SMD + through-hole)"})
    s.part("U1", "Regulator_Linear:AP2112K-3.3", "AP2112K-3.3", FP_LDO, (70, 12),
           {"1": "+5V", "2": "GND", "3": "+5V", "4": None, "5": "+3V3"}, {"MPN": "Diodes Inc AP2112K-3.3TRG1"})
    s.part("J2", "Connector_Generic:Conn_02x06_Odd_Even", "BAY (socket)", FP_SOCK2, (110, 22),
           {str(p): (None if n == "SPARE" else n) for p, n in BAY.items()}, {"MPN": "generic 2x6 2.54 mm socket"})
    st = Strip(56, 40, 80)
    s.c("1u", "+5V", "GND", st.next())
    s.c("1u", "+3V3", "GND", st.next())
    s.r("1k", "CS_CONN", "CS", st.next())
    s.c("100p", "CS", "GND", st.next(), v="50V")
    s.r("100k", "+3V3", "CS", st.next())
    s.r("10k", "+3V3", "INT", st.next())
    s.r("150", "MISO", "MISO_CONN", st.next())     # was 33: a bridge to +5V now puts 9 mA into the MCP23S17, not 40
    for ref, x, quad in (("U2", 150, ("SCK", "MOSI", "MISO_CONN", "CS_CONN")), ("U3", 185, ("INT_CONN", "LED_DIN", "CC1", "CC2"))):
        s.part(ref, "keyboard:TPD4E1U06DBV", "TPD4E1U06", FP_TPS, (x, 14),
               {"1": quad[0], "3": quad[1], "6": quad[2], "4": quad[3], "5": None, "2": "GND"}, {"MPN": "TI TPD4E1U06DBVR"})
    s.part("D1", "Power_Protection:TVS0500DRV", "TVS0500", "Package_SON:WSON-6-1EP_2x2mm_P0.65mm_EP1x1.6mm", (165, 40),
           {"1": "GND", "2": "GND", "3": "GND", "7": "GND", "4": "+5V", "5": "+5V", "6": "+5V"}, {"MPN": "TI TVS0500DRVR"})
    s.r("5.1k", "CC1", "GND", st.next())
    s.r("5.1k", "CC2", "GND", st.next())
    s.r("1k", "INT_CONN", "INT", st.next())        # robustness review 3 (user, 2026-11-14): J1's INT pins lie 0.15 mm from +5V
    s.flags = [("#FLG01", "+5V", (20, 62)), ("#FLG02", "GND", (28, 62))]
    s.notes = [((8, 76), "Port board, module side (spec section 1 wire plan, module column): SCK on RX+, its return on RX-, MOSI on TX+, MISO on TX-,\n"
                         "CS on D+ (1k + 100 pF and 100k pull-up at the module: CS stays high while the hub does not drive it), INT on D- (1k in series, 10k pull-up here, none at the hub),\n"
                         "MISO through 150 R at its source (33 until the robustness review; M4 step 2 measures the edge), LED data on SBU, +5V on VBUS, CC1/CC2 5.1k Rd each, shell direct to GND.\n"
                         "3.3 V from VBUS via AP2112K-3.3 to bay pin 5. TPD4E1U06 on the six signals and CC, TVS0500 on VBUS.\n"
                         "J2 pin numbers equal the key board bay header J1; place the socket on the layer that mates pin 1 to pin 1.")]
    return s, 215, 100


PAPERS = [("A4", 297, 210), ("A3", 420, 297), ("A2", 594, 420), ("A1", 841, 594), ("A0", 1189, 841)]


def paper_for(w, h):
    for n, pw, ph in PAPERS:
        if w * G <= pw and h * G <= ph:
            return n
    sys.exit("sheet content larger than A0")


def normalise_uuids(path, stable):
    """Replace every random UUID by one derived from the file name and first-seen order."""
    text = path.read_text()
    seen = {}

    def sub(m):
        u = m.group(0)
        if u in stable:
            return u
        if u not in seen:
            seen[u] = str(uuid.uuid5(uuid.NAMESPACE_URL, f"keyboard/{path.stem}/uuid/{len(seen)}"))
        return seen[u]
    path.write_text(re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", sub, text))


def generate(name, s, w, h, ref_base):
    sch_path = HW / name / f"{name}.kicad_sch"
    sch = schlib.build(name, f"{name} key board" if name != "port-module" else "Port board, module side",
                       ref_base, s.parts, s.flags, s.notes, paper=paper_for(w, h))
    sch.save(str(sch_path))
    schlib.post_process(sch_path, set(), {}, {})
    stable = {str(uuid.uuid5(uuid.NAMESPACE_URL, f"keyboard/{name}/{p[0]}")) for p in s.parts}
    normalise_uuids(sch_path, stable)
    schlib.to_current_format(sch_path)
    print("wrote", sch_path)
    return sch_path


# ---- self-check -------------------------------------------------------------------------------------

def read_netlist(sch_path):
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "n.net"
        subprocess.run([schlib._cli(), "sch", "export", "netlist", "-o", str(out), str(sch_path)], check=True, capture_output=True)
        text = out.read_text()
    comps = {m.group(1): m.group(2) for m in re.finditer(r'\(comp\s*\(ref "([^"]+)"\)\s*\(value "([^"]*)"\)', text)}
    net_of, nodes = {}, {}
    for m in re.finditer(r'\(net\s*\(code "\d+"\)\s*\(name "([^"]*)"\)(.*?)\n\t\t\)', text, re.S):
        nm = m.group(1).lstrip("/")
        for r, p in re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', m.group(2)):
            net_of[(r, p)] = nm
            nodes.setdefault(nm, []).append((r, p))
    return comps, net_of, nodes


class Checker:
    def __init__(self, label, comps, net_of, nodes):
        self.label, self.comps, self.net_of, self.nodes = label, comps, net_of, nodes
        self.errors, self.n = [], 0

    def eq(self, what, got, want):
        self.n += 1
        if got != want:
            self.errors.append(f"{self.label}: {what}: got {got!r}, want {want!r}")

    def net(self, ref, pin):
        return self.net_of.get((ref, str(pin)))

    def partner(self, ref, pin, prefix):
        """Parts with the given reference prefix on the net of ref.pin: [(ref, value, other pin net)]."""
        n = self.net(ref, pin)
        out = []
        for r, p in self.nodes.get(n, []):
            if re.match(prefix + r"\d+$", r) and r != ref:
                other = "2" if p == "1" else "1"
                out.append((r, self.comps[r], self.net(r, other)))
        return sorted(out)


def verify_key_board(name, mod, sch_path):
    comps, net_of, nodes = read_netlist(sch_path)
    c = Checker(name, comps, net_of, nodes)
    sw = [r for r in comps if re.match(r"SW\d+$", r)]
    di = [r for r in comps if re.match(r"D\d+$", r)]
    le = [r for r in comps if re.match(r"LED\d+$", r)]
    exp = len(mod["switches"])
    c.eq("switch count", len(sw), exp)
    c.eq("diode count", len(di), exp)
    c.eq("LED count", len(le), len(mod["leds"]))
    for k in mod["switches"]:
        s_ref, d_ref = key_refs(k)
        c.eq(f"{k['id']} column", c.net(s_ref, 1), f"COL{k['col']}")
        c.eq(f"{k['id']} diode anode on switch", c.net(d_ref, 2), c.net(s_ref, 2))
        c.eq(f"{k['id']} row", c.net(d_ref, 1), f"ROW{k['row']}")
        c.eq(f"{k['id']} switch-diode net private", sorted(nodes[c.net(s_ref, 2)]), sorted([(s_ref, "2"), (d_ref, "2")]))
    # expanders
    spare_expected = ["SPARE", "+3V3", "GND"]
    for ref, addr, roles in SPEC[name]["chips"]:
        c.eq(f"{ref} value", comps.get(ref), "MCP23S17-E/SO")
        want = {}
        for i, p in enumerate(roles.get("col", [])):
            want[p] = f"COL{i}"
        for i, p in enumerate(roles.get("row", [])):
            want[p] = f"ROW{i}"
        for p, n in zip(roles.get("dial", []), ("DIAL_A", "DIAL_B")):
            want[p] = n
        for p in roles.get("en", []):
            want[p] = "LED_EN"
        for p in roles["spare"]:
            want[p] = f"SP_{ref}_{p}"
            spare_expected.append(want[p])
        for p, n in want.items():
            c.eq(f"{ref}.{p}", c.net(ref, MCP_PIN[p]), n)
        for b in range(3):
            c.eq(f"{ref}.A{b}", c.net(ref, MCP_PIN[f"A{b}"]), "+3V3" if addr >> b & 1 else "GND")
        for k, n in (("VDD", "+3V3"), ("VSS", "GND"), ("CS", "CS"), ("SCK", "SCK"), ("SI", "MOSI"), ("SO", "MISO"), ("INTA", "INT")):
            c.eq(f"{ref}.{k}", c.net(ref, MCP_PIN[k]), n)
        c.eq(f"{ref}.INTB unconnected", (c.net(ref, MCP_PIN["INTB"]) or "").startswith("unconnected-"), True)
        rn = c.net(ref, MCP_PIN["RESET"])
        c.eq(f"{ref} reset pull-up", [(v, o) for _, v, o in c.partner(ref, MCP_PIN["RESET"], "R")], [("10k", "+3V3")])
        c.eq(f"{ref} reset cap", [(v, o) for _, v, o in c.partner(ref, MCP_PIN["RESET"], "C")], [("100n", "GND")])
    # one 100n decoupling cap per chip on +3V3 (the net is shared, so count per board)
    c.eq("decoupling caps on +3V3", sum(1 for r, v, o in c.partner(SPEC[name]["chips"][0][0], MCP_PIN["VDD"], "C") if v == "100n" and o == "GND"),
         len(SPEC[name]["chips"]))
    # pull-ups
    pulled = [f"COL{i}" for i in range(mod["cols"])] + (["DIAL_A", "DIAL_B"] if name == "right" else [])
    for n in pulled:
        ups = [(r, comps[r]) for r, p in nodes[n] if r.startswith("R") and net_of[(r, "1" if p == "2" else "2")] == "+3V3"]
        c.eq(f"{n} pull-up", [v for _, v in ups], ["10k"])
    # bay and spare header
    for p, n in BAY.items():
        c.eq(f"bay J1.{p}", c.net("J1", p), n)
    c.eq("spare header nets", sorted(c.net("J2", p) for p in range(1, 1 + len(spare_expected))), sorted(spare_expected))
    c.eq("spare header pin count", sum(1 for r, p in net_of if r == "J2"), len(spare_expected))
    if name == "right":
        d = mod["dial"]
        for p, n in DIAL_NETS.items():
            c.eq(f"J_DIAL.{p}", c.net("J3", p), n.format(r=d["row"], c=d["col"]))
    # LED chain in keys.json order
    for i, k in enumerate(mod["leds"]):
        ref = f"LED{i + 1}"
        c.eq(f"{ref} is {k['id']}", comps.get(ref), "SK6812MINI-E")
        din = c.net(ref, 2)
        if i == 0:
            c.eq(f"{ref} DIN", din, "LED_D0")
        else:
            c.eq(f"{ref} DIN from LED{i} DOUT", din, c.net(f"LED{i}", 4))
            c.eq(f"{ref} DIN net has two nodes", len(nodes[din]), 2)
        c.eq(f"{ref} VDD", c.net(ref, 3), "+5V_LED")
        c.eq(f"{ref} VSS", c.net(ref, 1), "GND")
        c.eq(f"{ref} cap", c.net(f"CL{i + 1}", 1), "+5V_LED")
        c.eq(f"{ref} cap gnd", c.net(f"CL{i + 1}", 2), "GND")
    last = f"LED{len(mod['leds'])}"
    c.eq("last DOUT to test point", sorted(nodes[c.net(last, 4)]), sorted([(last, "4"), ("TP1", "1")]))
    # LED rail
    c.eq("TPS VIN", c.net("U10", 1), "+5V")
    c.eq("TPS ON is LED_EN", c.net("U10", 3), "LED_EN")
    c.eq("TPS ON pull-down", [(v, o) for _, v, o in c.partner("U10", 3, "R")], [("100k", "GND")])
    c.eq("TPS CT cap", [(v, o) for _, v, o in c.partner("U10", 4, "C")], [("1n", "GND")])
    c.eq("TPS QOD = VOUT", c.net("U10", 5), c.net("U10", 6))
    c.eq("TPS VOUT net", c.net("U10", 6), "+5V_LED")
    c.eq("TPS VIN cap", sorted((v, o) for _, v, o in c.partner("U10", 1, "C")), [("1u", "GND")])
    c.eq("TPS VOUT bulk", sorted((v, o) for _, v, o in c.partner("U10", 6, "C") if v != "100n"), [("100u", "GND"), ("10u", "GND")])
    # LED_EN comes from the right expander pin
    en_chip = [ref for ref, _, roles in SPEC[name]["chips"] if "en" in roles][0]
    c.eq("LED_EN driven by", sorted(r for r, p in nodes["LED_EN"] if r.startswith("U")), sorted([en_chip, "U10"]))
    return c


def verify_port(sch_path):
    comps, net_of, nodes = read_netlist(sch_path)
    c = Checker("port-module", comps, net_of, nodes)
    for net, pins in RECEPTACLE.items():
        for p in pins:
            c.eq(f"J1.{p}", c.net("J1", p), net)
    c.eq("J1 pin count", sum(1 for r, p in net_of if r == "J1"), 25)
    for p, n in BAY.items():
        want = n
        if n == "SPARE":
            c.eq("J2.6 unconnected", (c.net("J2", 6) or "").startswith("unconnected-"), True)
        else:
            c.eq(f"J2.{p}", c.net("J2", p), want)
    c.eq("LDO", [c.net("U1", p) for p in (1, 2, 3, 5)], ["+5V", "GND", "+5V", "+3V3"])
    c.eq("LDO in cap", [(v, o) for _, v, o in c.partner("U1", 1, "C")], [("1u", "GND")])
    c.eq("LDO out cap", [(v, o) for _, v, o in c.partner("U1", 5, "C")], [("1u", "GND")])
    c.eq("CS series R", sorted((v, o) for _, v, o in c.partner("J1", "A6", "R")), [("1k", "CS")])
    c.eq("INT series R", sorted((v, o) for _, v, o in c.partner("J1", "A7", "R")), [("1k", "INT")])
    c.eq("MISO series R", sorted((v, o) for _, v, o in c.partner("J1", "A3", "R")), [("150", "MISO")])
    c.eq("INT pull-up behind the series R", sorted((v, o) for _, v, o in c.partner("J2", 7, "R")), [("10k", "+3V3"), ("1k", "INT_CONN")])
    c.eq("CS filter C", sorted((v, o) for _, v, o in c.partner("J2", 8, "C")), [("100p", "GND")])
    for cc in ("CC1", "CC2"):
        c.eq(f"{cc} Rd", sorted((v, o) for _, v, o in c.partner("J1", "A5" if cc == "CC1" else "B5", "R")), [("5.1k", "GND")])
    return c


def report(checks):
    bad = 0
    for c in checks:
        print(f"{c.label}: {c.n} assertions, {len(c.errors)} failed")
        for e in c.errors[:20]:
            print("  FAIL", e)
        bad += len(c.errors)
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="only verify the schematics on disk against keys.json and the spec")
    args = ap.parse_args()
    mods = load_modules()
    checks = []
    for name in ("left", "right", "numpad"):
        mod = mods[name]
        if not args.verify:
            s, w, h = build_key_board(name, mod)
            generate(name, s, w, h, 0)
        sw = len(mod["switches"])
        print(f"{name}: {sw} switches, {sw} diodes, {len(mod['leds'])} LEDs from keys.json"
              + (f" (+ dial push at row {mod['dial']['row']} col {mod['dial']['col']} on the dial board)" if mod["dial"] else ""))
        checks.append(verify_key_board(name, mod, HW / name / f"{name}.kicad_sch"))
    if not args.verify:
        s, w, h = build_port_board()
        generate("port-module", s, w, h, 0)
    checks.append(verify_port(HW / "port-module" / "port-module.kicad_sch"))
    sys.exit(1 if report(checks) else 0)


if __name__ == "__main__":
    main()
