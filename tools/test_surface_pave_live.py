# SPDX-License-Identifier: GPL-3.0-or-later

"""Check live selection, mask boundaries, stable instances and lifecycle cleanup."""

from pathlib import Path
import sys
from time import perf_counter

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jewelry_suite
from jewelry_suite import pave_live
from jewelry_suite.pave_layout import MASK_NAME


def set_mask(surface, function):
    group = surface.vertex_groups[MASK_NAME]
    for vertex in surface.data.vertices:
        group.add([vertex.index], function(vertex.co), 'REPLACE')
    surface.data.update()
    bpy.context.view_layer.update()


def visible_ids(output):
    return {i for i, value in enumerate(output.data.attributes['pave_visible'].data) if value.value}


def instance_states(output):
    bpy.context.view_layer.update()
    return {tuple(instance.persistent_id): tuple(tuple(row) for row in instance.matrix_world)
            for instance in bpy.context.evaluated_depsgraph_get().object_instances
            if instance.is_instance and instance.parent.original == output}


def tick():
    assert pave_live._dirty, 'The depsgraph handler must detect mask changes'
    assert pave_live._tick() is not None
    assert not pave_live._dirty


started = perf_counter()
jewelry_suite.register()
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_grid_add(x_subdivisions=49, y_subdivisions=49, size=12)
surface = bpy.context.object
surface.name = 'Live Pave Test'
surface.jewel_pave.diameter = 1.0
surface.jewel_pave.gap = 0.1
surface.jewel_pave.border = 0.1
bpy.context.scene.jewel_pave_surface = surface
assert surface.jewel_pave.live_preview

area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
region = next(region for region in area.regions if region.type == 'WINDOW')
area.spaces.active.overlay.weight_paint_mode_opacity = 0.7
with bpy.context.temp_override(area=area, region=region):
    assert bpy.ops.object.pave_mask(action='PAINT') == {'FINISHED'}
output = surface.jewel_pave.output
assert output['candidate_count'] > 80
assert output['stone_count'] == 0
assert not output.hide_get() and output.hide_select
assert surface.mode == 'WEIGHT_PAINT'
assert area.spaces.active.overlay.weight_paint_mode_opacity == 0.0
assert bpy.app.timers.is_registered(pave_live._tick)

points = output.data
group = next(m.node_group for m in output.modifiers if m.type == 'NODES')
template = output['pave_template']
positions = [tuple(v.co) for v in points.vertices]
data_counts = (len(bpy.data.objects), len(bpy.data.meshes), len(bpy.data.node_groups))

# Grow the painted half-plane. Both visible point indices and evaluated
# Geometry Nodes instance IDs must remain unchanged for existing gems.
previous = set()
previous_instances = {}
for boundary in (-3.0, 0.0, 3.0):
    set_mask(surface, lambda p: min(1.0, max(0.0, boundary - p.x + 0.5)))
    tick()
    current = visible_ids(output)
    assert previous <= current and len(current) > len(previous)
    assert all(points.vertices[i].co.x <= boundary - 0.6 + 1e-5 for i in current)
    instances = instance_states(output)
    assert len(instances) == len(current) == output['stone_count']
    assert all(instances.get(key) == value for key, value in previous_instances.items())
    previous, previous_instances = current, instances
    assert [tuple(v.co) for v in points.vertices] == positions
    assert output.data == points and output['pave_template'] == template
    assert data_counts == (len(bpy.data.objects), len(bpy.data.meshes), len(bpy.data.node_groups))
print('LIVE_GROWTH', len(previous), 'visible of', len(positions))

# Erase a small hole inside the region, then restore it with the same IDs.
set_mask(surface, lambda p: 0.0 if abs(p.x) < 0.3 and abs(p.y) < 0.3 else min(1.0, max(0.0, 3.5 - p.x)))
tick()
erased = visible_ids(output)
assert erased < previous
assert all(points.vertices[i].co.length > 0.85 for i in erased)
set_mask(surface, lambda p: min(1.0, max(0.0, 3.5 - p.x)))
tick()
assert visible_ids(output) == previous
assert instance_states(output) == previous_instances

# Switching the brush preserves the prepared mesh and restores user overlays.
assert bpy.ops.object.pave_mask(action='ERASE') == {'FINISHED'}
assert output.data == points
assert bpy.context.tool_settings.weight_paint.unified_paint_settings.weight == 0.0
surface.jewel_pave.show_mask = True
assert abs(area.spaces.active.overlay.weight_paint_mode_opacity - 0.7) < 1e-5
surface.jewel_pave.show_mask = False
assert area.spaces.active.overlay.weight_paint_mode_opacity == 0.0
assert bpy.ops.object.pave_mask(action='DONE') == {'FINISHED'}
assert not bpy.app.timers.is_registered(pave_live._tick)
assert not output.hide_get() and not output.hide_select
assert abs(area.spaces.active.overlay.weight_paint_mode_opacity - 0.7) < 1e-5
assert output.data == points

# Fill/Clear updates the preview immediately, including an empty valid mask.
assert bpy.ops.object.pave_mask(action='CLEAR') == {'FINISHED'}
assert output['stone_count'] == 0 and not instance_states(output)
assert output.data == points
assert bpy.ops.object.pave_mask(action='FILL') == {'FINISHED'}
assert output['stone_count'] == output['candidate_count']
assert output.data == points

# Manual mode exit flushes the final stroke and stops the timer.
assert bpy.ops.object.pave_mask(action='PAINT') == {'FINISHED'}
set_mask(surface, lambda p: 0.0)
bpy.ops.object.mode_set(mode='OBJECT')
assert pave_live._tick() is None
pave_live.stop()
assert not surface.jewel_pave.paint_state
assert output['stone_count'] == 0
assert not output.hide_get()

# A geometry edit cannot silently reuse old positions. Preparing again rebuilds.
surface.data.vertices[0].co.z += 0.2
surface.data.update()
try:
    pave_live.refresh(bpy.context, surface)
except ValueError as error:
    assert 'Surface changed' in str(error)
else:
    raise AssertionError('Geometry changes must invalidate the live layout')
assert bpy.ops.object.pave_refresh_live() == {'FINISHED'}
assert surface.jewel_pave.output['pave_live_error'] == ''

# The original packing remains an explicit operation, followed by live prepare.
assert bpy.ops.object.pave_mask(action='FILL') == {'FINISHED'}
assert bpy.ops.object.pave_build() == {'FINISHED'}
assert surface.jewel_pave.output['pave_layout_mode'] == 'PACKED'
assert bpy.ops.object.pave_mask(action='PAINT') == {'FINISHED'}
assert surface.jewel_pave.output['pave_layout_mode'] == 'LIVE'
assert surface.mode == 'WEIGHT_PAINT'
assert bpy.ops.object.pave_mask(action='DONE') == {'FINISHED'}

# A subdivided, transformed sphere keeps its evaluated surface and fixed slots
# when the control-mesh weights change in Weight Paint mode.
bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=4)
sphere = bpy.context.object
sphere.name = 'Live Curved Surface'
for polygon in sphere.data.polygons:
    polygon.use_smooth = True
modifier = sphere.modifiers.new('Smooth Surface', 'SUBSURF')
modifier.levels = 1
sphere.matrix_world = Matrix.Translation((10, -3, 2)) @ Matrix.Rotation(0.4, 4, 'Y') @ Matrix.Diagonal((1.2, 0.8, 1.0, 1.0))
sphere.jewel_pave.diameter = 1.0
bpy.context.scene.jewel_pave_surface = sphere
assert bpy.ops.object.pave_mask(action='FILL') == {'FINISHED'}
sphere_output = sphere.jewel_pave.output
sphere_points = sphere_output.data
assert bpy.ops.object.pave_mask(action='PAINT') == {'FINISHED'}
assert sphere_output.data == sphere_points
set_mask(sphere, lambda p: min(1.0, max(0.0, p.z + 0.5)))
tick()
assert 10 < sphere_output['stone_count'] < sphere_output['candidate_count']
before = instance_states(sphere_output)
assert bpy.ops.object.pave_mask(action='ERASE') == {'FINISHED'}
assert sphere_output.data == sphere_points
assert instance_states(sphere_output) == before
print('LIVE_CURVED_SURFACE', sphere_output['stone_count'], 'visible')
jewelry_suite.unregister()
assert not bpy.app.timers.is_registered(pave_live._tick)
assert all(callback not in handlers for handlers, callback in pave_live._HANDLERS)
jewelry_suite.register()
assert all(list(handlers).count(callback) == 1 for handlers, callback in pave_live._HANDLERS)
jewelry_suite.unregister()
print('SURFACE_PAVE_LIVE_TEST_PASSED', round(perf_counter() - started, 2), 'seconds')
