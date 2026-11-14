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

- **Hub tower** (114 x 114 mm ASA stack on the desk since M2 session 7, user, 2026-11-14; rev 8 concept, was 100 x 100): top to
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
  an expander pin; the 24-pin receptacle (**Amphenol 12401548E4-2A**, horizontal, hybrid; M2, user, 2026-11-13: the JAE part drawn at M1
  was an upright type) sits on the small port board.
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
  **Port board layout (M2 session 6, 2026-11-14):** `hardware/port-module`, 30 x 23.5 mm, **4 copper layers (user,
  2026-11-14)** like `hub-conn` (top parts and signals, inner 1 GND plane, inner 2 +5V and signals, bottom signals):
  the receptacle carries every signal twice, on opposite sides, and each pair is joined across it. Receptacle at the
  rear edge midway between the two screws, socket underneath, all SMD parts on top. Placed by `tools/pcb_port.py`
  (which checks its socket pins and holes against the bays of the three routed key boards), routed by
  `tools/route_hub.sh port-module`; DRC 0 errors, 0 unconnected, parity 0. +5V runs on inner 2 (**1 oz, user, 2026-11-14**, as `hub-conn`): a 1 mm bar for 2 mm at the receptacle, then 2 mm and wider to the header.
- **Cable-free modules are a wanted upgrade (user, 2026-11-13), not rev 9's first
  build.** The module's cable connector doubles as a **pod socket**: a later pod
  (its own controller with radio, its own AA pack and converter) plugs in where the
  cable goes and becomes the SPI master of that module's expander. Key boards stay
  the same in both cases: the pod replaces the port board on the 2x6 bay header and
  feeds 5 V and 3.3 V through it (O10).
  **User, 2026-11-14 (M3 session 1): the cable-free (wireless) variant of the modules must be part of the final
  hardware design before anything is built and tested**, beside the wired one: pod electronics, its board and its
  place in the shell are designed before the order (D7). The software stack is left open until the hardware
  exists. **Decided at M3b session 1 (2026-11-14): §2b** (radio-only pod with an nRF52840 module, power board and
  4 / 6 AA in a rail along the rear and outer side, the same pod as the hub's receiver); nothing is drawn yet.
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
  **Decoupling places (M2 session 9, 2026-11-14, from the PCB review):** each LED's 100 nF sits between the LED and
  the key's diode, its +5V pad 2.1 mm from the LED's VDD pad centre to centre (0.6 mm between the pads) and its
  ground on its own via 1.1 mm away, in line with the switch's peg hole (**user, 2026-11-14**; it was west of the
  LED on 9.5 mm of track; one capacitor on `left`, CL32, found no room for its via and is grounded by the pours
  only); the expander's 100 nF sits in front of its VDD / VSS pins (9, 10), each pin on a 3.2 mm track straight to
  its pad (was 13 mm away).
- Stabilisers: Cherry MX plate/PCB 2U footprint from the vendored kiswitch subset.
- **Plates (M2 session 8, 2026-11-14): `hardware/plate-{left,right,numpad}`, 1.6 mm FR4, no copper** (user, 2026-11-14:
  1.6 mm, the stock thickness, inside Cherry's 1.5 +/- 0.1 mm; was 1.5 mm as rev 8). Generated by `tools/pcb_plate.py`
  from `layout/keys.json` and the key board outline: **the key board's own outline with the port bay cut away to the
  inner edge (user, 2026-11-14)**, so plate and key board share the strip and front screw places (5 on `left` and
  `right`, 4 on `numpad`); 14.0 mm square switch cut-outs with 0.5 mm corners (Cherry's figure for a machined plate;
  the test cell's 14.1 mm was for FDM), Cherry stabiliser cut-outs with the wire notch on the large-hole side, a slot
  over the spare-pin header, a 17 mm opening at the dial (provisional until the dial board is mounted, M3). Plate top
  5 mm above the key board. The script checks every cut-out against the routed key board's footprints and stops on
  a mismatch; least web 1.44 mm (switch to stabiliser cut-out). DRC 0 errors, 0 warnings.
- **Key board outline (M2, user, 2026-11-13):** four straight edges with 3 mm fillets (outer, front parallel to the
  bottom row, inner along the split, rear parallel to the F-row chord), 4 mm beyond the caps at the sides, 6 mm at
  the front; all SMD parts on the back; provisional M2 holes, final with the case (M3). On `right` the split edge mirrors
  left's angle (user, 2026-11-13), which leaves a wedge of empty board in front of N / Space; the port bay is the same on
  every module (one port board), only its place in the strip mirrors. **Board house (D6): JLCPCB
  makes and assembles.** Placement is generated by `tools/pcb_keys.py`, routing by
  `tools/route_keys.py` (one scripted pattern per key cell, the rear strip autorouted; all three key boards routed
  2026-11-13, DRC 0 with parity). The rows start at the west end on every module, so the LED supply enters along the
  west edge: on `right` that is the split edge, and its LED rail switch sits beside the bay instead of mid-strip.
- **Key LEDs: SK6812MINI-E chain (D10, user, 2026-11-13)**, one per key, reverse
  mount through a 3.4 x 3.0 mm board window south of the switch, one data wire per
  module. Chain order (M2): every row west to east, top row first; the index of each key's LED is in `layout/keys.json`. Chosen over rev 8's IS31FL3733 matrix (I2C would add 2-3 cable wires, no
  TinyGo driver, 28 matrix nets per module, chip must not be power-gated). Costs
  accepted: about 1 mA per LED with the rail on and the LEDs dark (datasheet typ,
  about 110 mA for 110 LEDs), so **the hub switches the LED rail off whenever the
  LEDs are off**; a dead LED cuts the chain behind it; the 3.3 V data line needs a
  5 V level shifter at the hub (74AHCT125 class; VIH is 0.7 x VDD). Driver:
  `tinygo.org/x/drivers/ws2812` (PIO on RP2350). Source: not found at Mouser so far
  (Adafruit 4960 packs, or OPSCO parts from another distributor); to settle in the
  M1 parts list.

## 2a. Key-module shell (M3 session 1, 2026-11-14)

`mech/case/build_case.py` (FreeCAD), fed by `tools/case_dump.py` (reads the routed key board and the plate). Done for
`numpad`; `left` and `right` use the same script (the bay parts are built in the bay frame).

- **Held by screws from the top into inserts (user, 2026-11-14)**: a flat-bottomed ASA tray (floor 2.4 mm, 4.0 mm
  cavity under the board, wall 2.4 mm with 0.3 mm to board and plate, wall top 1 mm above the plate); the key board
  lies on bosses with Ruthex M2 inserts under **its existing M2 holes, which are now final** (no board changed) and
  on 4 mm support posts at the key cell corners; a 3.4 mm printed spacer and an M2 x 10 at each plate hole.
- **Port bay**: the port board stands 11.04 mm above the key board (header body + 8.5 mm socket) on two printed
  sleeves; a cover over the bay (skirts between the F-row caps and the port board, and over the plate's notch edge)
  with the cable opening (13.5 x 7.5 mm, takes the plug's overmould) in its rear wall; one M2 x 22 at each bay hole
  holds cover, port board, sleeve and key board in the tray's insert. Cover top 14.6 mm above the plate, about 3 mm
  under the cap tops. The cover is the wired variant; the pod variant (§1) replaces it.
- **D8 (user, 2026-11-14)**: **negative tilt by screwed-on front foot bars, swappable, 4 and 7 degrees**, the tray
  bottom stays flat (flat = no bar; two inserts set from below in the tray); **tenting by a separate printed base
  per alpha half** (the numpad stays untented; angle to be taken from the user's K860, about 7 degrees from memory);
  **palm rest separate and attachable**, one per alpha half, none on the numpad.
- Feet: four 3M Bumpon recesses (8.4 mm); the tilt bars carry their own.
- **Hub: `hub-core` and `battery` stay 94 mm (user, 2026-11-14, final)**; the room to the 114 mm shell is for walls,
  seam magnets and grips.

## 2b. Wireless variant of the modules (M3b session 1, user, 2026-11-14)

Hardware only; the software stack (link protocol, pairing, firmware of pod and receiver) is open until the boards
exist. Decided through the options UI, the numpad shell shown in FreeCAD. **No key board, hole, outline or bay
changes: no board is placed or routed again.** Nothing below is drawn yet; parts marked "candidate" are from memory
and are checked against their datasheets when the schematics are written.

```
 cells (4 or 6 AA, in the rail)                      radio pod, in the bay (2 screws)
   |                                                +---------------------------------+
   v                                                |  nRF52840 module                |
 +-- power board (in the rail, behind the bay) --+  |   SPI master, INT (wake), CS    |
 | fuse, reverse protection                      |  |   LED data -> 5 V level shifter |
 | 3.3 V buck, always on, uA idle  --- +3V3 -----+--+-> 3.3 V                         |
 | 5 V buck-boost, about 0.5 A     --- +5V_LED --+--+-> 5 V                           |
 |   enable (off by default)      <--- EN_5V ----+--+   USB-C (USB 2.0): flashing     |
 | pack divider                    --- VBAT_S ---+--+   SWD pads, reset button        |
 +-----------------------------------------------+  +----------- 2x6 socket ----------+
              6-wire lead                                             |
                                                      frozen 2x6 bay header (key board)
                                                      or the hub's carrier board
```

- **Radio pod = the bay board, radio only (user)**: a soldered **nRF52840 module** (MDBT50Q class, candidate) on a
  board of the port board's size and holes (30 x 23.5 mm, 2x6 socket underneath, two M2 screws), so a dead radio is a
  two-screw swap of a small board. On it: the module, a single-gate 5 V level shifter for LED data (fed from the
  5 V pins), CS and INT pull-ups, series resistors, the lead connector, a **16-pin USB-C receptacle on the module's
  own USB for flashing and a console (user; it does not power the module and does not make it wired)**, SWD pads,
  a reset button. The pod is the SPI master of the module's expander(s) and wakes on the INT line. Header pins as
  the port board (§1): 5 V and 3.3 V are fed INTO the key board from the lead.
- **Power board at the cells (user)**: converters, fuse and the pack input are on a second small board in the
  battery rail, behind the bay; a 6-wire lead joins it to the pod (+5V_LED, +3V3, 2 x GND, EN_5V, VBAT_SENSE). A
  dead converter is a swap of that board only. Input **4.0 to about 10 V, so the same board takes 4 or 6 cells**:
  3.3 V by an always-on buck with microamp idle current (candidate TPS629210), 5 V for the LED rail by a
  buck-boost that is off unless the pod enables it (candidate TPS63070 family, as the hub's first converter).
- **Cells (user): 6 x AA on `left` and `right`, 4 x AA on `numpad`**, NiMH (alkaline tolerated), charged outside
  the keyboard, as the hub's packs. The user first asked for cells under the modules; shown and withdrawn: an AA
  is 14.5 mm and the tray has 4 mm under the board, so cells under the keys raise every key by about 19 mm.
- **Place (user): a battery rail along the rear edge and the outer side of each module**, at desk level, 19 mm wide
  and 19 mm high (lower than the bay cover, key height unchanged), cells in single file, changed from above. The
  rear part ends behind the bay, so the lead to the pod is short on every module. `numpad`: 3 cells along the
  right side, 1 cell and the power board (about 48 x 14 mm, provisional) along the rear; the module grows from
  88.6 x 154.4 to 107.6 x 173.4 mm. The pod's service port faces the rear above the rail (bay board top 20.64 mm,
  rail top 19 mm; the plug's overmould needs a notch of about 0.5 mm in the rail's lid). Preview:
  `mech/case/pod_preview.py` (envelopes only). **Found, open: `left` takes only 5 cells in single file** (side 3,
  rear 2 beside the power board; its rear edge is 141 mm); the sixth needs a doubled piece of rail or another
  place for the power board. `right` (241 mm rear edge) takes 6.
- **LEDs on battery (user): capped.** The 5 V converter is sized for about 0.5 A (2.5 W) and is off by default;
  the LED rail is on only while LEDs are lit (the dark chain alone draws 22 / 36 / 52 mA). Estimates, to measure:
  months per charge without LEDs; at 5 mA per LED about 15 h on `numpad` (4 cells) and about 9 h on `right`
  (6 cells). Full brightness needs the cable.
- **Hub side (user): the same radio pod on a carrier board** on the core's 2x5 expansion header (found: it
  carries +3V3, +5V, GND and GP0 / GP1, which are also UART0; SP1-SP4 reach no Pico pin). The carrier is passive:
  2x5 socket, a 2x6 header and two M2 holes as a key board's bay, the pod's 3.3 V pin fed from the Pico, UART on
  two of the pod's SPI pins, the spare pin tied low so the pod knows it sits in the hub. `hub-core` and `hub-conn`
  do not change; the Pico's own radio stays free for the host link (M6). Chosen over the Pico 2 W's radio
  (Bluetooth only, 7.5 ms connection interval at best, one radio for three pods and the host) and over a Nordic
  core board. One radio board design in four places.
- **One design for all three modules**: one radio pod, one power board; the rail print and the cell count differ
  per module.
- **Decided at M3b session 2 (user, options UI, 2026-11-14)**: **on / off slide switch on the converters' enables**
  (carries no load current); **cells in printed pockets with bought spring / button contacts**, wired in a printed
  channel (slots need a fit print); **lead = JST GH, 6 pins, 1:1**; **32.768 kHz crystal fitted, and the pod board
  made roomier** (user's own wording: easy to work on, good properties; how it grows is decided at the board session
  with the shell in FreeCAD: the bay is 30 mm wide between the screws' key-board parts, so the room is to the rear,
  over the rail, which also gives the antenna its free edge). **Sixth cell on `left`: the user proposes a wider left
  shell on its outer side**, the strip beside the keys kept for later LEDs or buttons. My estimate, not modelled:
  about 20 mm more width makes the rear run three cells long (3 rear + 3 side); anything in that strip would be a
  small board on the spare-pin header, the key board stays as routed. To show in FreeCAD at left's shell (M3).
- **Schematics (M3b session 2): `tools/sch_pod.py`** writes `hardware/pod`, `hardware/pod-power`, `hardware/hub-radio`
  and `firmware/pod-pinmap.json`, then checks the netlists (bay socket against the key boards' table, the lead pin
  for pin on both boards, every module pin, IC pins against a second copy of the datasheet tables, the carrier
  against hub-core's expansion header). ERC 0 on all three. Datasheets read: TPS629210, TPS63070, TPS2553,
  MDBT50Q-1MV2, nRF52840, SN74AHCT1G125, AO3401A, MF-MSMF, JST GH, USB4085 (`build/ds/`).
  - **`pod`**: MDBT50Q-1MV2 with VDD = VDDH = 3.3 V (normal-voltage mode; the 32 MHz crystal and the REG1 inductor
    are inside the module). SPI on pins that are not "low frequency only": SCK P0.19, MOSI P0.21 (33 R each),
    MISO P0.20, CS P0.23 and INT P0.22 (100 k pull-ups), LED data P0.24 through a 74AHCT1G125 on the 5 V pins
    (100 R out, 100 k pull-down in), EN_5V P0.15, pack sense P0.04 (AIN2), status LED P0.06, hub detect P0.25
    through 1 k to bay pin 6, crystal on P0.00 / P0.01 with 12 pF. USB-C (GCT USB4085) on the module's USB: VBUS
    feeds only the USB regulator pin (2.2 R, 10 uF), 27 R in D+ / D-, Rd on both CC, USBLC6-2. **The pod must be
    powered from the lead or the hub to be flashed.** Debug: 2x5 1.27 mm Cortex header (my choice over bare pads:
    any debugger's cable fits), reset button. Lead J2: 1 +5V, 2 GND, 3 EN_5V, 4 VBAT_SENSE, 5 GND, 6 +3V3.
  - **`pod-power`**: pack on a 2-pin JST XH (my choice: 3 A contacts; the GH's 1 A is too little for the pack
    line), MF-MSMF110/16X fuse, AO3401A against a reversed pack (10 V Zener on its gate, 47 uF on the pack rail),
    slide switch C&K OS102011MA1QN1. **TPS629210** (27.4 k on MODE/S-CONF: VSET mode, automatic power save, output
    discharge; FB/VSET open = 3.3 V; 2.2 uH, 22 uF). **TPS630701** (fixed 5.0 V, power save, 1.5 uH, 2 x 22 uF +
    10 uF), enabled only by EN_5V (1 k, 100 k pull-down), **behind a TPS2553 with 49.9 k: the LED rail is capped at
    475-565 mA in hardware** (added by me: the converter alone would give 2 A and the lead's contacts carry 1 A).
    Pack divider 2.2 M / 680 k behind the switch. Test pads for the pack rail, 3.3 V, 5 V, GND.
    **Pack cut-off (review finding, added)**: a divider on the 3.3 V converter's precise enable turns the module
    off at 0.9 V per cell and on again at 1.0 V per cell; without it the converter runs a NiMH pack down to
    2.75 V. **Its top resistor depends on the cell count: 1 M for 4, 1.33 M for 5, 1.65 M for 6 (drawn)**: the one
    part that differs between modules (**session 3: replaced by a solder jumper, below**). Idle cost: the two dividers draw about 6 uA at 7.2 V. Off: 3 to 13 uA.
  - **`hub-radio`**: 2x5 socket onto hub-core's expansion header, a bay header, 10 uF. GP0 (UART0 TX) to bay pin 9
    (the pod's MISO pin), GP1 (UART0 RX) from bay pin 10 (its MOSI pin); bay pin 6 to GND; CS, SCK, INT to
    SP1-SP3 (no Pico pin today, for a later core board). **Hub firmware must not start I2C0 on GP0 / GP1 when the
    carrier is fitted** (`firmware/hub-pinmap.json` still lists them as I2C0; it is hub-core's file, not changed).
  - **Independent review (Opus, datasheets and netlists only)**: nothing wrong in pins, ratings or UART
    direction; 3 should-fix and 9 notes, all taken into the generator except two left as limits: the fuse holds
    only 0.85 A at 50 C, which is the pack current if the LED rail sits in its limit at a 4.0 V pack (firmware
    budget: 450 mA); `hub-pinmap.json` as above. Not checkable from the files: USBLC6-2 pinning (no datasheet on
    disk), whether the slide switch is break-before-make (its third contact is left unused, so it cannot short
    the pack either way), capacitor derating (no part numbers yet).
- **Boards (M3b session 3, 2026-11-14)**: `tools/pcb_pod.py` places `pod`, `pod-power` and `hub-radio`,
  `tools/route_hub.sh <board>` places, routes and checks each; DRC 0 errors, 0 unconnected, parity 0 on all three;
  fab outputs by `tools/fab.py`. **Decided by the user (options UI, numpad shell and rail shown in FreeCAD)**:
  - **Pod grows straight to the rear, over the rail: 30 x 50.7 mm** (bay frame a -15 .. 15, t 1.5 .. 52.2). Measured
    first: its parts need 735 mm2, the port board's 30 x 23.5 mm is 705 mm2, so one-sided at that size was never
    possible. Sideways was ruled out (the bay is at opposite ends on `left` and `right`). 4 copper layers (my
    choice, not asked: inner 1 is a GND plane under the module). Module with its **antenna end on the rear edge** (body 0.3 mm inside it),
    2.7 mm from the east edge; the footprint's own rule area (12.4 x 3.75 mm, all copper layers) is free of tracks,
    vias, pours and foreign pads on all four layers (`pcb_pod.py --check`). USB-C at the rear edge, its shell ends
    flush with the rail's rear face (board edge 2.51 mm inside it); lead connector on the west side over the rail,
    mouth to the west; debug header, reset button, status LED and level shifter over the bay. Socket and holes
    checked against the bays of the three routed key boards (worst offset 0.005 mm). **Cost, accepted with the
    choice**: the antenna sits about 3 mm above the rail with the power board 14 mm under it and steel cells
    beside it: range to be measured at bring-up; the fallback is the MDBT50Q-U variant with an antenna socket
    (same footprint).
  - **Rear leg of the rail 27 mm deep (side leg stays 19), power board 48 x 22 mm**, one side, 4 copper layers (my
    choice). Measured first: its parts need 627 mm2, the 48 x 14 mm guess was 672 mm2. `numpad` becomes
    107.6 x 181.4 mm. West end: pack plug (mouth to the west, into a wiring channel beside the rear cell: the
    cell lies in the front lane of the rear leg), fuse, reverse FET, 47 uF can; slide switch on the rear edge
    (actuator through the rail's rear wall, about 1.6 mm proud of a 2 mm wall); converters in the middle; **lead
    connector vertical (JST BM06B-GHS-TBT, plugged from above) in the rear-east corner. The front-east corner
    (15.5 x 6.6 mm) is cut away**: found in FreeCAD after the choice, the numpad's three side cells with a contact
    end about 6 mm inside the board's rectangle. Two M2 holes on the front edge, both in the west half: the east
    end needs printed posts under it (the lead is pushed in there).
  - **Cell count by a solder jumper**: 1.65 M is always fitted (6 cells, as delivered); bridging `JP1` puts
    2.55 M in parallel (1.0 M, 4 cells: `numpad`). One assembled board for every module. (I offered a 3-pad
    jumper; a 2-pad one that is only ever bridged does the same without a cut.) 5 cells are no longer provided for.
  - **Kept (user)**: TPS2553 LED rail cap, 47 uF can and gate Zener, 2x5 debug header, pack on a JST XH plug;
    also kept: status LED, four test pads, the carrier's SP1-SP3 wires.
  - **Footprints** (`tools/gen_kicad.py`, from the datasheets): `TI_VQFN-HR-15_2.5x3mm_RNM0015A` (land pattern
    4222000/B; the VIN and VOUT leads are U-shaped, drawn as two legs and a bar), `L_Coilcraft_XGL3530` (lands
    0.81 x 3.2 mm, 1.8 mm apart; drawing from a distributor's copy of Document 1607, 2020: compare with Coilcraft's
    current sheet), `L_Coilcraft_XFL4020` (0.98 x 3.4 mm, 2.37 mm apart, Document 745-3). **KiCad's
    `RF_Module:Raytac_MDBT50Q` against Raytac's spec: outline 10.6 x 15.6 mm, 61 pads (55 numbered round the edge
    plus 6 inner), antenna end, the 10.5 x 3.8 mm no-ground area and the 1.6 x 1.2 mm top-layer patch 2.95 mm from
    the edge all agree; Raytac's separate footprint package could not be downloaded, the review checked every pad
    against the spec's drawing instead.**
  - **Scripted copper** (`route_hub.py` `pod_power_copper`): the two converters' supply and switch pins to their
    capacitors and inductors, 0.25 mm, each under 5 mm; the rest by the autorouter (supply nets 0.5 mm) and the
    finishing pass. The GND via pass and the finishing pass now respect footprint rule areas and the power
    board's notch.
  - **Hub**: the carrier (`hub-radio`, 27.5 x 20 mm, 2 layers, stepped round the stack connector) sits on the
    expansion header at the rear left; the bay is turned by 180 degrees, so **the pod points to the front of the
    tower, above the Pico** (the other way its rear end would pass the rear wall). Socket checked pad by pad
    against the routed `hub-core`. Found: the pod's module top is 27.3 mm above the core board, the plain shell
    tube of the section ends 19.5 mm above it: **the tower's core section must be at least 9 mm taller with the
    radio fitted** (M3 hub shell). The two antennas (Pico at x -35, pod at x -47, 13 mm higher) are close: the
    host link and the module link may disturb each other, to measure at M6.
  - **Independent PCB review (Opus)**: footprints, module pads (every coordinate against the spec's drawing, which
    settles the pad pitch), mating and the lead found correct. Fixed: PGND of the 5 V converter (inductor at
    1.15 mm, two PGND vias between its pads, two vias at each capacitor), the 3.3 V output capacitor at the chip's
    GND end, pack current on top at 1.0 mm, crystal under its pins, level shifter capacitor at its pin, through
    vias, module 0.3 mm inside the edge. Left open: GND copper and the USB-C shell beside the antenna area on the
    rear edge (moving the port is a user decision), an 0603 at the converter's VIN / VOUT pins, D+ on a stub at the
    ESD array, a support for the carrier in the hub, the "buried" via mark on `hub-conn`, `port-module`, `usb-port`
    (**fixed 2026-11-14, user: `route_hub.py <board> --through-vias`, 262 / 12 / 8 vias, drill files identical before
    and after, DRC unchanged**).
- **Shell (M3b step 3 with M3 session 2, 2026-11-14)**: `mech/case/pod_case.py`, loaded by `build_case.py` with
  `CASE_VARIANT=pod` (output `build/case/numpad-pod/`); `numpad` only so far. **Decided by the user (options UI, each
  shown in FreeCAD)**:
  - **Service port stays on the pod's rear edge; the copper beside the antenna is cut back**: a rule area `ANT_band`
    (no tracks, vias or zone copper on any layer) from 0.6 mm east of the USB-C shell's lug to the east edge, 4.15 mm
    deep (`route_hub.py` `ANT_BAND_*`). `pod` routed again, same placement; measured: 0 mm2 of copper in the band.
    The shell itself stays 5.3 mm from the antenna area: range is measured at bring-up, fallback MDBT50Q-U.
  - **Tray and rail are one print** (107.6 x 181.4 x 19 mm; wired tray unchanged, 88.6 x 154.4). Feet at the four
    corners of the larger rectangle; the tilt bars run on under the side leg and are computed from the new rear feet.
    A wired module that goes wireless gets a new tray.
  - **Contacts: Keystone 5201 (coil spring on an 11.2 x 12.0 x 0.51 mm plate, spring 10.5 mm high) and 5223 (button,
    dome 1.4 mm)**, drawings in `build/ds/contacts/`. The three side cells lie end to end with **a 5201 at both ends**
    (3.75 mm each with three 50.5 mm cells, 5.70 mm with three 49.2 mm cells); the rear cell has a 5223 at the west
    wall and a 5201 at the east end (4.5 to 5.8 mm). Plates drop into 0.6 mm slots behind a rib with a 7 mm window.
    **Not in any drawing: the spring's solid height and force** (fit print).
  - **Power board notched at its west-front corner too (4 x 13 mm)**: the rear cell's lane was 3.9 mm short for a
    coil spring (found at this step: the 48 x 22 mm board was placed in session 3 without the contacts drawn).
    West mounting hole moved to (6.8, 19.3) from the board's west end / rear edge, three test pads moved;
    `pod-power` placed and routed again (clean on try 1).
  - **Lids: two sliding cell lids** (side 179.9 x 16.2 mm, out to the front; rear 47.9 x 24.7 mm, out to the west),
    1.0 mm edge flanges in 0.7 mm grooves of the rail walls, a 0.4 mm ridge under the outer end that drops behind
    the lowered end wall (the snap). The side lid also covers the lead's plug in the rear-east corner.
    **Changed from the option text, by me**: sliding instead of hook-and-latch (a latch pocket does not fit a 2 mm
    wall), no separate lid over the lead corner, no deck plate under the pod (the rail walls end at 16.5 mm there
    and the cover closes it; the lead has to drop from the pod's west edge into the rail at that spot).
  - **Cover over the pod**: the bay cover carried on to the rail's rear face (42.3 x 54.2 mm, same height 27.62),
    a hood west of the pod for the lead's plug, arched over the cell lane so the rear cell tips out, USB-C opening
    9.5 x 3.8 mm for the shell (flush with the rear face), same two M2 x 22 screws.
  - **Power board** on two bosses with inserts and five posts, underside 6.0 mm above the desk side (can top 13.4);
    switch slot 8.0 x 3.4 mm in the rear wall. **Wires** (not modelled): tabs up and bent over; column wires in the
    pocket's bottom corner beside the cells, west along the 2.5 mm strip in front of the board; the column's minus
    wire passes under the board to the pack plug.
  - Clash checks 31 pairs, 0 clashes (wired: 14, 0). Fit pieces: `fit-rail-front`, `fit-rail-rear`, `fit-power`,
    `fit-lid-side`, `fit-lid-rear`.
- **Open**: the pod's rear end overhangs its two screws by 32 mm with nothing under it (a support has no free spot
  on the rear wall: pack plug, can, switch and antenna); lid snap, groove play, plate slots and spring heights on
  the fit print; slide switch actuator against its slot (C&K drawing); `left` and `right` (rail turned with the
  rear strip, their cell plan, left's width for the sixth cell); the tower's core section height and a support for
  the carrier; USB4085 shell overhang (2.51 mm, from KiCad's footprint) against the GCT drawing; on `pod-power` the
  finishing pass closed one +5V_RAW link and the +3V3 line at 0.2 mm (review before the order).

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
- **Hub mechanics (M2 session 4, user, 2026-11-13)**, numbers in `mech/hub/hub_geom.py`, section model
  `mech/hub/build_hub.py`, placement `tools/pcb_hub.py`: **tower 114 mm square outside (user, 2026-11-14; was 100)**, grown
  to the rear and the sides so that the front wall and the module ports stay where they were; connector layer board
  108 x 108 mm, core (94 x 77) and battery (94 x 94) boards unchanged for now and all on the same four screw places
  (+-43.5 / +-20 mm), 17.5 mm between boards everywhere. Stack: Samtec ESQ-125 stack-through socket on both boards (both on top, the core's tails
  in the connector layer's socket). Pico on standard sockets; USB and BOOTSEL by three Mill-Max 0929-7 spring pins
  (1.15 mm of 1.40 mm stroke used: check on the real socket stack). Buttons: NKK UB16 (power, latching) and UB15 on
  leads to JST XH plugs on the core board. Module ports: Amphenol 12401548E4-2A on the connector layer's front edge.
  Chain seam: riser (Samtec DW-08-17-T-D-254) and cap board with a Mill-Max 827 2x8 spring-pin strip on each battery
  board, Mill-Max 1578 target discs under the board above. Placed and routed (next point).
- **Hub board layouts (M2 session 5, 2026-11-14)**, `tools/pcb_hub.py` (placement) and `tools/route_hub.py` (routing):
  - **`hub-conn` has 4 copper layers (user, 2026-11-13)**: top = parts and signals, inner 1 = unbroken GND plane (no
    tracks), inner 2 = power trunks and signals, bottom = signals. All SMD parts stay on top. The heavy copper is
    drawn by the script; the autorouter adds only the thin nets and never touches the plane layer.
  - Arrangement: host-port header rear left with a clear strip for its plug; USB switch, battery switch and the SYS
    bulk capacitors around one SYS node behind it; the converter under them at the left edge; the five pack inputs as
    five columns across the middle (west to east packs 3, 2, 1, 4, 5), each entry vias, TVS, ideal-diode FET, priority
    FET, VBAT vias; the three ports along the front, each ESD arrays and series resistors behind the receptacle, the
    buffer behind them, the TPS25810 at the receptacle's east side; the +5V 220 uF at the front left.
  - Converter as the TPS552892 datasheet layout: input and output capacitors at the VIN and VOUT strips with PGND
    between them, a GND via row behind the capacitors, inductor on the other side with the boot capacitors on the
    switch strips, VCC capacitor at its pin. **Not as the datasheet: AGND is not a separate island**; pins 2, 5, 17
    and the FSW, FB, COMP and EN parts go to the GND plane by their own vias (to judge at the PCB review).
  - **Chain seam comb**: every pack line has one target pad in the north row and one in the south row, in mirrored
    order, so no two can be joined on one layer between the rows. The north pads cross the pad block on inner 2; on
    the bottom all ten ends then lie in one row and the pairs nest (PACK1 outermost), joined by five 1.2 mm lanes.
    Each lane leaves through two vias and a 1.2 mm trunk on inner 2 to its column (PACK1 straight on the bottom).
  - Supply copper: SYS 2.2 mm on top (USB switch to the input capacitors); VBUS_IN 2.5 mm on the bottom under the
    header; VBAT 3 mm on inner 2 along the columns and up to the battery switch; +5V 3 mm on inner 2 from the output
    capacitors along the front to the three ports (3 mm branch and three vias at each TPS25810) and the 220 uF; port
    VBUS through two vias and an inner-2 bar to the receptacle's two VBUS through-pins. All four hub boards: DRC
    0 errors, 0 unconnected, parity 0 (2026-11-14).
  - **Host port board `hardware/usb-port` (M2 session 7, user, 2026-11-14)**: 38 x 15 mm, 4 copper layers, all parts on
    top, in the rear strip of the connector layer behind the stack connector, on two M2 x 3 mm threaded standoffs that
    stand on `hub-conn` (holes at x = -28 and -12, y = 57.5 in hub coordinates) left and right of the receptacle. The
    USB4085's mouth is flush with the rear wall's outer face; the 11-pin cable header is at the board's front edge and
    faces forward, so its plug and the plug on `hub-conn` are both in the open. Placement `tools/pcb_port.py`, copper
    `tools/route_hub.py` `usb_port_copper`: the KTS1693's OUT and IN ball groups each leave the 0.4 mm field as a mesh
    of 0.22 mm tracks on their own side (no via under the chip) into via fields; both VBUS paths run on inner 2
    (2 mm from the receptacle to the switch, a 1.2 mm bus to the header's three VBUS pins); **inner copper 1 oz (user, 2026-11-14)**.
    DRC 0 errors, 0 unconnected, parity 0. To clear with JLCPCB at the order: 0.22 mm lands with 0.18 mm gaps.
  - **Inner copper of `hub-conn`: 1 oz (user, 2026-11-14)**, an order option at JLCPCB (default 0.5 oz; goes into
    D7). On 0.5 oz a 1.2 mm pack trunk would warm by roughly 20 K at 2.2 A (one pack at its 8-10 W) and more at the
    fuse's 5 A; the 3 mm trunks are fine either way.
  - After routing a tidy pass (`route_hub.py --tidy`) removes unused stubs and pushes close via pairs apart, and
    `tools/silk_keys.py` places the references (hidden where a dense spot leaves no room). Left on `hub-conn`: two
    via pairs with holes 0.49 mm apart (our margin is 0.5 mm) and one of port B's two VBUS vias that joins nothing.
  - `hub-core` and `battery` are plain 2-layer boards, routed by the autorouter (battery pack lines 1.5 mm, their
    vias 1.5 / 0.9 mm since the PCB review). **They stay 94 mm for now (user, 2026-11-14: shown at 108 mm in FreeCAD,
    taken back; to decide at M3).**
  - **Power areas (PCB review, 2026-11-14; `route_hub.py` `power_areas`, on a routed board `--power-areas`)**: the
    TPS552892's VIN, VOUT and switch strips are 0.25 mm wide at 0.5 mm pitch and left through 0.25-0.4 mm necks up to
    1.8 mm long (the review's one must-fix). Now each neck is 0.25-0.45 mm long and opens into a copper area on top:
    SYS over the input capacitor bar (about 26 mm2), +5V over the output capacitors and their vias (30 mm2), SW1 and
    SW2 down to the inductor pads (25 mm2 each); a PGND via at each end of the PGND strip. Module ports: VBUS as an
    area on top (switch to vias) and on inner 2 (vias to the receptacle's through-pins; port B's second via now
    carries); extra vias under the TPS25810 exposed pads where the routed board has room (A 2, B 1, C 3; three each
    on the next routing). `port-module`: +5V area on inner 2 round the receptacle's through-pins.
  - **Placement findings of the PCB review, closed at M2 session 9 (2026-11-14); boards placed and routed again.**
    Distances are pin to capacitor pad, centre to centre, measured on the routed boards.
    `hub-conn`: the 74AHCT125's 100 nF beside its pins 12-14 (2.5 mm; was 45 mm); each port buffer's 100 nF beside
    its pin 14 (1.9 mm; was 27 mm); each port's TVS0500 at the port's VBUS vias beside the receptacle, its VBUS pads
    inside the top VBUS area (1.3 mm from the vias, 5.6 mm from the receptacle's VBUS pins over the inner-2 area;
    was 13-23 mm on a 0.4 mm track). Converter, a quiet corner west of the chip, away from the switch nodes (**user,
    2026-11-14: no separate AGND island; every ground end has its own via to the unbroken plane**): **a 1 uF 0603
    added right at VCC pin 18 (user, 2026-11-14; 1.7 mm, pad edge 1.2 mm, 0.3 mm track)**, because the 22 uF 1210
    cannot come nearer than 2.4 mm without shutting the FB, COMP and AGND pins in; the 22 uF stands below it on the
    same 0.3 mm track, each capacitor's ground end on its own via(s), the AGND pin's via between them. The 470 pF
    on COMP is 3.3 mm from pin 15 (was 15 mm), the track to the 12 k and 15 nF runs on under the 470 pF's body to a
    column below it; the FB divider sits beside the +5V vias (FB about 8 mm, routed along the edge of the +5V area).
    `usb-port`: the KTS1693's input 100 nF beside its west ball column, 1.5 mm from IN ball E4 (was 14 mm), its
    ground pad at the via of the chip's west GND balls. Key boards: §2.
  - **Finishing pass on every routed board (M2 session 9).** `tools/route_hub.py` `finish()` (a small maze router that
    closes what KiCad's DRC lists as open and redraws autorouted tracks DRC reports for clearance) now also runs on
    the 2-layer key boards (`tools/route_keys.py`, after the strip autorouter) and once more after the tidy pass on
    the 4-layer boards (the tidy pass took a via that lands in the middle of a wide trunk for a loose one).
  - **Cap board `hardware/chain-cap`** (26 x 18 mm, 2 layers, no parts but the riser's upper end and the spring-pin
    strip): riser pin n to spring pin n, nets `LINE1`-`LINE16`. Every line passes one row of foreign pins through the
    0.84 mm gap between two pads as a 0.4 mm neck 2.5 mm long (about 3 mOhm), 1.2 mm wide otherwise.
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
  2 x 100 n, VCC 22 uF + 1 uF 0603 at the pin (M2 session 9), COMP 12 k + 15 n with 470 p in parallel (crossover about
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
- **Host port (`hardware/usb-port`, changed at M1 task 5; laid out at M2 session 7, §3a).** KTS1693 **ISET 2.87 k**:
  limit 3.17 / 3.48 / 3.80 A (10000 / R, +/-9 %, 0-70 C; was 4.99 k, 2 A); switch
  13 mOhm max, 0.16 W at 3.5 A. **OC_MODE open** = high through the internal 5 M
  pull-up = auto-restart (limits for 8 ms, off, retries after 200 ms; was latch-off).
  **OVLO stays external, 100 k / 26.4 k 0.1 %**: trips at 5.56-5.93 V. The rev 8 value
  (27.4 k, from 5.40 V) could cut off a legal 5.5 V host; the internal threshold
  (5.77-6.13 V) is above the USBLC6-2's 6 V breakdown (from memory, check at the
  parts list). The cable header carries VBUS and GND on three JST GH contacts each,
  1 A per contact: 3 A is its limit.
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
- **O10** cable-free pods (**hardware now required before the order, user, 2026-11-14; roadmap M3b**): they take the port board's place in the bay (2x6 header,
  two M2 screws; D3); bay size and header position frozen at M1. **Hardware decided 2026-11-14 (§2b)**; schematics, boards and
  the shell's rail are next; the radio link, its latency and the firmware come after the hardware exists.
- O4, O5 closed 2026-11-13 (archive move; Pico 2 W, test image compiles for `pico2-w`;
  RP2350 erratum E9 avoided by pull-up scanning, which the expander's pull-ups give).
