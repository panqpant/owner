// See net.h. Everything is non-blocking and driven by net_poll, so the app never stalls on the network.
#include "net.h"
#include "ds_bridge.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#include <iphlpapi.h>
typedef SOCKET sock_t;
#define BAD_SOCK INVALID_SOCKET
#define sock_close closesocket
#define sock_err() WSAGetLastError()
#define ERR_WOULDBLOCK WSAEWOULDBLOCK
#define ERR_INPROGRESS WSAEWOULDBLOCK
#define SEND_FLAGS 0
#else
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <ifaddrs.h>
#include <net/if.h>
#include <netdb.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <sys/socket.h>
#include <unistd.h>
typedef int sock_t;
#define BAD_SOCK (-1)
#define sock_close close
#define sock_err() errno
#define ERR_WOULDBLOCK EWOULDBLOCK
#define ERR_INPROGRESS EINPROGRESS
#ifdef MSG_NOSIGNAL
#define SEND_FLAGS MSG_NOSIGNAL /* a closed link is an error code, not a crash */
#else
#define SEND_FLAGS 0
#endif
#endif

#define FIND_MSG  "B2ON-FIND"
#define HOST_MSG  "B2ON-HOST"
#define BUF_SIZE  (256 * 1024)
#define PING_MS   1000
#define DEAD_MS   10000
#define RETRY_MS  1000

struct Net {
    char gameCode[5];
    enum NetRole role;
    sock_t listener, udp, conn;
    int connecting;          /* conn is a connect() still in progress */
    int helloOk;             /* the other side's HELLO matched ours */
    int gaveUp;              /* joining: the host is a different game or version, stop retrying */
    char joinAddr[64];       /* "" = find by broadcast */
    struct sockaddr_in target;
    int haveTarget;
    uint8_t rx[BUF_SIZE];
    size_t rxLen;
    uint8_t tx[BUF_SIZE];
    size_t txLen;
    long long lastRecv, lastSend, lastTry;
    char status[160];
    char peerAddr[64];
};

static long long now_ms(void) {
#ifdef _WIN32
    return (long long) GetTickCount64();
#else
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long long) ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
#endif
}

static void set_nonblocking(sock_t s) {
#ifdef _WIN32
    u_long one = 1;
    ioctlsocket(s, FIONBIO, &one);
#else
    fcntl(s, F_SETFL, fcntl(s, F_GETFL, 0) | O_NONBLOCK);
#endif
}

static void set_status(struct Net *n, const char *fmt, const char *arg) {
    snprintf(n->status, sizeof(n->status), fmt, arg ? arg : "");
}

static void close_sock(sock_t *s) {
    if (*s != BAD_SOCK) {
        sock_close(*s);
        *s = BAD_SOCK;
    }
}

struct Net *net_create(const char *gameCode) {
#ifdef _WIN32
    static int wsaStarted;
    if (!wsaStarted) {
        WSADATA wsa;
        WSAStartup(MAKEWORD(2, 2), &wsa);
        wsaStarted = 1;
    }
#endif
    struct Net *n = (struct Net *) calloc(1, sizeof(struct Net));
    if (!n)
        return NULL;
    snprintf(n->gameCode, sizeof(n->gameCode), "%s", gameCode ? gameCode : "");
    n->listener = n->udp = n->conn = BAD_SOCK;
    set_status(n, "Playing solo", NULL);
    return n;
}

static void drop_conn(struct Net *n, const char *why) {
    if (n->conn != BAD_SOCK && n->helloOk) {
        uint8_t bye[3] = {PKT_BYE, 0, 0};
        send(n->conn, (const char *) bye, 3, SEND_FLAGS);
    }
    close_sock(&n->conn);
    n->connecting = n->helloOk = 0;
    n->rxLen = n->txLen = 0;
    n->peerAddr[0] = 0;
    n->lastTry = now_ms();
    if (n->role == NET_JOIN && !n->joinAddr[0])
        n->haveTarget = 0; /* look for the host again */
    if (why)
        set_status(n, "%s", why);
}

void net_stop(struct Net *n) {
    drop_conn(n, NULL);
    close_sock(&n->listener);
    close_sock(&n->udp);
    n->role = NET_OFF;
    set_status(n, "Playing solo", NULL);
}

void net_destroy(struct Net *n) {
    if (!n)
        return;
    net_stop(n);
    free(n);
}

int net_host(struct Net *n) {
    net_stop(n);
    n->role = NET_HOST;
    int one = 1;
    struct sockaddr_in a;
    memset(&a, 0, sizeof(a));
    a.sin_family = AF_INET;
    a.sin_addr.s_addr = htonl(INADDR_ANY);

    n->listener = socket(AF_INET, SOCK_STREAM, 0);
    if (n->listener == BAD_SOCK)
        goto fail;
    setsockopt(n->listener, SOL_SOCKET, SO_REUSEADDR, (const char *) &one, sizeof(one));
    a.sin_port = htons(NET_PORT);
    if (bind(n->listener, (struct sockaddr *) &a, sizeof(a)) != 0 || listen(n->listener, 2) != 0)
        goto fail;
    set_nonblocking(n->listener);

    n->udp = socket(AF_INET, SOCK_DGRAM, 0);
    if (n->udp != BAD_SOCK) {
        setsockopt(n->udp, SOL_SOCKET, SO_REUSEADDR, (const char *) &one, sizeof(one));
        a.sin_port = htons(NET_DISCOVERY_PORT);
        if (bind(n->udp, (struct sockaddr *) &a, sizeof(a)) == 0)
            set_nonblocking(n->udp);
        else
            close_sock(&n->udp); /* joining by address (F2) still works */
    }
    set_status(n, "Hosting - waiting for the other player", NULL);
    return 0;
fail:
    close_sock(&n->listener);
    n->role = NET_OFF;
    set_status(n, "Couldn't host: port %s is in use (is the app already open?)", "47611");
    return -1;
}

static int parse_addr(const char *text, struct sockaddr_in *out) {
    char host[64];
    int port = NET_PORT;
    snprintf(host, sizeof(host), "%s", text);
    char *colon = strchr(host, ':');
    if (colon) {
        *colon = 0;
        port = atoi(colon + 1);
    }
    memset(out, 0, sizeof(*out));
    out->sin_family = AF_INET;
    out->sin_port = htons((uint16_t) port);
    if (inet_pton(AF_INET, host, &out->sin_addr) == 1)
        return 1;
    struct addrinfo hints, *res = NULL;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_INET;
    if (getaddrinfo(host, NULL, &hints, &res) != 0 || !res)
        return 0;
    out->sin_addr = ((struct sockaddr_in *) res->ai_addr)->sin_addr;
    freeaddrinfo(res);
    return 1;
}

void net_join(struct Net *n, const char *addr) {
    net_stop(n);
    n->role = NET_JOIN;
    snprintf(n->joinAddr, sizeof(n->joinAddr), "%s", addr ? addr : "");
    n->gaveUp = 0;
    n->haveTarget = 0;
    n->lastTry = 0;
    if (n->joinAddr[0]) {
        if (!parse_addr(n->joinAddr, &n->target)) {
            set_status(n, "Can't read the address \"%s\"", n->joinAddr);
            return;
        }
        n->haveTarget = 1;
        set_status(n, "Connecting to %s", n->joinAddr);
    } else {
        int one = 1;
        n->udp = socket(AF_INET, SOCK_DGRAM, 0);
        if (n->udp != BAD_SOCK) {
            setsockopt(n->udp, SOL_SOCKET, SO_BROADCAST, (const char *) &one, sizeof(one));
            set_nonblocking(n->udp);
        }
        set_status(n, "Looking for the host on this network...", NULL);
    }
}

static void queue(struct Net *n, uint8_t type, const void *data, size_t len) {
    if (len > NET_MAX_PAYLOAD || n->txLen + 3 + len > BUF_SIZE)
        return; /* only happens if the link stalls for many seconds; the dead-link timer handles that */
    uint8_t *p = n->tx + n->txLen;
    p[0] = type;
    p[1] = (uint8_t) (len & 0xFF);
    p[2] = (uint8_t) (len >> 8);
    if (len)
        memcpy(p + 3, data, len);
    n->txLen += 3 + len;
}

static void send_hello(struct Net *n) {
    uint8_t h[10];
    memcpy(h, "B2ON", 4);
    h[4] = NET_VERSION & 0xFF;
    h[5] = NET_VERSION >> 8;
    memcpy(h + 6, n->gameCode, 4);
    queue(n, PKT_HELLO, h, sizeof(h));
}

static void on_connected(struct Net *n, const struct sockaddr_in *peer) {
    int one = 1;
    setsockopt(n->conn, IPPROTO_TCP, TCP_NODELAY, (const char *) &one, sizeof(one));
    set_nonblocking(n->conn);
    inet_ntop(AF_INET, &peer->sin_addr, n->peerAddr, sizeof(n->peerAddr));
    n->rxLen = n->txLen = 0;
    n->helloOk = 0;
    n->lastRecv = n->lastSend = now_ms();
    send_hello(n);
    set_status(n, "Saying hello to %s...", n->peerAddr);
}

static void host_poll(struct Net *n) {
    /* answer "who's hosting?" */
    if (n->udp != BAD_SOCK) {
        char buf[64];
        struct sockaddr_in from;
        socklen_t fromLen = sizeof(from);
        int r;
        while ((r = recvfrom(n->udp, buf, sizeof(buf) - 1, 0, (struct sockaddr *) &from, &fromLen)) > 0) {
            buf[r] = 0;
            if (strncmp(buf, FIND_MSG, strlen(FIND_MSG)) == 0) {
                char reply[64];
                int len = snprintf(reply, sizeof(reply), "%s %d %s", HOST_MSG, NET_PORT, n->gameCode);
                sendto(n->udp, reply, len, 0, (struct sockaddr *) &from, fromLen);
            }
            fromLen = sizeof(from);
        }
    }
    struct sockaddr_in peer;
    socklen_t peerLen = sizeof(peer);
    sock_t s = accept(n->listener, (struct sockaddr *) &peer, &peerLen);
    if (s == BAD_SOCK)
        return;
    if (n->conn != BAD_SOCK) {
        sock_close(s); /* already playing with someone */
        return;
    }
    n->conn = s;
    on_connected(n, &peer);
}

static void broadcast_find(struct Net *n) {
    struct sockaddr_in to;
    memset(&to, 0, sizeof(to));
    to.sin_family = AF_INET;
    to.sin_port = htons(NET_DISCOVERY_PORT);
    to.sin_addr.s_addr = htonl(INADDR_BROADCAST);
    sendto(n->udp, FIND_MSG, (int) strlen(FIND_MSG), 0, (struct sockaddr *) &to, sizeof(to));
    /* 255.255.255.255 doesn't leave every adapter on Windows, so also try each subnet's own broadcast */
#ifdef _WIN32
    ULONG size = 16384;
    IP_ADAPTER_ADDRESSES *list = (IP_ADAPTER_ADDRESSES *) malloc(size);
    if (list && GetAdaptersAddresses(AF_INET, GAA_FLAG_SKIP_ANYCAST | GAA_FLAG_SKIP_MULTICAST | GAA_FLAG_SKIP_DNS_SERVER, NULL, list, &size) == NO_ERROR) {
        for (IP_ADAPTER_ADDRESSES *a = list; a; a = a->Next) {
            if (a->OperStatus != IfOperStatusUp || a->IfType == IF_TYPE_SOFTWARE_LOOPBACK)
                continue;
            for (IP_ADAPTER_UNICAST_ADDRESS *u = a->FirstUnicastAddress; u; u = u->Next) {
                struct sockaddr_in *sin = (struct sockaddr_in *) u->Address.lpSockaddr;
                ULONG mask = u->OnLinkPrefixLength >= 32 ? 0xFFFFFFFFu : htonl(~(0xFFFFFFFFu >> u->OnLinkPrefixLength));
                to.sin_addr.s_addr = sin->sin_addr.s_addr | ~mask;
                sendto(n->udp, FIND_MSG, (int) strlen(FIND_MSG), 0, (struct sockaddr *) &to, sizeof(to));
            }
        }
    }
    free(list);
#else
    struct ifaddrs *ifs = NULL;
    if (getifaddrs(&ifs) == 0) {
        for (struct ifaddrs *i = ifs; i; i = i->ifa_next) {
            if (!i->ifa_addr || i->ifa_addr->sa_family != AF_INET || !(i->ifa_flags & IFF_BROADCAST) || !i->ifa_broadaddr)
                continue;
            to.sin_addr = ((struct sockaddr_in *) i->ifa_broadaddr)->sin_addr;
            sendto(n->udp, FIND_MSG, (int) strlen(FIND_MSG), 0, (struct sockaddr *) &to, sizeof(to));
        }
        freeifaddrs(ifs);
    }
#endif
}

static void join_poll(struct Net *n) {
    long long t = now_ms();
    if (n->gaveUp)
        return;
    if (!n->haveTarget) {
        if (n->udp == BAD_SOCK)
            return;
        char buf[64];
        struct sockaddr_in from;
        socklen_t fromLen = sizeof(from);
        int r;
        while ((r = recvfrom(n->udp, buf, sizeof(buf) - 1, 0, (struct sockaddr *) &from, &fromLen)) > 0) {
            buf[r] = 0;
            int port = 0;
            char code[8] = {0};
            if (sscanf(buf, HOST_MSG " %d %7s", &port, code) >= 1 && port > 0) {
                n->target = from;
                n->target.sin_port = htons((uint16_t) port);
                n->haveTarget = 1;
                n->lastTry = 0;
                break;
            }
            fromLen = sizeof(from);
        }
        if (!n->haveTarget && t - n->lastTry >= RETRY_MS) {
            broadcast_find(n);
            n->lastTry = t;
        }
        if (!n->haveTarget)
            return;
    }
    if (n->conn == BAD_SOCK) {
        if (t - n->lastTry < RETRY_MS)
            return;
        n->lastTry = t;
        n->conn = socket(AF_INET, SOCK_STREAM, 0);
        if (n->conn == BAD_SOCK)
            return;
        set_nonblocking(n->conn);
        char addr[64];
        inet_ntop(AF_INET, &n->target.sin_addr, addr, sizeof(addr));
        if (connect(n->conn, (struct sockaddr *) &n->target, sizeof(n->target)) == 0) {
            on_connected(n, &n->target);
        } else if (sock_err() == ERR_INPROGRESS || sock_err() == ERR_WOULDBLOCK) {
            n->connecting = 1;
            set_status(n, "Connecting to %s...", addr);
        } else {
            close_sock(&n->conn);
            set_status(n, "Can't reach %s - retrying", addr);
        }
        return;
    }
    if (n->connecting) {
        fd_set w, e;
        FD_ZERO(&w);
        FD_ZERO(&e);
        FD_SET(n->conn, &w);
        FD_SET(n->conn, &e);
        struct timeval tv = {0, 0};
        if (select((int) n->conn + 1, NULL, &w, &e, &tv) <= 0) {
            if (t - n->lastTry > 3000)
                drop_conn(n, "No answer from the host - retrying");
            return;
        }
        int soErr = 0;
        socklen_t len = sizeof(soErr);
        getsockopt(n->conn, SOL_SOCKET, SO_ERROR, (char *) &soErr, &len);
        if (soErr || FD_ISSET(n->conn, &e)) {
            drop_conn(n, "The host isn't answering - retrying");
            return;
        }
        n->connecting = 0;
        on_connected(n, &n->target);
    }
}

static int refuse(struct Net *n, const char *why) {
    drop_conn(n, why);
    if (n->role == NET_JOIN)
        n->gaveUp = 1;
    return 0;
}

static int check_hello(struct Net *n, const uint8_t *p, size_t len) {
    if (len < 10 || memcmp(p, "B2ON", 4) != 0)
        return refuse(n, "That isn't Black 2 Online on the other side");
    if ((p[4] | p[5] << 8) != NET_VERSION)
        return refuse(n, "The other player has a different version of the app");
    if (memcmp(p + 6, n->gameCode, 4) != 0)
        return refuse(n, "The other player is using a different game (Black 2 vs White 2, or another region)");
    n->helloOk = 1;
    set_status(n, "Connected to %s", n->peerAddr);
    return 1;
}

static void pump(struct Net *n, NetRecvFn fn, void *ctx) {
    long long t = now_ms();
    for (;;) {
        if (n->rxLen == BUF_SIZE)
            break;
        int r = recv(n->conn, (char *) n->rx + n->rxLen, (int) (BUF_SIZE - n->rxLen), 0);
        if (r > 0) {
            n->rxLen += (size_t) r;
            n->lastRecv = t;
            continue;
        }
        if (r == 0 || (sock_err() != ERR_WOULDBLOCK
#ifndef _WIN32
                       && sock_err() != EAGAIN && sock_err() != EINTR
#endif
                       )) {
            drop_conn(n, n->role == NET_HOST ? "The other player left - waiting for them" : "Lost the host - retrying");
            return;
        }
        break;
    }
    size_t off = 0;
    while (n->rxLen - off >= 3) {
        uint8_t type = n->rx[off];
        size_t len = n->rx[off + 1] | (size_t) n->rx[off + 2] << 8;
        if (len > NET_MAX_PAYLOAD) {
            drop_conn(n, "The link sent garbage - reconnecting");
            return;
        }
        if (n->rxLen - off < 3 + len)
            break;
        const uint8_t *p = n->rx + off + 3;
        off += 3 + len;
        if (type == PKT_HELLO) {
            if (!check_hello(n, p, len))
                return;
        } else if (type == PKT_BYE) {
            drop_conn(n, n->role == NET_HOST ? "The other player left - waiting for them" : "The host closed - retrying");
            return;
        } else if (type != PKT_PING && n->helloOk && fn) {
            fn(ctx, type, p, len);
        }
    }
    memmove(n->rx, n->rx + off, n->rxLen - off);
    n->rxLen -= off;

    if (t - n->lastSend >= PING_MS)
        queue(n, PKT_PING, NULL, 0);
    while (n->txLen > 0) {
        int w = send(n->conn, (const char *) n->tx, (int) n->txLen, SEND_FLAGS);
        if (w <= 0)
            break;
        memmove(n->tx, n->tx + w, n->txLen - (size_t) w);
        n->txLen -= (size_t) w;
        n->lastSend = t;
    }
    if (t - n->lastRecv > DEAD_MS)
        drop_conn(n, n->role == NET_HOST ? "Lost the other player - waiting for them" : "Lost the host - retrying");
}

void net_poll(struct Net *n, NetRecvFn fn, void *ctx) {
    if (n->role == NET_HOST)
        host_poll(n);
    else if (n->role == NET_JOIN)
        join_poll(n);
    if (n->conn != BAD_SOCK && !n->connecting)
        pump(n, fn, ctx);
}

void net_send(struct Net *n, uint8_t type, const void *data, size_t len) {
    if (n->conn != BAD_SOCK && !n->connecting && n->helloOk)
        queue(n, type, data, len);
}

int net_connected(const struct Net *n) { return n->conn != BAD_SOCK && !n->connecting && n->helloOk; }
enum NetRole net_role(const struct Net *n) { return n->role; }
const char *net_status(const struct Net *n) { return n->status; }
const char *net_peer_addr(const struct Net *n) { return n->peerAddr; }

void net_local_addresses(char *out, size_t outSize) {
    size_t used = 0;
    out[0] = 0;
#ifdef _WIN32
    ULONG size = 16384;
    IP_ADAPTER_ADDRESSES *list = (IP_ADAPTER_ADDRESSES *) malloc(size);
    if (list && GetAdaptersAddresses(AF_INET, GAA_FLAG_SKIP_ANYCAST | GAA_FLAG_SKIP_MULTICAST | GAA_FLAG_SKIP_DNS_SERVER, NULL, list, &size) == NO_ERROR) {
        for (IP_ADAPTER_ADDRESSES *a = list; a; a = a->Next) {
            if (a->OperStatus != IfOperStatusUp || a->IfType == IF_TYPE_SOFTWARE_LOOPBACK)
                continue;
            for (IP_ADAPTER_UNICAST_ADDRESS *u = a->FirstUnicastAddress; u; u = u->Next) {
                char ip[64];
                inet_ntop(AF_INET, &((struct sockaddr_in *) u->Address.lpSockaddr)->sin_addr, ip, sizeof(ip));
                if (strncmp(ip, "169.254.", 8) == 0)
                    continue;
                used += (size_t) snprintf(out + used, used < outSize ? outSize - used : 0, "%s%s", used ? ", " : "", ip);
            }
        }
    }
    free(list);
#else
    struct ifaddrs *ifs = NULL;
    if (getifaddrs(&ifs) == 0) {
        for (struct ifaddrs *i = ifs; i; i = i->ifa_next) {
            if (!i->ifa_addr || i->ifa_addr->sa_family != AF_INET || (i->ifa_flags & IFF_LOOPBACK))
                continue;
            char ip[64];
            inet_ntop(AF_INET, &((struct sockaddr_in *) i->ifa_addr)->sin_addr, ip, sizeof(ip));
            used += (size_t) snprintf(out + used, used < outSize ? outSize - used : 0, "%s%s", used ? ", " : "", ip);
        }
        freeifaddrs(ifs);
    }
#endif
    if (used >= outSize && outSize > 0)
        out[outSize - 1] = 0;
}
