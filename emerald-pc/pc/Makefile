# Native PC build of pokeemerald. Run from the repository root:
#   make -f pc/Makefile                  headless test binary (Linux)
#   make -f pc/Makefile sdl              windowed game (Linux, SDL2)
#   make -f pc/Makefile PLATFORM=win     windowed game (Windows .exe, cross-built with MinGW)
# Requires the normal GBA build to have run once (it generates the graphics,
# maps, music and tool binaries this build reuses).

PLATFORM  ?= linux
PREPROC   := tools/preproc/preproc
ASMTREE   := build/pc/asmtree
SDL_MINGW ?= ../sdl2-mingw/i686-w64-mingw32

# The game uses GCC bitfield layout and 32-bit pointers on every platform.
COMMON_CPP := -iquote include -Wno-trigraphs -DMODERN=1 -DPLATFORM_PC -DBUGFIX -std=gnu11
COMMON_C   := -std=gnu11 -O2 -g -funsigned-char -fno-strict-aliasing -fwrapv -fno-stack-protector -fcommon

ifeq ($(PLATFORM),win)
  HOST_CC   := i686-w64-mingw32-gcc
  HOST_AS   := i686-w64-mingw32-as
  OBJCOPY   := i686-w64-mingw32-objcopy
  BUILD     := build/win
  ARCH      := -mno-ms-bitfields
  SYMPREFIX := _
  # Keep the image clear of the GBA address range (0x02000000-0x08000000).
  LDFLAGS   := -static-libgcc -Wl,--image-base,0x10000000 -Wl,--disable-dynamicbase \
               -Wl,--defsym,_gNumMusicPlayers=4 -Wl,--defsym,_gMaxLines=0 -mwindows
  SDL_CFLAGS := -I$(SDL_MINGW)/include/SDL2
  SDL_LIBS   := -L$(SDL_MINGW)/lib -lSDL2
  EXE       := .exe
else
  HOST_CC   := gcc
  HOST_AS   := as
  OBJCOPY   := objcopy
  BUILD     := build/pc
  ARCH      := -m32 -fno-pie
  SYMPREFIX :=
  LDFLAGS   := -m32 -no-pie -z noexecstack -Wl,--defsym,gNumMusicPlayers=4 -Wl,--defsym,gMaxLines=0
  SDL_CFLAGS := $(shell PKG_CONFIG_PATH=/usr/lib/i386-linux-gnu/pkgconfig pkg-config --cflags sdl2 2>/dev/null)
  SDL_LIBS   := $(shell PKG_CONFIG_PATH=/usr/lib/i386-linux-gnu/pkgconfig pkg-config --libs sdl2 2>/dev/null || echo -lSDL2)
  EXE       :=
endif

OBJ       := $(BUILD)/obj
CPPFLAGS  := $(ARCH) $(COMMON_CPP)
CFLAGS    := $(ARCH) $(COMMON_C) -w
PC_CFLAGS := $(ARCH) -std=gnu11 -O2 -g -fno-stack-protector -Wall -Wno-unused-function -Ipc
LIBS      := -lm

# Hardware drivers replaced by pc/*.c
EXCLUDE   := agb_flash agb_flash_1m agb_flash_le agb_flash_mx siirtc
GAME_SRCS := $(filter-out $(addprefix src/,$(addsuffix .c,$(EXCLUDE))),$(wildcard src/*.c))
GAME_OBJS := $(patsubst src/%.c,$(OBJ)/game/%.o,$(GAME_SRCS))

DATA_SRCS := $(wildcard data/*.s)
DATA_OBJS := $(patsubst data/%.s,$(OBJ)/data/%.o,$(DATA_SRCS))
SONG_SRCS := $(wildcard sound/songs/midi/*.s)
SONG_OBJS := $(patsubst sound/songs/midi/%.s,$(OBJ)/songs/%.o,$(SONG_SRCS))

PORT_COMMON := platform bios ppu flash_pc rtc_pc stubs nullguard script hdpack
# Port files that use the game's own headers and structures.
PORT_GAME := m4a_pc texthd
PORT_OBJS := $(patsubst %,$(OBJ)/pc/%.o,$(PORT_COMMON)) $(patsubst %,$(OBJ)/pcgame/%.o,$(PORT_GAME))

ALL_GAME := $(GAME_OBJS) $(DATA_OBJS) $(SONG_OBJS) $(PORT_OBJS)

.PHONY: all headless sdl asmtree clean
ifeq ($(PLATFORM),win)
all: $(BUILD)/emerald.exe
else
all: headless
endif
headless: $(BUILD)/emerald_headless$(EXE)
sdl: $(BUILD)/emerald$(EXE)

$(BUILD)/emerald_headless$(EXE): $(ALL_GAME) $(OBJ)/pc/frontend_headless.o $(OBJ)/pcgame/testhooks.o
	$(HOST_CC) $(LDFLAGS) -o $@ $^ $(LIBS)

$(BUILD)/emerald$(EXE): $(ALL_GAME) $(OBJ)/pc/frontend_sdl.o $(OBJ)/pc/render_gl.o $(OBJ)/pcgame/testhooks.o
	$(HOST_CC) $(LDFLAGS) -o $@ $^ $(LIBS) $(SDL_LIBS)
ifeq ($(PLATFORM),win)
	cp $(SDL_MINGW)/bin/SDL2.dll $(BUILD)/
endif

$(OBJ)/game/%.o: src/%.c
	@mkdir -p $(@D)
	@echo "cc  $<"
	@$(HOST_CC) -E $(CPPFLAGS) $< | $(PREPROC) -i -g build/assets $< charmap.txt | $(HOST_CC) -x c $(CFLAGS) -c - -o $@

$(OBJ)/pc/%.o: pc/%.c pc/port.h pc/render_gl.h pc/script.h pc/hdpack.h pc/texthd.h
	@mkdir -p $(@D)
	@echo "cc  $<"
	@$(HOST_CC) $(PC_CFLAGS) $(if $(filter frontend_sdl render_gl,$*),$(SDL_CFLAGS)) -c $< -o $@

$(OBJ)/pcgame/%.o: pc/%.c pc/port.h
	@mkdir -p $(@D)
	@echo "cc  $<"
	@$(HOST_CC) $(CPPFLAGS) $(COMMON_C) -Wall -Wno-unused-function -Wno-pointer-to-int-cast -Wno-int-to-pointer-cast -Ipc -c $< -o $@

# Data assembly is converted to x86 gas syntax in a mirror tree first. On
# Windows, C symbols carry a leading underscore, so the assembled data gets
# the same prefix.
asmtree:
	@python3 -I pc/mkasmtree.py

define ASM_FIXUP
$(if $(SYMPREFIX),&& $(OBJCOPY) --prefix-symbols=$(SYMPREFIX) $(1) $(1))
endef

$(OBJ)/data/%.o: data/%.s | asmtree
	@mkdir -p $(@D)
	@echo "as  $<"
	@cd $(ASMTREE) && ../../../$(PREPROC) $< charmap.txt | cpp -I include - | ../../../$(PREPROC) -ie $< charmap.txt | $(HOST_AS) --32 --divide -o ../../../$@ $(call ASM_FIXUP,../../../$@)

$(OBJ)/songs/%.o: sound/songs/midi/%.s | asmtree
	@mkdir -p $(@D)
	@cd $(ASMTREE) && $(HOST_AS) --32 --divide -I sound -o ../../../$@ $< $(call ASM_FIXUP,../../../$@)

clean:
	rm -rf $(BUILD)
