"""My_Gem_Cast (tools/gn_gem_cast_build.py): замеры по вычисленному мешу.

Фоновый Blender, пустая сцена (файл не сохраняется):
  Blender --factory-startup --background --python tools/test_gem_cast.py [-- --preview]
  --preview  ещё и лист dist/previews/gem_cast_cuts.png
Код выхода 1 — проверка не прошла.

1. Сверка с My_Round_Cast: ROUND 2 x 2 против ø Stone 2, Count 4, ° Z 45°, общий катер.
2. Груша, изумруд, багет в двух размерах (BoolCutter выкл — крапана и каст отдельными
   оболочками): высоты, кромка каста от настоящего контура рундиста, толщина стенки, оси
   крапанов, прорезь; с BoolCutter — замкнутость, камень-инстанс.
3. Общий булеан: BoolObject и BoolCollection (два пересекающихся куба).
4. Subdivision 0 — число вершин клетки; повторная сборка не меняет значения.
5. Set: верх крапана на Set Height % высоты площадки, кончик лежит на короне и не входит в камень,
   заход за рундист — в долях пути по короне короткой стороны; свой Cutter режет только ниже рундиста.
"""

from math import atan2, cos, hypot, pi, radians, sin, tan
from pathlib import Path
import sys
import traceback

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "tools" / "gn_gem_cast_build.py"
ROUND_BUILD = ROOT / "tools" / "gn_round_cast_build.py"
PREVIEW = ROOT / "dist" / "previews" / "gem_cast_cuts.png"
CASES = (("PEAR", 3.0, 5.0), ("PEAR", 6.0, 9.0), ("EMERALD", 4.0, 6.0), ("EMERALD", 7.0, 10.0),
         ("BAGUETTE", 2.0, 4.0), ("BAGUETTE", 3.0, 7.0))
SHEET = (("PEAR", 3.0, 5.0), ("EMERALD", 4.0, 6.0), ("BAGUETTE", 2.0, 4.0))
TOL = 0.02          # мм
TOL_TH = 0.05       # доля Cast Thickness
UP = Vector((0.0, 0.0, 1.0))


def load(path, name):
    ns = {"__name__": name}
    exec(compile(path.read_text(), str(path), "exec"), ns)
    return ns


def inputs(ob):
    md = ob.modifiers[0]
    return {(it.parent.name or None, it.name): it.identifier for it in md.node_group.interface.items_tree
            if it.item_type == "SOCKET" and it.in_out == "INPUT" and it.socket_type != "NodeSocketGeometry"}


def get(ob, key):
    return getattr(ob.modifiers[0].properties.inputs, inputs(ob)[key]).value


def put(ob, key, value):
    getattr(ob.modifiers[0].properties.inputs, inputs(ob)[key]).value = value
    ob.update_tag()


def set_defaults(ob, ns):
    keys = inputs(ob)
    for name, _t, default, _a, _b, panel, _s in ns["SOCKETS"]:
        if default is not None and (panel, name) in keys and name not in ("Width", "Length"):
            put(ob, (panel, name), default)
    for k in (("Bool", "Cutter"), ("Bool", "BoolObject"), ("Bool", "BoolCollection")):
        put(ob, k, None)


def evaluate(ob):
    """Вершины, грани металла (инстанс камня в меш не входит)."""
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    me = ob.evaluated_get(dg).to_mesh()
    verts = [v.co.copy() for v in me.vertices]
    faces = [tuple(p.vertices) for p in me.polygons]
    ob.evaluated_get(dg).to_mesh_clear()
    return verts, faces


def triangles(ob):
    """Центры треугольников металла: у невыпуклой грани после булеана центр грани — вне поверхности."""
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    me = ob.evaluated_get(dg).to_mesh()
    me.calc_loop_triangles()
    out = [sum((me.vertices[i].co for i in t.vertices), Vector()) / 3.0 for t in me.loop_triangles]
    ob.evaluated_get(dg).to_mesh_clear()
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
    if not faces or any(v != 2 for v in edges.values()):
        return False, 0, 0.0
    total = 0.0
    parts = shells(faces, len(verts))
    for part in parts:
        vol = sum(verts[f[0]].dot(verts[f[i]].cross(verts[f[i + 1]])) / 6.0 for f in part for i in range(1, len(f) - 1))
        if vol <= 0:
            return False, len(parts), total
        total += vol
    return True, len(parts), total


def stone_instances(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    return [i.object.original for i in dg.object_instances if i.is_instance and i.parent and i.parent.original == ob]


def ray(bvh, origin, direction, skip=0):
    """Точка попадания (skip — сколько попаданий пропустить)."""
    d = direction.normalized()
    p = origin
    for _ in range(skip + 1):
        loc = bvh.ray_cast(p, d, 100.0)[0]
        if loc is None:
            return None
        p = loc + d * 1e-5
    return loc


def outside(bvh, p):
    loc, nor = bvh.find_nearest(p)[:2]
    return (p - loc).dot(nor) > 0


# --- контуры ------------------------------------------------------------------

def loop_of(proto, w, l):
    """Петля прототипа (вершины с рёбрами по порядку), места крапанов, в мм."""
    me = proto.data
    linked = {i for e in me.edges for i in e.vertices}
    corner = me.attributes["corner"].data
    loop = [(v.co.x * w, v.co.y * l, corner[v.index].value > 0.5) for v in me.vertices if v.index in linked]
    sites = [(v.co.x * w, v.co.y * l) for v in me.vertices if v.index not in linked]
    return loop, sites


def girdle_outline(stone, w, l):
    """Настоящий контур рундиста: граница верхних граней (как crown_outline в test_gem_setting.py)."""
    verts = [(v.co.x * w, v.co.y * l, v.co.z * w) for v in stone.data.vertices]
    uses = {}
    for p in stone.data.polygons:
        if p.normal.z > 1e-3:
            for k in p.edge_keys:
                uses[k] = uses.get(k, 0) + 1
    links = {}
    for (a, b), c in uses.items():
        if c == 1:
            links.setdefault(a, []).append(b)
            links.setdefault(b, []).append(a)
    start = min(links)
    order, prev, cur = [start], None, start
    while True:
        cur, prev = next(v for v in links[cur] if v != prev), cur
        if cur == start:
            break
        order.append(cur)
    pts = [(verts[i][0], verts[i][1]) for i in order]
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))
    return pts if area > 0 else pts[::-1]


def signed_distance(p, outline):
    """Расстояние до контура, снаружи — плюс."""
    best = 1e9
    for i in range(len(outline)):
        (ax, ay), (bx, by) = outline[i], outline[(i + 1) % len(outline)]
        vx, vy = bx - ax, by - ay
        t = min(1.0, max(0.0, ((p[0] - ax) * vx + (p[1] - ay) * vy) / (vx * vx + vy * vy)))
        best = min(best, hypot(p[0] - ax - vx * t, p[1] - ay - vy * t))
    inside = False
    for k in range(len(outline)):
        (x1, y1), (x2, y2) = outline[k - 1], outline[k]
        if (y1 > p[1]) != (y2 > p[1]) and p[0] < x1 + (p[1] - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return -best if inside else best


def nearest_normal(dense, p):
    """Наружная нормаль предела в ближайшей точке плотной выборки (в острой вершине — биссектриса)."""
    _, _, tx, ty = min(dense, key=lambda s: (s[0] - p[0]) ** 2 + (s[1] - p[1]) ** 2)
    return Vector((ty, -tx, 0.0))


# --- замеры -------------------------------------------------------------------

class Geo:
    def __init__(self, ob, go, stone, proto):
        g = lambda k: get(ob, k)
        self.W, self.L = g(("Stone", "Width")), g(("Stone", "Length"))
        zs = [v.co.z for v in stone.data.vertices]
        self.table, self.culet = max(zs) * self.W, min(zs) * self.W
        self.T = g(("Prongs", "Tilt"))
        self.d = g(("Prongs", "ø"))
        self.k = self.d * (0.5 - g(("Prongs", "Intersection")) / 100.0)
        self.bottom = self.culet - g(("Cast", "Below Culet"))
        self.dome = self.table + g(("Prongs", "Above Table"))
        self.ztop = g(("Cast", "Z Offset"))
        self.xy = g(("Cast", "XY Offset"))
        self.th = g(("Cast", "Cast Thickness"))
        self.hb, self.ob = g(("Cast", "HeightBool")), g(("Cast", "OffsetBool"))
        self.hc = max(self.ztop - self.bottom, 0.05)
        self.loop, sites = loop_of(proto, self.W, self.L)
        self.dense = go.limit_curve(self.loop, 64)
        self.prongs = []
        for x, y in sites:
            n = nearest_normal(self.dense, (x, y))
            self.prongs.append((Vector((x, y, 0.0)) + n * self.k, n,
                                Vector((n.x * sin(self.T), n.y * sin(self.T), cos(self.T)))))
        self.girdle = girdle_outline(stone, self.W, self.L)


def split(verts, faces, g):
    """BVH всего, каста и крапанов: оболочка с центром дальше 0.25 ширины от центра — крапан."""
    cast_f, prong_f = [], []
    c0 = Vector(((min(p[0] for p in g.girdle) + max(p[0] for p in g.girdle)) / 2,
                 (min(p[1] for p in g.girdle) + max(p[1] for p in g.girdle)) / 2, 0.0))
    for part in shells(faces, len(verts)):
        c = sum((verts[i] for f in part for i in f), Vector()) / sum(len(f) for f in part)
        (cast_f if (c - c0).xy.length < 0.25 * g.W else prong_f).extend(part)
    return [BVHTree.FromPolygons(verts, f) for f in (faces, cast_f, prong_f)]


def wall_probe(castb, g, p, n, z):
    """Луч снаружи по -n на высоте z: (наружная точка, толщина по горизонтали — минимум веером
    от внутренней стенки наружу)."""
    o = Vector((p[0], p[1], z)) + n * 3.0
    p_out = ray(castb, o, -n)
    p_in = ray(castb, o, -n, skip=1)
    if p_out is None or p_in is None:
        return None, None
    if (p_in - p_out).length > 2.0 * g.th:
        return p_out, None      # луч прошёл сплошной клин (у острия стенки сходятся) — толщину не мерить
    nor_in = castb.ray_cast(p_out - n * 1e-5, -n, 100.0)[1]   # нормаль внутренней стенки — в полость
    th = 9.0
    for k in range(-40, 41):
        a = radians(2.0 * k)
        dirn = Vector((n.x * cos(a) - n.y * sin(a), n.x * sin(a) + n.y * cos(a), 0.0))
        if dirn.dot(nor_in) >= 0.0:
            continue
        loc, nor = castb.ray_cast(p_in + dirn * 1e-4, dirn, 100.0)[:2]
        if loc is not None and nor.dot(dirn) > 0.0:      # выход из металла — наружная стенка
            th = min(th, (loc - p_in).length)
    return p_out, th


def measure(ob, g, errors, tag):
    verts, faces = evaluate(ob)
    allb, castb, prongb = split(verts, faces, g)
    c = cos(g.T)
    res = {"dome": 0.0, "prong bot": 0.0, "axis": 0.0}
    for p0, n, a in g.prongs:
        top = ray(prongb, p0 + a * (g.dome / c + 3 * g.d), -a)
        dome = ((top - p0).dot(a) - g.d / 2) * c - g.dome
        bot = ray(prongb, p0 + a * (g.bottom / c - 1.0), a).z - g.bottom
        # ось на z = 0: середины сечения по n и по касательной
        t = Vector((-n.y, n.x, 0.0))
        mid_n = (ray(prongb, p0 + n * 2.0, -n) + ray(prongb, p0 - n * 2.0, n)) / 2
        mid_t = (ray(prongb, p0 + t * 2.0, -t) + ray(prongb, p0 - t * 2.0, t)) / 2
        axis = max((mid_n - p0).dot(n), (mid_t - p0).dot(t), key=abs)
        for k, v in (("dome", dome), ("prong bot", bot), ("axis", axis)):
            res[k] = max(res[k], v, key=abs)
    # стенка: в узлах острых вершин и по пролётам петли (середины), выше прорези
    n_loop = len(g.loop)
    z = g.ztop - 0.03
    edge, th_min, th_max, th_corner, bots, skipped = 0.0, 9.0, 0.0, 9.0, 0.0, 0
    tol_edge = max(TOL, 0.005 * g.W)
    for i in range(n_loop):
        for f in (0.0, 0.25, 0.5, 0.75):
            x, y, tx, ty = g.dense[int((i + f) * 64)]
            n = Vector((ty, -tx, 0.0))
            p_out, th = wall_probe(castb, g, (x, y), n, z)
            if p_out is None:
                errors.append("%s: wall probe missed at %d+%.2f" % (tag, i, f))
                continue
            # кромка: верх наружной стенки, отступ от настоящего контура
            top_out = p_out + (g.ztop - z) * tan(g.T) * n
            edge = max(edge, signed_distance(top_out.xy, g.girdle) - g.xy, key=abs)
            if th is None:
                skipped += 1
            elif f == 0.0 and g.loop[i][2]:
                th_corner = min(th_corner, th)
            else:
                th_min, th_max = min(th_min, th), max(th_max, th)
            if f == 0.5:
                o = Vector((x, y, g.bottom - 1.0)) + n * (g.xy - g.th / 2 - g.hc * tan(g.T))
                bots = max(bots, ray(castb, o, UP).z - g.bottom, key=abs)
    res.update({"cast bot": bots, "edge": edge, "skipped": skipped})
    # прорезь: середина высоты + OffsetBool, насквозь посреди стенки в серединах пролётов
    zc = g.ztop - g.hc / 2 + g.ob
    through = True
    for i in range(n_loop):
        x, y, tx, ty = g.dense[int((i + 0.5) * 64)]
        n = Vector((ty, -tx, 0.0))
        p = Vector((x, y, zc)) + n * (g.xy - g.th / 2 - (g.ztop - zc) * tan(g.T))
        if not any((p - q).xy.length < g.d * 1.2 for q, _n, _a in g.prongs):
            through = through and outside(allb, p)
    for k in ("dome", "prong bot", "cast bot", "axis"):
        if abs(res[k]) > TOL:
            errors.append("%s: %s %+.4f" % (tag, k, res[k]))
    if abs(edge) > tol_edge:
        errors.append("%s: cast edge vs girdle %+.4f (tol %.3f)" % (tag, edge, tol_edge))
    if abs(th_min / g.th - 1) > TOL_TH or abs(th_max / g.th - 1) > TOL_TH:
        errors.append("%s: wall %.3f..%.3f vs %.3f" % (tag, th_min, th_max, g.th))
    if th_corner < g.th * (1 - TOL_TH):
        errors.append("%s: wall at sharp corner %.3f < %.3f" % (tag, th_corner, g.th))
    if not through:
        errors.append("%s: slot does not cut through" % tag)
    return res, (th_min, th_max, th_corner), through


def check_round(errors, ns):
    """ROUND 2 x 2 против My_Round_Cast с теми же входами и общим катером."""
    rns = load(ROUND_BUILD, "round_cast_build")
    ob = ns["setup"]("ROUND", 2.0, 2.0)
    set_defaults(ob, ns)
    unit = bpy.data.objects["Unit Round"]
    # катер-единица: цилиндр ø 1.02 над рундистом + конус до калетты
    bm = bmesh.new()
    for z, r in ((3.0, 0.51), (0.0, 0.51)):
        for k in range(48):
            bm.verts.new((r * cos(2 * pi * k / 48), r * sin(2 * pi * k / 48), z))
    bm.verts.new((0.0, 0.0, -0.5))
    bmesh.ops.convex_hull(bm, input=bm.verts)
    me = bpy.data.meshes.new("Test Cutter")
    bm.to_mesh(me)
    bm.free()
    cutter = bpy.data.objects.new("Test Cutter", me)
    bpy.context.scene.collection.objects.link(cutter)
    rob = rns["setup"]("Ref Round Cast", diam=unit, cutter=cutter)
    for o in (ob, rob):
        put(o, ("Bool", "BoolCutter"), True)
    put(ob, ("Bool", "Cutter"), cutter)
    put(rob, ("Round", "ø Stone"), 2.0)
    put(rob, ("Prongs", "Count"), 4)
    put(rob, ("Prongs", "° Z"), pi / 4)
    va, fa = evaluate(ob)
    vb, fb = evaluate(rob)
    g = Geo(ob, ns["go"], unit, bpy.data.objects["Outline Round"])
    t_dome = g.dome / cos(g.T)

    def in_dome(p):
        return any((p - p0).dot(a) > t_dome for p0, _n, a in g.prongs if (p - p0).xy.length < 2 * g.d)
    far = dome = 0.0
    for (v1, t1), (v2, f2) in (((va, triangles(ob)), (vb, fb)), ((vb, triangles(rob)), (va, fa))):
        bvh = BVHTree.FromPolygons(v2, f2)
        for p in list(v1) + t1:
            dist = bvh.find_nearest(p)[3]
            if in_dome(p):
                dome = max(dome, dist)
            else:
                far = max(far, dist)
    ok = closed_outward(va, fa)[0]
    print("round vs My_Round_Cast: outside domes %.4f, domes %.4f, closed %s" % (far, dome, ok))
    if far > TOL or not ok:
        errors.append("round: surface %.4f > %.2f or not closed" % (far, TOL))
    return ob, rob


def check_cuts(errors, ns):
    print("case          dome    prongBot castBot axis    edge    wall min/max/corner (wedge)  slot  closed inst")
    for cut, w, l in CASES:
        ob = ns["setup"](cut, w, l)
        set_defaults(ob, ns)
        put(ob, ("Stone", "Width"), w)
        put(ob, ("Stone", "Length"), l)
        stone, proto = bpy.data.objects["Unit " + cut.title()], bpy.data.objects["Outline " + cut.title()]
        g = Geo(ob, ns["go"], stone, proto)
        tag = "%s %gx%g" % (cut.lower(), w, l)
        res, th, through = measure(ob, g, errors, tag)
        put(ob, ("Bool", "BoolCutter"), True)
        ok, nsh, _vol = closed_outward(*evaluate(ob))
        inst = stone_instances(ob)
        inst_ok = len(inst) == 1 and inst[0] == stone and "gem" in stone
        print("%-13s %s  %.3f/%.3f/%.3f (%d)  %-5s %s(%d) %s" % (
            tag, " ".join("%+.4f" % res[k] for k in ("dome", "prong bot", "cast bot", "axis", "edge")),
            th[0], th[1], th[2], res["skipped"], through, ok, nsh, inst_ok))
        if not ok:
            errors.append("%s: BoolCutter result not closed / inverted" % tag)
        if not inst_ok:
            errors.append("%s: stone is not an instance of %s" % (tag, stone.name))
        set_defaults(ob, ns)


def check_bools(errors, ns):
    """BoolObject (куб на +X) и BoolCollection (два пересекающихся куба на -X) режут стенку."""
    ob = ns["setup"]("PEAR", 3.0, 5.0)
    set_defaults(ob, ns)
    g = Geo(ob, ns["go"], bpy.data.objects["Unit Pear"], bpy.data.objects["Outline Pear"])
    z = g.ztop - 0.1
    xs = [p[0] for p in g.girdle]
    right, left = max(xs) + g.xy - g.th / 2, min(xs) - g.xy + g.th / 2

    def cube(name, loc, size, coll):
        me = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bm.to_mesh(me)
        bm.free()
        o = bpy.data.objects.new(name, me)
        coll.objects.link(o)
        o.location, o.scale = loc, size
        return o
    scene = bpy.context.scene.collection
    obj = cube("Bool A", (right, 0.0, z), (1.0, 0.6, 0.3), scene)
    coll = bpy.data.collections.new("Bool Set")
    scene.children.link(coll)
    cube("Bool B", (left, 0.3, z), (1.0, 0.6, 0.3), coll)
    cube("Bool C", (left, -0.1, z), (1.0, 0.6, 0.3), coll)      # пересекается с B
    probes = [Vector((right, 0.0, z)), Vector((left, 0.5, z)), Vector((left, -0.3, z))]
    for bc in (False, True):
        put(ob, ("Bool", "BoolCutter"), bc)
        put(ob, ("Bool", "BoolObject"), None)
        put(ob, ("Bool", "BoolCollection"), None)
        before = BVHTree.FromPolygons(*evaluate(ob))
        put(ob, ("Bool", "BoolObject"), obj)
        put(ob, ("Bool", "BoolCollection"), coll)
        v, f = evaluate(ob)
        after = BVHTree.FromPolygons(v, f)
        was = [not outside(before, p) for p in probes]
        cut_ok = [outside(after, p) for p in probes]
        ok = closed_outward(v, f)[0]
        inst = stone_instances(ob)
        print("bool BoolCutter %-5s: metal before %s, cut %s, closed %s, stone %s" % (
            bc, was, cut_ok, ok, [i.name for i in inst]))
        if not all(was) or not all(cut_ok) or not ok or len(inst) != 1:
            errors.append("bool BoolCutter %s: before %s cut %s closed %s stone %d" % (bc, was, cut_ok, ok, len(inst)))
    set_defaults(ob, ns)
    for o in (obj, *coll.objects):
        bpy.data.objects.remove(o)
    bpy.data.collections.remove(coll)


def check_cage(errors, ns):
    for cut in ("PEAR", "EMERALD", "BAGUETTE"):
        ob = bpy.data.objects[cut.title() + " Cast"]
        put(ob, (None, "Subdivision"), 0)
        loop, sites = loop_of(bpy.data.objects["Outline " + cut.title()], 1.0, 1.0)
        nv = len(evaluate(ob)[0])
        want = 12 * len(sites) + 4 * len(loop)
        print("cage %-8s: %d verts (want %d = 12 x %d + 4 x %d)" % (cut.lower(), nv, want, len(sites), len(loop)))
        if nv != want:
            errors.append("cage %s: %d verts, want %d" % (cut, nv, want))
        put(ob, (None, "Subdivision"), 2)
    ob = bpy.data.objects["Pear Cast"]
    put(ob, ("Cast", "XY Offset"), -0.123)
    put(ob, ("Prongs", "Tilt"), 0.1)
    before = {k: get(ob, k) for k in inputs(ob)}
    ns["build_group"]()
    after = {k: get(ob, k) for k in inputs(ob)}
    changed = [k for k in before if before[k] != after.get(k)]
    print("rebuild: %d inputs, changed %s" % (len(after), changed))
    if changed or len(after) != len(before):
        errors.append("rebuild changed %s" % changed)
    set_defaults(ob, ns)


def check_set(errors, ns):
    """Set: кончики загнуты. Верх крапана, зазор до камня, заход за рундист, замкнутость, клетка."""
    print("set case      top     want    reach% gap     inside closed  cage")
    for cut, w, l in CASES:
        ob = ns["setup"](cut, w, l)
        set_defaults(ob, ns)
        put(ob, ("Stone", "Width"), w)
        put(ob, ("Stone", "Length"), l)
        put(ob, ("Prongs", "Set"), True)
        stone, proto = bpy.data.objects["Unit " + cut.title()], bpy.data.objects["Outline " + cut.title()]
        g = Geo(ob, ns["go"], stone, proto)
        tag = "set %s %gx%g" % (cut.lower(), w, l)
        sv = [Vector((v.co.x * w, v.co.y * l, v.co.z * w)) for v in stone.data.vertices]
        sb = BVHTree.FromPolygons(sv, [tuple(q.vertices) for q in stone.data.polygons])
        zmax = max(v.co.z for v in stone.data.vertices)
        crown = w * (0.5 - max(abs(v.co.x) for v in stone.data.vertices if v.co.z >= zmax * 0.999))
        zg = max(v.z for v in sv if signed_distance((v.x, v.y), g.girdle) > -1e-4)   # верх рундиста
        want = g.table * get(ob, ("Prongs", "Set Height")) / 100
        row = None
        for bc in (False, True):
            put(ob, ("Bool", "BoolCutter"), bc)
            verts, faces = evaluate(ob)
            top = max(v.z for v in verts)
            tip = [v for v in verts if v.z > zg + 0.01]
            reach = max(-signed_distance((v.x, v.y), g.girdle) for v in tip) / crown
            dist = []
            for v in tip:
                loc, nor = sb.find_nearest(v)[:2]
                dist.append((v - loc).dot(nor))
            gap, inside = min(dist), sum(x < -1e-3 * w for x in dist)
            ok, nsh, _vol = closed_outward(verts, faces)
            row = (top, reach, gap, inside, ok, nsh)
            if abs(top - want) > TOL:
                errors.append("%s: top %.4f, want %.4f" % (tag, top, want))
            if inside or gap > 0.02 * w:
                errors.append("%s: tip inside stone %d, gap %.4f" % (tag, inside, gap))
            if not ok or (bc and nsh != 1):
                errors.append("%s: closed %s, %d shells (BoolCutter %s)" % (tag, ok, nsh, bc))
        put(ob, (None, "Subdivision"), 0)
        loop, sites = loop_of(proto, 1.0, 1.0)
        nv, cage = len(evaluate(ob)[0]), 16 * len(sites) + 4 * len(loop)
        if nv != cage:
            errors.append("%s: cage %d verts, want %d" % (tag, nv, cage))
        top, reach, gap, inside, ok, nsh = row
        print("%-13s %.4f  %.4f  %5.1f  %.4f  %d      %s(%d) %d/%d" % (
            tag[4:], top, want, reach * 100, gap, inside, ok, nsh, nv, cage))
        set_defaults(ob, ns)

    # свой Cutter (камень, увеличенный на 3 %) при Set режет только ниже рундиста: кончик на месте
    ob = ns["setup"]("PEAR", 3.0, 5.0)
    set_defaults(ob, ns)
    stone = bpy.data.objects["Unit Pear"]
    me = stone.data.copy()
    me.transform(Matrix.Diagonal((1.03, 1.03, 1.0, 1.0)))
    cutter = bpy.data.objects.new("Set Cutter", me)
    bpy.context.scene.collection.objects.link(cutter)
    put(ob, ("Prongs", "Set"), True)
    put(ob, ("Bool", "BoolCutter"), True)
    auto = evaluate(ob)
    put(ob, ("Bool", "Cutter"), cutter)
    own = evaluate(ob)
    tops = [max(v.z for v in m[0]) for m in (auto, own)]
    ok, nsh, _vol = closed_outward(*own)
    print("set own cutter: top %.4f (auto %.4f), closed %s (%d)" % (tops[1], tops[0], ok, nsh))
    if abs(tops[0] - tops[1]) > 1e-4 or not ok or nsh != 1:
        errors.append("set own cutter: top %.4f vs %.4f, closed %s, %d shells" % (tops[1], tops[0], ok, nsh))
    set_defaults(ob, ns)
    bpy.data.objects.remove(cutter)


# --- лист превью ----------------------------------------------------------------

def render_sheet(ns):
    """Ряды: 3/4, сверху, сбоку, клетка (Subdivision 0, каркас). Колонки — SHEET."""
    scene = bpy.context.scene
    scene.world = scene.world or bpy.data.worlds.new("World")
    scene.world.use_nodes = False
    scene.world.color = (1.0, 1.0, 1.0)
    frozen = []
    for cut, w, l in SHEET:
        ob = ns["setup"](cut, w, l)
        set_defaults(ob, ns)
        put(ob, ("Stone", "Width"), w)
        put(ob, ("Stone", "Length"), l)
        put(ob, ("Bool", "BoolCutter"), True)
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        metal = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        put(ob, (None, "Subdivision"), 0)
        dg.update()
        cage = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        put(ob, (None, "Subdivision"), 2)
        frozen.append((cut, w, l, metal, cage, bpy.data.objects["Unit " + cut.title()].data))
    for ob in list(scene.collection.all_objects):
        ob.hide_render = True
    view = bpy.data.collections.new("Sheet")
    scene.collection.children.link(view)
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    view.objects.link(cam)
    cam.data.type = "ORTHO"
    gap = 8.5
    cam.data.ortho_scale = 3 * gap
    scene.camera = cam
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x, scene.render.resolution_y = 1500, 620
    scene.render.resolution_percentage = 100
    scene.display.render_aa = "16"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.show_cavity = True
    scene.view_settings.view_transform = "Standard"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    rows = (("3/4 view", Euler((radians(58), 0, radians(32)))), ("top", Euler((0, 0, 0))),
            ("side", Euler((radians(90), 0, radians(90)))), ("cage, Subdivision 0", Euler((radians(58), 0, radians(32)))))
    tmp = Path(bpy.app.tempdir or "/tmp")
    images = []
    for r, (title, rot) in enumerate(rows):
        for o in list(view.objects):
            if o != cam:
                bpy.data.objects.remove(o)
        m = rot.to_matrix()
        right, fwd, upv = m @ Vector((1, 0, 0)), m @ Vector((0, 0, -1)), m @ Vector((0, 1, 0))
        cam.matrix_world = Matrix.Translation(-fwd * 30.0 + upv * (0.0 if r == 1 else -0.3)) @ rot.to_matrix().to_4x4()

        def text(body, x, y, size):
            cu = bpy.data.curves.new("t", "FONT")
            cu.body, cu.size, cu.align_x = body, size, "CENTER"
            t = bpy.data.objects.new("t", cu)
            view.objects.link(t)
            t.parent = cam
            t.location = (x, y, -5.0)
            t.color = (0.0, 0.0, 0.0, 1.0)
        text(title, 0.0, 4.6, 0.45)
        for col, (cut, w, l, metal, cage, unit) in enumerate(frozen):
            at = right * (col - 1) * gap
            if r < 3:
                mo = bpy.data.objects.new("m", metal)
                mo.color = (0.86, 0.66, 0.24, 1.0)
                st = bpy.data.objects.new("s", unit)
                st.matrix_world = Matrix.Translation(at) @ Matrix.Diagonal((w, l, w, 1.0))
                st.color = (0.72, 0.84, 1.0, 1.0)
                view.objects.link(st)
            else:
                mo = bpy.data.objects.new("c", cage)
                mo.color = (0.15, 0.15, 0.15, 1.0)
                wf = mo.modifiers.new("w", "WIREFRAME")
                wf.thickness = 0.03
                text("%d verts" % len(cage.vertices), (col - 1) * gap, -4.4, 0.4)
            mo.matrix_world = Matrix.Translation(at)
            view.objects.link(mo)
            if r == 0:
                text("%s %g x %g mm" % (cut.title(), w, l), (col - 1) * gap, -4.4, 0.4)
        path = tmp / ("gem_cast_row%d.png" % r)
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(str(path))
        px = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        images.append(px.reshape(img.size[1], img.size[0], 4))
    sheet = np.concatenate(images[::-1], axis=0)   # пиксели Blender — снизу вверх
    out = bpy.data.images.new("sheet", sheet.shape[1], sheet.shape[0])
    out.pixels.foreach_set(sheet.ravel())
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    out.filepath_raw = str(PREVIEW)
    out.file_format = "PNG"
    out.save()
    print("preview: %s" % PREVIEW)


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ns = load(BUILD, "gem_cast_build")
    sys.path.insert(0, str(ROOT / "jewel_tools"))
    import gem_outline
    ns["go"] = gem_outline
    errors = []
    check_round(errors, ns)
    check_cuts(errors, ns)
    check_bools(errors, ns)
    check_cage(errors, ns)
    check_set(errors, ns)
    if "--preview" in args:
        render_sheet(ns)
    for e in errors:
        print("FAIL", e)
    print("GEM_CAST_TEST", "failed" if errors else "passed")
    if errors:
        sys.exit(1)


try:
    main()
except SystemExit:
    raise
except Exception:
    traceback.print_exc()
    sys.exit(1)
