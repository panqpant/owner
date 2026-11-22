// SDL2 front end: window, input, audio and frame pacing.
//
// Keyboard: arrows = D-pad, X = A, Z = B, Enter = Start, Backspace = Select,
//           A = L, S = R, Tab (hold) = fast-forward, F11 / Alt+Enter = fullscreen,
//           F12 = screenshot, Esc = quit.
//           F1 = HD / original graphics, F2 = HD internal scale, F3 = colour grade,
//           F4 = time-of-day lighting, F6 = dump tiles for HD packs (hd/dump).
// Gamepad:  south button = A, east = B, Start, Back = Select, shoulders = L/R,
//           D-pad or left stick to move.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define SDL_MAIN_HANDLED
#include <SDL.h>
#include "port.h"
#include "render_gl.h"
#include "script.h"
#include "hdpack.h"

void TestHookRun(const char *cmd);

#define AUDIO_RATE 48000
#define FRAME_SECONDS (280896.0 / 16777216.0)

static SDL_Window *sWindow;
static SDL_GLContext sGl;
static int sUseGl;
static int sHdMode = 1;
static int sAutoShotFrame = -1;
static int sFixedAspect;
static int sInitW, sInitH;
static int sStartFullscreen;
// Display lock: on 60/120/180/240 Hz displays the game runs at refresh/N
// (60 fps) and each frame is shown for exactly N refreshes, paced by vsync.
static int sLockN, sLockDisabled, sLockChecks;
static uint64_t sLockT0;
static void UpdateDisplayLock(void);
static int sDumpAtStart;   // --aspect given: don't follow the window shape

// Match the game's visible width to the window's shape: wider screens show
// more of the overworld on each side (the height stays 160 GBA lines).
static void FitWidthToWindow(void)
{
    int w, h, gw;
    if (sFixedAspect || !sWindow)
        return;
    if (sUseGl)
        SDL_GL_GetDrawableSize(sWindow, &w, &h);
    else
        SDL_GetWindowSize(sWindow, &w, &h);
    if (h <= 0)
        return;
    gw = (int)((long long)w * GBA_H / h) & ~1;
    if (gw < GBA_W) gw = GBA_W;
    if (gw > PC_MAX_W) gw = PC_MAX_W;
    gPcScreenW = gw;
}
static char sAutoShotPath[1024];
static SDL_Renderer *sRenderer;
static SDL_Texture *sTexture;
static SDL_AudioDeviceID sAudio;
static SDL_GameController *sPad;
extern void HdSetTilt(float t);
extern float HdGetTilt(void);
static int sQuit;
static int sFastForward;
static uint64_t sNextFrame;
static char sBasePath[1024];
static uint32_t sLastFrame[PC_MAX_W * GBA_H];

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

#define MAX_SHOT_PIXELS (7680 * 4320)
static uint32_t *sShot;          // last frame as shown on screen
static int sShotW, sShotH, sWantShot;

static void SaveScreenshot(const char *path)
{
    SDL_Surface *s;

    if (sUseGl && sShot && sShotW > 0)
        s = SDL_CreateRGBSurfaceWithFormatFrom(sShot, sShotW, sShotH, 32, sShotW * 4, SDL_PIXELFORMAT_ABGR8888);
    else
        s = SDL_CreateRGBSurfaceWithFormatFrom(sLastFrame, gPcScreenW, GBA_H, 32, gPcScreenW * 4,
                                               SDL_PIXELFORMAT_ARGB8888);
    if (!s)
        return;
    SDL_SaveBMP(s, path);
    SDL_FreeSurface(s);
}

static void Screenshot(void)
{
    char path[1200];
    int n;
    for (n = 1; n < 10000; n++)
    {
        FILE *f;
        snprintf(path, sizeof(path), "%sscreenshot_%04d.bmp", sBasePath, n);
        f = fopen(path, "rb");
        if (!f)
            break;
        fclose(f);
    }
    SaveScreenshot(path);
}

#include "settings_ui.c"

int FrontendInit(int argc, char **argv)
{
    SDL_AudioSpec want, have;
    char *base;
    char savePath[1100];
    int i, scale = 4, scaleGiven = 0;

    for (i = 1; i < argc; i++)
    {
        if (!strcmp(argv[i], "--scale") && i + 1 < argc)
        {
            scale = atoi(argv[++i]);
            scaleGiven = 1;
        }
        else if (!strcmp(argv[i], "--original"))
            sHdMode = 0;
        else if (!strcmp(argv[i], "--aspect") && i + 1 < argc)
        {
            // e.g. 16:9, 21:9, 3:2 (original). Height stays 160 lines.
            int aw = 16, ah = 9, w;
            sscanf(argv[++i], "%d:%d", &aw, &ah);
            sFixedAspect = 1;
            w = ah > 0 ? (GBA_H * aw / ah + 1) & ~1 : GBA_W;
            gPcScreenW = w < GBA_W ? GBA_W : w > PC_MAX_W ? PC_MAX_W : w;
        }
        else if (!strcmp(argv[i], "--script") && i + 1 < argc)
            ScriptLoad(argv[++i]);
        else if (!strcmp(argv[i], "--dump-tiles"))
            sDumpAtStart = 1;
        else if (!strcmp(argv[i], "--no-display-lock"))
            sLockDisabled = 1;
        else if (!strcmp(argv[i], "--fullscreen"))
            sStartFullscreen = 1;
        else if (!strcmp(argv[i], "--autoshot") && i + 2 < argc)
        {
            sAutoShotFrame = atoi(argv[++i]);
            snprintf(sAutoShotPath, sizeof(sAutoShotPath), "%s", argv[++i]);
        }
    }
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
    // Default window: 16:9-ish and as large as comfortably fits the desktop.
    {
        SDL_DisplayMode dm;
        int winW = 0, winH = 0;
        if (SDL_GetDesktopDisplayMode(0, &dm) == 0 && !scaleGiven)
        {
            winH = dm.h * 3 / 4;
            winW = sFixedAspect ? winH * gPcScreenW / GBA_H : winH * 16 / 9;
            if (winW > dm.w * 9 / 10) { winW = dm.w * 9 / 10; winH = winW * 9 / 16; }
        }
        if (winW <= 0) { winW = gPcScreenW * scale; winH = GBA_H * scale; }
        sInitW = winW;
        sInitH = winH;
    }
    // Prefer OpenGL 3.3 for the HD renderer; fall back to SDL's renderer.
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
    SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1);
    sWindow = SDL_CreateWindow("Pokémon Emerald", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
                               sInitW, sInitH,
                               SDL_WINDOW_RESIZABLE | SDL_WINDOW_ALLOW_HIGHDPI | SDL_WINDOW_OPENGL);
    if (sWindow)
    {
        sGl = SDL_GL_CreateContext(sWindow);
        HdPackInit(sBasePath);
        if (sDumpAtStart)
            HdPackSetDump(1);
        if (sGl && !getenv("EMERALD_NOGL") && HdInit() == 0)
        {
            sUseGl = 1;
            LoadSettings();
            if (getenv("EMERALD_MENU"))
                MenuOpen(1);
            // Vsync (adaptive where supported) to avoid tearing; frame pacing
            // to the GBA's 59.73 Hz is still done by the timer below.
            if (SDL_GL_SetSwapInterval(-1) != 0)
                SDL_GL_SetSwapInterval(1);
        }
        else
        {
            fprintf(stderr, "OpenGL 3.3 unavailable (%s); using basic renderer\n", SDL_GetError());
            if (sGl)
                SDL_GL_DeleteContext(sGl);
            sGl = NULL;
            SDL_DestroyWindow(sWindow);
            sWindow = NULL;
        }
    }
    if (!sWindow)
        sWindow = SDL_CreateWindow("Pokémon Emerald", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
                                   sInitW, sInitH, SDL_WINDOW_RESIZABLE | SDL_WINDOW_ALLOW_HIGHDPI);
    if (!sWindow)
    {
        fprintf(stderr, "SDL_CreateWindow failed: %s\n", SDL_GetError());
        return 1;
    }
    if (!sUseGl)
    {
        sFixedAspect = 1; // the basic renderer keeps one texture size
        sRenderer = SDL_CreateRenderer(sWindow, -1, SDL_RENDERER_ACCELERATED);
        if (!sRenderer)
            sRenderer = SDL_CreateRenderer(sWindow, -1, SDL_RENDERER_SOFTWARE);
        SDL_RenderSetLogicalSize(sRenderer, gPcScreenW, GBA_H);
        sTexture = SDL_CreateTexture(sRenderer, SDL_PIXELFORMAT_ARGB8888, SDL_TEXTUREACCESS_STREAMING, gPcScreenW, GBA_H);
    }

    SDL_zero(want);
    want.freq = AUDIO_RATE;
    want.format = AUDIO_S16SYS;
    want.channels = 2;
    want.samples = 1024;
    sAudio = SDL_OpenAudioDevice(NULL, 0, &want, &have, 0);
    if (sAudio)
        SDL_PauseAudioDevice(sAudio, 0);

    if (sStartFullscreen)
        SDL_SetWindowFullscreen(sWindow, SDL_WINDOW_FULLSCREEN_DESKTOP);
    UpdateDisplayLock();
    FitWidthToWindow();
    OpenPad();
    sNextFrame = SDL_GetPerformanceCounter();
    return 0;
}

static void UpdateDisplayLock(void)
{
    SDL_DisplayMode dm;
    int n = 0;
    if (!sUseGl || sLockDisabled || SDL_GL_GetSwapInterval() == 0)
    {
        sLockN = 0;
        M4aPcSetFrameRate(0);
        return;
    }
    if (SDL_GetCurrentDisplayMode(SDL_GetWindowDisplayIndex(sWindow), &dm) == 0 && dm.refresh_rate > 0)
    {
        int r = dm.refresh_rate;
        if (r >= 59 && r <= 61) n = 1;
        else if (r >= 119 && r <= 121) n = 2;
        else if (r >= 179 && r <= 181) n = 3;
        else if (r >= 239 && r <= 241) n = 4;
        if (n)
            M4aPcSetFrameRate((double)r / n);
    }
    if (!n)
        M4aPcSetFrameRate(0);
    sLockN = n;
    sLockChecks = 0;
    sLockT0 = SDL_GetPerformanceCounter();
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
        if (MenuEvent(&e))
            continue;
        if ((e.type == SDL_KEYDOWN && e.key.keysym.sym == SDLK_F10 && sUseGl)
         || (e.type == SDL_CONTROLLERBUTTONDOWN && e.cbutton.button == SDL_CONTROLLER_BUTTON_GUIDE && sUseGl))
        {
            MenuOpen(1);
            continue;
        }
        switch (e.type)
        {
        case SDL_QUIT:
            sQuit = 1;
            break;
        case SDL_MOUSEWHEEL:   // mouse wheel tilts the camera
            HdSetTilt(HdGetTilt() + e.wheel.y * 0.08f);
            break;
        case SDL_MOUSEMOTION:  // or drag with the right mouse button
            if (e.motion.state & SDL_BUTTON_RMASK)
                HdSetTilt(HdGetTilt() - e.motion.yrel * 0.005f);
            break;
        case SDL_KEYDOWN:
            if (e.key.keysym.sym == SDLK_F11
             || (e.key.keysym.sym == SDLK_RETURN && (e.key.keysym.mod & KMOD_ALT)))
                ToggleFullscreen();
            else if (e.key.keysym.sym == SDLK_F12)
            {
                if (sUseGl)
                    sWantShot = 1; // captured after the next frame is drawn
                else
                    Screenshot();
            }
            else if (e.key.keysym.sym == SDLK_F1)
                sHdMode = !sHdMode;
            else if (e.key.keysym.sym == SDLK_F2 && sUseGl)
                HdSetScale(HdGetScale() >= 6 ? 2 : HdGetScale() + 1);
            else if (e.key.keysym.sym == SDLK_F3 && sUseGl)
                HdSetGrade(!HdGetGrade());
            else if (e.key.keysym.sym == SDLK_F4 && sUseGl)
                HdSetLighting(!HdGetLighting());
            else if (e.key.keysym.sym == SDLK_F5)
            {
                extern int gPcHdAudio;
                extern void M4aPcSetHdAudio(int on);
                M4aPcSetHdAudio(!gPcHdAudio);
                SDL_SetWindowTitle(sWindow, gPcHdAudio ? "Pokémon Emerald  [HD audio]" : "Pokémon Emerald  [original audio]");
            }
            else if (e.key.keysym.sym == SDLK_m && sUseGl)
            {
                extern void HdSetMinimap(int on);
                extern int HdGetMinimap(void);
                HdSetMinimap(!HdGetMinimap());
            }
            else if (e.key.keysym.sym == SDLK_F8 && sUseGl)
            {
                extern void HdCycleTilt(void);
                extern float HdGetTilt(void);
                char t[64];
                HdCycleTilt();
                snprintf(t, sizeof(t), "Pokémon Emerald  [tilt %s]", HdGetTilt() <= 0 ? "off" : HdGetTilt() < 0.3f ? "gentle" : HdGetTilt() < 0.5f ? "normal" : "strong");
                SDL_SetWindowTitle(sWindow, t);
            }
            else if (e.key.keysym.sym == SDLK_F7)
            {
                extern int gPcSynthInstruments;
                extern void M4aPcSetSynth(int on);
                M4aPcSetSynth(!gPcSynthInstruments);
                SDL_SetWindowTitle(sWindow, gPcSynthInstruments ? "Pokémon Emerald  [new instruments]" : "Pokémon Emerald  [original instruments]");
            }
            else if (e.key.keysym.sym == SDLK_F6)
            {
                HdPackSetDump(!gHdDumpEnabled);
                SDL_SetWindowTitle(sWindow, gHdDumpEnabled ? "Pokémon Emerald  [dumping tiles to hd/dump]" : "Pokémon Emerald");
            }
            else if (e.key.keysym.sym == SDLK_ESCAPE)
                sQuit = 1;
            break;
        case SDL_WINDOWEVENT:
            if (e.window.event == SDL_WINDOWEVENT_SIZE_CHANGED)
                FitWidthToWindow();
            if (e.window.event == SDL_WINDOWEVENT_MOVED || e.window.event == SDL_WINDOWEVENT_DISPLAY_CHANGED)
                UpdateDisplayLock();
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

    memcpy(sLastFrame, fb, (size_t)gPcScreenW * GBA_H * 4);
    PumpEvents();

    // Fast-forward renders every 4th frame and skips pacing.
    if (ScriptActive() ? ScriptShotDue() : (!sFastForward || (PortFrameCount() & 3) == 0))
    {
        if (sUseGl)
        {
            int w, h;
            SDL_GL_GetDrawableSize(sWindow, &w, &h);
            HdPresent(fb, sHdMode, w, h);
            if (sWantShot || (ScriptActive() && ScriptShotDue()))
            {
                if (!sShot)
                    sShot = malloc((size_t)MAX_SHOT_PIXELS * 4);
                if (sShot && HdReadFrame(sShot, &sShotW, &sShotH, MAX_SHOT_PIXELS) != 0)
                    sShotW = 0;
            }
            SDL_GL_SwapWindow(sWindow);
            // High-refresh displays: show the same image for the remaining refreshes.
            if (sLockN > 1 && !sFastForward && !ScriptActive())
            {
                int k;
                for (k = 1; k < sLockN; k++)
                {
                    HdPresentAgain(w, h);
                    SDL_GL_SwapWindow(sWindow);
                }
            }
            if (sWantShot)
            {
                sWantShot = 0;
                Screenshot();
            }
        }
        else
        {
            SDL_UpdateTexture(sTexture, NULL, fb, gPcScreenW * 4);
            SDL_SetRenderDrawColor(sRenderer, 0, 0, 0, 255);
            SDL_RenderClear(sRenderer);
            SDL_RenderCopy(sRenderer, sTexture, NULL, NULL);
            SDL_RenderPresent(sRenderer);
        }
    }

    if (sAutoShotFrame >= 0 && (int)PortFrameCount() >= sAutoShotFrame)
    {
        if (sUseGl)
        {
            int w, h;
            if (!sShot)
                sShot = malloc((size_t)MAX_SHOT_PIXELS * 4);
            SDL_GL_GetDrawableSize(sWindow, &w, &h);
            HdPresent(fb, sHdMode, w, h);
            if (sShot && HdReadFrame(sShot, &sShotW, &sShotH, MAX_SHOT_PIXELS) != 0)
                sShotW = 0;
        }
        SaveScreenshot(sAutoShotPath);
        sQuit = 1;
    }

    if (sFastForward)
    {
        sNextFrame = SDL_GetPerformanceCounter();
        return;
    }

    if (sLockN && !ScriptActive())
    {
        // Paced by vsync. Make sure the driver really waits for it: if 120
        // frames arrive much faster than the refresh rate, use the timer.
        if (++sLockChecks == 120)
        {
            double secs = (double)(SDL_GetPerformanceCounter() - sLockT0) / freq;
            if (secs < 120.0 / 60.0 * 0.8)
            {
                sLockN = 0;
                M4aPcSetFrameRate(0);
            }
        }
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
    {
        // Keyboard: Page Up / Page Down (or I / K) tilt the camera.
        const Uint8 *ks = SDL_GetKeyboardState(NULL);
        if (ks[SDL_SCANCODE_PAGEUP] || ks[SDL_SCANCODE_I]) HdSetTilt(HdGetTilt() + 0.02f);
        if (ks[SDL_SCANCODE_PAGEDOWN] || ks[SDL_SCANCODE_K]) HdSetTilt(HdGetTilt() - 0.02f);
    }
    const uint8_t *k = SDL_GetKeyboardState(NULL);
    uint16_t keys = 0;

    if (ScriptActive())
    {
        sFastForward = 1; // scripted runs go as fast as possible
        return ScriptStep(SaveScreenshot, TestHookRun, &sQuit);
    }

    if (sMenuOpen)
        return 0;
    {
        int i;
        for (i = 0; i < 10; i++)
            if (k[sKeyMap[i]]) keys |= sButtonBits[i];
    }
    if (sPad && SDL_GameControllerGetButton(sPad, SDL_CONTROLLER_BUTTON_BACK) && SDL_GameControllerGetButton(sPad, SDL_CONTROLLER_BUTTON_START))
    {
        MenuOpen(1);   // Back + Start opens the settings
        return 0;
    }
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
        {
            // Right stick up/down tilts the camera.
            int16_t ry = SDL_GameControllerGetAxis(sPad, SDL_CONTROLLER_AXIS_RIGHTY);
            if (ry > 6000 || ry < -6000)
                HdSetTilt(HdGetTilt() - ry / 32768.0f * 0.025f);
        }
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
