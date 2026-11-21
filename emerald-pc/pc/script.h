#ifndef PC_SCRIPT_H
#define PC_SCRIPT_H
#include <stdint.h>
int ScriptLoad(const char *path);
int ScriptActive(void);
int ScriptShotDue(void);
uint16_t ScriptStep(void (*onShot)(const char *), void (*onCall)(const char *), int *quit);
#endif
