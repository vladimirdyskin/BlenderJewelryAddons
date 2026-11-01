"""
Face Rotation: ось X инстанса по направлению U развёртки, а не по первому ребру грани.

Проблема: группа "Face Rotation" (внутри "Instance Face" / "My Instance Face") строит
поворот так: Z = нормаль грани, X = первое ребро (угол 0 -> угол 1). Модификатор Mirror
у отражённой грани разворачивает обход углов, оставляя первый на месте (0-1-2-3 -> 0-3-2-1),
первым ребром становится соседнее — у квада инстанс поворачивается на 90° вокруг нормали.
Грани, отражённые дважды (Mirror X+Y), снова в исходном порядке — у них всё верно.

Решение: X = направление, в котором растёт U на грани. UV-координата угла едет вместе
с вершиной (Mirror копирует её как есть), значит направление U на отражённой грани —
зеркальное направление оригинала, при любом порядке углов и любой оси Mirror.
У примитива Plane U растёт от угла 0 к углу 1 — для неотражённых граней поворот прежний.

Математика (ковариация позиции и U по углам грани):
    X = mean(P * u) - mean(P) * mean(u)
В графе одно поле S = P * u: Evaluate on Domain (Corner) от S в контексте грани даёт
mean(P * u), а S, вычисленное прямо на грани, — mean(P) * mean(u) (Position и UV
сами усредняются на грань).

Нет UV-слоя с именем UV_NAME — X по первому ребру, как раньше.
Отражённая сторона — повёрнутая копия, не зеркальная (для симметричных деталей одно и то же).
Mirror U / Mirror V в модификаторе Mirror должны быть выключены (иначе X развернётся на 180°).

Скрипт идемпотентен: узлы патча с префиксом "UV ", повторный запуск их пересобирает.
"""

import bpy

GROUP_NAME = "Face Rotation"
UV_NAME = "UVMap"
PREFIX = "UV "


def patch(group_name=GROUP_NAME):
    ng = bpy.data.node_groups[group_name]
    N, L = ng.nodes, ng.links

    # ось X: Align Euler to Vector с axis X (pivot Z) — её Vector и подменяем
    align_x = next(n for n in N if n.bl_idname == "FunctionNodeAlignEulerToVector" and n.axis == "X")
    # старый источник X: Vector Math SUBTRACT (угол 1 - угол 0)
    edge = next(n for n in N if n.bl_idname == "ShaderNodeVectorMath" and n.operation == "SUBTRACT"
                and not n.name.startswith(PREFIX))

    for n in [n for n in N if n.name.startswith(PREFIX)]:
        N.remove(n)

    def new(idname, name, loc):
        n = N.new(idname)
        n.name = n.label = PREFIX + name
        n.location = (edge.location.x + loc[0], edge.location.y + loc[1])
        return n

    uv = new("GeometryNodeInputNamedAttribute", "Attr", (-600, -250))
    uv.data_type = "FLOAT_VECTOR"  # FLOAT2 -> (u, v, 0)
    uv.inputs["Name"].default_value = UV_NAME
    sep = new("ShaderNodeSeparateXYZ", "U", (-400, -250))
    pos = new("GeometryNodeInputPosition", "Position", (-400, -400))

    s = new("ShaderNodeVectorMath", "P*u", (-200, -320))
    s.operation = "SCALE"
    mean = new("GeometryNodeFieldOnDomain", "Mean P*u", (0, -250))
    mean.domain = "CORNER"
    mean.data_type = "FLOAT_VECTOR"
    cov = new("ShaderNodeVectorMath", "Covariance", (200, -300))
    cov.operation = "SUBTRACT"

    sw = new("GeometryNodeSwitch", "Has UV", (400, -100))
    sw.input_type = "VECTOR"

    L.new(uv.outputs["Attribute"], sep.inputs["Vector"])
    L.new(pos.outputs["Position"], s.inputs[0])
    L.new(sep.outputs["X"], s.inputs["Scale"])
    L.new(s.outputs["Vector"], mean.inputs[0])
    L.new(mean.outputs[0], cov.inputs[0])
    L.new(s.outputs["Vector"], cov.inputs[1])

    L.new(uv.outputs["Exists"], sw.inputs["Switch"])
    L.new(edge.outputs["Vector"], sw.inputs["False"])
    L.new(cov.outputs["Vector"], sw.inputs["True"])
    L.new(sw.outputs["Output"], align_x.inputs["Vector"])

    print("Face Rotation UV patch applied to '%s'" % group_name)
    return ng


def main():
    patch()


if __name__ == "__main__":
    main()
