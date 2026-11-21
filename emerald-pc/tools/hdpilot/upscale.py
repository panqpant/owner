"""Upscalers for HD pack generation. All take an RGBA uint8 image (A = 0/255)
and return an RGBA uint8 image `scale` times larger."""
import subprocess, numpy as np

KEY = np.array([255, 0, 255], np.uint8)   # stands in for transparency in RGB-only filters

def _ffmpeg(rgb, filt):
    h, w = rgb.shape[:2]
    p = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{w}x{h}', '-i', '-',
                        '-vf', filt, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], input=rgb.tobytes(), capture_output=True, check=True)
    return np.frombuffer(p.stdout, np.uint8).reshape(h * 4, w * 4, 3)

def _keyed(rgba):
    rgb = rgba[..., :3].copy()
    rgb[rgba[..., 3] == 0] = KEY
    return rgb

def _snap(rgb_src_keyed, big, f):
    """Map each pixel of `big` (f x the source) to the closest colour among its
    source pixel's 3x3 neighbourhood: removes blended in-between colours.
    Transparency (the key colour) is decided separately from an xBR-scaled
    mask, and opaque pixels only snap to opaque colours (no halos)."""
    h, w = rgb_src_keyed.shape[:2]
    keyed = (rgb_src_keyed == KEY).all(-1)
    mask = np.where(keyed, 0, 255).astype(np.uint8)
    mbig = _ffmpeg(np.dstack([mask] * 3), 'xbr=4')[..., 0] if keyed.any() else np.full(big.shape[:2], 255, np.uint8)
    pad = np.pad(rgb_src_keyed.astype(np.int32), ((1, 1), (1, 1), (0, 0)), mode='edge')
    cands = np.stack([pad[1 + dy:1 + dy + h, 1 + dx:1 + dx + w] for dy in (-1, 0, 1) for dx in (-1, 0, 1)], 2)  # h,w,9,3
    cands = np.repeat(np.repeat(cands, f, 0), f, 1)                                                          # H,W,9,3
    d = ((cands - big[:, :, None, :].astype(np.int32)) ** 2).sum(-1)
    d = np.where((cands == KEY).all(-1), 1 << 40, d)          # never snap to transparent here
    best = d.argmin(-1)
    out = np.take_along_axis(cands, best[..., None, None], 2)[:, :, 0, :].astype(np.uint8)
    allkey = (cands == KEY).all(-1).all(-1)
    out[(mbig < 128) | allkey] = KEY
    return out

def _unkey(rgb):
    a = np.where((rgb == KEY).all(-1), 0, 255).astype(np.uint8)
    return np.dstack([rgb, a])

def nearest(rgba, scale):
    return np.repeat(np.repeat(rgba, scale, 0), scale, 1)

def xbr4(rgba):
    k = _keyed(rgba)
    return _unkey(_snap(k, _ffmpeg(k, 'xbr=4'), 4))

def hqx4(rgba):
    k = _keyed(rgba)
    return _unkey(_snap(k, _ffmpeg(k, 'hqx=4'), 4))

def _blur(a, sigma):
    r = max(1, int(sigma * 3))
    x = np.arange(-r, r + 1); k = np.exp(-x * x / (2 * sigma * sigma)); k /= k.sum()
    a = np.apply_along_axis(lambda v: np.convolve(v, k, 'same'), 0, a) if False else a
    # separable convolution with edge padding
    p = np.pad(a, ((r, r), (0, 0)), mode='edge'); a = sum(k[i] * p[i:i + a.shape[0]] for i in range(2 * r + 1))
    p = np.pad(a, ((0, 0), (r, r)), mode='edge'); a = sum(k[i] * p[:, i:i + a.shape[1]] for i in range(2 * r + 1))
    return a

def _edt(mask):
    """Approximate distance (in pixels) from each True pixel to the nearest
    False pixel (two-pass chamfer)."""
    INF = 1e6
    d = np.where(mask, INF, 0.0).astype(np.float32)
    h, w = d.shape
    a, b = 1.0, 1.4142
    for y in range(h):
        row = d[y]
        if y > 0:
            up = d[y - 1]
            row = np.minimum(row, up + a)
            row[1:] = np.minimum(row[1:], up[:-1] + b); row[:-1] = np.minimum(row[:-1], up[1:] + b)
        for x in range(1, w): pass
        d[y] = row
    # horizontal sweeps with cumulative trick
    for y in range(h):
        r = d[y]
        for x in range(1, w):
            if r[x - 1] + a < r[x]: r[x] = r[x - 1] + a
        for x in range(w - 2, -1, -1):
            if r[x + 1] + a < r[x]: r[x] = r[x + 1] + a
    for y in range(h - 2, -1, -1):
        dn = d[y + 1]
        d[y] = np.minimum(d[y], dn + a)
        d[y, 1:] = np.minimum(d[y, 1:], dn[:-1] + b); d[y, :-1] = np.minimum(d[y, :-1], dn[1:] + b)
    return d

def smooth_labels(rgba, scale=8, base='xbr', sigma=1.1, aa=0.9, shade=0.0):
    """Shapes from xBR (or hqx) at 4x, region outlines smoothed and re-drawn
    at `scale`x with anti-aliasing only on the boundaries."""
    k = _keyed(rgba)
    big = _snap(k, _ffmpeg(k, 'xbr=4' if base == 'xbr' else 'hqx=4'), 4)    # 4x, pure palette colours
    H, W = big.shape[0] * scale // 4, big.shape[1] * scale // 4
    codes = (big[..., 0].astype(np.int32) << 16) | (big[..., 1].astype(np.int32) << 8) | big[..., 2]
    labels, inv = np.unique(codes, return_inverse=True)
    inv = inv.reshape(codes.shape)
    best = np.full((H, W), -1e9, np.float32); second = np.full((H, W), -1e9, np.float32)
    bestl = np.zeros((H, W), np.int32); secondl = np.zeros((H, W), np.int32)
    yy = (np.arange(H) + 0.5) * 4 / scale - 0.5; xx = (np.arange(W) + 0.5) * 4 / scale - 0.5
    y0 = np.clip(np.floor(yy).astype(int), 0, big.shape[0] - 1); y1 = np.clip(y0 + 1, 0, big.shape[0] - 1); fy = (yy - np.floor(yy))[:, None]
    x0 = np.clip(np.floor(xx).astype(int), 0, big.shape[1] - 1); x1 = np.clip(x0 + 1, 0, big.shape[1] - 1); fx = (xx - np.floor(xx))[None, :]
    for li in range(len(labels)):
        m = inv == li
        ys, xs = np.nonzero(m)
        if len(ys) == 0: continue
        f = _blur(m.astype(np.float32), sigma)
        f = (f[y0][:, x0] * (1 - fx) + f[y0][:, x1] * fx) * (1 - fy) + (f[y1][:, x0] * (1 - fx) + f[y1][:, x1] * fx) * fy
        gt = f > best
        second = np.where(gt, best, np.maximum(second, f)); secondl = np.where(gt, bestl, np.where(f > second, li, secondl))
        bestl = np.where(gt, li, bestl); best = np.where(gt, f, best)
    def col(l):
        c = labels[l]
        return np.dstack([(c >> 16) & 255, (c >> 8) & 255, c & 255]).astype(np.float32)
    # anti-alias: blend the two strongest regions where they are nearly tied
    t = np.clip((best - second) / (0.25 * aa) , 0, 1)[..., None] * 0.5 + 0.5
    cb, cs = col(bestl), col(secondl)
    ab = np.where((cb == KEY).all(-1), 0, 255)[..., None].astype(np.float32)
    as_ = np.where((cs == KEY).all(-1), 0, 255)[..., None].astype(np.float32)
    a = ab * t + as_ * (1 - t)
    rgb = (cb * ab * t + cs * as_ * (1 - t)) / np.maximum(a, 1e-3)
    # Where the best region is transparent, take the colour of the best opaque one.
    rgb = np.where(ab > 0, rgb, np.where(as_ > 0, cs, rgb))
    # 8x8 source tiles with no transparent pixels stay fully opaque (no seams at tile edges).
    h0, w0 = rgba.shape[:2]
    op = rgba[..., 3] > 0
    th, tw = (h0 + 7) // 8, (w0 + 7) // 8
    full = np.zeros((th * 8, tw * 8), bool); full[:h0, :w0] = op
    full = full.reshape(th, 8, tw, 8).all((1, 3))
    fullpx = np.repeat(np.repeat(full, 8 * scale, 0), 8 * scale, 1)[:H, :W]
    a = np.where(fullpx[..., None], 255.0, a)
    if shade > 0:
        # Soft cel shading: each flat colour region darkens gently toward its
        # outline and gets a faint highlight toward its top-left.
        inner = np.zeros((H, W), np.float32)
        edge = np.zeros((H, W), bool)
        edge[1:, :] |= bestl[1:, :] != bestl[:-1, :]; edge[:-1, :] |= bestl[1:, :] != bestl[:-1, :]
        edge[:, 1:] |= bestl[:, 1:] != bestl[:, :-1]; edge[:, :-1] |= bestl[:, 1:] != bestl[:, :-1]
        d = _edt(~edge) / scale                              # distance to an outline, in GBA pixels
        rim = np.exp(-d / 0.9)                               # 1 at outlines
        gy, gx = np.gradient(_blur(bestl.astype(np.float32) * 0 + d, 2.0))
        light = np.clip(-(gx + gy) * 0.7, -1, 1)             # facing top-left = brighter
        k = 1.0 - shade * 0.22 * rim + shade * 0.10 * light * (1 - rim)
        rgb = np.clip(rgb * k[..., None], 0, 255)
    return np.dstack([np.clip(rgb, 0, 255), a]).astype(np.uint8)
