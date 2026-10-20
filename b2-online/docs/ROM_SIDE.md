# The game side: plan and status

The app is finished and tested. The game side, the patch inside the Black 2 ROM, has **not been
started yet**. It needs the ROM: every hook means finding the right routine and memory address in
Black 2 itself, and none of that can be guessed.

Black 2 is a much bigger job than HeartGold was, for three reasons:

- **No followers in the engine.** HeartGold has walking Pokémon built in. Black 2 doesn't, so the
  follower has to be built from scratch: an extra map object, the code that makes it trail behind
  you, and handling for stairs, bridges, surfing and cutscenes.
- **No sprites for most Pokémon.** Gen 5 only has overworld sprites for the few Pokémon that appear
  on maps in the story. Walking Pokémon need sprites for all 649. For #1–493, HeartGold's follower
  sprites can be converted, and the HeartGold ROM is the source for those. #494–649 need new art,
  either fan-made sprite sheets with credit or drawn from scratch.
- **No decompilation.** HeartGold has a mature community decompilation, which turns the game back
  into readable C code. Black 2's equivalent is far behind, so most hooks are assembly patches at
  addresses found by hand.

## How the patch gets built

- Unpack the ROM with `ndstool`. Put the new code in a new overlay, or in free space at the end of
  ARM9 RAM.
- The new code is C, built with `arm-none-eabi-gcc` the same way as `tests/testrom`. Branch patches
  hook it into the game.
- A script applies everything to a clean ROM and writes `Pokemon_Black2_Online.bps`, so nobody has to
  share the ROM itself.

## Milestones

Each milestone is something you can play-test on two PCs.

1. **Mailbox and your own state.** Allocate the mailbox and fill SELF every frame: zone, position,
   facing, name, gender, season, busy flag. Send PROFILE when the team changes.
   *Test:* F3 on the other PC shows your name, team, badges and zone.
2. **See each other.** When PEER is on the same zone, spawn a map object with Nate's or Rosa's
   sprite and walk it along the steps in PEER. Remove it when they leave.
   *Test:* you see each other walking around.
3. **Walking Pokémon.** Your lead Pokémon follows you, and the other player's walks behind them.
   This includes the sprite import above.
4. **Battle and trade.** Pressing A on the other player opens Battle / Double / Triple / Rotation /
   Trade and a level choice. These run over the messages in [PROTOCOL.md](PROTOCOL.md).
   - A shortcut worth trying first: Black 2 already has local wireless battles and trades (Union
     Room, C-Gear). melonDS can emulate DS-to-DS wireless, so routing that over this app's link
     could make the game's own battle and trade code work unchanged.
5. **Wild Pokémon walking around, no random encounters.** Turn off grass, cave and water encounter
   rolls (fishing and dust clouds stay). Spawn a few wild Pokémon as map objects from that area's
   encounter table, by season and time of day. Walking into one starts that battle.
6. **The extras HeartGold Online had.** A new spread of wild Pokémon, trade evolutions by level,
   evolution items in shops, Exp. Share for the whole team, level caps, reusable TMs (already true
   in Gen 5) and faster text. These are mostly table edits, and much easier than milestones 2–5.

## What's needed to start

- **The Black 2 ROM:** say which region it is (USA is game code `IREO`). The app checks the code, and
  both PCs have to use the same file.
- **The HeartGold ROM:** only for the follower sprites in milestone 3.
- Someone to play-test each milestone on two PCs and report what goes wrong. The app's headless test
  mode, `--test-frames`, can boot the game and print what the mailbox holds, but it can't play it.
