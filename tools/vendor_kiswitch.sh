#!/usr/bin/env bash
# Vendor the kiswitch footprints the key boards use into hardware/lib/kiswitch/:
# Kailh MX hotswap (CPG151101S11), the Cherry MX 2.00u stabiliser cutout, their 3D models
# and the licences. Choc footprints and the rest of the repo are left out.
#
# Run: tools/vendor_kiswitch.sh [path-to-kiswitch-clone]
# Without an argument it shallow-clones github.com/kiswitch/kiswitch into a temp dir.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/hardware/lib/kiswitch"

src="${1:-}"
if [[ -z "$src" ]]; then
  src="$(mktemp -d)/kiswitch"
  git clone --depth 1 https://github.com/kiswitch/kiswitch "$src"
fi
commit="$(git -C "$src" rev-parse HEAD)"
lib="$src/library"

stage="$(mktemp -d)"
chmod 755 "$stage"
mkdir -p "$stage/Switch_Keyboard_Hotswap_Kailh.pretty" "$stage/Mounting_Keyboard_Stabilizer.pretty" "$stage/3dmodels"
cp "$lib"/footprints/Switch_Keyboard_Hotswap_Kailh.pretty/SW_Hotswap_Kailh_MX*.kicad_mod "$stage/Switch_Keyboard_Hotswap_Kailh.pretty/"
# 2U, 2.25U and 2.75U keys share the 23.8 mm stabiliser spacing, so 2.00u is the only one used.
cp "$lib"/footprints/Mounting_Keyboard_Stabilizer.pretty/Stabilizer_Cherry_MX_2.00u.kicad_mod "$stage/Mounting_Keyboard_Stabilizer.pretty/"
for m in SW_Hotswap_Kailh_MX SW_Cherry_MX_Plate Stabilizer_Cherry_MX_2.00u; do
  cp "$lib/3dmodels/3d-library.3dshapes/$m.wrl" "$lib/3dmodels/3d-library.3dshapes/$m.stp" "$stage/3dmodels/"
done
cp "$src/LICENSE-MIT" "$src/LICENSE-CC-BY-SA" "$stage/"

# Point 3D models at the vendored copies. Key board projects sit one level below
# hardware/, so ${KIPRJMOD}/../lib reaches this directory.
find "$stage" -name '*.kicad_mod' -exec sed -i.bak \
  's#${KICAD6_3RD_PARTY}/3dmodels/com_github_perigoso_keyswitch-kicad-library/3d-library.3dshapes/#${KIPRJMOD}/../lib/kiswitch/3dmodels/#' {} +
find "$stage" -name '*.bak' -delete

cat > "$stage/VENDORED.md" <<EOF
# kiswitch (vendored subset)

Source: https://github.com/kiswitch/kiswitch at \`$commit\`, dual MIT / CC-BY-SA 4.0
(see the licence files). Regenerate with \`tools/vendor_kiswitch.sh\`; do not edit by hand.

- \`Switch_Keyboard_Hotswap_Kailh.pretty\`: MX variants only (Kailh CPG151101S11)
- \`Mounting_Keyboard_Stabilizer.pretty\`: Cherry MX 2.00u stabiliser (23.8 mm, covers 2U, 2.25U and 2.75U)
- \`3dmodels\`: the models those footprints reference, paths rewritten to \`\${KIPRJMOD}/../lib/kiswitch/3dmodels/\`
EOF

if [[ -e "$DEST" ]]; then
  old="$(mktemp -d)"
  mv "$DEST" "$old/"
  echo "previous $DEST moved to $old/kiswitch"
fi
mv "$stage" "$DEST"
echo "vendored kiswitch $commit into $DEST"
