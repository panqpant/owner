// The online mailbox: a block of main RAM shared by the patched Black 2 / White 2 ROM and the app.
// This header is the contract between the two sides. The app (app/ds_bridge.c) and the game-side
// code both include it, so change it in one place and bump B2O_VERSION.
//
// The game allocates the block anywhere in main RAM (4-byte aligned) and writes B2O_MAGIC and
// B2O_VERSION at the start. The app scans RAM for the magic, so no fixed address is needed.
// The app only touches the mailbox between emulated frames, so the game never sees a half write.
//
// All values are little-endian. Offsets are byte offsets from the start of the block.
#pragma once

#define B2O_MAGIC          0x4E4F3242u  /* "B2ON" in game memory */
#define B2O_VERSION        1
#define B2O_MSG_MAX        512
#define B2O_RING_SLOTS     8
#define B2O_STATE_SIZE     156
#define B2O_MSG_SLOT_SIZE  516          /* u16 type, u16 len, then up to B2O_MSG_MAX bytes */

/* Mailbox header. Who writes each field: [G] game, [A] app. */
#define BMB_MAGIC      0x00  /* u32 [G] B2O_MAGIC */
#define BMB_VERSION    0x04  /* u16 [G] B2O_VERSION */
#define BMB_HEARTBEAT  0x06  /* u8  [A] +1 every frame the app services the mailbox */
#define BMB_CONNECTED  0x07  /* u8  [A] 1 while linked to the other player */
#define BMB_ISHOST     0x08  /* u8  [A] 1 on the host */
#define BMB_TXHEAD     0x09  /* u8  [G] game -> app ring: game writes slot TXHEAD, then advances it */
#define BMB_TXTAIL     0x0A  /* u8  [A] app advances it after sending a slot */
#define BMB_RXHEAD     0x0B  /* u8  [A] app -> game ring: app writes slot RXHEAD, then advances it */
#define BMB_RXTAIL     0x0C  /* u8  [G] game advances it after reading a slot */
#define BMB_PEERSEQ    0x0D  /* u8  [A] +1 whenever the PEER state changes */
#define BMB_SELFSEQ    0x0E  /* u8  [G] free for the game */
#define BMB_SELF       0x10  /* [G] this player's state (B2O_STATE_SIZE bytes) */
#define BMB_PEER       (BMB_SELF + B2O_STATE_SIZE)                          /* [A] other player's state */
#define BMB_TX         (BMB_PEER + B2O_STATE_SIZE)                          /* [G] B2O_RING_SLOTS message slots */
#define BMB_RX         (BMB_TX + B2O_RING_SLOTS * B2O_MSG_SLOT_SIZE)        /* [A] B2O_RING_SLOTS message slots */
#define BMB_SIZE       (BMB_RX + B2O_RING_SLOTS * B2O_MSG_SLOT_SIZE)        /* 8584 bytes */

/* A player state (156 bytes). The app sends SELF whenever it changes (and every 30 frames)
   and copies what arrives into PEER. */
#define BST_VALID      0   /* u8  1 while the player is on a map the other side can show */
#define BST_MAP_LO     1   /* u16 zone ID */
#define BST_MAP_HI     2
#define BST_GENDER     3   /* u8  0 boy (Nate), 1 girl (Rosa) */
#define BST_BUSY       4   /* u8  1 in a battle, menu, cutscene...: don't offer to link */
#define BST_SEASON     5   /* u8  0 spring, 1 summer, 2 autumn, 3 winter */
#define BST_NAME       12  /* 8 x u16, Gen 5 text (UTF-16), 0xFFFF-terminated */
#define BST_ENTITIES   28  /* B2O_ENTITIES x B2O_ENTITY_SIZE */

#define B2O_ENTITIES     8
#define B2O_ENTITY_SIZE  16
#define BEN_KIND     0   /* u8  0 none, 1 player, 2 walking Pokemon */
#define BEN_FACING   1   /* u8  0 up, 1 down, 2 left, 3 right */
#define BEN_X        2   /* s16 tile X */
#define BEN_Y        4   /* s16 tile Z (the "Y" on the map grid) */
#define BEN_H        6   /* s16 height (Gen 5 maps have elevation) */
#define BEN_ANIM     8   /* u8  0 stand, 1 walk, 2 run, 3 bike, 4 surf */
#define BEN_SEQ      9   /* u8  +1 per step, so the other side can play every step */
#define BEN_SPECIES  10  /* u16 national dex number (walking Pokemon) */
#define BEN_FORM     12  /* u8 */
#define BEN_FLAGS    13  /* u8  bit 0 shiny, bit 1 female */
/* entity 0 is the player, entity 1 is their walking lead Pokemon, the rest are reserved */

/* Message types inside the rings. The app forwards every message as-is, except PROFILE, which it
   also keeps for the ONLINE screen (F3). The battle and trade messages are the game side's
   business; see docs/PROTOCOL.md for how they are meant to be used. */
#define BMSG_REQUEST        1   /* u8 kind (BREQ_*), u8 level mode (0 as is, 1 all Lv. 50, 2 all Lv. 100) */
#define BMSG_ANSWER         2   /* u8 1 accept, 0 decline */
#define BMSG_CANCEL         3
#define BMSG_PARTY          4   /* u8 slot, u8 count, then one 220-byte party Pokemon */
#define BMSG_SEED           5   /* u32 battle RNG seed, sent by the host */
#define BMSG_BATTLE_INPUT   6   /* u16 turn, then that player's choices for the turn */
#define BMSG_TRADE_OFFER    7   /* u8 slot, then one 220-byte party Pokemon */
#define BMSG_TRADE_CONFIRM  8   /* u8 1 yes, 0 no */
#define BMSG_TRADE_DONE     9
#define BMSG_PROFILE        10  /* game -> app: B2O_PROFILE_SIZE bytes, see below */

#define BREQ_SINGLE    1
#define BREQ_DOUBLE    2
#define BREQ_TRIPLE    3
#define BREQ_ROTATION  4
#define BREQ_TRADE     5

/* PROFILE message payload (36 bytes), sent by the game when any of it changes */
#define B2O_PROFILE_SIZE  36
#define BPR_SPECIES    0   /* 6 x u16 national dex number, 0 = empty slot */
#define BPR_LEVEL      12  /* 6 x u8 */
#define BPR_BADGES     18  /* u8 bit per badge */
#define BPR_GENDER     19  /* u8 */
#define BPR_DEX_SEEN   20  /* u16 */
#define BPR_DEX_CAUGHT 22  /* u16 */
#define BPR_HOURS      24  /* u16 play time */
#define BPR_MINUTES    26  /* u8 */
#define BPR_SEASON     27  /* u8 */
#define BPR_MAP        28  /* u16 zone ID */
#define BPR_PARTY      30  /* u8 number of Pokemon in the party */
