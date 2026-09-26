from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json

import bpy


def gem_metadata(obj: bpy.types.Object) -> dict[str, object]:
    value = obj.get("gem")
    if value is None:
        return {}
    try:
        return dict(value)
    except TypeError:
        return {}


def normalized_mesh_signature(mesh: bpy.types.Mesh) -> str:
    if not mesh.vertices:
        return "empty"
    coordinates = [vertex.co.copy() for vertex in mesh.vertices]
    minimum = [min(coordinate[axis] for coordinate in coordinates) for axis in range(3)]
    maximum = [max(coordinate[axis] for coordinate in coordinates) for axis in range(3)]
    extent = [maximum[axis] - minimum[axis] for axis in range(3)]
    normalized = [
        tuple(
            round((coordinate[axis] - minimum[axis]) / extent[axis], 6)
            if extent[axis] > 1e-12
            else 0.0
            for axis in range(3)
        )
        for coordinate in coordinates
    ]
    topology = [tuple(polygon.vertices) for polygon in mesh.polygons]
    payload = {
        "vertices": normalized,
        "edges": [tuple(edge.vertices) for edge in mesh.edges],
        "polygons": topology,
    }
    return hashlib.sha1(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:12]


mesh_objects = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
gem_objects = [obj for obj in mesh_objects if gem_metadata(obj)]
round_objects = [
    obj
    for obj in gem_objects
    if str(gem_metadata(obj).get("cut", "")).upper() == "ROUND"
]

groups: dict[tuple[str, tuple[str | None, ...]], list[bpy.types.Object]] = defaultdict(list)
for obj in round_objects:
    signature = normalized_mesh_signature(obj.data)
    materials = tuple(material.name if material else None for material in obj.data.materials)
    groups[(signature, materials)].append(obj)

result = {
    "blend": bpy.data.filepath,
    "objects": {
        "total": len(bpy.context.scene.objects),
        "mesh": len(mesh_objects),
        "gems": len(gem_objects),
        "round_gems": len(round_objects),
        "selected_round_gems": sum(obj.select_get() for obj in round_objects),
    },
    "gem_cuts": Counter(
        str(gem_metadata(obj).get("cut", "UNKNOWN")) for obj in gem_objects
    ).most_common(),
    "round_meshes": {
        "unique_mesh_data": len({obj.data.as_pointer() for obj in round_objects}),
        "already_linked_objects": sum(obj.data.users > 1 for obj in round_objects),
        "normalized_groups": len(groups),
        "linkable_groups": sum(len(objects) > 1 for objects in groups.values()),
        "linkable_objects": sum(len(objects) for objects in groups.values() if len(objects) > 1),
    },
    "groups": [
        {
            "signature": signature,
            "materials": materials,
            "objects": len(objects),
            "unique_meshes": len({obj.data.as_pointer() for obj in objects}),
            "sample": [
                {
                    "name": obj.name,
                    "mesh": obj.data.name,
                    "dimensions": [round(value, 4) for value in obj.dimensions],
                    "scale": [round(value, 6) for value in obj.scale],
                    "modifiers": [modifier.type for modifier in obj.modifiers],
                }
                for obj in objects[:3]
            ],
        }
        for (signature, materials), objects in sorted(
            groups.items(), key=lambda item: len(item[1]), reverse=True
        )[:10]
    ],
}
