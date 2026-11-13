#!/usr/bin/env python3
"""Capture the USB port board schematic (hardware/usb-port/usb-port.kicad_sch).

The hub's host port (plans/keyboard.md sections 3a, 3b; board carried over from rev 8):
GCT USB4085 receptacle -> KTS1693 OVP switch with an external OVLO divider and
ISET (3.5 A, auto-restart) -> SMF6.0A and USBLC6-2SC6 on the protected side ->
J_USB cable header to hub-conn. CC1/CC2 carry 5.1 k Rd and a TVS2200 each.

Placement, stubs, labels and the netlist check live in tools/schlib.py.

Run: .venv/bin/python tools/sch_usb_port.py [--force]
Check: tools/kicad-check.sh
"""

import schlib

SCH = schlib.ROOT / "hardware" / "usb-port" / "usb-port.kicad_sch"

FP_R = "Resistor_SMD:R_0603_1608Metric"
FP_R0805 = "Resistor_SMD:R_0805_2012Metric"
FP_C = "Capacitor_SMD:C_0603_1608Metric"
FP_TVS2200 = "keyboard:TI_WSON-6-1EP_2x2mm_P0.65mm_DRV0006A_TVS2200"

IN_BALLS = ("C3", "D2", "D3", "E2", "E3", "E4")
OUT_BALLS = ("A2", "A3", "A4", "B2", "B3", "C2")

# Part tuples and pin-table conventions: see tools/schlib.py.
PARTS = [
    # receptacle: USB 2.0, 16 contacts, all through-hole; SBU unused on the local port
    ("J501", "Connector:USB_C_Receptacle_USB2.0_16P", "USB4085-GF-A", "Connector_USB:USB_C_Receptacle_GCT_USB4085", (14, 34),
     {"A4": "VBUS_CONN", "A9": "VBUS_CONN", "B4": "VBUS_CONN", "B9": "VBUS_CONN",
      "A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "SH": "GND",
      "A5": "CC1", "B5": "CC2", "A6": "USB_DP", "B6": "USB_DP", "A7": "USB_DN", "B7": "USB_DN",
      "A8": None, "B8": None},
     {"MPN": "GCT USB4085-GF-A"}),
    # connector-side VBUS TVS: footprint only (spec: fit only if the §16 ESD/surge tests need it)
    ("D504", "Power_Protection:TVS2200DRV", "TVS2200", FP_TVS2200, (44, 16),
     {"1": "GND", "2": "GND", "3": "GND", "7": "GND", "4": "VBUS_CONN", "5": "VBUS_CONN", "6": "VBUS_CONN"},
     {"MPN": "TI TVS2200DRVR", "DNP_reason": "fit only if ESD/surge tests need it"}),
    ("C501", "Device:C", "100n", FP_C, (36, 16),
     {"1": "VBUS_CONN", "2": "GND"}, {"Voltage": "50V", "Dielectric": "X7R"}),
    # OVP switch: EN tied on, OC_MODE open = high through the internal 5 M pull-up (auto-restart), CDET unused
    ("U501", "keyboard:KTS1693EVB", "KTS1693EVB", "keyboard:Kinetic_WLCSP-20_1.935x2.16mm_Layout4x5_P0.4mm", (62, 34),
     {**{b: "VBUS_CONN" for b in IN_BALLS}, **{b: "VBUS_LOCAL" for b in OUT_BALLS},
      "D1": "OVLO", "E1": "ISET", "B1": "GND", "B4": None, "C4": "GND", "D4": "GND",
      "C1": "ACOK", "A1": None},
     {"MPN": "Kinetic KTS1693EVB-TR"}),
    ("R501", "Device:R", "100k", FP_R, (46, 48),
     {"1": "VBUS_CONN", "2": "OVLO"}, {"Tolerance": "0.1%"}),
    ("R502", "Device:R", "26.4k", FP_R, (46, 58),
     {"1": "OVLO", "2": "GND"}, {"Tolerance": "0.1%"}),
    ("R503", "Device:R", "2.87k", FP_R, (56, 56),
     {"1": "ISET", "2": "GND"}, {"Tolerance": "1%"}),
    # protected side
    ("C502", "Device:C", "1u", FP_C, (80, 16),
     {"1": "VBUS_LOCAL", "2": "GND"}, {"Voltage": "25V", "Dielectric": "X7R"}),
    ("D501", "Diode:PTVS22VZ1USK", "SMF6.0A", "keyboard:D_SOD-123FL_Littelfuse_SMF", (92, 16),
     {"1": "VBUS_LOCAL", "2": "GND"}, {"MPN": "Littelfuse SMF6.0A"}),
    ("U502", "Power_Protection:USBLC6-2SC6", "USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6", (84, 50),
     {"1": "USB_DP", "6": "USB_DP", "3": "USB_DN", "4": "USB_DN", "5": "VBUS_LOCAL", "2": "GND"},
     {"MPN": "ST USBLC6-2SC6"}),
    # CC: Rd to GND and a 22 V TVS each; 0805 Rd takes ~78 mW if CC is shorted to a 20 V VBUS
    ("R504", "Device:R", "5.1k", FP_R0805, (10, 60),
     {"1": "CC1", "2": "GND"}, {"Tolerance": "1%", "Power": "125mW"}),
    ("R505", "Device:R", "5.1k", FP_R0805, (18, 60),
     {"1": "CC2", "2": "GND"}, {"Tolerance": "1%", "Power": "125mW"}),
    ("D502", "Power_Protection:TVS2200DRV", "TVS2200", FP_TVS2200, (26, 60),
     {"1": "GND", "2": "GND", "3": "GND", "7": "GND", "4": "CC1", "5": "CC1", "6": "CC1"},
     {"MPN": "TI TVS2200DRVR"}),
    ("D503", "Power_Protection:TVS2200DRV", "TVS2200", FP_TVS2200, (34, 60),
     {"1": "GND", "2": "GND", "3": "GND", "7": "GND", "4": "CC2", "5": "CC2", "6": "CC2"},
     {"MPN": "TI TVS2200DRVR"}),
    # J_USB, reversal-safe: pin k and 12-k never pair power with the opposite rail
    ("J502", "Connector_Generic:Conn_01x11", "J_USB", "Connector_JST:JST_GH_SM11B-GHS-TB_1x11-1MP_P1.25mm_Horizontal", (106, 34),
     {"1": "VBUS_LOCAL", "2": "GND", "3": "CC1", "4": "GND", "5": "USB_DP", "6": "VBUS_LOCAL",
      "7": "USB_DN", "8": "ACOK", "9": "CC2", "10": "GND", "11": "VBUS_LOCAL"},
     {"MPN": "JST SM11B-GHS-TB"}),
]
DNP = {"D504"}
# VBUS_CONN comes from passive connector pins; GND likewise
FLAGS = [("#FLG0501", "VBUS_CONN", (28, 10)), ("#FLG0502", "GND", (72, 58))]

NETS = {
    "VBUS_CONN": ["J501.A4", "J501.A9", "J501.B4", "J501.B9", *(f"U501.{b}" for b in IN_BALLS),
                  "C501.1", "D504.4", "D504.5", "D504.6", "R501.1"],
    "VBUS_LOCAL": [*(f"U501.{b}" for b in OUT_BALLS), "C502.1", "D501.1", "U502.5", "J502.1", "J502.6", "J502.11"],
    "GND": ["J501.A1", "J501.A12", "J501.B1", "J501.B12", "J501.SH", "U501.B1", "U501.C4", "U501.D4",
            "C501.2", "C502.2", "D501.2", "U502.2", "R502.2", "R503.2", "R504.2", "R505.2",
            *(f"{d}.{p}" for d in ("D502", "D503", "D504") for p in ("1", "2", "3", "7")),
            "J502.2", "J502.4", "J502.10"],
    "OVLO": ["U501.D1", "R501.2", "R502.1"],
    "ISET": ["U501.E1", "R503.1"],
    "ACOK": ["U501.C1", "J502.8"],
    "CC1": ["J501.A5", "R504.1", "D502.4", "D502.5", "D502.6", "J502.3"],
    "CC2": ["J501.B5", "R505.1", "D503.4", "D503.5", "D503.6", "J502.9"],
    "USB_DP": ["J501.A6", "J501.B6", "U502.1", "U502.6", "J502.5"],
    "USB_DN": ["J501.A7", "J501.B7", "U502.3", "U502.4", "J502.7"],
}

NOTES = [
    ((4, 70), "Host USB-C port of the hub (spec sections 3a, 3b). KTS1693: external OVLO 100k / 26.4k 0.1 % (E192) trips at 5.56-5.93 V: above a legal 5.5 V VBUS,\n"
              "below the USBLC6's 6 V breakdown (the internal threshold, 5.77-6.13 V, is not).\n"
              "ISET 2.87k -> limit 3.17 / 3.48 / 3.80 A (10000 / R, +/-9 %, 0-70 C): a 3 A host is not cut off; the cable header's 3 x 1 A contacts are the 3 A limit.\n"
              "EN tied low. OC_MODE open: the internal 5 M pull-up makes it high = auto-restart (limits for 8 ms, off, retries after 200 ms).\n"
              "ACOK is open-drain and not used by the hub (J_USB pin 8 is open there). CDET unused. D504 (TVS2200 on connector VBUS) is a DNP footprint.\n"
              "USBLC6-2SC6 VBUS (pin 5) is on VBUS_LOCAL, never on connector VBUS.\n"
              "CC1/CC2: 5.1k Rd (0805 for a 20 V CC short) and TVS2200 (22 V VRWM); hub-conn adds 100k in series before the Pico's ADC pins.\n"
              "J_USB is reversal-safe: an end-reversed cable keeps VBUS on VBUS and GND on GND; D+/D- swap and USB does not enumerate."),
]

if __name__ == "__main__":
    schlib.run(SCH, "usb-port", "USB port board", 500, PARTS, FLAGS, NOTES, NETS, dnp=DNP)
