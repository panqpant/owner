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
#include <SDL.h>
#include "port.h"
#include "render_gl.h"

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
    "uniform usampler2D uMeta;\n"
    "uniform usampler2D uLine;\n"
    "uniform vec2 uDim;\n"        // native frame size (W, 160)
    "uniform vec2 uContent;\n"    // visible content columns [x0, x1); outside is pillarbox
    "vec3 blend(vec3 a, vec3 b, float ea, float eb) { return min(a * ea + b * eb, vec3(1.0)); }\n"
    "void main() {\n"
    "  ivec2 np = ivec2(min(floor(vUv * uDim), uDim - 1.0));\n"
    "  np.y = 159 - np.y;\n"
    "  if (float(np.x) < uContent.x || float(np.x) >= uContent.y) { oColor = vec4(0.0, 0.0, 0.0, 1.0); return; }\n"
    "  vec2 uv = vec2(vUv.x, 1.0 - vUv.y);\n"
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
    "  lay[0] = texture(uLayer[0], uv); lay[1] = texture(uLayer[1], uv);\n"
    "  lay[2] = texture(uLayer[2], uv); lay[3] = texture(uLayer[3], uv);\n"
    "  lay[4] = texture(uLayer[4], uv);\n"
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
    // Thin, mostly transparent fringes of layers in front of the top layer.
    "  for (int k = ti - 1; k >= 0; k--) { vec4 c = lay[order[k]]; res = res * (1.0 - c.a) + c.rgb; }\n"
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
    "void main() {\n"
    "  vec2 uv = vec2(vUv.x * uUScale, uFlip > 0.5 ? 1.0 - vUv.y : vUv.y);\n"
    "  vec3 c = texture(uTex, uv).rgb;\n"
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
static GLuint sLayerTex[5], sUpTex[5], sUpFbo[5];
static GLuint sMetaTex, sLineTex, sFrameTex;
static GLuint sCompTex, sCompFbo;
static int sScale = 4;
static int sW = GBA_W;
static int sCompW, sCompH; // composite size = on-screen size of the game image
static int sGrade = 1;

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
    for (i = 0; i < 5; i++)
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
        glUniform1i(glGetUniformLocation(sProgComp, "uLine"), 6);
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

static void DrawQuad(void)
{
    glDrawArrays(GL_TRIANGLES, 0, 3);
}

// Render the HD composite into sCompFbo.
static void RenderHd(int outW, int outH)
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

    // Pass 2: composite at output resolution.
    EnsureComposite(outW, outH);
    glViewport(0, 0, sCompW, sCompH);
    glBindFramebuffer(GL_FRAMEBUFFER, sCompFbo);
    glUseProgram(sProgComp);
    glUniform2f(glGetUniformLocation(sProgComp, "uDim"), sW, GBA_H);
    glUniform2f(glGetUniformLocation(sProgComp, "uContent"), gPpuContentX0, gPpuContentX1);
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

void HdPresent(const uint32_t *frame, int hdMode, int winW, int winH)
{
    int x, y, w, h;

    if (!sReady)
        return;

    Letterbox(winW, winH, &x, &y, &w, &h);
    if (hdMode)
        RenderHd(w, h);
    else
    {
        glBindTexture(GL_TEXTURE_2D, sFrameTex);
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, gPcScreenW, GBA_H, GL_BGRA, GL_UNSIGNED_BYTE, frame);
    }

    glBindFramebuffer(GL_FRAMEBUFFER, 0);
    glViewport(0, 0, winW, winH);
    glClearColor(0, 0, 0, 1);
    glClear(GL_COLOR_BUFFER_BIT);
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
    }
    else
    {
        glBindTexture(GL_TEXTURE_2D, sFrameTex);
        glUniform1f(glGetUniformLocation(sProgPresent, "uGrade"), 0.0f);
        glUniform1f(glGetUniformLocation(sProgPresent, "uFlip"), 1.0f);
        glUniform1f(glGetUniformLocation(sProgPresent, "uUScale"), (float)gPcScreenW / PC_MAX_W);
    }
    DrawQuad();
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
