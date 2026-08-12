from __future__ import annotations

import bpy

from bl_ext.user_default import parametric_gems


obj = bpy.context.object
if obj is None or not obj.parametric_gem.is_parametric:
    raise RuntimeError("Active object is not a parametric gem")

parametric_gems._UPDATE_GUARD = True
try:
    obj.parametric_gem.cut = "MARQUISE"
finally:
    parametric_gems._UPDATE_GUARD = False

parametric_gems.rebuild_object(obj, bpy.context.scene)
bpy.context.view_layer.update()
bpy.ops.wm.save_mainfile()

result = {
    "name": obj.name,
    "cut": obj.parametric_gem.cut,
    "dimensions": [round(value, 6) for value in obj.dimensions],
    "depth_mm": obj.parametric_gem.depth_mm,
    "girdle_percent": obj.parametric_gem.girdle_percent,
    "crown_percent": obj.parametric_gem.crown_percent,
    "pavilion_percent": obj.parametric_gem.pavilion_percent,
}
