#!/usr/bin/env python3
"""Capture the seam board schematic (hardware/seam/seam.kicad_sch).

A small 1.2 mm board standing at a seam wall, four per keyboard (spec §2a "Seam board",
§6 "Seam pogo"). It carries up to two SAMZO 4P magnetic pogo halves and a TPD4E05U06
per half, and cables to its link board on J_SEAM, which joins ahead of that board's
KTS1693. Nothing on VBUS here: the link board clamps it and keeps it off until the
handshake.

Pair A (J701): VBUS LA LB GND. Pair B (J702): GND S1 S2 VBUS. Facing pads mate k <-> k
(spring pad 1 = S end, flat pad 1 = N end; tools/gen_kicad.py samzo()), so a seam
passes LA/LB/S1/S2 straight through like a USB-C cable, and a one-pair seam uses pair A
on both sides.

KiCad design variants, one per position (default population = left):

  left         2 x spring            PR5L3715-4P-C-H
  right-left   2 x flat              PR5L2820-4P-C-F
  right-right  pair A only, spring   (J702, U702 not fitted)
  numpad       pair A only, flat     (J702, U702 not fitted)

Both halves share one land pattern (SAMZO GA0480/GA0481), so the footprint is not
overridden; flat variants override Value and MPN only.

Run: .venv/bin/python tools/sch_seam.py [--force]
Check: tools/kicad-check.sh
"""

import schlib

SCH = schlib.ROOT / "hardware" / "seam" / "seam.kicad_sch"

FP_SPRING = "keyboard:SAMZO_PR5L3715-4P-C-H_Spring"
FP_ESD = "keyboard:TI_USON-10_2.5x1.0mm_P0.5mm_DQA0010"
SPRING = {"Value": "PR5L3715-4P-C-H", "MPN": "SAMZO PR5L3715-4P-C-H"}
FLAT = {"Value": "PR5L2820-4P-C-F", "MPN": "SAMZO PR5L2820-4P-C-F"}


def esd(ref, pos, a, b):
    """TPD4E05U06: channel 1 on the pair's two signals, channel 2 unused (SLVSBO7O Table 4-2)."""
    return (ref, "Power_Protection:TPD4E05U06DQA", "TPD4E05U06", FP_ESD, pos,
            {"1": a, "2": b, "3": "GND", "8": "GND", "4": None, "5": None,
             "6": None, "7": None, "9": None, "10": None},
            {"MPN": "TI TPD4E05U06DQAR"})


# Part tuples and pin-table conventions: see tools/schlib.py.
PARTS = [
    # pogo halves, hand-soldered THT; pad 1 = spring S end / flat N end
    ("J701", "Connector_Generic:Conn_01x04", SPRING["Value"], FP_SPRING, (20, 20),
     {"1": "VBUS", "2": "LA", "3": "LB", "4": "GND"}, {"MPN": SPRING["MPN"]}),
    ("J702", "Connector_Generic:Conn_01x04", SPRING["Value"], FP_SPRING, (20, 50),
     {"1": "GND", "2": "S1", "3": "S2", "4": "VBUS"}, {"MPN": SPRING["MPN"]}),
    # ESD arrays at the contacts, assembler-placed
    esd("U701", (50, 22), "LA", "LB"),
    esd("U702", (50, 52), "S1", "S2"),
    # J_SEAM, same pin order as the link board's J602; pin-1-to-pin-1 cable
    ("J703", "Connector_Generic:Conn_01x08", "J_SEAM", "Connector_JST:JST_GH_SM08B-GHS-TB_1x08-1MP_P1.25mm_Horizontal",
     (84, 34),
     {"1": "VBUS", "2": "LA", "3": "LB", "4": "GND", "5": "GND", "6": "S1", "7": "S2", "8": "VBUS"},
     {"MPN": "JST SM08B-GHS-TB"}),
]
VARIANTS = {
    "left": set(),
    "right-left": set(),
    "right-right": {"J702", "U702"},
    "numpad": {"J702", "U702"},
}
FIELDS = {
    "right-left": {"J701": FLAT, "J702": FLAT},
    "numpad": {"J701": FLAT},
}
# VBUS and GND come only from passive connector pins
FLAGS = [("#FLG0701", "VBUS", (70, 12)), ("#FLG0702", "GND", (76, 12))]

NETS = {
    "VBUS": ["J701.1", "J702.4", "J703.1", "J703.8"],
    "GND": ["J701.4", "J702.1", "J703.4", "J703.5", "U701.3", "U701.8", "U702.3", "U702.8"],
    "LA": ["J701.2", "U701.1", "J703.2"],
    "LB": ["J701.3", "U701.2", "J703.3"],
    "S1": ["J702.2", "U702.1", "J703.6"],
    "S2": ["J702.3", "U702.2", "J703.7"],
}

NOTES = [
    ((4, 70), "Seam board per spec §6 'Seam pogo'. Variants: 'left' (default; 2 x spring), 'right-left' (2 x flat),\n"
              "'right-right' (pair A, spring), 'numpad' (pair A, flat). Pogo halves are THT, hand-soldered; U701/U702 assembler-placed.\n"
              "Pad 1 = spring S end / flat N end, so facing pads mate k <-> k: LA, LB, S1, S2 pass straight through like a USB-C cable.\n"
              "Flat seam boards mount flipped about the contact line relative to spring boards.\n"
              "TPD4E05U06 channel 1 on each pair's signals, channel 2 unused; no supply pin, so an unpowered module does not load the link.\n"
              "No VBUS parts here: the link board's SMF6.0A (and KTS1693 upstream) protect it. J_SEAM pin order matches link J602;\n"
              "cable pin 1 to pin 1. Both halves share the SAMZO GA0480/GA0481 land pattern; flat variants override Value/MPN only."),
]

if __name__ == "__main__":
    schlib.run(SCH, "seam", "Seam board", 700, PARTS, FLAGS, NOTES, NETS, variants=VARIANTS, fields=FIELDS)
