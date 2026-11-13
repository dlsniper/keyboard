#!/usr/bin/env bash
# DRC with schematic parity for one or more key boards; prints a summary. Usage: tools/pcb_check.sh left right numpad
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
mkdir -p "$ROOT/build/kicad-check"
for m in "$@"; do
  "$CLI" pcb drc --schematic-parity --severity-all --format json -o "$ROOT/build/kicad-check/$m-drc.json" "$ROOT/hardware/$m/$m.kicad_pcb" >/dev/null 2>&1
  python3 - "$ROOT/build/kicad-check/$m-drc.json" "$m" "${OPEN:-0}" "${ERRS:-12}" <<'P'
import json, sys, collections
d = json.load(open(sys.argv[1]))
err = [v for v in d["violations"] if v["severity"] == "error"]
warn = collections.Counter(v["type"] for v in d["violations"] if v["severity"] != "error")
print(f"{sys.argv[2]}: {len(err)} errors, {len(d.get('schematic_parity', []))} parity, {len(d['unconnected_items'])} unconnected, warnings {dict(warn)}")
print("  ", dict(collections.Counter(v["type"] for v in err)))
for v in err[:int(sys.argv[4]) if len(sys.argv) > 4 else 12]:
    print("  ", v["type"], [(i["description"][:60], round(i["pos"]["x"], 1), round(i["pos"]["y"], 1)) for i in v["items"]])
for v in d.get("schematic_parity", [])[:10]:
    print("   parity", v["type"], [i["description"][:60] for i in v["items"]])
for v in d["unconnected_items"][:int(sys.argv[3]) if len(sys.argv) > 3 else 0]:
    print("   open", [(i["description"][:60], round(i["pos"]["x"], 1), round(i["pos"]["y"], 1)) for i in v["items"]])
P
done
