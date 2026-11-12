#!/usr/bin/env python3
"""Board-to-board header audit (spec §6 "Board interconnect", §16 "every net matches end to end").

Reads the PARTS tables of the sch_*.py scripts (the schematics' source of truth) and checks:
  1. every JST GH header is either mated to its partner or listed as pending (rev 9 key boards not drawn yet);
  2. mated headers agree pin for pin, through an explicit per-pair net alias table;
  3. mated headers share footprint pin count and MPN;
  4. end-reversal: pin k faces pin N+1-k. A power pin may only face its own net; GND facing a signal is an
     error unless allowlisted with its reason (spec §6 table);
  5. every power net has >= 2 contacts, and every non-GND net on >= 2 contacts is a power net;
  6. pin counts are unique per header type (the battery pair shares 4 by design).

Run with the venv python (the scripts import kicad-sch-api): ../.venv/bin/python check_interconnect.py
"""

import importlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Rev 9: only the boards still in hardware/. Archived rev 8 boards (archive/rev8/) are not read.
BOARDS = ["usb_port", "dial"]

POWER = {
    "usb_port": {"VBUS_LOCAL"},
    "dial": set(),
}

# (board, ref), (board, ref), {net on the second board: net on the first}
MATES = []

# mate lives on a rev 9 key board that has no schematic yet (roadmap M1)
PENDING = {
    ("usb_port", "J502"): "right key board, host port header",
    ("dial", "J901"): "right key board J_DIAL",
}

# (board, ref, net that faces GND when reversed): why it is harmless
GND_SIGNAL_OK = {
    ("usb_port", "J502", "ACOK"): "open-drain KTS1693 ACOK into GND",
}

SHARED_COUNT = {"J_BAT_A", "J_BAT_B", "J_BAT"}


def load():
    headers = {}
    for board in BOARDS:
        mod = importlib.import_module(f"sch_{board}")
        for ref, _sym, value, fp, _pos, pins, fields in mod.PARTS:
            if "JST_GH" not in fp:
                continue
            n = int(re.search(r"_1x(\d+)-", fp).group(1))
            nets = {int(k): v for k, v in pins.items()}
            if sorted(nets) != list(range(1, n + 1)):
                raise SystemExit(f"{board} {ref}: pins {sorted(nets)} do not cover 1..{n} of {fp}")
            headers[(board, ref)] = {"name": value, "n": n, "fp": fp, "mpn": fields.get("MPN"), "nets": nets}
    return headers


def cls(board, net):
    if net == "GND":
        return "gnd"
    return "power" if net in POWER[board] else "signal"


def main():
    headers = load()
    errors, notes = [], []
    err = errors.append

    mated = set()
    for a, b, alias in MATES:
        mated |= {a, b}
        ha, hb = headers[a], headers[b]
        tag = f"{a[0]} {a[1]} ({ha['name']}) <-> {b[0]} {b[1]} ({hb['name']})"
        if ha["n"] != hb["n"]:
            err(f"{tag}: {ha['n']} vs {hb['n']} pins")
            continue
        if ha["mpn"] != hb["mpn"]:
            err(f"{tag}: MPN {ha['mpn']} vs {hb['mpn']}")
        unused = set(alias) - set(hb["nets"].values())
        if unused:
            err(f"{tag}: alias for nets not on the header {sorted(unused)}")
        for k in range(1, ha["n"] + 1):
            na, nb = ha["nets"][k], hb["nets"][k]
            if na != alias.get(nb, nb):
                err(f"{tag}: pin {k} {na} vs {nb}")
            if cls(a[0], na) != cls(b[0], nb):
                err(f"{tag}: pin {k} class {cls(a[0], na)} vs {cls(b[0], nb)}")
        notes.append(f"ok  {tag}: {ha['n']} pins")

    for key, h in sorted(headers.items()):
        if key in mated and key in PENDING:
            err(f"{key}: both mated and pending")
        elif key not in mated and key not in PENDING:
            err(f"{key[0]} {key[1]} ({h['name']}): no mate and not pending")
        elif key in PENDING:
            notes.append(f"--  {key[0]} {key[1]} ({h['name']}): mate pending on {PENDING[key]}")

    for (board, ref), h in sorted(headers.items()):
        tag = f"{board} {ref} ({h['name']})"
        n, nets = h["n"], h["nets"]
        for k in range(1, n // 2 + 1):
            p, q = nets[k], nets[n + 1 - k]
            if p == q:
                continue
            cp, cq = cls(board, p), cls(board, q)
            if "power" in (cp, cq):
                err(f"{tag} reversed: pin {k} {p} faces pin {n + 1 - k} {q}")
            elif {cp, cq} == {"gnd", "signal"}:
                sig = p if cp == "signal" else q
                if (board, ref, sig) in GND_SIGNAL_OK:
                    notes.append(f"ok  {tag} reversed: {sig} faces GND ({GND_SIGNAL_OK[(board, ref, sig)]})")
                else:
                    err(f"{tag} reversed: signal {sig} faces GND (pins {k}/{n + 1 - k})")
        counts = {}
        for net in nets.values():
            counts[net] = counts.get(net, 0) + 1
        for net, c in counts.items():
            if cls(board, net) == "power" and c < 2:
                err(f"{tag}: power net {net} on {c} contact")
            if cls(board, net) == "signal" and c > 1:
                err(f"{tag}: {net} on {c} contacts but not in POWER[{board!r}]")

    by_count = {}
    for (board, ref), h in sorted(headers.items()):
        name = "J_BAT" if h["name"] in SHARED_COUNT else h["name"]
        prev = by_count.setdefault(h["n"], name)
        if prev != name:
            err(f"{board} {ref} ({h['name']}): {h['n']} pins also used by {prev}")

    for p in POWER:
        seen = {net for (board, _ref), h in headers.items() if board == p for net in h["nets"].values()}
        for net in sorted(POWER[p] - seen):
            err(f"POWER[{p!r}] lists {net}, which is on no header")

    for line in notes:
        print(line)
    for line in errors:
        print(f"ERR {line}")
    print(f"interconnect: {len(headers)} headers, {len(MATES)} mated pairs, {len(PENDING)} pending, "
          f"{len(errors)} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
