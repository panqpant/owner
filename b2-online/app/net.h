// The link between two apps on the same network.
// The host listens on TCP NET_PORT and answers "who's hosting?" broadcasts on UDP NET_DISCOVERY_PORT.
// A joining app broadcasts until a host answers (or connects straight to an address typed with F2),
// then both sides exchange HELLO and stream packets: u8 type, u16 length (LE), payload.
#pragma once
#include <stddef.h>
#include <stdint.h>

#define NET_PORT            47611
#define NET_DISCOVERY_PORT  47610
#define NET_VERSION         1
#define NET_MAX_PAYLOAD     4096

typedef void (*NetRecvFn)(void *ctx, uint8_t type, const uint8_t *data, size_t len);

enum NetRole { NET_OFF, NET_HOST, NET_JOIN };

struct Net;

#ifdef __cplusplus
extern "C" {
#endif
/* gameCode: the ROM's 4-letter code; both sides must match. */
struct Net *net_create(const char *gameCode);
void net_destroy(struct Net *n);

int net_host(struct Net *n);                    /* 0 on success; net_status says why not */
void net_join(struct Net *n, const char *addr); /* addr NULL or "": find the host by broadcast */
void net_stop(struct Net *n);

/* Call once per frame: accepts, connects, reads and hands complete packets to fn. */
void net_poll(struct Net *n, NetRecvFn fn, void *ctx);
void net_send(struct Net *n, uint8_t type, const void *data, size_t len);

int net_connected(const struct Net *n);
enum NetRole net_role(const struct Net *n);
const char *net_status(const struct Net *n);    /* one line for the screen */
const char *net_peer_addr(const struct Net *n);
/* This PC's LAN addresses, comma separated, for the joining player to type with F2. */
void net_local_addresses(char *out, size_t outSize);
#ifdef __cplusplus
}
#endif
