#!/usr/bin/env python3
"""Generate the KiCad project skeleton and the custom library for hardware/.

Idempotent for the library (always regenerated). Project files are only created
when missing, so schematic and board work is never overwritten.

Every custom land pattern and pinout below cites the datasheet it came from;
parts whose land pattern could not be verified are left without a footprint.

Run: python3 tools/gen_kicad.py
Then: tools/kicad-check.sh   (normalises the library and runs ERC/DRC)
"""

import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HW = ROOT / "hardware"
LIB = HW / "lib"
LIBNAME = "keyboard"

# project dir (relative to hardware/), reference start, board thickness (mm)
# Rev 9: only the boards still in hardware/. The rev 8 boards live under archive/rev8/ and
# are not generated, checked or read by any tool; the rev 9 key boards are added at M1.
PROJECTS = [
    ("usb-port", 500, 1.6),
    ("dial", 900, 1.6),
    ("left", 1, 1.6),
    ("right", 1, 1.6),
    ("numpad", 1, 1.6),
    ("port-module", 1, 1.6),
    ("hub-core", 100, 1.6),
    ("hub-conn", 200, 1.6),
    ("battery", 800, 1.6),
    ("pod", 1, 1.6),
    ("pod-power", 1, 1.6),
    ("hub-radio", 1, 1.6),
]
# Key boards (tools/sch_keys.py) carry the vendored kiswitch footprint libraries
KEY_BOARDS = {"left", "right", "numpad"}

# Design-rule minimums from the spec (§12): JLCPCB economy 0.127 mm track/space,
# 0.2 mm drill; the USB port and link boards carry the KTS1693 0.4 mm WLCSP and
# are quoted with 0.15 mm vias.
FINE_PITCH = {"usb-port"}

# Four copper layers (2026-09-16): the core carries the MCU module, USB D+/D- and two boosts.
# The dielectric split below is a placeholder until the fab stackup is chosen (spec §12, Phase 4).
FOUR_LAYER = set()


# --------------------------------------------------------------------------
# s-expression helpers
# --------------------------------------------------------------------------

def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def n(x):
    return f"{x:.4f}".rstrip("0").rstrip(".") if isinstance(x, float) else str(x)


def font(size=1.27, hide=False, justify=None):
    j = f" (justify {justify})" if justify else ""
    h = " (hide yes)" if hide else ""
    return f"(effects (font (size {n(size)} {n(size)})){j}{h})"


# --------------------------------------------------------------------------
# symbols
# --------------------------------------------------------------------------

def symbol(name, ref, fp, datasheet, descr, keywords, left, right, bottom=(), top=(), width=15.24):
    """Box symbol. left/right/top/bottom: lists of (number, name, electrical type).

    Pins sharing a name are stacked on one position with all but the first hidden.
    Hidden stacked pins are typed passive (KiCad library convention): KiCad joins
    hidden power-input pins to a global net named after the pin, so a hidden "IN"
    would otherwise rename or merge nets across the sheet.
    """
    def column(pins):
        groups, order = {}, []
        for num, nm, et in pins:
            if nm not in groups:
                groups[nm] = []
                order.append(nm)
            groups[nm].append((num, et))
        return order, groups

    lorder, lgroups = column(left)
    rorder, rgroups = column(right)
    rows = max(len(lorder), len(rorder), 1)
    # bottom/top pins print their names inside the box, so leave two rows clear for them
    extra = (3 if bottom else 0) + (3 if top else 0)
    h = (rows + 1 + extra) * 2.54
    half_w = width / 2
    top_y = round((h / 2) / 2.54) * 2.54
    if top:
        top_y_rows = top_y - 3 * 2.54
    else:
        top_y_rows = top_y
    bot_y = top_y - h
    below = bot_y - (5.08 if bottom else 1.27)
    above = top_y + (5.08 if top else 1.27)

    out = []
    props = [
        ("Reference", ref, (half_w + 1.27, above), False, "left"),
        ("Value", name, (half_w + 1.27, below), False, "left"),
        ("Footprint", fp, (0, below - 2.54), True, None),
        ("Datasheet", datasheet, (0, below - 5.08), True, None),
        ("Description", descr, (0, below - 7.62), True, None),
        ("ki_keywords", keywords, (0, 0), True, None),
    ]
    out.append(f"\t(symbol {q(name)} (exclude_from_sim no) (in_bom yes) (on_board yes)")
    for key, val, (x, y), hide, just in props:
        out.append(f"\t\t(property {q(key)} {q(val)} (at {n(x)} {n(y)} 0) {font(hide=hide, justify=just)})")
    out.append(f"\t\t(symbol {q(name + '_0_1')} (rectangle (start {n(-half_w)} {n(top_y)}) (end {n(half_w)} {n(bot_y)})"
               f" (stroke (width 0.254) (type default)) (fill (type background))))")
    pins = []

    def emit(x, y, rot, nm, grp):
        for i, (num, et) in enumerate(grp):
            hide = " (hide yes)" if i else ""
            et = et if not i else "passive"
            pins.append(f"\t\t\t(pin {et} line (at {n(x)} {n(y)} {rot}) (length 2.54){hide}"
                        f" (name {q(nm)} {font()}) (number {q(num)} {font()}))")

    for i, nm in enumerate(lorder):
        emit(-half_w - 2.54, top_y_rows - 2.54 * (i + 1), 0, nm, lgroups[nm])
    for i, nm in enumerate(rorder):
        emit(half_w + 2.54, top_y_rows - 2.54 * (i + 1), 180, nm, rgroups[nm])
    for pinset, y, rot in ((bottom, bot_y - 2.54, 90), (top, top_y + 2.54, 270)):
        order, groups = column(pinset)
        for i, nm in enumerate(order):
            # 5.08 mm apart, centred on the grid (2.54 mm spacing rounded an even count onto one point)
            x = (2 * i - (len(order) - 1)) * 2.54
            emit(x, y, rot, nm, groups[nm])
    out.append(f"\t\t(symbol {q(name + '_1_1')}")
    out.extend(pins)
    out.append("\t\t)")
    out.append("\t)")
    return "\n".join(out)


SYMBOLS = [
    # Kinetic KTS1693 rev 04d, "Pin Descriptions" (p. 2)
    symbol(
        "KTS1693EVB", "U", f"{LIBNAME}:Kinetic_WLCSP-20_1.935x2.16mm_Layout4x5_P0.4mm",
        "https://www.kinet-ic.com/uploads/web/KTS1693/KTS1693-04d.pdf",
        "USB VBUS OVP switch, 30 V abs-max, adjustable OVLO, ISET OCP, ACOK output (KTS1693EVB-TR), WLCSP-20",
        "OVP VBUS USB protection Kinetic",
        left=[(p, "IN", "power_in") for p in ("C3", "D2", "D3", "E2", "E3", "E4")]
        + [("D1", "OVLO", "input"), ("E1", "ISET", "passive"), ("B1", "~{EN}", "input"), ("B4", "OC_MODE", "input")],
        right=[(p, "OUT", "power_out") for p in ("A2", "A3", "A4", "B2", "B3", "C2")]
        + [("C1", "~{ACOK}", "open_collector"), ("A1", "CDET", "open_collector")],
        bottom=[("C4", "GND", "power_in"), ("D4", "GND", "power_in")],
    ),
    # TI LM66200 SLVSG04, Table 5-1; DRL package shares SOT-583-8 with TPS2116DRL
    symbol(
        "LM66200DRL", "U", "Package_TO_SOT_SMD:SOT-583-8",
        "https://www.ti.com/lit/ds/symlink/lm66200.pdf",
        "Dual ideal-diode OR, 1.6-5.5 V, 2.5 A, active-low ON, SOT-583-8",
        "ideal diode OR power mux",
        left=[("3", "VIN1", "power_in"), ("6", "VIN2", "power_in"), ("4", "~{ON}", "input")],
        right=[("2", "VOUT", "power_out"), ("7", "VOUT", "power_out"), ("8", "ST", "output")],
        bottom=[("1", "GND", "power_in"), ("5", "GND", "power_in")],
    ),
    # TI TPS3840 SNVSB03E, Table 5-1 (PL: active-low push-pull RESET on pin 1)
    symbol(
        "TPS3840PL35DBV", "U", f"{LIBNAME}:TI_SOT-23-5_DBV0005A",
        "https://www.ti.com/lit/ds/symlink/tps3840.pdf",
        "Nano-power supervisor, 3.5 V falling threshold, push-pull active-low RESET, SOT-23-5",
        "supervisor reset voltage monitor",
        left=[("2", "VDD", "power_in"), ("4", "~{MR}", "input"), ("5", "CT", "passive")],
        right=[("1", "~{RESET}", "output")],
        bottom=[("3", "GND", "power_in")],
    ),
    symbol(
        "TPS3840PH18DBV", "U", f"{LIBNAME}:TI_SOT-23-5_DBV0005A",
        "https://www.ti.com/lit/ds/symlink/tps3840.pdf",
        "Nano-power supervisor, 1.8 V falling threshold, push-pull active-high RESET, SOT-23-5",
        "supervisor reset voltage monitor",
        left=[("2", "VDD", "power_in"), ("4", "~{MR}", "input"), ("5", "CT", "passive")],
        right=[("1", "RESET", "output")],
        bottom=[("3", "GND", "power_in")],
    ),
    # TI TPS22950 SLVSFJ2B, Table 6-1, WCSP column; the L variant ships only as YBH
    symbol(
        "TPS22950LYBH", "U", f"{LIBNAME}:Texas_DSBGA-6_0.706x1.106mm_Layout2x3_P0.4mm_YBH",
        "https://www.ti.com/lit/ds/symlink/tps22950.pdf",
        "Current-limited load switch, 1.8-5.5 V, 0.5-3.5 A adjustable limit, latch-off, no reverse current blocking, DSBGA-6 (YBH)",
        "load switch current limit",
        left=[("B1", "VIN", "power_in"), ("A1", "ON", "input"), ("C2", "ILIM", "passive")],
        right=[("B2", "VOUT", "power_out"), ("A2", "~{FLT}", "open_collector")],
        bottom=[("C1", "GND", "power_in")],
    ),
    # TI TPS629210 SLVSGE0B, Table 6-1 (DRL, SOT-583): 3.3 V buck of the wireless power board (tools/sch_pod.py)
    symbol(
        "TPS629210DRL", "U", "Package_TO_SOT_SMD:SOT-583-8",
        "https://www.ti.com/lit/ds/symlink/tps629210.pdf",
        "Buck converter, 3-17 V in, 1 A, 4 uA quiescent, VSET / Smart-CONFIG, SOT-583 (DRL)",
        "buck converter low Iq TI",
        left=[("6", "VIN", "power_in"), ("7", "EN", "input"), ("8", "MODE/S-CONF", "passive")],
        right=[("4", "SW", "passive"), ("3", "VOS", "input"), ("1", "FB/VSET", "passive"), ("2", "PG", "open_collector")],
        bottom=[("5", "GND", "power_in")],
    ),
    # TI TPS63070 SLVSC58, Pin Functions (RNM, 15-pin VQFN 2.5 x 3 mm); TPS630701 = fixed 5.0 V. Footprint: board session.
    symbol(
        "TPS630701RNM", "U", "",
        "https://www.ti.com/lit/ds/symlink/tps63070.pdf",
        "Buck-boost converter, 2-16 V in, fixed 5.0 V out, 2 A at 4 V in, power save mode, VQFN-15 (RNM)",
        "buck-boost converter TI",
        left=[("12", "VIN", "power_in"), ("13", "VIN", "power_in"), ("14", "EN", "input"), ("1", "PS/SYNC", "input"),
              ("15", "VSEL", "input"), ("11", "L1", "passive"), ("9", "L2", "passive")],
        right=[("7", "VOUT", "passive"), ("8", "VOUT", "passive"), ("5", "FB", "input"), ("6", "FB2", "passive"),
               ("2", "PG", "open_collector"), ("3", "VAUX", "passive")],
        bottom=[("4", "GND", "power_in"), ("10", "PGND", "power_in")],
    ),
    # TI TPS2553 SLVS841, Pin Functions (DBV, SOT-23-6; EN active high): current cap of the wireless LED rail
    symbol(
        "TPS2553DBV", "U", f"{LIBNAME}:TI_SOT-23-6_DBV0006A",
        "https://www.ti.com/lit/ds/symlink/tps2553.pdf",
        "Current-limited power switch, 2.5-6.5 V, limit 75 mA-1.7 A by RILIM, EN active high, SOT-23-6 (DBV)",
        "current limit power switch",
        left=[("1", "IN", "power_in"), ("3", "EN", "input"), ("5", "ILIM", "passive")],
        right=[("6", "OUT", "passive"), ("4", "~{FAULT}", "open_collector")],
        bottom=[("2", "GND", "power_in")],
    ),
    # TI TPS22918 SLVSCY5 (DBV, SOT-23-6): key-board LED rail switch
    symbol(
        "TPS22918DBV", "U", f"{LIBNAME}:TI_SOT-23-6_DBV0006A",
        "https://www.ti.com/lit/ds/symlink/tps22918.pdf",
        "Load switch, 1-5.5 V, 2 A, 60 mOhm, adjustable rise time (CT), quick output discharge (QOD), SOT-23-6 (DBV)",
        "load switch slew rate",
        left=[("1", "VIN", "power_in"), ("3", "ON", "input"), ("4", "CT", "passive")],
        right=[("6", "VOUT", "power_out"), ("5", "QOD", "passive")],
        bottom=[("2", "GND", "power_in")],
    ),
    # Microchip MCP23S17 (DS20001952), SOIC-28 wide. Stock Interface_Expansion symbol types SO as output, which
    # fails ERC when two chips share MISO (right); SO is tri-state (high-Z while CS is high).
    symbol(
        "MCP23S17-E_SO", "U", "Package_SO:SOIC-28W_7.5x17.9mm_P1.27mm",
        "https://ww1.microchip.com/downloads/en/DeviceDoc/20001952C.pdf",
        "16-bit SPI I/O expander, 10 MHz, hardware address pins A0-A2, SOIC-28 wide",
        "gpio expander spi",
        left=[(str(1 + i), f"GPB{i}", "bidirectional") for i in range(8)]
        + [("15", "A0", "input"), ("16", "A1", "input"), ("17", "A2", "input"),
           ("18", "~{RESET}", "input"), ("11", "~{CS}", "input"), ("12", "SCK", "input"), ("13", "SI", "input")],
        right=[(str(21 + i), f"GPA{i}", "bidirectional") for i in range(8)]
        + [("14", "SO", "tri_state"), ("20", "INTA", "tri_state"), ("19", "INTB", "tri_state")],
        top=[("9", "VDD", "power_in")],
        bottom=[("10", "VSS", "power_in")],
        width=17.78,
    ),
    # 24-pin full-featured USB-C receptacle for the port board (GCT USB4085 and the stock 16P symbols have no TX/RX).
    # Same pin names as KiCad's Connector:USB_C_Receptacle, all passive: the board ties RX/TX/SBU/D to signal nets,
    # and a bidirectional pin on GND trips ERC against PWR_FLAG.
    symbol(
        "USB_C_Receptacle_24P", "J", "Connector_USB:USB_C_Receptacle_Amphenol_12401548E4-2A",
        "https://www.usb.org/document-library/usb-type-cr-cable-and-connector-specification",
        "USB Type-C receptacle, all 24 contacts plus shield (full-featured)",
        "usb type-c receptacle full featured",
        left=[("A4", "VBUS", "passive"), ("A9", "VBUS", "passive"), ("B4", "VBUS", "passive"), ("B9", "VBUS", "passive"),
              ("A1", "GND", "passive"), ("A12", "GND", "passive"), ("B1", "GND", "passive"), ("B12", "GND", "passive"),
              ("A5", "CC1", "passive"), ("B5", "CC2", "passive"), ("A6", "D+", "passive"), ("B6", "D+", "passive"),
              ("A7", "D-", "passive"), ("B7", "D-", "passive"), ("A8", "SBU1", "passive"), ("B8", "SBU2", "passive")],
        right=[("A2", "TX1+", "passive"), ("A3", "TX1-", "passive"), ("B2", "TX2+", "passive"), ("B3", "TX2-", "passive"),
               ("B11", "RX1+", "passive"), ("B10", "RX1-", "passive"), ("A11", "RX2+", "passive"), ("A10", "RX2-", "passive"),
               ("SH", "SHIELD", "passive")],
    ),
    # TI TPS61023 SLVSF14B, Pin Functions; DRL = SOT-563
    symbol(
        "TPS61023DRL", "U", "Package_TO_SOT_SMD:SOT-563",
        "https://www.ti.com/lit/ds/symlink/tps61023.pdf",
        "Synchronous boost, 0.5-5.5 V in, adjustable output, 3.7 A valley switch limit, SOT-563",
        "boost converter step-up",
        left=[("3", "VIN", "power_in"), ("5", "SW", "passive"), ("2", "EN", "input")],
        right=[("6", "VOUT", "power_out"), ("1", "FB", "input")],
        bottom=[("4", "GND", "power_in")],
    ),
    # ADI/Maxim MAX17220-MAX17225 datasheet, Pin Description (uDFN column).
    # Land pattern (Maxim 90-0004, package L622+1C) not yet obtained: no footprint.
    symbol(
        "MAX17222ELT", "U", "",
        "https://www.analog.com/media/en/technical-documentation/data-sheets/max17220-max17225.pdf",
        "nanoPower boost, 0.4-5.5 V in, RSEL-set output, 0.5 A peak inductor limit, true shutdown, uDFN-6 2x2 (footprint pending: Maxim land pattern 90-0004)",
        "boost converter step-up nanopower",
        left=[("5", "IN", "power_in"), ("2", "LX", "passive"), ("6", "EN", "input")],
        right=[("1", "OUT", "power_out"), ("4", "SEL", "passive")],
        bottom=[("3", "GND", "power_in")],
    ),
    # Bourns PEC11R-4xxxF-Sxxxx (rev D04/26): Device:RotaryEncoder_Switch pins plus MP for
    # the two mounting lugs (footprint pads "MP"), so the lugs can be tied to GND
    symbol(
        "RotaryEncoder_Switch_MP", "SW", f"{LIBNAME}:RotaryEncoder_Bourns_PEC11R-4xxxF-Sxxxx_Vertical",
        "https://www.bourns.com/docs/Product-Datasheets/PEC11R.pdf",
        "Rotary encoder with push switch and mounting-lug pin (MP), Bourns PEC11R-4xxxF-Sxxxx",
        "rotary encoder switch Bourns PEC11R",
        left=[("A", "A", "passive"), ("C", "C", "passive"), ("B", "B", "passive")],
        right=[("S1", "S1", "passive"), ("S2", "S2", "passive")],
        bottom=[("MP", "MP", "passive")],
    ),
    # TI TLV757P SBVS320, Pin Functions (DBV column). The stock Regulator_Linear:TLV75733PDBV
    # extends TLV70012_SOT23-5, and derived symbols trip ERC lib_symbol_mismatch through kicad-sch-api
    symbol(
        "TLV75733PDBV", "U", f"{LIBNAME}:TI_SOT-23-5_DBV0005A",
        "https://www.ti.com/lit/ds/symlink/tlv757p.pdf",
        "1 A LDO, 3.3 V fixed, 1.45-5.5 V in, 6.0 V abs-max, active discharge, SOT-23-5",
        "LDO regulator linear TI",
        left=[("1", "IN", "power_in"), ("3", "EN", "input")],
        right=[("5", "OUT", "power_out"), ("4", "NC", "no_connect")],
        bottom=[("2", "GND", "power_in")],
    ),
    # TI TPS7A02 SBVS277C, Table 5-1 (DBV column); same pinout and DBV0005A drawing (4214839/K) as the
    # TLV75733P, which stays its drop-in second source on the key boards (2026-09-29). Not in stock KiCad.
    symbol(
        "TPS7A0233PDBV", "U", f"{LIBNAME}:TI_SOT-23-5_DBV0005A",
        "https://www.ti.com/lit/ds/symlink/tps7a02.pdf",
        "200 mA nanopower LDO, 3.3 V fixed, 25 nA IQ, 1.5-6.0 V in, 6.5 V abs-max, active discharge, SOT-23-5",
        "LDO regulator linear nanopower TI",
        left=[("1", "IN", "power_in"), ("3", "EN", "input")],
        right=[("5", "OUT", "power_out"), ("4", "NC", "no_connect")],
        bottom=[("2", "GND", "power_in")],
    ),
    # TI TPD4E1U06 SLVSBQ9D, "Pin Functions" (DBV): four independent I/O channels, NC may float
    symbol(
        "TPD4E1U06DBV", "U", f"{LIBNAME}:TI_SOT-23-6_DBV0006A",
        "https://www.ti.com/lit/ds/symlink/tpd4e1u06.pdf",
        "Quad-channel unidirectional ESD protection, 5.5 V VRWM, 0.8 pF, IEC 61000-4-2 +/-15 kV, SOT-23-6",
        "ESD TVS protection TI",
        left=[("1", "D1+", "passive"), ("3", "D2+", "passive"), ("5", "NC", "passive")],
        right=[("6", "D1-", "passive"), ("4", "D2-", "passive")],
        bottom=[("2", "GND", "passive")],
    ),
    # TI MSPM0G350x SLASEX6C (rev C, Oct 2025), Table 6-2 "48 LQFP, VQFN" column, checked
    # against Figure 6-3 (48-pin PT): 44 GPIOs, NRST 4, VDD 6, VSS 7, VCORE 48 (core regulator
    # output, capacitor only), no exposed pad. Names carry the one function the key board relies
    # on: default BSL I2C (PA0/PA1, 5 V-tolerant open-drain), BSL UART (PA10/PA11), BSL_invoke
    # (PA18), SWD (PA19/PA20), crystal pins, ROSC and VREF.
    symbol(
        "MSPM0G3505SPT", "U", f"{LIBNAME}:TI_LQFP-48_7x7mm_P0.5mm_PT0048A",
        "https://www.ti.com/lit/ds/symlink/mspm0g3505.pdf",
        "Arm Cortex-M0+ MCU, 80 MHz, 32 KB flash, 16 KB SRAM, 1.62-3.6 V, 2x I2C, QEI, ROM I2C/UART bootloader, LQFP-48 (PT)",
        "MSPM0 MSPM0G3505 TI microcontroller ARM Cortex-M0+",
        left=[("4", "NRST", "input")] + [
            (num, nm, "bidirectional") for num, nm in (
                ("1", "PA0/BSLSDA"), ("2", "PA1/BSLSCL"), ("8", "PA2/ROSC"), ("9", "PA3/LFXIN"),
                ("10", "PA4/LFXOUT"), ("11", "PA5/HFXIN"), ("12", "PA6/HFXOUT"), ("13", "PA7"),
                ("16", "PA8"), ("17", "PA9"), ("18", "PA10/BSLTX"), ("19", "PA11/BSLRX"),
                ("27", "PA12"), ("28", "PA13"), ("29", "PA14"), ("30", "PA15"), ("31", "PA16"),
                ("32", "PA17"), ("33", "PA18/BSL_INVOKE"), ("34", "PA19/SWDIO"), ("35", "PA20/SWCLK"),
                ("39", "PA21/VREF-"))],
        right=[(num, nm, "bidirectional") for num, nm in (
            ("40", "PA22"), ("43", "PA23/VREF+"), ("44", "PA24"), ("45", "PA25"), ("46", "PA26"),
            ("47", "PA27"), ("3", "PA28"), ("5", "PA31"), ("14", "PB2"), ("15", "PB3"), ("20", "PB6"),
            ("21", "PB7"), ("22", "PB8"), ("23", "PB9"), ("24", "PB14"), ("25", "PB15"), ("26", "PB16"),
            ("36", "PB17"), ("37", "PB18"), ("38", "PB19"), ("41", "PB20"), ("42", "PB24"))],
        top=[("6", "VDD", "power_in"), ("48", "VCORE", "power_out")],
        bottom=[("7", "VSS", "power_in")],
        width=30.48,
    ),
    # ---- hub (rev 9.1, tools/sch_hub.py) ------------------------------------------------------------
    # TI LM74610-Q1 SNOSCZ1B, section 5 (DGK, VSSOP-8). Floating: no ground pin.
    symbol(
        "LM74610QDGK", "U", "Package_SO:VSSOP-8_3x3mm_P0.65mm",
        "https://www.ti.com/lit/ds/symlink/lm74610-q1.pdf",
        "Zero-Iq ideal-diode controller for one external N-FET, reverse polarity to -45 V, VSSOP-8",
        "ideal diode controller OR-ing reverse polarity",
        left=[("4", "ANODE", "passive"), ("1", "VCAPL", "passive"), ("3", "NC3", "passive")],
        right=[("8", "CATHODE", "passive"), ("7", "VCAPH", "passive"), ("6", "GATE", "passive"),
               ("2", "PULLDN", "passive"), ("5", "NC5", "passive")],
    ),
    # TI TPS552892 SLVSH28A, Table 5-1 (RYQ, 21-pin VQFN-HR 3 x 5 mm, no exposed pad pin). Footprint at M2.
    symbol(
        "TPS552892RYQ", "U", "keyboard:TI_VQFN-HR-21_5x3mm_RYQ0021A",
        "https://www.ti.com/lit/ds/symlink/tps552892.pdf",
        "Buck-boost converter, 3-36 V in, 0.8-22 V out by FB divider, 8 A average inductor current limit, PFM, VQFN-HR-21 (RYQ)",
        "buck-boost converter TI",
        left=[("7", "VIN", "power_in"), ("1", "EN/UVLO", "input"), ("2", "MODE", "input"), ("5", "DITH/SYNC", "input"),
              ("6", "FSW", "passive"), ("21", "EXTVCC", "input"), ("18", "VCC", "power_out"), ("20", "BOOT1", "passive"),
              ("8", "SW1", "passive")],
        right=[("11", "VOUT", "power_out"), ("12", "ISP", "input"), ("13", "ISN", "input"), ("14", "FB", "input"),
               ("15", "COMP", "passive"), ("16", "CDC", "passive"), ("3", "PG", "open_collector"),
               ("4", "CC", "open_collector"), ("19", "BOOT2", "passive"), ("10", "SW2", "passive")],
        bottom=[("17", "AGND", "power_in"), ("9", "PGND", "power_in")],
    ),
    # TI TPS3840 SNVSB03E, Table 5-1: any PLxx option (push-pull, active-low RESET); the value field names the threshold
    symbol(
        "TPS3840PLxxDBV", "U", f"{LIBNAME}:TI_SOT-23-5_DBV0005A",
        "https://www.ti.com/lit/ds/symlink/tps3840.pdf",
        "Nano-power supervisor, push-pull active-low RESET, threshold per value (PL40 4.0 V, PL43 4.3 V), SOT-23-5",
        "supervisor reset voltage monitor",
        left=[("2", "VDD", "passive"), ("4", "~{MR}", "passive"), ("5", "CT", "passive")],
        right=[("1", "~{RESET}", "passive")],
        bottom=[("3", "GND", "power_in")],
    ),
    # TI TPS3700 SBVS187, DDC (SOT-23-6 thin) pinout: window comparator, 400 mV thresholds, open-drain outputs, 1.8-18 V
    symbol(
        "TPS3700DDC", "U", "Package_TO_SOT_SMD:TSOT-23-6",
        "https://www.ti.com/lit/ds/symlink/tps3700.pdf",
        "Window comparator, 400 mV reference, OUTA low while INA+ is under it, OUTB low while INB- is over it, open drain, SOT-23-6 thin",
        "overvoltage undervoltage detector window comparator",
        left=[("5", "VDD", "passive"), ("3", "INA+", "passive"), ("4", "INB-", "passive")],
        right=[("1", "OUTA", "passive"), ("6", "OUTB", "passive")],
        bottom=[("2", "GND", "power_in")],
    ),
    # 74x125 quad tri-state buffer as one unit (the stock 74xx symbols are derived and multi-unit). SOIC-14.
    symbol(
        "74x125_SO14", "U", "Package_SO:SOIC-14_3.9x8.7mm_P1.27mm",
        "https://www.ti.com/lit/ds/symlink/sn74lvc125a.pdf",
        "Quad bus buffer, tri-state outputs, active-low output enables (74LVC125A at 3.3 V, 74AHCT125 at 5 V), SOIC-14",
        "buffer tri-state level shifter 125",
        left=[("1", "~{1OE}", "input"), ("2", "1A", "input"), ("4", "~{2OE}", "input"), ("5", "2A", "input"),
              ("10", "~{3OE}", "input"), ("9", "3A", "input"), ("13", "~{4OE}", "input"), ("12", "4A", "input")],
        right=[("3", "1Y", "tri_state"), ("6", "2Y", "tri_state"), ("8", "3Y", "tri_state"), ("11", "4Y", "tri_state")],
        top=[("14", "VCC", "power_in")],
        bottom=[("7", "GND", "power_in")],
    ),
    # Diodes DMN63D8LDW (SOT-363): 1 S1, 2 G1, 3 D2, 4 S2, 5 G2, 6 D1
    symbol(
        "DMN63D8LDW", "Q", "Package_TO_SOT_SMD:SOT-363_SC-70-6",
        "https://www.diodes.com/assets/Datasheets/DMN63D8LDW.pdf",
        "Dual N-channel MOSFET, 30 V, VGS +/-20 V, Vth 0.8-1.5 V, ESD-protected gates, SOT-363",
        "dual N-MOSFET small signal",
        left=[("2", "G1", "passive"), ("5", "G2", "passive")],
        right=[("6", "D1", "passive"), ("1", "S1", "passive"), ("3", "D2", "passive"), ("4", "S2", "passive")],
    ),
    # Vishay SQ4184EY (SO-8, datasheet drawing): S 1-3, G 4, D 5-8. In the LM74610-Q1 datasheet's FET table.
    symbol(
        "SQ4184EY", "Q", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
        "https://www.vishay.com/docs/65946/sq4184ey.pdf",
        "N-channel MOSFET, 40 V, VGS +/-20 V, 5.6 mOhm max at 4.5 V, SO-8",
        "N-MOSFET SO-8 ideal diode",
        left=[("4", "G", "passive")],
        right=[("5", "D", "passive"), ("6", "D", "passive"), ("7", "D", "passive"), ("8", "D", "passive"),
               ("1", "S", "passive"), ("2", "S", "passive"), ("3", "S", "passive")],
    ),
    # TI CSD25483F4 SLPS449 (FemtoFET, 1.0 x 0.6 mm LGA): 1 G, 2 S, 3 D, to be confirmed in the M1 review
    symbol(
        "CSD25483F4", "Q", "keyboard:TI_PicoStar-3_1.0x0.6mm_YJC0003A",
        "https://www.ti.com/lit/ds/symlink/csd25483f4.pdf",
        "P-channel FemtoFET, -20 V, VGS -12 V, IDSS <= 100 nA, LGA 1.0 x 0.6 mm",
        "P-MOSFET FemtoFET low leakage",
        left=[("1", "G", "passive")],
        right=[("2", "S", "passive"), ("3", "D", "passive")],
    ),
    # Raspberry Pi Pico 2 W header pin-out (40 pins). The stock MCU_Module symbol types GND and AGND as power
    # outputs, which fails ERC as soon as both are grounded.
    symbol(
        "Pico2W", "A", "Module:RaspberryPi_Pico_Common_THT",
        "https://datasheets.raspberrypi.com/picow/pico-2-w-datasheet.pdf",
        "Raspberry Pi Pico 2 W (RP2350, CYW43439), 40-pin module on pin sockets",
        "Pico 2 W RP2350 module",
        left=[(str(pin), f"GP{g}", "bidirectional") for pin, g in
              ((1, 0), (2, 1), (4, 2), (5, 3), (6, 4), (7, 5), (9, 6), (10, 7), (11, 8), (12, 9), (14, 10), (15, 11),
               (16, 12), (17, 13), (19, 14), (20, 15))],
        right=[("40", "VBUS", "passive"), ("39", "VSYS", "power_in"), ("37", "3V3_EN", "passive"), ("36", "3V3", "power_out"),
               ("35", "ADC_VREF", "passive"), ("34", "GP28_ADC2", "bidirectional"), ("32", "GP27_ADC1", "bidirectional"),
               ("31", "GP26_ADC0", "bidirectional"), ("30", "RUN", "passive"), ("29", "GP22", "bidirectional"),
               ("27", "GP21", "bidirectional"), ("26", "GP20", "bidirectional"), ("25", "GP19", "bidirectional"),
               ("24", "GP18", "bidirectional"), ("22", "GP17", "bidirectional"), ("21", "GP16", "bidirectional")],
        bottom=[(str(n), "GND", "passive") for n in (3, 8, 13, 18, 23, 28, 38)] + [("33", "AGND", "passive")],
        width=25.4,
    ),
]


def write_symbols():
    body = "\n".join(SYMBOLS)
    text = f'(kicad_symbol_lib (version 20241209) (generator "gen_kicad") (generator_version "10.0")\n{body}\n)\n'
    (LIB / f"{LIBNAME}.kicad_sym").write_text(text)


# --------------------------------------------------------------------------
# footprints
# --------------------------------------------------------------------------

def fp_text(ref_y, val_y, name):
    return (f'\t(property "Reference" "REF**" (at 0 {n(ref_y)} 0) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))\n'
            f'\t(property "Value" {q(name)} (at 0 {n(val_y)} 0) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))\n')


def rect(layer, x1, y1, x2, y2, w):
    return f'\t(fp_rect (start {n(x1)} {n(y1)}) (end {n(x2)} {n(y2)}) (stroke (width {n(w)}) (type solid)) (fill no) (layer {q(layer)}))\n'


def circle(layer, cx, cy, r, w, fill=False):
    return (f'\t(fp_circle (center {n(cx)} {n(cy)}) (end {n(cx + r)} {n(cy)}) (stroke (width {n(w)}) (type solid))'
            f' (fill {"yes" if fill else "no"}) (layer {q(layer)}))\n')


def footprint(name, descr, tags, attr, body, ref_y, val_y):
    return (f'(footprint {q(name)} (version 20241229) (generator "gen_kicad") (generator_version "10.0") (layer "F.Cu")\n'
            f'\t(descr {q(descr)})\n\t(tags {q(tags)})\n{fp_text(ref_y, val_y, name)}\t(attr {attr})\n{body})\n')


def csp(name, descr, cols, rows, pitch, pad_d, mask_d, body_x, body_y):
    """Ball grid, top view, A1 top-left; rows are letters along +Y, columns numbers along +X."""
    letters = "ABCDEFGHJKLMNPRTUVWY"
    x0 = -(cols - 1) * pitch / 2
    y0 = -(rows - 1) * pitch / 2
    body = ""
    for r in range(rows):
        for c in range(cols):
            x, y = x0 + c * pitch, y0 + r * pitch
            margin = (mask_d - pad_d) / 2
            body += (f'\t(pad {q(letters[r] + str(c + 1))} smd circle (at {n(x)} {n(y)}) (size {n(pad_d)} {n(pad_d)})'
                     f' (layers "F.Cu" "F.Paste" "F.Mask") (solder_mask_margin {n(margin)}))\n')
    bx, by = body_x / 2, body_y / 2
    body += rect("F.Fab", -bx, -by, bx, by, 0.1)
    cy = max(bx, by) + 0.25
    body += rect("F.CrtYd", -bx - 0.25, -by - 0.25, bx + 0.25, by + 0.25, 0.05)
    # pin A1 marker outside the body on silkscreen
    body += circle("F.SilkS", -bx - 0.3, -by - 0.3, 0.08, 0.1, fill=True)
    return footprint(name, descr, "WLCSP DSBGA CSP", "smd", body, -cy - 0.6, cy + 0.6)


def samzo(name, descr, body_len, body_w, s_at_pad1):
    """SAMZO PR5L 4P straight-pin pogo halves: drawings GA0480 / GA0481 recommended PCB layout.

    4 x drill 0.85 / pad 1.30, 2.54 mm pitch, 7.62 mm span, +/-0.05, centred on the housing.
    Housing outline is from the drawing's overall length; its width is approximate.

    Numbering (decided 2026-09-14): a join only attracts S to N, so pad 1 is the spring
    half's S end and the flat half's N end. Facing pads then mate k <-> k and a seam
    passes LA/LB/S1/S2 straight through like a USB-C cable. With pad 1 at S on both,
    pads would mate k <-> 5-k and the one-pair seam would put VBUS on GND.
    """
    body = ""
    for i in range(4):
        x = -3.81 + i * 2.54
        shape = "rect" if i == 0 else "circle"
        body += (f'\t(pad "{i + 1}" thru_hole {shape} (at {n(x)} 0) (size 1.3 1.3) (drill 0.85)'
                 f' (layers "*.Cu" "*.Mask"))\n')
    lx, wy = body_len / 2, body_w / 2
    body += rect("F.Fab", -lx, -wy, lx, wy, 0.1)
    body += rect("F.CrtYd", -lx - 0.25, -wy - 0.25, lx + 0.25, wy + 0.25, 0.05)
    body += rect("F.SilkS", -lx - 0.12, -wy - 0.12, lx + 0.12, wy + 0.12, 0.12)
    s_x = -lx + 1.2 if s_at_pad1 else lx - 1.2
    body += (f'\t(fp_text user "S" (at {n(s_x)} 0 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))\n'
             f'\t(fp_text user "N" (at {n(-s_x)} 0 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))\n')
    return footprint(name, descr, "pogo magnetic connector SAMZO", "through_hole", body, -wy - 1.2, wy + 1.2)


def pec11r_switch():
    """Bourns PEC11R-4xxxF-Sxxxx (vertical, push switch): datasheet p. 2 recommended layout.

    Origin on the shaft axis, component side. A-C-B row 7.5 mm below the axis at
    2.5 mm pitch; switch pins 1-2 7.0 mm above the axis, 5.0 mm apart; all
    1.0 +0.1 mm holes. Mounting lugs: 1.8 x 2.6 (+0.2) mm slots at +/-6.6 mm on
    the axis line. Body 12.5 x 13.4 mm.
    Pad names follow Device:RotaryEncoder_Switch (A, B, C, S1, S2).
    """
    body = ""
    for name, x, y in (("A", -2.5, 7.5), ("C", 0.0, 7.5), ("B", 2.5, 7.5), ("S1", -2.5, -7.0), ("S2", 2.5, -7.0)):
        body += (f'\t(pad {q(name)} thru_hole circle (at {n(x)} {n(y)}) (size 1.8 1.8) (drill 1.1)'
                 f' (layers "*.Cu" "*.Mask"))\n')
    for x in (-6.6, 6.6):
        body += (f'\t(pad "MP" thru_hole oval (at {n(x)} 0) (size 2.8 3.6) (drill oval 2.0 2.8)'
                 f' (layers "*.Cu" "*.Mask"))\n')
    body += rect("F.Fab", -6.25, -6.7, 6.25, 6.7, 0.1)
    body += circle("F.Fab", 0, 0, 3.0, 0.1)
    for y in (-6.82, 6.82):  # top and bottom edges only, clear of the lug pads
        body += (f'\t(fp_line (start -6.37 {n(y)}) (end -3.6 {n(y)}) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))\n'
                 f'\t(fp_line (start 3.6 {n(y)}) (end 6.37 {n(y)}) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))\n')
    body += rect("F.CrtYd", -8.2, -8.2, 8.2, 8.7, 0.05)
    return footprint("RotaryEncoder_Bourns_PEC11R-4xxxF-Sxxxx_Vertical",
                     "Bourns PEC11R-4xxxF-Sxxxx 12 mm incremental encoder with push switch, vertical (datasheet p. 2)",
                     "rotary encoder switch Bourns PEC11R", "through_hole", body, -9.2, 9.7)


def bc2aapc():
    """MPD BC2AAPC 2xAA series holder, PC pins: drawing BC2AAPC rev P (2024-06-21) PCB layout.

    Origin on pin 1 (+), which sits 8.61 mm from the body's outside edge; pin 2 (-)
    13.00 mm away (rev P; KiCad's stock footprint still has rev M's 13.59 mm).
    Pins 0.85 x 0.50 mm flat in 1.17 mm holes. Unplated 3.56 mm hole 26.16 mm along
    the body and 15.24 mm from the outside edge, i.e. centred on the 58.0 x 30.5 mm
    body, which puts the pins 2.84 mm from its end. Pad numbers follow Device:Battery.
    """
    body = ""
    for name, y, shape in (("1", 0.0, "rect"), ("2", 13.0, "circle")):
        body += (f'\t(pad {q(name)} thru_hole {shape} (at 0 {n(y)}) (size 2.17 2.17) (drill 1.17)'
                 f' (layers "*.Cu" "*.Mask"))\n')
    body += '\t(pad "" np_thru_hole circle (at 26.16 6.63) (size 3.56 3.56) (drill 3.56) (layers "*.Cu" "*.Mask"))\n'
    x1, y1, x2, y2 = -2.84, -8.61, 55.16, 21.89
    body += rect("F.Fab", x1, y1, x2, y2, 0.1)
    body += rect("F.SilkS", x1 - 0.12, y1 - 0.12, x2 + 0.12, y2 + 0.12, 0.12)
    body += rect("F.CrtYd", x1 - 0.5, y1 - 0.5, x2 + 0.5, y2 + 0.5, 0.05)
    for text, y in (("+", 0.0), ("-", 13.0)):
        body += (f'\t(fp_text user {q(text)} (at -4.4 {n(y)} 0) (layer "F.SilkS")'
                 f' (effects (font (size 1.5 1.5) (thickness 0.15))))\n')
    return footprint("BatteryHolder_MPD_BC2AAPC_2xAA_RevP",
                     "MPD BC2AAPC 2xAA series holder, PC pins, 15.0 mm above board (drawing rev P, 2024-06-21: pin spacing 13.00 mm)",
                     "battery holder AA 2xAA MPD BC2AAPC", "through_hole", body, y1 - 1.5, y2 + 1.5)


def vqfn_hr21_ryq():
    """TI RYQ0021A VQFN-HR 21-pin 5 x 3 mm (TPS552892 SLVSH28A p. 33, land pattern example 4226658/A).

    Top view, long axis along X. Pins 1-4 down the left side, 5-13 along the bottom
    (left to right), 14-17 up the right side, 18-21 along the top (right to left).
    Pins 7-11 are 3.4 mm strips across the package (VIN, SW1, PGND, SW2, VOUT).
    Row X positions: +/-2.04, 1.54, 1.04, 0.54 and 0 (the two steps beside the centre
    are 0.54 mm, the others 0.5 mm). Pads 0.25 mm wide; the centre strip's lead is
    0.28-0.38 mm, drawn 0.3 mm. No thermal pad: heat leaves through the strips.
    """
    def pad(name, x, y, sx, sy):
        return (f'\t(pad {q(str(name))} smd roundrect (at {n(x)} {n(y)}) (size {n(sx)} {n(sy)})'
                f' (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.2))\n')
    body = ""
    for i in range(4):
        y = -0.75 + 0.5 * i
        body += pad(1 + i, -2.4, y, 0.6, 0.25)
        body += pad(17 - i, 2.4, y, 0.6, 0.25)
    xs = [-2.04, -1.54, -1.04, -0.54, 0.0, 0.54, 1.04, 1.54, 2.04]
    for i, x in enumerate(xs):
        num = 5 + i
        if 7 <= num <= 11:
            body += pad(num, x, 0, 0.3 if num == 9 else 0.25, 3.4)
        elif num in (5, 13):
            body += pad(num, x, 1.375, 0.25, 0.65)
        else:
            body += pad(num, x, 1.4, 0.25, 0.6)
    for num, x, y, sy in ((21, -2.04, -1.375, 0.65), (20, -1.54, -1.4, 0.6), (19, 1.54, -1.4, 0.6), (18, 2.04, -1.375, 0.65)):
        body += pad(num, x, y, 0.25, sy)
    body += rect("F.Fab", -2.5, -1.5, 2.5, 1.5, 0.1)
    body += rect("F.CrtYd", -2.95, -1.95, 2.95, 1.95, 0.05)
    body += circle("F.SilkS", -3.15, -0.75, 0.08, 0.1, fill=True)
    return footprint("TI_VQFN-HR-21_5x3mm_RYQ0021A",
                     "TI RYQ0021A VQFN-HR 21-pin 5 x 3 mm, flip-chip leads, no thermal pad (TPS552892 SLVSH28A p. 33)",
                     "VQFN-HR RYQ TI TPS552892", "smd", body, -2.7, 2.7)


def vqfn_hr15_rnm():
    """TI RNM0015A VQFN-HR 15-pin 2.5 x 3 mm (TPS63070 SLVSC58, land pattern example 4222000/B).

    Top view, origin on the package centre (PKG and SYMM lines), 3 mm axis along Y. Pins 1-4 down the left side
    (x -1.15, y -0.75 .. 0.75), 5-8 along the bottom from the left (x -0.725, -0.225, 0.275, 0.775, y 1.4), 9-11 up
    the right side as strips (y 0.5, 0, -0.5; 9 and 11 are 1.35 mm long centred on x 0.775, 10 is 1.7 mm long
    centred on x 0.6), 12-15 along the top from the right. 7 / 8 (VOUT) and 12 / 13 (VIN) are one U-shaped lead
    each: two 0.25 x 0.6 mm legs joined on the inner side by a 0.25 mm bar, drawn as two pads plus a bar pad.
    """
    def pad(name, x, y, sx, sy):
        return (f'\t(pad {q(str(name))} smd roundrect (at {n(x)} {n(y)}) (size {n(sx)} {n(sy)})'
                f' (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.2))\n')
    body = ""
    for i in range(4):
        body += pad(1 + i, -1.15, -0.75 + 0.5 * i, 0.6, 0.25)
    for num, x in ((5, -0.725), (6, -0.225), (7, 0.275), (8, 0.775)):
        body += pad(num, x, 1.4, 0.25, 0.6)
    for num, x in ((15, -0.725), (14, -0.225), (13, 0.275), (12, 0.775)):
        body += pad(num, x, -1.4, 0.25, 0.6)
    body += pad(8, 0.525, 1.225, 0.75, 0.25) + pad(12, 0.525, -1.225, 0.75, 0.25)
    body += pad(9, 0.775, 0.5, 1.35, 0.25) + pad(10, 0.6, 0, 1.7, 0.25) + pad(11, 0.775, -0.5, 1.35, 0.25)
    body += rect("F.Fab", -1.25, -1.5, 1.25, 1.5, 0.1)
    body += rect("F.CrtYd", -1.7, -1.95, 1.7, 1.95, 0.05)
    body += circle("F.SilkS", -1.75, -0.75, 0.08, 0.1, fill=True)
    return footprint("TI_VQFN-HR-15_2.5x3mm_RNM0015A",
                     "TI RNM0015A VQFN-HR 15-pin 2.5 x 3 mm, flip-chip leads, no thermal pad (TPS63070 land pattern 4222000/B)",
                     "VQFN-HR RNM TI TPS63070 TPS630701", "smd", body, -2.6, 2.6)


def coilcraft_2pad(name, descr, body_x, body_y, pad_x, pad_y, pitch):
    """Coilcraft XGL / XFL moulded inductor: two strip lands, recommended land pattern from the datasheet."""
    body = ""
    for num, x in (("1", -pitch / 2), ("2", pitch / 2)):
        body += f'\t(pad {q(num)} smd rect (at {n(x)} 0) (size {n(pad_x)} {n(pad_y)}) (layers "F.Cu" "F.Paste" "F.Mask"))\n'
    hx, hy = body_x / 2, body_y / 2
    body += rect("F.Fab", -hx, -hy, hx, hy, 0.1)
    for y in (-hy - 0.15, hy + 0.15):
        body += f'\t(fp_line (start {n(-hx)} {n(y)}) (end {n(hx)} {n(y)}) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))\n'
    body += rect("F.CrtYd", -hx - 0.3, -hy - 0.3, hx + 0.3, hy + 0.3, 0.05)
    return footprint(name, descr, "inductor Coilcraft " + name.split("_")[-1], "smd", body, -hy - 1.0, hy + 1.0)


def picostar_yjc3():
    """TI YJC0003A PicoStar / FemtoFET F4, 1.0 x 0.6 mm, 3 lands (CSD25483F4 SLPS449F section 7.2).

    Pins 1 and 2 (0.25 x 0.15 mm) at x = -0.325, y = -/+0.175; pin 3 (0.25 x 0.5 mm) at
    x = +0.325. The datasheet's pattern is solder mask defined (copper larger than the
    opening); here the copper is the land and the mask is opened 0.05 mm around it.
    Reflow only. CSD25483F4: 1 gate, 2 source, 3 drain.
    """
    body = ""
    for name, x, y, sy in (("1", -0.325, -0.175, 0.15), ("2", -0.325, 0.175, 0.15), ("3", 0.325, 0.0, 0.5)):
        body += (f'\t(pad {q(name)} smd roundrect (at {n(x)} {n(y)}) (size 0.25 {n(sy)}) (layers "F.Cu" "F.Paste" "F.Mask")'
                 f' (roundrect_rratio 0.2) (solder_mask_margin 0.05))\n')
    body += rect("F.Fab", -0.5, -0.3, 0.5, 0.3, 0.05)
    body += rect("F.CrtYd", -0.75, -0.55, 0.75, 0.55, 0.05)
    body += circle("F.SilkS", -0.9, -0.45, 0.06, 0.1, fill=True)
    return footprint("TI_PicoStar-3_1.0x0.6mm_YJC0003A",
                     "TI YJC0003A PicoStar (FemtoFET F4) 1.0 x 0.6 mm, 3 lands, 0.35 mm pitch (CSD25483F4 SLPS449F p. 8)",
                     "PicoStar FemtoFET YJC TI", "smd", body, -1.3, 1.3)


def bc4aapc():
    """MPD BC4AAPC 4xAA series holder, PC pins: drawing BC4AAPC rev F (2020-02-14) PCB layout.

    Four 1.17 mm holes, origin on pad 1: pad 1 is 3.00 mm from one outside edge, pad 2
    55.00 mm away (3.30 mm from the other edge), pads 3 and 4 are 26.10 mm across,
    8.10 mm and 24.70 mm from that second edge. Body 61.3 mm (this axis) x 57.2 mm.
    NOT IN THE DRAWING, to check on a real holder before the battery board is laid out:
    which pins are + and - (taken here as pad 1 = +, pad 2 = -, read off the cell
    symbols and springs in the top view; pads 3 and 4 are left unconnected), and where
    the body sits along X (drawn with pads 3 and 4 on the centre line, 28.6 mm in).
    """
    body = ""
    for name, x, y, shape in (("1", 0, 0, "rect"), ("2", 0, 55.0, "circle"), ("3", 26.1, 50.2, "circle"), ("4", 26.1, 33.6, "circle")):
        body += (f'\t(pad {q(name)} thru_hole {shape} (at {n(x)} {n(y)}) (size 2.17 2.17) (drill 1.17)'
                 f' (layers "*.Cu" "*.Mask"))\n')
    x1, y1, x2, y2 = -2.5, -3.0, 54.7, 58.3
    body += rect("F.Fab", x1, y1, x2, y2, 0.1)
    body += rect("F.SilkS", x1 - 0.12, y1 - 0.12, x2 + 0.12, y2 + 0.12, 0.12)
    body += rect("F.CrtYd", x1 - 1.5, y1 - 0.5, x2 + 1.5, y2 + 0.5, 0.05)
    for text, y in (("+?", 0.0), ("-?", 55.0)):
        body += (f'\t(fp_text user {q(text)} (at 3 {n(y)} 0) (layer "F.SilkS")'
                 f' (effects (font (size 1.5 1.5) (thickness 0.15))))\n')
    return footprint("BatteryHolder_MPD_BC4AAPC_4xAA",
                     "MPD BC4AAPC 4xAA series holder, PC pins (drawing rev F). Polarity and body position along X are not in the drawing: check on the part",
                     "battery holder AA 4xAA MPD BC4AAPC", "through_hole", body, y1 - 1.5, y2 + 1.5)


def sod123fl_littelfuse():
    """Littelfuse SMF4L SOD-123FL: datasheet (rev JC 04/22/25) p. 5 mounting pad layout.

    Pads 0.98 x 1.25 mm, 2.24 mm inner gap, so centres at +/-1.61 mm (stock
    D_SOD-123F uses 1.1 x 1.1 at +/-1.4, less toe for hand soldering). Body
    A 2.70-3.10 x D 1.70-2.00 mm, lead span B up to 3.90 mm. The SMF4L9.0CA is
    bidirectional, so the pad order carries no polarity.
    """
    body = ""
    for name, x in (("1", -1.61), ("2", 1.61)):
        body += (f'\t(pad {q(name)} smd rect (at {n(x)} 0) (size 0.98 1.25)'
                 f' (layers "F.Cu" "F.Paste" "F.Mask"))\n')
    body += rect("F.Fab", -1.55, -1.0, 1.55, 1.0, 0.1)
    for y in (-1.12, 1.12):  # long edges only, clear of the pads
        body += f'\t(fp_line (start -0.9 {n(y)}) (end 0.9 {n(y)}) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))\n'
    body += rect("F.CrtYd", -2.35, -1.25, 2.35, 1.25, 0.05)
    return footprint("D_SOD-123FL_Littelfuse",
                     "Littelfuse SOD-123FL (SMF4L series), pads 0.98 x 1.25 mm at 3.22 mm pitch (datasheet p. 5)",
                     "SOD-123FL TVS Littelfuse SMF4L", "smd", body, -2.0, 2.0)


def ptslr1206():
    """Eaton PTSLR12066V075-V500: datasheet 11048 (effective June 2021) p. 3 recommended pad layout.

    Pads G 1.0 x H 1.9 mm with F 2.0 mm between them, so centres at +/-1.5 mm. Kept
    at Eaton's size rather than KiCad's 1206 hand-solder pads (1.425 x 1.75 mm,
    1.55 mm gap): pad copper is a heat path, and a PTC's hold and trip depend on it.
    Body A 3.0-3.5 x B 1.5-1.8 mm (V175: C 0.6-1.2 mm thick).
    """
    body = ""
    for name, x in (("1", -1.5), ("2", 1.5)):
        body += (f'\t(pad {q(name)} smd rect (at {n(x)} 0) (size 1.0 1.9)'
                 f' (layers "F.Cu" "F.Paste" "F.Mask"))\n')
    body += rect("F.Fab", -1.75, -0.9, 1.75, 0.9, 0.1)
    for y in (-1.07, 1.07):  # long edges only, between the pads
        body += f'\t(fp_line (start -0.85 {n(y)}) (end 0.85 {n(y)}) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))\n'
    body += rect("F.CrtYd", -2.25, -1.2, 2.25, 1.2, 0.05)
    return footprint("Fuse_1206_Eaton_PTSLR1206",
                     "Eaton PTSLR1206 PTC fuse (V075-V500), pads 1.0 x 1.9 mm, 2.0 mm gap (datasheet 11048 p. 3)",
                     "PTC polyfuse resettable 1206 Eaton PTSLR1206", "smd", body, -2.0, 2.0)


def tvs2200_drv():
    """TI TVS2200 DRV0006A (WSON-6 2 x 2 mm): datasheet land pattern example, drawing 4222173/C (11/2025).

    Pads 0.45 x 0.30 mm at 0.65 mm pitch, centres at x = +/-0.975 mm (1.95 mm
    apart); exposed pad 7 is 1.0 x 1.6 mm. Pins 1-3 GND down the left (1 at top),
    4-6 IN up the right (6 at top), pad 7 GND. The stock
    WSON-6-1EP_2x2mm_P0.65mm_EP1x1.6mm comes from a TPS61040 drawing and puts the
    pads at +/-0.8875 mm with 0.375 x 0.40 mm size.
    """
    body = ""
    for name, x, y in (("1", -0.975, -0.65), ("2", -0.975, 0.0), ("3", -0.975, 0.65),
                       ("4", 0.975, 0.65), ("5", 0.975, 0.0), ("6", 0.975, -0.65)):
        body += (f'\t(pad {q(name)} smd roundrect (at {n(x)} {n(y)}) (size 0.45 0.3) (roundrect_rratio 0.166)'
                 f' (layers "F.Cu" "F.Paste" "F.Mask"))\n')
    body += '\t(pad "7" smd rect (at 0 0) (size 1.0 1.6) (layers "F.Cu" "F.Paste" "F.Mask"))\n'
    body += rect("F.Fab", -1.0, -1.0, 1.0, 1.0, 0.1)
    body += circle("F.SilkS", -1.45, -0.95, 0.08, 0.1, fill=True)
    body += rect("F.CrtYd", -1.45, -1.25, 1.45, 1.25, 0.05)
    return footprint("TI_WSON-6-1EP_2x2mm_P0.65mm_DRV0006A_TVS2200",
                     "TI DRV0006A WSON-6 2 x 2 mm, TVS2200 land pattern (drawing 4222173/C)",
                     "WSON DRV TVS2200 TI", "smd", body, -2.0, 2.0)


def sod123fl_smf():
    """Littelfuse SMF series (SMF6.0A etc.) SOD-123FL case 498 issue D: recommended soldering footprint.

    Pads 1.22 x 1.25 mm, 4.20 mm overall, so centres at +/-1.49 mm and a 1.76 mm gap.
    Pin 1 is the cathode (polarity band). Different from the SMF4L layout
    (D_SOD-123FL_Littelfuse: 0.98 mm pads, 2.24 mm gap). Body E 2.50-2.90 x D 1.50-1.80 mm.
    """
    body = ""
    for name, x in (("1", -1.49), ("2", 1.49)):
        body += (f'\t(pad {q(name)} smd rect (at {n(x)} 0) (size 1.22 1.25)'
                 f' (layers "F.Cu" "F.Paste" "F.Mask"))\n')
    body += rect("F.Fab", -1.45, -0.9, 1.45, 0.9, 0.1)
    body += f'\t(fp_line (start -0.9 -0.9) (end -0.9 0.9) (stroke (width 0.1) (type solid)) (layer "F.Fab"))\n'
    for y in (-1.02, 1.02):
        body += f'\t(fp_line (start -0.75 {n(y)}) (end 0.75 {n(y)}) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))\n'
    body += f'\t(fp_line (start -2.3 -0.75) (end -2.3 0.75) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))\n'
    body += rect("F.CrtYd", -2.45, -1.2, 2.35, 1.2, 0.05)
    return footprint("D_SOD-123FL_Littelfuse_SMF",
                     "Littelfuse SMF series SOD-123FL (case 498D), pads 1.22 x 1.25 mm, 4.20 mm overall; pin 1 cathode",
                     "SOD-123FL TVS Littelfuse SMF", "smd", body, -2.0, 2.0)


def uson10_dqa():
    """TI DQA0010A and DQA0010B (USON-10 2.5 x 1.0 mm): TPDxE05U06 SLVSBO7O (rev O) pp. 28-33.

    Both land pattern examples (4220328/A p. 29, 4230307/A p. 32): pads 0.565 x 0.2 mm,
    R0.05, 0.5 mm pitch, column centres 0.835 mm apart; pads 3 and 8 are 0.4 mm tall.
    Pins 1-5 down the left (1 at top), 6-10 up the right. DQA0010B adds a 0.8 x 0.3 mm
    copper bar joining 3 and 8 under its tied centre lead; it is copper and mask only
    (the B stencil, p. 33, leaves the centre open) and both pins are GND, so one
    footprint takes either package. Paste on 3 and 8 is 0.525 x 0.36 mm, inside the
    A stencil's 0.36 mm (90 %, p. 30) and the B stencil's 0.4 mm apertures. Mask
    0.05 mm around, within TI's NSMD 0.07 mm max. The stock
    USON-10_2.5x1.0mm_P0.5mm (from tpd4e02b04) has 0.55 x 0.3 mm pads at 0.77 mm centres.
    """
    body = ""
    for i in range(10):
        x, y = (-0.4175, -1.0 + 0.5 * i) if i < 5 else (0.4175, 1.0 - 0.5 * (i - 5))
        tall = i in (2, 7)
        h = 0.4 if tall else 0.2
        paste = " (solder_paste_margin -0.02)" if tall else ""
        body += (f'\t(pad "{i + 1}" smd roundrect (at {n(x)} {n(y)}) (size 0.565 {n(h)}) (roundrect_rratio {n(0.05 / h)})'
                 f' (layers "F.Cu" "F.Paste" "F.Mask") (solder_mask_margin 0.05){paste})\n')
    body += '\t(pad "3" smd rect (at 0 0) (size 0.8 0.3) (layers "F.Cu" "F.Mask") (solder_mask_margin 0.05))\n'
    body += rect("F.Fab", -0.5, -1.25, 0.5, 1.25, 0.1)
    for y in (-1.37, 1.37):
        body += f'\t(fp_line (start -0.5 {n(y)}) (end 0.5 {n(y)}) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))\n'
    body += circle("F.SilkS", -0.95, -1.3, 0.08, 0.1, fill=True)
    body += rect("F.CrtYd", -0.95, -1.5, 0.95, 1.5, 0.05)
    return footprint("TI_USON-10_2.5x1.0mm_P0.5mm_DQA0010",
                     "TI DQA0010A/DQA0010B USON-10 2.5 x 1.0 mm, TPD4E05U06 land pattern (SLVSBO7O pp. 29, 32)",
                     "USON DQA TPD4E05U06 TI", "smd", body, -2.2, 2.2)


def sot23_6_dbv():
    """TI DBV0006A (SOT-23-6): package drawing 4214840/G (08/2024) example board layout.

    Pads 1.1 x 0.6 mm, R0.05, 0.95 mm pitch, column centres 2.6 mm apart. Pins 1-3
    down the left (1 at top), 4-6 up the right. Mask 0.05 mm around (NSMD, TI 0.07 mm
    max). Body 2.75-3.05 x 1.45-1.75 mm, lead span 2.6-3.0 mm. The stock
    Package_TO_SOT_SMD:SOT-23-6 has 1.325 x 0.6 mm pads at 2.275 mm centres.
    """
    body = ""
    for i in range(6):
        x, y = (-1.3, -0.95 + 0.95 * i) if i < 3 else (1.3, 0.95 - 0.95 * (i - 3))
        body += (f'\t(pad "{i + 1}" smd roundrect (at {n(x)} {n(y)}) (size 1.1 0.6) (roundrect_rratio 0.0833)'
                 f' (layers "F.Cu" "F.Paste" "F.Mask") (solder_mask_margin 0.05))\n')
    body += rect("F.Fab", -0.8, -1.45, 0.8, 1.45, 0.1)
    for y in (-1.57, 1.57):
        body += f'\t(fp_line (start -0.4 {n(y)}) (end 0.4 {n(y)}) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))\n'
    body += circle("F.SilkS", -2.1, -1.4, 0.08, 0.1, fill=True)
    body += rect("F.CrtYd", -2.35, -1.75, 2.1, 1.75, 0.05)
    return footprint("TI_SOT-23-6_DBV0006A",
                     "TI DBV0006A SOT-23-6, example board layout (drawing 4214840/G): 1.1 x 0.6 mm pads, 2.6 mm column centres",
                     "SOT-23-6 DBV TI", "smd", body, -2.5, 2.5)


def sot23_5_dbv():
    """TI DBV0005A (SOT-23-5): package drawing 4214839/K (08/2024) example board layout (TLV757P SBVS320).

    Pads 1.1 x 0.6 mm, R0.05, 0.95 mm pitch, column centres 2.6 mm apart. Pins 1-3 down
    the left (1 at top), 4 bottom right, 5 top right, no pad at the right centre. The stock
    Package_TO_SOT_SMD:SOT-23-5 has 1.325 x 0.6 mm pads at 2.275 mm centres.
    """
    body = ""
    for name, x, y in (("1", -1.3, -0.95), ("2", -1.3, 0.0), ("3", -1.3, 0.95), ("4", 1.3, 0.95), ("5", 1.3, -0.95)):
        body += (f'\t(pad {q(name)} smd roundrect (at {n(x)} {n(y)}) (size 1.1 0.6) (roundrect_rratio 0.0833)'
                 f' (layers "F.Cu" "F.Paste" "F.Mask") (solder_mask_margin 0.05))\n')
    body += rect("F.Fab", -0.8, -1.45, 0.8, 1.45, 0.1)
    for y in (-1.57, 1.57):
        body += f'\t(fp_line (start -0.4 {n(y)}) (end 0.4 {n(y)}) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))\n'
    body += circle("F.SilkS", -2.1, -1.4, 0.08, 0.1, fill=True)
    body += rect("F.CrtYd", -2.1, -1.75, 2.1, 1.75, 0.05)
    return footprint("TI_SOT-23-5_DBV0005A",
                     "TI DBV0005A SOT-23-5, example board layout (drawing 4214839/K): 1.1 x 0.6 mm pads, 2.6 mm column centres",
                     "SOT-23-5 DBV TI", "smd", body, -2.5, 2.5)


def sot563_drl():
    """TI DRL0006A (SOT-5X3, 6 pins): TPS61023 SLVSF14B example board layout.

    Pads 0.67 x 0.3 mm, R0.05, 0.5 mm pitch, column centres 1.48 mm apart. Pins 1-3 down
    the left (1 at top), 4-6 up the right. The stock Package_TO_SOT_SMD:SOT-563 has
    0.675 x 0.35 mm pads at 1.425 mm centres. (SOT-583-8 matches TI DRL0008A: 0.67 x 0.3 at 1.48.)
    """
    body = ""
    for i in range(6):
        x, y = (-0.74, -0.5 + 0.5 * i) if i < 3 else (0.74, 0.5 - 0.5 * (i - 3))
        body += (f'\t(pad "{i + 1}" smd roundrect (at {n(x)} {n(y)}) (size 0.67 0.3) (roundrect_rratio 0.1667)'
                 f' (layers "F.Cu" "F.Paste" "F.Mask"))\n')
    body += rect("F.Fab", -0.6, -0.8, 0.6, 0.8, 0.1)
    body += circle("F.SilkS", -1.3, -0.75, 0.08, 0.1, fill=True)
    body += rect("F.CrtYd", -1.35, -1.05, 1.35, 1.05, 0.05)
    return footprint("TI_SOT-563_DRL0006A",
                     "TI DRL0006A SOT-5X3 6-pin, TPS61023 SLVSF14B example board layout: 0.67 x 0.3 mm pads, 1.48 mm column centres",
                     "SOT-563 DRL TI", "smd", body, -1.8, 1.8)


def we_lqs_2512():
    """Wuerth WE-LQS 2512 (74404024022): datasheet rev 003.001 recommended land pattern.

    Two 1.1 x 2.0 mm pads with a 0.8 mm gap (centres +/-0.95 mm); body 2.5 x 2.0 x 1.2 mm.
    The stock Inductor_SMD:L_1008_2520Metric has 1.25 x 2.2 mm pads at +/-1.075 mm.
    """
    body = ""
    for name, x in (("1", -0.95), ("2", 0.95)):
        body += f'\t(pad {q(name)} smd rect (at {n(x)} 0) (size 1.1 2.0) (layers "F.Cu" "F.Paste" "F.Mask"))\n'
    body += rect("F.Fab", -1.25, -1.0, 1.25, 1.0, 0.1)
    for y in (-1.15, 1.15):
        body += f'\t(fp_line (start -0.3 {n(y)}) (end 0.3 {n(y)}) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))\n'
    body += rect("F.CrtYd", -1.75, -1.25, 1.75, 1.25, 0.05)
    return footprint("L_Wuerth_WE-LQS-2512",
                     "Wuerth WE-LQS 2512 semi-shielded power inductor (74404024022), datasheet recommended land pattern",
                     "inductor Wuerth WE-LQS 2512", "smd", body, -2.0, 2.0)


def lqfp48_pt():
    """TI PT0048A (LQFP-48 7 x 7 mm, 0.5 mm pitch): MSPM0G350x SLASEX6C, drawing 4215159/B example board layout.

    48 pads 1.6 x 0.3 mm, R0.05, 0.5 mm pitch, opposite pad centres 8.2 mm apart (+/-4.1 mm).
    Pins 1-12 down the left (1 at top), 13-24 left to right along the bottom, 25-36 up the
    right, 37-48 right to left along the top. Mask 0.05 mm around (NSMD, TI 0.05 mm max).
    Body 6.8-7.2 mm, lead tips 8.8-9.2 mm. The stock Package_QFP:LQFP-48_7x7mm_P0.5mm has
    1.475 x 0.3 mm pads at +/-4.1625 mm (same toe, 0.125 mm shorter heel).
    """
    body = ""
    for i in range(48):
        side, k = divmod(i, 12)
        off = -2.75 + 0.5 * k
        x, y, w, h = ((-4.1, off, 1.6, 0.3), (off, 4.1, 0.3, 1.6), (4.1, -off, 1.6, 0.3), (-off, -4.1, 0.3, 1.6))[side]
        body += (f'\t(pad "{i + 1}" smd roundrect (at {n(x)} {n(y)}) (size {n(w)} {n(h)}) (roundrect_rratio 0.1667)'
                 f' (layers "F.Cu" "F.Paste" "F.Mask") (solder_mask_margin 0.05))\n')
    body += (f'\t(fp_poly (pts (xy -2.5 -3.5) (xy 3.5 -3.5) (xy 3.5 3.5) (xy -3.5 3.5) (xy -3.5 -2.5))'
             f' (stroke (width 0.1) (type solid)) (fill no) (layer "F.Fab"))\n')
    # silk corner marks on the body outline, stopping 0.2 mm short of the outer pads
    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        body += (f'\t(fp_line (start {n(sx * 3.61)} {n(sy * 3.1)}) (end {n(sx * 3.61)} {n(sy * 3.61)})'
                 f' (stroke (width 0.12) (type solid)) (layer "F.SilkS"))\n'
                 f'\t(fp_line (start {n(sx * 3.61)} {n(sy * 3.61)}) (end {n(sx * 3.1)} {n(sy * 3.61)})'
                 f' (stroke (width 0.12) (type solid)) (layer "F.SilkS"))\n')
    body += circle("F.SilkS", -4.6, -3.35, 0.08, 0.1, fill=True)
    body += rect("F.CrtYd", -5.15, -5.15, 5.15, 5.15, 0.05)
    return footprint("TI_LQFP-48_7x7mm_P0.5mm_PT0048A",
                     "TI PT0048A LQFP-48 7 x 7 mm, 0.5 mm pitch, example board layout (drawing 4215159/B): 1.6 x 0.3 mm pads, 8.2 mm row centres",
                     "LQFP-48 PT TI MSPM0", "smd", body, -6.0, 6.0)


def tssop24_pw():
    """TI PW0024A (TSSOP-24 4.4 x 7.8 mm, 0.65 mm pitch): TCA9548A SCPS207H, drawing 4220208/A example board layout.

    24 pads 1.5 x 0.45 mm, R0.05, 0.65 mm pitch, column centres 5.8 mm apart (+/-2.9 mm).
    Pins 1-12 down the left (1 at top), 13-24 up the right. Mask 0.05 mm around (NSMD,
    TI 0.05 mm max). Body 4.3-4.5 x 7.7-7.9 mm. The stock Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm
    has 1.475 x 0.4 mm pads at +/-2.8625 mm.
    """
    body = ""
    for i in range(24):
        x, y = (-2.9, -3.575 + 0.65 * i) if i < 12 else (2.9, 3.575 - 0.65 * (i - 12))
        body += (f'\t(pad "{i + 1}" smd roundrect (at {n(x)} {n(y)}) (size 1.5 0.45) (roundrect_rratio 0.1111)'
                 f' (layers "F.Cu" "F.Paste" "F.Mask") (solder_mask_margin 0.05))\n')
    body += (f'\t(fp_poly (pts (xy -1.2 -3.9) (xy 2.2 -3.9) (xy 2.2 3.9) (xy -2.2 3.9) (xy -2.2 -2.9))'
             f' (stroke (width 0.1) (type solid)) (fill no) (layer "F.Fab"))\n')
    for y in (-4.01, 4.01):
        body += f'\t(fp_line (start -2.0 {n(y)}) (end 2.0 {n(y)}) (stroke (width 0.12) (type solid)) (layer "F.SilkS"))\n'
    body += circle("F.SilkS", -3.4, -4.05, 0.08, 0.1, fill=True)
    body += rect("F.CrtYd", -3.9, -4.2, 3.9, 4.2, 0.05)
    return footprint("TI_TSSOP-24_4.4x7.8mm_P0.65mm_PW0024A",
                     "TI PW0024A TSSOP-24 4.4 x 7.8 mm, 0.65 mm pitch, example board layout (drawing 4220208/A): 1.5 x 0.45 mm pads, 5.8 mm column centres",
                     "TSSOP-24 PW TI TCA9548A", "smd", body, -5.0, 5.0)


def spring_pin_0929():
    """Mill-Max 0929 discrete spring pin, through-hole (catalogue p. 25: solder mount in .029 in min hole, tail .025 in,
    largest body step .072 in). Used for the Pico 2 W underside pads; TP2 and TP3 are 2.0 mm apart, so the pad is 1.3 mm."""
    body = ('\t(pad "1" thru_hole circle (at 0 0) (size 1.3 1.3) (drill 0.8) (layers "*.Cu" "*.Mask"))\n')
    body += circle("F.Fab", 0, 0, 0.915, 0.05)
    body += circle("F.CrtYd", 0, 0, 0.95, 0.05)
    return footprint("SpringPin_MillMax_0929_THT", "Mill-Max 0929-x-15-20-7x-14-11-0 spring pin, through-hole, 0.8 mm hole",
                     "pogo spring pin Mill-Max 0929", "through_hole", body, -1.8, 1.8)


def pogo_target_2x08():
    """2x8 target pads on 2.54 mm for Mill-Max 1578 discs (1.98 mm), reflowed. Numbered like KiCad's PinSocket_2x08
    (pin 2 at -2.54 in x), so that placed on the BOTTOM of the upper board pad n sits over pin n of a PinHeader_2x08
    pattern on the top of the board below (the spring-pin strip on the cap board)."""
    body = ""
    for i in range(16):
        x, y = (-2.54 if i % 2 else 0.0), 2.54 * (i // 2)
        body += (f'\t(pad {q(str(i + 1))} smd circle (at {n(x)} {n(y)}) (size 2.1 2.1) (layers "F.Cu" "F.Paste" "F.Mask"))\n')
    body += rect("F.Fab", -3.81, -1.27, 1.27, 19.05, 0.05)
    body += rect("F.CrtYd", -4.1, -1.55, 1.55, 19.35, 0.05)
    body += circle("F.SilkS", 1.9, 0, 0.1, 0.15, fill=True)
    return footprint("PogoTarget_2x08_P2.54mm", "2x8 target pads, 2.54 mm, Mill-Max 1578-0-57-15-00-00-03-0 discs; PinSocket numbering",
                     "pogo target pads chain", "smd", body, -2.6, 20.4)


FOOTPRINTS = {
    "SpringPin_MillMax_0929_THT": spring_pin_0929(),
    "PogoTarget_2x08_P2.54mm": pogo_target_2x08(),
    "TI_LQFP-48_7x7mm_P0.5mm_PT0048A": lqfp48_pt(),
    "TI_TSSOP-24_4.4x7.8mm_P0.65mm_PW0024A": tssop24_pw(),
    "TI_SOT-23-5_DBV0005A": sot23_5_dbv(),
    "TI_SOT-563_DRL0006A": sot563_drl(),
    "L_Wuerth_WE-LQS-2512": we_lqs_2512(),
    "TI_SOT-23-6_DBV0006A": sot23_6_dbv(),
    "TI_USON-10_2.5x1.0mm_P0.5mm_DQA0010": uson10_dqa(),
    "TI_WSON-6-1EP_2x2mm_P0.65mm_DRV0006A_TVS2200": tvs2200_drv(),
    "D_SOD-123FL_Littelfuse_SMF": sod123fl_smf(),
    "Fuse_1206_Eaton_PTSLR1206": ptslr1206(),
    "D_SOD-123FL_Littelfuse": sod123fl_littelfuse(),
    "BatteryHolder_MPD_BC2AAPC_2xAA_RevP": bc2aapc(),
    "BatteryHolder_MPD_BC4AAPC_4xAA": bc4aapc(),
    "TI_VQFN-HR-21_5x3mm_RYQ0021A": vqfn_hr21_ryq(),
    "TI_PicoStar-3_1.0x0.6mm_YJC0003A": picostar_yjc3(),
    "TI_VQFN-HR-15_2.5x3mm_RNM0015A": vqfn_hr15_rnm(),
    "L_Coilcraft_XGL3530": coilcraft_2pad(
        "L_Coilcraft_XGL3530", "Coilcraft XGL3530, 3.2 x 3.5 x 3.0 mm: lands 0.81 x 3.2 mm, 1.8 mm centre to centre (Document 1607-1)",
        body_x=3.2, body_y=3.5, pad_x=0.81, pad_y=3.2, pitch=1.8),
    "L_Coilcraft_XFL4020": coilcraft_2pad(
        "L_Coilcraft_XFL4020", "Coilcraft XFL4020, 4.0 x 4.0 x 2.1 mm: lands 0.98 x 3.4 mm, 2.37 mm centre to centre (Document 745-3)",
        body_x=4.0, body_y=4.0, pad_x=0.98, pad_y=3.4, pitch=2.37),
    "RotaryEncoder_Bourns_PEC11R-4xxxF-Sxxxx_Vertical": pec11r_switch(),
    "Kinetic_WLCSP-20_1.935x2.16mm_Layout4x5_P0.4mm": csp(
        "Kinetic_WLCSP-20_1.935x2.16mm_Layout4x5_P0.4mm",
        "Kinetic KTS1693 WLCSP-20, 4 x 5 at 0.4 mm, NSMD copper 0.22 mm, mask 0.32 mm (datasheet rev 04d p. 15)",
        cols=4, rows=5, pitch=0.4, pad_d=0.22, mask_d=0.32, body_x=1.935, body_y=2.16),
    "Texas_DSBGA-6_0.706x1.106mm_Layout2x3_P0.4mm_YBH": csp(
        "Texas_DSBGA-6_0.706x1.106mm_Layout2x3_P0.4mm_YBH",
        "TI YBH0006 DSBGA-6, 2 x 3 at 0.4 mm, NSMD copper 0.2 mm (TPS22950 SLVSFJ2B, 4226594/A)",
        cols=2, rows=3, pitch=0.4, pad_d=0.2, mask_d=0.3, body_x=0.706, body_y=1.106),
    "SAMZO_PR5L3715-4P-C-H_Spring": samzo(
        "SAMZO_PR5L3715-4P-C-H_Spring",
        "SAMZO magnetic pogo, spring half, 4P 2.54 mm straight pin, tails 1.50 mm (drawing GA0480-P001); pad 1 at the S end",
        body_len=21.2, body_w=4.8, s_at_pad1=True),
    "SAMZO_PR5L2820-4P-C-F_Flat": samzo(
        "SAMZO_PR5L2820-4P-C-F_Flat",
        "SAMZO magnetic pogo, flat half, 4P 2.54 mm straight pin, tails 2.00 mm (drawing GA0481-P001); pad 1 at the N end",
        body_len=21.2, body_w=4.8, s_at_pad1=False),
}


def write_footprints():
    d = LIB / f"{LIBNAME}.pretty"
    d.mkdir(parents=True, exist_ok=True)
    for name, text in FOOTPRINTS.items():
        (d / f"{name}.kicad_mod").write_text(text)


# --------------------------------------------------------------------------
# projects
# --------------------------------------------------------------------------

LAYERS = """\t(layers
\t\t(0 "F.Cu" signal) {inner}(2 "B.Cu" signal)
\t\t(9 "F.Adhes" user "F.Adhesive") (11 "B.Adhes" user "B.Adhesive")
\t\t(13 "F.Paste" user) (15 "B.Paste" user)
\t\t(5 "F.SilkS" user "F.Silkscreen") (7 "B.SilkS" user "B.Silkscreen")
\t\t(1 "F.Mask" user) (3 "B.Mask" user)
\t\t(17 "Dwgs.User" user "User.Drawings") (19 "Cmts.User" user "User.Comments")
\t\t(25 "Edge.Cuts" user) (27 "Margin" user)
\t\t(31 "F.CrtYd" user "F.Courtyard") (29 "B.CrtYd" user "B.Courtyard")
\t\t(35 "F.Fab" user) (33 "B.Fab" user)
\t)"""


def pcb_text(thickness, four_layer=False):
    core = thickness - 2 * 0.035 - 2 * 0.01
    if four_layer:
        inner_cu, prepreg = 0.035, 0.2
        core = round(core - 2 * inner_cu - 2 * prepreg, 3)
        dielectric = (
            f'\t\t\t(layer "F.Cu" (type "copper") (thickness 0.035))\n'
            f'\t\t\t(layer "dielectric 1" (type "prepreg") (thickness {n(prepreg)}) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))\n'
            f'\t\t\t(layer "In1.Cu" (type "copper") (thickness {n(inner_cu)}))\n'
            f'\t\t\t(layer "dielectric 2" (type "core") (thickness {n(core)}) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))\n'
            f'\t\t\t(layer "In2.Cu" (type "copper") (thickness {n(inner_cu)}))\n'
            f'\t\t\t(layer "dielectric 3" (type "prepreg") (thickness {n(prepreg)}) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))\n'
            f'\t\t\t(layer "B.Cu" (type "copper") (thickness 0.035))\n')
    else:
        dielectric = (
            f'\t\t\t(layer "F.Cu" (type "copper") (thickness 0.035))\n'
            f'\t\t\t(layer "dielectric 1" (type "core") (thickness {n(round(core, 3))}) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))\n'
            f'\t\t\t(layer "B.Cu" (type "copper") (thickness 0.035))\n')
    inner = '(4 "In1.Cu" signal) (6 "In2.Cu" signal) ' if four_layer else ""
    return f"""(kicad_pcb (version 20241229) (generator "pcbnew") (generator_version "10.0")
\t(general (thickness {n(thickness)}) (legacy_teardrops no))
\t(paper "A4")
{LAYERS.format(inner=inner)}
\t(setup
\t\t(stackup
\t\t\t(layer "F.SilkS" (type "Top Silk Screen"))
\t\t\t(layer "F.Paste" (type "Top Solder Paste"))
\t\t\t(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
{dielectric}\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))
\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen"))
\t\t\t(copper_finish "None")
\t\t\t(dielectric_constraints no)
\t\t)
\t\t(pad_to_mask_clearance 0)
\t)
\t(net 0 "")
)
"""


def sch_text(title):
    return f"""(kicad_sch (version 20250114) (generator "eeschema") (generator_version "10.0")
\t(uuid {q(uuid.uuid4())})
\t(paper "A4")
\t(title_block (title {q(title)}))
\t(lib_symbols)
\t(sheet_instances (path "/" (page "1")))
)
"""


def pro_json(name, ref_start, fine):
    rules = {
        "min_clearance": 0.127,
        "min_track_width": 0.127,
        "min_through_hole_diameter": 0.15 if fine else 0.2,
    }
    return {
        "board": {"design_settings": {"rules": rules}},
        "meta": {"filename": f"{name}.kicad_pro", "version": 3},
        "schematic": {"annotate_start_num": ref_start},
    }


# Vendored kiswitch libraries (tools/vendor_kiswitch.sh), key board projects only.
# Their 3D model paths assume the project sits one level below hardware/.
KISWITCH_LIBS = [
    ("Switch_Keyboard_Hotswap_Kailh", "Kailh MX hotswap (kiswitch, vendored)"),
    ("Mounting_Keyboard_Stabilizer", "Cherry MX stabiliser (kiswitch, vendored)"),
]


def fp_lib_line(name, uri, descr):
    return f'\t(lib (name {q(name)}) (type "KiCad") (uri {q(uri)}) (options "") (descr {q(descr)}))\n'


def lib_tables(depth, key_board):
    up = "/".join([".."] * depth)
    sym = (f'(sym_lib_table\n\t(version 7)\n\t(lib (name "{LIBNAME}") (type "KiCad")'
           f' (uri "${{KIPRJMOD}}/{up}/lib/{LIBNAME}.kicad_sym") (options "") (descr "Project custom symbols"))\n)\n')
    fp_libs = [fp_lib_line(LIBNAME, f"${{KIPRJMOD}}/{up}/lib/{LIBNAME}.pretty", "Project custom footprints")]
    if key_board:
        fp_libs += [fp_lib_line(name, f"${{KIPRJMOD}}/{up}/lib/kiswitch/{name}.pretty", descr)
                    for name, descr in KISWITCH_LIBS]
    fp = "(fp_lib_table\n\t(version 7)\n" + "".join(fp_libs) + ")\n"
    return sym, fp, fp_libs


def add_missing_libs(path, lines):
    """Append library entries missing from an existing table, keeping any the user added."""
    text = path.read_text()
    missing = [ln for ln in lines if f"(name {ln.split('(name ', 1)[1].split(')', 1)[0]})" not in text]
    if missing:
        head, tail = text.rstrip().rsplit(")", 1)
        path.write_text(head.rstrip("\n") + "\n" + "".join(missing) + ")" + tail + "\n")


def write_projects():
    for rel, ref_start, thickness in PROJECTS:
        d = HW / rel
        d.mkdir(parents=True, exist_ok=True)
        name = Path(rel).name
        depth = len(Path(rel).parts)
        files = {
            f"{name}.kicad_pro": json.dumps(pro_json(name, ref_start, name in FINE_PITCH), indent=2) + "\n",
            f"{name}.kicad_sch": sch_text(name),
            f"{name}.kicad_pcb": pcb_text(thickness, name in FOUR_LAYER),
        }
        sym, fp, fp_libs = lib_tables(depth, name in KEY_BOARDS)
        files["sym-lib-table"] = sym
        files["fp-lib-table"] = fp
        for fname, text in files.items():
            p = d / fname
            if not p.exists():
                p.write_text(text)
        add_missing_libs(d / "fp-lib-table", fp_libs)


if __name__ == "__main__":
    LIB.mkdir(parents=True, exist_ok=True)
    write_symbols()
    write_footprints()
    write_projects()
    import subprocess
    subprocess.run([str(ROOT / "tools" / "kicad_format.sh")], check=False)      # new project stubs: installed KiCad's file format
    print("generated", HW)
