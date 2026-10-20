# How the two halves talk

Black 2 Online has two halves, just like HeartGold Online:

- **The game side** is code patched into the ROM. It knows where you are, draws the other player, and
  starts battles and trades.
- **The app** is the emulator (melonDS) plus the network link. It never looks inside the game. It
  only moves bytes between the game's mailbox and the other PC.

```
 Game (PC 1)                App (PC 1)                       App (PC 2)                Game (PC 2)
 SELF state  ── mailbox ──▶ ds_bridge ── TCP (net.c) ──▶ ds_bridge ── mailbox ──▶ PEER state
 TX ring     ── mailbox ──▶ ds_bridge ──────────────────▶ ds_bridge ── mailbox ──▶ RX ring
```

## The mailbox (in game RAM)

The exact layout is in [`rom/b2o_mailbox.h`](../rom/b2o_mailbox.h). Both halves include it.

- The game puts an 8,584-byte block anywhere in main RAM. It starts with the magic `"B2ON"` and the
  version number. The app finds the block by scanning RAM, so the patch needs no fixed address. The
  game should write the magic **last**, after the rest of the block is set up.
- The app only touches the block between frames, so the game never sees a half-written value.
- **SELF / PEER (156 bytes each):** valid flag, zone ID, gender, busy flag, season, the player name
  (UTF-16), and 8 entity slots of 16 bytes each. Entity 0 is the player and entity 1 is the walking
  lead Pokémon. Each slot holds position, facing, animation, a step counter, species, form and shiny
  flag.
  - The game writes SELF whenever you move. The app sends it when it changes, or every 30 frames.
  - The app writes the other player's state into PEER and bumps `PEERSEQ`. The game draws from PEER.
- **TX / RX rings:** 8 slots of up to 512 bytes each, for messages. The game writes slot `TXHEAD`
  and advances it. The app sends the slot and advances `TXTAIL`. Receiving works the same way in
  the other direction. When the game stops reading, the ring fills, which holds back the sender.
- **PROFILE (message 10)** carries team, levels, badges, Pokédex counts, play time and zone. The app
  keeps a copy for the ONLINE screen (F3) and doesn't pass it into the other game.

## Battle and trade messages (the game side's plan)

The app forwards these as-is. The order below is the plan for the game-side code.

1. Player presses A facing the other player. Their game sends `REQUEST {kind, level mode}`. The kind
   is single, double, triple, rotation or trade. The level mode is as is, all Lv. 50 or all Lv. 100.
2. The other game asks its player, then sends `ANSWER {1 or 0}`.
3. **Battle:** each side sends its 6 `PARTY` Pokémon (220 bytes each, one per message). The host
   sends `SEED`. Both games then run the same battle in lockstep: each turn, each side sends its
   `BATTLE_INPUT` and waits for the other side's. With the same seed and the same inputs, both games
   compute the same battle.
4. **Trade:** each side sends `TRADE_OFFER {slot, Pokémon}`, then `TRADE_CONFIRM`, then
   `TRADE_DONE`. After a trade, save in the game.
5. Either side can send `CANCEL` at any point.

## The network (app to app)

- The host listens on **TCP 47611** and answers "who's hosting?" broadcasts on **UDP 47610**.
- Join broadcasts `B2ON-FIND` on every network adapter until a host answers. F2 connects straight to
  a typed address instead.
- Packets are `u8 type, u16 length (little-endian), payload`. The types are HELLO, STATE, MSG, PING
  and BYE.
- HELLO carries the app version and the ROM's game code. A mismatch, such as Black 2 against White 2
  or two different regions, is refused with a clear message.
- A link with no traffic for 10 seconds counts as lost. The host goes back to waiting, and the
  joiner keeps retrying.
