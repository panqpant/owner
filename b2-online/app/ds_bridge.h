// Services the online mailbox the Black 2 / White 2 ROM keeps in main RAM.
// Same idea as HeartGold Online: the game fills the mailbox, the app moves it over the network.
// The layout itself lives in rom/b2o_mailbox.h, which the game-side code includes too.
#pragma once
#include <stddef.h>
#include <stdint.h>

#include "../rom/b2o_mailbox.h"

/* Network packets between two apps */
#define PKT_HELLO   1
#define PKT_STATE   2
#define PKT_MSG     3
#define PKT_PING    4
#define PKT_BYE     5

typedef void (*DsSendFn)(void *ctx, uint8_t type, const void *data, size_t len);

#define DSB_INQ 64

struct DsBridge {
    uint8_t *ram;
    size_t ramSize;
    long mb;
    int scanCooldown;
    int isHost;
    int connected;
    uint8_t lastSentState[B2O_STATE_SIZE];
    int stateAge;
    int forceState;
    uint8_t peerState[B2O_STATE_SIZE];
    int peerStateNew;
    int peerStateValid;
    struct { uint16_t type, len; uint8_t data[B2O_MSG_MAX]; } inq[DSB_INQ];
    int inqHead, inqTail;
    unsigned long framesWithGame;
    char selfName[24];
    char peerName[24];
    int selfOnMap, peerOnMap, sameMap;
    uint8_t selfProfile[B2O_PROFILE_SIZE], peerProfile[B2O_PROFILE_SIZE];
    int selfProfileValid, peerProfileValid;
};

#ifdef __cplusplus
extern "C" {
#endif
void ds_bridge_init(struct DsBridge *b, uint8_t *ram, size_t size);
void ds_bridge_set_host(struct DsBridge *b, int isHost);
void ds_bridge_set_connected(struct DsBridge *b, int connected);
void ds_bridge_on_packet(struct DsBridge *b, uint8_t type, const uint8_t *data, size_t len);
void ds_bridge_after_frame(struct DsBridge *b, DsSendFn send, void *ctx);
int ds_bridge_found(const struct DsBridge *b);
void ds_decode_name(const uint8_t *src, int maxChars, char *out, size_t outSize);
void ds_bridge_describe(const struct DsBridge *b, char *out, size_t outSize);
#ifdef __cplusplus
}
#endif
