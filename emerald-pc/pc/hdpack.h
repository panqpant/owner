// HD texture packs (hdpack.c).
#ifndef PC_HDPACK_H
#define PC_HDPACK_H
#include <stdint.h>

extern int gHdPackActive;   // a pack with at least one tile is loaded
extern int gHdDumpEnabled;  // dumping tiles seen on screen

void HdPackInit(const char *baseDir);   // loads <baseDir>hd/tiles/*.png
void HdPackSetDump(int on);
void HdPackBeginFrame(void);
// Slot+1 of the replacement for this tile (0 = none). charAddr is the
// tile's VRAM offset; palBase the first palette index it uses (0-511).
uint16_t HdPackLookup(uint32_t charAddr, int is8, int palBase);
uint16_t HdPackUnfaded(int palIndex);
int HdPackAtlas(const uint32_t **pixels, int *w, int *h, int *scale, int *perRow);

#endif
