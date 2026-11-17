"""
My_Metal_Bool — булеан всего металла, камень не трогается. Решатель Manifold.

Модификатор в конце стека (после My_Stone / My_Stone_Prongs / My_Stone_Cast) или на любом объекте,
где металл — меш, а камни — инстансы.

Металл — меш-компонента геометрии. Острова (Mesh Island -> Split to Instances) объединяются Union,
каждый остров — отдельный операнд: перекрытия внутри одного операнда Manifold не склеивает.
Из объединённого тела вычитаются BoolObject и объекты BoolCollection (Relative, Separate Children) —
тоже отдельные операнды. Резаков нет — на выходе просто объединённый металл.
Всё остальное (инстансы: камень и носители My_Stone) проходит нетронутым и присоединяется в конце:
камень остаётся инстансом объекта с "gem", JewelCraft его видит.

Чего нода не делает:
    посадку под камень не режет — это My_Setting_Bool;
    металл, который пришёл инстансами (крапана My_Prongs без Realize), не режется — проходит как есть;
    незамкнутый металл или резак Manifold молча превращает в пустой результат.

Помощники сборки и интерфейса — gn_stone_setting_build.py (сокеты только добавляются, узлы пересобираются).
Запуск: Text Editor -> Run Script или через MCP: exec(open(путь).read(), ns); ns["main"]().
    setup(ob, bool_object=None, bool_collection=None) — модификатор в конец стека объекта.
"""

import importlib.util
import os

import bpy

REPO = os.path.expanduser("~/GitHub/BlenderJewelryAddons")
STONE_PATH = os.path.join(REPO, "tools", "gn_stone_setting_build.py")

GROUP_NAME = "My_Metal_Bool"
CATALOG_ID = "0d8c4291-31b6-4372-87df-d74166d6de54"     # MyAsset
# (имя, тип, default, min, max, панель, subtype)
SOCKETS = [
    ("BoolObject", "NodeSocketObject", None, None, None, None, None),
    ("BoolCollection", "NodeSocketCollection", None, None, None, None, None),
    ("Smooth", "NodeSocketBool", True, None, None, None, None),
]

_SS = []


def stone_builder():
    """Модуль gn_stone_setting_build.py: begin, join, boolean, object_info, has_instances, smooth, finish."""
    if not _SS:
        spec = importlib.util.spec_from_file_location("gn_stone_setting_ref", STONE_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _SS.append(mod)
    return _SS[0]


def build_group():
    ss = stone_builder()
    ss.SOCKETS[GROUP_NAME] = SOCKETS
    ng, b, gi = ss.begin(GROUP_NAME)

    # --- металл (меш) и всё остальное (инстансы — камни — проходят нетронутыми) ---
    b.section("Metal")
    parts = b.node("GeometryNodeSeparateComponents", 0, 0)
    b.link(b.g("Geometry"), parts.inputs["Geometry"])
    metal = parts.outputs["Mesh"]
    rest = ss.join(b, [s for s in parts.outputs if s.name != "Mesh"], 200, -300)
    # острова — отдельные операнды Manifold
    split = b.node("GeometryNodeSplitToInstances", 400, 0, domain="FACE")
    b.link(metal, split.inputs["Geometry"])
    b.link(b.node("GeometryNodeInputMeshIsland", 200, -150).outputs["Island Index"], split.inputs["Group ID"])
    islands = split.outputs["Instances"]

    # --- резаки: BoolObject и объекты BoolCollection — отдельные операнды ---
    b.section("Booleans")
    x0 = 800
    bool_obj = ss.object_info(b, gi(None, "BoolObject"), "RELATIVE", x0, -500).outputs["Geometry"]
    coll = b.node("GeometryNodeCollectionInfo", x0, -700, transform_space="RELATIVE")
    b.link(gi(None, "BoolCollection"), coll.inputs["Collection"])
    coll.inputs["Separate Children"].default_value = True
    coll.inputs["Reset Children"].default_value = False
    bools = ss.join(b, [bool_obj, coll.outputs["Instances"]], x0 + 200, -600)
    has_bool = ss.has_instances(b, bools, x0 + 200, -800)
    united = ss.boolean(b, "UNION", None, [islands], x0, 0)
    result = b.switch("GEOMETRY", has_bool, united, ss.boolean(b, "DIFFERENCE", united, [bools], x0 + 400, -200),
                      x0 + 600, 0)

    # --- выход: сглаживание, остальное (камни) — последним ---
    b.section("Output")
    result = ss.smooth(b, result, gi(None, "Smooth"), x0 + 800, 0)
    out = ss.join(b, [result, rest], x0 + 1400, 0)
    return ss.finish(b, ng, out, x0 + 1600)


def setup(ob, bool_object=None, bool_collection=None):
    """Модификатор My_Metal_Bool в конце стека объекта (уже есть — тот же); резаки — когда заданы."""
    ss = stone_builder()
    ng = bpy.data.node_groups.get(GROUP_NAME) or build_group()
    ob = bpy.data.objects[ob] if isinstance(ob, str) else ob
    md = next((m for m in ob.modifiers if m.type == "NODES" and m.node_group == ng), None)
    if md is None:
        md = ob.modifiers.new(GROUP_NAME, "NODES")
        md.node_group = ng
    keys = ss.mods()[1].socket_keys(ng)
    for name, value, data in (("BoolObject", bool_object, bpy.data.objects),
                              ("BoolCollection", bool_collection, bpy.data.collections)):
        if value is not None:
            getattr(md.properties.inputs, keys[(None, name)]).value = data[value] if isinstance(value, str) else value
    ob.update_tag()
    print("Metal boolean set up on '%s'" % ob.name)
    return md


def publish():
    """Группа — ассетом в каталог MyAsset (запуск на MyAssets.blend; файл сохраняет вызывающий)."""
    ng = build_group()
    ng.use_fake_user = True
    ng.asset_mark()
    ng.asset_data.catalog_id = CATALOG_ID
    return ng


def main():
    build_group()


if __name__ == "__main__":
    main()
