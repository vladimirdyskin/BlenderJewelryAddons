"""
My_Gem_Channel — просвет: сплошной катер вдоль ряда камней. Модификатор на отдельном объекте
без меша, камни — с объекта Stones (кривая с My_Gems_Curve), как в My_Gem_Cutters / My_Prongs.
Boolean по нему ставится отдельно: у катеров и просвета свои операнды, внутри каждого
ничего не перекрывается (Manifold перекрытия внутри одного операнда не склеивает).

Схема:
    Камни по порядку и соседи — stone_rows() из tools/gn_gem_cutters_build.py.
    Путь — Catmull-Rom через центры камней (+ Up * Z Offset), куски рвутся там, где зазор больше
    Max Gap; замкнутый ряд — замкнутый путь. На концах куска — точка за крайним камнем:
    ось X камня (gem_along) наружу от соседа, на Extend.
    Сечение — прямоугольник Width x Height со скруглением Round (0 — углы, 1 — овал),
    верх сечения — gem_up (Set Curve Normal Free). Curve to Mesh с Fill Caps — замкнутый меш.
    Scale by Stone: Width, Height, Z Offset и Extend умножаются на размер камня (gem_size),
    вдоль ряда плавно (Scale у Curve to Mesh).
    Расчёт в координатах Stones, в конце — to_self_space() (матрица Object Info Relative).

Интерфейс: сокеты только добавляются, повторный запуск не сбрасывает значения на модификаторах.
Узлы пересобираются целиком.
"""

import bpy
import importlib.util
import os

GROUP_NAME = "My_Gem_Channel"
CUTTERS_PATH = os.path.expanduser("~/GitHub/BlenderJewelryAddons/tools/gn_gem_cutters_build.py")

# (имя, тип, default, min, max, панель, subtype)
SOCKETS = [
    ("Stones", "NodeSocketObject", None, None, None, None, None),
    ("Width", "NodeSocketFloat", 0.6, 0.0, None, None, None),
    ("Height", "NodeSocketFloat", 0.6, 0.0, None, None, None),
    ("Round", "NodeSocketFloat", 1.0, 0.0, 1.0, None, "FACTOR"),
    ("Z Offset", "NodeSocketFloat", -0.5, None, None, None, None),
    ("Extend", "NodeSocketFloat", 0.5, None, None, None, None),
    ("Scale by Stone", "NodeSocketBool", True, None, None, None, None),
    ("Max Gap", "NodeSocketFloat", 1.0, 0.0, None, None, None),
]

CHANNEL_RES = 12   # точек на участок между камнями (Catmull-Rom)
FILLET_COUNT = 6   # точек на скругление угла сечения


def load_cutters():
    # stone_rows / to_self_space / load_prongs — общие с My_Gem_Cutters
    spec = importlib.util.spec_from_file_location("gn_gem_cutters_ref", CUTTERS_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_channel(b, pr, cap, pos, up, along):
    """Меш просвета в координатах Stones. cap — камни по порядку с соседями (stone_rows)."""
    b.section("Channel")
    x, y = 2860, 200
    pts = cap.outputs["Geometry"]

    def store(geo, name, dtype, value, xx, yy):
        n = b.node("GeometryNodeStoreNamedAttribute", xx, yy, data_type=dtype, domain="POINT")
        n.inputs["Name"].default_value = name
        b.link(geo, n.inputs["Geometry"])
        b._set(b.enabled(n, "Value"), value)
        return n.outputs["Geometry"]

    size_attr = b.named(pr.ATTR_SIZE, "FLOAT", x, y - 200)
    size = b.switch("FLOAT", size_attr.outputs["Exists"], 1.0, size_attr.outputs["Attribute"], x + 180, y - 200)
    k = b.switch("FLOAT", b.g("Scale by Stone"), 1.0, size, x + 360, y - 200)
    start = b.boolean("NOT", cap.outputs["Prev OK"], None, x, y - 400)
    end = b.boolean("NOT", cap.outputs["Next OK"], None, x, y - 560)
    # номер куска: растёт на каждом камне без связи с предыдущим
    acc = b.node("GeometryNodeAccumulateField", x + 180, y - 400, data_type="FLOAT", domain="POINT")
    b.link(start, acc.inputs["Value"])
    idx = b.node("GeometryNodeInputIndex", x, y - 720).outputs[0]

    # точки пути: центры камней + Z Offset, с номером куска, порядком, верхом и масштабом
    line = store(pts, "_ch_g", "FLOAT", acc.outputs["Leading"], x + 560, y)
    line = store(line, "_ch_w", "FLOAT", idx, x + 760, y)
    line = store(line, "_ch_up", "FLOAT_VECTOR", up, x + 960, y)
    line = store(line, "_ch_k", "FLOAT", k, x + 1160, y)
    line = store(line, "_ch_ext", "FLOAT", b.math("MULTIPLY", b.g("Extend"), k, x + 960, y - 200),
                 x + 1360, y)

    def tail(sel, other_p, w_shift, yy):
        # точка за крайним камнем: ось X камня наружу от соседа, на Channel Extend
        keep = b.node("GeometryNodeDeleteGeometry", x + 1600, yy, domain="POINT")
        b.link(line, keep.inputs["Geometry"])
        b.link(b.boolean("NOT", sel, None, x + 1600, yy - 160), keep.inputs["Selection"])
        outside = b.vmath("DOT_PRODUCT", along, b.vmath("SUBTRACT", pos, other_p, x + 1800, yy - 160), x + 1980, yy - 160)
        away = b.vmath("SCALE", along, b.math("SIGN", outside, None, x + 2160, yy - 160), x + 2340, yy - 160)
        ext = b.named("_ch_ext", "FLOAT", x + 2160, yy - 320).outputs["Attribute"]
        mv = b.node("GeometryNodeSetPosition", x + 2520, yy)
        b.link(keep.outputs["Geometry"], mv.inputs["Geometry"])
        b.link(b.vmath("SCALE", away, ext, x + 2520, yy - 160), mv.inputs["Offset"])
        w = b.math("ADD", b.named("_ch_w", "FLOAT", x + 2520, yy - 320).outputs["Attribute"], w_shift, x + 2700, yy - 320)
        return store(mv.outputs["Geometry"], "_ch_w", "FLOAT", w, x + 2880, yy)

    head = tail(start, cap.outputs["Next P"], -0.5, y - 1100)
    foot = tail(end, cap.outputs["Prev P"], 0.5, y - 1500)
    join = b.node("GeometryNodeJoinGeometry", x + 3100, y)
    for geo in (line, head, foot):
        b.link(geo, join.inputs["Geometry"])
    moved = b.node("GeometryNodeSetPosition", x + 3300, y)
    b.link(join.outputs["Geometry"], moved.inputs["Geometry"])
    b.link(b.vmath("SCALE", b.named("_ch_up", "FLOAT_VECTOR", x + 3100, y - 200).outputs["Attribute"],
                   b.math("MULTIPLY", b.g("Z Offset"),
                          b.named("_ch_k", "FLOAT", x + 2920, y - 360).outputs["Attribute"], x + 3100, y - 360),
                   x + 3300, y - 200), moved.inputs["Offset"])

    # путь: Catmull-Rom по кускам, замкнутый ряд — замкнутый путь
    p2c = b.node("GeometryNodePointsToCurves", x + 3500, y)
    b.link(moved.outputs["Geometry"], p2c.inputs["Points"])
    b.link(b.named("_ch_g", "FLOAT", x + 3300, y - 400).outputs["Attribute"], p2c.inputs["Curve Group ID"])
    b.link(b.named("_ch_w", "FLOAT", x + 3300, y - 560).outputs["Attribute"], p2c.inputs["Weight"])
    starts = b.stat(pts, start, "FLOAT", x + 3300, y - 720)          # среднее: 0 — разрывов нет
    closed = b.cmp("LESS_THAN", starts, 1e-6, x + 3500, y - 720)
    cyc = b.node("GeometryNodeSetSplineCyclic", x + 3700, y)
    b.link(p2c.outputs["Curves"], cyc.inputs["Geometry"])
    b.link(closed, cyc.inputs["Cyclic"])
    smooth = b.node("GeometryNodeCurveSplineType", x + 3900, y, spline_type="CATMULL_ROM")
    b.link(cyc.outputs["Geometry"], smooth.inputs["Curve"])
    res = b.node("GeometryNodeSetSplineResolution", x + 4100, y)
    b.link(smooth.outputs["Curve"], res.inputs["Curve"])
    res.inputs["Resolution"].default_value = CHANNEL_RES
    nrm = b.node("GeometryNodeSetCurveNormal", x + 4300, y)
    b.link(res.outputs["Curve"], nrm.inputs["Curve"])
    nrm.inputs["Mode"].default_value = "Free"
    b.link(b.named("_ch_up", "FLOAT_VECTOR", x + 4100, y - 200).outputs["Attribute"], nrm.inputs["Normal"])

    # сечение: прямоугольник со скруглёнными углами; X профиля идёт по нормали пути (gem_up),
    # поэтому высота — в Width прямоугольника (проверено замером)
    rect = b.node("GeometryNodeCurvePrimitiveQuadrilateral", x + 3900, y - 1000, mode="RECTANGLE")
    b.link(b.g("Height"), rect.inputs["Width"])
    b.link(b.g("Width"), rect.inputs["Height"])
    fil = b.node("GeometryNodeFilletCurve", x + 4100, y - 1000)
    b.link(rect.outputs["Curve"], fil.inputs["Curve"])
    fil.inputs["Mode"].default_value = "Poly"
    fil.inputs["Count"].default_value = FILLET_COUNT
    fil.inputs["Limit Radius"].default_value = True
    half_min = b.math("MULTIPLY", b.math("MINIMUM", b.g("Width"), b.g("Height"), x + 3900, y - 1200),
                      0.5, x + 4080, y - 1200)
    b.link(b.math("MULTIPLY", b.g("Round"), half_min, x + 4260, y - 1200), fil.inputs["Radius"])

    c2m = b.node("GeometryNodeCurveToMesh", x + 4500, y)
    b.link(nrm.outputs["Curve"], c2m.inputs["Curve"])
    b.link(fil.outputs["Curve"], c2m.inputs["Profile Curve"])
    b.link(b.named("_ch_k", "FLOAT", x + 4300, y - 200).outputs["Attribute"], c2m.inputs["Scale"])
    c2m.inputs["Fill Caps"].default_value = True
    rm = b.node("GeometryNodeRemoveAttribute", x + 4700, y)
    rm.inputs["Pattern Mode"].default_value = "Wildcard"
    rm.inputs["Name"].default_value = "_ch_*"
    b.link(c2m.outputs["Mesh"], rm.inputs["Geometry"])
    return rm.outputs["Geometry"]


def build_group():
    cu = load_cutters()
    pr = cu.load_prongs()
    pr.SOCKETS = SOCKETS
    ng = bpy.data.node_groups.get(GROUP_NAME)
    if ng is None:
        ng = bpy.data.node_groups.new(GROUP_NAME, "GeometryNodeTree")
    pr.ensure_interface(ng)
    ng.nodes.clear()

    b = pr.B(ng, -300)
    r = cu.stone_rows(b, pr)
    mesh = build_channel(b, pr, r["cap"], r["pos"], r["up"], r["along"])
    b.frame = None
    out = cu.to_self_space(b, mesh, 7800, 200)
    gout = b.node("NodeGroupOutput", 8300, 200)
    b.link(out, gout.inputs["Geometry"])

    print("Node group '%s' rebuilt: %d nodes" % (GROUP_NAME, len(ng.nodes)))
    return ng


def setup(stones, name=None, values=None):
    """Объект без меша с модификатором, в коллекции объекта Stones. values — {вход: значение}."""
    ng = build_group()
    src = bpy.data.objects[stones]
    name = name or "%s Channel" % stones
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, bpy.data.meshes.new(name))
        src.users_collection[0].objects.link(ob)
    md = ob.modifiers.get(GROUP_NAME) or ob.modifiers.new(GROUP_NAME, "NODES")
    md.node_group = ng
    ids = {it.name: it.identifier for it in ng.interface.items_tree
           if it.item_type == "SOCKET" and it.in_out == "INPUT"}
    getattr(md.properties.inputs, ids["Stones"]).value = src
    for k, v in (values or {}).items():
        getattr(md.properties.inputs, ids[k]).value = v
    ob.update_tag()
    print("Channel object '%s' set up on '%s'" % (ob.name, stones))
    return ob


def main():
    build_group()


if __name__ == "__main__":
    main()
