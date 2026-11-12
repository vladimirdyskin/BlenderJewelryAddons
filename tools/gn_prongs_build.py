"""
My_Prongs — крапана между камнями. Второй модификатор после My_Gems_Curve.

На вход приходят инстансы камней с атрибутами gem_order, gem_up, gem_along, gem_r
(см. tools/gn_gems_curve_build.py). На выход — те же камни плюс инстансы крапанов.

Stones (объект): камни берутся с этого объекта (кривая с My_Gems_Curve) через Object Info,
модификатор можно повесить на отдельный объект. Расчёт в координатах Stones (gem_up — вектор
в его пространстве), в конце Transform Geometry матрицей Transform у Object Info Relative.
Show Stones пропускает только свою геометрию из стека — камни Stones не копируются.
Пусто или на объекте нет инстансов — камни из стека, как раньше.

Схема:
    Instances to Points -> Sort Elements по gem_order: точки идут по порядку вдоль ряда.
    Evaluate at Index: для каждого камня следующий и предыдущий (по кругу).
    Камни соединены, если зазор между ними не больше Max Gap. Так один граф работает на
    замкнутом ряду и на открытом: пара через разрыв просто не соединяется.
    Каждый камень даёт две заготовки, вперёд и назад (Duplicate Elements):
        вперёд — зазор со следующим, либо конец ряда при Prong at End;
        назад  — только начало ряда при Prong at Start (остальные зазоры уже посчитал сосед).
    Поэтому каждый зазор считается один раз и дублей на оси нет.
    Начало и конец — по исходной кривой: у зеркальной копии (gem_mirror < 0) ход обратный,
    и крапана на концах ставятся симметрично обеим половинам.

Место в зазоре: P + dir * (r + gap / 2), учитывает разный размер соседних камней.
Конец ряда: P + dir * (r + Start/End Offset), dir — ось X камня наружу от соседа.
Хорда к соседу не годится: на изгибе крайний камень к ней наклонён, и крапан ушёл бы с его плоскости.
Up — среднее осей Z двух камней, T — ход вдоль ряда, Across = Up x T.

Внутрь и наружу: Across у всех зазоров смотрит в одну сторону относительно хода по ряду.
Какая это сторона, решает знак среднего dot(Across, Site - центр камней): наружу — туда,
где знак положительный. Направление рисования кривой на результат не влияет.

Крапан: Site + side * Offset + Up * Z Offset, side = +-Across.
Prong Tilt: Z = Up * cos - side * sin, плюс — верхушки к камням, минус — наружу, вокруг origin
крапана.

Оси крапана одинаковы относительно своего камня (зеркальная расстановка): +Y — side, от линии
ряда к крапану (по стороне Inner/Outer, а не по положению — отрицательный Offset не переворачивает),
+X — вдоль ряда от своего камня (общий крапан при Along Offset = 0 — по ходу ряда).
Где Z x X смотрит против side, Scale Y = -1: несимметричный крапан отражается, как копии камней.
Inner/Outer Offset и Scale XY — своей стороны.

Чтобы убрать одну сторону, поставьте ей Scale XY = 0.

Scale by Stone: размеры крапана заданы для камня размером 1 и умножаются на размер камня
(атрибут gem_size от My_Gems_Curve; нет атрибута — 1): Scale XY, Scale Z, Inner/Outer Offset,
Z Offset. В зазоре — среднее двух соседних камней, на конце ряда — крайний камень.
Max Gap и Start/End Offset — зазоры от края камня, не масштабируются.

Along Offset (не 0): крапан в зазоре делится на два, сдвиг вдоль ряда (T) на -+Along Offset
от середины зазора — каждому камню свой, по четыре крапана на камень. На конце ряда пара одна.
С Scale by Stone разделённый крапан (и его Along Offset) — по своему камню, общий — по среднему.
Inner/Outer Offset (вбок) у обоих — по среднему двух камней: крапана зазора стоят в одну линию.

Realize: всё, что вышло из группы (камни и крапана), становится мешем, отражённым камням
переворачиваются грани.

Интерфейс: сокеты только добавляются, если их нет — повторный запуск скрипта
не сбрасывает значения на модификаторах. Узлы пересобираются целиком.
"""

import bpy

GROUP_NAME = "My_Prongs"

ATTR_ORDER = "gem_order"
ATTR_UP = "gem_up"
ATTR_ALONG = "gem_along"
ATTR_R = "gem_r"
ATTR_MIRROR = "gem_mirror"
ATTR_SIZE = "gem_size"

# (имя, тип, default, min, max, панель, subtype)
SOCKETS = [
    ("Prongs", "NodeSocketObject", None, None, None, None, None),
    ("Stones", "NodeSocketObject", None, None, None, None, None),
    ("Metal Material", "NodeSocketMaterial", None, None, None, None, None),
    ("Show Stones", "NodeSocketBool", True, None, None, None, None),
    ("Realize", "NodeSocketBool", False, None, None, None, None),
    ("Inner Offset", "NodeSocketFloat", 0.4, None, None, "Inner", None),
    ("Inner Scale XY", "NodeSocketFloat", 1.0, 0.0, None, "Inner", None),
    ("Outer Offset", "NodeSocketFloat", 0.4, None, None, "Outer", None),
    ("Outer Scale XY", "NodeSocketFloat", 1.0, 0.0, None, "Outer", None),
    ("Scale Z", "NodeSocketFloat", 1.0, 0.0, None, "Prong", None),
    ("Z Offset", "NodeSocketFloat", 0.0, None, None, "Prong", None),
    ("Prong Tilt", "NodeSocketFloat", 0.0, None, None, "Prong", "ANGLE"),
    ("Scale by Stone", "NodeSocketBool", False, None, None, "Prong", None),
    ("Along Offset", "NodeSocketFloat", 0.0, None, None, "Prong", None),
    ("Max Gap", "NodeSocketFloat", 1.0, 0.0, None, "Row", None),
    ("Prong at Start", "NodeSocketBool", False, None, None, "Row", None),
    ("Start Offset", "NodeSocketFloat", 0.05, None, None, "Row", None),
    ("Prong at End", "NodeSocketBool", False, None, None, "Row", None),
    ("End Offset", "NodeSocketFloat", 0.05, None, None, "Row", None),
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
        return n

    def at_index(self, value, index, dtype, x, y):
        n = self.node("GeometryNodeFieldAtIndex", x, y, data_type=dtype, domain="POINT")
        self.link(value, self.enabled(n, "Value"))
        self.link(index, n.inputs["Index"])
        return self.enabled_out(n, "Value")

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

    def stat(self, geo, value, dtype, x, y):
        n = self.node("GeometryNodeAttributeStatistic", x, y, data_type=dtype, domain="POINT")
        self.link(geo, n.inputs["Geometry"])
        self.link(value, self.enabled(n, "Attribute"))
        return self.enabled_out(n, "Mean")

    def capture(self, geo, items, x, y):
        """Capture Attribute на несколько значений: {имя: (тип, значение)} -> {имя: выход}, Geometry."""
        n = self.node("GeometryNodeCaptureAttribute", x, y, domain="POINT")
        for name, (stype, _value) in items.items():
            n.capture_items.new(stype, name)
        self.link(geo, n.inputs["Geometry"])
        for name, (_stype, value) in items.items():
            self.link(value, n.inputs[name])
        return n


def build_group():
    ng = bpy.data.node_groups.get(GROUP_NAME)
    if ng is None:
        ng = bpy.data.node_groups.new(GROUP_NAME, "GeometryNodeTree")
    ensure_interface(ng)
    ng.nodes.clear()

    b = B(ng, -300)

    # --- камни по порядку вдоль ряда ---
    b.section("Stones in Order")
    order = b.named(ATTR_ORDER, "FLOAT", 0, -60)
    to_pts = b.node("GeometryNodeInstancesToPoints", 200, 200)
    # камни: с объекта Stones (если на нём есть инстансы) или из стека
    src = b.node("GeometryNodeObjectInfo", -200, 520, transform_space="ORIGINAL")
    b.link(b.g("Stones"), src.inputs["Object"])
    src_n = b.node("GeometryNodeAttributeDomainSize", 0, 520, component="INSTANCES")
    b.link(src.outputs["Geometry"], src_n.inputs["Geometry"])
    use_obj = b.cmp("GREATER_THAN", src_n.outputs["Instance Count"], 0.0, 200, 520)
    source = b.switch("GEOMETRY", use_obj, b.g("Geometry"), src.outputs["Geometry"], 0, 360)
    b.link(source, to_pts.inputs["Instances"])
    # только камни: у крапанов, пришедших вместе с камнями, gem_* после Join = 0
    is_stone = b.cmp("GREATER_THAN", b.named(ATTR_R, "FLOAT", 0, -220).outputs["Attribute"], 0.0, 200, -220)
    b.link(b.boolean("AND", order.outputs["Exists"], is_stone, 200, -60), to_pts.inputs["Selection"])
    sort = b.node("GeometryNodeSortElements", 400, 200, domain="POINT")
    b.link(to_pts.outputs["Points"], sort.inputs["Geometry"])
    b.link(order.outputs["Attribute"], sort.inputs["Sort Weight"])
    stones = sort.outputs["Geometry"]

    # --- соседи: следующий и предыдущий по кругу ---
    b.section("Neighbours")
    size = b.node("GeometryNodeAttributeDomainSize", 640, 200, component="POINTCLOUD")
    b.link(stones, size.inputs["Geometry"])
    count = size.outputs["Point Count"]
    idx = b.node("GeometryNodeInputIndex", 640, -60).outputs[0]
    next_i = b.math("FLOORED_MODULO", b.math("ADD", idx, 1.0, 840, 200), count, 1020, 200)
    prev_i = b.math("FLOORED_MODULO", b.math("SUBTRACT", idx, 1.0, 840, 20), count, 1020, 20)

    pos = b.node("GeometryNodeInputPosition", 1020, -160).outputs[0]
    up = b.named(ATTR_UP, "FLOAT_VECTOR", 1020, -280).outputs["Attribute"]
    rad = b.named(ATTR_R, "FLOAT", 1020, -440).outputs["Attribute"]

    next_p = b.at_index(pos, next_i, "FLOAT_VECTOR", 1240, 200)
    next_u = b.at_index(up, next_i, "FLOAT_VECTOR", 1240, 40)
    # размер камня: нет атрибута (старая группа камней) — 1
    size_attr = b.named(ATTR_SIZE, "FLOAT", 1020, -1240)
    size = b.switch("FLOAT", size_attr.outputs["Exists"], 1.0, size_attr.outputs["Attribute"], 1240, -1240)
    next_s = b.at_index(size, next_i, "FLOAT", 1460, -1240)
    prev_s = b.at_index(size, prev_i, "FLOAT", 1460, -1400)
    next_r = b.at_index(rad, next_i, "FLOAT", 1240, -120)
    prev_p = b.at_index(pos, prev_i, "FLOAT_VECTOR", 1240, -280)
    prev_u = b.at_index(up, prev_i, "FLOAT_VECTOR", 1240, -440)
    prev_r = b.at_index(rad, prev_i, "FLOAT", 1240, -600)

    # два камня: пара через конец ряда — это тот же зазор, его не считать второй раз
    many = b.cmp("GREATER_THAN", count, 2.0, 1240, -780)
    not_last = b.cmp("LESS_THAN", idx, b.math("SUBTRACT", count, 1.0, 1060, -920), 1240, -920)
    not_first = b.cmp("GREATER_THAN", idx, 0.0, 1240, -1060)

    def linked(other_p, other_r, inner_ok, y):
        gap = b.math("SUBTRACT", b.vmath("DISTANCE", pos, other_p, 1460, y), rad, 1640, y)
        gap = b.math("SUBTRACT", gap, other_r, 1820, y)
        close = b.cmp("LESS_EQUAL", gap, b.g("Max Gap"), 2000, y)
        return b.boolean("AND", close, b.boolean("OR", inner_ok, many, 2000, y - 180), 2180, y)

    next_ok = linked(next_p, next_r, not_last, 200)
    prev_ok = linked(prev_p, prev_r, not_first, -240)

    cap = b.capture(stones, {
        "Next P": ("VECTOR", next_p), "Next Up": ("VECTOR", next_u), "Next R": ("FLOAT", next_r),
        "Next OK": ("BOOLEAN", next_ok),
        "Prev P": ("VECTOR", prev_p), "Prev Up": ("VECTOR", prev_u), "Prev R": ("FLOAT", prev_r),
        "Prev OK": ("BOOLEAN", prev_ok),
        "Next S": ("FLOAT", next_s), "Prev S": ("FLOAT", prev_s),
    }, 2420, 200)

    # --- заготовки вперёд и назад ---
    b.section("Sites")
    dup = b.node("GeometryNodeDuplicateElements", 2700, 200, domain="POINT")
    b.link(cap.outputs["Geometry"], dup.inputs["Geometry"])
    dup.inputs["Amount"].default_value = 2
    back = b.cmp("GREATER_THAN", dup.outputs["Duplicate Index"], 0.5, 2700, -60)

    nb_p = b.switch("VECTOR", back, cap.outputs["Next P"], cap.outputs["Prev P"], 2920, 200)
    ot_p = b.switch("VECTOR", back, cap.outputs["Prev P"], cap.outputs["Next P"], 2920, 20)
    nb_u = b.switch("VECTOR", back, cap.outputs["Next Up"], cap.outputs["Prev Up"], 2920, -160)
    nb_r = b.switch("FLOAT", back, cap.outputs["Next R"], cap.outputs["Prev R"], 2920, -340)
    ok = b.switch("BOOLEAN", back, cap.outputs["Next OK"], cap.outputs["Prev OK"], 2920, -520)

    # конец ряда в понятиях исходной кривой: у зеркальной копии вперёд и назад меняются местами
    mirrored = b.cmp("LESS_THAN", b.named(ATTR_MIRROR, "FLOAT", 2700, -240).outputs["Attribute"], 0.0, 2920, -700)
    at_start = b.boolean("XOR", back, mirrored, 2920, -880)
    cap_on = b.switch("BOOLEAN", at_start, b.g("Prong at End"), b.g("Prong at Start"), 3140, -880)
    keep = b.switch("BOOLEAN", back,
                    b.boolean("OR", ok, cap_on, 3140, -520),
                    b.boolean("AND", b.boolean("NOT", ok, None, 3140, -700), cap_on, 3320, -700),
                    3500, -520)
    cut = b.node("GeometryNodeDeleteGeometry", 3700, 200, domain="POINT")
    b.link(dup.outputs["Geometry"], cut.inputs["Geometry"])
    b.link(b.boolean("NOT", keep, None, 3700, -520), cut.inputs["Selection"])

    # направление от камня: к соседу или, на конце ряда, ось X камня наружу от соседа
    to_nb = b.vmath("NORMALIZE", b.vmath("SUBTRACT", nb_p, pos, 3140, 200), None, 3320, 200)
    stone_x = b.named(ATTR_ALONG, "FLOAT_VECTOR", 2920, 400).outputs["Attribute"]
    outside = b.vmath("DOT_PRODUCT", stone_x, b.vmath("SUBTRACT", pos, ot_p, 3140, 20), 3320, 20)
    away = b.vmath("SCALE", stone_x, b.math("SIGN", outside, None, 3500, 20), 3680, 20)
    dirv = b.switch("VECTOR", ok, away, to_nb, 3500, 200)

    gap = b.math("SUBTRACT", b.vmath("DISTANCE", nb_p, pos, 3140, -160), rad, 3320, -160)
    half = b.math("MULTIPLY", b.math("SUBTRACT", gap, nb_r, 3500, -160), 0.5, 3680, -160)
    cap_off = b.switch("FLOAT", at_start, b.g("End Offset"), b.g("Start Offset"), 3500, -340)
    along = b.math("ADD", rad, b.switch("FLOAT", ok, cap_off, half, 3860, -160), 4040, -160)
    site = b.vmath("ADD", pos, b.vmath("SCALE", dirv, along, 4220, -160), 4400, -160)

    both = b.vmath("NORMALIZE", b.vmath("ADD", up, nb_u, 4040, -340), None, 4220, -340)
    site_up = b.switch("VECTOR", ok, up, both, 4400, -340)
    # размеры камней по ходу T: сзади — этот камень, спереди — сосед (на конце ряда — тот же)
    nb_s = b.switch("FLOAT", back, cap.outputs["Next S"], cap.outputs["Prev S"], 4040, -1240)
    front_s = b.switch("FLOAT", ok, size, nb_s, 4220, -1240)
    travel = b.switch("VECTOR", back, dirv, b.vmath("SCALE", dirv, -1.0, 4220, -520), 4400, -520)
    across = b.vmath("NORMALIZE", b.vmath("CROSS_PRODUCT", site_up, travel, 4580, -520), None, 4760, -520)

    sites = b.capture(cut.outputs["Geometry"], {
        "Site": ("VECTOR", site), "Up": ("VECTOR", site_up), "T": ("VECTOR", travel), "Across": ("VECTOR", across),
        "Pair": ("BOOLEAN", ok), "S Back": ("FLOAT", size), "S Front": ("FLOAT", front_s),
        # X крапана от своего камня: у начала ряда (назад) T смотрит на камень
        "X Sign": ("FLOAT", b.switch("FLOAT", back, 1.0, -1.0, 4580, -1400)),
    }, 4960, 200)

    # --- какая сторона наружу ---
    b.section("Outward Side")
    center = b.stat(stones, pos, "FLOAT_VECTOR", 5240, 200)
    from_c = b.vmath("SUBTRACT", sites.outputs["Site"], center, 5440, 200)
    probe = b.vmath("DOT_PRODUCT", sites.outputs["Across"], from_c, 5620, 200)
    mean = b.stat(sites.outputs["Geometry"], probe, "FLOAT", 5800, 200)
    outward = b.switch("FLOAT", b.cmp("GREATER_EQUAL", mean, 0.0, 6000, 200), -1.0, 1.0, 6180, 200)

    # --- Along Offset: крапан в зазоре делится на два, каждому камню свой ---
    b.section("Along Split")
    s_back, s_front = sites.outputs["S Back"], sites.outputs["S Front"]
    split = b.boolean("AND", sites.outputs["Pair"],
                      b.cmp("NOT_EQUAL", b.g("Along Offset"), 0.0, 6200, -640), 6380, -640)
    dup_a = b.node("GeometryNodeDuplicateElements", 6440, 200, domain="POINT")
    b.link(sites.outputs["Geometry"], dup_a.inputs["Geometry"])
    b.link(b.switch("INT", split, 1, 2, 6440, -640), dup_a.inputs["Amount"])
    front = b.cmp("GREATER_THAN", dup_a.outputs["Duplicate Index"], 0.5, 6620, -460)
    shift = b.switch("FLOAT", split, 0.0, b.switch("FLOAT", front, -1.0, 1.0, 6800, -460), 6980, -460)
    # Scale by Stone: разделённый — по своему камню, общий — среднее двух
    own_s = b.switch("FLOAT", front, s_back, s_front, 6800, -820)
    mean_s = b.math("MULTIPLY", b.math("ADD", s_back, s_front, 6800, -1000), 0.5, 6980, -1000)
    k = b.switch("FLOAT", b.g("Scale by Stone"), 1.0,
                 b.switch("FLOAT", split, mean_s, own_s, 7160, -820), 7340, -820)
    step = b.math("MULTIPLY", b.math("MULTIPLY", shift, b.g("Along Offset"), 7160, -460), k, 7340, -460)
    site = b.vmath("ADD", sites.outputs["Site"], b.vmath("SCALE", sites.outputs["T"], step, 7520, -460), 7700, -460)
    # отступ вбок — по среднему двух камней: крапана зазора стоят в одну линию
    k_side = b.switch("FLOAT", b.g("Scale by Stone"), 1.0, mean_s, 7340, -1000)
    along_cap = b.capture(dup_a.outputs["Geometry"], {
        "Site": ("VECTOR", site), "K": ("FLOAT", k), "K Side": ("FLOAT", k_side),
        # разделённый передний крапан: свой камень впереди, X назад
        "X Sign": ("FLOAT", b.math("MULTIPLY", sites.outputs["X Sign"],
                                   b.switch("FLOAT", b.boolean("AND", split, front, 7340, -1180), 1.0, -1.0,
                                            7520, -1180), 7700, -1180)),
    }, 7900, 200)

    # --- крапана: внутрь и наружу ---
    b.section("Prongs")
    dup2 = b.node("GeometryNodeDuplicateElements", 8140, 200, domain="POINT")
    b.link(along_cap.outputs["Geometry"], dup2.inputs["Geometry"])
    dup2.inputs["Amount"].default_value = 2
    inner = b.cmp("GREATER_THAN", dup2.outputs["Duplicate Index"], 0.5, 6440, -60)
    k = along_cap.outputs["K"]
    offset = b.math("MULTIPLY", b.switch("FLOAT", inner, b.g("Outer Offset"), b.g("Inner Offset"), 6660, -60),
                    along_cap.outputs["K Side"], 6840, -60)
    scale_xy = b.math("MULTIPLY", b.switch("FLOAT", inner, b.g("Outer Scale XY"), b.g("Inner Scale XY"), 6660, -240),
                      k, 6840, -240)
    sign = b.switch("FLOAT", inner, outward, b.math("MULTIPLY", outward, -1.0, 6660, -420), 6840, -420)
    side = b.vmath("SCALE", sites.outputs["Across"], sign, 7020, -420)

    moved = b.vmath("ADD", along_cap.outputs["Site"], b.vmath("SCALE", side, offset, 7020, -60), 7200, -60)
    lifted = b.vmath("ADD", moved, b.vmath("SCALE", sites.outputs["Up"],
                                           b.math("MULTIPLY", b.g("Z Offset"), k, 7020, -240), 7200, -240), 7380, -60)
    place = b.node("GeometryNodeSetPosition", 7580, 200)
    b.link(dup2.outputs["Geometry"], place.inputs["Geometry"])
    b.link(lifted, place.inputs["Position"])

    # наклон вокруг origin крапана: плюс — верхушка к середине ряда
    cos_t = b.math("COSINE", b.g("Prong Tilt"), None, 7200, -420)
    sin_t = b.math("SINE", b.g("Prong Tilt"), None, 7200, -600)
    up_part = b.vmath("SCALE", sites.outputs["Up"], cos_t, 7380, -420)
    side_part = b.vmath("SCALE", side, sin_t, 7380, -600)
    lean = b.vmath("SUBTRACT", up_part, side_part, 7560, -420)

    # X — от своего камня вдоль ряда, Y — side; где Z x X против side, отражение по Y
    axis_x = b.vmath("SCALE", sites.outputs["T"], along_cap.outputs["X Sign"], 7560, -820)
    rot = b.node("FunctionNodeAxesToRotation", 7740, -420, primary_axis="Z", secondary_axis="X")
    b.link(lean, rot.inputs["Primary Axis"])
    b.link(axis_x, rot.inputs["Secondary Axis"])
    y_dot = b.vmath("DOT_PRODUCT", b.vmath("CROSS_PRODUCT", lean, axis_x, 7740, -820), side, 7920, -820)
    y_sign = b.switch("FLOAT", b.cmp("GREATER_EQUAL", y_dot, 0.0, 8100, -820), -1.0, 1.0, 8280, -820)
    scale = b.node("ShaderNodeCombineXYZ", 7740, -640)
    b.link(scale_xy, scale.inputs["X"])
    b.link(b.math("MULTIPLY", scale_xy, y_sign, 7560, -1000), scale.inputs["Y"])
    b.link(b.math("MULTIPLY", b.g("Scale Z"), k, 7560, -640), scale.inputs["Z"])

    # один меш на все крапана: материал на меш, инстансы ссылаются на него
    info = b.node("GeometryNodeObjectInfo", 7200, -820, transform_space="ORIGINAL")
    info.inputs["As Instance"].default_value = False
    b.link(b.g("Prongs"), info.inputs["Object"])
    mat = b.node("GeometryNodeSetMaterial", 7400, -820)
    b.link(info.outputs["Geometry"], mat.inputs["Geometry"])
    b.link(b.g("Metal Material"), mat.inputs["Material"])

    iop = b.node("GeometryNodeInstanceOnPoints", 7980, 200)
    b.link(place.outputs["Geometry"], iop.inputs["Points"])
    b.link(mat.outputs["Geometry"], iop.inputs["Instance"])
    b.link(rot.outputs["Rotation"], iop.inputs["Rotation"])
    b.link(scale.outputs["Vector"], iop.inputs["Scale"])
    # атрибуты камней остались на точках и перешли на крапана: иначе их примут за камни
    rm = b.node("GeometryNodeRemoveAttribute", 8200, 200)
    rm.inputs["Pattern Mode"].default_value = "Wildcard"
    rm.inputs["Name"].default_value = "gem_*"
    b.link(iop.outputs["Instances"], rm.inputs["Geometry"])
    # камни с объекта Stones: из его координат в координаты своего объекта
    rel = b.node("GeometryNodeObjectInfo", 8200, -200, transform_space="RELATIVE")
    b.link(b.g("Stones"), rel.inputs["Object"])
    tf = b.node("GeometryNodeTransform", 8420, -60)
    tf.inputs["Mode"].default_value = "Matrix"
    b.link(rm.outputs["Geometry"], tf.inputs["Geometry"])
    b.link(rel.outputs["Transform"], tf.inputs["Transform"])
    prongs = b.switch("GEOMETRY", use_obj, rm.outputs["Geometry"], tf.outputs["Geometry"], 8640, -60)

    # --- выход: своя геометрия из стека + крапана ---
    b.frame = None
    empty = b.node("GeometryNodeSwitch", 8200, 420, input_type="GEOMETRY")
    b.link(b.g("Show Stones"), empty.inputs["Switch"])
    b.link(b.g("Geometry"), empty.inputs["True"])
    join = b.node("GeometryNodeJoinGeometry", 8840, 200)
    b.link(prongs, join.inputs["Geometry"])
    b.link(empty.outputs["Output"], join.inputs["Geometry"])
    done = b.realize(join.outputs["Geometry"], 9040, 200)
    gout = b.node("NodeGroupOutput", 10240, 200)
    b.link(done, gout.inputs["Geometry"])

    print("Node group '%s' rebuilt: %d nodes" % (GROUP_NAME, len(ng.nodes)))
    return ng


def main():
    build_group()


if __name__ == "__main__":
    main()
