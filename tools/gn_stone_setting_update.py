"""
Обновление связки каста в открытом файле: устаревшие копии групп My_Stone, My_Stone_Prongs,
My_Stone_Cast, My_Setting_Bool пересобираются на месте скриптом gn_stone_setting_build.py.
Каждое добавление ассета из библиотеки даёт файлу свою копию группы (.001, .002) — обновляются все.

Устаревшая — та, у которой нет сокетов текущей версии; остальные не трогаются (в них могут быть
правки руками). Сборщик мог измениться и без новых сокетов — тогда main(force=True) пересобирает
все копии; перед этим убедиться, что в них нет ручных правок.
Значения на модификаторах сохраняются, групп, которых в файле нет, скрипт не создаёт, файл не сохраняет.

Камни и контуры огранок (Unit ..., Outline ..., RWPRound), на которые ссылается My_Stone, берутся из
библиотеки MyAssets.blend (append, без коллекции) — как при добавлении ассета. Библиотека не найдена —
сборщик создаст их сам в коллекции My_Gem_Cast Utils этого файла.
Сборщик ищет группу по имени, поэтому копия на время сборки получает базовое имя.
Set Material, поставленный руками прямо перед выходом My_Stone (до появления входа Stone Material),
переносится: его материал записывается во вход Stone Material модификаторов этой группы, где он пуст.
Запуск: Text Editor -> Run Script или через MCP: exec(open(путь).read(), ns); ns["main"]().
"""

import os
import re

import bpy

BUILDER = os.path.expanduser("~/GitHub/BlenderJewelryAddons/tools/gn_stone_setting_build.py")
BUILD = {"My_Stone": "build_stone", "My_Stone_Prongs": "build_prongs", "My_Stone_Cast": "build_cast",
         "My_Setting_Bool": "build_bool"}
KEEP = "__keep__"
LIBRARY = "MyAssets.blend"
HELPERS = ("Unit ", "Outline ", "RWPRound")


def helpers_from_library(library=None):
    """Недостающие камни и контуры огранок — из MyAssets.blend библиотеки ассетов, без коллекции."""
    paths = [library] if library else [os.path.join(lib.path, LIBRARY) for lib in
                                       bpy.context.preferences.filepaths.asset_libraries]
    path = next((p for p in paths if p and os.path.exists(p)), None)
    if path is None:
        print("Library %s not found: helper objects will be generated in this file" % LIBRARY)
        return 0
    with bpy.data.libraries.load(path) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith(HELPERS) and n not in bpy.data.objects]
    return len(dst.objects)


def manual_material(ng):
    """Материал узла Set Material, поставленного руками прямо перед выходом группы."""
    out = next((n for n in ng.nodes if n.bl_idname == "NodeGroupOutput" and n.inputs[0].links), None)
    node = out.inputs[0].links[0].from_node if out else None
    if node and node.bl_idname == "GeometryNodeSetMaterial" and not node.inputs["Material"].is_linked:
        return node.inputs["Material"].default_value
    return None


def set_empty(ng, socket, value):
    """Вход socket модификаторов группы ng, где он пуст, = value."""
    key = next(it.identifier for it in ng.interface.items_tree if it.item_type == "SOCKET" and it.name == socket)
    for ob in bpy.data.objects:
        for md in ob.modifiers:
            if md.type == "NODES" and md.node_group == ng and getattr(md.properties.inputs, key).value is None:
                getattr(md.properties.inputs, key).value = value


def outdated(ng, sockets):
    have = {(it.parent.name or None, it.name) for it in ng.interface.items_tree if it.item_type == "SOCKET"}
    return any((panel, name) not in have for name, _t, _d, _mn, _mx, panel, _s in sockets)


def main(force=False, library=None):
    added = helpers_from_library(library)
    ns = {"__name__": "gn_stone_setting_build"}
    exec(open(BUILDER).read(), ns)
    done, kept = [], []
    for base, fn in BUILD.items():
        pat = re.compile(re.escape(base) + r"(\.\d+)?$")
        for ng in [g for g in bpy.data.node_groups if pat.match(g.name) and g.library is None]:
            name = ng.name
            if not force and not outdated(ng, ns["SOCKETS"][base]):
                kept.append(name)
                continue
            mat = manual_material(ng) if base == "My_Stone" else None
            other = bpy.data.node_groups.get(base) if name != base else None
            if other is not None:
                other.name = KEEP + base
            ng.name = base
            ns[fn]()
            if mat is not None:
                set_empty(ng, "Stone Material", mat)
            ng.name = name
            if other is not None:
                other.name = base
            done.append("%s %d" % (name, len(ng.nodes)))
    for ob in bpy.data.objects:
        ob.update_tag()
    print("Updated in place: %s; kept: %s; helper objects from library: %d" % (
        ", ".join(done) or "-", ", ".join(kept) or "-", added))
    return done, kept


if __name__ == "__main__":
    main()
