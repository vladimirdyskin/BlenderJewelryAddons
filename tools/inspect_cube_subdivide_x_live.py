from __future__ import annotations

import bpy
import bmesh


def end_face_counts(mesh: bpy.types.Mesh) -> dict[str, int]:
    if not mesh.vertices:
        return {"left": 0, "right": 0}
    min_x = min(vertex.co.x for vertex in mesh.vertices)
    max_x = max(vertex.co.x for vertex in mesh.vertices)
    tolerance = max(1e-5, (max_x - min_x) * 1e-5)
    counts = {"left": 0, "right": 0}
    for polygon in mesh.polygons:
        xs = [mesh.vertices[index].co.x for index in polygon.vertices]
        if xs and all(abs(value - min_x) <= tolerance for value in xs):
            counts["left"] += 1
        if xs and all(abs(value - max_x) <= tolerance for value in xs):
            counts["right"] += 1
    return counts


obj = bpy.data.objects.get("Cube")
if obj is None:
    raise RuntimeError("Object 'Cube' was not found")

depsgraph = bpy.context.evaluated_depsgraph_get()
evaluated = obj.evaluated_get(depsgraph)
evaluated_mesh = evaluated.to_mesh()
bm = bmesh.new()
bm.from_mesh(evaluated_mesh)
non_manifold_edges = sum(1 for edge in bm.edges if not edge.is_manifold)
bm.free()

result = {
    "blend": bpy.data.filepath,
    "source": {
        "vertices": len(obj.data.vertices),
        "faces": len(obj.data.polygons),
        "end_faces": end_face_counts(obj.data),
    },
    "evaluated": {
        "vertices": len(evaluated_mesh.vertices),
        "faces": len(evaluated_mesh.polygons),
        "end_faces": end_face_counts(evaluated_mesh),
        "non_manifold_edges": non_manifold_edges,
    },
    "modifiers": [
        {
            "name": modifier.name,
            "type": modifier.type,
            "node_group": modifier.node_group.name if modifier.type == "NODES" and modifier.node_group else None,
        }
        for modifier in obj.modifiers
    ],
}

evaluated.to_mesh_clear()
