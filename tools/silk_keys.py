#!/usr/bin/env python3
"""Silkscreen pass for a key board: every visible reference that sits on a pad, a hole, another part's silk or
another reference is moved to the nearest free spot beside its part. Copper is not touched.

tools/route_keys.py runs this at its end. For a board that is already routed (KiCad closed):
    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 tools/silk_keys.py left
Then: tools/pcb_check.sh left   (no silk_overlap, no silk_over_copper)
"""
import math
import os
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pcb_keys import ROOT, frame, inside  # noqa: E402

SIZE, THICK = 1.0, 0.15              # JLCPCB: 1 mm high, 0.15 mm stroke reads safely
PAD_GAP, SILK_GAP, EDGE_GAP = 0.2, 0.12, 0.5
STEPS = (0.3, 0.9, 1.6, 2.4, 3.4, 4.6)

T = pcbnew.ToMM
mm = pcbnew.FromMM


def box(bb, grow=0.0):
    return T(bb.GetLeft()) - grow, T(bb.GetTop()) - grow, T(bb.GetRight()) + grow, T(bb.GetBottom()) + grow


def hit(a, b, gap=0.0):
    return a[0] < b[2] + gap and b[0] < a[2] + gap and a[1] < b[3] + gap and b[1] < a[3] + gap


def tidy(b, lines):
    """Returns (moved, stuck): references moved, and those for which no free spot was found."""
    silk_of = {False: pcbnew.F_SilkS, True: pcbnew.B_SilkS}
    cu_of = {False: pcbnew.F_Cu, True: pcbnew.B_Cu}
    fixed = {pcbnew.F_SilkS: [], pcbnew.B_SilkS: []}     # pads and holes, per silk layer
    drawn = {pcbnew.F_SilkS: [], pcbnew.B_SilkS: []}     # silk graphics (tested by their real shape: an outline is not its box)
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            for back in (False, True):
                if pad.GetDrillSize().x > 0 or pad.IsOnLayer(cu_of[back]):
                    fixed[silk_of[back]].append((box(pad.GetBoundingBox()), PAD_GAP))
        for g in fp.GraphicalItems():
            if g.GetLayer() in fixed:
                drawn[g.GetLayer()].append(g)
    # not the switches: their reference is part of the key pattern, clear by construction, and its box is too
    # coarse a test on the turned keys
    refs = [fp for fp in sorted(b.GetFootprints(), key=lambda f: f.GetReference())
            if fp.Reference().IsVisible() and not fp.GetReference().startswith("SW")]
    for fp in b.GetFootprints():
        if fp.Reference().IsVisible() and fp.GetReference().startswith("SW"):
            fixed[fp.Reference().GetLayer()].append((box(fp.Reference().GetBoundingBox()), 0.0))
    for fp in refs:
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(mm(SIZE), mm(SIZE)))
        fp.Reference().SetTextThickness(mm(THICK))
    placed = {}                                          # reference -> its box, once it is known to be free

    def free(fp, bb, strict=True):
        """strict: with the gaps a new spot must keep; otherwise only whether it touches anything where it is."""
        layer = fp.Reference().GetLayer()
        if not all(inside(lines, p, EDGE_GAP if strict else 0.0) for p in ((bb[0], bb[1]), (bb[2], bb[1]), (bb[2], bb[3]), (bb[0], bb[3]))):
            return False
        if any(hit(bb, o, gap if strict else 0.0) for o, gap in fixed[layer]):
            return False
        g = SILK_GAP if strict else 0.0
        rect = pcbnew.BOX2I(pcbnew.VECTOR2I(mm(bb[0] - g), mm(bb[1] - g)), pcbnew.VECTOR2I(mm(bb[2] - bb[0] + 2 * g), mm(bb[3] - bb[1] + 2 * g)))
        if any(s.HitTest(rect, False, 0) for s in drawn[layer]):
            return False
        return not any(hit(bb, o, SILK_GAP if strict else 0.0) for r, (o, lay) in placed.items() if lay == layer and r != fp.GetReference())

    moved, stuck = [], []
    waiting = []
    for fp in refs:                                      # those that are fine stay and become obstacles
        bb = fp.Reference().GetBoundingBox()               # the box of a turned text is larger than its ink
        turn = fp.GetOrientationDegrees() % 90
        bb = box(bb, -0.2 - T(max(bb.GetWidth(), bb.GetHeight())) * math.sin(math.radians(min(turn, 90 - turn))) / 2)
        if free(fp, bb, False):
            placed[fp.GetReference()] = (bb, fp.Reference().GetLayer())
        else:
            waiting.append(fp)
    for fp in waiting:
        ref = fp.Reference()
        body = box(fp.GetBoundingBox(False))
        cx, cy = (body[0] + body[2]) / 2, (body[1] + body[3]) / 2
        hx, hy = (body[2] - body[0]) / 2, (body[3] - body[1]) / 2
        a0 = ref.GetTextAngleDegrees()
        done = False
        for d in STEPS:
            for ang in (a0, a0 + 90):
                ref.SetTextAngleDegrees(ang)
                tb = box(ref.GetBoundingBox())
                tx, ty = (tb[2] - tb[0]) / 2, (tb[3] - tb[1]) / 2
                for ox, oy in ((0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (1, -1), (-1, 1), (1, 1)):
                    x, y = cx + ox * (hx + tx + d), cy + oy * (hy + ty + d)
                    ref.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
                    tb = box(ref.GetBoundingBox())
                    if free(fp, tb):
                        placed[fp.GetReference()] = (tb, ref.GetLayer())
                        done = True
                        break
                if done:
                    break
            if done:
                break
        (moved if done else stuck).append(fp.GetReference())
    return moved, stuck


def main():
    name = sys.argv[1]
    pcb = ROOT / "hardware" / name / f"{name}.kicad_pcb"
    b = pcbnew.LoadBoard(str(pcb))
    _, _, (lines, _, _, _, _) = frame(name)
    moved, stuck = tidy(b, lines)
    pcbnew.SaveBoard(str(pcb), b)
    print(f"{name}: {len(moved)} references moved ({' '.join(moved)})" + (f"; NO ROOM for {' '.join(stuck)}" if stuck else ""))
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
