#!/usr/bin/env python3
"""Capture the link board schematic (hardware/link/link.kicad_sch).

Rear USB-C link port, four per keyboard (spec §2a "Link board", §4 "USB input OVP"
and "Downstream ports", §6 "Link USB-C", "Board interconnect"). One PCB in two
KiCad design variants:

  upstream   (`right` upstream, `numpad`): KTS1693 OVP with OVLO divider and ISET,
             ACOK out, 9-pin J_LB. This is also the default (no-variant) population,
             so a plain BOM never fits the OVP bypass.
  downstream (`left`, `right` downstream): no KTS1693, no divider, no ISET; a 1206
             0 ohm jumper across IN/OUT; 10-pin J_LBD, no ACOK; TPS22950L link VBUS
             switch from J_LBD's VBUS to the port, ON from LINK_SW_EN (P14).

The receptacle's pairs are tied (A6=B6 -> LA, A7=B7 -> LB), SBU brought out as S1/S2,
no CC resistors. The seam board joins on J_SEAM ahead of the KTS1693, so one OVP
covers the rear port and the pogo contacts. TPD6E05U06 on all six signal pins.

Placement, stubs, labels, variants and the netlist/BOM checks live in tools/schlib.py.

Run: .venv/bin/python tools/sch_link.py [--force]
Check: tools/kicad-check.sh
"""

import schlib

SCH = schlib.ROOT / "hardware" / "link" / "link.kicad_sch"

FP_R = "Resistor_SMD:R_0603_1608Metric"
FP_R1206 = "Resistor_SMD:R_1206_3216Metric"
FP_C = "Capacitor_SMD:C_0603_1608Metric"
FP_GH = "Connector_JST:JST_GH_SM{0:02d}B-GHS-TB_1x{0:02d}-1MP_P1.25mm_Horizontal"

IN_BALLS = ("C3", "D2", "D3", "E2", "E3", "E4")
OUT_BALLS = ("A2", "A3", "A4", "B2", "B3", "C2")

# Part tuples and pin-table conventions: see tools/schlib.py.
PARTS = [
    # receptacle: pairs tied across plug sides, SBU separate (tying A8=B8 would short P2_DN to P2_UP), CC open
    ("J601", "Connector:USB_C_Receptacle_USB2.0_16P", "USB4085-GF-A", "Connector_USB:USB_C_Receptacle_GCT_USB4085", (14, 34),
     {"A4": "VBUS_CONN", "A9": "VBUS_CONN", "B4": "VBUS_CONN", "B9": "VBUS_CONN",
      "A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "SH": "GND",
      "A5": None, "B5": None, "A6": "LA", "B6": "LA", "A7": "LB", "B7": "LB", "A8": "S1", "B8": "S2"},
     {"MPN": "GCT USB4085-GF-A"}),
    # ESD: one channel per receptacle signal pin, placed at the pins; no supply pin.
    # Stock RVZ footprint accepted on its KiCad citation (older SLVSBO7 p. 28), not re-checked (hardware/README.md)
    ("U602", "Power_Protection:TPD6E05U06RVZ", "TPD6E05U06", "Package_SON:Texas_R-PUSON-N14", (16, 62),
     {"14": "LA", "13": "LA", "12": "LB", "11": "LB", "9": "S1", "8": "S2", "5": "GND", "10": "GND",
      "1": None, "2": None, "3": None, "4": None, "6": None, "7": None},
     {"MPN": "TI TPD6E05U06RVZR"}),
    ("C601", "Device:C", "100n", FP_C, (36, 16),
     {"1": "VBUS_CONN", "2": "GND"}, {"Voltage": "50V", "Dielectric": "X7R"}),
    # OVP switch (upstream only): EN tied on, OC_MODE low, CDET unused
    ("U601", "keyboard:KTS1693EVB", "KTS1693EVB", "keyboard:Kinetic_WLCSP-20_1.935x2.16mm_Layout4x5_P0.4mm", (62, 34),
     {**{b: "VBUS_CONN" for b in IN_BALLS}, **{b: "VBUS_LINK" for b in OUT_BALLS},
      "D1": "OVLO", "E1": "ISET", "B1": "GND", "B4": "GND", "C4": "GND", "D4": "GND",
      "C1": "ACOK", "A1": None},
     {"MPN": "Kinetic KTS1693EVB-TR"}),
    ("R601", "Device:R", "100k", FP_R, (46, 48),
     {"1": "VBUS_CONN", "2": "OVLO"}, {"Tolerance": "0.1%"}),
    ("R602", "Device:R", "26.4k", FP_R, (46, 58),
     {"1": "OVLO", "2": "GND"}, {"Tolerance": "0.1%"}),
    ("R603", "Device:R", "4.99k", FP_R, (56, 56),
     {"1": "ISET", "2": "GND"}, {"Tolerance": "1%"}),
    # OVP bypass (downstream only): 0 ohm across the KTS1693's IN/OUT
    ("R604", "Device:R", "0", FP_R1206, (62, 16),
     {"1": "VBUS_CONN", "2": "VBUS_LINK"},
     {"MPN": "Vishay CRCW12060000Z0EA", "Power": "3.5A jumper", "DNP_reason": "downstream only: bypasses OVP"}),
    # protected side
    ("C602", "Device:C", "1u", FP_C, (80, 16),
     {"1": "VBUS_LINK", "2": "GND"}, {"Voltage": "25V", "Dielectric": "X7R"}),
    ("D601", "Diode:PTVS22VZ1USK", "SMF6.0A", "keyboard:D_SOD-123FL_Littelfuse_SMF", (92, 16),
     {"1": "VBUS_LINK", "2": "GND"}, {"MPN": "Littelfuse SMF6.0A"}),
    # J_SEAM, reversal-safe, in pogo contact order (pair A VBUS LA LB GND, pair B GND S1 S2 VBUS)
    ("J602", "Connector_Generic:Conn_01x08", "J_SEAM", FP_GH.format(8), (106, 60),
     {"1": "VBUS_CONN", "2": "LA", "3": "LB", "4": "GND", "5": "GND", "6": "S1", "7": "S2", "8": "VBUS_CONN"},
     {"MPN": "JST SM08B-GHS-TB"}),
    # J_LB (upstream), reversal-safe: ACOK on the centre pin
    ("J603", "Connector_Generic:Conn_01x09", "J_LB", FP_GH.format(9), (106, 16),
     {"1": "VBUS_LINK", "2": "LA", "3": "LB", "4": "GND", "5": "ACOK", "6": "GND", "7": "S1", "8": "S2", "9": "VBUS_LINK"},
     {"MPN": "JST SM09B-GHS-TB"}),
    # J_LBD (downstream), reversal-safe: reversed, LINK_SW_EN meets GND at both ends, so the switch stays off
    ("J604", "Connector_Generic:Conn_01x10", "J_LBD", FP_GH.format(10), (126, 16),
     {"1": "VBUS_LBD", "2": "LA", "3": "LB", "4": "GND", "5": "GND", "6": "LINK_SW_EN", "7": "GND", "8": "S1", "9": "S2",
      "10": "VBUS_LBD"},
     {"MPN": "JST SM10B-GHS-TB"}),
    # link VBUS switch (downstream only, P14): latch-off at IHCD, no reverse current blocking; FLT has no J_LBD pin.
    # VOUT on VBUS_CONN, not VBUS_LINK: R604 joins them downstream, and it keeps two power outputs (U601, U603) off one net
    ("U603", "keyboard:TPS22950LYBH", "TPS22950LYBH", "keyboard:Texas_DSBGA-6_0.706x1.106mm_Layout2x3_P0.4mm_YBH", (146, 40),
     {"B1": "VBUS_LBD", "A1": "LINK_SW_EN", "C2": "ILIM", "B2": "VBUS_CONN", "A2": None, "C1": "GND"},
     {"MPN": "TI TPS22950LYBHR"}),
    ("C603", "Device:C", "1u", FP_C, (130, 40),
     {"1": "VBUS_LBD", "2": "GND"}, {"Voltage": "25V", "Dielectric": "X7R"}),
    # SLVSFJ2B Table 7.5 test point: IHCD 1.2-1.9 A, ILIM,PEAK 2.1 A typ
    ("R605", "Device:R", "624", FP_R, (140, 56),
     {"1": "ILIM", "2": "GND"}, {"Tolerance": "0.5%"}),
]
UPSTREAM_DNP = {"R604", "J604", "U603", "C603", "R605"}
VARIANTS = {
    "upstream": UPSTREAM_DNP,
    "downstream": {"U601", "R601", "R602", "R603", "J603"},
}
# VBUS_LBD comes from passive connector pins; GND likewise. VBUS_CONN is driven by U603's VOUT, so it needs no flag
FLAGS = [("#FLG0602", "GND", (72, 58)), ("#FLG0603", "VBUS_LBD", (130, 30))]

NETS = {
    "VBUS_CONN": ["J601.A4", "J601.A9", "J601.B4", "J601.B9", *(f"U601.{b}" for b in IN_BALLS),
                  "C601.1", "R601.1", "R604.1", "J602.1", "J602.8", "U603.B2"],
    "VBUS_LINK": [*(f"U601.{b}" for b in OUT_BALLS), "R604.2", "C602.1", "D601.1",
                  "J603.1", "J603.9"],
    "VBUS_LBD": ["J604.1", "J604.10", "U603.B1", "C603.1"],
    "LINK_SW_EN": ["J604.6", "U603.A1"],
    "ILIM": ["U603.C2", "R605.1"],
    "GND": ["J601.A1", "J601.A12", "J601.B1", "J601.B12", "J601.SH", "U602.5", "U602.10",
            "U601.B1", "U601.B4", "U601.C4", "U601.D4", "C601.2", "C602.2", "D601.2", "R602.2", "R603.2",
            "J602.4", "J602.5", "J603.4", "J603.6", "J604.4", "J604.5", "J604.7",
            "U603.C1", "C603.2", "R605.2"],
    "OVLO": ["U601.D1", "R601.2", "R602.1"],
    "ISET": ["U601.E1", "R603.1"],
    "ACOK": ["U601.C1", "J603.5"],
    "LA": ["J601.A6", "J601.B6", "U602.14", "U602.13", "J602.2", "J603.2", "J604.2"],
    "LB": ["J601.A7", "J601.B7", "U602.12", "U602.11", "J602.3", "J603.3", "J604.3"],
    "S1": ["J601.A8", "U602.9", "J602.6", "J603.7", "J604.8"],
    "S2": ["J601.B8", "U602.8", "J602.7", "J603.8", "J604.9"],
}

NOTES = [
    ((4, 76), "Link USB-C port per spec §6. Variants: 'upstream' (default population; right upstream, numpad) and 'downstream' (left, right downstream).\n"
              "Upstream: KTS1693 with external OVLO 100k / 26.4k 0.1 % (trip 5.55-5.95 V); ISET 4.99k -> OCP 1.82-2.18 A latch-off\n"
              "(datasheet rev 04d Table 1; was 1M, no OCP, until E9 2026-09-15); EN and OC_MODE low; ACOK open-drain to J_LB pin 5, pulled up on the core (wired-OR on right).\n"
              "Downstream: U601, R601-R603 and J_LB not fitted; R604 0 ohm 1206 (CRCW1206 jumper 3.5 A, <=20 mOhm) bridges VBUS; J_LBD fitted, no ACOK.\n"
              "R604 must never be fitted with U601: it bypasses the OVP. Upstream: U603, C603, R605 and J_LBD not fitted.\n"
              "Downstream U603 TPS22950L (P14) switches J_LBD VBUS to VBUS_CONN (port, J_SEAM; via R604 to C602/D601), ON = LINK_SW_EN (J_LBD 6, smart pulldown; series R on the core).\n"
              "R605 624 ohm (SLVSFJ2B Table 7.5): latches off above IHCD 1.2-1.9 A for 120-188 us, peak 2.1 A typ; <=2 A for 2 J_LBD contacts (P9).\n"
              "Cleared only by toggling ON or VIN. No reverse current blocking (SLVSFJ2B Table 5). FLT not used. CIN 1 uF per SLVSFJ2B 10.3.\n"
              "No CC resistors: a charger never enables VBUS into a link port. A6=B6 (LA) and A7=B7 (LB) tied; A8 (S1) and B8 (S2) separate.\n"
              "TPD6E05U06 on all six signal pins, at the receptacle. J_SEAM joins the seam board ahead of the KTS1693.\n"
              "J_SEAM, J_LB, J_LBD are reversal-safe: pin k and N+1-k never pair VBUS with GND; LA/LB swap with S2/S1."),
]

if __name__ == "__main__":
    schlib.run(SCH, "link", "Link board", 600, PARTS, FLAGS, NOTES, NETS, dnp=UPSTREAM_DNP, variants=VARIANTS)
