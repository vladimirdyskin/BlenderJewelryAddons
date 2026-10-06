"""
Solidify XY — толщина строго в плоскости XY, высота (Z) не меняется.

Задача: у открытой поверхности (конический каст, лента кольца) сделать стенку
заданной толщины так, чтобы верхний и нижний края остались на своих Z.
Штатный Solidify гонит толщину по нормали и поэтому «раздувает» деталь по высоте.

Математика:
    направление сдвига  d = normalize(N.x, N.y, 0)
    величина сдвига     s = Thickness / |N_xy|
    итого               offset = (N.x, N.y, 0) * Thickness / (N.x^2 + N.y^2)

Проверка: скалярное произведение offset на нормаль даёт ровно Thickness,
то есть перпендикулярная толщина стенки честная, а движение — горизонтальное.
Знаменатель ограничен снизу, иначе горизонтальные грани (N_xy = 0) улетают в бесконечность.

Интерфейс группы:
    Geometry  — вход
    Thickness — реальная толщина стенки по нормали
    Offset    — куда растёт: +1 наружу (исходная поверхность = внутренняя),
                -1 внутрь (исходная = наружная), 0 симметрично

Скрипт идемпотентен: повторный запуск пересобирает группу с тем же именем,
не плодя дубликаты, и сохраняет уже проставленные значения на модификаторах.
"""

import bpy

GROUP_NAME = "Solidify XY"
EPS = 0.001  # нижняя отсечка знаменателя


def build_group():
    """Собрать (или пересобрать) node group. Возвращает готовую группу."""
    ng = bpy.data.node_groups.get(GROUP_NAME)
    if ng is None:
        ng = bpy.data.node_groups.new(GROUP_NAME, "GeometryNodeTree")
    else:
        # чистим содержимое, но сам datablock оставляем — ссылки в модификаторах живут
        ng.nodes.clear()
        ng.interface.clear()

    # --- интерфейс ---
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    s_thick = ng.interface.new_socket("Thickness", in_out="INPUT", socket_type="NodeSocketFloat")
    s_thick.default_value = 1.0
    s_thick.min_value = 0.0
    s_thick.max_value = 1000.0
    s_off = ng.interface.new_socket("Offset", in_out="INPUT", socket_type="NodeSocketFloat")
    s_off.default_value = -1.0
    s_off.min_value = -1.0
    s_off.max_value = 1.0
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    n = ng.nodes.new
    gin = n("NodeGroupInput");  gin.location = (-900, 0)
    gout = n("NodeGroupOutput"); gout.location = (700, 0)

    # --- вектор сдвига ---
    normal = n("GeometryNodeInputNormal"); normal.location = (-900, -260)
    sep = n("ShaderNodeSeparateXYZ");      sep.location = (-720, -260)
    comb = n("ShaderNodeCombineXYZ");      comb.location = (-540, -260)
    comb.inputs["Z"].default_value = 0.0

    # dot(base, base) = N.x^2 + N.y^2
    dot = n("ShaderNodeVectorMath"); dot.location = (-540, -440)
    dot.operation = "DOT_PRODUCT"

    clamp = n("ShaderNodeMath"); clamp.location = (-360, -440)
    clamp.operation = "MAXIMUM"
    clamp.inputs[1].default_value = EPS

    k = n("ShaderNodeMath"); k.location = (-180, -440)
    k.operation = "DIVIDE"  # Thickness / (N.x^2 + N.y^2)

    offvec = n("ShaderNodeVectorMath"); offvec.location = (0, -300)
    offvec.operation = "SCALE"

    # --- предсдвиг исходной поверхности под режим Offset ---
    # факт = (Offset - 1) * 0.5 : +1 -> 0, 0 -> -0.5, -1 -> -1
    fsub = n("ShaderNodeMath"); fsub.location = (-180, 220)
    fsub.operation = "SUBTRACT"
    fsub.inputs[1].default_value = 1.0

    fmul = n("ShaderNodeMath"); fmul.location = (0, 220)
    fmul.operation = "MULTIPLY"
    fmul.inputs[1].default_value = 0.5

    preshift = n("ShaderNodeVectorMath"); preshift.location = (180, 120)
    preshift.operation = "SCALE"

    setpos = n("GeometryNodeSetPosition"); setpos.location = (360, 0)

    extrude = n("GeometryNodeExtrudeMesh"); extrude.location = (520, 0)
    extrude.mode = "FACES"
    extrude.inputs["Individual"].default_value = False
    extrude.inputs["Offset Scale"].default_value = 1.0

    # Extrude Mesh выбрасывает исходные грани — остаётся смещённая оболочка плюс борта.
    # Возвращаем исходник обратно, вывернув нормали (он становится внутренней стенкой),
    # и завариваем общие вершины на границах.
    flip = n("GeometryNodeFlipFaces"); flip.location = (520, 260)
    join = n("GeometryNodeJoinGeometry"); join.location = (700, 120)
    merge = n("GeometryNodeMergeByDistance"); merge.location = (880, 120)
    merge.inputs["Distance"].default_value = 1e-5
    gout.location = (1060, 120)

    L = ng.links.new
    L(normal.outputs["Normal"], sep.inputs["Vector"])
    L(sep.outputs["X"], comb.inputs["X"])
    L(sep.outputs["Y"], comb.inputs["Y"])
    L(comb.outputs["Vector"], dot.inputs[0])
    L(comb.outputs["Vector"], dot.inputs[1])
    L(dot.outputs["Value"], clamp.inputs[0])
    L(gin.outputs["Thickness"], k.inputs[0])
    L(clamp.outputs["Value"], k.inputs[1])
    L(comb.outputs["Vector"], offvec.inputs[0])
    L(k.outputs["Value"], offvec.inputs["Scale"])

    L(gin.outputs["Offset"], fsub.inputs[0])
    L(fsub.outputs["Value"], fmul.inputs[0])
    L(offvec.outputs["Vector"], preshift.inputs[0])
    L(fmul.outputs["Value"], preshift.inputs["Scale"])

    L(gin.outputs["Geometry"], setpos.inputs["Geometry"])
    L(preshift.outputs["Vector"], setpos.inputs["Offset"])
    L(setpos.outputs["Geometry"], extrude.inputs["Mesh"])
    L(offvec.outputs["Vector"], extrude.inputs["Offset"])
    L(setpos.outputs["Geometry"], flip.inputs["Mesh"])
    L(extrude.outputs["Mesh"], join.inputs["Geometry"])
    L(flip.outputs["Mesh"], join.inputs["Geometry"])
    L(join.outputs["Geometry"], merge.inputs["Geometry"])
    L(merge.outputs["Geometry"], gout.inputs["Geometry"])

    print("Node group '%s' rebuilt: %d nodes" % (GROUP_NAME, len(ng.nodes)))
    return ng


def _set_input(md, identifier, value):
    """Записать значение входа GN-модификатора.

    В Blender 5.x входы переехали из IDProperties в md.properties.inputs:
    сокет доступен как атрибут по идентификатору, значение лежит в .value
    (рядом .type VALUE/ATTRIBUTE и .attribute_name). До 5.x работал md[identifier].
    """
    props = getattr(md, "properties", None)
    if props is not None and hasattr(props, "inputs"):
        getattr(props.inputs, identifier).value = value
    else:
        md[identifier] = value


def attach(obj_name, thickness=1.0, offset=-1.0, index=0):
    """Повесить группу на объект. Модификатор переиспользуется, если уже есть."""
    obj = bpy.data.objects[obj_name]
    ng = bpy.data.node_groups[GROUP_NAME]
    md = next((m for m in obj.modifiers if m.type == "NODES" and m.node_group == ng), None)
    if md is None:
        md = obj.modifiers.new(GROUP_NAME, "NODES")
        md.node_group = ng
        name = md.name
        obj.modifiers.move(obj.modifiers.find(name), index)
        md = obj.modifiers[name]  # после move прежняя ссылка невалидна
    ids = {s.name: s.identifier for s in ng.interface.items_tree
           if s.item_type == "SOCKET" and s.in_out == "INPUT"}
    _set_input(md, ids["Thickness"], thickness)
    _set_input(md, ids["Offset"], offset)
    obj.update_tag()
    print("Modifier attached to %s: thickness=%.3f offset=%.1f" % (obj_name, thickness, offset))
    return md


def main():
    build_group()


if __name__ == "__main__":
    main()
