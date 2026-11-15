#!/usr/bin/env python3
"""ESD arrays in the path or on a stub (robustness review, finding 4): for every signal pad of every TPD4E1U06 on a
routed board, the copper length from the receptacle pin to the array, and how far the array hangs off the way from
that pin to every other pad of the net (stub = (d(J, A) + d(A, X) - d(J, X)) / 2 along the tracks; 0 = the strike
passes the array before it reaches X).

Run with KiCad's Python:
    /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 tools/esd_stub.py [--max 2.0] board ...
Exit 1 if a stub is longer than --max (mm). Tracks and vias only (signal nets have no areas).
"""
import heapq
import math
import os
import sys
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parent.parent
MM = pcbnew.ToMM


def graph(b, net):
    """Nodes (x, y, layer) in nm; edges with lengths in mm. Track ends that touch another track's middle are joined."""
    segs, vias = [], []
    for t in b.GetTracks():
        if t.GetNetname() != net:
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            vias.append((t.GetPosition().x, t.GetPosition().y))
        else:
            segs.append(((t.GetStart().x, t.GetStart().y), (t.GetEnd().x, t.GetEnd().y), t.GetLayer(), t.GetWidth()))
    adj = {}

    def link(p, q, d):
        adj.setdefault(p, []).append((q, d))
        adj.setdefault(q, []).append((p, d))
    for a, e, layer, w in segs:
        cuts = [a, e]
        for a2, e2, layer2, _ in segs:                      # other tracks' ends on this track
            if layer2 != layer:
                continue
            for q in (a2, e2):
                if q in (a, e):
                    continue
                dx, dy = e[0] - a[0], e[1] - a[1]
                n2 = dx * dx + dy * dy
                if not n2:
                    continue
                k = ((q[0] - a[0]) * dx + (q[1] - a[1]) * dy) / n2
                if 0 < k < 1 and math.hypot(a[0] + k * dx - q[0], a[1] + k * dy - q[1]) <= w / 2:
                    cuts.append(q)
        cuts.sort(key=lambda q: math.hypot(q[0] - a[0], q[1] - a[1]))
        for p, q in zip(cuts, cuts[1:]):
            link((p[0], p[1], layer), (q[0], q[1], layer), MM(math.hypot(p[0] - q[0], p[1] - q[1])))
    nodes = list(adj)
    for vx, vy in vias:                                      # a via joins every node at its place
        at = [n for n in nodes if math.hypot(n[0] - vx, n[1] - vy) < 50000]
        for n in at:
            link(("via", vx, vy), n, 0.0)
    return adj


def attach(adj, pad, key):
    """Join a pad to the track nodes inside it (through-hole pads on every layer)."""
    box = pad.GetBoundingBox()
    c = pad.GetPosition()
    layers = pad.GetLayerSet()
    for n in list(adj):
        if n[0] == "via" or isinstance(n[0], str):
            if n[0] == "via" and box.Contains(pcbnew.VECTOR2I(int(n[1]), int(n[2]))):
                adj.setdefault(key, []).append((n, 0.0)); adj[n].append((key, 0.0))
            continue
        if layers.Contains(n[2]) and box.Contains(pcbnew.VECTOR2I(int(n[0]), int(n[1]))):
            d = MM(math.hypot(n[0] - c.x, n[1] - c.y))
            adj.setdefault(key, []).append((n, d)); adj[n].append((key, d))


def dist(adj, src):
    best, heap, k = {src: 0.0}, [(0.0, 0, src)], 0
    while heap:
        d, _, n = heapq.heappop(heap)
        if d > best.get(n, 1e9):
            continue
        for m, w in adj.get(n, ()):
            if d + w < best.get(m, 1e9):
                best[m] = d + w
                k += 1
                heapq.heappush(heap, (d + w, k, m))
    return best


def board(name, limit):
    b = pcbnew.LoadBoard(str(ROOT / "hardware" / name / f"{name}.kicad_pcb"))
    fps = list(b.GetFootprints())
    worst = 0.0
    for u in sorted((f for f in fps if f.GetValue() in ("TPD4E1U06", "USBLC6-2SC6")), key=lambda f: f.GetReference()):
        for p in u.Pads():
            net = p.GetNetname()
            if not net or net == "GND" or net.startswith("unconnected") or net.lstrip("/") in ("+5V", "+3V3") or "VBUS" in net:
                continue
            adj = graph(b, net)
            others = [(f.GetReference(), q) for f in fps for q in f.Pads() if q.GetNetname() == net and f is not u]
            jp = [(r, q) for r, q in others if r.startswith("J") and "Receptacle" in str(next(f for f in fps if f.GetReference() == r).GetFPID().GetLibItemName())
                  or r.startswith("J") and any(k in next(f for f in fps if f.GetReference() == r).GetValue() for k in ("USB-C", "MODULE PORT", "USB4085"))]
            if not jp:
                continue
            attach(adj, p, "A")
            for i, (r, q) in enumerate(others):
                attach(adj, q, ("P", i))
            da = dist(adj, "A")
            line = []
            for r, q in jp:
                kj = ("P", others.index((r, q)))
                dj = dist(adj, kj)
                if "A" not in dj:
                    continue
                stub = 0.0
                for i, (r2, q2) in enumerate(others):
                    k2 = ("P", i)
                    if r2 == r or k2 not in dj or k2 not in da:
                        continue
                    stub = max(stub, (dj["A"] + da[k2] - dj[k2]) / 2)
                line.append((q.GetNumber(), dj["A"], stub))
            if line:
                s = max(x[2] for x in line)
                worst = max(worst, s)
                print(f"{name} {u.GetReference()}.{p.GetNumber()} {net.lstrip('/'):10s} " + "  ".join(f"{n}: {d:.1f} mm to the array, stub {st:.1f}" for n, d, st in line)
                      + ("   <-- stub" if s > limit else ""))
    print(f"{name}: longest stub {worst:.1f} mm (limit {limit})")
    return worst <= limit


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    limit = float(next((sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--max"), "2.0"))
    args = [a for a in args if a != str(limit) and a != next((sys.argv[i + 1] for i, x in enumerate(sys.argv) if x == "--max"), None)]
    ok = all([board(n, limit) for n in args])
    sys.stdout.flush()
    os._exit(0 if ok else 1)              # KiCad's Python crashes at exit after pcbnew work


if __name__ == "__main__":
    main()
