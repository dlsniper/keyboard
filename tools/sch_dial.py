#!/usr/bin/env python3
"""Capture the dial board schematic (hardware/dial/dial.kicad_sch).

Dial on `right` (spec §2a "Dial board", §2 "Selector", §8, parts shortlist "Encoder"):
Bourns PEC11R 24 detents / 24 ppr with push switch -> 1k + 10 nF low-pass per
quadrature channel (pull-ups stay on the core) -> J_DIAL to the key board. The
push switch is a matrix key with its 1N4148W on this board; the mounting lugs go
to GND; a TPD4E1U06 ESD footprint on the encoder pins is not fitted.
Hand-solderable: 0805 passives, SOD-123, SOT-23-6, through-hole encoder.

Placement, stubs, labels and the netlist check live in tools/schlib.py.

Run: .venv/bin/python tools/sch_dial.py [--force]
Check: tools/kicad-check.sh
"""

import schlib

SCH = schlib.ROOT / "hardware" / "dial" / "dial.kicad_sch"

FP_R = "Resistor_SMD:R_0805_2012Metric_Pad1.20x1.40mm_HandSolder"
FP_C = "Capacitor_SMD:C_0805_2012Metric_Pad1.18x1.45mm_HandSolder"

# Part tuples and pin-table conventions: see tools/schlib.py.
PARTS = [
    # encoder: C common to GND, lugs to GND so a shaft discharge has a path that avoids the contacts
    ("SW901", "keyboard:RotaryEncoder_Switch_MP", "PEC11R-42xxx-S0024", "keyboard:RotaryEncoder_Bourns_PEC11R-4xxxF-Sxxxx_Vertical", (14, 30),
     {"A": "ENC_A_SW", "B": "ENC_B_SW", "C": "GND", "S1": "SW_COL", "S2": "SW_D", "MP": "GND"},
     {"MPN": "Bourns PEC11R-42xxx-S0024", "Shaft": "TBD Phase 1 (knob + case height): 15/20/25/30 mm, F flatted or K knurled (K 15/20 only)"}),
    # quadrature low-pass: series R limits the contact discharge of C, C sits on the connector side
    ("R901", "Device:R", "1k", FP_R, (36, 20),
     {"1": "ENC_A_SW", "2": "ENC_A"}, {"Tolerance": "1%"}),
    ("C901", "Device:C", "10n", FP_C, (48, 26),
     {"1": "ENC_A", "2": "GND"}, {"Voltage": "50V", "Dielectric": "X7R"}),
    ("R902", "Device:R", "1k", FP_R, (36, 40),
     {"1": "ENC_B_SW", "2": "ENC_B"}, {"Tolerance": "1%"}),
    ("C902", "Device:C", "10n", FP_C, (48, 46),
     {"1": "ENC_B", "2": "GND"}, {"Voltage": "50V", "Dielectric": "X7R"}),
    # push switch diode, col2row: column -> switch -> anode -> cathode -> row.
    # Device:D (1 K, 2 A): Diode:1N4148W extends 1N4001 and trips lib_symbol_mismatch
    ("D901", "Device:D", "1N4148W", "Diode_SMD:D_SOD-123", (36, 58),
     {"1": "SW_ROW", "2": "SW_D"}, {"MPN": "Diodes Inc 1N4148W-7-F"}),
    # ESD on the four encoder-side nets: footprint only (fit only if the §16 ESD test needs it)
    ("U901", "keyboard:TPD4E1U06DBV", "TPD4E1U06", "keyboard:TI_SOT-23-6_DBV0006A", (14, 48),
     {"1": "ENC_A_SW", "3": "ENC_B_SW", "4": "SW_D", "6": "SW_COL", "2": "GND", "5": None},
     {"MPN": "TI TPD4E1U06DBVR", "DNP_reason": "fit only if ESD tests need it"}),
    # J_DIAL, reversal-safe: an end-reversed cable swaps A/B and ROW/COL only
    ("J901", "Connector_Generic:Conn_01x05", "J_DIAL", "Connector_JST:JST_GH_SM05B-GHS-TB_1x05-1MP_P1.25mm_Horizontal", (70, 34),
     {"1": "SW_ROW", "2": "ENC_A", "3": "GND", "4": "ENC_B", "5": "SW_COL"},
     {"MPN": "JST SM05B-GHS-TB"}),
    # M2 mounting holes, no copper: in the schematic so PCB parity has nothing board-only (symbol is in_bom no)
    ("H901", "Mechanical:MountingHole", "MountingHole", "MountingHole:MountingHole_2.2mm_M2_ISO7380", (60, 6), {}, {}),
    ("H902", "Mechanical:MountingHole", "MountingHole", "MountingHole:MountingHole_2.2mm_M2_ISO7380", (66, 6), {}, {}),
]
DNP = {"U901"}
# GND comes only from the passive connector pin
FLAGS = [("#FLG0901", "GND", (62, 52))]

NETS = {
    "ENC_A_SW": ["SW901.A", "R901.1", "U901.1"],
    "ENC_B_SW": ["SW901.B", "R902.1", "U901.3"],
    "ENC_A": ["R901.2", "C901.1", "J901.2"],
    "ENC_B": ["R902.2", "C902.1", "J901.4"],
    "SW_COL": ["SW901.S1", "U901.6", "J901.5"],
    "SW_D": ["SW901.S2", "D901.2", "U901.4"],
    "SW_ROW": ["D901.1", "J901.1"],
    "GND": ["SW901.C", "SW901.MP", "C901.2", "C902.2", "U901.2", "J901.3"],
}

NOTES = [
    ((4, 62), "Dial board per spec §2a/§8. PEC11R 24 detents / 24 ppr with push switch (datasheet rev D04/26); shaft TBD in Phase 1.\n"
              "A/B: pull-ups are the core's internal ones (~13k, range unverified). 1k series + 10 nF to GND on the connector side:\n"
              "closed-contact level ~0.24 V (< 0.3 VDD), discharge peak 3.3 mA (contact rating 10 mA at 5 V), rise ~0.2 ms vs >= 10 ms\n"
              "between edges at 60 RPM max. Bourns' own filter (10k pull-up, 10k, 10 nF) needs a supply J_DIAL does not carry.\n"
              "Push switch is a matrix key, col2row (ZMK: columns drive, rows read): SW_COL -> S1-S2 -> D901 anode -> cathode -> SW_ROW.\n"
              "Mounting lugs (MP) to GND; lug-to-bushing continuity is not stated by Bourns. U901 TPD4E1U06 is a DNP footprint.\n"
              "J_DIAL 1 SW_ROW, 2 ENC_A, 3 GND, 4 ENC_B, 5 SW_COL: end-reversed, A/B swap (direction) and the push diode\n"
              "reverses (press not seen); nothing is damaged. Bourns: hand soldering 'not recommended'; see the build guide."),
]

if __name__ == "__main__":
    schlib.run(SCH, "dial", "Dial board", 900, PARTS, FLAGS, NOTES, NETS, dnp=DNP)
