from __future__ import annotations

from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jewelry_suite

# Капля PadaniElementCurve.003 (PadaniRing.blend): (co, handle_left, handle_right, типы, radius, tilt)
DROP = [
    ((-2.4619, -0.4126, 9.1288), (-2.5198, -1.2224, 9.0699), (-2.3421, 1.2642, 9.2505), "ALIGNED", 1.072, 0.01),
    ((-0.0596, 2.3695, 9.4673), (-0.9935, 1.609, 9.3322), (1.0355, 1.5997, 9.3278), "FREE", 1.072, 0.0),
    ((2.3983, -0.387, 9.1287), (2.4175, 1.3413, 9.2854), (2.3891, -1.2133, 9.0538), "ALIGNED", 1.072, -0.05),
    ((-0.0019, -2.362, 9.4536), (2.0449, -2.3519, 9.4447), (-2.0486, -2.3722, 9.4626), "ALIGNED", 1.072, -0.01),
]
EPS = 1e-5


def make_curve(name: str, points, cyclic: bool = True) -> bpy.types.Object:
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(points) - 1)
    sp.use_cyclic_u = cyclic
    for p, (co, hl, hr, kind, radius, tilt) in zip(sp.bezier_points, points):
        p.handle_left_type = p.handle_right_type = kind
        p.co, p.handle_left, p.handle_right = co, hl, hr
        p.radius, p.tilt = radius, tilt
    ob = bpy.data.objects.new(name, cu)
    bpy.context.collection.objects.link(ob)
    return ob


def run(ob: bpy.types.Object, **kwargs) -> set[str]:
    bpy.context.view_layer.objects.active = ob
    return bpy.ops.curve.symmetrize_bezier(**kwargs)


def flip(v, k: int = 0) -> Vector:
    v = Vector(v)
    v[k] = -v[k]
    return v


def same(a, b) -> bool:
    return (Vector(a) - Vector(b)).length < EPS


def assert_symmetric(spline, k: int = 0) -> None:
    """Каждой точке есть зеркальный двойник: позиция, ручки (обмен), типы, радиус, tilt."""
    pts = list(spline.bezier_points)
    for p in pts:
        q = min(pts, key=lambda o: (o.co - flip(p.co, k)).length)
        assert same(q.co, flip(p.co, k)), (tuple(p.co), tuple(q.co))
        assert same(q.handle_left, flip(p.handle_right, k)) and same(q.handle_right, flip(p.handle_left, k))
        assert (q.handle_left_type, q.handle_right_type) == (p.handle_right_type, p.handle_left_type)
        assert abs(q.radius - p.radius) < EPS and abs(q.tilt - p.tilt) < EPS


def gn_normal_symmetry(curve_ob: bpy.types.Object, k: int = 0, n: int = 300) -> float:
    """Минимальный dot(n(M P), M n(P)) по нормалям, которые видит Geometry Nodes."""
    ng = bpy.data.node_groups.new("Probe", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    nodes, links = ng.nodes, ng.links
    info = nodes.new("GeometryNodeObjectInfo")
    info.inputs["Object"].default_value = curve_ob
    to_points = nodes.new("GeometryNodeCurveToPoints")
    to_points.mode = "COUNT"
    to_points.inputs["Count"].default_value = n
    store = nodes.new("GeometryNodeStoreNamedAttribute")
    store.data_type = "FLOAT_VECTOR"
    store.inputs["Name"].default_value = "nrm"
    to_verts = nodes.new("GeometryNodePointsToVertices")
    out = nodes.new("NodeGroupOutput")
    links.new(info.outputs["Geometry"], to_points.inputs["Curve"])
    links.new(to_points.outputs["Points"], store.inputs["Geometry"])
    links.new(to_points.outputs["Normal"], store.inputs["Value"])
    links.new(store.outputs["Geometry"], to_verts.inputs["Points"])
    links.new(to_verts.outputs["Mesh"], out.inputs["Geometry"])
    probe = bpy.data.objects.new("Probe", bpy.data.meshes.new("Probe"))
    bpy.context.collection.objects.link(probe)
    probe.modifiers.new("GN", "NODES").node_group = ng
    evaluated = probe.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    pos = [v.co.copy() for v in mesh.vertices]
    nrm = [Vector(a.vector) for a in mesh.attributes["nrm"].data]
    evaluated.to_mesh_clear()
    bpy.data.objects.remove(probe)
    bpy.data.node_groups.remove(ng)
    worst = 1.0
    for p, nv in zip(pos, nrm):
        j = min(range(len(pos)), key=lambda i: (pos[i] - flip(p, k)).length)
        worst = min(worst, nrm[j].dot(flip(nv, k)))
    return worst


jewelry_suite.register()

# --- Капля: +X на -X, верх/низ на ось ----------------------------------------
drop = make_curve("Drop", DROP)
sp = drop.data.splines[0]
right_before = (sp.bezier_points[2].co.copy(), sp.bezier_points[2].handle_left.copy(),
                sp.bezier_points[2].handle_right.copy())
assert gn_normal_symmetry(drop) < 0.999  # исходная капля не симметрична
assert run(drop) == {"FINISHED"}
sp = drop.data.splines[0]
pts = sp.bezier_points
assert len(pts) == 4
assert same(pts[2].co, right_before[0]) and same(pts[2].handle_left, right_before[1])  # мастер не тронут
assert pts[0].co.x < 0 and same(pts[0].co, flip(pts[2].co))  # начало сплайна осталось слева
for i in (1, 3):  # верх и низ — ровно на оси, ручки зеркальные
    assert pts[i].co.x == 0.0
    assert same(pts[i].handle_left, flip(pts[i].handle_right))
assert (pts[1].handle_left_type, pts[1].handle_right_type) == ("FREE", "FREE")  # носик капли сверху
bottom = pts[3].handle_right - pts[3].co  # низ гладкий (ALIGNED): ручки поперёк оси, длина та же
assert (pts[3].handle_left_type, pts[3].handle_right_type) == ("ALIGNED", "ALIGNED")
assert abs(bottom.y) < EPS and abs(bottom.z) < EPS
assert abs(bottom.length - (Vector(DROP[3][1]) - Vector(DROP[3][0])).length) < EPS
assert_symmetric(sp)
assert gn_normal_symmetry(drop) > 0.999
drop_result = [tuple(round(c, 4) for c in p.co) for p in pts]

# --- - на +, ось Y ---------------------------------------------------------
neg = make_curve("Neg", DROP)
assert run(neg, direction="NEGATIVE") == {"FINISHED"}
assert same(neg.data.splines[0].bezier_points[0].co, (-2.4619, -0.4126, 9.1288))  # левая — мастер
assert_symmetric(neg.data.splines[0])
rot = make_curve("RotY", [((y, x, z), (hy, hx, hz), (ry, rx, rz), t, r, tl)
                          for (x, y, z), (hx, hy, hz), (rx, ry, rz), t, r, tl in DROP])
assert run(rot, axis="Y") == {"FINISHED"}
assert_symmetric(rot.data.splines[0], k=1)

# --- Порог: точка дальше порога — не на оси, замкнутому нужно 2 -------------
far = make_curve("Far", DROP)
assert run(far, threshold=0.01) == {"CANCELLED"}  # верх в 0.06 от оси
assert same(far.data.splines[0].bezier_points[1].co, DROP[1][0])  # ничего не тронуто

# --- Разное число точек: справа 2, слева 1 — сплайн пересобирается -----------
uneven = make_curve("Uneven", [
    ((0, 2, 0), (-1, 2, 0), (1, 2, 0), "ALIGNED", 1.0, 0.0),
    ((2, 1, 0), (1.8, 1.6, 0), (2.2, 0.4, 0), "ALIGNED", 1.0, 0.2),
    ((2, -1, 0), (2.2, -0.4, 0), (1.8, -1.6, 0), "ALIGNED", 1.0, -0.1),
    ((0, -2, 0), (1, -2, 0), (-1, -2, 0), "ALIGNED", 1.0, 0.0),
    ((-2, 0, 0), (-2, -1, 0), (-2, 1, 0), "ALIGNED", 1.0, 0.0),
])
assert run(uneven) == {"FINISHED"}
assert len(uneven.data.splines) == 1 and len(uneven.data.splines[0].bezier_points) == 6
assert uneven.data.splines[0].use_cyclic_u
assert_symmetric(uneven.data.splines[0])

# --- Открытая дуга с одной точкой на оси --------------------------------------
arc = make_curve("Arc", [
    ((-2.1, 0, 0), (-2.1, -1, 0), (-2.1, 1, 0), "ALIGNED", 1.0, 0.0),
    ((0.03, 2, 0), (-1, 2, 0), (1, 2.1, 0), "ALIGNED", 1.0, 0.3),
    ((2, 0, 0), (2, 1, 0), (2, -1, 0), "ALIGNED", 1.0, 0.0),
], cyclic=False)
assert run(arc) == {"FINISHED"}
pts = arc.data.splines[0].bezier_points
assert pts[1].co.x == 0.0 and same(pts[1].handle_left, flip(pts[1].handle_right))
assert (pts[1].handle_left_type, pts[1].handle_right_type) == ("ALIGNED", "ALIGNED")
assert abs((pts[1].handle_right - pts[1].co).y) < EPS  # гладкая вершина дуги без излома
assert_symmetric(arc.data.splines[0])

# --- Edit Mode: правка сохраняется после выхода из режима ---------------------
edit = make_curve("Edit", DROP)
bpy.context.view_layer.objects.active = edit
edit.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
assert run(edit) == {"FINISHED"}
bpy.ops.object.mode_set(mode="OBJECT")
assert [tuple(round(c, 4) for c in p.co) for p in edit.data.splines[0].bezier_points] == drop_result
assert_symmetric(edit.data.splines[0])

jewelry_suite.unregister()
print("CURVE_SYMMETRY_TEST", {"drop": drop_result})
