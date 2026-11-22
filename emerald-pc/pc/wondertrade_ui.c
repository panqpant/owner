// Wonder Trade screen (W on the keyboard, Y on a gamepad, on the overworld):
// pick a Pokémon, "search" with a spinning globe like X/Y and OR/AS, meet the
// partner, then the game's own trade scene plays and a result card shows
// what arrived. Included by frontend_sdl.c after settings_ui.c.
#include "wondertrade.h"
#include <math.h>

enum { WT_CLOSED, WT_PICK, WT_SEARCH, WT_FOUND, WT_TRADING, WT_RESULT };
static int sWtState, sWtSel, sWtTimer, sWtSearchLen, sWtMsg;

static void WtCircle(int cx, int cy, int r, uint32_t argb)
{
    int x, y;
    for (y = -r; y <= r; y++)
        for (x = -r; x <= r; x++)
            if (x * x + y * y <= r * r) OvRect(cx + x, cy + y, 1, 1, argb);
}

// A turning globe: blue sphere, drifting continents, latitude and longitude lines.
static void WtGlobe(int cx, int cy, int r, float t)
{
    int x, y;
    for (y = -r; y <= r; y++)
        for (x = -r; x <= r; x++)
        {
            float nx = x / (float)r, ny = y / (float)r, nz2 = 1.0f - nx * nx - ny * ny, nz, lon, lat, land, shade;
            uint32_t col;
            if (nz2 < 0) continue;
            nz = sqrtf(nz2);
            lon = atan2f(nx, nz) + t;
            lat = asinf(ny);
            land = sinf(lon * 3.0f) * cosf(lat * 4.0f) + 0.6f * sinf(lon * 5.0f + 1.3f) * sinf(lat * 3.0f + 0.7f);
            shade = 0.55f + 0.45f * (nz * 0.8f - nx * 0.3f - ny * 0.3f);
            if (land > 0.55f)
                col = 0xFF000000u | ((uint32_t)(90 * shade) << 16) | ((uint32_t)(190 * shade) << 8) | (uint32_t)(120 * shade);
            else
                col = 0xFF000000u | ((uint32_t)(70 * shade) << 16) | ((uint32_t)(140 * shade) << 8) | (uint32_t)(235 * shade);
            if (fabsf(fmodf(lon + 100.0f, 0.5236f)) < 0.025f || fabsf(fmodf(lat + 10.0f, 0.3927f)) < 0.02f)
                col = 0xFFB8E8FFu;
            OvRect(cx + x, cy + y, 1, 1, col);
        }
    // a glowing ring
    for (y = -r - 6; y <= r + 6; y++)
        for (x = -r - 6; x <= r + 6; x++)
        {
            float d = sqrtf((float)(x * x + y * y)) - r;
            if (d > 0 && d < 6) OvRect(cx + x, cy + y, 1, 1, ((uint32_t)(140 * (1 - d / 6)) << 24) | 0x8FE6FF);
        }
}

static void WtDraw(void)
{
    int i, x0 = 230, y0 = 40, w = 500;
    char line[96];
    memset(sOv, 0, sizeof(sOv));
    if (sWtState == WT_PICK)
    {
        OvRect(0, 0, OV_W, OV_H, 0x99000000);
        OvRect(x0, y0, w, 460, 0xEE10223A);
        OvRect(x0, y0, w, 4, 0xFF38B8F8);
        OvText(x0 + 24, y0 + 14, "Wonder Trade", 1.0f, 0xFFFFFF);
        OvText(x0 + 24, y0 + 52, "Which Pokemon will you offer?", 0.62f, 0xB8D8F8);
        for (i = 0; i < gPcWt.count && i < 6; i++)
        {
            int y = y0 + 92 + i * 46;
            int ok = !gPcWt.egg[i] && !(gPcWt.usable <= 1 && gPcWt.level[i] > 0 && !gPcWt.egg[i] && 0);
            if (i == sWtSel) OvRect(x0 + 14, y - 6, w - 28, 42, 0x6038B8F8);
            snprintf(line, sizeof(line), "%s", gPcWt.egg[i] ? "Egg" : gPcWt.name[i]);
            OvText(x0 + 34, y, line, 0.8f, ok ? 0xF4F8FF : 0x808890);
            if (!gPcWt.egg[i])
            {
                snprintf(line, sizeof(line), "Lv. %d", gPcWt.level[i]);
                OvText(x0 + w - 130, y, line, 0.8f, 0xB8D8F8);
            }
        }
        if (sWtMsg) OvText(x0 + 24, y0 + 380, "You can't trade your last Pokemon that can battle!", 0.55f, 0xFF9080);
        OvText(x0 + 24, y0 + 426, "Up/Down: choose   Enter/A: offer   Esc/B: cancel", 0.55f, 0x90A8C8);
    }
    else if (sWtState == WT_SEARCH || sWtState == WT_FOUND)
    {
        float t = sWtTimer / 60.0f;
        OvRect(0, 0, OV_W, OV_H, 0xC0050A18);
        WtGlobe(OV_W / 2, 230, 120, t * 0.9f);
        if (sWtState == WT_SEARCH)
        {
            int dots = (sWtTimer / 20) % 4;
            snprintf(line, sizeof(line), "Searching for a trade partner%.*s", dots, "...");
            OvText(OV_W / 2 - OvTextWidth("Searching for a trade partner...", 0.8f) / 2, 400, line, 0.8f, 0xFFFFFF);
            // satellites of light orbiting the globe
            for (i = 0; i < 3; i++)
            {
                float a = t * (1.6f + i * 0.4f) + i * 2.1f;
                WtCircle(OV_W / 2 + (int)(cosf(a) * 160), 230 + (int)(sinf(a) * 46), 4, 0xFFFFF0A0);
            }
            OvText(OV_W / 2 - OvTextWidth("Esc/B: cancel", 0.5f) / 2, 470, "Esc/B: cancel", 0.5f, 0x8098B8);
        }
        else
        {
            OvText(OV_W / 2 - OvTextWidth("Trade partner found!", 0.9f) / 2, 380, "Trade partner found!", 0.9f, 0xFFE070);
            snprintf(line, sizeof(line), "%s  -  %s", gPcWt.partner, gPcWt.country);
            OvText(OV_W / 2 - OvTextWidth(line, 0.75f) / 2, 430, line, 0.75f, 0xFFFFFF);
        }
    }
    else if (sWtState == WT_RESULT)
    {
        OvRect(x0 - 60, 330, w + 120, 170, 0xEE10223A);
        OvRect(x0 - 60, 330, w + 120, 4, gPcWt.shiny ? 0xFFFFD040 : 0xFF38B8F8);
        OvText(x0 - 36, 344, gPcWt.shiny ? "Wonder Trade complete!   It's shiny!" : "Wonder Trade complete!", 0.7f, gPcWt.shiny ? 0xFFE070 : 0xB8D8F8);
        OvText(x0 - 36, 386, gPcWt.resultLine1, 0.85f, 0xFFFFFF);
        OvText(x0 - 36, 428, gPcWt.resultLine2, 0.6f, 0xD8E4F4);
        OvText(x0 - 36, 460, gPcWt.resultLine3, 0.6f, 0xD8E4F4);
    }
    HdSetOverlay(sWtState == WT_CLOSED || sWtState == WT_TRADING ? NULL : sOv, OV_W, OV_H);
}

static int WtActive(void) { return sWtState != WT_CLOSED && sWtState != WT_TRADING; }

static void WtOpen(void)
{
    if (!gPcWt.canOpen || sMenuOpen || sWtState != WT_CLOSED)
        return;
    sWtState = WT_PICK;
    sWtSel = 0;
    sWtMsg = 0;
    WtDraw();
}

// Called once per frame.
static void WtTick(void)
{
    if (getenv("EMERALD_WT_AUTO") && sWtState == WT_CLOSED && gPcWt.canOpen && !gPcWt.done)
    {
        static int wait;
        if (++wait > 30) { sWtState = WT_SEARCH; gPcWt.offerSlot = atoi(getenv("EMERALD_WT_AUTO")); sWtTimer = 0; sWtSearchLen = 240; wait = 0; }
    }
    switch (sWtState)
    {
    case WT_SEARCH:
        sWtTimer++;
        if (sWtTimer >= sWtSearchLen && gPcWt.found) { sWtState = WT_FOUND; sWtTimer = 0; }
        WtDraw();
        break;
    case WT_FOUND:
        sWtTimer++;
        if (sWtTimer > 150) { sWtState = WT_TRADING; gPcWt.go = 1; WtDraw(); }
        else WtDraw();
        break;
    case WT_TRADING:
        if (gPcWt.done) { gPcWt.done = 0; sWtState = WT_RESULT; sWtTimer = 0; WtDraw(); }
        break;
    case WT_RESULT:
        if (++sWtTimer > 480) { sWtState = WT_CLOSED; WtDraw(); }
        break;
    }
}

static int WtEvent(const SDL_Event *e)
{
    int up = 0, down = 0, ok = 0, back = 0;
    if (e->type == SDL_KEYDOWN && e->key.keysym.sym == SDLK_w && sWtState == WT_CLOSED) { WtOpen(); return sWtState != WT_CLOSED; }
    if (e->type == SDL_CONTROLLERBUTTONDOWN && e->cbutton.button == SDL_CONTROLLER_BUTTON_Y && sWtState == WT_CLOSED) { WtOpen(); return sWtState != WT_CLOSED; }
    if (!WtActive())
        return 0;
    if (e->type == SDL_KEYDOWN)
    {
        SDL_Keycode k = e->key.keysym.sym;
        up = k == SDLK_UP; down = k == SDLK_DOWN; ok = k == SDLK_RETURN || k == SDLK_x || k == SDLK_SPACE; back = k == SDLK_ESCAPE || k == SDLK_z;
    }
    else if (e->type == SDL_CONTROLLERBUTTONDOWN)
    {
        int b = e->cbutton.button;
        up = b == SDL_CONTROLLER_BUTTON_DPAD_UP; down = b == SDL_CONTROLLER_BUTTON_DPAD_DOWN;
        ok = b == SDL_CONTROLLER_BUTTON_A; back = b == SDL_CONTROLLER_BUTTON_B;
    }
    else
        return e->type == SDL_KEYUP || e->type == SDL_CONTROLLERBUTTONUP;
    if (sWtState == WT_PICK)
    {
        int n = gPcWt.count > 0 ? gPcWt.count : 1;
        if (up) sWtSel = (sWtSel + n - 1) % n;
        if (down) sWtSel = (sWtSel + 1) % n;
        if (back) { sWtState = WT_CLOSED; }
        if (ok && !gPcWt.egg[sWtSel])
        {
            if (gPcWt.usable <= 1)
                sWtMsg = 1;
            else
            {
                gPcWt.offerSlot = sWtSel;
                sWtState = WT_SEARCH;
                sWtTimer = 0;
                sWtSearchLen = 180 + rand() % 540;   // 3-12 seconds, like the real thing
            }
        }
    }
    else if (sWtState == WT_SEARCH && back)
    {
        gPcWt.offerSlot = -1;
        gPcWt.found = 0;
        sWtState = WT_CLOSED;
    }
    else if (sWtState == WT_RESULT && (ok || back))
        sWtState = WT_CLOSED;
    WtDraw();
    return 1;
}
