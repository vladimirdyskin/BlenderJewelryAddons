
bl_info = {
    "name": "Pretty Ruler Overlay",
    "author": "Vladimir",
    "version": (0, 10, 0),
    "blender": (5, 1, 0),
    "location": "View3D > Sidebar > View > Pretty Ruler",
    "description": "Styled dimension graphics over the native Measure tool",
    "category": "3D View",
}

import bpy
import blf
import bmesh
import gpu
import math
from gpu_extras.batch import batch_for_shader
from bpy_extras import view3d_utils
from mathutils import Matrix, Vector, geometry, interpolate
from mathutils.bvhtree import BVHTree

_handle = None
_shaders = {}
SYNC_INTERVAL = 0.5


def _get_shader(name):
    if name not in _shaders:
        _shaders[name] = gpu.shader.from_builtin(name)
    return _shaders[name]


def get_ruler_strokes():
    out = []
    for ann in bpy.data.annotations:
        for layer in ann.layers:
            if not getattr(layer, "is_ruler", False):
                continue
            af = layer.active_frame
            if not af:
                continue
            for st in af.strokes:
                out.append([Vector(p.co) for p in st.points])
    return out


def _stroke_key(pts):
    """Идентификатор линейки по её точкам (у нативных линеек нет своего id)."""
    return ";".join("{:.5f},{:.5f},{:.5f}".format(*p) for p in pts)


def _match_flags(old, new):
    """old: [(точки, enabled)], new: [точки] -> enabled для new.
    Сначала точное совпадение (линейку не трогали), затем общая точка при том же
    числе точек (линейку тянули за один конец). Новые линейки включены."""
    used = set()
    flags = [None] * len(new)
    for exact in (True, False):
        for i, pts in enumerate(new):
            if flags[i] is not None:
                continue
            for j, (opts, enabled) in enumerate(old):
                if j in used or len(opts) != len(pts):
                    continue
                hit = opts == pts if exact else bool(set(opts) & set(pts))
                if hit:
                    used.add(j)
                    flags[i] = enabled
                    break
    return [True if f is None else f for f in flags]


def _label(pts, props):
    dec = props.decimals
    if len(pts) == 2:
        dist = (pts[1] - pts[0]).length
        return ("{:." + str(dec) + "f}").format(dist) + props.unit_suffix
    if len(pts) == 3:
        v1 = pts[0] - pts[1]
        v2 = pts[2] - pts[1]
        if v1.length and v2.length:
            ang = math.degrees(v1.angle(v2))
            return "∠ " + ("{:." + str(dec) + "f}").format(ang) + "°"
        return "Angle"
    return "Ruler"


def sync_items(props):
    """Приводит список к текущим линейкам; флаги переносятся по геометрии, а не по индексу."""
    strokes = get_ruler_strokes()
    keys = [_stroke_key(pts) for pts in strokes]
    items = props.items
    if [it.key for it in items] != keys:
        old = [(it.key.split(";"), it.enabled) for it in items]
        flags = _match_flags(old, [k.split(";") for k in keys])
        items.clear()
        for key, enabled in zip(keys, flags):
            it = items.add()
            it.key = key
            it.enabled = enabled
    for it, pts in zip(items, strokes):
        name = _label(pts, props)
        if it.name != name:
            it.name = name


def _sync_timer():
    # Запись в данные сцены из draw-колбэка запрещена, поэтому список ведёт таймер
    props = getattr(bpy.context.scene, "pretty_ruler", None)
    if props is not None and props.enabled:
        sync_items(props)
    return SYNC_INTERVAL


# --- Живые размеры: концы привязаны к граням исходного меша ---------------------
# Точка хранится как (объект, индекс грани, вершины грани, веса poly_3d_calc) и каждую
# перерисовку собирается заново из текущих вершин. В Edit Mode читается живой BMesh,
# поэтому размер меняется прямо во время G/S.

def _ints(s):
    return [int(x) for x in s.split(",")] if s else []


def _floats(s):
    return [float(x) for x in s.split(",")] if s else []


def _face_world(obj, face, vids, cache):
    """Мировые координаты вершин привязанной грани; None, если привязка потеряна."""
    if obj is None or obj.type != 'MESH' or face < 0 or not vids:
        return None
    me = obj.data
    if me.is_editmode:
        bm = cache.get(me.as_pointer())
        if bm is None:
            bm = cache[me.as_pointer()] = bmesh.from_edit_mesh(me)
            bm.verts.ensure_lookup_table()
            bm.faces.ensure_lookup_table()
        if face >= len(bm.faces) or max(vids) >= len(bm.verts):
            return None
        fv = bm.faces[face].verts
        # после extrude/delete индексы съезжают — сверяем, что грань та же
        if len(fv) != len(vids) or not all(bm.verts[i] == v for i, v in zip(vids, fv)):
            return None
        local = [bm.verts[i].co for i in vids]
    else:
        if face >= len(me.polygons) or list(me.polygons[face].vertices) != vids:
            return None
        local = [me.vertices[i].co for i in vids]
    mw = obj.matrix_world
    return [mw @ co for co in local]


def _on_face(pts, weights):
    return sum((p * w for p, w in zip(pts, weights)), Vector())


def link_points(link, cache):
    """Текущие мировые концы живого размера [A, B]; None, если привязка потеряна."""
    fa = _face_world(link.obj_a, link.face_a, _ints(link.verts_a), cache)
    fb = _face_world(link.obj_b, link.face_b, _ints(link.verts_b), cache)
    if fa is None or fb is None:
        return None
    a = _on_face(fa, _floats(link.weights_a))
    if link.kind == 'THICK':
        # толщина: от A по нормали грани A до плоскости грани B
        na = geometry.normal(fa)
        nb = geometry.normal(fb)
        denom = na.dot(nb)
        if abs(denom) > 0.1:
            return [a, a + na * ((fb[0] - a).dot(nb) / denom)]
        return [a, a - nb * (a - fb[0]).dot(nb)]
    return [a, _on_face(fb, _floats(link.weights_b))]


def _base_mesh(obj):
    """Вершины и грани исходного меша (в Edit Mode — из BMesh, индексы как у меша после выхода)."""
    me = obj.data
    if me.is_editmode:
        bm = bmesh.from_edit_mesh(me)
        bm.verts.index_update()
        return [v.co.copy() for v in bm.verts], [[v.index for v in f.verts] for f in bm.faces]
    return [v.co.copy() for v in me.vertices], [list(p.vertices) for p in me.polygons]


def _bind_point(p, objects):
    """Ближайшая к мировой точке p грань: (obj, face, vids, weights) или None."""
    best = None
    for obj in objects:
        verts, polys = _base_mesh(obj)
        if not polys:
            continue
        mw = obj.matrix_world
        loc, _, face, _ = BVHTree.FromPolygons(verts, polys).find_nearest(mw.inverted_safe() @ p)
        if loc is None:
            continue
        dist = (mw @ loc - p).length
        tol = 1e-4 * max(1.0, max(obj.dimensions))
        if dist <= tol and (best is None or dist < best[0]):
            best = (dist, obj, face, polys[face], [mw @ verts[i] for i in polys[face]])
    if best is None:
        return None
    _, obj, face, vids, world = best
    return obj, face, vids, interpolate.poly_3d_calc(world, p)


def add_link(props, pa, pb, objects):
    """Живой размер между мировыми точками pa и pb, если обе лежат на гранях объектов."""
    a = _bind_point(pa, objects)
    b = _bind_point(pb, objects)
    if a is None or b is None:
        return None
    link = props.links.add()
    link.obj_a, link.face_a = a[0], a[1]
    link.verts_a = ",".join(map(str, a[2]))
    link.weights_a = ",".join("{:.9g}".format(w) for w in a[3])
    link.obj_b, link.face_b = b[0], b[1]
    link.verts_b = ",".join(map(str, b[2]))
    link.weights_b = ",".join("{:.9g}".format(w) for w in b[3])
    # Shift-линейка: A внутри грани, отрезок идёт по её нормали -> толщина стенки
    d = pb - pa
    if d.length and min(a[3]) > 1e-4:
        na = geometry.normal(_face_world(a[0], a[1], a[2], {}))
        if abs(d.normalized().dot(na)) > 0.9995:
            link.kind = 'THICK'
    return link


class _Recolor:
    """props с подменённым цветом линий и текста — для живых размеров."""

    def __init__(self, props, color):
        self._props = props
        self.line_color = self.text_color = color

    def __getattr__(self, name):
        return getattr(self._props, name)


# --- Калибровка Empty-картинки по линейке ---------------------------------------

def is_reference(obj):
    return obj is not None and obj.type == 'EMPTY' and obj.empty_display_type == 'IMAGE'


def to_image_plane(obj, p, region=None, rv3d=None):
    """Точка на плоскости картинки (локальная XY Empty), видимая там же, где p.
    С видом — по лучу взгляда, без вида — ортогональной проекцией. None, если вид вдоль плоскости."""
    mw = obj.matrix_world
    co = mw.translation
    no = (mw.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
    if region is not None and rv3d is not None:
        p2d = view3d_utils.location_3d_to_region_2d(region, rv3d, p)
        if p2d is not None:
            origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, p2d)
            direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, p2d)
            return geometry.intersect_line_plane(origin, origin + direction, co, no)
    return p - no * (p - co).dot(no)


def calibrate(obj, a, b, length):
    """Равномерно масштабирует obj относительно a так, чтобы отрезок a-b стал length. Возвращает k."""
    k = length / (b - a).length
    obj.matrix_world = Matrix.Translation(a) @ Matrix.Scale(k, 4) @ Matrix.Translation(-a) @ obj.matrix_world
    return k


def _set_stroke(key, points):
    """Переставляет точки родной линейки с данным ключом."""
    for ann in bpy.data.annotations:
        for layer in ann.layers:
            af = layer.active_frame if getattr(layer, "is_ruler", False) else None
            for st in (af.strokes if af else ()):
                if _stroke_key([Vector(p.co) for p in st.points]) == key:
                    for p, co in zip(st.points, points):
                        p.co = co
                    return


def _draw_lines(points, prim, color, width):
    # line_width_set не работает на Metal — толщину даёт polyline-шейдер
    shader = _get_shader('POLYLINE_UNIFORM_COLOR')
    gpu.state.blend_set('ALPHA')
    batch = batch_for_shader(shader, prim, {"pos": [(p[0], p[1], 0.0) for p in points]})
    _, _, w, h = gpu.state.viewport_get()
    shader.bind()
    shader.uniform_float("viewportSize", (float(w), float(h)))
    shader.uniform_float("lineWidth", width)
    shader.uniform_float("color", color)
    batch.draw(shader)


def _line(a, b, color, width):
    _draw_lines([a, b], 'LINES', color, width)


def _polyline(points, color, width):
    if len(points) < 2:
        return
    _draw_lines(points, 'LINE_STRIP', color, width)


def _tris(points, color):
    shader = _get_shader('UNIFORM_COLOR')
    gpu.state.blend_set('ALPHA')
    batch = batch_for_shader(shader, 'TRIS', {"pos": points})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def _arrow_outward(tip, outward_unit, size, color):
    """Tip at 'tip', body inside -> arrow points outward (normal dimension)."""
    d = outward_unit.normalized() if outward_unit.length else Vector((1, 0))
    perp = Vector((-d.y, d.x))
    base = tip - d * size
    _tris([tuple(tip), tuple(base + perp * size * 0.45), tuple(base - perp * size * 0.45)], color)


def _arrow_inward(tip, outward_unit, size, color):
    """Tip at 'tip', body outside -> arrow points inward (small dimension)."""
    d = outward_unit.normalized() if outward_unit.length else Vector((1, 0))
    perp = Vector((-d.y, d.x))
    base = tip + d * size
    _tris([tuple(tip), tuple(base + perp * size * 0.45), tuple(base - perp * size * 0.45)], color)


def _endcap(pt, outward_dir, props, color):
    style = props.endcap_style
    d = outward_dir.normalized() if outward_dir.length else Vector((1, 0))
    perp = Vector((-d.y, d.x))
    if style == 'TICK':
        L = props.tick_length
        _line(pt + perp * L * 0.5, pt - perp * L * 0.5, color, props.line_width)
    elif style == 'ARROW':
        _arrow_outward(pt, d, props.arrow_size, color)


def _text_dims(text, size):
    blf.size(0, size)
    return blf.dimensions(0, text)


def _bg_quad_axis(center, dr, up, hw, hh, props):
    if not props.text_bg:
        return
    col = (*props.bg_color, props.bg_alpha)
    c00 = center - dr * hw - up * hh
    c10 = center + dr * hw - up * hh
    c11 = center + dr * hw + up * hh
    c01 = center - dr * hw + up * hh
    _tris([tuple(c00), tuple(c10), tuple(c11)], col)
    _tris([tuple(c00), tuple(c11), tuple(c01)], col)


def _draw_text_h(pos2d, text, props):
    """Horizontal centered text with optional background."""
    fid = 0
    blf.size(fid, props.font_size)
    tw, th = blf.dimensions(fid, text)
    if props.text_bg:
        pad = 4
        _bg_quad_axis(Vector(pos2d), Vector((1, 0)), Vector((0, 1)),
                      tw * 0.5 + pad, th * 0.5 + pad, props)
    blf.position(fid, pos2d.x - tw * 0.5, pos2d.y - th * 0.5, 0)
    blf.color(fid, *props.text_color, 1.0)
    blf.draw(fid, text)


def _draw_text_along(center, line_dir, text, props):
    """Text centered, rotated to run along line_dir, sitting above the line."""
    fid = 0
    d = line_dir.normalized() if line_dir.length else Vector((1, 0))
    ang = math.atan2(d.y, d.x)
    # keep upright/readable
    if ang > math.pi / 2:
        ang -= math.pi
    elif ang < -math.pi / 2:
        ang += math.pi
    dr = Vector((math.cos(ang), math.sin(ang)))
    up = Vector((-dr.y, dr.x))
    if up.y < 0:
        up = -up
    blf.size(fid, props.font_size)
    tw, th = blf.dimensions(fid, text)
    # place above the line
    text_center = Vector(center) + up * (props.text_gap + th * 0.5)
    # background (rotated)
    pad = 4
    _bg_quad_axis(text_center, dr, up, tw * 0.5 + pad, th * 0.5 + pad, props)
    # baseline start so glyphs center on text_center
    start = text_center - dr * (tw * 0.5) - up * (th * 0.5)
    blf.enable(fid, blf.ROTATION)
    blf.rotation(fid, ang)
    blf.position(fid, start.x, start.y, 0)
    blf.color(fid, *props.text_color, 1.0)
    blf.draw(fid, text)
    blf.disable(fid, blf.ROTATION)


def _away_from_center(region, rv3d, pt2d):
    """Экранный вектор от проекции начала координат к точке; None, если начало за камерой."""
    c2d = view3d_utils.location_3d_to_region_2d(region, rv3d, Vector((0.0, 0.0, 0.0)))
    return None if c2d is None else pt2d - c2d


def _draw_distance(pts, props, region, rv3d):
    a3d, b3d = pts[0], pts[1]
    a2d = view3d_utils.location_3d_to_region_2d(region, rv3d, a3d)
    b2d = view3d_utils.location_3d_to_region_2d(region, rv3d, b3d)
    if a2d is None or b2d is None:
        return
    color = (*props.line_color, 1.0)
    direction = b2d - a2d
    if direction.length == 0:
        return
    perp = Vector((-direction.y, direction.x)).normalized()

    # Dimension line endpoints (offset by extension lines if enabled)
    if props.extension_lines and props.ext_offset != 0:
        signed_perp = perp.copy()
        if props.ext_auto_side:
            # от центра сцены на экране; центр на оси размера -> вверх (вертикальный -> вправо)
            away = _away_from_center(region, rv3d, (a2d + b2d) * 0.5)
            s = signed_perp.dot(away) if away is not None else 0.0
            if abs(s) < 1.0:
                s = signed_perp.y or signed_perp.x
            if s < 0:
                signed_perp = -signed_perp
            mag = abs(props.ext_offset)
        else:
            mag = props.ext_offset
        off = signed_perp * mag
        gap = signed_perp * props.ext_gap
        P0 = a2d + off
        P1 = b2d + off
        _line(a2d + gap, P0, color, props.line_width)
        _line(b2d + gap, P1, color, props.line_width)
    else:
        P0, P1 = a2d, b2d

    dist = (b3d - a3d).length
    text = ("{:." + str(props.decimals) + "f}").format(dist) + props.unit_suffix
    d = (P1 - P0).normalized()
    tw, th = _text_dims(text, props.font_size)
    # «малый» — когда на экране между концами не помещаются текст и стрелки
    caps = 2.0 * props.arrow_size if props.endcap_style == 'ARROW' else 0.0

    if (P1 - P0).length < tw + caps + 8.0:
        # Small style: arrows outside pointing in, dimension line extended, leader + shelf + text
        stub = max(props.arrow_size, 8.0) * 1.4
        out0 = P0 - d * stub
        out1 = P1 + d * stub
        _line(out0, out1, color, props.line_width)
        _arrow_inward(P0, -d, props.arrow_size, color)
        _arrow_inward(P1, d, props.arrow_size, color)
        # выноска — в сторону от центра сцены на экране
        anchor = (P0 + P1) * 0.5
        away = _away_from_center(region, rv3d, anchor)
        side = -1.0 if away is not None and away.x < 0.0 else 1.0
        diag = Vector((side, 1.0)).normalized()
        elbow = anchor + diag * props.small_leader_length
        shelf_len = tw + 12.0
        shelf_end = elbow + Vector((side, 0.0)) * shelf_len
        _line(anchor, elbow, color, props.line_width)
        _line(elbow, shelf_end, color, props.line_width)
        # text above the shelf, centered over it
        text_center = (elbow + shelf_end) * 0.5 + Vector((0.0, th * 0.5 + props.text_gap))
        _draw_text_h(text_center, text, props)
    else:
        # Normal style: arrows/ticks at ends, text along axis above the line
        _line(P0, P1, color, props.line_width)
        _endcap(P0, P0 - P1, props, color)
        _endcap(P1, P1 - P0, props, color)
        _draw_text_along((P0 + P1) * 0.5, d, text, props)


def _draw_angle(pts, props, region, rv3d):
    a3d, c3d, b3d = pts[0], pts[1], pts[2]
    a2d = view3d_utils.location_3d_to_region_2d(region, rv3d, a3d)
    c2d = view3d_utils.location_3d_to_region_2d(region, rv3d, c3d)
    b2d = view3d_utils.location_3d_to_region_2d(region, rv3d, b3d)
    if None in (a2d, c2d, b2d):
        return
    color = (*props.line_color, 1.0)
    _line(c2d, a2d, color, props.line_width)
    _line(c2d, b2d, color, props.line_width)
    v1 = (a3d - c3d)
    v2 = (b3d - c3d)
    if v1.length == 0 or v2.length == 0:
        return
    ang = math.degrees(v1.angle(v2))
    text = ("{:." + str(props.decimals) + "f}").format(ang) + "\u00b0"
    da = (a2d - c2d)
    db = (b2d - c2d)
    if da.length == 0 or db.length == 0:
        return
    a_ang = math.atan2(da.y, da.x)
    b_ang = math.atan2(db.y, db.x)
    diff = (b_ang - a_ang + math.pi) % (2 * math.pi) - math.pi
    R = props.arc_radius
    segs = 24
    arc_pts = [c2d + Vector((math.cos(a_ang + diff * (i / segs)),
                             math.sin(a_ang + diff * (i / segs)))) * R for i in range(segs + 1)]
    _polyline(arc_pts, color, props.line_width)
    mid_ang = a_ang + diff * 0.5
    label_pos = c2d + Vector((math.cos(mid_ang), math.sin(mid_ang))) * (R + props.font_size)
    _draw_text_h(label_pos, text, props)


def draw_callback():
    ctx = bpy.context
    props = getattr(ctx.scene, "pretty_ruler", None)
    if props is None or not props.enabled:
        return
    region = ctx.region
    rv3d = ctx.region_data
    if rv3d is None:
        return
    hidden = {it.key for it in props.items if not it.enabled}
    for pts in get_ruler_strokes():
        if hidden and _stroke_key(pts) in hidden:
            continue
        if len(pts) == 2:
            _draw_distance(pts, props, region, rv3d)
        elif len(pts) == 3:
            _draw_angle(pts, props, region, rv3d)
    if props.links:
        linked_props = _Recolor(props, props.link_color)
        cache = {}
        space = ctx.space_data
        for link in props.links:
            if not link.enabled:
                continue
            # размер скрытого объекта (или вне Local View) не рисуем
            if not all(o is not None and o.visible_get(viewport=space) for o in (link.obj_a, link.obj_b)):
                continue
            pts = link_points(link, cache)
            if pts is not None:
                _draw_distance(pts, linked_props, region, rv3d)
    gpu.state.blend_set('NONE')


def enable_draw():
    global _handle
    if _handle is None:
        _handle = bpy.types.SpaceView3D.draw_handler_add(draw_callback, (), 'WINDOW', 'POST_PIXEL')


def disable_draw():
    global _handle
    if _handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_handle, 'WINDOW')
        _handle = None


def redraw_all(self, context):
    for area in context.screen.areas:
        if area.type == 'VIEW_3D':
            area.tag_redraw()


def update_enabled(self, context):
    if self.enabled:
        sync_items(self)
    redraw_all(self, context)


def _switch_tool(tool_id):
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        with bpy.context.temp_override(window=win, area=area, region=region):
                            try:
                                bpy.ops.wm.tool_set_by_id(name=tool_id)
                            except Exception:
                                pass
                        return


def update_hide_native(self, context):
    target = 0.0 if self.hide_native else 1.0
    for ann in bpy.data.annotations:
        for layer in ann.layers:
            if getattr(layer, "is_ruler", False):
                layer.annotation_opacity = target
    if self.hide_native:
        _switch_tool("builtin.select_box")
    redraw_all(self, context)


class PrettyRulerItem(bpy.types.PropertyGroup):
    enabled: bpy.props.BoolProperty(name="", default=True, update=redraw_all)
    name: bpy.props.StringProperty(default="Ruler")
    key: bpy.props.StringProperty()


class PrettyRulerLink(bpy.types.PropertyGroup):
    enabled: bpy.props.BoolProperty(name="", default=True, update=redraw_all)
    kind: bpy.props.EnumProperty(
        items=[('DIST', "Distance", ""), ('THICK', "Thickness", "")], default='DIST')
    obj_a: bpy.props.PointerProperty(type=bpy.types.Object)
    face_a: bpy.props.IntProperty(default=-1)
    verts_a: bpy.props.StringProperty()
    weights_a: bpy.props.StringProperty()
    obj_b: bpy.props.PointerProperty(type=bpy.types.Object)
    face_b: bpy.props.IntProperty(default=-1)
    verts_b: bpy.props.StringProperty()
    weights_b: bpy.props.StringProperty()


class PRETTYRULER_OT_refresh(bpy.types.Operator):
    bl_idname = "pretty_ruler.refresh"
    bl_label = "Refresh List"
    bl_description = "Sync the list with current ruler measurements"

    def execute(self, context):
        sync_items(context.scene.pretty_ruler)
        redraw_all(self, context)
        return {'FINISHED'}


class PRETTYRULER_OT_link(bpy.types.Operator):
    bl_idname = "pretty_ruler.link"
    bl_label = "Link to Geometry"
    bl_description = ("Glue rulers that lie on mesh faces to those faces: the dimensions "
                      "follow mesh edits. A Shift ruler becomes a wall thickness")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.pretty_ruler
        objects = [o for o in context.visible_objects if o.type == 'MESH']
        strokes = get_ruler_strokes()
        linked = [pts for pts in strokes if len(pts) == 2 and add_link(props, pts[0], pts[1], objects)]
        if not linked:
            self.report({'WARNING'}, "No ruler lies on mesh faces")
            return {'CANCELLED'}
        if len(linked) == len(strokes):
            # все линейки стали живыми — убираем родные; инструмент Measure сначала
            # выключаем, иначе он запишет свои линейки обратно
            _switch_tool("builtin.select_box")
            for ann in bpy.data.annotations:
                for layer in ann.layers:
                    if getattr(layer, "is_ruler", False) and layer.active_frame:
                        layer.frames.remove(layer.active_frame)
        else:
            # strokes по одной удалить нельзя — просто не рисуем привязанные
            sync_items(props)
            keys = {_stroke_key(pts) for pts in linked}
            for it in props.items:
                if it.key in keys:
                    it.enabled = False
        props.enabled = True
        sync_items(props)
        self.report({'INFO'}, "Linked %d of %d rulers" % (len(linked), len(strokes)))
        redraw_all(self, context)
        return {'FINISHED'}


class PRETTYRULER_OT_link_remove(bpy.types.Operator):
    bl_idname = "pretty_ruler.link_remove"
    bl_label = "Remove Linked Dimension"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.pretty_ruler
        if 0 <= props.active_link < len(props.links):
            props.links.remove(props.active_link)
            props.active_link = min(props.active_link, len(props.links) - 1)
        redraw_all(self, context)
        return {'FINISHED'}


class PRETTYRULER_OT_calibrate(bpy.types.Operator):
    bl_idname = "pretty_ruler.calibrate"
    bl_label = "Calibrate"
    bl_description = ("Scale the active reference image about the ruler's first point "
                      "so the ruler reads Real Length")
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return is_reference(context.active_object)

    def execute(self, context):
        props = context.scene.pretty_ruler
        sync_items(props)
        strokes = {_stroke_key(pts): pts for pts in get_ruler_strokes()}
        dists = [it for it in props.items if len(strokes.get(it.key, ())) == 2]
        if len(dists) == 1:
            item = dists[0]
        elif 0 <= props.active_index < len(props.items):
            item = props.items[props.active_index]
        else:
            item = None
        pts = strokes.get(item.key) if item else None
        if pts is None or len(pts) != 2:
            self.report({'WARNING'}, "Select a distance ruler in the Measurements list")
            return {'CANCELLED'}

        obj = context.active_object
        area = context.area
        region = rv3d = None
        if area is not None and area.type == 'VIEW_3D':
            region = next((r for r in area.regions if r.type == 'WINDOW'), None)
            rv3d = area.spaces.active.region_3d
        a = to_image_plane(obj, pts[0], region, rv3d)
        b = to_image_plane(obj, pts[1], region, rv3d)
        if a is None or b is None or (b - a).length < 1e-9:
            self.report({'WARNING'}, "Look at the image face-on: the ruler does not land on it")
            return {'CANCELLED'}

        k = calibrate(obj, a, b, props.calib_length)
        # линейка встаёт на картинку и показывает реальную длину; Measure сначала
        # выключаем, иначе он перезапишет точки
        _switch_tool("builtin.select_box")
        _set_stroke(item.key, [a, a + (b - a) * k])
        sync_items(props)
        self.report({'INFO'}, "Scaled '%s' by %.4f" % (obj.name, k))
        redraw_all(self, context)
        return {'FINISHED'}


class PRETTYRULER_UL_items(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.label(text=item.name)


class PRETTYRULER_UL_links(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        pts = link_points(item, {})
        if pts is None:
            row.label(text="Lost", icon='ERROR')
        else:
            row.label(text=_label(pts, data),
                      icon='MOD_SOLIDIFY' if item.kind == 'THICK' else 'DRIVER_DISTANCE')


class PrettyRulerProps(bpy.types.PropertyGroup):
    enabled: bpy.props.BoolProperty(name="Enabled", default=False, update=update_enabled)
    items: bpy.props.CollectionProperty(type=PrettyRulerItem)
    active_index: bpy.props.IntProperty(default=0)
    links: bpy.props.CollectionProperty(type=PrettyRulerLink)
    active_link: bpy.props.IntProperty(default=0)
    calib_length: bpy.props.FloatProperty(name="Real Length", default=10.0, min=0.0001, precision=3)
    endcap_style: bpy.props.EnumProperty(
        name="End Cap",
        items=[('TICK', "Tick", ""), ('ARROW', "Arrow", ""), ('NONE', "None", "")],
        default='ARROW', update=redraw_all)
    tick_length: bpy.props.FloatProperty(name="Tick Length", default=14.0, min=0, max=100, update=redraw_all)
    arrow_size: bpy.props.FloatProperty(name="Arrow Size", default=12.0, min=2, max=60, update=redraw_all)
    line_width: bpy.props.FloatProperty(name="Line Width", default=2.0, min=0.5, max=10, update=redraw_all)
    font_size: bpy.props.IntProperty(name="Font Size", default=18, min=6, max=120, update=redraw_all)
    decimals: bpy.props.IntProperty(name="Decimals", default=2, min=0, max=4, update=redraw_all)
    small_leader_length: bpy.props.FloatProperty(name="Leader Length", default=45.0, min=10, max=300, update=redraw_all)
    text_gap: bpy.props.FloatProperty(name="Text Gap", default=6.0, min=0, max=50, update=redraw_all)
    unit_suffix: bpy.props.StringProperty(name="Unit Suffix", default=" mm", update=redraw_all)
    extension_lines: bpy.props.BoolProperty(name="Extension Lines", default=False, update=redraw_all)
    ext_offset: bpy.props.FloatProperty(name="Offset", default=40.0, min=-300, max=300, update=redraw_all)
    ext_gap: bpy.props.FloatProperty(name="Gap", default=6.0, min=0, max=50, update=redraw_all)
    ext_auto_side: bpy.props.BoolProperty(name="Auto Side (scene center)", default=True, update=redraw_all)
    arc_radius: bpy.props.FloatProperty(name="Arc Radius", default=40.0, min=10, max=200, update=redraw_all)
    line_color: bpy.props.FloatVectorProperty(name="Line", subtype='COLOR', size=3, default=(1, 1, 1), min=0, max=1, update=redraw_all)
    text_color: bpy.props.FloatVectorProperty(name="Text", subtype='COLOR', size=3, default=(1, 1, 1), min=0, max=1, update=redraw_all)
    link_color: bpy.props.FloatVectorProperty(name="Linked", subtype='COLOR', size=3, default=(1.0, 0.6, 0.1), min=0, max=1, update=redraw_all)
    text_bg: bpy.props.BoolProperty(name="Text Background", default=True, update=redraw_all)
    bg_color: bpy.props.FloatVectorProperty(name="BG", subtype='COLOR', size=3, default=(0, 0, 0), min=0, max=1, update=redraw_all)
    bg_alpha: bpy.props.FloatProperty(name="BG Alpha", default=0.6, min=0, max=1, update=redraw_all)
    hide_native: bpy.props.BoolProperty(name="Hide Native Ruler", default=False, update=update_hide_native)


class VIEW3D_PT_pretty_ruler(bpy.types.Panel):
    bl_label = "Pretty Ruler"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Jewelry"

    def draw(self, context):
        layout = self.layout
        p = context.scene.pretty_ruler
        layout.prop(p, "enabled", toggle=True)

        box = layout.box()
        box.label(text="Measurements:")
        box.operator("pretty_ruler.refresh", icon='FILE_REFRESH')
        if len(p.items):
            box.template_list("PRETTYRULER_UL_items", "", p, "items", p, "active_index", rows=4)
        box.operator("pretty_ruler.link", icon='LINKED')
        if len(p.links):
            row = box.row()
            row.template_list("PRETTYRULER_UL_links", "", p, "links", p, "active_link", rows=3)
            row.column(align=True).operator("pretty_ruler.link_remove", icon='X', text="")

        box = layout.box()
        box.label(text="Calibrate Reference:")
        obj = context.active_object
        if is_reference(obj):
            box.label(text=obj.name, icon='IMAGE_REFERENCE')
        else:
            box.label(text="Select a reference image", icon='INFO')
        row = box.row(align=True)
        row.prop(p, "calib_length")
        row.operator("pretty_ruler.calibrate")

        col = layout.column()
        col.enabled = p.enabled
        col.prop(p, "endcap_style")
        if p.endcap_style == 'TICK':
            col.prop(p, "tick_length")
        elif p.endcap_style == 'ARROW':
            col.prop(p, "arrow_size")
        col.prop(p, "line_width")
        col.separator()
        col.label(text="Text:")
        col.prop(p, "font_size")
        col.prop(p, "decimals")
        col.prop(p, "text_gap")
        col.prop(p, "unit_suffix")
        col.separator()
        col.label(text="Small Dimension:")
        col.prop(p, "small_leader_length")
        col.separator()
        col.label(text="Extension Lines:")
        col.prop(p, "extension_lines")
        sub = col.column()
        sub.enabled = p.extension_lines
        sub.prop(p, "ext_auto_side")
        sub.prop(p, "ext_offset")
        sub.prop(p, "ext_gap")
        col.separator()
        col.label(text="Angle:")
        col.prop(p, "arc_radius")
        col.separator()
        col.label(text="Colors:")
        col.prop(p, "line_color")
        col.prop(p, "text_color")
        col.prop(p, "link_color")
        col.prop(p, "text_bg")
        s2 = col.column()
        s2.enabled = p.text_bg
        s2.prop(p, "bg_color")
        s2.prop(p, "bg_alpha")
        col.separator()
        col.prop(p, "hide_native")


classes = (PrettyRulerItem, PrettyRulerLink, PrettyRulerProps, PRETTYRULER_OT_refresh, PRETTYRULER_OT_link,
           PRETTYRULER_OT_link_remove, PRETTYRULER_OT_calibrate, PRETTYRULER_UL_items, PRETTYRULER_UL_links,
           VIEW3D_PT_pretty_ruler)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.pretty_ruler = bpy.props.PointerProperty(type=PrettyRulerProps)
    # Обработчик живёт всё время работы аддона: состояние Enabled хранится в .blend,
    # а update-колбэк при открытии файла не вызывается
    enable_draw()
    if not bpy.app.timers.is_registered(_sync_timer):
        bpy.app.timers.register(_sync_timer, first_interval=SYNC_INTERVAL, persistent=True)


def unregister():
    if bpy.app.timers.is_registered(_sync_timer):
        bpy.app.timers.unregister(_sync_timer)
    disable_draw()
    if hasattr(bpy.types.Scene, "pretty_ruler"):
        del bpy.types.Scene.pretty_ruler
    for c in reversed(classes):
        try:
            bpy.utils.unregister_class(c)
        except Exception:
            pass


if __name__ == "__main__":
    register()
