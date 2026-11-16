"""Стек My_Stone -> My_Stone_Prongs -> My_Stone_Cast -> My_Setting_Bool (tools/gn_stone_setting_build.py)
против монолитов My_Round_Cast и My_Gem_Cast.

Фоновый Blender на КОПИИ библиотеки (файл не сохраняется):
  Blender --factory-startup --background --python tools/test_stone_setting.py -- <копия MyAssets.blend> [--preview]
  --preview  ещё и лист dist/previews/stone_setting_split.png
Код выхода 1 — проверка не прошла.

1. Round против My_Round_Cast (RWPRound, Cutter), те же значения: ø 1..6.5, BoolCutter, Set; Count 6,
   Tilt 0.14. Поверхность — вершины + центры треугольников одной сетки до BVH другой и обратно
   (триангуляция bmesh BEAUTY у обеих, см. evaluate).
   Set + BoolCutter выкл: стек режет оболочкой камня и каст — сравниваются только крапана, у стека
   ещё проверка «нет вершин металла в камне».
2. Emerald против My_Gem_Cast (EMERALD, места по умолчанию, авто-катер) 4 x 6 и 7 x 10, та же матрица.
3. BoolCutter: замкнуто, наружу, одна оболочка. Subdivision 0 — голые клетки, без булеанов.
4. Камень — инстанс Diam с "gem"; ShowStone выкл — инстанса камня нет, металл тот же; носитель.
   Diam пуст — встроенный камень по Cut (RWPRound / Unit Emerald): инстанс и металл те же, что с ним в Diam.
   Stone Material: пуст — камень остаётся инстансом Diam; задан — материал на камне, металл тот же.
5. Общий булеан: объект и коллекция из двух пересекающихся кубов при любом BoolCutter.
6. Stones: крапана и каст на втором объекте (сдвинут, повёрнут) = геометрия стека в мировых координатах.
7. Пересборка не меняет значения модификаторов (и меню Cut, Type, Tip).
8. Глухой каст (Type Bezel, без крапанов): Round 2 и 6.5, Emerald 4 x 6 и 7 x 10, Set выкл/вкл —
   замкнуто, клетка 56; верх на zt; наружная стенка на Wall от контура рундиста; металл не в камне,
   камень вставляется сверху / губа на cov и зазор до короны; опора под павильоном; с My_Setting_Bool
   поверхность та же (посадка не режется второй раз), BoolObject режет.
   --preview: ещё лист dist/previews/stone_setting_bezel.png
9. Крапан-коготь (Tip = Claw), полный стек с My_Setting_Bool: Round 2 / 3 / 6.5 (ø 0.5 / 0.6 / 0.9),
   Emerald 4 x 6 и 7 x 10 (ø 0.5), Set выкл/вкл — замкнуто, одна оболочка; клетка 16 вершин на
   крапан; заготовка: верх у h + Above Table + Claw Length ø (-0.25 ø .. +0.02), ствол у рундиста = ø (3 %);
   Set (коготь дугой): металл не в камне, верх крюка 0.95..1.05 от Set Height % h, заход по короне
   (Round: cov - 0.04 .. + 0.02, Emerald — печать), без раструба (выше рундиста не дальше наружной
   поверхности ствола + 0.02), острие (последние 25 % захода уже 0.5 ø, плечо шире 0.8 ø), контакт с камнем
   (самая дальняя вершина когтя не дальше 0.05 мм от камня); Tip обратно в Round — те же вершины.
   --preview: ещё лист dist/previews/stone_setting_claw.png (ряды — вид 3/4 и сверху)
10. Корзинка (Type = Basket), полный стек, Below Culet 1.0: Round 3 / 6.5 (ø 0.6 / 0.9), Emerald 7 x 10;
   Rail Shape Round и Flat, Set выкл/вкл; Round 6.5 ещё Tilt 8° и Claw + Set — замкнуто, одна оболочка;
   клетка каста 64; Flat: верх верхнего ранта на Z Offset, низ нижнего на zb, высота Rail, толщина
   Cast Thickness, наружная поверхность на d_out (0.002 мм, между крапанами, вне посадки); Round: сечение
   по ширине и высоте 2 %, наружная точка на d_out (0.01); сверху не видно (XY Offset <= 0: ранты не дальше
   0.01 за рундистом); зазор между рантами (>= 0.4 у Round 6.5 и Emerald 7 x 10) и калетта над нижним рантом
   (>= 0) — печать; металл не в камне, павильон лежит на верхнем ранте, на оси металла нет.
   --preview: ещё лист dist/previews/stone_setting_basket.png (ряды — вид 3/4 и сбоку)
11. Огранки по контуру: Oval 5 x 7 и Pear 5 x 8, ø 0.7, полный стек; Wall + Round, Wall + Claw + Set,
   Bezel выкл/вкл (без крапанов, как в разделе 8), Basket Round и Flat — замкнуто, металл не в камне;
   крапанов столько, сколько мест в контуре, ось на ø (0.5 - I) за рундистом (0.02 мм); стенка на XY Offset
   от рундиста (0.01 W); Bezel — верх, стенка, губа / вставка камня; Basket — размеры рантов (в самой
   широкой точке по +X), сверху не видно. Pear против My_Gem_Cast (та же Outline Pear), как разделы 1-2,
   только Set выкл: путь по короне у мест контура у стека свой (до края площадки по нормали места, минимум
   по местам), у монолита прежний — при Set вкл вместо сравнения заход круглого кончика у места с
   кратчайшим путём (окно GIA 0.33..0.50, как test_round_cast) и зазор до короны (0.05 мм).
   Свои точки: копия контура без одного места / с новым на рундисте — крапанов на одно меньше / больше,
   новый на своём месте; та же копия в Outline у Round и Emerald. Cut Oval -> Round — прежние вершины;
   носители контура и камня при Realize в конце стека — только вершины в начале координат.
   --preview: ещё лист dist/previews/stone_setting_cuts.png (ряды — вид 3/4 и сверху)
12. Остальные 13 огранок (длинная сторона 7 мм, ø 0.7), полный стек: Wall + Round — замкнуто, одна оболочка,
   металл не в камне, крапанов по RULES, ось на ø (0.5 - I) от места (0.02); Wall + Claw + Set — замкнуто,
   заход когтя — доля своего пути по короне в cov - 0.05 .. + 0.03 (пути разные — у места с кратчайшим),
   зазор круглого кончика Set у этого места до короны не больше 0.05 мм; Bezel выкл/вкл (без крапанов) — замкнуто, верх и стенка как в разделе 11; Basket,
   круглые ранты — замкнуто. Не проходящее по геометрической причине — в KNOWN (печать с замерами).
   --preview: ещё листы dist/previews/stone_setting_all_cuts.png и stone_setting_all_bezel.png (17 огранок)
13. Места крапанов — вершины без рёбер собственного меша объекта (мм), полный стек: Round 6.5 — три точки
   у рундиста дают три крапана на своих азимутах (0.5°), ось на ø (0.5 - I) за рундистом (0.02), без точек —
   прежние вершины; Emerald 7 x 10 — восемь точек у срезов углов, 8 крапанов, замкнуто, металл не в камне;
   Pear — встроенные места своими точками дают то же, сдвиг точки на 1 мм по рундисту двигает крапан, точка
   в 1 мм от рундиста (снаружи и внутри) садится на рундист; на выходе нет вершин без рёбер; куб в меше
   остаётся металлом; свои точки важнее Outline; Mirror X над My_Stone — четыре крапана зеркально.
   --preview: ещё лист dist/previews/stone_setting_points.png
14. V-крапан (V at Corners): Pear 6 x 9 (V на острие, два круглых на головке), Princess 6, Marquise 4 x 8,
   Triangle 6 (Wall и Basket), Set выкл/вкл — замкнуто, одна оболочка, металл не в камне; V столько, сколько
   мест на острых вершинах; стенка = V Thickness и крыло = V Length (0.02 мм, на наружных гранях вдали от
   рёбер); без V at Corners — прежние вершины. Triangle Wall / Basket с V — одна оболочка (без V — в KNOWN).
15. Лапка (Tip = Tab): Round 6.5, Emerald 7 x 10, Oval 5 x 7, Set выкл/вкл — замкнуто, металл не в камне;
   сечение ствола ø x Tab Width (0.02 мм); Set — заход в cov - 0.05 .. + 0.03 (Round, Oval; Emerald —
   печать), торец плоский.
16. Корона (Type = Crown): Round 6.5 Count 4 и 6, Emerald 7 x 10, Oval 5 x 7, Princess 6 с V — замкнуто, одна
   оболочка с крапанами, металл не в камне; верх на Z Offset у мест и на Z Offset - Crown Depth посередине
   (0.03 мм), толщина = Cast Thickness (0.01 мм); Crown Depth 0 — те же вершины, что Wall без прорези.
17. Edge Round: врез наружного ребра от идеального острого угла на лапке и на крыле V, камни 2 и 10 мм —
   0.2..1.0 Edge Round, оба размера в пределах 20 %; Edge Round 0 — врез меньше 0.002.
   --preview: ещё лист dist/previews/stone_setting_new_types.png
18. Edge Round на касте: 17 огранок (длинная сторона 7 мм, ø 0.7) x Wall / Bezel / Basket Flat / Basket Round /
   Crown, полный стек, Edge Round 0.08 и 0.3 — замкнуто, оболочек не больше, чем при 0. Только каст, 0.08
   против 0: скруглённый не дальше 0.5 Edge Round снаружи острого (галтель во внутренних вертикальных углах;
   без скруглённых вершин пути — 0), срез углов 0.2..1.5 Edge Round (круглый рант — только верхняя граница);
   Wall и Basket Flat — верх и низ на прежней высоте (1e-4). Bezel + Set: заход губы тот же, что при 0
   (Round, Oval, Cushion — 0.01 мм; с острыми вершинами — галтель до 0.5 Edge Round); Round — и габарит.
Разделы 1-16 идут с Edge Round 0 (stack_defaults): там проверяются точные размеры конструкции.
"""

from math import cos, pi, radians, sin, tan
from math import cos as pi_cos, sin as pi_sin
from pathlib import Path
import sys
import traceback

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "tools" / "gn_stone_setting_build.py"
ROUND_BUILD = ROOT / "tools" / "gn_round_cast_build.py"
GEM_BUILD = ROOT / "tools" / "gn_gem_cast_build.py"
PREVIEW = ROOT / "dist" / "previews" / "stone_setting_split.png"
PREVIEW_BEZEL = ROOT / "dist" / "previews" / "stone_setting_bezel.png"
PREVIEW_CLAW = ROOT / "dist" / "previews" / "stone_setting_claw.png"
PREVIEW_BASKET = ROOT / "dist" / "previews" / "stone_setting_basket.png"
PREVIEW_CUTS = ROOT / "dist" / "previews" / "stone_setting_cuts.png"
PREVIEW_ALL = ROOT / "dist" / "previews" / "stone_setting_all_cuts.png"
PREVIEW_POINTS = ROOT / "dist" / "previews" / "stone_setting_points.png"
PREVIEW_NEW = ROOT / "dist" / "previews" / "stone_setting_new_types.png"
PREVIEW_ALL_BEZEL = ROOT / "dist" / "previews" / "stone_setting_all_bezel.png"
TOL = 0.002         # мм
ROUND_SIZES = (1.0, 2.0, 3.0, 5.0, 6.5)
EMERALD_SIZES = ((4.0, 6.0), (7.0, 10.0))


def load(path, name):
    ns = {"__name__": name}
    exec(compile(path.read_text(), str(path), "exec"), ns)
    return ns


def mod(ob, group):
    return next(m for m in ob.modifiers if m.type == "NODES" and m.node_group and m.node_group.name == group)


def keys(md):
    """{(панель, имя): identifier}"""
    return {(it.parent.name or None, it.name): it.identifier for it in md.node_group.interface.items_tree
            if it.item_type == "SOCKET" and it.in_out == "INPUT" and it.socket_type != "NodeSocketGeometry"}


def get(ob, group, key):
    md = mod(ob, group)
    return getattr(md.properties.inputs, keys(md)[key]).value


def put(ob, group, key, value):
    md = mod(ob, group)
    getattr(md.properties.inputs, keys(md)[key]).value = value
    ob.update_tag()


def values(ob):
    """Все входы всех модификаторов-нод: {(модификатор, панель, имя): значение}"""
    return {(md.name,) + k: getattr(md.properties.inputs, i).value
            for md in ob.modifiers if md.type == "NODES" for k, i in keys(md).items()}


def evaluate(ob, world=False):
    """Вершины, грани, атрибуты металла (инстансы в меш не входят) и треугольники: центры, грань,
    вершины. Триангуляция — bmesh BEAUTY: диагональ неплоского квада и разбиение многоугольника
    выбираются по геометрии, а не по порядку вершин, поэтому у двух сеток с одной поверхностью
    треугольники одни. (С loop triangles неплоский квад купола делится по-разному — до 0.0016 мм,
    а у многоугольника-«замочной скважины» после булеана — контур и дырка, соединённые ребром —
    триангуляция Blender оставляет щель: точка внутри многоугольника, а до треугольников 0.0046 мм.)"""
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    m = ob.matrix_world if world else Matrix.Identity(4)
    verts = [m @ v.co for v in me.vertices]
    faces = [tuple(p.vertices) for p in me.polygons]
    attrs = {a.name for a in me.attributes}
    bm = bmesh.new()
    bm.from_mesh(me)
    ev.to_mesh_clear()
    layer = bm.faces.layers.int.new("_face")
    for f in bm.faces:
        f[layer] = f.index
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
    tri_verts = [tuple(v.index for v in f.verts) for f in bm.faces]
    tri_face = [f[layer] for f in bm.faces]
    bm.free()
    tris = [(verts[a] + verts[b] + verts[c]) / 3.0 for a, b, c in tri_verts]
    return verts, faces, tris, attrs, tri_face, tri_verts


def surface_dist(a, b):
    """Максимум расстояний вершин и центров треугольников одной сетки до треугольников другой,
    в обе стороны."""
    out = 0.0
    for ma, mb in ((a, b), (b, a)):
        if not mb[5]:
            return 9.0 if ma[0] else 0.0
        bvh = BVHTree.FromPolygons(mb[0], mb[5])
        for p in ma[0] + ma[2]:
            out = max(out, bvh.find_nearest(p)[3])
    return out


def shell_ids(faces, nverts):
    """Номера граней по оболочкам."""
    parent = list(range(nverts))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for f in faces:
        for v in f[1:]:
            parent[root(v)] = root(f[0])
    out = {}
    for k, f in enumerate(faces):
        out.setdefault(root(f[0]), []).append(k)
    return list(out.values())


def shells(faces, nverts):
    parent = list(range(nverts))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for f in faces:
        for v in f[1:]:
            parent[root(v)] = root(f[0])
    out = {}
    for f in faces:
        out.setdefault(root(f[0]), []).append(f)
    return list(out.values())


def closed_outward(verts, faces):
    """Каждое ребро у двух граней, все оболочки с положительным объёмом. -> (ok, оболочек)"""
    edges = {}
    for f in faces:
        for a, b in zip(f, f[1:] + f[:1]):
            k = (min(a, b), max(a, b))
            edges[k] = edges.get(k, 0) + 1
    if not faces or any(v != 2 for v in edges.values()):
        return False, len(shells(faces, len(verts)))
    parts = shells(faces, len(verts))
    for part in parts:
        vol = sum(verts[f[0]].dot(verts[f[i]].cross(verts[f[i + 1]])) / 6.0 for f in part for i in range(1, len(f) - 1))
        if vol <= 0:
            return False, len(parts)
    return True, len(parts)


def prongs_only(mesh, width):
    """Только оболочки крапанов: центр дальше 0.25 ширины от начала координат (каст — вокруг центра).
    Та же запись, что у evaluate: вершины (все), грани, центры и вершины их треугольников."""
    verts, faces, tris, attrs, tri_face, tri_verts = mesh
    keep = set()
    for part in shell_ids(faces, len(verts)):
        c = sum((verts[i] for k in part for i in faces[k]), Vector()) / sum(len(faces[k]) for k in part)
        if c.xy.length > 0.25 * width:
            keep.update(part)
    used = sorted({i for k in keep for i in faces[k]})
    sel = [j for j, k in enumerate(tri_face) if k in keep]
    return ([verts[i] for i in used], [faces[k] for k in sorted(keep)], [tris[j] for j in sel], attrs,
            [tri_face[j] for j in sel], [tri_verts[j] for j in sel], verts)


def prong_dist(a, b, width):
    pa, pb = prongs_only(a, width), prongs_only(b, width)
    out = 0.0
    for ma, mb in ((pa, pb), (pb, pa)):
        bvh = BVHTree.FromPolygons(mb[6], mb[5])
        for p in ma[0] + ma[2]:
            out = max(out, bvh.find_nearest(p)[3])
    return out


def inside_stone(verts, diam, w, ln):
    """Вершины металла глубже 1e-3 * W внутри камня. Знак по нормали ближайшей грани у острого угла камня
    (Triangle, Trillion) ошибается снаружи — кандидат подтверждается чётностью пересечений луча."""
    me = diam.data
    stone = BVHTree.FromPolygons([Vector((v.co.x * w, v.co.y * ln, v.co.z * w)) for v in me.vertices],
                                 [tuple(p.vertices) for p in me.polygons])
    ray = Vector((0.123, 0.456, 0.881)).normalized()

    def parity(p):
        hits, o = 0, p
        while True:
            loc = stone.ray_cast(o, ray, 100.0)[0]
            if loc is None:
                return hits % 2 == 1
            hits += 1
            o = loc + ray * 1e-6
    n = 0
    for v in verts:
        loc, nor = stone.find_nearest(v)[:2]
        n += (v - loc).dot(nor) < -1e-3 * w and parity(v)
    return n


def instances(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    return [i.object.original for i in dg.object_instances if i.is_instance and i.parent and i.parent.original == ob]


def outside(bvh, p):
    loc, nor = bvh.find_nearest(p)[:2]
    return (p - loc).dot(nor) > 0


def stack_defaults(ob, ss):
    for group, sockets in ss["SOCKETS"].items():
        for name, _t, default, _a, _b, panel, _s in sockets:
            if default is not None and name not in ("Width", "Length"):
                put(ob, group, (panel, name), default)
    put(ob, "My_Setting_Bool", ("Bool", "BoolObject"), None)
    put(ob, "My_Setting_Bool", ("Bool", "BoolCollection"), None)
    put(ob, "My_Stone_Prongs", (None, "Stones"), None)
    put(ob, "My_Stone_Cast", (None, "Stones"), None)
    put(ob, "My_Stone_Cast", (None, "Type"), "Wall")
    put(ob, "My_Stone_Prongs", (None, "Tip"), "Round")
    put(ob, "My_Stone_Cast", ("Basket", "Rail Shape"), "Round")
    # точные размеры конструкции (разделы 1-16) проверяются на острых рёбрах; скругление — разделы 17, 18
    put(ob, "My_Stone", ("Setting", "Edge Round"), 0.0)


def mono_defaults(ob, ns, group):
    for name, _t, default, _a, _b, panel, _s in ns["SOCKETS"]:
        if default is not None and name not in ("Width", "Length", "ø Stone"):
            put(ob, group, (panel, name), default)
    put(ob, group, ("Bool", "BoolObject"), None)
    put(ob, group, ("Bool", "BoolCollection"), None)


def row(tag, dist, note, closed, errors, ok_dist=True):
    ok, nsh = closed
    print("%-30s %.5f  %-24s %s (%d)" % (tag, dist, note, ok, nsh))
    if not ok_dist or dist > TOL:
        errors.append("%s: surface %.5f > %.3f" % (tag, dist, TOL))


# --- 1, 2: сравнение с монолитами ------------------------------------------------------------------

def compare_case(errors, tag, stack, ref, ref_group, set_on, bc, w, ln, diam):
    put(ref, ref_group, ("Bool", "BoolCutter"), bc)
    put(ref, ref_group, ("Prongs", "Set"), set_on)
    put(stack, "My_Setting_Bool", ("Bool", "BoolCutter"), bc)
    put(stack, "My_Stone", ("Setting", "Set"), set_on)
    a, r = evaluate(stack), evaluate(ref)
    closed = closed_outward(a[0], a[1])
    tag = "%s bc %s set %s" % (tag, "on " if bc else "off", "on " if set_on else "off")
    if set_on and not bc:
        dist = prong_dist(a, r, w)
        inside = inside_stone(a[0], diam, w, ln)
        row(tag, dist, "prongs only, in stone %d" % inside, closed, errors)
        if inside:
            errors.append("%s: %d metal vertices inside the stone" % (tag, inside))
    else:
        row(tag, surface_dist(a, r), "", closed, errors)
    if bc and closed != (True, 1):
        errors.append("%s: closed %s, %d shells" % (tag, closed[0], closed[1]))


def check_round(errors, ss, rns, diam, cutter):
    ref = rns["setup"]("Ref Round Cast", diam=diam, cutter=cutter)
    stack = ss["setup"]("Round", diam=diam, cutter=cutter)
    print("case                           surface  note                     closed (shells)")
    for D in ROUND_SIZES:
        stack_defaults(stack, ss)
        mono_defaults(ref, rns, "My_Round_Cast")
        put(stack, "My_Stone", ("Stone", "Width"), D)
        put(ref, "My_Round_Cast", ("Round", "ø Stone"), D)
        for bc in (True, False):
            for set_on in (False, True):
                compare_case(errors, "round %.1f" % D, stack, ref, "My_Round_Cast", set_on, bc, D, D, diam)
    for tag, sk, rk, value in (("round 2.0 count 6", ("My_Stone_Prongs", ("Prongs", "Count")), ("Prongs", "Count"), 6),
                               ("round 2.0 tilt 0.14", ("My_Stone", ("Setting", "Tilt")), ("Prongs", "Tilt"), 0.14)):
        stack_defaults(stack, ss)
        mono_defaults(ref, rns, "My_Round_Cast")
        put(stack, "My_Stone", ("Stone", "Width"), 2.0)
        put(ref, "My_Round_Cast", ("Round", "ø Stone"), 2.0)
        put(stack, sk[0], sk[1], value)
        put(ref, "My_Round_Cast", rk, value)
        for bc in (True, False):
            compare_case(errors, tag, stack, ref, "My_Round_Cast", False, bc, 2.0, 2.0, diam)
    stack_defaults(stack, ss)
    put(stack, "My_Stone", ("Stone", "Width"), 2.0)
    return stack


def check_emerald(errors, ss, gns):
    for w, ln in EMERALD_SIZES:
        ref = gns["setup"]("EMERALD", w, ln)
        mono_defaults(ref, gns, "My_Gem_Cast")
        stack = ss["setup"]("Emerald", w, ln, name="Emerald %gx%g Setting" % (w, ln))
        stack_defaults(stack, ss)
        put(stack, "My_Stone", ("Stone", "Width"), w)
        put(stack, "My_Stone", ("Stone", "Length"), ln)
        diam = get(stack, "My_Stone", (None, "Diam"))
        if diam != get(ref, "My_Gem_Cast", (None, "Diam")):
            errors.append("emerald: different unit stones")
        for bc in (True, False):
            for set_on in (False, True):
                compare_case(errors, "emerald %gx%g" % (w, ln), stack, ref, "My_Gem_Cast", set_on, bc, w, ln, diam)
        stack_defaults(stack, ss)
        mono_defaults(ref, gns, "My_Gem_Cast")


# --- 3: клетки -----------------------------------------------------------------------------------

def check_cages(errors, ss, obs, cube):
    for ob in obs:
        n = 4 if get(ob, "My_Stone", (None, "Cut")) == "Emerald" else get(ob, "My_Stone_Prongs", ("Prongs", "Count"))
        put(ob, "My_Stone", ("Setting", "Subdivision"), 0)
        put(ob, "My_Setting_Bool", ("Bool", "BoolCutter"), True)
        put(ob, "My_Setting_Bool", ("Bool", "BoolObject"), cube)     # булеанов в клетке быть не должно
        res = []
        for set_on, per in ((False, 12), (True, 16)):
            put(ob, "My_Stone", ("Setting", "Set"), set_on)
            verts, faces, _t, attrs = evaluate(ob)[:4]
            want = per * n + 32
            res.append("%d/%d" % (len(verts), want))
            if len(verts) != want or "crease_edge" not in attrs or len(shells(faces, len(verts))) != n + 1:
                errors.append("%s cage set %s: %d verts (want %d), crease_edge %s" % (
                    ob.name, set_on, len(verts), want, "crease_edge" in attrs))
        print("cage %-24s %s (set off, set on), crease_edge, no booleans" % (ob.name, " ".join(res)))
        stack_defaults(ob, ss)


# --- 4: камень ------------------------------------------------------------------------------------

def check_stone(errors, ss, ob, diam):
    stack_defaults(ob, ss)
    inst = instances(ob)
    ok = inst == [diam] and "gem" in diam
    print("stone instance: %s, gem %s" % ([o.name for o in inst], "gem" in diam))
    if not ok:
        errors.append("stone is not an instance of %s with 'gem': %s" % (diam.name, [o.name for o in inst]))
    for bc, set_on in ((True, False), (True, True), (False, True)):
        put(ob, "My_Setting_Bool", ("Bool", "BoolCutter"), bc)
        put(ob, "My_Stone", ("Setting", "Set"), set_on)
        put(ob, "My_Stone", (None, "ShowStone"), True)
        a = evaluate(ob)
        put(ob, "My_Stone", (None, "ShowStone"), False)
        b = evaluate(ob)
        gems = [o.name for o in instances(ob) if "gem" in o or o == diam]
        same = len(a[0]) == len(b[0]) and all((p - q).length < 1e-6 for p, q in zip(a[0], b[0]))
        print("ShowStone off, bc %-5s set %-5s: gem instances %s, metal same %s (%d verts)" % (
            bc, set_on, gems, same, len(b[0])))
        if gems or not same:
            errors.append("ShowStone off (bc %s, set %s): gems %s, metal same %s" % (bc, set_on, gems, same))
    # носитель: что даёт Realize Instances в конце стека
    ng = bpy.data.node_groups.new("Test Realize", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gin, gout = ng.nodes.new("NodeGroupInput"), ng.nodes.new("NodeGroupOutput")
    real = ng.nodes.new("GeometryNodeRealizeInstances")
    ng.links.new(gin.outputs[0], real.inputs[0])
    ng.links.new(real.outputs[0], gout.inputs[0])
    md = ob.modifiers.new("Test Realize", "NODES")
    md.node_group = ng
    put(ob, "My_Setting_Bool", ("Bool", "BoolCutter"), True)
    put(ob, "My_Stone", ("Setting", "Set"), False)
    for show in (True, False):
        put(ob, "My_Stone", (None, "ShowStone"), show)
        md.show_viewport = False
        base = evaluate(ob)[0]
        md.show_viewport = True
        verts = evaluate(ob)[0]
        extra = verts[len(base):]       # меш стека идёт первым, за ним — вершины инстансов
        ext = max((v - extra[0]).length for v in extra) if extra else 0.0
        print("realized at the end, ShowStone %-5s: +%d verts, spread %.6f" % (show, len(verts) - len(base), ext))
        if not show and ext > 1e-9:
            errors.append("zero-scale carrier: realized vertices spread %.6f" % ext)
    ob.modifiers.remove(md)
    bpy.data.node_groups.remove(ng)
    put(ob, "My_Stone", (None, "ShowStone"), True)
    stack_defaults(ob, ss)


def check_builtin(errors, ss, obs):
    """Diam пуст — встроенный камень огранки: инстанс и металл те же, что с этим объектом в Diam."""
    for ob, name in zip(obs, ("RWPRound", "Unit Emerald")):
        stack_defaults(ob, ss)
        was, stone = get(ob, "My_Stone", (None, "Diam")), bpy.data.objects[name]
        put(ob, "My_Stone", (None, "Diam"), stone)
        a = evaluate(ob)[0]
        put(ob, "My_Stone", (None, "Diam"), None)
        b = evaluate(ob)[0]
        inst = instances(ob)
        same = len(a) == len(b) and all((p - q).length < 1e-6 for p, q in zip(a, b))
        print("Diam empty, Cut %s: instance %s, metal same %s (%d verts)" % (
            get(ob, "My_Stone", (None, "Cut")), [o.name for o in inst], same, len(b)))
        if inst != [stone] or not same or not b:
            errors.append("Diam empty (%s): instance %s, metal same %s, %d verts" % (
                ob.name, [o.name for o in inst], same, len(b)))
        put(ob, "My_Stone", (None, "Diam"), was)


def check_material(errors, ss, obs):
    """Stone Material: пуст — камень остаётся инстансом Diam; задан — материал на камне, металл тот же."""
    mat = bpy.data.materials.get("Test Ruby") or bpy.data.materials.new("Test Ruby")
    key = ("Stone", "Stone Material")
    for ob in obs:
        stack_defaults(ob, ss)
        put(ob, "My_Stone", key, None)
        diam = get(ob, "My_Stone", (None, "Diam"))
        a, inst = evaluate(ob)[0], instances(ob)
        put(ob, "My_Stone", key, mat)
        b = evaluate(ob)[0]
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        mats = sorted({m.name for i in dg.object_instances if i.is_instance and i.parent and i.parent.original == ob
                       for m in i.object.data.materials if m})
        same = len(a) == len(b) and all((p - q).length < 1e-6 for p, q in zip(a, b))
        print("Stone Material, %s: empty -> instance %s; set -> stone materials %s, metal same %s" % (
            ob.name, [o.name for o in inst], mats, same))
        if inst != [diam] or mats != [mat.name] or not same:
            errors.append("Stone Material (%s): instance %s, materials %s, metal same %s" % (
                ob.name, [o.name for o in inst], mats, same))
        put(ob, "My_Stone", key, None)


# --- 5: общий булеан ------------------------------------------------------------------------------

def check_bools(errors, ss, ob, diam):
    stack_defaults(ob, ss)
    w = get(ob, "My_Stone", ("Stone", "Width"))
    z = get(ob, "My_Stone_Cast", ("Cast", "Z Offset")) - 0.1
    mid = w / 2 + get(ob, "My_Stone_Cast", ("Cast", "XY Offset")) - get(ob, "My_Stone_Cast", ("Cast", "Cast Thickness")) / 2

    def cube(name, loc, size, coll):
        me = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bm.to_mesh(me)
        bm.free()
        o = bpy.data.objects.new(name, me)
        coll.objects.link(o)
        o.location, o.scale = loc, size
        return o
    scene = bpy.context.scene.collection
    obj = cube("Bool A", (mid, 0.0, z), (1.0, 0.6, 0.3), scene)
    coll = bpy.data.collections.new("Bool Set")
    scene.children.link(coll)
    cube("Bool B", (-mid, 0.15, z), (1.0, 0.4, 0.3), coll)
    cube("Bool C", (-mid, -0.15, z), (1.0, 0.4, 0.3), coll)     # пересекается с B
    # пробы — в стенке каста вдали от крапанов (у Round они на 45°): при перекрытых оболочках
    # (BoolCutter выкл) ближайшая грань у пробы рядом с крапаном — крапан, и «внутри» не распознать
    probes = [Vector((mid, 0.0, z)), Vector((-mid, 0.25, z)), Vector((-mid, -0.25, z))]
    for bc in (False, True):
        put(ob, "My_Setting_Bool", ("Bool", "BoolCutter"), bc)
        put(ob, "My_Setting_Bool", ("Bool", "BoolObject"), None)
        put(ob, "My_Setting_Bool", ("Bool", "BoolCollection"), None)
        before = BVHTree.FromPolygons(*evaluate(ob)[:2])
        put(ob, "My_Setting_Bool", ("Bool", "BoolObject"), obj)
        put(ob, "My_Setting_Bool", ("Bool", "BoolCollection"), coll)
        v, f = evaluate(ob)[:2]
        after = BVHTree.FromPolygons(v, f)
        was = [not outside(before, p) for p in probes]
        cut = [outside(after, p) for p in probes]
        ok, nsh = closed_outward(v, f)
        inst = instances(ob)
        print("bool BoolCutter %-5s: metal before %s, cut %s, closed %s (%d), stone %s" % (
            bc, was, cut, ok, nsh, [o.name for o in inst]))
        if not all(was) or not all(cut) or not ok or inst != [diam]:
            errors.append("bool BoolCutter %s: before %s cut %s closed %s stone %s" % (bc, was, cut, ok, inst))
    stack_defaults(ob, ss)
    return obj, coll


# --- 6: Stones ------------------------------------------------------------------------------------

def check_stones(errors, ss, groups, src, label, set_on):
    stack_defaults(src, ss)
    put(src, "My_Stone", ("Setting", "Set"), set_on)
    src.matrix_world = Matrix.LocRotScale(Vector((-1.0, 2.0, 0.5)), Euler((0.1, 0.0, 0.4)), None)
    bool_md = mod(src, "My_Setting_Bool")
    bool_md.show_viewport = False
    probe = bpy.data.objects.new("Stones Probe", bpy.data.meshes.new("Stones Probe"))
    bpy.context.scene.collection.objects.link(probe)
    probe.matrix_world = Matrix.LocRotScale(Vector((3.0, -2.0, 1.0)), Euler((0.3, 0.2, 0.7)), None)
    for g in ("My_Stone_Prongs", "My_Stone_Cast"):
        md = probe.modifiers.new(g, "NODES")
        md.node_group = groups[g]
        getattr(md.properties.inputs, keys(md)[(None, "Stones")]).value = src
    a, b = evaluate(src, world=True), evaluate(probe, world=True)
    dist = surface_dist(a, b)
    print("Stones %-23s %.5f  (%d / %d verts, world space)" % (label, dist, len(a[0]), len(b[0])))
    if dist > TOL or len(a[0]) != len(b[0]):
        errors.append("Stones %s: %.5f, verts %d / %d" % (label, dist, len(a[0]), len(b[0])))
    bpy.data.objects.remove(probe)
    bool_md.show_viewport = True
    src.matrix_world = Matrix.Identity(4)
    stack_defaults(src, ss)


# --- 7: пересборка --------------------------------------------------------------------------------

def check_rebuild(errors, ss, obs, cutter, coll):
    changes = [("My_Stone", ("Setting", "Tilt"), 0.1), ("My_Stone", ("Setting", "Below Culet"), 0.33),
               ("My_Stone", ("Setting", "Subdivision"), 3), ("My_Stone", ("Setting", "Set"), True),
               ("My_Stone", (None, "ShowStone"), False), ("My_Stone_Prongs", ("Prongs", "Count"), 5),
               ("My_Stone_Prongs", ("Prongs", "ø"), 0.6), ("My_Stone_Prongs", ("Prongs", "Smooth"), False),
               ("My_Stone_Cast", ("Cast", "Z Offset"), -0.2), ("My_Stone_Cast", ("Cast", "CastBool"), False),
               ("My_Setting_Bool", (None, "Realize All"), True), ("My_Setting_Bool", ("Bool", "BoolCutter"), False),
               ("My_Setting_Bool", ("Bool", "BoolCollection"), coll), ("My_Stone_Cast", (None, "Type"), "Basket"),
               ("My_Stone_Prongs", (None, "Tip"), "Claw"), ("My_Stone_Cast", ("Basket", "Rail Shape"), "Flat")]
    for ob in obs:
        for g, k, v in changes:
            put(ob, g, k, v)
    before = {ob.name: values(ob) for ob in obs}
    ss["build_all"]()
    after = {ob.name: values(ob) for ob in obs}
    changed = [(n, k) for n in before for k in before[n] if before[n][k] != after[n].get(k)]
    cuts = ([get(ob, "My_Stone", (None, "Cut")) for ob in obs] + [get(ob, "My_Stone_Cast", (None, "Type")) for ob in obs]
            + [get(ob, "My_Stone_Prongs", (None, "Tip")) for ob in obs]
            + [get(ob, "My_Stone_Cast", ("Basket", "Rail Shape")) for ob in obs])
    # setup на существующем объекте без размеров тоже ничего не меняет
    ss["setup"]("Emerald", name=obs[1].name)
    again = [k for k in after[obs[1].name] if after[obs[1].name][k] != values(obs[1]).get(k)]
    print("rebuild: %d values, changed %s, Cut + Type + Tip + Rail Shape %s; setup again changed %s" % (
        sum(len(v) for v in before.values()), changed, cuts, again))
    if changed or again or cuts != ["Round", "Emerald", "Basket", "Basket", "Claw", "Claw", "Flat", "Flat"]:
        errors.append("rebuild changed %s, Cut + Type + Tip + Rail Shape %s, setup again changed %s" % (
            changed, cuts, again))
    for ob in obs:
        stack_defaults(ob, ss)


# --- глухой каст (Bezel) --------------------------------------------------------------------------

def girdle_outline(stone, w, ln):
    """Настоящий контур рундиста: граница граней, смотрящих вверх (как в test_gem_cast.py), против
    часовой. -> [(x, y)], высота верха рундиста."""
    me = stone.data
    uses = {}
    for p in me.polygons:
        if p.normal.z > 1e-3:
            for k in p.edge_keys:
                uses[k] = uses.get(k, 0) + 1
    links = {}
    for (a, b), c in uses.items():
        if c == 1:
            links.setdefault(a, []).append(b)
            links.setdefault(b, []).append(a)
    start = min(links)
    order, prev, cur = [start], None, start
    while True:
        cur, prev = next(v for v in links[cur] if v != prev), cur
        if cur == start:
            break
        order.append(cur)
    pts = [(me.vertices[i].co.x * w, me.vertices[i].co.y * ln) for i in order]
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))
    return (pts if area > 0 else pts[::-1]), max(me.vertices[i].co.z for i in order) * w


def signed_distance(p, outline):
    """Расстояние до контура, снаружи — плюс."""
    best = 1e9
    for i in range(len(outline)):
        (ax, ay), (bx, by) = outline[i], outline[(i + 1) % len(outline)]
        vx, vy = bx - ax, by - ay
        t = min(1.0, max(0.0, ((p[0] - ax) * vx + (p[1] - ay) * vy) / (vx * vx + vy * vy)))
        best = min(best, ((p[0] - ax - vx * t) ** 2 + (p[1] - ay - vy * t) ** 2) ** 0.5)
    inside = False
    for k in range(len(outline)):
        (x1, y1), (x2, y2) = outline[k - 1], outline[k]
        if (y1 > p[1]) != (y2 > p[1]) and p[0] < x1 + (p[1] - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return -best if inside else best


def bezel_case(errors, ss, ob, cut, w, ln, diam, set_on, cube):
    """Одна строка таблицы глухого каста. Стек My_Stone -> My_Stone_Cast (Bezel), крапанов нет."""
    from math import tan
    bool_md = mod(ob, "My_Setting_Bool")
    stack_defaults(ob, ss)
    put(ob, "My_Stone_Cast", (None, "Type"), "Bezel")
    put(ob, "My_Stone", ("Setting", "Set"), set_on)
    g = lambda k: get(ob, "My_Stone_Cast", ("Bezel", k))
    wall, seat, cover = g("Wall"), g("Seat"), g("Bezel Cover") / 100.0
    me = diam.data
    zmax = max(v.co.z for v in me.vertices)
    table = [v.co for v in me.vertices if v.co.z >= zmax * 0.999]
    edge = max(abs(v.x) for v in table) if cut == "Emerald" else max(v.xy.length for v in table)
    h, c = zmax * w, w * (0.5 - edge)
    zt, cov, clr = g("Height") / 100.0 * h, cover * c, ss["BEZEL_CLEAR"] * w
    outline, zg = girdle_outline(diam, w, ln)
    tag = "bezel %s %s set %s" % (cut.lower(), ("%g" % w) if cut == "Round" else "%gx%g" % (w, ln),
                                  "on " if set_on else "off")
    bad = []

    # 1. замкнуто, одна оболочка; клетка 56, булеанов нет (с Bool и BoolObject)
    bool_md.show_viewport = False
    m = evaluate(ob)
    verts = m[0]
    closed = closed_outward(verts, m[1])
    put(ob, "My_Stone", ("Setting", "Subdivision"), 0)
    bool_md.show_viewport = True
    put(ob, "My_Setting_Bool", ("Bool", "BoolObject"), cube)
    cage = len(evaluate(ob)[0])
    put(ob, "My_Setting_Bool", ("Bool", "BoolObject"), None)
    bool_md.show_viewport = False
    put(ob, "My_Stone", ("Setting", "Subdivision"), 2)
    if closed != (True, 1) or cage != 56:
        bad.append("closed %s (%d), cage %d" % (closed[0], closed[1], cage))
    # 2. верх: zt (без Set — у края расточки, ниже на clr tan β)
    top = max(v.z for v in verts) - (zt - (0.0 if set_on else clr * tan(ss["BEZEL_BEVEL"])))
    if abs(top) > 0.02:
        bad.append("top %+.4f" % top)
    # 3. наружная стенка в плоскости рундиста — на Wall от настоящего контура. Round — по вершинам
    # петли z = 0 (они на предельной поверхности; лучом между ними мерилась бы хорда 32-угольника
    # Subdivision 2: r (1 - cos π/32) = 0.48 % радиуса, у ø 6.5 это 0.018 мм). Emerald — грани плоские,
    # лучи по нормалям из середин сторон контура.
    bvh = BVHTree.FromPolygons(verts, m[5])
    wall_err = 0.0
    if cut == "Round":
        for v in verts:
            if abs(v.z) < 1e-5:
                sd = signed_distance(v.xy, outline)
                if sd > wall / 2:
                    wall_err = max(wall_err, sd - wall, key=abs)
    else:
        for (ax, ay), (bx, by) in zip(outline, outline[1:] + outline[:1]):
            n = Vector((by - ay, ax - bx, 0.0)).normalized()
            o = Vector(((ax + bx) / 2, (ay + by) / 2, 0.001)) + n * 5.0
            hit = bvh.ray_cast(o, -n, 100.0)[0]
            wall_err = max(wall_err, (signed_distance(hit.xy, outline) - wall) if hit else 9.0, key=abs)
    if abs(wall_err) > 0.01:
        bad.append("wall %+.4f" % wall_err)
    # 4. металл не в камне; без Set камень вставляется сверху; Set — губа на cov, зазор до короны
    in_stone = inside_stone(verts, diam, w, ln)
    note = ""
    if not set_on:
        drop = sum(1 for v in verts if v.z > 1e-4 and signed_distance(v.xy, outline) < -1e-4)
        note = "drop-in blocked %d" % drop
        if drop:
            bad.append("metal above girdle inside outline: %d verts" % drop)
    else:
        lip = [v for v in verts if v.z > zg + 0.005]
        if cut == "Round":
            inner = w / 2 - min(v.xy.length for v in lip)
        else:
            cy = 0.5 - max(abs(v.co.y) for v in me.vertices if abs(v.co.x) >= 0.5 - 1e-4)
            inner = w / 2 - min(abs(v.x) for v in lip if abs(v.y) < ln * (0.5 - cy))
        stone = BVHTree.FromPolygons([Vector((v.co.x * w, v.co.y * ln, v.co.z * w)) for v in me.vertices],
                                     [tuple(p.vertices) for p in me.polygons])
        over = [v for v in lip if signed_distance(v.xy, outline) < 0]
        gap = min((v - stone.find_nearest(v)[0]).length for v in over)
        note = "lip %.4f/%.4f gap %.4f" % (inner, cov, gap)
        if abs(inner - cov) > 0.03 * c or gap > 0.02 * w:
            bad.append("lip %.4f (cov %.4f), gap %.4f" % (inner, cov, gap))
    if in_stone:
        bad.append("%d metal verts inside the stone" % in_stone)
    # 5. опора: проба под посадкой (камень * grow по XY) на Seat/2 внутри контура — металл; ось — нет
    grow = ss["mods"]()[1].SET_GROW if set_on else ss["mods"]()[2].CUTTER_GROW
    stone_b = BVHTree.FromPolygons([Vector((v.co.x * w, v.co.y * ln, v.co.z * w)) for v in me.vertices],
                                   [tuple(p.vertices) for p in me.polygons])
    q = Vector((w / 2 - seat / 2, 0.0, 0.0))
    pav = stone_b.ray_cast(Vector((q.x / grow, 0.0, -50.0)), Vector((0, 0, 1)), 100.0)[0].z
    bearing = not outside(bvh, Vector((q.x, 0.0, pav - 0.02)))
    axis = not outside(bvh, Vector((0.0, 0.0, min(v.co.z for v in me.vertices) * w / 2)))
    if not bearing or axis:
        bad.append("bearing %s, metal on axis %s" % (bearing, axis))
    # 6. + My_Setting_Bool (BoolCutter): та же поверхность, замкнуто; BoolObject режет; камень — инстанс
    bool_md.show_viewport = True
    put(ob, "My_Setting_Bool", ("Bool", "BoolCutter"), True)
    mb = evaluate(ob)
    dist = surface_dist(m, mb)
    closed_b = closed_outward(mb[0], mb[1])
    # куб на наружной стенке (целиком внутри металла он оставил бы полость), проба — в металле под ним
    cube.location = (w / 2 + wall, 0.0, -0.1)
    probe = Vector((w / 2 + wall - 0.05, 0.0, -0.1))
    before = not outside(BVHTree.FromPolygons(mb[0], mb[5]), probe)
    put(ob, "My_Setting_Bool", ("Bool", "BoolObject"), cube)
    mc = evaluate(ob)
    cut_ok = before and outside(BVHTree.FromPolygons(mc[0], mc[5]), probe) and closed_outward(mc[0], mc[1])[0]
    inst = instances(ob)
    put(ob, "My_Setting_Bool", ("Bool", "BoolObject"), None)
    bool_md.show_viewport = False
    if dist > 0.001 or closed_b != (True, 1) or not cut_ok or inst != [diam]:
        bad.append("with Bool: %.5f, closed %s (%d), cube cut %s, stone %s" % (
            dist, closed_b[0], closed_b[1], cut_ok, [o.name for o in inst]))
    print("%-26s %s(%d) %2d  %+.4f %+.4f  %d   %-28s %-5s %-5s %.5f %s(%d) %s" % (
        tag, closed[0], closed[1], cage, top, wall_err, in_stone, note, bearing, axis, dist, closed_b[0],
        closed_b[1], cut_ok))
    errors.extend("%s: %s" % (tag, e) for e in bad)
    stack_defaults(ob, ss)


def check_bezel(errors, ss, gns_unit):
    """Глухой каст на отдельных объектах: Round 2 и 6.5 (RWPRound), Emerald 4 x 6 и 7 x 10."""
    rwp = bpy.data.objects["RWPRound"]
    cube = bpy.data.objects.new("Bezel Bool Cube", bpy.data.meshes.new("Bezel Bool Cube"))
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=0.2)
    bm.to_mesh(cube.data)
    bm.free()
    bpy.context.scene.collection.objects.link(cube)
    obs = []
    print("bezel case                 closed cage top     wall     inStone note                   "
          "  bear  axis  +Bool   closed cube")
    for cut, w, ln, diam in (("Round", 2.0, 2.0, rwp), ("Round", 6.5, 6.5, rwp),
                             ("Emerald", 4.0, 6.0, gns_unit), ("Emerald", 7.0, 10.0, gns_unit)):
        name = "Bezel %s %gx%g" % (cut, w, ln)
        ob = ss["setup"](cut, w, ln, diam=diam, name=name, cast_type="Bezel")
        mod(ob, "My_Stone_Prongs").show_viewport = False
        for set_on in (False, True):
            bezel_case(errors, ss, ob, cut, w, ln, diam, set_on, cube)
        mod(ob, "My_Setting_Bool").show_viewport = True
        obs.append(ob)
    return obs


# --- крапан-коготь (Tip = Claw) -------------------------------------------------------------------

CLAW_CASES = (("Round", 2.0, 2.0, 0.5), ("Round", 3.0, 3.0, 0.6), ("Round", 6.5, 6.5, 0.9),
              ("Emerald", 4.0, 6.0, 0.5), ("Emerald", 7.0, 10.0, 0.5))   # ø — как в test_round_cast / разделе 2


def prong_sites(cut, w, ln, unit, count):
    """Места крапанов в плоскости рундиста: (точка контура, наружная нормаль) — как в My_Stone_Prongs."""
    if cut == "Round":
        out = []
        for k in range(count):
            a = pi / 4 + 2 * pi * k / count
            n = Vector((cos(a), sin(a), 0.0))
            out.append((n * w / 2, n))
        return out
    me = unit.data
    cx = w * (0.5 - max(abs(v.co.x) for v in me.vertices if abs(v.co.y) >= 0.5 - 1e-4))
    cy = ln * (0.5 - max(abs(v.co.y) for v in me.vertices if abs(v.co.x) >= 0.5 - 1e-4))
    out = []
    for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
        out.append((Vector((sx * (w / 2 - cx / 2), sy * (ln / 2 - cy / 2), 0.0)),
                    Vector((sx * cy, sy * cx, 0.0)).normalized()))
    return out


def claw_case(errors, ss, ob, cut, w, ln, dia, set_on, unit):
    tag = "claw %s %s set %s" % (cut.lower(), ("%g" % w) if cut == "Round" else "%gx%g" % (w, ln),
                                 "on " if set_on else "off")
    put(ob, "My_Stone", ("Setting", "Set"), set_on)
    gp = lambda k: get(ob, "My_Stone_Prongs", ("Prongs", k))
    me = unit.data
    zmax = max(v.co.z for v in me.vertices)
    table = [v.co for v in me.vertices if v.co.z >= zmax * 0.999]
    edge = max(abs(v.x) for v in table) if cut == "Emerald" else max(v.xy.length for v in table)
    h, c = zmax * w, w * (0.5 - edge)
    cov = max(gp("Set Cover") / 100.0, 0.05)
    m = evaluate(ob)
    verts = m[0]
    closed = closed_outward(verts, m[1])
    bad = []
    if closed != (True, 1):
        bad.append("closed %s, %d shells" % closed)
    # клетка: 16 вершин на крапан + 32 стенки
    put(ob, "My_Stone", ("Setting", "Subdivision"), 0)
    cage = len(evaluate(ob)[0])
    put(ob, "My_Stone", ("Setting", "Subdivision"), 2)
    want = 16 * 4 + 32
    if cage != want:
        bad.append("cage %d, want %d" % (cage, want))
    sites = prong_sites(cut, w, ln, unit, 4)
    keep = 0.5 - gp("Intersection") / 100.0
    tilt = get(ob, "My_Stone", ("Setting", "Tilt"))
    bvh = BVHTree.FromPolygons(verts, m[5])
    # вершины крапанов выше рундиста (верх стенки ниже него) по ближайшему месту: (u к камню, t вбок)
    above = [v for v in verts if v.z > 0.01]
    per = [[] for _ in sites]
    for v in above:
        k = min(range(len(sites)), key=lambda i: (v.xy - sites[i][0].xy).length)
        o, n = sites[k]
        per[k].append((-(v - o).dot(n), (v - o).dot(Vector((-n.y, n.x, 0.0))), v))
    if not set_on:
        target = h + gp("Above Table") + gp("Claw Length") * dia
        top = max(v.z for v in verts) - target
        # ствол у рундиста: ширина вбок (поперёк радиуса) на высоте 0.02 через ось крапана. По радиусу не
        # мерить: изнутри ствол срезан посадкой (Intersection — крапан заходит на камень)
        o, n = sites[0]
        t = Vector((-n.y, n.x, 0.0))
        ax = o + n * (dia * keep + 0.02 * tan(tilt)) + Vector((0, 0, 0.02))
        a = bvh.ray_cast(ax + t * 2 * dia, -t, 9.0)[0]
        b_ = bvh.ray_cast(ax - t * 2 * dia, t, 9.0)[0]
        stem = ((a - b_).length / dia - 1.0) if a and b_ else 9.0
        note = "top %+.4f (-%.3f..+0.02) stem %+.1f%%" % (top, 0.25 * dia, stem * 100)
        if not -0.25 * dia <= top <= 0.02:
            bad.append("top %+.4f outside [-%.3f, +0.02]" % (top, 0.25 * dia))
        if abs(stem) > 0.03:
            bad.append("stem width %+.1f%%" % (stem * 100))
    else:
        inside = inside_stone(verts, unit, w, ln)
        # Set Height — верх сглаженного крюка: доля от Set Height h
        top = max(v.z for v in above) / (gp("Set Height") / 100.0 * h)
        stone = BVHTree.FromPolygons([Vector((v.co.x * w, v.co.y * ln, v.co.z * w)) for v in me.vertices],
                                     [tuple(p.vertices) for p in me.polygons])
        reach, tipw, knw, contact = 9.0, 0.0, 9.0, 0.0
        for pts in per:
            far = max(u for u, _t, _v in pts)
            reach = min(reach, far / c)
            last = [t_ for u, t_, _v in pts if u >= 0.75 * far]
            tipw = max(tipw, max(last) - min(last))
            # плечо — крюк снаружи от рундиста (u <= 0): там он шириной со ствол
            knee = [t_ for u, t_, _v in pts if u <= 0.0]
            knw = min(knw, (max(knee) - min(knee)) if knee else 0.0)
            inner = max(pts, key=lambda q: q[0])[2]
            contact = max(contact, (inner - stone.find_nearest(inner)[0]).length)
        # без раструба: выше рундиста ни одна вершина крапана не дальше наружной поверхности ствола на той
        # же высоте (ствол — прямая под Tilt через замер лучом снаружи у рундиста)
        flare = -9.0
        for (o, n), pts in zip(sites, per):
            ax = o + n * (dia * keep + 0.02 * tan(tilt)) + Vector((0, 0, 0.02))
            hit = bvh.ray_cast(ax + n * 2 * dia, -n, 9.0)[0]
            s0 = (hit - o).dot(n)
            flare = max(flare, max((v - o).dot(n) - (s0 + (v.z - 0.02) * tan(tilt)) for _u, _t, v in pts))
        note = "in stone %d top %.2f·SH reach %.3f (cov %.2f) tip %.2fø shoulder %.2fø contact %.4f flare %+.4f" % (
            inside, top, reach, cov, tipw / dia, knw / dia, contact, flare)
        if inside:
            bad.append("%d metal verts inside the stone" % inside)
        if not 0.95 <= top <= 1.05:
            bad.append("top %.2f of Set Height outside [0.95, 1.05]" % top)
        # рез оболочкой камня (она больше камня на SET_GROW по XY) укорачивает заход на 0.01-0.02 мм
        if cut == "Round" and not cov - 0.04 <= reach <= cov + 0.02:
            bad.append("reach %.3f outside [%.2f, %.2f]" % (reach, cov - 0.04, cov + 0.02))
        if flare > 0.02:
            bad.append("flare %+.4f beyond the stem" % flare)
        if tipw > 0.5 * dia or knw < 0.8 * dia:
            bad.append("tip width %.2fø, shoulder %.2fø" % (tipw / dia, knw / dia))
        if contact > 0.05:
            bad.append("contact %.4f" % contact)
    print("%-24s %s(%d) %3d  %s" % (tag, closed[0], closed[1], cage, note))
    errors.extend("%s: %s" % (tag, e) for e in bad)


def check_claw(errors, ss, cutter, unit_em):
    """Полный стек, Tip = Claw: Round 2 / 3 / 6.5, Emerald 4 x 6 / 7 x 10, Set выкл и вкл."""
    rwp = bpy.data.objects["RWPRound"]
    print("claw case                closed cage  checks")
    obs = {}
    for cut, w, ln, dia in CLAW_CASES:
        unit = rwp if cut == "Round" else unit_em
        ob = ss["setup"](cut, w, ln, diam=unit, cutter=cutter if cut == "Round" else None,
                         name="Claw %s %gx%g" % (cut, w, ln))
        stack_defaults(ob, ss)
        put(ob, "My_Stone_Prongs", ("Prongs", "ø"), dia)
        before = evaluate(ob)[0]
        put(ob, "My_Stone_Prongs", (None, "Tip"), "Claw")
        for set_on in (False, True):
            claw_case(errors, ss, ob, cut, w, ln, dia, set_on, unit)
        # обратно Round — те же вершины
        put(ob, "My_Stone", ("Setting", "Set"), False)
        put(ob, "My_Stone_Prongs", (None, "Tip"), "Round")
        after = evaluate(ob)[0]
        same = len(before) == len(after) and all((p - q).length < 1e-6 for p, q in zip(before, after))
        if not same:
            errors.append("claw %s %gx%g: Tip back to Round changes vertices (%d -> %d)" % (
                cut.lower(), w, ln, len(before), len(after)))
        obs[(cut, w)] = (ob, unit, w, ln, dia)
    print("Tip back to Round: same vertices in all cases %s" % (not any("Tip back" in e for e in errors)))
    return obs


def render_claw_sheet(ss, obs):
    """Коготь: Round 6.5 и Emerald 7 x 10, без Set и с Set; ряды — вид 3/4 и вид сверху."""
    cells = []
    col = 0
    for key in (("Round", 6.5), ("Emerald", 7.0)):
        ob, unit, w, ln, dia = obs[key]
        put(ob, "My_Stone_Prongs", (None, "Tip"), "Claw")
        for set_on in (False, True):
            put(ob, "My_Stone", ("Setting", "Set"), set_on)
            me = freeze(ob)
            for rw in (0, 1):
                cells.append((col, rw, label(ob, w, ln, set_on) + (", top" if rw else ""), me, unit.data, w, ln,
                              "top" if rw else None))
            col += 1
        put(ob, "My_Stone", ("Setting", "Set"), False)
        put(ob, "My_Stone_Prongs", (None, "Tip"), "Round")
    render_cells(PREVIEW_CLAW, "My_Stone_Prongs: Tip = Claw", cells, (1800, 0))


# --- корзинка (Type = Basket) ---------------------------------------------------------------------

SEAT_GAP = 0.1      # мм: павильон над поверхностью посадки на верхнем ранте не выше
BASKET_CASES = (("Round", 3.0, 3.0, 0.6), ("Round", 6.5, 6.5, 0.9), ("Emerald", 7.0, 10.0, 0.5))


def basket_case(errors, ss, ob, cut, w, ln, unit, shape, set_on, tag):
    put(ob, "My_Stone_Cast", ("Basket", "Rail Shape"), shape)
    put(ob, "My_Stone", ("Setting", "Set"), set_on)
    gc_ = lambda k: get(ob, "My_Stone_Cast", ("Cast", k))
    z_t, xy, t = gc_("Z Offset"), gc_("XY Offset"), gc_("Cast Thickness")
    tilt = get(ob, "My_Stone", ("Setting", "Tilt"))
    below = get(ob, "My_Stone", ("Setting", "Below Culet"))
    me = unit.data
    culet = min(v.co.z for v in me.vertices) * w
    z_b = culet - below
    rail = min(get(ob, "My_Stone_Cast", ("Basket", "Rail")), max(z_t - z_b, ss["mods"]()[1].MIN_CAST))
    d_out = lambda z: xy + z * tan(tilt)
    bad = []
    m = evaluate(ob)
    verts = m[0]
    closed = closed_outward(verts, m[1])
    if closed != (True, 1):
        bad.append("closed %s, %d shells" % closed)
    # клетка каста: крапана выключены, Bool в режиме клетки пропускает всё
    prongs_md, bool_md = mod(ob, "My_Stone_Prongs"), mod(ob, "My_Setting_Bool")
    prongs_md.show_viewport = False
    put(ob, "My_Stone", ("Setting", "Subdivision"), 0)
    cage = len(evaluate(ob)[0])
    put(ob, "My_Stone", ("Setting", "Subdivision"), 2)
    # размеры рантов — на самих рантах (без крапанов и My_Setting_Bool): у Emerald посадка срезает
    # наружный край верха верхнего ранта по всей длине, места «вне посадки» на нём нет
    bool_md.show_viewport = False
    raw = evaluate(ob)
    bool_md.show_viewport = True
    prongs_md.show_viewport = True
    if cage != 64:
        bad.append("cast cage %d, want 64" % cage)
    rv = raw[0]
    bvh_r = BVHTree.FromPolygons(rv, raw[5])
    edge_x = w / 2                                   # Round — по +X между крапанами, Emerald — середина длинной стороны
    P = lambda d, z: Vector((edge_x + d, 0.0, z))
    X, Z = Vector((1, 0, 0)), Vector((0, 0, 1))
    hit = lambda o, dv: bvh_r.ray_cast(o, dv, 50.0)[0]
    z_gap = (z_t - rail + z_b + rail) / 2
    if shape == "Flat":
        zc = z_b + rail / 2
        d_o = hit(P(d_out(zc) + 2.0, zc), -X).x - edge_x
        d_i = hit(P(-2.0, zc), X).x - edge_x
        up_o = hit(P(d_out(z_t - rail / 2) + 2.0, z_t - rail / 2), -X).x - edge_x
        top = hit(P(d_out(z_t) - 0.5 * t, z_t + 1.0), -Z).z
        ubot = hit(P(d_out(z_t - rail) - 0.5 * t, z_gap), Z).z
        bot = hit(P(d_out(z_b) - 0.5 * t, z_b - 1.0), Z).z
        res = {"top": top - z_t, "bottom": bot - z_b, "height": (top - ubot) - rail, "thick": (d_o - d_i) - t,
               "outer": max(d_o - d_out(zc), up_o - d_out(z_t - rail / 2), key=abs)}
        note = " ".join("%s %+.4f" % (k, v) for k, v in res.items())
        bad += ["%s %+.4f" % (k, v) for k, v in res.items() if abs(v) > 0.002]
    else:
        # вершины предела в столбце y = 0 (лучом мерилась бы грань Subdivision 2 у сдвинутой наклоном вершины)
        res = []
        for lower in (True, False):
            col = [v for v in rv if abs(v.y) < 1e-4 and v.x > 0 and (v.z < z_gap) == lower]
            zc = (max(v.z for v in col) + min(v.z for v in col)) / 2
            res.append(((max(v.x for v in col) - min(v.x for v in col)) / t - 1.0,
                        (max(v.z for v in col) - min(v.z for v in col)) / rail - 1.0,
                        max(v.x for v in col) - edge_x - d_out(zc)))
        width, height = max((r[0] for r in res), key=abs), max((r[1] for r in res), key=abs)
        outer = max((r[2] for r in res), key=abs)
        note = "width %+.1f%% height %+.1f%% outer %+.4f" % (width * 100, height * 100, outer)
        if abs(width) > 0.02 or abs(height) > 0.02:
            bad.append("section width %+.1f%%, height %+.1f%%" % (width * 100, height * 100))
        if abs(outer) > 0.01:
            bad.append("outer %+.4f" % outer)
    # сверху не видно: вершины рантов не дальше 0.01 за контуром рундиста
    outline, _zg = girdle_outline(unit, w, ln)
    out_max = max(signed_distance(v.xy, outline) for v in rv)
    if xy <= 0 and out_max > 0.01:
        bad.append("rail outside the girdle by %.4f" % out_max)
    gap = (z_t - rail) - (z_b + rail)
    culet_up = culet - (z_b + rail)
    if (w, ln) in ((6.5, 6.5), (7.0, 10.0)) and gap < 0.4:
        bad.append("gap between rails %.3f < 0.4" % gap)
    if culet_up < 0:
        bad.append("culet below the lower rail top by %.3f" % -culet_up)
    # камень: металл не в камне; павильон лежит на верхнем ранте — луч вниз под павильоном у внутренней
    # части ранта: первая поверхность металла (посадка) — на верхнем ранте, зазор до павильона — печать
    inside = inside_stone(verts, unit, w, ln)
    bvh = BVHTree.FromPolygons(verts, m[5])
    stone = BVHTree.FromPolygons([Vector((v.co.x * w, v.co.y * ln, v.co.z * w)) for v in me.vertices],
                                 [tuple(p.vertices) for p in me.polygons])
    dp = d_out(z_t) - 0.75 * t
    pav = stone.ray_cast(P(dp, -50.0), Z, 100.0)[0].z
    seat = bvh.ray_cast(P(dp, pav - 1e-4), -Z, 50.0)[0]
    seat_gap = pav - seat.z if seat else 9.0
    bearing = seat is not None and z_t - rail - 1e-4 <= seat.z <= z_t + 1e-4 and seat_gap <= SEAT_GAP
    axis = not outside(bvh, Vector((0.0, 0.0, culet / 2)))
    if inside or not bearing or axis:
        bad.append("in stone %d, seat on the upper rail %s (gap %.4f), metal on axis %s" % (
            inside, bearing, seat_gap, axis))
    print("%-34s %s(%d) %2d  %-58s out %+.3f gap %.3f culet %+.3f in %d seat %.3f %s" % (
        tag, closed[0], closed[1], cage, note, out_max, gap, culet_up, inside, seat_gap, bearing))
    errors.extend("%s: %s" % (tag, e) for e in bad)


def check_basket(errors, ss, cutter, unit_em):
    """Полный стек, Type = Basket, Below Culet 1.0: Round 3 / 6.5, Emerald 7 x 10; Rail Shape Round и Flat,
    Set выкл/вкл; Round 6.5 ещё с Tilt 8° и с Tip = Claw + Set."""
    rwp = bpy.data.objects["RWPRound"]
    print("basket case                        closed cage  section                                          "
          "            outside / gap / culet / stone")
    obs = {}
    for cut, w, ln, dia in BASKET_CASES:
        unit = rwp if cut == "Round" else unit_em
        ob = ss["setup"](cut, w, ln, diam=unit, cutter=cutter if cut == "Round" else None,
                         name="Basket %s %gx%g" % (cut, w, ln), cast_type="Basket")
        stack_defaults(ob, ss)
        put(ob, "My_Stone_Cast", (None, "Type"), "Basket")
        put(ob, "My_Stone_Prongs", ("Prongs", "ø"), dia)
        put(ob, "My_Stone", ("Setting", "Below Culet"), 1.0)
        name = "%s %s" % (cut.lower(), ("%g" % w) if cut == "Round" else "%gx%g" % (w, ln))
        for shape in ("Round", "Flat"):
            for set_on in (False, True):
                basket_case(errors, ss, ob, cut, w, ln, unit, shape, set_on,
                            "basket %s %s set %s" % (name, shape.lower(), "on " if set_on else "off"))
        if (cut, w) == ("Round", 6.5):
            put(ob, "My_Stone", ("Setting", "Tilt"), radians(8.0))
            basket_case(errors, ss, ob, cut, w, ln, unit, "Round", True, "basket %s round tilt 8 set on" % name)
            put(ob, "My_Stone_Prongs", (None, "Tip"), "Claw")
            basket_case(errors, ss, ob, cut, w, ln, unit, "Round", True, "basket %s round tilt 8 claw set" % name)
            put(ob, "My_Stone_Prongs", (None, "Tip"), "Round")
            put(ob, "My_Stone", ("Setting", "Tilt"), 0.0524)
        put(ob, "My_Stone", ("Setting", "Set"), False)
        put(ob, "My_Stone_Cast", ("Basket", "Rail Shape"), "Round")
        obs[(cut, w)] = (ob, unit, w, ln)
    return obs


def render_basket_sheet(ss, obs):
    """Корзинка: Round 6.5 — круглые ранты + круглые крапана | круглые ранты + Claw Set, Tilt 8° | плоские
    ранты; Emerald 7 x 10 — круглые ранты. Ряды — вид 3/4 и вид сбоку (~10° над горизонтом)."""
    ob, unit, w, ln = obs[("Round", 6.5)]
    eo, eunit, ew, eln = obs[("Emerald", 7.0)]
    variants = [(ob, unit, w, ln, "round rails", {}),
                (ob, unit, w, ln, "round rails, Claw Set, Tilt 8°",
                 {("My_Stone_Prongs", (None, "Tip")): "Claw", ("My_Stone", ("Setting", "Set")): True,
                  ("My_Stone", ("Setting", "Tilt")): radians(8.0)}),
                (ob, unit, w, ln, "flat rails", {("My_Stone_Cast", ("Basket", "Rail Shape")): "Flat"}),
                (eo, eunit, ew, eln, "round rails", {})]
    cells = []
    for col, (o, u, w_, l_, text_, vals) in enumerate(variants):
        old = {k: get(o, *k) for k in vals}
        for k, v in vals.items():
            put(o, k[0], k[1], v)
        me = freeze(o)
        size = "ø %g" % w_ if w_ == l_ else "%g x %g" % (w_, l_)
        cells.append((col, 0, "%s %s" % (get(o, "My_Stone", (None, "Cut")), size), me, u.data, w_, l_))
        cells.append((col, 1, text_, me, u.data, w_, l_, "side"))
        for k, v in old.items():
            put(o, k[0], k[1], v)
    render_cells(PREVIEW_BASKET, "My_Stone_Cast: Basket (top: 3/4 view, bottom: side view)", cells, (2000, 0))


# --- огранки по контуру (Oval, Pear) ------------------------------------------------------------------

CUT_CASES = (("Oval", 5.0, 7.0), ("Pear", 5.0, 8.0))
CUT_DIA = 0.7


def loop_limit(proto, w, ln):
    """Предел управляющей петли контура в мм: (плотный многоугольник [(x, y)], острые вершины [(x, y)])."""
    loop, dense = outline_loop_dense(proto, w, ln)
    return [(x, y) for x, y, _tx, _ty in dense], [(x, y) for x, y, c in loop if c]


def outline_loop_dense(proto, w, ln):
    """Петля контура против часовой [(x, y, corner)] в мм и её предел (gem_outline.limit_curve)."""
    sys.path.insert(0, str(ROOT / "jewel_tools"))
    import gem_outline as go
    me = proto.data
    linked = {i for e in me.edges for i in e.vertices}
    corner = me.attributes["corner"].data
    order, cur, prev = [], min(linked), None
    links = {}
    for e in me.edges:
        a, b_ = e.vertices
        links.setdefault(a, []).append(b_)
        links.setdefault(b_, []).append(a)
    while True:
        order.append(cur)
        cur, prev = next(v for v in links[cur] if v != prev), cur
        if cur == order[0]:
            break
    loop = [(me.vertices[i].co.x * w, me.vertices[i].co.y * ln, corner[i].value > 0.5) for i in order]
    if sum(a[0] * b_[1] - b_[0] * a[1] for a, b_ in zip(loop, loop[1:] + loop[:1])) < 0:
        loop = loop[::-1]
    return loop, go.limit_curve(loop, 64)


def outline_sites(proto, w, ln):
    """Места крапанов контура (вершины без рёбер) в мм и наружная нормаль предела петли в ближайшей точке."""
    _loop, dense = outline_loop_dense(proto, w, ln)
    me = proto.data
    linked = {i for e in me.edges for i in e.vertices}
    out = []
    for v in me.vertices:
        if v.index in linked:
            continue
        x, y = v.co.x * w, v.co.y * ln
        _x, _y, tx, ty = min(dense, key=lambda q: (q[0] - x) ** 2 + (q[1] - y) ** 2)
        out.append((Vector((x, y, 0.0)), Vector((ty, -tx, 0.0)).normalized()))
    return out


def site_paths(unit, w, ln, sites):
    """Путь по короне каждого места: по горизонтали от места внутрь (-n) до края площадки камня
    (выпуклая оболочка вершин площадки в плане) — как в My_Stone_Prongs на контуре."""
    me = unit.data
    zmax = max(v.co.z for v in me.vertices)
    pts = sorted({(round(v.co.x * w, 9), round(v.co.y * ln, 9)) for v in me.vertices if v.co.z >= zmax * 0.999})

    def half(seq):
        out = []
        for p in seq:
            while len(out) >= 2 and ((out[-1][0] - out[-2][0]) * (p[1] - out[-2][1]) -
                                     (out[-1][1] - out[-2][1]) * (p[0] - out[-2][0])) <= 1e-12:
                out.pop()
            out.append(p)
        return out
    hull = half(pts)[:-1] + half(pts[::-1])[:-1]
    out = []
    for o, n in sites:
        best = 9.0
        for (ax, ay), (bx, by) in zip(hull, hull[1:] + hull[:1]):
            ex, ey = bx - ax, by - ay
            den = (-n.x) * ey - (-n.y) * ex
            if abs(den) < 1e-12:
                continue
            t = ((ax - o.x) * ey - (ay - o.y) * ex) / den
            u = ((ax - o.x) * (-n.y) - (ay - o.y) * (-n.x)) / den
            if t > 0 and -1e-9 <= u <= 1 + 1e-9:
                best = min(best, t)
        out.append(best)
    return out


def site_reach(verts, sites, zmin=0.01):
    """Заход металла выше рундиста по каждому месту: max -(v - место) . n у вершин, ближайших к месту."""
    per = [0.0] * len(sites)
    for v in verts:
        if v.z > zmin:
            k = min(range(len(sites)), key=lambda i: (v.xy - sites[i][0].xy).length)
            per[k] = max(per[k], -(v - sites[k][0]).dot(sites[k][1]))
    return per


def tip_gap(verts, sites, k, unit, w, ln, _zg=None):
    """Зазор от кончика крапана места k (вершины выше верха рундиста у этого места + 0.01) до камня.
    Верх рундиста — по вершинам камня в 0.3 мм от ближайшей к месту (у Heart граница верхних граней идёт через выемку
    на высоте площадки, общий верх рундиста по ней неверен)."""
    me = unit.data
    co = [Vector((v.co.x * w, v.co.y * ln, v.co.z * w)) for v in me.vertices]
    stone = BVHTree.FromPolygons(co, [tuple(p.vertices) for p in me.polygons])
    d0 = min((p.xy - sites[k][0].xy).length for p in co)
    zg = max(p.z for p in co if (p.xy - sites[k][0].xy).length < d0 + 0.3)
    tip = [v for v in verts if v.z > zg + 0.01 and
           min(range(len(sites)), key=lambda i: (v.xy - sites[i][0].xy).length) == k]
    return min((v - stone.find_nearest(v)[0]).length for v in tip) if tip else 9.0


def prong_count(ob):
    """Крапанов — оболочек металла выше рундиста (верх стенки ниже него), без My_Setting_Bool."""
    md = mod(ob, "My_Setting_Bool")
    md.show_viewport = False
    verts, faces = evaluate(ob)[:2]
    md.show_viewport = True
    return sum(1 for part in shell_ids(faces, len(verts)) if max(verts[i].z for k in part for i in faces[k]) > 0.01)


def prong_axes(ob, sites, dia):
    """Ось каждого крапана на z = 0.02: середина сечения по нормали места (без My_Setting_Bool — посадка
    не срезает ствол изнутри). -> [точка оси]"""
    md = mod(ob, "My_Setting_Bool")
    md.show_viewport = False
    m = evaluate(ob)
    md.show_viewport = True
    bvh = BVHTree.FromPolygons(m[0], m[5])
    out = []
    for o, n in sites:
        c = o + n * dia * 0.25 + Vector((0, 0, 0.02))
        a = bvh.ray_cast(c + n * 2 * dia, -n, 9.0)[0]
        b_ = bvh.ray_cast(c - n * 2 * dia, n, 9.0)[0]
        out.append((a + b_) / 2 if a and b_ else None)
    return out


def outline_rays(outline, z):
    """Лучи снаружи к контуру по нормалям из середин его сторон: [(начало, направление, точка контура)]."""
    out = []
    for (ax, ay), (bx, by) in zip(outline, outline[1:] + outline[:1]):
        n = Vector((by - ay, ax - bx, 0.0)).normalized()
        mid = Vector(((ax + bx) / 2, (ay + by) / 2, z))
        out.append((mid + n * 5.0, -n, mid))
    return out


def cut_case(errors, ss, ob, cut, w, ln, unit, proto, config, tag):
    """Строка таблицы огранки по контуру. config: wall | wall claw set | bezel off | bezel on | basket round |
    basket flat."""
    from math import tan as tan_
    stack_defaults(ob, ss)
    put(ob, "My_Stone_Prongs", ("Prongs", "ø"), CUT_DIA)
    prongs_md = mod(ob, "My_Stone_Prongs")
    kind = config.split()[0].title()
    put(ob, "My_Stone_Cast", (None, "Type"), kind)
    if "claw" in config:
        put(ob, "My_Stone_Prongs", (None, "Tip"), "Claw")
    set_on = config.endswith("set") or config.endswith(" on")
    put(ob, "My_Stone", ("Setting", "Set"), set_on)
    if kind == "Basket":
        put(ob, "My_Stone_Cast", ("Basket", "Rail Shape"), config.split()[1].title())
    prongs_md.show_viewport = kind != "Bezel"            # глухой каст — без крапанов, как в разделе 8
    sites = outline_sites(proto, w, ln)
    outline, zg = girdle_outline(unit, w, ln)
    m = evaluate(ob)
    verts = m[0]
    closed = closed_outward(verts, m[1])
    inside = inside_stone(verts, unit, w, ln)
    bad = []
    if closed != (True, 1) or inside:
        bad.append("closed %s (%d), %d verts inside the stone" % (closed[0], closed[1], inside))
    note = ""
    tilt = get(ob, "My_Stone", ("Setting", "Tilt"))
    bvh = BVHTree.FromPolygons(verts, m[5])
    if kind == "Wall":
        nprong = prong_count(ob)
        if nprong != len(sites):
            bad.append("%d prongs, %d sites" % (nprong, len(sites)))
        note = "prongs %d/%d" % (nprong, len(sites))
        if "claw" in config:
            # заход когтя — доля своего пути по короне (как раздел 12)
            cov = get(ob, "My_Stone_Prongs", ("Prongs", "Set Cover")) / 100.0
            paths = site_paths(unit, w, ln, sites)
            reach = [r / p_ for r, p_ in zip(site_reach(verts, sites), paths)]
            k0 = min(range(len(paths)), key=lambda i: paths[i])
            same = max(paths) / min(paths) - 1.0 < 0.01
            note += " reach %s (cov %.2f%s)" % (" ".join("%.2f" % r for r in reach), cov,
                                                "" if same else ", shortest %d" % k0)
            if any(not cov - 0.05 <= r <= cov + 0.03 for r in (reach if same else [reach[k0]])):
                bad.append("claw reach outside [%.2f, %.2f]" % (cov - 0.05, cov + 0.03))
        else:
            axes = prong_axes(ob, sites, CUT_DIA)
            ax_err = max(((signed_distance(a.xy, outline) - CUT_DIA * 0.25) if a else 9.0 for a in axes), key=abs)
            z_t, xy = get(ob, "My_Stone_Cast", ("Cast", "Z Offset")), get(ob, "My_Stone_Cast", ("Cast", "XY Offset"))
            z = z_t - 0.01
            wall_err = 0.0
            for o, d, mid in outline_rays(outline, z):
                if min((mid.xy - (s_[0] + s_[1] * CUT_DIA * 0.25).xy).length for s_ in sites) < 1.2 * CUT_DIA:
                    continue
                hit = bvh.ray_cast(o, d, 20.0)[0]
                e = (signed_distance(hit.xy, outline) - (xy - 0.01 * tan_(tilt))) if hit else 9.0
                wall_err = max(wall_err, e, key=abs)
            note += " axis %+.4f wall %+.4f" % (ax_err, wall_err)
            if abs(ax_err) > 0.02:
                bad.append("prong axis %+.4f from girdle + ø (0.5 - I)" % ax_err)
            if abs(wall_err) > 0.01 * w:
                bad.append("wall %+.4f from girdle + XY Offset" % wall_err)
    elif kind == "Bezel":
        g = lambda k: get(ob, "My_Stone_Cast", ("Bezel", k))
        me = unit.data
        zmax = max(v.co.z for v in me.vertices)
        h = zmax * w
        c = w * (0.5 - max(abs(v.co.x) for v in me.vertices if v.co.z >= zmax * 0.999))
        zt, cov, clr = g("Height") / 100.0 * h, g("Bezel Cover") / 100.0 * c, ss["BEZEL_CLEAR"] * w
        top = max(v.z for v in verts) - (zt - (0.0 if set_on else clr * tan_(ss["BEZEL_BEVEL"])))
        wall_err = 0.0
        for o, d, _mid in outline_rays(outline, 0.001):
            hit = bvh.ray_cast(o, d, 20.0)[0]
            wall_err = max(wall_err, (signed_distance(hit.xy, outline) - g("Wall")) if hit else 9.0, key=abs)
        if set_on:
            # губа — от предела управляющей петли (от него и строится; рундист меша отличается на подгонку)
            lim, _sharp = loop_limit(proto, w, ln)
            lip = [v for v in verts if v.z > zg + 0.005]
            inner = -min(signed_distance(v.xy, lim) for v in lip)
            # на изогнутом пути высокая внутренняя грань губы между рёбрами с crease после SubD выгибается
            # внутрь (у Round в разделе 8 +7 %, у головки Pear до +21 %) — проверка «закрывает не меньше cov»,
            # перебор печатается
            extra = "lip %.4f/%.4f (+%.0f%%, check >= cov)" % (inner, cov, (inner / cov - 1) * 100)
            if inner < cov - 0.03 * c:
                bad.append("lip %.4f, cov %.4f" % (inner, cov))
        else:
            drop = sum(1 for v in verts if v.z > 1e-4 and signed_distance(v.xy, outline) < -1e-4)
            extra = "drop-in blocked %d" % drop
            if drop:
                bad.append("metal above girdle inside outline: %d" % drop)
        # стенка: допуск 0.01 W, как у Wall в разделе 11 (у Round в разделе 8 — 0.01 мм): предел управляющей
        # петли — подгонка к рундисту меша, у Pear расходится на ~0.035 мм (у монолита так же)
        note = "top %+.4f wall %+.4f (tol %.3f) %s" % (top, wall_err, 0.01 * w, extra)
        if abs(top) > 0.02:
            bad.append("top %+.4f" % top)
        if abs(wall_err) > 0.01 * w:
            bad.append("wall %+.4f" % wall_err)
    else:
        # рант: размеры на самих рантах (без крапанов и Bool), в самой широкой точке контура по +X
        z_t, xy, t = (get(ob, "My_Stone_Cast", ("Cast", k)) for k in ("Z Offset", "XY Offset", "Cast Thickness"))
        culet = min(v.co.z for v in unit.data.vertices) * w
        z_b = culet - get(ob, "My_Stone", ("Setting", "Below Culet"))
        rail = min(get(ob, "My_Stone_Cast", ("Basket", "Rail")), max(z_t - z_b, 0.05))
        d_out = lambda z: xy + z * tan_(tilt)
        bool_md = mod(ob, "My_Setting_Bool")
        prongs_md.show_viewport = bool_md.show_viewport = False
        raw = evaluate(ob)
        prongs_md.show_viewport = bool_md.show_viewport = True
        # отступы ранта — от предела управляющей петли (от него и строятся), без вершин у острых углов петли
        # (митра там законно дальше); ширина / высота / отступ — по всему нижнему ранту, вершины предела SubD
        lim, sharp = loop_limit(proto, w, ln)
        z_gap = (z_t - rail + z_b + rail) / 2
        keep = lambda v: all((v.xy - Vector(q)).length > 3 * t for q in sharp)
        lo_r = [v for v in raw[0] if v.z < z_gap and keep(v)]
        up_r = [v for v in raw[0] if v.z > z_gap and keep(v)]
        sd = {id(v): signed_distance(v.xy, lim) for v in lo_r}
        zc = z_b + rail / 2
        if "flat" in config:
            mid = [v for v in lo_r if abs(v.z - zc) < 1e-4]
            outer = max(sd[id(v)] for v in mid) - d_out(zc)
            res = {"top": max(v.z for v in up_r) - z_t, "bottom": min(v.z for v in lo_r) - z_b,
                   "height": (max(v.z for v in up_r) - min(v.z for v in up_r)) - rail,
                   "thick": (max(sd[id(v)] for v in mid) - min(sd[id(v)] for v in mid)) - t, "outer": outer}
            # допуски на контуре: высоты точные (0.002), отступы от предела — как у монолита My_Gem_Cast
            # (test_gem_cast: толщина 5 %), наружный край 0.01: вынос петли с компенсацией сглаживания точен
            # только в точках петли, между ними толщина гуляет
            tol = {"top": 0.002, "bottom": 0.002, "height": 0.002, "thick": 0.05 * t, "outer": 0.01}
            note = " ".join("%s %+.4f" % (k, v) for k, v in res.items()) + " (tol thick 5%, outer 0.01)"
            bad += ["%s %+.4f" % (k, v) for k, v in res.items() if abs(v) > tol[k]]
        else:
            width = (max(sd.values()) - min(sd.values())) / t - 1.0
            height = (max(v.z for v in lo_r) - min(v.z for v in lo_r)) / rail - 1.0
            outer = max(sd.values()) - d_out(zc)
            note = "width %+.1f%% height %+.1f%% outer %+.4f (tol width 5%%)" % (width * 100, height * 100, outer)
            if abs(width) > 0.05 or abs(height) > 0.02 or abs(outer) > 0.01:
                bad.append(note)
        out_max = max(signed_distance(v.xy, outline) for v in raw[0])
        note += " out %+.3f" % out_max
        if xy <= 0 and out_max > 0.01:
            bad.append("rail outside the girdle by %.4f" % out_max)
    print("%-26s %s(%d) in %d  %s" % (tag, closed[0], closed[1], inside, note))
    errors.extend("%s: %s" % (tag, e) for e in bad)
    prongs_md.show_viewport = True
    stack_defaults(ob, ss)


def check_cuts(errors, ss, gns, round_ob, em_ob):
    """Раздел 11: Oval 5 x 7 и Pear 5 x 8, ø 0.7, полный стек; Pear против My_Gem_Cast; свои точки контура."""
    print("cut case                   closed in  checks")
    obs = {}
    for cut, w, ln in CUT_CASES:
        ob = ss["setup"](cut, w, ln, name="Cut %s %gx%g" % (cut, w, ln))
        unit = get(ob, "My_Stone", (None, "Diam")) or bpy.data.objects["Unit " + cut]
        proto = bpy.data.objects["Outline " + cut]
        stack_defaults(ob, ss)
        for config in ("wall", "wall claw set", "bezel off", "bezel on", "basket round", "basket flat"):
            cut_case(errors, ss, ob, cut, w, ln, unit, proto, config, "%s %gx%g %s" % (cut.lower(), w, ln, config))
        obs[cut] = (ob, unit, proto, w, ln)

    # Pear против монолита My_Gem_Cast (та же Outline Pear, те же значения)
    ob, unit, proto, w, ln = obs["Pear"]
    ref = gns["setup"]("PEAR", w, ln)
    mono_defaults(ref, gns, "My_Gem_Cast")
    put(ref, "My_Gem_Cast", ("Prongs", "ø"), CUT_DIA)
    stack_defaults(ob, ss)
    put(ob, "My_Stone_Prongs", ("Prongs", "ø"), CUT_DIA)
    same = get(ref, "My_Gem_Cast", (None, "Outline")) == proto and get(ref, "My_Gem_Cast", (None, "Diam")) == unit
    print("pear vs My_Gem_Cast (same Outline Pear and Unit Pear: %s)" % same)
    if not same:
        errors.append("pear: monolith uses another outline / stone")
    for bc in (True, False):
        compare_case(errors, "pear %gx%g" % (w, ln), ob, ref, "My_Gem_Cast", False, bc, w, ln, unit)
    # Set вкл: путь по короне у стека — свой у мест контура (у монолита прежний W (0.5 - max |x|)), сравнения
    # с монолитом нет; круглый кончик — заход у места с кратчайшим путём в окне GIA test_round_cast и зазор
    sites = outline_sites(proto, w, ln)
    paths = site_paths(unit, w, ln, sites)
    k0 = min(range(len(paths)), key=lambda i: paths[i])
    _o, zg = girdle_outline(unit, w, ln)
    for bc in (True, False):
        put(ob, "My_Setting_Bool", ("Bool", "BoolCutter"), bc)
        put(ob, "My_Stone", ("Setting", "Set"), True)
        m = evaluate(ob)
        reach = site_reach(m[0], sites)[k0] / paths[k0]
        gap = tip_gap(m[0], sites, k0, unit, w, ln, zg)
        inside = inside_stone(m[0], unit, w, ln)
        print("pear %gx%g bc %s set on  round tip reach %.3f (0.33..0.50) gap %.4f in stone %d" % (
            w, ln, "on " if bc else "off", reach, gap, inside))
        if not 0.33 <= reach <= 0.50 or gap > 0.05 or inside:
            errors.append("pear set on (bc %s): reach %.3f, gap %.4f, inside %d" % (bc, reach, gap, inside))
    stack_defaults(ob, ss)

    # свои точки: копия контура без одного места и с новым местом на рундисте (+X)
    ob, unit, proto, w, ln = obs["Oval"]
    stack_defaults(ob, ss)
    put(ob, "My_Stone_Prongs", ("Prongs", "ø"), CUT_DIA)
    n0 = len(outline_sites(proto, w, ln))
    fewer = proto.copy()
    fewer.data = proto.data.copy()
    fewer.name = "Outline Oval fewer"
    bpy.context.scene.collection.objects.link(fewer)
    bm = bmesh.new()
    bm.from_mesh(fewer.data)
    bmesh.ops.delete(bm, geom=[next(v for v in bm.verts if not v.link_edges)], context="VERTS")
    bm.to_mesh(fewer.data)
    bm.free()
    more = proto.copy()
    more.data = proto.data.copy()
    more.name = "Outline Oval more"
    bpy.context.scene.collection.objects.link(more)
    me = more.data
    pos = [v.co.copy() for v in me.vertices]
    corner = [me.attributes["corner"].data[i].value for i in range(len(pos))]
    edges = [tuple(e.vertices) for e in me.edges]
    me.clear_geometry()
    me.from_pydata(pos + [Vector((0.5, 0.0, 0.0))], edges, [])
    me.attributes.new("corner", "FLOAT", "POINT").data.foreach_set("value", corner + [0.0])
    me.update()
    res = []
    for label_, obj, want in (("fewer", fewer, n0 - 1), ("more", more, n0 + 1)):
        put(ob, "My_Stone", (None, "Outline"), obj)
        n = prong_count(ob)
        res.append("%s %d/%d" % (label_, n, want))
        if n != want:
            errors.append("custom outline %s: %d prongs, want %d" % (label_, n, want))
    # новое место (+X): ось крапана на ø (0.5 - I) за рундистом
    sites = outline_sites(more, w, ln)
    new_site = [s_ for s_ in sites if s_[0].x > 0.49 * w and abs(s_[0].y) < 0.01]
    axis = prong_axes(ob, new_site, CUT_DIA)[0]
    outline, _zg = girdle_outline(unit, w, ln)
    err = (signed_distance(axis.xy, outline) - CUT_DIA * 0.25) if axis else 9.0
    res.append("new site axis %+.4f" % err)
    if abs(err) > 0.02:
        errors.append("custom outline: new site axis %+.4f" % err)
    put(ob, "My_Stone", (None, "Outline"), None)
    # тот же контур у Round и Emerald — крапана по его точкам
    for o in (round_ob, em_ob):
        stack_defaults(o, ss)
        put(o, "My_Stone", (None, "Outline"), more)
        n = prong_count(o)
        w_, l_ = get(o, "My_Stone", ("Stone", "Width")), get(o, "My_Stone", ("Stone", "Length"))
        if get(o, "My_Stone", (None, "Cut")) == "Round":
            l_ = w_
        # Wall: прорезь не мешает; оси — по точкам контура
        axes = prong_axes(o, outline_sites(more, w_, l_), get(o, "My_Stone_Prongs", ("Prongs", "ø")))
        res.append("%s %d/%d" % (get(o, "My_Stone", (None, "Cut")).lower(), n, n0 + 1))
        if n != n0 + 1 or any(a is None for a in axes):
            errors.append("%s with custom outline: %d prongs, want %d" % (o.name, n, n0 + 1))
        put(o, "My_Stone", (None, "Outline"), None)
    print("custom outline: %s" % ", ".join(res))

    # Round: Cut Oval -> Round — прежние вершины; носитель контура не виден (realize в конце стека)
    stack_defaults(round_ob, ss)
    before = evaluate(round_ob)[0]
    put(round_ob, "My_Stone", (None, "Cut"), "Oval")
    put(round_ob, "My_Stone", ("Stone", "Length"), 7.0)
    evaluate(round_ob)
    put(round_ob, "My_Stone", (None, "Cut"), "Round")
    after = evaluate(round_ob)[0]
    same = len(before) == len(after) and all((p - q).length < 1e-6 for p, q in zip(before, after))
    ob = obs["Oval"][0]
    stack_defaults(ob, ss)
    put(ob, "My_Stone", (None, "ShowStone"), False)
    ng = bpy.data.node_groups.new("Test Realize", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gin, gout = ng.nodes.new("NodeGroupInput"), ng.nodes.new("NodeGroupOutput")
    real = ng.nodes.new("GeometryNodeRealizeInstances")
    ng.links.new(gin.outputs[0], real.inputs[0])
    ng.links.new(real.outputs[0], gout.inputs[0])
    base = evaluate(ob)[0]
    md = ob.modifiers.new("Test Realize", "NODES")
    md.node_group = ng
    verts = evaluate(ob)[0]
    extra = verts[len(base):]
    spread = max((v.length for v in extra), default=0.0)
    ob.modifiers.remove(md)
    bpy.data.node_groups.remove(ng)
    stack_defaults(ob, ss)
    print("Cut Oval -> Round: same vertices %s; hidden carriers realized: +%d verts, farthest from origin %.6f" % (
        same, len(extra), spread))
    if not same:
        errors.append("Cut Oval -> Round changes the vertices")
    if spread > 1e-6:
        errors.append("hidden carriers: realized vertices %.6f from origin" % spread)
    return obs


def render_cuts_sheet(ss, obs):
    """Oval и Pear: Wall + Round | Wall + Claw, Set | Bezel, Set | Basket + Round; ряды — 3/4 и сверху."""
    cells = []
    configs = (("Wall + Round", {}), ("Wall + Claw, Set", {("My_Stone_Prongs", (None, "Tip")): "Claw",
                                                        ("My_Stone", ("Setting", "Set")): True}),
               ("Bezel, Set", {("My_Stone_Cast", (None, "Type")): "Bezel", ("My_Stone", ("Setting", "Set")): True}),
               ("Basket + Round", {("My_Stone_Cast", (None, "Type")): "Basket"}))
    col = 0
    for cut in ("Oval", "Pear"):
        ob, unit, _proto, w, ln = obs[cut]
        for text_, vals in configs:
            stack_defaults(ob, ss)
            put(ob, "My_Stone_Prongs", ("Prongs", "ø"), CUT_DIA)
            for k, v in vals.items():
                put(ob, k[0], k[1], v)
            mod(ob, "My_Stone_Prongs").show_viewport = "Bezel" not in text_
            me = freeze(ob)
            mod(ob, "My_Stone_Prongs").show_viewport = True
            cells.append((col, 0, "%s %g x %g, %s" % (cut, w, ln, text_), me, unit.data, w, ln))
            cells.append((col, 1, "top", me, unit.data, w, ln, "top"))
            col += 1
        stack_defaults(ob, ss)
    render_cells(PREVIEW_CUTS, "Oval and Pear by outline points", cells, (2600, 0))


# --- остальные 13 огранок -------------------------------------------------------------------------

ALL_LONG = 7.0     # длинная сторона камня, мм
ALL_DIA = 0.7
# случаи, которые не проходят по геометрической причине (печатаются с замерами, прогон не валят)
KNOWN = {
    ("Triangle", "wall"): "60° tips: the mitred wall corner sits 2 d from the girdle corner and recedes "
                          "further down with Tilt; with Intersection 25% the tip prong no longer reaches the "
                          "lower ring under the slot (one shell with Intersection 35% or Tilt 0)",
    ("Triangle", "basket"): "60° tips: same as wall — the lower rail corner recedes past the tip prong "
                            "(one shell with Intersection 35% or Tilt 0)",
    ("Triangle", "claw set"): "60° tips: same as wall — the claw leg misses the lower ring under the slot by about "
                              "0.01 mm (one shell with Intersection 30%; the pre-arc claw reached it by the same margin)",
    ("Heart", "bezel off"): "concave notch: the seat cutters are convex hulls of the stone (auto cutter, Set hull — "
                            "as My_Gem_Cast) and bridge the notch, cutting the bezel wall there (uncut cage: wall "
                            "+0.003 at the notch)",
    ("Heart", "bezel on"): "concave notch: same convex-hull seat cutter cuts the bezel wall in the notch",
}


def cut_size(gems, cut):
    """Пропорции огранки base_width x base_length, длинная сторона ALL_LONG."""
    spec = gems._CUT_SPECS[cut.upper()]
    k = ALL_LONG / max(spec.base_width, spec.base_length)
    return spec.base_width * k, spec.base_length * k


def rule_count(ss, cut):
    """Число крапанов по RULES: заданное, 4 у diag и cuts, острые вершины петли у corners."""
    rule = ss["RULES"][cut.upper()]
    if len(rule) > 1:
        return rule[1]
    if rule[0] == "corners":
        proto = bpy.data.objects["Outline " + cut]
        return sum(1 for d in proto.data.attributes["corner"].data if d.value > 0.5)
    return 4


def all_cut_case(errors, ss, ob, cut, w, ln, unit, proto, mode):
    from math import tan as tan_
    stack_defaults(ob, ss)
    put(ob, "My_Stone_Prongs", ("Prongs", "ø"), ALL_DIA)
    prongs_md = mod(ob, "My_Stone_Prongs")
    set_on = mode in ("claw set", "bezel on")
    put(ob, "My_Stone", ("Setting", "Set"), set_on)
    put(ob, "My_Stone_Cast", (None, "Type"), {"bezel off": "Bezel", "bezel on": "Bezel", "basket": "Basket"}.get(mode, "Wall"))
    if mode == "claw set":
        put(ob, "My_Stone_Prongs", (None, "Tip"), "Claw")
    prongs_md.show_viewport = not mode.startswith("bezel")     # глухой каст — без крапанов, как в разделе 8
    m = evaluate(ob)
    verts = m[0]
    closed = closed_outward(verts, m[1])
    inside = inside_stone(verts, unit, w, ln)
    bad = [] if closed == (True, 1) and not inside else ["closed %s (%d), %d verts inside" % (closed[0], closed[1], inside)]
    sites = outline_sites(proto, w, ln)
    me = unit.data
    zmax = max(v.co.z for v in me.vertices)
    h, c = zmax * w, w * (0.5 - max(abs(v.co.x) for v in me.vertices if v.co.z >= zmax * 0.999))
    note = ""
    if mode == "wall":
        n, want = prong_count(ob), rule_count(ss, cut)
        axes = prong_axes(ob, sites, ALL_DIA)
        ax = max((((a.xy - o.xy).length - ALL_DIA * 0.25) if a else 9.0 for a, (o, _n) in zip(axes, sites)), key=abs)
        note = "prongs %d/%d axis %+.4f" % (n, want, ax)
        if n != want or abs(ax) > 0.02:
            bad.append(note)
    elif mode == "claw set":
        # заход — доля своего пути по короне; пути равны — окно у всех мест, нет (Pear, Marquise, Heart) —
        # у места с кратчайшим путём (по нему считается коготь), остальные печатаются
        cov = get(ob, "My_Stone_Prongs", ("Prongs", "Set Cover")) / 100.0
        paths = site_paths(unit, w, ln, sites)
        reach = [r / p_ for r, p_ in zip(site_reach(verts, sites), paths)]
        k0 = min(range(len(paths)), key=lambda i: paths[i])
        same = max(paths) / min(paths) - 1.0 < 0.01
        check = reach if same else [reach[k0]]
        # зазор круглого кончика Set у места с кратчайшим путём
        put(ob, "My_Stone_Prongs", (None, "Tip"), "Round")
        _o, zg = girdle_outline(unit, w, ln)
        gap = tip_gap(evaluate(ob)[0], sites, k0, unit, w, ln, zg)
        note = "reach %s (cov %.2f%s) round tip gap %.4f" % (
            " ".join("%.2f" % r for r in reach), cov, "" if same else ", shortest %d" % k0, gap)
        if any(not cov - 0.05 <= r <= cov + 0.03 for r in check) or gap > 0.05:
            bad.append(note)
    elif mode.startswith("bezel"):
        g = lambda k: get(ob, "My_Stone_Cast", ("Bezel", k))
        zt, clr = g("Height") / 100.0 * h, ss["BEZEL_CLEAR"] * w
        top = max(v.z for v in verts) - (zt - (0.0 if set_on else clr * tan_(ss["BEZEL_BEVEL"])))
        outline, _zg = girdle_outline(unit, w, ln)
        bvh = BVHTree.FromPolygons(verts, m[5])
        wall = 0.0
        for o, d, _mid in outline_rays(outline, 0.001):
            hit = bvh.ray_cast(o, d, 20.0)[0]
            wall = max(wall, (signed_distance(hit.xy, outline) - g("Wall")) if hit else 9.0, key=abs)
        note = "top %+.4f wall %+.4f (tol 0.02, %.3f)" % (top, wall, 0.01 * w)
        if abs(top) > 0.02 or abs(wall) > 0.01 * w:
            bad.append(note)
    prongs_md.show_viewport = True
    stack_defaults(ob, ss)
    tag = "all %s %s" % (cut.lower(), mode)
    reason = KNOWN.get((cut, mode))
    if reason and bad:
        print("%-24s %s(%d) in %d  %s  known: %s" % (tag, closed[0], closed[1], inside, note, reason))
    else:
        print("%-24s %s(%d) in %d  %s" % (tag, closed[0], closed[1], inside, note))
        errors.extend("%s: %s" % (tag, e) for e in bad)
        if reason:
            errors.append("%s: listed in KNOWN but passes — remove the entry" % tag)


def check_all_cuts(errors, ss):
    """Раздел 12: 13 огранок, длинная сторона 7 мм, ø 0.7, полный стек."""
    gems = ss["mods"]()[2].load_module("gem_cast_gems", ss["mods"]()[2].GEMS_PATH)
    print("all-cuts case            closed in  checks")
    for cut in ss["CUTS"][4:]:
        w, ln = cut_size(gems, cut)
        ob = ss["setup"](cut, w, ln, name="All %s" % cut)
        unit = get(ob, "My_Stone", (None, "Diam")) or bpy.data.objects["Unit " + cut]
        proto = bpy.data.objects["Outline " + cut]
        for mode in ("wall", "claw set", "bezel off", "bezel on", "basket"):
            all_cut_case(errors, ss, ob, cut, w, ln, unit, proto, mode)
    # объекты, на которые ссылается My_Stone (Index Switch по огранке: камни и контуры)
    refs = {sk.default_value.name for n in bpy.data.node_groups["My_Stone"].nodes
            if n.bl_idname == "GeometryNodeIndexSwitch" and n.data_type == "OBJECT"
            for sk in n.inputs[1:] if getattr(sk, "default_value", None)}
    print("My_Stone references: %d stones, %d outlines" % (
        sum(1 for r in refs if not r.startswith("Outline")), sum(1 for r in refs if r.startswith("Outline"))))


def render_all_cuts(ss, path, title, vals, prongs=True):
    """Все 17 огранок сеткой 6 колонок, вид 3/4."""
    gems = ss["mods"]()[2].load_module("gem_cast_gems", ss["mods"]()[2].GEMS_PATH)
    cells = []
    for i, cut in enumerate(ss["CUTS"]):
        w, ln = cut_size(gems, cut)
        ob = bpy.data.objects.get("All %s" % cut) or ss["setup"](cut, w, ln, name="All %s" % cut)
        stack_defaults(ob, ss)
        put(ob, "My_Stone_Prongs", ("Prongs", "ø"), ALL_DIA)
        for k, v in vals.items():
            put(ob, k[0], k[1], v)
        mod(ob, "My_Stone_Prongs").show_viewport = prongs
        unit = get(ob, "My_Stone", (None, "Diam")) or bpy.data.objects.get("Unit " + cut) or bpy.data.objects["RWPRound"]
        if cut == "Round":
            ln = w
            unit = bpy.data.objects["RWPRound"]
        cells.append((i % 6, i // 6, cut, freeze(ob), unit.data, w, ln))
        mod(ob, "My_Stone_Prongs").show_viewport = True
        stack_defaults(ob, ss)
    render_cells(path, title, cells, (2400, 0))


# --- места крапанов в собственном меше объекта ------------------------------------------------------

PTS_DIA = 0.7


def set_own(ob, points, cube=None):
    """Собственный меш объекта: вершины без рёбер (мм) и, по желанию, куб (центр, размер)."""
    verts, faces = [Vector(p_) for p_ in points], []
    if cube:
        c, h = Vector(cube[0]), cube[1] / 2
        base = len(verts)
        verts += [c + Vector((x, y, z)) for x in (-h, h) for y in (-h, h) for z in (-h, h)]
        faces = [tuple(base + i for i in f) for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6),
                                                       (0, 2, 6, 4), (1, 5, 7, 3))]
    me = ob.data
    me.clear_geometry()
    me.from_pydata(verts, [], faces)
    me.update()
    ob.update_tag()


def loose_count(mesh):
    verts, faces = mesh[0], mesh[1]
    used = {i for f in faces for i in f}
    return sum(1 for i in range(len(verts)) if i not in used)


def prong_centres(ob, guesses, dia):
    """Центры сечений крапанов на z = 0.02 (без My_Setting_Bool): по нормали места и поперёк неё через
    найденную середину. guesses — [(точка на рундисте, наружная нормаль)]."""
    md = mod(ob, "My_Setting_Bool")
    md.show_viewport = False
    m = evaluate(ob)
    md.show_viewport = True
    bvh = BVHTree.FromPolygons(m[0], m[5])
    out = []
    for o, n in guesses:
        t = Vector((-n.y, n.x, 0.0))
        c = o + n * dia * 0.25 + Vector((0, 0, 0.02))
        a, b_ = bvh.ray_cast(c + n * 2 * dia, -n, 9.0)[0], bvh.ray_cast(c - n * 2 * dia, n, 9.0)[0]
        if not (a and b_):
            out.append(None)
            continue
        c = (a + b_) / 2
        a, b_ = bvh.ray_cast(c + t * 2 * dia, -t, 9.0)[0], bvh.ray_cast(c - t * 2 * dia, t, 9.0)[0]
        out.append((a + b_) / 2 if a and b_ else None)
    return out


def check_points(errors, ss, cutter):
    """Раздел 13: места крапанов — вершины без рёбер собственного меша объекта."""
    from math import atan2, cos as cos_, degrees, sin as sin_
    keep = PTS_DIA * 0.25                       # ø (0.5 - Intersection 25 %)
    rwp = bpy.data.objects["RWPRound"]
    obs = {}

    def fresh(cut, w, ln, name, diam=None, cut_obj=None):
        ob = ss["setup"](cut, w, ln, diam=diam, cutter=cut_obj, name=name)
        stack_defaults(ob, ss)
        put(ob, "My_Stone_Prongs", ("Prongs", "ø"), PTS_DIA)
        set_own(ob, [])
        return ob

    def same(a, b_):
        return len(a) == len(b_) and all((p_ - q).length < 1e-6 for p_, q in zip(a, b_))

    # a) Round 6.5: три точки на 0, 120, 240° в 0.3 мм за рундистом
    ob = fresh("Round", 6.5, 6.5, "Points Round", rwp, cutter)
    before = evaluate(ob)[0]
    outline, _zg = girdle_outline(rwp, 6.5, 6.5)
    angs = (0.0, 120.0, 240.0)
    dirs = [Vector((cos_(radians(a_)), sin_(radians(a_)), 0.0)) for a_ in angs]
    set_own(ob, [d_ * (3.25 + 0.3) for d_ in dirs])
    n = prong_count(ob)
    cs = prong_centres(ob, [(d_ * 3.25, d_) for d_ in dirs], PTS_DIA)
    az = max(abs((degrees(atan2(c_.y, c_.x)) - a_ + 180) % 360 - 180) if c_ else 99.0 for c_, a_ in zip(cs, angs))
    off = max(((signed_distance(c_.xy, outline) - keep) if c_ else 9.0 for c_ in cs), key=abs)
    m = evaluate(ob)
    closed = closed_outward(m[0], m[1])
    lc = loose_count(m)
    set_own(ob, [])
    back = same(before, evaluate(ob)[0])
    print("points round 6.5 x3      prongs %d/3 azimuth %.2f° axis %+.4f closed %s(%d) loose %d removed-same %s" % (
        n, az, off, closed[0], closed[1], lc, back))
    if n != 3 or az > 0.5 or abs(off) > 0.02 or closed != (True, 1) or lc or not back:
        errors.append("points round: prongs %d, az %.2f, axis %+.4f, closed %s, loose %d, back %s" % (
            n, az, off, closed, lc, back))
    obs["round3"] = (ob, [d_ * (3.25 + 0.3) for d_ in dirs])
    obs["round6"] = (ob, [Vector((cos_(radians(a_)), sin_(radians(a_)), 0.0)) * 3.55 for a_ in range(0, 360, 60)])

    # b) Emerald 7 x 10: по две точки у каждого среза угла (у концов среза, 0.3 мм наружу)
    eo = fresh("Emerald", 7.0, 10.0, "Points Emerald")
    unit_e = get(eo, "My_Stone", (None, "Diam")) or bpy.data.objects["Unit Emerald"]
    before = evaluate(eo)[0]
    me_ = unit_e.data
    cx = 7.0 * (0.5 - max(abs(v.co.x) for v in me_.vertices if abs(v.co.y) >= 0.5 - 1e-4))
    cy = 10.0 * (0.5 - max(abs(v.co.y) for v in me_.vertices if abs(v.co.x) >= 0.5 - 1e-4))
    pts = []
    for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
        p1, p2 = Vector((sx * 3.5, sy * (5.0 - cy), 0)), Vector((sx * (3.5 - cx), sy * 5.0, 0))
        nrm = Vector((sx * cy, sy * cx, 0)).normalized()
        for t_ in (0.2, 0.8):
            pts.append(p1.lerp(p2, t_) + nrm * 0.3)
    set_own(eo, pts)
    outline_e, _zg = girdle_outline(unit_e, 7.0, 10.0)
    n = prong_count(eo)
    guess = []
    for p_ in pts:
        sx, sy = (1 if p_.x > 0 else -1), (1 if p_.y > 0 else -1)
        nrm = Vector((sx * cy, sy * cx, 0)).normalized()
        guess.append((p_ - nrm * 0.3, nrm))
    cs = prong_centres(eo, guess, PTS_DIA)
    off = max(((signed_distance(c_.xy, outline_e) - keep) if c_ else 9.0 for c_ in cs), key=abs)
    m = evaluate(eo)
    closed, inside = closed_outward(m[0], m[1]), inside_stone(m[0], unit_e, 7.0, 10.0)
    set_own(eo, [])
    back = same(before, evaluate(eo)[0])
    print("points emerald 7x10 x8   prongs %d/8 axis %+.4f closed %s(%d) in %d removed-same %s" % (
        n, off, closed[0], closed[1], inside, back))
    if n != 8 or abs(off) > 0.02 or closed != (True, 1) or inside or not back:
        errors.append("points emerald: prongs %d, axis %+.4f, closed %s, inside %d, back %s" % (n, off, closed, inside, back))
    obs["emerald8"] = (eo, pts)

    # c) Pear: свои точки = встроенные места в мм — то же; точка сдвинута по рундисту на 1 мм — крапан за ней;
    # точка в 1 мм от рундиста снаружи и внутри — садится на рундист
    po = fresh("Pear", 5.0, 8.0, "Points Pear")
    unit_p = get(po, "My_Stone", (None, "Diam")) or bpy.data.objects["Unit Pear"]
    proto = bpy.data.objects["Outline Pear"]
    outline_p, _zg = girdle_outline(unit_p, 5.0, 8.0)
    base = evaluate(po)
    sites = outline_sites(proto, 5.0, 8.0)
    set_own(po, [o for o, _n in sites])
    copy_d = surface_dist(base, evaluate(po))
    o1, n1 = sites[1]
    t1 = Vector((-n1.y, n1.x, 0.0))
    moved = [o for o, _n in sites]
    moved[1] = o1 + t1 * 1.0
    set_own(po, moved)
    c_old = prong_centres(po, [(o1, n1)], PTS_DIA)[0]
    c_new = prong_centres(po, [(o1 + t1 * 1.0, n1)], PTS_DIA)[0]
    shift = (c_new - (o1 + n1 * keep)).length if c_new else 9.0
    off_new = (signed_distance(c_new.xy, outline_p) - keep) if c_new else 9.0
    res = []
    for k_, sign in (("out", 1.0), ("in", -1.0)):
        pts_k = [o for o, _n in sites]
        pts_k[1] = o1 + n1 * sign
        set_own(po, pts_k)
        c_ = prong_centres(po, [(o1, n1)], PTS_DIA)[0]
        # садится на рундист: ось на ø (0.5 - I) от рундиста; вдоль рундиста — до шага точек предела
        # (64 на пролёт петли, место — ближайшая из них), печатается
        res.append((k_, (signed_distance(c_.xy, outline_p) - keep) if c_ else 9.0,
                    abs((c_ - o1).dot(t1)) if c_ else 9.0))
    obs["pear"] = (po, moved)
    set_own(po, [])
    print("points pear 5x8          copy of built-in %.5f, moved 1 mm: prong shift %.3f axis %+.4f (old site empty %s),"
          " 1 mm off girdle -> axis from girdle %s" % (copy_d, shift, off_new, c_old is None,
                                                        " ".join("%s %+.4f (along %.3f)" % r for r in res)))
    if copy_d > 1e-4 or not 0.9 <= shift <= 1.1 or abs(off_new) > 0.02 or any(abs(e) > 0.02 for _k, e, _t in res):
        errors.append("points pear: copy %.5f, shift %.3f, axis %+.4f, off-girdle %s" % (copy_d, shift, off_new, res))

    # d) на выходе нет вершин без рёбер: полный стек и My_Stone + My_Stone_Cast (Bezel)
    ob, pts3 = obs["round3"]
    set_own(ob, pts3)
    full = loose_count(evaluate(ob))
    put(ob, "My_Stone_Cast", (None, "Type"), "Bezel")
    for g in ("My_Stone_Prongs", "My_Setting_Bool"):
        mod(ob, g).show_viewport = False
    bezel = loose_count(evaluate(ob))
    for g in ("My_Stone_Prongs", "My_Setting_Bool"):
        mod(ob, g).show_viewport = True
    put(ob, "My_Stone_Cast", (None, "Type"), "Wall")
    # e) свой меш = маленький куб + точки: куб в металле, точки израсходованы
    set_own(ob, pts3, cube=((6.0, 0.0, -1.0), 0.5))
    m = evaluate(ob)
    cube_in = not outside(BVHTree.FromPolygons(m[0], m[5]), Vector((6.0, 0.0, -1.0)))
    with_cube = (loose_count(m), cube_in, prong_count(ob))
    print("points loose on output   full stack %d, stone + bezel %d; cube + points: loose %d, cube in metal %s, "
          "prongs %d/3" % (full, bezel, *with_cube))
    if full or bezel or with_cube != (0, True, 3):
        errors.append("points: loose full %d bezel %d, cube %s" % (full, bezel, with_cube))
    # f) свои точки важнее точек Outline
    alt = bpy.data.objects.get("Outline Oval more")
    put(ob, "My_Stone", (None, "Outline"), alt)
    set_own(ob, pts3)
    n_own = prong_count(ob)
    put(ob, "My_Stone", (None, "Outline"), None)
    print("points over Outline      Outline with %d sites + 3 own points -> prongs %d" % (
        len(outline_sites(alt, 1.0, 1.0)), n_own))
    if n_own != 3:
        errors.append("points: own points over Outline give %d prongs" % n_own)
    # g) Mirror X над My_Stone, две точки с одной стороны — четыре крапана, зеркально
    two = [Vector((cos_(radians(a_)), sin_(radians(a_)), 0.0)) * 3.55 for a_ in (30.0, -40.0)]
    set_own(ob, two)
    mir = ob.modifiers.new("Mirror", "MIRROR")
    mir.use_axis[0] = True
    while ob.modifiers[0] != mir:
        bpy.ops.object.modifier_move_up({"object": ob}, modifier=mir.name) if False else ob.modifiers.move(
            list(ob.modifiers).index(mir), 0)
        mir = ob.modifiers["Mirror"]
    n_m = prong_count(ob)
    dirs = [d_ for d_ in (v_.normalized() for v_ in two)] + [Vector((-v_.x, v_.y, 0)).normalized() for v_ in two]
    cs = prong_centres(ob, [(d_ * 3.25, d_) for d_ in dirs], PTS_DIA)
    sym = max(((cs[i].xy - Vector((-cs[i + 2].x, cs[i + 2].y))).length if cs[i] and cs[i + 2] else 9.0)
              for i in range(2))
    ob.modifiers.remove(ob.modifiers["Mirror"])
    set_own(ob, [])
    print("points mirror X          prongs %d/4, mirror pair mismatch %.4f" % (n_m, sym))
    if n_m != 4 or sym > 0.02:
        errors.append("points mirror: prongs %d, mismatch %.4f" % (n_m, sym))
    return obs


def render_points_sheet(ss, obs):
    """Свои точки: Round 3 и 6 точек | Emerald 8 точек | Pear с одним сдвинутым крапаном; ряды — 3/4 и сверху."""
    cells = []
    for col, (key, text_) in enumerate((("round3", "Round, 3 own points"), ("round6", "Round, 6 own points"),
                                        ("emerald8", "Emerald, 8 own points"), ("pear", "Pear, one prong moved"))):
        ob, pts = obs[key]
        set_own(ob, pts)
        w, ln = get(ob, "My_Stone", ("Stone", "Width")), get(ob, "My_Stone", ("Stone", "Length"))
        if get(ob, "My_Stone", (None, "Cut")) == "Round":
            ln = w
        unit = get(ob, "My_Stone", (None, "Diam")) or bpy.data.objects["Unit " + get(ob, "My_Stone", (None, "Cut"))]
        me = freeze(ob)
        cells.append((col, 0, text_, me, unit.data, w, ln))
        cells.append((col, 1, "top", me, unit.data, w, ln, "top"))
        set_own(ob, [])
    render_cells(PREVIEW_POINTS, "Prong places from the object's own loose vertices", cells, (2000, 0))


# --- новые типы: V-крапан, лапка, корона, скругление рёбер ------------------------------------------

def corner_frames(proto, w, ln, sites):
    """Места на острых вершинах петли: [(угол C, t1 к предыдущей точке, t2 к следующей)] в мм."""
    loop, _dense = outline_loop_dense(proto, w, ln)
    out = []
    for o, _n in sites:
        for k, (x, y, c) in enumerate(loop):
            if c and (Vector((x, y)) - o.xy).length < 1e-3:
                p0 = Vector((x, y, 0.0))
                pp, pn = loop[k - 1], loop[(k + 1) % len(loop)]
                out.append((p0, (Vector((pp[0], pp[1], 0.0)) - p0).normalized(),
                            (Vector((pn[0], pn[1], 0.0)) - p0).normalized()))
    return out


def ray_through(bvh, origin, d, n_hits=2):
    """Точки первых n_hits попаданий луча."""
    out, o = [], origin
    for _ in range(n_hits):
        loc = bvh.ray_cast(o, d, 50.0)[0]
        if loc is None:
            break
        out.append(loc)
        o = loc + d * 1e-5
    return out


def only_prongs(ob, on=True):
    """Без My_Stone_Cast и My_Setting_Bool: крапана отдельными оболочками (места для короны не нужны)."""
    for g in ("My_Stone_Cast", "My_Setting_Bool"):
        mod(ob, g).show_viewport = not on


def check_v(errors, ss):
    """Раздел 14: V-крапан на острых вершинах."""
    print("V case                      closed in  V  wall    wing   (V off same)")
    for cut, w, ln, types in (("Pear", 6.0, 9.0, ("Wall",)), ("Princess", 6.0, 6.0, ("Wall",)),
                              ("Marquise", 4.0, 8.0, ("Wall",)),
                              ("Triangle", 6.0, 6.0 * 1.000000358 / 1.154700756, ("Wall", "Basket"))):
        ob = ss["setup"](cut, w, ln, name="V %s" % cut)
        stack_defaults(ob, ss)
        unit = get(ob, "My_Stone", (None, "Diam")) or bpy.data.objects["Unit " + cut]
        proto = bpy.data.objects["Outline " + cut]
        sites = outline_sites(proto, w, ln)
        corners = corner_frames(proto, w, ln, sites)
        vt, vl = (get(ob, "My_Stone_Prongs", ("Prongs", k)) for k in ("V Thickness", "V Length"))
        ii = get(ob, "My_Stone_Prongs", ("Prongs", "Intersection")) / 100.0
        for typ in types:
            put(ob, "My_Stone_Cast", (None, "Type"), typ)
            for set_on in (False, True):
                put(ob, "My_Stone", ("Setting", "Set"), set_on)
                put(ob, "My_Stone_Prongs", ("Prongs", "V at Corners"), False)
                before = evaluate(ob)[0]
                put(ob, "My_Stone_Prongs", ("Prongs", "V at Corners"), True)
                m = evaluate(ob)
                closed, inside = closed_outward(m[0], m[1]), inside_stone(m[0], unit, w, ln)
                # V на клетке: оболочки крапанов по числу вершин клетки V (92 / 146)
                only_prongs(ob)
                put(ob, "My_Stone", ("Setting", "Subdivision"), 0)
                cv, cf = evaluate(ob)[:2]
                n_v = sum(1 for part in shell_ids(cf, len(cv))
                          if len({i for k in part for i in cf[k]}) == (146 if set_on else 92))
                put(ob, "My_Stone", ("Setting", "Subdivision"), 2)
                pm = evaluate(ob)
                only_prongs(ob, False)
                bvh = BVHTree.FromPolygons(pm[0], pm[5])
                # стенка и длина крыла на первом угле: ниже рундиста (без сдвига по Tilt почти), вдали от рёбер
                c0, t1, t2 = corners[0]
                n1 = Vector((-t1.y, t1.x, 0.0))
                z = -0.3
                hits = ray_through(bvh, c0 + t1 * (vl * 0.6) + n1 * 3.0 + Vector((0, 0, z)), -n1)
                wall = ((hits[0] - hits[1]).length - vt) if len(hits) == 2 else 9.0
                um = (0.5 - ii) * vt
                end = bvh.ray_cast(c0 + t1 * (vl + 2.0) + n1 * um + Vector((0, 0, -0.05)), -t1, 50.0)[0]
                wing = ((end - c0).dot(t1) - vl) if end else 9.0
                put(ob, "My_Stone_Prongs", ("Prongs", "V at Corners"), False)
                same = len(before) == len(evaluate(ob)[0])
                tag = "V %s %s set %s" % (cut.lower(), typ.lower(), "on " if set_on else "off")
                print("%-27s %s(%d) %d  %d  %+.4f %+.4f %s" % (tag, closed[0], closed[1], inside, n_v, wall, wing, same))
                bad = closed != (True, 1) or inside or n_v != len(corners) or abs(wall) > 0.02 or abs(wing) > 0.02
                if bad or not same:
                    errors.append("%s: closed %s, inside %d, V %d/%d, wall %+.4f, wing %+.4f, V off same %s" % (
                        tag, closed, inside, n_v, len(corners), wall, wing, same))
        stack_defaults(ob, ss)


def check_tab(errors, ss, cutter):
    """Раздел 15: лапка (Tip = Tab) на трёх ветках."""
    print("tab case                    closed in  section ø x W          reach / end face")
    for cut, w, ln, diam in (("Round", 6.5, 6.5, bpy.data.objects["RWPRound"]), ("Emerald", 7.0, 10.0, None),
                             ("Oval", 5.0, 7.0, None)):
        ob = ss["setup"](cut, w, ln, diam=diam, cutter=cutter if cut == "Round" else None, name="Tab %s" % cut)
        stack_defaults(ob, ss)
        put(ob, "My_Stone_Prongs", (None, "Tip"), "Tab")
        unit = diam or get(ob, "My_Stone", (None, "Diam")) or bpy.data.objects["Unit " + cut]
        dia, tw = get(ob, "My_Stone_Prongs", ("Prongs", "ø")), get(ob, "My_Stone_Prongs", ("Prongs", "Tab Width"))
        keep = dia * (0.5 - get(ob, "My_Stone_Prongs", ("Prongs", "Intersection")) / 100.0)
        cov = get(ob, "My_Stone_Prongs", ("Prongs", "Set Cover")) / 100.0
        er = get(ob, "My_Stone", ("Setting", "Edge Round"))
        if cut == "Round":
            sites = [(Vector((pi_cos(a_), pi_sin(a_), 0.0)) * w / 2, Vector((pi_cos(a_), pi_sin(a_), 0.0)))
                     for a_ in (pi / 4 + k * pi / 2 for k in range(4))]
        elif cut == "Emerald":
            me_ = unit.data
            cx = w * (0.5 - max(abs(v.co.x) for v in me_.vertices if abs(v.co.y) >= 0.5 - 1e-4))
            cy = ln * (0.5 - max(abs(v.co.y) for v in me_.vertices if abs(v.co.x) >= 0.5 - 1e-4))
            sites = [(Vector((sx * (w / 2 - cx / 2), sy * (ln / 2 - cy / 2), 0.0)),
                      Vector((sx * cy, sy * cx, 0.0)).normalized()) for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
        else:
            sites = outline_sites(bpy.data.objects["Outline " + cut], w, ln)
        culet = min(v.co.z for v in unit.data.vertices) * w
        z_b = culet - get(ob, "My_Stone", ("Setting", "Below Culet"))
        for set_on in (False, True):
            put(ob, "My_Stone", ("Setting", "Set"), set_on)
            m = evaluate(ob)
            closed, inside = closed_outward(m[0], m[1]), inside_stone(m[0], unit, w, ln)
            only_prongs(ob)
            pm = evaluate(ob)
            only_prongs(ob, False)
            bvh = BVHTree.FromPolygons(pm[0], pm[5])
            o, n = sites[0]
            t = Vector((-n.y, n.x, 0.0))
            zm = z_b * 0.5                              # середина ствола под рундистом
            tilt = get(ob, "My_Stone", ("Setting", "Tilt"))
            ax = o + n * (keep + zm * tan(tilt)) + Vector((0, 0, zm))
            hn = ray_through(bvh, ax + n * 3.0, -n)
            ht = ray_through(bvh, ax + t * 3.0, -t)
            th = ((hn[0] - hn[1]).length - dia) if len(hn) == 2 else 9.0
            wd = ((ht[0] - ht[1]).length - tw) if len(ht) == 2 else 9.0
            note, bad = "", closed != (True, 1) or inside or abs(th) > 0.02 or abs(wd) > 0.02
            if set_on:
                if cut == "Round":
                    me_ = unit.data
                    zmax = max(v.co.z for v in me_.vertices)
                    paths = [w * (0.5 - max(v.co.xy.length for v in me_.vertices if v.co.z >= zmax * 0.999))] * 4
                else:
                    paths = site_paths(unit, w, ln, sites)
                reach = [r / p_ for r, p_ in zip(site_reach(m[0], sites), paths)]
                # торец: вершины лапки у самого дальнего по пути места (в пределах 0.005) — плоская грань
                us = [-(v - o).dot(n) for v in pm[0] if (v.xy - o.xy).length < 2.0 and v.z > 0.0]
                flat_n = sum(1 for u in us if u >= max(us) - 0.005)
                note = "reach %s end-face verts %d" % (" ".join("%.3f" % r for r in reach), flat_n)
                if cut != "Emerald" and any(not cov - 0.05 <= r <= cov + 0.03 for r in reach):
                    bad = True
                if flat_n < 9:
                    bad = True
            tag = "tab %s set %s" % (cut.lower(), "on " if set_on else "off")
            print("%-27s %s(%d) %d  %+.4f x %+.4f       %s" % (tag, closed[0], closed[1], inside, th, wd, note))
            if bad:
                errors.append("%s: closed %s, inside %d, ø %+.4f, W %+.4f %s" % (tag, closed, inside, th, wd, note))
        stack_defaults(ob, ss)


def check_crown(errors, ss, cutter):
    """Раздел 16: каст-корона (Type = Crown)."""
    print("crown case                  closed in  top at sites / midpoints     thick   depth 0 = Wall")
    rwp = bpy.data.objects["RWPRound"]
    cases = (("Round", 6.5, 6.5, rwp, {("My_Stone_Prongs", ("Prongs", "Count")): 4}, "count 4"),
             ("Round", 6.5, 6.5, rwp, {("My_Stone_Prongs", ("Prongs", "Count")): 6}, "count 6"),
             ("Emerald", 7.0, 10.0, None, {}, ""), ("Oval", 5.0, 7.0, None, {}, ""),
             ("Princess", 6.0, 6.0, None, {("My_Stone_Prongs", ("Prongs", "V at Corners")): True}, "V"))
    obs = {}
    for cut, w, ln, diam, vals, label_ in cases:
        ob = ss["setup"](cut, w, ln, diam=diam, cutter=cutter if cut == "Round" else None,
                         name="Crown %s %s" % (cut, label_))
        stack_defaults(ob, ss)
        put(ob, "My_Stone_Cast", (None, "Type"), "Crown")
        for k, v_ in vals.items():
            put(ob, k[0], k[1], v_)
        unit = diam or get(ob, "My_Stone", (None, "Diam")) or bpy.data.objects["Unit " + cut]
        z_t, xy, th = (get(ob, "My_Stone_Cast", ("Cast", k)) for k in ("Z Offset", "XY Offset", "Cast Thickness"))
        depth = get(ob, "My_Stone_Cast", ("Crown", "Crown Depth"))
        tilt = get(ob, "My_Stone", ("Setting", "Tilt"))
        if cut == "Round":
            cnt = vals[("My_Stone_Prongs", ("Prongs", "Count"))]
            angs = [pi / 4 + k * pi / cnt for k in range(2 * cnt)]
            pts = [(Vector((pi_cos(a_), pi_sin(a_), 0.0)) * w / 2, Vector((pi_cos(a_), pi_sin(a_), 0.0)), k % 2)
                   for k, a_ in enumerate(angs)]
        elif cut == "Emerald":
            me_ = unit.data
            cx = w * (0.5 - max(abs(v.co.x) for v in me_.vertices if abs(v.co.y) >= 0.5 - 1e-4))
            cy = ln * (0.5 - max(abs(v.co.y) for v in me_.vertices if abs(v.co.x) >= 0.5 - 1e-4))
            pts = [(Vector((sx * (w / 2 - cx / 2), sy * (ln / 2 - cy / 2), 0.0)),
                    Vector((sx * cy, sy * cx, 0.0)).normalized(), 0) for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
            pts += [(Vector((w / 2, 0, 0)), Vector((1, 0, 0)), 1), (Vector((-w / 2, 0, 0)), Vector((-1, 0, 0)), 1),
                    (Vector((0, ln / 2, 0)), Vector((0, 1, 0)), 1), (Vector((0, -ln / 2, 0)), Vector((0, -1, 0)), 1)]
        elif cut == "Oval":
            pts = [(o, n, 0) for o, n in outline_sites(bpy.data.objects["Outline Oval"], w, ln)]
            pts += [(Vector((w / 2, 0, 0)), Vector((1, 0, 0)), 1), (Vector((-w / 2, 0, 0)), Vector((-1, 0, 0)), 1),
                    (Vector((0, ln / 2, 0)), Vector((0, 1, 0)), 1), (Vector((0, -ln / 2, 0)), Vector((0, -1, 0)), 1)]
        else:
            pts = [(Vector((sx * w / 2, sy * ln / 2, 0)), Vector((sx, sy, 0)).normalized(), 0)
                   for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1))]
            pts += [(Vector((w / 2, 0, 0)), Vector((1, 0, 0)), 1), (Vector((-w / 2, 0, 0)), Vector((-1, 0, 0)), 1),
                    (Vector((0, ln / 2, 0)), Vector((0, 1, 0)), 1), (Vector((0, -ln / 2, 0)), Vector((0, -1, 0)), 1)]
        m = evaluate(ob)
        closed, inside = closed_outward(m[0], m[1]), inside_stone(m[0], unit, w, ln)
        # верх и толщина — на стенке без My_Setting_Bool (крапана нужны: места короны — их)
        mod(ob, "My_Setting_Bool").show_viewport = False
        rm = evaluate(ob)
        mod(ob, "My_Setting_Bool").show_viewport = True
        bvh = BVHTree.FromPolygons(rm[0], rm[5])
        err_s = err_m = 0.0
        for o, n, is_mid in pts:
            # середина стенки; в углу (острая вершина) — по биссектрисе с митрой
            k_ = 1.0 / max(n.dot((o.xy.normalized()).to_3d()), 0.5) if cut == "Princess" and not is_mid else 1.0
            dmid = (xy - th / 2) * (1.4142 if cut == "Princess" and not is_mid else 1.0)
            want = z_t - (depth if is_mid else 0.0)
            hit = bvh.ray_cast(o + n * (dmid + want * tan(tilt)) + Vector((0, 0, 5.0)), Vector((0, 0, -1)), 20.0)[0]
            e = (hit.z - want) if hit else 9.0
            if is_mid:
                err_m = max(err_m, e, key=abs)
            else:
                err_s = max(err_s, e, key=abs)
        o, n, _m = next(q for q in pts if q[2])
        zc = (z_t - depth + min(p_.z for p_ in rm[0])) / 2
        hits = ray_through(bvh, o + n * 3.0 + Vector((0, 0, zc)), -n)
        thick = ((hits[0] - hits[1]).length - th) if len(hits) == 2 else 9.0
        put(ob, "My_Stone_Cast", ("Crown", "Crown Depth"), 0.0)
        a = evaluate(ob)[0]
        put(ob, "My_Stone_Cast", (None, "Type"), "Wall")
        put(ob, "My_Stone_Cast", ("Cast", "CastBool"), False)
        b_ = evaluate(ob)[0]
        same = len(a) == len(b_) and all((p_ - q).length < 1e-6 for p_, q in zip(a, b_))
        stack_defaults(ob, ss)
        put(ob, "My_Stone_Cast", (None, "Type"), "Crown")
        for k, v_ in vals.items():
            put(ob, k[0], k[1], v_)
        tag = "crown %s %s" % (cut.lower(), label_)
        print("%-27s %s(%d) %d  %+.4f / %+.4f              %+.4f  %s" % (tag, closed[0], closed[1], inside, err_s, err_m,
                                                                    thick, same))
        if closed != (True, 1) or inside or abs(err_s) > 0.03 or abs(err_m) > 0.03 or abs(thick) > 0.01 or not same:
            errors.append("%s: closed %s, inside %d, top %+.4f / %+.4f, thick %+.4f, depth 0 same %s" % (
                tag, closed, inside, err_s, err_m, thick, same))
        obs[(cut, label_)] = (ob, unit, w, ln)
    return obs


def check_edge_round(errors, ss):
    """Раздел 17: скругление рёбер новых деталей — врез от идеального острого угла (по биссектрисе) на лапке
    и на крыле V, камни 2 и 10 мм, одно Edge Round; Edge Round 0 — острое."""
    rwp = bpy.data.objects["RWPRound"]
    res = {}
    for size in (2.0, 10.0):
        tob = ss["setup"]("Round", size, size, diam=rwp, name="ER Tab %g" % size)
        stack_defaults(tob, ss)
        put(tob, "My_Stone_Prongs", (None, "Tip"), "Tab")
        vob = ss["setup"]("Princess", size, size, name="ER V %g" % size)
        stack_defaults(vob, ss)
        put(vob, "My_Stone_Prongs", ("Prongs", "V at Corners"), True)
        proto = bpy.data.objects["Outline Princess"]
        corner = corner_frames(proto, size, size, outline_sites(proto, size, size))[0]
        for er in (0.08, 0.0):
            row = []
            for ob in (tob, vob):
                put(ob, "My_Stone", ("Setting", "Edge Round"), er)
                only_prongs(ob)
                pm = evaluate(ob)
                only_prongs(ob, False)
                bvh = BVHTree.FromPolygons(pm[0], pm[5])
                dia = get(ob, "My_Stone_Prongs", ("Prongs", "ø"))
                tilt = get(ob, "My_Stone", ("Setting", "Tilt"))
                z = -0.3
                if ob is tob:
                    # наружное вертикальное ребро лапки на 45°: угол (ø/2 наружу от оси, Tab Width/2 вбок)
                    nn = Vector((0.7071, 0.7071, 0.0))
                    tt = Vector((-nn.y, nn.x, 0.0))
                    keep = dia * (0.5 - get(ob, "My_Stone_Prongs", ("Prongs", "Intersection")) / 100.0)
                    ax = nn * (size / 2 + keep + z * tan(tilt)) + Vector((0, 0, z))
                    ideal = ax + nn * dia / 2 + tt * get(ob, "My_Stone_Prongs", ("Prongs", "Tab Width")) / 2
                    bis = (nn + tt).normalized()
                else:
                    # наружное вертикальное ребро конца крыла 1: торец x наружная грань
                    c0, t1, _t2 = corner
                    n1 = Vector((-t1.y, t1.x, 0.0))
                    vt, vl = (get(ob, "My_Stone_Prongs", ("Prongs", k)) for k in ("V Thickness", "V Length"))
                    ii = get(ob, "My_Stone_Prongs", ("Prongs", "Intersection")) / 100.0
                    bis_o = -(t1 + _t2).normalized()
                    ideal = c0 + t1 * vl + n1 * ((1 - ii) * vt) + bis_o * (z * tan(tilt)) + Vector((0, 0, z))
                    bis = (n1 + t1).normalized()
                hit = bvh.ray_cast(ideal + bis * 1.0, -bis, 5.0)[0]
                row.append((hit - ideal).length if hit else 9.0)
            res[(size, er)] = row
        put(tob, "My_Stone", ("Setting", "Edge Round"), 0.08)
        put(vob, "My_Stone", ("Setting", "Edge Round"), 0.08)
    er = 0.08
    print("edge round 0.08: cut-back tab %.4f / %.4f, V wing %.4f / %.4f (stone 2 / 10 mm, %.2f..%.2f of Edge Round); "
          "Edge Round 0: %.4f %.4f / %.4f %.4f" % (res[(2.0, er)][0], res[(10.0, er)][0], res[(2.0, er)][1],
                                                     res[(10.0, er)][1], min(res[(2.0, er)] + res[(10.0, er)]) / er,
                                                     max(res[(2.0, er)] + res[(10.0, er)]) / er,
                                                     *res[(2.0, 0.0)], *res[(10.0, 0.0)]))
    for k in (0, 1):
        a, b_ = res[(2.0, er)][k], res[(10.0, er)][k]
        if not (0.2 * er <= a <= er and 0.2 * er <= b_ <= er) or abs(a - b_) > 0.2 * max(a, b_):
            errors.append("edge round %s: cut-back %.4f / %.4f" % (("tab", "V")[k], a, b_))
        if res[(2.0, 0.0)][k] > 0.002 or res[(10.0, 0.0)][k] > 0.002:
            errors.append("edge round 0 %s: cut-back %.4f / %.4f" % (("tab", "V")[k], res[(2.0, 0.0)][k],
                                                                      res[(10.0, 0.0)][k]))


CAST_ROUND_TYPES = (("Wall", None), ("Bezel", None), ("Basket", "Flat"), ("Basket", "Round"), ("Crown", None))


def check_cast_round(errors, ss):
    """Раздел 18: Edge Round на касте, 17 огранок x 5 типов."""
    gems = ss["mods"]()[2].load_module("gem_cast_gems", ss["mods"]()[2].GEMS_PATH)
    er = 0.08
    worst = {"out": (0.0, ""), "cut": (0.0, ""), "lip": (0.0, "")}
    print("cast round case            shells at 0 / 0.08 / 0.3   outside   cut-back")
    for cut in ss["CUTS"]:
        w, ln = cut_size(gems, cut)
        ob = ss["setup"](cut, w, ln, name="All %s" % cut)
        unit = get(ob, "My_Stone", (None, "Diam")) or ss["builtin_stone"](cut.upper())
        outline, _zg = girdle_outline(unit, w, ln)
        hide = [mod(ob, g) for g in ("My_Stone_Prongs", "My_Setting_Bool")]
        for kind, shape in CAST_ROUND_TYPES:
            stack_defaults(ob, ss)
            put(ob, "My_Stone_Prongs", ("Prongs", "ø"), ALL_DIA)
            put(ob, "My_Stone_Cast", (None, "Type"), kind)
            if shape:
                put(ob, "My_Stone_Cast", ("Basket", "Rail Shape"), shape)
            tag = "cast round %s %s" % (cut.lower(), (kind + (" " + shape if shape else "")).lower())
            full, cast = {}, {}
            for e in (0.0, er, 0.3):
                put(ob, "My_Stone", ("Setting", "Edge Round"), e)
                hide[0].show_viewport = kind != "Bezel"          # глухой каст — без крапанов
                m = evaluate(ob)
                full[e] = closed_outward(m[0], m[1])
                if e < 0.3 and kind != "Crown":
                    for md in hide:
                        md.show_viewport = False
                    cast[e] = evaluate(ob)
                    for md in hide:
                        md.show_viewport = True
            bad = []
            for e in (er, 0.3):
                if not full[e][0] or full[e][1] > full[0.0][1]:
                    bad.append("Edge Round %g: closed %s, shells %d (%d at 0)" % (e, full[e][0], full[e][1], full[0.0][1]))
            out = cutb = 0.0
            if cast:
                sharp, soft = cast[0.0], cast[er]
                bvh0 = BVHTree.FromPolygons(sharp[0], sharp[5])
                out = max((bvh0.find_nearest(v)[3] for v in soft[0] if outside(bvh0, v)), default=0.0)
                bvh1 = BVHTree.FromPolygons(soft[0], soft[5])
                cutb = max(bvh1.find_nearest(v)[3] for v in sharp[0])
                held = shape != "Round"
                if out > 0.5 * er or cutb > 1.5 * er or (held and cutb < 0.2 * er):
                    bad.append("metal added %.4f, corner cut-back %.4f" % (out, cutb))
                if kind == "Wall" or shape == "Flat":
                    dz = max(abs(max(v.z for v in soft[0]) - max(v.z for v in sharp[0])),
                             abs(min(v.z for v in soft[0]) - min(v.z for v in sharp[0])))
                    if dz > 1e-4:
                        bad.append("top / bottom moved %.5f" % dz)
                for key, val in (("out", out), ("cut", cutb)):
                    if val > worst[key][0]:
                        worst[key] = (val, tag)
            if kind == "Bezel":
                # Set: заход губы (верхняя половина каста, от контура камня внутрь) и габарит Round — как при
                # Edge Round 0; у огранок с острыми вершинами губа во внутренних углах — с галтелью
                put(ob, "My_Stone", ("Setting", "Set"), True)
                hide[0].show_viewport = hide[1].show_viewport = False
                reach, span, half = [], [], None
                for e in (0.0, er):
                    put(ob, "My_Stone", ("Setting", "Edge Round"), e)
                    verts = evaluate(ob)[0]
                    half = half or 0.5 * max(v.z for v in verts)
                    reach.append(-min(signed_distance(v.xy, outline) for v in verts if v.z > half))
                    span.append(max(v.xy.length for v in verts))
                hide[0].show_viewport = hide[1].show_viewport = True
                lip = abs(reach[1] - reach[0])
                smooth_path = cut in ("Round", "Oval", "Cushion")
                if lip > (0.01 if smooth_path else 0.5 * er) or (cut == "Round" and abs(span[1] - span[0]) > 1e-3):
                    bad.append("Set: lip %.4f -> %.4f, radius %.4f -> %.4f" % (reach[0], reach[1], span[0], span[1]))
                if lip > worst["lip"][0]:
                    worst["lip"] = (lip, tag)
            print("%-28s %d / %d / %d   %.4f   %.4f%s" % (tag, full[0.0][1], full[er][1], full[0.3][1], out, cutb,
                                                         "" if not bad else "   " + "; ".join(bad)))
            errors.extend("%s: %s" % (tag, e) for e in bad)
        stack_defaults(ob, ss)
    print("cast round worst: metal added %.4f (%s), cut-back %.4f = %.2f Edge Round (%s), Set lip change %.4f (%s)" % (
        worst["out"][0], worst["out"][1], worst["cut"][0], worst["cut"][0] / er, worst["cut"][1],
        worst["lip"][0], worst["lip"][1]))


def render_new_types(ss, crowns):
    """Pear V + два круглых | Princess четыре V, Set | Emerald лапки, Set | Round корона 4 | Round корона 6;
    ряды — 3/4 и сверху (у корон — сбоку)."""
    cells = []
    cfg = [("Pear", 6.0, 9.0, None, {("My_Stone_Prongs", ("Prongs", "V at Corners")): True}, "Pear: V + two round"),
           ("Princess", 6.0, 6.0, None, {("My_Stone_Prongs", ("Prongs", "V at Corners")): True,
                                         ("My_Stone", ("Setting", "Set")): True}, "Princess: four V, Set"),
           ("Emerald", 7.0, 10.0, None, {("My_Stone_Prongs", (None, "Tip")): "Tab",
                                         ("My_Stone", ("Setting", "Set")): True}, "Emerald: tabs, Set")]
    for col, (cut, w, ln, diam, vals, text_) in enumerate(cfg):
        ob = ss["setup"](cut, w, ln, name="Sheet %s" % cut)
        stack_defaults(ob, ss)
        for k, v_ in vals.items():
            put(ob, k[0], k[1], v_)
        unit = get(ob, "My_Stone", (None, "Diam")) or bpy.data.objects["Unit " + cut]
        me = freeze(ob)
        cells.append((col, 0, text_, me, unit.data, w, ln))
        cells.append((col, 1, "top", me, unit.data, w, ln, "top"))
    for col, key in ((3, ("Round", "count 4")), (4, ("Round", "count 6"))):
        ob, unit, w, ln = crowns[key]
        me = freeze(ob)
        cells.append((col, 0, "Round: crown, %s" % key[1], me, unit.data, w, w))
        cells.append((col, 1, "side", me, unit.data, w, w, "side"))
    render_cells(PREVIEW_NEW, "V-prong, tab prong, crown cast", cells, (2600, 0))


# --- лист превью ----------------------------------------------------------------------------------

def freeze(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    return bpy.data.meshes.new_from_object(ob.evaluated_get(dg))


def render_cells(path, title, cells, size):
    """Лист: cells = [(колонка, ряд, подпись, меш металла, меш камня-единицы, W, L[, вид])], вид 3/4,
    каждая ячейка в одном экранном размере; вид "top" — сборка довёрнута осью Z к камере (вид сверху той же
    камерой), "side" — довёрнута вокруг горизонтали экрана: взгляд ~10° над горизонтом. Рендер — в отдельной сцене только с листом (объекты корня тестовой
    сцены не исключить)."""
    cols = max(c[0] for c in cells) + 1
    rows = max(c[1] for c in cells) + 1
    scene = bpy.data.scenes.new("Sheet " + path.stem)
    scene.world = bpy.data.worlds.new("Sheet World")
    scene.world.use_nodes = False      # иначе Workbench берёт фон из узлов мира
    scene.world.color = (1.0, 1.0, 1.0)
    view = bpy.data.collections.new("Sheet")
    scene.collection.children.link(view)
    rot = Euler((radians(58), 0.0, radians(32)))
    m = rot.to_matrix()
    right, fwd, upv = m @ Vector((1, 0, 0)), m @ Vector((0, 0, -1)), m @ Vector((0, 1, 0))
    gap, show, row_gap = 5.0, 3.2, 5.0
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    view.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = (cols + 0.2) * gap
    cam.matrix_world = Matrix.Translation(-fwd * 30.0 - upv * 0.3) @ m.to_4x4()

    def text(body, x, y, size_):
        cu = bpy.data.curves.new("t", "FONT")
        cu.body, cu.size, cu.align_x = body, size_, "CENTER"
        t = bpy.data.objects.new("t", cu)
        view.objects.link(t)
        t.parent = cam
        t.location = (x, y, -5.0)
        t.color = (0.0, 0.0, 0.0, 1.0)
    height = rows * row_gap + 1.6
    text(title, 0.0, height / 2 - 0.9, 0.45)
    for col, rw, label, me, unit, w, ln, *top in cells:
        x, y = (col - (cols - 1) / 2) * gap, ((rows - 1) / 2 - rw) * row_gap - 0.4
        at = right * x + upv * y
        view_ = top[0] if top else None
        turn = (m.to_4x4() if view_ == "top" else Matrix.Rotation(radians(-22.0), 4, right) if view_ == "side"
                else Matrix.Identity(4))
        k = show / max(w, ln)
        mo = bpy.data.objects.new("m", me)
        view.objects.link(mo)
        mo.matrix_world = Matrix.Translation(at) @ turn @ Matrix.Scale(k, 4)
        mo.color = (0.86, 0.66, 0.24, 1.0)
        st = bpy.data.objects.new("s", unit)
        view.objects.link(st)
        st.matrix_world = Matrix.Translation(at) @ turn @ Matrix.Diagonal((w * k, ln * k, w * k, 1.0))
        st.color = (0.72, 0.84, 1.0, 1.0)
        text(label, x, y - 2.8, 0.4)
    scene.camera = cam
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = size[0]
    scene.render.resolution_y = int(size[0] * height / cam.data.ortho_scale)
    scene.render.resolution_percentage = 100
    scene.display.render_aa = "16"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.show_cavity = True
    scene.display.shading.background_type = "VIEWPORT"
    scene.display.shading.background_color = (1.0, 1.0, 1.0)
    scene.view_settings.view_transform = "Standard"
    path.parent.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(path)
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.film_transparent = False
    bpy.ops.render.render(write_still=True, scene=scene.name)
    print("preview: %s" % path)


def label(ob, w, ln, set_on):
    size = "ø %g mm" % w if w == ln else "%g x %g mm" % (w, ln)
    return "%s %s%s" % (get(ob, "My_Stone", (None, "Cut")), size, ", Set" if set_on else "")


def render_sheet(ss, round_ob, em_ob):
    """Round 2 мм и Emerald 4 x 6 стеком, без Set и с Set."""
    cells = []
    for ob in (round_ob, em_ob):
        stack_defaults(ob, ss)
        w, ln = get(ob, "My_Stone", ("Stone", "Width")), get(ob, "My_Stone", ("Stone", "Length"))
        if get(ob, "My_Stone", (None, "Cut")) == "Round":
            ln = w
        diam = get(ob, "My_Stone", (None, "Diam"))
        for set_on in (False, True):
            put(ob, "My_Stone", ("Setting", "Set"), set_on)
            cells.append((len(cells), 0, label(ob, w, ln, set_on), freeze(ob), diam.data, w, ln))
        stack_defaults(ob, ss)
    render_cells(PREVIEW, "My_Stone + My_Stone_Prongs + My_Stone_Cast + My_Setting_Bool", cells, (1800, 0))


def render_bezel_sheet(ss, obs):
    """Глухой каст: Round 2, Round 6.5, Emerald 4 x 6; верх — без Set, низ — Set; четверть срезана кубом
    через BoolObject, чтобы была видна посадка."""
    quarter = bpy.data.objects.new("Quarter Cut", bpy.data.meshes.new("Quarter Cut"))
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=40.0)
    bm.to_mesh(quarter.data)
    bm.free()
    bpy.context.scene.collection.objects.link(quarter)
    quarter.location = (20.0, -20.0, 0.0)     # x > 0, y < 0 — четверть к камере
    cells = []
    for col, ob in enumerate(obs[:3]):
        w, ln = get(ob, "My_Stone", ("Stone", "Width")), get(ob, "My_Stone", ("Stone", "Length"))
        if get(ob, "My_Stone", (None, "Cut")) == "Round":
            ln = w
        stack_defaults(ob, ss)
        put(ob, "My_Stone_Cast", (None, "Type"), "Bezel")
        put(ob, "My_Setting_Bool", ("Bool", "BoolObject"), quarter)
        for rw, set_on in enumerate((False, True)):
            put(ob, "My_Stone", ("Setting", "Set"), set_on)
            cells.append((col, rw, label(ob, w, ln, set_on), freeze(ob), get(ob, "My_Stone", (None, "Diam")).data,
                          w, ln))
        stack_defaults(ob, ss)
    render_cells(PREVIEW_BEZEL, "My_Stone_Cast: Bezel (quarter cut away)", cells, (1500, 0))


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    paths = [a for a in args if a.endswith(".blend")]
    if paths and Path(bpy.data.filepath or "") != Path(paths[0]):
        bpy.ops.wm.open_mainfile(filepath=paths[0])
    errors = []
    ss = load(BUILD, "stone_setting_build")
    rns = load(ROUND_BUILD, "round_cast_build")
    gns = load(GEM_BUILD, "gem_cast_build")
    diam, cutter = bpy.data.objects["RWPRound"], bpy.data.objects["Cutter"]
    round_ob = check_round(errors, ss, rns, diam, cutter)
    check_emerald(errors, ss, gns)
    em_ob = bpy.data.objects["Emerald 4x6 Setting"]
    groups = {g: bpy.data.node_groups[g] for g in ss["ORDER"]}
    obj, coll = check_bools(errors, ss, round_ob, diam)
    check_cages(errors, ss, (round_ob, em_ob), obj)
    check_stone(errors, ss, round_ob, diam)
    check_builtin(errors, ss, (round_ob, em_ob))
    check_material(errors, ss, (round_ob, em_ob))
    check_stones(errors, ss, groups, round_ob, "round 2", False)
    check_stones(errors, ss, groups, em_ob, "emerald 4x6, set", True)
    check_rebuild(errors, ss, (round_ob, em_ob), cutter, coll)
    bezels = check_bezel(errors, ss, bpy.data.objects["Unit Emerald"])
    claws = check_claw(errors, ss, cutter, bpy.data.objects["Unit Emerald"])
    baskets = check_basket(errors, ss, cutter, bpy.data.objects["Unit Emerald"])
    cuts = check_cuts(errors, ss, gns, round_ob, em_ob)
    check_all_cuts(errors, ss)
    points = check_points(errors, ss, cutter)
    check_v(errors, ss)
    check_tab(errors, ss, cutter)
    crowns = check_crown(errors, ss, cutter)
    check_edge_round(errors, ss)
    check_cast_round(errors, ss)
    print("nodes: %s" % ", ".join("%s %d" % (g, len(groups[g].nodes)) for g in ss["ORDER"]))
    if "--preview" in args:
        render_sheet(ss, round_ob, em_ob)
        render_bezel_sheet(ss, bezels)
        render_claw_sheet(ss, claws)
        render_basket_sheet(ss, baskets)
        render_cuts_sheet(ss, cuts)
        render_points_sheet(ss, points)
        render_new_types(ss, crowns)
        render_all_cuts(ss, PREVIEW_ALL, "All cuts: Wall + Round prongs, Set", {("My_Stone", ("Setting", "Set")): True})
        render_all_cuts(ss, PREVIEW_ALL_BEZEL, "All cuts: Bezel, Set",
                        {("My_Stone_Cast", (None, "Type")): "Bezel", ("My_Stone", ("Setting", "Set")): True}, prongs=False)
    for e in errors:
        print("FAIL", e)
    print("STONE_SETTING_TEST", "failed" if errors else "passed")
    if errors:
        sys.exit(1)


try:
    main()
except SystemExit:
    raise
except Exception:
    traceback.print_exc()
    sys.exit(1)
