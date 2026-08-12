from __future__ import annotations

import bpy


parametric_gems = [
    obj
    for obj in bpy.context.scene.objects
    if obj.type == "MESH"
    and getattr(obj, "parametric_gem", None) is not None
    and obj.parametric_gem.is_parametric
]

result = {
    "cast_properties_registered": hasattr(bpy.types.Object, "parametric_cast"),
    "cast_operator_registered": hasattr(bpy.ops.object, "parametric_cast_add"),
    "template_properties_registered": hasattr(bpy.types.Object, "parametric_cast_template"),
    "instance_properties_registered": hasattr(bpy.types.Object, "parametric_cast_instance"),
    "template_register_operator": hasattr(bpy.ops.object, "parametric_cast_template_register"),
    "instance_place_operator": hasattr(bpy.ops.object, "parametric_cast_instances_place"),
    "parametric_gem_count": len(parametric_gems),
    "casts": [
        {
            "name": obj.name,
            "source": obj.parametric_cast.source_gem.name if obj.parametric_cast.source_gem else None,
            "dimensions": [round(value, 6) for value in obj.dimensions],
            "rail_width_mm": obj.parametric_cast.wall_thickness_mm,
            "rail_height_mm": obj.parametric_cast.rail_height_mm,
            "basket_height_mm": obj.parametric_cast.height_mm,
            "bottom_scale_percent": obj.parametric_cast.bottom_scale_percent,
            "support_count": obj.parametric_cast.support_count,
            "support_width_mm": obj.parametric_cast.support_width_mm,
        }
        for obj in bpy.context.scene.objects
        if obj.type == "MESH"
        and getattr(obj, "parametric_cast", None) is not None
        and obj.parametric_cast.is_parametric
    ],
    "saved_file": bpy.data.filepath,
}
