# Инструменты раскладки граней (bmesh, Edit Mode, выделенные грани).
# Пункты в меню Face и контекстном меню Edit Mode.
#
#   Even Gap Faces       — равный ЗАЗОР между гранями по оси (размер граней сохраняется).
#   Spread Faces         — раздвинуть грани от центра/курсора с коэффициентом.
#   Shuffle Faces        — поменять грани позициями (перемешать) по сиду.
#   Insert Faces Between — вставить грань между соседними (усреднённый размер).

import bpy, bmesh
from mathutils import Vector


# ---------- 1. Spread Faces ----------
class MESH_OT_spread_faces(bpy.types.Operator):
    bl_idname = "mesh.spread_faces"
    bl_label = "Spread Faces (keep size)"
    bl_options = {'REGISTER', 'UNDO'}
    factor: bpy.props.FloatProperty(name="Factor", default=1.5, min=0.0, soft_max=5.0)
    from_cursor: bpy.props.BoolProperty(name="From 3D Cursor", default=False)

    def execute(self, context):
        obj = context.edit_object
        bm = bmesh.from_edit_mesh(obj.data)
        faces = [f for f in bm.faces if f.select]
        if not faces:
            self.report({'WARNING'}, "No faces selected"); return {'CANCELLED'}
        if self.from_cursor:
            pivot = obj.matrix_world.inverted() @ context.scene.cursor.location
        else:
            pivot = sum((f.calc_center_median() for f in faces), Vector()) / len(faces)
        k = self.factor - 1.0
        for f in faces:
            off = (f.calc_center_median() - pivot) * k
            for v in f.verts:
                v.co += off
        bmesh.update_edit_mesh(obj.data)
        return {'FINISHED'}


# ---------- 2. Even Gap Faces (равное расстояние по оси) ----------
class MESH_OT_even_gap_faces(bpy.types.Operator):
    bl_idname = "mesh.even_gap_faces"
    bl_label = "Even Gap Faces (keep size)"
    bl_options = {'REGISTER', 'UNDO'}
    gap: bpy.props.FloatProperty(name="Gap", default=0.3, min=0.0, soft_max=10.0)
    axis: bpy.props.EnumProperty(name="Axis",
        items=[('AUTO', 'Auto', ''), ('X', 'X', ''), ('Y', 'Y', ''), ('Z', 'Z', '')], default='AUTO')

    def execute(self, context):
        obj = context.edit_object
        bm = bmesh.from_edit_mesh(obj.data)
        faces = [f for f in bm.faces if f.select]
        if len(faces) < 2:
            self.report({'WARNING'}, "Select 2+ faces"); return {'CANCELLED'}
        data = [(f, f.calc_center_median()) for f in faces]
        if self.axis == 'AUTO':
            ext = [max(c[ai] for _, c in data) - min(c[ai] for _, c in data) for ai in range(3)]
            ai = ext.index(max(ext))
        else:
            ai = {'X': 0, 'Y': 1, 'Z': 2}[self.axis]
        data.sort(key=lambda d: d[1][ai])
        w = lambda f: max(v.co[ai] for v in f.verts) - min(v.co[ai] for v in f.verts)
        f0, c0 = data[0]
        prev_edge = c0[ai] + w(f0) / 2.0
        for f, c in data[1:]:
            wf = w(f)
            delta = (prev_edge + self.gap + wf / 2.0) - c[ai]
            for v in f.verts:
                v.co[ai] += delta
            prev_edge = prev_edge + self.gap + wf
        bmesh.update_edit_mesh(obj.data)
        return {'FINISHED'}


# ---------- 3. Shuffle Faces ----------
class MESH_OT_shuffle_faces(bpy.types.Operator):
    bl_idname = "mesh.shuffle_faces"
    bl_label = "Shuffle Faces (swap positions)"
    bl_options = {'REGISTER', 'UNDO'}
    seed: bpy.props.IntProperty(name="Seed", default=0, min=0)

    def execute(self, context):
        import random
        obj = context.edit_object
        bm = bmesh.from_edit_mesh(obj.data)
        faces = [f for f in bm.faces if f.select]
        if len(faces) < 2:
            self.report({'WARNING'}, "Select 2+ faces"); return {'CANCELLED'}
        centers = [f.calc_center_median() for f in faces]
        idx = list(range(len(faces)))
        random.seed(self.seed); random.shuffle(idx)
        for i, f in enumerate(faces):
            delta = centers[idx[i]] - centers[i]
            for v in f.verts:
                v.co += delta
        bmesh.update_edit_mesh(obj.data)
        return {'FINISHED'}


# ---------- 4. Insert Faces Between ----------
class MESH_OT_insert_between_faces(bpy.types.Operator):
    bl_idname = "mesh.insert_between_faces"
    bl_label = "Insert Faces Between (avg size)"
    bl_options = {'REGISTER', 'UNDO'}
    axis: bpy.props.EnumProperty(name="Axis",
        items=[('AUTO', 'Auto', ''), ('X', 'X', ''), ('Y', 'Y', ''), ('Z', 'Z', '')], default='AUTO')

    def execute(self, context):
        import math
        obj = context.edit_object
        bm = bmesh.from_edit_mesh(obj.data)
        faces = [f for f in bm.faces if f.select]
        if len(faces) < 2:
            self.report({'WARNING'}, "Select 2+ faces"); return {'CANCELLED'}
        data = [(f, f.calc_center_median()) for f in faces]
        if self.axis == 'AUTO':
            ext = [max(c[k] for _, c in data) - min(c[k] for _, c in data) for k in range(3)]
            ai = ext.index(max(ext))
        else:
            ai = {'X': 0, 'Y': 1, 'Z': 2}[self.axis]
        data.sort(key=lambda d: d[1][ai])
        specs = []
        for (a, ca), (b, cb) in zip(data, data[1:]):
            mid = (ca + cb) * 0.5
            sa = math.sqrt(max(a.calc_area(), 1e-9))
            sb = math.sqrt(max(b.calc_area(), 1e-9))
            factor = ((sa + sb) * 0.5) / sa
            specs.append([mid + (v.co - ca) * factor for v in a.verts])
        for f in faces:
            f.select = False
            for v in f.verts:
                v.select = False
        for coords in specs:
            verts = [bm.verts.new(c) for c in coords]
            nf = bm.faces.new(verts); nf.select = True
        bmesh.ops.delete(bm, geom=faces, context='FACES')
        bm.normal_update()
        bmesh.update_edit_mesh(obj.data)
        return {'FINISHED'}


_classes = (
    MESH_OT_spread_faces,
    MESH_OT_even_gap_faces,
    MESH_OT_shuffle_faces,
    MESH_OT_insert_between_faces,
)


def _faces_menu(self, context):
    L = self.layout
    L.separator()
    L.operator("mesh.spread_faces", text="Spread Faces (keep size)")
    L.operator("mesh.even_gap_faces", text="Even Gap Faces (keep size)")
    L.operator("mesh.shuffle_faces", text="Shuffle Faces (swap positions)")
    L.operator("mesh.insert_between_faces", text="Insert Faces Between (avg size)")


_menus = (bpy.types.VIEW3D_MT_edit_mesh_faces, bpy.types.VIEW3D_MT_edit_mesh_context_menu)


def register():
    for c in _classes:
        bpy.utils.register_class(c)
    for mt in _menus:
        mt.append(_faces_menu)


def unregister():
    for mt in _menus:
        mt.remove(_faces_menu)
    for c in reversed(_classes):
        bpy.utils.unregister_class(c)
