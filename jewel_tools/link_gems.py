# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from collections import defaultdict
import hashlib
import json

import bpy
from bpy.props import EnumProperty
from bpy.types import Operator
from mathutils import Vector


def _gem_metadata(obj: bpy.types.Object) -> dict[str, object]:
    value = obj.get("gem")
    if value is None:
        return {}
    try:
        return dict(value)
    except TypeError:
        return {}


def _mesh_extent(mesh: bpy.types.Mesh) -> Vector:
    if not mesh.vertices:
        return Vector((0.0, 0.0, 0.0))
    coordinates = [vertex.co for vertex in mesh.vertices]
    minimum = Vector(
        tuple(min(coordinate[axis] for coordinate in coordinates) for axis in range(3))
    )
    maximum = Vector(
        tuple(max(coordinate[axis] for coordinate in coordinates) for axis in range(3))
    )
    return maximum - minimum


def _mesh_signature(mesh: bpy.types.Mesh) -> str:
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
    payload = {
        "vertices": normalized,
        "edges": [tuple(edge.vertices) for edge in mesh.edges],
        "polygons": [tuple(polygon.vertices) for polygon in mesh.polygons],
        "attributes": sorted(
            (attribute.name, attribute.data_type, attribute.domain)
            for attribute in mesh.attributes
            if not attribute.is_internal
        ),
    }
    return hashlib.sha1(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _is_parametric_gem(obj: bpy.types.Object) -> bool:
    properties = getattr(obj, "parametric_gem", None)
    return bool(properties is not None and properties.is_parametric)


def _is_safe_candidate(obj: bpy.types.Object) -> bool:
    return (
        obj.type == "MESH"
        and bool(_gem_metadata(obj))
        and not _is_parametric_gem(obj)
        and obj.data.shape_keys is None
        and obj.data.animation_data is None
        and not obj.modifiers
        and obj.library is None
    )


def _modifier_input_value(modifier: bpy.types.Modifier, item) -> object:
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
        value = modifier.get(item.identifier, getattr(item, "default_value", None))

    if isinstance(value, bpy.types.ID):
        return (value.bl_rna.identifier, value.name)
    if hasattr(value, "to_list"):
        return tuple(round(number, 6) for number in value.to_list())
    if isinstance(value, float):
        return round(value, 6)
    return value


def _modifier_signature(obj: bpy.types.Object) -> tuple[object, ...]:
    signature = []
    for modifier in obj.modifiers:
        if modifier.type != "NODES" or modifier.node_group is None:
            return ()
        inputs = tuple(
            (item.name, _modifier_input_value(modifier, item))
            for item in modifier.node_group.interface.items_tree
            if item.item_type == "SOCKET"
            and item.in_out == "INPUT"
            and item.name != "Geometry"
        )
        signature.append(
            (
                modifier.type,
                modifier.node_group.name,
                inputs,
                modifier.show_viewport,
                modifier.show_render,
            )
        )
    return tuple(signature)


def _is_safe_prong_candidate(obj: bpy.types.Object) -> bool:
    return (
        obj.type == "MESH"
        and "prong" in obj.name.lower()
        and not _is_parametric_gem(obj)
        and obj.data.shape_keys is None
        and obj.data.animation_data is None
        and obj.animation_data is None
        and not obj.children
        and not obj.constraints
        and obj.library is None
        and all(
            modifier.type == "NODES"
            and modifier.node_group is not None
            and modifier.node_group.name == "Smooth by Angle"
            for modifier in obj.modifiers
        )
    )


def _group_key(obj: bpy.types.Object) -> tuple[object, ...]:
    metadata = _gem_metadata(obj)
    materials = tuple(material.name if material else None for material in obj.data.materials)
    return (
        str(metadata.get("cut", "")).upper(),
        str(metadata.get("stone", "")).upper(),
        materials,
        _mesh_signature(obj.data),
    )


def _prong_group_key(obj: bpy.types.Object) -> tuple[object, ...]:
    materials = tuple(material.name if material else None for material in obj.data.materials)
    return (
        materials,
        _modifier_signature(obj),
        _mesh_signature(obj.data),
    )


def _dimensions_match(expected: Vector, actual: Vector) -> bool:
    for expected_value, actual_value in zip(expected, actual):
        tolerance = max(1e-5, abs(expected_value) * 1e-5)
        if abs(expected_value - actual_value) > tolerance:
            return False
    return True


def _link_identical_objects(
    objects: list[bpy.types.Object],
    view_layer: bpy.types.ViewLayer,
    candidate_test,
    group_key,
) -> dict[str, int]:
    groups: dict[tuple[object, ...], list[bpy.types.Object]] = defaultdict(list)
    skipped = 0
    for obj in objects:
        if candidate_test(obj):
            groups[group_key(obj)].append(obj)
        else:
            skipped += 1

    linked_objects = 0
    linked_groups = 0
    failed_groups = 0

    for group_objects in groups.values():
        unique_meshes = {obj.data.as_pointer() for obj in group_objects}
        if len(group_objects) < 2 or len(unique_meshes) < 2:
            continue

        master = max(
            group_objects,
            key=lambda obj: (obj.data.users, -len(obj.name), obj.name),
        )
        master_extent = _mesh_extent(master.data)
        if any(value <= 1e-12 for value in master_extent):
            failed_groups += 1
            continue

        states = [
            (obj, obj.data, obj.scale.copy(), obj.dimensions.copy())
            for obj in group_objects
        ]

        for obj, old_mesh, old_scale, _old_dimensions in states:
            if obj == master or old_mesh == master.data:
                continue
            old_extent = _mesh_extent(old_mesh)
            if any(value <= 1e-12 for value in old_extent):
                continue
            obj.data = master.data
            obj.scale = Vector(
                tuple(
                    old_scale[axis] * old_extent[axis] / master_extent[axis]
                    for axis in range(3)
                )
            )

        view_layer.update()
        if any(
            not _dimensions_match(old_dimensions, obj.dimensions)
            for obj, _old_mesh, _old_scale, old_dimensions in states
        ):
            for obj, old_mesh, old_scale, _old_dimensions in states:
                obj.data = old_mesh
                obj.scale = old_scale
            view_layer.update()
            failed_groups += 1
            continue

        changed = sum(old_mesh != obj.data for obj, old_mesh, _old_scale, _dims in states)
        if changed:
            linked_objects += changed
            linked_groups += 1

    return {
        "linked_objects": linked_objects,
        "linked_groups": linked_groups,
        "skipped": skipped,
        "failed_groups": failed_groups,
    }


def link_identical_gems(
    objects: list[bpy.types.Object],
    view_layer: bpy.types.ViewLayer,
) -> dict[str, int]:
    return _link_identical_objects(
        objects,
        view_layer,
        _is_safe_candidate,
        _group_key,
    )


def link_identical_prongs(
    objects: list[bpy.types.Object],
    view_layer: bpy.types.ViewLayer,
) -> dict[str, int]:
    return _link_identical_objects(
        objects,
        view_layer,
        _is_safe_prong_candidate,
        _prong_group_key,
    )


class OBJECT_OT_link_identical_gems(Operator):
    bl_idname = "object.link_identical_gems"
    bl_label = "Link Identical Gems"
    bl_description = "Share mesh data between identical gems while preserving dimensions with object scale"
    bl_options = {"REGISTER", "UNDO"}

    scope: EnumProperty(
        name="Scope",
        items=(
            ("SELECTED", "Selected Gems", "Process selected editable gem objects"),
            ("ALL", "All Scene Gems", "Process all editable gem objects in the scene"),
        ),
        default="SELECTED",
    )

    def execute(self, context: bpy.types.Context):
        if self.scope == "SELECTED":
            objects = list(context.selected_editable_objects)
        else:
            objects = [obj for obj in context.scene.objects if obj.library is None]

        stats = link_identical_gems(objects, context.view_layer)
        if not stats["linked_objects"]:
            self.report(
                {"INFO"},
                "No separate identical gem meshes were found",
            )
            return {"CANCELLED"}

        self.report(
            {"INFO"},
            f"Linked {stats['linked_objects']} gems in {stats['linked_groups']} group(s); "
            f"skipped {stats['skipped']}, failed {stats['failed_groups']}",
        )
        return {"FINISHED"}


class OBJECT_OT_link_identical_prongs(Operator):
    bl_idname = "object.link_identical_prongs"
    bl_label = "Link Identical Prongs"
    bl_description = "Share mesh data between identical prongs while preserving dimensions and Smooth by Angle"
    bl_options = {"REGISTER", "UNDO"}

    scope: EnumProperty(
        name="Scope",
        items=(
            ("SELECTED", "Selected Prongs", "Process selected editable prong objects"),
            ("ALL", "All Scene Prongs", "Process all editable prong objects in the scene"),
        ),
        default="SELECTED",
    )

    def execute(self, context: bpy.types.Context):
        if self.scope == "SELECTED":
            objects = [
                obj
                for obj in context.selected_editable_objects
                if obj.type == "MESH" and "prong" in obj.name.lower()
            ]
        else:
            objects = [
                obj
                for obj in context.scene.objects
                if obj.type == "MESH"
                and "prong" in obj.name.lower()
                and obj.library is None
            ]

        stats = link_identical_prongs(objects, context.view_layer)
        if not stats["linked_objects"]:
            self.report({"INFO"}, "No separate identical prong meshes were found")
            return {"CANCELLED"}

        self.report(
            {"INFO"},
            f"Linked {stats['linked_objects']} prongs in {stats['linked_groups']} group(s); "
            f"skipped {stats['skipped']}, failed {stats['failed_groups']}",
        )
        return {"FINISHED"}


_CLASSES = (
    OBJECT_OT_link_identical_gems,
    OBJECT_OT_link_identical_prongs,
)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
