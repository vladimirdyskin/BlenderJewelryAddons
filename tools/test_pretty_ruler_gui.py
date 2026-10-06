# GUI-тест живых размеров Pretty Ruler: Shift-линейка Measure -> Link to Geometry ->
# правка меша в Edit Mode -> скриншот. Только с окном и симуляцией событий:
#   BLENDER_USER_RESOURCES=<tmp>/5.2 Blender --factory-startup --enable-event-simulate \
#       --python tools/test_pretty_ruler_gui.py -- <out_dir>
from __future__ import annotations

import json
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
            finish(0)
    except Exception as exc:
        log["errors"].append("step %d: %r" % (s, exc))
        finish(1)
    return 0.5


bpy.app.timers.register(step, first_interval=2.0)
