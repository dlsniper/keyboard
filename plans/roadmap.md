# Roadmap, rev 9

How we get from today to a keyboard on the desk. The spec (`keyboard.md`) says what
the keyboard is; this file says in what order it gets built, what "done" means at
each step, and where the user decides. Written 2026-11-13.

Rules for every milestone:

- A milestone is done only when its **exit check** passes. No starting the next one
  on a promise.
- Choices that are the user's come as options with pros and cons (the **D** items).
  Nothing is ordered without sign-off.
- **One clean session per milestone** (user, 2026-11-13). A session starts from
  `next.md`, the spec and this file only, and ends by updating `next.md` and
  committing. A milestone that grows too large is split into sessions at a task
  boundary. Tokens are limited: read only what the task needs, hand bulk work to
  cheaper models, keep scripts and data as the source so work is regenerated, not
  redone by hand.
- **Hardware stays flexible**: boards are generated from `layout/keys.json` and
  Python scripts, so a changed decision is a re-run, not a redraw.
- Missing upstream support (TinyGo, tinygo-keyboard) is not a blocker to plan
  around: we fix it when we reach it and contribute the fix back.

## At a glance

```
 now ─► M0 layout ─► M1 schematics ─► M2 PCBs ─► order ─┐
              └────► M3 case + hub (starts at layout sign-off) ├─► M5 firmware ─► M6 wireless (later)
                     M4 firmware bring-up on a breadboard ┘
```

Hardware first (user, 2026-11-13): layout, schematics, PCBs and case are done before
any firmware work. M4 needs only Picos and a breadboard, so it can run while the
boards are being made.

## M0, layout

**Goal:** the key positions exist as data and are proven against the real K860
and a real switch. Rev 8 never did this.

**Buy:** 10 × MX switches, 10 × Kailh hotswap sockets, 10 × SK6812MINI-E, a few
keycaps, for the test cell.

1. `layout/keys.json`: every key of the three modules with position, rotation,
   size, matrix row/column and LED order. The one source for PCB placement, plate
   and case.
2. A script that renders it 1:1 to PDF (A4 tiles with alignment marks) and to a
   preview image.
3. The user prints it and lays it over the K860; corrections go back into the file.
4. One printed test cell (FDM, ASA): socket, switch, LED and cap at the tightest
   rotated spot, to prove the 19.05 mm pitch and the LED window.

**Decisions:** **D1** the exact key set per module (top row, nav cluster, where
the dial sits); ANSI decided 2026-11-13. **D2** layout sign-off after the print.

**Exit check:** the user signs off the print and the test cell; key counts and
matrix sizes in the spec are final.

## M1, schematics

**Goal:** key boards, hub boards and battery module drawn from scripts, checked.

1. `tools/sch_keys.py` builds the three key boards from `layout/keys.json`: matrix,
   SPI port expander(s), LEDs (type per D10), LED rail switch on a spare expander
   pin, the 2x6 bay header (D3), spare-pin header. Plus the **port board** (USB-C
   receptacle, 3.3 V regulator, protection), module side and hub side.
2. Hub: core layer (Pico 2 W sockets, buttons, frozen stack connector), connector
   layer (3 module slots, rail switches, host port from `hardware/usb-port`), power
   path and AA module for up to 5 packs. Starting points are rev 8.1's spec and the
   archived generators (`archive/rev8/tools/sch_core.py`, `sch_battery.py`), brought
   out and reworked, not used in place.
3. Hub pin map written into the spec and exported as data for the firmware. Pull-up
   scanning. Rails, cable and fuses sized from datasheets.
4. ERC clean; an independent review of the schematics against the datasheets.
   Done 2026-11-13: all findings fixed except the 5 V rail (task 5).
5. **5 V rail at 3 A or more (user, 2026-11-13)**: TPS552892 in place of the
   TPS630701 on `hub-conn` (application circuit from its datasheet, light-load mode),
   larger ideal-diode FET, +5 V bulk capacitor, host-port limit and auto-restart on
   `usb-port`, stale notes on `usb-port`; then a focused review of the changed power
   path (Opus) and the switchover re-checked. Done 2026-11-13 (spec §3a, §3b; new
   `tools/sim_switchover.py`); review findings closed.

**Decisions:** D10 key LED type is decided (SK6812MINI-E chain). D3 is decided
(full-featured USB-C cable, port board in a pod bay; spec §1).

**Exit check:** ERC 0, the review's findings closed, pin map exported. All three
met 2026-11-13; signed off by the user 2026-11-13.

## M2, PCBs

**Goal:** key boards, plates, hub boards and battery module boards ready to order.

1. Footprint placement from `layout/keys.json` by script; outlines shared with the case.
   `tools/pcb_keys.py`: `left` placed and DRC-checked 2026-11-13 (straight edges, rear strip, bay at the split,
   port board on top; user). `right` (split edge mirrors left's angle; user) and `numpad` placed 2026-11-13, DRC 0 errors.
   Hub boards: FreeCAD section (`mech/hub/`), parts chosen (user), `tools/pcb_hub.py` placed hub-core, hub-conn and battery
   2026-11-13; `hub-conn` arranged for routing 2026-11-14 (4 layers, user; converter per its datasheet layout, port
   clusters, pack columns); cap board `hardware/chain-cap` added. `port-module` placed 2026-11-14 (`tools/pcb_port.py`,
   4 layers, user; bay checked against the three key boards). **Tower grown to 114 mm (user, 2026-11-14)**: `hub-conn`
   108 x 108 mm (outline only), core screws aligned with the boards below (hub-core placed again); `usb-port` placed
   2026-11-14 in the new rear strip on two standoffs (38 x 15 mm, 4 layers, user).
2. Routing: matrix, LEDs with wide 5 V, SPI with series resistors at the source. `tools/route_keys.py`: `left`, `right` and
   `numpad` routed 2026-11-13 (DRC 0 errors, 0 unconnected, parity 0 on each; `tools/route_board.sh` repeats the strip
   autorouter until clean), silkscreen pass by `tools/silk_keys.py`. Hub boards: `tools/route_hub.py` (`tools/route_hub.sh`
   repeats until clean): `hub-core`, `battery` and `chain-cap` routed 2026-11-14 (DRC 0 errors, 0 unconnected, parity 0);
   `hub-conn` (4 layers: scripted power copper, autorouter for the thin nets, a finishing maze router) routed 2026-11-14 too,
   DRC 0 errors, 0 unconnected, parity 0. `port-module` routed the same way 2026-11-14 (DRC 0 errors, 0 unconnected,
   parity 0); tidy pass (`route_hub.py --tidy`) and silkscreen pass on the hub and port boards. `usb-port` routed
   2026-11-14 (KTS1693 ball field and both VBUS paths scripted; DRC 0 errors, 0 unconnected, parity 0); `hub-core` routed
   again for its moved screws. All nine boards clean. KiCad file formats: `tools/kicad_format.sh`, checked by `kicad-check.sh`.
3. DRC with schematic parity; a second independent review, including every Pico pin
   against the RP2350 and Pico 2 W datasheets. Review done 2026-11-14 (Opus, 14 findings; all 40 Pico pins, board-to-board
   mating and the cable wire plan found correct). Closed: converter and port power copper, pack vias (spec §3a).
   **Placement findings closed 2026-11-14** (decoupling at the pins, port TVS at the receptacles, converter VCC and COMP
   parts at their pins with a 1 uF added at the VCC pin (user), key LED capacitor beside the LED (user): `hub-conn`, `usb-port` and the three key boards placed and
   routed again, plates re-run; spec §2, §3a). Left: checks on real parts (next.md).
4. Plates (1.6 mm FR4; user, 2026-11-14) from the same file. Done 2026-11-14: `tools/pcb_plate.py`,
   `hardware/plate-{left,right,numpad}`, DRC 0, checked against the three key boards.
5. Fab outputs, BOM with European sources, a costed quote. **Fab outputs done 2026-11-14: `python3 tools/fab.py`** writes
   Gerbers, drill files, placement file, BOM (parts as drawn, no distributor numbers) and fab notes for all thirteen boards
   into `build/fab/` (copper weights, plate thickness and the questions for the board house are in the notes; a board that
   is not DRC-clean is not exported). Left: sources and the costed quote (sourcing is the user's call, parked).

**Decisions:** **D6** board house and who assembles. **D7** the order itself, placed
only after M4 step 2 has proven SPI over the real cable (spec O2).

**Exit check:** DRC 0 on all boards, review closed, the user approves the quote.

## M3, case and hub tower

**Goal:** three ASA key-module shells and the hub tower, fitting the boards.

1. One FreeCAD script per key module, driven by `layout/keys.json` and the board outlines.
2. Hub tower from rev 8's `build_hub.py` (v7), reworked for the rev 9 boards and
   five battery modules; the seam test print rev 8 never did (pogo force against
   magnet pull).
3. Fit prints of corners and seams before any full print; feet; cable openings.

**Decisions:** **D8** tenting, negative tilt and palm rest: decided 2026-11-14 (spec §2a): screwed-on tilt bars
4 / 7 degrees, separate tent base per alpha half, separate attachable palm rest. Fastening: top screws into inserts.
Hub boards stay 94 mm.

**Progress:** session 1 (2026-11-14): `mech/case/build_case.py` + `tools/case_dump.py`, numpad tray, bay cover,
spacers, sleeves, tilt bars, two fit-print pieces; the key boards' M2 holes are final as routed. Session 2
(2026-11-14): the wireless numpad shell (see M3b session 4). Session 3 (2026-11-14): `left` and `right` shells in
both variants (0 clashes); decided (options UI, FreeCAD): `left` 4 cells and not widened, dial board on the plate
on two new holes in `plate-right`, tent base screwed with four M2 and repeating the tray's underside, palm rest on
a screwed tongue with the pose parts under both, square split-side rail end. Session 4 (2026-11-14): pose parts of `left` / `right` in both variants
(`mech/case/pose_case.py`, 0 clashes): tent bases 5 and 7 degrees (short and long, `left` lifted to level the split
edges), palm rest 100 x 26 mm with a pillow top, tilt bars for under it; the tray's tilt bars got a second hole
pair for the base (spec §2a). Session 5 (2026-11-14): the hub's core section as a shell (`mech/hub/build_core.py`,
0 clashes): decided (options UI, FreeCAD): the radio comes with a deeper lid (8 mm; the core section is the same
with and without it), the carrier rests on a wall shelf and a nut sleeve (no board change), a tooth on the rail's
rear wall under the pod's rear edge in the three wireless shells (spec §3a "Core section shell", §2b). Session 6
(2026-11-14): the rest of the tower (`mech/hub/build_tower.py`, 0 clashes): connector section, battery module, base
and a seam test pair; decided (options UI, FreeCAD): the core's screws end in hex standoffs that hold hub-conn,
pin-seam magnets on the east wall and in the rear-west corner, test pair of two rings with pull holes (spec §3a
"Tower under the core"). Still to do: fit prints (case pieces, hub seam test pair, core section and lid).

**Exit check:** everything assembles with no rework; the user has typed on it for a day.

Starts after D2; outlines must be frozen before M2 step 1 finishes.

## M3b, wireless modules: hardware (user, 2026-11-14)

**Goal:** the cable-free variant of the key modules is designed as hardware, beside the wired one, **before the
order (D7) and before the user tests anything**. Software stack open until the hardware exists.

1. Decisions (options UI): radio and controller of the pod, what the hub listens with (Pico 2 W radio or a radio on
   a core / expansion board), pod power (AA pack and converter in the module, LEDs on battery), where the pod and
   its cells sit in the shell.
2. Pod schematic and board on the frozen 2x6 bay header (spec §1, O10); hub side if it needs hardware.
3. Shell: pod variant of the bay cover / tray; re-check the numpad shell of M3 session 1 against it.

**Progress:** session 1 (2026-11-14): step 1 decided (spec §2b): radio-only pod in the bay with a soldered nRF52840
module and a USB-C service port; power board (3.3 V always on, capped 5 V for LEDs) and 4 AA (`numpad`) or 6 AA
(`left`, `right`) in a rail along the rear edge and the outer side; the same pod on a passive carrier on the hub's
expansion header. No key board changes. Preview `mech/case/pod_preview.py`. Boards now to draw: `pod`, `pod-power`,
`hub-radio` (carrier). Session 2 (2026-11-14): decided (options UI): on / off slide switch on the converters'
enables, printed cell pockets with bought contacts, JST GH lead, 32.768 kHz crystal fitted and a roomier pod board
(user); `left`'s sixth cell: the user proposes a wider left shell (to show in FreeCAD at left's shell). Schematics
by `tools/sch_pod.py` for `pod`, `pod-power`, `hub-radio` (ERC 0, netlist checks in `kicad-check.sh`), pin map
`firmware/pod-pinmap.json`, independent review (Opus). Next: footprints (TPS630701 RNM, two inductors), boards,
the rail in the shell. Open: rail joint, pod outline (how it grows), left's width.
Session 3 (2026-11-14): decided (options UI, shell and rail in FreeCAD): pod straight to the rear over the rail
(30 x 50.7 mm), rear leg of the rail 27 mm deep with a 48 x 22 mm power board, cell count by a solder jumper, all
added parts kept. Footprints drawn (TPS630701 RNM, XGL3530, XFL4020), `tools/pcb_pod.py` + `tools/route_hub.sh`:
`pod`, `pod-power`, `hub-radio` placed and routed (DRC 0 errors, 0 unconnected, parity 0; antenna keep-out free on
all four layers; socket checked against the three key boards, carrier against hub-core), fab outputs, independent
PCB review. No key board, hub-core or hub-conn changed. Next: step 3, the shell (rail, lids, cover over the pod),
with `left` / `right` (M3 session 2).
Session 4 = M3 session 2 (2026-11-14): decided (options UI, FreeCAD): service port stays at the rear with a
ground-free band beside the antenna (`pod` routed again), one-piece wireless tray, Keystone 5201 / 5223 contacts
(springs at both ends of the column), power board notched for the rear cell's spring (`pod-power` placed and routed
again), two sliding cell lids; "buried" via mark fixed on hub-conn, port-module, usb-port. Wireless numpad shell by
`mech/case/pod_case.py` (`CASE_VARIANT=pod`), 0 clashes, fit pieces. Next: fit prints, `left` / `right` with the
rail, left's width, hub core section with the carrier.
Session 5 (2026-11-14): open review items decided (options UI): `pod-power` placed and routed again with a 0603 at
the 5 V converter's VIN pins, its 0603 output capacitor at the VOUT pins, 100 nF at the TPS2553's input, a 1 mm
pack path and an MF-MSMF150/16X fuse (DRC 0 errors, 0 unconnected, parity 0; fab outputs written again); `pod`'s
D+ stub stays. An independent robustness review of all boards (crowding, ESD / noise, power, single faults): next.md.

**Exit check:** ERC / DRC 0, review closed, both variants fit the same key board and tray.

## M4, firmware bring-up

**Goal:** the firmware skeleton runs on a real Pico 2 W and reads keys through an
expander, so M5 starts from something that types. Can run while M1 to M3 proceed.

1. `firmware/` Go module: one program for the hub, on tinygo-keyboard, with our
   SPI-expander matrix source; a `make` target and a CI job.
2. Pico 2 W on a breadboard with an MCP23S17, 2x2 switches, the encoder and 8 LEDs,
   **through 1 m of the candidate cable**: types, turns volume, lights, opens in
   Vial; scan rate and key-to-USB latency measured (O2).
3. n-key rollover over USB checked; added to TinyGo if missing (O9).
4. LED current against brightness, caps per source (O3); idle current on a 4 x AA
   pack measured.

**Exit check:** the user types on the breadboard; O2, O3 and O9 have written
answers in the spec.

**Buy:** 2 x Pico 2 W with headers, MCP23S17 in DIP, breadboards and jumper wires, a
micro-USB cable, through-hole 1N4148 diodes, a DIP 74AHCT125, the candidate cable.

## M5, firmware

**Goal:** the daily-driver firmware, on the assembled keyboard.

1. Final keymap and layers, Vial definition for all three modules.
2. Dial behaviour; lighting effects and the current cap; layer indication.
3. Link robustness: hot-plug of a satellite, missing satellite, error counting.
4. Flashing and recovery guide.

**Decisions:** **D9** keymap and layers.

**Exit check:** a week of daily use with no firmware fault; anything fixed in
tinygo-keyboard or TinyGo is sent upstream.

## M6, wireless (later, not scheduled)

Bluetooth to the host on the Pico 2 W's radio needs pairing support in
`tinygo.org/x/bluetooth` for the CYW43439 (O6); we add it and contribute it. The
batteries and power path are already in the hub by then. If it proves too hard, a
new core layer with a Nordic module is the fallback. After it: cable-free module
pods (spec O10).

## Who does what

Kept cheap without giving up checks. Subagents may delegate further, up to five
levels deep, to the cheapest model that does the task correctly (user, 2026-11-13);
whoever delegates verifies what comes back.

| Work | Model |
| --- | --- |
| Design decisions, pin maps, integration, anything the user signs off | Fable (main session) |
| **PCB design work (placement, routing, outlines), the overall layout and the keyboard body (case and hub CAD)** (user, 2026-11-13: no tokens spent on fixing a cheaper model's mistakes); FreeCAD and KiCad used freely for it | Fable (main session), not delegated |
| Independent reviews: schematics against datasheets (M1), PCBs (M2) | Opus 5.5, given the files, not the conclusions |
| Bulk, well-specified work: data entry, render scripts, schematic script bodies written to the main session's pin maps, keymaps | Sonnet 5.5 |
| Lookups: stock and price at Mouser Europe, datasheet dimensions | Haiku 5.5 |

## Decision list

| | Decision | When |
| --- | --- | --- |
| D1 | Key set per module (ANSI decided) | M0 start |
| D2 | Layout sign-off: signed off 2026-11-13 (print and test cell), M0 exit check passed | done |
| D3 | Module cable and connector: decided 2026-11-13, full-featured USB-C cable, receptacle on a swappable port board in a pod bay | done |
| D4 | Host USB port: decided, USB-C port board on `right` | done |
| D5 | Retired rev 8 folders: decided, moved to `archive/rev8/` | done |
| D6 | Board house and assembly: decided 2026-11-13, JLCPCB makes and assembles | done |
| D7 | Place the order (already settled for it: inner copper 1 oz on `hub-conn` and `port-module` and `usb-port`, user, 2026-11-14; plates 1.6 mm; to ask JLCPCB: KTS1693 lands, receptacle hole rules) | M2 end |
| D8 | Tenting, tilt, palm rest: decided 2026-11-14 (spec §2a) | done |
| D9 | Keymap and layers | M5 |
| D10 | Key LED type: decided 2026-11-13, SK6812MINI-E chain | done |
