# Open questions

Every question the design still carries, in one place. The spec
([`../plans/keyboard.md`](../plans/keyboard.md)) owns the numbers and §16
verification gates; the architecture doc
([`01-architecture.md`](01-architecture.md)) owns the reasoning; the parts list
([`02-parts-shortlist.md`](02-parts-shortlist.md)) owns part candidates. This file
only tracks what is unanswered, what answers it, and when.

When a question closes, delete it here and record the answer in the document that
owns it.

Last reviewed: 2026-09-15, core capture: P18 added (core parts whose datasheets are not yet read), P9 `J_LED` load updated. Before that, Phase 3 calculations (`tools/sim/`): E9, E11, E12 and E14 closed
(answers in the spec §4, §5 and the parts list; E14's ngspice run found a hot cell swap passes a
14500 pair, fixed with the R806 bleeder); E3, F6, E15 and P11 narrowed to bench, sample or stock
checks. Earlier the same day: P14 closed (TPS22950L moves to the downstream link board;
its missing reverse current blocking is accepted, spec §4) and P17 closed (the expansion
connector moves to an expansion board). Before that, 2026-09-14, after the pre-schematic desk research (P10 closed: shared
land pattern, seam board 1.2 mm for the spring half's 1.50 mm tails; P1 combined
LED footprint, P11 dual boost footprint and the P8 Mill-Max fallback decided; P9
and E11 updated with datasheet findings). Before that, rev 7 (E4, E13 and M9 closed, P11 narrowed, P12
added, E9 widened; answers in the spec §17). Before that, rev 6 (review findings, see
[`03-review-rev5.md`](03-review-rev5.md)). Rev 6 adds P11, E13, M9 and rewords E4
and F6. P2–P4 closed 2026-09-13 (answers in the spec §4 and the parts list). M5
(seam header) was replaced by the rev 5 seam-board cable and is now covered by M1
and M7.

## Parts

| # | Question | Why it matters | Resolved by | Phase |
| --- | --- | --- | --- | --- |
| P1 | Which RGB LED is the second source for SunLED XZMDKCBDDG45S-9? | Open-source builds need a second source on every BOM line; the SunLED part is listed at DigiKey but not confirmed at Mouser. **Survey (2026-09-14): no footprint-compatible part found.** SunLED is gull-wing, 5.2 mm lead span, pads 1.4 × 0.65 mm, Ø3.2 mm hole for the lens only (body on the board surface). The two reverse-mount common-anode alternates found, **Inolux IN-P32TRRRGB** (Vf max 2.4 / 3.6 / 3.6 V, IF 25 mA) and **QT-Brightek QBLP677R-RGB** (Vf max 2.7 / 3.7 / 3.7 V, IF 30 mA), share a different package: body sits *in* a **Ø4.5 mm** round cutout, ~6.0 mm lead span, 1.5 mm pad pitch. Their drawn pinout (anode 4; R 3, G 2, B 1) reads as a mirror of SunLED's (anode 2; R 1, B 3, G 4), unconfirmed until a sample is in hand. A Ø4.5 mm hole also eats into the M3 cell clearance | **Decided 2026-09-14: one combined key-board footprint** (Ø4.5 mm cutout, pads spanning both lead lengths). Still open: does the SunLED seat and light correctly over a Ø4.5 mm hole, can one pad-to-net mapping serve both pinouts (confirm the mirror on samples), and does Ø4.5 mm fit the M3 cell. Resolved by samples of all three parts and the Phase 1 test cell; if the pinouts cannot share a mapping, P1 reopens | before Phase 3 |
| P7 | Is the KTS1693 stocked for builds, and is the TPS25947 an acceptable second source? | Used on 5 USB-C sockets since rev 7 (3 USB port boards, 2 upstream link boards); single-vendor WLCSP; Mouser and DigiKey list it, stock not confirmed. Survey (rev 7): **TI TPS25947** (TPS259470x/4x) is the leaded candidate: 28 V abs-max, adjustable OVLO (ref 1.183–1.223 V), **1.2 µs** turn-off vs 100 ns, 28 mΩ, 430–610 µA Iq, QFN 2 × 2 mm 0.45 mm pitch, true reverse blocking, not footprint-compatible. TPS2660x rejected on 150 mΩ; AOZ13984 (fixed 24 V OVP), AP22950/AP22953 (WLCSP) and RT1735 (CC/SBU only) excluded | Mouser Europe stock for both; whether 1.2 µs holds the protected side under 6.0 V in the E1 hot-plug test | before Phase 3 |
| P11 | Is the MAX17222 second-source footprint sound, and are both boosts stocked? | Rev 7 picks the adjustable TPS61099DRV (WSON-6) with a ~1 µA feedback divider, because the fixed 3.3 V TPS610994 is WCSP only. **Decided 2026-09-14: dual footprint on the core** for the MAX17222 Manual European stock check for both, and the µDFN-6 land pattern (Maxim 90-0004). **Load check done 2026-09-15**: ~124 mA out at 1.85 V in (`IPEAK` min 0.40 A) vs ~26 mA `VSYS` peak. Survey data: candidate **ADI MAX17222ELT+** (µDFN-6 2 × 2 mm): 300 nA into OUT, 0.88 V minimum startup (runs to 0.4 V after), output set by one 1 % RSEL resistor (80.6 kΩ → 3.3 V, read once at startup, no divider current), buck-like regulation while `VOUT` < `VIN` < `VOUT` + ~0.7 V so it still regulates at the 3.81 V OVP ceiling, 0.5 A peak inductor limit, true shutdown. **Different pinout from the TPS61099DRV**, so it is not a drop-in; the 0.5 A limit leaves ~4.8× margin at 1.85 V in | before Phase 3 |
| P15 | Is the MPD BC2AAPC holder stocked in Europe, is 50 mΩ inside the pack budget, and can the Keystone 2462 share its footprint? | **Chosen 2026-09-14: MPD BC2AAPC** (drawing rev P, 2024-06-21): 2×AA in series, PC pins, 15.0 mm above board against the ~16 mm height floor, nickel-plated steel springs and brass rivets, contact resistance **under 50 mΩ** (EIA-540J000). Rev P moved the pins to 13.00 mm, so KiCad's stock `BatteryHolder_MPD_BC2AAPC_2xAA` (13.59 mm, rev M) is wrong and the library has a rev P footprint. The spec's series budget assumed ~30 mΩ for the holder; at 50 mΩ the worst case rises from ~276 to **~296 mΩ**, still under 300 mΩ. Second source **Keystone 2462** (16.0 mm high, 59.5 × 32.9 mm, nickel-plated brass pins, no contact resistance published) is not a drop-in: KiCad's footprint puts its pins 14.99 mm apart, and its current drawing could not be downloaded (keyelco.com blocks automated requests) | Manual stock check for both at Mouser Europe/TME/Farnell; Keystone 2462 drawing to decide whether a combined footprint works (pin 2 would sit ~2 mm from the MPD's pin 2, and the mounting holes differ); contact resistance measured on samples | before Phase 3 |
| P18 | Do the core's unverified parts match their footprints, and which exact crystal MPN? | Core capture (2026-09-15) assigned parts whose datasheets could not be downloaded (vendor sites block automated requests): **Epson FC-135 32.768 kHz CL 9 pF** (stock `Crystal_SMD_3215-2Pin_3.2x1.5mm`; ESR ≤100 kΩ, C0 ≤2 pF needed per nRF52840 PS v1.9 p. 170), **Alps SKRTLAE010** and **C&K PCM12SMTR** (stock footprints), **Coilcraft XEL4030-102ME** (placed on stock `L_Coilcraft_XAL4030-XXX`, assumed to share the land pattern). The MAX17222 still has no footprint (Maxim 90-0004, P11). Stock KiCad footprints often differ from the vendor land pattern (TI SOT-563 and SOT-23-5 did, now in the library) | User supplies the four datasheets; compare land patterns, confirm the crystal's full MPN, ESR and C0 | before Phase 4 |
| P12 | Which kit supplies the two 2.75U spacebars? | Standard sets carry one 2.75U key (right shift) and no 2.75U spacebar; two blank or convex 2.75U keys come from ortho/ergo spacebar kits. 2U, 2.25U and 2.75U share the 23.8 mm stabiliser spacing, so one stabiliser part covers all | Pin a specific kit in the Phase 1 cap count | Phase 1 |
| P8 | Can the seam pogo pairs be bought from a European distributor? | Parts are sourced from Mouser Europe or similar; SAMZO PR5L3715-4P-C-H / PR5L2820-4P-C-F were found only at LCSC. If no distributor carries them, the seam needs a different magnetic pogo pair, which reopens M1 (seam depth) and the seam board design. **Search (2026-09-14):** web search finds SAMZO only at LCSC/JLCPCB, Chipmall and SemiKey, not at Mouser, DigiKey, Farnell or TME (distributor sites block automated checks, so a manual search is still owed). Stocked fallback found: **Mill-Max Maxnetic 872/873** series, 2.54 mm, 4 positions (e.g. 872-22-04-10-012101 spring / 873-10-04-10-012000 target, solder tail), 5.2 A per pin, ≤20 mΩ, but **10.9 mm mated stack**, against the ~6 mm seam budget | Manual distributor check. **Fallback decided 2026-09-14: if SAMZO is not sold in Europe, switch to Mill-Max Maxnetic 872/873**, which reopens the seam depth (M1), the ~468 mm width and the seam board design | before Phase 1 |
| P9 | Is JST GH stocked in Europe with premade cables, and does link VBUS fit its contact rating? | **Datasheet-checked (2026-09-14, JST eGH catalog):** 1.0 A AC/DC per contact (AWG #26), 50 V, 30 mΩ initial / 50 mΩ after test, −40 to +105 °C including rise, AWG #30–#26; 2–15 circuits; side-entry header **SMxxB-GHS-TB**, housing GHR-xxV-S. JST publishes **no multi-contact derating and no mating-cycle rating**; "~30 cycles" appears only in third-party pages, so the build guide keeps the don't-reseat advice as a precaution. Per-contact loads: `J_LED` ~254 mA (2 rail contacts since the core capture, 2026-09-15; was ~170 mA on 3), `J_BAT` ~365 mA, `J_USB` ~530 mA at 1.6 A. **Link VBUS on 2 contacts (`J_LINK`, `J_LBD`) carries up to the TPS22950L limit, so the limit must stay ≤~2 A, or add contacts.** Since P14 (2026-09-15) the switch sits on the downstream link board, after those contacts, so a short in that cable is bounded only by the source's limit (spec §6). Keyed GH variants exist only in 2/4/5 pins, so uniqueness stays with pin counts | Mouser/DigiKey/TME stock (manual); premade or crimped cable source; TPS22950L limit set 2026-09-15: `ILIM` 624 Ω, `IHCD` 1.2–1.9 A (SLVSFJ2B Table 7.5), inside the 2-contact budget. Chain load 425 mA bottom-up at full white, 725 mA with 150 mA expansion loads (2026-09-15). Any fallback must also be positive-lock; friction-lock JST SH is excluded | before Phase 3 |
| P5 | What is the SAMZO pogo pair's magnet pull force, and does the pad numbering hold? | Decides whether the connectors' magnets contribute meaningful retention or only alignment and reverse-join rejection; not on the drawing. **Pad numbering decided 2026-09-14** (spec §6): pad 1 = spring S end, flat N end, so facing pads mate k ↔ k. If a sample's magnets are not at the ends the drawings suggest, a join would put VBUS on GND on the one-pair seam | Samples on a force gauge; a mated pair checked for continuity pad 1 ↔ pad 1 and the S/N ends marked against the silkscreen | Phase 1 |
| P6 | Is there enough stock of both pogo halves for a full build? | SAMZO at LCSC: flat half ~490, spring half 750 at last check; moot if P8 replaces the part; a build needs 3 of each per keyboard, but open-source builders multiply that | Stock recheck | Phase 6 |

## Electrical

| # | Question | Why it matters | Resolved by | Phase |
| --- | --- | --- | --- | --- |
| E1 | Does the KTS1693 hold the protected side under 6.0 V on a 20 V hot plug and on a 5 → 20 V step while connected, with the real cable, 10 µF bulk and SMF6.0A? | Trip is 5.55–5.95 V and turn-off 100 ns, so the margin to 6.0 V is 50 mV at the top of the tolerance; overshoot during the 100 ns is not specified for our load | §16 hot-plug and step tests on the scope | bring-up |
| E2 | Does 460 800 baud hold on pair 2 through two 1 m cables? | Pair 2 crosses eight ESD arrays, ~370 mm of trace, ~0.8 m of internal cable since rev 5 and up to two external cables; the ~250 pF budget is an estimate. If it fails, 115 200 baud is the fallback; if that fails or builders report cable trouble, the firmware relay (architecture §6) returns | Scope in milestone 7b | 7b |
| E3 | Does the `PR1` threshold behave on real ports? **Set 2026-09-15: 301 kΩ / 100 kΩ + 1 MΩ to `ST`**, drop to the boost at 3.63–4.40 V (`VREF` ±8 %), ~0.3 V hysteresis | Too high and a weak but usable USB port hands LED load to the boost, which draws the cells; too low and the rail sits on a sagging VBUS with starved LED headroom | Bench test at 4.5 V and 4.75 V sources and a slow ramp through the threshold (§16) | bring-up |
| E6 | Do max-bin green and blue LEDs visibly dim or colour-shift on a weak USB port? | Estimated headroom is ~0.2 V on battery but ~0 V at USB's 4.75 V minimum after path drops. SunLED offers Vf sorting to ±0.1 V if needed | Phase 1 test cell on a current-limited supply | Phase 1 |
| E7 | What is the real idle current with both UARTs parked and break wake working? | The ≥6-month idle target is unproven until measured | µA trace, §16 | 7b |
| E10 | Does host USB enumerate reliably with D+/D− crossing the USB port board cable? | Full speed tolerates short uncontrolled-impedance runs, but the cable length and conductor arrangement are not yet fixed | Eye and enumeration check on three hosts, §16 | bring-up |
| E8 | How hot does the IS31FL3733 get at full white on a 5 V rail? | USB raises CS dissipation compared with the 4.7 V battery rail | 30-minute case-temperature test, §16 | bring-up |
| E15 | Do the dial encoder's lugs connect to its bushing? | Tying the lugs to GND only drains a shaft zap if the bushing is bonded to them. (Pull-up half closed 2026-09-15: product spec v1.9 gives `RPU` 11 / 13 / 16 kΩ, closed level 0.21–0.28 V with the 1 kΩ filter) | Continuity check on a PEC11R sample | sample |

## Mechanical

| # | Question | Why it matters | Resolved by | Phase |
| --- | --- | --- | --- | --- |
| M1 | Do the seam boards, their cable exits, both pogo housings (2.7 mm spring, 2.8 mm flat) and 0.7 mm working compression fit the ~6 mm seam? | If not, the ~468 mm width grows or the connectors move | 1:1 print | Phase 1 |
| M2 | How is retention held against 200 gf of pogo spring force on the `left`–`right` seam? | Retention must hold the seam gap inside the pogo compression tolerance | Joining design and print | Phase 1 |
| M3 | Do a hotswap socket, the **Ø4.5 mm** combined LED cutout (P1), a diode and stabiliser clearance coexist in one 19.05 mm cell? | Asserted, not proven; an MX cell is tight | Physical test cell | Phase 1 |
| M4 | Is the key-lighting glow legible through an opaque keycap? | Profile indication depends on it; no light pipe or indicator LEDs | Test cell with a real opaque cap | Phase 1 |
| M6 | Where does the core sit in each case so its antenna end overhangs no copper? | The core is off the key board's footprint since rev 5; on `left` it must be at the outer edge for the host radio, and it competes with the 46 mm Qi2 keepout, the palm-rest cells and the case-wall openings for buttons and expansion | 1:1 print, Phase 4 3D export, RSSI comparison in §16. **Core outline 32 × 90 mm, placed 2026-09-16** (placement-driven): antenna on one short edge, SW401–403 on the opposite case-wall edge, GH headers on a long edge, tightest rectangle + 1 mm with M2 corners; the case adapts or the placement is revisited | Phase 1 / 4 |
| M7 | Can every internal cable be routed and clipped clear of switch pins, sockets and LED holes, with service loops? | Up to ~8 cables per module; a pinched or rubbing cable becomes the new failure mode | Phase 1 print with dummy cables | Phase 1 |
| M8 | Does a tool-less battery door fit the palm rest and hold cells without rattle, and does the numpad's palm rest fit two battery boards? | Cell access without tools is a rev 5 requirement; resin latches are brittle. The numpad takes two packs (decided 2026-09-14), so its palm rest may need to grow, which touches the silhouette | Print and cycle test | Phase 1 |

## Firmware and hosts

| # | Question | Why it matters | Resolved by | Phase |
| --- | --- | --- | --- | --- |
| F1 | Do nine BLE profiles survive a power cycle with `CONFIG_BT_MAX_PAIRED=11`? | Bond storage at the raised limit is untested | §16 pairing test | 7a |
| F2 | Which host OSes accept the NKRO descriptor over BLE? | Rollover over BLE varies by OS and is verified per host, not assumed | §16 per-host test | 7a |
| F3 | What debounce settings does the stocked PEC11R encoder need? | Missed or doubled steps break preview-then-commit; the dial board now has a fitted 1 kΩ + 10 nF low-pass on A/B (2026-09-15), so this checks what bounce is left | Bench measurement | 7a |
| F4 | Does the module's transport translation unit survive linking? | A module-registered split transport is supported in source; the 10-line stub confirms the linker keeps it | Week-1 stub build | week 1 |
| F6 | Do the module-ID bands read as calculated on hardware? | **Calculated 2026-09-15**: worst case 0.085–0.097 / 0.308–0.330 / 0.675–0.699 against ±0.06 bands, including ≤800 Ω GPIO output resistance, tempco and SAADC offset + INL; `TACQ` ≥10 µs; gain error cancels only with the same gain and reference on both channels | Bench read on all three key boards | 7a |
| F5 | Does the pair-2 pinctrl swap behave on hardware? | Verified in Zephyr source (dynamic pinctrl + UARTE suspend/resume), not yet run; the driver asserts if RX is still enabled at suspend | Dev-kit test before 7b | 7b |

## Standing risks

These have no single answer; they are watched rather than closed.

- **Wired split is experimental upstream**, and this design depends on and extends
  it. Mitigated by BLE failover, the pinned ZMK commit and the weekly canary.
- **Pair 2 needs a passive full-featured USB-C cable** between `left` and `right`.
  Builders will reach for USB 2.0 cables; `left` flags the case, but it remains the
  most likely support question. Fallback: the firmware relay.
- **TPS61023 has no pin-compatible second source.** Accepted; stock rechecked at
  Phase 6.
