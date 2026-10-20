// A stand-in for the patched game: keeps a mailbox in main RAM exactly as rom/b2o_mailbox.h says,
// walks a "player" left and right, draws where the other player is, and answers link requests.
// Used by tests/e2e_test.sh to check the whole path (game RAM -> app -> network -> other app -> game RAM).
#include <stdint.h>
#include "../../rom/b2o_mailbox.h"

#define REG(a) (*(volatile uint32_t *) (a))
#define REG16(a) (*(volatile uint16_t *) (a))
#define VCOUNT REG16(0x04000006)
#define VRAM ((volatile uint16_t *) 0x06800000)
#define MB ((volatile uint8_t *) 0x02300000)

static void wr16(volatile uint8_t *p, uint16_t v) { p[0] = v & 0xFF; p[1] = v >> 8; }
static uint16_t rd16(volatile const uint8_t *p) { return p[0] | p[1] << 8; }

static void rect(int x, int y, int w, int h, uint16_t c) {
    for (int j = y; j < y + h; j++)
        for (int i = x; i < x + w; i++)
            if (i >= 0 && i < 256 && j >= 0 && j < 192)
                VRAM[j * 256 + i] = c;
}

static void send(uint16_t type, const uint8_t *data, uint16_t len) {
    uint8_t head = MB[BMB_TXHEAD];
    if ((head + 1) % B2O_RING_SLOTS == MB[BMB_TXTAIL])
        return;
    volatile uint8_t *m = MB + BMB_TX + head * B2O_MSG_SLOT_SIZE;
    wr16(m, type);
    wr16(m + 2, len);
    for (int i = 0; i < len; i++)
        m[4 + i] = data[i];
    MB[BMB_TXHEAD] = (head + 1) % B2O_RING_SLOTS;
}

int main(void) {
    REG16(0x04000304) = 0x8003;       /* both LCDs and 2D engine A on */
    *(volatile uint8_t *) 0x04000240 = 0x80; /* VRAM A for the LCD controller */
    REG(0x04000000) = 0x00020000;     /* display VRAM A directly */

    for (int i = 0; i < BMB_SIZE; i++)
        MB[i] = 0;
    wr16(MB + BMB_VERSION, B2O_VERSION);
    volatile uint8_t *self = MB + BMB_SELF;
    self[BST_VALID] = 1;
    wr16(self + BST_MAP_LO, 427);
    const char *name = "Tester";
    int n = 0;
    for (; name[n]; n++)
        wr16(self + BST_NAME + n * 2, (uint8_t) name[n]);
    wr16(self + BST_NAME + n * 2, 0xFFFF);
    volatile uint8_t *ent = self + BST_ENTITIES;
    ent[BEN_KIND] = 1;
    /* the magic goes in last, so the app never finds a half-built mailbox */
    MB[0] = B2O_MAGIC & 0xFF; MB[1] = (B2O_MAGIC >> 8) & 0xFF; MB[2] = (B2O_MAGIC >> 16) & 0xFF; MB[3] = B2O_MAGIC >> 24;

    int x = 0, dir = 1, frame = 0, answered = 0, lastX = 0, lastPeerX = -100;
    uint16_t lastBg = 0xFFFF;
    for (;;) {
        while (VCOUNT != 192) {}
        frame++;
        if (frame % 4 == 0) {
            x += dir;
            if (x <= 0 || x >= 240) dir = -dir;
            wr16(ent + BEN_X, (uint16_t) x);
            ent[BEN_SEQ]++;
        }
        /* answer every request, and count what came in */
        while (MB[BMB_RXTAIL] != MB[BMB_RXHEAD]) {
            volatile uint8_t *m = MB + BMB_RX + MB[BMB_RXTAIL] * B2O_MSG_SLOT_SIZE;
            if (rd16(m) == BMSG_REQUEST) {
                uint8_t yes = 1;
                send(BMSG_ANSWER, &yes, 1);
            } else if (rd16(m) == BMSG_ANSWER) {
                answered++;
            }
            MB[BMB_RXTAIL] = (MB[BMB_RXTAIL] + 1) % B2O_RING_SLOTS;
        }
        /* the host asks once a second while linked */
        if (MB[BMB_CONNECTED] && MB[BMB_ISHOST] && frame % 60 == 0) {
            uint8_t req[2] = {BREQ_SINGLE, 0};
            send(BMSG_REQUEST, req, 2);
        }
        MB[BMB_SELFSEQ] = (uint8_t) answered;

        /* redraw only what moved: the full screen is too slow to fill every frame from uncached RAM */
        uint16_t bg = MB[BMB_CONNECTED] ? 0x1940 /* dark green */ : 0x2880 /* dark blue */;
        if (bg != lastBg) {
            rect(0, 0, 256, 192, bg);
            lastBg = bg;
        }
        rect(lastX, 40, 16, 16, bg);
        rect(x, 40, 16, 16, 0x7FFF);  /* me: white */
        lastX = x;
        volatile uint8_t *peer = MB + BMB_PEER;
        int px = peer[BST_VALID] ? (int16_t) rd16(peer + BST_ENTITIES + BEN_X) : -100;
        rect(lastPeerX, 120, 16, 16, bg);
        rect(px, 120, 16, 16, 0x001F); /* them: red */
        lastPeerX = px;
        for (int i = 0; i < answered && i < 30; i++)
            rect(4 + i * 8, 180, 6, 6, 0x03FF); /* one yellow pip per answered request */
        while (VCOUNT == 192) {}
    }
}
