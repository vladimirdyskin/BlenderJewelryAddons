"""
My_Round_Cast — круглый каст с крапанами. Повторяет группу RoundWithProngs (MyAssets.blend),
но построен на клетках под Subdivision Surface: на крапан 12 вершин, на стенку 32,
и каст следует за камнем: высоты берутся с объекта Diam, а не задаются в мм от рундиста.

Камень: Diam — камень-единица ø 1 (рундист на z = 0). Bounding Box его геометрии (Object Info
без As Instance) * ø Stone: table_z = max.z * D, culet_z = min.z * D, R = D/2. Diam пуст — обе 0.
Общий низ: bottom_z = culet_z - Cast/Below Culet — на нём кончаются и каст, и крапана.

    Крапан: ось через точку (R + ø * (0.5 - Intersection/100), z = 0), наклон Tilt наружу кверху
        (поворот вокруг этой точки), Count штук по кругу, поворот кольца ° Z, ось X крапана — наружу.
        Intersection — заход крапана на камень в % его диаметра: 0 — касается снаружи, 50 — ось
        на рундисте, 100 — крапан целиком над камнем (у RoundWithProngs «Intesetion» — % радиуса,
        его 50 = здесь 25). Центр нижнего торца (торец поперёк оси) на z = bottom_z, центр
        основания купола на z = table_z + Prongs/Above Table, верх купола на ø/2 дальше по оси.
        Длина ствола = разница высот / cos Tilt, не меньше ø * (0.05 - TAU_SH) — иначе плечо клетки
        уходит ниже основания и клетка выворачивается.
    Set (камень закреплён, нормы GIA): кончик опущен и наклонён к камню. В радиальной плоскости
        корона — отрезок от рундиста (z = 0) до края площадки (путь crown, высота table_z; край
        площадки — вершины Diam на высоте max.z). Купол ø/2: верх на Set Height % высоты площадки,
        касается короны на Set Cover % её пути. В клетку добавлено кольцо-излом на оси ствола,
        на ø ниже центра купола (16 вершин на крапан); плечо и верхушка — вдоль оси излом — центр
        купола. Наружу от ствола кончик не уходит. Above Table не действует.
        Посадка: вместо Cutter — оболочка камня, увеличенного по XY в SET_GROW (кончик лежит
        на короне), и Cutter ниже рундиста (z < -SET_CLIP * ø Stone). Оболочка камня вычитается
        из крапанов и без BoolCutter.
    Каст: верх на z = Cast/Z Offset, наружный радиус верха R + XY Offset (радиальный отступ от
        рундиста), стенка параллельна оси крапана: r(z) = r_top + (z - z_top) * tan Tilt,
        внутренний r(z) - Cast Thickness (по горизонтали), низ на bottom_z (высота не меньше 0.05).
    Прорезь (CastBool): параллелепипед высотой HeightBool, центр на середине высоты каста
        + OffsetBool, по X и Y — 1.5 наружного диаметра каста (режет насквозь).
    После SubD: прорезь -> BoolCutter: Union(крапана, каст) минус Cutter (масштаб ø Stone);
        без BoolCutter — Join, крапана и каст отдельными оболочками. ShowCutter показывает катер всегда.
    Общий булеан (при любом BoolCutter): из металла вычитаются BoolObject и все объекты BoolCollection
        (вычисленная геометрия, Relative — где стоят в сцене). Каждый объект — свой инстанс (Collection
        Info, Separate Children), т.е. отдельный операнд Manifold: пересекающиеся резаки режут верно.
        При BoolCutter — после Cutter; без него — крапана и каст режутся по отдельности.
        Камень не режется. Пусто — металл не меняется.
    Material и Smooth (Smooth by Angle 30°) — на металл; Realize Instances; камень Diam (инстанс,
    масштаб ø Stone) присоединяется последним и остаётся инстансом объекта.

Клетка крапана — ящик из трёх квадратных колец (основание, плечо, верхушка) с торцами-квадами,
сторона квадрата смотрит на камень. Числа из jewel_tools/gem_setting.py (докстринг, рамки
Prong Length / Prong Rings) при Tip Scale 1, Tip Round 1 и оси без наклона (наклон Tilt —
жёсткий поворот всего крапана). Низ — торец поперёк оси.
Рёбра кольца основания — crease 1 (плоский торец), остальное гладкое.

Клетка каста — трубка 8 точек по кругу x 4 угла профиля, все продольные петли — crease 1:
сечение остаётся параллелограммом, петли — B-сплайн восьмиугольника. Радиус петли после SubD =
радиус клетки * CAST_SHRINK, поэтому клетка растянута по XY на 1 / CAST_SHRINK.

Subdivision = 0: голая клетка (крапана и стенка — отдельные оболочки, атрибут crease_edge),
без union и вырезов — применить и править руками.

Интерфейс: ключ сокета — панель + имя (Z Offset есть в Prongs и в Cast). Устаревшие (OBSOLETE)
удаляются, недостающие добавляются, порядок в панелях — как в SOCKETS; значения остальных входов
на модификаторах не меняются. Узлы пересобираются целиком. Помощник сборки B — из
tools/gn_prongs_build.py.
"""

import bpy
import importlib.util
import os
from math import pi, sqrt

GROUP_NAME = "My_Round_Cast"
PRONGS_PATH = os.path.expanduser("~/GitHub/BlenderJewelryAddons/tools/gn_prongs_build.py")

# --- клетка крапана: из jewel_tools/gem_setting.py (не менять там — скопировано) ---
K_PRISM = (11.0 / 12.0 + 2.0 * sqrt(2.0) / 3.0) * 0.5   # средний радиус ствола / полусторона
DOME_APEX = 149.0 / 162.0                                # вершина купола над плечом, доля шага
TIP_FLARE = 1.15                                         # верхушка шире плеча
SHOULDER_A = 6.0 / (4.0 + TIP_FLARE) - 0.1
SHOULDER_B = 1.0 / (4.0 + TIP_FLARE) - 0.1
DOME_MAX = 1.8                                           # шаг плечо — верхушка при Tip Round 1
# Tip Scale 1, Tip Round 1, ось вертикальна — всё линейно по ø:
H_BOT = 1.0 / (2.0 * K_PRISM)                  # полусторона основания / ø
H_SH = H_BOT * (SHOULDER_A - SHOULDER_B)       # полусторона плеча / ø
H_TIP = H_SH * TIP_FLARE                       # полусторона верхушки / ø
DELTA = H_SH * DOME_MAX                        # шаг плечо — верхушка / ø
# верх купола (плечо + DOME_APEX * шаг) на Height + ø/2 над основанием
TAU_SH = 0.5 - DOME_APEX * DELTA               # плечо: Height + ø * TAU_SH
TAU_TIP = TAU_SH + DELTA                       # верхушка: Height + ø * TAU_TIP
MIN_STEM = 0.05 - TAU_SH                       # ствол не короче ø * MIN_STEM: плечо выше основания
MIN_CAST = 0.05                                # высота каста не меньше, мм
# --- Set: загнутый кончик ---
SET_BREAK = 1.0        # излом клетки ниже центра купола, в ø
MIN_BREAK = 0.05       # излом не ниже ø * MIN_BREAK над основанием
SET_GROW = 1.01        # оболочка камня для посадки: увеличение по XY (меньше катера — без совпадающих стенок)
SET_CLIP = 0.002       # Cutter действует ниже z = -SET_CLIP * ø Stone

# --- клетка каста: предел B-сплайна восьмиугольника / радиус клетки ---
# в вершинах (2 + cos 45°)/3 = 0.9024, в серединах 0.9013
CAST_SHRINK = 0.9019
SLOT_SIZE = 1.5        # прорезь по X и Y — доля наружного диаметра каста
SMOOTH_ANGLE = pi / 6  # как Smooth by Angle 30° у RoundWithProngs
SOLVER = "MANIFOLD"

# (имя, тип, default, min, max, панель, subtype)
SOCKETS = [
    ("Diam", "NodeSocketObject", None, None, None, None, None),
    ("Realize All", "NodeSocketBool", False, None, None, None, None),
    ("Subdivision", "NodeSocketInt", 2, 0, 4, None, None),
    ("ShowStone", "NodeSocketBool", True, None, None, "Round", None),
    ("ø Stone", "NodeSocketFloat", 2.0, 0.5, 30.0, "Round", None),
    ("Smooth", "NodeSocketBool", True, None, None, "Prongs", None),
    ("Count", "NodeSocketInt", 4, 2, 20, "Prongs", None),
    ("° Z", "NodeSocketFloat", 0.7854, None, None, "Prongs", "ANGLE"),
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
# убраны из прежних версий: (панель, имя)
OBSOLETE = [("Prongs", "Z Offset"), ("Prongs", "Height"), ("Cast", "Height"), ("Cast", "Cast Taper")]


def load_prongs():
    spec = importlib.util.spec_from_file_location("gn_prongs_ref", PRONGS_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def socket_keys(ng):
    """{(панель, имя): identifier} входов группы."""
    out = {}
    for it in ng.interface.items_tree:
        if it.item_type == "SOCKET" and it.in_out == "INPUT":
            out[(it.parent.name if it.parent and it.parent.name else None, it.name)] = it.identifier
    return out


def socket_items(ng):
    """{(панель, имя): item} входов группы."""
    return {(it.parent.name if it.parent and it.parent.name else None, it.name): it
            for it in ng.interface.items_tree if it.item_type == "SOCKET" and it.in_out == "INPUT"}


def ensure_interface(ng):
    """Устаревшие сокеты убрать, недостающие добавить (ключ — панель + имя), порядок в панелях —
    как в SOCKETS. Значения существующих входов на модификаторах не трогать."""
    for key in OBSOLETE:
        it = socket_items(ng).get(key)
        if it is not None:
            ng.interface.remove(it)
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
    # порядок внутри панели — как в SOCKETS (default сокета — тоже; на модификаторы не влияет)
    have = socket_items(ng)
    pos = {}
    for name, stype, default, mn, mx, panel, subtype in SOCKETS:
        if panel is None:
            continue
        it = have[(panel, name)]
        ng.interface.move_to_parent(it, panels[panel], pos.get(panel, 0))
        pos[panel] = pos.get(panel, 0) + 1
        if default is not None and it.default_value != default:
            it.default_value = default
    # новый сокет на уже существующем модификаторе в 5.2 получает 0 / False, а не default
    for obj in bpy.data.objects:
        for md in obj.modifiers:
            if md.type == "NODES" and md.node_group == ng:
                for ident, default in added:
                    if default is not None:
                        getattr(md.properties.inputs, ident).value = default


def build_prong_cage(b, d, bottom_z, dome_z, tilt, cos_t, inter, table_z, crown, sett, ox, oy):
    """Клетка одного крапана: ящик из квадратных колец, основание на z = 0, ось +Z, ось X — наружу.
    Обычный крапан — 3 кольца (основание, плечо, верхушка), ось прямая.
    Set — 4 кольца: добавлен излом K на оси ствола; плечо и верхушка — вдоль оси K — E (центр купола),
    кольцо излома — по биссектрисе (его проекция на плоскость поперёк ствола — тот же квадрат).
    inter — Intersection %, table_z — высота площадки над рундистом, crown — путь по короне от
    рундиста до края площадки, sett = (Set, Set Cover %, Set Height %).
    Расчёт загиба — рамка Set Tip от точки (ox, oy). Используется и в gn_gem_cast_build.py.
    """
    set_on, cover, height = sett

    def madd(a, m, c, x, y):
        n = b.node("ShaderNodeMath", x, y, operation="MULTIPLY_ADD")
        for sock, v in zip(n.inputs, (a, m, c)):
            b._set(sock, v)
        return n.outputs[0]

    def combine(vx, vy, vz, x, y):
        n = b.node("ShaderNodeCombineXYZ", x, y)
        for sock, v in zip(n.inputs, (vx, vy, vz)):
            b._set(sock, v)
        return n.outputs[0]

    def mul(a, c, x, y):
        return b.math("MULTIPLY", a, c, x, y)

    # --- Set: центр купола E и излом K ---
    b.section("Set Tip")
    X = lambda i: ox + 200 * i
    Y = lambda j: oy - 170 * j
    rho = mul(d, 0.5, X(0), Y(0))
    cov = b.math("DIVIDE", cover, 100.0, X(0), Y(1))
    hgt = b.math("DIVIDE", height, 100.0, X(0), Y(2))
    sin_t = b.math("SINE", tilt, None, X(0), Y(3))
    keep = b.math("SUBTRACT", 0.5, b.math("DIVIDE", inter, 100.0, X(7), Y(2)), X(8), Y(2))
    # радиальная плоскость: u — к камню от рундиста, z — вверх от рундиста; корона — отрезок
    # (0, 0) — (crown, table_z). Купол: верх на hgt * table_z, касается короны в её точке cov.
    ez_w = b.math("SUBTRACT", mul(table_z, hgt, X(1), Y(2)), rho, X(2), Y(2))
    dz = b.math("SUBTRACT", ez_w, mul(table_z, cov, X(1), Y(1)), X(3), Y(1))
    root = b.math("SQRT", b.math("MAXIMUM", b.math("SUBTRACT", mul(rho, rho, X(3), Y(0)), mul(dz, dz, X(4), Y(1)),
                                                   X(5), Y(0)), 0.0, X(6), Y(0)), None, X(7), Y(0))
    eu = b.math("SUBTRACT", mul(crown, cov, X(7), Y(1)), root, X(8), Y(0))
    # x — наружу от оси крапана на z = 0 (рундист на -ø * keep)
    ex_w = mul(madd(d, keep, eu, X(9), Y(0)), -1.0, X(10), Y(0))
    # в систему ствола (поворот на -Tilt), высота — от основания; наружу от ствола кончик не уходит
    x_f = b.math("MINIMUM", b.math("SUBTRACT", mul(ex_w, cos_t, X(11), Y(0)), mul(ez_w, sin_t, X(11), Y(1)),
                                   X(12), Y(0)), 0.0, X(13), Y(0))
    z_f = b.math("ADD", mul(ex_w, sin_t, X(11), Y(2)), mul(ez_w, cos_t, X(11), Y(3)), X(12), Y(2))
    ez = b.math("SUBTRACT", z_f, b.math("DIVIDE", bottom_z, cos_t, X(12), Y(3)), X(13), Y(2))
    # излом K — на оси ствола, на ø * SET_BREAK ниже E
    kz = b.math("MAXIMUM", madd(d, -SET_BREAK, ez, X(14), Y(2)), mul(d, MIN_BREAK, X(14), Y(3)), X(15), Y(2))
    dzk = b.math("MAXIMUM", b.math("SUBTRACT", ez, kz, X(16), Y(2)), mul(d, MIN_STEM, X(16), Y(3)), X(17), Y(2))
    length = b.math("SQRT", b.math("ADD", mul(x_f, x_f, X(14), Y(0)), mul(dzk, dzk, X(18), Y(2)), X(19), Y(1)),
                    None, X(20), Y(1))
    sin_g = b.math("DIVIDE", mul(x_f, -1.0, X(14), Y(1)), length, X(21), Y(0))
    cos_g = b.math("DIVIDE", dzk, length, X(21), Y(2))

    # --- клетка: ящик 3 (Set — 4) кольца x 4, основание на z = 0 ---
    b.section("Prong Cage")
    # длина ствола: от низа до основания купола по оси, не короче ø * MIN_STEM
    stem = b.math("DIVIDE", b.math("SUBTRACT", dome_z, bottom_z, 900, 1400), cos_t, 1100, 1400)
    h_prong = b.math("MAXIMUM", stem, mul(d, MIN_STEM, 1100, 1200), 1300, 1400)
    # без Set: излом на основании, ось прямая — плечо и верхушка как раньше
    k_z = b.switch("FLOAT", set_on, 0.0, kz, -200, -450)
    k_len = b.switch("FLOAT", set_on, h_prong, length, -200, -610)
    k_sin = b.switch("FLOAT", set_on, 0.0, sin_g, -200, -770)
    k_cos = b.switch("FLOAT", set_on, 1.0, cos_g, -200, -930)
    segs = b.math("ADD", set_on, 2.0, 0, 620)
    cyl = b.node("GeometryNodeMeshCylinder", 0, 400, fill_type="NGON")
    cyl.inputs["Vertices"].default_value = 4
    b.link(segs, cyl.inputs["Side Segments"])
    cyl.inputs["Radius"].default_value = sqrt(2.0)
    cyl.inputs["Depth"].default_value = 2.0
    # углы на диагоналях (+-1, +-1): сторона квадрата смотрит на камень (ось X — наружу)
    rot = b.node("GeometryNodeTransform", 200, 400)
    b.link(cyl.outputs["Mesh"], rot.inputs["Geometry"])
    rot.inputs["Rotation"].default_value = (0.0, 0.0, pi / 4)
    pos = b.node("GeometryNodeInputPosition", 200, 100).outputs[0]
    zc = b.node("ShaderNodeSeparateXYZ", 400, 100)
    b.link(pos, zc.inputs[0])
    # crease: рёбра кольца основания (z = -1 у обоих концов)
    crease = b.node("GeometryNodeStoreNamedAttribute", 600, 400, data_type="FLOAT", domain="EDGE")
    crease.inputs["Name"].default_value = "crease_edge"
    b.link(rot.outputs["Geometry"], crease.inputs["Geometry"])
    b.link(b.cmp("LESS_THAN", zc.outputs["Z"], -0.75, 600, 100), crease.inputs["Value"])
    # номер кольца 0..segs -> роль: 0 основание, 1 излом (только Set), 2 плечо, 3 верхушка
    k = b.math("ROUND", mul(b.math("ADD", zc.outputs["Z"], 1.0, 600, -100), mul(segs, 0.5, 600, -260), 800, -100),
               None, 1000, -100)
    ring = madd(b.math("MINIMUM", k, 1.0, 1000, -260), b.math("SUBTRACT", 1.0, set_on, 800, -260), k, 1200, -260)

    def by_ring(values, x, y):
        n = b.node("GeometryNodeIndexSwitch", x, y, data_type="FLOAT")
        while len(n.index_switch_items) < len(values):
            n.index_switch_items.new()
        b.link(ring, n.inputs["Index"])
        for i, v in enumerate(values):
            b._set(n.inputs[i + 1], v)
        return n.outputs[0]

    hb, hs, ht = mul(d, H_BOT, 0, -450), mul(d, H_SH, 0, -610), mul(d, H_TIP, 0, -770)
    # плечо и верхушка — на оси K — E, от излома
    a2, a3 = madd(d, TAU_SH, k_len, 0, -930), madd(d, TAU_TIP, k_len, 0, -1090)
    cx = by_ring((0.0, 0.0, mul(mul(k_sin, a2, 200, -450), -1.0, 400, -450),
                  mul(mul(k_sin, a3, 200, -610), -1.0, 400, -610)), 800, -450)
    cz = by_ring((0.0, k_z, madd(k_cos, a2, k_z, 200, -770), madd(k_cos, a3, k_z, 200, -930)), 800, -650)
    # сторона кольца вдоль X: проекция на X и подъём наружного края
    ax = by_ring((hb, hb, mul(hs, k_cos, 400, -770), mul(ht, k_cos, 400, -930)), 800, -850)
    az = by_ring((0.0, b.math("DIVIDE", mul(hb, k_sin, 200, -1090), b.math("ADD", k_cos, 1.0, 200, -1250), 400, -1090),
                  mul(hs, k_sin, 600, -1090), mul(ht, k_sin, 600, -1250)), 800, -1050)
    hy = by_ring((hb, hb, hs, ht), 800, -1250)
    sp = b.node("GeometryNodeSetPosition", 1200, 400)
    b.link(crease.outputs["Geometry"], sp.inputs["Geometry"])
    vma = b.node("ShaderNodeVectorMath", 1200, 100, operation="MULTIPLY_ADD")
    b.link(pos, vma.inputs[0])
    b.link(combine(ax, hy, 0.0, 1000, 100), vma.inputs[1])
    b.link(combine(cx, 0.0, madd(zc.outputs["X"], az, cz, 1000, -650), 1000, -450), vma.inputs[2])
    b.link(vma.outputs["Vector"], sp.inputs["Position"])
    return sp.outputs["Geometry"]


def build_group():
    pr = load_prongs()
    ng = bpy.data.node_groups.get(GROUP_NAME)
    if ng is None:
        ng = bpy.data.node_groups.new(GROUP_NAME, "GeometryNodeTree")
    ensure_interface(ng)
    ng.is_modifier = True
    ng.nodes.clear()
    keys = socket_keys(ng)
    b = pr.B(ng, -400)

    def gi(panel, name):
        ident = keys[(panel, name)]
        return next(s for s in b.gin.outputs if s.identifier == ident)

    def combine(vx, vy, vz, x, y):
        n = b.node("ShaderNodeCombineXYZ", x, y)
        for sock, v in zip(n.inputs, (vx, vy, vz)):
            b._set(sock, v)
        return n.outputs[0]

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
        b.link(b.named("crease_edge", "FLOAT", x - 200, y - 200).outputs["Attribute"], n.inputs["Edge Crease"])
        n.inputs["Limit Surface"].default_value = True
        return n.outputs["Mesh"]

    def gate(cond, geo, x, y):
        """выключено — пустая геометрия"""
        n = b.node("GeometryNodeSwitch", x, y, input_type="GEOMETRY")
        b.link(cond, n.inputs["Switch"])
        b.link(geo, n.inputs["True"])
        return n.outputs["Output"]

    def madd(a, m, c, x, y):
        """a * m + c"""
        n = b.node("ShaderNodeMath", x, y, operation="MULTIPLY_ADD")
        for sock, v in zip(n.inputs, (a, m, c)):
            b._set(sock, v)
        return n.outputs[0]

    def object_info(sock, space, x, y):
        n = b.node("GeometryNodeObjectInfo", x, y, transform_space=space)
        n.inputs["As Instance"].default_value = True
        b.link(sock, n.inputs["Object"])
        return n.outputs["Geometry"]

    d_stone = gi("Round", "ø Stone")
    s_stone = combine(d_stone, d_stone, d_stone, -100, -2400)

    # --- камень: высоты площадки и калетты по Bounding Box геометрии Diam ---
    b.section("Stone Heights")
    di = b.node("GeometryNodeObjectInfo", -100, 1400, transform_space="ORIGINAL")
    di.inputs["As Instance"].default_value = False
    b.link(gi(None, "Diam"), di.inputs["Object"])
    bb = b.node("GeometryNodeBoundBox", 100, 1400)
    b.link(di.outputs["Geometry"], bb.inputs["Geometry"])
    bmax = b.node("ShaderNodeSeparateXYZ", 300, 1500)
    b.link(bb.outputs["Max"], bmax.inputs[0])
    bmin = b.node("ShaderNodeSeparateXYZ", 300, 1300)
    b.link(bb.outputs["Min"], bmin.inputs[0])
    table_z = b.math("MULTIPLY", bmax.outputs["Z"], d_stone, 500, 1500)
    culet_z = b.math("MULTIPLY", bmin.outputs["Z"], d_stone, 500, 1300)
    bottom_z = b.math("SUBTRACT", culet_z, gi("Cast", "Below Culet"), 700, 1300)
    dome_z = b.math("ADD", table_z, gi("Prongs", "Above Table"), 700, 1500)
    tilt = gi("Prongs", "Tilt")
    cos_t = b.math("COSINE", tilt, None, 700, 1100)
    tan_t = b.math("TANGENT", tilt, None, 700, 950)

    # край площадки — вершины Diam на высоте max.z; crown — путь по короне от рундиста до него
    spos = b.node("GeometryNodeInputPosition", 100, 1900).outputs[0]
    sz = b.node("ShaderNodeSeparateXYZ", 300, 1900)
    b.link(spos, sz.inputs[0])
    on_table = b.cmp("GREATER_THAN", sz.outputs["Z"], b.math("MULTIPLY", bmax.outputs["Z"], 0.999, 500, 1750), 700, 1900)
    r_xy = b.vmath("LENGTH", b.vmath("MULTIPLY", spos, (1.0, 1.0, 0.0), 300, 2100), None, 500, 2100)
    st = b.node("GeometryNodeAttributeStatistic", 900, 1900, data_type="FLOAT", domain="POINT")
    b.link(di.outputs["Geometry"], st.inputs["Geometry"])
    b.link(on_table, st.inputs["Selection"])
    b.link(r_xy, b.enabled(st, "Attribute"))
    crown = b.math("MULTIPLY", d_stone, b.math("SUBTRACT", 0.5, b.enabled_out(st, "Max"), 1100, 1900), 1300, 1900)

    # --- клетка крапана: основание на z = 0, ось +Z; Set — кончик загнут к камню ---
    d = gi("Prongs", "ø")
    set_on = gi("Prongs", "Set")
    prong_cage = build_prong_cage(b, d, bottom_z, dome_z, tilt, cos_t, gi("Prongs", "Intersection"), table_z, crown,
                                  (set_on, gi("Prongs", "Set Cover"), gi("Prongs", "Set Height")), 0, 3200)

    # --- крапана по кругу: низ на bottom_z, наклон Tilt вокруг Y (ось через z = 0), Count штук ---
    b.section("Prong Ring")
    z_axis = b.math("DIVIDE", bottom_z, cos_t, 1500, 250)
    pc = transform(prong_cage, 1500, 400, translation=combine(0.0, 0.0, z_axis, 1500, 100))
    pc = transform(pc, 1700, 400, rotation=axis_angle((0.0, 1.0, 0.0), tilt, 1700, 100))
    # радиус: ø Stone/2 + ø * (0.5 - Intersection/100) — заход в % диаметра крапана
    keep = b.math("SUBTRACT", 0.5, b.math("DIVIDE", gi("Prongs", "Intersection"), 100.0, 1500, -200), 1700, -200)
    rr = madd(d_stone, 0.5, b.math("MULTIPLY", d, keep, 1900, -360), 1900, -200)
    circle = b.node("GeometryNodeMeshCircle", 2100, 100, fill_type="NONE")
    b.link(gi("Prongs", "Count"), circle.inputs["Vertices"])
    b.link(rr, circle.inputs["Radius"])
    pts = transform(circle.outputs["Mesh"], 2300, 100, rotation=axis_angle((0.0, 0.0, 1.0), gi("Prongs", "° Z"), 2300, -200))
    face_out = b.node("FunctionNodeAlignRotationToVector", 2500, -200, axis="X")
    b.link(b.node("GeometryNodeInputPosition", 2300, -400).outputs[0], face_out.inputs["Vector"])
    iop = b.node("GeometryNodeInstanceOnPoints", 2700, 400)
    b.link(pts, iop.inputs["Points"])
    b.link(pc, iop.inputs["Instance"])
    b.link(face_out.outputs["Rotation"], iop.inputs["Rotation"])
    real = b.node("GeometryNodeRealizeInstances", 2900, 400)
    b.link(iop.outputs["Instances"], real.inputs["Geometry"])
    prongs = real.outputs["Geometry"]

    # --- клетка каста: трубка 8 x 4, профиль как у MakeCast, продольные петли — crease 1 ---
    b.section("Cast Cage")
    y0 = -1600
    # верх: z_top, r_top = R + XY Offset; низ: bottom_z, r = r_top - h * tan Tilt
    z_top = gi("Cast", "Z Offset")
    r_top = madd(d_stone, 0.5, gi("Cast", "XY Offset"), 0, y0 - 300)
    th = gi("Cast", "Cast Thickness")
    h_cast = b.math("MAXIMUM", b.math("SUBTRACT", z_top, bottom_z, 0, y0 - 500), MIN_CAST, 200, y0 - 500)
    p2 = b.math("MULTIPLY", h_cast, tan_t, 400, y0 - 500)
    r = b.math("SUBTRACT", r_top, p2, 400, y0 - 300)
    quad = b.node("GeometryNodeCurvePrimitiveQuadrilateral", 1000, y0 - 200, mode="POINTS")
    b.link(combine(0.0, h_cast, 0.0, 800, y0 - 300), quad.inputs["Point 1"])
    b.link(combine(p2, 0.0, 0.0, 800, y0 - 460), quad.inputs["Point 2"])
    b.link(combine(b.math("SUBTRACT", p2, th, 600, y0 - 620), 0.0, 0.0, 800, y0 - 620), quad.inputs["Point 3"])
    b.link(combine(b.math("MULTIPLY", th, -1.0, 600, y0 - 780), h_cast, 0.0, 800, y0 - 780), quad.inputs["Point 4"])
    ccirc = b.node("GeometryNodeCurvePrimitiveCircle", 400, y0, mode="RADIUS")
    ccirc.inputs["Resolution"].default_value = 8
    b.link(r, ccirc.inputs["Radius"])
    # номер точки окружности: у продольного ребра концы на соседних точках — среднее дробное
    path = store(ccirc.outputs["Curve"], "_rc_k", "FLOAT", "POINT", b.node("GeometryNodeInputIndex", 400, y0 - 160).outputs[0],
                 600, y0)
    c2m = b.node("GeometryNodeCurveToMesh", 1200, y0)
    b.link(path, c2m.inputs["Curve"])
    b.link(quad.outputs["Curve"], c2m.inputs["Profile Curve"])
    flip = b.node("GeometryNodeFlipFaces", 1400, y0)
    b.link(c2m.outputs["Mesh"], flip.inputs["Mesh"])
    frac = b.math("FRACT", b.named("_rc_k", "FLOAT", 1400, y0 - 200).outputs["Attribute"], None, 1600, y0 - 200)
    cast = store(flip.outputs["Mesh"], "crease_edge", "FLOAT", "EDGE", b.cmp("GREATER_THAN", frac, 0.25, 1800, y0 - 200),
                 1800, y0)
    rm = b.node("GeometryNodeRemoveAttribute", 2000, y0)
    rm.inputs["Name"].default_value = "_rc_k"
    b.link(cast, rm.inputs["Geometry"])
    grow = 1.0 / CAST_SHRINK
    cast = transform(rm.outputs["Geometry"], 2200, y0, translation=combine(0.0, 0.0, z_top, 2200, y0 - 300),
                     scale=(grow, grow, 1.0))
    cast_cage = gate(gi("Cast", "Show"), cast, 2400, y0)

    # --- Subdivision Surface: крапана и стенка — отдельные оболочки ---
    b.section("Subdivision")
    prongs_sd = subd(prongs, 3300, 400)
    cast_sd = subd(cast_cage, 3300, y0)

    # --- прорезь: параллелепипед в середине высоты каста ---
    b.section("Cast Slot")
    span = b.math("MULTIPLY", b.math("MAXIMUM", r_top, r, 3500, y0 - 400), 2.0 * SLOT_SIZE, 3700, y0 - 400)
    cube = b.node("GeometryNodeMeshCube", 3900, y0 - 300)
    b.link(combine(span, span, gi("Cast", "HeightBool"), 3900, y0 - 500), cube.inputs["Size"])
    # центр — середина высоты каста + OffsetBool
    slot_z = b.math("ADD", madd(h_cast, -0.5, z_top, 3700, y0 - 700), gi("Cast", "OffsetBool"), 3900, y0 - 700)
    slot = transform(cube.outputs["Mesh"], 4100, y0 - 300, translation=combine(0.0, 0.0, slot_z, 4100, y0 - 700))
    slotted = boolean("DIFFERENCE", cast_sd, [slot], 4300, y0)
    cast_cut = b.switch("GEOMETRY", gi("Cast", "CastBool"), cast_sd, slotted, 4500, y0)

    # --- булеаны: union + катер посадки (BoolCutter), общий булеан BoolObject + BoolCollection ---
    b.section("Booleans")
    cutter = transform(object_info(gi("Bool", "Cutter"), "ORIGINAL", 4700, -700), 4900, -700, scale=s_stone)
    bool_obj = object_info(gi("Bool", "BoolObject"), "RELATIVE", 4700, -900)
    # каждый объект коллекции — свой инстанс = отдельный операнд Manifold (пересечения между ними допустимы)
    coll = b.node("GeometryNodeCollectionInfo", 4700, -1100, transform_space="RELATIVE")
    coll.inputs["Separate Children"].default_value = True
    b.link(gi("Bool", "BoolCollection"), coll.inputs["Collection"])
    common = [bool_obj, coll.outputs["Instances"]]
    # Set: посадку режут оболочка камня (кончик лежит на короне) и Cutter ниже рундиста —
    # отдельными операндами; оболочка меньше катера, совпадающих стенок нет
    grow = b.math("MULTIPLY", d_stone, SET_GROW, 4700, -1500)
    hull = b.node("GeometryNodeConvexHull", 5100, -1400)
    b.link(transform(di.outputs["Geometry"], 4900, -1400, scale=combine(grow, grow, d_stone, 4900, -1650)),
           hull.inputs["Geometry"])
    box = b.node("GeometryNodeMeshCube", 4900, -1900)
    side = b.math("MULTIPLY", d_stone, 4.0, 4700, -1900)
    b.link(combine(side, side, side, 4700, -2060), box.inputs["Size"])
    below = transform(box.outputs["Mesh"], 5100, -1900,
                      translation=combine(0.0, 0.0, b.math("MULTIPLY", d_stone, -2.0 - SET_CLIP, 4900, -2150), 5100, -2150))
    # Cutter пуст — пересечение не делать: Intersect с пустым операндом возвращает сам ящик
    count = b.node("GeometryNodeAttributeDomainSize", 5100, -2400, component="INSTANCES")
    b.link(cutter, count.inputs["Geometry"])
    low = gate(b.cmp("GREATER_THAN", count.outputs["Instance Count"], 0.0, 5300, -2400),
               boolean("INTERSECT", None, [cutter, below], 5300, -1900), 5500, -1900)
    seat = [b.switch("GEOMETRY", set_on, cutter, low, 5700, -1700),
            gate(set_on, hull.outputs["Convex Hull"], 5500, -1400)]
    united = boolean("UNION", None, [prongs_sd, cast_cut], 4900, 0)
    cut = boolean("DIFFERENCE", united, seat, 5100, 0)
    cut = boolean("DIFFERENCE", cut, common, 5300, 0)
    # без посадки крапана и каст режутся по отдельности и остаются отдельными оболочками
    plain = join([boolean("DIFFERENCE", prongs_sd, common + [seat[1]], 5100, -300),
                  boolean("DIFFERENCE", cast_cut, common, 5100, -500)], 5300, -400)
    metal = b.switch("GEOMETRY", gi("Bool", "BoolCutter"), plain, cut, 5700, 0)
    # катер виден при любом BoolCutter
    shown = gate(gi("Bool", "ShowCutter"), join(seat, 5700, -1500), 5900, -300)
    metal = join([metal, shown], 5800, 0)

    # --- выход: клетка при Subdivision 0, материал, сглаживание, камень ---
    b.section("Output")
    cage_all = join([prongs, cast_cage], 5700, -400)
    has_sd = b.cmp("GREATER_THAN", gi(None, "Subdivision"), 0, 5700, 300)
    metal = b.switch("GEOMETRY", has_sd, cage_all, metal, 5900, 0)
    mat = b.node("GeometryNodeSetMaterial", 6100, 0)
    b.link(metal, mat.inputs["Geometry"])
    b.link(gi("Prongs", "Material"), mat.inputs["Material"])
    sm_f = b.node("GeometryNodeSetShadeSmooth", 6300, -300, domain="FACE")
    b.link(mat.outputs["Geometry"], sm_f.inputs["Mesh"])
    sm_e = b.node("GeometryNodeSetShadeSmooth", 6500, -300, domain="EDGE")
    b.link(sm_f.outputs["Mesh"], sm_e.inputs["Mesh"])
    b.link(b.cmp("LESS_EQUAL", b.node("GeometryNodeInputMeshEdgeAngle", 6300, -500).outputs["Unsigned Angle"],
                 SMOOTH_ANGLE, 6500, -500), sm_e.inputs["Shade Smooth"])
    smooth = b.switch("GEOMETRY", gi("Prongs", "Smooth"), mat.outputs["Geometry"], sm_e.outputs["Mesh"], 6700, 0)
    realize = b.node("GeometryNodeRealizeInstances", 6900, 0)
    b.link(smooth, realize.inputs["Geometry"])
    b.link(gi(None, "Realize All"), realize.inputs["Realize All"])
    realize.inputs["Depth"].default_value = 2

    # камень — инстанс объекта Diam: на него не вешать Set Material / Remove Attribute / Merge
    stone = transform(object_info(gi(None, "Diam"), "ORIGINAL", 6700, -700), 6900, -700, scale=s_stone)
    stone = gate(gi("Round", "ShowStone"), stone, 7100, -700)
    out = join([realize.outputs["Geometry"], stone], 7300, 0)
    b.frame = None
    gout = b.node("NodeGroupOutput", 7500, 0)
    b.link(out, gout.inputs["Geometry"])

    print("Node group '%s' rebuilt: %d nodes" % (GROUP_NAME, len(ng.nodes)))
    return ng


def setup(name="Round Cast", diam=None, cutter=None):
    """Объект с пустым мешем и модификатором. Значения входов не сбрасывает."""
    ng = build_group()
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, bpy.data.meshes.new(name))
        bpy.context.scene.collection.objects.link(ob)
    md = next((m for m in ob.modifiers if m.type == "NODES" and m.node_group == ng), None)
    if md is None:
        md = ob.modifiers.new(GROUP_NAME, "NODES")
        md.node_group = ng
    keys = socket_keys(ng)
    for key, obj in (((None, "Diam"), diam), (("Bool", "Cutter"), cutter)):
        if obj:
            getattr(md.properties.inputs, keys[key]).value = bpy.data.objects[obj] if isinstance(obj, str) else obj
    ob.update_tag()
    print("Round cast object '%s' set up" % ob.name)
    return ob


def main():
    build_group()


if __name__ == "__main__":
    main()
