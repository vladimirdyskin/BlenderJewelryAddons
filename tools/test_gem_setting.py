# SPDX-License-Identifier: GPL-3.0-or-later

"""Каст My_Gem_Setting (jewel_tools/gem_setting.py) против вычисленного меша GN + SubD.

Фоновый Blender:
  Blender --factory-startup --background --python tools/test_gem_setting.py [-- --preview]
  --preview  ещё и лист dist/previews/gem_setting_v1.png
Код выхода 1 — проверка не прошла.

Истина — меш после GN и Subdivision Surface объекта-каста; на время замера уровень SubD
поднят до LEVEL (почти предельная поверхность).
"""

from __future__ import annotations

from math import acos, atan2, ceil, cos, degrees, hypot, pi, radians, sin
from pathlib import Path
import sys
import traceback

import bpy
from mathutils import Euler, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from jewelry_suite import gem_outline as go, gem_setting as gs, gems  # gems — parametric_gems

SIZE = 6.0               # мм на единицу шаблона
STRETCH = 1.3            # растянутый камень: длина (Y) x 1.3
SHIFT = (0.7, -0.4)      # и меш сдвинут
LEVEL = 5                # уровень SubD на время замера
PRONG_VERTS = 10 * 4 ** LEVEL + 2  # крапан после SubD (у трубки-рейки вершин столько же, сколько граней)
CAP_VERTS = (2 ** LEVEL + 1) ** 2  # вершин торца-квада после SubD
PREVIEW_CUTS = ("ROUND", "OVAL", "PEAR", "PRINCESS", "EMERALD", "HEART")
PREVIEW = ROOT / "dist" / "previews" / "gem_setting_v1.png"
PREVIEW_WIDTH = 6.5      # мм — ширина камней на листе превью
TOL_DIAMETER = 2.0       # % ствола при Tip Scale 1
TOL_SHOULDER = 3.0       # % диаметра у плеча при Tip Scale 0.8
TOL_DOME = 0.2           # высота купола / радиус верхушки при Tip Round 1: 1 +- 0.2
TOL_POS = 0.02           # мм: ось, верх, низ, z реек
TOL_SECTION = 5.0        # % сечения рейки (ширина; высота и углы — тот же допуск)
TOL_NORMAL = 2.0         # градусы
# прогоны: (Tip Scale, Tip Round, Rail Sharpness)
RUNS = ((1.0, 0.0, 0.0), (1.0, 0.5, 0.5), (1.0, 1.0, 1.0), (0.8, 0.0, 1.0), (0.8, 0.5, 0.0), (0.8, 1.0, 0.5))


# --- геометрия ---------------------------------------------------------------

def walk(links: dict) -> list:
    assert all(len(v) == 2 for v in links.values()), "not a simple loop"
    start = min(links)
    order, prev, cur = [start], None, start
    while True:
        cur, prev = next(v for v in links[cur] if v != prev), cur
        if cur == start:
            break
        order.append(cur)
    assert len(order) == len(links), "several loops"
    return order


def crown_outline(verts, faces) -> list[tuple[float, float]]:
    """Настоящий контур рундиста сверху (как в tools/test_gem_outline.py), против часовой."""
    uses = {}
    for f in faces:
        nx = ny = nz = 0.0
        for a, b in zip(f, f[1:] + f[:1]):
            (x1, y1, z1), (x2, y2, z2) = verts[a], verts[b]
            nx += y1 * z2 - z1 * y2
            ny += z1 * x2 - x1 * z2
            nz += x1 * y2 - y1 * x2
        if nz > 1e-3 * (nx * nx + ny * ny + nz * nz) ** 0.5:
            for a, b in zip(f, f[1:] + f[:1]):
                key = (min(a, b), max(a, b))
                uses[key] = uses.get(key, 0) + 1
    links = {}
    for (a, b), count in uses.items():
        if count == 1:
            links.setdefault(a, []).append(b)
            links.setdefault(b, []).append(a)
    points = [(verts[i][0], verts[i][1]) for i in walk(links)]
    size = max(max(p[0] for p in points) - min(p[0] for p in points), max(p[1] for p in points) - min(p[1] for p in points))
    clean = []
    for p in points:
        if not clean or hypot(p[0] - clean[-1][0], p[1] - clean[-1][1]) > 1e-6 * size:
            clean.append(p)
    clean = [p for i, p in enumerate(clean) if abs(go._turn(clean[i - 1], p, clean[(i + 1) % len(clean)])) > 1e-4]
    return clean if go._area2(clean) > 0.0 else clean[::-1]


def angle(u, v) -> float:
    """Угол между векторами XY, градусы."""
    d = (u[0] * v[0] + u[1] * v[1]) / ((hypot(u[0], u[1]) * hypot(v[0], v[1])) or 1.0)
    return degrees(acos(max(-1.0, min(1.0, d))))


def limit_normal(p, dense):
    """Наружная нормаль предела петли в ближайшей к p точке плотной выборки
    (в острой вершине касательная выборки — биссектриса)."""
    _, _, tx, ty = min(dense, key=lambda s: (s[0] - p[0]) ** 2 + (s[1] - p[1]) ** 2)
    return ty, -tx


def nearest_segment(outline, p):
    """(индекс отрезка i..i+1, доля по нему, расстояние) — ближайший к p отрезок контура."""
    best = None
    for i in range(len(outline)):
        (ax, ay), (bx, by) = outline[i], outline[(i + 1) % len(outline)]
        vx, vy = bx - ax, by - ay
        t = min(1.0, max(0.0, ((p[0] - ax) * vx + (p[1] - ay) * vy) / (vx * vx + vy * vy)))
        d = hypot(p[0] - ax - vx * t, p[1] - ay - vy * t)
        if best is None or d < best[2]:
            best = (i, t, d)
    return best


def signed_distance(p, outline) -> float:
    """Расстояние до контура (против часовой), снаружи — плюс."""
    i, t, d = nearest_segment(outline, p)
    (ax, ay), (bx, by) = outline[i], outline[(i + 1) % len(outline)]
    inside = False
    for k in range(len(outline)):
        (x1, y1), (x2, y2) = outline[k - 1], outline[k]
        if (y1 > p[1]) != (y2 > p[1]) and p[0] < x1 + (p[1] - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return -d if inside else d


def girdle_normal(outline, p):
    """Нормаль настоящего контура у p. Контур шаблона — ломаная с изломами до 18° (вершины на
    гладкой кривой), нормаль отрезка не годится: нормаль у p по окружностям через три вершины
    вокруг отрезка (i-1, i, i+1) и (i, i+1, i+2), смесь по доле на отрезке."""
    n = len(outline)
    i, t, _ = nearest_segment(outline, p)
    (ax, ay), (bx, by) = outline[i], outline[(i + 1) % n]
    seg = ((by - ay), -(bx - ax))

    def circle_normal(a, b, c):
        d = 2.0 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]))
        if abs(d) < 1e-9:
            return seg
        sa, sb, sc = a[0] ** 2 + a[1] ** 2, b[0] ** 2 + b[1] ** 2, c[0] ** 2 + c[1] ** 2
        ux = (sa * (b[1] - c[1]) + sb * (c[1] - a[1]) + sc * (a[1] - b[1])) / d
        uy = (sa * (c[0] - b[0]) + sb * (a[0] - c[0]) + sc * (b[0] - a[0])) / d
        nx, ny = p[0] - ux, p[1] - uy
        return (nx, ny) if nx * seg[0] + ny * seg[1] > 0.0 else (-nx, -ny)

    n1 = circle_normal(outline[i - 1], outline[i], outline[(i + 1) % n])
    n2 = circle_normal(outline[i], outline[(i + 1) % n], outline[(i + 2) % n])
    l1, l2 = hypot(*n1), hypot(*n2)
    return ((1.0 - t) * n1[0] / l1 + t * n2[0] / l2, (1.0 - t) * n1[1] / l1 + t * n2[1] / l2)


# --- Blender ------------------------------------------------------------------

def make_gem(cut: str, stretched: bool, size: float = SIZE) -> bpy.types.Object:
    """Камень огранки cut: size мм на единицу шаблона."""
    spec = gems._CUT_SPECS[cut]
    length = size * spec.base_length * (STRETCH if stretched else 1.0)
    width = size * spec.base_width
    verts, faces = gems._cut_geometry(cut, length, width, spec.girdle_percent, spec.crown_percent, spec.pavilion_percent)
    if stretched:
        verts = [(x + SHIFT[0], y + SHIFT[1], z) for x, y, z in verts]
    mesh = bpy.data.meshes.new(cut)
    mesh.from_pydata(verts, [], faces)
    obj = bpy.data.objects.new(cut + (" stretched" if stretched else ""), mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj["gem"] = {"cut": cut.title() if stretched else cut, "stone": "DIAMOND"}  # регистр не важен
    return obj


def drop(obj) -> None:
    for child in list(obj.children):
        drop(child)
    mesh = obj.data
    bpy.data.objects.remove(obj)
    if mesh is not None and mesh.users == 0:
        bpy.data.meshes.remove(mesh)


def modifier(obj, kind):
    return next(m for m in obj.modifiers if m.type == kind)


def ids(obj):
    return {it.name: it.identifier for it in modifier(obj, "NODES").node_group.interface.items_tree
            if it.item_type == "SOCKET" and it.in_out == "INPUT"}


def set_inputs(obj, values: dict) -> None:
    md, names = modifier(obj, "NODES"), ids(obj)
    for name, value in values.items():
        getattr(md.properties.inputs, names[name]).value = value
    obj.update_tag()


def get_input(obj, name):
    return getattr(modifier(obj, "NODES").properties.inputs, ids(obj)[name]).value


def evaluate(obj, subd: bool, level: int = LEVEL):
    """Вычисленный меш: координаты, рёбра, грани, crease рёбер."""
    sub = modifier(obj, "SUBSURF")
    sub.show_viewport = subd
    sub.levels = level
    obj.update_tag()
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    m = ev.to_mesh()
    try:
        co = [0.0] * (3 * len(m.vertices))
        m.vertices.foreach_get("co", co)
        flat = [0] * (2 * len(m.edges))
        m.edges.foreach_get("vertices", flat)
        crease = m.attributes.get("crease_edge")
        return {
            "verts": [Vector(co[i:i + 3]) for i in range(0, len(co), 3)],
            "edges": [(flat[i], flat[i + 1]) for i in range(0, len(flat), 2)],
            "faces": [tuple(p.vertices) for p in m.polygons],
            "crease": [d.value for d in crease.data] if crease else None,
        }
    finally:
        ev.to_mesh_clear()


def shells(mesh):
    """Связные куски: [{verts, edges, faces}]."""
    parent = list(range(len(mesh["verts"])))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in mesh["edges"]:
        ra, rb = root(a), root(b)
        if ra != rb:
            parent[ra] = rb
    groups = {}
    for i in range(len(mesh["verts"])):
        groups.setdefault(root(i), {"verts": [], "edges": [], "faces": []})["verts"].append(i)
    for e in mesh["edges"]:
        groups[root(e[0])]["edges"].append(e)
    for f in mesh["faces"]:
        groups[root(f[0])]["faces"].append(f)
    return list(groups.values())


def closed_volume(verts, faces):
    """(каждое ребро ровно в двух гранях, объём)."""
    uses = {}
    vol = 0.0
    for f in faces:
        for a, b in zip(f, f[1:] + f[:1]):
            key = (min(a, b), max(a, b))
            uses[key] = uses.get(key, 0) + 1
        for k in range(1, len(f) - 1):
            vol += verts[f[0]].dot(verts[f[k]].cross(verts[f[k + 1]])) / 6.0
    return all(c == 2 for c in uses.values()), vol


def loose_points(mesh) -> list[tuple[float, float]]:
    used = {i for e in mesh.edges for i in e.vertices}
    return [(v.co.x, v.co.y) for v in mesh.vertices if v.index not in used]


def ray(bvh, origin, direction, far=3.0):
    return bvh.ray_cast(origin, direction, far)[3]


# --- замеры -------------------------------------------------------------------

def prong_cages(cage):
    """Крапана клетки: центры колец (основание, плечо, верхушка), ось, кольцо основания.
    Кольца — по 4 вершины подряд (порядок Curve to Mesh)."""
    out = []
    v = cage["verts"]
    for s in shells(cage):
        if len(s["verts"]) == 12 and len(s["faces"]) == 10:     # у рейки из 3 точек тоже 12 вершин
            ring = sorted(s["verts"])
            base, shoulder, tip = (sum((v[i] for i in ring[k:k + 4]), Vector()) / 4.0 for k in (0, 4, 8))
            out.append({"base": base, "shoulder": shoulder, "tip": tip, "axis": (tip - shoulder).normalized(),
                        "base_ring": [v[i] for i in ring[:4]]})
    return out


def axis_at(prong, z):
    p, a = prong["shoulder"], prong["axis"]
    return p + a * ((z - p.z) / a.z)


def nearest_prong(prongs, site):
    return min(prongs, key=lambda p: hypot(axis_at(p, 0.0).x - site[0], axis_at(p, 0.0).y - site[1]))


def section_widths(verts, edges, origin, axis, tau, face, side):
    """Ширина сечения плоскостью поперёк оси на tau: по сторонам квадрата и по диагоналям."""
    pts = []
    for a, b in edges:
        ta, tb = (verts[a] - origin).dot(axis) - tau, (verts[b] - origin).dot(axis) - tau
        if ta * tb < 0.0:
            p = verts[a] + (verts[b] - verts[a]) * (ta / (ta - tb))
            pts.append(((p - origin).dot(face), (p - origin).dot(side)))
    widths = []
    for k in range(4):
        c, s = cos(k * pi / 4), sin(k * pi / 4)
        proj = [x * c + y * s for x, y in pts]
        widths.append(max(proj) - min(proj))
    return widths


def prong_profile(verts, shell, prong, n, diameter):
    """Ствол, плечо, купол одного крапана после SubD.
    stem — ширины (4 направления) в 5 сечениях от верха косого основания + радиус до плеча - радиус;
    (None, если ствол короче четверти диаметра); shoulder — средний диаметр на кольце плеча;
    dome — высота скругления / радиус верхушки: эллипс tau = c + H sqrt(1 - (r / R)^2) с экватором c
    по сечениям колпака r = 0.3-0.95 R, R — наибольший радиус над плечом."""
    a, origin = prong["axis"], prong["base"]
    side = a.cross(Vector((n[0], n[1], 0.0))).normalized()
    face = side.cross(a)
    edges = shell["edges"]
    taus = [(verts[i] - origin).dot(a) for i in shell["verts"]]
    apex = max(taus)
    tau_s = (prong["shoulder"] - origin).dot(a)

    def radius(tau):
        return sum(section_widths(verts, edges, origin, a, tau, face, side)) / 8.0

    r_s = radius(tau_s)
    low = max((p - origin).dot(a) for p in prong["base_ring"]) + diameter * 0.25
    high = tau_s - r_s
    stem = [section_widths(verts, edges, origin, a, low + (high - low) * k / 4.0, face, side)
            for k in range(5)] if high - low > diameter * 0.25 else None
    profile = [(tau_s + (apex - tau_s) * (k + 0.5) / 60.0, 0.0) for k in range(60)]
    profile = [(tau, radius(tau)) for tau, _ in profile]
    r_cap = max(r for _, r in profile)
    rows = []
    for tau, r in profile:
        r /= r_cap
        if 0.3 <= r <= 0.95:
            rows.append((tau, (1.0 - r * r) ** 0.5))
    s11 = len(rows)
    s12 = sum(f for _, f in rows)
    s22 = sum(f * f for _, f in rows)
    b1 = sum(t for t, _ in rows)
    b2 = sum(t * f for t, f in rows)
    det = s11 * s22 - s12 * s12
    height = (s11 * b2 - s12 * b1) / det if rows and det else 0.0
    return {"stem": stem, "shoulder": 2.0 * r_s, "dome": height / r_cap}


def measure_prongs(cage, result, sites, dense, values, profile=False):
    """По местам: ошибка оси у Pg и Pb (и центра основания), верх - Prong Height,
    низ + Basket Height, число вершин на плоскости z = -Basket Height, угол нормали GN к нормали
    предела;
    с profile — ствол, плечо и купол первого крапана."""
    prongs = prong_cages(cage)
    v = result["verts"]
    sub = [s for s in shells(result) if len(s["verts"]) == PRONG_VERTS]
    centers = [sum((v[i] for i in s["verts"]), Vector()) / len(s["verts"]) for s in sub]
    offset, scale, bh = values["Prong Offset"], values["Bottom Scale"], values["Basket Height"]
    out = []
    for k, site in enumerate(sites):
        prong = nearest_prong(prongs, site)
        n = limit_normal(site, dense)
        pg = (site[0] + n[0] * offset, site[1] + n[1] * offset)
        at0, atb = axis_at(prong, 0.0), axis_at(prong, -bh)
        gn = ((at0.x - site[0]) / offset, (at0.y - site[1]) / offset)
        mid = (prong["base"] + prong["tip"]) * 0.5
        s = sub[min(range(len(sub)), key=lambda i: (centers[i] - mid).length)]
        pts = [v[i] for i in s["verts"]]
        row = {
            "axis": max(hypot(at0.x - pg[0], at0.y - pg[1]), hypot(atb.x - pg[0] * scale, atb.y - pg[1] * scale),
                        (prong["base"] - atb).length),
            "top": max(p.z for p in pts) - values["Prong Height"],
            "bottom": min(p.z for p in pts) + bh,
            "flat": sum(1 for p in pts if abs(p.z + bh) < 1e-5),
            "normal": angle(gn, n), "gn": gn, "site": site,
        }
        if profile and k == 0:
            row.update(prong_profile(v, s, prong, n, values["Prong Diameter"]))
        out.append(row)
    return out


def measure_rails(result, outline, loop, dense, values):
    """Рейки лучами из середины расчётного сечения поперёк рейки (по нормали предела петли) и по Z:
    ширина и высота (%), расстояние наружной стороны до настоящего контура - Rail Offset (мм),
    z-границы (мм); в острых вершинах петли — ширина по биссектрисе против W / cos(половины
    поворота) (%). Нижняя рейка — против контура, масштабированного Bottom Scale."""
    v = result["verts"]
    width, height, offset = values["Rail Width"], values["Rail Height"], values["Rail Offset"]
    levels = {"top": (1.0, -values["Rail Drop"] - height * 0.5),
              "bottom": (values["Bottom Scale"], -values["Basket Height"] + height * 0.5)}
    rails = {}
    for s in shells(result):
        if len(s["verts"]) != PRONG_VERTS:
            z = sum(v[i].z for i in s["verts"]) / len(s["verts"])
            name = min(levels, key=lambda k: abs(levels[k][1] - z))
            rails[name] = BVHTree.FromPolygons(v, s["faces"])
    mid = offset - width * 0.5
    keep_out = 1.5 * (width + abs(offset)) + 0.1     # у острой вершины луч уходит в соседнюю сторону
    res = {}
    for name, bvh in rails.items():
        k, zc = levels[name]
        girdle = [(x * k, y * k) for x, y in outline]
        corners = [(x * k, y * k) for x, y, c in loop if c]
        worst = {"width": 0.0, "height": 0.0, "outer": 0.0, "z": 0.0, "corner": 0.0, "missed": 0}

        def keep(key, value):
            worst[key] = max(worst[key], value, key=abs)

        for x, y, tx, ty in dense[::4]:
            if any(hypot(x * k - cx, y * k - cy) < keep_out for cx, cy in corners):
                continue
            n = Vector((ty, -tx, 0.0))
            c = Vector((x * k, y * k, zc)) + n * mid
            t = [ray(bvh, c, d) for d in (n, -n, Vector((0, 0, 1)), Vector((0, 0, -1)))]
            if None in t:
                worst["missed"] += 1
                continue
            keep("width", 100.0 * ((t[0] + t[1]) / width - 1.0))
            keep("height", 100.0 * ((t[2] + t[3]) / height - 1.0))
            outer = c + n * t[0]
            keep("outer", signed_distance((outer.x, outer.y), girdle) - offset)
            keep("z", t[2] - height * 0.5)
            keep("z", height * 0.5 - t[3])
        for i, (x, y, sharp) in enumerate(loop):
            if not sharp:
                continue
            a, b = loop[i - 1], loop[(i + 1) % len(loop)]
            turn = Vector((x - a[0], y - a[1], 0)).normalized() + Vector((b[0] - x, b[1] - y, 0)).normalized()
            bis = turn.cross(Vector((0, 0, 1))).normalized()
            miter = 2.0 / turn.length
            c = Vector((x * k, y * k, zc)) + bis * mid * miter
            t = [ray(bvh, c, d) for d in (bis, -bis)]
            if None in t:
                worst["missed"] += 1
                continue
            keep("corner", 100.0 * ((t[0] + t[1]) / (width * miter) - 1.0))
        res[name] = worst
    return res


# --- проверки -------------------------------------------------------------------

def check_cut(cut: str, stretched: bool, errors: list) -> dict:
    gem = make_gem(cut, stretched)
    obj = gs.setup(gem)
    label = f"{cut} {'stretched' if stretched else 'default'}"
    mesh = gem.data
    outline = crown_outline([tuple(p.co) for p in mesh.vertices], [tuple(p.vertices) for p in mesh.polygons])
    xs, ys = [p.co.x for p in mesh.vertices], [p.co.y for p in mesh.vertices]
    stone = min(max(xs) - min(xs), max(ys) - min(ys))
    tol_outer = max(TOL_POS, 0.005 * stone)
    loop = go.gem_loop(gem)
    dense = go.limit_curve(loop, 512)
    sites = loose_points(obj.data)
    row = {"points": len(loop), "sites": len(sites), "axis": 0.0, "normal": 0.0, "stem": 0.0, "shoulder": {},
           "dome": {}, "top": {}, "bottom": 0.0, "flat": 0, "rails": {}}
    # 0.8 мм по умолчанию — под камень шириной 6 мм; узкому камню крапан тоньше
    set_inputs(obj, {"Prong Diameter": 0.8 * stone / SIZE})

    for ts, tr, rs in RUNS:
        set_inputs(obj, {"Tip Scale": ts, "Tip Round": tr, "Rail Sharpness": rs})
        values = {name: get_input(obj, name) for name in ids(obj) if name not in ("Geometry", "Metal Material")}
        cage, result = evaluate(obj, False), evaluate(obj, True)
        tag = f"{label} TS {ts} TR {tr} RS {rs}"

        # a) оболочки замкнуты и наружу; их число
        for mesh_name, m in (("cage", cage), ("SubD", result)):
            parts = shells(m)
            if len(parts) != len(sites) + 2:
                errors.append(f"{tag}: {mesh_name} has {len(parts)} shells, expected {len(sites) + 2}")
            for s in parts:
                closed, vol = closed_volume(m["verts"], s["faces"])
                if not closed or vol <= 0.0:
                    errors.append(f"{tag}: {mesh_name} shell of {len(s['verts'])} verts closed={closed} volume {vol:.4f}")
        # b) вершины клетки
        expected = 12 * len(sites) + 2 * 4 * len(loop)
        if len(cage["verts"]) != expected:
            errors.append(f"{tag}: cage has {len(cage['verts'])} verts, expected {expected}")
        row["cage"] = len(cage["verts"])
        row["shells"] = len(shells(result))

        # c) крапана
        for p in measure_prongs(cage, result, sites, dense, values, profile=True):
            row["axis"] = max(row["axis"], p["axis"])
            row["normal"] = max(row["normal"], p["normal"])
            row["bottom"] = max(row["bottom"], p["bottom"], key=abs)
            row["flat"] = min(row["flat"] or p["flat"], p["flat"])
            row["top"][(ts, tr)] = max(row["top"].get((ts, tr), 0.0), p["top"], key=abs)
            if p["axis"] > TOL_POS:
                errors.append(f"{tag}: prong axis misses Pg/Pb by {p['axis']:.4f} mm")
            if p["normal"] > TOL_NORMAL:
                errors.append(f"{tag}: contour normal off by {p['normal']:.2f} deg")
            if abs(p["top"]) > TOL_POS:
                errors.append(f"{tag}: prong top off Prong Height by {p['top']:+.4f} mm")
            if abs(p["bottom"]) > TOL_POS or p["flat"] < CAP_VERTS:
                errors.append(f"{tag}: prong bottom off -Basket Height by {p['bottom']:+.5f} mm, "
                              f"{p['flat']} verts on its plane (cap has {CAP_VERTS})")
            if "stem" not in p:
                continue
            diameter = values["Prong Diameter"]
            if p["stem"] is None:
                row["short"] = True
            elif ts == 1.0:
                # диаметр — среднее четырёх ширин; по сторонам и диагоналям скруглённый квадрат даёт -+1.4 %
                stem = max((sum(ws) / 4.0 / diameter - 1.0 for ws in p["stem"]), key=abs) * 100.0
                spread = max((w / diameter - 1.0 for ws in p["stem"] for w in ws), key=abs) * 100.0
                row["stem"] = max(row["stem"], stem, key=abs)
                row["spread"] = max(row.get("spread", 0.0), spread, key=abs)
                if abs(stem) > TOL_DIAMETER:
                    errors.append(f"{tag}: stem diameter off by {stem:+.2f}%")
            else:
                means = [sum(ws) / 4.0 for ws in p["stem"]]
                if any(b > a + 1e-3 * diameter for a, b in zip(means, means[1:])):
                    errors.append(f"{tag}: stem does not taper monotonically: {[round(m, 4) for m in means]}")
            if ts != 1.0:
                shoulder = (p["shoulder"] / (diameter * ts) - 1.0) * 100.0
                row["shoulder"][tr] = max(row["shoulder"].get(tr, 0.0), shoulder, key=abs)
                if tr > 0.0 and abs(shoulder) > TOL_SHOULDER:
                    errors.append(f"{tag}: shoulder diameter off by {shoulder:+.2f}%")
            row["dome"][(ts, tr)] = p["dome"]
            if tr == 1.0 and abs(p["dome"] - 1.0) > TOL_DOME:
                errors.append(f"{tag}: dome height / tip radius = {p['dome']:.3f}")

        # d) рейки
        for name, r in measure_rails(result, outline, loop, dense, values).items():
            key = (name, rs)
            row["rails"][key] = {k: max(row["rails"].get(key, {}).get(k, 0.0), r[k], key=abs) for k in r}
            if r["missed"]:
                errors.append(f"{tag}: {name} rail missed by {r['missed']} rays")
            if abs(r["z"]) > TOL_POS:
                errors.append(f"{tag}: {name} rail z bound off by {r['z']:+.4f} mm")
            if rs == 1.0 and abs(r["outer"]) > tol_outer:
                errors.append(f"{tag}: {name} rail outer side off Rail Offset by {r['outer']:+.4f} mm "
                              f"(tolerance {tol_outer:.3f})")
    # сечение реек — одной строкой на рейку (ширина от Tip Scale / Tip Round не зависит)
    for name in ("top", "bottom"):
        for what in ("width", "height", "corner"):
            worst = max((r[what] for (n, _), r in row["rails"].items() if n == name), key=abs, default=0.0)
            if abs(worst) > TOL_SECTION:
                errors.append(f"{label}: {name} rail {what} off by {worst:+.2f}% (Rail Sharpness 0 / 0.5 / 1)")
    drop(gem)
    return row


def evaluate_count(obj) -> tuple[int, int]:
    m = evaluate(obj, True, 2)
    return len(m["verts"]), len(shells(m))


def check_normals(errors: list) -> None:
    """Нормаль контура у крапана (по оси клетки: Pg - site) на круге, овале и груше в 16 местах
    общего положения: против нормали предела петли, против настоящего контура (у круга —
    радиус от центра)."""
    for cut in ("ROUND", "OVAL", "PEAR"):
        for stretched in (False, True):
            gem = make_gem(cut, stretched)
            obj = gs.setup(gem, count=16, phase=0.31)
            mesh = gem.data
            outline = crown_outline([tuple(p.co) for p in mesh.vertices], [tuple(p.vertices) for p in mesh.polygons])
            xs, ys = [p.co.x for p in mesh.vertices], [p.co.y for p in mesh.vertices]
            center = ((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5)
            loop = go.gem_loop(gem)
            dense = go.limit_curve(loop, 512)
            corners = [(x, y) for x, y, c in loop if c]
            offset = get_input(obj, "Prong Offset")
            prongs = prong_cages(evaluate(obj, False))
            to_limit = to_girdle = 0.0
            for site in loose_points(obj.data):
                at0 = axis_at(nearest_prong(prongs, site), 0.0)
                gn = ((at0.x - site[0]) / offset, (at0.y - site[1]) / offset)
                to_limit = max(to_limit, angle(gn, limit_normal(site, dense)))
                if any(hypot(site[0] - x, site[1] - y) < 0.5 for x, y in corners):
                    continue
                truth = (site[0] - center[0], site[1] - center[1]) if cut == "ROUND" and not stretched \
                    else girdle_normal(outline, site)
                to_girdle = max(to_girdle, angle(gn, truth))
            what = "circle" if cut == "ROUND" and not stretched else "girdle"
            print(f"  normal {cut:5s} {'stretched' if stretched else 'default  '}: to limit {to_limit:.2f} deg, "
                  f"to {what} {to_girdle:.2f} deg")
            if to_limit > TOL_NORMAL or to_girdle > TOL_NORMAL:
                errors.append(f"normal {cut} {'stretched' if stretched else 'default'}: {to_limit:.2f} deg to limit, "
                              f"{to_girdle:.2f} deg to {what}")
            drop(gem)


def check_cases(errors: list) -> None:
    """e) выключатели и пустые случаи, f) ручная правка, g) повторный запуск, h) Apply на копии."""
    gem = make_gem("ROUND", False)
    obj = gs.setup(gem)
    sites = loose_points(obj.data)
    cases = [({}, len(sites) + 2), ({"Prongs": False}, 2), ({"Top Rail": False}, len(sites) + 1),
             ({"Bottom Rail": False}, len(sites) + 1), ({"Top Rail": False, "Bottom Rail": False}, len(sites)),
             ({"Prongs": False, "Top Rail": False, "Bottom Rail": False}, 0)]
    for values, expected in cases:
        set_inputs(obj, {"Prongs": True, "Top Rail": True, "Bottom Rail": True})
        set_inputs(obj, values)
        _, count = evaluate_count(obj)
        print(f"  toggles {values or 'default'}: {count} shells")
        if count != expected:
            errors.append(f"toggles {values}: {count} shells, expected {expected}")
    set_inputs(obj, {"Prongs": True, "Top Rail": True, "Bottom Rail": True})
    gs.setup(gem, count=0)
    _, count = evaluate_count(obj)
    print(f"  no sites: {count} shells")
    if count != 2:
        errors.append(f"no sites: {count} shells, expected 2 rails")
    for name, verts, edges in (("no loop", [(1.0, 0.0, 0.0), (0.0, 2.0, 0.0), (-1.5, 0.0, 0.0)], []),
                               ("empty mesh", [], [])):
        mesh = obj.data
        mesh.clear_geometry()
        mesh.from_pydata(verts, edges, [])
        mesh.update()
        count, _ = evaluate_count(obj)
        print(f"  {name}: {count} verts")
        if count:
            errors.append(f"{name}: output has {count} verts, expected empty")

    # f) ручная правка: сдвинуть место по контуру, увести с контура, добавить вершину
    gs.setup(gem, count=4)
    loop = go.gem_loop(gem)
    dense = go.limit_curve(loop, 512)
    offset = get_input(obj, "Prong Offset")
    mesh = obj.data
    loose = [v.index for v in mesh.vertices if v.index >= len(loop)]

    def on_curve(deg):
        """Точка предела на полярном угле deg от центра камня."""
        x, y, *_ = min(dense, key=lambda s: abs((degrees(atan2(s[1], s[0])) - deg + 180.0) % 360.0 - 180.0))
        return x, y

    moved = on_curve(20.0)
    off_curve = (mesh.vertices[loose[1]].co.x * 1.04, mesh.vertices[loose[1]].co.y * 1.04)
    added = on_curve(200.0)
    mesh.vertices[loose[0]].co = (*moved, 0.0)
    mesh.vertices[loose[1]].co = (*off_curve, 0.0)
    mesh.vertices.add(1)
    mesh.vertices[-1].co = (*added, 0.0)
    mesh.update()
    prongs = prong_cages(evaluate(obj, False))
    print(f"  edit: {len(prongs)} prongs after adding a vertex")
    if len(prongs) != 5:
        errors.append(f"edit: {len(prongs)} prongs, expected 5")
    for name, site in (("moved along", moved), ("moved off", off_curve), ("added", added)):
        n = limit_normal(site, dense)
        at0 = axis_at(nearest_prong(prongs, site), 0.0)
        miss = hypot(at0.x - site[0] - n[0] * offset, at0.y - site[1] - n[1] * offset)
        print(f"  edit {name}: axis misses site + n * offset by {miss:.5f} mm")
        if miss > TOL_POS:
            errors.append(f"edit {name}: axis misses site + n * offset by {miss:.4f} mm")

    # g) повторный запуск: значения на модификаторе целы, ничего не задвоилось;
    #    сокет, которого не было, получает default (в 5.2 — 0 без ensure_interface)
    values = {"Prong Diameter": 0.7, "Rail Width": 0.5, "Top Rail": False, "Tip Round": 0.3,
              "Rail Sharpness": 0.8, "Prong Height": 0.9, "Basket Height": 1.7}
    set_inputs(obj, values)
    ng = bpy.data.node_groups[gs.GROUP_NAME]
    ng.interface.remove(next(it for it in ng.interface.items_tree if it.item_type == "SOCKET" and it.name == "Rail Drop"))
    gs.build_group()
    gs.setup(gem, count=6)
    kept = {k: get_input(obj, k) for k in values}
    bad = {k: v for k, v in kept.items() if abs(float(v) - float(values[k])) > 1e-6}
    nodes = sum(1 for m in obj.modifiers if m.type == "NODES")
    subs = sum(1 for m in obj.modifiers if m.type == "SUBSURF")
    twins = [o.name for o in bpy.data.objects if o.name.startswith(gem.name + " Setting")]
    groups = [g.name for g in bpy.data.node_groups if g.name.startswith(gs.GROUP_NAME)]
    drop_value = get_input(obj, "Rail Drop")
    _, count = evaluate_count(obj)
    print(f"  rerun: changed {bad or 'none'}, modifiers {nodes}+{subs}, objects {twins}, groups {groups}, "
          f"re-added Rail Drop = {drop_value:.2f}, {count} shells")
    if bad or nodes != 1 or subs != 1 or len(twins) != 1 or len(groups) != 1:
        errors.append(f"rerun: values {bad}, modifiers {nodes}+{subs}, objects {twins}, groups {groups}")
    if abs(drop_value - 0.2) > 1e-6:
        errors.append(f"rerun: re-added socket got {drop_value}, expected default 0.2")
    if count != 6 + 1:
        errors.append(f"rerun: {count} shells, expected 6 prongs + 1 rail")

    # h) Apply GN на копии: клетка с тем же числом вершин, SubD работает
    cage_count = len(evaluate(obj, False)["verts"])
    result_count, result_shells = evaluate_count(obj)
    copy = obj.copy()
    copy.data = obj.data.copy()
    bpy.context.scene.collection.objects.link(copy)
    with bpy.context.temp_override(object=copy, active_object=copy, selected_objects=[copy]):
        bpy.ops.object.modifier_apply(modifier=modifier(copy, "NODES").name)
    applied = len(copy.data.vertices)
    has_crease = "crease_edge" in copy.data.attributes
    left = [m.type for m in copy.modifiers]
    after, after_shells = evaluate_count(copy)
    m = evaluate(copy, True, 2)
    bad_shells = [s for s in shells(m) if not (lambda c: c[0] and c[1] > 0)(closed_volume(m["verts"], s["faces"]))]
    print(f"  apply: cage {applied}/{cage_count} verts, crease_edge {has_crease}, modifiers left {left}, "
          f"SubD {after}/{result_count} verts, {after_shells}/{result_shells} shells, bad shells {len(bad_shells)}")
    if applied != cage_count or not has_crease or left != ["SUBSURF"] or after != result_count \
            or after_shells != result_shells or bad_shells:
        errors.append("apply: applied cage differs from the live result")
    drop(copy)
    drop(gem)


def run(preview: bool) -> list[str]:
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    errors = []
    print(f"SubD level {LEVEL} for measuring; mm unless %; max over default and stretched x{STRETCH} stone; "
          f"Prong Diameter = 0.8 * stone width / {SIZE:g}")
    print("cut        pts site cage | axis   normal | top TS1 TR0/.5/1        TS.8 TR0/.5/1        bottom cap  | "
          "stem% mean/side  shoulder% TR0/.5/1    dome H/R TR0/.5/1 TS.8 | rail w% top/bottom  h%    outer RS1     corner%  z")
    for cut in gems._CUT_SPECS:
        rows = [check_cut(cut, stretched, errors) for stretched in (False, True)]
        d = rows[0]

        def worst(get):
            return max((get(r) for r in rows), key=abs)

        tops = [worst(lambda r, k=k: r["top"][k]) for k in ((1.0, 0.0), (1.0, 0.5), (1.0, 1.0),
                                                           (0.8, 0.0), (0.8, 0.5), (0.8, 1.0))]
        shoulder = [worst(lambda r, k=k: r["shoulder"].get(k, 0.0)) for k in (0.0, 0.5, 1.0)]
        dome = [worst(lambda r, k=k: r["dome"].get(k, 0.0) - 1.0) + 1.0
                for k in ((1.0, 0.0), (1.0, 0.5), (1.0, 1.0), (0.8, 1.0))]
        t = {key: {what: worst(lambda r, key=key, what=what: r["rails"].get(key, {}).get(what, 0.0))
                   for what in ("width", "height", "outer", "corner", "z")}
             for key in [(n, rs) for n in ("top", "bottom") for rs in (0.0, 0.5, 1.0)]}

        def over(name, what):
            return max((t[(name, rs)][what] for rs in (0.0, 0.5, 1.0)), key=abs)

        print(f"{cut:10s} {d['points']:3d} {d['sites']:3d} {d['cage']:4d} | "
              f"{worst(lambda r: r['axis']):.4f} {worst(lambda r: r['normal']):5.2f}  | "
              f"{tops[0]:+.4f}/{tops[1]:+.4f}/{tops[2]:+.4f} {tops[3]:+.4f}/{tops[4]:+.4f}/{tops[5]:+.4f} "
              f"{worst(lambda r: r['bottom']):+.6f} {min(r['flat'] for r in rows):4d} | "
              f"{'  short    ' if any(r.get('short') for r in rows) else ''}"
              f"{worst(lambda r: r['stem']):+5.2f}/{worst(lambda r: r.get('spread', 0.0)):+5.2f}  "
              f"{shoulder[0]:+5.2f}/{shoulder[1]:+5.2f}/{shoulder[2]:+5.2f}   "
              f"{dome[0]:.3f}/{dome[1]:.3f}/{dome[2]:.3f} {dome[3]:.3f} | "
              f"{over('top', 'width'):+5.2f}/{over('bottom', 'width'):+5.2f}  "
              f"{max(over('top', 'height'), over('bottom', 'height'), key=abs):+5.2f}  "
              f"{t[('top', 1.0)]['outer']:+.4f}/{t[('bottom', 1.0)]['outer']:+.4f}  "
              f"{max(over('top', 'corner'), over('bottom', 'corner'), key=abs):+5.2f}  "
              f"{max((t[k]['z'] for k in t), key=abs):+.4f}", flush=True)
    print("normals:")
    check_normals(errors)
    print("cases:")
    check_cases(errors)
    if preview:
        render_sheet()
    return errors


# --- лист превью ------------------------------------------------------------------

def render_sheet() -> None:
    """Вид 3/4, ортографический: сверху камень + каст после SubD, снизу каст клеткой
    (SubD выключен, рёбра клетки — тёмный каркас). Workbench, свет студии, цвет объекта."""
    scene = bpy.context.scene
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    camera = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    scene.collection.objects.link(camera)
    camera.rotation_euler = Euler((radians(74.0), 0.0, radians(30.0)))
    bpy.context.view_layer.update()
    right, up = camera.matrix_world.col[0].xyz, camera.matrix_world.col[1].xyz
    view = -camera.matrix_world.col[2].xyz
    gap = 12.5
    cols = len(PREVIEW_CUTS)
    cells = []
    for index, cut in enumerate(PREVIEW_CUTS):
        for row in (0, 1):
            cell = right * (index - (cols - 1) * 0.5) * gap + up * (0.5 - row) * gap * 0.62
            gem = make_gem(cut, False, PREVIEW_WIDTH / gems._CUT_SPECS[cut].base_width)
            gem.name = f"{cut} {row}"
            gem.location = cell
            gem.color = (0.72, 0.84, 1.0, 1.0)
            cast = gs.setup(gem)
            cast.color = (0.86, 0.66, 0.24, 1.0)
            set_inputs(cast, {"Tip Round": 1.0})
            if row:
                modifier(cast, "SUBSURF").show_render = modifier(cast, "SUBSURF").show_viewport = False
                cast.update_tag()
                depsgraph = bpy.context.evaluated_depsgraph_get()
                depsgraph.update()
                wire = bpy.data.objects.new(f"{cut} wire", bpy.data.meshes.new_from_object(cast.evaluated_get(depsgraph)))
                scene.collection.objects.link(wire)
                wire.parent = gem
                wire.color = (0.12, 0.12, 0.14, 1.0)
                wf = wire.modifiers.new("Wire", "WIREFRAME")
                wf.thickness = 0.05
                wf.offset = 0.0              # по умолчанию -1: каркас уходит внутрь граней и не виден
                wf.use_even_offset = False
                for p in wire.data.polygons:
                    p.use_smooth = False
            cells.append((cut, row, cell, gem, cast))
    # подписи: огранка — над верхним рядом, число точек клетки — под нижним
    depsgraph = bpy.context.evaluated_depsgraph_get()
    depsgraph.update()
    low, high = {}, {}
    for cut, row, cell, gem, cast in cells:
        for obj in (gem, cast):
            ev = obj.evaluated_get(depsgraph)
            for corner in ev.bound_box:
                lift = (ev.matrix_world @ Vector(corner) - cell).dot(up)
                low[row] = min(low.get(row, 0.0), lift)
                high[row] = max(high.get(row, 0.0), lift)
    for cut, row, cell, gem, cast in cells:
        text = bpy.data.curves.new(f"{cut} label {row}", "FONT")
        sites = len(loose_points(cast.data))
        loop_points = sum(1 for e in cast.data.edges)
        text.body = cut if not row else f"{cut} cage: {12 * sites + 8 * loop_points} points"
        text.size = 0.6
        text.align_x = "CENTER"
        label = bpy.data.objects.new(f"{cut} label {row}", text)
        scene.collection.objects.link(label)
        label.location = cell + up * ((high[row] + 0.35) if row == 0 else (low[row] - 0.75)) - view * 6.0
        label.rotation_euler = camera.rotation_euler
        label.color = (0.0, 0.0, 0.0, 1.0)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = cols * gap
    camera.location = -view * 40.0 - up * gap * 0.1
    scene.camera = camera
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 2400
    scene.render.resolution_y = round(2400 * 2 * 0.62 / cols * 1.24)
    scene.render.resolution_percentage = 100
    scene.display.render_aa = "16"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.show_cavity = True
    scene.display.shading.background_type = "VIEWPORT"
    scene.display.shading.background_color = (1.0, 1.0, 1.0)
    scene.world = scene.world or bpy.data.worlds.new("World")
    scene.world.color = (1.0, 1.0, 1.0)
    scene.view_settings.view_transform = "Standard"
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(PREVIEW)
    scene.render.image_settings.file_format = "PNG"
    bpy.ops.render.render(write_still=True)
    print(f"preview: {PREVIEW}")


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    errors = run("--preview" in args)
    for error in errors:
        print("FAIL", error)
    print("GEM_SETTING_TEST", "failed" if errors else "passed")
    if errors:
        sys.exit(1)


try:
    main()
except SystemExit:
    raise
except Exception:
    traceback.print_exc()
    sys.exit(1)
