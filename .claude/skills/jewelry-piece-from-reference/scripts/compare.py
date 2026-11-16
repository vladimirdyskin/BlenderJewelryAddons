"""Лист сравнения: сверху вырезки фото в масштабе рендера, снизу рендеры тех же ракурсов.

  python3 compare.py ВЫХОД.png --size 17 --mm-per-px 0.0196 \\
      --pair ФОТО CX CY РЕНДЕР [--pair ...]

CX, CY — пиксель фото, которому соответствует центр кадра рендера; --size — сторона кадра рендера в мм
(ortho_scale в preview.py). Наложение силуэта: добавить --overlay (первая пара, красным поверх фото).
"""
import argparse
from PIL import Image, ImageOps

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--size", type=float, required=True)
ap.add_argument("--mm-per-px", type=float, required=True)
ap.add_argument("--pair", nargs=4, action="append", required=True, metavar=("PHOTO", "CX", "CY", "RENDER"))
ap.add_argument("--overlay", action="store_true")
ap.add_argument("--tile", type=int, default=700)
a = ap.parse_args()
half, t = a.size / 2 / a.mm_per_px, a.tile
sheet = Image.new("RGB", (t * len(a.pair), t * (3 if a.overlay else 2)), "white")
for i, (photo, cx, cy, render) in enumerate(a.pair):
    cx, cy = float(cx), float(cy)
    ph = Image.open(photo).convert("RGB").crop((int(cx - half), int(cy - half), int(cx + half), int(cy + half)))
    ph = ph.resize((t, t), Image.LANCZOS)
    r = Image.open(render).convert("RGB").resize((t, t), Image.LANCZOS)
    sheet.paste(ph, (i * t, 0))
    sheet.paste(r, (i * t, t))
    if a.overlay:
        mask = ImageOps.invert(r.convert("L")).point(lambda v: 255 if v < 215 else 0)
        sheet.paste(Image.composite(Image.blend(ph, Image.new("RGB", (t, t), (255, 0, 0)), 0.35), ph, mask), (i * t, 2 * t))
sheet.save(a.out)
print("saved", a.out)
