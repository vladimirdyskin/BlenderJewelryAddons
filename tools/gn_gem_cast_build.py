"""
My_Gem_Cast — каст с крапанами под некруглую огранку. Логика и входы — как у My_Round_Cast
(tools/gn_round_cast_build.py), только вместо окружности — контур рундиста огранки.

Камень: Diam — камень-единица (габарит XY 1 x 1 с центром в начале координат, рундист снизу на
z = 0, высоты на единицу ширины), на выходе — его инстанс с масштабом (Width, Length, Width).
Bounding Box геометрии Diam: table_z = max.z * Width, culet_z = min.z * Width,
bottom_z = culet_z - Cast/Below Culet — на нём кончаются и каст, и крапана.

Контур: Outline — меш-прототип в тех же единичных координатах, плоскость z = 0:
    управляющая петля рундиста — вершины, соединённые рёбрами в замкнутый контур, атрибут corner
        (FLOAT, POINT: 1 — острый угол), как в jewel_tools/gem_setting.py;
    места крапанов — вершины без рёбер (на пределе петли).
    В группе прототип масштабируется на (Width, Length, 1): подразделение аффинно-инвариантно,
    предел масштабированной петли — масштабированный предел.
Рамки Loop и Limit Curve и смещение петли с компенсацией сглаживания — из gem_setting.py:
    предел петли — сплайн Безье, нормаль контура у крапана — по ближайшей точке предела
    (в острой вершине — биссектриса); вынос по биссектрисе b * s: острая вершина — митра
    1 / cos(половины поворота), гладкая — локальная оценка + один шаг Якоби.

    Крапан: ось через точку место + n * ø * (0.5 - Intersection/100) на z = 0, n — наружная
        нормаль предела; наклон Tilt наружу кверху вокруг касательной; низ (торец поперёк оси)
        на bottom_z, основание купола на table_z + Above Table. Клетка 12 вершин и защита
        от короткого ствола — как в My_Round_Cast. Ось X крапана — по n (сторона к камню).
    Set (камень закреплён): кончик опущен и наклонён к камню — клетка и расчёт из My_Round_Cast
        (build_prong_cage). Путь по короне один на все крапана — по короткой стороне камня:
        Width * (0.5 - max |x| вершин площадки камня-единицы). Посадка: оболочка камня,
        увеличенного по XY в SET_GROW, и заданный Cutter ниже рундиста; оболочка вычитается
        из крапанов и без BoolCutter.
    Каст: трубка-клетка вдоль петли, N точек x 4 угла профиля, четыре продольные петли —
        управляющая петля, смещённая по нормали на d: наружная верхняя d = XY Offset
        (z = Z Offset), наружная нижняя d - H tan Tilt (z = bottom_z, H — высота каста, не меньше
        MIN_CAST) — стенка параллельна крапанам; внутренние на Cast Thickness глубже.
        Продольные рёбра — crease 1, рёбра колец в острых вершинах — crease 1.
    После SubD: прорезь (параллелепипед HeightBool на середине высоты + OffsetBool, по XY — 1.5
        габарита клетки каста) -> BoolCutter: Union(крапана, каст) минус катер; иначе Join.
        Общий булеан: BoolObject и объекты BoolCollection (Relative, каждый — отдельный инстанс,
        то есть отдельный операнд Manifold) вычитаются всегда, когда заданы; без BoolCutter —
        из крапанов и каста по отдельности (перекрытые оболочки одним операндом Manifold не режет).
    Катер: Cutter задан — его геометрия * (Width, Length, Width); пуст — выпуклая оболочка камня,
        увеличенного по XY в CUTTER_GROW, и его копии, поднятой на table_z + Above Table + ø
        (павильон + вертикальные стенки над рундистом). ShowCutter — при любом BoolCutter.
    Subdivision = 0: голая клетка (оболочки отдельно, атрибут crease_edge), без union и вырезов.

Интерфейс: ключ сокета — панель + имя. Недостающие сокеты добавляются, порядок в панелях —
как в SOCKETS, значения на модификаторах не меняются. Узлы пересобираются целиком.
Помощник сборки B — из tools/gn_prongs_build.py.

setup(cut, width, length) — объект "<Cut> Cast" с модификатором, камень-единица "Unit <Cut>"
и прототип "Outline <Cut>" в коллекции My_Gem_Cast Utils. Места крапанов — таблица SITES.
"""

import bpy
import importlib.util
import os
from math import hypot, pi

GROUP_NAME = "My_Gem_Cast"
UTILS = "My_Gem_Cast Utils"
REPO = os.path.expanduser("~/GitHub/BlenderJewelryAddons")
PRONGS_PATH = os.path.join(REPO, "tools", "gn_prongs_build.py")
ROUND_PATH = os.path.join(REPO, "tools", "gn_round_cast_build.py")   # клетка крапана
OUTLINE_PATH = os.path.join(REPO, "jewel_tools", "gem_outline.py")
GEMS_PATH = os.path.join(REPO, "parametric_gems", "__init__.py")

MIN_CAST = 0.05

# --- петля: из jewel_tools/gem_setting.py ---
LIMIT_RES = 64           # точек предела на пролёт петли
MITER_LIMIT = 4.0        # предел выноса в острой вершине

SLOT_SIZE = 1.5          # прорезь по X и Y — доля габарита клетки каста
CUTTER_GROW = 1.02       # катер из камня: увеличение по XY
SMOOTH_ANGLE = pi / 6
SOLVER = "MANIFOLD"

# Места крапанов по умолчанию (параметр петли u: целое — узел точки u, дробное — доля пролёта):
#   ("even", count, u0) — count точек равномерно по длине предела от точки u0;
#   ("at", (u, ...)) — точки предела в этих параметрах.
SITES = {
    "ROUND": ("even", 4, 1),                 # 45°, 135°, ... (точка 1 петли на 45°)
    "PEAR": ("even", 5, 4),                  # остриё (точка 4) и ещё 4 по длине
    "EMERALD": ("at", (0.5, 2.5, 4.5, 6.5)), # середины срезанных углов
    "BAGUETTE": ("at", (0, 1, 2, 3)),        # углы
}

# (имя, тип, default, min, max, панель, subtype)
SOCKETS = [
    ("Diam", "NodeSocketObject", None, None, None, None, None),
    ("Outline", "NodeSocketObject", None, None, None, None, None),
    ("Realize All", "NodeSocketBool", False, None, None, None, None),
    ("Subdivision", "NodeSocketInt", 2, 0, 4, None, None),
    ("ShowStone", "NodeSocketBool", True, None, None, "Stone", None),
    ("Width", "NodeSocketFloat", 3.0, 0.3, 30.0, "Stone", None),
    ("Length", "NodeSocketFloat", 5.0, 0.3, 30.0, "Stone", None),
    ("Smooth", "NodeSocketBool", True, None, None, "Prongs", None),
    ("ø", "NodeSocketFloat", 0.5, 0.1, None, "Prongs", None),
    ("Intersection", "NodeSocketFloat", 25.0, 0.0, 100.0, "Prongs", "PERCENTAGE"),
    ("Tilt", "NodeSocketFloat", 0.0524, None, None, "Prongs", "ANGLE"),
    ("Above Table", "NodeSocketFloat", 0.0, None, None, "Prongs", None),
    ("Set", "NodeSocketBool", False, None, None, "Prongs", None),
    ("Set Cover", "NodeSocketFloat", 40.0, 0.0, 100.0, "Prongs", "PERCENTAGE"),
    ("Set Height", "NodeSocketFloat", 80.0, 0.0, 200.0, "Prongs", "PERCENTAGE"),
    ("Material", "NodeSocketMaterial", None, None, None, "Prongs", None),
    ("Show", "NodeSocketBool", True, None, None, "Cast", None),
    ("Z Offset", "NodeSocketFloat", -0.15, None, None, "Cast", None),
    ("Below Culet", "NodeSocketFloat", 0.4, 0.0, None, "Cast", None),
    ("XY Offset", "NodeSocketFloat", -0.05, None, None, "Cast", None),
    ("Cast Thickness", "NodeSocketFloat", 0.4, 0.0, None, "Cast", None),
    ("CastBool", "NodeSocketBool", True, None, None, "Cast", None),
    ("HeightBool", "NodeSocketFloat", 0.4, None, None, "Cast", None),
    ("OffsetBool", "NodeSocketFloat", 0.0, None, None, "Cast", None),
    ("ShowCutter", "NodeSocketBool", False, None, None, "Bool", None),
    ("Cutter", "NodeSocketObject", None, None, None, "Bool", None),
    ("BoolCutter", "NodeSocketBool", False, None, None, "Bool", None),
    ("BoolObject", "NodeSocketObject", None, None, None, "Bool", None),
    ("BoolCollection", "NodeSocketCollection", None, None, None, "Bool", None),
]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def socket_items(ng):
    """{(панель, имя): item} входов группы."""
    return {(it.parent.name if it.parent and it.parent.name else None, it.name): it
            for it in ng.interface.items_tree if it.item_type == "SOCKET" and it.in_out == "INPUT"}


def socket_keys(ng):
    """{(панель, имя): identifier} входов группы."""
    return {k: it.identifier for k, it in socket_items(ng).items()}


def ensure_interface(ng):
    """Недостающие сокеты добавить (ключ — панель + имя), порядок в панелях — как в SOCKETS.
    Значения существующих входов на модификаторах не трогать."""
    items = {(it.name, it.item_type, getattr(it, "in_out", None)) for it in ng.interface.items_tree}
    if ("Geometry", "SOCKET", "INPUT") not in items:
        ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    if ("Geometry", "SOCKET", "OUTPUT") not in items:
        ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    panels = {it.name: it for it in ng.interface.items_tree if it.item_type == "PANEL"}
    have = socket_keys(ng)
    added = []
    for name, stype, default, mn, mx, panel, subtype in SOCKETS:
        if (panel, name) in have:
            continue
        parent = None
        if panel:
            parent = panels.get(panel) or ng.interface.new_panel(panel)
            panels[panel] = parent
        s = ng.interface.new_socket(name, in_out="INPUT", socket_type=stype, parent=parent)
        if subtype:
            s.subtype = subtype
        if default is not None:
            s.default_value = default
        if mn is not None:
            s.min_value = mn
        if mx is not None:
            s.max_value = mx
        added.append((s.identifier, default))
    have = socket_items(ng)
    pos = {}
    for name, stype, default, mn, mx, panel, subtype in SOCKETS:
        if panel is None:
            continue
        it = have[(panel, name)]
        ng.interface.move_to_parent(it, panels[panel], pos.get(panel, 0))
        pos[panel] = pos.get(panel, 0) + 1
    # новый сокет на уже существующем модификаторе в 5.2 получает 0 / False, а не default
    for obj in bpy.data.objects:
        for md in obj.modifiers:
            if md.type == "NODES" and md.node_group == ng:
                for ident, default in added:
                    if default is not None:
                        getattr(md.properties.inputs, ident).value = default


def build_group():
    pr = load_module("gn_prongs_ref", PRONGS_PATH)
    rc = load_module("gn_round_cast_ref", ROUND_PATH)
    ng = bpy.data.node_groups.get(GROUP_NAME)
    if ng is None:
        ng = bpy.data.node_groups.new(GROUP_NAME, "GeometryNodeTree")
    ensure_interface(ng)
    ng.is_modifier = True
    ng.nodes.clear()
    keys = socket_keys(ng)
    b = pr.B(ng, -400)
    up = (0.0, 0.0, 1.0)

    def gi(panel, name):
        ident = keys[(panel, name)]
        return next(s for s in b.gin.outputs if s.identifier == ident)

    def combine(vx, vy, vz, x, y):
        n = b.node("ShaderNodeCombineXYZ", x, y)
        for sock, v in zip(n.inputs, (vx, vy, vz)):
            b._set(sock, v)
        return n.outputs[0]

    def sep(v, x, y):
        n = b.node("ShaderNodeSeparateXYZ", x, y)
        b.link(v, n.inputs[0])
        return n.outputs

    def vma(a, m, c, x, y):
        """a * m + c (вектора)"""
        n = b.node("ShaderNodeVectorMath", x, y, operation="MULTIPLY_ADD")
        for sock, v in zip(n.inputs, (a, m, c)):
            b._set(sock, v)
        return n.outputs["Vector"]

    def madd(a, m, c, x, y):
        """a * m + c"""
        n = b.node("ShaderNodeMath", x, y, operation="MULTIPLY_ADD")
        for sock, v in zip(n.inputs, (a, m, c)):
            b._set(sock, v)
        return n.outputs[0]

    def icmp(op, a, v, x, y):
        n = b.node("FunctionNodeCompare", x, y, data_type="INT", operation=op)
        ab = [s for s in n.inputs if s.enabled]
        b._set(ab[0], a)
        b._set(ab[1], v)
        return n.outputs["Result"]

    def transform(geo, x, y, translation=None, rotation=None, scale=None):
        n = b.node("GeometryNodeTransform", x, y)
        b.link(geo, n.inputs["Geometry"])
        for sock, v in (("Translation", translation), ("Rotation", rotation), ("Scale", scale)):
            if v is not None:
                b._set(n.inputs[sock], v)
        return n.outputs["Geometry"]

    def axis_angle(axis, angle, x, y):
        n = b.node("FunctionNodeAxisAngleToRotation", x, y)
        n.inputs["Axis"].default_value = axis
        b.link(angle, n.inputs["Angle"])
        return n.outputs["Rotation"]

    def store(geo, name, dtype, domain, value, x, y):
        n = b.node("GeometryNodeStoreNamedAttribute", x, y, data_type=dtype, domain=domain)
        n.inputs["Name"].default_value = name
        b.link(geo, n.inputs["Geometry"])
        b._set(n.inputs["Value"], value)
        return n.outputs["Geometry"]

    def attr(name, dtype, x, y):
        return b.named(name, dtype, x, y).outputs["Attribute"]

    def join(geos, x, y):
        n = b.node("GeometryNodeJoinGeometry", x, y)
        for g in reversed(geos):
            b.link(g, n.inputs["Geometry"])
        return n.outputs["Geometry"]

    def boolean(op, a, cutters, x, y):
        n = b.node("GeometryNodeMeshBoolean", x, y, operation=op, solver=SOLVER)
        if a is not None:
            b.link(a, n.inputs["Mesh 1"])
        for c in cutters:
            b.link(c, n.inputs["Mesh 2"])
        return n.outputs["Mesh"]

    def subd(geo, x, y):
        n = b.node("GeometryNodeSubdivisionSurface", x, y)
        b.link(geo, n.inputs["Mesh"])
        b.link(gi(None, "Subdivision"), n.inputs["Level"])
        b.link(attr("crease_edge", "FLOAT", x - 200, y - 200), n.inputs["Edge Crease"])
        n.inputs["Limit Surface"].default_value = True
        return n.outputs["Mesh"]

    def gate(cond, geo, x, y):
        """выключено — пустая геометрия"""
        n = b.node("GeometryNodeSwitch", x, y, input_type="GEOMETRY")
        b.link(cond, n.inputs["Switch"])
        b.link(geo, n.inputs["True"])
        return n.outputs["Output"]

    def object_info(sock, space, x, y, instance=True):
        n = b.node("GeometryNodeObjectInfo", x, y, transform_space=space)
        n.inputs["As Instance"].default_value = instance
        b.link(sock, n.inputs["Object"])
        return n.outputs["Geometry"]

    def instances(geo, x, y):
        n = b.node("GeometryNodeAttributeDomainSize", x, y, component="INSTANCES")
        b.link(geo, n.inputs["Geometry"])
        return icmp("GREATER_THAN", n.outputs["Instance Count"], 0, x + 200, y)

    w, ln = gi("Stone", "Width"), gi("Stone", "Length")
    s_stone = combine(w, ln, w, -100, -2400)

    # --- камень: высоты площадки и калетты по Bounding Box геометрии Diam ---
    b.section("Stone Heights")
    stone_geo = object_info(gi(None, "Diam"), "ORIGINAL", -100, 1400, instance=False)
    bb = b.node("GeometryNodeBoundBox", 100, 1400)
    b.link(stone_geo, bb.inputs["Geometry"])
    table_z = b.math("MULTIPLY", sep(bb.outputs["Max"], 300, 1500)["Z"], w, 500, 1500)
    culet_z = b.math("MULTIPLY", sep(bb.outputs["Min"], 300, 1300)["Z"], w, 500, 1300)
    bottom_z = b.math("SUBTRACT", culet_z, gi("Cast", "Below Culet"), 700, 1300)
    dome_z = b.math("ADD", table_z, gi("Prongs", "Above Table"), 700, 1500)
    tilt = gi("Prongs", "Tilt")
    cos_t = b.math("COSINE", tilt, None, 700, 1100)
    tan_t = b.math("TANGENT", tilt, None, 700, 950)
    # край площадки — вершины Diam на высоте max.z; crown — путь по короне по короткой стороне (X)
    sxyz = sep(b.node("GeometryNodeInputPosition", 100, 1900).outputs[0], 300, 1900)
    on_table = b.cmp("GREATER_THAN", sxyz["Z"], b.math("MULTIPLY", sep(bb.outputs["Max"], 300, 1700)["Z"], 0.999, 500, 1750),
                     700, 1900)
    st = b.node("GeometryNodeAttributeStatistic", 900, 1900, data_type="FLOAT", domain="POINT")
    b.link(stone_geo, st.inputs["Geometry"])
    b.link(on_table, st.inputs["Selection"])
    b.link(b.math("ABSOLUTE", sxyz["X"], None, 500, 2050), b.enabled(st, "Attribute"))
    crown = b.math("MULTIPLY", w, b.math("SUBTRACT", 0.5, b.enabled_out(st, "Max"), 1100, 1900), 1300, 1900)

    # --- контур-прототип: единичные координаты камня -> (Width, Length, 1) ---
    b.section("Outline")
    base = transform(object_info(gi(None, "Outline"), "ORIGINAL", -100, 3000, instance=False), 100, 3000,
                     scale=combine(w, ln, 1.0, -100, 2800))

    # --- петля: рёбра прототипа, против часовой (из gem_setting.py) ---
    b.section("Loop")
    x0, y0 = 400, 3000
    loop = b.node("GeometryNodeMeshToCurve", x0, y0)
    b.link(base, loop.inputs["Mesh"])
    pos = b.node("GeometryNodeInputPosition", x0, y0 - 300).outputs[0]
    nxt = b.node("GeometryNodeOffsetPointInCurve", x0, y0 - 450)
    nxt.inputs["Offset"].default_value = 1
    prv = b.node("GeometryNodeOffsetPointInCurve", x0, y0 - 650)
    prv.inputs["Offset"].default_value = -1
    p_next = b.at_index(pos, nxt.outputs["Point Index"], "FLOAT_VECTOR", x0 + 200, y0 - 450)
    p_prev = b.at_index(pos, prv.outputs["Point Index"], "FLOAT_VECTOR", x0 + 200, y0 - 650)
    # удвоенная площадь каждой петли: сумма P x P+ по точкам её кривой
    cross = sep(b.vmath("CROSS_PRODUCT", pos, p_next, x0 + 400, y0 - 200), x0 + 600, y0 - 200)["Z"]
    of_curve = b.node("GeometryNodeCurveOfPoint", x0 + 400, y0 - 400)
    area = b.node("GeometryNodeAccumulateField", x0 + 800, y0 - 200, data_type="FLOAT", domain="POINT")
    b.link(cross, area.inputs["Value"])
    b.link(of_curve.outputs["Curve Index"], area.inputs["Group ID"])
    ccw = b.node("GeometryNodeReverseCurve", x0 + 1000, y0)
    b.link(loop.outputs["Curve"], ccw.inputs["Curve"])
    b.link(b.cmp("LESS_THAN", area.outputs["Total"], 0.0, x0 + 1000, y0 - 200), ccw.inputs["Selection"])
    loop = ccw.outputs["Curve"]
    sharp = b.cmp("GREATER_THAN", attr("corner", "FLOAT", x0 + 400, y0 - 800), 0.5, x0 + 600, y0 - 800)

    # --- предел петли сплайном Безье: точки с касательной (из gem_setting.py) ---
    b.section("Limit Curve")
    x0, y0 = 1700, 3000
    hl = b.vmath("SCALE", vma(pos, (2.0, 2.0, 2.0), p_prev, x0, y0 - 400), 1.0 / 3.0, x0 + 180, y0 - 400)
    hr = b.vmath("SCALE", vma(pos, (2.0, 2.0, 2.0), p_next, x0, y0 - 560), 1.0 / 3.0, x0 + 180, y0 - 560)
    handles = b.capture(loop, {"Left": ("VECTOR", hl), "Right": ("VECTOR", hr)}, x0 + 380, y0)
    bez = b.node("GeometryNodeCurveSplineType", x0 + 580, y0, spline_type="BEZIER")
    b.link(handles.outputs["Geometry"], bez.inputs["Curve"])
    free = b.node("GeometryNodeCurveSetHandles", x0 + 780, y0, handle_type="FREE", mode={"LEFT", "RIGHT"})
    b.link(bez.outputs["Curve"], free.inputs["Curve"])
    smooth_k = b.vmath("SCALE", vma(pos, (4.0, 4.0, 4.0), b.vmath("ADD", p_prev, p_next, x0, y0 - 720),
                                    x0 + 180, y0 - 720), 1.0 / 6.0, x0 + 360, y0 - 720)
    knot = b.node("GeometryNodeSetPosition", x0 + 980, y0)
    b.link(free.outputs["Curve"], knot.inputs["Geometry"])
    b.link(b.switch("VECTOR", sharp, smooth_k, pos, x0 + 780, y0 - 720), knot.inputs["Position"])
    left = b.node("GeometryNodeSetCurveHandlePositions", x0 + 1180, y0, mode="LEFT")
    b.link(knot.outputs["Geometry"], left.inputs["Curve"])
    b.link(handles.outputs["Left"], left.inputs["Position"])
    right = b.node("GeometryNodeSetCurveHandlePositions", x0 + 1380, y0, mode="RIGHT")
    b.link(left.outputs["Curve"], right.inputs["Curve"])
    b.link(handles.outputs["Right"], right.inputs["Position"])
    res = b.node("GeometryNodeSetSplineResolution", x0 + 1580, y0)
    b.link(right.outputs["Curve"], res.inputs["Curve"])
    res.inputs["Resolution"].default_value = LIMIT_RES
    limit = b.node("GeometryNodeCurveToPoints", x0 + 1780, y0, mode="EVALUATED")
    b.link(res.outputs["Curve"], limit.inputs["Curve"])

    # --- клетка крапана: из My_Round_Cast; Set — кончик загнут к камню ---
    d = gi("Prongs", "ø")
    set_on = gi("Prongs", "Set")
    sp_geo = rc.build_prong_cage(b, d, bottom_z, dome_z, tilt, cos_t, gi("Prongs", "Intersection"), table_z, crown,
                                 (set_on, gi("Prongs", "Set Cover"), gi("Prongs", "Set Height")), 0, 4600)
    # низ на bottom_z, наклон Tilt вокруг Y (ось через начало координат на z = 0)
    pc = transform(sp_geo, 1500, 400,
                   translation=combine(0.0, 0.0, b.math("DIVIDE", bottom_z, cos_t, 1500, 250), 1500, 100))
    prong_cage = transform(pc, 1700, 400, rotation=axis_angle((0.0, 1.0, 0.0), tilt, 1700, 100))

    # --- места крапанов: ось на z = 0 в месте + n * ø * (0.5 - Intersection/100) ---
    b.section("Prong Sites")
    x0, y0 = 2000, 800
    lone = icmp("EQUAL", b.node("GeometryNodeInputMeshVertexNeighbors", x0, y0 - 200).outputs["Vertex Count"], 0,
                x0 + 200, y0 - 200)
    sites = b.node("GeometryNodeMeshToPoints", x0 + 400, y0, mode="VERTICES")
    b.link(base, sites.inputs["Mesh"])
    b.link(lone, sites.inputs["Selection"])
    # нормаль контура: касательная ближайшей точки предела, повёрнутая наружу
    near = b.node("GeometryNodeSampleNearest", x0 + 400, y0 - 400, domain="POINT")
    b.link(limit.outputs["Points"], near.inputs["Geometry"])
    b.link(pos, near.inputs["Sample Position"])
    tangent = b.node("GeometryNodeSampleIndex", x0 + 600, y0 - 400, data_type="FLOAT_VECTOR", domain="POINT")
    b.link(limit.outputs["Points"], tangent.inputs["Geometry"])
    b.link(limit.outputs["Tangent"], tangent.inputs["Value"])
    b.link(near.outputs["Index"], tangent.inputs["Index"])
    normal = b.vmath("NORMALIZE", b.vmath("CROSS_PRODUCT", tangent.outputs["Value"], up, x0 + 800, y0 - 400),
                     None, x0 + 1000, y0 - 400)
    keep = b.math("SUBTRACT", 0.5, b.math("DIVIDE", gi("Prongs", "Intersection"), 100.0, x0 + 800, y0 - 600),
                  x0 + 1000, y0 - 600)
    reach = b.math("MULTIPLY", d, keep, x0 + 1200, y0 - 600)
    axis_p = vma(normal, combine(reach, reach, 0.0, x0 + 1200, y0 - 760), pos, x0 + 1400, y0 - 400)
    at_axis = b.node("GeometryNodeSetPosition", x0 + 1600, y0)
    b.link(sites.outputs["Points"], at_axis.inputs["Geometry"])
    b.link(axis_p, at_axis.inputs["Position"])
    # ось X крапана — по n (поворот только вокруг Z)
    face_out = b.node("FunctionNodeAlignRotationToVector", x0 + 1400, y0 - 900, axis="X", pivot_axis="Z")
    b.link(normal, face_out.inputs["Vector"])
    iop = b.node("GeometryNodeInstanceOnPoints", x0 + 1800, y0)
    b.link(at_axis.outputs["Geometry"], iop.inputs["Points"])
    b.link(prong_cage, iop.inputs["Instance"])
    b.link(face_out.outputs["Rotation"], iop.inputs["Rotation"])
    real = b.node("GeometryNodeRealizeInstances", x0 + 2000, y0)
    b.link(iop.outputs["Instances"], real.inputs["Geometry"])
    prongs = real.outputs["Geometry"]

    # --- вынос петли по биссектрисе с компенсацией сглаживания (из gem_setting.py) ---
    b.section("Loop Offset")
    x0, y0 = 1700, -1600
    d_in = b.vmath("NORMALIZE", b.vmath("SUBTRACT", pos, p_prev, x0, y0 - 200), None, x0 + 180, y0 - 200)
    d_out = b.vmath("NORMALIZE", b.vmath("SUBTRACT", p_next, pos, x0, y0 - 360), None, x0 + 180, y0 - 360)
    turn = b.vmath("ADD", d_in, d_out, x0 + 360, y0 - 280)
    bis = b.vmath("NORMALIZE", b.vmath("CROSS_PRODUCT", turn, up, x0 + 540, y0 - 240), None, x0 + 720, y0 - 240)
    # острая вершина: s = 1 / cos(половины поворота) = 2 / |d_in + d_out|, не больше MITER_LIMIT
    miter = b.math("MINIMUM", b.math("DIVIDE", 2.0, b.vmath("LENGTH", turn, None, x0 + 540, y0 - 400),
                                     x0 + 720, y0 - 400), MITER_LIMIT, x0 + 900, y0 - 400)
    # гладкая: (s- b- + 4 s b + s+ b+) / 6 . N = 1, N — поперёк P+ - P-
    chord = b.vmath("NORMALIZE", b.vmath("CROSS_PRODUCT", b.vmath("SUBTRACT", p_next, p_prev, x0, y0 - 600),
                                         up, x0 + 180, y0 - 600), None, x0 + 360, y0 - 600)
    bn_prev = b.vmath("DOT_PRODUCT", b.at_index(bis, prv.outputs["Point Index"], "FLOAT_VECTOR", x0 + 360, y0 - 760),
                      chord, x0 + 540, y0 - 760)
    bn_next = b.vmath("DOT_PRODUCT", b.at_index(bis, nxt.outputs["Point Index"], "FLOAT_VECTOR", x0 + 360, y0 - 920),
                      chord, x0 + 540, y0 - 920)
    s0 = b.switch("FLOAT", sharp, b.math("DIVIDE", 6.0, b.math("ADD", b.math("ADD", bn_prev, bn_next, x0 + 720,
                                                                               y0 - 760), 4.0, x0 + 900, y0 - 760),
                                         x0 + 1080, y0 - 760), miter, x0 + 1260, y0 - 760)
    # шаг Якоби с настоящими s соседей
    pull = madd(b.at_index(s0, nxt.outputs["Point Index"], "FLOAT", x0 + 1260, y0 - 1080), bn_next,
                b.math("MULTIPLY", b.at_index(s0, prv.outputs["Point Index"], "FLOAT", x0 + 1260, y0 - 920),
                       bn_prev, x0 + 1440, y0 - 920), x0 + 1620, y0 - 1000)
    s1 = b.math("DIVIDE", b.math("SUBTRACT", 6.0, pull, x0 + 1800, y0 - 1000),
                b.math("MULTIPLY", b.vmath("DOT_PRODUCT", bis, chord, x0 + 1620, y0 - 1160), 4.0, x0 + 1800, y0 - 1160),
                x0 + 1980, y0 - 1000)
    offset = b.vmath("SCALE", bis, b.switch("FLOAT", sharp, s1, miter, x0 + 2160, y0 - 1000), x0 + 2340, y0 - 280)
    path = store(loop, "_gc_p", "FLOAT_VECTOR", "POINT", pos, x0 + 2340, y0)
    path = store(path, "_gc_o", "FLOAT_VECTOR", "POINT", offset, x0 + 2540, y0)
    path = store(path, "_gc_s", "FLOAT", "POINT", sharp, x0 + 2740, y0)

    # --- клетка каста: петля x 4 угла профиля (d — вынос по нормали, z) ---
    b.section("Cast Cage")
    x0, y0 = 4700, -1600
    z_top = gi("Cast", "Z Offset")
    th = gi("Cast", "Cast Thickness")
    h_cast = b.math("MAXIMUM", b.math("SUBTRACT", z_top, bottom_z, x0, y0 - 500), MIN_CAST, x0 + 200, y0 - 500)
    z_bot = b.math("SUBTRACT", z_top, h_cast, x0 + 400, y0 - 500)
    d_ot = gi("Cast", "XY Offset")
    d_ob = b.math("SUBTRACT", d_ot, b.math("MULTIPLY", h_cast, tan_t, x0 + 200, y0 - 660), x0 + 400, y0 - 660)
    d_it = b.math("SUBTRACT", d_ot, th, x0 + 400, y0 - 820)
    d_ib = b.math("SUBTRACT", d_ob, th, x0 + 400, y0 - 980)
    quad = b.node("GeometryNodeCurvePrimitiveQuadrilateral", x0 + 800, y0 - 200, mode="POINTS")
    for i, (dd, zz) in enumerate(((d_ot, z_top), (d_ob, z_bot), (d_ib, z_bot), (d_it, z_top))):
        b.link(combine(dd, zz, 0.0, x0 + 600, y0 - 500 - 160 * i), quad.inputs["Point %d" % (i + 1)])
    profile = store(quad.outputs["Curve"], "_gc_dz", "FLOAT_VECTOR", "POINT", pos, x0 + 1000, y0 - 200)
    profile = store(profile, "_gc_k", "FLOAT", "POINT", b.node("GeometryNodeInputIndex", x0 + 1000, y0 - 400).outputs[0],
                    x0 + 1200, y0 - 200)
    c2m = b.node("GeometryNodeCurveToMesh", x0 + 1400, y0)
    b.link(path, c2m.inputs["Curve"])
    b.link(profile, c2m.inputs["Profile Curve"])
    dz = sep(attr("_gc_dz", "FLOAT_VECTOR", x0 + 1400, y0 - 300), x0 + 1600, y0 - 300)
    place = b.node("GeometryNodeSetPosition", x0 + 1800, y0)
    b.link(c2m.outputs["Mesh"], place.inputs["Geometry"])
    b.link(vma(attr("_gc_o", "FLOAT_VECTOR", x0 + 1600, y0 - 460), combine(dz["X"], dz["X"], dz["X"], x0 + 1800, y0 - 460),
               b.vmath("ADD", attr("_gc_p", "FLOAT_VECTOR", x0 + 1600, y0 - 620),
                       combine(0.0, 0.0, dz["Y"], x0 + 1800, y0 - 620), x0 + 2000, y0 - 620), x0 + 2000, y0 - 400),
           place.inputs["Position"])
    # ребро кольца: углы профиля соседние — дробный средний _gc_k; продольное — целый
    ring_edge = b.cmp("GREATER_THAN", b.math("FRACT", attr("_gc_k", "FLOAT", x0 + 2000, y0 - 800), None,
                                             x0 + 2200, y0 - 800), 0.25, x0 + 2400, y0 - 800)
    crease = b.switch("FLOAT", ring_edge, 1.0, attr("_gc_s", "FLOAT", x0 + 2400, y0 - 960), x0 + 2600, y0 - 800)
    cast = store(place.outputs["Geometry"], "crease_edge", "FLOAT", "EDGE", crease, x0 + 2600, y0)
    rm = b.node("GeometryNodeRemoveAttribute", x0 + 2800, y0)
    rm.inputs["Pattern Mode"].default_value = "Wildcard"
    rm.inputs["Name"].default_value = "_gc_*"
    b.link(cast, rm.inputs["Geometry"])
    cast_cage = gate(gi("Cast", "Show"), rm.outputs["Geometry"], x0 + 3000, y0)

    # --- Subdivision Surface: крапана и стенка — отдельные оболочки ---
    b.section("Subdivision")
    prongs_sd = subd(prongs, 8000, 400)
    cast_sd = subd(cast_cage, 8000, -1600)

    # --- прорезь: параллелепипед на середине высоты каста ---
    b.section("Cast Slot")
    x0, y0 = 8300, -1600
    cbb = b.node("GeometryNodeBoundBox", x0, y0 - 300)
    b.link(cast_cage, cbb.inputs["Geometry"])
    size = b.vmath("SCALE", b.vmath("SUBTRACT", cbb.outputs["Max"], cbb.outputs["Min"], x0 + 200, y0 - 300),
                   SLOT_SIZE, x0 + 400, y0 - 300)
    mid = sep(b.vmath("SCALE", b.vmath("ADD", cbb.outputs["Max"], cbb.outputs["Min"], x0 + 200, y0 - 500), 0.5,
                      x0 + 400, y0 - 500), x0 + 600, y0 - 500)
    cube = b.node("GeometryNodeMeshCube", x0 + 800, y0 - 300)
    b.link(combine(sep(size, x0 + 600, y0 - 300)["X"], sep(size, x0 + 600, y0 - 150)["Y"], gi("Cast", "HeightBool"),
                   x0 + 800, y0 - 500), cube.inputs["Size"])
    # центр — середина высоты каста + OffsetBool
    slot_z = b.math("ADD", madd(h_cast, -0.5, z_top, x0 + 600, y0 - 700), gi("Cast", "OffsetBool"), x0 + 800, y0 - 700)
    slot = transform(cube.outputs["Mesh"], x0 + 1000, y0 - 300,
                     translation=combine(mid["X"], mid["Y"], slot_z, x0 + 1000, y0 - 600))
    slotted = boolean("DIFFERENCE", cast_sd, [slot], x0 + 1200, y0)
    cast_cut = b.switch("GEOMETRY", gi("Cast", "CastBool"), cast_sd, slotted, x0 + 1400, y0)

    # --- катер: Cutter * (W, L, W) или оболочка камня с поднятой копией ---
    b.section("Cutter")
    x0, y0 = 8300, -3200
    given = transform(object_info(gi("Bool", "Cutter"), "ORIGINAL", x0, y0), x0 + 200, y0, scale=s_stone)
    grown = transform(stone_geo, x0, y0 - 300, scale=combine(b.math("MULTIPLY", w, CUTTER_GROW, x0 - 200, y0 - 500),
                                                             b.math("MULTIPLY", ln, CUTTER_GROW, x0 - 200, y0 - 660),
                                                             w, x0, y0 - 500))
    lift = b.math("ADD", dome_z, d, x0 + 200, y0 - 600)
    lifted = transform(grown, x0 + 200, y0 - 400, translation=combine(0.0, 0.0, lift, x0 + 400, y0 - 600))
    hull = b.node("GeometryNodeConvexHull", x0 + 600, y0 - 300)
    b.link(join([grown, lifted], x0 + 400, y0 - 300), hull.inputs["Geometry"])
    has_given = instances(given, x0 + 400, y0 + 200)
    cutter = b.switch("GEOMETRY", has_given, hull.outputs["Convex Hull"], given, x0 + 800, y0)
    # Set: посадку режут оболочка камня (кончик лежит на короне) и заданный Cutter ниже рундиста —
    # отдельными операндами; оболочка меньше катера, совпадающих стенок нет
    y1 = y0 - 1000
    set_hull = b.node("GeometryNodeConvexHull", x0 + 400, y1)
    b.link(transform(stone_geo, x0 + 200, y1, scale=combine(b.math("MULTIPLY", w, rc.SET_GROW, x0, y1 - 200),
                                                            b.math("MULTIPLY", ln, rc.SET_GROW, x0, y1 - 360),
                                                            w, x0 + 200, y1 - 250)), set_hull.inputs["Geometry"])
    box = b.node("GeometryNodeMeshCube", x0 + 400, y1 - 500)
    side = b.math("MULTIPLY", b.math("MAXIMUM", w, ln, x0, y1 - 550), 4.0, x0 + 200, y1 - 550)
    b.link(combine(side, side, side, x0 + 200, y1 - 720), box.inputs["Size"])
    drop = madd(side, -0.5, b.math("MULTIPLY", w, -rc.SET_CLIP, x0 + 200, y1 - 900), x0 + 400, y1 - 800)
    below = transform(box.outputs["Mesh"], x0 + 600, y1 - 500, translation=combine(0.0, 0.0, drop, x0 + 600, y1 - 800))
    # Cutter пуст — пересечение не делать: Intersect с пустым операндом возвращает сам ящик
    low = gate(has_given, boolean("INTERSECT", None, [given, below], x0 + 800, y1 - 500), x0 + 1000, y1 - 500)
    seat = [b.switch("GEOMETRY", set_on, cutter, low, x0 + 1200, y1 - 300),
            gate(set_on, set_hull.outputs["Convex Hull"], x0 + 1000, y1)]

    # --- булеаны: union, посадка, общий булеан ---
    b.section("Booleans")
    x0, y0 = 10000, 0
    bool_obj = object_info(gi("Bool", "BoolObject"), "RELATIVE", x0, y0 - 900)
    coll = b.node("GeometryNodeCollectionInfo", x0, y0 - 1100, transform_space="RELATIVE")
    b.link(gi("Bool", "BoolCollection"), coll.inputs["Collection"])
    # каждый объект — отдельный инстанс = отдельный операнд (пересекающиеся резаки)
    coll.inputs["Separate Children"].default_value = True
    coll.inputs["Reset Children"].default_value = False
    bools = join([bool_obj, coll.outputs["Instances"]], x0 + 200, y0 - 1000)
    has_bool = instances(bools, x0 + 200, y0 - 1200)
    united = boolean("UNION", None, [prongs_sd, cast_cut], x0, y0)
    seated = boolean("DIFFERENCE", united, seat, x0 + 200, y0)
    seated = b.switch("GEOMETRY", has_bool, seated, boolean("DIFFERENCE", seated, [bools], x0 + 400, y0 - 200),
                      x0 + 600, y0)
    # без BoolCutter: оболочки отдельно, общий булеан — по каждой; Set — камень вырезан из крапанов
    prongs_x = b.switch("GEOMETRY", set_on, prongs_sd, boolean("DIFFERENCE", prongs_sd, [seat[1]], x0, y0 - 300),
                        x0 + 200, y0 - 400)
    apart = join([boolean("DIFFERENCE", prongs_x, [bools], x0 + 400, y0 - 500),
                  boolean("DIFFERENCE", cast_cut, [bools], x0 + 400, y0 - 700)], x0 + 600, y0 - 500)
    plain = b.switch("GEOMETRY", has_bool, join([prongs_x, cast_cut], x0 + 600, y0 - 300), apart, x0 + 800, y0 - 400)
    metal = b.switch("GEOMETRY", gi("Bool", "BoolCutter"), plain, seated, x0 + 1000, y0)
    # катер виден при любом BoolCutter
    metal = join([metal, gate(gi("Bool", "ShowCutter"), join(seat, x0 + 800, y0 - 200), x0 + 1000, y0 - 200)],
                 x0 + 1200, y0)

    # --- выход: клетка при Subdivision 0, материал, сглаживание, камень ---
    b.section("Output")
    x0, y0 = 11500, 0
    cage_all = join([prongs, cast_cage], x0, y0 - 400)
    has_sd = icmp("GREATER_THAN", gi(None, "Subdivision"), 0, x0, y0 + 300)
    metal = b.switch("GEOMETRY", has_sd, cage_all, metal, x0 + 200, y0)
    mat = b.node("GeometryNodeSetMaterial", x0 + 400, y0)
    b.link(metal, mat.inputs["Geometry"])
    b.link(gi("Prongs", "Material"), mat.inputs["Material"])
    sm_f = b.node("GeometryNodeSetShadeSmooth", x0 + 600, y0 - 300, domain="FACE")
    b.link(mat.outputs["Geometry"], sm_f.inputs["Mesh"])
    sm_e = b.node("GeometryNodeSetShadeSmooth", x0 + 800, y0 - 300, domain="EDGE")
    b.link(sm_f.outputs["Mesh"], sm_e.inputs["Mesh"])
    b.link(b.cmp("LESS_EQUAL", b.node("GeometryNodeInputMeshEdgeAngle", x0 + 600, y0 - 500).outputs["Unsigned Angle"],
                 SMOOTH_ANGLE, x0 + 800, y0 - 500), sm_e.inputs["Shade Smooth"])
    smooth = b.switch("GEOMETRY", gi("Prongs", "Smooth"), mat.outputs["Geometry"], sm_e.outputs["Mesh"], x0 + 1000, y0)
    realize = b.node("GeometryNodeRealizeInstances", x0 + 1200, y0)
    b.link(smooth, realize.inputs["Geometry"])
    b.link(gi(None, "Realize All"), realize.inputs["Realize All"])
    realize.inputs["Depth"].default_value = 2
    # камень — инстанс объекта Diam: на него не вешать Set Material / Remove Attribute / Merge
    stone = transform(object_info(gi(None, "Diam"), "ORIGINAL", x0 + 1000, y0 - 700), x0 + 1200, y0 - 700,
                      scale=s_stone)
    stone = gate(gi("Stone", "ShowStone"), stone, x0 + 1400, y0 - 700)
    out = join([realize.outputs["Geometry"], stone], x0 + 1600, y0)
    b.frame = None
    gout = b.node("NodeGroupOutput", x0 + 1800, y0)
    b.link(out, gout.inputs["Geometry"])

    print("Node group '%s' rebuilt: %d nodes" % (GROUP_NAME, len(ng.nodes)))
    return ng


def site_points(loop, rule, steps=LIMIT_RES):
    """Места крапанов на пределе петли [(x, y, corner)] по правилу из SITES."""
    go = load_module("gem_outline_ref", OUTLINE_PATH)
    dense = go.limit_curve(loop, steps)
    n = len(dense)
    if rule[0] == "at":
        return [dense[int(round(u * steps)) % n][:2] for u in rule[1]]
    _, count, u0 = rule
    start = int(round(u0 * steps)) % n
    pts = [dense[(start + i) % n][:2] for i in range(n)] + [dense[start][:2]]
    lengths = [0.0]
    for a, c in zip(pts, pts[1:]):
        lengths.append(lengths[-1] + hypot(c[0] - a[0], c[1] - a[1]))
    out = []
    for k in range(count):
        s = lengths[-1] * k / count
        j = max(i for i in range(n) if lengths[i] <= s)
        f = (s - lengths[j]) / ((lengths[j + 1] - lengths[j]) or 1.0)
        a, c = pts[j], pts[j + 1]
        out.append((a[0] + (c[0] - a[0]) * f, a[1] + (c[1] - a[1]) * f))
    return out


def utils_collection():
    coll = bpy.data.collections.get(UTILS)
    if coll is None:
        coll = bpy.data.collections.new(UTILS)
    if coll.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(coll)
    return coll


def unit_stone(cut):
    """Камень-единица: габарит XY 1 x 1, рундист снизу на z = 0, высоты на единицу ширины."""
    name = "Unit %s" % cut.title()
    obj = bpy.data.objects.get(name)
    if obj is not None:
        return obj
    gems = load_module("gem_cast_gems", GEMS_PATH)
    spec = gems._CUT_SPECS[cut]
    verts, faces = gems._cut_geometry(cut, 1.0, 1.0, spec.girdle_percent, spec.crown_percent, spec.pavilion_percent)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj["gem"] = {"cut": cut, "stone": "DIAMOND"}
    utils_collection().objects.link(obj)
    return obj


def outline_proto(cut, stone):
    """Прототип контура: управляющая петля рундиста (рёбра, corner) + места крапанов (вершины без рёбер).
    Уже есть — не трогать (пользователь мог править руками)."""
    name = "Outline %s" % cut.title()
    obj = bpy.data.objects.get(name)
    if obj is not None:
        return obj
    go = load_module("gem_outline_ref", OUTLINE_PATH)
    loop = go.gem_loop(stone)
    sites = site_points(loop, SITES[cut])
    n = len(loop)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(x, y, 0.0) for x, y, _ in loop] + [(x, y, 0.0) for x, y in sites],
                     [(i, (i + 1) % n) for i in range(n)], [])
    corner = mesh.attributes.new("corner", "FLOAT", "POINT")
    corner.data.foreach_set("value", [1.0 if c else 0.0 for *_, c in loop] + [0.0] * len(sites))
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    utils_collection().objects.link(obj)
    return obj


def setup(cut, width=None, length=None):
    """Объект '<Cut> Cast' с модификатором: Diam, Outline, Width, Length. Остальные входы не трогает."""
    cut = cut.upper()
    ng = build_group()
    stone = unit_stone(cut)
    proto = outline_proto(cut, stone)
    name = "%s Cast" % cut.title()
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, bpy.data.meshes.new(name))
        bpy.context.scene.collection.objects.link(ob)
    md = next((m for m in ob.modifiers if m.type == "NODES" and m.node_group == ng), None)
    if md is None:
        md = ob.modifiers.new(GROUP_NAME, "NODES")
        md.node_group = ng
    if width is None:
        width = 3.0
    if length is None:
        gems = load_module("gem_cast_gems", GEMS_PATH)
        spec = gems._CUT_SPECS[cut]
        length = width * spec.base_length / spec.base_width
    keys = socket_keys(ng)
    for key, v in (((None, "Diam"), stone), ((None, "Outline"), proto), (("Stone", "Width"), width),
                   (("Stone", "Length"), length)):
        getattr(md.properties.inputs, keys[key]).value = v
    ob.update_tag()
    print("Gem cast '%s': %.2f x %.2f mm" % (ob.name, width, length))
    return ob


def main():
    build_group()


if __name__ == "__main__":
    main()
