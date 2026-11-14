#!/usr/bin/env bash
# Bring every KiCad file under hardware/ to the installed KiCad's file format, or check that it already is.
#   tools/kicad_format.sh            upgrade in place (schematics, boards, our symbol and footprint library)
#   tools/kicad_format.sh --check    change nothing; list the files KiCad would convert and exit 1 if there are any
# Why: the generators (gen_kicad.py, schlib.py) write schematic text with an older format stamp, and KiCad then says
# on opening that the file comes from an older version. Every generator runs this as its last step and
# tools/kicad-check.sh runs the check, so an old-format file cannot stay unnoticed (user, 2026-11-14).
# archive/ (rev 8) and the vendored hardware/lib/kiswitch are never touched.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLI="${KICAD_CLI:-/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli}"
check=0; [ "${1:-}" = "--check" ] && check=1
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT

stamp() { head -c 400 "$1" | tr -d '\n\t ' | grep -o '(version[0-9]*)' | head -1; }

# the format numbers this KiCad writes: upgrade a copy of one file of each kind
want() {            # kind, sample file
  cp "$2" "$tmp/sample.$1"
  case "$1" in
    kicad_sch) "$CLI" sch upgrade --force "$tmp/sample.$1" >/dev/null 2>&1 ;;
    kicad_pcb) "$CLI" pcb upgrade --force "$tmp/sample.$1" >/dev/null 2>&1 ;;
    kicad_sym) "$CLI" sym upgrade --force "$tmp/sample.$1" >/dev/null 2>&1 ;;
  esac
  stamp "$tmp/sample.$1"
}
smallest() { find "$ROOT/hardware" -name "*.$1" -not -path '*/kiswitch/*' -exec ls -S {} + | tail -1; }
W_SCH="$(want kicad_sch "$(smallest kicad_sch)")"
W_PCB="$(want kicad_pcb "$(smallest kicad_pcb)")"
W_SYM="$(want kicad_sym "$ROOT/hardware/lib/keyboard.kicad_sym")"
mkdir -p "$tmp/fp.pretty"; cp "$(ls "$ROOT"/hardware/lib/keyboard.pretty/*.kicad_mod | head -1)" "$tmp/fp.pretty/"
"$CLI" fp upgrade --force "$tmp/fp.pretty" >/dev/null 2>&1
W_FP="$(stamp "$(ls "$tmp"/fp.pretty/*.kicad_mod | head -1)")"

old=0
while IFS= read -r f; do
  case "$f" in
    *.kicad_sch) w="$W_SCH"; cmd=(sch upgrade) ;;
    *.kicad_pcb) w="$W_PCB"; cmd=(pcb upgrade) ;;
    *.kicad_sym) w="$W_SYM"; cmd=(sym upgrade --force) ;;
    *.kicad_mod) w="$W_FP"; cmd=() ;;
  esac
  [ "$(stamp "$f")" = "$w" ] && continue
  if [ "$check" = 1 ]; then
    echo "old format: ${f#$ROOT/}  $(stamp "$f"), KiCad writes $w"; old=1
  elif [ "${#cmd[@]}" -gt 0 ]; then
    "$CLI" "${cmd[@]}" "$f" >/dev/null 2>&1; echo "upgraded ${f#$ROOT/}"
  else
    old=2            # footprints are upgraded as a library, below
  fi
done < <(find "$ROOT/hardware" \( -name '*.kicad_sch' -o -name '*.kicad_pcb' -o -name '*.kicad_sym' -o -name '*.kicad_mod' \) -not -path '*/kiswitch/*' | sort)
if [ "$old" = 2 ]; then
  "$CLI" fp upgrade --force "$ROOT/hardware/lib/keyboard.pretty" >/dev/null 2>&1; echo "upgraded hardware/lib/keyboard.pretty"
  old=0
fi
[ "$check" = 1 ] && [ "$old" = 0 ] && echo "KiCad file formats: all current ($W_SCH schematics, $W_PCB boards)"
exit "$old"
