# Единая N-панель аддона (вкладка "Jewel" в сайдбаре вьюпорта).
# Поля снимка живут в Scene (PropertyGroup) и прокидываются в оператор при клике.

import bpy


class JewelSnapProps(bpy.types.PropertyGroup):
    resolution_x: bpy.props.IntProperty(name="Resolution X", default=4000, min=4, soft_max=16000)
    resolution_y: bpy.props.IntProperty(name="Resolution Y", default=4000, min=4, soft_max=16000)
    filepath: bpy.props.StringProperty(name="Output", default="/tmp/viewport_hi.png", subtype='FILE_PATH')
    file_format: bpy.props.EnumProperty(name="Format",
        items=[('PNG', 'PNG', ''), ('JPEG', 'JPEG', ''), ('TIFF', 'TIFF', '')], default='PNG')
    background: bpy.props.EnumProperty(name="Background",
        items=[('THEME', 'Theme', ''), ('TRANSPARENT', 'Transparent', ''), ('COLOR', 'Color', '')],
        default='THEME')
    bg_color: bpy.props.FloatVectorProperty(name="BG Color", subtype='COLOR', size=3,
        min=0.0, max=1.0, default=(0.05, 0.05, 0.05))
    layout: bpy.props.EnumProperty(name="Layout",
        items=[('SINGLE', 'Single', ''), ('QUAD', 'Quad 2x2', ''), ('SIDE', 'Side by side', '')],
        default='SINGLE')


class VIEW3D_PT_jewel_tools(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Jewel"
    bl_label = "Jewel Tools"

    def draw(self, context):
        L = self.layout
        p = context.scene.jewel_snap

        box = L.box()
        box.label(text="Hi-Res Snapshot", icon='RENDER_STILL')
        box.prop(p, "layout")
        col = box.column(align=True)
        col.prop(p, "resolution_x")
        col.prop(p, "resolution_y")
        box.prop(p, "file_format")
        box.prop(p, "background")
        if p.background == 'COLOR':
            box.prop(p, "bg_color")
        box.prop(p, "filepath")
        op = box.operator("render.hires_viewport_snapshot", text="Save Snapshot", icon='RENDER_STILL')
        op.resolution_x = p.resolution_x
        op.resolution_y = p.resolution_y
        op.filepath = p.filepath
        op.file_format = p.file_format
        op.background = p.background
        op.bg_color = p.bg_color
        op.layout = p.layout

        box = L.box()
        box.label(text="Face Tools (Edit Mode)", icon='FACESEL')
        col = box.column(align=True)
        col.operator("mesh.even_gap_faces", text="Even Gap")
        col.operator("mesh.spread_faces", text="Spread")
        col.operator("mesh.shuffle_faces", text="Shuffle")
        col.operator("mesh.insert_between_faces", text="Insert Between")

        box = L.box()
        box.label(text="Geometry Nodes", icon='NODETREE')
        box.operator("node.rebuild_instance_face", text="Rebuild Instance Face")


def register():
    bpy.utils.register_class(JewelSnapProps)
    bpy.types.Scene.jewel_snap = bpy.props.PointerProperty(type=JewelSnapProps)
    bpy.utils.register_class(VIEW3D_PT_jewel_tools)


def unregister():
    bpy.utils.unregister_class(VIEW3D_PT_jewel_tools)
    del bpy.types.Scene.jewel_snap
    bpy.utils.unregister_class(JewelSnapProps)
