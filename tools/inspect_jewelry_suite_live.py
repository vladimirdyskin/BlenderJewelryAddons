from __future__ import annotations

import sys

import bpy


enabled = sorted(
    addon.module
    for addon in bpy.context.preferences.addons
    if any(token in addon.module.lower() for token in ("parametric", "jewel", "ruler"))
)

result = {
    "blend": bpy.data.filepath,
    "enabled_addons": enabled,
    "loaded_modules": sorted(
        name
        for name in sys.modules
        if any(token in name.lower() for token in ("parametric_gems", "jewel_tools", "pretty_ruler", "jewelry_suite"))
    ),
    "properties": {
        "parametric_gem": hasattr(bpy.types.Object, "parametric_gem"),
        "jewel_snap": hasattr(bpy.types.Scene, "jewel_snap"),
        "pretty_ruler": hasattr(bpy.types.Scene, "pretty_ruler"),
        "subdivide_local_x": hasattr(bpy.types.Scene, "jewel_subdivide_x"),
    },
    "panel_categories": {
        "parametric_gems": bpy.types.VIEW3D_PT_parametric_gems.bl_category,
        "jewel_tools": bpy.types.VIEW3D_PT_jewel_tools.bl_category,
        "pretty_ruler": bpy.types.VIEW3D_PT_pretty_ruler.bl_category,
    },
    "operators": {
        "subdivide_local_x": hasattr(bpy.types, "OBJECT_OT_add_subdivide_x_nodes"),
        "legacy_destructive_subdivide_x": hasattr(bpy.types, "MESH_OT_subdivide_local_x"),
        "link_identical_gems": hasattr(bpy.types, "OBJECT_OT_link_identical_gems"),
        "link_identical_prongs": hasattr(bpy.types, "OBJECT_OT_link_identical_prongs"),
    },
}
