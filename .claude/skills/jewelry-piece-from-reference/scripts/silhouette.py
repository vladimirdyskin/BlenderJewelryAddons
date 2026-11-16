"""Силуэт изделия на белом фоне построчно: левый и правый край в пикселях и ширина в мм.

  python3 silhouette.py ФОТО --mm-per-px 0.0196 --rows 1150 1760 20 [--x 650 1350] [--threshold 243]

Масштаб мм/пиксель брать с подложки в сцене Blender (размер картинки-пустышки / ширина фото в пикселях)
или с детали известного размера. Блики на камне и золоте дают провалы — сверять фронт со спинкой.
"""
import argparse
import numpy as np
from PIL import Image, ImageFilter

ap = argparse.ArgumentParser()
ap.add_argument("photo")
ap.add_argument("--mm-per-px", type=float, required=True)
ap.add_argument("--rows", type=int, nargs=3, required=True, metavar=("Y0", "Y1", "STEP"))
ap.add_argument("--x", type=int, nargs=2, default=None)
ap.add_argument("--threshold", type=int, default=243)
a = ap.parse_args()
img = np.asarray(Image.open(a.photo).convert("RGB").filter(ImageFilter.GaussianBlur(1.2))).astype(int)
x0, x1 = a.x or (0, img.shape[1])
dark = img.min(2) < a.threshold
for y in range(*a.rows):
    xs = np.where(dark[y, x0:x1])[0]
    if len(xs) > 2:
        l, r = int(xs.min() + x0), int(xs.max() + x0)
        print("y %5d  x %5d..%5d  width %.2f mm  centre %.1f px" % (y, l, r, (r - l) * a.mm_per_px, (l + r) / 2))
