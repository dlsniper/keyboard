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
   path (Opus) and the switchover re-checked.

**Decisions:** D10 key LED type is decided (SK6812MINI-E chain). D3 is decided
(full-featured USB-C cable, port board in a pod bay; spec §1).

**Exit check:** ERC 0, the review's findings closed (open: task 5), pin map exported (done).

## M2, PCBs

**Goal:** key boards, plates, hub boards and battery module boards ready to order.

1. Footprint placement from `layout/keys.json` by script; outlines shared with the case.
2. Routing: matrix, LEDs with wide 5 V, SPI with series resistors at the source.
3. DRC with schematic parity; a second independent review, including every Pico pin
   against the RP2350 and Pico 2 W datasheets.
4. Plates (1.5 mm FR4) from the same file.
5. Fab outputs, BOM with European sources, a costed quote.

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

**Decisions:** **D8** tenting, negative tilt and palm rest: how close to the K860.

**Exit check:** everything assembles with no rework; the user has typed on it for a day.

Starts after D2; outlines must be frozen before M2 step 1 finishes.

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
| D6 | Board house and assembly | M2 |
| D7 | Place the order | M2 end |
| D8 | Tenting, tilt, palm rest | M3 |
| D9 | Keymap and layers | M5 |
| D10 | Key LED type: decided 2026-11-13, SK6812MINI-E chain | done |
