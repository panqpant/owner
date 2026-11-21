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

void TestHookRun(const char *cmd)
{
    char name[32];
    int a = 0, b = 0, c = 0, d = 0;

    if (sscanf(cmd, "%31s %i %i %i %i", name, &a, &b, &c, &d) < 1)
        return;

    if (!strcmp(name, "givemon"))
    {
        ScriptGiveMon(a, b ? b : 5, ITEM_NONE, 0, 0, 0);
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
    else
    {
        fprintf(stderr, "unknown test hook: %s\n", cmd);
    }
}
