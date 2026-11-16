# Проверка стыков изделия: детали, которые должны срастаться, обязаны пересекаться (взаимное проникновение > 0).
# Для каждой пары: число пересекающихся треугольников и наибольшая глубина захода вершин одной детали в другую;
# если пересечения нет — наименьший зазор. Плюс число отдельных оболочек в металле каждого объекта.
import bpy, bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

def metal(name, dg):
    """Треугольники металла объекта в мировых координатах (меш-часть вычисленной геометрии, без инстансов камня)."""
    ob = bpy.data.objects[name]
    e = ob.evaluated_get(dg)
    if ob.type == "MESH":
        g = e.evaluated_geometry()
        me, own = g.mesh, False
    else:
        me, own = e.to_mesh(), True
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.transform(ob.matrix_world)
    bm.verts.ensure_lookup_table()
    verts = [v.co.copy() for v in bm.verts]
    tris = [tuple(v.index for v in f.verts) for f in bm.faces]
    # оболочки
    seen, shells = set(), 0
    for v in bm.verts:
        if v.index in seen: continue
        shells += 1
        st = [v]
        while st:
            c = st.pop()
            if c.index in seen: continue
            seen.add(c.index)
            st.extend(e2.other_vert(c) for e2 in c.link_edges if e2.other_vert(c).index not in seen)
    bm.free()
    if own: e.to_mesh_clear()
    return verts, tris, shells

def inside(tree, p):
    """Точка внутри замкнутого тела: луч вверх пересекает нечётное число раз."""
    n, o, d = 0, p.copy(), Vector((0.137, 0.211, 1.0)).normalized()
    while True:
        hit = tree.ray_cast(o, d)
        if hit[0] is None: break
        n += 1
        o = hit[0] + d * 1e-5
    return n % 2 == 1

def check(pairs, parts):
    dg = bpy.context.evaluated_depsgraph_get(); dg.update()
    data = {n: metal(n, dg) for n in parts}
    trees = {n: BVHTree.FromPolygons(v, t) for n, (v, t, _s) in data.items()}
    out = {"shells": {n: data[n][2] for n in parts}, "joints": {}}
    for a, b, region in pairs:
        va = [p for p in data[a][0] if region is None or region(p)]
        cross = len(trees[a].overlap(trees[b]))
        depth, gap = 0.0, 1e9
        for p in va:
            loc, _n, _i, dist = trees[b].find_nearest(p)
            if loc is None: continue
            if inside(trees[b], p): depth = max(depth, dist)
            else: gap = min(gap, dist)
        out["joints"]["%s / %s" % (a, b)] = {"crossing_tris": cross, "max_penetration_mm": round(depth, 3),
                                             "min_gap_mm": round(gap, 3) if depth == 0 else 0.0}
    return out
