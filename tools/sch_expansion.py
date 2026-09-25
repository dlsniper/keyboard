#!/usr/bin/env python3
"""Capture the expansion board schematic (hardware/expansion/expansion.kicad_sch).

A small board at the case wall, one per module (spec §2a "Expansion board", §6
"Expansion connector", P17). It carries the user-facing 12-pin JST-SH, the ESD arrays
on its ten non-GND pins and a 100 nF per rail, and cables to the core on the 15-pin
J_EXP. The gated 3.3 V LDO and the bus pull-ups stay on the core.

J_EXP is reversal-safe by mirroring: pin k and 16-k always carry the same net class.
5V x2 (1, 15), GND x3 (2, 14, centre 8), 3V3 x2 (3, 13); the signal pairs are
SCL-SCK, SDA-INT, RST-MOSI, DC-CS, so an end-reversed cable never puts a rail or GND
on a signal and never faces two push-pull drivers.

Run: .venv/bin/python tools/sch_expansion.py [--force]
Check: tools/kicad-check.sh
"""

import schlib

SCH = schlib.ROOT / "hardware" / "expansion" / "expansion.kicad_sch"

FP_C = "Capacitor_SMD:C_0603_1608Metric"

# Part tuples and pin-table conventions: see tools/schlib.py.
PARTS = [
    # user connector, side entry at the case wall; spec §6 pin order.
    # Stock footprint checked against JST eSH.pdf p. 1 side-entry layout: pads 0.6 x 1.55, MP 1.2 x 1.8 at +-6.8, rows 3.875 apart
    ("J1001", "Connector_Generic:Conn_01x12", "JST-SH 12", "Connector_JST:JST_SH_SM12B-SRSS-TB_1x12-1MP_P1.00mm_Horizontal",
     (14, 30),
     {"1": "GND", "2": "3V3", "3": "5V", "4": "SDA", "5": "SCL", "6": "SCK", "7": "MOSI", "8": "CS", "9": "DC",
      "10": "RST", "11": "INT", "12": "GND"},
     {"MPN": "JST SM12B-SRSS-TB"}),
    # ESD at the connector, IO + GND only (SLVSBO7O Tables 4-2, 4-3). VRWM 5.5 V, VBR 6.5 V min at 1 mA:
    # 5V stays below VBR up to the KTS1693 OVLO trip (5.95 V max)
    ("U1001", "Power_Protection:TPD4E05U06DQA", "TPD4E05U06", "keyboard:TI_USON-10_2.5x1.0mm_P0.5mm_DQA0010", (40, 18),
     {"1": "3V3", "2": "5V", "4": "SDA", "5": "SCL", "3": "GND", "8": "GND",
      "6": None, "7": None, "9": None, "10": None},
     {"MPN": "TI TPD4E05U06DQAR"}),
    # Stock RVZ footprint as on the link board (hardware/README.md)
    ("U1002", "Power_Protection:TPD6E05U06RVZ", "TPD6E05U06", "Package_SON:Texas_R-PUSON-N14", (40, 44),
     {"14": "SCK", "13": "MOSI", "12": "CS", "11": "DC", "9": "RST", "8": "INT", "5": "GND", "10": "GND",
      "1": None, "2": None, "3": None, "4": None, "6": None, "7": None},
     {"MPN": "TI TPD6E05U06RVZR"}),
    # rail decoupling at the connector: short ESD return next to the clamps; bulk stays at the core LDO
    ("C1001", "Device:C", "100n", FP_C, (62, 14),
     {"1": "3V3", "2": "GND"}, {"Voltage": "16V", "Dielectric": "X7R"}),
    ("C1002", "Device:C", "100n", FP_C, (70, 14),
     {"1": "5V", "2": "GND"}, {"Voltage": "16V", "Dielectric": "X7R"}),
    # J_EXP to the core, mirrored: pin k and 16-k carry the same net class
    ("J1002", "Connector_Generic:Conn_01x15", "J_EXP", "Connector_JST:JST_GH_SM15B-GHS-TB_1x15-1MP_P1.25mm_Horizontal",
     (92, 32),
     {"1": "5V", "2": "GND", "3": "3V3", "4": "SCL", "5": "SDA", "6": "RST", "7": "DC", "8": "GND",
      "9": "CS", "10": "MOSI", "11": "INT", "12": "SCK", "13": "3V3", "14": "GND", "15": "5V"},
     {"MPN": "JST SM15B-GHS-TB"}),
]
# 5V, 3V3 and GND come only from passive connector pins
FLAGS = [("#FLG01001", "GND", (62, 26)), ("#FLG01002", "3V3", (70, 26)), ("#FLG01003", "5V", (78, 26))]

NETS = {
    "GND": ["J1001.1", "J1001.12", "U1001.3", "U1001.8", "U1002.5", "U1002.10", "C1001.2", "C1002.2",
            "J1002.2", "J1002.8", "J1002.14"],
    "3V3": ["J1001.2", "U1001.1", "C1001.1", "J1002.3", "J1002.13"],
    "5V": ["J1001.3", "U1001.2", "C1002.1", "J1002.1", "J1002.15"],
    "SDA": ["J1001.4", "U1001.4", "J1002.5"],
    "SCL": ["J1001.5", "U1001.5", "J1002.4"],
    "SCK": ["J1001.6", "U1002.14", "J1002.12"],
    "MOSI": ["J1001.7", "U1002.13", "J1002.10"],
    "CS": ["J1001.8", "U1002.12", "J1002.9"],
    "DC": ["J1001.9", "U1002.11", "J1002.7"],
    "RST": ["J1001.10", "U1002.9", "J1002.6"],
    "INT": ["J1001.11", "U1002.8", "J1002.11"],
}

NOTES = [
    ((4, 62), "Expansion board per spec §2a, §6 (P17). J1001 JST-SH 12 at the case wall: 1 GND 2 3V3 3 5V 4 SDA 5 SCL 6 SCK 7 MOSI 8 CS 9 DC 10 RST 11 INT 12 GND.\n"
              "3V3 is the core's gated TLV75733P; 5V is local USB only (after the KTS1693). Pull-ups and bulk capacitance stay on the core.\n"
              "U1001 TPD4E05U06 (3V3, 5V, SDA, SCL) and U1002 TPD6E05U06 (SCK..INT), assembler-placed at J1001, IO + GND only (SLVSBO7O).\n"
              "VRWM 5.5 V, VBR >= 6.5 V at 1 mA: 5V up to the 5.95 V OVLO trip stays below breakdown. C1001/C1002 100 nF at the connector.\n"
              "J1002 J_EXP (JST GH 15), mirrored for reversal: 1/15 5V, 2/14 GND, 3/13 3V3, 8 GND; 4 SCL-12 SCK, 5 SDA-11 INT, 6 RST-10 MOSI, 7 DC-9 CS.\n"
              "Reversed, rails and GND meet themselves and no two push-pull drivers face each other. Cable pin 1 to pin 1."),
]

if __name__ == "__main__":
    schlib.run(SCH, "expansion", "Expansion board", 1000, PARTS, FLAGS, NOTES, NETS)
