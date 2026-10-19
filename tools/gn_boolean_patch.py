"""
Boolean (Difference) для группы «My_Gems_On_Curve»: режущее тело вычитается из
крапанов и кастов; камни не режутся и всегда остаются инстансами.

Входы (панель Boolean): «Boolean» — включить, «Boolean Object» — режущее тело,
«Fast Solver» — Manifold вместо Exact (замер на 240 телах в режиме Realize: 0.13 с против
6.5 с), но только для замкнутых мешей: с незамкнутым телом задетые копии исчезают.

Срез стоит в самом конце, после зеркала (Triple Mirror), чтобы зеркальные ряды
резались настоящим телом, даже несимметричным.
  - До общего Join касты и крапана помечаются флагом «Body» (Capture, домен Instance).
  - Инстансы (Realize выключен): тела отделяются от камней; контейнеры 4-Prong
    (внутри только вложенные инстансы, Instance Bounds = 0) разворачиваются на один
    уровень — каждый крапан становится отдельным инстансом. Задета ли копия: сфера по
    Instance Bounds в мировых осях; задета, если поверхность тела ближе радиуса или
    центр внутри тела (нормаль ближайшей точки). Задетые реализуются и режутся,
    остальные остаются инстансами (экспорт iJewel переиспользует их меш).
    У зеркальных копий (det матрицы < 0) после Realize грани вывернуты — Flip Faces.
  - Realize включён: всё уже меш — режутся все тела (флаг на точках).
  Новые грани среза получают Metal Material.

Идемпотентно: повторный запуск удаляет узлы с префиксом BO и собирает заново.
"""

import bpy

GROUP_NAME = "My_Gems_On_Curve"
PANEL_NAME = "Boolean"
PREFIX = "BO "


def _socket(ng, name):
    return next((i for i in ng.interface.items_tree if i.item_type == "SOCKET"
                 and i.in_out == "INPUT" and i.name == name), None)


def _ensure_sockets(ng):
    panel = next((i for i in ng.interface.items_tree if i.item_type == "PANEL" and i.name == PANEL_NAME), None)
    if panel is None:
        panel = ng.interface.new_panel(PANEL_NAME)
    if _socket(ng, "Boolean") is None:
        s = ng.interface.new_socket("Boolean", in_out="INPUT", socket_type="NodeSocketBool", parent=panel)
        s.default_value = False
        s.description = "Cut prongs and casts with Boolean Object; stones are never cut"
    if _socket(ng, "Boolean Object") is None:
        s = ng.interface.new_socket("Boolean Object", in_out="INPUT", socket_type="NodeSocketObject", parent=panel)
        s.description = "Cutting body, subtracted from prongs and casts"
    if _socket(ng, "Fast Solver") is None:
        s = ng.interface.new_socket("Fast Solver", in_out="INPUT", socket_type="NodeSocketBool", parent=panel)
        s.default_value = False
        s.description = ("Manifold solver: much faster, but prongs, casts and the cutting body must be "
                         "closed meshes, otherwise cut copies disappear")


def _enabled(node, name):
    return next(s for s in node.inputs if s.name == name and s.enabled)


def _link_once(L, out_socket, in_socket):
    if not any(l.from_socket == out_socket for l in in_socket.links):
        L.new(out_socket, in_socket)


def patch(ng):
    N, L = ng.nodes, ng.links
    for n in [n for n in N if n.name.startswith(PREFIX)]:
        N.remove(n)

    join = N["Join Geometry"]
    casts = N["Instance on Points.001"].outputs["Instances"]
    prongs = N["Switch.017"].outputs[0]
    mirror = N["Group.010"].outputs[0]
    gout = N["Group Output"]
    # вернуть исходные связи (на случай повторного запуска)
    _link_once(L, casts, join.inputs[0])
    _link_once(L, prongs, join.inputs[0])
    L.new(mirror, gout.inputs[0])

    _ensure_sockets(ng)

    x0, y0 = gout.location_absolute
    def node(kind, name, dx, dy, **props):
        n = N.new(kind)
        n.name = n.label = PREFIX + name
        n.location = (x0 + dx, y0 + dy)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def vmath(name, op, dx, dy):
        return node("ShaderNodeVectorMath", name, dx, dy, operation=op)

    def compare(name, op, dx, dy, b=None):
        c = node("FunctionNodeCompare", name, dx, dy, data_type="FLOAT", operation=op)
        if b is not None:
            _enabled(c, "B").default_value = b
        return c

    # --- флаг «тело» на кастах и крапанах ---
    body_join = node("GeometryNodeJoinGeometry", "Body Join", -600, -600)
    flag = node("GeometryNodeCaptureAttribute", "Body Flag", -400, -600, domain="INSTANCE")
    flag.capture_items.new("BOOLEAN", "Body")
    flag.inputs["Body"].default_value = True
    for link in [l for l in join.inputs[0].links if l.from_socket in (casts, prongs)]:
        L.remove(link)
    L.new(casts, body_join.inputs[0])
    L.new(prongs, body_join.inputs[0])
    L.new(body_join.outputs[0], flag.inputs["Geometry"])
    L.new(flag.outputs["Geometry"], join.inputs[0])
    body = flag.outputs["Body"]

    # --- входы и режущее тело ---
    gin = node("NodeGroupInput", "Input", 0, -400)
    for s in gin.outputs:
        s.hide = s.name not in ("Boolean", "Boolean Object", "Fast Solver", "Realize", "Metal Material")
    obj = node("GeometryNodeObjectInfo", "Object", 200, -400, transform_space="RELATIVE")
    obj.inputs["As Instance"].default_value = False
    cutter_real = node("GeometryNodeRealizeInstances", "Cutter", 400, -400)
    L.new(gin.outputs["Boolean Object"], obj.inputs["Object"])
    L.new(obj.outputs["Geometry"], cutter_real.inputs["Geometry"])
    cutter = cutter_real.outputs[0]

    # --- инстансы: тела отдельно, контейнеры 4-Prong развернуть ---
    split = node("GeometryNodeSeparateGeometry", "Split Body", 200, -700, domain="INSTANCE")
    L.new(mirror, split.inputs["Geometry"])
    L.new(body, split.inputs["Selection"])
    b0 = node("GeometryNodeInputInstanceBounds", "Bounds", 200, -900)
    size0 = vmath("Size", "SUBTRACT", 400, -900)
    len0 = vmath("Size Length", "LENGTH", 600, -900)
    is_box = compare("Is Container", "LESS_EQUAL", 800, -900, 0.0)
    flat = node("GeometryNodeRealizeInstances", "Flatten", 1000, -700)
    flat.inputs["Realize All"].default_value = False
    flat.inputs["Depth"].default_value = 1
    L.new(b0.outputs["Max"], size0.inputs[0])
    L.new(b0.outputs["Min"], size0.inputs[1])
    L.new(size0.outputs["Vector"], len0.inputs[0])
    L.new(len0.outputs["Value"], _enabled(is_box, "A"))
    L.new(split.outputs["Selection"], flat.inputs["Geometry"])
    L.new(is_box.outputs["Result"], flat.inputs["Selection"])

    # --- задета ли копия: сфера по Instance Bounds в осях объекта ---
    b1 = node("GeometryNodeInputInstanceBounds", "Bounds Copy", 1000, -1000)
    xf = node("GeometryNodeInstanceTransform", "Transform", 1000, -1200)
    mid = vmath("Center Sum", "ADD", 1200, -1000)
    mid2 = vmath("Center Local", "SCALE", 1400, -1000)
    mid2.inputs["Scale"].default_value = 0.5
    half = vmath("Half Size", "SUBTRACT", 1200, -1150)
    half2 = vmath("Half Local", "SCALE", 1400, -1150)
    half2.inputs["Scale"].default_value = 0.5
    center = node("FunctionNodeTransformPoint", "Center", 1600, -1000)
    halfw = node("FunctionNodeTransformDirection", "Half World", 1600, -1150)
    radius = vmath("Radius", "LENGTH", 1800, -1150)
    prox = node("GeometryNodeProximity", "Proximity", 1800, -900, target_element="FACES")
    normal = node("GeometryNodeInputNormal", "Cutter Normal", 1600, -1300)
    nearest_n = node("GeometryNodeSampleNearestSurface", "Nearest Normal", 1800, -1300, data_type="FLOAT_VECTOR")
    to_c = vmath("To Center", "SUBTRACT", 2000, -1000)
    dot = vmath("Side", "DOT_PRODUCT", 2200, -1100)
    inside = compare("Inside", "LESS_THAN", 2400, -1100, 0.0)
    near = compare("Near", "LESS_THAN", 2200, -900)
    hit = node("FunctionNodeBooleanMath", "Near or Inside", 2600, -1000, operation="OR")
    touched = node("FunctionNodeBooleanMath", "Touched", 2800, -1000, operation="AND")

    L.new(b1.outputs["Min"], mid.inputs[0]); L.new(b1.outputs["Max"], mid.inputs[1])
    L.new(mid.outputs["Vector"], mid2.inputs[0])
    L.new(b1.outputs["Max"], half.inputs[0]); L.new(b1.outputs["Min"], half.inputs[1])
    L.new(half.outputs["Vector"], half2.inputs[0])
    L.new(mid2.outputs["Vector"], center.inputs["Vector"]); L.new(xf.outputs["Transform"], center.inputs["Transform"])
    L.new(half2.outputs["Vector"], halfw.inputs["Direction"]); L.new(xf.outputs["Transform"], halfw.inputs["Transform"])
    L.new(halfw.outputs["Direction"], radius.inputs[0])
    L.new(cutter, prox.inputs["Geometry"]); L.new(center.outputs["Vector"], prox.inputs["Sample Position"])
    L.new(cutter, nearest_n.inputs["Mesh"]); L.new(normal.outputs["Normal"], nearest_n.inputs["Value"])
    L.new(center.outputs["Vector"], nearest_n.inputs["Sample Position"])
    L.new(center.outputs["Vector"], to_c.inputs[0]); L.new(prox.outputs["Position"], to_c.inputs[1])
    L.new(to_c.outputs["Vector"], dot.inputs[0]); L.new(nearest_n.outputs["Value"], dot.inputs[1])
    L.new(dot.outputs["Value"], _enabled(inside, "A"))
    L.new(prox.outputs["Distance"], _enabled(near, "A")); L.new(radius.outputs["Value"], _enabled(near, "B"))
    L.new(near.outputs["Result"], hit.inputs[0]); L.new(inside.outputs["Result"], hit.inputs[1])
    L.new(hit.outputs[0], touched.inputs[0]); L.new(prox.outputs["Is Valid"], touched.inputs[1])

    split_t = node("GeometryNodeSeparateGeometry", "Split Touched", 3000, -700, domain="INSTANCE")
    L.new(flat.outputs[0], split_t.inputs["Geometry"])
    L.new(touched.outputs[0], split_t.inputs["Selection"])

    # --- задетые: зеркальные (det < 0) после Realize вывернуты -> Flip Faces ---
    det = node("FunctionNodeMatrixDeterminant", "Determinant", 3000, -900)
    neg = compare("Mirrored", "LESS_THAN", 3200, -900, 0.0)
    mflag = node("GeometryNodeCaptureAttribute", "Mirrored Flag", 3200, -700, domain="INSTANCE")
    mflag.capture_items.new("BOOLEAN", "Mirrored")
    real = node("GeometryNodeRealizeInstances", "Realize Touched", 3400, -700)
    flip = node("GeometryNodeFlipFaces", "Fix Mirrored", 3600, -700)
    L.new(xf.outputs["Transform"], det.inputs[0])
    L.new(det.outputs[0], _enabled(neg, "A"))
    L.new(split_t.outputs["Selection"], mflag.inputs["Geometry"])
    L.new(neg.outputs["Result"], mflag.inputs["Mirrored"])
    L.new(mflag.outputs["Geometry"], real.inputs["Geometry"])
    L.new(real.outputs[0], flip.inputs["Mesh"])
    L.new(mflag.outputs["Mirrored"], flip.inputs["Selection"])
    keep_inst = node("GeometryNodeJoinGeometry", "Keep Instances", 3600, -500)
    L.new(split_t.outputs["Inverted"], keep_inst.inputs[0])
    L.new(split.outputs["Inverted"], keep_inst.inputs[0])

    # --- Realize включён: всё уже меш, тела по флагу на точках ---
    split_m = node("GeometryNodeSeparateGeometry", "Split Body Mesh", 3400, -300, domain="POINT")
    L.new(mirror, split_m.inputs["Geometry"])
    L.new(body, split_m.inputs["Selection"])

    src = node("GeometryNodeSwitch", "Cut Source", 3800, -600, input_type="GEOMETRY")
    keep = node("GeometryNodeSwitch", "Keep", 3800, -400, input_type="GEOMETRY")
    for sw in (src, keep):
        L.new(gin.outputs["Realize"], sw.inputs["Switch"])
    L.new(flip.outputs[0], src.inputs["False"]); L.new(split_m.outputs["Selection"], src.inputs["True"])
    L.new(keep_inst.outputs[0], keep.inputs["False"]); L.new(split_m.outputs["Inverted"], keep.inputs["True"])

    # Exact + Self Intersection: верно при перекрытии крапана и каста и для незамкнутого тела.
    # Manifold в разы быстрее, но на незамкнутом теле молча отдаёт пустоту.
    cut = node("GeometryNodeMeshBoolean", "Cut", 4000, -600, operation="DIFFERENCE", solver="EXACT")
    cut.inputs["Self Intersection"].default_value = True
    fast = node("GeometryNodeMeshBoolean", "Cut Fast", 4000, -800, operation="DIFFERENCE", solver="MANIFOLD")
    solver = node("GeometryNodeSwitch", "Solver", 4200, -700, input_type="GEOMETRY")
    metal = node("GeometryNodeSetMaterial", "Metal", 4400, -600)
    result = node("GeometryNodeJoinGeometry", "Result", 4600, -500)
    on = node("GeometryNodeSwitch", "On", 4800, -300, input_type="GEOMETRY")
    for b in (cut, fast):
        L.new(src.outputs[0], b.inputs["Mesh 1"]); L.new(cutter, b.inputs["Mesh 2"])
    L.new(gin.outputs["Fast Solver"], solver.inputs["Switch"])
    L.new(cut.outputs["Mesh"], solver.inputs["False"]); L.new(fast.outputs["Mesh"], solver.inputs["True"])
    L.new(solver.outputs[0], metal.inputs["Geometry"])
    L.new(gin.outputs["Metal Material"], metal.inputs["Material"])
    L.new(metal.outputs[0], result.inputs[0]); L.new(keep.outputs[0], result.inputs[0])
    L.new(gin.outputs["Boolean"], on.inputs["Switch"])
    L.new(mirror, on.inputs["False"]); L.new(result.outputs[0], on.inputs["True"])
    L.new(on.outputs[0], gout.inputs[0])

    print("Patched '%s' with Boolean" % ng.name)
    return ng


def main():
    patch(bpy.data.node_groups[GROUP_NAME])


if __name__ == "__main__":
    main()
