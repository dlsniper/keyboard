# Next

State 2026-09-14: spec at rev 7 plus pre-schematic research. KiCad skeleton and
custom library in `hardware/`. Details in `docs/open-questions.md`.

## You (manual)

- [ ] Stock checks at Mouser/DigiKey/TME/Farnell (they block automated requests): SAMZO
      PR5L3715-4P-C-H + PR5L2820-4P-C-F (P8), KTS1693 + TPS25947 (P7),
      TPS61099DRVR + MAX17222ELT+ (P11), JST GH SMxxB-GHS-TB + cables (P9)
- [ ] If SAMZO isn't sold in Europe → switch to Mill-Max Maxnetic 872/873 (redo the seam, width, M1)
- [ ] Order LED samples: SunLED XZMDKCBDDG45S-9, Inolux IN-P32TRRRGB,
      QT-Brightek QBLP677R-RGB (P1 combined footprint, pinout mirror)
- [ ] Provide: Maxim land pattern 90-0004 (µDFN-6, L622+1C) from analog.com
- [ ] Provide: `git clone --depth 1 https://github.com/kiswitch/kiswitch hardware/lib/kiswitch`
- [ ] Optional: ask Lumissil for the IS31FL3733 input clamp-current limit (E11)
- [ ] Optional: attach the Konnect MCP before schematic capture
- [ ] Decide P14: TPS22950L is WCSP-only (key board) → accept, move the switch to the
      downstream link board, or use the TPS22950C

## Claude (once inputs arrive)

- [ ] MAX17222 µDFN footprint (needs 90-0004)
- [ ] Vendor kiswitch; MX hotswap + combined Ø4.5 mm LED footprint (needs samples)
- [ ] Choose the 2×AA holder part; footprint
- [ ] `.gitignore` for `build/`

## Then Phase 1 / Phase 3

- Phase 1 print + test cell: M1–M4, M6–M8, P5, P12, LED combined footprint
- Phase 3 schematics, in order: battery, usb-port, link, seam, dial, core, key boards
  (the key boards wait for Phase 1)
- In Phase 3: E12 pin assignment, E9 fault currents, E11 resistor values, F6 ID bands,
  E3 PR1 threshold, ISET/OVLO/FB dividers, MAX17222 0.5 A ILIM check,
  TPS22950L limit ≤~2 A (P9)

## Check

`python3 tools/gen_kicad.py && tools/kicad-check.sh` (currently fails only on "no board outline")
