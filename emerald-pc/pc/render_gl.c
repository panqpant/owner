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
    "uniform float uTime;\n"
    "uniform vec4 uGridPos;\n"      // grid cell (0,0): screen x, y; map x, y
    "uniform int uGrid[144];\n"     // 36x16 metatile flags, 4 per int (PC_CELL_*)
    "uniform vec4 uSun;\n"          // xy: shadow vector (GBA px), z: shadow strength, w: daylight
    "uniform int uMapType;\n"
    "uniform float uForest;\n"
    "uniform vec4 uKey;\n"
    "uniform float uFlash;\n"       // lightning, 0-1          // key light: direction towards the light (x, y down, z up), strength      // fraction of scenery around: light shafts
    "vec2 gUpSize, gUpFw;\n"
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
    "  if (float(np.x) < uContent.x || float(np.x) >= uContent.y) { oColor = vec4(0.0, 0.0, 0.0, 1.0); return; }\n"
    "  vec2 uv = vec2(vUv.x, 1.0 - vUv.y);\n"
    "  gUpSize = vec2(textureSize(uLayer[0], 0));\n"
    "  gUpFw = fwidth(uv * gUpSize);\n"
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
    "  lay[0] = TexS(uLayer[0], uv); lay[1] = TexS(uLayer[1], uv);\n"
    "  lay[2] = TexS(uLayer[2], uv); lay[3] = TexS(uLayer[3], uv);\n"
    "  lay[4] = TexS(uLayer[4], uv);\n"
    "  vec2 gp = vec2(vUv.x * uDim.x - uMargin, (1.0 - vUv.y) * uDim.y);\n"
    "  vec2 wp = gp - uGridPos.xy + uGridPos.zw * 16.0;\n"   // world position (map pixels)
    "  int here = uFieldFx != 0 ? Cell(ivec2(floor(CellPos(gp)))) : 0;\n"
    // Wind: grass and tree leaves sway, anchored at the top and bottom of each tile.
    "  if (uFieldFx != 0 && uMapType != 4 && uMapType != 8 && (here & 5) != 0) {\n"
    "    float fy = fract(CellPos(gp).y);\n"
    "    float gust = 0.6 + 0.4 * sin(uTime * 0.37 + wp.x * 0.004);\n"
    "    float amp = ((here & 4) != 0 ? 0.55 : 0.3) * gust * sin(3.14159 * fy);\n"
    "    vec2 o = vec2(sin(uTime * 2.1 + wp.x * 0.045 + wp.y * 0.11) * amp / uDim.x, 0.0);\n"
    "    vec4 s2;\n"
    "    if (Green(lay[1])) { s2 = TexS(uLayer[1], uv + o); if (Green(s2)) lay[1] = s2; }\n"
    "    if (Green(lay[2])) { s2 = TexS(uLayer[2], uv + o); if (Green(s2)) lay[2] = s2; }\n"
    "    if (Green(lay[3])) { s2 = TexS(uLayer[3], uv + o); if (Green(s2)) lay[3] = s2; }\n"
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
    "  if (top != 5 && top != 0 && ((M.b >> uint(top)) & 1u) != 0u && lay[top].a < 0.999)\n"
    "    under = TexS(uFlat, uv).rgb;\n"
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
    // Per-pixel surface lighting: a normal for every pixel from the art's
    // shading (fine relief), sprite outlines (rounded characters) and depth
    // inside solid scenery (domed trees, roofs, cliffs); lit by the key light.
    "  vec3 N = vec3(0.0, 0.0, 1.0);\n"
    "  if (uFieldFx != 0 && top >= 1 && top <= 4 && uKey.w > 0.0) {\n"
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
    // Scenery lighting on the ground: ambient occlusion around solid
    // scenery, sun shadows that follow the time of day, drifting cloud shadows.
    "  float recv = (uFieldFx != 0 && top >= 1 && top <= 3) ? 1.0 - Solid(gp) : 0.0;\n"   // how much this is open ground
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
    "    if ((Cell(c0 - ivec2(0, up + 1)) & 1) != 0) {\n"   // something solid on the shore
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
    "    vec4 ch = MirrorChars(gp);\n"
    "    res = mix(res, ch.rgb / max(ch.a, 1e-3) * vec3(0.75, 0.85, 0.95), ch.a * 0.45);\n"
    "    vec3 sky = mix(vec3(0.55, 0.75, 1.0), vec3(1.0, 0.7, 0.45), clamp((uTint.r - uTint.b) * 3.0, 0.0, 1.0)) * (uTint.a > 0.5 ? uTint.rgb : vec3(1.0));\n"
    "    res = mix(res, sky * max(dot(res, vec3(0.33)), 0.35) * 1.4, 0.12);\n"
    "  }\n"
    // Rain: wet ground darkens and puddles reflect buildings, trees,
    // characters and lights (streaks below lamps and doorways).
    "  if (uFieldFx != 0 && (uWeather == 1 || uWeather == 2) && recv > 0.5 && (here & 2) == 0 && top >= 1 && top <= 3) {\n"
    "    float pud = Puddles(wp) * (uWeather == 2 ? 1.0 : 0.75);\n"
    "    res *= 0.88 - 0.08 * pud;\n"
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
    "  if (uFieldFx != 0 && top >= 1 && top <= 3 && (here & 2) != 0) {\n"
    "    float w = sin(wp.x * 0.42 + uTime * 1.6 + sin(wp.y * 0.31 + uTime * 0.9) * 1.7) * 0.5\n"
    "            + sin(wp.y * 0.57 - uTime * 1.2 + wp.x * 0.13) * 0.5;\n"
    "    float sp = smoothstep(0.82, 0.98, w) * (0.6 + 0.4 * Noise(wp * 0.7 + uTime));\n"
    "    vec3 glint = mix(vec3(0.75, 0.85, 1.0), vec3(1.0, 0.95, 0.8), uSun.w);\n"
    "    res = res * (1.0 + w * 0.04) + glint * sp * (0.12 + 0.16 * uSun.w);\n"
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
    "    float cs = 11.0; vec2 c = floor(wp / cs); float h = Hash(c + 3.7);\n"
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
    // Full-resolution weather over the whole widescreen frame (not over UI).
    "  if (uFieldFx != 0 && uWeather != 0 && top != 0) {\n"
    "    if (uWeather <= 2) {\n"
    "      float heavy = uWeather == 2 ? 1.0 : 0.0;\n"
    "      float r = Rain(gp, uTime, 5.0, 2.6, 0.30 + heavy * 0.25) * 0.55\n"
    "              + Rain(gp + 37.0, uTime, 8.0, 2.0, 0.22 + heavy * 0.2) * 0.75;\n"
    "      res = mix(res, vec3(0.80, 0.86, 0.95), clamp(r, 0.0, 1.0) * 0.55);\n"
    "    } else {\n"
    "      vec2 q = gp * vec2(0.035, 0.09) + vec2(uTime * 1.4, uTime * 0.15);\n"
    "      float n = Noise(q) * 0.6 + Noise(q * 2.3 + 5.0) * 0.4;\n"
    "      float grain = step(0.985, Hash(floor(gp * 2.0) + floor(uTime * 30.0)));\n"
    "      res = mix(res, vec3(0.86, 0.72, 0.50), clamp(n * 0.45 + grain * 0.4, 0.0, 0.7));\n"
    "    }\n"
    "  }\n"
    // Thin, mostly transparent fringes of layers in front of the top layer.
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
    "uniform vec3 uSoftSides;\n"  // battles: x = left edge u, y = right edge u, z = message box top (v, from top)
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
    "  oColor = vec4(c, 1.0);\n"
    "}\n";

// ---------------------------------------------------------------------------

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
    if (!sProgXbr || !sProgComp || !sProgPresent)
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
void HdSetLighting(int on) { sLighting = on; }
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

// Outdoor lighting colour for the local time: neutral by day, warm at dawn
// and dusk, cool and dim at night, blended smoothly between.
static void TimeOfDayTint(float *rgb)
{
    static const float k[][4] = {
        { 0.0f, 0.52f, 0.58f, 0.86f }, { 4.5f, 0.52f, 0.58f, 0.86f },
        { 6.0f, 1.02f, 0.88f, 0.80f }, { 7.5f, 1.00f, 1.00f, 1.00f },
        { 16.5f, 1.00f, 1.00f, 1.00f }, { 18.0f, 1.06f, 0.86f, 0.70f },
        { 19.5f, 0.72f, 0.68f, 0.88f }, { 21.0f, 0.52f, 0.58f, 0.86f },
        { 24.0f, 0.52f, 0.58f, 0.86f },
    };
    float h = LocalHour(), f;
    int i;
    for (i = 0; i < 8 && h >= k[i + 1][0]; i++)
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

// Render the HD composite into sCompFbo.
static void RenderHd(const uint32_t *frame, int outW, int outH)
{
    int i, w, h;

    if (sW != gPcScreenW)
    {
        sW = gPcScreenW;
        AllocScaled();
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
        glUniform1i(glGetUniformLocation(sProgComp, "uWeather"), gPcHdEffects ? gPcFieldFx.weather : 0);
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
                    ks = gPcFieldFx.mapType == 4 /* underground */ ? 0.4f : 0.55f;
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
    glActiveTexture(GL_TEXTURE0);
    if (hdMode)
    {
        glBindTexture(GL_TEXTURE_2D, sCompTex);
        glUniform1f(glGetUniformLocation(sProgPresent, "uGrade"), sGrade ? 1.0f : 0.0f);
        glUniform1f(glGetUniformLocation(sProgPresent, "uFlip"), 0.0f);
        glUniform1f(glGetUniformLocation(sProgPresent, "uUScale"), 1.0f);
        glUniform1f(glGetUniformLocation(sProgPresent, "uBloom"), sGrade ? 0.25f + sNight * 0.9f : 0.0f);
        glUniform1f(glGetUniformLocation(sProgPresent, "uSharpen"), sGrade ? 1.0f : 0.0f);
        glUniform2f(glGetUniformLocation(sProgPresent, "uTexel"), 1.0f / (sCompW > 0 ? sCompW : 1), 1.0f / (sCompH > 0 ? sCompH : 1));
        glUniform2f(glGetUniformLocation(sProgPresent, "uContentUv"),
                    (float)gPpuContentX0 / gPcScreenW, (float)gPpuContentX1 / gPcScreenW);
        {
            float m = (float)(gPcScreenW - GBA_W) / 2 / gPcScreenW;
            int battle = gPcBattleFrame && gPcScreenW > GBA_W;
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
