// Headless mGBA runner: ./run rom.gba script.txt outdir
// script lines: "<frames> <keys>" (tap) or "hold <frames> <keys>" (keys: A B s(elect) S(tart) R L U D r l or -), "shot <name>"
#include <mgba/core/core.h>
#include <mgba/core/config.h>
#include <mgba/core/log.h>
#include <png.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void shot(const char *path, const uint32_t *buf, unsigned w, unsigned h) {
    FILE *f = fopen(path, "wb");
    png_structp p = png_create_write_struct(PNG_LIBPNG_VER_STRING, NULL, NULL, NULL);
    png_infop i = png_create_info_struct(p);
    png_init_io(p, f);
    png_set_IHDR(p, i, w, h, 8, PNG_COLOR_TYPE_RGB, 0, 0, 0);
    png_write_info(p, i);
    unsigned char *row = malloc(w * 3);
    for (unsigned y = 0; y < h; y++) {
        for (unsigned x = 0; x < w; x++) {
            uint32_t c = buf[y * w + x];
            row[x * 3] = c & 0xFF; row[x * 3 + 1] = (c >> 8) & 0xFF; row[x * 3 + 2] = (c >> 16) & 0xFF;
        }
        png_write_row(p, row);
    }
    png_write_end(p, NULL); png_destroy_write_struct(&p, &i); fclose(f); free(row);
}

static void quiet(struct mLogger *l, int c, enum mLogLevel lv, const char *f, va_list a) { (void) l; (void) c; (void) lv; (void) f; (void) a; }

int main(int argc, char **argv) {
    static struct mLogger logger = { .log = quiet };
    mLogSetDefaultLogger(&logger);
    struct mCore *core = mCoreFind(argv[1]);
    if (!core || !core->init(core)) return 1;
    mCoreInitConfig(core, NULL);
    unsigned w, h;
    core->desiredVideoDimensions(core, &w, &h);
    uint32_t *buf = calloc(w * h, 4);
    core->setVideoBuffer(core, (color_t *) buf, w);
    if (!mCoreLoadFile(core, argv[1])) return 2;
    core->reset(core);
    FILE *s = fopen(argv[2], "r");
    char line[256];
    while (fgets(line, sizeof line, s)) {
        char a[64], b[64];
        if (sscanf(line, "shot %63s", a) == 1) {
            char path[512]; snprintf(path, sizeof path, "%s/%s.png", argv[3], a);
            shot(path, buf, w, h); continue;
        }
        unsigned addr, mx, my;
        if (sscanf(line, "peekmap %x %u %u", &addr, &mx, &my) == 3) {
            int w = (int) core->busRead32(core, addr), h = (int) core->busRead32(core, addr + 4);
            uint32_t m = core->busRead32(core, addr + 8);
            printf("map %dx%d", w, h);
            for (int dx = -1; dx <= 1; dx++) printf("  (%u,%u)=%04x", mx + dx, my, core->busRead16(core, m + 2 * ((my + 7) * w + mx + dx + 7)));
            printf("\n");
            continue;
        }
        if (!strncmp(line, "pos", 3)) {     // live player coords: gObjectEvents[0].currentCoords
            printf("pos %d,%d\n", (int16_t) core->busRead16(core, 0x02036b20) - 7, (int16_t) core->busRead16(core, 0x02036b22) - 7);
            continue;
        }
        if (sscanf(line, "peek %x", &addr) == 1) {
            uint32_t p = core->busRead32(core, addr);
            printf("peek %08x -> %08x  pos16 %d,%d\n", addr, p, (int16_t) core->busRead16(core, p), (int16_t) core->busRead16(core, p + 2));
            continue;
        }
        int hold = 0;
        if (sscanf(line, "hold %63s %63s", a, b) == 2) hold = 1;
        else if (sscanf(line, "%63s %63s", a, b) != 2) continue;
        int frames = atoi(a), keys = 0;
        for (char *k = b; *k; k++) {
            const char *map = "ABsSRLUDrl"; char *p = strchr(map, *k);
            if (p) keys |= 1 << (p - map);
        }
        for (int f = 0; f < frames; f++) {
            // tap: hold keys for the first 6 frames of each step only
            core->setKeys(core, (hold || f < 6) ? keys : 0);
            core->runFrame(core);
        }
    }
    core->deinit(core);
    return 0;
}
