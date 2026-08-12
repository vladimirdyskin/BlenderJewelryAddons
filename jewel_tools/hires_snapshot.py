# Hi-Res снимок вьюпорта (OpenGL), разрешение не зависит от размера окна.
# bpy.ops.render.opengl(write_still=True, view_context=True) рисует активный вьюпорт
# в scene.render.resolution_x/y. Настройки рендера сохраняются и восстанавливаются.
#
# Layout:
#   SINGLE — один активный вьюпорт (как было).
#   QUAD   — 4 вида Quad View (Ctrl+Alt+Q) одного вьюпорта, склейка 2x2.
#            render.opengl игнорирует override региона и берёт активный space.region_3d,
#            поэтому 4 вида рендерятся прогоном активного region_3d через состояния
#            region_quadviews (с восстановлением). Раскладка: TL=Front, TR=Right,
#            BL=Top, BR=User (стандартный порядок Quad View).
#   SIDE   — несколько отдельных вьюпортов рядом, склейка в ряд (слева направо).
# Склейка тайлов через numpy (встроен в Blender). Тайлы — в общем разрешении resolution_x/y.

import bpy
import os


def _win_regions(area):
    return [r for r in area.regions if r.type == 'WINDOW']


def _set_render(r, res_x, res_y, fmt, path):
    r.resolution_x = res_x
    r.resolution_y = res_y
    r.resolution_percentage = 100
    r.image_settings.file_format = fmt
    r.filepath = path


def _render(context, win, area, region):
    with context.temp_override(window=win, area=area, region=region):
        bpy.ops.render.opengl(write_still=True, view_context=True)


def _load_rgba(path):
    import numpy as np
    img = bpy.data.images.load(path)
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    bpy.data.images.remove(img)
    return buf.reshape(h, w, 4)  # строки снизу вверх (как в Blender)


def _save_rgba(arr, path, fmt):
    import numpy as np
    h, w = arr.shape[:2]
    out = bpy.data.images.new("jt_composite", w, h, alpha=True)
    out.pixels.foreach_set(np.ascontiguousarray(arr, dtype=np.float32).ravel())
    out.file_format = fmt
    out.filepath_raw = path
    out.save()
    bpy.data.images.remove(out)


def _save_rv(v):
    return (v.view_perspective, v.view_rotation.copy(), v.view_location.copy(), v.view_distance)


def _apply_rv(v, s):
    v.view_perspective = s[0]
    v.view_rotation = s[1]
    v.view_location = s[2]
    v.view_distance = s[3]


class RENDER_OT_hires_viewport_snapshot(bpy.types.Operator):
    bl_idname = "render.hires_viewport_snapshot"
    bl_label = "Hi-Res Viewport Snapshot"
    bl_description = "OpenGL snapshot of the viewport(s) at a custom resolution (bigger than screen)"
    bl_options = {'REGISTER'}

    resolution_x: bpy.props.IntProperty(name="Resolution X", default=4000, min=4, soft_max=16000)
    resolution_y: bpy.props.IntProperty(name="Resolution Y", default=4000, min=4, soft_max=16000)
    filepath: bpy.props.StringProperty(name="Output", default="/tmp/viewport_hi.png", subtype='FILE_PATH')
    file_format: bpy.props.EnumProperty(name="Format",
        items=[('PNG', 'PNG', ''), ('JPEG', 'JPEG', ''), ('TIFF', 'TIFF', '')], default='PNG')
    background: bpy.props.EnumProperty(name="Background",
        items=[('THEME', 'Theme', 'Use viewport theme color'),
               ('TRANSPARENT', 'Transparent', 'Alpha background for compositing (PNG/TIFF)'),
               ('COLOR', 'Color', 'Custom solid color (solid shading only)')],
        default='THEME')
    bg_color: bpy.props.FloatVectorProperty(name="BG Color", subtype='COLOR', size=3,
        min=0.0, max=1.0, default=(0.05, 0.05, 0.05))
    layout: bpy.props.EnumProperty(name="Layout",
        items=[('SINGLE', 'Single', 'One active viewport'),
               ('QUAD', 'Quad 2x2', 'Four views of a Quad View viewport'),
               ('SIDE', 'Side by side', 'All viewports in a row, left to right')],
        default='SINGLE')

    def _apply_background(self, r, shadings):
        # вернуть кортеж для восстановления; shadings — список View3DShading задействованных областей
        old_r = (r.image_settings.color_mode, r.film_transparent)
        old_sh = [(sh, sh.background_type, tuple(sh.background_color)) for sh in shadings]
        if self.background == 'TRANSPARENT':
            r.film_transparent = True
            r.image_settings.color_mode = 'RGBA'
        elif self.background == 'COLOR':
            for sh in shadings:
                sh.background_type = 'VIEWPORT'
                sh.background_color = self.bg_color
        return old_r, old_sh

    def _restore_background(self, r, old_r, old_sh):
        r.image_settings.color_mode, r.film_transparent = old_r
        for sh, bt, bc in old_sh:
            sh.background_type = bt
            sh.background_color = bc

    def execute(self, context):
        import numpy as np

        win = context.window
        v3d = [a for a in win.screen.areas if a.type == 'VIEW_3D']
        if not v3d:
            self.report({'ERROR'}, "No 3D viewport found")
            return {'CANCELLED'}

        r = context.scene.render
        old_res = (r.resolution_x, r.resolution_y, r.resolution_percentage,
                   r.filepath, r.image_settings.file_format)
        rx, ry, fmt = self.resolution_x, self.resolution_y, self.file_format
        base, ext = os.path.splitext(self.filepath)
        ext = ext or ".png"
        tiles_paths = []

        try:
            if self.layout == 'SINGLE':
                area = context.area if (context.area and context.area.type == 'VIEW_3D') else v3d[0]
                region = max(_win_regions(area), key=lambda rg: rg.width * rg.height)
                old_bg = self._apply_background(r, [area.spaces.active.shading])
                _set_render(r, rx, ry, fmt, self.filepath)
                _render(context, win, area, region)
                self._restore_background(r, *old_bg)

            elif self.layout == 'QUAD':
                area = next((a for a in v3d if len(_win_regions(a)) == 4), None)
                if area is None:
                    self.report({'ERROR'}, "Enable Quad View (Ctrl+Alt+Q) on a viewport first")
                    return {'CANCELLED'}
                space = area.spaces.active
                region = max(_win_regions(area), key=lambda rg: rg.width * rg.height)
                rv = space.region_3d
                states = [_save_rv(q) for q in space.region_quadviews]  # 0=TL,1=BL,2=TR,3=BR
                orig = _save_rv(rv)
                old_bg = self._apply_background(r, [space.shading])
                tiles = []
                try:
                    for i, s in enumerate(states):
                        _apply_rv(rv, s)
                        tp = "%s_t%d%s" % (base, i, ext)
                        _set_render(r, rx, ry, fmt, tp)
                        _render(context, win, area, region)
                        tiles_paths.append(tp)
                        tiles.append(_load_rgba(tp))
                finally:
                    _apply_rv(rv, orig)
                    self._restore_background(r, *old_bg)
                tl, bl, tr, br = tiles
                big = np.concatenate([np.concatenate([bl, br], axis=1),
                                      np.concatenate([tl, tr], axis=1)], axis=0)
                _save_rgba(big, self.filepath, fmt)

            else:  # SIDE
                if len(v3d) < 2:
                    self.report({'ERROR'}, "Need 2+ viewports side by side")
                    return {'CANCELLED'}
                areas = sorted(v3d, key=lambda a: a.x)
                old_bg = self._apply_background(r, [a.spaces.active.shading for a in areas])
                tiles = []
                try:
                    for i, a in enumerate(areas):
                        region = max(_win_regions(a), key=lambda rg: rg.width * rg.height)
                        tp = "%s_t%d%s" % (base, i, ext)
                        _set_render(r, rx, ry, fmt, tp)
                        _render(context, win, a, region)
                        tiles_paths.append(tp)
                        tiles.append(_load_rgba(tp))
                finally:
                    self._restore_background(r, *old_bg)
                big = np.concatenate(tiles, axis=1)  # слева направо
                _save_rgba(big, self.filepath, fmt)
        finally:
            (r.resolution_x, r.resolution_y, r.resolution_percentage,
             r.filepath, r.image_settings.file_format) = old_res
            for p in tiles_paths:
                if os.path.exists(p):
                    os.remove(p)

        self.report({'INFO'}, "Saved %s (%s, %s) -> %s" %
                    (self.layout.lower(), self.background.lower(), fmt, self.filepath))
        return {'FINISHED'}


def _view_menu(self, context):
    self.layout.operator("render.hires_viewport_snapshot", icon='RENDER_STILL')


def register():
    bpy.utils.register_class(RENDER_OT_hires_viewport_snapshot)
    bpy.types.VIEW3D_MT_view.append(_view_menu)


def unregister():
    bpy.types.VIEW3D_MT_view.remove(_view_menu)
    bpy.utils.unregister_class(RENDER_OT_hires_viewport_snapshot)
