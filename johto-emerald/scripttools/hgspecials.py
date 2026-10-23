"""Small engine helpers HGSS scripts expect, added as Emerald specials."""
import os, re
PE = os.environ.get('PE', '/tmp/claude-0/-home-user-owner/ff77f0d1-c832-536b-9509-6c7ef5c1b385/scratchpad/pokeemerald')

C = '''#include "global.h"
#include "event_object_movement.h"
#include "field_player_avatar.h"
#include "rtc.h"
#include "constants/event_object_movement.h"

// HGSS numbers directions 0 up, 1 down, 2 left, 3 right
u16 HGSS_GetPlayerFacing(void)
{
    switch (GetPlayerFacingDirection())
    {
    case DIR_NORTH: return 0;
    case DIR_WEST:  return 2;
    case DIR_EAST:  return 3;
    default:        return 1;
    }
}

// HGSS weekdays: 0 Sunday ... 6 Saturday, from the cartridge clock
u16 HGSS_GetWeekday(void)
{
    RtcCalcLocalTime();
    return gLocalTime.days % 7;
}
'''

def install():
    open(PE + '/src/hgss_specials.c', 'w').write(C)
    p = PE + '/data/specials.inc'; s = open(p).read()
    if 'HGSS_GetPlayerFacing' not in s:
        s = s.replace('\tdef_special HealPlayerParty\n', '\tdef_special HealPlayerParty\n\tdef_special HGSS_GetPlayerFacing\n\tdef_special HGSS_GetWeekday\n', 1)
        open(p, 'w').write(s)
    p = PE + '/ld_script.ld'; s = open(p).read()
    if 'hgss_specials.o' not in s:
        s = s.replace('        src/field_specials.o(.text);\n', '        src/field_specials.o(.text);\n        src/hgss_specials.o(.text);\n', 1)
        open(p, 'w').write(s)
        # the Pokémon animation block is pinned only so vanilla matches retail; Johto's maps need the room
    s = open(p).read()
    s = s.replace('    anim_mon_front_pic_data __anim_mon_load_address :', '    anim_mon_front_pic_data :')
    s = s.replace('    gfx_data __gfx_load_address :', '    gfx_data :')
    open(p, 'w').write(s)
    p = PE + '/include/field_specials.h'; s = open(p).read()
    if 'HGSS_GetPlayerFacing' not in s:
        s = s.replace('#endif', 'u16 HGSS_GetPlayerFacing(void);\nu16 HGSS_GetWeekday(void);\n\n#endif', 1)
        open(p, 'w').write(s)
    # HGSS maps can have several setup scripts of one kind (e.g. on-transition and on-resume both
    # placing people); Emerald ran only the first, so run every matching entry. Vanilla maps have one each.
    p = PE + '/src/script.c'; s = open(p).read()
    old = '''void MapHeaderRunScriptType(u8 tag)
{
    u8 *ptr = MapHeaderGetScriptTable(tag);
    if (ptr)
        RunScriptImmediately(ptr);
}'''
    new = '''void MapHeaderRunScriptType(u8 tag)
{
    const u8 *mapScripts = gMapHeader.mapScripts;

    if (!mapScripts)
        return;
    for (; *mapScripts; mapScripts += 5)
    {
        if (*mapScripts == tag)
            RunScriptImmediately(T2_READ_PTR(mapScripts + 1));
    }
}'''
    if old in s:
        open(p, 'w').write(s.replace(old, new, 1))

if __name__ == '__main__':
    install()
