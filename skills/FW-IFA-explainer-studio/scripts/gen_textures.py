# -*- coding: utf-8 -*-
"""生成风格底纹（程序生成，没有版权问题）。一般不用重跑，assets/textures 里已经有成品。
用法：python3 gen_textures.py [输出目录]
  stone.jpg    石墨岩面（分形噪声＋浮雕光照，备用底纹）
  archive.jpg  档案：暖黑纤维纸面
"""
import os, sys
import numpy as np
from PIL import Image

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "textures")
os.makedirs(OUT, exist_ok=True)
W, H = 1200, 2100
rng = np.random.default_rng(7)

def value_noise(w, h, cell):
    gw, gh = w // cell + 3, h // cell + 3
    g = rng.random((gh, gw))
    ys, xs = np.mgrid[0:h, 0:w] / cell
    x0, y0 = xs.astype(int), ys.astype(int)
    fx, fy = xs - x0, ys - y0
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = g[y0, x0], g[y0, x0 + 1]
    c, d = g[y0 + 1, x0], g[y0 + 1, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy

def fbm(w, h, cells, gains):
    n = np.zeros((h, w))
    for c, g in zip(cells, gains):
        n += value_noise(w, h, c) * g
    return (n - n.min()) / (n.max() - n.min())

# 石墨岩面
hgt = fbm(W, H, [420, 180, 80, 32, 12, 5], [1.0, 0.6, 0.35, 0.2, 0.12, 0.06])
ridge = 1 - np.abs(fbm(W, H, [260, 90, 30], [1, .5, .25]) * 2 - 1)
hgt = hgt * 0.75 + ridge ** 3 * 0.25
gy, gx = np.gradient(hgt * 60)
light = np.clip(0.55 + (-gx * 0.6 - gy * 0.8), 0, 1.4)
base = 0.18 + hgt * 0.32
v = np.clip(base * light, 0, 1)
speck = (rng.random((H, W)) > 0.9965) * rng.random((H, W)) * 0.35
v = np.clip(v + speck, 0, 1)
rgb = np.stack([v * 1.00, v * 0.98, v * 0.95], -1)
Image.fromarray((rgb * 255).astype(np.uint8)).save(os.path.join(OUT, "stone.jpg"), quality=88)

# 暖黑纤维纸
fib = fbm(W, H, [600, 200, 40, 9, 3], [0.6, 0.5, 0.3, 0.25, 0.2])
streak = value_noise(W, H * 1, 4)
streak = np.repeat(streak[:, ::1], 1, axis=0)
v = 0.06 + fib * 0.07 + streak * 0.02
rgb = np.stack([v * 1.25, v * 1.0, v * 0.82], -1)
Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT, "archive.jpg"), quality=88)
print("ok", OUT)
