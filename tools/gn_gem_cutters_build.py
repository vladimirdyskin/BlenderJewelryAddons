"""
My_Gem_Cutters — катеры для камней. Модификатор на отдельном объекте без меша.
Два катера: Gap Cutter — между камнями, Stone Cutter — в центре каждого камня.

Камни берутся с объекта Stones (кривая с My_Gems_Curve) через Object Info: инстансы
с атрибутами gem_order, gem_up, gem_along, gem_r (см. tools/gn_gems_curve_build.py).

Схема:
    Object Info (Original) -> Capture Instance Transform -> Instances to Points
    -> Sort Elements по gem_order. Соседи — следующий и предыдущий по кругу (Evaluate at Index).
    Пара соединена, если зазор не больше Max Gap: у открытого ряда пара «последний -> первый»
    отпадает по зазору.

    Between: каждый камень даёт две заготовки, вперёд и назад (Duplicate Elements):
        вперёд — зазор со следующим, либо конец ряда при Cutters at Ends;
        назад  — только начало ряда при Cutters at Ends (остальные зазоры посчитал сосед).
        В зазоре: P + dir * (r + gap / 2), Z — среднее gem_up двух камней, X — к соседу.
        На конце: P + dir * (r + gap / 2), gap — зазор с единственным соседом, чтобы катер стоял
        от края так же, как в ряду; dir — ось X камня (gem_along) наружу от соседа: хорда
        на изгибе увела бы катер с плоскости камня. Z — gem_up камня.
        Плюс Gap Z Offset по Z катера.
    On Stones: катер с матрицей камня (положение, поворот, размер, у отражённых копий —
        отражение), умноженной на Stone Scale XY/Z; Stone Z Offset — по gem_up в координатах
        Stones, не зависит от размера камня.

    Всё считается в координатах объекта Stones: gem_up и gem_along — вектора в его
    пространстве, Object Info (Relative) атрибуты не поворачивает. В конце Transform Geometry
    матрицей Stones относительно объекта катеров (выход Transform у Object Info Relative).

Realize: катеры становятся мешем, отражённым переворачиваются грани.

Помощники сборки (B, ensure_interface) — из tools/gn_prongs_build.py.
Интерфейс: сокеты только добавляются, повторный запуск не сбрасывает значения
на модификаторах. Узлы пересобираются целиком.
"""

import bpy
import importlib.util
import os

GROUP_NAME = "My_Gem_Cutters"
PRONGS_PATH = os.path.expanduser("~/GitHub/BlenderJewelryAddons/tools/gn_prongs_build.py")

# (имя, тип, default, min, max, панель, subtype)
SOCKETS = [
    ("Stones", "NodeSocketObject", None, None, None, None, None),
    ("Realize", "NodeSocketBool", False, None, None, None, None),
    ("Between", "NodeSocketBool", True, None, None, "Gap Cutters", None),
    ("Gap Cutter", "NodeSocketObject", None, None, None, "Gap Cutters", None),
    ("Gap Scale XY", "NodeSocketFloat", 1.0, 0.0, None, "Gap Cutters", None),
    ("Gap Scale Z", "NodeSocketFloat", 1.0, 0.0, None, "Gap Cutters", None),
    ("Gap Z Offset", "NodeSocketFloat", 0.0, None, None, "Gap Cutters", None),
    ("Cutters at Ends", "NodeSocketBool", False, None, None, "Gap Cutters", None),
    ("Max Gap", "NodeSocketFloat", 1.0, 0.0, None, "Gap Cutters", None),
    ("On Stones", "NodeSocketBool", True, None, None, "Stone Cutters", None),
    ("Stone Cutter", "NodeSocketObject", None, None, None, "Stone Cutters", None),
    ("Stone Scale XY", "NodeSocketFloat", 1.0, 0.0, None, "Stone Cutters", None),
    ("Stone Scale Z", "NodeSocketFloat", 1.0, 0.0, None, "Stone Cutters", None),
    ("Stone Z Offset", "NodeSocketFloat", 0.0, None, None, "Stone Cutters", None),
]


def load_prongs():
    # свой экземпляр модуля: подмена SOCKETS не задевает My_Prongs
    spec = importlib.util.spec_from_file_location("gn_prongs_ref", PRONGS_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.SOCKETS = SOCKETS
    return mod


def build_group():
    pr = load_prongs()
    ng = bpy.data.node_groups.get(GROUP_NAME)
    if ng is None:
        ng = bpy.data.node_groups.new(GROUP_NAME, "GeometryNodeTree")
    pr.ensure_interface(ng)
    ng.nodes.clear()

    b = pr.B(ng, -300)

    def shape(sock_name, x, y):
        info = b.node("GeometryNodeObjectInfo", x, y, transform_space="ORIGINAL")
        info.inputs["As Instance"].default_value = False
        b.link(b.g(sock_name), info.inputs["Object"])
        return info.outputs["Geometry"]

    def gate(sock_name, geo, x, y):
        # выключено — пустая геометрия
        n = b.node("GeometryNodeSwitch", x, y, input_type="GEOMETRY")
        b.link(b.g(sock_name), n.inputs["Switch"])
        b.link(geo, n.inputs["True"])
        return n.outputs["Output"]

    # --- камни по порядку вдоль ряда, в координатах объекта Stones ---
    b.section("Stones in Order")
    src = b.node("GeometryNodeObjectInfo", 0, 200, transform_space="ORIGINAL")
    b.link(b.g("Stones"), src.inputs["Object"])
    xf = b.node("GeometryNodeCaptureAttribute", 200, 200, domain="INSTANCE")
    xf.capture_items.new("MATRIX", "Transform")
    b.link(src.outputs["Geometry"], xf.inputs["Geometry"])
    b.link(b.node("GeometryNodeInstanceTransform", 0, -60).outputs["Transform"], xf.inputs["Transform"])
    order = b.named(pr.ATTR_ORDER, "FLOAT", 200, -120)
    to_pts = b.node("GeometryNodeInstancesToPoints", 400, 200)
    b.link(xf.outputs["Geometry"], to_pts.inputs["Instances"])
    b.link(order.outputs["Exists"], to_pts.inputs["Selection"])
    sort = b.node("GeometryNodeSortElements", 600, 200, domain="POINT")
    b.link(to_pts.outputs["Points"], sort.inputs["Geometry"])
    b.link(order.outputs["Attribute"], sort.inputs["Sort Weight"])
    stones = sort.outputs["Geometry"]
    stone_xf = xf.outputs["Transform"]

    pos = b.node("GeometryNodeInputPosition", 1020, -160).outputs[0]
    up = b.named(pr.ATTR_UP, "FLOAT_VECTOR", 1020, -280).outputs["Attribute"]
    along = b.named(pr.ATTR_ALONG, "FLOAT_VECTOR", 1020, -1240).outputs["Attribute"]
    rad = b.named(pr.ATTR_R, "FLOAT", 1020, -440).outputs["Attribute"]

    # --- соседи: следующий и предыдущий по кругу ---
    b.section("Neighbours")
    size = b.node("GeometryNodeAttributeDomainSize", 840, 200, component="POINTCLOUD")
    b.link(stones, size.inputs["Geometry"])
    count = size.outputs["Point Count"]
    idx = b.node("GeometryNodeInputIndex", 840, -60).outputs[0]
    next_i = b.math("FLOORED_MODULO", b.math("ADD", idx, 1.0, 1020, 200), count, 1200, 200)
    prev_i = b.math("FLOORED_MODULO", b.math("SUBTRACT", idx, 1.0, 1020, 20), count, 1200, 20)

    next_p = b.at_index(pos, next_i, "FLOAT_VECTOR", 1400, 200)
    next_u = b.at_index(up, next_i, "FLOAT_VECTOR", 1400, 40)
    next_r = b.at_index(rad, next_i, "FLOAT", 1400, -120)
    prev_p = b.at_index(pos, prev_i, "FLOAT_VECTOR", 1400, -280)
    prev_u = b.at_index(up, prev_i, "FLOAT_VECTOR", 1400, -440)
    prev_r = b.at_index(rad, prev_i, "FLOAT", 1400, -600)

    # два камня: пара через конец ряда — это тот же зазор, его не считать второй раз
    many = b.cmp("GREATER_THAN", count, 2.0, 1400, -780)
    not_last = b.cmp("LESS_THAN", idx, b.math("SUBTRACT", count, 1.0, 1220, -920), 1400, -920)
    not_first = b.cmp("GREATER_THAN", idx, 0.0, 1400, -1060)

    def linked(other_p, other_r, inner_ok, y):
        gap = b.math("SUBTRACT", b.vmath("DISTANCE", pos, other_p, 1620, y), rad, 1800, y)
        gap = b.math("SUBTRACT", gap, other_r, 1980, y)
        close = b.cmp("LESS_EQUAL", gap, b.g("Max Gap"), 2160, y)
        return b.boolean("AND", close, b.boolean("OR", inner_ok, many, 2160, y - 180), 2340, y)

    next_ok = linked(next_p, next_r, not_last, 200)
    prev_ok = linked(prev_p, prev_r, not_first, -240)

    # Evaluate at Index считается по индексам — зафиксировать до Duplicate
    cap = b.capture(stones, {
        "Next P": ("VECTOR", next_p), "Next Up": ("VECTOR", next_u), "Next R": ("FLOAT", next_r),
        "Next OK": ("BOOLEAN", next_ok),
        "Prev P": ("VECTOR", prev_p), "Prev Up": ("VECTOR", prev_u), "Prev R": ("FLOAT", prev_r),
        "Prev OK": ("BOOLEAN", prev_ok),
    }, 2580, 200)

    # --- между камнями: заготовки вперёд и назад ---
    b.section("Gap Sites")
    dup = b.node("GeometryNodeDuplicateElements", 2860, 200, domain="POINT")
    b.link(cap.outputs["Geometry"], dup.inputs["Geometry"])
    dup.inputs["Amount"].default_value = 2
    back = b.cmp("GREATER_THAN", dup.outputs["Duplicate Index"], 0.5, 2860, -60)

    nb_p = b.switch("VECTOR", back, cap.outputs["Next P"], cap.outputs["Prev P"], 3080, 200)
    ot_p = b.switch("VECTOR", back, cap.outputs["Prev P"], cap.outputs["Next P"], 3080, 20)
    nb_u = b.switch("VECTOR", back, cap.outputs["Next Up"], cap.outputs["Prev Up"], 3080, -160)
    nb_r = b.switch("FLOAT", back, cap.outputs["Next R"], cap.outputs["Prev R"], 3080, -340)
    ot_r = b.switch("FLOAT", back, cap.outputs["Prev R"], cap.outputs["Next R"], 3080, -520)
    ok = b.switch("BOOLEAN", back, cap.outputs["Next OK"], cap.outputs["Prev OK"], 3080, -700)

    ends = b.g("Cutters at Ends")
    keep = b.switch("BOOLEAN", back,
                    b.boolean("OR", ok, ends, 3300, -700),
                    b.boolean("AND", b.boolean("NOT", ok, None, 3300, -880), ends, 3480, -880),
                    3660, -700)

    # направление: к соседу или, на конце ряда, ось X камня наружу от соседа
    to_nb = b.vmath("NORMALIZE", b.vmath("SUBTRACT", nb_p, pos, 3300, 200), None, 3480, 200)
    outside = b.vmath("DOT_PRODUCT", along, b.vmath("SUBTRACT", pos, ot_p, 3300, 20), 3480, 20)
    away = b.vmath("SCALE", along, b.math("SIGN", outside, None, 3660, 20), 3840, 20)
    dirv = b.switch("VECTOR", ok, away, to_nb, 3660, 200)

    # зазор: к соседу или, на конце, тот же, что с единственным соседом
    gap_nb = b.math("SUBTRACT", b.math("SUBTRACT", b.vmath("DISTANCE", nb_p, pos, 3300, -160), rad, 3480, -160),
                    nb_r, 3660, -160)
    gap_ot = b.math("SUBTRACT", b.math("SUBTRACT", b.vmath("DISTANCE", ot_p, pos, 3300, -340), rad, 3480, -340),
                    ot_r, 3660, -340)
    gap_ot = b.math("MAXIMUM", gap_ot, 0.0, 3840, -340)  # один камень в ряду
    half = b.math("MULTIPLY", b.switch("FLOAT", ok, gap_ot, gap_nb, 4020, -160), 0.5, 4200, -160)
    site = b.vmath("ADD", pos, b.vmath("SCALE", dirv, b.math("ADD", rad, half, 4380, -160), 4560, -160), 4740, -160)

    both = b.vmath("NORMALIZE", b.vmath("ADD", up, nb_u, 4020, -520), None, 4200, -520)
    site_up = b.switch("VECTOR", ok, up, both, 4380, -520)
    site = b.vmath("ADD", site, b.vmath("SCALE", site_up, b.g("Gap Z Offset"), 4560, -520), 4920, -160)
    travel = b.switch("VECTOR", back, dirv, b.vmath("SCALE", dirv, -1.0, 4380, -700), 4560, -700)

    # позиция меняется ниже — зафиксировать до Set Position
    sites = b.capture(dup.outputs["Geometry"], {
        "Site": ("VECTOR", site), "Up": ("VECTOR", site_up), "T": ("VECTOR", travel), "Keep": ("BOOLEAN", keep),
    }, 5120, 200)

    # --- катеры между камнями ---
    b.section("Gap Cutters")
    cut = b.node("GeometryNodeDeleteGeometry", 5380, 200, domain="POINT")
    b.link(sites.outputs["Geometry"], cut.inputs["Geometry"])
    b.link(b.boolean("NOT", sites.outputs["Keep"], None, 5380, -60), cut.inputs["Selection"])
    place = b.node("GeometryNodeSetPosition", 5600, 200)
    b.link(cut.outputs["Geometry"], place.inputs["Geometry"])
    b.link(sites.outputs["Site"], place.inputs["Position"])

    rot = b.node("FunctionNodeAxesToRotation", 5600, -200, primary_axis="Z", secondary_axis="X")
    b.link(sites.outputs["Up"], rot.inputs["Primary Axis"])
    b.link(sites.outputs["T"], rot.inputs["Secondary Axis"])
    scale = b.node("ShaderNodeCombineXYZ", 5600, -400)
    b.link(b.g("Gap Scale XY"), scale.inputs["X"])
    b.link(b.g("Gap Scale XY"), scale.inputs["Y"])
    b.link(b.g("Gap Scale Z"), scale.inputs["Z"])

    iop = b.node("GeometryNodeInstanceOnPoints", 5840, 200)
    b.link(place.outputs["Geometry"], iop.inputs["Points"])
    b.link(shape("Gap Cutter", 5600, -600), iop.inputs["Instance"])
    b.link(rot.outputs["Rotation"], iop.inputs["Rotation"])
    b.link(scale.outputs["Vector"], iop.inputs["Scale"])
    gap_out = gate("Between", iop.outputs["Instances"], 6060, 200)

    # --- катеры в центре камня: матрица камня ---
    b.section("Stone Cutters")
    lift = b.node("FunctionNodeCombineTransform", 2860, -1400)
    b.link(b.vmath("SCALE", up, b.g("Stone Z Offset"), 2660, -1400), lift.inputs["Translation"])
    shrink = b.node("FunctionNodeCombineTransform", 2860, -1640)
    s_scale = b.node("ShaderNodeCombineXYZ", 2660, -1640)
    b.link(b.g("Stone Scale XY"), s_scale.inputs["X"])
    b.link(b.g("Stone Scale XY"), s_scale.inputs["Y"])
    b.link(b.g("Stone Scale Z"), s_scale.inputs["Z"])
    b.link(s_scale.outputs["Vector"], shrink.inputs["Scale"])
    m1 = b.node("FunctionNodeMatrixMultiply", 3080, -1400)
    b.link(lift.outputs["Transform"], m1.inputs[0])
    b.link(stone_xf, m1.inputs[1])
    m2 = b.node("FunctionNodeMatrixMultiply", 3300, -1400)
    b.link(m1.outputs[0], m2.inputs[0])
    b.link(shrink.outputs["Transform"], m2.inputs[1])

    iop2 = b.node("GeometryNodeInstanceOnPoints", 3080, -1100)
    b.link(stones, iop2.inputs["Points"])
    b.link(shape("Stone Cutter", 2860, -1100), iop2.inputs["Instance"])
    set_xf = b.node("GeometryNodeSetInstanceTransform", 3520, -1100)
    b.link(iop2.outputs["Instances"], set_xf.inputs["Instances"])
    b.link(m2.outputs[0], set_xf.inputs["Transform"])
    stone_out = gate("On Stones", set_xf.outputs["Instances"], 6060, -1100)

    # --- выход: в координаты объекта катеров ---
    b.section("To Self Space")
    join = b.node("GeometryNodeJoinGeometry", 6300, 200)
    b.link(gap_out, join.inputs["Geometry"])
    b.link(stone_out, join.inputs["Geometry"])
    # атрибуты камней перешли на катеры: иначе их примут за камни
    rm = b.node("GeometryNodeRemoveAttribute", 6500, 200)
    rm.inputs["Pattern Mode"].default_value = "Wildcard"
    rm.inputs["Name"].default_value = "gem_*"
    b.link(join.outputs["Geometry"], rm.inputs["Geometry"])
    rel = b.node("GeometryNodeObjectInfo", 6500, -200, transform_space="RELATIVE")
    b.link(b.g("Stones"), rel.inputs["Object"])
    tf = b.node("GeometryNodeTransform", 6720, 200)
    tf.inputs["Mode"].default_value = "Matrix"
    b.link(rm.outputs["Geometry"], tf.inputs["Geometry"])
    b.link(rel.outputs["Transform"], tf.inputs["Transform"])

    b.frame = None
    done = b.realize(tf.outputs["Geometry"], 6940, 200)
    gout = b.node("NodeGroupOutput", 8140, 200)
    b.link(done, gout.inputs["Geometry"])

    print("Node group '%s' rebuilt: %d nodes" % (GROUP_NAME, len(ng.nodes)))
    return ng


def setup(stones, gap_cutter=None, stone_cutter=None, name=None):
    """Объект без меша с модификатором, в коллекции объекта Stones. Значения входов не сбрасывает."""
    ng = build_group()
    src = bpy.data.objects[stones]
    name = name or "%s Cutters" % stones
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, bpy.data.meshes.new(name))
        src.users_collection[0].objects.link(ob)
    md = ob.modifiers.get(GROUP_NAME) or ob.modifiers.new(GROUP_NAME, "NODES")
    md.node_group = ng
    ids = {it.name: it.identifier for it in ng.interface.items_tree
           if it.item_type == "SOCKET" and it.in_out == "INPUT"}
    getattr(md.properties.inputs, ids["Stones"]).value = src
    for sock, obj in (("Gap Cutter", gap_cutter), ("Stone Cutter", stone_cutter)):
        if obj:
            getattr(md.properties.inputs, ids[sock]).value = bpy.data.objects[obj]
    ob.update_tag()
    print("Cutters object '%s' set up on '%s'" % (ob.name, stones))
    return ob


def main():
    build_group()


if __name__ == "__main__":
    main()
