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
    Замкнутый ряд (циклическая кривая, Trim Curve = 0, зеркала нет): Trim размыкает кривую
        и оставляет оба конца в одной точке, поэтому режем через шов и замыкаем обратно.
        Камней столько же, сколько зазоров, Offset Curve поворачивает весь ряд.
    Curve to Points: X камня = касательная, Z = нормаль с учётом Tilt.
    Свободный конец ряда: касательная берётся с самой кривой. У ломаной между камнями на конце
        это хорда к соседу, и на изгибе крайний камень разворачивается на половину угла.
        Конец на оси зеркала не трогаем: X задаёт ось, а Z по хорде не зависит от того,
        как последний участок кривой подходит к оси.
    Зеркало (подгруппа Gems Curve Mirror) по очереди X, Y, Z — на точках, а не на инстансах.
    Один Instance on Points.
    Realize: камни становятся мешем, отражённым переворачиваются грани. Включать, только если
        дальше нет My_Prongs: он находит камни по инстансам, без них крапанов не будет.

Камень, пересекающий ось (|d| < половины длины камня), копии не получает и ставится ровно
на ось: Z — среднее с отражением, X — поперёк оси. Копия остальных камней — точное отражение:
повороты считаются так, чтобы матрица была R * diag(-1, 1, 1), знак лежит в gem_mirror и идёт
в Scale X. Иначе несимметричный камень в копии развернулся бы не туда.

Длина камня вдоль кривой — Gem Size * bbox X исходника (багеты), как в My_Gems_On_Curve.

Auto Size: размер камня по радиусу точки кривой (Alt+S), как в My_Gems_On_Curve:
    Map Range Curve R Min..Max -> Stone ø Min..Max, к ближайшему Stone ø Step (0 — без шага).
    Раскладка по длине дуги ряда (после Trim и реза по зеркалу), два Repeat Zone:
        1) жадно от начала: центр следующего = S + R + Spacing + r, r — по размеру в его центре
           (3 уточнения; центр ставится по последнему r, поэтому зазор точный и на смене шага);
           камни, пока центр не вышел за конец (замкнутый ряд — пока есть место под зазор
           до первого камня);
        2) то же число камней с зазором Spacing + остаток / число зазоров.
    Остаток после второго прохода (размеры сдвинулись) — поровну на зазоры.
    Концы ряда на концах кривой, при зеркале камень на оси, как без Auto Size.
    Точки -> Points to Curves -> дальше общий путь (касательные, зеркало, инстансы).
    Размер каждого камня — атрибут _gc_size, gem_r — свой у каждого камня.

Атрибуты на инстансах (их читает My_Prongs):
    gem_order — порядок вдоль ряда. Отражается относительно того конца ряда, что ближе к оси,
                поэтому обход идёт непрерывно через ось и не разворачивается.
    gem_up    — ось Z камня (Instance Rotation не годится: у копий отрицательный масштаб).
    gem_along — ось X камня, по ней встают концевые крапана.
    gem_r     — половина длины камня вдоль кривой.
    gem_size  — размер камня (масштаб инстанса), по нему My_Prongs масштабирует крапана.
    gem_mirror — -1 у зеркальной копии: её ход по кривой обратный, начало ряда стало концом.

Ограничение: замкнутая кривая с включённым зеркалом режется в порядке точек, шов должен быть
на отрезаемой стороне. Для зеркала нужна половина контура. Замкнутая кривая с Trim Curve > 0 —
открытый ряд.

Интерфейс: сокеты только добавляются, если их нет — повторный запуск скрипта
не сбрасывает значения на модификаторах. Узлы пересобираются целиком.
"""

import bpy

GROUP_NAME = "My_Gems_Curve"
MIRROR_GROUP = "Gems Curve Mirror"

ATTR_ORDER = "gem_order"
ATTR_UP = "gem_up"
ATTR_ALONG = "gem_along"
ATTR_R = "gem_r"
ATTR_S = "gem_mirror"  # знак Scale X: -1 у зеркальной копии
ATTR_GEM_SIZE = "gem_size"
ATTR_X = "_gc_x"       # ось X камня
ATTR_Z = "_gc_z"       # ось Z камня
ATTR_SIZE = "_gc_size" # размер камня (масштаб инстанса)
ATTR_SPOS = "_gc_s"    # Auto Size: центр камня по длине ряда
ATTR_IDX = "_gc_i"     # Auto Size: номер камня в ряду
ATTR_TILT = "_gc_tilt" # Auto Size: наклон кривой в центре камня

CUT_STEP = 0.002     # шаг мелкого Resample, доля шага камней: ошибка реза меньше 0.2% шага
SEAM_GAP = 1e-4      # замкнутый ряд режется чуть раньше шва: при равных концах Trim даёт точку

# (имя, тип, default, min, max, панель, subtype)
SOCKETS = [
    ("Diam", "NodeSocketObject", None, None, None, None, None),
    ("Realize", "NodeSocketBool", False, None, None, None, None),
    ("Gem Size", "NodeSocketFloat", 1.0, 0.01, None, "Stone", None),
    ("Spacing", "NodeSocketFloat", 0.1, None, None, "Stone", None),
    ("Trim Curve", "NodeSocketFloat", 0.0, None, None, "Stone", None),
    ("Offset Curve", "NodeSocketFloat", 0.0, None, None, "Stone", None),
    ("Tilt", "NodeSocketFloat", 0.0, None, None, "Stone", "ANGLE"),
    ("Auto Size", "NodeSocketBool", False, None, None, "Auto Size", None),
    ("Curve R Min", "NodeSocketFloat", 1.0, None, None, "Auto Size", None),
    ("Curve R Max", "NodeSocketFloat", 3.0, None, None, "Auto Size", None),
    ("Stone ø Min", "NodeSocketFloat", 1.0, 0.01, None, "Auto Size", None),
    ("Stone ø Max", "NodeSocketFloat", 2.0, 0.01, None, "Auto Size", None),
    ("Stone ø Step", "NodeSocketFloat", 0.1, 0.0, None, "Auto Size", None),
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
    next(i for i in ng.interface.items_tree if i.name == "Realize").description = \
        "Stones become mesh. Keep off if My_Prongs follows: it needs stone instances"


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

    def realize(self, geo, x, y):
        """Галочка Realize. Realize не учитывает отрицательный масштаб: отражённые камни выворачиваются."""
        det = self.node("FunctionNodeMatrixDeterminant", x + 200, y - 200)
        self.link(self.node("GeometryNodeInstanceTransform", x, y - 200).outputs["Transform"], det.inputs[0])
        cap = self.node("GeometryNodeCaptureAttribute", x + 400, y, domain="INSTANCE")
        cap.capture_items.new("BOOLEAN", "Mirrored")
        self.link(geo, cap.inputs["Geometry"])
        self.link(self.cmp("LESS_THAN", det.outputs[0], 0.0, x + 200, y - 360), cap.inputs["Mirrored"])
        real = self.node("GeometryNodeRealizeInstances", x + 600, y)
        self.link(cap.outputs["Geometry"], real.inputs["Geometry"])
        flip = self.node("GeometryNodeFlipFaces", x + 800, y)
        self.link(real.outputs[0], flip.inputs["Mesh"])
        self.link(cap.outputs["Mirrored"], flip.inputs["Selection"])
        return self.switch("GEOMETRY", self.g("Realize"), geo, flip.outputs[0], x + 1000, y)

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


def auto_layout(b, row, factor, x, y):
    """Auto Size: точки камней на ряду row (см. docstring модуля). Выход — ломаная по камням."""
    b.section("Auto Size")
    clen = b.node("GeometryNodeCurveLength", x, y + 400)
    b.link(row, clen.inputs["Curve"])
    length = clen.outputs["Length"]
    loop = b.node("GeometryNodeInputSplineCyclic", x, y + 560).outputs[0]
    closed = b.enabled_out(b.stat(row, loop, "FLOAT", x + 200, y + 560), "Max")  # 1 — замкнутый
    gap = b.g("Spacing")
    rad = b.node("GeometryNodeInputRadius", x, y + 720).outputs[0]
    tilt = b.node("GeometryNodeInputCurveTilt", x, y + 880).outputs[0]

    def sample(value, s, xx, yy):
        n = b.node("GeometryNodeSampleCurve", xx, yy, mode="LENGTH", data_type="FLOAT")
        b.link(row, n.inputs["Curves"])
        b.link(value, n.inputs["Value"])
        b._set(n.inputs["Length"], s)
        return n

    def size_at(s, xx, yy):
        # радиус точки кривой -> ø камня, к ближайшему шагу
        mr = b.node("ShaderNodeMapRange", xx + 200, yy, data_type="FLOAT")
        b.link(sample(rad, s, xx, yy).outputs["Value"], b.enabled(mr, "Value"))
        for sock, name in (("From Min", "Curve R Min"), ("From Max", "Curve R Max"),
                           ("To Min", "Stone ø Min"), ("To Max", "Stone ø Max")):
            b.link(b.g(name), b.enabled(mr, sock))
        v, step = mr.outputs["Result"], b.g("Stone ø Step")
        snapped = b.math("MULTIPLY", b.math("ROUND", b.math("DIVIDE", v, step, xx + 400, yy - 160), None,
                                            xx + 580, yy - 160), step, xx + 760, yy - 160)
        return b.switch("FLOAT", b.cmp("GREATER_THAN", step, 0.0, xx + 400, yy), v, snapped, xx + 940, yy)

    def half(size, xx, yy):
        return b.math("MULTIPLY", b.math("MULTIPLY", size, factor, xx, yy), 0.5, xx + 180, yy)

    def next_stone(s_prev, r_prev, g, xx, yy):
        # центр = S + R + g + r, r — по размеру в центре; 3 уточнения, центр по последнему r
        base = b.math("ADD", b.math("ADD", s_prev, r_prev, xx, yy), g, xx + 180, yy)
        r, size = r_prev, None
        for k in range(3):
            xk = xx + 360 + k * 1400
            size = size_at(b.math("ADD", base, r, xk, yy), xk + 180, yy)
            r = half(size, xk + 1140, yy)
        return b.math("ADD", base, r, xx + 4600, yy), r, size

    def repeat(items, iterations, xx, yy):
        rin = b.node("GeometryNodeRepeatInput", xx, yy)
        rout = b.node("GeometryNodeRepeatOutput", xx + 5600, yy)
        rin.pair_with_output(rout)
        rout.repeat_items.clear()
        for stype, name in items:
            rout.repeat_items.new(stype, name)
        b.link(iterations, rin.inputs["Iterations"])
        return rin, rout

    size0 = size_at(0.0, x, y)
    r0 = half(size0, x + 1140, y)

    # --- проход 1: сколько камней влезает с зазором Spacing ---
    min_size = b.math("MINIMUM", b.g("Stone ø Min"), b.g("Stone ø Max"), x, y - 300)
    stride = b.math("MAXIMUM", b.math("ADD", half(min_size, x + 180, y - 300), gap, x + 540, y - 300), 0.02,
                    x + 720, y - 300)
    iters = b.math("MINIMUM", b.math("ADD", b.math("CEIL", b.math("DIVIDE", length, stride, x + 900, y - 300),
                                                   None, x + 1080, y - 300), 2.0, x + 1260, y - 300), 5000.0,
                   x + 1440, y - 300)
    rin, rout = repeat((("FLOAT", "S"), ("FLOAT", "R"), ("FLOAT", "N")), iters, x + 1600, y - 600)
    b.link(r0, rin.inputs["R"])
    s, r, _ = next_stone(rin.outputs["S"], rin.outputs["R"], gap, x + 1800, y - 600)
    tail = b.math("MULTIPLY", closed, b.math("ADD", b.math("ADD", r, gap, x + 6400, y - 800), r0, x + 6580, y - 800),
                  x + 6760, y - 800)
    fits = b.cmp("LESS_EQUAL", b.math("ADD", s, tail, x + 6940, y - 800),
                 b.math("ADD", length, 1e-5, x + 6940, y - 980), x + 7120, y - 800)
    b.link(b.switch("FLOAT", fits, rin.outputs["S"], s, x + 7000, y - 600), rout.inputs["S"])
    b.link(b.switch("FLOAT", fits, rin.outputs["R"], r, x + 7000, y - 440), rout.inputs["R"])
    b.link(b.math("ADD", rin.outputs["N"], fits, x + 7000, y - 280), rout.inputs["N"])
    extra = rout.outputs["N"]                      # камней после первого

    # остаток -> зазор второго прохода; зазоров n - 1, у замкнутого n
    gaps = b.math("MAXIMUM", b.math("ADD", extra, closed, x + 7400, y - 300), 1.0, x + 7580, y - 300)

    def end_used(s_last, r_last, g, xx, yy):
        pad = b.math("ADD", b.math("ADD", r_last, g, xx, yy), r0, xx + 180, yy)
        return b.math("ADD", s_last, b.math("MULTIPLY", closed, pad, xx + 360, yy), xx + 540, yy)

    def share(s_last, r_last, g, xx, yy):
        left = b.math("SUBTRACT", length, end_used(s_last, r_last, g, xx, yy), xx + 720, yy)
        return b.math("DIVIDE", left, gaps, xx + 900, yy)

    gap2 = b.math("ADD", gap, share(rout.outputs["S"], rout.outputs["R"], gap, x + 7400, y - 480), x + 8480, y - 480)

    # --- проход 2: те же камни с подогнанным зазором, точки с размером и номером ---
    def stone_point(s_val, size, idx, xx, yy):
        pt = b.node("GeometryNodePoints", xx, yy)
        geo = b.store(pt.outputs["Points"], ATTR_SPOS, "FLOAT", s_val, xx + 200, yy)
        geo = b.store(geo, ATTR_SIZE, "FLOAT", size, xx + 400, yy)
        return b.store(geo, ATTR_IDX, "FLOAT", idx, xx + 600, yy)

    first = stone_point(0.0, size0, 0.0, x + 8600, y - 1400)
    rin2, rout2 = repeat((("GEOMETRY", "Stones"), ("FLOAT", "S"), ("FLOAT", "R"), ("FLOAT", "I")), extra,
                         x + 8800, y - 1100)
    b.link(first, rin2.inputs["Stones"])
    b.link(r0, rin2.inputs["R"])
    s2, r2, size2 = next_stone(rin2.outputs["S"], rin2.outputs["R"], gap2, x + 9000, y - 1100)
    i2 = b.math("ADD", rin2.outputs["I"], 1.0, x + 13800, y - 1300)
    join = b.node("GeometryNodeJoinGeometry", x + 14200, y - 1100)
    b.link(rin2.outputs["Stones"], join.inputs["Geometry"])
    b.link(stone_point(s2, size2, i2, x + 13800, y - 1500), join.inputs["Geometry"])
    b.link(join.outputs["Geometry"], rout2.inputs["Stones"])
    b.link(s2, rout2.inputs["S"])
    b.link(r2, rout2.inputs["R"])
    b.link(i2, rout2.inputs["I"])

    # --- остаток после второго прохода поровну на зазоры, точки на ряд ---
    per = share(rout2.outputs["S"], rout2.outputs["R"], gap2, x + 14600, y - 800)
    s_fin = b.math("ADD", b.named(ATTR_SPOS, "FLOAT", x + 15600, y - 1300),
                   b.math("MULTIPLY", b.named(ATTR_IDX, "FLOAT", x + 15600, y - 1460), per, x + 15780, y - 1460),
                   x + 15960, y - 1300)
    on_row = sample(tilt, s_fin, x + 16140, y - 1300)
    pts = b.store(rout2.outputs["Stones"], ATTR_TILT, "FLOAT", on_row.outputs["Value"], x + 16400, y - 1100)
    place = b.node("GeometryNodeSetPosition", x + 16600, y - 1100)
    b.link(pts, place.inputs["Geometry"])
    b.link(on_row.outputs["Position"], place.inputs["Position"])
    p2c = b.node("GeometryNodePointsToCurves", x + 16800, y - 1100)
    b.link(place.outputs["Geometry"], p2c.inputs["Points"])
    b.link(b.named(ATTR_IDX, "FLOAT", x + 16600, y - 1300), p2c.inputs["Weight"])
    st = b.node("GeometryNodeSetCurveTilt", x + 17000, y - 1100)
    b.link(p2c.outputs["Curves"], st.inputs["Curve"])
    b.link(b.named(ATTR_TILT, "FLOAT", x + 16800, y - 1300), st.inputs["Tilt"])
    cyc = b.node("GeometryNodeSetSplineCyclic", x + 17200, y - 1100)
    b.link(st.outputs["Curve"], cyc.inputs["Geometry"])
    b.link(b.cmp("GREATER_THAN", closed, 0.5, x + 17000, y - 1300), cyc.inputs["Cyclic"])
    return cyc.outputs["Geometry"]


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
    # мелкий шаг реза: при Auto Size — по самому мелкому камню
    min_stone = b.math("MULTIPLY", b.math("MINIMUM", b.g("Stone ø Min"), b.g("Stone ø Max"), 1120, -680), factor,
                       1300, -680)
    cut_pitch = b.switch("FLOAT", b.g("Auto Size"), pitch,
                         b.math("ADD", min_stone, b.g("Spacing"), 1480, -680), 1660, -500)
    # размер и половина длины камня — свои у каждой точки (атрибут _gc_size)
    size_f = b.named(ATTR_SIZE, "FLOAT", 1120, -860)
    radius = b.math("MULTIPLY", b.math("MULTIPLY", size_f, factor, 1300, -860), 0.5, 1480, -860)

    # --- Trim / Offset ---
    b.section("Trim")
    clen = b.node("GeometryNodeCurveLength", 0, 200)
    b.link(b.g("Geometry"), clen.inputs["Curve"])
    start = b.math("ADD", b.g("Trim Curve"), b.g("Offset Curve"), 200, 200)
    rest = b.math("SUBTRACT", clen.outputs["Length"], b.g("Trim Curve"), 200, 20)
    end = b.math("ADD", rest, b.g("Offset Curve"), 380, 20)
    # замкнутый ряд: Start > End ведёт Trim через шов, вся кривая начинается с Offset Curve
    any_m = b.boolean("OR", b.boolean("OR", b.g("XMirror"), b.g("YMirror"), 0, 800), b.g("ZMirror"), 200, 800)
    is_loop = b.node("GeometryNodeInputSplineCyclic", 0, 640).outputs[0]
    whole = b.cmp("EQUAL", b.g("Trim Curve"), 0.0, 0, 520)
    closed = b.boolean("AND", is_loop,
                       b.boolean("AND", whole, b.boolean("NOT", any_m, None, 200, 640), 380, 640), 560, 640)
    cap = b.node("GeometryNodeCaptureAttribute", 380, 420, domain="CURVE")
    cap.capture_items.new("BOOLEAN", "Closed")
    b.link(b.g("Geometry"), cap.inputs["Geometry"])
    b.link(closed, cap.inputs["Closed"])
    loop_len = b.node("GeometryNodeSplineLength", 0, -160).outputs["Length"]
    from_seam = b.math("FLOORED_MODULO", b.g("Offset Curve"), loop_len, 380, -160)
    to_seam = b.math("FLOORED_MODULO", b.math("SUBTRACT", b.g("Offset Curve"), SEAM_GAP, 200, -320), loop_len, 380, -320)
    trim = b.node("GeometryNodeTrimCurve", 760, 420, mode="LENGTH")
    b.link(cap.outputs["Geometry"], trim.inputs["Curve"])
    b.link(b.switch("FLOAT", closed, start, from_seam, 560, -160), b.enabled(trim, "Start"))
    b.link(b.switch("FLOAT", closed, end, to_seam, 560, -320), b.enabled(trim, "End"))

    # --- рез по осям зеркала: остаётся сторона, где среднее положение кривой ---
    b.section("Cut at Mirror Axes")
    fine = b.node("GeometryNodeResampleCurve", 800, 200)
    fine.inputs["Mode"].default_value = "Length"
    b.link(trim.outputs["Curve"], fine.inputs["Curve"])
    b.link(b.math("MULTIPLY", cut_pitch, CUT_STEP, 800, -60), fine.inputs["Length"])
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
    row = b.node("GeometryNodeSetSplineCyclic", 2680, 200)
    b.link(cut.outputs["Geometry"], row.inputs["Geometry"])
    b.link(cap.outputs["Closed"], row.inputs["Selection"])
    row.inputs["Cyclic"].default_value = True

    # --- раскладка: концы ряда на концах кривой, зазор подгоняется ---
    b.section("Layout")
    slen = b.node("GeometryNodeSplineLength", 2920, 20)
    gaps = b.math("FLOOR", b.math("DIVIDE", slen.outputs["Length"], pitch, 3100, 20), None, 3280, 20)
    # в замкнутом ряду камней столько же, сколько зазоров, в открытом на один больше
    count = b.math("ADD", gaps, b.switch("FLOAT", is_loop, 1.0, 0.0, 3280, -140), 3460, 20)
    coarse = b.node("GeometryNodeResampleCurve", 3640, 200)
    coarse.inputs["Mode"].default_value = "Count"
    b.link(row.outputs["Geometry"], coarse.inputs["Curve"])
    b.link(count, coarse.inputs["Count"])
    fixed = b.store(coarse.outputs["Curve"], ATTR_SIZE, "FLOAT", b.g("Gem Size"), 3640, 400)
    layout = b.frame
    auto = auto_layout(b, row.outputs["Geometry"], factor, 2920, 2200)
    b.frame = layout
    laid = b.switch("GEOMETRY", b.g("Auto Size"), fixed, auto, 3840, 400)
    ctilt = b.node("GeometryNodeInputCurveTilt", 3640, -60)
    tilt = b.node("GeometryNodeSetCurveTilt", 3840, 200)
    b.link(laid, tilt.inputs["Curve"])
    b.link(b.math("ADD", b.g("Tilt"), ctilt.outputs[0], 3840, -60), tilt.inputs["Tilt"])

    # --- свободные концы ряда: касательная кривой вместо хорды к соседу ---
    b.section("Free Ends")
    ends = b.node("GeometryNodeCurveEndpointSelection", 3100, -320)
    pos = b.node("GeometryNodeInputPosition", 3100, -500).outputs[0]
    off = b.vmath("SCALE", b.vmath("SUBTRACT", (1.0, 1.0, 1.0), mask.outputs["Vector"], 3100, -640), 1e6, 3280, -640)
    far = b.vmath("ADD", b.vmath("ABSOLUTE", pos, None, 3280, -500), off, 3460, -500)
    fs = b.node("ShaderNodeSeparateXYZ", 3640, -500)
    b.link(far, fs.inputs[0])
    nearest = b.math("MINIMUM", b.math("MINIMUM", fs.outputs["X"], fs.outputs["Y"], 3820, -500), fs.outputs["Z"], 4000, -500)
    # у замкнутого ряда концов нет
    free = b.boolean("AND", b.boolean("AND", ends.outputs["Selection"], b.boolean("NOT", is_loop, None, 3280, -320), 3460, -320),
                     b.cmp("GREATER_EQUAL", nearest, radius, 4180, -500), 4360, -320)
    param = b.node("GeometryNodeSplineParameter", 3460, -760)
    of_point = b.node("GeometryNodeCurveOfPoint", 3460, -920)
    sample = b.node("GeometryNodeSampleCurve", 3820, -760, mode="FACTOR")
    b.link(row.outputs["Geometry"], sample.inputs["Curves"])
    b.link(param.outputs["Factor"], sample.inputs["Factor"])
    b.link(of_point.outputs["Curve Index"], sample.inputs["Curve Index"])
    tangent = b.node("GeometryNodeInputTangent", 4180, -760).outputs[0]
    axis_x = b.switch("VECTOR", free, tangent, sample.outputs["Tangent"], 4360, -760)

    b.frame = layout
    curve = b.store(tilt.outputs["Curve"], ATTR_X, "FLOAT_VECTOR", axis_x, 4040, 200)
    c2p = b.node("GeometryNodeCurveToPoints", 4240, 200, mode="EVALUATED")
    b.link(curve, c2p.inputs["Curve"])
    # Z остаётся нормалью ломаной, только перпендикулярно новому X: крен ряда не меняется
    vx = b.named(ATTR_X, "FLOAT_VECTOR", 4240, -60)
    along = b.vmath("SCALE", vx, b.vmath("DOT_PRODUCT", c2p.outputs["Normal"], vx, 4420, -60), 4600, -60)
    z = b.vmath("NORMALIZE", b.vmath("SUBTRACT", c2p.outputs["Normal"], along, 4780, -60), None, 4960, -60)
    pts = b.store(c2p.outputs["Points"], ATTR_Z, "FLOAT_VECTOR", z, 4440, 200)
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
    pts = b.store(pts, ATTR_ALONG, "FLOAT_VECTOR", b.named(ATTR_X, "FLOAT_VECTOR", 5800, -240), 6100, 200)
    pts = b.store(pts, ATTR_R, "FLOAT", radius, 6200, 200)
    pts = b.store(pts, ATTR_GEM_SIZE, "FLOAT", size_f, 6300, 200)
    rot = b.node("FunctionNodeAxesToRotation", 6200, -60, primary_axis="Z", secondary_axis="X")
    b.link(vz, rot.inputs["Primary Axis"])
    b.link(b.named(ATTR_X, "FLOAT_VECTOR", 6000, -240), rot.inputs["Secondary Axis"])
    scale = b.node("ShaderNodeCombineXYZ", 6200, -240)
    b.link(b.math("MULTIPLY", size_f, b.named(ATTR_S, "FLOAT", 5800, -420), 6000, -420), scale.inputs["X"])
    b.link(size_f, scale.inputs["Y"])
    b.link(size_f, scale.inputs["Z"])
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
    done = b.realize(rm.outputs["Geometry"], 6900, 200)
    gout = b.node("NodeGroupOutput", 8100, 200)
    b.link(done, gout.inputs["Geometry"])

    print("Node group '%s' rebuilt: %d nodes" % (GROUP_NAME, len(ng.nodes)))
    return ng


def main():
    build_group()


if __name__ == "__main__":
    main()
