# Next

State 2026-09-29, branch `next-steps`. **Spec rev 8** (`plans/keyboard.md`). Committed on this branch: the rev 8
docs (`050284d`), vendor datasheets (`1590e5b`), and the 2026-09-28/29 work (`b76c3f6`: X1; F7's hardware side;
`J_COMM`, `J_SLOT`, slot-header and hub MCU pad orders; key-board LDO; TCA9548A package; ESQ family and lead style;
M11's first decisions; the MSPM0G3505 and TPS7A0233PDBV symbols, two TI land patterns; `mech/hub/build_hub.py` v0).
Commit only when the user asks. Rev 7 (per-module cores + wired/BLE split) is
commit `0b22b91`.

**The user wants the hardware solved before any firmware work.** In progress: **M11, the hub tower**, modelled in
FreeCAD through the `freecad` MCP server (see Tools). A v0 model exists and **waits for the user's review** (step 1a).

For a fresh session: read this file, then spec §1, §2a, §4 (battery chain), §5 (pad tables), §6 (every header
pinout, the stacking-header block), §9 (bootloader recovery), §11 (mechanical, the hub tower bullet), §13
(antenna), §14 (`mech/hub/` workflow), §17, the header and the M11/P20 rows of `docs/open-questions.md`, and
`mech/hub/build_hub.py`.

## Rules
- Decisions: one at a time, AskUserQuestion, **recommended option first**, pros/cons per option with datasheet numbers. No silent picks (e.g. a package or a part variant is a decision).
- Critique the user's proposals with datasheet numbers before writing them in.
- Parts from Mouser Europe/TME/Farnell; LCSC = reference only. Numbers only from datasheets read; cite; flag unverified.
- Missing file/tool → ask the user (tell them exactly what to download). No commits unless asked.
- Session-only ideas the user floats are not recorded anywhere.
- Schematics are owned by `tools/sch_*.py` (never edit in Eeschema/MCP). PCB: KiCad + Konnect MCP, or `pcbnew` Python with KiCad closed.
- Record each decision in the spec, `docs/01-architecture.md`, `docs/02-parts-shortlist.md`, `docs/open-questions.md` (delete closed rows, note them in its header), `hardware/README.md`, this file.
- Installing third-party code or changing Claude Code's MCP config: the auto-mode classifier blocks the agent (`claude mcp add…` was denied). Give the user the exact `! command` to run instead.

## Rev 8 in one screen
- **Hub stack, top → bottom:** optional layers (display…, on the 2×10 expansion header; the JST-SH expansion board stays too) / **core layer** = one base board, ~84 × 84 mm, one ESQ joint tall: **MDBT50Q-U1MV2** (u.FL; single source), power path, LED rail, TCA9548A, buttons, stacking headers; u.FL → **adhesive flex antenna on the inside of a core-section wall**, **blanked RP-SMA knock-out** in that wall for an external antenna on a pigtail (all 2026-09-29) / **connector layer**, swappable, chooses the medium (wired: carrier + 3 socket boards = hub-population comms boards on `J_SLOT`) / **battery modules 1…N** (2×AA each) **or a Qi2 board** instead (never charges cells).
- **Key modules are dumb:** key board with a TI **MSPM0G3505SPTR** (LQFP-48 PT) module controller serving one I2C register map, IS31FL3733, **TPS7A0233PDBVR** LDO; module-side comms board (USB-C, BAT54C CC→`INT`, `J_COMM`). Link = plain USB 2.0 C-to-C cable: VBUS = switched LED rail, D± = SDA/SCL (400 kHz, auto 100 kHz fallback per slot), CC = `INT` (220 kΩ pull-ups from `SLOT_EN`). A USB 2.0 cable has no spare conductor, so `J_COMM`/`J_SLOT` spares never cross it.
- Power: LED boost ~5.0 V (750k/100k); battery lighting cap 250 mA for the whole keyboard; per pack LM66200 one channel, `~ON` = `PACK_EN` with ~10 MΩ pull-up (a detached module is off); `PACK_SENSE` feeds the UVLO supervisor; pack path ~296 + 10·n mΩ. A slot is on while its module answers (~200 ms window, ~100 ms re-probe every ~2 s awake, none asleep).

### Header pinouts (all in spec §6)
- **Chain 2×6** (every layer from the core down): `1 VBAT 2 GND 3 VBAT 4 GND 5 AUX_5V 6 PACK_EN 7 PACK_SENSE 8 AUX_5V 9 GND 10 VBAT 11 GND 12 VBAT` (reversal-safe).
- **Slot header 2×16** (core ↔ connector): reversal-safe, pin p meets 33−p; slots 0 and 2 mirror images (a rotated layer swaps them, still works: keys map by module ID), slot 1 folded (`S1_SLOT_EN` faces global `SPARE`, so it stays off). Table in §6.
- **Top expansion 2×10** (X1): `1 5V 2 GND 3 3V3 4 SDA 5 INT 6 CS0 7 CS1 8 DC 9 SCK 10 GND 11 GND 12 MOSI 13 RST 14 CS2 15 CS3 16 MISO 17 SCL 18 3V3 19 GND 20 5V` (reversal-safe; 5V = `VBUS_LOCAL`, host USB only; 3V3 = gated expansion LDO, 150 mA incl. the SH socket). Each layer picks CS0–CS3 by solder jumper and carries a 24xx02-class ID EEPROM at 0x50 + CS number (0x50–0x53 reserved on the expansion bus; EEPROM part not chosen).
- **`J_SLOT` 14** (GH): `1 LED_RAIL 2 VSYS 3 GND 4 SDA 5 SPARE1 6 GND 7 SLOT_EN 8 INT_B 9 INT_A 10 SPARE2 11 SCL 12 GND 13 VSYS 14 LED_RAIL`.
- **`J_COMM` 10** (GH): `1 VIN 2 GND 3 SDA 4 SPARE1 5 GND 6 INT 7 SPARE2 8 SCL 9 GND 10 VIN`.
- **MDBT50Q pads** (§5 table): 21 LF signals fill the 21 LF-only pads; 5 full-function pads free. NFC pads P0.09/P0.10 carry `EXP_RST`/`EXP_LDO_EN` (`CONFIG_NFCT_PINS_AS_GPIOS=y`); their mutual leakage is unverified (needs the nRF52840 PS). Raytac ver L: **1MV2 = chip antenna, P1MV2 = PCB antenna, U1MV2 = u.FL**, one land pattern (`build/ds/mdbt50q.pdf`).
- Hub keeps every `SPARE` pad hi-Z until a connector layer defines it.

### Key board specifics
- MSPM0G3505 **48-pin PT numbering** (SLASEX6C Table 6-2, second number column; the first is the 64-pin package): link SDA/SCL = **PA0/PA1, pins 1/2** (default BSL I2C, 5 V-tolerant open-drain, BSL address 0x48); `BSL_invoke` = **PA18, pin 33**; SWD PA19/PA20 = 34/35; NRST 4, VDD 6, VSS 7, VCORE 48 (capacitor only).
- Bootloader recovery (F7 hardware side): software entry (`RESETLEVEL` = BOOTLOADERENTRY), the hub writes the vector table last (an interrupted update boots into the BSL by the blank-device rule), the hub power-cycles the slot for the POR the BSL needs after its 10 s timeout; PA18 pull-down + rescue pad beside a 3V3 pad. No NONMAIN changes.

### Stacking headers (M10 family and lead style decided)
- **Samtec ESQ elevated socket, square stack-through tails, socket on each board's top face, tails down** (PC/104 style): chain ESQ-106, slot ESQ-116, expansion ESQ-110, **`-24-G-D`** (standard force; decided 2026-09-29), **gap 17.5 mm on every joint, 19.1 mm board pitch, tails 8.05 mm below each board, 2.5 mm over the AA holder**. 5.7 A/pin, insertion 3.68–6.35 mm; A + B = 23.24 mm for every lead style → **one joint spans ~15.3–18.0 mm board to board** (1.6 mm boards). Wave/hand soldering only.
- **The bottom battery module's tails carry live VBAT**: its case must shroud them (tips recessed inside the bottom outline). In the v0 model they sit only 1.45 mm inside an open skirt (question 1a-ii).

## Next steps, in order
1. **M11, the hub tower** (spec §11; open-questions M11).
   **Decided 2026-09-29** (all recorded in the docs):
   - Workflow: `mech/hub/build_hub.py` owns the model (run through the MCP's `execute_python`, recipe in Gotchas); the `.FCStd` and PNGs are build outputs in `build/mech/hub/`; exports a STEP per layer + assembly and an STL per printed part; outlines, holes and header positions flow FreeCAD → KiCad (DXF or a pcbnew script), the boards' STEP comes back for clearance checks.
   - Footprint 90 × 90 mm outside, 2 mm resin walls, boards 84 × 84 mm.
   - Hub MCU = **MDBT50Q-U1MV2** on the base board (single source); the vertical MCU board, `J_MCU` and a riser are dropped; the core is one joint tall. Antenna: adhesive flex antenna inside the rear wall + blanked RP-SMA knock-out beside it.
   - ESQ `-24-G-D`, standard force, **17.5 mm gap on every joint** (19.1 mm pitch; tails 8.05 mm below each board; 2.5 mm over the AA holder; two-pack tower ~88 mm).
   - Walls (front = facing the keyboard): **front** 3 slot sockets (connector layer) + slide switch, reset, boot (core, above them); **rear, right to left** host USB-C, SH socket, flex antenna + knock-out (antenna ≤~40 mm long); **sides** nothing. The user asked for every cable at the back and accepted the antenna ~20–40 mm from two cables and the USB shell (RSSI in §16).
   - Joints: core ↔ connector layer **M2 screws** into heat-set inserts; **battery modules, optional layers and the lid: magnets + a nesting lip with an asymmetric key** (no 90°/180° misfit), magnets away from the antenna corner. Cells: lift everything above the module off.

   **Model state (`build_hub.py` v0)**: boxes only: boards, ESQ bodies + tails, AA holders, the three socket boards + receptacles, host USB and expansion boards, the antenna strip, section shells with wall openings, the blanked knock-out, a lid. Axes: X right (seen from the keyboard), Y to the rear, Z up. Section boundary 9.5 mm under each board's bottom; board bottoms at z 9.5 / 28.6 / 47.7 / 66.8 (batt2, batt1, connector, core), top 87.9 mm. Every `[approx]` value in the script is a placeholder (receptacle, SH body, cut-out sizes, control positions, antenna size).

   **Next, in order:**
   a. **Get the user's review of v0** (they look at it in FreeCAD; views `0`–`6`, Space hides shells), then ask, one at a time with AskUserQuestion: (i) the header positions proposed: chain (x 25, y 20), slot (x −5, y 5), expansion (x 0, y −20), AA holder centred at y −22; (ii) a foot/base under the bottom module to cover its live tails (alternatives: a deeper skirt on every battery module, or a cap on the bottom module only); (iii) the core's chain and slot ESQ sockets face up with nothing plugged in: keep ESQ (one part family) or a tails-only header there (a part decision); (iv) where the core ↔ connector M2 screws go (reachable from outside, or from inside before the next layer goes on).
   b. Model the joints: nesting lip + asymmetric key, magnet pockets (placeholder size until the magnet part is chosen), screw bosses + heat-set insert holes, board standoffs (M2, one driver), J_SLOT/J_USB/J_EXP cable paths.
   c. The antenna's clearance (base-board copper pull-back near the rear wall, distance to the layer above and to the USB shell): needs the P20 antenna part and its datasheet.
   d. Export: STEP per layer + assembly, STL per printed part (into `build/mech/hub/`; commit exports only when the user asks), and the board outlines + header/hole positions to KiCad for step 3.
   Inputs:
   - AA holder MPD BC2AAPC rev P: body 58.0 × 30.5 mm, 15.0 mm tall, pins 13.00 mm apart (footprint `BatteryHolder_MPD_BC2AAPC_2xAA_RevP`); whether the cells stand above the 15.0 mm body is **not verified** (MPD's datasheet URL 404s; ask the user for the drawing).
   - ESQ bodies (Samtec F-226): length 2.54·N + 0.51 mm, 4.95 mm deep (`-D`): chain 15.75, expansion 25.91, slot 41.15 mm; insertion 4.14 mm at S = 17.5 (holds for S 15.29–17.96).
   - MDBT50Q: 15.5 × 10.5 mm, one land pattern for every variant; the stock `RF_Module:Raytac_MDBT50Q` carries an antenna keepout zone the U1MV2 doesn't need.
   - USB4085 courtyard 10.6 × 10.2 mm; plug overmolds ~12 mm wide. A future radio connector layer puts its antenna on the front wall.
2. **M10 rest**: a second source (none found; ESQ looks Samtec-only), ESQ contact resistance and `-G` cycles (Samtec test report; E20 assumes ~20 mΩ, a plain Würth 61301221121 2×6 meets 20 mΩ max).
3. **Board refactor**: `core/` → `hub-base/`, one board with the MDBT50Q-U1MV2 (from `sch_core.py`: drop matrix/UART/link/ID/`J_ROW`/`J_COL`/`J_LED`/`J_LINK`/`J_BAT`; add TCA9548APWR on `keyboard:TI_TSSOP-24_4.4x7.8mm_P0.65mm_PW0024A`, the ESQ headers, the u.FL module (stock footprint has the antenna keepout zone: a keyboard: copy without it is a capture decision), `PACK_EN`/`PACK_SENSE`, `AUX_5V`, CS0–CS3 pull-ups, the §5 pad table); `link/` → `comms/` (variants `hub`/`module`, CC instead of SBU, no KTS1693, §6 orders); new `connector-wired/` (12xx); revise `battery/` (LM66200, BAT54, chain header); retire `seam/`; update `gen_kicad.py` `PROJECTS`, `check_interconnect.py` `MATES`/`PENDING`, `kicad-check.sh`. Plan in `hardware/README.md`. Outlines from M11.
4. Key boards (`hardware/common`: LED matrix + module-controller block with `MSPM0G3505SPT`, `TPS7A0233PDBV`, PA18 rescue pad).
5. Firmware (**on hold** until the hardware is done): F7 framework + register map; F9 (started 2026-09-28: ZMK `main` and `641514a` both pin Zephyr `v4.1.0+zmk-fixes`, which has `dts/bindings/i2c/ti,tca9548a.yaml`; clones in `build/zmk`, `build/zephyr-zmk`; custom `kscan` and MSPM0 Zephyr support not yet checked; ZMK's west.yml blocklists `hal_ti`).
6. Later: Qi2 board (Q1), radio/optical/mixed connector layers (C1).

## Blocked on user
- The v0 hub model review (step 1a).
- Raytac's antenna list for the MDBT50Q-U approval (P20): ask Raytac or get the full SGS report E2/2018/50088-02. A flex antenna and a u.FL-to-RP-SMA pigtail to choose (datasheets), and a magnet part (holding force; the ESQ withdrawal force is not on Samtec's catalog page, maybe in its test report).
- MPD BC2AAPC rev P drawing (cell height above the holder body).
- Stock checks: MDBT50Q-U1MV2, MSPM0G3505SPTR, TCA9548APWR, TPS7A0233PDBVR, Samtec ESQ-106/110/116-24-G-D, KTS1693/TPS25947 (P7), TPS61099DRVR/MAX17222 (P11), JST GH 10/14 pin (P9), MPD BC2AAPC (P15).
- Files: nRF52840 Product Specification v1.9 (NFC-pad leakage for P0.09/P0.10; nordic blocks curl), Samtec ESQ test report if suddendocs has none, Maxim 90-0004 (MAX17222), P18 (Epson FC-135, Alps SKRTLAE010, C&K PCM12SMTR, Coilcraft XEL4030).
- Samples: LEDs (P1), PEC11R lug continuity (E15).

## Tools
- **FreeCAD MCP** (verified 2026-09-29: `get_connection_status` → connected, xmlrpc, FreeCAD 1.1.4, GUI): server = Docker image `spkane/freecad-robust-mcp` (registered in the user's *local* Claude config as `freecad`, `FREECAD_MODE=xmlrpc`, `FREECAD_SOCKET_HOST=host.docker.internal`). Needs, in order: **OrbStack running** (Docker engine; `open -a OrbStack`), **FreeCAD open with the bridge started** (Robust MCP Bridge workbench → Start MCP Bridge, or its auto-start preference; listens on localhost 9875 XML-RPC / 9876 socket; check with `nc -z -G 2 localhost 9875`), then `/mcp` → reconnect `freecad`. The FreeCAD add-on is **not** in the Addon Manager catalogue; it is a git clone of `github.com/spkane/freecad-addon-robust-mcp-server` in `~/Library/Application Support/FreeCAD/v1-1/Mod/RobustMCPBridge`. Tools are deferred: load them with ToolSearch (`select:mcp__freecad__…`). `execute_python` runs arbitrary FreeCAD Python.
- kicad-cli: `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli` (10.0.6). KiCad Python (`pcbnew`): `/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3`.
- Library: `python3 tools/gen_kicad.py`. Schematic: `cd tools && ../.venv/bin/python sch_<board>.py --force`. Check all: `tools/kicad-check.sh` (log to `build/kicad-check.log`). Render a library item: `kicad-cli sym export svg --symbol NAME -o build/libcheck hardware/lib/keyboard.kicad_sym`, `kicad-cli fp export svg --footprint NAME --layers F.Cu,F.SilkS,F.Fab,F.CrtYd -o build/libcheck hardware/lib/keyboard.pretty`, then `rsvg-convert -w 900 -b white x.svg -o x.png` and Read the PNG.
- DRC + parity: `kicad-cli pcb drc --schematic-parity --severity-all --format json -o x.json <board>.kicad_pcb` (`--refill-zones --save-board` after via/zone edits).
- Sims: `python3 tools/sim/phase3_calcs.py`, `tools/sim/e14_pack_swap.py`.
- Datasheets → `build/ds/` (git-ignored, survives reboots), `pdftotext -layout`. Already there: TI `mspm0g3505` (SLASEX6C rev C), `slau887` (MSPM0 bootloader UG, rev A), `tca9548a` (SCPS207H), `tps7a02` (SBVS277C), `tlv757p`; Raytac `mdbt50q` (ver L; images of pages in `mdbt50q_pages/`, the keepout, antenna and certificate pages are images); Samtec `esq_th`; Würth `61301221121`. curl works (browser UA): ti.com/lit/ds/symlink and ti.com/lit/ug, usb.org, raspberrypi.com, bourns, diodes, raytac, suddendocs.samtec.com, we-online.com, raw.githubusercontent.com, api.github.com. Blocked: st, microchip, nordic, onsemi, nexperia, littelfuse, eaton, epson, alps, coilcraft, ckswitches, Mouser/Arrow → ask the user.

## Gotchas
- `tools/kicad-check.sh` **always exits 1**: every board without an outline has one "no board outline" DRC violation. The rev 7 core PCB carries 303 DRC items (8 known `hole_clearance`, 15 unconnected, silk); it is being replaced. Judge by ERC (14 sheets, 0 violations on 2026-09-29) and `interconnect: … 0 errors`.
- `gen_kicad.py` rewrites every library footprint without UUIDs and `kicad-check.sh` normalises them with fresh UUIDs, so untouched footprints show UUID-only diffs. Restore them: `for f in $(git diff --name-only hardware/lib/keyboard.pretty); do [ -z "$(git diff $f | grep '^[-+]' | grep -v '^[-+][-+]' | grep -v uuid)" ] && git checkout -- $f; done`.
- `symbol()` in `gen_kicad.py` spaces top/bottom pin names 5.08 mm apart (fixed 2026-09-29: an even count used to land on one point). Keep symbol widths a multiple of 5.08 mm so pin ends stay on the 2.54 mm grid.
- TI "(8.2)"-style dimensions on land-pattern examples are pad centre-to-centre.
- kicad-sch-api 0.5.6: symbols unrotated, always writes `(in_bom yes)` (`schlib.post_process` fixes). Derived (`extends`) symbols → ERC mismatch: use `Device:D` / a `keyboard:` copy (the stock `TCA9548APWR` is not derived; stock KiCad 10.0.6 has no MSPM0G350x or TPS7A02). ERC ignores variants: keep variant-exclusive power outputs apart with a jumper.
- **FreeCAD MCP recipe**: run the model with `execute_python`: `p='<repo>/mech/hub/build_hub.py'; g={'__file__': p}; exec(open(p).read(), g); _result_=g['_result_']` (pass `__file__` so the script finds the repo). **`get_screenshot` fails** (`'dict' object has no attribute '__name__'`, a bug in the tool's own code, seen 2026-09-29). Take images with `FreeCADGui.getDocument('hub').ActiveView.saveImage('<repo>/build/mech/hub/iso.png', 1000, 900, 'White')` after `viewIsometric()` + `SendMsgToActiveView("ViewFit")`, then Read the PNG. Outputs go to `build/mech/hub/` (`hub.FCStd`, PNGs).
- A reboot wipes `/tmp` and the scratchpad: keep long work in `build/` (git-ignored).
- Stock footprints often ≠ vendor land pattern; check each.
- `.kicad_dru` values need units (`0.127mm`) or KiCad 10.0.6 silently ignores the file.
- `pcbnew.SaveBoard(out)` rewrites `<out>.kicad_pro`: load from the real name, compare the `.kicad_pro` after. Edit with KiCad closed (`pgrep -lf MacOS/kicad` empty). Copy `GetStart()`/`GetEnd()` before reuse; keep removed items referenced.
- **FreeCAD MCP** (enclosure/mechanical work; setup in Tools): `/mcp` "Failed to reconnect" / CONNECTION_CLOSED means OrbStack is stopped (the `docker run` never starts) or the bridge is not listening on 9875; check both before anything else. The Addon Manager's custom-repository route did not persist in FreeCAD 1.1.4 (`user.cfg` had no entry), so the add-on is a git clone; turn on its auto-start in Edit → Preferences → Robust MCP Bridge to skip the manual Start. The bridge (git clone) and the server (Docker image) update separately: after a `git pull` of the add-on, `docker pull spkane/freecad-robust-mcp` too. Registering or changing the MCP server is the user's `! claude mcp …` command (the agent is blocked).
- **Konnect 0.11.1 KiCad MCP** (PCB only; KiCad open with the board in the PCB editor, API enabled; `get_installation_info` → `open_project` → `list_toolboxes` → `load_toolset`): no shove/pathfinding, no DRC on `route_trace`/`add_via`; `update_pcb_from_schematic` refuses footprint-less symbols (use F8); `save_project` before trusting file-based checks; `add_zone` = copper only; `export_specctra_dsn` fails (use headless Freerouting via `pcbnew.ExportSpecctraDSN`; full recipe in `0b22b91`'s next.md); refill zones with kicad-cli after IPC edits. **KiCad segfaults if a Konnect write arrives while the schematic side is loaded**: F8, quit, reopen the PCB editor only, then Konnect.
