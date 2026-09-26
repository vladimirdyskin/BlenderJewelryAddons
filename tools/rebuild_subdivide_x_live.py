from __future__ import annotations

import sys

import bpy


MODULE_NAME = "bl_ext.user_default.jewelry_suite.gn_subdivide_x"
module = sys.modules.get(MODULE_NAME)
if module is None:
    raise RuntimeError(f"Module '{MODULE_NAME}' is not loaded")

group = module.build_group()
bpy.context.view_layer.update()

saved = False
if bpy.data.filepath:
    bpy.ops.wm.save_mainfile()
    saved = True

result = {
    "blend": bpy.data.filepath,
    "group": group.name,
    "build_version": group.get("jewelry_suite_build_version"),
    "nodes": len(group.nodes),
    "saved": saved,
}
