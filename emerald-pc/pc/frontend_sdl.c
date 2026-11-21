// SDL2 front end: window, input, audio and frame pacing.
//
// Keyboard: arrows = D-pad, X = A, Z = B, Enter = Start, Backspace = Select,
//           A = L, S = R, Tab (hold) = fast-forward, F11 / Alt+Enter = fullscreen,
//           F12 = screenshot, Esc = quit.
// Gamepad:  south button = A, east = B, Start, Back = Select, shoulders = L/R,
//           D-pad or left stick to move.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define SDL_MAIN_HANDLED
#include <SDL.h>
#include "port.h"

#define AUDIO_RATE 48000
#define FRAME_SECONDS (280896.0 / 16777216.0)

static SDL_Window *sWindow;
static SDL_Renderer *sRenderer;
static SDL_Texture *sTexture;
static SDL_AudioDeviceID sAudio;
static SDL_GameController *sPad;
static int sQuit;
static int sFastForward;
static uint64_t sNextFrame;
static char sBasePath[1024];
static uint32_t sLastFrame[GBA_W * GBA_H];

static void OpenPad(void)
{
    int i;
    if (sPad)
        return;
    for (i = 0; i < SDL_NumJoysticks(); i++)
    {
        if (SDL_IsGameController(i))
        {
            sPad = SDL_GameControllerOpen(i);
            if (sPad)
                return;
        }
    }
}

static void Screenshot(void)
{
    char path[1200];
    SDL_Surface *s = SDL_CreateRGBSurfaceWithFormatFrom(sLastFrame, GBA_W, GBA_H, 32, GBA_W * 4,
                                                        SDL_PIXELFORMAT_ARGB8888);
    int n;
    if (!s)
        return;
    for (n = 1; n < 10000; n++)
    {
        FILE *f;
        snprintf(path, sizeof(path), "%sscreenshot_%04d.bmp", sBasePath, n);
        f = fopen(path, "rb");
        if (!f)
            break;
        fclose(f);
    }
    SDL_SaveBMP(s, path);
    SDL_FreeSurface(s);
}

int FrontendInit(int argc, char **argv)
{
    SDL_AudioSpec want, have;
    char *base;
    char savePath[1100];
    int i, scale = 4;

    for (i = 1; i < argc; i++)
        if (!strcmp(argv[i], "--scale") && i + 1 < argc)
            scale = atoi(argv[++i]);
    if (scale < 1)
        scale = 1;

    SDL_SetMainReady();
    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_GAMECONTROLLER) != 0)
    {
        fprintf(stderr, "SDL_Init failed: %s\n", SDL_GetError());
        return 1;
    }

    base = SDL_GetBasePath();
    if (base)
    {
        snprintf(sBasePath, sizeof(sBasePath), "%s", base);
        SDL_free(base);
    }
    snprintf(savePath, sizeof(savePath), "%semerald.sav", sBasePath);
    for (i = 1; i < argc; i++)
        if (!strcmp(argv[i], "--save") && i + 1 < argc)
            snprintf(savePath, sizeof(savePath), "%s", argv[++i]);
    FlashPcSetPath(savePath);

    SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, "0");
    sWindow = SDL_CreateWindow("Pokémon Emerald", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
                               GBA_W * scale, GBA_H * scale, SDL_WINDOW_RESIZABLE | SDL_WINDOW_ALLOW_HIGHDPI);
    if (!sWindow)
    {
        fprintf(stderr, "SDL_CreateWindow failed: %s\n", SDL_GetError());
        return 1;
    }
    sRenderer = SDL_CreateRenderer(sWindow, -1, SDL_RENDERER_ACCELERATED);
    if (!sRenderer)
        sRenderer = SDL_CreateRenderer(sWindow, -1, SDL_RENDERER_SOFTWARE);
    SDL_RenderSetLogicalSize(sRenderer, GBA_W, GBA_H);
    sTexture = SDL_CreateTexture(sRenderer, SDL_PIXELFORMAT_ARGB8888, SDL_TEXTUREACCESS_STREAMING, GBA_W, GBA_H);

    SDL_zero(want);
    want.freq = AUDIO_RATE;
    want.format = AUDIO_S16SYS;
    want.channels = 2;
    want.samples = 1024;
    sAudio = SDL_OpenAudioDevice(NULL, 0, &want, &have, 0);
    if (sAudio)
        SDL_PauseAudioDevice(sAudio, 0);

    OpenPad();
    sNextFrame = SDL_GetPerformanceCounter();
    return 0;
}

static void ToggleFullscreen(void)
{
    uint32_t flags = SDL_GetWindowFlags(sWindow);
    SDL_SetWindowFullscreen(sWindow, (flags & SDL_WINDOW_FULLSCREEN_DESKTOP) ? 0 : SDL_WINDOW_FULLSCREEN_DESKTOP);
}

static void PumpEvents(void)
{
    SDL_Event e;
    while (SDL_PollEvent(&e))
    {
        switch (e.type)
        {
        case SDL_QUIT:
            sQuit = 1;
            break;
        case SDL_KEYDOWN:
            if (e.key.keysym.sym == SDLK_F11
             || (e.key.keysym.sym == SDLK_RETURN && (e.key.keysym.mod & KMOD_ALT)))
                ToggleFullscreen();
            else if (e.key.keysym.sym == SDLK_F12)
                Screenshot();
            else if (e.key.keysym.sym == SDLK_ESCAPE)
                sQuit = 1;
            break;
        case SDL_CONTROLLERDEVICEADDED:
            OpenPad();
            break;
        case SDL_CONTROLLERDEVICEREMOVED:
            if (sPad && !SDL_GameControllerGetAttached(sPad))
            {
                SDL_GameControllerClose(sPad);
                sPad = NULL;
                OpenPad();
            }
            break;
        }
    }
}

void FrontendPresent(const uint32_t *fb)
{
    uint64_t freq = SDL_GetPerformanceFrequency();
    uint64_t now;

    memcpy(sLastFrame, fb, sizeof(sLastFrame));
    PumpEvents();

    // Fast-forward renders every 4th frame and skips pacing.
    if (!sFastForward || (PortFrameCount() & 3) == 0)
    {
        SDL_UpdateTexture(sTexture, NULL, fb, GBA_W * 4);
        SDL_SetRenderDrawColor(sRenderer, 0, 0, 0, 255);
        SDL_RenderClear(sRenderer);
        SDL_RenderCopy(sRenderer, sTexture, NULL, NULL);
        SDL_RenderPresent(sRenderer);
    }

    if (sFastForward)
    {
        sNextFrame = SDL_GetPerformanceCounter();
        return;
    }

    // Pace to the GBA's 59.73 Hz. When audio is running, also keep its queue
    // short so sound stays in sync with the picture.
    sNextFrame += (uint64_t)(FRAME_SECONDS * freq);
    now = SDL_GetPerformanceCounter();
    if (now > sNextFrame + freq / 10)
        sNextFrame = now; // fell far behind (window drag etc.): resync
    while ((now = SDL_GetPerformanceCounter()) < sNextFrame)
    {
        uint64_t ms = (sNextFrame - now) * 1000 / freq;
        if (ms > 1)
            SDL_Delay((uint32_t)(ms - 1));
    }
}

uint16_t FrontendPollKeys(void)
{
    const uint8_t *k = SDL_GetKeyboardState(NULL);
    uint16_t keys = 0;

    if (k[SDL_SCANCODE_X]) keys |= PC_KEY_A;
    if (k[SDL_SCANCODE_Z]) keys |= PC_KEY_B;
    if (k[SDL_SCANCODE_RETURN]) keys |= PC_KEY_START;
    if (k[SDL_SCANCODE_BACKSPACE]) keys |= PC_KEY_SELECT;
    if (k[SDL_SCANCODE_RIGHT]) keys |= PC_KEY_RIGHT;
    if (k[SDL_SCANCODE_LEFT]) keys |= PC_KEY_LEFT;
    if (k[SDL_SCANCODE_UP]) keys |= PC_KEY_UP;
    if (k[SDL_SCANCODE_DOWN]) keys |= PC_KEY_DOWN;
    if (k[SDL_SCANCODE_A]) keys |= PC_KEY_L;
    if (k[SDL_SCANCODE_S]) keys |= PC_KEY_R;
    sFastForward = k[SDL_SCANCODE_TAB];

    if (sPad)
    {
        int16_t lx = SDL_GameControllerGetAxis(sPad, SDL_CONTROLLER_AXIS_LEFTX);
        int16_t ly = SDL_GameControllerGetAxis(sPad, SDL_CONTROLLER_AXIS_LEFTY);
        if (SDL_GameControllerGetButton(sPad, SDL_CONTROLLER_BUTTON_A)) keys |= PC_KEY_A;
        if (SDL_GameControllerGetButton(sPad, SDL_CONTROLLER_BUTTON_B)) keys |= PC_KEY_B;
        if (SDL_GameControllerGetButton(sPad, SDL_CONTROLLER_BUTTON_START)) keys |= PC_KEY_START;
        if (SDL_GameControllerGetButton(sPad, SDL_CONTROLLER_BUTTON_BACK)) keys |= PC_KEY_SELECT;
        if (SDL_GameControllerGetButton(sPad, SDL_CONTROLLER_BUTTON_LEFTSHOULDER)) keys |= PC_KEY_L;
        if (SDL_GameControllerGetButton(sPad, SDL_CONTROLLER_BUTTON_RIGHTSHOULDER)) keys |= PC_KEY_R;
        if (SDL_GameControllerGetButton(sPad, SDL_CONTROLLER_BUTTON_DPAD_UP) || ly < -16000) keys |= PC_KEY_UP;
        if (SDL_GameControllerGetButton(sPad, SDL_CONTROLLER_BUTTON_DPAD_DOWN) || ly > 16000) keys |= PC_KEY_DOWN;
        if (SDL_GameControllerGetButton(sPad, SDL_CONTROLLER_BUTTON_DPAD_LEFT) || lx < -16000) keys |= PC_KEY_LEFT;
        if (SDL_GameControllerGetButton(sPad, SDL_CONTROLLER_BUTTON_DPAD_RIGHT) || lx > 16000) keys |= PC_KEY_RIGHT;
        if (SDL_GameControllerGetAxis(sPad, SDL_CONTROLLER_AXIS_TRIGGERRIGHT) > 16000) sFastForward = 1;
    }

    // Opposite directions can't be pressed together on a real D-pad.
    if ((keys & (PC_KEY_LEFT | PC_KEY_RIGHT)) == (PC_KEY_LEFT | PC_KEY_RIGHT))
        keys &= ~(PC_KEY_LEFT | PC_KEY_RIGHT);
    if ((keys & (PC_KEY_UP | PC_KEY_DOWN)) == (PC_KEY_UP | PC_KEY_DOWN))
        keys &= ~(PC_KEY_UP | PC_KEY_DOWN);
    return keys;
}

int FrontendShouldQuit(void)
{
    return sQuit;
}

void FrontendAudio(const int16_t *samples, int frames)
{
    if (!sAudio)
        return;
    if (sFastForward)
        return;
    // Keep at most ~100 ms queued; drop audio rather than drift behind.
    if (SDL_GetQueuedAudioSize(sAudio) > AUDIO_RATE * 4 / 10)
        return;
    SDL_QueueAudio(sAudio, samples, frames * 4);
}
