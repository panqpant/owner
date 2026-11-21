// CPU reference of Hyllian's xBR 4x (as in FFmpeg's vf_xbr), used to verify
// the GLSL port. Usage: xbr_ref in.ppm out.ppm
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

static uint32_t *sR2Y;

static void InitYuv(void)
{
    int bg, rg, g;
    sR2Y = calloc(1 << 24, 4);
    for (bg = -255; bg < 256; bg++)
        for (rg = -255; rg < 256; rg++)
        {
            const uint32_t u = (uint32_t)((-169 * rg + 500 * bg) / 1000) + 128;
            const uint32_t v = (uint32_t)((500 * rg - 81 * bg) / 1000) + 128;
            int startg = -bg > -rg ? -bg : -rg;
            int endg = 255 - bg < 255 - rg ? 255 - bg : 255 - rg;
            uint32_t y, c;
            if (startg < 0) startg = 0;
            if (endg > 255) endg = 255;
            y = (uint32_t)((299 * rg + 1000 * startg + 114 * bg) / 1000);
            c = bg + rg * (1 << 16) + 0x010101 * startg;
            for (g = startg; g <= endg; g++)
            {
                sR2Y[c] = y << 16 | u << 8 | v;
                c += 0x010101;
                y++;
            }
        }
}

static uint32_t Diff(uint32_t x, uint32_t y)
{
    uint32_t a = sR2Y[x & 0xFFFFFF], b = sR2Y[y & 0xFFFFFF];
    return (abs((int)(a & 0xFF0000) - (int)(b & 0xFF0000)) >> 16)
         + (abs((int)(a & 0x00FF00) - (int)(b & 0x00FF00)) >> 8)
         + abs((int)(a & 0x0000FF) - (int)(b & 0x0000FF));
}

#define LB_MASK 0x00FEFEFE
#define RB_MASK 0x00FF00FF
#define G_MASK 0x0000FF00
#define B128(a, b) ((((a) & LB_MASK) >> 1) + (((b) & LB_MASK) >> 1))
#define BBASE(a, b, m, s) ((RB_MASK & (((a) & RB_MASK) + (((((b) & RB_MASK) - ((a) & RB_MASK)) * (m)) >> (s)))) \
                         | (G_MASK & (((a) & G_MASK) + (((((b) & G_MASK) - ((a) & G_MASK)) * (m)) >> (s)))))
#define B64(a, b) BBASE(a, b, 1, 2)
#define B192(a, b) BBASE(a, b, 3, 2)

#define df(A, B) Diff(A, B)
#define eq(A, B) (df(A, B) < 155)

// Role offsets for rotation 0 (corner = bottom-right), (dx, dy) with y down.
enum { rE, rI, rH, rF, rG, rC, rD, rB, rA, rG5, rC4, rG0, rD0, rC1, rB1, rF4, rI4, rH5, rI5, rA0, rA1, NROLE };
static const int kRole[NROLE][2] = {
    { 0, 0 }, { 1, 1 }, { 0, 1 }, { 1, 0 }, { -1, 1 }, { 1, -1 }, { -1, 0 }, { 0, -1 }, { -1, -1 },
    { -1, 2 }, { 2, -1 }, { -2, 1 }, { -2, 0 }, { 1, -2 }, { 0, -2 }, { 2, 0 }, { 2, 1 }, { 0, 2 }, { 1, 2 },
    { -2, -1 }, { -1, -2 },
};

static void Rot(int k, int x, int y, int *ox, int *oy)
{
    while (k--) { int t = x; x = y; y = -t; }
    *ox = x; *oy = y;
}

int main(int argc, char **argv)
{
    FILE *f = fopen(argv[1], "rb");
    int w, h, maxv, x, y, k, i;
    unsigned char *rgb;
    uint32_t *src, *dst;

    if (!f || fscanf(f, "P6 %d %d %d", &w, &h, &maxv) != 3) return 1;
    fgetc(f);
    rgb = malloc(w * h * 3);
    if (fread(rgb, 1, w * h * 3, f) != (size_t)(w * h * 3)) return 1;
    src = malloc(w * h * 4);
    for (i = 0; i < w * h; i++)
        src[i] = (rgb[i * 3] << 16) | (rgb[i * 3 + 1] << 8) | rgb[i * 3 + 2];
    dst = malloc((size_t)w * h * 16 * 4);
    InitYuv();

    for (y = 0; y < h; y++)
        for (x = 0; x < w; x++)
        {
            uint32_t E[16];
            for (i = 0; i < 16; i++)
                E[i] = src[y * w + x];
            for (k = 0; k < 4; k++)
            {
                uint32_t P[NROLE];
                int sx, sy, n;
                int N[16];
                // Fetch neighbours (edge pixels clamp).
                for (n = 0; n < NROLE; n++)
                {
                    int dx, dy, px, py;
                    Rot(k, kRole[n][0], kRole[n][1], &dx, &dy);
                    px = x + dx; py = y + dy;
                    if (px < 0) px = 0; if (px >= w) px = w - 1;
                    if (py < 0) py = 0; if (py >= h) py = h - 1;
                    P[n] = src[py * w + px];
                }
                // Subpixel indices: corner + a*u + b*v, with u along the H edge, v along the F edge.
                {
                    int cx, cy, ux, uy, vx, vy, a, b;
                    // rotation 0: corner (3,3), u = (-1,0), v = (0,-1); rotate about block centre.
                    double ccx, ccy;
                    { int tx, ty; Rot(k, 3, 3, &tx, &ty); (void)tx; (void)ty; }
                    // centre-relative corner (1.5, 1.5) rotated
                    ccx = 1.5; ccy = 1.5;
                    for (i = 0; i < k; i++) { double t = ccx; ccx = ccy; ccy = -t; }
                    cx = (int)(ccx + 1.5); cy = (int)(ccy + 1.5);
                    Rot(k, -1, 0, &ux, &uy);
                    Rot(k, 0, -1, &vx, &vy);
                    for (a = 0; a < 4; a++)
                        for (b = 0; b < 4; b++)
                            N[a * 4 + b] = -1;
                    for (a = 0; a < 4; a++)
                        for (b = 0; b < 4; b++)
                        {
                            sx = cx + a * ux + b * vx;
                            sy = cy + a * uy + b * vy;
                            if (sx >= 0 && sx < 4 && sy >= 0 && sy < 4)
                                N[a * 4 + b] = sy * 4 + sx;
                        }
                }
                // Named subpixels (see FILT4): N15 corner, N14/N13/N12 along u, N11/N7/N3 along v, N10 diagonal.
                {
                    int N15 = N[0], N14 = N[4], N13 = N[8], N12 = N[12], N11 = N[1], N7 = N[2], N3 = N[3], N10 = N[5];
                    uint32_t PE = P[rE], PI = P[rI], PH = P[rH], PF = P[rF], PG = P[rG], PC = P[rC], PD = P[rD], PB = P[rB];
                    uint32_t H5 = P[rH5], F4 = P[rF4], I5 = P[rI5], I4 = P[rI4];
                    if (PE != PH && PE != PF)
                    {
                        const unsigned e = df(PE, PC) + df(PE, PG) + df(PI, H5) + df(PI, F4) + (df(PH, PF) << 2);
                        const unsigned ii = df(PH, PD) + df(PH, I5) + df(PF, I4) + df(PF, PB) + (df(PE, PI) << 2);
                        if (e <= ii)
                        {
                            const uint32_t px = df(PE, PF) <= df(PE, PH) ? PF : PH;
                            if (e < ii && ((!eq(PF, PB) && !eq(PH, PD)) || (eq(PE, PI) && (!eq(PF, I4) || !eq(PH, I5)))
                                           || eq(PE, PG) || eq(PE, PC)))
                            {
                                const unsigned ke = df(PF, PG), ki = df(PH, PC);
                                const int left = (ke << 1) <= ki && PE != PG && PD != PG;
                                const int up = ke >= (ki << 1) && PE != PC && PB != PC;
                                if (left && up)
                                {
                                    E[N13] = B192(E[N13], px);
                                    E[N12] = B64(E[N12], px);
                                    E[N15] = E[N14] = E[N11] = px;
                                    E[N10] = E[N3] = E[N12];
                                    E[N7] = E[N13];
                                }
                                else if (left)
                                {
                                    E[N11] = B192(E[N11], px);
                                    E[N13] = B192(E[N13], px);
                                    E[N10] = B64(E[N10], px);
                                    E[N12] = B64(E[N12], px);
                                    E[N14] = px;
                                    E[N15] = px;
                                }
                                else if (up)
                                {
                                    E[N14] = B192(E[N14], px);
                                    E[N7] = B192(E[N7], px);
                                    E[N10] = B64(E[N10], px);
                                    E[N3] = B64(E[N3], px);
                                    E[N11] = px;
                                    E[N15] = px;
                                }
                                else
                                {
                                    E[N11] = B128(E[N11], px);
                                    E[N14] = B128(E[N14], px);
                                    E[N15] = px;
                                }
                            }
                            else
                            {
                                E[N15] = B128(E[N15], px);
                            }
                        }
                    }
                }
            }
            for (i = 0; i < 16; i++)
                dst[(size_t)(y * 4 + i / 4) * w * 4 + x * 4 + i % 4] = E[i];
        }

    f = fopen(argv[2], "wb");
    fprintf(f, "P6\n%d %d\n255\n", w * 4, h * 4);
    for (i = 0; i < w * h * 16; i++)
    {
        unsigned char px[3] = { dst[i] >> 16, (dst[i] >> 8) & 0xFF, dst[i] & 0xFF };
        fwrite(px, 1, 3, f);
    }
    fclose(f);
    return 0;
}
