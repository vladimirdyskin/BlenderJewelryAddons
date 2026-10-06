# SPDX-License-Identifier: GPL-3.0-or-later

"""Run with Blender --background --factory-startup --python-exit-code 1."""

from pathlib import Path
import sys
import time

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jewelry_suite
from jewelry_suite.surface_pave import MASK_NAME, rebuild


def grid(name, half=5.0, subdivisions=20, weight=None):
    vertices = [(-half + 2 * half * x / subdivisions,
                 -half + 2 * half * y / subdivisions, 0.0)
                for y in range(subdivisions + 1) for x in range(subdivisions + 1)]
    faces = []
    row = subdivisions + 1
    for y in range(subdivisions):
        for x in range(subdivisions):
            a = y * row + x
            faces.append((a, a + 1, a + row + 1, a + row))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    group = obj.vertex_groups.new(name=MASK_NAME)
    for vertex in mesh.vertices:
        value = 1.0 if weight is None else weight(vertex.co)
        group.add([vertex.index], value, 'REPLACE')
    obj.jewel_pave.diameter = 1.0
    obj.jewel_pave.gap = 0.1
    obj.jewel_pave.border = 0.1
    obj.jewel_pave.live_preview = False
    return obj


def centers(obj):
    return [obj.matrix_world @ v.co for v in obj.data.vertices]


def validate_spacing(obj):
    values = centers(obj)
    minimum = min((a - b).length for i, a in enumerate(values) for b in values[i + 1:])
    assert minimum >= obj['minimum_center_distance_mm'] - 2e-5, minimum
    return minimum


def instance_matrices(output):
    bpy.context.view_layer.update()
    return [i.matrix_world.copy() for i in bpy.context.evaluated_depsgraph_get().object_instances
            if i.is_instance and i.parent.original == output]


started = time.monotonic()
jewelry_suite.register()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

plane = grid("Pave Plane")
output = rebuild(bpy.context, plane)
first = [tuple(v) for v in centers(output)]
assert 60 <= len(first) <= 85, len(first)
assert all(abs(x) <= 4.40001 and abs(y) <= 4.40001 and abs(z) < 1e-6 for x, y, z in first)
validate_spacing(output)
matrices = instance_matrices(output)
assert len(matrices) == len(first), (len(matrices), len(first))
assert all(i.object.original.get('gem', {}).get('cut') == 'ROUND'
           for i in bpy.context.evaluated_depsgraph_get().object_instances
           if i.is_instance and i.parent.original == output)
assert all((m.to_3x3() @ Vector((0, 0, 1)) - Vector((0, 0, 1))).length < 1e-5 for m in matrices)
counts = (len(bpy.data.objects), len(bpy.data.meshes), len(bpy.data.node_groups))
assert rebuild(bpy.context, plane) == output
assert [tuple(v) for v in centers(output)] == first
assert counts == (len(bpy.data.objects), len(bpy.data.meshes), len(bpy.data.node_groups))
print('PAVE_PLANE', len(first), 'instances', len(matrices))

# A small unpainted hole must exclude a whole stone, even if its center and
# circumference would miss the hole in a sparse point-sampling test.
hole = grid("Pave Hole", subdivisions=40,
            weight=lambda v: 0.0 if abs(v.x) <= 0.25 and abs(v.y) <= 0.25 else 1.0)
hole_output = rebuild(bpy.context, hole)
assert all(v.length >= 0.94 for v in centers(hole_output))
validate_spacing(hole_output)
print('PAVE_HOLE', hole_output['stone_count'])

# Two disconnected painted islands, with a threshold boundary at x = +/- 1.5.
islands = grid("Pave Islands", weight=lambda v: min(1.0, max(0.0, abs(v.x) - 1.0)))
island_output = rebuild(bpy.context, islands)
values = centers(island_output)
assert any(v.x > 2.1 for v in values) and any(v.x < -2.1 for v in values)
assert all(abs(v.x) >= 2.1 - 1e-5 for v in values)
validate_spacing(island_output)

# Paint setup, erase, fill and exit use Blender's actual 5.2 brush APIs.
bpy.context.scene.jewel_pave_surface = plane
bpy.context.tool_settings.use_auto_normalize = True
bpy.context.tool_settings.weight_paint.use_symmetry_x = True
assert bpy.ops.object.pave_mask(action='PAINT') == {'FINISHED'}
assert plane.mode == 'WEIGHT_PAINT'
assert plane.vertex_groups.active.name == MASK_NAME
assert bpy.context.tool_settings.weight_paint.brush.use_frontface
assert not bpy.context.tool_settings.weight_paint.use_symmetry_x
assert not bpy.context.tool_settings.use_auto_normalize
assert bpy.ops.object.pave_mask(action='ERASE') == {'FINISHED'}
assert bpy.context.tool_settings.weight_paint.unified_paint_settings.weight == 0.0
assert bpy.ops.object.pave_mask(action='DONE') == {'FINISHED'}
assert plane.mode == 'OBJECT'
assert bpy.context.tool_settings.use_auto_normalize
assert bpy.context.tool_settings.weight_paint.use_symmetry_x
assert not output.hide_get()
# Switching the target while painting restores the previous session as well.
assert bpy.ops.object.pave_mask(action='PAINT') == {'FINISHED'}
bpy.context.scene.jewel_pave_surface = hole
assert bpy.ops.object.pave_mask(action='ERASE') == {'FINISHED'}
assert not plane.jewel_pave.paint_state
assert not output.hide_get()
assert bpy.ops.object.pave_mask(action='DONE') == {'FINISHED'}
assert bpy.context.tool_settings.use_auto_normalize
print('PAVE_PAINT_WORKFLOW', 'passed')

# Evaluated geometry and world units, independent of scene display scale.
transformed = grid("Pave Transform", half=4.0)
displace = transformed.modifiers.new('Evaluated Surface', 'DISPLACE')
displace.direction = 'Z'
displace.mid_level = 0.0
displace.strength = 1.25
transformed.matrix_world = Matrix.Translation((12, -4, 3)) @ Matrix.Rotation(0.6, 4, 'Y') @ Matrix.Diagonal((1.5, 0.8, 1.0, 1.0))
bpy.context.scene.unit_settings.system = 'METRIC'
bpy.context.scene.unit_settings.scale_length = 0.001
transform_output = rebuild(bpy.context, transformed)
world_normal = (transformed.matrix_world.to_3x3().inverted().transposed() @ Vector((0, 0, 1))).normalized()
for center in centers(transform_output):
    local = transformed.matrix_world.inverted() @ center
    assert abs(local.z - 1.25) < 1e-5
    assert abs(local.x) <= 3.60001 and abs(local.y) <= 3.25001
for matrix in instance_matrices(transform_output):
    assert matrix.to_scale().x > 0.99999 and matrix.to_scale().x < 1.00001
    assert (matrix.to_3x3() @ Vector((0, 0, 1)) - world_normal).length < 1e-5
validate_spacing(transform_output)
original = centers(transform_output)
transformed.location += Vector((2, 3, 4))
bpy.context.view_layer.update()
assert all((a + Vector((2, 3, 4)) - b).length < 1e-5 for a, b in zip(original, centers(transform_output)))
print('PAVE_WORLD_UNITS', transform_output['stone_count'])

bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=6.0)
sphere = bpy.context.object
sphere.name = "Pave Sphere"
for polygon in sphere.data.polygons:
    polygon.use_smooth = True
group = sphere.vertex_groups.new(name=MASK_NAME)
group.add(list(range(len(sphere.data.vertices))), 1.0, 'REPLACE')
sphere.jewel_pave.diameter = 1.2
sphere.jewel_pave.gap = 0.12
sphere.jewel_pave.offset = -0.15
sphere_output = rebuild(bpy.context, sphere)
values = centers(sphere_output)
assert len(values) >= 190, len(values)
assert min(v.z for v in values) < -5 and max(v.z for v in values) > 5
assert all(5.80 < v.length < 5.86 for v in values)
validate_spacing(sphere_output)
for matrix in instance_matrices(sphere_output):
    assert (matrix.to_3x3() @ Vector((0, 0, 1))).dot(matrix.translation.normalized()) > 0.999
print('PAVE_SPHERE', len(values))

# Concave normals and positive seating offsets still keep the complete gem
# envelopes apart. This catches spacing checked only at the surface points.
for polygon in sphere.data.polygons:
    polygon.flip()
sphere.data.update()
sphere.jewel_pave.offset = 0.25
concave_output = rebuild(bpy.context, sphere)
assert all(5.70 < v.length < 5.76 for v in centers(concave_output))
validate_spacing(concave_output)
for matrix in instance_matrices(concave_output):
    assert (matrix.to_3x3() @ Vector((0, 0, 1))).dot(matrix.translation.normalized()) < -0.999
print('PAVE_CONCAVE', concave_output['stone_count'])

# Normalize a custom source without editing its mesh, transforms or metadata.
bpy.ops.object.select_all(action='DESELECT')
assert bpy.ops.mesh.parametric_gem_add(cut='ROUND', length_mm=3, width_mm=3, stone='RUBY') == {'FINISHED'}
source = bpy.context.object
source.location = (30, 20, 10)
source.rotation_euler = (0.3, 0.4, 0.7)
source.scale = (2, 2, 2)
for vertex in source.data.vertices:
    vertex.co += Vector((2, -1, 5))
source.data.update()
bpy.context.view_layer.update()
source_coords = [tuple(v.co) for v in source.data.vertices]
source_matrix = source.matrix_world.copy()
hole.jewel_pave.gem = source
custom_output = rebuild(bpy.context, hole)
assert [tuple(v.co) for v in source.data.vertices] == source_coords
bpy.context.view_layer.update()
assert source.matrix_world == source_matrix
assert tuple(source.location) == (30, 20, 10)
assert tuple(source.scale) == (2, 2, 2)
template = custom_output['pave_template']
assert template['gem']['stone'] == 'RUBY'
assert abs(template.dimensions.x - 1.0) < 1e-5
assert abs(template.dimensions.y - 1.0) < 1e-5
validate_spacing(custom_output)
print('PAVE_CUSTOM_SOURCE', custom_output['stone_count'])

# Mask writes must not modify another object sharing the source mesh.
shared = plane.copy()
bpy.context.collection.objects.link(shared)
shared.jewel_pave.output = None
bpy.context.scene.jewel_pave_surface = shared
original_mesh = plane.data
assert bpy.ops.object.pave_mask(action='CLEAR') == {'FINISHED'}
assert shared.data != original_mesh and plane.data == original_mesh
assert all(plane.vertex_groups[MASK_NAME].weight(v.index) == 1.0 for v in plane.data.vertices)
assert bpy.ops.object.pave_mask(action='FILL') == {'FINISHED'}
assert all(shared.vertex_groups[MASK_NAME].weight(v.index) == 1.0 for v in shared.data.vertices)

# Exercise the panel's real VIEW_3D context, including its active brush tool.
area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
region = next(region for region in area.regions if region.type == 'WINDOW')
with bpy.context.temp_override(area=area, region=region):
    assert bpy.ops.object.pave_mask(action='PAINT') == {'FINISHED'}
    assert bpy.context.workspace.tools.from_space_view3d_mode('PAINT_WEIGHT').idname == 'builtin.brush'
    assert bpy.ops.object.pave_mask(action='DONE') == {'FINISHED'}

# A valid empty layout must replace the previous gems, rather than leave a
# stale layout visible outside the current mask.
counts = (len(bpy.data.objects), len(bpy.data.meshes), len(bpy.data.node_groups))
plane.jewel_pave.diameter = 100.0
assert rebuild(bpy.context, plane) == output
assert output['stone_count'] == 0 and len(output.data.vertices) == 0
assert not instance_matrices(output)
assert counts == (len(bpy.data.objects), len(bpy.data.meshes), len(bpy.data.node_groups))
plane.jewel_pave.diameter = 1.0
assert rebuild(bpy.context, plane)['stone_count'] == len(first)
plane.vertex_groups[MASK_NAME].add(list(range(len(plane.data.vertices))), 0.0, 'REPLACE')
plane.data.update()
assert rebuild(bpy.context, plane) == output
assert output['stone_count'] == 0 and not instance_matrices(output)
assert counts == (len(bpy.data.objects), len(bpy.data.meshes), len(bpy.data.node_groups))

# Invalid sources preserve the previous result and do not leak data blocks.
# A square mesh must not be silently labelled and packed as a round diamond.
hole.jewel_pave.gem = plane
previous_custom_mesh = custom_output.data
try:
    rebuild(bpy.context, hole)
except ValueError as error:
    assert 'circular girdle' in str(error)
else:
    raise AssertionError('A non-round custom source must be rejected')
assert custom_output.data == previous_custom_mesh
assert counts == (len(bpy.data.objects), len(bpy.data.meshes), len(bpy.data.node_groups))

sphere.jewel_pave.max_stones = 12
limited = rebuild(bpy.context, sphere)
assert limited['stone_count'] == 12 and limited['limit_reached']
jewelry_suite.unregister()
jewelry_suite.register()
assert hasattr(bpy.types, 'VIEW3D_PT_surface_pave')
jewelry_suite.unregister()
print('SURFACE_PAVE_TEST_PASSED', round(time.monotonic() - started, 2), 'seconds')
