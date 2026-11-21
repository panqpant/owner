// File-backed replacement for the 128KB flash save chip (agb_flash*.c).
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include "port.h"

typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;

#define FLASH_SIZE   0x20000
#define SECTOR_SIZE  0x1000
#define SECTOR_COUNT 32

struct FlashSector { u32 size; u8 shift; u16 count; u16 top; };
struct FlashType {
    u32 romSize;
    struct FlashSector sector;
    u16 wait[2];
    union { struct { u8 makerId; u8 deviceId; } separate; u16 joined; } ids;
};

static u8 sFlash[FLASH_SIZE];
static int sLoaded;
static char sPath[1024] = "pokeemerald.sav";

static const struct FlashType sType = {
    FLASH_SIZE, { SECTOR_SIZE, 12, SECTOR_COUNT, 0 }, { 3, 1 }, { { 0xC2, 0x09 } }
};
static const u16 sMaxTime[] = { 10, 65469, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 };

u16 gFlashNumRemainingBytes;
u8 gFlashTimeoutFlag;
const u16 *gFlashMaxTime = sMaxTime;
const struct FlashType *gFlash = &sType;

void FlashPcSetPath(const char *path)
{
    snprintf(sPath, sizeof(sPath), "%s", path);
    sLoaded = 0;
}

static void Load(void)
{
    FILE *f;
    if (sLoaded)
        return;
    sLoaded = 1;
    memset(sFlash, 0xFF, sizeof(sFlash));
    f = fopen(sPath, "rb");
    if (f)
    {
        size_t n = fread(sFlash, 1, sizeof(sFlash), f);
        (void)n;
        fclose(f);
    }
}

static void Store(void)
{
    char tmp[1100];
    FILE *f;
    snprintf(tmp, sizeof(tmp), "%s.tmp", sPath);
    f = fopen(tmp, "wb");
    if (!f)
        return;
    fwrite(sFlash, 1, sizeof(sFlash), f);
    fclose(f);
    remove(sPath);
    rename(tmp, sPath);
}

static u16 PcProgramFlashByte(u16 sector, u32 offset, u8 data)
{
    Load();
    if (sector >= SECTOR_COUNT || offset >= SECTOR_SIZE)
        return 0x80FF;
    sFlash[sector * SECTOR_SIZE + offset] = data;
    Store();
    return 0;
}

static u16 PcProgramFlashSector(u16 sector, u8 *src)
{
    Load();
    if (sector >= SECTOR_COUNT)
        return 0x80FF;
    memcpy(&sFlash[sector * SECTOR_SIZE], src, SECTOR_SIZE);
    Store();
    return 0;
}

static u16 PcEraseFlashChip(void)
{
    Load();
    memset(sFlash, 0xFF, sizeof(sFlash));
    Store();
    return 0;
}

static u16 PcEraseFlashSector(u16 sector)
{
    Load();
    if (sector >= SECTOR_COUNT)
        return 0x80FF;
    memset(&sFlash[sector * SECTOR_SIZE], 0xFF, SECTOR_SIZE);
    Store();
    return 0;
}

static u16 PcWaitForFlashWrite(u8 phase, u8 *addr, u8 last) { (void)phase; (void)addr; (void)last; return 0; }
static u8 PcPollFlashStatus(u8 *addr) { (void)addr; return 0; }

u16 (*ProgramFlashByte)(u16, u32, u8) = PcProgramFlashByte;
u16 (*ProgramFlashSector)(u16, u8 *) = PcProgramFlashSector;
u16 (*EraseFlashChip)(void) = PcEraseFlashChip;
u16 (*EraseFlashSector)(u16) = PcEraseFlashSector;
u16 (*WaitForFlashWrite)(u8, u8 *, u8) = PcWaitForFlashWrite;
u8 (*PollFlashStatus)(u8 *) = PcPollFlashStatus;

u16 IdentifyFlash(void)
{
    Load();
    return 0;
}

u16 SetFlashTimerIntr(u8 timerNum, void (**intrFunc)(void))
{
    (void)timerNum; (void)intrFunc;
    return 0;
}

void ReadFlash(u16 sector, u32 offset, u8 *dest, u32 size)
{
    u32 start = sector * SECTOR_SIZE + offset;
    Load();
    if (start >= FLASH_SIZE)
        return;
    if (start + size > FLASH_SIZE)
        size = FLASH_SIZE - start;
    memcpy(dest, &sFlash[start], size);
}

u32 ProgramFlashSectorAndVerify(u16 sector, u8 *src)
{
    if (PcProgramFlashSector(sector, src))
        return 1;
    return memcmp(&sFlash[sector * SECTOR_SIZE], src, SECTOR_SIZE) ? 1 : 0;
}

u32 ProgramFlashSectorAndVerifyNBytes(u16 sector, void *src, u32 n)
{
    Load();
    if (sector >= SECTOR_COUNT)
        return 1;
    memcpy(&sFlash[sector * SECTOR_SIZE], src, n);
    Store();
    return 0;
}

u32 VerifyFlashSector(u16 sector, u8 *src)
{
    Load();
    return memcmp(&sFlash[sector * SECTOR_SIZE], src, SECTOR_SIZE) ? 1 : 0;
}

u32 VerifyFlashSectorNBytes(u16 sector, u8 *src, u32 n)
{
    Load();
    return memcmp(&sFlash[sector * SECTOR_SIZE], src, n) ? 1 : 0;
}

void SwitchFlashBank(u8 bank) { (void)bank; }
u16 ReadFlashId(void) { return 0x09C2; }
void StartFlashTimer(u8 phase) { (void)phase; }
void StopFlashTimer(void) {}
void SetReadFlash1(u16 *dest) { (void)dest; }
