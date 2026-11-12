"""
My_Cube_Ring — кольцо из кубических сегментов с фасками (как Chopard Ice Cube).

Ось кольца по Y, центр в origin, первый сегмент сверху (+Z). Один замкнутый меш без Boolean.

Интерфейс:
    Inner Diameter — внутренний диаметр
    Thickness      — толщина: от внутренней поверхности до центра наружной грани
    Square Size    — сторона квадрата = ширина кольца по Y
    Count          — число сегментов; 0 — подобрать, чтобы наружная грань была квадратной
    Chamfer        — фаска 45° по четырём краям наружной грани (ширина по грани),
                     и V-канавка 45° на боковинах между сегментами; не больше 0.95 от
                     половины грани, половины ширины и толщины

Геометрия сегмента (Ri — внутренний радиус, Ro = Ri + Thickness, a = pi / Count — половина
угла сегмента, H = Square Size / 2, c — фаска). Локальные оси сегмента: u — к центру наружной
грани, t — по окружности, y — по оси кольца; Th = Ro tan a — половина грани по окружности.
Плоскости (сторона +t, +y, остальные зеркально):
    O  наружная грань        u = Ro
    G  фаска канавки 45°     u + t = Ro + Th - c
    F  фаска по краю боковины u + y = Ro + H - c
    Y  боковина              y = H
    S  боковая канавка 45°   y + t_a = H - c, где t_a = t cos a - u sin a — расстояние до границы
                             сегмента (радиальная плоскость R: t_a = 0, у соседа — зеркально)
    внутри — цилиндр Ri.
Точки угла: A = O∩G∩F (угол грани), Q = G∩F∩S (сходятся три фаски), B = G∩S∩R (дно обеих
канавок), C = F∩S∩Y (конец боковой канавки у края), Ci / Bi — линия и дно боковой канавки на
внутреннем цилиндре. Из Q три линии стыка: Q-A, Q-B, Q-C.
Сетка: труба Curve to Mesh, вершины положены формулой по номеру столбца и строки.
    Столбцы сегмента: граница B, линия фаски K, STEPS - 1 внутренних (лучи от оси), линия фаски K.
    Строки профиля: внутренние ±H, край ±H, строка Q, линия фаски ±(H - c) — обход так,
    чтобы нормали смотрели наружу.
    Столбец K идёт по линиям стыка: A, Q, C, Ci; столбец B: B, B, B, Bi — совпавшие вершины
    сливает Merge by Distance, угловые клетки становятся треугольниками. Все грани плоские.
Внутренние грани гладкие, остальные острые. Merge by Distance сливает и совпавшие строки/столбцы
при Chamfer = 0 или на максимуме.

Скрипт идемпотентен: группа пересобирается на месте, сокеты только добавляются.
"""

import math
import bpy

GROUP_NAME = "My_Cube_Ring"
STEPS = 4            # промежутков между линиями фаски на сегмент (гладкость внутреннего цилиндра)
COLS = STEPS + 2     # столбцов на сегмент: граница, линия фаски, STEPS - 1 внутренних, линия фаски
MERGE_DIST = 1e-5
CHAMFER_MAX = 0.95   # доля от min(половина грани, половина ширины, толщина)

# (имя, тип, default, min, max)
SOCKETS = [
    ("Inner Diameter", "NodeSocketFloat", 17.0, 1.0, 200.0),
    ("Thickness", "NodeSocketFloat", 1.6, 0.05, 50.0),
    ("Square Size", "NodeSocketFloat", 4.0, 0.05, 50.0),
    ("Count", "NodeSocketInt", 0, 0, 1000),
    ("Chamfer", "NodeSocketFloat", 0.3, 0.0, 50.0),
]


def ensure_interface(ng):
    """Сокеты по именам: недостающие добавить, существующие не трогать.
    Новый сокет на уже существующем модификаторе в 5.2 получает 0, а не default — проставляем."""
    names = {(it.name, it.in_out) for it in ng.interface.items_tree if it.item_type == "SOCKET"}
    added = []
    for name, kind, default, mn, mx in SOCKETS:
        if (name, "INPUT") in names:
            continue
        s = ng.interface.new_socket(name, in_out="INPUT", socket_type=kind)
        s.default_value = default
        s.min_value = mn
        s.max_value = mx
        added.append((s.identifier, default))
    if ("Geometry", "OUTPUT") not in names:
        ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    for obj in bpy.data.objects:
        for md in obj.modifiers:
            if md.type == "NODES" and md.node_group == ng:
                for ident, default in added:
                    getattr(md.properties.inputs, ident).value = default


def build_group(name=GROUP_NAME):
    """Собрать (или пересобрать) node group. Возвращает готовую группу."""
    ng = bpy.data.node_groups.get(name)
    if ng is None:
        ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.nodes.clear()
    ensure_interface(ng)
    ng.is_modifier = True

    def node(kind, x, y, **props):
        nd = ng.nodes.new(kind)
        nd.location = (x, y)
        for k, v in props.items():
            setattr(nd, k, v)
        return nd

    def put(sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            ng.links.new(v, sock)
        else:
            sock.default_value = v

    def fmath(op, a, b, x, y):
        nd = node("ShaderNodeMath", x, y, operation=op)
        put(nd.inputs[0], a)
        if b is not None:
            put(nd.inputs[1], b)
        return nd.outputs[0]

    def imath(op, a, b, x, y):
        nd = node("FunctionNodeIntegerMath", x, y, operation=op)
        put(nd.inputs[0], a)
        put(nd.inputs[1], b)
        return nd.outputs[0]

    def icmp(op, a, b, x, y):
        nd = node("FunctionNodeCompare", x, y, data_type="INT", operation=op)
        ab = [s for s in nd.inputs if s.enabled]       # одноимённые A/B под разные типы — активные
        put(ab[0], a)
        put(ab[1], b)
        return nd.outputs[0]

    def switch(kind, cond, no, yes, x, y):
        nd = node("GeometryNodeSwitch", x, y, input_type=kind)
        put(nd.inputs["Switch"], cond)
        put(nd.inputs["False"], no)
        put(nd.inputs["True"], yes)
        return nd.outputs[0]

    def pick(index, values, x, y, kind="FLOAT"):
        """Index Switch по номеру строки/столбца."""
        nd = node("GeometryNodeIndexSwitch", x, y, data_type=kind)
        while len(nd.index_switch_items) < len(values):
            nd.index_switch_items.new()
        put(nd.inputs["Index"], index)
        for i, v in enumerate(values):
            put(nd.inputs[i + 1], v)
        return nd.outputs[0]

    def on_points(field, x, y):
        """Посчитать на вершинах — в контексте грани значение усреднится по её вершинам."""
        nd = node("GeometryNodeFieldOnDomain", x, y, domain="POINT", data_type="FLOAT")
        put(nd.inputs[0], field)
        return nd.outputs[0]

    def store(geo, attr, value, x, y):
        nd = node("GeometryNodeStoreNamedAttribute", x, y, data_type="INT", domain="POINT")
        nd.inputs["Name"].default_value = attr
        ng.links.new(geo, nd.inputs["Geometry"])
        put(nd.inputs["Value"], value)
        return nd.outputs["Geometry"]

    def named(attr, x, y):
        nd = node("GeometryNodeInputNamedAttribute", x, y, data_type="INT")
        nd.inputs["Name"].default_value = attr
        return nd.outputs["Attribute"]

    gin = node("NodeGroupInput", -2400, 0)
    g = gin.outputs

    # --- размеры ---
    ri = fmath("MULTIPLY", g["Inner Diameter"], 0.5, -2200, 400)
    ro = fmath("ADD", ri, g["Thickness"], -2000, 400)
    half = fmath("MULTIPLY", g["Square Size"], 0.5, -2200, 200)
    # число сегментов: грань квадратная, если 2 Ro tan(pi / N) = Square Size
    n_auto = fmath("ROUND", fmath("DIVIDE", math.pi, fmath("ARCTANGENT", fmath("DIVIDE", half, ro, -2000, 0),
                                                              None, -1840, 0), -1680, 0), None, -1520, 0)
    n = fmath("MAXIMUM", switch("FLOAT", icmp("GREATER_THAN", g["Count"], 0, -1680, -160), n_auto, g["Count"],
                                -1360, 0), 3.0, -1200, 0)
    alpha = fmath("DIVIDE", math.pi, n, -1040, 0)                       # a — половина угла сегмента
    theta = fmath("MULTIPLY", alpha, 2.0, -880, 80)
    tan_a = fmath("TANGENT", alpha, None, -880, -80)
    th = fmath("MULTIPLY", ro, tan_a, -720, -80)                        # Th
    # при c = H боковые канавки сходятся посередине и сегменты касаются по линии, при c = Thickness
    # канавка доходит до внутреннего цилиндра — оставляем перемычку
    c_max = fmath("MULTIPLY", fmath("MINIMUM", fmath("MINIMUM", th, half, -880, 360), g["Thickness"], -720, 360),
                  CHAMFER_MAX, -560, 360)
    c = fmath("MAXIMUM", fmath("MINIMUM", g["Chamfer"], c_max, -560, 200), 0.0, -400, 200)
    dc = fmath("ARCTANGENT", fmath("DIVIDE", fmath("SUBTRACT", th, c, -560, -240), ro, -400, -240), None, -240, -240)
    h_c = fmath("SUBTRACT", half, c, -240, 200)                         # H - c
    cos_a = fmath("COSINE", alpha, None, -880, -240)
    sin_a = fmath("SINE", alpha, None, -880, -400)
    g_d = fmath("SUBTRACT", fmath("ADD", ro, th, -560, -400), c, -400, -400)       # Ro + Th - c (плоскость G)
    # Q = G∩F∩S: u = (Ro + (Ro + Th - c) cos a) / (1 + cos a + sin a)
    a_q = fmath("DIVIDE", fmath("ADD", ro, fmath("MULTIPLY", g_d, cos_a, -240, -400), -80, -400),
                fmath("ADD", fmath("ADD", cos_a, sin_a, -400, -560), 1.0, -240, -560), 80, -400)
    b_q = fmath("SUBTRACT", g_d, a_q, 240, -400)
    y_q = fmath("SUBTRACT", fmath("ADD", ro, h_c, 80, -560), a_q, 240, -560)
    # B = G∩S∩R: u = (Ro + Th - c) / (1 + tan a)
    a_b = fmath("DIVIDE", g_d, fmath("ADD", tan_a, 1.0, -240, -720), 80, -720)
    # C = F∩S∩Y: u = Ro - c, t = (Ro - c) tan a - c / cos a
    a_c = fmath("SUBTRACT", ro, c, -240, -880)
    b_c = fmath("SUBTRACT", fmath("MULTIPLY", a_c, tan_a, -80, -880), fmath("DIVIDE", c, cos_a, -80, -1000), 80, -880)
    # Ci: линия боковой канавки на внутреннем цилиндре — угол a - asin(c / Ri)
    d_ci = fmath("SUBTRACT", alpha, fmath("ARCSINE", fmath("DIVIDE", c, ri, -400, -1160), None, -240, -1160), -80,
                 -1160)

    # --- труба: столбцы (_cr_col) по кругу × строки профиля (_cr_row) ---
    path = node("GeometryNodeCurvePrimitiveCircle", -1200, -700, mode="RADIUS")
    put(path.inputs["Resolution"], imath("MULTIPLY", n, COLS, -1360, -700))
    prof = node("GeometryNodeCurvePrimitiveCircle", -1200, -950, mode="RADIUS")
    prof.inputs["Resolution"].default_value = 8
    idx = node("GeometryNodeInputIndex", -1200, -1150).outputs[0]
    path_c = store(path.outputs["Curve"], "_cr_col", idx, -1000, -700)
    prof_c = store(prof.outputs["Curve"], "_cr_row", idx, -1000, -950)
    tube = node("GeometryNodeCurveToMesh", -800, -700)
    ng.links.new(path_c, tube.inputs["Curve"])
    ng.links.new(prof_c, tube.inputs["Profile Curve"])

    # --- столбец: номер сегмента k, тип (0 — граница B, 1 — линия фаски K, 2 — внутренний луч), сторона ---
    col = named("_cr_col", 0, -1400)
    j = imath("MODULO", col, COLS, 200, -1400)
    k = imath("DIVIDE_FLOOR", col, COLS, 200, -1560)
    col_type = pick(j, [0, 1] + [2] * (COLS - 3) + [1], 400, -1300, "INT")
    side = pick(j, [-1.0, -1.0] + [1.0] * (COLS - 2), 400, -1500)
    step = fmath("DIVIDE", fmath("MULTIPLY", dc, 2.0, 200, -1700), STEPS, 400, -1700)
    delta = fmath("SUBTRACT", fmath("MULTIPLY", imath("SUBTRACT", j, 1, 400, -1850), step, 560, -1750), dc,
                  720, -1750)                                              # угол внутреннего луча
    tan_d = fmath("TANGENT", delta, None, 880, -1750)

    # --- строка: тип (0 — внутренняя, 1 — край, 2 — Q, 3 — линия фаски), знак y ---
    row = named("_cr_row", 0, 600)
    # порядок строк задаёт обход профиля: так нормали наружу (проверено объёмом)
    row_type = pick(row, [0, 0, 1, 2, 3, 3, 2, 1], 200, 700, "INT")
    y_sign = pick(row, [1.0, -1.0, -1.0, -1.0, -1.0, 1.0, 1.0, 1.0], 200, 500)
    y_abs = pick(row_type, [half, half, y_q, h_c], 400, 700)            # для лучей и столбца K

    # --- (u, t, |y|) вершины в осях сегмента ---
    def vec3(a, b, c3, x, y):
        nd = node("ShaderNodeCombineXYZ", x, y)
        for sock, v in zip(nd.inputs, (a, b, c3)):
            put(sock, v)
        return nd.outputs[0]

    a_ray = pick(row_type, [fmath("MULTIPLY", ri, fmath("COSINE", delta, None, 880, -1600), 1040, -1600),
                            a_c, a_q, ro], 1200, -1500)
    v_ray = vec3(a_ray, fmath("MULTIPLY", a_ray, tan_d, 1400, -1600), y_abs, 1600, -1500)
    v_k = vec3(pick(row_type, [fmath("MULTIPLY", ri, fmath("COSINE", d_ci, None, 880, -1100), 1040, -1100),
                               a_c, a_q, ro], 1200, -1100),
               pick(row_type, [fmath("MULTIPLY", ri, fmath("SINE", d_ci, None, 880, -1250), 1040, -1250),
                               b_c, b_q, fmath("SUBTRACT", th, c, 1040, -1350)], 1200, -1250),
               y_abs, 1600, -1150)
    a_bnd = pick(row_type, [fmath("MULTIPLY", ri, cos_a, 1040, -800), a_b, a_b, a_b], 1200, -800)
    v_b = vec3(a_bnd, fmath("MULTIPLY", a_bnd, tan_a, 1400, -850), h_c, 1600, -850)
    local = pick(col_type, [v_b, v_k, v_ray], 1800, -1100, "VECTOR")
    sep = node("ShaderNodeSeparateXYZ", 2000, -1100)
    ng.links.new(local, sep.inputs[0])
    u_l = sep.outputs["X"]
    t_l = fmath("MULTIPLY", sep.outputs["Y"], side, 2200, -1200)
    phi = fmath("ADD", fmath("MULTIPLY", k, theta, 2000, -1400), math.pi / 2.0, 2200, -1400)
    cos_p = fmath("COSINE", phi, None, 2400, -1400)
    sin_p = fmath("SINE", phi, None, 2400, -1550)
    pos = vec3(fmath("SUBTRACT", fmath("MULTIPLY", u_l, cos_p, 2600, -1300), fmath("MULTIPLY", t_l, sin_p, 2600,
                                                                                  -1450), 2800, -1300),
               fmath("MULTIPLY", sep.outputs["Z"], y_sign, 2600, -1000),
               fmath("ADD", fmath("MULTIPLY", u_l, sin_p, 2600, -1600), fmath("MULTIPLY", t_l, cos_p, 2600, -1750),
                     2800, -1600), 3000, -1200)
    inner = icmp("LESS_THAN", row, 2, 400, 450)
    setpos = node("GeometryNodeSetPosition", 3200, -700)
    ng.links.new(tube.outputs["Mesh"], setpos.inputs["Geometry"])
    ng.links.new(pos, setpos.inputs["Position"])

    # --- гладкий только внутренний цилиндр ---
    smooth = node("GeometryNodeSetShadeSmooth", 3400, -700, domain="FACE")
    ng.links.new(setpos.outputs["Geometry"], smooth.inputs["Mesh"])
    put(smooth.inputs["Shade Smooth"], fmath("GREATER_THAN", on_points(inner, 3200, -950), 0.99, 3400, -950))

    merge = node("GeometryNodeMergeByDistance", 3600, -700)
    ng.links.new(smooth.outputs["Mesh"], merge.inputs["Geometry"])
    merge.inputs["Distance"].default_value = MERGE_DIST
    clean = node("GeometryNodeRemoveAttribute", 3800, -700)
    clean.inputs["Pattern Mode"].default_value = "Wildcard"
    clean.inputs["Name"].default_value = "_cr_*"
    ng.links.new(merge.outputs["Geometry"], clean.inputs["Geometry"])
    gout = node("NodeGroupOutput", 4000, -700)
    ng.links.new(clean.outputs["Geometry"], gout.inputs["Geometry"])

    print("Node group '%s' rebuilt: %d nodes" % (name, len(ng.nodes)))
    return ng


def main():
    build_group()


if __name__ == "__main__":
    main()
