"""Tiling facade textures for the building styles, drawn by code: windows, frames, sills, mullions and
spandrels on a transparent background, so each texture overlays any wall colour / Roblox material.
Writes assets/roblox/textures/<name>.png and src/shared/FacadeTextures.luau (tile size in studs per
texture; fill in the asset ids after uploading the PNGs to Roblox).
Usage (from costa-verde/): python3 tools/make_facades.py"""
import os
import random

from PIL import Image, ImageDraw

OUT = "assets/roblox/textures"
PX = 512  # texture size; each tile covers U x V studs (floor height 12-14 studs, bays 8-12 studs)

GLASS = (58, 92, 112, 255)
GLASS_HI = (120, 160, 180, 255)
FRAME = (230, 230, 226, 255)
DARK = (36, 44, 52, 255)
SILL = (238, 236, 228, 255)


def glass(d, box, rng, tint=GLASS):
    """A window pane with a soft sky reflection and the odd blind / light."""
    x0, y0, x1, y1 = box
    d.rectangle(box, fill=tint)
    h = y1 - y0
    d.polygon([(x0, y0 + h * 0.65), (x1, y0 + h * 0.25), (x1, y0), (x0, y0)], fill=tuple(min(255, int(c * 1.25)) for c in tint[:3]) + (255,))
    if rng.random() < 0.25:  # blinds half down
        d.rectangle((x0, y0, x1, y0 + h * rng.uniform(0.2, 0.6)), fill=(212, 206, 190, 255))


def curtain_wall(rng):  # towers: 4 floors x 4 bays of glass, thin mullions, opaque spandrels
    im = Image.new("RGBA", (PX, PX), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fh, bw = PX // 4, PX // 4
    for f in range(4):
        for b in range(4):
            x0, y0 = b * bw, f * fh
            glass(d, (x0 + 3, y0 + 3, x0 + bw - 3, y0 + fh * 0.78), rng)
            d.rectangle((x0, y0 + fh * 0.78, x0 + bw, y0 + fh), fill=(70, 96, 110, 255))  # spandrel
            d.rectangle((x0, y0, x0 + 3, y0 + fh), fill=(190, 196, 200, 255))
    return im, 40, 56


def ribbon(rng):  # midrise offices: continuous window bands per floor
    im = Image.new("RGBA", (PX, PX), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fh = PX // 4
    for f in range(4):
        y0 = f * fh + fh * 0.22
        y1 = f * fh + fh * 0.72
        for b in range(6):
            x0 = b * PX / 6
            glass(d, (x0 + 2, y0, x0 + PX / 6 - 2, y1), rng)
        d.rectangle((0, y1, PX, y1 + 6), fill=SILL)
    return im, 48, 52


def deco(rng):  # Art Deco: vertical window strips between pilasters, eyebrow ledges over each window
    im = Image.new("RGBA", (PX, PX), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fh, bw = PX // 3, PX // 4
    for f in range(3):
        for b in range(4):
            x0, y0 = b * bw + bw * 0.22, f * fh + fh * 0.3
            x1, y1 = b * bw + bw * 0.78, f * fh + fh * 0.85
            glass(d, (x0, y0, x1, y1), rng, (70, 110, 120, 255))
            d.line((x0 + (x1 - x0) / 2, y0, x0 + (x1 - x0) / 2, y1), fill=FRAME, width=4)
            d.rectangle((x0 - 10, y0 - 16, x1 + 10, y0 - 6), fill=(250, 250, 246, 200))  # eyebrow shade
        d.rectangle((0, f * fh + 2, PX, f * fh + 8), fill=(255, 255, 255, 140))  # banding
    return im, 36, 39


def punched(rng):  # stucco: punched windows with frames, sills and shutters
    im = Image.new("RGBA", (PX, PX), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fh, bw = PX // 2, PX // 3
    for f in range(2):
        for b in range(3):
            x0, y0 = b * bw + bw * 0.3, f * fh + fh * 0.28
            x1, y1 = b * bw + bw * 0.7, f * fh + fh * 0.8
            d.rectangle((x0 - 6, y0 - 6, x1 + 6, y1 + 6), fill=FRAME)
            glass(d, (x0, y0, x1, y1), rng, (60, 80, 90, 255))
            d.line((x0, (y0 + y1) / 2, x1, (y0 + y1) / 2), fill=FRAME, width=4)
            d.rectangle((x0 - 12, y1 + 6, x1 + 12, y1 + 14), fill=SILL)
            if rng.random() < 0.5:  # shutters
                col = rng.choice([(40, 110, 100, 255), (60, 80, 130, 255), (150, 90, 60, 255)])
                d.rectangle((x0 - 30, y0 - 6, x0 - 8, y1 + 6), fill=col)
                d.rectangle((x1 + 8, y0 - 6, x1 + 30, y1 + 6), fill=col)
    return im, 30, 26


def house(rng):  # one storey, two windows and a door with white frames
    im = Image.new("RGBA", (PX, PX), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for x0 in (60, 300):
        x1 = x0 + 150
        d.rectangle((x0 - 8, 150, x1 + 8, 370), fill=FRAME)
        glass(d, (x0, 158, x1, 362), rng, (54, 70, 80, 255))
        d.line(((x0 + x1) / 2, 158, (x0 + x1) / 2, 362), fill=FRAME, width=6)
        d.line((x0, 260, x1, 260), fill=FRAME, width=6)
    d.rectangle((0, PX - 20, PX, PX), fill=(200, 196, 186, 120))  # foundation line
    return im, 24, 12


def warehouse(rng):  # clerestory strip high up, loading door low
    im = Image.new("RGBA", (PX, PX), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for b in range(8):
        glass(d, (b * 64 + 6, 40, b * 64 + 58, 90), rng, (80, 100, 110, 255))
    d.rectangle((140, 260, 372, PX), fill=(150, 150, 146, 255))  # roll-up door
    for y in range(270, PX, 18):
        d.line((140, y, 372, y), fill=(120, 120, 116, 255), width=3)
    return im, 40, 28


def shopfront(rng):  # ground-floor display windows and an awning band
    im = Image.new("RGBA", (PX, PX), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    awn = rng.choice([(180, 50, 50, 255), (30, 110, 120, 255), (40, 70, 140, 255), (200, 150, 40, 255)])
    d.rectangle((0, 120, PX, 180), fill=awn)
    for x in range(0, PX, 24):
        d.line((x, 120, x, 180), fill=(255, 255, 255, 90), width=8)
    glass(d, (20, 200, 230, 470), rng, (50, 70, 80, 255))
    d.rectangle((260, 200, 330, 490), fill=(40, 40, 40, 255))  # door
    glass(d, (350, 200, 492, 470), rng, (50, 70, 80, 255))
    d.rectangle((0, 470, PX, 500), fill=SILL)
    return im, 24, 16


TEXTURES = {"glass_curtain": curtain_wall, "ribbon": ribbon, "deco": deco, "punched": punched,
            "house": house, "warehouse": warehouse, "shopfront": shopfront}


def main():
    os.makedirs(OUT, exist_ok=True)
    lines = ["-- Generated by tools/make_facades.py: facade textures (transparent except windows) and the stud size",
             "-- one tile covers. Upload assets/roblox/textures/*.png (Studio: Asset Manager > Bulk Import), then paste",
             "-- each image's id as id = \"rbxassetid://...\"; buildings without an id just show their wall material.",
             "return {"]
    for name, fn in TEXTURES.items():
        im, u, v = fn(random.Random(name))
        im.save(f"{OUT}/{name}.png")
        lines.append(f'\t{name} = {{ u = {u}, v = {v}, id = "" }},')
        print(f"{name}: tile {u}x{v} studs -> {OUT}/{name}.png")
    lines.append("}")
    open("src/shared/FacadeTextures.luau", "w").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
