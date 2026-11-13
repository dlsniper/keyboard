# Test cell (M0 task 4)

Two MX positions at their real relative position and rotation: `'` (R_QUOTE, 1u) and
right Shift (R_RSHIFT, 2.75u), the tightest rotated spot of the layout (0.64 mm
between caps). It proves the 19.05 mm pitch, cap clearance, the hotswap socket fit
and the SK6812MINI-E window (D10).

Generated, never edited by hand:

```
/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd mech/testcell/build_testcell.py
```

The script reads both keys from `layout/keys.json`, so a layout change is a re-run.

## Print files

| File | Part | Print |
| --- | --- | --- |
| `testcell-plate.stl` / `.step` | plate, 1.5 mm, 14.1 mm switch cutouts, four Ø6.5 bosses with Ø3.2 x 4.2 mm insert holes | as exported: top face on the bed, bosses up |
| `testcell-pcb.stl` / `.step` | 1.6 mm stand-in for the PCB: switch holes, socket holes, 3.5 x 3.1 mm LED window 4.7 mm south of each switch, four Ø2.2 screw holes | flat |
| `testcell.FCStd` | both parts assembled | view only |

Size 76.8 x 52.3 mm, 6.6 mm tall assembled. ASA, 0.4 mm nozzle, 0.1 mm layers for
the plate (1.5 mm = 15 layers) and 0.2 mm for the stand-in (1.6 mm = 8 layers), no
supports. Hole clearances for FDM are parameters at the top of the script (+0.1 mm
on the cutout and the window, +0.2 mm on round holes); if the switch does not clip
or rattles, change `CUTOUT_CLR` and re-run.

No stabiliser features: right Shift is checked on its switch alone.

## Assembly and what to check

1. Set four M2 inserts into the bosses (from the boss end).
2. Clip both switches into the plate, pins towards the rear (the `'` is the rear-left key seen from the top).
3. Put the stand-in over the switch pins, four M2 x 5 screws.
4. Push a hotswap socket onto each switch from below; drop an LED into each window
   from below, lens up, legs resting on the underside.
5. Fit the caps and check: the two caps do not touch through the full travel; the
   sockets seat flat and do not reach the neighbour's LED legs; the LED lens sits
   under the switch's LED slot; the distance between the two stems matches the print
   of `layout/keys-a4.pdf`.

## Parts

Mouser Europe numbers could **not be verified** on 2026-11-13: mouser.de did not
answer automated lookups in two attempts. Only numbers actually seen are listed;
check each on mouser.de before ordering.

| Qty (cell / M0 buy) | Part | Maker part | Source | Status |
| --- | --- | --- | --- | --- |
| 2 / 10 | MX switch, 5-pin (3-pin also fits) | Cherry MX1A-G1NW (brown, 5-pin) or MX1A-G1NN (3-pin) | Mouser `540-MX1A-G1NN` | number seen in a Mouser search snippet only; EU price and stock not verified; 5-pin number not seen |
| 2 / 10 | Hotswap socket | Kailh CPG151101S11 | not at Mouser; splitkb.com (NL): https://splitkb.com/products/kailh-hotswap-sockets | about EUR 5.74 per pack, from a search snippet |
| 2 / 10 | LED, reverse mount | SK6812MINI-E (OPSCO); Adafruit 4960 = pack of 10 | not found at Mouser; Adafruit 4960 at DigiKey: https://www.digikey.hu/en/products/detail/adafruit-industries-llc/4960/14302512 | USD 2.95 per 10 at Adafruit; DigiKey showed a 24-week lead time; European source still open |
| 4 | M2 heat-set insert, 4 mm long, Ø3.2 hole | Ruthex RX-M2x4 | not at Mouser; https://www.3djake.com/ruthex/threaded-insert-m2-70-pieces | pack of 70; price seen only in CHF |
| 4 | M2 x 5 pan-head screw (5.5 mm at most: the insert hole is blind) | any ISO 7045 | not looked up at this length | |
| 2 | Keycaps: one 1u, one 2.75u (row 3 and row 4 profile if sculpted) | any MX | from the user's stock | |
| 0 / 1 | Level shifter for lighting the LEDs later (M4) | TI SN74AHCT125N, DIP-14 | DigiKey: https://www.digikey.de/en/products/detail/texas-instruments/SN74AHCT125N/375798 | about EUR 0.7 to 0.8 from search snippets; Mouser not verified |

The LEDs are not powered in this cell; it is a mechanical fit check.
