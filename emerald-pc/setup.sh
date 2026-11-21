#!/bin/bash
# Fetches the pokeemerald decompilation, applies the PC port, and builds it.
#
#   ./setup.sh            build the headless test binary (Linux)
#   ./setup.sh sdl        build the windowed game (Linux, needs SDL2)
#
# Requirements (Debian/Ubuntu): build-essential gcc-multilib binutils-arm-none-eabi
#   libpng-dev git python3, plus libsdl2-dev:i386 for the windowed build.
# No ROM is needed: the decompilation builds every asset from source.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${WORK:-$HERE/work}"
POKEEMERALD_COMMIT=9103e529c2fbdd7add4a1ff3350c6c1f92112c42
TARGET="${1:-headless}"

mkdir -p "$WORK"
cd "$WORK"

if [ ! -d pokeemerald ]; then
    git clone https://github.com/pret/pokeemerald.git
    git -C pokeemerald checkout -q "$POKEEMERALD_COMMIT"
    git -C pokeemerald apply "$HERE/patches/pokeemerald-pc.patch"
fi
if [ ! -d agbcc ]; then
    git clone https://github.com/pret/agbcc.git
fi

# Original GBA compiler, used by the reference GBA build that generates assets.
if [ ! -x pokeemerald/tools/agbcc/bin/agbcc ]; then
    (cd agbcc && sh build.sh && sh install.sh ../pokeemerald)
fi

# Port sources live next to the game code.
rm -rf pokeemerald/pc
cp -r "$HERE/pc" pokeemerald/pc

cd pokeemerald
# The GBA build converts graphics, maps and music into the forms the game
# includes; the PC build reuses those generated files.
make -j"$(nproc)"
make -f pc/Makefile -j"$(nproc)" "$TARGET"
echo "Built: $WORK/pokeemerald/build/pc/"
