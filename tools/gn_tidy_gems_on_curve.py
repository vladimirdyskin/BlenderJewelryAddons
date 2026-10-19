"""
Порядок в графе «My_Gems_On_Curve» — результат вычисления не меняется.

- Все узлы разложены по фреймам; новые фреймы с префиксом «TD ».
- Узлы патча Exact Spacing (ES) — в три фрейма: Exact Spacing, Stone Length, Seam Prongs.
  Общий «ES Input» делится на локальные Group Input для каждого фрейма.
- У Group Input скрыты неиспользуемые выходы.
- Внутри фрейма узлы раскладываются по слоям (длиннейший путь связей),
  фреймы — колонками слева направо по ходу данных.
- Подписи неочевидных переключателей (2/4 крапана от X/Y Offset).
- Узлы патча Boolean (BO) — во фрейм Boolean под Output; без патча фрейм удаляется.
- Удалены вход «Stone Material» и его мёртвая ветка (Set Material -> Group.002 без выхода).
  Камни выводятся инстансом объекта SampleGem ради JewelCraft, а Set Material
  на инстансы не действует — материал камня задаётся на самом SampleGem.

Запускать после tools/gn_exact_spacing_patch.py и tools/gn_prong_tilt_patch.py
(они пересоздают свои узлы вне фреймов). Нужен открытый редактор нод с этой
группой: размеры узлов Blender считает только при отрисовке.
Идемпотентно.
"""

import bpy

GROUP_NAME = "My_Gems_On_Curve"

# фрейм: (подпись, узлы, которые нужно в него положить)
FRAMES = {
    "Frame": ("Default Gem", ["Group Input.001"]),
    "Frame.003": ("Stepped Size from Radius", []),
    "Frame.004": ("Auto Size Curve", []),
    "Frame.007": ("Row Points", ["Group.001", "Reroute"]),
    "Frame.005": ("Cap Selection", []),
    "Frame.006": ("Cap Position Shift", []),
    "Frame.008": ("Prong Source", []),
    "Frame.001": ("2-Prong Setup", []),
    "Frame.002": ("4-Prong Setup", ["Switch.012"]),
    "TD Stone Length": ("Stone Length", [
        "ES Input Stone", "ES Stone Info", "ES Stone BBox", "ES BBox Min", "ES BBox Max",
        "ES BBox X", "ES Has Stone", "ES Length Factor", "ES Stone Length"]),
    "TD Exact Spacing": ("Exact Spacing", [
        "ES Input", "ES Count", "ES Segments", "ES Row Length", "ES Leftover",
        "ES Start", "ES End", "ES Trim", "ES Open"]),
    "TD Seam Prongs": ("Seam Prongs", [
        "ES Input Seam", "ES Cyclic", "ES Cyclic Max", "ES Closed", "ES Source Length",
        "ES Row Length Real", "ES Seam Gap", "ES Gap Small", "ES Merge Seam", "ES Row Points",
        "ES Last Index", "ES Index", "ES Is Last", "ES Is First", "ES Merge Last", "ES Drop Last",
        "ES Merge First", "ES Seam Tilt", "ES Seam Length", "ES Seam Sample", "ES Seam Align Z",
        "ES Seam Align X", "ES Seam Position", "ES Seam Rotation"]),
    "TD Stones": ("Stones", [
        "Group Input.014", "Switch.011", "Join Geometry.001", "Instance on Points.001",
        "JewelCraft Gem Selection", "JewelCraft Gem Instances"]),
    "TD Output": ("Output", [
        "Group Input.015", "Switch.002", "Switch.017", "Join Geometry", "Realize Instances",
        "Group Input.022", "Switch.004", "Group Input.006", "Group.010", "Group Output"]),
    "TD Boolean": ("Boolean", []),
}

# узлы по префиксу имени -> фрейм (патчи, которых может не быть в файле)
PREFIX_FRAMES = {"BO ": "TD Boolean"}

# колонки фреймов слева направо, в колонке — сверху вниз
COLUMNS = [
    ["Frame", "TD Stone Length", "Frame.003", "Frame.004"],
    ["Frame.007", "TD Exact Spacing"],
    ["TD Stones", "Frame.005", "Frame.006"],
    ["Frame.008", "TD Seam Prongs"],
    ["Frame.002", "Frame.001"],
    ["TD Output", "TD Boolean"],
]

# общий ES Input -> локальные входы фреймов: (новый узел, потребители)
SPLIT_INPUTS = {
    "ES Input Stone": ["ES Stone Info", "ES Stone Length"],
    "ES Input Seam": ["ES Cyclic Max", "ES Source Length", "ES Seam Tilt", "ES Seam Length"],
}

LABELS = {
    "Switch.002": "4-Prong if X Offset ≠ 0",
    "Switch.001": "2 per point if Y Offset ≠ 0",
    "Switch.003": "4 per stone if Y Offset ≠ 0",
}

PAD = 30            # отступ узлов от края фрейма
TOP = 50            # место под подпись фрейма
GAP_X, GAP_Y = 60, 20
FRAME_GAP_X, FRAME_GAP_Y = 200, 120


def _remove_stone_material(ng):
    N = ng.nodes
    setmat = N.get("Set Material")
    geo = setmat.inputs["Geometry"].links if setmat else []
    if geo and geo[0].from_node.name == "Gem":    # только материал камня, не металла
        N.remove(setmat)
    for name in ("Group.002", "Group Input.008"):
        if name in N:
            N.remove(N[name])
    sock = next((i for i in ng.interface.items_tree if i.item_type == "SOCKET"
                 and i.in_out == "INPUT" and i.name == "Stone Material"), None)
    if sock is not None:
        ng.interface.remove(sock)


def _split_inputs(ng):
    N, L = ng.nodes, ng.links
    src = N["ES Input"]
    for name, consumers in SPLIT_INPUTS.items():
        gin = N.get(name)
        if gin is None:
            gin = N.new("NodeGroupInput")
            gin.name = gin.label = name
        for link in [l for l in L if l.from_node == src and l.to_node.name in consumers]:
            to_socket, out_name = link.to_socket, link.from_socket.name
            L.remove(link)
            L.new(gin.outputs[out_name], to_socket)


def _hide_unused_inputs(ng):
    for n in ng.nodes:
        if n.bl_idname == "NodeGroupInput":
            for s in n.outputs:
                s.hide = not s.is_linked


def _frames(ng):
    N = ng.nodes
    for name, (label, members) in FRAMES.items():
        fr = N.get(name)
        if fr is None:
            fr = N.new("NodeFrame")
            fr.name = name
        fr.label = label
        fr.shrink = True
        for m in members:
            node = N[m]
            if node.parent != fr:
                node.parent = fr
    for n in N:
        for prefix, name in PREFIX_FRAMES.items():
            if n.name.startswith(prefix) and n.bl_idname != "NodeFrame" and n.parent != N[name]:
                n.parent = N[name]
    for name in FRAMES:
        if not any(n.parent == N[name] for n in N):
            N.remove(N[name])        # патча нет — пустой фрейм не нужен
    loose = [n.name for n in N if n.parent is None and n.bl_idname != "NodeFrame"]
    if loose:
        raise RuntimeError("Nodes without frame: %s" % loose)


def _redraw():
    bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)


def _size(n):
    w, h = n.dimensions
    if w == 0:
        raise RuntimeError("Node sizes are unknown: open this group in a node editor")
    return w, h


def _layout_frame(ng, fr):
    """Слои по длиннейшему пути; источники подтягиваются к своим потребителям."""
    nodes = [n for n in ng.nodes if n.parent == fr]
    inside = set(nodes)
    pred = {n: [] for n in nodes}
    succ = {n: [] for n in nodes}
    for l in ng.links:
        if l.from_node in inside and l.to_node in inside:
            pred[l.to_node].append(l.from_node)
            succ[l.from_node].append(l.to_node)

    depth = {}

    def walk(n):
        if n not in depth:
            depth[n] = 1 + max((walk(p) for p in pred[n]), default=-1)
        return depth[n]

    for n in nodes:
        walk(n)
    for n in nodes:
        if not pred[n] and succ[n]:
            depth[n] = min(depth[s] for s in succ[n]) - 1
    low = min(depth.values())
    cols = {}
    for n in sorted(nodes, key=lambda n: -n.location_absolute.y):
        cols.setdefault(depth[n] - low, []).append(n)
    keys = sorted(cols)

    # порядок в колонке: барицентр соседей (несколько проходов туда-обратно)
    pos = {n: i for k in keys for i, n in enumerate(cols[k])}
    for sweep in range(4):
        order = keys if sweep % 2 == 0 else list(reversed(keys))
        for k in order:
            nb = pred if sweep % 2 == 0 else succ
            cols[k].sort(key=lambda n: (sum(pos[m] for m in nb[n]) / len(nb[n])) if nb[n] else pos[n])
            for i, n in enumerate(cols[k]):
                pos[n] = i

    x = PAD
    for k in keys:
        y = -TOP
        for n in cols[k]:
            w, h = _size(n)
            n.location = (x, y)
            y -= h + GAP_Y
        x += max(_size(n)[0] for n in cols[k]) + GAP_X


def _frame_size(ng, fr):
    nodes = [n for n in ng.nodes if n.parent == fr]
    w = max(n.location.x + _size(n)[0] for n in nodes) + PAD
    h = max(-n.location.y + _size(n)[1] for n in nodes) + PAD
    return w, h


def tidy(ng):
    _remove_stone_material(ng)
    _split_inputs(ng)
    _hide_unused_inputs(ng)
    _frames(ng)
    for node, label in LABELS.items():
        ng.nodes[node].label = label
    _redraw()
    frames = [name for name in FRAMES if name in ng.nodes]
    for name in frames:
        _layout_frame(ng, ng.nodes[name])
    _redraw()

    x = 0.0
    for col in COLUMNS:
        y, width = 0.0, 0.0
        for name in (n for n in col if n in frames):
            fr = ng.nodes[name]
            fr.location = (x, y)
            w, h = _frame_size(ng, fr)
            y -= h + FRAME_GAP_Y
            width = max(width, w)
        x += width + FRAME_GAP_X
    _redraw()
    print("Tidied '%s'" % ng.name)
    return ng


def main():
    tidy(bpy.data.node_groups[GROUP_NAME])


if __name__ == "__main__":
    main()
