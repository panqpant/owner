"""Batch 8: every 2D texture the game needs, drawn in code so they all share one style.

Run:  python textures/build_textures.py      (needs Pillow; the Fredoka One font is in fonts/)

Writes export/textures/decals/*.png and export/textures/particles/*.png, plus previews/_textures.png.
Upload them in Studio (Asset Manager, bulk import) and use them as Decals, SurfaceGui images or
ParticleEmitter textures. Particles are white on transparent so a ParticleEmitter's Color tints them.
"""

import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ART = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ART, "export", "textures")
FONT = os.path.join(ART, "fonts", "FredokaOne-Regular.ttf")

NAVY, ORANGE, YELLOW, WHITE, RED = (35, 48, 107), (255, 154, 46), (255, 210, 63), (255, 255, 255), (232, 68, 58)
INK = (27, 28, 33)


def font(size):
    return ImageFont.truetype(FONT, size)


def fit_text(draw, text, box_w, box_h, start=200):
    """Largest Fredoka size that fits the box."""
    size = start
    while size > 8:
        l, t, r, b = draw.textbbox((0, 0), text, font=font(size), stroke_width=max(1, size // 12))
        if r - l <= box_w and b - t <= box_h:
            return font(size), (r - l, b - t, l, t)
        size -= 2
    return font(8), (0, 0, 0, 0)


def text_centre(draw, text, cx, cy, box_w, box_h, fill=WHITE, stroke=INK):
    f, (w, h, l, t) = fit_text(draw, text, box_w, box_h)
    sw = max(1, f.size // 12)
    draw.text((cx - w / 2 - l, cy - h / 2 - t), text, font=f, fill=fill, stroke_width=sw, stroke_fill=stroke)


def parcel_icon(draw, cx, cy, s, body=(198, 156, 109), tape=(233, 216, 166)):
    """The courier parcel: a box in 3/4 view with tape, used in logos and ads."""
    top = [(cx, cy - s * 0.55), (cx + s * 0.6, cy - s * 0.25), (cx, cy + 0.05 * s), (cx - s * 0.6, cy - s * 0.25)]
    left = [(cx - s * 0.6, cy - s * 0.25), (cx, cy + 0.05 * s), (cx, cy + s * 0.65), (cx - s * 0.6, cy + s * 0.35)]
    right = [(cx + s * 0.6, cy - s * 0.25), (cx, cy + 0.05 * s), (cx, cy + s * 0.65), (cx + s * 0.6, cy + s * 0.35)]
    shade = tuple(int(c * 0.8) for c in body)
    for poly, col in ((left, shade), (right, body), (top, tuple(min(255, int(c * 1.12)) for c in body))):
        draw.polygon(poly, fill=col, outline=INK, width=max(2, int(s / 20)))
    draw.line([(cx - s * 0.3, cy - s * 0.4), (cx + s * 0.3, cy - s * 0.1)], fill=tape, width=max(3, int(s / 8)))
    draw.line([(cx + s * 0.3, cy - s * 0.1), (cx + s * 0.3, cy + s * 0.5)], fill=tape, width=max(3, int(s / 8)))


def save(img, group, name):
    os.makedirs(os.path.join(OUT, group), exist_ok=True)
    img.save(os.path.join(OUT, group, name + ".png"))
    return name


# ------------------------------------------------------------------ signs


def depot_logo():
    img = Image.new("RGB", (1024, 160), NAVY)
    d = ImageDraw.Draw(img)
    parcel_icon(d, 90, 80, 110)
    text_centre(d, "RAGDOLL COURIERS", 590, 80, 820, 110, fill=YELLOW)
    return save(img, "decals", "sign_depot")


def leaderboard_header():
    img = Image.new("RGB", (1024, 128), (18, 22, 40))
    d = ImageDraw.Draw(img)
    for k in range(3):  # gold stars either side
        for side in (-1, 1):
            star(d, 512 + side * (380 + k * 40), 64, 16 - k * 3, YELLOW)
    text_centre(d, "TOP COURIERS", 512, 64, 640, 100, fill=YELLOW)
    return save(img, "decals", "sign_leaderboard")


def star(draw, cx, cy, r, fill):
    pts = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        rr = r if k % 2 == 0 else r * 0.45
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    draw.polygon(pts, fill=fill, outline=INK, width=max(1, int(r / 6)))


SHOPS = [
    ("Parcel & Pastry", (246, 194, 107), (120, 70, 40)),
    ("Bubble Wrap Books", (143, 193, 227), NAVY),
    ("The Fragile Vase", (58, 123, 240), WHITE),
    ("Lucky Laptops", (67, 184, 92), WHITE),
    ("Cake Expectations", (255, 143, 199), (120, 30, 80)),
    ("Piano Forte", INK, WHITE),
    ("Teddy's Toys", (233, 139, 125), WHITE),
    ("Fishy Business", (31, 181, 168), WHITE),
]


def shop_signs():
    names = []
    for k, (name, bg, fg) in enumerate(SHOPS):
        img = Image.new("RGB", (512, 96), bg)
        d = ImageDraw.Draw(img)
        d.rectangle((4, 4, 507, 91), outline=fg, width=4)
        text_centre(d, name, 256, 48, 470, 70, fill=fg, stroke=bg)
        names.append(save(img, "decals", f"sign_shop_{k + 1}"))
    return names


def district_signs():
    names = []
    for name, bg in (("HUB", (67, 184, 92)), ("SUBURBS", (67, 184, 92)), ("OLD TOWN", (67, 184, 92)), ("DOCKS", (58, 123, 240)), ("DOWNTOWN", (58, 123, 240)), ("MOUNTAIN ROAD", (139, 90, 60))):
        img = Image.new("RGB", (512, 112), bg)
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((6, 6, 505, 105), radius=14, outline=WHITE, width=5)
        text_centre(d, name, 256, 56, 460, 76, fill=WHITE, stroke=bg)
        names.append(save(img, "decals", "sign_district_" + name.lower().replace(" ", "_")))
    return names


def building_signs():
    """Signs for the hub garages and the summit lodge (their boards are about 7.5:1 and 8:1)."""
    names = []
    for name, text, bg, fg, size in (("sign_garage", "GARAGE", (58, 123, 240), WHITE, (1024, 136)), ("sign_vip", "VIP GARAGE", INK, YELLOW, (1024, 136)), ("sign_lodge", "SUMMIT LODGE", NAVY, WHITE, (1024, 124))):
        img = Image.new("RGB", size, bg)
        d = ImageDraw.Draw(img)
        d.rectangle((5, 5, size[0] - 6, size[1] - 6), outline=fg, width=5)
        text_centre(d, text, size[0] // 2, size[1] // 2, size[0] - 80, size[1] - 30, fill=fg, stroke=bg)
        names.append(save(img, "decals", name))
    return names


# ------------------------------------------------------------------ billboards (2:1, the billboard panel is 24 x 12)


def billboard(name, bg_top, bg_bottom, headline, sub, art):
    img = Image.new("RGB", (1024, 512))
    d = ImageDraw.Draw(img)
    for y in range(512):  # vertical gradient
        t = y / 511
        d.line([(0, y), (1023, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(bg_top, bg_bottom)))
    art(d)  # artwork lives in the left 400px; text keeps to the right of it
    text_centre(d, headline, 712, 200, 560, 170, fill=WHITE)
    text_centre(d, sub, 712, 380, 560, 70, fill=YELLOW)
    d.rectangle((0, 0, 1023, 511), outline=INK, width=10)
    return save(img, "decals", name)


def billboards():
    def courier(d):
        parcel_icon(d, 200, 230, 190)
        for k in range(4):  # motion lines: it's flying
            d.line([(30, 120 + k * 50), (90, 120 + k * 50)], fill=WHITE, width=8)

    def bubble(d):
        for k in range(26):
            r = random.Random(k).randint(14, 40)
            x, y = random.Random(k + 50).randint(40, 360), random.Random(k + 90).randint(40, 470)
            d.ellipse((x - r, y - r, x + r, y + r), outline=WHITE, width=5)

    def rocket(d):
        d.polygon([(120, 380), (300, 140), (330, 170), (160, 410)], fill=(220, 220, 230), outline=INK, width=6)
        d.polygon([(300, 140), (350, 90), (330, 170)], fill=RED, outline=INK, width=6)
        for k, c in enumerate((YELLOW, ORANGE, RED)):
            d.polygon([(130 - k * 20, 395 + k * 20), (90 - k * 30, 470), (175 - k * 10, 430)], fill=c)

    def shield(d):
        d.polygon([(200, 80), (330, 130), (310, 330), (200, 430), (90, 330), (70, 130)], fill=WHITE, outline=INK, width=8)
        parcel_icon(d, 200, 250, 130)

    def cocoa(d):
        d.polygon([(60, 420), (200, 140), (340, 420)], fill=(240, 240, 248), outline=INK, width=6)
        d.rounded_rectangle((150, 300, 290, 440), radius=16, fill=RED, outline=INK, width=6)
        for k in range(3):
            d.arc((170 + k * 30, 220, 210 + k * 30, 300), 200, 340, fill=WHITE, width=6)

    def fish(d):
        d.ellipse((70, 180, 320, 330), fill=(255, 154, 46), outline=INK, width=6)
        d.polygon([(310, 255), (380, 190), (380, 320)], fill=(255, 154, 46), outline=INK, width=6)
        d.ellipse((115, 225, 145, 255), fill=INK)

    random.seed(5)
    return [
        billboard("billboard_couriers", (58, 123, 240), (35, 48, 107), "DELIVER ANYTHING", "in one piece (probably)", courier),
        billboard("billboard_bubblewrap", (31, 181, 168), (20, 110, 120), "BUBBLE-WRAP PRO", "padding for the clumsy", bubble),
        billboard("billboard_rocket", (255, 143, 46), (200, 60, 50), "ROCKET SCOOTER", "now 90% more rocket", rocket),
        billboard("billboard_insurance", (67, 184, 92), (30, 110, 60), "PARCEL INSURANCE", "because ramps", shield),
        billboard("billboard_lodge", (139, 92, 246), (60, 40, 140), "SUMMIT LODGE", "hot cocoa at the top", cocoa),
        billboard("billboard_fish", (31, 120, 200), (20, 60, 120), "FISHY BUSINESS", "fresh catch at the docks", fish),
    ]


# ------------------------------------------------------------------ posters, road markings, graffiti


def posters():
    names = []
    specs = [
        ("poster_lost_chicken", (255, 241, 214), "LOST", "CHICKEN", "last seen flying out of a scooter"),
        ("poster_courier_month", (214, 236, 255), "COURIER", "OF THE MONTH", "0 crashes (we checked)"),
        ("poster_cake_contest", (255, 214, 230), "CAKE", "CONTEST", "Saturday · Old Town square"),
        ("poster_beware_dog", (255, 243, 176), "BEWARE", "OF THE DOG", "he does not like scooters"),
    ]
    for name, bg, a, b, c in specs:
        img = Image.new("RGB", (256, 384), bg)
        d = ImageDraw.Draw(img)
        d.rectangle((6, 6, 249, 377), outline=INK, width=4)
        text_centre(d, a, 128, 60, 220, 70, fill=RED)
        text_centre(d, b, 128, 120, 220, 50, fill=INK, stroke=bg)
        d.rectangle((40, 160, 216, 300), fill=(200, 200, 210), outline=INK, width=3)
        if "chicken" in name:
            d.ellipse((90, 200, 170, 270), fill=WHITE, outline=INK, width=3)
            d.ellipse((140, 180, 180, 220), fill=WHITE, outline=INK, width=3)
            d.polygon([(178, 198), (196, 204), (178, 210)], fill=ORANGE)
        elif "dog" in name:
            d.ellipse((80, 190, 176, 280), fill=(210, 166, 121), outline=INK, width=3)
            d.ellipse((104, 220, 120, 236), fill=INK)
            d.ellipse((136, 220, 152, 236), fill=INK)
        elif "cake" in name:
            d.rectangle((88, 240, 168, 280), fill=(255, 143, 199), outline=INK, width=3)
            d.rectangle((104, 210, 152, 240), fill=WHITE, outline=INK, width=3)
        else:
            parcel_icon(d, 128, 225, 90)
        text_centre(d, c, 128, 335, 220, 34, fill=INK, stroke=bg)
        names.append(save(img, "decals", name))
    return names


def road_markings():
    names = []
    for name in ("arrow_straight", "arrow_left", "arrow_right", "text_slow"):
        img = Image.new("RGBA", (256, 512), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        w = (255, 255, 255, 235)
        if name == "text_slow":
            # Road lettering reads across the lane but is stretched along it, so it reads from a low angle.
            flat = Image.new("RGBA", (512, 220), (0, 0, 0, 0))
            fd = ImageDraw.Draw(flat)
            f, (tw, th, tl, tt) = fit_text(fd, "SLOW", 480, 190)
            fd.text((256 - tw / 2 - tl, 110 - th / 2 - tt), "SLOW", font=f, fill=w)  # no outline: paint has none
            img = flat.resize((256, 512))
        else:
            d.rectangle((108, 200, 148, 500), fill=w)
            if name == "arrow_straight":
                d.polygon([(128, 20), (40, 200), (216, 200)], fill=w)
            else:
                s = -1 if name == "arrow_left" else 1
                d.rectangle((108, 140, 148, 240), fill=w)
                d.rectangle((min(128, 128 + s * 70), 140, max(128, 128 + s * 70), 180), fill=w)  # the turn's arm
                d.polygon([(128 + s * 120, 160), (128 + s * 60, 100), (128 + s * 60, 220)], fill=w)
        names.append(save(img, "decals", "road_" + name))
    return names


def graffiti():
    names = []
    for k, (tag, fill, stroke) in enumerate((("YEET", (255, 90, 160), (40, 20, 60)), ("BONK!", (90, 220, 255), (20, 40, 90)), ("RC", (255, 210, 63), (90, 40, 20)))):
        img = Image.new("RGBA", (512, 256), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        f, (w, h, l, t) = fit_text(d, tag, 440, 180)
        x, y = 256 - w / 2 - l, 128 - h / 2 - t
        d.text((x + 8, y + 8), tag, font=f, fill=(0, 0, 0, 110))  # drop shadow
        d.text((x, y), tag, font=f, fill=fill + (255,), stroke_width=f.size // 10, stroke_fill=stroke + (255,))
        for j in range(5):  # drips
            dx = random.Random(k * 10 + j).randint(80, 430)
            d.line([(dx, 170), (dx, 170 + random.Random(j).randint(20, 60))], fill=fill + (220,), width=6)
        img = img.rotate(random.Random(k).uniform(-8, 8), resample=Image.BICUBIC)
        names.append(save(img, "decals", f"graffiti_{k + 1}"))
    return names


def cracks():
    """Damage decals for parcels: put on a parcel's faces as it loses condition."""
    names = []
    for level, branches in ((1, 3), (2, 7), (3, 14)):
        img = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        rnd = random.Random(level)
        for b in range(branches):
            x, y = 256 + rnd.uniform(-60, 60), 256 + rnd.uniform(-60, 60)
            a = rnd.uniform(0, math.tau)
            width = 9
            for _ in range(rnd.randint(6, 12)):
                a += rnd.uniform(-0.6, 0.6)
                step = rnd.uniform(18, 40)
                nx, ny = x + math.cos(a) * step, y + math.sin(a) * step
                d.line([(x, y), (nx, ny)], fill=(20, 20, 24, 235), width=max(2, int(width)))
                if rnd.random() < 0.25:  # small side cracks
                    sa = a + rnd.choice((-1, 1)) * rnd.uniform(0.6, 1.2)
                    d.line([(nx, ny), (nx + math.cos(sa) * step * 0.6, ny + math.sin(sa) * step * 0.6)], fill=(20, 20, 24, 200), width=max(1, int(width / 2)))
                x, y = nx, ny
                width *= 0.82
        names.append(save(img, "decals", f"crack_{level}"))
    return names


# ------------------------------------------------------------------ particles (white on transparent; tint in Roblox)


def soft_blob(size, radius, blur, lumps=0, seed=0):
    img = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(img)
    c = size / 2
    d.ellipse((c - radius, c - radius, c + radius, c + radius), fill=255)
    rnd = random.Random(seed)
    for _ in range(lumps):
        a, r = rnd.uniform(0, math.tau), radius * rnd.uniform(0.35, 0.6)
        x, y = c + math.cos(a) * radius * 0.7, c + math.sin(a) * radius * 0.7
        d.ellipse((x - r, y - r, x + r, y + r), fill=255)
    return img.filter(ImageFilter.GaussianBlur(blur))


def white(alpha):
    img = Image.new("RGBA", alpha.size, (255, 255, 255, 0))
    img.putalpha(alpha)
    return img


def particles():
    names = []
    names.append(save(white(soft_blob(256, 70, 18, lumps=6, seed=1)), "particles", "dust_puff"))
    names.append(save(white(soft_blob(256, 90, 30, lumps=8, seed=2).point(lambda v: int(v * 0.7))), "particles", "smoke"))

    spark = Image.new("L", (256, 256), 0)
    d = ImageDraw.Draw(spark)
    d.ellipse((96, 20, 160, 236), fill=255)
    names.append(save(white(spark.filter(ImageFilter.GaussianBlur(10))), "particles", "spark"))

    star_img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    star(ImageDraw.Draw(star_img), 128, 128, 110, (255, 255, 255, 255))
    names.append(save(star_img, "particles", "crash_star"))

    confetti = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(confetti)
    d.rounded_rectangle((88, 40, 168, 216), radius=10, fill=(255, 255, 255, 255))
    names.append(save(confetti, "particles", "confetti"))

    coin = Image.new("RGBA", (256, 256), (0, 0, 0, 0))  # coloured: it's always gold
    d = ImageDraw.Draw(coin)
    d.ellipse((16, 16, 240, 240), fill=(214, 160, 30, 255), outline=INK + (255,), width=8)
    d.ellipse((40, 40, 216, 216), fill=(255, 210, 63, 255))
    text_centre(d, "C", 128, 128, 140, 140, fill=(214, 160, 30, 255), stroke=(140, 100, 10, 255))
    names.append(save(coin, "particles", "coin"))

    splash = Image.new("L", (256, 256), 0)
    d = ImageDraw.Draw(splash)
    for k in range(9):
        a = -math.pi / 2 + (k - 4) * 0.28
        x, y = 128 + math.cos(a) * 85, 150 + math.sin(a) * 85
        d.ellipse((x - 14, y - 22, x + 14, y + 22), fill=255)
    d.ellipse((60, 150, 196, 220), fill=255)
    names.append(save(white(splash.filter(ImageFilter.GaussianBlur(3))), "particles", "water_splash"))

    speed = Image.new("L", (256, 256), 0)
    d = ImageDraw.Draw(speed)
    d.rectangle((0, 120, 255, 136), fill=255)
    names.append(save(white(speed.filter(ImageFilter.GaussianBlur(4))), "particles", "speed_line"))

    ring = Image.new("L", (256, 256), 0)
    d = ImageDraw.Draw(ring)
    d.ellipse((20, 20, 236, 236), outline=255, width=22)
    names.append(save(white(ring.filter(ImageFilter.GaussianBlur(4))), "particles", "shockwave"))
    return names


def preview(groups):
    """Contact sheet on a checkerboard so transparent textures read."""
    files = [(g, n) for g, ns in groups for n in ns]
    cols, cell = 8, 200
    rows = math.ceil(len(files) / cols)
    sheet = Image.new("RGB", (cols * cell, rows * (cell + 20)), (40, 42, 50))
    d = ImageDraw.Draw(sheet)
    for k, (g, n) in enumerate(files):
        im = Image.open(os.path.join(OUT, g, n + ".png")).convert("RGBA")
        im.thumbnail((cell - 12, cell - 12))
        x, y = (k % cols) * cell, (k // cols) * (cell + 20)
        bg = Image.new("RGBA", (cell - 8, cell - 8), (90, 90, 100, 255))
        bd = ImageDraw.Draw(bg)
        for i in range(0, cell, 16):
            for j in range(0, cell, 16):
                if (i // 16 + j // 16) % 2:
                    bd.rectangle((i, j, i + 15, j + 15), fill=(120, 120, 130, 255))
        bg.alpha_composite(im, ((cell - 8 - im.width) // 2, (cell - 8 - im.height) // 2))
        sheet.paste(bg.convert("RGB"), (x + 4, y + 4))
        d.text((x + 6, y + cell + 2), n, fill=(230, 230, 230))
    sheet.save(os.path.join(ART, "previews", "_textures.png"))


def main():
    decals = [depot_logo(), leaderboard_header()] + building_signs() + shop_signs() + district_signs() + billboards() + posters() + road_markings() + graffiti() + cracks()
    parts = particles()
    preview([("decals", decals), ("particles", parts)])
    print(f"textures: {len(decals)} decals, {len(parts)} particles")


if __name__ == "__main__":
    main()
