# GUI-тест Pretty Ruler: Shift-линейка Measure -> Link to Geometry -> правка меша в Edit Mode;
# затем линейка по Empty-картинке -> Calibrate. Скриншоты в <out_dir>. Только с окном и симуляцией событий:
#   BLENDER_USER_RESOURCES=<tmp>/5.2 Blender --factory-startup --enable-event-simulate \
#       --python tools/test_pretty_ruler_gui.py -- <out_dir>
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import sys

import bmesh
import bpy
from bpy_extras import view3d_utils
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jewelry_suite
from jewelry_suite import pretty_ruler as pr

OUT = Path(sys.argv[-1])
OUT.mkdir(parents=True, exist_ok=True)
log: dict = {"errors": []}
state = {"step": 0}


def view3d():
    win = bpy.context.window_manager.windows[0]
    area = max((a for a in win.screen.areas if a.type == 'VIEW_3D'), key=lambda a: a.width * a.height)
    region = next(r for r in area.regions if r.type == 'WINDOW')
    return win, area, region


def finish(code: int) -> None:
    (OUT / "result.json").write_text(json.dumps(log, indent=1, default=str))
    os._exit(code)


def step():
    s = state["step"]
    state["step"] += 1
    win, area, region = view3d()
    ctx = dict(window=win, area=area, region=region)
    props = bpy.context.scene.pretty_ruler if hasattr(bpy.types.Scene, "pretty_ruler") else None
    try:
        if s == 0:
            # закрыть заставку Quick Setup — она перехватывает события
            win.event_simulate(type='ESC', value='PRESS')
            win.event_simulate(type='ESC', value='RELEASE')
            jewelry_suite.register()
            cube = bpy.data.objects["Cube"]
            cube.select_set(True)
            bpy.context.view_layer.objects.active = cube
            with bpy.context.temp_override(**ctx):
                bpy.ops.view3d.view_axis(type='FRONT')
                bpy.ops.view3d.view_selected()
                bpy.ops.wm.tool_set_by_id(name="builtin.measure")
            area.spaces.active.overlay.show_floor = False
            bpy.context.scene.pretty_ruler.enabled = True
        elif s == 1:
            rv3d = area.spaces.active.region_3d
            p = view3d_utils.location_3d_to_region_2d(region, rv3d, Vector((0.3, -1.0, 0.2)))
            state["xy"] = (region.x + int(p.x), region.y + int(p.y))
            x, y = state["xy"]
            win.event_simulate(type='MOUSEMOVE', value='NOTHING', x=x, y=y)
        elif s == 2:
            # перетаскивание начинается без Shift (иначе не срабатывает клавиша Measure)
            x, y = state["xy"]
            win.event_simulate(type='LEFTMOUSE', value='PRESS', x=x, y=y)
            for dx in (4, 8, 12):
                win.event_simulate(type='MOUSEMOVE', value='NOTHING', x=x + dx, y=y)
        elif s == 3:
            # Shift во время перетаскивания -> толщина между гранями
            x, y = state["xy"]
            win.event_simulate(type='LEFT_SHIFT', value='PRESS', x=x + 12, y=y)
            for dx in (16, 20, 24):
                win.event_simulate(type='MOUSEMOVE', value='NOTHING', x=x + dx, y=y, shift=True)
        elif s == 4:
            x, y = state["xy"]
            win.event_simulate(type='LEFTMOUSE', value='RELEASE', x=x + 24, y=y, shift=True)
            win.event_simulate(type='LEFT_SHIFT', value='RELEASE', x=x + 24, y=y)
        elif s == 5:
            log["native"] = [[tuple(round(c, 4) for c in p) for p in pts] for pts in pr.get_ruler_strokes()]
            with bpy.context.temp_override(**ctx):
                log["link_op"] = list(bpy.ops.pretty_ruler.link())
            log["links"] = [(l.kind, round((lambda q: (q[1] - q[0]).length)(pr.link_points(l, {})), 4)) for l in props.links]
            log["native_after_link"] = len(pr.get_ruler_strokes())
            with bpy.context.temp_override(**ctx):
                bpy.ops.screen.screenshot_area(filepath=str(OUT / "before.png"))
            area.spaces.active.show_region_ui = True
        elif s == 6:
            with bpy.context.temp_override(**ctx):
                bpy.ops.object.mode_set(mode='EDIT')
            cube = bpy.data.objects["Cube"]
            bm = bmesh.from_edit_mesh(cube.data)
            for v in bm.verts:
                if v.co.y > 0:
                    v.co.y += 0.75  # задняя стенка назад -> толщина 2.75
            bmesh.update_edit_mesh(cube.data)
            next(r for r in area.regions if r.type == 'UI').active_panel_category = "Jewelry"
            area.tag_redraw()
        elif s == 7:
            ui = next(r for r in area.regions if r.type == 'UI')
            with bpy.context.temp_override(window=win, area=area, region=ui):
                for _ in range(2):
                    bpy.ops.view2d.scroll_down(page=True)
            log["links_after_edit"] = [round((lambda q: (q[1] - q[0]).length)(pr.link_points(l, {})), 4) for l in props.links]
            with bpy.context.temp_override(**ctx):
                bpy.ops.screen.screenshot_area(filepath=str(OUT / "after.png"))
        elif s == 8:
            # калибровка: картинка за плоскостью курсора (y = 0.5), линейка на y = 0
            with bpy.context.temp_override(**ctx):
                bpy.ops.object.mode_set(mode='OBJECT')
            bpy.data.objects["Cube"].hide_set(True)
            img = bpy.data.images.new("Ref", 64, 32)
            img.generated_type = 'UV_GRID'
            ref = bpy.data.objects.new("Ref", None)
            ref.empty_display_type = 'IMAGE'
            ref.data = img
            ref.empty_display_size = 3.0
            ref.rotation_euler = (math.pi / 2, 0.0, 0.0)
            ref.location = (0.0, 0.5, 0.0)
            bpy.context.collection.objects.link(ref)
            bpy.context.view_layer.objects.active = ref
            ref.select_set(True)
            area.spaces.active.show_region_ui = False
            with bpy.context.temp_override(**ctx):
                bpy.ops.wm.tool_set_by_id(name="builtin.measure")
        elif s == 9:
            rv3d = area.spaces.active.region_3d
            pa = view3d_utils.location_3d_to_region_2d(region, rv3d, Vector((-1.0, 0.0, 0.2)))
            pb = view3d_utils.location_3d_to_region_2d(region, rv3d, Vector((1.0, 0.0, 0.2)))
            state["a"] = (region.x + int(pa.x), region.y + int(pa.y))
            state["b"] = (region.x + int(pb.x), region.y + int(pb.y))
            win.event_simulate(type='MOUSEMOVE', value='NOTHING', x=state["a"][0], y=state["a"][1])
        elif s == 10:
            (ax, ay), (bx, by) = state["a"], state["b"]
            win.event_simulate(type='LEFTMOUSE', value='PRESS', x=ax, y=ay)
            for t in (0.25, 0.5, 0.75, 1.0):
                win.event_simulate(type='MOUSEMOVE', value='NOTHING', x=int(ax + (bx - ax) * t), y=ay)
        elif s == 11:
            bx, by = state["b"]
            win.event_simulate(type='LEFTMOUSE', value='RELEASE', x=bx, y=by)
        elif s == 12:
            ref = bpy.data.objects["Ref"]
            props.calib_length = 3.0
            log["calib_native_before"] = [round((q[1] - q[0]).length, 4) for q in pr.get_ruler_strokes()]
            with bpy.context.temp_override(**ctx):
                log["calib_op"] = list(bpy.ops.pretty_ruler.calibrate())
            log["calib_native_after"] = [[tuple(round(c, 4) for c in p) for p in q] for q in pr.get_ruler_strokes()]
            log["calib_length_after"] = [round((q[1] - q[0]).length, 4) for q in pr.get_ruler_strokes()]
            log["ref_scale"] = tuple(round(v, 4) for v in ref.scale)
            log["ref_location"] = tuple(round(v, 4) for v in ref.location)
            area.tag_redraw()
        elif s == 13:
            with bpy.context.temp_override(**ctx):
                bpy.ops.screen.screenshot_area(filepath=str(OUT / "calibrated.png"))
            finish(0)
    except Exception as exc:
        log["errors"].append("step %d: %r" % (s, exc))
        finish(1)
    return 0.5


bpy.app.timers.register(step, first_interval=2.0)
