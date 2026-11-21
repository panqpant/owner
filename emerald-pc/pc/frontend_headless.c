// Headless front end for automated testing: replays a script (see script.c),
// writes screenshots as PPM and optionally the audio as WAV.
// Usage: emerald_headless --script FILE [--save FILE] [--wav FILE]
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "port.h"
#include "script.h"

void TestHookRun(const char *cmd);

static int sQuit;
static uint32_t sLast[PC_MAX_W * GBA_H];
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

static void WritePpm(const char *path)
{
    FILE *f = fopen(path, "wb");
    int i;
    if (!f)
        return;
    fprintf(f, "P6\n%d %d\n255\n", gPcScreenW, GBA_H);
    for (i = 0; i < gPcScreenW * GBA_H; i++)
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
    for (i = 1; i < argc; i++)
    {
        if (!strcmp(argv[i], "--script") && i + 1 < argc)
            script = argv[++i];
        else if (!strcmp(argv[i], "--width") && i + 1 < argc)
        {
            int w = atoi(argv[++i]) & ~1;
            gPcScreenW = w < GBA_W ? GBA_W : w > PC_MAX_W ? PC_MAX_W : w;
        }
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
    if (!script || ScriptLoad(script) != 0)
    {
        fprintf(stderr, "usage: %s --script FILE [--save FILE] [--wav FILE]\n", argv[0]);
        return 1;
    }
    return 0;
}

void FrontendPresent(const uint32_t *fb)
{
    memcpy(sLast, fb, (size_t)gPcScreenW * GBA_H * 4);
}

uint16_t FrontendPollKeys(void)
{
    return ScriptStep(WritePpm, TestHookRun, &sQuit);
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
