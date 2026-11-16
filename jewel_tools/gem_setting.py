# SPDX-License-Identifier: GPL-3.0-or-later

"""Каст с крапанами под камень: клетка под Subdivision Surface (группа My_Gem_Setting).

Объект-каст — ребёнок камня, его базовый меш в координатах камня в плоскости z = 0:
    петля рундиста — вершины, соединённые рёбрами в замкнутый контур, атрибут corner
        (FLOAT, POINT: 1 — острый угол, 0 или нет атрибута — гладкая точка);
    места крапанов (sites) — вершины без рёбер на контуре.
Меш можно править руками: сдвинуть или добавить вершину-крапан, нарисовать свой контур.
За GN-модификатором в стеке — обычный Subdivision Surface: после Apply группы остаётся
редактируемая клетка. Каждая деталь — своя замкнутая правильная оболочка (крапан — 12 вершин,
рейка — трубка петля x 4), оболочки только пересекаются; склейка — Build Metal Mesh.

Предел петли (кривая SubD) — сплайн Безье: узел P у острой вершины и (P- + 4 P + P+) / 6
у гладкой, ручки (2 P + P±) / 3 (см. gem_outline.limit_curve). Нормаль контура у крапана —
по ближайшей точке этого сплайна (выборка LIMIT_RES точек на пролёт; касательная выборки
в острой вершине — биссектриса).

Крапан — проволока: ось через Pb и Pg, Pg = site + n * Prong Offset (z = 0), Pb = Pg с XY
* Bottom Scale на z = -Basket Height; сторона квадратного сечения смотрит на камень.
Три кольца: основание — сечение призмы плоскостью z = -Basket Height (плоский горизонтальный
торец, crease 1), плечо и верхушка — поперёк оси, верхний торец гладкий. Ствол от основания
до плеча: диаметр Prong Diameter -> Prong Diameter * Tip Scale; купол над плечом — шаг плечо —
верхушка, по Tip Round от почти плоского среза до полусферы. Длина ствола — так, что самая
верхняя точка после SubD на Prong Height с учётом наклона оси.

Рейка: петля, смещённая по биссектрисе b вершины на b * s, x прямоугольный профиль; рёбра колец
в острых вершинах — crease 1, продольные — Rail Sharpness. Острая вершина: s = 1 / cos(половины
поворота) (не больше MITER_LIMIT). Гладкая: предел смещённой петли в вершине отстоит на 1
по нормали предела N: (s- b- + 4 s b + s+ b+) / 6 . N = 1 — локальная оценка
s = 6 / (4 + b- . N + b+ . N) и один шаг Якоби с настоящими s соседей.
Ограничение: предел смещённой клетки — не точная параллельная кривая. Ширина сечения у огранок
из отрезков точная, у кривых — до -4.7 % (сердце растянутое), у остальных в пределах 3.7 %
(замер tools/test_gem_setting.py). Предел одного кольца на точку петли: даже оптимум МНК даёт
до 3.4 % (сердце); второй шаг Якоби меняет меньше 0.3 %.

Коэффициенты получены замером (SubD levels 5-6, quality 3, Use Limit Surface; Blender 5.2):
    crease c переходит в резкость OpenSubdiv 10 c^2; размах сечения трубки = клетка
        * (11 + min(1, 10 c^2)) / 12 — как у B-сплайна квадрата (замер совпал до 1e-5);
    K_PRISM = (11/12 + 2 sqrt(2)/3) / 2: средний радиус ствола / полусторона квадрата
        (по стороне 11/12, по диагонали 2 sqrt(2)/3, разброс +-1.4 %); основание косое —
        профиль поперёк оси тот же, все кольца ствола — сдвиги одного квадрата вдоль оси;
    DOME_APEX = 149/162: вершина купола выше кольца плеча на 149/162 шага плечо — верхушка
        (зависит только от двух верхних колец, не от размеров и длины ствола);
    TIP_FLARE: верхушка шире плеча — купол ближе к эллипсу (при 1 купол начинается ниже плеча
        и вытянут «пулей»); ствол у плеча — до +1.3 %;
    SHOULDER_A, SHOULDER_B: полусторона плеча = основание * (A * Tip Scale - B): оценка
        B-сплайна (6 TS - 1) / (4 + TIP_FLARE) (узел плеча на TS) и + 0.1 (1 - TS) по замеру
        (иначе при Tip Scale 0.8 у плеча на 2-4 % тоньше);
    DOME_MIN, DOME_MAX: шаг плечо — верхушка в полусторонах плеча при Tip Round 0 и 1. Купол —
        аффинный образ одной формы (по оси ~ шагу), она полнее полусферы: высота скругления
        (эллипс с экватором по сечениям 0.3-0.95 радиуса) растёт линейно с шагом; 1.8 — скругление
        высотой в радиус верхушки (полусфера: 0.98 при Tip Scale 1, 1.14 при 0.8 — сужающийся ствол
        начинает скругление раньше), 0.1 — почти плоский срез со скруглённым краем;
    DOME_RHO, DOME_ETA: при наклоне phi самая верхняя точка купола выше его вершины на
        sqrt((RHO h sin)^2 + (ETA delta cos)^2) - ETA delta cos, h — полусторона плеча, delta —
        шаг (купол — аффинный образ одного: по радиусу ~ h, по оси ~ delta); подгонка по 120
        замерам, наклон до 40°: ошибка < 0.013 h, до 50°: < 0.023 h.
"""

from __future__ import annotations

from math import hypot, sqrt

import bpy
from mathutils import Matrix

from . import gem_outline

GROUP_NAME = "My_Gem_Setting"
SUBD_NAME = "Subdivision"
LIMIT_RES = 64           # точек предела на пролёт петли для нормали у крапана
MITER_LIMIT = 4.0        # предел выноса рейки в острой вершине: 1 / cos(половины поворота)
K_PRISM = (11.0 / 12.0 + 2.0 * sqrt(2.0) / 3.0) * 0.5
DOME_APEX = 149.0 / 162.0
TIP_FLARE = 1.15
SHOULDER_A = 6.0 / (4.0 + TIP_FLARE) - 0.1
SHOULDER_B = 1.0 / (4.0 + TIP_FLARE) - 0.1
DOME_MIN = 0.1
DOME_MAX = 1.8
DOME_RHO = 0.85
DOME_ETA = 0.29
PRONG_HEIGHT_K = 0.5     # начальный Prong Height: доля верха короны
BASKET_HEIGHT_K = 0.75   # начальный Basket Height: доля глубины павильона

# (имя, тип, default, min, max, панель, subtype)
SOCKETS = [
    ("Metal Material", "NodeSocketMaterial", None, None, None, None, None),
    ("Prongs", "NodeSocketBool", True, None, None, "Prongs", None),
    ("Prong Diameter", "NodeSocketFloat", 0.8, 0.05, None, "Prongs", None),
    ("Prong Height", "NodeSocketFloat", 1.0, None, None, "Prongs", None),
    ("Prong Offset", "NodeSocketFloat", 0.15, None, None, "Prongs", None),
    ("Tip Scale", "NodeSocketFloat", 0.8, 0.0, 1.0, "Prongs", "FACTOR"),
    ("Tip Round", "NodeSocketFloat", 1.0, 0.0, 1.0, "Prongs", "FACTOR"),
    ("Basket Height", "NodeSocketFloat", 1.5, 0.0, None, "Basket", None),
    ("Bottom Scale", "NodeSocketFloat", 0.75, 0.05, 1.0, "Basket", "FACTOR"),
    ("Top Rail", "NodeSocketBool", True, None, None, "Basket", None),
    ("Bottom Rail", "NodeSocketBool", True, None, None, "Basket", None),
    ("Rail Width", "NodeSocketFloat", 0.6, 0.05, None, "Basket", None),
    ("Rail Height", "NodeSocketFloat", 0.4, 0.05, None, "Basket", None),
    ("Rail Offset", "NodeSocketFloat", 0.15, None, None, "Basket", None),
    ("Rail Drop", "NodeSocketFloat", 0.2, 0.0, None, "Basket", None),
    ("Rail Sharpness", "NodeSocketFloat", 0.5, 0.0, 1.0, "Basket", "FACTOR"),
]


def ensure_interface(ng):
    """Сокеты по именам: недостающие добавить, существующие не трогать."""
    items = {(it.name, it.item_type, getattr(it, "in_out", None)) for it in ng.interface.items_tree}
    if ("Geometry", "SOCKET", "INPUT") not in items:
        ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    if ("Geometry", "SOCKET", "OUTPUT") not in items:
        ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    panels = {it.name: it for it in ng.interface.items_tree if it.item_type == "PANEL"}
    names = {it.name for it in ng.interface.items_tree if it.item_type == "SOCKET" and it.in_out == "INPUT"}
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


class _B:
    """Короткие помощники сборки графа."""

    def __init__(self, ng):
        self.ng, self.N, self.L = ng, ng.nodes, ng.links
        self.frame = None
        self.gin = self.N.new("NodeGroupInput")
        self.gin.location = (-400, 0)

    def section(self, label):
        """Следующие узлы — в рамке с этой подписью."""
        self.frame = self.N.new("NodeFrame")
        self.frame.label = label
        self.frame.label_size = 16

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

    def put(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.link(v, sock)
        else:
            sock.default_value = v

    def math(self, op, a, b=None, c=None, x=0, y=0):
        n = self.node("ShaderNodeMath", x, y, operation=op)
        for i, v in enumerate((a, b, c)):
            if v is not None:
                self.put(n.inputs[i], v)
        return n.outputs[0]

    def vmath(self, op, a, b=None, c=None, x=0, y=0):
        n = self.node("ShaderNodeVectorMath", x, y, operation=op)
        self.put(n.inputs[0], a)
        if b is not None:
            self.put(n.inputs["Scale"] if op == "SCALE" else n.inputs[1], b)
        if c is not None:
            self.put(n.inputs[2], c)
        return n.outputs["Value"] if op in ("LENGTH", "DOT_PRODUCT", "DISTANCE") else n.outputs["Vector"]

    def cmp(self, op, a, b, x, y, dtype="FLOAT"):
        n = self.node("FunctionNodeCompare", x, y, data_type=dtype, operation=op)
        ab = [s for s in n.inputs if s.enabled]
        self.put(ab[0], a)
        self.put(ab[1], b)
        return n.outputs["Result"]

    def boolean(self, op, a, b=None, x=0, y=0):
        n = self.node("FunctionNodeBooleanMath", x, y, operation=op)
        self.put(n.inputs[0], a)
        if b is not None:
            self.put(n.inputs[1], b)
        return n.outputs[0]

    def switch(self, dtype, cond, false, true, x, y):
        n = self.node("GeometryNodeSwitch", x, y, input_type=dtype)
        self.put(n.inputs["Switch"], cond)
        self.put(n.inputs["False"], false)
        self.put(n.inputs["True"], true)
        return n.outputs["Output"]

    def combine(self, vx, vy, vz, x, y):
        n = self.node("ShaderNodeCombineXYZ", x, y)
        for sock, v in zip(n.inputs, (vx, vy, vz)):
            self.put(sock, v)
        return n.outputs[0]

    def separate(self, v, x, y):
        n = self.node("ShaderNodeSeparateXYZ", x, y)
        self.link(v, n.inputs[0])
        return n.outputs

    def named(self, name, dtype, x, y):
        n = self.node("GeometryNodeInputNamedAttribute", x, y, data_type=dtype)
        n.inputs["Name"].default_value = name
        return n.outputs["Attribute"]

    def store(self, geo, name, dtype, value, x, y, domain="POINT"):
        n = self.node("GeometryNodeStoreNamedAttribute", x, y, data_type=dtype, domain=domain)
        n.inputs["Name"].default_value = name
        self.link(geo, n.inputs["Geometry"])
        self.put(n.inputs["Value"], value)
        return n.outputs["Geometry"]

    def at_index(self, value, index, dtype, x, y):
        n = self.node("GeometryNodeFieldAtIndex", x, y, data_type=dtype, domain="POINT")
        self.link(value, n.inputs["Value"])
        self.link(index, n.inputs["Index"])
        return n.outputs["Value"]


def build_group():
    """Собрать (или пересобрать) группу My_Gem_Setting. Сокеты только добавляются."""
    ng = bpy.data.node_groups.get(GROUP_NAME)
    if ng is None:
        ng = bpy.data.node_groups.new(GROUP_NAME, "GeometryNodeTree")
    ensure_interface(ng)
    ng.is_modifier = True
    ng.nodes.clear()
    b = _B(ng)
    up = (0.0, 0.0, 1.0)

    # --- петля: рёбра базового меша, против часовой ---
    b.section("Loop")
    loop = b.node("GeometryNodeMeshToCurve", 0, 300)
    b.link(b.g("Geometry"), loop.inputs["Mesh"])
    pos = b.node("GeometryNodeInputPosition", 0, 0).outputs[0]
    nxt = b.node("GeometryNodeOffsetPointInCurve", 0, -150)
    nxt.inputs["Offset"].default_value = 1
    prv = b.node("GeometryNodeOffsetPointInCurve", 0, -350)
    prv.inputs["Offset"].default_value = -1
    p_next = b.at_index(pos, nxt.outputs["Point Index"], "FLOAT_VECTOR", 200, -150)
    p_prev = b.at_index(pos, prv.outputs["Point Index"], "FLOAT_VECTOR", 200, -350)
    # удвоенная площадь каждой петли: сумма P x P+ по точкам её кривой
    cross = b.separate(b.vmath("CROSS_PRODUCT", pos, p_next, x=400, y=100), 600, 100)["Z"]
    of_curve = b.node("GeometryNodeCurveOfPoint", 400, -100)
    area = b.node("GeometryNodeAccumulateField", 800, 100, data_type="FLOAT", domain="POINT")
    b.link(cross, area.inputs["Value"])
    b.link(of_curve.outputs["Curve Index"], area.inputs["Group ID"])
    ccw = b.node("GeometryNodeReverseCurve", 1000, 300)
    b.link(loop.outputs["Curve"], ccw.inputs["Curve"])
    b.link(b.cmp("LESS_THAN", area.outputs["Total"], 0.0, 1000, 100), ccw.inputs["Selection"])
    loop = ccw.outputs["Curve"]
    sharp = b.cmp("GREATER_THAN", b.named("corner", "FLOAT", 400, -500), 0.5, 600, -500)
    count = b.node("GeometryNodeAttributeDomainSize", 1000, -100, component="CURVE")
    b.link(loop, count.inputs["Geometry"])
    has_loop = b.cmp("GREATER_THAN", count.outputs["Point Count"], 0, 1200, -100, dtype="INT")

    # --- предел петли сплайном Безье: точки с касательной ---
    b.section("Limit Curve")
    x0 = 1500
    hl = b.vmath("SCALE", b.vmath("MULTIPLY_ADD", pos, (2.0, 2.0, 2.0), p_prev, x=x0, y=-100), 1.0 / 3.0,
                 x=x0 + 180, y=-100)
    hr = b.vmath("SCALE", b.vmath("MULTIPLY_ADD", pos, (2.0, 2.0, 2.0), p_next, x=x0, y=-260), 1.0 / 3.0,
                 x=x0 + 180, y=-260)
    handles = b.node("GeometryNodeCaptureAttribute", x0 + 380, 300, domain="POINT")
    handles.capture_items.new("VECTOR", "Left")
    handles.capture_items.new("VECTOR", "Right")
    b.link(loop, handles.inputs["Geometry"])
    b.link(hl, handles.inputs["Left"])
    b.link(hr, handles.inputs["Right"])
    bez = b.node("GeometryNodeCurveSplineType", x0 + 580, 300, spline_type="BEZIER")
    b.link(handles.outputs["Geometry"], bez.inputs["Curve"])
    free = b.node("GeometryNodeCurveSetHandles", x0 + 780, 300, handle_type="FREE", mode={"LEFT", "RIGHT"})
    b.link(bez.outputs["Curve"], free.inputs["Curve"])
    smooth_k = b.vmath("SCALE", b.vmath("MULTIPLY_ADD", pos, (4.0, 4.0, 4.0),
                                        b.vmath("ADD", p_prev, p_next, x=x0, y=-420), x=x0 + 180, y=-420),
                       1.0 / 6.0, x=x0 + 360, y=-420)
    knot = b.node("GeometryNodeSetPosition", x0 + 980, 300)
    b.link(free.outputs["Curve"], knot.inputs["Geometry"])
    b.link(b.switch("VECTOR", sharp, smooth_k, pos, x0 + 780, -420), knot.inputs["Position"])
    left = b.node("GeometryNodeSetCurveHandlePositions", x0 + 1180, 300, mode="LEFT")
    b.link(knot.outputs["Geometry"], left.inputs["Curve"])
    b.link(handles.outputs["Left"], left.inputs["Position"])
    right = b.node("GeometryNodeSetCurveHandlePositions", x0 + 1380, 300, mode="RIGHT")
    b.link(left.outputs["Curve"], right.inputs["Curve"])
    b.link(handles.outputs["Right"], right.inputs["Position"])
    res = b.node("GeometryNodeSetSplineResolution", x0 + 1580, 300)
    b.link(right.outputs["Curve"], res.inputs["Curve"])
    res.inputs["Resolution"].default_value = LIMIT_RES
    limit = b.node("GeometryNodeCurveToPoints", x0 + 1780, 300, mode="EVALUATED")
    b.link(res.outputs["Curve"], limit.inputs["Curve"])

    # --- рейки: две копии петли, смещённые по биссектрисе ---
    b.section("Rails")
    x0 = 1500
    y0 = -900
    d_in = b.vmath("NORMALIZE", b.vmath("SUBTRACT", pos, p_prev, x=x0, y=y0 - 200), x=x0 + 180, y=y0 - 200)
    d_out = b.vmath("NORMALIZE", b.vmath("SUBTRACT", p_next, pos, x=x0, y=y0 - 360), x=x0 + 180, y=y0 - 360)
    turn = b.vmath("ADD", d_in, d_out, x=x0 + 360, y=y0 - 280)
    bis = b.vmath("NORMALIZE", b.vmath("CROSS_PRODUCT", turn, up, x=x0 + 540, y=y0 - 240), x=x0 + 720, y=y0 - 240)
    # вынос по биссектрисе b * s. Острая вершина: s = 1 / cos(половины поворота) = 2 / |d_in + d_out|
    # (не больше MITER_LIMIT), предел клетки в ней — сама вершина
    miter = b.math("MINIMUM", b.math("DIVIDE", 2.0, b.vmath("LENGTH", turn, x=x0 + 540, y=y0 - 400),
                                     x=x0 + 720, y=y0 - 400), MITER_LIMIT, x=x0 + 900, y=y0 - 400)
    # гладкая: предел смещённой петли в вершине на расстоянии 1 по нормали предела N:
    # (s- b- + 4 s b + s+ b+) / 6 . N = 1; N — поперёк P+ - P- (касательная B-сплайна в узле)
    chord = b.vmath("NORMALIZE", b.vmath("CROSS_PRODUCT", b.vmath("SUBTRACT", p_next, p_prev, x=x0, y=y0 - 1400),
                                         up, x=x0 + 180, y=y0 - 1400), x=x0 + 360, y=y0 - 1400)
    bn_prev = b.vmath("DOT_PRODUCT", b.at_index(bis, prv.outputs["Point Index"], "FLOAT_VECTOR", x0 + 360, y0 - 1560),
                      chord, x=x0 + 540, y=y0 - 1560)
    bn_next = b.vmath("DOT_PRODUCT", b.at_index(bis, nxt.outputs["Point Index"], "FLOAT_VECTOR", x0 + 360, y0 - 1720),
                      chord, x=x0 + 540, y=y0 - 1720)
    # начальное приближение: соседи с тем же s и b . N = 1 — s = 6 / (4 + b- . N + b+ . N)
    s0 = b.switch("FLOAT", sharp, b.math("DIVIDE", 6.0, b.math("ADD", b.math("ADD", bn_prev, bn_next, x=x0 + 720,
                                                                               y=y0 - 1560), 4.0, x=x0 + 900,
                                                                  y=y0 - 1560), x=x0 + 1080, y=y0 - 1560),
                  miter, x0 + 1260, y0 - 1560)
    # шаг Якоби с настоящими s соседей (у острых — митра); второй шаг даёт < 0.3 %
    pull = b.math("MULTIPLY_ADD", b.at_index(s0, nxt.outputs["Point Index"], "FLOAT", x0 + 1260, y0 - 1880), bn_next,
                  b.math("MULTIPLY", b.at_index(s0, prv.outputs["Point Index"], "FLOAT", x0 + 1260, y0 - 1720),
                         bn_prev, x=x0 + 1440, y=y0 - 1720), x=x0 + 1620, y=y0 - 1800)
    s1 = b.math("DIVIDE", b.math("SUBTRACT", 6.0, pull, x=x0 + 1800, y=y0 - 1800),
                b.math("MULTIPLY", b.vmath("DOT_PRODUCT", bis, chord, x=x0 + 1620, y=y0 - 1960), 4.0,
                       x=x0 + 1800, y=y0 - 1960), x=x0 + 1980, y=y0 - 1800)
    offset = b.vmath("SCALE", bis, b.switch("FLOAT", sharp, s1, miter, x0 + 2160, y0 - 1800), x=x0 + 1080, y=y0 - 280)
    # усадка профиля SubD: размах = клетка * (11 + min(1, 10 c^2)) / 12
    sharp_r = b.math("MINIMUM", b.math("MULTIPLY", b.math("POWER", b.g("Rail Sharpness"), 2.0, x=x0, y=y0 - 560),
                                       10.0, x=x0 + 180, y=y0 - 560), 1.0, x=x0 + 360, y=y0 - 560)
    grow = b.math("DIVIDE", 6.0, b.math("ADD", sharp_r, 11.0, x=x0 + 540, y=y0 - 560), x=x0 + 720, y=y0 - 560)
    half_w = b.math("MULTIPLY", b.g("Rail Width"), grow, x=x0 + 900, y=y0 - 560)
    half_h = b.math("MULTIPLY", b.g("Rail Height"), grow, x=x0 + 900, y=y0 - 720)
    # центр сечения: наружная сторона на Rail Offset, ширина внутрь
    mid = b.math("MULTIPLY_ADD", b.g("Rail Width"), -0.5, b.g("Rail Offset"), x=x0 + 900, y=y0 - 880)
    neg_bh = b.math("MULTIPLY", b.g("Basket Height"), -1.0, x=x0, y=y0 - 1040)
    z_top = b.math("SUBTRACT", b.math("MULTIPLY", b.g("Rail Height"), -0.5, x=x0, y=y0 - 1200), b.g("Rail Drop"),
                   x=x0 + 180, y=y0 - 1200)
    z_bot = b.math("MULTIPLY_ADD", b.g("Rail Height"), 0.5, neg_bh, x=x0 + 180, y=y0 - 1040)

    rails = b.node("GeometryNodeDuplicateElements", x0 + 1300, y0, domain="SPLINE")
    b.link(loop, rails.inputs["Geometry"])
    rails.inputs["Amount"].default_value = 2
    lower = rails.outputs["Duplicate Index"]          # 0 — верхняя, 1 — нижняя
    off = b.switch("BOOLEAN", lower, b.boolean("NOT", b.g("Top Rail"), x=x0 + 1300, y=y0 - 200),
                   b.boolean("NOT", b.g("Bottom Rail"), x=x0 + 1300, y=y0 - 360), x0 + 1480, y0 - 200)
    kept = b.node("GeometryNodeDeleteGeometry", x0 + 1660, y0, domain="CURVE")
    b.link(rails.outputs["Geometry"], kept.inputs["Geometry"])
    b.link(off, kept.inputs["Selection"])
    scaled = b.vmath("MULTIPLY", pos, b.combine(b.g("Bottom Scale"), b.g("Bottom Scale"), 1.0, x0 + 1300, y0 - 560),
                     x=x0 + 1480, y=y0 - 560)
    base = b.switch("VECTOR", lower, pos, scaled, x0 + 1660, y0 - 560)
    lift = b.combine(0.0, 0.0, b.switch("FLOAT", lower, z_top, z_bot, x0 + 1480, y0 - 1100), x0 + 1660, y0 - 1100)
    center = b.vmath("ADD", b.vmath("ADD", base, b.vmath("SCALE", offset, mid, x=x0 + 1660, y=y0 - 760),
                                    x=x0 + 1840, y=y0 - 640), lift, x=x0 + 2020, y=y0 - 640)
    # оси профиля: u — вверх, v — наружу (такой порядок даёт нормали наружу, проверено объёмом)
    geo = b.store(kept.outputs["Geometry"], "_gs_c", "FLOAT_VECTOR", center, x0 + 2220, y0)
    geo = b.store(geo, "_gs_u", "FLOAT_VECTOR", b.combine(0.0, 0.0, half_h, x0 + 2220, y0 - 760), x0 + 2420, y0)
    geo = b.store(geo, "_gs_v", "FLOAT_VECTOR", b.vmath("SCALE", offset, half_w, x=x0 + 2420, y=y0 - 760),
                  x0 + 2620, y0)
    # crease: x — рёбра кольца (острая вершина), y — продольные рёбра
    rail_geo = b.store(geo, "_gs_k", "FLOAT_VECTOR",
                       b.combine(sharp, b.g("Rail Sharpness"), 0.0, x0 + 2620, y0 - 760), x0 + 2820, y0)

    # --- крапана: ось, кадр ---
    b.section("Prong Axis")
    x0, y0 = 1500, -2600
    lone = b.cmp("EQUAL", b.node("GeometryNodeInputMeshVertexNeighbors", x0 - 200, y0 - 200).outputs["Vertex Count"],
                 0, x0, y0 - 200, dtype="INT")
    pick = b.boolean("AND", b.boolean("AND", lone, b.g("Prongs"), x=x0 + 180, y=y0 - 200), has_loop,
                     x=x0 + 360, y=y0 - 200)
    sites = b.node("GeometryNodeMeshToPoints", x0 + 540, y0, mode="VERTICES")
    b.link(b.g("Geometry"), sites.inputs["Mesh"])
    b.link(pick, sites.inputs["Selection"])
    ends = b.node("GeometryNodeDuplicateElements", x0 + 740, y0, domain="POINT")
    b.link(sites.outputs["Points"], ends.inputs["Geometry"])
    ends.inputs["Amount"].default_value = 3
    ring = ends.outputs["Duplicate Index"]            # 0 — основание, 1 — плечо, 2 — верхушка
    # нормаль контура: касательная ближайшей точки предела, повернутая наружу
    near = b.node("GeometryNodeSampleNearest", x0, y0 - 400, domain="POINT")
    b.link(limit.outputs["Points"], near.inputs["Geometry"])
    b.link(pos, near.inputs["Sample Position"])
    tangent = b.node("GeometryNodeSampleIndex", x0 + 180, y0 - 400, data_type="FLOAT_VECTOR", domain="POINT")
    b.link(limit.outputs["Points"], tangent.inputs["Geometry"])
    b.link(limit.outputs["Tangent"], tangent.inputs["Value"])
    b.link(near.outputs["Index"], tangent.inputs["Index"])
    normal = b.vmath("NORMALIZE", b.vmath("CROSS_PRODUCT", tangent.outputs["Value"], up, x=x0 + 360, y=y0 - 400),
                     x=x0 + 540, y=y0 - 400)
    p_g = b.vmath("MULTIPLY_ADD", normal, b.combine(b.g("Prong Offset"), b.g("Prong Offset"), 0.0, x0 + 540, y0 - 560),
                  pos, x=x0 + 720, y=y0 - 400)
    p_b = b.vmath("ADD", b.vmath("MULTIPLY", p_g, b.combine(b.g("Bottom Scale"), b.g("Bottom Scale"), 0.0,
                                                           x0 + 720, y0 - 720), x=x0 + 900, y=y0 - 640),
                  b.combine(0.0, 0.0, neg_bh, x0 + 900, y0 - 800), x=x0 + 1080, y=y0 - 640)
    axis = b.vmath("NORMALIZE", b.vmath("SUBTRACT", p_g, p_b, x=x0 + 1260, y=y0 - 500), x=x0 + 1440, y=y0 - 500)
    # кадр кольца: face — проекция n на плоскость кольца (сторона квадрата смотрит на камень),
    # side — вдоль контура
    side = b.vmath("NORMALIZE", b.vmath("CROSS_PRODUCT", normal, axis, x=x0 + 1620, y=y0 - 400),
                   x=x0 + 1800, y=y0 - 400)
    face = b.vmath("CROSS_PRODUCT", axis, side, x=x0 + 1980, y=y0 - 400)

    # --- длина и кольца: низ — сечение призмы плоскостью z = -Basket Height, верх на Prong Height ---
    b.section("Prong Length")
    x0, y0 = 3700, -2900
    cos_a = b.separate(axis, x0, y0)["Z"]
    sin_a = b.math("SQRT", b.math("MULTIPLY_ADD", cos_a, b.math("MULTIPLY", cos_a, -1.0, x=x0 + 180, y=y0 - 160),
                                  1.0, x=x0 + 360, y=y0 - 160), x=x0 + 540, y=y0 - 160)
    # полусторона основания: средний радиус ствола = Prong Diameter / 2
    h_bot = b.math("DIVIDE", b.g("Prong Diameter"), 2.0 * K_PRISM, x=x0, y=y0 - 400)
    # плечо: радиус ствола у плеча = Tip Scale * радиус основания; верхушка шире плеча в TIP_FLARE
    h_sh = b.math("MULTIPLY", h_bot, b.math("MAXIMUM", b.math("MULTIPLY_ADD", b.g("Tip Scale"), SHOULDER_A,
                                                                -SHOULDER_B, x=x0, y=y0 - 560),
                                            0.02, x=x0 + 180, y=y0 - 560), x=x0 + 360, y=y0 - 480)
    h_tip = b.math("MULTIPLY", h_sh, TIP_FLARE, x=x0 + 540, y=y0 - 480)
    # длина купола: шаг плечо — верхушка, линейно по Tip Round
    delta = b.math("MULTIPLY", h_sh, b.math("MULTIPLY_ADD", b.g("Tip Round"), DOME_MAX - DOME_MIN, DOME_MIN,
                                            x=x0 + 360, y=y0 - 720), x=x0 + 540, y=y0 - 640)
    # верх купола: вершина на плечо + DOME_APEX * delta по оси; при наклоне самая верхняя точка
    # выше на sqrt((RHO h sin)^2 + (ETA delta cos)^2) - ETA delta cos
    lift = b.vmath("LENGTH", b.combine(b.math("MULTIPLY", b.math("MULTIPLY", h_sh, sin_a, x=x0 + 720, y=y0 - 480),
                                              DOME_RHO, x=x0 + 900, y=y0 - 480),
                                       b.math("MULTIPLY", b.math("MULTIPLY", delta, cos_a, x=x0 + 720, y=y0 - 640),
                                              DOME_ETA, x=x0 + 900, y=y0 - 640), 0.0, x0 + 1080, y0 - 560),
                   x=x0 + 1260, y=y0 - 560)
    # (Prong Height + Basket Height - lift) / cos - (DOME_APEX - ETA) delta
    tau_sh = b.math("MULTIPLY_ADD", delta, DOME_ETA - DOME_APEX,
                    b.math("DIVIDE", b.math("SUBTRACT", b.math("ADD", b.g("Prong Height"), b.g("Basket Height"),
                                                               x=x0 + 1260, y=y0 - 400), lift,
                                            x=x0 + 1440, y=y0 - 400), cos_a, x=x0 + 1620, y=y0 - 400),
                    x=x0 + 1800, y=y0 - 400)
    tau_tip = b.math("ADD", tau_sh, delta, x=x0 + 1980, y=y0 - 400)

    # --- кольца крапанов: три точки по оси, кривая на каждый крапан ---
    b.section("Prong Rings")
    x0, y0 = 6400, -2600

    def by_ring(values, x, y):
        n = b.node("GeometryNodeIndexSwitch", x, y, data_type="FLOAT")
        while len(n.index_switch_items) < len(values):
            n.index_switch_items.new()
        b.link(ring, n.inputs["Index"])
        for i, v in enumerate(values):
            b.put(n.inputs[i + 1], v)
        return n.outputs[0]

    at = by_ring((0.0, tau_sh, tau_tip), x0, y0 - 300)
    h = by_ring((h_bot, h_sh, h_tip), x0, y0 - 500)
    base = b.cmp("EQUAL", ring, 0, x0, y0 - 700, dtype="INT")

    def flat(v, y):
        """Основание: ось кольца, сдвинутая вдоль оси крапана на плоскость z = const."""
        shifted = b.vmath("SUBTRACT", v, b.vmath("SCALE", axis, b.math("DIVIDE", b.separate(v, x0, y)["Z"], cos_a,
                                                                         x=x0 + 180, y=y), x=x0 + 360, y=y),
                          x=x0 + 540, y=y)
        return b.vmath("SCALE", b.switch("VECTOR", base, v, shifted, x0 + 720, y), h, x=x0 + 900, y=y)

    center = b.vmath("MULTIPLY_ADD", axis, b.combine(at, at, at, x0 + 180, y0 - 300), p_b, x=x0 + 360, y=y0 - 300)
    # оси профиля: u — вдоль контура, v — к камню (той же ориентации, что у реек)
    geo = b.store(ends.outputs["Geometry"], "_gs_c", "FLOAT_VECTOR", center, x0 + 1100, y0)
    geo = b.store(geo, "_gs_u", "FLOAT_VECTOR", flat(side, y0 - 900), x0 + 1300, y0)
    geo = b.store(geo, "_gs_v", "FLOAT_VECTOR", flat(face, y0 - 1100), x0 + 1500, y0)
    # crease: рёбра кольца основания — 1 (плоский торец), остальное гладкое
    geo = b.store(geo, "_gs_k", "FLOAT_VECTOR", b.combine(base, 0.0, 0.0, x0 + 1500, y0 - 700), x0 + 1700, y0)
    curves = b.node("GeometryNodePointsToCurves", x0 + 1900, y0)
    b.link(geo, curves.inputs["Points"])
    site_id = b.node("FunctionNodeIntegerMath", x0 + 1700, y0 - 300, operation="DIVIDE_FLOOR")
    b.link(b.node("GeometryNodeInputIndex", x0 + 1500, y0 - 300).outputs[0], site_id.inputs[0])
    site_id.inputs[1].default_value = 3
    b.link(site_id.outputs[0], curves.inputs["Curve Group ID"])
    b.link(ring, curves.inputs["Weight"])

    # --- клетка: петли x квадратный профиль, позиции по кольцам ---
    b.section("Cage")
    x0, y0 = 8800, -900
    join = b.node("GeometryNodeJoinGeometry", x0, y0)
    b.link(curves.outputs["Curves"], join.inputs["Geometry"])
    b.link(rail_geo, join.inputs["Geometry"])
    quad = b.node("GeometryNodeCurvePrimitiveQuadrilateral", x0, y0 - 300, mode="RECTANGLE")
    quad.inputs["Width"].default_value = 2.0
    quad.inputs["Height"].default_value = 2.0
    profile = b.store(quad.outputs["Curve"], "_gs_ab", "FLOAT_VECTOR", pos, x0 + 200, y0 - 300)
    tube = b.node("GeometryNodeCurveToMesh", x0 + 400, y0)
    b.link(join.outputs["Geometry"], tube.inputs["Curve"])
    b.link(profile, tube.inputs["Profile Curve"])
    tube.inputs["Fill Caps"].default_value = True
    ab = b.named("_gs_ab", "FLOAT_VECTOR", x0 + 400, y0 - 300)
    abs_ = b.separate(ab, x0 + 580, y0 - 300)
    around = b.vmath("ADD", b.vmath("SCALE", b.named("_gs_u", "FLOAT_VECTOR", x0 + 580, y0 - 460), abs_["X"],
                                    x=x0 + 760, y=y0 - 400),
                     b.vmath("SCALE", b.named("_gs_v", "FLOAT_VECTOR", x0 + 580, y0 - 620), abs_["Y"],
                             x=x0 + 760, y=y0 - 560), x=x0 + 940, y=y0 - 460)
    place = b.node("GeometryNodeSetPosition", x0 + 1120, y0)
    b.link(tube.outputs["Mesh"], place.inputs["Geometry"])
    b.link(b.vmath("ADD", b.named("_gs_c", "FLOAT_VECTOR", x0 + 940, y0 - 300), around, x=x0 + 1120, y=y0 - 300),
           place.inputs["Position"])
    # ребро: у продольного обе вершины в одном углу профиля — среднее ab по ребру длины sqrt(2)
    along = b.cmp("GREATER_THAN", b.vmath("DOT_PRODUCT", ab, ab, x=x0 + 1120, y=y0 - 700), 1.5, x0 + 1300, y0 - 700)
    kk = b.separate(b.named("_gs_k", "FLOAT_VECTOR", x0 + 1120, y0 - 860), x0 + 1300, y0 - 860)
    crease = b.switch("FLOAT", along, kk["X"], kk["Y"], x0 + 1480, y0 - 700)
    geo = b.store(place.outputs["Geometry"], "crease_edge", "FLOAT", crease, x0 + 1480, y0, domain="EDGE")
    # гладко, острые только рёбра с crease 1 (Curve to Mesh метит острыми края торцов)
    shade = b.node("GeometryNodeSetShadeSmooth", x0 + 1680, y0, domain="FACE")
    b.link(geo, shade.inputs["Mesh"])
    edges = b.node("GeometryNodeSetShadeSmooth", x0 + 1880, y0, domain="EDGE")
    b.link(shade.outputs["Mesh"], edges.inputs["Mesh"])
    b.link(b.cmp("LESS_THAN", crease, 0.999, x0 + 1680, y0 - 700), edges.inputs["Shade Smooth"])
    mat = b.node("GeometryNodeSetMaterial", x0 + 2080, y0)
    b.link(edges.outputs["Mesh"], mat.inputs["Geometry"])
    b.link(b.g("Metal Material"), mat.inputs["Material"])
    clean = b.node("GeometryNodeRemoveAttribute", x0 + 2280, y0)
    clean.inputs["Pattern Mode"].default_value = "Wildcard"
    clean.inputs["Name"].default_value = "_gs_*"
    b.link(mat.outputs["Geometry"], clean.inputs["Geometry"])
    b.frame = None
    gout = b.node("NodeGroupOutput", x0 + 2500, y0)
    b.link(clean.outputs["Geometry"], gout.inputs["Geometry"])

    print("Node group '%s' rebuilt: %d nodes" % (GROUP_NAME, len(ng.nodes)))
    return ng


def limit_sites(loop, count: int, phase: float = 0.0) -> list[tuple[float, float]]:
    """count точек равномерно по длине предела петли, первая — на phase шага от узла первой точки."""
    curve = gem_outline.limit_curve(loop, LIMIT_RES)
    points = [(x, y) for x, y, *_ in curve]
    lengths = [0.0]
    for a, c in zip(points, points[1:] + points[:1]):
        lengths.append(lengths[-1] + hypot(c[0] - a[0], c[1] - a[1]))
    total = lengths[-1]
    out = []
    j = 0
    for k in range(count):
        s = ((k + phase) / count % 1.0) * total
        j = max(i for i in range(len(points)) if lengths[i] <= s)
        a, c = points[j], points[(j + 1) % len(points)]
        f = (s - lengths[j]) / ((lengths[j + 1] - lengths[j]) or 1.0)
        out.append((a[0] + (c[0] - a[0]) * f, a[1] + (c[1] - a[1]) * f))
    return out


def _inputs(ng):
    return {it.name: it.identifier for it in ng.interface.items_tree
            if it.item_type == "SOCKET" and it.in_out == "INPUT"}


def setup(gem, count: int = 4, phase: float = 0.0):
    """Объект-каст для камня: ребёнок камня в его коллекции, базовый меш — петля рундиста
    + count мест крапанов. Повторный вызов переписывает базовый меш, значения входов
    модификатора не трогает."""
    ng = build_group()
    name = f"{gem.name} Setting"
    obj = bpy.data.objects.get(name)
    if obj is None:
        obj = bpy.data.objects.new(name, bpy.data.meshes.new(name))
        (gem.users_collection[0] if gem.users_collection else bpy.context.scene.collection).objects.link(obj)
    obj.parent = gem
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.matrix_basis = Matrix.Identity(4)

    loop = gem_outline.gem_loop(gem)
    sites = limit_sites(loop, count, phase)
    n = len(loop)
    mesh = obj.data
    mesh.clear_geometry()
    mesh.from_pydata([(x, y, 0.0) for x, y, _ in loop] + [(x, y, 0.0) for x, y in sites],
                     [(i, (i + 1) % n) for i in range(n)], [])
    corner = mesh.attributes.get("corner") or mesh.attributes.new("corner", "FLOAT", "POINT")
    corner.data.foreach_set("value", [1.0 if c else 0.0 for *_, c in loop] + [0.0] * len(sites))
    mesh.update()

    md = next((m for m in obj.modifiers if m.type == "NODES" and m.node_group == ng), None)
    if md is None:
        md = obj.modifiers.new(GROUP_NAME, "NODES")
        md.node_group = ng
        zs = [v.co.z for v in gem.data.vertices]
        ids = _inputs(ng)
        getattr(md.properties.inputs, ids["Prong Height"]).value = PRONG_HEIGHT_K * max(zs)
        getattr(md.properties.inputs, ids["Basket Height"]).value = -BASKET_HEIGHT_K * min(zs)
    if not any(m.type == "SUBSURF" for m in obj.modifiers):
        sub = obj.modifiers.new(SUBD_NAME, "SUBSURF")
        sub.levels = 2
        sub.render_levels = 3
        sub.quality = 3
        sub.use_creases = True
        sub.use_limit_surface = True
    obj.update_tag()
    print("Setting '%s': %d loop points, %d prongs" % (obj.name, n, len(sites)))
    return obj
