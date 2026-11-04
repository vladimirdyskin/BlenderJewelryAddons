"""
My_Gems_Curve — только камни по кривой, с зеркалом без дублей на оси.

Модификатор вешается на кривую. Выход — инстансы камня Diam (для JewelCraft), больше ничего.
Крапана ставит следующая в стеке группа My_Prongs (tools/gn_prongs_build.py).

Схема:
    Trim Curve / Offset Curve
    Мелкий Resample -> Delete: при включённом зеркале остаётся одна сторона кривой
        (та, где среднее положение точек). Концы, зашедшие за ось, отрезаются.
    Resample (Count): n - 1 = floor(L / шаг), шаг = длина камня + Spacing. Крайние камни
        встают на концы, поэтому на оси всегда камень, а зазор между ними подгоняется.
        Spacing — минимальный зазор вдоль кривой.
    Curve to Points: X камня = касательная, Z = нормаль с учётом Tilt.
    Зеркало (подгруппа Gems Curve Mirror) по очереди X, Y, Z — на точках, а не на инстансах.
    Один Instance on Points.

Камень, пересекающий ось (|d| < половины длины камня), копии не получает и ставится ровно
на ось: Z — среднее с отражением, X — поперёк оси. Копия остальных камней — точное отражение:
повороты считаются так, чтобы матрица была R * diag(-1, 1, 1), знак лежит в gem_mirror и идёт
в Scale X. Иначе несимметричный камень в копии развернулся бы не туда.

Длина камня вдоль кривой — Gem Size * bbox X исходника (багеты), как в My_Gems_On_Curve.

Атрибуты на инстансах (их читает My_Prongs):
    gem_order — порядок вдоль ряда. Отражается относительно того конца ряда, что ближе к оси,
                поэтому обход идёт непрерывно через ось и не разворачивается.
    gem_up    — ось Z камня (Instance Rotation не годится: у копий отрицательный масштаб).
    gem_r     — половина длины камня вдоль кривой.
    gem_mirror — -1 у зеркальной копии: её ход по кривой обратный, начало ряда стало концом.

Ограничение: замкнутая кривая с включённым зеркалом режется в порядке точек, шов должен быть
на отрезаемой стороне. Для зеркала нужна половина контура.

Интерфейс: сокеты только добавляются, если их нет — повторный запуск скрипта
не сбрасывает значения на модификаторах. Узлы пересобираются целиком.
"""

import bpy

GROUP_NAME = "My_Gems_Curve"
MIRROR_GROUP = "Gems Curve Mirror"

ATTR_ORDER = "gem_order"
ATTR_UP = "gem_up"
ATTR_R = "gem_r"
ATTR_S = "gem_mirror"  # знак Scale X: -1 у зеркальной копии
ATTR_X = "_gc_x"       # ось X камня
ATTR_Z = "_gc_z"       # ось Z камня

CUT_STEP = 0.002     # шаг мелкого Resample, доля шага камней: ошибка реза меньше 0.2% шага

# (имя, тип, default, min, max, панель, subtype)
SOCKETS = [
    ("Diam", "NodeSocketObject", None, None, None, None, None),
    ("Gem Size", "NodeSocketFloat", 1.0, 0.01, None, "Stone", None),
    ("Spacing", "NodeSocketFloat", 0.1, None, None, "Stone", None),
    ("Trim Curve", "NodeSocketFloat", 0.0, None, None, "Stone", None),
    ("Offset Curve", "NodeSocketFloat", 0.0, None, None, "Stone", None),
    ("Tilt", "NodeSocketFloat", 0.0, None, None, "Stone", "ANGLE"),
    ("XMirror", "NodeSocketBool", False, None, None, "Mirror", None),
    ("YMirror", "NodeSocketBool", False, None, None, "Mirror", None),
    ("ZMirror", "NodeSocketBool", False, None, None, "Mirror", None),
]


def ensure_interface(ng):
    items = {(it.name, it.item_type) for it in ng.interface.items_tree}
    if ("Geometry", "SOCKET") not in items:
        ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    panels = {it.name: it for it in ng.interface.items_tree if it.item_type == "PANEL"}
    names = {it.name for it in ng.interface.items_tree if it.item_type == "SOCKET"}
    added = []
    for name, stype, default, mn, mx, panel, subtype in SOCKETS:
        if name in names:
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
    # новый сокет на уже существующем модификаторе в 5.2 получает 0 / False, а не default
    for obj in bpy.data.objects:
        for md in obj.modifiers:
            if md.type == "NODES" and md.node_group == ng:
                for ident, default in added:
                    if default is not None:
                        getattr(md.properties.inputs, ident).value = default


class B:
    """Короткие помощники сборки графа."""

    def __init__(self, ng, x=-300):
        self.ng, self.N, self.L = ng, ng.nodes, ng.links
        self.frame = None
        self.gin = self.N.new("NodeGroupInput")
        self.gin.location = (x, 0)

    def section(self, label):
        """Следующие узлы — в рамке с этой подписью."""
        self.frame = self.N.new("NodeFrame")
        self.frame.label = label
        self.frame.label_size = 16
        return self.frame

    def node(self, idname, x, y, **props):
        n = self.N.new(idname)
        if self.frame is not None:
            n.parent = self.frame
        n.location = (x, y)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def link(self, a, b):
        self.L.new(a, b)

    def g(self, name):
        return self.gin.outputs[name]

    def _set(self, sock, v):
        if isinstance(v, (bool, int, float, tuple)):
            sock.default_value = v
        else:
            self.link(v, sock)

    def enabled(self, node, name):
        # одноимённые сокеты под разные режимы — берём активный
        return next(s for s in node.inputs if s.name == name and s.enabled)

    def enabled_out(self, node, name):
        return next(s for s in node.outputs if s.name == name and s.enabled)

    def math(self, op, a, b=None, x=0, y=0):
        n = self.node("ShaderNodeMath", x, y, operation=op)
        for i, v in enumerate((a, b)):
            if v is not None:
                self._set(n.inputs[i], v)
        return n.outputs[0]

    def vmath(self, op, a, b=None, x=0, y=0):
        n = self.node("ShaderNodeVectorMath", x, y, operation=op)
        if a is not None:
            self._set(n.inputs[0], a)
        if b is not None:
            self._set(n.inputs["Scale"] if op == "SCALE" else n.inputs[1], b)
        return n.outputs["Value"] if op in ("DISTANCE", "LENGTH", "DOT_PRODUCT") else n.outputs["Vector"]

    def cmp(self, op, a, b, x, y):
        n = self.node("FunctionNodeCompare", x, y, data_type="FLOAT", operation=op)
        self._set(self.enabled(n, "A"), a)
        self._set(self.enabled(n, "B"), b)
        return n.outputs["Result"]

    def boolean(self, op, a, b=None, x=0, y=0):
        n = self.node("FunctionNodeBooleanMath", x, y, operation=op)
        self.link(a, n.inputs[0])
        if b is not None:
            self.link(b, n.inputs[1])
        return n.outputs[0]

    def switch(self, dtype, cond, false, true, x, y):
        n = self.node("GeometryNodeSwitch", x, y, input_type=dtype)
        self.link(cond, n.inputs["Switch"])
        self._set(n.inputs["False"], false)
        self._set(n.inputs["True"], true)
        return n.outputs["Output"]

    def named(self, name, dtype, x, y):
        n = self.node("GeometryNodeInputNamedAttribute", x, y, data_type=dtype)
        n.inputs["Name"].default_value = name
        return n.outputs["Attribute"]

    def store(self, geo, name, dtype, value, x, y, selection=None):
        n = self.node("GeometryNodeStoreNamedAttribute", x, y, data_type=dtype, domain="POINT")
        n.inputs["Name"].default_value = name
        self.link(geo, n.inputs["Geometry"])
        if selection is not None:
            self.link(selection, n.inputs["Selection"])
        self._set(self.enabled(n, "Value"), value)
        return n.outputs["Geometry"]

    def stat(self, geo, value, dtype, x, y, selection=None):
        n = self.node("GeometryNodeAttributeStatistic", x, y, data_type=dtype, domain="POINT")
        self.link(geo, n.inputs["Geometry"])
        if selection is not None:
            self.link(selection, n.inputs["Selection"])
        self.link(value, self.enabled(n, "Attribute"))
        return n


def _new_group(name):
    ng = bpy.data.node_groups.get(name)
    if ng is None:
        ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.nodes.clear()
    return ng


def build_mirror():
    """Одна ось зеркала на точках камней: см. docstring модуля."""
    ng = _new_group(MIRROR_GROUP)
    if not len(ng.interface.items_tree):
        ng.interface.new_socket("Points", in_out="OUTPUT", socket_type="NodeSocketGeometry")
        ng.interface.new_socket("Points", in_out="INPUT", socket_type="NodeSocketGeometry")
        ng.interface.new_socket("Enable", in_out="INPUT", socket_type="NodeSocketBool")
        ng.interface.new_socket("Axis", in_out="INPUT", socket_type="NodeSocketVector")
        ng.interface.new_socket("Radius", in_out="INPUT", socket_type="NodeSocketFloat")

    b = B(ng, -1600)
    pts = b.g("Points")
    axis = b.g("Axis")

    # --- расстояние до плоскости, кто стоит на оси ---
    b.section("On Axis")
    p = b.node("GeometryNodeInputPosition", -1300, 300).outputs[0]
    d = b.vmath("DOT_PRODUCT", p, axis, -1120, 300)
    dist = b.math("ABSOLUTE", d, None, -940, 300)
    near = b.cmp("LESS_THAN", dist, b.g("Radius"), -760, 300)
    on = b.boolean("AND", b.g("Enable"), near, -580, 300)

    vx = b.named(ATTR_X, "FLOAT_VECTOR", -1300, 80)
    vz = b.named(ATTR_Z, "FLOAT_VECTOR", -1300, -80)
    xa = b.vmath("DOT_PRODUCT", vx, axis, -1120, 80)
    za = b.vmath("DOT_PRODUCT", vz, axis, -1120, -80)
    # камень, лежащий в плоскости лицом к оси или вдоль неё, не симметризуется: оси вырождаются
    x_ok = b.cmp("GREATER_THAN", b.math("ABSOLUTE", xa, None, -940, 80), 0.1, -760, 80)
    z_ok = b.cmp("LESS_THAN", b.math("ABSOLUTE", za, None, -940, -80), 0.7, -760, -80)
    fix = b.boolean("AND", on, b.boolean("AND", x_ok, z_ok, -580, 0), -400, 80)

    # --- ряд: камни на оси садятся на плоскость ---
    b.section("Master")
    z_axis = b.vmath("SCALE", axis, za, -220, 420)
    z_new = b.vmath("NORMALIZE", b.vmath("SUBTRACT", vz, z_axis, -40, 420), None, 140, 420)
    x_new = b.vmath("SCALE", axis, b.math("SIGN", xa, None, -40, 240), 140, 240)
    m = b.store(pts, ATTR_Z, "FLOAT_VECTOR", z_new, 340, 420, fix)
    m = b.store(m, ATTR_X, "FLOAT_VECTOR", x_new, 540, 420, fix)
    snap = b.node("GeometryNodeSetPosition", 740, 420)
    b.link(m, snap.inputs["Geometry"])
    b.link(on, snap.inputs["Selection"])
    b.link(b.vmath("SCALE", axis, b.math("MULTIPLY", d, -1.0, 340, 180), 540, 180), snap.inputs["Offset"])

    # --- порядок: отражение относительно конца ряда, что ближе к оси ---
    b.section("Order Pivot")
    order = b.named(ATTR_ORDER, "FLOAT", -220, -60)
    st = b.stat(pts, order, "FLOAT", -40, -60)
    omin, omax = b.enabled_out(st, "Min"), b.enabled_out(st, "Max")
    at_min = b.cmp("LESS_THAN", b.math("ABSOLUTE", b.math("SUBTRACT", order, omin, 140, -60), None, 320, -60),
                   0.25, 500, -60)
    at_max = b.cmp("LESS_THAN", b.math("ABSOLUTE", b.math("SUBTRACT", order, omax, 140, -240), None, 320, -240),
                   0.25, 500, -240)
    dmin = b.enabled_out(b.stat(pts, dist, "FLOAT", 680, -60, at_min), "Mean")
    dmax = b.enabled_out(b.stat(pts, dist, "FLOAT", 680, -300, at_max), "Mean")
    use_max = b.cmp("LESS_EQUAL", dmax, dmin, 880, -180)
    # пол-единицы: конец ряда не на оси получает копию, и у неё другой номер
    pivot = b.switch("FLOAT", use_max, b.math("SUBTRACT", omin, 0.5, 880, -360),
                     b.math("ADD", omax, 0.5, 880, -520), 1060, -180)

    # --- копия: отражение всех камней, кроме стоящих на оси ---
    b.section("Mirror Copy")
    drop = b.boolean("OR", b.boolean("NOT", b.g("Enable"), None, -220, -800), on, -40, -800)
    copy = b.node("GeometryNodeDeleteGeometry", 140, -800, domain="POINT")
    b.link(pts, copy.inputs["Geometry"])
    b.link(drop, copy.inputs["Selection"])
    # X = -отражение(x), Z = отражение(z): R' = M * R * diag(-1, 1, 1), det > 0
    cx = b.vmath("SUBTRACT", b.vmath("SCALE", axis, b.math("MULTIPLY", xa, 2.0, 140, -980), 340, -980), vx, 540, -980)
    cz = b.vmath("SUBTRACT", vz, b.vmath("SCALE", axis, b.math("MULTIPLY", za, 2.0, 340, -1160), 540, -1160), 740, -1160)
    cs = b.math("MULTIPLY", b.named(ATTR_S, "FLOAT", 740, -980), -1.0, 940, -980)
    co = b.math("SUBTRACT", b.math("MULTIPLY", pivot, 2.0, 1140, -980), order, 1320, -980)
    c = b.store(copy.outputs["Geometry"], ATTR_X, "FLOAT_VECTOR", cx, 540, -800)
    c = b.store(c, ATTR_Z, "FLOAT_VECTOR", cz, 740, -800)
    c = b.store(c, ATTR_S, "FLOAT", cs, 940, -800)
    c = b.store(c, ATTR_ORDER, "FLOAT", co, 1140, -800)
    flip = b.node("GeometryNodeSetPosition", 1340, -800)
    b.link(c, flip.inputs["Geometry"])
    b.link(b.vmath("SUBTRACT", p, b.vmath("SCALE", axis, b.math("MULTIPLY", d, 2.0, 1140, -1160), 1320, -1160),
                   1500, -1160), flip.inputs["Position"])

    b.frame = None
    join = b.node("GeometryNodeJoinGeometry", 1700, 0)
    b.link(flip.outputs["Geometry"], join.inputs["Geometry"])
    b.link(snap.outputs["Geometry"], join.inputs["Geometry"])
    gout = b.node("NodeGroupOutput", 1900, 0)
    b.link(join.outputs["Geometry"], gout.inputs["Points"])
    return ng


def build_group():
    mirror = build_mirror()
    ng = bpy.data.node_groups.get(GROUP_NAME)
    if ng is None:
        ng = bpy.data.node_groups.new(GROUP_NAME, "GeometryNodeTree")
    ensure_interface(ng)
    ng.nodes.clear()

    b = B(ng, -300)

    # --- длина камня вдоль кривой и шаг ---
    b.section("Stone Length")
    info = b.node("GeometryNodeObjectInfo", 0, -500, transform_space="ORIGINAL")
    info.inputs["As Instance"].default_value = False
    b.link(b.g("Diam"), info.inputs["Object"])
    bbox = b.node("GeometryNodeBoundBox", 200, -500)
    b.link(info.outputs["Geometry"], bbox.inputs["Geometry"])
    size = b.node("ShaderNodeSeparateXYZ", 580, -500)
    b.link(b.vmath("SUBTRACT", bbox.outputs["Max"], bbox.outputs["Min"], 400, -500), size.inputs[0])
    has = b.cmp("GREATER_THAN", size.outputs["X"], 1e-6, 760, -500)
    factor = b.switch("FLOAT", has, 1.0, size.outputs["X"], 940, -500)
    stone = b.math("MULTIPLY", b.g("Gem Size"), factor, 1120, -500)
    pitch = b.math("ADD", stone, b.g("Spacing"), 1300, -500)
    radius = b.math("MULTIPLY", stone, 0.5, 1300, -680)

    # --- Trim / Offset ---
    b.section("Trim")
    clen = b.node("GeometryNodeCurveLength", 0, 200)
    b.link(b.g("Geometry"), clen.inputs["Curve"])
    start = b.math("ADD", b.g("Trim Curve"), b.g("Offset Curve"), 200, 200)
    rest = b.math("SUBTRACT", clen.outputs["Length"], b.g("Trim Curve"), 200, 20)
    end = b.math("ADD", rest, b.g("Offset Curve"), 380, 20)
    trim = b.node("GeometryNodeTrimCurve", 560, 200, mode="LENGTH")
    b.link(b.g("Geometry"), trim.inputs["Curve"])
    b.link(start, b.enabled(trim, "Start"))
    b.link(end, b.enabled(trim, "End"))

    # --- рез по осям зеркала: остаётся сторона, где среднее положение кривой ---
    b.section("Cut at Mirror Axes")
    fine = b.node("GeometryNodeResampleCurve", 800, 200)
    fine.inputs["Mode"].default_value = "Length"
    b.link(trim.outputs["Curve"], fine.inputs["Curve"])
    b.link(b.math("MULTIPLY", pitch, CUT_STEP, 800, -60), fine.inputs["Length"])
    p = b.node("GeometryNodeInputPosition", 1000, -60).outputs[0]
    st = b.stat(fine.outputs["Curve"], p, "FLOAT_VECTOR", 1000, 200)
    sign = b.vmath("SIGN", b.enabled_out(st, "Mean"), None, 1200, 200)
    mask = b.node("ShaderNodeCombineXYZ", 1200, 20)
    b.link(b.g("XMirror"), mask.inputs["X"])
    b.link(b.g("YMirror"), mask.inputs["Y"])
    b.link(b.g("ZMirror"), mask.inputs["Z"])
    side = b.vmath("MULTIPLY", b.vmath("MULTIPLY", p, sign, 1400, 200), mask.outputs["Vector"], 1580, 200)
    sep = b.node("ShaderNodeSeparateXYZ", 1760, 200)
    b.link(side, sep.inputs[0])
    low = b.math("MINIMUM", b.math("MINIMUM", sep.outputs["X"], sep.outputs["Y"], 1940, 200), sep.outputs["Z"], 2120, 200)
    behind = b.cmp("LESS_THAN", low, 0.0, 2300, 200)
    cut = b.node("GeometryNodeDeleteGeometry", 2480, 200, domain="POINT")
    b.link(fine.outputs["Curve"], cut.inputs["Geometry"])
    b.link(behind, cut.inputs["Selection"])
    # Delete не размыкает замкнутую кривую, Resample учёл бы отрезок через ось
    any_m = b.boolean("OR", b.boolean("OR", b.g("XMirror"), b.g("YMirror"), 2300, 20), b.g("ZMirror"), 2480, 20)
    opened = b.node("GeometryNodeSetSplineCyclic", 2680, 200)
    b.link(cut.outputs["Geometry"], opened.inputs["Geometry"])
    b.link(any_m, opened.inputs["Selection"])
    opened.inputs["Cyclic"].default_value = False

    # --- раскладка: концы ряда на концах кривой, зазор подгоняется ---
    b.section("Layout")
    slen = b.node("GeometryNodeSplineLength", 2920, 20)
    gaps = b.math("FLOOR", b.math("DIVIDE", slen.outputs["Length"], pitch, 3100, 20), None, 3280, 20)
    count = b.math("ADD", gaps, 1.0, 3460, 20)
    coarse = b.node("GeometryNodeResampleCurve", 3640, 200)
    coarse.inputs["Mode"].default_value = "Count"
    b.link(opened.outputs["Geometry"], coarse.inputs["Curve"])
    b.link(count, coarse.inputs["Count"])
    ctilt = b.node("GeometryNodeInputCurveTilt", 3640, -60)
    tilt = b.node("GeometryNodeSetCurveTilt", 3840, 200)
    b.link(coarse.outputs["Curve"], tilt.inputs["Curve"])
    b.link(b.math("ADD", b.g("Tilt"), ctilt.outputs[0], 3840, -60), tilt.inputs["Tilt"])
    c2p = b.node("GeometryNodeCurveToPoints", 4040, 200, mode="EVALUATED")
    b.link(tilt.outputs["Curve"], c2p.inputs["Curve"])
    pts = b.store(c2p.outputs["Points"], ATTR_X, "FLOAT_VECTOR", c2p.outputs["Tangent"], 4240, 200)
    pts = b.store(pts, ATTR_Z, "FLOAT_VECTOR", c2p.outputs["Normal"], 4440, 200)
    pts = b.store(pts, ATTR_S, "FLOAT", 1.0, 4640, 200)
    index = b.node("GeometryNodeInputIndex", 4640, -60)
    pts = b.store(pts, ATTR_ORDER, "FLOAT", index.outputs[0], 4840, 200)

    # --- зеркало X, Y, Z ---
    b.section("Mirror")
    for i, (name, axis) in enumerate((("XMirror", (1.0, 0.0, 0.0)), ("YMirror", (0.0, 1.0, 0.0)),
                                      ("ZMirror", (0.0, 0.0, 1.0)))):
        g = b.node("GeometryNodeGroup", 5100 + i * 220, 200)
        g.node_tree = mirror
        g.label = name
        b.link(pts, g.inputs["Points"])
        b.link(b.g(name), g.inputs["Enable"])
        g.inputs["Axis"].default_value = axis
        b.link(radius, g.inputs["Radius"])
        pts = g.outputs["Points"]

    # --- камни: один Instance on Points на всё ---
    b.section("Stones")
    vz = b.named(ATTR_Z, "FLOAT_VECTOR", 5800, -60)
    pts = b.store(pts, ATTR_UP, "FLOAT_VECTOR", vz, 6000, 200)
    pts = b.store(pts, ATTR_R, "FLOAT", radius, 6200, 200)
    rot = b.node("FunctionNodeAxesToRotation", 6200, -60, primary_axis="Z", secondary_axis="X")
    b.link(vz, rot.inputs["Primary Axis"])
    b.link(b.named(ATTR_X, "FLOAT_VECTOR", 6000, -240), rot.inputs["Secondary Axis"])
    scale = b.node("ShaderNodeCombineXYZ", 6200, -240)
    b.link(b.math("MULTIPLY", b.g("Gem Size"), b.named(ATTR_S, "FLOAT", 5800, -420), 6000, -420), scale.inputs["X"])
    b.link(b.g("Gem Size"), scale.inputs["Y"])
    b.link(b.g("Gem Size"), scale.inputs["Z"])
    gem = b.node("GeometryNodeObjectInfo", 6200, -420, transform_space="ORIGINAL")
    gem.inputs["As Instance"].default_value = True
    b.link(b.g("Diam"), gem.inputs["Object"])
    iop = b.node("GeometryNodeInstanceOnPoints", 6440, 200)
    b.link(pts, iop.inputs["Points"])
    b.link(gem.outputs["Geometry"], iop.inputs["Instance"])
    b.link(rot.outputs["Rotation"], iop.inputs["Rotation"])
    b.link(scale.outputs["Vector"], iop.inputs["Scale"])
    rm = b.node("GeometryNodeRemoveAttribute", 6660, 200)
    rm.inputs["Pattern Mode"].default_value = "Wildcard"
    rm.inputs["Name"].default_value = "_gc_*"
    b.link(iop.outputs["Instances"], rm.inputs["Geometry"])

    b.frame = None
    gout = b.node("NodeGroupOutput", 6900, 200)
    b.link(rm.outputs["Geometry"], gout.inputs["Geometry"])

    print("Node group '%s' rebuilt: %d nodes" % (GROUP_NAME, len(ng.nodes)))
    return ng


def main():
    build_group()


if __name__ == "__main__":
    main()
