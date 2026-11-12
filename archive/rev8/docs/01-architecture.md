# Architecture and decision record

Companion to [`../plans/keyboard.md`](../plans/keyboard.md), which is the
authoritative spec and owns every number. This document owns the *shape* of the
design and the *reasoning*: block diagrams, power and logic domains, hazard
analysis, and why each rejected alternative lost.

If a number appears in both, the spec wins.

**Rev 8** (2026-09-26): a hub on the desk holds the only radio, the only power
path, the host port and the cells; the three key modules carry keys, LEDs, the LED
driver and a small module controller, and link to the hub through swappable comms
board pairs. The rev 5–7 architecture (a core board with MCU and power path in
every module, a wired + BLE split) is commit `0b22b91`; §6 records why it lost.
Claims from earlier revisions now known to be wrong are called out in place rather
than quietly deleted.

## 1. System shape

One hub, three key modules, star-wired. The hub is the keyboard as far as the host
and the firmware are concerned; the key modules are I2C targets.

```
  [HUB]  MDBT50Q (BLE + USB), ZMK as one keyboard, power path, LED rail
         host USB-C (USB port board), expansion board, chain port (battery modules, later Qi)
         TCA9548A: one I2C channel per slot
           slot 1            slot 2            slot 3
             |                 |                 |
         comms pair        comms pair        comms pair       rev A: USB-C cable boards + USB 2.0 C-C cable
             |                 |                 |
  [left] key board      [right] key board   [numpad] key board
         module ctrl           module ctrl          module ctrl
         IS31FL3733            IS31FL3733           IS31FL3733
                               + dial board
```

- **One firmware image runs the keyboard.** ZMK on the hub, not split. It
  discovers modules at run time, reads each one's ID, and maps its keys into one
  matrix transform. No split transport, no failover, no cross-module lighting
  tunnel.
- **The module controller is the key board's only link endpoint.** It scans the
  matrix at ~1 kHz, decodes the dial, owns the LED driver on a local bus, and serves
  one register map (spec §9): an event FIFO, lighting frames, identity, status.
  `INT` tells the hub to read; the hub never polls the matrix.
- **Comms pairs are swappable because the register map is the contract.** Rev A
  carries it on copper: SDA/SCL on a USB 2.0 cable's D± pair, `INT` on CC, the
  switched LED rail on VBUS. A radio, optical or mixed pair can carry the same map
  later by forwarding events and frames; neither the hub nor the key board changes.
- **The hub is a stack of layers**: optional layers (display…) / core (one base
  board with the MCU on it) / swappable connector layer / battery modules 1…N or a Qi2
  board. The connector layer chooses the medium for all three modules.
- **The hub owns the power.** Cells, host USB and a future Qi board feed one power
  path; each slot gets the LED rail through its own latch-off switch; each key board
  makes its 3.3 V locally.
- **Not untethered.** Modules need their hub cable. That is the price of dumb
  modules, accepted in rev 8.
- **Any module in any slot.** The hub maps by module ID.
- **Deep sleep works across modules.** A keypress on any module raises its `INT`,
  which wakes the hub. Rev 7 could not wake a sleeping central from an untethered
  satellite.

## 1a. Board shape

```
  HUB STACK (top to bottom)
    [optional layers: display, ...] --expansion header 2x10 (pass-through)--+
    [CORE LAYER]  base board: MDBT50Q-U1MV2, power path, LED rail, TCA9548A, buttons, headers
                  + Yageo PCB antenna on the inside of the case wall (u.FL; whip knock-out, blanked)
                  + [USB port board] on J_USB (11)      USB-C, CC, KTS1693, USBLC6
                  + [expansion board] on J_EXP (15)     JST-SH 12, ESD (cabled accessories)
        --slot header 2x16--   --chain header 2x6--
    [CONNECTOR LAYER, wired]  carrier PCB, chain passed through
                  + 3 x [socket board = comms board, hub population] on J_SLOT (14)
                                                        USB-C, TPD6E05U06, TPS22950L, CC pull-ups
        --chain header 2x6--
    [battery module 1] --chain 2x6-- [battery module 2] -- ... -- [battery module N]
     or instead of all battery modules: [Qi2 board, later]

  EACH KEY MODULE
    USB 2.0 C-C cable from a hub slot
      -> [comms board, module population]  USB-C, TPD6E05U06, BAT54C CC -> INT
           | J_COMM (10)
         [KEY BOARD]  sockets, LEDs, IS31FL3733, module controller (MSPM0G3505), LDO
           | J_DIAL (5), right only
         [dial board]
```

**The principle is unchanged: put every failure mode on something cheap that plugs
in.** Plug wear, surges, ESD, reversed cells and encoder wear hit a
small board: USB port, comms, battery module, dial or expansion. The hub core and
key boards sit behind that protection.

Partitioning rules:

- **Anything medium-specific lives on the comms boards.** CC handling (the BAT54C
  and the pull-ups), the slot switch, the USB-C sockets and their ESD. A future
  medium replaces the comms boards and nothing else.
- **Anything that must reach the MCU without detour plugs into the hub core.** Host
  D+/D− crosses one cable (USB port board → hub core). The battery chain plugs into
  the hub core, where the undervoltage supervisor and the power switch sit.

Rules that protect it from mistakes:

- **Every header pin count is unique.** `J_SLOT` 14 and `J_COMM` 10 keep the two
  comms populations apart; `J_DIAL` 5, `J_USB` 11 and `J_EXP` 15 are unchanged. The
  battery chain uses its own connector type (M10).
- **Nothing on a key board sources power**, so no two things on a link can fight
  over VBUS. The module side has no switch and no CC `Rd`.

## 2. Power domains

```
  BATTERY MODULES (passive, up to 3; rev 8.1)
  -------------------------------------------
  4xAA --[PTC]--> own chain line; each module shifts the lines by one, so packs reach hub inputs A, B, C

  PACK INPUTS AND SYS (hub)
  -------------------------
  PACK_A/B/C --[bidirectional TVS]--[LM74610-Q1 + N-FET ideal diode]--+--> VBAT --[Qb P-FET]--+--> SYS
       `--[Schottky]--> PL40 node (10 k, 1 uF) --> TPS3840PL40 UVLO --> power switch --> Qb   |
                                                                  (Qb also off while USB is in)|
  USB AND AUX INPUT (hub)                                                                     |
  -----------------------                                                                     |
  host USB VBUS --[KTS1693 OVP 5.38-5.78 V, OCP latch ~2 A]--[TVS]--[LM66200 IN1]--+          |
  AUX_5V (chain header, Qi board later) ---------------------------[LM66200 IN2]------+-- VBUS_IN --[Qu P-FET]--+
                                                                   VBUS_IN --> TPS3840PL43 (USB present)

  DOMAIN A: VSYS, 3.3 V regulated (hub)
  -------------------------------------
  SYS --[TPS70933 LDO]--> VSYS --> MDBT50Q VDD, TCA9548A, hub I/O

  DOMAIN B: LED rail, ~5.0 V on USB and battery (hub)
  ---------------------------------------------------
  SYS --[TPS630701 buck-boost, fixed 5.0 V]--> LED RAIL --> expansion LDO (gated)
                                                   +-----------------+-----------------+
                                           slot switch (TPS22950L, latch-off), one per slot, on the hub-side comms board
                                                   |
  DOMAIN C: key board, per module
  -------------------------------
  cable VBUS --> IS31FL3733 VCC + LED anodes
             `--[LDO 3.3 V]--> module controller, driver VIO, link pull-ups
```

**Where the domains live.** The battery modules carry only cells, a PTC and seam
parts; pack protection, the OR, the UVLO, both switches and domains A and B are on
the hub base board; host VBUS protection is on the USB port board; each slot switch
is on its hub-side comms board; domain C is on each key board.

**Why one `SYS` rail (rev 8.1).** Rev 8 split the rails because USB (5 V) and a
2-cell pack (1.8–3.2 V) needed different converters, and paid for it with two
priority muxes, a logic boost, a USB LDO and an LED boost. A 4-cell pack (~4.0–6.4 V)
straddles 5 V the way USB does, so one rail takes either source, and one converter
per domain follows it. Full reasoning and the rejected alternatives in §6, "Battery —
up to 3 passive 4×AA modules".

**Why VSYS is an LDO output, always (rev 2, rev 6, rev 8.1).** The nRF52840 `VDD` is
rated to 3.6 V. **Rev 2 OR-ed 5 V VBUS straight onto VSYS**, which would have
destroyed the MCU on the first plug-in. **Rev 5 ran `VSYS` unregulated** from the
cells, so logic levels moved with the cells. Since rev 8.1 the TPS70933 (2.7–30 V
in) makes VSYS from `SYS` on every source, so `VDD`, the slot I2C levels and every
`AINx` reading are independent of the source; it drops out only briefly near the
UVLO cut, during an LM74610 body-diode window (spec §4).

**Why USB has priority over the packs.** An ideal-diode OR picks the higher source,
and fresh alkalines (~6.4 V) sit above any USB port, so they would carry the
keyboard while it is plugged in. The PL43 on `VBUS_IN` turns the battery switch Qb
off whenever USB is present, and a delay turns the USB switch Qu on only after Qb is
off (simulated at the datasheet corners, E21): the packs supply nothing on USB, and
a pack never back-feeds `VBUS_IN`.

**Why only the host port has an integrated OVP switch (rev 8).** The LM66200 behind
`VBUS_IN` is 6.0 V abs-max and the MDBT50Q's `VBUS` pad 5.8 V; the KTS1693's ±3.2 %
reference cannot trip between vSafe5V's 5.5 V and 5.8 V, so its divider sets 5.38–5.78 V
and gives up the top of vSafe5V on low-corner units rather than the MCU module (E22,
2026-10-01). A
discrete comparator plus P-FET was designed and
simulated first (rev 4 and 2026-09-13): its comparator output is undefined for
~190 µs at power-up, the FET's gate–drain capacitance let a 20 V hot plug through,
and a source that jumped from 5 to 20 V while connected still put 16.8 V on the
output. The KTS1693 switches off in 100 ns and debounces turn-on for 0.7 ms. Rev 7
had five of them, one per inward USB-C socket. **In rev 8 power only flows inward
at the host port.** Link sockets carry the hub's own LED rail outward, and the key
modules' sockets have no `Rd`, so a USB-C source never turns on into them. A
legacy USB-A-to-C charger forcing 5 V into a link socket is ≤6 V; a
non-compliant >6 V source there reaches the TPS22950L or the key board's LDO and
driver behind only the slot TVS (TVS0500 since 2026-10-01: VBR 7.5–8.4 V, ≤50 mA
DC breakdown), the same residual risk rev 7 accepted on its
downstream link ports.

**Why the key boards run from the LED rail, not `VBUS_IN`.** The key boards need
power on battery too. The LED rail is the one rail that exists on both battery and
USB and already has the current capacity. The cost is that the LED converter runs
whenever the keyboard is on, and in sleep the three slot switches stay on with it:
together most of the ~0.26 mA idle estimate (E7). Each key board makes its own 3.3 V
with an LDO, so `VIO` is derived from `VCC`'s own net and cannot come up first. On a
collapse an LDO that blocks reverse current can hold `VIO` above a falling `VCC`, so
the rev 7 series resistors at the driver stay.

**Why each slot has a latch-off switch.** A slot is a user-facing socket that
sources power. A shorted cable, a crushed plug or a phone plugged into a hub slot
must cost one slot, not the LED rail. The TPS22950L latches off above `IHCD`
1.2–1.9 A and stays off until `SLOT_EN` toggles; firmware keeps a slot on only
while its module answers (spec §6).

**Why one buck-boost makes the LED rail on USB and battery (rev 8.1).** Rev 3–8 fed
the rail from VBUS directly on USB (through an OR, then a priority mux) to avoid
pushing LED current through a 3.3 V LDO and back up through a boost, and boosted
from the cells on battery. With one `SYS` rail the TPS630701 takes either source and
regulates 5.0 V in buck or boost mode, so the rail never changes source and a weak
USB port no longer leaves max-bin LEDs short of headroom.

**Why domain B is ~5.0 V (E19, 2026-09-26; 4.7 V until rev 7).** The
driver's datasheet headroom is ≤400 mV sink at 672 mA and ≤200 mV source at 42 mA,
about 0.4 V at our 320 mA / 20 mA. The LED's maximum forward voltage at 20 mA is
4.1 V green and 4.0 V blue, so a max-bin die needs ~4.5 V at the driver. Rev 7's
4.7 V (4.63–4.87 V) left ~0.2 V with the driver on the same board; rev 8 puts ~1 m
of cable, a slot switch and two connectors in between (~0.1 V at 0.28 A), which left
~0.03 V worst case. The TPS630701's fixed 5.0 V (4.95–5.15 V) leaves ≥0.35 V after
the cable, under the driver's 5.5 V maximum. **Rev 3 said blue and green run to
about 3.6 V**; that was closer to typical than maximum.

**Why the driver is never power-gated.** Absolute maximum is "voltage at any input
pin, VCC + 0.3 V". Collapsing VCC while `VIO`, SDA and SCL still sit at 3.3 V puts
every logic pin above its ceiling. Idle is `SDB` low plus software shutdown, which
the datasheet rates at microamps. A side benefit: the 192 PWM registers survive
sleep, so the effect layer needs no reload-on-wake path.

**Why there is no I2C level translator.** Pin 39 is `VIO`, "input logic reference
voltage", and the datasheet's own application circuit ties it to the MCU rail while
the VCC group sits higher.

**The battery rules (rev 8.1).** Six hazards.

1. **No pack may reach another pack.** Each pack has its own chain line and its own
   LM74610 ideal diode into `VBAT`, which blocks reverse current, so a fresh pack
   never charges a depleted one, alkaline or not. This is why the module count is
   capped at three: one hub input per pack.
2. **Reverse polarity.** The LM74610 turns its FET off within 2 µs of reverse voltage
   and blocks to −45 V; the pack's sense Schottky blocks it from the UVLO node. The
   input TVS sits ahead of the LM74610, so it is bidirectional; a unidirectional part
   would forward-conduct into a reversed pack with only the PTC limiting the current.
3. **Overvoltage: none needed (rev 8.1).** Li-ion is not supported (2026-09-30), so
   the worst input is a fresh 4×alkaline pack at ~6.4 V, and every part on the pack
   side and on `SYS` is rated ≥10 V. Rev 2 had no protection against 14500 cells;
   rev 6–8 had a per-pack supervisor + P-FET OVP with a gate RC and a pack bleeder,
   all gone with the 2-cell packs.
4. **Short circuit.** NiMH packs deliver amps. The PTC in each pack lead (MF-MSMF125/16X:
   1.25 A hold, 2.5 A trip) is the only current limit on the battery side; a hard
   short also pulls the pack below the UVLO, which opens Qb. On the USB side a
   KTS1693 latch stays fully on for its 5–10 ms debounce, so one short pulse passes;
   accepted rather than trading the latch for a 200 ms retry loop. On the slot side,
   each slot's TPS22950L latches off above 1.2–1.9 A.
5. **Over-discharge.** Firmware enters system-off at 4.12 V on the UVLO node. As a
   backstop the TPS3840PL40 turns Qb off at 4.0 V on its node (~4.16 V at the hub
   input, ~1.03 V/cell plus the path IR). On battery that removes supply from the hub
   and every key board together. **Rev 2 put the supervisor on boost EN alone**,
   which collapsed the driver's VCC under a live `VIO` and left the MCU draining the
   cells indefinitely.
6. **Pack load is not shared.** Ideal-diode OR-ing hands the whole load to the
   highest pack until they equalise. **Rev 2 claimed two packs halve the C-rate.**
   Every per-pack part is sized for the whole keyboard's battery load, and battery
   lighting is capped at 250 mA on the rail for the whole keyboard, ~0.37–0.45 A from
   one pack near the cut. Adding battery modules adds runtime, not brightness. The
   worst-case series path (holder, PTC, three pogo hops, ESQ, both FETs) is ~291 mΩ,
   ≤0.13 V at 0.45 A.

**Why the UVLO is fed from the pack inputs (rev 8.1, E21).** The supervisor that cuts
the packs off must survive the cut. Rev 7 and 8 fed it ahead of the OR through
Schottkys (`PACK_SENSE` in rev 8), and rev 8.1 does the same with one Schottky per hub
input. A first rev 8.1 drawing put it on `VBAT`, which keeps its supply after the
cut but sits ~0.77 V under the pack whenever an LM74610 runs on its body diode (for
~45–60 ms each time a pack takes over), so it tripped at USB unplug (switchover sim).

**VBUS must reach the MDBT50Q's `VBUS` pad directly**, not only through the power
path. The USB regulator and attach detection both depend on it.

## 3. Logic domains and crossings

| Signal group | Domain | Crossing |
| --- | --- | --- |
| Key matrix, encoder | key board 3.3 V | none; module controller pins |
| LED matrix CS/SW, anodes | slot VBUS (LED rail) | none |
| Driver I2C and `SDB` | key board 3.3 V, referenced by `VIO` | module controller's local bus; 470 Ω on SDA/SCL and 1 kΩ on `VIO`/`SDB` at the driver, for a collapse where `VIO` outlives `VCC` |
| Link SDA/SCL | hub `VSYS` 3.3 V ↔ key board 3.3 V | TCA9548A channel (isolates an unpowered key board); pull-ups on the key board side to its own 3.3 V; 470 Ω series at the key board; ESD at both sockets |
| Link `INT` | key board open-drain → hub GPIO | BAT54C on the module side, 220 kΩ pull-ups from `SLOT_EN` on the hub side; 1 kΩ series at the key board |
| Internal cables | same domain at both ends | none: not an entry point; header pin counts are unique |
| Host CC sense | 0.25–2.04 V into `AINx` | series R + ESD |
| Expansion I2C/SPI | `VSYS` | none on our side |

There is no mandatory level translator anywhere.

## 4. The link

**One slot, one module, one I2C channel.** The hub opens a slot's TCA9548A channel
for a transaction and closes it afterwards, so a key board being plugged, pulled or
hung affects only its own channel. A stuck channel is recovered by the TCA9548A's
`RESET` and nine clocks on that channel.

**Why I2C and not UART.** The nRF52840 has two UARTEs and three slots; the
TCA9548A gives one TWIM as many slots as needed and isolation per slot. The module
controller is an I2C target, so there is no protocol state beyond the register map.

**Why on a USB 2.0 cable.** The link needs five conductors: power, ground, two bus
lines and an interrupt. A USB 2.0 C-to-C cable has exactly VBUS, GND, D+, D− and
CC, is stocked everywhere, and is a spare part anyone has. D± pass straight
through the cable and are tied A6=B6, A7=B7 at each receptacle, so all plug
orientations work for SDA/SCL without mirroring. CC has one wire in the cable,
landing on CC1 or CC2 by orientation, so the module side ORs both through a BAT54C
and the hub reads both.

**What it costs.** SDA and SCL ride one twisted pair, which couples SCL edges onto
SDA; I2C over a 1 m cable is at the edge of what I2C is for (E16). Designed for
400 kHz; the hub drops a slot to 100 kHz on its own when it counts link errors. `INT`'s pull-up must stay well above USB `Rp` values so a phone in a
hub slot does not see a source (E17). E-marked cables pull one CC pin low through
their Ra; the hub masks that pin.

**Why not a differential bus (PCA9615) on the cable.** It needs four signal wires;
a USB 2.0 cable has three. It stays an option for a future comms pair on a
different medium or a full-featured cable.

**Slot power policy (E18, 2026-09-26).** A slot turns on at boot and stays on
while a module controller answers; with no answer within ~200 ms it turns off, and
while the hub is awake it is re-probed with ~100 ms of power every ~2 s. Asleep,
only slots holding a module stay powered and empty slots are not probed. Rejected:
always on (a phone or legacy device would drain the cells) and a passive
detect-before-power signature (another sense path per CC pin that must not look
like a USB source either). That keeps a phone, a looped cable or a dead module from
drawing on the LED rail indefinitely.

## 5. Mis-plug hazard analysis

Every link socket is a user-facing USB-C socket, so every plausible USB device and
cable must be inert rather than damaging.

| Plugged in | What happens | Verdict |
| --- | --- | --- |
| Phone or laptop (C-to-C) in a hub slot | `INT` pull-ups at ≤~0.09 V against the device's `Rd`, below vRa max 0.15 V (Type-C R2.0 Table 4-36), so no source is seen; slot VBUS is on until the probe times out; no module answers, slot turns off, re-probed later | Inert (E17, E18) |
| Legacy device on a C-to-micro-B cable in a hub slot | Draws from VBUS regardless of CC until the probe timeout; latch-off above 1.2 A | Benign; a few seconds of current per re-probe |
| C-to-C charger in a hub slot | Charger needs `Rd` to source; sees none | Inert |
| Legacy USB-A-to-C charger in a hub slot | 5 V forced into the slot output; the TPS22950L has no reverse current blocking, so it can back-feed the LED rail at ≤5.25 V; the rail is the TPS630701's output, in power-save mode (`PS/SYNC` high, rev 8.1), so it stops switching rather than pumping that current back into `SYS` (rev 8: the TPS2116 blocked it) | Benign; >6 V non-compliant sources are the accepted residual risk |
| Key module into a laptop or C-to-C charger | No `Rd` on the module side: the source never turns on VBUS | Inert |
| Key module on a legacy USB-A-to-C charger or port | 5 V powers the key board; D± see the host's 15 kΩ pull-downs or nothing; no hub, so nothing addresses the module controller | Inert |
| Two key modules cabled together | Neither sources power | Inert |
| Two hub slots cabled together | Both sources carry the same rail; the hub probes one channel at a time, nothing answers, both slots time out | Inert |
| A hub slot cabled into the hub's own host port | Slot VBUS reaches `VBUS_IN` through the host port's KTS1693, a supply loop from the LED rail; no module answers, the slot times out and the loop opens; `ACOK` rising with a slot on is flagged | Recovers after the timeout (E18) |
| E-marked (5 A) cable on a link | Ra on the VCONN pin: at the module end the BAT54C blocks it; at the hub end one `INT` pin reads low and is masked | Works |
| Charge-only cable on a link | No D±: the module powers but never answers; slot times out | Inert |
| Link cable pulled live | SDA/SCL/`INT` may stay at 3.3 V while the key board's rails fall; 470 Ω / 1 kΩ at the key board limit clamp current; the TCA9548A channel is closed between transactions | Against the service rule, designed to survive, tested |
| Hub-side comms board cabled into a key board header, or the reverse | `J_SLOT` 14 and `J_COMM` 10 do not mate | Cannot happen |
| Two modules with the same ID | The hub uses the first and flags the second | Inert, flagged |
| Metal object across a battery module's chain contacts | ESD clamp on the chain contacts; `VBAT` shorts are PTC- and UVLO-bounded as any `VBAT` short (battery rule 4) | Bounded |

## 6. Decision record

### Architecture — hub + dumb key modules (rev 8)

Rejected **a core board with MCU and power path in every module, linked by a
wired UART split with BLE failover** (rev 5–7). It kept every module wireless and
untethered, but at the cost of three radios, three power paths, twelve cells, 22+
boards per keyboard, a multi-peripheral wired split transport that ZMK upstream
does not have (a rewrite of that file), all-or-nothing failover, a numpad link
passed through `right` in copper on SBU needing full-featured cables, orientation
detection, handshakes, VBUS gating chains and cross-module lighting tunnelled
through `INVOKE_BEHAVIOR`. Its core PCB also did not fit: 32 × 90 mm inside a key
module, with 7 nets unroutable after every scripted approach.

Rejected **a USB hub with three independent keyboards**: the modules become
separate HID devices that cannot share layers.

Chosen: one hub with one radio and one power path; dumb key modules on cables. The
costs accepted: the key modules are tethered to the hub; the keyboard is a hub plus
up to three cables on the desk; a dead hub stops the whole keyboard (one board to
swap); battery capacity is what the hub carries, not three times four AA.

### Key board brain — module controller MCU (rev 8)

Rejected **raw matrix lines over the link**: 13–17 scan lines per module plus the
LED bus and power, a custom multi-conductor cable, ESD straight onto the hub's MCU
pins, and a scan slowed by cable capacitance. This is the "dumb satellite" rev 5
rejected, and the reasons still hold.

Rejected **the TI TCA8418 keypad scanner**: no firmware, event FIFO, 3 µA idle, one
fixed address (fine behind a TCA9548A), but keypad debounce is fixed: "All columns
are scanned once every 25 ms… it takes 25 ms to detect the key press… [or] 40 ms"
(SCPS215G p. 33). That latency sits on top of BLE's.

Rejected **the TI TCA6424A 24-bit expander scanned by the hub**: no key-board
firmware, 1 µA standby, fast on a cable with a port-wide scan driver (~2 ms per
module), but the hub drives each column and reads the rows over I2C, dozens of
round trips per scan. That cannot cross a radio or optical link, so every future
comms board would need its own scanner MCU and the hub side an expander emulator.

Rejected **a module MCU speaking a UART split protocol**: brings back a split
protocol and needs more UARTs than the hub has.

Chosen: a small non-radio MCU with one I2C register map: **TI MSPM0G3505 in
LQFP-48** (P19, 2026-09-26): 44 GPIO, two I2C, a QEI timer for the dial, 1.5 µA
STANDBY, and a ROM I2C bootstrap loader on the pins that carry the link, so the
hub can reflash key boards over their cables. Rejected: MSPM0L1306 (zero pin
headroom, QFN), RP2040 (0.18 mA asleep, external flash). Costs: a
second firmware image to maintain and flash, and a part the key board did not have
in rev 7 (where the core scanned). Keyboardio's Model 01 uses the same shape (an
ATtiny88 key scanner per half on I2C over cables).

### Comms — swappable pairs, cable first (rev 8)

Rejected **custom radio or optical links for rev A**: the medium is not the
problem, power is. A module linked without wires needs its own cells and power
path, which is most of what rev 8 removes. Free-space IR to a desk hub also needs
line of sight a hand or a mug breaks. Kept as future comms boards (spec §15),
together with a mixed pair (cable + radio) that picks or relays between media
itself.

Rejected **magnetic breakaway cables for rev A**: they protect the sockets from a
snag, but the cable becomes a custom part and bounces on every connect. A comms
pair with a magnetic connector can come later without touching anything else.

Rejected **daisy-chaining modules through the seams**: one cable on the desk, but a
shared bus across modules (addressing, and hot-plugging the numpad glitches
everyone) and more seam contacts.

Rejected **a non-USB locking connector**: impossible to confuse with USB, but custom
cables. The USB-C mis-plug cases are all inert or bounded (§5).

### Hub — a stack of layers (rev 8, 2026-09-26)

Chosen with the user: optional layers / core / connector / battery modules 1…N or
a Qi2 board. The **connector layer** is the one part a user swaps to change how
the key modules connect, so the medium is a single, whole-hub choice; a mixed
layer can still carry two media. Joints: a 2×6 chain header in the same place on
every layer from the core down (so a battery module even mates straight to the
core for testing), a 2×16 slot header between core and connector only, and a
pass-through 2×10 expansion header on the core's top for optional layers. Two
headers at different places on the core/connector joint key its orientation.

Rejected **one large core/connector header** (~2×22): a battery could no longer
mate to the core, and a 44-pin reversal-safe layout is impractical. Rejected
**cabling the slots between core and connector**: cables inside a stack meant to
click together.

**Wired connector layer: a carrier plus three socket boards.** Rejected **the
sockets on the layer PCB**: simplest, but a worn socket would take the other two
and the slot switches with it. The socket boards are the hub-population comms
boards on `J_SLOT`, so wear still lands on the smallest board.

**Pin orders (2026-09-29): every header in the slot path is reversal-safe** (spec
§6). `J_SLOT` and `J_COMM` follow the rule of the other GH headers: power meets its
own net, open-drain meets open-drain, spares meet spares, and the odd GND faces the
one signal that is harmless from both ends (`INT_A` on `J_SLOT`, `INT` on
`J_COMM`; `SLOT_EN` facing GND would short a hub output). On `J_SLOT`, GND beside
SDA and SCL was preferred over GND beside the LED rail. **The 2×16 slot header is
also reversal-safe**, although the chain header already keys the joint (the user's
choice, over per-slot blocks keyed only by the second header): slot 0 and slot 2
are mirror images, so a rotated layer swaps them and still works (keys map by
module ID), and slot 1 folds onto itself with its `SLOT_EN` facing the global
`SPARE`, so it stays off. Cost: the three slot blocks are not identical on the
carrier. The spares on `J_SLOT`/`J_COMM` cannot reach the far end of a USB 2.0
C-to-C cable (five conductors), so they stay reserved for other media.

**Stacking headers: Samtec ESQ, socket up, tails down (M10, 2026-09-29).** A
battery module is a board plus a 15.0 mm AA holder, so a joint must span ~17 mm,
beyond an Arduino-style long-tail socket (~11 mm). One ESQ joint spans ~15.3–18.0
mm (A + B = 23.24 mm for every lead style). The user chose the PC/104 orientation,
socket on each board's top face, over socket down / tails up, which would have left
only a recessed female socket at the bottom of the stack; the cost is live `VBAT`
tails under the bottom module, which a separate printed base covers (2026-09-29). Rejected **two parts
(extra-long pins + socket)**: easier to second-source, but two parts per header per
board and ~20 mm pins. **Lead style `-24`, standard force, gap 17.5 mm on every joint
(2026-09-29)**: 2.5 mm over the AA holder and 4.14 mm insertion, for 8.05 mm tails
under the bottom module (vs 5.5 mm with `-34` at 17.0 mm, which left 2.0 mm over
the holder); low insertion force `-49` rejected for lower contact normal force
against the E20 contact budget.
**Battery seams on pogo pins (2026-09-29)**: every cell swap opens the chain
joints above that module, and ESQ is rated 100 mating cycles (10 µ″ gold), so the
seams below the connector layer carry the chain on 12 pogo pins (100 000+ cycles)
standing on each battery board, pins up, landing on gold target discs under the board above;
the magnets hold the stack against the springs (~7 N). **Part (2026-09-30): Mill-Max
827-22-012-10-004101**, a through-hole 2×6 strip with 2.29 mm stroke (60 g per pin at
mid-stroke, 20 mΩ max, 7 A), on a cap board over a **Samtec DW-06-17-T-D-254** riser
(2026-09-30: one 2×6 board spacer soldered through both boards at 6.45 mm ±0.20, no
extra mated contact; a pluggable BCS socket + pins was rejected for its extra contact); **targets (2026-09-30):
Mill-Max 1578-0 discs** (Ø1.98 × 0.63 mm, 10 µ″ hard gold) reflowed on ENIG pads, since
ENIG alone wears and hard-gold fingers exist only at a board edge; chosen over the
1.4 mm-stroke 818/814 for twice the window for FDM seam tolerance at the same force,
over the SMT 820 (solder pads alone take the side load) and the 3 mm 839 (~11.8 N). A module left behind after
a lift shows dead pins (its pack switches off when detached). The screwed
core ↔ connector joint and the expansion header keep ESQ. Rejected: ESQ on every
seam, pogo everywhere, pins facing down.

**Key-board bootloader recovery (2026-09-29, F7's hardware side).** Chosen:
software entry, the vector table written last (so an interrupted update boots
into the ROM BSL by the blank-device rule), and TI's default `BSL_invoke` pin PA18
with a pull-down and a rescue pad. Rejected **the hub forcing the BSL through
`INT`** (remote, but reopens E17's margins and needs a NONMAIN write per chip) and
**SWD only** (a probe and an open case for any rescue; PA18 needs its pull-down
anyway).

**Optional layers stack on top; the expansion board's JST-SH socket stays.**
Rejected **top header only** (no cabled accessories, ESD moves to every layer) and
**SH socket only** (add-ons dangle on cables). The shared bus costs one chip select
per SPI layer, so the number of CS lines caps how many SPI layers stack.

**Top header (X1, 2026-09-28): 2×10, four chip selects picked by a jumper on each
layer, an ID EEPROM per layer, a reversal-safe pin order** (spec §6). A layer keeps
its CS whatever the stack order, which is what ZMK's fixed devicetree needs; the
cost is 4 full-function pads (18 of 24 in use) and a jumper the builder sets.
Rejected **rotated CS lines** (each layer takes the bottom line and shifts the rest
up; no jumper, no clash, but a layer's CS then depends on its position, so
reordering breaks a static devicetree), **two CS lines on a 2×8** (frees 2 pads,
caps SPI layers at two, a new core to grow) and **CS from an I2C expander** (every
CS edge an I2C transaction, fragile as Zephyr `cs-gpios`, one more part on the
core). The ID EEPROM (Microchip 24AA024, 2026-10-01; address 0x50 + CS number by jumpers next to
the CS jumper) tells the hub which layers are fitted, on which CS, of what type and
revision, and catches two layers on one CS; it does not auto-configure drivers.
Rejected **no ID** (a write-only SPI display on the wrong CS is just blank, and
adding an ID later changes every layer) and **presence by a pull-up on CS** (the
nRF52840's ~13 kΩ pull-down against a 10 kΩ pull-up reads ~1.9 V, under `VIH`;
gives no type, and two layers on one CS read as one). The pin order puts power on
power, hub outputs on hub outputs and layer-driven lines on hub inputs when a
layer is fitted 180°; offset-by-one is left to the enclosure (M11).

**Core layer: one base board with the MCU on it, antenna in the case wall
(2026-09-29).** Rev 8 first (2026-09-26) put the MCU on a vertical board standing
on the core's wall, so an on-module antenna had a free edge facing the room, joined
to the base board by a 2.54 mm right-angle 2×30 (`J_MCU`). Laying out the tower
showed that board is ~27–32 mm tall (socket, two header rows, the 15.5 mm module
with its antenna up) against one ESQ joint's 15.3–18.0 mm gap, so the core needed
a riser (a passive board carrying the expansion bus up a second joint). Raytac's
datasheet (ver L) also showed the spec's second source was wrong: **1MV2 is the
chip-antenna part, P1MV2 the PCB antenna, U1MV2 the u.FL part**, all on one land
pattern. The user asked for a detachable antenna, then an antenna inside the case:
**chosen, the MDBT50Q-U1MV2 on the base board, its u.FL to an adhesive flex
antenna on the inside of a core-section wall, and a blanked RP-SMA knock-out in
that wall** so an external antenna on a pigtail is a swap, not a respin. That drops
the MCU board, `J_MCU`, the wall's keying slot and the riser; the core is one joint
tall and the tower ~17–20 mm lower. Costs accepted: **a single-source module**
(no other u.FL module on these pads), an MCU fault costs the whole base board (the
module's bottom pads need hot air), the antenna part and its Raytac approval still
to settle (P20, closed 2026-10-01, below), and RSSI now depends on where the
antenna sits in the case.

**Antenna parts (2026-10-01, P20).** Raytac's separate MDBT50Q-U1MV2 datasheet
(ver L, ch. 7) lists four antennas tested with the -U; only two carry CE, and the
hub uses both: the **Yageo ANTX100P011B24003** PCB dipole (39 × 10 × 0.55 mm,
adhesive, 2.2 dBi, ≥10 mm from metal) inside the rear wall, and the **Yageo
ANTX100ETHAB24553** whip (2.0 dBi, integral 100 mm cable, base Ø9.35 mm) as the
external option through a blanked knock-out. The RP-SMA knock-out and pigtail went:
no RP-SMA antenna is on the list, and Raytac warns its certificates "might not be
applicable" with any other antenna. Costs accepted: the PCB antenna is rigid, has
no data on plastic and resonates near 2.35 GHz in Yageo's fixture, so the 2 mm ASA
wall may cost match at the top of the band (RSSI test); the whip needs a printed
clamp; the external antenna is swapped inside the core (Hirose U.FL: 30 cycles).
Rejected: flexes tuned on 2 mm ABS (Taoglas FXP74, FXP830) or tolerant of metal
(Ezurio FlexPIFA), all outside Raytac's list and two of them over 2.2 dBi.
Rejected: **1MV2 with P1MV2 as second source** (integral, both in Raytac's reports,
but RF tied to the tower and nothing to fall back on); **the U1MV2 with only an
external antenna** (a stick on the desk); **keeping the vertical MCU board** with
the u.FL module (a 60-pin joint, a riser and a taller tower for an on-board antenna
no longer used); earlier, **a horizontal core with an antenna tab** and **the whole
core vertical**. The pad assignment (spec §5) stays.

### Battery — up to 3 passive 4×AA modules (rev 8.1, decided 2026-09-30)

The user asked for simpler battery modules: holder only, the connector just
passed on. A board stays either way (the pogo strip, riser and target discs solder
to one, and the holder is PCB-mount), so the choice was active vs passive. Rev 8's
module board did three jobs a passive board cannot: it OR-ed its pack (so a fresh
pack never drives a flat one), switched itself off when lifted (so its ~6 mm proud
pins were dead), and protected the LM66200 (a 5.5 V class part) against reversed
cells. **Li-ion is not supported at all (2026-09-30)**; the rev 7 overvoltage reasoning
about 14500 cells below is history only. Moving those jobs to the hub works only if each pack keeps its own
line to the hub, which caps the count. The user accepted **up to 3 modules of 4×AA
NiMH** (4.8 V nominal, ~4.0 V empty, ~5.6–5.8 V fresh; ~6.4 V with alkalines).

Chosen: **passive modules** (4×AA holder, one PTC, the pogo seam parts); **one
chain line per pack, shifted by one position per module** so identical modules
reach hub inputs A, B, C by position and a 4th is unconnected; chain pinout 1/12
`PACK_A`, 3/10 `PACK_B`, 5/8 `PACK_C`, 2/11/4/9 GND, 6/7 `AUX_5V` (reversal-safe);
**the hub** carries per-input reverse/OVP/ESD, a 3-input OR, a buck-boost for the
~5.0 V LED rail (the 4-cell pack spans it), a 3.3 V regulator and a 4-cell UVLO
(parts decided the same day, E21). Accepted: a lifted module's pins carry its raw pack (the PTC
bounds a short); the hub is laid out for 3 inputs whether used or not. **Li-ion is not
supported (2026-09-30)**, which removed the overvoltage cut entirely.

**Hub power path (2026-09-30).** Rev 8 split the rails because USB (5 V) and a 2-cell
pack (1.8–3.2 V) needed different converters. A 4-cell pack (3.6–6.4 V) straddles
5 V like USB does, so one `SYS` rail takes either, a buck-boost (TPS630701, fixed
5.0 V) makes the LED rail from it on USB and battery alike, and one LDO (TPS70933)
makes 3.3 V: the logic boost, the USB LDO, both TPS2116 muxes, the LED boost and its
PR1 divider all go. Each pack input is a zero-Iq LM74610-Q1 ideal diode (reverse
protection and OR), and one P-FET (CSD25402Q3A) after the OR is the only battery
cutoff: off when the power switch is off, when the TPS3840PL40 sees <4.0 V,
or when a TPS3840PL43 on `VBUS_IN` sees USB (a second, reversed CSD25402Q3A then feeds
`SYS` from USB). The supervisor is powered from the three pack inputs through one
Schottky each (BAT54C + BAT54, 2026-10-01), ahead of the LM74610s and the cut, so it keeps
its supply without rev 8's `PACK_SENSE` diode-OR. It first sat on `VBAT`; the E21
switchover sim (`tools/sim/e21_switchover.py`) showed why that fails: each time a pack
takes over, its LM74610 runs ~100–155 ms on the FET's body diode (pump capacitor empty)
and then 55 ms every ~2.7 s, ~0.77 V under the pack, so a `VBAT` sense cut out at
unplug from packs up to ~4.9 V. The same sim set the USB handover: Qu's gate pull-up
10 kΩ (off before Qb turns on, or the pack back-feeds `VBUS_IN` and USB is re-detected
forever) and a 2.2 MΩ / 22 nF delay on N4's gate with a BAT54 bypass (Qu on only after
Qb is off, or a fresh alkaline pack drives `VBUS_IN` past the LM66200's 6.0 V; 10 nF
failed at the datasheet corners), N2's pull-up 1 MΩ and 100 µF on `SYS`; then the last
values: Qb's gate pull-up 1 MΩ, N1's pull-down 4.7 MΩ (its current runs through the
sense Schottkys and lifts the cut), a 100 kΩ `VBUS_IN` bleeder (Qu's leak must never
fake a USB detect) and a 1 µF LM74610 pump cap (halves the post-handover window).
The supervisor's `VDD` sits behind 10 kΩ with 1 µF, which keeps the TVS clamp
(15.4 V) off its 12 V pin and gives firmware ~166 ms to drop the lighting to the
battery cap after USB goes; without that a ≤4.6 V pack cycles the cut at the ~0.8 A
USB rail. Firmware's own low-battery stages read that same supervisor node through a
switched 1/3 divider (low-leakage CSD25483F4, so the pin is not loaded), with a one-off
gain calibration at bring-up, and power off cleanly at 4.12 V, just above the 4.0 V
±1.5 % hardware cut.
First pick was the LM74720-Q1 per input (reverse, OR and OV in one), dropped once its datasheet showed an internal boost
with an inductor per channel, and OV was unneeded without Li-ion. Worst-case series
path ~291 mΩ (≤0.13 V at 0.45 A).

Rejected: **active 4×AA modules** (protection and a ≥6.5 V ideal diode per module,
any number of modules; more parts per module), **staying at 2×AA**, **packs
directly in parallel** (packs charge each other; lifted pins unbounded).

### Battery — chainable 2×AA modules on the hub (rev 8, superseded by rev 8.1)

Rejected **fixed battery slots on the hub**: the pack count is fixed when the hub
is laid out.

Rejected **a Li-ion cell with a charger in the hub**: the user kept AA cells (buy
anywhere); Qi is an alternative power source, not a charger.

Rejected **the LM66100 as the per-pack ideal diode**: 1.5 A, 150 nA, SC-70, but
**210 mΩ max at 1.8 V** (SLVSEZ8A), which puts the pack path near 455 mΩ against
300 mΩ. An LM66200 with one channel used keeps the rev 7 ≤51 mΩ (E20).

Chosen: every battery module carries the rev 7 pack chain plus its own ideal diode,
and chains to the next through a pass-through stacking header, modules stacked
under the hub (M10, 2026-09-26; side by side is a future option). The header's
pinout is reversal-safe and a detached module switches itself off (spec §4). More
modules add runtime, not peak current (battery rule 6).

### USB power — LDO + priority mux, LED rail direct, CC sensed (rev 3–8; rev 8.1: one `SYS` rail, §2)

Rejected **LDO before the OR**: fewer parts, but fresh packs win the OR and drain
on USB.

Rejected **everything through the LDO**: ~270 mA of rail current for the whole
board on default USB, and a hot LDO.

Rejected **ideal-diode OR for the LED rail** (rev 3): at the low end of USB
tolerance the boost wins and the cells carry LED current while on USB (rev 7 and
earlier said the LDO would; the boost is fed from `VBAT`).

Chosen: logic through LDO + mux, LED rail straight from VBUS through a priority
mux, and CC sense on the
host port so firmware uses 1.5 A or 3 A when offered. Since rev 8 that one budget
covers the whole keyboard; the hub renders every LED and applies it.

### Lighting — IS31FL3733, common-anode, 1 CS + 3 SW, 20 mA peak

Rejected **SK6812MINI-E addressable chain**: stock ZMK support and one data wire,
but 0.6 mA per part merely sitting powered.

Chosen for what it does to the *off* and *partial* states: microamps idle, charge
only for lit LEDs.

**Rev 1 described the part backwards**; the datasheet is explicit that `CS1~CS16`
source and `SW1~SW12` sink. Resolved to common-anode, one CS and three SW per LED,
the configuration behind the datasheet's headline "64 RGBs".

**Rev 2 set 42 mA peaks.** At 1/12 duty that averages 3.3 mA, but typical
reverse-mount RGB parts are rated around 20 mA DC. Peak is now fixed at ~20 mA,
safe for any candidate part, and driver heat roughly halves. Full-board brightness
drops accordingly; on battery that level also happens to sit at the 250 mA cap.

**Cross-module lighting (rev 8).** The hub renders every LED and sends frames to
the module controllers, ~100 full frames/s at 400 kHz before compression (spec §7).
Rev 3–7 tunnelled `(command, argument)` through ZMK's `INVOKE_BEHAVIOR` because the
split protocol had no generic payload; with no split, that mechanism is gone.

### Host profiles — dial with preview-then-commit

Rejected **absolute nine-position rotary switch**: a maintained contact reads as a
permanently held key and fights deep sleep.

Rejected **cycling pushbutton** and **next/previous pair**: a stray press changes
the live connection.

Rejected **magnetic angle sensor**: 3.4 mA whenever awake.

Chosen: a detented mechanical quadrature encoder with preview-then-commit, Bourns
PEC11R with 24 detents and 24 pulses. It must rest with **both** contacts open at
every detent, which Bourns states for pulses = detents; variants with half as many
pulses as detents alternate between open and closed rests, which reintroduces the
standing pull-up current.

### Profile indication — light number-row keys 1 to 9

Rejected **seven-segment digit** in both variants.

Rejected **requiring shine-through caps**: it narrows purchasable sets sharply and
works against the sculpted-profile dish argument.

Rejected **separate indicator LEDs behind a light pipe**: legible on any cap, but
adds parts and a case window.

Chosen: the RGB already under every key, accepting that on opaque caps the
indication reads as a glow around the cap edge. Legibility is checked in the Phase 1
test cell.

### Cells — alkaline and NiMH only (OVP until rev 8; none since rev 8.1)

Rev 8.1 (2026-09-30): Li-ion is not supported and the packs are 4×AA, so the OVP and
the reasoning below about 2-cell packs are history; 4 × L91 lithium primaries are not
checked against rev 8.1 and stay unsupported.


Rejected **supporting lithium primaries through a regulator**: costs dropout at the
NiMH end or a bypass-mode part's quiescent current.

Rejected **supporting them as-is**: 3.66 V against a 3.6 V recommended maximum,
with an OVP threshold squeezed into the tolerance band.

Rejected **docs-only protection against 14500s** and **a crowbar clamp**: the first
destroys three boards on one mistake, the second depends on a PTC tripping before
the clamp fails.

### Switches and caps — MX hotswap, widths to 2.75U

Rejected **Kailh Choc v2**: slimmer, but lost to the off-the-shelf keycap
requirement. **Rev 1 then capped widths at 2U**, which made a bottom row
unbuildable. Resolved to ≤2.75U with a flat bottom row. The finished keyboard
stands visibly taller than a K860.

### Plate — 1.5 mm FR4

Rejected **aluminium**: best feel, but a ground plane over the antenna and a second
supplier. Rejected **printed resin**: MX clips crack it under hotswap cycling.
Rejected **plateless**: sockets take lateral load and crack over time.

Chosen: FR4 from the same fab, no copper, plate-mount stabilisers.

### Layout — true arc on the alpha rows, standard pitch

Rejected **exact clone including non-standard widths** and **per-block rotation
with straight rows**.

**Rev 1 opened the pitch to 19.8 mm on arithmetic that was wrong twice.** The
pitch stays at 19.05 mm; the key field matches the K860's 456 mm, and two seams add
about 12 mm overall, accepted as a known deviation.

### MCU — pre-certified module, on the hub only (rev 8)

Rejected **bare nRF52840 with a PCB antenna** and **socketed nice!nano**. The hub
carries the **MDBT50Q-U1MV2** (u.FL) with a Yageo PCB antenna in the case wall
(2026-09-29 / 2026-10-01, §1a above). Raytac restricts **21 of the 48 pads to low-frequency
I/O**; the hub uses 42 of 47 GPIOs with 19 of 24 full-function pads (spec §5,
2026-09-29). The 32.768 kHz
crystal is **not** inside the module. The nRF52840's TWIM tops out at **400 kHz**,
not the 1 MHz rev 2 assumed.

## 7. Mechanical

The key modules lose their cells, their core board and their seam contacts. What
is left in a key module is the key board, the plate, a comms board at the rear
wall and, on `right`, the dial board. **Seams are mechanical only**: two walls and
the joining hardware in ~6 mm.

**The hub is a tower of layers** (M11, 2026-09-26): optional layers (a display
first) on top, the core layer, the swappable connector layer, then battery modules
(any number, M10) or a Qi2 board in their place. Each layer is its own enclosure
section, latched or screwed to the next; the stacking headers carry signals only.
The tower is ~100 × 100 mm (2026-09-29); the core is one base board with the MCU on
it and one joint tall; the hub antenna is a Yageo ANTX100P011B24003 PCB antenna
inside a core-section wall with a blanked knock-out for the Yageo whip behind it
(2026-10-01). Walls (2026-09-29): slot sockets
and the controls on the front (facing the keyboard; 2026-10-01: three NKK UB snap-in
pushbuttons with 17.8 mm square bezels, a green latching power button and red/black momentary
reset/boot, wired to the core board, chosen to be easy to press; pinholes and a small slide
were tried first and rejected as too fiddly); on the rear, right to left,
host USB-C, SH socket and the antenna (the user wanted every cable at the back;
rejected, the antenna alone on the left wall, better RF margin but off §11's
opposite-wall rule; accepted, the antenna ~20–40 mm from two cables and a USB
shell, and a flex antenna up to ~50 × 12 mm under the core/lid seam, which sits 5 mm higher all round since 2026-10-01; a raised rear-wall tab until then, rejected by the user for its stepped seam). Joints: core ↔ connector layer on M2
screws (a 44-contact joint should not come apart by accident); battery modules and
the lid on magnets with a keyed nesting lip, so cell access stays tool-less;
optional layers join the same way (a display swaps without tools).
**v0 review (2026-09-29)**: headers at chain (25, 20), slot (−5, 5), expansion
(0, −20) on every board, clear of the AA holder and of the antenna corner; a
separate base under the lowest layer covers its live tails in every configuration
(rejected: a slotted floor in every section, which leaves the tails reachable; a
loose tail cap); the core keeps full ESQ parts although its sockets face up unused
(one part family, and a future optional layer can tap the chain or slot bus;
rejected a TSW pins-only strip, a second family with unverified post length); the
core ↔ connector M2 screws go in from the top through the core board, so they also
hold it down (rejected: from below, through the side walls).
**Case (2026-09-29)**: FDM in ASA on the user's Bambu Lab H2S and Prusa CORE One,
one piece per module (both beds take a 233 mm module), M2 heat-set brass inserts.
The earlier SLA-resin premise (and the captive nuts chosen for it the same day) was
wrong: the user has no resin printer. Rejected PETG (softer, creeps) and PLA
(softens on a sunny desk). **Magnets (2026-09-29)**: the user's 20 × 10 × 2 mm NdFeB blocks,
two per seam, flat in loose side-entry pockets on side-wall shelves (no glue, all
north up); a low holding force is accepted, the magnets only seat the lip.
Rejected: magnets everywhere (the core joint could be pulled apart by a cable),
printed snap latches (rejected as brittle when the case was assumed SLA resin; not revisited for ASA). A future radio connector layer puts
its antenna on the front wall, opposite the core's. The model is a script in
`mech/hub/` driving FreeCAD; outlines flow from it to KiCad.

The **palm rest** keeps the K860 silhouette but no longer houses cells, so its
height floor is no longer the AA holder. The **plate** is FR4, no copper.

### Row dish — flat boards, tilt and keycap profile

A stepped or curved plate over a flat PCB is not physically possible beyond about a
millimetre, because the MX switch body fixes plate-to-PCB distance.

Rejected **per-row board segments joined by flex cable** and **rigid-flex**.
Chosen: flat boards, dish from **independent per-module tilt** and a **sculpted
keycap profile**.


## 8. Known unknowns

Summarised here; [`open-questions.md`](open-questions.md) tracks each with its
resolution and phase.

- **The module controller's firmware**: framework, register map, and the update
  flow over its ROM I2C bootloader (F7; part decided, MSPM0G3505).
- **I2C through a USB 2.0 cable's twisted pair** at 400 kHz and 1 m (E16).
- **CC as `INT`** against e-marked cables and without looking like a USB source
  (E17); the slot power policy and its mis-plug loops (E18).
- **LED headroom** after the cable's drop, on battery (E19).
- **The battery chain**: the per-pack ideal diode, contact resistance per hop, the
  stacking header's exact part and the stack's mechanical joint (M10); the per-hop
  resistance is accepted at ~10 mΩ (E20).
- **Idle current** of the hub asleep with three key boards in scan-wait (E7). The
  datasheet estimate (2026-10-01, spec §4) is ~0.26 mA typ / ~0.47 mA worst, ~9 / ~5
  months per 4×AA pack. The cost of keeping slots powered in sleep dominates it: three
  TPS22950L at 44 µA each, through the LED converter at ~60–65 % light-load
  efficiency. The slot-VBUS TVS became a TVS0500 so that no part on the always-live
  LED rail has an unbounded leakage.
- **The hub tower**: layer enclosures, latching, the antenna's ≥10 mm from the
  other layers' copper (pull-back, RSSI), the whip's clamp, keying the top header
  against offset-by-one, the base, magnets and screw bosses (M11).
- **KTS1693 supply** for the one host port.
- Whether a hotswap socket, a reverse-mount LED window, a diode and stabiliser
  clearance coexist in one 19.05 mm cell, and whether glow through an opaque cap is
  legible.
- NKRO descriptor support over BLE on each host OS; nine BLE profiles across a
  power cycle.
- Driver temperature at full white on a 5 V rail.
- Real debounce behaviour of whichever encoder is stocked.

Resolved and still valid from rev 7: Zephyr's `is31fl3733` driver does bulk writes
(now relevant to the module controller only if it runs Zephyr); the power-path
ratings (LM66200, TPS22950, TLV757P 6.0 V abs-max; TPS3840 12 V). Rev 8's TPS2116,
TPS61023, logic boost, MAX17222 and pack bleeder results are history since rev 8.1.
New in rev 8.1: the E21 switchover sim (`tools/sim/e21_switchover.py`) and the E7
datasheet idle estimate (spec §4); the MDBT50Q `VBUS` pad vs the KTS1693 trip (E22).

The number row is locked at 6/3: 1–6 on `left`, 7–9 and 0 on `right`.
