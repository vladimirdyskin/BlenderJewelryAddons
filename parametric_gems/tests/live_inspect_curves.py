from __future__ import annotations

import bpy


def spline_length(spline) -> float | None:
    try:
        return spline.calc_length()
    except Exception:
        return None


result = {
    "active": bpy.context.object.name if bpy.context.object else None,
    "curves": [
        {
            "name": obj.name,
            "dimensions": [round(value, 6) for value in obj.dimensions],
            "scale": [round(value, 6) for value in obj.scale],
            "rotation": [round(value, 6) for value in obj.rotation_euler],
            "splines": [
                {
                    "type": spline.type,
                    "cyclic": spline.use_cyclic_u,
                    "bezier_points": len(spline.bezier_points),
                    "points": len(spline.points),
                    "local_length": spline_length(spline),
                }
                for spline in obj.data.splines
            ],
            "modifiers": [modifier.name for modifier in obj.modifiers],
            "diameter_mm": (
                obj.parametric_circle_size.diameter_mm
                if hasattr(obj, "parametric_circle_size")
                else None
            ),
            "circumference_mm": (
                obj.parametric_circle_size.circumference_mm
                if hasattr(obj, "parametric_circle_size")
                else None
            ),
        }
        for obj in bpy.context.scene.objects
        if obj.type == "CURVE"
    ],
}
