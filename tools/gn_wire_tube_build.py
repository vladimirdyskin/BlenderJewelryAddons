"""
Wire Tube — трубка (проволока) по рёбрам меша, с развилками и скруглёнными концами.

Задача: из меша-«скелета» (только рёбра, ветки сходятся в узлах) получить одно
замкнутое тело — как литая филигрань: круглая проволока, полусферы на свободных
концах, плавный «пах» в местах, где ветка раздваивается.

Как устроено (через SDF, а не Curve to Mesh — у отдельных трубок в развилке
остаётся острая складка):
    Mesh to Curve       — режет сетку на ветки в узлах (валентность != 2)
    Resample Curve      — частые точки вдоль ветки, шаг = Voxel Size
    Points to SDF Grid  — шар радиуса Diameter/2 + Fillet в каждой точке:
                          цепочка шаров = трубка, раздутая на Fillet, на конце полусфера
    Grid to Mesh        — раздутое тело
    Mesh to SDF Grid    — заново в поле, с широкой полосой (Band Width >= Fillet)
    Grid to Mesh        — поверхность на глубине Fillet внутрь

Раздуть на k и ужать на k = морфологическое «закрытие»: выпуклое (трубка, концы)
возвращается точно к Diameter/2, а вогнутое (развилки) остаётся заполненным —
скругление катящимся шаром радиуса Fillet. Побочный эффект: щель между
проволоками уже 2 * Fillet тоже заливается.

Почему не SDF Offset / SDF Fillet по сетке от Points to SDF Grid (проверено в 5.2):
полоса у неё меньше 2 вокселей, значения в вокселях, а не в мм — Offset дальше
полосы срабатывает частично, Fillet даёт скругление в пару вокселей.
У Mesh to SDF Grid порог Grid to Mesh — в мм.

Рябь от шаров при шаге s и радиусе r ~ s^2 / (8r) — при s = Voxel Size меньше вокселя.

Интерфейс группы:
    Geometry   — меш из рёбер (после Subdivision, если он есть)
    Diameter   — диаметр проволоки
    Fillet     — радиус скругления развилок, мм (0 — без скругления)
    Voxel Size — разрешение; ~ Diameter / 20

Скрипт идемпотентен: повторный запуск пересобирает группу с тем же именем.
"""

import bpy

GROUP_NAME = "Wire Tube"


def build_group():
    """Собрать (или пересобрать) node group. Возвращает готовую группу."""
    ng = bpy.data.node_groups.get(GROUP_NAME)
    if ng is None:
        ng = bpy.data.node_groups.new(GROUP_NAME, "GeometryNodeTree")
    else:
        # чистим содержимое, datablock оставляем — ссылки в модификаторах живут
        ng.nodes.clear()
        ng.interface.clear()
    ng.is_modifier = True

    # --- интерфейс ---
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    s = ng.interface.new_socket("Diameter", in_out="INPUT", socket_type="NodeSocketFloat")
    s.default_value = 0.6
    s.min_value = 0.01
    s = ng.interface.new_socket("Fillet", in_out="INPUT", socket_type="NodeSocketFloat")
    s.default_value = 0.15
    s.min_value = 0.0
    s = ng.interface.new_socket("Voxel Size", in_out="INPUT", socket_type="NodeSocketFloat")
    s.default_value = 0.03
    s.min_value = 0.002
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    n = ng.nodes.new
    gin = n("NodeGroupInput"); gin.location = (-1000, 0)

    to_curve = n("GeometryNodeMeshToCurve"); to_curve.location = (-780, 80)
    to_curve.mode = "EDGES"

    resample = n("GeometryNodeResampleCurve"); resample.location = (-580, 80)
    resample.inputs["Mode"].default_value = "Length"  # в 5.x режим — menu-сокет
    resample.keep_last_segment = True  # короткую ветку не схлопывать в точку

    to_points = n("GeometryNodeCurveToPoints"); to_points.location = (-380, 80)
    to_points.mode = "EVALUATED"

    # радиус шаров = Diameter/2 + Fillet
    half = n("ShaderNodeMath"); half.location = (-580, -160)
    half.operation = "MULTIPLY"
    half.inputs[1].default_value = 0.5
    grow = n("ShaderNodeMath"); grow.location = (-380, -160)
    grow.operation = "ADD"

    sdf = n("GeometryNodePointsToSDFGrid"); sdf.location = (-180, 80)
    grown = n("GeometryNodeGridToMesh"); grown.location = (20, 80)
    grown.inputs["Threshold"].default_value = 0.0
    grown.inputs["Adaptivity"].default_value = 0.0

    # полоса поля в вокселях: ceil(Fillet / Voxel Size) + 2, чтобы уровень -Fillet был внутри
    band_div = n("ShaderNodeMath"); band_div.location = (20, -200)
    band_div.operation = "DIVIDE"
    band_ceil = n("ShaderNodeMath"); band_ceil.location = (200, -200)
    band_ceil.operation = "CEIL"
    band_add = n("ShaderNodeMath"); band_add.location = (380, -200)
    band_add.operation = "ADD"
    band_add.inputs[1].default_value = 2.0

    resdf = n("GeometryNodeMeshToSDFGrid"); resdf.location = (560, 80)

    shrink = n("ShaderNodeMath"); shrink.location = (560, -200)
    shrink.operation = "MULTIPLY"
    shrink.inputs[1].default_value = -1.0

    to_mesh = n("GeometryNodeGridToMesh"); to_mesh.location = (760, 80)
    to_mesh.inputs["Adaptivity"].default_value = 0.0

    smooth = n("GeometryNodeSetShadeSmooth"); smooth.location = (960, 80)
    gout = n("NodeGroupOutput"); gout.location = (1160, 80)

    L = ng.links.new
    L(gin.outputs["Geometry"], to_curve.inputs["Mesh"])
    L(to_curve.outputs["Curve"], resample.inputs["Curve"])
    L(gin.outputs["Voxel Size"], resample.inputs["Length"])
    L(resample.outputs["Curve"], to_points.inputs["Curve"])
    L(gin.outputs["Diameter"], half.inputs[0])
    L(half.outputs["Value"], grow.inputs[0])
    L(gin.outputs["Fillet"], grow.inputs[1])
    L(to_points.outputs["Points"], sdf.inputs["Points"])
    L(grow.outputs["Value"], sdf.inputs["Radius"])
    L(gin.outputs["Voxel Size"], sdf.inputs["Voxel Size"])
    L(sdf.outputs[0], grown.inputs["Grid"])

    L(gin.outputs["Fillet"], band_div.inputs[0])
    L(gin.outputs["Voxel Size"], band_div.inputs[1])
    L(band_div.outputs["Value"], band_ceil.inputs[0])
    L(band_ceil.outputs["Value"], band_add.inputs[0])
    L(grown.outputs["Mesh"], resdf.inputs["Mesh"])
    L(gin.outputs["Voxel Size"], resdf.inputs["Voxel Size"])
    L(band_add.outputs["Value"], resdf.inputs["Band Width"])

    L(gin.outputs["Fillet"], shrink.inputs[0])
    L(resdf.outputs[0], to_mesh.inputs["Grid"])
    L(shrink.outputs["Value"], to_mesh.inputs["Threshold"])
    L(to_mesh.outputs["Mesh"], smooth.inputs["Geometry"])
    L(smooth.outputs["Geometry"], gout.inputs["Geometry"])

    print("Node group '%s' rebuilt: %d nodes" % (GROUP_NAME, len(ng.nodes)))
    return ng


def main():
    build_group()


if __name__ == "__main__":
    main()
