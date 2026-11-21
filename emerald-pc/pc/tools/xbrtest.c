// Runs the HD renderer's layer upscaler on a PPM image (for shader tuning).
//   xbrtest in.ppm out.ppm scale
#define SDL_MAIN_HANDLED
#include "../render_gl.c"
#include <stdlib.h>

struct PpuLayers gPpuLayers;
int gPpuExportLayers;

int main(int argc, char **argv)
{
    FILE *f = fopen(argv[1], "rb");
    int w, h, maxv, scale = atoi(argv[3]), x, y;
    unsigned char *rgb;
    uint32_t *img, *out;
    SDL_Window *win;
    GLuint tex, outTex, fbo;

    if (!f || fscanf(f, "P6 %d %d %d", &w, &h, &maxv) != 3) return 1;
    fgetc(f);
    rgb = malloc(w * h * 3);
    if (fread(rgb, 1, w * h * 3, f) != (size_t)(w * h * 3)) return 1;
    img = malloc(w * h * 4);
    for (x = 0; x < w * h; x++)
        img[x] = 0xFF000000u | (rgb[x * 3 + 2] << 16) | (rgb[x * 3 + 1] << 8) | rgb[x * 3];

    SDL_Init(SDL_INIT_VIDEO);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
    win = SDL_CreateWindow("t", 0, 0, 64, 64, SDL_WINDOW_OPENGL | SDL_WINDOW_HIDDEN);
    SDL_GL_CreateContext(win);
    if (LoadGl()) return 1;
    sProgXbr = Program(kXbr);
    if (!sProgXbr) return 1;
    glGenVertexArrays(1, &sVao);
    glBindVertexArray(sVao);
    tex = MakeTex(w, h, GL_RGBA8, GL_RGBA, GL_NEAREST);
    glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, img);
    outTex = MakeTex(w * scale, h * scale, GL_RGBA8, GL_RGBA, GL_NEAREST);
    fbo = MakeFbo(outTex);
    glBindFramebuffer(GL_FRAMEBUFFER, fbo);
    glViewport(0, 0, w * scale, h * scale);
    glUseProgram(sProgXbr);
    glUniform1i(glGetUniformLocation(sProgXbr, "uTex"), 0);
    glUniform2f(glGetUniformLocation(sProgXbr, "uSize"), w, h);
    glUniform1f(glGetUniformLocation(sProgXbr, "uScale"), scale);
    glActiveTexture(GL_TEXTURE0);
    glBindTexture(GL_TEXTURE_2D, tex);
    glDrawArrays(GL_TRIANGLES, 0, 3);
    out = malloc((size_t)w * h * scale * scale * 4);
    glReadPixels(0, 0, w * scale, h * scale, GL_RGBA, GL_UNSIGNED_BYTE, out);
    f = fopen(argv[2], "wb");
    fprintf(f, "P6\n%d %d\n255\n", w * scale, h * scale);
    // FBO row 0 holds image row 0 (top), as in the game renderer.
    for (y = 0; y < h * scale; y++)
        for (x = 0; x < w * scale; x++)
        {
            uint32_t p = out[(size_t)y * w * scale + x];
            unsigned char px[3] = { p & 0xFF, (p >> 8) & 0xFF, (p >> 16) & 0xFF };
            fwrite(px, 1, 3, f);
        }
    fclose(f);
    return 0;
}
