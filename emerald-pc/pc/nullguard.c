// "Open bus" emulation for reads near address 0.
//
// On the GBA, addresses 0x00000000-0x00003FFF are the BIOS: reading through a
// NULL (or freed-and-cleared) pointer quietly returns BIOS bytes. The original
// game relies on this by accident in several places (e.g. a VBlank callback
// that touches a screen's state after the screen freed it). On a PC those
// reads are fatal, so this handler catches access faults in the low 16 MB,
// decodes the faulting x86 instruction, emulates it as if memory read 0
// (writes are dropped), and resumes after it.
//
// Only the instruction forms GCC emits for plain loads, stores, compares and
// ALU ops with a memory operand are handled; anything else still crashes.
#ifndef _WIN32
#define _GNU_SOURCE
#endif
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <windows.h>
#else
#include <signal.h>
#include <ucontext.h>
#endif

#define GUARD_LIMIT 0x01000000u

enum { R_EAX, R_ECX, R_EDX, R_EBX, R_ESP, R_EBP, R_ESI, R_EDI };

struct Cpu {
    uint32_t *reg[8];
    uint32_t *eip;
    uint32_t *eflags;
};

static int sReported;

// EFLAGS from a result, for compare/test/ALU forms against a zero operand.
static void SetFlags(struct Cpu *c, uint32_t res, int size, int cf, int of)
{
    uint32_t f = *c->eflags & ~0x8D5u; // clear CF PF AF ZF SF OF
    uint32_t mask = size == 1 ? 0xFF : size == 2 ? 0xFFFF : 0xFFFFFFFF;
    uint32_t sign = size == 1 ? 0x80 : size == 2 ? 0x8000 : 0x80000000;
    uint8_t lo = res & 0xFF;
    int parity = !__builtin_parity(lo);
    res &= mask;
    if (cf) f |= 1;
    if (parity) f |= 4;
    if (res == 0) f |= 0x40;
    if (res & sign) f |= 0x80;
    if (of) f |= 0x800;
    *c->eflags = f;
}

static uint32_t GetReg(struct Cpu *c, int r, int size)
{
    if (size == 1)
        return r < 4 ? (*c->reg[r] & 0xFF) : ((*c->reg[r - 4] >> 8) & 0xFF);
    if (size == 2)
        return *c->reg[r] & 0xFFFF;
    return *c->reg[r];
}

static void SetReg(struct Cpu *c, int r, int size, uint32_t v)
{
    if (size == 1)
    {
        if (r < 4) *c->reg[r] = (*c->reg[r] & ~0xFFu) | (v & 0xFF);
        else *c->reg[r - 4] = (*c->reg[r - 4] & ~0xFF00u) | ((v & 0xFF) << 8);
    }
    else if (size == 2)
        *c->reg[r] = (*c->reg[r] & ~0xFFFFu) | (v & 0xFFFF);
    else
        *c->reg[r] = v;
}

// Returns 1 if the instruction was emulated.
static int Emulate(struct Cpu *c)
{
    const uint8_t *p = (const uint8_t *)(uintptr_t)*c->eip;
    const uint8_t *start = p;
    int opsize = 4, two = 0, op, modrm, mod, reg, rm, immSize = 0, size;
    uint32_t imm = 0;

    for (;;)
    {
        if (*p == 0x66) { opsize = 2; p++; }
        else if (*p == 0xF0 || *p == 0x2E || *p == 0x3E || *p == 0x26 || *p == 0x36 || *p == 0x64 || *p == 0x65) p++;
        else break;
    }
    op = *p++;
    if (op == 0x0F) { two = 1; op = *p++; }

    modrm = *p++;
    mod = modrm >> 6; reg = (modrm >> 3) & 7; rm = modrm & 7;
    if (mod == 3)
        return 0;
    if (rm == 4)
    {
        int sib = *p++;
        if ((sib & 7) == 5 && mod == 0) p += 4;
    }
    else if (rm == 5 && mod == 0)
        p += 4;
    if (mod == 1) p += 1;
    else if (mod == 2) p += 4;

    if (!two)
    {
        switch (op)
        {
        case 0x80: case 0xC6: case 0xF6: immSize = 1; break;
        case 0x81: case 0xC7: case 0xF7: immSize = opsize; break;
        case 0x83: immSize = 1; break;
        case 0x69: immSize = opsize; break;
        case 0x6B: immSize = 1; break;
        }
        if ((op == 0xF6 || op == 0xF7) && reg != 0 && reg != 1)
            immSize = 0;
    }
    if (immSize == 1) imm = (uint32_t)(int32_t)(int8_t)*p;
    else if (immSize == 2) imm = p[0] | (p[1] << 8);
    else if (immSize == 4) imm = p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24);
    p += immSize;

    size = (op & 1) ? opsize : 1;

    if (two)
    {
        switch (op)
        {
        case 0xB6: case 0xBE: SetReg(c, reg, opsize, 0); break; // movzx/movsx r, m8
        case 0xB7: case 0xBF: SetReg(c, reg, opsize, 0); break; // movzx/movsx r, m16
        case 0xAF: SetReg(c, reg, opsize, 0); SetFlags(c, 0, opsize, 0, 0); break; // imul r, m
        default:
            if (op >= 0x90 && op <= 0x9F) break; // setcc m8: drop the write
            return 0;
        }
    }
    else
    {
        switch (op)
        {
        case 0x88: case 0x89: case 0xC6: case 0xC7: break; // stores: dropped
        case 0x8A: case 0x8B: SetReg(c, reg, size, 0); break; // loads read 0
        // reg op= mem (mem reads as 0)
        case 0x02: case 0x03: case 0x0A: case 0x0B: case 0x12: case 0x13:
        case 0x1A: case 0x1B: case 0x2A: case 0x2B: case 0x32: case 0x33:
            SetFlags(c, GetReg(c, reg, size), size, 0, 0);
            break;
        case 0x22: case 0x23: // and reg, mem -> 0
            SetReg(c, reg, size, 0);
            SetFlags(c, 0, size, 0, 0);
            break;
        // mem op= reg: write dropped, flags from 0 op reg
        case 0x00: case 0x01: case 0x08: case 0x09: case 0x30: case 0x31:
            SetFlags(c, GetReg(c, reg, size), size, 0, 0);
            break;
        case 0x20: case 0x21: case 0x84: case 0x85: // and/test mem, reg -> 0
            SetFlags(c, 0, size, 0, 0);
            break;
        case 0x28: case 0x29: // sub mem, reg
        case 0x38: case 0x39: // cmp mem, reg: 0 - reg
        {
            uint32_t r = GetReg(c, reg, size);
            uint32_t sign = size == 1 ? 0x80 : size == 2 ? 0x8000 : 0x80000000;
            uint32_t res = 0u - r;
            SetFlags(c, res, size, r != 0, (r & sign) && (res & sign));
            break;
        }
        case 0x3A: case 0x3B: // cmp reg, mem: reg - 0
            SetFlags(c, GetReg(c, reg, size), size, 0, 0);
            break;
        case 0x80: case 0x81: case 0x83: // ALU mem, imm
        {
            int sz = op == 0x80 ? 1 : opsize;
            uint32_t sign = sz == 1 ? 0x80 : sz == 2 ? 0x8000 : 0x80000000;
            uint32_t mask = sz == 1 ? 0xFF : sz == 2 ? 0xFFFF : 0xFFFFFFFF;
            uint32_t i = imm & mask;
            switch (reg)
            {
            case 0: case 1: case 2: case 6: SetFlags(c, i, sz, 0, 0); break;   // add/or/adc/xor
            case 4: SetFlags(c, 0, sz, 0, 0); break;                           // and
            case 3: case 5: case 7:                                            // sbb/sub/cmp
            {
                uint32_t res = (0u - i) & mask;
                SetFlags(c, res, sz, i != 0, (i & sign) && (res & sign));
                break;
            }
            }
            break;
        }
        case 0xF6: case 0xF7:
            if (reg == 0 || reg == 1) SetFlags(c, 0, size, 0, 0);            // test
            else if (reg == 2 || reg == 3) break;                            // not/neg: dropped
            else if (reg == 4 || reg == 5) {                                 // mul/imul: 0
                SetReg(c, R_EAX, size == 1 ? 2 : size, 0);
                if (size != 1) SetReg(c, R_EDX, size, 0);
                SetFlags(c, 0, size, 0, 0);
            }
            else return 0;                                                   // div by 0
            break;
        case 0x69: case 0x6B: SetReg(c, reg, opsize, 0); SetFlags(c, 0, opsize, 0, 0); break;
        case 0xFE: case 0xFF:
            if (reg == 0 || reg == 1) break;                                 // inc/dec m: dropped
            if (op == 0xFF && reg == 6)                                      // push m: push 0
            {
                *c->reg[R_ESP] -= 4;
                *(uint32_t *)(uintptr_t)*c->reg[R_ESP] = 0;
                break;
            }
            return 0;
        case 0xD0: case 0xD1: case 0xD2: case 0xD3: case 0xC0: case 0xC1: break; // shifts on m: dropped
        default:
            return 0;
        }
    }

    *c->eip += (uint32_t)(p - start);
    return 1;
}

static void Report(uint32_t addr, uint32_t eip)
{
    if (sReported < 20)
    {
        fprintf(stderr, "[nullguard] read of unmapped address 0x%08X at eip 0x%08X treated as open bus\n", addr, eip);
        sReported++;
    }
}

#ifdef _WIN32
static LONG CALLBACK Handler(EXCEPTION_POINTERS *ep)
{
    CONTEXT *ctx = ep->ContextRecord;
    struct Cpu c;
    uint32_t addr;

    if (ep->ExceptionRecord->ExceptionCode != EXCEPTION_ACCESS_VIOLATION)
        return EXCEPTION_CONTINUE_SEARCH;
    addr = (uint32_t)ep->ExceptionRecord->ExceptionInformation[1];
    if (addr >= GUARD_LIMIT)
        return EXCEPTION_CONTINUE_SEARCH;

    c.reg[R_EAX] = (uint32_t *)&ctx->Eax; c.reg[R_ECX] = (uint32_t *)&ctx->Ecx;
    c.reg[R_EDX] = (uint32_t *)&ctx->Edx; c.reg[R_EBX] = (uint32_t *)&ctx->Ebx;
    c.reg[R_ESP] = (uint32_t *)&ctx->Esp; c.reg[R_EBP] = (uint32_t *)&ctx->Ebp;
    c.reg[R_ESI] = (uint32_t *)&ctx->Esi; c.reg[R_EDI] = (uint32_t *)&ctx->Edi;
    c.eip = (uint32_t *)&ctx->Eip; c.eflags = (uint32_t *)&ctx->EFlags;
    Report(addr, ctx->Eip);
    if (!Emulate(&c))
        return EXCEPTION_CONTINUE_SEARCH;
    return EXCEPTION_CONTINUE_EXECUTION;
}

void NullGuardInstall(void)
{
    AddVectoredExceptionHandler(1, Handler);
}
#else
static void Handler(int sig, siginfo_t *si, void *uctx)
{
    ucontext_t *uc = uctx;
    greg_t *g = uc->uc_mcontext.gregs;
    uint32_t addr = (uint32_t)(uintptr_t)si->si_addr;
    struct Cpu c;

    if (addr < GUARD_LIMIT)
    {
        c.reg[R_EAX] = (uint32_t *)&g[REG_EAX]; c.reg[R_ECX] = (uint32_t *)&g[REG_ECX];
        c.reg[R_EDX] = (uint32_t *)&g[REG_EDX]; c.reg[R_EBX] = (uint32_t *)&g[REG_EBX];
        c.reg[R_ESP] = (uint32_t *)&g[REG_UESP]; c.reg[R_EBP] = (uint32_t *)&g[REG_EBP];
        c.reg[R_ESI] = (uint32_t *)&g[REG_ESI]; c.reg[R_EDI] = (uint32_t *)&g[REG_EDI];
        c.eip = (uint32_t *)&g[REG_EIP]; c.eflags = (uint32_t *)&g[REG_EFL];
        Report(addr, (uint32_t)g[REG_EIP]);
        if (Emulate(&c))
            return;
    }
    fprintf(stderr, "fatal: access violation at 0x%08X (eip 0x%08X)\n", addr, (uint32_t)g[REG_EIP]);
    signal(sig, SIG_DFL);
    raise(sig);
}

void NullGuardInstall(void)
{
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_sigaction = Handler;
    sa.sa_flags = SA_SIGINFO | SA_NODEFER;
    sigaction(SIGSEGV, &sa, NULL);
}
#endif
