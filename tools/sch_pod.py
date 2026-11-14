#!/usr/bin/env python3
"""Capture the three wireless boards of spec section 2b (M3b session 2) and check their netlists.

  pod        radio board in a key module's bay (and on the hub's carrier): Raytac MDBT50Q-1MV2 (nRF52840), 2x6 bay
             socket, 5 V level shifter for LED data, 32.768 kHz crystal, USB-C service port (USB 2.0 on the module's
             own USB; it does not power the module), Cortex debug header (SWD), reset button, status LED, 6-pin lead.
  pod-power  power board at the cells: pack connector, fuse, reverse-polarity FET, on / off slide switch on the
             converters' enables, TPS629210 (3.3 V, always on), TPS630701 (5 V, off unless EN_5V) behind a TPS2553
             current cap (about 0.5 A), pack divider, 6-pin lead.
  hub-radio  passive carrier on hub-core's 2x5 expansion header: a bay header for the same pod, UART on the pod's
             MISO / MOSI pins, spare pin tied low (the pod then knows it sits in the hub).

Datasheets read for every pin and value below are in build/ds (tps629210, tps63070, tps2553, mdbt50q, nrf52840_ps,
sn74ahct1g125, ao3401a, bourns_mf-msmf, jst/eGH, usb4085). Key boards, hub-core and hub-conn are not changed.

Run:   .venv/bin/python tools/sch_pod.py            (writes the three schematics, the pin map, then verifies)
Check: .venv/bin/python tools/sch_pod.py --verify   (netlists on disk only; tools/kicad-check.sh runs this)
"""

import argparse
import json
import re
import sys
import uuid
from pathlib import Path

import schlib
from sch_keys import BAY, FP_HDR2, FP_SOCK2, Checker, Sheet, Strip, normalise_uuids, paper_for, read_netlist, report

HW = schlib.ROOT / "hardware"
PINMAP = schlib.ROOT / "firmware" / "pod-pinmap.json"
STOCK_FP = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")

FP_R = "Resistor_SMD:R_0603_1608Metric"
FP_C = "Capacitor_SMD:C_0603_1608Metric"
FP_C0805 = "Capacitor_SMD:C_0805_2012Metric"
FP_C1206 = "Capacitor_SMD:C_1206_3216Metric"
FP_GH6 = "Connector_JST:JST_GH_SM06B-GHS-TB_1x06-1MP_P1.25mm_Horizontal"
FP_GH6V = "Connector_JST:JST_GH_BM06B-GHS-TBT_1x06-1MP_P1.25mm_Vertical"      # power board: plugged from above
FP_SOT23_6 = "keyboard:TI_SOT-23-6_DBV0006A"
FP_TP = "TestPoint:TestPoint_Pad_D1.5mm"

# 6-wire lead, JST GH, wired 1:1 (user, 2026-11-14). Pin -> (net on the pod, net on the power board).
LEAD = {1: ("+5V", "+5V_LED"), 2: ("GND", "GND"), 3: ("EN_5V", "EN_5V"), 4: ("VBAT_SENSE", "VBAT_SENSE"),
        5: ("GND", "GND"), 6: ("+3V3", "+3V3")}

# MDBT50Q-1MV2 pin table (Raytac datasheet section 5, checked against KiCad's RF_Module symbol): module pin -> name
MODULE = {1: "GND", 2: "GND", 3: "P1.10", 4: "P1.11", 5: "P1.12", 6: "P1.13", 7: "P1.14", 8: "P1.15", 9: "P0.03",
          10: "P0.29", 11: "P0.02", 12: "P0.31", 13: "P0.28", 14: "P0.30", 15: "GND", 16: "P0.27", 17: "P0.00",
          18: "P0.01", 19: "P0.26", 20: "P0.04", 21: "P0.05", 22: "P0.06", 23: "P0.07", 24: "P0.08", 25: "P1.08",
          26: "P1.09", 27: "P0.11", 28: "VDD", 29: "P0.12", 30: "VDDH", 31: "DCCH", 32: "VBUS", 33: "GND", 34: "D-",
          35: "D+", 36: "P0.14", 37: "P0.13", 38: "P0.16", 39: "P0.15", 40: "P0.18", 41: "P0.17", 42: "P0.19",
          43: "P0.21", 44: "P0.20", 45: "P0.23", 46: "P0.22", 47: "P1.00", 48: "P0.24", 49: "P0.25", 50: "P1.02",
          51: "SWDIO", 52: "P0.09", 53: "SWDCLK", 54: "P0.10", 55: "GND", 56: "P1.04", 57: "P1.06", 58: "P1.07",
          59: "P1.05", 60: "P1.03", 61: "P1.01"}
# "standard drive, low frequency I/O only" (near the radio): Raytac section 2.6, nRF52840 PS pin table
LOW_FREQ = {"P0.02", "P0.03", "P0.09", "P0.10", "P0.28", "P0.29", "P0.30", "P0.31",
            *(f"P1.{i:02d}" for i in (1, 2, 3, 4, 5, 6, 7, 10, 11, 12, 13, 14, 15))}
ANALOG = {"P0.02": 0, "P0.03": 1, "P0.04": 2, "P0.05": 3, "P0.28": 4, "P0.29": 5, "P0.30": 6, "P0.31": 7}

# Pod pin map: function -> (nRF52840 pin, net at the module pin, note). All on the module's bay-side pad row
# (pins 36-49) except the analog input and the crystal; pins may be swapped at layout, the map is regenerated.
POD = {
    "SCK": ("P0.19", "SCK_R", "SPI clock to the expander(s), 33 R at the pod"),
    "MOSI": ("P0.21", "MOSI_R", "33 R at the pod; in the hub: UART TX of the pod (to GP1)"),
    "MISO": ("P0.20", "MISO", "in the hub: UART RX of the pod (from GP0)"),
    "CS": ("P0.23", "CS", "active low, 100 k pull-up on the pod"),
    "INT": ("P0.22", "INT", "expander interrupt, open drain, active low, 100 k pull-up on the pod; wake source"),
    "LED_DATA": ("P0.24", "LED_3V3", "to the 5 V level shifter (74AHCT1G125), 100 k pull-down; hold low while the key board's LED rail is off"),
    "HUB_DETECT": ("P0.25", "HUB_DET", "through 1 k to bay pin 6: tied low on the hub carrier, open on a key board; read once with the internal pull-up, then pull-up off, never drive"),
    "EN_5V": ("P0.15", "EN_5V", "high = LED rail converter on; 100 k pull-down on the power board (off by default)"),
    "VBAT_SENSE": ("P0.04", "VBAT_SENSE", "AIN2; pack voltage x 680 / 2880 (2.2 M / 680 k), 100 nF at the pin: sample slowly"),
    "STATUS_LED": ("P0.06", "STATUS", "high = on (1 k, LED to GND)"),
    "XL1": ("P0.00", "XL1", "32.768 kHz crystal"),
    "XL2": ("P0.01", "XL2", "32.768 kHz crystal"),
    "RESET": ("P0.18", "RESET", "nRESET: button to GND, debug header pin 10; works only once UICR PSELRESET[0] and [1] select P0.18"),
    "SWO": ("P1.00", "SWO", "debug header pin 6"),
}
FAST = ("SCK", "MOSI", "MISO", "CS", "LED_DATA")
PIN_OF = {v: k for k, v in MODULE.items() if v != "GND"}

# IC pin tables typed from the datasheets a second time (the symbols in gen_kicad.py are the first): number -> name
TPS629210 = {1: "FB/VSET", 2: "PG", 3: "VOS", 4: "SW", 5: "GND", 6: "VIN", 7: "EN", 8: "MODE/S-CONF"}
TPS630701 = {1: "PS/SYNC", 2: "PG", 3: "VAUX", 4: "GND", 5: "FB", 6: "FB2", 7: "VOUT", 8: "VOUT", 9: "L2", 10: "PGND",
             11: "L1", 12: "VIN", 13: "VIN", 14: "EN", 15: "VSEL"}
TPS2553 = {1: "IN", 2: "GND", 3: "EN", 4: "FAULT", 5: "ILIM", 6: "OUT"}
DIVIDER = ("2.2M", "680k")          # VSW -> VBAT_SENSE -> GND
# Pack cut-off on the 3.3 V converter's precise enable (rising 1.0 V, falling 0.9 V): VSW -> RTOP -> EN -> 330 k -> GND.
# On at 1.0 V per cell, off at 0.9 V per cell. One board for every module (user, 2026-11-14): 1.65 M is always in
# (6 cells, as delivered); solder jumper JP1 puts 2.55 M in parallel (1.0 M) for 4 cells.
UVLO_BOTTOM = "330k"
UVLO_TOP = "1.65M"
UVLO_PAR = "2.55M"
FP_L33 = "keyboard:L_Coilcraft_XGL3530"
FP_L5 = "keyboard:L_Coilcraft_XFL4020"
FP_RNM = "keyboard:TI_VQFN-HR-15_2.5x3mm_RNM0015A"
EXPANSION = {1: "+3V3", 2: "+5V", 3: "SDA", 4: "SCL", 5: "SP1", 6: "SP2", 7: "SP3", 8: "SP4", 9: "GND", 10: "GND"}
# carrier: bay pin -> expansion pin (SDA = GP0 = UART0 TX of the Pico, SCL = GP1 = UART0 RX)
CARRIER = {1: 2, 2: 2, 3: 9, 5: 1, 6: 9, 7: 7, 8: 5, 9: 3, 10: 4, 11: 10, 12: 6}


class S(Sheet):
    def r(self, value, n1, n2, pos, tol="1%"):
        self.nr += 1
        self.part(f"R{self.nr}", "Device:R", value, FP_R, pos, {"1": n1, "2": n2}, {"Tolerance": tol})

    def c(self, value, n1, n2, pos, fp=FP_C, v="16V", diel="X7R"):
        self.nc += 1
        self.part(f"C{self.nc}", "Device:C", value, fp, pos, {"1": n1, "2": n2}, {"Voltage": v, "Dielectric": diel})


def build_pod():
    s = S()
    pins = {str(n): ("GND" if name == "GND" else None) for n, name in MODULE.items()}
    for fn, (gpio, net, _) in POD.items():
        pins[str(PIN_OF[gpio])] = net
    pins.update({"28": "+3V3", "30": "+3V3", "31": None, "32": "VBUS_NRF", "34": "USB_DN", "35": "USB_DP",
                 "51": "SWDIO", "53": "SWDCLK"})
    s.part("U1", "RF_Module:MDBT50Q-1MV2", "MDBT50Q-1MV2", "RF_Module:Raytac_MDBT50Q", (60, 40), pins,
           {"MPN": "Raytac MDBT50Q-1MV2 (nRF52840, chip antenna)"})
    s.part("J1", "Connector_Generic:Conn_02x06_Odd_Even", "BAY (socket)", FP_SOCK2, (112, 16),
           {str(p): n for p, n in BAY.items()}, {"MPN": "generic 2x6 2.54 mm socket"})
    s.part("J2", "Connector_Generic:Conn_01x06", "LEAD", FP_GH6, (112, 36),
           {str(p): n[0] for p, n in LEAD.items()}, {"MPN": "JST SM06B-GHS-TB"})
    s.part("U2", "74xGxx:74AHCT1G125", "74AHCT1G125", "Package_TO_SOT_SMD:SOT-23-5", (112, 56),
           {"1": "GND", "2": "LED_3V3", "3": "GND", "4": "LED_Y", "5": "+5V"}, {"MPN": "TI SN74AHCT1G125DBVR"})
    s.part("J3", "Connector:USB_C_Receptacle_USB2.0_16P", "USB4085-GF-A", "Connector_USB:USB_C_Receptacle_GCT_USB4085", (140, 30),
           {"A4": "VBUS_USB", "A9": "VBUS_USB", "B4": "VBUS_USB", "B9": "VBUS_USB",
            "A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "SH": "GND",
            "A5": "CC1", "B5": "CC2", "A6": "USB_DP_C", "B6": "USB_DP_C", "A7": "USB_DN_C", "B7": "USB_DN_C",
            "A8": None, "B8": None}, {"MPN": "GCT USB4085-GF-A"})
    s.part("U3", "Power_Protection:USBLC6-2SC6", "USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6", (170, 22),
           {"1": "USB_DP_C", "6": "USB_DP_C", "3": "USB_DN_C", "4": "USB_DN_C", "5": "VBUS_USB", "2": "GND"},
           {"MPN": "ST USBLC6-2SC6"})
    s.part("J4", "Connector_Generic:Conn_02x05_Odd_Even", "SWD", "Connector_PinHeader_1.27mm:PinHeader_2x05_P1.27mm_Vertical_SMD", (170, 46),
           {"1": "+3V3", "2": "SWDIO", "3": "GND", "4": "SWDCLK", "5": "GND", "6": "SWO", "7": None, "8": None,
            "9": "GND", "10": "RESET"}, {"MPN": "2x5 1.27 mm Cortex debug header (Samtec FTSH-105-01 class)"})
    s.part("Y1", "Device:Crystal", "32.768kHz", "Crystal:Crystal_SMD_3215-2Pin_3.2x1.5mm", (12, 16),
           {"1": "XL1", "2": "XL2"}, {"MPN": "32.768 kHz, 3215, CL 9 pF, 20 ppm (ref. circuit: Raytac / Nordic)"})
    s.part("SW1", "Switch:SW_Push", "RESET", "Button_Switch_SMD:SW_SPST_PTS647_Sx38", (12, 30),
           {"1": "RESET", "2": "GND"}, {"MPN": "C&K PTS647 class"})
    s.part("D1", "Device:LED", "green", "LED_SMD:LED_0603_1608Metric", (12, 44),
           {"2": "STATUS_A", "1": "GND"}, {})
    st = Strip(104, 76, 96)
    s.r("33", "SCK_R", "SCK", st.next())
    s.r("33", "MOSI_R", "MOSI", st.next())
    s.r("100k", "+3V3", "CS", st.next())
    s.r("100k", "+3V3", "INT", st.next())
    s.r("100k", "LED_3V3", "GND", st.next())
    s.r("100", "LED_Y", "LED_DIN", st.next())
    s.r("1k", "STATUS", "STATUS_A", st.next())
    s.r("27", "USB_DP_C", "USB_DP", st.next())
    s.r("27", "USB_DN_C", "USB_DN", st.next())
    s.r("2.2", "VBUS_USB", "VBUS_NRF", st.next())
    s.r("5.1k", "CC1", "GND", st.next())
    s.r("5.1k", "CC2", "GND", st.next())
    s.r("1k", "HUB_DET", "SPARE", st.next())
    s.c("10u", "+3V3", "GND", st.next(), fp=FP_C0805, v="10V")
    s.c("100n", "+3V3", "GND", st.next())
    s.c("100n", "+5V", "GND", st.next())
    s.c("10u", "VBUS_NRF", "GND", st.next(), fp=FP_C0805, v="10V")
    s.c("12p", "XL1", "GND", st.next(), v="50V", diel="C0G")
    s.c("12p", "XL2", "GND", st.next(), v="50V", diel="C0G")
    s.c("100n", "VBAT_SENSE", "GND", st.next())
    s.flags = [("#FLG01", "+3V3", (12, 60)), ("#FLG02", "+5V", (20, 60)), ("#FLG03", "GND", (28, 60)),
               ("#FLG04", "VBUS_NRF", (36, 60))]
    s.notes = [((8, 106),
        "Radio pod (spec 2b): the bay board of a cable-free key module, and the hub's receiver on the hub-radio carrier. Radio only: 3.3 V and 5 V come in over the lead\n"
        "(J2, JST GH, 1:1 to pod-power: 1 +5V, 2 GND, 3 EN_5V, 4 VBAT_SENSE, 5 GND, 6 +3V3) and go on into the key board through J1 (pins as the port board, spec 1).\n"
        "U1 MDBT50Q-1MV2: VDD = VDDH = 3.3 V (normal-voltage mode, DCCH open; the REG1 DC/DC inductor and the 32 MHz crystal are inside the module).\n"
        "SPI on pins that are not 'low frequency I/O only'; SCK and MOSI through 33 R at the source. CS and INT: 100 k pull-ups (INT is open drain on the expander).\n"
        "LED data: 74AHCT1G125 on the 5 V pins (VIH 2 V), enable tied low, 100 R at its output (the key board has 220 R before LED1), 100 k pull-down at its input.\n"
        "Bay pin 6 (SPARE) reads low on the hub carrier and floats on a key board: internal pull-up, read once at start; 1 k in series, so a driven pin cannot short into the carrier's GND.\n"
        "USB-C J3 is the module's own USB for flashing and a console: VBUS feeds only the nRF52840's USB regulator pin (2.2 R + 10 uF), never the 3.3 V rail,\n"
        "so the pod must be powered (lead or hub) to be flashed. 27 R in D+ / D- as Raytac's reference circuit; Rd 5.1 k on CC1 / CC2; USBLC6-2 at the receptacle.\n"
        "J4: 2x5 1.27 mm Cortex debug pinout (1 VTref, 2 SWDIO, 4 SWDCLK, 6 SWO = P1.00, 10 nRESET). Y1 with 12 pF as Raytac's reference circuit (crystal CL 9 pF).\n"
        "The two M2 holes are board features (placement script), as on the port board. Pin map for the firmware: firmware/pod-pinmap.json.")]
    return s, 215, 135


def build_power():
    s = S()
    s.part("J1", "Connector_Generic:Conn_01x02", "PACK", "Connector_JST:JST_XH_S2B-XH-A_1x02_P2.50mm_Horizontal", (10, 20),
           {"1": "BAT+", "2": "GND"}, {"MPN": "JST S2B-XH-A (3 A per contact)"})
    s.part("F1", "Device:Polyfuse", "1.5A", "Fuse:Fuse_1812_4532Metric", (24, 20),
           {"1": "BAT+", "2": "VFUSE"}, {"MPN": "Bourns MF-MSMF150/16X (hold 1.5 A at 23 C, 1.08 A at 50 C, trip 3.0 A, 16 V)"})
    s.part("Q1", "Transistor_FET:AO3401A", "AO3401A", "Package_TO_SOT_SMD:SOT-23", (40, 20),
           {"1": "GATE", "2": "VPACK", "3": "VFUSE"}, {"MPN": "Alpha & Omega AO3401A"})
    s.part("SW1", "Switch:SW_SPDT", "ON / OFF", "Button_Switch_THT:SW_Slide_SPDT_Angled_CK_OS102011MA1Q", (60, 20),
           {"1": "VPACK", "2": "VSW", "3": None}, {"MPN": "C&K OS102011MA1QN1 (common = pin 2)"})
    s.part("U1", "keyboard:TPS629210DRL", "TPS629210", "Package_TO_SOT_SMD:SOT-583-8", (92, 22),
           {"6": "VPACK", "7": "EN_3V3", "8": "SCONF", "4": "SW_3V3", "3": "+3V3", "1": None, "2": None, "5": "GND"},
           {"MPN": "TI TPS629210DRLR"})
    s.part("L1", "Device:L", "2.2u", FP_L33, (120, 20), {"1": "SW_3V3", "2": "+3V3"}, {"MPN": "Coilcraft XGL3530-222ME"})
    s.part("U2", "keyboard:TPS630701RNM", "TPS630701", FP_RNM, (92, 54),
           {"12": "VPACK", "13": "VPACK", "14": "EN_5V_F", "1": "PS", "15": "GND", "11": "L5A", "9": "L5B",
            "7": "+5V_RAW", "8": "+5V_RAW", "5": "+5V_RAW", "6": None, "2": None, "3": "VAUX", "4": "GND", "10": "GND"},
           {"MPN": "TI TPS630701RNMR"})
    s.part("L2", "Device:L", "1.5u", FP_L5, (66, 56), {"1": "L5A", "2": "L5B"}, {"MPN": "Coilcraft XFL4020-152ME"})
    s.part("U3", "keyboard:TPS2553DBV", "TPS2553", FP_SOT23_6, (136, 54),
           {"1": "+5V_RAW", "3": "EN_5V_F", "5": "ILIM", "6": "+5V_LED", "4": None, "2": "GND"}, {"MPN": "TI TPS2553DBVR"})
    s.part("J2", "Connector_Generic:Conn_01x06", "LEAD", FP_GH6V, (170, 30),
           {str(p): n[1] for p, n in LEAD.items()}, {"MPN": "JST BM06B-GHS-TBT (vertical: the lead is plugged from above)"})
    for i, (net, x) in enumerate((("VPACK", 150), ("+3V3", 158), ("+5V_LED", 166), ("GND", 174)), 1):
        s.part(f"TP{i}", "Connector:TestPoint", net, FP_TP, (x, 60), {"1": net}, {})
    s.part("D1", "Device:D_Zener", "10V", "Diode_SMD:D_SOD-123", (40, 36), {"1": "VPACK", "2": "GATE"}, {"MPN": "BZT52C10 class"})
    s.part("C20", "Device:C_Polarized", "47u", "Capacitor_SMD:CP_Elec_6.3x5.8", (52, 36), {"1": "VPACK", "2": "GND"},
           {"Voltage": "25V", "MPN": "polymer or electrolytic, 6.3 mm can"})
    st = Strip(8, 84, 176)
    s.r("100k", "GATE", "GND", st.next())
    s.r(UVLO_TOP, "VSW", "EN_3V3", st.next())
    s.r(UVLO_BOTTOM, "EN_3V3", "GND", st.next())
    s.c("100n", "EN_3V3", "GND", st.next())
    s.r(DIVIDER[0], "VSW", "VBAT_SENSE", st.next())
    s.r(DIVIDER[1], "VBAT_SENSE", "GND", st.next())
    s.r("27.4k", "SCONF", "GND", st.next())
    s.c("10u", "VPACK", "GND", st.next(), fp=FP_C1206, v="25V")
    s.c("22u", "+3V3", "GND", st.next(), fp=FP_C1206, v="10V")
    s.r("100k", "VPACK", "PS", st.next())
    s.r("1k", "EN_5V", "EN_5V_F", st.next())
    s.r("100k", "EN_5V_F", "GND", st.next())
    s.c("10u", "VPACK", "GND", st.next(), fp=FP_C1206, v="25V")
    s.c("100n", "VAUX", "GND", st.next())
    s.c("22u", "+5V_RAW", "GND", st.next(), fp=FP_C1206, v="16V")
    s.c("22u", "+5V_RAW", "GND", st.next(), fp=FP_C1206, v="16V")
    s.c("10u", "+5V_RAW", "GND", st.next(), v="16V")
    s.r("49.9k", "ILIM", "GND", st.next())
    s.c("10u", "+5V_LED", "GND", st.next(), fp=FP_C0805, v="16V")
    s.r(UVLO_PAR, "VSW", "UVLO_4", st.next())
    s.c("10u", "VPACK", "GND", st.next(), v="25V", diel="X5R")     # review 1: 0603 at U2's VIN pins (datasheet C1)
    s.c("100n", "+5V_RAW", "GND", st.next())                       # review 15: at U3's IN pin
    s.part("JP1", "Jumper:SolderJumper_2_Open", "4 AA", "Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm", (150, 76),
           {"1": "UVLO_4", "2": "EN_3V3"}, {})
    s.flags = [("#FLG01", "BAT+", (10, 36)), ("#FLG02", "GND", (18, 36)), ("#FLG03", "VPACK", (26, 36)),
               ("#FLG04", "+3V3", (34, 36)), ("#FLG05", "+5V_RAW", (42, 36))]
    s.notes = [((8, 102),
        "Power board of a cable-free key module (spec 2b), in the battery rail. Pack: 4, 5 or 6 AA, NiMH or alkaline, 4.0 to about 10 V, on J1.\n"
        "F1 1.5 A hold at 23 C, 1.08 A at 50 C (user, 2026-11-14; worst case 0.85 A: LEDs at the cap on a 4.0 V pack). Q1 blocks a reversed pack (gate to GND through 100 k; |VGS| = pack voltage, 12 V absolute maximum).\n"
        "D1 clamps its gate (10 V Zener, conducts only above a fresh alkaline pack); C20 damps the ringing when the pack is plugged in.\n"
        "SW1 is the on / off switch: it carries no load current (third contact unused). On: VSW = VPACK feeds the cut-off divider on the 3.3 V converter's enable and the pack divider.\n"
        "Cut-off (review): R2 / 330 k on the precise enable (1.0 V rising, 0.9 V falling) = on at 1.0 V per cell, off at 0.9 V per cell. R2 = 1.65 M: 6 cells, as delivered.\n"
        "4 cells (numpad): bridge JP1, which puts 2.55 M in parallel (1.0 M). One board for every module (user). Off: VSW pulled to GND by the dividers, both converters in shutdown (the pod is dead, so EN_5V is low); 3 to 13 uA left (shutdown currents, 85 C worst case).\n"
        "U1 TPS629210: MODE/S-CONF 27.4 k = VSET mode, auto PFM/PWM with AEE, up to 2.5 MHz, output discharge on; FB/VSET open = 3.3 V; 2.2 uH, 22 uF; 4 uA quiescent.\n"
        "U2 TPS630701 (fixed 5.0 V): FB on VOUT, VSEL low, PS/SYNC high through 100 k = power save, 1.5 uH, 2 x 22 uF, VAUX 100 nF; a 10 uF 0603 at the VIN pins and one (C8) at the VOUT pins, as the datasheet. Enabled only by EN_5V from the pod\n"
        "(1 k in series, 100 k pull-down: off by default). U3 TPS2553 caps the LED rail: RILIM 49.9 k = 475-565 mA, constant current (not latching); FAULT is not wired; 100 nF at its IN pin.\n"
        "Pack divider 2.2 M / 680 k: 10 V -> 2.36 V at the pod's ADC pin (100 nF there); the two dividers draw 2.5 + 3.6 uA at 7.2 V while the switch is on.\n"
        "Lead J2 (JST GH, 1 A per contact, 1:1 to the pod): 1 +5V_LED, 2 GND, 3 EN_5V, 4 VBAT_SENSE, 5 GND, 6 +3V3.\n"
        "Board: tools/pcb_pod.py, 48 x 22 mm in the rear leg of the battery rail (27 mm deep; user).")]
    return s, 195, 132


def build_carrier():
    s = S()
    exp_net = {1: "+3V3", 2: "+5V", 3: "UART_H2P", 4: "UART_P2H", 5: "SP1", 6: "SP2", 7: "SP3", 8: None, 9: "GND", 10: "GND"}
    s.part("J1", "Connector_Generic:Conn_02x05_Odd_Even", "EXPANSION (socket)", "Connector_PinSocket_2.54mm:PinSocket_2x05_P2.54mm_Vertical", (20, 20),
           {str(p): n for p, n in exp_net.items()}, {"MPN": "generic 2x5 2.54 mm socket"})
    bay = {p: exp_net[CARRIER[p]] if p in CARRIER else None for p in BAY}
    s.part("J2", "Connector_Generic:Conn_02x06_Odd_Even", "BAY", FP_HDR2, (60, 20),
           {str(p): n for p, n in bay.items()}, {"MPN": "generic 2x6 2.54 mm header"})
    s.c("10u", "+3V3", "GND", (90, 20), fp=FP_C0805, v="10V")
    s.flags = [("#FLG01", "+3V3", (20, 40)), ("#FLG02", "GND", (28, 40)), ("#FLG03", "+5V", (36, 40))]
    s.notes = [((8, 52),
        "Hub carrier for the radio pod (spec 2b): passive. J1 plugs onto hub-core's 2x5 expansion header; J2 is a key board's bay header (same pins, two M2 holes\n"
        "placed by the board script), so the same pod fits. Pod 3.3 V from the Pico's 3.3 V, the pod's 5 V pins from the hub's +5V (level shifter only).\n"
        "UART: GP0 (expansion pin 3, UART0 TX of the Pico) -> bay pin 9 (the pod's MISO pin, its input); GP1 (pin 4, UART0 RX) <- bay pin 10 (the pod's MOSI pin,\n"
        "its output, 33 R on the pod). hub-core's 4.7 k pull-ups on GP0 / GP1 keep the lines high while idle.\n"
        "Bay pin 6 (SPARE) is tied to GND: the pod reads it low and knows it sits in the hub. Bay pin 4 (LED data, 5 V level) is open.\n"
        "CS -> SP1, SCK -> SP2, INT -> SP3: these reach no Pico pin today (reserved lines of the stack), wired for a later core board; SP4 open.")]
    return s, 110, 70


BUILDERS = {"pod": (build_pod, "Radio pod (nRF52840)"), "pod-power": (build_power, "Power board of a cable-free module"),
            "hub-radio": (build_carrier, "Hub carrier for the radio pod")}


def generate(name):
    fn, title = BUILDERS[name]
    s, w, h = fn()
    path = HW / name / f"{name}.kicad_sch"
    schlib.build(name, title, 0, s.parts, s.flags, s.notes, paper=paper_for(w, h)).save(str(path))
    schlib.post_process(path, set(), {}, {})
    normalise_uuids(path, {str(uuid.uuid5(uuid.NAMESPACE_URL, f"keyboard/{name}/{p[0]}")) for p in s.parts})
    schlib.to_current_format(path)
    print("wrote", path)


# ---- checks -----------------------------------------------------------------------------------------

def ohms(v):
    m = re.fullmatch(r"([\d.]+)([kM]?)", v)
    return float(m.group(1)) * {"": 1, "k": 1e3, "M": 1e6}[m.group(2)]


def load(name):
    comps, net_of, nodes = read_netlist(HW / name / f"{name}.kicad_sch")
    return Checker(name, comps, net_of, nodes)


def parts_on(c, ref, pin, prefix):
    return sorted((v, o) for _, v, o in c.partner(ref, pin, prefix))


def footprints(c, name):
    """Every part has a footprint and it exists (stock library, project library)."""
    text = (HW / name / f"{name}.kicad_sch").read_text()
    missing, empty = [], []
    for m in re.finditer(r'\(property "Reference" "([A-Z]+\d+)".*?\(property "Footprint" "([^"]*)"', text, re.S):
        ref, fp = m.groups()
        if not fp:
            empty.append(ref)
            continue
        lib, fname = fp.split(":")
        base = HW / "lib" / "keyboard.pretty" if lib == "keyboard" else STOCK_FP / f"{lib}.pretty"
        if not (base / f"{fname}.kicad_mod").exists():
            missing.append(fp)
    c.eq("footprints exist", missing, [])
    c.eq("parts without a footprint", sorted(set(empty)), [])


def verify_pod():
    c = load("pod")
    for p, n in BAY.items():
        c.eq(f"bay socket J1.{p}", c.net("J1", p), n)
    for p, (n, _) in LEAD.items():
        c.eq(f"lead J2.{p}", c.net("J2", p), n)
    used = {}
    for fn, (gpio, net, _) in POD.items():
        c.eq(f"{fn} on {gpio} (module pin {PIN_OF[gpio]})", c.net("U1", PIN_OF[gpio]), net)
        c.eq(f"{gpio} used once", gpio in used, False)
        used[gpio] = fn
    for fn in FAST:
        c.eq(f"{fn} not on a low-frequency-only pin", POD[fn][0] in LOW_FREQ, False)
    c.eq("VBAT_SENSE on an analog input", POD["VBAT_SENSE"][0] in ANALOG, True)
    c.eq("crystal pins", (POD["XL1"][0], POD["XL2"][0]), ("P0.00", "P0.01"))
    c.eq("reset pin", POD["RESET"][0], "P0.18")
    c.eq("SWO pin", POD["SWO"][0], "P1.00")
    wired = {PIN_OF[g] for g, _, _ in POD.values()} | {28, 30, 32, 34, 35, 51, 53}
    for n, name in MODULE.items():
        got = c.net("U1", n) or ""
        if name == "GND":
            c.eq(f"U1.{n} GND", got, "GND")
        elif n not in wired:
            c.eq(f"U1.{n} {name} unconnected", got.startswith("unconnected-"), True)
    c.eq("module supply", [c.net("U1", p) for p in (28, 30, 32, 34, 35, 51, 53)],
         ["+3V3", "+3V3", "VBUS_NRF", "USB_DN", "USB_DP", "SWDIO", "SWDCLK"])
    c.eq("SCK series R", parts_on(c, "J1", 12, "R"), [("33", "SCK_R")])
    c.eq("MOSI series R", parts_on(c, "J1", 10, "R"), [("33", "MOSI_R")])
    c.eq("MISO direct", (c.net("J1", 9), parts_on(c, "J1", 9, "R")), ("MISO", []))
    c.eq("CS pull-up", parts_on(c, "J1", 8, "R"), [("100k", "+3V3")])
    c.eq("INT pull-up", parts_on(c, "J1", 7, "R"), [("100k", "+3V3")])
    c.eq("level shifter", [c.net("U2", p) for p in range(1, 6)], ["GND", "LED_3V3", "GND", "LED_Y", "+5V"])
    c.eq("LED data series R", parts_on(c, "J1", 4, "R"), [("100", "LED_Y")])
    c.eq("LED data pull-down", parts_on(c, "U2", 2, "R"), [("100k", "GND")])
    c.eq("crystal", sorted([c.net("Y1", 1), c.net("Y1", 2)]), ["XL1", "XL2"])
    c.eq("crystal load", (parts_on(c, "Y1", 1, "C"), parts_on(c, "Y1", 2, "C")), ([("12p", "GND")], [("12p", "GND")]))
    for a, b, d in (("A6", "B6", "USB_DP"), ("A7", "B7", "USB_DN")):
        c.eq(f"{d} receptacle pins", (c.net("J3", a), c.net("J3", b)), (d + "_C", d + "_C"))
        c.eq(f"{d} series R", parts_on(c, "J3", a, "R"), [("27", d)])
    c.eq("D+ / D- at the module", (c.net("U1", PIN_OF["D+"]), c.net("U1", PIN_OF["D-"])), ("USB_DP", "USB_DN"))
    c.eq("CC Rd", (parts_on(c, "J3", "A5", "R"), parts_on(c, "J3", "B5", "R")), ([("5.1k", "GND")], [("5.1k", "GND")]))
    c.eq("VBUS only to the USB regulator pin", sorted(r for r, _ in c.nodes["VBUS_NRF"]), ["C4", "R10", "U1"])
    c.eq("USB VBUS not on a rail", {c.net("J3", "A4")} & {"+3V3", "+5V"}, set())
    c.eq("ESD array", [c.net("U3", p) for p in range(1, 7)], ["USB_DP_C", "GND", "USB_DN_C", "USB_DN_C", "VBUS_USB", "USB_DP_C"])
    c.eq("debug header", [c.net("J4", p) for p in (1, 2, 3, 4, 5, 6, 9, 10)],
         ["+3V3", "SWDIO", "GND", "SWDCLK", "GND", "SWO", "GND", "RESET"])
    c.eq("reset button", sorted([c.net("SW1", 1), c.net("SW1", 2)]), ["GND", "RESET"])
    c.eq("status LED", (c.net("D1", 1), parts_on(c, "D1", 2, "R")), ("GND", [("1k", "STATUS")]))
    c.eq("spare pin series R", parts_on(c, "J1", 6, "R"), [("1k", "HUB_DET")])
    c.eq("VBUS capacitor", parts_on(c, "U1", 32, "C"), [("10u", "GND")])
    c.eq("ADC capacitor", parts_on(c, "J2", 4, "C"), [("100n", "GND")])
    footprints(c, "pod")
    return c


def verify_power():
    c = load("pod-power")
    for p, (_, n) in LEAD.items():
        c.eq(f"lead J2.{p}", c.net("J2", p), n)
    want = {"U1": (TPS629210, {"VIN": "VPACK", "EN": "EN_3V3", "MODE/S-CONF": "SCONF", "SW": "SW_3V3", "VOS": "+3V3",
                               "GND": "GND", "FB/VSET": None, "PG": None}),
            "U2": (TPS630701, {"VIN": "VPACK", "EN": "EN_5V_F", "PS/SYNC": "PS", "VSEL": "GND", "L1": "L5A", "L2": "L5B",
                               "VOUT": "+5V_RAW", "FB": "+5V_RAW", "FB2": None, "PG": None, "VAUX": "VAUX",
                               "GND": "GND", "PGND": "GND"}),
            "U3": (TPS2553, {"IN": "+5V_RAW", "GND": "GND", "EN": "EN_5V_F", "FAULT": None, "ILIM": "ILIM", "OUT": "+5V_LED"})}
    for ref, (table, nets) in want.items():
        for num, name in table.items():
            got = c.net(ref, num) or ""
            if nets[name] is None:
                c.eq(f"{ref}.{num} {name} open", got.startswith("unconnected-"), True)
            else:
                c.eq(f"{ref}.{num} {name}", got, nets[name])
    c.eq("pack path", [c.net("J1", 1), c.net("J1", 2), sorted([c.net("F1", 1), c.net("F1", 2)]),
                       [c.net("Q1", p) for p in (1, 2, 3)]],
         ["BAT+", "GND", ["BAT+", "VFUSE"], ["GATE", "VPACK", "VFUSE"]])   # AO3401A: 1 G, 2 S (load side), 3 D (pack side)
    c.eq("gate resistor", parts_on(c, "Q1", 1, "R"), [("100k", "GND")])
    c.eq("switch", [c.net("SW1", 1), c.net("SW1", 2), (c.net("SW1", 3) or "").startswith("unconnected-")], ["VPACK", "VSW", True])
    c.eq("switch carries no load", sorted(r for r, _ in c.nodes["VSW"]), ["R11", "R2", "R4", "SW1"])
    c.eq("3.3 V enable = pack cut-off divider", (parts_on(c, "U1", 7, "R"), parts_on(c, "U1", 7, "C")),
         (sorted([(UVLO_TOP, "VSW"), (UVLO_BOTTOM, "GND")]), [("100n", "GND")]))
    c.eq("cell-count jumper: 2.55 M from VSW in parallel when bridged", (sorted([c.net("JP1", 1), c.net("JP1", 2)]), parts_on(c, "JP1", 1, "R")),
         (["EN_3V3", "UVLO_4"], [(UVLO_PAR, "VSW")]))
    par = ohms(UVLO_TOP) * ohms(UVLO_PAR) / (ohms(UVLO_TOP) + ohms(UVLO_PAR))
    for cells, top in ((6, ohms(UVLO_TOP)), (4, par)):
        k = (top + ohms(UVLO_BOTTOM)) / ohms(UVLO_BOTTOM)
        c.eq(f"{cells} cells: on at 0.97-1.05 V, off at 0.87-0.95 V per cell", (0.97 < 1.0 * k / cells < 1.05, 0.87 < 0.9 * k / cells < 0.95), (True, True))
    c.eq("gate clamp", (c.net("D1", 1), c.net("D1", 2), c.comps["D1"]), ("VPACK", "GATE", "10V"))
    c.eq("S-CONF resistor (VSET mode, auto, discharge)", parts_on(c, "U1", 8, "R"), [("27.4k", "GND")])
    c.eq("3.3 V inductor", sorted([c.net("L1", 1), c.net("L1", 2)]) + [c.comps["L1"]], ["+3V3", "SW_3V3", "2.2u"])
    c.eq("3.3 V output capacitor", parts_on(c, "U1", 3, "C"), [("22u", "GND")])
    c.eq("5 V inductor", sorted([c.net("L2", 1), c.net("L2", 2)]) + [c.comps["L2"]], ["L5A", "L5B", "1.5u"])
    c.eq("5 V output capacitors", parts_on(c, "U2", 7, "C"), [("100n", "GND"), ("10u", "GND"), ("22u", "GND"), ("22u", "GND")])
    c.eq("input capacitors", parts_on(c, "U1", 6, "C"), [("10u", "GND"), ("10u", "GND"), ("10u", "GND"), ("47u", "GND")])
    c.eq("VAUX capacitor", parts_on(c, "U2", 3, "C"), [("100n", "GND")])
    c.eq("power save", parts_on(c, "U2", 1, "R"), [("100k", "VPACK")])
    c.eq("5 V enable: off by default", parts_on(c, "U2", 14, "R"), [("100k", "GND"), ("1k", "EN_5V")])
    c.eq("LED rail limit resistor", parts_on(c, "U3", 5, "R"), [("49.9k", "GND")])
    div = parts_on(c, "J2", 4, "R")
    c.eq("pack divider", div, sorted([(DIVIDER[0], "VSW"), (DIVIDER[1], "GND")]))
    top, bot = ohms(DIVIDER[0]), ohms(DIVIDER[1])
    c.eq("divider at 10 V stays under 3.0 V", 10 * bot / (top + bot) < 3.0, True)
    c.eq("3.3 V never reaches the 5 V rail", {"+3V3"} & {c.net("U3", 6), c.net("U2", 7)}, set())
    footprints(c, "pod-power")
    return c


def verify_carrier(pod):
    c = load("hub-radio")
    hub = load("hub-core")
    exp = [r for r, v in hub.comps.items() if v == "EXPANSION"]
    c.eq("hub-core has one expansion header", len(exp), 1)
    for p, n in EXPANSION.items():
        c.eq(f"hub-core expansion pin {p}", hub.net(exp[0], p), n)
    same = {"SDA": "UART_H2P", "SCL": "UART_P2H"}
    for bay, e in CARRIER.items():
        hub_net = EXPANSION[e]
        c.eq(f"bay pin {bay} on expansion pin {e} ({hub_net})", c.net("J2", bay), c.net("J1", e))
        c.eq(f"expansion pin {e} net", c.net("J1", e), same.get(hub_net, hub_net))
    c.eq("bay pin 4 (LED data) open", (c.net("J2", 4) or "").startswith("unconnected-"), True)
    c.eq("SP4 open", (c.net("J1", 8) or "").startswith("unconnected-"), True)
    # what the pod presents on each bay pin, against what the hub gives it
    c.eq("pod 3.3 V pin fed from the Pico's 3.3 V", (BAY[5], EXPANSION[CARRIER[5]]), ("+3V3", "+3V3"))
    c.eq("pod 5 V pins on +5V", {EXPANSION[CARRIER[p]] for p in (1, 2)}, {"+5V"})
    c.eq("pod GND pins on GND", {EXPANSION[CARRIER[p]] for p in (3, 11)}, {"GND"})
    c.eq("spare pin low = in the hub", (BAY[6], EXPANSION[CARRIER[6]], pod.net("J1", 6)), ("SPARE", "GND", "SPARE"))
    c.eq("Pico TX (GP0) into the pod's input", (BAY[9], EXPANSION[CARRIER[9]]), ("MISO", "SDA"))
    c.eq("Pico RX (GP1) from the pod's output", (BAY[10], EXPANSION[CARRIER[10]]), ("MOSI", "SCL"))
    footprints(c, "hub-radio")
    return c


def pinmap():
    hub = json.loads((schlib.ROOT / "firmware" / "hub-pinmap.json").read_text()) if (schlib.ROOT / "firmware" / "hub-pinmap.json").exists() else {}
    return {
        "board": "pod", "module": "Raytac MDBT50Q-1MV2", "mcu": "nRF52840", "source": "tools/sch_pod.py",
        "supply": "VDD = VDDH = 3.3 V from the lead (key module) or the Pico (hub); REG1 DC/DC may be enabled (inductor in the module); "
                  "USB VBUS feeds only the USB regulator",
        "lfclk": "32.768 kHz crystal on P0.00 / P0.01",
        "pins": {fn: {"gpio": gpio, "module_pin": PIN_OF[gpio], "net": net, "note": note,
                      **({"ain": ANALOG[gpio]} if fn == "VBAT_SENSE" else {})}
                 for fn, (gpio, net, note) in POD.items()},
        "usb": {"d_plus_module_pin": PIN_OF["D+"], "d_minus_module_pin": PIN_OF["D-"], "vbus_module_pin": PIN_OF["VBUS"]},
        "swd": {"swdio_module_pin": PIN_OF["SWDIO"], "swdclk_module_pin": PIN_OF["SWDCLK"], "header": "2x5 1.27 mm Cortex debug"},
        "active_levels": {"CS": "low", "INT": "low", "EN_5V": "high", "STATUS_LED": "high", "HUB_DETECT": "low = hub", "RESET": "low"},
        "pack_cutoff": {"per_cell_on_v": 1.0, "per_cell_off_v": 0.9, "note": "hardware, on the 3.3 V converter; drop EN_5V at about 1.1 V per cell in firmware"},
        "vbat": {"divider_top_ohm": ohms(DIVIDER[0]), "divider_bottom_ohm": ohms(DIVIDER[1]),
                 "pack_volts_per_pin_volt": round((ohms(DIVIDER[0]) + ohms(DIVIDER[1])) / ohms(DIVIDER[1]), 4),
                 "note": "reads 0 while the pack switch is off (then the pod is unpowered too); in the hub the pin is open"},
        "led_rail": {"limit_ma": [475, 520, 565], "note": "TPS2553 constant-current cap; keep the firmware's LED budget below 450 mA"},
        "key_module": {"spi": {"sck": POD["SCK"][0], "mosi": POD["MOSI"][0], "miso": POD["MISO"][0], "cs": POD["CS"][0]},
                       "int": POD["INT"][0], "led_data": POD["LED_DATA"][0],
                       "expander_addresses": {"left": [0], "numpad": [1], "right": [2, 3]}},
        "hub": {"uart": {"pod_tx": POD["MOSI"][0], "pod_rx": POD["MISO"][0], "pico_tx": "GP0", "pico_rx": "GP1", "pico_uart": "uart0"},
                "note": "HUB_DETECT reads low; hub firmware must not start I2C0 on GP0 / GP1 with a carrier fitted (hub-pinmap.json lists them as I2C0); the Pico's I2C0 pull-ups (4.7 k) hold both lines high; CS, SCK, INT go to SP1, SP2, SP3 (no Pico pin)",
                "hub_pinmap": "firmware/hub-pinmap.json" if hub else None},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="only verify the schematics and the pin map on disk")
    args = ap.parse_args()
    want = json.dumps(pinmap(), indent=2) + "\n"
    if not args.verify:
        for name in BUILDERS:
            generate(name)
        PINMAP.write_text(want)
        print("wrote", PINMAP)
    pod = verify_pod()
    checks = [pod, verify_power(), verify_carrier(pod)]
    pm = Checker("pod-pinmap.json", {}, {}, {})
    pm.eq("file matches the tables", PINMAP.read_text() if PINMAP.exists() else None, want)
    sys.exit(1 if report(checks + [pm]) else 0)


if __name__ == "__main__":
    main()
