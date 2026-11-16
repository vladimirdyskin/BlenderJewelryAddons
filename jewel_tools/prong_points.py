# SPDX-License-Identifier: GPL-3.0-or-later

"""
Места крапанов -> меш объекта (связка My_Stone, tools/gn_stone_setting_build.py).

У связки места крапанов — вершины без рёбер в меше самого объекта; пустой меш — места по умолчанию.
Кнопка записывает места по умолчанию в меш выделенных объектов, чтобы их двигать, а не ставить с нуля.

Откуда берутся места: вход Outline модификатора My_Stone, иначе встроенный контур «Outline <Cut>»
(вершины без рёбер, единичные координаты) * (Width, Length). Round без Outline — Count и ° Z
модификатора My_Stone_Prongs на окружности рундиста. Уже записанные точки заменяются, остальной меш
не трогается.
"""

from __future__ import annotations

import re
from math import cos, pi, sin

import bmesh
import bpy
from bpy.types import Operator

_STONE = re.compile(r"My_Stone(\.\d+)?$")
_PRONGS = re.compile(r"My_Stone_Prongs(\.\d+)?$")


def _modifier(ob: bpy.types.Object, pattern: re.Pattern):
    return next((m for m in ob.modifiers if m.type == "NODES" and m.node_group and pattern.match(m.node_group.name)),
                None)


def _value(md, name: str):
    item = next((it for it in md.node_group.interface.items_tree
                 if it.item_type == "SOCKET" and it.in_out == "INPUT" and it.name == name), None)
    return getattr(md.properties.inputs, item.identifier).value if item else None


def default_points(ob: bpy.types.Object) -> list[tuple[float, float]] | None:
    """Места крапанов по умолчанию в мм, в координатах объекта. None — контур огранки не найден."""
    md = _modifier(ob, _STONE)
    cut = _value(md, "Cut") or "Round"
    width = _value(md, "Width")
    length = width if cut == "Round" else _value(md, "Length")
    outline = _value(md, "Outline")
    if outline is None and cut == "Round":
        prongs = _modifier(ob, _PRONGS)
        count = _value(prongs, "Count") if prongs else 4
        angle = _value(prongs, "° Z") if prongs else pi / 4
        return [(0.5 * width * cos(angle + 2 * pi * k / count), 0.5 * width * sin(angle + 2 * pi * k / count))
                for k in range(count)]
    outline = outline or bpy.data.objects.get("Outline " + cut)
    if outline is None or outline.type != "MESH":
        return None
    mesh = outline.data
    used = {v for e in mesh.edges for v in e.vertices}
    return [(v.co.x * width, v.co.y * length) for v in mesh.vertices if v.index not in used]


def write_points(ob: bpy.types.Object, points: list[tuple[float, float]]) -> None:
    """Вершины без рёбер меша заменить на points (z = 0)."""
    mesh = ob.data
    edit = ob.mode == "EDIT"
    bm = bmesh.from_edit_mesh(mesh) if edit else bmesh.new()
    if not edit:
        bm.from_mesh(mesh)
    for v in [v for v in bm.verts if not v.link_edges]:
        bm.verts.remove(v)
    for x, y in points:
        bm.verts.new((x, y, 0.0))
    if edit:
        bmesh.update_edit_mesh(mesh)
    else:
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()


class OBJECT_OT_prong_points_to_mesh(Operator):
    bl_idname = "object.prong_points_to_mesh"
    bl_label = "Prong Points to Mesh"
    bl_description = ("Write the default prong places of the stone setting (My_Stone) into the object's own "
                      "mesh as loose vertices, ready to be moved, added or deleted")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return any(o.type == "MESH" and _modifier(o, _STONE) for o in context.selected_objects)

    def execute(self, context: bpy.types.Context):
        done = 0
        for ob in context.selected_objects:
            if ob.type != "MESH" or _modifier(ob, _STONE) is None:
                continue
            points = default_points(ob)
            if points is None:
                self.report({"WARNING"}, "%s: outline of the cut not found" % ob.name)
                continue
            write_points(ob, points)
            done += 1
            print("Prong points: %s, %d" % (ob.name, len(points)))
        if not done:
            return {"CANCELLED"}
        self.report({"INFO"}, "Prong points written: %d object(s)" % done)
        return {"FINISHED"}


_CLASSES = (OBJECT_OT_prong_points_to_mesh,)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
