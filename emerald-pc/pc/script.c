// Scripted input for automated runs (shared by the headless and SDL front
// ends). Script commands, one per line:
//   wait N                 N frames with no keys
//   hold MASK N            hold key mask for N frames
//   tap MASK COUNT [GAP]   press MASK for 4 frames then GAP (default 20) idle, COUNT times
//   shot PATH              save a screenshot (front end decides the format)
//   call HOOK ARGS         run a test hook (testhooks.c, headless build only)
//   quit                   exit
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "script.h"

#define MAX_FRAMES 400000
#define MAX_EVENTS 8192

struct Event { int frame; int type; char *arg; };
enum { EV_SHOT, EV_CALL };

static uint16_t *sKeys;
static int sNumFrames, sQuitAt = -1, sFrame, sLoaded;
static struct Event sEvents[MAX_EVENTS];
static int sNumEvents, sNext;

static void Push(uint16_t keys, int n)
{
    while (n-- > 0 && sNumFrames < MAX_FRAMES)
        sKeys[sNumFrames++] = keys;
}

int ScriptLoad(const char *path)
{
    FILE *f = fopen(path, "r");
    char line[1024];
    if (!f)
        return -1;
    sKeys = calloc(MAX_FRAMES, sizeof(uint16_t));
    while (fgets(line, sizeof(line), f))
    {
        char cmd[32], arg[900];
        int a = 0, b = 0, c = 20;
        if (sscanf(line, "%31s", cmd) != 1 || cmd[0] == '#')
            continue;
        if (!strcmp(cmd, "wait") && sscanf(line, "%*s %d", &a) == 1)
            Push(0, a);
        else if (!strcmp(cmd, "hold") && sscanf(line, "%*s %i %d", &a, &b) == 2)
            Push(a, b);
        else if (!strcmp(cmd, "tap") && sscanf(line, "%*s %i %d %d", &a, &b, &c) >= 2)
        {
            int i;
            for (i = 0; i < b; i++) { Push(a, 4); Push(0, c); }
        }
        else if ((!strcmp(cmd, "shot") || !strcmp(cmd, "call")) && sNumEvents < MAX_EVENTS)
        {
            char *p = line + strlen(cmd);
            while (*p == ' ' || *p == '\t') p++;
            p[strcspn(p, "\r\n")] = 0;
            snprintf(arg, sizeof(arg), "%s", p);
            sEvents[sNumEvents].frame = sNumFrames;
            sEvents[sNumEvents].type = cmd[0] == 's' ? EV_SHOT : EV_CALL;
            sEvents[sNumEvents].arg = strdup(arg);
            sNumEvents++;
        }
        else if (!strcmp(cmd, "quit"))
            sQuitAt = sNumFrames;
    }
    fclose(f);
    if (sQuitAt < 0)
        sQuitAt = sNumFrames;
    sLoaded = 1;
    return 0;
}

int ScriptActive(void) { return sLoaded; }

int ScriptShotDue(void)
{
    int i;
    for (i = sNext; i < sNumEvents && sEvents[i].frame <= sFrame; i++)
        if (sEvents[i].type == EV_SHOT)
            return 1;
    return 0;
}

uint16_t ScriptStep(void (*onShot)(const char *), void (*onCall)(const char *), int *quit)
{
    uint16_t k;
    while (sNext < sNumEvents && sEvents[sNext].frame <= sFrame)
    {
        struct Event *e = &sEvents[sNext++];
        if (e->type == EV_SHOT) { if (onShot) onShot(e->arg); }
        else if (onCall) onCall(e->arg);
    }
    if (sFrame >= sQuitAt)
        *quit = 1;
    k = sFrame < sNumFrames ? sKeys[sFrame] : 0;
    sFrame++;
    return k;
}
