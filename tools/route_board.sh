#!/usr/bin/env bash
# Place, route and check one key board, again and again until the DRC is clean (the strip autorouter's result
# differs from run to run). Usage: [PASSES=10] tools/route_board.sh numpad [tries, default 5]      KiCad must be closed.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
m="$1"
for try in $(seq 1 "${2:-5}"); do
  "$PY" "$ROOT/tools/pcb_keys.py" "$m" --force 2>&1 | grep ERROR
  "$PY" "$ROOT/tools/route_keys.py" "$m" --strip --passes "${PASSES:-30}" 2>&1 | grep -E "WARNING|NO ROOM|finish|^$m:"
  out="$(OPEN=10 "$ROOT/tools/pcb_check.sh" "$m")"
  echo "try $try: $out" | cut -c1-900
  if echo "$out" | head -1 | grep -q ": 0 errors, 0 parity, 0 unconnected"; then exit 0; fi
  cp "$ROOT/hardware/$m/$m.kicad_pcb" "$ROOT/build/route/$m/$m-try$try.kicad_pcb"
done
exit 1
