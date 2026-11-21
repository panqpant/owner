// C implementations of the GBA BIOS calls the game uses (libagbsyscall).
#include <math.h>
#include <string.h>
#include <stdint.h>
#include "port.h"

typedef int8_t s8; typedef uint8_t u8; typedef int16_t s16; typedef uint16_t u16;
typedef int32_t s32; typedef uint32_t u32;

void PortSoftReset(void);

void VBlankIntrWait(void)
{
    PortRunFrame();
}

void SoftReset(u32 flags)
{
    (void)flags;
    PortSoftReset();
}

void RegisterRamReset(u32 flags)
{
    if (flags & 0x01) memset((void *)PC_EWRAM, 0, 0x40000);
    if (flags & 0x02) memset((void *)PC_IWRAM, 0, 0x7E00);
    if (flags & 0x04) memset((void *)PC_PLTT, 0, 0x400);
    if (flags & 0x08) memset((void *)PC_VRAM, 0, 0x18000);
    if (flags & 0x10) memset((void *)PC_OAM, 0, 0x400);
    if (flags & 0x80)
    {
        u16 keys = IO16(0x130);
        memset((void *)PC_IO, 0, 0x200);
        IO16(0x130) = keys;
        IO16(0x20) = 0x100; IO16(0x26) = 0x100; // BG2 PA/PD
        IO16(0x30) = 0x100; IO16(0x36) = 0x100; // BG3 PA/PD
    }
}

void CpuSet(const void *src, void *dest, u32 control)
{
    u32 count = control & 0x1FFFFF, i;
    int fixed = (control >> 24) & 1;

    if (control & (1 << 26))
    {
        const volatile u32 *s = (const volatile u32 *)((uintptr_t)src & ~3u);
        volatile u32 *d = (volatile u32 *)((uintptr_t)dest & ~3u);
        for (i = 0; i < count; i++)
            d[i] = fixed ? s[0] : s[i];
    }
    else
    {
        const volatile u16 *s = (const volatile u16 *)((uintptr_t)src & ~1u);
        volatile u16 *d = (volatile u16 *)((uintptr_t)dest & ~1u);
        for (i = 0; i < count; i++)
            d[i] = fixed ? s[0] : s[i];
    }
}

void CpuFastSet(const void *src, void *dest, u32 control)
{
    u32 count = ((control & 0x1FFFFF) + 7) & ~7u, i;
    int fixed = (control >> 24) & 1;
    const volatile u32 *s = (const volatile u32 *)((uintptr_t)src & ~3u);
    volatile u32 *d = (volatile u32 *)((uintptr_t)dest & ~3u);

    for (i = 0; i < count; i++)
        d[i] = fixed ? s[0] : s[i];
}

static void LZ77UnComp(const u32 *src, void *dest)
{
    const u8 *s = (const u8 *)src;
    u8 *d = (u8 *)dest;
    u32 size = (s[1] | (s[2] << 8) | (s[3] << 16)), out = 0;
    s += 4;

    while (out < size)
    {
        u8 flags = *s++;
        int b;
        for (b = 0; b < 8 && out < size; b++, flags <<= 1)
        {
            if (flags & 0x80)
            {
                int len = (s[0] >> 4) + 3;
                int disp = (((s[0] & 0xF) << 8) | s[1]) + 1;
                s += 2;
                while (len-- && out < size)
                {
                    d[out] = d[out - disp];
                    out++;
                }
            }
            else
            {
                d[out++] = *s++;
            }
        }
    }
}

void LZ77UnCompWram(const u32 *src, void *dest) { LZ77UnComp(src, dest); }
void LZ77UnCompVram(const u32 *src, void *dest) { LZ77UnComp(src, dest); }

static void RLUnComp(const u32 *src, void *dest)
{
    const u8 *s = (const u8 *)src;
    u8 *d = (u8 *)dest;
    u32 size = (s[1] | (s[2] << 8) | (s[3] << 16)), out = 0;
    s += 4;

    while (out < size)
    {
        u8 flag = *s++;
        if (flag & 0x80)
        {
            int len = (flag & 0x7F) + 3;
            u8 v = *s++;
            while (len-- && out < size)
                d[out++] = v;
        }
        else
        {
            int len = (flag & 0x7F) + 1;
            while (len-- && out < size)
                d[out++] = *s++;
        }
    }
}

void RLUnCompWram(const u32 *src, void *dest) { RLUnComp(src, dest); }
void RLUnCompVram(const u32 *src, void *dest) { RLUnComp(src, dest); }

s32 Div(s32 num, s32 denom)
{
    if (denom == 0)
        return 0;
    return num / denom;
}

s32 Mod(s32 num, s32 denom)
{
    if (denom == 0)
        return 0;
    return num % denom;
}

u16 Sqrt(u32 num)
{
    u32 r = 0, bit = 1u << 30;
    while (bit > num)
        bit >>= 2;
    while (bit)
    {
        if (num >= r + bit)
        {
            num -= r + bit;
            r = (r >> 1) + bit;
        }
        else
        {
            r >>= 1;
        }
        bit >>= 2;
    }
    return (u16)r;
}

// Same polynomial the BIOS uses, so angles match the original exactly.
static s32 BiosArcTan(s32 i)
{
    s32 a = -((i * i) >> 14);
    s32 b = ((0xA9 * a) >> 14) + 0x390;
    b = ((b * a) >> 14) + 0x91C;
    b = ((b * a) >> 14) + 0xFB6;
    b = ((b * a) >> 14) + 0x16AA;
    b = ((b * a) >> 14) + 0x2081;
    b = ((b * a) >> 14) + 0x3651;
    b = ((b * a) >> 14) + 0xA2F9;
    return (i * b) >> 16;
}

u16 ArcTan2(s16 x, s16 y)
{
    s32 X = x, Y = y;
    if (Y == 0)
        return X >= 0 ? 0 : 0x8000;
    if (X == 0)
        return Y >= 0 ? 0x4000 : 0xC000;
    if (Y >= 0)
    {
        if (X >= 0)
        {
            if (X >= Y)
                return BiosArcTan((Y << 14) / X);
        }
        else if (-X >= Y)
        {
            return BiosArcTan((Y << 14) / X) + 0x8000;
        }
        return 0x4000 - BiosArcTan((X << 14) / Y);
    }
    else
    {
        if (X <= 0)
        {
            if (-X > -Y)
                return BiosArcTan((Y << 14) / X) + 0x8000;
        }
        else if (X >= -Y)
        {
            return BiosArcTan((Y << 14) / X) + 0x10000;
        }
        return 0xC000 - BiosArcTan((X << 14) / Y);
    }
}

static s16 BiosSin(u16 angle) // angle: 0..0xFFFF, BIOS uses the top 8 bits
{
    return (s16)lrint(sin((angle >> 8) * (2.0 * M_PI / 256.0)) * 16384.0);
}

static s16 BiosCos(u16 angle)
{
    return BiosSin((u16)(angle + 0x4000));
}

struct BgAffineSrc { s32 texX, texY; s16 scrX, scrY, sx, sy; u16 alpha; u16 pad; };
struct BgAffineDst { s16 pa, pb, pc, pd; s32 dx, dy; };

void BgAffineSet(struct BgAffineSrc *src, struct BgAffineDst *dest, s32 count)
{
    for (; count > 0; count--, src++, dest++)
    {
        s32 sn = BiosSin(src->alpha), cs = BiosCos(src->alpha);
        s32 pa = (cs * src->sx) >> 14, pb = -((sn * src->sx) >> 14);
        s32 pc = (sn * src->sy) >> 14, pd = (cs * src->sy) >> 14;
        dest->pa = pa; dest->pb = pb; dest->pc = pc; dest->pd = pd;
        dest->dx = src->texX - (pa * src->scrX + pb * src->scrY);
        dest->dy = src->texY - (pc * src->scrX + pd * src->scrY);
    }
}

void ObjAffineSet(const void *srcv, void *destv, s32 count, s32 offset)
{
    const u8 *src = srcv;
    u8 *dest = destv;
    for (; count > 0; count--, src += 8)
    {
        s16 xs = *(const s16 *)src, ys = *(const s16 *)(src + 2);
        u16 rot = *(const u16 *)(src + 4);
        s32 sn = BiosSin(rot), cs = BiosCos(rot);
        *(s16 *)dest = (cs * xs) >> 14; dest += offset;
        *(s16 *)dest = -((sn * xs) >> 14); dest += offset;
        *(s16 *)dest = (sn * ys) >> 14; dest += offset;
        *(s16 *)dest = (cs * ys) >> 14; dest += offset;
    }
}

int MultiBoot(void *mp)
{
    (void)mp;
    return 1; // no link cable: report failure
}
