# SPDX-License-Identifier: GPL-3.0-or-later

"""Build, save and render a separate Surface Pave demonstration scene."""

from pathlib import Path
import sys

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import jewelry_suite
from jewelry_suite.surface_pave import MASK_NAME, rebuild


def material(name, color, metallic, roughness):
    result = bpy.data.materials.new(name)
    result.diffuse_color = (*color, 1.0)
    result.use_nodes = True
    shader = result.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (*color, 1.0)
    shader.inputs['Metallic'].default_value = metallic
    shader.inputs['Roughness'].default_value = roughness
    return result


def point_at(obj, point):
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat('-Z', 'Y').to_euler()


jewelry_suite.register()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.unit_settings.system = 'NONE'
gold = material('Satin Gold', (0.5, 0.29, 0.085), 0.75, 0.28)
stone = material('Pave Preview Sapphire', (0.07, 0.27, 0.4), 0.55, 0.18)

bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=64, radius=6.0)
surface = bpy.context.object
surface.name = 'Pave Demo Surface'
surface.data.materials.append(gold)
for face in surface.data.polygons:
    face.use_smooth = True
mask = surface.vertex_groups.new(name=MASK_NAME)
for vertex in surface.data.vertices:
    # A broad painted cap, with an intentionally unpainted circular opening.
    x, y, z = vertex.co
    outer = min(1.0, max(0.0, (z - 1.5) * 2.0))
    hole_distance = ((x - 1.0) ** 2 + (y + 0.3) ** 2) ** 0.5
    hole = min(1.0, max(0.0, (hole_distance - 0.75) * 3.0))
    mask.add([vertex.index], min(outer, hole), 'REPLACE')
surface.jewel_pave.diameter = 0.9
surface.jewel_pave.gap = 0.12
surface.jewel_pave.border = 0.12
surface.jewel_pave.offset = 0.035
output = rebuild(bpy.context, surface)
output['pave_template'].data.materials.clear()
output['pave_template'].data.materials.append(stone)
scene.jewel_pave_surface = surface

bpy.ops.object.camera_add(location=(10.0, -13.0, 16.0))
camera = bpy.context.object
camera.name = 'Pave Demo Camera'
camera.data.type = 'ORTHO'
camera.data.ortho_scale = 15.0
point_at(camera, (0, 0, 0.8))
scene.camera = camera
for name, position, power, size in (
        ('Key', (1, -8, 16), 3500, 9),
        ('Fill', (-10, -3, 8), 2500, 8),
        ('Rim', (3, 8, 12), 4500, 7)):
    bpy.ops.object.light_add(type='AREA', location=position)
    light = bpy.context.object
    light.name = name
    light.data.energy = power
    light.data.shape = 'DISK'
    light.data.size = size
    point_at(light, (0, 0, 0))
scene.world.color = (0.18, 0.18, 0.18)
scene.render.engine = 'CYCLES'
scene.cycles.samples = 24
scene.cycles.use_denoising = True
scene.render.resolution_x = 1000
scene.render.resolution_y = 1000
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.film_transparent = False
scene.view_settings.view_transform = 'AgX'

bpy.ops.object.select_all(action='DESELECT')
surface.select_set(True)
bpy.context.view_layer.objects.active = surface
surface.vertex_groups.active_index = mask.index
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type == 'VIEW_3D':
            area.spaces.active.region_3d.view_distance = 20
            area.spaces.active.region_3d.view_location = (0, 0, 1)
            area.spaces.active.region_3d.view_rotation = camera.rotation_euler.to_quaternion()
            area.spaces.active.show_region_ui = True

destination = ROOT / 'dist'
destination.mkdir(exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(destination / 'surface-pave-demo.blend'))
scene.render.filepath = str(destination / 'surface-pave-sphere.png')
bpy.ops.render.render(write_still=True)
camera.location = (0, 0, 20)
point_at(camera, (0, 0, 0))
scene.render.filepath = str(destination / 'surface-pave-top.png')
bpy.ops.render.render(write_still=True)
print('SURFACE_PAVE_DEMO', output['stone_count'], 'gems', destination)
