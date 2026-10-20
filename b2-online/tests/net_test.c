// A host and a joiner in one process, linked over 127.0.0.1.
#include "../app/ds_bridge.h"
#include "../app/net.h"

#include <stdio.h>
#include <string.h>
#include <time.h>
#ifdef _WIN32
#include <windows.h>
static void nap(void) { Sleep(5); }
#else
#include <unistd.h>
static void nap(void) { usleep(5000); }
#endif

static int failures;
#define CHECK(cond) do { if (!(cond)) { printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond); failures++; } } while (0)

struct Got { int count; uint8_t type; uint8_t data[NET_MAX_PAYLOAD]; size_t len; };

static void on_recv(void *ctx, uint8_t type, const uint8_t *data, size_t len) {
    struct Got *g = ctx;
    g->count++;
    g->type = type;
    g->len = len;
    memcpy(g->data, data, len);
}

static int pump_until(struct Net *a, struct Got *ga, struct Net *b, struct Got *gb, int (*done)(void *), void *arg) {
    for (int i = 0; i < 1000; i++) {
        net_poll(a, on_recv, ga);
        net_poll(b, on_recv, gb);
        if (done(arg))
            return 1;
        nap();
    }
    return 0;
}

static struct Net *H, *J;
static int both_connected(void *unused) { (void) unused; return net_connected(H) && net_connected(J); }
static int got_one(void *g) { return ((struct Got *) g)->count > 0; }
static int join_gave_up(void *unused) { (void) unused; return !net_connected(J) && strstr(net_status(J), "different game") != NULL; }

int main(void) {
    static struct Got gh, gj;
    H = net_create("IREO");
    J = net_create("IREO");
    CHECK(net_host(H) == 0);
    net_join(J, "127.0.0.1");
    CHECK(pump_until(H, &gh, J, &gj, both_connected, NULL));
    printf("host: %s | join: %s\n", net_status(H), net_status(J));

    uint8_t state[B2O_STATE_SIZE];
    for (int i = 0; i < B2O_STATE_SIZE; i++)
        state[i] = (uint8_t) i;
    net_send(J, PKT_STATE, state, sizeof(state));
    CHECK(pump_until(H, &gh, J, &gj, got_one, &gh));
    CHECK(gh.type == PKT_STATE && gh.len == sizeof(state) && memcmp(gh.data, state, sizeof(state)) == 0);

    /* a big message both ways */
    uint8_t msg[4 + B2O_MSG_MAX];
    memset(msg, 0xAB, sizeof(msg));
    gh.count = gj.count = 0;
    net_send(H, PKT_MSG, msg, sizeof(msg));
    CHECK(pump_until(H, &gh, J, &gj, got_one, &gj));
    CHECK(gj.type == PKT_MSG && gj.len == sizeof(msg) && gj.data[515] == 0xAB);

    /* the joiner leaves; the host goes back to waiting and takes them back */
    net_stop(J);
    for (int i = 0; i < 100 && net_connected(H); i++) {
        net_poll(H, on_recv, &gh);
        nap();
    }
    CHECK(!net_connected(H));
    net_join(J, "127.0.0.1");
    CHECK(pump_until(H, &gh, J, &gj, both_connected, NULL));

    /* a different game is turned away, and the joiner stops retrying */
    net_destroy(J);
    J = net_create("IRDO");
    for (int i = 0; i < 100 && net_connected(H); i++) {
        net_poll(H, on_recv, &gh);
        nap();
    }
    net_join(J, "127.0.0.1");
    CHECK(pump_until(H, &gh, J, &gj, join_gave_up, NULL));
    printf("mismatch: %s\n", net_status(J));

    char addrs[200];
    net_local_addresses(addrs, sizeof(addrs));
    printf("local addresses: %s\n", addrs);

    net_destroy(J);
    net_destroy(H);
    printf(failures ? "net_test: %d FAILED\n" : "net_test: all passed\n", failures);
    return failures != 0;
}
