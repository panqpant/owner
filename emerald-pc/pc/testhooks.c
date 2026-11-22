// Test hooks for the headless runner: lets a script jump straight to game
// situations (battles, maps) instead of playing there by hand. Compiled with
// the game's headers so it can call game functions directly.
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "global.h"
#include "main.h"
#include "pokemon.h"
#include "battle_setup.h"
#include "overworld.h"
#include "script_pokemon_util.h"
#include "constants/items.h"
#include "field_screen_effect.h"
#include "field_weather.h"
#include "event_data.h"
#include "event_object_movement.h"
#include "field_player_avatar.h"

void TestHookRun(const char *cmd)
{
    char name[32];
    int a = 0, b = 0, c = 0, d = 0;

    if (sscanf(cmd, "%31s %i %i %i %i", name, &a, &b, &c, &d) < 1)
        return;

    if (!strcmp(name, "givemon"))
    {
        ScriptGiveMon(a, b ? b : 5, ITEM_NONE, 0, 0, 0);
        FlagSet(FLAG_SYS_POKEMON_GET);   // start menu shows POKéMON
        FlagSet(FLAG_SYS_POKEDEX_GET);   // and POKéDEX
    }
    else if (!strcmp(name, "battle"))
    {
        if (gPlayerPartyCount == 0)
            ScriptGiveMon(SPECIES_TREECKO, 5, ITEM_NONE, 0, 0, 0);
        CreateMon(&gEnemyParty[0], a, b ? b : 5, USE_RANDOM_IVS, 0, 0, OT_ID_PLAYER_ID, 0);
        BattleSetup_StartScriptedWildBattle();
    }
    else if (!strcmp(name, "warp"))
    {
        // warp MAPGROUP MAPNUM X Y
        SetWarpDestination(a, b, WARP_ID_NONE, c, d);
        DoWarp();
        ResetInitialPlayerAvatarState();
    }
    else if (!strcmp(name, "capture"))
    {
        char path[512];
        extern void PpuRequestCapture(const char *path);
        if (sscanf(cmd, "%*s %511s", path) == 1)
            PpuRequestCapture(path);
    }
    else if (!strcmp(name, "pc"))
    {
        void ShowPokemonStorageSystemPC(void);
        ShowPokemonStorageSystemPC();   // the PC's box menu, as from a Pokémon Center PC
    }
    else if (!strcmp(name, "flag"))
    {
        fprintf(stderr, "[test] flag 0x%X = %d\n", a, FlagGet(a));
    }
    else if (!strcmp(name, "setflag"))
    {
        // setflag N [0]: set (or with 0, clear) a flag
        if (sscanf(cmd, "%*s %i %i", &a, &b) == 2 && b == 0) FlagClear(a); else FlagSet(a);
    }
    else if (!strcmp(name, "pos"))
    {
        struct ObjectEvent *o = &gObjectEvents[gPlayerAvatar.objectEventId];
        fprintf(stderr, "[test] pos %d,%d\n", o->currentCoords.x, o->currentCoords.y);
    }
    else if (!strcmp(name, "trainer"))
    {
        // trainer ID: start that trainer's battle here (as a trainer script would)
        extern u16 gTrainerBattleOpponent_A;
        void BattleSetup_StartTrainerBattle(void);
        if (gPlayerPartyCount == 0)
            ScriptGiveMon(SPECIES_TREECKO, 5, ITEM_NONE, 0, 0, 0);
        gTrainerBattleOpponent_A = a;
        BattleSetup_StartTrainerBattle();
    }
    else if (!strcmp(name, "hp"))
    {
        // hp SLOT VALUE: set a party Pokémon's HP (0 faints it)
        u16 hp = b;
        if (a >= 0 && a < PARTY_SIZE)
            SetMonData(&gPlayerParty[a], MON_DATA_HP, &hp);
    }
    else if (!strcmp(name, "map"))
    {
        extern int gPcMapRequest;
        gPcMapRequest = 1;   // as the map button does
    }
    else if (!strcmp(name, "weather"))
    {
        SetCurrentAndNextWeatherNoDelay(a);
    }
    else if (!strcmp(name, "warpto"))
    {
        // warpto MAPGROUP MAPNUM: arrive at the map's first warp point
        fprintf(stderr, "[test] warp %d.%d\n", a, b);
        SetWarpDestinationToMapWarp(a, b, 0);
        DoWarp();
        ResetInitialPlayerAvatarState();
    }
    else
    {
        fprintf(stderr, "unknown test hook: %s\n", cmd);
    }
}
