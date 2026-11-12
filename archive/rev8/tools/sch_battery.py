#!/usr/bin/env python3
"""Capture the battery board schematic (hardware/battery/battery.kicad_sch).

One pack chain per board (spec §5 "Overvoltage protection per pack", parts
shortlist "Pack chain"): 2xAA holder -> bidirectional TVS -> reverse-block
AO3415A -> OVP AO3415A switched by a TPS3840PL35 -> PTC -> J_BAT.

Placement, stubs, labels and the netlist check live in tools/schlib.py.

Run: .venv/bin/python tools/sch_battery.py [--force]
Check: tools/kicad-check.sh
"""

import schlib

SCH = schlib.ROOT / "hardware" / "battery" / "battery.kicad_sch"

FP_R = "Resistor_SMD:R_0805_2012Metric_Pad1.20x1.40mm_HandSolder"
FP_R1206 = "Resistor_SMD:R_1206_3216Metric_Pad1.30x1.75mm_HandSolder"
FP_C = "Capacitor_SMD:C_0805_2012Metric_Pad1.18x1.45mm_HandSolder"
FP_SOT23 = "Package_TO_SOT_SMD:SOT-23"

# Part tuples and pin-table conventions: see tools/schlib.py.
PARTS = [
    # cells and terminal ESD
    ("BT801", "Device:Battery", "2xAA", "keyboard:BatteryHolder_MPD_BC2AAPC_2xAA_RevP", (8, 24),
     {"1": "CELL+", "2": "GND"}, {"MPN": "MPD BC2AAPC"}),
    ("D801", "Device:D_TVS", "SMF4L9.0CA", "keyboard:D_SOD-123FL_Littelfuse", (22, 24),
     {"1": "CELL+", "2": "GND"}, {"MPN": "Littelfuse SMF4L9.0CA"}),
    # bleeder: discharges the pack node after cell removal so C801 cannot hold Q802 on into a hot 14500 swap
    ("R806", "Device:R", "330k", FP_R, (96, 44),
     {"1": "CELL+", "2": "GND"}, {"Tolerance": "1%"}),
    # reverse block: drain on the cell, source on CELL_RB, gate to GND with a VGS clamp
    ("Q801", "Transistor_FET:Q_PMOS_GSD", "AO3415A", FP_SOT23, (38, 24),
     {"1": "RB_GATE", "2": "CELL_RB", "3": "CELL+"}, {"MPN": "AOS AO3415A"}),
    ("R801", "Device:R", "100k", FP_R, (30, 42),
     {"1": "RB_GATE", "2": "GND"}, {"Tolerance": "1%"}),
    ("D802", "Diode:BZX84Cxx", "BZX84-C6V2", FP_SOT23, (42, 42),
     {"1": "RB_GATE", "2": "-", "3": "CELL_RB"}, {"MPN": "Nexperia BZX84-C6V2"}),
    # OVP switch: source on CELL_RB (back-to-back with Q801), off by default
    ("Q802", "Transistor_FET:Q_PMOS_GSD", "AO3415A", FP_SOT23, (56, 24),
     {"1": "OVP_GATE", "2": "CELL_RB", "3": "CELL_OVP"}, {"MPN": "AOS AO3415A"}),
    ("R802", "Device:R", "10M", FP_R, (54, 42),
     {"1": "CELL_RB", "2": "OVP_GATE"}, {"Tolerance": "1%"}),
    ("C801", "Device:C", "68n", FP_C, (60, 42),
     {"1": "CELL_RB", "2": "OVP_GATE"}, {"Voltage": "25V", "Dielectric": "X7R"}),
    ("D803", "Diode:BZX84Cxx", "BZX84-C6V2", FP_SOT23, (72, 42),
     {"1": "OVP_GATE", "2": "-", "3": "CELL_RB"}, {"MPN": "Nexperia BZX84-C6V2"}),
    ("R803", "Device:R", "470k", FP_R, (54, 60),
     {"1": "OVP_GATE", "2": "OVP_RST"}, {"Tolerance": "1%"}),
    ("D804", "Diode:BAT54W", "BAT54", FP_SOT23, (68, 60),
     {"1": "OVP_RST", "2": "-", "3": "OVP_GATE"}, {"MPN": "Diodes BAT54-7-F"}),
    # supervisor, senses after the reverse block through the VDD filter
    ("R804", "Device:R", "1k", FP_R, (8, 60),
     {"1": "CELL_RB", "2": "SUP_VDD"}, {"Tolerance": "1%"}),
    ("C802", "Device:C", "100n", FP_C, (16, 60),
     {"1": "SUP_VDD", "2": "GND"}, {"Voltage": "25V", "Dielectric": "X7R"}),
    ("U801", "keyboard:TPS3840PL35DBV", "TPS3840PL35DBV", "keyboard:TI_SOT-23-5_DBV0005A", (36, 60),
     {"2": "SUP_VDD", "3": "GND", "1": "OVP_RST", "4": None, "5": None}, {"MPN": "TI TPS3840PL35DBVR"}),
    # PTC, DNP OVP bypass (Li-ion build, spec §15), connector
    ("F801", "Device:Polyfuse", "PTSLR12066V175", "keyboard:Fuse_1206_Eaton_PTSLR1206", (70, 24),
     {"1": "CELL_OVP", "2": "PACK+"}, {"MPN": "Eaton PTSLR12066V175"}),
    ("R805", "Device:R", "0R", FP_R1206, (64, 14),
     {"1": "CELL_RB", "2": "CELL_OVP"}, {"DNP_reason": "OVP bypass, Li-ion build only"}),
    ("J801", "Connector_Generic:Conn_01x04", "J_BAT", "Connector_JST:JST_GH_SM04B-GHS-TB_1x04-1MP_P1.25mm_Horizontal", (88, 24),
     {"1": "PACK+", "2": "GND", "3": "GND", "4": "PACK+"}, {"MPN": "JST SM04B-GHS-TB"}),
]
DNP = {"R805"}
# CELL+ comes from a passive battery pin, SUP_VDD through R804
FLAGS = [("#FLG0801", "CELL+", (14, 12)), ("#FLG0802", "GND", (10, 34)), ("#FLG0803", "SUP_VDD", (22, 50))]

# Intended connectivity, checked against the netlist KiCad exports.
NETS = {
    "CELL+": ["BT801.1", "D801.1", "Q801.3", "R806.1"],
    "GND": ["BT801.2", "C802.2", "D801.2", "J801.2", "J801.3", "R801.2", "R806.2", "U801.3"],
    "RB_GATE": ["D802.1", "Q801.1", "R801.1"],
    "CELL_RB": ["C801.1", "D802.3", "D803.3", "Q801.2", "Q802.2", "R802.1", "R804.1", "R805.1"],
    "OVP_GATE": ["C801.2", "D803.1", "D804.3", "Q802.1", "R802.2", "R803.1"],
    "OVP_RST": ["D804.1", "R803.2", "U801.1"],
    "SUP_VDD": ["C802.1", "R804.2", "U801.2"],
    "CELL_OVP": ["F801.1", "Q802.3", "R805.2"],
    "PACK+": ["F801.2", "J801.1", "J801.4"],
}

NOTES = [
    ((6, 72), "Pack chain per spec §5. Rev FET and OVP FET are back-to-back AO3415As, common source on CELL_RB.\n"
              "OVP FET off by default: R802 10M holds its gate at the source, C801 sits gate-to-source (never to GND),\n"
              "U801 pulls the gate down through R803 470k (tau = 32 ms, >= 25 ms at -10 %); D804 speeds turn-off.\n"
              "D802/D803 clamp VGS to ~6.2 V (AO3415A is +/-8 V; a 14500 pair is 8.4 V). U801 MR and CT float (TPS3840 pin table).\n"
              "R806 330k bleeds CELL+ (8.5 uA at 2.8 V): a charged pack node let C801 hold Q802 on, so a 14500 swapped in within\n"
              "~2-4 s reached VBAT (ngspice, 2026-09-15); with R806 the window is ~0.5 s. Core pack inputs keep CIN at 1 uF.\n"
              "J_BAT pinout is mirror-symmetric (PACK+, GND, GND, PACK+): an end-reversed cable still lands + on +.\n"
              "The 10M gate node needs residue-free assembly."),
]


if __name__ == "__main__":
    schlib.run(SCH, "battery", "Battery board", 800, PARTS, FLAGS, NOTES, NETS, dnp=DNP)
