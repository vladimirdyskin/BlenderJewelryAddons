from __future__ import annotations

from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jewelry_suite


def evaluated_geometry_snapshot(
    obj: bpy.types.Object,
    depsgraph: bpy.types.Depsgraph,
) -> tuple[list[tuple[float, float, float]], tuple[tuple[int, ...], ...]]:
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    matrix = evaluated.matrix_world
    coordinates = [tuple(matrix @ vertex.co) for vertex in mesh.vertices]
    topology = tuple(tuple(polygon.vertices) for polygon in mesh.polygons)
    evaluated.to_mesh_clear()
    return coordinates, topology


jewelry_suite.register()
prongs = [
    obj
    for obj in bpy.context.scene.objects
    if obj.type == "MESH" and "prong" in obj.name.lower()
]
bpy.context.view_layer.update()
depsgraph = bpy.context.evaluated_depsgraph_get()
states = {
    obj.name: {
        "dimensions": obj.dimensions.copy(),
        "geometry": evaluated_geometry_snapshot(obj, depsgraph),
    }
    for obj in prongs
}
unique_before = len({obj.data.as_pointer() for obj in prongs})

stats = jewelry_suite.link_gems.link_identical_prongs(prongs, bpy.context.view_layer)
unique_after = len({obj.data.as_pointer() for obj in prongs})
bpy.context.view_layer.update()
depsgraph = bpy.context.evaluated_depsgraph_get()

mismatches = []
for obj in prongs:
    state = states[obj.name]
    assert all(
        abs(a - b) <= max(1e-5, abs(a) * 1e-5)
        for a, b in zip(obj.dimensions, state["dimensions"])
    )
    old_coordinates, old_topology = state["geometry"]
    new_coordinates, new_topology = evaluated_geometry_snapshot(obj, depsgraph)
    topology_matches = old_topology == new_topology
    if len(old_coordinates) != len(new_coordinates):
        maximum_error = float("inf")
    else:
        maximum_error = max(
            abs(old_value - new_value)
            for old_coordinate, new_coordinate in zip(old_coordinates, new_coordinates)
            for old_value, new_value in zip(old_coordinate, new_coordinate)
        )
    if not topology_matches or maximum_error > 2e-6:
        mismatches.append((obj.name, maximum_error, topology_matches))

print(
    "LINK_SCENE_PRONGS_TEST",
    {
        "blend": bpy.data.filepath,
        "prongs": len(prongs),
        "unique_meshes_before": unique_before,
        "unique_meshes_after": unique_after,
        "stats": stats,
        "mismatches": sorted(mismatches, key=lambda item: item[1], reverse=True)[:10],
    },
)

assert not mismatches

jewelry_suite.unregister()
