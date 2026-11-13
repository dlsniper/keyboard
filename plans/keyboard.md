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
- **Cable, hub to each module, about 8 wires**: SCK, MOSI, MISO, CS, INT, LED data,
  5 V (switched LED/logic rail), GND; whether 3.3 V travels or is made on the module
  is an M1 detail. Connector and cable: open (O1); a plain USB-C 2.0 cable does not
  have enough wires.
- **Cable-free modules are a wanted upgrade (user, 2026-11-13), not rev 9's first
  build.** The module's cable connector doubles as a **pod socket**: a later pod
  (its own controller with radio, its own AA pack and converter) plugs in where the
  cable goes and becomes the SPI master of that module's expander. Key boards stay
  the same in both cases; the connector is chosen with this in mind (O1, O10).
- The hub has a rear **expansion port**; each key board keeps a few spare expander
  pins on a header.

## 2. Modules

| | left | right | numpad |
| --- | --- | --- | --- |
| Keys (D1, 2026-11-13; final at D2) | 36 | 52 + dial push | 22 |
| Matrix (rows x cols), by physical position | 6 x 7 | 6 x 11 | 6 x 4 |
| Reader | 1 x SPI expander (13 pins used) | 2 x SPI expander (17 matrix + 2 dial) | 1 x SPI expander (10 pins) |
| LEDs (SK6812MINI-E, D10) | 36 | 52 (none under the dial) | 22 |
| Dial | none | PEC11R, 24 detents, push switch in the matrix, on the separate dial board | none |

- Switches: MX, Kailh hotswap sockets (CPG151101S11). One `1N4148W` per key, so
  every module has full n-key rollover.
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
  numpad square. To be checked against the K860 print (D2). The file is independent of
  where the controller sits.
- Stabilisers: Cherry MX plate/PCB 2U footprint from the vendored kiswitch subset.
- Plate: 1.5 mm FR4, no copper (as rev 8).
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
- Power path in the hub, starting from rev 8.1's design (ideal-diode OR of the
  packs, USB priority switch, under-voltage cut-off at about 1.0 V per cell, 5 V
  rail converter, pack voltage read by the controller). It was specified but never
  drawn; M1 draws it, reworked for 5 packs and the Pico 2 W.
- The hub switches each module's rail, so LEDs draw nothing when off and on battery.
- Firmware caps LED current from what the source offers (USB 500 mA / 1.5 A / 3 A
  from the CC pins; battery: its own cap). Values by measurement (O3).
- Batteries only pay off with Bluetooth (M6). Expect days to weeks per pack on a
  Pico 2 W, to be measured; the swappable core layer is the way out if that is not
  enough.

## 4. Firmware

- Go, built with TinyGo, one program, on the hub's Pico 2 W. Based on
  `github.com/sago35/tinygo-keyboard` (layers, Vial, encoder) with our own matrix
  source that scans the SPI expanders; a small MCP23S17 driver to write and upstream.
- **Rollover:** hardware is n-key. TinyGo's USB keyboard report is to be checked
  at M4; if it is 6-key only we add an n-key report and send it upstream.
- Dial: turn = volume, read through the `right` expander at the scan rate.
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

- **O1** module cable and connector, about 8 wires (D3, M1).
- **O2** SPI at 4 MHz over a 1 m cable: prove on the bench at M4 before PCBs are
  ordered, or order after M4.
- **O3** LED current caps per source: sized at M1, measured at M4.
- **O6** Bluetooth on the Pico 2 W (roadmap M6); idle current on batteries to measure.
- O7 closed 2026-11-13: SK6812MINI-E chain (D10, §2). Open under it: a European source for the LED.
- **O8** five battery modules: chain connector and power path rework from rev 8.1's three.
- **O9** n-key USB report in TinyGo (M4).
- **O10** cable-free pods: mechanical mount and power pins on the module connector
  reserved at M1; the pods themselves (controller, radio link to the hub, latency
  over radio) come after M6.
- O4, O5 closed 2026-11-13 (archive move; Pico 2 W, test image compiles for `pico2-w`;
  RP2350 erratum E9 avoided by pull-up scanning, which the expander's pull-ups give).
