from __future__ import annotations

import addon_utils
import bpy
import importlib
import sys


MODULE_NAME = "bl_ext.user_default.parametric_gems"

before = []
snapshots = []
cast_snapshots = []
template_snapshots = []
instance_snapshots = []
scene_settings = getattr(bpy.context.scene, "parametric_gem_settings", None)
active_template_name = (
    scene_settings.cast_template.name
    if scene_settings is not None
    and hasattr(scene_settings, "cast_template")
    and scene_settings.cast_template is not None
    else None
)
for obj in bpy.context.scene.objects:
    props = getattr(obj, "parametric_gem", None)
    if props is not None and props.is_parametric:
        gem_metadata = obj.get("gem", {})
        snapshots.append({
            "object_name": obj.name,
            "cut": gem_metadata.get("cut", props.cut),
            "stone": gem_metadata.get("stone", props.stone),
            "length_mm": props.length_mm,
            "width_mm": props.width_mm,
            "girdle_percent": props.girdle_percent,
            "crown_percent": props.crown_percent,
            "pavilion_percent": props.pavilion_percent,
        })
        before.append({
            "name": obj.name,
            "dimensions": [round(value, 6) for value in obj.dimensions],
            "scale": [round(value, 6) for value in obj.scale],
        })
    cast_props = getattr(obj, "parametric_cast", None)
    if cast_props is not None and cast_props.is_parametric:
        cast_snapshots.append({
            "object_name": obj.name,
            "source_gem_name": cast_props.source_gem.name if cast_props.source_gem is not None else None,
            "clearance_mm": cast_props.clearance_mm,
            "wall_thickness_mm": cast_props.wall_thickness_mm,
            "height_mm": cast_props.height_mm,
            "top_offset_mm": cast_props.top_offset_mm,
            "rail_height_mm": getattr(cast_props, "rail_height_mm", 0.4),
            "bottom_scale_percent": getattr(cast_props, "bottom_scale_percent", 60.0),
            "support_count": getattr(cast_props, "support_count", 4),
            "support_width_mm": getattr(cast_props, "support_width_mm", 0.7),
        })
    template_props = getattr(obj, "parametric_cast_template", None)
    if template_props is not None and template_props.is_template:
        template_snapshots.append({
            "object_name": obj.name,
            "cut": template_props.cut,
            "reference_length_mm": template_props.reference_length_mm,
            "reference_width_mm": template_props.reference_width_mm,
            "reference_depth_mm": template_props.reference_depth_mm,
        })
    instance_props = getattr(obj, "parametric_cast_instance", None)
    if instance_props is not None and instance_props.is_instance:
        instance_snapshots.append({
            "object_name": obj.name,
            "template_name": instance_props.template_object.name if instance_props.template_object else None,
            "source_gem_name": instance_props.source_gem.name if instance_props.source_gem else None,
        })

_, loaded = addon_utils.check(MODULE_NAME)
if loaded:
    addon_utils.disable(MODULE_NAME, default_set=False)

importlib.invalidate_caches()
if MODULE_NAME in sys.modules:
    importlib.reload(sys.modules[MODULE_NAME])

module = addon_utils.enable(MODULE_NAME, default_set=True, persistent=True)
if module is None:
    raise RuntimeError(f"Could not reload extension: {MODULE_NAME}")

rebuilt = []
module._UPDATE_GUARD = True
try:
    for snapshot in snapshots:
        obj = bpy.data.objects.get(snapshot["object_name"])
        if obj is None:
            continue
        props = obj.parametric_gem
        props.is_parametric = True
        props.cut = snapshot["cut"]
        props.stone = snapshot["stone"]
        props.length_mm = snapshot["length_mm"]
        props.width_mm = snapshot["width_mm"]
        props.girdle_percent = snapshot["girdle_percent"]
        props.crown_percent = snapshot["crown_percent"]
        props.pavilion_percent = snapshot["pavilion_percent"]
        module.rebuild_object(obj, bpy.context.scene)
        rebuilt.append(obj)
finally:
    module._UPDATE_GUARD = False

rebuilt_casts = []
module._CAST_UPDATE_GUARD = True
try:
    for snapshot in cast_snapshots:
        obj = bpy.data.objects.get(snapshot["object_name"])
        source_name = snapshot["source_gem_name"]
        source_gem = bpy.data.objects.get(source_name) if source_name else None
        if obj is None or source_gem is None:
            continue
        props = obj.parametric_cast
        props.is_parametric = True
        props.source_gem = source_gem
        props.clearance_mm = snapshot["clearance_mm"]
        props.wall_thickness_mm = snapshot["wall_thickness_mm"]
        props.height_mm = snapshot["height_mm"]
        props.top_offset_mm = snapshot["top_offset_mm"]
        props.rail_height_mm = snapshot["rail_height_mm"]
        props.bottom_scale_percent = snapshot["bottom_scale_percent"]
        props.support_count = snapshot["support_count"]
        props.support_width_mm = snapshot["support_width_mm"]
        module.rebuild_cast_object(obj)
        rebuilt_casts.append(obj)
finally:
    module._CAST_UPDATE_GUARD = False

restored_templates = []
for snapshot in template_snapshots:
    obj = bpy.data.objects.get(snapshot["object_name"])
    if obj is None:
        continue
    props = obj.parametric_cast_template
    props.is_template = True
    props.cut = snapshot["cut"]
    props.reference_length_mm = snapshot["reference_length_mm"]
    props.reference_width_mm = snapshot["reference_width_mm"]
    props.reference_depth_mm = snapshot["reference_depth_mm"]
    restored_templates.append(obj)

rebuilt_instances = []
for snapshot in instance_snapshots:
    obj = bpy.data.objects.get(snapshot["object_name"])
    template_name = snapshot["template_name"]
    source_name = snapshot["source_gem_name"]
    template = bpy.data.objects.get(template_name) if template_name else None
    source_gem = bpy.data.objects.get(source_name) if source_name else None
    if obj is None or template is None or source_gem is None:
        continue
    props = obj.parametric_cast_instance
    props.is_instance = True
    props.template_object = template
    props.source_gem = source_gem
    module.rebuild_cast_instance(obj)
    rebuilt_instances.append(obj)

if active_template_name:
    active_template = bpy.data.objects.get(active_template_name)
    if active_template is not None:
        bpy.context.scene.parametric_gem_settings.cast_template = active_template

for obj in bpy.context.scene.objects:
    props = getattr(obj, "parametric_gem", None)
    if props is None or not props.is_parametric or obj in rebuilt:
        continue
    module.rebuild_object(obj, bpy.context.scene)
    rebuilt.append(obj)

bpy.context.view_layer.update()
bpy.ops.wm.save_userpref()
if bpy.data.filepath:
    bpy.ops.wm.save_mainfile()

result = {
    "before": before,
    "after": [
        {
            "name": obj.name,
            "dimensions": [round(value, 6) for value in obj.dimensions],
            "scale": [round(value, 6) for value in obj.scale],
            "length_mm": obj.parametric_gem.length_mm,
            "width_mm": obj.parametric_gem.width_mm,
        }
        for obj in rebuilt
    ],
    "casts": [
        {
            "name": obj.name,
            "source": obj.parametric_cast.source_gem.name,
            "dimensions": [round(value, 6) for value in obj.dimensions],
        }
        for obj in rebuilt_casts
    ],
    "templates": [obj.name for obj in restored_templates],
    "instances": [obj.name for obj in rebuilt_instances],
    "saved_file": bpy.data.filepath,
}
