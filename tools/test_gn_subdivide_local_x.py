from __future__ import annotations

from math import cos, pi, sin
from pathlib import Path
import sys

import bmesh
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jewelry_suite


def build_prism() -> tuple[bpy.types.Object, list[tuple[float, float]]]:
    profile = []
    for index in range(12):
        angle = 2.0 * pi * index / 12.0
        radius_y = 2.0 + 0.25 * cos(3.0 * angle)
        radius_z = 1.0 + 0.15 * sin(2.0 * angle)
        profile.append((radius_y * cos(angle), radius_z * sin(angle)))

    vertices = []
    for x in (-6.0, 6.0):
        vertices.extend((x, y, z) for y, z in profile)

    count = len(profile)
    faces = [tuple(range(count - 1, -1, -1)), tuple(range(count, count * 2))]
    for index in range(count):
        next_index = (index + 1) % count
        faces.append((index, next_index, count + next_index, count + index))

    mesh = bpy.data.meshes.new("GN Subdivide X Test Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("GN Subdivide X Test", mesh)
    bpy.context.collection.objects.link(obj)
    return obj, profile


def non_manifold_edges(mesh: bpy.types.Mesh) -> int:
    bm = bmesh.new()
    bm.from_mesh(mesh)
    count = sum(1 for edge in bm.edges if not edge.is_manifold)
    bm.free()
    return count


def end_face_counts(mesh: bpy.types.Mesh) -> tuple[int, int]:
    min_x = min(vertex.co.x for vertex in mesh.vertices)
    max_x = max(vertex.co.x for vertex in mesh.vertices)
    tolerance = max(1e-5, (max_x - min_x) * 1e-5)
    left = 0
    right = 0
    for polygon in mesh.polygons:
        values = [mesh.vertices[index].co.x for index in polygon.vertices]
        left += int(all(abs(value - min_x) <= tolerance for value in values))
        right += int(all(abs(value - max_x) <= tolerance for value in values))
    return left, right


jewelry_suite.register()
obj, profile = build_prism()
expected_profile = {(round(y, 5), round(z, 5)) for y, z in profile}
bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj

bpy.context.scene.jewel_subdivide_x.segment_length = 1.25
operator_result = bpy.ops.object.add_subdivide_x_nodes()
assert operator_result == {"FINISHED"}
assert len(obj.data.vertices) == 24

bpy.context.view_layer.update()
depsgraph = bpy.context.evaluated_depsgraph_get()
evaluated = obj.evaluated_get(depsgraph)
mesh = evaluated.to_mesh()

x_positions = {round(vertex.co.x, 5) for vertex in mesh.vertices}
actual_profile = {
    (round(vertex.co.y, 5), round(vertex.co.z, 5))
    for vertex in mesh.vertices
}
internal_profile = {
    (round(vertex.co.y, 5), round(vertex.co.z, 5))
    for vertex in mesh.vertices
    if -5.999 < vertex.co.x < 5.999
}
result = {
    "source_vertices": len(obj.data.vertices),
    "evaluated_vertices": len(mesh.vertices),
    "evaluated_edges": len(mesh.edges),
    "evaluated_faces": len(mesh.polygons),
    "x_sections": len(x_positions),
    "profile_points": len(actual_profile),
    "non_manifold_edges": non_manifold_edges(mesh),
    "min_x": min(x_positions) if x_positions else None,
    "max_x": max(x_positions) if x_positions else None,
}
print("GN_SUBDIVIDE_X_TEST", result)
print("GN_SUBDIVIDE_X_PROFILE_EXTRA", sorted(actual_profile - expected_profile))
print("GN_SUBDIVIDE_X_PROFILE_MISSING", sorted(expected_profile - actual_profile))

assert len(x_positions) == 11
assert min(x_positions) == -6.0 and max(x_positions) == 6.0
assert internal_profile == expected_profile
assert non_manifold_edges(mesh) == 0

evaluated.to_mesh_clear()

bpy.ops.object.select_all(action="DESELECT")
bpy.ops.mesh.primitive_cube_add()
cube = bpy.context.object
cube.name = "GN Subdivide X Cube Test"
cube.scale = (6.0, 1.0, 1.0)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
assert len(cube.data.vertices) == 8
bpy.context.scene.jewel_subdivide_x.segment_length = 1.25
assert bpy.ops.object.add_subdivide_x_nodes() == {"FINISHED"}
bpy.context.view_layer.update()
evaluated_cube = cube.evaluated_get(bpy.context.evaluated_depsgraph_get())
cube_mesh = evaluated_cube.to_mesh()
cube_end_faces = end_face_counts(cube_mesh)
print(
    "GN_SUBDIVIDE_X_CUBE_TEST",
    {
        "source_vertices": len(cube.data.vertices),
        "evaluated_vertices": len(cube_mesh.vertices),
        "end_faces": cube_end_faces,
        "non_manifold_edges": non_manifold_edges(cube_mesh),
    },
)
assert cube_end_faces[0] > 0
assert cube_end_faces[1] > 0
assert non_manifold_edges(cube_mesh) == 0
evaluated_cube.to_mesh_clear()

curve_data = bpy.data.curves.new("GN Subdivide X Test Curve", "CURVE")
curve_data.dimensions = "3D"
spline = curve_data.splines.new("BEZIER")
spline.bezier_points.add(1)
spline.bezier_points[0].co = (-6.0, 0.0, 0.0)
spline.bezier_points[1].co = (6.0, 4.0, 0.0)
for point in spline.bezier_points:
    point.handle_left_type = "AUTO"
    point.handle_right_type = "AUTO"
curve_obj = bpy.data.objects.new("GN Subdivide X Test Curve", curve_data)
bpy.context.collection.objects.link(curve_obj)

curve_modifier = obj.modifiers.new("Curve", "CURVE")
curve_modifier.object = curve_obj
curve_modifier.deform_axis = "POS_X"
bpy.context.view_layer.update()
evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
curve_mesh = evaluated.to_mesh()
assert len(curve_mesh.vertices) == result["evaluated_vertices"]
assert non_manifold_edges(curve_mesh) == 0
assert obj.modifiers[0].type == "NODES"
assert obj.modifiers[1].type == "CURVE"
evaluated.to_mesh_clear()

jewelry_suite.unregister()
