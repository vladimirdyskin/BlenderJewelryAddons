"""
Словарь изделия поверх живых узлов: каст с камнем — короткая программа из именованных частей.

    stone("Main", cut="Emerald", width=8, length=10)
    prongs("Main", tip="Claw")
    cast("Main", type="Wall")
    seat("Main")

Глаголы не запекают меш: каждый добавляет модификатор группы из библиотеки (My_Stone, My_Stone_Prongs,
My_Stone_Cast, My_Setting_Bool — tools/gn_stone_setting_build.py) и ставит входы, дальше всё правится
ползунками. Повторный прогон программы меняет значения, второй модификатор / объект не появляется.
Порядок модификаторов всегда Stone, Prongs, Cast, Bool, в каком порядке ни вызывать.

**inputs — имена сокетов в snake_case (Set Cover -> set_cover, ø -> d, ° Z -> angle); углы в градусах,
длины в мм. Записывается только переданное, остальное на модификаторе не трогается.
Описание словаря для промпта — tools/jewel_api.md.

Запуск: import или exec(open(path).read(), ns). Группы берутся из файла, нет — дописываются из
библиотеки ассетов (поиск по Preferences -> File Paths -> Asset Libraries или use_library(path)).
"""

import importlib.util
import os
import re
from math import radians
from pathlib import Path

import bpy

STONE, PRONGS, CAST, BOOL = "My_Stone", "My_Stone_Prongs", "My_Stone_Cast", "My_Setting_Bool"
ORDER = (STONE, PRONGS, CAST, BOOL)
ALIASES = {"ø": "d", "° Z": "angle"}       # имена, которые snake_case не передаёт
try:
    REPO = Path(__file__).resolve().parent.parent
except NameError:                            # exec без __file__
    REPO = Path("~/GitHub/BlenderJewelryAddons").expanduser()

_LIB = {"path": None}
_MODS = {}


def use_library(path):
    """Явный .blend библиотеки с группами (иначе — поиск по библиотекам ассетов из настроек)."""
    path = Path(path).expanduser()
    if not path.is_file():
        raise ValueError("library not found: %s" % path)
    _LIB["path"] = path


def _library():
    if _LIB["path"]:
        return _LIB["path"]
    for lib in bpy.context.preferences.filepaths.asset_libraries:
        for blend in sorted(Path(bpy.path.abspath(lib.path)).rglob("*.blend")):
            with bpy.data.libraries.load(str(blend)) as (src, _dst):
                if STONE in src.node_groups:
                    _LIB["path"] = blend
                    return blend
    raise RuntimeError("node group %s not found in asset libraries, call use_library(path)" % STONE)


def _group(name):
    """Группа из файла; нет хотя бы одной из четырёх — все недостающие одним append (общие камни-единицы
    и контуры приходят один раз, без .001)."""
    missing = [g for g in ORDER if g not in bpy.data.node_groups]
    if missing:
        with bpy.data.libraries.load(str(_library()), link=False) as (src, dst):
            absent = [g for g in missing if g not in src.node_groups]
            if absent:
                raise RuntimeError("not in library: %s" % ", ".join(absent))
            dst.node_groups = list(missing)   # список заменяется на группы после load
        print("jewel: appended %s" % ", ".join(missing))
    return bpy.data.node_groups[name]


def _load(name, path):
    if name not in _MODS:
        spec = importlib.util.spec_from_file_location("jewel_" + name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _MODS[name] = mod
    return _MODS[name]


def _snake(name):
    if name in ALIASES:
        return ALIASES[name]
    name = re.sub(r"(?<=[a-z])(?=[A-Z])", "_", name).lower()
    return re.sub(r"[^a-z0-9]+", "_", name).strip("_")


def keywords(gname):
    """{keyword: элемент интерфейса} входов группы (без Geometry)."""
    return {_snake(it.name): it for it in _group(gname).interface.items_tree
            if it.item_type == "SOCKET" and it.in_out == "INPUT" and it.socket_type != "NodeSocketGeometry"}


def _object(ob):
    if isinstance(ob, str):
        found = bpy.data.objects.get(ob)
        if found is None:
            raise ValueError("object not found: %s" % ob)
        return found
    return ob


def _modifier(ob, gname):
    pattern = re.compile(re.escape(gname) + r"(\.\d+)?$")
    return next((m for m in ob.modifiers if m.type == "NODES" and m.node_group and pattern.match(m.node_group.name)),
                None)


def _sort(ob):
    """Модификаторы связки — по ORDER на занятых ими местах стека (чужие модификаторы не двигаются)."""
    ours = [g for g in ORDER if _modifier(ob, g)]
    slots = sorted(list(ob.modifiers).index(_modifier(ob, g)) for g in ours)
    for slot, g in zip(slots, ours):
        ob.modifiers.move(list(ob.modifiers).index(_modifier(ob, g)), slot)   # ссылки после move невалидны


_DATA = {"NodeSocketObject": "objects", "NodeSocketMaterial": "materials", "NodeSocketCollection": "collections"}


def _value(it, v):
    if isinstance(v, str) and it.socket_type in _DATA:
        found = getattr(bpy.data, _DATA[it.socket_type]).get(v)
        if found is None:
            raise ValueError("%s '%s' not found for %s" % (_DATA[it.socket_type][:-1], v, it.name))
        return found
    if getattr(it, "subtype", "") == "ANGLE":
        return radians(v)
    return v


def _apply(ob, gname, inputs):
    """Модификатор группы на ob (добавить, если нет) и переданные входы."""
    keys = keywords(gname)
    bad = [k for k in inputs if k not in keys]
    if bad:
        raise ValueError("%s: unknown %s; valid: %s" % (gname, ", ".join(bad), ", ".join(keys)))
    if _modifier(ob, gname) is None:
        ob.modifiers.new(gname, "NODES").node_group = _group(gname)
        _sort(ob)
    md = _modifier(ob, gname)
    for k, v in inputs.items():
        it = keys[k]
        try:
            getattr(md.properties.inputs, it.identifier).value = _value(it, v)
        except TypeError as e:     # пункт меню / тип значения
            raise ValueError("%s.%s: %s" % (gname, k, e)) from None
    ob.update_tag()
    return ob


def _std_length(cut, width):
    """Длина по стандартным пропорциям огранки (parametric_gems)."""
    spec = _load("gems", REPO / "parametric_gems" / "__init__.py")._CUT_SPECS.get(cut.upper())
    return width * spec.base_length / spec.base_width if spec else width


def stone(name, cut="Round", width=2.0, length=None, material=None, at=(0, 0, 0), **inputs):
    """Объект name (новый — с пустым мешем) с My_Stone. length=None — Round: = width, иначе пропорции огранки."""
    ob = bpy.data.objects.get(name)
    if ob is None:
        ob = bpy.data.objects.new(name, bpy.data.meshes.new(name))
        bpy.context.scene.collection.objects.link(ob)
    ob.location = at
    if length is None:
        length = width if cut == "Round" else _std_length(cut, width)
    named = {"cut": cut, "width": width, "length": length}
    if material is not None:
        named["stone_material"] = material
    return _apply(ob, STONE, {**named, **inputs})


def prongs(ob, tip="Round", d=None, **inputs):
    """My_Stone_Prongs: tip Round / Claw, d — диаметр крапана, мм."""
    named = {"tip": tip} if d is None else {"tip": tip, "d": d}
    return _apply(_object(ob), PRONGS, {**named, **inputs})


def cast(ob, type="Wall", **inputs):
    """My_Stone_Cast: type Wall / Bezel / Basket."""
    return _apply(_object(ob), CAST, {"type": type, **inputs})


def seat(ob, **inputs):
    """My_Setting_Bool — посадка камня и сборка металла в одну оболочку, последний в стеке."""
    return _apply(_object(ob), BOOL, inputs)


def points(ob, pts=None):
    """Места крапанов — вершины без рёбер меша объекта: [(x, y), ...] мм, "default" — места по умолчанию,
    None / [] — убрать (тогда места по умолчанию считают узлы)."""
    ob = _object(ob)
    pp = _load("prong_points", REPO / "jewel_tools" / "prong_points.py")
    if isinstance(pts, str):
        if pts != "default":
            raise ValueError("points: list of (x, y), 'default' or None")
        pts = pp.default_points(ob)
        if pts is None:
            raise ValueError("points: outline of the cut not found for %s" % ob.name)
    pp.write_points(ob, [(float(x), float(y)) for x, y in (pts or [])])
    ob.update_tag()
    return ob
