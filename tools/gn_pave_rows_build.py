"""
Pave Rows — строгие ряды камней по поверхности вдоль условной направляющей кривой.

Модификатор вешается на кривую-направляющую (как My_Gems_On_Curve). Кривая условная:
задаёт только направление и середину полосы, может висеть над поверхностью —
сначала проецируется на Surface, дальше всё строится по поверхности.

Этап 1 — ряды и камни:
    Resample направляющей (шаг Sample Step), касательная T0 — в атрибут (до проекции:
    касательная сдвигаемого ряда копит шум проекции и уводит ряд в зигзаг)
    -> проекция на Surface (Geometry Proximity)
    Duplicate Elements (Spline) x Rows, номер ряда k в атрибут
    Repeat Zone (Surface Steps): шаг поперёк по A = N x T0 на s_k / Steps + проекция
        s_k = (k - (Rows-1)/2) * h + Row Offset — расстояние от направляющей вдоль поверхности
    Ряды — копии направляющей с одним числом точек: точка j каждого ряда лежит на одном
    поперечном сечении.

    Общая сетка по сечениям (ряды на изгибе разной длины: если центровать каждый
    отдельно, полушаг между рядами к концам уплывает и камни сходятся по диагонали):
        m(j) = min длины сегмента j у крайних рядов (самый сжатый ряд на этом участке)
        C(j) = накопленная m — длина «самого тесного ряда» до сечения j
        камень (k, x): C = C_total/2 + x * p, x = i + 0.5 * ((k - k_ref) mod 2)
        C -> сечение j + доля (Sample Nearest по точкам (C, 0, 0)) -> точка на ряду k
    В самом сжатом ряду зазор ровно Gap, в остальных — чуть больше.
    Сетка Rows x M мест не удаляется: у места флаг valid (камень есть). Отбор камней
    (Trim и будущие условия) только меняет valid — крапана перестраиваются сами.
    Камень: Z = нормаль поверхности, X = направление ряда, посадка Seat Offset по нормали.

Этап 2 — крапана (по решётке, без поиска ближайших). Индекс места g = k*M + ii,
x = ii - floor(M/2) + o_k, o_k = 0.5 * ((k - k_ref) mod 2). Соседи камня a = (k, x):
    b = (k, x+1) = g+1,  f = (k, x-1) = g-1
    c = (k+1, x+0.5) = g + M + 2*o_k,  e = (k+1, x-0.5) = c - 1,  dn = (k-1, x+0.5) = g - M + 2*o_k
У каждой тройки решётки ровно одно ребро в ряду — тройки перебираются по паре (a, b):
    0: (a, b, c)    1: (a, b, dn)             — на три камня, центр описанной окружности
Краевые (на два камня) — у ребра, с одной стороны которого тройки нет:
    2/3: ребро a-b, нет c / нет dn          4/5: ребро a-c, нет b / нет e
    6/7: ребро a-e, нет f / нет c
    положение: середина ребра + (p / (2*sqrt(3)) + Edge Offset) в сторону без тройки
    (как у крапана тройки с одинаковыми зазорами). Каждое ребро «принадлежит» одному камню —
    дублей нет.
Замыкающие (End Prongs) — у конца ряда, тройки с двумя пустыми соседями:
    8/9:  впереди — нет b и нет c / нет b и нет dn
    10/11: сзади — нет f и нет e / нет f и нет dn2 = (k-1, x-0.5)
    как краевой у виртуального ребра a -> a +- T * (p + 2 * End Offset): выступающий конец
    ряда закрывается парой (±30° от оси ряда), утопленный конец в «зубце» держат краевые.
Затем проекция на Surface, Prong Z Offset по нормали, Z = нормаль.

Ластик — ручное удаление камней: Eraser (объект) и/или Eraser Collection. Камня нет, если
центр места внутри ластика: точка позади ближайшей грани (Geometry Proximity + нормаль
этой грани) — надёжно для выпуклых форм (куб, сфера, цилиндр в любом масштабе и повороте),
вогнутое — набором выпуклых в коллекции. Меняет только valid — крапана перестраиваются.

Выход: инстансы камней помечены атрибутом pave_stone (bool, домен Instance) — по нему
отдельный объект с группой Pave Cutters (tools/gn_pave_cutters_build.py) ставит катеры.

Шаг между рядами: h = sqrt((D + Row Gap)^2 - (p/2)^2) — диагональный зазор = Row Gap.
Направляющая — один сплайн.

Интерфейс: сокеты только добавляются, если их нет — повторный запуск скрипта
не сбрасывает значения на модификаторах. Узлы пересобираются целиком.
"""

import bpy

GROUP_NAME = "Pave Rows"
ATTR_ROW = "_pr_row"     # ряд k (int)
ATTR_X = "_pr_x"         # позиция в решётке x (float, полуцелые в сдвинутых рядах)
ATTR_TAN = "_pr_t"       # касательная направляющей
ATTR_SEG = "_pr_seg"     # длина сегмента ряда
ATTR_M = "_pr_m"         # min сегмент по крайним рядам
ATTR_C = "_pr_c"         # накопленная длина по сечениям
ATTR_CS = "_pr_cs"       # координата места по C
ATTR_VALID = "_pr_valid" # 1 — камень есть
ATTR_G = "_pr_g"         # индекс места в сетке
ATTR_N = "_pr_n"         # нормаль поверхности в месте
ATTR_DIR = "_pr_dir"     # ось X инстанса
ATTR_TYPE = "_pr_type"   # тип крапана 0..11
ATTR_STONE = "pave_stone"  # на выходе: True у инстансов-камней (для Pave Cutters), не удаляется
ATTR_PDIR = "_pr_pdir"   # ось X крапана — отдельно от _pr_dir: поля пересчитываются
                         # в каждом узле, перезапись _pr_dir развернула бы замыкающие сзади

# (имя, тип, default, min, max, панель)
SOCKETS = [
    ("Surface", "NodeSocketObject", None, None, None, "Surface"),
    ("Flip Normal", "NodeSocketBool", False, None, None, "Surface"),
    ("Row Offset", "NodeSocketFloat", 0.0, None, None, "Surface"),
    ("Surface Steps", "NodeSocketInt", 16, 1, 200, "Surface"),
    ("Sample Step", "NodeSocketFloat", 0.05, 0.005, 1.0, "Surface"),
    ("Diam", "NodeSocketObject", None, None, None, "Stones"),
    ("Show Stone", "NodeSocketBool", True, None, None, "Stones"),
    ("Gem Size", "NodeSocketFloat", 1.0, 0.05, None, "Stones"),
    ("Rows", "NodeSocketInt", 3, 1, 50, "Stones"),
    ("Gap", "NodeSocketFloat", 0.06, 0.0, None, "Stones"),
    ("Row Gap", "NodeSocketFloat", 0.06, 0.0, None, "Stones"),
    ("Trim Start", "NodeSocketFloat", 0.0, 0.0, None, "Stones"),
    ("Trim End", "NodeSocketFloat", 0.0, 0.0, None, "Stones"),
    ("Seat Offset", "NodeSocketFloat", 0.0, None, None, "Stones"),
    ("Prongs", "NodeSocketObject", None, None, None, "Prongs"),
    ("Show Prongs", "NodeSocketBool", True, None, None, "Prongs"),
    ("Prong Size", "NodeSocketFloat", 1.2, 0.0, None, "Prongs"),
    ("Prong Height", "NodeSocketFloat", 1.0, 0.0, None, "Prongs"),
    ("Prong Z Offset", "NodeSocketFloat", 0.0, None, None, "Prongs"),
    ("Edge Prongs", "NodeSocketBool", True, None, None, "Prongs"),
    ("Edge Offset", "NodeSocketFloat", 0.0, None, None, "Prongs"),
    ("End Prongs", "NodeSocketBool", True, None, None, "Prongs"),
    ("End Offset", "NodeSocketFloat", 0.0, None, None, "Prongs"),
    ("Eraser", "NodeSocketObject", None, None, None, "Eraser"),
    ("Eraser Collection", "NodeSocketCollection", None, None, None, "Eraser"),
    ("Realize", "NodeSocketBool", False, None, None, None),
]


def ensure_interface(ng):
    items = {(it.name, it.item_type) for it in ng.interface.items_tree}
    if ("Geometry", "SOCKET") not in items:
        ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    panels = {it.name: it for it in ng.interface.items_tree if it.item_type == "PANEL"}
    names = {it.name for it in ng.interface.items_tree if it.item_type == "SOCKET"}
    added = []
    for name, stype, default, mn, mx, panel in SOCKETS:
        if name in names:
            continue
        parent = None
        if panel:
            parent = panels.get(panel) or ng.interface.new_panel(panel)
            panels[panel] = parent
        s = ng.interface.new_socket(name, in_out="INPUT", socket_type=stype, parent=parent)
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

    def __init__(self, ng):
        self.ng, self.N, self.L = ng, ng.nodes, ng.links
        self.gin = self.N.new("NodeGroupInput")
        self.gin.location = (-2400, 0)

    def node(self, idname, x, y, **props):
        n = self.N.new(idname)
        n.location = (x, y)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def link(self, a, b):
        self.L.new(a, b)

    def g(self, name):
        return self.gin.outputs[name]

    def _set(self, sock, v):
        if isinstance(v, (int, float, tuple)):
            sock.default_value = v
        else:
            self.link(v, sock)

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

    def enabled(self, node, name):
        # одноимённые сокеты под разные режимы — берём активный
        return next(s for s in node.inputs if s.name == name and s.enabled)

    def enabled_out(self, node, name):
        return next(s for s in node.outputs if s.name == name and s.enabled)

    def named(self, name, dtype, x, y):
        n = self.node("GeometryNodeInputNamedAttribute", x, y, data_type=dtype)
        n.inputs["Name"].default_value = name
        return n.outputs["Attribute"]

    def store(self, geo, name, dtype, value, domain, x, y):
        n = self.node("GeometryNodeStoreNamedAttribute", x, y, data_type=dtype, domain=domain)
        n.inputs["Name"].default_value = name
        self.link(geo, n.inputs["Geometry"])
        self._set(self.enabled(n, "Value"), value)
        return n.outputs["Geometry"]

    def sample(self, geo, value, index, dtype, x, y):
        n = self.node("GeometryNodeSampleIndex", x, y, data_type=dtype, domain="POINT", clamp=True)
        self.link(geo, n.inputs["Geometry"])
        self._set(self.enabled(n, "Value"), value)
        self._set(n.inputs["Index"], index)
        return self.enabled_out(n, "Value")

    def pick(self, dtype, index, values, x, y):
        """Index Switch: значение по номеру (типу крапана)."""
        n = self.node("GeometryNodeIndexSwitch", x, y, data_type=dtype)
        while len([s for s in n.inputs if s.identifier.startswith("Item_")]) < len(values):
            n.index_switch_items.new()
        self._set(n.inputs["Index"], index)
        items = [s for s in n.inputs if s.identifier.startswith("Item_")]
        for sock, v in zip(items, values):
            self._set(sock, v)
        return n.outputs[0]


def surface_normal(b, surface_geo, flip, x, y):
    """Нормаль поверхности в ближайшей точке (с учётом Flip Normal)."""
    nrm = b.node("GeometryNodeInputNormal", x - 200, y - 120)
    sns = b.node("GeometryNodeSampleNearestSurface", x, y, data_type="FLOAT_VECTOR")
    b.link(surface_geo, sns.inputs["Mesh"])
    b.link(nrm.outputs["Normal"], b.enabled(sns, "Value"))
    sign = b.node("GeometryNodeSwitch", x, y - 220, input_type="FLOAT")
    sign.inputs["False"].default_value = 1.0
    sign.inputs["True"].default_value = -1.0
    b.link(flip, sign.inputs["Switch"])
    return b.vmath("SCALE", b.enabled_out(sns, "Value"), sign.outputs[0], x + 200, y)


def project(b, geo, surface_geo, x, y):
    """Set Position на ближайшую точку поверхности."""
    prox = b.node("GeometryNodeProximity", x, y - 160, target_element="FACES")
    b.link(surface_geo, prox.inputs["Geometry"])
    setp = b.node("GeometryNodeSetPosition", x + 200, y)
    b.link(geo, setp.inputs["Geometry"])
    b.link(prox.outputs["Position"], setp.inputs["Position"])
    return setp.outputs["Geometry"]


def instance(b, points, obj_socket, show, rotation_dir, normal, scale, x, y):
    """Инстансы объекта на точках: Z = normal, X = rotation_dir."""
    rot = b.node("FunctionNodeAxesToRotation", x, y - 300, primary_axis="Z", secondary_axis="X")
    b.link(normal, rot.inputs["Primary Axis"])
    b.link(rotation_dir, rot.inputs["Secondary Axis"])
    info = b.node("GeometryNodeObjectInfo", x, y + 300)
    info.inputs["As Instance"].default_value = True
    b.link(obj_socket, info.inputs["Object"])
    iop = b.node("GeometryNodeInstanceOnPoints", x + 250, y)
    b.link(points, iop.inputs["Points"])
    b.link(show, iop.inputs["Selection"])
    b.link(info.outputs["Geometry"], iop.inputs["Instance"])
    b.link(rot.outputs["Rotation"], iop.inputs["Rotation"])
    b.link(scale, iop.inputs["Scale"])
    return iop.outputs["Instances"]


def build_group():
    ng = bpy.data.node_groups.get(GROUP_NAME)
    if ng is None:
        ng = bpy.data.node_groups.new(GROUP_NAME, "GeometryNodeTree")
    ng.is_modifier = True
    ensure_interface(ng)
    ng.nodes.clear()
    b = B(ng)

    # --- поверхность в координатах кривой ---
    surf = b.node("GeometryNodeObjectInfo", -2400, -600, transform_space="RELATIVE")
    b.link(b.g("Surface"), surf.inputs["Object"])
    S = surf.outputs["Geometry"]

    # --- константы раскладки ---
    D = b.g("Gem Size")
    p = b.math("ADD", D, b.g("Gap"), -2200, -900)                          # шаг в ряду
    dg = b.math("ADD", D, b.g("Row Gap"), -2200, -1000)
    half = b.math("MULTIPLY", p, 0.5, -2000, -900)
    h2 = b.math("SUBTRACT", b.math("POWER", dg, 2.0, -1800, -1000), b.math("POWER", half, 2.0, -1800, -900), -1600, -950)
    h = b.math("SQRT", b.math("MAXIMUM", h2, 0.0, -1400, -950), None, -1200, -950)  # шаг между рядами
    kref = b.math("FLOOR", b.math("MULTIPLY", b.g("Rows"), 0.5, -1400, -1100), None, -1200, -1100)

    # --- направляющая на поверхность ---
    res = b.node("GeometryNodeResampleCurve", -2200, 0)
    res.inputs["Mode"].default_value = "Length"
    res.keep_last_segment = True
    b.link(b.g("Geometry"), res.inputs["Curve"])
    b.link(b.g("Sample Step"), b.enabled(res, "Length"))
    t0 = b.node("GeometryNodeInputTangent", -2200, -200)
    guide = b.store(res.outputs["Curve"], ATTR_TAN, "FLOAT_VECTOR", t0.outputs["Tangent"], "POINT", -2000, 150)
    guide = project(b, guide, S, -1900, 0)
    nsz = b.node("GeometryNodeAttributeDomainSize", -1700, 300, component="CURVE")
    b.link(guide, nsz.inputs["Geometry"])
    NP = nsz.outputs["Point Count"]                                         # точек в ряду

    # --- ряды: копии направляющей с номером ---
    dup = b.node("GeometryNodeDuplicateElements", -1600, 0, domain="SPLINE")
    b.link(guide, dup.inputs["Geometry"])
    b.link(b.g("Rows"), dup.inputs["Amount"])
    rows0 = b.store(dup.outputs["Geometry"], ATTR_ROW, "INT", dup.outputs["Duplicate Index"], "CURVE", -1400, 0)

    # s_k = (k - (Rows-1)/2) * h + Row Offset
    mid = b.math("MULTIPLY", b.math("SUBTRACT", b.g("Rows"), 1.0, -1400, -450), 0.5, -1200, -450)
    s_k = b.math("ADD", b.math("MULTIPLY", b.math("SUBTRACT", b.named(ATTR_ROW, "INT", -1400, -300), mid, -1000, -350), h, -800, -350),
                 b.g("Row Offset"), -600, -350)
    step = b.math("DIVIDE", s_k, b.g("Surface Steps"), -400, -350)

    # --- шагание поперёк по поверхности ---
    rin = b.node("GeometryNodeRepeatInput", -1200, 0)
    rout = b.node("GeometryNodeRepeatOutput", 200, 0)
    rin.pair_with_output(rout)
    b.link(b.g("Surface Steps"), rin.inputs["Iterations"])
    b.link(rows0, rin.inputs["Geometry"])
    nrm = surface_normal(b, S, b.g("Flip Normal"), -900, -150)
    across = b.vmath("NORMALIZE", b.vmath("CROSS_PRODUCT", nrm, b.named(ATTR_TAN, "FLOAT_VECTOR", -900, -400), -700, -250), None, -500, -250)
    mv = b.node("GeometryNodeSetPosition", -300, 0)
    b.link(rin.outputs["Geometry"], mv.inputs["Geometry"])
    b.link(b.vmath("SCALE", across, step, -300, -250), mv.inputs["Offset"])
    b.link(project(b, mv.outputs["Geometry"], S, -100, 0), rout.inputs["Geometry"])

    # длина сегмента ряда |P[g+1] - P[g]| (у последней точки ряда не используется)
    pos = b.node("GeometryNodeInputPosition", 300, -300).outputs["Position"]
    idx = b.node("GeometryNodeInputIndex", 300, -400).outputs["Index"]
    nxt = b.sample(rout.outputs["Geometry"], pos, b.math("ADD", idx, 1.0, 500, -400), "FLOAT_VECTOR", 700, -300)
    rows = b.store(rout.outputs["Geometry"], ATTR_SEG, "FLOAT", b.vmath("DISTANCE", nxt, pos, 900, -300), "POINT", 1100, 0)

    # --- сечения: m(j) по крайним рядам, C(j) накоплением ---
    j = b.node("GeometryNodeInputIndex", 1100, 400).outputs["Index"]
    last = b.math("MULTIPLY", b.math("SUBTRACT", b.g("Rows"), 1.0, 1100, 600), NP, 1300, 600)
    seg_a = b.sample(rows, b.named(ATTR_SEG, "FLOAT", 1300, 300), j, "FLOAT", 1500, 400)
    seg_b = b.sample(rows, b.named(ATTR_SEG, "FLOAT", 1300, 500), b.math("ADD", last, j, 1500, 600), "FLOAT", 1700, 500)
    car = b.store(guide, ATTR_M, "FLOAT", b.math("MINIMUM", seg_a, seg_b, 1900, 450), "POINT", 2100, 300)
    acc = b.node("GeometryNodeAccumulateField", 2100, 500, data_type="FLOAT", domain="POINT")
    b.link(b.named(ATTR_M, "FLOAT", 1900, 650), b.enabled(acc, "Value"))
    car = b.store(car, ATTR_C, "FLOAT", b.enabled_out(acc, "Trailing"), "POINT", 2300, 300)
    stat = b.node("GeometryNodeAttributeStatistic", 2500, 500, data_type="FLOAT", domain="POINT")
    b.link(car, stat.inputs["Geometry"])
    b.link(b.named(ATTR_M, "FLOAT", 2300, 650), b.enabled(stat, "Attribute"))
    ctot = b.enabled_out(stat, "Sum")
    # облако (C, 0, 0) — обратный поиск сечения по C
    cxyz = b.node("ShaderNodeCombineXYZ", 2500, 200)
    b.link(b.named(ATTR_C, "FLOAT", 2300, 150), cxyz.inputs["X"])
    car_pts = b.node("GeometryNodeCurveToPoints", 2500, 350, mode="EVALUATED")  # Sample Nearest — по облаку точек
    b.link(car, car_pts.inputs["Curve"])
    cloud = b.node("GeometryNodeSetPosition", 2700, 300)
    b.link(car_pts.outputs["Points"], cloud.inputs["Geometry"])
    b.link(cxyz.outputs["Vector"], cloud.inputs["Position"])

    # --- решётка мест: Rows x M ---
    M = b.math("ADD", b.math("CEIL", b.math("DIVIDE", ctot, p, 2700, 700), None, 2900, 700), 3.0, 3100, 700)
    pts = b.node("GeometryNodePoints", 3300, 0)
    b.link(b.math("MULTIPLY", M, b.g("Rows"), 3300, 700), pts.inputs["Count"])
    pidx = b.node("GeometryNodeInputIndex", 3300, 900).outputs["Index"]
    k = b.math("FLOOR", b.math("DIVIDE", pidx, M, 3500, 900), None, 3700, 900)
    i = b.math("SUBTRACT", b.math("SUBTRACT", pidx, b.math("MULTIPLY", k, M, 3700, 1000), 3900, 950),
               b.math("FLOOR", b.math("MULTIPLY", M, 0.5, 3700, 1100), None, 3900, 1100), 4100, 1000)
    o = b.math("MULTIPLY", b.math("FLOORED_MODULO", b.math("SUBTRACT", k, kref, 3900, 1200), 2.0, 4100, 1200), 0.5, 4300, 1200)
    xx = b.math("ADD", i, o, 4300, 1000)
    cs = b.math("ADD", b.math("MULTIPLY", ctot, 0.5, 4300, 800), b.math("MULTIPLY", xx, p, 4500, 900), 4700, 850)
    cand = b.store(pts.outputs["Points"], ATTR_ROW, "INT", k, "POINT", 3500, 0)
    cand = b.store(cand, ATTR_X, "FLOAT", xx, "POINT", 3700, 0)
    cand = b.store(cand, ATTR_CS, "FLOAT", cs, "POINT", 3900, 0)
    cand = b.store(cand, ATTR_G, "INT", pidx, "POINT", 4100, 0)

    # --- C -> сечение jA + доля -> точка на ряду k ---
    csv = b.node("ShaderNodeCombineXYZ", 5100, -300)
    b.link(b.named(ATTR_CS, "FLOAT", 4900, -400), csv.inputs["X"])
    near = b.node("GeometryNodeSampleNearest", 5300, -300, domain="POINT")
    b.link(cloud.outputs["Geometry"], near.inputs["Geometry"])
    b.link(csv.outputs["Vector"], near.inputs["Sample Position"])
    j0 = near.outputs["Index"]
    c0 = b.sample(car, b.named(ATTR_C, "FLOAT", 5300, -500), j0, "FLOAT", 5500, -400)
    jA = b.math("SUBTRACT", j0, b.math("GREATER_THAN", c0, b.named(ATTR_CS, "FLOAT", 5500, -600), 5700, -500), 5900, -450)
    jA = b.math("MINIMUM", b.math("MAXIMUM", jA, 0.0, 6100, -450), b.math("SUBTRACT", NP, 2.0, 6100, -600), 6300, -450)
    cA = b.sample(car, b.named(ATTR_C, "FLOAT", 6300, -650), jA, "FLOAT", 6500, -500)
    mA = b.sample(car, b.named(ATTR_M, "FLOAT", 6300, -800), jA, "FLOAT", 6500, -700)
    frac = b.math("DIVIDE", b.math("SUBTRACT", b.named(ATTR_CS, "FLOAT", 6500, -900), cA, 6700, -600),
                  b.math("MAXIMUM", mA, 1e-6, 6700, -750), 6900, -650)
    frac = b.math("MINIMUM", b.math("MAXIMUM", frac, 0.0, 7100, -650), 1.0, 7300, -650)
    gidx = b.math("ADD", b.math("MULTIPLY", b.named(ATTR_ROW, "INT", 6500, -1000), NP, 6700, -1000), jA, 6900, -950)
    pa = b.sample(rows, pos, gidx, "FLOAT_VECTOR", 7300, -900)
    pb = b.sample(rows, pos, b.math("ADD", gidx, 1.0, 7100, -1100), "FLOAT_VECTOR", 7300, -1100)
    dpb = b.vmath("SUBTRACT", pb, pa, 7500, -1000)
    place = b.node("GeometryNodeSetPosition", 7700, 0)
    b.link(cand, place.inputs["Geometry"])
    b.link(b.vmath("ADD", pa, b.vmath("SCALE", dpb, frac, 7500, -800), 7700, -800), place.inputs["Position"])

    # --- флаг «камень есть»: внутри [Trim Start + D/2, C_total - Trim End - D/2] ---
    rD = b.math("MULTIPLY", D, 0.5, 7700, 400)
    lo = b.math("ADD", b.g("Trim Start"), rD, 7900, 400)
    hi = b.math("SUBTRACT", b.math("SUBTRACT", ctot, b.g("Trim End"), 7900, 500), rD, 8100, 500)
    csn = b.named(ATTR_CS, "FLOAT", 7900, 600)
    off = b.math("MAXIMUM", b.math("LESS_THAN", csn, lo, 8100, 600), b.math("GREATER_THAN", csn, hi, 8100, 700), 8300, 600)

    # --- ластик: центр места внутри объекта / коллекции — камня нет ---
    # внутри = точка позади ближайшей грани ластика (надёжно для выпуклых форм)
    er_obj = b.node("GeometryNodeObjectInfo", 7700, 1000, transform_space="RELATIVE")
    b.link(b.g("Eraser"), er_obj.inputs["Object"])
    er_col = b.node("GeometryNodeCollectionInfo", 7700, 1300, transform_space="RELATIVE")
    b.link(b.g("Eraser Collection"), er_col.inputs["Collection"])
    er_join = b.node("GeometryNodeJoinGeometry", 7900, 1100)
    b.link(er_obj.outputs["Geometry"], er_join.inputs["Geometry"])
    b.link(er_col.outputs["Instances"], er_join.inputs["Geometry"])
    er = b.node("GeometryNodeRealizeInstances", 8100, 1100)
    b.link(er_join.outputs["Geometry"], er.inputs["Geometry"])
    er_prox = b.node("GeometryNodeProximity", 8300, 1100, target_element="FACES")
    b.link(er.outputs["Geometry"], er_prox.inputs["Geometry"])
    er_nrm = b.node("GeometryNodeSampleNearestSurface", 8300, 900, data_type="FLOAT_VECTOR")
    b.link(er.outputs["Geometry"], er_nrm.inputs["Mesh"])
    b.link(b.node("GeometryNodeInputNormal", 8100, 800).outputs["Normal"], b.enabled(er_nrm, "Value"))
    behind = b.math("LESS_THAN", b.vmath("DOT_PRODUCT", b.vmath("SUBTRACT", pos, er_prox.outputs["Position"], 8500, 1100),
                                         b.enabled_out(er_nrm, "Value"), 8700, 1000), 0.0, 8900, 1000)
    inside = b.math("MULTIPLY", behind, er_prox.outputs["Is Valid"], 9100, 1000)
    off = b.math("MAXIMUM", off, inside, 9300, 700)
    grid = b.store(place.outputs["Geometry"], ATTR_VALID, "FLOAT", b.math("SUBTRACT", 1.0, off, 8500, 600), "POINT", 8000, 0)
    grid = b.store(grid, ATTR_N, "FLOAT_VECTOR", surface_normal(b, S, b.g("Flip Normal"), 8000, -300), "POINT", 8300, 0)
    grid = b.store(grid, ATTR_DIR, "FLOAT_VECTOR", b.vmath("NORMALIZE", dpb, None, 8300, -400), "POINT", 8500, 0)

    # === камни ===
    valid = b.named(ATTR_VALID, "FLOAT", 8700, -200)
    gn = b.named(ATTR_N, "FLOAT_VECTOR", 8700, -300)
    stones = b.node("GeometryNodeDeleteGeometry", 8900, 0, domain="POINT")
    b.link(grid, stones.inputs["Geometry"])
    b.link(b.math("LESS_THAN", valid, 0.5, 8900, -200), stones.inputs["Selection"])
    seat = b.node("GeometryNodeSetPosition", 9100, 0)
    b.link(stones.outputs["Geometry"], seat.inputs["Geometry"])
    b.link(b.vmath("SCALE", gn, b.g("Seat Offset"), 9100, -300), seat.inputs["Offset"])
    gem_inst = instance(b, seat.outputs["Geometry"], b.g("Diam"), b.g("Show Stone"),
                        b.named(ATTR_DIR, "FLOAT_VECTOR", 9300, -500), gn, D, 9400, 0)

    # === крапана ===
    X0, Y0 = 8700, -2000
    dupp = b.node("GeometryNodeDuplicateElements", X0, Y0, domain="POINT")
    b.link(grid, dupp.inputs["Geometry"])
    b.link(b.math("GREATER_THAN", valid, 0.5, X0, Y0 - 200), dupp.inputs["Selection"])
    dupp.inputs["Amount"].default_value = 12
    prong = b.store(dupp.outputs["Geometry"], ATTR_TYPE, "INT", dupp.outputs["Duplicate Index"], "POINT", X0 + 200, Y0)

    t = b.named(ATTR_TYPE, "INT", X0, Y0 - 400)
    gi = b.named(ATTR_G, "INT", X0, Y0 - 500)
    kk = b.named(ATTR_ROW, "INT", X0, Y0 - 600)
    two_o = b.math("FLOORED_MODULO", b.math("SUBTRACT", kk, kref, X0 + 200, Y0 - 700), 2.0, X0 + 400, Y0 - 700)   # 2*o_k
    ii = b.math("SUBTRACT", gi, b.math("MULTIPLY", kk, M, X0 + 200, Y0 - 800), X0 + 400, Y0 - 800)
    rows_n = b.g("Rows")
    has_up = b.math("LESS_THAN", b.math("ADD", kk, 1.0, X0 + 600, Y0 - 600), rows_n, X0 + 800, Y0 - 600)
    has_dn = b.math("GREATER_THAN", kk, 0.5, X0 + 600, Y0 - 900)
    ii_c = b.math("ADD", ii, two_o, X0 + 600, Y0 - 750)
    in_c_row = b.math("LESS_THAN", ii_c, M, X0 + 800, Y0 - 750)
    in_e_row = b.math("GREATER_THAN", b.math("SUBTRACT", ii_c, 1.0, X0 + 800, Y0 - 1000), -0.5, X0 + 1000, Y0 - 1000)

    def nb(index, inside, x, y):
        """(флаг камня, позиция) соседа по индексу места; вне сетки — флаг 0."""
        v = b.math("MULTIPLY", inside, b.sample(grid, valid, index, "FLOAT", x, y), x + 200, y)
        return v, b.sample(grid, pos, index, "FLOAT_VECTOR", x, y - 150)

    idx_b = b.math("ADD", gi, 1.0, X0 + 1000, Y0 - 300)
    idx_f = b.math("SUBTRACT", gi, 1.0, X0 + 1000, Y0 - 400)
    idx_c = b.math("ADD", b.math("ADD", gi, M, X0 + 1000, Y0 - 500), two_o, X0 + 1200, Y0 - 500)
    idx_e = b.math("SUBTRACT", idx_c, 1.0, X0 + 1400, Y0 - 500)
    idx_dn = b.math("ADD", b.math("SUBTRACT", gi, M, X0 + 1000, Y0 - 700), two_o, X0 + 1200, Y0 - 700)
    vb, Pb = nb(idx_b, b.math("LESS_THAN", b.math("ADD", ii, 1.0, X0 + 1200, Y0 - 300), M, X0 + 1400, Y0 - 300), X0 + 1600, Y0 - 100)
    vf, Pf = nb(idx_f, b.math("GREATER_THAN", ii, 0.5, X0 + 1200, Y0 - 400), X0 + 1600, Y0 - 400)
    vc, Pc = nb(idx_c, b.math("MULTIPLY", has_up, in_c_row, X0 + 1400, Y0 - 650), X0 + 1600, Y0 - 700)
    ve, Pe = nb(idx_e, b.math("MULTIPLY", has_up, in_e_row, X0 + 1400, Y0 - 800), X0 + 1600, Y0 - 1000)
    vdn, Pdn = nb(idx_dn, b.math("MULTIPLY", has_dn, in_c_row, X0 + 1400, Y0 - 950), X0 + 1600, Y0 - 1300)
    # dn2 = (k-1, x-0.5) — для замыкающих сзади
    vdn2, _ = nb(b.math("SUBTRACT", idx_dn, 1.0, X0 + 1400, Y0 - 1450), b.math("MULTIPLY", has_dn, in_e_row, X0 + 1400, Y0 - 1550), X0 + 1600, Y0 - 1600)

    # виртуальный сосед по ряду для замыкающих: a +- T * (p + 2 * End Offset)
    T = b.named(ATTR_DIR, "FLOAT_VECTOR", X0 + 1600, Y0 - 1800)
    vlen = b.math("ADD", p, b.math("MULTIPLY", b.g("End Offset"), 2.0, X0 + 1600, Y0 - 1950), X0 + 1800, Y0 - 1950)
    Bfwd = b.vmath("ADD", pos, b.vmath("SCALE", T, vlen, X0 + 1800, Y0 - 1800), X0 + 2000, Y0 - 1800)
    Bback = b.vmath("SUBTRACT", pos, b.vmath("SCALE", T, vlen, X0 + 1800, Y0 - 2050), X0 + 2000, Y0 - 2050)

    E = b.g("Edge Prongs")
    EP = b.g("End Prongs")
    inv = lambda v, x, y: b.math("SUBTRACT", 1.0, v, x, y)
    mul = lambda a, c, x, y: b.math("MULTIPLY", a, c, x, y)
    XE = X0 + 2000
    exists = b.pick("FLOAT", t, [
        mul(vb, vc, XE, Y0 - 100),
        mul(vb, vdn, XE, Y0 - 200),
        mul(mul(vb, inv(vc, XE, Y0 - 300), XE + 200, Y0 - 300), E, XE + 400, Y0 - 300),
        mul(mul(vb, inv(vdn, XE, Y0 - 400), XE + 200, Y0 - 400), E, XE + 400, Y0 - 400),
        mul(mul(vc, inv(vb, XE, Y0 - 500), XE + 200, Y0 - 500), E, XE + 400, Y0 - 500),
        mul(mul(vc, inv(ve, XE, Y0 - 600), XE + 200, Y0 - 600), E, XE + 400, Y0 - 600),
        mul(mul(ve, inv(vf, XE, Y0 - 700), XE + 200, Y0 - 700), E, XE + 400, Y0 - 700),
        mul(mul(ve, inv(vc, XE, Y0 - 800), XE + 200, Y0 - 800), E, XE + 400, Y0 - 800),
        # замыкающие: тройка с двумя пустыми соседями впереди / сзади по ряду
        mul(mul(inv(vb, XE, Y0 - 900), inv(vc, XE, Y0 - 950), XE + 200, Y0 - 900), EP, XE + 400, Y0 - 900),
        mul(mul(inv(vb, XE, Y0 - 1000), inv(vdn, XE, Y0 - 1050), XE + 200, Y0 - 1000), EP, XE + 400, Y0 - 1000),
        mul(mul(inv(vf, XE, Y0 - 1100), inv(ve, XE, Y0 - 1150), XE + 200, Y0 - 1100), EP, XE + 400, Y0 - 1100),
        mul(mul(inv(vf, XE, Y0 - 1200), inv(vdn2, XE, Y0 - 1250), XE + 200, Y0 - 1200), EP, XE + 400, Y0 - 1200),
    ], XE + 600, Y0 - 300)
    Bp = b.pick("VECTOR", t, [Pb, Pb, Pb, Pb, Pc, Pc, Pe, Pe, Bfwd, Bfwd, Bback, Bback], XE + 600, Y0 - 600)
    Cp = b.pick("VECTOR", t, [Pc, Pdn, Pc, Pc, Pc, Pc, Pc, Pc, Pc, Pc, Pc, Pc], XE + 600, Y0 - 900)
    # сторона: + = к ряду k+1 при u = b - a; у замыкающих сзади u смотрит назад — знак обратный
    side = b.pick("FLOAT", t, [0.0, 0.0, 1.0, -1.0, -1.0, 1.0, 1.0, -1.0, 1.0, -1.0, -1.0, 1.0], XE + 600, Y0 - 1200)

    keep = b.node("GeometryNodeDeleteGeometry", XE + 800, Y0, domain="POINT")
    b.link(prong, keep.inputs["Geometry"])
    b.link(b.math("LESS_THAN", exists, 0.5, XE + 800, Y0 - 200), keep.inputs["Selection"])

    # центр описанной окружности (a, B, C): a + (|u|^2 (v x w) + |v|^2 (w x u)) / (2 |w|^2)
    XC = XE + 1000
    u = b.vmath("SUBTRACT", Bp, pos, XC, Y0 - 500)
    v = b.vmath("SUBTRACT", Cp, pos, XC, Y0 - 650)
    w = b.vmath("CROSS_PRODUCT", u, v, XC + 200, Y0 - 575)
    t1 = b.vmath("SCALE", b.vmath("CROSS_PRODUCT", v, w, XC + 400, Y0 - 500), b.vmath("DOT_PRODUCT", u, u, XC + 400, Y0 - 400), XC + 600, Y0 - 450)
    t2 = b.vmath("SCALE", b.vmath("CROSS_PRODUCT", w, u, XC + 400, Y0 - 700), b.vmath("DOT_PRODUCT", v, v, XC + 400, Y0 - 800), XC + 600, Y0 - 750)
    den = b.math("MAXIMUM", b.math("MULTIPLY", b.vmath("DOT_PRODUCT", w, w, XC + 600, Y0 - 900), 2.0, XC + 800, Y0 - 900), 1e-12, XC + 1000, Y0 - 900)
    tri = b.vmath("ADD", pos, b.vmath("SCALE", b.vmath("ADD", t1, t2, XC + 800, Y0 - 600), b.math("DIVIDE", 1.0, den, XC + 1000, Y0 - 800), XC + 1000, Y0 - 650), XC + 1200, Y0 - 600)
    # краевой: середина ребра + (p / (2*sqrt(3)) + Edge Offset) в сторону без тройки
    de = b.math("ADD", b.math("MULTIPLY", p, 0.28867513, XC, Y0 - 1100), b.g("Edge Offset"), XC + 200, Y0 - 1100)
    sdir = b.vmath("NORMALIZE", b.vmath("CROSS_PRODUCT", b.named(ATTR_N, "FLOAT_VECTOR", XC, Y0 - 1300), u, XC + 200, Y0 - 1250), None, XC + 400, Y0 - 1250)
    edge = b.vmath("ADD", b.vmath("SCALE", b.vmath("ADD", pos, Bp, XC + 400, Y0 - 1050), 0.5, XC + 600, Y0 - 1050),
                   b.vmath("SCALE", sdir, b.math("MULTIPLY", side, de, XC + 600, Y0 - 1150), XC + 800, Y0 - 1250), XC + 1000, Y0 - 1100)
    choose = b.node("GeometryNodeSwitch", XC + 1400, Y0 - 800, input_type="VECTOR")
    b.link(b.math("LESS_THAN", t, 1.5, XC + 1200, Y0 - 900), choose.inputs["Switch"])
    b.link(edge, choose.inputs["False"])
    b.link(tri, choose.inputs["True"])

    pdir = b.store(keep.outputs["Geometry"], ATTR_PDIR, "FLOAT_VECTOR", b.vmath("NORMALIZE", u, None, XC + 1400, Y0 - 300), "POINT", XC + 1600, Y0)
    mvp = b.node("GeometryNodeSetPosition", XC + 1800, Y0)
    b.link(pdir, mvp.inputs["Geometry"])
    b.link(choose.outputs["Output"], mvp.inputs["Position"])
    onsurf = project(b, mvp.outputs["Geometry"], S, XC + 2000, Y0)
    pn = surface_normal(b, S, b.g("Flip Normal"), XC + 2200, Y0 - 300)
    pz = b.node("GeometryNodeSetPosition", XC + 2400, Y0)
    b.link(onsurf, pz.inputs["Geometry"])
    b.link(b.vmath("SCALE", pn, b.g("Prong Z Offset"), XC + 2400, Y0 - 300), pz.inputs["Offset"])
    # нормаль и ось X — на месте крапана до подъёма по Z
    pcap = b.node("GeometryNodeCaptureAttribute", XC + 2200, Y0 + 300, domain="POINT")
    pcap.capture_items.new("VECTOR", "Normal")
    b.link(onsurf, pcap.inputs["Geometry"])
    b.link(pn, pcap.inputs["Normal"])
    b.link(pcap.outputs["Geometry"], pz.inputs["Geometry"])
    pscale = b.node("ShaderNodeCombineXYZ", XC + 2400, Y0 - 500)
    b.link(b.g("Prong Size"), pscale.inputs["X"])
    b.link(b.g("Prong Size"), pscale.inputs["Y"])
    b.link(b.g("Prong Height"), pscale.inputs["Z"])
    prong_inst = instance(b, pz.outputs["Geometry"], b.g("Prongs"), b.g("Show Prongs"),
                          b.named(ATTR_PDIR, "FLOAT_VECTOR", XC + 2600, Y0 - 500), pcap.outputs["Normal"],
                          pscale.outputs["Vector"], XC + 2700, Y0)

    # --- выход ---
    XO = XC + 3200
    join = b.node("GeometryNodeJoinGeometry", XO, 0)
    # метка камней на выходе — по ней Pave Cutters ставит катеры (крапана без метки)
    b.link(b.store(gem_inst, ATTR_STONE, "BOOLEAN", True, "INSTANCE", XO - 200, 200), join.inputs["Geometry"])
    b.link(prong_inst, join.inputs["Geometry"])
    rm = b.node("GeometryNodeRemoveAttribute", XO + 200, 0)
    rm.inputs["Pattern Mode"].default_value = "Wildcard"
    rm.inputs["Name"].default_value = "_pr_*"
    b.link(join.outputs["Geometry"], rm.inputs["Geometry"])
    real = b.node("GeometryNodeRealizeInstances", XO + 400, -150)
    b.link(rm.outputs["Geometry"], real.inputs["Geometry"])
    sw = b.node("GeometryNodeSwitch", XO + 600, 0, input_type="GEOMETRY")
    b.link(b.g("Realize"), sw.inputs["Switch"])
    b.link(rm.outputs["Geometry"], sw.inputs["False"])
    b.link(real.outputs["Geometry"], sw.inputs["True"])
    gout = b.node("NodeGroupOutput", XO + 800, 0)
    b.link(sw.outputs["Output"], gout.inputs["Geometry"])

    print("Node group '%s' rebuilt: %d nodes" % (GROUP_NAME, len(ng.nodes)))
    return ng


def main():
    build_group()


if __name__ == "__main__":
    main()
