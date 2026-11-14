#!/usr/bin/env bash
# Normalise the custom library to the installed KiCad format, then run ERC and DRC
# on every project under hardware/, then the board-to-board header audit. Reports land in build/kicad-check/.
# archive/ (rev 8) is never checked.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KICAD_CLI="${KICAD_CLI:-$(command -v kicad-cli || echo /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli)}"
OUT="$ROOT/build/kicad-check"
mkdir -p "$OUT"

"$KICAD_CLI" sym upgrade --force "$ROOT/hardware/lib/keyboard.kicad_sym"
"$KICAD_CLI" fp upgrade --force "$ROOT/hardware/lib/keyboard.pretty"

status=0
echo "== file formats"
"$ROOT/tools/kicad_format.sh" --check || status=1
while IFS= read -r pro; do
  dir="$(dirname "$pro")"
  name="$(basename "$pro" .kicad_pro)"
  echo "== $name"
  if [ -f "$dir/$name.kicad_sch" ]; then   # plates have no schematic
    "$KICAD_CLI" sch erc --exit-code-violations --output "$OUT/$name-erc.rpt" "$dir/$name.kicad_sch" || status=1
  fi
  # errors only: kicad-cli counts warnings as violations too, and a few are known and written into the fab notes
  # (via pairs 0.47-0.49 mm hole to hole on hub-conn and port-module, the USB4085's outline at usb-port's edge);
  # tools/pcb_check.sh lists the warnings and checks schematic parity
  "$KICAD_CLI" pcb drc --severity-error --exit-code-violations --output "$OUT/$name-drc.rpt" "$dir/$name.kicad_pcb" || status=1
done < <(find "$ROOT/hardware" -name '*.kicad_pro' -not -path '*/lib/*' | sort)

echo "== key boards: netlist self-check against layout/keys.json and the spec"
"$ROOT/.venv/bin/python" "$ROOT/tools/sch_keys.py" --verify || status=1

echo "== hub boards: netlist check against the tools/sch_hub.py tables, cross-board checks"
"$ROOT/.venv/bin/python" "$ROOT/tools/sch_hub.py" --verify 2>&1 | grep -v "^INFO\|^WARNING" || status=1

echo "== interconnect"
"$ROOT/.venv/bin/python" "$ROOT/tools/check_interconnect.py" > "$OUT/interconnect.rpt" || status=1
grep "^ERR" "$OUT/interconnect.rpt" || true
tail -n 1 "$OUT/interconnect.rpt"

exit "$status"
