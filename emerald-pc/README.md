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
| All game C code and data compiled for 32-bit x86 (Linux and Windows) | done |
| Platform layer: memory map, frame/scanline loop, interrupts, DMA, BIOS calls | done |
| Graphics renderer (text and affine BGs, sprites, windows, blending, mosaic) | done, pixel-identical to mGBA on tested frames |
| Sound engine (m4a sequencer, 48 kHz 16-bit mixer, GB PSG channels) | done, matches mGBA by spectrogram |
| Flash saves (`emerald.sav`), real-time clock (host clock) | done |
| SDL2 window, keyboard and gamepad, fullscreen, fast-forward, Windows `.exe` | done (Windows build not yet confirmed on real hardware) |
| **HD renderer:** each layer upscaled with xBR on the GPU, composited at screen resolution | done |
| **Widescreen:** overworld fills any aspect ratio (16:9, 21:9, any window); UI stays centred | done |
| **HD texture packs:** dump tiles (F6), replace with hand-drawn art in `hd/tiles` | done, see [HDPACKS.md](HDPACKS.md) |
| Day/night lighting outdoors, soft side fill for 3:2 screens, colour grade | done |
| **Lighting engine:** sun shadows that move with the clock, character silhouette shadows (sun and night lights), ambient occlusion, cloud shadows, swaying grass and trees, fireflies, rain splashes, forest light shafts, cave mist, lit windows at night, scenery reflections on water | done |
| **HD audio:** Lanczos resampling, smooth volume ramps, band-limited PSG with a stereo double, stereo hall reverb, mastering EQ and soft limiter | done |
| **Battles:** new backdrops drawn live for every terrain (town with lit windows and street lamps at night, routes, sea with sun/moon glitter, desert, mountains, cave crystals, indoor, underwater), real sky by the hour with sun, moon, stars and clouds, Pokémon shadows and breathing, move effects light the scene | done |
| Sharp scaling (pixel-edge sampling plus contrast-adaptive sharpening), highlight roll-off | done |
| **Relit:** per-pixel surface lighting (sun, moon, indoor key light, lamp rim light), water reflections of characters and sky, wet ground with puddle reflections and light streaks, lightning with shadows | done |
| Verified: intro, new game, overworld, a full battle turn, all 518 maps load and render | done |
| Full playthrough (late-game scenes, every menu, link features) | needs playtesting |

## Controls

| Key | Action |
|---|---|
| Arrows | D-pad |
| X / Z | A / B |
| Enter / Backspace | Start / Select |
| A / S | L / R |
| Tab (hold) | Fast-forward |
| F1 | HD / original graphics |
| F3 | Colour grade |
| F4 | Day/night lighting |
| F5 | HD audio / original GBA sound |
| F6 | Dump tiles for HD packs |
| F7 | Brass/strings/bass layer on / off |
| F8 | Camera tilt presets |
| Page Up/Down, I/K, mouse wheel, right-drag, right stick | Tilt the camera |
| F11 or Alt+Enter | Fullscreen |
| F12 | Screenshot |
| Esc | Quit |

Gamepads use the Xbox layout (bottom = A, right = B). Command-line options:
`--fullscreen`, `--aspect 16:9` (fix the shape instead of following the window), `--original`.

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
- **Changes to the decomp** are in `patches/pokeemerald-pc.patch` (about 175
  changed lines in 14 files, all under `#ifdef PLATFORM_PC` or `UBFIX`). The GBA build still matches
  the retail ROM.

## Building

`./setup.sh win` cross-builds `emerald.exe` for Windows. `./setup.sh sdl` builds the
windowed Linux version.

### Linux

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

## Roadmap

- ~~Relit 3~~ done: light bounce, door light beams, golden-hour rays, sky colours by hour, cave lantern with shadows
- ~~Relit 4~~ done: battle lighting, shadows, move-effect light, breathing Pokémon, new time-of-day battle backdrops
- Phase 5: widescreen menus, settings screen, rebindable keys, 64-bit
- Phase 1: offline HD art rebuild (pilot tooling in `tools/hdpilot`; needs a decision on AI upscaling)
- Phase 3: battle overhaul; Phase 4: synthesised soundtrack
