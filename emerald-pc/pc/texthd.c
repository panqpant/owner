// High-resolution text.
//
// The game draws text by copying glyph bitmaps into window pixel buffers,
// which are later copied into BG tile memory. Here every window pixel that
// belongs to a glyph gets a tag (which glyph, where in it, and the text
// colours). Tags follow the pixels: they are cleared when the window is
// filled, shifted when it scrolls, and copied alongside the tiles into a
// VRAM-shaped tag array (gPcTextTags). The renderer then draws tagged pixels
// from a high-resolution version of the glyph, coloured with the live
// palette. A tag is only trusted while the pixel still has the colour it was
// drawn with, so anything that overwrites text without going through these
// hooks just falls back to normal rendering.
//
// Compiled with the game's headers.
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "global.h"
#include "window.h"
#include "text.h"
#include "bg.h"
#include "texthd.h"

// Tag layout: slot+1 (10 bits) | lx (4) | ly (4) | fg (4) | shadow (4) | bg (4)
#define TAG_SLOT(t)  ((t) & 0x3FF)
#define TAG(slot, lx, ly, fg, sh, bg) \
    ((u32)(slot) | ((u32)(lx) << 10) | ((u32)(ly) << 14) | ((u32)(fg) << 18) | ((u32)(sh) << 22) | ((u32)(bg) << 26))

u32 gPcTextTags[0x20000]; // one per BG VRAM pixel (4bpp): index = byte address * 2 + nibble

// Checksum of each BG VRAM tile's contents when its tags were written. Tags
// in a tile are only used while the tile still matches, so tiles later
// overwritten by anything else (map tilesets, other screens) are ignored.
static u32 sTileSum[0x10000 / 32];
static u32 sTileStamp[0x10000 / 32];
static u8 sTileOk[0x10000 / 32];
static u32 sFrameStamp = 1;

static u32 TileSum(const u8 *p)
{
    u32 h = 2166136261u;
    int i;
    for (i = 0; i < 32; i++)
        h = (h ^ p[i]) * 16777619u;
    return h | 1;
}

void PcTextBeginFrame(void)
{
    sFrameStamp++;
}

int PcTextTileOk(u32 tileIndex)
{
    if (tileIndex >= 0x10000 / 32 || !sTileSum[tileIndex])
        return 0;
    if (sTileStamp[tileIndex] != sFrameStamp)
    {
        sTileStamp[tileIndex] = sFrameStamp;
        sTileOk[tileIndex] = TileSum((const u8 *)VRAM + tileIndex * 32) == sTileSum[tileIndex];
    }
    return sTileOk[tileIndex];
}
int gPcTextHd = 1;

static u32 *sWinTags[WINDOWS_MAX];
static int sWinW[WINDOWS_MAX], sWinH[WINDOWS_MAX]; // in pixels

// --- Glyph atlas ------------------------------------------------------------

#define GLYPH_CELL 16          // max glyph size in GBA pixels
#define GLYPH_SCALE 8          // atlas pixels per GBA pixel
#define GLYPH_PX (GLYPH_CELL * GLYPH_SCALE)
#define ATLAS_COLS 16
#define ATLAS_ROWS 32
#define MAX_GLYPHS (ATLAS_COLS * ATLAS_ROWS - 1)

struct Glyph {
    u32 hash;
    u8 w, h;
    u8 role[GLYPH_CELL][GLYPH_CELL]; // 0 background, 1 foreground, 2 shadow
};
static struct Glyph sGlyphs[MAX_GLYPHS + 1]; // slot 0 unused
static int sNumGlyphs;
static u8 *sAtlas;              // RG8, ATLAS_COLS*GLYPH_PX wide
static u16 sPending[MAX_GLYPHS + 1];
static int sNumPending;

int PcTextAtlasSize(int *w, int *h)
{
    *w = ATLAS_COLS * GLYPH_PX;
    *h = ATLAS_ROWS * GLYPH_PX;
    return GLYPH_SCALE;
}

// Next glyph whose high-resolution image still needs uploading to the GPU.
int PcTextNextPending(const u8 **pixels, int *x, int *y, int *w, int *h, int *stride)
{
    int slot;
    if (!sNumPending || !sAtlas)
        return 0;
    slot = sPending[--sNumPending];
    *x = (slot % ATLAS_COLS) * GLYPH_PX;
    *y = (slot / ATLAS_COLS) * GLYPH_PX;
    *w = GLYPH_PX;
    *h = GLYPH_PX;
    *stride = ATLAS_COLS * GLYPH_PX;
    *pixels = sAtlas + ((size_t)*y * *stride + *x) * 2;
    return 1;
}

// Expected palette index of a pixel inside a glyph, or -1 if none.
int PcTextExpected(u32 tag)
{
    u32 slot = TAG_SLOT(tag);
    int lx = (tag >> 10) & 15, ly = (tag >> 14) & 15, r;
    if (!slot || slot > (u32)sNumGlyphs)
        return -1;
    r = sGlyphs[slot].role[ly][lx];
    return r == 1 ? (tag >> 18) & 15 : r == 2 ? (tag >> 22) & 15 : (tag >> 26) & 15;
}

// xBR 4x on a small greyscale image (same rules as the GPU shader), used to
// turn a 1-bit glyph mask into smooth curves.
static void Xbr4Gray(const u8 *src, int w, int h, u8 *dst)
{
    static const int kRole[11][2] = {
        { 1, 1 }, { 0, 1 }, { 1, 0 }, { -1, 1 }, { 1, -1 }, { -1, 0 }, { 0, -1 },
        { 0, 2 }, { 2, 0 }, { 1, 2 }, { 2, 1 },
    };
    int x, y, k, i;
#define DF(a, b) abs((int)(a) - (int)(b))
#define EQ(a, b) (DF(a, b) < 155)
#define B(a, b, t) ((a) + (((int)(b) - (int)(a)) * (t)) / 4)
    for (y = 0; y < h; y++)
        for (x = 0; x < w; x++)
        {
            int E[16];
            int e0 = src[y * w + x];
            for (i = 0; i < 16; i++)
                E[i] = e0;
            for (k = 0; k < 4; k++)
            {
                int P[11], n;
                for (n = 0; n < 11; n++)
                {
                    int dx = kRole[n][0], dy = kRole[n][1], r, px, py;
                    for (r = 0; r < k; r++) { int t = dx; dx = dy; dy = -t; }
                    px = x + dx; py = y + dy;
                    P[n] = (px < 0 || py < 0 || px >= w || py >= h) ? 0 : src[py * w + px];
                }
                {
                    int PE = e0, PI = P[0], PH = P[1], PF = P[2], PG = P[3], PC = P[4], PD = P[5], PB = P[6];
                    int H5 = P[7], F4 = P[8], I5 = P[9], I4 = P[10];
                    int cx2 = 3, cy2 = 3, ux = -1, uy = 0, vx = 0, vy = -1, r;
                    int N15, N14, N13, N12, N11, N7, N3, N10;
                    for (r = 0; r < k; r++)
                    {
                        int t;
                        t = cx2; cx2 = cy2; cy2 = -t;
                        t = ux; ux = uy; uy = -t;
                        t = vx; vx = vy; vy = -t;
                    }
                    cx2 = (cx2 + 3) / 2; cy2 = (cy2 + 3) / 2;
#define IDX(a, b) ((cy2 + (a) * uy + (b) * vy) * 4 + (cx2 + (a) * ux + (b) * vx))
                    N15 = IDX(0, 0); N14 = IDX(1, 0); N13 = IDX(2, 0); N12 = IDX(3, 0);
                    N11 = IDX(0, 1); N7 = IDX(0, 2); N3 = IDX(0, 3); N10 = IDX(1, 1);
#undef IDX
                    if (PE != PH && PE != PF)
                    {
                        int e = DF(PE, PC) + DF(PE, PG) + DF(PI, H5) + DF(PI, F4) + 4 * DF(PH, PF);
                        int ii = DF(PH, PD) + DF(PH, I5) + DF(PF, I4) + DF(PF, PB) + 4 * DF(PE, PI);
                        if (e <= ii)
                        {
                            int px = DF(PE, PF) <= DF(PE, PH) ? PF : PH;
                            if (e < ii && ((!EQ(PF, PB) && !EQ(PH, PD)) || (EQ(PE, PI) && (!EQ(PF, I4) || !EQ(PH, I5)))
                                           || EQ(PE, PG) || EQ(PE, PC)))
                            {
                                int ke = DF(PF, PG), ki = DF(PH, PC);
                                int left = 2 * ke <= ki && PE != PG && PD != PG;
                                int up = ke >= 2 * ki && PE != PC && PB != PC;
                                if (left && up)
                                {
                                    E[N13] = B(E[N13], px, 3); E[N12] = B(E[N12], px, 1);
                                    E[N15] = E[N14] = E[N11] = px;
                                    E[N10] = E[N3] = E[N12]; E[N7] = E[N13];
                                }
                                else if (left)
                                {
                                    E[N11] = B(E[N11], px, 3); E[N13] = B(E[N13], px, 3);
                                    E[N10] = B(E[N10], px, 1); E[N12] = B(E[N12], px, 1);
                                    E[N14] = E[N15] = px;
                                }
                                else if (up)
                                {
                                    E[N14] = B(E[N14], px, 3); E[N7] = B(E[N7], px, 3);
                                    E[N10] = B(E[N10], px, 1); E[N3] = B(E[N3], px, 1);
                                    E[N11] = E[N15] = px;
                                }
                                else
                                {
                                    E[N11] = B(E[N11], px, 2); E[N14] = B(E[N14], px, 2);
                                    E[N15] = px;
                                }
                            }
                            else
                                E[N15] = B(E[N15], px, 2);
                        }
                    }
                }
            }
            for (i = 0; i < 16; i++)
                dst[(y * 4 + i / 4) * (w * 4) + x * 4 + i % 4] = (u8)E[i];
        }
#undef DF
#undef EQ
#undef B
}

// Scale2x (EPX) on a binary image: doubles the size and turns 1-pixel
// stair-steps into finer diagonals, which suits thin font strokes.
static void Scale2x(const u8 *src, int w, int h, u8 *dst)
{
    int x, y;
#define S(px, py) (((px) < 0 || (py) < 0 || (px) >= w || (py) >= h) ? 0 : src[(py) * w + (px)])
    for (y = 0; y < h; y++)
        for (x = 0; x < w; x++)
        {
            u8 P = S(x, y), A = S(x, y - 1), B = S(x + 1, y), C = S(x - 1, y), D = S(x, y + 1);
            u8 o1 = P, o2 = P, o3 = P, o4 = P;
            if (C == A && C != D && A != B) o1 = A;
            if (A == B && A != C && B != D) o2 = B;
            if (D == C && D != B && C != A) o3 = C;
            if (B == D && B != A && D != C) o4 = D;
            dst[(y * 2) * (w * 2) + x * 2] = o1;
            dst[(y * 2) * (w * 2) + x * 2 + 1] = o2;
            dst[(y * 2 + 1) * (w * 2) + x * 2] = o3;
            dst[(y * 2 + 1) * (w * 2) + x * 2 + 1] = o4;
        }
#undef S
}

// Smooth high-resolution coverage for one role of a glyph, into the atlas:
// Scale2x twice (4x), then blur and re-threshold at 8x into a crisp,
// anti-aliased outline.
static void RenderCoverage(const struct Glyph *g, int role, u8 *out, int channel)
{
    u8 mask[GLYPH_CELL * GLYPH_CELL];
    static u8 m2[GLYPH_CELL * GLYPH_CELL * 4], m4[GLYPH_CELL * GLYPH_CELL * 16];
    static float hd[GLYPH_PX * GLYPH_PX], tmp[GLYPH_PX * GLYPH_PX];
    // Gaussian, sigma ~3.5 atlas pixels (~0.45 GBA pixels): rounds the font's
    // 1-2 pixel stair-steps into smooth slants while keeping strokes solid.
    static float k[15];
    static int kInit;
    int x, y, i, W = g->w * GLYPH_SCALE, H = g->h * GLYPH_SCALE, stride = ATLAS_COLS * GLYPH_PX;

    if (!kInit)
    {
        float sum = 0;
        for (i = 0; i < 15; i++) { k[i] = expf(-(float)((i - 7) * (i - 7)) / (2 * 3.5f * 3.5f)); sum += k[i]; }
        for (i = 0; i < 15; i++) k[i] /= sum;
        kInit = 1;
    }
    for (y = 0; y < g->h; y++)
        for (x = 0; x < g->w; x++)
            mask[y * g->w + x] = g->role[y][x] == role;
    Scale2x(mask, g->w, g->h, m2);
    Scale2x(m2, g->w * 2, g->h * 2, m4);

    for (y = 0; y < H; y++)
        for (x = 0; x < W; x++)
            hd[y * W + x] = m4[(y / 2) * (g->w * 4) + x / 2] ? 1.0f : 0.0f;
    // Separable blur (horizontal then vertical).
    for (y = 0; y < H; y++)
        for (x = 0; x < W; x++)
        {
            float v = 0;
            for (i = -7; i <= 7; i++)
            {
                int xx = x + i;
                if (xx >= 0 && xx < W) v += hd[y * W + xx] * k[i + 7];
            }
            tmp[y * W + x] = v;
        }
    for (y = 0; y < H; y++)
        for (x = 0; x < W; x++)
        {
            float v = 0, t;
            for (i = -7; i <= 7; i++)
            {
                int yy = y + i;
                if (yy >= 0 && yy < H) v += tmp[yy * W + x] * k[i + 7];
            }
            t = (v - 0.40f) / 0.16f;
            if (t < 0) t = 0;
            if (t > 1) t = 1;
            t = t * t * (3 - 2 * t);
            out[((size_t)y * stride + x) * 2 + channel] = (u8)(t * 255 + 0.5f);
        }
}

static int FindOrAddGlyph(const struct Glyph *g)
{
    int i, slot;
    for (i = 1; i <= sNumGlyphs; i++)
        if (sGlyphs[i].hash == g->hash && sGlyphs[i].w == g->w && sGlyphs[i].h == g->h
         && !memcmp(sGlyphs[i].role, g->role, sizeof(g->role)))
            return i;
    if (sNumGlyphs >= MAX_GLYPHS)
        return 0;
    if (!sAtlas)
    {
        sAtlas = calloc((size_t)ATLAS_COLS * GLYPH_PX * ATLAS_ROWS * GLYPH_PX, 2);
        if (!sAtlas)
            return 0;
    }
    slot = ++sNumGlyphs;
    sGlyphs[slot] = *g;
    {
        u8 *cell = sAtlas + (((size_t)(slot / ATLAS_COLS) * GLYPH_PX) * ATLAS_COLS * GLYPH_PX
                             + (slot % ATLAS_COLS) * GLYPH_PX) * 2;
        RenderCoverage(g, 1, cell, 0);
        RenderCoverage(g, 2, cell, 1);
    }
    sPending[sNumPending++] = slot;
    return slot;
}

// --- Window pixel access ------------------------------------------------------

static int WinPixel(u8 windowId, int x, int y)
{
    const u8 *tiles = gWindows[windowId].tileData;
    int w = gWindows[windowId].window.width;
    int b = tiles[((y >> 3) * w + (x >> 3)) * 32 + (y & 7) * 4 + ((x & 7) >> 1)];
    return (x & 1) ? b >> 4 : b & 15;
}

static u32 *Tags(u8 windowId)
{
    int w, h;
    if (windowId >= WINDOWS_MAX || !gWindows[windowId].tileData)
        return NULL;
    w = gWindows[windowId].window.width * 8;
    h = gWindows[windowId].window.height * 8;
    if (!sWinTags[windowId] || sWinW[windowId] != w || sWinH[windowId] != h)
    {
        free(sWinTags[windowId]);
        sWinTags[windowId] = calloc((size_t)w * h, 4);
        sWinW[windowId] = w;
        sWinH[windowId] = h;
    }
    return sWinTags[windowId];
}

// --- Hooks called from the game (PLATFORM_PC) ----------------------------------

void PcTextGlyph(struct TextPrinter *printer)
{
    u8 id = printer->printerTemplate.windowId;
    u32 *tags = Tags(id);
    int x0 = printer->printerTemplate.currentX, y0 = printer->printerTemplate.currentY;
    int gw = gCurGlyph.width, gh = gCurGlyph.height, x, y, slot;
    int fg = printer->printerTemplate.fgColor, sh = printer->printerTemplate.shadowColor;
    int bg = printer->printerTemplate.bgColor;
    struct Glyph g;

    if (!tags || !gPcTextHd || gWindows[id].window.paletteNum > 15)
        return;
    if (x0 + gw > sWinW[id]) gw = sWinW[id] - x0;
    if (y0 + gh > sWinH[id]) gh = sWinH[id] - y0;
    if (gw <= 0 || gh <= 0 || gw > GLYPH_CELL || gh > GLYPH_CELL)
        return;

    memset(&g, 0, sizeof(g));
    g.w = gw;
    g.h = gh;
    g.hash = 2166136261u;
    for (y = 0; y < gh; y++)
        for (x = 0; x < gw; x++)
        {
            int c = WinPixel(id, x0 + x, y0 + y);
            int r = (c == fg && fg != bg) ? 1 : (c == sh && sh != bg) ? 2 : 0;
            g.role[y][x] = r;
            g.hash = (g.hash ^ r) * 16777619u;
        }
    slot = FindOrAddGlyph(&g);
    for (y = 0; y < gh; y++)
        for (x = 0; x < gw; x++)
            tags[(y0 + y) * sWinW[id] + x0 + x] = slot ? TAG(slot, x, y, fg, sh, bg) : 0;
}

void PcTextClear(u8 windowId, int x, int y, int w, int h)
{
    u32 *tags = Tags(windowId);
    int yy;
    if (!tags)
        return;
    if (x < 0) { w += x; x = 0; }
    if (y < 0) { h += y; y = 0; }
    if (x + w > sWinW[windowId]) w = sWinW[windowId] - x;
    if (y + h > sWinH[windowId]) h = sWinH[windowId] - y;
    for (yy = y; yy < y + h && w > 0; yy++)
        memset(&tags[yy * sWinW[windowId] + x], 0, (size_t)w * 4);
}

void PcTextClearAll(u8 windowId)
{
    PcTextClear(windowId, 0, 0, 1 << 12, 1 << 12);
}

// direction 0: content moves up by distance; 1: down. Others: forget tags.
void PcTextScroll(u8 windowId, int direction, int distance)
{
    u32 *tags = Tags(windowId);
    int w = sWinW[windowId], h = sWinH[windowId], y;
    if (!tags)
        return;
    if (direction == 0)
    {
        for (y = 0; y < h; y++)
        {
            if (y + distance < h)
                memcpy(&tags[y * w], &tags[(y + distance) * w], (size_t)w * 4);
            else
                memset(&tags[y * w], 0, (size_t)w * 4);
        }
    }
    else if (direction == 1)
    {
        for (y = h - 1; y >= 0; y--)
        {
            if (y - distance >= 0)
                memcpy(&tags[y * w], &tags[(y - distance) * w], (size_t)w * 4);
            else
                memset(&tags[y * w], 0, (size_t)w * 4);
        }
    }
    else
        memset(tags, 0, (size_t)w * h * 4);
}

void PcTextFree(u8 windowId)
{
    if (windowId < WINDOWS_MAX)
    {
        free(sWinTags[windowId]);
        sWinTags[windowId] = NULL;
        sWinW[windowId] = sWinH[windowId] = 0;
    }
}

// Copy tags for a linear range of the window's tiles (as CopyWindowRectToVram does).
void PcTextToVramRange(u8 windowId, int firstTile, int numTiles)
{
    int w = gWindows[windowId].window.width, t;
    if (w <= 0)
        return;
    for (t = firstTile; t < firstTile + numTiles; t++)
        PcTextToVram(windowId, t % w, t / w, 1, 1);
}

// The window's tiles were copied to BG VRAM: copy the tags alongside.
// (tileX, tileY, tileW, tileH) in tiles; the whole window when tileW == 0.
void PcTextToVram(u8 windowId, int tileX, int tileY, int tileW, int tileH)
{
    u32 *tags = Tags(windowId);
    int w, h, tx, ty, px, py;
    u32 base;

    if (!tags)
        return;
    w = gWindows[windowId].window.width;
    h = gWindows[windowId].window.height;
    if (tileW == 0)
    {
        tileX = tileY = 0;
        tileW = w;
        tileH = h;
    }
    base = GetBgAttribute(gWindows[windowId].window.bg, BG_ATTR_CHARBASEINDEX) * 0x4000
         + gWindows[windowId].window.baseBlock * 32;
    for (ty = tileY; ty < tileY + tileH && ty < h; ty++)
        for (tx = tileX; tx < tileX + tileW && tx < w; tx++)
        {
            u32 tileAddr = base + (ty * w + tx) * 32;
            u32 *dst;
            if (tileAddr + 32 > 0x10000)
                continue;
            dst = &gPcTextTags[tileAddr * 2];
            sTileSum[tileAddr / 32] = TileSum(gWindows[windowId].tileData + (ty * w + tx) * 32);
            sTileStamp[tileAddr / 32] = 0;
            for (py = 0; py < 8; py++)
                for (px = 0; px < 8; px++)
                    dst[py * 8 + px] = tags[(ty * 8 + py) * sWinW[windowId] + tx * 8 + px];
        }
}
