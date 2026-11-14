#!/usr/bin/env bash
# Place, route and check one hub board, again and again until the DRC is clean (the autorouter's result differs
# from run to run). Usage: [PASSES=25] tools/route_hub.sh hub-conn [tries, default 3]      KiCad must be closed.
# Boards: hub-core, battery, hub-conn, chain-cap (placed by pcb_hub.py), port-module (pcb_port.py). Failed tries are kept in build/route/<board>/.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
m="$1"
mkdir -p "$ROOT/build/route/$m"
for try in $(seq 1 "${2:-3}"); do
  case "$m" in port-module|usb-port) place=pcb_port.py ;; *) place=pcb_hub.py ;; esac
  "$PY" "$ROOT/tools/$place" --force "$m" 2>&1 | grep ERROR
  "$PY" "$ROOT/tools/route_hub.py" "$m" --passes "${PASSES:-25}" 2>&1 | grep -E "WARNING|no room|finish|tidy|^$m:"
  "$PY" "$ROOT/tools/silk_keys.py" "$m" 2>&1 | grep "^$m"
  out="$(OPEN=10 "$ROOT/tools/pcb_check.sh" "$m")"
  echo "try $try: $out" | cut -c1-900
  if echo "$out" | head -1 | grep -q ": 0 errors, 0 parity, 0 unconnected"; then exit 0; fi
  cp "$ROOT/hardware/$m/$m.kicad_pcb" "$ROOT/build/route/$m/$m-try$try.kicad_pcb"
done
exit 1
