# Architecture and decision record

Companion to [`../plans/keyboard.md`](../plans/keyboard.md), which is the
authoritative spec and owns every number. This document owns the *shape* of the
design and the *reasoning*: block diagrams, power and logic domains, hazard
analysis, and why each rejected alternative lost.

If a number appears in both, the spec wins.

**Rev 5**: each module splits into boards by failure mode (§1a). All three
modules share one core board, and the parts that wear out or get abused plug in on
small boards. Rev 4 moved the central to `left` and carried the numpad's link
through `right` in copper. Claims from earlier revisions now known to be wrong are
called out in place rather than quietly deleted. The 2026-09-15 Phase 3
calculations (spec §4, §5; `tools/sim/`) changed the reasoning in §2 and §5: a
hot-swap hole in the pack OVP, over-current behaviour on inward USB ports, the
LED-rail hand-over threshold and the driver's unplug resistors.

## 1. System shape

One central, two satellites, wired as a chain but electrically a star: both UART
pairs terminate on the central, and the middle module carries one of them in
copper.

```
  [left, central]                  [right satellite]                [numpad satellite]
   MDBT50Q, 6x7                     MDBT50Q, 6x9 + PEC11R dial       MDBT50Q, 5x4
   IS31FL3733, 4xAA                 IS31FL3733, 4xAA                 IS31FL3733, 4xAA
   host USB-C, CC sense             USB-C (DFU/power)                USB-C (DFU/power)
                                    MCU on pair 1 only
   UARTE0 <----- pair 1 ------------ UARTE0
   UARTE1 <----- pair 2 ------------ copper, no MCU contact -------- UARTE0

   2 spring pogo halves + rear USB  2 flat | 1 spring half         1 flat half + rear USB-C
   (pair 2 on SBU)                  2 rear USB-C
        |
   BLE or USB --> PC
```

**Both split transports are compiled in, and the choice is all-or-nothing.** ZMK
core keeps a single `active_transport` for the whole central and re-selects only
when that transport reports disconnected. Wired has the higher priority, and our
wired transport reports available only when every expected satellite has completed
a link handshake:

| State | Split transport | What transmits |
| --- | --- | --- |
| Both satellites linked, host on USB | wired | nothing |
| Both satellites linked, host on BLE | wired | `left` only |
| Any satellite unlinked | BLE for **both** | `left` and both satellites |

**Rev 2 of this document said "an uncabled module reverts to BLE and keeps
working" while the other stays wired.** Core cannot do that: there is one active
transport pointer, not one per peripheral. A second, subtler trap follows from the
fix. A cabled satellite chooses its own transport, and would sit on wired while the
central listens on BLE. So the central broadcasts an *all-present* flag over the
link, and a satellite's wired transport is available only while that flag is set.

Three things remain true regardless:

- **Only `left` talks to the PC.** `ZMK_USB` depends on the central role.
- **Satellites are never keyboards.** A satellite in a PC gets you a UF2
  bootloader and a power input, nothing that types.
- **Untethered deep sleep has a seam.** A sleeping satellite cannot wake a sleeping
  central over BLE. Cabled, a UART break does it. Accepted and documented.

## 1a. Board shape

Each module is the same set of boards around a module-specific key board, which
acts as the backplane:

```
                     [battery board] x1-2          [dial board]  (right only)
                            |  J_BAT (4)                 |  J_DIAL (5)
   [USB port board] --J_USB (11)-- [CORE] ==J_ROW (7), J_COL (13), J_LED (12), J_LINK (14)== [KEY BOARD]
     USB-C, CC, KTS1693,           MDBT50Q, power path,                                   sockets, LEDs,
     USBLC6                        buttons, expansion LDO,                                IS31FL3733,
                                   Tag-Connect                                            link routing,
                                     |  J_EXP (15)                                        ID resistor
                                   [expansion board]                                           |  J_LB (9) / J_LBD (10), x1-2
                                     JST-SH 12, ESD                                       [link board]
                                                                                            USB-C link, TPD6E05U06,
                                                                                            upstream: KTS1693
                                                                                            downstream: TPS22950L
                                                                                               |  J_SEAM (8)
                                                                                          [seam board]
                                                                                            pogo halves, ESD
```

**The principle is to put every failure mode on something cheap that plugs in.**
Plug wear, surges, ESD, reversed or Li-ion cells, pogo wear and encoder wear all
hit a small board: USB port, link, battery, seam, dial or expansion (P17, 2026-09-15). The core and key board
sit behind that protection. The core also carries the parts that are hardest to
rework (the MDBT50Q and the power path), and it is identical on every module. So a
spare core fixes any module, and swapping cores between modules is a fault-finding
step.

Two partitioning rules keep the small boards to one design each:

- **Anything module-specific is key-board copper.** Link pinout mirroring, pair 1
  versus pair 2, which link port sources VBUS, `right`'s pair-2 passthrough. The
  link board PCB is therefore identical at all four link positions. Since rev 7 it
  has two populations, upstream (KTS1693) and downstream (none), on headers with
  different pin counts, so neither can be fitted in the other's position.
- **Anything that must reach the MCU without detour plugs into the core.** Host
  D+/D− crosses one cable (USB port board → core), not two. The battery boards
  plug into the core, where the pack OR lives.

Two more rules protect it from mistakes:

- **Every header pin count is unique**, except the two identical battery headers.
  A cable cannot reach the wrong header, so there is no mis-plug case to analyse
  for internal cables.
- **A module ID resistor on the key board** is read by the core at boot. A core
  flashed for another module enters a safe mode rather than driving link pins
  wired for a different role.

## 2. Power domains

Four domains per board, plus a protection chain ahead of them. The boundaries are
most of the electrical design.

```
  PROTECTION
  ----------
  pack A, 2xAA --[TVS, bleeder]--[rev FET]--[OVP FET]--[PTC]--> LM66200 IN1 (1 uF)
  pack B, 2xAA --[TVS, bleeder]--[rev FET]--[OVP FET]--[PTC]--> LM66200 IN2 (1 uF)   OR-ed, never paralleled
                                                          |  ON <- TPS3840PH18 (~1.9 V pack)
                                                        VBAT

  USB INPUT
  ---------
  local USB VBUS --[KTS1693 OVP 5.55-5.95 V, OCP latch ~2 A]--[TVS]--[ideal diode]--+
  upstream link VBUS ----[KTS1693, same OVP and OCP]--[ideal diode, inward]--+-- VBUS_IN

  DOMAIN A: VSYS, 3.3 V regulated (rev 6)
  ---------------------------------------
  VBUS_IN --[LDO 3.3 V]--------------> IN1 [priority mux] --> VSYS --> MDBT50Q VDD
  VBAT ----[logic boost 3.3 V]-------> IN2                         +--> matrix, encoder
            (TPS61099DRV, always on)                               +--> LED driver VIO

  DOMAIN B: LED rail, 4.7 V on battery, ~5 V on USB
  -------------------------------------------------
  VBAT ----[boost 4.7 V, EN pulled up]--> IN2 [priority mux] --+
  VBUS_IN ------------------------------> IN1 (above 3.6-4.4 V,  +--> IS31FL3733 VCC + anodes
                                              hysteresis via ST)

  DOMAIN C: expansion 3V3, gated
  ------------------------------
  LED rail --[LDO, EN from MCU]--> expansion pin 2 (150 mA budget; on a satellite it loads the link chain)

  left only:  VBUS_IN --[latch-off ILIM switch, EN after pair-1 handshake]--[TVS]--> link port + seam pins
  right only: VBUS_IN --[latch-off ILIM switch, EN while pair2_up from left]--[TVS]--> numpad port + seam pins
              (TPS22950L on the downstream link board, no reverse blocking; no KTS1693 there since rev 7)
```

**Where the domains live since rev 5.** The protection chain is on the battery
board (packs) and on the USB port and link boards (VBUS). Domains A–C and the
OR-ing are on the core. The LED driver is on the key board. The downstream link
switch is on the downstream link board since P14 (2026-09-15; it was on the key
board, but the L variant ships only as a 0.4 mm WCSP), fed from `VBUS_IN` over
`J_LBD` on both `left` and `right`; rev 4 fed `left`'s from local VBUS, which on
`left` is the same source minus one ideal-diode drop.

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

**Why every USB-C socket has an integrated OVP switch.** Every part behind VBUS is
6.0 V abs-max. A discrete comparator plus P-FET was designed and simulated first: its
comparator output is undefined for ~190 µs at power-up, so turn-on needed a delay
network; the FET's own gate–drain capacitance let a 20 V hot plug through until a gate
capacitor was added; and a source that jumped from 5 to 20 V while connected still put
16.8 V on the output, because cable inductance charges the bulk capacitor within
microseconds and no µs-scale comparator catches it. The KTS1693 switches off in 100 ns,
debounces turn-on for 0.7 ms internally and carries its own surge and ESD ratings. The
cost is a 0.4 mm-pitch WLCSP that must be placed by the assembler. Since rev 5 it
sits only on the small USB port and upstream link boards, so a failed one is a board
swap. **Rev 5 and 6 also put it on downstream link ports**, where power flows
backwards through it; its datasheet covers that only at start-up, not a sustained
`OUT` > `IN` with the far end shorted or the part tripped. Rev 7 removes it there.
A port with no CC cannot negotiate above 5 V, and a non-compliant >6 V source on a
downstream socket is the accepted residual risk. Rev 7 also said the downstream
TPS22950L blocks reverse current; **it does not** (TI SLVSFJ2B Table 5: RCB only on
the TPS22950 and TPS22950C). That was accepted on 2026-09-15: satellites feed link
VBUS only through inward-only ideal diodes, so only a foreign supply in a downstream
socket can backfeed, and it stops at the core's LM66200, which blocks reverse
current into the local port (spec §4). The same day the switch moved from the key
board to the downstream link board (P14), because the L variant is sold only as a
0.4 mm WCSP.

**Why the LED rail bypasses that path on USB.** At the USB default 500 mA, pushing
LED current through a 3.3 V LDO and back up through a 4.7 V boost yields about
270 mA of rail current for the whole keyboard, with the LDO burning ~0.75 W. A
direct VBUS feed onto the rail, muxed with the boost output, fixes both. The boost
stays enabled and idles while VBUS holds the rail above its setpoint, so neither
plug nor unplug collapses the rail.

**Why domain B is 4.7 V on battery.** The driver's datasheet headroom is ≤400 mV
sink at 672 mA and ≤200 mV source at 42 mA, about 0.4 V at our 320 mA / 20 mA. The
LED's maximum forward voltage at 20 mA is 4.1 V green and 4.0 V blue, which leaves
~0.2 V on battery. **Rev 3 said blue and green run to about 3.6 V**; that was
closer to typical than maximum. On USB the rail is VBUS_IN, which on a healthy port
costs driver dissipation and on a weak one can leave a max-bin part slightly under
current.

**Why the driver is never power-gated.** Absolute maximum is "voltage at any input
pin, VCC + 0.3 V". Collapsing VCC while `VIO`, SDA and SCL still sit at VSYS puts
every logic pin above its ceiling. Idle is `SDB` low plus software shutdown, which
the datasheet rates at microamps. A side benefit: the 192 PWM registers survive
sleep, so the effect layer needs no reload-on-wake path.

**Why there is no I2C level translator.** Pin 39 is `VIO`, "input logic reference
voltage", and the datasheet's own application circuit ties it to the MCU rail while
the VCC group sits higher.

**The battery rules.** Six hazards.

1. **No pack may reach another pack.** Link VBUS enters every satellite only through
   an inward-only ideal diode, and `VBUS_IN` is only ever USB-derived, so no pack
   ever drives a link. The downstream switches (`left` to `right`, `right` to
   `numpad`) do **not** block reverse current; that is safe only because nothing on
   our side can drive their outputs (§2, "Why every USB-C socket").
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
   the core keeps its bulk on `VBAT`, after the OR, not on the pack inputs. Rejected:
   a 100 kΩ bleeder (a 0.17 s window, but 28 µA per pack against a 6-month idle
   target) and a zener-driven fast turn-off clamp (closes the hole outright, but three
   more parts and an unsimulated circuit).
4. **Short circuit.** 2×NiMH will deliver amps, and there is a boost inductor
   downstream. PTC in each pack lead, hold ≥1 A. **Nothing in the path is a current
   limiter**, and the LM66200 has no limit of its own. A hard short pulls the pack
   below the UVLO, which opens the OR. A partial short between the LM66200's 2.5 A
   rating and the PTC's 3.5 A trip may sit there until the LM66200's thermal
   shutdown, because Eaton publishes no trip curve below 8 A. That band was accepted
   (E9, 2026-09-15): the board at risk is the core, only under an internal fault
   that has already damaged something, and the lower-trip PTCs push the pack path
   past its 300 mΩ budget. The USB side has the same shape: a KTS1693 latch stays fully
   on for its 5–10 ms debounce, so one short pulse passes; that too is accepted
   rather than trading the latch for a 200 ms retry loop. Upstream link ports now
   latch like local ports, because a legacy 5 V charger in one had no limit at all.
5. **Over-discharge.** Firmware enters system-off at ~2.05 V. As a backstop, a
   supervisor disables the LM66200 pack OR through its `ON` pin at ~1.9 V at the
   pack, so the OR doubles as the cutoff switch. On battery that removes supply from
   MCU, `VIO` and boost together. The supervisor is fed from both packs through a
   Schottky pair so it survives its own cutoff, which is why a 1.8 V part gives a
   1.9 V pack threshold. **Rev 2 put the supervisor on boost EN
   alone**, which collapsed the driver's VCC under a live `VIO` and left the MCU
   draining the cells indefinitely.
6. **Pack load is not shared.** Ideal-diode OR-ing hands the whole load to the
   higher pack until the two equalise. **Rev 2 claimed two packs halve the
   C-rate.** Every per-pack part is sized for the full module load, and battery
   lighting is capped at 250 mA on the rail, about 730 mA from one pack near UVLO.
   Two P-FETs at 1.9 V gate drive make a 150 mΩ series budget unreachable; the path
   is allowed 300 mΩ, about 0.2 V at worst case.

**VBUS must reach the module's `VBUS` pad directly**, not only through the power
path. The USB regulator and attach detection both depend on it.

## 3. Logic domains and crossings

| Signal group | Domain | Crossing |
| --- | --- | --- |
| Key matrix, encoder, buttons | VSYS | none |
| LED matrix CS/SW, anodes | LED rail | none |
| Driver I2C and `SDB` | VSYS, referenced by `VIO` | **none needed**, `VIO` ties to VSYS; series resistors at the driver on `VIO`, SDA, SCL and `SDB` for the live-unplug case only |
| Link UART, incl. detect and wake | VSYS to VSYS across cable or pogo | 470 Ω series at each MCU pin + ESD clamps at every connector |
| Pair 2 through `right` | numpad VSYS to `left` VSYS; `right`'s rails not involved | ESD on `right`'s two link boards and two seam boards, key-board copper only, never on a core connector, no MCU pin, supply-less ESD arrays so an unpowered `right` does not clamp |
| Internal cables (rev 5) | same domain at both ends | none: not an entry point; header pin counts are unique so a cable cannot land on the wrong header |
| Host CC sense | 0.25–2.04 V into `AINx` | series R + ESD |
| Expansion I2C/SPI | VSYS | none on our side; attached device may need its own |

There is no mandatory level translator anywhere on the board.

## 4. The link

Two UART pairs, both ending on `left`. Pair 1 reaches `right`'s MCU. Pair 2 reaches
the numpad's MCU, and on `right`'s board it is only copper between the two seam
walls and the two rear ports.

| Link | Nets | Seam | Rear cable |
| --- | --- | --- | --- |
| `left`–`right` | GND, VBUS, TX1, RX1, `P2_DN`, `P2_UP` | 6 contacts, pins on `left` | passive full-featured USB-C, pair 2 on SBU |
| `right`–`numpad` | GND, VBUS, `P2_DN`, `P2_UP` | 4 contacts, pins on `right` | any USB 2.0 data cable |

**Why copper and not a relay.** See the decision record. In short: no firmware in
the numpad's path, and a numpad break wakes `left` directly. The price is paid in
this section: SBU, orientation, a second pogo pair and a VBUS flag.

**Why pogo in the seam.** A USB-C plug and its strain relief need 10–25 mm of
clearance; the seam budget is about 6 mm. Rear-facing jumper cables would work, but
visible loops behind the seams break the silhouette the whole project is about.
The seam uses SAMZO magnetic pogo pairs: a spring half (`PR5L3715-4P-C-H`) upstream
and a flat half (`PR5L2820-4P-C-F`) downstream, so a detached numpad exposes only
flat contacts and a detached `right` exposes flat contacts plus unpowered pins. Both
halves are vertical through-hole parts, so each sits on a small seam board
standing at the seam wall, cabled to the link board on that side. Their polarised magnets align, add retention and repel a
reversed join. The busier seam uses two 4-contact pairs because larger sizes are
drawn but not stocked. Rejected **plain ENIG pads**, which wear through; **a
hard-gold board finish**, which JLCPCB offers only on edge fingers; and **SMD
target discs against separate spring pins**, which rev 4 briefly specified on the
mistaken belief that the SAMZO part was a right-angle spring connector.

**Why pair 2 rides SBU, and what that costs.** A USB 2.0 cable has one data pair,
already used by pair 1. The only other signal wires in a passive USB-C cable are
SBU1 and SBU2, which only full-featured cables carry. Unlike D+/D−, SBU has one pin
per plug side, so it cannot be tied A-to-B to make orientation irrelevant: tying
would short `P2_DN` to `P2_UP`. So:

- *Orientation*: `left` idles both pair-2 pins as pulled-down inputs. The numpad's
  weak TX pull-up lifts exactly one; that one becomes RX, and UARTE1 takes the
  matching pinctrl state. Re-detected on every link-up.
- *Both high*: the two nets are shorted, which happens when a flipped rear cable
  sits in parallel with a joined seam. `left` drives neither and asks for the cable
  to be removed. Nothing pings, so the numpad never drives either.
- *Wrong cable*: a USB 2.0 cable links `right` and silently leaves pair 2 open, so
  the split falls to BLE. `left` can see that combination (pair 1 up, numpad on BLE,
  pair 2 silent) and say so.
- *Active cables*: need VCONN, which a CC-less link never supplies. Unsupported.

**Why wake and detect ride the UART.** Rev 2 budgeted separate wake and
cable-detect GPIOs, **but the link had no conductor for them**. Rather than use the
CC wire, which would put a foreign charger's Rp onto a GPIO, both functions live on
the RX pin:

- *Detect*: `left`'s RX pins have ≥100 kΩ pull-downs; a satellite's weak TX pull-up
  lifts them.
- *Handshake*: `left` sends `PING(nonce)`; a satellite answers `PONG(sat_id,
  nonce)`. A bare echo means loopback and is rejected. The source id comes from
  `sat_id`, not the pair. A `sat_id` already present on the other pair is rejected.
- *Speak when spoken to*: a satellite never drives TX until it has heard a valid
  `PING`, so a cable between two satellites has no driver on either line.
- *Hysteresis*: drop to BLE after ~300 ms of loss, which absorbs pogo bounce;
  return to wired only after ~2 s all-present and ~1 s with no key held, so a
  switch never lands mid-chord. Held keys from a lost source are released.
- *Wake*: `left` parks both UARTEs after idle and arms `SENSE` on each RX pin; a
  satellite sends a break. The numpad's break crosses `right` in copper, so a
  sleeping `right` is not in the wake path.

**Why the handshake gates VBUS, and why `right` needs a flag.** Link VBUS is
sourced downstream, so no switch may push 5 V into the wrong thing. RX-high alone
is fooled by a BC1.2 wall charger, which shorts D+ to D− and loops our own TX back.
The handshake is cheap and makes that case, laptops, charge-only cables and bare
seam pins all inert. `left`'s switch follows the pair-1 handshake. `right`'s
numpad-port switch cannot: pair 2 never touches `right`'s MCU. So `left` sends
`LINK_STATUS(all_present, pair2_up)` over pair 1, and `right` enables that switch
only while `pair2_up` is set and fresh.

**Cable requirement.** `right`–`numpad` needs the USB 2.0 pair. **Rev 2 said
charge-only cables work**; they usually have no D+/D− at all. `left`–`right` needs
a passive full-featured cable.

## 5. Mis-plug hazard analysis

Every module has at least two USB-C sockets plus seam contacts. Every combination
must be inert rather than damaging. A 470 Ω series resistor at every MCU UART pin
(not at the connectors) keeps two drivers fighting through a mis-plug under 3.5 mA,
which several rows rely on.

| Plugged in | What happens | Verdict |
| --- | --- | --- |
| Charger into any upstream port (`right`'s upstream, `numpad`) | No CC resistors, so the charger never enables VBUS | Inert |
| Charger into `left`'s port or `right`'s downstream port | No CC, charger stays off; if it shorts D+/D− (BC1.2), the loopback fails the handshake, or on `right`'s downstream port the short joins `P2_DN` to `P2_UP` with nothing pulling either high. VBUS stays off | Inert |
| Legacy USB-A-to-C into an upstream port | 5 V enters through the input OVP and the inward diode, then the LDO + mux; a faulty high-voltage source is blocked like on a local port, and since 2026-09-15 an over-current latches there too | Benign |
| Legacy USB-A-to-C into a downstream port | No handshake, so the switch is off, but it has no reverse blocking: 5 V can backfeed `VBUS_IN`, and the core's LM66200 stops it at the local port. Downstream boards have no OVP since rev 7, so a faulty >6 V source reaches the switch behind only the SMF6.0A | Benign; >6 V is an accepted risk |
| PC into any link port | Host needs CC; PC D+/D− pull-downs hold RX low, SBU is undriven without alt-mode negotiation | Inert |
| Charge-only cable between modules | No UART pair, no handshake, no VBUS; split runs on BLE | Inert |
| USB 2.0 cable between `left` and `right` | Pair 1 links, pair 2 open; split on BLE, `left` flags the cable | Works on BLE |
| Active USB-C cable between `left` and `right` | No VCONN, cable electronics unpowered; at worst nothing links | Inert |
| Flipped `left`–`right` cable, seam open | `left` detects orientation from the numpad's pull-up | Works |
| Flipped `left`–`right` cable **and** joined seam | Pair 2 nets shorted; both pins read high, `left` drives neither, nobody pings the numpad | Inert, flagged |
| Straight `left`–`right` cable and joined seam | Parallel paths agree | Works |
| Link between two battery-powered modules | Switches enable only if the source board is on USB; otherwise each runs on its own cells | Correct by design |
| Satellite USB into a PC | UF2 bootloader, or nothing. `ZMK_USB` needs central role | Never types |
| Satellite on a charger, link cable to a laptop | Upstream link VBUS is inward-only; `VBUS` pad and expansion 5 V from the local port only | Inert |
| Link cable into a satellite's own USB port | Sees 5 V only after a handshake, which cannot happen through that port | Inert |
| Module offered up to its neighbour reversed | The pogo halves' polarised magnets repel; no contact is made | Inert |
| Metal object across `left`'s or `right`'s exposed seam pins | Switch off until handshake; pair-2 pins on `left` are pulled-down inputs until a numpad is detected | Inert |
| Numpad cabled into `right`'s upstream port | Two satellite pinouts; both TX weak pull-ups, nobody pings | Inert |
| Numpad cabled straight into `left`'s port | Handshakes on pair 1 as `sat_id` numpad; `right` absent, split on BLE | Works on BLE |
| `left` cabled into `right`'s downstream port | Pair 1 lands on `P2_DN`/`P2_UP`. Floating unless a numpad is on `right`'s seam, in which case the numpad handshakes on pair 1. if that handshake enables `left`'s switch, its VBUS backfeeds `right` through the downstream switch (no reverse blocking) into `VBUS_IN`, which the LM66200 keeps off `right`'s local port | Inert, or works on BLE |
| `right`'s two rear ports cabled together, seam joined | `right`'s own UART loops onto pair 2; `left`'s pair-1 and pair-2 TX fight through series R; `right` answers on both pairs, the duplicate `sat_id` is rejected. `right`'s downstream VBUS stays off (no numpad handshake), and could only loop back through its own inward diode anyway | Inert |
| `right` powered off, `left` and numpad linked through it | Pair 2 is copper with supply-less clamps; `right`'s rails are not in the path | Numpad link unaffected; split on BLE without `right` |
| Core moved to another module without reflashing | Module ID mismatch: safe mode, no matrix scan, link pins undriven, link VBUS switch off | Inert, flagged |
| `right`'s two link-board cables swapped | Cut too short to reach, and the upstream (9-pin) and downstream (10-pin) headers do not mate with each other's cable (rev 7) | Cannot happen |
| Key-board lighting cable pulled while powered | Driver VCC and `VIO` break in no defined order; may exceed "VCC + 0.3 V"; series resistors on `VIO`/SDA/SCL/`SDB` at the driver limit the clamp current (SDA/SCL are also bounded by the pull-ups, since the bus only rises through them) | Against the service rule, but designed to survive; tested |

## 6. Decision record

### Board partition — by failure mode, shared core

Rejected **one main PCB per module** (rev 4 and earlier): fewest parts and no
cables, but the KTS1693 WLCSP sits behind every USB-C socket on a board that also
carries 40–52 LEDs and an MCU module. A worn socket or a surge is then a scrapped
assembled board for anyone without hot-air rework of a 0.4 mm-pitch part.

Rejected **a core stacked under the key board on mezzanine connectors**: no cables,
but key-board copper would sit over the antenna, and fine-pitch board-to-board
connectors are not hand-solderable.

Rejected **one I/O board per module carrying all its sockets**: fewer boards, but a
worn socket scraps its neighbours. `right`'s two link ports also sit at opposite
ends, so one board would need a long span or long cables.

Rejected **the LED driver on the core**: it would make the key board passive, but
it puts 28 LED nets and 320 mA SW currents through a connector, for a part that
rarely fails.

Rejected **population variants of the link board per position on a shared
header**: it would drop routing from the key board, but a misfitted variant could
source link VBUS without the handshake gate. Rev 7 adopts exactly two populations
(upstream with KTS1693, downstream without) for a different reason, E13, and keys
them by header pin count so a misfit cannot be cabled.

Rejected **one large backplane connector**: a single ~50-contact connector puts
power, matrix and USB in one part that is not hand-solderable, and mis-plug safety
would rest on routing alone.

Chosen: core, key, USB port, link, seam, battery and dial boards, joined by
several small locking wire-to-board connectors split by function, with unique pin
counts. Costs accepted: 9 PCB designs instead of 3 + seam; a pin budget set by the
union (45 of 47); ~0.8 m of internal cable in pair 2's budget (200 → 250 pF); host
D+/D− over one internal cable; series resistors on the driver's `VIO`/SDA/SCL/`SDB` so
a live lighting-cable unplug is survivable rather than only prohibited; a core placement constrained by the antenna in every case.

### Central — `left`

Rejected **central on `right`** (rev 3), superseded by a design decision to keep
everything host- and radio-facing on one outer module. A side benefit: rev 3 put
the only host radio in the centre module between two cases, the worst RF position.

Chosen: `left` owns the host USB-C port, host BLE, the split central role and the
BLE split connections. The radio moves to an outer edge. `right` becomes a
peripheral, so the dial's sensor events cross the split before reaching the
profile and volume behaviors.

### Numpad link through `right` — copper passthrough

Rejected **firmware relay**: `right` terminates the numpad's UART and forwards its
frames to `left` on pair 1, tagged by source. Every link stays at 4 nets, any USB
2.0 data cable works in any orientation, and `right` gates the numpad's VBUS from
its own handshake. It lost on putting custom, non-ZMK relay code (buffering, flow
control, command forwarding) in the numpad's path, and on a two-step wake
(numpad → `right` → `left`).

Chosen: pair 2 runs across `right` as copper. `left` runs two UARTs, the numpad's
break wakes `left` directly, and `right` needs one UART, which eases the tightest
pin budget.

Costs accepted: a passive full-featured cable between `left` and `right`; pair 2 on
SBU, so run-time orientation detection and a shorted-pair state; a second pogo pair
on that seam; a `pair2_up` flag so `right` can gate the numpad's VBUS; the longest,
most heavily clamped line in the design; and a numpad that is wired only while
`right` is linked, which all-or-nothing makes moot.

One argument for copper turned out weaker than it looked: isolation from `right`'s
firmware. If `right` reboots, its own keys drop off the wired link and
all-or-nothing takes the whole split to BLE anyway. The relay stays the documented
fallback if pair 2's signal integrity or cable complaints force it.

### Inter-module transport — both, all-or-nothing

Rejected **per-source transport selection via a core patch**: it delivers the
per-link failover rev 2 described, but carries a rebase burden until upstream
accepts it.

Rejected **wired-sticky**, where a partially linked split stays wired: an uncabled
satellite goes silently dead, which is the worst possible failure for a keyboard.

Rejected **wired-only**: it deleted untethered operation.

Rejected **BLE-split-only**: entirely stock, but the radios stay on when cabled,
which was explicitly not wanted.

Rejected **single MCU with dumb satellites**: runs scan signals a metre off-board,
needs far more conductors than a USB-C cable has, and forecloses everything else.

Rejected **independent numpad behind a USB hub**: the numpad becomes a separate
HID device that cannot share layers.

Chosen because it keeps "radios off when linked" and "wireless", needs no core
patch, and sizes the core peripheral arrays correctly for free via
`MAX(BLE_PERIPHERAL_COUNT, WIRED_PERIPHERAL_COUNT)`. The cost is that unlinking one
satellite turns on both satellites' radios.

Remaining work: the wired transport is single-peripheral by construction, and
generalising it is effectively a rewrite of one file, delivered in our out-of-tree
module alongside the handshake, pair-2 orientation, all-present and `pair2_up`
flags, VBUS gating and break wake. On `left` it drives two UART instances.

### Link physical — seam pogo plus rear USB-C

Rejected **rear ports with short jumpers**: no extra parts, but visible cables.

Rejected **recessed USB-C in the seam**: hides the cable but forces the seam wider
than 6 mm.

Chosen: pogo for joined, USB-C for separated, same nets. It adds a part and a
compression tolerance that the joining hardware has to hold (0.7 mm working
compression, 25 gf per contact); the `left`–`right` seam needs two pogo pairs since
rev 4, and every seam needs a seam board. Accepted width is now about 468 mm with the
seams.

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
host port so firmware uses 1.5 A or 3 A when offered. `left` shares that budget
with both satellites through the chained link VBUS switches.

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

**Cross-module lighting.** The split protocol has no generic payload, so rev 2's
"no core patch" held only for single-module effects. Rejected **a core patch adding
a custom message**, which allows per-frame streaming at a rebase cost. Rejected
**descoping** to per-module lighting, which would move the profile indicator.
Chosen: tunnel `(command, argument)` through `INVOKE_BEHAVIOR`; satellites render
effects locally, synchronised by effect id and start tick.

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

### MCU — same pre-certified module on all three boards

Rejected **bare nRF52840 with a PCB antenna**, **socketed nice!nano**, **nRF52832
on satellites**, and **non-radio MCU on satellites**. Chosen: one part number
everywhere, and since rev 5 one core board everywhere.

The nice!nano lost because it brings out too few pins for a 6×9 matrix plus two
UARTs, LEDs and expansion. It was also a second MCU part number. The rev 5 core
board is a plug-in controller too, but it brings out every pin the union of the
three modules needs and uses the same MDBT50Q, so neither objection applies.

Raytac restricts **21 of the 48 pads to low-frequency I/O**, so pin assignment was
an explicit Phase 3 activity with a pin-class column (spec §5, 2026-09-15). It fits
with 2 full-function pads spare: 24 are usable once the crystal and nRESET pads are
taken, not the 23 earlier revisions counted. The two NFC pads carry matrix rows,
because they leak between each other only when held at different levels, and rows
idle at the same level. The 32.768 kHz crystal is
**not** inside the module. The nRF52840's TWIM tops out at **400 kHz**, not the
1 MHz rev 2 assumed for the LED bus.

## 7. Mechanical

The hard problem is the **seams**. Three separate cases need two walls at each of
two seams, about 6 mm of dead space each in resin, and the pogo pairs and their
seam boards must fit inside that: two pairs on the `left`–`right` seam, one on
the other. Each seam board's cable exits inward to its link board.

**Rev 5 adds three placement problems.** The core must sit where its antenna end
overhangs no copper. Every internal cable needs a routed channel clear of switch
pins, sockets and LED holes. And the palm rest gets a tool-less battery door with
the battery boards behind it. Joining needs real alignment and retention, now also holding the pogo
compression within tolerance; the connectors' own magnets help but are not assumed
to be enough.

The **palm rest** is the defining silhouette feature and houses the cells. The
**height floor** is set by the AA holder, around 35 mm before the arc's vertical
component. The **plate** is FR4, so no antenna cutout is needed.

### Row dish — flat boards, tilt and keycap profile

A stepped or curved plate over a flat PCB is not physically possible beyond about a
millimetre, because the MX switch body fixes plate-to-PCB distance.

Rejected **per-row board segments joined by flex cable** and **rigid-flex**.
Chosen: flat boards, dish from **independent per-module tilt** and a **sculpted
keycap profile**.

## 8. Known unknowns

Summarised here; [`open-questions.md`](open-questions.md) tracks each with its
resolution and phase, and the spec's verification list carries the gates.

- **Idle current.** Unproven until measured with both UARTs parked and break wake
  working.
- **Pair 2 signal integrity**: budgeted at ~250 pF for 460 800 baud, including
  internal cables since rev 5; unproven until scoped through two 1 m cables.
- **Seam stack depth**: seam boards, their cable exits, both pogo housings and
  working compression inside the ~6 mm seam.
- **KTS1693 supply**: stock and a second source for a 0.4 mm WLCSP part used on
  every USB port and link board.
- **Interconnect**: the connector family's derated contact current, its European
  stock and premade cables; host USB over one internal cable.
- **Core placement** against the antenna keepout in all three cases.
- Max-Vf green and blue LEDs on a weak USB port may run slightly under set current.
- Whether a hotswap socket, a reverse-mount LED window, a diode and stabiliser
  clearance coexist in one 19.05 mm cell, and whether glow through an opaque cap is
  legible.
- Whether nine BLE profiles survive a power cycle once `BT_MAX_PAIRED` is raised.
- NKRO descriptor support over BLE on each host OS in use.
- Driver temperature at full white on a 5 V rail.
- Real debounce behaviour of whichever encoder is stocked.

Resolved:

- **A module can register a split transport.**
  `ZMK_SPLIT_TRANSPORT_CENTRAL_REGISTER` uses an iterable section gathered across
  the whole link. A ten-line stub transport in week one confirms the translation
  unit is not dropped.
- **Zephyr's `is31fl3733` driver does bulk writes**: `write_channels` is one I2C
  burst, and `is31fl3733_current_limit()` sets the global current register.
- **Satellite battery reporting works over wired.** Peripherals raise
  `BATTERY_EVENT` on any transport; the central's shared handler is gated only by
  the BLE-named `ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_FETCHING`.
- **Wired split stability.** Pinned ZMK commit, weekly canary against `main`.
- **A peripheral's encoder works.** `peripheral.c` forwards `zmk_sensor_event` as a
  `SENSOR_EVENT` over either transport, and `central.c` re-raises it.
- **Pair-2 orientation can be swapped at run time.** Zephyr's dynamic pinctrl
  (`pinctrl_update_states()`) plus UARTE PM suspend/resume re-applies the default
  state, and nRF pinctrl writes the UARTE `PSEL` registers.
- **Power-path ratings.** TPS2116, LM66200, TPS22950 and TLV757P are 6.0 V abs-max;
  TPS3840 is 12 V abs-max (10 V recommended); TPS61023 starts at ≤1.8 V input.
- **Phase 3 margins (2026-09-15).** `left`'s link chain is 425 mA at full white
  against a 1.2 A latch minimum (725 mA with two 150 mA expansion loads); the
  MAX17222 second-source boost has ~4.8× margin over logic peaks; the module-ID
  bands hold across tolerance; the nRF52840 pull-up is 11–16 kΩ; the logic boost
  divider was tightened because rev 7 understated its leakage error.
- **Hot cell swap** is closed in simulation by the pack bleeder; the bench test in
  the spec's verification list confirms it.

The number row is locked at 6/3: 1–6 on `left`, 7–9 and 0 on `right`.
