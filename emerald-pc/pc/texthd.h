// High-resolution text (texthd.c). Plain C interface usable from both the
// game-side hooks and the PC renderer.
#ifndef PC_TEXTHD_H
#define PC_TEXTHD_H
#include <stdint.h>

extern uint32_t gPcTextTags[0x20000]; // per BG VRAM pixel; 0 = not text
extern int gPcTextHd;                 // enabled

// Renderer side
int PcTextExpected(uint32_t tag);     // palette index the pixel must still have, -1 if invalid
int PcTextTileOk(uint32_t tileIndex); // BG VRAM tile still holds the text it was tagged with
void PcTextBeginFrame(void);
int PcTextAtlasSize(int *w, int *h);  // returns atlas pixels per GBA pixel
int PcTextNextPending(const uint8_t **pixels, int *x, int *y, int *w, int *h, int *stride);

#define PC_TEXT_TAG_SLOT(t) ((t) & 0x3FF)
#define PC_TEXT_TAG_LX(t)   (((t) >> 10) & 15)
#define PC_TEXT_TAG_LY(t)   (((t) >> 14) & 15)
#define PC_TEXT_TAG_FG(t)   (((t) >> 18) & 15)
#define PC_TEXT_TAG_SH(t)   (((t) >> 22) & 15)
#define PC_TEXT_TAG_BG(t)   (((t) >> 26) & 15)

#endif
