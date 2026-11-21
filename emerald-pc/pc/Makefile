# Native PC build of pokeemerald. Run from the repository root:
#   make -f pc/Makefile            (headless test binary)
#   make -f pc/Makefile sdl        (SDL2 window build)
# Requires the normal GBA build to have run once (it generates the graphics,
# maps, music and tool binaries this build reuses).

HOST_CC   ?= gcc
HOST_AS   ?= as
ARCH      := -m32
BUILD     := build/pc
OBJ       := $(BUILD)/obj
ASMTREE   := $(BUILD)/asmtree
PREPROC   := tools/preproc/preproc

CPPFLAGS  := $(ARCH) -iquote include -Wno-trigraphs -DMODERN=1 -DPLATFORM_PC -DBUGFIX -std=gnu11
CFLAGS    := $(ARCH) -std=gnu11 -O2 -g -funsigned-char -fno-strict-aliasing -fwrapv \
             -fno-pie -fno-stack-protector -fcommon -w
PC_CFLAGS := $(ARCH) -std=gnu11 -O2 -g -fno-pie -fno-stack-protector -Wall -Wno-unused-function -Ipc
LDFLAGS   := $(ARCH) -no-pie -z noexecstack -Wl,--defsym,gNumMusicPlayers=4 -Wl,--defsym,gMaxLines=0
LIBS      := -lm

# Hardware drivers replaced by pc/*.c
EXCLUDE   := agb_flash agb_flash_1m agb_flash_le agb_flash_mx siirtc
GAME_SRCS := $(filter-out $(addprefix src/,$(addsuffix .c,$(EXCLUDE))),$(wildcard src/*.c))
GAME_OBJS := $(patsubst src/%.c,$(OBJ)/game/%.o,$(GAME_SRCS))

DATA_SRCS := $(wildcard data/*.s)
DATA_OBJS := $(patsubst data/%.s,$(OBJ)/data/%.o,$(DATA_SRCS))
SONG_SRCS := $(wildcard sound/songs/midi/*.s)
SONG_OBJS := $(patsubst sound/songs/midi/%.s,$(OBJ)/songs/%.o,$(SONG_SRCS))

PORT_COMMON := platform bios ppu flash_pc rtc_pc stubs nullguard
# Port files that use the game's own headers and structures.
PORT_GAME := m4a_pc
PORT_OBJS := $(patsubst %,$(OBJ)/pc/%.o,$(PORT_COMMON)) $(patsubst %,$(OBJ)/pcgame/%.o,$(PORT_GAME))

ALL_GAME := $(GAME_OBJS) $(DATA_OBJS) $(SONG_OBJS) $(PORT_OBJS)

.PHONY: all headless sdl asmtree clean
all: headless
headless: $(BUILD)/emerald_headless
sdl: $(BUILD)/emerald

$(BUILD)/emerald_headless: $(ALL_GAME) $(OBJ)/pc/frontend_headless.o
	$(HOST_CC) $(LDFLAGS) -o $@ $^ $(LIBS)

$(BUILD)/emerald: $(ALL_GAME) $(OBJ)/pc/frontend_sdl.o
	$(HOST_CC) $(LDFLAGS) -o $@ $^ $(LIBS) $(shell pkg-config --libs sdl2 2>/dev/null || echo -lSDL2)

$(OBJ)/game/%.o: src/%.c
	@mkdir -p $(@D)
	@echo "cc  $<"
	@$(HOST_CC) -E $(CPPFLAGS) $< | $(PREPROC) -i -g build/assets $< charmap.txt | $(HOST_CC) -x c $(CFLAGS) -c - -o $@

$(OBJ)/pc/%.o: pc/%.c pc/port.h
	@mkdir -p $(@D)
	@echo "cc  $<"
	@$(HOST_CC) $(PC_CFLAGS) $(if $(findstring sdl,$*),$(shell pkg-config --cflags sdl2 2>/dev/null)) -c $< -o $@

$(OBJ)/pcgame/%.o: pc/%.c pc/port.h
	@mkdir -p $(@D)
	@echo "cc  $<"
	@$(HOST_CC) $(CPPFLAGS) $(subst -w,-Wall -Wno-unused-function -Wno-pointer-to-int-cast -Wno-int-to-pointer-cast,$(CFLAGS)) -Ipc -c $< -o $@

# Data assembly is converted to x86 gas syntax in a mirror tree first.
asmtree:
	@python3 -I pc/mkasmtree.py

$(OBJ)/data/%.o: data/%.s | asmtree
	@mkdir -p $(@D)
	@echo "as  $<"
	@cd $(ASMTREE) && ../../../$(PREPROC) $< charmap.txt | cpp -I include - | ../../../$(PREPROC) -ie $< charmap.txt | $(HOST_AS) --32 --divide -o ../../../$@

$(OBJ)/songs/%.o: sound/songs/midi/%.s | asmtree
	@mkdir -p $(@D)
	@cd $(ASMTREE) && $(HOST_AS) --32 --divide -I sound -o ../../../$@ $<

clean:
	rm -rf $(BUILD)
