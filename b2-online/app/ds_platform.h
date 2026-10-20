// The app's view of the emulator: one DS, plus the platform hooks melonDS calls back into.
#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string>
#include <vector>

namespace melonDS { class NDS; }

struct DSInstance {
    melonDS::NDS* nds = nullptr;
    std::string romPath;
    std::string savPath;
    std::vector<uint8_t> saveBuf;  // latest save contents the game wrote
    bool saveDirty = false;        // saveBuf has changes not yet written to savPath
    int saveQuietFrames = 0;       // frames since the game last wrote its save
};

bool ds_load(DSInstance* inst, const char* romPath, const char* savPath, bool jit, std::string* err);
void ds_frame(DSInstance* inst, uint32_t keys, int touchX, int touchY);
bool ds_screens(DSInstance* inst, const uint32_t** top, const uint32_t** bottom);
uint8_t* ds_mainram(DSInstance* inst, uint32_t* size);
bool ds_read(DSInstance* inst, uint32_t addr, void* out, uint32_t len);
bool ds_write(DSInstance* inst, uint32_t addr, const void* in, uint32_t len);
bool ds_savestate(DSInstance* inst, const char* path);
bool ds_loadstate(DSInstance* inst, const char* path);
int ds_audio(DSInstance* inst, int16_t* out, int maxFrames);
int ds_audio_pending(DSInstance* inst);
void ds_set_clock(DSInstance* inst, long offsetSeconds);
void ds_get_clock(DSInstance* inst, int* hour, int* minute);
void ds_free(DSInstance* inst);

// The game writes its save in many small pieces. Call ds_save_tick once per frame: it writes the
// .sav file once the game has stopped writing for a moment. ds_save_flush writes it right away.
void ds_save_tick(DSInstance* inst);
bool ds_save_flush(DSInstance* inst);

// fopen that takes a UTF-8 path on every platform (Windows fopen doesn't).
FILE* ds_fopen(const char* path, const char* mode);

// The 4-letter game code in the ROM header ("IREO" is Black 2 USA), or "" if unreadable.
std::string ds_rom_gamecode(const char* romPath);

// DS key bits, as the app passes them to ds_frame
enum {
    DSK_A = 1 << 0, DSK_B = 1 << 1, DSK_SELECT = 1 << 2, DSK_START = 1 << 3,
    DSK_RIGHT = 1 << 4, DSK_LEFT = 1 << 5, DSK_UP = 1 << 6, DSK_DOWN = 1 << 7,
    DSK_R = 1 << 8, DSK_L = 1 << 9, DSK_X = 1 << 10, DSK_Y = 1 << 11,
};
