# SPDX-License-Identifier: GPL-3.0-or-later

"""Use --factory-startup --enable-event-simulate; this test closes its own window."""

from pathlib import Path
import sys
import traceback

import bpy
from bpy_extras.view3d_utils import location_3d_to_region_2d
from mathutils import Quaternion, Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import jewelry_suite

assert not bpy.app.background, 'This test requires a real viewport'
jewelry_suite.register()
step = 0
saved_ids = set()
first_ids = set()


def snapshot():
    surface = bpy.data.objects['Live Brush Surface']
    output = surface.jewel_pave.output
    ids = {i for i, value in enumerate(output.data.attributes['pave_visible'].data) if value.value}
    return surface, output, ids


def mouse(window, region, space, x, event='MOUSEMOVE', value='NOTHING'):
    point = location_3d_to_region_2d(region, space.region_3d, Vector((x, 0, 0)))
    window.event_simulate(type=event, value=value,
                          x=round(region.x + point.x), y=round(region.y + point.y))


def run():
    global step, saved_ids, first_ids
    try:
        window = bpy.context.window_manager.windows[0]
        area = next(a for a in window.screen.areas if a.type == 'VIEW_3D')
        region = next(r for r in area.regions if r.type == 'WINDOW')
        space = area.spaces.active
        with bpy.context.temp_override(window=window, area=area, region=region):
            if step == 0:
                bpy.ops.object.select_all(action='SELECT')
                bpy.ops.object.delete(use_global=False)
                bpy.ops.mesh.primitive_grid_add(x_subdivisions=64, y_subdivisions=64, size=12)
                surface = bpy.context.object
                surface.name = 'Live Brush Surface'
                surface.jewel_pave.diameter = 0.8
                surface.jewel_pave.gap = 0.1
                surface.jewel_pave.border = 0.08
                bpy.context.scene.jewel_pave_surface = surface
                space.region_3d.view_rotation = Quaternion((1, 0, 0, 0))
                space.region_3d.view_perspective = 'ORTHO'
                space.region_3d.view_location = (0, 0, 0)
                space.region_3d.view_distance = 13
                space.show_region_ui = True
                bpy.ops.ed.undo_push(message='Live Pave Base')
                assert bpy.ops.object.pave_mask('EXEC_DEFAULT', True, action='PAINT') == {'FINISHED'}
                unified = bpy.context.tool_settings.weight_paint.unified_paint_settings
                unified.use_unified_size = True
                unified.size = 160
                unified.use_unified_strength = True
                unified.strength = 1.0
                space.shading.color_type = 'MATERIAL'
                for obj, name, color in (
                        (surface, 'Pave Surface Gold', (0.55, 0.33, 0.1, 1)),
                        (surface.jewel_pave.output['pave_template'], 'Pave Preview Blue', (0.1, 0.5, 0.8, 1))):
                    material = bpy.data.materials.new(name)
                    material.diffuse_color = color
                    obj.data.materials.clear()
                    obj.data.materials.append(material)
                bpy.ops.wm.save_as_mainfile(filepath='/tmp/pave-live-ui-initial.blend')
            elif step == 1:
                mouse(window, region, space, -3)
            elif step == 2:
                mouse(window, region, space, -3, 'LEFTMOUSE', 'PRESS')
                # Invoke the native modal brush, then simulate motion and release.
                assert bpy.ops.paint.weight_paint('INVOKE_DEFAULT') == {'RUNNING_MODAL'}
            elif step == 3:
                first_ids = snapshot()[2]
                mouse(window, region, space, -1)
            elif step == 4:
                mouse(window, region, space, 2)
            elif step == 5:
                surface, output, saved_ids = snapshot()
                print('UI_PAINT_WHILE_HELD', len(first_ids), len(saved_ids), output.get('pave_live_error'), flush=True)
                if not first_ids < saved_ids:
                    weights = [g.weight for v in surface.data.vertices for g in v.groups]
                    print('UI_EVENT_DIAGNOSTIC', {'window': (window.width, window.height),
                          'region': (region.x, region.y, region.width, region.height),
                          'weights': (len(weights), max(weights, default=0)),
                          'mode': surface.mode, 'dirty': jewelry_suite.pave_live._dirty,
                          'timer': bpy.app.timers.is_registered(jewelry_suite.pave_live._tick),
                          'modal': [op.bl_idname for op in window.modal_operators]}, flush=True)
                mouse(window, region, space, 2, 'LEFTMOUSE', 'RELEASE')
            elif step == 6:
                print('UI_AFTER_RELEASE', snapshot()[1]['stone_count'], flush=True)
                assert first_ids < saved_ids, 'Gems must update before the mouse button is released'
                destination = ROOT / 'dist'
                destination.mkdir(exist_ok=True)
                bpy.ops.wm.save_as_mainfile(filepath=str(destination / 'surface-pave-live-demo.blend'))
                bpy.context.scene.render.filepath = str(destination / 'surface-pave-live-viewport.png')
                bpy.context.scene.render.resolution_x = 1000
                bpy.context.scene.render.resolution_y = 800
                bpy.context.scene.render.resolution_percentage = 100
                bpy.ops.render.opengl(write_still=True, view_context=True)
                assert bpy.ops.ed.undo() == {'FINISHED'}
            elif step == 7:
                surface, output, ids = snapshot()
                print('UI_UNDO', len(ids), surface.mode, flush=True)
                assert not ids, 'Undo must remove the stroke and its live gems'
                assert bpy.ops.ed.redo() == {'FINISHED'}
            elif step == 8:
                surface, output, ids = snapshot()
                print('UI_REDO', len(ids), flush=True)
                assert ids == saved_ids, 'Redo must restore the same gem positions'
                assert bpy.ops.object.pave_mask('EXEC_DEFAULT', True, action='ERASE') == {'FINISHED'}
            elif step == 9:
                mouse(window, region, space, -3)
                mouse(window, region, space, -3, 'LEFTMOUSE', 'PRESS')
                assert bpy.ops.paint.weight_paint('INVOKE_DEFAULT') == {'RUNNING_MODAL'}
            elif step == 10:
                mouse(window, region, space, 2)
            elif step == 11:
                mouse(window, region, space, 2, 'LEFTMOUSE', 'RELEASE')
            elif step == 12:
                surface, output, ids = snapshot()
                print('UI_ERASE', len(ids), flush=True)
                assert ids < saved_ids, 'Visible gem instances must not block the erase brush'
                bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'dist/surface-pave-live-demo.blend'))
            elif step == 13:
                surface, output, ids = snapshot()
                assert ids == saved_ids
                assert bpy.app.timers.is_registered(jewelry_suite.pave_live._tick)
                surface.vertex_groups['PaveMask'].add(list(range(len(surface.data.vertices))), 0.0, 'REPLACE')
                surface.data.update()
            elif step == 14:
                surface, output, ids = snapshot()
                print('UI_RELOAD', len(ids), surface.mode, flush=True)
                assert not ids, 'Live updates must resume after loading a saved paint session'
                assert bpy.ops.object.pave_mask(action='DONE') == {'FINISHED'}
                jewelry_suite.unregister()
                print('SURFACE_PAVE_LIVE_UI_TEST_PASSED', flush=True)
                bpy.ops.wm.quit_blender()
                return None
        step += 1
        return 1.0
    except Exception:
        traceback.print_exc()
        print('SURFACE_PAVE_LIVE_UI_TEST_FAILED', step, flush=True)
        bpy.ops.wm.quit_blender()
        return None


bpy.app.timers.register(run, first_interval=2.0, persistent=True)
