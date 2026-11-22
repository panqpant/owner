// PC platform core: process entry, GBA memory map, frame/scanline loop,
// interrupt dispatch and DMA emulation.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "port.h"

#ifdef _WIN32
#include <windows.h>
#include <process.h>
#else
#include <sys/mman.h>
#include <unistd.h>
#endif

typedef void (*IntrFunc)(void);
extern IntrFunc gIntrTable[];
void AgbMain(void);
void NullGuardInstall(void);

// ---------------------------------------------------------------------------
// Memory map

static void MapRegion(uint32_t addr, uint32_t size)
{
#ifdef _WIN32
    void *p = VirtualAlloc((void *)(uintptr_t)addr, size, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
#else
    void *p = mmap((void *)(uintptr_t)addr, size, PROT_READ | PROT_WRITE,
                   MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE, -1, 0);
    if (p == MAP_FAILED)
        p = NULL;
#endif
    if (p != (void *)(uintptr_t)addr)
    {
        fprintf(stderr, "fatal: could not map GBA memory at 0x%08X\n", addr);
        exit(1);
    }
    memset(p, 0, size);
}

void PortMapMemory(void)
{
    MapRegion(PC_EWRAM, 0x40000);
    MapRegion(PC_IWRAM, 0x8000);
    MapRegion(PC_IO,    0x1000);
    MapRegion(PC_PLTT,  0x1000);
    MapRegion(PC_VRAM,  0x18000);
    MapRegion(PC_OAM,   0x1000);
}

// ---------------------------------------------------------------------------
// Interrupts

enum {
    IRQ_VBLANK = 1 << 0, IRQ_HBLANK = 1 << 1, IRQ_VCOUNT = 1 << 2,
    IRQ_TIMER3 = 1 << 6, IRQ_SERIAL = 1 << 7,
};

#define REG_DISPSTAT_OFF 0x004
#define REG_VCOUNT_OFF   0x006
#define REG_KEYINPUT_OFF 0x130
#define REG_IE_OFF       0x200
#define REG_IF_OFF       0x202
#define REG_IME_OFF      0x208
#define REG_TM1CNT_L_OFF 0x104
#define REG_TM1CNT_H_OFF 0x106

static int sInIrq;
int gPcBattleFrame;   // the frame being drawn belongs to a battle
static int sBattleSeen; // the battle loop ran during the current frame

static void RaiseIrq(uint16_t flag)
{
    int idx;

    if (sInIrq || !(IO16(REG_IME_OFF) & 1) || !(IO16(REG_IE_OFF) & flag))
        return;

    // Same slot order as the game's IntrMain dispatcher.
    switch (flag)
    {
    case IRQ_VCOUNT: idx = 0; break;
    case IRQ_SERIAL: idx = 1; break;
    case IRQ_TIMER3: idx = 2; break;
    case IRQ_HBLANK: idx = 3; break;
    case IRQ_VBLANK: idx = 4; break;
    default: return;
    }
    if (!gIntrTable[idx])
        return;

    sInIrq = 1;
    IO16(REG_IME_OFF) = 0;
    gIntrTable[idx]();
    IO16(REG_IME_OFF) = 1;
    sInIrq = 0;
}

// ---------------------------------------------------------------------------
// DMA

struct DmaChan {
    uint32_t src, dst, count;
};
static struct DmaChan sDma[4];

static uint32_t DmaRegBase(int n) { return 0xB0 + n * 12; }

static void DmaTransfer(int n)
{
    struct DmaChan *ch = &sDma[n];
    uint32_t base = DmaRegBase(n);
    uint16_t cnt = IO16(base + 10);
    int unit = (cnt & 0x0400) ? 4 : 2;
    int dstMode = (cnt >> 5) & 3, srcMode = (cnt >> 7) & 3;
    int srcStep = srcMode == 0 ? unit : srcMode == 1 ? -unit : 0;
    int dstStep = dstMode == 1 ? -unit : dstMode == 2 ? 0 : unit;
    uint32_t count = ch->count, i;

    if (unit == 4)
    {
        for (i = 0; i < count; i++)
        {
            *(volatile uint32_t *)(uintptr_t)(ch->dst & ~3u) = *(volatile uint32_t *)(uintptr_t)(ch->src & ~3u);
            ch->src += srcStep;
            ch->dst += dstStep;
        }
    }
    else
    {
        for (i = 0; i < count; i++)
        {
            *(volatile uint16_t *)(uintptr_t)(ch->dst & ~1u) = *(volatile uint16_t *)(uintptr_t)(ch->src & ~1u);
            ch->src += srcStep;
            ch->dst += dstStep;
        }
    }

    if ((cnt & 0x0200) && ((cnt >> 12) & 3) != 0) // repeat
    {
        uint32_t c = IO16(base + 8);
        ch->count = c ? c : (n == 3 ? 0x10000 : 0x4000);
        if (dstMode == 3)
            ch->dst = IO32(base + 4);
    }
    else
    {
        IO16(base + 10) = cnt & ~0x8000;
    }
}

void PortDmaSet(int n, uint32_t src, uint32_t dst, uint32_t control)
{
    uint32_t base = DmaRegBase(n);
    uint16_t cnt = control >> 16;
    uint32_t c = control & 0xFFFF;

    IO32(base) = src;
    IO32(base + 4) = dst;
    IO16(base + 8) = control & 0xFFFF;
    IO16(base + 10) = cnt;

    if (!(cnt & 0x8000))
        return;

    sDma[n].src = src;
    sDma[n].dst = dst;
    sDma[n].count = c ? c : (n == 3 ? 0x10000 : 0x4000);

    if (((cnt >> 12) & 3) == 0)
        DmaTransfer(n);
}

void PortDmaRunTiming(int timing)
{
    int n;
    for (n = 0; n < 4; n++)
    {
        uint16_t cnt = IO16(DmaRegBase(n) + 10);
        if ((cnt & 0x8000) && ((cnt >> 12) & 3) == timing)
            DmaTransfer(n);
    }
}

// ---------------------------------------------------------------------------
// Frame loop. The game spends its frame in logic, then calls VBlankIntrWait;
// we then run the scanlines up to the next VBlank, rendering as we go.

static uint32_t sFrameBuffer[GBA_H * PC_MAX_W];
static int sLine = 161;
static uint32_t sFrameCount;

uint32_t PortFrameCount(void) { return sFrameCount; }

static void StepLine(int line)
{
    uint16_t stat = IO16(REG_DISPSTAT_OFF);
    int lyc = stat >> 8;

    IO16(REG_VCOUNT_OFF) = line;
    stat &= ~7;
    if (line >= 160 && line < 227)
        stat |= 1;
    if (line == lyc)
        stat |= 4;
    IO16(REG_DISPSTAT_OFF) = stat;

    if (line == lyc && (stat & 0x20))
        RaiseIrq(IRQ_VCOUNT);

    if (line == 0)
        PpuBeginFrame();

    if (line < 160)
    {
        PpuRenderLine(line, &sFrameBuffer[line * gPcScreenW]);
    }
    else if (line == 160)
    {
        uint16_t keys;

        FrontendPresent(sFrameBuffer);
        if (FrontendShouldQuit())
            exit(0);
        keys = FrontendPollKeys();
        IO16(REG_KEYINPUT_OFF) = (~keys) & 0x3FF;
        if (IO16(REG_TM1CNT_H_OFF) & 0x80)
            IO16(REG_TM1CNT_L_OFF) += (uint16_t)280896;
        sFrameCount++;

        PortDmaRunTiming(1);
        if (IO16(REG_DISPSTAT_OFF) & 0x08)
            RaiseIrq(IRQ_VBLANK);
        // The frame just shown was a battle if the battle loop ran during it.
        gPcBattleFrame = sBattleSeen;
        sBattleSeen = 0;
    }

    if (line < 160)
    {
        PortDmaRunTiming(2);
        PpuEndHBlank(line);
    }
    IO16(REG_DISPSTAT_OFF) |= 2;
    if (IO16(REG_DISPSTAT_OFF) & 0x10)
        RaiseIrq(IRQ_HBLANK);
    IO16(REG_DISPSTAT_OFF) &= ~2;
}

void PortRunFrame(void)
{
    for (;;)
    {
        if (++sLine >= 228)
            sLine = 0;
        StepLine(sLine);
        if (sLine == 160)
            break;
    }
    // Game logic resumes at the start of VBlank, as on hardware.
    sLine = 161;
    IO16(REG_VCOUNT_OFF) = 161;
}

// ---------------------------------------------------------------------------
// Widescreen hooks called from game code (PLATFORM_PC).

void PcSetFieldMaps(uint16_t *bg1, uint16_t *bg2, uint16_t *bg3, int base1, int base2, int base3)
{
    gPcFieldMap[1] = bg1; gPcFieldMapBase[1] = base1;
    gPcFieldMap[2] = bg2; gPcFieldMapBase[2] = base2;
    gPcFieldMap[3] = bg3; gPcFieldMapBase[3] = base3;
}

int gPcOutdoors;
void PcMarkBattleFrame(void) { sBattleSeen = 1; }
int gPcIntroSerial, gPcIntroKind;
// Wild battles get one of five gentle intros, trainers one of four bolder
// ones, legendaries and gym leaders the full shatter.
void PcBattleIntro(void)
{
    extern uint32_t gBattleTypeFlags;
    static uint32_t rng = 2463534242u;
    rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5;
    if (gBattleTypeFlags & ((1u << 12) | (1u << 13) | (1u << 14) | (1u << 28) | (1u << 29) | (1u << 30))   /* Kyogre/Groudon, legendary, Regi, Groudon, Kyogre, Rayquaza */)
        gPcIntroKind = 9;
    else if (gBattleTypeFlags & 0x8 /* TRAINER */)
        gPcIntroKind = 5 + rng % 4;
    else
        gPcIntroKind = rng % 5;
    if (getenv("EMERALD_INTRO"))
        gPcIntroKind = atoi(getenv("EMERALD_INTRO"));
    gPcIntroSerial++;
}
int gPcMapPopup;
void PcSetMapPopup(int shown) { gPcMapPopup = shown; }
void PcSetOutdoors(int outdoors) { gPcOutdoors = outdoors; }

// Extra pixels visible on each side of the GBA screen on the overworld.
int PcFieldMargin(void)
{
    if (gPcScreenW <= GBA_W || !PcFieldWideActive())
        return 0;
    return (gPcScreenW - GBA_W) / 2;
}

// ---------------------------------------------------------------------------
// Entry point

static char **sArgv;

void PortSoftReset(void)
{
#ifdef _WIN32
    _execv(sArgv[0], (const char *const *)sArgv);
#else
    execv("/proc/self/exe", sArgv);
#endif
    exit(0);
}

int main(int argc, char **argv)
{
    sArgv = argv;
    PortMapMemory();
    NullGuardInstall();
    IO16(REG_KEYINPUT_OFF) = 0x3FF;
    // State the BIOS leaves behind: in VBlank, display force-blanked,
    // identity affine matrices.
    IO16(REG_VCOUNT_OFF) = 161;
    IO16(REG_DISPSTAT_OFF) = 1;
    IO16(0x000) = 0x80;
    IO16(0x20) = 0x100; IO16(0x26) = 0x100;
    IO16(0x30) = 0x100; IO16(0x36) = 0x100;
    if (FrontendInit(argc, argv) != 0)
        return 1;
    AgbMain();
    return 0;
}
