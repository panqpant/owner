// Generated from sound/direct_sound_data.inc: melodic instrument samples
// that the HD audio replaces with synthesised voices.
enum { SYN_NONE, SYN_STRINGS, SYN_BRASS, SYN_PIANO, SYN_ORGAN, SYN_WIND, SYN_BASS, SYN_CHOIR };
extern const struct WaveData DirectSoundWaveData_classical_choir_voice_ahhs;
extern const struct WaveData DirectSoundWaveData_sc88pro_accordion;
extern const struct WaveData DirectSoundWaveData_sc88pro_accordion_duplicate;
extern const struct WaveData DirectSoundWaveData_sc88pro_church_organ3_high;
extern const struct WaveData DirectSoundWaveData_sc88pro_church_organ3_low;
extern const struct WaveData DirectSoundWaveData_sc88pro_fingered_bass;
extern const struct WaveData DirectSoundWaveData_sc88pro_flute;
extern const struct WaveData DirectSoundWaveData_sc88pro_french_horn_60;
extern const struct WaveData DirectSoundWaveData_sc88pro_french_horn_72;
extern const struct WaveData DirectSoundWaveData_sc88pro_fretless_bass;
extern const struct WaveData DirectSoundWaveData_sc88pro_organ2;
extern const struct WaveData DirectSoundWaveData_sc88pro_piano1_48;
extern const struct WaveData DirectSoundWaveData_sc88pro_piano1_60;
extern const struct WaveData DirectSoundWaveData_sc88pro_piano1_72;
extern const struct WaveData DirectSoundWaveData_sc88pro_piano1_84;
extern const struct WaveData DirectSoundWaveData_sc88pro_string_ensemble_60;
extern const struct WaveData DirectSoundWaveData_sc88pro_string_ensemble_72;
extern const struct WaveData DirectSoundWaveData_sc88pro_string_ensemble_84;
extern const struct WaveData DirectSoundWaveData_sc88pro_synth_bass;
extern const struct WaveData DirectSoundWaveData_sc88pro_trumpet_60;
extern const struct WaveData DirectSoundWaveData_sc88pro_trumpet_72;
extern const struct WaveData DirectSoundWaveData_sc88pro_trumpet_84;
extern const struct WaveData DirectSoundWaveData_sc88pro_tuba_39;
extern const struct WaveData DirectSoundWaveData_sc88pro_tuba_51;
extern const struct WaveData DirectSoundWaveData_sd90_classical_oboe;
extern const struct WaveData DirectSoundWaveData_sd90_classical_shakuhachi;
extern const struct WaveData DirectSoundWaveData_sd90_classical_whistle;
extern const struct WaveData DirectSoundWaveData_steinway_b_piano;
static const struct { const struct WaveData *wav; int kind; } sSynthInstruments[] = {
    { &DirectSoundWaveData_classical_choir_voice_ahhs, SYN_CHOIR },
    { &DirectSoundWaveData_sc88pro_accordion, SYN_ORGAN },
    { &DirectSoundWaveData_sc88pro_accordion_duplicate, SYN_ORGAN },
    { &DirectSoundWaveData_sc88pro_church_organ3_high, SYN_ORGAN },
    { &DirectSoundWaveData_sc88pro_church_organ3_low, SYN_ORGAN },
    { &DirectSoundWaveData_sc88pro_fingered_bass, SYN_BASS },
    { &DirectSoundWaveData_sc88pro_flute, SYN_WIND },
    { &DirectSoundWaveData_sc88pro_french_horn_60, SYN_BRASS },
    { &DirectSoundWaveData_sc88pro_french_horn_72, SYN_BRASS },
    { &DirectSoundWaveData_sc88pro_fretless_bass, SYN_BASS },
    { &DirectSoundWaveData_sc88pro_organ2, SYN_ORGAN },
    { &DirectSoundWaveData_sc88pro_piano1_48, SYN_PIANO },
    { &DirectSoundWaveData_sc88pro_piano1_60, SYN_PIANO },
    { &DirectSoundWaveData_sc88pro_piano1_72, SYN_PIANO },
    { &DirectSoundWaveData_sc88pro_piano1_84, SYN_PIANO },
    { &DirectSoundWaveData_sc88pro_string_ensemble_60, SYN_STRINGS },
    { &DirectSoundWaveData_sc88pro_string_ensemble_72, SYN_STRINGS },
    { &DirectSoundWaveData_sc88pro_string_ensemble_84, SYN_STRINGS },
    { &DirectSoundWaveData_sc88pro_synth_bass, SYN_BASS },
    { &DirectSoundWaveData_sc88pro_trumpet_60, SYN_BRASS },
    { &DirectSoundWaveData_sc88pro_trumpet_72, SYN_BRASS },
    { &DirectSoundWaveData_sc88pro_trumpet_84, SYN_BRASS },
    { &DirectSoundWaveData_sc88pro_tuba_39, SYN_BRASS },
    { &DirectSoundWaveData_sc88pro_tuba_51, SYN_BRASS },
    { &DirectSoundWaveData_sd90_classical_oboe, SYN_WIND },
    { &DirectSoundWaveData_sd90_classical_shakuhachi, SYN_WIND },
    { &DirectSoundWaveData_sd90_classical_whistle, SYN_WIND },
    { &DirectSoundWaveData_steinway_b_piano, SYN_PIANO },
};
