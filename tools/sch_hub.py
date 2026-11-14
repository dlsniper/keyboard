#!/usr/bin/env python3
"""Capture the hub tower boards: hub-core (core layer), hub-conn (connector layer with the power path)
and battery (AA module).

Spec: plans/keyboard.md section 1 (wire plan, hub column), section 3 (power) and section 3a (hub: stack
connector, pin map, port circuit, pack priority). The tables below are the source; the spec quotes them.

hub-core: Pico 2 W on pin sockets, three pogo pins to its underside pads (TP2 USB D-, TP3 USB D+,
          TP6 BOOTSEL), power / reset / boot buttons, the frozen 2x25 stack connector, expansion header.
hub-conn: three module ports (24-pin USB-C receptacle, TPS25810 Type-C source switch, 74LVC125 SPI
          buffer gated by the port's CS, ESD arrays), one 74AHCT125 for LED data, the host-port cable
          header (hardware/usb-port J502), and the power path: five pack inputs (TVS, LM74610-Q1 ideal
          diode, priority P-FET), pack-priority supervisors, UVLO, battery and USB switches, 5 V buck-boost
          (TPS552892, 3.5 A).
battery:  passive 4xAA module: holder, PTC, chain in / chain out with the one-line shift.
chain-cap: the small board on a battery module's riser that carries the spring-pin strip (pin n to pin n).

Run:   .venv/bin/python tools/sch_hub.py            (generate + verify)
Check: .venv/bin/python tools/sch_hub.py --verify   (verify the files on disk only)
ERC:   tools/kicad-check.sh
"""

import argparse
import json
import sys
import uuid

import schlib
from sch_keys import normalise_uuids, paper_for, read_netlist

HW = schlib.ROOT / "hardware"

FP_R = "Resistor_SMD:R_0805_2012Metric_Pad1.20x1.40mm_HandSolder"
FP_C = "Capacitor_SMD:C_0805_2012Metric_Pad1.18x1.45mm_HandSolder"
FP_C1210 = "Capacitor_SMD:C_1210_3225Metric_Pad1.33x2.70mm_HandSolder"
FP_C0603 = "Capacitor_SMD:C_0603_1608Metric"
FP_SOT23 = "Package_TO_SOT_SMD:SOT-23"
FP_SOD123 = "Diode_SMD:D_SOD-123"
FP_USBC24 = "Connector_USB:USB_C_Receptacle_Amphenol_12401548E4-2A"
FP_GH11 = "Connector_JST:JST_GH_SM11B-GHS-TB_1x11-1MP_P1.25mm_Horizontal"
FP_TP = "TestPoint:TestPoint_Pad_D1.5mm"
# stack: the same stack-through socket on both boards, both on the top side (user, 2026-11-13: rev 8's ESQ, 17.5 mm)
FP_STACK = "Connector_PinSocket_2.54mm:PinSocket_2x25_P2.54mm_Vertical"
MPN_STACK = "Samtec ESQ-125-24-T-D (stack-through: body 13.59 mm, tail 9.65 mm; 17.5 mm between the boards)"
FP_TARGET = "keyboard:PogoTarget_2x08_P2.54mm"      # on the board's underside
MPN_TARGET = "16 x Mill-Max 1578-0-57-15-00-00-03-0 target discs, underside"
FP_XH2 = "Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical"
FP_XH3 = "Connector_JST:JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical"

PORTS = ("A", "B", "C")
PACKS = (1, 2, 3, 4, 5)  # hub input 1 = the module next to the hub, 5 = the lowest module

# ---- frozen stack connector, core layer <-> connector layer (2x25, 2.54 mm) -----------------------
STACK = {
    1: "+5V", 2: "+5V", 3: "GND", 4: "GND", 5: "+3V3", 6: "+3V3", 7: "USB_DP", 8: "GND", 9: "USB_DN", 10: "GND",
    11: "SCK", 12: "GND", 13: "MOSI", 14: "MISO", 15: "CS_A", 16: "CS_B", 17: "CS_C", 18: "GND",
    19: "INT_A", 20: "INT_B", 21: "INT_C", 22: "PORT_FLT", 23: "LED_A", 24: "LED_B", 25: "LED_C", 26: "GND",
    27: "EN_A", 28: "EN_B", 29: "EN_C", 30: "USB_PRESENT", 31: "DET_A", 32: "DET_B", 33: "DET_C", 34: "GND",
    35: "CC1_SENSE", 36: "CC2_SENSE", 37: "VBAT_SENSE", 38: "GND", 39: "BAT_DIV_EN", 40: "RUN",
    41: "PWR_SW_A", 42: "PWR_SW_B", 43: "SDA", 44: "SCL", 45: "SP1", 46: "SP2", 47: "SP3", 48: "SP4",
    49: "GND", 50: "GND",
}
# stack nets the connector layer does not use (reserved for later boards)
STACK_RESERVED = {"RUN", "SDA", "SCL", "SP1", "SP2", "SP3", "SP4"}

# ---- hub pin map: Pico 2 W GPIO -> net ---------------------------------------------------------------
PICO_GPIO = {
    0: "SDA", 1: "SCL",
    2: "EN_A", 3: "DET_A", 4: "INT_A", 5: "CS_A", 6: "LED_A",
    7: "EN_B", 8: "DET_B", 9: "INT_B", 10: "CS_B", 11: "LED_B",
    12: "EN_C", 13: "DET_C", 14: "INT_C", 15: "CS_C",
    16: "MISO", 17: "LED_C", 18: "SCK", 19: "MOSI",
    20: "PORT_FLT", 21: "USB_PRESENT", 22: "BAT_DIV_EN",
    26: "CC1_SENSE", 27: "CC2_SENSE", 28: "VBAT_SENSE",
}
# Pico header pin -> GPIO (Pico 2 W pin-out; symbol keyboard:Pico2W)
PICO_HEADER = {1: 0, 2: 1, 4: 2, 5: 3, 6: 4, 7: 5, 9: 6, 10: 7, 11: 8, 12: 9, 14: 10, 15: 11, 16: 12, 17: 13,
               19: 14, 20: 15, 21: 16, 22: 17, 24: 18, 25: 19, 26: 20, 27: 21, 29: 22, 31: 26, 32: 27, 34: 28}
PICO_GND = (3, 8, 13, 18, 23, 28, 33, 38)

# ---- hub receptacle (spec section 1 wire plan, hub column), per port ---------------------------------
RECEPTACLE_HUB = {"SCK_{p}": ["A2", "B2"], "GND": ["A3", "B3", "A1", "B1", "A12", "B12", "SH"],
                  "MOSI_{p}": ["B11", "A11"], "MISO_{p}": ["B10", "A10"], "CSO_{p}": ["A6", "B6"],
                  "INTO_{p}": ["A7", "B7"], "LEDO_{p}": ["A8", "B8"], "VBUS_{p}": ["A4", "A9", "B4", "B9"],
                  "CC1_{p}": ["A5"], "CC2_{p}": ["B5"]}

# ---- battery chain, 2x8, reversal-safe (pin k meets 17-k) --------------------------------------------
CHAIN = {1: "PACK1", 2: "GND", 3: "PACK2", 4: "PACK3", 5: "GND", 6: "PACK4", 7: "PACK5", 8: "AUX_5V",
         9: "AUX_5V", 10: "PACK5", 11: "PACK4", 12: "GND", 13: "PACK3", 14: "PACK2", 15: "GND", 16: "PACK1"}
# host port cable header = hardware/usb-port J502
J_USB = {1: "VBUS_IN", 2: "GND", 3: "CC1", 4: "GND", 5: "USB_DP", 6: "VBUS_IN", 7: "USB_DN", 8: None,
         9: "CC2", 10: "GND", 11: "VBUS_IN"}


class Board:
    """Parts table with a flowing placer (cells wrap at the sheet width; overlaps are caught by the netlist check)."""

    def __init__(self, width=150):
        self.parts, self.flags, self.notes, self.dnp = [], [], [], set()
        self.count = {}
        self.group = "misc"      # placement group, a symbol field read by tools/pcb_hub.py
        self.x0, self.y0, self.w = 12, 12, width
        self.x, self.y, self.rowh = self.x0, self.y0, 0

    def at(self, w, h):
        if self.x + w > self.x0 + self.w:
            self.row()
        pos = (self.x + w // 2, self.y + h // 2)
        self.x += w
        self.rowh = max(self.rowh, h)
        return pos

    def row(self, gap=0):
        self.x, self.y, self.rowh = self.x0, self.y + self.rowh + gap, 0

    def ref(self, prefix):
        self.count[prefix] = self.count.get(prefix, 0) + 1
        return f"{prefix}{self.count[prefix]}"

    def part(self, prefix, lib, value, fp, size, pins, props=None):
        ref = self.ref(prefix)
        props = dict(props or {}, Group=self.group)
        self.parts.append((ref, lib, value, fp, self.at(*size), {str(k): v for k, v in pins.items()}, props))
        return ref

    def r(self, value, n1, n2, tol="1%", dnp=False):
        ref = self.part("R", "Device:R", value, FP_R, (8, 18), {1: n1, 2: n2}, {"Tolerance": tol})
        if dnp:
            self.dnp.add(ref)
        return ref

    def c(self, value, n1, n2="GND", fp=FP_C, v="16V"):
        return self.part("C", "Device:C", value, fp, (8, 18), {1: n1, 2: n2}, {"Voltage": v, "Dielectric": "X7R"})

    def bulk(self, net):
        return self.part("C", "Device:C_Polarized", "220u", "Capacitor_SMD:CP_Elec_8x10", (10, 18), {1: net, 2: "GND"},
                         {"Voltage": "16V", "MPN": "220 uF 16 V aluminium polymer, ESR 30 mOhm or less, 8 mm can"})

    def schottky(self, anode, cathode):
        return self.part("D", "Diode:BAT54W", "BAT54", FP_SOT23, (26, 10), {1: anode, 2: None, 3: cathode},
                         {"MPN": "Diodes BAT54-7-F"})

    def bat54c(self, a1, a2, cathode):
        return self.part("D", "Diode:BAT54C", "BAT54C", FP_SOT23, (28, 12), {1: a1, 2: a2, 3: cathode},
                         {"MPN": "Diodes BAT54C-7-F"})

    def dual_nfet(self, g1, d1, s1, g2, d2, s2):
        return self.part("Q", "keyboard:DMN63D8LDW", "DMN63D8LDW", "Package_TO_SOT_SMD:SOT-363_SC-70-6", (30, 12),
                         {2: g1, 6: d1, 1: s1, 5: g2, 3: d2, 4: s2}, {"MPN": "Diodes DMN63D8LDW-7"})

    def pfet(self, g, s, d):
        # stock symbol: 1-3 D, 4 G, 5 S (CSD25402Q3A top view: D 1-3, G 4, S 5-8)
        return self.part("Q", "Transistor_FET:CSD25402Q3A", "CSD25402Q3A", "Package_SON:VSON-8_3.3x3.3mm_P0.65mm_NexFET",
                         (26, 18), {1: d, 2: d, 3: d, 4: g, 5: s}, {"MPN": "TI CSD25402Q3A"})

    def supervisor(self, value, vdd, out):
        return self.part("U", "keyboard:TPS3840PLxxDBV", value, "keyboard:TI_SOT-23-5_DBV0005A", (30, 16),
                         {2: vdd, 3: "GND", 1: out, 4: None, 5: None}, {"MPN": f"TI {value}DBVR"})

    def flag(self, net):
        n = len(self.flags) + 1
        self.flags.append((f"#FLG0{n}", net, None))

    def finish(self, note):
        self.row(4)
        self.flags = [(ref, net, (self.x0 + 4 + 10 * i, self.y + 2)) for i, (ref, net, _) in enumerate(self.flags)]
        self.notes = [((self.x0, self.y + 14), note)]
        return self.w + 2 * self.x0, self.y + 16 + int(1.2 * (note.count("\n") + 2))


def conn(pins_to_net, skip=()):
    return {p: (None if n in skip else n) for p, n in pins_to_net.items()}


# ---- hub-core --------------------------------------------------------------------------------------------

def build_core():
    b = Board(150)
    pico = {str(p): PICO_GPIO[g] for p, g in PICO_HEADER.items()}
    pico.update({str(p): "GND" for p in PICO_GND})
    pico.update({"30": "RUN", "35": None, "36": "+3V3", "37": None, "39": "VSYS", "40": None})
    b.part("A", "keyboard:Pico2W", "Pico 2 W (on 2x 1x20 sockets)", "Module:RaspberryPi_Pico_Common_THT",
           (44, 36), pico, {"MPN": "Raspberry Pi Pico 2 W (SC1634) on 2 x 1x20 2.54 mm sockets"})
    b.part("J", "Connector_Generic:Conn_02x25_Odd_Even", "STACK (ESQ, tails down)",
           FP_STACK, (44, 36), STACK, {"MPN": MPN_STACK})
    b.part("J", "Connector_Generic:Conn_02x05_Odd_Even", "EXPANSION",
           "Connector_PinHeader_2.54mm:PinHeader_2x05_P2.54mm_Vertical", (40, 22),
           {1: "+3V3", 2: "+5V", 3: "SDA", 4: "SCL", 5: "SP1", 6: "SP2", 7: "SP3", 8: "SP4", 9: "GND", 10: "GND"},
           {"MPN": "generic 2x5 2.54 mm header"})
    b.row(2)
    # pogo pins to the Pico's underside test pads
    for net, name in (("USB_DN", "TP2 USB D-"), ("USB_DP", "TP3 USB D+"), ("BOOTSEL", "TP6 BOOTSEL")):
        b.part("TP", "Connector:TestPoint", f"pogo, Pico {name}", "keyboard:SpringPin_MillMax_0929_THT", (16, 16), {1: net},
               {"MPN": "Mill-Max 0929-7-15-20-75-14-11-0 (12.19 mm free, 1.40 mm stroke)"})
    # buttons: power is latching (on: UVLO output to the battery-switch gate; off: gate line to GND)
    b.part("SW", "Switch:SW_SPDT", "POWER (latching, on leads)", FP_XH3, (30, 16), {1: "PWR_SW_A", 2: "PWR_SW_B", 3: "GND"},
           {"MPN": "NKK UB16KKG01N-F on leads to a JST XHP-3; board: JST B3B-XH-A"})
    b.part("SW", "Switch:SW_Push", "RESET (on leads)", FP_XH2, (26, 16), {1: "RUN", 2: "GND"},
           {"MPN": "NKK UB15KKG01N-C on leads to a JST XHP-2; board: JST B2B-XH-A"})
    b.part("SW", "Switch:SW_Push", "BOOT (on leads)", FP_XH2, (26, 16), {1: "BOOTSEL", 2: "GND"},
           {"MPN": "NKK UB15KKG01N-C on leads to a JST XHP-2; board: JST B2B-XH-A"})
    b.row(2)
    b.part("D", "Device:D_Schottky", "MBR120", FP_SOD123, (24, 12), {1: "VSYS", 2: "+5V"}, {"MPN": "onsemi MBR120VLSFT1G"})
    b.c("10u", "+5V")
    b.c("10u", "VSYS")
    b.c("100n", "+3V3")
    b.r("4.7k", "+3V3", "SDA")
    b.r("4.7k", "+3V3", "SCL")
    for net in ("GND", "VSYS"):
        b.flag(net)
    w, h = b.finish(
        "Hub core layer (spec section 3a). The only controller: Pico 2 W on sockets, VSYS from the stack's +5V through D1\n"
        "(so the Pico's own micro-USB cannot back-feed the hub rail); the Pico's 3V3 output is the hub's +3V3 logic rail.\n"
        "Host USB D+/D- and BOOTSEL reach the Pico through three pogo pins on its underside pads TP2, TP3, TP6.\n"
        "J1 is the frozen 2x25 stack connector to the connector layer; pin map in tools/sch_hub.py STACK.\n"
        "Power switch: closed = PWR_SW_A (UVLO output, pack level, microamps) to PWR_SW_B (battery-switch gate); open = gate to GND.\n"
        "On USB the hub is on regardless of the switch. GP0/GP1 (SDA/SCL) and SP1-SP4 go to the expansion header and the stack.")
    return b, w, h


# ---- hub-conn --------------------------------------------------------------------------------------------

def build_port(b, p):
    f = lambda s: s.format(p=p)
    b.group = f"port{p}"
    nets = {}
    for net, pins in RECEPTACLE_HUB.items():
        for pin in pins:
            nets[pin] = f(net)
    b.part("J", "keyboard:USB_C_Receptacle_24P", f"MODULE PORT {p}", FP_USBC24, (40, 24), nets,
           {"MPN": "Amphenol 12401548E4-2A (24-pin, horizontal, hybrid SMD + through-hole)"})
    # Type-C source switch: Rp on CC, VBUS on only with Rd, UFP low = sink attached
    b.part("U", "Interface_USB:TPS25810RVC", "TPS25810", "Package_DFN_QFN:Texas_RVC0020A_WQFN-20-1EP_3x4mm_P0.5mm_EP1.6x2.6mm",
           (44, 30),
           {1: "PORT_FLT", 2: "+5V", 3: "+5V", 4: "+5V", 5: "+5V", 6: f("EN_{p}"), 7: "+5V", 8: "CHG_HI",
            9: f("REFR_{p}"), 10: f("REF_{p}"), 11: f("CC1_{p}"), 12: "GND", 13: f("CC2_{p}"), 14: f("VBUS_{p}"),
            15: f("VBUS_{p}"), 16: None, 17: None, 18: None, 19: f("DET_{p}"), 20: None, 21: "GND"},
           {"MPN": "TI TPS25810RVCR"})
    # SPI buffer: SCK, MOSI out and MISO back only while this port's CS is low; CS out only while a sink is attached
    b.part("U", "keyboard:74x125_SO14", "74LVC125A", "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm", (34, 26),
           {1: f("CS_{p}"), 2: "SCK", 3: f("SCKB_{p}"), 4: f("CS_{p}"), 5: "MOSI", 6: f("MOSIB_{p}"),
            10: f("DET_{p}"), 9: f("CS_{p}"), 8: f("CSB_{p}"), 13: f("CS_{p}"), 12: f("MISO_{p}"), 11: "MISO",
            14: "+3V3", 7: "GND"}, {"MPN": "74LVC125A, SOIC-14"})
    for quad in (("SCK_{p}", "MOSI_{p}", "MISO_{p}", "CSO_{p}"), ("INTO_{p}", "LEDO_{p}", "CC1_{p}", "CC2_{p}")):
        b.part("U", "keyboard:TPD4E1U06DBV", "TPD4E1U06", "keyboard:TI_SOT-23-6_DBV0006A", (30, 14),
               {1: f(quad[0]), 3: f(quad[1]), 6: f(quad[2]), 4: f(quad[3]), 5: None, 2: "GND"}, {"MPN": "TI TPD4E1U06DBVR"})
    b.part("D", "Power_Protection:TVS0500DRV", "TVS0500", "Package_SON:WSON-6-1EP_2x2mm_P0.65mm_EP1x1.6mm", (30, 20),
           {1: "GND", 2: "GND", 3: "GND", 7: "GND", 4: f("VBUS_{p}"), 5: f("VBUS_{p}"), 6: f("VBUS_{p}")},
           {"MPN": "TI TVS0500DRVR"})
    b.r("33", f("SCKB_{p}"), f("SCK_{p}"))
    b.r("33", f("MOSIB_{p}"), f("MOSI_{p}"))
    b.r("33", f("CSB_{p}"), f("CSO_{p}"))
    b.r("100k", f("SCK_{p}"), "GND")
    b.r("100k", f("MOSI_{p}"), "GND")
    b.r("100k", f("MISO_{p}"), "GND")
    b.r("10k", "+3V3", f("CS_{p}"))
    b.r("1k", f("INTO_{p}"), f("INT_{p}"))
    b.r("10k", "+3V3", f("DET_{p}"))
    b.r("10k", f("EN_{p}"), "GND")
    b.r("100k", f("REF_{p}"), f("REFR_{p}"))
    b.r("330", f("LEDB_{p}"), f("LEDO_{p}"))
    b.r("100k", f("LED_{p}"), "GND")
    b.c("10u", "+5V")
    b.c("100n", "+5V")
    b.c("10u", f("VBUS_{p}"))
    b.c("100n", "+3V3")
    b.row(2)


def build_pack_input(b, i):
    """Pack input i: TVS, ideal diode, and for inputs 1-4 the priority P-FET (body diode = waiting path)."""
    b.group = f"pack{i}"
    pk, vm = f"PACK{i}", (f"VM{i}" if i < 5 else "VBAT")
    b.part("D", "Device:D_TVS", "SMF4L9.0CA", "keyboard:D_SOD-123FL_Littelfuse", (24, 12), {1: pk, 2: "GND"},
           {"MPN": "Littelfuse SMF4L9.0CA"})
    b.part("U", "keyboard:LM74610QDGK", "LM74610-Q1", "Package_SO:VSSOP-8_3x3mm_P0.65mm", (34, 16),
           {4: pk, 8: vm, 6: f"IDG{i}", 2: f"IDG{i}", 1: f"CPL{i}", 7: f"CPH{i}", 3: None, 5: None},
           {"MPN": "TI LM74610QDGKRQ1"})
    # SO-8 from the LM74610 datasheet's FET table: 5.6 mOhm max at 4.5 V; at 4.5 A about 0.15 W in the channel plus
    # 0.1-0.3 W for the 2-8 % of the time the LM74610 leaves it on the body diode (the 2 x 2 mm CSD17313Q2 was
    # package-limited to 5 A)
    b.part("Q", "keyboard:SQ4184EY", "SQ4184EY", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", (26, 18),
           {4: f"IDG{i}", 1: pk, 2: pk, 3: pk, 5: vm, 6: vm, 7: vm, 8: vm}, {"MPN": "Vishay SQ4184EY-T1_GE3"})
    b.c("1u", f"CPH{i}", f"CPL{i}")
    if i < 5:
        # on only while no healthy pack sits below: BLK high -> EN low -> gate at VBAT (off, body diode path)
        b.pfet(f"PG{i}", "VBAT", vm)
        b.dual_nfet(f"BLK{i}", f"PEN{i}", "GND", f"PEN{i}", f"PG{i}", "GND")
        b.bat54c(f"OK{i + 1}", f"BLK{i + 1}" if i < 4 else f"OK{i + 1}", f"BLK{i}")
        b.r("1M", "VBAT", f"PG{i}")
        b.r("2.2M", "VBAT", f"PEN{i}")
        b.r("4.7M", f"BLK{i}", "GND")
    if i > 1:
        # "healthy" supervisor of this pack: falls at 4.3 V, re-arms only above about 5.0 V (910k feedback;
        # tools/sim_priority.py). The bleeder (on while the hub runs) keeps an empty slot's input low against
        # the ideal diode's reverse leakage, which would otherwise read as a healthy pack.
        b.supervisor("TPS3840PL43", f"PVDD{i}", f"OK{i}")
        b.r("100k", pk, f"PVDD{i}")
        b.r("910k", f"PVDD{i}", f"OK{i}")
        b.schottky("GND", f"PVDD{i}")  # a reversed pack must not pull the supervisor below -0.3 V
        b.c("1u", f"PVDD{i}")
        b.r("22k", pk, f"BLD{i}")
    if i != 1:  # compact rows
        b.row(2)


def build_conn():
    b = Board(436)
    b.part("J", "Connector_Generic:Conn_02x25_Odd_Even", "STACK (ESQ, socket up)",
           FP_STACK, (44, 32), conn(STACK, STACK_RESERVED), {"MPN": MPN_STACK})
    b.part("J", "Connector_Generic:Conn_01x11", "J_USB (host port board)", FP_GH11, (36, 30), J_USB, {"MPN": "JST SM11B-GHS-TB"})
    b.part("J", "Connector_Generic:Conn_02x08_Odd_Even", "CHAIN (to AA module 1)",
           FP_TARGET, (40, 24), CHAIN, {"MPN": MPN_TARGET})
    # LED data level shifter, one for the three ports; outputs low by default
    b.part("U", "keyboard:74x125_SO14", "74AHCT125", "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm", (34, 26),
           {1: "GND", 2: "LED_A", 3: "LEDB_A", 4: "GND", 5: "LED_B", 6: "LEDB_B", 10: "GND", 9: "LED_C", 8: "LEDB_C",
            13: "+5V", 12: "GND", 11: None, 14: "+5V", 7: "GND"}, {"MPN": "74AHCT125, SOIC-14"})
    b.c("100n", "+5V")
    b.r("10k", "+3V3", "PORT_FLT")
    b.r("100k", "+3V3", "MISO")
    b.r("100k", "+5V", "CHG_HI")
    b.r("0R", "CHG_HI", "GND", dnp=True)
    b.r("100k", "CC1", "CC1_SENSE")
    b.r("100k", "CC2", "CC2_SENSE")
    b.c("10n", "CC1_SENSE")
    b.c("10n", "CC2_SENSE")
    b.row(2)
    for p in PORTS:
        build_port(b, p)
    for i in (2, 3, 4, 1, 5):  # 1 and 5 are the short ones and share a row
        build_pack_input(b, i)
    b.group = "sense"
    # bleeder switches for pack inputs 2-5, on with the logic rail
    b.dual_nfet("+3V3", "BLD2", "GND", "+3V3", "BLD3", "GND")
    b.dual_nfet("+3V3", "BLD4", "GND", "+3V3", "BLD5", "GND")
    # UVLO (rev 8.1): supervisor on the highest pack through Schottkys, 10k, 1u
    b.bat54c("PACK1", "PACK2", "SENSE_K")
    b.bat54c("PACK3", "PACK4", "SENSE_K")
    b.schottky("PACK5", "SENSE_K")
    b.r("10k", "SENSE_K", "UVLO_VDD")
    b.c("1u", "UVLO_VDD")
    b.supervisor("TPS3840PL40", "UVLO_VDD", "PWR_SW_A")
    # pack voltage to the ADC: 200k / 100k switched on the high side
    b.part("Q", "keyboard:CSD25483F4", "CSD25483F4", "keyboard:TI_PicoStar-3_1.0x0.6mm_YJC0003A", (26, 12), {1: "DIV_G", 2: "SENSE_K", 3: "DIV_TOP"},
           {"MPN": "TI CSD25483F4"})
    b.r("470k", "SENSE_K", "DIV_G")
    b.r("200k", "DIV_TOP", "VBAT_SENSE")
    b.r("100k", "VBAT_SENSE", "GND")
    b.c("100n", "VBAT_SENSE")
    b.r("100k", "BAT_DIV_EN", "GND")
    b.dual_nfet("BAT_DIV_EN", "DIV_G", "GND", "GND", "GND", "GND")
    b.row(2)
    b.group = "switch"
    # battery switch VBAT -> SYS: on with the power switch AND UVLO OK AND no USB
    b.pfet("QB_G", "VBAT", "SYS")
    b.r("1M", "VBAT", "QB_G")
    b.dual_nfet("PWR_SW_B", "QB_G", "N12", "NVBUS", "N12", "GND")
    b.r("4.7M", "PWR_SW_B", "GND")
    b.r("1M", "VBAT", "NVBUS")
    # USB into SYS, with priority: detect, delayed turn-on
    b.pfet("QU_G", "SYS", "VBUS_IN")
    b.r("1k", "SYS", "QU_G")  # off within microseconds, before the battery switch closes (tools/sim_switchover.py)
    b.dual_nfet("USB_OK", "NVBUS", "GND", "USB_DLY", "QU_G", "GND")
    # 3.6 V: a host inside the USB limits (4.0 V at the connector at 3 A) never reads as absent
    b.supervisor("TPS3840PL36", "VBUS_IN", "USB_OK")
    b.r("2.2M", "USB_OK", "USB_DLY")
    b.c("22n", "USB_DLY")
    b.schottky("USB_DLY", "USB_OK")
    b.r("100k", "VBUS_IN", "GND")
    b.c("100n", "VBUS_IN")
    b.r("10k", "USB_OK", "USB_PRESENT")  # 5.5k source: pulls an RP2350-E9 pad low
    b.r("15k", "USB_PRESENT", "GND")  # 2.3 V at the Pico with VBUS at 3.8 V, 3.3 V at 5.5 V
    b.r("0R", "AUX_5V", "VBUS_IN", dnp=True)
    b.row(2)
    b.group = "conv"
    # SYS bulk and the 5 V buck-boost (TPS552892, datasheet section 8.2: 400 kHz, 4.7 uH, PFM at light load)
    for _ in range(4):
        b.c("47u", "SYS", fp=FP_C1210)
    b.c("10u", "SYS")
    b.c("100n", "SYS")
    b.bulk("SYS")  # carries the hub over the USB-to-battery hand-over
    b.part("U", "keyboard:TPS552892RYQ", "TPS552892", "keyboard:TI_VQFN-HR-21_5x3mm_RYQ0021A", (40, 24),
           {7: "SYS", 1: "CONV_EN", 2: "GND", 5: "GND", 6: "FSW", 21: None, 18: "VCC5", 20: "BOOT1", 8: "L1",
            11: "+5V", 12: "+5V", 13: "+5V", 14: "FB", 15: "COMP", 16: None, 3: None, 4: None, 19: "BOOT2", 10: "L2",
            17: "GND", 9: "GND"}, {"MPN": "TI TPS552892RYQR"})
    b.part("L", "Device:L", "4.7u", "Inductor_SMD:L_Coilcraft_XAL7070-XXX", (10, 22), {1: "L1", 2: "L2"},
           {"MPN": "Coilcraft XAL7070-472ME (Isat 15 A, 14.3 mOhm)"})
    # EN/UVLO: on above about 3.5 V, off below about 2.95 V (5 uA hysteresis current in the 100k), so the converter
    # never runs under its 3.0 V minimum when a pack sags
    b.r("100k", "SYS", "CONV_EN")
    b.r("54.9k", "CONV_EN", "GND")
    b.r("49.9k", "FSW", "GND")  # 400 kHz
    b.c("100n", "BOOT1", "L1")
    b.c("100n", "BOOT2", "L2")
    b.c("22u", "VCC5", fp=FP_C1210)  # more than 4.7 uF asked for, after DC bias
    b.c("1u", "VCC5", fp=FP_C0603)  # right at pins 17 / 18 (user, 2026-11-14: the 1210 cannot sit nearer than 2.4 mm)
    b.r("100k", "+5V", "FB")  # 1.2 V x (1 + 100k / 31.6k) = 5.00 V
    b.r("31.6k", "FB", "GND")
    b.r("12k", "COMP", "COMP_C")  # crossover about 4 kHz with 300 uF on +5V (worst case 3.6 V in, 3.5 A)
    b.c("15n", "COMP_C")
    b.c("470p", "COMP")
    for _ in range(3):
        b.c("22u", "+5V", fp=FP_C1210)
    b.c("100n", "+5V")
    b.bulk("+5V")  # the TPS25810 asks for 120 uF or more on its input
    for net in ("GND", "SYS", "+3V3", "VBAT"):
        b.flag(net)
    w, h = b.finish(
        "Hub connector layer (spec sections 1, 3, 3a). J1 = frozen stack connector to the core layer; +3V3 comes from the Pico.\n"
        "Module ports A-C: hub column of the wire plan (SCK on TX+, its return on TX-, MOSI on RX+, MISO on RX-, CS on D+, INT on D-, LED data on SBU).\n"
        "TPS25810 per port: CHG high, CHG_HI 100k to +5V = 3 A advertised, 3.4 A limit (fit the DNP 0R to GND for 1.5 A / 1.7 A); UFP low = sink attached (DET).\n"
        "74LVC125A per port: SCK, MOSI and the MISO return are enabled only while that port's CS is low; the CS output only while DET is low,\n"
        "so an empty or unpowered port, or a phone that never answers, sees no SPI. CS idles high through 10k. One 74AHCT125 shifts LED data to 5 V.\n"
        "Pack inputs 1 (next to the hub) to 5 (lowest module): SMF4L9.0CA, LM74610-Q1 + SQ4184EY ideal diode; inputs 1-4 then pass a CSD25402Q3A\n"
        "that is on only while no healthy pack sits below (BLKn low); otherwise the pack waits behind the FET's body diode and takes over without a gap.\n"
        "Healthy = TPS3840PL43 on the pack through 100k / 1u, 910k from VDD to its output: falls at about 4.3 V, re-arms above about 5.0 V (a swapped-in charged pack).\n"
        "22k bleeder per pack input 2-5, switched by +3V3: an empty slot floats up through the ideal diode's leakage and must not read as healthy (tools/sim_priority.py).\n"
        "UVLO, battery switch, USB switch, delay, pack divider: rev 8.1 values (TPS3840PL40, 10k / 1u, 1M, 4.7M, 2.2M / 22n, 200k / 100k), except:\n"
        "USB detect TPS3840PL36 (a host sagging to 4.0 V at 3 A stays 'present'), 1k on the USB switch gate (break before make), 220u on SYS (tools/sim_switchover.py).\n"
        "TPS552892 makes +5V from SYS on USB and on battery (3.5 A on USB or several packs; one pack gives about 8-10 W): MODE low = PFM at light load,\n"
        "400 kHz (49.9k), FB 100k / 31.6k, EN/UVLO 100k / 54.9k (on above 3.5 V, off below 2.95 V),\n"
        "ISP = ISN = VOUT (no output current limit; the ports have their own), EXTVCC and CDC open (internal VCC, no cable compensation), DITH/SYNC to GND.\n"
        "Layout (M2): AGND (pin 17) and PGND (pin 9) join only at the VCC capacitor; boot capacitors at the pins; FB and COMP away from L1 / L2.\n"
        "DNP 0R from AUX_5V to VBUS_IN: reserved for a later Qi module. Footprints still open (M2): TPS552892, CSD25483F4, inductor.")
    return b, w, h


# ---- battery module ----------------------------------------------------------------------------------------

def build_battery():
    b = Board(120)
    b.part("BT", "Device:Battery", "4xAA NiMH", "keyboard:BatteryHolder_MPD_BC4AAPC_4xAA", (20, 22), {1: "CELL+", 2: "GND"}, {"MPN": "MPD BC4AAPC"})
    # 5 A hold (4.2 A at 40 C, 3.3 A at 60 C), 10 A trip, 25 mOhm max: one pack feeds a 3 A port (user, 2026-11-13)
    b.part("F", "Device:Polyfuse", "MF-LSMF500/16X", "Fuse:Fuse_2920_7451Metric_Pad2.10x5.45mm_HandSolder", (12, 22),
           {1: "CELL+", 2: "PACK1"}, {"MPN": "Bourns MF-LSMF500/16X-2"})
    # up: own pack on PACK1, packs from below shifted by one; down: what the modules below deliver
    up = dict(CHAIN)
    down = {p: {"PACK1": "PACK2", "PACK2": "PACK3", "PACK3": "PACK4", "PACK4": "PACK5", "PACK5": None}.get(n, n)
            for p, n in CHAIN.items()}
    b.part("J", "Connector_Generic:Conn_02x08_Odd_Even", "CHAIN UP (pogo pins)",
           "Connector_PinHeader_2.54mm:PinHeader_2x08_P2.54mm_Vertical", (40, 24), up,
           {"MPN": "Samtec DW-08-17-T-D-254 riser to the cap board (Mill-Max 827-22-016-10-004101 spring pins)"})
    b.part("J", "Connector_Generic:Conn_02x08_Odd_Even", "CHAIN DOWN (target pads)",
           FP_TARGET, (40, 24), down, {"MPN": MPN_TARGET})
    b.flag("GND")
    w, h = b.finish(
        "AA battery module (spec section 3): passive. 4 x AA NiMH in series (alkaline tolerated), one PTC in the pack lead.\n"
        "Line shift: this module's pack leaves upwards on PACK1; PACK1-PACK4 arriving from the modules below leave as PACK2-PACK5;\n"
        "a sixth module's pack ends here. So the hub input number is the module's position counted from the hub, 5 = lowest.\n"
        "Chain 2x8 is reversal-safe (pin k meets pin 17-k). GND and AUX_5V pass straight through. Holder footprint (BC4AAPC) at M2.")
    return b, w, h


# ---- cap board of the chain seam --------------------------------------------------------------------------

def build_cap():
    """Small board on top of each battery module's riser: riser pin n to spring pin n, nothing else."""
    b = Board(120)
    line = {p: f"LINE{p}" for p in CHAIN}
    b.part("J", "Connector_Generic:Conn_02x08_Odd_Even", "RISER (from the battery board)",
           "Connector_PinHeader_2.54mm:PinHeader_2x08_P2.54mm_Vertical", (40, 24), line,
           {"MPN": "upper end of the Samtec DW-08-17-T-D-254 on the battery board, soldered"})
    b.part("J", "Connector_Generic:Conn_02x08_Odd_Even", "SPRING PINS (to the board above)",
           "Connector_PinHeader_2.54mm:PinHeader_2x08_P2.54mm_Vertical", (40, 24), line,
           {"MPN": "Mill-Max 827-22-016-10-004101 spring-pin strip [check its drawing]"})
    w, h = b.finish(
        "Cap board of the battery chain seam (spec section 3a): sits on the riser of a battery board and carries the spring-pin\n"
        "strip that presses on the target pads of the board above. Pin n to pin n, 16 lines, no parts. Nets are numbered by\n"
        "pin (LINE1-LINE16), not by pack: the two pins of a pack line are joined on the battery board and the connector layer.")
    return b, w, h


# ---- generate and verify ---------------------------------------------------------------------------------

BOARDS = {"hub-core": ("Hub core layer", build_core), "hub-conn": ("Hub connector layer", build_conn),
          "battery": ("AA battery module", build_battery), "chain-cap": ("Chain seam cap board", build_cap)}


def table_nets(b):
    nets = {}
    for ref, _lib, _val, _fp, _pos, pins, _props in b.parts:
        for pin, net in pins.items():
            if net not in (None, "-"):
                nets.setdefault(net, []).append(f"{ref}.{pin}")
    return nets


def generate(name, title, b, w, h):
    path = HW / name / f"{name}.kicad_sch"
    schlib.build(name, title, 0, b.parts, b.flags, b.notes, paper=paper_for(w, h)).save(str(path))
    schlib.post_process(path, b.dnp, {}, {})
    normalise_uuids(path, {str(uuid.uuid5(uuid.NAMESPACE_URL, f"keyboard/{name}/{p[0]}")) for p in b.parts})
    schlib.to_current_format(path)
    print("wrote", path)


def cross_checks(boards):
    """Design rules that span boards or tables; returns a list of error strings."""
    err = []
    core, cn, bat = (table_nets(boards[n]) for n in ("hub-core", "hub-conn", "battery"))
    # every stack net is used on the core; on the connector layer all but the reserved ones
    for pin, net in STACK.items():
        if f"J1.{pin}" not in core.get(net, []):
            err.append(f"core J1.{pin} is not {net}")
        if net not in STACK_RESERVED and f"J1.{pin}" not in cn.get(net, []):
            err.append(f"conn J1.{pin} is not {net}")
    # every Pico GPIO net reaches the stack
    for g, net in PICO_GPIO.items():
        if net not in STACK.values():
            err.append(f"GP{g} {net} is not on the stack connector")
    if len(set(PICO_GPIO.values())) != len(PICO_GPIO):
        err.append("a net is on two Pico pins")
    # chain: reversal-safe, and a module's down side is its up side shifted by one
    for p, n in CHAIN.items():
        if CHAIN[17 - p] != n:
            err.append(f"chain pin {p} is not mirrored")
    for k in range(1, 5):
        up = sorted(x for x in bat[f"PACK{k + 1}"] if x.startswith("J1."))
        down = sorted(x.replace("J2.", "J1.") for x in bat[f"PACK{k + 1}"] if x.startswith("J2."))
        want = sorted(f"J1.{p}" for p, n in CHAIN.items() if n == f"PACK{k}")
        if down != want:
            err.append(f"battery: PACK{k} from below does not leave as PACK{k + 1} ({down} / {up})")
    # hub receptacles follow the wire plan; module side (sch_keys.RECEPTACLE) is the cable-crossed counterpart
    import sch_keys
    cross = {"A2": "B11", "B2": "A11", "A3": "B10", "B3": "A10", "B11": "A2", "A11": "B2", "B10": "A3", "A10": "B3"}
    mod = {pin: net for net, pins in sch_keys.RECEPTACLE.items() for pin in pins}
    hub = {pin: net for net, pins in RECEPTACLE_HUB.items() for pin in pins}
    same = {"SCK_{p}": "SCK", "MOSI_{p}": "MOSI", "MISO_{p}": "MISO_CONN", "GND": "GND"}
    for hp, mp in cross.items():
        if same.get(hub[hp]) != mod[mp]:
            err.append(f"wire plan: hub {hp} {hub[hp]} meets module {mp} {mod[mp]}")
    return err


# ---- hub pin map as data for the firmware ----------------------------------------------------------------

PINMAP = schlib.ROOT / "firmware" / "hub-pinmap.json"
# what the firmware needs to know about each net: direction seen from the Pico, active level, state at reset
SIGNALS = {
    "EN": ("out", "high", "port power on; 10k pull-down, off at reset"),
    "DET": ("in", "low", "sink (Rd) attached and VBUS on; 10k pull-up"),
    "INT": ("in", "low", "module's open-drain interrupt; pull-up is on the module, enable the internal pull-up while DET is low"),
    "CS": ("out", "low", "expander chip select; 10k pull-up; reaches the cable only while DET is low"),
    "LED": ("out", "data", "SK6812 data, shifted to 5 V; 100k pull-down, keep low while the module's LED rail is off"),
    "MISO": ("in", "spi0", "SPI0 RX; 100k pull-up"), "SCK": ("out", "spi0", "SPI0 SCK"),
    "MOSI": ("out", "spi0", "SPI0 TX"),
    "PORT_FLT": ("in", "low", "a port is in current limit or too hot (wired-OR); 10k pull-up"),
    "USB_PRESENT": ("in", "high", "host VBUS present (above about 3.8 V); 10k / 15k divider, no pull needed"),
    "BAT_DIV_EN": ("out", "high", "switches the pack divider on; 100k pull-down"),
    "CC1_SENSE": ("adc", "analog", "host CC1 through 100k / 10n; Rp level gives the current cap"),
    "CC2_SENSE": ("adc", "analog", "host CC2 through 100k / 10n"),
    "VBAT_SENSE": ("adc", "analog", "highest pack (less a Schottky drop) x 1/3 while BAT_DIV_EN is high; 100n, wait 50 ms"),
    "SDA": ("i2c", "i2c0", "reserved, expansion; 4.7k pull-up"), "SCL": ("i2c", "i2c0", "reserved, expansion; 4.7k pull-up"),
}


def pinmap():
    import sch_keys
    gpio = {}
    for g, net in sorted(PICO_GPIO.items()):
        base, _, port = net.partition("_") if net.split("_")[-1] in PORTS and net.count("_") == 1 else (net, "", "")
        kind, active, note = SIGNALS[base]
        gpio[f"GP{g}"] = {"gpio": g, "net": net, "kind": kind, "active": active, "note": note,
                          **({"port": port} if port else {})}
    ports = {p: {base.lower(): g for g, net in PICO_GPIO.items() for base in ("EN", "DET", "INT", "CS", "LED")
                 if net == f"{base}_{p}"} for p in PORTS}
    spi = {k.lower(): g for g, net in PICO_GPIO.items() for k in ("SCK", "MOSI", "MISO") if net == k}
    return {"_": "Generated by tools/sch_hub.py from its tables; do not edit. Spec: plans/keyboard.md section 3a.",
            "board": "Raspberry Pi Pico 2 W", "spi": {"bus": 0, **spi}, "ports": ports, "gpio": gpio,
            "adc": {"vbat_ratio": 3, "vref": 3.3},
            "expander_address": {name: [addr for _ref, addr, _roles in spec["chips"]]
                                 for name, spec in sch_keys.SPEC.items()}}


def pinmap_text():
    return json.dumps(pinmap(), indent=2) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="only verify the schematics on disk")
    ap.add_argument("--only", help="generate this board only (the others are verified)")
    args = ap.parse_args()
    built = {}
    for name, (title, fn) in BOARDS.items():
        b, w, h = fn()
        built[name] = b
        if not args.verify and args.only in (None, name):
            generate(name, title, b, w, h)
        print(f"{name}: {len(b.parts)} parts")
        schlib.check_netlist(HW / name / f"{name}.kicad_sch", table_nets(b))
        comps, _, _ = read_netlist(HW / name / f"{name}.kicad_sch")
        if set(comps) != {p[0] for p in b.parts}:
            sys.exit(f"{name}: parts on the sheet differ from the table")
    if not args.verify and not args.only:
        PINMAP.write_text(pinmap_text())
        print("wrote", PINMAP)
    err = cross_checks(built)
    if not PINMAP.exists() or PINMAP.read_text() != pinmap_text():
        err.append(f"{PINMAP.name} differs from the tables (run tools/sch_hub.py)")
    for e in err:
        print("FAIL", e)
    print(f"cross checks: {len(err)} failed")
    sys.exit(1 if err else 0)


if __name__ == "__main__":
    main()
