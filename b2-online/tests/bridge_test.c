// Two fake games, each with a mailbox somewhere in its own 4 MB of RAM, linked through two bridges.
#include "../app/ds_bridge.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define RAM_SIZE (4 * 1024 * 1024)

static int failures;
#define CHECK(cond) do { if (!(cond)) { printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); failures++; } } while (0)

struct Side { uint8_t *ram; uint8_t *mb; struct DsBridge bridge; struct Side *other; };

static void wr16(uint8_t *p, uint16_t v) { p[0] = v & 0xFF; p[1] = v >> 8; }
static uint16_t rd16(const uint8_t *p) { return p[0] | p[1] << 8; }

static void send_to_other(void *ctx, uint8_t type, const void *data, size_t len) {
    struct Side *s = ctx;
    ds_bridge_on_packet(&s->other->bridge, type, data, len);
}

static void game_init(struct Side *s, size_t offset) {
    s->ram = calloc(1, RAM_SIZE);
    s->mb = s->ram + offset;
    wr16(s->mb + BMB_MAGIC, B2O_MAGIC & 0xFFFF);
    wr16(s->mb + BMB_MAGIC + 2, B2O_MAGIC >> 16);
    wr16(s->mb + BMB_VERSION, B2O_VERSION);
    ds_bridge_init(&s->bridge, s->ram, RAM_SIZE);
}

static void game_set_state(struct Side *s, const char *name, int map, int x, int y) {
    uint8_t *st = s->mb + BMB_SELF;
    st[BST_VALID] = 1;
    wr16(st + BST_MAP_LO, (uint16_t) map);
    int i = 0;
    for (; name[i] && i < 7; i++)
        wr16(st + BST_NAME + i * 2, (uint8_t) name[i]);
    wr16(st + BST_NAME + i * 2, 0xFFFF);
    uint8_t *e = st + BST_ENTITIES;
    e[BEN_KIND] = 1;
    wr16(e + BEN_X, (uint16_t) x);
    wr16(e + BEN_Y, (uint16_t) y);
    e[BEN_SEQ]++;
}

static void game_send(struct Side *s, uint16_t type, const void *data, uint16_t len) {
    uint8_t head = s->mb[BMB_TXHEAD];
    uint8_t *m = s->mb + BMB_TX + head * B2O_MSG_SLOT_SIZE;
    wr16(m, type);
    wr16(m + 2, len);
    memcpy(m + 4, data, len);
    s->mb[BMB_TXHEAD] = (head + 1) % B2O_RING_SLOTS;
}

static int game_recv(struct Side *s, uint16_t *type, uint8_t *data) {
    uint8_t tail = s->mb[BMB_RXTAIL];
    if (tail == s->mb[BMB_RXHEAD])
        return -1;
    const uint8_t *m = s->mb + BMB_RX + tail * B2O_MSG_SLOT_SIZE;
    *type = rd16(m);
    int len = rd16(m + 2);
    memcpy(data, m + 4, len);
    s->mb[BMB_RXTAIL] = (tail + 1) % B2O_RING_SLOTS;
    return len;
}

static void frame(struct Side *a, struct Side *b) {
    ds_bridge_after_frame(&a->bridge, send_to_other, a);
    ds_bridge_after_frame(&b->bridge, send_to_other, b);
}

int main(void) {
    static struct Side a, b;
    game_init(&a, 0x1A2B40);
    game_init(&b, 0x2FF000);
    a.other = &b;
    b.other = &a;
    CHECK(BMB_SIZE == 8584);

    frame(&a, &b);
    CHECK(ds_bridge_found(&a.bridge) && a.bridge.mb == 0x1A2B40);
    CHECK(ds_bridge_found(&b.bridge) && b.bridge.mb == 0x2FF000);

    /* not linked yet: nothing crosses, and the game's TX ring is drained */
    game_set_state(&a, "Nate", 427, 10, 20);
    uint8_t req[2] = {BREQ_DOUBLE, 1};
    game_send(&a, BMSG_REQUEST, req, 2);
    frame(&a, &b);
    CHECK(a.mb[BMB_TXTAIL] == a.mb[BMB_TXHEAD]);
    CHECK(b.mb[BMB_PEER + BST_VALID] == 0);

    ds_bridge_set_connected(&a.bridge, 1);
    ds_bridge_set_connected(&b.bridge, 1);
    ds_bridge_set_host(&a.bridge, 1);
    game_set_state(&b, "Rosa", 427, 12, 20);
    uint8_t seqBefore = b.mb[BMB_PEERSEQ];
    frame(&a, &b);
    frame(&a, &b);
    CHECK(a.mb[BMB_CONNECTED] == 1 && a.mb[BMB_ISHOST] == 1 && b.mb[BMB_ISHOST] == 0);
    CHECK(b.mb[BMB_PEERSEQ] != seqBefore);
    CHECK(memcmp(b.mb + BMB_PEER, a.mb + BMB_SELF, B2O_STATE_SIZE) == 0);
    CHECK(memcmp(a.mb + BMB_PEER, b.mb + BMB_SELF, B2O_STATE_SIZE) == 0);
    CHECK(strcmp(b.bridge.peerName, "Nate") == 0 && strcmp(a.bridge.peerName, "Rosa") == 0);
    CHECK(a.bridge.sameMap && b.bridge.sameMap);

    /* a step on A shows up on B */
    game_set_state(&a, "Nate", 427, 11, 20);
    frame(&a, &b);
    CHECK(rd16(b.mb + BMB_PEER + BST_ENTITIES + BEN_X) == 11);

    /* different maps */
    game_set_state(&a, "Nate", 428, 0, 0);
    frame(&a, &b);
    CHECK(!b.bridge.sameMap);

    /* messages arrive in order, and the full ring holds back the rest until the game reads */
    for (int i = 0; i < 12; i++) {
        uint8_t data[300];
        memset(data, i, sizeof(data));
        if ((a.mb[BMB_TXHEAD] + 1) % B2O_RING_SLOTS == a.mb[BMB_TXTAIL])
            frame(&a, &b);
        game_send(&a, BMSG_PARTY, data, sizeof(data));
    }
    frame(&a, &b);
    int got = 0;
    for (int round = 0; round < 10; round++) {
        uint16_t type;
        uint8_t data[B2O_MSG_MAX];
        int len;
        while ((len = game_recv(&b, &type, data)) >= 0) {
            CHECK(type == BMSG_PARTY && len == 300 && data[0] == got && data[299] == got);
            got++;
        }
        frame(&a, &b);
    }
    CHECK(got == 12);

    /* PROFILE goes to the ONLINE screen, not into the other game's ring */
    uint8_t prof[B2O_PROFILE_SIZE] = {0};
    wr16(prof + BPR_SPECIES, 497);
    prof[BPR_LEVEL] = 52;
    game_send(&a, BMSG_PROFILE, prof, sizeof(prof));
    frame(&a, &b);
    CHECK(a.bridge.selfProfileValid && b.bridge.peerProfileValid);
    CHECK(rd16(b.bridge.peerProfile + BPR_SPECIES) == 497 && b.bridge.peerProfile[BPR_LEVEL] == 52);
    uint16_t type;
    uint8_t data[B2O_MSG_MAX];
    CHECK(game_recv(&b, &type, data) < 0);

    /* unlinking clears the other player from the game */
    ds_bridge_set_connected(&b.bridge, 0);
    frame(&a, &b);
    CHECK(b.mb[BMB_PEER + BST_VALID] == 0 && b.mb[BMB_CONNECTED] == 0);

    /* the game moving its mailbox (e.g. a reset) is found again */
    memset(a.mb, 0, BMB_SIZE);
    game_init(&a, 0x0C0000);
    a.other = &b;
    for (int i = 0; i < 40; i++)
        frame(&a, &b);
    CHECK(a.bridge.mb == 0x0C0000);

    char desc[300];
    ds_bridge_describe(&b.bridge, desc, sizeof(desc));
    printf("%s\n", desc);
    printf(failures ? "bridge_test: %d FAILED\n" : "bridge_test: all passed\n", failures);
    return failures != 0;
}
