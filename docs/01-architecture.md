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
- **The hub is a stack of layers**: optional layers (display…) / core (base board
  + vertical MCU board) / swappable connector layer / battery modules 1…N or a Qi2
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
    [CORE LAYER]  base board: power path, LED rail, TCA9548A, buttons, headers
                  + vertical MCU board (MDBT50Q, crystal, SWD) on the wall, J_MCU 2x25 right angle
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
in.** Plug wear, surges, ESD, reversed or Li-ion cells and encoder wear hit a
small board: USB port, comms, battery module, dial or expansion. The hub core and
key boards sit behind that protection.

Partitioning rules:

- **Anything medium-specific lives on the comms boards.** CC handling (the BAT54C
  and the pull-ups), the slot switch, the USB-C sockets and their ESD. A future
  medium replaces the comms boards and nothing else.
- **Anything that must reach the MCU without detour plugs into the hub core.** Host
  D+/D− crosses one cable (USB port board → hub core). The battery chain plugs into
  the hub core, where the undervoltage supervisor and the slide switch sit.

Rules that protect it from mistakes:

- **Every header pin count is unique.** `J_SLOT` 14 and `J_COMM` 10 keep the two
  comms populations apart; `J_DIAL` 5, `J_USB` 11 and `J_EXP` 15 are unchanged. The
  battery chain uses its own connector type (M10).
- **Nothing on a key board sources power**, so no two things on a link can fight
  over VBUS. The module side has no switch and no CC `Rd`.

## 2. Power domains

```
  PROTECTION (per battery module, xN, chained)
  --------------------------------------------
  2xAA --[TVS, bleeder]--[rev FET]--[OVP FET]--[PTC]--[ideal diode (1 uF in), ~ON <- PACK_EN]--> VBAT (chain)
     `--[BAT54]--> PACK_SENSE (chain) --> [hub] TPS3840PH18 (~1.9 V pack) --> slide switch --> PACK_EN

  USB AND AUX INPUT (hub)
  -----------------------
  host USB VBUS --[KTS1693 OVP 5.55-5.95 V, OCP latch ~2 A]--[TVS]--[LM66200 IN1]--+
  AUX_5V (chain header, Qi board later) ---------------------------[LM66200 IN2]------+-- VBUS_IN

  DOMAIN A: VSYS, 3.3 V regulated (hub)
  -------------------------------------
  VBUS_IN --[LDO 3.3 V]--> IN1 [priority mux] --> VSYS --> MDBT50Q VDD, TCA9548A, expansion I/O
  VBAT ----[logic boost]--> IN2

  DOMAIN B: LED rail, ~5.0 V on battery (E19), ~5 V on USB (hub)
  -------------------------------------------------------
  VBAT ----[boost 5.0 V, EN pulled up]--> IN2 [priority mux] --> LED RAIL --> expansion LDO (gated)
  VBUS_IN ------------------------------> IN1                        |
                                                   +-----------------+-----------------+
                                           slot switch (TPS22950L, latch-off), one per slot, on the hub-side comms board
                                                   |
  DOMAIN C: key board, per module
  -------------------------------
  cable VBUS --> IS31FL3733 VCC + LED anodes
             `--[LDO 3.3 V]--> module controller, driver VIO, link pull-ups
```

**Where the domains live.** The pack protection is on each battery module; host
VBUS protection is on the USB port board; domains A and B, the input OR and the
UVLO are on the hub core; each slot switch is on its hub-side comms board; domain C
is on each key board.

**Why VSYS is fed through an LDO and a mux on USB.** The nRF52840 `VDD` is rated
to 3.6 V. **Rev 2 OR-ed 5 V VBUS straight onto VSYS**, which would have destroyed
the MCU on the first plug-in. An LDO alone is not enough: an ideal-diode OR picks
the higher source, and a fresh alkaline pack near 3.3 V would keep supplying while
on USB. A priority mux disconnects the packs whenever VBUS is present.

**Why VSYS is regulated on battery too (rev 6).** Rev 5 fed VBAT straight into the
mux, so `VSYS` ran at 1.85–3.3 V and differed between modules. The nRF52840's
`VIH` is 0.7·`VDD` and its pin abs-max is `VDD` + 0.3 V, so a module on USB could
not read a 2.2 V module's TX, and a 3.3 V module over-drove a 1.9 V module's pins;
the wired link only worked with matched cells. A dedicated logic boost now takes
VBAT to 3.3 V on the mux's IN2, so every module's UART, I2C and `AINx` levels are
identical whatever the cells. With a fresh pack above 3.3 V the boost stays in
down mode and still regulates. The cost is the boost's ~1 µA quiescent current.

**Why the LED rail uses a priority mux, not an OR.** **Rev 3 OR-ed VBUS with the
4.7 V boost and assumed VBUS always wins.** USB only promises 4.75 V at the
receptacle; after the cable, the OVP FET and the switches, VBUS_IN can sit below
4.7 V under load, and an OR would quietly move the LED load onto the boost, which
draws from `VBAT`, so on USB the cells would carry it (rev 7 and earlier said "the
3.3 V LDO", which the topology does not do). A TPS2116 in priority mode keeps VBUS_IN
selected above its `PR1` threshold, 3.63–4.40 V with ~0.3 V of hysteresis from its
`ST` pin (E3, 2026-09-15). The threshold sits low on purpose: `VREF` is ±8 %, so rev 7's
~4.3 V nominal could reach 4.72 V and hand a compliant but weak port's LED load to the
cells. Below ~4.5 V the LEDs dim instead, which is the lesser failure. `ST` is low only
while IN2 is in use, so a resistor from `PR1` to `ST` adds the hysteresis the part
lacks without a GPIO, and a sagging source cannot hunt between inputs.


**Why only the host port has an integrated OVP switch (rev 8).** Every part behind
`VBUS_IN` is 6.0 V abs-max. A discrete comparator plus P-FET was designed and
simulated first (rev 4 and 2026-09-13): its comparator output is undefined for
~190 µs at power-up, the FET's gate–drain capacitance let a 20 V hot plug through,
and a source that jumped from 5 to 20 V while connected still put 16.8 V on the
output. The KTS1693 switches off in 100 ns and debounces turn-on for 0.7 ms. Rev 7
had five of them, one per inward USB-C socket. **In rev 8 power only flows inward
at the host port.** Link sockets carry the hub's own LED rail outward, and the key
modules' sockets have no `Rd`, so a USB-C source never turns on into them. A
legacy USB-A-to-C charger forcing 5 V into a link socket is ≤6 V; a
non-compliant >6 V source there reaches the TPS22950L or the key board's LDO and
driver behind only the SMF6.0A, the same residual risk rev 7 accepted on its
downstream link ports.

**Why the key boards run from the LED rail, not `VBUS_IN`.** The key boards need
power on battery too. The LED rail is the one rail that exists on both battery and
USB and already has the current capacity. The cost is that the LED boost runs
whenever the keyboard is on battery (rev 7 already kept it running: "Driver idle"
in the spec). Each key board makes its own 3.3 V with an LDO, so `VIO` is derived
from `VCC`'s own net and cannot come up first. On a collapse an LDO that blocks
reverse current can hold `VIO` above a falling `VCC`, so the rev 7 series
resistors at the driver stay.

**Why each slot has a latch-off switch.** A slot is a user-facing socket that
sources power. A shorted cable, a crushed plug or a phone plugged into a hub slot
must cost one slot, not the LED rail. The TPS22950L latches off above `IHCD`
1.2–1.9 A and stays off until `SLOT_EN` toggles; firmware keeps a slot on only
while its module answers (spec §6).

**Why the LED rail bypasses that path on USB.** At the USB default 500 mA, pushing
LED current through a 3.3 V LDO and back up through a 4.7 V boost yields about
270 mA of rail current for the whole keyboard, with the LDO burning ~0.75 W. A
direct VBUS feed onto the rail, muxed with the boost output, fixes both. The boost
stays enabled and idles while VBUS holds the rail above its setpoint, so neither
plug nor unplug collapses the rail.

**Why domain B is ~5.0 V on battery (E19, 2026-09-26; 4.7 V until rev 7).** The
driver's datasheet headroom is ≤400 mV sink at 672 mA and ≤200 mV source at 42 mA,
about 0.4 V at our 320 mA / 20 mA. The LED's maximum forward voltage at 20 mA is
4.1 V green and 4.0 V blue, so a max-bin die needs ~4.5 V at the driver. Rev 7's
4.7 V (4.63–4.87 V) left ~0.2 V with the driver on the same board; rev 8 puts ~1 m
of cable, a slot switch and two connectors in between (~0.1 V at 0.28 A), which left
~0.03 V worst case. The divider moves to 750 kΩ / 100 kΩ: 4.93–5.19 V, ≥0.33 V after
the cable, under the boost's 5.5 V OVP and the driver's 5.5 V maximum, for ~7 % more
cell power at the same brightness. **Rev 3 said blue and green run to about 3.6 V**;
that was closer to typical than maximum. On USB the rail is VBUS_IN, which on a
healthy port costs driver dissipation and on a weak one can leave a max-bin part
slightly under current.

**Why the driver is never power-gated.** Absolute maximum is "voltage at any input
pin, VCC + 0.3 V". Collapsing VCC while `VIO`, SDA and SCL still sit at 3.3 V puts
every logic pin above its ceiling. Idle is `SDB` low plus software shutdown, which
the datasheet rates at microamps. A side benefit: the 192 PWM registers survive
sleep, so the effect layer needs no reload-on-wake path.

**Why there is no I2C level translator.** Pin 39 is `VIO`, "input logic reference
voltage", and the datasheet's own application circuit ties it to the MCU rail while
the VCC group sits higher.


**The battery rules.** Seven hazards.

1. **No pack may reach another pack.** Every battery module feeds `VBAT` through
   its own ideal diode, which blocks reverse current, so a fresh pack never
   charges a depleted one, including an alkaline one. **This is why the chain needs
   an ideal diode per module** and why the rev 7 dual LM66200 could not simply be
   extended: it had two inputs. Nothing on the link side can back-feed `VBAT`.
2. **Reverse polarity.** A plain high-side ideal diode's body diode conducts with a
   reversed pack, dragging VSYS to about −2.4 V. A series reverse-blocking P-FET
   precedes the OR-ing, one per pack. The terminal TVS sits ahead of that FET, so it
   is bidirectional; a unidirectional part would forward-conduct into the reversed
   pack with nothing limiting the current.
3. **Overvoltage.** 14500 Li-ion cells fit AA holders, and two in a 2S holder make
   8.4 V. **Rev 2 had no protection here.** No integrated OVP switch goes below 4 V,
   so each pack gets a nano-power supervisor driving a second series P-FET. The
   supervisor's rated threshold is a falling edge with 200 mV hysteresis, so a 3.5 V
   part trips rising near 3.7 V: under `VDD`'s 3.9 V abs-max, above the freshest
   alkaline pack. A 9 V-standoff TVS guards the terminals without crowbarring a
   14500 pair. Lithium primaries (L91, ~3.66 V fresh per pack) are also excluded as
   unsupported, since they exceed `VDD`'s recommended maximum.
   **The supervisor is too slow to stop a step, so the FET must already be off when
   one arrives.** Rev 6 made it off by default with a gate-to-source capacitor, which
   works on a discharged board. **The 2026-09-15 simulation found the other case:**
   on a running pack that capacitor holds the FET on, and the pack node, a 1 µF input
   capacitor drained by microamps, keeps it charged for seconds after the cells come
   out. A 14500 pair swapped in during that time reached `VBAT` at 8.3 V, and swapping
   a single cell (5.6 V) would pass through the logic boost to `VDD`. A bleeder at the
   holder terminal (330 kΩ, 8.5 µA) empties the node in about half a second, faster
   than anyone can change a cell. The window scales with that node's capacitance, so
   each battery module keeps its ideal diode's input at 1 µF and the bulk sits on
   `VBAT` at the hub, after the OR. Rejected:
   a 100 kΩ bleeder (a 0.17 s window, but 28 µA per pack against a 6-month idle
   target) and a zener-driven fast turn-off clamp (closes the hole outright, but three
   more parts and an unsimulated circuit).
4. **Short circuit.** 2×NiMH will deliver amps, and there is a boost inductor
   downstream. PTC in each pack lead, hold ≥1 A. **Nothing in the path is a current
   limiter**, and the LM66200 has no limit of its own. A hard short pulls the pack
   below the UVLO, which opens the OR. A partial short between the LM66200's 2.5 A
   rating and the PTC's 3.5 A trip may sit there until the LM66200's thermal
   shutdown, because Eaton publishes no trip curve below 8 A. That band was accepted
   (E9, 2026-09-15): the part at risk is a battery module's ideal diode, only under an internal fault
   that has already damaged something, and the lower-trip PTCs push the pack path
   past its 300 mΩ budget. The USB side has the same shape: a KTS1693 latch stays fully
   on for its 5–10 ms debounce, so one short pulse passes; that too is accepted
   rather than trading the latch for a 200 ms retry loop. On the slot side, each
   slot's TPS22950L latches off above 1.2–1.9 A.
5. **Over-discharge.** Firmware enters system-off at ~2.05 V. As a backstop, a
   supervisor on the hub drives `PACK_EN`, the active-low `~ON` of every battery
   module's ideal diode, at ~1.9 V at the pack, so the ideal diodes double as the
   cutoff switch. On battery that removes supply from the hub and every key board
   together. The supervisor is fed from `PACK_SENSE`, a BAT54 from each pack node,
   so it survives its own cutoff (below), which is why a 1.8 V part gives a
   1.9 V pack threshold. **Rev 2 put the supervisor on boost EN
   alone**, which collapsed the driver's VCC under a live `VIO` and left the MCU
   draining the cells indefinitely.
6. **Pack load is not shared.** Ideal-diode OR-ing hands the whole load to the
   higher pack until the two equalise. **Rev 2 claimed two packs halve the
   C-rate.** Every per-pack part is sized for the whole keyboard's battery load
   (rev 8; one module's in rev 7), and battery lighting is capped at 250 mA on the
   rail for the whole keyboard, about 730 mA from one pack near UVLO. Adding battery
   modules adds runtime, not brightness.
   Two P-FETs at 1.9 V gate drive make a 150 mΩ series budget unreachable; the path
   is allowed 300 mΩ, about 0.2 V at worst case.

7. **The chain adds resistance (rev 8).** The pack path had ~4 mΩ of headroom under
   its 300 mΩ budget in rev 7, which did not count connector contacts. Every chain
   hop adds contact resistance on `VBAT` and GND, most for the pack farthest from
   the hub. Low-resistance chain contacts or a larger budget (lighting scales down
   earlier on a flat far pack) are decided with the contacts (E20, M10).

**`PACK_SENSE` and the supervisor (rev 8).** The supervisor that cuts the packs
off must survive the cutoff. Rev 7 powered it from both packs ahead of the OR
through a BAT54C. The chain keeps that: a BAT54 from each pack node onto a µA-level
`PACK_SENSE` net, which is the supervisor's supply and sense. Powered from `VBAT`
instead, it would lose its supply the instant it opened the ideal diodes, release
them, and oscillate.

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
| Legacy USB-A-to-C charger in a hub slot | 5 V forced into the slot output; the TPS22950L has no reverse current blocking, so it can back-feed the LED rail at ≤5.25 V; the TPS2116 blocks reverse current into its inputs | Benign; >6 V non-compliant sources are the accepted residual risk |
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

**Optional layers stack on top; the expansion board's JST-SH socket stays.**
Rejected **top header only** (no cabled accessories, ESD moves to every layer) and
**SH socket only** (add-ons dangle on cables). The shared bus costs one chip select
per SPI layer, so the number of CS lines caps how many SPI layers stack (X1).

**Core layer: horizontal base board + vertical MCU board on the wall** (the user's
idea). Rejected **a horizontal core with an antenna tab**: one board, but the
antenna's plane would be parallel to the metal layers right beside it and the
stack gets a tab; rejected **the whole core vertical**: the tallest layer and the
widest join, with the power path's heat rising past the MCU. Cost accepted: a
2.54 mm right-angle 2×25 join carrying ~40 MCU signals and USB D±.

### Battery — chainable 2×AA modules on the hub (rev 8)

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

### USB power — LDO + priority mux, LED rail direct, CC sensed

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

### Cells — alkaline and NiMH only, with OVP

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
carries the MDBT50Q-1MV2 or -U1MV2 on one land pattern with both keepouts. Raytac
restricts **21 of the 48 pads to low-frequency I/O**; the hub uses 37 of 47 pins
with 14 of 24 full-function pads, far from rev 7's 45 / 22 (spec §5). The 32.768 kHz
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
The core layer's MCU board stands on a wall with its antenna facing the room; a
future radio connector layer puts its antenna on the opposite wall, facing the
keyboard.

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
- **Idle current** of the hub asleep with three key boards in scan-wait (E7).
- **The hub tower**: layer enclosures, latching, the MCU board's distance from the
  other layers' metal (RSSI), the top expansion header's CS count (M11, X1).
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
ratings (TPS2116, LM66200, TPS22950, TLV757P 6.0 V abs-max; TPS3840 12 V; TPS61023
starts at ≤1.8 V); the hot cell swap closed in simulation by the pack bleeder; the
MAX17222 second-source margin; the logic boost divider.

The number row is locked at 6/3: 1–6 on `left`, 7–9 and 0 on `right`.
