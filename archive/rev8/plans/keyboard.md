# Split K860-alike — hardware + firmware spec

Three-piece mechanical keyboard styled on the Logitech ERGO K860. Key modules:
`left` (alphas), `right` (alphas + arrows + nav + dial), `numpad`. **Rev 8: the key
modules carry no radio, battery or power path.** A single **hub** on the desk holds
the radio, the host USB-C port, the cells, the power path and the expansion
connector, and each key module plugs into it through a **swappable comms board
pair**, a USB-C cable in rev A. BLE or USB to the host, per-key RGB, 9 host
profiles, MX hotswap, AA cells in up to 3 stacked 4-cell battery modules (NiMH; rev 8.1, 2026-09-30).

Ends at gerbers + costed BOM + firmware that builds. Nothing ordered without
sign-off.

**Rev 8** (2026-09-26): the per-module-core architecture of rev 5–7 is replaced by
a hub and "dumb" key modules. What drove it: one radio and one power path instead
of three, no split transport in firmware (no wired/BLE failover, no all-or-nothing
rule, no pair-2 passthrough), fewer boards, cheaper modules, and room to grow the
hub and the comms boards later. The rev 7 state (spec, docs, schematics, the
core PCB routed to 7 open nets) is commit `0b22b91`. What rev 8 changed is in §17;
earlier changelogs are kept after it because they record why the carried-over
power design looks the way it does.

## 1. Topology

```
  HUB: a stack of layers on the desk, top to bottom (decided 2026-09-26)

   +-----------------------------------------------------------------+
   | OPTIONAL LAYERS (0..n), e.g. a display; stack on the core's top   |
   |   expansion header (2x10, pass-through)                           |
   +===================== expansion header 2x10 =======================+
   | CORE LAYER   base board (one board, ~94 x 94 mm): MDBT50Q-U1MV2,  |<-- host USB-C (USB port board)
   |              power path, LED rail, TCA9548A, buttons, all         |    expansion SH socket (expansion board)
   |              stacking headers; u.FL -> Yageo PCB antenna on the   |    antenna inside the case wall
   |              inside of the case wall (whip knock-out, blanked)    |    (external Yageo whip optional)
   +==== slot header 2x16 ==== chain header 2x6 ======================+
   | CONNECTOR LAYER (swappable: wired now; radio, optical, mixed      |
   |   later). Wired: carrier PCB + 3 socket boards (hub-side comms    |--> slot 1 --> USB-C cable --> [left]
   |   boards on J_SLOT), chain passed through                         |--> slot 2 --> USB-C cable --> [right] + dial
   +============================ chain header 2x6 =====================+--> slot 3 --> USB-C cable --> [numpad]
   | BATTERY MODULE 1  (4xAA, passive; rev 8.1)   -- or instead: Qi2 board (ends the stack)
   +============================ chain header 2x6 =====================+
   | BATTERY MODULE 2  (4xAA, passive)
   +===================================================================+
   | BATTERY MODULE 3  (4xAA, passive; a 4th gets no chain line)
   +-------------------------------------------------------------------+

  Each key module: module-side comms board -> key board (module controller,
  IS31FL3733, LEDs, sockets); right adds the dial board.
```

- **The hub owns everything host-, radio- and power-facing**: the host USB-C port,
  BLE to the host, the cells, the power path, the lighting power, the expansion
  connector, and later Qi2. It runs the keyboard firmware as **one keyboard**, not
  a split.
- **The hub is a stack of layers** (decided 2026-09-26), top to bottom: **optional
  layers** (a display, later others; any number), the **core layer**, the
  **connector layer**, then **battery module 1 … N**, or a **Qi2 board** in place
  of battery module 1, which then ends the stack. Layers join on stacking headers:
  a **2×10 expansion header** on the core's top face (passed through by every
  optional layer), a **2×16 slot header** between the core and the connector layer
  only, and a **2×6 chain header** in the same place on every layer from the core
  down (§6). The expansion board's JST-SH socket stays for cabled accessories.
- **The core layer is one board** (decided 2026-09-29; the vertical MCU board of
  2026-09-26 is dropped): the **base board** carries the **MDBT50Q-U1MV2** (u.FL,
  no on-module antenna), the power path, LED rail, TCA9548A, buttons and every
  stacking header. The module's u.FL feeds an **adhesive PCB antenna (Yageo
  ANTX100P011B24003, 2026-10-01) on the inside of a core-section wall**; the wall
  also has a **blanked knock-out for Yageo's ANTX100ETHAB24553 whip**, so an
  external antenna is a swap, not a respin. Both are on Raytac's approved antenna
  list for the -U with CE (§11, §13).
- **Each key module is a key board plus a module-side comms board.** The key board
  carries switches, diodes, RGB LEDs, the LED driver and a small **module
  controller** MCU (no radio) that scans the matrix and the dial, drives the LED
  driver, and serves **one I2C register map** to the hub (§9). The module has no
  cells and no power path; it runs from the hub.
- **Star wiring, one link per module.** Each module links to its own hub slot. No
  module passes another's traffic, and a fault or hot-plug on one link does not
  touch the others: each slot sits on its own channel of an I2C switch.
- **The connector layer is swappable, and chooses the medium.** It holds the hub
  side of all three links. A link is the connector layer's slot, a medium, and a
  module-side comms board. Rev A is the **wired connector layer**: a carrier PCB
  with three small **socket boards** (hub-side comms boards, one USB-C socket
  each, cabled to the carrier on `J_SLOT`, so a worn socket costs one small board)
  and a plain USB 2.0 C-to-C cable to each module's USB-C comms board. Radio,
  optical or mixed (e.g. cable plus radio) connector layers and module-side boards
  may replace them later (§15). **The contract between a comms pair
  and the boards it plugs into is the module register map, not the medium**: the
  hub and the key board never know which medium is fitted. How a mixed pair picks
  or relays between media is the comms pair's business.
- **Seams are mechanical only.** Joined modules align and retain with magnets or
  dovetails; no contacts cross a seam.
- **Batteries chain.** **Rev 8.1 (2026-09-30): up to 3 passive 4×AA (NiMH) modules, each pack on its own chain line (shifted by one per module), all protection and the OR on the hub (§4).** Rev 8 had: each battery module is one 2×AA pack with its own protection
  and ideal diode. Modules **stack under the hub** on a pass-through stacking
  header (decided 2026-09-26; side by side is kept as a future option). Rev A fits
  two. A future Qi board plugs into the same hub header **instead of** the battery
  stack (§15).
- **Not untethered.** The key modules cannot run away from the hub; the hub is the
  wireless part. Accepted in rev 8 (§17).

## 2. Per-module spec

| | left | right | numpad |
| --- | --- | --- | --- |
| Keys (approx) | 40 | 52 | 17 |
| Matrix | 6×7 | 6×9 | 5×4 |
| Module controller | **TI MSPM0G3505, LQFP-48** (P19, 2026-09-26) | same | same |
| Module ID | strap on the key board, read by the module controller, reported in the register map | same | same |
| LED driver | IS31FL3733, on the key board, driven by the module controller | same | same |
| RGB LEDs / 64 max | 40 | 52 | 17 |
| Dial | — | dial board, PEC11R, 24 detents / 24 ppr, on the module controller | — |
| Link | 1 module-side comms board (rev A: USB-C cable board) | same | same |
| Power | from its hub slot only (switched LED rail) | same | same |
| SWD | module controller SWD pads | same | same |

Key counts firm only after Phase 1. Diodes `1N4148W` per key, so ghosting and
blocking are impossible regardless of how many keys are held.

| | Hub |
| --- | --- |
| MCU | **MDBT50Q-U1MV2** (u.FL, 2026-09-29), on the base board; Yageo ANTX100P011B24003 PCB antenna inside the case wall, blanked knock-out for the Yageo ANTX100ETHAB24553 whip (2026-10-01) |
| Host | USB-C on the USB port board (KTS1693, CC sense); BLE |
| Slots | 3, on the connector layer (rev A wired: a socket board per slot), each with a switched LED rail, one TCA9548A channel, `INT`; joined to the core by the 2×16 slot header |
| Cells | battery chain, rev A 2 battery modules × 2 AA (alkaline or NiMH) |
| Expansion | expansion board, cabled to the hub core |
| Layers | optional layers (0..n) / core (one base board, MCU on it) / connector / battery module 1…N, or Qi2 board instead of the battery modules (§1) |
| Future | Qi2 board in place of battery module 1 (§15); radio/optical/mixed connector layers and module-side boards (§15) |
| SWD | test points + Tag-Connect footprint |

## 2a. Boards

**The principle is unchanged from rev 5: every event that damages or wears
something happens on a small board you can swap.** Plug wear, surges, ESD,
reversed cells and encoder wear land on boards that cost a few euros and
plug in with cables. The hub core and key boards sit behind that protection.

| Board | Design | Per keyboard | Carries | Assembly | Replaced when |
| --- | --- | --- | --- | --- | --- |
| **Hub base board** (horizontal, 94 × 77 mm since 2026-10-01: its front edge at y −30 leaves room for the panel buttons; one board since 2026-09-29) | 1 | 1 | **MDBT50Q-U1MV2** with its u.FL to the Yageo ANTX100P011B24003 PCB antenna on the inside of the case wall (or the Yageo ANTX100ETHAB24553 whip in the blanked knock-out), 32.768 kHz crystal, `VDD`/`VBUS` decoupling, SWD pads + Tag-Connect TC2030-NL footprint, 27 Ω D+/D−, connectors for the three front panel buttons (power, reset, boot; NKK UB, §11), and the rev 8.1 battery path (§4: 3 pack inputs with SMF4L9.0CA + LM74610-Q1 + CSD17313Q2, CSD25402Q3A battery and USB switches, TPS3840PL40 UVLO and PL43 USB detect, DMN63D8LDW drivers, battery sense on the PL40 node), `VBUS_IN` OR (host USB + chain `AUX_5V`), TPS70933 VSYS LDO, TPS630701 LED rail, expansion LDO + `J_EXP`, **TCA9548A I2C switch**, 2×10 expansion header on top, 2×16 slot header and 2×6 chain header underneath, `J_USB`, test points | assembler | power path or MCU fault |
| **Connector layer, wired** (2026-09-26) | 1 carrier PCB | 1 | carrier PCB: 2×16 slot header and 2×6 chain header on top, 2×6 chain header underneath (chain passed through), 3 × 14-pin `J_SLOT` to the socket boards; no active parts planned | assembler (headers) or by hand | rarely; the socket boards take the wear |
| **Key board** | 3, one per module | 3 | hotswap sockets, diodes, RGB LEDs, IS31FL3733, **module controller**, 3.3 V LDO (TPS7A0233PDBVR, TLV75733PDBVR second source on the same footprint), I2C pull-ups, module-ID strap, SWD pads, `BSL_invoke` rescue pad (PA18 + 3V3, §9), `J_COMM`, `J_DIAL` (`right`) | assembler | rarely; sockets and LEDs are hand-reworkable |
| **Comms board, cable** | 1 PCB, 2 populations | 3 hub side (the wired connector layer's socket boards) + 3 module side | GCT USB4085 USB-C receptacle, TPD6E05U06 on A5, B5, A6, B6, A7, B7, **TVS0500** on VBUS (was SMF6.0A; 2026-10-01, E7). **Hub population:** TPS22950L slot switch + `ILIM` 624 Ω, CC pull-ups fed from `SLOT_EN`, **14-pin `J_SLOT`**. **Module population:** BAT54C joining CC1/CC2 into `INT`, **10-pin `J_COMM`**. KiCad design variants `hub` / `module`; the header pin counts differ so neither fits the other's position (repurposes the rev 7 link board) | assembler | socket worn, surge |
| **USB port board** | 1 | 1 (host port, on the hub) | USB-C receptacle, 2 × 5.1 kΩ CC, KTS1693, OVLO divider, TVS2200 footprint, SMF6.0A, USBLC6-2SC6, TVS2200 on CC1/CC2; GCT USB4085 (unchanged from rev 7) | assembler | socket worn, surge, OVP latched and not recovering |
| **Battery module** | 1 | up to 3 (rev 8.1) | **rev 8.1 (2026-09-30): passive**: a 4×AA holder (part open), one PTC in the pack lead, the pogo seam parts (Samtec DW-06-17-T-D-254 riser + cap board with the Mill-Max 827 strip on top, 12 Mill-Max 1578-0 discs underneath), and the chain's one-position line shift (own pack → `PACK_A`, `PACK_A`/`PACK_B` from below → `PACK_B`/`PACK_C`); the rev 7 pack chain, LM66200 and BAT54 move to the hub or go (§4) | hand-solderable except the discs and the PTC (reflow) | corroded holder, worn pogo parts |
| **Dial board** | 1 | 1 (`right`) | unchanged from rev 7: PEC11R, push-switch diode, 1 kΩ + 10 nF on A and B, DNP TPD4E1U06DBV, 5-pin `J_DIAL`; the A/B filter re-checked against the MSPM0G3505's 40 kΩ pull-up and unchanged (2026-09-26) | hand-solderable | encoder worn |
| **Expansion board** | 1 | 1 (on the hub) | unchanged from rev 7: JST SM12B-SRSS-TB, TPD4E05U06 + TPD6E05U06, 15-pin `J_EXP`; shares the expansion bus with the top header (kept 2026-09-26 for cabled accessories) | assembler (ESD arrays) | socket worn, ESD hit |
| *Optional top layers* (display first, future) | per add-on | 0..n | stack on the core's 2×10 expansion header and pass it through; each takes one SPI chip select (CS0–CS3) by a jumper, carries a Microchip 24AA024 ID EEPROM at 0x50 + its CS number (X1, §6) and needs distinct I2C addresses for anything else; ESD on anything user-touchable | — | — |
| *Qi board* (future) | 1 | 0–1 | Qi2 receiver, `AUX_5V` into the hub's chain header, used instead of the battery stack (§15) | — | — |
| *Radio / optical / mixed connector layers and module-side boards* (future) | per medium | 1 layer + 3 module boards | the layer uses the same 2×16 slot header and 2×6 chain pass-through; the module side uses `J_COMM`; a module-side wireless board may bring its own battery chain (§15) | — | — |

Rules that fall out of the partition:

- **One hub, three identical slots.** Any module works in any slot. The hub reads
  each module's ID from its register map and maps its keys accordingly; it does
  not care which slot a module is in.
- **One comms board PCB per medium, two populations keyed by header pin count.**
  The hub side sources power and has the current-limited switch; the module side
  takes power and has none. `J_SLOT` (14) and `J_COMM` (10) differ, so a hub-side
  board cannot be cabled into a key board or the reverse.
- **The LED driver stays on the key board**, now behind the module controller's
  own I2C bus. Moving it to the hub would put 28 LED nets and 320 mA SW currents
  through the link.
- **The module controller is the only thing on the key board that talks to the
  link.** The hub never addresses the LED driver directly. That keeps the link at
  one I2C address per module and keeps the register map the only contract a
  comms pair must carry.
- **Service rule: power switch off and USB unplugged before unplugging any
  internal cable.** Advice, not the only protection: the key board limits current
  into its logic pins if a link is pulled live (§4), and link cables are
  user-pluggable by design (§6).
- **Tool-less cell access.** Each battery module opens without tools. Every board
  is fixed with M2 screws into captive M2 nuts (§11), so one driver services the whole
  keyboard.
- **Fault reporting.** Firmware reads the host port's `ACOK`, each slot switch's
  state, and each module's presence and status. It reports faults as key-light
  blink codes and over the log. The build guide maps each symptom to the board to
  swap.

## 3. Locked decisions

| Area | Decision | Why |
| --- | --- | --- |
| Architecture (rev 8) | **Hub + dumb key modules**, star-wired, one hub slot per module; **the hub is a stack: core layer / connector layer / battery modules 1…N or a Qi2 board** | one radio, one power path, one firmware image for the keyboard; modules cheaper and easier to repair; hub and comms can grow later |
| Key board brain (rev 8) | **Module controller: TI MSPM0G3505 (LQFP-48)** per key board (P19, 2026-09-26), scanning at ~1 kHz, decoding the dial, owning the LED driver, serving one I2C register map | the TCA8418 keypad scanner adds 25–40 ms per press (TI SCPS215G p. 33); a hub-scanned expander (TCA6424A) needs register polling that a radio or optical comms pair cannot carry |
| Comms (rev 8) | **Swappable connector layer** (hub side, all three links) **+ module-side comms boards**; rev A = wired layer with three socket boards and plain USB 2.0 C-to-C cables; the register map is the contract | start cheap, keep radio/optical/mixed media possible without touching the hub or key boards |
| Link cable (rev 8) | USB-C both ends, **any passive USB 2.0 C-to-C cable**; VBUS = switched LED rail, D+ = SDA, D− = SCL, CC = `INT` | cheap, stocked everywhere, a cable is a spare part; the USB 2.0 cable has exactly five conductors, which is what the link needs |
| Battery (rev 8.1, 2026-09-30) | **Up to 3 passive 4×AA battery modules** (NiMH; alkaline fits), stacked under the hub on pogo seams; each pack on its own chain line, protection + OR + UVLO on the hub; **no charging** | simplest modules; a hard cap of 3 lets each pack keep its own line (rev 8 had any number of active 2×AA modules) |
| Qi2 (rev 8) | **Optional, later**: a Qi board on the hub's chain header feeds `AUX_5V`, **used instead of the battery stack**; it never charges cells | reserve the path now, design the board later |
| Switches | Cherry MX, Kailh hotswap `CPG151101S11` | off-the-shelf caps |
| Caps | widths 1U–2.75U inclusive, **any off-the-shelf set** | standard sets need 2.25U/2.75U; shine-through not required |
| Spacebar | 2 × 2.75U, one per half | the K860's spacebar is already split |
| Bottom row | flat, not arced | lets long keys stay rectangular; the K860's bottom row is nearly level anyway |
| Pitch | **19.05 mm throughout, pending Phase 1** | see §10 |
| Width | **~468 mm accepted** | 456 mm key field + two ~6 mm seams; known deviation from the K860 |
| Layout | K860 arc via per-key rotation, alpha rows only | the arc is the K860 look |
| Size (2026-10-01) | **not a goal**: easy repair and user-friendliness win over the smallest or thinnest hub, boards and enclosure (user) | bigger controls, roomier boards and hand-reworkable parts are worth more than a compact tower; compactness-driven choices get revisited |
| Board partition | **by failure mode** (§2a): hub core, key, comms, USB port, battery, dial, expansion | a worn or abused part costs a small plug-in board, not an assembled board |
| Interconnect | **several small locking wire-to-board connectors, split by function**, JST GH family (1.25 mm, positive lock) proposed, **any fallback must also lock**; ≥2 contacts per power net; unique pin counts | hand-solderable, premade cables, a cable is a spare part |
| Module ID | strap on the key board, read by the module controller, reported in the register map | identical module-controller firmware on every key board; the hub maps keys by ID, not by slot |
| Service | power switch off and USB unplugged before unplugging an internal cable, **backed by series R into the key board's logic pins**; tool-less cell access; M2 screws throughout; every external connector is user-replaceable by swapping the small board it sits on | builders will pull cables live anyway; plugs wear and take the surges |
| MCU (hub) | **Raytac MDBT50Q-U1MV2** (u.FL connector, no on-module antenna; 2026-09-29), **single source accepted**; on the base board; antenna (2026-10-01): **Yageo ANTX100P011B24003** adhesive PCB dipole (2.2 dBi) on the inside of a core-section wall, **blanked knock-out for the Yageo ANTX100ETHAB24553 whip** (2.0 dBi, integral cable); no RP-SMA | pre-certified module; both antennas are on Raytac's -U approved list with CE (-U datasheet ver L, ch. 7; an RP-SMA antenna is not), antenna placed away from the stack's copper and cells; Raytac datasheet ver L: 1MV2 = chip antenna, P1MV2 = PCB antenna, U1MV2 = u.FL (the spec called U1MV2 the chip variant until 2026-09-29); all three share one land pattern; Fanstel BT840 is a different pad layout and **not** a drop-in |
| LFCLK | external 32.768 kHz crystal: **Epson FC-135R, CL 9 pF, ±20 ppm** (ESR 50 kΩ max), **12 pF C0G** load caps (2026-10-01) | **not** on-module; internal RC is ±250 ppm; nRF52840 PS v1.11 §5.4.4.3 wants CL ≤12.5 pF, C0 ≤2 pF, ESR ≤100 kΩ |
| Seams | numpad = digits+operators only; arrows+nav on `right`; **mechanical join only** (rev 8) | detaching numpad loses only digits; nothing electrical crosses a seam |
| Lighting | IS31FL3733, common-anode RGB, 1 CS + 3 SW per LED | per-key independent colour, 8-bit PWM per channel; serial-chain parts cost 0.6 mA/LED idle |
| LED current | **~20 mA peak per die**, `RSET` ≈ 42.2 kΩ | safe for any reverse-mount RGB part at 1/12 duty; halves driver heat |
| LED rail | **~5.0 V from a TPS630701 buck-boost on `SYS`, on USB and on battery** (rev 8.1; 4.95–5.15 V; rev 8 had a 5.0 V boost on battery and VBUS on USB); carried to every slot through a latch-off switch | the rail does not move with the source; ≥0.35 V of LED headroom after a 1 m cable (E19) |
| Driver idle | `SDB` + software shutdown, rail stays up | power-gating VCC violates abs-max on `VIO`/SDA/SCL |
| Cells | **alkaline and NiMH AA only; no Li-ion support (2026-09-30)**. Rev 8.1: 4×AA packs, NiMH intended (~4.0–5.8 V), alkaline fits (~6.4 V fresh); rev 8 was 1.9–3.3 V per 2-cell pack. Low-self-discharge NiMH recommended | rev 8's reason (an L91 lithium-primary pair at 3.66 V, over `VDD`'s recommended max) is gone with the LDO; 4 × L91 (~7.2 V at the usual ~1.8 V/cell, unverified) is not checked against rev 8.1 and stays unsupported |
| Overvoltage | **rev 8.1: none (2026-09-30)**: Li-ion is not supported, the worst pack is ~6.4 V and everything on `SYS` is rated ≥16 V; rev 8 had the rev 7 TPS3840PL35 + AO3415A chain per module | reverse polarity and OR stay (LM74610-Q1 per input) |
| Undervoltage | firmware system-off at 4.12 V on the PL40 node (§9); **the hub's TPS3840PL40 turns the battery switch off at 4.0 V on its node** (~4.16 V at the hub input), fed from the pack inputs through Schottkys (rev 8.1) | the supervisor survives its own cut and does not oscillate |
| Battery path | per pack input an LM74610-Q1 + CSD17313Q2 ideal diode, OR-ed into one CSD25402Q3A battery switch onto `SYS`; USB into `SYS` through a second CSD25402Q3A, with priority (rev 8.1, §4) | zero Iq, reverse blocking to −45 V, packs isolated on USB |
| Pack series resistance | ~291 mΩ worst case (pack C, three pogo hops), ≤0.13 V at 0.45 A (rev 8.1) | holder, PTC and contacts dominate; the FETs add ≤41 mΩ |
| Host USB input | **KTS1693** on the host port's USB port board, external divider for a 5.38–5.78 V trip (E22, 2026-10-01), `ISET` 4.99 kΩ (1.82–2.18 A latch) | the LM66200 behind it is 6.0 V abs-max and the MDBT50Q `VBUS` pad 5.8 V; 100 ns turn-off |
| Slot power | **TPS22950L latch-off switch per slot on the hub-side comms board**, `ILIM` 624 Ω (`IHCD` 1.2–1.9 A); on only while its slot holds a module that answers (§6) | a short or a foreign sink costs one latch, not the rail |
| Logic rail | **regulated 3.3 V always**: TPS70933 LDO from `SYS` (rev 8.1) | 5 V never reaches `VDD` |
| Enable defaults | TPS630701 and TPS70933 enabled by wiring; only the expansion LDO is GPIO-gated | on USB with no cells nothing could enable a GPIO-gated regulator |
| LED converter | TPS630701 (fixed 5.0 V) + Coilcraft XFL4020-152ME (rev 8.1) | second source not looked for |
| Pack ESD | **bidirectional** 9 V-standoff TVS per pack (SMF4L9.0CA; rev 8.1: per pack input on the hub, E21) | above a fresh 4×alkaline pack (~6.4 V) |
| D+/D− ESD (host) | USBLC6-2SC6 with its `VBUS` pin on the KTS1693's **protected** side (or NC) | the pin's abs-max is 5.5 V |
| USB CC sense | host port CC1/CC2 to the hub's `AINx` | sets the whole-keyboard LED budget |
| Dial | on `right`'s key board, read by its module controller; behaviors run on the hub | the dial stays where the K860's host keys were |
| Battery lighting | firmware cap ≤250 mA at the LED rail **for the whole keyboard** (rev 8; was per module), ~49 % of full white; **kept 2026-09-26** | one pack path carries the whole load (§4); more packs add runtime, not brightness. Rejected: ~400 mA above 2.30 V (~1.04 A per pack) and full white above 2.30 V (~1.31 A, 87 % of the PTC's 40 °C hold): less margin on the pack parts and chain contacts, shorter runtime |
| Profiles | 9, `CONFIG_BT_MAX_PAIRED=9` (no BLE split to subtract) | one host connection at a time |
| Selector | **detented** encoder, Bourns PEC11R **24 detents / 24 pulses** with push switch, preview-then-commit | Bourns states both switches open at every detent when pulses = detents |
| RGB LED | SunLED XZMDKCBDDG45S-9, common anode (pin 2; cathodes 1 R, 3 B, 4 G), reverse-mount PLCC4; second sources Inolux IN-P32TRRRGB / QT-Brightek QBLP677R-RGB on a combined key-board footprint, feasibility open (P1) | datasheet-verified: 30 mA DC, Vf max at 20 mA 2.5 / 4.0 / 4.1 V; HBM only 250 V on blue |
| Dial duty | volume default; profile picker on Fn layer | daily use is volume |
| Profile display | light number-row keys 1–9; **glow around caps is enough** | no part, no pins, no case window |
| Deep sleep | stock ZMK sleep on the hub; **a keypress on any module wakes it** through that module's `INT` (rev 8) | rev 7's untethered-sleep limitation is gone with the split |
| Rollover | full NKRO, every key independent | diode per key; `CONFIG_ZMK_HID_REPORT_TYPE_NKRO=y` |
| Mechanical | in scope, palm rest and hub enclosure included | it defines the K860 silhouette |
| Case | **FDM, ASA** (2026-09-29), printed on the user's Bambu Lab H2S (340 × 320 × 340 mm) or Prusa CORE One (250 × 220 × 270 mm), one piece per module; ~1.6 mm seam walls, 2 mm hub walls; **M2 heat-set brass inserts** | both printers are enclosed with a heated chamber (ASA warps without one); a 233 mm deep module fits either bed; no carbon-fibre or metal-filled filament near the hub antenna |
| Plate | **1.5 mm FR4, no copper**, plate-mount stabilisers | same fab as the PCB |
| Row dish | flat boards; dish from per-module tilt + sculpted keycap rows | a stepped plate needs a stepped PCB, see §11 |
| Distribution | open source, others may build | second sources throughout, build guide with a repair section (symptom → board) and a spares list, no panelisation |
| Spares | listed in the build guide, **every item optional**: 1 hub-side and 1 module-side comms board, 1 USB port board, 1 battery module, 1 cable set | keeps a first order cheap |
| Parts sourcing | **Mouser Europe or a similar European distributor (DigiKey, Farnell, TME, Romanian distributors)**; LCSC part numbers are kept as references only | the build is sourced in Europe |

Rejected in rev 8 (reasons in [`docs/01-architecture.md`](../docs/01-architecture.md)
§6): the rev 5–7 per-module core with wired + BLE split; raw matrix lines over the
link cable; the TCA8418 keypad scanner (25–40 ms per press); a hub-scanned GPIO
expander (register polling cannot cross a radio link); a module MCU speaking a
UART split protocol; custom radio or optical links for rev A (a module linked
without wires needs its own cells, so it stops being dumb; kept as future comms
boards); modules daisy-chained through the seams (shared bus, hot-plug glitches);
magnetic breakaway cables for rev A (custom cable); charging the cells from Qi;
the LM66100 as the per-pack ideal diode (210 mΩ max at 1.8 V).

Rejected earlier and still rejected: Choc v2, addressable RGB chain, 7-segment
digit, magnetic angle sensor, absolute 9-position rotary, shine-through caps
required, aluminium plate, printed plate, lithium primaries, the LED driver on the
main controller board (28 nets and 320 mA SW currents through a connector).

## 4. Power

Board in brackets: `[BAT]` battery module, `[USB]` USB port board, `[HUB]` hub
core, `[COM-H]` hub-side comms board, `[COM-M]` module-side comms board, `[KEY]`
key board.

**Battery architecture, rev 8.1 (decided 2026-09-30; parts and values closed
2026-10-01, E21).**
- **Up to 3 battery modules, each 4×AA** in series, meant for **NiMH** (1.2 V nominal:
  4.8 V pack, ~5.6–5.8 V fresh off the charger, ~4.0 V empty at 1.0 V/cell;
  typical chemistry figures, no cell datasheet read). Alkalines still fit (~6.4 V
  fresh), so every pack input tolerates ≥6.5 V. **No Li-ion support (2026-09-30)**:
  Li-ion AA-size cells (14500) are neither supported nor designed against. Cells are
  charged outside the keyboard.
- **Battery modules are passive**: a 4×AA holder (**MPD BC4AAPC**, decided 2026-09-30: MPD drawing rev F, 57.2 × 61.3 × 15.5 mm, 2 PC pins Ø0.50 26.1 mm apart, polypropylene UL94-HB, nickel-plated spring-steel contacts, **<50 mΩ** +/− per EIA-540J000, −10…+100 °C; cells along x, centred at (−5, −15): 1.35 mm clear of the magnet shelves, 3.9 mm of the cap board, 2.0 mm under the board above; rejected BH4AAPC (UL94V-0 nylon, 15.88 mm, no contact resistance stated) and BK-1279-PC8 (8 pins, 16.7 mm); EU stock unchecked), **one PTC** in the pack lead (a
  lifted module's pins, ~6 mm proud, carry its raw pack, PTC-limited), the chain line
  shift and the pogo seam parts (riser, strip, target discs). No active parts.
- **Each pack has its own chain line to the hub.** Chain pinout (reversal-safe, pin
  k meets 13−k): **1 `PACK_A`, 2 GND, 3 `PACK_B`, 4 GND, 5 `PACK_C`, 6 `AUX_5V`, 7
  `AUX_5V`, 8 `PACK_C`, 9 GND, 10 `PACK_B`, 11 GND, 12 `PACK_A`**. Every module
  **shifts the lines by one**: its own pack drives its pins' `PACK_A`; the `PACK_A`
  and `PACK_B` arriving on its discs from below leave on its pins as `PACK_B` and
  `PACK_C`; the `PACK_C` from below ends there. So identical modules land on hub
  inputs A, B, C by position, and a 4th module is simply unconnected.
- **The hub does the rest** on one `SYS` rail (below): per pack input ESD, reverse
  blocking and an ideal-diode OR; one UVLO; USB priority; a buck-boost for the ~5.0 V
  LED rail (the pack spans ~4.0–6.4 V around it) and an LDO for VSYS 3.3 V.
- **Hub topology (decided 2026-09-30): one `SYS` rail.** Per pack input (A, B, C):
  a TVS, then a **TI LM74610-Q1** zero-Iq ideal-diode controller with one N-FET
  (SNOSCZ1B, `build/ds/lm74610-q1.pdf`: not ground-referenced, **zero Iq**, reverse
  polarity to −45 V, 2 µs reverse response, "can be used in OR-ing", VSSOP-8; its
  charge pump needs the FET body diode's forward drop ≥0.48 V). The three outputs OR
  into `VBAT`. **One shared high-side P-FET switch** takes `VBAT` to `SYS`, on only
  when the power switch is on AND the UVLO supervisor (powered from the pack inputs
  through a Schottky OR, so it stays alive after the cut and `PACK_SENSE` goes; first
  on `VBAT`, moved 2026-10-01 after the E21 sim) reads OK AND `VBUS_IN` is absent:
  **USB has priority**, and a second P-FET (below) feeds `VBUS_IN` into `SYS`; on USB the P-FET's body diode
  is reverse-biased by any pack above `SYS`, and the ideal diodes block the other
  direction. **No overvoltage cut**: with Li-ion unsupported the worst pack is a
  fresh 4×alkaline at ~6.4 V, and everything on `SYS` is rated far above it. From
  `SYS`: a **TI TPS63070** buck-boost makes the ~5.0 V LED rail on USB and on battery
  (SLVSC58B: 2–16 V in, 20 V abs max, 2 A out at 4 V → 5 V, 54/103 µA PFM
  quiescent) and a **TI TPS70933** LDO makes VSYS 3.3 V (SBVS186H: 2.7–30 V in,
  150 mA, 1.3/2.05 µA ground current, dropout 295/650 mV at 50 mA). **Removed**: the
  TPS61099 / MAX17222 logic boost, the TLV75733P USB LDO, both TPS2116 muxes, the
  TPS61023 LED boost and its PR1 threshold divider (E3), `PACK_EN`/`PACK_SENSE`.
  Rejected: the **LM74720-Q1** per input (first chosen the same day: 3–65 V, OV cut,
  ≤35 µA, but an internal boost needing an inductor and a 1 µF cap per channel plus
  2 FETs), a **Schottky OR** (~0.3–0.4 V at 0.45 A, generic figure: ~7–9 % of runtime
  and ~0.3 V LDO headroom at the cutoff), rev 8's split rails re-parted (a TPS2121
  priority mux draws 300 µA typ from its active input, a third of E7's ~0.9 mA, and
  has no reverse protection) and rev 7-style discrete protection per input. The
  LM7480-Q1 was passed over for ~400 µA; ADI's LTC4417 could not be read.
- **Hub power parts (decided 2026-09-30, all TI datasheets in `build/ds/`):**
  - Pack inputs ×3: **SMF4L9.0CA** TVS (carried over from rev 8's pack ESD: 9 V
    standoff, above a fresh 4×alkaline's ~6.4 V) → **LM74610-Q1** + **TI CSD17313Q2**
    N-FET (30 V, VGS +10/−8 V, Vth 0.9/1.3/1.8 V, 26/32 mΩ at 4.5 V, body diode
    0.65 V at 125 °C per TI's LM74610 table, SON 2 × 2 mm) + a **1 µF X7R ≥16 V**
    charge-pump cap (decided 2026-10-01; the datasheet's 220 nF–4.7 µF range, timing
    scales with C, duty ~98 % for any value: 1.2 s on / 25 ms body diode; first charge
    from empty ~45–60 ms vs ~100–155 ms with TI's 2.2 µF example; rejected 2.2 µF (the
    longest dropout windows) and 0.47 µF (2.1× the minimum before X7R derating, dips
    twice as often)). Below ~1 mA (idle) the FET acts as a plain diode.
  - Battery switch `VBAT` → `SYS`: **TI CSD25402Q3A** P-FET (−20 V, VGS ±12 V, Vth
    −0.65/−0.90/−1.15 V, 13.3 mΩ at −2.5 V, 7.7/8.9 mΩ at −4.5 V, SON 3.3 × 3.3 mm),
    gate pulled up to `VBAT` through **1 MΩ** (decided 2026-10-01: 4.4–6.4 µA from the
    packs while Qb is on; 470 kΩ would double that), pulled down through **two series
    N-FETs**: N1 from the UVLO output through the **power switch** (**4.7 MΩ pull-down**,
    decided 2026-10-01: the PL40 output feeds it through the sense Schottkys whenever the
    switch is on, 0.9–1.3 µA, cut +~22 mV; 1 MΩ: 4–6 µA, +~52 mV; 10 MΩ left 0.57 V on
    the gate with an assumed 100 MΩ leak across the open switch, unverified), N2 from
    NOT-VBUS (**R2 = 1 MΩ pull-up to `VBAT`**, decided 2026-10-01; grounded by N3 when
    USB is present, so the packs feed 4–6.4 µA into R2 while USB is in).
  - UVLO: **TPS3840PL40** (SNVSB03E: 1.5–10 V, 300/700 nA, VIT− 4.0 V
    ±1.5 %, hysteresis 175/200/225 mV → back on at ~4.2 V, push-pull active-low,
    SOT-23-5): cut at ~1.0 V/cell. **`VDD` = the pack inputs through one Schottky each
    (decided 2026-10-01)**: a **Diodes BAT54C-7-F** (common cathode = the sense node) for
    inputs A and B, a **BAT54** for C, then **10 kΩ to `VDD` with 1 µF on `VDD`**
    (decided 2026-10-01, E21 1b). The 10 kΩ protects the 12 V abs max `VDD` from the
    SMF4L9.0CA clamp (VC 15.4 V at 26.4 A): straight onto 100 nF, `VDD` reached 10.6 V
    for a 0.1 µs clamp and 15.0 V for 1 µs; through 10 kΩ into 1 µF it stays ≤6.30 V for
    20 µs and ≤7.1 V for 1 ms (sim `tvs`); it adds ~1.6 µA × 10 kΩ = +16 mV to the cut
    and limits `VDD` slew at a pack insert to ≤0.6 mV/µs (EC conditions ≤100 mV/µs).
    The 1 µF holds the sense node at the packs' recent peak, decaying at ~1.6 V/s, which
    sets the firmware's lighting-cut window below (~166 ms); a genuine cut under a
    sudden heavy load comes up to ~0.17 s late (harmless for NiMH). Rejected 100 nF
    (~15 ms window) and 470 nF (~75 ms), and 1 kΩ (τ 1 ms: a 1 ms clamp reaches ~12 V).
    Rev 8.1 first put `VDD` on
    `VBAT`, after the LM74610s; the switchover sim showed it trips whenever an LM74610
    runs on its body diode (below). The Schottky adds its drop at 0.3–0.7 µA
    (~0.12 V at 25 °C, ~0.2 V at −20 °C; e14 BAT54 model fitted to DS11005 Fig. 1), so
    the cut sits at ~4.12 V at the hub input (~1.03 V/cell plus the series-path IR) and
    re-arms at ~4.32 V. On USB it reads the real packs (`VBAT` is pulled up from `SYS`
    through Qb's body diode there). Rejected: an RC filter (47 kΩ + 22 µF) on a `VBAT`
    sense (`VBAT` rests ~0.42 V under the pack below ~1 mA, so a switch-on needs a
    ≥4.62 V pack: the sim's 4.4 V switch-on never starts), replacing the LM74610 (the
    ≥6.5 V candidates read draw 80–400 µA). `MR` unused (its internal 100 kΩ pull-up would
    draw 40–64 µA if held low). **Firmware first stage (decided 2026-10-01, E21 1c):**
    the SAADC reads **the PL40's own `VDD` node** (after the 10 kΩ, on the 1 µF), so it
    compares against exactly what the hardware cut compares, on USB too and outside the
    LM74610 windows (rejected: `VBAT`, which reads `SYS` through Qb's body diode on USB
    and ~0.77 V low in every body-diode window; the Schottky cathode, whose reading
    depends on load history; per-pack dividers, which need 2 more AIN pads). Divider
    **200 kΩ / 100 kΩ 1 %** (1/3: 4.0 V → 1.33 V, 8.9 V → 2.97 V, under `VDD`; source
    66.7 kΩ → TACQ 10 µs), switched on the high side by a **TI CSD25483F4** P-FET (−20 V,
    VGS −12 V, Vth −0.70/−0.95/−1.20 V, IDSS ≤100 nA at −16 V, IGSS ≤50 nA, LGA
    1.0 × 0.6 mm, reflow) with a **470 kΩ** gate pull-up to the node, pulled down by half
    of a third **DMN63D8LDW** from `BAT_DIV_EN`; a switch is needed because nRF52840
    I/O ≤ `VDD` + 0.3 V (PS v1.11 §9) and the node stays up with the hub off. Rejected
    rev 7's AO3415A: IDSS ≤1 µA at 25 °C / ≤5 µA at 55 °C would load the PL40 pin (window
    ~166 → ~40 ms, cut +~90 mV). A read (divider on ≤100 µs) drains the 1 µF by ~2 mV.
    **Bring-up calibration**: bench supply on one pack input, DMM on the node, firmware
    stores the SAADC gain factor (SAADC gain error ±3 % at 1/6 uncalibrated, +0.02 %/°C,
    offset ±2 LSB10 after offset calibration; divider error absorbed). Residual ±0.7 % +
    21 mV, so the thresholds sit on the node: **system-off 4.12 V** (fires 4.09–4.17 V,
    above the 3.94–4.06 V cut; pack ~4.3 V ≈ 1.07 V/cell), **lighting off 4.25 V**,
    **lighting scale-down start 4.40 V** (loaded; tuned on hardware, §9). Uncalibrated
    with 0.1 % parts the system-off would need 4.24 V and fire up to ~4.43 V. Rejected: PL38 (0.5 V over the LDO's
    worst dropout, cell-reversal risk), PL42 (runtime).
  - USB into `SYS`: a second **CSD25402Q3A** "Qu", source on `SYS`, drain on `VBUS_IN`
    (body diode VBUS→SYS, blocking SYS→VBUS), turned on by N4 when USB is present;
    off-state leak = its IDSS (≤1 µA at 25 °C; no hot limit given); a **100 kΩ
    bleeder** on `VBUS_IN` (decided 2026-10-01) holds `VBUS_IN` under the PL43's
    re-detect level (worst ~4.41 V) for up to 44 µA of leak, where 1 MΩ allowed only
    4.4 µA (a phantom USB detect turns Qb off and oscillates); costs 50 µA from USB only. **Sequencing (decided 2026-10-01):** Qu's gate pull-up
    is **10 kΩ to `SYS`** (off in ~25 µs at unplug; ~0.5 mA from USB while on), and
    **N4's gate is fed from the PL43 output through 2.2 MΩ with 22 nF to GND and a
    BAT54 back to the PL43 output** (Qu turns on ~9–22 ms after USB appears, once Qb is
    off; off again within ~5 µs at unplug). The cap was 10 nF until the 2026-10-01
    corner sim: with N4 Vth 0.8 V, Qb Vth −0.65 V, Qb Ciss 1790 pF (all datasheet
    limits) and 10 nF −10 %, Qu turned on 0.84 ms before Qb was off and a 6.4 V
    alkaline drove `VBUS_IN` to 6.1 V; with 22 nF the worst corner keeps 3.4 ms of margin
    (Qb off 5.5 ms, Qu on 8.9 ms). While Qu waits, `SYS` runs on Qu's body
    diode (sim: ≥4.34 V). Rejected: the 10 kΩ alone (a fresh 4×alkaline still drives
    `VBUS_IN` to ~6.2 V for ~3 ms at plug-in), an active P-FET pull-up on Qb's gate
    (shortens, does not remove, the plug-in overlap). Rejected for Qu itself: a Schottky
    (drop, and reverse leakage of tens of µA from the packs), a second LM74610 (≥1 mA
    needed to pump).
  - **`SYS` bulk: 100 µF effective at 5 V** (decided 2026-10-01; ceramic parts at
    capture).
  - USB detect: **TPS3840PL43** on `VBUS_IN`, powered by it (zero pack drain):
    absent below 4.3 V, present above ~4.5 V; drives N3 and N4. Covers USB and the
    future Qi `AUX_5V`. Rejected: KTS1693 `ACOK` (misses `AUX_5V`, threshold unread),
    PL45 (rejects weak USB ports).
  - N1–N4: **2 × Diodes DMN63D8LDW** dual N-FET (SOT-363: 30 V, VGS ±20 V, Vth 0.8/
    1.5 V max, IDSS ≤1 µA). Rejected: 4 × 2N7002 (Vth up to 2.5 V).
  - LED rail: **TPS630701** (fixed 5.0 V: ±1 % PWM, +3/−1 % PFM, internal 1.5 MΩ
    feedback, discharge off; **`PS/SYNC` tied high = power save**, decided 2026-10-01:
    the E7 idle figure needs PFM, forced PWM is ~1–5 % efficient at 0.1–1 mA (Fig. 39)
    and its negative current limit runs current from a back-fed rail into `SYS`;
    rejected a GPIO-controlled mode, nothing needs PWM ripple under lighting) with a **Coilcraft XFL4020-152ME** (1.5 µH, 4 × 4 × 2.1 mm,
    Isat 4.6 A, 14.4 mΩ, from TI's Table 5: Coilcraft blocks curl). Load ≤0.35 A at
    5 V: ~0.54 A average / ~0.72 A peak at 3.6 V in; Isat clears the 3.6 A switch limit.
  - VSYS: **TPS70933DBVR** (SOT-23-5).
  - **Series path, worst case (pack C, 3 pogo hops):** holder <50 + PTC ≤140 + pogo
    3 × (10 line + 5 GND) + core↔connector ESQ ~15 + CSD17313Q2 ≤32 + CSD25402Q3A
    ≤8.9 ≈ **~291 mΩ** (pogo 20 mΩ max per pin, 2 per pack line, 4 GND; ESQ assumed
    20 mΩ per contact as in E20): ≤0.13 V at 0.45 A.
  - **Idle current, estimate (E7, 2026-10-01; datasheets only, the §16 µA trace
    replaces it).** Hub in System OFF (ZMK sleep), three key boards powered with the
    module controllers in STANDBY, no lighting, power switch on, typ / worst:
    - LED rail (5.0 V): **TPS22950L 44 / 60 µA per slot while on** (SLVSFJ2B §7.5;
      ×3 = 132 / 180 µA, ~88 % of the idle), IS31FL3733 shutdown 2 / 5 µA each (Rev. G,
      at 3.6 V; 5 V not given), MSPM0G3505 STANDBY1 1.5 / 4 µA each (SLASEX6C §7.5.2,
      25 °C, "GPIOA enabled": the matrix wake pins must work in STANDBY, checked at
      key-board capture), TPS7A0233 25 / 46 nA each, slot TVS0500 ≤5.5 nA each (below):
      **~143 / ~207 µA**. From `SYS` through the TPS630701: ~250 µA typ (Fig. 38, PFM,
      25 °C: ~60–65 % at 0.1–0.2 mA out, VIN 4.2–5 V; IQ 54 µA into VIN + 5 µA into
      VOUT); worst ~440 µA (IQ 103 + 9 µA, 5.15 V, `SYS` 3.9 V at the end of a pack,
      85 % switching efficiency assumed).
    - VSYS 3.3 V: nRF52840 System OFF 0.40 µA (PS v1.11, typ only, 3 V), TCA9548A
      standby 0.1 / 2 µA, TPS70933 IGND 1.3 / 2.05 µA: **~1.8 / ~4.5 µA**. An e-marked
      cable adds ≤~15 µA per slot (220 kΩ `INT` pull-up into its Ra; most USB 2.0
      cables carry none).
    - Battery path: Qb pull-up 4.4–6.4 µA, N1 pull-down 0.9–1.3 µA, PL40 0.3 / 0.7 µA,
      CSD25483F4 ≤0.1 µA, LM74610 0, the off DMN63D8LDW halves (N3, N4, divider) and
      Qu ≤1 µA each (max at 16–30 V, typ not given), SMF4L9.0CA ≤5 µA each at 9 V:
      **~6.5 / ~28 µA**.
    - **Total ~0.26 mA typ, ~0.47 mA worst.** Per 4×AA LSD NiMH pack (no cell
      datasheet read: ~1900 mAh minimum / 2000 typical is the usual LSD AA rating, and
      ~1700 mAh usable to the 1.03 V/cell cut after 6 months of self-discharge, both
      unverified): **~9 months typ / ~5 months worst on one pack**, ~18 / ~10 on two,
      ~27 / ~15 on three (packs in OR add). The ≥6-month idle target is 0.39 mA per
      pack: met typically on one pack, in the worst case from two.
    - At idle (<1 mA) the LM74610 FET is a plain diode (`SYS` ~0.42–0.6 V under the
      pack): current-neutral, it only lowers the converter's VIN. Under load the 25 ms
      body-diode phase every ~1.2 s (~2 % of the time, ~0.77 V) raises the converter's
      input current ~17 % in those windows: ~0.35 % of runtime, negligible.
    - Power switch off (storage): PL40 + its Schottky, the SMF4L9.0CA and Qb/`SYS`
      leakage: ~1 µA typ, ≤~17 µA max: years.
    - Not estimated: the hub awake and idle with BLE connected before ZMK's sleep
      timeout (firmware, measured in 7a), and 85 °C (MSPM0 STANDBY up to 40 µA each,
      TPS22950L off-state up to 9 µA).
    - **Slot VBUS TVS → TI TVS0500 (decided 2026-10-01).** The six slot-VBUS TVS (both
      comms-board populations) sit on the LED rail, which stays live on battery and in
      sleep; the SMF6.0A's IR is given only at 6 V (≤400 µA) with no 5 V figure (up to
      ~2.4 mA for six). TVS0500 (SLVSED2C): ILEAK ≤5.5 nA at 5 V 27 °C, ≤220 nA at
      85 °C, VBR 7.5–8.4 V, clamp 9.2 V at 43 A 8/20 µs (SMF6.0A 10.3 V at 19.4 A), IEC
      61000-4-2 ±24 kV contact, DC breakdown current ≤50 mA, WSON-6 2 × 2 mm (DRV, stock
      `Power_Protection:TVS0500DRV` + `Package_SON:WSON-6-1EP_2x2mm_P0.65mm_EP1x1.6mm`,
      land pattern checked against TI's DRV0006A at capture). Its 5 V VRWM is under the
      rail's 5.15 V PFM maximum, but VBR min is 7.5 V. Rising edges faster than 2.5 V/µs
      (a cable plugged onto a live slot) clamp for a few µs, harmless (§8.5.3); the
      TPS22950L's soft start is far slower. The SMF6.0A stays on the host USB port
      board (behind the KTS1693, where sources reach 5.78 V; 5.95 V before E22). Rejected: TVS0701 (VBR
      ≥9.3 V, clamp 11–11.7 V, IEC ±8 kV), keeping the SMF6.0A and measuring.
  - **Switchover sim (E21, 2026-10-01; `tools/sim/e21_switchover.py`, case set `fix3`
    = the values above; per-case data and every model number in `build/sim/e21/`,
    `notes.md`).** ngspice; behavioural LM74610 (Vcap 6.3/5.15 V, Fig. 8 charge
    current × 40/46, 0.95 µA, ~2 ms gate slew, 2 µs reverse turn-off) and TPS3840s
    (tP_HL 30 µs, tD 50 µs, tSTRT 350 µs), level-1 FETs from the datasheet Vth/RDS/C,
    LED rail as constant power (rail × 5 V / 0.9), TPS70933 26 mA with a 13 Ω dropout,
    packs as V + R (0.35 Ω NiMH, 0.6 Ω alkaline incl. holder, PTC, pogo, ESQ). Results:
    - Whenever a pack takes over (unplug, switch-on, pack swap) its LM74610 starts with
      Vcap empty (it drains in ~7 s idle) and runs on the CSD17313Q2's body diode for
      **~45–60 ms**, then 25 ms every ~1.2 s, at ~0.77 V drop (0.45 A, 25 °C).
    - Unplug at the 250 mA cap, 4.4–6.4 V packs: 1 detector edge, no UVLO trip,
      `VBUS_IN` ≤4.98 V, Qb on in 110–200 µs; `SYS` ≥3.39 V and VSYS ≥3.06 V at 4.4 V
      (under 3.64 V for 59 ms), `SYS` ≥3.93 V from 4.9 V up.
    - Unplug at the ~0.8 A USB rail: no trip for packs ≥4.7 V (`SYS` ≥3.39 V); lower
      packs need the firmware lighting cut (below).
    - Plug-in, 4.4–6.4 V, including the N4/Qb datasheet corners: no Qb/Qu overlap
      (≥3.4 ms margin), `VBUS_IN` ≤5.0 V even with fresh alkalines, `SYS` ≥4.21 V.
    - Pack swap 4.9 → 4.4 V, pack insert, switch-on from 4.4 / 4.7 V, 60 °C at 4.4 V:
      fine. A 4.2 V pack does not start (below the ~4.32 V re-arm), as intended. At
      −20 °C a 4.4 V pack cuts once at 11 ms (the Schottky's ~0.2 V cold drop puts the
      cut at ~4.2 V at the hub input and the 0.61 A draw pulls it there); 4.5 V runs.
    - **Firmware requirement:** at the ~0.8 A USB rail with a low pack (≤4.6 V), the IR
      under ~1.5 A puts the input below the cut and the UVLO cycles (4.4 V: 76 edges
      in 0.6 s, `SYS` down to 1.8 V). Firmware drops the lighting to the 250 mA battery
      cap as soon as the PL43 output falls (a GPIO). It has as long as the PL40's 1 µF
      holds the sense node against the PL40's IDD and its output current into N1's
      pull-down: **~166 ms** (4.4 V pack). With the lighting dropped 100 ms after
      unplug: no cut, `SYS` ≥3.02 V, VSYS ≥2.69 V (above the key boards' 2.31 V VIH).
    - **Accepted:** `SYS` sits ~0.8 V under the pack during every LM74610 body-diode
      window, so near the cut the TPS70933 drops out briefly (VSYS ≥~3.0 V at the
      250 mA cap; nRF52840 runs to 1.7 V; key boards' I2C VIH 0.7 × 3.3 = 2.31 V).
    - The first drawing failed three ways, which set the values above: the UVLO on
      `VBAT` tripped in every body-diode window (unplug at 4.9 V: 77 cut-offs, `SYS`
      1.8 V); a pack back-fed `VBUS_IN` through a slow-off Qu (1 MΩ pull-up) and the
      PL43 re-detected USB (`VBUS_IN` 6.18 V with alkalines); plug-in overlapped Qb
      and Qu for ~3 ms (`VBUS_IN` 6.18 V).
    - Not modelled: layout inductance, cell chemistry dynamics, the KTS1693, `AUX_5V`,
      the LM66200 beyond an ideal diode (its "IRCB 1.4/4 A activation current" row in
      SLVSG04 is unexplained).
- **Module PTC (decided 2026-09-30): Bourns MF-MSMF125/16X** (1812; Bourns MF-MSMF
  datasheet, `build/ds/bourns_mf-msmf.pdf`): 16 V max, hold 1.25 A at 23 °C / 0.95 A
  at 50 °C, trip 2.50 A, 0.4 s max at 8 A, R 0.04 min / 0.14 Ω R1max (≤63 mV at the
  ≤0.45 A pack load), AEC-Q200. Replaces the 6 V PTSLR12066V175. Rejected:
  MF-MSMF110/16X (0.20 Ω), MF-MSMF150/16X (3.0 A trip).
- Chosen over **active 4×AA modules** (per-module protection and a ≥6.5 V ideal
  diode, any number of modules: more parts per module) and **staying at 2×AA** (no
  change). Rejected earlier the same day: board-less modules (the pogo strip, riser
  and discs need a PCB) and paralleling packs directly (packs charge each other;
  lifted pins live without a limit).

```
  [BAT] module 1: 4xAA -[PTC]--> own pins PACK_A ; discs PACK_A, PACK_B --> pins PACK_B, PACK_C
  [BAT] module 2, 3: same (line shift); a 4th module's pack reaches nothing
                                                                                    chain PACK_A/B/C
  [HUB] per input A, B, C: -[SMF4L9.0CA]-[LM74610-Q1 + CSD17313Q2]--+--> VBAT -[Qb CSD25402Q3A]--+--> SYS (100 uF)
        per input: -[BAT54C / BAT54]--+                             |                          |
                                      +-[10k]-+- 1 uF, PL40 node -> TPS3840PL40 -> power sw -> N1 \
                                              |                                      N2 <- NOT USB -> Qb gate
                                              +-[CSD25483F4]-[200k/100k]-> AIN0 (battery reading)
  [USB] host VBUS -[KTS1693 OVP]-[SMF6.0A]--> [HUB] LM66200 IN1 --+
  [Qi, later] AUX_5V (chain) ---------------> [HUB] LM66200 IN2 --+--> VBUS_IN -[Qu CSD25402Q3A]--> SYS
                                    VBUS_IN -> TPS3840PL43 -> N3 (Qb off), N4 (Qu on after ~9-22 ms), GPIO

  SYS -[TPS70933]--> VSYS 3.3 V -> MDBT50Q VDD, TCA9548A, hub pull-ups
  SYS -[TPS630701, 5.0 V]--> LED RAIL ---> [HUB] expansion LDO TLV75733P (gated) -> J_EXP 3V3
                                |
           +--------------------+--------------------+
     [COM-H] TPS22950L    [COM-H] TPS22950L    [COM-H] TPS22950L     (ON = SLOT_EN per slot)
           |                    |                    |
     cable VBUS (TVS0500 at both ends)
           |                    |                    |
     [KEY] IS31FL3733 VCC + LED anodes; TPS7A0233P LDO -> module controller, driver VIO, pull-ups
```

The battery modules carry no active parts, so a reversed cell or a terminal ESD
strike meets the hub's input stage (TVS, LM74610) on the hub base board. The KTS1693
sits on the host port's USB port board, so a surge damages at most a small board. A
slot short or a foreign load latches its own slot switch on a small comms board.

Rules:

- **5 V never reaches VSYS.** VSYS is only the TPS70933's output (2.7–30 V in), so
  `SYS` at a fresh alkaline's ~6.4 V or at USB's ~5 V never reaches `VDD` (3.6 V max,
  3.9 V abs-max). **Rev 2 OR-ed VBUS straight onto VSYS, which feeds `VDD`: the first
  USB plug-in would have destroyed the MCU.**
- **The logic rail is regulated, 3.3 V always (rev 6; rev 8.1 part: TPS70933).** The
  hub's `VDD`, its I2C levels toward the slots and every `AINx` reading are therefore
  independent of which cells are fitted or how flat they are. Dropout is 295/650 mV
  at 50 mA, so VSYS only follows `SYS` down inside the LM74610 body-diode windows near
  the cut (accepted, above).
- **USB has priority and isolates the packs.** With `VBUS_IN` present the PL43 turns
  N3 on, which turns N2 and so Qb off; N4 then turns Qu on after its delay. Every
  LM74610 blocks `SYS`/`VBAT` → pack, and a pack above `SYS` (fresh alkalines over a
  5 V port) cannot pass the off Qb (its body diode points `SYS` → `VBAT`). Zero pack
  current on USB; the PL40 node still reads the packs.
- **Enable pins default on in hardware.** The TPS630701 and the TPS70933 are enabled
  by wiring; only the expansion LDO is GPIO-gated. A GPIO may pull an enable low,
  never be required to pull one high. On USB with no cells the MCU has no supply
  until VSYS runs, so a GPIO-gated logic regulator could never start; a GPIO-gated
  LED rail would leave `VCC` at 0 V while `VIO`, SDA and SCL sit at 3.3 V, the same
  abs-max violation the hot-unplug rule below guards against, at every boot.
- **The LED rail is the TPS630701's output on USB and on battery.** Fixed 5.0 V (±1 %
  PWM, +3/−1 % PFM: 4.95–5.15 V), buck or boost as `SYS` requires, so the rail does
  not move with the source. Rev 8's TPS2116 priority mux, its `PR1` divider (E3) and
  the switchover bulk are gone.
- **`VIO` of the LED driver ties to the key board's 3.3 V** (rev 8; was `VSYS` on
  the core side of a cable). No I2C level translator: pin 39 is an input-logic
  reference and the datasheet's own app circuit does exactly this.
- **The driver's VCC rails are never power-gated in normal operation.** Abs-max is
  "voltage at any input pin, VCC + 0.3 V", so collapsing VCC while `VIO`/SDA/SCL sit
  at 3.3 V is a violation on every transition. Idle is `SDB` low plus software
  shutdown, which is µA-class. The TPS630701's quiescent current and the slot
  switches' are then always paid (E7 estimate: ~0.26 mA typ for the keyboard).
- **Undervoltage, two stages (rev 8.1).** Firmware reads the PL40 node on the SAADC:
  lighting scale-down from 4.40 V, lighting off at 4.25 V, **system-off at 4.12 V**
  (drives `SDB` low, drops BLE cleanly; thresholds and calibration in §9 and the UVLO
  bullet above). As a backstop the **TPS3840PL40 turns Qb off at 4.0 V ±1.5 % on its
  node** (~4.16 V at the hub input, ~1.03 V/cell plus the path IR) and re-arms ~200 mV
  higher. It is fed from the pack inputs ahead of the OR, so it survives its own cut
  and does not oscillate. On battery the cut removes `SYS`: hub, LED rail and every
  key board die together, and on each key board `VIO` is an LDO output from `VCC`'s
  own net, so `VCC` never falls below `VIO`. On USB nothing changes. **Rev 2 put UVLO
  on boost EN alone, which collapsed driver VCC under a live `VIO` and left the MCU
  draining the cells.**
- **Reverse polarity: blocked per pack input on the hub** (rev 8.1). The LM74610-Q1
  turns its FET off within 2 µs of reverse voltage and blocks to −45 V; a reversed
  pack also reverse-biases its sense Schottky, so the PL40 node never goes negative.
  A single reversed cell only lowers its pack.
- **No overvoltage cut and no gate clamps (rev 8.1).** With Li-ion unsupported the
  worst input is a fresh 4×alkaline pack at ~6.4 V: CSD17313Q2 30 V (VGS +10/−8 V),
  CSD25402Q3A −20 V (VGS ±12 V), TPS630701 2–16 V in (20 V abs-max), TPS70933 30 V,
  TPS3840 10 V recommended; no gate sees more than the pack. Rev 7/8's per-pack
  TPS3840PL35 + AO3415A OVP, its gate RC and the 6.2 V gate zeners are gone.
- **Pack-input ESD: a bidirectional 9 V-standoff TVS per pack input on the hub**
  (Littelfuse SMF4L9.0CA: VBR 10.0–11.1 V, IR ≤5 µA at 9 V, VC 15.4 V at 26.4 A,
  400 W at 10/1000 µs, SOD-123FL), which does not conduct at a fresh alkaline's
  ~6.4 V. Its 15.4 V clamp exceeds the TPS3840's 12 V abs-max, so the PL40's `VDD`
  takes the 10 kΩ + 1 µF above (≤7.1 V for a 1 ms clamp). **It must be
  bidirectional**: it sits ahead of the LM74610's reverse block, so a unidirectional
  part forward-conducts into a reversed pack with only the PTC to limit it.
- **Host USB input OVP.** The host USB-C socket's VBUS goes through a **Kinetic
  KTS1693** integrated OVP switch on the USB port board, unchanged from rev 7.
  Behind it the LM66200 is **6.0 V abs-max** and the MDBT50Q's `VBUS` pad 5.8 V
  (nRF52840 PS v1.11 §9; 5.5 V recommended); everything after `VBUS_IN` is rated ≥12 V. The numbers that shape the circuit:
  - **Ratings.** IN 30 V abs-max, internal clamp 32 V, IEC 61000-4-5 ±110 V surge
    and IEC 61000-4-2 ±8 kV contact on IN, 9 mΩ typ / 13 mΩ max, 8 A continuous.
    Turn-off **100 ns** after VIN crosses OVLO. Turn-on only after a **0.7 ms
    debounce**, then a ~2 ms soft start.
  - **Trip point: external divider (E22, decided 2026-10-01).** The internal OVLO
    (5.77–6.13 V) can exceed 6.0 V. With **R1 = 100 kΩ, R2 = 27.4 kΩ (0.1 %)** against
    the 1.162–1.238 V reference (±3.2 %), ±0.16 % from the resistor ratio and ±100 nA
    pin leakage (±10 mV), the trip is **5.38–5.78 V (5.58 V typ)**: under the MDBT50Q
    `VBUS` pad's 5.8 V abs-max in every corner, at the cost of refusing a compliant PD
    source at the top of vSafe5V (5.38–5.5 V) on a unit at the low reference corner
    (it then runs on battery); USB 2.0 ports (≤5.25 V) and typical chargers are
    unaffected. The reference spread alone is 6.5 %, so no divider fits between 5.5 and
    5.8 V. Was 26.4 kΩ (5.55–5.95 V, rev 7): it passed 5.80–5.95 V onto the pad.
    OVLO pin 4.30 V at 20 V in (20 V abs-max), 39 µA at 5 V. Rejected: accepting the
    band (the risk lands on the hub's MCU module), the TI TPS25947 (OVLO ±1.7 %: 5.54–
    5.77 V with 100 k / 27.0 k, but 1.2 µs turn-off against the KTS1693's 100 ns, a
    USB port board redesign and 430–610 µA on USB; stays the P7 second-source
    candidate), a series Schottky to the pad (the nRF52840 allows ≤6 Ω on `VBUS`,
    PS §5.3.8.6, and the pad needs ≥4.35 V).
  - **`ISET` 4.99 kΩ 1 %: 1.82–2.18 A latch** (Table 1, 0–70 °C), under the
    LM66200's 2.5 A abs-max behind it. With `OC_MODE` low the switch stays fully on
    for the 5–10 ms `tOCP_DEB` before it latches (p. 11): one ≤10 ms pulse passes,
    accepted (E9). `EN` tied to GND; the latch clears on unplug. `ACOK` to a GPIO
    reports the trip. The whole keyboard on the host port is ~0.8 A at full white
    with 150 mA of expansion load (below).
  - **Around it.** 0.1 µF (50 V) on IN, ≥1 µF on OUT, then the SMF6.0A and the
    10 µF bulk. TVS2200 footprint at the connector, not fitted. 140–180 µA while
    VBUS is present.
  - **Package.** WLCSP-20, 0.4 mm pitch, **not hand-solderable**; only the USB port
    board carries it (§12). Second source still owed (P7: TPS25947, different
    footprint).
  - **Rejected: discrete TLV6713 + AO3401A** (simulated: a 5 → 20 V step while
    connected reached 16.8 V at the output), NCP361, TPD1S514, LM74502, MAX4987AE
    (reasons in the parts list).
- **Packs are never directly paralleled.** Each pack has its own chain line and its
  own LM74610 into `VBAT`. **OR-ing does not share load:** the highest pack carries
  all of it until the packs equalise, then they alternate. The keyboard runs
  correctly on one pack alone, and every per-pack part is sized for the whole
  keyboard's battery load. More modules add runtime, not current, and the 250 mA
  lighting cap holds however many are fitted. **Rev 2 claimed two packs halve the
  C-rate; they do not.**
- **Battery chain.** Pinout and line shift at the top of this section; series path
  ~291 mΩ worst case (above). **Part family (M10, decided
  2026-09-29): Samtec ESQ elevated socket with square stack-through tails, socket
  on each board's top face, tails down** into the socket of the layer below (§11).
  **Battery seams on pogo pins (decided 2026-09-29, M10)**: every seam below the
  connector layer (connector ↔ battery module ↔ battery module …) opens on each cell
  swap, and ESQ is rated only **100 mating cycles with 10 µ″ gold** (catalog page;
  no figure for `-G`); spring pins are rated **100 000–1 000 000 cycles**. So the
  chain crosses those seams on **12 pogo pins in the same 2×6, 2.54 mm order**
  (reversal-safe as before). **Part (decided 2026-09-30): Mill-Max
  827-22-012-10-004101**, a through-hole 2×6 spring-loaded strip (Mill-Max drawing
  827-22-0XX-10-004101 and part data; spring guide MM-ISSPG rev 3.0): 9.96 mm above
  its board free, tails 2.92 mm (Ø0.64) below, insulator 15.24 × 5.08 × 2.79 mm,
  plunger Ø1.07, barrel Ø1.5; **stroke 2.29 mm (mid 1.14 mm)**, spring #77 (BeCu):
  5 g preload, **60 g at mid-stroke**; 7 A at 30 °C rise (5.6 A derated), **20 mΩ
  max**; 100 000–1 000 000 cycles; plating `-22` (20 µ″ gold plunger and body).
  Working height 8.81 mm, so the strip's board sits ~8.7 mm over the battery board
  (riser below). Twelve pins push
  ~7.1 N at mid-stroke. Chosen over the 1.4 mm-stroke strips (818 through-hole /
  814 SMT, spring #75, 60 g mid, 10 g preload) for about twice the window for FDM
  seam stack-up at the same force, over its SMT twin 820-22-012-30-001191 (7.32 mm,
  the solder pads alone take the side load of seating a module), over the 3 mm 839
  (spring #89, 100 g mid: ~11.8 N against an unmeasured magnet pull), and over
  loose 0906 pins (12 parts aligned only by their holes). EU stock not checked. The
  strip stands **pins up** on a riser on each battery board, landing on **gold target
  discs on the underside of the board above** (the next battery board, or the
  connector layer's carrier). **Targets (decided 2026-09-30): Mill-Max
  1578-0-57-15-00-00-03-0**, 12 per pad field, reflowed onto ENIG pads (Mill-Max PR663
  rev D): solid brass, Ø1.98 mm, 0.63 mm tall ±0.05, **10 µ″ hard gold over nickel**,
  tape and reel; suggested pad Ø2.24 mm (0.30 mm apart at 2.54 mm). Plain ENIG is
  2–5 µ″ soft gold and wears through (rev 7 review, §17a); hard-gold fingers are
  electroplated only at a board edge in one row (JLCPCB gold-finger rules), which a
  mid-board 2×6 field cannot be; JLCPCB offers no full-board hard gold (HASL, ENIG,
  OSP). Rejected: edge fingers with the single-row 825-22-012-10-004101 (moves the
  field to a wall, loses the 2×6 reversal-safe order), full-board hard gold at PCBWay
  (1–10 µ″ standard, second fab, solderability unchecked), plain ENIG. The taller
  1578-1/-3 (0.89/1.40 mm) were rejected for a more exposed live contact under a
  lifted stack and more leverage on the joint. **Riser (decided 2026-09-30): Samtec
  DW-06-17-T-D-254**, a 2×6 "low-cost board spacer" soldered through both the
  battery board and a 1.6 mm cap board (Samtec print XW rev BD): two PBT insulators
  2.54 mm each, **board spacing 0.254″ = 6.45 mm ±0.20** (pins within 0.25 mm of each
  other), 0.64 mm square phosphor-bronze posts, tail 2.79 mm (1.19 mm past the battery
  board), overall 12.19 mm (lead style `-17`, post 2.95 mm above the top insulator,
  1.35 mm past the cap), matte tin (`-T`: both ends soldered). Cap top at 8.05 mm puts
  the strip at mid-stroke on the discs. No mated contact is added, so E20's per-hop
  resistance holds. Through-hole, wave or hand soldering only (not lead-free
  reflow); non-standard, non-returnable, likely bought from Samtec directly
  (sourcing exception, EU stock unknown); current rating not on the catalog page (we
  carry <1 A). Rejected: a pluggable Samtec BCS-106-L-D-TE socket (7.37 mm) + pins in
  a 0.8 mm cap (a mated contact per pin per hop, about doubling E20's per-hop
  figure), an SMT socket + header pair (same cost, parts unread). The old "SMT base
  so the underside stays free" premise was dropped: the tails at (25, 20) end 6.9 mm
  clear of the module below, away from the discs at (25, 28). **The riser stands at the
  chain position (25, 20)**, and its cap board carries the pins to **(25, 28)** [approx], clear of the connector
  layer's through-hole ESQ chain socket at (25, 20), whose cut tails sit under its
  carrier; every board's pads sit at (25, 28). **Pogo seams sit 5 mm under the
  upper board** (2026-09-29), so the upper section's magnet shelf and lip fit under
  its board with no notch; rejected a ~2.5 mm skirt (pins ~3.5 mm proud, but a
  10.5 × 24 mm notch at each magnet in every board). The pins cannot sit recessed:
  mated, their tips touch a board that sits above the seam, so **a lifted-off
  module shows its pins ~6 mm above its rim**; they carry the module's own pack
  (PTC-limited; the module is passive since rev 8.1) and are spring-loaded. The lifted stack shows its target
  discs (0.63 mm) in a 5 mm skirt. Twelve
  pins push ~7.1 N apart at mid-stroke; the magnets' pull through the skins is
  not measured yet (seam test print). The riser base and the pad
  field on one board must not overlap (identical modules: the pins of one meet the
  pads of the next). The core ↔ connector joint (screwed, 44 contacts, rarely
  opened) and the expansion header keep ESQ; the connector layer's ESQ tails are
  cut flush under its carrier (its skirt is ~2 mm now). Per hop: ~10 mΩ per pack
  line (2 pins of ≤20 mΩ) + ~5 mΩ of GND (4 pins), counted in the ~291 mΩ series path. Rejected: keeping
  ESQ on every seam (cycle rating), pogo everywhere (the screwed 44-contact joint
  gains nothing), pins facing down (a tall riser hanging ~6 mm out of a lifted
  section, live when packs in the lifted stack are on).
- **Slot power (rev 8).** Each slot's hub-side comms board takes the LED rail over
  `J_SLOT` and feeds its cable's VBUS through a **TPS22950L** (latch-off, no
  reverse current blocking, `ON` from `SLOT_EN` on `J_SLOT`; its smart pull-down
  keeps it off if the header is unplugged; SLVSFJ2B Table 9-2). **`ILIM` 624 Ω:
  latch-off `IHCD` 1.2–1.9 A** (SLVSFJ2B Table 7.5), unchanged from the rev 7
  downstream link board. The hub turns a slot on at boot and keeps it on only while
  a module controller answers on that slot's I2C channel. **Slot power policy (E18,
  decided 2026-09-26):** no answer within **~200 ms** of power-on turns the slot
  off; while the hub is awake an off slot is **re-probed with ~100 ms of power
  every ~2 s**; while the hub sleeps only slots holding a module stay powered (so a
  keypress can wake it) and empty slots are not probed. A phone, legacy device,
  charge-only cable or looped cable therefore sees ≤~5 % duty while the hub is
  awake and nothing while it sleeps; a new module is found within ~2 s. Accepted:
  plugging a module into a sleeping hub does not wake it. `ACOK` rising while a slot
  is on flags the slot-to-host-port loop (§9). The LED rail is the
  right source because the key boards must run on battery: `VBUS_IN` alone would
  leave them dark without USB. **Load, full white (from the rev 7 Phase 3
  bottom-up, less rev 7's per-core ~30 mA logic, module-controller current
  unverified):** `right` ~0.28 A, `left` ~0.22 A, `numpad` ~0.1 A per slot, all
  under `IHCD`'s 1.2 A minimum.
- **Key board power (rev 8).** The key board takes the slot's VBUS as its only
  supply: IS31FL3733 `VCC` and the LED anodes directly, and a 3.3 V LDO for the
  module controller, the driver's `VIO` and the local I2C pull-ups. `VIO` is an
  LDO output fed from `VCC`'s own net, so it cannot come up before `VCC`. **On a
  collapse it can briefly sit above a falling `VCC`** if the LDO blocks reverse
  current and its output capacitance holds 3.3 V, so the rev 7 series resistors
  stay at the driver: **1 kΩ on `VIO` and `SDB`, 470 Ω on SDA and SCL (E11)**. The
  link's SDA, SCL and `INT` come from the hub, so a link pulled live can also drive
  them into an unpowered key board (below).
- **LED headroom after the cable (E19, 2026-09-26; rev 8.1 part 2026-09-30).** A
  max-bin die needs ~4.5 V at the driver (Vf max 4.1 V green + ~0.4 V driver). The
  slot switch (≤41 mΩ), two GH contacts, the comms boards and ~1 m of cable (VBUS
  and GND, ~0.4 Ω round trip on 28 AWG) drop ~0.1 V at `right`'s 0.28 A. The
  TPS630701's fixed 5.0 V (4.95–5.15 V; SLVSC58B Fig. 40 shows ~5.02–5.04 V in PFM at
  25 °C) leaves **≥0.35 V of headroom** after the cable, under the IS31FL3733's 5.5 V
  maximum. Rev 8's TPS61023 at 750 kΩ / 100 kΩ (4.93–5.19 V) and its unpublished PFM
  offset are gone. Rejected (E19): requiring a heavier or shorter cable (not
  enforceable), Vf-binned LEDs only (narrows sourcing), relying on lower peak current
  on battery (no verified Vf-vs-current curve).
- **`VBUS` must reach the MDBT50Q's `VBUS` pad directly**, not only through the
  power path, or USB and DFU are dead. It arrives from the USB port board on its
  own contacts of the hub core's `J_USB`.
- Set `DCDCEN`. The REG1 inductor and the 32 MHz crystal are inside the module.
- Hub controls: power switch, reset and bootloader buttons are **NKK UB** snap-in panel pushbuttons (2026-10-01, user: easy to press, not minimal): power
  **UB16KKG01N-F** (latching ON-ON, green cap, COM + NO), reset **UB15KKG01N-C** (momentary,
  red), boot **UB15KKG01N-A** (momentary, black); gold contacts 0.1 mA–0.1 A at 20 mV–28 V,
  100 mΩ max, 1.9 N, 2.3 mm travel (1.0 mm proud when latched down), 1M momentary / 200k
  gold electrical; solder lugs, wired to connectors on the core board (part chosen at
  capture), so a button is unplugged and snapped out to replace it (NKK UB catalogue
  D80–D83, `build/ds/buttons/nkk_ub_illum.pdf`; non-illuminated, an LED would cost battery
  current). The power contact carries ~1 µA (4.7 MΩ), under NKK's 0.1 mA gold minimum; gold
  does not oxidise and ~100 mΩ is nothing against 4.7 MΩ, so this is accepted and checked in
  §16. Superseded the same day: Alps SKRTLBE010 tactiles behind pinholes and a C&K PCM12SMTR
  slide in a fingernail pocket (§11). **The power switch sits
  between the PL40 output and N1's gate** (rev 8.1), whose 4.7 MΩ pull-down holds N1
  off when it is open, so off turns Qb off whatever the packs read. Off costs ~1 µA
  (E7) and USB still runs the keyboard, so DFU works with the switch off.
- **Link hot-unplug (rev 8).** Pulling a link cable, or unplugging a comms board,
  powered can leave SDA, SCL or `INT` at 3.3 V while the key board's rails fall.
  **Series resistors where the link enters the key board** (470 Ω on SDA and SCL,
  1 kΩ on `INT`, E11 values carried over) limit the current into the module
  controller's and the driver's clamps while that lasts. The key-board-side I2C
  pull-ups go to the key board's own 3.3 V, so an unpowered key board presents no
  pull-up; the hub's TCA9548A channel for that slot is closed except during a
  transaction. **The hub-side `INT` pull-ups are fed from `SLOT_EN`**, so they are
  off whenever the slot's power is off (§6). The §16 unplug test is the proof.

**Pack current.** Worst case is the whole keyboard at the battery cap near the cut:
250 mA × 5.0 V / 0.9 ≈ 1.39 W into the TPS630701 plus VSYS (~26 mA peak): **~0.37 A
from one pack** at a 4.0 V `SYS`, ~0.45 A while an LM74610 runs on its body diode
(`SYS` ~0.8 V lower); the series path above uses 0.45 A. Inside the MF-MSMF125/16X's
1.25 A hold at 23 °C (0.95 A at 50 °C). At the ~0.8 A USB rail an unplug briefly
draws ~1.5 A until firmware drops the lighting (switchover sim, above).

Budget, whole keyboard, per 4×AA NiMH pack (~2000 mAh, the usual LSD AA rating; no
cell datasheet read). Two packs double the runtime, three triple it. `IOUT` ≈
19.8 mA peak at `RSET = 42.2 kΩ`, `GCC = 255`; `ILED = IOUT/12.75 ≈ 1.55 mA` average
per die at `PWM = 255`; 109 keys × 3 dice = **507 mA at the rail**, over the
250 mA battery cap, so battery lighting tops out near 49 %. Pack current = rail
current × 5.0 V / (4.8 V × 0.9) ≈ 1.16 × rail (TPS630701 Fig. 38: ~89–93 % from 10
to 250 mA out at 4.2–5 V in). Radio, hub MCU and module controllers excluded,
except in the idle row.

| Condition | At rail | From the pack | Runtime per pack |
| --- | --- | --- | --- |
| Idle, no lighting (E7 estimate, §4 power parts) | ~143 µA | ~0.26 mA typ / ~0.47 mA worst | ~9 / ~5 months (~1700 mAh usable after 6 months of self-discharge, unverified); unproven until the §16 trace |
| 10 keys dim (24 %) | 11 mA | 13 mA | ~155 h |
| All 109 at 3 % | 15 mA | 17 mA | ~115 h |
| All 109 at 24 % | 122 mA | 141 mA | ~14 h |
| All 109 at the 250 mA cap (~49 %) | 250 mA | 290 mA | ~6.9 h |

Rev 8 counted two 2×AA modules (4000 mAh at 2.4 V); one 4×AA pack holds the same
four cells, so the runtimes barely moved. A 6-month idle target on NiMH requires
low-self-discharge cells.

On USB the LED budget follows the host port's CC reading (§6). Full white is
~0.51 A at the rail, plus the key boards' logic, plus up to 150 mA of expansion
3V3: ~0.8 A from the host port, inside a 1.5 A advertisement.

## 5. Pin budget

### Hub core

Raytac restricts 21 of the 48 pads to **low-frequency I/O only, ≤10 kHz — no
UART, I2C, SPI or PWM** because they sit near the radio. Restricted (LF-only) pads:
`P0.02 P0.03 P0.09 P0.10 P0.28 P0.29 P0.30 P0.31 P1.01–P1.07 P1.10–P1.15`
(MDBT50Q datasheet version L, §2.5, one pin table for every variant). `P0.09`/`P0.10` need
`CONFIG_NFCT_PINS_AS_GPIOS=y`. 24 full-function pads remain once XL1/XL2 (P0.00,
P0.01) and nRESET (P0.18) are taken.

**Pad assignment (decided 2026-09-29).** Pad numbers from `RF_Module:Raytac_MDBT50Q`;
the left column (pads 1–14) and the inner row (56–61) are all LF-only, the bottom
row (16–29) all full-function, the right column (36–49) full-function except the
three LF pads 50, 52, 54.

| Pad | GPIO | Net | Class | | Pad | GPIO | Net | Class |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 3 | P1.10 | `S0_INT_A` | LF | | 36 | P0.14 | `EXP_SCK` | full |
| 4 | P1.11 | `S0_INT_B` | LF | | 37 | P0.13 | `EXP_MOSI` | full |
| 5 | P1.12 | `S1_INT_A` | LF | | 38 | P0.16 | `EXP_MISO` | full |
| 6 | P1.13 | `S1_INT_B` | LF | | 39 | P0.15 | `EXP_DC` | full |
| 7 | P1.14 | `S2_INT_A` | LF | | 41 | P0.17 | `EXP_CS0` | full |
| 8 | P1.15 | `S2_INT_B` | LF | | 42 | P0.19 | `EXP_CS1` | full |
| 9 | P0.03 | `S0_SLOT_EN` | LF | | 43 | P0.21 | `EXP_CS2` | full |
| 10 | P0.29 | `CC2_SENSE` (AIN5) | LF | | 44 | P0.20 | `EXP_CS3` | full |
| 11 | P0.02 | `VBAT_SENSE` (AIN0) | LF | | 45 | P0.23 | `EXP_SDA` | full |
| 12 | P0.31 | `CC1_SENSE` (AIN7) | LF | | 46 | P0.22 | `EXP_SCL` | full |
| 13 | P0.28 | `S1_SLOT_EN` | LF | | 47 | P1.00 | — | full, free |
| 14 | P0.30 | `S2_SLOT_EN` | LF | | 48 | P0.24 | — | full, free |
| 16 | P0.27 | `SLOT_SCL` | full | | 49 | P0.25 | — | full, free |
| 19 | P0.26 | `SLOT_SDA` | full | | 50 | P1.02 | `BOOT` | LF |
| 20 | P0.04 | `S0_SPARE1` (AIN2) | full | | 52 | P0.09 | `EXP_RST` | LF, NFC |
| 21 | P0.05 | `S0_SPARE2` (AIN3) | full | | 54 | P0.10 | `EXP_LDO_EN` | LF, NFC |
| 22 | P0.06 | `S1_SPARE1` | full | | 56 | P1.04 | `TCA_RESET` | LF |
| 23 | P0.07 | `S1_SPARE2` | full | | 57 | P1.06 | `BAT_DIV_EN` | LF |
| 24 | P0.08 | `S2_SPARE1` | full | | 58 | P1.07 | `LED_BOOST_EN` | LF |
| 25 | P1.08 | `S2_SPARE2` | full | | 59 | P1.05 | `ACOK` | LF |
| 26 | P1.09 | `SPARE` | full | | 60 | P1.03 | `AUX_5V_PRES` | LF |
| 27 | P0.11 | — | full, free | | 61 | P1.01 | `EXP_INT` | LF |
| 29 | P0.12 | — | full, free | | 40 | P0.18 | `NRESET` | reset |

Dedicated: 17/18 XL1/XL2 (LFXO), 34/35 D−/D+, 32 `VBUS`, 28 `VDD`, 30 `VDDH`,
31 `DCCH`, 51/53 SWDIO/SWDCLK, GND 1, 2, 15, 33, 55.

- **Totals:** 19 full-function signals on 24 full-function pads (5 free: P0.11,
  P0.12, P1.00, P0.24, P0.25); 21 LF signals exactly fill the 21 LF-only pads;
  42 of 47 GPIOs plus nRESET. The CC sense pads are rev 7's; the battery-sense pad now reads
  the PL40 node (rev 8.1, AIN0), and the table still lists rev 8 power signals (re-checked at
  hub-base capture).
- The NFC pads carry two outputs (`EXP_RST`, `EXP_LDO_EN`), which needs
  `CONFIG_NFCT_PINS_AS_GPIOS=y` (UICR). Leakage between the NFC pads when driven to
  different states: **INFC_LEAK 1 µA typ / 10 µA max** (nRF52840 PS v1.11 §6.9.3.2,
  read 2026-10-01; §6.14 asks for both pads at the same level in power-saving modes).
  Firmware keeps `EXP_RST` and `EXP_LDO_EN` at the same level except during a reset
  pulse (both low with the expansion rail off, both high while it runs).
- The hub keeps every `SPARE` pad hi-Z until a connector layer defines it (§6).
- The module sits on the base board with everything it drives (2026-09-29; the
  `J_MCU` join is dropped, §6).

Rev 7's core union was 45 of 47 with 22 of 24 full-function pads; the key matrix,
dial, two UARTs, link switch and module-ID pins are gone. The TCA9548A's spare
channels (8 − 3 slots) can carry a Qi board's status bus.

### Key board (module controller)

| Use | `left` | `right` | `numpad` |
| --- | --- | --- | --- |
| Matrix | 13 (6×7) | 15 (6×9) | 9 (5×4) |
| Encoder A/B (push switch in the matrix) | — | 2 | — |
| Link I2C (target) + `INT` | 3 | 3 | 3 |
| LED driver I2C (controller) + `SDB` | 3 | 3 | 3 |
| Module-ID strap | 1–2 | 1–2 | 1–2 |
| `J_COMM` spares (future comms) | 2 | 2 | 2 |
| SWD | 2 | 2 | 2 |
| `BSL_invoke` rescue pad (PA18, pull-down; §9) | 1 | 1 | 1 |
| **Total** | **26–27** | **30–31** | **22–23** |

Fixed pins: link SDA/SCL on **PA0/PA1** (default BSL I2C), `BSL_invoke` on **PA18**,
SWD on PA19/PA20; on the 48-pin PT package these are pins 1, 2, 33, 34, 35, with
`NRST` 4, `VDD` 6, `VSS` 7 and `VCORE` 48 (SLASEX6C Table 6-2 and Figure 6-3). Library:
`keyboard:MSPM0G3505SPT` on `keyboard:TI_LQFP-48_7x7mm_P0.5mm_PT0048A` (TI drawing
4215159/B land pattern, 2026-09-29).

**Part (P19, decided 2026-09-26): TI MSPM0G3505 in LQFP-48 (`MSPM0G3505SPTR`)**,
one part on all three key boards. SLASEX6C: Arm Cortex-M0+ to 80 MHz, 32 KB flash
/ 16 KB SRAM, 1.62–3.6 V, **44 GPIO** in LQFP-48 (≈16 spare on `right`), **two I2C**
(FM+), a 16-bit timer with a **QEI** quadrature decoder for the dial, STANDBY
1.5 µA with a 32 kHz timer, internal pull-ups 40 kΩ typ, `VOL` ≤0.4 V at 2 mA, and
a **ROM bootstrap loader on I2C** (default BSL I2C pins, 5 V-tolerant open-drain) and
UART. **The link I2C target goes on the BSL's default I2C pins** so the hub can
reflash every key board over its link (F7). The leaded 0.5 mm LQFP can be reworked
by hand. Rejected: MSPM0L1306 VQFN-32 (28 GPIO including SWD, zero headroom on
`right`, no QEI, not reworkable), RP2040 (0.18 mA typ in DORMANT, ~0.54 mA for
three boards against a ~0.9 mA idle budget; external flash), ST STM32G0/C0 and
Microchip AVR DA (not compared; their datasheets could not be downloaded). Stock
and price at European distributors not yet checked.
**Dial filter re-check:** with a 40 kΩ pull-up the dial board's 1 kΩ + 10 nF gives a
closed level of ~0.08 V (limit 0.3 × `VDD` = 0.99 V) and a ~0.9 ms 10–90 % rise
against ≥10 ms between edges at 60 RPM; the dial board is unchanged.

## 6. Connectors and the comms interface

**The comms contract.** A comms pair connects one hub slot to one key board. On
both ends it presents the same electrical interface, and whatever it does in
between must deliver the module controller's register map (§9) to the hub
unchanged.

| Header | Pins | Between | Nets |
| --- | --- | --- | --- |
| `J_SLOT` | 14 | wired connector layer's carrier ↔ socket board (hub-side comms board, ×3) | `LED_RAIL` ×2 (into the slot switch), GND ×3, `VSYS` ×2 (3.3 V for an active comms board), SDA, SCL (the slot's TCA9548A channel), `INT_A`, `INT_B`, `SLOT_EN`, `SPARE1`, `SPARE2` (full-function hub pads, reserved). **Order (2026-09-29): 1 `LED_RAIL`, 2 `VSYS`, 3 GND, 4 SDA, 5 `SPARE1`, 6 GND, 7 `SLOT_EN`, 8 `INT_B`, 9 `INT_A`, 10 `SPARE2`, 11 SCL, 12 GND, 13 `VSYS`, 14 `LED_RAIL`** |
| `J_COMM` | 10 | key board ↔ module-side comms board | `VIN` ×2 (power into the key board), GND ×3, SDA, SCL, `INT`, `SPARE1`, `SPARE2` (module-controller pins, reserved). **Order (2026-09-29): 1 `VIN`, 2 GND, 3 SDA, 4 `SPARE1`, 5 GND, 6 `INT`, 7 `SPARE2`, 8 SCL, 9 GND, 10 `VIN`** |

Both are reversal-safe (pin k meets N + 1 − k on an end-reversed cable). `J_SLOT`:
power meets its own net, SDA meets SCL, `SPARE1` meets `SPARE2`, GND meets `INT_A`
(the hub input reads low, the comms board's CC pull-up sinks ~15 µA) and `SLOT_EN`
meets `INT_B` (the hub drives a CC line to 3.3 V; the slot switch's `ON` sees a hub
input and the TPS22950's smart pull-down keeps it off); SDA and SCL each sit beside
a GND. `J_COMM`: SDA meets SCL, `SPARE1` meets `SPARE2`, GND meets `INT` (the open-drain
`INT` just sinks; the hub sees `INT` stuck and flags the slot); on the flat GH cable
SDA and SCL are four positions apart with GND between. **The spares on both headers
are reserved inputs, and they face each other when reversed:** a future comms board
that drives them uses series resistors. None of them can reach the far end over a
USB 2.0 C-to-C cable, which has no spare conductor, so the rev A cable comms boards
leave them NC.

Two counts are over what rev A needs: `VSYS` on `J_SLOT` and the spares on both.
They are the reservation for radio, optical and mixed comms boards (§15). A
module-side radio board would bring its own battery chain and feed `VIN`, which is
why `VIN` is "into the key board" rather than "from the hub".

**Cable comms boards (rev A).** One PCB with a GCT USB4085 receptacle. A plain USB
2.0 C-to-C cable has five conductors (VBUS, GND, D+, D−, CC), exactly the link's
five nets:

| Receptacle pins | Hub side | Module side |
| --- | --- | --- |
| A4 A9 B4 B9 (VBUS) | slot switch output (TPS22950L), TVS0500 | `VIN`, TVS0500 |
| A1 A12 B1 B12 | GND | GND |
| A6 **tied to** B6 (D+) | SDA | SDA |
| A7 **tied to** B7 (D−) | SCL | SCL |
| A5 (CC1) | `INT_A`, 220 kΩ pull-up from `SLOT_EN` | BAT54C anode → `INT` |
| B5 (CC2) | `INT_B`, 220 kΩ pull-up from `SLOT_EN` | BAT54C anode → `INT` |
| A8 B8 (SBU) | NC | NC |

- **D+/D− pass straight through a C-to-C cable** and are tied A6=B6, A7=B7 at each
  receptacle, so SDA meets SDA and SCL meets SCL in all four plug orientations. No
  mirroring is needed, unlike rev 7's UART link.
- **CC carries `INT`.** A cable has one CC wire; which receptacle pin it lands on
  depends on the plug's orientation, so each end handles both pins. The module side
  joins CC1 and CC2 through a **BAT54C** (common cathode on the module controller's
  open-drain `INT`), and the hub side reads each pin on its own GPIO. An
  **e-marked cable** carries an Ra (~1 kΩ) to GND on the plug's VCONN pin: at the
  module end its BAT54C diode is reverse-biased and inert; at the hub end one pin
  reads low permanently and firmware masks it. `INT` low level at the hub:
  the MSPM0G3505's `VOL` (≤0.4 V at 2 mA; ours is ~33 µA) plus the BAT54C's
  ~0.25 V is ≤~0.65 V, under the nRF52840's `VIL` of 0.3 × `VDD` ≈ 0.99 V.
- **The pull-ups do not look like a USB source (E17, decided 2026-09-26: 220 kΩ).**
  USB Type-C spec R2.0 Tables 4-35/4-36: a sink classifies CC below the **0.2 V**
  threshold as open/Ra (vRa max 0.15 V) and needs **vRd-Connect ≥0.25 V** to see a
  source. 220 kΩ from `SLOT_EN` (≤3.56 V worst case) against a sink's 5.1 kΩ
  ±10 % Rd gives **≤~0.09 V**, below vRa max, so a phone or laptop in a hub slot
  never sees a source. The first draft's 100 kΩ reached ~0.19 V worst case, inside
  the 0.15–0.25 V band where sink behaviour is undefined. `INT` rise with ~70 pF is
  ~15 µs, ~15 µA while asserted; a high-impedance line beside the SCL wire picks up
  more coupled noise, and a spurious `INT` only costs the hub one FIFO read. USB `Rp` values (36 kΩ / 12 kΩ /
  4.7 kΩ to 3.3 V) are avoided on purpose; the nRF52840's 11–16 kΩ internal
  pull-up would look like a 1.5 A source. Feeding the pull-ups from `SLOT_EN` turns
  them off with the slot.
- **No USB `Rd` on the module side**, so a USB-C source (PC, charger) never turns on
  VBUS into a key module, as rev 7's link ports.
- **I2C over the cable (E16).** The cable pairs SDA and SCL in the D+/D− twisted
  pair, which couples SCL edges onto SDA; USB 2.0 cables are not specified for it.
  Capacitance estimate per line: ~60 pF/m × 1 m + 4 × 0.5 pF of TPD6E05U06 + pins and
  traces ≈ 90 pF. With **2.2 kΩ pull-ups** on the key board: rise 0.8473 × 2.2 kΩ ×
  90 pF ≈ 170 ns against 300 ns at 400 kHz, 1.5 mA sink. **Decided 2026-09-26:
  design for 400 kHz with an automatic per-slot fallback to 100 kHz**: the hub
  counts NACKs, bus errors and register-map check failures per slot and drops that
  slot to 100 kHz past a threshold (logged, re-tried at 400 kHz after a replug).
  Lighting then runs ~33 instead of ~100 full frames/s on that slot; key events
  are unaffected (<1 ms either way). Rejected: 100 kHz only (gives up headroom the
  link probably has) and edge-rate RC networks (eat the rise budget, need bench
  tuning). Unproven until scoped (E16). Links are **≤1 m**.

**Host USB-C, on the USB port board** (unchanged from rev 7): 2 × 5.1 kΩ CC
pulldowns with both CC pins also routed to the hub's `AINx` pads, KTS1693,
SMF6.0A behind it and USBLC6-2SC6 on D+/D− with its `VBUS` pin on the KTS1693's
`OUT`. Firmware reads vRd on the active CC and sets the whole keyboard's LED
budget:

| vRd | Advertised | LED budget at ~5 V |
| --- | --- | --- |
| 0.25–0.61 V | default USB, 500 mA | ~350 mA at the rail, all modules together |
| 0.70–1.16 V | 1.5 A | uncapped (full board ≈ 507 mA at the rail) |
| 1.31–2.04 V | 3.0 A | uncapped |

**Expansion connector**, 12-pin 1.0 mm JST-SH on the expansion board, on the hub,
unchanged from rev 7:

```
1 GND  2 3V3(gated LDO)  3 5V(host USB only)  4 SDA  5 SCL  6 SCK
7 MOSI 8 CS              9 DC/GPIO            10 RST 11 INT 12 GND
```

Pin 2 is a regulated 3.3 V from a gated LDO off the LED rail, **budgeted at
150 mA**. The expansion board carries the socket and its ESD (TPD4E05U06 +
TPD6E05U06) and cables to the hub core on `J_EXP`.

**Board interconnect.** Internal cables use one locking wire-to-board family, JST GH
(1.25 mm pitch, positive lock, up to 15 contacts) as the proposal (P9). **Every
header pin count is unique** except the battery chain, which is its own connector
type (M10). Power nets get ≥2 contacts each.

| Connector | Contacts | Between | Nets |
| --- | --- | --- | --- |
| `J_CHAIN` | 12, 2.54 mm 2×6: core ↔ connector on Samtec **ESQ-106-24-G-D** socket up / tails down (M10, 2026-09-29), gap 17.5 mm; **below the connector layer on pogo pins** (Samtec DW riser + Mill-Max 827 strip on each battery module, pins up, Mill-Max 1578-0 discs under the board above; 2026-09-29/30, §4) | hub base board ↔ connector layer (passed through) ↔ battery module 1 ↔ 2 ↔ 3 (each shifts the pack lines by one), or ↔ Qi2 board in place of battery module 1 | **rev 8.1 (2026-09-30): 1 `PACK_A`, 2 GND, 3 `PACK_B`, 4 GND, 5 `PACK_C`, 6 `AUX_5V`, 7 `AUX_5V`, 8 `PACK_C`, 9 GND, 10 `PACK_B`, 11 GND, 12 `PACK_A`** (reversal-safe, pin k meets 13−k; §4). Rev 8 was 1 `VBAT`, 2 GND, 3 `VBAT`, 4 GND, 5 `AUX_5V`, 6 `PACK_EN`, 7 `PACK_SENSE`, 8 `AUX_5V`, 9 GND, 10 `VBAT`, 11 GND, 12 `VBAT` |
| `J_DIAL` | 5 | key board ↔ dial board (`right`) | unchanged from rev 7: **1 SW_ROW, 2 ENC_A, 3 GND, 4 ENC_B, 5 SW_COL** (reversal-safe) |
| `J_COMM` | 10 | key board ↔ module-side comms board | above |
| `J_USB` | 11 | hub core ↔ USB port board | unchanged from rev 7: **1 VBUS, 2 GND, 3 CC1, 4 GND, 5 D+, 6 VBUS, 7 D−, 8 ACOK, 9 CC2, 10 GND, 11 VBUS** |
| `J_SLOT` | 14 | wired connector carrier ↔ socket board (×3) | above |
| Slot header | 32, 2.54 mm 2×16 stacking, Samtec **ESQ-116-24-G-D**, socket on the connector layer's top, the core's tails down (M10) | hub base board (underside) ↔ connector layer (top) | 3 slots × (SDA, SCL, `INT_A`, `INT_B`, `SLOT_EN`, `SPARE1`, `SPARE2`), `LED_RAIL` ×4, `VSYS` ×2, GND ×4, 1 spare (`SPARE`); order decided 2026-09-29, below |
| Expansion header | 20, 2.54 mm 2×10 stacking, pass-through (X1, 2026-09-28), Samtec **ESQ-110-24-G-D**, socket up / tails down (M10) | hub base board (top) ↔ optional layer ↔ optional layer … | **1 5V, 2 GND, 3 3V3, 4 SDA, 5 `INT`, 6 CS0, 7 CS1, 8 DC, 9 SCK, 10 GND, 11 GND, 12 MOSI, 13 RST, 14 CS2, 15 CS3, 16 MISO, 17 SCL, 18 3V3, 19 GND, 20 5V** (below) |
| `J_EXP` | 15 | hub core ↔ expansion board | unchanged from rev 7: **1 5V, 2 GND, 3 3V3, 4 SCL, 5 SDA, 6 RST, 7 DC, 8 GND, 9 CS, 10 MOSI, 11 INT, 12 SCK, 13 3V3, 14 GND, 15 5V** (mirrored) |
| Expansion | 12, JST-SH | expansion board ↔ user | above |

Rev 7's `J_ROW` (7), `J_COL` (13), `J_LED` (12), `J_LINK` (14), `J_LB` (9), `J_LBD`
(10), `J_SEAM` (8) and the two 4-pin `J_BAT` headers are gone.

**Top expansion header (X1, decided 2026-09-28).** 2×10, passed straight through
by every optional layer; the same bus as `J_EXP` and the SH socket.

```
 1 5V        2 GND         pin k meets pin 21-k when a layer is fitted 180°:
 3 3V3       4 SDA           5V-5V, 3V3-3V3, GND-GND (power on power)
 5 INT       6 CS0           SCK-MOSI, CS0-CS3, CS1-CS2, DC-RST (hub outputs meet hub outputs)
 7 CS1       8 DC            MISO-INT, SDA-SCL (layer-driven lines meet hub inputs)
 9 SCK      10 GND
11 GND      12 MOSI
13 RST      14 CS2
15 CS3      16 MISO
17 SCL      18 3V3
19 GND      20 5V
```

- **5V** is `VBUS_LOCAL`, host USB only (as `J_EXP` 1/15); **3V3** is the gated
  expansion LDO, 150 mA for everything on the bus including the SH socket.
- **Chip selects:** CS0–CS3 run straight through; each layer picks one with a
  solder jumper, so a layer keeps its CS in any stack order and ZMK's devicetree
  stays fixed. At most four SPI layers. Each CS has a pull-up to 3V3 on the core.
- **Layer ID:** every layer carries a 2 Kbit I2C EEPROM (**Microchip 24AA024, MSOP-8**, 2026-10-01;
  second source Rohm BR24G02-3; WP tied high through a solder jumper so the ID is read-only
  until bridged; the 24AA02/24LC02B would not work, its A0–A2 are not connected)
  on SDA/SCL, its A0/A1 jumpers set to match the CS jumper (CSn → 0x50 + n). The
  hub reads 0x50–0x53 with the expansion LDO on to learn which layers are fitted,
  on which CS, their type and revision, and flags two layers set to the same CS.
  **0x50–0x53 are reserved on the expansion bus**, SH-socket accessories included.
  Drivers are still bound from the devicetree; the ID is for detection and checks.
- A reversed layer fights nothing; an offset-by-one insertion is not made safe
  by the pinout, the enclosure keys it (M11).

**Slot header (decided 2026-09-29).** 2×16 between the base board's underside and
the connector layer. The chain header at a different spot already keys the joint;
the pinout is reversal-safe as well (pin p meets 33 − p).

```
col  odd            even
 1    1 LED_RAIL     2 LED_RAIL     rotated 180°:
 2    3 VSYS         4 GND            power meets power
 3    5 S0_SDA       6 S0_SCL         slot 0 meets slot 2, function for function
 4    7 S0_INT_A     8 S0_INT_B       (the hub maps keys by module ID, so both work)
 5    9 S0_SLOT_EN  10 S0_SPARE1      slot 1 folds onto itself: SDA-SCL,
 6   11 S0_SPARE2   12 GND            INT_A-INT_B, SPARE1-SPARE2, SLOT_EN-SPARE,
 7   13 S1_SDA      14 S1_INT_A       so slot 1 never powers and reads as absent
 8   15 S1_SLOT_EN  16 S1_SPARE1
 9   17 S1_SPARE2   18 SPARE
10   19 S1_INT_B    20 S1_SCL
11   21 GND         22 S2_SPARE2
12   23 S2_SPARE1   24 S2_SLOT_EN
13   25 S2_INT_B    26 S2_INT_A
14   27 S2_SCL      28 S2_SDA
15   29 GND         30 VSYS
16   31 LED_RAIL    32 LED_RAIL
```

- `S0`–`S2` are the hub's slots (TCA9548A channels 0–2); slot numbers on the
  connector layer follow the header, not the socket boards' positions.
- **The hub keeps `SPARE` and every `SnSPAREm` hi-Z** until a connector layer
  defines them; a layer that uses `SPARE` must tolerate meeting `S1_SLOT_EN`.
- Offset-by-one is prevented by the chain header's position, not by the pinout;
  the chain header must not sit where a 180°-rotated layer could still mate
  offset (M11).
- The `LED_RAIL` contacts carry up to all three slots (~0.9 A worst case at full
  white, ~0.23 A per contact); rating with the part (M10).

**`J_MCU` dropped (2026-09-29).** With the MDBT50Q-U1MV2 (u.FL) the module needs no
free board edge, so it moved onto the base board; the vertical MCU board and its
2×30 join (order decided earlier the same day) are gone. The pad assignment (§5)
stays; the `J_MCU` pin order was never committed and is not kept.

**Stacking headers (M10, decided 2026-09-29).** Every stacking joint (chain 2×6, slot
2×16, expansion 2×10; **below the connector layer the chain moved to pogo pins the
same day**, §4) uses a **Samtec ESQ** elevated socket with square stack-through
tails (catalog page ESW/ESQ): **socket on each board's top face, tails down** into
the socket of the layer below, as in PC/104. 5.7 A per pin (2 pins powered),
insertion depth 3.68–6.35 mm, 0.64 mm square tails, phosphor bronze, `-G` 20 µ″ gold.
For every lead style the tail length A and body height B add to 23.24 mm, so with a
1.6 mm board one ESQ joint spans **~15.3–18.0 mm board to board** (spacing S ≥ B and
3.68 ≤ A − 1.6 − (S − B) ≤ 6.35), enough to clear the 15.0 mm AA holder.
**Lead style decided 2026-09-29 (M11): `-24`, standard insertion force, on every
joint: ESQ-106-24-G-D (chain), ESQ-110-24-G-D (expansion), ESQ-116-24-G-D (slot)**;
A 9.65 mm, B 13.59 mm; **every joint's gap S = 17.5 mm** (lower board top → upper
board bottom), so every layer is **19.1 mm** board pitch; insertion 4.14 mm
(3.68–6.35 holds for S 15.29–17.96, so the case holds S within +0.46/−2.2 mm);
tails protrude **8.05 mm** under each board; 2.5 mm over the AA holder's 15.0 mm
body (whether the cells stand above the body is not verified); 3.9 mm of bare tail
between a socket's top and the board above. Rejected `-34` at S = 17.0 (5.5 mm
tails, 2.0 mm over the holder) and at 16.13 (boards resting on the sockets, 1.1 mm
over the holder); rejected low insertion force `-49` (no force figures on the
catalog page; lower normal force against E20's contact budget).
- **The lowest layer's underside**: since the battery seams went to pogo pins
  (2026-09-29, §4) the bottom layer shows its chain target discs (with no battery
  module, the connector layer's discs and its flush-cut ESQ tails). In rev 8.1 they
  reach only hub pack inputs that no pack below drives (each LM74610 blocks reverse
  current) and `AUX_5V` (the LM66200 does not drive its input), so they sit at
  ~0 V; rev 8 had every pack's `VBAT` there. **A separate printed base closes the bottom
  (2026-09-29, M11)**: a 2 mm floor with rubber-foot recesses (**3M Bumpon SJ5012**, black
  Ø12.7 × 3.5 mm, in Ø13.3 × 1.0 mm recesses at (±40, ±40), ~2.5 mm proud, 2026-10-01), joined with the same
  keyed lip and magnets as a battery module, so it fits under whichever layer is
  lowest (~+2 mm floor + feet). Rejected: a floor with a slot over the tail field in
  every section (the bottom layer's tails stay reachable through the slot), a cap
  on the tail field (one per header, loose, friction on the tails). A Qi2 board
  closes the bottom itself. A detached module's pins carry its own pack through its PTC (§4).
- The core carries ESQ tails down into the connector layer (chain, slot) and the
  expansion socket on its top face; optional layers stack the same way. **The core
  keeps full ESQ-106/116 parts (2026-09-29)** although nothing plugs into their
  sockets: one part family and footprint per header, and the open sockets let a
  future optional layer tap the chain or slot bus; cost: two 13.59 mm bodies on the
  core's top (3.9 mm left under an optional layer's board there) and open live
  contacts under the lid. Rejected: a Samtec TSW pins-only strip on the core (a
  second family, its post length and stock unverified). The connector layer's slot
  tails stay untrimmed: they stop 10.1 mm behind the AA holder in the section below.
- Open: a second source (the family is Samtec-only as far as checked), contact
  resistance (not on the catalog page; E20 assumes ~20 mΩ, which a plain Würth
  61301221121 2×6 header meets at 20 mΩ max), mating cycles with `-G` plating
  (the page gives 100 with 10 µ″ gold), and soldering: wave or hand only, no
  reflow.

- **Host D+/D− cross one cable** (USB port board → hub core), kept ≤100 mm, with the
  two conductors adjacent and GND on both sides.
- **Contact current.** `J_SLOT`'s rail contacts carry one slot's load (≤~0.3 A at
  full white, bounded by the slot switch for faults past it). `J_USB` carries the
  whole keyboard on USB (~0.8 A). GH is rated 1.0 A per contact (P9).

## 7. Lighting

- `IS31FL3733`, LCSC `C506251`. Datasheet-verified: **`CS1~CS16` are current
  sources** fed from `PVCC`, **`SW1~SW12` are sinks** ("switch pin for LED matrix
  scanning", pulled low when on). 192 channels, 1/12 duty, µA shutdown.
- **Wiring: 1 CS + 3 SW per RGB LED**, common-anode, giving the datasheet's
  headline 64 RGB per driver. `right` uses 52. The alternative, 3 CS + 1 SW with
  common-cathode, caps at 60 and is QMK's convention; either fits, so the LED part
  is pinned **before Phase 3** so the schematic is unambiguous.
- **Peak current ~20 mA per die**, `RSET` ≈ 42.2 kΩ, fixed regardless of LED part.
  Rev 2's 20 kΩ gave ~42 mA peaks, twice the DC rating of typical reverse-mount RGB
  parts.
- 16 + 12 = **28 nets** from driver to key field.
- **The 12 SW nets carry up to ~320 mA** each and are routed by hand at ≥0.5 mm,
  excluded from autorouting alongside power and RF.
- **Headroom, datasheet-verified.** Driver sink headroom is ≤400 mV at 672 mA and
  source headroom ≤200 mV at 42 mA. Our worst SW carries 16 × 20 mA = 320 mA and our
  CS 20 mA, so ≈0.2 + ≤0.2 ≈ **0.4 V** is the working estimate. LED Vf max at 20 mA
  is **4.1 V green, 4.0 V blue**. On battery the ~5.0 V rail leaves ≥0.3 V after the
  cable (E19; rev 7's 4.7 V left ~0.2 V before any cable). On USB
  the rail is VBUS_IN, 4.75 V minimum at the receptacle less path drops, so a
  max-bin green or blue part on a weak port can fall a little short of its set
  current and shift colour; SunLED offers Vf sorting to ±0.1 V if that shows in
  Phase 1. On a healthy 5 V port the rail raises CS dissipation instead; driver
  thermal is a §16 check.
- **The LEDs are ESD-fragile**: 250 V HBM on blue. Assembly-side handling note; in
  the product they sit under the plate with no touch path.
- **The driver sits on the module controller's own I2C bus** (rev 8), not on the
  link. The hub sends frames and commands to the module controller, which writes
  the driver. The driver accepts 1 MHz and the MSPM0G3505's second I2C supports
  FM+, so the local bus can run at 1 MHz.
- **Frame budget over the link.** 3 PWM bytes per LED: `left` 120, `right` 156,
  `numpad` 51 bytes per full frame. At 400 kHz (~22.5 µs per byte) a full frame
  for all three modules is ~7.4 ms plus addressing, so ~100 full frames/s is the
  ceiling before any compression. Effects that change few LEDs cost less.
- **Current limit.** The driver's global current register is how the battery and
  USB budgets are enforced in hardware rather than by scaling PWM; the hub sends
  the budget, the module controller applies it.
- **Caps need not be shine-through.** On opaque caps the indication reads as glow
  around the cap edge; legibility is checked in the Phase 1 test cell.

## 8. Profiles + dial

- 9 profiles. `CONFIG_BT_MAX_PAIRED=9`: with no BLE split,
  `ZMK_BLE_PROFILE_COUNT` = `BT_MAX_PAIRED` (rev 7 needed 11 to leave 2 bonds for
  the split).
- The dial is on `right`'s key board. Its module controller decodes the quadrature
  and reports signed steps and the push as register-map events; the hub turns
  steps into ZMK sensor events for the keymap's sensor bindings.
- Dial: turn = volume. Fn + turn = preview. Fn + press = commit. No press, no
  change; pending reverts after a few seconds.
- Indication: keys 1–9 dim backdrop, pending bright, active in a second colour,
  single flash on commit then fade.
- Number row splits **6/3**: 1–6 on `left`, 7–9 and 0 on `right`. The hub renders
  every LED itself, so no cross-module lighting tunnel is needed (rev 7 tunnelled
  through `INVOKE_BEHAVIOR`). The indicator reads key positions from the matrix
  transform rather than hard-coding modules.
- Effect layer needs an **overlay** so indication borrows 9 keys and returns them.
- Stock ZMK cannot express preview-then-commit; `&bt BT_SEL n` takes a
  compile-time index. Custom behavior in our module.

## 9. Firmware

Two firmware images:

1. **Hub: ZMK, one keyboard, no split.** A Zephyr **board** definition for the hub
   core. No shields: the key modules are discovered at run time.
2. **Module controller: one image for all three key boards.** Reads its module-ID
   strap to pick the matrix, scans, debounces, decodes the dial, drives the LED
   driver, serves the register map. Runs on the MSPM0G3505; **updates use its ROM
   I2C bootstrap loader over the link**, driven by the hub. Framework open (F7).

**Module register map (draft, fixed at P19/F7).** One I2C target address per
module controller, the same on every key board; the TCA9548A keeps slots apart.

| Block | Contents |
| --- | --- |
| Identity | protocol version, firmware version, module ID (`left`/`right`/`numpad`), matrix size, LED count |
| Status | interrupt flags (event, fault, reset seen), `SDB` state, driver fault |
| Event FIFO | count, then entries: key index + press/release, encoder step ±n, encoder push |
| Scan config | debounce press/release ms, scan rate |
| Lighting | PWM frame (3 bytes per LED, auto-increment), global current, shutdown |
| Maintenance | reset, enter the ROM I2C bootstrap loader (update over the link, F7; entry and recovery below) |
| Integrity | a CRC or sequence number on event and frame blocks, so the hub can count link errors (E16 fallback) |

**Bootloader entry and recovery (hardware side of F7, decided 2026-09-29).** The
link sits on the MSPM0's default BSL I2C pins, **PA0 = SDA, PA1 = SCL** (LQFP-48
48-pin PT pins 1, 2; 5 V-tolerant open-drain; SLASEX6C Table 6-2), BSL target address 0x48
by default (SLAU887A §4.2.2.2). Sources: SLASEX6C (rev C, Oct 2025) §8.33, SLAU887A
(Nov 2025) §3.
- **Normal entry is from software:** the Maintenance command makes the application
  reset with `RESETLEVEL` = BOOTLOADERENTRY (SLAU887A §3.2.2).
- **Interrupted updates:** the hub writes the vector-table sector last. Until it
  lands, the stack pointer and reset vector are erased, and the boot code starts
  the BSL on any boot (blank-device rule, §3.2.1). The hub power-cycles the slot
  (`SLOT_EN`) for the power-on reset that the BSL needs after its 10 s
  no-connection timeout (§3.1.1.1).
- **Rescue:** PA18 stays TI's default `BSL_invoke` (active high, 48-pin PT pin 33)
  with a pull-down, since the invoke pin must not float (§3.2.3), and gets a pad
  beside a 3V3 pad on the key board. An image that boots but will not talk is
  rescued by bridging the pads while replugging the cable. SWD pads stay as the
  last resort. No NONMAIN (BCR/BSL configuration) changes are needed.
- Rejected: **forcing the BSL from the hub through `INT`** (invoke pin = `INT`,
  level low, ~2.2 MΩ pull-down), which is fully remote but reopens E17's margins
  (`INT` idles ~2.8–2.95 V against `VIH` 0.7 × `VDD` = 2.31 V) and needs a NONMAIN
  write per chip. `NRST`/`BSL_invoke` wires to the hub are impossible, since a
  USB 2.0 cable has no spare conductor.

`INT` is asserted while the FIFO is non-empty or a flag is set, and released when
the hub has read everything. **The hub never polls the matrix**: one `INT`, one
burst read. That is what lets a radio or optical comms pair carry the link: it
forwards events and frames, not register round trips.

**Hub module contents (out-of-tree ZMK module):** a `kscan` driver over the
TCA9548A slots that maps each module's key indices into one matrix transform by
module ID, not slot; per-slot 400 → 100 kHz fallback on link errors (E16); slot management (power on, probe, timeout, re-probe, latch
detection, stuck-bus recovery through the TCA9548A `RESET` plus nine clocks); the
`INT` pin masking for e-marked cables (§6); a sensor driver turning dial events
into `zmk_sensor_event`; the IS31FL3733 effect layer rendered on the hub and sent as
frames; overlay mechanism; preview-then-commit profile behavior; host CC
current-budget reader; battery state-of-charge driver with a NiMH/alkaline curve and
the ~2.05 V system-off threshold; slot-switch fault handling; `ACOK` fault
reporting as blink codes. **Zephyr's `ti,tca9548a` I2C mux binding is believed to
exist upstream; verify at the pinned ZMK/Zephyr version (F9).**

Carried over from the rev 7 source check (ZMK `main` at `641514a`, 2026-08-21):
`lithium_ion_mv_to_pct()` returns 0 below 3450 mV, so a 2-cell pack needs a real
curve; `ZMK_USB` + `CONFIG_ZMK_USB_BOOT=y` for BIOS; NKRO via
`CONFIG_ZMK_HID_REPORT_TYPE_NKRO=y`, verified per host over BLE. The split-transport
findings of rev 7 no longer apply.

**Delivery.** `west.yml` pins an exact ZMK commit; the required CI build uses the
pin, and a weekly non-blocking canary builds against ZMK `main`. The module
controller firmware builds in the same CI.

**Thresholds.**

| Threshold | Value | Measured as |
| --- | --- | --- |
| Lighting scale-down start | 4.40 V | PL40 `VDD` node SAADC (rev 8.1, 2026-10-01; §4), during a lighting frame (loaded); tuned on hardware |
| Lighting off | 4.25 V | same |
| System-off | 4.12 V | same node with lighting off, averaged over 8 reads; needs the bring-up gain calibration (§4) |
| Lighting cut on unplug | battery cap within ~166 ms | PL43 output falling (GPIO), §4 |
| Hardware UVLO (backstop) | 4.0 V ±1.5 % on the node (~4.16 V at the hub input, 25 °C) | TPS3840PL40 fed from the pack inputs through BAT54C + BAT54 and 10 kΩ, 1 µF; re-arms ~200 mV higher |
| Slot probe (E18) | ~200 ms answer window after power-on; ~100 ms re-probe every ~2 s while awake; none while asleep | time from `SLOT_EN` high to the first register-map answer; tune both on hardware |

**Deep sleep.** The hub sleeps with ZMK's stock sleep; the key boards stay powered
with their module controllers in a low-power scan-wait state, and a keypress
raises `INT`, which is wake-capable on the hub (System OFF wakes on any GPIO's
DETECT). Idle current of the hub, the three key boards' LDOs and module
controllers, and the LED converter is unproven (E7; datasheet estimate ~0.26 mA typ, ~0.47 mA
worst, dominated by the three TPS22950L slot switches, §4).

Set debounce in the module controller and measure in 7a.

Milestones:

- **7a bring-up**: hub board, three modules on cables, keymap, 9 profiles,
  dial → volume, battery reporting, lighting caps.
- **7b** module-controller update over the link, slot fault handling, idle current.

## 10. Layout geometry

- Per-key rotation on the alpha rows. Bottom row flat so long keys stay
  rectangular.
- **Pitch stays 19.05 mm unless Phase 1 proves otherwise.** A square of side *s*
  rotated by θ has half-width `(s/2)(cos θ + sin θ)`, so growth per side is
  `(s/2)(cos θ + sin θ − 1)`, roughly `(s/2)·sin θ`. An 18 mm cap in a 19.05 mm cell
  has 1.05 mm of gap, consumed at **7.15°** of relative rotation. Logitech describes
  the K860 arc as reaching about 5° at the edges, which across ~7 columns is
  **~0.7° between neighbours**, consuming ~0.11 mm. So the key field matches the
  K860's 456 mm.
- **Overall width ~468 mm**, accepted: two seams at ~6 mm each sit on top of the
  456 mm key field. Recorded as a known deviation.
- Bounding-box clearance is conservative; rotated squares interleave closer.
  Verified in the Phase 4 3D export, and in a Phase 1 physical test cell.
- Dial + 2 programmable keys replace the K860's three host-switch keys in the
  `right` top row.

## 11. Mechanical

In scope, co-gated with Phase 1.

- **Joining**: alignment and retention between modules — magnets, dovetails or
  latches. **Nothing electrical crosses a seam** (rev 8), so the seam budget holds
  only the two walls and the joining hardware.
- **Seam wall budget**: three cases need two walls at each of two seams. An FDM wall
  of ~1.6 mm (four 0.4 mm lines) gives about **6 mm** of dead space mid-field.
- **Comms boards**: each key module's sits at its rear wall, one cable, reachable
  without removing another board. On the hub, the wired connector layer's three
  socket boards sit at that layer's wall the same way. **Every board with a USB-C
  lies flat** (2026-09-29): the GCT USB4085 is a horizontal top-mount part (axis
  parallel to the board, 3.46 mm tall), so the board lies parallel to the floor on
  standoffs with the receptacle at the edge facing the wall, its nose flush with
  the wall's outer face in an opening ~0.25 mm larger than the receptacle all round
  (every cable's overmold stays outside). Each wall opening stays inside its own
  section, ≥1.7 mm under the seam (v0 had them straddling the seams).
- **The hub is a tower of layers (M11, decided 2026-09-26)**: optional layers
  (display…) on top, the core layer, the connector layer, then battery modules or
  a Qi2 board. Each layer is its own enclosure section; the stacking headers carry
  the signals but are not a mechanical joint, so layers latch or screw to each
  other. **Footprint ~100 × 100 mm outside** (2026-09-29; grown from 90 × 90 the same
  day for room): 2 mm ASA walls, boards ~94 × 94 mm, still under the 100 × 100 mm
  size where many fabs' cheapest tier ends (from memory). Rejected: 110 × 110 mm
  (boards past 100 mm), staying at 90 × 90 mm (tight: 3 mm from the AA holder to
  the magnet shelves, antenna ≤40 × 7 mm). **Flat core/lid seam (2026-10-01, user;
  replaced the 2026-09-29 antenna tab)**: the core section's walls rise 5 mm over
  its 19.1 mm band all round (24.1 mm tall), so the antenna (up to ~50 × 12 mm)
  fits under one flat seam; the lid is a shallow cap, 4.5 mm of wall + the 2 mm roof
  (its magnet shelves fit under the roof with 0.9 mm to spare); the tower height is
  unchanged. Accepted: an optional layer starts 4.5 mm below its board, so its ESQ
  tails (8.05 mm) stick out ~3.5 mm below its case when it is off the tower; the
  core's ESQ sockets stand 0.6 mm over the core wall with the lid off; the rear notch
  that doubled as a second key is gone (the front key stays). Rejected: the 5 mm
  rear-wall tab with a matching notch in the lid and every optional layer (user: the
  stepped seam), a taller core layer now (deferred revisit), the antenna under the lid
  roof (it travels with the lid, ~4 mm over the ESQ sockets), keeping 7 mm. Height per layer is not a choice: an
  ESQ joint spans at most ~18 mm. **The core layer is one ESQ joint tall**: the MCU sits on the base
  board (2026-09-29), so nothing in the core is taller than the joint gap.
  **Every joint's gap is 17.5 mm (ESQ `-24`), so every layer is 19.1 mm board
  pitch**; a two-pack tower is ~88 mm tall (9.5 mm tail skirt, four boards, four
  17.5 mm gaps, a 2 mm lid roof; 87.9 mm in the v0 model), ~92 mm with the base
  (2 mm floor + ~2 mm feet). **The hub antenna is the Yageo ANTX100P011B24003 PCB
  antenna (39 × 10 × 0.55 mm, adhesive; 2026-10-01) on the inside of the core
  section's rear wall**, fed from the module's u.FL, at x −46 … −7 (≥10 mm to the
  expansion board and its SH shell, the datasheet's minimum to metal), kept ≥10 mm
  from the base board's copper, the layer above and the cells (copper pull-back
  open, M11), checked by the RSSI test; behind it the wall carries a **blanked
  Ø9.6 mm knock-out** for the Yageo ANTX100ETHAB24553 whip (base Ø9.35 ±0.1; Yageo
  shows no mounting, so a printed clamp is open). Rejected 2026-10-01: an RP-SMA
  knock-out with a u.FL-to-RP-SMA pigtail (no RP-SMA antenna is on Raytac's -U
  list). **Walls (2026-09-29)**, front = the wall facing the keyboard, sides as seen from
  the keyboard: **front**: the connector layer's three slot USB-C sockets, and the
  power, reset and bootloader buttons on the core's front wall above them: **three NKK
  UB snap-in pushbuttons** (§5 notes; 2026-10-01) in **16.2 mm square cut-outs**, 17.8 mm
  square bezels **at the top of the core wall, 0.65 mm under the lid seam** (2026-10-02, user; moved up 5 mm into the
  wall the flat lid seam freed),
  power at x −30, reset 8, boot 28; each body (15.8 mm square, 8 mm behind the 2 mm wall
  + 5 mm solder lugs) sits in front of the **core board, whose front edge is pulled back
  to y −30** (user: no notches, a shorter board instead; the board is 94 × 77 mm, 5 mm
  between the lug tips and its edge for the wires); the bodies end 4.65 mm above the
  connector section, so its lip runs unbroken. Caps stand 3.9 mm proud of the wall (1.4 bezel + 2.5 cap).
  **Bezels vs slot USB-C cables:** the bezels' lower edges are 7.6 mm above the slot
  USB-C receptacles (11.3 mm above their axis), so a plug overmold up to ~18.6 mm thick
  clears; the USB-C spec sets no overmold maximum (R2.0 §3.10.3, Fig. 3-80 only asks
  0.05 mm from the product surface). ~1.45 mm of printed wall stays over each cut-out.
  Rejected 2026-10-02: centring the buttons in the 24.1 mm wall (13.6 mm plugs, ~3.9 mm
  of wall round each cut-out), leaving them 2.6 mm above the receptacles (plugs over
  8.6 mm thick touch a bezel). Rejected 2026-10-01: Alps SKRTLBE010 tactiles
  behind Ø1.6 mm pinholes and a C&K PCM12SMTR slide in a fingernail pocket (too fiddly,
  user); APEM IP (10 N latching force), NKK KB (~28 mm deep), NKK YB (~22 mm deep);
  **rear**, right to left: host USB-C (USB port board), the expansion board's SH
  socket (JST SM12B-SRSS-TB, 14.0 × 4.25 × 2.9 mm, mouth 0.3 mm inside the wall;
  opening **15.6 × 3.4 mm** = the SHR-12V-S-B plug's 15.0 × 2.8 mm + 0.3 mm a side,
  JST eSH p2–p3, 2026-10-01), then the PCB antenna and the blanked whip knock-out in the remaining
  ~40 mm at the left end (all cables leave the back; the antenna sits ~20–40 mm from
  the SH cable and the USB shell, RSSI risk accepted, checked in §16; **the flex
  antenna may be up to ~50 × 12 mm**: the core/lid seam sits 5 mm higher all round, 2026-10-01; the chosen one is 39 × 10 mm); **left** and **right**: nothing.
  **Joints (2026-09-29)**: the core and the connector layer are joined by **M2
  screws** into captive M2 nuts (the 44-contact joint cannot be pulled apart by
  accident; swapping the connector layer takes the one driver); **battery modules
  and the lid join magnetically**: each section's bottom edge nests in a lip on the
  section below (takes sideways cable pulls), an asymmetric key in the lip stops a
  90°/180° misfit, and magnets hold it, kept away from the antenna. Cell access is tool-less: lift everything above a module off
  (the cells sit 2.5 mm under the next board). **Magnets (2026-09-29)**: the user's
  own NdFeB blocks, **20 × 10 × 2 mm** (sizes vary; brittle; **magnetised through the
  2 mm**, confirmed by the user; pockets sized for the nominal size + 0.3 mm, the
  user's call, a test print confirms the fit), **two per seam**, one on the left and one on the
  right wall, **lying flat** in a pocket in an ~11 × 23 mm shelf (x 37–48 from the
  centre, centred front to back): the lower section's shelf sits under the seam, the
  upper section's over it, pole faces meeting through two 0.6 mm skins. The shelves
  sit mid-gap (8 mm over the lower board, 9.5 mm under the upper), so no board is
  notched; they clear the AA holder (x ±29), the chain header, the USB boards and
  the antenna. **Pockets are closed, side-entry, loose (~20.6 × 10.6 × 2.4 mm, about
  0.3 mm clearance), no glue**: the magnet slides in from the section's inside after
  printing, before the board goes in; gravity and its partner's pull keep it there
  (accepted: a loose layer shaken sideways can lose one). **Every magnet is fitted
  north face up**, so every seam attracts and every layer is built the same way.
  The user has 40+ (more can be bought; a two-pack tower uses 16) and reports them
  very strong: if a test print is hard to separate, thicken the 0.6 mm seam-side
  skin (the tuning knob), or fall back to one pair per seam. Holding force is not
  a target (the user accepts a low one): the magnets seat the
  lip; the ESQ contacts add their own (Samtec's -37 LIF report: 0.57–1.09 N per
  contact new). Rejected: upright magnets inside a thickened wall (end-to-end
  pairing, much weaker), glue, a snap step at the pocket mouth (brittle magnet), a wall slot with a plug (visible on the clean side walls). **Optional layers join the core's top (and each
  other) the same magnetic way**; the lid sits on the topmost section.
  **v0 review (2026-09-29)**: header centres on every 94 × 94 mm board (x right
  from the keyboard, y to the rear, board centre 0,0; all along X): **chain (25,
  20), slot (−5, 5), expansion (0, −20)**, AA holder centred at (0, −22): every
  tail clears the holder (the connector layer's slot tails stop 10.1 mm behind it),
  the chain's pack pins stay out of the antenna corner (rear-left), and the
  rear-left quadrant stays free for the MDBT50Q beside its antenna; no header is
  centred, so a layer turned 180° does not mate (the keyed lip prevents it).
  **A separate base closes the bottom** (§6). **The core ↔ connector M2 screws go
  in from the top**: four vertical screws near the corners, through the core board
  and a 9.5 mm boss in the core section's skirt, into captive M2 nuts in corner
  bosses in the connector section; the same screws hold the core board down; reach
  them by lifting the lid and any optional layers off (tool-less); the connector
  layer stays on the batteries during a swap. Rejected: from below (lift and turn
  over two layers, separate board fasteners, heads among the next module's tails),
  through the side walls (visible heads, inner bosses in the 1 mm board-to-wall
  gap, easy to undo by accident).
  **Joint geometry (model v1, 2026-09-29, placeholders marked `[approx]` in
  `mech/hub/build_hub.py`)**: the lower section of every seam carries a 1.2 × 2 mm
  lip inside the upper wall (0.2 mm clearance) with a 5 mm key on the front lip
  at x −15 (no 90°/180°/270° fit); magnetic seams put a 23 × 11 × 3.6 mm shelf on
  the left and right walls on each side of the seam, the pocket 20.6 × 10.6 × 2.4 mm
  with 0.6 mm skins, mouth towards the centre; the lip is gapped at the shelves and
  at the screw bosses. Core ↔ connector screws at (±43.5, −26.5) (moved from −30 on 2026-10-01 with the core board's front edge) and (±43.5, 26)
  (the rear pair clear of the USB port board), Ø6.5 bosses, heat-set inserts atop
  6 mm bosses in the connector section. Every other board hangs on its own four M2
  screws at (±43.5, ±20) into insert bosses under it (6 mm; on a pogo seam the whole 5 mm skirt, the lip gapped there). The base is 6 mm
  (2 mm floor, shelves standing on it, foot recesses); with the pogo seams
  (5 mm skirts) the two-pack tower spans −6 to 83.4 mm (−8.5 mm with the SJ5012 feet: ~92 mm). FDM: the shelves under a seam are 11 mm
  cantilevers, so they need supports or the section printed the other way up. **A future radio connector layer puts
  its radio on the wall facing the keyboard**, and on the opposite side from the
  core's antenna wall, so the two 2.4 GHz radios sit apart (coexistence is a future
  test).
- **Battery modules (M10, decided 2026-09-26; rev 8.1 2026-09-30: up to 3, 4×AA, passive)**: each a closed 4×AA case (2×AA in rev 8) with its
  passive battery board (holder, PTC, line shift), tool-less cell access, and the chain on **pogo pins** (Mill-Max
  827-22-012-10-004101 on a cap board over a Samtec DW-06-17-T-D-254 riser (6.45 mm), pins up, Mill-Max 1578-0 gold target discs under the board above; 2026-09-29, §4) so modules **stack
  under the hub**; a separate base under the lowest layer covers its underside
  (2026-09-29); the case
  keys the join and the pinout is reversal-safe (§4). A future Qi board plugs into
  the hub instead of the stack, so the pad sits under the hub. Side by side is a future
  option.
- **Cable routing**: every internal cable has a routed channel and a clip point,
  clear of the switch pins, the hotswap sockets and the reverse-mount LED holes.
  Service loops are just long enough to lift a board out. Each key module has only
  two internal cables now (`J_COMM`, and `J_DIAL` on `right`).
- **Fastening**: **M2 heat-set brass inserts** melted into the ASA (2026-09-29),
  **Ruthex RX-M2x4**: 3.6 mm across, 4.0 mm long, hole 3.2 mm (5.0 mm deep in the
  model: 4.0 + 1 mm for displaced plastic), ≥1.3 mm of wall around it (ruthex.de
  table; no strength figures published). Bosses are 6.5 mm across (1.65 mm wall).
  Sourcing exception: not a Mouser/TME/Farnell part (ruthex.de, 3DJake). Rejected:
  PEM IUB-M2-1 (datasheet: 334 N pull-out, 0.3 N·m torque-out in ABS; dearer,
  stock unchecked). Screw lengths are set with the boards: ~M2 × 16 for the
  core ↔ connector joint (1.6 board + 9.5 boss + insert), ~M2 × 5 for a board on its
  own bosses. Not self-tapping
  screws. Every board uses M2 screws, so one driver services the whole keyboard.
  (Captive M2 nuts were chosen earlier the same day on the wrong premise of an SLA
  resin case, which takes no heat-set insert; reverted once the case became FDM.)
- **Row dish**: the PCBs stay flat. The MX switch body fixes plate-to-PCB distance,
  so a stepped plate cannot reach a flat board. The dish comes from **per-module
  tilt** and a **sculpted keycap profile**. Shallower than the real K860's arc.
- **Plate**: **1.5 mm FR4, no copper**, ordered from the PCB fab with rotated
  switch cutouts and plate-mount stabiliser cutouts (2.75U ×2, 2.25U, numpad 2U).
  Not a ground plane, so no antenna cutout is needed; keep any copper off it.
- **Palm rest**: the defining silhouette feature and the reason the real thing is
  233 mm deep.
- **No cells in the key modules** (rev 8). The palm rest no longer houses battery
  boards, so its height floor is no longer the 16 mm AA holder: the key module's
  floor becomes PCB + plate + switch + keycap plus the palm-rest shell. The
  silhouette is kept; the space under the palm rest is free.
- **Printing (2026-09-29, replaces rev 7's M9 answer)**: **FDM in ASA** on the
  user's own printers, Bambu Lab H2S (340 × 320 × 340 mm, chamber heated to 65 °C)
  and Prusa CORE One (250 × 220 × 270 mm, chamber to 55 °C), both from the vendors'
  pages. **One piece per module**: `left` and `right` at 233 mm deep fit either bed,
  so no print service and no joints. ASA needs the warm chamber against warping;
  vent the fumes. Overhangs past ~45° (magnet shelves, lips) get a chamfer or
  are printed the other way up. Rev 7 had assumed SLA resin from a large-plate
  service, a premise the user never had (no resin printer). Rejected: PETG
  (Tg ~80 °C, glossy, creeps), PLA (Tg ~55–60 °C, softens on a sunny desk).

## 12. Fabrication constraints

- **Reverse-mount LEDs mean ~109 board holes** across the three boards, the LEDs on
  the bottom side emitting upward. SunLED's own pattern calls for a **Ø3.2 ±0.1 mm
  round hole** (lens only) with pads 1.4 × 0.65 mm across a 5.2 mm span; the
  Inolux/QT-Brightek alternates call for a **Ø4.5 mm round cutout** (body in the
  hole) with pads at 1.5 mm pitch across ~6.0 mm. **The combined footprint
  (2026-09-14) is a Ø4.5 mm cutout with pads spanning both lead lengths**, provided
  the SunLED seats on it and the pinouts can be reconciled (P1). These are plain
  non-plated routed circles, not slots. Explicit fab note on hole tolerance. They
  also perforate the ground plane, which matters for USB and the antenna.
- **Stackup must be defined in Phase 4**: layer assignment, ground-reference
  strategy, min trace/space (JLCPCB 4-layer economy is 0.127 mm), min via.
- **Hub core stackup**: 4 layers as the rev 7 core, which had a 32 × 90 mm outline
  forced by fitting inside a key module. **The hub core is not size-constrained**:
  its outline is set by the hub enclosure (M11: ~94 × 94 mm, 2026-09-29, with the
  MDBT50Q-U1MV2 on it and no antenna keepout), and the rev 7 fan-out congestion
  around the MDBT50Q (7 nets left open after every scripted approach) is expected
  to disappear with room to spread the power path. The rev 7 placement, rules
  (`U401_ESCAPE`), and routing notes stay in `0b22b91` for reference.
- **Hotswap socket + reverse LED window + diode + stabiliser clearance inside one
  19.05 mm cell** is asserted, not proven. Phase 1 deliverable: one test cell
  printed 1:1 with a real socket, switch and opaque keycap in hand. **The LED goes
  south** (0, +5.08 mm): the MX north LED position collides with the Kailh
  socket body and its pad at (2.54, −5.08), which is why every hotswap RGB board
  is south-facing. The chosen switches must pass light through the south side of
  the bottom housing.
- **The KTS1693's WLCSP sets the fab class of the USB port board**: a 4 × 5 array at
  0.4 mm pitch needs 0.15 mm vias and via-in-pad (six inner balls cannot escape on
  economy rules). Rev 8 has one such board per keyboard (rev 7 had seven). The P7
  survey's leaded candidate TPS25947 (QFN 2 × 2 mm) would drop the requirement at
  the cost of a USB port board redesign.
- **The TPS22950L (YBH DSBGA-6, 0.4 mm)** sets the fab class of the comms board, as
  it did the rev 7 link board.
- **No aqueous wash.** Kailh sockets trap flux in gold spring contacts and JLCPCB
  washes by default. Fab note, or hand-install sockets after wash.
- **RGB rotation** is a common JLC defect. Explicit CPL rotation per LED,
  first-article check on one board before the run.
- **FR4 plates**: three extra boards per build, no copper, outline + cutouts only.
- **Board designs and counts per keyboard** (§2a): hub base board (MCU on it since
  2026-09-29), 1 wired connector carrier, 3 key boards, 6 comms boards (3 hub-side socket boards
  + 3 module side), 1 USB port board, 2 battery modules (more by chaining), 1 dial
  board, 1 expansion board, 3 plates. That is **10 PCB designs**: hub base,
  connector carrier, 3 key boards, comms, USB port, battery, dial, expansion,
  with the comms board in two BOMs; optional top layers come on top.
- **Assembly split.** Key boards, the hub core, comms boards, the USB port board and
  the expansion board need assembly-house placement (module controller, WLCSP,
  QFN, the MDBT50Q). Battery and dial boards are hand-solderable, **except the
  battery board's PTC (MF-MSMF125/16X, 1812): reflow only** ("hand soldering is not
  recommended", Bourns) **and its 1578-0 target discs (reflowed onto ENIG pads)**,
  placed in one reflow or hot-air step; the DW riser and the 827 strip are
  through-hole, hand or wave soldered. **MSL 3 LEDs**: bake note if reels have been opened.
- Check `IS31FL3733` vs `-B` lifecycle and stock parity before committing.

## 13. Analogue and RF notes

- **SAADC** (nRF52840 PS v1.11 §6.23): internal 0.6 V reference at gain 1/6 (3.6 V
  range), **not** `VDD/4`. **Rev 8.1 (2026-10-01):** `AIN0` reads **the TPS3840PL40's
  `VDD` node** (the highest pack through its Schottky and 10 kΩ, held on 1 µF), so the
  pack level is known on USB too. Divider **200 kΩ / 100 kΩ 1 %, switched on the high
  side** by a CSD25483F4 (470 kΩ gate pull-up to the node) whose gate half a
  DMN63D8LDW pulls down from `BAT_DIV_EN` (1 MΩ `BAT_DIV_EN` pull-down kept), so it
  draws ≤100 nA off and `AIN0` never sits above `VDD` + 0.3 V. Reading, `AIN0` is
  ≤2.1 V (≤3.0 V even at 8.9 V), the divider draws ~13 µA for ≤100 µs, TACQ 10 µs; a
  bring-up gain calibration is required (§4). Rev 7's VBAT divider (49.9 kΩ / 49.9 kΩ,
  AO3415A + 2N7002) is superseded. Host CC sense reads 0.25–2.04 V through a 100 kΩ series
  resistor into an `AINx` pad.
- **Antenna** (2026-09-29): the hub holds the only radio, on the desk, away from
  the palms and the key field. The **MDBT50Q-U1MV2** has no antenna of its own; its
  u.FL feeds an **adhesive PCB antenna on the inside of a core-section wall**, so
  the antenna's position is chosen in the enclosure, not dictated by the module's
  board edge. **Parts (2026-10-01, P20 closed):** Raytac's MDBT50Q-U1MV2 datasheet
  (ver L, 2023-05-24, ch. 7, `build/ds/raytac/`) lists four approved antennas; only
  two carry CE, and the hub uses both: **Yageo ANTX100P011B24003** (PCB dipole,
  39 × 10 × 0.55 mm FR4 on adhesive tape, peak 2.1–2.2 dBi, 63–68 % efficient,
  VSWR 2.5:1 max at 2.40–2.50 GHz, I-PEX 20278 on 1.13 mm × 100 mm cable,
  −40…+85 °C, ≥10 mm from metal on three sides; Yageo datasheet V1 p3–p6) inside,
  and **Yageo ANTX100ETHAB24553** (hinged whip, 102.3 mm, 2.0 dBi, VSWR ≤ 2.0,
  integral 1.13 mm × 100 mm cable, base Ø9.35 mm, −40…+65 °C; spec R02 p4, p12)
  as the external option through a **blanked knock-out** in the same wall, if the
  RSSI test (§16) is poor. Raytac: "End-product may need to perform further testing
  when applying CE"; "certificate(s) might not be applicable when using antenna
  apart from above list". Hirose U.FL: 30 mating cycles, 2 N max cable load off
  the board, 4 N along it (U.FL catalogue 2019.6, p2, p7); the u.FL is mated at
  assembly, not by the user. ISED number for the -U is 8017A-MDBT50QU (not
  8017A-MDBT50Q). **Risks:** Yageo measured the antenna in its own fixture with no
  plastic; it resonates near 2.35 GHz there (p5), and the 2 mm ASA wall pulls it
  lower, so the match near 2.48 GHz gets worse (RSSI test). **Open (M11):** the
  base board's and the layer above's copper pull-back for the ≥10 mm, the whip's
  clamp. Rejected: Ezurio FlexPIFA, Taoglas FXP74/FXP73/FXP830, Molex 146153,
  Kyocera AVX 1001932FT (not on Raytac's list; FXP74/FXP830 also over 2.2 dBi),
  Linx ANT-2.4-FPC-LH (5–6 dBi), Yageo ANTX100P111B24003 (3.3 dBi, no CE),
  Aristotle RFA-02-5 (5 dBi, no CE), an RP-SMA knock-out with a u.FL-to-RP-SMA
  pigtail (no RP-SMA antenna approved). The rev 8 vertical MCU board (2026-09-26)
  is dropped: the u.FL module needs no free board edge.
- **ESD**: entry points are the host USB-C port (USB port board), every link socket
  at both ends (comms boards, TPD6E05U06 on the six CC/D± pins, TVS0500 on VBUS),
  the expansion connector (expansion board), the key matrix (finger → keycap →
  switch → module-controller pin, clamped on the key board), the dial shaft (dial
  board, lugs to GND, DNP TPD4E1U06DBV), and the AA terminals and chain contacts
  (rev 8.1: the battery module is passive, so they are clamped at the hub's pack
  inputs, SMF4L9.0CA). Internal cables are not
  entry points and get no clamps.
- **EMC**: informational only, since this ships as open source and builders carry
  their own compliance. Modular approval covers the intentional radiator only; the
  product remains an unintentional radiator under FCC Part 15B / EN 55032, and the
  module's FCC and IC identifiers would go on the label of anything sold.
- **Test points** beyond SWD: on the hub core, `PACK_A`/`B`/`C`, `VBAT`, `SYS`, the PL40 node,
  `VSYS`, `VBUS_IN`, LED rail, expansion 3V3, GND, each slot's SDA/SCL/`INT` and
  `SLOT_EN`, host CC1/CC2. On the key board, `VIN`, 3.3 V, SDA/SCL/`INT` at the
  link entry, the driver's I2C, and the module controller's SWD pads.

## 14. Repo layout

```
plans/      this spec
docs/       architecture + decision record, power budget, build guide,
            repair guide (symptom -> board), spares list
layout/     k860.yaml, generator + render scripts
mech/       joining, palm rest, plate, case, hub enclosure, battery modules, cable routing
  hub/      hub tower (M11, 2026-09-29): a Python script owns the FreeCAD model (run
            through the FreeCAD MCP; the .FCStd is a build output); exports a STEP per
            layer + the assembly and an STL per printed part; board outlines, holes
            and header positions flow FreeCAD → KiCad (DXF or a pcbnew script), the
            boards' STEP comes back for clearance checks
hardware/
  lib/      vendored kiswitch footprints, custom MX socket + RGB combo footprint,
            interconnect footprints and the cable drawing
  common/   shared sheets: key-board LED matrix + module controller block
  keys-right/ keys-left/ keys-numpad/   one KiCad project per key board
  hub-base/ hub base board (MDBT50Q-U1MV2, power path etc., from the rev 7 core)
  connector-wired/  wired connector layer carrier
  comms/    cable comms board, hub (socket board) + module populations (from the rev 7 link board)
  usb-port/ battery/ dial/ expansion/   one KiCad project each
  plate/    FR4 plate outlines, one per module
firmware/   zmk-config (west.yml pins ZMK): hub board definition, out-of-tree module;
            module-controller/ firmware
tools/      kicad-cli wrappers, gerber/BOM export, Konnect config
.github/workflows/  build (pinned, required), canary (ZMK main, weekly, non-blocking)
```

KiCad annotates per project, so refs are partitioned by project: `keys-right` 1xx,
`keys-left` 2xx, `keys-numpad` 3xx, hub core 4xx, `usb-port` 5xx, `comms` 6xx,
`battery` 8xx, `dial` 9xx, `expansion` 10xx. 7xx (the retired seam board) stays
unused; a Qi board takes 11xx and future comms boards 12xx and up. A ref alone
names the board it is on, which the repair guide relies on.

## 15. Future modules: Qi2, comms

**Qi2 (optional, later).** A Qi board takes power from a Qi2 charging pad and
feeds `AUX_5V` into the hub, where it is `VBUS_IN`'s second OR input. **It is used
instead of the battery stack** (decided 2026-09-26): it plugs straight into the
hub's chain header, so the pad sits under the hub and nothing else is in the path.
Battery modules still pass `AUX_5V` through, which keeps a Qi board under a battery
stack possible later at no cost; it is not a supported setup in rev 8. A Qi-only
hub has no battery: off the pad and off USB it stops. Behaviour is either/or: with `AUX_5V` present the
hub runs the keyboard from it as from USB (`VBUS_IN`, Qu), the packs sit isolated, and
**nothing charges the cells**. Rev A reserves: `AUX_5V` on the chain bus (≥2
contacts), the LM66200 IN2 on the hub, an `AUX_5V`-present GPIO, and a spare
TCA9548A channel for a receiver's status bus. Candidate receiver: ST **STWLC89** (Qi 2.x
MPP; from a web search, datasheet not read, stock unchecked). Its budget is open:
at 5 W the lighting cap on `AUX_5V` sits between the battery and USB budgets.

**Radio, optical and mixed connector layers.** The connector layer is the part a
user swaps to choose how the modules connect. Rev A reserves, on both ends: the
register-map contract (§9); on the hub side the 2×16 slot header with `VSYS`, the
LED rail and two spare full-function pins per slot; on the module side two spare
module-controller pins on `J_COMM` and a `VIN` that accepts power from the
module-side board. A radio connector layer puts its antenna on the wall facing
the keyboard, opposite the core's (§11). A module-side radio board would carry its
own battery chain (a module linked without wires needs its own cells) and feed the
key board through `VIN`. A mixed pair (e.g. cable plus radio) chooses or relays
between media itself; the hub and key board see only the register map. Nothing
beyond the reservation is designed in rev 8.

**Li-ion: not supported (2026-09-30).** No Li-ion build is planned; rev 7's reserved path (`VDDH` jumper, DNP REG0) is dropped from the plans.

## 16. Verification

- [ ] `kicad-cli sch erc` + `kicad-cli pcb drc` clean, every project + plates
- [ ] Interconnect audit: every net matches end to end across every connector and
      cable; no two headers that one cable could reach share a pin count
      (`tools/check_interconnect.py`)
- [ ] Konnect power-rail review, decoupling analysis, connectivity audit per board
- [ ] Phase 1: 1:1 print matches a real K860; physical test cell with socket,
      switch and opaque keycap, indicator glow legible; per-size cap count against a
      purchasable set
- [ ] **Insert one AA backwards, then both, in each battery module. Nothing is
      damaged.**
- [ ] **Chain (rev 8.1):** one, two and three battery modules stacked, and a 4th
      below them (its pack reaches no hub input); a fresh pack with a flat one: no
      current between packs, the highest carries the load; a lifted module's pins
      show its own pack through its PTC; the power switch off turns Qb off (`SYS`
      0 V on battery)
- [ ] **Runs correctly on one battery module alone**
- [ ] **USB only, no cells fitted**: boots, `VSYS` = 3.3 V, every slot powers its
      module
- [ ] Battery power-on: each key board's 3.3 V never exceeds its `VIN` (scope both
      at the driver); no GPIO required for the TPS630701 or TPS70933 to start
- [ ] **Switch-on** from a ~4.4 V pack starts; a 4.2 V pack does not (re-arm ~4.32 V)
- [ ] **Pack swap and insert while running** (4.9 → 4.4 V, and a pack added): no
      UVLO edge, `SYS` ≥~3.4 V
- [ ] 20 V on the host USB-C socket's VBUS, steady and **hot-plugged from a charged
      source**: `VBUS_IN` never exceeds 6.0 V and `VBUS_LOCAL` (the MDBT50Q `VBUS` pad)
      5.8 V at any instant; then a 5 V source
      stepped to 20 V while connected: same limit
- [ ] 1 kV contact ESD (then the chosen IEC level) on AA terminals, chain contacts
      and a lifted module's pins, and a surge into one pack input that drives its
      SMF4L9.0CA into clamp: the PL40's `VDD` stays ≤10 V
- [ ] Contact ESD on every link socket at both ends, on the dial shaft and knob, and
      on the expansion socket: no reset, no stuck key, the link recovers
- [ ] **Plug USB with fresh alkaline packs fitted: `VBUS_IN` ≤5.5 V at every
      instant (Qb off before Qu on), `VSYS` ≤3.3 V, then zero pack current**
- [ ] **Bring-up SAADC calibration** (bench supply on one pack input, DMM on the
      PL40 node; firmware stores the gain), then: lighting off at 4.25 V and
      **system-off at 4.12 V** on the node (fires 4.09–4.17 V); the hardware cut at
      3.94–4.06 V on the node (~4.16 V at the hub input) without oscillation, 0–40 °C
- [ ] **USB unplug** at the 250 mA cap (4.4–6.4 V packs) and at the ~0.8 A USB rail
      with a ~4.4 V pack: firmware drops the lighting within ~166 ms of the PL43
      output falling, no UVLO edge; `VSYS` never resets the MCU; every key board's
      module controller stays up. Scope the PL43 output, both P-FET gates and `SYS`
- [ ] USB source ramped down through the PL43's 4.3 V and back with full lighting:
      one hand-over each way to the packs and back, no oscillation
- [ ] −20 °C with a ~4.4 V pack at the 250 mA cap: at most one clean cut; 4.5 V runs
- [ ] Steady battery near the cut (~4.5 V, 250 mA cap): the LM74610 body-diode
      windows (25 ms every ~1.2 s) keep VSYS ≥~3.0 V
- [ ] Bench supply ramped slowly on the host port: the KTS1693 trips between 5.38 and
      5.78 V (E22) and re-arms ~0.1 V lower
- [ ] Host CC sense reads default / 1.5 A / 3 A correctly on three chargers; LED
      budget follows
- [ ] Driver case temperature at full white on a 5.0 V rail, 30 min
- [ ] LED rail (TPS630701) idle (PFM) 4.95–5.15 V and under full load 4.95–5.05 V
      (E19)
- [ ] **LED headroom (E19):** max-bin green and blue at full current at `right`'s
      far end on a 1 m cable, on battery and on a 4.75 V USB source
- [ ] **Measured idle current, µA trace**, hub asleep, three modules in scan-wait.
      The §4 idle row is unproven until this exists; compare against the §4 estimate
      (~0.26 mA typ, ~0.47 mA worst; ~143 µA on the LED rail, of it 3 × ~44 µA TPS22950L)
- [ ] Keypress on each module wakes a sleeping hub
- [ ] **I2C over the cable (E16):** scope SDA/SCL at both ends through 1 m cables
      from three makers at 400 kHz: rise ≤300 ns, no SCL-to-SDA glitch past
      threshold, no NACK storms under full-rate frames; 100 kHz fallback checked
- [ ] **e-marked cable** (5 A) in every orientation: `INT` works, the Ra pin is
      masked
- [ ] Short a slot's VBUS at the far end with the slot on: its TPS22950L latches,
      the other two slots keep working
- [ ] **Mis-plugs** (architecture §5): a phone, a laptop, a C-to-C charger and a
      legacy A-to-C charger in a hub slot; a key module into a laptop and a charger;
      two hub slots cabled together; a hub slot cabled into the host port; two key
      modules cabled together. Nothing is damaged; every case recovers
- [ ] Unplug a link cable under full lighting, against the service rule, 10 times
      at each end: the key board survives; scope the clamp current through
      SDA/SCL/`INT` at the link entry, and `VIO` against `VCC` at the driver
- [ ] A stuck slot bus (SDA held low on one key board): the other slots keep
      working; the hub recovers the stuck one
- [ ] Any module in any slot, all 6 permutations: keys map correctly
- [ ] Expansion 3V3 at its 150 mA budget with full white on a 1.5 A host: TLV75733P
      case temperature recorded
- [ ] Trip the host port KTS1693 into its over-current latch: the fault blink code
      names the USB port board; the trip lands at 1.82–2.18 A. Scope the 5–10 ms
      debounce pulse on a hard short from a 3 A charger
- [ ] Partial short on `SYS` (~1 Ω, fresh NiMH, one pack): record the LM74610 FET
      and Qb case temperatures, UVLO or thermal cycling, and whether the PTC trips
      (hold 1.25 A, trip 2.50 A)
- [ ] Host USB eye/enumeration through the USB port board cable at its longest
      routed length, on three hosts
- [ ] Change cells in a battery module with no tools
- [ ] Hub stack: a display layer on top and two battery modules below; compare BLE
      RSSI with and without them, and with the connector layer swapped out
- [ ] A battery module stacked straight under the core (no connector layer): the hub
      powers up, no slot exists, nothing is damaged
- [ ] Two optional layers on the expansion header with different chip selects both
      work; two on the same chip select are flagged (ID EEPROM read at 0x50–0x53),
      nothing is damaged
- [ ] A layer fitted rotated 180° on the expansion header: nothing is damaged, the
      layer works again once refitted
- [ ] Power button (NKK UB16, gold, ~1 µA through the 4.7 MΩ pull-down, under NKK's
      0.1 mA minimum): Qb turns on and off reliably over ~1000 latches, and N1's gate reads
      the PL40 output within a few mV when latched
- [ ] Hub BLE RSSI against a dev kit in the open, **once with the internal PCB
      antenna and once with the Yageo whip in the knock-out**, with the
      stack as above
- [ ] Canary CI against ZMK `main` runs weekly and reports breakage
- [ ] Dial spun fast both ways: no missed or doubled steps; a turn without a press
      never changes the live profile
- [ ] **Hold 10+ keys at once spanning all three modules; every one registers**,
      over USB and over BLE, on each host OS in use
- [ ] Key-press latency, switch contact to USB report, per module: record it
- [ ] BIOS/UEFI sees the keyboard over USB (boot protocol)
- [ ] 9 hosts paired; profile 9 survives a power cycle
- [ ] Hub and module-controller firmware build in CI
- [ ] **Replace one of each small board (comms, USB port, battery module, dial,
      expansion) with hand tools only**, from the published repair guide
- [ ] Every BOM line in stock before ordering, **with a second source recorded**
- [ ] Build guide reproduces the assembly from the published files alone

## 17. What rev 8 changed

Decided 2026-09-26 in a design review with the user; the rev 7 state is commit
`0b22b91`.

| Was (rev 7) | Now (rev 8) |
| --- | --- |
| Case SLA resin from a large-plate print service (M9, rev 7) | **FDM ASA on the user's H2S / CORE One, one piece per module, M2 heat-set inserts** (2026-09-29) |
| Three modules, each with a core board (MDBT50Q, full power path), 2 battery boards, a USB port board, link boards and seam boards | **One hub** with the only MCU module, the only power path and the host port; **three key modules with no radio, cells or power path** |
| ZMK split: `left` central, `right` and `numpad` peripherals; wired UART transport with BLE failover, all-or-nothing, pair-2 passthrough on `right`, orientation detection, handshake, hysteresis | **One ZMK keyboard**; key modules are I2C targets behind a TCA9548A; no split transport |
| Key matrix, dial and LED driver wired to the core over `J_ROW`/`J_COL`/`J_LED` | **Module controller** MCU on each key board: scans, decodes the dial, drives the LED driver, serves one register map; **TCA8418 rejected** (25–40 ms per press, SCPS215G p. 33), **hub-scanned TCA6424A rejected** (polling cannot cross a radio link) |
| Link boards (upstream with KTS1693, downstream with TPS22950L) + seam boards with SAMZO magnetic pogo pairs | **Comms board pairs**, swappable; rev A cable comms board (repurposed link board: hub population with TPS22950L, module population without); seams mechanical only; pogo parts dropped |
| Link over USB-C: pair 1 on D±, pair 2 on SBU, needing a full-featured cable between `left` and `right` | **Any USB 2.0 C-to-C cable**; SDA/SCL on D±, `INT` on CC; star wiring |
| 4 AA per module in two packs (12 AA per keyboard), pack OR (LM66200) and UVLO on each core | **Chainable 2×AA battery modules** on the hub, rev A two; each carries its own ideal diode; UVLO and power switch on the hub drive `PACK_EN`; `PACK_SENSE` keeps the supervisor alive **Rev 8.1 (2026-09-30): up to 3 passive 4×AA (NiMH) modules, one chain line per pack, protection + OR + UVLO on the hub** |
| Battery lighting cap 250 mA per module | **250 mA for the whole keyboard**; more battery modules add runtime only |
| Link VBUS switch on the downstream link boards, gated by handshakes | **Slot switch per hub slot**, on while its module answers |
| Module ID: resistor on the key board, ratiometric ADC read on the core, safe mode on mismatch | **Strap read by the module controller**, reported in the register map; any module in any slot |
| Core PCB 32 × 90 mm, 7 nets unrouted after every scripted approach | **Hub core = one base board, ~94 × 94 mm, in a ~100 × 100 mm tower** (2026-09-29; a vertical MCU board 2026-09-26 → 29); rev 7 core PCB kept in git for reference |
| Every board inside a module case | **The hub is a stack of layers**: optional layers (display…) / core / swappable connector layer / battery modules 1…N or a Qi2 board; 2×10 expansion (reversal-safe, CS0–CS3 by jumper, an ID EEPROM per layer; X1, 2026-09-28), 2×16 slot and 2×6 chain stacking headers |
| Qi2: keepouts, DNP footprints, a future Li-ion battery board | **Qi board on the hub's chain header, instead of the battery stack**, `AUX_5V`, never charging cells |
| — | **Reserved for future comms boards**: spare pins and `VSYS` on `J_SLOT`, spare pins on `J_COMM`, `VIN` accepts power from the module side |
| MDBT50Q-1MV2 with "-U1MV2 (chip antenna)" as second source, both keepouts on the core | **MDBT50Q-U1MV2 only** (u.FL; Raytac ver L: 1MV2 is the chip-antenna part, U1MV2 the u.FL part), on the base board; adhesive flex antenna inside the case wall, blanked RP-SMA knock-out for an external antenna (2026-09-29); **2026-10-01: Yageo ANTX100P011B24003 PCB antenna inside, blanked knock-out for the Yageo ANTX100ETHAB24553 whip, both on Raytac's -U list (no RP-SMA)** |
| `CONFIG_BT_MAX_PAIRED=11` | 9 |
| Untethered use: modules work apart on BLE | **Modules need their hub cable**; accepted |
| Untethered deep sleep: a sleeping satellite cannot wake the central | Any module's keypress wakes the hub |
| 9 PCB designs, 22+ boards per keyboard | 8–9 PCB designs, ~18 boards per keyboard (fewer designs with assembly-house parts on them) |

Carried over unchanged: the pack chain per pack (OVP, reverse block, PTC, TVS,
bleeder, gate network, series budget), the host USB port board, the logic and LED
power paths, lighting, dial board, expansion board, layout geometry, plate, case
print route, most of the verification list (rev 8.1 replaced the pack chain and the
logic and LED power paths, below).

### Rev 8.1 (2026-09-30 – 2026-10-01): battery architecture

Decided with the user one part at a time (E21); switchover simulated in
`tools/sim/e21_switchover.py`. §4 was rewritten around it on 2026-10-01.

| Was (rev 8) | Now (rev 8.1) |
| --- | --- |
| Chainable 2×AA battery modules, any number, each with TVS, AO3415A reverse FET, TPS3840PL35 + AO3415A OVP, PTSLR12066V175 PTC and an LM66200 ideal diode on `PACK_EN`; MPD BC2AAPC | **Up to 3 passive 4×AA (NiMH) modules**: MPD BC4AAPC, Bourns MF-MSMF125/16X PTC, a line shift so each pack reaches its own hub input (`PACK_A`/`B`/`C`); a 4th module is unconnected |
| Chain 2×6: 4 `VBAT`, 4 GND, 2 `AUX_5V`, `PACK_EN`, `PACK_SENSE` | **2×6: `PACK_A`/`B`/`C` twice each, 4 GND, 2 `AUX_5V`** (reversal-safe) |
| UVLO TPS3840PH18 on `PACK_SENSE` driving `PACK_EN` (~1.9 V per 2-cell pack); firmware system-off ~2.05 V on a rev 7 AO3415A/2N7002 divider | **TPS3840PL40** fed from the pack inputs through BAT54C + BAT54, 10 kΩ / 1 µF: cut ~4.16 V at the hub input; firmware reads that node (200 k / 100 k via a CSD25483F4, bring-up gain calibration): system-off 4.12 V, lighting off 4.25 V |
| Per-module OVP, gate RC, 6.2 V gate zeners | **None**: Li-ion unsupported, worst pack ~6.4 V |
| Logic rail: TPS61099DRV/MAX17222 boost and TLV75733P LDO on a TPS2116 priority mux | **TPS70933** LDO from `SYS` |
| LED rail: TPS61023 boost (750 k / 100 k) on battery, VBUS on USB, TPS2116 priority mux | **TPS630701** buck-boost (fixed 5.0 V, XFL4020-152ME) from `SYS` on both |
| Packs OR-ed on the modules | Per pack input on the hub: **SMF4L9.0CA + LM74610-Q1 + CSD17313Q2** (1 µF pump cap), OR into `VBAT`, **CSD25402Q3A** battery switch (power switch AND UVLO AND no USB, 2 × DMN63D8LDW) and a second one for USB into `SYS` (TPS3840PL43 detect, 2.2 MΩ / 22 nF delay); `SYS` 100 µF |
| Series path ~296 + 10·n mΩ | ~291 mΩ worst (pack C, three pogo hops) |
| Slot-VBUS TVS SMF6.0A on both comms-board populations | **TVS0500DRV** (2026-10-01, E7: the slot VBUS is the always-live LED rail; the SMF6.0A has no leakage figure at 5 V) |
| Idle current unestimated | Datasheet estimate **~0.26 mA typ / ~0.47 mA worst**, ~9 / ~5 months per pack (E7) |

## 17a. Earlier changelogs (rev 2–7, per-module-core architecture)

These describe the superseded architecture. They are kept because the carried-over
power design and many rejected alternatives are explained there.

## 17. What rev 7 changed

The rev 5 review items that rev 6 left conditional, open or unverified, closed by
decision or datasheet check (2026-09-14).

| Was | Now |
| --- | --- |
| Downstream KTS1693 awaiting Kinetic (E13), keyed variant as fallback | **Downstream link boards drop the KTS1693**: same PCB, 0 Ω across the footprint, no `ACOK`, **10-pin `J_LBD`** vs upstream 9-pin `J_LB`. A >6 V non-compliant source on a downstream port reaches the TPS22950L behind only the SMF6.0A |
| MDBT50Q-U1MV2 a second source "only if" the core fits both | **Core laid out for both land patterns and keepouts**; RSSI checked with each |
| Case in sections or from a service (M9) | **One piece per module from a large-plate service** |
| OVP gate RC ~10 ms, TPS3840 timing not looked up | **τ ≥ 25 ms**, capacitor gate-to-source. Window is ~460 µs (filter ≤110 µs + `tSTRT` 350 µs max); at the AO3415A's −0.3 V `VGS(th)` min, 10 ms crossed it at ~380 µs |
| TPS2116 "1.3 ms switchover"; `SDB` blanking ISR + bulk for ISR latency (E4) | Switchover is **8 µs typ**; 1.3 ms is soft start. **~10 µF LED-rail bulk, no ISR** |
| Logic boost: TPS61099 fixed 3.3 V, package unchecked (P11) | Fixed 3.3 V is WCSP only; **TPS61099DRV adjustable (WSON-6) with a ~1 µA divider**. Down mode regulates up to 3.8 V in, so pass-through never reaches `VDD` |
| KTS1693 second source: survey owed a QFN/DFN part (P7) | **TPS25947** (28 V abs-max, adjustable OVLO, 1.2 µs turn-off, 28 mΩ, ~430–610 µA, QFN 2 × 2) recorded as the leaded candidate; not footprint-compatible; stock unchecked |
| Local-port short not in E9 | Added to E9 |
| JST GH cycles and 2.75U spacebar kit deferred | Tracked in open questions (P9, P12) |

### Rev 6 changelog

Findings from the rev 5 review ([`docs/03-review-rev5.md`](../docs/03-review-rev5.md)),
with disposition. The one design choice was the logic rail; the rest are
corrections.

| Was | Now |
| --- | --- |
| `VSYS` unregulated, 1.85–3.3 V, different per module | **Regulated 3.3 V always**: dedicated logic boost (TPS61099 family) from VBAT on the mux's IN2, VBUS LDO on IN1. A 3.3 V module could not read a 2.2 V module's TX and over-drove a 1.9 V module's pin; the wired link only worked with matched cells |
| OVP FET on by default, supervisor turns it off | **Off by default**: gate pulled up to source, ~10 ms RC turn-on, diode fast turn-off. A 14500 pair passed 8.4 V to the LM66200 and toward the MCU for the supervisor's start-up plus release delay |
| Module-ID pull-up from the switched `VBAT` node | Pull-up top is the divider-enable GPIO: ratiometric to `VDD`. On USB with no cells the ID read as a short → safe mode |
| Boost `EN` and "3V3 LDO EN" as plain GPIOs | LED boost `EN` pulled up; logic LDO and logic boost always on; only the expansion LDO gated. On USB with no cells nothing could enable the LDO; on battery `VIO` came up before `VCC` at every boot |
| USBLC6-2SC6 at the connector, `VBUS` pin unstated | `VBUS` pin on the KTS1693's protected side (5.5 V abs-max) |
| LED rail rides the mux switchover on bulk capacitance | ~460 µF at 250 mA; instead `SDB` low in the VBUS-event ISR, bulk sized for that latency; TPS2116 switchover figure to be confirmed (E4) |
| `left`'s pair-1 TX always driven | Pull-up-only input until RX detect; ~5 mA into a switched-off neighbour's clamps otherwise |
| Local port `ISET` 3.0 A | ~2.0 A; the LM66200 behind it is 2.5 A abs-max |
| Downstream KTS1693 reverse conduction covered by the OTG section | Sustained `OUT` > `IN` in the shorted and tripped cases is not; Kinetic asked (E13); keyed DNP variant is the fallback |
| MCU second sources MDBT50Q-U1MV2 / BT840 | BT840 is a different pad layout; U1MV2 only if the land pattern and keepout are laid out for both |
| Antenna at `left`'s "outer edge" | Rear outer corner, behind the key field, not under the palm |
| SLA case, one piece per module | 233 mm deep modules exceed desktop SLA plates; sections or a service (M9) |
| Reverse LED position unstated | South (0, +5.08 mm); north collides with the Kailh socket |
| KTS1693 escape routing unstated | 0.15 mm vias / via-in-pad on the USB port and link boards; P7 survey must include a QFN/DFN part |
| Thresholds scattered as "~" | One table in §9 with measurement conditions |
| "Nothing transmits" when wired | Requires stopping peripheral advertising; added to the module and §16 |
| CC sense straight into `AINx` | 100 kΩ series |
| `P0.09`/`P0.10` counted as GPIO | Need `CONFIG_NFCT_PINS_AS_GPIOS=y` |
| Cable SBU straight | A compliant cable crosses SBU1↔SBU2; labels in the §16 test |

Not adopted from the review: none. Deferred: JST GH ~30 mating cycles (build-guide
note, P9), 2.75U spacebar sourcing (Phase 1 cap count).

### Rev 5 changelog

A repairability decision: each module splits into boards by failure mode, and
wear and abuse land on small plug-in boards.

| Was | Now |
| --- | --- |
| One main PCB per module, everything soldered to it | **Core, key, USB port, link, seam, battery and dial boards** (§2a), joined by locking wire-to-board cables |
| Three different MCU and power-path layouts sharing schematic sheets | **One core board** for all three modules: identical layout and BOM, union pinout, swappable for fault finding |
| KTS1693 WLCSP on every main board; one damaged part scraps an assembled board | KTS1693 only on the USB port and link boards; a damaged one costs a small board |
| Pack protection on the main board | **Battery board** per pack, hand-solderable except the PTC (reflow/hot air); takes reversed cells, 14500s and terminal ESD |
| Encoder soldered to `right`'s main board | Dial board on a 5-contact cable |
| Seam daughterboard on a right-angle 2.54 mm header to the main PCB | Seam board **cabled to its link board**; rear port and seam join ahead of the link board's KTS1693; one seam design with two pair positions |
| Link ports on the main PCB, with a pinout per board type | **One link board design** at all four positions; mirroring and pair roles are key-board routing |
| `left`'s link switch fed from local VBUS | Fed from `VBUS_IN` like `right`'s; one source net per core |
| Pin budget `left` 38, `right` 40, `numpad` 31 | Core union **45 / 47**, 22 of 23 full-function pads, including module ID and two `ACOK` lines |
| Pair-2 budget ~175 pF, rounded to 200 pF | ~0.8 m of internal cable added: ~225 pF, rounded to 250 pF; 12 % of a 460 800-baud bit |
| One firmware target per module | One core **board** definition plus three **shields**; module-ID check with safe mode |
| No service provisions | Tool-less battery door, M2 screws throughout, Tag-Connect footprint, `ACOK` blink codes, series R so a live lighting-cable unplug is survivable, repair guide and an optional spares list |
| Numpad may carry one pack | Two battery boards on every module, the numpad included |
| 3 KiCad projects + plates | 9 projects + plates; refs partitioned per project |

### Rev 4 changelog

A topology decision rather than review findings: `left` owns everything host- and
radio-facing, and `right` passes the numpad's link through in copper.

| Was | Now |
| --- | --- |
| `right` central, host USB and host BLE on `right` | **`left` central.** Host port, host BLE and split central role on `left`; `right` is a peripheral |
| Star wiring: both satellites cable into `right` | Both UART pairs terminate on `left`; pair 2 runs through `right` as copper with no MCU connection |
| One link type, 4 nets | `left`–`right` 6 nets (pair 2 on SBU); `right`–`numpad` 4 nets |
| Any USB 2.0 data cable everywhere | `left`–`right` needs a **passive full-featured** USB-C cable; `right`–`numpad` unchanged |
| 4-contact pogo, pins on `right`'s two walls | 6 nets on the `left`–`right` seam, 4 on `right`–`numpad`; spring halves always upstream |
| `right` sources both link ports | `left` sources `right`; `right` sources the numpad, gated by a `pair2_up` flag from `left` |
| All link pairs orientation-free | Pair 2 on SBU flips with the plug; `left` detects orientation and treats both-high as a shorted pair |
| Rear-cable swap test (`left` in the numpad port) | No longer a topology: `left` has one port. Replaced by numpad-into-`left`, `right`-port-to-`right`-port and flipped-cable-plus-seam cases |
| Radio in the centre module, worst position | Radio at `left`'s outer edge |
| Dial on the central | Dial on a peripheral; sensor forwarding to be verified in week 1 |
| `right` pin budget 43 / 47 | `left` 38, `right` 40, `numpad` 31 |
| Untethered sleep: press a key on `right` | Press a key on `left` |
| "`PR5L2820-4P-C-F` right-angle spring pins" and Mill-Max target discs | That part is the **flat, vertical** half of a magnetic pair. `PR5L3715-4P-C-H` spring half upstream, `-C-F` flat half downstream, on seam daughterboards; two pairs on the 6-net seam |
| 6-contact seam part owed | Two stocked 4-contact pairs |
| Dial sensor forwarding and runtime pinctrl swap unverified | Both verified in source (§9) |
| Pair-2 baud open, series R at every connector | 460 800 baud against a 200 pF budget; 470 Ω at MCU pins only |
| TLV6703 + AO3415A USB OVP | Comparator output undefined for 150 µs at power-up, VDD 20 V abs-max, FET −20 V: TLV6713 + AO3401A with delayed turn-on |
| LED rail LM66200 auto-OR, "VBUS always wins" | False at USB's low tolerance; TPS2116 priority mode |
| Driver headroom 600 mV | That was at 672 mA / 42 mA; ~0.4 V at our currents against Vf max 4.1 V |
| LED windows as milled slots | Ø3.2 mm round holes per SunLED |
| TPS3840 10 V abs-max; TPS22950L limit from 0.05 A; PTC Vmax ≥9 V | 12 V abs-max (10 V recommended); L variant limits from 0.5 A; 6 V PTC sufficient behind the OVP |

### Rev 3 changelog

Findings from the second review, with disposition.

| Was | Now |
| --- | --- |
| Per-link failover: one satellite on BLE, the other wired | **Impossible in core**: one `active_transport` for the whole central. All-or-nothing, with an all-present flag so a cabled satellite never strands |
| USB VBUS OR-ed straight onto VSYS | **Would have put 5 V on `VDD`.** VBUS → 3.3 V LDO → priority mux; packs isolated on USB |
| Wake and cable-detect GPIOs budgeted | **No conductor existed for them.** Both moved onto UART RX; 4 pins freed |
| UVLO on boost EN | **Collapsed driver VCC under live `VIO`**, and the MCU kept draining cells. Firmware system-off at 2.0 V + supervisor load switch at 1.85 V |
| "Any USB-C cable including charge-only" | Charge-only cables have no D+/D−. USB 2.0 data cable required |
| "Two packs halve the C-rate" | OR-ing does not share. Per-pack parts sized for full load; battery lighting capped at 250 mA rail |
| No overvoltage protection | 14500 pair = 8.4 V. OVP per pack, 3.7 V ±3 % |
| Lithium primaries accepted, VSYS to 3.4 V | L91 fresh = 3.66 V. Alkaline and NiMH only |
| Link VBUS inward-only at both ends, yet a 3-module USB budget | `right` sources through gated ILIM switches after a UART handshake that rejects loopback chargers |
| All USB LED power through LDO + boost | ~270 mA rail on 500 mA USB. LED rail fed from VBUS directly; host CC sensed for 1.5/3 A |
| 42 mA peak per die | ~2× typical reverse-mount DC rating. 20 mA peak, `RSET` 42.2 kΩ |
| "10 keys dim → 24 mA from cells" | That was rail current. Table rebuilt at 20 mA and a 2.4 V pack |
| Cross-module lighting, "no core patch" | No generic payload in the protocol. Tunnelled through `INVOKE_BEHAVIOR` |
| Joined modules on USB-C cables in a 6 mm seam | Plugs need 10–25 mm. Seam pogo, pins on `right`, pads on satellites; rear USB-C when separated |
| Plate material unstated | 1.5 mm FR4, no copper |
| Width "the K860's 456 mm" | ~468 mm with seams, accepted |
| Profile indication implied shine-through | Any caps; glow accepted, checked in Phase 1 |
| 1 MHz I2C | nRF52840 TWIM max 400 kHz |
| `BT_MAX_CONN` 2–3 | ≥3 |
| `SDB` missing from pin budget | Added |
| EC11 "~20 detents" | Bourns PEC11R 24 detents / 24 pulses; both switches open at every detent |
| UVLO ~1.85 V on a separate load switch | LM66200 dual OR doubles as cutoff; TPS3840PH18 via BAT54C ≈ 1.9 V at the pack |
| OVP as a generic switch | No integrated OVP goes below 4 V. TPS3840PL35 + AO3415A; the PL35 trips rising near 3.7 V |
| 150 mΩ series budget | Unreachable with two FETs at 1.9 V gate drive; 300 mΩ max |
| No USB input OVP | Downstream parts are 5.5 V; TLV6703 + P-FET per local USB port (NCP361 600 mA cap, TPD1S514 DSBGA) |
| No pack-terminal ESD part | 9 V-standoff TVS + RC to supervisor |
| Link VBUS switch unspecified | TPS22950L, latch-off |
| LED part open | SunLED XZMDKCBDDG45S-9 |
| Boot fallback assumed | `CONFIG_ZMK_USB_BOOT=y` |
| Satellite battery reporting BLE-only | `BATTERY_EVENT` is now transport-level; re-check |
| Deep-sleep wake across BLE unstated | Documented limitation |
| Transport switching undamped | Asymmetric hysteresis, no switch mid-chord, held keys released on loss |
| Rear ports fixed per satellite | Mapped by handshake `sat_id` |
| Satellite-to-satellite cable: TX against TX | Satellites drive TX only after a `PING` |
| CC sense on `right` only | All three boards |
| Satellite pogo pads, plain | ENIG wears through; JLCPCB hard gold is edge-finger only. SMD gold target contacts on ENIG |
| ZMK dependency unmanaged | Pinned commit + weekly canary |
| Number row gated on Phase 1 | Locked 6/3 |
| Zephyr bulk write unknown | Verified: single burst, plus `current_limit()` |

### Rev 2 changelog

| Was | Now |
| --- | --- |
| Link UART same pinout both ends | **Dead link.** D+ passes straight through, TX met TX. Mirrored pinout per board type, A6=B6 and A7=B7 tied |
| Wired-only, untethered deleted | Both transports, wired preferred, BLE failover. Untethered restored |
| "ZMK core untouched" | Core hardcodes `WIRED_PERIPHERAL_COUNT 1`; a 2nd peripheral would have smashed the stack. BLE split at 2 peripherals sizes it via `MAX()` |
| Transports mutually exclusive | Wrong. Both compile in; core fails over at runtime |
| Caps ≤2U | Impossible to buy a bottom row. Now ≤2.75U, flat bottom row |
| 12 sinks × 16 sources | Inverted. 16 CS **sources**, 12 SW **sinks**. Wiring is 1 CS + 3 SW |
| 4.0 V LED rail | 4.7 V. 600 mV internal drop left too little for blue and green |
| I2C level translator | Deleted. `VIO` pin 39 ties to VSYS |
| Power-gate the driver | Violates abs-max on `VIO`/SDA/SCL. `SDB` + software shutdown instead |
| "3 % → 245 mA" | Was 8× off, from mixing the addressable current model in |
| ~45 usable GPIO | 21 pads are LF-only, no UART/I2C/SPI/PWM. Pin classes now explicit |
| 32 kHz crystal assumed on-module | It is not. Added, 2 pins |
| Pitch opened to 19.8 mm | Formula was 2× wrong on a 6× overstated angle. Back to 19.05 mm pending Phase 1 |
| 14500 "no layout change" | Would destroy the MCU. VDDH/REG0 topology now reserved |
| No reverse-polarity, fuse or UVLO | All three added |
| Link VBUS shared net | Per-port inward-only diodes; `VBUS` pad and expansion 5 V from the local port only |
| Battery reporting "works" | Would report 0 % forever below 3450 mV. Custom SoC driver added |
| No mechanical content | §11 added, full scope including palm rest |
| Milled LED windows unmentioned | §12 added |
| Numpad 20 keys | 17 |
| 2×AA per module | 4×AA as two independently OR-ed 2-cell packs, under the palm rest |
| Detentless encoder | Detented |

Rev 2 reviewer finding not adopted: that LED polarity was wrong and common-cathode
required. The datasheet's own 64-RGB figure corresponds to common-anode with
1 CS + 3 SW.

## 18. Open items

All open questions, with what resolves each and when, are tracked in
[`docs/open-questions.md`](../docs/open-questions.md); candidate parts and the
datasheet queue in [`docs/02-parts-shortlist.md`](../docs/02-parts-shortlist.md).
Rev 8 opens:

- **P19** closed 2026-09-26: MSPM0G3505 LQFP-48. **F7** its firmware framework,
  register map, and the BSL-over-link update flow (hardware side decided
  2026-09-29: software entry, vector table written last, PA18 rescue pad; §9).
- Pin orders decided 2026-09-29: `J_COMM`, `J_SLOT`, the 2×16 slot header (§6).
- **E16** I2C through a USB 2.0 cable's D± pair; **E17** CC as `INT` (closed 2026-09-26: 220 kΩ pull-ups); **E18** slot power policy (closed 2026-09-26: answer window ~200 ms, ~100 ms re-probe every ~2 s awake, none asleep);
  **E20** closed 2026-09-26 (LM66200 per pack, 2×6 header, ~296 + 10·n mΩ).
- **M10** battery-module mechanics (contacts decided: 2×6 stacking header, stack only, any number of modules;
  battery seams on a Mill-Max 827-22-012-10-004101 pogo strip, 2026-09-30; targets Mill-Max 1578-0 discs, riser Samtec DW-06-17-T-D-254, 2026-09-30);
  **E21** closed 2026-10-01: the rev 8.1 battery power path (§4, simulated; §17 rev 8.1
  table); **E7** datasheet idle estimate ~0.26 mA typ (§4), measured in 7a;
  **E22** closed 2026-10-01: KTS1693 trip lowered to 5.38–5.78 V (27.4 kΩ) for the
  MDBT50Q `VBUS` pad's 5.8 V abs-max;
  **M11** the hub enclosure (2026-09-29: ~100 × 100 mm tower, MCU on the base board,
  core one joint tall; workflow in §14). **P20** closed 2026-10-01: Yageo
  ANTX100P011B24003 PCB antenna + a blanked knock-out for the Yageo
  ANTX100ETHAB24553 whip, both on Raytac's -U approved list (§13).
- **X1** closed 2026-09-28: top expansion header 2×10, reversal-safe, CS0–CS3 by
  jumper, an ID EEPROM per layer at 0x50 + CS number (§6).
- **F9** Zephyr/ZMK support for the TCA9548A and a custom `kscan` at the pinned
  version.

Rev 8 closes as moot: everything about the split transport, pair 2, the seam pogo
parts (P5, P6, P8), the link boards' KTS1693s, and the module-ID ADC bands (F6).
