#include <math.h>
#include <stdio.h>
// Overworld lighting data for the renderer: light sources (building doors)
// and character positions (for soft shadows), in GBA screen coordinates.
// Called once per overworld frame. Compiled with the game's headers.
#include <stdlib.h>
#include "global.h"
#include "event_object_movement.h"
#include "field_camera.h"
#include "fieldmap.h"
#include "overworld.h"
#include "sprite.h"
#include "field_weather.h"
#include "port.h"
#include "window.h"
#include "bg.h"
#include "gpu_regs.h"
#include "party_menu.h"
#include "constants/party_menu.h"
#include "constants/moves.h"
#include "save.h"
#include "event_data.h"
#include "new_game.h"
#include "battle_pike.h"
#include "battle_pyramid.h"
#include "field_specials.h"
#include "link.h"
#include "safari_zone.h"
#include "constants/battle_pyramid.h"
#include "fieldmap.h"
#include "battle.h"
#include "palette.h"
#include "sound.h"
#include "constants/songs.h"
bool8 ArePlayerFieldControlsLocked(void);   // game script.h (pc/script.h shadows it)
void LockPlayerFieldControls(void);
#include "metatile_behavior.h"
#include "constants/weather.h"
#include "field_player_avatar.h"
#include "battle.h"
#include "battle_util.h"
#include "battle_main.h"
#include "battle_anim.h"
#include "data.h"
#include "battle_setup.h"
#include "constants/trainers.h"
#include "constants/battle.h"
#include "constants/map_types.h"
#include "pokemon.h"
#include "constants/moves.h"
#include "constants/map_groups.h"
bool8 ArePlayerFieldControlsLocked(void); // (game script.h; pc/script.h shadows it)
#include "trainer_see.h"
#include "constants/event_objects.h"
#include "constants/trainer_types.h"
#include "pokemon_icon.h"
#include "palette.h"
#include "field_camera.h"
#include "wondertrade.h"
#include "fieldfx.h"

struct PcFieldFx gPcFieldFx;
int gPcMapRequest;   // set by the frontend's map button
int gPcQuickSave;    // set by the frontend's quick-save key (F6)
struct PcAmbient gPcAmbient;
struct PcFollower gPcFollower;
struct PcBattleFx gPcBattleFx;
struct PcCine gPcCine;
int gPcHdEffects;

static int MapCineStyle(u16 id)
{
    switch (id)
    {
    case MAP_RUSTBORO_CITY_GYM: case MAP_DEWFORD_TOWN_GYM: case MAP_MAUVILLE_CITY_GYM: case MAP_LAVARIDGE_TOWN_GYM_1F:
    case MAP_PETALBURG_CITY_GYM: case MAP_FORTREE_CITY_GYM: case MAP_MOSSDEEP_CITY_GYM: case MAP_SOOTOPOLIS_CITY_GYM_1F:
    case MAP_SOOTOPOLIS_CITY_GYM_B1F:
        return CINE_GYM;
    case MAP_MT_CHIMNEY: case MAP_AQUA_HIDEOUT_B2F: case MAP_MAGMA_HIDEOUT_4F: case MAP_SLATEPORT_CITY_HARBOR:
    case MAP_ROUTE119_WEATHER_INSTITUTE_2F: case MAP_MT_PYRE_SUMMIT:
        return CINE_VILLAIN;
    case MAP_TERRA_CAVE_END:
        return CINE_LEGEND_RED;
    case MAP_SEAFLOOR_CAVERN_ROOM9: case MAP_MARINE_CAVE_END:
        return CINE_LEGEND_BLUE;
    case MAP_SKY_PILLAR_TOP:
        return CINE_LEGEND_GREEN;
    case MAP_CAVE_OF_ORIGIN_B1F: case MAP_SOOTOPOLIS_CITY:
        return gWeatherPtr->currWeather == WEATHER_DROUGHT ? CINE_LEGEND_RED
             : gWeatherPtr->currWeather == WEATHER_DOWNPOUR ? CINE_LEGEND_BLUE
             : id == MAP_SOOTOPOLIS_CITY ? CINE_STORY : CINE_ANCIENT;
    case MAP_DESERT_RUINS: case MAP_ISLAND_CAVE: case MAP_ANCIENT_TOMB:
        return CINE_ANCIENT;
    case MAP_SOUTHERN_ISLAND_INTERIOR: case MAP_FARAWAY_ISLAND_INTERIOR: case MAP_BIRTH_ISLAND_EXTERIOR:
    case MAP_NAVEL_ROCK_TOP: case MAP_NAVEL_ROCK_BOTTOM:
        return CINE_MYSTIC;
    case MAP_EVER_GRANDE_CITY_SIDNEYS_ROOM: return CINE_E4_SIDNEY;
    case MAP_EVER_GRANDE_CITY_PHOEBES_ROOM: return CINE_E4_PHOEBE;
    case MAP_EVER_GRANDE_CITY_GLACIAS_ROOM: return CINE_E4_GLACIA;
    case MAP_EVER_GRANDE_CITY_DRAKES_ROOM:  return CINE_E4_DRAKE;
    case MAP_EVER_GRANDE_CITY_CHAMPIONS_ROOM: return CINE_CHAMPION;
    case MAP_EVER_GRANDE_CITY_HALL_OF_FAME: return CINE_HALL_OF_FAME;
    }
    return CINE_NONE;
}

static void SpriteFeet(struct ObjectEvent *obj, int *x, int *y)
{
    struct Sprite *sp = &gSprites[obj->spriteId];
    *x = sp->x + sp->x2 + (sp->coordOffsetEnabled ? gSpriteCoordOffsetX : 0);
    *y = sp->y + sp->y2 + (sp->coordOffsetEnabled ? gSpriteCoordOffsetY : 0);
}

// Decide whether a cinematic moment is happening: a trainer spotting the
// player, or a cutscene (a script holds the controls while characters move
// by themselves), or anything scripted on a story map.
static void CineDebug(void);
static void PcUpdateFollower(void);
static void CineForce(void);
static int *s_cineWasLocked;
static void PcUpdateCinematic(void)
{
    struct PcCine *c = &gPcCine;
    u16 id = gSaveBlock1Ptr->location.mapNum | (gSaveBlock1Ptr->location.mapGroup << 8);
    int locked = ArePlayerFieldControlsLocked(), moving = 0, sx = 0, sy = 0, n = 0, i;
    c->mapStyle = MapCineStyle(id);
    c->want = 0;
    c->style = c->mapStyle;
    c->zoom = 1.0f;
    if (gPlayerAvatar.objectEventId < OBJECT_EVENTS_COUNT && gObjectEvents[gPlayerAvatar.objectEventId].spriteId < MAX_SPRITES)
    {
        SpriteFeet(&gObjectEvents[gPlayerAvatar.objectEventId], &sx, &sy);
        n = 1;
    }
    else
    {
        sx = 120; sy = 80; n = 1;
    }
    if (!locked)
    {
        if (s_cineWasLocked) *s_cineWasLocked = 0;
        if (c->mapStyle == CINE_HALL_OF_FAME) { c->want = 1; c->zoom = 1.04f; }
        c->fx = sx; c->fy = sy;
        return;
    }
    // A cutscene: while a script holds the controls, someone other than the
    // player actually walks (turning to face the player doesn't count). It
    // lasts until the script lets go.
    {
        static s16 startX[OBJECT_EVENTS_COUNT], startY[OBJECT_EVENTS_COUNT];
        static int wasLocked, latched;
        static u16 lockMap;
        if (!wasLocked || lockMap != id)
        {
            for (i = 0; i < OBJECT_EVENTS_COUNT; i++)
            {
                startX[i] = gObjectEvents[i].currentCoords.x;
                startY[i] = gObjectEvents[i].currentCoords.y;
            }
            latched = 0;
            lockMap = id;
        }
        wasLocked = 1;
        for (i = 0; i < OBJECT_EVENTS_COUNT; i++)
        {
            struct ObjectEvent *o = &gObjectEvents[i];
            int x, y;
            if (!o->active || o->invisible || o->spriteId >= MAX_SPRITES)
                continue;
            if (i != gPlayerAvatar.objectEventId && (o->currentCoords.x != startX[i] || o->currentCoords.y != startY[i]))
                latched = 1;
            if (i != gPlayerAvatar.objectEventId && o->heldMovementActive && !o->heldMovementFinished && !o->frozen)
            {
                SpriteFeet(o, &x, &y);
                sx += x; sy += y; n++;
            }
        }
        moving = latched;
        s_cineWasLocked = &wasLocked;
    }
    if (gNoOfApproachingTrainers > 0 || gTrainerApproachedPlayer)
    {
        struct ObjectEvent *t = &gObjectEvents[gApproachingTrainers[0].objectEventId & 15];
        c->want = 1;
        c->style = c->mapStyle ? c->mapStyle : CINE_SPOTTED;
        c->zoom = 1.12f;
        if (t->active && t->spriteId < MAX_SPRITES)
        {
            int x, y;
            SpriteFeet(t, &x, &y);
            sx += x * 2; sy += y * 2; n += 2;
        }
    }
    else if (moving > 0 || (c->mapStyle != CINE_NONE && c->mapStyle != CINE_GYM))
    {
        c->want = 1;
        if (!c->mapStyle) c->style = CINE_STORY;
        c->zoom = 1.08f;
    }
    c->fx = sx / n;
    c->fy = sy / n - 12;
}
static void CineForce(void)
{
    if (getenv("EMERALD_CINESTYLE"))
    {
        gPcCine.want = 1;
        gPcCine.style = atoi(getenv("EMERALD_CINESTYLE"));
        gPcCine.zoom = 1.08f;
    }
}
static void CineDebug(void)
{
    static int k;
    if (getenv("EMERALD_CINEDEBUG") && k++ % 20 == 0)
    {
        int i, held = 0, fr = 0;
        for (i = 0; i < OBJECT_EVENTS_COUNT; i++)
            if (gObjectEvents[i].active) { held |= gObjectEvents[i].heldMovementActive << i; fr |= gObjectEvents[i].frozen << i; }
        fprintf(stderr, "cine: locked=%d want=%d style=%d held=%x frozen=%x appr=%d\n", ArePlayerFieldControlsLocked(), gPcCine.want, gPcCine.style, held, fr, gNoOfApproachingTrainers);
    }
}

void PcUpdateFieldFx(void)
{
    struct PcFieldFx *fx = &gPcFieldFx;
    int i;

    fx->outdoors = IsMapTypeOutdoors(gMapHeader.mapType);
    fx->numLights = 0;
    fx->numShadows = 0;
    fx->hideTileCount[0] = fx->hideTileCount[1] = 0;

    // Weather the renderer redraws at full resolution.
    fx->weather = PC_WEATHER_NONE;
    switch (gWeatherPtr->currWeather)
    {
    case WEATHER_RAIN:
    case WEATHER_RAIN_THUNDERSTORM:
        fx->weather = gWeatherPtr->rainSpriteCount ? PC_WEATHER_RAIN : PC_WEATHER_NONE;
        break;
    case WEATHER_DOWNPOUR:
        fx->weather = gWeatherPtr->rainSpriteCount ? PC_WEATHER_DOWNPOUR : PC_WEATHER_NONE;
        break;
    case WEATHER_SANDSTORM:
        fx->weather = gWeatherPtr->sandstormSpritesCreated ? PC_WEATHER_SANDSTORM : PC_WEATHER_NONE;
        break;
    }
    fx->flash = 0;
    fx->ash = gWeatherPtr->currWeather == WEATHER_VOLCANIC_ASH;
    {
        u16 id = gSaveBlock1Ptr->location.mapNum | (gSaveBlock1Ptr->location.mapGroup << 8);
        fx->mood = 0;
        if (id == MAP_ROUTE119 || id == MAP_ROUTE120) fx->mood = 1;
        else if (id == MAP_ROUTE111) fx->mood = 2;
        else if (id == MAP_FORTREE_CITY) fx->mood = 3;
        else if (id == MAP_SOOTOPOLIS_CITY) fx->mood = 4;
        else if (id == MAP_MT_PYRE_EXTERIOR || id == MAP_MT_PYRE_SUMMIT) fx->mood = 5;
        else if (id == MAP_LAVARIDGE_TOWN) fx->mood = 6;
        else if (id == MAP_PACIFIDLOG_TOWN || id == MAP_EVER_GRANDE_CITY) fx->mood = 7;
        fx->heat = id == MAP_MT_CHIMNEY || id == MAP_FIERY_PATH
                || (id >= MAP_MAGMA_HIDEOUT_1F && id <= MAP_MAGMA_HIDEOUT_1F + 7);
    }
    if (gWeatherPtr->currWeather == WEATHER_RAIN_THUNDERSTORM && gWeatherPtr->colorMapIndex > 3)
        fx->flash = gWeatherPtr->colorMapIndex - 3;
    if (fx->weather == PC_WEATHER_RAIN || fx->weather == PC_WEATHER_DOWNPOUR)
    {
        u16 t = GetSpriteTileStartByTag(GFXTAG_RAIN);
        if (t != 0xFFFF) { fx->hideTileStart[0] = t; fx->hideTileCount[0] = 48 /* graphics/weather/rain.png */; }
    }
    else if (fx->weather == PC_WEATHER_SANDSTORM)
    {
        u16 t = GetSpriteTileStartByTag(GFXTAG_SANDSTORM);
        if (t != 0xFFFF) { fx->hideTileStart[0] = t; fx->hideTileCount[0] = 80 /* graphics/weather/sandstorm.png */; }
    }

    // Metatile flags around the camera (one row above the screen too, so
    // shadows from scenery just off-screen still fall into view).
    fx->mapType = gMapHeader.mapType;
    {
        int margin = (PcFieldMargin() + 15) / 16 + 1, row, col;
        int mx0 = gSaveBlock1Ptr->pos.x - margin, my0 = gSaveBlock1Ptr->pos.y - 2;
        s16 sx, sy;
        SetSpritePosToMapCoords(mx0, my0, &sx, &sy);
        fx->gridX = sx + gSpriteCoordOffsetX;
        fx->gridY = sy + gSpriteCoordOffsetY;
        fx->gridWX = mx0;
        fx->gridWY = my0;
        for (row = 0; row < PC_GRID_H; row++)
            for (col = 0; col < PC_GRID_W; col++)
            {
                int x = mx0 + col, y = my0 + row;
                u8 b = MapGridGetMetatileBehaviorAt(x, y), f = 0;
                if (MetatileBehavior_IsSurfableWaterOrUnderwater(b))
                    f |= PC_CELL_WATER;
                else if (MapGridGetCollisionAt(x, y))
                    f |= PC_CELL_SOLID;
                if (MetatileBehavior_IsTallGrass(b) || MetatileBehavior_IsLongGrass(b) || MetatileBehavior_IsAshGrass(b))
                    f |= PC_CELL_GRASS;
                if (MetatileBehavior_IsSandOrDeepSand(b) || MetatileBehavior_IsFootprints(b))
                    f |= PC_CELL_SAND;
                if (MetatileBehavior_IsJumpEast(b) || MetatileBehavior_IsJumpWest(b)
                 || MetatileBehavior_IsJumpNorth(b) || MetatileBehavior_IsJumpSouth(b))
                    f |= PC_CELL_LEDGE;
                if (MetatileBehavior_IsPuddle(b) || MetatileBehavior_IsShallowFlowingWater(b) || MetatileBehavior_IsReflective(b))
                    f |= PC_CELL_PUDDLE;
                if (MetatileBehavior_IsDoor(b) || MetatileBehavior_IsWarpDoor(b) || MetatileBehavior_IsNonAnimDoor(b))
                    f |= PC_CELL_DOOR;
                fx->grid[row][col] = f;
            }
    }

    // Map button (M / pad X): fade out and open the game's own Hoenn region
    // map, which marks where the player is; B returns to the field.
    {
        static int opening;
        if (gPcMapRequest && !opening && gMain.callback2 == CB2_Overworld && !gPaletteFade.active
         && !ArePlayerFieldControlsLocked() && gPlayerAvatar.tileTransitionState == T_NOT_MOVING)
        {
            PlaySE(SE_WIN_OPEN);
            FreezeObjectEvents();
            PlayerFreeze();
            StopPlayerAvatar();
            LockPlayerFieldControls();
            FadeScreen(FADE_TO_BLACK, 0);
            opening = 1;
        }
        gPcMapRequest = 0;
        if (opening && !gPaletteFade.active)
        {
            opening = 0;
            CleanupOverworldWindowsAndTilemaps();
            FieldInitRegionMap(CB2_ReturnToField);
        }
    }

    // Screen fade (doors, warps): the 3D world fades with the palettes.
    {
        u16 c = gPaletteFade.blendColor;
        fx->fade[0] = (c & 31) / 31.0f; fx->fade[1] = ((c >> 5) & 31) / 31.0f; fx->fade[2] = ((c >> 10) & 31) / 31.0f;
        fx->fade[3] = gPaletteFade.y / 16.0f;
    }

    // Quick save (F6) while the player is free to move, wherever the start
    // menu would offer SAVE. Never over a different file the player has not
    // saved over yet (a new game: the start menu, with its warning, does that).
    if (gPcQuickSave)
    {
        int free = gMain.callback2 == CB2_Overworld && !gPaletteFade.active && !ArePlayerFieldControlsLocked()
                && gPlayerAvatar.tileTransitionState == T_NOT_MOVING;
        int may = !gDifferentSaveFile && !IsOverworldLinkActive() && !InUnionRoom() && !GetSafariZoneFlag()
               && !InBattlePike() && CurrentBattlePyramidLocation() == PYRAMID_LOCATION_NONE && !InMultiPartnerRoom();
        if (free && may)
        {
            SaveMapView();
            TrySavingData(SAVE_NORMAL);
        }
        PlaySE(free && may ? SE_SAVE : SE_FAILURE);
        gPcQuickSave = 0;   // pressed in a menu or battle: refused, not saved later by surprise
    }

    // Wake: while swimming, where the player was every few frames (the
    // renderer spreads rings from these, leaving a V behind).
    {
        static int tick;
        float now = (float)PortFrameCount();
        int cx = (fx->playerX - fx->gridX) >> 4, cy = (fx->playerY - 4 - fx->gridY) >> 4, k;
        int swim = fx->playerX > -900 && cx >= 0 && cx < PC_GRID_W && cy >= 0 && cy < PC_GRID_H
            && (fx->grid[cy][cx] & PC_CELL_WATER);
        float wx = (float)(fx->playerX - fx->gridX + fx->gridWX * 16), wy = (float)(fx->playerY - 4 - fx->gridY + fx->gridWY * 16);
        if (fx->playerX <= -900)
            for (k = 0; k < 12; k++) fx->wake[k][2] = -1;
        if (swim && ++tick >= 6)
        {
            float dx = wx - fx->wake[1][0], dy = wy - fx->wake[1][1];
            tick = 0;
            if (fx->wake[1][2] < 0 || dx * dx + dy * dy >= 4)
            {
                memmove(fx->wake[2], fx->wake[1], sizeof(fx->wake[0]) * 10);
                fx->wake[1][0] = wx; fx->wake[1][1] = wy; fx->wake[1][2] = now;
            }
        }
        fx->wake[0][0] = wx; fx->wake[0][1] = wy; fx->wake[0][2] = swim ? now : -1;
    }

    PcWonderTradeUpdate();
    PcUpdateFollower();
    PcUpdateCinematic();
    CineForce();
    CineDebug();

    // Ambient sound: what is around the player, and on which side.
    {
        struct PcAmbient *a = &gPcAmbient;
        int margin = (PcFieldMargin() + 15) / 16 + 1, row, col;
        float wl = 0, wr = 0, tr = 0, sum = 0;
        for (row = 0; row < PC_GRID_H; row++)
            for (col = 0; col < PC_GRID_W; col++)
            {
                float dx = col - margin, dy = row - 2, w = 1.0f / (1.0f + (dx * dx + dy * dy) / 20.0f);
                u8 f = fx->grid[row][col];
                sum += w;
                if (f & PC_CELL_WATER) { float p = dx / 6.0f; p = p < -1 ? -1 : p > 1 ? 1 : p; wl += w * (1 - p) * 0.5f; wr += w * (1 + p) * 0.5f; }
                if ((f & PC_CELL_SOLID) || (f & PC_CELL_GRASS)) tr += w;
            }
        a->waterL = wl / sum * 3.0f; a->waterR = wr / sum * 3.0f;
        if (a->waterL > 1) a->waterL = 1;
        if (a->waterR > 1) a->waterR = 1;
        a->trees = tr / sum * 1.5f; if (a->trees > 1) a->trees = 1;
        a->open = fx->outdoors ? 1.0f - a->trees * 0.6f : 0.0f;
        a->rain = fx->weather == PC_WEATHER_RAIN ? 0.6f : fx->weather == PC_WEATHER_DOWNPOUR ? 1.0f : 0.0f;
        a->lava = fx->heat ? 1.0f : 0.0f;
        a->cave = gMapHeader.mapType == MAP_TYPE_UNDERGROUND ? 1.0f : 0.0f;
        a->town = (gMapHeader.mapType == MAP_TYPE_TOWN || gMapHeader.mapType == MAP_TYPE_CITY) ? 1.0f : 0.0f;
        if (!fx->outdoors) { a->trees = 0; a->waterL *= 0.3f; a->waterR *= 0.3f; }
        a->active = 1;
    }

    // Doors and other entrances glow at night.
    if (gMapHeader.events)
    {
        for (i = 0; i < gMapHeader.events->warpCount && fx->numLights < PC_MAX_LIGHTS; i++)
        {
            const struct WarpEvent *w = &gMapHeader.events->warps[i];
            s16 sx, sy;
            SetSpritePosToMapCoords(w->x + MAP_OFFSET, w->y + MAP_OFFSET, &sx, &sy);
            // Same camera offset field sprites get; then the tile's centre.
            sx += gSpriteCoordOffsetX + 8;
            sy += gSpriteCoordOffsetY + 6;
            if (sx < -160 || sx > 400 || sy < -80 || sy > 240)
                continue;
            fx->lights[fx->numLights].x = sx;
            fx->lights[fx->numLights].y = sy;
            fx->lights[fx->numLights].radius = 34;
            fx->numLights++;
        }
    }

    fx->playerX = fx->playerY = -999;
    if (gPlayerAvatar.spriteId < MAX_SPRITES && gSprites[gPlayerAvatar.spriteId].inUse)
    {
        struct Sprite *sp = &gSprites[gPlayerAvatar.spriteId];
        fx->playerX = sp->x + sp->x2 + (sp->coordOffsetEnabled ? gSpriteCoordOffsetX : 0);
        fx->playerY = sp->y + sp->y2 + (sp->coordOffsetEnabled ? gSpriteCoordOffsetY : 0) - sp->centerToCornerVecY - 2;
    }

    // The following Pokémon casts a shadow too.
    if (gPcFollower.show && fx->numShadows < PC_MAX_SHADOWS)
    {
        fx->shadows[fx->numShadows].x = gPcFollower.x + 16;
        fx->shadows[fx->numShadows].y = gPcFollower.feetY;
        fx->shadows[fx->numShadows].w = 14;
        fx->numShadows++;
    }

    // Soft shadows under characters.
    for (i = 0; i < OBJECT_EVENTS_COUNT && fx->numShadows < PC_MAX_SHADOWS; i++)
    {
        struct ObjectEvent *obj = &gObjectEvents[i];
        struct Sprite *sp;
        s16 cx, cy;
        if (!obj->active || obj->invisible || obj->spriteId >= MAX_SPRITES)
            continue;
        sp = &gSprites[obj->spriteId];
        if (!sp->inUse || sp->invisible)
            continue;
        cx = sp->x + sp->x2;
        cy = sp->y + sp->y2;
        if (sp->coordOffsetEnabled)
        {
            cx += gSpriteCoordOffsetX;
            cy += gSpriteCoordOffsetY;
        }
        // Feet: bottom of the sprite's frame.
        cy += -sp->centerToCornerVecY - 2;
        if (cx < -100 || cx > 340 || cy < -40 || cy > 200)
            continue;
        fx->shadows[fx->numShadows].x = cx;
        fx->shadows[fx->numShadows].y = cy;
        fx->shadows[fx->numShadows].w = -sp->centerToCornerVecX * 2 >= 32 ? 22 : 12;
        fx->numShadows++;
    }
}

// Where each battler's sprite is, for battle lighting, shadows and idle motion.
void PcUpdateBattleFx(void)
{
    static const u8 sDim[3][4][2] = {
        { { 8, 8 }, { 16, 16 }, { 32, 32 }, { 64, 64 } },     // square
        { { 16, 8 }, { 32, 8 }, { 32, 16 }, { 64, 32 } },     // horizontal
        { { 8, 16 }, { 8, 32 }, { 16, 32 }, { 32, 64 } },     // vertical
    };
    struct PcBattleFx *b = &gPcBattleFx;
    int i;
    b->outdoors = IsMapTypeOutdoors(gMapHeader.mapType);
    b->boss = PcBattleBoss();
    // Which new backdrop to draw; special battles keep their own art.
    b->scene = -1;
    if (!(gBattleTypeFlags & (BATTLE_TYPE_LINK | BATTLE_TYPE_FRONTIER | BATTLE_TYPE_EREADER_TRAINER | BATTLE_TYPE_RECORDED_LINK
                              | BATTLE_TYPE_GROUDON | BATTLE_TYPE_KYOGRE | BATTLE_TYPE_RAYQUAZA))
        && GetCurrentMapBattleScene() == MAP_BATTLE_SCENE_NORMAL
        && !((gBattleTypeFlags & BATTLE_TYPE_TRAINER)
             && (gTrainers[gTrainerBattleOpponent_A].trainerClass == TRAINER_CLASS_LEADER
                 || gTrainers[gTrainerBattleOpponent_A].trainerClass == TRAINER_CLASS_CHAMPION)))
    {
        switch (gBattleEnvironment)
        {
        case BATTLE_ENVIRONMENT_GRASS:
        case BATTLE_ENVIRONMENT_PLAIN:
            b->scene = (gMapHeader.mapType == MAP_TYPE_TOWN || gMapHeader.mapType == MAP_TYPE_CITY) ? PC_BSCENE_TOWN : PC_BSCENE_ROUTE;
            break;
        case BATTLE_ENVIRONMENT_LONG_GRASS: b->scene = PC_BSCENE_TALLGRASS; break;
        case BATTLE_ENVIRONMENT_SAND:       b->scene = PC_BSCENE_SAND; break;
        case BATTLE_ENVIRONMENT_UNDERWATER: b->scene = PC_BSCENE_UNDERWATER; break;
        case BATTLE_ENVIRONMENT_WATER:      b->scene = PC_BSCENE_SEA; break;
        case BATTLE_ENVIRONMENT_POND:       b->scene = PC_BSCENE_POND; break;
        case BATTLE_ENVIRONMENT_MOUNTAIN:   b->scene = PC_BSCENE_MOUNTAIN; break;
        case BATTLE_ENVIRONMENT_CAVE:       b->scene = PC_BSCENE_CAVE; break;
        case BATTLE_ENVIRONMENT_BUILDING:   b->scene = PC_BSCENE_INDOOR; break;
        }
        if (getenv("EMERALD_BSCENE"))   // testing: force a backdrop
            b->scene = atoi(getenv("EMERALD_BSCENE"));
    }
    b->count = gBattlersCount < 4 ? gBattlersCount : 4;
    {
        extern u16 gPcAnimMove;
        extern u8 gPcAnimIsMove;
        static u16 lastHp[4];
        static int seen;
        b->anim = gAnimScriptActive && gPcAnimIsMove;
        b->attacker = gBattleAnimAttacker & 3;
        b->target = gBattleAnimTarget & 3;
        b->moveType = b->anim && gPcAnimMove < MOVES_COUNT ? gBattleMoves[gPcAnimMove].type : -1;
        b->shake *= 0.85f;
        for (i = 0; i < b->count; i++)
        {
            u16 hp = gBattleMons[i].hp;
            if (seen && hp < lastHp[i] && gBattleMons[i].maxHP)
            {
                float f = 0.35f + 2.0f * (lastHp[i] - hp) / (float)gBattleMons[i].maxHP;
                if (f > 1) f = 1;
                if (f > b->shake) b->shake = f;
            }
            lastHp[i] = hp;
        }
        seen = 1;
    }
    for (i = 0; i < b->count; i++)
    {
        u8 id = gBattlerSpriteIds[i];
        struct Sprite *sp;
        int w, h;
        b->mon[i].visible = 0;
        if (id >= MAX_SPRITES)
            continue;
        sp = &gSprites[id];
        if (!sp->inUse || sp->invisible || sp->oam.shape > 2)
            continue;
        w = sDim[sp->oam.shape][sp->oam.size][0];
        h = sDim[sp->oam.shape][sp->oam.size][1];
        if (sp->oam.affineMode == ST_OAM_AFFINE_DOUBLE)
        {
            w *= 2;
            h *= 2;
        }
        b->mon[i].x = sp->x + sp->x2 - w / 2;
        b->mon[i].y = sp->y + sp->y2 - h / 2;
        b->mon[i].w = w;
        b->mon[i].h = h;
        b->mon[i].side = GetBattlerSide(i);
        b->mon[i].tile = sp->oam.tileNum;
        b->mon[i].visible = 1;
    }
}

// Style for the current battle: the map's own cinematic style if it has
// one (Elite Four rooms, legendary lairs), else by opponent.
int PcBattleBoss(void)
{
    u16 id = gSaveBlock1Ptr->location.mapNum | (gSaveBlock1Ptr->location.mapGroup << 8);
    int ms = MapCineStyle(id);
    if (gBattleTypeFlags & (BATTLE_TYPE_LEGENDARY | BATTLE_TYPE_REGI | BATTLE_TYPE_GROUDON | BATTLE_TYPE_KYOGRE | BATTLE_TYPE_RAYQUAZA | BATTLE_TYPE_KYOGRE_GROUDON))
    {
        if (gBattleTypeFlags & BATTLE_TYPE_GROUDON) return CINE_LEGEND_RED;
        if (gBattleTypeFlags & BATTLE_TYPE_KYOGRE) return CINE_LEGEND_BLUE;
        if (gBattleTypeFlags & BATTLE_TYPE_RAYQUAZA) return CINE_LEGEND_GREEN;
        if (gBattleTypeFlags & BATTLE_TYPE_REGI) return CINE_ANCIENT;
        return ms ? ms : CINE_MYSTIC;
    }
    if (gBattleTypeFlags & BATTLE_TYPE_TRAINER)
    {
        u8 tc = gTrainers[gTrainerBattleOpponent_A].trainerClass;
        if (ms >= CINE_E4_SIDNEY && ms <= CINE_CHAMPION) return ms;
        if (tc == TRAINER_CLASS_CHAMPION) return CINE_CHAMPION;
        if (tc == TRAINER_CLASS_ELITE_FOUR) return CINE_E4_SIDNEY;
        if (tc == TRAINER_CLASS_LEADER) return CINE_GYM;
        if (tc == TRAINER_CLASS_MAGMA_LEADER || tc == TRAINER_CLASS_AQUA_LEADER) return CINE_VILLAIN;
        if (tc == TRAINER_CLASS_RIVAL) return CINE_RIVAL;
    }
    return CINE_NONE;
}

// ---- Following Pokémon ----
#define TRAIL 64
static void PcUpdateFollower(void)
{
    struct PcFollower *f = &gPcFollower;
    static s16 tx[TRAIL], ty[TRAIL];
    static int tn, lastSpecies = -1, bottom = 28, lastMap = -1, animT;
    struct ObjectEvent *pl = &gObjectEvents[gPlayerAvatar.objectEventId];
    struct Sprite *sp;
    u16 mapId = gSaveBlock1Ptr->location.mapNum | (gSaveBlock1Ptr->location.mapGroup << 8);
    int i, species = 0, wx, wy;
    f->show = 0;
    if (!getenv("EMERALD_FOLLOW"))   // following Pokémon: off (dropped)
        return;
    for (i = 0; i < PARTY_SIZE; i++)
    {
        u16 sp2 = GetMonData(&gPlayerParty[i], MON_DATA_SPECIES_OR_EGG);
        if (sp2 != SPECIES_NONE && sp2 != SPECIES_EGG && GetMonData(&gPlayerParty[i], MON_DATA_HP) > 0)
        {
            species = sp2;
            break;
        }
    }
    if (!species || gPlayerAvatar.spriteId >= MAX_SPRITES
        || (gPlayerAvatar.flags & (PLAYER_AVATAR_FLAG_SURFING | PLAYER_AVATAR_FLAG_UNDERWATER)))
    {
        tn = 0;
        return;
    }
    // The icon image: two 32x32 frames of 4bpp tiles, coloured with its palette.
    if (species != lastSpecies)
    {
        const u8 *tiles = GetMonIconPtr(species, GetMonData(&gPlayerParty[i], MON_DATA_PERSONALITY), TRUE);
        const u16 *pal = GetValidMonIconPalettePtr(species);
        int px, py, minB = 0;
        for (py = 0; py < 64; py++)
            for (px = 0; px < 32; px++)
            {
                int fr = py / 32, ly = py % 32;
                int tile = fr * 16 + (ly / 8) * 4 + px / 8;
                u8 b = tiles[tile * 32 + (ly % 8) * 4 + (px % 8) / 2];
                int c = (px & 1) ? b >> 4 : b & 15;
                u16 col = pal[c];
                u32 r = (col & 31) << 3, g = ((col >> 5) & 31) << 3, bl = ((col >> 10) & 31) << 3;
                f->rgba[py][px] = c ? (0xFF000000u | (bl | bl >> 5) << 16 | (g | g >> 5) << 8 | (r | r >> 5)) : 0;
                f->col[py][px] = c ? (col & 0x7FFF) | 0x8000 : 0;
                if (c && fr == 0 && ly > minB) minB = ly;
            }
        bottom = minB;
        lastSpecies = species;
        f->iconVersion++;
    }
    f->species = species;
    // Trail of the player's feet in world pixels (screen minus camera offset).
    sp = &gSprites[gPlayerAvatar.spriteId];
    wx = sp->x + sp->x2;
    wy = sp->y + sp->y2 - sp->centerToCornerVecY - 2;
    if (mapId != lastMap)
    {
        tn = 0;
        lastMap = mapId;
    }
    if (tn > 0 && (abs(wx - tx[0]) > 40 || abs(wy - ty[0]) > 40))
        tn = 0;   // a jump (map connection, warp): start over
    if (tn == 0 || wx != tx[0] || wy != ty[0])
    {
        memmove(tx + 1, tx, sizeof(tx) - sizeof(tx[0]));
        memmove(ty + 1, ty, sizeof(ty) - sizeof(ty[0]));
        tx[0] = wx; ty[0] = wy;
        if (tn < TRAIL) tn++;
    }
    {
        // Follow 16 px of path behind the player.
        float dist = 0, fxp = tx[tn - 1], fyp = ty[tn - 1];
        int moving = 0;
        for (i = 1; i < tn; i++)
        {
            float dx = tx[i] - tx[i - 1], dy = ty[i] - ty[i - 1], seg = sqrtf(dx * dx + dy * dy);
            if (dist + seg >= 16.0f)
            {
                float t = (16.0f - dist) / seg;
                fxp = tx[i - 1] + dx * t;
                fyp = ty[i - 1] + dy * t;
                break;
            }
            dist += seg;
        }
        if (tn < 2)
        {
            // No path yet: stand one tile behind, opposite the facing direction.
            int dir = pl->facingDirection;
            fxp = wx + (dir == DIR_EAST ? -16 : dir == DIR_WEST ? 16 : 0);
            fyp = wy + (dir == DIR_SOUTH ? -16 : dir == DIR_NORTH ? 16 : 0);
        }
        {
            static float lastX, lastY;
            moving = fabsf(fxp - lastX) + fabsf(fyp - lastY) > 0.1f;
            if (fxp > lastX + 0.1f) f->flip = 1;
            else if (fxp < lastX - 0.1f) f->flip = 0;
            lastX = fxp; lastY = fyp;
        }
        animT += moving ? 2 : 1;
        f->frame = (animT / 16) & 1;
        f->feetY = (int)fyp + (sp->coordOffsetEnabled ? gSpriteCoordOffsetY : 0);
        f->x = (int)fxp - 16 + (sp->coordOffsetEnabled ? gSpriteCoordOffsetX : 0);
        f->y = f->feetY - bottom - 1;
    }
    f->prio = sp->oam.priority;
    f->playerFeetY = wy + (sp->coordOffsetEnabled ? gSpriteCoordOffsetY : 0);
    {
        // Follow the palette fade the player's sprite is under (warps, cutscenes).
        int pn = sp->oam.paletteNum, k, best = 1, bl = -1;
        for (k = 1; k < 16; k++)
        {
            u16 u = gPlttBufferUnfaded[0x100 + pn * 16 + k];
            int l = (u & 31) + ((u >> 5) & 31) + ((u >> 10) & 31);
            if (l > bl) { bl = l; best = k; }
        }
        {
            u16 u = gPlttBufferUnfaded[0x100 + pn * 16 + best], fd = gPlttBufferFaded[0x100 + pn * 16 + best];
            for (k = 0; k < 3; k++)
            {
                float U = ((u >> (k * 5)) & 31) / 31.0f, F = ((fd >> (k * 5)) & 31) / 31.0f;
                if (F <= U) { f->fadeMul[k] = U > 0.02f ? F / U : 1.0f; f->fadeAdd[k] = 0; }
                else { float t = U < 0.98f ? (F - U) / (1.0f - U) : 0.0f; f->fadeMul[k] = 1.0f - t; f->fadeAdd[k] = t; }
            }
        }
    }
    f->show = 1;
}

int PcPartyUi(struct PcPartyCard out[6])
{
    int i, n = 0;
    for (i = 0; i < PARTY_SIZE; i++)
    {
        const struct WindowTemplate *w = &gWindows[i].window;
        struct PcPartyCard *c = &out[i];
        int left;
        if (w->bg != 0 || (w->width != 10 && w->width != 18) || gWindows[i].tileData == NULL)
            break;
        left = w->width == 10;
        c->x = w->tilemapLeft * 8; c->y = w->tilemapTop * 8;
        c->w = w->width * 8; c->h = w->height * 8;
        c->barX = c->x + (left ? 24 : 88); c->barY = c->y + (left ? 35 : 10); c->barW = 48;
        c->state = 0; c->hp = 0;
        if (i < gPlayerPartyCount && GetMonData(&gPlayerParty[i], MON_DATA_SPECIES) != SPECIES_NONE)
        {
            u16 hp = GetMonData(&gPlayerParty[i], MON_DATA_HP), max = GetMonData(&gPlayerParty[i], MON_DATA_MAX_HP);
            c->state |= 1;
            c->hp = max ? (float)hp / max : 0;
            if (hp == 0 && !GetMonData(&gPlayerParty[i], MON_DATA_IS_EGG)) c->state |= 4;
        }
        if (!(gPcPartyBars & (1 << i)))
            c->barW = 0;   // this screen hides HP (eggs, TM compatibility)
        if (gPartyMenu.slotId == i) c->state |= 2;
        if (gPartyMenu.action == PARTY_ACTION_SWITCHING && gPartyMenu.slotId2 == i) c->state |= 8;
        n++;
    }
    return n;
}

// HD window panels: the game records framed windows instead of drawing their
// frames; a panel stays while its window is allocated and its tilemap is
// still on the BG (a cleared or reused window drops it).
static struct { u8 used, windowId, dialogue; struct WindowTemplate t; } sPanels[16];

void PcPanelAdd(u8 windowId, int dialogue)
{
    int i, free = -1;
    for (i = 0; i < 16; i++)
    {
        if (sPanels[i].used && sPanels[i].windowId == windowId) { free = i; break; }
        if (!sPanels[i].used && free < 0) free = i;
    }
    if (free < 0)
        return;
    sPanels[free].used = 1;
    sPanels[free].windowId = windowId;
    sPanels[free].dialogue = dialogue;
    sPanels[free].t = gWindows[windowId].window;
}

void PcPanelRemove(u8 windowId)
{
    int i;
    for (i = 0; i < 16; i++)
        if (sPanels[i].used && sPanels[i].windowId == windowId)
            sPanels[i].used = 0;
}

int PcPanels(struct PcPanel out[16])
{
    int i, n = 0;
    u16 dispcnt = GetGpuReg(REG_OFFSET_DISPCNT);
    for (i = 0; i < 16; i++)
    {
        const struct WindowTemplate *t = &sPanels[i].t, *w = &gWindows[sPanels[i].windowId].window;
        const u16 *map;
        if (!sPanels[i].used)
            continue;
        if (gWindows[sPanels[i].windowId].tileData == NULL || w->bg != t->bg || w->tilemapLeft != t->tilemapLeft
         || w->tilemapTop != t->tilemapTop || w->width != t->width || w->height != t->height || w->baseBlock != t->baseBlock)
        {
            sPanels[i].used = 0;   // the window was removed or its id reused
            continue;
        }
        map = GetBgTilemapBuffer(t->bg);
        if (!map || (map[t->tilemapTop * 32 + t->tilemapLeft] & 0x3FF) != (t->baseBlock & 0x3FF) || !(dispcnt & (DISPCNT_BG0_ON << t->bg)))
            continue;   // not on screen right now (tilemap cleared or BG hidden)
        out[n].x = t->tilemapLeft * 8; out[n].y = t->tilemapTop * 8;
        out[n].w = t->width * 8; out[n].h = t->height * 8;
        out[n].bg = t->bg; out[n].dialogue = sPanels[i].dialogue;
        n++;
    }
    return n;
}

// Physical/special split: the moves that are special from generation 4 on
// (pokeemerald-expansion's categories); every other damaging move is physical.
static const u16 sSpecialMoves[] = {
    MOVE_RAZOR_WIND, MOVE_GUST, MOVE_SONIC_BOOM, MOVE_ACID,
    MOVE_EMBER, MOVE_FLAMETHROWER, MOVE_WATER_GUN, MOVE_HYDRO_PUMP,
    MOVE_SURF, MOVE_ICE_BEAM, MOVE_BLIZZARD, MOVE_PSYBEAM,
    MOVE_BUBBLE_BEAM, MOVE_AURORA_BEAM, MOVE_HYPER_BEAM, MOVE_ABSORB,
    MOVE_MEGA_DRAIN, MOVE_SOLAR_BEAM, MOVE_PETAL_DANCE, MOVE_DRAGON_RAGE,
    MOVE_FIRE_SPIN, MOVE_THUNDER_SHOCK, MOVE_THUNDERBOLT, MOVE_THUNDER,
    MOVE_CONFUSION, MOVE_PSYCHIC, MOVE_NIGHT_SHADE, MOVE_SMOG,
    MOVE_SLUDGE, MOVE_FIRE_BLAST, MOVE_SWIFT, MOVE_DREAM_EATER,
    MOVE_BUBBLE, MOVE_PSYWAVE, MOVE_TRI_ATTACK, MOVE_SNORE,
    MOVE_AEROBLAST, MOVE_POWDER_SNOW, MOVE_SLUDGE_BOMB, MOVE_MUD_SLAP,
    MOVE_OCTAZOOKA, MOVE_ZAP_CANNON, MOVE_ICY_WIND, MOVE_GIGA_DRAIN,
    MOVE_DRAGON_BREATH, MOVE_HIDDEN_POWER, MOVE_TWISTER, MOVE_MIRROR_COAT,
    MOVE_ANCIENT_POWER, MOVE_SHADOW_BALL, MOVE_FUTURE_SIGHT, MOVE_WHIRLPOOL,
    MOVE_UPROAR, MOVE_SPIT_UP, MOVE_HEAT_WAVE, MOVE_ERUPTION,
    MOVE_LUSTER_PURGE, MOVE_MIST_BALL, MOVE_HYPER_VOICE, MOVE_BLAST_BURN,
    MOVE_HYDRO_CANNON, MOVE_WEATHER_BALL, MOVE_AIR_CUTTER, MOVE_OVERHEAT,
    MOVE_SILVER_WIND, MOVE_WATER_SPOUT, MOVE_SIGNAL_BEAM, MOVE_EXTRASENSORY,
    MOVE_SHEER_COLD, MOVE_MUDDY_WATER, MOVE_FRENZY_PLANT, MOVE_MUD_SHOT,
    MOVE_MAGICAL_LEAF, MOVE_SHOCK_WAVE, MOVE_WATER_PULSE, MOVE_DOOM_DESIRE,
    MOVE_PSYCHO_BOOST
};

bool8 PcMoveIsPhysical(u16 move, u8 type)
{
    int i;
    if (move == MOVE_NONE)
        return IS_TYPE_PHYSICAL(type);
    for (i = 0; i < (int)ARRAY_COUNT(sSpecialMoves); i++)
        if (sSpecialMoves[i] == move)
            return FALSE;
    return TRUE;
}

// Hard mode: trainers' Pokémon a few levels higher (10%, at least 2), stats recalculated.
void PcHardModeBoost(struct Pokemon *party, int count)
{
    int i;
    if (!FlagGet(FLAG_PC_HARD_MODE))
        return;
    for (i = 0; i < count; i++)
    {
        u16 species = GetMonData(&party[i], MON_DATA_SPECIES);
        u32 lvl = GetMonData(&party[i], MON_DATA_LEVEL), exp;
        if (species == SPECIES_NONE)
            continue;
        lvl += lvl / 10 > 2 ? lvl / 10 : 2;
        if (lvl > MAX_LEVEL)
            lvl = MAX_LEVEL;
        exp = gExperienceTables[gSpeciesInfo[species].growthRate][lvl];
        SetMonData(&party[i], MON_DATA_EXP, &exp);
        CalculateMonStats(&party[i]);
    }
}
