// Scanline renderer for the GBA picture processor. Reads the game's VRAM,
// palette RAM, OAM and display registers exactly as the hardware would, so
// mid-frame (HBlank) effects work unchanged.
//
// Widescreen: the output can be wider than 240 px. The GBA's 240-pixel
// screen sits in the centre (GBA x = output x - margin). On the overworld,
// the map layers are read from a 64-tile-wide buffer (gPcFieldMap) so the
// margins show real map, and sprites extend into them; the UI layer and
// everything else stays inside the centre. Other screens are pillarboxed.
#include <string.h>
#include "port.h"
#include "hdpack.h"
#include "texthd.h"
#include "fieldfx.h"

typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;
typedef int16_t s16; typedef int32_t s32;

#define R16(off) IO16(off)

enum { L_BG0, L_BG1, L_BG2, L_BG3, L_OBJ, L_BD };

#define TRANSPARENT 0x8000
#define POPUP_W 96 // map-name sign size including its frame
#define POPUP_H 40

int gPcScreenW = GBA_W;
uint16_t *gPcFieldMap[4];
uint8_t gPcFieldMapBase[4];

// Per-line layer buffers: 15-bit colour, or TRANSPARENT. Index = output x.
static u16 sBg[4][PC_MAX_W];
static u16 sObjColor[PC_MAX_W];
static u8  sObjPrio[PC_MAX_W];
static u8  sObjSemi[PC_MAX_W];
static u8  sObjWin[PC_MAX_W];
static u8  sObjHidden[PC_MAX_W]; // pixel comes from a weather sprite the HD renderer redraws
static u8  sWinMask[PC_MAX_W];

// HD pack tile references for the current line (see PpuLayers.tref).
static u16 sRefSlot[5][PC_MAX_W];
static u8  sRefInfo[5][PC_MAX_W];
static u16 sRefUnfaded[5][PC_MAX_W];
static int sDoRefs;
static int sHideThis;

// Result of compositing each pixel of the current line (used by the layer
// export to hide pixels the GBA never shows from the HD upscaler).
static u8  sTopLayer[PC_MAX_W];   // L_BG0..L_BD
static u8  sBlended[PC_MAX_W];    // pixel used a two-layer colour effect
static u16 sFinal[PC_MAX_W];

// Per-line geometry. sWide: overworld widescreen; sBattle: battle widescreen
// (backgrounds extended by repeating their edges, message box stretched).
static int sW, sMargin, sWide, sBattle;

// Affine BG internal reference points (BG2, BG3).
static s32 sRefX[2], sRefY[2];
static u32 sLastRegX[2], sLastRegY[2];

static s32 Sext28(u32 v) { return (s32)(v << 4) >> 4; }

int PcFieldWideActive(void)
{
    return gPcFieldMap[1] || gPcFieldMap[2] || gPcFieldMap[3];
}

int gPpuBattleBoxTop = GBA_H;     // battles: first line where the message box reaches the screen edge
static int sBoxTopThisFrame = GBA_H;

void PpuBeginFrame(void)
{
    int i;
    sBoxTopThisFrame = GBA_H;
    HdPackBeginFrame();
    PcTextBeginFrame();
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

static void ClearRow(u16 *row)
{
    int x;
    for (x = 0; x < sW; x++)
        row[x] = TRANSPARENT;
}

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
    u16 *refSlot = sRefSlot[bg];
    u8 *refInfo = sRefInfo[bg];
    u16 *refU = sRefUnfaded[bg];
    const u16 *fieldMap = NULL;
    int x0 = sMargin, x1 = sMargin + GBA_W;

    if ((sBattle && bg == 0) || (sWide && bg == 0 && gPcMapPopup))
    {
        x0 = 0;
        x1 = sW;
    }
    // Overworld map layers: read the wide map buffer and fill the margins.
    if (sWide && gPcFieldMap[bg] && ((cnt >> 8) & 0x1F) == gPcFieldMapBase[bg])
    {
        fieldMap = gPcFieldMap[bg];
        w = 512;
        h = 256;
        x0 = 0;
        x1 = sW;
    }

    if (cnt & 0x40)
    {
        u16 m = R16(0x4C);
        mosH = (m & 0xF) + 1;
        mosV = ((m >> 4) & 0xF) + 1;
    }

    y = ((line - line % mosV) + vofs) & (h - 1);

    for (x = 0; x < sW; x++)
    {
        int gx, sx, tx, tile, px, py, c;
        u16 entry;
        u32 addr;

        if (x < x0 || x >= x1)
        {
            out[x] = TRANSPARENT;
            continue;
        }
        gx = x - sMargin;
        if (sBattle && bg == 0)
        {
            // Message box: its 8-pixel frame moves to the screen edges and
            // the interior widens to fill the space in between.
            if (x < 8)
                gx = x;
            else if (x < sMargin + 8)
                gx = 8;
            else if (x >= sW - 8)
                gx = GBA_W - (sW - x);
            else if (x >= sMargin + GBA_W - 8)
                gx = GBA_W - 9;
        }
        else if (sWide && bg == 0 && gPcMapPopup)
        {
            // Map-name sign (BG0 tiles 0-11 x 0-4): draw it in the true top-left
            // corner of the wide screen and hide it at its original place.
            int inSign = (y & 255) < POPUP_H;
            if (inSign && x < POPUP_W)
                gx = x;
            else if (gx < 0 || gx >= GBA_W || (inSign && gx < POPUP_W))
            {
                out[x] = TRANSPARENT;
                if (sDoRefs) refSlot[x] = 0;
                continue;
            }
        }
        sx = gx - ((gx % mosH) + mosH) % mosH;
        tx = (sx + hofs) & (w - 1);
        if (fieldMap)
        {
            entry = fieldMap[(y >> 3) * 64 + (tx >> 3)];
        }
        else
        {
            int block = (tx >> 8) + (y >> 8) * (w >> 8);
            u32 mapAddr = screenBase + block * 0x800 + ((y & 255) >> 3) * 64 + ((tx & 255) >> 3) * 2;
            entry = *(volatile u16 *)(PC_VRAM + (mapAddr & 0xFFFF));
        }
        tile = entry & 0x3FF;
        px = tx & 7;
        py = y & 7;

        if (entry & 0x400) px = 7 - px;
        if (entry & 0x800) py = 7 - py;

        if (sDoRefs)
            refSlot[x] = 0;
        if (is8)
        {
            addr = charBase + tile * 64 + py * 8 + px;
            if (addr >= 0x10000) { out[x] = TRANSPARENT; continue; }
            c = PC_VRAM8[addr];
            out[x] = c ? Pal(c) : TRANSPARENT;
            if (sDoRefs && c)
            {
                refSlot[x] = HdPackLookup(charBase + tile * 64, 1, 0);
                refU[x] = HdPackUnfaded(c);
            }
        }
        else
        {
            addr = charBase + tile * 32 + py * 4 + (px >> 1);
            if (addr >= 0x10000) { out[x] = TRANSPARENT; continue; }
            c = PC_VRAM8[addr];
            c = (px & 1) ? (c >> 4) : (c & 0xF);
            out[x] = c ? Pal((entry >> 12) * 16 + c) : TRANSPARENT;
            if (sDoRefs && c)
            {
                u32 tag = gPcTextHd ? gPcTextTags[(addr << 1) | (px & 1)] : 0;
                if (tag && PcTextExpected(tag) == c && PcTextTileOk(addr >> 5))
                {
                    // High-resolution text: glyph slot, position in glyph, colours.
                    refSlot[x] = 0x8000 | PC_TEXT_TAG_SLOT(tag);
                    refInfo[x] = PC_TEXT_TAG_LX(tag) | (PC_TEXT_TAG_LY(tag) << 4);
                    refU[x] = PC_TEXT_TAG_FG(tag) | (PC_TEXT_TAG_SH(tag) << 4)
                            | (PC_TEXT_TAG_BG(tag) << 8) | ((entry >> 12) << 12);
                    continue;
                }
                refSlot[x] = HdPackLookup(charBase + tile * 32, 0, (entry >> 12) * 16);
                refU[x] = HdPackUnfaded((entry >> 12) * 16 + c);
            }
        }
        if (sDoRefs)
            refInfo[x] = px | (py << 3) | ((entry & 0x400) ? 64 : 0) | ((entry & 0x800) ? 128 : 0);
    }

    // Battle backgrounds: mirror the scene into the margins; the renderer
    // blurs that area so it reads as out-of-focus scenery, not stretched art.
    if (sBattle && bg != 0)
    {
        for (x = 0; x < sMargin; x++)
        {
            int src = 2 * sMargin - 1 - x;            // mirror about the left edge
            out[x] = out[src < sMargin + GBA_W ? src : sMargin];
            if (sDoRefs) refSlot[x] = 0;
        }
        for (x = sMargin + GBA_W; x < sW; x++)
        {
            int src = 2 * (sMargin + GBA_W) - 1 - x;  // mirror about the right edge
            out[x] = out[src >= sMargin ? src : sMargin + GBA_W - 1];
            if (sDoRefs) refSlot[x] = 0;
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

    ClearRow(out);
    memset(sRefSlot[bg], 0, sizeof(sRefSlot[bg]));
    for (x = sMargin; x < sMargin + GBA_W; x++, rx += pa, ry += pc)
    {
        int tx = rx >> 8, ty = ry >> 8, tile, c;
        if (wrap)
        {
            tx &= size - 1;
            ty &= size - 1;
        }
        else if (tx < 0 || ty < 0 || tx >= size || ty >= size)
        {
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
    int gx;
    ClearRow(out);
    memset(sRefSlot[2], 0, sizeof(sRefSlot[2]));
    for (gx = 0; gx < GBA_W; gx++)
    {
        u16 c;
        if (mode == 3)
            c = PC_VRAM16[line * 240 + gx] & 0x7FFF;
        else if (mode == 4)
        {
            int i = PC_VRAM8[frame * 0xA000 + line * 240 + gx];
            c = i ? Pal(i) : TRANSPARENT;
        }
        else
            c = (gx < 160 && line < 128) ? (PC_VRAM16[(frame * 0xA000) / 2 + line * 160 + gx] & 0x7FFF) : TRANSPARENT;
        out[gx + sMargin] = c;
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
    // Sprites may extend into the margins on the wide overworld and in battle.
    int wideNow = sWide || sBattle;
    int xmin = wideNow ? 0 : sMargin, xmax = wideNow ? sW : sMargin + GBA_W;
    // A 9-bit X decodes as negative past the right edge of the visible area.
    int xWrap = GBA_W + (wideNow ? sMargin : 0);
    int i;

    memset(sObjPrio, 4, sW);
    if (sDoRefs)
        memset(sRefSlot[4], 0, sizeof(sRefSlot[4]));
    memset(sObjSemi, 0, sW);
    memset(sObjWin, 0, sW);
    memset(sObjHidden, 0, sW);
    ClearRow(sObjColor);

    if (!(dispcnt & 0x1000))
        return;

    for (i = 0; i < 128; i++)
    {
        u16 a0 = PC_OAM16[i * 4], a1 = PC_OAM16[i * 4 + 1], a2 = PC_OAM16[i * 4 + 2];
        int affine = (a0 >> 8) & 1;
        int shape = (a0 >> 14) & 3, size = (a1 >> 14) & 3;
        int mode = (a0 >> 10) & 3;
        int is8 = (a0 >> 13) & 1;
        int w, h, bw, bh, y, x, sy, cx, row;
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
        if (x >= xWrap) x -= 512;

        if (bitmapMode && tile < 512)
            continue;
        {
            int hide = 0, k;
            if (gPcHdEffects && sWide)
                for (k = 0; k < 2; k++)
                    if (gPcFieldFx.hideTileCount[k] && tile >= gPcFieldFx.hideTileStart[k]
                     && tile < gPcFieldFx.hideTileStart[k] + gPcFieldFx.hideTileCount[k])
                        hide = 1;
            sHideThis = hide;
        }

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
            int px = x + cx + sMargin, tx, ty, c;
            u32 addr;
            if (px < xmin || px >= xmax)
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

            u32 tileAddr;
            int palBase;
            if (is8)
            {
                int t = (tile & ~1) + (ty >> 3) * row + (tx >> 3) * 2;
                tileAddr = 0x10000 + ((t * 32) & 0x7FFF);
                addr = tileAddr + (ty & 7) * 8 + (tx & 7);
                c = PC_VRAM8[addr];
                if (!c) continue;
                palBase = 256;
                c = 256 + c;
            }
            else
            {
                int t = tile + (ty >> 3) * row + (tx >> 3);
                tileAddr = 0x10000 + ((t * 32) & 0x7FFF);
                addr = tileAddr + (ty & 7) * 4 + ((tx & 7) >> 1);
                c = PC_VRAM8[addr];
                c = (tx & 1) ? (c >> 4) : (c & 0xF);
                if (!c) continue;
                palBase = 256 + palBank * 16;
                c = palBase + c;
            }

            if (mode == 2)
            {
                sObjWin[px] = 1;
                continue;
            }
            if (sObjColor[px] == TRANSPARENT || prio < sObjPrio[px])
            {
                sObjHidden[px] = sHideThis;
                sObjColor[px] = Pal(c);
                sObjPrio[px] = prio;
                sObjSemi[px] = mode == 1;
                if (sDoRefs)
                {
                    // Rotated/scaled sprites keep the xBR upscale.
                    sRefSlot[4][px] = affine ? 0 : HdPackLookup(tileAddr, is8, palBase);
                    sRefInfo[4][px] = (tx & 7) | ((ty & 7) << 3)
                                    | ((a1 & 0x1000) ? 64 : 0) | ((a1 & 0x2000) ? 128 : 0);
                    sRefUnfaded[4][px] = HdPackUnfaded(c);
                }
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
        memset(sWinMask, 0x3F, sW);
        return;
    }
    if (x0b > 240) x0b = 240;
    if (x1b > 240) x1b = 240;
    if (win0) in0 = InRange(line, R16(0x44) >> 8, R16(0x44) & 0xFF);
    if (win1) in1 = InRange(line, R16(0x46) >> 8, R16(0x46) & 0xFF);

    for (x = 0; x < sW; x++)
    {
        // Widescreen margins take the window state of the nearest edge
        // column, so full-width windows extend to the edges of the output.
        int gx = x - sMargin;
        if (gx < 0) gx = 0;
        if (gx >= GBA_W) gx = GBA_W - 1;
        if (in0 && InRange(gx, x0a, x0b))
            sWinMask[x] = winin & 0x3F;
        else if (in1 && InRange(gx, x1a, x1b))
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

struct PpuLayers gPpuLayers;
int gPpuExportLayers;
int gPpuContentX0, gPpuContentX1; // visible content range for the HD compositor

static inline u32 ToRgba(u16 c)
{
    u32 r = c & 31, g = (c >> 5) & 31, b = (c >> 10) & 31;
    r = (r << 3) | (r >> 2);
    g = (g << 3) | (g >> 2);
    b = (b << 3) | (b >> 2);
    return 0xFF000000u | (b << 16) | (g << 8) | r;
}

// line[y][0]: backdrop colour (RGBA)
// line[y][1]: byte0 layer enables (bits 0-3 BG, bit 4 OBJ), byte1 BG priorities
//             (2 bits each), byte2 flags (bit 0 forced blank)
// line[y][2]: BLDCNT (low 16 bits), EVA (byte 2), EVB (byte 3)
// line[y][3]: EVY (byte 0), effect mode (byte 1)
static void ExportLine(int line, const int *bgOn, const int *bgPrio, int forcedBlank,
                       u16 bldcnt, int eva, int evb, int evy, int effect)
{
    u32 *L = gPpuLayers.line[line];
    u32 en = 0, pr = 0;
    int i, x;

    for (i = 0; i < 4; i++)
    {
        if (bgOn[i]) en |= 1u << i;
        pr |= (u32)(bgPrio[i] & 3) << (i * 2);
    }
    if (R16(0x00) & 0x1000) en |= 1u << 4;
    L[0] = ToRgba(Pal(0));
    L[1] = en | (pr << 8) | ((u32)(forcedBlank ? 1 : 0) << 16);
    L[2] = bldcnt | ((u32)eva << 16) | ((u32)evb << 24);
    L[3] = (u32)evy | ((u32)effect << 8);

    if (forcedBlank)
        return;

    if (gHdPackActive || gPcTextHd)
    {
        for (i = 0; i < 5; i++)
        {
            u16 (*t)[4] = gPpuLayers.tref[i][line];
            const u16 *col = i < 4 ? sBg[i] : sObjColor;
            int on = i < 4 ? bgOn[i] : 1;
            for (x = 0; x < sW; x++)
            {
                if (!on || col[x] == TRANSPARENT || !sRefSlot[i][x])
                {
                    t[x][0] = 0;
                    continue;
                }
                t[x][0] = sRefSlot[i][x];
                t[x][1] = sRefInfo[i][x];
                t[x][2] = sRefUnfaded[i][x];
                t[x][3] = col[x];
            }
        }
    }

    for (i = 0; i < 4; i++)
    {
        u32 *dst = gPpuLayers.layer[i][line];
        if (!bgOn[i])
        {
            memset(dst, 0, sW * 4);
            continue;
        }
        for (x = 0; x < sW; x++)
        {
            u16 c = sBg[i][x];
            if (c == TRANSPARENT)
                dst[x] = 0;
            else if (sTopLayer[x] != i && !sBlended[x])
                dst[x] = ToRgba(sFinal[x]); // hidden: what is actually visible here
            else
                dst[x] = ToRgba(c);
        }
    }
    {
        u32 *dst = gPpuLayers.layer[4][line];
        u32 *meta = gPpuLayers.meta[line];
        for (x = 0; x < sW; x++)
        {
            if (sObjColor[x] == TRANSPARENT || sObjHidden[x])
                dst[x] = 0;
            else if (sTopLayer[x] != L_OBJ && !sBlended[x])
                dst[x] = ToRgba(sFinal[x]);
            else
                dst[x] = ToRgba(sObjColor[x]);
            u32 opaque = 0;
            int b;
            // Which layers are opaque at this original pixel (B channel): the
            // compositor keeps them fully opaque so upscaled edges can't let
            // hidden pixels underneath show through.
            for (b = 0; b < 4; b++)
                if (bgOn[b] && sBg[b][x] != TRANSPARENT)
                    opaque |= 1u << b;
            if (sObjColor[x] != TRANSPARENT && !sObjHidden[x])
                opaque |= 16;
            meta[x] = sWinMask[x] | ((u32)((sObjPrio[x] & 3) | (sObjSemi[x] ? 4 : 0)) << 8) | (opaque << 16);
        }
    }
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
    int i, x, cx0, cx1;

    sW = gPcScreenW;
    sMargin = (sW - GBA_W) / 2;
    sWide = sMargin > 0 && PcFieldWideActive();
    sBattle = sMargin > 0 && !sWide && gPcBattleFrame;
    sDoRefs = gHdPackActive || gHdDumpEnabled || gPcTextHd;
    if (sDoRefs)
        for (i = 0; i < 4; i++)
            memset(sRefSlot[i], 0, sW * sizeof(u16));
    cx0 = (sWide || sBattle) ? 0 : sMargin;
    cx1 = (sWide || sBattle) ? sW : sMargin + GBA_W;
    gPpuContentX0 = cx0;
    gPpuContentX1 = cx1;

    if (eva > 16) eva = 16;
    if (evb > 16) evb = 16;
    if (evy > 16) evy = 16;

    CheckAffineReload();

    for (i = 0; i < 4; i++)
    {
        bgOn[i] = (dispcnt >> (8 + i)) & 1;
        bgPrio[i] = R16(0x08 + i * 2) & 3;
    }

    if (dispcnt & 0x80)
    {
        for (x = 0; x < sW; x++)
            out[x] = (x >= cx0 && x < cx1) ? 0xFFFFFFFFu : 0xFF000000u;
        if (gPpuExportLayers)
            ExportLine(line, bgOn, bgOn, 1, 0, 0, 0, 0, 0);
        return;
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

    for (x = 0; x < sW; x++)
    {
        int mask = sWinMask[x];
        int topL = L_BD, botL = L_BD, p, found = 0;
        u16 top = backdrop, bot = backdrop;
        u16 c;

        sTopLayer[x] = L_BD;
        sBlended[x] = 0;
        if (x < cx0 || x >= cx1)
        {
            out[x] = 0xFF000000u; // pillarbox
            sFinal[x] = 0;
            continue;
        }

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
            {
                c = Blend(top, bot, eva, evb);
                sBlended[x] = 1;
            }
            else if (topIs1st)
            {
                if (effect == 1 && botIs2nd)
                {
                    c = Blend(top, bot, eva, evb);
                    sBlended[x] = 1;
                }
                else if (effect == 2)
                    c = Brighten(top, evy);
                else if (effect == 3)
                    c = Darken(top, evy);
            }
        }
        sTopLayer[x] = topL;
        // Keep the un-faded colour of the top layer: brightness fades are
        // applied again by the HD compositor.
        sFinal[x] = top;
        out[x] = ToRgb(c);
    }

    if (sBattle && bgOn[0] && sBg[0][0] != TRANSPARENT && line < sBoxTopThisFrame)
        sBoxTopThisFrame = line;
    if (line == GBA_H - 1)
        gPpuBattleBoxTop = sBattle ? sBoxTopThisFrame : GBA_H;

    if (gPpuExportLayers)
        ExportLine(line, bgOn, bgPrio, 0, bldcnt, eva, evb, evy, effect);
}
