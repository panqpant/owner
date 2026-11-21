// Headless front end for automated testing: replays a scripted input
// sequence and writes screenshots. Script commands, one per line:
//   wait N              N frames with no keys
//   hold MASK N         hold key mask for N frames
//   tap MASK COUNT [GAP] press MASK for 4 frames, then GAP (default 20) idle, COUNT times
//   shot PATH           write the most recent frame as a PPM image
//   quit                exit
// Usage: emerald_headless --script FILE [--save FILE] [--wav FILE]
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "port.h"

#define MAX_EVENTS 200000

struct Event { int frame; char *shot; };

static uint16_t *sKeys;
static int sNumFrames;
static struct Event sShots[4096];
static int sNumShots, sNextShot;
static int sFrame;
static int sQuitAt = -1;
static int sQuit;
static uint32_t sLast[GBA_W * GBA_H];
static FILE *sWav;
static uint32_t sWavFrames;

static void WavHeader(FILE *f, uint32_t frames)
{
    uint32_t data = frames * 4, riff = 36 + data, rate = 48000, byteRate = 48000 * 4, fmtLen = 16;
    uint16_t fmt = 1, chans = 2, align = 4, bits = 16;
    fseek(f, 0, SEEK_SET);
    fwrite("RIFF", 1, 4, f); fwrite(&riff, 4, 1, f); fwrite("WAVEfmt ", 1, 8, f);
    fwrite(&fmtLen, 4, 1, f); fwrite(&fmt, 2, 1, f); fwrite(&chans, 2, 1, f);
    fwrite(&rate, 4, 1, f); fwrite(&byteRate, 4, 1, f); fwrite(&align, 2, 1, f); fwrite(&bits, 2, 1, f);
    fwrite("data", 1, 4, f); fwrite(&data, 4, 1, f);
    fseek(f, 0, SEEK_END);
}

static void CloseWav(void)
{
    if (sWav)
    {
        WavHeader(sWav, sWavFrames);
        fclose(sWav);
        sWav = NULL;
    }
}

static void Push(uint16_t keys, int n)
{
    while (n-- > 0 && sNumFrames < MAX_EVENTS)
        sKeys[sNumFrames++] = keys;
}

static void LoadScript(const char *path)
{
    FILE *f = fopen(path, "r");
    char line[1024];
    if (!f)
    {
        fprintf(stderr, "cannot open script %s\n", path);
        exit(1);
    }
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
        else if (!strcmp(cmd, "shot") && sscanf(line, "%*s %899s", arg) == 1 && sNumShots < 4096)
        {
            sShots[sNumShots].frame = sNumFrames;
            sShots[sNumShots].shot = strdup(arg);
            sNumShots++;
        }
        else if (!strcmp(cmd, "quit"))
            sQuitAt = sNumFrames;
    }
    fclose(f);
    if (sQuitAt < 0)
        sQuitAt = sNumFrames;
}

static void WritePpm(const char *path)
{
    FILE *f = fopen(path, "wb");
    int i;
    if (!f)
        return;
    fprintf(f, "P6\n%d %d\n255\n", GBA_W, GBA_H);
    for (i = 0; i < GBA_W * GBA_H; i++)
    {
        unsigned char px[3] = { (sLast[i] >> 16) & 0xFF, (sLast[i] >> 8) & 0xFF, sLast[i] & 0xFF };
        fwrite(px, 1, 3, f);
    }
    fclose(f);
}

int FrontendInit(int argc, char **argv)
{
    int i;
    const char *script = NULL;
    sKeys = calloc(MAX_EVENTS, sizeof(uint16_t));
    for (i = 1; i < argc; i++)
    {
        if (!strcmp(argv[i], "--script") && i + 1 < argc)
            script = argv[++i];
        else if (!strcmp(argv[i], "--save") && i + 1 < argc)
            FlashPcSetPath(argv[++i]);
        else if (!strcmp(argv[i], "--wav") && i + 1 < argc)
        {
            sWav = fopen(argv[++i], "wb");
            if (sWav)
            {
                WavHeader(sWav, 0);
                atexit(CloseWav);
            }
        }
    }
    if (!script)
    {
        fprintf(stderr, "usage: %s --script FILE [--save FILE]\n", argv[0]);
        return 1;
    }
    LoadScript(script);
    return 0;
}

void FrontendPresent(const uint32_t *fb)
{
    memcpy(sLast, fb, sizeof(sLast));
}

uint16_t FrontendPollKeys(void)
{
    uint16_t k;
    while (sNextShot < sNumShots && sShots[sNextShot].frame <= sFrame)
        WritePpm(sShots[sNextShot++].shot);
    if (sFrame >= sQuitAt)
        sQuit = 1;
    k = sFrame < sNumFrames ? sKeys[sFrame] : 0;
    sFrame++;
    return k;
}

int FrontendShouldQuit(void)
{
    return sQuit;
}

void FrontendAudio(const int16_t *samples, int frames)
{
    if (!sWav)
        return;
    fwrite(samples, 4, frames, sWav);
    sWavFrames += frames;
}
