# Next

State 2026-09-26, branch `next-steps`. **Spec rev 8** (`plans/keyboard.md`); the rev 8 docs are
committed on this branch. Rev 7 (per-module cores + wired/BLE split; core PCB at 7 open nets) is
commit `0b22b91`. For a fresh session: read this file, then spec §1, §2a, §4, §6, §9, §17 and the
header of `docs/open-questions.md` (it lists everything closed on 2026-09-26).

## Rules
- Decisions: one at a time, AskUserQuestion, recommended option first, pros/cons per option. No silent picks.
- Critique the user's proposals with datasheet numbers before writing them in.
- Parts from Mouser Europe/TME/Farnell; LCSC = reference only. Numbers only from datasheets read; cite; flag unverified.
- Missing file/tool → ask the user (tell them exactly what to download). No commits unless asked.
- Session-only ideas the user floats are not recorded anywhere.
- Schematics are owned by `tools/sch_*.py` (never edit in Eeschema/MCP). PCB: KiCad + Konnect MCP, or `pcbnew` Python with KiCad closed.
- Record each decision in the spec, `docs/01-architecture.md`, `docs/02-parts-shortlist.md`, `docs/open-questions.md` (delete closed rows, note them in its header), `hardware/README.md`, this file.

## Rev 8 in one screen
- **Hub stack, top → bottom:** optional layers (display…, on a 2×10 pass-through expansion header; the JST-SH expansion board stays too) / **core layer** = horizontal base board (power path, LED rail, TCA9548A, buttons, headers) + **vertical MCU board** on the wall (MDBT50Q, antenna faces the room; `J_MCU` 2.54 mm 2×25 right angle) / **connector layer**, swappable, chooses the medium (wired: carrier + 3 socket boards = hub-population comms boards on `J_SLOT` 14) / **battery modules 1…N** (2×AA each, any number) **or a Qi2 board** instead (never charges cells).
- Headers: slot 2×16 (core↔connector); chain 2×6 on every layer from the core down (`1 VBAT 2 GND 3 VBAT 4 GND 5 AUX_5V 6 PACK_EN 7 PACK_SENSE 8 AUX_5V 9 GND 10 VBAT 11 GND 12 VBAT`, reversal-safe).
- **Key modules are dumb:** key board with a TI **MSPM0G3505** (LQFP-48) module controller serving one I2C register map, IS31FL3733, LDO; module-side comms board (USB-C, BAT54C CC→`INT`, `J_COMM` 10). Link = plain USB 2.0 C-to-C cable: VBUS switched LED rail, D± = SDA/SCL (400 kHz, auto 100 kHz fallback per slot), CC = `INT` (220 kΩ pull-ups from `SLOT_EN`).
- Power: LED boost ~5.0 V (750k/100k); battery lighting cap 250 mA for the whole keyboard; per pack LM66200 one channel, `~ON` = `PACK_EN` with ~10 MΩ pull-up (a detached module is off); `PACK_SENSE` feeds the UVLO supervisor; pack path ~296 + 10·n mΩ. A slot is on while its module answers (~200 ms window, ~100 ms re-probe every ~2 s awake, none asleep).

## Next steps, in order
1. **Remaining decisions** (same AskUserQuestion treatment):
   - **X1** top expansion header: pin count, number of chip selects, layer ID (e.g. I2C EEPROM).
   - **F7** module-controller firmware: framework (Zephyr / TI MSPM0 SDK / bare metal), register map v0 (spec §9 draft), BSL-over-link update flow (software entry vs `BSL_invoke`, recovery).
   - **F9** check Zephyr/ZMK at the pinned commit for the TCA9548A binding and a custom `kscan`; MSPM0 Zephyr support.
   - **M11** hub tower mechanics (layer enclosures, latching, MCU-board wall, core-layer height); **M10** stacking-header part.
   - Pin orders: `J_SLOT`, `J_COMM`, slot header, `J_MCU`.
2. **Board refactor** (after the decisions): `core/` → `hub-base/` + `hub-mcu/` (from `sch_core.py`: drop matrix/UART/link/ID/`J_ROW`/`J_COL`/`J_LED`/`J_LINK`/`J_BAT`; add TCA9548A, headers, `PACK_EN`/`PACK_SENSE`, `AUX_5V`); `link/` → `comms/` (variants `hub`/`module`, CC instead of SBU, no KTS1693); new `connector-wired/` (12xx); revise `battery/` (LM66200, BAT54, chain header); retire `seam/`; update `gen_kicad.py`, `check_interconnect.py`, `kicad-check.sh`. Plan in `hardware/README.md`.
3. Key boards (`hardware/common`: LED matrix + module-controller block).
4. Firmware: hub ZMK board + module (kscan over TCA9548A, slot manager, LED frames, dial, CC budget, battery curve); module-controller firmware.
5. Later: Qi2 board (Q1), radio/optical/mixed connector layers (C1).

## Blocked on user
- Stock checks: MSPM0G3505SPTR, TCA9548A, KTS1693/TPS25947 (P7), TPS61099DRVR/MAX17222 (P11), JST GH 10/14 pin (P9), MPD BC2AAPC (P15).
- Files: Maxim 90-0004 (MAX17222), MDBT50Q-U1MV2 datasheet, P18 (Epson FC-135, Alps SKRTLAE010, C&K PCM12SMTR, Coilcraft XEL4030).
- Samples: LEDs (P1), PEC11R lug continuity (E15).

## Commands
- kicad-cli: `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli` (10.0.6). KiCad Python (`pcbnew`): `/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3`.
- Library: `tools/gen_kicad.py`. Schematic: `cd tools && ../.venv/bin/python sch_<board>.py --force`. Check all: `tools/kicad-check.sh`.
- DRC + parity: `kicad-cli pcb drc --schematic-parity --severity-all --format json -o x.json <board>.kicad_pcb` (`--refill-zones --save-board` after via/zone edits).
- Sims: `python3 tools/sim/phase3_calcs.py`, `tools/sim/e14_pack_swap.py`.
- Datasheets → scratchpad, `pdftotext -layout`. curl works: ti.com/lit/ds/symlink, usb.org, raspberrypi.com, bourns, diodes, raytac (browser UA). Blocked: st, microchip, nordic, onsemi, nexperia, littelfuse, eaton, epson, alps, coilcraft, ckswitches, Mouser/Arrow → ask the user.

## Gotchas
- kicad-sch-api 0.5.6: symbols unrotated, always writes `(in_bom yes)` (`schlib.post_process` fixes). Derived (`extends`) symbols → ERC mismatch: use `Device:D` / a `keyboard:` copy. ERC ignores variants: keep variant-exclusive power outputs apart with a jumper.
- A reboot wipes `/tmp` and the scratchpad: keep long work in `build/` (git-ignored).
- Stock footprints often ≠ vendor land pattern; check each.
- `.kicad_dru` values need units (`0.127mm`) or KiCad 10.0.6 silently ignores the file.
- `pcbnew.SaveBoard(out)` rewrites `<out>.kicad_pro`: load from the real name, compare the `.kicad_pro` after. Edit with KiCad closed (`pgrep -lf MacOS/kicad` empty). Copy `GetStart()`/`GetEnd()` before reuse; keep removed items referenced.
- **Konnect 0.11.1 KiCad MCP** (PCB only; KiCad open with the board in the PCB editor, API enabled; `get_installation_info` → `open_project` → `list_toolboxes` → `load_toolset`): no shove/pathfinding, no DRC on `route_trace`/`add_via`; `update_pcb_from_schematic` refuses footprint-less symbols (use F8); `save_project` before trusting file-based checks; `add_zone` = copper only; `export_specctra_dsn` fails (use headless Freerouting via `pcbnew.ExportSpecctraDSN`; full recipe in `0b22b91`'s next.md); refill zones with kicad-cli after IPC edits. **KiCad segfaults if a Konnect write arrives while the schematic side is loaded**: F8, quit, reopen the PCB editor only, then Konnect.
