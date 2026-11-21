"""Read EMCAP1 capture files written by the game (pc/ppu.c)."""
import numpy as np

def load(path):
    b = open(path, 'rb').read()
    assert b[:6] == b'EMCAP1', path
    w, h = np.frombuffer(b, '<u4', 2, 8)
    w, h = int(w), int(h)
    o = 16
    layers = []
    for i in range(5):
        rgba = np.frombuffer(b, np.uint8, w * h * 4, o).reshape(h, w, 4).copy(); o += w * h * 4
        hsh = np.frombuffer(b, '<u8', w * h, o).reshape(h, w).copy(); o += w * h * 8
        info = np.frombuffer(b, np.uint8, w * h, o).reshape(h, w).copy(); o += w * h
        rgba[..., 3] = np.where(rgba[..., 3] > 0, 255, 0)
        layers.append(dict(rgba=rgba, hash=hsh, info=info))
    return w, h, layers

def flatten(layers, order=(3, 2, 1, 4)):
    h, w = layers[0]['rgba'].shape[:2]
    out = np.zeros((h, w, 3), np.float32)
    for i in order:
        c = layers[i]['rgba'].astype(np.float32)
        a = c[..., 3:4] / 255
        out = out * (1 - a) + c[..., :3] * a
    return out.astype(np.uint8)
