"""Pixel width of an Emerald message line in the normal font (placeholders count as 0)."""
import re
def load(root):
    cm = {}
    for line in open(root + '/charmap.txt', encoding='utf-8'):
        m = re.match(r"^'(.)'\s*=\s*([0-9A-F]{2})\s*$", line)
        if m: cm[m.group(1)] = int(m.group(2), 16)
    src = open(root + '/src/fonts.c').read()
    body = src.split('gFontNormalLatinGlyphWidths[] = {', 1)[1].split('};', 1)[0]
    widths = [int(x) for x in re.findall(r'\d+', body)]
    def width(s):
        s = re.sub(r'\{[^}]*\}', '', s)
        s = re.sub(r'\\[nlp]|\$$', '', s).replace("\\'", "'")
        return sum(widths[cm[c]] if c in cm and cm[c] < len(widths) else 6 for c in s)
    return width
