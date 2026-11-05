"""
Шаг поворота для группы «Circular Instance Array».

Вход «Step Rotation» (угол): элемент массива с индексом i поворачивается на
i * Step Rotation вокруг нормали исходной грани (локальная Z исходника) через
origin инстанса. 0 — как раньше. 180° — элементы чередуются: у грани, смещённой
от origin по Y, половина уходит в +Y, половина в −Y (число элементов должно быть
чётным, иначе первый и последний окажутся рядом с одной стороны).

Исходник уже повёрнут на Instant Rotation внутри Transform Geometry, поэтому
в осях инстанса его Z — это (0, 0, 1), повёрнутый на Instant Rotation.
Поворот добавляется к выравниванию по нормали точки в локальных осях (Rotate
Rotation, Local) прямо на входе Rotation узла Instance on Points: Index считается
на точках окружности, Instance Selection нумерацию не сбивает.

Идемпотентно: повторный запуск удаляет узлы с префиксом SR и собирает заново.
"""

import bpy

GROUP_NAME = "Circular Instance Array"
SOCKET_NAME = "Step Rotation"
PREFIX = "SR "


def _ensure_socket(ng):
    sock = next((i for i in ng.interface.items_tree
                 if i.item_type == "SOCKET" and i.in_out == "INPUT" and i.name == SOCKET_NAME), None)
    if sock is None:
        sock = ng.interface.new_socket(SOCKET_NAME, in_out="INPUT", socket_type="NodeSocketFloat")
        sock.subtype = "ANGLE"
        sock.default_value = 0.0
        sock.description = "Each next instance turns by this angle around the source face normal"
    return sock


def main(group_name=GROUP_NAME):
    ng = bpy.data.node_groups[group_name]
    _ensure_socket(ng)

    for node in [n for n in ng.nodes if n.name.startswith(PREFIX)]:
        ng.nodes.remove(node)

    def add(bl_idname, name, x, y):
        node = ng.nodes.new(bl_idname)
        node.name = node.label = PREFIX + name
        node.location = (iop.location.x + x, iop.location.y + y)
        return node

    iop = ng.nodes["Instance on Points"]
    align = ng.nodes["Switch"].outputs["Output"]

    # Узлы ставим под фреймом выравнивания, слева направо по ходу данных
    group_in = add("NodeGroupInput", "Group Input", -900, -960)
    index = add("GeometryNodeInputIndex", "Index", -900, -1140)
    angle = add("ShaderNodeMath", "Angle", -680, -1060)
    axis = add("FunctionNodeRotateVector", "Axis", -680, -900)
    step = add("FunctionNodeAxisAngleToRotation", "Step", -460, -960)
    rotate = add("FunctionNodeRotateRotation", "Rotate", -240, -920)

    angle.operation = "MULTIPLY"
    axis.inputs["Vector"].default_value = (0.0, 0.0, 1.0)
    rotate.rotation_space = "LOCAL"

    links = ng.links
    links.new(index.outputs["Index"], angle.inputs[0])
    links.new(group_in.outputs[SOCKET_NAME], angle.inputs[1])
    links.new(group_in.outputs["Instant Rotation"], axis.inputs["Rotation"])
    links.new(axis.outputs[0], step.inputs["Axis"])
    links.new(angle.outputs[0], step.inputs["Angle"])
    links.new(align, rotate.inputs["Rotation"])
    links.new(step.outputs[0], rotate.inputs["Rotate By"])
    links.new(rotate.outputs[0], iop.inputs["Rotation"])

    print(f"Step Rotation patched: {group_name}")


if __name__ == "__main__":
    main()
