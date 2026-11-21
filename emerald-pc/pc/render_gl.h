// OpenGL HD renderer (render_gl.c).
#ifndef PC_RENDER_GL_H
#define PC_RENDER_GL_H
#include <stdint.h>
int  HdInit(void);                     // needs a current GL 3.3 core context
void HdPresent(const uint32_t *frame, int hdMode, int winW, int winH);
void HdSetScale(int scale);
int  HdGetScale(void);
void HdSetGrade(int on);
int  HdGetGrade(void);
void HdSetLighting(int on);
int  HdGetLighting(void);
int  HdReadComposite(uint32_t *out, int *w, int *h);
int  HdReadFrame(uint32_t *out, int *w, int *h, int maxPixels);
#endif
