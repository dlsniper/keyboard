# Prompt for M3 session 7 (fit prints)

Run this in a clean session once the fit pieces are printed (3D prints, FDM, ASA). Fill in the results block
first; delete the lines of pieces you did not print.

```
Keyboard project, rev 9.1, branch rev9-go. Read next.md (last session block), plans/keyboard.md (§2a and §2b "Open",
§3a "Core section shell" and "Tower under the core") and plans/roadmap.md, nothing else to start.
M3 session 7: fit prints. My results are below (numpad pieces, a tent base, the left palm rest, the hub's seam
test pair with the weight it carried, the core section or a lid): change slots, grooves, snap, spring heights, palm rest
height, the joint, the lid's hold, the seam magnets' pattern and skin, and the standoff seam from them. Change only
what a result covers. If the test pair shows a module is hard to pull off or to grip, show grip options in FreeCAD
and through the options UI with pros and cons, critique my choices first.
No board changes without asking; say which boards are placed and routed again before changing any.
Printers are FDM, ASA (long tent bases and right's wireless tray fit the H2S only). Budget: tokens are tight. PCB and CAD
work stays with you; delegate only lookups.
No leftover background processes. End by updating next.md, committing, and giving me the prompt for the next session.

Results:

Numpad pieces (build/case/numpad-pod/)
- numpad-fit-rail-front + numpad-fit-lid-side
  - Keystone 5201 / 5223 plates in the 0.6 mm slots (loose / right / too tight):
  - spring in its window, force to push a cell in:
  - lid in the groove (0.1 mm play):
  - snap ridge holds / releases:
- numpad-fit-rail-rear + numpad-fit-lid-rear
  - 5223 slot:
  - cell through the west entry:
  - rear cell tips out under the hood's arch (yes / no):
- numpad-fit-power
  - board on the bosses and posts:
  - switch actuator in its slot:
  - both notches, rear spring wall:
- numpad-cover
  - fit over the pod:
  - USB-C opening, lead hood:

Pose parts of left
- tent5 base: the four M2 screws line up, inserts sit, rocks (yes / no):
- palm rest: 26 mm high (too high / right / too low), 100 mm deep, tongue joint flexes or creaks:

Hub
- seam test pair (two rings)
  - weight carried before the seam opened:
  - spring pins push it open at an edge (which):
  - hard to pull off or to grip:
  - 0.6 mm skin over the magnets intact, magnets stay seated:
- core section / lid (if printed)
  - lid holds on the rear-wall magnets:
  - M2 nut in the shelf pocket and in the sleeve:
  - M2 x 14 in the standoffs (thread depth, 6 mm stud):
  - plug overmould through the 13 x 7 mm openings:

Not printed:
```

# Prompt for the pod-power session (decided 2026-11-14, any time before the order)

```
Keyboard project, rev 9.1, branch rev9-go. Read next.md (last session block and the "User decisions on the open pod
review items" lines), plans/keyboard.md §2b and plans/roadmap.md M3b, nothing else to start.
M3b session 5: pod-power, as decided: 0603 capacitor across the 5 V converter's VIN and VOUT pins, 100 nF at the
TPS2553's input, VPACK wider, next fuse value up (pick it from the series' curves at 50 C; show me the value before
using it). pod-power is placed and routed again; no other board changes without asking. Then ERC / DRC / parity 0,
fab outputs, and the wireless shells' bosses, posts and notches checked against the new board (0 clashes).
Budget: tokens are tight. PCB and CAD work stays with you; delegate only lookups.
No leftover background processes. End by updating next.md, committing, and giving me the prompt for the next session.
```
