# Split K860-alike, rev 9: wired, Go firmware

Three-piece MX keyboard styled on the Logitech ERGO K860: `left` (alphas), `right`
(alphas + arrows + nav + dial), `numpad`. **Rev 9 (2026-11-13) restarts the
electronics** around what TinyGo can run today. The typing part of rev 8 is kept;
the hub tower, radio, battery chain and module controllers are archived
(tag `rev8-archive`, files under `archive/rev8/`).

Decided by the user 2026-11-13: wired USB first; a socketed Raspberry Pi Pico 2 W per
module; SK6812MINI-E per key; archive rev 8 and write this short spec; the Pico on a
strip above the top row; a USB-C port board on `right`; ANSI layout.

Priorities, unchanged: repairable and user-friendly before compact; modular and
upgradeable; FDM-printed ASA case; parts from Mouser Europe / European distributors.

## 1. Topology

```
 host --USB-C--> [USB port board] --> [right: Pico, primary] --link--> [left: Pico]
                                              |
                                              +----------link--> [numpad: Pico]
```

- `right` is the primary: USB HID to the host, keymap, layers, Vial.
- `left` and `numpad` are satellites: scan their own matrix, report key events to
  the primary over UART (tinygo-keyboard's split support). The Pico's two UARTs
  give exactly two satellite links.
- Every key board is the same kind of board: sockets, diodes, LEDs, a Pico on pin
  sockets, a link connector. No hub, no cells, no power path. The Pico 2 W's radio
  is unused in rev 9 (O6).
- **The Pico sits on a strip of the key PCB behind the top row** (about 25 mm deep),
  USB end towards the rear edge, antenna at the board edge. Each case has an opening
  for the Pico's micro-USB and a way to press BOOTSEL, so any module can be flashed
  on its own.
- **Host port: a USB-C port board on `right`**, swappable, cabled to the key board.
  It carries the receptacle, protection and CC current sensing, feeds 5 V to the
  LED rail and the links, and passes data to the Pico through a short internal
  micro-USB lead. Starting point: rev 8's `hardware/usb-port`.
- A link carries 5 V, GND, TX, RX. Connector and cable: open (O1).
- Each key board brings its spare Pico pins and 5 V / 3V3 / GND to an **expansion
  header**, so a wireless or other module can be added later without a respin.

## 2. Modules

| | left | right | numpad |
| --- | --- | --- | --- |
| Keys (D1, 2026-11-13; final at D2) | 36 | 52 + dial push | 22 |
| Matrix (rows x cols) | 6 x 7 | 6 x 9 | 6 x 4 |
| Controller | Raspberry Pi Pico 2 W (RP2350 + CYW43439), socketed; the Pico 2 and Pico fit the same sockets | same | same |
| LEDs | 36 x SK6812MINI-E | 52 (none under the dial) | 22 |
| Dial | none | PEC11R, 24 detents, push switch in the matrix, on the separate dial board | none |
| GPIO used / 26 | 13 matrix + 1 LED + 2 UART = 16 | 15 matrix + 2 dial + 1 LED + 4 UART = 22 | 10 + 1 + 2 = 13 |

- Switches: MX, Kailh hotswap sockets (CPG151101S11). One `1N4148W` per key.
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
  numpad square. To be checked against the K860 print (D2).
- Stabilisers: Cherry MX plate/PCB 2U footprint from the vendored kiswitch subset.
- **Antenna keep-out**: no copper, sockets or metal under and around the Pico 2 W antenna
  end, per the Raspberry Pi datasheet (dimensions taken from it at M1). The on-board LED
  hangs off the radio chip, not a GPIO; status indication uses the key LEDs.
- LED data: one GPIO per module through a 3.3 V to 5 V buffer (74AHCT1G125 class),
  LEDs chained in a serpentine, row by row.
- Plate: 1.5 mm FR4, no copper (as rev 8).

## 3. Power

- USB bus power only, entering at the USB-C port board on `right`.
- Rails: port board 5 V -> `right`'s LED rail and Pico; -> each link through a
  resettable fuse -> the satellite's LED rail, and its Pico's `VSYS` through a
  Schottky, so a satellite can be on its own USB and the link at once.
- 110 LEDs at full white would draw several amps. **Firmware caps total LED
  current** from what the host offers: the port board reports 500 mA, 1.5 A or
  3 A from the CC pins. At 500 mA roughly 250-300 mA is left for light. Cap values
  per level are set by measurement (O3); link wire, connector and fuse are sized
  for the 3 A case.

## 4. Firmware

- Go, built with TinyGo, on `github.com/sago35/tinygo-keyboard` (matrix scan, rotary
  encoder, layers, UART split, Vial). One `main` package per module under
  `firmware/`.
- LEDs with the `ws2812` driver from `tinygo.org/x/drivers`.
- Dial: turn = volume. Layer/profile indication on the number row is a rev 9
  stretch goal; rev 8's 9 BLE host profiles are gone with the radio.

## 5. What is reused from rev 8

- Layout intent and key counts (§2), dial board (`hardware/dial`, drawn and laid out).
- `hardware/lib/kiswitch` (hotswap + stabiliser footprints), the PEC11R footprint.
- Tooling: `tools/schlib.py`, `tools/gen_kicad.py`, `tools/kicad-check.sh` (schematics
  generated from Python, checked headless).
- Mechanical decisions: ASA on FDM, Ruthex M2 inserts, magnet seams, 3M Bumpon feet.
- `hardware/usb-port` (USB-C receptacle, KTS1693 over-voltage switch, CC sense, ESD;
  ERC clean in rev 8): the base for rev 9's port board, to be reworked at M1.

Retired (kept only in the archive): hub tower and its CAD, MDBT50Q, MSPM0G3505
module controllers and register map, TCA9548A, comms/socket boards, AA battery
modules and the rev 8.1 power path, IS31FL3733, ZMK. Their folders, generator scripts and sims were moved to `archive/rev8/`
(2026-11-13); KiCad library paths inside them no longer resolve, use the
`rev8-archive` tag to open them.

## 6. Milestones

See [`roadmap.md`](roadmap.md): M0 layout, M1 schematics, M2 PCBs, M3 case,
M4 firmware bring-up, M5 firmware, M6 wireless. Hardware first (user, 2026-11-13).

## 7. Open items

- **O1** link connector and cable (TRRS, JST, USB-C-as-cable, other): decide at M1.
- **O2** tinygo-keyboard with two UART satellites, and a primary-to-satellite
  channel for lighting commands (stock UART split reports keys one way): prove at M4.
- **O3** LED current caps per host level (500 mA / 1.5 A / 3 A): sized for 3 A at M1, cap values measured at M4.
- **O4** closed 2026-11-13: retired folders moved under `archive/rev8/`.
- **O5** closed 2026-11-13: **Pico 2 W** (user). A test image (matrix + encoder + two UART
  satellites + ws2812, tinygo-keyboard v0.9.0, TinyGo 0.44.0) compiles for `pico2-w`, `pico2`
  and `pico`; not yet run on hardware. RP2350 pull-down erratum (E9): the matrix is wired for
  pull-up scanning, which tinygo-keyboard supports as an option.
- **O6** wireless (roadmap M6). `tinygo.org/x/bluetooth` v0.17.0 pairs only on Nordic chips
  today; when we get there we add what the Pico 2 W needs and contribute it upstream
  (user, 2026-11-13). Needs a battery design, which rev 9 does not have.
