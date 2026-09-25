# Parts shortlist

Companion to [`../plans/keyboard.md`](../plans/keyboard.md), which owns the
requirements. This document owns candidate parts: the chosen primary, alternates,
the numbers that made the choice, and what still needs verifying against a full
datasheet before the schematic.

Stock and price are volatile; recheck every line before ordering (§16 of the spec).

**Sourcing: Mouser Europe or a similar European distributor** (DigiKey, Farnell, TME,
Romanian distributors). LCSC/JLC part numbers below are references, not the source.
Distributor listing checked 2026-09-13 by search only, not a live stock check: KTS1693
listed at Mouser and DigiKey; SunLED XZMDKCBDDG45S-9 at DigiKey; **SAMZO pogo halves
found at LCSC only**.

Status legend: **chosen** = decided, **proposed** = default pending confirmation,
**open** = no candidate yet.

**Rev 8 (2026-09-26):** hub + dumb key modules (spec §17). The pack chain moves
onto chainable battery modules with their own ideal diode; the KTS1693 remains on
the host port only; the rev 7 link board becomes the cable comms board; the seam
pogo parts, link series resistors and module-ID resistors are dropped (rows kept
in commit `0b22b91`); new rows for the module controller, the key-board LDO, the
TCA9548A and the rejected key scanners.

## Pack chain (per battery module, one 2×AA pack each; rev A fits two)

| Slot | Status | Part | Key numbers | Verify |
| --- | --- | --- | --- | --- |
| Pack ESD | chosen | Littelfuse **SMF4L9.0CA** (bidirectional, marking AV), SOD-123FL; 2nd source SMF9.0CA (200 W, same footprint and clamp; DC Components, MCC, Semiware) | datasheet-verified: 9 V VR, VBR 10.0–11.1 V at 1 mA, IR ≤5 µA at 9 V, VC 15.4 V at 26.4 A, 400 W at 10/1000 µs, 2000 W at 8/20 µs, IEC 61000-4-2 ±30 kV contact, MSL 1. **Bidirectional is required**: the TVS is ahead of the reverse-blocking FET and PTC, so a unidirectional part shorts a reversed pack. 9.0 V is the lowest bidirectional voltage in the series | clamp at the chosen IEC level |
| Reverse-block FET | chosen | AOS **AO3415A**, 2nd source ElecSuper AO3415A (LCSC C5350990) | −20 V VDS, ±8 V VGS, RDS(on) <65 mΩ at −1.8 V (AOS; <75 mΩ used as the cross-vendor budget), RθJA 85 °C/W steady, SOT-23 | gate R + ~6.2 V zener clamp (VGS ±8 V vs 8.4 V pack) |
| OVP detector | chosen | TI **TPS3840PL35** | 1.5–10 V VDD recommended, **12 V abs-max**, 300 nA, ±1.5 % max, +200 mV hysteresis, push-pull active-low, SOT-23-5 | rising trip lands 3.65–3.75 V including hysteresis tolerance |
| OVP FET | chosen | **AO3415A**, source on pack side; **gate pulled up to source (~10 MΩ), supervisor pulls down through ~470 kΩ into a gate-to-source capacitor, τ ≥ 25 ms (e.g. 56 nF), diode for fast turn-off** (rev 6; τ rev 7) | as above; `VGS(th)` −0.3 / −0.57 / −0.9 V; `Crss` ≤115 pF. TPS3840: `tSTRT` 100–350 µs with CT open (includes no-cap `tD`), `VPOR` output defined only for `VDD` slew ≤100 mV/µs | back-to-back with the rev FET; gate clamp; capacitor must be gate-to-source, ≥10 nF |
| Cell holder | chosen | MPD **BC2AAPC** (2×AA series, PC pins); 2nd source Keystone 2462 unconfirmed (P15) | datasheet-verified (drawing rev P, 2024-06-21): 15.0 mm above board, 58.0 × 30.5 mm, contact resistance <50 mΩ, nickel-plated spring-steel springs and PC pins, polypropylene UL94-HB, −10 to +100 °C; pins 13.00 mm apart since rev P (stock KiCad footprint is rev M, 13.59 mm) | European stock; Keystone 2462 drawing for a combined footprint; contact resistance on samples |
| OVP supervisor filter | chosen | 1 kΩ + 100 nF on TPS3840 `VDD` | keeps the TVS clamp inside the 10 V recommended range at the pin | ESD test |
| Gate clamp zener (×2: rev FET, OVP FET) | chosen 2026-09-14 | Nexperia **BZX84-C6V2**, SOT-23 (pin 1 A, 3 K), cathode on `CELL_RB` | datasheet-checked: VZ 5.8–6.6 V, IR ≤3 µA at 4 V max; typical ~10–20 nA at 3.3 V (BZX384 series Fig. 8, same die family). Leakage flows through the rev FET's 100 kΩ gate resistor to GND (a few µV typ, ≤0.3 V at the 3 µA maximum) and through R803 470 kΩ on the OVP gate (≤1.4 V at the maximum) | leakage at 85 °C against the idle budget and the −1.8 V gate drive at a 1.9 V pack |
| Rev FET gate resistor | chosen 2026-09-14 | 100 kΩ 1 % 0805, gate to GND | 22 µA through the clamp with a 14500 pair inserted; small enough that zener leakage costs little gate drive | — |
| OVP gate network | chosen 2026-09-14 | R802 10 MΩ 1 %, R803 470 kΩ 1 %, C801 **68 nF** X7R 25 V 0805 (gate-to-source) | τ = 32 ms nominal, 28.7 ms at −10 %, so τ ≥ 25 ms holds at tolerance (56 nF gives 23.7 ms at −10 %); AA turn-on at a 1.9 V pack grows from ~17 to ~22 ms. **E14 closed 2026-09-15**: D804's residual drop decays in milliseconds in simulation (the BAT54 conducts down to sub-µA), but C801 holds a running pack's FET on after cell removal, hence R806 | — |
| OVP turn-off diode | chosen 2026-09-14 | Diodes **BAT54-7-F**, SOT-23 (pin 1 A, 3 K), anode on `~RESET`, cathode on the gate | datasheet-checked: 30 V, VF ≤400 mV at 10 mA, IR ≤2 µA at 25 V (discharges 68 nF by ≤14 mV over the ~460 µs insertion window even at the maximum); typical VF at 100 µA ~0.25 V at 25 °C, ~0.35 V at −40 °C (Fig. 1) | — |
| Supervisor filter parts | chosen 2026-09-14 | 1 kΩ 1 % 0805, 100 nF X7R 25 V 0805 | 25 V covers the 15.4 V TVS clamp | — |
| OVP bypass | chosen 2026-09-14 | 0 Ω 1206, **DNP**, across the OVP FET | Li-ion build only (§15) | 1206 jumper current rating against the 730 mA worst case |
| Pack-node bleeder (R806) | chosen 2026-09-15 | 330 kΩ 1 % 0805, `CELL+` to GND | ngspice (`tools/sim/e14_pack_swap.py`): without it C801 keeps the OVP FET on for 2.3–3.8 s after the cells come out (1 µF `CIN`, as on the rev 7 core), so a hot 14500 swap put 8.3 V on `VBAT` and a one-cell swap 5.5 V; with it the window is 0.46–0.50 s. 8.5 µA per pack at 2.8 V (~74 mAh/yr), 25 µA with a 14500 pair. Needs each battery module's ideal-diode input at ≤1 µF (10 µF stretches the window to 3.4–3.7 s) | §16 hot-swap test |
| `J_CHAIN` contacts (rev 8) | **2×6 2.54 mm pass-through stacking header, decided 2026-09-26; exact part open (M10)** | pinout **1 `VBAT`, 2 GND, 3 `VBAT`, 4 GND, 5 `AUX_5V`, 6 `PACK_EN`, 7 `PACK_SENSE`, 8 `AUX_5V`, 9 GND, 10 `VBAT`, 11 GND, 12 `VBAT`** (turned 180° pin k meets 13−k: only `PACK_EN`/`PACK_SENSE` swap, leaving every pack off); battery modules pass `AUX_5V` through | ~20 mΩ per contact is **assumed** in the ~296 + 10·n mΩ pack path; confirm on the chosen part; current ≤0.8 A on 4 contacts | M10 |
| PTC | chosen | Eaton **PTSLR12066V175** (PTSLR1206 family, marking L3) | datasheet-verified: 1.75 A hold, 3.5 A trip, 0.4 s max at 8 A, 50 A Imax, 0.8 W tripped, **Ri min 5 mΩ, R1 max 45 mΩ**, 2500/reel, **6 V rated** (the whole family is 6 V), 1206, −40 to 85 °C with derating (~88 % hold at 40 °C). 6 V is sufficient: the PTC is behind the OVP FET, so it never sees a 14500 pair. Pack path ~296 mΩ worst case against 300 mΩ (holder at its 50 mΩ maximum). Rejected: PTSLR12066V150 (3.0 A trip, R1 max 80 mΩ, path 311 mΩ with the LM66200 at its maximum RON) and PTSLR12066V110 (130 mΩ). Both trip currents exceed the LM66200's 2.5 A rating (open question E9). **Pads (datasheet 11048 p. 3): 1.0 × 1.9 mm, 2.0 mm gap**, in the library as `Fuse_1206_Eaton_PTSLR1206`; stock `Fuse_1206_3216Metric` pads are larger and closer. **Eaton: manual soldering +350 °C, 4–5 s, "generally manual/hand soldering is not recommended"; MSL 2a**. **Decided 2026-09-14: F801 is reflowed or hot-air soldered**, the rest of the battery board stays hand-solderable. **Hand-solderable alternatives compared 2026-09-14, PTSLR kept:** Bourns MF-SVS210 nickel strap (Ih 2.1 A, It 5.0 A, R1 max 40 mΩ, 10 V, ~22 × 5 mm weldable 0.127 mm nickel leads, no PCB soldering guidance, 0.4 A hold at 80 °C); Bourns MF-RHS450 radial (Ih 4.5 A, It 9.0 A, R1 max 40 mΩ: may never trip on a 2×AA fault); Bourns MF-R400 radial (It 8 A, R1 max 50 mΩ, path ~301 mΩ); Bourns MF-MSMF300/6X 1812 (It 5.0 A, R1 max 40 mΩ, also "hand soldering is not recommended"). Bourns MF-PSML/X and MF-PSMF carry the same restriction. No low-resistance PTC found is both hand-solderable and trips near 3.5 A. **E9 (2026-09-15): kept.** Eaton publishes no trip curve (one point, 0.4 s at 8 A), so a 2.5–3.5 A fault may never trip it and sits on the LM66200 until UVLO or thermal shutdown; accepted, with a §16 partial-short test. V110 (Itrip 2.2 A, path ~381 mΩ) and V150 (3.0 A, ~331 mΩ) were the alternatives | second source |

Alternates considered for pack OVP: TLV6703 comparator (1.8–18 V, 5.5 µA, 400 mV
ref), adjustable but ~11 µA more idle. Integrated OVP switches (KTS1693, NX30P6093A,
BCT7915) all start at ≥4 V.

Alternate FET: Diodes **DMP1045U** (−12 V, 45–75 mΩ at −1.8 V, gate ESD), thinner
voltage margin.

## Pack ideal diode and undervoltage (rev 8: ideal diode per battery module, supervisor on the hub)

| Slot | Status | Part | Key numbers | Verify |
| --- | --- | --- | --- | --- |
| Per-pack ideal diode + cutoff (battery module) | **chosen 2026-09-26** | TI **LM66200**, one channel used: `VIN1` pack, `VIN2` GND, `~ON` from the chain's `PACK_EN` with a **~10 MΩ pull-up to the pack node** (a detached module is off), `ST` unused; reflowed with the PTC | SLVSG04 truth table §7.3.1: only the higher input conducts, so the two channels cannot be paralleled to halve RON. Rejected: LM66100 (210 mΩ), discrete P-FET + comparator (65–75 mΩ, new circuit), Schottky (0.3–0.4 V, no enable). Datasheet: dual ideal-diode OR, 1.6–5.5 V, **6.0 V abs-max** on all pins, **2.5 A/ch abs-max, 4 A for 1 ms at 2 %, no current limit**, thermal shutdown 170 °C, RON 41 typ / **51 max at 1.8 V, 25 °C** (61 mΩ at 85 °C), 1.32 µA, active-low `ON` disables both channels, SOT-5X3 | RON at 1.9 V; `ON` threshold vs a 1.8 V push-pull high |
| UVLO supervisor (hub) | chosen | TI **TPS3840PH18**, `VDD` from `PACK_SENSE`, output → slide switch → `PACK_EN` | 1.8 V falling ±1.5 %, +100 mV hysteresis, push-pull active-high, 300 nA | effective pack threshold with the BAT54 drop at nA, over temperature; no oscillation at cutoff (§16 chain test) |
| Supervisor supply (`PACK_SENSE`) | proposed | **BAT54** per battery module, pack node → `PACK_SENSE` (rev 7: one BAT54C for two packs on the core) | ~0.1 V at nA currents | measured drop 0–40 °C |

USB input OVP rejected alternates: **discrete TLV6713 + AO3401A** (rev 4 and the
2026-09-13 BSS138 gate-delay proposal): simulated, it needed a 10 nF gate–source
capacitor to stop a 20 V hot plug coupling through the FET's ~250 pF Crss, turned off
in ~350 µs, and let **16.8 V** through when a connected source stepped from 5 to 20 V;
TI **TPD1S514** (30 V, DSBGA-12); onsemi **NCP361** (600 mA DC max); TI **LM74502**
(OV threshold ±6.6 %); ADI **MAX4987AE** (fixed 6.15 V OVLO, over the ceiling); TI
**TLV6703** (VDD 20 V abs-max).

Rejected: 2× LM66100 (141 mΩ each at 1.8 V) + TPS22916 load switch (100 mΩ at
1.8 V), which needed two more parts and ~240 mΩ. **Rejected again for the per-pack
ideal diode (rev 8): LM66100 RON is 141 mΩ typ / 210 mΩ max at 1.8 V, 125 mΩ max
at 3.6 V (SLVSEZ8A, −40 to 85 °C)**, which takes the pack path to ~455 mΩ; it does
have a comparator `CE` and 120 nA shutdown, and SC-70 would be easier by hand than
the LM66200's SOT-583. TPS3839 has no threshold between
1.67 and 2.325 V.

## USB input and VSYS

| Slot | Status | Part | Key numbers | Verify |
| --- | --- | --- | --- | --- |
| USB OVP switch (rev 8: the host port's USB port board only; rev 7 had five sockets) | chosen | Kinetic **KTS1693EVB-TR** (C1 = `ACOK`) | datasheet-verified: IN 2.7–28 V, **30 V abs-max**, 32 V internal clamp, IEC 61000-4-5 ±110 V and IEC 61000-4-2 ±8 kV contact on IN; 9 mΩ typ / 13 mΩ max N-FET, 8 A continuous; **turn-off 100 ns**; 0.7 ms debounce + ~2 ms soft start; UVLO 2.1–2.7 V rising; internal OVLO 5.77–6.13 V (**not used**: max exceeds 6.0 V); OVLO pin reference 1.162–1.238 V, ±100 nA; OCP set by `ISET`: **4.99 kΩ 1 % → 1.82–2.18 A on local ports** (datasheet Table 1: 5.00 kΩ = 1820/2000/2180 mA min/typ/max, 0–70 °C; rev 6: 3.0 A exceeded the LM66200's 2.5 A abs-max; value fixed 2026-09-14), **4.99 kΩ on upstream link ports too since E9 (2026-09-15)**; the earlier 1 MΩ (OCP disabled, datasheet Table 2) left a legacy charger in an upstream port unlimited, since the short-circuit detect needs >10 A and VIN − VOUT > 0.15 V (p. 13); with `OC_MODE` low the switch stays fully on for the 5–10 ms `tOCP_DEB` before latching (p. 11), an accepted pulse; **`OC_MODE` low (latch off), `EN` tied to GND**, so the latch clears on unplug; 140–180 µA quiescent; OUT abs-max IN + 0.3 V, OTG (OUT → IN) operation documented; thermal shutdown 140 °C; **WLCSP-20, 0.4 mm pitch, 1.935 × 2.160 mm** | Mouser stock; second source (P7): **TI TPS25947** (TPS259470x/4x) is the leaded candidate (28 V abs-max, 100 V/µs max input slew, adjustable OVLO 1.183–1.223 V ref, **1.2 µs** OVLO turn-off, 28 mΩ, 430–610 µA Iq, QFN 2 × 2 mm 0.45 mm pitch, true reverse blocking, different footprint); the 4 × 5 WLCSP needs 0.15 mm vias / via-in-pad on 7 boards |
| USB-C receptacle (USB port board and both comms board populations) | chosen 2026-09-14 | GCT **USB4085-GF-A**, USB 2.0 16P, all contacts and shell through-hole | drawing rev B (28/02/23): VBUS 5.00 A total, GND 6.25 A, 0.25 A other pins; 40 mΩ initial / 50 mΩ after test; 20 000 cycles; 5–20 N mating; gold flash over 50 µ" Ni; −40 to +85 °C. Chosen over the SMT USB4105-GF-A for retention on a user-facing port. Stock `Connector_USB:USB_C_Receptacle_GCT_USB4085` matches the recommended layout (0.85 mm pitch, rows 1.35 mm, Ø0.40 drills, slots) except signal pads Ø0.70 vs Ø0.65 mm | second source; European stock |
| CC ESD (×2 per USB port board) | chosen 2026-09-14 | TI **TVS2200** on CC1 and CC2 | 22 V VRWM, VBR 24.6–27.6 V, so a 20 V CC short does not conduct; 105 pF (inside a sink's CC capacitance allowance); clamp 28.4 V at 40 A. Library footprint `TI_WSON-6-1EP_2x2mm_P0.65mm_DRV0006A_TVS2200` from drawing 4222173/C (stock WSON-6 footprint uses a different TI pad layout). Rejected: TPD2S300 / TPD4S311A (WCSP/DSBGA with series OVP FETs and a supply pin), low-voltage ESD arrays (fail on a 20 V CC short) | — |
| CC Rd | chosen 2026-09-14 | 5.1 kΩ 1 % **0805** | a CC shorted to 20 V VBUS puts ~78 mW in Rd | — |
| KTS1693 bypass | chosen 2026-09-14 | 100 nF 50 V X7R on IN, 1 µF 25 V X7R on OUT (0603) | datasheet: 0.1 µF on IN close to the part, 1 µF on OUT | — |
| `J_USB` header | chosen 2026-09-14 | JST **SM11B-GHS-TB**, pinout **1 VBUS, 2 GND, 3 CC1, 4 GND, 5 D+, 6 VBUS, 7 D−, 8 ACOK, 9 CC2, 10 GND, 11 VBUS** | reversal-safe: pin k meets pin 12−k on an end-reversed cable, so VBUS stays on VBUS and GND on GND (pin 4 GND meets ACOK, harmless); D+/D− swap and USB fails to enumerate. The core's `J_USB` uses the same order | P9 |
| OVLO divider | chosen | 100 kΩ / 26.4 kΩ, 0.1 % | trip 5.55–5.95 V including reference tolerance and pin leakage; pin at 4.2 V with 20 V in; 40 µA at 5 V | — |
| VBUS TVS, connector | footprint, not fitted | TI **TVS2200** (WSON-6, 2 × 2 mm) | 22 V VRWM, VBR 24.6–27.6 V, VCLAMP ≤28 V at 40 A, ≤62 nA. Kept as a footprint; the KTS1693 carries its own IEC surge and ESD ratings | fit only if the §16 ESD/surge tests need it |
| VBUS TVS, behind OVP | chosen, fitted | Littelfuse **SMF6.0A**, SOD-123FL | 6 V VRWM, VBR 6.67–7.37 V, VC 10.3 V at 19.4 A, IR ≤400 µA at 6 V; never conducts below the 5.95 V max trip. TVS0500 rejected: 5 V VRWM is under the 5.95 V a source can hold without tripping | leakage at 5 V (counts against USB idle only) |
| VBUS_IN OR (hub: host USB on IN1, chain `AUX_5V` on IN2 for a future Qi board) | chosen | TI **LM66200** | as above; 6.0 V abs-max holds only because the KTS1693 opens by 5.95 V (and the Qi board regulates `AUX_5V`) | — |
| Logic LDO | chosen | TI **TLV75733P** | 1.45–5.5 V in, **6.0 V abs-max**, 1 A, 425 mV max dropout at 1 A, 25 µA Iq, active discharge, SOT-23-5 | thermal at 5 V in |
| VSYS priority mux | chosen | TI **TPS2116**, IN1 = VBUS LDO 3.3 V, IN2 = logic boost 3.3 V | 1.6–5.5 V, **6.0 V abs-max**, 2.5 A (4 A 1 ms pulses), 40 mΩ, 1.32 µA, priority mode, reverse-current blocking | datasheet (rev 7): **switchover `tSW` 8 µs typ at 5 V, 6.2 µs at 3.3 V** (no max); soft start 1.3–1.7 ms applies only at power-up; `VREF` (PR1) 0.92–1.08 V; reverse-blocking response 2 µs. LED rail ~10 µF bulk, no blanking ISR; `VSYS` bulk checked on the §16 hand-over test |
| Logic boost (rev 6) | chosen (rev 7) | TI **TPS61099DRVR**, adjustable, WSON-6 2 × 2 mm, **divider 576 kΩ / 249 kΩ 1 % for 3.3 V** (Phase 3, 2026-09-15; the earlier 2.3 MΩ / 1 MΩ put PFM at ~3.61 V with 50 nA FB leakage) | datasheet-verified: 0.7–5.5 V in, UVLO 0.6–0.7 V rising; Iq 0.4 µA (VIN) + 0.6 µA (VOUT) typ; `VREF` 0.98–1.02 V, PFM ~3 % high; FB leakage ≤50 nA; ILIM 0.8–1.25 A; **down mode regulates while VIN < VOUT + 0.5 V**, pass-through above; true shutdown. **The fixed 3.3 V TPS610994 exists only as YFF WCSP (6-ball, 0.4 mm)**; WSON is sold only as the adjustable and the 3.6 V TPS610995 | PWM 3.20–3.46 V worst case, PFM ~3.56 V (typ offset), 4 µA divider. Efficiency at ~10 µA with the divider; second source on a **dual footprint** (decided 2026-09-14): ADI **MAX17222ELT+** (µDFN-6 2 × 2 mm, RSEL 80.6 kΩ for 3.3 V, 300 nA, 0.88 V start, `IPEAK` 0.40–0.575 A), different pinout; **load check done 2026-09-15**: ~124 mA out at 1.85 V in with 2.2 µH (datasheet p. 14 method, `IPEAK` min, `tON` 330 ns max) vs ~26 mA `VSYS` peak; ULPM output bias +1 to +4 % (3.43 V max) |

## LED rail

| Slot | Status | Part | Key numbers | Verify |
| --- | --- | --- | --- | --- |
| Boost ~5.0 V (E19, 2026-09-26; was 4.7 V) | chosen, **single source accepted** | TI **TPS61023** | 0.5–5.5 V in, **UVLO rising 1.7 V typ / 1.8 V max** (verified), falling 0.5 V, VOUT OVP 5.5–6.0 V, 7 V abs-max, 2.2–5.5 V out, 3.7 A valley limit, 20 µA Iq, auto-PFM, true disconnect in shutdown, SOT563 | bench confirmation at 1.9 V pack (it stays enabled, so it starts once per cell change); the datasheet already guarantees it. No pin-compatible second source exists per TI; recheck stock at Phase 6 |
| VBUS → LED rail | chosen | TI **TPS2116**, priority mode, IN1 VBUS_IN, IN2 boost output | IN1 selected above the `PR1` threshold, whatever the boost is doing. Replaces rev 3's LM66200 auto-OR, which hands LED load to the boost (and so the cells) when VBUS_IN sags below 4.7 V. **`PR1` (E3, 2026-09-15): 301 kΩ / 100 kΩ 1 % from VBUS_IN, 1 MΩ 1 % from `PR1` to `ST`**: `VREF` 0.92–1.08 V puts the drop to IN2 at 3.63–4.40 V (4.3 V nominal would have been 3.90–4.72 V); `ST` is low while IN1 is unused (Table 5-1), so the 1 MΩ adds ~0.3 V of hysteresis, which the datasheet does not provide | bench test at 4.5 / 4.75 V sources (E3); switchover dip vs driver `VIO` rule |
| LED driver | chosen | ISSI **IS31FL3733**, LCSC C506251 | 16 CS / 12 SW, 1/12 duty, 2.7–5.5 V, 6.0 V abs-max, sink headroom ≤400 mV at 672 mA, source ≤200 mV at 42 mA, 2 µA shutdown, Zephyr driver verified | `-B` lifecycle |
| RGB LED | chosen | SunLED **XZMDKCBDDG45S-9**, JLC C5355400 (extended) | datasheet-verified: common anode on pin 2, cathodes 1 R / 3 B / 4 G; IF 30 mA; IFP 185 R / 150 B / 150 G mA (1/10, 0.1 ms); Vf typ 1.95 / 3.3 / 3.3 V, **max 2.5 / 4.0 / 4.1 V** at 20 mA; HBM 3000 / **250** / 450 V; MSL 3; **Ø3.2 mm round board hole**, pads 1.4 × 0.65 mm, 2.25 mm pitch, 5.2 mm span; Vf sorting to ±0.1 V on request | stock; **second source on a combined Ø4.5 mm footprint (decided 2026-09-14, feasibility P1)**: Inolux IN-P32TRRRGB and QT-Brightek QBLP677R-RGB, both common anode, reverse mount, Ø4.5 mm cutout with the body in the hole, ~6.0 mm lead span, 1.5 mm pad pitch, Vf max 2.4–2.7 / 3.6–3.7 / 3.6–3.7 V |
| Expansion LDO | chosen | TI **TLV75733P** | as above, EN from MCU; **3V3 budget 150 mA** (2026-09-15; one expansion board on the hub since rev 8): ~0.26 W at 5 V in | package thermal at 150 mA |

Rejected LED alternates: MEIHUA MHT151RGBCT (LCSC C409782): common cathode, no
IF/IFP/Vf in the datasheet, 2,850 in stock. SK6812MINI-E: ~0.6 mA per LED at rest
(see architecture doc).

## Comms boards (cable) and hub slots (rev 8)

| Slot | Status | Part | Key numbers | Verify |
| --- | --- | --- | --- | --- |
| Slot switch (hub-side comms board, ×3; was rev 7's downstream link switch) | chosen | TI **TPS22950LYBHR** (YBH DSBGA-6, 0.4 mm; the L variant's only package), fed from the LED rail over `J_SLOT`, `ON` from `SLOT_EN` | SLVSFJ2B: 1.8–5.5 V, **6.0 V abs-max**, L variant limit 0.5–3.5 A, 2.7 A continuous, 34–41 mΩ, 40 µA on / 0.2 µA off, **latch-off** after `tDEBOUNCE` 120–188 µs above `IHCD` (§9.3.2), cleared by toggling `VIN` or `ON`; smart pull-down on `ON` (Table 9-2). **No reverse current blocking** (Table 5, RCB "No"): a legacy A-to-C charger in a slot can back-feed the LED rail at ≤5.25 V (architecture §5). Rejected for rev 7's P14: TPS22950CDDCR (SOT-23-6, reverse blocking) because it retries after thermal shutdown instead of latching | **`ILIM` = 624 Ω 0.5 %**: latch-off `IHCD` 1.2–1.9 A (Table 7.5). Load per slot at full white ≤~0.28 A (`right`). Input cap 1 µF (§10.3). Open: E192 624 Ω stock |
| Link ESD, both populations | chosen | TI **TPD6E05U06** | one channel per receptacle pin A5, B5 (CC), A6, B6 (D+ = SDA), A7, B7 (D− = SCL); verified: 6 channels, 0.42–0.5 pF, 5.5 V working, ±12 kV contact / ±15 kV air, IO + GND only, UQFN-14 3.5 × 1.35 mm; stock KiCad `Texas_R-PUSON-N14` land pattern accepted on its citation of an older datasheet's p. 28 | — |
| Link VBUS TVS, both populations | chosen | Littelfuse **SMF6.0A** | as on the USB port board | — |
| CC → `INT` (module population) | proposed | **BAT54C** dual common-cathode Schottky, anodes on CC1/CC2, cathode on the module controller's open-drain `INT` | already in the BOM (rev 7 supervisor supply); isolates an e-marked cable's Ra on the unused CC pin; `INT` low level = `VOL` + ~0.25 V at 33 µA (BAT54 Fig. 1 typ at 100 µA) | against the hub's `VIL` 0.3 × `VDD` once P19 sets `VOL` (E17) |
| `INT` pull-ups (hub population) | **chosen 2026-09-26 (E17)** | **220 kΩ 1 %** from `SLOT_EN` to CC1 and CC2 | USB Type-C spec R2.0 Tables 4-35/4-36: vRa max 0.15 V, threshold 0.2 V, vRd-Connect min 0.25 V; 220 kΩ from ≤3.56 V into 5.1 kΩ +10 % gives ≤~0.09 V, so no sink sees a source (100 kΩ reached ~0.19 V, in the undefined band); off whenever the slot is off; rise ~15 µs with ~70 pF | bench with a phone and a laptop in each orientation |
| Slot I2C switch (hub core) | proposed | TI **TCA9548A** | SCPS207H: 8 bidirectional translating channels, 1.65–5.5 V, three address pins (8 devices), active-low `RESET` that recovers a stuck downstream bus, power-on reset deselects all channels | package and stock; Zephyr binding at our pin (F9) |
| `J_SLOT` / `J_COMM` | proposed | JST GH **SM14B-GHS-TB** (wired connector carrier ↔ socket board) / **SM10B-GHS-TB** (module side) | 14 and 10 are free counts in rev 8; signals in spec §6, pin orders set at capture (mirrored) | P9 |
| Hub stacking headers (2026-09-26) | proposed | 2.54 mm stacking headers: **slot header 2×16** (base board ↔ connector layer), **chain header 2×6** (every layer from the core down), **expansion header 2×10** pass-through (core top ↔ optional layers, X1) | 2.54 mm pitch keeps them hand-solderable (rev 5 rule: no fine-pitch board-to-board); parts not yet chosen | part choice; contact resistance on the chain (E20 assumes ~20 mΩ) |
| `J_MCU` (2026-09-26) | proposed | 2.54 mm **2×25 right-angle** header on the vertical MCU board, straight socket on the base board | ~40 MCU signals + power; USB D± adjacent with GND either side | part choice; USB eye across it (E10) |
| Host USB D+/D− ESD | chosen | ST **USBLC6-2SC6**, **`VBUS` pin (pin 5) on the KTS1693's `OUT`, or NC** (rev 6; pin number corrected 2026-09-14 from ST's Figure 1: 1/6 I/O1, 2 GND, 3/4 I/O2, 5 VBUS, matching KiCad's `Power_Protection:USBLC6-2SC6`) | standard USB 2.0 array; VBUS pin abs-max 5.5 V, so it must never see connector VBUS | — |
| Expansion ESD | chosen 2026-09-15 | TI **TPD4E05U06DQAR** (U1001: 3V3, 5V, SDA, SCL) + **TPD6E05U06RVZR** (U1002: SCK, MOSI, CS, DC, RST, INT), **on the expansion board** (P17) | all ten non-GND pins. SLVSBO7O rev O: VRWM 5.5 V, VBR 6.5–8.5 V at 1 mA, ≤10 nA at 2.5 V, ±12 kV contact. The 5V pin can reach the KTS1693's 5.95 V OVLO trip, above VRWM but below VBR min. TPD4E05U06 (DQA) footprint: SLVSBO7O pp. 29, 32, one library footprint for DQA0010A/B (was also the seam board's part until rev 8) | — |
| Expansion connector and `J_EXP` | chosen 2026-09-15 (P17) | JST **SM12B-SRSS-TB** (12-pin 1.0 mm SH, side entry) on the expansion board (user side); JST GH **SM15B-GHS-TB** `J_EXP` to the hub core | Pinout mirrored with 5V ×2, 3V3 ×2, GND ×3 (spec §6). SH: 1.0 A, 50 V (JST eSH.pdf p. 1); stock KiCad `JST_SH_SM12B-SRSS-TB_1x12-1MP_P1.00mm_Horizontal` checked against the p. 1 side-entry layout | SH and GH 15-pin stock (P9) |
| Expansion rail decoupling | chosen 2026-09-15 | 100 nF X7R 16 V 0603 on 3V3 (C1001) and 5V (C1002) at the socket | short ESD return next to the clamps | — |

Dropped in rev 8 (rows in `0b22b91`): SAMZO PR5L3715-4P-C-H / PR5L2820-4P-C-F seam
pogo halves and their Mill-Max Maxnetic fallback, the seam board's GH 8-pin and
TPD4E05U06 per pair, the 470 Ω link UART series resistors, the upstream link
KTS1693 and its `ISET`, the downstream-population 0 Ω bypass (R604).

## Key board (rev 8)

| Slot | Status | Part | Key numbers | Verify |
| --- | --- | --- | --- | --- |
| Module controller | **chosen 2026-09-26 (P19)** | TI **MSPM0G3505SPTR** (LQFP-48, 0.5 mm, 9 × 9 mm) | SLASEX6C: Cortex-M0+ 80 MHz, 32 KB flash / 16 KB SRAM, 1.62–3.6 V, 44 GPIO (LQFP-48), 2 × I2C (FM+), 4 UART, 2 SPI, QEI timer (dial), STANDBY 1.5 µA, `RPU`/`RPD` 40 kΩ typ, `VOL` ≤0.4 V at 2 mA, ODIO pins 5 V-tolerant open-drain; ROM BSL on I2C (default BSL I2C pins) and UART, `BSL_invoke` pin. Rejected: MSPM0L1306 (SLASEX0D: 28 GPIO incl. SWD in VQFN-32, STANDBY 1.0 µA, no QEI), RP2040 (DORMANT 0.18 mA typ; external flash); STM32G0/C0 and AVR DA not compared (datasheets not downloadable) | Mouser Europe / TME stock and price; second source (G3506/G3507 are the same die family with more flash) |
| Key-board 3.3 V LDO | proposed | TI **TLV75733P** (already in the BOM) | 1.45–5.5 V in, 6.0 V abs-max, 25 µA Iq; three of them are 75 µA of idle on battery against ~0.9 mA average for 6 months (E7); a lower-Iq part is worth checking; reverse-current behaviour on collapse decides how much the driver's series resistors do | Iq vs E7; reverse current |
| Link entry series resistors | proposed | 470 Ω 1 % on SDA and SCL, 1 kΩ 1 % on `INT`, where `J_COMM` enters the key board | E11 values carried over: bound clamp current if a link is pulled live | §16 unplug test |
| Link I2C pull-ups | proposed | 2.2 kΩ 1 % to the key board's 3.3 V | rise ~170 ns at ~90 pF (spec §6), 1.5 mA sink; absent when the key board is unpowered | E16 |
| Driver series resistors | chosen (E11, carried over) | 470 Ω on SDA and SCL, 1 kΩ on `VIO` and `SDB`, at the IS31FL3733 | kept because an LDO that blocks reverse current can hold `VIO` above a collapsing `VCC` (spec §4) | §16 unplug test |
| Module-ID strap | proposed | resistors or pin straps read by the module controller; replaces rev 7's ratiometric ID resistor | exact form set with P19 | — |

Rejected key scanners (rev 8, datasheets read 2026-09-26):

- TI **TCA8418** (SCPS215G): 8 × 10 matrix (80 keys) on 18 GPIOs, 1.65–3.6 V, 10-event
  FIFO, open-drain `INT`, one fixed I2C address, 3 µA idle, WQFN-24; **keypad
  debounce fixed: "All columns are scanned once every 25 ms… it takes 25 ms to
  detect the key press… [or] 40 ms" (p. 33)**. Its ghosting section assumes a
  diode-less matrix.
- TI **TCA6424A** (SCPS193D): 24 GPIO, 1.65–5.5 V, 1 µA standby, 400 kHz, one `ADDR`
  pin (2 addresses), `INT`, UQFN-32; fast on a cable with a port-wide scan, but the
  hub would poll it over I2C, which a radio or optical comms pair cannot carry.

## Input

| Slot | Status | Part | Key numbers | Verify |
| --- | --- | --- | --- | --- |
| Encoder | chosen | Bourns **PEC11R-42xxx-S0024**: 24 detents / 24 ppr, push switch; shaft length (15/20/25/30 mm) and style (F flatted, K knurled, K only 15/20 mm with a switch) fixed in Phase 1 (2026-09-15) | datasheet rev D04/26: both switches open at every detent when pulses = detents; 10 mA at 5 V contact rating; bounce 2.0 ms max at 15 RPM; 60 RPM max; 30 000 rotations, 20 000 switch cycles; wave soldering 260 °C 3 s, **hand soldering "not recommended"** (accepted, build guide note); Bourns advises noise-reduction filters | shaft length/style against the case in Phase 1; lug-to-bushing continuity (not stated) |
| Hotswap socket | chosen | Kailh CPG151101S11 | — | — |
| Key diode | chosen | 1N4148W | orientation set by the module controller's scan direction at key-board capture | — |
| Dial push-switch diode | chosen | **Diodes Inc 1N4148W-7-F** (SOD123), on the dial board, `Device:D` + stock `D_SOD-123` | DS30086 rev 31: 300 mA, 100 V, VF 0.715 V at 1 mA; suggested pads 0.90 × 0.95 mm, 4.05 mm overall; the stock footprint (0.9 × 1.2 mm at ±1.65 mm, 4.2 mm) covers the leads (He 3.55–3.85, L 0.25–0.40) with extra toe | second source (must be SOD-123, not SOD-323 `1N4148WS`) |
| Dial A/B filter | chosen (re-checked 2026-09-26 against the MSPM0G3505's 40 kΩ pull-up: closed ~0.08 V, rise ~0.9 ms; unchanged) | 1 kΩ 1 % 0805 series + 10 nF X7R 50 V 0805 to GND per channel, connector side (2026-09-15) | computed in rev 7 against the nRF52840's internal pull-up; the module controller's pull-ups replace it (P19): **11 / 13 / 16 kΩ** (nRF52840 product spec v1.9 §6.9.3.1, read 2026-09-15): closed level 0.21–0.28 V (< 0.3·`VDD` = 0.97 V), contact discharge 3.3 mA peak (rating 10 mA), rise ≈0.2 ms (≤0.26 ms at 16 kΩ) against ≥10 ms between edges at 60 RPM; Bourns' own circuit (10k pull-up to 5 V, 10k, 10 nF) needs a supply `J_DIAL` does not carry | — |
| Dial ESD | footprint only | **TI TPD4E1U06DBVR**, SOT-23-6, DNP, on the encoder-side A, B, S1, S2 (2026-09-15) | SLVSBQ9D: 4 channels, ±15 kV IEC contact, VRWM 5.5 V, 0.8 pF, 10 nA; land pattern from TI DBV0006A drawing 4214840/G (1.1 × 0.6 mm pads, 2.6 mm centres; stock SOT-23-6 differs) | fit only if the §16 dial ESD test fails |

## Interconnect and service (rev 5)

| Slot | Status | Part | Key numbers | Verify |
| --- | --- | --- | --- | --- |
| Driver hot-unplug resistors (rev 7 figures; rev 8 keeps the resistors, see Key board) | chosen 2026-09-15 (E11) | **470 Ω 1 % on SDA and SCL, 1 kΩ 1 % on `VIO` and `SDB`**, at the IS31FL3733 on the key board; rev 7 had **4.7 kΩ 1 % pull-ups to `VSYS` on the core** | ACK low at the nRF52840 0.68 V vs `VIL` 0.97 V (driver SDA `VOL` unpublished, 0.4 V assumed); rise 201 ns at 50 pF vs 300 ns; clamp ≤0.56 mA on SDA/SCL (bounded by the pull-up), ≤2.9 mA on `VIO`/`SDB`. `SDB` added: push-pull at `VSYS`, same hazard | §16 live-unplug test (no clamp-current limit published); `VIO` supply current unpublished |
| Internal wire-to-board connectors | proposed | **JST GH** family, side-entry SMD headers, positive lock; any fallback must also lock | 1.25 mm pitch; rev 8 uses 5 (`J_DIAL`), 10 (`J_COMM`), 11 (`J_USB`), 14 (`J_SLOT`) and 15 (`J_EXP`), all unique; the battery chain has its own contacts (M10); power nets ≥2 contacts | datasheet-verified (JST eGH): 1.0 A per contact at AWG #26, 50 V, 30 mΩ, −40 to +105 °C, 2–15 circuits, side-entry **SMxxB-GHS-TB** / housing **GHR-xxV-S**; no published derating or mating-cycle figure. European stock; premade cables; link VBUS 2-contact budget vs TPS22950L limit (P9) |
| Internal cables | proposed | premade or crimped GH cables, cut per position | lengths set in Phase 4 | cable drawing in `hardware/lib` |
| SWD access | chosen | Tag-Connect **TC2030-NL** footprint on the hub core, beside the SWD pads; SWD pads for the module controller on each key board (form set with P19) | pads 1 VCC (`VSYS`), 2 SWDIO, 3 nRESET, 4 SWCLK, 5 GND, 6 SWO unconnected (Tag-Connect TC2030-CTX sheet); no part fitted; cable-side legged or clipped variant | footprint against the core's keepouts |
| Module ID | rev 8 | strap read by the module controller (Key board section); rev 7's ratiometric ID resistors and their F6 bands are dropped | — | — |

## Hub core support parts (from the rev 7 core capture, 2026-09-15)

| Slot | Status | Part | Key numbers | Verify |
| --- | --- | --- | --- | --- |
| Slide power switch | chosen | C&K **PCM12SMTR**, side-actuated SPDT, on the chain's `PACK_EN` (common; rev 7: the pack LM66200's `~ON`), TPS3840PH18 output (on) / `PACK_SENSE` (off) | signal-level; off = 0 µA, USB still powers the module; 10 MΩ `~ON`→GND across the gap. Rejected: `MR` to GND (100 kΩ internal pull-up, SNVSB03E, ~30 µA off) | datasheet, land pattern (P18) |
| Reset, bootloader tactiles | chosen | Alps **SKRTLAE010** side-push | pressed through the case wall | datasheet, land pattern (P18) |
| 32.768 kHz crystal | chosen | Epson **FC-135**, CL 9 pF, 3.2 × 1.5 mm; 12 pF C0G load caps | nRF52840 PS v1.9 p. 170: CL ≤12.5 pF, C0 ≤2 pF, ESR ≤100 kΩ, Cpin 4 pF; 2 × 9 − 4 − ~2 pF stray = 12 pF, as Raytac §8.3 | full MPN, ESR, C0 (P18) |
| Logic boost inductor | chosen | Würth **74404024022** (WE-LQS 2512), 2.2 µH, for both boost footprints | datasheet-verified: 1.9 A Isat typ (ΔL 30 %), 1.65 A IR, 80 mΩ; TI SLVSD88M Table 8-2 lists it for VOUT > 3 V; land pattern 1.1 × 2.0 mm pads, 0.8 mm gap (library `L_Wuerth_WE-LQS-2512`; stock 1008 differs). TPS61099 ILIM 0.8–1.25 A and MAX17222 IPEAK ≤0.575 A stay under Isat | — |
| Logic boost caps | chosen | TPS61099: 10 µF in, 2 × 10 µF out (SLVSD88M §8.2.2.5: ≥20 µF nominal); MAX17222: 10 µF in and out (pin table), RSEL 80.6 kΩ, output via a 0 Ω fitted only with it (variant `max17222`) | the 0 Ω keeps the two power outputs apart for ERC, as R604 did on the rev 7 link board | MLCC DC-bias derating |
| LED boost inductor | chosen | Coilcraft **XEL4030-102ME**, 1 µH | TI SLVSF14B Table 8-2: 9.0 A sat, 9.78 mΩ, 4 × 4 × 3.1 mm; above the 3.7 A valley limit, so an LED-rail overload does not saturate it; DC current at 250 mA rail from 1.9 V ≈ 0.78 A at 5.06 V (0.73 A at rev 7's 4.7 V) | datasheet, land pattern (P18) |
| LED boost divider and caps | chosen (divider changed 2026-09-26, E19) | **750 kΩ / 100 kΩ 1 %** (was 698 kΩ / 100 kΩ); 10 µF in, 2 × 22 µF out; no feedforward cap | VREF 580–610 mV (PWM) → **4.93–5.19 V, 5.06 V nominal** (was 4.63–4.87 V), under OVP 5.5 V min and the IS31FL3733's 5.5 V max; FB leakage ≤20 nA adds ≤15 mV; PFM light-load offset unpublished, bench check (spec §16); COUT effective 4–1000 µF, FF cap only above 40 µF | — |
| VSYS mux `PR1` | chosen | 301 kΩ / 100 kΩ 1 % from `VBUS_IN`, own divider, `MODE` to IN1 | IN2 below 3.63–4.40 V while the LDO still regulates | §16 hand-over test |
| VBAT sense | chosen | AOS AO3415A high-side switch, Nexperia 2N7002 gate driver, 1 MΩ gate pull-up, **1 MΩ `BAT_DIV_EN` pull-down R440 (2026-09-16)**, 49.9 kΩ / 49.9 kΩ 1 % | off 0 µA, `AIN0` at 0 V; reading ≤1.9 V, ~38 µA; ≤100 kΩ total keeps `TACQ` short (spec §13) | 2N7002 VGS(th) at 3.3 V gate drive (only pulls a 1 MΩ node) |
| MCU support | chosen | 10 µF + 100 nF on `VDD`, 10 µF on `VBUS`, 27 Ω on D+/D− (Raytac datasheet ver L §8.3; Nordic's reference has no series R); `VDDH` bridged to `VDD` by a solder jumper, DNP 4.7 µF on `VDDH` and DNP 10 µH 0603 `DCCH`→`VDD` (spec §15) | — | — |
| Hub pull resistors | chosen (pruned in rev 8: no `ACOK_LINK`, `VBUS_LINK_IN` or UART pull-downs) | 100 kΩ to `VSYS` on `ACOK_LOCAL`, LED boost `EN`; 100 kΩ pull-down on expansion LDO `EN`; a pull-down on `AUX_5V` (value at hub capture); 4.7 kΩ SDA/SCL and 100 kΩ CS/INT pull-ups to the gated expansion 3V3; 10 µF on expansion 3V3 | `ACOK` pull-ups draw 33 µA only while VBUS is present; firmware keeps expansion pins low or undriven while its rail is off | — |
| TI small-package footprints | chosen | library `TI_SOT-23-5_DBV0005A` (TLV75733P, TPS3840PH18 on the hub core; TPS3840PL35 U801 on the battery board, 2026-09-16), `TI_SOT-563_DRL0006A` (TPS61023), existing DRV0006A footprint for the TPS61099 (same drawing 4222173/C as the TVS2200) | DBV0005A 1.1 × 0.6 mm at 2.6 mm centres (stock 1.325 × 0.6 at 2.275); DRL0006A 0.67 × 0.3 at 1.48 (stock 0.675 × 0.35 at 1.425); SOT-583-8 stock matches DRL0008A. TPS3840 SNVSB03E carries the same DBV0005A drawing 4214839/K | — |

## Open verifications, in priority order

Also tracked in [`open-questions.md`](open-questions.md).

1. Module controller stock and price (MSPM0G3505SPTR).
2. Per-pack ideal diode and chain contacts (E20, M10).
3. RGB LED combined footprint: samples of SunLED, Inolux and QT-Brightek, pinout
   mirror, seating over Ø4.5 mm (P1).
4. Manual European stock check, which automated fetches cannot do (every
   distributor blocks them): KTS1693 and TPS25947 (P7), TPS61099DRVR and
   MAX17222ELT+ (P11), JST GH headers and cables (P9), TCA9548A.

Resolved 2026-09-26 (rev 8, datasheets read): TCA8418 rejected (25–40 ms keypad
detection), TCA6424A rejected (polling), LM66100 rejected as the per-pack diode
(210 mΩ max), TCA9548A proposed for the slots.

Resolved 2026-09-15 (Phase 3 calculations, `tools/sim/`): R806 pack bleeder added
(hot-swap sim), upstream link `ISET` 4.99 kΩ, logic boost divider 576 kΩ / 249 kΩ,
`PR1` 301 kΩ / 100 kΩ + 1 MΩ to `ST`, `J_LED` series resistors and I2C pull-ups,
`LINK_SW_EN` 10 kΩ, expansion 3V3 150 mA budget, MAX17222 load margin, nRF52840
pull-up range (11–16 kΩ).

Resolved 2026-09-14: SAMZO halves share one land pattern (P10), seam board 1.2 mm
for the 1.50 mm spring-half tails; JST GH ratings read from the catalog (no derating
or mating-cycle figure published); IS31FL3733 input limits read (no clamp-current
figure published, E11).

Resolved 2026-09-13: PTC part and resistance (PTSLR12066V175, R1 max 45 mΩ); pack
TVS (SMF4L9.0CA, bidirectional); USB OVP moved to KTS1693 after simulating the discrete design; VBUS TVS (SMF6.0A
behind the OVP); TLV6713's own tpd, IDD and rising-threshold accuracy, which forces
a 0.1 % divider.

Resolved earlier: SunLED datasheet (Vf max, pinout, board hole); TPS2116 /
LM66200 / TPS22950 / TLV757P abs-max (6.0 V); TPS3840 abs-max (12 V); TPS61023
start-up (≤1.8 V); USB OVP comparator supply and FET VDS; pogo mechanical ratings
and a 6-net seam solution; pair-2 capacitance budget and baud.

## Sources

- [TI TLV6713](https://www.ti.com/product/TLV6713), [LM74502](https://www.ti.com/product/LM74502), [TPD6E05U06](https://www.ti.com/product/TPD6E05U06), [ISSI IS31FL3733 datasheet](https://www.lumissil.com/assets/pdf/core/IS31FL3733_DS.pdf), [AO3401A datasheet](http://www.aosmd.com/pdfs/datasheet/AO3401A.pdf)
- [TI TPS2116](https://www.ti.com/product/TPS2116), [LM66100](https://www.ti.com/product/LM66100), [LM66200](https://www.ti.com/product/LM66200), [TPS61023](https://www.ti.com/product/TPS61023), [TLV6703](https://www.ti.com/product/TLV6703), [TPS3839](https://www.ti.com/product/TPS3839), [TPS3840](https://www.ti.com/product/TPS3840), [TPS22916](https://www.ti.com/product/TPS22916), [TPS22950](https://www.ti.com/product/TPS22950), [TLV757P](https://www.ti.com/product/TLV757P), [TPD1S514](https://www.ti.com/product/TPD1S514)
- [AO3415A datasheet](http://www.aosmd.com/pdfs/datasheet/AO3415A.pdf), [ElecSuper AO3415A (LCSC)](https://datasheet.lcsc.com/lcsc/2504101957_ElecSuper-AO3415A_C5350990.pdf), [DMP1045U datasheet](https://www.diodes.com/assets/Datasheets/DMP1045U.pdf)
- [Eaton PTSLR1206](https://www.eaton.com/us/en-us/catalog/electronic-components/ptslr1206-ptc-resettable-fuse.html), [PTSLR1206 datasheet (Farnell copy)](https://www.farnell.com/datasheets/3169278.pdf)
- [Kinetic KTS1693 datasheet](https://www.kinet-ic.com/uploads/web/KTS1693/KTS1693-04d.pdf), [TI TLV6713 datasheet](https://www.ti.com/lit/ds/symlink/tlv6713.pdf), [TI TVS2200 datasheet](https://www.ti.com/lit/ds/symlink/tvs2200.pdf), [TI TVS0500 datasheet](https://www.ti.com/lit/ds/symlink/tvs0500.pdf), [Littelfuse SMF5.0AT1G series](https://static.datasheets.com/doc/9941545-littelfuse-smf11at1g-ds.pdf), [Littelfuse SMF4L series](https://www.littelfuse.com/assetdocs/tvs-diodes-smf4l-datasheet?assetguid=d2ba8fab-1de3-4176-8530-f36ecb0b8799), [SMF9.0CA (TME, DC Components)](https://www.tme.com/us/en-us/details/smf9.0ca-dc/bidirectional-tvs-smd-diodes/dc-components/smf9-0ca/), [onsemi BSS138](https://www.onsemi.com/products/discrete-power-modules/mosfets/small-signal-mosfets/bss138)
- [SunLED reverse-mount RGB](https://www.digikey.com/en/product-highlight/s/sunled/reverse-mount-rgb-plcc-smd-led), [XZMDKCBDDG45S-9 spec](https://www.sunledusa.com/products/spec/XZMDKCBDDG45S-9.pdf), [JLC C5355400](https://jlcpcb.com/partdetail/SunLED-XZMDKCBDDG45S9/C5355400), [MEIHUA MHT151RGBCT (LCSC C409782)](https://www.lcsc.com/product-detail/C409782.html)
- [Bourns PEC11R datasheet](https://www.bourns.com/docs/Product-Datasheets/PEC11R.pdf), [PEC11R-4220F-S0024 (DigiKey)](https://www.digikey.com/en/products/detail/bourns-inc/PEC11R-4220F-S0024/4499660)
- [SAMZO PR5L3715-4P-C-H (LCSC C41361287)](https://www.lcsc.com/product-detail/C41361287.html), [SAMZO PR5L2820-4P-C-F (LCSC)](https://www.lcsc.com/product-detail/Pogo-Pin-Spring-Probe-Connector_SAMZO-PR5L2820-4P-C-F_C41361286.html), [Mill-Max SMT target discs](https://www.mill-max.com/products/new/low-profile-smt-target-discs), [Mill-Max 858-22-004-30-011101](https://www.digikey.com/en/products/detail/mill-max-manufacturing-corp/858-22-004-30-011101/ED11067-ND/7313766), [Mill-Max 856-10-004-40-001000](https://www.digikey.com/en/products/detail/mill-max-manufacturing-corp/856-10-004-40-001000/5880278)
- [onsemi NCP361 datasheet](https://www.onsemi.com/pdf/datasheet/ncp361-d.pdf), [TI TPS61033](https://www.ti.com/product/TPS61033), [TI E2E: no drop-in TPS61023 replacement](https://e2e.ti.com/support/power-management-group/power-management/f/power-management-forum/942424/tps61023-direct-replacement-for-tps61023)
- OVP ICs surveyed: [KTS1693](https://www.kinet-ic.com/kts1693/), [NX30P6093A](https://www.nxp.com/docs/en/data-sheet/NX30P6093A.pdf), [BCT7915](https://www.broadchip.com/Public/Uploads/uploadfile/files/20241213/BCT7915.pdf)
- Rev 8 (read 2026-09-26): [TI TCA8418 (SCPS215G)](https://www.ti.com/lit/ds/symlink/tca8418.pdf), [TI TCA6424A (SCPS193D)](https://www.ti.com/lit/ds/symlink/tca6424a.pdf), [TI TCA9548A (SCPS207H)](https://www.ti.com/lit/ds/symlink/tca9548a.pdf), [TI LM66100 (SLVSEZ8A)](https://www.ti.com/lit/ds/symlink/lm66100.pdf); Qi2 receiver lead from a web search only: [ST community, STWLC89](https://community.st.com/power-management-53/qi2-2-25w-receiver-160236)
- Module controller (read 2026-09-26): [TI MSPM0G350x (SLASEX6C)](https://www.ti.com/lit/ds/symlink/mspm0g3507.pdf), [TI MSPM0L130x (SLASEX0D)](https://www.ti.com/lit/ds/symlink/mspm0l1306.pdf), [RP2040 datasheet](https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf); also downloaded, not used: MSPM0C1104
- Type-C sink thresholds (read 2026-09-26): [USB Type-C Cable and Connector Specification R2.0, Aug 2019](https://www.usb.org/sites/default/files/USB%20Type-C%20Spec%20R2.0%20-%20August%202019.pdf), Tables 4-35/4-36
