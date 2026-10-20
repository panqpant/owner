#!/usr/bin/env python3
"""Packs arm9.bin and arm7.bin into a minimal .nds the emulator can direct-boot."""
import struct, sys

arm9 = open(sys.argv[1], "rb").read()
arm7 = open(sys.argv[2], "rb").read()
out = sys.argv[3]
code = (sys.argv[4] if len(sys.argv) > 4 else "B2TT").encode()

def pad(b, n): return b + b"\0" * (-len(b) % n)
arm9, arm7 = pad(arm9, 0x200), pad(arm7, 0x200)
ARM9_OFF, ARM7_OFF = 0x8000, 0x8000 + len(arm9)
size = ARM7_OFF + len(arm7)

h = bytearray(0x200)
h[0:12] = b"B2O TESTROM\0"
h[0x0C:0x10] = code
h[0x10:0x12] = b"01"
h[0x14] = 7  # 128 KB chip
struct.pack_into("<IIII", h, 0x20, ARM9_OFF, 0x02000000, 0x02000000, len(arm9))
struct.pack_into("<IIII", h, 0x30, ARM7_OFF, 0x037F8000, 0x037F8000, len(arm7))
struct.pack_into("<I", h, 0x80, size)
struct.pack_into("<I", h, 0x84, 0x4000)

def crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc
struct.pack_into("<H", h, 0x15C, 0xCF56)
struct.pack_into("<H", h, 0x15E, crc16(h[:0x15E]))

rom = bytearray(size)
rom[0:0x200] = h
rom[ARM9_OFF:ARM9_OFF + len(arm9)] = arm9
rom[ARM7_OFF:ARM7_OFF + len(arm7)] = arm7
rom = pad(bytes(rom), 0x20000)
open(out, "wb").write(rom)
