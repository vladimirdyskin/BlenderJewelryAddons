# SPDX-License-Identifier: GPL-3.0-or-later

"""
Параметрическая груша: меш камня строится из контура рундиста и пропорций, без шаблона Unit Pear.

Контур — тот же объект «Outline ...», по которому связка My_Stone строит каст и крапана (петля рёбрами,
атрибут corner у острия, единичные координаты; предел петли — кубический B-сплайн, gem_outline.py).
Камень и контур из одного источника: рундист камня лежит точно на пределе петли.

Схема граней — бриллиантовая груша, 8-кратная (как у шаблона JewelCraft): площадка 8, звёзды 8,
основные грани короны 8, верхние клинья 16, рундист 32, нижние клинья 16, основные грани павильона 8.
Все грани плоские по построению:
    основная грань — плоскость через вершину рундиста, вершину площадки (или калетту) и касательную
        контура в этой вершине (грань лежит на рундисте; у груши касательная на боку далеко не
        перпендикулярна радиусу — с перпендикуляром грани у острия выворачиваются); вершина звезды /
        нижнего клина — на линии пересечения двух соседних основных граней на заданной высоте;
    клин — плоскость через эту вершину и две соседние вершины рундиста; промежуточная точка рундиста
        лежит на контуре, её высота берётся с плоскости клина (рундист получается волнистым).
Вершины рундиста: остриё, самое широкое место и головка, между ними по три точки поровну по длине.

Меш — камень-единица (габарит XY 1 x 1, z в долях ширины), как ждёт вход Diam у My_Stone: камень
остаётся инстансом объекта с меткой gem, JewelCraft его видит.

Панель (вкладка Jewelry -> Gem from Outline): у объекта со связкой My_Stone кнопка Make Parametric Pear
строит камень по его контуру и размерам и ставит во вход Diam; ползунки пропорций хранятся на объекте
камня и пересобирают меш сразу. За правкой точек контура аддон не следит — после неё кнопка Update.
"""

from __future__ import annotations

import re

import bmesh
import bpy
from bpy.props import BoolProperty, FloatProperty, PointerProperty
from bpy.types import Operator, PropertyGroup
from mathutils import Vector

from . import gem_outline

_STONE = re.compile(r"My_Stone(\.\d+)?$")
SUFFIX = " Gem"


# --- геометрия -----------------------------------------------------------------------------------

def outline_loop(obj: bpy.types.Object) -> list[tuple[float, float, bool]]:
    """Петля объекта-контура: [(x, y, corner)] по рёбрам, остриё (corner) первым."""
    me = obj.data
    nxt: dict[int, list[int]] = {}
    for e in me.edges:
        a, b = e.vertices
        nxt.setdefault(a, []).append(b)
        nxt.setdefault(b, []).append(a)
    if len(nxt) < 3:
        raise ValueError("%s: outline has no closed loop" % obj.name)
    corner = me.attributes.get("corner")
    sharp = [i for i in nxt if corner is not None and corner.data[i].value > 0.5]
    start = sharp[0] if sharp else min(nxt, key=lambda i: me.vertices[i].co.y)
    order, prev = [start], None
    while True:
        cur = order[-1]
        step = [i for i in nxt[cur] if i != prev]
        if not step or step[0] == start:
            break
        prev = cur
        order.append(step[0])
    return [(me.vertices[i].co.x, me.vertices[i].co.y, i in sharp) for i in order]


def _half(dense):
    """Правая половина замкнутого контура [(x, y)]: от острия (min y) до головки (max y), x >= 0."""
    k = min(range(len(dense)), key=lambda i: dense[i][1])
    ring = dense[k:] + dense[:k]
    if ring[1][0] < 0:
        ring = ring[:1] + ring[:0:-1]
    top = max(range(len(ring)), key=lambda i: ring[i][1])
    half = [(max(x, 0.0), y) for x, y in ring[:top + 1]]
    half[0], half[-1] = (0.0, half[0][1]), (0.0, half[-1][1])
    return half


def _along(path):
    acc = [0.0]
    for a, b in zip(path, path[1:]):
        acc.append(acc[-1] + ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5)

    def at(d):
        d = min(max(d, 0.0), acc[-1])
        for i in range(len(path) - 1):
            if acc[i] <= d <= acc[i + 1] + 1e-12:
                f = (d - acc[i]) / (acc[i + 1] - acc[i]) if acc[i + 1] > acc[i] else 0.0
                return (path[i][0] + (path[i + 1][0] - path[i][0]) * f, path[i][1] + (path[i + 1][1] - path[i][1]) * f)
        return path[-1]
    return acc, at


def _plane(a, b, h):
    """Плоскость через точки a, b и направление h: (нормаль, точка)."""
    return (b - a).cross(h).normalized(), a


def _on_two(p1, p2, z):
    """Точка на линии пересечения плоскостей p1, p2 на высоте z."""
    (n1, a1), (n2, a2) = p1, p2
    r1, r2 = n1.dot(a1) - n1.z * z, n2.dot(a2) - n2.z * z
    det = n1.x * n2.y - n1.y * n2.x
    return Vector(((r1 * n2.y - r2 * n1.y) / det, (n1.x * r2 - n2.x * r1) / det, z))


def _z_on(a, b, c, xy):
    """Высота плоскости через a, b, c над точкой xy."""
    n = (b - a).cross(c - a)
    return a.z - (n.x * (xy[0] - a.x) + n.y * (xy[1] - a.y)) / n.z


def pear_geometry(dense, table=0.60, crown=0.14, girdle=0.0375, pavilion=0.435, star=0.69, lower=0.75):
    """Вершины и грани груши по плотному контуру рундиста [(x, y)] в мм (симметричен по X, остриё вниз по Y).
    Доли ширины: table — площадка от радиуса до рундиста, crown / girdle / pavilion — высоты;
    star — высота вершины звезды в доле короны, lower — глубина вершины нижнего клина в доле павильона."""
    half = _half(dense)
    acc, at = _along(half)
    wide = max(range(len(half)), key=lambda i: half[i][0])
    sw, se = acc[wide], acc[-1]
    stops = [sw * k / 4 for k in range(4)] + [sw + (se - sw) * k / 4 for k in range(5)]     # 9 вершин рундиста
    main = [at(s) for s in stops]
    mid = [at((a + b) / 2) for a, b in zip(stops, stops[1:])]
    main[0], main[-1] = (0.0, half[0][1]), (0.0, half[-1][1])
    # касательная контура в чётных вершинах рундиста (у острия и головки — поперёк оси)
    eps = se * 1e-3
    tang = [Vector((1.0, 0.0, 0.0)) if k in (0, 8) else
            Vector((at(stops[k] + eps)[0] - at(stops[k] - eps)[0], at(stops[k] + eps)[1] - at(stops[k] - eps)[1], 0.0))
            for k in range(0, 9, 2)]
    side = tang + [Vector((-t.x, t.y, 0.0)) for t in tang[-2:0:-1]]                         # 8, как грани
    ring = main + [(-x, y) for x, y in main[-2:0:-1]]                                       # 16, против часовой
    mids = mid + [(-x, y) for x, y in mid[::-1]]                                            # 16: между k и k + 1
    w = 2.0 * half[wide][0]
    zg, zc = girdle * w, -pavilion * w
    zt = zg + crown * w
    centre = Vector((0.0, half[wide][1], 0.0))

    top = [Vector((x, y, zg)) for x, y in ring]
    bot = [Vector((x, y, 0.0)) for x, y in ring]
    tab = [centre + (top[2 * i] - Vector((0, 0, zg)) - centre) * table + Vector((0, 0, zt)) for i in range(8)]
    cul = centre + Vector((0, 0, zc))
    bezel = [_plane(top[2 * i], tab[i], side[i]) for i in range(8)]
    pav = [_plane(bot[2 * i], cul, side[i]) for i in range(8)]
    stars = [_on_two(bezel[i], bezel[(i + 1) % 8], zg + star * (zt - zg)) for i in range(8)]
    lows = [_on_two(pav[i], pav[(i + 1) % 8], lower * zc) for i in range(8)]
    mtop = [Vector((x, y, _z_on(stars[k // 2], top[k], top[(k + 1) % 16], (x, y)))) for k, (x, y) in enumerate(mids)]
    mbot = [Vector((x, y, _z_on(lows[k // 2], bot[k], bot[(k + 1) % 16], (x, y)))) for k, (x, y) in enumerate(mids)]

    verts = tab + stars + top + mtop + bot + mbot + lows + [cul]
    T, S, MT, GT, MB, GB, L, C = 0, 8, 16, 32, 48, 64, 80, 88
    faces = [tuple(T + i for i in range(8))]
    for i in range(8):
        j, a, b, c = (i + 1) % 8, 2 * i, 2 * i + 1, (2 * i + 2) % 16
        faces += [(T + i, S + i, T + j),                                   # звезда
                  (T + i, S + (i - 1) % 8, MT + a, S + i),                 # основная грань короны
                  (S + i, MT + a, GT + a, MT + b), (S + i, MT + b, GT + b, MT + c),      # верхние клинья
                  (L + i, MB + b, GB + a, MB + a), (L + i, MB + c, GB + b, MB + b),      # нижние клинья
                  (C, L + i, MB + a, L + (i - 1) % 8)]                     # основная грань павильона
    for k in range(16):
        n = (k + 1) % 16
        faces += [(MT + k, MB + k, GB + k, GT + k), (GT + k, GB + k, MB + n, MT + n)]   # рундист
    return verts, faces


def fill_mesh(mesh: bpy.types.Mesh, outline: bpy.types.Object, width: float, length: float, **props) -> None:
    """Меш камня-единицы по объекту-контуру: width x length мм задают пропорции. Датаблок тот же."""
    dense = [(x * width, y * length) for x, y, _tx, _ty in gem_outline.limit_curve(outline_loop(outline), 64)]
    verts, faces = pear_geometry(dense, **props)
    xs, ys = [v.x for v in verts], [v.y for v in verts]
    cx, cy, sx, sy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, max(xs) - min(xs), max(ys) - min(ys)
    bm = bmesh.new()
    bv = [bm.verts.new(((v.x - cx) / sx, (v.y - cy) / sy, v.z / sx)) for v in verts]
    for f in faces:
        bm.faces.new([bv[i] for i in f])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh.clear_geometry()
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


# --- свойства и операторы ------------------------------------------------------------------------

def _modifier(ob):
    if ob is None:
        return None
    return next((m for m in ob.modifiers if m.type == "NODES" and m.node_group and _STONE.match(m.node_group.name)),
                None)


def _socket(md, name: str):
    item = next((it for it in md.node_group.interface.items_tree
                 if it.item_type == "SOCKET" and it.in_out == "INPUT" and it.name == name), None)
    return getattr(md.properties.inputs, item.identifier) if item else None


def _value(md, name: str):
    sock = _socket(md, name)
    return sock.value if sock is not None else None


def _relations(ob: bpy.types.Object) -> None:
    """Пересобрать связи графа зависимостей объекта. Новый объект во входе Diam граф ещё не знает:
    Object Info отдаёт пустую геометрию, My_Stone берёт встроенный камень и так и остаётся.
    Добавление и удаление модификатора пересборку связей вызывает (ссылки на модификаторы после него
    перезапрашивать)."""
    ob.modifiers.remove(ob.modifiers.new("_relations", "DISPLACE"))


def rebuild(gem: bpy.types.Object) -> None:
    p = gem.param_gem
    if p.outline is None or p.outline.type != "MESH":
        raise ValueError("%s: outline object is not set" % gem.name)
    fill_mesh(gem.data, p.outline, p.width, p.length, table=p.table / 100.0, crown=p.crown / 100.0,
              girdle=p.girdle / 100.0, pavilion=p.pavilion / 100.0, star=p.star / 100.0, lower=p.lower / 100.0)
    gem["gem"] = {"cut": "PEAR", "stone": "DIAMOND"}      # метка JewelCraft
    for ob in bpy.data.objects:                           # носители My_Stone с этим камнем
        md = _modifier(ob)
        if md is not None and _value(md, "Diam") == gem:
            ob.update_tag()


def _on_change(self, _context) -> None:
    gem = self.id_data
    if self.enabled and gem.type == "MESH":
        try:
            rebuild(gem)
        except Exception as ex:               # ползунок не должен ронять интерфейс
            print("Parametric gem: %s" % ex)


def _is_mesh(_self, ob) -> bool:
    return ob.type == "MESH"


class ParamGemProperties(PropertyGroup):
    enabled: BoolProperty(default=False)
    outline: PointerProperty(name="Outline", type=bpy.types.Object, poll=_is_mesh,
                             description="Girdle outline object (the one used by My_Stone)")
    width: FloatProperty(name="Width", default=7.0, min=0.3, soft_max=30.0, unit="LENGTH", update=_on_change,
                         description="Stone width, sets the proportions of the unit mesh")
    length: FloatProperty(name="Length", default=10.0, min=0.3, soft_max=30.0, unit="LENGTH", update=_on_change,
                          description="Stone length, sets the proportions of the unit mesh")
    table: FloatProperty(name="Table", default=60.0, min=30.0, max=85.0, subtype="PERCENTAGE", update=_on_change,
                         description="Table size, % of the distance from the centre to the girdle")
    crown: FloatProperty(name="Crown", default=14.0, min=3.0, max=30.0, subtype="PERCENTAGE", update=_on_change,
                         description="Crown height, % of the width")
    girdle: FloatProperty(name="Girdle", default=3.75, min=0.5, max=12.0, subtype="PERCENTAGE", update=_on_change,
                          description="Girdle thickness, % of the width")
    pavilion: FloatProperty(name="Pavilion", default=43.5, min=20.0, max=70.0, subtype="PERCENTAGE",
                            update=_on_change, description="Pavilion depth, % of the width")
    star: FloatProperty(name="Star", default=69.0, min=20.0, max=95.0, subtype="PERCENTAGE", update=_on_change,
                        description="Height of the star facet vertices, % of the crown")
    lower: FloatProperty(name="Lower Girdle", default=75.0, min=30.0, max=95.0, subtype="PERCENTAGE",
                         update=_on_change, description="Depth of the lower girdle facet vertices, % of the pavilion")


def _gem_of(ob):
    """Параметрический камень объекта: он сам или камень во входе Diam его My_Stone."""
    if ob is None:
        return None
    if ob.type == "MESH" and ob.param_gem.enabled:
        return ob
    md = _modifier(ob)
    diam = _value(md, "Diam") if md is not None else None
    return diam if diam is not None and diam.type == "MESH" and diam.param_gem.enabled else None


def _sync(gem, md) -> None:
    """Контур и размеры камня — со связки My_Stone (без пересборки на каждое свойство)."""
    p = gem.param_gem
    was, p.enabled = p.enabled, False
    outline = _value(md, "Outline") or bpy.data.objects.get("Outline Pear")
    if outline is not None:
        p.outline = outline
    p.width, p.length = _value(md, "Width"), _value(md, "Length")
    p.enabled = was


class OBJECT_OT_param_gem_make(Operator):
    bl_idname = "object.param_gem_make"
    bl_label = "Make Parametric Pear"
    bl_description = ("Build a parametric pear from the outline and size of the selected stone settings (My_Stone) "
                      "and put it into their Diam input")
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return _modifier(context.active_object) is not None

    def execute(self, context: bpy.types.Context):
        md = _modifier(context.active_object)
        if _value(md, "Cut") != "Pear":
            self.report({"ERROR"}, "Only the Pear cut is supported")
            return {"CANCELLED"}
        outline = _value(md, "Outline") or bpy.data.objects.get("Outline Pear")
        if outline is None:
            self.report({"ERROR"}, "Outline object not found")
            return {"CANCELLED"}
        name = outline.name + SUFFIX
        gem = bpy.data.objects.get(name)
        if gem is None:
            gem = bpy.data.objects.new(name, bpy.data.meshes.new(name))
        gem.use_fake_user = True                      # ссылка модификатора пользователем не считается
        gem.param_gem.enabled = True
        _sync(gem, md)
        try:
            rebuild(gem)
        except Exception as ex:
            self.report({"ERROR"}, str(ex))
            return {"CANCELLED"}
        done = 0
        for ob in {context.active_object, *context.selected_objects}:
            m = _modifier(ob)
            if m is not None and _value(m, "Cut") == "Pear":
                _socket(m, "Diam").value = gem
                _relations(ob)
                ob.update_tag()
                done += 1
        self.report({"INFO"}, "Parametric pear '%s' set on %d object(s)" % (name, done))
        return {"FINISHED"}


class OBJECT_OT_param_gem_update(Operator):
    bl_idname = "object.param_gem_update"
    bl_label = "Update"
    bl_description = "Rebuild the parametric gem: re-read the outline points and the size of the stone setting"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return _gem_of(context.active_object) is not None

    def execute(self, context: bpy.types.Context):
        gem = _gem_of(context.active_object)
        md = _modifier(context.active_object)
        if md is not None:
            _sync(gem, md)
        try:
            rebuild(gem)
        except Exception as ex:
            self.report({"ERROR"}, str(ex))
            return {"CANCELLED"}
        self.report({"INFO"}, "Parametric gem '%s' rebuilt" % gem.name)
        return {"FINISHED"}


class VIEW3D_PT_param_gem(bpy.types.Panel):
    """Своя панель во вкладке Jewelry: в ней уже есть «Parametric Gems» аддона шаблонных камней,
    поэтому имя другое, а блок внутри Jewel Tools терялся."""
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Jewelry"
    bl_label = "Gem from Outline"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        ob = context.active_object
        gem = _gem_of(ob)
        if gem is None:
            if _modifier(ob) is None:
                layout.label(text="Select a stone setting (My_Stone)", icon="INFO")
            layout.operator("object.param_gem_make", icon="ADD")
            return
        p = gem.param_gem
        col = layout.column(align=True)
        col.label(text=gem.name, icon="MESH_ICOSPHERE")
        col.prop(p, "outline")
        col = layout.column(align=True)
        for name in ("table", "crown", "girdle", "pavilion", "star", "lower"):
            col.prop(p, name, slider=True)
        layout.operator("object.param_gem_update", icon="FILE_REFRESH")


_CLASSES = (ParamGemProperties, OBJECT_OT_param_gem_make, OBJECT_OT_param_gem_update, VIEW3D_PT_param_gem)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Object.param_gem = PointerProperty(type=ParamGemProperties)


def unregister() -> None:
    del bpy.types.Object.param_gem
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
