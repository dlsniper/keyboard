# Split K860-alike, rev 9: hub tower, one Pico 2 W, Go firmware

Three-piece MX keyboard styled on the Logitech ERGO K860: `left` (alphas), `right`
(alphas + arrows + nav + dial), `numpad`, each cabled to a **hub tower** that is the
keyboard as far as the host is concerned. Firmware in Go (TinyGo).

**Rev 9.1 (2026-11-13, user):** the hub tower and the AA battery modules are back.
They are an integral part of the product and its differentiator; the first rev 9
draft had dropped them and put a Pico in every module. Now: **one socketed Pico 2 W,
in the hub**; key modules carry no controller. Rev 8's files stay under
`archive/rev8/` (tag `rev8-archive`) as the reference for the hub and battery work.

Decided by the user 2026-11-13: wired USB first; Pico 2 W; ANSI; D1 key set (§2);
hub tower + AA modules restored; key modules read through SPI port expanders scanned
by the hub; the hub's core layer is the swappable unit; up to 5 AA modules;
latency like a proper keyboard and n-key rollover.

Priorities, unchanged: repairable and user-friendly before compact; modular and
upgradeable; FDM-printed ASA case; parts from Mouser Europe / European distributors.

## 1. Topology

```
                         +--------------------------+
 host --USB-C----------->| hub tower                |--cable--> left
        (Bluetooth: M6)  |  core layer: Pico 2 W    |--cable--> right
                         |  connector layer: 3 slots|--cable--> numpad
                         |  AA modules 1..5         |
                         +--------------------------+
```

- **Hub tower** (about 100 x 100 mm ASA stack on the desk, rev 8 concept): top to
  bottom optional layers, core layer, connector layer, AA battery modules. It holds
  the only controller, the host USB-C port, the power path and the cells. Front
  buttons: power, reset, boot.
- **Core layer = the upgrade unit**: Pico 2 W on pin sockets. The connector between
  core layer and the rest is frozen at M1 so a later core board (for example with a
  Nordic module, if Bluetooth on the Pico 2 W proves too hard) drops in without
  touching key modules, cables or battery modules.
- **Key modules are dumb**: sockets, diodes, LEDs, one SPI port expander
  (MCP23S17 class; two on `right`), a cable connector. No firmware, nothing to flash.
- **Cable, hub to each module (D3, user, 2026-11-13): a full-featured USB-C cable
  (USB 3 / Thunderbolt class, all wires present) used as plain wiring, not as USB.**
  A USB 2.0 or charge-only USB-C cable does not work; ports and cables get marked.
  Chosen over RJ45, GX16 and a ribbon header. **Wire plan (M1, 2026-11-13)**,
  flip-proof without a mux: on every receptacle the two lanes of each kind are tied
  together (A2=B2, A3=B3, A10=B10, A11=B11, A6=B6, A7=B7, A8=B8), so each signal
  runs on two cable wires in parallel and either plug orientation gives the same
  circuit. Pairs are chosen by what tolerates crosstalk inside a pair:

  | Signal | Hub receptacle | Module receptacle | Why there |
  | --- | --- | --- | --- |
  | SCK | TX1+/TX2+ (A2, B2) | RX1+/RX2+ (B11, A11) | shielded, alone |
  | GND (SCK return) | TX1-/TX2- (A3, B3) | RX1-/RX2- (B10, A10) | clock gets its own return |
  | MOSI | RX1+/RX2+ (B11, A11) | TX1+/TX2+ (A2, B2) | data with data: both settle before the SCK edge |
  | MISO | RX1-/RX2- (B10, A10) | TX1-/TX2- (A3, B3) | as above |
  | CS | D+ (A6, B6) | D+ | slow; 1 k + 100 pF and a 100 k pull-up at the module |
  | INT | D- (A7, B7) | D- | open drain, 10 k pull-up on the module's port board (none at the hub, so a port that is off is not back-fed) |
  | LED data, 5 V level | SBU1 = SBU2 (A8, B8) | SBU1 = SBU2 | 330 R at the hub, 220 R in front of the first LED |
  | 5 V | VBUS x 4 | VBUS x 4 | 3 A cable |
  | GND | GND x 4, shell | GND x 4, shell | |
  | CC1, CC2 (separate) | Rp each | Rd 5.1 k each | real USB-C roles, below |

  The cable crosses TX to RX, so **hub side and module side have different
  pin-outs**. Checked at the M1 review against the Type-C cable wiring (A2 to B11,
  A3 to B10, B2 to A11, B3 to A10, D+/D- straight, SBU1 to SBU2, one CC wire): right
  for passive full-featured cables; **active or redriver cables do not pass DC and
  do not work**. Still buzz out the real cable before M4's bench test (O2).
- **CC is used as USB-C means it**: every hub port is a plain 5 V source (Rp, VBUS
  switched on only when Rd is seen, current-limited; one **TPS25810** Type-C source
  switch per port, user, 2026-11-13, §3a), every module is a plain
  sink (Rd). That gives module detect and the per-module rail switch, and makes
  mis-plugs harmless: a module in a charger or laptop is just powered and idle
  (INT is open drain, MISO is off while CS is high, CS is held high by the port
  board's pull-up); a phone in a hub port is charged, sees CS (3.3 V) on D+ and no
  clock or data. The hub drives SCK and MOSI on a port only while that port's CS is
  low, and holds LED data low while a module's LED rail is off.
- Modules are told apart by expander address, so **any module works in any hub
  port**: `left` 0, `numpad` 1, `right` 2 and 3 (MCP23S17 address pins, HAEN).
- Other consequences: there is no 3.3 V wire, so 3.3 V is made on the module's port
  board; there is one 5 V wire, so the LED rail is switched **on the key board** by
  an expander pin; the 24-pin receptacle is reflow-only, which is why it sits on
  the small port board.
- **Port bay (D3, user, 2026-11-13):** the USB-C receptacle is not on the key board.
  Each key board has a frozen through-hole **2x6 header** in a rear bay (about
  30 x 25 mm), 2.54 mm pitch, pins on the key board, socket on the port board:

  | Pin | Net | Pin | Net |
  | --- | --- | --- | --- |
  | 1 | 5 V | 2 | 5 V |
  | 3 | GND | 4 | LED data in |
  | 5 | 3.3 V in | 6 | spare (to the spare-pin header) |
  | 7 | INT | 8 | CS |
  | 9 | MISO | 10 | MOSI |
  | 11 | GND | 12 | SCK |

  (Detect needs no pin: it is done on CC, on the port board.) A small **port board**
  (receptacle, Rd, 3.3 V regulator, CS filter and pull-up, INT pull-up, 33 R in MISO, ESD arrays and a VBUS TVS) plugs onto it, held
  by two M2 screws placed off-centre so it cannot go on reversed. A worn port is a
  two-screw swap, and a different cable later needs only new port boards.
  **M2 (user, 2026-11-13):** the bay is at the inner (split) end of a full-width rear strip, 25 mm deep behind the
  F-row caps; the port board plugs on the **top side** of the key board (header pins up, socket on the underside
  of the port board), under a small top cover. Bay geometry: `tools/pcb_keys.py` `BAY`.
- **Cable-free modules are a wanted upgrade (user, 2026-11-13), not rev 9's first
  build.** The module's cable connector doubles as a **pod socket**: a later pod
  (its own controller with radio, its own AA pack and converter) plugs in where the
  cable goes and becomes the SPI master of that module's expander. Key boards stay
  the same in both cases: the pod replaces the port board on the 2x6 bay header and
  feeds 5 V and 3.3 V through it (O10).
- The hub has a rear **expansion port**; each key board keeps a few spare expander
  pins on a header.

## 2. Modules

| | left | right | numpad |
| --- | --- | --- | --- |
| Keys (D1; **final, D2 signed off 2026-11-13**) | 36 | 52 + dial push | 22 |
| Matrix (rows x cols), by physical position; final | 6 x 7 | 6 x 11 | 6 x 4 |
| Reader | 1 x SPI expander (13 pins used) | 2 x SPI expander (17 matrix + 2 dial) | 1 x SPI expander (10 pins) |
| LEDs (SK6812MINI-E, D10) | 36 | 52 (none under the dial) | 22 |
| Dial | none | PEC11R, 24 detents, push switch in the matrix, on the separate dial board | none |

- Switches: MX, Kailh hotswap sockets (CPG151101S11). One **Schottky diode (BAT43W
  class, SOD-123)** per key, so every module has full n-key rollover. Not a 1N4148W
  (M1 review): at the 0.3 mA of a 10 k pull-up its drop (up to about 0.68 V) leaves
  the column above the expander's guaranteed input-low level (0.2 x VDD = 0.66 V).
  BAT43W values are from memory; its datasheet is to be read when the parts list is made.
- **Latency target: that of a proper keyboard.** The hub scans all three matrices
  at 1 kHz or faster (about 0.1 ms per module pass at 4 MHz SPI). A keypad-scanner
  chip was rejected for this: the TCA8418 datasheet gives a fixed 25-40 ms.
- **ANSI (US) layout.**
- **Key set (D1, user, 2026-11-13)**, K860 as the model, all alpha keys 1u (stepped
  inner edge, standard caps):
  - `left`: Esc F1-F6 / ` 1-6 / Tab Q-T / Caps A-G / Shift Z-B / Ctrl 1.5, Win 1.5,
    Alt 1.5, Space 2.75.
  - `right`: F7-F12 + 2 extra 1u keys / 7-= Backspace / Y-\ / H-Enter / N-Shift /
    Space 2.75, Alt 1.75, Fn 1.75, Ctrl 1.5 (1.75u modifiers need blank or relegended
    caps); TKL nav block (Ins Home PgUp / Del End PgDn, inverted-T arrows); above it
    two keys and the dial in the rear outer corner.
  - `numpad`: K860 copy, 4 keys level with the F-row, Clr / * -, tall +, 1u Enter,
    2u 0, `.`, `=`.
- **Positions: `layout/keys.json`**, written by `tools/gen_layout.py` (parameters at
  the top; never edit the JSON by hand), drawn by `tools/render_layout.py`. Pitch
  19.05 mm. Each alpha half: rows are concentric arcs (Shift row radius 790 mm), 0° at
  the outer edge to about 10° at the split, constant pitch along each arc; the bottom
  row is straight, on the 5° chord; F-row 0.25u behind the number row; nav block and
  numpad square. Checked against the K860 print and the printed test cell
  (`mech/testcell/`: switch in the 14.1 mm cutout, cap gap at the tightest rotated
  spot, socket seating, LED window under the switch slot); **signed off by the user,
  D2, 2026-11-13**. The file is independent of where the controller sits.
- **Key board circuit (M1, 2026-11-13).** Rows are driven low one at a time,
  columns are read; diode anode towards the column, cathode on the row. Each column
  has an **external 10 k pull-up to 3.3 V**: the expander's internal 100 k is too
  slow to let a column recover between two rows at 1 kHz+. The same for the two dial
  phases. Expander pins (MCP23S17, `GPA`/`GPB`):

  | | left (addr 0) | numpad (addr 1) | right U1 (addr 2) | right U2 (addr 3) |
  | --- | --- | --- | --- | --- |
  | Columns | GPA0-6 | GPA0-3 | GPA0-7 = col 0-7, GPB0-2 = col 8-10 | |
  | Rows | GPB0-5 | GPB0-5 | | GPA0-5 |
  | Dial A, B | | | GPB3, GPB4 | |
  | LED rail enable | GPB7 | GPB7 | | GPB7 |
  | Spare, on the header | GPA7, GPB6 | GPA4-7, GPB6 | GPB5-7 | GPA6-7, GPB0-6 |

  On `right` one 4-byte read of U1 returns all columns and the dial, so a full scan
  is 6 row writes and 6 reads. INT outputs are open drain, wired together. The LED
  rail goes through a load switch with slew control (TPS22918 class, 2 A) whose
  enable is pulled down, so LEDs are off until firmware turns them on (CT 1 nF:
  about 2.5 ms rise, about 0.2 A inrush). LED chain: 100 nF per LED, bulk capacitor
  at the switch output, 220 R in front of the first LED's data input.
- Stabilisers: Cherry MX plate/PCB 2U footprint from the vendored kiswitch subset.
- Plate: 1.5 mm FR4, no copper (as rev 8).
- **Key board outline (M2, user, 2026-11-13):** four straight edges with 3 mm fillets (outer, front parallel to the
  bottom row, inner along the split, rear parallel to the F-row chord), 4 mm beyond the caps at the sides, 6 mm at
  the front; all SMD parts on the back; provisional M2 holes, final with the case (M3). **Board house (D6): JLCPCB
  makes and assembles.** Placement is generated by `tools/pcb_keys.py`.
- **Key LEDs: SK6812MINI-E chain (D10, user, 2026-11-13)**, one per key, reverse
  mount through a 3.4 x 3.0 mm board window south of the switch, one data wire per
  module. Chosen over rev 8's IS31FL3733 matrix (I2C would add 2-3 cable wires, no
  TinyGo driver, 28 matrix nets per module, chip must not be power-gated). Costs
  accepted: about 1 mA per LED with the rail on and the LEDs dark (datasheet typ,
  about 110 mA for 110 LEDs), so **the hub switches the LED rail off whenever the
  LEDs are off**; a dead LED cuts the chain behind it; the 3.3 V data line needs a
  5 V level shifter at the hub (74AHCT125 class; VIH is 0.7 x VDD). Driver:
  `tinygo.org/x/drivers/ws2812` (PIO on RP2350). Source: not found at Mouser so far
  (Adafruit 4960 packs, or OPSCO parts from another distributor); to settle in the
  M1 parts list.

## 3. Power

- Sources: host USB (priority) or **AA battery modules, up to 5** stacked under the
  hub (user, 2026-11-13; rev 8.1 planned 3). Each is passive: 4 x AA NiMH (alkaline
  tolerated), holder, PTC; charged outside the keyboard. No Li-ion, no charging.
- Power path in the hub, on the connector layer, from rev 8.1's design (ideal diode
  per pack, USB priority switch, under-voltage cut-off at about 1.0 V per cell, 5 V
  buck-boost, pack voltage read by the controller), drawn at M1 for 5 packs and the
  Pico 2 W, with **lowest-module-first pack priority** (user, 2026-11-13). Details
  in §3a.
- The hub switches each module's rail, so LEDs draw nothing when off and on battery.
- Firmware caps LED current from what the source offers (USB 500 mA / 1.5 A / 3 A
  from the CC pins; battery: its own cap). Values by measurement (O3).
- Batteries only pay off with Bluetooth (M6). Expect days to weeks per pack on a
  Pico 2 W, to be measured; the swappable core layer is the way out if that is not
  enough.

## 3a. Hub boards (M1, 2026-11-13)

Source of every table here: `tools/sch_hub.py` (generates `hardware/hub-core`,
`hardware/hub-conn`, `hardware/battery`; the script checks the netlists against its
tables and the boards against each other).

- **Two hub boards.** Core layer `hub-core`: Pico 2 W on sockets, buttons, stack
  connector, expansion header. Connector layer `hub-conn`: three module ports, the
  cable header to the host port board (`hardware/usb-port`, unchanged), and the
  whole power path (user, 2026-11-13: not a separate power board).
- **Pico USB and BOOTSEL by pogo pins** (user, 2026-11-13): the Pico 2 W has USB
  D+/D- and BOOTSEL only on underside pads (TP3, TP2, TP6); three spring pins on the
  core board reach them. Pin height and positions are set at M2 from the Pico
  drawing. The Pico's VSYS is fed from +5V through a Schottky; its 3V3 output is the
  hub's logic rail.
- **Buttons:** power is a latching switch in the battery-switch gate line (microamps;
  on USB the hub is always on), reset pulls RUN low, boot pulls BOOTSEL low.
- **Stack connector, frozen: 2x25, 2.54 mm**, pins on the core, socket on the
  connector layer. `SDA`/`SCL` (GP0/GP1), `RUN` and `SP1`-`SP4` are reserved for
  later boards and also sit on the core's 2x5 expansion header.

  | Pin | Net | Pin | Net |
  | --- | --- | --- | --- |
  | 1 | +5V | 2 | +5V |
  | 3 | GND | 4 | GND |
  | 5 | +3V3 | 6 | +3V3 |
  | 7 | USB_DP | 8 | GND |
  | 9 | USB_DN | 10 | GND |
  | 11 | SCK | 12 | GND |
  | 13 | MOSI | 14 | MISO |
  | 15 | CS_A | 16 | CS_B |
  | 17 | CS_C | 18 | GND |
  | 19 | INT_A | 20 | INT_B |
  | 21 | INT_C | 22 | PORT_FLT |
  | 23 | LED_A | 24 | LED_B |
  | 25 | LED_C | 26 | GND |
  | 27 | EN_A | 28 | EN_B |
  | 29 | EN_C | 30 | USB_PRESENT |
  | 31 | DET_A | 32 | DET_B |
  | 33 | DET_C | 34 | GND |
  | 35 | CC1_SENSE | 36 | CC2_SENSE |
  | 37 | VBAT_SENSE | 38 | GND |
  | 39 | BAT_DIV_EN | 40 | RUN |
  | 41 | PWR_SW_A | 42 | PWR_SW_B |
  | 43 | SDA | 44 | SCL |
  | 45 | SP1 | 46 | SP2 |
  | 47 | SP3 | 48 | SP4 |
  | 49 | GND | 50 | GND |

- **Hub pin map (Pico 2 W).** SPI0 on GP16/18/19; everything else is plain GPIO.
  No internal pull-downs are relied on (RP2350-E9): every input has an external
  pull-up or a divider.

  | GPIO | Net |
  | --- | --- |
  | GP0 | SDA |
  | GP1 | SCL |
  | GP2 | EN_A |
  | GP3 | DET_A |
  | GP4 | INT_A |
  | GP5 | CS_A |
  | GP6 | LED_A |
  | GP7 | EN_B |
  | GP8 | DET_B |
  | GP9 | INT_B |
  | GP10 | CS_B |
  | GP11 | LED_B |
  | GP12 | EN_C |
  | GP13 | DET_C |
  | GP14 | INT_C |
  | GP15 | CS_C |
  | GP16 | MISO |
  | GP17 | LED_C |
  | GP18 | SCK |
  | GP19 | MOSI |
  | GP20 | PORT_FLT |
  | GP21 | USB_PRESENT |
  | GP22 | BAT_DIV_EN |
  | GP26 | CC1_SENSE |
  | GP27 | CC2_SENSE |
  | GP28 | VBAT_SENSE |

  `EN_x` high powers port x (10 k pull-down: off at reset). `DET_x` low = a sink
  (Rd) is attached and VBUS is on. `PORT_FLT` low = a port is in current limit or
  too hot (wired-OR). `INT_x` is the module's open-drain interrupt (pull-up on the module; firmware
  enables the Pico's pull-up on it only while `DET_x` is low). `USB_PRESENT` high = host VBUS above about 3.8 V. `CC1/CC2_SENSE` read the
  host's Rp for the current cap (§3). `VBAT_SENSE` is 1/3 of the highest pack (less a Schottky drop) while
  `BAT_DIV_EN` is high; the divider hangs before the UVLO supervisor's 10 k so a
  measurement cannot trip the UVLO. `USB_PRESENT` is a 10 k / 15 k divider (stiff
  enough for RP2350-E9; 2.3 V at the pin with VBUS at 3.8 V, 3.3 V at 5.5 V). **Exported for the firmware: `firmware/hub-pinmap.json`**,
  written and checked by `tools/sch_hub.py`.
- **Module port (x3).** 24-pin receptacle wired per the hub column of §1.
  **TPS25810** (user, 2026-11-13, over the 1.5 A TPS25821): advertises 3 A, limit
  3.4 A; a strap changes it to 1.5 A / 1.7 A. Confirmed by the user after the M1
  review; the 5 V rail was raised to match (TPS552892, §3b). **One 74LVC125A per port** (user, 2026-11-13): SCK and MOSI reach the
  cable, and MISO comes back, only while that port's CS is low; the CS line itself
  is driven only while `DET_x` is low. So each cable is driven point to point, a
  dead module cannot hold MISO, and a phone or an unpowered module sees no SPI.
  33 R in series at the buffer outputs, 100 k pull-downs on the cable side. LED
  data: one 74AHCT125 at 5 V for the three ports, 330 R in series, low by default.
  ESD arrays (TPD4E1U06) on the six signals and CC, TVS0500 on the port's VBUS.
- **Battery chain, 2x8 pogo seam** (user, 2026-11-13), reversal-safe (pin k meets
  17-k): 1 PACK1, 2 GND, 3 PACK2, 4 PACK3, 5 GND, 6 PACK4, 7 PACK5, 8 AUX_5V, 9 AUX_5V, 10 PACK5, 11 PACK4, 12 GND, 13 PACK3, 14 PACK2, 15 GND, 16 PACK1. Each module puts its own pack on `PACK1` upwards and passes
  `PACK1`-`PACK4` from below on as `PACK2`-`PACK5`, so hub input n is the n-th
  module from the hub and input 5 is the lowest. Modules stay passive (holder, PTC).
- **Power path** (rev 8.1 parts and values unless said): per pack input SMF4L9.0CA,
  LM74610-Q1 + **SQ4184EY** (SO-8, from the LM74610 datasheet's own FET list; M1 task 5);
  the packs meet on `VBAT`; CSD25402Q3A battery switch to
  `SYS` (power switch AND TPS3840PL40 UVLO AND no USB); second CSD25402Q3A from
  `VBUS_IN` with a **TPS3840PL36** detect and the 2.2 M / 22 n delay, **1 k** on its gate;
  4 x 47 uF ceramic + **220 uF polymer** on `SYS`; a **TPS552892** makes +5V for the ports
  and the Pico. Dropped against rev 8.1: the
  TPS70933 (the Pico has its own regulator; `SYS` reaches 6.4 V, above the Pico's
  5.5 V VSYS limit, which is why the Pico runs from +5V).
- **5 V converter, TPS552892 (M1 task 5, 2026-11-13)**, 21-pin VQFN 3 x 5 mm, no I2C,
  circuit from its datasheet: 400 kHz (FSW 49.9 k), 4.7 uH (XAL7070-472 class: Isat
  15 A against the 13 A peak limit; the loop needs more than 3 uH at 400 kHz), FB
  100 k / 31.6 k = 5.00 V, MODE low = PFM at light load, DITH/SYNC to GND, EXTVCC and
  CDC open (internal VCC regulator, no cable compensation), ISP = ISN = VOUT (no
  output current limit; each port has its own), PG and CC unused, boot capacitors
  2 x 100 n, VCC 22 uF, COMP 12 k + 15 n with 470 p in parallel (crossover about
  4 kHz with the 300 uF on +5V; right-half-plane zero 20-25 kHz at 3.6 V in), output
  3 x 22 uF + 100 n + **220 uF polymer** (the TPS25810 asks for 120 uF or more; the
  converter allows 10-1000 uF). **EN/UVLO 100 k / 54.9 k**: on above about 3.5 V, off
  below about 2.95 V, so a sagging pack switches the converter off cleanly instead of
  running it under its 3.0 V minimum. Start-up: VCC comes from VIN, then from the 5 V
  output while VIN is below it. Layout notes for M2 are on the sheet (AGND and PGND
  join at the VCC capacitor).
- **USB / battery switchover, simulated** (`python3 tools/sim_switchover.py`, new at
  M1 task 5; the rev 8.1 values did not survive the higher load):
  - *Both switches were on together for about 20 us at every unplug* (10 k gate
    resistor); with a full alkaline pack that lifted `VBUS_IN`, the detector saw
    "USB" again and the two switches chattered. Fix: **1 k** on the USB switch gate
    (5 mA, on USB only): no overlap in any case.
  - *A 4.3 V detect threshold reads a loaded host as absent.* USB allows 4.0 V at the
    connector at 3 A; with a pack fitted the hub then flipped between the sources at
    several hundred Hz. Fix: **TPS3840PL36** (falls at 3.6 V, rises at 3.8 V). The
    price: after an unplug `SYS` sags to 3.6 V before the pack takes over, which the
    converter does not notice (lowest `SYS` 3.3-3.6 V up to 10 W with the extra
    **220 uF on `SYS`**).
  - Unplug with the pack's ideal diode asleep (after a time on USB the LM74610 has
    lost its charge, so the pack current runs through the FET's body diode, about
    0.75 V, for the first 25-140 ms): fine at 6 W from a 5.2 V pack and at 10 W from a
    6.3 V pack; **a nearly empty pack (4.4 V) cannot take over more than about 3 W and
    the hub restarts**. Harmless while the host link is USB; to revisit with Bluetooth
    (O12).
  - Plug-in: the load runs through the USB switch's body diode for about 7 ms
    (lowest `SYS` 3.9 V at 10 W), then the switch closes. With a pack above 5 V the
    `SYS` capacitors push about 1 A back into the host for under 0.1 ms.
  - A host and cable outside the USB limits (4.75 V behind 0.35 Ohm, 12 W): the
    sources still flip, or the hub restarts without a pack. The firmware lowers the
    LED cap when `USB_PRESENT` drops under load (§4). Not modelled: the KTS1693
    limit (8 ms, then off for 200 ms), the converter's soft start.
- **Pack priority: lowest module first** (user, 2026-11-13), in hardware, no
  firmware. Inputs 1-4 pass a second CSD25402Q3A after the ideal diode. It is on
  only while no healthy pack sits below; otherwise that pack waits behind the FET's
  body diode (about 0.7 V handicap) and takes over with no gap when the pack below
  is pulled or empties. "Healthy" is one TPS3840PL43 per pack (inputs 2-5) on the
  pack through 100 k / 1 uF, with **910 k** from its VDD to its output: it drops out
  at about 4.3 V (4.3-4.5 V over tolerance) and re-arms only above about 5.0 V
  (4.9-5.2 V), so an emptied NiMH pack (rests at 4.8 V or less) does not bounce back
  to "healthy" when its load is removed, and a charged pack (5.2 V or more) is
  recognised; an emptied pack then shares with the packs above. A Schottky from GND
  to each supervisor's VDD protects it from a pack put in reversed.
- **Simulated at the M1 review** (`python3 tools/sim_priority.py`, ngspice, three
  inputs, decks in `build/sim/`):
  - *Empty slots read as healthy without a bleeder.* The LM74610's reverse leakage
    (60 uA typ at 13.5 V) lifts an empty input to the battery rail, its supervisor
    then reports "healthy" and the pack above stays behind its body diode for good.
    Fix: **22 k bleeder on pack inputs 2-5, switched by `+3V3`** (two DMN63D8LDW), so
    it costs nothing while the hub is off and about 0.25 mA per pack while it runs.
  - Active pack pulled (0.5 W and 5 W load): no gap; the pack above carries the load
    through the body diode for about 15-25 ms (lowest rail 3.9 V at 5 W), then its
    FET turns on. On the real board the LM74610 can hold the pulled input up for up
    to about 1.2 s (charge-pump capacitor) before the bleeder wins; the body diode
    carries the load for that time (about 1 W at 1.3 A, harmless).
  - Pack emptying under 0.3 W and 2.5 W: one clean hand-over at 4.3 V, no chatter;
    in the last stretch the packs above already help through their body diodes.
  - Start-up from a single pack in any slot, 4.6 V or 5.2 V: its FET turns on.
  - Load steps up to 10 W with aged packs (0.9 Ohm): no bouncing, because the packs
    above share through the body diodes before the active pack reaches 4.3 V.
  - A 4.9 V pack put in below a running pack is not preferred (stays idle until the
    pack above falls under it); a 5.3 V pack takes over after about 0.25 s.
  - With the M1 task 5 parts (8 mOhm ideal diode, 380 uF, loads to 18 W): same
    results; at 15-18 W three packs share (about 2.0 / 1.7 / 0.4 A) with one clean
    hand-over and no bouncing.
  Limits, accepted: alkaline packs recover to about 4.9-5.1 V at rest and can swap
  back in for a while after dropping out (gap-free, it just uses them up); a
  half-used pack put back in is not preferred; idle drain of the priority stages is
  about 3-6 uA per pack; the LM74610 runs the pack through the FET's body diode for
  about 2 % of the time (25 ms every 1.2 s, about 0.5 V dip on the battery rail).

## 3b. Sizing (M1 task 3, 2026-11-13)

From the datasheets in `build/ds/` (tables with sources were gathered by look-up
agents and spot-checked). "Graph" = read from a datasheet plot.

- **Loads at 5 V.** SK6812MINI-E: 12 mA per colour, so 36 mA per LED at full white
  and 1 mA dark: `left` 1.30 A, `right` 1.87 A, `numpad` 0.79 A, all 110 LEDs 3.96 A;
  0.11 A with the rails on and the LEDs dark. Expander 1 mA, port-board regulator
  0.06 mA. Pico 2 W: not in its datasheet, 0.1 A allowed, to measure at M4.
- **Module cable and port.** Receptacle: 4 VBUS and 4 GND contacts at 1.25 A, other
  contacts 0.25 A; a 3 A cable drops at most 0.25 V on VBUS and 0.25 V on GND (Type-C
  figures from memory, not from a file). TPS25810: limit 3.16 / 3.40 / 3.64 A at the
  3 A setting, 37 mOhm max. At `right`'s 1.87 A the module still sees about 4.5 V;
  LEDs work down to 3.7 V and the AP2112K (0.4 V dropout at 0.6 A) needs 3.7 V.
  Ground shift up to 0.16 V, harmless for 3.3 V SPI.
- **LED rail switch (key boards).** TPS22918: 2 A at 70 C, 59 mOhm max; firmware
  caps `right` at 1.8 A.
- **Ports stay at 3 A and the hub rail is raised to 3 A or more (user, 2026-11-13).**
  The TPS630701 was a 2 A part, so three 3.4 A ports could pull the rail down (the M1
  review's one must-fix finding). **Drawn at M1 task 5: TPS552892** (§3a): average
  inductor current limit 7 / 8 / 9 A, so about 4.4 A at 5 V from 3.6 V in and about
  6 A from 5 V in (calculated at 88 %, before heat: about 1.3 W in the chip at 3.5 A
  from 3.6 V, 43 K/W); peak inductor current 5.8 A at 3.5 A out. Efficiency at 5 V
  out and 5 V in (graph, PFM): about 80 % at 10 mA, 88 % at 50 mA, 91 % at 100 mA,
  96 % at 1-3 A; quiescent 0.76 mA (0.86 max) against the TPS630701's 0.05 mA, so idle
  battery life drops by roughly 15 % (accepted, to measure at M4).
- **What the sources can give.** USB: at most 3 A from the host, about 2.7 A at the
  rail for all ports together. **One AA pack: about 8-10 W, not 3 A at 5 V**: a pack
  with its path is about 0.3-0.5 Ohm, so it cannot deliver more than V^2 / 4R (9.7 W
  at 4.4 V and 0.5 Ohm, about 17 W at 5.2 V and 0.4 Ohm, and only with `SYS` near
  2.6 V); the earlier "3.8 A from one pack" was wrong. Several packs share through
  the priority FETs' body diodes once the active pack sags by 0.7 V (simulated to
  18 W on three packs). So the battery LED cap is a firmware value that follows the
  measured pack voltage: about 8 W of input per pack as the starting point (O3).
- **Host port (`hardware/usb-port`, changed at M1 task 5).** KTS1693 **ISET 2.87 k**:
  limit 3.17 / 3.48 / 3.80 A (10000 / R, +/-9 %, 0-70 C; was 4.99 k, 2 A); switch
  13 mOhm max, 0.16 W at 3.5 A. **OC_MODE open** = high through the internal 5 M
  pull-up = auto-restart (limits for 8 ms, off, retries after 200 ms; was latch-off).
  **OVLO stays external, 100 k / 26.4 k 0.1 %**: trips at 5.56-5.93 V. The rev 8 value
  (27.4 k, from 5.40 V) could cut off a legal 5.5 V host; the internal threshold
  (5.77-6.13 V) is above the USBLC6-2's 6 V breakdown (from memory, check at the
  parts list). The cable header carries VBUS and GND on three JST GH contacts each,
  1 A per contact: 3 A is its limit. The board file still has rev 8's layout (M2).
- **Battery path.** Pack fuse **MF-LSMF500/16X (user, 2026-11-13)**: holds 5.0 A at
  23 C, 4.2 A at 40 C, 3.3 A at 60 C, trips at 10 A, 25 mOhm max, 2920 size (was
  MF-MSMF125, 1.25 A, which capped the battery at about 0.8 A at 5 V). Note: it needs
  10 A to trip, which NiMH cells deliver into a short and alkalines may not. Chain
  seam: pack lines doubled, Mill-Max spring pins 4.8 A or more each (derated), 20 to
  40 mOhm; headers 4.6 A or more per pin. Battery switch CSD25402Q3A: 8.9 mOhm max at
  -4.5 V, 15.9 at -2.5 V; about 0.3 W at 4.5 A, package limit 35 A. Ideal-diode FET
  SQ4184EY: 5.6 mOhm max at 4.5 V gate drive, VGS +/-20 V, threshold 2.5 V max against
  the LM74610's 5.2-6.3 V drive; at 4.5 A about 0.15 W in the channel plus 0.1-0.3 W
  for the 2-8 % of the time the LM74610 leaves it on the body diode (80 K/W).
- **Core layer.** +5 V over two stack pins feeds only the Pico (MBR120: 0.28 V at
  0.1 A, VSYS about 4.7 V). The connector layer takes a few mA from the Pico's 3V3
  (limit 300 mA).
- **Firmware budget (O3), until measured:** LED current is capped from what the
  source offers: host 0.5 / 1.5 / 3 A (CC) less the Pico and conversion loss; on
  battery the cap follows the pack voltage (about 8 W in per pack; the fuse's 4.2 A
  is the hardware ceiling).

## 4. Firmware

- Go, built with TinyGo, one program, on the hub's Pico 2 W. Based on
  `github.com/sago35/tinygo-keyboard` (layers, Vial, encoder) with our own matrix
  source that scans the SPI expanders; a small MCP23S17 driver to write and upstream.
- **Rollover:** hardware is n-key. TinyGo's USB keyboard report is to be checked
  at M4; if it is 6-key only we add an n-key report and send it upstream.
- Dial: turn = volume, read through the `right` expander at the scan rate.
- **Rules from the hardware (M1 review):** on `right`, write IOCON.HAEN to address 0
  before any read (both chips answer to address 0 until HAEN is set); set IOCON.ODR
  before enabling interrupts (INTA is push-pull at power-on and the two are tied);
  never assert two CS lines at once (the port buffers share MISO); disable the
  digital input on the three ADC pins; pin data in `firmware/hub-pinmap.json`.
  Power (M1 task 5): when `USB_PRESENT` falls, cut the LEDs to the battery cap at
  once (interrupt); if it falls while the host is still there (sagging host, or the
  port's 3.5 A limit cycling every 200 ms), lower the USB cap before trying again.
- Bluetooth (M6): `tinygo.org/x/bluetooth` pairs only on Nordic chips today; we add
  what the Pico 2 W needs and contribute it.

## 5. What is reused from rev 8

- Hub tower concept and CAD script (`archive/rev8/mech/hub/build_hub.py`), stacking
  layers, pogo/magnet battery seams, front buttons, expansion port.
- Battery modules and power path as specified in rev 8.1 (§3).
- `hardware/usb-port` (USB-C receptacle, KTS1693, CC sense, ESD), now the hub's
  host port; `hardware/dial`; `hardware/lib/kiswitch`; the PEC11R footprint.
- Tooling: `tools/schlib.py`, `tools/gen_kicad.py`, `tools/kicad-check.sh`.
- Mechanical decisions: ASA on FDM, Ruthex M2 inserts, magnet seams, 3M Bumpon feet.

Still retired: MDBT50Q, MSPM0G3505 module controllers and their register map,
TCA9548A, I2C-over-USB-cable comms boards, ZMK. Files are brought out of
`archive/rev8/` only when a milestone reworks them; archived KiCad library paths do
not resolve in place.

## 6. Milestones

See [`roadmap.md`](roadmap.md). Hardware first (user, 2026-11-13).

## 7. Open items

- O1 closed 2026-11-13: full-featured USB-C cable, receptacle on a swappable port
  board, 2x6 bay header on the key boards (D3, §1). Open under it, for M1: the wire
  plan checked against the USB-C cable wiring, the CC detect and mis-plug
  protection, how ports and cables are marked.
- **O2** SPI at 4 MHz over a 1 m full-featured USB-C cable: prove on the bench at M4
  before PCBs are ordered, or order after M4.
- **O3** LED current caps per source: sized at M1 (§3b), measured at M4.
- O11 closed 2026-11-13: 5 V rail on a TPS552892, drawn and reviewed (§3a, §3b).
- **O12** USB unplug onto a weak pack restarts the hub above about 3 W (the pack's
  ideal diode needs 25-140 ms to wake, §3a). Measure at M4; matters from M6
  (Bluetooth keeps the link after an unplug). Ways out then: firmware keeps the
  LEDs low while a pack is weak, or an always-on ideal-diode controller.
- **O6** Bluetooth on the Pico 2 W (roadmap M6); idle current on batteries to measure.
- O7 closed 2026-11-13: SK6812MINI-E chain (D10, §2). Open under it: a European source for the LED.
- O8 closed 2026-11-13: 2x8 chain, five pack inputs, lowest-first priority (§3a). Priority hand-over simulated and the re-arm level tuned at the M1 review (§3a).
  Open under it: pogo parts for 2x8.
- **O9** n-key USB report in TinyGo (M4).
- **O10** cable-free pods: they take the port board's place in the bay (2x6 header,
  two M2 screws; D3); bay size and header position frozen at M1; the pods themselves (controller, radio link to the hub, latency
  over radio) come after M6.
- O4, O5 closed 2026-11-13 (archive move; Pico 2 W, test image compiles for `pico2-w`;
  RP2350 erratum E9 avoided by pull-up scanning, which the expander's pull-ups give).
