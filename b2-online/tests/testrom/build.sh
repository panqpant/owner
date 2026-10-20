#!/bin/sh
# Builds the test ROM: tests/testrom/build.sh OUT_DIR
set -e
here=$(cd "$(dirname "$0")" && pwd)
out=${1:-$here}
mkdir -p "$out"
CFLAGS="-mcpu=arm946e-s -marm -Os -ffreestanding -nostdlib -fno-builtin"
arm-none-eabi-gcc $CFLAGS -T "$here/arm9.ld" -o "$out/arm9.elf" "$here/crt0.s" "$here/arm9.c" -lgcc
arm-none-eabi-gcc -mcpu=arm7tdmi -marm -nostdlib -T "$here/arm7.ld" -o "$out/arm7.elf" "$here/arm7.s"
arm-none-eabi-objcopy -O binary "$out/arm9.elf" "$out/arm9.bin"
arm-none-eabi-objcopy -O binary "$out/arm7.elf" "$out/arm7.bin"
python3 -I "$here/mkrom.py" "$out/arm9.bin" "$out/arm7.bin" "$out/testrom.nds"
echo "$out/testrom.nds"
