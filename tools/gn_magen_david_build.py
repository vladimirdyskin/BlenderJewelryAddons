"""
My_Magen_David — плоский правильный Маген Давид в плоскости XY, луч вверх по +Y, центр в origin.

Интерфейс:
    Mode        — Lines: два треугольника-рамки, слитые в один контур (без переплетения);
                  Solid: сплошная звезда; Double Outline: две полосы вдоль края звезды
    Size        — расстояние между концами противоположных лучей (диаметр описанной окружности)
    Line Width  — ширина полосы по перпендикуляру к ней (в Lines — не больше Size / 8,
                  при Size / 8 дырки в лучах закрываются)
    Offset      — Double Outline: зазор между внешней и внутренней полосой

Обозначения: R = Size / 2 — радиус по концам лучей, s = 1 / sqrt(3). Сектор 60° вокруг верхнего
луча, все квады против часовой (нормаль +Z). Сектор поворачивается 6 раз по 60°, совпадающие
вершины сливаются.

Lines (r = R - 2 * Width — радиус внутренних углов рамки):
    E  = (0, R)                   конец луча
    D  = (0, r)                   внутренний угол рамки
    B  = (R s / 2, R / 2)         внешний угол между лучами,  B' — зеркально по X
    A  = (r s / 2, r / 2)         угол центрального шестиугольника,  A' — зеркально
    C  = ((r - R / 2) s, R / 2)   угол дырки в луче,  C' — зеркально
    C2 = ((R - r / 2) s, r / 2)   угол ромба на пересечении полос (C' соседнего сектора)
    квады: половинки луча (B, E, D, C) и (C', D, E, B'), полоса (A', A, C, C'), ромб (A, C2, B, C);
    итого 24 квада, 36 вершин.
Solid: квад (O, B, E, B') с центром O; итого 6 квадов, 13 вершин.
Double Outline: все 12 сторон звезды лежат на 6 прямых на расстоянии R / 2 от центра, поэтому
    сдвиг края внутрь на d — та же звезда с радиусом R - 2 d. Полосы — между звёздами радиусов
    R0 = R, R1 = R - 2 W и R2 = R - 2 (W + Offset), R3 = R - 2 (2 W + Offset) (не меньше 0),
    у каждой звезды точки E_k, B_k, B'_k как выше. Квады на стороне: (B, E, E1, B1), (E, B', B'1, E1)
    и так же для R2/R3; итого 24 квада.

Реализация режима: квад Mesh Circle (4 вершины, N-Gon) × (6 * углов / 4) через Duplicate Elements;
у вершины индекс i = 4 * копия + угол, угол сектора — Index Switch по i % углов, поворот —
на 60° * (i // углов) вокруг Z. Режим выбирает Menu Switch, затем общий Merge by Distance.

Скрипт идемпотентен: группа пересобирается на месте, сокеты только добавляются
(и выстраиваются в порядке SOCKETS — значения на модификаторах не теряются).
"""

import math
import bpy

GROUP_NAME = "My_Magen_David"
MERGE_DIST = 1e-5
S3 = 1.0 / math.sqrt(3.0)
MODES = ["Lines", "Solid", "Double Outline"]

# (имя, тип, default, min, max)
SOCKETS = [
    ("Mode", "NodeSocketMenu", MODES[0], None, None),
    ("Size", "NodeSocketFloat", 10.0, 0.0, 1000.0),
    ("Line Width", "NodeSocketFloat", 0.8, 0.0, 100.0),
    ("Offset", "NodeSocketFloat", 0.5, 0.0, 100.0),
]

# углы квадов сектора по режимам (None — центр звезды)
CORNERS = {
    "Lines": ["B", "E", "D", "C",          # половинка луча справа
              "C'", "D", "E", "B'",        # половинка луча слева
              "A'", "A", "C", "C'",        # полоса между дырками
              "A", "C2", "B", "C"],        # ромб на пересечении полос
    "Solid": [None, "B", "E", "B'"],
    "Double Outline": ["B", "E", "E1", "B1", "E", "B'", "B'1", "E1",          # внешняя полоса
                       "B2", "E2", "E3", "B3", "E2", "B'2", "B'3", "E3"],     # внутренняя
}


def ensure_interface(ng):
    """Сокеты по именам: недостающие добавить, существующие не трогать; порядок — как в SOCKETS.
    Возвращает [(identifier, default)] добавленных — их значения проставляются на модификаторы."""
    items = {(it.name, it.in_out): it for it in ng.interface.items_tree if it.item_type == "SOCKET"}
    added = []
    for name, kind, default, mn, mx in SOCKETS:
        if (name, "INPUT") in items:
            continue
        s = ng.interface.new_socket(name, in_out="INPUT", socket_type=kind)
        if kind == "NodeSocketFloat":   # default меню — после сборки, когда известны пункты
            s.default_value = default
            s.min_value = mn
            s.max_value = mx
        items[(name, "INPUT")] = s
        added.append((s.identifier, default))
    if ("Geometry", "OUTPUT") not in items:
        ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    for name, *_ in reversed(SOCKETS):
        ng.interface.move(items[(name, "INPUT")], 0)
    return added


def build_group(name=GROUP_NAME):
    """Собрать (или пересобрать) node group. Возвращает готовую группу."""
    ng = bpy.data.node_groups.get(name)
    if ng is None:
        ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    # пункты нового Menu Switch получают другие внутренние id, а модификатор хранит id —
    # без этого после пересборки режим на модификаторах сам меняется; запоминаем его по имени
    mode_id = next((it.identifier for it in ng.interface.items_tree
                    if it.item_type == "SOCKET" and it.in_out == "INPUT" and it.name == "Mode"), None)
    kept = [(md, getattr(md.properties.inputs, mode_id).value)
            for obj in bpy.data.objects for md in obj.modifiers
            if mode_id and md.type == "NODES" and md.node_group == ng]
    ng.nodes.clear()
    added = ensure_interface(ng)
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
        put(nd.inputs[1], b)
        return nd.outputs[0]

    def imath(op, a, b, x, y):
        nd = node("FunctionNodeIntegerMath", x, y, operation=op)
        put(nd.inputs[0], a)
        put(nd.inputs[1], b)
        return nd.outputs[0]

    def vec(px, py, x, y):
        nd = node("ShaderNodeCombineXYZ", x, y)
        put(nd.inputs["X"], px)
        put(nd.inputs["Y"], py)
        return nd.outputs[0]

    def neg(v, x, y):
        return fmath("MULTIPLY", v, -1.0, x, y)

    def ring(corners, pts, x, y):
        """Квады сектора (по 4 угла подряд) × 6 поворотов на 60° вокруг Z."""
        n = len(corners)
        quad = node("GeometryNodeMeshCircle", x, y, fill_type="NGON")
        quad.inputs["Vertices"].default_value = 4
        dup = node("GeometryNodeDuplicateElements", x + 200, y, domain="FACE")
        ng.links.new(quad.outputs["Mesh"], dup.inputs["Geometry"])
        dup.inputs["Amount"].default_value = 6 * n // 4
        index = node("GeometryNodeInputIndex", x, y - 200).outputs[0]
        sw = node("GeometryNodeIndexSwitch", x + 400, y + 300, data_type="VECTOR")
        while len(sw.index_switch_items) < n:
            sw.index_switch_items.new()
        put(sw.inputs["Index"], imath("MODULO", index, n, x + 200, y - 200))
        for i, key in enumerate(corners):
            put(sw.inputs[i + 1], pts[key] if key else (0.0, 0.0, 0.0))
        sector = imath("DIVIDE_FLOOR", index, n, x + 200, y - 360)
        rot = node("ShaderNodeVectorRotate", x + 600, y, rotation_type="Z_AXIS")
        ng.links.new(sw.outputs[0], rot.inputs["Vector"])
        put(rot.inputs["Angle"], fmath("MULTIPLY", sector, math.pi / 3.0, x + 400, y - 360))
        setpos = node("GeometryNodeSetPosition", x + 800, y)
        ng.links.new(dup.outputs["Geometry"], setpos.inputs["Geometry"])
        ng.links.new(rot.outputs[0], setpos.inputs["Position"])
        return setpos.outputs["Geometry"]

    gin = node("NodeGroupInput", -1800, 0)
    size, line_w = gin.outputs["Size"], gin.outputs["Line Width"]

    # --- внешний край звезды (общий для всех режимов) ---
    big = fmath("MULTIPLY", size, 0.5, -1600, 200)                       # R
    big_h = fmath("MULTIPLY", size, 0.25, -1600, 40)                     # R / 2
    xb = fmath("MULTIPLY", size, 0.25 * S3, -1600, 360)                  # R s / 2
    pts = {
        "E": vec(0.0, big, -100, 600),
        "B": vec(xb, big_h, -100, 480),
        "B'": vec(neg(xb, -280, 420), big_h, -100, 360),
    }

    # --- Lines: рамки треугольников ---
    width = fmath("MINIMUM", line_w, fmath("MULTIPLY", size, 0.125, -1600, -120), -1420, -120)  # <= Size / 8
    small = fmath("SUBTRACT", big, fmath("MULTIPLY", width, 2.0, -1240, -120), -1060, 120)    # r
    small_h = fmath("MULTIPLY", small, 0.5, -880, -40)                  # r / 2
    xa = fmath("MULTIPLY", small_h, S3, -700, 280)                       # r s / 2
    xc = fmath("MULTIPLY", fmath("SUBTRACT", small, big_h, -880, 160), S3, -700, 160)    # (r - R/2) s
    xc2 = fmath("MULTIPLY", fmath("SUBTRACT", big, small_h, -700, 20), S3, -520, 20)     # (R - r/2) s
    pts.update({
        "D": vec(0.0, small, -100, 240),
        "A": vec(xa, small_h, -100, 120),
        "A'": vec(neg(xa, -280, 60), small_h, -100, 0),
        "C": vec(xc, big_h, -100, -120),
        "C'": vec(neg(xc, -280, -180), big_h, -100, -240),
        "C2": vec(xc2, small_h, -100, -360),
    })

    # --- Double Outline: уменьшенные звёзды R1..R3 ---
    two_w = fmath("MULTIPLY", line_w, 2.0, -1600, -1700)
    two_wg = fmath("MULTIPLY", fmath("ADD", line_w, gin.outputs["Offset"], -1600, -1860), 2.0, -1420, -1860)
    radii = {
        "1": fmath("SUBTRACT", big, two_w, -1240, -1700),
        "2": fmath("SUBTRACT", big, two_wg, -1240, -1860),
        "3": fmath("SUBTRACT", fmath("SUBTRACT", big, two_wg, -1240, -2020), two_w, -1060, -2020),
    }
    y = -1600
    for tag, rad in radii.items():
        rad = fmath("MAXIMUM", rad, 0.0, -880, y)
        for key, unit in (("E", (0.0, 1.0, 0.0)), ("B", (0.5 * S3, 0.5, 0.0)), ("B'", (-0.5 * S3, 0.5, 0.0))):
            sc = node("ShaderNodeVectorMath", -100, y, operation="SCALE")
            sc.inputs[0].default_value = unit
            put(sc.inputs["Scale"], rad)
            pts[key + tag] = sc.outputs[0]
            y -= 160

    # --- режимы и выход ---
    meshes = {
        "Lines": ring(CORNERS["Lines"], pts, 300, -700),
        "Solid": ring(CORNERS["Solid"], pts, 300, -1200),
        "Double Outline": ring(CORNERS["Double Outline"], pts, 300, -2300),
    }
    menu = node("GeometryNodeMenuSwitch", 1400, -1200, data_type="GEOMETRY")
    menu.enum_items.clear()
    for m in MODES:
        menu.enum_items.new(m)
    ng.links.new(gin.outputs["Mode"], menu.inputs["Menu"])
    for m in MODES:
        ng.links.new(meshes[m], menu.inputs[m])
    merge = node("GeometryNodeMergeByDistance", 1600, -1200)
    ng.links.new(menu.outputs[0], merge.inputs["Geometry"])
    merge.inputs["Distance"].default_value = MERGE_DIST
    # схлопнутая в центр полоса (Double Outline при W + Offset >= R / 2) оставляет вершину без граней
    faces = node("GeometryNodeInputMeshVertexNeighbors", 1600, -1400).outputs["Face Count"]
    loose = node("GeometryNodeDeleteGeometry", 1800, -1200, domain="POINT")
    ng.links.new(merge.outputs["Geometry"], loose.inputs["Geometry"])
    put(loose.inputs["Selection"], fmath("LESS_THAN", faces, 0.5, 1800, -1400))
    gout = node("NodeGroupOutput", 2000, -1200)
    ng.links.new(loose.outputs["Geometry"], gout.inputs["Geometry"])

    # default меню задаётся, когда пункты уже известны (после связи с Menu Switch)
    ng.interface_update(bpy.context)
    mode = next(it for it in ng.interface.items_tree
                if it.item_type == "SOCKET" and it.in_out == "INPUT" and it.name == "Mode")
    mode.default_value = MODES[0]
    for md, value in kept:
        if value in MODES:
            getattr(md.properties.inputs, mode_id).value = value
    # новый сокет на уже существующем модификаторе в 5.2 получает 0 / пусто, а не default
    for obj in bpy.data.objects:
        for md in obj.modifiers:
            if md.type == "NODES" and md.node_group == ng:
                for ident, default in added:
                    getattr(md.properties.inputs, ident).value = default

    print("Node group '%s' rebuilt: %d nodes" % (name, len(ng.nodes)))
    return ng


def main():
    build_group()


if __name__ == "__main__":
    main()
