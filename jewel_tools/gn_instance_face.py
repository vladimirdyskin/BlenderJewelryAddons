# Пересборка GN-графа "Instance Face" (inner) / "My Instance Face" (outer).
# Бывший build-скрипт gn_instance_face_build.py, обёрнут в оператор.
#
# Две фичи (добавляются в граф):
#   1) Масштаб инстанса от площади грани, квантованный шагом 0.1
#      (Face Area -> SQRT -> SNAP -> Capture FACE "size" -> Instance.Scale).
#   2) Подписи-размеры у каждой грани (Repeat Zone + Sample Index + String to Curves),
#      тумблер Show Size / Label Size в интерфейсе обеих групп.
#
# Предусловия сцены: inner-группа с узлами Capture Attribute(FACE), Mesh to Points(FACES),
# Instance on Points, Switch(realize); outer-группа — один Group-узел на inner.
# ВНИМАНИЕ: операция НЕ идемпотентна (создаёт узлы) — повторный запуск продублирует.
# Защита: если граф уже собран (есть узел с label "snap 0.1") — оператор откажет.

import bpy

INNER = "Instance Face"
OUTER = "My Instance Face"


def osock(node, name):
    return next(s for s in node.outputs if s.name == name)


def isock(node, name):
    return next(s for s in node.inputs if s.name == name)


def ensure_socket(ng, name, sock, default=None, mn=None):
    for it in ng.interface.items_tree:
        if getattr(it, "in_out", None) == "INPUT" and it.name == name:
            return it
    s = ng.interface.new_socket(name, in_out="INPUT", socket_type=sock)
    if default is not None:
        s.default_value = default
    if mn is not None:
        s.min_value = mn
    return s


def build_scale_from_area(ng):
    N, L = ng.nodes, ng.links
    m2p = N["Mesh to Points"]
    iop = N["Instance on Points"]

    src_link = next(l for l in L if l.to_node == m2p and l.to_socket.name == "Mesh")
    geo_from = src_link.from_socket

    fa = N.new("GeometryNodeInputMeshFaceArea")
    sq = N.new("ShaderNodeMath"); sq.operation = "SQRT"; sq.label = "sqrt area"
    sn = N.new("ShaderNodeMath"); sn.operation = "SNAP"; sn.label = "snap 0.1"
    sn.inputs[1].default_value = 0.1
    cap = N.new("GeometryNodeCaptureAttribute"); cap.domain = "FACE"
    cap.capture_items.new("FLOAT", "size")

    L.new(osock(fa, "Area"), sq.inputs[0])
    L.new(osock(sq, "Value"), sn.inputs[0])
    L.new(osock(sn, "Value"), cap.inputs[1])
    L.new(geo_from, isock(cap, "Geometry"))
    L.new(osock(cap, "Geometry"), isock(m2p, "Mesh"))
    L.new(cap.outputs[1], isock(iop, "Scale"))
    return cap


def build_size_hints(ng_inner, ng_outer):
    for ng in (ng_inner, ng_outer):
        ensure_socket(ng, "Show Size", "NodeSocketBool", default=False)
        ensure_socket(ng, "Label Size", "NodeSocketFloat", default=0.5, mn=0.0)

    outer_grp = next(n for n in ng_outer.nodes if n.bl_idname == "GeometryNodeGroup")
    gin = next(n for n in ng_outer.nodes if n.bl_idname == "NodeGroupInput")
    for nm in ("Show Size", "Label Size"):
        if not any(l for l in isock(outer_grp, nm).links):
            ng_outer.links.new(osock(gin, nm), isock(outer_grp, nm))

    N, L = ng_inner.nodes, ng_inner.links
    cap = N["Capture Attribute"]

    nrm = next((n for n in N if n.bl_idname == "GeometryNodeInputNormal"), None)
    if nrm is None:
        nrm = N.new("GeometryNodeInputNormal")
    if not any(s.name == "nrm" for s in cap.inputs):
        cap.capture_items.new("VECTOR", "nrm")
    nrm_in = next(s for s in cap.inputs if s.name == "nrm")
    if not nrm_in.links:
        L.new(osock(nrm, "Normal"), nrm_in)

    m2p = N["Mesh to Points"]
    pts = osock(m2p, "Points")
    gout = N.get("Group Output.001") or next(n for n in N if n.bl_idname == "NodeGroupOutput")
    realize_switch = N["Switch"]
    main_geo = osock(realize_switch, "Output")

    gi = N.new("NodeGroupInput"); gi.location = (-1400, -600)
    showsize = osock(gi, "Show Size")
    labelsize = osock(gi, "Label Size")

    X, Y = -1000, -700
    dsz = N.new("GeometryNodeAttributeDomainSize"); dsz.component = "POINTCLOUD"
    dsz.location = (X, Y)
    L.new(pts, isock(dsz, "Geometry"))

    rin = N.new("GeometryNodeRepeatInput"); rin.location = (X + 250, Y)
    rout = N.new("GeometryNodeRepeatOutput"); rout.location = (X + 1400, Y)
    rin.pair_with_output(rout)
    rout.repeat_items.new("INT", "i")
    L.new(osock(dsz, "Point Count"), isock(rin, "Iterations"))
    isock(rin, "i").default_value = 0

    posn = N.new("GeometryNodeInputPosition"); posn.location = (X + 200, Y - 300)

    def sample(dtype, valsock, y):
        s = N.new("GeometryNodeSampleIndex"); s.domain = "POINT"; s.data_type = dtype
        s.location = (X + 550, y)
        L.new(pts, isock(s, "Geometry"))
        L.new(osock(rin, "i"), isock(s, "Index"))
        L.new(valsock, isock(s, "Value"))
        return s

    si_pos = sample("FLOAT_VECTOR", osock(posn, "Position"), Y - 250)
    si_size = sample("FLOAT", osock(cap, "size"), Y - 450)
    si_nrm = sample("FLOAT_VECTOR", osock(cap, "nrm"), Y - 650)

    v2s = N.new("FunctionNodeValueToString"); v2s.location = (X + 780, Y - 450)
    L.new(osock(si_size, "Value"), isock(v2s, "Value"))
    isock(v2s, "Decimals").default_value = 1
    s2c = N.new("GeometryNodeStringToCurves"); s2c.location = (X + 960, Y - 450)
    L.new(osock(v2s, "String"), isock(s2c, "String"))
    L.new(labelsize, isock(s2c, "Size"))

    al = N.new("FunctionNodeAlignEulerToVector"); al.axis = "Z"; al.location = (X + 780, Y - 650)
    L.new(osock(si_nrm, "Value"), isock(al, "Vector"))
    vsc = N.new("ShaderNodeVectorMath"); vsc.operation = "SCALE"; vsc.location = (X + 780, Y - 250)
    L.new(osock(si_nrm, "Value"), isock(vsc, "Vector"))
    L.new(labelsize, isock(vsc, "Scale"))
    vad = N.new("ShaderNodeVectorMath"); vad.operation = "ADD"; vad.location = (X + 960, Y - 250)
    L.new(osock(si_pos, "Value"), vad.inputs[0])
    L.new(osock(vsc, "Vector"), vad.inputs[1])

    xf = N.new("GeometryNodeTransform"); xf.location = (X + 1150, Y - 450)
    L.new(osock(s2c, "Curve Instances"), isock(xf, "Geometry"))
    L.new(osock(vad, "Vector"), isock(xf, "Translation"))
    L.new(osock(al, "Rotation"), isock(xf, "Rotation"))

    jn = N.new("GeometryNodeJoinGeometry"); jn.location = (X + 1300, Y - 200)
    L.new(osock(rin, "Geometry"), isock(jn, "Geometry"))
    L.new(osock(xf, "Geometry"), isock(jn, "Geometry"))
    L.new(osock(jn, "Geometry"), isock(rout, "Geometry"))
    addi = N.new("ShaderNodeMath"); addi.operation = "ADD"; addi.location = (X + 1150, Y - 700)
    L.new(osock(rin, "i"), addi.inputs[0]); addi.inputs[1].default_value = 1
    L.new(osock(addi, "Value"), isock(rout, "i"))
    labels = osock(rout, "Geometry")

    jn2 = N.new("GeometryNodeJoinGeometry"); jn2.location = (X + 1650, Y + 200)
    L.new(main_geo, isock(jn2, "Geometry"))
    L.new(labels, isock(jn2, "Geometry"))
    sw2 = N.new("GeometryNodeSwitch"); sw2.input_type = "GEOMETRY"; sw2.location = (X + 1850, Y + 250)
    L.new(showsize, isock(sw2, "Switch"))
    L.new(main_geo, isock(sw2, "False"))
    L.new(osock(jn2, "Geometry"), isock(sw2, "True"))

    old = next(l for l in gout.inputs[0].links)
    L.remove(old)
    L.new(osock(sw2, "Output"), gout.inputs[0])


class NODE_OT_rebuild_instance_face(bpy.types.Operator):
    bl_idname = "node.rebuild_instance_face"
    bl_label = "Rebuild Instance Face Graph"
    bl_description = "Add area-scale + size-hint nodes to the 'Instance Face' / 'My Instance Face' groups"
    bl_options = {'REGISTER'}

    def execute(self, context):
        inner = bpy.data.node_groups.get(INNER)
        outer = bpy.data.node_groups.get(OUTER)
        if inner is None or outer is None:
            self.report({'ERROR'}, "Node groups '%s' / '%s' not found" % (INNER, OUTER))
            return {'CANCELLED'}
        if any(n.label == "snap 0.1" for n in inner.nodes):
            self.report({'WARNING'}, "Already built (found 'snap 0.1' node) — skipped")
            return {'CANCELLED'}
        try:
            build_scale_from_area(inner)
            build_size_hints(inner, outer)
        except (KeyError, StopIteration) as e:
            self.report({'ERROR'}, "Graph structure mismatch: %s" % e)
            return {'CANCELLED'}
        if bpy.data.filepath:
            bpy.ops.wm.save_mainfile()
            self.report({'INFO'}, "Build done, file saved")
        else:
            self.report({'INFO'}, "Build done, file NOT saved (no filepath)")
        return {'FINISHED'}


def register():
    bpy.utils.register_class(NODE_OT_rebuild_instance_face)


def unregister():
    bpy.utils.unregister_class(NODE_OT_rebuild_instance_face)
