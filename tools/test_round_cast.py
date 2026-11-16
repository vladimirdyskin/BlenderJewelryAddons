"""My_Round_Cast (tools/gn_round_cast_build.py): сравнение с RoundWithProngs и замеры новой логики.

Фоновый Blender на КОПИИ библиотеки (файл не сохраняется):
  Blender --factory-startup --background --python tools/test_round_cast.py -- <копия MyAssets.blend> [--preview]
  --preview  ещё и лист dist/previews/round_cast_sizes.png
Код выхода 1 — проверка не прошла.

1. Сравнение: значения RoundWithProngs вычисляются из наших так, чтобы геометрия совпадала.
   Поверхность — точки (вершины + центры граней) одной сетки до BVH другой и обратно, металл без
   камня; зона купола (выше основания купола по оси крапана) отдельно. Его прорезь — куб 4 x 4,
   поэтому камни крупнее 3 мм не сравниваются.
2. Замеры лучами по нашей сетке (BoolCutter выкл — крапана и каст отдельными оболочками).
"""

from math import atan2, cos, pi, sin, tan
from pathlib import Path
import sys
import traceback

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "tools" / "gn_round_cast_build.py"
PREVIEW = ROOT / "dist" / "previews" / "round_cast_sizes.png"
REF = "RoundWithProngs"
NEW = "Round Cast"
TOL = 0.02          # мм вне куполов
TOL_DOME = 0.06     # мм в зоне купола
TOL_M = 0.01        # прямые замеры
SIZES = (1.0, 2.0, 3.0, 5.0, 6.5)
SET_CASES = ((1.0, 0.4), (2.0, 0.5), (3.0, 0.6), (5.0, 0.8), (6.5, 0.9))   # ø камня, ø крапана
GIA_COVER = (0.33, 0.50)   # контакт крапана — доля пути по короне
UP = Vector((0.0, 0.0, 1.0))


def load_build():
    ns = {"__name__": "round_cast_build"}
    exec(compile(BUILD.read_text(), str(BUILD), "exec"), ns)
    return ns


def inputs(md):
    """{(панель, имя): identifier}"""
    return {(it.parent.name or None, it.name): it.identifier for it in md.node_group.interface.items_tree
            if it.item_type == "SOCKET" and it.in_out == "INPUT" and it.socket_type != "NodeSocketGeometry"}


def get(ob, key):
    md = ob.modifiers[0]
    return getattr(md.properties.inputs, inputs(md)[key]).value


def put(ob, key, value):
    md = ob.modifiers[0]
    getattr(md.properties.inputs, inputs(md)[key]).value = value
    ob.update_tag()


def evaluate(ob):
    """Вершины, треугольники поверхности, грани, атрибуты. Внутренние грани (все рёбра у 3+ граней,
    как крышка цилиндра внутри купола у RoundWithProngs) в треугольники не идут."""
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    me = ob.evaluated_get(dg).to_mesh()
    verts = [v.co.copy() for v in me.vertices]
    faces = [tuple(p.vertices) for p in me.polygons]
    users = {}
    for p in me.polygons:
        for k in p.edge_keys:
            users[k] = users.get(k, 0) + 1
    inner = {p.index for p in me.polygons if all(users[k] > 2 for k in p.edge_keys)}
    me.calc_loop_triangles()
    tris = [tuple(t.vertices) for t in me.loop_triangles if t.polygon_index not in inner]
    attrs = {a.name for a in me.attributes}
    ob.evaluated_get(dg).to_mesh_clear()
    return verts, tris, faces, attrs


def stone_unit_heights(diam):
    """max.z, min.z геометрии Diam (ø 1)."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = diam.evaluated_get(dg).to_mesh()
    zs = [v.co.z for v in me.vertices]
    diam.evaluated_get(dg).to_mesh_clear()
    return max(zs), min(zs)


class Geo:
    """Расчётная геометрия новой логики по значениям нашего объекта."""

    def __init__(self, ob, unit):
        g = lambda k: get(ob, k)
        self.D = g(("Round", "ø Stone"))
        self.R = self.D / 2
        self.T = g(("Prongs", "Tilt"))
        self.d = g(("Prongs", "ø"))
        self.n = g(("Prongs", "Count"))
        self.rot = g(("Prongs", "° Z"))
        self.I = g(("Prongs", "Intersection"))
        self.table = unit[0] * self.D
        self.culet = unit[1] * self.D
        self.bottom = self.culet - g(("Cast", "Below Culet"))
        self.dome = self.table + g(("Prongs", "Above Table"))
        self.ztop = g(("Cast", "Z Offset"))
        self.rtop = self.R + g(("Cast", "XY Offset"))
        self.th = g(("Cast", "Cast Thickness"))
        self.hb = g(("Cast", "HeightBool"))
        self.ob = g(("Cast", "OffsetBool"))
        self.rr = self.R + self.d * (0.5 - self.I / 100)
        self.hc = self.ztop - self.bottom

    def r_out(self, z):
        return self.rtop + (z - self.ztop) * tan(self.T)

    def u(self, k=0.0):
        a = self.rot + k * 2 * pi / self.n
        return Vector((cos(a), sin(a), 0.0))

    def axis(self):
        return Vector((sin(self.T) * self.u().x, sin(self.T) * self.u().y, cos(self.T)))


def his_values(g):
    """Значения RoundWithProngs, при которых его геометрия совпадает с нашей."""
    c = cos(g.T)
    rbot = g.rtop - g.hc * tan(g.T)
    return {("Prongs", "Z Offset"): g.bottom / c, ("Prongs", "Height"): (g.dome - g.bottom) / c,
            ("Prongs", "Intesetion"): int(round(2 * g.I)),
            ("Cast", "Z Offset"): g.ztop, ("Cast", "Height"): g.hc,
            ("Cast", "XY Offset"): 2 * rbot - g.D, ("Cast", "Cast Taper"): g.rtop / rbot,
            ("Cast", "OffsetBool"): -g.hc / 2 + g.ob}


SAME = [(None, "Realize All"), ("Round", "ShowStone"), ("Round", "ø Stone"), ("Prongs", "Smooth"),
        ("Prongs", "Count"), ("Prongs", "° Z"), ("Prongs", "ø"), ("Prongs", "Tilt"), ("Cast", "Show"),
        ("Cast", "Cast Thickness"), ("Cast", "CastBool"), ("Cast", "HeightBool"), ("Bool", "ShowCutter"),
        ("Bool", "BoolObject"), ("Bool", "BoolCutter")]


def dome_test(g):
    """Точка в зоне купола: выше основания купола по оси своего крапана."""
    t_dome = g.dome / cos(g.T)

    def test(p):
        k = round((atan2(p.y, p.x) - g.rot) / (2 * pi / g.n))
        x = p.dot(g.u(k)) - g.rr
        return x * sin(g.T) + p.z * cos(g.T) > t_dome
    return test


def compare(ref_mesh, new_mesh, dome):
    out = [0.0, 0.0]
    for (va, fa), (vb, fb) in ((ref_mesh, new_mesh), (new_mesh, ref_mesh)):
        bvh = BVHTree.FromPolygons(vb, fb)
        for p in list(va) + [(va[t[0]] + va[t[1]] + va[t[2]]) / 3.0 for t in fa]:
            d = bvh.find_nearest(p)[3]
            k = 1 if dome(p) else 0
            out[k] = max(out[k], d)
    return out


def shells(faces, nverts):
    parent = list(range(nverts))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for f in faces:
        for v in f[1:]:
            parent[root(v)] = root(f[0])
    out = {}
    for f in faces:
        out.setdefault(root(f[0]), []).append(f)
    return list(out.values())


def closed_outward(verts, faces):
    """Каждое ребро у двух граней, все оболочки с положительным объёмом."""
    edges = {}
    for f in faces:
        for a, b in zip(f, f[1:] + f[:1]):
            k = (min(a, b), max(a, b))
            edges[k] = edges.get(k, 0) + 1
    if any(v != 2 for v in edges.values()):
        return False, 0
    parts = shells(faces, len(verts))
    for part in parts:
        vol = 0.0
        for f in part:
            for i in range(1, len(f) - 1):
                vol += verts[f[0]].dot(verts[f[i]].cross(verts[f[i + 1]])) / 6.0
        if vol <= 0:
            return False, len(parts)
    return True, len(parts)


def set_defaults(ob, ns, diam):
    keys = inputs(ob.modifiers[0])
    for name, _t, default, _a, _b, panel, _s in ns["SOCKETS"]:
        if default is not None and (panel, name) in keys:
            put(ob, (panel, name), default)
    put(ob, (None, "Diam"), diam)
    put(ob, ("Bool", "BoolObject"), None)
    put(ob, ("Bool", "BoolCollection"), None)


def hit(bvh, origin, direction):
    loc = bvh.ray_cast(origin, direction.normalized(), 100.0)[0]
    return loc


def outside(bvh, p):
    loc, nor = bvh.find_nearest(p)[:2]
    return (p - loc).dot(nor) > 0


def measure(new, g, errors, tag):
    """Замеры по нашей сетке (BoolCutter выкл). Возвращает строку отчёта."""
    verts, _t, faces, _a = evaluate(new)
    parts = shells(faces, len(verts))
    cast_f, prong_f = [], []
    for part in parts:
        c = sum((verts[i] for f in part for i in f), Vector()) / sum(len(f) for f in part)
        (cast_f if c.xy.length < g.R / 2 else prong_f).extend(part)
    allb, castb, prongb = (BVHTree.FromPolygons(verts, f) for f in (faces, cast_f, prong_f))
    u, a, ub = g.u(), g.axis(), g.u(0.5)
    c = cos(g.T)
    res = {}
    # основание купола: от вершины купола по оси вниз ø/2
    t0 = g.dome / c + 3 * g.d
    top = hit(prongb, g.rr * u + t0 * a, -a)
    res["dome"] = ((top - g.rr * u).dot(a) - g.d / 2) * c - g.dome
    # низ крапана по оси, низ каста между крапанами (середина стенки)
    t1 = g.bottom / c - 1.0
    res["prong bot"] = hit(prongb, g.rr * u + t1 * a, a).z - g.bottom
    rm = g.r_out(g.bottom) - g.th / 2
    res["cast bot"] = hit(castb, rm * ub + Vector((0, 0, g.bottom - 1.0)), UP).z - g.bottom
    # наружный радиус верха каста
    z = g.ztop - 0.005
    res["r top"] = hit(castb, (g.R + 5) * ub + Vector((0, 0, z)), -ub).xy.length - g.rtop
    # заход каста в крапан у верха и низа каста
    ov = []
    for z in (g.ztop - 0.02, g.bottom + 0.02):
        rc = hit(castb, (g.R + 5) * u + Vector((0, 0, z)), -u).xy.length
        rp = hit(prongb, Vector((0, 0, z)), u).xy.length
        ov.append(rc - rp)
    res["overlap diff"] = ov[0] - ov[1]
    # прорезь: середина высоты каста + OffsetBool, насквозь между крапанами и под крапаном
    zc = (g.ztop + g.bottom) / 2 + g.ob
    p = (g.r_out(zc) - g.th / 2) * ub + Vector((0, 0, zc))
    up, dn = hit(allb, p, UP), hit(allb, p, -UP)
    res["slot center"] = (up.z + dn.z) / 2 - zc if up and dn else 9.0
    res["slot height"] = up.z - dn.z - g.hb if up and dn else 9.0
    free = [g.r_out(zc) - g.th + 0.02, g.r_out(zc) - 0.02]
    through = all(outside(allb, r * ub + Vector((0, 0, zc))) for r in free)
    through = through and outside(allb, free[0] * u + Vector((0, 0, zc)))
    for k, v in res.items():
        if abs(v) > TOL_M:
            errors.append("%s: %s %.4f" % (tag, k, v))
    if not through:
        errors.append("%s: slot does not cut through" % tag)
    return res, ov[0], through


def axis_at_rundist(new, g):
    """Ось крапана на z = 0: середина горизонтального сечения вдоль радиуса."""
    verts, _t, faces, _a = evaluate(new)
    bvh = BVHTree.FromPolygons(verts, faces)
    u = g.u()
    x1 = hit(bvh, Vector((0, 0, 0)), u).xy.length
    x2 = hit(bvh, (g.R + 5) * u, -u).xy.length
    return (x1 + x2) / 2


def gem_names(new):
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    return [i.object.original.name for i in dg.object_instances
            if i.is_instance and i.parent and i.parent.original == new]


def cube(name, center, size, coll, bevel=False):
    me = bpy.data.meshes.new(name)
    h = size / 2
    me.from_pydata([(x, y, z) for x in (-h, h) for y in (-h, h) for z in (-h, h)], [],
                   [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.location = center
    if bevel:
        md = ob.modifiers.new("Bevel", "BEVEL")
        md.width = size * 0.15
        md.segments = 3
    return ob


def world_bvh(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    me = ob.evaluated_get(dg).to_mesh()
    verts = [ob.matrix_world @ v.co for v in me.vertices]
    faces = [tuple(p.vertices) for p in me.polygons]
    ob.evaluated_get(dg).to_mesh_clear()
    return BVHTree.FromPolygons(verts, faces)


def bool_checks(new, ns, diam, cutter, unit, errors):
    """Общий булеан: BoolObject и BoolCollection режут весь металл при любом BoolCutter."""
    set_defaults(new, ns, diam)
    put(new, ("Bool", "Cutter"), cutter)
    g = Geo(new, unit)
    scratch = bpy.data.collections.new("TestCutters")
    bpy.context.scene.collection.children.link(scratch)
    coll = bpy.data.collections.new("BoolColl")
    empty = bpy.data.collections.new("EmptyColl")
    scratch.children.link(coll)
    # A — в куполе крапана 0, B (Bevel) пересекает A; C — в стенке каста между крапанами, выше прорези
    pa = g.rr * g.u() + g.dome / cos(g.T) * g.axis()
    a = cube("CutA", pa, 0.3, coll)
    b = cube("CutB", pa + Vector((0.1, 0.0, 0.1)), 0.3, coll, bevel=True)
    zc = g.ztop - 0.15
    c = cube("CutC", g.r_out(zc) * g.u(0.5) + Vector((0, 0, zc)), 0.2, scratch)
    # точка внутри резака и внутри металла до булеана (C — выемка в наружной стенке)
    probe = {a: a.location.copy(), b: b.location.copy(), c: c.location - 0.05 * g.u(0.5)}

    def run(tag, obj, collection, bc, objs):
        put(new, ("Bool", "BoolCutter"), bc)
        put(new, ("Bool", "BoolObject"), obj)
        put(new, ("Bool", "BoolCollection"), collection)
        verts, _t, faces, _a = evaluate(new)
        metal = BVHTree.FromPolygons(verts, faces)
        inside = 0
        for o in objs:
            cb = world_bvh(o)
            # вершина металла глубже 1e-3 внутри резака (точнее не даёт триангуляция фасок Bevel)
            for v in verts:
                loc, nor = cb.find_nearest(v)[:2]
                inside += (v - loc).dot(nor) < -1e-3
            if not outside(metal, probe[o]):
                inside += 1
        ok, nsh = closed_outward(verts, faces)
        gem = gem_names(new) == [diam.name]
        print("%-22s inside %d, closed %s (%d shells), gem %s" % (tag, inside, ok, nsh, gem))
        if inside or not ok or not gem:
            errors.append("%s: inside %d, closed %s, gem %s" % (tag, inside, ok, gem))

    # резаки внутри металла до булеана (иначе проверка пустая)
    put(new, ("Bool", "BoolCutter"), True)
    verts, _t, faces, _a = evaluate(new)
    metal = BVHTree.FromPolygons(verts, faces)
    if any(outside(metal, p) for p in probe.values()):
        errors.append("bool: test cutters are not inside metal")
    run("object, BoolCutter off", c, None, False, [c])
    run("object, BoolCutter on", c, None, True, [c])
    run("collection, off", None, coll, False, [a, b])
    run("collection, on", None, coll, True, [a, b])
    run("object+collection, off", c, coll, False, [a, b, c])
    run("object+collection, on", c, coll, True, [a, b, c])

    # пустая коллекция = ничего не задано
    for bc in (False, True):
        put(new, ("Bool", "BoolCutter"), bc)
        res = []
        for collection in (None, empty):
            put(new, ("Bool", "BoolObject"), None)
            put(new, ("Bool", "BoolCollection"), collection)
            verts = evaluate(new)[0]
            res.append((len(verts), tuple(round(min(v[i] for v in verts), 5) for i in range(3)),
                        tuple(round(max(v[i] for v in verts), 5) for i in range(3))))
        print("empty collection, BoolCutter %s: %d verts, same %s" % (bc, res[0][0], res[0] == res[1]))
        if res[0] != res[1]:
            errors.append("empty collection changes result (BoolCutter %s)" % bc)
    set_defaults(new, ns, diam)


def set_checks(new, ns, diam, cutter, unit, errors):
    """Set: верх крапана на Set Height % высоты площадки, контакт с короной около Set Cover %,
    кончик лежит на короне (не в камне), результат замкнут; клетка — 16 вершин на крапан."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = diam.evaluated_get(dg).to_mesh()
    sv = [v.co.copy() for v in me.vertices]
    sf = [tuple(p.vertices) for p in me.polygons]
    diam.evaluated_get(dg).to_mesh_clear()
    r_table = max(v.xy.length for v in sv if v.z >= unit[0] * 0.999)
    girdle = max(v.z for v in sv if v.xy.length >= 0.499)
    print("set: table r %.4f, girdle top %.4f (unit)" % (r_table, girdle))
    print("stone ø     top     want    cover%  gap     inside closed")
    for D, d in SET_CASES:
        set_defaults(new, ns, diam)
        for k, v in ((("Round", "ø Stone"), D), (("Prongs", "ø"), d), (("Bool", "Cutter"), cutter),
                     (("Prongs", "Set"), True)):
            put(new, k, v)
        g = Geo(new, unit)
        H, C = get(new, ("Prongs", "Set Height")) / 100, get(new, ("Prongs", "Set Cover")) / 100
        crown = D * (0.5 - r_table)
        stone = BVHTree.FromPolygons([v * D for v in sv], sf)
        tag = "set %.1f" % D
        res = []
        for bc in (False, True):
            put(new, ("Bool", "BoolCutter"), bc)
            verts, _t, faces, _a = evaluate(new)
            top = max(v.z for v in verts)
            tip = [v for v in verts if v.z > girdle * D + 0.01]
            cover = (g.R - min(v.xy.length for v in tip)) / crown
            # кончик над короной: зазор до камня и вершины металла внутри камня
            dist = []
            for v in tip:
                loc, nor = stone.find_nearest(v)[:2]
                dist.append((v - loc).dot(nor))
            gap, inside = min(dist), sum(x < -1e-3 * D for x in dist)
            ok, nsh = closed_outward(verts, faces)
            res.append((top, cover, gap, inside, ok, nsh))
            if abs(top - H * g.table) > TOL:
                errors.append("%s: top %.4f, want %.4f" % (tag, top, H * g.table))
            if not GIA_COVER[0] <= cover <= GIA_COVER[1]:
                errors.append("%s: cover %.3f outside %s" % (tag, cover, GIA_COVER))
            if inside or gap > 0.02 * D:
                errors.append("%s: tip inside stone %d, gap %.4f" % (tag, inside, gap))
            if bc and not (ok and nsh == 1):
                errors.append("%s: closed %s, %d shells" % (tag, ok, nsh))
        top, cover, gap, inside, ok, nsh = res[1]
        print("%-5.1f %-4.1f  %.4f  %.4f  %5.1f   %.4f  %d      %s (%d)" % (
            D, d, top, H * g.table, cover * 100, gap, inside, ok, nsh))
    # Cutter пуст: посадку режет только оболочка камня, каст и стволы на месте
    put(new, ("Bool", "Cutter"), None)
    verts, _t, faces, _a = evaluate(new)
    ok, nsh = closed_outward(verts, faces)
    low = min(v.z for v in verts)
    # низ наклонного торца крапана чуть ниже bottom_z; металл до низа дошёл — ящик-ограничитель не вычтен
    print("set, no Cutter: closed %s (%d), bottom %.4f (bottom_z %.4f)" % (ok, nsh, low, g.bottom))
    if not (ok and nsh == 1) or low > g.bottom + TOL_M:
        errors.append("set, no Cutter: closed %s, %d shells, bottom %.4f" % (ok, nsh, low))
    # клетка и возврат
    set_defaults(new, ns, diam)
    before = len(evaluate(new)[0])
    put(new, ("Prongs", "Set"), True)
    put(new, (None, "Subdivision"), 0)
    nv = len(evaluate(new)[0])
    want = 16 * get(new, ("Prongs", "Count")) + 32
    put(new, (None, "Subdivision"), 2)
    put(new, ("Prongs", "Set"), False)
    after = len(evaluate(new)[0])
    print("set cage: %d verts (want %d); Set off again: %d verts (was %d)" % (nv, want, after, before))
    if nv != want or after != before:
        errors.append("set cage %d (want %d), toggle %d -> %d" % (nv, want, before, after))


def check(errors, ns):
    ref = bpy.data.objects[REF]
    his0 = {k: get(ref, k) for k in inputs(ref.modifiers[0])}
    diam, cutter = get(ref, (None, "Diam")), bpy.data.objects["Cutter"]
    unit = stone_unit_heights(diam)
    new = ns["setup"](NEW, diam=diam, cutter="Cutter")
    print("Diam %s: table %.4f, culet %.4f (unit)" % (diam.name, unit[0], unit[1]))

    # 1. сравнение с RoundWithProngs
    base = {(None, "Realize All"): True, ("Bool", "BoolCutter"): True,
            ("Bool", "BoolObject"): his0[("Bool", "BoolObject")]}
    variants = [("defaults 2.0", {}), ("stone 1.2", {("Round", "ø Stone"): 1.2}),
                ("stone 3.0", {("Round", "ø Stone"): 3.0}),
                # у него при Tilt ровно 0 (Taper 1) Manifold-булеан почти всё теряет — сравнение без булеанов
                ("tilt 0, no bool", {("Prongs", "Tilt"): 0.0, ("Bool", "BoolCutter"): False}),
                ("tilt 0.14", {("Prongs", "Tilt"): 0.14}), ("BoolCutter off", {("Bool", "BoolCutter"): False})]
    print("compare          outside  dome    closed")
    for tag, values in variants:
        set_defaults(new, ns, diam)
        for k, v in list(base.items()) + list(values.items()):
            put(new, k, v)
        # у него BoolObject действует только при BoolCutter, у нас — всегда
        if not get(new, ("Bool", "BoolCutter")):
            put(new, ("Bool", "BoolObject"), None)
        g = Geo(new, unit)
        for k in SAME:
            put(ref, k, get(new, k))
        put(ref, (None, "Diam"), diam)
        for k, v in his_values(g).items():
            put(ref, k, v)
        r, n = evaluate(ref), evaluate(new)
        far, dome = compare(r[:2], n[:2], dome_test(g))
        ok, nsh = closed_outward(n[0], n[2])
        print("%-16s %.4f   %.4f  %s (%d shells)" % (tag, far, dome, ok, nsh))
        if far > TOL:
            errors.append("%s: surface %.4f > %.2f" % (tag, far, TOL))
        if dome > TOL_DOME:
            errors.append("%s: dome %.4f > %.2f" % (tag, dome, TOL_DOME))
        if values.get(("Bool", "BoolCutter"), True) and not ok:
            errors.append("%s: not closed / inverted" % tag)
    for k, v in his0.items():
        put(ref, k, v)

    # 2. прямые замеры по размерам камня
    print("stone  dome    prongBot castBot rTop    ovDiff  slotC   slotH   overlap through closed")
    for D in SIZES:
        set_defaults(new, ns, diam)
        put(new, ("Round", "ø Stone"), D)
        g = Geo(new, unit)
        res, ov, through = measure(new, g, errors, "stone %.1f" % D)
        put(new, ("Bool", "Cutter"), cutter)
        put(new, ("Bool", "BoolCutter"), True)
        n = evaluate(new)
        ok, nsh = closed_outward(n[0], n[2])
        if not ok:
            errors.append("stone %.1f: union not closed / inverted" % D)
        print("%-6.1f %s %.4f  %s %s (%d)" % (D, " ".join("%+.4f" % res[k] for k in
              ("dome", "prong bot", "cast bot", "r top", "overlap diff", "slot center", "slot height")),
              ov, through, ok, nsh))
    for I, want in ((0.0, 0.5), (50.0, 0.0), (100.0, -0.5)):
        set_defaults(new, ns, diam)
        put(new, ("Prongs", "Intersection"), I)
        put(new, ("Cast", "Show"), False)
        g = Geo(new, unit)
        x = axis_at_rundist(new, g)
        err = x - (g.R + want * g.d)
        print("intersection %3.0f: axis %.4f (want %.4f)" % (I, x, g.R + want * g.d))
        if abs(err) > 0.005:
            errors.append("intersection %.0f: axis off %.4f" % (I, err))
    set_defaults(new, ns, diam)

    # 3. клетка, камень, пустой Diam, пересборка
    put(new, (None, "Subdivision"), 0)
    verts, _tris, faces, attrs = evaluate(new)
    want = 12 * get(new, ("Prongs", "Count")) + 32
    print("cage: %d verts (want %d), crease_edge %s" % (len(verts), want, "crease_edge" in attrs))
    if len(verts) != want or "crease_edge" not in attrs:
        errors.append("cage: %d verts, crease_edge %s" % (len(verts), "crease_edge" in attrs))
    put(new, (None, "Subdivision"), 2)

    gems = gem_names(new)
    print("stone instance: %s" % gems)
    if not (gems == [diam.name] and "gem" in diam):
        errors.append("stone is not an instance of Diam with 'gem'")

    bool_checks(new, ns, diam, cutter, unit, errors)
    set_checks(new, ns, diam, cutter, unit, errors)

    put(new, (None, "Diam"), None)
    nv = len(evaluate(new)[0])
    print("empty Diam: %d verts" % nv)
    if nv == 0:
        errors.append("empty Diam: no geometry")
    put(new, (None, "Diam"), diam)

    # устаревшие сокеты, как в прежней версии группы, — сборка их убирает, остальное не трогает
    ng = new.modifiers[0].node_group
    panels = {it.name: it for it in ng.interface.items_tree if it.item_type == "PANEL"}
    for panel, name in ns["OBSOLETE"]:
        ng.interface.new_socket(name, in_out="INPUT", socket_type="NodeSocketFloat", parent=panels[panel])
    put(new, ("Cast", "XY Offset"), -0.123)
    before = {k: get(new, k) for k in inputs(new.modifiers[0]) if k not in ns["OBSOLETE"]}
    ns["build_group"]()
    keys = inputs(new.modifiers[0])
    after = {k: get(new, k) for k in keys}
    changed = [k for k in before if before[k] != after.get(k)]
    stale = [k for k in ns["OBSOLETE"] if k in keys]
    order = [k for k in keys if k[0]] == [(p, n) for n, _t, _d, _a, _b, p, _s in ns["SOCKETS"] if p]
    print("rebuild: %d inputs, changed %s, obsolete left %s, panel order ok %s" % (len(after), changed, stale, order))
    if changed or stale or not order:
        errors.append("rebuild: changed %s, obsolete %s, order %s" % (changed, stale, order))
    return ref, new, his0, diam


def render_sheet(ref, new, his0, diam, ns):
    """Вид сбоку, камни SIZES в одном экранном размере. Верх — его группа с его значениями, низ — наша."""
    scene = bpy.context.scene
    for k, v in his0.items():
        put(ref, k, v)
    set_defaults(new, ns, diam)
    scene.world = scene.world or bpy.data.worlds.new("World")
    scene.world.use_nodes = False      # иначе Workbench берёт фон из узлов мира (в файле — чёрный)
    scene.world.color = (1.0, 1.0, 1.0)
    # меши — до скрытия сцены: объект в исключённой коллекции depsgraph не считает
    frozen = {}
    for ob in (ref, new):
        for D in SIZES:
            put(ob, ("Round", "ø Stone"), D)
            dg = bpy.context.evaluated_depsgraph_get()
            dg.update()
            frozen[ob.name, D] = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    for ob in scene.collection.objects:
        ob.hide_render = True
    view = bpy.data.collections.new("Sheet")
    scene.collection.children.link(view)
    for lc in bpy.context.view_layer.layer_collection.children:
        lc.exclude = lc.collection != view
    gap, show = 4.0, 2.0                       # шаг ячеек; экранный ø камня

    def text(body, loc, size):
        cu = bpy.data.curves.new("t", "FONT")
        cu.body = body
        cu.size = size
        cu.align_x = "CENTER"
        ob = bpy.data.objects.new("t", cu)
        view.objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (pi / 2, 0.0, 0.0)
        ob.color = (0.0, 0.0, 0.0, 1.0)

    for row, (ob, title) in enumerate(((ref, "RoundWithProngs, his values"), (new, "My_Round_Cast, defaults"))):
        zc = (0.5 - row) * gap
        text(title, Vector((0.0, -3.0, zc + 1.45)), 0.3)
        for col, D in enumerate(SIZES):
            me = frozen[ob.name, D]
            cell = Vector(((col - 2) * gap, 0.0, zc + 0.3))
            k = show / D
            m = bpy.data.objects.new("m", me)
            view.objects.link(m)
            m.matrix_world = Matrix.Translation(cell) @ Matrix.Scale(k, 4)
            m.color = (0.86, 0.66, 0.24, 1.0)
            gem = bpy.data.objects.new("gem", diam.data)
            view.objects.link(gem)
            gem.matrix_world = Matrix.Translation(cell) @ Matrix.Scale(show, 4)
            gem.color = (0.72, 0.84, 1.0, 1.0)
            if row == 1:
                text("ø %.1f mm" % D, cell + Vector((0.0, -3.0, -2.75)), 0.3)

    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    view.objects.link(cam)
    cam.location = (0.0, -20.0, -0.2)
    cam.rotation_euler = (pi / 2, 0.0, 0.0)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 5.2 * gap
    scene.camera = cam
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 2080
    scene.render.resolution_y = 940
    scene.render.resolution_percentage = 100
    scene.display.render_aa = "16"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.show_cavity = True
    scene.display.shading.background_type = "VIEWPORT"
    scene.display.shading.background_color = (1.0, 1.0, 1.0)
    scene.view_settings.view_transform = "Standard"
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(PREVIEW)
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.image_settings.color_mode = "RGB"
    bpy.ops.render.render(write_still=True)
    print("preview: %s" % PREVIEW)


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    paths = [a for a in args if a.endswith(".blend")]
    if paths and Path(bpy.data.filepath or "") != Path(paths[0]):
        bpy.ops.wm.open_mainfile(filepath=paths[0])
    errors = []
    ns = load_build()
    ref, new, his0, diam = check(errors, ns)
    if "--preview" in args:
        render_sheet(ref, new, his0, diam, ns)
    for e in errors:
        print("FAIL", e)
    print("ROUND_CAST_TEST", "failed" if errors else "passed")
    if errors:
        sys.exit(1)


try:
    main()
except SystemExit:
    raise
except Exception:
    traceback.print_exc()
    sys.exit(1)
