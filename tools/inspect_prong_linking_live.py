from __future__ import annotations

from collections import Counter
import sys

import bpy


objects = [
    obj
    for obj in bpy.context.scene.objects
    if obj.type == "MESH" and "prong" in obj.name.lower()
]

link_module = sys.modules.get("bl_ext.user_default.jewelry_suite.link_gems")
if link_module is None:
    raise RuntimeError("Jewelry Suite link_gems module is not loaded")


def input_values(modifier: bpy.types.Modifier) -> tuple[tuple[str, object], ...]:
    if modifier.type != "NODES" or modifier.node_group is None:
        return ()
    values = []
    for item in modifier.node_group.interface.items_tree:
        if item.item_type != "SOCKET" or item.in_out != "INPUT" or item.name == "Geometry":
            continue
        properties = getattr(modifier, "properties", None)
        if properties is not None and hasattr(properties, "inputs"):
            input_property = getattr(properties.inputs, item.identifier)
            if hasattr(input_property, "value"):
                value = input_property.value
            else:
                value = (
                    input_property.__class__.__name__,
                    getattr(input_property, "type", None),
                    getattr(input_property, "attribute_name", None),
                )
        else:
            value = modifier.get(item.identifier, item.default_value)
        if hasattr(value, "to_list"):
            value = tuple(round(number, 6) for number in value.to_list())
        elif isinstance(value, float):
            value = round(value, 6)
        elif isinstance(value, bpy.types.ID):
            value = (value.bl_rna.identifier, value.name)
        values.append((item.name, value))
    return tuple(values)

result = {
    "blend": bpy.data.filepath,
    "prongs": len(objects),
    "selected": sum(obj.select_get() for obj in objects),
    "unique_mesh_data": len({obj.data.as_pointer() for obj in objects}),
    "already_linked": sum(obj.data.users > 1 for obj in objects),
    "materials": Counter(
        tuple(material.name if material else None for material in obj.data.materials)
        for obj in objects
    ).most_common(),
    "vertex_face_counts": Counter(
        (len(obj.data.vertices), len(obj.data.polygons)) for obj in objects
    ).most_common(),
    "modifier_sets": Counter(
        tuple(modifier.type for modifier in obj.modifiers) for obj in objects
    ).most_common(),
    "normalized_signatures": Counter(
        link_module._mesh_signature(obj.data) for obj in objects
    ).most_common(),
    "node_groups": Counter(
        tuple(
            (
                modifier.node_group.name if modifier.node_group else None,
                input_values(modifier),
            )
            for modifier in obj.modifiers
            if modifier.type == "NODES"
        )
        for obj in objects
    ).most_common(),
    "samples": [
        {
            "name": obj.name,
            "mesh": obj.data.name,
            "dimensions": [round(value, 4) for value in obj.dimensions],
            "scale": [round(value, 6) for value in obj.scale],
            "materials": [material.name if material else None for material in obj.data.materials],
            "modifiers": [modifier.type for modifier in obj.modifiers],
        }
        for obj in objects[:10]
    ],
}
