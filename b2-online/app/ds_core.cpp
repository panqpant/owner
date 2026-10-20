// Thin wrapper around the melonDS core.
#include "ds_platform.h"

#include "NDS.h"
#include "NDSCart.h"
#include "GPU.h"
#include "Savestate.h"
#include "SPI_Firmware.h"

#include <cstdio>
#include <cstring>
#include <ctime>
#include <memory>
#include <vector>

using namespace melonDS;

static bool read_file(const char* path, std::vector<uint8_t>& out)
{
    FILE* f = ds_fopen(path, "rb");
    if (!f) return false;
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    out.resize(n > 0 ? n : 0);
    bool ok = n <= 0 || fread(out.data(), 1, n, f) == (size_t)n;
    fclose(f);
    return ok;
}

static void set_host_time(NDS* nds)
{
    time_t t = time(nullptr);
    struct tm lt;
#ifdef _WIN32
    localtime_s(&lt, &t);
#else
    localtime_r(&t, &lt);
#endif
    nds->RTC.SetDateTime(lt.tm_year + 1900, lt.tm_mon + 1, lt.tm_mday, lt.tm_hour, lt.tm_min, lt.tm_sec);
}

// Game clock: the PC's clock moved by offsetSeconds (to pick the time of day).
void ds_set_clock(DSInstance* inst, long offsetSeconds)
{
    if (!inst || !inst->nds)
        return;
    time_t t = time(nullptr) + offsetSeconds;
    struct tm lt;
#ifdef _WIN32
    localtime_s(&lt, &t);
#else
    localtime_r(&t, &lt);
#endif
    inst->nds->RTC.SetDateTime(lt.tm_year + 1900, lt.tm_mon + 1, lt.tm_mday, lt.tm_hour, lt.tm_min, lt.tm_sec);
}

void ds_get_clock(DSInstance* inst, int* hour, int* minute)
{
    int y = 0, mo = 0, d = 0, h = 0, mi = 0, s = 0;
    if (inst && inst->nds)
        inst->nds->RTC.GetDateTime(y, mo, d, h, mi, s);
    *hour = h;
    *minute = mi;
}

bool ds_load(DSInstance* inst, const char* romPath, const char* savPath, bool jit, std::string* err)
{
    std::vector<uint8_t> rom;
    if (!read_file(romPath, rom) || rom.size() < 0x200)
    {
        if (err) *err = "Couldn't read the game file.";
        return false;
    }
    inst->romPath = romPath;
    inst->savPath = savPath ? savPath : "";

    NDSArgs args;
    args.Firmware = Firmware(0);  // generated DS firmware
    if (!jit) args.JIT = std::nullopt;
    inst->nds = new NDS(std::move(args), inst);

    std::unique_ptr<u8[]> sram;
    u32 sramLen = 0;
    if (savPath && *savPath)
    {
        std::vector<uint8_t> sav;
        if (read_file(savPath, sav) && !sav.empty())
        {
            sramLen = (u32)sav.size();
            sram = std::make_unique<u8[]>(sramLen);
            memcpy(sram.get(), sav.data(), sramLen);
        }
    }
    NDSCart::NDSCartArgs cartargs { .SDCard = std::nullopt, .SRAM = std::move(sram), .SRAMLength = sramLen };

    auto romdata = std::make_unique<u8[]>(rom.size());
    memcpy(romdata.get(), rom.data(), rom.size());
    auto cart = NDSCart::ParseROM(std::move(romdata), (u32)rom.size(), inst, std::move(cartargs));
    if (!cart)
    {
        if (err) *err = "That file isn't a DS game.";
        delete inst->nds;
        inst->nds = nullptr;
        return false;
    }
    inst->nds->SetNDSCart(std::move(cart));
    inst->nds->Reset();
    inst->nds->SetupDirectBoot("game.nds");
    set_host_time(inst->nds);
    inst->nds->Start();
    return true;
}

void ds_frame(DSInstance* inst, uint32_t keys, int touchX, int touchY)
{
    NDS* nds = inst->nds;
    nds->SetKeyMask(~keys & 0xFFF);
    if (touchX >= 0 && touchY >= 0)
        nds->TouchScreen((u16)touchX, (u16)touchY);
    else
        nds->ReleaseScreen();
    nds->RunFrame();
}

bool ds_screens(DSInstance* inst, const uint32_t** top, const uint32_t** bottom)
{
    void* t = nullptr;
    void* b = nullptr;
    if (!inst->nds->GPU.GetFramebuffers(&t, &b)) return false;
    *top = (const uint32_t*)t;
    *bottom = (const uint32_t*)b;
    return true;
}

uint8_t* ds_mainram(DSInstance* inst, uint32_t* size)
{
    if (size) *size = inst->nds->MainRAMMask + 1;
    return inst->nds->MainRAM;
}

bool ds_read(DSInstance* inst, uint32_t addr, void* out, uint32_t len)
{
    if ((addr & 0xFF000000) != 0x02000000) return false;
    uint32_t size;
    uint8_t* ram = ds_mainram(inst, &size);
    for (uint32_t i = 0; i < len; i++)
        ((uint8_t*)out)[i] = ram[(addr + i) & (size - 1)];
    return true;
}

bool ds_write(DSInstance* inst, uint32_t addr, const void* in, uint32_t len)
{
    if ((addr & 0xFF000000) != 0x02000000) return false;
    uint32_t size;
    uint8_t* ram = ds_mainram(inst, &size);
    for (uint32_t i = 0; i < len; i++)
        ram[(addr + i) & (size - 1)] = ((const uint8_t*)in)[i];
    return true;
}

bool ds_savestate(DSInstance* inst, const char* path)
{
    Savestate st;
    if (st.Error) return false;
    inst->nds->DoSavestate(&st);
    if (st.Error) return false;
    st.Finish();
    FILE* f = ds_fopen(path, "wb");
    if (!f) return false;
    bool ok = fwrite(st.Buffer(), 1, st.Length(), f) == st.Length();
    fclose(f);
    return ok;
}

bool ds_loadstate(DSInstance* inst, const char* path)
{
    std::vector<uint8_t> buf;
    if (!read_file(path, buf) || buf.empty()) return false;
    Savestate st(buf.data(), (u32)buf.size(), false);
    if (st.Error) return false;
    if (!inst->nds->DoSavestate(&st) || st.Error) return false;
    return true;
}

int ds_audio(DSInstance* inst, int16_t* out, int maxFrames)
{
    return inst->nds->SPU.ReadOutput(out, maxFrames);
}

int ds_audio_pending(DSInstance* inst)
{
    return inst->nds->SPU.GetOutputSize();
}

void ds_free(DSInstance* inst)
{
    if (inst->nds)
    {
        inst->nds->Stop();
        delete inst->nds;
        inst->nds = nullptr;
    }
}
