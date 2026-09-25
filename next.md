# Next

State 2026-09-26. Spec rev 7 (`plans/keyboard.md`). Nothing committed. Branch `next-steps`.
Written for a fresh session: read this file, then `plans/keyboard.md` §2a/§4/§5/§6/§12/§16 for the board you touch.
**Next up: task 1, the core PCB's last 7 real unconnected.** The user wants to rethink how to finish them. Start by presenting the options in task 1 (AskUserQuestion); don't pick one silently. Everything needed is in "Core PCB now" and task 1.
KiCad was closed at the end of the last session (board re-checked after closing: same numbers; a stale 2026-09-16 `~core.kicad_sch.lck` removed). Before any `pcbnew` script, check `pgrep -lf MacOS/kicad` is empty. Before any Konnect write, check the schematic editor is closed (see gotchas).

## Rules
- Parts from Mouser Europe/TME/Farnell. LCSC = reference only.
- Undecided part/value → AskUserQuestion, pros/cons, recommended first. No silent picks.
- Numbers only from datasheets actually read. Cite. Flag unverified.
- Missing tool/file → ask user. No commits unless asked. Don't touch repo-root PDFs.
- Schematics are owned by `tools/sch_*.py`; never edit in Eeschema/MCP. PCB: KiCad + Konnect MCP, or KiCad's Python `pcbnew` with KiCad closed (see gotchas).
- `hardware/` is **not in git**. Back up a board file before any scripted rewrite, **and check `core.kicad_pro` is unchanged afterwards** (see the `SaveBoard` gotcha).
- **Test the premise before building on it**: a quick synthetic check (two tracks on a blank board) takes minutes. A broken rules file cost a day on 2026-09-25.
- Record each decision in `plans/keyboard.md`, `docs/02-parts-shortlist.md`, `docs/open-questions.md` (delete closed), `hardware/README.md`, this file.

## Status
Schematics done (ERC 0): core 4xx (A1 sheet, variants `tps61099`/`max17222`, 89 nets), battery 8xx (U801 on `keyboard:TI_SOT-23-5_DBV0005A`; both TPS3840 symbols default to it), usb-port 5xx, link 6xx, seam 7xx, dial 9xx (PCB trial-routed, DRC+parity 0), expansion 10xx (SM12B-SRSS-TB, TPD4E05U06 + TPD6E05U06, mirrored `J_EXP` 1 5V 2 GND 3 3V3 4 SCL 5 SDA 6 RST 7 DC 8 GND 9 CS 10 MOSI 11 INT 12 SCK 13 3V3 14 GND 15 5V).
Not started: keys-* 1xx–3xx (wait for Phase 1, P1).

Core decisions 2026-09-15 (spec §4, §6, §13, §18; parts list "Core support parts"): slide switch = SPDT on pack LM66200 `~ON`; VSYS PR1 own 301k/100k from VBUS_IN; VBAT sense high-side AO3415A + 2N7002, 49.9k/49.9k; `J_LED` RAIL×2 VSYS×2 mirrored (1 RAIL 2 GND 3 SDA 4 VSYS 5 SDB 6 GND 7 GND 8 ID 9 VSYS 10 SCL 11 GND 12 RAIL); `J_ROW` 1-3 ROW0-2, 4 GND, 5-7 ROW3-5; `J_COL` 1 GND, 2-10 COL0-8, 11 ENC_A, 12 ENC_B, 13 GND; `J_LINK` 1 VBUS_LINK_IN 2 GND 3 U0_TX 4 U1_A 5 GND 6 LINK_SW_EN 7 VBUS_IN_OUT 8 VBUS_IN_OUT 9 ACOK_LINK 10 GND 11 U1_B 12 U0_RX 13 GND 14 VBUS_LINK_IN. Key boards must use these orders.
Core review 2026-09-16: R440 1M `BAT_DIV_EN`→GND (variants now 108/107 fitted); R412 stays on VSYS (VSYS is the regulated 3.3 V `VDD` rail); H401–H404 4× M2 corners as symbols; core PCB 4 layers (`gen_kicad.py` `FOUR_LAYER`, placeholder 0.2/1.04/0.2 dielectrics until a fab stackup is chosen).
Phase 3 calcs 2026-09-15 (`tools/sim/phase3_calcs.py`, `tools/sim/e14_pack_swap.py`; results in spec §4/§5): E9, E11, E12, E14 closed; E3/F6/E15/P11 narrowed. Battery adds R806 330k CELL+ bleeder; link upstream R603 ISET 1M → 4.99k.
Interconnect audit `tools/check_interconnect.py` (runs inside `kicad-check.sh`): 16 GH headers, 5 mated pairs pass, 7 pending keys-*, 0 errors.

## Core PCB now (`hardware/core/core.kicad_pcb`, 2026-09-26)
**Checks** (last run 2026-09-26, after reverting the trial pin swap): ERC 0. DRC 8 errors, all `hole_clearance` inside the stock Alps SW401/SW402 footprints (own pads 0.099 mm from own NPTH vs the 0.25 mm rule; decide with P18). 295 warnings (145 silk over copper, 129 silk overlap, 6 silk edge, 6 `lib_footprint_mismatch`, 9 `via_dangling` = old Freerouting half-routes on the open nets). Parity: U407 only (no footprint, MAX17222). **15 unconnected = 8 on purpose + 7 real** (task 1).
Backups in `hardware/core/`: `core.pre-ripup.kicad_pcb` (11 real, before 2026-09-24), `core.pre-task1.kicad_pcb` (first autoroute, 48 unconnected), `core.pre-freerouting.kicad_pcb` (hand copper only). Delete all three once the route is accepted. Known-good `core.kicad_pro` copies: `build/core-esc2/core.kicad_pro` (the 2026-09-26 file differs from older copies only in the order of the two variant entries).

**Placement** (Konnect score 100/100):
- Outline 32 × 90 mm, corners r1, (100, 100) → (132, 190). 4 copper layers. 121 footprints, all on F.Cu.
- **Antenna: top short edge.** U401 (MDBT50Q-1MV2) at (116, 108.25), body top flush with y=100. Raytac ver L §2.3: **no copper on any layer in y 100–103.8, full width**. Rule areas `ANTENNA_KEEPOUT_ROUTING` (blocks tracks/vias/pours) and `ANTENNA_KEEPOUT_PADS` (blocks pads, except 2.2 mm squares around NPTH H401 (102.5, 102.5) / H402 (129.5, 102.5)) on all 4 layers. H403/H404 at y 187.5.
- **U401 pad field** (`RF_Module:Raytac_MDBT50Q`): left pads 1–14 in two staggered columns x 111.35 / 112.25; bottom pads 15–33 staggered y 115.4 / 114.5; right pads 34–55 staggered x 120.65 (outer) / 119.75 (inner), 0.8 mm pitch per row, **0.40 mm between outer pads**; inner row 56–61 at y 108.8, x 114.0–118.0. The crystal Y401 + C402 sit **right below bottom pads 17–21** (Y401.2 XL2 pad x 114.0–115.1, y 117.2–119.0).
- **Left edge (x 103.2, rot 270), key board:** J407 ROW y 111.6, J408 COL 129.55, J409 LINK 151.88, J406 LED 173.59.
- **Right edge (x 128.8, rot 90):** J404 EXP y 116.6, J405 USB 138.3, J402 BAT_A 153.13, J403 BAT_B 163.59, J401 Tag-Connect 173.0.
- **Bottom edge:** SW401 reset (108.3, 187.7), SW402 boot (114.5, 187.7), SW403 power (122.6, 186.6); actuators toward +y.
- **Middle channel x 106.4–125.6, top to bottom:** crystal Y401 + C401/C402 at the module, C403/C404 at pad 28, C405 at pad 32, pull-up row y 123.2, VBAT sense Q401/Q402 + R419–421, Li-ion DNP group JP401/C406/L401, expansion LDO U411 + C425 beside J404, UART series/pull-downs y 137–141.5, VBUS OR U404 + LDO U405 + VSYS mux U408 y 132–144, pack OR U402/D401/U403 y 148–157, logic boost U406/L402 y 156–164, **3 × 3 mm free at (111.5–114.5, 166.1–169.1) for U407**, MAX branch L403/C417/C418/R425/R426, LED boost U409/L404/C421/C422 + mux U410 y 172–181, **R434 rotated 180° on 2026-09-24** (pad 1 `PR_LED` top at (122.4, 175.975), pad 2 `LED_ST` bottom), TP401–411 bottom right, TP412–421 at x 108–112, y 146–152.

**Rules & layers** (`core.kicad_pro` net-class patterns on `/NET`, plus `core.kicad_dru`): stackup stays **generic** (user: JLC-like 0.127 mm track / 0.2 mm drill; pick the fab later, widths may need a pass then).
- `Default` 0.2 mm / 0.15 clr, via 0.6/0.3. `USB` (`USB_DP/DN`, `_MCU`) 0.2 mm, gap 0.2 (Full Speed, no impedance target).
- `VBUS_HI` (`VBUS_IN`, `VBUS_LINK_IN`, `VBUS_LOCAL`; KTS1693 latch 1.82–2.18 A) **0.6 mm, F.Cu/B.Cu only** (IPC-2221 est. ~20 °C on 1 oz outer; not a fab figure), clr 0.2, via 0.8/0.4.
- `POWER` (`VBAT`, `PACK_A/B`, `VSYS`, `V3P3_*`, `LED_RAIL`, `LED_BOOST`, `EXP_3V3`, `SW_*`) 0.4 mm. Neck down to ~0.28 mm for ≤1 mm at SOT-583/WSON pads.
- **U401 escape rule (2026-09-25, spec §12):** non-blocking rule area `U401_ESCAPE` (x 109.2–122.8, y 103.8–117.5, F/B.Cu) + `core.kicad_dru`: inside it, everything except `POWER`/`VBUS_HI`/`USB` may use **0.127 mm track and clearance and 0.5/0.25 mm vias**, with `opt` values so KiCad's interactive router picks them by itself there. Verified working 2026-09-25 (a candidate at 0.1365 mm passes). **Values must carry units (`0.127mm`)**: with bare numbers KiCad 10.0.6 silently ignores the whole file.
- **In1.Cu = zone `GND_IN1`, whole board. In2.Cu split: `VSYS_IN2` y 100–146, `VBAT_IN2` y 146.5–190.** A VSYS/VBAT/GND pad connects by a via into its plane, no trace, **but only if the pad sits over its own In2 region** (VBAT north of y 146.5 or VSYS south of 146 needs a real trace).

**Routing:**
- Hand-routed (Konnect), keep: TPS61099 loop per SLVSD88M Fig. 8-9 (L402 (116.4, 159.05) r270, C414 (113, 157.4), C415/C416 (110.1/108.1, 160), R423/R424 under FB); USB pair U401.34/35 → R401/R402 → corridor x 125.3 (DP) / 125.7 (DN) → J405.5/.7, D+/D− order swap by DP passing between R402's pads; pack OR U402 (PACK_A on F.Cu, PACK_B on B.Cu, J402/J403 pins 1/4 joined at x 128.6); VBUS OR U404 r180 with VBUS_LOCAL/VBUS_LINK_IN/VBUS_IN trunks (B.Cu x 118.6 → J409.7/8); module VSYS/VBUS_LOCAL/GND vias; U408 VSYS bridged under the body.
- **U410 corner (2026-09-24, spec §12):** `LED_BOOST` U410.6 → centred 0.28 mm stub (≤1.1 mm, between U410.7 and U410.5) → via (121.2, 177.45) → 0.4 mm on B.Cu under U410 → via (116.9, 176.9) → C422.1. `LED_ST` U410.8 dips to y 176.75 → R434.2; `PR_LED` crosses under it via (121.2, 176.15) and a B.Cu run round the `LED_BOOST` via down to U410.4's via (118.66, 178.56). Script: `build/core-rip/ledfix3.py`.
- Rest: Freerouting 2026-09-17 (`build/core-reroute/`: `fanout.py` → `shiftbus.py` → `preroute.py` → `lock_export.py` + `patch_dsn.py` → Freerouting → `import_ses.py` → `finish.py` → `clean_dangling.py`), then the 2026-09-24 transactional rip-up (`build/core-rip/txn.sh` → `txn.py` on `txn_lib.py`: a change is kept only if every net it disturbs re-joins and DRC is unchanged), which closed `V3P3_LDO` (0.4 mm), `EXP_SCL`, `SWDCLK` and `LED_ST`.
- **Unrouted on purpose until P18 verifies the footprints:** `XL1`/`XL2` (Y401, C401, C402), `SW_LED` (U409/L404), `LED_BOOST` at U409/C421/C422/R429. Autorouted copper on the SW401–403 nets (RESET/BOOT/power) sits on stock footprints: rip it up if P18 changes them.

## Tasks, in order
1. **Core PCB: the last 7 real unconnected.** Exact gap ends (board mm, from the 2026-09-26 DRC):
   | Net | Gap end A | Gap end B | Notes |
   | --- | --- | --- | --- |
   | `NRESET` | track end at U401.40 (119.75, 111.60) | via (108.40, 151.05), TP421/SW401 side | P0.18, fixed pin; inner right row |
   | `BOOT` | SW402.1 (115.72, 186.80) | U401.39 (120.65, 112.00) | outer right row; runs the full board length |
   | `SWDIO` | U401.51 (120.65, 106.40) | track end (110.00, 150.00), TP419 side | fixed pin; also goes to J401.2 |
   | `EXP_SDA` | track end (126.95, 120.35), J404.5 | track end (110.00, 152.00), TP410 | U401.47 side is routed |
   | `EXP_LDO_EN` | via (118.67, 114.28) (also via (118.07, 113.22)), U401.29 side | track corner (122.35, 124.68), U411.3/R435.1 side | must cross the USB pair and the B.Cu VSYS/VBUS_LOCAL diagonals |
   | `VBAT_SENSE` | track end (113.40, 127.17), R420.2 | via (111.73, 113.20), U401.11 side | analog (AIN0) |
   | `COL0` | track end (105.05, 123.30), J408.2 | via (114.97, 110.46), U401.56 side | inner row under the module |
   Every scripted route needs more than 5 other nets moved, or moves a net that then can't re-join. The bottleneck is the U401 fan-out, not board area.
   **Options to put to the user** (they want to reconsider the approach):
   - a. **Interactive routing in KiCad, user drives, Claude guides net by net** (was about to start with `EXP_LDO_EN`): open only the PCB editor. Route → Interactive Router Settings… (`Cmd+<`; *not* in Preferences) → Mode *Shove* + *Shove vias* (already set on the user's machine). Keys: `X` route, `` ` `` highlight net, `F` auto-finish, `V` via + layer flip, `/` posture, `Back` undo segment, `Cmd+E` continue from a track end, `Esc` cancel, `Cmd+Z` undo, `Cmd+F` find a ref. **The user is new to KiCad**: give one net at a time, say which pad or via to hover, which direction to go, where to press `V`, what not to shove (USB pair, thick power tracks). DRC after each save (command below). The fine U401 rule now works, so shove can use the 0.40 mm gaps between outer pads.
   - b. **Computer use**: rerun the session in the Claude desktop app with computer use enabled, and Claude drives KiCad's shove router via screenshots. Slow; aiming at 0.4 mm pads from screenshots is error-prone. Not tried.
   - c. **A cloud autorouter** (DeepPCB, Quilter; not tested): means uploading the design to a third party. User decision.
   - d. **Structural change** (user decision): signals on In2 through the VSYS/VBAT split; 6 layers; re-place the module fan-out area (e.g. move the crystal or the pull-up row away from the module's bottom edge).
   - e. Write a proper negotiated-congestion router (all nets at once, segment-exact clearance). Large effort, uncertain.
   **Tried and dropped (don't repeat):** Freerouting with unlocked signal copper (it never rips up existing wires); 34 mm outline via a stretch at x 106.5 + full signal re-route (12 open; the new lane is crossed by 71 fan-out tracks); transactional rip-up with the working fine rule on the original pin map (`build/core-esc2/`, stays at 7); **trial U401 pin swap** (VBAT_SENSE 11→20, BOOT 39→21, EXP_SDA 47→39, COL0 56→11): stays at 7, and pads 20/21 sit right above the crystal. Reverted 2026-09-26, spec §5 pin table unchanged. (Earlier "fine rule doesn't help" and "regional re-route ended at 31" results ran with the rules file silently ignored, so they aren't valid tests; with the working rule, the rip-up stayed at 7.)
   Done = 8 unconnected (on-purpose), DRC the 8 SW401/SW402 errors, parity U407 only. Then update this file, the `hardware/README.md` core row and spec §12, and delete the three backups.
2. **Core PCB finish:** GND pours on F.Cu and B.Cu (a whole-board trial with 0.2 mm clearance, thermal pads gave 16 `starved_thermal` before task 1's vias; add stitching vias or use solid connections where it still starves), keep them out of the antenna strip (rule area already blocks pours), then silk cleanup (6 refs clipped by the edge, ~130 overlaps), then DRC + parity back to the numbers above (warnings down). Delete the 9 dangling Freerouting half-route vias once their nets are routed.
3. **Core PCB leftovers:** the 6 `lib_footprint_mismatch` (U402/U404/U408/U410 SOT-583-8, J401, U401) need KiCad's own Tools → Update Footprints from Library (Konnect's refresh refuses them: `solder_mask_margin`/`unlocked`/`zone`). SW401/SW402 hole clearance: relax the 0.25 mm rule or swap the footprint (P18).
4. Optional: expansion PCB (board size open). Check whether keys-* boards overflow 99 refs of one type (diode + LED per key) in their 100-ref range.
5. Optional: dial re-route (S1/S2 out from under the encoder, drop the U901 detour; keep DRC+parity 0). Link sheet cosmetic: parts past the A4 edge, notes below the frame (rerun with `paper="A3"`).
6. Later (Phase 1 / P1): keys-* schematics (`hardware/common` LED matrix + link routing sheets) using the core header orders above; move each key-board mate from `PENDING` to `MATES` in `tools/check_interconnect.py`; key board side of `J_LED` carries 1 kΩ VIO/SDB and 470 Ω SDA/SCL at the driver.
7. Later: firmware core board devicetree from the §5 pad table and `sch_core.py` MCU_PINS (UARTE0 P0.06/P0.07, UARTE1 P0.08/P1.08, TWIM0 P0.13/P0.14, TWIM1 P1.00/P0.24, SPIM3 P0.22/P0.23; AIN0 VBAT, AIN1 ID, AIN5 CC2, AIN7 CC1; `CONFIG_NFCT_PINS_AS_GPIOS=y`).

## Blocked on user
- Stock checks (add core parts: FC-135, SKRTLAE010, PCM12SMTR, XEL4030-102ME, 74404024022): P7, P8, P9, P11, P15, USB4085, TVS2200, CRCW1206 jumper, 624 Ω 0.5 % 0603, JST SM12B-SRSS-TB, JST SM15B-GHS-TB.
- Files: Keystone 2462 drawing (P15), Maxim 90-0004 (MAX17222; U407 stays footprint-less until then), MDBT50Q-U1MV2 datasheet (pad numbering vs 1MV2), P18: Epson FC-135 (MPN, ESR, C0), Alps SKRTLAE010, C&K PCM12SMTR, Coilcraft XEL4030 (vs XAL4030 footprint).
- Samples: LEDs (P1), PEC11R lug continuity (E15).
- Case fit: the 32 × 90 mm core outline is placement-driven and unchecked against any case (M6).

## Commands
- kicad-cli: `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli` (10.0.6)
- KiCad Python (has `pcbnew`): `/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3`
- Library: add to `tools/gen_kicad.py` (cite datasheet) → `python3 tools/gen_kicad.py`
- Schematic: `cd tools && ../.venv/bin/python sch_<board>.py --force` (checks netlist + variant BOMs)
- Check all: `tools/kicad-check.sh` → ERC 0 everywhere; DRC 1 "no board outline" on unlaid boards (the script exits 1 because of these); dial 0; core 8 (SW401/SW402) + 15 unconnected; interconnect 0 errors (`build/kicad-check/interconnect.rpt`).
- Board DRC + parity: `kicad-cli pcb drc --schematic-parity --severity-all --format json -o /tmp/x.json hardware/<board>/<board>.kicad_pcb` (add `--refill-zones --save-board` after any via/zone edit). `--format report` names the rule behind each violation. Score the JSON with `python3 build/core-rip/score.py x.json` (real vs on-purpose unconnected, errors by type, parity).
- Copper map of a window (F red, B blue, nets labelled): `<KiCad python> build/core-rip/snap.py board.kicad_pcb x0 y0 x1 y1 out.svg` → `qlmanage -t -s 1400 -o . out.svg`. Works on a copy while KiCad is open (read only).
- Board render: `kicad-cli pcb render --side top --width 1200 --height 3000 -o /tmp/x.png hardware/core/core.kicad_pcb`.
- Venv: `python3 -m venv .venv && .venv/bin/pip install kicad-sch-api`
- Phase 3 sims: `python3 tools/sim/phase3_calcs.py`; `python3 tools/sim/e14_pack_swap.py [case]` (ngspice-47, decks in `build/sim/`).
- Datasheets → scratchpad; `pdftotext -layout`, `pdftoppm -png`. Render sheet: `kicad-cli sch export svg`. SVG → PNG: `qlmanage -t -s 1400 -o <dir> f.svg` (ImageMagick hangs on SVG; no rsvg/matplotlib/PIL).
- curl works: ti.com/lit/ds/symlink, ti.com/lit/ml, bourns.com/docs, diodes.com/assets, raytac.com/download/index.php?index_id=43 (MDBT50Q-1MV2 ver L; needs a browser User-Agent). Blocked: eaton, keyelco, nordicsemi, onsemi, nexperia, littelfuse, st, Mouser/Arrow → ask user.

## Gotchas
- kicad-sch-api 0.5.6: symbols unrotated; hidden no_connect pins → `"-"`; always writes `(in_bom yes)` (`schlib.post_process` fixes, and writes KiCad 10 variants).
- Derived symbols (`extends`, e.g. `Diode:1N4148W`, `Regulator_Linear:TLV75733PDBV`, `Transistor_FET:2N7002`) → ERC mismatch; use `Device:D` / `Q_NMOS_GSD` / a `keyboard:` copy. Hidden stacked pins must be passive.
- Changing a symbol's default footprint in `gen_kicad.py` leaves every schematic that already embeds it reporting `lib_symbol_mismatch` until each `sch_*.py` is rerun with `--force`.
- Variant BOM check skips `in_bom no` symbols (solder jumpers). Stock TPS61099DRV types SW as power_in → PWR_FLAG on the SW net.
- ERC ignores variants: two `power_out` pins (or `power_out` + PWR_FLAG) on one net = error. Put variant-exclusive outputs on opposite sides of a jumper.
- **A reboot wipes `/tmp` and the session scratchpad** (lost a finished autoroute on 2026-09-17). Keep long pipelines and their boards in `build/` (git-ignored).
- Stock footprints often ≠ vendor land pattern; check each. Connector pin 1 is convention; check how halves mate.
- `kicad-check.sh` rewrites `hardware/lib/keyboard.kicad_sym` in KiCad format; a big diff after `gen_kicad.py` is expected.
- Blocked datasheet hosts also: epson, ckswitches, alpsalpine, coilcraft (we-online and tag-connect work).
- **KiCad custom rules (`.kicad_dru`) need units on every value** (`(min 0.127mm)`). With bare numbers KiCad 10.0.6 ignores the whole file without any error; DRC then reports 0.15 mm netclass clearances labelled "Local override". Test a new rule on a two-track board first (`build/core-esc/synth/mk.py`). The DRC copy of a board needs `<name>.kicad_dru` next to it.
- **`pcbnew.SaveBoard(out)` also writes `<out>.kicad_pro`** from the settings the board was loaded with. Loading a board whose basename has no `.kicad_pro` (e.g. a backup) and saving it as `core.kicad_pcb` overwrote `core.kicad_pro` with defaults on 2026-09-25 (restored). Always load from the real name, and compare the `.kicad_pro` afterwards.
- **`pcbnew` Python board edits** (work well for exact geometry): only with KiCad **closed** (`pgrep -lf MacOS/kicad` empty), or the GUI overwrites the file on save. `b = pcbnew.LoadBoard(path)`; tracks via `b.GetTracks()` (`PCB_VIA_T` for vias); new segment `t = pcbnew.PCB_TRACK(b)`, `SetStart/SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(x), …))`, `SetWidth`, `SetLayer(pcbnew.F_Cu)`, `SetNet(b.FindNet("/NET"))`, `b.Add(t)`; new via `pcbnew.PCB_VIA(b)` + `SetPosition`/`SetDrill`/`SetWidth`; `pcbnew.SaveBoard(path, b)`. Then `kicad-cli pcb drc --refill-zones --save-board`. **`GetStart()`/`GetEnd()` return live references**: copy (`V(p.x, p.y)`) before calling `SetStart`/`SetEnd` on the same item. **Keep removed items referenced** (`GRAVE.append(t); b.Remove(t)`): when a removed track's wrapper is garbage-collected, SWIG breaks (`SwigPyObject … no attribute 'Pads'`). New nets: `b.Add(pcbnew.NETINFO_ITEM(b, name))`. Harmless noise: the wxApp `assert "traits"` line, `swig/python detected a memory leak`, `PCB_VIA::GetWidth called without a layer`. A track end landing mid-segment counts as connected. Net names carry the `/` prefix (`GND` does not). Rule areas, zones and net classes survive the load/save round trip. Run DRC from a folder without `fp-lib-table` and you get `lib_footprint_issues` (copy one with absolute paths, as in `build/core-esc/`).
- Rip-up tooling (`build/core-rip/`, `build/core-esc2/` = escape-rule aware): `txn_lib.py` is a 0.1 mm grid A* router with soft obstacles; it can't leave a 0.5 mm-pitch SOT-583 pad whose centre is off-grid (hand-place the escape). One-connection-at-a-time routing packs a fan-out badly.
- **Freerouting headless** (Konnect `export_specctra_dsn` fails on all boards; the PCM plugin needs the GUI): on a copy, `pcbnew`: lock tracks (`SetLocked(True)`, exported as `(type fix)`) → `pcbnew.ExportSpecctraDSN(b, "x.dsn")`. Patch the DSN: `(layer In1.Cu\n      (type signal)` → `(type power)` (same for In2) so nothing routes across the planes, and delete `(net /NAME (pins …))` blocks (plus the name in its `(class …)` list) for nets to leave unrouted. Run `java -jar ~/Documents/KiCad/10.0/3rdparty/plugins/app_freerouting_kicad-plugin/jar/freerouting-2.4.1.jar -de x.dsn -do x.ses -mp 100 --gui.enabled=false` (~6–10 min for core, Java Temurin 25) → load the locked board, `pcbnew.ImportSpecctraSES(b, "x.ses")`, save, unlock, DRC. Its own plane fanout leaves GND stubs without vias, so add a plane via for every plane pad before exporting (`build/core-reroute/fanout.py`). It can't shove or rip up existing wires: unlocked copper in the DSN just stays as it is.
- **KiCad 10.0.6 segfaults (`API_HANDLER_EDITOR::checkForBusy`, eeschema kiface) when a Konnect PCB write arrives while the schematic side is loaded.** Update PCB from Schematic (F8) loads it. So: F8 in one KiCad session, then quit KiCad, reopen with only the PCB editor, and only then drive Konnect. Nothing is lost by the crash if the board was saved, but Konnect then refuses file writes ("previously reached KiCad") until it restarts.
- Konnect 0.11.1 KiCad MCP (https://github.com/mixelpixx/Konnect; PCB only; needs KiCad open, board in PCB Editor, KiCad API enabled; start `get_installation_info` → `open_project` → `list_toolboxes` → `load_toolset`). **It has no shove or pathfinding**: `route_trace`/`route_pad_to_pad` draw exactly the given path without DRC.
  - `update_pcb_from_schematic` refuses the whole netlist while any symbol lacks a footprint (U407); use KiCad's F8 instead. It also needs the schematic closed in Eeschema.
  - `set_component_placements` in batches of ~25 is reliable; rotation 90 maps footprint local +y to board +x (GH horizontal headers: signal pads inboard, MP pads at the edge).
  - `save_project` saves the board. `score_placement`, `run_drc`, `get_board_2d_view` and kicad-cli all read the **file**, so save before trusting them.
  - `add_zone` makes copper zones only, no rule areas/keepouts.
  - `update_footprints_from_library` refuses pads with `solder_mask_margin`/`unlocked`/`zone`; pass `references` to skip, or do it in the KiCad GUI.
  - `export_specctra_dsn` fails on all boards → headless Freerouting above.
  - Mounting holes: `place_component` `MountingHole:MountingHole_2.2mm_M2_ISO7380`.
  - Vias/zones added over IPC are not refilled in the saved file: run `kicad-cli pcb drc --refill-zones` or it reports false `via_dangling`/zone clearance errors.
  - No via delete tool (use `pcbnew` Python with KiCad closed, or the GUI); `route_trace`/`add_via` do not check DRC; run DRC after every batch.
