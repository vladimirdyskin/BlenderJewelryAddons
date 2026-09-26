# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import bpy
from bpy.props import FloatProperty, PointerProperty
from bpy.types import Operator, PropertyGroup


GROUP_NAME = "Subdivide Local X"
MAX_SEGMENTS = 512
BUILD_VERSION = 2


def _input(node: bpy.types.Node, name: str) -> bpy.types.NodeSocket:
    return next(socket for socket in node.inputs if socket.name == name)


def _output(node: bpy.types.Node, name: str) -> bpy.types.NodeSocket:
    return next(socket for socket in node.outputs if socket.name == name)


def _math(nodes, operation: str, x: float, y: float) -> bpy.types.Node:
    node = nodes.new("ShaderNodeMath")
    node.operation = operation
    node.location = (x, y)
    return node


def build_group() -> bpy.types.GeometryNodeTree:
    group = bpy.data.node_groups.get(GROUP_NAME)
    preserved_values: list[tuple[bpy.types.Modifier, float]] = []
    if group is None:
        group = bpy.data.node_groups.new(GROUP_NAME, "GeometryNodeTree")
    elif group.get("jewelry_suite_build_version") == BUILD_VERSION and len(group.nodes):
        return group
    else:
        old_socket = next(
            (
                item
                for item in group.interface.items_tree
                if item.item_type == "SOCKET"
                and item.in_out == "INPUT"
                and item.name == "Segment Length"
            ),
            None,
        )
        if old_socket is not None:
            for obj in bpy.data.objects:
                for modifier in obj.modifiers:
                    if modifier.type != "NODES" or modifier.node_group != group:
                        continue
                    properties = getattr(modifier, "properties", None)
                    if properties is not None and hasattr(properties, "inputs"):
                        value = getattr(properties.inputs, old_socket.identifier).value
                    else:
                        value = modifier.get(old_socket.identifier, old_socket.default_value)
                    preserved_values.append((modifier, float(value)))
        group.nodes.clear()
        group.interface.clear()

    group.is_modifier = True
    group.color_tag = "GEOMETRY"

    group.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    segment_socket = group.interface.new_socket(
        "Segment Length",
        in_out="INPUT",
        socket_type="NodeSocketFloat",
    )
    segment_socket.default_value = 0.5
    segment_socket.min_value = 0.001
    segment_socket.max_value = 1000.0
    segment_socket.subtype = "DISTANCE"
    group.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    nodes = group.nodes
    links = group.links
    group_input = nodes.new("NodeGroupInput")
    group_input.location = (-1900, 300)
    group_output = nodes.new("NodeGroupOutput")
    group_output.location = (1500, 300)

    bounding_box = nodes.new("GeometryNodeBoundBox")
    bounding_box.location = (-1900, 50)
    links.new(_output(group_input, "Geometry"), _input(bounding_box, "Geometry"))

    separate_min = nodes.new("ShaderNodeSeparateXYZ")
    separate_min.location = (-1700, 0)
    separate_max = nodes.new("ShaderNodeSeparateXYZ")
    separate_max.location = (-1700, -180)
    links.new(_output(bounding_box, "Min"), _input(separate_min, "Vector"))
    links.new(_output(bounding_box, "Max"), _input(separate_max, "Vector"))

    length_x = _math(nodes, "SUBTRACT", -1450, 160)
    length_y = _math(nodes, "SUBTRACT", -1450, -20)
    length_z = _math(nodes, "SUBTRACT", -1450, -200)
    for node, axis in ((length_x, "X"), (length_y, "Y"), (length_z, "Z")):
        links.new(_output(separate_max, axis), node.inputs[0])
        links.new(_output(separate_min, axis), node.inputs[1])

    safe_segment = _math(nodes, "MAXIMUM", -1450, 360)
    safe_segment.inputs[1].default_value = 0.001
    links.new(_output(group_input, "Segment Length"), safe_segment.inputs[0])

    count_divide = _math(nodes, "DIVIDE", -1230, 300)
    count_ceil = _math(nodes, "CEIL", -1040, 300)
    count_min = _math(nodes, "MAXIMUM", -850, 300)
    count_min.inputs[1].default_value = 1.0
    count_max = _math(nodes, "MINIMUM", -660, 300)
    count_max.inputs[1].default_value = float(MAX_SEGMENTS)
    links.new(_output(length_x, "Value"), count_divide.inputs[0])
    links.new(_output(safe_segment, "Value"), count_divide.inputs[1])
    links.new(_output(count_divide, "Value"), count_ceil.inputs[0])
    links.new(_output(count_ceil, "Value"), count_min.inputs[0])
    links.new(_output(count_min, "Value"), count_max.inputs[0])

    step = _math(nodes, "DIVIDE", -850, 120)
    links.new(_output(length_x, "Value"), step.inputs[0])
    links.new(_output(count_max, "Value"), step.inputs[1])

    center_y_add = _math(nodes, "ADD", -1450, -420)
    center_y_half = _math(nodes, "MULTIPLY", -1230, -420)
    center_y_half.inputs[1].default_value = 0.5
    center_z_add = _math(nodes, "ADD", -1450, -580)
    center_z_half = _math(nodes, "MULTIPLY", -1230, -580)
    center_z_half.inputs[1].default_value = 0.5
    links.new(_output(separate_min, "Y"), center_y_add.inputs[0])
    links.new(_output(separate_max, "Y"), center_y_add.inputs[1])
    links.new(_output(center_y_add, "Value"), center_y_half.inputs[0])
    links.new(_output(separate_min, "Z"), center_z_add.inputs[0])
    links.new(_output(separate_max, "Z"), center_z_add.inputs[1])
    links.new(_output(center_z_add, "Value"), center_z_half.inputs[0])

    size_y = _math(nodes, "MULTIPLY", -1230, -60)
    size_y.inputs[1].default_value = 1.1
    size_z = _math(nodes, "MULTIPLY", -1230, -220)
    size_z.inputs[1].default_value = 1.1
    links.new(_output(length_y, "Value"), size_y.inputs[0])
    links.new(_output(length_z, "Value"), size_z.inputs[0])

    repeat_input = nodes.new("GeometryNodeRepeatInput")
    repeat_input.location = (-400, 300)
    repeat_output = nodes.new("GeometryNodeRepeatOutput")
    repeat_output.location = (1050, 300)
    repeat_input.pair_with_output(repeat_output)
    repeat_output.repeat_items.new("GEOMETRY", "Slices")
    repeat_output.repeat_items.new("INT", "Index")
    links.new(_output(count_max, "Value"), _input(repeat_input, "Iterations"))
    _input(repeat_input, "Index").default_value = 0

    index_half = _math(nodes, "ADD", -180, -420)
    index_half.inputs[1].default_value = 0.5
    center_x_scale = _math(nodes, "MULTIPLY", 20, -420)
    center_x_add = _math(nodes, "ADD", 220, -420)
    links.new(_output(repeat_input, "Index"), index_half.inputs[0])
    links.new(_output(index_half, "Value"), center_x_scale.inputs[0])
    links.new(_output(step, "Value"), center_x_scale.inputs[1])
    links.new(_output(center_x_scale, "Value"), center_x_add.inputs[0])
    links.new(_output(separate_min, "X"), center_x_add.inputs[1])

    cube_size = nodes.new("ShaderNodeCombineXYZ")
    cube_size.location = (-180, -120)
    links.new(_output(step, "Value"), _input(cube_size, "X"))
    links.new(_output(size_y, "Value"), _input(cube_size, "Y"))
    links.new(_output(size_z, "Value"), _input(cube_size, "Z"))

    cube_center = nodes.new("ShaderNodeCombineXYZ")
    cube_center.location = (220, -220)
    links.new(_output(center_x_add, "Value"), _input(cube_center, "X"))
    links.new(_output(center_y_half, "Value"), _input(cube_center, "Y"))
    links.new(_output(center_z_half, "Value"), _input(cube_center, "Z"))

    cube = nodes.new("GeometryNodeMeshCube")
    cube.location = (20, -80)
    _input(cube, "Vertices X").default_value = 2
    _input(cube, "Vertices Y").default_value = 2
    _input(cube, "Vertices Z").default_value = 2
    links.new(_output(cube_size, "Vector"), _input(cube, "Size"))

    transform_cube = nodes.new("GeometryNodeTransform")
    transform_cube.location = (420, -80)
    links.new(_output(cube, "Mesh"), _input(transform_cube, "Geometry"))
    links.new(_output(cube_center, "Vector"), _input(transform_cube, "Translation"))

    boolean = nodes.new("GeometryNodeMeshBoolean")
    boolean.location = (610, 80)
    boolean.operation = "INTERSECT"
    boolean.solver = "EXACT"
    links.new(_output(group_input, "Geometry"), boolean.inputs[1])
    links.new(_output(transform_cube, "Geometry"), boolean.inputs[1])

    edge_to_face = nodes.new("GeometryNodeFieldOnDomain")
    edge_to_face.location = (610, -240)
    edge_to_face.data_type = "FLOAT"
    edge_to_face.domain = "FACE"
    links.new(_output(boolean, "Intersecting Edges"), _input(edge_to_face, "Value"))

    all_intersection_edges = _math(nodes, "GREATER_THAN", 810, -240)
    all_intersection_edges.inputs[1].default_value = 0.999
    links.new(_output(edge_to_face, "Value"), all_intersection_edges.inputs[0])

    position = nodes.new("GeometryNodeInputPosition")
    position.location = (420, -520)
    separate_position = nodes.new("ShaderNodeSeparateXYZ")
    separate_position.location = (610, -520)
    links.new(_output(position, "Position"), _input(separate_position, "Vector"))

    boundary_epsilon_scale = _math(nodes, "MULTIPLY", 20, -650)
    boundary_epsilon_scale.inputs[1].default_value = 0.00001
    boundary_epsilon = _math(nodes, "MAXIMUM", 220, -650)
    boundary_epsilon.inputs[1].default_value = 0.00001
    links.new(_output(length_x, "Value"), boundary_epsilon_scale.inputs[0])
    links.new(_output(boundary_epsilon_scale, "Value"), boundary_epsilon.inputs[0])

    internal_min = _math(nodes, "ADD", 420, -650)
    internal_max = _math(nodes, "SUBTRACT", 420, -790)
    links.new(_output(separate_min, "X"), internal_min.inputs[0])
    links.new(_output(boundary_epsilon, "Value"), internal_min.inputs[1])
    links.new(_output(separate_max, "X"), internal_max.inputs[0])
    links.new(_output(boundary_epsilon, "Value"), internal_max.inputs[1])

    after_min = _math(nodes, "GREATER_THAN", 810, -520)
    before_max = _math(nodes, "LESS_THAN", 810, -650)
    links.new(_output(separate_position, "X"), after_min.inputs[0])
    links.new(_output(internal_min, "Value"), after_min.inputs[1])
    links.new(_output(separate_position, "X"), before_max.inputs[0])
    links.new(_output(internal_max, "Value"), before_max.inputs[1])

    inside_bounds = _math(nodes, "MULTIPLY", 1010, -580)
    links.new(_output(after_min, "Value"), inside_bounds.inputs[0])
    links.new(_output(before_max, "Value"), inside_bounds.inputs[1])
    delete_selection = _math(nodes, "MULTIPLY", 1010, -300)
    links.new(_output(all_intersection_edges, "Value"), delete_selection.inputs[0])
    links.new(_output(inside_bounds, "Value"), delete_selection.inputs[1])

    delete_caps = nodes.new("GeometryNodeDeleteGeometry")
    delete_caps.location = (1210, 80)
    delete_caps.domain = "FACE"
    links.new(_output(boolean, "Mesh"), _input(delete_caps, "Geometry"))
    links.new(_output(delete_selection, "Value"), _input(delete_caps, "Selection"))

    join = nodes.new("GeometryNodeJoinGeometry")
    join.location = (1250, 300)
    links.new(_output(repeat_input, "Slices"), _input(join, "Geometry"))
    links.new(_output(delete_caps, "Geometry"), _input(join, "Geometry"))
    links.new(_output(join, "Geometry"), _input(repeat_output, "Slices"))

    next_index = _math(nodes, "ADD", 1250, -420)
    next_index.inputs[1].default_value = 1.0
    links.new(_output(repeat_input, "Index"), next_index.inputs[0])
    links.new(_output(next_index, "Value"), _input(repeat_output, "Index"))

    merge = nodes.new("GeometryNodeMergeByDistance")
    merge.location = (1470, 300)
    _input(merge, "Distance").default_value = 0.00001
    links.new(_output(repeat_output, "Slices"), _input(merge, "Geometry"))
    links.new(_output(merge, "Geometry"), _input(group_output, "Geometry"))

    group_output.location = (1700, 300)
    group["jewelry_suite_build_version"] = BUILD_VERSION
    for modifier, value in preserved_values:
        _set_modifier_input(modifier, group, "Segment Length", value)
    return group


def _set_modifier_input(
    modifier: bpy.types.Modifier,
    group: bpy.types.GeometryNodeTree,
    socket_name: str,
    value: float,
) -> None:
    socket = next(
        item
        for item in group.interface.items_tree
        if item.item_type == "SOCKET" and item.in_out == "INPUT" and item.name == socket_name
    )
    properties = getattr(modifier, "properties", None)
    if properties is not None and hasattr(properties, "inputs"):
        getattr(properties.inputs, socket.identifier).value = value
    else:
        modifier[socket.identifier] = value


def attach_modifier(obj: bpy.types.Object, segment_length: float) -> bpy.types.Modifier:
    group = build_group()
    modifier = next(
        (
            item
            for item in obj.modifiers
            if item.type == "NODES" and item.node_group is not None and item.node_group.name == GROUP_NAME
        ),
        None,
    )
    if modifier is None:
        modifier = obj.modifiers.new(GROUP_NAME, "NODES")
        modifier.node_group = group
    else:
        modifier.node_group = group

    _set_modifier_input(modifier, group, "Segment Length", segment_length)

    curve_indices = [index for index, item in enumerate(obj.modifiers) if item.type == "CURVE"]
    if curve_indices:
        current_index = obj.modifiers.find(modifier.name)
        target_index = min(curve_indices)
        if current_index > target_index:
            obj.modifiers.move(current_index, target_index)

    obj.update_tag()
    return modifier


class SubdivideXSettings(PropertyGroup):
    segment_length: FloatProperty(
        name="Segment Length",
        description="Maximum local X segment length",
        default=0.5,
        min=0.001,
        soft_max=10.0,
        precision=3,
        unit="LENGTH",
    )


class OBJECT_OT_add_subdivide_x_nodes(Operator):
    bl_idname = "object.add_subdivide_x_nodes"
    bl_label = "Add Subdivide Local X"
    bl_description = "Add or update the Subdivide Local X Geometry Nodes modifier before Curve"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return context.object is not None and context.object.type == "MESH"

    def execute(self, context: bpy.types.Context):
        settings = context.scene.jewel_subdivide_x
        modifier = attach_modifier(context.object, settings.segment_length)
        self.report({"INFO"}, f"Updated {modifier.name} on {context.object.name}")
        return {"FINISHED"}


_CLASSES = (
    SubdivideXSettings,
    OBJECT_OT_add_subdivide_x_nodes,
)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.jewel_subdivide_x = PointerProperty(type=SubdivideXSettings)


def unregister() -> None:
    if hasattr(bpy.types.Scene, "jewel_subdivide_x"):
        del bpy.types.Scene.jewel_subdivide_x
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
