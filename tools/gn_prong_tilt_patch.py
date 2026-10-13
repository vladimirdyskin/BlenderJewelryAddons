"""
Наклон крапанов для группы «My_Gems_On_Curve».

Вход «Prong Tilt» (угол, панель Prong Setup): «+» — верхушки крапанов к камням,
«−» — наружу. Ось поворота — origin крапана (уровень кривой / камня).

Общая подгруппа «Prong Lean»: Rotate Instances в локальных осях инстанса,
ось = Offset x Z, где Offset — локальное смещение крапана от точки привязки.
Верхушка уходит против Offset, т.е. к точке привязки. Offset = 0 — поворота нет.
  - 2-Prong: Offset = ±Axis(Y Offset) по Duplicate Index -> левый/правый крапан
    наклоняются зеркально, поворот вокруг касательной к кривой. Крапан у шва
    и крайние (Prong at Start/End) идут этой же веткой.
  - 4-Prong: Offset = угловой вектор (±X, ±Y) по Duplicate Index mod 4 ->
    каждый крапан наклоняется к центру своего камня.

Попутно: в ветке 4-Prong узел «Transform Geometry» второй раз масштабировал крапан
на Prong Scale XY (float -> (s, s, s)): XY = s², Z = Scale Z * s, Z Offset тоже * s.
Узел удаляется, заготовка крапана идёт в Geometry to Instance напрямую.

Идемпотентно: повторный запуск удаляет узлы с префиксом PT и собирает заново.
"""

import math

import bpy

GROUP_NAME = "My_Gems_On_Curve"
LEAN_GROUP = "Prong Lean"
SOCKET_NAME = "Prong Tilt"
PANEL_NAME = "Prong Setup"
PREFIX = "PT "


def _item(ng, name, kind="SOCKET"):
    return next((i for i in ng.interface.items_tree
                 if i.item_type == kind and i.name == name
                 and (kind == "PANEL" or i.in_out == "INPUT")), None)


def _ensure_socket(ng):
    sock = _item(ng, SOCKET_NAME)
    if sock is None:
        panel = _item(ng, PANEL_NAME, "PANEL")
        sock = ng.interface.new_socket(SOCKET_NAME, in_out="INPUT", socket_type="NodeSocketFloat", parent=panel)
        sock.subtype = "ANGLE"
        sock.default_value = 0.0
        sock.min_value, sock.max_value = -math.pi / 2, math.pi / 2
        sock.description = "Lean prongs: positive tips toward the stones, negative outward"
        ng.interface.move_to_parent(sock, panel, _item(ng, "Z Offset").position + 1)
    return sock


def _lean_group():
    """Подгруппа: повернуть инстансы вокруг своего origin, верхушкой против Offset."""
    lg = bpy.data.node_groups.get(LEAN_GROUP) or bpy.data.node_groups.new(LEAN_GROUP, "GeometryNodeTree")
    lg.nodes.clear()
    lg.interface.clear()
    lg.description = "Rotate instances about their origin so the tip leans against Offset (toward the anchor)"
    lg.interface.new_socket("Instances", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    lg.interface.new_socket("Instances", in_out="INPUT", socket_type="NodeSocketGeometry")
    off = lg.interface.new_socket("Offset", in_out="INPUT", socket_type="NodeSocketVector")
    off.description = "Local offset of the instance from its anchor"
    ang = lg.interface.new_socket("Angle", in_out="INPUT", socket_type="NodeSocketFloat")
    ang.subtype = "ANGLE"

    N, L = lg.nodes, lg.links
    gin = N.new("NodeGroupInput")
    gin.location = (-600, 0)
    cross = N.new("ShaderNodeVectorMath")
    cross.operation = "CROSS_PRODUCT"
    cross.inputs[1].default_value = (0.0, 0.0, 1.0)
    cross.location = (-400, -120)
    to_rot = N.new("FunctionNodeAxisAngleToRotation")   # нулевая ось -> без поворота
    to_rot.location = (-200, -120)
    rot = N.new("GeometryNodeRotateInstances")
    rot.inputs["Local Space"].default_value = True
    rot.location = (0, 0)
    gout = N.new("NodeGroupOutput")
    gout.location = (200, 0)

    L.new(gin.outputs["Offset"], cross.inputs[0])
    L.new(cross.outputs["Vector"], to_rot.inputs["Axis"])
    L.new(gin.outputs["Angle"], to_rot.inputs["Angle"])
    L.new(gin.outputs["Instances"], rot.inputs["Instances"])
    L.new(to_rot.outputs["Rotation"], rot.inputs["Rotation"])
    L.new(rot.outputs["Instances"], gout.inputs["Instances"])
    return lg


def _fix_4prong_scale(ng):
    N, L = ng.nodes, ng.links
    extra = N.get("Transform Geometry")
    if extra is not None:
        N.remove(extra)
    L.new(N["Transform Geometry.001"].outputs["Geometry"], N["Geometry to Instance"].inputs[0])


def patch(ng):
    N, L = ng.nodes, ng.links
    for n in [n for n in N if n.name.startswith(PREFIX)]:
        N.remove(n)

    _ensure_socket(ng)
    lean = _lean_group()
    _fix_4prong_scale(ng)

    def node(kind, name, anchor, dx, dy):
        n = N.new(kind)
        n.name = n.label = PREFIX + name
        n.parent = anchor.parent
        n.location = (anchor.location.x + dx, anchor.location.y + dy)
        return n

    def lean_node(name, anchor, dx, dy):
        n = node("GeometryNodeGroup", name, anchor, dx, dy)
        n.node_tree = lean
        gin = node("NodeGroupInput", name + " Input", anchor, dx - 200, dy - 120)
        for s in gin.outputs:
            s.hide = s.name != SOCKET_NAME
        L.new(gin.outputs[SOCKET_NAME], n.inputs["Angle"])
        return n

    # --- 2-Prong: левый / правый крапан по Duplicate Index ---
    dup2 = N["Duplicate Elements"]
    axis2 = N["Group"]                       # LB_Axis Offset (Y Offset)
    tr2 = N["Translate Instances.001"]       # последний сдвиг в цепочке 2-Prong
    side = node("GeometryNodeSwitch", "Side Offset", tr2, 250, -220)
    side.input_type = "VECTOR"
    L.new(dup2.outputs["Duplicate Index"], side.inputs["Switch"])
    L.new(axis2.outputs[1], side.inputs["False"])     # -Axis: индекс 0
    L.new(axis2.outputs[0], side.inputs["True"])      # +Axis: индекс 1
    lean2 = lean_node("Lean 2", tr2, 450, 0)
    L.new(tr2.outputs["Instances"], lean2.inputs["Instances"])
    L.new(side.outputs[0], lean2.inputs["Offset"])
    L.new(lean2.outputs["Instances"], N["Switch.002"].inputs["False"])

    # --- 4-Prong: угловой вектор по Duplicate Index mod 4 (как Compare.001..004) ---
    tr4 = N["Translate Instances.005"]       # последний сдвиг в цепочке 4-Prong
    corner = node("GeometryNodeIndexSwitch", "Corner Offset", tr4, 250, -220)
    corner.data_type = "VECTOR"
    while len(corner.index_switch_items) < 4:
        corner.index_switch_items.new()
    L.new(N["Math.006"].outputs[0], corner.inputs["Index"])
    for i, vm in enumerate(("Vector Math", "Vector Math.001", "Vector Math.002", "Vector Math.003")):
        L.new(N[vm].outputs["Vector"], corner.inputs[i + 1])
    lean4 = lean_node("Lean 4", tr4, 450, 0)
    L.new(tr4.outputs["Instances"], lean4.inputs["Instances"])
    L.new(corner.outputs[0], lean4.inputs["Offset"])
    L.new(lean4.outputs["Instances"], N["Instance on Points.002"].inputs["Instance"])

    print("Patched '%s' with Prong Tilt" % ng.name)
    return ng


def main():
    patch(bpy.data.node_groups[GROUP_NAME])


if __name__ == "__main__":
    main()
