from __future__ import annotations

import importlib
import sys
from pathlib import Path

import bpy


ADDON_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = Path(__file__).resolve().parent / "marquise_preview.png"
sys.path.insert(0, str(ADDON_DIR.parent))
parametric_gems = importlib.import_module("parametric_gems")


def add_area_light(name: str, location: tuple[float, float, float], energy: float, size: float) -> None:
    light_data = bpy.data.lights.new(name, "AREA")
    light_data.energy = energy
    light_data.shape = "DISK"
    light_data.size = size
    light = bpy.data.objects.new(name, light_data)
    bpy.context.scene.collection.objects.link(light)
    light.location = location


def main() -> None:
    parametric_gems.register()

    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 600
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(OUTPUT_PATH)
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "WORLD"
    scene.display.shading.background_type = "VIEWPORT"
    scene.display.shading.background_color = (0.008, 0.01, 0.015)

    bpy.ops.mesh.parametric_gem_add(
        "EXEC_DEFAULT",
        length_mm=10.0,
        width_mm=5.0,
        girdle_percent=3.41,
        crown_percent=12.73,
        pavilion_percent=39.51,
    )
    gem = bpy.context.object

    material = bpy.data.materials.new("Preview Gem")
    material.diffuse_color = (0.08, 0.55, 0.72, 1.0)
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = (0.03, 0.35, 0.55, 1.0)
    principled.inputs["Metallic"].default_value = 0.15
    principled.inputs["Roughness"].default_value = 0.22
    gem.data.materials.append(material)

    camera_data = bpy.data.cameras.new("Preview Camera")
    camera = bpy.data.objects.new("Preview Camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (0.0, 0.0, 25.0)
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 12.0
    camera_data.clip_start = 0.1
    scene.camera = camera

    bpy.ops.render.render(write_still=True)
    print(f"Rendered preview: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
