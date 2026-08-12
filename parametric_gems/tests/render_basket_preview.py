from __future__ import annotations

import importlib
import sys
from pathlib import Path

import bpy
from mathutils import Vector


ADDON_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = Path(__file__).resolve().parent / "basket_preview.png"
sys.path.insert(0, str(ADDON_DIR.parent))
parametric_gems = importlib.import_module("parametric_gems")


def main() -> None:
    parametric_gems.register()

    scene = bpy.context.scene
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

    scene.unit_settings.system = "NONE"
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(OUTPUT_PATH)
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "BOTH"
    scene.display.shading.background_type = "VIEWPORT"
    scene.display.shading.background_color = (0.025, 0.03, 0.04)

    spec = parametric_gems._CUT_SPECS["MARQUISE"]
    bpy.ops.mesh.parametric_gem_add(
        "EXEC_DEFAULT",
        cut="MARQUISE",
        length_mm=10.0,
        width_mm=5.0,
        girdle_percent=spec.girdle_percent,
        crown_percent=spec.crown_percent,
        pavilion_percent=spec.pavilion_percent,
    )
    gem = bpy.context.object
    bpy.ops.object.parametric_cast_add("EXEC_DEFAULT")
    cast = bpy.context.object
    gem.hide_render = True

    cast_material = bpy.data.materials.new("Basket Preview")
    cast_material.diffuse_color = (0.82, 0.48, 0.08, 1.0)
    cast.data.materials.append(cast_material)

    camera_data = bpy.data.cameras.new("Preview Camera")
    camera = bpy.data.objects.new("Preview Camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (9.5, -12.0, 5.5)
    target = Vector((0.0, 0.0, -0.7))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 13.0
    scene.camera = camera

    bpy.ops.render.render(write_still=True)
    print(f"Rendered preview: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
