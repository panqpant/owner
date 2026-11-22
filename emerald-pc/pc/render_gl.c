// OpenGL renderer: upscales each GBA layer separately on the GPU and
// composites them at high resolution with the GBA's priority, window and
// colour-effect rules.
//
//   pass 1  xBR edge-directed upscale of BG0-3 and OBJ (each 240x160 -> S x)
//   pass 2  composite at S x: priorities, windows, alpha blending, fades
//   pass 3  present to the window (aspect-correct, optional colour grade)
//
// "Original" mode skips passes 1-2 and draws the CPU-composited frame with
// nearest-neighbour scaling.
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include <stdlib.h>
#include <SDL.h>
#include "port.h"
#include "render_gl.h"
#include "hdpack.h"
#include "texthd.h"
#include "fieldfx.h"
#include "wondertrade.h"

typedef unsigned int GLenum, GLuint, GLbitfield;
typedef int GLint, GLsizei;
typedef float GLfloat;
typedef char GLchar;
typedef unsigned char GLboolean;

#define GL_TEXTURE_2D 0x0DE1
#define GL_TEXTURE0 0x84C0
#define GL_TEXTURE_MIN_FILTER 0x2801
#define GL_TEXTURE_MAG_FILTER 0x2800
#define GL_TEXTURE_WRAP_S 0x2802
#define GL_TEXTURE_WRAP_T 0x2803
#define GL_NEAREST 0x2600
#define GL_LINEAR 0x2601
#define GL_CLAMP_TO_EDGE 0x812F
#define GL_RGBA 0x1908
#define GL_RGBA8 0x8058
#define GL_RGBA8UI 0x8D7C
#define GL_RGBA16UI 0x8D76
#define GL_UNSIGNED_SHORT 0x1403
#define GL_RG8 0x822B
#define GL_RG 0x8227
#define GL_R16UI 0x8234
#define GL_RED_INTEGER 0x8D94
#define GL_RGBA_INTEGER 0x8D99
#define GL_UNSIGNED_BYTE 0x1401
#define GL_FRAGMENT_SHADER 0x8B30
#define GL_VERTEX_SHADER 0x8B31
#define GL_COMPILE_STATUS 0x8B81
#define GL_LINK_STATUS 0x8B82
#define GL_FRAMEBUFFER 0x8D40
#define GL_COLOR_ATTACHMENT0 0x8CE0
#define GL_FRAMEBUFFER_COMPLETE 0x8CD5
#define GL_COLOR_BUFFER_BIT 0x4000
#define GL_TRIANGLES 0x0004
#define GL_UNPACK_ALIGNMENT 0x0CF5
#define GL_UNPACK_ROW_LENGTH 0x0CF2
#define GL_PACK_ALIGNMENT 0x0D05
#define GL_BGRA 0x80E1

#define GLFUNCS \
    X(void, glGenTextures, (GLsizei, GLuint *)) \
    X(void, glBindTexture, (GLenum, GLuint)) \
    X(void, glTexImage2D, (GLenum, GLint, GLint, GLsizei, GLsizei, GLint, GLenum, GLenum, const void *)) \
    X(void, glTexSubImage2D, (GLenum, GLint, GLint, GLint, GLsizei, GLsizei, GLenum, GLenum, const void *)) \
    X(void, glTexParameteri, (GLenum, GLenum, GLint)) \
    X(void, glActiveTexture, (GLenum)) \
    X(void, glPixelStorei, (GLenum, GLint)) \
    X(void, glViewport, (GLint, GLint, GLsizei, GLsizei)) \
    X(void, glClearColor, (GLfloat, GLfloat, GLfloat, GLfloat)) \
    X(void, glClear, (GLbitfield)) \
    X(void, glDrawArrays, (GLenum, GLint, GLsizei)) \
    X(void, glReadPixels, (GLint, GLint, GLsizei, GLsizei, GLenum, GLenum, void *)) \
    X(void, glCopyTexSubImage2D, (GLenum, GLint, GLint, GLint, GLint, GLint, GLsizei, GLsizei)) \
    X(GLenum, glGetError, (void)) \
    X(GLuint, glCreateShader, (GLenum)) \
    X(void, glShaderSource, (GLuint, GLsizei, const GLchar *const *, const GLint *)) \
    X(void, glCompileShader, (GLuint)) \
    X(void, glGetShaderiv, (GLuint, GLenum, GLint *)) \
    X(void, glGetShaderInfoLog, (GLuint, GLsizei, GLsizei *, GLchar *)) \
    X(void, glDeleteShader, (GLuint)) \
    X(GLuint, glCreateProgram, (void)) \
    X(void, glAttachShader, (GLuint, GLuint)) \
    X(void, glLinkProgram, (GLuint)) \
    X(void, glGetProgramiv, (GLuint, GLenum, GLint *)) \
    X(void, glGetProgramInfoLog, (GLuint, GLsizei, GLsizei *, GLchar *)) \
    X(void, glUseProgram, (GLuint)) \
    X(GLint, glGetUniformLocation, (GLuint, const GLchar *)) \
    X(void, glUniform1i, (GLint, GLint)) \
    X(void, glUniform1f, (GLint, GLfloat)) \
    X(void, glUniform2f, (GLint, GLfloat, GLfloat)) \
    X(void, glUniform4f, (GLint, GLfloat, GLfloat, GLfloat, GLfloat)) \
    X(void, glUniform3f, (GLint, GLfloat, GLfloat, GLfloat)) \
    X(void, glUniform1iv, (GLint, GLsizei, const GLint *)) \
    X(void, glUniform3fv, (GLint, GLsizei, const GLfloat *)) \
    X(void, glUniform4fv, (GLint, GLsizei, const GLfloat *)) \
    X(void, glUniform1fv, (GLint, GLsizei, const GLfloat *)) \
    X(void, glGenVertexArrays, (GLsizei, GLuint *)) \
    X(void, glBindVertexArray, (GLuint)) \
    X(void, glGenFramebuffers, (GLsizei, GLuint *)) \
    X(void, glBindFramebuffer, (GLenum, GLuint)) \
    X(void, glFramebufferTexture2D, (GLenum, GLenum, GLenum, GLuint, GLint)) \
    X(GLenum, glCheckFramebufferStatus, (GLenum)) \
    X(void, glDeleteTextures, (GLsizei, const GLuint *)) \

#ifdef _WIN32
#define GLAPIENTRY __stdcall
#else
#define GLAPIENTRY
#endif

#define X(ret, name, args) static ret (GLAPIENTRY *p_##name) args;
GLFUNCS
#undef X

#define glGenTextures p_glGenTextures
#define glBindTexture p_glBindTexture
#define glTexImage2D p_glTexImage2D
#define glTexSubImage2D p_glTexSubImage2D
#define glTexParameteri p_glTexParameteri
#define glActiveTexture p_glActiveTexture
#define glPixelStorei p_glPixelStorei
#define glViewport p_glViewport
#define glClearColor p_glClearColor
#define glClear p_glClear
#define glDrawArrays p_glDrawArrays
#define glReadPixels p_glReadPixels
#define glCopyTexSubImage2D p_glCopyTexSubImage2D
#define glGetError p_glGetError
#define glCreateShader p_glCreateShader
#define glShaderSource p_glShaderSource
#define glCompileShader p_glCompileShader
#define glGetShaderiv p_glGetShaderiv
#define glGetShaderInfoLog p_glGetShaderInfoLog
#define glDeleteShader p_glDeleteShader
#define glCreateProgram p_glCreateProgram
#define glAttachShader p_glAttachShader
#define glLinkProgram p_glLinkProgram
#define glGetProgramiv p_glGetProgramiv
#define glGetProgramInfoLog p_glGetProgramInfoLog
#define glUseProgram p_glUseProgram
#define glGetUniformLocation p_glGetUniformLocation
#define glUniform1i p_glUniform1i
#define glUniform1f p_glUniform1f
#define glUniform2f p_glUniform2f
#define glUniform4f p_glUniform4f
#define glUniform3f p_glUniform3f
#define glUniform1iv p_glUniform1iv
#define glUniform3fv p_glUniform3fv
#define glUniform4fv p_glUniform4fv
#define glUniform1fv p_glUniform1fv
#define glGenVertexArrays p_glGenVertexArrays
#define glBindVertexArray p_glBindVertexArray
#define glGenFramebuffers p_glGenFramebuffers
#define glBindFramebuffer p_glBindFramebuffer
#define glFramebufferTexture2D p_glFramebufferTexture2D
#define glCheckFramebufferStatus p_glCheckFramebufferStatus
#define glDeleteTextures p_glDeleteTextures

// ---------------------------------------------------------------------------
// Shaders

static const char *kVert =
    "#version 330 core\n"
    "out vec2 vUv;\n"
    "void main() {\n"
    "  vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);\n"
    "  vUv = p;\n"
    "  gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);\n"
    "}\n";

// Hyllian's xBR 4x (the algorithm in FFmpeg's vf_xbr, verified against it
// with pc/tools/xbr_ref.c), extended to premultiplied RGBA so that edges
// against transparent pixels are smoothed too. Each output pixel rebuilds
// its source pixel's 4x4 block through the four corner rotations.
static const char *kXbr =
    "#version 330 core\n"
    "in vec2 vUv;\n"
    "out vec4 oColor;\n"
    "uniform sampler2D uTex;\n"
    "uniform vec2 uSize;\n"
    "uniform float uScale;\n"
    "ivec2 gBase;\n"
    "vec4 P(int dx, int dy) {\n"
    "  ivec2 q = clamp(gBase + ivec2(dx, dy), ivec2(0), ivec2(uSize) - 1);\n"
    "  vec4 t = texelFetch(uTex, q, 0);\n"
    "  return vec4(t.rgb * t.a, t.a);\n"
    "}\n"
    "float df(vec4 a, vec4 b) {\n"
    "  vec3 d = (a.rgb - b.rgb) * 255.0;\n"
    "  float y = abs(dot(d, vec3(0.299, 0.587, 0.114)));\n"
    "  float u = abs(dot(d, vec3(-0.169, -0.331, 0.5)));\n"
    "  float v = abs(dot(d, vec3(0.5, -0.419, -0.081)));\n"
    "  return y + u + v + abs(a.a - b.a) * 255.0;\n"
    "}\n"
    "bool eq(vec4 a, vec4 b) { return df(a, b) < 155.0; }\n"
    "bool ne(vec4 a, vec4 b) { return any(notEqual(a, b)); }\n"
    "ivec2 R(ivec2 p, int k) { for (int i = 0; i < k; i++) p = ivec2(p.y, -p.x); return p; }\n"
    "void main() {\n"
    "  vec2 pos = vUv * uSize;\n"
    "  gBase = ivec2(floor(pos));\n"
    "  ivec2 sub = clamp(ivec2(floor(fract(pos) * 4.0)), ivec2(0), ivec2(3));\n"
    "  int me = sub.y * 4 + sub.x;\n"
    "  vec4 E0 = P(0, 0);\n"
    "  vec4 Eb[16];\n"
    "  for (int i = 0; i < 16; i++) Eb[i] = E0;\n"
    "  for (int k = 0; k < 4; k++) {\n"
    "    ivec2 o;\n"
    "    o = R(ivec2(1, 1), k);   vec4 PI = P(o.x, o.y);\n"
    "    o = R(ivec2(0, 1), k);   vec4 PH = P(o.x, o.y);\n"
    "    o = R(ivec2(1, 0), k);   vec4 PF = P(o.x, o.y);\n"
    "    o = R(ivec2(-1, 1), k);  vec4 PG = P(o.x, o.y);\n"
    "    o = R(ivec2(1, -1), k);  vec4 PC = P(o.x, o.y);\n"
    "    o = R(ivec2(-1, 0), k);  vec4 PD = P(o.x, o.y);\n"
    "    o = R(ivec2(0, -1), k);  vec4 PB = P(o.x, o.y);\n"
    "    o = R(ivec2(0, 2), k);   vec4 H5 = P(o.x, o.y);\n"
    "    o = R(ivec2(2, 0), k);   vec4 F4 = P(o.x, o.y);\n"
    "    o = R(ivec2(1, 2), k);   vec4 I5 = P(o.x, o.y);\n"
    "    o = R(ivec2(2, 1), k);   vec4 I4 = P(o.x, o.y);\n"
    "    vec4 PE = E0;\n"
    "    if (!(ne(PE, PH) && ne(PE, PF))) continue;\n"
    "    float e = df(PE, PC) + df(PE, PG) + df(PI, H5) + df(PI, F4) + 4.0 * df(PH, PF);\n"
    "    float ii = df(PH, PD) + df(PH, I5) + df(PF, I4) + df(PF, PB) + 4.0 * df(PE, PI);\n"
    "    if (e > ii) continue;\n"
    // Subpixel indices: corner + a*u + b*v (u along the H edge, v along the F edge).
    "    ivec2 c2 = R(ivec2(3, 3) * 2 - 3, k);\n"
    "    ivec2 corner = (c2 + 3) / 2;\n"
    "    ivec2 u = R(ivec2(-1, 0), k), v = R(ivec2(0, -1), k);\n"
    "    ivec2 q;\n"
    "    q = corner;            int N15 = q.y * 4 + q.x;\n"
    "    q = corner + u;        int N14 = q.y * 4 + q.x;\n"
    "    q = corner + 2 * u;    int N13 = q.y * 4 + q.x;\n"
    "    q = corner + 3 * u;    int N12 = q.y * 4 + q.x;\n"
    "    q = corner + v;        int N11 = q.y * 4 + q.x;\n"
    "    q = corner + 2 * v;    int N7 = q.y * 4 + q.x;\n"
    "    q = corner + 3 * v;    int N3 = q.y * 4 + q.x;\n"
    "    q = corner + u + v;    int N10 = q.y * 4 + q.x;\n"
    "    vec4 px = df(PE, PF) <= df(PE, PH) ? PF : PH;\n"
    "    if (e < ii && ((!eq(PF, PB) && !eq(PH, PD)) || (eq(PE, PI) && (!eq(PF, I4) || !eq(PH, I5))) || eq(PE, PG) || eq(PE, PC))) {\n"
    "      float ke = df(PF, PG), ki = df(PH, PC);\n"
    "      bool left = 2.0 * ke <= ki && ne(PE, PG) && ne(PD, PG);\n"
    "      bool up = ke >= 2.0 * ki && ne(PE, PC) && ne(PB, PC);\n"
    "      if (left && up) {\n"
    "        Eb[N13] = mix(Eb[N13], px, 0.75); Eb[N12] = mix(Eb[N12], px, 0.25);\n"
    "        Eb[N15] = px; Eb[N14] = px; Eb[N11] = px;\n"
    "        Eb[N10] = Eb[N12]; Eb[N3] = Eb[N12]; Eb[N7] = Eb[N13];\n"
    "      } else if (left) {\n"
    "        Eb[N11] = mix(Eb[N11], px, 0.75); Eb[N13] = mix(Eb[N13], px, 0.75);\n"
    "        Eb[N10] = mix(Eb[N10], px, 0.25); Eb[N12] = mix(Eb[N12], px, 0.25);\n"
    "        Eb[N14] = px; Eb[N15] = px;\n"
    "      } else if (up) {\n"
    "        Eb[N14] = mix(Eb[N14], px, 0.75); Eb[N7] = mix(Eb[N7], px, 0.75);\n"
    "        Eb[N10] = mix(Eb[N10], px, 0.25); Eb[N3] = mix(Eb[N3], px, 0.25);\n"
    "        Eb[N11] = px; Eb[N15] = px;\n"
    "      } else {\n"
    "        Eb[N11] = mix(Eb[N11], px, 0.5); Eb[N14] = mix(Eb[N14], px, 0.5);\n"
    "        Eb[N15] = px;\n"
    "      }\n"
    "    } else {\n"
    "      Eb[N15] = mix(Eb[N15], px, 0.5);\n"
    "    }\n"
    "  }\n"
    "  oColor = Eb[me];\n" // premultiplied RGBA
    "}\n";

// Composite the upscaled layers using the GBA's per-pixel rules.
static const char *kComposite =
    "#version 330 core\n"
    "in vec2 vUv;\n"
    "out vec4 oColor;\n"
    "uniform sampler2D uLayer[5];\n"   // premultiplied, upscaled (or native, nearest)
    "uniform sampler2D uFlat;\n"       // the original flattened frame, upscaled
    "uniform usampler2D uMeta;\n"
    "uniform usampler2D uLine;\n"
    "uniform vec2 uDim;\n"        // native frame size (W, 160)
    "uniform vec2 uContent;\n"    // visible content columns [x0, x1); outside is pillarbox
    "uniform usampler2D uTref[5];\n"
    "uniform sampler2D uAtlas;\n"
    "uniform int uHasPack;\n"
    "uniform float uPackScale;\n"
    "uniform int uPerRow;\n"
    "uniform sampler2D uGlyphs;\n"   // high-resolution glyph coverage: R = text, G = shadow
    "uniform usampler2D uPal;\n"     // live palette (BGR555), 512 entries
    "uniform float uGlyphScale;\n"
    "uniform vec4 uTint;\n"   // rgb multiplier, a = 1 to apply (outdoor overworld)
    "uniform int uFieldFx;\n"
    "uniform float uNight;\n"
    "uniform float uMargin;\n"
    "uniform int uNumLights, uNumShadows;\n"
    "uniform vec3 uLights[24];\n"   // x, y (GBA screen coords), radius
    "uniform vec3 uShadows[32];\n"  // feet x, y, width
    "uniform vec3 uShadowLight[32];\n"  // per character: shadow direction from the nearest light (x, y per px of height), strength
    "uniform int uWeather;\n"       // 1 rain, 2 downpour, 3 sandstorm
    "uniform vec4 uLiveWx;\n"       // live weather: x cloud, y rain amount (0-1), z fog, w rainbow
    "uniform float uWet;\n"         // how wet the ground is (dries slowly after rain)
    "uniform float uTime;\n"
    "uniform vec4 uGridPos;\n"      // grid cell (0,0): screen x, y; map x, y
    "uniform int uGrid[144];\n"     // 36x16 metatile flags, 4 per int (PC_CELL_*)
    "uniform vec4 uSun;\n"          // xy: shadow vector (GBA px), z: shadow strength, w: daylight
    "uniform int uMapType;\n"
    "uniform float uForest;\n"
    "uniform vec4 uKey;\n"
    "uniform float uFlash;\n"
    "uniform vec2 uPlayer;\n"
    "uniform vec3 uWake[12];\n"     // player's recent world positions (map px) and when (uTime); z < 0 unused
    "uniform vec3 uLife;\n"
    "uniform vec4 uInSun;\n"
    "uniform vec3 uGrassDark, uGrassLight;\n"
    "uniform float uTilt;\n"
    "uniform vec3 uCineZoom;\n"
    "uniform sampler2D uFollow;\n"   // following Pokémon icon (2 frames, 32x64)
    "uniform vec4 uFollowPos;\n"     // top-left x, y (GBA px), flip, frame
    "uniform vec2 uFollowOn;\n"      // x on, y feet y (draw order)     // cinematic camera: focus (uv), zoom
    "uniform int uMood;\n"
    "uniform int uSeason;\n"        // 0 spring, 1 summer, 2 autumn, 3 winter
    "uniform sampler2D uGi;\n"      // ray-traced light (native res)
    "uniform float uGiOn;\n"
    "uniform int uMenu;\n"          // menu screen kind (0 none)
    "uniform vec3 uMenuBg1, uMenuBg2;\n"
    "uniform int uPanels;\n"        // HD window panels (frames the game no longer draws)
    "uniform vec4 uPanel[16];\n"    // window rect x, y, w, h (native px incl. margin)
    "uniform vec4 uPanelT[16];\n"   // window fill colour (follows screen fades), dialogue style
    "uniform int uCards;\n"         // party screen: slot cards drawn by the renderer (0 none)
    "uniform vec4 uCard[6];\n"      // x, y, w, h (native px incl. margin)
    "uniform vec4 uCardBar[6];\n"   // HP bar x, y, w (0: none), HP fraction
    "uniform float uCardState[6];\n"   // 1 present, 2 cursor, 4 fainted, 8 picked to move   // the menu's background pattern colours        // HD-2D tilt strength (0 = flat)   // this screen's tall grass colours        // indoors: direction sunlight travels from windows (x, y), strength, night         // x: water fraction on screen, y: volcanic ash, z: heat haze
    "uniform int uBattle;\n"        // battle scene lighting on
    "uniform vec4 uMon[4];\n"       // battler sprite rects x, y, w, h (w = 0: none)
    "uniform vec3 uMonFeet[4];\n"   // feet x, y; half width
    "uniform vec4 uBTint;\n"        // time-of-day colour, a = 1 outdoors
    "uniform vec3 uBShadow;\n"      // shadow direction per px of height (x, y), strength
    "uniform vec4 uMoveLight;\n"    // move effects as a light: x, y, strength, radius
    "uniform vec3 uMoveColor;\n"
    "uniform int uScene;\n"
    "uniform vec3 uCam;\n"          // battle camera: centre (uv), zoom
    "uniform vec2 uShake;\n"        // camera shake offset, GBA px
    "uniform float uBoxTop;\n"      // battle message box top line
    "uniform int uMoveType;\n"      // type of the move being animated (-1 none)
    "uniform float uMoveFx;\n"      // its effect strength 0-1         // procedural battle backdrop (-1 = the game's art)
    "uniform vec3 uSkyTop, uSkyHor;\n"
    "uniform vec3 uSunPos;\n"       // sun (z = 1) or moon (z = 0) position, GBA px; z = -1 none
    "uniform float uNightB;\n"
    "uniform vec3 uBLight;\n"       // colour of the light at this hour       // player's feet (GBA screen coords)       // lightning, 0-1          // key light: direction towards the light (x, y down, z up), strength      // fraction of scenery around: light shafts
    "vec2 gUpSize, gUpFw;\n"
    "bool gZoomField = false;\n"   // field view is zoomed: the flattened frame (uFlat) no longer lines up
    // Sharp magnification of the upscaled layers: each upscaled pixel stays
    // solid and only the 1-output-pixel seam between neighbours is blended.
    "vec2 SharpUv(vec2 uv) {\n"
    "  vec2 p = uv * gUpSize, seam = floor(p + 0.5);\n"
    "  p = seam + clamp((p - seam) / max(gUpFw, vec2(1e-4)), -0.5, 0.5);\n"
    "  return p / gUpSize;\n"
    "}\n"
    "vec4 TexS(sampler2D t, vec2 uv) { return texture(t, SharpUv(uv)); }\n"
    "float Hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }\n"
    "float Rain(vec2 p, float t, float scale, float speed, float density) {\n"
    "  p.x += p.y * 0.22;\n"
    "  vec2 q = vec2(p.x / scale, p.y / (scale * 7.0) - t * speed);\n"
    "  vec2 cell = floor(q), f = fract(q);\n"
    "  if (Hash(cell) > density) return 0.0;\n"
    "  float x0 = 0.15 + 0.7 * Hash(cell + 7.31);\n"
    "  float d = abs(f.x - x0) * scale;\n"
    "  return (1.0 - smoothstep(0.0, 0.55, d)) * smoothstep(0.0, 0.35, f.y) * (1.0 - smoothstep(0.65, 1.0, f.y));\n"
    "}\n"
    "float Noise(vec2 p) {\n"
    "  vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);\n"
    "  return mix(mix(Hash(i), Hash(i + vec2(1, 0)), f.x), mix(Hash(i + vec2(0, 1)), Hash(i + vec2(1, 1)), f.x), f.y);\n"
    "}\n"
    "int Cell(ivec2 c) {\n"
    "  if (c.x < 0 || c.y < 0 || c.x >= 36 || c.y >= 16) return 0;\n"
    "  int i = c.y * 36 + c.x;\n"
    "  return (uGrid[i >> 2] >> ((i & 3) * 8)) & 255;\n"
    "}\n"
    "vec2 CellPos(vec2 gp) { return (gp - uGridPos.xy) / 16.0; }\n"
    // Smooth 0..1 field of solid scenery (rounded corners, ~6 px soft edge).
    "float Solid(vec2 gp) {\n"
    "  vec2 q = CellPos(gp) - 0.5; ivec2 i = ivec2(floor(q)); vec2 f = fract(q);\n"
    "  float a = float(Cell(i) & 1), b = float(Cell(i + ivec2(1, 0)) & 1);\n"
    "  float c = float(Cell(i + ivec2(0, 1)) & 1), d = float(Cell(i + ivec2(1, 1)) & 1);\n"
    "  return smoothstep(0.12, 0.88, mix(mix(a, b, f.x), mix(c, d, f.x), f.y));\n"
    "}\n"
    // A character's own sprite silhouette projected onto the ground: a point
    // h px above the feet lands at feet + h * k.
    "float Sil(vec2 g, vec3 s, vec2 k) {\n"
    "  if (abs(k.y) < 0.15) k.y = k.y < 0.0 ? -0.15 : 0.15;\n"
    "  float h = (g.y - s.y) / k.y;\n"
    "  if (h < 0.0 || h > 34.0) return 0.0;\n"
    "  vec2 sp = vec2(g.x - h * k.x, s.y - h);\n"
    "  if (abs(sp.x - s.x) > s.z * 0.75) return 0.0;\n"
    "  vec2 suv = vec2((sp.x + uMargin) / uDim.x, sp.y / uDim.y);\n"
    "  float a = texture(uLayer[4], suv).a + texture(uLayer[4], suv + vec2(0.6 / uDim.x, 0.0)).a;\n"
    "  return min(a * 0.5, 1.0) * (1.0 - smoothstep(8.0, 34.0, h) * 0.55);\n"   // softer toward the head
    "}\n"
    // Depth inside solid scenery (0 at its edge, 1 three tiles in), smooth.
    "float Depth(vec2 gp) {\n"
    "  vec2 q = CellPos(gp) - 0.5; ivec2 i = ivec2(floor(q)); vec2 f = fract(q); f = f * f * (3.0 - 2.0 * f);\n"
    "  float a = float(Cell(i) >> 6), b = float(Cell(i + ivec2(1, 0)) >> 6);\n"
    "  float c = float(Cell(i + ivec2(0, 1)) >> 6), d = float(Cell(i + ivec2(1, 1)) >> 6);\n"
    "  return mix(mix(a, b, f.x), mix(c, d, f.x), f.y) / 3.0;\n"
    "}\n"
    "float LumL(int k, vec2 q, float centre) {\n"   // relief height: art luminance for scenery, outline for sprites
    "  if (k == 4) return texture(uLayer[4], q).a;\n"
    "  vec4 c = k == 1 ? texture(uLayer[1], q) : k == 2 ? texture(uLayer[2], q) : texture(uLayer[3], q);\n"
    "  if (c.a < 0.95) return centre;\n"   // a layer edge is not a bump in the surface
    "  return dot(c.rgb, vec3(0.3, 0.59, 0.11));\n"
    "}\n"
    // The scene mirrored about a horizontal line (a shoreline or the base of
    // a wall): what a reflective surface below that line shows.
    "vec4 MirrorScene(vec2 m, bool sprites) {\n"
    "  vec2 muv = vec2((m.x + uMargin) / uDim.x, m.y / uDim.y);\n"
    "  if (muv.y < 0.0 || muv.y > 1.0) return vec4(0.0);\n"
    "  ivec2 mnp = clamp(ivec2(floor(vec2(m.x + uMargin, m.y))), ivec2(0), ivec2(uDim) - 1);\n"
    "  uint mm = texelFetch(uMeta, mnp, 0).r;\n"
    "  if ((mm & 6u) != 6u || TexS(uLayer[0], muv).a > 0.0) return vec4(0.0);\n"   // hidden by a window or a text box
    "  vec4 a = TexS(uLayer[1], muv), b = TexS(uLayer[2], muv);\n"
    "  vec4 c = vec4(a.rgb + b.rgb * (1.0 - a.a), a.a + b.a * (1.0 - a.a));\n"
    "  c *= Solid(m);\n"   // objects only, never the ground
    "  if (sprites) { vec4 o = TexS(uLayer[4], muv); c = vec4(o.rgb + c.rgb * (1.0 - o.a), o.a + c.a * (1.0 - o.a)); }\n"
    "  return c;\n"
    "}\n"
    // Characters reflected below their feet.
    "vec4 MirrorChars(vec2 gp) {\n"
    "  vec4 acc = vec4(0.0);\n"
    "  for (int k = 0; k < uNumShadows; k++) {\n"
    "    vec3 s = uShadows[k];\n"
    "    float dy = gp.y - s.y;\n"
    "    if (dy < -2.0 || dy > 34.0 || abs(gp.x - s.x) > s.z) continue;\n"
    "    vec2 m = vec2(gp.x + sin(gp.y * 0.6 + uTime * 3.0) * 0.5, s.y - dy - 1.0);\n"
    "    vec2 muv = vec2((m.x + uMargin) / uDim.x, m.y / uDim.y);\n"
    "    vec4 o = TexS(uLayer[4], muv);\n"
    "    o *= 1.0 - smoothstep(10.0, 34.0, dy);\n"
    "    acc = o + acc * (1.0 - o.a);\n"
    "  }\n"
    "  return acc;\n"
    "}\n"
    "float Puddles(vec2 wp) {\n"   // where rain collects: irregular patches
    "  float n = Noise(wp * 0.045) * 0.65 + Noise(wp * 0.11 + 9.0) * 0.35;\n"
    "  return smoothstep(0.48, 0.62, n);\n"
    "}\n"
    "float SilH(vec2 g, vec3 s, vec2 k, float hmax) {\n"
    "  if (abs(k.y) < 0.15) k.y = k.y < 0.0 ? -0.15 : 0.15;\n"
    "  float h = (g.y - s.y) / k.y;\n"
    "  if (h < 0.0 || h > hmax) return 0.0;\n"
    "  vec2 sp = vec2(g.x - h * k.x, s.y - h);\n"
    "  if (abs(sp.x - s.x) > s.z) return 0.0;\n"
    "  return texture(uLayer[4], vec2((sp.x + uMargin) / uDim.x, sp.y / uDim.y)).a * (1.0 - smoothstep(hmax * 0.3, hmax, h) * 0.6);\n"
    "}\n"
    "int MonAt(vec2 gp) {\n"
    "  if ((gp.y >= 74.0 && gp.y < 114.0 && gp.x >= 118.0) || (gp.y < 46.0 && gp.x < 120.0)) return -1;\n"   // health boxes
    "  for (int k = 0; k < 4; k++) { vec4 m = uMon[k]; if (m.z > 0.0 && gp.x >= m.x && gp.x < m.x + m.z && gp.y >= m.y && gp.y < m.y + m.w) return k; }\n"
    "  return -1;\n"
    "}\n"
    "#define BD_H 46.0\n"
    // ---- Procedural battle backdrops (sky, scenery, ground, platforms) ----
    "float Fbm(vec2 p) { float a = 0.5, s = 0.0; for (int i = 0; i < 4; i++) { s += a * Noise(p); p = p * 2.03 + 7.1; a *= 0.5; } return s; }\n"
    "float Ell(vec2 p, vec4 e) { vec2 d = (p - e.xy) / e.zw; return length(d); }\n"
    "vec3 Fog(vec3 c, float y, float amt) { return mix(c, uSkyHor, amt); }\n"
    // Sky with sun or moon, stars and clouds.
    "vec3 Sky(vec2 p) {\n"
    "  float t = clamp(p.y / BD_H, 0.0, 1.0);\n"
    "  vec3 c = mix(uSkyTop, uSkyHor, pow(t, 1.4));\n"
    // stars
    "  vec2 sc = floor(p * 0.9);\n"
    "  float st = step(0.985, Hash(sc)) * (0.6 + 0.4 * sin(uTime * (1.0 + Hash(sc + 3.0) * 3.0) + Hash(sc) * 40.0));\n"
    "  c += vec3(0.9, 0.95, 1.0) * st * uNightB * (1.0 - t * 0.7);\n"
    // sun / moon
    "  float d = distance(p, uSunPos.xy);\n"
    "  if (uSunPos.z > 0.5) {\n"
    "    vec3 sunc = mix(vec3(1.0, 0.75, 0.45), vec3(1.0, 0.97, 0.88), clamp((BD_H - uSunPos.y) / 30.0, 0.0, 1.0));\n"
    "    c = mix(c, sunc * 1.15, 1.0 - smoothstep(5.0, 6.0, d));\n"
    "    c += sunc * 0.35 * exp(-d * 0.06) + sunc * 0.15 * exp(-d * 0.015);\n"
    "  } else if (uSunPos.z > -0.5 && uNightB > 0.3) {\n"
    "    vec3 moonc = vec3(0.92, 0.94, 1.0);\n"
    "    float m = 1.0 - smoothstep(4.0, 4.8, d);\n"
    "    float cres = 1.0 - smoothstep(3.6, 4.4, distance(p, uSunPos.xy + vec2(1.8, -1.0)));\n"
    "    c = mix(c, moonc, m * (1.0 - cres * 0.85));\n"
    "    c += moonc * 0.12 * exp(-d * 0.05) * uNightB;\n"
    "  }\n"
    // clouds drifting
    "  vec2 q = vec2(p.x * 0.018 + uTime * 0.01, p.y * 0.05);\n"
    "  float cl = smoothstep(0.52, 0.75, Fbm(q)) * (1.0 - t * 0.5);\n"
    "  vec3 cloudc = mix(vec3(1.0), uSkyHor * 1.1, 0.35) * mix(1.0, 0.35, uNightB);\n"
    "  c = mix(c, cloudc, cl * 0.85);\n"
    "  return c;\n"
    "}\n"
    // Ground plane in perspective: z grows toward the horizon.
    "vec2 GroundUv(vec2 p) {\n"
    "  float dy = max(p.y - BD_H, 0.5);\n"
    "  float z = 40.0 / dy;\n"
    "  return vec2((p.x - 120.0) * z * 0.05, z);\n"
    "}\n"
    "vec3 GroundCol(vec2 p, int sc) {\n"
    "  vec2 g = GroundUv(p);\n"
    "  vec2 gr = mat2(0.88, 0.48, -0.48, 0.88) * g + vec2(3.7, 1.3);\n"   // rotated: no noise-grid lines toward the vanishing point
    "  float n = Fbm(gr * vec2(1.0, 1.6));\n"
    "  vec3 c;\n"
    "  if (sc == 4) {            // sand with ripples\n"
    "    c = mix(vec3(0.86, 0.74, 0.50), vec3(0.95, 0.84, 0.60), n);\n"
    "    c *= 0.93 + 0.07 * sin(g.y * 7.0 + sin(g.x * 1.3) * 1.5 + n * 4.0);\n"
    "  } else if (sc == 5) {     // rocky\n"
    "    c = mix(vec3(0.48, 0.42, 0.36), vec3(0.62, 0.55, 0.46), n);\n"
    "    c *= 0.85 + 0.15 * step(0.6, Noise(g * 6.0));\n"
    "  } else if (sc == 6) {     // cave floor\n"
    "    c = mix(vec3(0.22, 0.19, 0.17), vec3(0.34, 0.29, 0.24), n);\n"
    "  } else if (sc == 7) {     // wooden floor\n"
    "    float plank = fract(g.x * 1.6);\n"
    "    c = mix(vec3(0.55, 0.38, 0.24), vec3(0.66, 0.47, 0.30), Noise(vec2(floor(g.x * 1.6), g.y * 3.0)));\n"
    "    c *= 0.9 + 0.1 * smoothstep(0.0, 0.06, plank) * smoothstep(1.0, 0.94, plank);\n"
    "  } else if (sc == 8) {     // seabed\n"
    "    c = mix(vec3(0.55, 0.62, 0.55), vec3(0.70, 0.72, 0.60), n);\n"
    "  } else if (sc == 2 || sc == 3) { // water\n"
    "    float w = sin(g.x * 5.0 + uTime * 1.3 + n * 5.0) * 0.5 + sin(g.y * 7.0 - uTime * 0.9) * 0.5;\n"
    "    c = mix(vec3(0.16, 0.38, 0.62), vec3(0.28, 0.56, 0.80), n) * (0.95 + 0.06 * w);\n"
    "    c = mix(c, uSkyHor, 0.25);\n"
    "  } else {                  // grass with mowing stripes\n"
    "    c = mix(vec3(0.36, 0.62, 0.30), vec3(0.50, 0.76, 0.38), n);\n"
    "    c *= 0.95 + 0.05 * smoothstep(-0.2, 0.2, sin(g.y * 2.2));\n"   // mowing bands across the field
    "    c *= 0.93 + 0.07 * Noise(vec2(p.x * 0.9, p.y * 1.7));\n"
    "    if (sc == 9) c *= 0.85 + 0.15 * Noise(g * 9.0);\n"
    "  }\n"
    "  return c;\n"
    "}\n"
    // Scenery standing on the horizon (towns, hills, dunes, peaks).
    "vec4 Scenery(vec2 p, int sc) {\n"
    "  float H = BD_H;\n"
    "  if (sc == 1) {            // town: two rows of houses\n"
    "    vec4 o = vec4(0.0);\n"
    "    for (int row = 1; row >= 0; row--) {\n"
    "      float scale = row == 1 ? 0.65 : 1.0;\n"
    "      float base = H + float(row) * -3.0;\n"
    "      float x = p.x / scale + float(row) * 37.0;\n"
    "      float cw = 22.0;\n"
    "      float ci = floor(x / cw); float h1 = Hash(vec2(ci, float(row)));\n"
    "      float lx = x - ci * cw;\n"
    "      float bw = 14.0 + h1 * 6.0, x0 = (cw - bw) * 0.5;\n"
    "      float hh = (10.0 + h1 * 12.0) * scale;\n"
    "      float py = base - p.y;\n"
    "      if (lx < x0 || lx > x0 + bw) continue;\n"
    "      float u = (lx - x0) / bw;\n"
    "      float roof = hh + (0.5 - abs(u - 0.5)) * 8.0 * scale;\n"
    "      if (py < 0.0 || py > roof) continue;\n"
    "      vec3 wall = mix(vec3(0.85, 0.78, 0.62), vec3(0.75, 0.55, 0.45), Hash(vec2(ci, 9.0 + float(row))));\n"
    "      vec3 roofc = mix(vec3(0.70, 0.30, 0.25), vec3(0.30, 0.40, 0.70), step(0.5, Hash(vec2(ci, 4.0))));\n"
    "      vec3 col = py > hh ? roofc : wall;\n"
    // windows
    "      if (py < hh - 2.0 * scale && py > 2.0 * scale) {\n"
    "        vec2 wcell = floor(vec2((lx - x0) / (4.0 * scale), py / (5.0 * scale)));\n"
    "        vec2 wf = fract(vec2((lx - x0) / (4.0 * scale), py / (5.0 * scale)));\n"
    "        if (wf.x > 0.3 && wf.x < 0.8 && wf.y > 0.3 && wf.y < 0.8 && (lx - x0) > 2.0 && (lx - x0) < bw - 2.0) {\n"
    "          float lit = step(0.45, Hash(wcell + ci * 13.0 + float(row) * 5.0));\n"
    "          vec3 day = mix(uSkyHor, vec3(0.3, 0.4, 0.5), 0.5);\n"
    "          vec3 night = vec3(1.0, 0.78, 0.42) * (0.9 + 0.1 * sin(uTime * 2.0 + ci));\n"
    "          col = mix(day, mix(col * 0.3, night * 1.4, lit), uNightB);\n"
    "        }\n"
    "      }\n"
    "      col *= mix(1.0, 0.35, uNightB);\n"
    "      if (row == 1) col = mix(col, uSkyHor, 0.35);\n"
    "      o = vec4(col, 1.0);\n"
    "    }\n"
    // lamp posts with glow at night
    "    float lpx = mod(p.x + 10.0, 48.0) - 24.0;\n"
    "    if (abs(lpx) < 0.7 && p.y > H - 14.0 && p.y < H) o = vec4(vec3(0.15), 1.0);\n"
    "    float lg = exp(-dot(vec2(lpx, p.y - (H - 15.0)), vec2(lpx, p.y - (H - 15.0))) / 10.0);\n"
    "    if (lg > 0.02) o = vec4(mix(o.a > 0.0 ? o.rgb : Sky(p), vec3(1.0, 0.85, 0.5) * 1.5, lg * uNightB), max(o.a, lg * uNightB));\n"
    "    return o;\n"
    "  }\n"
    "  if (sc == 0 || sc == 9 || sc == 3) {  // routes: far hills and a tree line\n"
    "    float far = H - 9.0 - 10.0 * Fbm(vec2(p.x * 0.015, 1.0));\n"
    "    float trees = H - 3.0 - 7.0 * (0.6 * Noise(vec2(p.x * 0.12, 2.0)) + 0.4 * abs(sin(p.x * 0.35)));\n"
    "    if (p.y > trees) {\n"
    "      vec3 c = mix(vec3(0.16, 0.36, 0.20), vec3(0.24, 0.48, 0.26), Noise(p * 0.4));\n"
    "      return vec4(c * mix(1.0, 0.3, uNightB), 1.0);\n"
    "    }\n"
    "    if (p.y > far) return vec4(mix(mix(vec3(0.35, 0.55, 0.45), uSkyHor, 0.45) * mix(1.0, 0.35, uNightB), uSkyHor, 0.2), 1.0);\n"
    "    return vec4(0.0);\n"
    "  }\n"
    "  if (sc == 4) {            // dunes\n"
    "    float d1 = H - 6.0 - 9.0 * (0.5 + 0.5 * sin(p.x * 0.03 + 1.0)) * Fbm(vec2(p.x * 0.01, 3.0));\n"
    "    if (p.y > d1) return vec4(mix(vec3(0.90, 0.75, 0.52), uSkyHor, 0.3) * mix(1.0, 0.35, uNightB), 1.0);\n"
    "    return vec4(0.0);\n"
    "  }\n"
    "  if (sc == 5) {            // mountain peaks with snow\n"
    "    float r = Fbm(vec2(p.x * 0.012, 5.0));\n"
    "    r = r * 0.75 + 0.25 * (1.0 - abs(Noise(vec2(p.x * 0.05, 8.0)) * 2.0 - 1.0)) * r;\n"
    "    float pk = H - 2.0 - 40.0 * smoothstep(0.25, 0.8, r);\n"
    "    if (p.y > pk) {\n"
    "      vec3 c = mix(vec3(0.45, 0.45, 0.55), uSkyHor, 0.35);\n"
    "      float snowline = H - 26.0 + Noise(vec2(p.x * 0.2, 3.0)) * 4.0;\n"
    "      if (p.y < snowline) c = mix(vec3(0.95, 0.97, 1.0), uSkyHor, 0.15);\n"
    "      c *= 0.9 + 0.15 * Noise(vec2(p.x * 0.3, p.y * 0.1));\n"
    "      return vec4(c * mix(1.0, 0.35, uNightB), 1.0);\n"
    "    }\n"
    "    return vec4(0.0);\n"
    "  }\n"
    "  return vec4(0.0);\n"
    "}\n"
    "vec3 Backdrop(vec2 p, int sc) {\n"
    "  vec3 c;\n"
    "  float H = BD_H;\n"
    "  if (sc == 6) {            // cave: rock walls, stalactites, glowing crystals\n"
    "    if (p.y < H + 4.0) {\n"
    "      float n = Fbm(p * vec2(0.05, 0.08));\n"
    "      c = mix(vec3(0.12, 0.10, 0.10), vec3(0.26, 0.22, 0.20), n);\n"
    "      float stal = 6.0 + 14.0 * pow(Noise(vec2(p.x * 0.2, 1.0)), 3.0);\n"
    "      if (p.y < stal) c *= 0.55;\n"
    "      vec2 cc = floor(p / vec2(18.0, 10.0));\n"
    "      vec2 cp = (cc + 0.5) * vec2(18.0, 10.0) + (vec2(Hash(cc), Hash(cc + 2.0)) - 0.5) * 8.0;\n"
    "      if (Hash(cc + 5.0) > 0.7) c += vec3(0.3, 0.8, 1.0) * exp(-distance(p, cp) * 0.6) * (0.7 + 0.3 * sin(uTime * 1.5 + Hash(cc) * 9.0));\n"
    "      return c;\n"
    "    }\n"
    "    c = GroundCol(p, sc);\n"
    "  } else if (sc == 7) {     // indoors: papered wall with windows onto the sky, wood floor\n"
    "    if (p.y < H + 2.0) {\n"
    "      c = mix(vec3(0.86, 0.80, 0.68), vec3(0.80, 0.72, 0.60), step(0.5, fract(p.x / 6.0)));\n"
    "      if (p.y > H - 8.0) c = vec3(0.55, 0.40, 0.28);          // wainscot\n"
    "      vec2 wl = vec2(mod(p.x + 20.0, 70.0) - 35.0, p.y - 18.0);\n"
    "      if (abs(wl.x) < 12.0 && abs(wl.y) < 10.0) {\n"
    "        c = abs(wl.x) > 11.0 || abs(wl.y) > 9.0 || abs(wl.x) < 0.6 ? vec3(0.45, 0.33, 0.24) : Sky(vec2(p.x, wl.y * 2.0 + 20.0));\n"
    "      }\n"
    "      vec2 lmp = vec2(mod(p.x - 15.0, 70.0) - 35.0, p.y - 6.0);\n"
    "      c += vec3(1.0, 0.85, 0.6) * exp(-dot(lmp, lmp) / 60.0) * 0.5;\n"
    "      return c * mix(1.0, 0.85, uNightB);\n"
    "    }\n"
    "    c = GroundCol(p, sc);\n"
    "  } else if (sc == 8) {     // underwater: depth gradient, light rays, bubbles\n"
    "    if (p.y < H + 6.0) {\n"
    "      c = mix(vec3(0.05, 0.20, 0.40), vec3(0.15, 0.45, 0.65), p.y / (H + 6.0));\n"
    "      float ray = smoothstep(0.6, 0.9, Noise(vec2(p.x * 0.05 + p.y * 0.02 + uTime * 0.05, 1.0)));\n"
    "      c += vec3(0.4, 0.7, 0.8) * ray * 0.25;\n"
    "      return c;\n"
    "    }\n"
    "    c = GroundCol(p, sc);\n"
    "  } else {\n"
    "    if (p.y < H) {\n"
    "      c = Sky(p);\n"
    "      vec4 s = Scenery(p, sc);\n"
    "      c = mix(c, s.rgb, s.a);\n"
    "      if (sc == 2) c = mix(c, uSkyHor, 0.0);\n"
    "      return c;\n"
    "    }\n"
    "    vec4 s = Scenery(p, sc);\n"
    "    if (s.a > 0.0 && sc == 1) return mix(GroundCol(p, sc), s.rgb, s.a);\n"
    "    c = GroundCol(p, sc);\n"
    "    if (sc == 2) {          // sun / moon glitter path on the sea\n"
    "      float gx = abs(p.x - uSunPos.x) / (2.0 + (p.y - H) * 0.6);\n"
    "      float gl = step(0.7, Noise(vec2(p.x * 0.6, p.y * 1.5 + uTime * 2.0))) * (1.0 - smoothstep(0.0, 1.0, gx));\n"
    "      c += (uSunPos.z > 0.5 ? vec3(1.0, 0.85, 0.6) : vec3(0.8, 0.85, 1.0) * uNightB) * gl * 0.6;\n"
    "    }\n"
    "  }\n"
    // haze toward the horizon, then the light of the hour
    "  float haze = exp(-max(p.y - H, 0.0) * 0.07);\n"
    "  c = mix(c, uSkyHor, haze * (sc == 6 || sc == 7 || sc == 8 ? 0.0 : 0.35));\n"
    "  c *= sc == 6 ? vec3(1.0) : mix(uBLight, vec3(1.0), 0.0);\n"
    // platforms: the battle spots, with a rim and soft contact shading
    "  vec4 E[2]; E[0] = vec4(175.5, 62.0, 64.0, 12.5); E[1] = vec4(62.0, 113.0, 64.0, 13.5);\n"
    "  for (int k = 0; k < 2; k++) {\n"
    "    float e = Ell(p, E[k]);\n"
    "    float sh = 1.0 - smoothstep(0.95, 1.25, Ell(p - vec2(0.0, 2.5), E[k]));\n"
    "    c *= 1.0 - sh * 0.18;\n"
    "    if (e < 1.0) {\n"
    "      vec3 top;\n"
    "      if (sc == 2 || sc == 3) top = mix(c, vec3(0.75, 0.9, 1.0), 0.35 * (0.6 + 0.4 * sin(e * 18.0 - uTime * 2.5)));\n"
    "      else if (sc == 4) top = vec3(0.93, 0.82, 0.60);\n"
    "      else if (sc == 5 || sc == 6) top = vec3(0.55, 0.50, 0.44) * (sc == 6 ? 0.6 : 1.0);\n"
    "      else if (sc == 7) top = vec3(0.70, 0.30, 0.28);               // rug\n"
    "      else if (sc == 8) top = vec3(0.70, 0.72, 0.62);\n"
    "      else top = vec3(0.55, 0.80, 0.40);\n"
    "      float n = Fbm((p - E[k].xy) * 0.15);\n"
    "      top *= 0.92 + 0.12 * n;\n"
    "      top *= 1.0 + 0.10 * (1.0 - e) - 0.10 * smoothstep(0.75, 1.0, e);   // domed light, darker rim\n"
    "      top *= sc == 6 || sc == 7 ? vec3(1.0) : uBLight;\n"
    "      c = mix(c, top, 1.0 - smoothstep(0.92, 1.0, e));\n"
    "      c *= 1.0 - 0.25 * smoothstep(0.86, 0.98, e) * (1.0 - smoothstep(0.98, 1.02, e));  // rim line\n"
    "    }\n"
    "  }\n"
    "  return c;\n"
    "}\n"
    "bool Glass(vec2 g) {\n"   // a window pane: pale blue pixel in a wall
    "  ivec2 c = ivec2(floor(CellPos(g)));\n"
    "  if ((Cell(c) & 1) == 0) return false;\n"
    "  for (int k = 1; k < 16; k++) {\n"   // back wall: nothing but wall above it, up to the top of the room
    "    ivec2 u = c - ivec2(0, k);\n"
    "    if (u.y < 0) break;\n"
    "    if ((Cell(u) & 1) == 0) return false;\n"
    "  }\n"
    "  vec3 k = TexS(uFlat, vec2((g.x + uMargin) / uDim.x, g.y / uDim.y)).rgb;\n"
    "  return k.b > 0.6 && k.b - k.r > 0.18 && k.g > 0.5;\n"
    "}\n"
    "float WaterArt(vec2 q) {\n"   // how much this pixel of the art is open water (blue)
    "  if (gZoomField) return 0.0;\n"
    "  vec3 k = TexS(uFlat, q).rgb;\n"
    "  return smoothstep(0.13, 0.22, k.b - max(k.r, k.g * 0.9)) * smoothstep(0.25, 0.4, k.b);\n"   // strongly blue only: lavender walls and grey stone are not water
    "}\n"
    "float Caustic(vec2 p, float t) {\n"   // sunlight focused by the waves onto the seabed: a bright moving net
    "  vec2 i = p; float c = 1.0;\n"
    "  for (int n = 0; n < 4; n++) {\n"
    "    float tt = t * (1.0 - 3.5 / float(n + 1));\n"
    "    i = p + vec2(cos(tt - i.x) + sin(tt + i.y), sin(tt - i.y) + cos(tt + i.x));\n"
    "    c += 1.0 / length(vec2(p.x / (sin(i.x + tt) / 0.005), p.y / (cos(i.y + tt) / 0.005)));\n"
    "  }\n"
    "  c = 1.17 - pow(c / 4.0, 1.4);\n"
    "  return clamp(pow(abs(c), 8.0), 0.0, 1.0);\n"
    "}\n"
    "void GrassColors(ivec2 cell, out vec3 dark, out vec3 light) {\n"   // darkest and lightest colours of a grass cell's art
    "  vec2 o = uGridPos.xy + vec2(cell) * 16.0;\n"
    "  dark = vec3(1.0); light = vec3(0.0); float dl = 9.0, ll = -1.0;\n"
    "  for (int i = 0; i < 4; i++) for (int j = 0; j < 4; j++) {\n"
    "    vec2 q = o + vec2(float(i), float(j)) * 4.0 + 2.0;\n"
    "    vec2 qq = vec2((q.x + uMargin) / uDim.x, q.y / uDim.y);\n"   // map layers only, never sprites
    "    vec4 l3 = TexS(uLayer[3], qq), l2 = TexS(uLayer[2], qq), l1 = TexS(uLayer[1], qq);\n"
    "    vec3 c = l3.rgb; c = c * (1.0 - l2.a) + l2.rgb; c = c * (1.0 - l1.a) + l1.rgb;\n"
    "    float l = dot(c, vec3(0.3, 0.59, 0.11));\n"
    "    if (c.g >= c.r * 0.9 || c.g >= c.b) { if (l < dl) { dl = l; dark = c; } if (l > ll) { ll = l; light = c; } }\n"
    "  }\n"
    "  if (ll < 0.0) { dark = vec3(0.12, 0.38, 0.2); light = vec3(0.45, 0.78, 0.42); }\n"
    "  dark = mix(dark, light, 0.35); light = mix(light, vec3(1.0), 0.08);\n"
    "}\n"
    "void GrassPal(ivec2 c, out vec3 dark, out vec3 light) {\n"
    "  vec3 d, l; float n = 0.0; dark = vec3(0.0); light = vec3(0.0);\n"
    "  for (int i = -1; i <= 1; i++) for (int j = -1; j <= 1; j++) {\n"
    "    ivec2 q = c + ivec2(i, j);\n"
    "    if ((Cell(q) & 4) == 0) continue;\n"
    "    GrassColors(q, d, l); dark += d; light += l; n += 1.0;\n"
    "  }\n"
    "  if (n > 0.0) { dark /= n; light /= n; } else GrassColors(c, dark, light);\n"
    "}\n"
    "float MenuBgAt(ivec2 n) {\n"   // native pixel n is the menu's background pattern
    "  n = clamp(n, ivec2(0), ivec2(uDim) - 1);\n"
    "  if (float(n.x) < uContent.x || float(n.x) >= uContent.y) return 1.0;\n"   // outside the original screen: open background
    "  vec3 k = texture(uFlat, (vec2(n) + 0.5) / uDim * vec2(1.0, 1.0)).rgb;\n"
    "  vec3 seg = uMenuBg2 - uMenuBg1;\n"
    "  float tt = clamp(dot(k - uMenuBg1, seg) / max(dot(seg, seg), 1e-5), 0.0, 1.0);\n"
    "  return distance(k, uMenuBg1 + seg * tt) < 0.06 ? 1.0 : 0.0;\n"
    "}\n"
    "float MenuMask(vec2 p) {\n"   // smooth (bilinear) background mask at native position p
    "  vec2 q = p - 0.5; ivec2 i = ivec2(floor(q)); vec2 f = smoothstep(0.0, 1.0, fract(q));\n"
    "  return mix(mix(MenuBgAt(i), MenuBgAt(i + ivec2(1, 0)), f.x), mix(MenuBgAt(i + ivec2(0, 1)), MenuBgAt(i + ivec2(1, 1)), f.x), f.y);\n"
    "}\n"
    "bool Green(vec4 c) { vec3 k = c.rgb / max(c.a, 1e-4); return c.a > 0.5 && k.g > k.r * 1.05 && k.g > k.b * 1.1; }\n"
    "vec3 C555(uint c) { return vec3(float(c & 31u), float((c >> 5) & 31u), float((c >> 10) & 31u)) / 31.0; }\n"
    "vec3 PalC(uint i) { return C555(texelFetch(uPal, ivec2(int(i), 0), 0).r); }\n"
    // Hand-made replacement tile, with the GBA's palette fade re-applied.
    "vec4 Pack(usampler2D tr, vec4 base, ivec2 np, vec2 sub) {\n"
    "  uvec4 t = texelFetch(tr, np, 0);\n"
    "  if (t.r == 0u) return base;\n"
    "  if ((t.r & 0x8000u) != 0u) {\n"   // high-resolution text
    "    uint slot = t.r & 1023u;\n"
    "    int cell = int(16.0 * uGlyphScale);\n"
    "    vec2 local = (vec2(float(t.g & 15u), float((t.g >> 4) & 15u)) + sub) * uGlyphScale;\n"
    "    ivec2 org = ivec2(int(slot % 16u), int(slot / 16u)) * cell;\n"
    "    vec2 cov = texelFetch(uGlyphs, org + clamp(ivec2(floor(local)), ivec2(0), ivec2(cell - 1)), 0).rg;\n"
    "    uint bank = (t.b >> 12) & 15u, bgi = (t.b >> 8) & 15u;\n"
    "    vec4 col = bgi == 0u ? vec4(0.0) : vec4(PalC(bank * 16u + bgi), 1.0);\n"
    "    col = mix(col, vec4(PalC(bank * 16u + ((t.b >> 4) & 15u)), 1.0), cov.g);\n"
    "    col = mix(col, vec4(PalC(bank * 16u + (t.b & 15u)), 1.0), cov.r);\n"
    "    return vec4(col.rgb * col.a, col.a);\n"
    "  }\n"
    "  uint slot = t.r - 1u;\n"
    "  int tile = int(8.0 * uPackScale + 0.5);\n"
    "  float fx = (t.g & 64u) != 0u ? 1.0 - sub.x : sub.x;\n"
    "  float fy = (t.g & 128u) != 0u ? 1.0 - sub.y : sub.y;\n"
    "  vec2 local = (vec2(float(t.g & 7u), float((t.g >> 3) & 7u)) + vec2(fx, fy)) * uPackScale;\n"
    "  ivec2 origin = ivec2(int(slot % uint(uPerRow)), int(slot / uint(uPerRow))) * tile;\n"
    "  vec4 h = texelFetch(uAtlas, origin + clamp(ivec2(floor(local)), ivec2(0), ivec2(tile - 1)), 0);\n"
    "  vec3 U = C555(t.b), F = C555(t.a), c = h.rgb;\n"
    "  vec3 dn = c * F / max(U, vec3(1.0 / 62.0));\n"
    "  vec3 up = c + (1.0 - c) * (F - U) / max(1.0 - U, vec3(1.0 / 62.0));\n"
    "  c = clamp(mix(up, dn, vec3(lessThanEqual(F, U))), 0.0, 1.0);\n"
    "  return vec4(c * h.a, h.a);\n"
    "}\n"
    "vec3 blend(vec3 a, vec3 b, float ea, float eb) { return min(a * ea + b * eb, vec3(1.0)); }\n"
    "void main() {\n"
    "  ivec2 np = ivec2(min(floor(vUv * uDim), uDim - 1.0));\n"
    "  np.y = 159 - np.y;\n"
    "  if (uMenu == 0 && (float(np.x) < uContent.x || float(np.x) >= uContent.y)) { oColor = vec4(0.0, 0.0, 0.0, 1.0); return; }\n"
    "  vec2 uv = vec2(vUv.x, 1.0 - vUv.y);\n"
    "  gUpSize = vec2(textureSize(uLayer[0], 0));\n"
    "  gUpFw = fwidth(uv * gUpSize);\n"
    "  vec2 uvc = uv; ivec2 npc = np; bool camOn = false;\n"
    "  if (uBattle != 0 && float(np.y) < uBoxTop) {\n"
    "    camOn = true;\n"
    "    uvc = uCam.xy + (uv - uCam.xy) / uCam.z + uShake / uDim;\n"
    "    if (uMoveFx > 0.0) {\n"
    "      vec2 gq = uvc * uDim;\n"
    "      if (uMoveType == 10) uvc.x += sin(gq.y * 0.9 + uTime * 9.0) * 0.35 * uMoveFx / uDim.x;\n"
    "      if (uMoveType == 14) uvc += vec2(sin(gq.y * 0.25 + uTime * 5.0), cos(gq.x * 0.2 + uTime * 4.0)) * 0.6 * uMoveFx / uDim;\n"
    "    }\n"
    "    npc = clamp(ivec2(floor(uvc * uDim)), ivec2(0), ivec2(uDim) - 1);\n"
    "  } else if (uTilt > 0.0 && uFieldFx != 0) {\n"
    // HD-2D: the ground plane recedes toward the top of the screen. Rows near
    // the top hold more of the map (foreshortened), rows near the bottom are
    // closer (magnified); the message box and UI (BG0) stay flat.
    "    camOn = true;\n"
    "    float k = uTilt, y = uv.y;\n"
    "    float sy = y * (1.0 + k) / (1.0 + k * y);\n"
    "    float sx = 1.0 / (1.0 + k * y);\n"
    "    uvc = vec2(0.5 + (uv.x - 0.5) * sx, sy);\n"
    "    npc = clamp(ivec2(floor(uvc * uDim)), ivec2(0), ivec2(uDim) - 1);\n"
    "  }\n"
    "  if (uCineZoom.z > 1.001 && uFieldFx != 0 && uBattle == 0) {\n"   // cinematic push-in (text boxes stay put)
    "    camOn = true;\n"
    "    uvc = uCineZoom.xy + (uvc - uCineZoom.xy) / uCineZoom.z;\n"
    "    npc = clamp(ivec2(floor(uvc * uDim)), ivec2(0), ivec2(uDim) - 1);\n"
    "  }\n"
    "  if (uFieldFx != 0 && uLife.z > 0.0 && np.y > 0) {\n"   // heat rising off the ground
    "    vec2 gq = uv * uDim;\n"
    "    uvc.x += sin(gq.y * 0.55 + uTime * 5.5 + sin(gq.x * 0.08 + uTime) * 2.0) * 0.32 / uDim.x;\n"
    "    uvc.y += sin(gq.x * 0.31 + uTime * 4.0) * 0.18 / uDim.y;\n"
    "  }\n"
    "  uvec4 L0 = texelFetch(uLine, ivec2(0, np.y), 0);\n"
    "  uvec4 L1 = texelFetch(uLine, ivec2(1, np.y), 0);\n"
    "  uvec4 L2 = texelFetch(uLine, ivec2(2, np.y), 0);\n"
    "  uvec4 L3 = texelFetch(uLine, ivec2(3, np.y), 0);\n"
    "  if ((L1.b & 1u) != 0u) { oColor = vec4(1.0); return; }\n"
    "  uvec4 M = texelFetch(uMeta, np, 0);\n"
    "  uint en = L1.r, prios = L1.g, mask = M.r;\n"
    "  uint objPrio = M.g & 3u; bool semi = (M.g & 4u) != 0u;\n"
    "  uint bld = L2.r | (L2.g << 8);\n"
    "  float eva = float(L2.b) / 16.0, evb = float(L2.a) / 16.0, evy = float(L3.r) / 16.0;\n"
    "  uint effect = L3.g;\n"
    "  vec4 lay[5];\n"
    "  lay[0] = TexS(uLayer[0], uv); lay[1] = TexS(uLayer[1], uvc);\n"
    "  lay[2] = TexS(uLayer[2], uvc); lay[3] = TexS(uLayer[3], uvc);\n"
    "  lay[4] = TexS(uLayer[4], uv);\n"
    "  if (camOn) {\n"
    "    uvec4 Mc = texelFetch(uMeta, npc, 0);\n"
    "    vec2 gs = uv * uDim - vec2(uMargin, 0.0), gc = uvc * uDim - vec2(uMargin, 0.0);\n"
    "    bool hbS = M.a == 2u && ((gs.y >= 70.0 && gs.y < 114.0 && gs.x >= 118.0) || (gs.y < 46.0 && gs.x < 120.0));\n"
    "    bool hbC = Mc.a == 2u && ((gc.y >= 70.0 && gc.y < 114.0 && gc.x >= 118.0) || (gc.y < 46.0 && gc.x < 120.0));\n"
    "    if (!hbS) {\n"
    "      lay[4] = hbC ? vec4(0.0) : TexS(uLayer[4], uvc);\n"
    "      if (uTilt > 0.0 && uBattle == 0) {\n"   // depth of field: the far distance goes soft
    "        float rr = uTilt * 4.0 * smoothstep(0.38, 0.0, uv.y);\n"
    "        if (rr > 0.05) {\n"
    "          vec2 o1 = vec2(rr, 0.0) / uDim, o2 = vec2(0.0, rr) / uDim;\n"
    "          lay[1] = (lay[1] * 2.0 + TexS(uLayer[1], uvc + o1) + TexS(uLayer[1], uvc - o1) + TexS(uLayer[1], uvc + o2) + TexS(uLayer[1], uvc - o2)) / 6.0;\n"
    "          lay[2] = (lay[2] * 2.0 + TexS(uLayer[2], uvc + o1) + TexS(uLayer[2], uvc - o1) + TexS(uLayer[2], uvc + o2) + TexS(uLayer[2], uvc - o2)) / 6.0;\n"
    "          lay[3] = (lay[3] * 2.0 + TexS(uLayer[3], uvc + o1) + TexS(uLayer[3], uvc - o1) + TexS(uLayer[3], uvc + o2) + TexS(uLayer[3], uvc - o2)) / 6.0;\n"
    "          lay[4] = (lay[4] * 2.0 + TexS(uLayer[4], uvc + o1) + TexS(uLayer[4], uvc - o1) + TexS(uLayer[4], uvc + o2) + TexS(uLayer[4], uvc - o2)) / 6.0;\n"
    "        }\n"
    "      }\n"
    "      M = uvec4(M.r, Mc.g, M.b, hbC ? 0u : Mc.a);\n"
    "      objPrio = M.g & 3u; semi = (M.g & 4u) != 0u;\n"
    "    }\n"
    "  }\n"
    "  gZoomField = camOn && uBattle == 0;\n"
    "  vec2 uvScreen = uv;\n"
    "  if (camOn) uv = uvc;\n"   // every scene effect below works in the camera's view
    "  vec2 gp = vec2(vUv.x * uDim.x - uMargin, (1.0 - vUv.y) * uDim.y);\n"
    "  if (camOn) gp = uvc * uDim - vec2(uMargin, 0.0);\n"
    "  vec2 wp = gp - uGridPos.xy + uGridPos.zw * 16.0;\n"   // world position (map pixels)
    "  int here = uFieldFx != 0 ? Cell(ivec2(floor(CellPos(gp)))) : 0;\n"
    // Wind: grass and tree leaves sway, anchored at the top and bottom of each tile.
    "  if (uFieldFx != 0 && uMapType != 4 && uMapType != 8 && (here & 1) != 0 && (here & 4) == 0) {\n"
    "    float fy = fract(CellPos(gp).y);\n"
    "    float gust = 0.6 + 0.4 * sin(uTime * 0.37 + wp.x * 0.004);\n"
    "    float amp = ((here & 4) != 0 ? 0.55 : 0.3) * gust * sin(3.14159 * fy);\n"
    "    vec2 o = vec2(sin(uTime * 2.1 + wp.x * 0.045 + wp.y * 0.11) * amp / uDim.x, 0.0);\n"
    "    vec4 s2;\n"
    "    if (Green(lay[1])) { s2 = TexS(uLayer[1], uv + o); if (Green(s2)) lay[1] = s2; }\n"
    "    if (Green(lay[2])) { s2 = TexS(uLayer[2], uv + o); if (Green(s2)) lay[2] = s2; }\n"
    "    if (Green(lay[3])) { s2 = TexS(uLayer[3], uv + o); if (Green(s2)) lay[3] = s2; }\n"
    "  }\n"
    "  if (uBattle != 0) {\n"   // Pokémon breathe: a gentle squash and stretch about their feet
    "    int mk = MonAt(gp);\n"
    "    if (mk >= 0) {\n"
    "      vec2 f = uMonFeet[mk].xy;\n"
    "      float a = 0.016 * sin(uTime * 2.3 + float(mk) * 1.9);\n"
    "      vec2 q = vec2(f.x + (gp.x - f.x) / (1.0 - a * 0.5), f.y + (gp.y - f.y) / (1.0 + a));\n"
    "      lay[4] = TexS(uLayer[4], vec2((q.x + uMargin) / uDim.x, q.y / uDim.y));\n"
    "    }\n"
    "  }\n"
    "  if (uHasPack != 0) {\n"
    "    vec2 sub = vec2(fract(vUv.x * uDim.x), 1.0 - fract(vUv.y * uDim.y));\n"
    "    lay[0] = Pack(uTref[0], lay[0], np, sub); lay[1] = Pack(uTref[1], lay[1], np, sub);\n"
    "    lay[2] = Pack(uTref[2], lay[2], np, sub); lay[3] = Pack(uTref[3], lay[3], np, sub);\n"
    "    lay[4] = Pack(uTref[4], lay[4], np, sub);\n"
    "  }\n"
    // Order visible layers front to back (OBJ before BGs of equal priority).
    "  int order[6]; int n = 0;\n"
    "  for (uint p = 0u; p < 4u; p++) {\n"
    "    if ((en & 16u) != 0u && (mask & 16u) != 0u && objPrio == p) order[n++] = 4;\n"
    "    for (int bg = 0; bg < 4; bg++) {\n"
    "      if ((en & (1u << uint(bg))) != 0u && (mask & (1u << uint(bg))) != 0u && ((prios >> uint(bg * 2)) & 3u) == p) order[n++] = bg;\n"
    "    }\n"
    "  }\n"
    "  vec3 bd = vec3(L0.rgb) / 255.0;\n"
    // Top and second layers: the first two that are mostly opaque here.
    "  int top = 5, bot = 5, ti = n, bi = n;\n"
    "  for (int k = 0; k < n; k++) {\n"
    "    if (lay[order[k]].a >= 0.5) { if (top == 5) { top = order[k]; ti = k; } else { bot = order[k]; bi = k; break; } }\n"
    "  }\n"
    // Colour of everything below the top layer (painter's algorithm, back to front).
    "  vec3 under = bd;\n"
    "  for (int k = n - 1; k > ti; k--) { vec4 c = lay[order[k]]; under = under * (1.0 - c.a) + c.rgb; }\n"
    // A smoothed edge inside a pixel that was solid in the original would
    // reveal what the GBA keeps hidden underneath; use the upscaled original
    // frame there instead.
    "  if (top != 5 && top != 0 && ((M.b >> uint(top)) & 1u) != 0u && lay[top].a < 0.999 && !(camOn && uBattle == 0))\n"
    "    under = TexS(uFlat, uvc).rgb;\n"
    "  vec3 botCol = bot == 5 ? bd : lay[bot].rgb / max(lay[bot].a, 1e-4);\n"
    "  vec3 res = under;\n"
    "  if (top != 5) {\n"
    "    vec4 t = lay[top];\n"
    "    vec3 tc = t.rgb / max(t.a, 1e-4);\n"
    "    vec3 c = tc;\n"
    "    bool fx = (mask & 32u) != 0u;\n"
    "    bool t1 = ((bld >> uint(top)) & 1u) != 0u;\n"
    "    bool b2 = ((bld >> uint(8 + bot)) & 1u) != 0u;\n"
    "    if (fx) {\n"
    "      if (top == 4 && semi && b2) c = blend(tc, botCol, eva, evb);\n"
    "      else if (t1) {\n"
    "        if (effect == 1u && b2) c = blend(tc, botCol, eva, evb);\n"
    "        else if (effect == 2u) c = tc + (1.0 - tc) * evy;\n"
    "        else if (effect == 3u) c = tc - tc * evy;\n"
    "      }\n"
    "    }\n"
    "    res = mix(under, c, clamp(t.a, 0.0, 1.0));\n"
    "  } else {\n"
    "    bool fx = (mask & 32u) != 0u;\n"
    "    if (fx && ((bld >> 5u) & 1u) != 0u) {\n"
    "      if (effect == 2u) res = res + (1.0 - res) * evy;\n"
    "      else if (effect == 3u) res = res - res * evy;\n"
    "    }\n"
    "  }\n"
    // Thin, mostly transparent fringes of map/sprite layers in front of the
    // top layer: added before lighting so they are lit like what they edge.
    "  for (int k = ti - 1; k >= 0; k--) if (order[k] != 0) { vec4 c = lay[order[k]]; res = res * (1.0 - c.a) + c.rgb; }\n"
    // ---- Remade water: replaces the blue water pixels of the art (so the
    // drawn shores, rocks and piers keep their exact shapes) with live
    // waves, sky reflection, sun glints, shallow-to-deep colour and foam ----
    "  float wm = 0.0;\n"
    "  if (uFieldFx != 0 && top >= 1 && top <= 3) {\n"
    "    ivec2 c0 = ivec2(floor(CellPos(gp)));\n"
    "    wm = WaterArt(uv);\n"
    // water art counts on and beside water tiles, and broad blue diagonally beside them
    // (water drawn under boats and piers), so the remake doesn't stop at a tile edge
    "    bool nearWater = false;\n"
    "    if (wm > 0.0) {\n"
    "      if (((here | Cell(c0 + ivec2(1, 0)) | Cell(c0 - ivec2(1, 0)) | Cell(c0 + ivec2(0, 1)) | Cell(c0 - ivec2(0, 1))) & 2) != 0) nearWater = true;\n"
    "      else {\n"   // beside water: only broad blue (open water drawn under boats/piers), not glass or trim
    "        float big = min(min(WaterArt(uv + vec2(6.0, 0.0) / uDim), WaterArt(uv - vec2(6.0, 0.0) / uDim)), min(WaterArt(uv + vec2(0.0, 6.0) / uDim), WaterArt(uv - vec2(0.0, 6.0) / uDim)));\n"
    "        if (big > 0.5) for (int j = -1; j <= 1 && !nearWater; j++) for (int i = -1; i <= 1; i++) if ((Cell(c0 + ivec2(i, j)) & 2) != 0) { nearWater = true; break; }\n"
    "      }\n"
    "    }\n"
    "    if (!nearWater) wm = 0.0;\n"
    "    if (nearWater) {\n"
    "      if (wm > 0.0) {\n"
    "        float shore = 0.0;\n"   // how close the nearest non-water art is (0 open water .. 1 at the shore)
    "        for (int k = 0; k < 8; k++) {\n"
    "          float a = float(k) * 0.785;\n"
    "          vec2 o = vec2(cos(a), sin(a));\n"
    "          shore += (1.0 - WaterArt(uv + o * 3.0 / uDim)) * 0.6 + (1.0 - WaterArt(uv + o * 7.0 / uDim)) * 0.4;\n"
    "        }\n"
    "        shore = clamp(shore / 8.0 * 1.6, 0.0, 1.0);\n"
    "        vec3 art = TexS(uFlat, uv).rgb;\n"
    // waves: a few travelling wave trains -> surface slope
    "        vec2 q = wp;\n"
    "        vec2 sl = vec2(0.0);\n"
    "        sl += vec2(0.8, 0.6) * cos(dot(q, vec2(0.8, 0.6)) * 0.35 - uTime * 1.6) * 0.5;\n"
    "        sl += vec2(-0.5, 0.85) * cos(dot(q, vec2(-0.5, 0.85)) * 0.55 - uTime * 2.1) * 0.3;\n"
    "        sl += vec2(0.2, -1.0) * cos(dot(q, vec2(0.2, -1.0)) * 0.9 - uTime * 2.7 + Noise(q * 0.05) * 3.0) * 0.18;\n"
    "        sl += (vec2(Noise(q * 0.18 + uTime * 0.4), Noise(q * 0.18 - uTime * 0.35 + 9.0)) - 0.5) * 0.2;\n"
    // wake: rings spreading from where the player swam, so surfing leaves a V behind
    "        float crest = 0.0;\n"
    "        for (int k = 0; k < 12; k++) {\n"
    "          float age = uTime - uWake[k].z;\n"
    "          if (uWake[k].z < 0.0 || age < 0.0 || age > 3.0) continue;\n"
    "          vec2 dv = q - uWake[k].xy; float d = length(dv);\n"
    "          float x = d - 4.0 - age * 16.0;\n"
    "          float ring = exp(-x * x / 18.0) * exp(-age * 1.3);\n"
    "          sl += dv / max(d, 1.0) * sin(x * 0.8) * ring * 1.4;\n"
    "          crest += ring * smoothstep(0.0, 1.5, -x + 1.5) * (1.0 - age / 3.0);\n"
    "        }\n"
    "        if (uWake[0].z >= 0.0 && uTime - uWake[0].z < 0.2) {\n"   // bobbing in place: small rings at the player
    "          float d = length(q - uWake[0].xy), x = mod(d - uTime * 10.0, 14.0) - 7.0;\n"
    "          sl += sin(x * 0.9) * exp(-d / 14.0) * 0.4 * vec2(1.0);\n"
    "        }\n"
    "        vec3 deep = vec3(0.10, 0.30, 0.55), shallow = vec3(0.25, 0.62, 0.72);\n"
    "        vec3 base = mix(deep, shallow, shore * 0.85);\n"
    "        base = mix(base, art, 0.25);\n"   // keep a little of each area's own water colour
    // shallows: the seabed shows through, bent by the waves, with sunlight caustics on it
    "        float clear = smoothstep(0.2, 0.85, shore) * (uMapType == 4 ? 0.0 : 1.0);\n"
    "        if (clear > 0.0) {\n"
    "          vec2 bp = q + sl * 3.0;\n"
    "          float cs = Caustic(bp * 0.09, uTime * 0.55) * 0.7 + Caustic(bp * 0.15 + 3.0, uTime * 0.8) * 0.3;\n"
    "          vec3 bed = vec3(0.80, 0.74, 0.55) * (0.82 + 0.18 * Noise(bp * 0.12));\n"
    "          bed *= 0.7 + cs * 1.1 * max(uSun.w, 0.1) * (1.0 - 0.7 * uLiveWx.x);\n"
    "          base = mix(base, mix(bed, shallow, 0.35), clear * 0.6);\n"
    "        }\n"
    "        float facing = clamp(0.5 + dot(sl, vec2(-0.5, -0.7)) * 0.6, 0.0, 1.0);\n"
    "        vec3 skyc = mix(vec3(0.62, 0.80, 1.0), vec3(1.0, 0.75, 0.5), clamp((uTint.r - uTint.b) * 3.0, 0.0, 1.0));\n"
    // clouds drifting overhead, seen in the surface (more on a cloudy day)
    "        vec2 cp = q * 0.012 + sl * 0.06 + vec2(uTime * 0.012, uTime * 0.005);\n"
    "        float cl = smoothstep(0.45, 0.8, Noise(cp) * 0.65 + Noise(cp * 2.3 + 5.0) * 0.35);\n"
    "        skyc = mix(skyc, vec3(1.0, 0.99, 0.97) * (0.6 + 0.4 * max(uSun.w, 0.2)), cl * (0.55 + 0.35 * uLiveWx.x));\n"
    "        vec3 wc = mix(base * (0.85 + 0.3 * facing), skyc, 0.18 + 0.22 * facing * facing);\n"
    "        float spec = pow(clamp(dot(normalize(vec3(sl * 1.2, 1.0)), normalize(vec3(-0.35, -0.55, 0.75))), 0.0, 1.0), 240.0);\n"
    "        wc += vec3(1.0, 0.97, 0.9) * spec * 0.6 * max(uSun.w, 0.15);\n"
    "        float foamBand = smoothstep(0.55, 0.95, shore) * (0.55 + 0.45 * sin(uTime * 1.5 - shore * 9.0 + Noise(q * 0.2) * 4.0));\n"
    "        float foam = foamBand * smoothstep(0.35, 0.65, Noise(q * 0.45 + vec2(uTime * 0.3, 0.0)));\n"
    "        foam += clamp(crest, 0.0, 1.0) * (0.35 + 0.35 * Noise(q * 0.12 + uTime * 0.4));\n"   // soft: no small noise cells, which read as blocks at 1440p
    "        wc = mix(wc, vec3(0.93, 0.97, 1.0), clamp(foam, 0.0, 1.0) * 0.85);\n"
    "        res = mix(res, wc, wm);\n"
    "      }\n"
    "    }\n"
    "  }\n"
    // ---- Remade tall grass: tufts of tapered blades drawn over the cell
    // (and over the legs of anyone standing in it), coloured from the area's
    // own grass art, swaying with the wind ----
    "  float gm = (uFieldFx != 0 && (here & 4) != 0) ? 1.0 : 0.0;\n"   // original tall grass art, untouched by relief
    "  if (false) {\n"   // redrawn grass: dropped
    "    ivec2 c0 = ivec2(floor(CellPos(gp)));\n"
    "    bool anyGrass = ((Cell(c0) | Cell(c0 + ivec2(0, 1))) & 4) != 0;\n"
    "    if (anyGrass) {\n"
    "      bool mapPx = top <= 3 || ((Cell(c0) & 4) != 0 && Green(lay[4]) && fract(CellPos(gp).y) >= 0.5);\n"   // map art, or the game's own grass-over sprite
    "      vec3 dark, light;\n"
    "      dark = uGrassDark; light = uGrassLight;\n"
    "      if ((Cell(c0) & 4) != 0 && mapPx) { res = mix(dark, light, 0.8) * (0.95 + 0.05 * Noise(wp * 0.4)); gm = 1.0; }\n"
    "      vec2 T = vec2(8.0, 8.0);\n"
    "      vec2 bc = floor(wp / T);\n"
    "      float wind = sin(uTime * 1.7 + wp.x * 0.03) * 0.6 + sin(uTime * 3.1 + wp.y * 0.05) * 0.25;\n"
    "      for (int dy = 0; dy <= 2; dy++) {\n"   // tufts whose base is at or below this pixel, far to near
    "        for (int dx = -2; dx <= 2; dx++) {\n"
    "          vec2 t = bc + vec2(float(dx), float(dy));\n"
    "          float h0 = Hash(t * 1.7 + 3.0);\n"
    "          if (h0 < 0.18) continue;\n"   // a few gaps, like separate tufts
    "          vec2 base = (t + vec2(0.5 + (h0 - 0.5) * 0.6 + mod(t.y, 2.0) * 0.5, 1.0 - Hash(t + 9.0) * 0.35)) * T;\n"
    "          ivec2 bcell = ivec2(floor((base - vec2(0.0, 0.5) - uGridPos.zw * 16.0) / 16.0));\n"
    "          if ((Cell(bcell) & 4) == 0) continue;\n"
    "          vec3 dk = dark, lt = light;\n"
    "          for (int b = 0; b < 5; b++) {\n"
    "            float hb = Hash(t * 3.1 + float(b) * 1.3);\n"
    "            float bx = (float(b) - 2.0) * 1.5 + (hb - 0.5);\n"
    "            float h = 4.5 + hb * 2.5 - abs(float(b) - 2.0) * 0.9;\n"
    "            vec2 a = base + vec2(bx, 0.0);\n"
    "            vec2 tip = a + vec2(bx * 0.55 + wind * (1.0 + hb), -h);\n"
    "            vec2 pa = wp - a, ba = tip - a;\n"
    "            float k = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);\n"
    "            float w = mix(1.25, 0.15, k);\n"
    "            float d = length(pa - ba * k);\n"
    "            float edge = 1.0 - smoothstep(w - 0.35, w + 0.35, d);\n"
    "            float rim = 1.0 - smoothstep(w + 0.1, w + 0.75, d);\n"
    "            if (rim <= 0.0) continue;\n"
    "            vec3 bcol = mix(dk, lt, k * 0.9 + 0.1 * hb);\n"
    "            res = mix(res, dk * 0.55, rim * 0.6);\n"   // dark outline, like the game's art style
    "            res = mix(res, bcol, edge);\n"
    "            gm = max(gm, rim);\n"
    "          }\n"
    "        }\n"
    "      }\n"
    "    }\n"
    "  }\n"
    // ---- Seasons (a new one each day) ----
    "  if (uFieldFx != 0 && top >= 1 && top <= 3 && (uMapType >= 1 && uMapType <= 3 || uMapType == 6) && wm < 0.5) {\n"
    "    vec3 k = res;\n"
    "    float l = dot(k, vec3(0.299, 0.587, 0.114));\n"
    "    bool leafy = k.g > k.r * 1.05 && k.g > k.b * 1.05;\n"
    "    ivec2 cc = ivec2(floor(CellPos(gp)));\n"
    "    float sat = k.g - max(k.r, k.b);\n"
    "    bool tree = leafy && sat / max(k.g, 0.05) > 0.28 && (here & 4) == 0;\n"   // strongly coloured foliage, never the pale ground
    "    bool ground = (Cell(cc) & 1) == 0;\n"
    "    float th = Noise(wp * 0.025 + 3.0);\n"   // smooth variation across the map (no tile seams)
    "    if (uSeason == 0) {\n"   // spring: fresh greens, some trees in blossom
    "      if (leafy) res = mix(k, k * vec3(0.95, 1.08, 0.92) + 0.03, 0.8);\n"
    "      if (tree) res = mix(res, vec3(1.0, 0.72, 0.84) * (0.55 + 0.6 * l), smoothstep(0.3, 0.6, l) * 0.85 * smoothstep(0.55, 0.7, th));\n"
    "    } else if (uSeason == 1) {\n"   // summer: deep saturated greens, warm light
    "      if (leafy) res = mix(vec3(l), k, 1.15) * vec3(1.0, 1.02, 0.95);\n"
    "      res *= vec3(1.04, 1.01, 0.96);\n"
    "    } else if (uSeason == 2) {\n"   // autumn: trees turn orange, red and gold; leaves on the paths
    "      if (leafy) {\n"
    "        vec3 pal = mix(mix(vec3(0.92, 0.3, 0.14), vec3(1.0, 0.55, 0.16), smoothstep(0.25, 0.5, th)), vec3(1.0, 0.78, 0.25), smoothstep(0.55, 0.8, th));\n"
    "        if (!tree) pal = vec3(0.85, 0.75, 0.35);\n"   // grass goes golden
    "        res = mix(k, pal * (l / dot(pal, vec3(0.299, 0.587, 0.114))) * 0.95, tree ? 0.85 : 0.35);\n"
    "      }\n"
    "      if (!tree && top >= 1 && top <= 3) {\n"   // fallen leaves: thick drifts, heaviest under trees
    "        float pile = smoothstep(0.35, 0.65, Noise(wp * 0.05 + 11.0)) * 0.7 + Solid(gp + vec2(0.0, -6.0)) * 0.6;\n"
    "        for (int L = 0; L < 2; L++) {\n"
    "          float cs = L == 0 ? 3.5 : 2.5;\n"
    "          vec2 base = floor(wp / cs + float(L) * 0.5);\n"
    "          for (int i = -1; i <= 1; i++) for (int j = -1; j <= 1; j++) {\n"   // neighbours too, so leaves are never cut off
    "            vec2 lc = base + vec2(float(i), float(j)); float lh = Hash(lc + 13.0 + float(L) * 7.0);\n"
    "            if (lh > 0.15 + 0.75 * clamp(pile, 0.0, 1.0)) continue;\n"
    "            vec2 lp = (lc - float(L) * 0.5 + 0.5 + 0.35 * (vec2(Hash(lc), Hash(lc + 2.0)) - 0.5)) * cs;\n"
    "            int lcell = Cell(ivec2(floor((lp - uGridPos.zw * 16.0) / 16.0)));\n"
    "            if ((lcell & 7) != 0) continue;\n"   // only on open ground (decided per leaf, so edges are ragged)
    "            float an = lh * 40.0; vec2 d = mat2(cos(an), -sin(an), sin(an), cos(an)) * (wp - lp);\n"
    "            float leaf = 1.0 - smoothstep(0.7, 1.15, length(d / vec2(1.6, 0.95)));\n"
    "            if (leaf <= 0.0) continue;\n"
    "            vec3 lcol = mix(mix(vec3(0.85, 0.28, 0.12), vec3(0.95, 0.55, 0.15), Hash(lc + 5.0)), vec3(0.98, 0.78, 0.25), step(0.75, Hash(lc + 9.0)));\n"
    "            res = mix(res, lcol * (0.8 + 0.25 * Hash(lc + 3.0)), leaf);\n"
    "          }\n"
    "        }\n"
    "      }\n"
    "    } else {\n"   // winter: snow on the ground, trees and roofs; icy water edges
    "      vec3 snow = vec3(0.93, 0.96, 1.0);\n"
    "      float n = Noise(wp * 0.12) * 0.6 + Noise(wp * 0.4) * 0.4;\n"
    "      if (ground && (here & 4) == 0 && !tree) res = mix(k, snow * (0.9 + 0.1 * n), smoothstep(0.12, 0.3, n) * 0.92);\n"
    "      else if (leafy) res = mix(k * vec3(0.8, 0.9, 0.95), snow, smoothstep(0.35, 0.65, l) * 0.8);\n"
    "      else res = mix(k, snow, smoothstep(0.45, 0.8, l) * 0.6);\n"   // roofs and walls: snow on the lit tops
    "      res *= vec3(0.96, 0.99, 1.04);\n"
    "    }\n"
    "  }\n"
    // Per-pixel surface lighting: a normal for every pixel from the art's
    // shading (fine relief), sprite outlines (rounded characters) and depth
    // inside solid scenery (domed trees, roofs, cliffs); lit by the key light.
    "  vec3 N = vec3(0.0, 0.0, 1.0);\n"
    "  if (uFieldFx != 0 && top >= 1 && top <= 4 && uKey.w > 0.0 && wm < 0.5 && gm < 0.5) {\n"
    "    float st = top == 4 ? 2.5 : 1.0;\n"
    "    vec2 du = vec2(st / uDim.x, 0.0), dv = vec2(0.0, st / uDim.y);\n"
    "    float hc = top == 4 ? 1.0 : dot(lay[top].rgb / max(lay[top].a, 1e-4), vec3(0.3, 0.59, 0.11));\n"
    "    float hx = LumL(top, uv + du, hc) - LumL(top, uv - du, hc);\n"
    "    float hy = LumL(top, uv + dv, hc) - LumL(top, uv - dv, hc);\n"
    "    float dx = 0.0, dy = 0.0;\n"
    "    if (top != 4) {\n"   // only shapes the scenery itself, never the open ground beside it
    "      float w = smoothstep(0.5, 1.0, Solid(gp));\n"
    "      dx = (Depth(gp + vec2(9.0, 3.0)) + Depth(gp + vec2(9.0, -3.0)) - Depth(gp - vec2(9.0, 3.0)) - Depth(gp - vec2(9.0, -3.0))) * 0.28 * w;\n"
    "      dy = (Depth(gp + vec2(3.0, 9.0)) + Depth(gp + vec2(-3.0, 9.0)) - Depth(gp - vec2(3.0, 9.0)) - Depth(gp - vec2(-3.0, 9.0))) * 0.07 * w;\n"   // fronts face the viewer and stay lit
    "    }\n"
    "    float detail = top == 4 ? 0.8 : 0.55;\n"
    "    N = normalize(vec3(-(hx * detail + dx * 2.4), -(hy * detail + dy * 2.4), 1.0));\n"
    "    float d = dot(N.xy, normalize(uKey.xy + 1e-5)) * 1.6;\n"   // facing the light brightens, facing away darkens; 0 on average
    "    res *= 1.0 + clamp(d, -0.45, 0.45) * uKey.w;\n"
    "  }\n"
    // Light bounce: open ground next to coloured scenery picks up a little
    // of its colour (a red roof warms the path beside it).
    "  if (uFieldFx != 0 && top >= 1 && top <= 3 && uKey.w > 0.0) {\n"
    "    vec2 gr = vec2(Solid(gp + vec2(6.0, 0.0)) - Solid(gp - vec2(6.0, 0.0)), Solid(gp + vec2(0.0, 6.0)) - Solid(gp - vec2(0.0, 6.0)));\n"
    "    float gl = length(gr);\n"
    "    if (gl > 0.02 && Solid(gp) < 0.5 && wm < 0.01 && !gZoomField) {\n"
    "      vec2 sp = gp + gr / gl * 9.0;\n"
    "      vec3 bc = TexS(uFlat, vec2((sp.x + uMargin) / uDim.x, sp.y / uDim.y)).rgb;\n"
    "      vec3 tintc = bc / max(dot(bc, vec3(0.333)), 0.08);\n"
    "      res *= mix(vec3(1.0), clamp(tintc, 0.6, 1.6), min(gl, 1.0) * 0.14 * uKey.w / 0.6);\n"
    "    }\n"
    "  }\n"
    // ---- Menu screens: the background pattern is replaced by a soft,
    // slowly moving gradient with drifting light; panels cast shadows. ----
    "  if (uMenu != 0) {\n"
    "    vec2 mp = vec2(vUv.x * uDim.x, (1.0 - vUv.y) * uDim.y);\n"
    "    bool side = float(np.x) < uContent.x || float(np.x) >= uContent.y;\n"
    "    float bm = side ? 1.0 : MenuMask(mp);\n"
    "    if (uCards > 0 && !side) {\n"   // party: the whole BG1 pattern goes, except the message box and buttons (bottom strip)
    "      vec2 g = mp - vec2(uContent.x, 0.0);\n"
    "      bool keep = (g.y >= 129.0 && g.x < 186.0) || (g.y >= 131.0 && g.x >= 184.0);\n"
    "      vec3 fk = TexS(uFlat, uv).rgb;\n"
    "      float yel = smoothstep(0.82, 0.7, fk.b / max(min(fk.r, fk.g), 0.05)) * step(0.25, fk.g);\n"   // the stripes are yellow-olive; box frames and buttons are not
    "      bm = (lay[0].a < 0.5 && lay[2].a < 0.5 && lay[4].a < 0.5) ? (keep ? yel : 1.0) : 0.0;\n"
    "    }\n"
    "    if (uMenu == 5 && !side) bm = (lay[0].a < 0.5 && lay[1].a < 0.5 && lay[2].a < 0.5 && lay[4].a < 0.5) ? 1.0 : 0.0;\n"   // PC boxes: the scrolling pattern is the bottom layer
    "    vec3 mbg = vec3(0.0);\n"
    "    if (bm > 0.0 || uCards > 0) {\n"
    "      vec3 a = mix(uMenuBg1, uMenuBg2, 0.5);\n"
    "      a = vec3(0.16, 0.22, 0.34);\n"   // every menu screen: one calm deep blue, so they read as one game
    "      vec3 c1 = a * 0.55 + vec3(0.05, 0.06, 0.12), c2 = a * 0.9 + vec3(0.08);\n"
    "      float g = mp.y / uDim.y + 0.15 * sin(mp.x * 0.02 + uTime * 0.3);\n"
    "      vec3 b = mix(c2, c1, clamp(g, 0.0, 1.0));\n"
    "      for (int k = 0; k < 6; k++) {\n"   // soft drifting light orbs
    "        float h = float(k) * 1.7;\n"
    "        vec2 o = vec2(fract(0.13 * h + uTime * 0.012 * (1.0 + 0.3 * float(k))) * uDim.x, uDim.y * (0.2 + 0.6 * fract(h * 0.37)) + 10.0 * sin(uTime * 0.3 + h));\n"
    "        b += vec3(1.0) * 0.07 * exp(-dot(mp - o, mp - o) / (300.0 + 200.0 * fract(h)));\n"
    "      }\n"
    "      float sh = 0.0;\n"   // shadow cast by panels above and to the left
    "      for (int k = 1; k <= 3; k++) sh = max(sh, (1.0 - MenuMask(mp - vec2(float(k) * 1.3))) * (1.0 - float(k) / 4.0));\n"
    "      if (!side && uCards == 0 && uMenu != 5) b *= 1.0 - sh * 0.4;\n"
    "      mbg = b;\n"
    "      if (side) { oColor = vec4(b, 1.0); return; }\n"
    "      res = mix(res, b, bm);\n"
    "    }\n"
    // ---- Party screen: glass cards with rounded corners, a glowing cursor,
    // smooth HP bars. The game's text (BG0) and icons (OBJ) go on top. ----
    "    for (int k = 0; k < 6; k++) {\n"
    "      if (k >= uCards) break;\n"
    "      vec4 r = uCard[k]; float st = uCardState[k];\n"
    "      vec2 hs = r.zw * 0.5 - 1.0, ce = r.xy + r.zw * 0.5;\n"
    "      float rad = r.w > 30.0 ? 6.0 : 5.0;\n"
    "      vec2 dq = abs(mp - ce) - (hs - rad);\n"
    "      float sd = length(max(dq, 0.0)) + min(max(dq.x, dq.y), 0.0) - rad;\n"
    "      vec2 dqs = abs(mp - vec2(1.2, 1.8) - ce) - (hs - rad);\n"
    "      float sds = length(max(dqs, 0.0)) + min(max(dqs.x, dqs.y), 0.0) - rad;\n"
    "      bool cur = mod(st, 4.0) >= 2.0, faint = mod(st, 8.0) >= 4.0, pick = st >= 8.0, here = mod(st, 2.0) >= 1.0;\n"
    "      float glowR = cur || pick ? 5.0 : 0.0;\n"
    "      if (sd > 4.0 + glowR && sds > 4.0) continue;\n"
    "      float aa = max(fwidth(sd), 0.02);\n"
    "      float inside = 1.0 - smoothstep(-aa, aa, sd);\n"
    "      vec3 top = vec3(0.21, 0.31, 0.48), bot = vec3(0.11, 0.17, 0.31);\n"
    "      if (cur) { top = vec3(0.40, 0.52, 0.74); bot = vec3(0.22, 0.32, 0.52); }\n"
    "      if (faint) { top = mix(top, vec3(0.50, 0.20, 0.24), 0.75); bot = mix(bot, vec3(0.27, 0.09, 0.12), 0.75); }\n"
    "      float fy = clamp((mp.y - r.y) / r.w, 0.0, 1.0);\n"
    "      vec3 cc = mix(top, bot, fy);\n"
    "      cc += 0.08 * (1.0 - smoothstep(0.0, 0.45, fy));\n"   // glass highlight along the top
    "      if (cur) {\n"   // light sweeping across the selected card
    "        float sx = mp.x - r.x - fract(uTime * 0.3) * (r.z + 80.0) + 40.0 + (mp.y - r.y) * 0.6;\n"
    "        cc += vec3(0.14) * exp(-sx * sx / 60.0);\n"
    "      }\n"
    "      float ca = here ? 0.94 : 0.35;\n"
    "      vec3 bc = vec3(0.60, 0.75, 1.0); float ba = 0.45;\n"
    "      if (cur) { bc = vec3(1.0, 0.78, 0.32); ba = 1.0; }\n"
    "      if (pick) { bc = vec3(0.45, 0.95, 1.0); ba = 1.0; }\n"
    "      float ring = 1.0 - smoothstep(0.0, aa * 1.5 + (cur || pick ? 0.7 : 0.3), abs(sd + 0.6));\n"
    "      vec3 col = mix(mbg, mix(mbg, cc, ca), inside);\n"
    "      col *= 1.0 - (1.0 - inside) * (1.0 - smoothstep(-1.0, 3.5, sds)) * 0.45;\n"   // soft drop shadow
    "      if (glowR > 0.0 && sd > 0.0) col += bc * exp(-sd / 2.6) * (0.7 + 0.25 * sin(uTime * 4.0));\n"
    "      col = mix(col, bc, ring * ba);\n"
    "      vec4 hb = uCardBar[k];\n"
    "      if (hb.z > 0.0 && here) {\n"   // HP bar: dark pill track, coloured fill with a bright edge
    "        vec2 bce = vec2(hb.x + hb.z * 0.5, hb.y + 1.5), bhs = vec2(hb.z * 0.5, 2.2);\n"
    "        vec2 bq = abs(mp - bce) - (bhs - 2.0);\n"
    "        float bsd = length(max(bq, 0.0)) + min(max(bq.x, bq.y), 0.0) - 2.0;\n"
    "        float bin = 1.0 - smoothstep(-aa, aa, bsd);\n"
    "        float f = hb.w;\n"
    "        vec3 hc = f > 0.5 ? vec3(0.32, 0.90, 0.55) : f > 0.2 ? vec3(1.0, 0.80, 0.25) : vec3(1.0, 0.33, 0.33);\n"
    "        float filled = 1.0 - smoothstep(-aa, aa, mp.x - (hb.x + hb.z * f));\n"
    "        float by = (mp.y - (bce.y - bhs.y)) / (bhs.y * 2.0);\n"
    "        vec3 fillc = hc * (1.15 - 0.35 * by) + 0.25 * (1.0 - smoothstep(0.0, 0.35, by));\n"
    "        col = mix(col, mix(vec3(0.04, 0.06, 0.10), fillc, filled * (1.0 - smoothstep(-aa, aa, bsd + 0.6))), bin);\n"
    "      }\n"
    "      col = col * (1.0 - lay[0].a) + lay[0].rgb;\n"   // the game's text on top
    "      col = col * (1.0 - lay[4].a) + lay[4].rgb;\n"   // then icons and badges
    "      res = col;\n"
    "    }\n"
    "  }\n"
    // Following Pokémon: drawn behind roofs and tree tops, and in front of or
    // behind the player by whose feet are lower.
    "  if (uFollowOn.x > 0.5 && uFieldFx != 0 && top != 0) {\n"
    "    vec2 lp = gp - uFollowPos.xy;\n"
    "    if (lp.x >= 0.0 && lp.y >= 0.0 && lp.x < 32.0 && lp.y < 32.0) {\n"
    "      if (uFollowPos.z > 0.5) lp.x = 31.999 - lp.x;\n"
    "      vec4 fc = texture(uFollow, vec2(lp.x / 32.0, (lp.y + uFollowPos.w * 32.0) / 64.0));\n"
    "      bool behindSprite = top == 4 && uFollowOn.y <= uPlayer.y;\n"
    "      if (fc.a > 0.5 && top != 1 && !behindSprite) {\n"
    "        vec3 k = fc.rgb;\n"
    "        if (uTint.a > 0.5) { float lk = dot(k, vec3(0.2126, 0.7152, 0.0722)); k = mix(k, vec3(lk), clamp((uTint.b - uTint.r) * 2.0, 0.0, 1.0) * 0.35) * uTint.rgb; }\n"
    "        res = k;\n"
    "      }\n"
    "    }\n"
    "  }\n"
    // Scenery lighting on the ground: ambient occlusion around solid
    // scenery, sun shadows that follow the time of day, drifting cloud shadows.
    "  float recv = (uFieldFx != 0 && top >= 1 && top <= 3 && uMapType != 8 && uMapType != 9) ? (1.0 - Solid(gp)) * (1.0 - wm) : 0.0;\n"   // how much this is open ground
    "  if (recv > 0.0) {\n"
    "    float ao = Solid(gp + vec2(0.0, -5.0)) * 0.55 + Solid(gp + vec2(-5.0, 0.0)) * 0.22\n"
    "             + Solid(gp + vec2(5.0, 0.0)) * 0.22 + Solid(gp + vec2(0.0, 5.0)) * 0.12;\n"
    "    res *= 1.0 - clamp(ao, 0.0, 1.0) * 0.17 * recv;\n"
    "    if (uSun.z > 0.0) {\n"
    "      float occ = 0.0;\n"
    "      vec2 side = normalize(vec2(-uSun.y, uSun.x)) * 2.5;\n"
    "      for (int k = 1; k <= 7; k++) {\n"
    "        vec2 q = gp - uSun.xy * (float(k) / 7.0);\n"
    "        occ = max(occ, (Solid(q) * 2.0 + Solid(q + side) + Solid(q - side)) * 0.25);\n"
    "      }\n"
    "      vec2 cu = vec2(uSun.x / uDim.x, uSun.y / uDim.y);\n"   // canopies/roofs: exact outline
    "      occ = max(occ, texture(uLayer[1], uv - cu).a * 0.9);\n"
    "      res *= vec3(1.0) - occ * uSun.z * recv * vec3(1.0, 0.93, 0.78);\n"
    "    }\n"
    "  }\n"
    "  if (uFieldFx != 0 && top != 0 && uSun.w > 0.0 && uMapType != 4 && uMapType != 8 && uMapType != 9) {\n"
    "    vec2 q = wp * 0.0055 + uTime * vec2(0.018, 0.007);\n"
    "    float cl = Noise(q) * 0.62 + Noise(q * 2.2 + 3.1) * 0.38;\n"
    "    res *= 1.0 - smoothstep(0.56, 0.74, cl) * 0.15 * uSun.w;\n"
    "  }\n"
    // Lightning: a blue-white flash with hard shadows straight down.
    "  if (uFieldFx != 0 && uFlash > 0.0 && top != 0) {\n"
    "    float occ = 0.0;\n"
    "    if (recv > 0.0) for (int k = 1; k <= 6; k++) occ = max(occ, Solid(gp - vec2(1.5, 9.0) * (float(k) / 6.0)));\n"
    "    res *= mix(vec3(1.0), vec3(1.12, 1.14, 1.2), uFlash * (1.0 - occ * recv)) * (1.0 - occ * recv * uFlash * 0.45);\n"
    "  }\n"
    // Soft shadows under characters, cast on the ground (not on sprites or UI).
    "  if (uFieldFx != 0 && top != 4 && top != 0) {\n"
    "    float sh = 0.0;\n"
    "    for (int k = 0; k < uNumShadows; k++) {\n"
    "      vec3 s = uShadows[k];\n"
    "      vec2 e = (gp - s.xy) / vec2(s.z * 0.5, s.z * 0.2);\n"
    "      float blob = (1.0 - smoothstep(0.45, 1.0, length(e)));\n"
    "      sh = max(sh, blob * (uSun.z > 0.0 ? 0.20 : 0.28));\n"     // contact shadow
    "      if (uSun.z > 0.0) sh = max(sh, Sil(gp, s, uSun.xy / 14.0) * uSun.z * 1.5);\n"   // sun
    "      vec3 L = uShadowLight[k];\n"
    "      if (L.z > 0.0) sh = max(sh, Sil(gp, s, L.xy) * L.z);\n"   // lamps and lit doorways
    "      if (sh > 0.55) break;\n"
    "    }\n"
    "    res *= 1.0 - sh;\n"
    "  }\n"
    // Time-of-day lighting on the overworld, not on text boxes/menus (BG0).
    "  if (uTint.a > 0.5 && top != 0) {\n"
    "    float l = dot(res, vec3(0.2126, 0.7152, 0.0722));\n"
    "    float night = clamp((1.0 - uTint.b) * 0.0 + (uTint.b > uTint.r ? (uTint.b - uTint.r) * 2.0 : 0.0), 0.0, 1.0);\n"
    "    res = mix(res, vec3(l), night * 0.35) * uTint.rgb;\n"
    "  }\n"
    // Water: moving sparkle and a gentle shimmer on water metatiles.
    // Reflections: scenery standing on the shore mirrored in the water.
    "  if (uFieldFx != 0 && top >= 1 && top <= 3 && (here & 2) != 0) {\n"
    "    ivec2 c0 = ivec2(floor(CellPos(gp)));\n"
    "    int up = 0;\n"
    "    for (int i = 1; i <= 4; i++) { if ((Cell(c0 - ivec2(0, i)) & 2) == 0) break; up = i; }\n"
    "    float shore = uGridPos.y + float(c0.y - up) * 16.0;\n"
    "    if (wm > 0.5 && (Cell(c0 - ivec2(0, up + 1)) & 1) != 0) {\n"   // something solid on the shore
    "      float dy = gp.y - shore;\n"
    "      vec2 m = vec2(gp.x + sin(wp.y * 0.5 + uTime * 2.0) * 0.6, shore - dy);\n"
    "      vec2 muv = vec2((m.x + uMargin) / uDim.x, m.y / uDim.y);\n"
    "      vec4 a = TexS(uLayer[1], muv), b = TexS(uLayer[2], muv);\n"
    "      vec3 refl = a.rgb + b.rgb * (1.0 - a.a);\n"
    "      float ra = clamp(a.a + b.a * (1.0 - a.a), 0.0, 1.0) * (1.0 - smoothstep(0.0, 40.0, dy));\n"
    "      ra *= Solid(m);\n"   // only objects (trees, rocks, buildings), not ground
    "      ivec2 mnp = clamp(ivec2(floor(vec2(m.x + uMargin, m.y))), ivec2(0), ivec2(uDim) - 1);\n"
    "      uint mm = texelFetch(uMeta, mnp, 0).r;\n"
    "      if ((mm & 6u) != 6u || TexS(uLayer[0], muv).a > 0.0) ra = 0.0;\n"   // hidden by a window or under a text box
    "      res = mix(res, refl / max(ra, 1e-3) * vec3(0.7, 0.8, 0.9), ra * 0.4);\n"
    "    }\n"
    "    vec4 ch = MirrorChars(gp) * wm;\n"   // reflections only on the water itself, never on scenery standing in water tiles
    "    res = mix(res, ch.rgb / max(ch.a, 1e-3) * vec3(0.75, 0.85, 0.95), ch.a * 0.45);\n"

    "  }\n"
    // Rain: wet ground darkens and puddles reflect buildings, trees,
    // characters and lights (streaks below lamps and doorways).
    "  if (uFieldFx != 0 && uWet > 0.01 && top >= 1 && top <= 4 && (here & 2) == 0) {\n"
    "    res *= 1.0 - 0.12 * uWet;\n"   // everything outdoors is wet: no edge between ground and scenery
    "  }\n"
    "  if (uFieldFx != 0 && uWet > 0.01 && recv > 0.0 && (here & 2) == 0 && top >= 1 && top <= 3) {\n"
    "    float pud = Puddles(wp) * uWet * smoothstep(0.2, 0.9, recv);\n"
    "    res *= 1.0 - 0.08 * pud;\n"
    "    if (pud > 0.01) {\n"
    "      ivec2 c0 = ivec2(floor(CellPos(gp)));\n"
    "      int up = -1;\n"
    "      for (int i = 1; i <= 3; i++) { if ((Cell(c0 - ivec2(0, i)) & 1) != 0) { up = i; break; } }\n"
    "      vec2 rip = vec2(sin(wp.y * 0.8 + uTime * 5.0) * 0.4, 0.0);\n"
    "      if (up > 0) {\n"
    "        float base = uGridPos.y + float(c0.y - up + 1) * 16.0;\n"
    "        vec4 m = MirrorScene(vec2(gp.x, base - (gp.y - base)) + rip, false);\n"
    "        m *= 1.0 - smoothstep(0.0, 36.0, gp.y - base);\n"
    "        res = mix(res, m.rgb / max(m.a, 1e-3) * 0.8, m.a * pud * 0.45);\n"
    "      }\n"
    "      vec4 ch = MirrorChars(gp + rip);\n"
    "      res = mix(res, ch.rgb / max(ch.a, 1e-3) * 0.8, ch.a * pud * 0.4);\n"
    "      if (uNight > 0.0) {\n"
    "        for (int k = 0; k < uNumLights; k++) {\n"
    "          vec2 q = gp - uLights[k].xy;\n"
    "          if (q.y < 4.0 || q.y > 60.0) continue;\n"
    "          float wdt = 2.5 + q.y * 0.06;\n"
    "          float st = (1.0 - smoothstep(0.0, wdt, abs(q.x + sin(q.y * 0.5 + uTime * 4.0)))) * (1.0 - q.y / 60.0);\n"
    "          res += vec3(1.0, 0.8, 0.5) * st * pud * uNight * 0.55;\n"
    "        }\n"
    "      }\n"
    "    }\n"
    "  }\n"
    // Windows light up at night: pale glass on building fronts (solid tiles
    // just above open ground) glows warm.
    "  if (uFieldFx != 0 && uNight > 0.15 && top >= 1 && top <= 3 && (here & 1) != 0 && uMapType != 4) {\n"
    "    ivec2 c0 = ivec2(floor(CellPos(gp)));\n"
    "    bool facade = (Cell(c0 + ivec2(0, 1)) & 1) == 0 || (Cell(c0 + ivec2(0, 2)) & 1) == 0;\n"
    "    vec3 k = lay[top].rgb / max(lay[top].a, 1e-4);\n"
    "    float glass = smoothstep(0.72, 0.88, k.b) * smoothstep(0.2, 0.32, k.b - k.r) * step(0.55, k.g);\n"
    "    if (facade && glass > 0.0) res = mix(res, vec3(1.0, 0.82, 0.5) * (0.75 + 0.25 * k.b), glass * min(uNight * 1.2, 1.0) * 0.85);\n"
    "  }\n"
    // Warm light around doors at night.
    "  if (uFieldFx != 0 && uNight > 0.0 && top != 0) {\n"
    "    float g = 0.0;\n"
    "    for (int k = 0; k < uNumLights; k++) {\n"
    "      float d = distance(gp, uLights[k].xy) / uLights[k].z;\n"
    "      float f = 1.0 - smoothstep(0.0, 1.0, d);\n"
    "      g += f * f;\n"
    "      vec2 tl = uLights[k].xy - gp; float dl = length(tl);\n"   // surfaces facing the lamp catch its light
    "      float fr = 1.0 - smoothstep(0.0, 1.8, dl / uLights[k].z);\n"
    "      g += max(dot(N.xy, tl / max(dl, 1e-3)), 0.0) * fr * (top == 4 ? 1.6 : 1.0);\n"
    "    }\n"
    "    g = min(g, 1.2) * uNight;\n"
    "    vec3 warm = vec3(1.0, 0.78, 0.48);\n"
    "    vec3 lit = res * (1.0 + warm * g * 0.55) + warm * g * 0.22 * (1.0 - res);\n"
    // Soft shoulder: bright surfaces (white hair, signs) roll off instead of clipping.
    "    res = mix(lit, 0.8 + 0.2 * (1.0 - exp(-(lit - 0.8) / 0.2)), step(0.8, lit));\n"
    "  }\n"
    // Light beams: cones of light spilling from doorways at night.
    "  if (uFieldFx != 0 && uNight > 0.1 && top != 0) {\n"
    "    float b = 0.0;\n"
    "    for (int k = 0; k < uNumLights; k++) {\n"
    "      vec2 q = gp - uLights[k].xy + vec2(0.0, 6.0);\n"
    "      if (q.y < 0.0 || q.y > 46.0) continue;\n"
    "      float wdt = 5.0 + q.y * 0.42;\n"
    "      b += (1.0 - smoothstep(wdt * 0.55, wdt, abs(q.x))) * (1.0 - q.y / 46.0) * (0.75 + 0.25 * Noise(wp * 0.15 + vec2(0.0, uTime * 0.6)));\n"
    "    }\n"
    "    res += vec3(1.0, 0.8, 0.5) * min(b, 1.0) * 0.10 * uNight;\n"
    "  }\n"
    // Golden hour: low sun streams through the air in broad warm rays.
    "  if (uFieldFx != 0 && top != 0 && uSun.z > 0.0 && uMapType != 4 && uMapType != 8) {\n"
    "    float low = smoothstep(9.0, 17.0, length(uSun.xy));\n"
    "    if (low > 0.0) {\n"
    "      vec2 dir = normalize(uSun.xy), perp = vec2(-dir.y, dir.x);\n"
    "      float x = dot(gp, perp) * 0.022;\n"
    "      float ray = smoothstep(0.5, 0.85, Noise(vec2(x + uTime * 0.015, 3.0))) * (0.6 + 0.4 * Noise(vec2(x * 0.4, uTime * 0.05)));\n"
    "      res += vec3(1.0, 0.82, 0.55) * ray * low * 0.10 * (1.0 - 0.5 * res);\n"
    "    }\n"
    "  }\n"
    // Caves: the player carries a lantern; rocks cast shadows away from it.
    "  if (uFieldFx != 0 && uMapType == 4 && top != 0 && uPlayer.x > -900.0) {\n"
    "    vec2 lp = uPlayer - vec2(0.0, 10.0);\n"
    "    vec2 to = lp - gp; float dl = length(to);\n"
    "    float occ = 0.0;\n"
    "    if (recv > 0.0) for (int k = 1; k <= 8; k++) occ = max(occ, Solid(gp + to * (float(k) / 9.0)) * step(8.0, dl * (1.0 - float(k) / 9.0)));\n"
    "    float lamp = (1.0 - smoothstep(10.0, 95.0, dl)) * (1.0 - occ * 0.5);\n"
    "    float flick = 0.95 + 0.05 * sin(uTime * 9.0) * Noise(vec2(uTime * 3.0, 1.0));\n"
    "    res *= 0.72 + vec3(1.0, 0.82, 0.6) * lamp * 0.5 * flick;\n"
    "  }\n"
    // ---- Indoors: sunbeams from windows, glowing screens and lamps,
    // soft furniture shadows, warm lamplight at night ----
    "  if (uFieldFx != 0 && top != 0 && (uMapType == 8 || uMapType == 9)) {\n"
    "    bool floor_ = top >= 1 && top <= 3 && (here & 1) == 0;\n"
    "    if (false) {\n"   // window sunbeams: removed (blocky edges)   // trace back toward the window along the light
    "      float beam = 0.0; vec2 dir = uInSun.xy;\n"
    "      for (int k = 2; k <= 14; k++) {\n"
    "        vec2 q = gp - dir * float(k) * 3.5;\n"
    "        if (Glass(q)) { beam = 1.0 - float(k) / 15.0; break; }\n"
    "      }\n"
    "      if (beam > 0.0) {\n"
    "        float dust = 0.85 + 0.15 * Noise(wp * 0.25 + vec2(uTime * 0.3, -uTime * 0.5));\n"
    "        vec2 mc = floor(wp / 5.0); float mh = Hash(mc);\n"
    "        vec2 mp = (mc + 0.5) * 5.0 + 1.5 * vec2(sin(uTime * 0.7 + mh * 30.0), cos(uTime * 0.5 + mh * 20.0));\n"
    "        float mote = step(0.85, mh) * exp(-dot(wp - mp, wp - mp) * 3.0);\n"
    "        float edge = smoothstep(0.0, 0.25, beam);\n"
    "        res += vec3(1.0, 0.88, 0.65) * (edge * (0.22 + 0.3 * beam) * dust + mote * 0.6 * beam) * uInSun.z * (0.5 + 0.5 * res);\n"
    "      }\n"
    "    }\n"
    "    if (uInSun.w > 0.0) {\n"   // night: dark windows, warm lamplight in the room
    "      if (top >= 1 && top <= 3 && Glass(gp)) res = mix(res, vec3(0.08, 0.12, 0.28) + res * 0.2, uInSun.w * 0.8);\n"
    "      else res *= mix(vec3(1.0), vec3(1.06, 0.97, 0.86), uInSun.w);\n"
    "    }\n"
    "  }\n"
    // ---- Living world: particles drawn into the scene (not over menus) ----
    "  if (uFieldFx != 0 && top != 0) {\n"
    "    bool outside = uMapType != 4 && uMapType != 8 && uMapType != 9;\n"
    "    float day = uSun.w;\n"
    // Falling leaves in wooded areas, drifting with the wind, with shadows.
    "    if (outside && uSeason == 3 && uWeather == 0) {\n"   // winter: falling snow
    "      for (int L = 0; L < 3; L++) {\n"
    "        float sz = 0.7 + float(L) * 0.45;\n"
    "        vec2 q = gp - vec2(sin(uTime * 0.5 + float(L)) * 6.0, uTime * (9.0 + float(L) * 7.0)) + float(L) * 37.0;\n"
    "        vec2 c = floor(q / 10.0); float h = Hash(c + float(L) * 3.0);\n"
    "        if (h > 0.5) continue;\n"
    "        vec2 ctr = (c + 0.5) * 10.0 + vec2(sin(uTime * 1.5 + h * 30.0) * 2.5, 0.0);\n"
    "        res = mix(res, vec3(1.0), (1.0 - smoothstep(sz * 0.4, sz, length(q - ctr))) * 0.9);\n"
    "      }\n"
    "    }\n"
    "    if (outside && uSeason == 0 && uWeather == 0) {\n"   // spring: drifting blossom petals
    "      vec2 q = gp - vec2(-12.0, 9.0) * uTime;\n"
    "      vec2 c = floor(q / 26.0); float h = Hash(c + 21.0);\n"
    "      if (h < 0.35) {\n"
    "        vec2 ctr = (c + 0.5) * 26.0 + vec2(sin(uTime * 1.3 + h * 20.0) * 5.0, cos(uTime * 0.9 + h * 9.0) * 3.0);\n"
    "        float an = uTime * 2.0 + h * 10.0; vec2 d = mat2(cos(an), -sin(an), sin(an), cos(an)) * (q - ctr);\n"
    "        res = mix(res, vec3(1.0, 0.78, 0.88), 1.0 - smoothstep(0.7, 1.0, length(d / vec2(1.8, 1.1))));\n"
    "      }\n"
    "    }\n"
    "    if ((uMapType == 3 && uForest > 0.32 || uSeason == 2 && outside) && uWeather == 0) {\n"
    "      for (int L = 0; L < 2; L++) {\n"
    "        vec2 vel = vec2(-9.0, 13.0) * (L == 0 ? 1.0 : 0.7);\n"
    "        for (int S = 0; S < 2; S++) {\n"   // S = 0 shadow, 1 leaf
    "          vec2 q = gp - vel * uTime + (S == 0 ? vec2(-4.0, -7.0) : vec2(0.0)) + float(L) * 17.0;\n"
    "          vec2 c = floor(q / 30.0); float h = Hash(c + float(L) * 7.3);\n"
    "          if (h > 0.05 + 0.2 * smoothstep(0.4, 0.7, uForest)) continue;\n"
    "          vec2 ctr = (c + 0.5) * 30.0 + vec2(sin(uTime * 1.7 + h * 30.0) * 6.0, cos(uTime * 1.1 + h * 17.0) * 3.0);\n"
    "          float an = uTime * (1.5 + h * 3.0) + h * 20.0;\n"
    "          vec2 d = mat2(cos(an), -sin(an), sin(an), cos(an)) * (q - ctr);\n"
    "          float flip = 0.35 + 0.65 * abs(sin(uTime * 3.0 + h * 9.0));\n"
    "          float leaf = 1.0 - smoothstep(0.75, 1.0, length(d / vec2(2.8, 1.5 * flip)));\n"
    "          if (leaf <= 0.0) continue;\n"
    "          vec3 lc = mix(vec3(0.45, 0.62, 0.18), vec3(0.85, 0.48, 0.15), Hash(c + 3.1)) * mix(0.35, 1.0, day);\n"
    "          res = S == 0 ? res * (1.0 - leaf * 0.25 * day) : mix(res, lc, leaf);\n"
    "        }\n"
    "      }\n"
    "    }\n"
    // Butterflies fluttering over grass on sunny days.
    "    if (outside && day > 0.5 && uWeather == 0) {\n"
    "      vec2 c = floor(wp / 64.0);\n"
    "      for (int i = -1; i <= 1; i++) for (int j = -1; j <= 1; j++) {\n"
    "        vec2 cc = c + vec2(float(i), float(j)); float h = Hash(cc * 2.3 + 5.0);\n"
    "        if (h > 0.4) continue;\n"
    "        vec2 p = (cc + 0.5) * 64.0 + vec2(sin(uTime * 0.5 + h * 40.0) * 20.0 + sin(uTime * 1.3 + h * 9.0) * 6.0, cos(uTime * 0.4 + h * 23.0) * 14.0);\n"
    "        if ((Cell(ivec2(floor((p - uGridPos.zw * 16.0) / 16.0))) & 1) != 0) continue;\n"
    "        vec2 d = wp - p;\n"
    "        float sh = exp(-dot(d - vec2(-3.0, 7.0), d - vec2(-3.0, 7.0)) / 3.0);\n"
    "        res *= 1.0 - sh * 0.25;\n"
    "        float flap = 0.25 + 0.75 * abs(sin(uTime * 15.0 + h * 50.0));\n"
    "        d /= 1.6;\n"
    "        float wing = 1.0 - smoothstep(0.8, 1.0, length(vec2(abs(d.x) - 1.3 * flap, d.y * 1.2) / vec2(1.4 * flap + 0.3, 1.3)));\n"
    "        vec3 bc = h < 0.13 ? vec3(1.0, 0.95, 0.5) : h < 0.27 ? vec3(1.0) : vec3(1.0, 0.65, 0.8);\n"
    "        res = mix(res, bc, wing);\n"
    "        res = mix(res, vec3(0.15), (1.0 - smoothstep(0.3, 0.6, length(d * vec2(2.5, 0.8)))) * 0.8);\n"
    "      }\n"
    "    }\n"
    // A flock of birds now and then: only their shadows sweep over the ground.
    "    if (outside && day > 0.3 && top >= 1 && top <= 3) {\n"
    "      float per = 26.0, k = floor(uTime / per), ph = fract(uTime / per);\n"
    "      vec2 base = vec2(-120.0 + ph * (uDim.x + 260.0) - uMargin, 30.0 + Hash(vec2(k, 2.0)) * 100.0 - ph * 30.0);\n"
    "      float sh = 0.0;\n"
    "      for (int b = 0; b < 4; b++) {\n"
    "        vec2 o = base + vec2(-float(b) * 11.0, float(b - (b / 2) * 2) * 9.0 - 4.0 + float(b) * 2.0);\n"
    "        vec2 d = gp - o; float fl = 0.6 + 0.4 * sin(uTime * 7.0 + float(b));\n"
    "        float v = 1.0 - smoothstep(0.9, 1.7, abs(abs(d.x) * 0.45 * fl - (-d.y + 1.0)) + max(abs(d.x) - 8.0, 0.0));\n"
    "        sh = max(sh, v * step(abs(d.y), 6.0));\n"
    "      }\n"
    "      res *= 1.0 - sh * 0.22 * day;\n"
    "    }\n"
    // Coast: seagulls circling overhead with shadows on the water, spray along the shore.
    "    if (false) {\n"   // seagulls: removed (looked crude up close)
    "      for (int g = 0; g < 3; g++) {\n"
    "        float gh = float(g) * 2.1 + 1.0;\n"
    "        vec2 p = vec2(120.0 + sin(uTime * 0.23 + gh) * 150.0, 50.0 + sin(uTime * 0.17 + gh * 1.7) * 40.0);\n"
    "        vec2 dir = normalize(vec2(cos(uTime * 0.23 + gh) * 150.0 * 0.23, cos(uTime * 0.17 + gh * 1.7) * 40.0 * 0.17) + 1e-4);\n"
    "        float fl = 0.5 + 0.5 * sin(uTime * 6.0 + gh);\n"
    "        for (int S = 0; S < 2; S++) {\n"
    "          vec2 d = gp - p - (S == 0 ? vec2(10.0, 22.0) : vec2(0.0));\n"
    "          d = vec2(dot(d, vec2(dir.y, -dir.x)), dot(d, dir));\n"   // wings across the flight direction
    "          float w = 1.0 - smoothstep(0.5, 1.2, abs(abs(d.x) * (0.25 + 0.25 * fl) - d.y * 0.9 - 0.8) + max(abs(d.x) - 7.0, 0.0) * 2.0);\n"
    "          if (S == 0) res *= 1.0 - w * 0.18 * day;\n"
    "          else res = mix(res, mix(vec3(0.25, 0.27, 0.3), vec3(0.98), smoothstep(0.0, 2.0, abs(d.x))) * mix(0.4, 1.0, day), w);\n"
    "        }\n"
    "      }\n"
    "    }\n"
    "    if ((here & 2) != 0 && top >= 1 && top <= 3 && wm > 0.5) {\n"
    "      ivec2 c0 = ivec2(floor(CellPos(gp)));\n"
    "      vec2 f = fract(CellPos(gp)) * 16.0;\n"   // distance (px) to the nearest land edge of this water tile
    "      float de = 99.0;\n"
    "      if ((Cell(c0 + ivec2(1, 0)) & 3) == 0) de = min(de, 16.0 - f.x);\n"
    "      if ((Cell(c0 - ivec2(1, 0)) & 3) == 0) de = min(de, f.x);\n"
    "      if ((Cell(c0 + ivec2(0, 1)) & 3) == 0) de = min(de, 16.0 - f.y);\n"
    "      if ((Cell(c0 - ivec2(0, 1)) & 3) == 0) de = min(de, f.y);\n"
    "      if (de < 5.0) {\n"
    "        vec2 sc = floor(wp / 4.0); float hh = Hash(sc);\n"
    "        float life = fract(uTime * 0.8 + hh * 7.0);\n"
    "        vec2 sp = (sc + 0.5 + 0.35 * vec2(Hash(sc + 1.3), Hash(sc + 2.7)) - 0.17) * 4.0;\n"
    "        float dot_ = (1.0 - smoothstep(0.3, 0.8, length(wp - sp))) * step(0.82, hh) * (1.0 - life) * (1.0 - de / 5.0);\n"
    "        res = mix(res, vec3(0.95, 0.98, 1.0), dot_ * 0.8);\n"
    "        res = mix(res, vec3(0.9, 0.95, 1.0), (1.0 - smoothstep(0.0, 2.5, de)) * (0.25 + 0.15 * sin(uTime * 2.0 + wp.x * 0.3)));\n"   // foam line
    "      }\n"
    "    }\n"
    // Volcanic ash: thick grey flakes drifting down.
    "    if (uLife.y > 0.0) {\n"
    "      for (int L = 0; L < 3; L++) {\n"
    "        float sz = 1.0 + float(L) * 0.6;\n"
    "        vec2 q = gp - vec2(-4.0 - float(L) * 3.0, 10.0 + float(L) * 6.0) * uTime + float(L) * 31.0;\n"
    "        vec2 c = floor(q / 9.0); float h = Hash(c + float(L));\n"
    "        if (h > 0.45) continue;\n"
    "        vec2 ctr = (c + 0.5) * 9.0 + vec2(sin(uTime * 2.0 + h * 30.0) * 2.5, 0.0);\n"
    "        float f = 1.0 - smoothstep(sz * 0.5, sz, length(q - ctr));\n"
    "        res = mix(res, vec3(0.62, 0.6, 0.58) * mix(0.5, 1.0, day), f * 0.85);\n"
    "      }\n"
    "      res = mix(res, vec3(0.55, 0.53, 0.5) * mix(0.5, 1.0, day), 0.10);\n"   // ashy air
    "    }\n"
    // Heat: a faint orange glow from below.
    "    if (uLife.z > 0.0) res *= vec3(1.06, 0.98, 0.92);\n"
    // Caves: water drips from the ceiling, with a ring where each lands.
    "    if (uMapType == 4) {\n"
    "      for (int k = 0; k < 6; k++) {\n"
    "        float per = 2.2 + float(k) * 0.37, ph = fract(uTime / per + float(k) * 0.31), n = floor(uTime / per + float(k) * 0.31);\n"
    "        vec2 land = vec2(Hash(vec2(n, float(k))) * 240.0, 30.0 + Hash(vec2(float(k), n)) * 110.0);\n"
    "        if (ph < 0.6) {\n"
    "          float y = land.y - 60.0 * (1.0 - ph / 0.6) * (1.0 - ph / 0.6);\n"
    "          vec2 d = gp - vec2(land.x, y);\n"
    "          res += vec3(0.6, 0.75, 0.9) * (1.0 - smoothstep(0.3, 0.9, length(d * vec2(1.6, 0.6)))) * 0.6;\n"
    "        } else {\n"
    "          float rr = (ph - 0.6) / 0.4 * 6.0;\n"
    "          float ring = 1.0 - smoothstep(0.0, 0.6, abs(length((gp - land) * vec2(1.0, 1.8)) - rr));\n"
    "          res += vec3(0.5, 0.65, 0.8) * ring * (1.0 - (ph - 0.6) / 0.4) * 0.35;\n"
    "        }\n"
    "      }\n"
    "    }\n"
    "  }\n"
    // Fireflies over grass and trees on summer nights.
    "  if (uFieldFx != 0 && top != 0 && uNight > 0.3 && uMapType != 4 && uMapType != 8 && uWeather == 0) {\n"
    "    vec2 base = floor(wp / 40.0); float glow = 0.0;\n"
    "    for (int i = -1; i <= 1; i++) for (int j = -1; j <= 1; j++) {\n"
    "      vec2 c = base + vec2(float(i), float(j)); float h = Hash(c * 1.37 + 11.0);\n"
    "      if (h > 0.45) continue;\n"
    "      vec2 p = c * 40.0 + 20.0 + 15.0 * vec2(sin(uTime * 0.31 + h * 40.0), cos(uTime * 0.23 + h * 23.0));\n"
    "      int f = Cell(ivec2(floor((p - uGridPos.zw * 16.0) / 16.0)));\n"
    "      if ((f & 5) == 0) continue;\n"
    "      float blink = smoothstep(0.2, 1.0, sin(uTime * (0.9 + h * 2.0) + h * 30.0));\n"
    "      float d = distance(wp, p);\n"
    "      glow += (exp(-d * d / 1.2) + exp(-d * d / 18.0) * 0.35) * blink;\n"
    "    }\n"
    "    res += vec3(0.75, 1.0, 0.35) * glow * (uNight - 0.3) * 1.2;\n"
    "  }\n"
    // Raindrops splashing on the ground and on water.
    "  if (uFieldFx != 0 && (uWeather == 1 || uWeather == 2) && top >= 1 && top <= 3 && (here & 1) == 0) {\n"
    "    float cs = 11.0 / max(uLiveWx.y, 0.35); vec2 c = floor(wp / cs); float h = Hash(c + 3.7);\n"
    "    float ph = fract(uTime * (0.8 + 0.5 * float(uWeather - 1)) + h);\n"
    "    vec2 ctr = (c + 0.25 + 0.5 * vec2(Hash(c + 1.1), Hash(c + 2.3))) * cs;\n"
    "    float d = distance(wp * vec2(1.0, 1.6), ctr * vec2(1.0, 1.6));\n"
    "    float ring = (1.0 - smoothstep(0.0, 0.7, abs(d - ph * 5.0))) * (1.0 - ph);\n"
    "    res = res * 0.94 + vec3(0.82, 0.88, 0.98) * ring * ((here & 34) != 0 ? 0.35 : 0.2);\n"
    "  }\n"
    // Sunlight shafts through dense trees.
    "  if (uFieldFx != 0 && top != 0 && uForest > 0.25 && uSun.w > 0.2 && uMapType != 4 && uMapType != 8) {\n"
    "    float x = (gp.x + gp.y * 0.6) * 0.03;\n"
    "    float ray = smoothstep(0.55, 0.85, Noise(vec2(x + uTime * 0.02, uTime * 0.03))) * (0.5 + 0.5 * Noise(vec2(x * 0.35, 7.0)));\n"
    "    ray *= 0.6 + 0.4 * Noise(gp * 0.02 + vec2(0.0, uTime * 0.1));\n"   // dust drifting through the beams
    "    res += vec3(1.0, 0.9, 0.65) * ray * 0.16 * smoothstep(0.25, 0.45, uForest) * uSun.w * (1.0 - 0.5 * res);\n"
    "  }\n"
    // Caves: slow drifting mist and floating dust.
    "  if (uFieldFx != 0 && top != 0 && uMapType == 4) {\n"
    "    vec2 q = wp * 0.012 + uTime * vec2(0.03, 0.012);\n"
    "    float m = Noise(q) * 0.6 + Noise(q * 2.3 + 4.0) * 0.4;\n"
    "    res = mix(res, vec3(0.62, 0.66, 0.74) * max(dot(res, vec3(0.33)) + 0.25, 0.3), smoothstep(0.45, 0.85, m) * 0.16);\n"
    "    vec2 dc = floor(wp / 18.0); float dh = Hash(dc);\n"
    "    vec2 dp = (dc + 0.5) * 18.0 + 7.0 * vec2(sin(uTime * 0.2 + dh * 50.0), cos(uTime * 0.15 + dh * 31.0));\n"
    "    if (dh < 0.3) res += vec3(0.9, 0.85, 0.7) * exp(-dot(wp - dp, wp - dp) / 0.5) * 0.35 * (0.5 + 0.5 * sin(uTime + dh * 20.0));\n"
    "  }\n"
    // ---- Live weather: overcast skies, fog banks and a rainbow after rain ----
    "  if (uFieldFx != 0 && top != 0 && uMapType != 4 && uMapType != 8 && uMapType != 9) {\n"
    "    float l = dot(res, vec3(0.299, 0.587, 0.114));\n"
    "    if (uLiveWx.x > 0.0) {\n"   // overcast: flatter, greyer light, heavier cloud shadows
    "      res = mix(res, mix(vec3(l), res, 0.75) * vec3(0.9, 0.93, 0.98), uLiveWx.x * 0.6);\n"
    "      vec2 q = wp * 0.006 + uTime * vec2(0.03, 0.012);\n"
    "      res *= 1.0 - smoothstep(0.45, 0.75, Noise(q) * 0.6 + Noise(q * 2.1 + 4.0) * 0.4) * 0.18 * uLiveWx.x;\n"
    "    }\n"
    "    if (uLiveWx.z > 0.0) {\n"   // fog: soft drifting banks
    "      vec2 q = wp * 0.012 + vec2(uTime * 0.04, uTime * 0.01);\n"
    "      float f = Noise(q) * 0.55 + Noise(q * 2.3 + 7.0) * 0.3 + Noise(q * 5.0 - uTime * 0.05) * 0.15;\n"
    "      vec3 fogc = mix(vec3(0.75, 0.78, 0.82), vec3(0.88, 0.9, 0.93), uSun.w);\n"
    "      if (uTint.a > 0.5) fogc *= mix(uTint.rgb, vec3(1.0), 0.4);\n"
    "      res = mix(res, fogc, uLiveWx.z * (0.35 + 0.4 * smoothstep(0.3, 0.75, f)));\n"
    "    }\n"
    "    if (uLiveWx.w > 0.0) {\n"   // rainbow arc across the sky side of the screen
    "      vec2 cpos = vec2(120.0, 430.0);\n"
    "      float rr = length((gp - cpos) * vec2(0.8, 1.0));\n"
    "      float band = (rr - 400.0) / 20.0;\n"
    "      if (band > 0.0 && band < 1.0) {\n"
    "        vec3 rb = clamp(abs(fract(band * 0.85 + vec3(0.0, 0.33, 0.67)) * 6.0 - 3.0) - 1.0, 0.0, 1.0);\n"
    "        float a = sin(band * 3.14159) * uLiveWx.w * 0.28 * smoothstep(95.0, 15.0, gp.y);\n"
    "        res = mix(res, res + rb * 0.6, a);\n"
    "      }\n"
    "    }\n"
    "  }\n"
    // Full-resolution weather over the whole widescreen frame (not over UI).
    "  if (uFieldFx != 0 && uWeather != 0 && top != 0) {\n"
    "    if (uWeather <= 2) {\n"
    "      float heavy = uWeather == 2 ? 1.0 : 0.0;\n"
    "      float r = Rain(gp, uTime, 5.0, 2.6, 0.30 + heavy * 0.25) * 0.55\n"
    "              + Rain(gp + 37.0, uTime, 8.0, 2.0, 0.22 + heavy * 0.2) * 0.75;\n"
    "      res = mix(res, vec3(0.80, 0.86, 0.95), clamp(r, 0.0, 1.0) * 0.55 * uLiveWx.y);\n"
    "    } else {\n"
    "      vec2 q = gp * vec2(0.035, 0.09) + vec2(uTime * 1.4, uTime * 0.15);\n"
    "      float n = Noise(q) * 0.6 + Noise(q * 2.3 + 5.0) * 0.4;\n"
    "      float grain = step(0.985, Hash(floor(gp * 2.0) + floor(uTime * 30.0)));\n"
    "      res = mix(res, vec3(0.86, 0.72, 0.50), clamp(n * 0.45 + grain * 0.4, 0.0, 0.7));\n"
    "    }\n"
    "  }\n"
    // Thin, mostly transparent fringes of layers in front of the top layer.
    // Battle lighting: the location's light and time of day on the scene and
    // the Pokémon, their shadows on the platforms, and move effects lighting
    // everything around them. Text box, health boxes and effects stay as drawn.
    "  if (uBattle != 0 && top != 0 && top != 5) {\n"
    "    bool isMon = top == 4 && (M.a & 1u) != 0u;\n"   // drawn from a Pokémon's own tiles
    "    int mk = isMon ? 0 : -1;\n"
    "    bool scene = top <= 3 || isMon;\n"
    "    if (scene) {\n"
    "      if (uScene >= 0 && top == 3) res = Backdrop(gp, uScene);\n"
    "      vec3 N = vec3(0.0, 0.0, 1.0);\n"
    "      if (mk >= 0) {\n"
    "        vec2 du = vec2(2.0 / uDim.x, 0.0), dv = vec2(0.0, 2.0 / uDim.y);\n"
    "        float hx = texture(uLayer[4], uv + du).a - texture(uLayer[4], uv - du).a;\n"
    "        float hy = texture(uLayer[4], uv + dv).a - texture(uLayer[4], uv - dv).a;\n"
    "        N = normalize(vec3(-hx * 0.8, -hy * 0.8, 1.0));\n"
    "        vec2 kd = normalize(vec2(-uBShadow.x, -max(uBShadow.y, 0.3)));\n"
    "        res *= 1.0 + dot(N.xy, kd) * 0.35;\n"
    "      }\n"
    "      if (top >= 2 && top <= 3) {\n"
    "        float sh = 0.0;\n"
    "        for (int k = 0; k < 4; k++) {\n"
    "          if (uMon[k].z <= 0.0) continue;\n"
    "          vec3 s = uMonFeet[k];\n"
    "          vec2 e = (gp - s.xy) / vec2(s.z * 0.9, s.z * 0.22);\n"
    "          sh = max(sh, (1.0 - smoothstep(0.4, 1.0, length(e))) * 0.32);\n"
    "          sh = max(sh, SilH(gp, s, uBShadow.xy, uMon[k].w) * uBShadow.z);\n"
    "        }\n"
    "        res *= 1.0 - sh;\n"
    "      }\n"
    "      if (uBTint.a > 0.5 && (uScene < 0 || isMon)) {\n"
    "        float l = dot(res, vec3(0.2126, 0.7152, 0.0722));\n"
    "        float night = clamp(uBTint.b > uBTint.r ? (uBTint.b - uBTint.r) * 2.0 : 0.0, 0.0, 1.0);\n"
    "        res = mix(res, vec3(l), night * 0.3) * mix(vec3(1.0), uBTint.rgb, 0.85);\n"
    "      }\n"
    "      if (uMoveLight.z > 0.0) {\n"
    "        vec2 to = uMoveLight.xy - gp; float d = length(to);\n"
    "        float f = exp(-d * d / (2.0 * uMoveLight.w * uMoveLight.w));\n"
    "        float facing = mk >= 0 ? 0.6 + max(dot(N.xy, to / max(d, 1e-3)), 0.0) * 2.0 : 1.0;\n"
    "        res += uMoveColor * f * uMoveLight.z * facing * (0.45 + 0.55 * res);\n"
    "      }\n"
    "      if (uMoveFx > 0.0) {\n"
    "        float e = uMoveFx; vec2 q = gp;\n"
    "        float l = dot(res, vec3(0.299, 0.587, 0.114));\n"
    "        if (uMoveType == 10) res = mix(res, res * vec3(1.12, 0.98, 0.86) + vec3(0.03, 0.01, 0.0), e);\n"
    "        else if (uMoveType == 11) {\n"
    "          float c = pow(abs(sin(q.x * 0.11 + sin(q.y * 0.13 + uTime * 1.7) * 2.0 + uTime) * sin(q.y * 0.09 - uTime * 1.3 + sin(q.x * 0.07) * 2.0)), 3.0);\n"
    "          res = mix(res, res * vec3(0.8, 0.95, 1.15) + vec3(0.5, 0.8, 1.0) * c * 0.35, e);\n"
    "        } else if (uMoveType == 13) {\n"
    "          float fl = step(0.55, Hash(vec2(floor(uTime * 18.0), 1.0)));\n"
    "          res = mix(res, res * (1.0 + fl * 0.5) + vec3(0.25, 0.22, 0.0) * fl, e);\n"
    "        } else if (uMoveType == 15) {\n"
    "          float edge = max(abs(gp.x / 240.0 - 0.5), abs(gp.y / 112.0 - 0.5)) * 2.0;\n"
    "          float fr = smoothstep(0.55, 1.0, edge + Noise(gp * 0.2) * 0.25);\n"
    "          res = mix(res, mix(vec3(l) * vec3(0.85, 0.95, 1.15), vec3(0.85, 0.93, 1.0), fr * 0.7), e);\n"
    "        } else if (uMoveType == 14) res = mix(res, res * vec3(1.1, 0.85, 1.2) + vec3(0.06, 0.0, 0.08), e);\n"
    "        else if (uMoveType == 7 || uMoveType == 17) {\n"
    "          float v = length((gp - vec2(120.0, 60.0)) / vec2(150.0, 90.0));\n"
    "          res = mix(res, res * mix(vec3(0.75, 0.65, 0.9), vec3(0.15, 0.08, 0.2), smoothstep(0.3, 1.0, v)), e);\n"
    "        } else if (uMoveType == 12) res = mix(res, res * vec3(0.9, 1.15, 0.85) + vec3(0.0, 0.05, 0.0), e);\n"
    "        else if (uMoveType == 16) res = mix(res, res * vec3(0.95, 0.85, 1.2), e);\n"
    "        else if (uMoveType == 3) res = mix(res, res * vec3(1.05, 0.85, 1.1), e);\n"
    "        else if (uMoveType == 4 || uMoveType == 5) {\n"
    "          float d = smoothstep(40.0, 112.0, gp.y) * (0.6 + 0.4 * Noise(gp * 0.05 + vec2(uTime * 0.5, -uTime * 0.8)));\n"
    "          res = mix(res, mix(res, vec3(0.72, 0.6, 0.42), d * 0.45), e);\n"
    "        } else if (uMoveType == 2) {\n"
    "          float w = smoothstep(0.75, 1.0, Noise(vec2(gp.x * 0.02 - uTime * 3.0, gp.y * 0.6)));\n"
    "          res = mix(res, res + vec3(0.25) * w, e);\n"
    "        }\n"
    "      }\n"
    "    }\n"
    "  }\n"
    // ---- Area atmosphere ----
    "  if (uFieldFx != 0 && uMood != 0 && top != 0) {\n"
    "    float l = dot(res, vec3(0.299, 0.587, 0.114));\n"
    "    float dayM = max(uSun.w, 0.3);\n"
    "    if (uMood == 1) {\n"   // rainforest: humid green air, soft contrast, light mist low on screen
    "      res = mix(res, vec3(l), 0.08) * vec3(0.94, 1.04, 0.94);\n"
    "      res = mix(res, vec3(0.70, 0.85, 0.72) * dayM, 0.10 + 0.06 * Noise(wp * 0.01 + uTime * 0.02));\n"
    "    } else if (uMood == 2) {\n"   // desert: bleached, hot, bright
    "      float sand = smoothstep(0.1, 0.3, res.r - res.b);\n"
    "      res = mix(res, mix(vec3(l), res, 0.85) * vec3(1.08, 1.02, 0.90) + 0.04, sand * dayM);\n"
    "    } else if (uMood == 3) {\n"   // Fortree: dappled light through the canopy
    "      vec2 q = wp * 0.06 + vec2(uTime * 0.05, uTime * 0.03);\n"
    "      float dap = smoothstep(0.55, 0.75, Noise(q) * 0.65 + Noise(q * 2.3 + 4.0) * 0.35);\n"
    "      res *= mix(0.9, 1.16, dap * uSun.w + (1.0 - uSun.w) * 0.5);\n"
    "      res *= vec3(0.98, 1.03, 0.97);\n"
    "    } else if (uMood == 4) {\n"   // Sootopolis: cool blue crater, deeper contrast
    "      res = ((res - 0.5) * 1.06 + 0.5) * vec3(0.92, 0.98, 1.08);\n"
    "    } else if (uMood == 5) {\n"   // Mt. Pyre: pale drifting mist
    "      float m = Noise(wp * 0.015 + vec2(uTime * 0.03, 0.0)) * 0.6 + Noise(wp * 0.04 - uTime * 0.02) * 0.4;\n"
    "      res = mix(mix(res, vec3(l), 0.2), vec3(0.82, 0.85, 0.9) * dayM, 0.18 + 0.2 * smoothstep(0.35, 0.8, m));\n"
    "    } else if (uMood == 6) {\n"   // Lavaridge: warm steam
    "      float m = Noise(wp * 0.03 + vec2(0.0, uTime * 0.12));\n"
    "      res = mix(res * vec3(1.04, 1.0, 0.95), vec3(0.95, 0.92, 0.88) * dayM, 0.12 * smoothstep(0.4, 0.9, m));\n"
    "    } else if (uMood == 7) {\n"   // open ocean: bright, airy, cyan
    "      res = mix(res, res * vec3(0.96, 1.02, 1.06) + 0.03, dayM);\n"
    "    }\n"
    "  }\n"
    "  if (uGiOn > 0.0 && uFieldFx != 0 && top != 0) {\n"   // ray-traced light, smoothed
    "    vec2 gq = (gp + vec2(uMargin, 0.0)) / vec2(textureSize(uGi, 0));\n"
    "    vec3 gi = vec3(0.0);\n"
    "    for (int i = -2; i <= 2; i++) for (int j = -2; j <= 2; j++) {\n"
    "      float w = exp(-float(i * i + j * j) / 4.0);\n"
    "      gi += texture(uGi, gq + vec2(float(i), float(j)) * 1.2 / vec2(textureSize(uGi, 0))).rgb * w;\n"
    "    }\n"
    "    gi = min(gi / 11.6, vec3(0.55));\n"
    "    if (uGiOn > 1.5) { oColor = vec4(gi * 3.0, 1.0); return; }\n"
    "    res = res * (1.0 + gi * 1.3) + gi * 0.05;\n"
    "    res = mix(res, 0.8 + 0.2 * (1.0 - exp(-(res - 0.8) / 0.2)), step(0.8, res));\n"   // soft highlight roll-off
    "  }\n"
    "  if (uTilt > 0.0 && uFieldFx != 0 && uBattle == 0 && top != 0 && uMapType != 8 && uMapType != 9) {\n"   // distance haze
    "    vec3 hz = mix(vec3(0.78, 0.86, 0.96), vec3(1.0, 0.78, 0.6), clamp((uTint.r - uTint.b) * 3.0, 0.0, 1.0));\n"
    "    if (uTint.a > 0.5) hz *= uTint.rgb;\n"
    "    if (uMapType == 4) hz = vec3(0.2, 0.18, 0.17);\n"
    "    res = mix(res, hz, smoothstep(0.42, 0.0, uvScreen.y) * 0.30 * uTilt / 0.4);\n"
    "  }\n"
    // ---- Window panels: rounded frosted frames with a soft shadow around the
    // game's framed windows (message box, menus, yes/no...) ----
    "  {\n"
    "    vec2 sp = vec2(vUv.x * uDim.x, (1.0 - vUv.y) * uDim.y);\n"
    "    for (int k = 0; k < 16; k++) {\n"
    "      if (k >= uPanels) break;\n"
    "      vec4 r = uPanel[k]; vec4 t = uPanelT[k];\n"
    "      int wbg = int(t.w) / 2;\n"
    "      if (all(greaterThanEqual(sp, r.xy)) && all(lessThan(sp, r.xy + r.zw))) {\n"   // the window itself: the game's pixels,
    "        vec2 e = min(sp - r.xy, r.xy + r.zw - sp);\n"                             // with its soft upscaled edge laid on the panel
    "        if (min(e.x, e.y) < 2.5) { float a = lay[clamp(wbg, 0, 3)].a; res = mix(vec3(0.99, 0.995, 1.0) * t.rgb, res, a); }\n"
    "        continue;\n"
    "      }\n"
    "      vec2 mg = mod(t.w, 2.0) > 0.5 ? vec2(11.0, 6.0) : vec2(6.0);\n"
    "      vec2 ce = r.xy + r.zw * 0.5, hs = r.zw * 0.5 + mg;\n"
    "      float rad = 6.0;\n"
    "      vec2 dq = abs(sp - ce) - (hs - rad);\n"
    "      float sd = length(max(dq, 0.0)) + min(max(dq.x, dq.y), 0.0) - rad;\n"
    "      vec2 ds = abs(sp - ce - vec2(1.0, 2.0)) - (hs - rad);\n"
    "      float sds = length(max(ds, 0.0)) + min(max(ds.x, ds.y), 0.0) - rad;\n"
    "      if (sd > 1.0 && sds > 5.0) continue;\n"
    "      float aa = max(fwidth(sd), 0.02);\n"
    "      float inside = 1.0 - smoothstep(-aa, aa, sd);\n"
    "      float fy = clamp((sp.y - (ce.y - hs.y)) / (hs.y * 2.0), 0.0, 1.0);\n"
    "      vec3 fill = mix(vec3(0.99, 0.995, 1.0), vec3(0.90, 0.93, 0.98), fy);\n"
    "      fill = mix(fill, vec3(0.72, 0.80, 0.95), (1.0 - smoothstep(0.0, 2.5, -sd)) * 0.55);\n"   // cool rim just inside the edge
    "      vec3 pc = res * (1.0 - (1.0 - inside) * (1.0 - smoothstep(-1.0, 5.0, sds)) * 0.35);\n"   // drop shadow
    "      pc = mix(pc, fill * t.rgb, inside);\n"
    "      res = pc;\n"
    "    }\n"
    "  }\n"
    "  for (int k = ti - 1; k >= 0; k--) if (order[k] == 0) { vec4 c = lay[0]; res = res * (1.0 - c.a) + c.rgb; }\n"
    "  oColor = vec4(res, 1.0);\n"
    "}\n";

static const char *kPresent =
    "#version 330 core\n"
    "in vec2 vUv;\n"
    "out vec4 oColor;\n"
    "uniform sampler2D uTex;\n"
    "uniform float uGrade;\n"
    "uniform float uFlip;\n"
    "uniform float uUScale;\n"
    "uniform vec2 uContentUv;\n" // content columns as u range; outside gets an ambient fill
    "uniform float uBloom;\n"
    "uniform float uSharpen;\n"
    "uniform vec2 uTexel;\n"
    "uniform vec3 uSoftSides;\n"
    "uniform sampler2D uSnap;\n"     // the screen as the battle intro began
    "uniform float uShatter;\n"      // intro time 0-1 (< 0: off)
    "uniform float uAspect;\n"
    "uniform int uIntroKind;\n"
    "uniform vec4 uCine;\n"         // x top bar, y bottom bar, z grade amount, w time
    "uniform int uCineStyle;\n"
    "uniform sampler2D uOverlay;\n"   // settings screen
    "uniform int uOverlayOn;\n"  // battles: x = left edge u, y = right edge u, z = message box top (v, from top)
    "void main() {\n"
    "  vec2 uv = vec2(vUv.x * uUScale, uFlip > 0.5 ? 1.0 - vUv.y : vUv.y);\n"
    "  vec3 c = texture(uTex, uv).rgb;\n"
    "  if (uv.x < uContentUv.x || uv.x > uContentUv.y) {\n"
    // Blurred, dimmed copy of the nearest strip of the picture.
    "    float edge = uv.x < uContentUv.x ? uContentUv.x : uContentUv.y;\n"
    "    float dir = uv.x < uContentUv.x ? 1.0 : -1.0;\n"
    "    float span = (uContentUv.y - uContentUv.x) * 0.18;\n"
    "    vec3 acc = vec3(0.0); float n = 0.0;\n"
    "    for (int i = 0; i < 6; i++) for (int j = -4; j <= 4; j++) {\n"
    "      vec2 q = vec2(edge + dir * span * (float(i) + 0.5) / 6.0, clamp(uv.y + float(j) * 0.035, 0.0, 1.0));\n"
    "      acc += texture(uTex, q).rgb; n += 1.0;\n"
    "    }\n"
    "    float fade = 1.0 - clamp(abs(uv.x - edge) / max(span * 1.5, 1e-4), 0.0, 1.0) * 0.35;\n"
    "    c = acc / n * 0.38 * fade;\n"
    "  }\n"
    // Battles: the mirrored scenery beside the original screen is shown out
    // of focus (above the message box), so it doesn't look like stretched art.
    "  if (uSoftSides.z > 0.0 && (uv.x < uSoftSides.x || uv.x > uSoftSides.y) && (1.0 - uv.y) < uSoftSides.z) {\n"
    "    vec3 acc = vec3(0.0); float wsum = 0.0;\n"
    "    for (int i = -4; i <= 4; i++) for (int j = -4; j <= 4; j++) {\n"
    "      vec2 o = vec2(float(i), float(j)) * vec2(0.0042, 0.0075);\n"
    "      vec2 q = uv + o;\n"
    "      q.y = min(q.y, 1.0);\n"
    "      q.y = max(q.y, 1.0 - uSoftSides.z + 0.004);\n"  // don't pull in the message box
    "      float w = exp(-float(i * i + j * j) / 10.0);\n"
    "      acc += texture(uTex, q).rgb * w; wsum += w;\n"
    "    }\n"
    "    float d = uv.x < uSoftSides.x ? (uSoftSides.x - uv.x) / max(uSoftSides.x, 1e-4) : (uv.x - uSoftSides.y) / max(1.0 - uSoftSides.y, 1e-4);\n"
    "    vec3 b = acc / wsum;\n"
    "    b = mix(b, vec3(dot(b, vec3(0.2126, 0.7152, 0.0722))), 0.25);\n"
    "    c = b * (0.92 - 0.22 * d);\n"
    "  }\n"
    // Contrast-adaptive sharpening: restores crispness lost to scaling
    // without halos (less sharpening where local contrast is already high).
    "  if (uSharpen > 0.0) {\n"
    "    vec3 n = texture(uTex, uv + vec2(0.0, uTexel.y)).rgb, s = texture(uTex, uv - vec2(0.0, uTexel.y)).rgb;\n"
    "    vec3 e = texture(uTex, uv + vec2(uTexel.x, 0.0)).rgb, w = texture(uTex, uv - vec2(uTexel.x, 0.0)).rgb;\n"
    "    vec3 mn = min(c, min(min(n, s), min(e, w))), mx = max(c, max(max(n, s), max(e, w)));\n"
    "    vec3 amp = sqrt(clamp(min(mn, 1.0 - mx) / max(mx, vec3(1e-4)), 0.0, 1.0));\n"
    "    vec3 wgt = -amp * mix(0.125, 0.2, uSharpen);\n"
    "    c = clamp((c + (n + s + e + w) * wgt) / (1.0 + 4.0 * wgt), 0.0, 1.0);\n"
    "  }\n"
    "  if (uBloom > 0.0) {\n"   // soft glow around bright areas
    "    vec3 b = vec3(0.0);\n"
    "    for (int i = 0; i < 12; i++) {\n"
    "      float a = float(i) * 0.5236;\n"
    "      for (int r = 1; r <= 2; r++) {\n"
    "        vec3 t = texture(uTex, uv + vec2(cos(a), sin(a)) * uTexel * float(r) * 6.0).rgb;\n"
    "        b += max(t - vec3(0.82), vec3(0.0));\n"
    "      }\n"
    "    }\n"
    "    c += b / 24.0 * uBloom;\n"
    "  }\n"
    "  if (uGrade > 0.0) {\n"
    "    float l = dot(c, vec3(0.2126, 0.7152, 0.0722));\n"
    "    vec3 sat = mix(vec3(l), c, 1.10);\n"                       // gentle vibrance
    "    vec3 con = (sat - 0.5) * 1.06 + 0.5;\n"                    // gentle contrast
    "    c = mix(c, clamp(con, 0.0, 1.0), uGrade);\n"
    "  }\n"
    // Battle intro: the screen cracks, then breaks into shards that spin
    // away toward the camera, revealing the game's own transition behind.
    "  if (uShatter >= 0.0 && (uIntroKind == 5 || uIntroKind == 9)) {\n"
    "    vec2 grid = uIntroKind == 9 ? vec2(12.0, 8.0) : vec2(9.0, 6.0);\n"
    "    float t = uShatter;\n"
    "    float fly = smoothstep(0.18, 1.0, t);\n"
    "    vec4 shard = vec4(0.0);\n"
    "    for (int cx = 0; cx < 12; cx++) for (int cy = 0; cy < 8; cy++) {\n"
    "      if (float(cx) >= grid.x || float(cy) >= grid.y) continue;\n"
    "      vec2 cell = vec2(float(cx), float(cy));\n"
    "      float h = fract(sin(dot(cell, vec2(12.9898, 78.233))) * 43758.5453);\n"
    "      float h2 = fract(h * 91.7);\n"
    "      vec2 seed = (cell + 0.25 + 0.5 * vec2(h, h2)) / grid;\n"
    "      vec2 away = normalize(seed - vec2(0.5) + 0.001);\n"
    "      float sc = 1.0 + fly * (0.6 + 1.2 * h);\n"   // flying toward the camera
    "      float ang = fly * (h2 - 0.5) * 5.0;\n"
    "      vec2 off = away * fly * (0.25 + 0.6 * h) + vec2(0.0, -fly * fly * 0.6);\n"
    "      vec2 d = (uv - seed - off) * vec2(uAspect, 1.0) / sc;\n"
    "      d = mat2(cos(ang), sin(ang), -sin(ang), cos(ang)) * d;\n"
    "      vec2 q = seed + d / vec2(uAspect, 1.0);\n"
    "      if (q.x < 0.0 || q.y < 0.0 || q.x > 1.0 || q.y > 1.0) continue;\n"
    "      vec2 qc = floor(q * grid); float best = 9.0, second = 9.0; vec2 bestSeed = vec2(-1.0);\n"
    "      for (int i = -1; i <= 1; i++) for (int j = -1; j <= 1; j++) {\n"
    "        vec2 nc = qc + vec2(float(i), float(j));\n"
    "        float nh = fract(sin(dot(nc, vec2(12.9898, 78.233))) * 43758.5453);\n"
    "        vec2 ns = (nc + 0.25 + 0.5 * vec2(nh, fract(nh * 91.7))) / grid;\n"
    "        float dd = length((q - ns) * vec2(uAspect, 1.0));\n"
    "        if (dd < best) { second = best; best = dd; bestSeed = ns; } else if (dd < second) second = dd;\n"
    "      }\n"
    "      if (distance(bestSeed, seed) > 1e-4) continue;\n"
    "      float edge = second - best;\n"
    "      vec3 col = texture(uSnap, vec2(q.x * uUScale, uFlip > 0.5 ? 1.0 - q.y : q.y)).rgb;\n"
    "      col *= 1.0 + 0.25 * sin(ang * 2.0 + h * 6.0) * fly;\n"   // glinting as they turn
    "      col = mix(col, vec3(1.0), (1.0 - smoothstep(0.0, 0.006, edge)) * (0.9 - 0.6 * fly));\n"   // cracks
    "      float a = 1.0 - smoothstep(0.75, 1.0, t);\n"
    "      if (sc > shard.a) shard = vec4(mix(c, col, a), sc);\n"
    "    }\n"
    "    if (shard.a > 0.0) c = shard.rgb;\n"
    "    else c *= smoothstep(0.1, 0.6, t);\n"   // behind the shards: the game's transition
    "    if (uIntroKind == 9) c += vec3(1.0) * (1.0 - smoothstep(0.0, 0.12, t)) * 0.9;\n"   // legendary: a flash first
    "  }\n"
    "  if (uShatter >= 0.0 && uIntroKind != 5 && uIntroKind != 9) {\n"
    "    float t = uShatter;\n"
    "    vec2 sv = vec2(uv.x * uUScale, uFlip > 0.5 ? 1.0 - uv.y : uv.y);\n"
    "    vec2 ctr = vec2(0.5 * uUScale, 0.5);\n"
    "    vec3 snap = vec3(0.0); float keep = 0.0;\n"   // keep: how much of the old screen still shows
    "    if (uIntroKind == 0) {\n"   // wild: soft zoom blur into a white bloom
    "      vec3 acc = vec3(0.0);\n"
    "      for (int k = 0; k < 10; k++) acc += texture(uSnap, ctr + (sv - ctr) * (1.0 - t * 0.35 * float(k) / 9.0)).rgb;\n"
    "      snap = mix(acc / 10.0, vec3(1.0), smoothstep(0.35, 0.8, t) * 0.8); keep = 1.0 - smoothstep(0.7, 1.0, t);\n"
    "    } else if (uIntroKind == 1) {\n"   // wild: iris closing on the centre
    "      float rad = mix(1.0, 0.0, smoothstep(0.0, 0.85, t));\n"
    "      float d = length((uv - 0.5) * vec2(uAspect, 1.0));\n"
    "      snap = texture(uSnap, sv).rgb; keep = 1.0 - smoothstep(rad - 0.04, rad + 0.04, d);\n"
    "      snap *= keep; keep = max(keep, 1.0 - smoothstep(0.85, 1.0, t));\n"
    "    } else if (uIntroKind == 2) {\n"   // wild: water ripple that washes the scene away
    "      float d = length((uv - 0.5) * vec2(uAspect, 1.0));\n"
    "      vec2 o = normalize(uv - 0.5 + 0.0001) * sin(d * 40.0 - t * 18.0) * 0.012 * t;\n"
    "      snap = mix(texture(uSnap, sv + o).rgb, vec3(0.85, 0.92, 1.0), smoothstep(0.4, 0.9, t) * 0.7);\n"
    "      keep = 1.0 - smoothstep(0.75, 1.0, t);\n"
    "    } else if (uIntroKind == 3) {\n"   // wild: a band of light sweeps across
    "      float x = uv.x + uv.y * 0.4;\n"
    "      float front = mix(-0.3, 1.7, t);\n"
    "      snap = texture(uSnap, sv).rgb + vec3(1.0, 0.95, 0.8) * exp(-pow((x - front) * 8.0, 2.0)) * 0.9;\n"
    "      keep = 1.0 - smoothstep(front - 0.1, front + 0.02, x) * 0.0 - smoothstep(0.0, 0.2, front - x);\n"
    "      keep = clamp(keep, 0.0, 1.0);\n"
    "    } else if (uIntroKind == 4) {\n"   // wild: dissolves into soft points
    "      vec2 cell = floor(uv * vec2(uAspect, 1.0) * 60.0);\n"
    "      float h = fract(sin(dot(cell, vec2(12.9898, 78.233))) * 43758.5453);\n"
    "      snap = texture(uSnap, sv).rgb; keep = 1.0 - smoothstep(h * 0.8, h * 0.8 + 0.15, t);\n"
    "    } else if (uIntroKind == 6) {\n"   // trainer: horizontal slices slide apart
    "      float band = floor(uv.y * 16.0);\n"
    "      float dir = mod(band, 2.0) < 1.0 ? 1.0 : -1.0;\n"
    "      float sl = pow(smoothstep(0.1, 0.9, t), 2.0) * 1.2 * dir;\n"
    "      vec2 q = vec2(sv.x - sl * uUScale, sv.y);\n"
    "      snap = texture(uSnap, q).rgb; keep = (q.x >= 0.0 && q.x <= uUScale) ? 1.0 : 0.0;\n"
    "    } else if (uIntroKind == 7) {\n"   // trainer: spiral twist into the centre
    "      vec2 d = (uv - 0.5) * vec2(uAspect, 1.0);\n"
    "      float a = t * t * 9.0 * (1.0 - length(d));\n"
    "      d = mat2(cos(a), sin(a), -sin(a), cos(a)) * d / max(1.0 - t * 0.9, 0.05);\n"
    "      vec2 q = 0.5 + d / vec2(uAspect, 1.0);\n"
    "      snap = texture(uSnap, vec2(q.x * uUScale, uFlip > 0.5 ? 1.0 - q.y : q.y)).rgb;\n"
    "      keep = (q.x >= 0.0 && q.x <= 1.0 && q.y >= 0.0 && q.y <= 1.0) ? 1.0 - smoothstep(0.8, 1.0, t) : 0.0;\n"
    "    } else {\n"   // trainer: zoom punch with speed lines
    "      vec2 d = uv - 0.5;\n"
    "      float z = 1.0 + pow(t, 3.0) * 6.0;\n"
    "      snap = texture(uSnap, ctr + (sv - ctr) / z).rgb;\n"
    "      float ang = atan(d.y, d.x);\n"
    "      float lines = step(0.8, fract(sin(floor(ang * 40.0) * 91.3) * 43758.5)) * smoothstep(0.1, 0.5, length(d));\n"
    "      snap = mix(snap, vec3(1.0), lines * smoothstep(0.1, 0.4, t) * 0.8);\n"
    "      keep = 1.0 - smoothstep(0.75, 1.0, t);\n"
    "    }\n"
    "    c = mix(c, snap, keep);\n"
    "  }\n"
    // Cinematic look for story moments: colour grade, vignette, a pulse of
    // coloured light for legendaries, and letterbox bars.
    "  if (uCine.z > 0.001 && uCineStyle > 0) {\n"
    "    const vec3 kTint[17] = vec3[17](vec3(1.0), vec3(1.0, 0.97, 0.95), vec3(1.02, 1.0, 0.97), vec3(0.92, 0.98, 1.05),\n"
    "      vec3(1.28, 0.82, 0.7), vec3(0.74, 0.92, 1.28), vec3(0.84, 1.22, 0.9), vec3(1.08, 0.98, 0.82), vec3(1.02, 0.96, 1.1),\n"
    "      vec3(1.1, 0.86, 0.86), vec3(0.96, 0.86, 1.12), vec3(0.88, 0.98, 1.15), vec3(1.12, 0.95, 0.8), vec3(1.14, 1.04, 0.82),\n"
    "      vec3(1.06, 1.03, 0.9), vec3(1.0, 0.98, 0.97), vec3(1.03, 1.0, 0.98));\n"
    "    const float kSat[17] = float[17](1.0, 1.1, 1.15, 0.75, 1.1, 1.05, 1.05, 0.65, 0.9, 0.95, 0.9, 0.85, 1.05, 1.1, 1.05, 0.88, 1.15);\n"
    "    const float kCon[17] = float[17](1.0, 1.08, 1.1, 1.12, 1.15, 1.12, 1.1, 1.08, 1.0, 1.15, 1.1, 1.05, 1.12, 1.1, 1.0, 1.1, 1.08);\n"
    "    const float kVig[17] = float[17](0.0, 0.35, 0.4, 0.5, 0.55, 0.55, 0.5, 0.5, 0.35, 0.55, 0.55, 0.45, 0.5, 0.4, 0.25, 0.45, 0.35);\n"
    "    const vec4 kPulse[17] = vec4[17](vec4(0.0), vec4(0.0), vec4(0.0), vec4(0.0), vec4(1.0, 0.3, 0.1, 0.3),\n"
    "      vec4(0.2, 0.5, 1.0, 0.3), vec4(0.3, 1.0, 0.5, 0.26), vec4(1.0, 0.8, 0.4, 0.08), vec4(0.8, 0.6, 1.0, 0.14),\n"
    "      vec4(1.0, 0.2, 0.2, 0.08), vec4(0.6, 0.3, 1.0, 0.1), vec4(0.6, 0.9, 1.0, 0.08), vec4(1.0, 0.5, 0.1, 0.08),\n"
    "      vec4(1.0, 0.85, 0.4, 0.12), vec4(1.0, 0.9, 0.5, 0.2), vec4(0.0), vec4(0.0));\n"
    "    int st = clamp(uCineStyle, 0, 16);\n"
    "    vec3 g = c;\n"
    "    float l = dot(g, vec3(0.2126, 0.7152, 0.0722));\n"
    "    g = mix(vec3(l), g, kSat[st]);\n"
    "    g = (g - 0.5) * kCon[st] + 0.5;\n"
    "    g *= kTint[st];\n"
    "    vec2 d = vUv - 0.5;\n"
    "    float vig = smoothstep(0.25, 0.85, length(d * vec2(1.25, 1.0)));\n"
    "    g *= 1.0 - vig * kVig[st];\n"
    "    vec4 pu = kPulse[st];\n"
    "    g += pu.rgb * pu.a * (0.6 + 0.4 * sin(uCine.w * 1.8)) * (0.4 + vig);\n"
    "    c = mix(c, clamp(g, 0.0, 1.0), uCine.z);\n"
    "  }\n"
    "  if (uCine.x > 0.001 && vUv.y > 1.0 - 0.105 * uCine.x) c = vec3(0.0);\n"
    "  if (uCine.y > 0.001 && vUv.y < 0.105 * uCine.y) c = vec3(0.0);\n"
    "  if (uOverlayOn != 0) { vec4 o = texture(uOverlay, vec2(vUv.x, 1.0 - vUv.y)); c = mix(c, o.rgb, o.a); }\n"
    "  oColor = vec4(c, 1.0);\n"
    "}\n";

// ---------------------------------------------------------------------------

// 2D ray-traced lighting: light from every glowing pixel, door and lantern,
// traced over the screen at native resolution and blocked by walls, roofs
// and trees. Its result is smoothed when the composite samples it.
static const char *kGi =
    "#version 330 core\n"
    "out vec4 oColor;\n"
    "uniform sampler2D uFrame;      // native frame, top row first\n"
    "uniform sampler2D uTop;        // BG1 (roofs, canopies), native\n"
    "uniform vec2 uDim;\n"
    "uniform float uMargin;\n"
    "uniform vec4 uGridPos;\n"
    "uniform int uGrid[144];\n"
    "uniform int uNumLights;\n"
    "uniform vec3 uLights[24];\n"
    "uniform vec3 uLantern;         // xy position, z on\n"
    "uniform float uStr;            // overall strength\n"
    "uniform float uNightWin;       // lit windows at night\n"
    "uniform float uLava;           // lava/fire glows\n"
    "int Cell(ivec2 c) {\n"
    "  if (c.x < 0 || c.y < 0 || c.x >= 36 || c.y >= 16) return 0;\n"
    "  int i = c.y * 36 + c.x;\n"
    "  return (uGrid[i >> 2] >> ((i & 3) * 8)) & 255;\n"
    "}\n"
    "float Solid(vec2 gp) {\n"
    "  vec2 q = (gp - uGridPos.xy) / 16.0 - 0.5; ivec2 i = ivec2(floor(q)); vec2 f = fract(q);\n"
    "  float a = float(Cell(i) & 1), b = float(Cell(i + ivec2(1, 0)) & 1);\n"
    "  float c = float(Cell(i + ivec2(0, 1)) & 1), d = float(Cell(i + ivec2(1, 1)) & 1);\n"
    "  return smoothstep(0.3, 0.7, mix(mix(a, b, f.x), mix(c, d, f.x), f.y));\n"
    "}\n"
    "// Light given off at a pixel (screen px, top-first).\n"
    "vec3 Emit(vec2 p) {\n"
    "  vec3 e = vec3(0.0);\n"
    "  vec2 sp = p + vec2(uMargin, 0.0);\n"
    "  if (sp.x < 0.0 || sp.y < 0.0 || sp.x >= uDim.x || sp.y >= uDim.y) return e;\n"
    "  vec3 c = texelFetch(uFrame, ivec2(sp), 0).rgb;\n"
    "  float mx = max(c.r, max(c.g, c.b)), mn = min(c.r, min(c.g, c.b));\n"
    "  // warm, saturated, very bright pixels: lamps, fire, signs\n"
    "  e += c * smoothstep(0.85, 0.98, mx) * smoothstep(0.3, 0.55, mx - mn) * step(c.b, c.r) * 1.2 * uLava;\n"
    "  // lava and embers\n"
    "  e += vec3(1.0, 0.45, 0.12) * uLava * smoothstep(0.55, 0.8, c.r) * smoothstep(0.25, 0.5, c.r - c.b) * smoothstep(0.2, 0.0, c.b - 0.2);\n"
    "  // lit windows: pale-blue glass inside a solid wall\n"
    "  if (uNightWin > 0.0) {\n"
    "    ivec2 cc = ivec2(floor((p - uGridPos.xy) / 16.0));\n"
    "    if ((Cell(cc) & 1) != 0 && c.b > 0.6 && c.b - c.r > 0.18 && c.g > 0.5) e += vec3(1.0, 0.75, 0.4) * uNightWin * 1.1;\n"
    "  }\n"
    "  for (int k = 0; k < uNumLights; k++)\n"
    "    e += vec3(1.0, 0.72, 0.4) * (1.0 - smoothstep(2.0, 6.0, distance(p, uLights[k].xy))) * 0.9;\n"
    "  if (uLantern.z > 0.0)\n"
    "    e += vec3(1.0, 0.8, 0.55) * (1.0 - smoothstep(2.0, 5.0, distance(p, uLantern.xy))) * 2.0;\n"
    "  return e;\n"
    "}\n"
    "float Block(vec2 p) {\n"
    "  vec2 sp = p + vec2(uMargin, 0.0);\n"
    "  float a = texelFetch(uTop, ivec2(clamp(sp, vec2(0.0), uDim - 1.0)), 0).a;\n"
    "  return max(Solid(p), a);\n"
    "}\n"
    "void main() {\n"
    "  vec2 p = gl_FragCoord.xy - vec2(uMargin, 0.0);   // screen px, top-first (texture rows = screen rows)\n"
    "  float noise = fract(52.9829189 * fract(dot(gl_FragCoord.xy, vec2(0.06711056, 0.00583715))));\n"
    "  vec3 acc = Emit(p) * 0.15;\n"
    "  bool inside = Block(p) > 0.5;\n"
    "  const int RAYS = 20;\n"
    "  for (int r = 0; r < RAYS; r++) {\n"
    "    float a = (float(r) + noise) * 6.2831853 / float(RAYS);\n"
    "    vec2 dir = vec2(cos(a), sin(a));\n"
    "    float t = 1.5, trans = 1.0;\n"
    "    for (int s = 0; s < 22; s++) {\n"
    "      vec2 q = p + dir * t;\n"
    "      vec3 e = Emit(q);\n"
    "      float lum = max(e.r, max(e.g, e.b));\n"
    "      if (lum > 0.02) { acc += e * trans / (1.0 + t * t * 0.0016); break; }\n"
    "      if (!inside || t > 6.0) {\n"
    "        float b = Block(q);\n"
    "        trans *= 1.0 - b * 0.85;   // walls, roofs and trees block light\n"
    "        if (trans < 0.05) break;\n"
    "      }\n"
    "      t += 1.5 + t * 0.12;\n"
    "      if (t > 90.0) break;\n"
    "    }\n"
    "  }\n"
    "  if (inside) acc *= 0.2;\n"   // light falls on the ground, it doesn't burn the walls it comes from
    "  oColor = vec4(acc / float(RAYS) * uStr * 3.0, 1.0);\n"
    "}\n";

static GLuint sProgGi, sGiTex, sGiFbo;
static GLuint sSnapTex, sOverlayTex, sFollowTex;
static int sFollowVersion = -1;
static int sOverlayOn, sGiEnabled = 1, sShatterEnabled = 1;
void HdSetGi(int on) { sGiEnabled = on; }
int HdGetGi(void) { return sGiEnabled; }
void HdSetShatter(int on) { sShatterEnabled = on; }
int HdGetShatter(void) { return sShatterEnabled; }
void HdSetOverlay(const uint32_t *rgba, int w, int h)
{
    sOverlayOn = rgba != NULL;
    if (!rgba)
        return;
    if (!sOverlayTex)
    {
        glGenTextures(1, &sOverlayTex);
        glBindTexture(GL_TEXTURE_2D, sOverlayTex);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    }
    glBindTexture(GL_TEXTURE_2D, sOverlayTex);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, w, h, 0, GL_BGRA, GL_UNSIGNED_BYTE, rgba);
}
static int sSnapW, sSnapH, sIntroSerial, sIntroFrame = -1000;
extern int gPcIntroSerial;
static float sGiStr;

static int sReady;
static GLuint sVao;
static GLuint sProgXbr, sProgComp, sProgPresent;
static GLuint sLayerTex[5], sUpTex[6], sUpFbo[6]; // [5] = flattened original frame
static GLuint sMetaTex, sLineTex, sFrameTex;
static GLuint sCompTex, sCompFbo;
static GLuint sTrefTex[5], sAtlasTex, sGlyphTex, sPalTex;
static int sPackScale, sPackPerRow, sGlyphScale;
static int sScale = 4;
static int sW = GBA_W;
static int sCompW, sCompH; // composite size = on-screen size of the game image
static int sLastWinW, sLastWinH;
static int sGrade = 1;
static int sLighting = 1;
static float sTilt = 0.0f;   // HD-2D tilt (off by default): F8 cycles off / gentle / strong
void HdCycleTilt(void) { sTilt = sTilt <= 0.0f ? 0.25f : sTilt < 0.3f ? 0.4f : sTilt < 0.5f ? 0.6f : 0.0f; }
float HdGetTilt(void) { return sTilt; }
void HdSetTilt(float t) { sTilt = t < 0 ? 0 : t > 1.2f ? 1.2f : t; }
static float sNight;

static int LoadGl(void)
{
#define X(ret, name, args) \
    p_##name = (ret (GLAPIENTRY *) args)SDL_GL_GetProcAddress(#name); \
    if (!p_##name) { fprintf(stderr, "GL: missing %s\n", #name); return -1; }
    GLFUNCS
#undef X
    return 0;
}

static GLuint Compile(GLenum type, const char *src)
{
    GLuint s = glCreateShader(type);
    GLint ok = 0;
    glShaderSource(s, 1, &src, NULL);
    glCompileShader(s);
    glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
    if (!ok)
    {
        char log[4096];
        glGetShaderInfoLog(s, sizeof(log), NULL, log);
        fprintf(stderr, "GL shader error:\n%s\n", log);
        return 0;
    }
    return s;
}

static GLuint Program(const char *frag)
{
    GLuint v = Compile(GL_VERTEX_SHADER, kVert), f = Compile(GL_FRAGMENT_SHADER, frag), p;
    GLint ok = 0;
    if (!v || !f)
        return 0;
    p = glCreateProgram();
    glAttachShader(p, v);
    glAttachShader(p, f);
    glLinkProgram(p);
    glGetProgramiv(p, GL_LINK_STATUS, &ok);
    glDeleteShader(v);
    glDeleteShader(f);
    if (!ok)
    {
        char log[4096];
        glGetProgramInfoLog(p, sizeof(log), NULL, log);
        fprintf(stderr, "GL link error:\n%s\n", log);
        return 0;
    }
    return p;
}

static GLuint MakeTex(int w, int h, GLint ifmt, GLenum fmt, GLint filter)
{
    GLuint t;
    glGenTextures(1, &t);
    glBindTexture(GL_TEXTURE_2D, t);
    glTexImage2D(GL_TEXTURE_2D, 0, ifmt, w, h, 0, fmt, GL_UNSIGNED_BYTE, NULL);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, filter);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, filter);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    return t;
}

static GLuint MakeFbo(GLuint tex)
{
    GLuint f;
    glGenFramebuffers(1, &f);
    glBindFramebuffer(GL_FRAMEBUFFER, f);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, tex, 0);
    if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE)
        fprintf(stderr, "GL: framebuffer incomplete\n");
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    return f;
}

static void AllocScaled(void)
{
    int i, w = sW * sScale, h = GBA_H * sScale;
    for (i = 0; i < 6; i++)
    {
        if (sUpTex[i])
            glDeleteTextures(1, &sUpTex[i]);
        sUpTex[i] = MakeTex(w, h, GL_RGBA8, GL_RGBA, GL_LINEAR);
        sUpFbo[i] = MakeFbo(sUpTex[i]);
    }
}

// The composite is rendered at the size the game image occupies on screen,
// so the final image is native-resolution rather than a stretched texture.
static void EnsureComposite(int w, int h)
{
    if (w < 1) w = 1;
    if (h < 1) h = 1;
    if (sCompTex && w == sCompW && h == sCompH)
        return;
    if (sCompTex)
        glDeleteTextures(1, &sCompTex);
    sCompTex = MakeTex(w, h, GL_RGBA8, GL_RGBA, GL_LINEAR);
    sCompFbo = MakeFbo(sCompTex);
    sCompW = w;
    sCompH = h;
}

int HdInit(void)
{
    int i;
    if (LoadGl() != 0)
        return -1;
    sProgXbr = Program(kXbr);
    sProgComp = Program(kComposite);
    sProgPresent = Program(kPresent);
    sProgGi = Program(kGi);
    if (!sProgXbr || !sProgComp || !sProgPresent || !sProgGi)
        return -1;

    glGenVertexArrays(1, &sVao);
    glBindVertexArray(sVao);
    glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
    glPixelStorei(GL_PACK_ALIGNMENT, 4);

    for (i = 0; i < 5; i++)
        sLayerTex[i] = MakeTex(PC_MAX_W, GBA_H, GL_RGBA8, GL_RGBA, GL_NEAREST);
    sMetaTex = MakeTex(PC_MAX_W, GBA_H, GL_RGBA8UI, GL_RGBA_INTEGER, GL_NEAREST);
    sLineTex = MakeTex(4, GBA_H, GL_RGBA8UI, GL_RGBA_INTEGER, GL_NEAREST);
    sFrameTex = MakeTex(PC_MAX_W, GBA_H, GL_RGBA8, GL_BGRA, GL_NEAREST);
    sGiTex = MakeTex(PC_MAX_W, GBA_H, GL_RGBA8, GL_RGBA, GL_LINEAR);
    sGiFbo = MakeFbo(sGiTex);
    sW = gPcScreenW;
    AllocScaled();

    glUseProgram(sProgComp);
    {
        GLint loc = glGetUniformLocation(sProgComp, "uLayer");
        int units[5] = { 0, 1, 2, 3, 4 };
        for (i = 0; i < 5; i++)
        {
            char name[32];
            snprintf(name, sizeof(name), "uLayer[%d]", i);
            glUniform1i(glGetUniformLocation(sProgComp, name), units[i]);
        }
        (void)loc;
        glUniform1i(glGetUniformLocation(sProgComp, "uMeta"), 5);
        glUniform1i(glGetUniformLocation(sProgComp, "uFlat"), 15);
        glUniform1i(glGetUniformLocation(sProgComp, "uLine"), 6);
        for (i = 0; i < 5; i++)
        {
            char name[32];
            snprintf(name, sizeof(name), "uTref[%d]", i);
            glUniform1i(glGetUniformLocation(sProgComp, name), 7 + i);
        }
        glUniform1i(glGetUniformLocation(sProgComp, "uAtlas"), 12);
        glUniform1i(glGetUniformLocation(sProgComp, "uGlyphs"), 13);
        glUniform1i(glGetUniformLocation(sProgComp, "uPal"), 14);
        glUniform1i(glGetUniformLocation(sProgComp, "uGi"), 16);
    }
    {
        const uint32_t *px;
        int aw, ah;
        int gw, gh;
        for (i = 0; i < 5; i++)
        {
            glGenTextures(1, &sTrefTex[i]);
            glBindTexture(GL_TEXTURE_2D, sTrefTex[i]);
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA16UI, PC_MAX_W, GBA_H, 0, GL_RGBA_INTEGER, GL_UNSIGNED_SHORT, NULL);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
        }
        if (HdPackAtlas(&px, &aw, &ah, &sPackScale, &sPackPerRow))
        {
            sAtlasTex = MakeTex(aw, ah, GL_RGBA8, GL_RGBA, GL_NEAREST);
            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, aw, ah, GL_RGBA, GL_UNSIGNED_BYTE, px);
        }
        sGlyphScale = PcTextAtlasSize(&gw, &gh);
        sGlyphTex = MakeTex(gw, gh, GL_RG8, GL_RG, GL_NEAREST);
        glGenTextures(1, &sPalTex);
        glBindTexture(GL_TEXTURE_2D, sPalTex);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_R16UI, 512, 1, 0, GL_RED_INTEGER, GL_UNSIGNED_SHORT, NULL);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    }
    gPpuExportLayers = 1;
    sReady = 1;
    return 0;
}

void HdDebugEnv(void)
{
    if (getenv("EMERALD_NOLIGHT")) sLighting = 0;
    if (getenv("EMERALD_TILT")) sTilt = (float)atof(getenv("EMERALD_TILT"));
}
void HdSetScale(int scale)
{
    if (scale < 1) scale = 1;
    if (scale > 8) scale = 8;
    if (scale == sScale)
        return;
    sScale = scale;
    if (sReady)
        AllocScaled();
}

int HdGetScale(void) { return sScale; }
void HdSetGrade(int on) { sGrade = on; }
int HdGetGrade(void) { return sGrade; }
void HdSetLighting(int on) { extern int gPcHdMenus; sLighting = on; gPcHdMenus = on && !getenv("EMERALD_NOMENU"); }
int HdGetLighting(void) { return sLighting; }

static float LocalHour(void)
{
    time_t t = time(NULL);
    struct tm *lt = localtime(&t);
    const char *force = getenv("EMERALD_HOUR"); // testing: pretend it is this hour
    if (force)
        return (float)atof(force);
    return lt->tm_hour + lt->tm_min / 60.0f + lt->tm_sec / 3600.0f;
}

// Sun shadow for the local time: long and to the west in the morning, short
// at noon, long and to the east in the evening; none at night or in rain.
static void SunVector(float *sun, int weather)
{
    float h = LocalHour(), a = (h - 6.0f) / 13.0f, e, len, dx, dy, n;
    if (a <= 0.0f || a >= 1.0f)
        return;
    e = sinf(a * 3.14159f);
    len = 5.0f + 15.0f * (1.0f - e);
    dx = 2.0f * a - 1.0f;
    dy = 0.45f + 0.35f * e;
    n = sqrtf(dx * dx + dy * dy);
    sun[0] = dx / n * len;
    sun[1] = dy / n * len;
    sun[2] = 0.30f * fminf(a / 0.06f, 1.0f) * fminf((1.0f - a) / 0.06f, 1.0f);
    if (weather == PC_WEATHER_RAIN || weather == PC_WEATHER_DOWNPOUR)
        sun[2] *= 0.2f;
    else if (weather == PC_WEATHER_SANDSTORM)
        sun[2] *= 0.5f;
}

static void TimeOfDayTint(float *rgb);

// Menu screens: find the two most common colours of the top map layer in a
// strip along the left edge of the original screen: the background pattern.
static void SetMenuUniforms(void)
{
    extern int gPcMenuFrame, gPcHdMenus;
    int m = (gPcScreenW - GBA_W) / 2, x, y, l, i, best[2] = { -1, -1 }, cnt[2] = { 0, 0 };
    static uint32_t cols[64]; static int n[64]; int nc = 0;
    int on = gPcMenuFrame && sLighting && !getenv("EMERALD_NOMENU");
    glUniform1i(glGetUniformLocation(sProgComp, "uMenu"), on ? gPcMenuFrame : 0);
    if (getenv("EMERALD_MENUDEBUG")) fprintf(stderr, "menu=%d light=%d\n", gPcMenuFrame, sLighting);
    gPcHdMenus = sLighting && !getenv("EMERALD_NOMENU");
    {
        // Window panels: rect and the window's fill colour (so they fade with the screen).
        struct PcPanel pn[16];
        float pr[16][4], pt[16][4];
        int np2 = gPcHdMenus ? PcPanels(pn) : 0, k;
        for (k = 0; k < np2; k++)
        {
            int px = pn[k].x + 2 + m, py = pn[k].y + 2;   // windows sit in the centred 240 px screen
            uint32_t c = px >= 0 && px < gPcScreenW && py >= 0 && py < GBA_H ? gPpuLayers.layer[pn[k].bg][py][px] : 0;
            pr[k][0] = pn[k].x + m; pr[k][1] = pn[k].y; pr[k][2] = pn[k].w; pr[k][3] = pn[k].h;
            if (c >> 24) { pt[k][0] = (c & 255) / 255.0f; pt[k][1] = ((c >> 8) & 255) / 255.0f; pt[k][2] = ((c >> 16) & 255) / 255.0f; }
            else { pt[k][0] = pt[k][1] = pt[k][2] = 1.0f; }
            pt[k][3] = (float)(pn[k].dialogue + pn[k].bg * 2);
        }
        glUniform1i(glGetUniformLocation(sProgComp, "uPanels"), np2);
        if (np2)
        {
            glUniform4fv(glGetUniformLocation(sProgComp, "uPanel"), np2, &pr[0][0]);
            glUniform4fv(glGetUniformLocation(sProgComp, "uPanelT"), np2, &pt[0][0]);
        }
    }
    {
        // Party screen cards: slot rects and states from the game, HP eased so bars glide.
        struct PcPartyCard pc[6];
        static float shown[6];
        int nc2 = on && gPcMenuFrame == 1 ? PcPartyUi(pc) : 0, k;
        float card[6][4], bar[6][4], st[6];
        static unsigned lastF;
        unsigned fnow = (unsigned)PortFrameCount();
        float ease = 1.0f - powf(0.8f, (float)(fnow - lastF > 60 ? 60 : fnow - lastF));   // per game frame, so bars glide at any refresh rate
        lastF = fnow;
        for (k = 0; k < nc2; k++)
        {
            shown[k] += (pc[k].hp - shown[k]) * ease;
            if (fabsf(pc[k].hp - shown[k]) < 0.002f) shown[k] = pc[k].hp;
            card[k][0] = pc[k].x + m; card[k][1] = pc[k].y; card[k][2] = pc[k].w; card[k][3] = pc[k].h;
            bar[k][0] = pc[k].barX + m; bar[k][1] = pc[k].barY; bar[k][2] = pc[k].barW; bar[k][3] = shown[k];
            st[k] = (float)pc[k].state;
        }
        glUniform1i(glGetUniformLocation(sProgComp, "uCards"), nc2);
        if (nc2)
        {
            glUniform4fv(glGetUniformLocation(sProgComp, "uCard"), nc2, &card[0][0]);
            glUniform4fv(glGetUniformLocation(sProgComp, "uCardBar"), nc2, &bar[0][0]);
            glUniform1fv(glGetUniformLocation(sProgComp, "uCardState"), nc2, st);
        }
    }
    if (!on)
        return;
    // Sample the background pattern: the left edge, or where a screen's
    // pattern shows clear of panels.
    // PC boxes: the cream strip under the box.
    int sx0 = gPcMenuFrame == 1 ? m + 40 : gPcMenuFrame == 5 ? m + 130 : m;
    int sy0 = gPcMenuFrame == 1 ? 90 : gPcMenuFrame == 5 ? 157 : 4, sy1 = gPcMenuFrame == 1 ? 140 : gPcMenuFrame == 5 ? 160 : GBA_H - 4;
    for (y = sy0; y < sy1; y += 2)
        for (x = sx0; x < sx0 + 6; x++)
            for (l = 0; l < 4; l++)
            {
                uint32_t c = gPpuLayers.layer[l][y][x];
                if (!(c >> 24)) continue;
                for (i = 0; i < nc && cols[i] != c; i++) ;
                if (i == nc && nc < 64) { cols[nc] = c; n[nc++] = 0; }
                if (i < nc) n[i]++;
                break;
            }
    for (i = 0; i < nc; i++)
        if (n[i] > cnt[0]) { cnt[1] = cnt[0]; best[1] = best[0]; cnt[0] = n[i]; best[0] = i; }
        else if (n[i] > cnt[1]) { cnt[1] = n[i]; best[1] = i; }
    for (i = 0; i < 2; i++)
    {
        uint32_t c = best[i] >= 0 ? cols[best[i]] : 0;
        if (best[1] < 0) c = best[0] >= 0 ? cols[best[0]] : 0;
        glUniform3f(glGetUniformLocation(sProgComp, i ? "uMenuBg2" : "uMenuBg1"), (c & 255) / 255.0f, ((c >> 8) & 255) / 255.0f, ((c >> 16) & 255) / 255.0f);
    }
}

// Battle scene lighting inputs: battler rects and feet (found from the
// sprite layer's pixels), light direction and colour, and move effects
// measured as a light source.
static void SetBattleUniforms(void)
{
    char name[32];
    int on = gPcBattleFrame && sLighting && gPcScreenW >= GBA_W;
    int k, x, y, m = (gPcScreenW - GBA_W) / 2;
    float tint[3] = { 1, 1, 1 }, sun[4] = { 0, 0, 0, 0 };
    double sw = 0, sx = 0, sy = 0, cr = 0, cg = 0, cb = 0;

    glUniform1i(glGetUniformLocation(sProgComp, "uBattle"), on);
    glUniform1i(glGetUniformLocation(sProgComp, "uScene"), -1);
    {
        // Battle camera: eases toward the action during a move, follows it
        // from attacker to target, and shakes when a hit lands.
        static float cx = -1, cy = 0.4f, cz = 1.0f, fx;
        static int animFrames;
        float tx, ty, tz = 1.0f, tfx = 0;
        const struct PcBattleFx *b = &gPcBattleFx;
        float W = (float)gPcScreenW, mm = (gPcScreenW - GBA_W) / 2.0f;
        float t = (float)(PortFrameCount() % 36000) / 59.73f;
        tx = (120.0f + mm) / W; ty = 60.0f / GBA_H;
        if (cx < 0) { cx = tx; cy = ty; }
        if (on && b->anim && b->attacker < b->count && b->target < b->count)
        {
            float ax = b->mon[b->attacker].x + b->mon[b->attacker].w / 2.0f, ay = b->mon[b->attacker].y + b->mon[b->attacker].h / 2.0f;
            float bx = b->mon[b->target].x + b->mon[b->target].w / 2.0f, by = b->mon[b->target].y + b->mon[b->target].h / 2.0f;
            float k = animFrames < 20 ? 0.25f : 0.7f;
            tx = ((ax + (bx - ax) * k) * 0.5f + 60.0f + mm) / W;
            ty = ((ay + (by - ay) * k) * 0.5f + 30.0f) / GBA_H;
            tz = 1.10f;
            tfx = 1.0f;
            animFrames++;
        }
        else
            animFrames = 0;
        if (getenv("EMERALD_NOCAM"))
            tz = 1.0f, tx = (120.0f + mm) / W, ty = 60.0f / GBA_H;
        cx += (tx - cx) * 0.06f; cy += (ty - cy) * 0.06f; cz += (tz - cz) * 0.06f;
        fx += (tfx - fx) * (tfx > fx ? 0.12f : 0.05f);
        glUniform3f(glGetUniformLocation(sProgComp, "uCam"), cx + 0.004f * sinf(t * 0.21f), cy + 0.003f * sinf(t * 0.17f), cz + 0.012f + 0.006f * sinf(t * 0.29f));
        {
            float sh = on ? b->shake * (b->moveType == 1 || b->moveType == 4 || b->moveType == 5 ? 4.0f : 2.5f) : 0;
            glUniform2f(glGetUniformLocation(sProgComp, "uShake"), sh * sinf(t * 91.0f), sh * cosf(t * 73.0f) * 0.7f);
        }
        glUniform1f(glGetUniformLocation(sProgComp, "uBoxTop"), (float)gPpuBattleBoxTop);
        glUniform1i(glGetUniformLocation(sProgComp, "uMoveType"), b->moveType);
        glUniform1f(glGetUniformLocation(sProgComp, "uMoveFx"), on && b->moveType >= 0 ? fx * 0.8f : 0.0f);
    }
    if (getenv("EMERALD_DEBUG_BATTLE"))
    {
        static int n;
        if (n++ % 120 == 0)
            fprintf(stderr, "battle fx: frame=%d light=%d w=%d count=%d out=%d m0=%d,%d %dx%d v%d\n", gPcBattleFrame, sLighting, gPcScreenW,
                    gPcBattleFx.count, gPcBattleFx.outdoors, gPcBattleFx.mon[0].x, gPcBattleFx.mon[0].y, gPcBattleFx.mon[0].w, gPcBattleFx.mon[0].h, gPcBattleFx.mon[0].visible);
    }
    if (!on)
        return;
    if (gPcBattleFx.outdoors && sLighting)
    {
        TimeOfDayTint(tint);
        SunVector(sun, PC_WEATHER_NONE);
    }
    glUniform4f(glGetUniformLocation(sProgComp, "uBTint"), tint[0], tint[1], tint[2], gPcBattleFx.outdoors ? 1.0f : 0.0f);
    {
        // Sky for the hour: night, dawn, day, golden hour, sunset, dusk.
        static const float k[][7] = {
            { 0.0f, 0.02f, 0.03f, 0.10f, 0.08f, 0.10f, 0.22f }, { 4.8f, 0.02f, 0.03f, 0.10f, 0.08f, 0.10f, 0.22f },
            { 6.0f, 0.25f, 0.30f, 0.55f, 1.00f, 0.62f, 0.45f }, { 7.5f, 0.28f, 0.48f, 0.85f, 0.95f, 0.85f, 0.80f },
            { 9.0f, 0.25f, 0.50f, 0.92f, 0.70f, 0.85f, 1.00f }, { 16.0f, 0.25f, 0.50f, 0.92f, 0.70f, 0.85f, 1.00f },
            { 17.5f, 0.30f, 0.45f, 0.80f, 1.00f, 0.80f, 0.50f }, { 18.5f, 0.20f, 0.20f, 0.45f, 1.00f, 0.45f, 0.30f },
            { 19.3f, 0.06f, 0.06f, 0.20f, 0.35f, 0.25f, 0.45f }, { 20.5f, 0.02f, 0.03f, 0.10f, 0.08f, 0.10f, 0.22f },
            { 24.0f, 0.02f, 0.03f, 0.10f, 0.08f, 0.10f, 0.22f },
        };
        float h = LocalHour(), f, sky[6], nightB, a;
        int i, j;
        for (i = 0; i < 9 && h >= k[i + 1][0]; i++)
            ;
        f = (h - k[i][0]) / (k[i + 1][0] - k[i][0]);
        for (j = 0; j < 6; j++)
            sky[j] = k[i][j + 1] + (k[i + 1][j + 1] - k[i][j + 1]) * f;
        nightB = 1.0f - (0.2126f * tint[0] + 0.7152f * tint[1] + 0.0722f * tint[2] - 0.55f) / 0.45f;
        nightB = nightB < 0 ? 0 : nightB > 1 ? 1 : nightB;
        glUniform1i(glGetUniformLocation(sProgComp, "uScene"), gPcBattleFx.scene);
        glUniform3f(glGetUniformLocation(sProgComp, "uSkyTop"), sky[0], sky[1], sky[2]);
        glUniform3f(glGetUniformLocation(sProgComp, "uSkyHor"), sky[3], sky[4], sky[5]);
        glUniform1f(glGetUniformLocation(sProgComp, "uNightB"), gPcBattleFx.scene == PC_BSCENE_INDOOR || gPcBattleFx.scene == PC_BSCENE_CAVE ? 0.0f : nightB);
        glUniform3f(glGetUniformLocation(sProgComp, "uBLight"), tint[0], tint[1], tint[2]);
        // The sun crosses the sky from left to right; the moon by night.
        a = (h - 6.0f) / 13.0f;
        if (a > 0 && a < 1)
            glUniform3f(glGetUniformLocation(sProgComp, "uSunPos"), -20.0f + a * 280.0f, 46.0f - sinf(a * 3.14159f) * 38.0f, 1.0f);
        else
        {
            float mh = h < 6 ? h + 24 : h, ma = (mh - 19.0f) / 11.0f;
            glUniform3f(glGetUniformLocation(sProgComp, "uSunPos"), -10.0f + ma * 260.0f, 42.0f - sinf(ma * 3.14159f) * 30.0f, 0.0f);
        }
    }
    // Shadows fall across the platform, away from the light: to the side the
    // sun's shadows point (from the upper left indoors and at night).
    {
        float dx = sun[2] > 0 ? sun[0] / 14.0f : 0.45f, strength = sun[2] > 0 ? 0.25f + sun[2] : 0.3f;
        glUniform3f(glGetUniformLocation(sProgComp, "uBShadow"), dx, 0.28f, strength);
    }
    for (k = 0; k < 4; k++)
    {
        int vis = k < gPcBattleFx.count && gPcBattleFx.mon[k].visible;
        int rx = gPcBattleFx.mon[k].x, ry = gPcBattleFx.mon[k].y, rw = gPcBattleFx.mon[k].w, rh = gPcBattleFx.mon[k].h;
        int feetY = ry + rh - 1, minX = rx + rw, maxX = rx;
        if (vis)
        {
            // Lowest row with a few opaque pixels = the feet.
            for (y = ry + rh - 1; y >= ry; y--)
            {
                int cnt = 0;
                if (y < 0 || y >= GBA_H) continue;
                for (x = rx; x < rx + rw; x++)
                {
                    int px = x + m;
                    if (px < 0 || px >= gPcScreenW) continue;
                    if (gPpuObjBattler[y][px] == 1) { cnt++; if (x < minX) minX = x; if (x > maxX) maxX = x; }
                }
                if (cnt >= 3) { feetY = y; break; }
            }
        }
        snprintf(name, sizeof(name), "uMon[%d]", k);
        glUniform4f(glGetUniformLocation(sProgComp, name), rx, ry, vis ? rw : 0, rh);
        snprintf(name, sizeof(name), "uMonFeet[%d]", k);
        glUniform3f(glGetUniformLocation(sProgComp, name), maxX >= minX ? (minX + maxX) / 2.0f : rx + rw / 2.0f, feetY,
                    maxX >= minX ? (maxX - minX) / 2.0f + 6 : rw * 0.35f);
    }
    // Move effects: bright sprite pixels that are not a Pokémon or a health
    // box, plus the effects background layer (BG1).
    for (y = 0; y < GBA_H; y++)
        for (x = 0; x < GBA_W; x++)
        {
            int px = x + m, l;
            for (l = 0; l < 2; l++)
            {
                uint32_t c = gPpuLayers.layer[l ? 1 : 4][y][px];
                float r, g, b, mx, mn, w;
                if (!(c >> 24)) continue;
                if (!l)
                {
                    if (gPpuObjBattler[y][px] != 2) continue;      // Pokémon, not an effect
                    if ((y < 46 && x < 120) || (y >= 70 && y < 114 && x >= 118)) continue; // health boxes
                }
                r = (c & 255) / 255.0f; g = ((c >> 8) & 255) / 255.0f; b = ((c >> 16) & 255) / 255.0f;
                mx = r > g ? (r > b ? r : b) : (g > b ? g : b);
                mn = r < g ? (r < b ? r : b) : (g < b ? g : b);
                w = mx * mx * (mx - mn + 0.25f) * (l ? 0.15f : 1.0f);
                sw += w; sx += w * x; sy += w * y; cr += w * r; cg += w * g; cb += w * b;
            }
        }
    if (sw > 1e-3)
    {
        float str = (float)sqrt(sw / 120.0);
        float mxc;
        cr /= sw; cg /= sw; cb /= sw;
        mxc = (float)(cr > cg ? (cr > cb ? cr : cb) : (cg > cb ? cg : cb));
        if (str > 1) str = 1;
        glUniform4f(glGetUniformLocation(sProgComp, "uMoveLight"), (float)(sx / sw), (float)(sy / sw), str * 0.65f, 60.0f);
        glUniform3f(glGetUniformLocation(sProgComp, "uMoveColor"), (float)cr / mxc, (float)cg / mxc, (float)cb / mxc);
    }
    else
        glUniform4f(glGetUniformLocation(sProgComp, "uMoveLight"), 0, 0, 0, 70.0f);
}

// Outdoor lighting colour for the local time: neutral by day, warm at dawn
// and dusk, cool and dim at night, blended smoothly between.
static void TimeOfDayTint(float *rgb)
{
    // (defined after use by the battle lighting)
    // Night, pre-dawn blue, pink sunrise, warm morning, neutral day,
    // golden hour, orange sunset, blue hour, night.
    static const float k[][4] = {
        { 0.0f, 0.52f, 0.58f, 0.86f }, { 4.6f, 0.52f, 0.58f, 0.86f },
        { 5.5f, 0.70f, 0.66f, 0.88f }, { 6.3f, 1.05f, 0.82f, 0.80f },
        { 7.5f, 1.03f, 0.97f, 0.90f }, { 9.0f, 1.00f, 1.00f, 1.00f },
        { 16.0f, 1.00f, 1.00f, 1.00f }, { 17.3f, 1.08f, 0.94f, 0.76f },
        { 18.4f, 1.10f, 0.78f, 0.62f }, { 19.2f, 0.68f, 0.66f, 0.92f },
        { 20.5f, 0.52f, 0.58f, 0.86f }, { 24.0f, 0.52f, 0.58f, 0.86f },
    };
    float h = LocalHour(), f;
    int i;
    for (i = 0; i < 10 && h >= k[i + 1][0]; i++)
        ;
    f = (h - k[i][0]) / (k[i + 1][0] - k[i][0]);
    rgb[0] = k[i][1] + (k[i + 1][1] - k[i][1]) * f;
    rgb[1] = k[i][2] + (k[i + 1][2] - k[i][2]) * f;
    rgb[2] = k[i][3] + (k[i + 1][3] - k[i][3]) * f;
}

static void DrawQuad(void)
{
    glDrawArrays(GL_TRIANGLES, 0, 3);
}

// The 2D ray-traced light pass (native resolution, into sGiTex).
static void RenderGi(void)
{
    char name[32];
    int field = PcFieldWideActive() && sLighting, k, cells = PC_GRID_W * PC_GRID_H;
    int mt = gPcFieldFx.mapType, packed[PC_GRID_W * PC_GRID_H / 4];
    const unsigned char *g = &gPcFieldFx.grid[0][0];
    float str = 0, lava = gPcFieldFx.heat ? 1.0f : 0.0f;
    if (field)
    {
        if (mt == 4 /* cave */) str = 1.0f;
        else if (mt == 8 || mt == 9 /* indoors */) str = 0.35f + 0.4f * sNight;
        else
        {
            float t[3];
            TimeOfDayTint(t);
            str = (1.0f - (0.2126f * t[0] + 0.7152f * t[1] + 0.0722f * t[2])) * 1.8f;
            str = str < 0 ? 0 : str > 1 ? 1 : str;
            sNight = str;
        }
        if (gPcFieldFx.heat) str = str > 0.8f ? str : 0.8f;
    }
    if (getenv("EMERALD_NOGI") || !sGiEnabled) str = 0;
    if (getenv("EMERALD_GIDEBUG")) { static int n; if (n++ % 60 == 0) fprintf(stderr, "gi: field=%d mt=%d night=%.2f str=%.2f lights=%d player=%d,%d margin=%d\n", field, mt, sNight, str, gPcFieldFx.numLights, gPcFieldFx.playerX, gPcFieldFx.playerY, (gPcScreenW - GBA_W) / 2); }
    sGiStr = str;
    if (str <= 0.01f)
        return;
    for (k = 0; k < cells / 4; k++)
        packed[k] = g[k * 4] | (g[k * 4 + 1] << 8) | (g[k * 4 + 2] << 16) | ((unsigned)g[k * 4 + 3] << 24);
    glBindFramebuffer(GL_FRAMEBUFFER, sGiFbo);
    glViewport(0, 0, sW, GBA_H);
    glUseProgram(sProgGi);
    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, sFrameTex);
    glActiveTexture(GL_TEXTURE0 + 1);
    glBindTexture(GL_TEXTURE_2D, sLayerTex[1]);
    glActiveTexture(GL_TEXTURE0);
    glUniform1i(glGetUniformLocation(sProgGi, "uFrame"), 0);
    glUniform1i(glGetUniformLocation(sProgGi, "uTop"), 1);
    glUniform2f(glGetUniformLocation(sProgGi, "uDim"), sW, GBA_H);
    glUniform1f(glGetUniformLocation(sProgGi, "uMargin"), (gPcScreenW - GBA_W) / 2.0f);
    glUniform4f(glGetUniformLocation(sProgGi, "uGridPos"), gPcFieldFx.gridX, gPcFieldFx.gridY, gPcFieldFx.gridWX, gPcFieldFx.gridWY);
    glUniform1iv(glGetUniformLocation(sProgGi, "uGrid"), cells / 4, packed);
    glUniform1i(glGetUniformLocation(sProgGi, "uNumLights"), sNight > 0.1f ? gPcFieldFx.numLights : 0);
    for (k = 0; k < gPcFieldFx.numLights; k++)
    {
        snprintf(name, sizeof(name), "uLights[%d]", k);
        glUniform3f(glGetUniformLocation(sProgGi, name), gPcFieldFx.lights[k].x, gPcFieldFx.lights[k].y, 0);
    }
    glUniform3f(glGetUniformLocation(sProgGi, "uLantern"), gPcFieldFx.playerX, gPcFieldFx.playerY - 10.0f,
                mt == 4 && gPcFieldFx.playerX > -900 ? 1.0f : 0.0f);
    glUniform1f(glGetUniformLocation(sProgGi, "uStr"), str);
    glUniform1f(glGetUniformLocation(sProgGi, "uNightWin"), 0.0f);   // window detection was unreliable
    glUniform1f(glGetUniformLocation(sProgGi, "uLava"), lava);
    DrawQuad();
}

// Live weather: every few minutes (real time) the outdoor weather drifts to
// a new state; changes fade over several seconds. Visual only.
float gPcLiveRain;
static void UpdateLiveWeather(int on, float *lw, float *wetOut, int *wxOut)
{
    enum { CLEAR, CLOUDY, FOG, RAIN, STORM };
    static float cloud, rain, fog, rainbow, wet, storm, lastRain;
    static int strikeTimer = 200, flashT;
    long period = (long)(time(NULL) / 180);
    uint32_t h = (uint32_t)period * 2654435761u;
    int st, pick;
    float tc, tr, tf, ts;
    h ^= h >> 15; h *= 2246822519u; h ^= h >> 13;
    pick = h % 100;
    st = pick < 40 ? CLEAR : pick < 64 ? CLOUDY : pick < 74 ? FOG : pick < 92 ? RAIN : STORM;
    if (getenv("EMERALD_LIVEWX")) st = atoi(getenv("EMERALD_LIVEWX"));
    tc = st == CLOUDY ? 0.8f : st == RAIN ? 0.9f : st == STORM ? 1.0f : st == FOG ? 0.5f : 0.0f;
    tr = st == RAIN ? 0.7f : st == STORM ? 1.0f : 0.0f;
    tf = st == FOG ? 0.9f : st == RAIN ? 0.15f : 0.0f;
    ts = st == STORM ? 1.0f : 0.0f;
    if (!on) tc = tr = tf = ts = 0;
    {
        float k = getenv("EMERALD_LIVEWX") ? 1.0f : 0.004f;   // fade over ~4 s at 60 fps
        cloud += (tc - cloud) * k; rain += (tr - rain) * k; fog += (tf - fog) * k; storm += (ts - storm) * k;
    }
    // The ground soaks up quickly and dries slowly.
    if (rain > wet) wet += (rain - wet) * 0.01f; else wet += (rain - wet) * 0.0008f;
    // A rainbow after rain stops in daylight.
    if (lastRain > 0.3f && rain < lastRain && rain < 0.3f && sNight < 0.3f) rainbow = 1.0f;
    rainbow *= 0.9993f;
    if (getenv("EMERALD_RAINBOW")) rainbow = 1.0f;
    lastRain = rain;
    lw[0] = cloud; lw[1] = rain; lw[2] = fog; lw[3] = on ? rainbow * (1.0f - cloud) : 0;
    *wetOut = wet;
    gPcLiveRain = on ? rain : 0;
    if (on && rain > 0.15f && *wxOut == 0)
        *wxOut = storm > 0.5f ? 2 : 1;
    // Lightning in storms.
    if (on && storm > 0.6f)
    {
        if (--strikeTimer <= 0) { flashT = 14; strikeTimer = 240 + (int)(h % 600); }
    }
    if (flashT > 0)
    {
        float f = (flashT > 10 ? 1.0f : flashT / 10.0f) * ((flashT % 4) < 2 ? 1.0f : 0.5f);
        gPcFieldFx.flash = (int)(f * 16);
        flashT--;
    }
}

// Cinematic moments: eased amount, bars, push-in and style.
static float sCineAmt, sCineBarT, sCineBarB, sCineZoom = 1.0f, sCineFx = 0.5f, sCineFy = 0.5f;
static int sCineStyle, sCineWant, sCineHold, sBattleFrames;
static void UpdateCinematic(void)
{
    int field = PcFieldWideActive() && !gPcBattleFrame;
    int want = 0, style = 0, boxOpen = 0, x, y, m = (gPcScreenW - GBA_W) / 2;
    float zoom = 1.0f, target, barT, barB;
    static unsigned lastF;
    unsigned fnow = (unsigned)PortFrameCount();
    int steps = (int)(fnow - lastF);
    lastF = fnow;
    if (steps < 1) steps = 1;
    if (steps > 60) steps = 60;
#define EASE(v, t, k) ((v) += ((t) - (v)) * (1.0f - powf(1.0f - (k), (float)steps)))
    if (getenv("EMERALD_NOCINE") || !sLighting) { sCineAmt = sCineBarT = sCineBarB = 0; sCineZoom = 1; return; }
    // Is a message box open (BG0 across the bottom of the screen)?
    for (y = 118; y < 156 && !boxOpen; y += 6)
        for (x = 40; x < 200; x += 8)
            if (gPpuLayers.layer[0][y][x + m] >> 24) { boxOpen = 1; break; }
    if (field)
    {
        sBattleFrames = 0;
        if (gPcCine.want) sCineWant += steps; else sCineWant = 0;
        if (sCineWant > 10 || (gPcCine.want && gPcCine.style == CINE_SPOTTED)) sCineHold = 50;
        if (sCineHold > 0) { want = 1; sCineHold -= steps; }
        if (gPcCine.want) style = gPcCine.style;
        zoom = gPcCine.zoom;
        if (want && gPcCine.want)
        {
            EASE(sCineFx, (gPcCine.fx + m) / (float)gPcScreenW, 0.05f);
            EASE(sCineFy, gPcCine.fy / (float)GBA_H, 0.05f);
        }
    }
    else if (gPcBattleFrame && gPcBattleFx.boss)
    {
        // Boss battles: the style's grade throughout, stronger for the opening.
        sBattleFrames += steps;
        want = 1;
        style = gPcBattleFx.boss;
        zoom = 1.0f;
    }
    if (style) sCineStyle = style;
    target = want ? (gPcBattleFrame ? (sBattleFrames < 300 ? 1.0f : 0.6f) : 1.0f) : 0.0f;
    EASE(sCineAmt, target, 0.04f);
    barT = want && !gPcBattleFrame ? 1.0f : 0.0f;
    barB = barT && !boxOpen ? 1.0f : 0.0f;
    EASE(sCineBarT, barT, 0.07f);
    EASE(sCineBarB, barB, 0.12f);
    EASE(sCineZoom, want && field ? zoom : 1.0f, 0.03f);
#undef EASE
    if (getenv("EMERALD_CINEDEBUG")) { static int k; if (k++ % 20 == 0) fprintf(stderr, "rcine: field=%d want=%d gw=%d amt=%.2f barT=%.2f zoom=%.3f box=%d\n", field, want, gPcCine.want, sCineAmt, sCineBarT, sCineZoom, boxOpen); }
}

// Render the HD composite into sCompFbo.
static void RenderHd(const uint32_t *frame, int outW, int outH)
{
    int i, w, h;

    if (sW != gPcScreenW)
    {
        sW = gPcScreenW;
        AllocScaled();
    }
    {
        static int once;
        if (!once) { once = 1; HdDebugEnv(); }
    }
    w = sW * sScale;
    h = GBA_H * sScale;

    glPixelStorei(GL_UNPACK_ROW_LENGTH, PC_MAX_W);
    for (i = 0; i < 5; i++)
    {
        glBindTexture(GL_TEXTURE_2D, sLayerTex[i]);
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, sW, GBA_H, GL_RGBA, GL_UNSIGNED_BYTE, gPpuLayers.layer[i]);
    }
    glBindTexture(GL_TEXTURE_2D, sMetaTex);
    glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, sW, GBA_H, GL_RGBA_INTEGER, GL_UNSIGNED_BYTE, gPpuLayers.meta);
    if (sAtlasTex || gPcTextHd)
    {
        glPixelStorei(GL_UNPACK_ALIGNMENT, 2);
        for (i = 0; i < 5; i++)
        {
            glBindTexture(GL_TEXTURE_2D, sTrefTex[i]);
            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, sW, GBA_H, GL_RGBA_INTEGER, GL_UNSIGNED_SHORT, gPpuLayers.tref[i]);
        }
        glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
    }
    glPixelStorei(GL_UNPACK_ROW_LENGTH, 0);
    glBindTexture(GL_TEXTURE_2D, sLineTex);
    glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, 4, GBA_H, GL_RGBA_INTEGER, GL_UNSIGNED_BYTE, gPpuLayers.line);

    // Pass 1: upscale each layer. Layer textures are stored top row first;
    // vUv.y = 0 at the bottom of the target, so flip when sampling.
    glUseProgram(sProgXbr);
    glUniform1i(glGetUniformLocation(sProgXbr, "uTex"), 0);
    glUniform2f(glGetUniformLocation(sProgXbr, "uSize"), sW, GBA_H);
    glUniform1f(glGetUniformLocation(sProgXbr, "uScale"), (float)sScale);
    glViewport(0, 0, w, h);
    for (i = 0; i < 5; i++)
    {
        glBindFramebuffer(GL_FRAMEBUFFER, sUpFbo[i]);
        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, sLayerTex[i]);
        DrawQuad();
    }
    // The flattened original frame, upscaled the same way.
    glBindTexture(GL_TEXTURE_2D, sFrameTex);
    glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, sW, GBA_H, GL_BGRA, GL_UNSIGNED_BYTE, frame);
    glBindFramebuffer(GL_FRAMEBUFFER, sUpFbo[5]);
    DrawQuad();

    RenderGi();

    // Battle intro: keep the last overworld frame before it starts (the
    // composite still holds it).
    if (gPcIntroSerial != sIntroSerial)
    {
        sIntroSerial = gPcIntroSerial;
        if (sCompTex && sCompW > 0 && sShatterEnabled && !getenv("EMERALD_NOSHATTER"))
        {
            if (!sSnapTex || sSnapW != sCompW || sSnapH != sCompH)
            {
                if (!sSnapTex) glGenTextures(1, &sSnapTex);
                glBindTexture(GL_TEXTURE_2D, sSnapTex);
                glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, sCompW, sCompH, 0, GL_RGBA, GL_UNSIGNED_BYTE, NULL);
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
                glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
                sSnapW = sCompW; sSnapH = sCompH;
            }
            glBindFramebuffer(GL_FRAMEBUFFER, sCompFbo);
            glBindTexture(GL_TEXTURE_2D, sSnapTex);
            glCopyTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, 0, 0, sCompW, sCompH);
            glBindFramebuffer(GL_FRAMEBUFFER, 0);
            sIntroFrame = (int)PortFrameCount();
        }
    }

    // Pass 2: composite at output resolution.
    EnsureComposite(outW, outH);
    glViewport(0, 0, sCompW, sCompH);
    glBindFramebuffer(GL_FRAMEBUFFER, sCompFbo);
    glUseProgram(sProgComp);
    glUniform2f(glGetUniformLocation(sProgComp, "uDim"), sW, GBA_H);
    glUniform2f(glGetUniformLocation(sProgComp, "uContent"), gPpuContentX0, gPpuContentX1);
    glUniform1i(glGetUniformLocation(sProgComp, "uHasPack"), (sAtlasTex || gPcTextHd) ? 1 : 0);
    glUniform1f(glGetUniformLocation(sProgComp, "uGlyphScale"), (float)sGlyphScale);
    if (gPcTextHd)
    {
        const uint8_t *gp;
        int gx, gy, gw, gh, gstride;
        glBindTexture(GL_TEXTURE_2D, sGlyphTex);
        glPixelStorei(GL_UNPACK_ALIGNMENT, 2);
        while (PcTextNextPending(&gp, &gx, &gy, &gw, &gh, &gstride))
        {
            glPixelStorei(GL_UNPACK_ROW_LENGTH, gstride);
            glTexSubImage2D(GL_TEXTURE_2D, 0, gx, gy, gw, gh, GL_RG, GL_UNSIGNED_BYTE, gp);
        }
        glPixelStorei(GL_UNPACK_ROW_LENGTH, 0);
        glBindTexture(GL_TEXTURE_2D, sPalTex);
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, 512, 1, GL_RED_INTEGER, GL_UNSIGNED_SHORT, (const void *)(uintptr_t)PC_PLTT);
        glPixelStorei(GL_UNPACK_ALIGNMENT, 4);
    }
    {
        float tint[3] = { 1, 1, 1 };
        int on = sLighting && gPcOutdoors && PcFieldWideActive();
        int field = PcFieldWideActive();
        float night = 0, lum;
        char name[32];
        int k;
        if (on)
            TimeOfDayTint(tint);
        glUniform4f(glGetUniformLocation(sProgComp, "uTint"), tint[0], tint[1], tint[2], on ? 1.0f : 0.0f);
        lum = 0.2126f * tint[0] + 0.7152f * tint[1] + 0.0722f * tint[2];
        if (on)
            night = (1.0f - lum) * 1.8f;
        if (night > 1) night = 1;
        if (night < 0) night = 0;
        sNight = night;
        glUniform1i(glGetUniformLocation(sProgComp, "uFieldFx"), field && sLighting);
        glUniform1f(glGetUniformLocation(sProgComp, "uNight"), night);
        glUniform1f(glGetUniformLocation(sProgComp, "uMargin"), (gPcScreenW - GBA_W) / 2.0f);
        glUniform1i(glGetUniformLocation(sProgComp, "uNumLights"), field ? gPcFieldFx.numLights : 0);
        glUniform1i(glGetUniformLocation(sProgComp, "uNumShadows"), field ? gPcFieldFx.numShadows : 0);
        gPcHdEffects = field && sLighting;
        {
            int wx = gPcHdEffects ? gPcFieldFx.weather : 0;
            float lw[4], wet;
            UpdateLiveWeather(field && sLighting && gPcFieldFx.outdoors && gPcFieldFx.weather == PC_WEATHER_NONE
                              && !gPcFieldFx.ash && gPcFieldFx.mapType != 4, lw, &wet, &wx);
            if (gPcFieldFx.weather == PC_WEATHER_RAIN || gPcFieldFx.weather == PC_WEATHER_DOWNPOUR)
            {
                lw[1] = 1.0f;   // the game's own rain: full strength
                wet = 1.0f;
            }
            glUniform1i(glGetUniformLocation(sProgComp, "uWeather"), wx);
            glUniform4f(glGetUniformLocation(sProgComp, "uLiveWx"), lw[0], lw[1], lw[2], lw[3]);
            glUniform1f(glGetUniformLocation(sProgComp, "uWet"), field && sLighting ? wet : 0.0f);
        }
        glUniform1f(glGetUniformLocation(sProgComp, "uTime"), (float)(PortFrameCount() % 36000) / 59.73f);
        {
            int packed[PC_GRID_W * PC_GRID_H / 4], solid = 0, cells = PC_GRID_W * PC_GRID_H;
            const unsigned char *g = &gPcFieldFx.grid[0][0];
            float sun[4] = { 0, 0, 0, 0 };
            unsigned char lv[PC_GRID_W * PC_GRID_H];
            int pass, x, y;
            // Depth level inside solid scenery: tiles from its edge, 0-3.
            for (k = 0; k < cells; k++)
                lv[k] = (g[k] & 1) ? 3 : 0;
            for (pass = 0; pass < 3; pass++)
                for (y = 0; y < PC_GRID_H; y++)
                    for (x = 0; x < PC_GRID_W; x++)
                    {
                        int i = y * PC_GRID_W + x, m = 3;
                        if (!lv[i]) continue;
                        if (x > 0 && lv[i - 1] < m) m = lv[i - 1];
                        if (x < PC_GRID_W - 1 && lv[i + 1] < m) m = lv[i + 1];
                        if (y > 0 && lv[i - PC_GRID_W] < m) m = lv[i - PC_GRID_W];
                        if (y < PC_GRID_H - 1 && lv[i + PC_GRID_W] < m) m = lv[i + PC_GRID_W];
                        if (m + 1 < lv[i]) lv[i] = m + 1;
                    }
            for (k = 0; k < cells / 4; k++)
            {
                unsigned b0 = (g[k * 4] & 63) | (lv[k * 4] << 6), b1 = (g[k * 4 + 1] & 63) | (lv[k * 4 + 1] << 6);
                unsigned b2 = (g[k * 4 + 2] & 63) | (lv[k * 4 + 2] << 6), b3 = (g[k * 4 + 3] & 63) | (lv[k * 4 + 3] << 6);
                packed[k] = (int)(b0 | (b1 << 8) | (b2 << 16) | (b3 << 24));
            }
            for (k = 0; k < cells; k++)
                solid += g[k] & 1;
            if (!field)
                memset(packed, 0, sizeof(packed));
            glUniform4f(glGetUniformLocation(sProgComp, "uGridPos"), gPcFieldFx.gridX, gPcFieldFx.gridY,
                        gPcFieldFx.gridWX, gPcFieldFx.gridWY);
            glUniform1iv(glGetUniformLocation(sProgComp, "uGrid"), cells / 4, packed);
            glUniform1i(glGetUniformLocation(sProgComp, "uMapType"), gPcFieldFx.mapType);
            glUniform1f(glGetUniformLocation(sProgComp, "uForest"), (float)solid / cells);
            {
                // Tall grass palette for this screen: dark and light ends of the
                // greenish colours found in tall-grass cells (map layers only).
                static float dk[3] = { 0.12f, 0.38f, 0.2f }, lt[3] = { 0.45f, 0.78f, 0.42f };
                int hist[64] = { 0 }, n = 0, row, col, px, py, m = (gPcScreenW - GBA_W) / 2, lo = -1, hi = -1, acc;
                float sd[3] = { 0 }, sl[3] = { 0 }, cd = 0, cl = 0;
                static unsigned char lum[GBA_H][PC_MAX_W];
                for (row = 0; field && row < PC_GRID_H; row++)
                    for (col = 0; col < PC_GRID_W; col++)
                    {
                        if (!(gPcFieldFx.grid[row][col] & 4)) continue;
                        for (py = 1; py < 16; py += 2)
                            for (px = 1; px < 16; px += 2)
                            {
                                int x = gPcFieldFx.gridX + col * 16 + px + m, y = gPcFieldFx.gridY + row * 16 + py, L, l;
                                uint32_t c = 0;
                                float rr, gg, bb;
                                if (x < 0 || y < 0 || x >= gPcScreenW || y >= GBA_H) continue;
                                for (L = 3; L >= 1; L--)
                                    if (gPpuLayers.layer[L][y][x] >> 24) c = gPpuLayers.layer[L][y][x];
                                if (!c) continue;
                                rr = (c & 255) / 255.0f; gg = ((c >> 8) & 255) / 255.0f; bb = ((c >> 16) & 255) / 255.0f;
                                if (gg < rr * 0.9f && gg < bb) continue;
                                l = (int)((0.3f * rr + 0.59f * gg + 0.11f * bb) * 63.0f);
                                lum[y][x] = (unsigned char)l;
                                hist[l]++; n++;
                            }
                    }
                if (n > 50)
                {
                    for (acc = 0, k = 0; k < 64; k++) { acc += hist[k]; if (lo < 0 && acc >= n / 5) lo = k; if (hi < 0 && acc >= n * 9 / 10) hi = k; }
                    for (row = 0; row < PC_GRID_H; row++)
                        for (col = 0; col < PC_GRID_W; col++)
                        {
                            if (!(gPcFieldFx.grid[row][col] & 4)) continue;
                            for (py = 1; py < 16; py += 2)
                                for (px = 1; px < 16; px += 2)
                                {
                                    int x = gPcFieldFx.gridX + col * 16 + px + m, y = gPcFieldFx.gridY + row * 16 + py, L;
                                    uint32_t c = 0;
                                    if (x < 0 || y < 0 || x >= gPcScreenW || y >= GBA_H) continue;
                                    for (L = 3; L >= 1; L--)
                                        if (gPpuLayers.layer[L][y][x] >> 24) c = gPpuLayers.layer[L][y][x];
                                    if (!c) continue;
                                    if (abs(lum[y][x] - lo) <= 2) { sd[0] += (c & 255); sd[1] += ((c >> 8) & 255); sd[2] += ((c >> 16) & 255); cd++; }
                                    if (abs(lum[y][x] - hi) <= 2) { sl[0] += (c & 255); sl[1] += ((c >> 8) & 255); sl[2] += ((c >> 16) & 255); cl++; }
                                }
                        }
                    for (k = 0; k < 3; k++)
                    {
                        if (cd > 0) dk[k] += (sd[k] / cd / 255.0f - dk[k]) * 0.2f;   // eased, so it never flickers
                        if (cl > 0) lt[k] += (sl[k] / cl / 255.0f - lt[k]) * 0.2f;
                    }
                }
                glUniform3f(glGetUniformLocation(sProgComp, "uGrassDark"), dk[0] * 0.7f + lt[0] * 0.3f, dk[1] * 0.7f + lt[1] * 0.3f, dk[2] * 0.7f + lt[2] * 0.3f);
                glUniform3f(glGetUniformLocation(sProgComp, "uGrassLight"), lt[0], lt[1], lt[2]);
            }
            {
                int water = 0;
                for (k = 0; k < cells; k++)
                    water += (g[k] & 2) != 0;
                glUniform3f(glGetUniformLocation(sProgComp, "uLife"), (float)water / cells,
                            field && gPcFieldFx.ash ? 1.0f : 0.0f, field && gPcFieldFx.heat ? 1.0f : 0.0f);
            }
            {
                // Indoor sunlight: falls into the room from the windows on
                // the back wall, slanting with the hour; off at night.
                float h = LocalHour(), a = (h - 6.5f) / 12.0f, str = 0, nightIn = 0;
                float dx = 0, dy = 1;
                if (a > 0 && a < 1)
                {
                    str = sinf(a * 3.14159f);
                    str = str > 0.25f ? 1.0f : str / 0.25f;
                    dx = (a - 0.5f) * 1.6f;
                }
                else
                    nightIn = 1;
                if (h > 18.0f && h < 19.5f) nightIn = (h - 18.0f) / 1.5f;
                if (h > 5.0f && h < 6.5f) nightIn = 1.0f - (h - 5.0f) / 1.5f;
                {
                    float n = sqrtf(dx * dx + dy * dy);
                    glUniform4f(glGetUniformLocation(sProgComp, "uInSun"), dx / n, dy / n,
                                field && sLighting ? str * 0.9f : 0.0f, field && sLighting ? nightIn : 0.0f);
                }
            }
            {
                // A new season each day: spring, summer, autumn, winter, repeating.
                time_t now = time(NULL);
                struct tm *lt = localtime(&now);
                int day = lt->tm_year * 366 + lt->tm_yday, season = day % 4;
                if (getenv("EMERALD_SEASON")) season = atoi(getenv("EMERALD_SEASON"));
                glUniform1i(glGetUniformLocation(sProgComp, "uSeason"), field && sLighting ? season : -1);
            }
            UpdateCinematic();
            glUniform3f(glGetUniformLocation(sProgComp, "uCineZoom"), sCineFx, sCineFy, sCineZoom);
            glUniform1i(glGetUniformLocation(sProgComp, "uMood"), field && sLighting ? gPcFieldFx.mood : 0);
            {
                const struct PcFollower *fo = &gPcFollower;
                if (!sFollowTex)
                {
                    glGenTextures(1, &sFollowTex);
                    glBindTexture(GL_TEXTURE_2D, sFollowTex);
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
                    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
                }
                glActiveTexture(GL_TEXTURE0 + 17);
                glBindTexture(GL_TEXTURE_2D, sFollowTex);
                if (fo->iconVersion != sFollowVersion)
                {
                    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, 32, 64, 0, GL_RGBA, GL_UNSIGNED_BYTE, fo->rgba);
                    sFollowVersion = fo->iconVersion;
                }
                glActiveTexture(GL_TEXTURE0);
                glUniform1i(glGetUniformLocation(sProgComp, "uFollow"), 17);
                glUniform4f(glGetUniformLocation(sProgComp, "uFollowPos"), fo->x, fo->y, fo->flip, fo->frame);
                glUniform2f(glGetUniformLocation(sProgComp, "uFollowOn"), 0.0f, fo->feetY);   // drawn by the PPU now
            }
            glUniform1f(glGetUniformLocation(sProgComp, "uTilt"), field && sLighting ? sTilt : 0.0f);
            glUniform2f(glGetUniformLocation(sProgComp, "uPlayer"), (float)gPcFieldFx.playerX, (float)gPcFieldFx.playerY);
            {
                // Wake trail from the field update: game frames -> shader time.
                float wake[12][3], now = (float)PortFrameCount();
                float t = (float)(PortFrameCount() % 36000) / 59.73f;
                for (int i = 0; i < 12; i++)
                {
                    wake[i][0] = gPcFieldFx.wake[i][0];
                    wake[i][1] = gPcFieldFx.wake[i][1];
                    wake[i][2] = field && gPcFieldFx.wake[i][2] >= 0 ? t - (now - gPcFieldFx.wake[i][2]) / 59.73f : -1.0f;
                }
                glUniform3fv(glGetUniformLocation(sProgComp, "uWake"), 12, &wake[0][0]);
            }
            SetBattleUniforms();
            SetMenuUniforms();
            glUniform1f(glGetUniformLocation(sProgComp, "uFlash"), field ? (getenv("EMERALD_FLASH") ? 1.0f : gPcFieldFx.flash / 16.0f) : 0.0f);
            if (on)
                SunVector(sun, gPcFieldFx.weather);
            sun[3] = on ? 1.0f - night : 0.0f;
            glUniform4f(glGetUniformLocation(sProgComp, "uSun"), sun[0], sun[1], sun[2], sun[3]);
            {
                // Key light for surface relief: the sun by day (low sun = long
                // shadows = grazing light), the moon at night, a ceiling light indoors.
                float kx, ky, kz, ks, n;
                if (on && sun[2] > 0)
                {
                    kx = -sun[0] * 0.07f; ky = -sun[1] * 0.07f; kz = 1.0f;
                    ks = 0.6f * sun[2] / 0.30f;
                }
                else if (on)
                {
                    kx = -0.35f; ky = -0.55f; kz = 1.0f; ks = 0.35f;   // moonlight
                }
                else
                {
                    kx = -0.3f; ky = -0.6f; kz = 1.0f;
                    ks = gPcFieldFx.mapType == 4 /* underground */ ? 0.4f : 0.0f;   // none indoors: furniture is all tiles
                }
                n = sqrtf(kx * kx + ky * ky + kz * kz);
                if (getenv("EMERALD_NORELIEF"))
                    ks = 0;
                glUniform4f(glGetUniformLocation(sProgComp, "uKey"), kx / n, ky / n, kz / n, field && sLighting ? ks : 0.0f);
            }
        }
        for (k = 0; field && k < gPcFieldFx.numLights; k++)
        {
            snprintf(name, sizeof(name), "uLights[%d]", k);
            glUniform3f(glGetUniformLocation(sProgComp, name), gPcFieldFx.lights[k].x, gPcFieldFx.lights[k].y, gPcFieldFx.lights[k].radius);
        }
        for (k = 0; field && k < gPcFieldFx.numShadows; k++)
        {
            float fx = gPcFieldFx.shadows[k].x, fy = gPcFieldFx.shadows[k].y, best = 0, bx = 0, by = 0;
            int j;
            snprintf(name, sizeof(name), "uShadows[%d]", k);
            glUniform3f(glGetUniformLocation(sProgComp, name), fx, fy, gPcFieldFx.shadows[k].w);
            // At night, the strongest nearby light casts this character's shadow away from it.
            for (j = 0; night > 0 && j < gPcFieldFx.numLights; j++)
            {
                float dx = fx - gPcFieldFx.lights[j].x, dy = fy - gPcFieldFx.lights[j].y;
                float d = sqrtf(dx * dx + dy * dy), r = gPcFieldFx.lights[j].radius * 1.8f, f;
                if (d >= r || d < 1.0f)
                    continue;
                f = 1.0f - d / r;
                f *= f;
                if (f > best)
                {
                    float len = 0.5f + 1.5f * (1.0f - f); // closer light, shorter shadow
                    best = f;
                    bx = dx / d * len;
                    by = dy / d * len;
                }
            }
            snprintf(name, sizeof(name), "uShadowLight[%d]", k);
            glUniform3f(glGetUniformLocation(sProgComp, name), bx, by, best * night * 0.55f);
        }
    }
    glUniform1f(glGetUniformLocation(sProgComp, "uPackScale"), (float)sPackScale);
    glUniform1i(glGetUniformLocation(sProgComp, "uPerRow"), sPackPerRow > 0 ? sPackPerRow : 1);
    for (i = 0; i < 5; i++)
    {
        glActiveTexture(GL_TEXTURE0 + 7 + i);
        glBindTexture(GL_TEXTURE_2D, sTrefTex[i]);
    }
    glActiveTexture(GL_TEXTURE0 + 12);
    glBindTexture(GL_TEXTURE_2D, sAtlasTex);
    glActiveTexture(GL_TEXTURE0 + 13);
    glBindTexture(GL_TEXTURE_2D, sGlyphTex);
    glActiveTexture(GL_TEXTURE0 + 14);
    glBindTexture(GL_TEXTURE_2D, sPalTex);
    glActiveTexture(GL_TEXTURE0 + 15);
    glBindTexture(GL_TEXTURE_2D, sUpTex[5]);
    glActiveTexture(GL_TEXTURE0 + 16);
    glBindTexture(GL_TEXTURE_2D, sGiTex);
    glUniform1f(glGetUniformLocation(sProgComp, "uGiOn"), sGiStr > 0.01f ? (getenv("EMERALD_GIVIEW") ? 2.0f : 1.0f) : 0.0f);
    for (i = 0; i < 5; i++)
    {
        glActiveTexture(GL_TEXTURE0 + i);
        glBindTexture(GL_TEXTURE_2D, sUpTex[i]);
    }
    glActiveTexture(GL_TEXTURE0 + 5);
    glBindTexture(GL_TEXTURE_2D, sMetaTex);
    glActiveTexture(GL_TEXTURE0 + 6);
    glBindTexture(GL_TEXTURE_2D, sLineTex);
    glActiveTexture(GL_TEXTURE0);
    DrawQuad();
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
}

static void Letterbox(int winW, int winH, int *x, int *y, int *w, int *h)
{
    // Largest rectangle with the frame's aspect ratio that fits.
    int fw = gPcScreenW;
    if (winW * GBA_H > winH * fw)
    {
        *h = winH;
        *w = winH * fw / GBA_H;
    }
    else
    {
        *w = winW;
        *h = winW * GBA_H / fw;
    }
    *x = (winW - *w) / 2;
    *y = (winH - *h) / 2;
}

static GLuint sCapTex, sCapFbo;
static int sCapW, sCapH;

static void DrawPresent(int hdMode, int winW, int winH)
{
    int x, y, w, h;
    glViewport(0, 0, winW, winH);
    glClearColor(0, 0, 0, 1);
    glClear(GL_COLOR_BUFFER_BIT);
    Letterbox(winW, winH, &x, &y, &w, &h);
    glViewport(x, y, w, h);
    glUseProgram(sProgPresent);
    glUniform1i(glGetUniformLocation(sProgPresent, "uTex"), 0);
    glUniform1i(glGetUniformLocation(sProgPresent, "uOverlay"), 2);
    glUniform1i(glGetUniformLocation(sProgPresent, "uOverlayOn"), sOverlayOn);
    glActiveTexture(GL_TEXTURE0 + 2);
    glBindTexture(GL_TEXTURE_2D, sOverlayTex);
    glActiveTexture(GL_TEXTURE0);
    glActiveTexture(GL_TEXTURE0);
    if (hdMode)
    {
        glBindTexture(GL_TEXTURE_2D, sCompTex);
        glUniform1f(glGetUniformLocation(sProgPresent, "uGrade"), sGrade ? 1.0f : 0.0f);
        glUniform1f(glGetUniformLocation(sProgPresent, "uFlip"), 0.0f);
        glUniform1f(glGetUniformLocation(sProgPresent, "uUScale"), 1.0f);
        glUniform1f(glGetUniformLocation(sProgPresent, "uBloom"), sGrade ? 0.25f + sNight * 0.9f : 0.0f);
        glUniform1f(glGetUniformLocation(sProgPresent, "uSharpen"), sGrade ? 1.0f : 0.0f);
        glUniform4f(glGetUniformLocation(sProgPresent, "uCine"), sCineBarT, sCineBarB, sCineAmt, (float)(PortFrameCount() % 36000) / 59.73f);
        glUniform1i(glGetUniformLocation(sProgPresent, "uCineStyle"), sCineStyle);
        {
            extern int gPcIntroKind;
            float t = ((int)PortFrameCount() - sIntroFrame) / (gPcIntroKind < 5 ? 48.0f : 54.0f);
            glUniform1f(glGetUniformLocation(sProgPresent, "uShatter"), sSnapTex && t >= 0 && t < 1 ? t : -1.0f);
            glUniform1f(glGetUniformLocation(sProgPresent, "uAspect"), (float)w / (h > 0 ? h : 1));
            {
                extern int gPcIntroKind;
                glUniform1i(glGetUniformLocation(sProgPresent, "uIntroKind"), gPcIntroKind);
            }
            glUniform1i(glGetUniformLocation(sProgPresent, "uSnap"), 1);
            glActiveTexture(GL_TEXTURE0 + 1);
            glBindTexture(GL_TEXTURE_2D, sSnapTex);
            glActiveTexture(GL_TEXTURE0);
        }
        glUniform2f(glGetUniformLocation(sProgPresent, "uTexel"), 1.0f / (sCompW > 0 ? sCompW : 1), 1.0f / (sCompH > 0 ? sCompH : 1));
        {
            extern int gPcMenuFrame;
            if (gPcMenuFrame && sLighting && !getenv("EMERALD_NOMENU"))
                glUniform2f(glGetUniformLocation(sProgPresent, "uContentUv"), -1.0f, 2.0f);   // menus fill the sides themselves
            else
                glUniform2f(glGetUniformLocation(sProgPresent, "uContentUv"),
                            (float)gPpuContentX0 / gPcScreenW, (float)gPpuContentX1 / gPcScreenW);
        }
        {
            float m = (float)(gPcScreenW - GBA_W) / 2 / gPcScreenW;
            int battle = gPcBattleFrame && gPcScreenW > GBA_W && !(gPcBattleFx.scene >= 0 && sLighting);
            glUniform3f(glGetUniformLocation(sProgPresent, "uSoftSides"), m, 1.0f - m,
                        battle ? (float)gPpuBattleBoxTop / GBA_H : 0.0f);
        }
    }
    else
    {
        glBindTexture(GL_TEXTURE_2D, sFrameTex);
        glUniform1f(glGetUniformLocation(sProgPresent, "uGrade"), 0.0f);
        glUniform1f(glGetUniformLocation(sProgPresent, "uFlip"), 1.0f);
        glUniform1f(glGetUniformLocation(sProgPresent, "uUScale"), (float)gPcScreenW / PC_MAX_W);
        glUniform1f(glGetUniformLocation(sProgPresent, "uBloom"), 0.0f);
        glUniform1f(glGetUniformLocation(sProgPresent, "uSharpen"), 0.0f);
        glUniform1f(glGetUniformLocation(sProgPresent, "uShatter"), -1.0f);
        glUniform4f(glGetUniformLocation(sProgPresent, "uCine"), 0, 0, 0, 0);
        glUniform2f(glGetUniformLocation(sProgPresent, "uContentUv"), -1.0f, 2.0f);
        glUniform3f(glGetUniformLocation(sProgPresent, "uSoftSides"), 0.0f, 1.0f, 0.0f);
    }
    DrawQuad();
}

static int sLastHdMode;

// Show the last rendered image again (for displays faster than 60 Hz).
void HdPresentAgain(int winW, int winH)
{
    if (!sReady)
        return;
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    DrawPresent(sLastHdMode, winW, winH);
}

void HdPresent(const uint32_t *frame, int hdMode, int winW, int winH)
{
    int x, y, w, h;

    if (!sReady)
        return;

    sLastWinW = winW;
    sLastWinH = winH;
    sLastHdMode = hdMode;
    Letterbox(winW, winH, &x, &y, &w, &h);
    if (hdMode)
        RenderHd(frame, w, h);
    else
    {
        glBindTexture(GL_TEXTURE_2D, sFrameTex);
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, gPcScreenW, GBA_H, GL_BGRA, GL_UNSIGNED_BYTE, frame);
    }
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    DrawPresent(hdMode, winW, winH);
}

// Read back exactly what was drawn to the window (top row first). Call after
// HdPresent and before swapping buffers.
int HdReadFrame(uint32_t *out, int *w, int *h, int maxPixels)
{
    int y, W = sLastWinW, H = sLastWinH;
    uint32_t *tmp;
    if (!sReady || W <= 0 || H <= 0 || W * H > maxPixels)
        return -1;
    tmp = SDL_malloc((size_t)W * H * 4);
    if (!tmp)
        return -1;
    // Redraw the final pass into an offscreen buffer: reading the window's
    // own framebuffer is unreliable on some drivers.
    if (!sCapTex || sCapW != W || sCapH != H)
    {
        if (sCapTex)
            glDeleteTextures(1, &sCapTex);
        sCapTex = MakeTex(W, H, GL_RGBA8, GL_RGBA, GL_NEAREST);
        sCapFbo = MakeFbo(sCapTex);
        sCapW = W;
        sCapH = H;
    }
    glBindFramebuffer(GL_FRAMEBUFFER, sCapFbo);
    DrawPresent(sLastHdMode, W, H);
    glReadPixels(0, 0, W, H, GL_RGBA, GL_UNSIGNED_BYTE, tmp);
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    for (y = 0; y < H; y++)
        memcpy(out + (size_t)y * W, tmp + (size_t)(H - 1 - y) * W, (size_t)W * 4);
    SDL_free(tmp);
    *w = W;
    *h = H;
    return 0;
}

// Read back the HD composite (top row first) for screenshots/tests.
int HdReadComposite(uint32_t *out, int *w, int *h)
{
    int y, W = sCompW, H = sCompH;
    uint32_t *tmp;
    if (!sReady)
        return -1;
    tmp = SDL_malloc((size_t)W * H * 4);
    if (!tmp)
        return -1;
    glBindFramebuffer(GL_FRAMEBUFFER, sCompFbo);
    glReadPixels(0, 0, W, H, GL_RGBA, GL_UNSIGNED_BYTE, tmp);
    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    for (y = 0; y < H; y++)
        memcpy(out + (size_t)y * W, tmp + (size_t)(H - 1 - y) * W, (size_t)W * 4);
    SDL_free(tmp);
    *w = W;
    *h = H;
    return 0;
}
