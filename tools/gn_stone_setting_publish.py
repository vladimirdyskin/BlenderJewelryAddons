"""
Публикация связки каста — My_Stone, My_Stone_Prongs, My_Stone_Cast, My_Setting_Bool — ассетами
в библиотеку (каталог MyAsset). Оформление как в gn_gems_curve_publish.py.

Группы уже собраны скриптом gn_stone_setting_build.py, здесь только пометка. Запуск в открытом
MyAssets.blend (MCP / Text Editor) или фоновым Blender на этом файле:

    BLENDER_USER_RESOURCES=<временная папка>/5.2 Blender --factory-startup --background \\
        ".../AssetLibrary/MyAssets.blend" --python tools/gn_stone_setting_publish.py

Камни по умолчанию встроены в My_Stone (RWPRound и Unit Emerald в узле, Diam пуст — камень по Cut):
с ассетом они приходят в файл сами, без коллекции. Объект по умолчанию на сокете интерфейса в 5.2
в новый модификатор не подставляется, поэтому у Diam его нет.
Unit Emerald — ещё и ассет-объект, как SampleGem.
"""

import os

import bpy

CATALOG_ID = "0d8c4291-31b6-4372-87df-d74166d6de54"     # MyAsset
GROUPS = ("My_Stone", "My_Stone_Prongs", "My_Stone_Cast", "My_Setting_Bool")
EMERALD = "Unit Emerald"
SAVE_VERSIONS = 3                                       # factory-startup держит только .blend1


def publish(idb):
    idb.use_fake_user = True
    idb.asset_mark()
    idb.asset_data.catalog_id = CATALOG_ID


def main():
    groups = [bpy.data.node_groups[n] for n in GROUPS]
    diam = next(i for i in groups[0].interface.items_tree if i.item_type == "SOCKET" and i.name == "Diam")
    diam.default_value = None
    for ng in groups:
        publish(ng)
    publish(bpy.data.objects[EMERALD])
    if bpy.app.background:
        bpy.context.preferences.filepaths.save_version = SAVE_VERSIONS
    bpy.ops.wm.save_mainfile()
    print("Published %d groups, '%s' to %s" % (len(groups), EMERALD, os.path.basename(bpy.data.filepath)))


if __name__ == "__main__":
    main()
