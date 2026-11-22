// Wonder Trade replica, game side. Generates the "trade partner" and the
// Pokémon they send, then runs the game's own in-game trade scene.
//
// The odds are a model of what people actually dumped on Wonder Trade in
// X/Y and Omega Ruby/Alpha Sapphire (from community reports, not official
// data): mostly level-1 breeding leftovers with good IVs and egg moves, lots
// of freshly caught route Pokémon, starters, some trained and competitive
// Pokémon, foreign high-IV Dittos, the odd legendary, and a shiny rate well
// above the wild one because breeders gave away spare shinies.
// Limited to the 386 species Emerald knows.
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>
#include "global.h"
#include "main.h"
#include "pokemon.h"
#include "data.h"
#include "event_data.h"
#include "script.h"
#include "task.h"
#include "palette.h"
#include "overworld.h"
#include "field_screen_effect.h"
#include "field_weather.h"
#include "item.h"
#include "constants/items.h"
#include "constants/characters.h"
#include "constants/abilities.h"
#include "string_util.h"
#include "constants/species.h"
#include "constants/moves.h"
#include "constants/region_map_sections.h"
#include "wondertrade.h"

struct PcWt gPcWt = { .offerSlot = -1 };
int gPcWonderTradeActive;
bool8 ArePlayerFieldControlsLocked(void);   // game script.h (pc/script.h shadows it)
void LockPlayerFieldControls(void);
void UnlockPlayerFieldControls(void);
void DoInGameTradeScene(void);
extern const u16 gEggMoves[];
extern const u8 *const gNatureNamePointers[];

// ---- Random numbers (independent of the game's RNG) ----
static u32 sWtRng;
static u32 R32(void)
{
    sWtRng ^= sWtRng << 13; sWtRng ^= sWtRng >> 17; sWtRng ^= sWtRng << 5;
    return sWtRng;
}
static int Rn(int n) { return (int)(R32() % (u32)n); }
static int Chance(int num, int den) { return Rn(den) < num; }

// ---- Species pools (national dex numbers) ----
static const u16 kBreeders[] = { 1, 4, 7, 152, 155, 158, 252, 255, 258, 133, 147, 246, 371, 280, 349, 175, 63, 92, 66, 74,
    129, 138, 140, 142, 173, 172, 174, 236, 238, 239, 240, 216, 228, 302, 303, 304, 328, 333, 343, 345, 347, 353, 355, 359,
    361, 363, 366, 370, 293, 296, 298, 300, 315, 318, 320, 322, 325, 327, 331, 41, 60, 95, 123, 127, 131, 143, 113, 79, 104,
    111, 116, 120, 214, 227, 231, 234, 241, 37, 58, 25, 35, 39, 52, 77, 83, 84, 86, 90, 96, 102, 108, 115, 128, 200, 215, 225 };
static const u16 kCommon[] = { 16, 19, 10, 13, 21, 29, 32, 41, 43, 46, 48, 52, 54, 56, 60, 69, 72, 74, 77, 79, 81, 84, 86, 92,
    96, 98, 100, 102, 109, 114, 116, 118, 120, 129, 161, 163, 165, 167, 170, 177, 179, 183, 187, 190, 191, 193, 194, 198,
    200, 204, 206, 207, 209, 211, 213, 216, 218, 220, 222, 223, 225, 226, 261, 263, 265, 270, 273, 276, 278, 280, 283, 285,
    287, 290, 293, 296, 299, 300, 302, 303, 304, 307, 309, 311, 312, 313, 314, 316, 318, 320, 322, 324, 325, 327, 328, 331,
    333, 335, 336, 337, 338, 339, 341, 343, 345, 347, 349, 351, 352, 353, 355, 357, 358, 359, 361, 363, 366, 369, 370 };
static const u16 kEvolved[] = { 3, 6, 9, 18, 20, 22, 24, 26, 28, 31, 34, 36, 38, 40, 42, 45, 47, 49, 51, 53, 55, 57, 59, 62,
    65, 68, 71, 73, 76, 78, 80, 82, 85, 87, 89, 91, 94, 97, 99, 101, 103, 105, 106, 107, 110, 112, 115, 119, 121, 122, 124,
    125, 126, 128, 130, 131, 134, 135, 136, 139, 141, 142, 143, 149, 154, 157, 160, 162, 164, 166, 168, 169, 171, 178, 181,
    182, 184, 185, 186, 189, 195, 196, 197, 199, 202, 203, 205, 208, 210, 212, 214, 217, 219, 221, 224, 226, 227, 229, 230,
    232, 233, 237, 241, 242, 248, 254, 257, 260, 262, 264, 267, 269, 272, 275, 277, 279, 282, 284, 286, 289, 291, 292, 295,
    297, 301, 305, 306, 308, 310, 317, 319, 321, 323, 326, 330, 332, 334, 340, 342, 344, 346, 348, 350, 354, 356, 362, 365,
    367, 368, 373, 376 };
static const u16 kCompetitive[] = { 130, 149, 248, 373, 376, 94, 65, 143, 242, 113, 227, 212, 260, 254, 257, 282, 286, 289, 306,
    334, 350, 359, 362, 365, 330, 6, 9, 3, 59, 121, 135, 197, 196, 169, 232, 214, 229, 230, 68, 76, 91, 103, 112, 131, 141, 186 };
static const u16 kLegends[] = { 144, 145, 146, 150, 151, 243, 244, 245, 249, 250, 251, 377, 378, 379, 380, 381, 382, 383, 384,
    385, 386, 380, 381, 384, 150, 249, 250 };   // the popular ones twice
static const u16 kStarters[] = { 1, 4, 7, 152, 155, 158, 252, 255, 258 };
#define PICK(a) (a[Rn(ARRAY_COUNT(a))])

// ---- Partners ----
static const char *const kNames[] = { "Alex", "Lukas", "Mateo", "Sofia", "Emma", "Noah", "Lucas", "Leon", "Hugo", "Elias",
    "Marie", "Chloe", "Liam", "Mia", "Jonas", "Finn", "Nico", "Paul", "Ana", "Marco", "Luca", "Giulia", "Pablo", "Lucia",
    "Sven", "Erik", "Kenji", "Haruto", "Ren", "Sora", "Minh", "Jin", "Arjun", "Ravi", "Omar", "Leila", "Zoe", "Ella", "Jack",
    "Ben", "Sam", "Kai", "Tom", "Max", "Felix", "Jules", "Ines", "Diego", "Carla", "Mats", "Lea", "Nina", "Theo", "Oscar",
    "Josh07", "Dan", "Kevin", "Ryan", "Tyler", "Brandon", "Kayla", "Jess", "Aiden", "Ethan", "Mason", "Owen", "Ruby", "Lily",
    "Hana", "Yuki", "Aoi", "Riku", "Daichi", "Mei", "Wei", "Jun", "Seo", "Minji", "Tomas", "Matti", "Aleks", "Pedro", "Joao",
    "Bruno", "Rafa", "Iker", "Unai", "Marta", "Elena", "Ola", "Piotr", "Kasia", "Lars", "Nils", "Freja", "Aksel", "Emil",
    "Ash", "Brock", "Misty", "Gary", "Joey", "Dawn", "Calem", "Serena", "Shauna", "Tierno", "Trevor", "Ruby", "Sapph" };
static const struct { const char *country; u8 language; } kCountries[] = {
    { "United States", LANGUAGE_ENGLISH }, { "United States", LANGUAGE_ENGLISH }, { "United States", LANGUAGE_ENGLISH },
    { "United Kingdom", LANGUAGE_ENGLISH }, { "Canada", LANGUAGE_ENGLISH }, { "Australia", LANGUAGE_ENGLISH },
    { "Ireland", LANGUAGE_ENGLISH }, { "New Zealand", LANGUAGE_ENGLISH }, { "France", LANGUAGE_FRENCH },
    { "France", LANGUAGE_FRENCH }, { "Belgium", LANGUAGE_FRENCH }, { "Germany", LANGUAGE_GERMAN }, { "Germany", LANGUAGE_GERMAN },
    { "Austria", LANGUAGE_GERMAN }, { "Switzerland", LANGUAGE_GERMAN }, { "Spain", LANGUAGE_SPANISH }, { "Mexico", LANGUAGE_SPANISH },
    { "Argentina", LANGUAGE_SPANISH }, { "Chile", LANGUAGE_SPANISH }, { "Italy", LANGUAGE_ITALIAN }, { "Italy", LANGUAGE_ITALIAN },
    { "Japan", LANGUAGE_ENGLISH }, { "Japan", LANGUAGE_ENGLISH }, { "South Korea", LANGUAGE_ENGLISH }, { "Taiwan", LANGUAGE_ENGLISH },
    { "Hong Kong", LANGUAGE_ENGLISH }, { "Netherlands", LANGUAGE_ENGLISH }, { "Sweden", LANGUAGE_ENGLISH }, { "Norway", LANGUAGE_ENGLISH },
    { "Denmark", LANGUAGE_ENGLISH }, { "Finland", LANGUAGE_ENGLISH }, { "Poland", LANGUAGE_ENGLISH }, { "Portugal", LANGUAGE_SPANISH },
    { "Brazil", LANGUAGE_SPANISH }, { "Singapore", LANGUAGE_ENGLISH }, { "Philippines", LANGUAGE_ENGLISH } };
static const char *const kNicknames[] = { "Sparky", "Lucky", "Blaze", "Fluffy", "Bubbles", "Shadow", "Rocky", "Bob", "Nugget",
    "Mochi", "Kevin", "Spike", "Flare", "Ziggy", "Dave", "Bean", "Thor", "Zeus", "Momo", "Taco", "Pepper", "Biscuit", "Waffles",
    "Toast", "Noodle", "Chaos", "Steve", "Jeff", "Dinky", "Gary", "Chonk", "Bolt", "Fang", "Pebble", "Ember", "Frosty", "Tank",
    "Ace", "Duke", "Luna", "Nova", "Star", "Coco", "Peanut", "Gizmo", "Rex", "Turbo", "Smol", "Boi", "Wonder", "Trade",
    "GiftForU", "Enjoy", "HaveFun", "FreeMon", "PkmnGO", "Breedjec", "Reject", "Spare", "Extra" };
static const u16 kItems[] = { ITEM_ORAN_BERRY, ITEM_SITRUS_BERRY, ITEM_LUM_BERRY, ITEM_LEFTOVERS, ITEM_EVERSTONE, ITEM_LUCKY_EGG,
    ITEM_EXP_SHARE, ITEM_SOOTHE_BELL, ITEM_CHOICE_BAND, ITEM_FOCUS_BAND, ITEM_NUGGET, ITEM_RARE_CANDY };
static const u16 kBalls[] = { ITEM_POKE_BALL, ITEM_POKE_BALL, ITEM_POKE_BALL, ITEM_GREAT_BALL, ITEM_ULTRA_BALL, ITEM_ULTRA_BALL,
    ITEM_PREMIER_BALL, ITEM_LUXURY_BALL, ITEM_NET_BALL, ITEM_DIVE_BALL, ITEM_NEST_BALL, ITEM_REPEAT_BALL, ITEM_TIMER_BALL };
static const u8 kGoodNatures[] = { 3 /* Adamant */, 13 /* Jolly */, 15 /* Modest */, 10 /* Timid */, 5 /* Bold */, 20 /* Calm */,
    8 /* Impish */, 23 /* Careful */, 2 /* Brave */, 17 /* Quiet */ };

static void ToGame(u8 *dst, const char *src, int max)
{
    int i;
    for (i = 0; src[i] && i < max; i++)
    {
        char ch = src[i];
        if (ch >= 'A' && ch <= 'Z') dst[i] = CHAR_A + (ch - 'A');
        else if (ch >= 'a' && ch <= 'z') dst[i] = CHAR_a + (ch - 'a');
        else if (ch >= '0' && ch <= '9') dst[i] = CHAR_0 + (ch - '0');
        else dst[i] = CHAR_SPACE;
    }
    dst[i] = EOS;
}
static void ToAscii(char *dst, const u8 *src, int max)
{
    int i;
    for (i = 0; src[i] != EOS && i < max - 1; i++)
    {
        u8 c = src[i];
        if (c >= CHAR_A && c < CHAR_A + 26) dst[i] = 'A' + (c - CHAR_A);
        else if (c >= CHAR_a && c < CHAR_a + 26) dst[i] = 'a' + (c - CHAR_a);
        else if (c >= CHAR_0 && c < CHAR_0 + 10) dst[i] = '0' + (c - CHAR_0);
        else if (c == CHAR_PERIOD) dst[i] = '.';
        else if (c == CHAR_HYPHEN) dst[i] = '-';
        else if (c == 0xB4) dst[i] = '\'';
        else dst[i] = ' ';
    }
    dst[i] = 0;
}

// Up to two egg moves for a species (taught over the default moveset).
static void GiveEggMoves(struct Pokemon *mon, u16 species, int count)
{
    u16 list[16];
    int n = 0, i;
    for (i = 0; gEggMoves[i] != 0xFFFF; i++)
        if (gEggMoves[i] == species + 20000)
        {
            for (i++; gEggMoves[i] < 20000 && gEggMoves[i] != 0xFFFF && n < 16; i++)
                list[n++] = gEggMoves[i];
            break;
        }
    for (i = 0; i < count && n > 0; i++)
    {
        int k = Rn(n);
        u16 mv = list[k];
        list[k] = list[--n];
        if (GiveMoveToMon(mon, mv) == 0xFFFF)   // MON_HAS_MAX_MOVES: replace a random slot
            SetMonMoveSlot(mon, mv, Rn(MAX_MON_MOVES));
    }
}

static void MakeReceivedMon(struct Pokemon *mon)
{
    int kind = Rn(1000), dex, level, i, shinyDen, perfectChance, natureGood = 0, ivs[NUM_STATS];
    u16 species;
    u32 otId = R32(), pid;
    const char *who = kNames[Rn(ARRAY_COUNT(kNames))];
    int c = Rn(ARRAY_COUNT(kCountries));
    u8 lang = kCountries[c].language, name[12], gender = Rn(2);
    const char *category;

    // Category weights (out of 1000).
    if (kind < 330)      { category = "breeding"; dex = PICK(kBreeders); level = 1; shinyDen = 140; perfectChance = 55; natureGood = 70; }
    else if (kind < 610) { category = "caught"; dex = Chance(1, 8) ? 1 + Rn(386) : PICK(kCommon); level = 2 + Rn(Chance(1, 3) ? 40 : 20); shinyDen = 4096; perfectChance = 0; }
    else if (kind < 760) { category = "trained"; dex = PICK(kEvolved); level = 20 + Rn(55); shinyDen = 1024; perfectChance = 10; natureGood = 25; }
    else if (kind < 840) { category = "starter"; dex = PICK(kStarters); level = Chance(1, 2) ? 1 : 5 + Rn(40); shinyDen = 200; perfectChance = 35; natureGood = 50; }
    else if (kind < 910) { category = "competitive"; dex = PICK(kCompetitive); level = Chance(7, 10) ? 50 : 100; shinyDen = 60; perfectChance = 80; natureGood = 95; }
    else if (kind < 945) { category = "ditto"; dex = 132; level = 1 + Rn(70); shinyDen = 64; perfectChance = 85; natureGood = 40; }
    else if (kind < 985) { category = "legend"; dex = PICK(kLegends); level = Chance(1, 3) ? 100 : Chance(1, 2) ? 70 : 40 + Rn(20); shinyDen = 16; perfectChance = 45; natureGood = 50; }
    else                 { category = "jackpot"; dex = Chance(1, 2) ? PICK(kStarters) : PICK(kCompetitive); level = 1; shinyDen = 1; perfectChance = 100; natureGood = 100; }
    if (dex > 386 || dex < 1) dex = 1;
    species = NationalPokedexNumToSpecies(dex);
    if (level > MAX_LEVEL) level = MAX_LEVEL;

    // Personality: nature, shininess (Gen 3 rule: tid ^ sid ^ pid halves < 8).
    pid = R32();
    if (natureGood && Chance(natureGood, 100))
    {
        u8 want = kGoodNatures[Rn(ARRAY_COUNT(kGoodNatures))];
        pid = pid - (pid % NUM_NATURES) + want;
    }
    if (Chance(1, shinyDen))
    {
        u16 lo = pid & 0xFFFF;
        u16 hi = (u16)((otId >> 16) ^ (otId & 0xFFFF) ^ lo ^ Rn(8));
        u32 nat = pid % NUM_NATURES;
        pid = ((u32)hi << 16) | lo;
        // Keep the nature if possible by trying nearby low halves.
        for (i = 0; i < 4096 && pid % NUM_NATURES != nat; i++)
        {
            lo = (u16)(lo + 1);
            hi = (u16)((otId >> 16) ^ (otId & 0xFFFF) ^ lo ^ (hi & 7));
            pid = ((u32)hi << 16) | lo;
        }
    }
    CreateMon(mon, species, level, USE_RANDOM_IVS, TRUE, pid, OT_ID_PRESET, otId);
    for (i = 0; i < NUM_STATS; i++)
    {
        ivs[i] = Chance(perfectChance, 100) ? 31 : Rn(32);
        if (Chance(perfectChance, 100) && ivs[i] < 31) ivs[i] = 25 + Rn(7);
        SetMonData(mon, MON_DATA_HP_IV + i, &ivs[i]);
    }
    {
        u8 ab = Rn(2);
        if (gSpeciesInfo[species].abilities[1] == ABILITY_NONE) ab = 0;
        SetMonData(mon, MON_DATA_ABILITY_NUM, &ab);
    }
    // Trained and competitive Pokémon have effort values.
    if (!strcmp(category, "competitive") || !strcmp(category, "trained") || !strcmp(category, "legend"))
    {
        int a = Rn(NUM_STATS), b = (a + 1 + Rn(NUM_STATS - 1)) % NUM_STATS;
        u8 ev = !strcmp(category, "trained") ? Rn(253) : 252, ev2 = 4;
        SetMonData(mon, MON_DATA_HP_EV + a, &ev);
        if (!strcmp(category, "trained")) ev = Rn(253); else ev = 252;
        SetMonData(mon, MON_DATA_HP_EV + b, &ev);
        SetMonData(mon, MON_DATA_HP_EV + (b + 1) % NUM_STATS == a ? (b + 2) % NUM_STATS : (b + 1) % NUM_STATS, &ev2);
    }
    if (!strcmp(category, "breeding") || !strcmp(category, "starter") || !strcmp(category, "jackpot"))
        GiveEggMoves(mon, species, Chance(7, 10) ? 1 + Rn(2) : 0);
    else if (!strcmp(category, "competitive"))
        GiveEggMoves(mon, species, Rn(2));

    // Identity.
    ToGame(name, who, PLAYER_NAME_LENGTH);
    SetMonData(mon, MON_DATA_OT_NAME, name);
    SetMonData(mon, MON_DATA_OT_GENDER, &gender);
    SetMonData(mon, MON_DATA_LANGUAGE, &lang);
    if (Chance(strcmp(category, "breeding") ? 22 : 8, 100))
    {
        ToGame(name, kNicknames[Rn(ARRAY_COUNT(kNicknames))], POKEMON_NAME_LENGTH);
        SetMonData(mon, MON_DATA_NICKNAME, name);
    }
    {
        u8 ball = kBalls[Rn(ARRAY_COUNT(kBalls))];
        u8 met = METLOC_IN_GAME_TRADE;
        if (!strcmp(category, "breeding") || !strcmp(category, "jackpot")) ball = Chance(3, 4) ? ITEM_POKE_BALL : ball;
        SetMonData(mon, MON_DATA_POKEBALL, &ball);
        SetMonData(mon, MON_DATA_MET_LOCATION, &met);
    }
    {
        u16 item = ITEM_NONE;
        if (!strcmp(category, "breeding")) item = Chance(15, 100) ? ITEM_EVERSTONE : ITEM_NONE;
        else if (!strcmp(category, "competitive")) item = Chance(70, 100) ? kItems[Rn(ARRAY_COUNT(kItems))] : ITEM_NONE;
        else if (Chance(18, 100)) item = kItems[Rn(ARRAY_COUNT(kItems))];
        if (item) SetMonData(mon, MON_DATA_HELD_ITEM, &item);
    }
    CalculateMonStats(mon);

    snprintf(gPcWt.partner, sizeof(gPcWt.partner), "%s", who);
    snprintf(gPcWt.country, sizeof(gPcWt.country), "%s", kCountries[c].country);
}

static void FillResult(void)
{
    struct Pokemon *mon = &gPlayerParty[gSpecialVar_0x8005];
    char sp[16], nick[16], nat[16], item[24];
    u8 buf[32];
    int i, ivs[NUM_STATS], perfect = 0, total = 0;
    u16 species = GetMonData(mon, MON_DATA_SPECIES), held = GetMonData(mon, MON_DATA_HELD_ITEM);
    ToAscii(sp, gSpeciesNames[species], sizeof(sp));
    GetMonData(mon, MON_DATA_NICKNAME, buf);
    ToAscii(nick, buf, sizeof(nick));
    ToAscii(nat, gNatureNamePointers[GetNature(mon)], sizeof(nat));
    for (i = 0; i < NUM_STATS; i++) { ivs[i] = GetMonData(mon, MON_DATA_HP_IV + i); perfect += ivs[i] == 31; total += ivs[i]; }
    gPcWt.shiny = IsMonShiny(mon);
    if (strcmp(nick, sp)) snprintf(gPcWt.resultLine1, sizeof(gPcWt.resultLine1), "%s%s (%s)  Lv. %d", gPcWt.shiny ? "* " : "", nick, sp, GetMonData(mon, MON_DATA_LEVEL));
    else snprintf(gPcWt.resultLine1, sizeof(gPcWt.resultLine1), "%s%s  Lv. %d", gPcWt.shiny ? "* " : "", sp, GetMonData(mon, MON_DATA_LEVEL));
    snprintf(gPcWt.resultLine2, sizeof(gPcWt.resultLine2), "%s nature   IVs %d/%d/%d/%d/%d/%d (%d perfect)", nat,
             ivs[0], ivs[1], ivs[2], ivs[3], ivs[4], ivs[5], perfect);
    item[0] = 0;
    if (held) ToAscii(item, GetItemName(held), sizeof(item));
    snprintf(gPcWt.resultLine3, sizeof(gPcWt.resultLine3), "From %s in %s%s%s", gPcWt.partner, gPcWt.country, held ? "   holding " : "", item);
}

// After the trade scene: back on the field, fade in, give control back.
static void Task_WtFadeIn(u8 taskId)
{
    if (!gPaletteFade.active)
    {
        DestroyTask(taskId);
        UnlockPlayerFieldControls();
        FillResult();
        gPcWt.busy = 0;
        gPcWt.done = 1;
        gPcWonderTradeActive = 0;
    }
}
void PcWonderTradeFieldCB(void)
{
    LockPlayerFieldControls();
    Overworld_PlaySpecialMapMusic();
    FadeInFromBlack();
    CreateTask(Task_WtFadeIn, 10);
}

void PcWonderTradeUpdate(void)
{
    struct PcWt *w = &gPcWt;
    int i, usable = 0;
    if (!sWtRng)
        sWtRng = (u32)time(NULL) * 2654435761u ^ 0x9E3779B9u;
    R32();   // keep the stream moving with play time
    {
        void PcWonderTradeStats(void);
        PcWonderTradeStats();
    }
    w->count = gPlayerPartyCount;
    for (i = 0; i < PARTY_SIZE; i++)
    {
        u8 buf[POKEMON_NAME_LENGTH + 2];
        w->egg[i] = i < gPlayerPartyCount && GetMonData(&gPlayerParty[i], MON_DATA_IS_EGG);
        w->level[i] = i < gPlayerPartyCount ? GetMonData(&gPlayerParty[i], MON_DATA_LEVEL) : 0;
        if (i < gPlayerPartyCount) { GetMonData(&gPlayerParty[i], MON_DATA_NICKNAME, buf); ToAscii(w->name[i], buf, sizeof(w->name[i])); }
        if (i < gPlayerPartyCount && !w->egg[i] && GetMonData(&gPlayerParty[i], MON_DATA_HP) > 0) usable++;
    }
    w->usable = usable;
    w->canOpen = !w->busy && !ArePlayerFieldControlsLocked() && gPlayerPartyCount > 0;

    if (w->offerSlot >= 0 && !w->found && !w->busy)
    {
        MakeReceivedMon(&gEnemyParty[0]);
        w->found = 1;
    }
    if (w->go && w->found && !w->busy && !ArePlayerFieldControlsLocked())
    {
        w->go = 0;
        w->found = 0;
        gSpecialVar_0x8005 = w->offerSlot;
        w->offerSlot = -1;
        w->busy = 1;
        gPcWonderTradeActive = 1;
        DoInGameTradeScene();
    }
}

// Testing: EMERALD_WT_STATS=n prints statistics over n generated trades.
void PcWonderTradeStats(void)
{
    static int done;
    int n, i, shiny = 0, lv1 = 0, lv100 = 0, legend = 0, perfect5 = 0, nick = 0, item = 0, distinct = 0;
    static u8 seen[NUM_SPECIES];
    struct Pokemon mon;
    if (done || !getenv("EMERALD_WT_STATS")) return;
    done = 1;
    n = atoi(getenv("EMERALD_WT_STATS"));
    if (!sWtRng) sWtRng = (u32)time(NULL) * 2654435761u ^ 0x9E3779B9u;
    for (i = 0; i < n; i++)
    {
        int k, p = 0, dex;
        u8 buf[16], sp[16];
        MakeReceivedMon(&mon);
        if (IsMonShiny(&mon)) shiny++;
        k = GetMonData(&mon, MON_DATA_LEVEL);
        lv1 += k == 1; lv100 += k == 100;
        dex = SpeciesToNationalPokedexNum(GetMonData(&mon, MON_DATA_SPECIES));
        legend += (dex >= 144 && dex <= 146) || dex == 150 || dex == 151 || (dex >= 243 && dex <= 245) || (dex >= 249 && dex <= 251) || dex >= 377;
        for (k = 0; k < NUM_STATS; k++) p += GetMonData(&mon, MON_DATA_HP_IV + k) == 31;
        perfect5 += p >= 5;
        GetMonData(&mon, MON_DATA_NICKNAME, buf);
        StringCopy(sp, gSpeciesNames[GetMonData(&mon, MON_DATA_SPECIES)]);
        nick += StringCompare(buf, sp) != 0;
        item += GetMonData(&mon, MON_DATA_HELD_ITEM) != 0;
        if (!seen[GetMonData(&mon, MON_DATA_SPECIES)]++) distinct++;
    }
    fprintf(stderr, "WTSTATS n=%d shiny=%d (1 in %.0f) level1=%.1f%% level100=%.1f%% legendary=%.1f%% 5+perfectIVs=%.1f%% nicknamed=%.1f%% item=%.1f%% species=%d\n",
            n, shiny, shiny ? (double)n / shiny : 0.0, lv1 * 100.0 / n, lv100 * 100.0 / n, legend * 100.0 / n, perfect5 * 100.0 / n, nick * 100.0 / n, item * 100.0 / n, distinct);
}
