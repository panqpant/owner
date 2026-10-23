#!/bin/sh
# Build Johto Emerald from source. No ROM needed: pret/pokeemerald rebuilds the game from code.
# Needs: git, make, gcc, python3, libpng-dev, binutils-arm-none-eabi (plus xdelta3 to make a patch).
# Usage: ./build.sh [workdir]   -> <workdir>/pokeemerald/pokeemerald.gba
set -e
here=$(cd "$(dirname "$0")" && pwd)
work=${1:-"$here/work"}
mkdir -p "$work" && cd "$work"
[ -d agbcc ] || git clone --depth 1 https://github.com/pret/agbcc.git
[ -d pokeemerald ] || { git clone https://github.com/pret/pokeemerald.git && git -C pokeemerald checkout -q "$(cat "$here/UPSTREAM_COMMIT")"; }
[ -x pokeemerald/tools/agbcc/bin/agbcc ] || (cd agbcc && ./build.sh && ./install.sh ../pokeemerald)

# Vanilla build first: it must match retail Emerald (USA) exactly, so the patch lines up with real carts
if [ ! -f vanilla.gba ]; then
    make -C pokeemerald -j"$(nproc)" compare
    cp pokeemerald/pokeemerald.gba vanilla.gba
fi
git -C pokeemerald checkout -q -- .
"$here/tools/apply.sh" pokeemerald
make -C pokeemerald -j"$(nproc)"
if command -v xdelta3 >/dev/null; then
    xdelta3 -e -9 -f -s vanilla.gba pokeemerald/pokeemerald.gba "$here/patch/johto-emerald.xdelta"
    echo "patch written to $here/patch/johto-emerald.xdelta"
fi
