# Handover: Emerald PC (read this first in a new chat)

This file carries the context of the long chat that built this project, so a
new chat can continue where it left off. Code is on branch
`claude/new-session-k24koo` (earlier: `claude/sharp-meitner-z013ct`) of `panqpant/owner`, folder `emerald-pc/`.

## What this is

A native Windows/Linux PC port of Pokémon Emerald built from the pret/pokeemerald
decompilation (not an emulator), with a large graphics/audio overhaul. Personal
use only: never distribute builds or the ROM; never commit binaries.

The owner plays on a 27" 2560x1440 BenQ monitor. That is the benchmark for
screenshots. Check every change at full 1440p size (crop at 1:1), not only
downscaled, before showing it.

## How to rebuild the work tree (it is not in the repo)

`emerald-pc/setup.sh` clones pokeemerald, applies `patches/pokeemerald-pc.patch`,
copies `pc/` and builds. The user's ROM is needed for the decomp's assets
(baserom check). Key commands, inside `work/pokeemerald`:

- Linux SDL build: `make -f pc/Makefile sdl` → `build/pc/emerald`
- Headless (scripted test runs, audio to WAV): `make -f pc/Makefile headless`
- Windows exe: `make -f pc/Makefile PLATFORM=win` (MinGW i686, SDL2 in `../sdl2-mingw`),
  then strip with `i686-w64-mingw32-strip`, package with SDL2.dll + README.txt + `hd/`.
- Screenshot runs: `xvfb-run -a -s "-screen 0 2560x1440x24" ./emerald --fullscreen --script X.txt`
  Script commands: `wait N`, `tap MASK N [M]`, `hold MASK N`, `shot PATH.bmp`,
  `call warpto GROUP NUM`, `call givemon SPECIES LV`, `call battle SPECIES LV`,
  `call weather N`, `call capture PATH.cap`, `quit`. Standard opening:
  `wait 300 / tap 8 1 / wait 200 / tap 8 1 60 / wait 200 / tap 1 1 60 / wait 100 / tap 1 60 30 / tap 1 90 30 / wait 2100 / tap 1 30 30`.
- Test env vars: `EMERALD_HOUR`, `EMERALD_SEASON` (0-3), `EMERALD_LIVEWX` (0-4),
  `EMERALD_RAINBOW`, `EMERALD_TILT`, `EMERALD_CINESTYLE`, `EMERALD_INTRO` (0-9),
  `EMERALD_BSCENE`, `EMERALD_WT_AUTO=slot`, `EMERALD_WT_STATS=n`, `EMERALD_NOGL`,
  `EMERALD_CLASSIC_AUDIO`, `EMERALD_MENU`.
- After changing files under `work/pokeemerald/{src,include}`, regenerate the
  patch: `git diff HEAD -- src include > ../../owner/emerald-pc/patches/pokeemerald-pc.patch`.
  Copy changed `pc/` files into `emerald-pc/pc/`.

Last Windows test build sent: **test 26**.

## Done so far (all committed)

Port (scanline PPU, m4a audio, flash saves, RTC, SDL2, gamepad), HD renderer
(xBR per layer at 1440p, sharp scaling), widescreen of any aspect, HD text, HD
tile packs, full lighting engine (time-of-day sun shadows, character shadows,
per-pixel surface lighting, reflections, wet weather, lightning, light bounce,
door beams, sky colours, cave lantern, ray-traced 2D light), living world
particles, area moods, daily seasons (spring/summer/autumn with leaf drifts/
winter with snow, a new one each real day), live weather (clear/cloudy/fog/
rain/storm/rainbow, visual only), new procedural battle backdrops by time of day,
battle lighting, battle camera, per-type move effects, ten battle intros (gentle
for wild, bolder for trainers, legendary shatter), cinematic story moments
(letterbox, camera push, 16 colour styles), HD audio (Lanczos, DS-era mix,
reverb, brass/bass layer), ambient soundscape, settings screen (F10), menu
backgrounds, tilt camera (right stick, PgUp/PgDn, I/K, wheel, right-drag),
Wonder Trade replica (W / Y on pad).

Session 2: water remake (continuous sea, shallows with seabed + caustics,
clouds reflected, surf wake); orchestral audio (real recorded instruments from
the FluidR3 GM soundfont via `hd/orchestra.bin`, built by
`pc/tools/sf2extract.py`; `EMERALD_NO_ORCH=1` turns it off); minimap removed,
M / pad X opens the game's own Hoenn region map; camera tilt now off by default
(owner: tilt looks bad with 2D sprites; it also disabled the water remake).
HD menus, step 1: party screen redrawn (glass cards, glowing cursor, smooth HP
bars, calm background). The game skips its own slot art/HP bars when
`gPcHdMenus` is on; `PcPartyUi()` (fieldfx.c) feeds the renderer. Step 2: every framed
window (dialogue, start menu, PC menus, yes/no, shops) gets a rounded frosted
panel: menu.c records windows (`PcPanelAdd/Remove`) instead of drawing frames;
`PcPanels()` checks each is still on screen. All menu screens (party, bag,
summary, Pokédex, PC boxes = menu kind 5) share one deep-blue background.

Item 7 (conveniences), always on in the PC version, no settings (owner: F10
stays graphics/audio only; no autosave): instant text, auto-run (B walks),
EXP Share for the whole party, physical/special split (gen-4 categories from
pokeemerald-expansion, table in fieldfx.c), F6 quick save (refused where the
start menu can't save and over a different file). Hard mode (trainers +10%
levels, min +2): Birch asks after the name; stored as FLAG_PC_HARD_MODE
(FLAG_UNUSED_0x020). Test hooks: `call flag N`, `call pc`.

Item 1 (3D world): owner wants own-made 3D scenery replacing the game's art;
characters and Pokémon stay the game's sprites (NOT to be modelled). Built:
`Render3d()` + `kWorld3d` in render_gl.c ray-trace a scene of code-built SDF
models (trees, houses grown from each door with pitched roof/windows/door,
blocks for cliffs/walls/rocks, ground and water with procedural detail),
placed from the map grid; colours sampled per cell from the art. Characters are
camera-facing cards from the OBJ layer. Outdoors overworld only; UI (BG0)
passes through. `EMERALD_NO3D=1` turns it off. Not done: weather/particles and
window panels are lost in 3D frames, ledges/stairs flat, cell-edge lines on
blocks, performance unmeasured on a real GPU (could need half-res).

## The owner's preferences (important)

- Wants big, visible upgrades, "think big". Answers short; often types quickly.
- Liked: Phase 2 lighting, procedural battle backdrops, cinematics, seasons with
  real visible change (e.g. leaves on the ground), Wonder Trade.
- Disliked, do not repeat: camera tilt (2D sprites look bad); the minimap; anything that looks like a colour filter; AI-upscaled
  or traced art ("terrible"); the redrawn grass; synth instruments ("weird and
  synthy", wants HG/SS-style sound instead); tile-shaped blotches or seams
  (always check at full size); crude particle sprites (seagulls); following
  Pokémon from party icons (dropped: "can't even rotate"); the first flat-colour
  minimap.
- Declined by policy: 3D remake / new 3D models of the game's characters or
  designs. Voxel/stand-up ideas were offered then skipped by the owner.
- The Wonder Trade is a fully offline fake; odds are modelled on community
  reports (no official stats exist): ~39% level 1, ~11% level 100, shiny ~1/52,
  ~3% legendary, all 386 species.

## Open items / ideas not yet done

- Owner's order from session 2: water (done) -> orchestral audio (first pass
  done, needs a listen) -> full HD menu redesign (party screen done) -> Switch-era conveniences (done) -> 3D world from the tiles with sprites standing up (no new 3D models).
- Surf Pokémon sprite renders with a black lower half (seen before session 2's changes).
- A thin strip of the original water art shows right against boat hulls (Slateport).
- Water art test is strongly-blue only (lavender walls were half-turned to water).

- Real Windows play-testing of recent builds (only screenshot-tested here).
- Settings screen entries for seasons, live weather, cinematics, minimap, moods.
- Smooth 120/144 Hz motion (frame interpolation), photo mode.
- HD menus beyond the bag background (party/summary/Pokédex unverified).
- Following Pokémon code exists but is disabled (`EMERALD_FOLLOW=1`).
- Commit messages end with the attribution lines from the session's reminder; no
  model names in commits.
