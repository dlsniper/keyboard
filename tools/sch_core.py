#!/usr/bin/env python3
"""Capture the core board schematic (hardware/core/core.kicad_sch).

The one core design every module shares (spec §2a "Core", §4 "Power", §5 pad table,
§6 connectors). Blocks:

  MCU        MDBT50Q-1MV2 (U1MV2 second source, same pads: unverified), 32.768 kHz
             crystal, SWD (TC2030-NL + pads), reset/bootloader tactiles
  pack OR    J_BAT_A/B -> LM66200 (1 uF per input max, E14) -> VBAT; TPS3840PH18 on
             ~ON via BAT54C; slide switch selects ~ON between the supervisor and SUP_VDD
  VBUS OR    J_USB VBUS_LOCAL + J_LINK VBUS_LINK_IN -> LM66200 -> VBUS_IN
  logic rail TLV75733P from VBUS_IN on IN1, logic boost from VBAT on IN2 of a TPS2116
             (priority, PR1 from VBUS_IN) -> VSYS. Boost is a dual footprint:
             TPS61099DRV (576k/249k) or MAX17222 (RSEL 80.6k, 0 ohm into the boost net)
  LED rail   TPS61023 4.7 V boost from VBAT on IN2, VBUS_IN on IN1 of a TPS2116
             (PR1 301k/100k, 1M PR1-ST) -> LED_RAIL
  expansion  gated TLV75733P from LED_RAIL -> EXP_3V3, pull-ups, J_EXP (mirrored)
  sense      VBAT divider switched high-side by BAT_DIV_EN, CC1/CC2 100k, module-ID 100k
  key board  J_ROW, J_COL, J_LED, J_LINK (reversal-safe orders, 2026-09-15)

Variants: 'tps61099' (default population) and 'max17222'.

Run: .venv/bin/python tools/sch_core.py [--force]
Check: tools/kicad-check.sh
"""

import sys

import schlib

SCH = schlib.ROOT / "hardware" / "core" / "core.kicad_sch"

FP_R = "Resistor_SMD:R_0603_1608Metric"
FP_R0402 = "Resistor_SMD:R_0402_1005Metric"
FP_C = "Capacitor_SMD:C_0603_1608Metric"
FP_C0805 = "Capacitor_SMD:C_0805_2012Metric"
FP_SOT23 = "Package_TO_SOT_SMD:SOT-23"
FP_SOT583 = "Package_TO_SOT_SMD:SOT-583-8"
FP_DBV5 = "keyboard:TI_SOT-23-5_DBV0005A"
FP_GH = "Connector_JST:JST_GH_SM{0:02d}B-GHS-TB_1x{0:02d}-1MP_P1.25mm_Horizontal"
FP_TP = "TestPoint:TestPoint_Pad_D1.0mm"


def R(ref, value, xy, a, b, tol="1%", fp=FP_R, **props):
    return (ref, "Device:R", value, fp, xy, {"1": a, "2": b}, {"Tolerance": tol, **props})


def C(ref, value, xy, a, volt, diel="X7R", fp=FP_C, b="GND", **props):
    return (ref, "Device:C", value, fp, xy, {"1": a, "2": b}, {"Voltage": volt, "Dielectric": diel, **props})


def TP(ref, net, xy):
    return (ref, "Connector:TestPoint", net, FP_TP, xy, {"1": net}, {})


# nRF52840 pads per spec §5 (E12); pad numbers from RF_Module:Raytac_MDBT50Q
MCU_PINS = {
    "3": "ROW0", "4": "ROW1", "5": "ROW2", "6": "ROW3", "7": "ENC_A", "8": "ENC_B",
    "9": "MODULE_ID", "10": "CC2_SENSE", "11": "VBAT_SENSE", "12": "CC1_SENSE", "13": "COL7", "14": "COL8",
    "56": "COL0", "57": "COL1", "58": "COL2", "59": "COL3", "60": "COL4", "61": "COL5", "50": "COL6",
    "52": "ROW4", "54": "ROW5",
    "16": "ACOK_LOCAL", "17": "XL1", "18": "XL2", "19": "LED_BOOST_EN", "20": None, "21": None,
    "22": "U0_TX_MCU", "23": "U0_RX_MCU", "24": "U1_A_MCU", "25": "U1_B_MCU", "26": "LINK_SW_EN_MCU",
    "27": "ACOK_LINK", "29": "EXP_LDO_EN",
    "36": "LED_SCL", "37": "LED_SDA", "38": "LED_SDB", "39": "BOOT", "40": "NRESET",
    "41": "EXP_INT", "42": "EXP_RST", "43": "EXP_DC", "44": "EXP_CS", "45": "EXP_MOSI", "46": "EXP_SCK",
    "47": "EXP_SDA", "48": "EXP_SCL", "49": "BAT_DIV_EN",
    "28": "VSYS", "30": "VDDH", "31": "DCCH", "32": "VBUS_LOCAL", "34": "USB_DN_MCU", "35": "USB_DP_MCU",
    "51": "SWDIO", "53": "SWDCLK",
    "1": "GND", "2": "GND", "15": "GND", "33": "GND", "55": "GND",
}

# Part tuples and pin-table conventions: see tools/schlib.py.
PARTS = [
    # ---- MCU -------------------------------------------------------------------------------------------
    ("U401", "RF_Module:MDBT50Q-1MV2", "MDBT50Q-1MV2", "RF_Module:Raytac_MDBT50Q", (40, 44), MCU_PINS,
     {"MPN": "Raytac MDBT50Q-1MV2"}),
    # Raytac datasheet ver L §8.3: 10 uF on VDD, 10 uF on VBUS, 12 pF LFXO caps
    C("C403", "10u", (70, 20), "VSYS", "10V", fp=FP_C0805),
    C("C404", "100n", (74, 20), "VSYS", "16V"),
    C("C405", "10u", (78, 20), "VBUS_LOCAL", "10V", fp=FP_C0805),
    # LFXO: nRF52840 PS v1.9 p. 170 CL <= 12.5 pF, ESR <= 100k, Cpin 4 pF; 2 x 9 pF - 4 - ~2 stray = 12 pF
    ("Y401", "Device:Crystal", "32.768k", "Crystal:Crystal_SMD_3215-2Pin_3.2x1.5mm", (84, 44),
     {"1": "XL1", "2": "XL2"}, {"MPN": "Epson FC-135 32.768kHz CL 9pF"}),
    C("C401", "12p", (90, 44), "XL1", "50V", diel="C0G"),
    C("C402", "12p", (94, 44), "XL2", "50V", diel="C0G"),
    # Li-ion reservation (spec §15): VDDH bridged to VDD; REG0 inductor and VDDH cap not fitted
    ("JP401", "Jumper:SolderJumper_2_Bridged", "VDDH", "Jumper:SolderJumper-2_P1.3mm_Bridged_RoundedPad1.0x1.5mm",
     (84, 20), {"1": "VDDH", "2": "VSYS"}, {}),
    C("C406", "4.7u", (90, 20), "VDDH", "10V", fp=FP_C0805, DNP_reason="Li-ion build only (spec 15)"),
    ("L401", "Device:L", "10u", "Inductor_SMD:L_0603_1608Metric", (94, 20),
     {"1": "DCCH", "2": "VSYS"}, {"MPN": "10uH 0603 IDC>=80mA (Raytac L4)", "DNP_reason": "Li-ion build only (spec 15)"}),
    # USB: series per Raytac §8.3 (Nordic's reference has none)
    R("R401", "27", (100, 20), "USB_DP", "USB_DP_MCU"),
    R("R402", "27", (104, 20), "USB_DN", "USB_DN_MCU"),
    # SWD: TC2030 1 VCC, 2 SWDIO, 3 nRESET, 4 SWCLK, 5 GND, 6 SWO (Tag-Connect TC2030-CTX); SWO unused
    ("J401", "Connector_Generic:Conn_01x06", "TC2030-NL", "Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical",
     (112, 44), {"1": "VSYS", "2": "SWDIO", "3": "NRESET", "4": "SWDCLK", "5": "GND", "6": None},
     {"DNP_reason": "footprint only, no part"}),
    ("SW401", "Switch:SW_Push", "RESET", "Button_Switch_SMD:SW_Push_1P1T-MP_NO_Horizontal_Alps_SKRTLAE010",
     (100, 60), {"1": "NRESET", "2": "GND"}, {"MPN": "Alps SKRTLAE010"}),
    ("SW402", "Switch:SW_Push", "BOOT", "Button_Switch_SMD:SW_Push_1P1T-MP_NO_Horizontal_Alps_SKRTLAE010",
     (112, 60), {"1": "BOOT", "2": "GND"}, {"MPN": "Alps SKRTLAE010"}),

    # ---- link, LED bus, sense --------------------------------------------------------------------------
    # 470 ohm at every UART pin (spec §6); >= 100k pull-downs on left's RX and pair-2 pins
    R("R404", "470", (8, 84), "U0_TX_MCU", "U0_TX", fp=FP_R0402),
    R("R405", "470", (12, 84), "U0_RX_MCU", "U0_RX", fp=FP_R0402),
    R("R406", "470", (16, 84), "U1_A_MCU", "U1_A", fp=FP_R0402),
    R("R407", "470", (20, 84), "U1_B_MCU", "U1_B", fp=FP_R0402),
    R("R408", "100k", (24, 84), "U0_RX", "GND"),
    R("R409", "100k", (28, 84), "U1_A", "GND"),
    R("R410", "100k", (32, 84), "U1_B", "GND"),
    # J_LBD reversed puts LINK_SW_EN on GND: 10k holds the GPIO to <= 0.35 mA
    R("R411", "10k", (36, 84), "LINK_SW_EN_MCU", "LINK_SW_EN"),
    # KTS1693 ACOK open-drain, low while VBUS is valid
    R("R412", "100k", (40, 84), "VSYS", "ACOK_LOCAL"),
    R("R413", "100k", (44, 84), "VSYS", "ACOK_LINK"),
    # CC sense (spec §13)
    R("R414", "100k", (48, 84), "CC1", "CC1_SENSE"),
    R("R415", "100k", (52, 84), "CC2", "CC2_SENSE"),
    # LED driver I2C pull-ups (E11)
    R("R416", "4.7k", (56, 84), "VSYS", "LED_SDA"),
    R("R417", "4.7k", (60, 84), "VSYS", "LED_SCL"),
    # module ID: pull-up top is BAT_DIV_EN, key board has the resistor to GND
    R("R418", "100k", (64, 84), "BAT_DIV_EN", "MODULE_ID"),
    # VBAT sense, switched on the high side so AIN0 sits at 0 V between reads
    ("Q401", "Transistor_FET:Q_PMOS_GSD", "AO3415A", FP_SOT23, (76, 84),
     {"1": "VBAT_SW_G", "2": "VBAT", "3": "VBAT_DIV"}, {"MPN": "AOS AO3415A"}),
    R("R419", "1M", (70, 84), "VBAT", "VBAT_SW_G"),
    ("Q402", "Transistor_FET:Q_NMOS_GSD", "2N7002", FP_SOT23, (84, 92),
     {"1": "BAT_DIV_EN", "2": "GND", "3": "VBAT_SW_G"}, {"MPN": "Nexperia 2N7002"}),
    # holds Q402 (and so Q401) off while BAT_DIV_EN is undriven at boot or reset (2026-09-16)
    R("R440", "1M", (100, 84), "BAT_DIV_EN", "GND"),
    R("R420", "49.9k", (92, 84), "VBAT_DIV", "VBAT_SENSE"),
    R("R421", "49.9k", (96, 84), "VBAT_SENSE", "GND"),

    # ---- pack OR and UVLO ------------------------------------------------------------------------------
    ("J402", "Connector_Generic:Conn_01x04", "J_BAT_A", FP_GH.format(4), (8, 112),
     {"1": "PACK_A", "2": "GND", "3": "GND", "4": "PACK_A"}, {"MPN": "JST SM04B-GHS-TB"}),
    ("J403", "Connector_Generic:Conn_01x04", "J_BAT_B", FP_GH.format(4), (8, 128),
     {"1": "PACK_B", "2": "GND", "3": "GND", "4": "PACK_B"}, {"MPN": "JST SM04B-GHS-TB"}),
    # <= 1 uF per pack input: the hot-swap window scales with it (E14, R806)
    C("C407", "1u", (20, 112), "PACK_A", "10V"),
    C("C408", "1u", (24, 112), "PACK_B", "10V"),
    ("U402", "keyboard:LM66200DRL", "LM66200", FP_SOT583, (40, 116),
     {"3": "PACK_A", "6": "PACK_B", "4": "PACK_ON", "2": "VBAT", "7": "VBAT", "8": None, "1": "GND", "5": "GND"},
     {"MPN": "TI LM66200DRLR"}),
    ("D401", "Diode:BAT54C", "BAT54C", FP_SOT23, (24, 136),
     {"1": "PACK_A", "2": "PACK_B", "3": "SUP_VDD"}, {"MPN": "Diodes BAT54C-7-F"}),
    C("C409", "100n", (32, 136), "SUP_VDD", "16V"),
    ("U403", "keyboard:TPS3840PH18DBV", "TPS3840PH18", FP_DBV5, (44, 138),
     {"2": "SUP_VDD", "4": None, "5": None, "1": "UVLO_RST", "3": "GND"}, {"MPN": "TI TPS3840PH18DBVR"}),
    # slide switch: 2 (common) = ~ON; 1 = supervisor (on), 3 = SUP_VDD (packs off)
    ("SW403", "Switch:SW_SPDT", "POWER", "Button_Switch_SMD:SW_SPDT_PCM12", (58, 128),
     {"2": "PACK_ON", "1": "UVLO_RST", "3": "SUP_VDD"}, {"MPN": "C&K PCM12SMTR"}),
    # holds ~ON low (packs on) across the switch's break-before-make gap
    R("R403", "10M", (64, 136), "PACK_ON", "GND"),

    # ---- VBUS OR -----------------------------------------------------------------------------------------
    ("U404", "keyboard:LM66200DRL", "LM66200", FP_SOT583, (40, 156),
     {"3": "VBUS_LOCAL", "6": "VBUS_LINK_IN", "4": "GND", "2": "VBUS_IN", "7": "VBUS_IN", "8": None,
      "1": "GND", "5": "GND"},
     {"MPN": "TI LM66200DRLR"}),
    C("C410", "1u", (20, 156), "VBUS_LINK_IN", "10V"),
    # left's link input is unused; keeps it from floating
    R("R422", "1M", (24, 156), "VBUS_LINK_IN", "GND"),
    C("C411", "10u", (58, 156), "VBUS_IN", "10V", fp=FP_C0805),

    # ---- logic rail --------------------------------------------------------------------------------------
    # TLV757P SBVS320: CIN, COUT >= 1 uF; EN tied on
    ("U405", "keyboard:TLV75733PDBV", "TLV75733P", FP_DBV5, (90, 112),
     {"1": "VBUS_IN", "3": "VBUS_IN", "5": "V3P3_LDO", "4": None, "2": "GND"}, {"MPN": "TI TLV75733PDBVR"}),
    C("C412", "1u", (78, 112), "VBUS_IN", "10V"),
    C("C413", "1u", (102, 112), "V3P3_LDO", "10V"),
    # TPS61099 SLVSD88M: 2.2 uH for VOUT > 3 V (Table 8-2), CIN 10 uF, COUT >= 20 uF nominal
    ("U406", "Regulator_Switching:TPS61099DRV", "TPS61099", "keyboard:TI_WSON-6-1EP_2x2mm_P0.65mm_DRV0006A_TVS2200",
     (90, 136), {"6": "VBAT", "4": "VBAT", "5": "SW_LOGIC", "2": "V3P3_BOOST", "3": "FB_LOGIC", "1": "GND", "7": "GND"},
     {"MPN": "TI TPS61099DRVR"}),
    ("L402", "Device:L", "2.2u", "keyboard:L_Wuerth_WE-LQS-2512", (78, 128),
     {"1": "VBAT", "2": "SW_LOGIC"}, {"MPN": "Wuerth 74404024022"}),
    C("C414", "10u", (74, 136), "VBAT", "10V", fp=FP_C0805),
    R("R423", "576k", (106, 132), "V3P3_BOOST", "FB_LOGIC"),
    R("R424", "249k", (106, 144), "FB_LOGIC", "GND"),
    C("C415", "10u", (112, 136), "V3P3_BOOST", "10V", fp=FP_C0805),
    C("C416", "10u", (116, 136), "V3P3_BOOST", "10V", fp=FP_C0805),
    # MAX17222 second source: 2.2 uH, 10 uF in and out, RSEL 80.6k -> 3.3 V (MAX17220-MAX17225 datasheet)
    ("U407", "keyboard:MAX17222ELT", "MAX17222", "", (90, 160),
     {"5": "VBAT", "6": "VBAT", "2": "SW_MAX", "1": "V3P3_MAX", "4": "MAX_SEL", "3": "GND"},
     {"MPN": "ADI MAX17222ELT+"}),
    ("L403", "Device:L", "2.2u", "keyboard:L_Wuerth_WE-LQS-2512", (78, 152),
     {"1": "VBAT", "2": "SW_MAX"}, {"MPN": "Wuerth 74404024022"}),
    C("C417", "10u", (74, 160), "VBAT", "10V", fp=FP_C0805),
    R("R425", "80.6k", (106, 164), "MAX_SEL", "GND"),
    C("C418", "10u", (112, 160), "V3P3_MAX", "10V", fp=FP_C0805),
    # keeps the two boosts' power outputs on separate nets for ERC; fitted only with the MAX17222
    R("R426", "0", (116, 152), "V3P3_MAX", "V3P3_BOOST"),
    # VSYS mux, priority mode (MODE tied to VIN1); PR1 from VBUS_IN, hands over at 3.63-4.40 V
    ("U408", "Power_Management:TPS2116DRL", "TPS2116", FP_SOT583, (140, 116),
     {"3": "V3P3_LDO", "5": "V3P3_LDO", "4": "PR_VSYS", "6": "V3P3_BOOST", "2": "VSYS", "7": "VSYS",
      "8": None, "1": "GND"},
     {"MPN": "TI TPS2116DRLR"}),
    R("R427", "301k", (126, 112), "VBUS_IN", "PR_VSYS"),
    R("R428", "100k", (126, 124), "PR_VSYS", "GND"),
    C("C419", "10u", (154, 116), "VSYS", "10V", fp=FP_C0805),

    # ---- LED rail ----------------------------------------------------------------------------------------
    # TPS61023 SLVSF14B: 1 uH (Table 8-2), VREF 595 mV: 698k/100k -> 4.75 V; EN pulled up, GPIO may only disable
    ("U409", "keyboard:TPS61023DRL", "TPS61023", "keyboard:TI_SOT-563_DRL0006A", (140, 140),
     {"3": "VBAT", "2": "LED_BOOST_EN", "5": "SW_LED", "6": "LED_BOOST", "1": "FB_LED", "4": "GND"},
     {"MPN": "TI TPS61023DRLR"}),
    ("L404", "Device:L", "1u", "Inductor_SMD:L_Coilcraft_XAL4030-XXX", (126, 136),
     {"1": "VBAT", "2": "SW_LED"}, {"MPN": "Coilcraft XEL4030-102ME"}),
    C("C420", "10u", (122, 144), "VBAT", "10V", fp=FP_C0805),
    R("R431", "100k", (126, 150), "VSYS", "LED_BOOST_EN"),
    R("R429", "698k", (154, 136), "LED_BOOST", "FB_LED"),
    R("R430", "100k", (154, 148), "FB_LED", "GND"),
    C("C421", "22u", (160, 140), "LED_BOOST", "10V", fp=FP_C0805),
    C("C422", "22u", (164, 140), "LED_BOOST", "10V", fp=FP_C0805),
    # LED mux, priority: PR1 301k/100k from VBUS_IN, 1M PR1-ST hysteresis (E3)
    ("U410", "Power_Management:TPS2116DRL", "TPS2116", FP_SOT583, (140, 164),
     {"3": "VBUS_IN", "5": "VBUS_IN", "4": "PR_LED", "6": "LED_BOOST", "2": "LED_RAIL", "7": "LED_RAIL",
      "8": "LED_ST", "1": "GND"},
     {"MPN": "TI TPS2116DRLR"}),
    R("R432", "301k", (122, 160), "VBUS_IN", "PR_LED"),
    R("R433", "100k", (122, 172), "PR_LED", "GND"),
    R("R434", "1M", (158, 160), "PR_LED", "LED_ST"),
    C("C423", "10u", (164, 164), "LED_RAIL", "10V", fp=FP_C0805),

    # ---- expansion ---------------------------------------------------------------------------------------
    ("U411", "keyboard:TLV75733PDBV", "TLV75733P", FP_DBV5, (190, 116),
     {"1": "LED_RAIL", "3": "EXP_LDO_EN", "5": "EXP_3V3", "4": None, "2": "GND"}, {"MPN": "TI TLV75733PDBVR"}),
    C("C424", "1u", (178, 112), "LED_RAIL", "10V"),
    R("R435", "100k", (178, 124), "EXP_LDO_EN", "GND"),
    C("C425", "10u", (202, 116), "EXP_3V3", "10V", fp=FP_C0805),
    R("R436", "4.7k", (178, 136), "EXP_3V3", "EXP_SDA"),
    R("R437", "4.7k", (182, 136), "EXP_3V3", "EXP_SCL"),
    R("R438", "100k", (186, 136), "EXP_3V3", "EXP_CS"),
    R("R439", "100k", (190, 136), "EXP_3V3", "EXP_INT"),
    # 4x M2 at the corners (2026-09-16); symbols so PCB parity stays clean
    *[(f"H40{i}", "Mechanical:MountingHole", "MountingHole", "MountingHole:MountingHole_2.2mm_M2_ISO7380",
       (24 + 6 * i, 8), {}, {}) for i in range(1, 5)],
    # J_EXP mirrored (spec §6), pin for pin with the expansion board's J1002
    ("J404", "Connector_Generic:Conn_01x15", "J_EXP", FP_GH.format(15), (214, 144),
     {"1": "VBUS_LOCAL", "2": "GND", "3": "EXP_3V3", "4": "EXP_SCL", "5": "EXP_SDA", "6": "EXP_RST", "7": "EXP_DC",
      "8": "GND", "9": "EXP_CS", "10": "EXP_MOSI", "11": "EXP_INT", "12": "EXP_SCK", "13": "EXP_3V3", "14": "GND",
      "15": "VBUS_LOCAL"},
     {"MPN": "JST SM15B-GHS-TB"}),

    # ---- connectors to the USB port board and key board ------------------------------------------------
    ("J405", "Connector_Generic:Conn_01x11", "J_USB", FP_GH.format(11), (150, 20),
     {"1": "VBUS_LOCAL", "2": "GND", "3": "CC1", "4": "GND", "5": "USB_DP", "6": "VBUS_LOCAL", "7": "USB_DN",
      "8": "ACOK_LOCAL", "9": "CC2", "10": "GND", "11": "VBUS_LOCAL"},
     {"MPN": "JST SM11B-GHS-TB"}),
    ("J406", "Connector_Generic:Conn_01x12", "J_LED", FP_GH.format(12), (174, 20),
     {"1": "LED_RAIL", "2": "GND", "3": "LED_SDA", "4": "VSYS", "5": "LED_SDB", "6": "GND", "7": "GND",
      "8": "MODULE_ID", "9": "VSYS", "10": "LED_SCL", "11": "GND", "12": "LED_RAIL"},
     {"MPN": "JST SM12B-GHS-TB"}),
    ("J407", "Connector_Generic:Conn_01x07", "J_ROW", FP_GH.format(7), (198, 20),
     {"1": "ROW0", "2": "ROW1", "3": "ROW2", "4": "GND", "5": "ROW3", "6": "ROW4", "7": "ROW5"},
     {"MPN": "JST SM07B-GHS-TB"}),
    ("J408", "Connector_Generic:Conn_01x13", "J_COL", FP_GH.format(13), (150, 64),
     {"1": "GND", "2": "COL0", "3": "COL1", "4": "COL2", "5": "COL3", "6": "COL4", "7": "COL5", "8": "COL6",
      "9": "COL7", "10": "COL8", "11": "ENC_A", "12": "ENC_B", "13": "GND"},
     {"MPN": "JST SM13B-GHS-TB"}),
    ("J409", "Connector_Generic:Conn_01x14", "J_LINK", FP_GH.format(14), (174, 64),
     {"1": "VBUS_LINK_IN", "2": "GND", "3": "U0_TX", "4": "U1_A", "5": "GND", "6": "LINK_SW_EN", "7": "VBUS_IN",
      "8": "VBUS_IN", "9": "ACOK_LINK", "10": "GND", "11": "U1_B", "12": "U0_RX", "13": "GND", "14": "VBUS_LINK_IN"},
     {"MPN": "JST SM14B-GHS-TB"}),

    # ---- test points (spec §13) ------------------------------------------------------------------------
    *[TP(f"TP{401 + i}", net, (200 + 9 * (i % 6), 44 + 12 * (i // 6))) for i, net in enumerate((
        "VBAT", "VSYS", "VBUS_IN", "LED_RAIL", "EXP_3V3", "GND",
        "LED_BOOST_EN", "LED_SDA", "LED_SCL", "EXP_SDA", "EXP_SCL", "U0_TX",
        "U0_RX", "U1_A", "U1_B", "CC1", "CC2", "MODULE_ID",
        "SWDIO", "SWDCLK", "NRESET"))],
]

MAX_ONLY = {"U407", "L403", "C417", "R425", "C418", "R426"}
TPS_ONLY = {"U406", "L402", "C414", "R423", "R424", "C415", "C416"}
DNP = MAX_ONLY | {"C406", "L401", "J401"}
VARIANTS = {
    "tps61099": DNP,
    "max17222": (DNP - MAX_ONLY) | TPS_ONLY,
}

# nets fed only by passive or power_in pins
FLAGS = [
    ("#FLG0401", "GND", (8, 150)), ("#FLG0402", "PACK_A", (14, 104)), ("#FLG0403", "PACK_B", (14, 120)),
    ("#FLG0404", "SUP_VDD", (20, 128)), ("#FLG0405", "VBUS_LOCAL", (14, 146)), ("#FLG0406", "VBUS_LINK_IN", (8, 160)),
    ("#FLG0407", "SW_LOGIC", (68, 124)), ("#FLG0408", "VDDH", (100, 34)),
]

# intended connectivity from the pin tables: KiCad's netlist is compared against it
NETS = {}
for _ref, _lib, _val, _fp, _xy, _pins, _props in PARTS:
    for _pin, _net in _pins.items():
        if _net not in (None, "-"):
            NETS.setdefault(_net, []).append(f"{_ref}.{_pin}")
# the nets come from the same table, so a mistyped name would pass the netlist check: catch it here
_single = sorted(n for n, nodes in NETS.items() if len(nodes) < 2)
if _single:
    sys.exit(f"nets with one node (typo?): {_single}")

NOTES = [
    ((4, 176), "Core board per spec §2a, §4, §5, §6. MCU pads per the §5 table (E12); MDBT50Q-U1MV2 second source assumed pad-identical (unverified).\n"
               "Pack OR: J_BAT_A/B (1 PACK+, 2 GND, 3 GND, 4 PACK+) -> LM66200 U402 -> VBAT. Each pack input <= 1 uF (E14: hot-swap window scales with it).\n"
               "UVLO: TPS3840PH18 on BAT54C-OR'd packs drives ~ON high below ~1.9 V. SW403 (slide) picks ~ON: supervisor (on) or SUP_VDD (packs off, 0 uA); R403 10M holds 'on' in the gap.\n"
               "VBUS_IN = LM66200 U404 OR of VBUS_LOCAL (J_USB) and VBUS_LINK_IN (J_LINK). VSYS = TPS2116 U408: IN1 TLV75733P from VBUS_IN, IN2 logic boost from VBAT;\n"
               "PR1 301k/100k from VBUS_IN (drops to IN2 at 3.63-4.40 V). Logic boost variants: 'tps61099' U406 576k/249k (default) or 'max17222' U407 RSEL 80.6k via R426 0 ohm.\n"
               "LED rail = TPS2116 U410: IN1 VBUS_IN, IN2 TPS61023 U409 (698k/100k -> 4.75 V, EN pulled up to VSYS); PR1 301k/100k, 1M PR1-ST hysteresis (E3).\n"
               "Expansion 3V3: TLV75733P U411 from LED_RAIL, EN from GPIO with 100k pull-down, 150 mA budget. Pull-ups to EXP_3V3: keep MCU pins low or undriven while it is off.\n"
               "VBAT sense: Q401 AO3415A switches 49.9k/49.9k from VBAT when BAT_DIV_EN (also the module-ID pull-up top) is high; R440 1M holds it off while undriven; AIN0 <= 1.9 V. CC1/CC2 100k into AINx.\n"
               "J_LED 1 RAIL 2 GND 3 SDA 4 VSYS 5 SDB 6 GND | 7 GND 8 ID 9 VSYS 10 SCL 11 GND 12 RAIL. J_ROW 1-3 ROW0-2, 4 GND, 5-7 ROW3-5.\n"
               "J_COL 1 GND, 2-10 COL0-8, 11 ENC_A, 12 ENC_B, 13 GND. J_LINK 1 VBUS_LINK_IN 2 GND 3 U0_TX 4 U1_A 5 GND 6 LINK_SW_EN 7 VBUS_IN_OUT | mirrored to 14.\n"
               "All key-board headers reversal-safe (pin k meets N+1-k). Li-ion reservation (spec §15): JP401 bridged VDDH-VDD, C406 and L401 (REG0) not fitted. J401 TC2030-NL footprint only."),
]

if __name__ == "__main__":
    schlib.run(SCH, "core", "Core board", 400, PARTS, FLAGS, NOTES, NETS, dnp=DNP, variants=VARIANTS, paper="A1")
