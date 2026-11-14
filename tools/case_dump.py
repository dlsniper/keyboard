#!/usr/bin/env python3
"""Geometry for the case scripts (M3): build/case/<name>.json for left, right, numpad.

Run with KiCad's Python (KiCad closed), after the key board is routed and the plate exists:
    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 tools/case_dump.py [left right numpad]

Nothing is designed here: it reads the routed key board (holes, footprints) and takes outline, plate and bay from
tools/pcb_keys.py and tools/pcb_plate.py, so mech/case/build_case.py (FreeCAD, no pcbnew) sees the same numbers as
the boards. KiCad coordinates (mm, y down). Re-run after a key board is placed again.
"""
import json
import math
import os
import sys

import pcbnew

import pcb_keys as K
import pcb_plate as P


def main():
    names = [a for a in sys.argv[1:] if not a.startswith("--")] or ["left", "right", "numpad"]
    out = K.ROOT / "build" / "case"
    out.mkdir(parents=True, exist_ok=True)
    status = 0
    for name in names:
        keys, inner_sign, (lines, corners, origin, phi, front_rot) = K.frame(name)
        at, sb = K.strip_frame(lines, origin, phi, inner_sign)
        _, _, _, errors, _, plate, _ = P.build(name, False)
        bay0 = at(sb, 0.0)
        a1, t1 = at(sb + inner_sign, 0.0), at(sb, 1.0)      # a: board x along the rear edge (the bay is never mirrored)
        ax = (a1[0] - bay0[0], a1[1] - bay0[1]); tx = (t1[0] - bay0[0], t1[1] - bay0[1])
        bay = lambda a, t: (bay0[0] + a * ax[0] + t * tx[0], bay0[1] + a * ax[1] + t * tx[1])
        b = pcbnew.LoadBoard(str(K.HW / name / f"{name}.kicad_pcb"))
        fps, holes = [], []
        for fp in b.GetFootprints():
            item = str(fp.GetFPID().GetLibItemName())
            xy = (pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y))
            pads = [(pcbnew.ToMM(p.GetPosition().x), pcbnew.ToMM(p.GetPosition().y), pcbnew.ToMM(p.GetDrillSize().x),
                     pcbnew.ToMM(max(p.GetSize().x, p.GetSize().y))) for p in fp.Pads()]
            if item == K.HOLE_FP[1]:
                holes.append(xy)
                continue
            fps.append({"ref": fp.GetReference(), "value": fp.GetValue(), "item": item, "xy": xy,
                        "rot": fp.GetOrientationDegrees(), "back": bool(fp.IsFlipped()), "pads": pads})
        screws = [bay(*s) for s in K.BAY["screws"]]
        for s in screws:
            if min(math.hypot(s[0] - h[0], s[1] - h[1]) for h in holes) > 0.01:
                errors.append(f"no key board hole at the bay screw {s[0]:.2f}, {s[1]:.2f}")
        data = {"name": name, "inner_sign": inner_sign, "phi": phi, "fillet": K.FILLET, "rear": K.REAR,
                "corners": [list(c) for c in corners],           # front x outer, outer x rear, rear x inner, inner x front
                "holes": holes, "bay": {"origin": bay0, "a": ax, "t": tx, "screws": screws,
                                        "header": bay(*K.BAY["header"]), "port": list(P.PORT), "width": K.BAY["width"]},
                "plate": plate, "footprints": fps,
                "keys": [{k_: k[k_] for k_ in ("id", "x", "y", "rot", "w", "h", "kind")} for k in keys]}
        (out / f"{name}.json").write_text(json.dumps(data))
        print(f"{name}: {len(holes)} holes, {len(fps)} footprints, bay at {bay0[0]:.2f}, {bay0[1]:.2f}")
        for e in errors:
            print("ERROR", e)
        status |= bool(errors)
    sys.stdout.flush()
    os._exit(status)


if __name__ == "__main__":
    main()
