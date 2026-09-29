# Split K860-alike — hardware + firmware spec

Three-piece mechanical keyboard styled on the Logitech ERGO K860. Key modules:
`left` (alphas), `right` (alphas + arrows + nav + dial), `numpad`. **Rev 8: the key
modules carry no radio, battery or power path.** A single **hub** on the desk holds
the radio, the host USB-C port, the cells, the power path and the expansion
connector, and each key module plugs into it through a **swappable comms board
pair**, a USB-C cable in rev A. BLE or USB to the host, per-key RGB, 9 host
profiles, MX hotswap, AA cells in chainable 2-cell battery modules.

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
   | CORE LAYER   base board (one board, ~84 x 84 mm): MDBT50Q-U1MV2,  |<-- host USB-C (USB port board)
   |              power path, LED rail, TCA9548A, buttons, all         |    expansion SH socket (expansion board)
   |              stacking headers; u.FL -> flex antenna on the        |    antenna inside the case wall
   |              inside of the case wall (RP-SMA knock-out, blanked)  |    (external RP-SMA optional)
   +==== slot header 2x16 ==== chain header 2x6 ======================+
   | CONNECTOR LAYER (swappable: wired now; radio, optical, mixed      |
   |   later). Wired: carrier PCB + 3 socket boards (hub-side comms    |--> slot 1 --> USB-C cable --> [left]
   |   boards on J_SLOT), chain passed through                         |--> slot 2 --> USB-C cable --> [right] + dial
   +============================ chain header 2x6 =====================+--> slot 3 --> USB-C cable --> [numpad]
   | BATTERY MODULE 1  (2xAA)   -- or instead: Qi2 board (ends the stack)
   +============================ chain header 2x6 =====================+
   | BATTERY MODULE 2  (2xAA)
   +===================================================================+
   | ... BATTERY MODULE N (any number)
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
  stacking header. The module's u.FL feeds an **adhesive flex antenna on the
  inside of a core-section wall**; the wall also has a **blanked RP-SMA
  knock-out**, so an external antenna (u.FL-to-RP-SMA pigtail) is a swap, not a
  respin (§11, §13).
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
- **Batteries chain.** Each battery module is one 2×AA pack with its own protection
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
| MCU | **MDBT50Q-U1MV2** (u.FL, 2026-09-29), on the base board; flex antenna inside the case wall, blanked RP-SMA knock-out for an external antenna |
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
reversed or Li-ion cells and encoder wear land on boards that cost a few euros and
plug in with cables. The hub core and key boards sit behind that protection.

| Board | Design | Per keyboard | Carries | Assembly | Replaced when |
| --- | --- | --- | --- | --- | --- |
| **Hub base board** (horizontal, ~84 × 84 mm; one board since 2026-09-29) | 1 | 1 | **MDBT50Q-U1MV2** with its u.FL to an adhesive flex antenna on the inside of the case wall (or a u.FL-to-RP-SMA pigtail to the blanked knock-out), 32.768 kHz crystal, `VDD`/`VBUS` decoupling, SWD pads + Tag-Connect TC2030-NL footprint, 27 Ω D+/D−, reset and bootloader tactiles, slide power switch and UVLO supervisor on the chain's `PACK_EN`, `VBUS_IN` OR (host USB + chain `AUX_5V`), logic LDO + logic boost (TPS61099DRV or MAX17222) + `VSYS` priority mux, LED boost + LED-rail mux, expansion LDO + `J_EXP`, **TCA9548A I2C switch**, 2×10 expansion header on top, 2×16 slot header and 2×6 chain header underneath, `J_USB`, `VBAT` sense, test points | assembler | power path or MCU fault |
| **Connector layer, wired** (2026-09-26) | 1 carrier PCB | 1 | carrier PCB: 2×16 slot header and 2×6 chain header on top, 2×6 chain header underneath (chain passed through), 3 × 14-pin `J_SLOT` to the socket boards; no active parts planned | assembler (headers) or by hand | rarely; the socket boards take the wear |
| **Key board** | 3, one per module | 3 | hotswap sockets, diodes, RGB LEDs, IS31FL3733, **module controller**, 3.3 V LDO (TPS7A0233PDBVR, TLV75733PDBVR second source on the same footprint), I2C pull-ups, module-ID strap, SWD pads, `BSL_invoke` rescue pad (PA18 + 3V3, §9), `J_COMM`, `J_DIAL` (`right`) | assembler | rarely; sockets and LEDs are hand-reworkable |
| **Comms board, cable** | 1 PCB, 2 populations | 3 hub side (the wired connector layer's socket boards) + 3 module side | GCT USB4085 USB-C receptacle, TPD6E05U06 on A5, B5, A6, B6, A7, B7, SMF6.0A on VBUS. **Hub population:** TPS22950L slot switch + `ILIM` 624 Ω, CC pull-ups fed from `SLOT_EN`, **14-pin `J_SLOT`**. **Module population:** BAT54C joining CC1/CC2 into `INT`, **10-pin `J_COMM`**. KiCad design variants `hub` / `module`; the header pin counts differ so neither fits the other's position (repurposes the rev 7 link board) | assembler | socket worn, surge |
| **USB port board** | 1 | 1 (host port, on the hub) | USB-C receptacle, 2 × 5.1 kΩ CC, KTS1693, OVLO divider, TVS2200 footprint, SMF6.0A, USBLC6-2SC6, TVS2200 on CC1/CC2; GCT USB4085 (unchanged from rev 7) | assembler | socket worn, surge, OVP latched and not recovering |
| **Battery module** | 1 | 2 in rev A, more by chaining | one 2×AA holder and the rev 7 pack chain (SMF4L9.0CA, reverse-block and OVP AO3415A with gate clamps, TPS3840PL35 + RC, PTC, DNP OVP bypass, R806 bleeder), **plus its own ideal diode onto the chain's `VBAT`** (LM66200, one channel, decided 2026-09-26), a BAT54 onto `PACK_SENSE`, and chain-in / chain-through contacts | hand-solderable except the PTC and the LM66200 (0.5 mm-pitch SOT), both reflowed or hot-air soldered | reversed cells, 14500s, terminal ESD, corroded holder |
| **Dial board** | 1 | 1 (`right`) | unchanged from rev 7: PEC11R, push-switch diode, 1 kΩ + 10 nF on A and B, DNP TPD4E1U06DBV, 5-pin `J_DIAL`; the A/B filter re-checked against the MSPM0G3505's 40 kΩ pull-up and unchanged (2026-09-26) | hand-solderable | encoder worn |
| **Expansion board** | 1 | 1 (on the hub) | unchanged from rev 7: JST SM12B-SRSS-TB, TPD4E05U06 + TPD6E05U06, 15-pin `J_EXP`; shares the expansion bus with the top header (kept 2026-09-26 for cabled accessories) | assembler (ESD arrays) | socket worn, ESD hit |
| *Optional top layers* (display first, future) | per add-on | 0..n | stack on the core's 2×10 expansion header and pass it through; each takes one SPI chip select (CS0–CS3) by a jumper, carries a 24xx02-class ID EEPROM at 0x50 + its CS number (X1, §6) and needs distinct I2C addresses for anything else; ESD on anything user-touchable | — | — |
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
- **Service rule: slide switch off and USB unplugged before unplugging any
  internal cable.** Advice, not the only protection: the key board limits current
  into its logic pins if a link is pulled live (§4), and link cables are
  user-pluggable by design (§6).
- **Tool-less cell access.** Each battery module opens without tools. Every board
  is fixed with M2 screws into heat-set inserts, so one driver services the whole
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
| Battery (rev 8) | **Chainable 2×AA battery modules**, rev A two, **stacked under the hub on a pass-through stacking header** (side by side: future option); alkaline and NiMH; per-pack ideal diode; **no charging** | runtime scales by adding modules; the rev 7 pack chain is reused per module |
| Qi2 (rev 8) | **Optional, later**: a Qi board on the hub's chain header feeds `AUX_5V`, **used instead of the battery stack**; it never charges cells | reserve the path now, design the board later |
| Switches | Cherry MX, Kailh hotswap `CPG151101S11` | off-the-shelf caps |
| Caps | widths 1U–2.75U inclusive, **any off-the-shelf set** | standard sets need 2.25U/2.75U; shine-through not required |
| Spacebar | 2 × 2.75U, one per half | the K860's spacebar is already split |
| Bottom row | flat, not arced | lets long keys stay rectangular; the K860's bottom row is nearly level anyway |
| Pitch | **19.05 mm throughout, pending Phase 1** | see §10 |
| Width | **~468 mm accepted** | 456 mm key field + two ~6 mm seams; known deviation from the K860 |
| Layout | K860 arc via per-key rotation, alpha rows only | the arc is the K860 look |
| Board partition | **by failure mode** (§2a): hub core, key, comms, USB port, battery, dial, expansion | a worn or abused part costs a small plug-in board, not an assembled board |
| Interconnect | **several small locking wire-to-board connectors, split by function**, JST GH family (1.25 mm, positive lock) proposed, **any fallback must also lock**; ≥2 contacts per power net; unique pin counts | hand-solderable, premade cables, a cable is a spare part |
| Module ID | strap on the key board, read by the module controller, reported in the register map | identical module-controller firmware on every key board; the hub maps keys by ID, not by slot |
| Service | slide switch off and USB unplugged before unplugging an internal cable, **backed by series R into the key board's logic pins**; tool-less cell access; M2 screws throughout; every external connector is user-replaceable by swapping the small board it sits on | builders will pull cables live anyway; plugs wear and take the surges |
| MCU (hub) | **Raytac MDBT50Q-U1MV2** (u.FL connector, no on-module antenna; 2026-09-29), **single source accepted**; on the base board; antenna: adhesive flex antenna on the inside of a core-section wall, **blanked RP-SMA knock-out** for an external antenna on a u.FL-to-RP-SMA pigtail | pre-certified module, antenna placed away from the stack's copper and cells; Raytac datasheet ver L: 1MV2 = chip antenna, P1MV2 = PCB antenna, U1MV2 = u.FL (the spec called U1MV2 the chip variant until 2026-09-29); all three share one land pattern; Fanstel BT840 is a different pad layout and **not** a drop-in |
| LFCLK | external 32.768 kHz crystal | **not** on-module; internal RC is ±250 ppm |
| Seams | numpad = digits+operators only; arrows+nav on `right`; **mechanical join only** (rev 8) | detaching numpad loses only digits; nothing electrical crosses a seam |
| Lighting | IS31FL3733, common-anode RGB, 1 CS + 3 SW per LED | per-key independent colour, 8-bit PWM per channel; serial-chain parts cost 0.6 mA/LED idle |
| LED current | **~20 mA peak per die**, `RSET` ≈ 42.2 kΩ | safe for any reverse-mount RGB part at 1/12 duty; halves driver heat |
| LED rail | **~5.0 V boost on battery (E19, 2026-09-26; was 4.7 V); VBUS (~5 V) on USB**, priority-muxed; carried to every slot through a latch-off switch | USB lighting skips the LDO and boost; 5.0 V leaves ≥0.3 V of LED headroom after a 1 m cable |
| Driver idle | `SDB` + software shutdown, rail stays up | power-gating VCC violates abs-max on `VIO`/SDA/SCL |
| Cells | **alkaline and NiMH only**, 1.9–3.3 V per 2-cell pack. Low-self-discharge NiMH recommended | lithium primaries (L91) reach 3.66 V fresh, over nRF52840 `VDD` recommended max |
| Overvoltage | per pack, unchanged from rev 7: TPS3840PL35 + series AO3415A, off by default, τ ≥ 25 ms, R806 bleeder, ≤1 µF on each pack node | a 14500 pair is 8.4 V; see §4 |
| Undervoltage | firmware system-off at ~2.05 V; **the hub's TPS3840PH18 drives the chain's `PACK_EN` at ~1.9 V**, fed from `PACK_SENSE` (a diode-OR of every pack node) | every pack's ideal diode is the cutoff; the supervisor survives its own cutoff |
| Pack series resistance | ≤300 mΩ max per path (~170 mΩ typical) | two FETs at 1.85 V gate drive cannot meet 150 mΩ |
| Host USB input | **KTS1693** on the host port's USB port board, external divider for a 5.55–5.95 V trip, `ISET` 4.99 kΩ (1.82–2.18 A latch) | everything behind it is 6.0 V abs-max; 100 ns turn-off |
| Slot power | **TPS22950L latch-off switch per slot on the hub-side comms board**, `ILIM` 624 Ω (`IHCD` 1.2–1.9 A); on only while its slot holds a module that answers (§6) | a short or a foreign sink costs one latch, not the rail |
| Logic rail | **regulated 3.3 V always**: VBUS → 3.3 V LDO on the priority mux's IN1; VBAT → logic boost (TPS61099DRV, 576 kΩ / 249 kΩ) on IN2 | 5 V never reaches `VDD` |
| Enable defaults | LED boost `EN` pulled up to `VSYS`; logic LDO and logic boost `EN` tied on; only the expansion LDO is GPIO-gated | on USB with no cells nothing could enable a GPIO-gated LDO |
| Boost | TPS61023, single source accepted | no pin-compatible alternative exists |
| Pack ESD | **bidirectional** 9 V-standoff TVS per pack (SMF4L9.0CA), RC into supervisor `VDD` | doesn't crowbar a 14500 pair |
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
| Case | 3D printed resin/SLA, ~1.5 mm seam walls, heat-set inserts; **one piece per module from a large-plate print service** | resin is brittle; a 233 mm deep module does not fit a desktop SLA plate |
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

```
  [BAT] pack 1, 2xAA -[TVS 9V]-[rev FET]-[OVP FET <- TPS3840PL35]-[PTC]-[ideal diode, ~ON <- PACK_EN]--+
  [BAT] pack 2, 2xAA -[TVS 9V]-[rev FET]-[OVP FET <- TPS3840PL35]-[PTC]-[ideal diode, ~ON <- PACK_EN]--+-- VBAT (chain)
  [BAT] pack n ...                                                                                   |
        each pack node -[BAT54]-> PACK_SENSE (chain) -> [HUB] TPS3840PH18 -> slide switch -> PACK_EN   |
                                                                                                     |
  [USB] host USB VBUS -[KTS1693 OVP 5.55-5.95 V]-[TVS]--> [HUB] LM66200 IN1 --+                        |
  [Qi, later] AUX_5V (chain) ---------------------------> [HUB] LM66200 IN2 --+-- VBUS_IN              |
                                                                              |                      |
                            +------[LDO 3.3 V]--IN1 [priority mux] IN2 <--[logic boost 3.3 V]<-------+ VBAT
                            |                          |
                            |                 VSYS (3.3 V) -> MDBT50Q VDD, TCA9548A, expansion I/O
                            |
          VBUS_IN ----------+--> TPS2116 IN1 (priority)
          VBAT --[LED boost 5.0 V]--> TPS2116 IN2
                                          |
                                     LED RAIL (4.7-5.0 V) ---> [HUB] expansion LDO (gated) -> J_EXP 3V3
                                          |
                     +--------------------+--------------------+
               [COM-H] TPS22950L    [COM-H] TPS22950L    [COM-H] TPS22950L     (EN per slot)
                     |                    |                    |
               cable VBUS            cable VBUS            cable VBUS
                     |                    |                    |
               [COM-M] TVS           [COM-M] TVS           [COM-M] TVS
                     |                    |                    |
               [KEY] IS31FL3733 VCC + LED anodes; TPS7A0233P LDO -> module controller, driver VIO, pull-ups
```

The pack chain sits on each battery module, so a reversed cell, a 14500 pair or a
terminal ESD strike damages at most one small, mostly hand-solderable board. The
KTS1693 sits on the host port's USB port board, so a surge damages at most a small
board. A slot short or a foreign load latches its own slot switch on a small
comms board.

Rules:

- **5 V never reaches VSYS.** VBUS enters VSYS only through the 3.3 V LDO and the
  priority mux. **Rev 2 OR-ed VBUS straight onto VSYS, which feeds `VDD` (3.6 V
  max, 3.9 V abs-max): the first USB plug-in would have destroyed the MCU.**
- **The logic rail is regulated, 3.3 V always (rev 6).** On battery a dedicated
  boost (TPS61099DRV, ~1 µA quiescent, 0.7 V minimum input)
  takes VBAT to 3.3 V on the priority mux's IN2; on USB the LDO on IN1 wins. The
  hub's `VDD`, its I2C levels toward the slots and every `AINx` reading are
  therefore independent of which cells are fitted or how flat they are. (Rev 5
  ran `VSYS` unregulated at 1.85–3.3 V, which broke the inter-module UART levels
  of the rev 5–7 split; rev 6 regulated it.) With
  its input above its output (fresh alkaline, ~3.36 V) the TPS61099 stays in
  **down mode and keeps regulating**; it only passes the input through above
  `VOUT` + 0.5 V = 3.8 V, which the pack OVP (≤3.81 V) keeps out of reach. Logic
  current through the boost is a few mA at ~85 %; the idle cost is the boost's
  own quiescent current, on the order of 1 µA.
  **Part choice (rev 7).** The fixed 3.3 V TPS610994 is sold only as a 6-ball
  0.4 mm WCSP, which would put a non-reworkable part on the hub core. The adjustable
  TPS61099DRV (WSON-6, 2 × 2 mm) takes a feedback divider instead: `VREF`
  0.98–1.02 V, FB leakage ≤50 nA (SLVSD88M §6.5). **Divider 576 kΩ / 249 kΩ 1 %
  (Phase 3, 2026-09-15)**: 4 µA, leakage error ≤29 mV, PWM 3.20–3.46 V worst case,
  and PFM (+3 % typical, no maximum published) ~3.56 V, under the nRF52840's
  3.6 V recommended `VDD` maximum (product spec v1.9 Table 100). **Rev 7's
  ~2.3 MΩ / 1 MΩ 0.1 % claimed a leakage error under ~2 %; at the 50 nA maximum it
  is +116 mV (3.5 %)**, which puts PWM at 3.51 V and PFM at ~3.61 V.
  **Second source: dual footprint (2026-09-14).** The hub core carries a second 2 × 2 mm
  land pattern for the **ADI MAX17222ELT+** (µDFN-6, different pinout), with its
  own RSEL resistor (80.6 kΩ 1 % → 3.3 V) and inductor pads; one of the two is
  fitted. The MAX17222 draws 300 nA into OUT, starts at 0.88 V and regulates
  buck-like while `VIN` < `VOUT` + ~0.7 V, so the 3.81 V OVP ceiling stays
  regulated. **Load check (Phase 3, 2026-09-15):** at `IPEAK` 0.40 A minimum and
  `tON` 330 ns maximum, the datasheet's own method (p. 14) gives ~124 mA out at
  1.85 V in with 2.2 µH (~147 mA with 3.3 µH), against a `VSYS` peak of ~26 mA
  (nRF52840 TX +8 dBm 16.4 mA, CPU 3.3 mA, SAADC 1.24 mA, pull-ups, held keys),
  about 4.8× margin. Its ultra-low-power mode biases the output +1 to +4 % (3.43 V
  maximum), still under 3.6 V; its "high output-voltage ripple" while `VIN` is
  within ~0.7 V above `VOUT` is not quantified and is scoped on the bench.
- **Priority mux isolates the packs on USB.** With VBUS present the packs supply
  nothing, even a fresh alkaline pack near 3.3 V that would win an ideal-diode OR.
  **`VSYS` mux `PR1` (rev 7 core capture, 2026-09-15): its own 301 kΩ / 100 kΩ 1 %
  divider from `VBUS_IN`**, no hysteresis resistor, `MODE` tied to IN1. It hands
  over to the boost at 3.63–4.40 V, while the LDO on IN1 still regulates. A divider
  from the LDO output would only fall to IN2 once `VSYS` had sagged to ~2.75 V
  (`VREF` 0.92 V); sharing the LED mux's node would couple an LED-mux thermal
  shutdown (`ST` low) into the `VSYS` threshold.
- **Enable pins default on in hardware.** LED boost `EN` has a pull-up to `VSYS`;
  the logic LDO and logic boost are enabled by wiring; only the expansion LDO is
  GPIO-gated. A GPIO may pull an enable low, never be required to pull one high.
  On USB with no cells the MCU has no supply until the LDO runs, so a GPIO-gated
  logic LDO could never start; on battery a GPIO-gated LED boost would leave
  `VCC` at 0 V while `VIO`, SDA and SCL sit at `VSYS`, the same abs-max violation
  the hot-unplug rule below guards against, at every boot.
- **The LED rail takes VBUS directly on USB.** A TPS2116 in priority mode selects
  VBUS_IN on IN1 whenever it is above its `PR1` threshold, even when the boost on
  IN2 is higher. **Rev 3 used an LM66200 auto-OR and claimed VBUS always wins over
  4.7 V; it does not.** USB allows 4.75 V at the receptacle, and cable, OVP FET and
  switch drops take VBUS_IN below 4.7 V under load, at which point an auto-OR hands
  LED current to the boost. **The boost is fed from `VBAT`, so on USB that load
  lands on the cells** (rev 7 and earlier said "the 3.3 V LDO", which the topology
  does not do; with no cells IN2 sits under 1.6 V, a case the TPS2116 truth table,
  SLVSFG1A §7.3.1, does not define). The
  boost stays enabled and idles on IN2, so hand-over in either direction lands on a
  running source. The LDO carries logic current only.
  **`PR1` threshold (E3, 2026-09-15): 301 kΩ / 100 kΩ 1 % from `VBUS_IN`, plus
  1 MΩ from `PR1` to `ST`.** `VREF` is 0.92–1.08 V (SLVSFG1A §6.5), so rev 7's
  ~4.3 V nominal spread to 3.90–4.72 V and could hand a compliant but weak port's
  LED load to the cells; 301k/100k falls to IN2 below 3.63–4.40 V. The datasheet
  gives `PR1` no hysteresis; `ST` is open-drain and low while IN1 is not in use
  (Table 5-1), so the 1 MΩ loads `PR1` only then and VBUS_IN must recover ~0.3 V
  (4.31 V nominal) before the rail returns to IN1. No GPIO. Below ~4.5 V the LEDs
  dim rather than draining cells (E6). Confirmed on the bench (E3).
- **Bulk capacitance carries the mux switchover (rev 7).** The TPS2116's
  break-before-make switchover is **8 µs typical at 5 V** (6.2 µs at 3.3 V; RL
  10 Ω, CL 10 µF; no maximum given). Its 1.3–1.7 ms figure is the power-up soft
  start, which the part skips on a switchover while `VOUT` > 1 V. At 250 mA and
  0.7 V of allowed droop, 8 µs needs ~3 µF; the LED rail gets **~10 µF** to cover
  the missing maximum, well inside USB's inrush allowance. `VSYS` needs far less
  at ~10 mA and gets the same part count for margin. **Rev 5 read 1.3 ms as the
  switchover and needed ~460 µF; rev 6 added an `SDB` blanking ISR on VBUS
  events to avoid that. Both are gone.** Two datasheet conditions still apply: the
  new channel only turns on once `VOUT` has fallen to the new input + ~40 mV
  (both hand-overs here land on a higher or equal input), and if the powering
  input collapses faster than 1 V / 10 µs the other input must be ≥2.5 V (the
  4.7 V boost and the 3.3 V logic boost both are).
- **`VIO` of the LED driver ties to the key board's 3.3 V** (rev 8; was `VSYS` on
  the core side of a cable). No I2C level translator: pin 39 is an input-logic
  reference and the datasheet's own app circuit does exactly this.
- **The driver's VCC rails are never power-gated in normal operation.** Abs-max is
  "voltage at any input pin, VCC + 0.3 V", so collapsing VCC while `VIO`/SDA/SCL sit
  at 3.3 V is a violation on every transition. Idle is `SDB` low plus software
  shutdown, which is µA-class. Boost quiescent is then always paid, tens of µA.
- **Undervoltage, two stages.** Firmware reads VBAT on the SAADC and at ~2.05 V
  drives `SDB` low, drops BLE cleanly, and enters system-off. As a backstop, a
  TPS3840PH18 on the hub drives `PACK_EN` high at **~1.9 V at the pack**, which
  disables every battery module's ideal diode (active-low `~ON`), so the ideal
  diodes are also the cutoff switch (rev 8; rev 7 had one dual LM66200 on the
  core). The supervisor is powered from `PACK_SENSE`, a BAT54 from each pack node,
  so it survives its own cutoff; the ~0.1 V diode drop is why the 1.8 V part gives
  a ~1.9 V pack threshold (about 1.87–1.93 V over temperature). On battery that is
  all of the hub's `VSYS` and every key board's supply, so MCU, module controllers
  and boost inputs die together; on each key board `VIO` is an LDO output from
  `VCC`'s own net, so `VCC` never falls below `VIO`. On USB the packs are already
  isolated and nothing changes. **Rev 2 put UVLO on boost EN alone, which collapsed
  driver VCC under a live `VIO` and left the MCU draining the cells.**
- **Reverse-polarity protection is mandatory.** A plain high-side ideal diode's
  body diode conducts with a reversed pack and drags VSYS to about −2.4 V into
  pins rated −0.3 V. Series reverse-blocking P-FET (AO3415A, <75 mΩ at −1.8 V)
  before the OR-ing.
- **Overvoltage protection per pack.** 14500 Li-ion cells fit AA holders; a pair in
  a 2S holder is 8.4 V. No integrated OVP switch found goes below 4 V, so each pack
  gets a TPS3840PL35 (10 V recommended maximum, 12 V abs-max, 300 nA) driving a
  second series AO3415A gate.
  The TPS3840's rated threshold is its *falling* edge, with +200 mV hysteresis, so
  the PL35 trips **rising at ~3.65–3.75 V** and releases falling at ~3.45–3.55 V:
  inside the 3.59–3.81 V window, under `VDD`'s 3.9 V abs-max, above the freshest
  alkaline pack at ~3.36 V. A fresh L91 pack (~3.66 V) may or may not trip; they
  are unsupported either way. DNP bypass footprint for the Li-ion build of §15.
  **The OVP FET is off by default and slow to turn on (rev 6).** A supervisor
  *detects* over-voltage; its below-threshold state, including during its own
  start-up, is "reset asserted", which for the PL35 is output low, which is
  "FET on". Inserting a 14500 pair therefore passed 8.4 V through the
  reverse-block FET, the OVP FET, the PTC and the LM66200 (6.0 V abs-max) onto
  `VBAT` and, via the mux path, toward the MCU, for the supervisor's start-up plus
  its 1 kΩ / 100 nF filter (τ = 100 µs) plus its release delay `tD`, hundreds of
  µs at least. Now the OVP FET's gate is pulled up to its source (pack side), the
  supervisor pulls it down through a series resistor into a gate RC, and a diode
  from the supervisor output to the gate makes turn-off immediate.
  **Sizing (rev 7, datasheet-checked).** The window to cover is insertion to
  supervisor release: the 1 kΩ / 100 nF filter reaches `VIT+` (≤3.81 V) in
  ≤~110 µs for any pack ≥6 V, then `tSTRT` is 350 µs max with CT open (it
  includes the no-cap `tD`), so **~460 µs**. The AO3415A's `VGS(th)` is −0.3 V
  min, and the gate must stay above that for the whole window. With ~10 MΩ
  pull-up and ~470 kΩ series (divider ≈0.95), a τ of 10 ms reaches −0.3 V at
  8.4 V in ~380 µs, short of the window; **τ ≥ 25 ms** (e.g. 56 nF) reaches it in
  ~960 µs, about 2× margin. AA cells then pass `VGS(th)` max after ~17 ms at a
  1.9 V pack, and the 0.95 divider gives −1.8 V of gate drive there, which the
  RDS(on) budget assumes. Layout rules: **the capacitor goes gate-to-source**
  (gate-to-GND starts the gate at 0 V on insertion, which is "FET on"), and it
  stays ≥10 nF so the FET's `Crss` cannot pull the gate below −0.1 V on an 8.4 V
  step. The 10 MΩ node needs clean, residue-free assembly. PL35 output
  behaviour below `VPOR` is only defined for `VDD` slew ≤100 mV/µs; the filter
  gives ≤~93 mV/µs at 8.4 V with a −10 % capacitor, and the gate RC rides over
  anything shorter anyway. **The OVP supervisor senses after the reverse-block
  FET**, so a reversed pack (−3 V) never reaches its `VDD` (abs-max −0.3 V).
  **Hot swap (Phase 3 ngspice, 2026-09-15; E14 closed).** The gate RC protects only
  a *discharged* board. With a pack running, C801 holds VGS ≈ −2.6 V, and nothing
  discharges the pack node quickly after the cells come out: 1 µF of LM66200 `CIN`
  against ~1 µA of supervisor, gate-divider and UVLO current (the LM66200 leaks only
  nA back out of an input, Fig. 6-8). Inserting a 14500 pair within **2.3–3.8 s**
  put **8.3 V on `VBAT`**; swapping one AA for one 14500 (5.6 V) put **5.5 V** there,
  which the logic boost passes through to `VDD`. Cold insertion stays blocked
  (6 mV). **Fix: a 330 kΩ bleeder from `CELL+` to GND on the battery board (R806)**,
  8.5 µA per pack at 2.8 V: the window falls to **0.46–0.50 s** and the one-cell swap
  after 1 s stays at 2.6 V. **The window scales with the pack node's capacitance:
  with 10 µF it is 3.4–3.7 s even with the bleeder, so each battery module keeps
  its ideal diode's input at 1 µF and bulk capacitance sits on `VBAT` at the
  hub** (rev 7: on the core's LM66200 pack inputs). E14's original worry,
  D804's forward drop leaving the FET partly on after a trip, did not appear: the
  BAT54 keeps discharging C801 down to sub-µA currents, so VGS reaches ≈0 within
  milliseconds rather than following R803 × C801. The models (AO3415A subthreshold
  slope n = 1.5 and −2.5 mV/K threshold tempco) are assumptions, not datasheet
  numbers; deck in `tools/sim/e14_pack_swap.py`.
- **FET gate clamps.** AO3415A is rated ±8 V VGS and a 14500 pair is 8.4 V, so every
  series P-FET gets a gate resistor and a ~6.2 V zener clamp.
- **Pack-terminal ESD.** A **bidirectional** 9 V-standoff TVS at each pack
  (Littelfuse SMF4L9.0CA: VBR 10.0–11.1 V, IR ≤5 µA at 9 V, VC 15.4 V at 26.4 A,
  400 W at 10/1000 µs, SOD-123FL), which does not
  conduct at 8.4 V; its 15.4 V clamp exceeds the TPS3840's 12 V abs-max, so
  supervisor `VDD` takes 1 kΩ series + 100 nF, which also keeps it inside the 10 V
  recommended range. The AO3415A's 20 V VDS covers the clamp. **It must be
  bidirectional**: the TVS sits across the pack terminals, ahead of the
  reverse-blocking FET and the PTC, so a unidirectional part forward-conducts into a
  reversed pack with nothing to limit the current.
- **Host USB input OVP.** The host USB-C socket's VBUS goes through a **Kinetic
  KTS1693** integrated OVP switch on the USB port board, unchanged from rev 7.
  Everything behind it is **6.0 V abs-max** (TPS2116, LM66200, TPS22950, TLV757P,
  all datasheet-verified). The numbers that shape the circuit:
  - **Ratings.** IN 30 V abs-max, internal clamp 32 V, IEC 61000-4-5 ±110 V surge
    and IEC 61000-4-2 ±8 kV contact on IN, 9 mΩ typ / 13 mΩ max, 8 A continuous.
    Turn-off **100 ns** after VIN crosses OVLO. Turn-on only after a **0.7 ms
    debounce**, then a ~2 ms soft start.
  - **Trip point: external divider.** The internal OVLO (5.77–6.13 V) can exceed
    6.0 V. With **R1 = 100 kΩ, R2 = 26.4 kΩ (0.1 %)** against the 1.162–1.238 V
    reference and ±100 nA leakage, the trip is **5.55–5.95 V**, above vSafe5V's
    5.5 V.
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
- **PTC in each pack lead, hold ≥1 A.** 2×NiMH will deliver amps into a short and
  there is a boost inductor downstream. **Eaton PTSLR12066V175**: 1.75 A hold,
  3.5 A trip, 0.4 s max at 8 A, 50 A Imax, **Ri min 5 mΩ, R1 max 45 mΩ**, 1206.
  Hold derates to ~88 % at 40 °C, ~1.5 A against the ~0.8 A worst case (rev 8, 5.0 V LED rail; 730 mA at rev 7's 4.7 V). Chosen over
  PTSLR12066V150 (R1 max 80 mΩ, 3.0 A trip), which puts the path over budget once
  the LM66200's maximum rather than typical on-resistance is used (below). The
  whole family is rated 6 V.
  That is enough: the PTC sits after the OVP FET, so a 14500 pair never appears
  across it, and an alkaline or NiMH pack is ≤3.4 V. Rev 3's "Vmax ≥9 V" is
  withdrawn.
  **Fault band accepted (E9, 2026-09-15).** The PTC may never trip between 2.5 A
  and its 3.5 A `Itrip` (~3.1 A at 40 °C), and Eaton publishes no trip curve, only
  0.4 s at 8 A. A partial short on `VBAT`, or an LED-rail overload that holds the
  TPS61023 output above 1.8 V (3.7 A typical valley limit; below 1.8 V its
  short-circuit protection folds back to ~350 mA, SLVSF14B §7.3.7), can hold an
  LM66200 channel above its 2.5 A abs-max until the pack node sags below the
  ~1.9 V UVLO (roughly 4–6 A with fresh NiMH) or the LM66200 reaches thermal
  shutdown (~1.5 W at 5 A × 61 mΩ, RθJA 111.5 °C/W). Hard shorts pull the node
  under the UVLO at once. The part at risk is the battery module's ideal diode,
  and only under an internal fault; PTSLR12066V110/V150 would close or narrow the band at 381/331 mΩ of path
  resistance and were not adopted. §16 runs a partial-short test.
- **Packs are never directly paralleled.** Each battery module has its own
  reverse-blocking FET, OVP, PTC and ideal diode into `VBAT`. **OR-ing does not share
  load:** the higher pack carries all of it until the packs equalise, then they
  alternate. The keyboard runs correctly on one pack alone, and every per-pack
  part is sized for the whole keyboard's battery load (rev 8; was one module's). **Rev 2 claimed two packs halve the
  C-rate; they do not.**
- **Series resistance budget ≤300 mΩ max per pack path**: rev FET ≤75 + OVP FET
  ≤75 + PTC ≤45 (R1 max) + LM66200 ≤51 (max at 1.8 V, 25 °C; 61 mΩ at 85 °C) +
  holder <50 mΩ (MPD BC2AAPC datasheet; ~30 mΩ was assumed before the holder was
  chosen, P15) = **~296 mΩ**, about 170 mΩ typical. Rev 4 counted the LM66200 at its
  40 mΩ typical; at its maximum the 80 mΩ PTSLR12066V150 would have made it 311 mΩ.
  At the worst-case ~0.8 A the path drops ≤0.24 V, so full brightness ends slightly early on a
  nearly flat pack; firmware already scales lighting with VBAT.
  **Rev 8: the budget becomes ~296 mΩ + ~10 mΩ per hop (E20, decided
  2026-09-26).** Rev 7 did not count connector contacts. On the 2×6 chain header
  (4 `VBAT` + 4 GND contacts, an **assumed** ~20 mΩ per 2.54 mm contact, to be
  confirmed on the chosen part) each hop adds ~10 mΩ round trip, so the pack in
  the n-th module sees ~296 + 10·n mΩ: ~316 mΩ for the far pack in rev A, ~396 mΩ
  at 10 modules. Accepted: at the ~0.8 A worst case that is ≤~80 mV more drop on the
  farthest pack, and the bus resistance makes nearer packs carry more of the load,
  so far packs simply drain later.
- **Battery chain (rev 8).** Battery modules connect to the hub's `J_CHAIN` and to
  each other through a chain bus that every module passes through:

  | Chain net | Contacts | Carries |
  | --- | --- | --- |
  | `VBAT` | 4 | every pack's ideal-diode output, OR-ed; the whole battery load passes through the modules nearer the hub |
  | GND | 4 | return |
  | `AUX_5V` | 2 | the Qi board's input to the hub; battery modules pass it through as plain copper (§15) |
  | `PACK_EN` | 1 | the hub's cutoff: the old `~ON` net, now distributed to every pack's ideal diode |
  | `PACK_SENSE` | 1 | diode-OR (one BAT54 per module) of every pack node, µA-level: the UVLO supervisor's supply and sense |

  **Header (decided 2026-09-26): 2×6, 2.54 mm pass-through stacking header**,
  pinout **1 `VBAT`, 2 GND, 3 `VBAT`, 4 GND, 5 `AUX_5V`, 6 `PACK_EN`, 7
  `PACK_SENSE`, 8 `AUX_5V`, 9 GND, 10 `VBAT`, 11 GND, 12 `VBAT`**. Turned 180°, pin
  k meets pin 13−k, so power meets its own net and only `PACK_EN` and
  `PACK_SENSE` swap, which leaves every pack off. **Part family (M10, decided
  2026-09-29): Samtec ESQ elevated socket with square stack-through tails, socket
  on each board's top face, tails down** into the socket of the layer below (§11).

  **Why `PACK_SENSE` exists.** The UVLO supervisor must survive its own cutoff.
  Rev 7 fed it from both packs ahead of the OR through a BAT54C. With the OR moved
  onto the battery modules, the hub no longer sees the pack nodes, and a
  supervisor on `VBAT` would lose its supply the moment it cut the packs off,
  release, and oscillate. **Per-pack ideal diode (decided 2026-09-26): an LM66200
  with one channel used**, `VIN1` = pack, `VIN2` tied to GND, `~ON` = `PACK_EN`,
  `ST` unused. It keeps the ≤51 mΩ the series budget assumes (41 typ / 51 max at
  1.8 V and 25 °C, 61 mΩ max from −40 to 85 °C, SLVSG04), blocks reverse current,
  draws 1.32 µA typ, and `ON` high turns the output off (Hi-Z). **Its two channels
  cannot be paralleled to halve RON**: only the higher input conducts (truth table
  §7.3.1). Rejected: the **LM66100** (210 mΩ max at 1.8 V, SLVSEZ8A, path ~455 mΩ);
  a discrete P-FET + comparator (hand-solderable, but 65–75 mΩ and a new circuit to
  simulate against hot swap); a Schottky (~0.3–0.4 V at 0.8 A, no enable). The ≤1 µF rule on the pack node
  (hot-swap window) applies on each battery module. **Chain contacts (M10, decided
  2026-09-26): a 2.54 mm pass-through stacking header**, pins on the top face and a
  socket on the bottom face of each module (or the reverse), modules stacked under
  the hub. Rules: **the pinout is reversal-safe** (a 2×N header turned 180° puts
  pin k on pin N·2+1−k: `VBAT` faces `VBAT`, GND faces GND, `AUX_5V` faces
  `AUX_5V`, `PACK_EN` faces `PACK_SENSE`), and the case keys the join as well;
  **a detached module switches itself off**: a pull-up from its `~ON` to its own
  pack node holds the LM66200 off unless the hub pulls `PACK_EN` low, so the
  exposed contacts of a loose module are dead. The swapped `PACK_EN`/`PACK_SENSE`
  of a reversed join therefore also leaves every module off. Rev A fits two
  modules. Side by side is a future option (it needs a right-angle part or a
  different join).
  **Any number of modules (2026-09-26).** Builders will stack as many as they like,
  so nothing may depend on the count. What holds at any N: the load is set by the
  firmware cap, so the current through the first hop never exceeds ~0.8 A; each
  ideal diode keeps packs from charging each other; the supervisor watches the
  highest pack, so a pack already below 1.9 V stays blocked and is never
  discharged further; a module added to a running stack joins the OR (a lower pack
  waits, a higher one takes over). What scales: resistance to the far packs
  (~10 mΩ per hop, above), each pack's own standby drain (~10 µA, mostly R806;
  per pack, so shelf life does not change), and the `~ON` pull-ups in parallel on
  `PACK_EN`: **~10 MΩ each**, so ten modules cost ~2.5 µA while the keyboard is on.
  The battery reading is the highest pack; the hub does not know how many modules
  are fitted. A tall stack needs a mechanical joint to the hub; the header is not
  one (M10).
  **More modules add runtime, not current**: OR-ing does not share load, so every
  per-pack part stays sized for the whole keyboard's battery load, and the 250 mA
  lighting cap holds however many modules are fitted.
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
- **LED headroom after the cable (E19, decided 2026-09-26): LED boost raised to
  ~5.0 V.** A max-bin die needs ~4.5 V at the driver (Vf max 4.1 V green + ~0.4 V
  driver). The slot switch (≤41 mΩ), two GH contacts, the comms boards and ~1 m of
  cable (VBUS and GND, ~0.4 Ω round trip on 28 AWG) drop ~0.1 V at `right`'s
  0.28 A, so rev 7's 4.7 V setpoint (4.63–4.87 V) left ~0.03 V worst case. **The
  TPS61023 divider goes from 698 kΩ / 100 kΩ to 750 kΩ / 100 kΩ**: `VREF` 580–610 mV
  (PWM) gives **4.93–5.19 V**, 5.06 V nominal, ≥0.33 V of headroom after the cable;
  under the TPS61023's output OVP (5.5 V min) and the IS31FL3733's 5.5 V maximum.
  Costs: ~7 % more cell power at the same brightness (the extra volts burn in the
  driver's current sources) and ~0.8 A from one pack at the battery cap (below).
  **Open check:** the TPS61023's PFM output offset at light load is not published;
  measure the rail at idle on the bench (§16). Rejected: requiring a heavier or
  shorter cable (not enforceable), Vf-binned LEDs only (narrows sourcing), and
  relying on lower peak current on battery (no verified Vf-vs-current curve).
- **`VBUS` must reach the MDBT50Q's `VBUS` pad directly**, not only through the
  power path, or USB and DFU are dead. It arrives from the USB port board on its
  own contacts of the hub core's `J_USB`.
- Set `DCDCEN`. The REG1 inductor and the 32 MHz crystal are inside the module.
- On the hub core: slide power switch, reset tactile, bootloader tactile, reachable
  through the hub enclosure (Alps SKRTLAE010 side-push tactiles, C&K PCM12SMTR
  side-actuated slide; land patterns not yet checked, P18). **The slide switch is an
  SPDT on `PACK_EN`**, as rev 7 had it on the pack LM66200's `~ON`: common on
  `PACK_EN`, one throw on the TPS3840PH18 output (on, UVLO in control), the other on
  `PACK_SENSE` (off: holds every pack's `~ON` high). Off costs nothing and USB still
  runs the keyboard, so DFU works with the switch off. A 10 MΩ from `PACK_EN` to GND
  holds "on" across the break-before-make gap.
- **Link hot-unplug (rev 8).** Pulling a link cable, or unplugging a comms board,
  powered can leave SDA, SCL or `INT` at 3.3 V while the key board's rails fall.
  **Series resistors where the link enters the key board** (470 Ω on SDA and SCL,
  1 kΩ on `INT`, E11 values carried over) limit the current into the module
  controller's and the driver's clamps while that lasts. The key-board-side I2C
  pull-ups go to the key board's own 3.3 V, so an unpowered key board presents no
  pull-up; the hub's TCA9548A channel for that slot is closed except during a
  transaction. **The hub-side `INT` pull-ups are fed from `SLOT_EN`**, so they are
  off whenever the slot's power is off (§6). The §16 unplug test is the proof.

**Pack current.** Worst case is the whole keyboard at the battery cap near UVLO:
250 mA × 5.06 V / (1.9 V × 0.85) ≈ **~0.78 A from one pack** (≤0.8 A at the
5.19 V setpoint maximum), inside the PTC's ~1.5 A hold at 40 °C. Rev 7 had 730 mA
at a 4.7 V rail, for one module's cap.

Budget, whole keyboard, 4000 mAh NiMH (two 2000 mAh battery modules). `IOUT` ≈
19.8 mA peak at `RSET = 42.2 kΩ`, `GCC = 255`; `ILED = IOUT/12.75 ≈ 1.55 mA` average
per die at `PWM = 255`; 109 keys × 3 dice = **507 mA at the rail**, over the
250 mA battery cap, so battery lighting tops out near 49 %. Cell current = rail
current × 5.06 V / (2.4 V × 0.85) ≈ 2.5 × rail. Radio, hub MCU and module
controllers excluded.

| Condition | At rail | From cells | Runtime |
| --- | --- | --- | --- |
| Idle, no lighting | — | **unproven, see §16** | target ≥6 months |
| 10 keys dim (24 %) | 11 mA | 27 mA | ~146 h |
| All 109 at 3 % | 15 mA | 37 mA | ~108 h |
| All 109 at 24 % | 122 mA | 302 mA | ~13 h |
| All 109 at the 250 mA cap (~49 %) | 250 mA | 620 mA | ~6.5 h |

Rev 7 had each module on its own two packs, so the keyboard carried three times
the cells; the rev 8 rows are for the whole keyboard on two battery modules.
Adding modules scales runtime linearly and leaves the cap unchanged. A 6-month idle
target on NiMH requires low-self-discharge cells.

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
  42 of 47 GPIOs plus nRESET. The CC and VBAT sense pads are rev 7's.
- The NFC pads carry two outputs (`EXP_RST`, `EXP_LDO_EN`), which needs
  `CONFIG_NFCT_PINS_AS_GPIOS=y` (UICR). Leakage between the NFC pads at different
  levels is **not verified** (the nRF52840 product specification cannot be
  downloaded here); both nets have ≤100 kΩ loads.
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
| A4 A9 B4 B9 (VBUS) | slot switch output (TPS22950L), SMF6.0A | `VIN`, SMF6.0A |
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
| `J_CHAIN` | 12, 2.54 mm 2×6 stacking header, Samtec **ESQ-106-24-G-D** socket up / tails down (M10, 2026-09-29), gap 17.5 mm | hub base board ↔ connector layer (passed through) ↔ battery module ↔ battery module …, or ↔ Qi2 board in place of battery module 1 | **1 `VBAT`, 2 GND, 3 `VBAT`, 4 GND, 5 `AUX_5V`, 6 `PACK_EN`, 7 `PACK_SENSE`, 8 `AUX_5V`, 9 GND, 10 `VBAT`, 11 GND, 12 `VBAT`** (reversal-safe, §4) |
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
- **Layer ID:** every layer carries a 2 Kbit I2C EEPROM (24xx02 class, part open)
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
2×16, expansion 2×10) uses a **Samtec ESQ** elevated socket with square stack-through
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
- **The bottom module's tails are live** (`VBAT` from every enabled pack): its case
  must shroud them, tips recessed inside the case's bottom outline (M11): the
  tails stand 8.05 mm below the board, so the shroud is ≥~9 mm deep. A
  detached module is still dead (§4).
- The core carries ESQ tails down into the connector layer (chain, slot) and the
  expansion socket on its top face; optional layers stack the same way.
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
| Lighting scale-down start | 2.30 V | `VBAT` SAADC, during a lighting frame (loaded) |
| Lighting off | 2.15 V | same |
| System-off | 2.05 V | `VBAT` SAADC with lighting off (unloaded), averaged over 8 reads |
| Hardware UVLO (backstop) | ~1.9 V at the pack | TPS3840PH18 on `PACK_SENSE` (BAT54 per pack); +100 mV hysteresis is smaller than the ~230 mV IR drop at ~0.78 A, which is why lighting is off well before this point |
| Slot probe (E18) | ~200 ms answer window after power-on; ~100 ms re-probe every ~2 s while awake; none while asleep | time from `SLOT_EN` high to the first register-map answer; tune both on hardware |

**Deep sleep.** The hub sleeps with ZMK's stock sleep; the key boards stay powered
with their module controllers in a low-power scan-wait state, and a keypress
raises `INT`, which is wake-capable on the hub (System OFF wakes on any GPIO's
DETECT). Idle current of the hub, the three key boards' LDOs and module
controllers, and the LED boost is unproven (E7).

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
- **Seam wall budget**: three cases need two walls at each of two seams. Resin/SLA
  holds ~1.5 mm, so about **6 mm** of dead space appears mid-field.
- **Comms boards**: each key module's faces its rear wall, screwed to the wall, one
  cable, reachable without removing another board. On the hub, the wired
  connector layer's three socket boards face that layer's wall the same way.
- **The hub is a tower of layers (M11, decided 2026-09-26)**: optional layers
  (display…) on top, the core layer, the connector layer, then battery modules or
  a Qi2 board. Each layer is its own enclosure section; the stacking headers carry
  the signals but are not a mechanical joint, so layers latch or screw to each
  other. **Footprint ~90 × 90 mm outside** (2026-09-29): 2 mm resin walls, boards
  ~84 × 84 mm. **The core layer is one ESQ joint tall**: the MCU sits on the base
  board (2026-09-29), so nothing in the core is taller than the joint gap.
  **Every joint's gap is 17.5 mm (ESQ `-24`), so every layer is 19.1 mm board
  pitch**; a two-pack tower is ~88 mm tall (9.5 mm tail skirt, four boards, four
  17.5 mm gaps, a 2 mm lid roof; 87.9 mm in the v0 model). **The hub antenna is an adhesive flex antenna on the inside of a
  core-section wall**, fed from the module's u.FL, placed clear of the base board's
  copper, the layer above and the cells (distances from the antenna's datasheet,
  checked by the RSSI test); the same wall carries a **blanked RP-SMA knock-out**
  for an external antenna on a u.FL-to-RP-SMA pigtail. **Walls (2026-09-29)**, front = the wall facing the keyboard, sides as seen from
  the keyboard: **front**: the connector layer's three slot USB-C sockets, and the
  slide switch, reset and bootloader buttons on the core's front wall above them;
  **rear**, right to left: host USB-C (USB port board), the expansion board's SH
  socket, then the flex antenna and the blanked RP-SMA knock-out in the remaining
  ~40 mm at the left end (all cables leave the back; the antenna sits ~20–40 mm from
  the SH cable and the USB shell, RSSI risk accepted, checked in §16; **the flex
  antenna must be ≤~40 mm long**); **left** and **right**: nothing.
  **Joints (2026-09-29)**: the core and the connector layer are joined by **M2
  screws** into heat-set inserts (the 44-contact joint cannot be pulled apart by
  accident; swapping the connector layer takes the one driver); **battery modules
  and the lid join magnetically**: each section's bottom edge nests in a lip on the
  section below (takes sideways cable pulls), an asymmetric key in the lip stops a
  90°/180° misfit, and disc magnets in the walls hold it, kept away from the
  antenna corner. Cell access is tool-less: lift everything above a module off
  (the cells sit 2.5 mm under the next board). Magnet part and holding force vs the
  ESQ withdrawal force are open. **Optional layers join the core's top (and each
  other) the same magnetic way**; the lid sits on the topmost section. **A future radio connector layer puts
  its radio on the wall facing the keyboard**, and on the opposite side from the
  core's antenna wall, so the two 2.4 GHz radios sit apart (coexistence is a future
  test).
- **Battery modules (M10, decided 2026-09-26)**: each a closed 2×AA case with its
  battery board, tool-less cell access, and a pass-through stacking header (Samtec
  ESQ, socket up, tails down, 2026-09-29, §6) so modules **stack under the hub**; the
  bottom module's case shrouds its live tails; the case
  keys the join and the pinout is reversal-safe (§4). A future Qi board plugs into
  the hub instead of the stack, so the pad sits under the hub. Side by side is a future
  option.
- **Cable routing**: every internal cable has a routed channel and a clip point,
  clear of the switch pins, the hotswap sockets and the reverse-mount LED holes.
  Service loops are just long enough to lift a board out. Each key module has only
  two internal cables now (`J_COMM`, and `J_DIAL` on `right`).
- **Fastening**: heat-set brass inserts, not self-tapping screws. Every board uses
  M2 screws, so one driver services the whole keyboard.
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
- **Printing (rev 7, M9 closed)**: desktop SLA plates run ~200–220 mm on the long
  axis (Form 4 200 × 125 mm, Saturn-class ~220 × 125 mm); `left` and `right` at
  233 mm deep do not fit in one piece. **The case is printed in one piece per
  module by a large-plate service.** No joints, so wall thickness, insert
  positions and the seam budget (M1) are unaffected. Cost: a slower, dearer
  iteration loop than a desktop printer, and builders need the same service; the
  build guide names the minimum build volume.

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
  its outline is set by the hub enclosure (M11: ~84 × 84 mm, 2026-09-29, with the
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
  battery board's PTC (PTSLR12066V175): reflow or hot air only**, per Eaton, MSL
  2a; and the per-pack LM66200 (DRL SOT, 0.5 mm pitch), placed in the same reflow or
  hot-air step as the PTC. **MSL 3 LEDs**: bake note if reels have been opened.
- Check `IS31FL3733` vs `-B` lifecycle and stock parity before committing.

## 13. Analogue and RF notes

- **SAADC**: internal 0.6 V bandgap reference, **not** `VDD/4`. Sense **`VBAT` on the
  chain bus**, ahead of the mux, so the pack level is known on USB too; it reads the
  highest pack. Divider (carried over from rev 7): **49.9 kΩ / 49.9 kΩ 1 %, switched
  on the high side** by an AO3415A whose gate a 2N7002 pulls down from `BAT_DIV_EN`
  (1 MΩ gate pull-up to `VBAT`; 1 MΩ `BAT_DIV_EN` pull-down), so it draws nothing
  off and `AIN0` never sits above `VDD` + 0.3 V. Reading, `AIN0` is ≤1.9 V and the
  divider draws ~38 µA. Host CC sense reads 0.25–2.04 V through a 100 kΩ series
  resistor into an `AINx` pad.
- **Antenna** (2026-09-29): the hub holds the only radio, on the desk, away from
  the palms and the key field. The **MDBT50Q-U1MV2** has no antenna of its own; its
  u.FL feeds an **adhesive flex antenna on the inside of a core-section wall**, so
  the antenna's position is chosen in the enclosure, not dictated by the module's
  board edge. **A blanked RP-SMA knock-out** in the same wall takes an external
  antenna on a u.FL-to-RP-SMA pigtail if the RSSI test (§16) is poor. The u.FL is
  mated at assembly, not by the user. **Open**: the antenna part and its clearance
  to metal and ground (from its datasheet); SLA resin loading the antenna
  (datasheets tune for a stated plastic and thickness); which antenna type and gain
  Raytac's MDBT50Q-U approval covers (the SGS RED report E2/2018/50088-02 lists the
  -U model, the datasheet does not name its antenna). The rev 8 vertical MCU board
  (2026-09-26) is dropped: the u.FL module needs no free board edge.
- **ESD**: entry points are the host USB-C port (USB port board), every link socket
  at both ends (comms boards, TPD6E05U06 on the six CC/D± pins, SMF6.0A on VBUS),
  the expansion connector (expansion board), the key matrix (finger → keycap →
  switch → module-controller pin, clamped on the key board), the AA terminals
  (battery module), the dial shaft (dial board, lugs to GND, DNP TPD4E1U06DBV), and
  the chain contacts (M10: clamp on each battery module). Internal cables are not
  entry points and get no clamps.
- **EMC**: informational only, since this ships as open source and builders carry
  their own compliance. Modular approval covers the intentional radiator only; the
  product remains an unintentional radiator under FCC Part 15B / EN 55032, and the
  module's FCC and IC identifiers would go on the label of anything sold.
- **Test points** beyond SWD: on the hub core, `VBAT`, `PACK_SENSE`, `PACK_EN`,
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

## 15. Future modules: Qi2, comms, Li-ion

**Qi2 (optional, later).** A Qi board takes power from a Qi2 charging pad and
feeds `AUX_5V` into the hub, where it is `VBUS_IN`'s second OR input. **It is used
instead of the battery stack** (decided 2026-09-26): it plugs straight into the
hub's chain header, so the pad sits under the hub and nothing else is in the path.
Battery modules still pass `AUX_5V` through, which keeps a Qi board under a battery
stack possible later at no cost; it is not a supported setup in rev 8. A Qi-only
hub has no battery: off the pad and off USB it stops. Behaviour is either/or: with `AUX_5V` present the
priority muxes run the keyboard from it as from USB, the packs sit isolated, and
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

**Li-ion.** Rev 7 reserved a Li-ion path on the core (`VDDH` on its own solder
jumper, DNP REG0 inductor). With the cells now off the hub core and chained, a
Li-ion build would be a different battery module with its own charger and
protection delivering 2S-AA-like voltage on `VBAT`, or feeding `AUX_5V`; the hub
keeps the `VDDH` jumper and DNP REG0 footprints in case it is needed.

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
- [ ] **Insert two 14500 cells in one pack. Nothing is damaged; OVP holds `VBAT`
      off.** Scope the OVP FET drain at 1 µs/div through the first 20 ms: `VBAT` never
      rises above 6.0 V at any instant. Repeat 10 times with contact bounce
- [ ] **Hot swap:** keyboard running on the other pack, pull a fresh AA pair and
      insert a 14500 pair as fast as possible, then swap one AA for one 14500:
      `VBAT` and `VSYS` never exceed 6.0 V / 3.6 V. Repeat with R806 lifted, then
      refit it
- [ ] **Chain:** one, two, three and ten battery modules, stacked (ten with a mix of fresh and flat packs: no reverse current into any pack, far packs drain last); one module joined turned 180° (if the case allows it) leaves every pack off; a detached module's contacts read 0 V:
      every combination runs; no current flows between packs when one is fresh and
      one depleted; the slide switch turns every pack off; UVLO cuts all packs at
      ~1.9 V and does not oscillate (scope `PACK_EN` and `PACK_SENSE`)
- [ ] **Runs correctly on one battery module alone**
- [ ] **USB only, no cells fitted**: boots, `VSYS` = 3.3 V, every slot powers its
      module
- [ ] Battery power-on: each key board's 3.3 V never exceeds its `VIN` (scope both
      at the driver); no GPIO required for the boost or logic regulators to start
- [ ] OVP on a bench supply: never trips below 3.59 V, always trips by 3.81 V
      rising; releases above 3.36 V falling
- [ ] 20 V on the host USB-C socket's VBUS, steady and **hot-plugged from a charged
      source**: `VBUS_IN` never exceeds 6.0 V at any instant; then a 5 V source
      stepped to 20 V while connected: same limit
- [ ] 1 kV contact ESD (then the chosen IEC level) on AA terminals and chain
      contacts: supervisor `VDD` stays under 10 V
- [ ] Contact ESD on every link socket at both ends, on the dial shaft and knob, and
      on the expansion socket: no reset, no stuck key, the link recovers
- [ ] Freshest alkaline pack available never trips OVP
- [ ] **Plug USB with fresh alkaline packs fitted: `VSYS` ≤3.3 V, zero pack current**
- [ ] Firmware system-off at ~2.05 V; `PACK_EN` disables every pack at
      ~1.87–1.93 V at the pack, across 0–40 °C
- [ ] USB hand-over: plug and unplug under full lighting; LED rail never dips below
      `VSYS`, ~10 µF bulk and no blanking; `VSYS` never resets the MCU; every key
      board's module controller stays up
- [ ] USB source at 4.5 V with full lighting: LED rail stays on `VBUS_IN`; ramp down
      and up: hands over between 3.63 and 4.40 V with ~0.3 V hysteresis (E3)
- [ ] Host CC sense reads default / 1.5 A / 3 A correctly on three chargers; LED
      budget follows
- [ ] Driver case temperature at full white on a 5.0 V rail, 30 min
- [ ] LED boost idle (PFM) output ≤5.3 V, and under full load 4.93–5.19 V (E19)
- [ ] **LED headroom (E19):** max-bin green and blue at full current at `right`'s
      far end on a 1 m cable, on battery and on a 4.75 V USB source
- [ ] **Measured idle current, µA trace**, hub asleep, three modules in scan-wait.
      The §4 idle row is unproven until this exists
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
- [ ] Partial short on `VBAT` (~1 Ω, fresh NiMH, two modules): record the pack
      LM66200 case temperature, UVLO or thermal cycling, whether the PTC trips (the
      2.5–3.5 A band is an accepted risk, E9)
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
- [ ] Hub BLE RSSI against a dev kit in the open, **once with the internal flex
      antenna and once with an external antenna on the RP-SMA knock-out**, with the
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
| Three modules, each with a core board (MDBT50Q, full power path), 2 battery boards, a USB port board, link boards and seam boards | **One hub** with the only MCU module, the only power path and the host port; **three key modules with no radio, cells or power path** |
| ZMK split: `left` central, `right` and `numpad` peripherals; wired UART transport with BLE failover, all-or-nothing, pair-2 passthrough on `right`, orientation detection, handshake, hysteresis | **One ZMK keyboard**; key modules are I2C targets behind a TCA9548A; no split transport |
| Key matrix, dial and LED driver wired to the core over `J_ROW`/`J_COL`/`J_LED` | **Module controller** MCU on each key board: scans, decodes the dial, drives the LED driver, serves one register map; **TCA8418 rejected** (25–40 ms per press, SCPS215G p. 33), **hub-scanned TCA6424A rejected** (polling cannot cross a radio link) |
| Link boards (upstream with KTS1693, downstream with TPS22950L) + seam boards with SAMZO magnetic pogo pairs | **Comms board pairs**, swappable; rev A cable comms board (repurposed link board: hub population with TPS22950L, module population without); seams mechanical only; pogo parts dropped |
| Link over USB-C: pair 1 on D±, pair 2 on SBU, needing a full-featured cable between `left` and `right` | **Any USB 2.0 C-to-C cable**; SDA/SCL on D±, `INT` on CC; star wiring |
| 4 AA per module in two packs (12 AA per keyboard), pack OR (LM66200) and UVLO on each core | **Chainable 2×AA battery modules** on the hub, rev A two; each carries its own ideal diode; UVLO and slide switch on the hub drive `PACK_EN`; `PACK_SENSE` keeps the supervisor alive |
| Battery lighting cap 250 mA per module | **250 mA for the whole keyboard**; more battery modules add runtime only |
| Link VBUS switch on the downstream link boards, gated by handshakes | **Slot switch per hub slot**, on while its module answers |
| Module ID: resistor on the key board, ratiometric ADC read on the core, safe mode on mismatch | **Strap read by the module controller**, reported in the register map; any module in any slot |
| Core PCB 32 × 90 mm, 7 nets unrouted after every scripted approach | **Hub core = one base board, ~84 × 84 mm, in a ~90 × 90 mm tower** (2026-09-29; a vertical MCU board 2026-09-26 → 29); rev 7 core PCB kept in git for reference |
| Every board inside a module case | **The hub is a stack of layers**: optional layers (display…) / core / swappable connector layer / battery modules 1…N or a Qi2 board; 2×10 expansion (reversal-safe, CS0–CS3 by jumper, an ID EEPROM per layer; X1, 2026-09-28), 2×16 slot and 2×6 chain stacking headers |
| Qi2: keepouts, DNP footprints, a future Li-ion battery board | **Qi board on the hub's chain header, instead of the battery stack**, `AUX_5V`, never charging cells |
| — | **Reserved for future comms boards**: spare pins and `VSYS` on `J_SLOT`, spare pins on `J_COMM`, `VIN` accepts power from the module side |
| MDBT50Q-1MV2 with "-U1MV2 (chip antenna)" as second source, both keepouts on the core | **MDBT50Q-U1MV2 only** (u.FL; Raytac ver L: 1MV2 is the chip-antenna part, U1MV2 the u.FL part), on the base board; adhesive flex antenna inside the case wall, blanked RP-SMA knock-out for an external antenna (2026-09-29) |
| `CONFIG_BT_MAX_PAIRED=11` | 9 |
| Untethered use: modules work apart on BLE | **Modules need their hub cable**; accepted |
| Untethered deep sleep: a sleeping satellite cannot wake the central | Any module's keypress wakes the hub |
| 9 PCB designs, 22+ boards per keyboard | 8–9 PCB designs, ~18 boards per keyboard (fewer designs with assembly-house parts on them) |

Carried over unchanged: the pack chain per pack (OVP, reverse block, PTC, TVS,
bleeder, gate network, series budget), the host USB port board, the logic and LED
power paths, lighting, dial board, expansion board, layout geometry, plate, case
print route, most of the verification list.

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
- **M10** battery-module mechanics (contacts decided: 2×6 stacking header, stack only, any number of modules);
  **M11** the hub enclosure (2026-09-29: ~90 × 90 mm tower, MCU on the base board,
  core one joint tall; workflow in §14). **P20** the hub antenna parts (flex
  antenna, RP-SMA pigtail) and Raytac's -U antenna approval.
- **X1** closed 2026-09-28: top expansion header 2×10, reversal-safe, CS0–CS3 by
  jumper, an ID EEPROM per layer at 0x50 + CS number (§6).
- **F9** Zephyr/ZMK support for the TCA9548A and a custom `kscan` at the pinned
  version.

Rev 8 closes as moot: everything about the split transport, pair 2, the seam pogo
parts (P5, P6, P8), the link boards' KTS1693s, and the module-ID ADC bands (F6).
