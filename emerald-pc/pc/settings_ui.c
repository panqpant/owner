// Settings screen (F10, or Back+Start on a gamepad): every effect switch and
// slider, audio options, and rebindable keyboard controls. Saved to
// settings.ini next to the game. Drawn on the CPU into an overlay texture
// that the renderer lays over the picture. Included by frontend_sdl.c.
#include "uifont.h"

extern void HdSetGrade(int on);   extern int HdGetGrade(void);
extern void HdSetLighting(int on); extern int HdGetLighting(void);
extern void HdSetGi(int on);      extern int HdGetGi(void);
extern void HdSetShatter(int on); extern int HdGetShatter(void);
extern void HdSetOverlay(const uint32_t *rgba, int w, int h);
extern int gPcHdAudio, gPcSynthInstruments;
extern float gPcAmbientVol;
extern void M4aPcSetHdAudio(int on);
extern void M4aPcSetSynth(int on);

#define OV_W 960
#define OV_H 540
static uint32_t sOv[OV_W * OV_H];
static int sMenuOpen, sMenuSel, sMenuPage, sRebinding = -1;

static const char *const sButtonNames[10] = { "A", "B", "Start", "Select", "L", "R", "Up", "Down", "Left", "Right" };
static const uint16_t sButtonBits[10] = { PC_KEY_A, PC_KEY_B, PC_KEY_START, PC_KEY_SELECT, PC_KEY_L, PC_KEY_R,
                                          PC_KEY_UP, PC_KEY_DOWN, PC_KEY_LEFT, PC_KEY_RIGHT };
static int sKeyMap[10] = { SDL_SCANCODE_X, SDL_SCANCODE_Z, SDL_SCANCODE_RETURN, SDL_SCANCODE_BACKSPACE, SDL_SCANCODE_A,
                           SDL_SCANCODE_S, SDL_SCANCODE_UP, SDL_SCANCODE_DOWN, SDL_SCANCODE_LEFT, SDL_SCANCODE_RIGHT };

enum { IT_TOGGLE, IT_SLIDER, IT_ACTION };
struct MenuItem { const char *name; int type; };
static const struct MenuItem sItems[] = {
    { "HD graphics", IT_TOGGLE }, { "Colour grade", IT_TOGGLE }, { "Lighting and effects", IT_TOGGLE },
    { "Ray-traced light", IT_TOGGLE }, { "Camera tilt", IT_SLIDER }, { "Battle intros", IT_TOGGLE },
    { "HD audio", IT_TOGGLE }, { "Brass/strings layer", IT_TOGGLE }, { "Ambient sound", IT_SLIDER },
    { "Fullscreen", IT_TOGGLE }, { "Controls...", IT_ACTION }, { "Close", IT_ACTION },
};
#define NUM_ITEMS (int)(sizeof(sItems) / sizeof(sItems[0]))

static float ItemValue(int i)
{
    switch (i)
    {
    case 0: return sHdMode;
    case 1: return HdGetGrade();
    case 2: return HdGetLighting();
    case 3: return HdGetGi();
    case 4: return HdGetTilt() / 1.2f;
    case 5: return HdGetShatter();
    case 6: return gPcHdAudio;
    case 7: return gPcSynthInstruments;
    case 8: return gPcAmbientVol / 2.0f;
    case 9: return (SDL_GetWindowFlags(sWindow) & SDL_WINDOW_FULLSCREEN_DESKTOP) != 0;
    }
    return 0;
}

static void ToggleFullscreen(void);
static void ItemChange(int i, int dir)
{
    switch (i)
    {
    case 0: sHdMode = !sHdMode; break;
    case 1: HdSetGrade(!HdGetGrade()); break;
    case 2: HdSetLighting(!HdGetLighting()); break;
    case 3: HdSetGi(!HdGetGi()); break;
    case 4: HdSetTilt(HdGetTilt() + dir * 0.1f); break;
    case 5: HdSetShatter(!HdGetShatter()); break;
    case 6: M4aPcSetHdAudio(!gPcHdAudio); break;
    case 7: M4aPcSetSynth(!gPcSynthInstruments); break;
    case 8: gPcAmbientVol += dir * 0.1f; if (gPcAmbientVol < 0) gPcAmbientVol = 0; if (gPcAmbientVol > 2) gPcAmbientVol = 2; break;
    case 9: ToggleFullscreen(); break;
    }
}

// ---- Saving ----
static void SettingsPath(char *out, size_t n) { snprintf(out, n, "%ssettings.ini", sBasePath); }
static void SaveSettings(void)
{
    char p[1100];
    FILE *f;
    int i;
    SettingsPath(p, sizeof(p));
    f = fopen(p, "w");
    if (!f) return;
    fprintf(f, "hd=%d\ngrade=%d\nlighting=%d\ngi=%d\ntilt=%.2f\nshatter=%d\nhdaudio=%d\nlayer=%d\nambient=%.2f\n",
            sHdMode, HdGetGrade(), HdGetLighting(), HdGetGi(), HdGetTilt(), HdGetShatter(), gPcHdAudio, gPcSynthInstruments, gPcAmbientVol);
    for (i = 0; i < 10; i++)
        fprintf(f, "key_%s=%s\n", sButtonNames[i], SDL_GetScancodeName((SDL_Scancode)sKeyMap[i]));
    fclose(f);
}
static void LoadSettings(void)
{
    char p[1100], line[256];
    FILE *f;
    SettingsPath(p, sizeof(p));
    f = fopen(p, "r");
    if (!f) return;
    while (fgets(line, sizeof(line), f))
    {
        char *eq = strchr(line, '='), *v;
        int i;
        if (!eq) continue;
        *eq = 0; v = eq + 1; v[strcspn(v, "\r\n")] = 0;
        if (!strcmp(line, "hd")) sHdMode = atoi(v);
        else if (!strcmp(line, "grade")) HdSetGrade(atoi(v));
        else if (!strcmp(line, "lighting")) HdSetLighting(atoi(v));
        else if (!strcmp(line, "gi")) HdSetGi(atoi(v));
        else if (!strcmp(line, "tilt")) HdSetTilt((float)atof(v));
        else if (!strcmp(line, "shatter")) HdSetShatter(atoi(v));
        else if (!strcmp(line, "hdaudio")) M4aPcSetHdAudio(atoi(v));
        else if (!strcmp(line, "layer")) M4aPcSetSynth(atoi(v));
        else if (!strcmp(line, "ambient")) gPcAmbientVol = (float)atof(v);
        else for (i = 0; i < 10; i++)
        {
            char k[32];
            snprintf(k, sizeof(k), "key_%s", sButtonNames[i]);
            if (!strcmp(line, k))
            {
                SDL_Scancode sc = SDL_GetScancodeFromName(v);
                if (sc != SDL_SCANCODE_UNKNOWN) sKeyMap[i] = sc;
            }
        }
    }
    fclose(f);
}

// ---- Drawing ----
static void OvRect(int x0, int y0, int w, int h, uint32_t argb)
{
    int x, y;
    uint32_t a = argb >> 24;
    for (y = y0; y < y0 + h; y++)
        for (x = x0; x < x0 + w; x++)
        {
            uint32_t *d, s;
            if (x < 0 || y < 0 || x >= OV_W || y >= OV_H) continue;
            d = &sOv[y * OV_W + x];
            s = *d;
            {
                uint32_t sa = s >> 24, oa = a + sa * (255 - a) / 255, c, out = oa << 24;
                for (c = 0; c < 24; c += 8)
                {
                    uint32_t sc = (s >> c) & 255, nc = (argb >> c) & 255;
                    uint32_t v = oa ? (nc * a + sc * sa * (255 - a) / 255) / oa : 0;
                    out |= (v > 255 ? 255 : v) << c;
                }
                *d = out;
            }
        }
}
static int OvTextWidth(const char *t, float sc)
{
    int w = 0;
    for (; *t; t++) if (*t >= 32 && *t < 127) w += sUiFontW[*t - 32];
    return (int)(w * sc);
}
static void OvText(int x0, int y0, const char *t, float sc, uint32_t rgb)
{
    for (; *t; t++)
    {
        int ch = *t, gw, x, y;
        if (ch < 32 || ch > 126) continue;
        gw = sUiFontW[ch - 32];
        for (y = 0; y < (int)(UIFONT_H * sc); y++)
            for (x = 0; x < (int)(gw * sc); x++)
            {
                int cov = sUiFontPx[sUiFontOff[ch - 32] + (int)(y / sc) * gw + (int)(x / sc)];
                if (cov) OvRect(x0 + x, y0 + y, 1, 1, ((uint32_t)cov << 24) | rgb);
            }
        x0 += (int)(gw * sc);
    }
}

static void DrawMenu(void)
{
    int i, x0 = 220, y0 = 22, w = 520, rowH = 32;
    memset(sOv, 0, sizeof(sOv));
    OvRect(0, 0, OV_W, OV_H, 0x99000000);
    OvRect(x0, y0, w, 496, 0xE8182030);
    OvRect(x0, y0, w, 4, 0xFF5AC8A0);
    if (sMenuPage == 0)
    {
        OvText(x0 + 24, y0 + 14, "Settings", 1.0f, 0xFFFFFF);
        for (i = 0; i < NUM_ITEMS; i++)
        {
            int y = y0 + 58 + i * rowH;
            if (i == sMenuSel) OvRect(x0 + 12, y - 3, w - 24, rowH - 2, 0x6040A080);
            OvText(x0 + 28, y, sItems[i].name, 0.8f, 0xF0F0F0);
            if (sItems[i].type == IT_TOGGLE)
                OvText(x0 + w - 90, y, ItemValue(i) > 0.5f ? "On" : "Off", 0.8f, ItemValue(i) > 0.5f ? 0x7CE8B0 : 0xA0A0A0);
            else if (sItems[i].type == IT_SLIDER)
            {
                OvRect(x0 + w - 190, y + 9, 160, 6, 0xFF404858);
                OvRect(x0 + w - 190, y + 9, (int)(160 * ItemValue(i)), 6, 0xFF5AC8A0);
            }
        }
        OvText(x0 + 24, y0 + 466, "Arrows: choose/change   Enter: select   F10/Esc: close", 0.55f, 0xA0A8B8);
    }
    else
    {
        OvText(x0 + 24, y0 + 14, "Controls", 1.0f, 0xFFFFFF);
        for (i = 0; i <= 10; i++)
        {
            int y = y0 + 58 + i * rowH;
            if (i == sMenuSel) OvRect(x0 + 12, y - 3, w - 24, rowH - 2, 0x6040A080);
            if (i == 10) { OvText(x0 + 28, y, "Back", 0.8f, 0xF0F0F0); break; }
            OvText(x0 + 28, y, sButtonNames[i], 0.8f, 0xF0F0F0);
            OvText(x0 + w - 200, y, sRebinding == i ? "press a key..." : SDL_GetScancodeName((SDL_Scancode)sKeyMap[i]), 0.8f,
                   sRebinding == i ? 0xFFD060 : 0x7CE8B0);
        }
        OvText(x0 + 24, y0 + 466, "Enter: rebind   Esc: back", 0.55f, 0xA0A8B8);
    }
    HdSetOverlay(sOv, OV_W, OV_H);
}

static void MenuOpen(int open)
{
    sMenuOpen = open;
    sMenuSel = 0; sMenuPage = 0; sRebinding = -1;
    if (open) DrawMenu();
    else { HdSetOverlay(NULL, 0, 0); SaveSettings(); }
}

// Returns 1 if the menu used the event.
static int MenuEvent(const SDL_Event *e)
{
    int up = 0, down = 0, left = 0, right = 0, ok = 0, back = 0;
    if (!sMenuOpen) return 0;
    if (e->type == SDL_KEYDOWN)
    {
        SDL_Keycode k = e->key.keysym.sym;
        if (sRebinding >= 0)
        {
            if (k != SDLK_ESCAPE) sKeyMap[sRebinding] = e->key.keysym.scancode;
            sRebinding = -1; DrawMenu(); return 1;
        }
        up = k == SDLK_UP; down = k == SDLK_DOWN; left = k == SDLK_LEFT; right = k == SDLK_RIGHT;
        ok = k == SDLK_RETURN || k == SDLK_SPACE || k == SDLK_x; back = k == SDLK_ESCAPE || k == SDLK_F10 || k == SDLK_z;
    }
    else if (e->type == SDL_CONTROLLERBUTTONDOWN)
    {
        int b = e->cbutton.button;
        up = b == SDL_CONTROLLER_BUTTON_DPAD_UP; down = b == SDL_CONTROLLER_BUTTON_DPAD_DOWN;
        left = b == SDL_CONTROLLER_BUTTON_DPAD_LEFT; right = b == SDL_CONTROLLER_BUTTON_DPAD_RIGHT;
        ok = b == SDL_CONTROLLER_BUTTON_A; back = b == SDL_CONTROLLER_BUTTON_B || b == SDL_CONTROLLER_BUTTON_GUIDE;
    }
    else
        return e->type == SDL_KEYUP || e->type == SDL_CONTROLLERBUTTONUP;
    {
        int n = sMenuPage == 0 ? NUM_ITEMS : 11;
        if (up) sMenuSel = (sMenuSel + n - 1) % n;
        if (down) sMenuSel = (sMenuSel + 1) % n;
        if (sMenuPage == 0)
        {
            if ((left || right) && sItems[sMenuSel].type != IT_ACTION) ItemChange(sMenuSel, right ? 1 : -1);
            if (ok)
            {
                if (sItems[sMenuSel].type == IT_TOGGLE) ItemChange(sMenuSel, 1);
                else if (sMenuSel == NUM_ITEMS - 2) { sMenuPage = 1; sMenuSel = 0; }
                else if (sMenuSel == NUM_ITEMS - 1) { MenuOpen(0); return 1; }
            }
            if (back) { MenuOpen(0); return 1; }
        }
        else
        {
            if (ok) { if (sMenuSel == 10) { sMenuPage = 0; sMenuSel = NUM_ITEMS - 2; } else sRebinding = sMenuSel; }
            if (back) { sMenuPage = 0; sMenuSel = NUM_ITEMS - 2; }
        }
    }
    DrawMenu();
    return 1;
}
