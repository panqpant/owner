// Black 2 Online: a DS emulator (melonDS) with a link to a second PC on the same network.
// The patched game keeps a mailbox in RAM (rom/b2o_mailbox.h); ds_bridge moves it over net.
#include <SDL.h>

#include <algorithm>
#include <cctype>
#include <cstdarg>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <string>

#include "ds_bridge.h"
#include "ds_platform.h"
#include "font8x16.h"
#include "net.h"
#include "species.h"

static const char* kRomName = "Pokemon_Black2_Online.nds";
static const double kFrameRate = 59.8261;

// ---------------------------------------------------------------------------------------------
// Settings, kept in b2online.ini next to the app

struct Settings {
    int clockMode = 0;   // 0 PC time, 1 morning, 2 day, 3 evening, 4 night
    int seasonMode = 0;  // 0 from the PC's month, 1 spring, 2 summer, 3 autumn, 4 winter
    int layout = 0;      // 0 stacked, 1 side by side, 2 big top screen
    int scale = 2;
    char lastAddr[96] = "";
};

static std::string g_dir;

static std::string path_in_dir(const char* name) { return g_dir + name; }

static void load_settings(Settings& s)
{
    FILE* f = ds_fopen(path_in_dir("b2online.ini").c_str(), "r");
    if (!f) return;
    char line[160];
    while (fgets(line, sizeof(line), f)) {
        char key[32], val[96];
        if (sscanf(line, "%31[^=]=%95[^\r\n]", key, val) != 2) continue;
        if (!strcmp(key, "clock")) s.clockMode = std::clamp(atoi(val), 0, 4);
        else if (!strcmp(key, "season")) s.seasonMode = std::clamp(atoi(val), 0, 4);
        else if (!strcmp(key, "layout")) s.layout = std::clamp(atoi(val), 0, 2);
        else if (!strcmp(key, "scale")) s.scale = std::clamp(atoi(val), 1, 6);
        else if (!strcmp(key, "address")) snprintf(s.lastAddr, sizeof(s.lastAddr), "%s", val);
    }
    fclose(f);
}

static void save_settings(const Settings& s)
{
    FILE* f = ds_fopen(path_in_dir("b2online.ini").c_str(), "w");
    if (!f) return;
    fprintf(f, "clock=%d\nseason=%d\nlayout=%d\nscale=%d\naddress=%s\n", s.clockMode, s.seasonMode, s.layout, s.scale, s.lastAddr);
    fclose(f);
}

// ---------------------------------------------------------------------------------------------
// Game clock. Black 2 picks the season from the month (Jan/May/Sep spring, Feb/Jun/Oct summer,
// Mar/Jul/Nov autumn, Apr/Aug/Dec winter) and the hours of morning/day/evening/night shift with
// the season, so the preset times are picked per season.

static const char* kClockNames[] = {"PC time", "Morning", "Day", "Evening", "Night"};
static const char* kSeasonNames[] = {"From PC date", "Spring", "Summer", "Autumn", "Winter"};
static const char* kSeasonShort[] = {"Spring", "Summer", "Autumn", "Winter"};

static int season_of_month(int month0) { return month0 % 4; } // 0 spring .. 3 winter

static long clock_offset(const Settings& s)
{
    time_t now = time(nullptr);
    struct tm t = *localtime(&now);
    if (s.seasonMode) {
        int want = s.seasonMode - 1;
        // the nearest month (forwards) in the wanted season
        for (int i = 0; i < 4 && season_of_month(t.tm_mon) != want; i++) {
            t.tm_mon++;
            if (t.tm_mon == 12) { t.tm_mon = 0; t.tm_year++; }
        }
        t.tm_mday = std::min(t.tm_mday, 28);
    }
    int season = season_of_month(t.tm_mon);
    static const int evening[4][2] = {{18, 30}, {20, 0}, {19, 0}, {18, 0}};
    switch (s.clockMode) {
    case 1: t.tm_hour = 8; t.tm_min = 0; break;
    case 2: t.tm_hour = 13; t.tm_min = 0; break;
    case 3: t.tm_hour = evening[season][0]; t.tm_min = evening[season][1]; break;
    case 4: t.tm_hour = 23; t.tm_min = 0; break;
    }
    t.tm_isdst = -1;
    return (long)difftime(mktime(&t), now);
}

// ---------------------------------------------------------------------------------------------
// Drawing: the two DS screens as textures, text from an 8x16 font atlas

struct Ui {
    SDL_Renderer* r = nullptr;
    SDL_Texture* font = nullptr;
    SDL_Texture* screens = nullptr; // 256x384: top above bottom
};

static void ui_init(Ui& ui, SDL_Renderer* r)
{
    ui.r = r;
    ui.screens = SDL_CreateTexture(r, SDL_PIXELFORMAT_ARGB8888, SDL_TEXTUREACCESS_STREAMING, 256, 384);
    ui.font = SDL_CreateTexture(r, SDL_PIXELFORMAT_ARGB8888, SDL_TEXTUREACCESS_STATIC, 95 * 8, 16);
    static uint32_t px[16][95 * 8];
    for (int c = 0; c < 95; c++)
        for (int y = 0; y < 16; y++)
            for (int x = 0; x < 8; x++)
                px[y][c * 8 + x] = (kFont8x16[c][y] & (0x80 >> x)) ? 0xFFFFFFFF : 0x00FFFFFF;
    SDL_UpdateTexture(ui.font, nullptr, px, 95 * 8 * 4);
    SDL_SetTextureBlendMode(ui.font, SDL_BLENDMODE_BLEND);
}

static int text_width(const char* s, int scale) { return (int)strlen(s) * 8 * scale; }

static void draw_text(Ui& ui, int x, int y, int scale, SDL_Color c, const char* s)
{
    SDL_SetTextureColorMod(ui.font, c.r, c.g, c.b);
    SDL_SetTextureAlphaMod(ui.font, c.a);
    for (; *s; s++, x += 8 * scale) {
        int ch = (unsigned char)*s;
        if (ch < 32 || ch > 126) ch = '?';
        SDL_Rect src = {(ch - 32) * 8, 0, 8, 16};
        SDL_Rect dst = {x, y, 8 * scale, 16 * scale};
        SDL_RenderCopy(ui.r, ui.font, &src, &dst);
    }
}

static void draw_textf(Ui& ui, int x, int y, int scale, SDL_Color c, const char* fmt, ...)
{
    char buf[256];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    draw_text(ui, x, y, scale, c, buf);
}

static void fill(Ui& ui, int x, int y, int w, int h, SDL_Color c)
{
    SDL_SetRenderDrawBlendMode(ui.r, SDL_BLENDMODE_BLEND);
    SDL_SetRenderDrawColor(ui.r, c.r, c.g, c.b, c.a);
    SDL_Rect rc = {x, y, w, h};
    SDL_RenderFillRect(ui.r, &rc);
}

static const SDL_Color kWhite = {255, 255, 255, 255};
static const SDL_Color kGrey = {170, 178, 190, 255};
static const SDL_Color kGold = {255, 210, 90, 255};
static const SDL_Color kGreen = {120, 230, 140, 255};
static const SDL_Color kRed = {255, 120, 110, 255};
static const SDL_Color kPanel = {16, 20, 30, 225};

// Where the two screens go in the window, for the current layout
struct Layout { SDL_Rect top, bottom; };

static Layout compute_layout(int layout, int winW, int winH)
{
    Layout L;
    int lw, lh; // layout size in DS pixels
    if (layout == 1) { lw = 512; lh = 192; }
    else if (layout == 2) { lw = 256 + 128; lh = 192; }
    else { lw = 256; lh = 384; }
    double s = std::min((double)winW / lw, (double)winH / lh);
    int ox = (int)((winW - lw * s) / 2), oy = (int)((winH - lh * s) / 2);
    auto R = [&](double x, double y, double w, double h) {
        return SDL_Rect{ox + (int)lround(x * s), oy + (int)lround(y * s), (int)lround(w * s), (int)lround(h * s)};
    };
    if (layout == 1) { L.top = R(0, 0, 256, 192); L.bottom = R(256, 0, 256, 192); }
    else if (layout == 2) { L.top = R(0, 0, 256, 192); L.bottom = R(256, 96, 128, 96); }
    else { L.top = R(0, 0, 256, 192); L.bottom = R(0, 192, 256, 192); }
    return L;
}

// ---------------------------------------------------------------------------------------------
// Input

struct Input {
    uint32_t keys = 0;  // DS keys from keyboard
    uint32_t pad = 0;   // DS keys from controllers
    int touchX = -1, touchY = -1;
    bool mouseDown = false;
    bool fastForward = false;
    SDL_GameController* controllers[4] = {};
};

static uint32_t key_to_ds(SDL_Keycode k)
{
    switch (k) {
    case SDLK_UP: return DSK_UP;
    case SDLK_DOWN: return DSK_DOWN;
    case SDLK_LEFT: return DSK_LEFT;
    case SDLK_RIGHT: return DSK_RIGHT;
    case SDLK_x: return DSK_A;
    case SDLK_z: return DSK_B;
    case SDLK_s: return DSK_X;
    case SDLK_a: return DSK_Y;
    case SDLK_q: return DSK_L;
    case SDLK_w: return DSK_R;
    case SDLK_RETURN: return DSK_START;
    case SDLK_BACKSPACE: return DSK_SELECT;
    default: return 0;
    }
}

// Controller buttons go by position, like a DS: bottom face button is B, right is A.
static uint32_t pad_keys(SDL_GameController* c)
{
    static const struct { SDL_GameControllerButton b; uint32_t k; } map[] = {
        {SDL_CONTROLLER_BUTTON_A, DSK_B}, {SDL_CONTROLLER_BUTTON_B, DSK_A},
        {SDL_CONTROLLER_BUTTON_X, DSK_Y}, {SDL_CONTROLLER_BUTTON_Y, DSK_X},
        {SDL_CONTROLLER_BUTTON_LEFTSHOULDER, DSK_L}, {SDL_CONTROLLER_BUTTON_RIGHTSHOULDER, DSK_R},
        {SDL_CONTROLLER_BUTTON_BACK, DSK_SELECT}, {SDL_CONTROLLER_BUTTON_START, DSK_START},
        {SDL_CONTROLLER_BUTTON_DPAD_UP, DSK_UP}, {SDL_CONTROLLER_BUTTON_DPAD_DOWN, DSK_DOWN},
        {SDL_CONTROLLER_BUTTON_DPAD_LEFT, DSK_LEFT}, {SDL_CONTROLLER_BUTTON_DPAD_RIGHT, DSK_RIGHT},
    };
    uint32_t keys = 0;
    for (auto& m : map)
        if (SDL_GameControllerGetButton(c, m.b)) keys |= m.k;
    int ax = SDL_GameControllerGetAxis(c, SDL_CONTROLLER_AXIS_LEFTX);
    int ay = SDL_GameControllerGetAxis(c, SDL_CONTROLLER_AXIS_LEFTY);
    if (ax < -16000) keys |= DSK_LEFT;
    if (ax > 16000) keys |= DSK_RIGHT;
    if (ay < -16000) keys |= DSK_UP;
    if (ay > 16000) keys |= DSK_DOWN;
    if (SDL_GameControllerGetAxis(c, SDL_CONTROLLER_AXIS_TRIGGERLEFT) > 16000) keys |= DSK_L;
    if (SDL_GameControllerGetAxis(c, SDL_CONTROLLER_AXIS_TRIGGERRIGHT) > 16000) keys |= DSK_R;
    return keys;
}

// ---------------------------------------------------------------------------------------------
// The app

enum Overlay { OV_NONE, OV_HELP, OV_ONLINE, OV_ADDRESS };

struct App {
    SDL_Window* win = nullptr;
    Ui ui;
    DSInstance ds;
    DsBridge bridge;
    Net* net = nullptr;
    Settings set;
    Input in;
    SDL_AudioDeviceID audio = 0;
    Overlay overlay = OV_NONE;
    char toast[160] = "";
    uint32_t toastUntil = 0;
    char addrInput[96] = "";
    std::string gameCode;
    bool running = true;
};

static void toast(App& a, const char* fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    vsnprintf(a.toast, sizeof(a.toast), fmt, args);
    va_end(args);
    a.toastUntil = SDL_GetTicks() + 3500;
}

static void net_to_bridge(void* ctx, uint8_t type, const uint8_t* data, size_t len)
{
    ds_bridge_on_packet(&((App*)ctx)->bridge, type, data, len);
}

static void bridge_to_net(void* ctx, uint8_t type, const void* data, size_t len)
{
    net_send(((App*)ctx)->net, type, data, len);
}

static void update_title(App& a)
{
    char title[200];
    if (net_role(a.net) == NET_OFF)
        snprintf(title, sizeof(title), "Black 2 Online - solo");
    else if (net_connected(a.net))
        snprintf(title, sizeof(title), "Black 2 Online - %s with %s", net_role(a.net) == NET_HOST ? "hosting" : "joined",
                 a.bridge.peerName[0] ? a.bridge.peerName : net_peer_addr(a.net));
    else
        snprintf(title, sizeof(title), "Black 2 Online - %s", net_status(a.net));
    static char last[200];
    if (strcmp(last, title)) {
        SDL_SetWindowTitle(a.win, title);
        snprintf(last, sizeof(last), "%s", title);
    }
}

static void apply_clock(App& a, bool announce)
{
    ds_set_clock(&a.ds, clock_offset(a.set));
    save_settings(a.set);
    if (announce) {
        int h, m;
        ds_get_clock(&a.ds, &h, &m);
        toast(a, "Clock: %s (%02d:%02d)   Season: %s", kClockNames[a.set.clockMode], h, m, kSeasonNames[a.set.seasonMode]);
    }
}

// --- Start menu: Host / Join / Solo ---

static int start_menu(App& a)
{
    const char* items[] = {"Host", "Join", "Play solo"};
    const char* help[] = {"The other PC chooses Join.", "Finds the host on this Wi-Fi.", "Host or join later with F3."};
    int sel = 0;
    for (;;) {
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_QUIT) return -1;
            if (e.type == SDL_KEYDOWN) {
                SDL_Keycode k = e.key.keysym.sym;
                if (k == SDLK_UP) sel = (sel + 2) % 3;
                if (k == SDLK_DOWN) sel = (sel + 1) % 3;
                if (k == SDLK_RETURN || k == SDLK_x || k == SDLK_KP_ENTER) return sel;
                if (k == SDLK_h) return 0;
                if (k == SDLK_j) return 1;
                if (k == SDLK_ESCAPE) return 2;
            }
            if (e.type == SDL_CONTROLLERBUTTONDOWN) {
                if (e.cbutton.button == SDL_CONTROLLER_BUTTON_DPAD_UP) sel = (sel + 2) % 3;
                if (e.cbutton.button == SDL_CONTROLLER_BUTTON_DPAD_DOWN) sel = (sel + 1) % 3;
                if (e.cbutton.button == SDL_CONTROLLER_BUTTON_B || e.cbutton.button == SDL_CONTROLLER_BUTTON_START) return sel;
            }
            if (e.type == SDL_CONTROLLERDEVICEADDED) SDL_GameControllerOpen(e.cdevice.which);
            if (e.type == SDL_MOUSEBUTTONDOWN || e.type == SDL_MOUSEMOTION) {
                int w, h;
                SDL_GetRendererOutputSize(a.ui.r, &w, &h);
                int s = std::max(1, std::min(w / 360, h / 260));
                int bx = (w - 220 * s) / 2, by = h / 2 - 30 * s;
                int mx = e.type == SDL_MOUSEBUTTONDOWN ? e.button.x : e.motion.x;
                int my = e.type == SDL_MOUSEBUTTONDOWN ? e.button.y : e.motion.y;
                float sx = (float)w / std::max(1, [&] { int ww; SDL_GetWindowSize(a.win, &ww, nullptr); return ww; }());
                mx = (int)(mx * sx); my = (int)(my * sx);
                for (int i = 0; i < 3; i++)
                    if (mx >= bx && mx < bx + 220 * s && my >= by + i * 30 * s && my < by + i * 30 * s + 24 * s) {
                        sel = i;
                        if (e.type == SDL_MOUSEBUTTONDOWN) return i;
                    }
            }
        }
        int w, h;
        SDL_GetRendererOutputSize(a.ui.r, &w, &h);
        int s = std::max(1, std::min(w / 360, h / 260));
        SDL_SetRenderDrawColor(a.ui.r, 12, 14, 22, 255);
        SDL_RenderClear(a.ui.r);
        const char* title = "BLACK 2 ONLINE";
        draw_text(a.ui, (w - text_width(title, s * 2)) / 2, h / 2 - 100 * s, s * 2, kGold, title);
        int bx = (w - 220 * s) / 2, by = h / 2 - 30 * s;
        for (int i = 0; i < 3; i++) {
            fill(a.ui, bx, by + i * 30 * s, 220 * s, 24 * s, i == sel ? SDL_Color{60, 90, 160, 255} : SDL_Color{32, 38, 56, 255});
            draw_text(a.ui, bx + (220 * s - text_width(items[i], s)) / 2, by + i * 30 * s + 4 * s, s, kWhite, items[i]);
        }
        draw_text(a.ui, (w - text_width(help[sel], s)) / 2, by + 96 * s, s, kGrey, help[sel]);
        const char* hint = "Arrows + X (or click) to choose";
        draw_text(a.ui, (w - text_width(hint, s)) / 2, h - 24 * s, s, kGrey, hint);
        SDL_RenderPresent(a.ui.r);
        SDL_Delay(16);
    }
}

// --- Overlays ---

static void draw_help(App& a, int w, int h, int s)
{
    static const char* lines[] = {
        "CONTROLS",
        "Arrow keys ...... move",
        "X / Z ........... A / B",
        "S / A ........... X / Y",
        "Q / W ........... L / R",
        "Enter ........... START",
        "Backspace ....... SELECT",
        "Mouse ........... touch screen",
        "Hold Tab ........ fast forward",
        "F1 .............. this help",
        "F2 .............. join by address",
        "F3 .............. ONLINE screen",
        "F4 .............. time of day",
        "F6 .............. season",
        "F5 / F8 ......... quick-save / load",
        "F9 .............. screen layout",
        "F11 ............. fullscreen",
    };
    int n = (int)(sizeof(lines) / sizeof(lines[0]));
    int pw = 300 * s, ph = (n * 18 + 16) * s;
    int x = (w - pw) / 2, y = (h - ph) / 2;
    fill(a.ui, x, y, pw, ph, kPanel);
    for (int i = 0; i < n; i++)
        draw_text(a.ui, x + 12 * s, y + (8 + i * 18) * s, s, i == 0 ? kGold : kWhite, lines[i]);
}

static void draw_online(App& a, int w, int h, int s)
{
    int pw = std::min(w - 16, 440 * s), ph = std::min(h - 16, 300 * s);
    int x = (w - pw) / 2, y = (h - ph) / 2, lx = x + 12 * s, ly = y + 10 * s, step = 18 * s;
    fill(a.ui, x, y, pw, ph, kPanel);
    draw_text(a.ui, lx, ly, s, kGold, "ONLINE");
    ly += step + 4 * s;

    bool linked = net_connected(a.net);
    draw_text(a.ui, lx, ly, s, linked ? kGreen : kWhite, net_status(a.net));
    ly += step;
    if (net_role(a.net) == NET_HOST) {
        char addrs[200];
        net_local_addresses(addrs, sizeof(addrs));
        draw_textf(a.ui, lx, ly, s, kGrey, "This PC: %s", addrs[0] ? addrs : "no network");
        ly += step;
    }
    if (!ds_bridge_found(&a.bridge)) {
        ly += 4 * s;
        draw_text(a.ui, lx, ly, s, kRed, "Game side not found in this ROM.");
        ly += step;
        draw_text(a.ui, lx, ly, s, kGrey, "The link works, but this game file has no");
        ly += step;
        draw_text(a.ui, lx, ly, s, kGrey, "online patch yet, so you won't see each");
        ly += step;
        draw_text(a.ui, lx, ly, s, kGrey, "other in the game. (Or load your save first.)");
        ly += step;
    } else if (linked) {
        ly += 4 * s;
        const uint8_t* p = a.bridge.peerProfile;
        auto rd16 = [](const uint8_t* q) { return q[0] | q[1] << 8; };
        draw_textf(a.ui, lx, ly, s, kWhite, "%s%s", a.bridge.peerName[0] ? a.bridge.peerName : "The other player",
                   !a.bridge.peerOnMap ? "  (busy)" : a.bridge.sameMap ? "  - same map as you!" : "");
        ly += step;
        if (a.bridge.peerProfileValid) {
            int badges = 0;
            for (int i = 0; i < 8; i++) badges += (p[BPR_BADGES] >> i) & 1;
            draw_textf(a.ui, lx, ly, s, kGrey, "Badges %d   Pokedex %d seen, %d caught", badges, rd16(p + BPR_DEX_SEEN), rd16(p + BPR_DEX_CAUGHT));
            ly += step;
            draw_textf(a.ui, lx, ly, s, kGrey, "Play time %d:%02d   %s   Zone %d", rd16(p + BPR_HOURS), p[BPR_MINUTES],
                       kSeasonShort[p[BPR_SEASON] & 3], rd16(p + BPR_MAP));
            ly += step + 4 * s;
            for (int i = 0; i < 6; i++) {
                int sp = rd16(p + BPR_SPECIES + i * 2);
                if (!sp) continue;
                draw_textf(a.ui, lx + (i % 2) * (pw / 2), ly + (i / 2) * step, s, kWhite, "%-12s Lv.%d",
                           sp < 650 ? kSpeciesNames[sp] : "?", p[BPR_LEVEL + i]);
            }
            ly += 3 * step;
        } else {
            draw_text(a.ui, lx, ly, s, kGrey, "Waiting for their team info...");
            ly += step;
        }
    }
    int by = y + ph - 3 * step - 6 * s;
    draw_text(a.ui, lx, by, s, kGrey, "H host  J join  F2 join by address  O solo");
    int hh, mm;
    ds_get_clock(&a.ds, &hh, &mm);
    draw_textf(a.ui, lx, by + step, s, kGrey, "Clock %02d:%02d, %s (F4)", hh, mm, kClockNames[a.set.clockMode]);
    draw_textf(a.ui, lx, by + 2 * step, s, kGrey, "Season: %s (F6)    F3 closes", kSeasonNames[a.set.seasonMode]);
}

static void draw_address(App& a, int w, int h, int s)
{
    int pw = 360 * s, ph = 84 * s, x = (w - pw) / 2, y = (h - ph) / 2;
    fill(a.ui, x, y, pw, ph, kPanel);
    draw_text(a.ui, x + 12 * s, y + 10 * s, s, kGold, "Host's address (shown on its F3 screen):");
    fill(a.ui, x + 12 * s, y + 32 * s, pw - 24 * s, 22 * s, SDL_Color{40, 46, 66, 255});
    bool blink = (SDL_GetTicks() / 500) % 2;
    draw_textf(a.ui, x + 16 * s, y + 35 * s, s, kWhite, "%s%s", a.addrInput, blink ? "_" : "");
    draw_text(a.ui, x + 12 * s, y + 60 * s, s, kGrey, "Enter to connect, Esc to cancel");
}

static void render(App& a)
{
    const uint32_t *top, *bottom;
    if (ds_screens(&a.ds, &top, &bottom)) {
        uint8_t* px;
        int pitch;
        if (SDL_LockTexture(a.ui.screens, nullptr, (void**)&px, &pitch) == 0) {
            for (int y = 0; y < 192; y++) {
                uint32_t* d0 = (uint32_t*)(px + y * pitch);
                uint32_t* d1 = (uint32_t*)(px + (y + 192) * pitch);
                for (int x = 0; x < 256; x++) {
                    d0[x] = top[y * 256 + x] | 0xFF000000;
                    d1[x] = bottom[y * 256 + x] | 0xFF000000;
                }
            }
            SDL_UnlockTexture(a.ui.screens);
        }
    }
    int w, h;
    SDL_GetRendererOutputSize(a.ui.r, &w, &h);
    SDL_SetRenderDrawColor(a.ui.r, 0, 0, 0, 255);
    SDL_RenderClear(a.ui.r);
    Layout L = compute_layout(a.set.layout, w, h);
    SDL_Rect srcTop = {0, 0, 256, 192}, srcBottom = {0, 192, 256, 192};
    SDL_RenderCopy(a.ui.r, a.ui.screens, &srcTop, &L.top);
    SDL_RenderCopy(a.ui.r, a.ui.screens, &srcBottom, &L.bottom);

    int s = std::max(1, std::min(w / 480, h / 400));
    if (a.overlay == OV_HELP) draw_help(a, w, h, s);
    else if (a.overlay == OV_ONLINE) draw_online(a, w, h, s);
    else if (a.overlay == OV_ADDRESS) draw_address(a, w, h, s);

    if (SDL_GetTicks() < a.toastUntil) {
        int tw = text_width(a.toast, s) + 16 * s;
        fill(a.ui, 8, 8, tw, 24 * s, kPanel);
        draw_text(a.ui, 8 + 8 * s, 8 + 4 * s, s, kWhite, a.toast);
    }
    if (a.in.fastForward) {
        const char* ff = ">> fast";
        fill(a.ui, w - text_width(ff, s) - 24 * s, 8, text_width(ff, s) + 16 * s, 24 * s, kPanel);
        draw_text(a.ui, w - text_width(ff, s) - 16 * s, 8 + 4 * s, s, kGold, ff);
    }
    SDL_RenderPresent(a.ui.r);
}

// Window pixel -> DS bottom-screen pixel, or -1
static void window_to_touch(App& a, int mx, int my, int* tx, int* ty)
{
    int w, h, ww, wh;
    SDL_GetRendererOutputSize(a.ui.r, &w, &h);
    SDL_GetWindowSize(a.win, &ww, &wh);
    mx = mx * w / std::max(1, ww);
    my = my * h / std::max(1, wh);
    Layout L = compute_layout(a.set.layout, w, h);
    const SDL_Rect& b = L.bottom;
    if (mx < b.x || my < b.y || mx >= b.x + b.w || my >= b.y + b.h) { *tx = *ty = -1; return; }
    *tx = std::clamp((mx - b.x) * 256 / b.w, 0, 255);
    *ty = std::clamp((my - b.y) * 192 / b.h, 0, 191);
}

static bool confirm_quit(App& a)
{
    const SDL_MessageBoxButtonData buttons[] = {
        {SDL_MESSAGEBOX_BUTTON_ESCAPEKEY_DEFAULT, 0, "Keep playing"},
        {SDL_MESSAGEBOX_BUTTON_RETURNKEY_DEFAULT, 1, "Quit"},
    };
    SDL_MessageBoxData box = {SDL_MESSAGEBOX_WARNING, a.win, "Quit Black 2 Online?",
                              "Anything since your last in-game save (menu > SAVE) will be lost.", 2, buttons, nullptr};
    int pressed = 0;
    if (SDL_ShowMessageBox(&box, &pressed) != 0) return true;
    return pressed == 1;
}

static void handle_key(App& a, const SDL_KeyboardEvent& k, bool down)
{
    SDL_Keycode sym = k.keysym.sym;
    if (a.overlay == OV_ADDRESS) {
        if (!down) return;
        if (sym == SDLK_ESCAPE) { a.overlay = OV_NONE; SDL_StopTextInput(); }
        else if (sym == SDLK_BACKSPACE && a.addrInput[0]) a.addrInput[strlen(a.addrInput) - 1] = 0;
        else if (sym == SDLK_RETURN || sym == SDLK_KP_ENTER) {
            SDL_StopTextInput();
            a.overlay = OV_ONLINE;
            snprintf(a.set.lastAddr, sizeof(a.set.lastAddr), "%s", a.addrInput);
            save_settings(a.set);
            net_join(a.net, a.addrInput);
        }
        return;
    }
    if (down && !k.repeat) {
        switch (sym) {
        case SDLK_F1: a.overlay = a.overlay == OV_HELP ? OV_NONE : OV_HELP; return;
        case SDLK_F2:
            snprintf(a.addrInput, sizeof(a.addrInput), "%s", a.set.lastAddr);
            a.overlay = OV_ADDRESS;
            SDL_StartTextInput();
            return;
        case SDLK_F3: a.overlay = a.overlay == OV_ONLINE ? OV_NONE : OV_ONLINE; return;
        case SDLK_F4: a.set.clockMode = (a.set.clockMode + 1) % 5; apply_clock(a, true); return;
        case SDLK_F6: a.set.seasonMode = (a.set.seasonMode + 1) % 5; apply_clock(a, true); return;
        case SDLK_F5:
            toast(a, ds_savestate(&a.ds, path_in_dir("Pokemon_Black2_Online.state").c_str()) ? "Quick-saved (F8 loads it)" : "Couldn't quick-save");
            return;
        case SDLK_F8:
            if (ds_loadstate(&a.ds, path_in_dir("Pokemon_Black2_Online.state").c_str())) {
                apply_clock(a, false);
                toast(a, "Quick-loaded");
            } else {
                toast(a, "No quick-save yet (F5 makes one)");
            }
            return;
        case SDLK_F9:
            a.set.layout = (a.set.layout + 1) % 3;
            save_settings(a.set);
            return;
        case SDLK_F11:
            SDL_SetWindowFullscreen(a.win, (SDL_GetWindowFlags(a.win) & SDL_WINDOW_FULLSCREEN_DESKTOP) ? 0 : SDL_WINDOW_FULLSCREEN_DESKTOP);
            return;
        case SDLK_ESCAPE:
            if (a.overlay != OV_NONE) { a.overlay = OV_NONE; return; }
            break;
        default: break;
        }
        if (sym == SDLK_RETURN && (k.keysym.mod & KMOD_ALT)) {
            SDL_SetWindowFullscreen(a.win, (SDL_GetWindowFlags(a.win) & SDL_WINDOW_FULLSCREEN_DESKTOP) ? 0 : SDL_WINDOW_FULLSCREEN_DESKTOP);
            return;
        }
        if (a.overlay == OV_ONLINE) {
            if (sym == SDLK_h) { net_host(a.net); return; }
            if (sym == SDLK_j) { net_join(a.net, nullptr); return; }
            if (sym == SDLK_o) { net_stop(a.net); return; }
        }
    }
    if (sym == SDLK_TAB) a.in.fastForward = down;
    uint32_t bit = key_to_ds(sym);
    if (bit) {
        if (down) a.in.keys |= bit;
        else a.in.keys &= ~bit;
    }
}

static void poll_events(App& a)
{
    SDL_Event e;
    while (SDL_PollEvent(&e)) {
        switch (e.type) {
        case SDL_QUIT:
            if (confirm_quit(a)) a.running = false;
            break;
        case SDL_KEYDOWN: handle_key(a, e.key, true); break;
        case SDL_KEYUP: handle_key(a, e.key, false); break;
        case SDL_TEXTINPUT:
            if (a.overlay == OV_ADDRESS)
                for (const char* c = e.text.text; *c; c++)
                    if ((isalnum((unsigned char)*c) || *c == '.' || *c == ':' || *c == '-') && strlen(a.addrInput) < 60) {
                        size_t n = strlen(a.addrInput);
                        a.addrInput[n] = *c;
                        a.addrInput[n + 1] = 0;
                    }
            break;
        case SDL_MOUSEBUTTONDOWN:
            if (e.button.button == SDL_BUTTON_LEFT) {
                a.in.mouseDown = true;
                window_to_touch(a, e.button.x, e.button.y, &a.in.touchX, &a.in.touchY);
            }
            break;
        case SDL_MOUSEMOTION:
            if (a.in.mouseDown) {
                int tx, ty;
                window_to_touch(a, e.motion.x, e.motion.y, &tx, &ty);
                if (tx >= 0) { a.in.touchX = tx; a.in.touchY = ty; }
            }
            break;
        case SDL_MOUSEBUTTONUP:
            if (e.button.button == SDL_BUTTON_LEFT) {
                a.in.mouseDown = false;
                a.in.touchX = a.in.touchY = -1;
            }
            break;
        case SDL_CONTROLLERDEVICEADDED:
            for (auto& c : a.in.controllers)
                if (!c) { c = SDL_GameControllerOpen(e.cdevice.which); break; }
            break;
        case SDL_CONTROLLERDEVICEREMOVED:
            for (auto& c : a.in.controllers)
                if (c && SDL_JoystickInstanceID(SDL_GameControllerGetJoystick(c)) == e.cdevice.which) {
                    SDL_GameControllerClose(c);
                    c = nullptr;
                }
            break;
        }
    }
    a.in.pad = 0;
    for (auto c : a.in.controllers)
        if (c) a.in.pad |= pad_keys(c);
}

static void fail(const char* msg)
{
    fprintf(stderr, "%s\n", msg);
    SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "Black 2 Online", msg, nullptr);
}

static bool is_b2w2(const std::string& code) { return code.size() == 4 && (code.compare(0, 3, "IRE") == 0 || code.compare(0, 3, "IRD") == 0); }

// --test-frames N [--host | --join ADDR] [--screenshot out.bmp]: run without a window for N frames
// (at 60 per second when linking), then print what the bridge saw. Used by tests/e2e_test.sh.
static int run_test(const char* rom, const char* sav, int frames, const char* shot, int role, const char* addr)
{
    static App a;
    std::string err;
    if (!ds_load(&a.ds, rom, sav, true, &err)) { fprintf(stderr, "%s\n", err.c_str()); return 1; }
    uint32_t ramSize;
    uint8_t* ram = ds_mainram(&a.ds, &ramSize);
    ds_bridge_init(&a.bridge, ram, ramSize);
    a.net = net_create(ds_rom_gamecode(rom).c_str());
    if (role == NET_HOST) net_host(a.net);
    else if (role == NET_JOIN) net_join(a.net, addr);
    ds_bridge_set_host(&a.bridge, role == NET_HOST);
    int linkedFrames = 0, sawPeerFrames = 0;
    static uint32_t lastShot[256 * 384];
    for (int i = 0; i < frames; i++) {
        ds_frame(&a.ds, 0, -1, -1);
        net_poll(a.net, net_to_bridge, &a);
        ds_bridge_set_connected(&a.bridge, net_connected(a.net));
        ds_bridge_after_frame(&a.bridge, bridge_to_net, &a);
        ds_save_tick(&a.ds);
        linkedFrames += net_connected(a.net);
        // keep the screen from the last frame where both players were on the map, or the last frame when solo
        const uint32_t *top, *bottom;
        if ((a.bridge.sameMap || role == NET_OFF) && ds_screens(&a.ds, &top, &bottom)) {
            memcpy(lastShot, top, 256 * 192 * 4);
            memcpy(lastShot + 256 * 192, bottom, 256 * 192 * 4);
        }
        sawPeerFrames += a.bridge.sameMap;
        if (role != NET_OFF) SDL_Delay(16);
    }
    char desc[300];
    ds_bridge_describe(&a.bridge, desc, sizeof(desc));
    int selfSeq = ds_bridge_found(&a.bridge) ? ram[a.bridge.mb + BMB_SELFSEQ] : -1;
    printf("game %s, %d frames, linked %d, saw the other player %d, net \"%s\", game counter %d\n%s\n",
           ds_rom_gamecode(rom).c_str(), frames, linkedFrames, sawPeerFrames, net_status(a.net), selfSeq, desc);
    if (shot) {
        SDL_Surface* sfc = SDL_CreateRGBSurfaceWithFormat(0, 256, 384, 32, SDL_PIXELFORMAT_ARGB8888);
        for (int y = 0; y < 384; y++)
            for (int x = 0; x < 256; x++)
                ((uint32_t*)((uint8_t*)sfc->pixels + y * sfc->pitch))[x] = lastShot[y * 256 + x] | 0xFF000000;
        SDL_SaveBMP(sfc, shot);
        SDL_FreeSurface(sfc);
    }
    net_destroy(a.net);
    ds_free(&a.ds);
    return 0;
}

int main(int argc, char** argv)
{
    char* base = SDL_GetBasePath();
    g_dir = base ? base : "";
    SDL_free(base);

    std::string rom = path_in_dir(kRomName);
    int testFrames = 0, testRole = NET_OFF;
    const char *shot = nullptr, *testAddr = nullptr;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--test-frames") && i + 1 < argc) testFrames = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--screenshot") && i + 1 < argc) shot = argv[++i];
        else if (!strcmp(argv[i], "--host")) testRole = NET_HOST;
        else if (!strcmp(argv[i], "--join") && i + 1 < argc) { testRole = NET_JOIN; testAddr = argv[++i]; }
        else if (argv[i][0] != '-') rom = argv[i];
    }
    std::string sav = rom.substr(0, rom.find_last_of('.')) + ".sav";
    if (testFrames > 0) return run_test(rom.c_str(), sav.c_str(), testFrames, shot, testRole, testAddr);

    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_GAMECONTROLLER) != 0) {
        fprintf(stderr, "SDL: %s\n", SDL_GetError());
        return 1;
    }
    static App a;
    a.gameCode = ds_rom_gamecode(rom.c_str());
    if (a.gameCode.empty()) {
        fail(("Put Pokemon_Black2_Online.nds in the same folder as the app, then start it again.\n(Looked for " + rom + ")").c_str());
        return 1;
    }
    load_settings(a.set);

    a.win = SDL_CreateWindow("Black 2 Online", SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
                             256 * a.set.scale + (a.set.layout == 1 ? 256 * a.set.scale : 0),
                             (a.set.layout == 1 ? 192 : 384) * a.set.scale, SDL_WINDOW_RESIZABLE | SDL_WINDOW_ALLOW_HIGHDPI);
    SDL_Renderer* r = SDL_CreateRenderer(a.win, -1, SDL_RENDERER_ACCELERATED);
    if (!r) r = SDL_CreateRenderer(a.win, -1, SDL_RENDERER_SOFTWARE);
    SDL_SetHint(SDL_HINT_RENDER_SCALE_QUALITY, "0");
    ui_init(a.ui, r);

    if (!is_b2w2(a.gameCode))
        toast(a, "This doesn't look like Black 2 / White 2 (game code %s).", a.gameCode.c_str());

    a.net = net_create(a.gameCode.c_str());
    int choice = start_menu(a);
    if (choice < 0) return 0;
    if (choice == 0) net_host(a.net);
    else if (choice == 1) net_join(a.net, nullptr);

    std::string err;
    if (!ds_load(&a.ds, rom.c_str(), sav.c_str(), true, &err)) {
        fail(err.c_str());
        return 1;
    }
    uint32_t ramSize;
    uint8_t* ram = ds_mainram(&a.ds, &ramSize);
    ds_bridge_init(&a.bridge, ram, ramSize);
    ds_bridge_set_host(&a.bridge, net_role(a.net) == NET_HOST);
    apply_clock(a, false);

    SDL_AudioSpec want = {}, have;
    want.freq = 48000;
    want.format = AUDIO_S16SYS;
    want.channels = 2;
    want.samples = 1024;
    a.audio = SDL_OpenAudioDevice(nullptr, 0, &want, &have, 0);
    if (a.audio) SDL_PauseAudioDevice(a.audio, 0);

    if (choice == 0) {
        a.overlay = OV_ONLINE;
        toast(a, "Hosting. The other PC chooses Join.");
    }

    const double frameTime = 1.0 / kFrameRate;
    const double freq = (double)SDL_GetPerformanceFrequency();
    double next = SDL_GetPerformanceCounter() / freq;
    int16_t samples[4096 * 2];
    int lastRole = -1;
    while (a.running) {
        poll_events(a);

        uint32_t keys = (a.overlay == OV_ADDRESS) ? 0 : (a.in.keys | a.in.pad);
        int frames = a.in.fastForward ? 4 : 1;
        for (int i = 0; i < frames; i++) {
            ds_frame(&a.ds, keys, a.in.touchX, a.in.touchY);
            net_poll(a.net, net_to_bridge, &a);
            if ((int)net_role(a.net) != lastRole) {
                lastRole = net_role(a.net);
                ds_bridge_set_host(&a.bridge, lastRole == NET_HOST);
            }
            ds_bridge_set_connected(&a.bridge, net_connected(a.net));
            ds_bridge_after_frame(&a.bridge, bridge_to_net, &a);
            ds_save_tick(&a.ds);

            int got = ds_audio(&a.ds, samples, 4096);
            if (a.audio && got > 0 && SDL_GetQueuedAudioSize(a.audio) < 48000 * 4 / 8)
                SDL_QueueAudio(a.audio, samples, got * 4);
        }
        update_title(a);
        render(a);

        next += frameTime;
        double now = SDL_GetPerformanceCounter() / freq;
        if (a.in.fastForward || next < now - 0.1) next = now;
        else if (next > now) SDL_Delay((uint32_t)((next - now) * 1000));
    }

    ds_save_flush(&a.ds);
    save_settings(a.set);
    net_destroy(a.net);
    ds_free(&a.ds);
    SDL_Quit();
    return 0;
}
