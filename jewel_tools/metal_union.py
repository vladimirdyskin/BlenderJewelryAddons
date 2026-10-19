# SPDX-License-Identifier: GPL-3.0-or-later

"""
Металл для STL: меши и GN-инстансы выделенных объектов склеиваются в один замкнутый
меш — объект «Metal» в коллекции «Metal» (повторный запуск заменяет его меш).
Камни (объекты JewelCraft со свойством «gem») пропускаются, исходники не меняются.

- У зеркальных копий (det матрицы < 0) грани после переноса в меш вывернуты —
  разворачиваем, иначе Boolean выбрасывает их как дыры.
- Union: острова меша -> Split to Instances -> Mesh Boolean (Manifold). Одним мешем
  Manifold перекрытия не склеивает (замер на кольце: 261 оболочка), по островам —
  1 тело за 0.13 с с тем же объёмом, что Exact + Self Intersection за 13.6 с.
  Незамкнутый вход Manifold молча теряет — тогда Exact + Self Intersection.
- Катеры: если у GN-модификатора источника задан вход «Cutter» (My_Gems_On_Curve),
  его меш ставится по матрице каждого камня этого объекта (в группе катер и камень
  ставит один Instance on Points) и вычитается после union, тоже по островам.
  При Show Cutter катер сидит в металле — острова, совпадающие с частями катера (число
  вершин и габариты в локальных осях), из металла выкидываются, иначе на совпадающих
  гранях Manifold оставляет обрывки стенок катера, а посадки не дорезаны.
"""

from __future__ import annotations

import time

import bmesh
import bpy
from bpy.types import Operator
from mathutils import Vector

RESULT_NAME = "Metal"
# Отдельные куски меньше этого объёма после Boolean — численный мусор (щепки у касания
# шарика с кольцом), удаляются. 0.001 мм³ — кубик 0.1 мм, меньше не отлить.
MIN_PART_VOLUME = 1e-3


def _islands(bm: bmesh.types.BMesh) -> list:
    """Связные куски: списки вершин."""
    seen, islands = set(), []
    for vert in bm.verts:
        if vert.index in seen:
            continue
        seen.add(vert.index)
        verts, stack = [vert], [vert]
        while stack:
            for edge in stack.pop().link_edges:
                for v in edge.verts:
                    if v.index not in seen:
                        seen.add(v.index)
                        verts.append(v)
                        stack.append(v)
        islands.append(verts)
    return islands


def _signature(coords) -> tuple:
    """Число вершин и габариты — по ним остров узнаётся как катер."""
    coords = list(coords)
    return (len(coords), Vector([min(c[i] for c in coords) for i in range(3)]),
            Vector([max(c[i] for c in coords) for i in range(3)]))


def _same(a: tuple, b: tuple) -> bool:
    return a[0] == b[0] and (a[1] - b[1]).length < 1e-4 and (a[2] - b[2]).length < 1e-4


def _mesh_signatures(mesh: bpy.types.Mesh) -> list:
    bm = bmesh.new()
    bm.from_mesh(mesh)
    signatures = [_signature(v.co for v in verts) for verts in _islands(bm)]
    bm.free()
    return signatures


def _add_part(bm: bmesh.types.BMesh, mesh: bpy.types.Mesh, matrix, skip: list | None = None) -> None:
    """Меш в мировые координаты; острова с сигнатурами из skip (части катера) не берутся."""
    part = bmesh.new()
    part.from_mesh(mesh)
    if skip:
        doomed = [v for verts in _islands(part)
                  if any(_same(_signature(x.co for x in verts), sig) for sig in skip) for v in verts]
        if doomed:
            bmesh.ops.delete(part, geom=doomed, context="VERTS")
            part.verts.index_update()
    part.transform(matrix)
    if matrix.determinant() < 0:
        bmesh.ops.reverse_faces(part, faces=part.faces)
    verts = [bm.verts.new(v.co) for v in part.verts]
    for face in part.faces:
        try:
            bm.faces.new([verts[v.index] for v in face.verts])
        except ValueError:      # дубль грани
            pass
    part.free()


def _instances(context: bpy.types.Context, sources: set):
    """(источник, объект инстанса или None, данные, матрица) для всего, что выдают источники."""
    for inst in context.evaluated_depsgraph_get().object_instances:
        owner = inst.parent.original if inst.is_instance and inst.parent else inst.object.original
        if owner in sources:
            ref = inst.instance_object.original if inst.is_instance and inst.instance_object else None
            yield owner, ref, inst.object.data, inst.matrix_world.copy()


def _collect(context: bpy.types.Context, sources: set, skip: dict) -> bmesh.types.BMesh:
    """Весь металл источников одним bmesh в мировых координатах.
    skip: {источник: сигнатуры частей катера}. При Show Cutter катер сидит в одном инстансе с кастом;
    если оставить его в металле, union и difference идут по совпадающим граням, и Manifold
    оставляет обрывки стенок катера (полосы вывернутых граней), посадки не дорезаны."""
    bm = bmesh.new()
    for owner, ref, mesh, matrix in _instances(context, sources):
        if "gem" in (ref or owner):
            continue
        if isinstance(mesh, bpy.types.Mesh) and mesh.polygons:
            _add_part(bm, mesh, matrix, skip.get(owner))
    return bm


def _cutter_object(obj: bpy.types.Object):
    """Объект из входа «Cutter» видимого GN-модификатора (My_Gems_On_Curve)."""
    for md in obj.modifiers:
        if md.type != "NODES" or md.node_group is None or not md.show_viewport:
            continue
        sock = next((i for i in md.node_group.interface.items_tree if i.item_type == "SOCKET"
                     and i.in_out == "INPUT" and i.name == "Cutter" and i.socket_type == "NodeSocketObject"), None)
        if sock is not None:
            cutter = getattr(md.properties.inputs, sock.identifier).value
            if cutter is not None:
                return cutter
    return None


def _cutter_meshes(context: bpy.types.Context, sources: set) -> dict:
    """{источник: копия вычисленного меша катера}; удалить после работы."""
    depsgraph = context.evaluated_depsgraph_get()
    meshes = {}
    for obj in sources:
        cutter = _cutter_object(obj)
        if cutter is not None:
            mesh = bpy.data.meshes.new_from_object(cutter.evaluated_get(depsgraph))
            if mesh.polygons:
                meshes[obj] = mesh
            else:
                bpy.data.meshes.remove(mesh)
    return meshes


def _collect_cutters(context: bpy.types.Context, sources: set, cutter_meshes: dict):
    """Катеры по матрицам камней: (bmesh, сколько поставлено, объекты без видимых камней)."""
    bm = bmesh.new()
    count, no_gems = 0, []
    gems = {}
    for owner, ref, _data, matrix in _instances(context, sources):
        if ref is not None and "gem" in ref:
            gems.setdefault(owner, []).append(matrix)
    for obj, mesh in cutter_meshes.items():
        if not gems.get(obj):
            no_gems.append(obj.name)
            continue
        for matrix in gems[obj]:
            _add_part(bm, mesh, matrix)
            count += 1
    return bm, count, no_gems


def _union_group(exact: bool, cutters: bpy.types.Object | None) -> bpy.types.NodeTree:
    group = bpy.data.node_groups.new(".Metal Union", "GeometryNodeTree")
    group.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    group.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    nodes, links = group.nodes, group.links
    gin = nodes.new("NodeGroupInput")
    gout = nodes.new("NodeGroupOutput")
    island = nodes.new("GeometryNodeInputMeshIsland")

    def boolean(operation, geometry):
        """Каждый остров geometry — отдельный операнд Mesh 2."""
        split = nodes.new("GeometryNodeSplitToInstances")
        split.domain = "FACE"
        links.new(geometry, split.inputs["Geometry"])
        links.new(island.outputs["Island Index"], split.inputs["Group ID"])
        node = nodes.new("GeometryNodeMeshBoolean")
        node.operation = operation
        node.solver = "EXACT" if exact else "MANIFOLD"
        if exact:
            node.inputs["Self Intersection"].default_value = True
        links.new(split.outputs["Instances"], node.inputs["Mesh 2"])
        return node

    result = boolean("UNION", gin.outputs[0]).outputs["Mesh"]
    if cutters is not None:
        info = nodes.new("GeometryNodeObjectInfo")
        info.transform_space = "RELATIVE"
        info.inputs["Object"].default_value = cutters
        diff = boolean("DIFFERENCE", info.outputs["Geometry"])
        links.new(result, diff.inputs["Mesh 1"])
        result = diff.outputs["Mesh"]
    links.new(result, gout.inputs[0])
    return group


def _union(context: bpy.types.Context, mesh: bpy.types.Mesh, cutters: bpy.types.Mesh | None,
           exact: bool) -> bpy.types.Mesh:
    temps = [bpy.data.objects.new(".Metal Union", mesh)]
    if cutters is not None:
        temps.append(bpy.data.objects.new(".Metal Cutters", cutters))
    for temp in temps:
        context.scene.collection.objects.link(temp)
    group = _union_group(exact, temps[1] if cutters is not None else None)
    try:
        temps[0].modifiers.new("Union", "NODES").node_group = group
        context.view_layer.update()
        return bpy.data.meshes.new_from_object(temps[0].evaluated_get(context.evaluated_depsgraph_get()))
    finally:
        for temp in temps:
            bpy.data.objects.remove(temp)
        bpy.data.node_groups.remove(group)


def _parts(bm: bmesh.types.BMesh) -> list:
    """Связные куски меша: [(вершины, объём)]."""
    parts = [[verts, 0.0] for verts in _islands(bm)]
    part_of = {v.index: i for i, (verts, _volume) in enumerate(parts) for v in verts}
    for face in bm.faces:       # объём куска: сумма тетраэдров от начала координат
        p = [v.co for v in face.verts]
        parts[part_of[face.verts[0].index]][1] += sum(
            p[0].dot(p[i].cross(p[i + 1])) for i in range(1, len(p) - 1)) / 6.0
    return parts


def _result_object(context: bpy.types.Context, mesh: bpy.types.Mesh) -> bpy.types.Object:
    obj = bpy.data.objects.get(RESULT_NAME)
    if obj is not None and obj.type == "MESH":
        old = obj.data
        obj.data = mesh
        if old.users == 0:
            bpy.data.meshes.remove(old)
        return obj
    coll = bpy.data.collections.get(RESULT_NAME)
    if coll is None:
        coll = bpy.data.collections.new(RESULT_NAME)
    if coll.name not in context.scene.collection.children:
        context.scene.collection.children.link(coll)
    obj = bpy.data.objects.new(RESULT_NAME, mesh)
    coll.objects.link(obj)
    return obj


class OBJECT_OT_metal_union(Operator):
    bl_idname = "object.metal_union"
    bl_label = "Build Metal Mesh"
    bl_description = ("Join the metal of the selected objects (meshes and Geometry Nodes instances, "
                      "gems skipped) into one closed mesh, the object \"Metal\"")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return bool(context.selected_objects)

    def execute(self, context: bpy.types.Context):
        start = time.time()
        sources = {o for o in context.selected_objects if o.name != RESULT_NAME and "gem" not in o}
        cutter_meshes = _cutter_meshes(context, sources)
        try:
            skip = {obj: _mesh_signatures(mesh) for obj, mesh in cutter_meshes.items()}
            bm = _collect(context, sources, skip)
            cut_bm, cut_count, no_gems = _collect_cutters(context, sources, cutter_meshes)
        finally:
            for mesh in cutter_meshes.values():
                bpy.data.meshes.remove(mesh)
        if not bm.faces:
            bm.free()
            cut_bm.free()
            self.report({"WARNING"}, "No metal mesh found in the selected objects")
            return {"CANCELLED"}
        exact = any(not e.is_manifold for e in bm.edges) or any(not e.is_manifold for e in cut_bm.edges)
        source_mesh = bpy.data.meshes.new(".Metal Source")
        bm.to_mesh(source_mesh)
        bm.free()
        cutter_mesh = None
        if cut_count:
            cutter_mesh = bpy.data.meshes.new(".Metal Cutters")
            cut_bm.to_mesh(cutter_mesh)
        cut_bm.free()
        try:
            mesh = _union(context, source_mesh, cutter_mesh, exact)
        finally:
            bpy.data.meshes.remove(source_mesh)
            if cutter_mesh is not None:
                bpy.data.meshes.remove(cutter_mesh)

        bm = bmesh.new()
        bm.from_mesh(mesh)
        parts = _parts(bm)
        debris = [verts for verts, part_volume in parts if abs(part_volume) < MIN_PART_VOLUME]
        if debris:
            bmesh.ops.delete(bm, geom=[v for verts in debris for v in verts], context="VERTS")
        # микрорёбра после Boolean (на кольце 337 рёбер короче 0.01 мкм): схлопнуть,
        # объём и замкнутость не меняются
        bmesh.ops.dissolve_degenerate(bm, dist=1e-5, edges=bm.edges)
        bm.to_mesh(mesh)
        shells = len(parts) - len(debris)
        open_edges = sum(1 for e in bm.edges if not e.is_manifold)
        volume = bm.calc_volume(signed=True)
        bm.free()

        obj = _result_object(context, mesh)
        mesh.name = RESULT_NAME
        for o in context.selected_objects:
            o.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj

        units = context.scene.unit_settings
        if units.system == "NONE":      # как Pretty Ruler: 1 unit = 1 mm
            volume_text = "%.1f mm³" % volume
        else:
            volume_text = bpy.utils.units.to_string(units.system, "VOLUME", volume * units.scale_length ** 3)
        message = "Metal: %d verts, %d shell(s), volume %s, %d cutter(s) subtracted, %s solver, %.2f s" % (
            len(mesh.vertices), shells, volume_text, cut_count, "Exact" if exact else "Manifold", time.time() - start)
        if debris:
            message += ", %d debris piece(s) removed" % len(debris)
        problems = []
        if open_edges:
            problems.append("%d open edge(s)" % open_edges)
        if shells > 1:
            problems.append("separate parts!")
        if no_gems:
            problems.append("cutters skipped, no visible stones in: " + ", ".join(sorted(no_gems)))
        if problems:
            self.report({"WARNING"}, message + "; " + "; ".join(problems))
        else:
            self.report({"INFO"}, message)
        return {"FINISHED"}


_CLASSES = (OBJECT_OT_metal_union,)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister() -> None:
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
