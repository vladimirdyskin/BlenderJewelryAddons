"""
Pave Cutters — катеры на месте камней из объекта с Pave Rows, отдельным объектом (для Boolean).

Модификатор вешается на отдельный (пустой) меш-объект. Берёт итоговую геометрию Source
(Pave Rows и всё, что после него в стеке, например Z180), оставляет инстансы с меткой
pave_stone (камни; крапана без метки) и ставит на каждый Cutter с тем же transform.
Связь живая: правка раскладки (Gap, ластик и т.п.) сразу двигает катеры.

    Object Info (Source, Relative)          — в координатах объекта-катера
    Separate Geometry (Instance, pave_stone)
    Capture Instance Transform -> Instances to Points -> Instance on Points (Cutter)
    Set Instance Transform: T_камня * (сдвиг по Z камня, масштаб Cutter Scale)
    Realize (по умолчанию вкл — Boolean нужен меш)

У SampleCutter origin там же, где у SampleGem (рундист), поэтому transform камня подходит
катеру без поправок. Multiply Matrices в 5.2: результат = верхний вход * нижний.

Интерфейс: Source, Cutter, Cutter Scale, Z Offset, Realize. Сокеты только добавляются,
если их нет — повторный запуск скрипта не сбрасывает значения на модификаторах.
"""

import bpy

GROUP_NAME = "Pave Cutters"
ATTR_STONE = "pave_stone"

# (имя, тип, default, min, max)
SOCKETS = [
    ("Source", "NodeSocketObject", None, None, None),
    ("Cutter", "NodeSocketObject", None, None, None),
    ("Cutter Scale", "NodeSocketFloat", 1.0, 0.0, None),
    ("Z Offset", "NodeSocketFloat", 0.0, None, None),
    ("Realize", "NodeSocketBool", True, None, None),
]


def ensure_interface(ng):
    names = {(it.name, it.in_out) for it in ng.interface.items_tree if it.item_type == "SOCKET"}
    if ("Geometry", "OUTPUT") not in names:
        ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    if ("Geometry", "INPUT") not in names:
        ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    added = []
    for name, stype, default, mn, mx in SOCKETS:
        if (name, "INPUT") in names:
            continue
        s = ng.interface.new_socket(name, in_out="INPUT", socket_type=stype)
        if default is not None:
            s.default_value = default
        if mn is not None:
            s.min_value = mn
        if mx is not None:
            s.max_value = mx
        added.append((s.identifier, default))
    # новый сокет на уже существующем модификаторе в 5.2 получает 0 / False, а не default
    for obj in bpy.data.objects:
        for md in obj.modifiers:
            if md.type == "NODES" and md.node_group == ng:
                for ident, default in added:
                    if default is not None:
                        getattr(md.properties.inputs, ident).value = default


def build_group():
    ng = bpy.data.node_groups.get(GROUP_NAME)
    if ng is None:
        ng = bpy.data.node_groups.new(GROUP_NAME, "GeometryNodeTree")
    ng.is_modifier = True
    ensure_interface(ng)
    ng.nodes.clear()
    n, L = ng.nodes.new, ng.links.new

    gin = n("NodeGroupInput"); gin.location = (-1000, 0)
    src = n("GeometryNodeObjectInfo"); src.location = (-800, 0)
    src.transform_space = "RELATIVE"
    src.inputs["As Instance"].default_value = False

    # только камни
    flag = n("GeometryNodeInputNamedAttribute"); flag.location = (-800, -250)
    flag.data_type = "BOOLEAN"
    flag.inputs["Name"].default_value = ATTR_STONE
    sep = n("GeometryNodeSeparateGeometry"); sep.location = (-600, 0)
    sep.domain = "INSTANCE"

    # transform камня -> точки -> катеры с тем же transform
    itf = n("GeometryNodeInstanceTransform"); itf.location = (-600, -250)
    cap = n("GeometryNodeCaptureAttribute"); cap.location = (-400, 0)
    cap.domain = "INSTANCE"
    cap.capture_items.new("MATRIX", "Transform")
    to_pts = n("GeometryNodeInstancesToPoints"); to_pts.location = (-200, 0)
    cut = n("GeometryNodeObjectInfo"); cut.location = (-200, 250)
    cut.inputs["As Instance"].default_value = True
    iop = n("GeometryNodeInstanceOnPoints"); iop.location = (0, 0)

    # T_камня * (сдвиг по Z камня, масштаб)
    local = n("ShaderNodeCombineXYZ"); local.location = (0, -400)
    loc = n("FunctionNodeCombineTransform"); loc.location = (200, -300)
    sc = n("ShaderNodeCombineXYZ"); sc.location = (0, -550)
    mul = n("FunctionNodeMatrixMultiply"); mul.location = (400, -200)
    setx = n("GeometryNodeSetInstanceTransform"); setx.location = (400, 0)

    real = n("GeometryNodeRealizeInstances"); real.location = (600, -150)
    sw = n("GeometryNodeSwitch"); sw.location = (800, 0)
    sw.input_type = "GEOMETRY"
    rm = n("GeometryNodeRemoveAttribute"); rm.location = (1000, 0)
    rm.inputs["Name"].default_value = ATTR_STONE
    gout = n("NodeGroupOutput"); gout.location = (1200, 0)

    L(gin.outputs["Source"], src.inputs["Object"])
    L(src.outputs["Geometry"], sep.inputs["Geometry"])
    L(flag.outputs["Attribute"], sep.inputs["Selection"])
    L(sep.outputs["Selection"], cap.inputs["Geometry"])
    L(itf.outputs["Transform"], cap.inputs["Transform"])
    L(cap.outputs["Geometry"], to_pts.inputs["Instances"])
    L(gin.outputs["Cutter"], cut.inputs["Object"])
    L(to_pts.outputs["Points"], iop.inputs["Points"])
    L(cut.outputs["Geometry"], iop.inputs["Instance"])

    L(gin.outputs["Z Offset"], local.inputs["Z"])
    L(local.outputs["Vector"], loc.inputs["Translation"])
    L(gin.outputs["Cutter Scale"], sc.inputs["X"])
    L(gin.outputs["Cutter Scale"], sc.inputs["Y"])
    L(gin.outputs["Cutter Scale"], sc.inputs["Z"])
    L(sc.outputs["Vector"], loc.inputs["Scale"])
    L(cap.outputs["Transform"], mul.inputs[0])
    L(loc.outputs["Transform"], mul.inputs[1])
    L(iop.outputs["Instances"], setx.inputs["Instances"])
    L(mul.outputs[0], setx.inputs["Transform"])

    L(setx.outputs["Instances"], real.inputs["Geometry"])
    L(gin.outputs["Realize"], sw.inputs["Switch"])
    L(setx.outputs["Instances"], sw.inputs["False"])
    L(real.outputs["Geometry"], sw.inputs["True"])
    L(sw.outputs["Output"], rm.inputs["Geometry"])
    L(rm.outputs["Geometry"], gout.inputs["Geometry"])

    print("Node group '%s' rebuilt: %d nodes" % (GROUP_NAME, len(ng.nodes)))
    return ng


def make_object(source_name, cutter_name="SampleCutter", obj_name="Pave Cutters", collection=None):
    """Отдельный объект-катер: пустой меш + модификатор Pave Cutters. Переиспользуется, если уже есть."""
    ng = bpy.data.node_groups[GROUP_NAME]
    src = bpy.data.objects[source_name]
    obj = bpy.data.objects.get(obj_name)
    if obj is None:
        obj = bpy.data.objects.new(obj_name, bpy.data.meshes.new(obj_name))
        coll = collection or (src.users_collection[0] if src.users_collection else bpy.context.scene.collection)
        coll.objects.link(obj)
    obj.display_type = "WIRE"
    obj.hide_render = True
    md = next((m for m in obj.modifiers if m.type == "NODES" and m.node_group == ng), None)
    if md is None:
        md = obj.modifiers.new(GROUP_NAME, "NODES")
        md.node_group = ng
    ids = {s.name: s.identifier for s in ng.interface.items_tree if s.item_type == "SOCKET" and s.in_out == "INPUT"}
    getattr(md.properties.inputs, ids["Source"]).value = src
    getattr(md.properties.inputs, ids["Cutter"]).value = bpy.data.objects[cutter_name]
    obj.update_tag()
    print("Cutter object '%s' -> source '%s'" % (obj.name, source_name))
    return obj


def main():
    build_group()


if __name__ == "__main__":
    main()
