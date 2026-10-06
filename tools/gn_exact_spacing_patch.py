"""
Exact Spacing для группы «My_Gems_On_Curve».

Проблема: Spacing в группе задаёт не зазор, а количество точек
(floor(L / ((Gem Size + Spacing) / 2))), после чего Resample Curve (Count)
растягивает точки равномерно по всей кривой. Зазор меняется скачками.

Патч: тумблер «Exact Spacing» в панели Stone. Когда он включён, перед Resample
кривая обрезается Trim Curve (Length) ровно до длины ряда (count - 1) * half_pitch,
центрированно: start = (L - used) / 2, и размыкается (Set Spline Cyclic). Тогда Resample даёт точный шаг
half_pitch = (Gem Size + Spacing) / 2, и Spacing = реальный зазор, плавно.
Выключен — Trim не применяется (Selection = False), поведение прежнее.

Длина камня вдоль кривой: граф писался под круглые камни и брал в шаг Gem Size
(= диаметр). У некруглых (багет) вдоль кривой лежит локальная ось X, её длина
= Gem Size * размер bbox исходного камня по X. Патч подставляет её вместо Gem Size
в Gem Size + Spacing. Для круглого SampleGem bbox X = 1, поведение не меняется.
Если камень не задан (bbox пуст), множитель 1.

Чётность точек: граф делает число точек нечётным (камень между двумя крапанами).
Исходно при чётном n брал n - 1 и терял камень, который реально влезал.
Патч меняет Math.004 на n + 1: точек n + 1 занимают n полушагов <= L (n = floor),
так что зазор не меньше заданного, а камней ровно floor(L / pitch).

Шов кольца: LB_Trim/Offset всегда обрезает кривую (Offset .. L + Offset), поэтому
на замкнутой кривой крайние крапана встают у шва друг в друга (обычный режим)
или почти вплотную (Exact Spacing, малый Trim). Если исходная кривая замкнута и
разрыв у шва (L - длина ряда) меньше полушага, последний крапан убирается,
а первый ставится в середину разрыва: исходная кривая в точке Offset Curve,
поворот как у остальных (Z по нормали, X по касательной, с учётом Tilt).
Большой Trim (полукольцо) — крапана остаются раздельными.

Prong at End: «последний индекс» (Domain Size -> Math.017) исходно считался по кривой
Auto Size (Group.008), и без Auto Size сдвиг конечного крапана не срабатывал. Патч
подключает Domain Size к Switch.013 — кривой, которая реально используется.

Ветка Auto Size и касты не затрагиваются.

Идемпотентно: повторный запуск удаляет прошлые узлы патча и собирает заново.
"""

import bpy

GROUP_NAME = "My_Gems_On_Curve"
SOCKET_NAME = "Exact Spacing"
PANEL_NAME = "Stone"
PREFIX = "ES "


def _panel(ng, name):
    return next(i for i in ng.interface.items_tree if i.item_type == "PANEL" and i.name == name)


def _ensure_socket(ng):
    sock = next((i for i in ng.interface.items_tree
                 if i.item_type == "SOCKET" and i.in_out == "INPUT" and i.name == SOCKET_NAME), None)
    if sock is None:
        panel = _panel(ng, PANEL_NAME)
        sock = ng.interface.new_socket(SOCKET_NAME, in_out="INPUT", socket_type="NodeSocketBool", parent=panel)
        sock.default_value = False
        sock.description = "Spacing is the exact gap between stones; the row is centered and not stretched"
        spacing = next(i for i in ng.interface.items_tree
                       if i.item_type == "SOCKET" and i.in_out == "INPUT" and i.name == "Spacing")
        ng.interface.move_to_parent(sock, panel, spacing.position + 1)
    return sock


def _enabled(node, name):
    return next(s for s in node.inputs if s.name == name and s.enabled)


def _seam_prongs(ng, node, gin, half):
    """Слияние крайних крапанов у шва замкнутой кривой. См. docstring модуля."""
    N, L = ng.nodes, ng.links
    iop = N["Instance on Points"]       # крапана
    setpos = N["Set Position"]          # сдвиги Prong at Start/End
    sel_src = N["Switch.015"]           # выбор точек под крапана
    align = N["Group.001"]              # точки ряда + поворот
    row = N["Switch.013"]               # кривая ряда (обычный / Auto Size)
    tilt = N["Math.007"]                # Tilt + Curve Tilt (поле)

    # вернуть исходные связи (на случай повторного запуска), затем вставиться
    L.new(setpos.outputs["Geometry"], iop.inputs["Points"])
    L.new(sel_src.outputs[0], iop.inputs["Selection"])
    L.new(align.outputs["Rotation"], iop.inputs["Rotation"])

    # --- замкнута ли исходная кривая, и мал ли разрыв у шва (одиночные значения) ---
    cyc = node("GeometryNodeInputSplineCyclic", "Cyclic", -900, 900)
    stat = node("GeometryNodeAttributeStatistic", "Cyclic Max", -720, 900)
    stat.domain = "CURVE"
    closed = node("FunctionNodeCompare", "Closed", -540, 900)
    closed.data_type, closed.operation = "FLOAT", "GREATER_THAN"
    _enabled(closed, "B").default_value = 0.5
    len_src = node("GeometryNodeCurveLength", "Source Length", -720, 750)
    len_row = node("GeometryNodeCurveLength", "Row Length Real", -720, 650)
    gap = node("ShaderNodeMath", "Seam Gap", -540, 700, "SUBTRACT")
    small = node("FunctionNodeCompare", "Gap Small", -360, 700)
    small.data_type, small.operation = "FLOAT", "LESS_THAN"
    merge = node("FunctionNodeBooleanMath", "Merge Seam", -180, 800)
    merge.operation = "AND"

    L.new(gin.outputs["Geometry"], stat.inputs["Geometry"])
    L.new(cyc.outputs[0], stat.inputs["Attribute"])
    L.new(stat.outputs["Max"], _enabled(closed, "A"))
    L.new(gin.outputs["Geometry"], len_src.inputs["Curve"])
    L.new(row.outputs[0], len_row.inputs["Curve"])
    L.new(len_src.outputs["Length"], gap.inputs[0])
    L.new(len_row.outputs["Length"], gap.inputs[1])
    L.new(gap.outputs[0], _enabled(small, "A"))
    L.new(half.outputs[0], _enabled(small, "B"))
    L.new(closed.outputs["Result"], merge.inputs[0])
    L.new(small.outputs["Result"], merge.inputs[1])

    # --- первый / последний индекс точек ряда ---
    size = node("GeometryNodeAttributeDomainSize", "Row Points", -540, 500)
    size.component = "CURVE"           # точки ряда — точки кривой, не меша
    last = node("ShaderNodeMath", "Last Index", -360, 500, "SUBTRACT", 1.0)
    index = node("GeometryNodeInputIndex", "Index", -540, 380)
    is_last = node("FunctionNodeCompare", "Is Last", -180, 500)
    is_last.data_type, is_last.operation = "INT", "EQUAL"
    is_first = node("FunctionNodeCompare", "Is First", -180, 380)
    is_first.data_type, is_first.operation = "INT", "EQUAL"
    drop = node("FunctionNodeBooleanMath", "Drop Last", 0, 500)
    drop.operation = "NIMPLY"           # Selection AND NOT (merge AND last)
    drop_m = node("FunctionNodeBooleanMath", "Merge Last", -20, 600)
    drop_m.operation = "AND"
    first_m = node("FunctionNodeBooleanMath", "Merge First", 0, 380)
    first_m.operation = "AND"

    L.new(align.outputs["Geometry"], size.inputs["Geometry"])
    L.new(size.outputs["Point Count"], last.inputs[0])
    L.new(index.outputs[0], _enabled(is_last, "A"))
    L.new(last.outputs[0], _enabled(is_last, "B"))
    L.new(index.outputs[0], _enabled(is_first, "A"))
    L.new(merge.outputs[0], drop_m.inputs[0])
    L.new(is_last.outputs["Result"], drop_m.inputs[1])
    L.new(sel_src.outputs[0], drop.inputs[0])
    L.new(drop_m.outputs[0], drop.inputs[1])
    L.new(merge.outputs[0], first_m.inputs[0])
    L.new(is_first.outputs["Result"], first_m.inputs[1])

    # --- точка шва на исходной кривой: позиция и поворот ---
    tilted = node("GeometryNodeSetCurveTilt", "Seam Tilt", -540, 1100)
    wrap = node("ShaderNodeMath", "Seam Length", -540, 1250, "FLOORED_MODULO")
    sample = node("GeometryNodeSampleCurve", "Seam Sample", -360, 1150)
    sample.mode = "LENGTH"
    rz = node("FunctionNodeAlignEulerToVector", "Seam Align Z", -180, 1150)
    rz.axis = "Z"
    rx = node("FunctionNodeAlignEulerToVector", "Seam Align X", 0, 1150)
    rx.axis = "X"
    place = node("GeometryNodeSetPosition", "Seam Position", 180, 450)
    rot = node("GeometryNodeSwitch", "Seam Rotation", 180, 300)
    rot.input_type = "VECTOR"

    L.new(gin.outputs["Geometry"], tilted.inputs["Curve"])
    L.new(tilt.outputs[0], tilted.inputs["Tilt"])
    L.new(gin.outputs["Offset Curve"], wrap.inputs[0])
    L.new(len_src.outputs["Length"], wrap.inputs[1])
    L.new(tilted.outputs["Curve"], sample.inputs["Curves"])
    L.new(wrap.outputs[0], _enabled(sample, "Length"))
    L.new(sample.outputs["Normal"], rz.inputs["Vector"])
    L.new(rz.outputs["Rotation"], rx.inputs["Rotation"])
    L.new(sample.outputs["Tangent"], rx.inputs["Vector"])

    L.new(setpos.outputs["Geometry"], place.inputs["Geometry"])
    L.new(first_m.outputs[0], place.inputs["Selection"])
    L.new(sample.outputs["Position"], place.inputs["Position"])
    L.new(first_m.outputs[0], rot.inputs["Switch"])
    L.new(align.outputs["Rotation"], rot.inputs["False"])
    L.new(rx.outputs["Rotation"], rot.inputs["True"])

    L.new(place.outputs["Geometry"], iop.inputs["Points"])
    L.new(drop.outputs[0], iop.inputs["Selection"])
    L.new(rot.outputs[0], iop.inputs["Rotation"])


def patch(ng):
    N, L = ng.nodes, ng.links
    for n in [n for n in N if n.name.startswith(PREFIX)]:
        N.remove(n)

    _ensure_socket(ng)

    # нечётное число точек: при чётном n брать n + 1, а не n - 1 (иначе теряется камень)
    N["Math.004"].operation = "ADD"

    # Prong at End: последний индекс — по реальной кривой ряда, а не по кривой Auto Size
    L.new(N["Switch.013"].outputs[0], N["Domain Size"].inputs[0])

    src = N["Group.006"]          # Trim/Offset Curve -> исходная кривая для раскладки
    resample = N["Resample Curve"]
    half = N["Math.001"]          # (Gem Size + Spacing) * 0.5
    count = N["Switch"]           # нечётное число точек
    length = N["Spline Length"]   # длина той же кривой (поле)

    x, y = resample.location.x - 900, resample.location.y - 300

    def node(kind, name, dx, dy, op=None, value=None):
        n = N.new(kind)
        n.name = n.label = PREFIX + name
        n.location = (x + dx, y + dy)
        if op:
            n.operation = op
        if value is not None:
            n.inputs[1].default_value = value
        return n

    # Count — поле от Spline Length. Без захвата Resample пересчитал бы его на уже обрезанной
    # кривой (длина меньше -> точек меньше -> шаг растянут). Фиксируем на исходной кривой.
    cap = node("GeometryNodeCaptureAttribute", "Count", 540, 250)
    cap.domain = "CURVE"
    cap.capture_items.new("INT", "Count")

    gin = node("NodeGroupInput", "Input", 0, 200)
    for s in gin.outputs:
        s.hide = s.name not in (SOCKET_NAME, "Gem Size", "Diam", "Geometry", "Offset Curve")

    # --- длина камня вдоль кривой: Gem Size * bbox(X) исходного камня ---
    # свой Object Info: узел "Gem" отдаёт камень как инстанс, а bbox инстанса пустой
    gem_info = node("GeometryNodeObjectInfo", "Stone Info", -720, -300)
    gem_info.transform_space = "ORIGINAL"
    gem_info.inputs["As Instance"].default_value = False
    pitch_add = N["Math"]         # Gem Size + Spacing
    bbox = node("GeometryNodeBoundBox", "Stone BBox", -540, -300)
    bmin = node("ShaderNodeSeparateXYZ", "BBox Min", -360, -380)
    bmax = node("ShaderNodeSeparateXYZ", "BBox Max", -360, -260)
    sx = node("ShaderNodeMath", "BBox X", -180, -300, "SUBTRACT")
    has = node("FunctionNodeCompare", "Has Stone", 0, -420)
    has.data_type = "FLOAT"
    has.operation = "GREATER_THAN"
    _enabled(has, "B").default_value = 1e-6
    safe = node("GeometryNodeSwitch", "Length Factor", 180, -300)
    safe.input_type = "FLOAT"
    safe.inputs["False"].default_value = 1.0
    stone_len = node("ShaderNodeMath", "Stone Length", 360, -300, "MULTIPLY")

    segs = node("ShaderNodeMath", "Segments", 0, 0, "SUBTRACT", 1.0)
    used = node("ShaderNodeMath", "Row Length", 180, 0, "MULTIPLY")
    rest = node("ShaderNodeMath", "Leftover", 360, 0, "SUBTRACT")
    start = node("ShaderNodeMath", "Start", 540, 0, "MULTIPLY", 0.5)
    end = node("ShaderNodeMath", "End", 720, 0, "ADD")
    trim = node("GeometryNodeTrimCurve", "Trim", 720, 250)
    trim.mode = "LENGTH"
    # Trim не размыкает замкнутую кривую: Resample иначе учтёт замыкающий отрезок и растянет шаг
    open_ = node("GeometryNodeSetSplineCyclic", "Open", 900, 250)
    open_.inputs["Cyclic"].default_value = False

    L.new(gin.outputs["Diam"], gem_info.inputs["Object"])
    L.new(gem_info.outputs["Geometry"], bbox.inputs["Geometry"])
    L.new(bbox.outputs["Min"], bmin.inputs[0])
    L.new(bbox.outputs["Max"], bmax.inputs[0])
    L.new(bmax.outputs["X"], sx.inputs[0])
    L.new(bmin.outputs["X"], sx.inputs[1])
    L.new(sx.outputs[0], _enabled(has, "A"))
    L.new(has.outputs[0], safe.inputs["Switch"])
    L.new(sx.outputs[0], safe.inputs["True"])
    L.new(gin.outputs["Gem Size"], stone_len.inputs[0])
    L.new(safe.outputs[0], stone_len.inputs[1])
    L.new(stone_len.outputs[0], pitch_add.inputs[0])

    L.new(src.outputs[0], cap.inputs["Geometry"])
    L.new(count.outputs[0], cap.inputs["Count"])
    L.new(cap.outputs["Count"], segs.inputs[0])
    L.new(segs.outputs[0], used.inputs[0])
    L.new(half.outputs[0], used.inputs[1])
    L.new(length.outputs["Length"], rest.inputs[0])
    L.new(used.outputs[0], rest.inputs[1])
    L.new(rest.outputs[0], start.inputs[0])
    L.new(start.outputs[0], end.inputs[0])
    L.new(used.outputs[0], end.inputs[1])

    L.new(cap.outputs["Geometry"], trim.inputs["Curve"])
    L.new(gin.outputs[SOCKET_NAME], trim.inputs["Selection"])
    L.new(start.outputs[0], _enabled(trim, "Start"))
    L.new(end.outputs[0], _enabled(trim, "End"))
    L.new(trim.outputs["Curve"], open_.inputs["Geometry"])
    L.new(gin.outputs[SOCKET_NAME], open_.inputs["Selection"])
    L.new(open_.outputs["Geometry"], resample.inputs["Curve"])
    L.new(cap.outputs["Count"], resample.inputs["Count"])

    _seam_prongs(ng, node, gin, half)

    print("Patched '%s' with Exact Spacing" % ng.name)
    return ng


def main():
    patch(bpy.data.node_groups[GROUP_NAME])


if __name__ == "__main__":
    main()
