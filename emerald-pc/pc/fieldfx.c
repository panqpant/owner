// Overworld lighting data for the renderer: light sources (building doors)
// and character positions (for soft shadows), in GBA screen coordinates.
// Called once per overworld frame. Compiled with the game's headers.
#include "global.h"
#include "event_object_movement.h"
#include "field_camera.h"
#include "fieldmap.h"
#include "overworld.h"
#include "sprite.h"
#include "field_weather.h"
#include "metatile_behavior.h"
#include "constants/weather.h"
#include "field_player_avatar.h"
#include "fieldfx.h"

struct PcFieldFx gPcFieldFx;
int gPcHdEffects;

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
                fx->grid[row][col] = f;
            }
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
