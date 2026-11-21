// Scanline renderer for the GBA picture processor. Reads the game's VRAM,
// palette RAM, OAM and display registers exactly as the hardware would, so
// mid-frame (HBlank) effects work unchanged.
#include <string.h>
#include "port.h"

typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;
typedef int16_t s16; typedef int32_t s32;

#define R16(off) IO16(off)

enum { L_BG0, L_BG1, L_BG2, L_BG3, L_OBJ, L_BD };

#define TRANSPARENT 0x8000

// Per-line layer buffers: 15-bit colour, or TRANSPARENT.
static u16 sBg[4][GBA_W];
static u16 sObjColor[GBA_W];
static u8  sObjPrio[GBA_W];
static u8  sObjSemi[GBA_W];
static u8  sObjWin[GBA_W];
static u8  sWinMask[GBA_W];

// Affine BG internal reference points (BG2, BG3).
static s32 sRefX[2], sRefY[2];
static u32 sLastRegX[2], sLastRegY[2];

static s32 Sext28(u32 v) { return (s32)(v << 4) >> 4; }

void PpuBeginFrame(void)
{
    int i;
    for (i = 0; i < 2; i++)
    {
        u32 base = 0x28 + i * 0x10;
        sLastRegX[i] = IO32(base);
        sLastRegY[i] = IO32(base + 4);
        sRefX[i] = Sext28(sLastRegX[i]);
        sRefY[i] = Sext28(sLastRegY[i]);
    }
}

// Writing BGxX/Y mid-frame reloads the internal reference on hardware.
static void CheckAffineReload(void)
{
    int i;
    for (i = 0; i < 2; i++)
    {
        u32 base = 0x28 + i * 0x10;
        u32 x = IO32(base), y = IO32(base + 4);
        if (x != sLastRegX[i]) { sLastRegX[i] = x; sRefX[i] = Sext28(x); }
        if (y != sLastRegY[i]) { sLastRegY[i] = y; sRefY[i] = Sext28(y); }
    }
}

void PpuEndHBlank(int line)
{
    int i;
    (void)line;
    for (i = 0; i < 2; i++)
    {
        u32 base = 0x20 + i * 0x10;
        sRefX[i] += (s16)IO16(base + 2); // PB
        sRefY[i] += (s16)IO16(base + 6); // PD
    }
}

static inline u16 Pal(int idx) { return PC_PAL16[idx] & 0x7FFF; }

static void RenderTextBg(int bg, int line)
{
    u16 cnt = R16(0x08 + bg * 2);
    int hofs = R16(0x10 + bg * 4) & 0x1FF;
    int vofs = R16(0x12 + bg * 4) & 0x1FF;
    u32 charBase = ((cnt >> 2) & 3) * 0x4000;
    u32 screenBase = ((cnt >> 8) & 0x1F) * 0x800;
    int is8 = (cnt >> 7) & 1;
    int size = cnt >> 14;
    int w = (size & 1) ? 512 : 256, h = (size & 2) ? 512 : 256;
    int mosH = 1, mosV = 1, x, y;
    u16 *out = sBg[bg];

    if (cnt & 0x40)
    {
        u16 m = R16(0x4C);
        mosH = (m & 0xF) + 1;
        mosV = ((m >> 4) & 0xF) + 1;
    }

    y = ((line - line % mosV) + vofs) & (h - 1);

    for (x = 0; x < GBA_W; x++)
    {
        int sx = x - x % mosH;
        int tx = (sx + hofs) & (w - 1);
        int block = (tx >> 8) + (y >> 8) * (w >> 8);
        u32 mapAddr = screenBase + block * 0x800 + ((y & 255) >> 3) * 64 + ((tx & 255) >> 3) * 2;
        u16 entry = *(volatile u16 *)(PC_VRAM + (mapAddr & 0xFFFF));
        int tile = entry & 0x3FF;
        int px = tx & 7, py = y & 7;
        u32 addr;
        int c;

        if (entry & 0x400) px = 7 - px;
        if (entry & 0x800) py = 7 - py;

        if (is8)
        {
            addr = charBase + tile * 64 + py * 8 + px;
            if (addr >= 0x10000) { out[x] = TRANSPARENT; continue; }
            c = PC_VRAM8[addr];
            out[x] = c ? Pal(c) : TRANSPARENT;
        }
        else
        {
            addr = charBase + tile * 32 + py * 4 + (px >> 1);
            if (addr >= 0x10000) { out[x] = TRANSPARENT; continue; }
            c = PC_VRAM8[addr];
            c = (px & 1) ? (c >> 4) : (c & 0xF);
            out[x] = c ? Pal((entry >> 12) * 16 + c) : TRANSPARENT;
        }
    }
}

static void RenderAffineBg(int bg)
{
    int i = bg - 2;
    u16 cnt = R16(0x08 + bg * 2);
    s32 pa = (s16)R16(0x20 + i * 0x10), pc = (s16)R16(0x24 + i * 0x10);
    u32 charBase = ((cnt >> 2) & 3) * 0x4000;
    u32 screenBase = ((cnt >> 8) & 0x1F) * 0x800;
    int size = 128 << (cnt >> 14);
    int wrap = (cnt >> 13) & 1;
    s32 rx = sRefX[i], ry = sRefY[i];
    u16 *out = sBg[bg];
    int x;

    for (x = 0; x < GBA_W; x++, rx += pa, ry += pc)
    {
        int tx = rx >> 8, ty = ry >> 8, tile, c;
        if (wrap)
        {
            tx &= size - 1;
            ty &= size - 1;
        }
        else if (tx < 0 || ty < 0 || tx >= size || ty >= size)
        {
            out[x] = TRANSPARENT;
            continue;
        }
        tile = PC_VRAM8[(screenBase + (ty >> 3) * (size >> 3) + (tx >> 3)) & 0xFFFF];
        c = PC_VRAM8[(charBase + tile * 64 + (ty & 7) * 8 + (tx & 7)) & 0xFFFF];
        out[x] = c ? Pal(c) : TRANSPARENT;
    }
}

static void RenderBitmapBg(int mode, int line)
{
    u16 *out = sBg[2];
    int frame = (R16(0x00) >> 4) & 1;
    int x;
    for (x = 0; x < GBA_W; x++)
    {
        if (mode == 3)
            out[x] = PC_VRAM16[line * 240 + x] & 0x7FFF;
        else if (mode == 4)
        {
            int c = PC_VRAM8[frame * 0xA000 + line * 240 + x];
            out[x] = c ? Pal(c) : TRANSPARENT;
        }
        else
            out[x] = (x < 160 && line < 128) ? (PC_VRAM16[(frame * 0xA000) / 2 + line * 160 + x] & 0x7FFF) : TRANSPARENT;
    }
}

static const u8 sObjSize[3][4][2] = {
    { { 8, 8 }, { 16, 16 }, { 32, 32 }, { 64, 64 } },
    { { 16, 8 }, { 32, 8 }, { 32, 16 }, { 64, 32 } },
    { { 8, 16 }, { 8, 32 }, { 16, 32 }, { 32, 64 } },
};

static void RenderSprites(int line)
{
    u16 dispcnt = R16(0x00);
    int oneD = (dispcnt >> 6) & 1;
    int bitmapMode = (dispcnt & 7) >= 3;
    int i;

    memset(sObjPrio, 4, sizeof(sObjPrio));
    memset(sObjSemi, 0, sizeof(sObjSemi));
    memset(sObjWin, 0, sizeof(sObjWin));
    for (i = 0; i < GBA_W; i++)
        sObjColor[i] = TRANSPARENT;

    if (!(dispcnt & 0x1000))
        return;

    for (i = 0; i < 128; i++)
    {
        u16 a0 = PC_OAM16[i * 4], a1 = PC_OAM16[i * 4 + 1], a2 = PC_OAM16[i * 4 + 2];
        int affine = (a0 >> 8) & 1;
        int shape = (a0 >> 14) & 3, size = (a1 >> 14) & 3;
        int mode = (a0 >> 10) & 3;
        int is8 = (a0 >> 13) & 1;
        int w, h, bw, bh, y, x, sy, cx, cy, row;
        int tile = a2 & 0x3FF, prio = (a2 >> 10) & 3, palBank = a2 >> 12;
        s32 pa = 0x100, pb = 0, pc = 0, pd = 0x100;

        if (!affine && (a0 & 0x200))
            continue; // disabled
        if (shape == 3 || mode == 3)
            continue;

        w = sObjSize[shape][size][0];
        h = sObjSize[shape][size][1];
        bw = w; bh = h;
        if (affine && (a0 & 0x200)) { bw *= 2; bh *= 2; } // double-size

        y = a0 & 0xFF;
        if (y + bh > 256) y -= 256;
        sy = line - y;
        if (sy < 0 || sy >= bh)
            continue;

        x = a1 & 0x1FF;
        if (x >= 240) x -= 512;

        if (bitmapMode && tile < 512)
            continue;

        if (affine)
        {
            int g = (a1 >> 9) & 0x1F;
            pa = (s16)PC_OAM16[g * 16 + 3];
            pb = (s16)PC_OAM16[g * 16 + 7];
            pc = (s16)PC_OAM16[g * 16 + 11];
            pd = (s16)PC_OAM16[g * 16 + 15];
        }

        row = oneD ? (w / 8) * (is8 ? 2 : 1) : 32;

        for (cx = 0; cx < bw; cx++)
        {
            int px = x + cx, tx, ty, c;
            u32 addr;
            if (px < 0 || px >= GBA_W)
                continue;

            if (affine)
            {
                int dx = cx - bw / 2, dy = sy - bh / 2;
                tx = ((pa * dx + pb * dy) >> 8) + w / 2;
                ty = ((pc * dx + pd * dy) >> 8) + h / 2;
                if (tx < 0 || ty < 0 || tx >= w || ty >= h)
                    continue;
            }
            else
            {
                tx = (a1 & 0x1000) ? w - 1 - cx : cx;
                ty = (a1 & 0x2000) ? h - 1 - sy : sy;
            }

            if (is8)
            {
                int t = (tile & ~1) + (ty >> 3) * row + (tx >> 3) * 2;
                addr = 0x10000 + ((t * 32) & 0x7FFF) + (ty & 7) * 8 + (tx & 7);
                c = PC_VRAM8[addr];
                if (!c) continue;
                c = 256 + c;
            }
            else
            {
                int t = tile + (ty >> 3) * row + (tx >> 3);
                addr = 0x10000 + ((t * 32) & 0x7FFF) + (ty & 7) * 4 + ((tx & 7) >> 1);
                c = PC_VRAM8[addr];
                c = (tx & 1) ? (c >> 4) : (c & 0xF);
                if (!c) continue;
                c = 256 + palBank * 16 + c;
            }

            if (mode == 2)
            {
                sObjWin[px] = 1;
                continue;
            }
            if (sObjColor[px] == TRANSPARENT || prio < sObjPrio[px])
            {
                sObjColor[px] = Pal(c);
                sObjPrio[px] = prio;
                sObjSemi[px] = mode == 1;
            }
        }
    }
}

static int InRange(int v, int a, int b)
{
    return a <= b ? (v >= a && v < b) : (v >= a || v < b);
}

static void BuildWindowMask(int line)
{
    u16 dispcnt = R16(0x00);
    int win0 = (dispcnt >> 13) & 1, win1 = (dispcnt >> 14) & 1, winObj = (dispcnt >> 15) & 1;
    u16 winin = R16(0x48), winout = R16(0x4A);
    int in0 = 0, in1 = 0, x;
    int x0a = R16(0x40) >> 8, x0b = R16(0x40) & 0xFF;
    int x1a = R16(0x42) >> 8, x1b = R16(0x42) & 0xFF;

    if (!win0 && !win1 && !winObj)
    {
        memset(sWinMask, 0x3F, sizeof(sWinMask));
        return;
    }
    if (x0b > 240) x0b = 240;
    if (x1b > 240) x1b = 240;
    if (win0) in0 = InRange(line, R16(0x44) >> 8, R16(0x44) & 0xFF);
    if (win1) in1 = InRange(line, R16(0x46) >> 8, R16(0x46) & 0xFF);

    for (x = 0; x < GBA_W; x++)
    {
        if (in0 && InRange(x, x0a, x0b))
            sWinMask[x] = winin & 0x3F;
        else if (in1 && InRange(x, x1a, x1b))
            sWinMask[x] = (winin >> 8) & 0x3F;
        else if (winObj && sObjWin[x])
            sWinMask[x] = (winout >> 8) & 0x3F;
        else
            sWinMask[x] = winout & 0x3F;
    }
}

static u16 Blend(u16 a, u16 b, int eva, int evb)
{
    int r = ((a & 31) * eva + (b & 31) * evb) >> 4;
    int g = (((a >> 5) & 31) * eva + ((b >> 5) & 31) * evb) >> 4;
    int bl = (((a >> 10) & 31) * eva + ((b >> 10) & 31) * evb) >> 4;
    if (r > 31) r = 31;
    if (g > 31) g = 31;
    if (bl > 31) bl = 31;
    return r | (g << 5) | (bl << 10);
}

static u16 Brighten(u16 c, int evy)
{
    int r = c & 31, g = (c >> 5) & 31, b = (c >> 10) & 31;
    r += ((31 - r) * evy) >> 4;
    g += ((31 - g) * evy) >> 4;
    b += ((31 - b) * evy) >> 4;
    return r | (g << 5) | (b << 10);
}

static u16 Darken(u16 c, int evy)
{
    int r = c & 31, g = (c >> 5) & 31, b = (c >> 10) & 31;
    r -= (r * evy) >> 4;
    g -= (g * evy) >> 4;
    b -= (b * evy) >> 4;
    return r | (g << 5) | (b << 10);
}

static inline u32 ToRgb(u16 c)
{
    u32 r = c & 31, g = (c >> 5) & 31, b = (c >> 10) & 31;
    r = (r << 3) | (r >> 2);
    g = (g << 3) | (g >> 2);
    b = (b << 3) | (b >> 2);
    return 0xFF000000u | (r << 16) | (g << 8) | b;
}

void PpuRenderLine(int line, u32 *out)
{
    u16 dispcnt = R16(0x00);
    int mode = dispcnt & 7;
    int bgOn[4] = { 0, 0, 0, 0 };
    int bgPrio[4];
    u16 bldcnt = R16(0x50), bldalpha = R16(0x52);
    int effect = (bldcnt >> 6) & 3;
    int eva = bldalpha & 0x1F, evb = (bldalpha >> 8) & 0x1F, evy = R16(0x54) & 0x1F;
    u16 backdrop = Pal(0);
    int i, x;

    if (eva > 16) eva = 16;
    if (evb > 16) evb = 16;
    if (evy > 16) evy = 16;

    CheckAffineReload();

    if (dispcnt & 0x80)
    {
        for (x = 0; x < GBA_W; x++)
            out[x] = 0xFFFFFFFFu;
        return;
    }

    for (i = 0; i < 4; i++)
    {
        bgOn[i] = (dispcnt >> (8 + i)) & 1;
        bgPrio[i] = R16(0x08 + i * 2) & 3;
    }

    switch (mode)
    {
    case 0:
        for (i = 0; i < 4; i++) if (bgOn[i]) RenderTextBg(i, line);
        break;
    case 1:
        if (bgOn[0]) RenderTextBg(0, line);
        if (bgOn[1]) RenderTextBg(1, line);
        if (bgOn[2]) RenderAffineBg(2);
        bgOn[3] = 0;
        break;
    case 2:
        bgOn[0] = bgOn[1] = 0;
        if (bgOn[2]) RenderAffineBg(2);
        if (bgOn[3]) RenderAffineBg(3);
        break;
    default:
        bgOn[0] = bgOn[1] = bgOn[3] = 0;
        if (bgOn[2]) RenderBitmapBg(mode, line);
        break;
    }

    RenderSprites(line);
    BuildWindowMask(line);

    for (x = 0; x < GBA_W; x++)
    {
        int mask = sWinMask[x];
        int topL = L_BD, botL = L_BD, p, found = 0;
        u16 top = backdrop, bot = backdrop;
        u16 c;

        // Walk priorities front to back; take the first two opaque layers.
        for (p = 0; p < 4 && found < 2; p++)
        {
            if (sObjColor[x] != TRANSPARENT && sObjPrio[x] == p && (mask & 0x10))
            {
                if (found == 0) { top = sObjColor[x]; topL = L_OBJ; }
                else { bot = sObjColor[x]; botL = L_OBJ; }
                found++;
            }
            for (i = 0; i < 4 && found < 2; i++)
            {
                if (bgOn[i] && bgPrio[i] == p && (mask & (1 << i)) && sBg[i][x] != TRANSPARENT)
                {
                    if (found == 0) { top = sBg[i][x]; topL = i; }
                    else { bot = sBg[i][x]; botL = i; }
                    found++;
                }
            }
        }

        c = top;
        if (mask & 0x20)
        {
            int topIs1st = (bldcnt >> topL) & 1;
            int botIs2nd = (bldcnt >> (8 + botL)) & 1;

            if (topL == L_OBJ && sObjSemi[x] && botIs2nd)
                c = Blend(top, bot, eva, evb);
            else if (topIs1st)
            {
                if (effect == 1 && botIs2nd)
                    c = Blend(top, bot, eva, evb);
                else if (effect == 2)
                    c = Brighten(top, evy);
                else if (effect == 3)
                    c = Darken(top, evy);
            }
        }
        out[x] = ToRgb(c);
    }
}
