// The platform hooks melonDS calls back into: files, threads, logging, saves.
// Everything a DS game could ask for that this app doesn't offer (local wireless, camera,
// microphone, add-ons) answers "nothing there".
#include "ds_platform.h"

#include "Platform.h"
#include "SPI_Firmware.h"

#include <chrono>
#include <condition_variable>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <thread>

#ifdef _WIN32
#include <windows.h>
#endif

using namespace melonDS;

FILE* ds_fopen(const char* path, const char* mode)
{
#ifdef _WIN32
    wchar_t wpath[1024], wmode[16];
    if (!MultiByteToWideChar(CP_UTF8, 0, path, -1, wpath, 1024)) return nullptr;
    if (!MultiByteToWideChar(CP_UTF8, 0, mode, -1, wmode, 16)) return nullptr;
    return _wfopen(wpath, wmode);
#else
    return fopen(path, mode);
#endif
}

static FILE* open_utf8(const std::string& path, const char* mode) { return ds_fopen(path.c_str(), mode); }

std::string ds_rom_gamecode(const char* romPath)
{
    FILE* f = open_utf8(romPath, "rb");
    if (!f) return "";
    char code[5] = {0};
    bool ok = fseek(f, 0x0C, SEEK_SET) == 0 && fread(code, 1, 4, f) == 4;
    fclose(f);
    return ok ? std::string(code) : "";
}

static bool write_file_atomic(const std::string& path, const uint8_t* data, size_t len)
{
    std::string tmp = path + ".tmp";
    FILE* f = open_utf8(tmp, "wb");
    if (!f) return false;
    bool ok = fwrite(data, 1, len, f) == len;
    ok = fclose(f) == 0 && ok;
    if (!ok) { remove(tmp.c_str()); return false; }
#ifdef _WIN32
    wchar_t wtmp[1024], wpath[1024];
    MultiByteToWideChar(CP_UTF8, 0, tmp.c_str(), -1, wtmp, 1024);
    MultiByteToWideChar(CP_UTF8, 0, path.c_str(), -1, wpath, 1024);
    return MoveFileExW(wtmp, wpath, MOVEFILE_REPLACE_EXISTING) != 0;
#else
    return rename(tmp.c_str(), path.c_str()) == 0;
#endif
}

bool ds_save_flush(DSInstance* inst)
{
    if (!inst->saveDirty || inst->savPath.empty() || inst->saveBuf.empty())
        return true;
    if (!write_file_atomic(inst->savPath, inst->saveBuf.data(), inst->saveBuf.size()))
        return false;
    inst->saveDirty = false;
    return true;
}

void ds_save_tick(DSInstance* inst)
{
    if (inst->saveDirty && ++inst->saveQuietFrames >= 30)
        ds_save_flush(inst);
}

namespace melonDS::Platform
{

void SignalStop(StopReason, void*) {}

static const char* mode_string(FileMode mode, bool exists)
{
    bool read = mode & FileMode::Read, write = mode & FileMode::Write;
    if (mode & FileMode::Append) return read ? "a+b" : "ab";
    if (!write) return "rb";
    bool keep = (mode & FileMode::NoCreate) || ((mode & FileMode::Preserve) && exists);
    if (keep) return "r+b";
    return read ? "w+b" : "wb";
}

FileHandle* OpenFile(const std::string& path, FileMode mode)
{
    if ((mode & (FileMode::ReadWrite | FileMode::Append)) == FileMode::None)
        return nullptr;
    bool exists = FileExists(path);
    if ((mode & FileMode::NoCreate) && !exists)
        return nullptr;
    return reinterpret_cast<FileHandle*>(open_utf8(path, mode_string(mode, exists)));
}

std::string GetLocalFilePath(const std::string& filename) { return filename; }
FileHandle* OpenLocalFile(const std::string& path, FileMode mode) { return OpenFile(path, mode); }

bool FileExists(const std::string& name)
{
    FILE* f = open_utf8(name, "rb");
    if (!f) return false;
    fclose(f);
    return true;
}

bool LocalFileExists(const std::string& name) { return FileExists(name); }

bool CheckFileWritable(const std::string& filepath)
{
    FILE* f = open_utf8(filepath, FileExists(filepath) ? "r+b" : "ab");
    if (!f) return false;
    fclose(f);
    return true;
}

bool CheckLocalFileWritable(const std::string& filepath) { return CheckFileWritable(filepath); }

static FILE* F(FileHandle* file) { return reinterpret_cast<FILE*>(file); }

bool CloseFile(FileHandle* file) { return fclose(F(file)) == 0; }
bool IsEndOfFile(FileHandle* file) { return feof(F(file)) != 0; }
bool FileReadLine(char* str, int count, FileHandle* file) { return fgets(str, count, F(file)) != nullptr; }

bool FileSeek(FileHandle* file, s64 offset, FileSeekOrigin origin)
{
    int whence = origin == FileSeekOrigin::Start ? SEEK_SET : origin == FileSeekOrigin::Current ? SEEK_CUR : SEEK_END;
#ifdef _WIN32
    return _fseeki64(F(file), offset, whence) == 0;
#else
    return fseeko(F(file), offset, whence) == 0;
#endif
}

void FileRewind(FileHandle* file) { rewind(F(file)); }
u64 FileRead(void* data, u64 size, u64 count, FileHandle* file) { return fread(data, size, count, F(file)); }
bool FileFlush(FileHandle* file) { return fflush(F(file)) == 0; }
u64 FileWrite(const void* data, u64 size, u64 count, FileHandle* file) { return fwrite(data, size, count, F(file)); }

u64 FileWriteFormatted(FileHandle* file, const char* fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    int n = vfprintf(F(file), fmt, args);
    va_end(args);
    return n < 0 ? 0 : (u64)n;
}

u64 FileLength(FileHandle* file)
{
    FILE* f = F(file);
#ifdef _WIN32
    s64 pos = _ftelli64(f);
    _fseeki64(f, 0, SEEK_END);
    s64 len = _ftelli64(f);
    _fseeki64(f, pos, SEEK_SET);
#else
    off_t pos = ftello(f);
    fseeko(f, 0, SEEK_END);
    off_t len = ftello(f);
    fseeko(f, pos, SEEK_SET);
#endif
    return len < 0 ? 0 : (u64)len;
}

void Log(LogLevel level, const char* fmt, ...)
{
#ifdef NDEBUG
    if (level == LogLevel::Debug) return;
#endif
    va_list args;
    va_start(args, fmt);
    vfprintf(stderr, fmt, args);
    va_end(args);
}

struct Thread { std::thread t; };
struct Semaphore { std::mutex m; std::condition_variable cv; int count = 0; };
struct Mutex { std::mutex m; };

Thread* Thread_Create(std::function<void()> func) { return new Thread{std::thread(std::move(func))}; }
void Thread_Free(Thread* thread)
{
    if (thread->t.joinable()) thread->t.detach();
    delete thread;
}
void Thread_Wait(Thread* thread) { if (thread->t.joinable()) thread->t.join(); }

Semaphore* Semaphore_Create() { return new Semaphore; }
void Semaphore_Free(Semaphore* sema) { delete sema; }
void Semaphore_Reset(Semaphore* sema)
{
    std::lock_guard<std::mutex> lock(sema->m);
    sema->count = 0;
}
void Semaphore_Wait(Semaphore* sema)
{
    std::unique_lock<std::mutex> lock(sema->m);
    sema->cv.wait(lock, [sema] { return sema->count > 0; });
    sema->count--;
}
bool Semaphore_TryWait(Semaphore* sema, int timeout_ms)
{
    std::unique_lock<std::mutex> lock(sema->m);
    if (!sema->cv.wait_for(lock, std::chrono::milliseconds(timeout_ms), [sema] { return sema->count > 0; }))
        return false;
    sema->count--;
    return true;
}
void Semaphore_Post(Semaphore* sema, int count)
{
    {
        std::lock_guard<std::mutex> lock(sema->m);
        sema->count += count;
    }
    sema->cv.notify_all();
}

Mutex* Mutex_Create() { return new Mutex; }
void Mutex_Free(Mutex* mutex) { delete mutex; }
void Mutex_Lock(Mutex* mutex) { mutex->m.lock(); }
void Mutex_Unlock(Mutex* mutex) { mutex->m.unlock(); }
bool Mutex_TryLock(Mutex* mutex) { return mutex->m.try_lock(); }

u64 GetMSCount()
{
    return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
}

u64 GetUSCount()
{
    return std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
}

void Sleep(u64 usecs) { std::this_thread::sleep_for(std::chrono::microseconds(usecs)); }

void WriteNDSSave(const u8* savedata, u32 savelen, u32, u32, void* userdata)
{
    auto* inst = static_cast<DSInstance*>(userdata);
    inst->saveBuf.assign(savedata, savedata + savelen);
    inst->saveDirty = true;
    inst->saveQuietFrames = 0;
}

void WriteGBASave(const u8*, u32, u32, u32, void*) {}
void WriteFirmware(const Firmware&, u32, u32, void*) {}
void WriteDateTime(int, int, int, int, int, int, void*) {}

// Local DS wireless: not offered (the online link goes through the mailbox instead).
void MP_Begin(void*) {}
void MP_End(void*) {}
int MP_SendPacket(u8*, int, u64, void*) { return 0; }
int MP_RecvPacket(u8*, u64*, void*) { return 0; }
int MP_SendCmd(u8*, int, u64, void*) { return 0; }
int MP_SendReply(u8*, int, u64, u16, void*) { return 0; }
int MP_SendAck(u8*, int, u64, void*) { return 0; }
int MP_RecvHostPacket(u8*, u64*, void*) { return 0; }
u16 MP_RecvReplies(u8*, u64, u16, void*) { return 0; }

int Net_SendPacket(u8*, int, void*) { return 0; }
int Net_RecvPacket(u8*, void*) { return 0; }

void Camera_Start(int, void*) {}
void Camera_Stop(int, void*) {}
void Camera_CaptureFrame(int, u32* frame, int width, int height, bool, void*)
{
    memset(frame, 0, (size_t)width * height * sizeof(u32));
}

void Mic_Start(void*) {}
void Mic_Stop(void*) {}
int Mic_ReadInput(s16*, int, void*) { return 0; }

AACDecoder* AAC_Init() { return nullptr; }
void AAC_DeInit(AACDecoder*) {}
bool AAC_Configure(AACDecoder*, int, int) { return false; }
bool AAC_DecodeFrame(AACDecoder*, const void*, int, void*, int) { return false; }

bool Addon_KeyDown(KeyType, void*) { return false; }
void Addon_RumbleStart(u32, void*) {}
void Addon_RumbleStop(void*) {}
float Addon_MotionQuery(MotionQueryType, void*) { return 0.f; }

DynamicLibrary* DynamicLibrary_Load(const char*) { return nullptr; }
void DynamicLibrary_Unload(DynamicLibrary*) {}
void* DynamicLibrary_LoadFunction(DynamicLibrary*, const char*) { return nullptr; }

}
