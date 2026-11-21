// HD texture packs: hand-made high-resolution replacements for individual
// 8x8 GBA tiles (backgrounds and sprites).
//
//   hd/tiles/<hash>.png   a replacement, any multiple of 8 px square (e.g.
//                         32x32 = 4x detail). Alpha = transparency.
//   hd/dump/<hash>.png    tiles dumped while playing (F6), at original size,
//                         to use as templates for drawing replacements.
//
// <hash> is 16 hex digits identifying the tile's pixels together with its
// palette (the game's unfaded palette, so screen fades don't change it and
// fades are re-applied to the HD art at draw time).
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "port.h"
#include "hdpack.h"

#define STB_IMAGE_IMPLEMENTATION
#define STBI_ONLY_PNG
#define STBI_NO_STDIO_HINT
#include "third_party/stb_image.h"
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "third_party/stb_image_write.h"

#ifdef _WIN32
#include <windows.h>
#include <direct.h>
#define MKDIR(p) _mkdir(p)
#else
#include <dirent.h>
#include <sys/stat.h>
#define MKDIR(p) mkdir(p, 0755)
#endif

extern uint16_t gPlttBufferUnfaded[512];

int gHdPackActive;
int gHdDumpEnabled;

static char sDir[1024];

// Pack lookup: open-addressing table hash -> slot+1.
#define TABLE_SIZE 65536
static uint64_t sKeys[TABLE_SIZE];
static uint16_t sVals[TABLE_SIZE];

// Atlas of replacement tiles.
static uint32_t *sAtlas;
static int sAtlasW, sAtlasH, sTile, sPerRow, sNumSlots, sScale;
#define MAX_SLOTS 16000

// Tiles already dumped (so each is written once).
static uint64_t sDumped[TABLE_SIZE];

static uint64_t Fnv(uint64_t h, const void *p, int n)
{
    const uint8_t *b = p;
    while (n--)
    {
        h ^= *b++;
        h *= 0x100000001B3ull;
    }
    return h;
}

static int TableFind(const uint64_t *keys, uint64_t k)
{
    uint32_t i = (uint32_t)(k ^ (k >> 29)) & (TABLE_SIZE - 1);
    while (keys[i] && keys[i] != k)
        i = (i + 1) & (TABLE_SIZE - 1);
    return (int)i;
}

static void AddReplacement(uint64_t hash, const unsigned char *rgba, int w, int h)
{
    int slot, x, y, ox, oy, i;
    if (sNumSlots >= MAX_SLOTS || !hash)
        return;
    if (!sAtlas)
    {
        // The first image sets the pack's scale.
        sScale = w / 8;
        sTile = sScale * 8;
        sPerRow = 4096 / sTile;
        if (sPerRow < 1) sPerRow = 1;
        sAtlasW = sPerRow * sTile;
        sAtlasH = ((MAX_SLOTS + sPerRow - 1) / sPerRow) * sTile;
        if (sAtlasH > 8192) sAtlasH = 8192;
        sAtlas = calloc((size_t)sAtlasW * sAtlasH, 4);
        if (!sAtlas)
            return;
    }
    slot = sNumSlots;
    ox = (slot % sPerRow) * sTile;
    oy = (slot / sPerRow) * sTile;
    if (oy + sTile > sAtlasH)
        return;
    // Resample (nearest) if this image's scale differs from the pack's.
    for (y = 0; y < sTile; y++)
        for (x = 0; x < sTile; x++)
        {
            int sx = x * w / sTile, sy = y * h / sTile;
            const unsigned char *p = rgba + ((size_t)sy * w + sx) * 4;
            sAtlas[(size_t)(oy + y) * sAtlasW + ox + x] = p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24);
        }
    i = TableFind(sKeys, hash);
    sKeys[i] = hash;
    sVals[i] = (uint16_t)(slot + 1);
    sNumSlots++;
}

static void LoadFile(const char *dir, const char *name)
{
    char path[2048];
    uint64_t hash = 0;
    int w, h, n, len = (int)strlen(name);
    unsigned char *img;

    if (len != 20 || strcmp(name + 16, ".png") != 0)
        return;
    if (sscanf(name, "%16llx", (unsigned long long *)&hash) != 1)
        return;
    snprintf(path, sizeof(path), "%s/%s", dir, name);
    img = stbi_load(path, &w, &h, &n, 4);
    if (!img)
        return;
    if (w == h && w >= 8 && w % 8 == 0 && w <= 128)
        AddReplacement(hash, img, w, h);
    stbi_image_free(img);
}

void HdPackInit(const char *baseDir)
{
    char tiles[1100];
    snprintf(sDir, sizeof(sDir), "%shd", baseDir);
    snprintf(tiles, sizeof(tiles), "%s/tiles", sDir);
#ifdef _WIN32
    {
        WIN32_FIND_DATAA fd;
        char pattern[1200];
        HANDLE hf;
        snprintf(pattern, sizeof(pattern), "%s\\*.png", tiles);
        hf = FindFirstFileA(pattern, &fd);
        if (hf != INVALID_HANDLE_VALUE)
        {
            do LoadFile(tiles, fd.cFileName); while (FindNextFileA(hf, &fd));
            FindClose(hf);
        }
    }
#else
    {
        DIR *d = opendir(tiles);
        struct dirent *e;
        if (d)
        {
            while ((e = readdir(d)))
                LoadFile(tiles, e->d_name);
            closedir(d);
        }
    }
#endif
    gHdPackActive = sNumSlots > 0;
    if (gHdPackActive)
        fprintf(stderr, "HD pack: %d tiles at %dx\n", sNumSlots, sScale);
}

int HdPackAtlas(const uint32_t **pixels, int *w, int *h, int *scale, int *perRow)
{
    if (!gHdPackActive)
        return 0;
    *pixels = sAtlas;
    *w = sAtlasW;
    *h = sAtlasH;
    *scale = sScale;
    *perRow = sPerRow;
    return 1;
}

void HdPackSetDump(int on)
{
    gHdDumpEnabled = on;
    if (on)
    {
        char d[1100];
        MKDIR(sDir);
        snprintf(d, sizeof(d), "%s/dump", sDir);
        MKDIR(d);
    }
}

// --- Per-frame tile cache -------------------------------------------------

#define CACHE_SIZE 8192
struct CacheEnt { uint32_t key, stamp; uint16_t slot; };
static struct CacheEnt sCache[CACHE_SIZE];
static uint32_t sStamp = 1;

void HdPackBeginFrame(void)
{
    sStamp++;
}

static void DumpTile(uint64_t hash, uint32_t charAddr, int is8, int palBase)
{
    char path[1200];
    uint32_t px[64];
    int i, slot = TableFind(sDumped, hash);
    FILE *f;

    if (sDumped[slot] == hash)
        return;
    sDumped[slot] = hash;
    snprintf(path, sizeof(path), "%s/dump/%016llx.png", sDir, (unsigned long long)hash);
    f = fopen(path, "rb");
    if (f)
    {
        fclose(f);
        return;
    }
    for (i = 0; i < 64; i++)
    {
        int c;
        uint16_t col;
        uint32_t r, g, b;
        if (is8)
            c = PC_VRAM8[(charAddr + i) & 0x17FFF];
        else
        {
            c = PC_VRAM8[(charAddr + (i >> 1)) & 0x17FFF];
            c = (i & 1) ? (c >> 4) : (c & 0xF);
        }
        if (c == 0)
        {
            px[i] = 0;
            continue;
        }
        col = gPlttBufferUnfaded[(palBase + c) & 511];
        r = col & 31; g = (col >> 5) & 31; b = (col >> 10) & 31;
        r = (r << 3) | (r >> 2); g = (g << 3) | (g >> 2); b = (b << 3) | (b >> 2);
        px[i] = r | (g << 8) | (b << 16) | 0xFF000000u;
    }
    stbi_write_png(path, 8, 8, 4, px, 32);
}

uint16_t HdPackLookup(uint32_t charAddr, int is8, int palBase)
{
    uint32_t key = (charAddr << 10) | ((uint32_t)palBase << 1) | (is8 ? 1 : 0);
    uint32_t ci = (key * 2654435761u) >> 19;
    struct CacheEnt *ce = &sCache[ci & (CACHE_SIZE - 1)];
    uint64_t h = 0xCBF29CE484222325ull;
    uint16_t slot = 0;
    int i, n = is8 ? 256 : 16;

    if (ce->stamp == sStamp && ce->key == key)
        return ce->slot;

    // Tile pixels...
    for (i = 0; i < (is8 ? 64 : 32); i++)
    {
        uint8_t b = PC_VRAM8[(charAddr + i) & 0x17FFF];
        h = Fnv(h, &b, 1);
    }
    // ...and the palette colours they can use (colour 0 is transparent).
    for (i = 1; i < n; i++)
    {
        uint16_t c = gPlttBufferUnfaded[(palBase + i) & 511] & 0x7FFF;
        h = Fnv(h, &c, 2);
    }
    if (!h) h = 1;

    if (gHdPackActive)
    {
        int ti = TableFind(sKeys, h);
        if (sKeys[ti] == h)
            slot = sVals[ti];
    }
    if (gHdDumpEnabled)
        DumpTile(h, charAddr, is8, palBase);

    ce->key = key;
    ce->stamp = sStamp;
    ce->slot = slot;
    return slot;
}

uint16_t HdPackUnfaded(int palIndex)
{
    return gPlttBufferUnfaded[palIndex & 511] & 0x7FFF;
}
