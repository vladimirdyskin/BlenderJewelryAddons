from __future__ import annotations

import bpy


scene = bpy.context.scene
gems = []
for obj in scene.objects:
    props = getattr(obj, "parametric_gem", None)
    if props is None or not props.is_parametric:
        continue
    gems.append({
        "name": obj.name,
        "dimensions": [round(value, 6) for value in obj.dimensions],
        "scale": [round(value, 6) for value in obj.scale],
        "length_mm": props.length_mm,
        "width_mm": props.width_mm,
        "depth_mm": props.depth_mm,
        "cut": props.cut,
        "girdle_percent": props.girdle_percent,
        "crown_percent": props.crown_percent,
        "pavilion_percent": props.pavilion_percent,
    })

result = {
    "filepath": bpy.data.filepath,
    "unit_system": scene.unit_settings.system,
    "scale_length": scene.unit_settings.scale_length,
    "length_unit": scene.unit_settings.length_unit,
    "active_object": bpy.context.object.name if bpy.context.object else None,
    "parametric_gems": gems,
}
