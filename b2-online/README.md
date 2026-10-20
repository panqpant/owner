# Black 2 Online

Pokémon Black 2 on two PCs at once: see each other on the map, battle, trade, walking Pokémon, and
wild Pokémon that walk around instead of random encounters. It's the same idea as HeartGold Online,
rebuilt for Gen 5.

It has two halves (details in [docs/PROTOCOL.md](docs/PROTOCOL.md)):

| Half | What it does | Status |
|---|---|---|
| **The app** (`app/`) | DS emulator (melonDS) with Host / Join, finds the other PC on your Wi-Fi, ONLINE screen, time of day and season, quick-save, controllers, fullscreen | **Done and tested** |
| **The game side** (`rom/`) | The patch inside the ROM: shows each other on the map, walking Pokémon, battles, trades, walking wild Pokémon | **Not started: needs the ROM.** See [docs/ROM_SIDE.md](docs/ROM_SIDE.md) |

Right now the app plays Black 2 and links two PCs, but you won't see each other in the game until
the ROM patch exists. The ONLINE screen (F3) says so.

## Playing (Windows)

1. Put `Black2Online.exe` and your game in one folder, and name the game
   `Pokemon_Black2_Online.nds`. Copy the folder to the other PC too.
2. On your PC, open the app and choose **Host**. When Windows Firewall asks, tick both Private and
   Public and click Allow.
3. On the other PC, choose **Join**. It finds the host by itself. If it doesn't, press **F2** and
   type the address shown on the host's F3 screen.

| Key | Does |
|---|---|
| Arrow keys | Move |
| X / Z | A / B |
| S / A | X / Y |
| Q / W | L / R |
| Enter / Backspace | START / SELECT |
| Mouse | Touch screen |
| Hold Tab | Fast forward |
| F1 | All controls |
| F2 | Join by address |
| F3 | ONLINE screen (host / join / solo from here too) |
| F4 | Time of day: PC time, morning, day, evening, night |
| F6 | Season: from the PC date, spring, summer, autumn, winter |
| F5 / F8 | Quick-save / quick-load |
| F9 | Screen layout |
| F11 or Alt+Enter | Fullscreen |

Xbox and PlayStation controllers work too, with buttons going by position like on a DS.

- Your save is written to `Pokemon_Black2_Online.sav` when you save in the game.
- In Black 2 the season comes from the month, so F6 moves the game's date. If the season doesn't
  change straight away, soft-reset the game (L + R + START + SELECT).

## Building

You need CMake, a C/C++17 compiler and SDL2. melonDS is downloaded automatically, pinned to the same
commit HeartGold Online used.

```sh
# Linux
cmake -S . -B build && cmake --build build -j
ctest --test-dir build              # mailbox + network tests
tests/e2e_test.sh build/Black2Online # two apps linked over loopback (needs arm-none-eabi-gcc)
```

For Windows, cross-compile from Linux with mingw-w64. Build SDL2 statically for mingw first (SDL's
own CMake with `-DSDL_SHARED=OFF`), then:

```sh
cmake -S . -B build-win -DCMAKE_TOOLCHAIN_FILE=cmake/mingw-w64-x86_64.cmake \
      -DCMAKE_PREFIX_PATH=/path/to/sdl2-mingw-install
cmake --build build-win -j          # build-win/Black2Online.exe, one file, no DLLs to ship
```

## Tests

- `tests/bridge_test.c`: two fake games' RAM, linked through the bridge. It covers state both ways,
  messages in order when the ring is full, PROFILE, unlinking, and finding the mailbox again after
  a reset.
- `tests/net_test.c`: host and join over 127.0.0.1. It covers the handshake, large messages, leaving
  and coming back, and refusing a different game.
- `tests/e2e_test.sh`: the full path. Two copies of the app each boot `tests/testrom`, a tiny DS
  program that plays the game side of the mailbox, in the real emulator. One copy hosts and the
  other joins. It checks that each game sees the other player moving and that link requests get
  answered.

## License

The app links melonDS, so it is GPLv3 like melonDS. SDL2 is under the zlib license. Ship both license
texts with the app. Don't commit ROMs or saves: `.gitignore` keeps them out.
