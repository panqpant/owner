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

    // Water metatiles around the camera, for the shimmer effect.
    {
        int margin = (PcFieldMargin() + 15) / 16 + 1, row, col;
        int mx0 = gSaveBlock1Ptr->pos.x - margin, my0 = gSaveBlock1Ptr->pos.y;
        s16 sx, sy;
        SetSpritePosToMapCoords(mx0, my0, &sx, &sy);
        fx->waterX = sx + gSpriteCoordOffsetX;
        fx->waterY = sy + gSpriteCoordOffsetY;
        fx->waterCols = 17 + margin * 2;
        if (fx->waterCols > 31)
            fx->waterCols = 31;
        for (row = 0; row < PC_WATER_ROWS; row++)
        {
            int bits = 0;
            for (col = 0; col < fx->waterCols; col++)
                if (MetatileBehavior_IsSurfableWaterOrUnderwater(MapGridGetMetatileBehaviorAt(mx0 + col, my0 + row)))
                    bits |= 1 << col;
            fx->water[row] = bits;
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
