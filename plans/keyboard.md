# Split K860-alike — hardware + firmware spec

Three-piece mechanical keyboard styled on the Logitech ERGO K860. Modules: `left`
(alphas, central), `right` (alphas + arrows + nav + dial), `numpad`. Wired UART
between modules with BLE-split failover, BLE or USB to the host, per-key RGB,
9 host profiles, MX hotswap, 4×AA per module as two independent 2-cell packs.

Ends at gerbers + costed BOM + a ZMK config that builds. Nothing ordered without
sign-off.

**Rev 7**: the review items rev 6 left open. Four are decided: the downstream link
boards drop the KTS1693 and become a keyed variant, the core takes both Raytac
land patterns, the case comes from a large-plate print service, and the logic
boost is the adjustable TPS61099 in WSON. Datasheet checks set the OVP gate
τ at ≥25 ms and the LED-rail bulk at ~10 µF for the TPS2116's 8 µs switchover, so
the LED blanking ISR is gone. The TPS25947 is recorded as the leaded KTS1693
alternate. See §17.

**Rev 6**: findings from [`docs/03-review-rev5.md`](../docs/03-review-rev5.md)
folded in. The logic rail is regulated to 3.3 V on every module (a dedicated
boost on battery, the VBUS LDO on USB), so UART, I2C and analogue levels no longer
depend on cell state. The pack OVP FET is off by default and turns on slowly, so
a 14500 pair never reaches the core. Enable pins default on in hardware, the
module-ID read is ratiometric, and `left`'s pair-1 TX is undriven until detect.
Rev 6 and earlier changelogs are kept below §17.

## 1. Topology

```
               seam pogo, 6 nets            seam pogo, 4 nets
               or rear USB-C,               or rear USB-C,
               full-featured cable          USB 2.0 data cable
     [left] <==================== [right] <==================== [numpad]
     central   pair 1: right       peripheral  pair 2: numpad    peripheral
               pair 2: numpad  ----copper----> (no MCU contact)
        |
  USB-C host port
        |
  BLE or USB --> PC
```

- **`left` owns everything host- and radio-facing**: the host USB-C port, BLE to
  the host, the split central role and the BLE split connections. `right` and
  `numpad` are peripherals.
- **Two UART pairs, both terminating on `left`.** Pair 1 links `left` to `right`.
  Pair 2 links `left` to `numpad`, and `right` carries it seam to seam as plain
  copper with no connection to its own MCU. No module forwards another's traffic
  in firmware.
- **Inter-module: both transports compiled in, all-or-nothing.** ZMK's central
  holds **one** `active_transport` for every peripheral, so the split is either
  wholly wired or wholly BLE. Our wired transport reports available only when
  **every** expected satellite has completed the link handshake (§6); otherwise it
  reports `DISCONNECTED` and the core fails the whole split over to BLE.
- **Host: USB when cabled, else BLE.** Stock runtime choice.
- **Radios:** host on USB, both satellites linked → nothing transmits. Both linked,
  host over BLE → only `left` transmits. Any satellite unlinked → the whole split
  runs on BLE and every module with a link down transmits, including a satellite
  that is still cabled.
- **Physical link, two paths in parallel.** Joined modules link through a pogo
  connector in the seam wall; separated modules link over a rear USB-C cable.
  Both paths carry the same nets: six on the `left`–`right` seam, four on the
  `right`–`numpad` seam.
- **The numpad links over wires only when `right` is linked too**, because pair 2
  physically runs through `right`. All-or-nothing makes that moot in practice.
- Untethered operation works.
- **Every module is built from boards by failure mode** (§2a). The MCU and power
  path sit on a core board that all three modules share. The sockets, pogo halves,
  cells and encoder sit on small boards that plug in with cables. A worn or
  damaged part costs one small board, never an assembled keyboard PCB.

## 2. Per-module spec

| | left | right | numpad |
| --- | --- | --- | --- |
| Role | **central** | peripheral | peripheral |
| Keys (approx) | 40 | 52 | 17 |
| Matrix | 6×7 | 6×9 | 5×4 |
| MCU | MDBT50Q-1MV2, on the shared core board | same core board | same core board |
| Module ID strap (§2a) | `left` band | `right` band | `numpad` band |
| LED driver | IS31FL3733, on the key board | IS31FL3733, on the key board | IS31FL3733, on the key board |
| RGB LEDs / 64 max | 40 | 52 | 17 |
| UARTs used | 2 (pair 1 → `right`, pair 2 → `numpad`) | 1 (pair 1) | 1 (pair 2) |
| Link, rear USB-C | 1 link board, 6-net | 2 link boards: upstream 6-net, downstream 4-net | 1 link board, 4-net |
| Link, seam pogo | 1 seam board, 2 × 4P spring half | 1 seam board with 2 × 4P flat half (left wall), 1 seam board with 1 × 4P spring half (right wall) | 1 seam board, 1 × 4P flat half |
| Link VBUS | sourced, gated | inward from `left` through input OVP; sourced to `numpad`, gated | inward-only, through input OVP |
| Pair 2 | terminates | copper passthrough on the key board, no MCU connection | terminates |
| USB-C | 1 USB port board (host, CC sense) | 1 USB port board (DFU+power, CC sense) | 1 USB port board (DFU+power, CC sense) |
| Cells | 2 battery boards × 2 AA | 2 battery boards × 2 AA | 2 battery boards × 2 AA |
| Dial | — | dial board, PEC11R, 24 detents / 24 ppr | — |
| Expansion conn. | expansion board, cabled to core | same | same |
| SWD | test points + Tag-Connect footprint, on core | same | same |

Key counts firm only after Phase 1. Diodes `1N4148W` per key, `col2row`, so
ghosting and blocking are impossible regardless of how many keys are held.

## 2a. Boards

**The principle: every event that damages or wears something happens on a small
board you can swap.** Plug wear, surges, ESD, reversed or Li-ion cells, pogo wear
and encoder wear all land on boards that cost a few euros and plug in with cables.
The core board and key board sit behind that protection.

| Board | Design | Per keyboard | Carries | Assembly | Replaced when |
| --- | --- | --- | --- | --- | --- |
| **Core** | 1, shared by all modules | 3 | MDBT50Q-1MV2 or MDBT50Q-U1MV2 (land pattern and keepout for both, rev 7), 32.768 kHz crystal, 470 Ω UART series resistors, SWD pads + Tag-Connect TC2030-NL footprint, reset and bootloader tactiles, slide power switch, pack OR + UVLO (LM66200, TPS3840PH18, BAT54C), `VBUS_IN` OR, logic LDO (from VBUS), logic boost (from VBAT, TPS61099DRV set to 3.3 V, or MAX17222 on a second footprint), VSYS priority mux, LED boost, LED-rail mux, expansion LDO + 15-pin `J_EXP` header to the expansion board (P17, 2026-09-15), battery sense, module-ID pull-up, test points | assembler | MCU or power path fault; swappable between modules for fault finding |
| **Key board** | 3, one per module | 3 | hotswap sockets, diodes, RGB LEDs, IS31FL3733, pair-2 copper (`right`), link-net routing and pinout mirroring, module-ID resistor, backplane connectors | assembler | rarely; sockets and LEDs are hand-reworkable |
| **USB port board** | 1 | 3 | USB-C receptacle, 2 × 5.1 kΩ CC, KTS1693 (local `ISET`), OVLO divider, TVS2200 footprint, SMF6.0A, USBLC6-2SC6, TVS2200 on CC1 and CC2; GCT USB4085 through-hole receptacle (2026-09-14) | assembler | socket worn, surge, OVP latched and not recovering |
| **Link board, upstream** | 1 | 2 (`right` upstream, `numpad`) | USB-C link receptacle (A6=B6, A7=B7 tied, no CC), KTS1693 (`ISET` 4.99 kΩ, as the local port since E9, 2026-09-15), OVLO divider, SMF6.0A, TPD6E05U06, junction of the rear port and the seam board; **9-pin** `J_LB` | assembler | socket worn, surge |
| **Link board, downstream** (rev 7) | 1 | 2 (`left`, `right` downstream) | same PCB with **no KTS1693** (1206 0 Ω jumper across its IN/OUT, 2026-09-14), no OVLO divider, no `ACOK`; SMF6.0A and ESD kept; **link VBUS switch TPS22950L (YBH WCSP) + `ILIM` 624 Ω (`IHCD` 1.2–1.9 A, 2026-09-15) between `J_LBD`'s VBUS pins and the port, `ON` from `LINK_SW_EN` on `J_LBD` pin 6** (P14, 2026-09-15; was on the key board); **10-pin** `J_LBD`. Both headers have footprints on the one PCB; the populations are KiCad design variants `upstream` (default) and `downstream` | assembler | socket worn, surge |
| **Seam board** | 1 | 4 | 1 or 2 pogo halves (spring or flat as fitted), TPD4E05U06 per pair (channel 1 on the pair's signals, channel 2 unused), nothing on VBUS, side-entry `J_SEAM`; **1.2 mm thick** so the spring half's 1.50 mm tails protrude. Populations are KiCad design variants per position, `left` (default), `right-left`, `right-right`, `numpad` (2026-09-14) | assembler (ESD array), pogo halves by hand | pogo wear |
| **Battery board** | 1 | 6 | one 2×AA holder, SMF4L9.0CA, reverse-block and OVP AO3415A with gate clamps, TPS3840PL35 + RC, PTC, DNP OVP bypass, 330 kΩ `CELL+` bleeder (R806, hot-swap fix, 2026-09-15) | **hand-solderable** (SOT-23, SOD-123FL, 0805, 1206) **except the PTC**, which is reflowed or hot-air soldered (Eaton discourages hand soldering it; decided 2026-09-14) | reversed cells, 14500s, terminal ESD, corroded holder |
| **Dial board** | 1 | 1 (`right`) | PEC11R-42xxx-S0024 (shaft TBD in Phase 1) with its mounting lugs to GND, push-switch diode (Diodes Inc 1N4148W-7-F), 1 kΩ + 10 nF low-pass on A and B (pull-ups stay on the core), DNP TPD4E1U06DBV ESD footprint on the encoder pins; 5-pin `J_DIAL` (2026-09-15) | **hand-solderable**; Bourns rates the PEC11R for wave soldering (260 °C, 3 s) and calls hand soldering "not recommended": accepted, the build guide gives a temperature-controlled iron, ≤3 s per pin, no reheating (2026-09-15) | encoder worn |
| **Expansion board** (P17, 2026-09-15) | 1 | 3 | 12-pin JST-SH expansion connector at the case wall, its ESD arrays, 15-pin `J_EXP` header to the core; JST SM12B-SRSS-TB side entry, TPD4E05U06 + TPD6E05U06 on all ten non-GND pins, 100 nF on each rail, refs 10xx (2026-09-15); board size still to set | assembler (ESD arrays) | socket worn, ESD hit |

Rules that fall out of the partition:

- **The core board is identical on all three modules, and so is its BOM.** It
  brings out the union of what any module needs (§5). A module leaves unused lines
  unconnected on its key board. One spare core fixes any module, and swapping cores
  between modules is a valid fault-finding step once the swapped core is reflashed.
- **One USB port board design, and one link board PCB in two keyed populations
  (rev 7).** Upstream positions (`right` upstream, `numpad`) take VBUS inward and
  carry the KTS1693. Downstream positions (`left`, `right` downstream) source VBUS
  outward and do not: the KTS1693 cannot be shown to tolerate sustained `OUT` >
  `IN` there (§4, "Downstream ports"). Only the downstream population fits the
  TPS22950L (P14, 2026-09-15).
  The two populations use **different header pin counts** (`J_LB` 9, `J_LBD` 10),
  so neither can be cabled into the other's position. What else differs by
  position is how the key board routes the link nets (TX/RX mirroring, pair 1 vs
  pair 2), which lives on the key board, which is module-specific anyway.
  **Rev 5 and 6 used one population at all four positions.**
  **Link boards have no CC resistors and USB port boards do.** That difference is
  what keeps a charger from enabling VBUS into a link port, so the two designs use
  connectors with different pin counts and cannot be swapped.
- **The LED driver stays on the key board.** Moving it to the core would put the 28
  LED nets and 320 mA SW currents through a connector, for a part that rarely fails.
- **Module ID.** The key board carries one 1 % resistor to GND. The core has a
  100 kΩ pull-up whose top is the **battery-divider enable GPIO**, driven high only
  during the read, so it costs nothing between reads; the `AINx` pad is read as a
  ratio against the SAADC's internal `VDD` channel. **Rev 5 fed the pull-up from
  the switched battery node, which is `VBAT`, not `VDD`: on USB with no cells it
  read as a short and the module would have entered safe mode; with flat cells the
  bands drifted.** A GPIO top makes the ratio independent of cell state. Bands: `left` 10 kΩ (ratio ≈ 0.09), `right` 47 kΩ (≈ 0.32), `numpad`
  220 kΩ (≈ 0.69). Open (≈ 1.0) means no key board, and a short (≈ 0) means a
  fault. **Margins (F6, Phase 3, 2026-09-15):** with 1 % resistors, ±100 ppm/K over
  ±25 K, ≤800 Ω of GPIO output resistance (`VOH` ≥ `VDD` − 0.4 V at 0.5 mA) and the
  SAADC's calibrated offset (±2 LSB10) plus INL (4.7 LSB12), the worst-case ratios
  are 0.085–0.097, 0.308–0.330 and 0.675–0.699, each well inside ±0.06. Gain error
  (±3 %) cancels only if the `AINx` and `VDD` channels use the same gain and
  reference. The numpad node's 68.8 kΩ source needs `TACQ` ≥10 µs (product spec
  Table 41). Bench read on all three key boards in 7a. A mismatch with the compiled shield is a **safe mode**: no matrix scan,
  link pins held as undriven inputs, link VBUS switch off, first LED blinks red at
  low current, bootloader still reachable.
- **Service rule: slide switch off and USB unplugged before unplugging any cable.**
  It is advice, not the only protection. Series resistors on `VIO`, SDA, SCL and
  `SDB` at the key board limit current into the driver if the lighting cable is pulled live
  (§4). The rule goes in the build guide and on the core board's silkscreen, and
  §16 checks that the likely mistakes do no damage.
- **Tool-less battery door.** Cells come out through a door in the palm-rest floor
  without undoing case screws. Every board is fixed with M2 screws into heat-set
  inserts, so one driver size services the whole keyboard.
- **Fault reporting.** Firmware reads each KTS1693's `ACOK` (local and link, one
  pin each) and the link handshake state. It reports faults as key-light blink codes
  and over the log. The build guide maps each symptom to the board to swap.

## 3. Locked decisions

| Area | Decision | Why |
| --- | --- | --- |
| Switches | Cherry MX, Kailh hotswap `CPG151101S11` | off-the-shelf caps |
| Caps | widths 1U–2.75U inclusive, **any off-the-shelf set** | standard sets need 2.25U/2.75U; shine-through not required |
| Spacebar | 2 × 2.75U, one per half | the K860's spacebar is already split |
| Bottom row | flat, not arced | lets long keys stay rectangular; the K860's bottom row is nearly level anyway |
| Pitch | **19.05 mm throughout, pending Phase 1** | see §10 |
| Width | **~468 mm accepted** | 456 mm key field + two ~6 mm seams; known deviation from the K860 |
| Layout | K860 arc via per-key rotation, alpha rows only | the arc is the K860 look |
| Board partition | **by failure mode** (§2a): core, key, USB port, link, seam, battery, dial | a worn or abused part costs a small plug-in board, not an assembled keyboard PCB |
| Core board | **one design for all three modules**, union pinout, identical BOM; placed with its antenna end clear of every other board's copper | one spare fixes any module; cores can be swapped between modules to find a fault |
| Interconnect | **several small locking wire-to-board connectors, split by function**, JST GH family (1.25 mm, positive lock) proposed, **any fallback must also lock**; ≥2 contacts per power net; no fine-pitch board-to-board stacking | hand-solderable, premade cables, a cable is a spare part; splitting by function keeps each connector ≤15 contacts and power away from the matrix |
| Backplane | **the key board routes everything module-specific**; small boards and the core plug into it, except the USB port and battery boards, which plug straight into the core | link and USB port boards stay single-design; host D+/D− crosses one cable, not two |
| Module ID | resistor on the key board, read as a ratio on one `AINx` pad with a **GPIO-driven pull-up top**; a mismatch is a safe mode | an identical core cannot run the wrong module's firmware against the wrong hardware; a `VDD`-level top keeps the ratio valid on USB with no or flat cells |
| Service | slide switch off and USB unplugged before unplugging a cable, **backed by series R on the driver's `VIO`/SDA/SCL/`SDB`** (1 kΩ / 470 Ω / 470 Ω / 1 kΩ, E11); tool-less battery door; M2 screws throughout; **every external connector is user-replaceable by swapping the small board it sits on (2026-09-14)**: reachable without removing another board, one cable and M2 screws, no soldering | builders will pull the lighting cable live anyway, so the hardware must survive it; cells need no tools; plugs wear and take the surges, so the part that fails is the part a user can change |
| MCU | Raytac MDBT50Q-1MV2, **second source MDBT50Q-U1MV2** (chip antenna); **the core is laid out for both land patterns and both antenna keepouts** (rev 7) | pre-certified, 48 GPIO pads, no RF work; one core accepts either module, so the MCU is no longer single-source; each variant gets its own RSSI check (§16). Fanstel BT840 has a different pad layout and is **not** a drop-in |
| LFCLK | external 32.768 kHz crystal | **not** on-module; internal RC is ±250 ppm |
| Seams | numpad = digits+operators only; arrows+nav on `right` | detaching numpad loses only digits |
| Central | **`left`**, which owns host USB, host BLE and the split central role | everything host- and radio-facing on one board; puts the only active radio at an outer edge instead of mid-keyboard |
| Numpad link | **copper passthrough across `right`**: pair 2 runs seam to seam and port to port on `right`'s PCB, never touching `right`'s MCU; `left` runs two UARTs | no relay firmware in the numpad's path; numpad wake reaches `left` directly |
| Split transport | wired + BLE, **all-or-nothing** | core has one active transport; no core patch |
| Transport hysteresis | wired→BLE after ~300 ms of link loss; BLE→wired after ~2 s all-present **and** ~1 s with no key held; held keys from a lost source released on switch | pogo bounce and satellite reboots don't flap the split or land mid-chord |
| Port mapping | source id from the handshake's `sat_id`, not the pair | a numpad cabled straight into `left` still maps correctly; ids match BLE slots |
| TX discipline | satellite TX is a weak pull-up until a valid `PING` arrives; `left` RX pull-downs ≥100 kΩ; both pair-2 pins on `left` stay pulled-down inputs until orientation is detected; **`left`'s pair-1 TX is also a pull-up-only input until its RX is lifted** (rev 6) | no link ever has two drivers before a handshake, and no driver sits on a switched-off neighbour's clamp diodes |
| Link signalling | **460 800 baud**, 115 200 fallback; **470 Ω series at every MCU UART pin**, none on connectors or on `right`'s pair-2 copper; ≤1 m per cable hop | ~200 pF worst-case pair-2 load gives ~0.2 µs edges against a 2.2 µs bit; two fighting drivers stay under 3.5 mA |
| Pair 2 orientation | `left` detects which SBU pin is RX from the numpad's TX pull-up, then applies the matching UART pin state; **both pins high = ambiguous, stay inputs** | SBU has one pin per plug side and cannot be tied like D+/D−; the ambiguous case catches a flipped cable in parallel with a joined seam |
| ZMK dependency | exact commit pinned in `west.yml`; weekly non-blocking CI canary against ZMK `main` | our module uses split internals; wired split is experimental upstream |
| Number row | **6/3**: 1–6 on `left`, 7–9 and 0 on `right` | locked; no longer gated on Phase 1 |
| Link, joined | **SAMZO magnetic pogo pairs**, spring half `PR5L3715-4P-C-H` upstream (`left`'s wall, `right`'s numpad wall), flat half `PR5L2820-4P-C-F` downstream; **two pairs** on the `left`–`right` seam, one on `right`–`numpad`; each on a **seam board** standing at the wall and **cabled to that side's link board** | no cable in the seam; built-in N/S magnets align, retain and refuse a reversed join; one stocked 4-contact part for both seams; a detached module exposes only flat contacts or unpowered pins; worn halves are replaced with their seam board, which unplugs |
| Link, separated | `left`–`right`: rear USB-C, **passive full-featured USB-C cable** (SBU wired). `right`–`numpad`: rear USB-C, any USB 2.0 data cable | pair 2 needs the SBU wires; active cables need VCONN, which a link without CC cannot supply |
| Link VBUS | `left` sources its port from `VBUS_IN` through a current-limited latch-off switch on its downstream link board (P14, 2026-09-15), **enabled only after a pair-1 handshake**. `right` sources its numpad port from `VBUS_IN` through a second switch, **enabled only while `left` reports a pair-2 handshake** | satellites stop draining cells when the host is on USB; loopback chargers rejected; `right` cannot see pair 2, so `left` tells it; one source net on every core |
| Link wake/detect | **on the UART lines**, no extra conductor | RX idle-high = detect; RX as `SENSE` + break = wake |
| Lighting | IS31FL3733, common-anode RGB, 1 CS + 3 SW per LED | per-key independent colour, 8-bit PWM per channel; serial-chain parts cost 0.6 mA/LED idle |
| LED current | **~20 mA peak per die**, `RSET` ≈ 42.2 kΩ | safe for any reverse-mount RGB part at 1/12 duty; halves driver heat |
| LED rail | **4.7 V boost on battery; VBUS (~5 V) on USB**, ideal-diode OR-ed | USB lighting skips the LDO and boost |
| Driver idle | `SDB` + software shutdown, rail stays up | power-gating VCC violates abs-max on `VIO`/SDA/SCL |
| Cells | **alkaline and NiMH only**, 1.9–3.3 V. Low-self-discharge NiMH recommended | lithium primaries (L91) reach 3.66 V fresh, over nRF52840 `VDD` recommended max |
| Overvoltage | per pack: TPS3840PL35 + series AO3415A, trips rising **~3.65–3.75 V** (window 3.59–3.81 V); **FET off by default**: gate pulled up to source, supervisor pulls it down through a gate RC of **τ ≥ 25 ms**, capacitor gate-to-source, diode for fast turn-off (rev 6; τ rev 7); **330 kΩ `CELL+` bleeder and ≤1 µF on each core pack input** so a hot cell swap cannot find the FET still on (2026-09-15) | a 14500 pair is 8.4 V; max stays under `VDD` 3.9 V abs-max, min clears fresh alkaline at ~3.36 V; the supervisor's below-threshold state is "FET on", so without the slow turn-on a 14500 pair passes for the supervisor's start-up plus release delay; C801 keeps a running pack's FET on for seconds after the cells come out, so without the bleeder a quick swap passes 8.3 V (ngspice) |
| Undervoltage | firmware system-off at ~2.05 V; **LM66200 `ON` driven by TPS3840PH18 at ~1.9 V pack** (via BAT54C), on the pack branch ahead of the mux | the OR doubles as the cutoff; on battery everything loses supply together; on USB a flat pack does not stop the keyboard |
| Pack series resistance | ≤300 mΩ max per path (~170 mΩ typical) | two FETs at 1.85 V gate drive cannot meet 150 mΩ |
| USB input | **KTS1693** integrated OVP switch on **every inward USB-C socket's VBUS** (local and upstream link; downstream link boards omit it, rev 7), **on the USB port and upstream link boards**, external divider for a 5.55–5.95 V trip | downstream TPS2116, LM66200, TPS22950 and TLV757P are all **6.0 V abs-max**; 100 ns turn-off also stops a source that fails while connected, which the discrete TLV6713 + AO3401A design could not (16.8 V simulated at its output); 0.7 ms built-in debounce replaces the discrete gate-delay network |
| LED rail source | **TPS2116 in priority mode**: VBUS_IN on IN1 (`PR1` 301 kΩ / 100 kΩ, IN2 below 3.63–4.40 V; 1 MΩ `PR1`–`ST` hysteresis, E3 2026-09-15), boost on IN2 | USB allows 4.75 V at the receptacle, and after cable and FET drops VBUS can sit below the 4.7 V boost; an auto-OR would then move LED load onto the boost, which draws from the cells |
| Boost | TPS61023, single source accepted | no pin-compatible alternative exists |
| Pack ESD | **bidirectional** 9 V-standoff TVS per pack (Littelfuse SMF4L9.0CA), RC into supervisor `VDD` | doesn't crowbar a 14500 pair; filters the clamp under 10 V; a unidirectional part sits ahead of the reverse-blocking FET and PTC and would short a reversed pack through its forward diode |
| Link VBUS fault | TPS22950**L**, latch-off; re-armed only by a fresh handshake | a short never sits in a retry loop |
| Logic rail | **regulated 3.3 V always** (rev 6): VBUS → 3.3 V LDO on the priority mux's IN1; VBAT → dedicated logic boost (**TPS61099DRV**, adjustable WSON-6, 576 kΩ / 249 kΩ divider for 3.3 V, 4 µA, Phase 3 2026-09-15) on IN2; packs isolated on USB | 5 V never reaches `VDD`; every module's UART, I2C and `AINx` levels are identical regardless of cell state. **Rev 5 ran `VSYS` at 1.85–3.3 V unregulated: a 3.3 V module could not read a 2.2 V module's TX (`VIH` = 0.7·`VDD`), and the reverse over-drove the pin (abs-max `VDD` + 0.3 V)** |
| Inward port OCP | KTS1693 `ISET` 4.99 kΩ, **1.82–2.18 A latch**, on local **and upstream link** ports (link since E9, 2026-09-15) | the LM66200 behind it is 2.5 A abs-max with no current limit; rev 5's 3.0 A trip let a fault sit above that, and link ports with OCP disabled left a legacy charger unlimited; the 5–10 ms debounce pulse is accepted |
| Enable defaults | LED boost `EN` pulled up to `VSYS`; logic LDO and logic boost `EN` tied on; only the expansion LDO is GPIO-gated; GPIOs on the others may disable, never enable | on USB with no cells nothing could enable the LDO; on battery the LED rail must be up before `VIO`/SDA/SCL, or the driver's `VCC` + 0.3 V rule is broken at every boot |
| LED-rail switchover | **~10 µF LED-rail bulk carries the TPS2116 switchover; no blanking ISR** (rev 7) | the TPS2116 break-before-make switchover is 8 µs typ at 5 V (no max given); 250 mA for 8 µs at 0.7 V droop is ~3 µF, tripled for the missing max. Rev 6's 1.3 ms was the power-up soft start, which is skipped on switchover while `VOUT` > 1 V |
| D+/D− ESD | USBLC6-2SC6 with its `VBUS` pin on the KTS1693's **protected** side (or NC) | the pin's abs-max is 5.5 V; at the connector a 20 V hot plug would kill the array |
| USB CC sense | **all three modules**, CC1/CC2 from the USB port board to the core's `AINx` | identical core; each module knows its local port's current |
| Dial | on `right`, a **peripheral** sensor; behaviors run on `left` | the dial stays where the K860's host keys were; profile selection is central-side anyway |
| Battery lighting | firmware cap ≤250 mA at the LED rail per module | keeps one-pack current inside the PTC at UVLO |
| Profiles | 9, `CONFIG_BT_MAX_PAIRED=11`, `CONFIG_BT_MAX_CONN≥3` | BLE split subtracts 2 bonds and needs 2 connections |
| Selector | **detented** encoder, Bourns PEC11R **24 detents / 24 pulses** with push switch, preview-then-commit | Bourns states both switches open at every detent when pulses = detents; 15°/step, profiles 1–9 span 135° |
| RGB LED | SunLED XZMDKCBDDG45S-9, common anode (pin 2; cathodes 1 R, 3 B, 4 G), reverse-mount PLCC4; **second sources Inolux IN-P32TRRRGB / QT-Brightek QBLP677R-RGB on a combined key-board footprint** (2026-09-14), feasibility open (P1) | datasheet-verified: 30 mA DC, pulsed 185 mA R / 150 mA B, G; Vf max at 20 mA 2.5 / 4.0 / 4.1 V; HBM only 250 V on blue. The alternates need a Ø4.5 mm cutout with the body in the hole and a ~6.0 mm lead span; their drawn pinout reads mirrored against SunLED's, which the combined footprint must resolve or disprove |
| Dial duty | volume default; profile picker on Fn layer | daily use is volume |
| Profile display | light number-row keys 1–9; **glow around caps is enough** | no part, no pins, no case window |
| Cross-module lighting | tunnelled through `INVOKE_BEHAVIOR`; satellites render locally | protocol has no generic payload; no core patch |
| Deep sleep | stock; documented limitation | untethered, a sleeping satellite cannot wake the central (`left`) |
| Rollover | full NKRO, every key independent | diode per key kills ghosting; `CONFIG_ZMK_HID_REPORT_TYPE_NKRO=y` lifts the 6-key report limit |
| Mechanical | in scope, palm rest included | it defines the K860 silhouette |
| Case | 3D printed resin/SLA, ~1.5 mm seam walls, heat-set inserts; **one piece per module from a large-plate print service** (rev 7) | resin is brittle; never self-tapping screws; a 233 mm deep module does not fit a desktop SLA plate (~200–220 mm long axis), and one piece keeps joints out of the wall, insert and seam budgets (M1) |
| Plate | **1.5 mm FR4, no copper**, plate-mount stabilisers | not a ground plane over the antenna; same fab as the PCB |
| Row dish | flat boards; dish from per-module tilt + sculpted keycap rows | a stepped plate needs a stepped PCB, see §11 |
| Distribution | open source, others may build | second sources throughout, build guide with a repair section (symptom → board) and a spares list, no panelisation |
| Spares | listed in the build guide, **every item optional**: 1 core, 1 USB port board, 1 upstream and 1 downstream link board, 2 seam boards, 1 battery board, 1 cable set | keeps a first order cheap; the list names the board for each wear or abuse failure so a builder can order it when needed |
| Parts sourcing | **Mouser Europe or a similar European distributor (DigiKey, Farnell, TME, Romanian distributors)**; LCSC part numbers are kept as references only | the build is sourced in Europe; a part stocked only at LCSC/JLC needs a distributor-stocked alternative |
| Qi2 | keepouts + DNP footprints + **reserved VDDH/REG0 topology** on the core; charger, coil and cell protection as a future battery board | see §15 |

Rejected: Choc v2 (lost to off-the-shelf caps), addressable RGB chain (0.6 mA/LED
idle), 7-segment digit (superseded by key lighting), magnetic angle sensor
(3.4 mA live), absolute 9-position rotary (maintained contact blocks sleep),
single-MCU dumb satellites (scan lines off-board, far more conductors than USB-C
has, forecloses everything), wired-only (deleted untethered use), per-source
transport core patch (rebase burden), shine-through caps required (narrows sets too
far), aluminium plate (ground plane over antenna), printed plate (MX clips crack
resin), lithium primaries (over `VDD` recommended max), central on `right`
(superseded in rev 4), firmware relay of the numpad through `right`'s MCU (relay
code and a two-step wake; lost to copper passthrough, see
[`docs/01-architecture.md`](../docs/01-architecture.md) §6), one main PCB per
module (superseded in rev 5), a core stacked under the key board on fine-pitch
mezzanine connectors (key-board copper over the antenna, not hand-solderable), one
I/O board per module carrying all its sockets (a worn socket scraps the others;
`right`'s ports sit at opposite ends), the LED driver on the core (28 nets and
320 mA SW currents through a connector), link board population variants per
position on a shared header (a misfit could source VBUS ungated; rev 7 adopts two
populations only with different header pin counts).

## 4. Power

Board in brackets: `[BAT]` battery, `[USB]` USB port, `[LNK]` link, `[SEAM]` seam,
`[CORE]` core, `[KEY]` key board.

```
  [BAT] pack A, 2xAA -[TVS 9V]-[rev-block FET]-[OVP FET <- TPS3840PL35]-[PTC]--> [CORE] LM66200 IN1
  [BAT] pack B, 2xAA -[TVS 9V]-[rev-block FET]-[OVP FET <- TPS3840PL35]-[PTC]--> [CORE] LM66200 IN2
                                                                              |  ON <- TPS3840PH18
                                                            (packs via BAT54C -> supervisor VDD)
                                                                              |
                                                                            VBAT ----------+
                                                                                           |
  [USB] local USB VBUS -[KTS1693 OVP, 5.55-5.95 V]-[TVS]--> [CORE] ideal diode --+          |
  [SEAM]+[LNK] upstream link VBUS -[KTS1693]--> [KEY] --> [CORE] ideal diode ----+- VBUS_IN |
                                                  |                            |
                                   +--------------+--[LDO 3.3 V]--IN1 [priority mux] IN2 <--[logic boost 3.3 V]<-- VBAT
                                   |                                     |
                                   |                            VSYS (3.3 V, regulated)
                                   |                                     |
                                   |              +----------------------+------+
                                   |              |                             |
                                   |      MDBT50Q VDD, matrix,      LED boost 4.7 V (EN pulled up) <-- VBAT
                                   |      encoder, driver VIO                   |
                                   |                                   TPS2116 IN2
                                   +-------------------------------------TPS2116 IN1 (priority)
                                                                                |
                                                                   LED RAIL (4.7-5.0 V)
                                                                                |
                                                      [KEY] IS31FL3733 VCC, LED anodes via CS
                                                     [CORE] [LDO 3.3 V, gated] -> expansion pin 2

  left, right: [CORE] VBUS_IN --> [KEY] --> [LNK, downstream: latch-off ILIM switch (no RCB), EN from core via J_LBD 6; TVS, no OVP] --> link port + [SEAM] pogo
               left: EN after pair-1 handshake.  right: EN while left reports pair 2 up.
```

The pack chain sits on the battery board, so a reversed cell, a 14500 pair or a
terminal ESD strike damages at most a small, mostly hand-solderable board. The KTS1693s sit on
the USB port and upstream link boards, so a surge damages at most a small board.

Rules:

- **5 V never reaches VSYS.** VBUS enters VSYS only through the 3.3 V LDO and the
  priority mux. **Rev 2 OR-ed VBUS straight onto VSYS, which feeds `VDD` (3.6 V
  max, 3.9 V abs-max): the first USB plug-in would have destroyed the MCU.**
- **The logic rail is regulated, 3.3 V always (rev 6).** On battery a dedicated
  boost (TPS61099DRV, ~1 µA quiescent, 0.7 V minimum input)
  takes VBAT to 3.3 V on the priority mux's IN2; on USB the LDO on IN1 wins. Every
  module therefore has the same `VDD`, so the link UARTs, the detect pull-ups,
  the wake break, driver `VIO` and every `AINx` reading are level-compatible
  regardless of which cells are fitted or how flat they are. **Rev 5 ran `VSYS`
  unregulated at 1.85–3.3 V: a module on USB (`VIH` 2.31 V) could not see a
  NiMH module's 2.2 V TX, so the wired split silently fell to BLE, and a 3.3 V
  module driving into a 1.9 V module sat 1.1 V above that pin's abs-max.** With
  its input above its output (fresh alkaline, ~3.36 V) the TPS61099 stays in
  **down mode and keeps regulating**; it only passes the input through above
  `VOUT` + 0.5 V = 3.8 V, which the pack OVP (≤3.81 V) keeps out of reach. Logic
  current through the boost is a few mA at ~85 %; the idle cost is the boost's
  own quiescent current, on the order of 1 µA.
  **Part choice (rev 7).** The fixed 3.3 V TPS610994 is sold only as a 6-ball
  0.4 mm WCSP, which would put a non-reworkable part on the core. The adjustable
  TPS61099DRV (WSON-6, 2 × 2 mm) takes a feedback divider instead: `VREF`
  0.98–1.02 V, FB leakage ≤50 nA (SLVSD88M §6.5). **Divider 576 kΩ / 249 kΩ 1 %
  (Phase 3, 2026-09-15)**: 4 µA, leakage error ≤29 mV, PWM 3.20–3.46 V worst case,
  and PFM (+3 % typical, no maximum published) ~3.56 V, under the nRF52840's
  3.6 V recommended `VDD` maximum (product spec v1.9 Table 100). **Rev 7's
  ~2.3 MΩ / 1 MΩ 0.1 % claimed a leakage error under ~2 %; at the 50 nA maximum it
  is +116 mV (3.5 %)**, which puts PWM at 3.51 V and PFM at ~3.61 V.
  **Second source: dual footprint (2026-09-14).** The core carries a second 2 × 2 mm
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
  **`VSYS` mux `PR1` (core capture, 2026-09-15): its own 301 kΩ / 100 kΩ 1 %
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
- **`VIO` of the LED driver ties to VSYS.** No I2C level translator: pin 39 is an
  input-logic reference and the datasheet's own app circuit does exactly this.
- **The driver's VCC rails are never power-gated in normal operation.** Abs-max is
  "voltage at any input pin, VCC + 0.3 V", so collapsing VCC while `VIO`/SDA/SCL sit
  at VSYS is a violation on every transition. Idle is `SDB` low plus software
  shutdown, which is µA-class. Boost quiescent is then always paid, tens of µA.
- **Undervoltage, two stages.** Firmware reads VBAT on the SAADC and at ~2.05 V
  drives `SDB` low, drops BLE cleanly, and enters system-off. As a backstop, a
  TPS3840PH18 drives the LM66200's active-low `ON` pin high at **~1.9 V at the
  pack**, disabling both OR channels, so the OR is also the cutoff switch. The
  supervisor is powered from both packs through a BAT54C so it survives its own
  cutoff; the ~0.1 V diode drop is why the 1.8 V part gives a ~1.9 V pack threshold
  (about 1.87–1.93 V over temperature). On battery that is all of VSYS, so
  MCU, `VIO` and boost input die together; the LED rail's bulk capacitance decays
  slower than VSYS, so VCC never falls below `VIO`. On USB the packs are already
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
  with 10 µF it is 3.4–3.7 s even with the bleeder, so the core keeps each LM66200
  pack input at 1 µF and puts bulk capacitance on `VBAT`.** E14's original worry,
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
- **USB input OVP.** Every inward USB-C socket's VBUS goes through a **Kinetic
  KTS1693** integrated OVP switch: the local port on all three modules and the
  upstream link net on `right` and `numpad`. The local port's KTS1693 is on the USB
  port board. Each upstream link board carries one: the seam board cables into the
  link board, so the rear port and the seam contacts join ahead of it and one
  KTS1693 covers both. **Downstream link boards (`left`, `right` downstream) carry
  none since rev 7**, see "Downstream ports" below. Everything behind it is **6.0 V abs-max** (TPS2116, LM66200, TPS22950,
  TLV757P, all datasheet-verified). Datasheet facts that shape the circuit:
  - **Ratings.** IN 30 V abs-max, internal clamp 32 V, IEC 61000-4-5 ±110 V surge
    and IEC 61000-4-2 ±8 kV contact on IN, 9 mΩ typ / 13 mΩ max N-FET driven by an
    internal charge pump, 8 A continuous. Turn-off **100 ns** after VIN crosses
    OVLO (2 V/µs input edge). Turn-on only after VIN has sat between UVLO
    (2.1–2.7 V) and OVLO for a **0.7 ms debounce**, then a ~2 ms soft start. That
    debounce is what the discrete design needed a gate network for.
  - **Trip point: external divider, not the internal one.** The internal OVLO is
    5.77–6.13 V over temperature, which can exceed the 6.0 V ceiling. The OVLO pin
    reference is 1.162–1.238 V; with **R1 = 100 kΩ, R2 = 26.4 kΩ (0.1 %)** and
    ±100 nA pin leakage the trip is **5.55–5.95 V**, above vSafe5V's 5.5 V. The pin
    sits at 4.2 V with 20 V on VBUS (20 V abs-max) and the divider draws 40 µA on
    USB. 1 MΩ, the datasheet's suggestion, lets pin leakage move the trip by ~2 %.
  - **Pins that must not float.** `ISET` **4.99 kΩ 1 %** for a **1.82–2.18 A**
    over-current latch (Table 1, specified 0–70 °C) on local ports **and, since E9
    (2026-09-15), on upstream link ports too**. Link ports had ≥500 kΩ (1 MΩ, OCP
    disabled, only the >10 A short-circuit detect of p. 13) on the grounds that the
    TPS22950L limits; it does not limit a legacy 5 V charger plugged into an upstream
    port, which could then hold a short on the core's LM66200 link channel
    indefinitely. At 4.99 kΩ the upstream KTS1693 may latch before `left`'s
    TPS22950L on a 1.82–1.9 A chain fault; both latch, so either is harmless. **Rev 5
    set 3.0 A**, above the 2.5 A abs-max of the LM66200 channel behind it. The whole
    keyboard on one port is ~0.67 A at full white plus up to 3 × 150 mA of expansion
    3V3 (Phase 3 bottom-up, below).
    **Accepted (E9): the latch is not a limiter.** With `OC_MODE` low the switch
    "will still fully turn-on" for the 5–10 ms `tOCP_DEB` before it opens (p. 11),
    so a fault between 2.5 A and the source's own limit passes one ≤10 ms pulse
    through an LM66200 channel rated 4 A for 1 ms. `OC_MODE` high would hold the
    current at `ISET` but retries every 200 ms instead of latching; not adopted. §16
    scopes the pulse.
    **`OC_MODE` tied low: an over-current latches the switch off.** `EN` is tied to
    GND rather than a GPIO, so there is no floating pin at boot and no firmware
    path; the latch clears when VBUS is removed and reapplied, which for the user
    means unplugging the cable. `ACOK` and `CDET` are open-drain and may float;
    `ACOK` to an LF-class GPIO is optional, and would let firmware report the trip.
  - **Downstream ports: no KTS1693 (rev 7).** On `left`'s link port and `right`'s
    numpad port, power flows outward, which would run the KTS1693 OUT → IN. Its
    OTG section covers only the start-up through the body diode; two sustained
    cases are not covered: the far end shorted, where the TPS22950L limits and
    `OUT` sits above `IN` + 0.3 V until it latches, and the KTS1693 tripping on a
    connector transient while the TPS22950L still feeds `OUT`, leaving `OUT` at
    5 V over `IN` at 0 V indefinitely. **Rev 6 asked Kinetic to confirm (E13);
    rev 7 removes the part from those positions instead.** The downstream link
    board is the same PCB with a 0 Ω link across the KTS1693 footprint and no
    OVLO divider, and a port with no CC cannot negotiate above 5 V. **Accepted
    consequence:** a non-compliant source forcing >6 V into a downstream port
    reaches the TPS22950L (6.0 V abs-max) with only the SMF6.0A in front of it.
    **Correction (2026-09-15): the TPS22950L has no reverse current blocking.**
    TI SLVSFJ2B Table 5 (p. 3) lists RCB "No" for the L variant and §9.3.4 (p. 14)
    covers only the TPS22950 and TPS22950C; rev 7 said it blocked. Accepted
    instead of adding a part: satellites feed link VBUS only through inward-only
    ideal diodes, so the one backfeed source is a foreign supply plugged into a
    downstream port. That supply reaches `VBUS_IN` through the switch, and the
    core's LM66200 blocks it from the local port (`VOUT` > `VINx` by 42–70 mV,
    SLVSG04 §6.5 p. 6). At ≤6 V that is harmless; above, it is the consequence
    already accepted. Checked in §16.
    The downstream board has no `ACOK`, so `left`'s link port reports no fault
    code and `right`'s wired-OR `ACOK` comes from its upstream board only. Its
    header is `J_LBD`, 10 pins, so it cannot be cabled into an upstream
    position, where it would leave `VBUS_IN` unprotected.
  - **Around it.** 0.1 µF (50 V) on IN, ≥1 µF on OUT, then the SMF6.0A and the
    10 µF bulk. The TVS2200 is kept as a footprint at the connector but not fitted:
    the KTS1693's own IEC ratings cover the input. Quiescent current is
    140–180 µA, drawn only while VBUS is present.
  - **Package.** 20-bump WLCSP, 1.935 × 2.160 mm, 0.4 mm pitch. **Not
    hand-solderable**. It sits only on the USB port and link boards, so only those
    small boards need assembly-house placement for it. A builder replaces a damaged
    one by swapping the board rather than reworking the part. Mouser lists it (stock unconfirmed); a second source is still owed (open
    question P7).
  - **Rejected: discrete TLV6713 + AO3401A** (rev 4, then the 2026-09-13 proposal).
    Simulated in ngspice: its comparator output is undefined for up to ~190 µs at
    power-up, so turn-on needed a BSS138 in series with a zener-referenced 1.3–3.0 ms
    delay; the AO3401A's ~250 pF Crss near 0 V let a 20 V hot plug through
    (8.5–10.6 V at the output) until a 10 nF gate–source capacitor was added, which
    slowed turn-off to ~350 µs; and **a source stepping from 5 to 20 V while
    connected reached 16.8 V at the output**, 11.9 V even with an ideal comparator.
    It also needed a 0.1 % divider because the TLV6713's rising threshold is
    400–413 mV, not the 0.75 % falling one. Also rejected: NCP361 (600 mA DC),
    TPD1S514 (DSBGA, no better for assembly than the KTS1693 and 30 V), LM74502
    (OV threshold ±6.6 %), MAX4987AE (OVLO 6.15 V fixed).
- **PTC in each pack lead, hold ≥1 A.** 2×NiMH will deliver amps into a short and
  there is a boost inductor downstream. **Eaton PTSLR12066V175**: 1.75 A hold,
  3.5 A trip, 0.4 s max at 8 A, 50 A Imax, **Ri min 5 mΩ, R1 max 45 mΩ**, 1206.
  Hold derates to ~88 % at 40 °C, ~1.5 A against the 730 mA worst case. Chosen over
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
  under the UVLO at once. The part at risk is the core, and only under an internal
  fault; PTSLR12066V110/V150 would close or narrow the band at 381/331 mΩ of path
  resistance and were not adopted. §16 runs a partial-short test.
- **The two packs are never directly paralleled.** Each gets its own
  reverse-blocking FET, OVP, PTC and LM66200 channel into VBAT. **OR-ing does not share
  load:** the higher pack carries all of it until the two equalise, then they
  alternate. The keyboard runs correctly on one pack alone, and every per-pack
  part is sized for the full module load. **Rev 2 claimed two packs halve the
  C-rate; they do not.**
- **Series resistance budget ≤300 mΩ max per pack path**: rev FET ≤75 + OVP FET
  ≤75 + PTC ≤45 (R1 max) + LM66200 ≤51 (max at 1.8 V, 25 °C; 61 mΩ at 85 °C) +
  holder <50 mΩ (MPD BC2AAPC datasheet; ~30 mΩ was assumed before the holder was
  chosen, P15) = **~296 mΩ**, about 170 mΩ typical. Rev 4 counted the LM66200 at its
  40 mΩ typical; at its maximum the 80 mΩ PTSLR12066V150 would have made it 311 mΩ.
  At the worst-case ~730 mA the path drops ≤0.22 V, so full brightness ends slightly early on a
  nearly flat pack; firmware already scales lighting with VBAT.
- **Link VBUS, a chain.** `left` sources its link port and seam pogo from
  `VBUS_IN` through a current-limited, latch-off load switch (TPS22950L, no
  reverse current blocking) on its downstream link board, off by default. Its `ON`
  pin has a smart pulldown (SLVSFJ2B Table 9-2), so an unplugged `J_LBD` leaves it
  off. **Until 2026-09-15 it sat on the key board (P14):** the L variant ships only
  as a 0.4 mm WCSP, which key boards do not carry; on the link board a failed switch
  is a board swap. The key-board-to-link-board cable is upstream of the limit. On `left`, `VBUS_IN` is the
  local port's VBUS through one core OR channel; the core's link-input channel is
  unused and pulled down. **Rev 4 fed `left`'s switch from local VBUS directly.**
  Rev 5 uses `VBUS_IN` so every core exposes a single source net, at the cost of
  one more ≤51 mΩ ideal-diode drop in `left`'s path. The switch is enabled only after `right` handshakes on pair 1 (§6), dropped on link
  loss. `right` takes that VBUS through the input OVP and an inward-only ideal diode
  into `VBUS_IN`,
  and sources its numpad port and seam pogo from `VBUS_IN` through a second
  TPS22950L. `right` cannot see pair 2, so that switch follows a **`pair2_up` flag
  that `left` sends over pair 1**; it drops on pair-1 loss, pair-2 loss, or flag
  timeout. `numpad` takes link VBUS through the input OVP and an inward-only ideal diode.
  The OVP sits where the link VBUS net enters the board, after the rear port and the
  seam contacts join, so one block covers both; a legacy USB-A-to-C cable into an
  upstream port gets the same protection as the local port. `VBUS_IN`
  is only ever USB-derived, so no pack reaches another pack. The nRF52840 `VBUS`
  pad and the expansion 5 V pin derive **only** from the local host/DFU connector.
- **Consequence: `right` on its own USB cannot power a cabled numpad unless `left`
  is linked.** Without `left` there is no pair-2 handshake, so the numpad runs on
  its cells. Accepted.
- **`left`'s switch carries `right` and `numpad` together**, so its current limit
  is set for both, and `left`'s host CC reading is the budget for the whole chain.
  **Load check (Phase 3, 2026-09-15), full white, bottom-up:** IS31FL3733 `IOUT`
  max 46 mA at 20 kΩ scales to 21.8 mA at 42.2 kΩ, `ILED` = `IOUT` / 12.75 =
  1.71 mA per die, plus 3 mA `ICC` and ~30 mA of logic through the LDO: `right`
  303 mA, `numpad` 122 mA, `left` 241 mA. `left`'s chain is **425 mA** against
  `IHCD` 1.2 A minimum; one scan slot peaks at 16 dice × 21.8 mA = 352 mA, also under
  it. **Expansion 3V3 budget: 150 mA per module** (2026-09-15), which takes the
  chain to 725 mA and the whole keyboard on `left`'s host port to ~1.12 A, inside a
  1.5 A advertisement. The parts list's earlier ~1.07 A chain estimate was an
  equal three-way split of an unsourced ~1.6 A keyboard total.
- **`VBUS` must reach the module's `VBUS` pad directly**, not only through the
  power path, or USB and DFU are dead. It arrives from the USB port board on its
  own contacts of the core's USB connector.
- Set `DCDCEN`. The REG1 inductor and the 32 MHz crystal are inside the module.
- Per module, on the core: slide power switch, reset tactile, bootloader tactile,
  reachable through the case wall at the core's edge (Alps SKRTLAE010 side-push
  tactiles, C&K PCM12SMTR side-actuated slide; land patterns not yet checked).
  **The slide switch is an SPDT on the pack LM66200's `~ON` (core capture,
  2026-09-15):** common on `~ON`, one throw on the TPS3840PH18 output (on, UVLO in
  control), the other on the supervisor's `VDD` (BAT54C cathode), which holds `~ON`
  high and turns both packs off. Off costs nothing and USB still runs the module,
  so DFU works with the switch off. A 10 MΩ from `~ON` to GND holds "on" across
  the break-before-make gap. Rejected: shorting the supervisor's `MR` to GND (its
  100 kΩ internal pull-up, SNVSB03E, would drain ~30 µA while off) and switching
  `VSYS` (load current through the contacts, no DFU while off).
- **Cable hot-unplug.** The driver's VCC (LED rail) and its `VIO`/SDA/SCL (VSYS)
  share one key-board connector, so they break together, but not in a defined
  order. Pulling that cable powered can briefly put `VIO`, SDA or SCL above the
  driver's "VCC + 0.3 V" abs-max. **Series resistors on `VIO`, SDA, SCL and `SDB`,
  placed at the driver on the key board**, limit the current through its input
  clamps while that lasts. **Values (E11, 2026-09-15): 470 Ω on SDA and SCL, 1 kΩ
  on `VIO` and `SDB`; 4.7 kΩ 1 % pull-ups to `VSYS` on the core.** `SDB` joins the
  list because it is a push-pull GPIO at `VSYS`, the same hazard. Checks, with the
  driver's SDA `VOL` taken as 0.4 V (Lumissil publishes it only for SYNC, at
  8 mA): an ACK low reaches the nRF52840 at 0.68 V against its 0.97 V `VIL`
  (0.3 · 3.23 V); rise time 0.8473 · 4.7 kΩ · 50 pF = 201 ns against the driver's
  300 ns; SDA/SCL clamp current ≤0.56 mA, since the open-drain bus only rises through
  the pull-up; `VIO`/`SDB` ≤2.9 mA. The driver's `VIO` supply current is not
  published; 1 kΩ costs 1 mV per µA. Lumissil publishes no clamp-current limit, so
  the §16 unplug test is the proof. A wire-to-board connector gives no mate-first
  contact, so nothing in the design relies on sequencing.

**Pack current.** Worst case is `right` at the battery cap near UVLO:
250 mA × 4.7 V / (1.9 V × 0.85) ≈ **730 mA from one pack**, inside a 1 A hold.

Budget, `right`, 4000 mAh NiMH (two 2000 mAh packs). `IOUT` ≈ 19.8 mA peak at
`RSET = 42.2 kΩ`, `GCC = 255`; `ILED = IOUT/12.75 ≈ 1.55 mA` average per die at
`PWM = 255`; 52 keys × 3 dice = **242 mA at the rail**. Cell current = rail
current × 4.7 V / (2.4 V × 0.85) ≈ 2.3 × rail. Boost efficiency below ~10 mA is
likely worse than 85 %, so the dim rows are optimistic. Radio and MCU excluded.

| Condition | At rail | From cells | Runtime |
| --- | --- | --- | --- |
| Idle, no lighting | — | **unproven, see §16** | target ≥6 months |
| 10 keys dim (24 %) | 11 mA | 26 mA | ~155 h |
| All 52 at 3 % | 7 mA | 17 mA | ~240 h |
| All 52 at 24 % | 58 mA | 134 mA | ~30 h |
| All 52 at 100 % | 242 mA | 557 mA | ~7 h |
| *(addressable chain, all LEDs black)* | *31 mA* | *72 mA* | *~56 h* |

**Rev 2's "10 keys dim" row listed rail current as cell current**, and every row
assumed ~2.8 V at the pack rather than NiMH's 2.4 V average.

A 6-month idle target on NiMH requires low-self-discharge cells; standard NiMH
loses that much charge to self-discharge alone.

## 5. Pin budget

Raytac restricts 21 of the 48 pads to **low-frequency I/O only, ≤10 kHz — no
UART, I2C, SPI or PWM** because they sit near the radio. Assignment must respect
this class split and is done explicitly in Phase 3, not left to the tools.

Restricted (LF-only) pads: `P0.02 P0.03 P0.09 P0.10 P0.28 P0.29 P0.30 P0.31
P1.01–P1.07 P1.10–P1.15`. `P0.09`/`P0.10` are NFC antenna pins by default and
need `CONFIG_NFCT_PINS_AS_GPIOS=y` (writes `UICR.NFCPINS`) before they work as
GPIO.

**The core board is identical, so the pin assignment is the union** of what any
module uses. Every core brings every line out to its connectors, and a module's key
board leaves its unused lines unconnected (disconnected input buffers in
firmware).

| Use | `left` | `right` | `numpad` | **core (union)** | Class |
| --- | --- | --- | --- | --- | --- |
| Key matrix | 13 (6×7) | 15 (6×9) | 9 (5×4) | 15 (6 rows, 9 cols) | LF ok |
| UART; RX doubles as detect + wake `SENSE` | 4 (UARTE0 pair 1, UARTE1 pair 2) | 2 | 2 | 4 | **full-function** |
| LED driver I2C, dedicated bus | 2 | 2 | 2 | 2 | **full-function** |
| LED driver `SDB` | 1 | 1 | 1 | 1 | LF ok |
| Expansion SDA/SCL/SCK/MOSI/CS/DC | 6 | 6 | 6 | 6 | **full-function** |
| Expansion RST/INT | 2 | 2 | 2 | 2 | LF ok |
| Link VBUS switch EN | 1 | 1 | — | 1 | LF ok |
| Local CC1/CC2 sense | 2 | 2 | 2 | 2 | LF ok, must be `AINx` pads |
| LED boost EN (disable only, pulled up), expansion LDO EN | 2 | 2 | 2 | 2 | LF ok |
| Battery sense + divider EN | 2 | 2 | 2 | 2 | LF ok, sense must be an `AINx` pad |
| Encoder A/B | — | 2 | — | 2 | LF ok |
| Bootloader button | 1 | 1 | 1 | 1 | LF ok |
| Module ID (rev 5) | 1 | 1 | 1 | 1 | LF ok, must be an `AINx` pad |
| KTS1693 `ACOK`, local + link (rev 5) | 2 | 2 | 2 | 2 | LF ok |
| LFXO crystal XL1/XL2 | 2 | 2 | 2 | 2 | dedicated |
| **Total** | **41 / 47** | **43 / 47** | **34 / 47** | **45 / 47** | |
| LF-class uses / spill onto full-function | 27 / 6 | 31 / 10 | 22 / 1 | 31 / 10 | |
| Full-function pads used | 18 of 24 | 20 of 24 | 11 of 24 | **22 of 24** | |

**The core's union is the binding budget: 45 of 47, 22 of 24 full-function pads.**
That is tight but fits, and nothing in it is speculative. **Rev 7 and earlier counted
23 full-function pads**; Raytac's pin table (MDBT50Q-1MV2 datasheet version L,
2023-05-24, §2.5) marks 21 pads LF-only and leaves 27, of which XL1/XL2 (P0.00,
P0.01) and nRESET (P0.18, the reset tactile) are taken, so 24. **Decided 2026-09-14:
keep both `ACOK` lines.** If Phase 3 needs a pin, the link `ACOK` goes first: link faults are also visible as a handshake with no
VBUS. Four `AINx` pads per core (battery, CC1, CC2, ID) out of eight. **Pair 2's
through-traces on `right` use no pins** and stay on the key board, never reaching
the core's connectors: an unpowered `right` would otherwise clamp the numpad's UART
through its ESD diodes.

`left`'s two pair-2 pins must both be full-function pads, since either may end up
as TX or RX after orientation detection.

Rev 2 counted separate cable-detect and wake lines, which had no conductor in the
link cable. Both now live on the UART RX pin.

Encoder push switch sits in the key matrix. USB D+/D−, SWDIO/SWDCLK and VBUS are
dedicated pads costing no GPIO.

Peripheral instances on `left`: UARTE0 + UARTE1 + TWIM0 (LEDs) + TWIM1 (expansion)
+ SPIM3 (expansion) do not collide. Satellites use UARTE0 only.

**Pad assignment (E12, Phase 3, 2026-09-15).** Pad numbers and edges from KiCad's
`RF_Module:Raytac_MDBT50Q` footprint; LF-only marking and `AINx` from the Raytac pin
table. Within one class and one edge, pads may still be swapped during layout; the
board devicetree follows the schematic.

| Edge | Pad | Pin | Class | Signal |
| --- | --- | --- | --- | --- |
| left | 3–6 | P1.10–P1.13 | LF | ROW0–ROW3 |
| left | 7, 8 | P1.14, P1.15 | LF | ENC_A, ENC_B |
| left | 9 | P0.03 / AIN1 | LF | MODULE_ID |
| left | 10 | P0.29 / AIN5 | LF | CC2_SENSE |
| left | 11 | P0.02 / AIN0 | LF | VBAT_SENSE |
| left | 12 | P0.31 / AIN7 | LF | CC1_SENSE |
| left | 13, 14 | P0.28, P0.30 | LF | COL7, COL8 |
| inner row | 56–61 | P1.04, P1.06, P1.07, P1.05, P1.03, P1.01 | LF | COL0–COL5 |
| right, top | 50 | P1.02 | LF | COL6 |
| right, top | 52, 54 | P0.09 / NFC1, P0.10 / NFC2 | LF | ROW4, ROW5 (`CONFIG_NFCT_PINS_AS_GPIOS=y`) |
| bottom | 16 | P0.27 | full | ACOK_LOCAL |
| bottom | 17, 18 | P0.00, P0.01 | dedicated | XL1, XL2 |
| bottom | 19 | P0.26 | full | LED_BOOST_EN |
| bottom | 20, 21 | P0.04 / AIN2, P0.05 / AIN3 | full | **spare** |
| bottom | 22, 23 | P0.06, P0.07 | full | U0_TX, U0_RX (pair 1) |
| bottom | 24, 25 | P0.08, P1.08 | full | U1_A, U1_B (pair 2) |
| bottom | 26 | P1.09 | full | LINK_SW_EN |
| bottom | 27 | P0.11 | full | ACOK_LINK |
| bottom | 29 | P0.12 | full | EXP_LDO_EN |
| right | 36, 37 | P0.14, P0.13 | full | LED_SCL, LED_SDA (TWIM0) |
| right | 38 | P0.16 | full | LED_SDB |
| right | 39 | P0.15 | full | BOOT_BTN |
| right | 40 | P0.18 | dedicated | nRESET (reset tactile) |
| right | 41, 42 | P0.17, P0.19 | full | EXP_INT, EXP_RST |
| right | 43, 44 | P0.21, P0.20 | full | EXP_DC, EXP_CS |
| right | 45, 46 | P0.23, P0.22 | full | EXP_MOSI, EXP_SCK (SPIM3) |
| right | 47, 48 | P1.00, P0.24 | full | EXP_SDA, EXP_SCL (TWIM1) |
| right | 49 | P0.25 | full | BAT_DIV_EN (also the module-ID pull-up top) |

Choices: the two NFC pads leak up to 10 µA between each other when held at different
levels (product spec v1.9 `INFC_LEAK`), so they carry two matrix rows, which idle at
the same level and are read against a 13 kΩ pull-down (0.13 V at 10 µA). The static
`ACOK_LOCAL` and `LED_BOOST_EN` sit next to the crystal pads, keeping edges away from
XL1/XL2. Four of the six LF `AINx` pads take the analogue reads; the two spare pads
are full-function and `AINx`-capable. **Unverified:** that the MDBT50Q-U1MV2 second
source uses the same pad numbering (its datasheet has not been read).

## 6. Connectors

**Link nets.** Two links, each on two connectors wired in parallel: a rear USB-C
receptacle and a seam pogo connector.

| Link | Nets |
| --- | --- |
| `left`–`right` | GND, VBUS, pair 1 TX/RX (`right`), pair 2 `P2_DN`/`P2_UP` (`numpad`), **6 nets** |
| `right`–`numpad` | GND, VBUS, pair 2 `P2_DN`/`P2_UP`, **4 nets** |

`P2_DN` carries `left` → `numpad`, `P2_UP` carries `numpad` → `left`. On `right`
they run as copper only on the key board, between its two link-board connectors.
Each link board joins its rear port and its seam board. The path has series
footprints and ESD clamps, but no MCU pin, no pull resistors and no core-board
connector. The ESD arrays have no
supply pin, so an unpowered `right` does not load the numpad's link.

**Link USB-C.** The pinout is **mirrored between the two ends of a cable**, because
a USB-C to USB-C cable passes D+ straight through. Identical pinouts at both ends
would put transmit against transmit and the link would be dead.

All four link ports use **the same link board PCB**, populated upstream (with
KTS1693, `J_LB` 9 pins) or downstream (without, `J_LBD` 10 pins; rev 7). It brings
the receptacle out as `LA` (A6=B6), `LB` (A7=B7), `S1` (A8), `S2` (B8), VBUS and
GND. The table below is therefore how each **key board** routes those nets.
Mirroring and pair 1 versus pair 2 are key-board copper; which population fits is
set by the header the key board carries.

| Pins | `left` link port | `right` upstream port | `right` downstream port | `numpad` link port |
| --- | --- | --- | --- | --- |
| A6 **tied to** B6 | pair 1 TX | pair 1 RX | `P2_DN` | pair 2 RX |
| A7 **tied to** B7 | pair 1 RX | pair 1 TX | `P2_UP` | pair 2 TX |
| A8 (SBU1) | pair 2, role detected | `P2_DN` | NC | NC |
| B8 (SBU2) | pair 2, role detected | `P2_UP` | NC | NC |
| A4 A9 B4 B9 | VBUS, no OVP, sourced via gated ILIM switch | VBUS, OVP, inward-only diode | VBUS, no OVP, sourced via gated ILIM switch | VBUS, OVP, inward-only diode |
| A1 A12 B1 B12 | GND | GND | GND | GND |
| A5 B5 | no CC resistors | no CC resistors | no CC resistors | no CC resistors |
| rest | NC | NC | NC | NC |

Tying A6=B6 and A7=B7 at each receptacle makes pair 1 and the `right`–`numpad`
link work in all four plug-orientation combinations. **SBU cannot be tied that
way**: there is one SBU pin per plug side, so tying A8 to B8 would short
`P2_DN` to `P2_UP`. Flipping a plug swaps them, and `left` resolves it at run time
(below). Full duplex throughout. **Series resistors sit at MCU pins, not at
connectors**: 470 Ω at every UART pin on every core, so two drivers fighting
through a mis-plug see ≥940 Ω and stay under 3.5 mA, and pair 2 does not collect a
resistor at each of `right`'s four connectors. ESD clamps at every connector.

**Cables.**

- `right`–`numpad`: **any USB 2.0 data cable.** Charge-only cables usually omit
  D+/D−; they will not link, and the handshake keeps VBUS off. **Rev 2 claimed any
  cable including charge-only works; it does not.**
- `left`–`right`: **a passive full-featured USB-C cable** (USB 3.x or USB4 class),
  because only those wire SBU. A USB 2.0 cable links `right` and leaves the numpad
  unlinked, so the split falls to BLE. **Active cables are unsupported**: they need
  VCONN, and the link has no CC. `left` flags the likely cause when `right` is
  handshaken on pair 1, the numpad is connected over BLE, and pair 2 stays silent.
- **A compliant cable crosses SBU**: plug-1 A8 (SBU1) is wired to plug-2 B8
  (SBU2). So with both plugs unflipped, `left`'s A8 meets `right`'s B8. Orientation
  detection handles it either way; it only matters for which cable orientation
  the §16 seam-plus-cable test calls "straight" and which "flipped".

**Seam pogo.** SAMZO's magnetic 2.54 mm pogo pairs, datasheet-verified:

| Half | Part | LCSC | Notes |
| --- | --- | --- | --- |
| Spring | `PR5L3715-4P-C-H` | C41361287 | 1.10 mm stroke, 0.7 mm working compression, 25 gf per pin, 2 A, ≤30 mΩ, 10 000 cycles, 3 µ" Au over 50 µ" Ni |
| Flat | `PR5L2820-4P-C-F` | C41361286 | mating flat contacts, same 21.2 mm housing and N/S magnet ends |

Both halves are **straight-pin through-hole parts**, so the connector face is
parallel to the board it is soldered to. Each seam wall therefore gets a small
**seam board** standing vertically at the wall. It carries the connector halves
and their ESD arrays and **cables to the link board on the same side**, so the rear
port and the seam join ahead of that link board's KTS1693. **One seam board
design** has two 4-contact positions (pair A → `LA`/`LB`, pair B → `S1`/`S2`);
4-net seams fit only pair A. Spring or flat halves are fitted as the position
requires. **Both halves share one land pattern** (SAMZO drawings GA0480/GA0481):
4 × Ø0.85 mm drills with Ø1.30 mm pads, 2.54 mm pitch, 7.62 mm span, ±0.05 mm.
They differ in tail length (spring 1.50 mm, flat 2.00 mm; the seam board is
therefore **1.2 mm thick**, so both protrude and the joints can be inspected), and their magnet poles are reversed (spring S…N, flat N…S
across the face), which is what makes a join attract one way and repel the other.
The silkscreen marks the S end for each half. **Pad numbering (2026-09-14): pad 1 is
the spring half's S end and the flat half's N end.** A join only attracts S to N, so
facing pads then mate k ↔ k, and a seam passes `LA`, `LB`, `S1`, `S2` straight through
exactly as a USB-C cable does; the §6 routing table holds for both paths, and a flat
seam board mounts flipped about the contact line relative to its spring mate. **The
first library footprints put pad 1 at the S end of both halves**, which mates k ↔ 5−k:
the two-pair seam would have met `LA` with `S2`, disagreeing with the cable on the
same link-board nets, and the one-pair seam would have put VBUS on GND. The numbering
is confirmed on samples (P5). **Rev 4
joined the daughterboard to the main PCB with a right-angle 2.54 mm header**, which
tied the seam part to the key board's outline and made it a solder job to
replace. The magnets at each housing's ends are polarised, so a reversed join
repels, and they add retention and alignment to whatever the case provides. **Rev 4
first listed `PR5L2820-4P-C-F` as right-angle spring pins; it is the flat, vertical
half.** The family is drawn from 2 to 12 contacts, but only 2–5 are stocked, so the
6-net seam uses two 4-contact pairs:

| Seam | Spring half | Flat half | Contacts |
| --- | --- | --- | --- |
| `left`–`right` | 2 on `left`'s seam board | 2 on `right`'s left seam board | pair A: VBUS, TX1, RX1, GND; pair B: GND, `P2_DN`, `P2_UP`, VBUS |
| `right`–`numpad` | 1 on `right`'s right seam board | 1 on `numpad`'s seam board | pair A only: VBUS, `P2_DN`, `P2_UP`, GND |

Every signal contact sits next to a ground or VBUS contact, and VBUS gets two
contacts on the busier seam. A detached `numpad` exposes only flat contacts. A
detached `right` exposes flat contacts on one wall and, on the other, spring pins
whose VBUS is off and whose pair-2 contacts float. `right`'s numpad-side pins, with
`right` joined to `left` and no numpad present, reach `left`'s pair-2 pins, which
are pulled-down inputs until a numpad is detected. Worn halves are replaced with
their seam board, which unplugs. TX on one side meets RX on the other at net level; mirrored
geometry is checked in the Phase 4 3D export.

The seam fixes pair-2 orientation; the rear cable does not. If both paths are
connected at once with a flipped cable, `P2_DN` and `P2_UP` short together through
`left`'s two pins. The detect rule below turns that into an inert state.

**Detect, handshake, wake.** All on the UART pairs, independently per pair.

- *Detect, pair 1*: `left`'s RX has a ≥100 kΩ pull-down; `right`'s weak TX pull-up
  lifts it. `left`'s pair-1 TX is a pull-up-only input until then; once RX is
  lifted `left` drives TX and `right`'s RX sees a powered central. **Rev 5 drove
  `left`'s TX always, which pushed ~5 mA through 470 Ω into the clamp diodes of a
  switched-off, seam-joined `right`, back-powering it and draining `left`'s
  cells.** On link loss TX returns to input.
- *Detect and orientation, pair 2*: both of `left`'s pair-2 pins idle as GPIO
  inputs with external ≥100 kΩ pull-downs and **no internal bias** (the nRF52840's
  ~13 kΩ internal pull-down would fight a satellite's weak pull-up). The numpad's weak TX pull-up lifts exactly one of them: that
  pin becomes RX, the other TX, and `left` applies the matching pinctrl state to
  UARTE1: stop RX, suspend the device, `pinctrl_update_states()` with the swapped
  default and sleep states, resume (§9). **Both pins high means the two nets are shorted**,
  typically a flipped cable in parallel with a joined seam: `left` drives neither,
  flags "remove the rear cable", and re-checks. Orientation is re-detected on every
  link-up. On link loss both pins return to pulled-down inputs.
- *Satellites speak only when spoken to*: a satellite's TX stays undriven, a weak
  pull-up only, until it receives a valid `PING`. It keeps driving while its RX
  stays high and returns to pull-up on link loss. Two satellites cabled together
  never ping, so neither ever drives.
- *Handshake*: on detect, `left` sends `PING(nonce)` on that pair. A satellite
  answers `PONG(sat_id, nonce)`. Only then is the satellite marked present. An echo
  of our own `PING` is a loopback, for example a BC1.2 charger shorting D+ to D−,
  and the pair stays down. **A `sat_id` already present on the other pair is
  rejected**, which covers `right`'s two ports cabled to each other.
- *VBUS gating*: `left` enables its link switch only after `right` handshakes on
  pair 1. `left` sends `LINK_STATUS(all_present, pair2_up)` to `right` over pair 1;
  `right` enables its numpad-port switch only while `pair2_up` is set and fresh.
  Loss of either pair, or a stale flag, drops the switch.
- *Source mapping*: the source id comes from `sat_id`, not from the pair, and
  matches the BLE transport's slot for that satellite. A numpad cabled straight into
  `left`'s port answers on pair 1 and still maps to the numpad's slot.
- *Hysteresis*: the transport drops to BLE after ~300 ms of link loss, and returns
  to wired only after all satellites have stayed handshaken ~2 s **and** no key has
  been held for ~1 s. On a switch, keys held on the lost source are released.
- *All-or-nothing flag*: `left` tells every linked satellite whether **all**
  expected satellites are present, over its own pair. A satellite's wired transport
  reports available only while that flag is set; otherwise a cabled satellite would
  stay on wired while the central listens on BLE, and go dead.
- *Wake*: after an idle timeout `left` parks both UARTEs and arms `SENSE` on each
  known RX pin. A satellite with a keypress holds TX low for a break, then resends
  once `left` re-enables. The numpad's break reaches `left` directly through
  `right`'s copper. This is what makes the §16 idle measurement achievable.

**Local USB-C, all modules, on the USB port board**: 2 × 5.1 kΩ CC pulldowns with
both CC pins also routed to the core's `AINx` pads, KTS1693 OVP switch (TVS2200
footprint, not fitted), SMF6.0A behind it and USBLC6-2SC6 on D+/D− (§4) **with its
`VBUS` pin on the KTS1693's `OUT`, never on connector VBUS** (5.5 V abs-max; ST
allows NC as the fallback). The 10 V
bulk cap and soft-start that keep inrush inside the USB budget sit on the core. On `left` this is the host port. On `right` and `numpad` it is UF2 DFU and
power only; `ZMK_USB` requires central role, so a satellite in a PC will not type.

Firmware reads vRd on the active CC. On `left` it sets the whole-keyboard LED
budget, which `left` shares with both satellites through the link VBUS chain. A
satellite on its own port uses its own reading for its own LEDs. A satellite
powered over the link budgets from `left`'s reading, sent in `LINK_STATUS`, even
if `right`'s local USB happens to be the source winning `right`'s `VBUS_IN` OR;
`right`'s numpad-port current limit bounds the worst case either way.

| vRd | Advertised | LED budget at ~5 V |
| --- | --- | --- |
| 0.25–0.61 V | default USB, 500 mA | ~450 mA total, scaled across the modules on that port |
| 0.70–1.16 V | 1.5 A | uncapped (full board ≈ 507 mA at the rail) |
| 1.31–2.04 V | 3.0 A | uncapped |

**Expansion connector**, 12-pin 1.0 mm JST-SH, all modules:

```
1 GND  2 3V3(gated LDO)  3 5V(local USB only)  4 SDA  5 SCL  6 SCK
7 MOSI 8 CS              9 DC/GPIO            10 RST 11 INT 12 GND
```

Pin 2 is a real regulated 3.3 V from a gated LDO off the LED rail, **budgeted at
150 mA per module** (2026-09-15; on a satellite it draws from `left`'s link chain,
§4). ESD protection
required: this is exposed user-facing I/O. **It sits on the expansion board, at the
case wall, with its ESD, cabled to the core on `J_EXP` (P17, 2026-09-15)**; the
expansion LDO stays on the core. A worn socket or an ESD hit costs the small board.
The socket is a JST **SM12B-SRSS-TB** (side entry). A TPD4E05U06 (3V3, 5V, SDA, SCL)
and a TPD6E05U06 (SCK, MOSI, CS, DC, RST, INT) clamp every non-GND pin at the socket,
with 100 nF on each rail (2026-09-15). SLVSBO7O gives VRWM 5.5 V and VBR ≥6.5 V at
1 mA, so 5V stays below breakdown up to the KTS1693's 5.95 V OVLO trip. Bus pull-ups
and bulk capacitance stay on the core.

**Board interconnect.** Internal cables use one locking wire-to-board family, JST GH
(1.25 mm pitch, positive lock, up to 15 contacts) as the proposal (open question
P9). **Connectors are split by function, and every header pin count is unique**
except the two identical battery connectors. A cable therefore cannot reach the
wrong header: 5 V from a USB port board cannot land on the matrix, for instance.
Power nets get ≥2 contacts each, and GND is spread across every connector.
**Locking is required.** If GH fails P9, the replacement must be another
positive-lock family near 1.25 mm, not friction-lock JST SH.

| Connector | Contacts | Between | Nets |
| --- | --- | --- | --- |
| `J_BAT_A`, `J_BAT_B` | 4 | core ↔ battery board | PACK+ ×2, GND ×2 |
| `J_DIAL` | 5 | key board ↔ dial board (`right`) | ENC_A, ENC_B, ENC_C (GND), SW_ROW, SW_COL; the push switch's matrix diode is on the dial board; **order 1 SW_ROW, 2 ENC_A, 3 GND, 4 ENC_B, 5 SW_COL** (reversal-safe: an end-reversed cable swaps A/B and ROW/COL only, 2026-09-15) |
| `J_ROW` | 7 | core ↔ key board | ROW0–5, GND; **order 1 ROW0, 2 ROW1, 3 ROW2, 4 GND, 5 ROW3, 6 ROW4, 7 ROW5** (reversal-safe: rows mirror, 2026-09-15) |
| `J_SEAM` | 8 | link board ↔ seam board | VBUS ×2, GND ×2, `LA`, `LB`, `S1`, `S2`; **order 1 VBUS, 2 LA, 3 LB, 4 GND, 5 GND, 6 S1, 7 S2, 8 VBUS** (pogo contact order, reversal-safe, 2026-09-14) |
| `J_LB` | 9 | key board ↔ upstream link board (`right` upstream, `numpad`) | VBUS ×2, GND ×2, `LA`, `LB`, `S1`, `S2`, `ACOK` (open-drain, wired-OR on `right`); **order 1 VBUS, 2 LA, 3 LB, 4 GND, 5 ACOK, 6 GND, 7 S1, 8 S2, 9 VBUS** (reversal-safe, 2026-09-14) |
| `J_LBD` | 10 | key board ↔ downstream link board (`left`, `right` downstream; rev 7) | VBUS ×2, GND ×3, `LA`, `LB`, `S1`, `S2`, `LINK_SW_EN` (no `ACOK`); **order 1 VBUS, 2 LA, 3 LB, 4 GND, 5 GND, 6 LINK_SW_EN, 7 GND, 8 S1, 9 S2, 10 VBUS** (reversal-safe, 2026-09-14; pin 6 was NC until P14, 2026-09-15). Reversed, `LINK_SW_EN` meets GND at both ends: the switch stays off, and the driving GPIO's **10 kΩ series resistor on the core** holds it to ≤0.35 mA (2026-09-15; `ON` needs ≥1 V against a 500–650 kΩ smart pull-down, so turn-on is unaffected) |
| `J_EXP` | 15 | core ↔ expansion board (P17, 2026-09-15) | 5V ×2, 3V3 ×2, GND ×3, SDA, SCL, SCK, MOSI, CS, DC, RST, INT; **order 1 5V, 2 GND, 3 3V3, 4 SCL, 5 SDA, 6 RST, 7 DC, 8 GND, 9 CS, 10 MOSI, 11 INT, 12 SCK, 13 3V3, 14 GND, 15 5V** (mirrored, 2026-09-15: pin k and 16−k carry the same net class, so reversed, rails and GND meet themselves; the signal pairs SCL–SCK, SDA–INT, RST–MOSI, DC–CS never face two push-pull drivers). Rails get two contacts each per the rule above, replacing P17's "spare pins to GND" |
| `J_USB` | 11 | core ↔ USB port board | VBUS_LOCAL ×3, GND ×3, D+, D−, CC1, CC2, `ACOK`; **order 1 VBUS, 2 GND, 3 CC1, 4 GND, 5 D+, 6 VBUS, 7 D−, 8 ACOK, 9 CC2, 10 GND, 11 VBUS** (reversal-safe, 2026-09-14) |
| `J_LED` | 12 | core ↔ key board | **LED_RAIL ×2**, GND ×4, **VSYS ×2** (driver `VIO`), SDA, SCL, `SDB`, ID; **order 1 LED_RAIL, 2 GND, 3 SDA, 4 VSYS, 5 SDB, 6 GND, 7 GND, 8 ID, 9 VSYS, 10 SCL, 11 GND, 12 LED_RAIL** (mirrored, 2026-09-15). Rev 7 listed LED_RAIL ×3 and VSYS ×1, which cannot be reversal-safe on 12 pins: one rail contact would face a signal, and an end-reversed cable would put the LED rail on an MCU pin or `VSYS`. Reversed now, only SDA↔SCL and `SDB`↔ID swap (the `SDB` GPIO into the ID resistor, ≤0.33 mA) |
| `J_COL` | 13 | core ↔ key board | COL0–8, ENC_A, ENC_B, GND ×2; **order 1 GND, 2–10 COL0–COL8, 11 ENC_A, 12 ENC_B, 13 GND** (reversal-safe: GND meets GND, so no driven column ever faces GND, 2026-09-15) |
| `J_LINK` | 14 | core ↔ key board | VBUS_LINK_IN ×2, VBUS_IN_OUT ×2, U0_TX, U0_RX, U1_A, U1_B, LINK_SW_EN, `ACOK_LINK`, GND ×4; **order 1 VBUS_LINK_IN, 2 GND, 3 U0_TX, 4 U1_A, 5 GND, 6 LINK_SW_EN, 7 VBUS_IN_OUT, 8 VBUS_IN_OUT, 9 ACOK_LINK, 10 GND, 11 U1_B, 12 U0_RX, 13 GND, 14 VBUS_LINK_IN** (reversal-safe, 2026-09-15: each VBUS net meets itself, TX↔RX and A↔B swap through the 470 Ω, LINK_SW_EN's 10 kΩ meets the pulled-up open-drain `ACOK_LINK`) |
| Expansion | 12, JST-SH | expansion board ↔ user | above |

- **Host D+/D− cross one cable** (USB port board → core), kept ≤100 mm, with the
  two conductors adjacent and GND on both sides. Full-speed USB needs no controlled
  impedance at that length, but the eye is still checked in §16.
- **Contact current.** `J_LED` carries at most ~507 mA of rail current on 2
  contacts (~254 mA each, 2026-09-15; was 3). `J_USB` on `left` carries the whole keyboard on USB. `J_LINK`'s
  VBUS_IN_OUT and `J_LBD`'s VBUS are bounded by the TPS22950L limit for any fault
  past the downstream link board (latch-off above `IHCD` 1.2–1.9 A with 624 Ω). Since P14 (2026-09-15) the switch sits after
  that cable, so a short in the cable itself is bounded only by the source feeding
  `VBUS_IN`: a local port's KTS1693 `ISET` (1.82–2.18 A), or on `right`'s link input,
  `left`'s TPS22950L. Contact counts are rechecked
  against the chosen family's derated rating in Phase 3.
- **`right`'s two link headers sit at opposite ends of its key board** and have
  different pin counts (`J_LB` 9 upstream, `J_LBD` 10 downstream, rev 7), so
  neither link board can be cabled into the other position; each cable is also
  cut too short to reach.
- **Pair 1 and pair 2 cross internal cables**: link board → key board → core on
  `left` and `numpad`, and seam board → link board on every side. §13 adds them
  to the pair-2 capacitance budget.

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
  is **4.1 V green, 4.0 V blue**. On battery the 4.7 V rail leaves ~0.2 V. On USB
  the rail is VBUS_IN, 4.75 V minimum at the receptacle less path drops, so a
  max-bin green or blue part on a weak port can fall a little short of its set
  current and shift colour; SunLED offers Vf sorting to ±0.1 V if that shows in
  Phase 1. On a healthy 5 V port the rail raises CS dissipation instead; driver
  thermal is a §16 check.
- **The LEDs are ESD-fragile**: 250 V HBM on blue. Assembly-side handling note; in
  the product they sit under the plate with no touch path.
- Dedicated I2C bus, not shared with the expansion connector. The driver accepts
  1 MHz but **nRF52840 TWIM tops out at 400 kHz**, so a 192-byte bulk write is
  ~5 ms plus page-select overhead.
- Zephyr ships the driver upstream, binding `issi,is31fl3733`. **Verified: it
  implements `write_channels` as a single I2C burst** and skips the page
  unlock/select when the page is already current. It also exposes
  `is31fl3733_current_limit()` for the global current register, which is how the
  battery and USB budgets are enforced in hardware rather than by scaling PWM.
- **Caps need not be shine-through.** On opaque caps the indication reads as glow
  around the cap edge; legibility is checked in the Phase 1 test cell.

## 8. Profiles + dial

- 9 profiles. `CONFIG_BT_MAX_PAIRED=11`, because with BLE split compiled in
  `ZMK_BLE_PROFILE_COUNT = BT_MAX_PAIRED − ZMK_SPLIT_BLE_CENTRAL_PERIPHERALS`.
  `BT_MAX_CONN` ≥3: host plus two BLE split peripherals when the split is on BLE.
- The dial is on `right`, a peripheral. Its sensor events cross the split to
  `left`, where the keymap's sensor bindings and the profile behavior run.
- Dial: turn = volume. Fn + turn = preview. Fn + press = commit. No press, no
  change; pending reverts after a few seconds.
- Indication: keys 1–9 dim backdrop, pending bright, active in a second colour,
  single flash on commit then fade.
- Number row splits **6/3**: 1–6 on `left`, 7–9 and 0 on `right`, so the central
  lights 1–6 locally and drives `right`'s LEDs for 7–9. The indicator reads key
  positions from the matrix transform rather than hard-coding the split.
- **Cross-module lighting is tunnelled through `INVOKE_BEHAVIOR`.** The split
  protocol's central commands are `POLL_EVENTS`, `INVOKE_BEHAVIOR`,
  `SET_PHYSICAL_LAYOUT` and `SET_HID_INDICATORS`, with no generic payload. A custom
  behavior on each peripheral takes `(param1, param2) = (command, argument)`:
  indicator state, effect id + start tick, brightness cap. Satellites render
  locally; no per-frame pixels cross the link. Works over wired and BLE.
- Effect layer needs an **overlay** so indication borrows 9 keys and returns them.
- Stock ZMK cannot express preview-then-commit; `&bt BT_SEL n` takes a
  compile-time index. Custom behavior in our module.

## 9. Firmware

Verified against ZMK source at `main` (last checked at `641514a`, 2026-08-21):

| Fact | Consequence |
| --- | --- |
| `central.c` holds a single `active_transport`; `transport_status_changed_cb()` re-selects only when the active transport reports `DISCONNECTED` | **all-or-nothing**: one satellite cannot be on BLE while the other is wired. Rev 2 assumed per-link failover |
| `ZMK_SPLIT_BLE` and `ZMK_SPLIT_WIRED` are not mutually exclusive; both carry `*_PRIORITY` ints | both compile in |
| Stock wired `get_status()` is driven by `detect-gpios`, reporting `ALL_CONNECTED` or `DISCONNECTED` | our transport reports available only when every satellite has handshaken |
| `#define WIRED_PERIPHERAL_COUNT 1` — hardcoded in `zmk/split/central.h` | with BLE split at 2 peripherals, `MAX(2,1)=2` sizes core arrays correctly. **No core patch** |
| Central commands: `POLL_EVENTS`, `INVOKE_BEHAVIOR`, `SET_PHYSICAL_LAYOUT`, `SET_HID_INDICATORS`; invoke carries `behavior_dev[16]` + two `uint32` params | cross-module lighting tunnels through a behavior |
| Peripheral raises `BATTERY_EVENT` on any transport under `ZMK_BATTERY_REPORTING`; the central handles it in shared `central.c` under `ZMK_SPLIT_BLE_CENTRAL_BATTERY_LEVEL_FETCHING` | satellite battery works over wired too, as long as that BLE-named symbol is enabled, which BLE split being compiled in permits |
| Peripheral also holds a single active transport chosen by priority | the all-present flag is required, or a cabled satellite picks wired while the central is on BLE |
| `ZMK_USB` depends on central role | host port only on `left` |
| `ZMK_SPLIT_TRANSPORT_CENTRAL_REGISTER` uses `STRUCT_SECTION_ITERABLE_NAMED`, gathered link-wide | a module can register a transport |
| `lithium_ion_mv_to_pct()` returns 0 below 3450 mV | a 2-cell pack would report 0 % forever; needs a real curve |
| Peripheral `peripheral.c` subscribes to `zmk_sensor_event` under `ZMK_KEYMAP_HAS_SENSORS` and reports `SENSOR_EVENT` through the active transport; the wired transport serialises it and the BLE service has a sensor characteristic; `central.c` re-raises it as `zmk_sensor_event` | **the dial works on a peripheral** over both transports. The shared devicetree declares `zmk,keymap-sensors` on all three shields so indices and binding counts match, with the encoder node enabled only on `right`. Only `channel_data[0]` crosses, which is all an encoder uses |
| Zephyr (ZMK's `v4.1.0+zmk-fixes`): `CONFIG_PINCTRL_DYNAMIC` + `CONFIG_PINCTRL_NON_STATIC` expose `pinctrl_update_states()` and `PINCTRL_DT_DEV_CONFIG_GET`; the nRF UARTE driver applies `PINCTRL_STATE_DEFAULT` on PM resume and `SLEEP` on suspend, and nRF pinctrl writes the UARTE `PSEL` registers | **pair-2 orientation swap is supported** without re-initialising the driver: stop RX, `PM_DEVICE_ACTION_SUSPEND`, update both states, `RESUME`. Needs `CONFIG_PM_DEVICE`; the driver asserts if RX is still enabled at suspend |

**The remaining gap.** The wired transport is single-peripheral by construction:
`if (source != 0) return -EINVAL;`, `get_available_source_ids()` returning one id,
and the UART buffers, event publishing and async state all instance-0 singletons
via `DT_INST_*`, plus `static const uint8_t peripheral_id = 0` on the peripheral.
Generalising means per-instance state iterated with `DT_INST_FOREACH_STATUS_OKAY`
and a source-id devicetree property. Nearly every static becomes per-instance, so
call it **a rewrite of that file**, not a patch. On `left` it runs two UART
instances, one per pair. Source ids must match the BLE transport's peripheral slots
so a failover does not reshuffle which module is which. Satellites run the
peripheral side of the same file with a single UART.

**Delivery: out-of-tree ZMK module.** Parallel transport registered through the
iterable section, in-tree `ZMK_SPLIT_WIRED` disabled. `west.yml` pins an exact ZMK
commit; the required CI build uses the pin, and a weekly non-blocking canary builds
against ZMK `main` and opens an issue on breakage. Bumps are deliberate. Week-1 smoke test: a 10-line
stub transport that logs at init, to prove the module's translation unit is not
dropped by the linker.

Module contents: multi-peripheral wired transport with handshake, `sat_id` source
mapping, duplicate-`sat_id` rejection, pair-2 orientation detection, satellite TX
discipline, `LINK_STATUS` (all-present, `pair2_up`, budget), asymmetric hysteresis
with held-key release, VBUS gating on both switches and break wake; IS31FL3733 effect layer; cross-module lighting behavior;
overlay mechanism; preview-then-commit profile behavior; USB CC current-budget
reader; battery state-of-charge sensor driver with a NiMH/alkaline lookup table and
the ~2.05 V system-off threshold; TPS22950L fault handling (latched off until a
fresh handshake); module-ID check with safe mode; `ACOK` fault reporting as
blink codes (no `ACOK` from downstream link boards, rev 7); **peripheral BLE advertising stopped while the wired transport is
active** and restarted on link loss (rev 6), without which §1's "nothing
transmits" is false, since a ZMK peripheral advertises whenever it has no BLE
central regardless of the active split transport.

**Thresholds (rev 6).** Every firmware threshold in one place, with how it is
measured, so 7a tests numbers rather than "~":

| Threshold | Value | Measured as |
| --- | --- | --- |
| Lighting scale-down start | 2.30 V | `VBAT` SAADC, during a lighting frame (loaded) |
| Lighting off | 2.15 V | same |
| System-off | 2.05 V | `VBAT` SAADC with lighting off (unloaded), averaged over 8 reads |
| Hardware UVLO (backstop) | ~1.9 V at the pack | TPS3840PH18 via BAT54C, on the loaded net; +100 mV hysteresis is smaller than the ~200 mV IR drop at 730 mA, which is why lighting is off well before this point |
| Wired → BLE | 300 ms of link loss | per pair |
| BLE → wired | 2 s all-present **and** 1 s no key held | |
| `pair2_up` flag freshness | 500 ms | `right` drops its numpad switch when stale |
| Module ID bands | 0.09 / 0.32 / 0.69 ±0.06 | ratio to internal `VDD`, GPIO top high, same gain and reference on both channels, `TACQ` ≥10 µs; worst case 0.085–0.097 / 0.308–0.330 / 0.675–0.699 (F6, Phase 3) |

**Board and shields follow the hardware split.** The core is one Zephyr **board**
definition: MCU, power-path GPIOs, connector pinout and the expansion bus, shared
by all three builds. `left`, `right` and `numpad` are **shields** for their key
boards: matrix transform, LED count, link-pin roles, dial. At boot, before matrix
scan or link bring-up, firmware reads the module ID (§2a) and compares it to the
shield's expected band. On a mismatch it enters the safe mode and stays there until
reflashed. The UF2 bootloader is untouched, so a swapped core is reflashed from its
USB port board the usual way.

**Rollover.** The diode-per-key matrix already makes ghosting impossible, so the
only limit is the HID report. Set `CONFIG_ZMK_HID_REPORT_TYPE_NKRO=y`. Peripherals
report key *positions* and the central aggregates them with no count limit. Host
support for the NKRO descriptor over BLE varies by OS and is **verified per host**,
not assumed.

**Boot protocol.** Set `CONFIG_ZMK_USB_BOOT=y`, or a BIOS/UEFI gets no keyboard at
all. Boot protocol is 6 keys by specification.

**Deep sleep.** Stock `ZMK_SLEEP`. Cabled, the UART break wakes the central.
Untethered, a sleeping satellite cannot wake a sleeping central: press a key on
`left`. Documented in the build guide as a known limitation.

Set matrix `debounce-press-ms`/`debounce-release-ms` and measure in 7a.

Milestones:

- **7a bring-up** — 3 shields, matrix transforms, keymap, 9 profiles, dial→volume,
  battery reporting, lighting caps. Runs on **BLE split alone** to prove hardware.
- **7b wired link** — the multi-peripheral transport, handshake, pair-2
  orientation, VBUS gating, wake; all-or-nothing failover verified by unlinking a
  module mid-typing.

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

In scope, co-gated with Phase 1, because module joining and AA placement are the
two things most likely to invalidate PCB outlines.

- **Joining**: alignment and retention between modules — magnets, dovetails or
  latches — with the pogo pairs' own polarised magnets contributing alignment,
  some retention and reverse-join rejection. Working compression is 0.7 mm of a
  1.1 mm stroke at 25 gf per pin (100 gf per 4-contact pair, 200 gf on the
  `left`–`right` seam), which sets both the seam-gap tolerance and the minimum
  retention force.
- **Seam wall budget**: three cases need two walls at each of two seams. Resin/SLA
  holds ~1.5 mm, so about **6 mm** of dead space appears mid-field. The pogo pocket
  must fit inside that budget or the ~468 mm width grows. The `left`–`right` seam
  carries two 4-contact magnetic pogo pairs, ~21 mm each along the wall, on vertical
  seam boards; the seam board's cable exits inward, away from the wall; the ~6 mm depth budget must hold both halves' housings
  (2.7 mm spring, 2.8 mm flat) plus working compression, checked in the Phase 1
  print.
- **Rear link ports**: USB-C link receptacles face the rear for separated use, each
  on its own link board screwed to the rear wall. `left` has one, `right` two (one
  at each end), `numpad` one. The host port is on `left`, on a USB port board.
- **Core placement**: the core sits flat in the case, off the key board's
  footprint. The MDBT50Q's antenna end overhangs no copper from any board, and
  Raytac's keepout is honoured in all three case designs. On `left` that is the
  **rear outer corner, behind the key field**, required for the host radio: the
  outer palm-rest corner is under the user's palm, and a hand within a few cm of
  a 2.4 GHz antenna costs 10–20 dB. On the satellites it is the rear or outer
  edge, whichever the case allows, likewise clear of the palm rest. The slide switch, reset and bootloader button
  face the case wall through openings; the expansion board has its own opening. The 46 mm Qi2 keepout is
  placed with it (§13).
- **External connector service (2026-09-14)**: every USB port board, link board and seam
  board is reachable from inside the opened case without removing another board, held by
  M2 screws, and connected by one locking cable. A worn or damaged socket or pogo half is
  fixed by swapping that board; the build guide gives the steps per board. The expansion
  connector follows the same rule on its own expansion board (P17, 2026-09-15); that
  board, not the core, faces the case wall.
- **Battery door**: tool-less, in the palm-rest floor. Battery boards are screwed in
  behind it with the holders facing the door, so changing cells never opens the
  case.
- **Cable routing**: every internal cable has a routed channel and a clip point in
  the case, clear of the switch pins, the hotswap sockets and the reverse-mount LED
  holes. Service loops are just long enough to lift a board out.
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
- **Cells live under the palm rest**, not under the keys. The numpad's palm rest
  section is the smallest, but **it takes two battery boards like the others**, so
  every module has the same runtime and the same one-pack fallback. The numpad's
  palm rest is sized to fit both. Every core has both battery connectors, so all
  three cores stay
  identical.
- **Height**: floor is set by the AA holder. 14.5 mm cell + walls ≈ 16 mm, + 1.6 mm
  PCB + plate + ~11 mm MX above plate + keycap ≈ **~35 mm** before the arc's
  vertical component, against the K860's 48 mm including palm rest and tilt.
- Fastening: standoffs, screw positions, mount style, case DFM.
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
  **Core PCB placed 2026-09-16**: outline **32 × 90 mm**, 1 mm corner radius, origin
  (100, 100). Antenna end is the top short edge with the Raytac 3.8 mm no-copper strip
  across the full width (ver L §2.3; the strip holds only the two NPTH M2 corner holes);
  key-board headers J407/J408/J409/J406 down the left long edge, J404/J405/J402/J403 and
  the Tag-Connect down the right, SW401–403 on the bottom short edge, power chain in the
  middle channel. Konnect placement score 100/100, DRC errors only the 8 internal to the
  SW401/SW402 stock footprints (P18). U407 has no footprint, so 3 × 3 mm is left free
  beside L403 and parity reports it.
  **Core: 4 copper layers (2026-09-16)**, for the MCU module, USB D+/D− and the two
  boosts over solid ground; the project carries a placeholder 0.2 / 1.04 / 0.2 mm
  dielectric split until the fab stackup is chosen. The core has **4× M2 corner
  holes** (`MountingHole_2.2mm_M2_ISO7380`, H401–H404, 2026-09-16).
  **Core routing prep (2026-09-16):** the antenna strip is two rule areas on all copper
  layers (tracks/vias/pours blocked across the strip; pads blocked except the two NPTH
  holes). **Stackup stays generic** until a fab is chosen (0.127 mm track/space, 0.2 mm
  drill). Net classes: `VBUS_HI` (`VBUS_IN`, `VBUS_LINK_IN`, `VBUS_LOCAL`) 0.6 mm on
  outer layers only (IPC-2221 estimate, ~20 °C rise at 2.2 A on 1 oz; not a fab figure),
  `POWER` 0.4 mm, `USB` pair 0.2 mm / 0.2 mm gap (Full Speed, no impedance target),
  signal 0.2 mm / 0.15 mm clearance.
  **Core autoroute (2026-09-16):** Freerouting 2.4.1 routed everything except the
  hand-routed copper (locked during the run), with In1/In2 set as plane layers so no
  signal crosses the GND or VSYS/VBAT planes. The crystal (`XL1`/`XL2`) and LED boost
  (`SW_LED`, `LED_BOOST` at U409/C421/C422) stay unrouted until their P18 footprints are
  verified.
  **Core rip-up (2026-09-24):** a scripted rip-up-and-reroute pass (`build/core-rip/`,
  transactional: a change is kept only if every net it disturbs re-joins and DRC is
  unchanged) closed `V3P3_LDO` (0.4 mm), `EXP_SCL` and `SWDCLK`. `LED_ST` was boxed in by
  the `LED_BOOST` U410.6 → C422 track wrapping over U410, so **`LED_BOOST` now hops to
  B.Cu**: 0.28 mm centred stub from U410.6 (≤ 1.1 mm, between U410.7 and U410.5) → via
  (121.2, 177.45) → 0.4 mm on B.Cu under U410 → via (116.9, 176.9) → C422.1; two 0.6/0.3 mm
  vias carry the ~320 mA IS31FL3733 SW-phase peak. **R434 rotated 180°** (pad 1 `PR_LED`
  now at the top, pad 2 `LED_ST` at the bottom) so `LED_ST` and `PR_LED` no longer cross at
  its pads. 7 real connections left for the interactive router.
  **U401 escape rule (2026-09-25):** the MDBT50Q-1MV2's staggered right-hand pad rows
  (x 119.75 / 120.65, 0.8 mm pitch per row) leave 0.40 mm between outer pads, less than a
  0.2 mm track at 0.15 mm clearance needs (0.50 mm). `hardware/core/core.kicad_dru` and a
  non-blocking rule area `U401_ESCAPE` (x 109.2–122.8, y 103.8–117.5, F/B.Cu) allow
  0.127 mm track and clearance (the generic 0.127 mm minimum) and 0.5 / 0.25 mm vias there
  for everything except `POWER`/`VBUS_HI`/`USB`; KiCad's router picks 0.127 mm / 0.5 mm vias
  inside the area by itself (`opt`). Rule values carry units (`0.127mm`): KiCad 10.0.6
  silently ignores a rules file with bare numbers (checked on a two-track test board).
  Tried and dropped: widening the outline to 34 mm (stretch at x 106.5 + full signal
  re-route ended at 12 open, the new lane is crossed by 71 fan-out tracks); the scripted
  rip-up with the working rule, on the original pin map and on a trial U401 pin swap, both
  end at the same 7 open (the swap's pads 20/21 sit right above crystal Y401).
- **Hotswap socket + reverse LED window + diode + stabiliser clearance inside one
  19.05 mm cell** is asserted, not proven. Phase 1 deliverable: one test cell
  printed 1:1 with a real socket, switch and opaque keycap in hand. **The LED goes
  south** (0, +5.08 mm): the MX north LED position collides with the Kailh
  socket body and its pad at (2.54, −5.08), which is why every hotswap RGB board
  is south-facing. The chosen switches must pass light through the south side of
  the bottom housing.
- **The KTS1693's WLCSP sets the fab class of the USB port and link boards.** A
  4 × 5 array at 0.4 mm pitch has six inner balls that cannot escape on economy
  rules (0.127 mm trace/space; a 0.2 mm via with 0.1 mm annular ring is a 0.4 mm
  land, the whole pitch). Those seven boards (downstream link boards included:
  same PCB, footprint unpopulated) are quoted with 0.15 mm vias and via-in-pad
  from the start. The P7 survey's leaded candidate is the **TI TPS25947**
  (TPS259470x/4x, QFN 2 × 2 mm, 0.45 mm pitch, rev 7), which escapes on economy
  rules; it is not footprint-compatible, so adopting it is a USB port and link
  board redesign.
- **No aqueous wash.** Kailh sockets trap flux in gold spring contacts and JLCPCB
  washes by default. Fab note, or hand-install sockets after wash.
- **RGB rotation** is a common JLC defect. Explicit CPL rotation per LED,
  first-article check on one board before the run.
- **FR4 plates**: three extra boards per build, no copper, outline + cutouts only.
- **Board designs and counts per keyboard** (§2a): 3 key boards, 3 cores, 3 USB
  port boards, 4 link boards (2 upstream, 2 downstream population), 4 seam boards,
  6 battery boards, 1 dial board, 3 plates. That is **9 PCB designs**: 3 key
  boards, core, USB port, link, seam, battery, dial, with the link board in two
  BOMs. The small boards can share one fab order, except the **seam board, which is
  1.2 mm** (SAMZO spring-half tails are 1.50 mm) and is ordered separately or panelled
  by thickness.
- **Assembly split.** Key boards, cores, USB port boards, link boards and the seam
  boards' ESD arrays need assembly-house placement (WLCSP, QFN, the MDBT50Q).
  Battery and dial boards are hand-solderable, **except the battery board's PTC
  (PTSLR12066V175): reflow or hot air only**, per Eaton ("generally manual/hand
  soldering is not recommended"), and it is **MSL 2a**, so opened reels need dry storage.
  THT pogo halves are hand-soldered.
  **MSL 3 LEDs**: bake note if reels have been opened.
- **Pair-2 through-traces on `right`**: ~200 mm between the two `J_LB` headers on
  the key board. Routed by hand on an inner layer over solid ground, kept clear of
  the 12 LED SW nets and the antenna keepout. Each header sits at its end of the
  board, so no stubs.
- Check `IS31FL3733` vs `-B` lifecycle and stock parity before committing.

## 13. Analogue and RF notes

- **SAADC**: internal 0.6 V bandgap reference, **not** `VDD/4` — with VSYS
  unregulated, a ratiometric reference reads constant. Sense **VBAT on the pack
  branch**, ahead of the mux, so pack level is known on USB too. Divider keeps the
  node well inside full scale at 3.3 V. Divider ≤100 kΩ total, or raise `TACQ` to
  40 µs. **Core capture (2026-09-15): 49.9 kΩ / 49.9 kΩ 1 %, switched on the high
  side** by an AO3415A whose gate a 2N7002 pulls down from `BAT_DIV_EN` (1 MΩ gate
  pull-up to `VBAT`; **1 MΩ `BAT_DIV_EN` pull-down R440, 2026-09-16**, so the switch stays
  off while the GPIO is undriven at boot or reset). Off, it draws nothing and `AIN0` sits at 0 V; a low-side
  switch would leave `AIN0` at `VBAT` through the top resistor, above `VDD` + 0.3 V
  between 3.6 V and the 3.81 V OVP ceiling. Reading, `AIN0` is ≤1.9 V and the
  divider draws ~38 µA. CC sense reads 0.25–2.04 V through a 100 kΩ series resistor into the
  `AINx` pad: with `VSYS` regulated the pin is never below 3.3 V while a source
  is attached, but the resistor costs nothing and covers a latched or tripped
  KTS1693 on an unregulated future variant.
- **Antenna**: `left` holds the only radio that talks to the host, at the outer end
  of the assembly with a case on one side only. Rev 3 had it in the centre module,
  the worst position. The module goes at `left`'s outer or rear edge, away from the
  seam, Raytac's keepout
  dimensions cited in the schematic. The `IS31FL3733` datasheet warns to keep the
  part away from the antenna. The 46 mm Qi2 keepout and the antenna keepout compete
  for area and must be placed together.
- **ESD**: five entry points. Link UART on USB-C, the seam pogo contacts, the exposed
  expansion connector, the key matrix (finger → keycap → switch → GPIO), and the AA
  terminals. The dial's metal shaft is a sixth touch point: its mounting lugs go to
  GND on the dial board, which also carries a DNP TPD4E1U06DBV footprint on the
  encoder pins, fitted only if the §16 dial ESD test needs it (2026-09-15). Four of the five are clamped on a small board: link, seam, expansion
  and battery (the USB port board clamps the host port too). The matrix is clamped on the key board; since
  P17 (2026-09-15) the core carries no entry-point clamp. Internal cables are not entry points and get no clamps. Name a part, an IEC 61000-4-2 level, and a clamp capacitance
  compatible with the baud rate. **Pair 2 is the worst-loaded line**: clamps at
  `left`'s link board and seam board, `right`'s two of each and the numpad's two,
  plus ~370 mm of trace, up to two external cables and, since rev 5, ~0.8 m of
  internal cable (seam → link ~30 mm on four boards, link → key ~100 mm on four,
  key → core ~100 mm on `left` and `numpad`). Budget: 8 arrays × 0.5 pF + ~45 pF
  of inner-layer trace + 2 × 1 m of external cable at ~60 pF/m + ~0.8 m of internal
  cable at ~60 pF/m + pins ≈ **~225 pF, rounded to 250 pF**. **Rev 4 budgeted
  200 pF with no internal cables.** Through 470 Ω that is τ ≈ 118 ns, a 10–90 %
  edge of ~0.26 µs, 12 % of a 460 800-baud bit. 1 Mbaud would be 26 % and is not
  used.
  Checked on the scope in 7b; 115 200 baud is the fallback. Link ESD: TPD6E05U06
  (6 channel, 0.5 pF, ±12 kV contact, IO + GND only) on **every link board**, one
  channel per receptacle pin A6, B6, A7, B7, A8, B8 (2026-09-14: one part keeps the
  link board at two BOMs; per-line capacitance is unchanged), TPD4E05U06 on the seam
  boards, channel 1 per pair with channel 2 left unconnected (paralleling it would
  double the line capacitance; 2026-09-14). Its DQA package ships as DQA0010A or
  DQA0010B; one library footprint takes both (SLVSBO7O rev O pp. 29, 32).
- **EMC**: informational only, since this ships as open source and builders carry
  their own compliance. Modular approval covers the intentional radiator only; the
  product remains an unintentional radiator under FCC Part 15B / EN 55032, and the
  module's FCC and IC identifiers would go on the label of anything sold.
- **Test points** beyond SWD: on the core, VBAT, VSYS, VBUS_IN, LED rail, 3V3,
  GND, boost EN, both I2C buses, both UARTs, CC1/CC2, module ID. On the key board,
  the link VBUS switch output and every link net (on `right`, pair 2's
  through-traces too). The Tag-Connect TC2030-NL footprint on the core reaches SWD
  without soldering.

## 14. Repo layout

```
plans/      this spec
docs/       architecture + decision record, link pinout, power budget, build guide,
            repair guide (symptom -> board), spares list
layout/     k860.yaml, generator + render scripts
mech/       joining, palm rest, plate, case, battery door, cable routing
hardware/
  lib/      vendored kiswitch footprints, custom MX socket + RGB combo footprint,
            interconnect footprints and the cable drawing
  common/   shared sheets: key-board LED + link routing blocks
  keys-right/ keys-left/ keys-numpad/   one KiCad project per key board
  core/     shared core board
  usb-port/ link/ seam/ battery/ dial/ expansion/   one KiCad project each
  plate/    FR4 plate outlines, one per module
firmware/   zmk-config (west.yml pins ZMK): core board definition, three shields,
            out-of-tree module
tools/      kicad-cli wrappers, gerber/BOM export, Konnect config
.github/workflows/  build (pinned, required), canary (ZMK main, weekly, non-blocking)
```

KiCad annotates per project, so refs are partitioned by project: `keys-right` 1xx,
`keys-left` 2xx, `keys-numpad` 3xx, `core` 4xx, `usb-port` 5xx, `link` 6xx,
`seam` 7xx, `battery` 8xx, `dial` 9xx, `expansion` 10xx (2026-09-15, since 1xx–9xx
are taken). A ref alone names the board it is on,
which the repair guide relies on.

## 15. Qi2 and the Li-ion path

Alkalines cannot be charged, so Qi2 is out of rev A. A 14500 cell reaches 4.2 V
against the nRF52840's 3.9 V absolute maximum, and the 2S holders would put two in
series at 8.4 V; the per-pack OVP rejects both.

To keep a Li-ion build possible, rev A reserves the high-voltage topology. Since
rev 5 the reservations split across boards, so a Li-ion build is a core population
variant plus a new battery board, not a rework of every module:

- **Core:** route `VDDH` (pad 30) separately from `VDD` with a solder jumper.
- **Core:** DNP footprints for the REG0 inductor (10 µH 0603, IDC ≥80 mA per Raytac)
  and its caps, with `DCCH` (pad 31) accessible.
- **Future battery board:** 1S holder, charger, coil header, cell thermistor,
  protection FETs, on the same `J_BAT` connector. The rev A battery board keeps a
  DNP OVP bypass.
- **Case and key board:** 46 mm bottom-side keepout.
- `UICR.REGOUT0` set in firmware for the Li-ion build.

## 16. Verification

- [ ] `kicad-cli sch erc` + `kicad-cli pcb drc` clean, all 9 projects + plates
- [ ] Interconnect audit: every net matches end to end across every connector and
      cable, per module; no two headers that one cable could reach share a pin count
      (`tools/check_interconnect.py`, 2026-09-16: core↔battery, core↔USB port,
      core↔expansion, link↔seam pass; key-board side pending keys-*)
- [ ] Konnect power-rail review, decoupling analysis, connectivity audit per board
- [ ] Phase 1: 1:1 print matches a real K860; physical test cell with socket,
      switch and opaque keycap, indicator glow legible; per-size cap count against a
      purchasable set
- [ ] **Insert one AA backwards, then both. Nothing is damaged.**
- [ ] **Insert two 14500 cells in one pack. Nothing is damaged; OVP holds VBAT off.**
      Scope the OVP FET drain at 1 µs/div through the first 20 ms: VBAT never
      rises above 6.0 V at any instant. Repeat 10 times with contact bounce
- [ ] **Hot swap (2026-09-15):** keyboard running on the other pack, pull a fresh AA
      pair and insert a 14500 pair as fast as possible, then swap one AA for one
      14500: `VBAT` and `VSYS` never exceed 6.0 V / 3.6 V (scope both). Repeat with
      R806 lifted to confirm the ngspice window (~2–4 s), then refit it
- [ ] **Link with `left` on USB and both satellites on cells at 2.0 V, then the
      reverse**: handshake succeeds, no pin sees more than `VDD` + 0.3 V (scope
      RX at both ends), transport stays wired
- [ ] **USB only, no cells fitted, on each module**: boots, ID reads its band,
      `VSYS` = 3.3 V, no safe mode
- [ ] Battery power-on: LED rail is up before `VIO` reaches 0.3 V above it (scope
      both at the driver); no GPIO required for the boost or logic regulators to
      start
- [ ] `right` seam-joined and switched off, `left` on: no current into `right`'s
      `VSYS`, `left`'s pair-1 TX reads as a pull-up-only input
- [ ] USB plug and unplug at full lighting: `SDB` falls within 100 µs of the
      VBUS event, LED rail never dips below `VIO`, MCU does not reset
- [ ] Both satellites wired: no BLE advertising from either (phone scanner);
      unlink one: advertising resumes within 1 s
- [ ] OVP on a bench supply: never trips below 3.59 V, always trips by 3.81 V
      rising; releases above 3.36 V falling
- [ ] 20 V on each USB-C socket's VBUS (local, upstream and downstream link), both applied steady and **hot-plugged from a
      charged source**: VBUS_IN never exceeds 6.0 V at any instant (scope at the
      TPS2116/LM66200 inputs, 1 µs/div through the first 2 ms); then a 5 V source
      stepped to 20 V while connected: same limit
- [ ] 1 kV contact ESD (then the chosen IEC level) on AA terminals: supervisor
      `VDD` stays under 10 V
- [ ] Contact ESD on the dial shaft and knob, with U901 not fitted: no reset, no
      stuck or phantom steps, encoder and core GPIOs still work; if it fails, fit U901
      (TPD4E1U06DBV) and repeat
- [ ] Short `left`'s seam VBUS, then `right`'s numpad-seam VBUS: each TPS22950L
      latches; it re-arms only after a fresh handshake
- [ ] Freshest alkaline pack available never trips OVP
- [ ] **Plug USB with fresh alkaline packs fitted: VSYS ≤3.3 V, zero pack current.**
- [ ] **No current flows between two modules' battery packs when linked**
- [ ] **No current flows out of a satellite's link VBUS when it is externally powered**
- [ ] 5 V bench supply into `left`'s link port, host on USB, switch off and then on
      (the TPS22950L has no reverse blocking, 2026-09-15): no current into the host
      port's VBUS (the LM66200 blocks), nothing heats, the switch still latches on a
      later short
- [ ] **`left` link VBUS and `right`'s numpad-port VBUS stay off into: a laptop, a
      BC1.2 charger (D+ shorted to D−), a charge-only cable, a detached seam.** Each
      turns on only for its satellite
- [ ] `right`'s numpad-port VBUS drops within the flag timeout when pair 2 is lost
      and when pair 1 is lost
- [ ] Short `left`'s seam VBUS pin to GND with the host on USB: current-limited, no
      damage
- [ ] Firmware system-off at ~2.05 V; LM66200 disabled by the supervisor at
      ~1.87–1.93 V at the pack, across 0–40 °C;
      no pin exceeds its supply during either transition (scope `VIO` vs LED rail)
- [ ] USB hand-over: plug and unplug under full lighting; LED rail never dips below
      VSYS, with ~10 µF bulk and no blanking (scope the TPS2116 switchover gap;
      rev 7), and VSYS never resets the MCU
- [ ] USB source at 4.5 V with full lighting: LED rail stays on VBUS_IN, 3.3 V LDO
      current unchanged from idle lighting. Ramp the source down and up: the rail
      drops to the boost between 3.63 and 4.40 V and returns ~0.3 V higher, with no
      hunting at the threshold (`PR1` hysteresis via `ST`, E3)
- [ ] Host CC sense reads default / 1.5 A / 3 A correctly on three chargers; LED
      budget follows
- [ ] Driver case temperature at full white on a 5.0 V rail, 30 min
- [ ] **Measured idle current, µA trace, both satellites linked and both UARTs parked.**
      The §4 idle row is unproven until this exists
- [ ] 9 hosts paired; profile 9 survives a power cycle
- [ ] All three battery levels visible and plausible
- [ ] **Runs correctly on one pack alone**, and no current flows between the two
      packs when one is fresh and one depleted
- [ ] Unlink a module mid-typing: whole split fails over to BLE and keeps working;
      relink: returns to wired; the still-cabled satellite never goes dead
- [ ] Hold a key across a link loss: it releases, never sticks. Relink while
      holding a key: no switch until ~1 s after release
- [ ] Rock a joined seam to bounce the pogo contacts: no transport switch
- [ ] Offer a module up to its neighbour reversed: magnets repel, no contact made
- [ ] Seam board stack, its cable exit and magnet retention fit the ~6 mm seam
      budget (Phase 1 print)
- [ ] **Swap the cores of `left` and `numpad` without reflashing: both enter safe
      mode, nothing drives a link pin, no link VBUS turns on. Reflash: both work**
- [ ] Power on with the key board's `J_LED` unplugged, then `J_ROW`, then `J_LINK`:
      ID reads open or the module runs degraded; nothing is damaged
- [ ] **Replace one of each small board (USB port, link, seam, battery, dial, expansion) with
      hand tools only**, from the published repair guide, and the keyboard passes the
      link and power tests above afterwards
- [ ] Unplug `J_LED` under full lighting, against the service rule, 10 times: the
      driver survives, and the scoped clamp current through `VIO`/SDA/SCL stays
      within the series resistors' design limit
- [ ] I2C at 400 kHz through the `J_LED` cable and the series resistors: rise times
      within spec (≤300 ns at the driver), ACK low at the nRF52840 ≤0.97 V, bulk LED
      writes error-free
- [ ] Expansion 3V3 at its 150 mA budget on both satellites with full white, linked
      to `left` on a 1.5 A host: `left`'s TPS22950L stays on, TLV75733P case
      temperature recorded
- [ ] Unplug a battery cable and a USB port cable under load: nothing is damaged
- [ ] Trip a USB port board's KTS1693 into its over-current latch: the fault blink
      code names the USB port board; the trip lands at 1.82–2.18 A, under the LM66200's
      2.5 A. Scope the 5–10 ms debounce pulse on a hard short from a 3 A charger and
      record its peak; repeat on an upstream link board fed by a USB-A-to-C legacy
      charger (E9, 2026-09-15)
- [ ] Partial short on `VBAT` (~1 Ω, fresh NiMH, both packs): record LM66200 case
      temperature, whether the UVLO or thermal shutdown cycles, and whether the PTC
      trips (the 2.5–3.5 A band is an accepted risk, E9)
- [ ] Short a downstream link port with the switch on: the TPS22950L limits and
      latches, nothing else heats. Offer an upstream link board's cable to a
      downstream header and vice versa: neither mates (rev 7)
- [ ] Host USB eye/enumeration through the USB port board cable at its longest
      routed length, on three hosts
- [ ] Change cells through the battery door with no tools and the case closed
- [ ] Core antenna keepout clear of all copper in every case; compare each placed
      module's BLE RSSI against a dev kit in the open (acceptance margin set in
      Phase 4), **once with MDBT50Q-1MV2 and once with MDBT50Q-U1MV2** (rev 7)
- [ ] `left`–`right` rear cable in all four plug orientations, seam open: pair 2
      orientation detected every time, numpad links
- [ ] Joined `left`–`right` seam plus a rear cable, both orientations: straight
      works; flipped leaves pair 2 undriven (scope both pins), flags "remove the rear
      cable", nothing is damaged
- [ ] USB 2.0 cable between `left` and `right`: `right` links, split stays on BLE,
      `left` flags the missing SBU pair
- [ ] Active USB-C cable between `left` and `right`: nothing is damaged
- [ ] Cable the numpad straight into `left`'s port: it handshakes on pair 1 and maps
      to the numpad's slot; split stays on BLE without `right`
- [ ] Cable `right`'s two rear ports to each other with the seam joined: duplicate
      `sat_id` rejected, contention current within GPIO rating, nothing is damaged
- [ ] Cable the numpad into `right`'s upstream port: neither drives TX (scope both
      lines), nothing is damaged
- [ ] Power `right` off with `left` and numpad linked through it: pair 2 signal
      integrity unchanged (no clamping through `right`)
- [ ] CC sense on each satellite's local port reads correctly on three chargers
- [ ] Pair 2 eye/edges at the chosen baud through the longest supported cables on
      both hops
- [ ] Canary CI against ZMK `main` runs weekly and reports breakage
- [ ] Dial spun fast both ways: no missed or doubled steps; a turn without a press
      never changes the live profile
- [ ] **Hold 10+ keys at once spanning all three modules; every one registers**,
      over USB and over BLE, on each host OS in use. Repeat with keys sharing rows
      and columns
- [ ] BIOS/UEFI sees the keyboard over USB (boot protocol)
- [ ] ZMK config builds in CI, 3 artifacts
- [ ] Every BOM line in stock before ordering, **with a second source recorded**
- [ ] Build guide reproduces the assembly from the published files alone

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
[`docs/open-questions.md`](../docs/open-questions.md). Summary:

- Parts: see [`docs/02-parts-shortlist.md`](../docs/02-parts-shortlist.md) for
  chosen parts and the datasheet verification queue. Still owed: an RGB LED second
  source and KTS1693 stock and second source.
- Rev 5 adds interconnect and placement questions: the connector family and its
  European stock (P9), whether both pogo halves share a footprint (P10), core
  placement against the antenna keepout (M6), and cable routing (M7).
- Rev 6 adds: the logic boost part number (P11), the KTS1693's sustained reverse
  state on downstream ports (E13), the TPS2116 switchover figure that sizes the
  bulk (E4, reworded), and case print sections (M9).
- Rev 7 closes E4, E13 and M9, narrows P11 to the logic boost's second source,
  and adds P12 (2.75U spacebar kit). P7 now records the TPS25947 but stays open
  for stock.
- Pre-schematic research (2026-09-14) closes P10 (shared pogo land pattern; seam
  board 1.2 mm), decides a combined LED footprint (P1, feasibility on samples), a
  dual logic-boost footprint with the MAX17222 (P11) and Mill-Max Maxnetic as the
  P8 fallback, and records JST GH and IS31FL3733 datasheet limits (P9, E11). Every
  stock check is still manual.
- 2026-09-15 closes P14 (the TPS22950L moves to the downstream link board, `ON` on
  `J_LBD` pin 6) and P17 (the expansion connector moves to a new expansion board on
  a 15-pin `J_EXP`), and corrects the claim that the TPS22950L blocks reverse
  current (accepted, §4 "Downstream ports", §16 check). The same day sets its `ILIM`
  resistor to 624 Ω on both downstream positions: SLVSFJ2B Table 7.5 guarantees the
  latch-off threshold `IHCD` at 1.2–1.9 A there, under the 2 A of two GH contacts (P9).
- Phase 3 calculations (2026-09-15) close E9, E11, E12 and E14 and narrow E3, F6,
  E15 and P11. An ngspice run of the pack chain found that a hot cell swap passes a
  14500 pair to `VBAT` (fixed with a 330 kΩ bleeder, R806, and ≤1 µF on the core's
  pack inputs); upstream link `ISET` becomes 4.99 kΩ; the logic boost divider becomes
  576 kΩ / 249 kΩ (rev 7's leakage error was understated); `PR1` becomes 301 kΩ /
  100 kΩ with `ST` hysteresis; `J_LED` gets 470 Ω on SDA/SCL and 1 kΩ on `VIO`/`SDB`
  with 4.7 kΩ pull-ups; `LINK_SW_EN` gets 10 kΩ; expansion 3V3 is budgeted at 150 mA;
  the core pad assignment is in §5, with 24 full-function pads rather than 23. The
  chain load is 425 mA bottom-up, and the MAX17222 has ~4.8× margin over `VSYS`
  peaks. Accepted: a ≤10 ms KTS1693 debounce pulse and a 2.5–3.5 A band under the
  pack PTC on the LM66200.
- Core capture (2026-09-15, `tools/sch_core.py`, variants `tps61099` default and
  `max17222`) sets the slide switch as an SPDT on the pack OR's `~ON` (§4), the
  `VSYS` mux `PR1` as its own divider from `VBUS_IN`, a high-side switched
  49.9 kΩ / 49.9 kΩ `VBAT` divider (§13), `J_LED` as LED_RAIL ×2 / VSYS ×2 so it
  can be mirrored, and pin orders for `J_ROW`, `J_COL`, `J_LINK` (§6). Values:
  TPS61099 2.2 µH Würth 74404024022, 10 µF in, 2 × 10 µF out; MAX17222 2.2 µH,
  10 µF in and out, fed to the boost net through a 0 Ω fitted only with it;
  TPS61023 1 µH Coilcraft XEL4030-102ME, 698 kΩ / 100 kΩ (4.75 V), 10 µF in,
  2 × 22 µF out; LDOs 1 µF in and out; Epson FC-135 CL 9 pF with 12 pF caps; 27 Ω
  on D+/D− (Raytac §8.3); 100 kΩ `ACOK` and LED boost `EN` pull-ups, 100 kΩ
  expansion `EN` pull-down, 1 MΩ on `VBUS_LINK_IN`, 100 kΩ UART pull-downs, 4.7 kΩ
  expansion I2C and 100 kΩ CS/INT pull-ups to the gated 3V3.
- Expansion board capture (2026-09-15) sets refs 10xx, the SM12B-SRSS-TB socket,
  TPD4E05U06 + TPD6E05U06 on all ten non-GND pins, and a mirrored `J_EXP` pinout
  with two contacts per rail (§6).
- Seam board capture (2026-09-14) fixes the pogo pad numbering (flat pad 1 at its N
  end, §6) and adds sample confirmation of it to P5.
- Pair 2 is the longest, most heavily clamped line in the design, and the one that
  needs a full-featured cable. If the 7b scope check forces a low baud or builders
  report cable trouble, the documented fallback is the rejected firmware relay on
  `right` (architecture §6), which returns every link to 4 nets.
- Wired split is marked experimental upstream, and this design both depends on it
  and extends it. BLE failover, the pinned ZMK commit and the weekly canary are what
  make that acceptable.
