cmake_minimum_required(VERSION 3.16)
project(B2Online C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if (NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# melonDS, pinned to the same commit HeartGold Online was built from.
# Pass -DMELONDS_DIR=/path/to/melonDS to use a checkout you already have.
set(MELONDS_COMMIT 906e9ebb27da8c6a715cd7abab4abfe8a8d29427)
set(BUILD_QT_SDL OFF CACHE BOOL "" FORCE)
set(ENABLE_OGLRENDERER OFF CACHE BOOL "" FORCE)
set(ENABLE_GDBSTUB OFF CACHE BOOL "" FORCE)
set(ENABLE_LTO_RELEASE OFF CACHE BOOL "" FORCE)
if (MINGW)
    find_library(ONECORE_LIB onecore)
    if (NOT ONECORE_LIB)
        add_library(onecore STATIC cmake/onecore_stub.c)
    endif()
endif()
if (MELONDS_DIR)
    add_subdirectory(${MELONDS_DIR} melonDS EXCLUDE_FROM_ALL)
else()
    include(FetchContent)
    FetchContent_Declare(melonDS GIT_REPOSITORY https://github.com/melonDS-emu/melonDS.git GIT_TAG ${MELONDS_COMMIT})
    FetchContent_GetProperties(melonDS)
    if (NOT melonds_POPULATED)
        FetchContent_Populate(melonDS)
        add_subdirectory(${melonds_SOURCE_DIR} ${melonds_BINARY_DIR} EXCLUDE_FROM_ALL)
    endif()
endif()

find_package(SDL2 REQUIRED)

add_executable(B2Online WIN32
    app/main.cpp
    app/ds_core.cpp
    app/ds_platform.cpp
    app/ds_bridge.c
    app/net.c)
set_target_properties(B2Online PROPERTIES OUTPUT_NAME Black2Online)
target_link_libraries(B2Online PRIVATE core)
target_compile_definitions(B2Online PRIVATE JIT_ENABLED)

if (WIN32)
    target_sources(B2Online PRIVATE app/app.rc)
    if (TARGET SDL2::SDL2-static)
        target_link_libraries(B2Online PRIVATE SDL2::SDL2main SDL2::SDL2-static)
    else()
        target_link_libraries(B2Online PRIVATE SDL2::SDL2main SDL2::SDL2)
    endif()
    target_link_libraries(B2Online PRIVATE ws2_32 iphlpapi winmm imm32 setupapi version ole32 oleaut32 gdi32)
    target_link_options(B2Online PRIVATE -static -static-libgcc -static-libstdc++ $<$<CONFIG:Release>:-s>)
else()
    if (TARGET SDL2::SDL2)
        target_link_libraries(B2Online PRIVATE SDL2::SDL2)
    else()
        target_include_directories(B2Online PRIVATE ${SDL2_INCLUDE_DIRS})
        target_link_libraries(B2Online PRIVATE ${SDL2_LIBRARIES})
    endif()
endif()

# Tests that need no ROM: the mailbox bridge, and two network links talking over loopback.
enable_testing()
add_executable(bridge_test tests/bridge_test.c app/ds_bridge.c)
add_test(NAME bridge COMMAND bridge_test)
add_executable(net_test tests/net_test.c app/net.c app/ds_bridge.c)
if (WIN32)
    target_link_libraries(net_test PRIVATE ws2_32 iphlpapi)
endif()
add_test(NAME net COMMAND net_test)
