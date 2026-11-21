// Shared declarations for the PC platform layer.
// The game code is compiled unmodified for 32-bit x86; this layer stands in
// for the GBA hardware (memory map, PPU, DMA, interrupts, BIOS, save chip).
#ifndef PC_PORT_H
#define PC_PORT_H

#include <stdint.h>

#define GBA_W 240
#define GBA_H 160

// GBA memory regions are mapped at their real addresses inside the
// 32-bit process, so the game's hard-coded addresses keep working.
#define PC_EWRAM 0x02000000u
#define PC_IWRAM 0x03000000u
#define PC_IO    0x04000000u
#define PC_PLTT  0x05000000u
#define PC_VRAM  0x06000000u
#define PC_OAM   0x07000000u

#define IO8(off)  (*(volatile uint8_t  *)(PC_IO + (off)))
#define IO16(off) (*(volatile uint16_t *)(PC_IO + (off)))
#define IO32(off) (*(volatile uint32_t *)(PC_IO + (off)))

#define PC_PAL16  ((volatile uint16_t *)PC_PLTT)
#define PC_VRAM8  ((volatile uint8_t  *)PC_VRAM)
#define PC_VRAM16 ((volatile uint16_t *)PC_VRAM)
#define PC_OAM16  ((volatile uint16_t *)PC_OAM)

// Key bits, GBA layout (1 = pressed).
enum {
    PC_KEY_A = 1 << 0, PC_KEY_B = 1 << 1, PC_KEY_SELECT = 1 << 2, PC_KEY_START = 1 << 3,
    PC_KEY_RIGHT = 1 << 4, PC_KEY_LEFT = 1 << 5, PC_KEY_UP = 1 << 6, PC_KEY_DOWN = 1 << 7,
    PC_KEY_R = 1 << 8, PC_KEY_L = 1 << 9,
};

// platform.c
void PortMapMemory(void);
void PortRunFrame(void);
void PortDmaRunTiming(int timing); // 1 = VBlank, 2 = HBlank
uint32_t PortFrameCount(void);

// ppu.c
// Per-layer output for the HD renderer: each background and the sprite layer
// are kept separate so they can be upscaled independently, together with the
// per-pixel and per-scanline state needed to composite them like the GBA.
struct PpuLayers {
    uint32_t layer[5][GBA_H][GBA_W]; // BG0-3, OBJ: 0xAABBGGRR, A = 255 opaque / 0 empty
    uint32_t meta[GBA_H][GBA_W];     // R: window mask (bits 0-5)  G: OBJ priority (0-1), semi-transparent (2)
    uint32_t line[GBA_H][4];         // see ppu.c: backdrop, enables/priorities, blend state
};
extern struct PpuLayers gPpuLayers;
extern int gPpuExportLayers;

void PpuBeginFrame(void);
void PpuRenderLine(int line, uint32_t *out);  // out: GBA_W pixels, 0xAARRGGBB
void PpuEndHBlank(int line);                 // advance affine reference points

// frontend (headless or SDL)
int  FrontendInit(int argc, char **argv);
void FrontendPresent(const uint32_t *fb);    // GBA_W * GBA_H pixels
uint16_t FrontendPollKeys(void);             // pressed-key mask
int  FrontendShouldQuit(void);
void FrontendAudio(const int16_t *samples, int frames); // interleaved stereo

// flash_pc.c
void FlashPcSetPath(const char *path);

// m4a_pc.c
void M4aPcMixFrame(int16_t *out, int frames);

#endif // PC_PORT_H
