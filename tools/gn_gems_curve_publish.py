"""
Публикация My_Gems_Curve и My_Prongs ассетами в библиотеку (каталог MyAsset).

Графы собираются скриптами gn_gems_curve_build.py и gn_prongs_build.py в открытом файле.
Повторный запуск обновляет группы на месте. Запуск фоновым Blender, чтобы не трогать сессию:

    BLENDER_USER_RESOURCES=<временная папка>/5.2 Blender --factory-startup --background \\
        ".../AssetLibrary/MyAssets.blend" --python tools/gn_gems_curve_publish.py

Оформление как у My_Gems_On_Curve: каталог MyAsset, is_modifier, fake user, входы Diam и Prongs
по умолчанию указывают на SampleGem и SingleProng этого файла (Add Modifier дотянет их сам).
Подгруппа Gems Curve Mirror — не ассет.
"""

import os

import bpy

CATALOG_ID = "0d8c4291-31b6-4372-87df-d74166d6de54"     # MyAsset
SAVE_VERSIONS = 3                                       # factory-startup держит только .blend1
HERE = os.path.dirname(os.path.abspath(__file__))


def build(script):
    ns = {"__name__": "gn_build"}
    exec(open(os.path.join(HERE, script)).read(), ns)
    return ns["build_group"]()


def set_default(ng, socket, value):
    item = next(i for i in ng.interface.items_tree if i.item_type == "SOCKET" and i.name == socket)
    item.default_value = value


def publish(ng):
    ng.is_modifier = True
    ng.use_fake_user = True
    ng.asset_mark()
    ng.asset_data.catalog_id = CATALOG_ID


def main():
    gems = build("gn_gems_curve_build.py")
    prongs = build("gn_prongs_build.py")
    set_default(gems, "Diam", bpy.data.objects["SampleGem"])
    set_default(prongs, "Prongs", bpy.data.objects["SingleProng"])
    publish(gems)
    publish(prongs)
    bpy.context.preferences.filepaths.save_version = SAVE_VERSIONS
    bpy.ops.wm.save_mainfile()
    print("Published '%s', '%s' to %s" % (gems.name, prongs.name, os.path.basename(bpy.data.filepath)))


if __name__ == "__main__":
    main()
