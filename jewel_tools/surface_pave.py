# SPDX-License-Identifier: GPL-3.0-or-later

"""Paint a region, then build rigid round-gem instances on its surface."""

import json
from math import atan2, pi
from pathlib import Path

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy.types import Operator, Panel, PropertyGroup
from mathutils import Matrix, Vector

from .pave_layout import MASK_NAME, Surface, pack
from . import pave_live


ROLE = "jewelry_pave_role"
OWNER = "jewelry_pave_owner"


def _mesh_poll(_self, obj):
    return obj.type == 'MESH' and not obj.get(ROLE)


class SurfacePaveSettings(PropertyGroup):
    live_preview: BoolProperty(name="Live Pave", default=True,
                               description="Reveal fixed gem positions as you paint or erase the mask")
    show_mask: BoolProperty(name="Show Mask Color", default=False,
                            description="Show the weight colors while painting gems",
                            update=pave_live.update_overlay)
    gem: PointerProperty(name="Gem Source", type=bpy.types.Object, poll=_mesh_poll,
                         description="Optional round gem; leave empty to use the bundled round diamond")
    diameter: FloatProperty(name="Diameter (mm)", default=1.5, min=0.05, soft_max=10.0,
                            description="Round gem diameter; one Blender unit equals one millimetre")
    gap: FloatProperty(name="Gap (mm)", default=0.15, min=0.0, soft_max=2.0,
                       description="Minimum clearance between conservative envelopes of the complete gems")
    border: FloatProperty(name="Border (mm)", default=0.1, min=0.0, soft_max=3.0,
                          description="Extra clearance beyond the gem radius at mask and mesh boundaries")
    offset: FloatProperty(name="Seat Offset (mm)", default=0.0, soft_min=-2.0, soft_max=2.0,
                          description="Girdle bottom above the surface along its normal; negative values sink the gem")
    angle: FloatProperty(name="Row Angle", subtype='ANGLE', default=0.0,
                         description="Initial row direction around the surface normal")
    threshold: FloatProperty(name="Mask Threshold", default=0.5, min=0.01, max=1.0,
                             description="Weights at or above this value belong to the paved region")
    use_cursor: BoolProperty(name="Start at 3D Cursor", default=False,
                             description="Start the first row near the cursor instead of the surface top")
    max_stones: IntProperty(name="Stone Limit", default=5000, min=1, max=50000)
    output: PointerProperty(type=bpy.types.Object)
    paint_state: StringProperty(options={'HIDDEN'})


def _target(context):
    obj = context.scene.jewel_pave_surface
    if obj is None:
        obj = context.active_object
    if obj is None or obj.type != 'MESH' or obj.get(ROLE):
        raise ValueError("Choose a mesh surface with Use Active Surface")
    if obj.name not in context.view_layer.objects:
        raise ValueError("The surface must be in the current view layer")
    if not obj.is_editable or not obj.data.is_editable:
        raise ValueError("Make the surface local before painting its mask")
    return obj


def _activate(context, obj):
    if context.object is not None and context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for selected in context.selected_objects:
        selected.select_set(False)
    obj.hide_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    context.scene.jewel_pave_surface = obj


def _mask(obj):
    group = obj.vertex_groups.get(MASK_NAME) or obj.vertex_groups.new(name=MASK_NAME)
    if group.lock_weight:
        raise ValueError("Unlock the PaveMask vertex group before painting")
    if obj.data.users > 1:
        obj.data = obj.data.copy()
    obj.vertex_groups.active_index = group.index
    return group


def _owned(obj, surface, role):
    return obj is not None and obj.get(ROLE) == role and obj.get(OWNER) == surface


def _restore_paint(context, obj):
    settings = obj.jewel_pave
    if not settings.paint_state:
        return
    pave_live.finish(context, obj)
    state = json.loads(settings.paint_state)
    for key, value in state["tools"].items():
        setattr(context.tool_settings, key, value)
    for key, value in state["mesh"].items():
        setattr(obj.data, key, value)
    for key, value in state["paint"].items():
        setattr(context.tool_settings.weight_paint, key, value)
    unified = context.tool_settings.weight_paint.unified_paint_settings
    for key, value in state["unified"].items():
        setattr(unified, key, value)
    context.tool_settings.weight_paint.use_group_restrict = state["restrict"]
    if _owned(settings.output, obj, "OUTPUT"):
        settings.output.hide_set(state["output_hidden"])
        settings.output.hide_select = state.get("output_hide_select", False)
    settings.paint_state = ""


def _finish_paint(context):
    if (context.object and context.object.mode == 'WEIGHT_PAINT'
            and context.object.jewel_pave.paint_state):
        bpy.ops.object.mode_set(mode='OBJECT')
    for obj in context.scene.objects:
        if obj.jewel_pave.paint_state:
            _restore_paint(context, obj)


def _template_mesh(source, diameter, depsgraph):
    if source is None:
        asset = Path(__file__).parent / "assets" / "gems.blend"
        if not asset.exists():
            asset = Path(__file__).parent.parent / "parametric_gems" / "assets" / "gems.blend"
        if not asset.exists():
            raise ValueError("Choose a round Gem Source; the bundled template is unavailable")
        with bpy.data.libraries.load(str(asset)) as (_source, target):
            target.meshes = ["Round"]
        mesh = target.meshes[0]
        metadata = {"cut": "ROUND", "stone": "DIAMOND"}
    else:
        metadata = dict(source.get("gem", {"cut": "ROUND", "stone": "DIAMOND"}))
        if metadata.get("cut", "ROUND") != "ROUND":
            raise ValueError("Surface Pave currently supports round gems only")
        evaluated = source.evaluated_get(depsgraph)
        mesh = bpy.data.meshes.new_from_object(evaluated, preserve_all_data_layers=True, depsgraph=depsgraph)
    try:
        if mesh is None or not mesh.vertices or not mesh.polygons:
            raise ValueError("The Gem Source has no mesh geometry")
        coords = [v.co.copy() for v in mesh.vertices]
        low_x, high_x = min(v.x for v in coords), max(v.x for v in coords)
        low_y, high_y = min(v.y for v in coords), max(v.y for v in coords)
        width, length = high_x - low_x, high_y - low_y
        if min(width, length) < 1e-6 or abs(width - length) > max(width, length) * 0.03:
            raise ValueError("Use a round source mesh with its girdle in the local XY plane")
        center_x, center_y = (low_x + high_x) * 0.5, (low_y + high_y) * 0.5
        radii = [((v.x - center_x) ** 2 + (v.y - center_y) ** 2) ** 0.5 for v in coords]
        radius = max(radii)
        angles = sorted({round(atan2(v.y - center_y, v.x - center_x), 6)
                         for v, r in zip(coords, radii) if r >= radius * 0.995})
        if (len(angles) < 8 or max(b - a for a, b in zip(angles, angles[1:] + [angles[0] + 2 * pi])) > pi / 3):
            raise ValueError("The source must have a circular girdle in its local XY plane")
        girdle = [v.z for v, r in zip(coords, radii) if r >= radius * 0.995]
        base_z = min(girdle)
        scale = diameter / (radius * 2.0)
        center = Vector((center_x, center_y, base_z))
        envelope = 0.0
        for vertex in mesh.vertices:
            vertex.co = (vertex.co - center) * scale
            envelope = max(envelope, vertex.co.length)
        mesh.name = "Pave Gem Template"
        mesh.update()
        return mesh, envelope, metadata
    except Exception:
        if mesh is not None:
            bpy.data.meshes.remove(mesh)
        raise


def _instance_group(template):
    group = bpy.data.node_groups.new("Surface Pave Instances", 'GeometryNodeTree')
    group[ROLE] = "NODES"
    group.is_modifier = True
    group.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    group.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    nodes, links = group.nodes, group.links
    input_node = nodes.new('NodeGroupInput')
    input_node.location = (-440, 160)
    source = nodes.new('GeometryNodeObjectInfo')
    source.location = (-440, -40)
    source.transform_space = 'ORIGINAL'
    source.inputs['Object'].default_value = template
    source.inputs['As Instance'].default_value = True
    rotation = nodes.new('GeometryNodeInputNamedAttribute')
    rotation.data_type = 'FLOAT_VECTOR'
    rotation.inputs['Name'].default_value = "pave_rotation"
    rotation.location = (-440, -310)
    visible = nodes.new('GeometryNodeInputNamedAttribute')
    visible.data_type = 'BOOLEAN'
    visible.inputs['Name'].default_value = "pave_visible"
    visible.location = (-200, 400)
    euler = nodes.new('FunctionNodeEulerToRotation')
    euler.location = (-200, -310)
    instances = nodes.new('GeometryNodeInstanceOnPoints')
    instances.location = (40, 160)
    output = nodes.new('NodeGroupOutput')
    output.location = (320, 160)
    links.new(input_node.outputs['Geometry'], instances.inputs['Points'])
    links.new(visible.outputs['Attribute'], instances.inputs['Selection'])
    links.new(source.outputs['Geometry'], instances.inputs['Instance'])
    links.new(rotation.outputs['Attribute'], euler.inputs['Euler'])
    links.new(euler.outputs['Rotation'], instances.inputs['Rotation'])
    links.new(instances.outputs['Instances'], output.inputs['Geometry'])
    return group


def _cleanup_output_data(mesh, group, template):
    if mesh is not None and mesh.users == 0:
        bpy.data.meshes.remove(mesh)
    if group is not None and group.users == 0 and group.get(ROLE) == "NODES":
        bpy.data.node_groups.remove(group)
    if template is not None and template.get(ROLE) == "TEMPLATE" and template.users <= 1:
        template_mesh = template.data
        bpy.data.objects.remove(template, do_unlink=True)
        if template_mesh.users == 0:
            bpy.data.meshes.remove(template_mesh)


def rebuild(context, surface, *, full_surface=False):
    """Calculate first; replace the generated result only after a successful build."""
    settings = surface.jewel_pave
    if settings.gem == surface:
        raise ValueError("The surface cannot also be the Gem Source")
    context.view_layer.update()
    depsgraph = context.evaluated_depsgraph_get()
    sampled = Surface(surface, depsgraph, settings.threshold, use_mask=not full_surface)
    mesh, envelope, metadata = _template_mesh(settings.gem, settings.diameter, depsgraph)
    template = points = group = None
    try:
        bounds = [surface.matrix_world @ Vector(corner) for corner in surface.bound_box]
        anchor = sum(bounds, Vector()) / 8.0
        anchor.z = max(v.z for v in bounds)
        if settings.use_cursor:
            anchor = context.scene.cursor.location.copy()
        layout = pack(sampled, diameter=settings.diameter, envelope_radius=envelope,
                      gap=settings.gap, border=settings.border, offset=settings.offset,
                      angle=settings.angle, preferred_axis=surface.matrix_world.to_3x3() @ Vector((1, 0, 0)),
                      anchor=anchor, max_stones=settings.max_stones)
        points = bpy.data.meshes.new("Pave Placement Points")
        points.from_pydata([p.center for p in layout.placements], [], [])
        rotations = points.attributes.new("pave_rotation", 'FLOAT_VECTOR', 'POINT')
        normals = points.attributes.new("pave_normal", 'FLOAT_VECTOR', 'POINT')
        surface_points = points.attributes.new("pave_surface_point", 'FLOAT_VECTOR', 'POINT')
        visible = points.attributes.new("pave_visible", 'BOOLEAN', 'POINT')
        identifiers = points.attributes.new("id", 'INT', 'POINT')
        identifiers.data.foreach_set('value', list(range(len(layout.placements))))
        for index, placement in enumerate(layout.placements):
            frame = Matrix((placement.tangent, placement.normal.cross(placement.tangent),
                            placement.normal)).transposed()
            rotations.data[index].vector = frame.to_euler('XYZ')
            normals.data[index].vector = placement.normal
            surface_points.data[index].vector = placement.surface_point
            visible.data[index].value = not full_surface
        template = bpy.data.objects.new("Pave Source | " + surface.name, mesh)
        template[ROLE], template[OWNER] = "TEMPLATE", surface
        template["gem"] = metadata
        template.hide_render = True
        template.hide_select = True
        group = _instance_group(template)
    except Exception:
        _cleanup_output_data(points, group, template)
        if template is None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        raise

    output = settings.output
    old_mesh = old_group = old_template = None
    if _owned(output, surface, "OUTPUT"):
        old_mesh = output.data
        modifier = next((m for m in output.modifiers if m.type == 'NODES'
                         and m.node_group and m.node_group.get(ROLE) == "NODES"), None)
        old_group = modifier.node_group if modifier else None
        old_template = output.get("pave_template")
        collection = output.users_collection[0] if output.users_collection else context.scene.collection
        output.data = points
    else:
        collection = bpy.data.collections.new("Pave | " + surface.name)
        collection[ROLE], collection[OWNER] = "COLLECTION", surface
        context.scene.collection.children.link(collection)
        output = bpy.data.objects.new("Pave | " + surface.name, points)
        output[ROLE], output[OWNER] = "OUTPUT", surface
        collection.objects.link(output)
        modifier = None
    collection.objects.link(template)
    template.hide_set(True)
    modifier = modifier or output.modifiers.new("Surface Pave", 'NODES')
    modifier.node_group = group
    output["pave_template"] = template
    output["stone_count"] = 0 if full_surface else len(layout.placements)
    output["candidate_count"] = len(layout.placements)
    output["pave_layout_mode"] = "LIVE" if full_surface else "PACKED"
    output["pave_geometry_key"] = sampled.geometry_key()
    output["pave_live_error"] = ""
    output["minimum_center_distance_mm"] = layout.pitch
    output["limit_reached"] = layout.limited
    output.parent = surface
    output.matrix_parent_inverse = surface.matrix_world.inverted()
    output.matrix_basis = Matrix.Identity(4)
    output.hide_set(False)
    settings.output = output
    _cleanup_output_data(old_mesh, old_group, old_template)
    context.view_layer.update()
    return output


class OBJECT_OT_pave_use_surface(Operator):
    bl_idname = "object.pave_use_surface"
    bl_label = "Use Active Surface"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and _mesh_poll(None, context.active_object)

    def execute(self, context):
        _finish_paint(context)
        context.scene.jewel_pave_surface = context.active_object
        return {'FINISHED'}


class OBJECT_OT_pave_mask(Operator):
    bl_idname = "object.pave_mask"
    bl_label = "Edit Pave Mask"
    bl_options = {'REGISTER', 'UNDO'}

    action: EnumProperty(items=[('PAINT', "Paint", "Paint the included area"),
                               ('ERASE', "Erase", "Erase the included area"),
                               ('FILL', "Fill Surface", "Include the entire surface"),
                               ('CLEAR', "Clear Mask", "Clear all mask weights"),
                               ('DONE', "Finish Painting", "Return to Object Mode")])

    def execute(self, context):
        try:
            surface = _target(context)
            _activate(context, surface)
            _finish_paint(context)
            if self.action == 'DONE':
                _restore_paint(context, surface)
                return {'FINISHED'}
            group = _mask(surface)
            if self.action in {'FILL', 'CLEAR'}:
                _restore_paint(context, surface)
                indices = list(range(len(surface.data.vertices)))
                if indices:
                    group.add(indices, 1.0 if self.action == 'FILL' else 0.0, 'REPLACE')
                surface.data.update()
                if surface.jewel_pave.live_preview:
                    pave_live.prepare(context, surface)
                    self.report({'INFO'}, "Mask and live gems updated")
                else:
                    self.report({'INFO'}, "Mask updated; press Build / Rebuild Pave")
                return {'FINISHED'}
            if surface.jewel_pave.live_preview:
                preview = pave_live.prepare(context, surface)
                if preview.get("limit_reached"):
                    self.report({'WARNING'}, "Live layout reached the stone limit; raise it to cover the whole surface")
            if not surface.jewel_pave.paint_state:
                tools = context.tool_settings
                tool_keys = ("use_auto_normalize", "use_multipaint", "use_lock_relative")
                mesh_keys = ("use_paint_mask", "use_paint_mask_vertex", "use_mirror_x",
                             "use_mirror_y", "use_mirror_z", "use_mirror_vertex_groups")
                paint_keys = ("use_symmetry_x", "use_symmetry_y", "use_symmetry_z")
                unified = tools.weight_paint.unified_paint_settings
                surface.jewel_pave.paint_state = json.dumps({
                    "tools": {key: getattr(tools, key) for key in tool_keys},
                    "mesh": {key: getattr(surface.data, key) for key in mesh_keys},
                    "paint": {key: getattr(tools.weight_paint, key) for key in paint_keys},
                    "unified": {key: getattr(unified, key) for key in ("use_unified_weight", "weight")},
                    "restrict": tools.weight_paint.use_group_restrict,
                    "output_hidden": surface.jewel_pave.output.hide_get() if surface.jewel_pave.output else False,
                    "output_hide_select": surface.jewel_pave.output.hide_select if surface.jewel_pave.output else False,
                })
                for key in tool_keys:
                    setattr(tools, key, False)
                for key in mesh_keys:
                    setattr(surface.data, key, False)
                for key in paint_keys:
                    setattr(tools.weight_paint, key, False)
                tools.weight_paint.use_group_restrict = False
            if _owned(surface.jewel_pave.output, surface, "OUTPUT"):
                surface.jewel_pave.output.hide_set(not surface.jewel_pave.live_preview)
                surface.jewel_pave.output.hide_select = True
            bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
            bpy.ops.brush.asset_activate(asset_library_type='ESSENTIALS',
                relative_asset_identifier='brushes/essentials_brushes-mesh_weight.blend/Brush/Paint')
            brush = context.tool_settings.weight_paint.brush
            if brush is None:
                raise ValueError("Activate a Weight Paint brush to paint PaveMask")
            brush.use_frontface = True
            brush.falloff_shape = 'SPHERE'
            brush.blend = 'MIX'
            brush.weight = 0.0 if self.action == 'ERASE' else 1.0
            unified = context.tool_settings.weight_paint.unified_paint_settings
            unified.use_unified_weight = True
            unified.weight = brush.weight
            if context.area and context.area.type == 'VIEW_3D':
                bpy.ops.wm.tool_set_by_id(name="builtin.brush")
            if surface.jewel_pave.live_preview:
                pave_live.start(context, surface)
            return {'FINISHED'}
        except (ValueError, RuntimeError, AttributeError) as error:
            if 'surface' in locals():
                if surface.mode == 'WEIGHT_PAINT':
                    bpy.ops.object.mode_set(mode='OBJECT')
                _restore_paint(context, surface)
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


class OBJECT_OT_pave_build(Operator):
    bl_idname = "object.pave_build"
    bl_label = "Build / Rebuild Pave"
    bl_description = "Fill the mask with round gems; rebuild after changing paint, geometry or settings"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            surface = _target(context)
            _activate(context, surface)
            _finish_paint(context)
            context.window_manager.progress_begin(0, 1)
            output = rebuild(context, surface)
        except (ValueError, RuntimeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        finally:
            context.window_manager.progress_end()
        count = output['stone_count']
        if not count:
            self.report({'INFO'}, "No stones fit the current mask; the previous layout was cleared")
        elif output['limit_reached']:
            self.report({'WARNING'}, f"Built {count} gems; stone limit reached, the surface may be incomplete")
        else:
            self.report({'INFO'}, f"Built {count} round gems")
        return {'FINISHED'}


class OBJECT_OT_pave_refresh_live(Operator):
    bl_idname = "object.pave_refresh_live"
    bl_label = "Refresh Live Layout"
    bl_description = "Recalculate fixed positions after changing the surface, source or layout settings"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            surface = _target(context)
            _activate(context, surface)
            _finish_paint(context)
            _mask(surface)
            output = pave_live.prepare(context, surface, force=True)
            self.report({'INFO'}, f"Prepared {output['candidate_count']} fixed positions")
            return {'FINISHED'}
        except (ValueError, RuntimeError) as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


class VIEW3D_PT_surface_pave(Panel):
    bl_idname = "VIEW3D_PT_surface_pave"
    bl_label = "Surface Pave"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Jewelry"

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, "jewel_pave_surface", text="Surface")
        layout.operator("object.pave_use_surface", icon='EYEDROPPER')
        surface = context.scene.jewel_pave_surface
        if surface is None:
            layout.label(text="Select a mesh and use it as the surface.")
            return
        settings = surface.jewel_pave
        painting = surface.mode == 'WEIGHT_PAINT' and bool(settings.paint_state)
        mask = layout.box()
        mask.label(text="Painted Area", icon='WPAINT_HLT')
        row = mask.row()
        row.enabled = not painting
        row.prop(settings, "live_preview")
        if settings.live_preview:
            mask.prop(settings, "show_mask")
        row = mask.row(align=True)
        row.operator("object.pave_mask", text="Paint", icon='BRUSH_DATA').action = 'PAINT'
        row.operator("object.pave_mask", text="Erase").action = 'ERASE'
        row = mask.row(align=True)
        row.operator("object.pave_mask", text="Fill Surface").action = 'FILL'
        row.operator("object.pave_mask", text="Clear Mask").action = 'CLEAR'
        if surface.mode == 'WEIGHT_PAINT' or settings.paint_state:
            mask.operator("object.pave_mask", text="Finish Painting").action = 'DONE'
        row = mask.row()
        row.enabled = not painting
        row.prop(settings, "threshold")
        if settings.live_preview:
            mask.label(text="Paint to add gems; erase to remove them.")
        else:
            mask.label(text="Paint on the visible side; red is included.")
        if len(surface.data.vertices) < 100:
            mask.label(text="Coarse mesh: subdivide for a finer mask.", icon='INFO')
        controls = layout.column()
        controls.enabled = not painting
        controls.prop(settings, "gem")
        if settings.gem is None:
            controls.label(text="Source: bundled round diamond")
        col = controls.column(align=True)
        for name in ("diameter", "gap", "border", "offset", "angle"):
            col.prop(settings, name)
        controls.prop(settings, "use_cursor")
        controls.prop(settings, "max_stones")
        if settings.live_preview:
            controls.operator("object.pave_refresh_live", icon='FILE_REFRESH')
        layout.operator("object.pave_build", text="Repack Painted Area", icon='GEOMETRY_NODES')
        if _owned(settings.output, surface, "OUTPUT"):
            output = settings.output
            if output.get('pave_layout_mode') == 'LIVE':
                layout.label(text=f"Live: {output.get('stone_count', 0)} / {output.get('candidate_count', 0)} gems")
            else:
                layout.label(text=f"Last build: {output.get('stone_count', 0)} gems")
            if output.get('limit_reached'):
                layout.label(text="Stone limit reached; increase it to fill more.", icon='ERROR')
            if output.get('pave_live_error'):
                layout.label(text=output['pave_live_error'], icon='ERROR')
            elif not settings.live_preview:
                layout.label(text="Rebuild after changing the mask or surface.")
        layout.label(text="1 Blender unit = 1 mm")


_CLASSES = (SurfacePaveSettings, OBJECT_OT_pave_use_surface, OBJECT_OT_pave_mask,
            OBJECT_OT_pave_build, OBJECT_OT_pave_refresh_live, VIEW3D_PT_surface_pave)


def register():
    registered = []
    object_property = False
    scene_property = False
    try:
        for cls in _CLASSES:
            bpy.utils.register_class(cls)
            registered.append(cls)
        bpy.types.Object.jewel_pave = PointerProperty(type=SurfacePaveSettings)
        object_property = True
        bpy.types.Scene.jewel_pave_surface = PointerProperty(type=bpy.types.Object, poll=_mesh_poll)
        scene_property = True
        pave_live.register()
    except Exception:
        pave_live.unregister()
        if scene_property:
            del bpy.types.Scene.jewel_pave_surface
        if object_property:
            del bpy.types.Object.jewel_pave
        for cls in reversed(registered):
            bpy.utils.unregister_class(cls)
        raise


def unregister():
    _finish_paint(bpy.context)
    pave_live.unregister()
    del bpy.types.Scene.jewel_pave_surface
    del bpy.types.Object.jewel_pave
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
