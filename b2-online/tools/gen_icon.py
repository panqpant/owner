#!/usr/bin/env python3
"""Draws app/icon.ico: a black and white Poke Ball with a blue centre, for Black 2."""
import sys
from PIL import Image, ImageDraw

out = sys.argv[1] if len(sys.argv) > 1 else "app/icon.ico"
S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
m, r = 40, S // 2 - 40
d.ellipse((m, m, S - m, S - m), fill=(20, 22, 28, 255))                    # black top half
d.pieslice((m, m, S - m, S - m), 0, 180, fill=(236, 238, 242, 255))       # white bottom half
d.ellipse((m, m, S - m, S - m), outline=(10, 10, 14, 255), width=56)
d.rectangle((m, S // 2 - 34, S - m, S // 2 + 34), fill=(10, 10, 14, 255))  # band
d.ellipse((S // 2 - 170, S // 2 - 170, S // 2 + 170, S // 2 + 170), fill=(10, 10, 14, 255))
d.ellipse((S // 2 - 110, S // 2 - 110, S // 2 + 110, S // 2 + 110), fill=(70, 150, 255, 255))
d.ellipse((S // 2 - 60, S // 2 - 60, S // 2 + 60, S // 2 + 60), fill=(200, 230, 255, 255))
img.resize((256, 256), Image.LANCZOS).save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
