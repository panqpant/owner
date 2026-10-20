// Services the mailbox the Black 2 / White 2 ROM keeps in main RAM. Runs between emulated frames,
// so there is never a race with the game.
#include "ds_bridge.h"
#include <stdio.h>
#include <string.h>

static uint32_t rd32(const uint8_t *p) { return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t) p[3] << 24); }
static uint16_t rd16(const uint8_t *p) { return p[0] | (p[1] << 8); }
static void wr16(uint8_t *p, uint16_t v) { p[0] = v & 0xFF; p[1] = v >> 8; }

void ds_bridge_init(struct DsBridge *b, uint8_t *ram, size_t size) {
    memset(b, 0, sizeof(*b));
    b->ram = ram;
    b->ramSize = size;
    b->mb = -1;
}

void ds_bridge_set_host(struct DsBridge *b, int isHost) { b->isHost = isHost; }

void ds_bridge_set_connected(struct DsBridge *b, int connected) {
    if (connected == b->connected)
        return;
    b->connected = connected;
    b->inqHead = b->inqTail = 0;
    b->peerStateValid = 0;
    b->peerStateNew = 1;
    memset(b->peerState, 0, sizeof(b->peerState));
    b->forceState = 1;
    b->peerName[0] = 0;
    b->peerProfileValid = 0;
}

int ds_bridge_found(const struct DsBridge *b) { return b->mb >= 0; }

static int mailbox_ok(struct DsBridge *b, long off) {
    if (off < 0 || (size_t) off + BMB_SIZE > b->ramSize)
        return 0;
    const uint8_t *p = b->ram + off;
    return rd32(p + BMB_MAGIC) == B2O_MAGIC && rd16(p + BMB_VERSION) == B2O_VERSION;
}

static void locate(struct DsBridge *b) {
    if (b->mb >= 0 && mailbox_ok(b, b->mb))
        return;
    b->mb = -1;
    if (b->scanCooldown > 0) {
        b->scanCooldown--;
        return;
    }
    b->scanCooldown = 30;
    if (!b->ram)
        return;
    for (size_t off = 0; off + BMB_SIZE <= b->ramSize; off += 4) {
        if (rd32(b->ram + off) == B2O_MAGIC && mailbox_ok(b, (long) off)) {
            b->mb = (long) off;
            b->forceState = 1;
            return;
        }
    }
}

/* Gen 5 text is UTF-16, so plain ASCII maps straight across. */
void ds_decode_name(const uint8_t *src, int maxChars, char *out, size_t outSize) {
    size_t n = 0;
    for (int i = 0; i < maxChars && n + 1 < outSize; i++) {
        uint16_t c = rd16(src + i * 2);
        if (c == 0xFFFF || c == 0)
            break;
        out[n++] = (c >= 0x20 && c < 0x7F) ? (char) c : '?';
    }
    out[n] = 0;
}

void ds_bridge_on_packet(struct DsBridge *b, uint8_t type, const uint8_t *data, size_t len) {
    switch (type) {
    case PKT_STATE:
        if (len >= B2O_STATE_SIZE) {
            memcpy(b->peerState, data, B2O_STATE_SIZE);
            b->peerStateNew = 1;
            b->peerStateValid = 1;
            ds_decode_name(b->peerState + BST_NAME, 8, b->peerName, sizeof(b->peerName));
        }
        break;
    case PKT_MSG:
        if (len >= 4) {
            uint16_t mtype = rd16(data), mlen = rd16(data + 2);
            if (mlen > B2O_MSG_MAX || mlen + 4u > len)
                break;
            if (mtype == BMSG_PROFILE) {
                /* only for the app's ONLINE screen; the game doesn't need it */
                if (mlen >= B2O_PROFILE_SIZE) {
                    memcpy(b->peerProfile, data + 4, B2O_PROFILE_SIZE);
                    b->peerProfileValid = 1;
                }
                break;
            }
            int next = (b->inqHead + 1) % DSB_INQ;
            if (next == b->inqTail)
                break; /* overflow: the game applies back-pressure, so this shouldn't happen */
            b->inq[b->inqHead].type = mtype;
            b->inq[b->inqHead].len = mlen;
            memcpy(b->inq[b->inqHead].data, data + 4, mlen);
            b->inqHead = next;
        }
        break;
    }
}

void ds_bridge_after_frame(struct DsBridge *b, DsSendFn send, void *ctx) {
    locate(b);
    if (b->mb < 0)
        return;
    uint8_t *mb = b->ram + b->mb;
    b->framesWithGame++;

    mb[BMB_HEARTBEAT]++;
    mb[BMB_ISHOST] = (uint8_t) b->isHost;
    mb[BMB_CONNECTED] = (uint8_t) b->connected;

    const uint8_t *self = mb + BMB_SELF;
    ds_decode_name(self + BST_NAME, 8, b->selfName, sizeof(b->selfName));
    b->selfOnMap = self[BST_VALID];

    if (!b->connected) {
        mb[BMB_TXTAIL] = mb[BMB_TXHEAD];
        if (mb[BMB_PEER + BST_VALID]) {
            memset(mb + BMB_PEER, 0, B2O_STATE_SIZE);
            mb[BMB_PEERSEQ]++;
        }
        b->peerOnMap = b->sameMap = 0;
        return;
    }

    b->stateAge++;
    if (b->forceState || b->stateAge >= 30 || memcmp(self, b->lastSentState, B2O_STATE_SIZE) != 0) {
        memcpy(b->lastSentState, self, B2O_STATE_SIZE);
        send(ctx, PKT_STATE, self, B2O_STATE_SIZE);
        b->stateAge = 0;
        b->forceState = 0;
    }

    while (mb[BMB_TXTAIL] != mb[BMB_TXHEAD]) {
        uint8_t slot = mb[BMB_TXTAIL] % B2O_RING_SLOTS;
        const uint8_t *m = mb + BMB_TX + slot * B2O_MSG_SLOT_SIZE;
        uint16_t len = rd16(m + 2);
        if (len > B2O_MSG_MAX) len = B2O_MSG_MAX;
        if (rd16(m) == BMSG_PROFILE && len >= B2O_PROFILE_SIZE) {
            memcpy(b->selfProfile, m + 4, B2O_PROFILE_SIZE);
            b->selfProfileValid = 1;
        }
        send(ctx, PKT_MSG, m, 4 + len);
        mb[BMB_TXTAIL] = (uint8_t) ((mb[BMB_TXTAIL] + 1) % B2O_RING_SLOTS);
    }

    while (b->inqTail != b->inqHead) {
        uint8_t head = mb[BMB_RXHEAD];
        uint8_t next = (uint8_t) ((head + 1) % B2O_RING_SLOTS);
        if (next == mb[BMB_RXTAIL])
            break;
        uint8_t *m = mb + BMB_RX + head * B2O_MSG_SLOT_SIZE;
        wr16(m, b->inq[b->inqTail].type);
        wr16(m + 2, b->inq[b->inqTail].len);
        memcpy(m + 4, b->inq[b->inqTail].data, b->inq[b->inqTail].len);
        mb[BMB_RXHEAD] = next;
        b->inqTail = (b->inqTail + 1) % DSB_INQ;
    }

    if (b->peerStateNew) {
        memcpy(mb + BMB_PEER, b->peerState, B2O_STATE_SIZE);
        mb[BMB_PEERSEQ]++;
        b->peerStateNew = 0;
    }
    b->peerOnMap = b->peerState[BST_VALID];
    b->sameMap = b->peerOnMap && b->selfOnMap
        && self[BST_MAP_LO] == b->peerState[BST_MAP_LO] && self[BST_MAP_HI] == b->peerState[BST_MAP_HI];
}

void ds_bridge_describe(const struct DsBridge *b, char *out, size_t outSize) {
    if (b->mb < 0) {
        snprintf(out, outSize, "mailbox not found");
        return;
    }
    const uint8_t *mb = b->ram + b->mb;
    const uint8_t *s = mb + BMB_SELF;
    const uint8_t *e = s + BST_ENTITIES;
    snprintf(out, outSize,
             "mb@%06lx self valid=%d map=%d busy=%d name=%s pos(%d,%d) seq=%d | peer valid=%d name=%s map=%d same=%d tx=%d/%d rx=%d/%d",
             b->mb, s[BST_VALID], s[BST_MAP_LO] | s[BST_MAP_HI] << 8, s[BST_BUSY], b->selfName,
             (int16_t) rd16(e + 2), (int16_t) rd16(e + 4), e[9],
             mb[BMB_PEER + BST_VALID], b->peerName, mb[BMB_PEER + BST_MAP_LO] | mb[BMB_PEER + BST_MAP_HI] << 8, b->sameMap,
             mb[BMB_TXHEAD], mb[BMB_TXTAIL], mb[BMB_RXHEAD], mb[BMB_RXTAIL]);
}
