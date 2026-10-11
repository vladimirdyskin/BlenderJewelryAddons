# SPDX-License-Identifier: GPL-3.0-or-later
# Symmetrize Curve: зеркалит одну сторону Bezier-кривой на другую (как Symmetrize у мешей).
# Переносятся позиции и типы ручек, радиус и наклон; точки у плоскости встают ровно на неё,
# их ручки становятся зеркальными. Плоскость проходит через центр мира (центр кольца),
# origin объекта или 3D-курсор.
#
# Tilt переносится с тем же знаком: при зеркале направление обхода меняется, и только так
# нормали кривой в Geometry Nodes получаются зеркальными (проверено замером, все twist mode).

from __future__ import annotations

import math

import bpy
from bpy.props import EnumProperty, FloatProperty
from bpy.types import Operator
from mathutils import Matrix, Vector


_AXES = {"X": 0, "Y": 1, "Z": 2}


class MirrorPlane:
    """Плоскость симметрии. Точки кривой локальные; matrix переводит их в пространство,
    где задана плоскость (origin, normal). Нормаль смотрит в мастер-сторону."""

    def __init__(self, matrix: Matrix, origin: Vector, normal: Vector):
        self.m = matrix
        self.mi = matrix.inverted_safe()
        self.o = Vector(origin)
        self.n = Vector(normal).normalized()

    def dist(self, v: Vector) -> float:
        return (self.m @ v - self.o).dot(self.n)

    def flip(self, v: Vector) -> Vector:
        w = self.m @ v
        return self.mi @ (w - 2.0 * (w - self.o).dot(self.n) * self.n)

    def snap(self, v: Vector) -> Vector:
        w = self.m @ v
        return self.mi @ (w - (w - self.o).dot(self.n) * self.n)

    def across(self, co: Vector, handle: Vector) -> Vector:
        """Ручка той же длины, но строго поперёк плоскости — в ту же сторону, что была."""
        a, b = self.m @ co, self.m @ handle
        offset = b - a
        return self.mi @ (a + self.n * math.copysign(offset.length, offset.dot(self.n)))


def make_plane(obj: bpy.types.Object, axis: str = "X", direction: str = "POSITIVE",
               pivot: str = "WORLD", cursor: Vector | None = None) -> MirrorPlane:
    normal = Vector((0.0, 0.0, 0.0))
    normal[_AXES[axis]] = 1.0 if direction == "POSITIVE" else -1.0
    if pivot == "OBJECT":
        return MirrorPlane(Matrix.Identity(4), Vector(), normal)
    origin = Vector(cursor) if pivot == "CURSOR" and cursor is not None else Vector()
    return MirrorPlane(obj.matrix_world, origin, normal)


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


def _mirrored(d: dict, plane: MirrorPlane) -> dict:
    """Зеркальный двойник точки: обход идёт в обратную сторону, поэтому ручки меняются местами."""
    return {**d, "co": plane.flip(d["co"]), "hl": plane.flip(d["hr"]), "hr": plane.flip(d["hl"]),
            "tl": d["tr"], "tr": d["tl"], "sl": d["sr"], "sr": d["sl"]}


def _on_axis(d: dict, plane: MirrorPlane, master_right: bool) -> dict:
    """Точка на плоскости; ручка второй половины — зеркало ручки, смотрящей в мастер-сторону.
    Гладкая точка (ALIGNED) без излома симметрична, только если ручки идут поперёк
    плоскости — выравниваем их, длину сохраняем. Острая (FREE) — зеркалим как есть."""
    co = plane.snap(d["co"])
    master = (d["hr"] if master_right else d["hl"]) + (co - d["co"])
    kind = d["tr"] if master_right else d["tl"]
    if kind == "ALIGNED":
        if abs(plane.dist(master) - plane.dist(co)) > 1e-9:
            master = plane.across(co, master)
        else:
            kind = "FREE"  # ручка вдоль плоскости — гладко не получится, остаётся носик
    hl, hr = (plane.flip(master), master) if master_right else (master, plane.flip(master))
    return {**d, "co": co, "hl": hl, "hr": hr, "tl": kind, "tr": kind}


def _rotate(points: list, start: int) -> list:
    """Сдвиг циклического списка: элемент 0 встаёт на позицию start."""
    start %= len(points)
    return points[-start:] + points[:-start] if start else points


def symmetrize_points(points: list[dict], cyclic: bool, plane: MirrorPlane, threshold: float) -> list[dict] | None:
    """Новый список точек сплайна или None, если форма не поддерживается:
    замкнутый — ровно 2 точки у плоскости, открытый — ровно 1."""
    side = []
    for d in points:
        dist = plane.dist(d["co"])
        side.append(0 if abs(dist) <= threshold else (1 if dist > 0 else -1))
    axis = [i for i, s in enumerate(side) if s == 0]
    n = len(points)
    mirror = lambda run: [_mirrored(points[i], plane) for i in reversed(run)]
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
            return _rotate([_on_axis(points[a0], plane, True)] + keep(run1)
                           + [_on_axis(points[a1], plane, False)] + mirror(run1), a0)
        if s2 <= {1} and s1 <= {-1}:
            return _rotate([_on_axis(points[a0], plane, False)] + mirror(run2)
                           + [_on_axis(points[a1], plane, True)] + keep(run2), a0)
        return None
    if len(axis) != 1:
        return None
    a = axis[0]
    before, after = list(range(a)), list(range(a + 1, n))
    sb, sa = {side[i] for i in before}, {side[i] for i in after}
    if sa <= {1} and sb <= {-1}:
        return mirror(after) + [_on_axis(points[a], plane, True)] + keep(after)
    if sb <= {1} and sa <= {-1}:
        return keep(before) + [_on_axis(points[a], plane, False)] + mirror(before)
    return None


def symmetrize_curve(curve: bpy.types.Curve, plane: MirrorPlane, threshold: float = 0.1) -> tuple[int, list[int]]:
    """Симметризует все Bezier-сплайны кривой. Возвращает (сделано, число точек у плоскости
    для каждого пропущенного сплайна)."""
    done, skipped = 0, []
    for spline in list(curve.splines):
        if spline.type != "BEZIER":
            continue
        points = [_read(p) for p in spline.bezier_points]
        new = symmetrize_points(points, spline.use_cyclic_u, plane, threshold)
        if new is None:
            skipped.append(sum(abs(plane.dist(d["co"])) <= threshold for d in points))
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


def pick_axis(obj: bpy.types.Object, direction: str = "POSITIVE", pivot: str = "WORLD",
              cursor: Vector | None = None, threshold: float = 0.1) -> str | None:
    """Ось, относительно которой кривая почти симметрична: больше всего сплайнов проходят
    проверку, а точки при симметрии сдвигаются меньше всего. None — ни одна ось не подходит."""
    best, best_key = None, None
    for axis in _AXES:
        plane = make_plane(obj, axis, direction, pivot, cursor)
        valid, change = 0, 0.0
        for spline in obj.data.splines:
            if spline.type != "BEZIER":
                continue
            points = [_read(p) for p in spline.bezier_points]
            new = symmetrize_points(points, spline.use_cyclic_u, plane, threshold)
            if new is None:
                continue
            valid += 1
            change += sum(min((d["co"] - o["co"]).length for o in points) for d in new)
        key = (valid, -change)
        if valid and (best_key is None or key > best_key):
            best, best_key = axis, key
    return best


class CURVE_OT_symmetrize_bezier(Operator):
    bl_idname = "curve.symmetrize_bezier"
    bl_label = "Symmetrize Curve"
    bl_description = ("Mirror one side of the Bezier curve onto the other: handles, radius and tilt. "
                      "Points near the mirror plane snap onto it with mirrored handles")
    bl_options = {"REGISTER", "UNDO"}

    axis: EnumProperty(
        name="Axis",
        items=[("AUTO", "Auto", "The axis the curve is closest to being symmetric about"),
               ("X", "X", ""), ("Y", "Y", ""), ("Z", "Z", "")],
        default="AUTO",
    )
    direction: EnumProperty(
        name="Direction",
        items=[("POSITIVE", "+ to -", "Copy the positive side onto the negative side"),
               ("NEGATIVE", "- to +", "Copy the negative side onto the positive side")],
        default="POSITIVE",
    )
    pivot: EnumProperty(
        name="Pivot",
        items=[("WORLD", "World Origin", "Mirror plane through the world origin (ring center), world axes"),
               ("OBJECT", "Object Origin", "Mirror plane through the object origin, local axes"),
               ("CURSOR", "3D Cursor", "Mirror plane through the 3D cursor, world axes")],
        default="WORLD",
    )
    threshold: FloatProperty(
        name="Axis Threshold", description="Points closer to the mirror plane than this snap onto it",
        default=0.1, min=0.0, soft_max=1.0, subtype="DISTANCE",
    )

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return context.object is not None and context.object.type == "CURVE"

    def execute(self, context: bpy.types.Context):
        obj = context.object
        cursor = context.scene.cursor.location
        axis = self.axis
        if axis == "AUTO":
            axis = pick_axis(obj, self.direction, self.pivot, cursor, self.threshold)
        if axis is None:
            # FINISHED, а не CANCELLED: только так Blender покажет панель Adjust Last Operation,
            # где можно сменить Axis и Pivot
            self.report({"WARNING"}, "Nothing to symmetrize about any axis: a closed spline needs exactly "
                                     "2 points within Axis Threshold of the mirror plane, an open one 1. "
                                     "Check Pivot")
            return {"FINISHED"}
        done, skipped = symmetrize_curve(obj.data, make_plane(obj, axis, self.direction, self.pivot, cursor),
                                         self.threshold)
        if not done:
            self.report({"WARNING"}, "Nothing to symmetrize across %s: %s point(s) within Axis Threshold of the "
                                     "mirror plane; a closed spline needs exactly 2, an open one 1. "
                                     "Check Axis and Pivot" % (axis, ", ".join(map(str, skipped))))
        elif skipped:
            self.report({"WARNING"}, "Symmetrized across %s: %d spline(s), skipped %d" % (axis, done, len(skipped)))
        else:
            self.report({"INFO"}, "Symmetrized across %s" % axis)
        return {"FINISHED"}


_CLASSES = (CURVE_OT_symmetrize_bezier,)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
