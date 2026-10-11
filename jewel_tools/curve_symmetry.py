# SPDX-License-Identifier: GPL-3.0-or-later
# Symmetrize Curve: зеркалит одну сторону Bezier-кривой на другую (как Symmetrize у мешей).
# Переносятся позиции и типы ручек, радиус и наклон; точки у оси встают ровно на ось,
# их ручки становятся зеркальными. Плоскость симметрии — локальная плоскость объекта.
#
# Tilt переносится с тем же знаком: при зеркале направление обхода меняется, и только так
# нормали кривой в Geometry Nodes получаются зеркальными (проверено замером, все twist mode).

from __future__ import annotations

import math

import bpy
from bpy.props import EnumProperty, FloatProperty
from bpy.types import Operator
from mathutils import Vector


_AXES = {"X": 0, "Y": 1, "Z": 2}


def _flip(v: Vector, k: int) -> Vector:
    v = v.copy()
    v[k] = -v[k]
    return v


def _read(p: bpy.types.BezierSplinePoint) -> dict:
    return {
        "co": p.co.copy(), "hl": p.handle_left.copy(), "hr": p.handle_right.copy(),
        "tl": p.handle_left_type, "tr": p.handle_right_type,
        "radius": p.radius, "tilt": p.tilt, "weight": p.weight_softbody, "hide": p.hide,
        "sel": p.select_control_point, "sl": p.select_left_handle, "sr": p.select_right_handle,
    }


def _write(p: bpy.types.BezierSplinePoint, d: dict) -> None:
    # типы ручек раньше позиций: смена типа пересчитывает ручки
    p.handle_left_type, p.handle_right_type = d["tl"], d["tr"]
    p.co = d["co"]
    p.handle_left = d["hl"]
    p.handle_right = d["hr"]
    p.radius, p.tilt, p.weight_softbody, p.hide = d["radius"], d["tilt"], d["weight"], d["hide"]
    p.select_control_point, p.select_left_handle, p.select_right_handle = d["sel"], d["sl"], d["sr"]


def _mirrored(d: dict, k: int) -> dict:
    """Зеркальный двойник точки: обход идёт в обратную сторону, поэтому ручки меняются местами."""
    return {**d, "co": _flip(d["co"], k), "hl": _flip(d["hr"], k), "hr": _flip(d["hl"], k),
            "tl": d["tr"], "tr": d["tl"], "sl": d["sr"], "sr": d["sl"]}


def _on_axis(d: dict, k: int, master_right: bool) -> dict:
    """Точка на оси; ручка второй половины — зеркало ручки, смотрящей в мастер-сторону.
    Гладкая точка (ALIGNED) без излома симметрична, только если ручки идут поперёк
    плоскости — выравниваем их по оси, длину сохраняем. Острая (FREE) — зеркалим как есть."""
    shift = -d["co"][k]
    co = d["co"].copy()
    co[k] = 0.0
    master = (d["hr"] if master_right else d["hl"]).copy()
    master[k] += shift
    kind = d["tr"] if master_right else d["tl"]
    offset = master - co
    if kind == "ALIGNED":
        if abs(offset[k]) > 1e-9:
            master = co.copy()
            master[k] = math.copysign(offset.length, offset[k])
        else:
            kind = "FREE"  # ручка вдоль плоскости — гладко не получится, остаётся носик
    hl, hr = (_flip(master, k), master) if master_right else (master, _flip(master, k))
    return {**d, "co": co, "hl": hl, "hr": hr, "tl": kind, "tr": kind}


def _rotate(points: list, start: int) -> list:
    """Сдвиг циклического списка: элемент 0 встаёт на позицию start."""
    start %= len(points)
    return points[-start:] + points[:-start] if start else points


def symmetrize_points(points: list[dict], cyclic: bool, k: int, sign: float, threshold: float) -> list[dict] | None:
    """Новый список точек сплайна или None, если форма не поддерживается:
    замкнутый — ровно 2 точки на оси, открытый — ровно 1."""
    side = [0 if abs(d["co"][k]) <= threshold else (1 if d["co"][k] * sign > 0 else -1) for d in points]
    axis = [i for i, s in enumerate(side) if s == 0]
    n = len(points)
    mirror = lambda run: [_mirrored(points[i], k) for i in reversed(run)]
    keep = lambda run: [points[i] for i in run]
    if cyclic:
        if len(axis) != 2:
            return None
        a0, a1 = axis
        run1 = list(range(a0 + 1, a1))
        run2 = [i % n for i in range(a1 + 1, a0 + n)]
        s1, s2 = {side[i] for i in run1}, {side[i] for i in run2}
        # список собирается от точки a0; поворот возвращает начало сплайна на прежнее место
        if s1 <= {1} and s2 <= {-1}:
            return _rotate([_on_axis(points[a0], k, True)] + keep(run1)
                           + [_on_axis(points[a1], k, False)] + mirror(run1), a0)
        if s2 <= {1} and s1 <= {-1}:
            return _rotate([_on_axis(points[a0], k, False)] + mirror(run2)
                           + [_on_axis(points[a1], k, True)] + keep(run2), a0)
        return None
    if len(axis) != 1:
        return None
    a = axis[0]
    before, after = list(range(a)), list(range(a + 1, n))
    sb, sa = {side[i] for i in before}, {side[i] for i in after}
    if sa <= {1} and sb <= {-1}:
        return mirror(after) + [_on_axis(points[a], k, True)] + keep(after)
    if sb <= {1} and sa <= {-1}:
        return keep(before) + [_on_axis(points[a], k, False)] + mirror(before)
    return None


def symmetrize_curve(curve: bpy.types.Curve, axis: str = "X", direction: str = "POSITIVE",
                     threshold: float = 0.1) -> tuple[int, int]:
    """Симметризует все Bezier-сплайны кривой. Возвращает (сделано, пропущено)."""
    k = _AXES[axis]
    sign = 1.0 if direction == "POSITIVE" else -1.0
    done = skipped = 0
    for spline in list(curve.splines):
        if spline.type != "BEZIER":
            continue
        new = symmetrize_points([_read(p) for p in spline.bezier_points], spline.use_cyclic_u, k, sign, threshold)
        if new is None:
            skipped += 1
            continue
        if len(new) == len(spline.bezier_points):
            for p, d in zip(spline.bezier_points, new):
                _write(p, d)
        else:
            # число точек изменилось — пересобираем сплайн (он встанет в конец списка)
            rebuilt = curve.splines.new("BEZIER")
            rebuilt.bezier_points.add(len(new) - 1)
            for attr in ("use_cyclic_u", "resolution_u", "tilt_interpolation", "radius_interpolation",
                         "use_smooth", "material_index", "hide"):
                setattr(rebuilt, attr, getattr(spline, attr))
            for p, d in zip(rebuilt.bezier_points, new):
                _write(p, d)
            curve.splines.remove(spline)
        done += 1
    curve.update_tag()
    return done, skipped


class CURVE_OT_symmetrize_bezier(Operator):
    bl_idname = "curve.symmetrize_bezier"
    bl_label = "Symmetrize Curve"
    bl_description = ("Mirror one side of the Bezier curve onto the other: handles, radius and tilt. "
                      "Points near the axis snap onto it with mirrored handles")
    bl_options = {"REGISTER", "UNDO"}

    axis: EnumProperty(name="Axis", items=[("X", "X", ""), ("Y", "Y", ""), ("Z", "Z", "")], default="X")
    direction: EnumProperty(
        name="Direction",
        items=[("POSITIVE", "+ to -", "Copy the positive side onto the negative side"),
               ("NEGATIVE", "- to +", "Copy the negative side onto the positive side")],
        default="POSITIVE",
    )
    threshold: FloatProperty(
        name="Axis Threshold", description="Points closer to the axis than this snap onto it",
        default=0.1, min=0.0, soft_max=1.0, subtype="DISTANCE",
    )

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return context.object is not None and context.object.type == "CURVE"

    def execute(self, context: bpy.types.Context):
        done, skipped = symmetrize_curve(context.object.data, self.axis, self.direction, self.threshold)
        if not done:
            self.report({"WARNING"}, "No spline crosses the axis: a closed spline needs 2 points "
                                     "near the axis, an open one needs 1")
            return {"CANCELLED"}
        if skipped:
            self.report({"WARNING"}, "Symmetrized %d spline(s), skipped %d" % (done, skipped))
        return {"FINISHED"}


_CLASSES = (CURVE_OT_symmetrize_bezier,)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
