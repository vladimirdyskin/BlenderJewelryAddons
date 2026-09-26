from __future__ import annotations

from pathlib import Path
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jewelry_suite


def create_gem(name: str, size: tuple[float, float, float]) -> bpy.types.Object:
    x, y, z = (value * 0.5 for value in size)
    vertices = (
        (-x, -y, -z),
        (x, -y, -z),
        (x, y, -z),
        (-x, y, -z),
        (-x, -y, z),
        (x, -y, z),
        (x, y, z),
        (-x, y, z),
    )
    faces = (
        (0, 3, 2, 1),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    )
    mesh = bpy.data.meshes.new(f"{name} Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(bpy.data.materials["Diamond"])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj["gem"] = {"cut": "ROUND", "stone": "DIAMOND"}
    bpy.context.collection.objects.link(obj)
    return obj


jewelry_suite.register()
bpy.data.materials.new("Diamond")

gems = (
    create_gem("Gem A", (1.0, 1.0, 0.6)),
    create_gem("Gem B", (2.0, 2.0, 1.2)),
    create_gem("Gem C", (0.5, 0.5, 0.3)),
)
gems[0].location = (1.0, 2.0, 3.0)
gems[1].rotation_euler = (0.2, -0.4, 0.8)
gems[2].scale = (3.0, 3.0, -3.0)

skipped = create_gem("Gem With Modifier", (1.0, 1.0, 0.6))
skipped.modifiers.new("Bevel", "BEVEL")

bpy.context.view_layer.update()
states = {
    obj.name: {
        "dimensions": obj.dimensions.copy(),
        "location": obj.location.copy(),
        "rotation": obj.rotation_euler.copy(),
        "gem": dict(obj["gem"]),
    }
    for obj in (*gems, skipped)
}
skipped_mesh = skipped.data

result = bpy.ops.object.link_identical_gems(scope="ALL")
assert result == {"FINISHED"}
bpy.context.view_layer.update()

assert len({obj.data.as_pointer() for obj in gems}) == 1
assert skipped.data == skipped_mesh
for obj in gems:
    state = states[obj.name]
    assert all(abs(a - b) <= 1e-5 for a, b in zip(obj.dimensions, state["dimensions"]))
    assert (obj.location - state["location"]).length <= 1e-8
    assert Vector(obj.rotation_euler).to_tuple() == Vector(state["rotation"]).to_tuple()
    assert dict(obj["gem"]) == state["gem"]

skipped_state = states[skipped.name]
assert (skipped.location - skipped_state["location"]).length <= 1e-8
assert Vector(skipped.rotation_euler).to_tuple() == Vector(skipped_state["rotation"]).to_tuple()
assert dict(skipped["gem"]) == skipped_state["gem"]

print(
    "LINK_GEMS_TEST",
    {
        "linked_objects": len(gems),
        "unique_meshes": len({obj.data.as_pointer() for obj in gems}),
        "dimensions": [tuple(round(value, 4) for value in obj.dimensions) for obj in gems],
        "skipped_modifier_mesh_preserved": skipped.data == skipped_mesh,
    },
)

jewelry_suite.unregister()
