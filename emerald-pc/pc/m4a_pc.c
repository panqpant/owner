// C port of m4a_1.s (the MusicPlayer2000 / "m4a" sound engine core) plus a
// PC audio mixer.
//
// Sequencer logic (MPlayMain, ply_* commands, ply_note channel allocation,
// envelopes) is a direct translation of the assembly, because game code
// polls this state (e.g. "is the BGM / cry still playing"). Only the final
// sample generation differs: instead of the GBA's 8-bit 13 kHz mix we render
// 16-bit stereo at 48 kHz, and emulate the GB-compatible PSG channels from
// the register writes m4a.c makes.
//
// Compiled with the game's flags so it can use the real m4a structures.
#include <math.h>
#include <stdlib.h>
#include "global.h"
#include "gba/m4a_internal.h"
#include "port.h"

extern const u8 gClockTable[];
extern const s8 gDeltaEncodingTable[];
extern void *const gMPlayJumpTableTemplate[];
u32 MidiKeyToFreq(struct WaveData *wav, u8 key, u8 fineAdjust);
void ClearChain(void *x);
void Clear64byte(void *addr);

#define TONEDATA_TYPE_REV 0x10
#define TONEDATA_TYPE_CMP 0x20
#define WAVE_DATA_FLAG_LOOP 0xC0

#define OUT_RATE 48000
#define GBA_FPS (16777216.0 / 280896.0)

typedef void (*JumpFunc)(struct MusicPlayerInfo *, struct MusicPlayerTrack *);

// ---------------------------------------------------------------------------
// Small helpers

u32 umul3232H32(u32 a, u32 b)
{
    return (u32)(((u64)a * b) >> 32);
}

void MPlayJumpTableCopy(MPlayFunc *table)
{
    memcpy(table, gMPlayJumpTableTemplate, 36 * sizeof(void *));
}

// Called through the jump table with the address to clear; the game's header
// declares it without parameters, so define it under another name and alias.
static void SoundMainBTM_Impl(void *p)
{
    memset(p, 0, 64);
}
void SoundMainBTM(void) __attribute__((alias("SoundMainBTM_Impl")));

void RealClearChain(void *x)
{
    struct SoundChannel *chan = x;
    struct MusicPlayerTrack *track = chan->track;
    struct SoundChannel *next, *prev;

    if (!track)
        return;
    next = chan->nextChannelPointer;
    prev = chan->prevChannelPointer;
    if (prev)
        prev->nextChannelPointer = next;
    else
        track->chan = next;
    if (next)
        next->prevChannelPointer = prev;
    chan->track = NULL;
}

static u8 ReadCmdByte(struct MusicPlayerTrack *track)
{
    return *track->cmdPtr++;
}

// ClearModM (clear_modM in the assembly) is shared with m4a.c.

// ---------------------------------------------------------------------------
// Sequence commands

void ply_fine(struct MusicPlayerInfo *mplay, struct MusicPlayerTrack *track)
{
    struct SoundChannel *chan;
    (void)mplay;
    for (chan = track->chan; chan; chan = chan->nextChannelPointer)
    {
        if (chan->statusFlags & SOUND_CHANNEL_SF_ON)
            chan->statusFlags |= SOUND_CHANNEL_SF_STOP;
        RealClearChain(chan);
    }
    track->flags = 0;
}

static u8 *ReadPtr(const u8 *p)
{
    return (u8 *)(uintptr_t)(p[0] | (p[1] << 8) | (p[2] << 16) | ((u32)p[3] << 24));
}

void ply_goto(struct MusicPlayerInfo *mplay, struct MusicPlayerTrack *track)
{
    (void)mplay;
    track->cmdPtr = ReadPtr(track->cmdPtr);
}

void ply_patt(struct MusicPlayerInfo *mplay, struct MusicPlayerTrack *track)
{
    if (track->patternLevel < 3)
    {
        track->patternStack[track->patternLevel] = track->cmdPtr + 4;
        track->patternLevel++;
        ply_goto(mplay, track);
    }
    else
    {
        ply_fine(mplay, track);
    }
}

void ply_pend(struct MusicPlayerInfo *mplay, struct MusicPlayerTrack *track)
{
    (void)mplay;
    if (track->patternLevel)
    {
        track->patternLevel--;
        track->cmdPtr = track->patternStack[track->patternLevel];
    }
}

void ply_rept(struct MusicPlayerInfo *mplay, struct MusicPlayerTrack *track)
{
    u8 *p = track->cmdPtr;
    (void)mplay;
    if (*p == 0)
    {
        track->cmdPtr = ReadPtr(p + 1);
        return;
    }
    track->repN++;
    if (track->repN < *p)
    {
        track->cmdPtr = ReadPtr(p + 1);
    }
    else
    {
        track->repN = 0;
        track->cmdPtr = p + 5;
    }
}

void ply_prio(struct MusicPlayerInfo *mplay, struct MusicPlayerTrack *track)
{
    (void)mplay;
    track->priority = ReadCmdByte(track);
}

void ply_tempo(struct MusicPlayerInfo *mplay, struct MusicPlayerTrack *track)
{
    u16 t = ReadCmdByte(track) * 2;
    mplay->tempoD = t;
    mplay->tempoI = (t * mplay->tempoU) >> 8;
}

void ply_keysh(struct MusicPlayerInfo *mplay, struct MusicPlayerTrack *track)
{
    (void)mplay;
    track->keyShift = ReadCmdByte(track);
    track->flags |= MPT_FLG_PITCHG;
}

void ply_voice(struct MusicPlayerInfo *mplay, struct MusicPlayerTrack *track)
{
    u8 idx = ReadCmdByte(track);
    track->tone = mplay->tone[idx];
}

void ply_vol(struct MusicPlayerInfo *mplay, struct MusicPlayerTrack *track)
{
    (void)mplay;
    track->vol = ReadCmdByte(track);
    track->flags |= MPT_FLG_VOLCHG;
}

void ply_pan(struct MusicPlayerInfo *mplay, struct MusicPlayerTrack *track)
{
    (void)mplay;
    track->pan = ReadCmdByte(track) - C_V;
    track->flags |= MPT_FLG_VOLCHG;
}

void ply_bend(struct MusicPlayerInfo *mplay, struct MusicPlayerTrack *track)
{
    (void)mplay;
    track->bend = ReadCmdByte(track) - C_V;
    track->flags |= MPT_FLG_PITCHG;
}

void ply_bendr(struct MusicPlayerInfo *mplay, struct MusicPlayerTrack *track)
{
    (void)mplay;
    track->bendRange = ReadCmdByte(track);
    track->flags |= MPT_FLG_PITCHG;
}

void ply_lfodl(struct MusicPlayerInfo *mplay, struct MusicPlayerTrack *track)
{
    (void)mplay;
    track->lfoDelay = ReadCmdByte(track);
}

void ply_modt(struct MusicPlayerInfo *mplay, struct MusicPlayerTrack *track)
{
    u8 v = ReadCmdByte(track);
    (void)mplay;
    if (track->modT != v)
    {
        track->modT = v;
        track->flags |= MPT_FLG_VOLCHG | MPT_FLG_PITCHG;
    }
}

void ply_tune(struct MusicPlayerInfo *mplay, struct MusicPlayerTrack *track)
{
    (void)mplay;
    track->tune = ReadCmdByte(track) - C_V;
    track->flags |= MPT_FLG_PITCHG;
}

void ply_port(struct MusicPlayerInfo *mplay, struct MusicPlayerTrack *track)
{
    u8 reg = ReadCmdByte(track);
    u8 val = ReadCmdByte(track);
    (void)mplay;
    *(vu8 *)(REG_ADDR_SOUND1CNT_L + reg) = val;
}

void ply_lfos(struct MusicPlayerInfo *mplay, struct MusicPlayerTrack *track)
{
    (void)mplay;
    track->lfoSpeed = ReadCmdByte(track);
    if (track->lfoSpeed == 0)
        ClearModM(track);
}

void ply_mod(struct MusicPlayerInfo *mplay, struct MusicPlayerTrack *track)
{
    (void)mplay;
    track->mod = ReadCmdByte(track);
    if (track->mod == 0)
        ClearModM(track);
}

void ply_endtie(struct MusicPlayerInfo *mplay, struct MusicPlayerTrack *track)
{
    struct SoundChannel *chan;
    u8 key;
    (void)mplay;

    if (*track->cmdPtr < 0x80)
    {
        key = *track->cmdPtr++;
        track->key = key;
    }
    else
    {
        key = track->key;
    }

    for (chan = track->chan; chan; chan = chan->nextChannelPointer)
    {
        u8 f = chan->statusFlags;
        if ((f & (SOUND_CHANNEL_SF_START | SOUND_CHANNEL_SF_ENV)) && !(f & SOUND_CHANNEL_SF_STOP)
         && chan->midiKey == key)
        {
            chan->statusFlags = f | SOUND_CHANNEL_SF_STOP;
            return;
        }
    }
}

// ---------------------------------------------------------------------------
// Channel volume and note-on

static void ChnVolSet(struct SoundChannel *chan, struct MusicPlayerTrack *track)
{
    s32 pan = chan->rhythmPan;
    u32 v;

    v = ((u32)((0x80 + pan) * chan->velocity) * track->volMR) >> 14;
    chan->rightVolume = v > 0xFF ? 0xFF : v;
    v = ((u32)((0x7F - pan) * chan->velocity) * track->volML) >> 14;
    chan->leftVolume = v > 0xFF ? 0xFF : v;
}

void ply_note(u32 noteCmd, struct MusicPlayerInfo *mplay, struct MusicPlayerTrack *track)
{
    struct SoundInfo *si = SOUND_INFO_PTR;
    struct ToneData *tone;
    struct SoundChannel *chan = NULL;
    s32 rhythmPan = 0;
    u32 key, prio, cgbType;
    u8 *p;
    s32 k;

    track->gateTime = gClockTable[noteCmd];
    p = track->cmdPtr;
    if (*p < 0x80)
    {
        track->key = *p++;
        if (*p < 0x80)
        {
            track->velocity = *p++;
            if (*p < 0x80)
            {
                track->gateTime += *p++;
            }
        }
        track->cmdPtr = p;
    }

    tone = &track->tone;
    key = track->key;
    if (tone->type & (TONEDATA_TYPE_RHY | TONEDATA_TYPE_SPL))
    {
        u32 idx = key;
        if (tone->type & TONEDATA_TYPE_SPL)
            idx = ((u8 *)(uintptr_t)*(u32 *)&tone->attack)[key]; // keySplitTable
        tone = &((struct ToneData *)tone->wav)[idx];
        if (tone->type & (TONEDATA_TYPE_SPL | TONEDATA_TYPE_RHY))
            return;
        if (track->tone.type & TONEDATA_TYPE_RHY)
        {
            if (tone->pan_sweep & 0x80)
                rhythmPan = ((s32)tone->pan_sweep - TONEDATA_P_S_PAN) << 1;
            key = tone->key;
        }
    }

    prio = mplay->priority + track->priority;
    if (prio > 0xFF)
        prio = 0xFF;

    cgbType = tone->type & TONEDATA_TYPE_CGB;
    if (cgbType)
    {
        struct CgbChannel *cgb;
        if (!si->cgbChans)
            return;
        cgb = &si->cgbChans[cgbType - 1];
        if ((cgb->statusFlags & SOUND_CHANNEL_SF_ON) && !(cgb->statusFlags & SOUND_CHANNEL_SF_STOP))
        {
            if (cgb->priority > prio)
                return;
            if (cgb->priority == prio && (uintptr_t)cgb->track < (uintptr_t)track)
                return;
        }
        chan = (struct SoundChannel *)cgb;
    }
    else
    {
        u32 bestPrio = prio;
        struct MusicPlayerTrack *bestTrack = track;
        int foundStopped = 0, i;
        struct SoundChannel *c = si->chans;

        for (i = 0; i < si->maxChans; i++, c++)
        {
            u8 f = c->statusFlags;
            if (!(f & SOUND_CHANNEL_SF_ON))
            {
                chan = c;
                break;
            }
            if (f & SOUND_CHANNEL_SF_STOP)
            {
                if (!foundStopped)
                {
                    foundStopped = 1;
                    bestPrio = c->priority;
                    bestTrack = c->track;
                    chan = c;
                    continue;
                }
            }
            else if (foundStopped)
            {
                continue;
            }

            if (c->priority < bestPrio)
            {
                bestPrio = c->priority;
                bestTrack = c->track;
                chan = c;
            }
            else if (c->priority == bestPrio)
            {
                if ((uintptr_t)c->track > (uintptr_t)bestTrack)
                {
                    bestTrack = c->track;
                    chan = c;
                }
                else if ((uintptr_t)c->track == (uintptr_t)bestTrack)
                {
                    chan = c;
                }
            }
        }
        if (!chan)
            return;
    }

    ClearChain(chan);
    chan->prevChannelPointer = NULL;
    chan->nextChannelPointer = track->chan;
    if (track->chan)
        ((struct SoundChannel *)track->chan)->prevChannelPointer = chan;
    track->chan = chan;
    chan->track = track;

    track->lfoDelayC = track->lfoDelay;
    if (track->lfoDelay)
        ClearModM(track);

    TrkVolPitSet(mplay, track);

    chan->gateTime = track->gateTime;
    chan->midiKey = track->key;
    chan->velocity = track->velocity;
    chan->priority = prio;
    chan->key = key;
    chan->rhythmPan = rhythmPan;
    chan->type = tone->type;
    chan->wav = tone->wav;
    chan->attack = tone->attack;
    chan->decay = tone->decay;
    chan->sustain = tone->sustain;
    chan->release = tone->release;
    chan->pseudoEchoVolume = track->pseudoEchoVolume;
    chan->pseudoEchoLength = track->pseudoEchoLength;
    ChnVolSet(chan, track);

    k = (s32)chan->key + track->keyM;
    if (k < 0)
        k = 0;

    if (cgbType)
    {
        struct CgbChannel *cgb = (struct CgbChannel *)chan;
        u8 ps = tone->pan_sweep;
        cgb->length = tone->length;
        cgb->sweep = ((ps & 0x80) || !(ps & 0x70)) ? 8 : ps;
        chan->frequency = si->MidiKeyToCgbFreq(cgbType, k, track->pitM);
    }
    else
    {
        chan->count = track->unk_3C;
        chan->frequency = MidiKeyToFreq(chan->wav, k, track->pitM);
    }
    chan->statusFlags = SOUND_CHANNEL_SF_START;
    track->flags &= 0xF0;
}

void TrackStop(struct MusicPlayerInfo *mplay, struct MusicPlayerTrack *track)
{
    struct SoundChannel *chan;
    (void)mplay;

    if (!(track->flags & MPT_FLG_EXIST))
        return;
    for (chan = track->chan; chan; chan = chan->nextChannelPointer)
    {
        if (chan->statusFlags)
        {
            u8 cgb = chan->type & TONEDATA_TYPE_CGB;
            if (cgb)
                SOUND_INFO_PTR->CgbOscOff(cgb);
            chan->statusFlags = 0;
        }
        chan->track = NULL;
    }
    track->chan = NULL;
}

// ---------------------------------------------------------------------------
// Sequencer tick

void MPlayMain(struct MusicPlayerInfo *mplay)
{
    struct SoundInfo *si;
    u32 tempoC;

    if (mplay->ident != ID_NUMBER)
        return;
    mplay->ident++;

    if (mplay->MPlayMainNext)
        mplay->MPlayMainNext(mplay->musicPlayerNext);

    if (mplay->status & MUSICPLAYER_STATUS_PAUSE)
        goto done;

    si = SOUND_INFO_PTR;
    FadeOutBody(mplay);
    if (mplay->status & MUSICPLAYER_STATUS_PAUSE)
        goto done;

    tempoC = (u16)(mplay->tempoC + mplay->tempoI);
    while (tempoC >= 150)
    {
        struct MusicPlayerTrack *track = mplay->tracks;
        u32 bit = 1, active = 0;
        int i;

        for (i = 0; i < mplay->trackCount; i++, track++, bit <<= 1)
        {
            struct SoundChannel *chan;

            if (!(track->flags & MPT_FLG_EXIST))
                continue;
            active |= bit;

            for (chan = track->chan; chan; chan = chan->nextChannelPointer)
            {
                if (chan->statusFlags & SOUND_CHANNEL_SF_ON)
                {
                    if (chan->gateTime && --chan->gateTime == 0)
                        chan->statusFlags |= SOUND_CHANNEL_SF_STOP;
                }
                else
                {
                    ClearChain(chan);
                }
            }

            if (track->flags & MPT_FLG_START)
            {
                Clear64byte(track);
                track->flags = MPT_FLG_EXIST;
                track->bendRange = 2;
                track->volX = 64;
                track->lfoSpeed = 22;
                track->tone.type = 1;
            }

            while (track->wait == 0)
            {
                u32 cmd = *track->cmdPtr;
                if (cmd < 0x80)
                {
                    cmd = track->runningStatus;
                }
                else
                {
                    track->cmdPtr++;
                    if (cmd >= 0xBD)
                        track->runningStatus = cmd;
                }

                if (cmd >= 0xCF)
                {
                    si->plynote(cmd - 0xCF, mplay, track);
                }
                else if (cmd > 0xB0)
                {
                    mplay->cmd = cmd - 0xB1;
                    ((JumpFunc)si->MPlayJumpTable[cmd - 0xB1])(mplay, track);
                    if (track->flags == 0)
                        goto next_track;
                }
                else
                {
                    track->wait = gClockTable[cmd - 0x80];
                }
            }

            track->wait--;

            if (track->lfoSpeed && track->mod)
            {
                if (track->lfoDelayC)
                {
                    track->lfoDelayC--;
                }
                else
                {
                    u8 c = track->lfoSpeedC += track->lfoSpeed;
                    s32 m = ((s8)(c - 0x40) < 0) ? (s32)(s8)c : (s32)(0x80 - c);
                    m = (track->mod * m) >> 6;
                    if ((u8)(track->modM ^ m))
                    {
                        track->modM = m;
                        track->flags |= track->modT == 0 ? MPT_FLG_PITCHG : MPT_FLG_VOLCHG;
                    }
                }
            }
        next_track:;
        }

        mplay->clock++;
        if (active == 0)
        {
            mplay->status = MUSICPLAYER_STATUS_PAUSE;
            goto done;
        }
        mplay->status = active;
        tempoC -= 150;
    }
    mplay->tempoC = tempoC;

    {
        struct MusicPlayerTrack *track = mplay->tracks;
        int i;
        for (i = 0; i < mplay->trackCount; i++, track++)
        {
            struct SoundChannel *chan;

            if (!(track->flags & MPT_FLG_EXIST) || !(track->flags & (MPT_FLG_VOLCHG | MPT_FLG_PITCHG)))
                continue;

            TrkVolPitSet(mplay, track);
            for (chan = track->chan; chan; chan = chan->nextChannelPointer)
            {
                u32 cgb;
                if (!(chan->statusFlags & SOUND_CHANNEL_SF_ON))
                {
                    ClearChain(chan);
                    continue;
                }
                cgb = chan->type & TONEDATA_TYPE_CGB;
                if (track->flags & MPT_FLG_VOLCHG)
                {
                    ChnVolSet(chan, track);
                    if (cgb)
                        ((struct CgbChannel *)chan)->modify |= CGB_CHANNEL_MO_VOL;
                }
                if (track->flags & MPT_FLG_PITCHG)
                {
                    s32 k = (s32)chan->key + track->keyM;
                    if (k < 0)
                        k = 0;
                    if (cgb)
                    {
                        chan->frequency = si->MidiKeyToCgbFreq(cgb, k, track->pitM);
                        ((struct CgbChannel *)chan)->modify |= CGB_CHANNEL_MO_PIT;
                    }
                    else
                    {
                        chan->frequency = MidiKeyToFreq(chan->wav, k, track->pitM);
                    }
                }
            }
            track->flags &= 0xF0;
        }
    }

done:
    mplay->ident = ID_NUMBER;
}

void m4aSoundVSync(void)
{
    struct SoundInfo *si = SOUND_INFO_PTR;
    s32 c;
    if (si->ident - ID_NUMBER > 1)
        return;
    c = (s32)si->pcmDmaCounter - 1;
    si->pcmDmaCounter = c;
    if (c > 0)
        return;
    si->pcmDmaCounter = si->pcmDmaPeriod;
}

// ---------------------------------------------------------------------------
// Mixer

#define MAX_FRAME_SAMPLES 1024

static double sSampleAcc;
static double sFps = GBA_FPS;

// Audio samples are generated per game frame; when the game is locked to the
// display's refresh rate the frame rate changes slightly.
void M4aPcSetFrameRate(double fps)
{
    sFps = fps > 1 ? fps : GBA_FPS;
}
static float sMixL[MAX_FRAME_SAMPLES], sMixR[MAX_FRAME_SAMPLES];
static float sPrevL[MAX_FRAME_SAMPLES], sPrevR[MAX_FRAME_SAMPLES];
static s16 sOut[MAX_FRAME_SAMPLES * 2];
static double sPos[MAX_DIRECTSOUND_CHANNELS]; // playback position (samples)

// "HD audio" (on by default, F5 toggles): high-quality resampling, smooth
// volume changes, band-limited PSG with a stereo double, a stereo hall
// reverb and a mastering stage. Off = the GBA mixer's sound.
int gPcHdAudio = 1;
static float sLastVol[MAX_DIRECTSOUND_CHANNELS][2];
static u8 sJustStarted[MAX_DIRECTSOUND_CHANNELS];

static s8 sDecoded[64];
static const struct WaveData *sDecodedWav;
static s32 sDecodedBlock = -1;

static int ChanCompressed(const struct SoundChannel *c)
{
    return (c->type & (TONEDATA_TYPE_CMP | TONEDATA_TYPE_REV)) && c->wav->type != 0;
}

static s32 WaveSample(const struct SoundChannel *c, s32 idx)
{
    const struct WaveData *w = c->wav;
    if (idx < 0)
        idx = 0;
    if ((u32)idx >= w->size)
        idx = w->size - 1;
    if (c->type & TONEDATA_TYPE_REV)
        idx = w->size - 1 - idx;
    if (ChanCompressed(c))
    {
        s32 block = idx >> 6;
        if (w != sDecodedWav || block != sDecodedBlock)
        {
            const u8 *src = (const u8 *)w->data + block * 33;
            s8 v = (s8)src[0];
            int i, n = 1;
            sDecoded[0] = v;
            v += gDeltaEncodingTable[src[1] & 0xF];
            sDecoded[n++] = v;
            for (i = 2; n < 64; i++)
            {
                v += gDeltaEncodingTable[src[i] >> 4];
                sDecoded[n++] = v;
                v += gDeltaEncodingTable[src[i] & 0xF];
                sDecoded[n++] = v;
            }
            sDecodedWav = w;
            sDecodedBlock = block;
        }
        return sDecoded[idx & 63];
    }
    return w->data[idx];
}

static void ChannelOff(struct SoundChannel *c)
{
    c->statusFlags = 0;
}

// Envelope update: a direct translation of the per-channel prologue of
// SoundMainRAM. Returns 0 if the channel is (now) off.
static int UpdateEnvelope(struct SoundInfo *si, struct SoundChannel *c, int idx)
{
    u8 f = c->statusFlags;
    u32 env;

    if (!(f & SOUND_CHANNEL_SF_ON))
        return 0;

    if (f & SOUND_CHANNEL_SF_START)
    {
        if (f & SOUND_CHANNEL_SF_STOP)
        {
            ChannelOff(c);
            return 0;
        }
        f = SOUND_CHANNEL_SF_ENV_ATTACK;
        c->statusFlags = f;
        sJustStarted[idx] = 1;
        sPos[idx] = c->count; // start offset
        c->currentPointer = c->wav->data + c->count;
        c->count = c->wav->size - c->count;
        env = 0;
        c->envelopeVolume = 0;
        c->fw = 0;
        if (((const u8 *)c->wav)[3] & WAVE_DATA_FLAG_LOOP)
        {
            f |= SOUND_CHANNEL_SF_LOOP;
            c->statusFlags = f;
        }
        goto attack;
    }

    env = c->envelopeVolume;
    if (f & SOUND_CHANNEL_SF_IEC)
    {
        u8 len = c->pseudoEchoLength;
        c->pseudoEchoLength = len - 1;
        if (len <= 1)
        {
            ChannelOff(c);
            return 0;
        }
        goto store;
    }
    if (f & SOUND_CHANNEL_SF_STOP)
    {
        env = (env * c->release) >> 8;
        if (env > c->pseudoEchoVolume)
            goto store;
    echo:
        env = c->pseudoEchoVolume;
        if (env == 0)
        {
            ChannelOff(c);
            return 0;
        }
        f |= SOUND_CHANNEL_SF_IEC;
        c->statusFlags = f;
        goto store;
    }
    if ((f & SOUND_CHANNEL_SF_ENV) == SOUND_CHANNEL_SF_ENV_DECAY)
    {
        env = (env * c->decay) >> 8;
        if (env > c->sustain)
            goto store;
        env = c->sustain;
        if (env == 0)
            goto echo;
        f--;
        c->statusFlags = f;
        goto store;
    }
    if ((f & SOUND_CHANNEL_SF_ENV) != SOUND_CHANNEL_SF_ENV_ATTACK)
        goto store;
attack:
    env += c->attack;
    if (env >= 0xFF)
    {
        env = 0xFF;
        f--;
        c->statusFlags = f;
    }
store:
    c->envelopeVolume = env;
    env = ((si->masterVolume + 1) * env) >> 4;
    c->envelopeVolumeRight = (c->rightVolume * env) >> 8;
    c->envelopeVolumeLeft = (c->leftVolume * env) >> 8;
    return 1;
}

// Sample with looping/ends handled, for interpolation taps.
static inline float Tap(const struct SoundChannel *c, s32 idx, u32 size, u32 loopStart, int loop)
{
    if (idx < 0)
        return 0;
    if ((u32)idx >= size)
    {
        if (!loop || size <= loopStart)
            return 0;
        idx = loopStart + (idx - size) % (s32)(size - loopStart);
    }
    return WaveSample(c, idx);
}

// Lanczos-3 kernel, tabulated at 256 sub-sample phases.
static float sLanczos[257][6];
static void InitLanczos(void)
{
    int ph, k;
    for (ph = 0; ph <= 256; ph++)
    {
        double f = ph / 256.0, sum = 0;
        for (k = 0; k < 6; k++)
        {
            double x = (k - 2) - f, v;
            if (fabs(x) < 1e-9) v = 1;
            else if (fabs(x) >= 3) v = 0;
            else v = 3 * sin(M_PI * x) * sin(M_PI * x / 3) / (M_PI * M_PI * x * x);
            sLanczos[ph][k] = (float)v;
            sum += v;
        }
        for (k = 0; k < 6; k++)
            sLanczos[ph][k] /= (float)sum;
    }
}

static void MixDirectSound(struct SoundInfo *si, int n)
{
    int i, s;
    static int lanczosReady;
    if (!lanczosReady)
    {
        InitLanczos();
        lanczosReady = 1;
        if (getenv("EMERALD_CLASSIC_AUDIO"))
            gPcHdAudio = 0;
    }
    double pcmFreq = si->pcmFreq ? si->pcmFreq : 13379;

    for (i = 0; i < si->maxChans && i < MAX_DIRECTSOUND_CHANNELS; i++)
    {
        struct SoundChannel *c = &si->chans[i];
        const struct WaveData *w;
        double step, pos;
        float vl, vr;
        u32 size, loopStart;
        int loop;

        if (!UpdateEnvelope(si, c, i))
            continue;

        w = c->wav;
        size = w->size;
        loopStart = w->loopStart;
        loop = (c->statusFlags & SOUND_CHANNEL_SF_LOOP) && !(c->type & TONEDATA_TYPE_REV);
        if (c->type & TONEDATA_TYPE_FIX)
            step = pcmFreq / OUT_RATE;
        else
            step = (double)c->frequency * si->divFreq / 8388608.0 * pcmFreq / OUT_RATE;
        vl = c->envelopeVolumeLeft / 256.0f;
        vr = c->envelopeVolumeRight / 256.0f;
        pos = sPos[i];
        {
        // HD: glide from last frame's volume (except on a new note, so attacks stay crisp).
        float vl0 = sJustStarted[i] ? vl : sLastVol[i][0], vr0 = sJustStarted[i] ? vr : sLastVol[i][1];
        float dvl = gPcHdAudio ? (vl - vl0) / n : 0, dvr = gPcHdAudio ? (vr - vr0) / n : 0;
        if (!gPcHdAudio) { vl0 = vl; vr0 = vr; }
        sJustStarted[i] = 0;
        sLastVol[i][0] = vl;
        sLastVol[i][1] = vr;
        vl = vl0;
        vr = vr0;

        for (s = 0; s < n; s++)
        {
            s32 ip = (s32)pos;
            float smp;
            if ((u32)ip >= size)
            {
                if (loop && size > loopStart)
                {
                    pos = loopStart + fmod(pos - size, (double)(size - loopStart));
                    ip = (s32)pos;
                }
                else
                {
                    ChannelOff(c);
                    break;
                }
            }
            if (gPcHdAudio && step <= 1.0)
            {
                const float *kk = sLanczos[(int)((pos - ip) * 256.0)];
                smp = kk[0] * Tap(c, ip - 2, size, loopStart, loop) + kk[1] * Tap(c, ip - 1, size, loopStart, loop)
                    + kk[2] * Tap(c, ip, size, loopStart, loop) + kk[3] * Tap(c, ip + 1, size, loopStart, loop)
                    + kk[4] * Tap(c, ip + 2, size, loopStart, loop) + kk[5] * Tap(c, ip + 3, size, loopStart, loop);
            }
            else if (c->type & TONEDATA_TYPE_FIX)
            {
                smp = WaveSample(c, ip);
            }
            else
            {
                s32 a = WaveSample(c, ip);
                s32 nb = ip + 1;
                s32 b;
                if ((u32)nb >= size)
                    nb = loop ? (s32)loopStart : ip;
                b = WaveSample(c, nb);
                smp = a + (b - a) * (float)(pos - ip);
            }
            sMixL[s] += smp * vl;
            sMixR[s] += smp * vr;
            vl += dvl;
            vr += dvr;
            pos += step;
        }
        }
        sPos[i] = pos;
        if (c->statusFlags)
        {
            u32 ip = (u32)pos;
            c->count = ip < size ? size - ip : 0;
            if (!ChanCompressed(c) && !(c->type & TONEDATA_TYPE_REV))
                c->currentPointer = (s8 *)w->data + (ip < size ? ip : size);
        }
    }
}

// ---------------------------------------------------------------------------
// GB-compatible PSG channels, driven by the NRxx register writes m4a.c makes.

struct Psg {
    int on;
    double phase;    // 0..1 position in waveform
    int vol;         // 0..15
    int envDir, envPeriod;
    double envTimer;
    int lenEnabled;
    double lenTimer; // seconds remaining
    int sweepPeriod, sweepNeg, sweepShift;
    double sweepTimer;
    u32 freq;        // 11-bit GB frequency value
    u16 lfsr;
    u8 wave[32];
    double phase2;   // HD: detuned double of the square channels
    float lp;        // HD: smoothing filter state
};
static struct Psg sPsg[4];

#define NR(off) (*(vu8 *)(REG_BASE + (off)))
enum { NR10 = 0x60, NR11 = 0x62, NR12 = 0x63, NR13 = 0x64, NR14 = 0x65,
       NR21 = 0x68, NR22 = 0x69, NR23 = 0x6C, NR24 = 0x6D,
       NR30 = 0x70, NR31 = 0x72, NR32 = 0x73, NR33 = 0x74, NR34 = 0x75,
       NR41 = 0x78, NR42 = 0x79, NR43 = 0x7C, NR44 = 0x7D,
       NR50 = 0x80, NR51 = 0x81, SOUNDCNT_H = 0x82, NR52 = 0x84, WAVE_RAM = 0x90 };

static const int sNrx2[4] = { NR12, NR22, 0, NR42 };
static const int sNrx4[4] = { NR14, NR24, NR34, NR44 };
static const int sNrx1[4] = { NR11, NR21, NR31, NR41 };
static const int sNrx3[4] = { NR13, NR23, NR33, NR43 };

static void PsgLatch(void)
{
    int ch;
    for (ch = 0; ch < 4; ch++)
    {
        struct Psg *p = &sPsg[ch];
        u8 n4 = NR(sNrx4[ch]);

        if (ch < 3)
            p->freq = NR(sNrx3[ch]) | ((n4 & 7) << 8);

        if (n4 & 0x80) // trigger: the write-only bit is consumed here
        {
            NR(sNrx4[ch]) = n4 & 0x7F;
            p->on = 1;
            p->lenEnabled = (n4 >> 6) & 1;
            if (ch == 2)
            {
                int i;
                p->lenTimer = (256 - NR(NR31)) / 256.0;
                for (i = 0; i < 16; i++)
                {
                    u8 b = NR(WAVE_RAM + i);
                    p->wave[i * 2] = b >> 4;
                    p->wave[i * 2 + 1] = b & 0xF;
                }
                p->phase = 0;
            }
            else
            {
                u8 nrx2 = NR(sNrx2[ch]);
                p->lenTimer = (64 - (NR(sNrx1[ch]) & 0x3F)) / 256.0;
                p->vol = nrx2 >> 4;
                p->envDir = (nrx2 & 8) ? 1 : -1;
                p->envPeriod = nrx2 & 7;
                p->envTimer = p->envPeriod / 64.0;
                if ((nrx2 & 0xF8) == 0)
                    p->on = 0; // DAC off
            }
            if (ch == 0)
            {
                u8 s = NR(NR10);
                p->sweepPeriod = (s >> 4) & 7;
                p->sweepNeg = (s >> 3) & 1;
                p->sweepShift = s & 7;
                p->sweepTimer = p->sweepPeriod / 128.0;
            }
            if (ch == 3)
                p->lfsr = 0x7FFF;
        }
        if (ch == 2 && !(NR(NR30) & 0x80))
            p->on = 0;
    }
}

static inline float PolyBlep(double t, double dt)
{
    if (t < dt) { t /= dt; return (float)(t + t - t * t - 1.0); }
    if (t > 1.0 - dt) { t = (t - 1.0) / dt; return (float)(t * t + t + t + 1.0); }
    return 0.0f;
}

// Band-limited GB pulse: high from s to s + d (fractions of a cycle).
static float Pulse(double ph, double dt, int duty)
{
    static const double sStart[4] = { 7 / 8.0, 7 / 8.0, 5 / 8.0, 1 / 8.0 };
    static const double sLen[4] = { 1 / 8.0, 2 / 8.0, 4 / 8.0, 6 / 8.0 };
    double st = sStart[duty], ln = sLen[duty];
    double t = ph - st; t -= floor(t);
    float v = t < ln ? 1.0f : -1.0f;
    double te = t - ln; te -= floor(te);
    v += PolyBlep(t, dt);      // rising edge
    v -= PolyBlep(te, dt);     // falling edge
    return v;
}

static void MixPsg(int n)
{
    static const u8 sDuty[4][8] = {
        { 0, 0, 0, 0, 0, 0, 0, 1 }, { 1, 0, 0, 0, 0, 0, 0, 1 },
        { 1, 0, 0, 0, 0, 1, 1, 1 }, { 0, 1, 1, 1, 1, 1, 1, 0 },
    };
    u8 nr51 = NR(NR51), nr50 = NR(NR50);
    u16 cnth = *(vu16 *)(REG_BASE + SOUNDCNT_H);
    float ratio = (cnth & 3) == 0 ? 0.25f : (cnth & 3) == 1 ? 0.5f : 1.0f;
    float mvL = (((nr50 >> 4) & 7) + 1) * ratio * 0.5f;
    float mvR = ((nr50 & 7) + 1) * ratio * 0.5f;
    const double dt = 1.0 / OUT_RATE;
    int ch, s;

    if (!(NR(NR52) & 0x80))
        return;

    for (ch = 0; ch < 4; ch++)
    {
        struct Psg *p = &sPsg[ch];
        int toL = (nr51 >> (4 + ch)) & 1, toR = (nr51 >> ch) & 1;
        double hz = 0;
        int shift3 = 0;

        if (!p->on)
            continue;

        if (ch < 2)
            hz = 131072.0 / (2048 - p->freq) * 8; // duty steps per second
        else if (ch == 2)
        {
            u8 v = NR(NR32);
            hz = 2097152.0 / (2048 - p->freq);   // wave samples per second
            shift3 = (v & 0x80) ? -1 : ((v >> 5) & 3);
        }
        else
        {
            u8 nr43 = NR(NR43);
            int r = nr43 & 7, sh = nr43 >> 4;
            hz = 524288.0 / (r ? r : 0.5) / (double)(2 << sh);
        }

        for (s = 0; s < n; s++)
        {
            float out = 0;

            if (p->lenEnabled)
            {
                p->lenTimer -= dt;
                if (p->lenTimer <= 0) { p->on = 0; break; }
            }
            if (ch != 2 && p->envPeriod)
            {
                p->envTimer -= dt;
                if (p->envTimer <= 0)
                {
                    p->envTimer += p->envPeriod / 64.0;
                    if (p->vol + p->envDir >= 0 && p->vol + p->envDir <= 15)
                        p->vol += p->envDir;
                }
            }
            if (ch == 0 && p->sweepPeriod && p->sweepShift)
            {
                p->sweepTimer -= dt;
                if (p->sweepTimer <= 0)
                {
                    s32 d = p->freq >> p->sweepShift;
                    s32 nf = p->sweepNeg ? (s32)p->freq - d : (s32)p->freq + d;
                    p->sweepTimer += p->sweepPeriod / 128.0;
                    if (nf > 2047) { p->on = 0; break; }
                    if (nf >= 0) { p->freq = nf; hz = 131072.0 / (2048 - p->freq) * 8; }
                }
            }

            p->phase += hz * dt;
            if (ch < 2 && gPcHdAudio)
            {
                // Two band-limited oscillators ~7 cents apart, spread across
                // the stereo field: a fuller, wider lead.
                int duty = NR(sNrx1[ch]) >> 6;
                double cyc = hz / 8.0 * dt;
                float a, b;
                p->phase2 += hz * 1.004 * dt;
                if (p->phase2 > 64.0) p->phase2 -= 64.0;
                a = Pulse(p->phase / 8.0, cyc, duty);
                b = Pulse(p->phase2 / 8.0, cyc * 1.004, duty);
                if (toL) sMixL[s] += (a * 0.62f + b * 0.38f) * p->vol * mvL * 0.92f;
                if (toR) sMixR[s] += (a * 0.38f + b * 0.62f) * p->vol * mvR * 0.92f;
                if (ch < 3 && p->phase > 64.0)
                    p->phase -= 64.0;
                continue;
            }
            if (ch < 2)
            {
                int duty = NR(sNrx1[ch]) >> 6;
                int stepi = (int)p->phase & 7;
                out = sDuty[duty][stepi] ? p->vol : -p->vol;
            }
            else if (ch == 2)
            {
                int smp = p->wave[(int)p->phase & 31];
                if (shift3 < 0)
                    out = (smp - 7.5f) * 0.75f;
                else if (shift3 == 0)
                    out = 0;
                else
                    out = (smp - 7.5f) / (float)(1 << (shift3 - 1));
            }
            else
            {
                while (p->phase >= 1.0)
                {
                    int bit = (p->lfsr ^ (p->lfsr >> 1)) & 1;
                    p->phase -= 1.0;
                    p->lfsr = (p->lfsr >> 1) | (bit << 14);
                    if (NR(NR43) & 8)
                        p->lfsr = (p->lfsr & ~0x40) | (bit << 6);
                }
                out = (p->lfsr & 1) ? -p->vol : p->vol;
            }
            if (gPcHdAudio && ch >= 2)
            {
                // Soften the wave channel's 4-bit steps and the noise channel's hiss.
                float k = ch == 2 ? 0.45f : 0.6f;
                p->lp += (out - p->lp) * k;
                out = p->lp;
            }
            if (ch < 3 && p->phase > 64.0)
                p->phase -= 64.0;

            // Scale PSG into the same units as Direct Sound (s8 sample * 4 = 10-bit range).
            if (toL) sMixL[s] += out * mvL;
            if (toR) sMixR[s] += out * mvR;
        }
    }
}

// ---------------------------------------------------------------------------
// HD reverb (Freeverb-style: 8 parallel combs + 4 allpasses per side) and mastering.

#define NCOMB 8
#define NAP 4
static const int sCombLen[NCOMB] = { 1215, 1293, 1390, 1476, 1548, 1623, 1696, 1759 };
static const int sApLen[NAP] = { 605, 480, 371, 245 };
#define STEREO_SPREAD 25
static float sCombBuf[2][NCOMB][1800], sCombStore[2][NCOMB];
static int sCombIdx[2][NCOMB];
static float sApBuf[2][NAP][640];
static int sApIdx[2][NAP];

static float Reverb(int side, float in)
{
    float out = 0;
    int i;
    const float fb = 0.83f, damp = 0.28f;
    for (i = 0; i < NCOMB; i++)
    {
        int len = sCombLen[i] + side * STEREO_SPREAD;
        float *b = sCombBuf[side][i];
        float y = b[sCombIdx[side][i]];
        sCombStore[side][i] = y * (1 - damp) + sCombStore[side][i] * damp;
        b[sCombIdx[side][i]] = in + sCombStore[side][i] * fb;
        if (++sCombIdx[side][i] >= len) sCombIdx[side][i] = 0;
        out += y;
    }
    for (i = 0; i < NAP; i++)
    {
        int len = sApLen[i] + side * STEREO_SPREAD;
        float *b = sApBuf[side][i];
        float bo = b[sApIdx[side][i]];
        b[sApIdx[side][i]] = out + bo * 0.5f;
        out = bo - out;
        if (++sApIdx[side][i] >= len) sApIdx[side][i] = 0;
    }
    return out;
}

// RBJ shelving biquads.
struct Biquad { float b0, b1, b2, a1, a2, z1[2], z2[2]; };
static struct Biquad sLowShelf, sHighShelf;
static void ShelfInit(struct Biquad *q, int high, double f0, double gainDb)
{
    double A = pow(10, gainDb / 40), w = 2 * M_PI * f0 / OUT_RATE, cw = cos(w), sw = sin(w);
    double al = sw / 2 * sqrt(2.0), b0, b1, b2, a0, a1, a2, sq = 2 * sqrt(A) * al;
    if (!high)
    {
        b0 = A * ((A + 1) - (A - 1) * cw + sq); b1 = 2 * A * ((A - 1) - (A + 1) * cw); b2 = A * ((A + 1) - (A - 1) * cw - sq);
        a0 = (A + 1) + (A - 1) * cw + sq; a1 = -2 * ((A - 1) + (A + 1) * cw); a2 = (A + 1) + (A - 1) * cw - sq;
    }
    else
    {
        b0 = A * ((A + 1) + (A - 1) * cw + sq); b1 = -2 * A * ((A - 1) + (A + 1) * cw); b2 = A * ((A + 1) + (A - 1) * cw - sq);
        a0 = (A + 1) - (A - 1) * cw + sq; a1 = 2 * ((A - 1) - (A + 1) * cw); a2 = (A + 1) - (A - 1) * cw - sq;
    }
    q->b0 = b0 / a0; q->b1 = b1 / a0; q->b2 = b2 / a0; q->a1 = a1 / a0; q->a2 = a2 / a0;
}
static inline float Biq(struct Biquad *q, int ch, float x)
{
    float y = q->b0 * x + q->z1[ch];
    q->z1[ch] = q->b1 * x - q->a1 * y + q->z2[ch];
    q->z2[ch] = q->b2 * x - q->a2 * y;
    return y;
}
static inline float SoftClip(float x)
{
    // Linear up to 0.8 of full scale, then a smooth knee into the ceiling.
    float a = fabsf(x);
    if (a <= 0.8f) return x;
    a = 0.8f + 0.2f * tanhf((a - 0.8f) / 0.2f);
    return x < 0 ? -a : a;
}

void M4aPcSetHdAudio(int on) { gPcHdAudio = on; }

// SoundMain: called from the game's VBlank handler.

void SoundMain(void)
{
    struct SoundInfo *si = SOUND_INFO_PTR;
    int n, i;

    if (si->ident != ID_NUMBER)
        return;
    si->ident++;

    if (si->MPlayMainHead)
        si->MPlayMainHead(si->musicPlayerHead);
    si->CgbSound();

    sSampleAcc += OUT_RATE / sFps;
    n = (int)sSampleAcc;
    sSampleAcc -= n;
    if (n > MAX_FRAME_SAMPLES)
        n = MAX_FRAME_SAMPLES;

    // Reverb: feed back the previous frame, as the GBA mixer does with its
    // double-buffered PCM output.
    if (si->reverb && !gPcHdAudio)
    {
        float r = si->reverb / 512.0f;
        for (i = 0; i < n; i++)
            sMixL[i] = sMixR[i] = (sPrevL[i] + sPrevR[i]) * 2 * r;
    }
    else
    {
        memset(sMixL, 0, n * sizeof(float));
        memset(sMixR, 0, n * sizeof(float));
    }

    MixDirectSound(si, n);
    memcpy(sPrevL, sMixL, n * sizeof(float));
    memcpy(sPrevR, sMixR, n * sizeof(float));

    PsgLatch();
    {
        // PSG is mixed separately so it doesn't feed the Direct Sound reverb.
        float dsL[MAX_FRAME_SAMPLES], dsR[MAX_FRAME_SAMPLES];
        memcpy(dsL, sMixL, n * sizeof(float));
        memcpy(dsR, sMixR, n * sizeof(float));
        memset(sMixL, 0, n * sizeof(float));
        memset(sMixR, 0, n * sizeof(float));
        MixPsg(n);
        if (gPcHdAudio)
        {
            static int init;
            float wet = 0.10f + (si->reverb & 0x7F) / 127.0f * 0.14f;
            if (!init)
            {
                ShelfInit(&sLowShelf, 0, 140, 2.0);
                ShelfInit(&sHighShelf, 1, 7000, 2.0);
                init = 1;
            }
            for (i = 0; i < n; i++)
            {
                float l = dsL[i] * 4.0f + sMixL[i] * 4.0f;
                float r = dsR[i] * 4.0f + sMixR[i] * 4.0f;
                static float hp, hpx;
                float rin = (l + r) * 0.5f * 0.015f;
                hp = 0.974f * (hp + rin - hpx); hpx = rin;   // keep bass out of the reverb (~200 Hz high-pass)
                rin = hp;
                float m, sd;
                l += Reverb(0, rin) * wet * 4.5f;
                r += Reverb(1, rin) * wet * 4.5f;
                m = (l + r) * 0.5f; sd = (l - r) * 0.5f * 1.2f;   // a little wider
                l = m + sd; r = m - sd;
                l = Biq(&sHighShelf, 0, Biq(&sLowShelf, 0, l));
                r = Biq(&sHighShelf, 1, Biq(&sLowShelf, 1, r));
                sOut[i * 2] = (s16)(SoftClip(l * 48.0f / 32768.0f) * 32767.0f);
                sOut[i * 2 + 1] = (s16)(SoftClip(r * 48.0f / 32768.0f) * 32767.0f);
            }
            FrontendAudio(sOut, n);
            si->ident = ID_NUMBER;
            return;
        }
        for (i = 0; i < n; i++)
        {
            // Direct Sound: s8 units * 4 (100% volume) -> 10-bit; PSG already 10-bit-ish.
            float l = dsL[i] * 4.0f + sMixL[i] * 4.0f;
            float r = dsR[i] * 4.0f + sMixR[i] * 4.0f;
            s32 L = (s32)(l * 48.0f), R = (s32)(r * 48.0f);
            if (L > 32767) L = 32767; else if (L < -32768) L = -32768;
            if (R > 32767) R = 32767; else if (R < -32768) R = -32768;
            sOut[i * 2] = L;
            sOut[i * 2 + 1] = R;
        }
    }
    FrontendAudio(sOut, n);

    si->ident = ID_NUMBER;
}

// The game copies SoundMainRAM into IWRAM; on PC it is just inert bytes.
char SoundMainRAM[0x800];
