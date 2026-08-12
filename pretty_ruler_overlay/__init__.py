
bl_info = {
    "name": "Pretty Ruler Overlay",
    "author": "Vladimir",
    "version": (0, 7, 0),
    "blender": (5, 1, 0),
    "location": "View3D > Sidebar > View > Pretty Ruler",
    "description": "Styled dimension graphics over the native Measure tool",
    "category": "3D View",
}

import bpy
import blf
import gpu
import math
from gpu_extras.batch import batch_for_shader
from bpy_extras import view3d_utils
from mathutils import Vector

_handle = None
_shader = None


def _get_shader():
    global _shader
    if _shader is None:
        _shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    return _shader


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


def _line(a, b, color, width):
    shader = _get_shader()
    gpu.state.line_width_set(width)
    gpu.state.blend_set('ALPHA')
    batch = batch_for_shader(shader, 'LINES', {"pos": [a, b]})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def _polyline(points, color, width):
    if len(points) < 2:
        return
    shader = _get_shader()
    gpu.state.line_width_set(width)
    gpu.state.blend_set('ALPHA')
    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": points})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def _tris(points, color):
    shader = _get_shader()
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
            mid_world = (a3d + b3d) * 0.5
            desired = 1.0 if mid_world.x >= 0.0 else -1.0
            if abs(signed_perp.x) > 1e-4 and (signed_perp.x * desired) < 0:
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

    if dist < props.small_threshold:
        # Small style: arrows outside pointing in, dimension line extended, leader + shelf + text
        stub = max(props.arrow_size, 8.0) * 1.4
        out0 = P0 - d * stub
        out1 = P1 + d * stub
        _line(out0, out1, color, props.line_width)
        _arrow_inward(P0, -d, props.arrow_size, color)
        _arrow_inward(P1, d, props.arrow_size, color)
        # leader direction by world X
        mid_world = (a3d + b3d) * 0.5
        side = 1.0 if mid_world.x >= 0.0 else -1.0
        anchor = (P0 + P1) * 0.5
        diag = Vector((side, 1.0)).normalized()
        elbow = anchor + diag * props.small_leader_length
        tw, th = _text_dims(text, props.font_size)
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
    props = ctx.scene.pretty_ruler
    region = ctx.region
    rv3d = ctx.region_data
    if rv3d is None:
        return
    items = props.items
    for i, pts in enumerate(get_ruler_strokes()):
        if i < len(items) and not items[i].enabled:
            continue
        if len(pts) == 2:
            _draw_distance(pts, props, region, rv3d)
        elif len(pts) == 3:
            _draw_angle(pts, props, region, rv3d)
    gpu.state.line_width_set(1.0)
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
    enable_draw() if self.enabled else disable_draw()
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


class PRETTYRULER_OT_refresh(bpy.types.Operator):
    bl_idname = "pretty_ruler.refresh"
    bl_label = "Refresh List"
    bl_description = "Sync the list with current ruler measurements"

    def execute(self, context):
        props = context.scene.pretty_ruler
        strokes = get_ruler_strokes()
        old = [it.enabled for it in props.items]
        props.items.clear()
        dec = props.decimals
        for i, pts in enumerate(strokes):
            it = props.items.add()
            it.enabled = old[i] if i < len(old) else True
            if len(pts) == 2:
                dist = (pts[1] - pts[0]).length
                it.name = ("{:." + str(dec) + "f}").format(dist) + props.unit_suffix
            elif len(pts) == 3:
                v1 = pts[0] - pts[1]
                v2 = pts[2] - pts[1]
                if v1.length and v2.length:
                    ang = math.degrees(v1.angle(v2))
                    it.name = "\u2220 " + ("{:." + str(dec) + "f}").format(ang) + "\u00b0"
                else:
                    it.name = "Angle"
            else:
                it.name = "Ruler " + str(i)
        redraw_all(self, context)
        return {'FINISHED'}


class PRETTYRULER_UL_items(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.label(text=item.name)


class PrettyRulerProps(bpy.types.PropertyGroup):
    enabled: bpy.props.BoolProperty(name="Enabled", default=False, update=update_enabled)
    items: bpy.props.CollectionProperty(type=PrettyRulerItem)
    active_index: bpy.props.IntProperty(default=0)
    endcap_style: bpy.props.EnumProperty(
        name="End Cap",
        items=[('TICK', "Tick", ""), ('ARROW', "Arrow", ""), ('NONE', "None", "")],
        default='ARROW', update=redraw_all)
    tick_length: bpy.props.FloatProperty(name="Tick Length", default=14.0, min=0, max=100, update=redraw_all)
    arrow_size: bpy.props.FloatProperty(name="Arrow Size", default=12.0, min=2, max=60, update=redraw_all)
    line_width: bpy.props.FloatProperty(name="Line Width", default=2.0, min=0.5, max=10, update=redraw_all)
    font_size: bpy.props.IntProperty(name="Font Size", default=18, min=6, max=120, update=redraw_all)
    decimals: bpy.props.IntProperty(name="Decimals", default=2, min=0, max=4, update=redraw_all)
    small_threshold: bpy.props.FloatProperty(name="Small Threshold", default=1.0, min=0, max=50, update=redraw_all)
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
    text_bg: bpy.props.BoolProperty(name="Text Background", default=True, update=redraw_all)
    bg_color: bpy.props.FloatVectorProperty(name="BG", subtype='COLOR', size=3, default=(0, 0, 0), min=0, max=1, update=redraw_all)
    bg_alpha: bpy.props.FloatProperty(name="BG Alpha", default=0.6, min=0, max=1, update=redraw_all)
    hide_native: bpy.props.BoolProperty(name="Hide Native Ruler", default=False, update=update_hide_native)


class VIEW3D_PT_pretty_ruler(bpy.types.Panel):
    bl_label = "Pretty Ruler"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "View"

    def draw(self, context):
        layout = self.layout
        p = context.scene.pretty_ruler
        layout.prop(p, "enabled", toggle=True)

        box = layout.box()
        box.label(text="Measurements:")
        box.operator("pretty_ruler.refresh", icon='FILE_REFRESH')
        if len(p.items):
            box.template_list("PRETTYRULER_UL_items", "", p, "items", p, "active_index", rows=4)

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
        col.prop(p, "small_threshold")
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
        col.prop(p, "text_bg")
        s2 = col.column()
        s2.enabled = p.text_bg
        s2.prop(p, "bg_color")
        s2.prop(p, "bg_alpha")
        col.separator()
        col.prop(p, "hide_native")


classes = (PrettyRulerItem, PrettyRulerProps, PRETTYRULER_OT_refresh, PRETTYRULER_UL_items, VIEW3D_PT_pretty_ruler)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.pretty_ruler = bpy.props.PointerProperty(type=PrettyRulerProps)


def unregister():
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
