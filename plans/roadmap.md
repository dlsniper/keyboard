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
              └────► M3 case (starts at layout sign-off) ├─► M5 firmware ─► M6 wireless (later)
                     M4 firmware bring-up on a bare Pico ┘
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

**Goal:** three key-board schematics generated from one script, checked.

1. `tools/sch_keys.py` builds all three from `layout/keys.json` (matrix, LED chain,
   Pico sockets, link connectors, expansion header, level shifter, fuses). Rework
   `tools/sch_usb_port.py` into the rev 9 port board. Add the three key boards to
   `tools/gen_kicad.py` and `check_interconnect.py` (pruned to rev 9 on 2026-11-13).
2. Pin assignment per module, written into the spec. Matrix wired for pull-up
   scanning (tinygo-keyboard supports both directions; pull-ups avoid the RP2350
   pull-down erratum E9). LED rail, links and fuses sized from datasheets for the
   3 A case; brightness caps are firmware values set later (M4).
3. Pico 2 W antenna keep-out and mechanical outline from the Raspberry Pi datasheet.
4. ERC clean; an independent review of the schematics against the datasheets.

**Decisions:** **D3** link connector and cable (O1). D4 (host USB) and D5 (old folders) were
decided 2026-11-13: a USB-C port board on `right`; folders moved to `archive/rev8/`.

**Exit check:** ERC 0, the review's findings closed, the pin map exported as data
for the firmware to use later.

## M2, PCBs

**Goal:** three boards and three plates ready to order.

1. Footprint placement from `layout/keys.json` by script; outlines shared with the case.
2. Routing: matrix, LED chain with wide 5 V, link, expansion.
3. DRC with schematic parity; a second independent review. No firmware has run
   on hardware at this point, so the review also checks every Pico pin against the
   RP2350 and Pico 2 W datasheets (UART-capable pins, radio-reserved pins).
4. Plates (1.5 mm FR4) from the same file.
5. Fab outputs, BOM with European sources, a costed quote.

**Decisions:** **D6** board house and who assembles (assembled SMD or hand
soldering). **D7** the order itself.

**Exit check:** DRC 0 on all boards, review closed, the user approves the quote.

## M3, case

**Goal:** three ASA shells that fit the boards and feel right.

1. One FreeCAD script per module, driven by `layout/keys.json` and the board outlines.
2. Fit prints of the corners and the seams before any full print.
3. Seams (magnets), feet, the opening for the host cable and the links.

**Decisions:** **D8** tenting, negative tilt and palm rest: how close to the K860.

**Exit check:** boards, plates and shells assemble with no rework; the user has
typed on it for a day.

Starts after D2; its outlines must be frozen before M2 step 1 finishes.

## M4, firmware bring-up

**Goal:** the firmware skeleton runs on real Pico 2 W boards, so M5 starts from
something that types. Comes after the hardware milestones by the user's choice;
the test image already compiles for `pico2-w`.

1. `firmware/` Go module: one package per module (`right`, `left`, `numpad`) on
   tinygo-keyboard, shared keymap and link code, a `make` target and a CI job.
   The pin map comes from the M1 data.
2. One Pico 2 W on a breadboard with 2×2 switches, the encoder and 8 LEDs: types,
   turns volume, lights, opens in Vial.
3. Three Pico 2 W wired primary + two satellites: keys from all three arrive;
   a primary-to-satellite channel for lighting (O2).
4. Measure LED current against brightness and set the caps per host level (O3).

**Exit check:** the user types on the breadboard through all three Picos; O2 and
O3 have written answers in the spec.

**Buy:** 4 × Pico 2 W with headers (3 go into the keyboard), breadboards and jumper
wires, a micro-USB cable, through-hole 1N4148 diodes, a DIP 74AHCT125. Switches,
sockets, the encoder and LEDs come from the M0 test-cell and M2 orders.

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

Bluetooth on the Pico 2 W's radio needs pairing support in `tinygo.org/x/bluetooth`
for the CYW43439 (O6); we add it and contribute it. Wireless also needs a battery
and charging design, which rev 9 does not have. Planned once M5 is done.

## Who does what

Kept cheap without giving up checks:

| Work | Model |
| --- | --- |
| Design decisions, pin maps, routing strategy, integration, anything the user signs off | Fable (main session) |
| Independent reviews: schematics against datasheets (M1), PCBs (M2) | Opus 5.5, given the files, not the conclusions |
| Bulk, well-specified work: layout data entry, render scripts, schematic and CAD script bodies, keymaps | Sonnet 5.5 |
| Lookups: stock and price at Mouser Europe, datasheet dimensions | Haiku 5.5 |

## Decision list

| | Decision | When |
| --- | --- | --- |
| D1 | Key set per module (ANSI decided) | M0 start |
| D2 | Layout sign-off | M0 end |
| D3 | Link connector and cable | M1 |
| D4 | Host USB port: decided, USB-C port board on `right` | done |
| D5 | Retired rev 8 folders: decided, moved to `archive/rev8/` | done |
| D6 | Board house and assembly | M2 |
| D7 | Place the order | M2 end |
| D8 | Tenting, tilt, palm rest | M3 |
| D9 | Keymap and layers | M5 |
