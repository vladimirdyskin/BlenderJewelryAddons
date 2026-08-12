from __future__ import annotations

import importlib
import sys
from pathlib import Path

import bpy


ADDON_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = Path(__file__).resolve().parent / "all_casts_preview.png"
sys.path.insert(0, str(ADDON_DIR.parent))
parametric_gems = importlib.import_module("parametric_gems")


def main() -> None:
    parametric_gems.register()

    scene = bpy.context.scene
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

    scene.unit_settings.system = "NONE"
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(OUTPUT_PATH)
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "WORLD"
    scene.display.shading.background_type = "VIEWPORT"
    scene.display.shading.background_color = (0.025, 0.03, 0.04)

    gem_material = bpy.data.materials.new("Gem Preview")
    gem_material.diffuse_color = (0.03, 0.35, 0.62, 1.0)
    cast_material = bpy.data.materials.new("Cast Preview")
    cast_material.diffuse_color = (0.82, 0.48, 0.08, 1.0)

    for index, (cut, spec) in enumerate(parametric_gems._CUT_SPECS.items()):
        column = index % 6
        row = index // 6
        x = (column - 2.5) * 6.0
        y = (1.0 - row) * 7.0

        size_scale = 4.0 / max(spec.base_width, spec.base_length)
        width = spec.base_width * size_scale
        length = spec.base_length * size_scale
        bpy.ops.mesh.parametric_gem_add(
            "EXEC_DEFAULT",
            cut=cut,
            length_mm=length,
            width_mm=width,
            girdle_percent=spec.girdle_percent,
            crown_percent=spec.crown_percent,
            pavilion_percent=spec.pavilion_percent,
        )
        gem = bpy.context.object
        gem.location = (x, y, 0.0)
        gem.data.materials.append(gem_material)

        bpy.ops.object.parametric_cast_add("EXEC_DEFAULT")
        cast = bpy.context.object
        cast.data.materials.append(cast_material)

    camera_data = bpy.data.cameras.new("Preview Camera")
    camera = bpy.data.objects.new("Preview Camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (0.0, 0.0, 50.0)
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 36.0
    camera_data.clip_start = 0.1
    scene.camera = camera

    bpy.ops.render.render(write_still=True)
    print(f"Rendered preview: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
