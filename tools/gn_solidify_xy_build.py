"""
Solidify XY — толщина строго в плоскости XY, высота (Z) не меняется.

Задача: у открытой поверхности (конический каст, лента кольца) сделать стенку
заданной толщины так, чтобы верхний и нижний края остались на своих Z.
Штатный Solidify гонит толщину по нормали и поэтому «раздувает» деталь по высоте.

Математика (сдвиг вершины, один на вершину, как Even Thickness у Solidify):
    n_f                 нормали прилегающих граней
    направление         d = normalize(xy(mean n_f))  — для двух граней это биссектриса угла
    величина            s = Thickness / mean(d . n_f)
    итого               offset = d * s

Проверка: на плоском участке d . n = |n_xy| — offset . n = Thickness, как раньше.
На углу между двумя гранями mean(d . n_f) = cos(θ/2) — толщина по нормали к обеим
граням ровно Thickness (без поправки было Thickness * cos(θ/2)).
Знаменатель ограничен снизу (MIN_COS): на очень острых углах сдвиг не длиннее
Thickness / MIN_COS, горизонтальные грани (n_xy = 0) не двигаются.

Сдвиг считается один раз по исходной геометрии (Capture Attribute) и им двигаются обе
стенки. Extrude Mesh (Faces) берёт Offset по граням и усредняет на общей вершине —
на углах стенка получалась другой длины, чем у предсдвига по вершинам, и наружная
поверхность уходила с исходного контура. Поэтому Extrude — с нулевым сдвигом,
новые вершины (индекс >= числа исходных) сдвигаются Set Position тем же вектором.

Crease — как у штатного Solidify (MOD_solidify_extrude.cc): значение прибавляется
к имеющемуся crease_edge (не больше 1), его читает Subdivision Surface.
    Outer — граничные рёбра оболочки на стороне нормалей (при Offset -1 — исходный контур)
    Inner — граничные рёбра второй (вывернутой) оболочки
    Rim   — рёбра торца поперёк толщины, между оболочками
Грани помечаются до склейки (Extrude Top / Side, вывернутая копия), ребро после Merge
классифицируется по соседним граням: боковая+наружная, боковая+внутренняя, две боковые.
Все три 0 — crease_edge не трогается.

Интерфейс группы:
    Geometry  — вход
    Thickness — реальная толщина стенки по нормали
    Offset    — куда растёт: +1 наружу (исходная поверхность = внутренняя),
                -1 внутрь (исходная = наружная), 0 симметрично
    Crease Inner / Outer / Rim — панель Crease, 0..1

Скрипт идемпотентен: повторный запуск пересобирает узлы группы с тем же именем;
сокеты интерфейса только добавляются, если их нет — значения на модификаторах сохраняются.
"""

import bpy

GROUP_NAME = "Solidify XY"
MIN_COS = 0.1  # нижняя отсечка mean(d . n): сдвиг не длиннее 10 * Thickness

# (имя, default, min, max, панель)
SOCKETS = [
    ("Thickness", 1.0, 0.0, 1000.0, None),
    ("Offset", -1.0, -1.0, 1.0, None),
    ("Crease Inner", 0.0, 0.0, 1.0, "Crease"),
    ("Crease Outer", 0.0, 0.0, 1.0, "Crease"),
    ("Crease Rim", 0.0, 0.0, 1.0, "Crease"),
]


def ensure_interface(ng):
    """Сокеты по именам: недостающие добавить, существующие не трогать."""
    names = {(it.name, getattr(it, "in_out", None)) for it in ng.interface.items_tree if it.item_type == "SOCKET"}
    if ("Geometry", "INPUT") not in names:
        ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    panels = {it.name: it for it in ng.interface.items_tree if it.item_type == "PANEL"}
    for name, default, mn, mx, panel in SOCKETS:
        if (name, "INPUT") in names:
            continue
        parent = None
        if panel:
            parent = panels.get(panel) or ng.interface.new_panel(panel)
            panels[panel] = parent
        s = ng.interface.new_socket(name, in_out="INPUT", socket_type="NodeSocketFloat", parent=parent)
        s.default_value = default
        s.min_value = mn
        s.max_value = mx
    if ("Geometry", "OUTPUT") not in names:
        ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")


def build_group(name=GROUP_NAME):
    """Собрать (или пересобрать) node group. Возвращает готовую группу."""
    ng = bpy.data.node_groups.get(name)
    if ng is None:
        ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.nodes.clear()  # datablock и интерфейс оставляем — ссылки и значения модификаторов живут
    ensure_interface(ng)

    n = ng.nodes.new
    L = ng.links.new

    def en(node, name, outputs=False):
        # одноимённые сокеты под разные типы — берём активный
        socks = node.outputs if outputs else node.inputs
        return next(s for s in socks if s.name == name and s.enabled)

    gin = n("NodeGroupInput");  gin.location = (-1400, 0)

    # --- направление d: средняя нормаль прилегающих граней, в XY ---
    normal = n("GeometryNodeInputNormal"); normal.location = (-1400, -300)
    face_n = n("GeometryNodeFieldOnDomain"); face_n.location = (-1200, -300)
    face_n.domain = "FACE"            # в контексте точки — среднее по граням, угла — своя грань
    face_n.data_type = "FLOAT_VECTOR"
    sep = n("ShaderNodeSeparateXYZ");  sep.location = (-1000, -300)
    comb = n("ShaderNodeCombineXYZ");  comb.location = (-800, -300)
    comb.inputs["Z"].default_value = 0.0
    dnorm = n("ShaderNodeVectorMath"); dnorm.location = (-600, -300)
    dnorm.operation = "NORMALIZE"
    d_pt = n("GeometryNodeFieldOnDomain"); d_pt.location = (-400, -300)
    d_pt.domain = "POINT"             # на углах берём d их вершины, а не своей грани
    d_pt.data_type = "FLOAT_VECTOR"

    # --- mean(d . n_f) по углам вершины ---
    dot = n("ShaderNodeVectorMath"); dot.location = (-200, -450)
    dot.operation = "DOT_PRODUCT"
    mean = n("GeometryNodeFieldOnDomain"); mean.location = (0, -450)
    mean.domain = "CORNER"
    mean.data_type = "FLOAT"
    clamp = n("ShaderNodeMath"); clamp.location = (200, -450)
    clamp.operation = "MAXIMUM"
    clamp.inputs[1].default_value = MIN_COS
    k = n("ShaderNodeMath"); k.location = (400, -450)
    k.operation = "DIVIDE"            # Thickness / mean(d . n)
    offvec = n("ShaderNodeVectorMath"); offvec.location = (600, -300)
    offvec.operation = "SCALE"

    # сдвиг фиксируем на исходной геометрии: копируется на новые вершины Extrude
    cap = n("GeometryNodeCaptureAttribute"); cap.location = (800, 0)
    cap.domain = "POINT"
    cap.capture_items.new("VECTOR", "Offset")

    # --- предсдвиг исходной поверхности под режим Offset ---
    # факт = (Offset - 1) * 0.5 : +1 -> 0, 0 -> -0.5, -1 -> -1
    fsub = n("ShaderNodeMath"); fsub.location = (800, 300)
    fsub.operation = "SUBTRACT"
    fsub.inputs[1].default_value = 1.0
    fmul = n("ShaderNodeMath"); fmul.location = (1000, 300)
    fmul.operation = "MULTIPLY"
    fmul.inputs[1].default_value = 0.5
    preshift = n("ShaderNodeVectorMath"); preshift.location = (1200, 200)
    preshift.operation = "SCALE"
    setpos = n("GeometryNodeSetPosition"); setpos.location = (1400, 0)

    # --- вторая стенка: Extrude без сдвига + тот же вектор на вершинах верхних граней ---
    # (граничные вершины Extrude копирует, внутренние двигает на месте — берём все вершины Top)
    extrude = n("GeometryNodeExtrudeMesh"); extrude.location = (1600, 0)
    extrude.mode = "FACES"
    extrude.inputs["Individual"].default_value = False
    extrude.inputs["Offset"].default_value = (0.0, 0.0, 0.0)
    extrude.inputs["Offset Scale"].default_value = 0.0
    top = n("GeometryNodeFieldOnDomain"); top.location = (1800, -300)
    top.domain = "FACE"               # в контексте точки — доля верхних граней вокруг вершины
    top.data_type = "FLOAT"
    is_top = n("ShaderNodeMath"); is_top.location = (2000, -300)
    is_top.operation = "GREATER_THAN"
    is_top.inputs[1].default_value = 0.0
    move = n("GeometryNodeSetPosition"); move.location = (2000, 0)

    # Extrude Mesh выбрасывает исходные грани — остаётся сдвинутая оболочка плюс борта.
    # Возвращаем исходник обратно, вывернув нормали (он становится внутренней стенкой),
    # и завариваем общие вершины на границах.
    flip = n("GeometryNodeFlipFaces"); flip.location = (2000, 300)
    join = n("GeometryNodeJoinGeometry"); join.location = (2400, 150)
    merge = n("GeometryNodeMergeByDistance"); merge.location = (2600, 150)
    merge.inputs["Distance"].default_value = 1e-5
    gout = n("NodeGroupOutput"); gout.location = (4600, 150)

    # --- пометки граней для Crease: верхние / боковые (Extrude) и вывернутая копия ---
    def mark(geo_socket, name, value_socket, x, y):
        st = n("GeometryNodeStoreNamedAttribute"); st.location = (x, y)
        st.data_type = "BOOLEAN"
        st.domain = "FACE"
        st.inputs["Name"].default_value = name
        L(geo_socket, st.inputs["Geometry"])
        val = en(st, "Value")
        if value_socket is None:
            val.default_value = True
        else:
            L(value_socket, val)
        return st.outputs["Geometry"]

    marked = mark(extrude.outputs["Mesh"], "_sxy_top", extrude.outputs["Top"], 1800, 150)
    marked = mark(marked, "_sxy_side", extrude.outputs["Side"], 1900, 250)
    inner_marked = mark(flip.outputs["Mesh"], "_sxy_inner", None, 2200, 350)

    # --- Crease: ребро по соседним граням (в контексте ребра — среднее по граням) ---
    def face_avg(name, x, y):
        na = n("GeometryNodeInputNamedAttribute"); na.location = (x - 200, y)
        na.data_type = "FLOAT"
        na.inputs["Name"].default_value = name
        ev = n("GeometryNodeFieldOnDomain"); ev.location = (x, y)
        ev.domain = "FACE"
        ev.data_type = "FLOAT"
        L(na.outputs["Attribute"], en(ev, "Value"))
        return en(ev, "Value", True)

    def math(op, a, b, x, y):
        m = n("ShaderNodeMath"); m.location = (x, y)
        m.operation = op
        for i, v in enumerate((a, b)):
            if isinstance(v, (int, float)):
                m.inputs[i].default_value = v
            else:
                L(v, m.inputs[i])
        return m.outputs["Value"]

    e_side = face_avg("_sxy_side", 2800, -200)
    e_top = face_avg("_sxy_top", 2800, -350)
    e_in = face_avg("_sxy_inner", 2800, -500)
    has_side = math("GREATER_THAN", e_side, 0.001, 3000, -200)
    outer_b = math("MULTIPLY", has_side, math("GREATER_THAN", e_top, 0.001, 3000, -350), 3200, -300)
    inner_b = math("MULTIPLY", has_side, math("GREATER_THAN", e_in, 0.001, 3000, -500), 3200, -450)
    rim_b = math("GREATER_THAN", e_side, 0.99, 3000, -650)          # две боковые грани
    add = math("ADD", math("ADD", math("MULTIPLY", outer_b, gin.outputs["Crease Outer"], 3400, -300),
                           math("MULTIPLY", inner_b, gin.outputs["Crease Inner"], 3400, -450), 3600, -375),
               math("MULTIPLY", rim_b, gin.outputs["Crease Rim"], 3400, -650), 3800, -450)
    old = n("GeometryNodeInputNamedAttribute"); old.location = (3600, -150)
    old.data_type = "FLOAT"
    old.inputs["Name"].default_value = "crease_edge"
    crease = math("MINIMUM", math("ADD", old.outputs["Attribute"], add, 4000, -300), 1.0, 4200, -300)
    st_cr = n("GeometryNodeStoreNamedAttribute"); st_cr.location = (4000, 150)
    st_cr.data_type = "FLOAT"
    st_cr.domain = "EDGE"
    st_cr.inputs["Name"].default_value = "crease_edge"
    any_cr = math("GREATER_THAN", math("ADD", math("ADD", gin.outputs["Crease Inner"], gin.outputs["Crease Outer"], 3800, 450),
                                       gin.outputs["Crease Rim"], 4000, 450), 0.0, 4200, 450)
    use_cr = n("GeometryNodeSwitch"); use_cr.location = (4200, 150)
    use_cr.input_type = "GEOMETRY"
    clean = n("GeometryNodeRemoveAttribute"); clean.location = (4400, 150)
    clean.inputs["Pattern Mode"].default_value = "Wildcard"
    clean.inputs["Name"].default_value = "_sxy_*"

    L(normal.outputs["Normal"], en(face_n, "Value"))
    L(en(face_n, "Value", True), sep.inputs["Vector"])
    L(sep.outputs["X"], comb.inputs["X"])
    L(sep.outputs["Y"], comb.inputs["Y"])
    L(comb.outputs["Vector"], dnorm.inputs[0])
    L(dnorm.outputs["Vector"], en(d_pt, "Value"))
    L(en(d_pt, "Value", True), dot.inputs[0])
    L(en(face_n, "Value", True), dot.inputs[1])
    L(dot.outputs["Value"], en(mean, "Value"))
    L(en(mean, "Value", True), clamp.inputs[0])
    L(gin.outputs["Thickness"], k.inputs[0])
    L(clamp.outputs["Value"], k.inputs[1])
    L(en(d_pt, "Value", True), offvec.inputs[0])
    L(k.outputs["Value"], offvec.inputs["Scale"])

    L(gin.outputs["Geometry"], cap.inputs["Geometry"])
    L(offvec.outputs["Vector"], cap.inputs["Offset"])

    L(gin.outputs["Offset"], fsub.inputs[0])
    L(fsub.outputs["Value"], fmul.inputs[0])
    L(cap.outputs["Offset"], preshift.inputs[0])
    L(fmul.outputs["Value"], preshift.inputs["Scale"])
    L(cap.outputs["Geometry"], setpos.inputs["Geometry"])
    L(preshift.outputs["Vector"], setpos.inputs["Offset"])

    L(setpos.outputs["Geometry"], extrude.inputs["Mesh"])
    L(extrude.outputs["Top"], en(top, "Value"))
    L(en(top, "Value", True), is_top.inputs[0])
    L(marked, move.inputs["Geometry"])
    L(is_top.outputs["Value"], move.inputs["Selection"])
    L(cap.outputs["Offset"], move.inputs["Offset"])

    L(setpos.outputs["Geometry"], flip.inputs["Mesh"])
    L(move.outputs["Geometry"], join.inputs["Geometry"])
    L(inner_marked, join.inputs["Geometry"])
    L(join.outputs["Geometry"], merge.inputs["Geometry"])

    L(merge.outputs["Geometry"], st_cr.inputs["Geometry"])
    L(crease, en(st_cr, "Value"))
    L(any_cr, use_cr.inputs["Switch"])
    L(merge.outputs["Geometry"], use_cr.inputs["False"])
    L(st_cr.outputs["Geometry"], use_cr.inputs["True"])
    L(use_cr.outputs["Output"], clean.inputs["Geometry"])
    L(clean.outputs["Geometry"], gout.inputs["Geometry"])

    print("Node group '%s' rebuilt: %d nodes" % (name, len(ng.nodes)))
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
