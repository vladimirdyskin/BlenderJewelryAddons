# SPDX-License-Identifier: GPL-3.0-or-later

"""Петля рундиста (jewel_tools/gem_outline.py) против настоящего SubD Blender.

Фоновый Blender:
  Blender --factory-startup --background --python tools/test_gem_outline.py [-- --preview | --table]
  --preview  ещё и лист dist/previews/gem_outline_sheet.png
  --table    пересчитать gem_outline.CUT_LOOPS по шаблонам gems.blend и напечатать (без проверки)
Код выхода 1 — проверка не прошла.
"""

from __future__ import annotations

from math import acos, copysign, cos, degrees, hypot, pi, sin
from pathlib import Path
import sys
import traceback

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from jewelry_suite import gem_outline as go, gems  # gems — parametric_gems

TOLERANCE = 0.5          # допуск, % ширины камня (меньшего габарита XY)
SIZE = 6.0               # мм на единицу шаблона
STRETCH = 1.3            # растянутый камень: длина (Y) x 1.3
SHIFT = (0.7, -0.4)      # и меш сдвинут — положение петли берётся из габарита
LEVELS = 4
STEPS = 2 ** LEVELS      # узлов SubD на пролёт петли
TUBE = 0.04              # полусечение трубки, доля ширины
PREVIEW = ROOT / "dist" / "previews" / "gem_outline_sheet.png"


# --- геометрия ---------------------------------------------------------------

def walk(links: dict) -> list:
    """Обход простого цикла по словарю соседей."""
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
    """Настоящий контур рундиста сверху: граница граней короны (нормаль вверх) в проекции на XY.
    Вертикальные грани рундиста не годятся: у сердца рундист местами нулевой высоты."""
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
    for p in points:  # повторы (рундист нулевой высоты) и точки на прямой
        if not clean or hypot(p[0] - clean[-1][0], p[1] - clean[-1][1]) > 1e-6 * size:
            clean.append(p)
    clean = [p for i, p in enumerate(clean) if abs(go._turn(clean[i - 1], p, clean[(i + 1) % len(clean)])) > 1e-4]
    return clean if go._area2(clean) > 0.0 else clean[::-1]


def box(points):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def distance(p, poly) -> float:
    return min(go._segment_distance(p, poly[i - 1], poly[i]) for i in range(len(poly)))


def deviation(curve, outline) -> float:
    """Двустороннее отклонение замкнутых ломаных: точки одной до другой и обратно."""
    return max(max(distance(p, outline) for p in curve), max(distance(q, curve) for q in outline))


def mirror_error(points, axis: int, center: float) -> float:
    """Наибольшее расстояние от зеркального образа точки до ближайшей точки набора с тем же
    флагом угла (у контура флагов нет)."""
    worst = 0.0
    for p in points:
        q = list(p)
        q[axis] = 2.0 * center - q[axis]
        same = [r for r in points if r[2:] == p[2:]]
        worst = max(worst, min(hypot(r[0] - q[0], r[1] - q[1]) for r in same))
    return worst


# --- Blender ------------------------------------------------------------------

def add_object(name: str, mesh) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def subdivided(obj, read, quality: int = 3):
    """Модификатор Subdivision Surface (Catmull-Clark, предел; quality 3 — по умолчанию)
    и чтение вычисленного меша."""
    md = obj.modifiers.new("SubD", "SUBSURF")
    md.levels = md.render_levels = LEVELS
    md.use_limit_surface = True
    md.quality = quality
    md.boundary_smooth = "ALL"
    md.uv_smooth = "NONE"
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        return read(mesh)
    finally:
        evaluated.to_mesh_clear()
        drop(obj)


def limit_boundary(loop, quality: int = 3) -> list[tuple[float, float]]:
    """Предел SubD петли: одна грань-n-угольник, crease_vert = corner, граница результата.
    У одной грани её вершины — валентности 2 на любом уровне, OpenSubdiv считает предел около
    них приближённо (точнее с ростом quality)."""
    mesh = bpy.data.meshes.new("Loop")
    mesh.from_pydata([(x, y, 0.0) for x, y, _ in loop], [], [tuple(range(len(loop)))])
    mesh.attributes.new("crease_vert", "FLOAT", "POINT").data.foreach_set(
        "value", [1.0 if corner else 0.0 for *_, corner in loop])

    def read(m):
        uses = {}
        for poly in m.polygons:
            for key in poly.edge_keys:
                uses[key] = uses.get(key, 0) + 1
        links = {}
        for (a, b), count in uses.items():
            if count == 1:
                links.setdefault(a, []).append(b)
                links.setdefault(b, []).append(a)
        return [tuple(m.vertices[i].co)[:2] for i in walk(links)]

    return subdivided(add_object("Loop", mesh), read, quality)


def tube_axis(loop, width: float) -> list[tuple[float, float]]:
    """Трубка-клетка: петля x квадратный профиль (наружу/внутрь, вверх/вниз), рёбра колец
    в углах — crease_edge = 1. Центры сечений вычисленной трубки — по UV-параметру вдоль петли
    (UV без сглаживания: узел сетки получает ровно k/16 пролёта)."""
    n, a = len(loop), TUBE * width
    verts = []
    for i, (x, y, _) in enumerate(loop):
        normals = []
        for p, q in ((loop[i - 1], loop[i]), (loop[i], loop[(i + 1) % n])):
            ex, ey = q[0] - p[0], q[1] - p[1]
            length = hypot(ex, ey)
            normals.append((ey / length, -ex / length))
        nx, ny = normals[0][0] + normals[1][0], normals[0][1] + normals[1][1]
        length = hypot(nx, ny)
        nx, ny = nx / length, ny / length
        verts += [(x + nx * o, y + ny * o, z) for o, z in ((a, a), (-a, a), (-a, -a), (a, -a))]
    faces, uvs = [], []
    for i in range(n):
        for j in range(4):
            faces.append((4 * i + j, 4 * ((i + 1) % n) + j, 4 * ((i + 1) % n) + (j + 1) % 4, 4 * i + (j + 1) % 4))
            uvs += [i / n, j / 4, (i + 1) / n, j / 4, (i + 1) / n, (j + 1) / 4, i / n, (j + 1) / 4]
    mesh = bpy.data.meshes.new("Tube")
    mesh.from_pydata(verts, [], faces)
    mesh.uv_layers.new(name="UV").data.foreach_set("uv", uvs)
    mesh.attributes.new("crease_edge", "FLOAT", "EDGE").data.foreach_set("value", [
        1.0 if e.vertices[0] // 4 == e.vertices[1] // 4 and loop[e.vertices[0] // 4][2] else 0.0
        for e in mesh.edges])

    def read(m):
        rings = {}
        uv = m.uv_layers[0].data
        for index, corner in enumerate(m.loops):
            k = round(uv[index].uv[0] * n * STEPS) % (n * STEPS)
            rings.setdefault(k, set()).add(corner.vertex_index)
        assert sorted(rings) == list(range(n * STEPS)), "tube rings by UV are broken"
        assert all(len(r) == 4 * STEPS for r in rings.values()), "tube ring size is not 4 x 16"
        return [(sum(m.vertices[v].co.x for v in rings[k]) / len(rings[k]),
                 sum(m.vertices[v].co.y for v in rings[k]) / len(rings[k])) for k in range(n * STEPS)]

    return subdivided(add_object("Tube", mesh), read)


def drop(obj) -> None:
    mesh = obj.data
    bpy.data.objects.remove(obj)
    bpy.data.meshes.remove(mesh)


def make_gem(cut: str, spec, stretched: bool) -> bpy.types.Object:
    length = SIZE * spec.base_length * (STRETCH if stretched else 1.0)
    width = SIZE * spec.base_width
    verts, faces = gems._cut_geometry(cut, length, width, spec.girdle_percent, spec.crown_percent, spec.pavilion_percent)
    if stretched:
        verts = [(x + SHIFT[0], y + SHIFT[1], z) for x, y, z in verts]
    mesh = bpy.data.meshes.new(cut)
    mesh.from_pydata(verts, [], faces)
    obj = add_object(cut, mesh)
    obj["gem"] = {"cut": cut.title() if stretched else cut, "stone": "DIAMOND"}  # регистр не важен
    return obj


# --- проверка -------------------------------------------------------------------

def measure(obj) -> dict:
    mesh = obj.data
    outline = crown_outline([tuple(v.co) for v in mesh.vertices], [tuple(p.vertices) for p in mesh.polygons])
    x0, y0, x1, y1 = box([tuple(v.co) for v in mesh.vertices])
    width, center = min(x1 - x0, y1 - y0), ((x0 + x1) * 0.5, (y0 + y1) * 0.5)
    loop = go.gem_loop(obj)
    limit = limit_boundary(loop)
    exact = limit_boundary(loop, 10)
    axis = tube_axis(loop, width)
    n = len(loop)
    corner_turns, smooth_turn = [], 0.0
    for k in range(len(axis)):
        turn = abs(degrees(go._turn(axis[k - 1], axis[k], axis[(k + 1) % len(axis)])))
        i = k // STEPS
        if k % STEPS == 0 and loop[i][2]:
            corner_turns.append((turn, abs(degrees(go._turn(loop[i - 1], loop[i], loop[(i + 1) % n])))))
        else:
            smooth_turn = max(smooth_turn, turn)
    symmetry = {}
    for axis_index, name in ((0, "X"), (1, "Y")):
        if mirror_error(outline, axis_index, center[axis_index]) <= 1e-3 * width:
            symmetry[name] = mirror_error(loop, axis_index, center[axis_index]) / width
    # go.limit_curve с тем же шагом, что у SubD: точки против центров сечений трубки (те же
    # параметры k / STEPS пролёта), касательная против хорды соседних центров (в острой
    # вершине — биссектрисы двух хорд)
    curve = go.limit_curve(loop, STEPS)
    curve_axis = max(hypot(c[0] - a[0], c[1] - a[1]) for c, a in zip(curve, axis))
    tangent = 0.0
    for k, (_, _, tx, ty) in enumerate(curve):
        a, b, c = axis[k - 1], axis[k], axis[(k + 1) % len(axis)]
        if k % STEPS == 0 and loop[k // STEPS][2]:
            u, v = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
            lu, lv = hypot(*u), hypot(*v)
            chord = (u[0] / lu + v[0] / lv, u[1] / lu + v[1] / lv)
        else:
            chord = (c[0] - a[0], c[1] - a[1])
        cos_t = (chord[0] * tx + chord[1] * ty) / hypot(*chord)
        tangent = max(tangent, degrees(acos(max(-1.0, min(1.0, cos_t)))))
    return {
        "outline": outline, "loop": loop, "limit": limit, "axis": axis, "width": width,
        "points": n, "corners": sum(1 for p in loop if p[2]),
        "edge": 100.0 * deviation(limit, outline) / width,
        "exact": 100.0 * deviation(exact, outline) / width,
        "axis_dev": 100.0 * deviation(axis, outline) / width,
        "axis_edge": 100.0 * deviation(axis, limit) / width,
        "axis_exact": 100.0 * deviation(axis, exact) / width,
        "corner_turns": corner_turns, "smooth_turn": smooth_turn,
        "ccw": go._area2(loop) > 0.0,
        "first": go._canonical(loop, center)[0] == loop[0],
        "symmetry": symmetry,
        "curve_axis": 100.0 * curve_axis / width, "tangent": tangent,
    }


def check(cut: str, default: dict, stretched: dict) -> list[str]:
    errors = []
    for label, r in (("default", default), ("stretched", stretched)):
        if r["edge"] > TOLERANCE:
            errors.append(f"{cut} {label}: limit deviates {r['edge']:.3f}% > {TOLERANCE}%")
        if r["axis_dev"] > TOLERANCE:
            errors.append(f"{cut} {label}: tube axis deviates {r['axis_dev']:.3f}%")
        if r["axis_edge"] > TOLERANCE:
            errors.append(f"{cut} {label}: tube axis is off the boundary limit by {r['axis_edge']:.3f}%")
        if r["axis_exact"] > 0.001:
            errors.append(f"{cut} {label}: tube axis is off the quality 10 boundary by {r['axis_exact']:.4f}%")
        for measured, expected in r["corner_turns"]:
            if abs(measured - expected) > 2.0:
                errors.append(f"{cut} {label}: corner turn {measured:.1f} deg, control polygon {expected:.1f}")
        if not r["ccw"] or not r["first"]:
            errors.append(f"{cut} {label}: loop is not CCW from the smallest polar angle")
        for name, error in r["symmetry"].items():
            if error > 1e-5:
                errors.append(f"{cut} {label}: loop is not mirror-symmetric in {name} ({error:.1e} of width)")
        if r["curve_axis"] > 0.001:
            errors.append(f"{cut} {label}: limit_curve is off the tube axis by {r['curve_axis']:.4f}%")
        if r["tangent"] > 1.0:
            errors.append(f"{cut} {label}: limit_curve tangent is off the tube axis chord by {r['tangent']:.2f} deg")
    if (default["points"], default["corners"]) != (stretched["points"], stretched["corners"]):
        errors.append(f"{cut}: point count changes with proportions")
    return errors


def run(preview: bool) -> list[str]:
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    errors, sheet = [], []
    print(f"% of width; d/s = default / stretched (length x{STRETCH}); edge = n-gon SubD boundary (q = quality),"
          " axis = tube section centers")
    print(f"{'cut':10s} pts crn  edge q3 d/s     edge q10 d/s    axis d/s        axis-edge q3/q10   "
          "corner deg meas/ctrl  smooth deg  sym  limit_curve %/deg")
    for cut, spec in gems._CUT_SPECS.items():
        results = []
        for stretched in (False, True):
            obj = make_gem(cut, spec, stretched)
            results.append(measure(obj))
            drop(obj)
        d, s = results
        turns = d["corner_turns"] + s["corner_turns"]
        worst = max(turns, key=lambda t: abs(t[0] - t[1])) if turns else None
        corner = f"{worst[0]:5.1f}/{worst[1]:5.1f}" if worst else "    -      "
        sym = "".join(sorted(d["symmetry"])) or "-"
        print(f"{cut:10s} {d['points']:3d} {d['corners']:3d}  {d['edge']:5.3f}/{s['edge']:5.3f}    "
              f"{d['exact']:5.3f}/{s['exact']:5.3f}    {d['axis_dev']:5.3f}/{s['axis_dev']:5.3f}    "
              f"{max(d['axis_edge'], s['axis_edge']):6.3f}/{max(d['axis_exact'], s['axis_exact']):.5f}   "
              f"{corner:>19s}  {max(d['smooth_turn'], s['smooth_turn']):10.1f}  {sym:3s}  "
              f"{max(d['curve_axis'], s['curve_axis']):.5f}/{max(d['tangent'], s['tangent']):.2f}")
        errors += check(cut, d, s)
        sheet.append((cut, d))

    print("fallback (convex hull, unknown cut):")
    for cut, spec in gems._CUT_SPECS.items():
        obj = make_gem(cut, spec, False)
        obj["gem"] = {"cut": "UNKNOWN"}
        r = measure(obj)
        drop(obj)
        print(f"  {cut:10s} pts {r['points']:2d} corners {r['corners']} edge {r['edge']:.3f}%")
        if not r["ccw"] or not r["first"]:
            errors.append(f"{cut} fallback: loop is not CCW from the smallest polar angle")

    if preview:
        render_sheet(sheet)
    return errors


# --- таблица CUT_LOOPS ----------------------------------------------------------

def print_table() -> None:
    def num(v):  # округление модуля: зеркальные пары остаются равными
        return repr(copysign(round(abs(v), 6), v) + 0.0)

    lines = ["CUT_LOOPS = {"]
    for cut, spec in gems._CUT_SPECS.items():
        verts, faces = gems._load_template(spec.mesh_name)
        outline = crown_outline(verts, faces)
        k, count = go.CUT_SPECS[cut]
        turns = [abs(go._turn(outline[i - 1], p, outline[(i + 1) % len(outline)])) for i, p in enumerate(outline)]
        corners = sorted(sorted(range(len(outline)), key=lambda i: -turns[i])[:k])
        loop = go.fit_loop(outline, corners, count)
        lines.append(f'    "{cut}": (({", ".join(num(v) for v in box(verts))}), (')
        lines += [f"        ({num(x)}, {num(y)}, {corner})," for x, y, corner in loop]
        lines.append("    )),")
        print(f"fitted {cut}: {len(loop)} points", flush=True)
    lines.append("}")
    print("\n".join(lines))


# --- лист превью ------------------------------------------------------------------

def render_sheet(items) -> None:
    """Вид сверху: контур рундиста (серый), предел SubD (оранжевый), петля (синие рёбра и
    точки, острые — красные квадраты), подпись. Workbench, плоский свет, цвет объекта."""
    scene = bpy.context.scene
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    cols, cell, gap = 6, 1.0, 1.55
    rows = (len(items) + cols - 1) // cols

    def poly(name, points, radius, color, z):
        curve = bpy.data.curves.new(name, "CURVE")
        curve.dimensions = "3D"
        curve.bevel_depth = radius
        curve.bevel_resolution = 2
        spline = curve.splines.new("POLY")
        spline.points.add(len(points) - 1)
        spline.points.foreach_set("co", [c for x, y in points for c in (x, y, z, 1.0)])
        spline.use_cyclic_u = True
        add_object(name, curve).color = color

    def marker(name, center, radius, sides, color, z):
        mesh = bpy.data.meshes.new(name)
        turn = 0.25 if sides == 4 else 0.0
        verts = [(center[0] + radius * cos(2 * pi * (k / sides + turn / 2)),
                  center[1] + radius * sin(2 * pi * (k / sides + turn / 2)), z) for k in range(sides)]
        mesh.from_pydata(verts, [], [tuple(range(sides))])
        add_object(name, mesh).color = color

    for index, (cut, r) in enumerate(items):
        ox = (index % cols - (cols - 1) * 0.5) * gap
        oy = -(index // cols) * gap * 1.12
        x0, y0, x1, y1 = box(r["outline"])
        scale = cell / max(x1 - x0, y1 - y0)
        cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5

        def to_sheet(p):
            return (ox + (p[0] - cx) * scale, oy + (p[1] - cy) * scale)

        poly(f"{cut} outline", [to_sheet(p) for p in r["outline"]], 0.016, (0.5, 0.5, 0.5, 1), 0.0)
        poly(f"{cut} limit", [to_sheet(p) for p in r["limit"]], 0.0055, (1.0, 0.45, 0.0, 1), 0.02)
        poly(f"{cut} loop", [to_sheet(p) for p in r["loop"]], 0.0022, (0.1, 0.3, 0.9, 1), 0.04)
        for k, p in enumerate(r["loop"]):
            if p[2]:
                marker(f"{cut} corner {k}", to_sheet(p), 0.034, 4, (0.85, 0.05, 0.05, 1), 0.06)
            else:
                marker(f"{cut} point {k}", to_sheet(p), 0.022, 16, (0.1, 0.3, 0.9, 1), 0.06)
        text = bpy.data.curves.new(f"{cut} label", "FONT")
        text.body = f"{cut}  {r['points']} pts / {r['corners']} sharp  {r['edge']:.2f}%"
        text.size = 0.085
        text.align_x = "CENTER"
        label = add_object(f"{cut} label", text)
        label.location = (ox, oy - 0.68 * cell, 0.0)
        label.color = (0, 0, 0, 1)

    legend = bpy.data.curves.new("legend", "FONT")  # в свободной ячейке
    legend.body = ("grey: girdle outline of the gem\norange: SubD limit (n-gon, level 4)\n"
                   "blue: control loop, smooth points\nred: sharp points (crease 1)\n% = deviation of width")
    legend.size = 0.08
    text = add_object("legend", legend)
    text.location = ((len(items) % cols - (cols - 1) * 0.5) * gap - 0.62, -(len(items) // cols) * gap * 1.12 + 0.25, 0.0)
    text.color = (0, 0, 0, 1)

    camera = add_object("Camera", bpy.data.cameras.new("Camera"))
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = cols * gap
    camera.location = (0.0, -(rows - 1) * gap * 1.12 * 0.5 - 0.06, 10.0)
    scene.camera = camera
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 2400
    scene.render.resolution_y = round(2400 * rows * gap * 1.12 / (cols * gap))
    scene.render.resolution_percentage = 100
    scene.display.render_aa = "16"
    scene.display.shading.light = "FLAT"
    scene.display.shading.color_type = "OBJECT"
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
    if "--table" in args:
        print_table()
        return
    errors = run("--preview" in args)
    for error in errors:
        print("FAIL", error)
    print("GEM_OUTLINE_TEST", "failed" if errors else "passed")
    if errors:
        sys.exit(1)


try:
    main()
except SystemExit:
    raise
except Exception:
    traceback.print_exc()
    sys.exit(1)
