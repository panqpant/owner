// Overworld lighting data for the renderer: light sources (building doors)
// and character positions (for soft shadows), in GBA screen coordinates.
// Called once per overworld frame. Compiled with the game's headers.
#include "global.h"
#include "event_object_movement.h"
#include "field_camera.h"
#include "fieldmap.h"
#include "overworld.h"
#include "sprite.h"
#include "fieldfx.h"

struct PcFieldFx gPcFieldFx;

void PcUpdateFieldFx(void)
{
    struct PcFieldFx *fx = &gPcFieldFx;
    int i;

    fx->outdoors = IsMapTypeOutdoors(gMapHeader.mapType);
    fx->numLights = 0;
    fx->numShadows = 0;

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
