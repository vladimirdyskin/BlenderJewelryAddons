from __future__ import annotations

import bpy
from bl_ext.user_default import parametric_gems


updated = []
parametric_gems._CAST_UPDATE_GUARD = True
try:
    for obj in bpy.context.scene.objects:
        props = getattr(obj, "parametric_cast", None)
        if props is None or not props.is_parametric:
            continue
        props.clearance_mm = parametric_gems._CAST_DEFAULT_CLEARANCE
        props.wall_thickness_mm = parametric_gems._CAST_DEFAULT_WALL_THICKNESS
        props.height_mm = parametric_gems._CAST_DEFAULT_HEIGHT
        props.top_offset_mm = parametric_gems._CAST_DEFAULT_TOP_OFFSET
        props.rail_height_mm = parametric_gems._CAST_DEFAULT_RAIL_HEIGHT
        props.bottom_scale_percent = parametric_gems._CAST_DEFAULT_BOTTOM_SCALE
        props.support_count = parametric_gems._CAST_DEFAULT_SUPPORT_COUNT
        props.support_width_mm = parametric_gems._CAST_DEFAULT_SUPPORT_WIDTH
        parametric_gems.rebuild_cast_object(obj)
        updated.append(obj)
finally:
    parametric_gems._CAST_UPDATE_GUARD = False

bpy.context.view_layer.update()
if bpy.data.filepath:
    bpy.ops.wm.save_mainfile()

result = {
    "updated": [
        {
            "name": obj.name,
            "source": obj.parametric_cast.source_gem.name,
            "dimensions": [round(value, 6) for value in obj.dimensions],
        }
        for obj in updated
    ],
    "saved_file": bpy.data.filepath,
}
