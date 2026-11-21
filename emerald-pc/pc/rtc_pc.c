// Host-clock replacement for the Seiko S-3511 RTC driver (siirtc.c).
// The game keeps its own offset from the RTC in the save file, so the
// RTC only has to report the real date and time.
#include <time.h>
#include <stdint.h>
#include <string.h>

typedef uint8_t u8; typedef uint8_t bool8;

struct SiiRtcInfo {
    u8 year, month, day, dayOfWeek, hour, minute, second, status, alarmHour, alarmMinute;
};

static u8 Bcd(int v) { return (u8)(((v / 10) << 4) | (v % 10)); }

void SiiRtcUnprotect(void) {}
void SiiRtcProtect(void) {}
u8 SiiRtcProbe(void) { return 1; }
bool8 SiiRtcReset(void) { return 1; }

bool8 SiiRtcGetStatus(struct SiiRtcInfo *rtc)
{
    rtc->status = 0x40; // 24-hour mode, no power-failure flag
    return 1;
}

bool8 SiiRtcSetStatus(struct SiiRtcInfo *rtc) { (void)rtc; return 1; }

bool8 SiiRtcGetDateTime(struct SiiRtcInfo *rtc)
{
    time_t t = time(NULL);
    struct tm *tm = localtime(&t);
    int year = tm->tm_year + 1900;
    // The cartridge RTC only counts 2000-2099.
    if (year < 2000) year = 2000;
    rtc->year = Bcd(year % 100);
    rtc->month = Bcd(tm->tm_mon + 1);
    rtc->day = Bcd(tm->tm_mday);
    rtc->dayOfWeek = Bcd(tm->tm_wday);
    rtc->hour = Bcd(tm->tm_hour);
    rtc->minute = Bcd(tm->tm_min);
    rtc->second = Bcd(tm->tm_sec);
    return 1;
}

bool8 SiiRtcSetDateTime(struct SiiRtcInfo *rtc) { (void)rtc; return 1; }

bool8 SiiRtcGetTime(struct SiiRtcInfo *rtc)
{
    struct SiiRtcInfo tmp;
    SiiRtcGetDateTime(&tmp);
    rtc->hour = tmp.hour;
    rtc->minute = tmp.minute;
    rtc->second = tmp.second;
    return 1;
}

bool8 SiiRtcSetTime(struct SiiRtcInfo *rtc) { (void)rtc; return 1; }
bool8 SiiRtcSetAlarm(struct SiiRtcInfo *rtc) { (void)rtc; return 1; }
