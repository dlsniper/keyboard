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
while IFS= read -r pro; do
  dir="$(dirname "$pro")"
  name="$(basename "$pro" .kicad_pro)"
  echo "== $name"
  "$KICAD_CLI" sch erc --exit-code-violations --output "$OUT/$name-erc.rpt" "$dir/$name.kicad_sch" || status=1
  "$KICAD_CLI" pcb drc --exit-code-violations --output "$OUT/$name-drc.rpt" "$dir/$name.kicad_pcb" || status=1
done < <(find "$ROOT/hardware" -name '*.kicad_pro' -not -path '*/lib/*' | sort)

echo "== interconnect"
"$ROOT/.venv/bin/python" "$ROOT/tools/check_interconnect.py" > "$OUT/interconnect.rpt" || status=1
grep "^ERR" "$OUT/interconnect.rpt" || true
tail -n 1 "$OUT/interconnect.rpt"

exit "$status"
