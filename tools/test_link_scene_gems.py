from __future__ import annotations

from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jewelry_suite


jewelry_suite.register()
gems = [
    obj
    for obj in bpy.context.scene.objects
    if obj.type == "MESH" and obj.get("gem") is not None
]
bpy.context.view_layer.update()
states = {
    obj.name: (obj.dimensions.copy(), obj.matrix_world.copy())
    for obj in gems
}
unique_before = len({obj.data.as_pointer() for obj in gems})

stats = jewelry_suite.link_gems.link_identical_gems(gems, bpy.context.view_layer)
unique_after = len({obj.data.as_pointer() for obj in gems})

for obj in gems:
    dimensions, matrix = states[obj.name]
    assert all(abs(a - b) <= max(1e-5, abs(a) * 1e-5) for a, b in zip(obj.dimensions, dimensions))
    for row in range(4):
        for column in range(4):
            assert abs(obj.matrix_world[row][column] - matrix[row][column]) <= 1e-6

print(
    "LINK_SCENE_GEMS_TEST",
    {
        "blend": bpy.data.filepath,
        "gems": len(gems),
        "unique_meshes_before": unique_before,
        "unique_meshes_after": unique_after,
        "stats": stats,
    },
)

jewelry_suite.unregister()
