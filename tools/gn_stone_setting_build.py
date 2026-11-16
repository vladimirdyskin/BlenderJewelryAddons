"""
Каст с крапанами из четырёх групп — модификаторы одного стека на одном объекте:
    My_Stone -> My_Stone_Prongs -> My_Stone_Cast -> My_Setting_Bool.
Та же геометрия, что у монолитов My_Round_Cast (tools/gn_round_cast_build.py) и My_Gem_Cast
(tools/gn_gem_cast_build.py), только для двух огранок: Round и Emerald.

Канал данных — атрибуты на инстансе камня (домен INSTANCE), как у связки My_Gems_Curve:
    gem_r (W/2, > 0 — это камень), gem_size (Width), gem_length, gem_cut (0 Round, 1 Emerald),
    gem_table, gem_culet (мм, Bounding Box камня-единицы * Width), gem_crown (путь по короне:
    Width * (0.5 - край площадки); Round — max length(xy) вершин площадки, Emerald — max |x|),
    gem_cx, gem_cy (срез угла изумруда вдоль X и вдоль Y, мм; Round — 0), set_tilt, set_below,
    set_subdiv, set_on. Следующие группы читают их одним значением: индекс первого инстанса
    с gem_r > 0 (Attribute Statistic) -> Sample Index. На инстансе камня не делать Remove Attribute /
    Merge by Distance / Set Material / Delete Geometry — JewelCraft должен видеть инстанс Diam.

My_Stone: камень-единица Diam (габарит XY 1 x 1 по центру, рундист на z = 0). Diam пуст (или без
    меша) — встроенный камень огранки Cut: Round — RWPRound, Emerald — Unit Emerald (builtin_stone);
    объекты записаны в узле, с ассетом приходят в файл сами. Stone Material: задан — Set Material на
    показанном камне (инстанс становится копией меша, JewelCraft такой камень не видит); пуст — камень
    не трогается. «Пуст» узлами: грань пробной сетки после Set Material(пусто) попадает в Material
    Selection без материала. ShowStone — инстанс
    объекта Diam с масштабом (W, L, W); выключен — невидимый носитель: инстанс меша Diam
    (Object Info без As Instance -> Geometry to Instance) с масштабом 0. Атрибуты те же, камень
    восстанавливается сбросом матрицы инстанса на масштаб (W, L, W). Round: L = W.
    Срез угла изумруда — по мешу: среди вершин с |y| >= 0.5 - EPS max |x| = 0.5 - cx, и наоборот.
My_Stone_Prongs: низ крапана плоский на gem_culet - set_below, вровень с низом каста: клетка строится ниже на
    ø tan |T|, после Subdivision вершины ниже этой плоскости поднимаются на неё (Flat Foot).
    Клетка build_prong_cage из gn_round_cast_build.py (Set = set_on), сдвиг и наклон,
    Subdivision Surface уровнем set_subdiv (0 — голая клетка с crease_edge). Места: Round — Count
    точек на окружности W/2 + ø * (0.5 - I/100), поворот ° Z; Emerald — 4 середины срезов углов
    + n * ø * (0.5 - I/100), n — наружная нормаль среза. Ось X крапана — по n.
    Aim Center (только огранки с контуром): ось X крапана — от нормали контура (0) к радиусу от центра камня (100 %).
    Tip = Claw — крапан-коготь (build_claw_cage), клетка 16 вершин: без Set — прямое острие (4 кольца:
    основание, шейка, плечо на площадке + Above Table, кончик на Claw Length ø выше, Claw Tip % от hb);
    Set — коготь дугой по прежним крапанам Владимира (4 кольца: пятка, колено, плечо на рундисте,
    кончик-клин): верх крюка на Set Height % высоты площадки, остриё на Set Cover % пути по короне,
    Claw Bow — выгиб ноги наружу от прямой (мм), Claw Swell — утолщение у колена (%). Round — как был.
    Места крапанов: вершины без рёбер собственного меша объекта (мм) > вершины без рёбер Outline > встроенные;
    место — его проекция на предел петли рундиста (поставленная примерно точка садится на рундист).
    Путь по короне на контуре — свой у каждого места (до края площадки по нормали места), один на все —
    минимум; корона когтя на контуре начинается с верха рундиста у места с кратчайшим путём.
My_Stone_Cast: стенка как у монолитов (верх Z Offset, низ gem_culet - set_below, наклон set_tilt,
    высота не меньше MIN_CAST), прорезь посередине высоты. Одна ветка на обе огранки: путь из
    8 точек x профиль 4 точки через Curve to Mesh (только топология), на точке пути P (контур) и
    B (сдвиг на единицу отступа), на точке профиля (d, z): Set Position = P + B d на высоте z.
    Round: P = dir W/2 / CAST_SHRINK, B = dir / CAST_SHRINK, dir через 45°, crease 1 на рёбрах вдоль
    пути. Emerald: P — вершины восьмиугольника рундиста, B = (n1 + n2) / (1 + n1 . n2) (точная
    митра), crease 1 на всех рёбрах.
    Type = Bezel — глухой каст: тот же путь, профиль 7 точек (клетка 56 вершин), d — от контура
    рундиста наружу, z — от плоскости рундиста; h = gem_table, c = gem_crown, zb = gem_culet -
    set_below, zt = Height% h, cov = Bezel Cover% c, clr = BEZEL_CLEAR * W, d_out(z) = Wall + z tan T,
    d_in(z) = d_out(z) - (Wall + Seat), верх — плоскость через (0, zt), наружу вниз на BEZEL_BEVEL.
        Не Set: (d_out(zb), zb), (Wall, 0), верх снаружи и внутри при d_out(zt) / d_in(zt),
            (d_in(zt/2), zt/2), (d_in(0), 0), (d_in(zb), zb).
        Set: губа (-cov, zt) — (-cov, 0) уходит в камень (рез камнем даёт контакт ровно на cov),
            наружный верх d3 = d_out(zt) - (cov + clr). Низ открыт (трубка), прорези нет.
        Своя посадка (как у My_Setting_Bool, общие помощники stone_mesh / seat_operands): Bezel Cutter
        или авто-катер (копия камня калеттой над верхом каста), Set — оболочка камня и Bezel Cutter
        ниже рундиста. Камень в потоке помечается set_seated — My_Setting_Bool посадку и оболочку камня
        не режет второй раз. В режиме Stones носителя в потоке нет — пометить нечего.
    Type = Basket — корзинка: два замкнутых ранта по тому же пути (клетка 2 x 8 x 4 = 64), сечение t x Rail
        (t = Cast Thickness), наружная линия d_out(z) = XY Offset + z tan T (рант идёт по наклону крапанов);
        верхний — верх на Z Offset, нижний — низ на gem_culet - set_below; Rail не больше высоты каста.
        Upper Rail выключен — только нижний рант (клетка 8 x 4 = 32).
        Rail Shape Round — круглый/овальный провод (SubD без crease вдоль пути, клетка больше в RAIL_EDGE),
        Flat — точный прямоугольник (crease вдоль пути). Emerald — углы пути острые. Посадку режет
        My_Setting_Bool, прорези нет.
    Edge Round (set_round) > 0 — рёбра каста скруглены: вместо crease у каждого угла сечения две опорные точки
        на EDGE_HOLD * Edge Round от него (не дальше HOLD_MAX стороны) — hold_corners; грани остаются плоскими
        и на месте, срезается сам угол (около 0.35 Edge Round у прямого). Круглый рант — без них. Вертикальные
        рёбра: так же опорные точки пути у острой вершины с поворотом меньше 60° (срезы изумруда, ашера,
        октагона), у глухого каста — у всех острых; прямые и острые углы остальных типов остаются острыми
        (в них стоят крапана, скругление отодвинуло бы угол каста от крапана). У глухого каста острыми остаются
        наружное ребро на рундисте и внутренний угол губы Set (размер Wall и заход Bezel Cover точные).
        Рёбра булеанов (прорезь, посадка, край расточки) не скругляются. Edge Round 0 — клетка прежняя.
    Stones (у Prongs и Cast): задан — атрибуты камня с вычисленной геометрии этого объекта, своя
    геометрия переносится в координаты своего объекта (Transform у Object Info Relative).
My_Setting_Bool: меш — металл, инстансы проходят нетронутыми и присоединяются в конце.
    set_subdiv = 0 (камень есть) — всё насквозь без изменений. Металл — острова (Mesh Island ->
    Split to Instances), каждый — отдельный операнд Manifold.
    BoolCutter: Union(острова) - посадка - общие резаки. Посадка без Set: Cutter * (W, L, W) или
        авто-катер My_Gem_Cast (оболочка камня * CUTTER_GROW по XY и его копии над верхом металла);
        Set: оболочка камня * SET_GROW по XY и Cutter ниже z = -SET_CLIP * W (Cutter пуст — без
        пересечения: Intersect с пустым операндом даёт сам ящик).
    Без BoolCutter: оболочки отдельно, каждый остров минус (общие резаки + оболочка камня при Set) —
        For Each по инстансам-островам; вычитать нечего — металл как есть.
    Общие резаки: BoolObject и объекты BoolCollection (Relative, Separate Children) — отдельные
    операнды, при любом BoolCutter. Камень для оболочек — копия инстанса камня из потока.
    Затем Smooth by Angle 30°, Realize All; ShowCutter показывает использованные операнды посадки.
    Камень с set_seated (посажен глухим кастом): без посадки и оболочки камня, union и общие резаки — как обычно.

Интерфейс: ensure_interface из gn_round_cast_build.py (ключ — панель + имя, сокеты только
добавляются, узлы пересобираются). Cut (Menu Switch): значение на модификаторах запоминается
до пересборки и возвращается после (новые id пунктов меню). Помощник B — gn_prongs_build.py.
"""

import bpy
import importlib.util
import os
from math import pi, tan

REPO = os.path.expanduser("~/GitHub/BlenderJewelryAddons")
PRONGS_PATH = os.path.join(REPO, "tools", "gn_prongs_build.py")
ROUND_PATH = os.path.join(REPO, "tools", "gn_round_cast_build.py")
GEM_PATH = os.path.join(REPO, "tools", "gn_gem_cast_build.py")
OUTLINE_PATH = os.path.join(REPO, "jewel_tools", "gem_outline.py")

STONE, PRONGS, CAST, BOOL = "My_Stone", "My_Stone_Prongs", "My_Stone_Cast", "My_Setting_Bool"
ORDER = (STONE, PRONGS, CAST, BOOL)
# номера пунктов не менять: на модификаторах хранится имя пункта, а gem_cut — номер (Round 0, Emerald 1)
CUTS = ["Round", "Emerald", "Oval", "Pear",
        # этап 2 — в порядке parametric_gems, только дописываются в конец
        "Cushion", "Marquise", "Princess", "Baguette", "Square", "Asscher", "Radiant", "Flanders", "Octagon",
        "Heart", "Trillion", "Trilliant", "Triangle"]
# места крапанов по умолчанию для всех огранок (Outline <Cut>), в настоящих пропорциях камня
# base_width x base_length: diag — 4 точки предела к диагоналям габарита; corners — острые вершины;
# cuts — середины 4 кратчайших пролётов угол-угол; tips — 3 дальних острых вершины не ближе 60°;
# even — от дальнего острого угла поровну по длине контура; третий элемент — какие из шагов оставить
# (груша: остриё и два на головке, без боковых — так стоит в библиотеке Владимира)
RULES = {"ROUND": ("diag",), "OVAL": ("diag",), "CUSHION": ("diag",),
         "PEAR": ("even", 5, (0, 2, 3)), "MARQUISE": ("even", 6), "HEART": ("even", 5),
         "PRINCESS": ("corners",), "BAGUETTE": ("corners",), "SQUARE": ("corners",),
         "TRILLION": ("tips", 3), "TRIANGLE": ("tips", 3), "TRILLIANT": ("tips", 3),
         "EMERALD": ("cuts",), "ASSCHER": ("cuts",), "RADIANT": ("cuts",), "FLANDERS": ("cuts",), "OCTAGON": ("cuts",)}
NO_OUTLINE = ("ROUND", "EMERALD")   # свои ветки без контура (Outline пуст) — как были
SITE_STEPS = 64                     # точек предела на пролёт петли при выборе мест
EPS = 1e-4          # отбор вершин рундиста камня-единицы (|x| или |y| у края габарита)

# (имя, тип, default, min, max, панель, subtype); default меню — после сборки (пункты известны тогда)
STONE_SOCKETS = [
    ("Cut", "NodeSocketMenu", None, None, None, None, None),
    ("Diam", "NodeSocketObject", None, None, None, None, None),
    ("ShowStone", "NodeSocketBool", True, None, None, None, None),
    ("Outline", "NodeSocketObject", None, None, None, None, None),
    ("Width", "NodeSocketFloat", 2.0, 0.3, 30.0, "Stone", None),
    ("Length", "NodeSocketFloat", 3.0, 0.3, 30.0, "Stone", None),
    ("Stone Material", "NodeSocketMaterial", None, None, None, "Stone", None),
    ("Tilt", "NodeSocketFloat", 0.0524, None, None, "Setting", "ANGLE"),
    ("Below Culet", "NodeSocketFloat", 0.4, 0.0, None, "Setting", None),
    ("Subdivision", "NodeSocketInt", 2, 0, 4, "Setting", None),
    ("Set", "NodeSocketBool", False, None, None, "Setting", None),
    ("Edge Round", "NodeSocketFloat", 0.08, 0.0, None, "Setting", None),
]
PRONGS_SOCKETS = [
    ("Tip", "NodeSocketMenu", None, None, None, None, None),
    ("Stones", "NodeSocketObject", None, None, None, None, None),
    ("Smooth", "NodeSocketBool", True, None, None, "Prongs", None),
    ("Count", "NodeSocketInt", 4, 2, 20, "Prongs", None),
    ("° Z", "NodeSocketFloat", 0.7854, None, None, "Prongs", "ANGLE"),
    ("ø", "NodeSocketFloat", 0.5, 0.1, None, "Prongs", None),
    ("Intersection", "NodeSocketFloat", 25.0, 0.0, 100.0, "Prongs", "PERCENTAGE"),
    ("Above Table", "NodeSocketFloat", 0.0, None, None, "Prongs", None),
    ("Set Cover", "NodeSocketFloat", 40.0, 0.0, 100.0, "Prongs", "PERCENTAGE"),
    ("Set Height", "NodeSocketFloat", 80.0, 0.0, 200.0, "Prongs", "PERCENTAGE"),
    ("Claw Length", "NodeSocketFloat", 0.9, 0.2, 3.0, "Prongs", None),
    ("Claw Tip", "NodeSocketFloat", 15.0, 5.0, 60.0, "Prongs", "PERCENTAGE"),
    ("Claw Bow", "NodeSocketFloat", 0.0, 0.0, None, "Prongs", None),
    ("Claw Swell", "NodeSocketFloat", 0.0, 0.0, 100.0, "Prongs", "PERCENTAGE"),
    ("Tab Width", "NodeSocketFloat", 1.2, 0.2, None, "Prongs", None),
    ("V at Corners", "NodeSocketBool", False, None, None, "Prongs", None),
    ("V Length", "NodeSocketFloat", 1.0, 0.2, None, "Prongs", None),
    ("V Thickness", "NodeSocketFloat", 0.5, 0.2, None, "Prongs", None),
    ("Aim Center", "NodeSocketFloat", 0.0, 0.0, 100.0, "Prongs", "PERCENTAGE"),
    ("Material", "NodeSocketMaterial", None, None, None, "Prongs", None),
]
TIPS = ["Round", "Claw", "Tab"]
EDGE_HOLD = 1.5     # опорные петли у рёбер новых деталей — на EDGE_HOLD * Edge Round от ребра (мм, не от размера)
HOLD_MAX = 0.4      # опорная точка каста — не дальше этой доли стороны от её конца
CORNER_SOFT = 0.5   # вертикальное ребро каста скругляется, если cos поворота пути в вершине больше (поворот < 60°)
CLAW_KNEE = 0.45    # колено когтя — на этой доле высоты ноги ниже рундиста (у прежних крапанов Владимира)
CLAW_SHOULDER = 0.1 # плечо когтя — кольцо на оси на CLAW_SHOULDER * ø над плоскостью рундиста, вертикальное
CLAW_BACK = 0.15    # спинка кончика-клина — на CLAW_BACK * ø внутрь от оси
# предел SubD угловой вершины клетки (спинка, остриё): W_OWN своя + W_SIDE вершина той же грани кончика +
# W_SIDE ближняя вершина плеча + W_FAR дальняя вершина плеча; подобрано замером захода и верха крюка
CLAW_W_OWN, CLAW_W_SIDE, CLAW_W_FAR = 0.60, 0.19, 0.02
CLAW_TOP = 0.965    # верх сглаженного крюка выше предела вершины спинки: предел ставится на CLAW_TOP высоты (замер)
CLAW_TIP_SINK = 0.02   # остриё когтя утоплено в корону на CLAW_TIP_SINK * ø: глубже — рез камнем укорачивает заход
CLAW_NECK = 0.6     # шейка заготовки — на CLAW_NECK * ø ниже плеча
CLAW_NECK_SIZE = (6.0 - 1.0 - 0.9) / 4.0   # полуразмер шейки / hb: предел (hb + 4 шейка + 0.9 hb) / 6 = hb
CLAW_SINK = 0.05    # кольца когтя на короне утоплены по -N на CLAW_SINK * ø (контакт даёт рез камнем)
CAST_SOCKETS = [
    ("Type", "NodeSocketMenu", None, None, None, None, None),
    ("Stones", "NodeSocketObject", None, None, None, None, None),
    ("Smooth", "NodeSocketBool", True, None, None, "Cast", None),
    ("Z Offset", "NodeSocketFloat", -0.15, None, None, "Cast", None),
    ("XY Offset", "NodeSocketFloat", -0.05, None, None, "Cast", None),
    ("Cast Thickness", "NodeSocketFloat", 0.4, 0.0, None, "Cast", None),
    ("CastBool", "NodeSocketBool", True, None, None, "Cast", None),
    ("HeightBool", "NodeSocketFloat", 0.4, None, None, "Cast", None),
    ("OffsetBool", "NodeSocketFloat", 0.0, None, None, "Cast", None),
    ("Material", "NodeSocketMaterial", None, None, None, "Cast", None),
    ("Wall", "NodeSocketFloat", 0.45, 0.0, None, "Bezel", None),
    ("Seat", "NodeSocketFloat", 0.3, 0.0, None, "Bezel", None),
    ("Height", "NodeSocketFloat", 60.0, 0.0, 200.0, "Bezel", "PERCENTAGE"),
    ("Bezel Cover", "NodeSocketFloat", 15.0, 0.0, 100.0, "Bezel", "PERCENTAGE"),
    ("ShowCutter", "NodeSocketBool", False, None, None, "Bezel", None),
    ("Bezel Cutter", "NodeSocketObject", None, None, None, "Bezel", None),
    ("Rail", "NodeSocketFloat", 0.5, 0.2, 3.0, "Basket", None),
    ("Rail Shape", "NodeSocketMenu", None, None, None, "Basket", None),
    ("Upper Rail", "NodeSocketBool", True, None, None, "Basket", None),
    ("Crown Depth", "NodeSocketFloat", 1.0, 0.0, None, "Crown", None),
]
CAST_TYPES = ["Wall", "Bezel", "Basket", "Crown"]
CROWN_SOFT = 0.3    # мм: скругление дна V короны между крапанами (по длине контура)
CROWN_REFINE = 2    # линейное измельчение стенки короны перед сдвигом верха (уровни Subdivide Mesh)
CROWN_POW = 1.3     # профиль выреза: глубина * tri ** CROWN_POW (у крапана полого, к середине — V, как макет)
RAIL_SHAPES = ["Round", "Flat"]
RAIL_EDGE = 12.0 / 11.0   # круглый рант: предел SubD 4-точечного сечения — 11/12 полуразмера (середина стороны)
BEZEL_BEVEL = 20.0 * pi / 180.0   # верх глухого каста — плоскость через (0, zt), наружу вниз на 20°
BEZEL_CLEAR = 0.01                # clr = 0.01 Width: край расточки авто-катера (CUTTER_GROW 1.02)
BOOL_SOCKETS = [
    ("Smooth", "NodeSocketBool", True, None, None, None, None),
    ("Realize All", "NodeSocketBool", False, None, None, None, None),
    ("ShowCutter", "NodeSocketBool", False, None, None, "Bool", None),
    ("Cutter", "NodeSocketObject", None, None, None, "Bool", None),
    ("BoolCutter", "NodeSocketBool", True, None, None, "Bool", None),
    ("BoolObject", "NodeSocketObject", None, None, None, "Bool", None),
    ("BoolCollection", "NodeSocketCollection", None, None, None, "Bool", None),
]
SOCKETS = {STONE: STONE_SOCKETS, PRONGS: PRONGS_SOCKETS, CAST: CAST_SOCKETS, BOOL: BOOL_SOCKETS}

# атрибуты инстанса камня: (имя, тип)
ATTRS = [("gem_r", "FLOAT"), ("gem_size", "FLOAT"), ("gem_length", "FLOAT"), ("gem_cut", "INT"),
         ("gem_table", "FLOAT"), ("gem_culet", "FLOAT"), ("gem_crown", "FLOAT"), ("gem_cx", "FLOAT"),
         ("gem_cy", "FLOAT"), ("set_tilt", "FLOAT"), ("set_below", "FLOAT"), ("set_subdiv", "INT"),
         ("set_on", "BOOLEAN"), ("set_round", "FLOAT")]

_MODS = {}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def mods():
    """B (gn_prongs_build), клетка крапана и ensure_interface (gn_round_cast_build), камень-единица
    (gn_gem_cast_build)."""
    if not _MODS:
        _MODS["pr"] = load_module("gn_prongs_ref", PRONGS_PATH)
        _MODS["rc"] = load_module("gn_round_cast_ref", ROUND_PATH)
        _MODS["gc"] = load_module("gn_gem_cast_ref", GEM_PATH)
    return _MODS["pr"], _MODS["rc"], _MODS["gc"]


# --- помощники сборки (поверх B) ---------------------------------------------------------------

def combine(b, vx, vy, vz, x, y):
    n = b.node("ShaderNodeCombineXYZ", x, y)
    for sock, v in zip(n.inputs, (vx, vy, vz)):
        b._set(sock, v)
    return n.outputs[0]


def sep(b, v, x, y):
    n = b.node("ShaderNodeSeparateXYZ", x, y)
    b.link(v, n.inputs[0])
    return n.outputs


def madd(b, a, m, c, x, y):
    """a * m + c"""
    n = b.node("ShaderNodeMath", x, y, operation="MULTIPLY_ADD")
    for sock, v in zip(n.inputs, (a, m, c)):
        b._set(sock, v)
    return n.outputs[0]


def vma(b, a, m, c, x, y):
    """a * m + c (вектора)"""
    n = b.node("ShaderNodeVectorMath", x, y, operation="MULTIPLY_ADD")
    for sock, v in zip(n.inputs, (a, m, c)):
        b._set(sock, v)
    return n.outputs["Vector"]


def icmp(b, op, a, v, x, y):
    n = b.node("FunctionNodeCompare", x, y, data_type="INT", operation=op)
    ab = [s for s in n.inputs if s.enabled]
    b._set(ab[0], a)
    b._set(ab[1], v)
    return n.outputs["Result"]


def transform(b, geo, x, y, translation=None, rotation=None, scale=None):
    n = b.node("GeometryNodeTransform", x, y)
    b.link(geo, n.inputs["Geometry"])
    for sock, v in (("Translation", translation), ("Rotation", rotation), ("Scale", scale)):
        if v is not None:
            b._set(n.inputs[sock], v)
    return n.outputs["Geometry"]


def axis_angle(b, axis, angle, x, y):
    n = b.node("FunctionNodeAxisAngleToRotation", x, y)
    n.inputs["Axis"].default_value = axis
    b.link(angle, n.inputs["Angle"])
    return n.outputs["Rotation"]


def store(b, geo, name, dtype, domain, value, x, y):
    n = b.node("GeometryNodeStoreNamedAttribute", x, y, data_type=dtype, domain=domain)
    n.inputs["Name"].default_value = name
    b.link(geo, n.inputs["Geometry"])
    b._set(n.inputs["Value"], value)
    return n.outputs["Geometry"]


def attr(b, name, dtype, x, y):
    return b.named(name, dtype, x, y).outputs["Attribute"]


def join(b, geos, x, y):
    n = b.node("GeometryNodeJoinGeometry", x, y)
    for g in reversed(geos):
        b.link(g, n.inputs["Geometry"])
    return n.outputs["Geometry"]


def boolean(b, op, a, cutters, x, y):
    _pr, rc, _gc = mods()
    n = b.node("GeometryNodeMeshBoolean", x, y, operation=op, solver=rc.SOLVER)
    if a is not None:
        b.link(a, n.inputs["Mesh 1"])
    for c in cutters:
        b.link(c, n.inputs["Mesh 2"])
    return n.outputs["Mesh"]


def gate(b, cond, geo, x, y):
    """выключено — пустая геометрия"""
    n = b.node("GeometryNodeSwitch", x, y, input_type="GEOMETRY")
    b.link(cond, n.inputs["Switch"])
    b.link(geo, n.inputs["True"])
    return n.outputs["Output"]


def object_info(b, sock, space, x, y, instance=True):
    n = b.node("GeometryNodeObjectInfo", x, y, transform_space=space)
    n.inputs["As Instance"].default_value = instance
    b.link(sock, n.inputs["Object"])
    return n


def has_instances(b, geo, x, y):
    n = b.node("GeometryNodeAttributeDomainSize", x, y, component="INSTANCES")
    b.link(geo, n.inputs["Geometry"])
    return icmp(b, "GREATER_THAN", n.outputs["Instance Count"], 0, x + 200, y)


def stat(b, geo, value, selection, domain, out, x, y):
    n = b.node("GeometryNodeAttributeStatistic", x, y, data_type="FLOAT", domain=domain)
    b.link(geo, n.inputs["Geometry"])
    if selection is not None:
        b.link(selection, n.inputs["Selection"])
    b.link(value, b.enabled(n, "Attribute"))
    return b.enabled_out(n, out)


def index_switch(b, dtype, index, values, x, y):
    n = b.node("GeometryNodeIndexSwitch", x, y, data_type=dtype)
    while len(n.index_switch_items) < len(values):
        n.index_switch_items.new()
    b._set(n.inputs["Index"], index)
    for i, v in enumerate(values):
        b._set(n.inputs[i + 1], v)
    return n.outputs[0]


def lattice(b, nx, ny, nz, x, y):
    """Решётка-куб nx x ny x nz вершин (грани наружу). -> геометрия, номера вершины по X, Y, Z (поля)."""
    cube = b.node("GeometryNodeMeshCube", x, y)
    cube.inputs["Size"].default_value = (nx - 1.0, ny - 1.0, nz - 1.0)
    for sock, n in (("Vertices X", nx), ("Vertices Y", ny), ("Vertices Z", nz)):
        cube.inputs[sock].default_value = n
    p = sep(b, b.node("GeometryNodeInputPosition", x, y - 200).outputs[0], x + 200, y - 200)
    ids = [b.math("ROUND", b.math("ADD", p[a], (n - 1) / 2.0, x + 400, y - 200 - 150 * k), None, x + 600,
                  y - 200 - 150 * k) for k, (a, n) in enumerate((("X", nx), ("Y", ny), ("Z", nz)))]
    return cube.outputs["Mesh"], ids


def hold_crease(b, geo, er, x, y):
    """crease_edge решётки: Edge Round 0 — 1 на всех рёбрах (точный многогранник), иначе 0 (опорные петли)."""
    return store(b, geo, "crease_edge", "FLOAT", "EDGE", b.cmp("LESS_EQUAL", er, 0.0, x, y - 200), x, y)


def hold_corners(b, curve, hh, pos, lerp, x, y, sharp=None, clear=()):
    """Замкнутая ломаная -> у каждой вершины (sharp задан — только у вершин с sharp > 0.5) две опорные точки
    на её сторонах: на hh от вершины, но не дальше HOLD_MAX стороны. Subdivide Curve с двумя разрезами даёт
    порядок «вершина, две новые, вершина…», новые ставятся в долю t стороны. pos — поле настоящего положения
    вершины; None — Position, тогда точки и передвигаются. lerp — [(имя, тип)] атрибутов точки: у опорной —
    между значениями концов стороны в той же доле t (читаются с вершин, а они не меняются). clear — имена
    FLOAT-атрибутов, которые у опорных точек обнуляются (Subdivide Curve их интерполирует)."""
    sub = b.node("GeometryNodeSubdivideCurve", x, y)
    b.link(curve, sub.inputs["Curve"])
    sub.inputs["Cuts"].default_value = 2
    r = b.math("FLOORED_MODULO", b.node("GeometryNodeInputIndex", x, y - 200).outputs[0], 3.0, x + 200, y - 200)
    ends = []
    for k, off in enumerate((b.math("MULTIPLY", r, -1.0, x + 400, y - 200), b.math("SUBTRACT", 3.0, r, x + 400, y - 360))):
        n = b.node("GeometryNodeOffsetPointInCurve", x + 600, y - 200 - 160 * k)
        b.link(off, n.inputs["Offset"])
        ends.append(n.outputs["Point Index"])
    place = pos is None
    if place:
        pos = b.node("GeometryNodeInputPosition", x, y - 500).outputs[0]
    pa = b.at_index(pos, ends[0], "FLOAT_VECTOR", x + 800, y - 200)
    pb = b.at_index(pos, ends[1], "FLOAT_VECTOR", x + 800, y - 360)
    ln = b.math("MAXIMUM", b.vmath("DISTANCE", pa, pb, x + 1000, y - 200), 1e-6, x + 1200, y - 200)
    f = b.math("MINIMUM", b.math("DIVIDE", hh, ln, x + 1400, y - 200), HOLD_MAX, x + 1600, y - 200)
    t = index_switch(b, "FLOAT", r, [0.0, f, b.math("SUBTRACT", 1.0, f, x + 1600, y - 360)], x + 1800, y - 200)
    tv = combine(b, t, t, t, x + 2000, y - 200)
    geo = sub.outputs["Curve"]
    if place:
        sp = b.node("GeometryNodeSetPosition", x + 2400, y)
        b.link(geo, sp.inputs["Geometry"])
        b.link(vma(b, b.vmath("SUBTRACT", pb, pa, x + 2000, y - 400), tv, pa, x + 2200, y - 300), sp.inputs["Position"])
        geo = sp.outputs["Geometry"]
    for i, (name, dtype) in enumerate(lerp):
        yy = y - 700 - 300 * i
        va = b.at_index(attr(b, name, dtype, x + 600, yy), ends[0], dtype, x + 800, yy)
        vb = b.at_index(attr(b, name, dtype, x + 600, yy - 140), ends[1], dtype, x + 800, yy - 140)
        geo = store(b, geo, name, dtype, "POINT", vma(b, b.vmath("SUBTRACT", vb, va, x + 1000, yy), tv, va, x + 1200, yy),
                    x + 2600 + 200 * i, y)
    for i, name in enumerate(clear):
        geo = store(b, geo, name, "FLOAT", "POINT",
                    index_switch(b, "FLOAT", r, [attr(b, name, "FLOAT", x + 2600, y - 300 - 200 * i), 0.0, 0.0],
                                 x + 2800, y - 300 - 200 * i), x + 3200 + 200 * i, y)
    if sharp is not None:
        own = index_switch(b, "FLOAT", r, [1.0, b.at_index(sharp, ends[0], "FLOAT", x + 800, y - 1800),
                                           b.at_index(sharp, ends[1], "FLOAT", x + 800, y - 1960)], x + 1000, y - 1800)
        cut = b.node("GeometryNodeDeleteGeometry", x + 3800, y, domain="POINT")
        b.link(geo, cut.inputs["Geometry"])
        b.link(b.cmp("LESS_THAN", own, 0.5, x + 1200, y - 1800), cut.inputs["Selection"])
        geo = cut.outputs["Geometry"]
    return geo


def subd(b, geo, level, x, y):
    n = b.node("GeometryNodeSubdivisionSurface", x, y)
    b.link(geo, n.inputs["Mesh"])
    b.link(level, n.inputs["Level"])
    b.link(attr(b, "crease_edge", "FLOAT", x - 200, y - 200), n.inputs["Edge Crease"])
    n.inputs["Limit Surface"].default_value = True
    return n.outputs["Mesh"]


def smooth(b, geo, flag, x, y):
    """Smooth by Angle 30°, как у монолитов"""
    _pr, rc, _gc = mods()
    sm_f = b.node("GeometryNodeSetShadeSmooth", x, y - 300, domain="FACE")
    b.link(geo, sm_f.inputs["Mesh"])
    sm_e = b.node("GeometryNodeSetShadeSmooth", x + 200, y - 300, domain="EDGE")
    b.link(sm_f.outputs["Mesh"], sm_e.inputs["Mesh"])
    b.link(b.cmp("LESS_EQUAL", b.node("GeometryNodeInputMeshEdgeAngle", x, y - 500).outputs["Unsigned Angle"],
                 rc.SMOOTH_ANGLE, x + 200, y - 500), sm_e.inputs["Shade Smooth"])
    return b.switch("GEOMETRY", flag, geo, sm_e.outputs["Mesh"], x + 400, y)


def finish(b, ng, out, x):
    b.frame = None
    gout = b.node("NodeGroupOutput", x, 0)
    b.link(out, gout.inputs["Geometry"])
    print("Node group '%s' rebuilt: %d nodes" % (ng.name, len(ng.nodes)))
    return ng


def begin(name):
    """Интерфейс (сокеты только добавляются), узлы с нуля. -> ng, b, gi(панель, имя)"""
    pr, rc, _gc = mods()
    ng = bpy.data.node_groups.get(name)
    if ng is None:
        ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    rc.SOCKETS, rc.OBSOLETE = SOCKETS[name], []
    rc.ensure_interface(ng)
    ng.is_modifier = True
    ng.nodes.clear()
    b = pr.B(ng, -400)
    keys = rc.socket_keys(ng)

    def gi(panel, sock):
        return next(s for s in b.gin.outputs if s.identifier == keys[(panel, sock)])
    return ng, b, gi


# --- чтение атрибутов камня ---------------------------------------------------------------------

def read_stone(b, geo, x, y, attrs=ATTRS):
    """Атрибуты первого инстанса с gem_r > 0 одним значением; 'found' — камень есть."""
    b.section("Stone Attributes")
    r = attr(b, "gem_r", "FLOAT", x, y - 200)
    idx = stat(b, geo, b.node("GeometryNodeInputIndex", x, y - 360).outputs[0],
               b.cmp("GREATER_THAN", r, 0.0, x + 200, y - 200), "INSTANCE", "Min", x + 400, y)
    out = {"found": b.cmp("GREATER_THAN", stat(b, geo, r, None, "INSTANCE", "Max", x + 400, y + 300), 0.0,
                          x + 600, y + 300)}
    for i, (name, dtype) in enumerate(attrs):
        yy = y - 200 * i
        n = b.node("GeometryNodeSampleIndex", x + 800, yy, data_type=dtype, domain="INSTANCE")
        b.link(geo, n.inputs["Geometry"])
        b.link(attr(b, name, dtype, x + 600, yy - 60), b.enabled(n, "Value"))
        b.link(idx, n.inputs["Index"])
        out[name] = b.enabled_out(n, "Value")
    return out


def stone_source(b, gi, x, y):
    """Камень с объекта Stones (если на нём есть камень) или из потока. -> геометрия, с объекта ли"""
    b.section("Stone Source")
    info = object_info(b, gi(None, "Stones"), "ORIGINAL", x, y, instance=False)
    geo = info.outputs["Geometry"]
    use_obj = b.cmp("GREATER_THAN", stat(b, geo, attr(b, "gem_r", "FLOAT", x, y - 200), None, "INSTANCE", "Max",
                                         x + 200, y), 0.0, x + 400, y)
    return b.switch("GEOMETRY", use_obj, b.g("Geometry"), geo, x + 600, y), use_obj


def to_self_space(b, gi, use_obj, geo, x, y):
    """Из координат объекта Stones в координаты своего объекта (Transform у Object Info Relative)."""
    rel = object_info(b, gi(None, "Stones"), "RELATIVE", x, y - 300)
    tf = b.node("GeometryNodeTransform", x + 200, y)
    tf.inputs["Mode"].default_value = "Matrix"
    b.link(geo, tf.inputs["Geometry"])
    b.link(rel.outputs["Transform"], tf.inputs["Transform"])
    return b.switch("GEOMETRY", use_obj, geo, tf.outputs["Geometry"], x + 400, y)


def finish_metal(b, gi, panel, v, use_obj, geo, x, stream=None):
    """Материал, сглаживание, нет камня — ничего, в свои координаты, + поток."""
    b.section("Output")
    mat = b.node("GeometryNodeSetMaterial", x, 0)
    b.link(geo, mat.inputs["Geometry"])
    b.link(gi(panel, "Material"), mat.inputs["Material"])
    geo = smooth(b, mat.outputs["Geometry"], gi(panel, "Smooth"), x + 200, 0)
    geo = gate(b, v["found"], geo, x + 600, 0)
    geo = to_self_space(b, gi, use_obj, geo, x + 800, 0)
    return join(b, [b.g("Geometry") if stream is None else stream, geo], x + 1400, 0)


def stone_mesh(b, geo, w, ln, x, y):
    """Меш камня из потока: копия первого инстанса с gem_r > 0, матрица — масштаб (W, L, W), Realize.
    Удаление — только на копии, сам инстанс камня в потоке не трогается."""
    b.section("Stone Mesh")
    parts = b.node("GeometryNodeSeparateComponents", x - 200, y)
    b.link(geo, parts.inputs["Geometry"])
    insts = parts.outputs["Instances"]
    is_stone = b.cmp("GREATER_THAN", attr(b, "gem_r", "FLOAT", x, y - 200), 0.0, x + 200, y - 200)
    first = b.node("GeometryNodeDeleteGeometry", x + 400, y, domain="INSTANCE")
    b.link(insts, first.inputs["Geometry"])
    idx = stat(b, insts, b.node("GeometryNodeInputIndex", x, y - 400).outputs[0], is_stone,
               "INSTANCE", "Min", x + 200, y - 400)
    b.link(b.cmp("NOT_EQUAL", b.node("GeometryNodeInputIndex", x + 200, y - 600).outputs[0], idx, x + 400, y - 400),
           first.inputs["Selection"])
    reset = b.node("GeometryNodeSetInstanceTransform", x + 600, y)
    b.link(first.outputs["Geometry"], reset.inputs["Instances"])
    m = b.node("FunctionNodeCombineTransform", x + 600, y - 300)
    b.link(combine(b, w, ln, w, x + 400, y - 600), m.inputs["Scale"])
    b.link(m.outputs["Transform"], reset.inputs["Transform"])
    real = b.node("GeometryNodeRealizeInstances", x + 800, y)
    b.link(reset.outputs["Instances"], real.inputs["Geometry"])
    return real.outputs["Geometry"]


def seat_operands(b, stone, w, ln, culet, top, cutter_obj, set_on, enable, x, y):
    """Посадка камня: без Set — объект-катер * (W, L, W) или авто-катер (оболочка камня * CUTTER_GROW
    по XY и его копии, поднятой калеттой на top); Set — оболочка камня * SET_GROW по XY и катер ниже
    z = -SET_CLIP * W отдельным операндом. enable выкл — посадки нет.
    -> [операнды], оболочка камня (операнд Set), условие оболочки."""
    _pr, rc, gc = mods()
    b.section("Seat")
    given = transform(b, object_info(b, cutter_obj, "ORIGINAL", x, y).outputs["Geometry"], x + 200, y,
                      scale=combine(b, w, ln, w, x, y - 200))
    has_given = has_instances(b, given, x + 200, y + 200)
    grown = transform(b, stone, x, y - 400, scale=(gc.CUTTER_GROW, gc.CUTTER_GROW, 1.0))
    # копия целиком над металлом: калетта на top
    lifted = transform(b, grown, x + 200, y - 500,
                       translation=combine(b, 0.0, 0.0, b.math("SUBTRACT", top, culet, x, y - 700), x + 200, y - 700))
    auto = b.node("GeometryNodeConvexHull", x + 600, y - 400)
    b.link(join(b, [grown, lifted], x + 400, y - 400), auto.inputs["Geometry"])
    cutter = b.switch("GEOMETRY", has_given, auto.outputs["Convex Hull"], given, x + 800, y)
    hull = b.node("GeometryNodeConvexHull", x + 400, y - 900)
    b.link(transform(b, stone, x + 200, y - 900, scale=(rc.SET_GROW, rc.SET_GROW, 1.0)), hull.inputs["Geometry"])
    hull_on = b.boolean("AND", set_on, enable, x + 400, y - 1050)
    set_hull = gate(b, hull_on, hull.outputs["Convex Hull"], x + 600, y - 900)
    box = b.node("GeometryNodeMeshCube", x + 400, y - 1200)
    side = b.math("MULTIPLY", b.math("MAXIMUM", w, ln, x, y - 1200), 4.0, x + 200, y - 1200)
    b.link(combine(b, side, side, side, x + 200, y - 1360), box.inputs["Size"])
    drop = madd(b, side, -0.5, b.math("MULTIPLY", w, -rc.SET_CLIP, x + 200, y - 1520), x + 400, y - 1450)
    below = transform(b, box.outputs["Mesh"], x + 600, y - 1200, translation=combine(b, 0.0, 0.0, drop,
                                                                                       x + 600, y - 1450))
    # катер пуст — пересечение не делать: Intersect с пустым операндом возвращает сам ящик
    low = gate(b, has_given, boolean(b, "INTERSECT", None, [given, below], x + 800, y - 1200), x + 1000, y - 1200)
    seat = [gate(b, enable, b.switch("GEOMETRY", set_on, cutter, low, x + 1000, y), x + 1200, y), set_hull]
    return seat, set_hull, hull_on


# --- контур огранки из потока (Oval, Pear, ... или Outline у Round / Emerald) -------------------------

LIMIT_RES = 64           # точек предела на пролёт петли (как My_Gem_Cast)
MITER_LIMIT = 4.0        # предел выноса в острой вершине


def outline_mesh(b, geo, w, ln, x, y):
    """Меш контура из второго носителя (инстанс с gem_outline > 0): копия, матрица — масштаб (W, L, 1),
    Realize (прототип в мм, как base у My_Gem_Cast). -> меш, есть ли контур."""
    b.section("Outline Mesh")
    parts = b.node("GeometryNodeSeparateComponents", x - 200, y)
    b.link(geo, parts.inputs["Geometry"])
    insts = parts.outputs["Instances"]
    tag = attr(b, "gem_outline", "FLOAT", x, y - 200)
    is_o = b.cmp("GREATER_THAN", tag, 0.0, x + 200, y - 200)
    found = b.cmp("GREATER_THAN", stat(b, insts, tag, None, "INSTANCE", "Max", x + 200, y + 200), 0.0, x + 400, y + 200)
    idx = stat(b, insts, b.node("GeometryNodeInputIndex", x, y - 400).outputs[0], is_o, "INSTANCE", "Min",
               x + 200, y - 400)
    first = b.node("GeometryNodeDeleteGeometry", x + 400, y, domain="INSTANCE")
    b.link(insts, first.inputs["Geometry"])
    b.link(b.cmp("NOT_EQUAL", b.node("GeometryNodeInputIndex", x + 200, y - 600).outputs[0], idx, x + 400, y - 400),
           first.inputs["Selection"])
    reset = b.node("GeometryNodeSetInstanceTransform", x + 600, y)
    b.link(first.outputs["Geometry"], reset.inputs["Instances"])
    m = b.node("FunctionNodeCombineTransform", x + 600, y - 300)
    b.link(combine(b, w, ln, 1.0, x + 400, y - 600), m.inputs["Scale"])
    b.link(m.outputs["Transform"], reset.inputs["Transform"])
    real = b.node("GeometryNodeRealizeInstances", x + 800, y)
    b.link(reset.outputs["Instances"], real.inputs["Geometry"])
    return real.outputs["Geometry"], found


def outline_loop(b, base, x0, y0):
    """Петля, предел и вынос — рамки Loop / Limit Curve / Loop Offset из My_Gem_Cast (gn_gem_cast_build.py,
    там же из gem_setting.py), перенесены как есть. -> {loop: кривая против часовой, pos, sharp (поле
    острой вершины), limit: точки предела (выходы Points, Tangent), offset: вынос на единицу отступа}."""
    up = (0.0, 0.0, 1.0)
    # --- петля: рёбра прототипа, против часовой ---
    b.section("Loop")
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
    cross = sep(b, b.vmath("CROSS_PRODUCT", pos, p_next, x0 + 400, y0 - 200), x0 + 600, y0 - 200)["Z"]
    of_curve = b.node("GeometryNodeCurveOfPoint", x0 + 400, y0 - 400)
    area = b.node("GeometryNodeAccumulateField", x0 + 800, y0 - 200, data_type="FLOAT", domain="POINT")
    b.link(cross, area.inputs["Value"])
    b.link(of_curve.outputs["Curve Index"], area.inputs["Group ID"])
    ccw = b.node("GeometryNodeReverseCurve", x0 + 1000, y0)
    b.link(loop.outputs["Curve"], ccw.inputs["Curve"])
    b.link(b.cmp("LESS_THAN", area.outputs["Total"], 0.0, x0 + 1000, y0 - 200), ccw.inputs["Selection"])
    loop = ccw.outputs["Curve"]
    sharp = b.cmp("GREATER_THAN", attr(b, "corner", "FLOAT", x0 + 400, y0 - 800), 0.5, x0 + 600, y0 - 800)

    # --- предел петли сплайном Безье: точки с касательной ---
    b.section("Limit Curve")
    x0 += 1300
    hl = b.vmath("SCALE", vma(b, pos, (2.0, 2.0, 2.0), p_prev, x0, y0 - 400), 1.0 / 3.0, x0 + 180, y0 - 400)
    hr = b.vmath("SCALE", vma(b, pos, (2.0, 2.0, 2.0), p_next, x0, y0 - 560), 1.0 / 3.0, x0 + 180, y0 - 560)
    handles = b.capture(loop, {"Left": ("VECTOR", hl), "Right": ("VECTOR", hr)}, x0 + 380, y0)
    bez = b.node("GeometryNodeCurveSplineType", x0 + 580, y0, spline_type="BEZIER")
    b.link(handles.outputs["Geometry"], bez.inputs["Curve"])
    free = b.node("GeometryNodeCurveSetHandles", x0 + 780, y0, handle_type="FREE", mode={"LEFT", "RIGHT"})
    b.link(bez.outputs["Curve"], free.inputs["Curve"])
    smooth_k = b.vmath("SCALE", vma(b, pos, (4.0, 4.0, 4.0), b.vmath("ADD", p_prev, p_next, x0, y0 - 720),
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

    # --- вынос петли по биссектрисе с компенсацией сглаживания ---
    b.section("Loop Offset")
    x0, y0 = x0 - 1300, y0 - 1100
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
    pull = madd(b, b.at_index(s0, nxt.outputs["Point Index"], "FLOAT", x0 + 1260, y0 - 1080), bn_next,
                b.math("MULTIPLY", b.at_index(s0, prv.outputs["Point Index"], "FLOAT", x0 + 1260, y0 - 920),
                       bn_prev, x0 + 1440, y0 - 920), x0 + 1620, y0 - 1000)
    s1 = b.math("DIVIDE", b.math("SUBTRACT", 6.0, pull, x0 + 1800, y0 - 1000),
                b.math("MULTIPLY", b.vmath("DOT_PRODUCT", bis, chord, x0 + 1620, y0 - 1160), 4.0, x0 + 1800, y0 - 1160),
                x0 + 1980, y0 - 1000)
    offset = b.vmath("SCALE", bis, b.switch("FLOAT", sharp, s1, miter, x0 + 2160, y0 - 1000), x0 + 2340, y0 - 280)
    return {"loop": loop, "pos": pos, "sharp": sharp, "limit": limit, "offset": offset}


# --- значения меню на модификаторах -------------------------------------------------------------

def menu_values(ng, name):
    """[(модификатор, значение)] входа-меню name — до пересборки; есть ли такой вход."""
    if ng is None:
        return [], False
    ident = next((it.identifier for it in ng.interface.items_tree
                  if it.item_type == "SOCKET" and it.in_out == "INPUT" and it.name == name), None)
    if ident is None:
        return [], False
    return [(md, getattr(md.properties.inputs, ident).value) for obj in bpy.data.objects for md in obj.modifiers
            if md.type == "NODES" and md.node_group == ng], True


def restore_menu(ng, name, items, kept, had):
    """После сборки: default меню (пункты известны только теперь), прежние значения на модификаторах —
    по имени пункта; вход только что добавлен — первый пункт на всех модификаторах."""
    ng.interface_update(bpy.context)
    item = next(it for it in ng.interface.items_tree
                if it.item_type == "SOCKET" and it.in_out == "INPUT" and it.name == name)
    item.default_value = items[0]
    for md, value in kept:
        if value in items:
            getattr(md.properties.inputs, item.identifier).value = value
    if not had:
        for obj in bpy.data.objects:
            for md in obj.modifiers:
                if md.type == "NODES" and md.node_group == ng:
                    getattr(md.properties.inputs, item.identifier).value = items[0]


def move_after(ng, name, after):
    """Вход name — сразу после входа after (оба на верхнем уровне)."""
    items = list(ng.interface.items_tree)
    pos = next(i for i, it in enumerate(items)
               if it.item_type == "SOCKET" and it.in_out == "INPUT" and it.name == after)
    item = next(it for it in items if it.item_type == "SOCKET" and it.in_out == "INPUT" and it.name == name)
    if items.index(item) != pos + 1:
        ng.interface.move(item, pos + 1 if items.index(item) > pos else pos)


def move_first(ng, name):
    """Вход name — первым (сразу после Geometry)."""
    items = list(ng.interface.items_tree)
    geo_in = next(i for i, it in enumerate(items)
                  if it.item_type == "SOCKET" and it.in_out == "INPUT" and it.name == "Geometry")
    ng.interface.move(next(it for it in items if it.item_type == "SOCKET" and it.name == name), geo_in + 1)


def menu_switch(b, sock, items, x, y):
    """Menu Switch (INT): номер пункта."""
    menu = b.node("GeometryNodeMenuSwitch", x, y, data_type="INT")
    menu.enum_items.clear()
    for c in items:
        menu.enum_items.new(c)
    b.link(sock, menu.inputs["Menu"])
    for i, c in enumerate(items):
        menu.inputs[c].default_value = i
    return menu.outputs[0]


# --- My_Stone ----------------------------------------------------------------------------------

def builtin_stone(cut):
    """Встроенный камень-единица огранки. Round — RWPRound, если он есть в файле, иначе unit_stone."""
    gc = mods()[2]
    return (bpy.data.objects.get("RWPRound") if cut == "ROUND" else None) or gc.unit_stone(cut)


def site_points(cut, loop):
    """Места крапанов по RULES: [(x, y)] в единичных координатах, на пределе петли. Правила считаются в
    настоящих пропорциях огранки (base_width x base_length), не в квадрате 1 x 1."""
    from math import atan2, hypot
    gc = mods()[2]
    go = load_module("gem_outline_ref", OUTLINE_PATH)
    spec = gc.load_module("gem_cast_gems", gc.GEMS_PATH)._CUT_SPECS[cut]
    k = 1.0 / max(spec.base_width, spec.base_length)
    w, ln = spec.base_width * k, spec.base_length * k
    dense = [(x * w, y * ln) for x, y, _tx, _ty in go.limit_curve(loop, SITE_STEPS)]
    n = len(dense)
    corners = [i * SITE_STEPS for i, p in enumerate(loop) if p[2]]
    rule = RULES[cut]
    if rule[0] == "corners":
        pick = corners
    elif rule[0] == "diag":
        pick = []
        for sx, sy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
            a = atan2(sy * ln, sx * w)
            pick.append(min(range(n), key=lambda i: abs((atan2(dense[i][1], dense[i][0]) - a + pi) % (2 * pi) - pi)))
    elif rule[0] == "cuts":
        spans = sorted(((hypot(dense[b % n][0] - dense[a][0], dense[b % n][1] - dense[a][1]), a, b)
                        for a, b in zip(corners, corners[1:] + [corners[0] + n])))[:4]
        pick = [(a + b) // 2 for _d, a, b in spans]
    elif rule[0] == "tips":
        pick = []
        for i in sorted(corners, key=lambda i: -hypot(*dense[i])):
            ang = atan2(dense[i][1], dense[i][0])
            if all(abs((ang - atan2(dense[j][1], dense[j][0]) + pi) % (2 * pi) - pi) > pi / 3 for j in pick):
                pick.append(i)
            if len(pick) == rule[1]:
                break
    else:
        # even: от острия (дальний острый угол), поровну по длине контура
        start = max(corners, key=lambda i: hypot(*dense[i]))
        acc, total = [0.0], 0.0
        for j in range(n):
            a, b = dense[(start + j) % n], dense[(start + j + 1) % n]
            total += hypot(b[0] - a[0], b[1] - a[1])
            acc.append(total)
        pick = [start + min(range(n), key=lambda i: abs(acc[i] - total * j / rule[1])) for j in range(rule[1])]
        if len(rule) > 2:
            pick = [pick[j] for j in rule[2]]      # часть шагов: груша — остриё и два на головке
    return [(dense[i % n][0] / w, dense[i % n][1] / ln) for i in pick]


def builtin_outline(cut, force=False):
    """Встроенный контур огранки 'Outline <Cut>' (формат outline_proto монолита My_Gem_Cast: петля рундиста
    рёбрами + атрибут corner, места крапанов — вершины без рёбер, единичные координаты). Уже есть — не
    трогать (мог быть поправлен руками). Round и Emerald — без контура (None), с force — тоже по RULES
    (нужен, когда места крапанов заданы своим мешем объекта)."""
    if cut in NO_OUTLINE and not force:
        return None
    gc = mods()[2]
    name = "Outline %s" % cut.title()
    obj = bpy.data.objects.get(name)
    if obj is not None:
        return obj
    go = load_module("gem_outline_ref", OUTLINE_PATH)
    loop = go.gem_loop(builtin_stone(cut))
    sites = site_points(cut, loop)
    n = len(loop)
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(x, y, 0.0) for x, y, _c in loop] + [(x, y, 0.0) for x, y in sites],
                     [(i, (i + 1) % n) for i in range(n)], [])
    corner = mesh.attributes.new("corner", "FLOAT", "POINT")
    corner.data.foreach_set("value", [1.0 if c else 0.0 for *_xy, c in loop] + [0.0] * len(sites))
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    gc.utils_collection().objects.link(obj)
    return obj


def by_cut(b, cut, objs, x, y):
    """Объект по номеру огранки (Index Switch по gem_cut)."""
    n = b.node("GeometryNodeIndexSwitch", x, y, data_type="OBJECT")
    while len(n.index_switch_items) < len(objs):
        n.index_switch_items.new()
    b.link(cut, n.inputs["Index"])
    for i, o in enumerate(objs):
        n.inputs[i + 1].default_value = o
    return n.outputs[0]


def build_stone():
    kept, had_cut = menu_values(bpy.data.node_groups.get(STONE), "Cut")
    ng, b, gi = begin(STONE)
    move_after(ng, "Outline", "Diam")
    w = gi("Stone", "Width")

    # --- огранка: номер пункта Cut; Round — L = W ---
    b.section("Cut")
    cut = menu_switch(b, gi(None, "Cut"), CUTS, 0, 800)
    is_em = icmp(b, "EQUAL", cut, 1, 200, 800)
    ln = b.switch("FLOAT", icmp(b, "EQUAL", cut, 0, 200, 650), gi("Stone", "Length"), w, 400, 800)

    # --- объект камня: Diam, а пуст (нет вершин) — встроенный камень-единица огранки ---
    b.section("Diam")
    given = b.node("GeometryNodeAttributeDomainSize", 800, 1200, component="MESH")
    b.link(object_info(b, gi(None, "Diam"), "ORIGINAL", 600, 1200, instance=False).outputs["Geometry"],
           given.inputs["Geometry"])
    pick = b.node("GeometryNodeSwitch", 1200, 1200, input_type="OBJECT")
    b.link(icmp(b, "GREATER_THAN", given.outputs["Point Count"], 0, 1000, 1200), pick.inputs["Switch"])
    b.link(by_cut(b, cut, [builtin_stone(c.upper()) for c in CUTS], 1000, 1000), pick.inputs["False"])
    b.link(gi(None, "Diam"), pick.inputs["True"])
    diam = pick.outputs["Output"]

    # --- свои места крапанов: вершины без рёбер собственного меша объекта (мм, z не важен) ---
    # из проходящей геометрии они убираются (на выход не попадают), остальной меш — как был
    b.section("Own Sites")
    parts = b.node("GeometryNodeSeparateComponents", 0, 2400)
    b.link(b.g("Geometry"), parts.inputs["Geometry"])
    own_mesh = parts.outputs["Mesh"]
    own_loose = icmp(b, "EQUAL", b.node("GeometryNodeInputMeshVertexNeighbors", 0, 2200).outputs["Vertex Count"], 0,
                     200, 2200)
    own_pts = b.node("GeometryNodeMeshToPoints", 400, 2400, mode="VERTICES")
    b.link(own_mesh, own_pts.inputs["Mesh"])
    b.link(own_loose, own_pts.inputs["Selection"])
    own_n = b.node("GeometryNodeAttributeDomainSize", 600, 2600, component="POINTCLOUD")
    b.link(own_pts.outputs["Points"], own_n.inputs["Geometry"])
    has_own = icmp(b, "GREATER_THAN", own_n.outputs["Point Count"], 0, 800, 2600)
    # в единичные координаты контура: (x / W, y / L, 0)
    own_unit = b.node("GeometryNodeSetPosition", 800, 2400)
    b.link(own_pts.outputs["Points"], own_unit.inputs["Geometry"])
    b.link(b.vmath("MULTIPLY", b.node("GeometryNodeInputPosition", 600, 2200).outputs[0],
                   combine(b, b.math("DIVIDE", 1.0, w, 400, 2000), b.math("DIVIDE", 1.0, ln, 400, 1850), 0.0, 600, 2000),
                   800, 2200), own_unit.inputs["Position"])
    own_verts = b.node("GeometryNodePointsToVertices", 1000, 2400)
    b.link(own_unit.outputs["Geometry"], own_verts.inputs["Points"])
    kept_mesh = b.node("GeometryNodeDeleteGeometry", 400, 2800, domain="POINT")
    b.link(own_mesh, kept_mesh.inputs["Geometry"])
    b.link(own_loose, kept_mesh.inputs["Selection"])
    passing = join(b, [kept_mesh.outputs["Geometry"]] + [o for o in parts.outputs if o.name != "Mesh"], 600, 2800)

    # --- контур: Outline, а пуст — встроенный контур огранки (у Round и Emerald его нет, но есть свои места —
    # встроенный по RULES) ---
    b.section("Outline")
    o_given = b.node("GeometryNodeAttributeDomainSize", 800, 1700, component="MESH")
    b.link(object_info(b, gi(None, "Outline"), "ORIGINAL", 600, 1700, instance=False).outputs["Geometry"],
           o_given.inputs["Geometry"])
    o_pick = b.node("GeometryNodeSwitch", 1200, 1700, input_type="OBJECT")
    b.link(icmp(b, "GREATER_THAN", o_given.outputs["Point Count"], 0, 1000, 1700), o_pick.inputs["Switch"])
    b.link(b.switch("OBJECT", has_own, by_cut(b, cut, [builtin_outline(c.upper()) for c in CUTS], 800, 1500),
                    by_cut(b, cut, [builtin_outline(c.upper(), force=True) for c in CUTS], 800, 1300), 1000, 1500),
           o_pick.inputs["False"])
    b.link(gi(None, "Outline"), o_pick.inputs["True"])
    outline = object_info(b, o_pick.outputs["Output"], "ORIGINAL", 1400, 1700, instance=False).outputs["Geometry"]
    o_size = b.node("GeometryNodeAttributeDomainSize", 1600, 1500, component="MESH")
    b.link(outline, o_size.inputs["Geometry"])
    has_outline = icmp(b, "GREATER_THAN", o_size.outputs["Point Count"], 0, 1800, 1500)

    # --- замеры камня-единицы: высоты, край площадки, срезы углов ---
    b.section("Unit Stone")
    unit = object_info(b, diam, "ORIGINAL", 0, 400, instance=False).outputs["Geometry"]
    bb = b.node("GeometryNodeBoundBox", 200, 400)
    b.link(unit, bb.inputs["Geometry"])
    zmax, zmin = sep(b, bb.outputs["Max"], 400, 450)["Z"], sep(b, bb.outputs["Min"], 400, 300)["Z"]
    p = sep(b, b.node("GeometryNodeInputPosition", 200, 100).outputs[0], 400, 100)
    on_table = b.cmp("GREATER_THAN", p["Z"], b.math("MULTIPLY", zmax, 0.999, 600, 250), 800, 250)
    r_xy = b.vmath("LENGTH", combine(b, p["X"], p["Y"], 0.0, 600, 100), None, 800, 100)
    ax = b.math("ABSOLUTE", p["X"], None, 600, -50)
    ay = b.math("ABSOLUTE", p["Y"], None, 600, -200)
    # край площадки: Round — max length(xy), Emerald и огранки по контуру — max |x| (как My_Gem_Cast)
    edge = stat(b, unit, b.switch("FLOAT", b.boolean("OR", is_em, has_outline, 800, -350), r_xy, ax, 1000, 100),
                on_table, "POINT", "Max", 1200, 250)
    crown = b.math("MULTIPLY", w, b.math("SUBTRACT", 0.5, edge, 1400, 250), 1600, 250)
    # рундист изумруда: у края габарита по Y max |x| = 0.5 - cx, у края по X max |y| = 0.5 - cy
    mx = stat(b, unit, ax, b.cmp("GREATER_EQUAL", ay, 0.5 - EPS, 1000, -50), "POINT", "Max", 1200, -50)
    my = stat(b, unit, ay, b.cmp("GREATER_EQUAL", ax, 0.5 - EPS, 1000, -250), "POINT", "Max", 1200, -250)
    cx = b.switch("FLOAT", is_em, 0.0, b.math("MULTIPLY", w, b.math("SUBTRACT", 0.5, mx, 1400, -50), 1600, -50),
                  1800, -50)
    cy = b.switch("FLOAT", is_em, 0.0, b.math("MULTIPLY", ln, b.math("SUBTRACT", 0.5, my, 1400, -250), 1600, -250),
                  1800, -250)

    # --- материал камня: задан ли (пробная грань без материала) ---
    b.section("Stone Material")
    mat = gi("Stone", "Stone Material")
    probe = b.node("GeometryNodeMeshGrid", 0, -1300)
    probe.inputs["Vertices X"].default_value = probe.inputs["Vertices Y"].default_value = 2
    probed = b.node("GeometryNodeSetMaterial", 200, -1300)
    b.link(probe.outputs["Mesh"], probed.inputs["Geometry"])
    b.link(mat, probed.inputs["Material"])
    empty = b.node("GeometryNodeMaterialSelection", 200, -1500).outputs["Selection"]
    no_mat = b.cmp("GREATER_THAN", stat(b, probed.outputs["Geometry"], empty, None, "FACE", "Max", 400, -1300), 0.5,
                   600, -1300)

    # --- камень: инстанс Diam (W, L, W) или невидимый носитель (масштаб 0) ---
    b.section("Stone")
    s_stone = combine(b, w, ln, w, 0, -700)
    shown = transform(b, object_info(b, diam, "ORIGINAL", 0, -500).outputs["Geometry"], 200, -500,
                      scale=s_stone)
    painted = b.node("GeometryNodeSetMaterial", 400, -700)
    b.link(shown, painted.inputs["Geometry"])
    b.link(mat, painted.inputs["Material"])
    shown = b.switch("GEOMETRY", no_mat, painted.outputs["Geometry"], shown, 400, -500)
    g2i = b.node("GeometryNodeGeometryToInstance", 200, -900)
    b.link(unit, g2i.inputs["Geometry"])
    carrier = transform(b, g2i.outputs["Instances"], 400, -900, scale=(0.0, 0.0, 0.0))
    stone = b.switch("GEOMETRY", gi(None, "ShowStone"), carrier, shown, 600, -500)
    # встроенного камня в файле нет — камня нет
    size = b.node("GeometryNodeAttributeDomainSize", 400, -1100, component="MESH")
    b.link(unit, size.inputs["Geometry"])
    stone = gate(b, icmp(b, "GREATER_THAN", size.outputs["Point Count"], 0, 600, -1100), stone, 800, -500)
    values = {"gem_r": b.math("MULTIPLY", w, 0.5, 800, -1300), "gem_size": w, "gem_length": ln, "gem_cut": cut,
              "gem_table": b.math("MULTIPLY", zmax, w, 800, -1460), "gem_culet": b.math("MULTIPLY", zmin, w, 800, -1620),
              "gem_crown": crown, "gem_cx": cx, "gem_cy": cy, "set_tilt": gi("Setting", "Tilt"),
              "set_below": gi("Setting", "Below Culet"), "set_subdiv": gi("Setting", "Subdivision"),
              "set_on": gi("Setting", "Set"), "set_round": gi("Setting", "Edge Round")}
    for i, (name, dtype) in enumerate(ATTRS):
        stone = store(b, stone, name, dtype, "INSTANCE", values[name], 1000 + 200 * i, -500)
    # второй невидимый носитель — контур: инстанс меша контура с масштабом 0 и gem_outline = 1 (gem_r = 0)
    b.section("Outline Carrier")
    # свои места вместо мест контура: вершины контура без рёбер убрать, свои добавить (приоритет:
    # свой меш > Outline > встроенный)
    o_loose = b.node("GeometryNodeDeleteGeometry", 1200, 2300, domain="POINT")
    b.link(outline, o_loose.inputs["Geometry"])
    b.link(icmp(b, "EQUAL", b.node("GeometryNodeInputMeshVertexNeighbors", 1000, 2500).outputs["Vertex Count"], 0,
                1200, 2500), o_loose.inputs["Selection"])
    carried = b.switch("GEOMETRY", has_own, outline, join(b, [o_loose.outputs["Geometry"], own_verts.outputs["Mesh"]],
                                                          1400, 2300), 1600, 2300)
    o_inst = b.node("GeometryNodeGeometryToInstance", 1400, 2000)
    b.link(carried, o_inst.inputs["Geometry"])
    o_carrier = store(b, transform(b, o_inst.outputs["Instances"], 1600, 2000, scale=(0.0, 0.0, 0.0)), "gem_outline",
                      "FLOAT", "INSTANCE", 1.0, 1800, 2000)
    o_carrier = gate(b, has_outline, o_carrier, 2000, 2000)
    out = join(b, [passing, stone, o_carrier], 1000 + 200 * len(ATTRS), 0)
    finish(b, ng, out, 1200 + 200 * len(ATTRS))
    restore_menu(ng, "Cut", CUTS, kept, had_cut)
    return ng


# --- My_Stone_Prongs ---------------------------------------------------------------------------

def build_claw_cage(b, d, bottom_z, dome_z, tilt, inter, table_z, crown, set_on, cover, height, claw_len, claw_tip,
                    bow, swell, ox, oy, crown_z0=0.0):
    """Клетка крапана-когтя: ящик из 4 колец по 4 вершины, основание на z = 0, ось +Z, ось X — наружу
    (как build_prong_cage, кладётся тем же сдвигом и наклоном). Кольцо — центр (cx, cz), направление
    пути n в плоскости XZ, полутолщина поперёк пути (в плоскости XZ), полуширина по Y у наружных и у
    внутренних вершин.
    Не Set — кольца на оси ствола, поперёк неё: основание, шейка (z_sh - CLAW_NECK ø, держит ствол
    прямым), плечо 0.9 hb на z_sh = площадка + Above Table, кончик Claw Tip % hb на Claw Length ø выше.
    Set — коготь дугой, по прежним крапанам Владимира (4 кольца, изгиб растянут на всю ногу): пятка; колено
    на оси на CLAW_KNEE высоты ноги, вынесено наружу на Claw Bow (клетка — на 1.5 Bow: предел (A + 4 B + C) / 6),
    толще поперёк на Claw Swell %; плечо — на оси над рундистом, вертикальное; кончик — клин: наружные вершины
    — спинка над плечом, внутренние — остриё на короне (ширина Claw Tip % hb). Спинка и остриё клетки — из
    предела SubD их угловых вершин (CLAW_W_*): верх крюка на Set Height % высоты площадки, остриё — на
    Set Cover % пути по короне, утоплено по -N на CLAW_TIP_SINK ø (точный контакт даёт рез оболочкой камня).
    Плоскость крапана (мир): x — наружу от оси крапана на рундисте, z — от плоскости рундиста; место на
    рундисте — x = -rk; корона (0, z0) — (c, h) от места внутрь. crown_z0 — высота начала короны у места."""
    _pr, rc, _gc = mods()
    b.section("Claw Cage")
    cnt = [0]

    def at():
        cnt[0] += 1
        return ox + 180 * (cnt[0] // 14), oy - 150 * (cnt[0] % 14)

    def m(op, a, c=None):
        return b.math(op, a, c, *at())

    def ma(a, k, c):
        return madd(b, a, k, c, *at())

    cos_t, sin_t = m("COSINE", tilt), m("SINE", tilt)
    hb = m("MULTIPLY", d, rc.H_BOT)
    tip_h = m("MULTIPLY", hb, m("DIVIDE", claw_tip, 100.0))
    rk = m("MULTIPLY", d, m("SUBTRACT", 0.5, m("DIVIDE", inter, 100.0)))   # ось крапана от рундиста
    boff = m("DIVIDE", bottom_z, cos_t)
    low = m("MULTIPLY", d, rc.MIN_BREAK)

    def axis_z(zw):
        """высота в системе ствола точки оси на высоте zw над рундистом"""
        return m("SUBTRACT", m("DIVIDE", zw, cos_t), boff)

    def to_stem(xw, z):
        """точка плоскости крапана в мире (x наружу от оси на рундисте, z) -> система ствола (x, z)"""
        return (m("SUBTRACT", m("MULTIPLY", xw, cos_t), m("MULTIPLY", z, sin_t)),
                m("SUBTRACT", m("ADD", m("MULTIPLY", xw, sin_t), m("MULTIPLY", z, cos_t)), boff))

    # --- заготовка: кольца на оси, поперёк ствола: (cx, cz, nx, nz, полутолщина, полуширина x 2) ---
    z1 = m("MAXIMUM", axis_z(ma(d, -CLAW_NECK, dome_z)), low)
    z2 = m("MAXIMUM", axis_z(dome_z), ma(d, 0.05, z1))
    z3 = ma(claw_len, d, z2)
    sh, tp = m("MULTIPLY", hb, 0.9), tip_h
    # шейка: предел SubD ~ (основание + 4 шейка + плечо) / 6 — шейка чуть больше hb, чтобы ствол у неё был ø
    nk = m("MULTIPLY", hb, CLAW_NECK_SIZE)
    blank = [(0.0, 0.0, 0.0, 1.0, hb, hb, hb), (0.0, z1, 0.0, 1.0, nk, nk, nk), (0.0, z2, 0.0, 1.0, sh, sh, sh),
             (0.0, z3, 0.0, 1.0, tp, tp, tp)]

    # --- коготь Set ---
    c, h = crown, m("SUBTRACT", table_z, crown_z0)        # h — подъём короны от её начала
    ln = m("SQRT", m("ADD", m("MULTIPLY", c, c), m("MULTIPLY", h, h)))
    cov = m("MAXIMUM", m("DIVIDE", cover, 100.0), 0.05)
    sink = m("MULTIPLY", d, CLAW_TIP_SINK)
    # колено
    zk = m("MAXIMUM", axis_z(m("MULTIPLY", bottom_z, CLAW_KNEE)), low)
    ht_k = m("MULTIPLY", hb, ma(swell, 0.015, 1.0))        # клетка: 1 + 1.5 Swell
    # плечо: на оси, вертикально
    z_c = m("MULTIPLY", d, CLAW_SHOULDER)
    c_s = to_stem(0.0, z_c)
    ht_c = m("MULTIPLY", hb, 1.02)
    # предел острия: точка короны на cov пути, утоплена по -N = (h, -c) / L на sink (x наружу: внутрь = -x)
    x_l = m("SUBTRACT", m("MULTIPLY", m("ADD", rk, m("MULTIPLY", cov, c)), -1.0), m("MULTIPLY", sink, m("DIVIDE", h, ln)))
    z_l = m("SUBTRACT", ma(cov, h, crown_z0), m("MULTIPLY", sink, m("DIVIDE", c, ln)))
    # предел верха крюка: Set Height % высоты площадки, не ниже плеча + 0.3 ø (крюк не ниже своего плеча)
    z_t = m("MAXIMUM", m("MULTIPLY", m("MULTIPLY", table_z, m("DIVIDE", height, 100.0)), CLAW_TOP), ma(d, 0.3, z_c))
    x_b = m("MULTIPLY", d, -CLAW_BACK)
    wo, ws, wf = CLAW_W_OWN, CLAW_W_SIDE, CLAW_W_FAR
    # остриё: x_l = wo x_p + ws x_b + ws (-ht_c) + wf ht_c
    x_p = m("DIVIDE", ma(ht_c, ws - wf, ma(x_b, -ws, x_l)), wo)
    # высоты спинки и острия: z_t = wo z_b + ws z_p + (ws + wf) z_c, z_l = wo z_p + ws z_b + (ws + wf) z_c
    kz = m("MULTIPLY", z_c, ws + wf)
    rt, rl = m("SUBTRACT", z_t, kz), m("SUBTRACT", z_l, kz)
    det = wo * wo - ws * ws
    z_b = m("MAXIMUM", m("DIVIDE", m("SUBTRACT", m("MULTIPLY", rt, wo), m("MULTIPLY", rl, ws)), det), ma(d, 0.25, z_c))
    z_p = m("DIVIDE", m("SUBTRACT", m("MULTIPLY", rl, wo), m("MULTIPLY", rt, ws)), det)
    bs, ps = to_stem(x_b, z_b), to_stem(x_p, z_p)
    ex, ez = m("SUBTRACT", bs[0], ps[0]), m("SUBTRACT", bs[1], ps[1])
    el = m("MAXIMUM", m("SQRT", m("ADD", m("MULTIPLY", ex, ex), m("MULTIPLY", ez, ez))), 1e-4)
    claw = [(0.0, 0.0, 0.0, 1.0, hb, hb, hb),
            (m("MULTIPLY", bow, 1.5), zk, 0.0, 1.0, ht_k, hb, hb),
            (c_s[0], c_s[1], m("MULTIPLY", sin_t, -1.0), cos_t, ht_c, hb, hb),
            # кольцо-клин: e = (спинка - остриё) / длина = (nz, -nx)
            (m("MULTIPLY", m("ADD", bs[0], ps[0]), 0.5), m("MULTIPLY", m("ADD", bs[1], ps[1]), 0.5),
             m("MULTIPLY", m("DIVIDE", ez, el), -1.0), m("DIVIDE", ex, el), m("MULTIPLY", el, 0.5),
             m("MULTIPLY", hb, 1.05), tip_h)]

    # --- клетка: цилиндр 4 x 4 кольца, crease на кольце основания ---
    b.section("Claw Cage")
    segs = 3
    cyl = b.node("GeometryNodeMeshCylinder", ox - 800, oy, fill_type="NGON")
    cyl.inputs["Vertices"].default_value = 4
    cyl.inputs["Side Segments"].default_value = segs
    cyl.inputs["Radius"].default_value = 2.0 ** 0.5
    cyl.inputs["Depth"].default_value = 2.0
    # углы на диагоналях (+-1, +-1): сторона квадрата смотрит на камень
    rot = transform(b, cyl.outputs["Mesh"], ox - 600, oy, rotation=(0.0, 0.0, pi / 4))
    p = sep(b, b.node("GeometryNodeInputPosition", ox - 600, oy - 300).outputs[0], ox - 400, oy - 300)
    geo = store(b, rot, "crease_edge", "FLOAT", "EDGE", b.cmp("LESS_THAN", p["Z"], -0.8, ox - 400, oy - 450),
                ox - 400, oy)
    rings = [tuple(b.switch("FLOAT", set_on, x, y_, *at()) for x, y_ in zip(r0, r1)) for r0, r1 in zip(blank, claw)]
    # угол кольца: центр + x * полутолщина * e + y * полуширина, e = (nz, -nx) — поперёк пути
    ring = m("ROUND", m("MULTIPLY", m("ADD", p["Z"], 1.0), segs * 0.5))
    cx, cz, nx, nzr, ht, hw_out, hw_in = (index_switch(b, "FLOAT", ring, [r[k] for r in rings], *at()) for k in range(7))
    hw = b.switch("FLOAT", b.cmp("GREATER_THAN", p["X"], 0.0, *at()), hw_in, hw_out, *at())
    sp = b.node("GeometryNodeSetPosition", *at())
    b.link(geo, sp.inputs["Geometry"])
    b.link(combine(b, ma(p["X"], m("MULTIPLY", ht, nzr), cx), m("MULTIPLY", p["Y"], hw),
                   ma(p["X"], m("MULTIPLY", m("MULTIPLY", ht, nx), -1.0), cz), *at()), sp.inputs["Position"])
    return sp.outputs["Geometry"]


def lattice_rings(b, geo, ids, rings, width, hh, x, y):
    """Брусок по решётке: кольцо k — отрезок (внутренняя, наружная точка) в плоскости XZ; поперёк — 4 точки
    отрезка (концы и на hh от них), вбок по Y — ±width/2 и на hh внутрь."""
    i, j, k = ids
    p_in = index_switch(b, "VECTOR", k, [r[0] for r in rings], x, y)
    p_out = index_switch(b, "VECTOR", k, [r[1] for r in rings], x, y - 200)
    seg = b.vmath("SUBTRACT", p_out, p_in, x + 200, y - 100)
    f = b.math("DIVIDE", hh, b.vmath("LENGTH", seg, None, x + 200, y - 300), x + 400, y - 300)
    frac = index_switch(b, "FLOAT", i, [0.0, f, b.math("SUBTRACT", 1.0, f, x + 600, y - 400), 1.0], x + 800, y - 300)
    half = b.math("MULTIPLY", width, 0.5, x + 400, y - 500)
    yy = index_switch(b, "FLOAT", j, [b.math("MULTIPLY", half, -1.0, x + 600, y - 500),
                                      b.math("SUBTRACT", hh, half, x + 600, y - 650),
                                      b.math("SUBTRACT", half, hh, x + 600, y - 800), half], x + 800, y - 550)
    q = sep(b, vma(b, seg, combine(b, frac, frac, frac, x + 1000, y - 300), p_in, x + 1000, y - 100), x + 1200, y - 100)
    sp = b.node("GeometryNodeSetPosition", x + 1400, y)
    b.link(geo, sp.inputs["Geometry"])
    b.link(combine(b, q["X"], yy, q["Z"], x + 1200, y - 300), sp.inputs["Position"])
    return sp.outputs["Geometry"]


def build_tab(b, d, bottom_z, dome_z, tilt, reach, table_z, crown, crown_z0, set_on, cover, tab_w, er, ox, oy):
    """Крапан-лапка: прямоугольная пластина ø (по нормали) x Tab Width (по касательной), в системе места
    крапана (начало — ось крапана на рундисте, X наружу, Z вверх). Наклон Tilt — сдвиг наружу на z tan T
    (верх остаётся горизонтальным). Не Set — прямо до площадки + Above Table, плоский верх. Set — изгиб на
    рундисте: ствол до пересечения с бруском на короне, брусок по линии короны когтя ((0, z0) — (c, h),
    утоплен на CLAW_SINK ø), до Set Cover %, торец поперёк короны. Решётка 4 x 4 x (4 | 7) с опорными
    петлями на EDGE_HOLD * Edge Round от рёбер (не больше 0.4 ø и 0.4 Tab Width)."""
    b.section("Tab")
    cnt = [0]

    def at():
        cnt[0] += 1
        return ox + 180 * (cnt[0] // 14), oy - 150 * (cnt[0] % 14)

    def m(op, a, c=None):
        return b.math(op, a, c, *at())

    def ma(a, k, c):
        return madd(b, a, k, c, *at())

    def pt(x, z):
        return combine(b, x, 0.0, z, *at())

    hh = m("MINIMUM", m("MAXIMUM", m("MULTIPLY", er, EDGE_HOLD), 0.01), m("MULTIPLY", m("MINIMUM", d, tab_w), 0.4))
    tt = m("TANGENT", tilt)
    half = m("MULTIPLY", d, 0.5)
    neg_half = m("MULTIPLY", half, -1.0)

    def stem(x0, z):
        return pt(ma(z, tt, x0), z)

    def flat(z):
        return (stem(neg_half, z), stem(half, z))
    off = [flat(bottom_z), flat(m("ADD", bottom_z, hh)), flat(m("SUBTRACT", dome_z, hh)), flat(dome_z)]

    # Set: линия короны x = -reach - t c + s Nx, z = z0 + t h' + s Nz (x наружу), h' = h - z0
    c = crown
    hp = m("SUBTRACT", table_z, crown_z0)
    ln = m("SQRT", m("ADD", m("MULTIPLY", c, c), m("MULTIPLY", hp, hp)))
    nx, nz = m("DIVIDE", hp, ln), m("DIVIDE", c, ln)
    ux, uz = m("DIVIDE", m("MULTIPLY", c, -1.0), ln), m("DIVIDE", hp, ln)
    sink = m("MULTIPLY", d, CLAW_SINK)
    s_in, s_out = m("MULTIPLY", sink, -1.0), m("SUBTRACT", d, sink)

    def on_line(t, s_):
        return (m("ADD", m("SUBTRACT", m("MULTIPLY", reach, -1.0), m("MULTIPLY", t, c)), m("MULTIPLY", s_, nx)),
                m("ADD", m("ADD", crown_z0, m("MULTIPLY", t, hp)), m("MULTIPLY", s_, nz)))

    def corner(x0, s_):
        """пересечение грани ствола x = x0 + z tan T с линией бруска s_"""
        num = m("ADD", m("ADD", m("ADD", x0, reach), m("MULTIPLY", crown_z0, tt)),
                m("MULTIPLY", s_, m("SUBTRACT", m("MULTIPLY", nz, tt), nx)))
        return on_line(m("DIVIDE", m("MULTIPLY", num, -1.0), m("ADD", c, m("MULTIPLY", hp, tt))), s_)
    ci, co = corner(neg_half, s_in), corner(half, s_out)
    sl = m("SQRT", m("ADD", 1.0, m("MULTIPLY", tt, tt)))
    sx, sz = m("DIVIDE", tt, sl), m("DIVIDE", 1.0, sl)              # вдоль ствола

    def shift(p_, dx, dz, k):
        return pt(ma(dx, k, p_[0]), ma(dz, k, p_[1]))
    cov = m("DIVIDE", cover, 100.0)
    ei, eo = on_line(cov, s_in), on_line(cov, s_out)
    neg_hh = m("MULTIPLY", hh, -1.0)
    bent = [flat(bottom_z), flat(m("ADD", bottom_z, hh)),
            (shift(ci, sx, sz, neg_hh), shift(co, sx, sz, neg_hh)), (pt(*ci), pt(*co)),
            (shift(ci, ux, uz, hh), shift(co, ux, uz, hh)), (shift(ei, ux, uz, neg_hh), shift(eo, ux, uz, neg_hh)),
            (pt(*ei), pt(*eo))]
    g4, ids4 = lattice(b, 4, 4, 4, ox - 600, oy)
    g7, ids7 = lattice(b, 4, 4, 7, ox - 600, oy - 800)
    straight = lattice_rings(b, g4, ids4, off, tab_w, hh, ox + 2600, oy)
    folded = lattice_rings(b, g7, ids7, bent, tab_w, hh, ox + 2600, oy - 800)
    return hold_crease(b, b.switch("GEOMETRY", set_on, straight, folded, ox + 4200, oy), er, ox + 4400, oy)


def build_v(b, sites, loop, sharp, v_on, path, d_inter, vt, vl, bottom_z, dome_z, tilt, table_z, set_on, cover,
            height, er, ox, oy):
    """V-крапан на острых вершинах петли (места, севшие на острую вершину; V at Corners). Два крыла вдоль
    сторон от угла (по касательным к соседним точкам петли), стенка V Thickness: Intersection % внутри
    рундиста, остальное снаружи, наружные грани параллельны сторонам, митра на острие; крыло кончается на
    V Length от угла вдоль стороны. Низ — у низа крапанов, верх плоский на площадке + Above Table; Tilt —
    сдвиг наружу по биссектрисе на z tan T. Set: выше рундиста наклон внутрь по биссектрисе так, что
    внутреннее ребро верха доходит до Set Cover % пути по короне от этого угла (свой путь места), верх на
    Set Height % площадки. Решётка 4 (поперёк) x 7 (вдоль) x (4 | 7) (по высоте) с опорными петлями на
    EDGE_HOLD * Edge Round. -> (меш V, точки мест с атрибутами _v_*)."""
    b.section("V Prong")
    cnt = [0]

    def at():
        cnt[0] += 1
        return ox + 180 * (cnt[0] // 14), oy - 150 * (cnt[0] % 14)

    def m(op, a, c=None):
        return b.math(op, a, c, *at())

    def vm(op, a, c=None):
        return b.vmath(op, a, c, *at())

    def attr_(name, dtype="FLOAT_VECTOR"):
        return attr(b, name, dtype, *at())

    # острые вершины петли: касательные к соседним точкам
    pos = b.node("GeometryNodeInputPosition", *at()).outputs[0]
    nxt = b.node("GeometryNodeOffsetPointInCurve", *at())
    nxt.inputs["Offset"].default_value = 1
    prv = b.node("GeometryNodeOffsetPointInCurve", *at())
    prv.inputs["Offset"].default_value = -1
    t_out = vm("NORMALIZE", vm("SUBTRACT", b.at_index(pos, nxt.outputs["Point Index"], "FLOAT_VECTOR", *at()), pos))
    t_in = vm("NORMALIZE", vm("SUBTRACT", b.at_index(pos, prv.outputs["Point Index"], "FLOAT_VECTOR", *at()), pos))
    marked = store(b, store(b, loop, "_vt_in", "FLOAT_VECTOR", "POINT", t_in, *at()), "_vt_out", "FLOAT_VECTOR", "POINT",
                   t_out, *at())
    cpts = b.node("GeometryNodeCurveToPoints", *at(), mode="EVALUATED")
    b.link(marked, cpts.inputs["Curve"])
    corners = b.node("GeometryNodeDeleteGeometry", *at(), domain="POINT")
    b.link(cpts.outputs["Points"], corners.inputs["Geometry"])
    b.link(b.boolean("NOT", sharp, None, *at()), corners.inputs["Selection"])
    corners = corners.outputs["Geometry"]
    near = b.node("GeometryNodeSampleNearest", *at(), domain="POINT")
    b.link(corners, near.inputs["Geometry"])
    b.link(pos, near.inputs["Sample Position"])

    def from_corner(field):
        n = b.node("GeometryNodeSampleIndex", *at(), data_type="FLOAT_VECTOR", domain="POINT")
        b.link(corners, n.inputs["Geometry"])
        b.link(field, b.enabled(n, "Value"))
        b.link(near.outputs["Index"], n.inputs["Index"])
        return b.enabled_out(n, "Value")
    on_corner = b.cmp("LESS_THAN", vm("DISTANCE", from_corner(pos), pos), 1e-3, *at())
    is_v = b.boolean("AND", v_on, on_corner, *at())
    sites = store(b, sites, "_v_on", "BOOLEAN", "POINT", is_v, *at())
    sites = store(b, sites, "_v_c", "FLOAT_VECTOR", "POINT", pos, *at())
    sites = store(b, sites, "_v_t1", "FLOAT_VECTOR", "POINT", from_corner(attr_("_vt_in")), *at())
    sites = store(b, sites, "_v_t2", "FLOAT_VECTOR", "POINT", from_corner(attr_("_vt_out")), *at())
    sites = store(b, sites, "_v_path", "FLOAT", "POINT", path, *at())

    # решётки: Set выкл — 4 уровня по высоте, Set — 7 (опорные петли у изгиба на рундисте)
    hh = m("MINIMUM", m("MAXIMUM", m("MULTIPLY", er, EDGE_HOLD), 0.01), m("MULTIPLY", m("MINIMUM", vt, vl), 0.4))
    g4, ids4 = lattice(b, 4, 7, 4, *at())
    g7, ids7 = lattice(b, 4, 7, 7, *at())
    z_s = m("MULTIPLY", table_z, m("DIVIDE", height, 100.0))
    neg_hh = m("MULTIPLY", hh, -1.0)

    def place(geo, ids, levels):
        # номера решётки — до инстансов (после Realize положение уже сдвинуто в угол)
        for name, f in zip(("_vli", "_vlk", "_vlj"), ids):
            geo = store(b, geo, name, "FLOAT", "POINT", f, *at())
        i, k, j = (attr_(name, "FLOAT") for name in ("_vli", "_vlk", "_vlj"))
        iop = b.node("GeometryNodeInstanceOnPoints", *at())
        b.link(sites, iop.inputs["Points"])
        b.link(geo, iop.inputs["Instance"])
        b.link(attr(b, "_v_on", "BOOLEAN", *at()), iop.inputs["Selection"])
        real = b.node("GeometryNodeRealizeInstances", *at())
        b.link(iop.outputs["Instances"], real.inputs["Geometry"])
        c, t1, t2, pth = attr_("_v_c"), attr_("_v_t1"), attr_("_v_t2"), attr_("_v_path", "FLOAT")
        bis = vm("SCALE", vm("NORMALIZE", vm("ADD", t1, t2)), -1.0)
        dot = vm("DOT_PRODUCT", t1, t2)
        sinh = m("SQRT", m("MAXIMUM", m("MULTIPLY", m("SUBTRACT", 1.0, dot), 0.5), 1e-8))
        coth = m("DIVIDE", m("SQRT", m("MAXIMUM", m("MULTIPLY", m("ADD", 1.0, dot), 0.5), 0.0)), sinh)
        s1, s2 = sep(b, t1, *at()), sep(b, t2, *at())
        n1 = combine(b, m("MULTIPLY", s1["Y"], -1.0), s1["X"], 0.0, *at())      # наружу у стороны назад
        n2 = combine(b, s2["Y"], m("MULTIPLY", s2["X"], -1.0), 0.0, *at())      # наружу у стороны вперёд
        u_in = m("MULTIPLY", vt, m("MULTIPLY", d_inter, -1.0))
        u_out = m("ADD", vt, u_in)
        u = index_switch(b, "FLOAT", i, [u_in, m("ADD", u_in, hh), m("SUBTRACT", u_out, hh), u_out], *at())
        s_m = m("MULTIPLY", m("MULTIPLY", u, coth), -1.0)                      # станция митры у этой грани
        s_k = index_switch(b, "FLOAT", k, [vl, m("SUBTRACT", vl, hh), m("ADD", s_m, hh), 0.0, m("ADD", s_m, hh),
                                           m("SUBTRACT", vl, hh), vl], *at())
        t_k = index_switch(b, "VECTOR", k, [t1, t1, t1, t1, t2, t2, t2], *at())
        n_k = index_switch(b, "VECTOR", k, [n1, n1, n1, n1, n2, n2, n2], *at())
        wing = vm("ADD", vma(b, t_k, combine(b, s_k, s_k, s_k, *at()), c, *at()), vm("SCALE", n_k, u))
        mitre = vma(b, bis, combine(b, *([m("DIVIDE", u, sinh)] * 2), 0.0, *at()), c, *at())
        plan = b.switch("VECTOR", icmp(b, "EQUAL", k, 3, *at()), wing, mitre, *at())
        z = index_switch(b, "FLOAT", j, levels, *at())
        # сдвиг по биссектрисе: наружу z tan T, при Set выше рундиста — внутрь до cov пути у верха
        cov = m("DIVIDE", cover, 100.0)
        lam_top = m("MAXIMUM", m("ADD", m("SUBTRACT", m("MULTIPLY", cov, pth), m("DIVIDE", m("MULTIPLY", vt, d_inter),
                                                                                         sinh)),
                                     m("MULTIPLY", z_s, m("TANGENT", tilt))), 0.0)
        lam = b.switch("FLOAT", set_on, 0.0, m("MULTIPLY", m("DIVIDE", m("MAXIMUM", z, 0.0), z_s), lam_top), *at())
        off = m("SUBTRACT", m("MULTIPLY", z, m("TANGENT", tilt)), lam)
        p_ = vm("ADD", vma(b, bis, combine(b, off, off, 0.0, *at()), plan, *at()), combine(b, 0.0, 0.0, z, *at()))
        sp = b.node("GeometryNodeSetPosition", *at())
        b.link(real.outputs["Geometry"], sp.inputs["Geometry"])
        b.link(p_, sp.inputs["Position"])
        return sp.outputs["Geometry"]
    straight = place(g4, ids4, [bottom_z, m("ADD", bottom_z, hh), m("SUBTRACT", dome_z, hh), dome_z])
    leaning = place(g7, ids7, [bottom_z, m("ADD", bottom_z, hh), neg_hh, 0.0, hh, m("SUBTRACT", z_s, hh), z_s])
    vmesh = hold_crease(b, b.switch("GEOMETRY", set_on, straight, leaning, *at()), er, *at())
    return vmesh, sites


def build_prongs():
    _pr, rc, _gc = mods()
    kept, had_tip = menu_values(bpy.data.node_groups.get(PRONGS), "Tip")
    ng, b, gi = begin(PRONGS)
    move_first(ng, "Tip")
    src, use_obj = stone_source(b, gi, -200, 2400)
    v = read_stone(b, src, 200, 2400)
    is_em = icmp(b, "EQUAL", v["gem_cut"], 1, 1400, 2600)
    d = gi("Prongs", "ø")
    tilt = v["set_tilt"]

    # огранка по контуру: крапан на каждом месте контура (вершина без рёбер), ось на site + n * reach,
    # n — наружная нормаль предела петли в ближайшей точке (как My_Gem_Cast); Count и ° Z не действуют
    base, has_o = outline_mesh(b, src, v["gem_size"], v["gem_length"], 600, -3000)
    fr = outline_loop(b, base, 1800, -3000)
    b.section("Outline Sites")
    x0, y0 = 5600, -3000
    pos = b.node("GeometryNodeInputPosition", x0, y0 - 800).outputs[0]
    lone = icmp(b, "EQUAL", b.node("GeometryNodeInputMeshVertexNeighbors", x0, y0 - 200).outputs["Vertex Count"], 0,
                x0 + 200, y0 - 200)
    sites = b.node("GeometryNodeMeshToPoints", x0 + 400, y0, mode="VERTICES")
    b.link(base, sites.inputs["Mesh"])
    b.link(lone, sites.inputs["Selection"])
    limit = fr["limit"]
    near = b.node("GeometryNodeSampleNearest", x0 + 400, y0 - 400, domain="POINT")
    b.link(limit.outputs["Points"], near.inputs["Geometry"])
    b.link(pos, near.inputs["Sample Position"])
    tangent = b.node("GeometryNodeSampleIndex", x0 + 600, y0 - 400, data_type="FLOAT_VECTOR", domain="POINT")
    b.link(limit.outputs["Points"], tangent.inputs["Geometry"])
    b.link(limit.outputs["Tangent"], b.enabled(tangent, "Value"))
    b.link(near.outputs["Index"], tangent.inputs["Index"])
    normal = b.vmath("NORMALIZE", b.vmath("CROSS_PRODUCT", b.enabled_out(tangent, "Value"), (0.0, 0.0, 1.0),
                                          x0 + 800, y0 - 400), None, x0 + 1000, y0 - 400)
    # место — его проекция: ближайшая точка предела петли (точка, поставленная примерно, садится на рундист)
    snap = b.node("GeometryNodeSampleIndex", x0 + 600, y0 - 600, data_type="FLOAT_VECTOR", domain="POINT")
    b.link(limit.outputs["Points"], snap.inputs["Geometry"])
    b.link(b.node("GeometryNodeInputPosition", x0 + 400, y0 - 700).outputs[0], b.enabled(snap, "Value"))
    b.link(near.outputs["Index"], snap.inputs["Index"])
    # Aim Center: направление крапана — от нормали контура (0 %) к направлению от центра камня (100 %);
    # у груши коготь на боку головки по нормали смотрит поперёк камня, а ювелир загибает его к центру
    aim = b.math("DIVIDE", gi("Prongs", "Aim Center"), 100.0, x0 + 600, y0 - 1000)
    radial = b.vmath("NORMALIZE", b.vmath("MULTIPLY", b.enabled_out(snap, "Value"), (1.0, 1.0, 0.0), x0 + 800, y0 - 800),
                     None, x0 + 1000, y0 - 800)
    normal = b.vmath("NORMALIZE", b.vmath("ADD", b.vmath("SCALE", normal, b.math("SUBTRACT", 1.0, aim, x0 + 800, y0 - 1000),
                                                        x0 + 1000, y0 - 1000),
                                          b.vmath("SCALE", radial, aim, x0 + 1000, y0 - 1150), x0 + 1200, y0 - 1000),
                     None, x0 + 1400, y0 - 1000)
    o_cap = b.capture(sites.outputs["Points"], {"N": ("VECTOR", normal)}, x0 + 1200, y0)
    on_limit = b.node("GeometryNodeSetPosition", x0 + 1400, y0 + 200)
    b.link(o_cap.outputs["Geometry"], on_limit.inputs["Geometry"])
    b.link(b.enabled_out(snap, "Value"), on_limit.inputs["Position"])
    o_sites = on_limit.outputs["Geometry"]
    # путь по короне на контуре: для каждого места — по горизонтали от места внутрь (-n) до края площадки
    # настоящего камня (луч по призме из вершин площадки), один на все крапана — минимум по местам.
    # gem_crown (W (0.5 - max |x| площадки)) у мест на диагоналях и углах неверен (Cushion: заход 0.09 при 0.40)
    b.section("Outline Crown")
    xc, yc = x0, y0 - 1400
    stone = stone_mesh(b, src, v["gem_size"], v["gem_length"], xc - 1200, yc)
    sbb = b.node("GeometryNodeBoundBox", xc, yc)
    b.link(stone, sbb.inputs["Geometry"])
    on_table = b.cmp("GREATER_THAN", sep(b, b.node("GeometryNodeInputPosition", xc, yc - 300).outputs[0], xc + 200,
                                         yc - 300)["Z"],
                     b.math("MULTIPLY", sep(b, sbb.outputs["Max"], xc + 200, yc - 150)["Z"], 0.999, xc + 400, yc - 150),
                     xc + 600, yc - 300)
    table = b.node("GeometryNodeMeshToPoints", xc + 400, yc, mode="VERTICES")
    b.link(stone, table.inputs["Mesh"])
    b.link(on_table, table.inputs["Selection"])
    prism = b.node("GeometryNodeConvexHull", xc + 1000, yc)
    b.link(join(b, [transform(b, table.outputs["Points"], xc + 600, yc, translation=(0.0, 0.0, -50.0)),
                    transform(b, table.outputs["Points"], xc + 600, yc - 150, translation=(0.0, 0.0, 50.0))],
                xc + 800, yc), prism.inputs["Geometry"])
    ray = b.node("GeometryNodeRaycast", xc + 1200, yc - 300)
    b.link(prism.outputs["Convex Hull"], ray.inputs["Target Geometry"])
    b.link(pos, ray.inputs["Source Position"])
    b.link(b.vmath("SCALE", o_cap.outputs["N"], -1.0, xc + 1000, yc - 450), ray.inputs["Ray Direction"])
    crown_o = stat(b, o_sites, ray.outputs["Hit Distance"], ray.outputs["Is Hit"], "POINT", "Min", xc + 1400, yc - 300)
    # начало короны когтя — верх рундиста у места с кратчайшим путём: луч сверху чуть внутри от места
    # (у Cushion, Octagon, Flanders корона у рундиста на 0.2-0.5 мм выше хорды из плоскости рундиста —
    # коготь на хорде уходил в камень и срезался посадкой)
    down = b.node("GeometryNodeRaycast", xc + 1200, yc - 700)
    b.link(stone, down.inputs["Target Geometry"])
    b.link(vma(b, o_cap.outputs["N"], (-0.01, -0.01, 0.0), b.vmath("ADD", pos, (0.0, 0.0, 50.0), xc + 800, yc - 850),
               xc + 1000, yc - 700), down.inputs["Source Position"])
    down.inputs["Ray Direction"].default_value = (0.0, 0.0, -1.0)
    shortest = b.cmp("LESS_EQUAL", ray.outputs["Hit Distance"], b.math("ADD", crown_o, 1e-5, xc + 1200, yc - 1000),
                     xc + 1400, yc - 1000)
    z0_o = stat(b, o_sites, sep(b, down.outputs["Hit Position"], xc + 1400, yc - 850)["Z"], shortest, "POINT", "Max",
                xc + 1600, yc - 850)
    b.frame = None
    crown = b.switch("FLOAT", has_o, v["gem_crown"], crown_o, 1300, 1700)
    crown_z0 = b.switch("FLOAT", has_o, 0.0, z0_o, 1300, 1850)

    b.section("Heights")
    flat_z = b.math("SUBTRACT", v["gem_culet"], v["set_below"], 1400, 1400)
    # низ крапана плоский, вровень с низом каста (flat_z): клетка строится ниже на ø tan |T| (наклонённое
    # основание целиком под плоскостью), после Subdivision всё, что ниже flat_z, поднимается на неё
    bottom_z = b.math("SUBTRACT", flat_z, b.math("MULTIPLY", d, b.math("TANGENT", b.math("ABSOLUTE", tilt, None, 1000, 1550),
                                                                       None, 1200, 1550), 1400, 1550), 1600, 1400)
    dome_z = b.math("ADD", v["gem_table"], gi("Prongs", "Above Table"), 1400, 1250)
    cos_t = b.math("COSINE", tilt, None, 1400, 1100)
    cage = rc.build_prong_cage(b, d, bottom_z, dome_z, tilt, cos_t, gi("Prongs", "Intersection"), v["gem_table"],
                               crown, (v["set_on"], gi("Prongs", "Set Cover"), gi("Prongs", "Set Height")),
                               0, 3200)
    claw = build_claw_cage(b, d, bottom_z, dome_z, tilt, gi("Prongs", "Intersection"), v["gem_table"], crown,
                           v["set_on"], gi("Prongs", "Set Cover"), gi("Prongs", "Set Height"),
                           gi("Prongs", "Claw Length"), gi("Prongs", "Claw Tip"), gi("Prongs", "Claw Bow"),
                           gi("Prongs", "Claw Swell"), 600, 6400, crown_z0)
    b.frame = None
    tip = menu_switch(b, gi(None, "Tip"), TIPS, 1100, 700)
    is_claw = icmp(b, "EQUAL", tip, 1, 1300, 700)
    is_tab = icmp(b, "EQUAL", tip, 2, 1300, 850)
    cage = b.switch("GEOMETRY", is_claw, cage, claw, 1300, 400)
    # низ на bottom_z, наклон Tilt вокруг Y (ось через начало координат на z = 0)
    b.section("Prong Sites")
    pc = transform(b, cage, 1500, 400, translation=combine(b, 0.0, 0.0, b.math("DIVIDE", bottom_z, cos_t, 1500, 250),
                                                           1500, 100))
    pc = transform(b, pc, 1700, 400, rotation=axis_angle(b, (0.0, 1.0, 0.0), tilt, 1700, 100))
    keep = b.math("SUBTRACT", 0.5, b.math("DIVIDE", gi("Prongs", "Intersection"), 100.0, 1500, -200), 1700, -200)
    reach = b.math("MULTIPLY", d, keep, 1900, -200)
    tab = build_tab(b, d, bottom_z, dome_z, tilt, reach, v["gem_table"], crown, crown_z0, v["set_on"],
                    gi("Prongs", "Set Cover"), gi("Prongs", "Tab Width"), v["set_round"], 600, 9000)
    b.frame = None
    pc = b.switch("GEOMETRY", is_tab, pc, tab, 1900, 400)
    # Round: Count точек на окружности W/2 + reach, поворот ° Z
    circle = b.node("GeometryNodeMeshCircle", 2100, 100, fill_type="NONE")
    b.link(gi("Prongs", "Count"), circle.inputs["Vertices"])
    b.link(b.math("ADD", v["gem_r"], reach, 2100, -100), circle.inputs["Radius"])
    round_pts = transform(b, circle.outputs["Mesh"], 2300, 100,
                          rotation=axis_angle(b, (0.0, 0.0, 1.0), gi("Prongs", "° Z"), 2300, -100))
    # Emerald: середины срезов углов + n * reach; n = S (cy, cx) / |(cx, cy)|, S — знаки четверти
    idx = b.node("GeometryNodeInputIndex", 2100, -400).outputs[0]
    quad = index_switch(b, "VECTOR", idx, [(1.0, 1.0, 0.0), (-1.0, 1.0, 0.0), (-1.0, -1.0, 0.0), (1.0, -1.0, 0.0)],
                        2300, -400)
    cx, cy = v["gem_cx"], v["gem_cy"]
    hyp = b.vmath("LENGTH", combine(b, cx, cy, 0.0, 2100, -700), None, 2300, -700)
    n_em = b.vmath("MULTIPLY", quad, combine(b, b.math("DIVIDE", cy, hyp, 2300, -850),
                                             b.math("DIVIDE", cx, hyp, 2300, -1000), 0.0, 2500, -850), 2700, -700)
    mid = b.vmath("MULTIPLY", quad, combine(b, madd(b, cx, -0.5, b.math("MULTIPLY", v["gem_size"], 0.5, 2300, -1150),
                                                    2500, -1150),
                                            madd(b, cy, -0.5, b.math("MULTIPLY", v["gem_length"], 0.5, 2300, -1300),
                                                 2500, -1300), 0.0, 2700, -1150), 2900, -1000)
    em = b.node("GeometryNodePoints", 3100, -400)
    em.inputs["Count"].default_value = 4
    b.link(vma(b, n_em, combine(b, reach, reach, 0.0, 2900, -1300), mid, 3100, -1000), em.inputs["Position"])
    pts = b.switch("GEOMETRY", is_em, round_pts, em.outputs["Points"], 3300, 100)
    # ось X крапана — наружу (поворот только вокруг Z)
    pos = b.node("GeometryNodeInputPosition", 3100, -1400).outputs[0]
    n = b.switch("VECTOR", is_em, b.vmath("NORMALIZE", pos, None, 3300, -1400), n_em, 3500, -1400)
    vmesh, o_sites_v = build_v(b, o_sites, fr["loop"], fr["sharp"], gi("Prongs", "V at Corners"),
                               ray.outputs["Hit Distance"], b.math("DIVIDE", gi("Prongs", "Intersection"), 100.0,
                                                                   3800, -5200),
                               gi("Prongs", "V Thickness"), gi("Prongs", "V Length"), bottom_z, dome_z, tilt,
                               v["gem_table"], v["set_on"], gi("Prongs", "Set Cover"), gi("Prongs", "Set Height"),
                               v["set_round"], 600, -12000)
    vmesh = gate(b, has_o, vmesh, 4100, -1800)
    b.section("Outline Sites")
    x0, y0 = 5600, -3000
    at_axis = b.node("GeometryNodeSetPosition", x0 + 1400, y0)
    b.link(o_sites_v, at_axis.inputs["Geometry"])
    b.link(vma(b, o_cap.outputs["N"], combine(b, reach, reach, 0.0, x0 + 1200, y0 - 600), pos, x0 + 1400, y0 - 400),
           at_axis.inputs["Position"])
    b.frame = None
    pts = b.switch("GEOMETRY", has_o, pts, at_axis.outputs["Geometry"], 3500, 100)
    n = b.switch("VECTOR", has_o, n, o_cap.outputs["N"], 3600, -1400)
    face_out = b.node("FunctionNodeAlignRotationToVector", 3700, -1400, axis="X", pivot_axis="Z")
    b.link(n, face_out.inputs["Vector"])
    iop = b.node("GeometryNodeInstanceOnPoints", 3700, 400)
    b.link(pts, iop.inputs["Points"])
    b.link(pc, iop.inputs["Instance"])
    b.link(face_out.outputs["Rotation"], iop.inputs["Rotation"])
    # места с V — без обычного крапана
    b.link(b.boolean("NOT", attr(b, "_v_on", "BOOLEAN", 3500, 600), None, 3700, 600), iop.inputs["Selection"])
    real = b.node("GeometryNodeRealizeInstances", 3900, 400)
    b.link(iop.outputs["Instances"], real.inputs["Geometry"])
    clean = b.node("GeometryNodeRemoveAttribute", 4000, 300)
    clean.inputs["Pattern Mode"].default_value = "Wildcard"
    clean.inputs["Name"].default_value = "_v*"
    b.link(join(b, [real.outputs["Geometry"], vmesh], 3950, 300), clean.inputs["Geometry"])
    prongs = clean.outputs["Geometry"]
    # места крапанов для My_Stone_Cast (корона): Count и ° Z — на инстансе камня в потоке (как set_seated;
    # Store на домене INSTANCE ссылку на объект камня не ломает); Emerald и контур — места по своим правилам
    marked = b.g("Geometry")
    is_gem = b.cmp("GREATER_THAN", attr(b, "gem_r", "FLOAT", 3900, 1100), 0.0, 4100, 1100)
    for k_, (name, dtype, value) in enumerate((("set_count", "INT", gi("Prongs", "Count")),
                                               ("set_rotz", "FLOAT", gi("Prongs", "° Z")))):
        mk = b.node("GeometryNodeStoreNamedAttribute", 4100 + 200 * k_, 900, data_type=dtype, domain="INSTANCE")
        mk.inputs["Name"].default_value = name
        b.link(marked, mk.inputs["Geometry"])
        b.link(is_gem, mk.inputs["Selection"])
        b.link(value, mk.inputs["Value"])
        marked = mk.outputs["Geometry"]

    # --- Subdivision: 0 — голая клетка с crease_edge ---
    b.section("Subdivision")
    has_sd = icmp(b, "GREATER_THAN", v["set_subdiv"], 0, 4100, 700)
    prongs = b.switch("GEOMETRY", has_sd, prongs, subd(b, prongs, v["set_subdiv"], 4300, 400), 4500, 400)
    b.section("Flat Foot")
    foot = b.node("GeometryNodeSetPosition", 4700, 400)
    b.link(prongs, foot.inputs["Geometry"])
    fp = sep(b, b.node("GeometryNodeInputPosition", 4300, 100).outputs[0], 4500, 100)
    b.link(combine(b, fp["X"], fp["Y"], b.math("MAXIMUM", fp["Z"], flat_z, 4500, -100), 4700, 100),
           foot.inputs["Position"])
    prongs = foot.outputs["Geometry"]
    b.frame = None
    finish(b, ng, finish_metal(b, gi, "Prongs", v, use_obj, prongs, 4800, stream=marked), 6500)
    restore_menu(ng, "Tip", TIPS, kept, had_tip)
    return ng


# --- My_Stone_Cast -----------------------------------------------------------------------------

# Emerald: вершина k восьмиугольника рундиста (против часовой) = K1 (W/2, L/2) - K2 (cx, cy)
OCT_K1 = [(1, 1), (1, 1), (-1, 1), (-1, 1), (-1, -1), (-1, -1), (1, -1), (1, -1)]
OCT_K2 = [(0, 1), (1, 0), (-1, 0), (0, 1), (0, -1), (-1, 0), (1, 0), (0, -1)]


def build_cast():
    _pr, rc, gc = mods()
    kept, had_type = menu_values(bpy.data.node_groups.get(CAST), "Type")
    kept_rail, had_rail = menu_values(bpy.data.node_groups.get(CAST), "Rail Shape")
    ng, b, gi = begin(CAST)
    move_first(ng, "Type")
    src, use_obj = stone_source(b, gi, -200, 2400)
    v = read_stone(b, src, 200, 2400, ATTRS + [("set_count", "INT"), ("set_rotz", "FLOAT")])
    is_em = icmp(b, "EQUAL", v["gem_cut"], 1, 1400, 2600)
    cast_type = menu_switch(b, gi(None, "Type"), CAST_TYPES, 1200, 2900)
    is_bezel = icmp(b, "EQUAL", cast_type, 1, 1400, 2900)
    is_basket = icmp(b, "EQUAL", cast_type, 2, 1400, 3050)
    is_crown = icmp(b, "EQUAL", cast_type, 3, 1400, 3350)
    rail_round = b.boolean("AND", is_basket, icmp(b, "EQUAL", menu_switch(b, gi("Basket", "Rail Shape"), RAIL_SHAPES,
                                                                              1200, 3200), 0, 1400, 3200), 1600, 3200)
    up = (0.0, 0.0, 1.0)

    # --- профиль: (d — отступ от контура, z) четырёх углов ---
    b.section("Profile")
    x0, y0 = 0, 0
    bottom_z = b.math("SUBTRACT", v["gem_culet"], v["set_below"], x0, y0)
    tan_t = b.math("TANGENT", v["set_tilt"], None, x0, y0 - 160)
    z_top = gi("Cast", "Z Offset")
    th = gi("Cast", "Cast Thickness")
    h_cast = b.math("MAXIMUM", b.math("SUBTRACT", z_top, bottom_z, x0 + 200, y0), rc.MIN_CAST, x0 + 400, y0)
    z_bot = b.math("SUBTRACT", z_top, h_cast, x0 + 600, y0)
    d_ot = gi("Cast", "XY Offset")
    d_ob = b.math("SUBTRACT", d_ot, b.math("MULTIPLY", h_cast, tan_t, x0 + 400, y0 - 160), x0 + 600, y0 - 160)
    d_it = b.math("SUBTRACT", d_ot, th, x0 + 600, y0 - 320)
    d_ib = b.math("SUBTRACT", d_ob, th, x0 + 600, y0 - 480)
    quad = b.node("GeometryNodeCurvePrimitiveQuadrilateral", x0 + 1000, y0, mode="POINTS")
    for i, (dd, zz) in enumerate(((d_ot, z_top), (d_ob, z_bot), (d_ib, z_bot), (d_it, z_top))):
        b.link(combine(b, dd, zz, 0.0, x0 + 800, y0 - 160 * i), quad.inputs["Point %d" % (i + 1)])

    # --- глухой каст: профиль 7 точек (d, z) ---
    # d_out(z) = Wall + z tan T, d_in(z) = d_out(z) - (Wall + Seat); верх — плоскость через (0, zt),
    # наружу вниз на BEZEL_BEVEL. Set: губа загнута на cov внутрь, наружная стенка над рундистом
    # наклонена на столько же (+ clr). Порядок точек — как у стенки: наружу вниз, внутрь вверх
    # (иначе грани вывернуты): 3, 2, 1, 7, 6, 5, 4 по нумерации описания.
    b.section("Bezel Profile")
    x0, y0 = 0, 1400
    wb, seat = gi("Bezel", "Wall"), gi("Bezel", "Seat")
    zt = b.math("MULTIPLY", v["gem_table"], b.math("DIVIDE", gi("Bezel", "Height"), 100.0, x0, y0), x0 + 200, y0)
    cov = b.math("MULTIPLY", v["gem_crown"], b.math("DIVIDE", gi("Bezel", "Bezel Cover"), 100.0, x0, y0 - 160),
                 x0 + 200, y0 - 160)
    clr = b.math("MULTIPLY", v["gem_size"], BEZEL_CLEAR, x0 + 200, y0 - 320)
    ws = b.math("ADD", wb, seat, x0 + 200, y0 - 480)
    tb = tan(BEZEL_BEVEL)

    def d_out(z, yy):
        return madd(b, z, tan_t, wb, x0 + 400, yy)

    def d_in(z, yy):
        return b.math("SUBTRACT", d_out(z, yy), ws, x0 + 600, yy)

    def top(d, yy):
        """z верхней плоскости над отступом d"""
        return madd(b, d, -tb, zt, x0 + 800, yy)

    o_zt = d_out(zt, y0 - 640)
    i_zt = d_in(zt, y0 - 800)
    d3s = b.math("SUBTRACT", o_zt, b.math("ADD", cov, clr, x0 + 600, y0 - 960), x0 + 800, y0 - 960)
    neg_cov = b.math("MULTIPLY", cov, -1.0, x0 + 400, y0 - 1120)
    set_on = v["set_on"]
    p3 = b.switch("VECTOR", set_on, combine(b, o_zt, top(o_zt, y0 - 640), 0.0, x0 + 1000, y0 - 640),
                  combine(b, d3s, madd(b, b.math("ADD", d3s, cov, x0 + 800, y0 - 1120), -tb, zt, x0 + 1000, y0 - 1120),
                          0.0, x0 + 1200, y0 - 1120), x0 + 1400, y0 - 640)
    p2 = combine(b, wb, 0.0, 0.0, x0 + 1200, y0)
    p1 = combine(b, d_out(bottom_z, y0 - 1280), bottom_z, 0.0, x0 + 1200, y0 - 1280)
    p7 = combine(b, d_in(bottom_z, y0 - 1440), bottom_z, 0.0, x0 + 1200, y0 - 1440)
    p6 = combine(b, b.math("SUBTRACT", wb, ws, x0 + 800, y0 - 1600), 0.0, 0.0, x0 + 1200, y0 - 1600)
    half = b.math("MULTIPLY", zt, 0.5, x0 + 400, y0 - 1760)
    p5 = b.switch("VECTOR", set_on, combine(b, d_in(half, y0 - 1760), half, 0.0, x0 + 1200, y0 - 1760),
                  combine(b, neg_cov, 0.0, 0.0, x0 + 1200, y0 - 1920), x0 + 1400, y0 - 1760)
    p4 = b.switch("VECTOR", set_on, combine(b, i_zt, top(i_zt, y0 - 800), 0.0, x0 + 1200, y0 - 800),
                  combine(b, neg_cov, zt, 0.0, x0 + 1200, y0 - 2080), x0 + 1400, y0 - 800)
    ring7 = b.node("GeometryNodeCurvePrimitiveCircle", x0 + 1400, y0 + 200, mode="RADIUS")
    ring7.inputs["Resolution"].default_value = 7
    at7 = b.node("GeometryNodeSetPosition", x0 + 1800, y0 + 200)
    b.link(ring7.outputs["Curve"], at7.inputs["Geometry"])
    b.link(index_switch(b, "VECTOR", b.node("GeometryNodeInputIndex", x0 + 1400, y0 - 200).outputs[0],
                        [p3, p2, p1, p7, p6, p5, p4], x0 + 1600, y0 - 200), at7.inputs["Position"])
    # _sc_h — рёбра, острые при любом Edge Round: наружное на рундисте (p2, размер Wall от контура; без Set оно
    # на прямой) и внутренний угол губы (p5: скругление вогнутого угла добавило бы металл и заход вырос бы)
    bezel_prof = store(b, at7.outputs["Geometry"], "_sc_h", "FLOAT", "POINT",
                       index_switch(b, "FLOAT", b.node("GeometryNodeInputIndex", x0 + 1800, y0 - 200).outputs[0],
                                    [0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0], x0 + 2000, y0 - 200), x0 + 2200, y0 + 200)

    # --- корзинка: два ранта, сечение — прямоугольник t x Rail, наружная линия d_out(z) = XY Offset + z tan T
    # (как крапана). Верхний — верх на Z Offset, нижний — низ на zb (низ крапанов). Круглый рант: клетка
    # больше в RAIL_EDGE (предел 4-точечного сечения — 11/12 полуразмера), центр на d_out - t/2, наружная
    # точка предела на d_out. Порядок углов — как у стенки (наружу вниз, внутрь вверх) ---
    b.section("Basket Profile")
    x0, y0 = 2000, 1400
    rail = b.math("MINIMUM", gi("Basket", "Rail"), b.math("MAXIMUM", b.math("SUBTRACT", z_top, bottom_z, x0, y0),
                                                           rc.MIN_CAST, x0 + 200, y0), x0 + 400, y0)
    half_t = b.math("MULTIPLY", th, 0.5, x0, y0 - 160)
    grow = b.switch("FLOAT", rail_round, 1.0, RAIL_EDGE, x0 + 200, y0 - 160)
    a_ = b.math("MULTIPLY", half_t, grow, x0 + 400, y0 - 160)                     # полуразмер по d
    c_ = b.math("MULTIPLY", b.math("MULTIPLY", rail, 0.5, x0 + 200, y0 - 320), grow, x0 + 400, y0 - 320)   # по z
    rails = []
    for i, zc in enumerate((madd(b, rail, -0.5, z_top, x0 + 600, y0), madd(b, rail, 0.5, bottom_z, x0 + 600, y0 - 160))):
        yy = y0 - 600 - 900 * i
        zt_, zb_ = b.math("ADD", zc, c_, x0 + 800, yy), b.math("SUBTRACT", zc, c_, x0 + 800, yy - 160)

        def dd(z, sign, yy2):
            """d угла: центр сечения d_out(z) - t/2 (наклон по T) +- полуразмер"""
            return madd(b, a_, sign, b.math("SUBTRACT", madd(b, z, tan_t, gi("Cast", "XY Offset"), x0 + 1000, yy2),
                                            half_t, x0 + 1200, yy2), x0 + 1400, yy2)
        q = b.node("GeometryNodeCurvePrimitiveQuadrilateral", x0 + 1800, yy, mode="POINTS")
        for k, (z, sg) in enumerate(((zt_, 1.0), (zb_, 1.0), (zb_, -1.0), (zt_, -1.0))):
            b.link(combine(b, dd(z, sg, yy - 160 * k), z, 0.0, x0 + 1600, yy - 160 * k), q.inputs["Point %d" % (k + 1)])
        # Upper Rail выключен — остаётся один нижний рант (спинка под камнем)
        rails.append(gate(b, gi("Basket", "Upper Rail"), q.outputs["Curve"], x0 + 1900, yy + 200) if i == 0
                     else q.outputs["Curve"])
    basket_prof = join(b, rails, x0 + 2000, y0 - 600)
    b.frame = None
    profile = b.switch("GEOMETRY", is_bezel, quad.outputs["Curve"], bezel_prof, 1400, 0)
    profile = b.switch("GEOMETRY", is_basket, profile, basket_prof, 1500, 0)
    # Edge Round > 0: рёбра сечения скругляют опорные точки у его углов (вместо crease); круглый рант — без них
    b.section("Edge Round")
    er_on = b.cmp("GREATER_THAN", v["set_round"], 0.0, 1400, 700)
    hh = b.math("MULTIPLY", v["set_round"], EDGE_HOLD, 1400, 550)
    profile = b.switch("GEOMETRY", b.boolean("AND", er_on, b.boolean("NOT", rail_round, None, 1600, 700), 1800, 700),
                       profile, hold_corners(b, profile, hh, None, [], 1700, 400, clear=("_sc_h",)), 4400, 0)
    b.frame = None
    profile = store(b, profile, "_sc_dz", "FLOAT_VECTOR", "POINT",
                    b.node("GeometryNodeInputPosition", 4400, -300).outputs[0], 4600, 0)

    # --- путь: 8 точек; P — точка контура, B — сдвиг на единицу отступа ---
    b.section("Path")
    x0, y0 = 0, -1000
    circle = b.node("GeometryNodeCurvePrimitiveCircle", x0, y0, mode="RADIUS")
    circle.inputs["Resolution"].default_value = 8
    k = b.node("GeometryNodeInputIndex", x0, y0 - 200).outputs[0]
    # Round: dir через 45°, P = dir W/2 / CAST_SHRINK, B = dir / CAST_SHRINK
    ang = b.math("MULTIPLY", k, pi / 4, x0 + 200, y0 - 200)
    dirv = combine(b, b.math("COSINE", ang, None, x0 + 400, y0 - 200), b.math("SINE", ang, None, x0 + 400, y0 - 360),
                   0.0, x0 + 600, y0 - 200)
    b_r = b.vmath("SCALE", dirv, 1.0 / rc.CAST_SHRINK, x0 + 800, y0 - 360)
    p_r = b.vmath("SCALE", b_r, v["gem_r"], x0 + 1000, y0 - 200)
    # Emerald: восьмиугольник, B — митра по нормалям соседних сторон
    k1 = index_switch(b, "VECTOR", k, [(a, c, 0.0) for a, c in OCT_K1], x0 + 200, y0 - 600)
    k2 = index_switch(b, "VECTOR", k, [(a, c, 0.0) for a, c in OCT_K2], x0 + 200, y0 - 900)
    half = combine(b, b.math("MULTIPLY", v["gem_size"], 0.5, x0 + 200, y0 - 1100),
                   b.math("MULTIPLY", v["gem_length"], 0.5, x0 + 200, y0 - 1260), 0.0, x0 + 400, y0 - 1100)
    p_e = b.vmath("SUBTRACT", b.vmath("MULTIPLY", k1, half, x0 + 600, y0 - 600),
                  b.vmath("MULTIPLY", k2, combine(b, v["gem_cx"], v["gem_cy"], 0.0, x0 + 400, y0 - 1400),
                          x0 + 600, y0 - 900), x0 + 800, y0 - 600)
    p_prev = b.at_index(p_e, b.math("FLOORED_MODULO", b.math("ADD", k, 7.0, x0 + 800, y0 - 900), 8.0,
                                    x0 + 1000, y0 - 900), "FLOAT_VECTOR", x0 + 1200, y0 - 900)
    p_next = b.at_index(p_e, b.math("FLOORED_MODULO", b.math("ADD", k, 1.0, x0 + 800, y0 - 1100), 8.0,
                                    x0 + 1000, y0 - 1100), "FLOAT_VECTOR", x0 + 1200, y0 - 1100)
    n1 = b.vmath("NORMALIZE", b.vmath("CROSS_PRODUCT", b.vmath("SUBTRACT", p_e, p_prev, x0 + 1400, y0 - 900), up,
                                      x0 + 1600, y0 - 900), None, x0 + 1800, y0 - 900)
    n2 = b.vmath("NORMALIZE", b.vmath("CROSS_PRODUCT", b.vmath("SUBTRACT", p_next, p_e, x0 + 1400, y0 - 1100), up,
                                      x0 + 1600, y0 - 1100), None, x0 + 1800, y0 - 1100)
    b_e = b.vmath("SCALE", b.vmath("ADD", n1, n2, x0 + 2000, y0 - 900),
                  b.math("DIVIDE", 1.0, b.math("ADD", 1.0, b.vmath("DOT_PRODUCT", n1, n2, x0 + 2000, y0 - 1100),
                                                x0 + 2200, y0 - 1100), x0 + 2400, y0 - 1100), x0 + 2600, y0 - 900)
    path = store(b, circle.outputs["Curve"], "_sc_k", "FLOAT", "POINT", k, x0 + 2800, y0)
    path = store(b, path, "_sc_p", "FLOAT_VECTOR", "POINT", b.switch("VECTOR", is_em, p_r, p_e, x0 + 2800, y0 - 300),
                 x0 + 3000, y0)
    path = store(b, path, "_sc_b", "FLOAT_VECTOR", "POINT", b.switch("VECTOR", is_em, b_r, b_e, x0 + 3000, y0 - 300),
                 x0 + 3200, y0)
    path = store(b, path, "_sc_s", "FLOAT", "POINT", b.switch("FLOAT", is_em, 0.0, 1.0, x0 + 3200, y0 - 300),
                 x0 + 3400, y0)

    # --- клетка: Curve to Mesh — топология, положение P + B d на высоте z ---
    b.section("Cast Cage")
    x0, y0 = 3600, -500
    # огранка по контуру: путь — управляющая петля (N точек), P — точка петли, B — вынос с компенсацией
    # сглаживания (My_Gem_Cast); _sc_u — точка на единичной окружности: у ребра вдоль пути среднее короче 1
    base, has_o = outline_mesh(b, src, v["gem_size"], v["gem_length"], -400, -3600)
    fr = outline_loop(b, base, 600, -3600)
    b.section("Outline Path")
    xo, yo = 3200, -3600
    npts = b.node("GeometryNodeAttributeDomainSize", xo, yo - 300, component="CURVE")
    b.link(fr["loop"], npts.inputs["Geometry"])
    ko = b.node("GeometryNodeInputIndex", xo, yo - 500).outputs[0]
    ang_o = b.math("DIVIDE", b.math("MULTIPLY", ko, 2.0 * pi, xo + 200, yo - 500), npts.outputs["Point Count"],
                   xo + 400, yo - 500)
    path_o = store(b, fr["loop"], "_sc_p", "FLOAT_VECTOR", "POINT", fr["pos"], xo + 200, yo)
    path_o = store(b, path_o, "_sc_b", "FLOAT_VECTOR", "POINT", fr["offset"], xo + 400, yo)
    path_o = store(b, path_o, "_sc_s", "FLOAT", "POINT", fr["sharp"], xo + 600, yo)
    path_o = store(b, path_o, "_sc_u", "FLOAT_VECTOR", "POINT",
                   combine(b, b.math("COSINE", ang_o, None, xo + 600, yo - 500),
                           b.math("SINE", ang_o, None, xo + 600, yo - 650), 0.0, xo + 800, yo - 500), xo + 800, yo)
    b.section("Cast Cage")
    path = b.switch("GEOMETRY", has_o, path, path_o, x0 - 200, y0)
    n_path = b.node("GeometryNodeAttributeDomainSize", x0 - 400, y0 + 400, component="CURVE")
    b.link(path, n_path.inputs["Geometry"])
    kq = b.node("GeometryNodeInputIndex", x0 - 400, y0 + 600).outputs[0]
    # номер точки пути k — единичный вектор под углом 2 pi k / N (у замыкающего пролёта не скачет)
    aq = b.math("DIVIDE", b.math("MULTIPLY", kq, 2.0 * pi, x0 - 300, y0 + 600), n_path.outputs["Point Count"],
                x0 - 200, y0 + 600)
    path = store(b, path, "_cqv", "FLOAT_VECTOR", "POINT",
                 combine(b, b.math("COSINE", aq, None, x0 - 100, y0 + 600), b.math("SINE", aq, None, x0 - 100, y0 + 750),
                         0.0, x0, y0 + 600), x0 - 200, y0 + 200)
    # Edge Round > 0: вертикальное ребро на острой вершине пути скругляют опорные точки на его сторонах; P, B и
    # номер точки пути у опорной — в той же доле стороны (на вынесенном контуре она на той же доле его стороны).
    # Скругляется вершина с поворотом меньше 60° (срезы изумруда, ашера, октагона): крапан в ней не стоит.
    # Прямые и острые углы (принцесса, треугольник, остриё груши) остаются острыми (_sc_c — crease на кольце):
    # скругление отодвигает угол каста от крапана, стоящего в нём (принцесса 7 мм с корзинкой — уже при 0.08).
    # Глухой каст (без крапанов) — все острые вершины.
    b.section("Edge Round")
    xe, ye = x0 - 2800, y0 + 5200
    pp = attr(b, "_sc_p", "FLOAT_VECTOR", xe, ye)
    legs = []
    for i, step in enumerate((-1, 1)):
        n = b.node("GeometryNodeOffsetPointInCurve", xe, ye - 200 - 160 * i)
        n.inputs["Offset"].default_value = step
        q = b.at_index(pp, n.outputs["Point Index"], "FLOAT_VECTOR", xe + 200, ye - 200 - 160 * i)
        legs.append(b.vmath("NORMALIZE", b.vmath("SUBTRACT", *((pp, q) if step < 0 else (q, pp)), xe + 400,
                                                 ye - 200 - 160 * i), None, xe + 600, ye - 200 - 160 * i))
    gentle = b.cmp("GREATER_THAN", b.vmath("DOT_PRODUCT", legs[0], legs[1], xe + 800, ye - 200), CORNER_SOFT,
                   xe + 1000, ye - 200)
    is_sharp = b.cmp("GREATER_THAN", attr(b, "_sc_s", "FLOAT", xe, ye - 600), 0.5, xe + 200, ye - 600)
    rounded = b.boolean("AND", is_sharp, b.boolean("OR", is_bezel, gentle, xe + 1200, ye - 200), xe + 1400, ye - 400)
    path = store(b, path, "_sc_r", "FLOAT", "POINT", rounded, xe + 1600, ye)
    path = store(b, path, "_sc_c", "FLOAT", "POINT",
                 b.boolean("AND", is_sharp, b.boolean("NOT", rounded, None, xe + 1600, ye - 400), xe + 1800, ye - 400),
                 xe + 2000, ye)
    path = b.switch("GEOMETRY", er_on, path,
                    hold_corners(b, path, hh, attr(b, "_sc_p", "FLOAT_VECTOR", xe + 2200, ye - 300),
                                 [("_sc_p", "FLOAT_VECTOR"), ("_sc_b", "FLOAT_VECTOR"), ("_cqv", "FLOAT_VECTOR")],
                                 xe + 2400, ye, sharp=attr(b, "_sc_r", "FLOAT", xe + 2200, ye - 500), clear=("_sc_c",)),
                    x0 - 100, y0 + 200)
    # точка пути после опорных — своя точка единичной окружности: у ребра кольца сечения среднее длиной 1
    n_w = b.node("GeometryNodeAttributeDomainSize", x0 - 100, y0 + 1000, component="CURVE")
    b.link(path, n_w.inputs["Geometry"])
    aw = b.math("DIVIDE", b.math("MULTIPLY", b.node("GeometryNodeInputIndex", x0 - 100, y0 + 800).outputs[0], 2.0 * pi,
                                 x0 + 100, y0 + 800), n_w.outputs["Point Count"], x0 + 300, y0 + 800)
    path = store(b, path, "_sc_w", "FLOAT_VECTOR", "POINT",
                 combine(b, b.math("COSINE", aw, None, x0 + 500, y0 + 800), b.math("SINE", aw, None, x0 + 500, y0 + 950),
                         0.0, x0 + 700, y0 + 800), x0 + 100, y0 + 200)
    b.section("Cast Cage")
    c2m = b.node("GeometryNodeCurveToMesh", x0, y0)
    b.link(path, c2m.inputs["Curve"])
    b.link(profile, c2m.inputs["Profile Curve"])
    dz = sep(b, attr(b, "_sc_dz", "FLOAT_VECTOR", x0, y0 - 300), x0 + 200, y0 - 300)
    place = b.node("GeometryNodeSetPosition", x0 + 600, y0)
    b.link(c2m.outputs["Mesh"], place.inputs["Geometry"])
    b.link(vma(b, attr(b, "_sc_b", "FLOAT_VECTOR", x0 + 200, y0 - 500), combine(b, dz["X"], dz["X"], dz["X"],
                                                                              x0 + 400, y0 - 500),
               b.vmath("ADD", attr(b, "_sc_p", "FLOAT_VECTOR", x0 + 200, y0 - 700),
                       combine(b, 0.0, 0.0, dz["Y"], x0 + 400, y0 - 700), x0 + 600, y0 - 700), x0 + 600, y0 - 500),
           place.inputs["Position"])
    # ребро вдоль пути: концы на соседних точках пути — дробный средний _sc_k; Emerald — все рёбра
    along = b.cmp("GREATER_THAN", b.math("FRACT", attr(b, "_sc_k", "FLOAT", x0 + 600, y0 - 900), None,
                                         x0 + 800, y0 - 900), 0.25, x0 + 1000, y0 - 900)
    # контур: вдоль пути — по _sc_u, острая точка пути — по corner (вместо «все точки острые» у Emerald)
    along = b.switch("BOOLEAN", has_o, along,
                     b.cmp("LESS_THAN", b.vmath("LENGTH", attr(b, "_sc_u", "FLOAT_VECTOR", x0 + 600, y0 - 1200), None,
                                                x0 + 800, y0 - 1200), 0.9999, x0 + 1000, y0 - 1200), x0 + 1100, y0 - 900)
    sharp_pt = b.switch("BOOLEAN", has_o, is_em, b.cmp("GREATER_THAN", attr(b, "_sc_s", "FLOAT", x0 + 600, y0 - 1350),
                                                        0.5, x0 + 800, y0 - 1350), x0 + 1000, y0 - 1350)
    crease = b.boolean("OR", along, sharp_pt, x0 + 1200, y0 - 900)
    # круглый рант: вдоль пути без crease (сечение скругляется); острые точки пути — crease на кольцах
    # сечения (углы пути острые)
    crease = b.switch("BOOLEAN", rail_round, crease,
                      b.boolean("AND", b.boolean("NOT", along, None, x0 + 1000, y0 - 1050), sharp_pt, x0 + 1200,
                                y0 - 1050), x0 + 1400, y0 - 900)
    # Edge Round > 0: рёбра держат опорные точки сечения и пути; crease — только на кольце сечения в острой
    # вершине пути, которая не скругляется (_sc_c), и вдоль пути на острых рёбрах сечения (_sc_h)
    ring = b.cmp("GREATER_THAN", b.vmath("LENGTH", attr(b, "_sc_w", "FLOAT_VECTOR", x0 + 600, y0 - 1500), None,
                                         x0 + 800, y0 - 1500), 0.9999, x0 + 1000, y0 - 1500)
    hard = b.boolean("AND", ring, b.cmp("GREATER_THAN", attr(b, "_sc_c", "FLOAT", x0 + 600, y0 - 1650), 0.5,
                                        x0 + 1000, y0 - 1650), x0 + 1200, y0 - 1500)
    hard_s = b.boolean("AND", b.boolean("NOT", ring, None, x0 + 1200, y0 - 1800),
                       b.cmp("GREATER_THAN", attr(b, "_sc_h", "FLOAT", x0 + 600, y0 - 1800), 0.5, x0 + 1000, y0 - 1800),
                       x0 + 1400, y0 - 1800)
    crease = b.switch("BOOLEAN", er_on, crease, b.boolean("OR", hard, hard_s, x0 + 1600, y0 - 1500), x0 + 1800, y0 - 900)
    cage = store(b, place.outputs["Geometry"], "crease_edge", "FLOAT", "EDGE", crease, x0 + 1200, y0)
    rm = b.node("GeometryNodeRemoveAttribute", x0 + 1400, y0)
    rm.inputs["Pattern Mode"].default_value = "Wildcard"
    rm.inputs["Name"].default_value = "_sc_*"
    b.link(cage, rm.inputs["Geometry"])
    cage = rm.outputs["Geometry"]

    # --- Subdivision и прорезь: параллелепипед HeightBool на середине высоты + OffsetBool ---
    b.section("Subdivision, Slot")
    x0, y0 = 5400, -500
    cast_sd = subd(b, cage, v["set_subdiv"], x0, y0)
    cbb = b.node("GeometryNodeBoundBox", x0, y0 - 400)
    b.link(cage, cbb.inputs["Geometry"])
    size = sep(b, b.vmath("SCALE", b.vmath("SUBTRACT", cbb.outputs["Max"], cbb.outputs["Min"], x0 + 200, y0 - 400),
                          gc.SLOT_SIZE, x0 + 400, y0 - 400), x0 + 600, y0 - 400)
    mid = sep(b, b.vmath("SCALE", b.vmath("ADD", cbb.outputs["Max"], cbb.outputs["Min"], x0 + 200, y0 - 600), 0.5,
                         x0 + 400, y0 - 600), x0 + 600, y0 - 600)
    cube = b.node("GeometryNodeMeshCube", x0 + 800, y0 - 400)
    b.link(combine(b, size["X"], size["Y"], gi("Cast", "HeightBool"), x0 + 800, y0 - 600), cube.inputs["Size"])
    slot_z = b.math("ADD", madd(b, h_cast, -0.5, z_top, x0 + 600, y0 - 800), gi("Cast", "OffsetBool"),
                    x0 + 800, y0 - 800)
    slot = transform(b, cube.outputs["Mesh"], x0 + 1000, y0 - 400,
                     translation=combine(b, mid["X"], mid["Y"], slot_z, x0 + 1000, y0 - 700))
    cast = b.switch("GEOMETRY", gi("Cast", "CastBool"), cast_sd, boolean(b, "DIFFERENCE", cast_sd, [slot],
                                                                         x0 + 1200, y0 - 200), x0 + 1400, y0)
    has_sd = icmp(b, "GREATER_THAN", v["set_subdiv"], 0, x0 + 1400, y0 + 300)
    cast = b.switch("GEOMETRY", has_sd, cage, cast, x0 + 1600, y0)

    # --- глухой каст: своя посадка (без прорези), только при Subdivision > 0 ---
    stone = stone_mesh(b, src, v["gem_size"], v["gem_length"], 5400, -2400)
    seat, _hull, _on = seat_operands(b, stone, v["gem_size"], v["gem_length"], v["gem_culet"],
                                     sep(b, cbb.outputs["Max"], 6400, -2200)["Z"], gi("Bezel", "Bezel Cutter"),
                                     v["set_on"], v["found"], 6600, -2400)
    b.section("Bezel Seat")
    x0, y0 = 8000, -1200
    bezel = b.switch("GEOMETRY", has_sd, cage, boolean(b, "DIFFERENCE", cast_sd, seat, x0, y0 - 200), x0 + 200, y0)
    cast = b.switch("GEOMETRY", is_bezel, cast, bezel, x0 + 400, y0)
    # корзинка: без прорези и своей посадки (её режет My_Setting_Bool)
    cast = b.switch("GEOMETRY", is_basket, cast, b.switch("GEOMETRY", has_sd, cage, cast_sd, x0 + 200, y0 + 200),
                    x0 + 500, y0)
    # корона: стенка без прорези, верх опускается между крапанами (после SubD)
    crown = build_crown(b, cast_sd, base, fr, has_o, is_em, v, circle.outputs["Curve"], p_e, z_top, h_cast, tan_t,
                        gi("Crown", "Crown Depth"), n_path.outputs["Point Count"], 8000, -6000)
    b.section("Bezel Seat")
    cast = b.switch("GEOMETRY", is_crown, cast, b.switch("GEOMETRY", has_sd, cage, crown, x0 + 400, y0 + 400),
                    x0 + 550, y0)
    seated = b.boolean("AND", is_bezel, has_sd, x0, y0 - 600)
    # ShowCutter — операнды посадки инстансом: My_Setting_Bool пропускает инстансы, в металл не попадёт
    shown = b.node("GeometryNodeGeometryToInstance", x0 + 200, y0 - 400)
    b.link(join(b, seat, x0, y0 - 400), shown.inputs["Geometry"])
    cast = join(b, [cast, gate(b, b.boolean("AND", seated, gi("Bezel", "ShowCutter"), x0 + 200, y0 - 600),
                                shown.outputs["Instances"], x0 + 400, y0 - 400)], x0 + 600, y0)
    # камень посажен здесь — My_Setting_Bool посадку не режет второй раз (совпадающие катеры дают
    # стенки нулевой толщины). Store на домене INSTANCE ссылку инстанса на объект не ломает.
    mark = b.node("GeometryNodeStoreNamedAttribute", x0 + 600, y0 - 800, data_type="BOOLEAN", domain="INSTANCE")
    mark.inputs["Name"].default_value = "set_seated"
    b.link(b.g("Geometry"), mark.inputs["Geometry"])
    b.link(b.cmp("GREATER_THAN", attr(b, "gem_r", "FLOAT", x0 + 200, y0 - 1000), 0.0, x0 + 400, y0 - 1000),
           mark.inputs["Selection"])
    b.link(seated, mark.inputs["Value"])
    cq = b.node("GeometryNodeRemoveAttribute", x0 + 800, y0)
    cq.inputs["Pattern Mode"].default_value = "Wildcard"
    cq.inputs["Name"].default_value = "_cq*"
    b.link(cast, cq.inputs["Geometry"])
    cast = cq.outputs["Geometry"]
    out = finish_metal(b, gi, "Cast", v, use_obj, cast, x0 + 1000, stream=mark.outputs["Geometry"])
    finish(b, ng, out, x0 + 2600)
    restore_menu(ng, "Type", CAST_TYPES, kept, had_type)
    restore_menu(ng, "Rail Shape", RAIL_SHAPES, kept_rail, had_rail)
    return ng


def build_crown(b, cast_sd, base, fr, has_o, is_em, v, circle8, p_e, z_top, h_cast, tan_t, depth, n_path, ox, oy):
    """Каст-корона: стенка Wall без прорези; верх на Z Offset у каждого места крапана и на Z Offset - Crown Depth
    посередине между соседними местами (по длине контура). Делается после SubD: у вершины стенки — доля пути
    x между местами по ближайшей точке плотной петли рундиста; z сжимается к низу стенки так, что верх
    опускается на Depth * f(x), и вершина сдвигается вбок на (z' - z) tan T (наружная линия остаётся по Tilt).
    f: tri = 1 - |1 - 2x| (0 у места, 1 посередине), s = tri ** CROWN_POW, дно V скруглено радиусом CROWN_SOFT мм
    по длине контура: f = 1 - h(t) / h(L/2), t = (1 - s) L / 2, h(t) = sqrt(t^2 + r^2) - r.
    Место вершины стенки на петле — по номеру точки пути каста (интерполирован SubD), плотная петля — с
    постоянным числом точек на пролёт пути. Места — те же, что у My_Stone_Prongs (Count и ° Z он пишет на инстанс камня: set_count, set_rotz); без
    крапанов в стеке — верх ровный. Петля: контур — предел петли, Round — окружность, Emerald — восьмиугольник.
    Subdivision 0 — клетка стенки без прорези и без выреза."""
    b.section("Crown")
    cnt = [0]

    def at():
        cnt[0] += 1
        return ox + 180 * (cnt[0] // 14), oy - 150 * (cnt[0] % 14)

    def m(op, a, c=None):
        return b.math(op, a, c, *at())

    # места крапанов — как в My_Stone_Prongs: Round — Count точек через 360 / Count от ° Z (set_count, set_rotz
    # на инстансе камня), Emerald — середины срезов углов, контур — его вершины без рёбер; крапанов нет — ровно
    circ = b.node("GeometryNodeMeshCircle", *at(), fill_type="NONE")
    b.link(v["set_count"], circ.inputs["Vertices"])
    b.link(v["gem_r"], circ.inputs["Radius"])
    r_pts = transform(b, circ.outputs["Mesh"], *at(), rotation=axis_angle(b, (0.0, 0.0, 1.0), v["set_rotz"], *at()))
    quad = index_switch(b, "VECTOR", b.node("GeometryNodeInputIndex", *at()).outputs[0],
                        [(1.0, 1.0, 0.0), (-1.0, 1.0, 0.0), (-1.0, -1.0, 0.0), (1.0, -1.0, 0.0)], *at())
    e_pts = b.node("GeometryNodePoints", *at())
    e_pts.inputs["Count"].default_value = 4
    b.link(b.vmath("MULTIPLY", quad, combine(b, madd(b, v["gem_cx"], -0.5, m("MULTIPLY", v["gem_size"], 0.5), *at()),
                                             madd(b, v["gem_cy"], -0.5, m("MULTIPLY", v["gem_length"], 0.5), *at()),
                                             0.0, *at()), *at()), e_pts.inputs["Position"])
    o_pts = b.node("GeometryNodeMeshToPoints", *at(), mode="VERTICES")
    b.link(base, o_pts.inputs["Mesh"])
    b.link(icmp(b, "EQUAL", b.node("GeometryNodeInputMeshVertexNeighbors", *at()).outputs["Vertex Count"], 0, *at()),
           o_pts.inputs["Selection"])
    r_cloud = b.node("GeometryNodeMeshToPoints", *at(), mode="VERTICES")
    b.link(r_pts, r_cloud.inputs["Mesh"])
    sites = b.switch("GEOMETRY", has_o, b.switch("GEOMETRY", is_em, r_cloud.outputs["Points"], e_pts.outputs["Points"],
                                                 *at()), o_pts.outputs["Points"], *at())
    has_sites = icmp(b, "GREATER_THAN", v["set_count"], 0, *at())

    # плотная петля рундиста по ходу против часовой
    # точек на пролёт пути: контур — LIMIT_RES (предел Безье), Round — 45 (окружность 360 от 0°, путь через 45°),
    # Emerald — 50 (восьмиугольник, каждая сторона на 50 частей)
    rc_ = b.node("GeometryNodeCurvePrimitiveCircle", *at(), mode="RADIUS")
    rc_.inputs["Resolution"].default_value = 360
    b.link(v["gem_r"], rc_.inputs["Radius"])
    oc = b.node("GeometryNodeSetPosition", *at())
    b.link(circle8, oc.inputs["Geometry"])
    b.link(p_e, oc.inputs["Position"])
    res = b.node("GeometryNodeSubdivideCurve", *at())
    b.link(oc.outputs["Geometry"], res.inputs["Curve"])
    res.inputs["Cuts"].default_value = 49
    loop_c = b.switch("GEOMETRY", is_em, rc_.outputs["Curve"], res.outputs["Curve"], *at())
    per_span = b.switch("FLOAT", has_o, b.switch("FLOAT", is_em, 45.0, 50.0, *at()), float(LIMIT_RES), *at())
    lp = b.node("GeometryNodeCurveToPoints", *at(), mode="EVALUATED")
    b.link(loop_c, lp.inputs["Curve"])
    dense = b.switch("GEOMETRY", has_o, lp.outputs["Points"], fr["limit"].outputs["Points"], *at())
    nd = b.node("GeometryNodeAttributeDomainSize", *at(), component="POINTCLOUD")
    b.link(dense, nd.inputs["Geometry"])
    n_d = nd.outputs["Point Count"]
    pos = b.node("GeometryNodeInputPosition", *at()).outputs[0]
    idx = b.node("GeometryNodeInputIndex", *at()).outputs[0]
    # место -> номер ближайшей точки петли
    near_d = b.node("GeometryNodeSampleNearest", *at(), domain="POINT")
    b.link(dense, near_d.inputs["Geometry"])
    b.link(pos, near_d.inputs["Sample Position"])
    sites = store(b, sites, "_cr_i", "FLOAT", "POINT", near_d.outputs["Index"], *at())
    near_s = b.node("GeometryNodeSampleNearest", *at(), domain="POINT")
    b.link(sites, near_s.inputs["Geometry"])
    b.link(pos, near_s.inputs["Sample Position"])
    s_i = b.node("GeometryNodeSampleIndex", *at(), data_type="FLOAT", domain="POINT")
    b.link(sites, s_i.inputs["Geometry"])
    b.link(attr(b, "_cr_i", "FLOAT", *at()), b.enabled(s_i, "Value"))
    b.link(near_s.outputs["Index"], s_i.inputs["Index"])
    is_site = b.cmp("LESS_THAN", m("ABSOLUTE", m("SUBTRACT", b.enabled_out(s_i, "Value"), idx)), 0.5, *at())
    first = stat(b, sites, attr(b, "_cr_i", "FLOAT", *at()), None, "POINT", "Min", *at())
    # нормаль петли наружу (против часовой: (t_y, -t_x)) — до сортировки
    nxt = m("FLOORED_MODULO", m("ADD", idx, 1.0), n_d)
    prv = m("FLOORED_MODULO", m("SUBTRACT", idx, 1.0), n_d)
    tang = b.vmath("SUBTRACT", b.at_index(pos, nxt, "FLOAT_VECTOR", *at()), b.at_index(pos, prv, "FLOAT_VECTOR", *at()),
                   *at())
    nrm = b.vmath("NORMALIZE", b.vmath("CROSS_PRODUCT", tang, (0.0, 0.0, 1.0), *at()), None, *at())
    dense = store(b, store(b, dense, "_cr_m", "FLOAT", "POINT", is_site, *at()), "_cr_n", "FLOAT_VECTOR", "POINT",
                  nrm, *at())
    dense = store(b, dense, "_cr_o", "FLOAT", "POINT", idx, *at())
    # с первого места по ходу; группы — участки от места до места
    srt = b.node("GeometryNodeSortElements", *at(), domain="POINT")
    b.link(dense, srt.inputs["Geometry"])
    b.link(m("FLOORED_MODULO", m("SUBTRACT", idx, first), n_d), srt.inputs["Sort Weight"])
    dense = srt.outputs["Geometry"]
    e = b.vmath("DISTANCE", pos, b.at_index(pos, m("FLOORED_MODULO", m("ADD", idx, 1.0), n_d), "FLOAT_VECTOR", *at()),
                *at())
    grp = b.node("GeometryNodeAccumulateField", *at(), data_type="FLOAT", domain="POINT")
    b.link(attr(b, "_cr_m", "FLOAT", *at()), grp.inputs["Value"])
    acc = b.node("GeometryNodeAccumulateField", *at(), data_type="FLOAT", domain="POINT")
    b.link(e, acc.inputs["Value"])
    b.link(grp.outputs["Leading"], acc.inputs["Group ID"])
    tot = acc.outputs["Total"]
    x = m("DIVIDE", acc.outputs["Trailing"], tot)
    tri = m("SUBTRACT", 1.0, m("ABSOLUTE", m("SUBTRACT", 1.0, m("MULTIPLY", x, 2.0))))
    sv = m("POWER", tri, CROWN_POW)
    half = m("MULTIPLY", tot, 0.5)

    def soft(t):
        return m("SUBTRACT", m("SQRT", m("ADD", m("MULTIPLY", t, t), CROWN_SOFT * CROWN_SOFT)), CROWN_SOFT)
    shape = m("SUBTRACT", 1.0, m("DIVIDE", soft(m("MULTIPLY", m("SUBTRACT", 1.0, sv), half)), soft(half)))
    dz = b.switch("FLOAT", has_sites, 0.0, m("MULTIPLY", depth, shape), *at())
    dense = store(b, dense, "_cr_dz", "FLOAT", "POINT", dz, *at())
    back = b.node("GeometryNodeSortElements", *at(), domain="POINT")      # обратно в порядок петли
    b.link(dense, back.inputs["Geometry"])
    b.link(attr(b, "_cr_o", "FLOAT", *at()), back.inputs["Sort Weight"])
    dense = back.outputs["Geometry"]

    # стенка: место вершины на петле — по номеру точки пути (интерполирован SubD). Ближайшая точка в плане не
    # годится: внутри митры острого угла она на стороне, а не в углу
    # вектор номера пути интерполирован внутри пролёта k..k+1 линейно: угол phi' от начала пролёта даёт долю
    # t = tan phi' / (sin D + tan phi' (1 - cos D)), D = 2 pi / N
    wv = sep(b, attr(b, "_cqv", "FLOAT_VECTOR", *at()), *at())
    phi = m("FLOORED_MODULO", m("ARCTAN2", wv["Y"], wv["X"]), 2.0 * pi)
    dd = m("DIVIDE", 2.0 * pi, n_path)
    k0 = m("FLOOR", m("DIVIDE", phi, dd))
    tp = m("TANGENT", m("SUBTRACT", phi, m("MULTIPLY", k0, dd)))
    tq = m("DIVIDE", tp, m("ADD", m("SINE", dd), m("MULTIPLY", tp, m("SUBTRACT", 1.0, m("COSINE", dd)))))
    q = m("ADD", k0, tq)
    pick = m("FLOORED_MODULO", m("ROUND", m("MULTIPLY", q, per_span)), n_d)
    pv = sep(b, pos, *at())

    def from_dense(name, dtype):
        n = b.node("GeometryNodeSampleIndex", *at(), data_type=dtype, domain="POINT")
        b.link(dense, n.inputs["Geometry"])
        b.link(attr(b, name, dtype, *at()), b.enabled(n, "Value"))
        b.link(pick, n.inputs["Index"])
        return b.enabled_out(n, "Value")
    z_bot = m("SUBTRACT", z_top, h_cast)
    dz_w = m("MULTIPLY", from_dense("_cr_dz", "FLOAT"), m("DIVIDE", m("SUBTRACT", pv["Z"], z_bot), h_cast))
    shift = m("MULTIPLY", m("MULTIPLY", dz_w, -1.0), tan_t)          # (z' - z) tan T
    n_w = from_dense("_cr_n", "FLOAT_VECTOR")
    # стенка после SubD 2 — 32 вершины по кругу: места и середины между ними не на вершинах, грань не
    # достаёт до высоты. Линейно x4 вдоль и поперёк (поверхность та же), потом сдвиг вершин
    fine = b.node("GeometryNodeSubdivideMesh", *at())
    b.link(cast_sd, fine.inputs["Mesh"])
    fine.inputs["Level"].default_value = CROWN_REFINE
    sp = b.node("GeometryNodeSetPosition", *at())
    b.link(fine.outputs["Mesh"], sp.inputs["Geometry"])
    b.link(b.vmath("ADD", vma(b, n_w, combine(b, shift, shift, 0.0, *at()), pos, *at()),
                   combine(b, 0.0, 0.0, m("MULTIPLY", dz_w, -1.0), *at()), *at()), sp.inputs["Position"])
    # Crown Depth 0 — та же стенка, что Wall без прорези (без измельчения)
    return b.switch("GEOMETRY", b.cmp("GREATER_THAN", depth, 0.0, *at()), cast_sd, sp.outputs["Geometry"], *at())


# --- My_Setting_Bool ---------------------------------------------------------------------------

def build_bool():
    _pr, rc, gc = mods()
    ng, b, gi = begin(BOOL)
    v = read_stone(b, b.g("Geometry"), -200, 2400, ATTRS + [("set_seated", "BOOLEAN")])
    w, ln, set_on, found = v["gem_size"], v["gem_length"], v["set_on"], v["found"]
    # камень уже посажен глухим кастом — своя посадка и оболочка камня не нужны
    enable = b.boolean("AND", found, b.boolean("NOT", v["set_seated"], None, 1000, 2600), 1200, 2600)

    # --- металл (меш) и всё остальное (инстансы — камни — проходят нетронутыми) ---
    b.section("Metal")
    parts = b.node("GeometryNodeSeparateComponents", 0, 0)
    b.link(b.g("Geometry"), parts.inputs["Geometry"])
    metal = parts.outputs["Mesh"]
    rest = join(b, [s for s in parts.outputs if s.name != "Mesh"], 200, -300)
    # острова — отдельные операнды Manifold (перекрытия внутри одного операнда он не склеивает)
    split = b.node("GeometryNodeSplitToInstances", 400, 0, domain="FACE")
    b.link(metal, split.inputs["Geometry"])
    b.link(b.node("GeometryNodeInputMeshIsland", 200, -150).outputs["Island Index"], split.inputs["Group ID"])
    islands = split.outputs["Instances"]
    mbb = b.node("GeometryNodeBoundBox", 200, 200)
    b.link(metal, mbb.inputs["Geometry"])
    metal_top = sep(b, mbb.outputs["Max"], 400, 200)["Z"]

    # --- камень из потока и посадка: Cutter * (W, L, W) или авто-катер; Set — оболочка камня и Cutter
    # ниже рундиста ---
    stone = stone_mesh(b, b.g("Geometry"), w, ln, 0, -1200)
    seat, set_hull, hull_on = seat_operands(b, stone, w, ln, v["gem_culet"], metal_top, gi("Bool", "Cutter"),
                                            set_on, enable, 1200, -1200)

    # --- общие резаки: BoolObject и объекты BoolCollection — отдельные операнды ---
    b.section("Booleans")
    x0, y0 = 2800, 0
    bool_obj = object_info(b, gi("Bool", "BoolObject"), "RELATIVE", x0, y0 - 900).outputs["Geometry"]
    coll = b.node("GeometryNodeCollectionInfo", x0, y0 - 1100, transform_space="RELATIVE")
    b.link(gi("Bool", "BoolCollection"), coll.inputs["Collection"])
    coll.inputs["Separate Children"].default_value = True
    coll.inputs["Reset Children"].default_value = False
    bools = join(b, [bool_obj, coll.outputs["Instances"]], x0 + 200, y0 - 1000)
    has_bool = has_instances(b, bools, x0 + 200, y0 - 1200)
    # BoolCutter: union островов, посадка, общие резаки
    united = boolean(b, "UNION", None, [islands], x0, y0)
    seated = boolean(b, "DIFFERENCE", united, seat, x0 + 200, y0)
    seated = b.switch("GEOMETRY", has_bool, seated, boolean(b, "DIFFERENCE", seated, [bools], x0 + 400, y0 - 200),
                      x0 + 600, y0)
    # без BoolCutter: каждый остров минус (общие резаки + оболочка камня при Set)
    fe_in = b.node("GeometryNodeForeachGeometryElementInput", x0, y0 - 400)
    fe_out = b.node("GeometryNodeForeachGeometryElementOutput", x0 + 800, y0 - 400)
    fe_in.pair_with_output(fe_out)
    fe_out.domain = "INSTANCE"
    b.link(islands, fe_in.inputs["Geometry"])
    piece = b.node("GeometryNodeRealizeInstances", x0 + 200, y0 - 400)
    b.link(fe_in.outputs["Element"], piece.inputs["Geometry"])
    b.link(boolean(b, "DIFFERENCE", piece.outputs["Geometry"], [bools, set_hull], x0 + 400, y0 - 400),
           fe_out.inputs["Generation_0"])
    cuts = b.boolean("OR", has_bool, hull_on, x0 + 600, y0 - 700)
    apart = b.switch("GEOMETRY", cuts, metal, fe_out.outputs["Generation_0"], x0 + 1000, y0 - 400)
    bool_cutter = gi("Bool", "BoolCutter")
    result = b.switch("GEOMETRY", bool_cutter, apart, seated, x0 + 1200, y0)
    # катер — использованные операнды посадки
    used = b.switch("GEOMETRY", bool_cutter, set_hull, join(b, seat, x0 + 1000, y0 - 900), x0 + 1200, y0 - 900)
    result = join(b, [result, gate(b, gi("Bool", "ShowCutter"), used, x0 + 1400, y0 - 900)], x0 + 1600, y0)

    # --- выход: сглаживание, Realize All, остальное (камни) — последним ---
    b.section("Output")
    x0 = 4600
    result = smooth(b, result, gi(None, "Smooth"), x0, 0)
    realize = b.node("GeometryNodeRealizeInstances", x0 + 600, 0)
    b.link(result, realize.inputs["Geometry"])
    b.link(gi(None, "Realize All"), realize.inputs["Realize All"])
    realize.inputs["Depth"].default_value = 2
    out = join(b, [realize.outputs["Geometry"], rest], x0 + 800, 0)
    # клетка (Subdivision 0) — всё как пришло
    cage = b.boolean("AND", found, icmp(b, "EQUAL", v["set_subdiv"], 0, x0 + 800, 300), x0 + 1000, 300)
    out = b.switch("GEOMETRY", cage, out, b.g("Geometry"), x0 + 1200, 0)
    return finish(b, ng, out, x0 + 1400)


def build_all():
    return [build_stone(), build_prongs(), build_cast(), build_bool()]


# --- объект со стеком --------------------------------------------------------------------------

def setup(cut, width=None, length=None, diam=None, cutter=None, name=None, cast_type=None):
    """Объект '<Cut> Setting' с четырьмя модификаторами по порядку. У нового модификатора My_Stone —
    Cut и Diam (не задан — камень-единица unit_stone); width, length, diam, cutter, cast_type (Wall / Bezel /
    Basket) — когда заданы. Остальные значения существующих модификаторов не меняются."""
    _pr, rc, gc = mods()
    cut = cut.title()
    groups = dict(zip(ORDER, build_all()))
    name = name or "%s Setting" % cut
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, bpy.data.meshes.new(name))
        bpy.context.scene.collection.objects.link(ob)
    new = set()
    for gname in ORDER:
        if not any(m.type == "NODES" and m.node_group == groups[gname] for m in ob.modifiers):
            md = ob.modifiers.new(gname, "NODES")
            md.node_group = groups[gname]
            new.add(gname)

    def put(gname, key, value):
        md = next(m for m in ob.modifiers if m.type == "NODES" and m.node_group == groups[gname])
        getattr(md.properties.inputs, rc.socket_keys(groups[gname])[key]).value = value

    if STONE in new:
        put(STONE, (None, "Cut"), cut)
        if diam is None:
            diam = gc.unit_stone(cut.upper())
        if cut == "Emerald" and width is not None and length is None:
            spec = gc.load_module("gem_cast_gems", gc.GEMS_PATH)._CUT_SPECS["EMERALD"]
            length = width * spec.base_length / spec.base_width
    for gname, key, value in ((STONE, (None, "Diam"), diam), (STONE, ("Stone", "Width"), width),
                              (STONE, ("Stone", "Length"), length), (BOOL, ("Bool", "Cutter"), cutter)):
        if value is not None:
            put(gname, key, bpy.data.objects[value] if isinstance(value, str) else value)
    if cast_type:
        put(CAST, (None, "Type"), cast_type.title())
    ob.update_tag()
    print("Stone setting '%s' set up" % ob.name)
    return ob


def main():
    build_all()


if __name__ == "__main__":
    main()
