from __future__ import annotations

from pathlib import Path

import bpy


SOURCE_OBJECT = "RingBaseProto"
OUTPUT_PATH = Path.home() / "GitHub/BlenderJewelryAddons/parametric_gems/assets/signets.blend"


obj = bpy.data.objects.get(SOURCE_OBJECT)
if obj is None or obj.type != "MESH":
    raise RuntimeError(f"Mesh object '{SOURCE_OBJECT}' was not found")

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
bpy.data.libraries.write(
    str(OUTPUT_PATH),
    {obj.data},
    fake_user=True,
    compress=True,
)

result = {
    "source_object": obj.name,
    "mesh": obj.data.name,
    "vertices": len(obj.data.vertices),
    "edges": len(obj.data.edges),
    "polygons": len(obj.data.polygons),
    "output": str(OUTPUT_PATH),
}
print("Signet template exported:", result)
