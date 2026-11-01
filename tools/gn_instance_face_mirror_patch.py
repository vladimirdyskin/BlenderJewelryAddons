"""
Mirror внутри "My Instance Face": зеркалим готовые инстансы, центральные не дублируем.

Задача: в одной сетке разложить грани под инстансы и отзеркалить их без модификатора
Mirror в стеке. Грань, центр которой лежит на плоскости зеркала (|координата| <= EPS),
по этой оси не копируется — инстанс посередине остаётся один.

Как устроено — подгруппа "Mirror Instances" сразу после Instance on Points
(до Realize), оси по очереди X -> Y -> Z:
    R    = Object Info(Mirror Object, Relative).Transform — система зеркала в координатах
           объекта; пустой Mirror Object даёт единичную матрицу = зеркало по origin
    отбор: ось включена и |(R^-1 * позиция инстанса)[ось]| > EPS
    копия: Duplicate Elements (Instance) -> Set Instance Transform  S_w * T * F
           S_w = R * S * R^-1 — отражение по оси в системе зеркала (S = diag(-1) по оси)
           F   = diag(1, -1, 1) — разворот локальной Y инстанса
    Join с оригиналами

У копии X и Z (нормаль грани) — зеркало оригинала, Y развёрнута, det > 0:
повёрнутая копия без отрицательного масштаба (Realize не выворачивает грани).
Тот же результат, что Mirror-модификатор + UV-патч Face Rotation, но без зависимости
от порядка углов и UV.

Multiply Matrices в 5.2: результат = верхний вход * нижний (проверено на точке).

Интерфейс (панель "Mirror" во внутренней и внешней группах):
    Mirror X / Mirror Y / Mirror Z — по умолчанию выключены (старые кольца с Mirror
    в стеке не задваиваются), Mirror Object — центр и оси зеркала.

Скрипт идемпотентен: подгруппа пересобирается на месте, узлы врезки — с префиксом "MI ".
"""

import bpy

MIRROR_GROUP = "Mirror Instances"
INNER = "Instance Face"
OUTER = "My Instance Face"
EPS = 0.001
PREFIX = "MI "
AXES = ("X", "Y", "Z")


def build_mirror_group():
    """Собрать (или пересобрать) подгруппу зеркала инстансов."""
    ng = bpy.data.node_groups.get(MIRROR_GROUP)
    if ng is None:
        ng = bpy.data.node_groups.new(MIRROR_GROUP, "GeometryNodeTree")
    ng.nodes.clear()
    # интерфейс не пересоздаём: при очистке рвутся связи узлов, которые ссылаются на группу
    if not len(ng.interface.items_tree):
        ng.interface.new_socket("Instances", in_out="INPUT", socket_type="NodeSocketGeometry")
        for a in AXES:
            ng.interface.new_socket("Mirror " + a, in_out="INPUT", socket_type="NodeSocketBool")
        ng.interface.new_socket("Mirror Object", in_out="INPUT", socket_type="NodeSocketObject")
        ng.interface.new_socket("Instances", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    N, L = ng.nodes, ng.links
    gin = N.new("NodeGroupInput"); gin.location = (-1400, 0)

    info = N.new("GeometryNodeObjectInfo"); info.location = (-1200, -300)
    info.transform_space = "RELATIVE"
    inv = N.new("FunctionNodeInvertMatrix"); inv.location = (-1000, -300)
    flip_y = N.new("FunctionNodeCombineTransform"); flip_y.location = (-1000, -500)
    flip_y.inputs["Scale"].default_value = (1, -1, 1)

    pos = N.new("GeometryNodeInputPosition"); pos.location = (-1000, -100)
    local = N.new("FunctionNodeTransformPoint"); local.location = (-800, -100)
    sep = N.new("ShaderNodeSeparateXYZ"); sep.location = (-600, -100)
    itf = N.new("GeometryNodeInstanceTransform"); itf.location = (-800, -500)

    L.new(gin.outputs["Mirror Object"], info.inputs["Object"])
    L.new(info.outputs["Transform"], inv.inputs["Matrix"])
    L.new(pos.outputs["Position"], local.inputs["Vector"])
    L.new(inv.outputs["Matrix"], local.inputs["Transform"])
    L.new(local.outputs["Vector"], sep.inputs["Vector"])

    geo = gin.outputs["Instances"]
    for i, a in enumerate(AXES):
        x = -400 + i * 700

        # отражение по оси в системе зеркала: R * S * R^-1
        s = N.new("FunctionNodeCombineTransform"); s.location = (x, -500)
        s.inputs["Scale"].default_value = tuple(-1 if k == i else 1 for k in range(3))
        rs = N.new("FunctionNodeMatrixMultiply"); rs.location = (x + 180, -450)
        mw = N.new("FunctionNodeMatrixMultiply"); mw.location = (x + 360, -450)
        L.new(info.outputs["Transform"], rs.inputs[0])
        L.new(s.outputs["Transform"], rs.inputs[1])
        L.new(rs.outputs[0], mw.inputs[0])
        L.new(inv.outputs["Matrix"], mw.inputs[1])

        # новый transform копии: S_w * T * F
        t1 = N.new("FunctionNodeMatrixMultiply"); t1.location = (x + 360, -650)
        t2 = N.new("FunctionNodeMatrixMultiply"); t2.location = (x + 540, -650)
        L.new(mw.outputs[0], t1.inputs[0])
        L.new(itf.outputs["Transform"], t1.inputs[1])
        L.new(t1.outputs[0], t2.inputs[0])
        L.new(flip_y.outputs["Transform"], t2.inputs[1])

        # отбор: ось включена и инстанс не на плоскости зеркала
        absv = N.new("ShaderNodeMath"); absv.location = (x, -150)
        absv.operation = "ABSOLUTE"
        cmp = N.new("FunctionNodeCompare"); cmp.location = (x + 180, -150)
        cmp.data_type = "FLOAT"
        cmp.operation = "GREATER_THAN"
        cmp.inputs[1].default_value = EPS  # 0/1 — float A/B (одноимённые сокеты других типов дальше)
        sel = N.new("FunctionNodeBooleanMath"); sel.location = (x + 360, -100)
        sel.operation = "AND"
        L.new(sep.outputs[a], absv.inputs[0])
        L.new(absv.outputs["Value"], cmp.inputs[0])
        L.new(gin.outputs["Mirror " + a], sel.inputs[0])
        L.new(cmp.outputs["Result"], sel.inputs[1])

        dup = N.new("GeometryNodeDuplicateElements"); dup.location = (x + 360, 150)
        dup.domain = "INSTANCE"
        setx = N.new("GeometryNodeSetInstanceTransform"); setx.location = (x + 540, 150)
        join = N.new("GeometryNodeJoinGeometry"); join.location = (x + 720, 250)
        L.new(geo, dup.inputs["Geometry"])
        L.new(sel.outputs["Boolean"], dup.inputs["Selection"])
        L.new(dup.outputs["Geometry"], setx.inputs["Instances"])
        L.new(t2.outputs[0], setx.inputs["Transform"])
        L.new(geo, join.inputs["Geometry"])
        L.new(setx.outputs["Instances"], join.inputs["Geometry"])
        geo = join.outputs["Geometry"]

    gout = N.new("NodeGroupOutput"); gout.location = (-400 + 3 * 700 + 200, 250)
    L.new(geo, gout.inputs["Instances"])
    print("Node group '%s' rebuilt: %d nodes" % (MIRROR_GROUP, len(N)))
    return ng


def ensure_mirror_sockets(ng):
    """Панель Mirror с Mirror X/Y/Z и Mirror Object в интерфейсе группы (если ещё нет)."""
    items = {it.name: it for it in ng.interface.items_tree}
    panel = items.get("Mirror")
    if panel is None or panel.item_type != "PANEL":
        panel = ng.interface.new_panel("Mirror")
    for a in AXES:
        if "Mirror " + a not in items:
            s = ng.interface.new_socket("Mirror " + a, in_out="INPUT", socket_type="NodeSocketBool", parent=panel)
            s.default_value = False
    if "Mirror Object" not in items:
        ng.interface.new_socket("Mirror Object", in_out="INPUT", socket_type="NodeSocketObject", parent=panel)


def patch(inner_name=INNER, outer_name=OUTER):
    mi = build_mirror_group()
    inner = bpy.data.node_groups[inner_name]
    outer = bpy.data.node_groups[outer_name]
    for ng in (inner, outer):
        ensure_mirror_sockets(ng)
    names = ["Mirror " + a for a in AXES] + ["Mirror Object"]

    # --- внутренняя группа: врезка после Instance on Points ---
    N, L = inner.nodes, inner.links
    iop = next(n for n in N if n.bl_idname == "GeometryNodeInstanceOnPoints")
    node = N.get(PREFIX + "Mirror")
    if node is None:
        node = N.new("GeometryNodeGroup")
        node.name = node.label = PREFIX + "Mirror"
        node.node_tree = mi
        node.location = (iop.location.x + 250, iop.location.y - 250)
    if not node.inputs["Instances"].links:
        # всё, что брало инстансы из Instance on Points, теперь берёт их после зеркала
        out = iop.outputs["Instances"]
        consumers = [l.to_socket for l in out.links if l.to_node != node]
        for l in list(out.links):
            L.remove(l)
        L.new(out, node.inputs["Instances"])
        for sock in consumers:
            L.new(node.outputs["Instances"], sock)
    gi = N.get(PREFIX + "Group Input")
    if gi is None:
        gi = N.new("NodeGroupInput")
        gi.name = gi.label = PREFIX + "Group Input"
        gi.location = (node.location.x - 250, node.location.y - 200)
    for nm in names:
        if not node.inputs[nm].links:
            L.new(gi.outputs[nm], node.inputs[nm])

    # --- внешняя группа: проброс входов в узел внутренней ---
    grp = next(n for n in outer.nodes if n.bl_idname == "GeometryNodeGroup" and n.node_tree == inner)
    ogin = next(n for n in outer.nodes if n.bl_idname == "NodeGroupInput")
    for nm in names:
        if not grp.inputs[nm].links:
            outer.links.new(ogin.outputs[nm], grp.inputs[nm])

    print("Mirror patch applied: %s -> %s" % (outer_name, inner_name))


def main():
    patch()


if __name__ == "__main__":
    main()
