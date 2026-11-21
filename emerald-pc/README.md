# Emerald PC

A native PC build of Pokémon Emerald, made from the
[pret/pokeemerald](https://github.com/pret/pokeemerald) decompilation. It isn't an
emulator: the game's own C code is compiled for x86, and a small platform layer
takes the place of the GBA hardware.

This is a personal project. Don't distribute built binaries, because they contain
the game's assets.

## Status

| Part | State |
|---|---|
| Decompilation builds a ROM identical to retail (SHA-1 `f3ae0881…`) | done |
| All game C code and data compiled for 32-bit x86 | done |
| Platform layer: memory map, frame/scanline loop, interrupts, DMA, BIOS calls | done |
| Graphics renderer (text and affine BGs, sprites, windows, blending, mosaic) | done, pixel-identical to mGBA on tested frames |
| Sound engine (m4a sequencer, 48 kHz 16-bit mixer, GB PSG channels) | done, matches mGBA by spectrogram |
| Flash saves (to a `.sav` file), real-time clock (host clock) | done |
| New game → intro → naming screen | playable |
| SDL2 window, keyboard/gamepad, Windows `.exe` | next |
| Widescreen, HD renderer, HD asset packs | planned |

## How it works

- **Memory map.** The 32-bit process reserves memory at the GBA's real addresses
  (`0x02000000` work RAM, `0x06000000` VRAM and so on), so the game's hard-coded
  addresses work unchanged.
- **Frame loop.** When the game waits for VBlank, `pc/platform.c` runs the 228
  scanlines: it renders each visible line, runs HBlank DMA and interrupts, and
  fires the VBlank interrupt. Per-scanline effects therefore work as they do on
  hardware.
- **Data.** The decomp's event scripts, maps, battle scripts and music are ARM
  assembler data files. `pc/asm_transform.py` rewrites their syntax for x86 `as`
  (comments, `.align`, `.word`). The resulting sections have the same sizes as
  the ARM build.
- **Open bus.** Some original code reads through NULL pointers after freeing
  screen state. On a GBA that harmlessly reads the BIOS. `pc/nullguard.c` catches
  those reads, emulates them as returning 0, and logs each one.
- **Changes to the decomp** are in `patches/pokeemerald-pc.patch` (about 50
  lines, all under `#ifdef PLATFORM_PC` or `UBFIX`). The GBA build still matches
  the retail ROM.

## Building (Linux)

```sh
sudo apt install build-essential gcc-multilib binutils-arm-none-eabi libpng-dev git python3
./setup.sh            # headless test build: work/pokeemerald/build/pc/emerald_headless
```

The headless build replays an input script and writes screenshots and audio:

```sh
cat > demo.txt <<EOF
wait 300
tap 8 1          # Start (key mask, GBA bit order)
wait 200
shot title.ppm
quit
EOF
./work/pokeemerald/build/pc/emerald_headless --script demo.txt --save test.sav --wav out.wav
```
