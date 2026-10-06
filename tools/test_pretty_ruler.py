from __future__ import annotations

from pathlib import Path
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jewelry_suite
from jewelry_suite import pretty_ruler as pr


def pts(*points: tuple[float, float, float]) -> list[str]:
    return pr._stroke_key(points).split(";")


A = pts((0, 0, 0), (1, 0, 0))
B = pts((0, 1, 0), (1, 1, 0))
C = pts((0, 2, 0), (1, 2, 0))
B_MOVED = pts((0, 1, 0), (3, 1, 0))
ANGLE = pts((0, 0, 0), (0, 0, 1), (1, 0, 1))

# Удаление линейки: флаги остальных не съезжают
assert pr._match_flags([(A, True), (B, False), (C, True)], [A, C]) == [True, True]
assert pr._match_flags([(A, True), (B, False), (C, True)], [B, C]) == [False, True]
# Перетащили один конец: флаг остаётся
assert pr._match_flags([(A, True), (B, False)], [A, B_MOVED]) == [True, False]
# Новая линейка включена; угол не сопоставляется с размером по общей точке
assert pr._match_flags([(A, False)], [A, C]) == [False, True]
assert pr._match_flags([(A, False)], [ANGLE]) == [True]
# Одинаковые линейки разбираются по одной
assert pr._match_flags([(A, False), (A, True)], [A, A]) == [False, True]

jewelry_suite.register()
assert pr._handle is not None, "draw handler must be active right after register"
assert bpy.app.timers.is_registered(pr._sync_timer)

props = bpy.context.scene.pretty_ruler
props.enabled = False
assert pr.draw_callback() is None  # выключено — выходит до обращения к региону
props.enabled = True
assert len(props.items) == len(pr.get_ruler_strokes())


# --- Живые размеры на кубе 2x2x2 ---------------------------------------------
def length(link) -> float:
    pts = pr.link_points(link, {})
    assert pts is not None, "link lost"
    return (pts[1] - pts[0]).length


def close(a: float, b: float) -> bool:
    return abs(a - b) < 1e-5


mesh = bpy.data.meshes.new("Wall")
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=2.0)
bm.to_mesh(mesh)
bm.free()
wall = bpy.data.objects.new("Wall", mesh)
bpy.context.collection.objects.link(wall)
wall.location = (10.0, 0.0, 0.0)
bpy.context.view_layer.update()
objects = [wall]
off = Vector((10.0, 0.0, 0.0))

# Shift-линейка между гранями +X и -X -> толщина; линейка по вершинам -> расстояние
thick = pr.add_link(props, off + Vector((1, 0.2, 0.3)), off + Vector((-1, 0.2, 0.3)), objects)
dist = pr.add_link(props, off + Vector((1, 1, 1)), off + Vector((-1, -1, -1)), objects)
assert thick.kind == 'THICK' and dist.kind == 'DIST'
assert close(length(thick), 2.0) and close(length(dist), 12 ** 0.5)
assert pr.add_link(props, off + Vector((5, 5, 5)), off, objects) is None  # точка не на грани

# Object Mode: грань +X наружу на 0.5, грань -X вбок по Y — толщина 2.5 и не зависит от сдвига
for v in mesh.vertices:
    if v.co.x > 0:
        v.co.x += 0.5
    else:
        v.co.y += 0.3
assert close(length(thick), 2.5)
assert not close(length(dist), 12 ** 0.5)
wall.scale.x = 2.0
bpy.context.view_layer.update()
assert close(length(thick), 5.0)

# Edit Mode: размер читает живой BMesh без выхода из режима
bpy.context.view_layer.objects.active = wall
wall.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
bm = bmesh.from_edit_mesh(mesh)
for v in bm.verts:
    if v.co.x > 0:
        v.co.x += 0.5
bmesh.update_edit_mesh(mesh)
assert close(length(thick), 6.0)

# Смена топологии: удаляем грань -X — привязка помечается потерянной
bm.faces.ensure_lookup_table()
face_b = bm.faces[thick.face_b]
bmesh.ops.delete(bm, geom=[face_b], context='FACES_ONLY')
bmesh.update_edit_mesh(mesh)
assert pr.link_points(thick, {}) is None
bpy.ops.object.mode_set(mode='OBJECT')

recolored = pr._Recolor(props, props.link_color)
assert tuple(recolored.text_color) == tuple(props.link_color)
assert recolored.font_size == props.font_size

jewelry_suite.unregister()
assert pr._handle is None
assert not bpy.app.timers.is_registered(pr._sync_timer)

print("PRETTY_RULER_TEST", {"match_flags": "ok", "handler": "ok", "timer": "ok", "linked": "ok"})
