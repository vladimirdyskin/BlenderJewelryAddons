# SPDX-License-Identifier: GPL-3.0-or-later

# Design Report в PNG. Данные (камни, караты, вес, Metadata) берутся из установленного
# JewelCraft: report_get.data_collect + report_fmt.data_format, поэтому цифры совпадают
# с его HTML-отчётом. Предупреждений в отчёте нет (show_warnings=False), язык — английский.
# Лист рисуется blf в GPUOffScreen (OpenImageIO в Blender без FreeType, текст не умеет),
# превью вьюпорта (JewelCraft asset.render_preview) вставляется через numpy.

import datetime
import importlib
import sys
from math import ceil
from pathlib import Path

import blf
import bpy
import gpu
import numpy as np
from bpy.props import BoolProperty, IntProperty, StringProperty
from bpy.types import Operator
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix

FONT = 0
PAGE = (1.0, 1.0, 1.0, 1.0)
INK = (0.08, 0.08, 0.08, 1.0)
MUTED = (0.40, 0.40, 0.40, 1.0)
LINE = (0.80, 0.80, 0.80, 1.0)
HEAD = (0.92, 0.92, 0.92, 1.0)

GEM_HEADER = ("Gem", "Cut", "Color", "Size (mm)", "Carats", "Qty", "Sum (ct)")
TEXT_COLUMNS = 3  # первые колонки выравниваются влево, остальные (числа) вправо


def _jewelcraft_package():
    if not hasattr(bpy.types.Scene, "jewelcraft"):
        return None
    for name in list(sys.modules):
        if name == "jewelcraft" or (name.startswith("bl_ext.") and name.endswith(".jewelcraft")):
            return name
    return None


def _collect(pkg):
    report_get = importlib.import_module(f"{pkg}.operators.design_report.report_get")
    report_fmt = importlib.import_module(f"{pkg}.operators.design_report.report_fmt")
    report = report_get.data_collect(show_warnings=False)
    if report.is_empty():
        return None
    report_fmt.data_format(report, lambda text: text, True)
    return report


def _sheet_data(report):
    gems = [(g.stone, g.cut, g.color, str(g.size), f"{g.ct:.3f}", str(g.qty), f"{g.ct_sum:.3f}")
            for g in report.gems]
    foot = ("Total", "", "", "", "", str(sum(g.qty for g in report.gems)),
            f"{sum(g.ct_sum for g in report.gems):.3f}")
    mats = [(name, str(value)) for typ, name, value in report.entries if typ in {"WEIGHT", "VOLUME"}]
    notes = [(name, str(value)) for typ, name, value in report.entries if typ not in {"WEIGHT", "VOLUME"}]
    stem = Path(bpy.data.filepath).stem if bpy.data.filepath else "Untitled"
    return {
        "title": stem,
        "date": datetime.date.today().isoformat(),
        "meta": [(m.name, m.value) for m in report.metadata],
        "gems": gems, "foot": foot, "mats": mats, "notes": notes,
    }


def _text_width(text, size):
    blf.size(FONT, size)
    return blf.dimensions(FONT, text)[0]


def _layout(width, scale, data, preview_size):
    """Раскладка сверху вниз в пикселях. Возвращает ops, высоту, rect превью, ширину таблицы / доступную."""
    k = width / 1600.0
    pad = 48 * k
    inner = width - 2 * pad
    body, head, title = 22 * scale * k, 30 * scale * k, 42 * scale * k
    row_h = body * 2.0
    cell = 16 * k * scale
    ops = []

    def text(x, ytop, h, txt, size, color, right=False):
        w = _text_width(txt, size)
        ops.append(("text", x - w if right else x, ytop + h / 2 + size * 0.36, txt, size, color))

    def rect(x, ytop, w, h, color):
        ops.append(("rect", x, ytop, w, h, color))

    def heading(y, label):
        text(pad, y, head * 1.4, label, head, INK)
        rect(pad, y + head * 1.4, inner, 2 * k, LINE)
        return y + head * 1.4 + 2 * k + row_h * 0.3

    def pairs(y, rows):
        label_w = max(_text_width(name, body) for name, _ in rows) + 40 * k * scale
        for name, value in rows:
            text(pad, y, row_h, name, body, MUTED)
            text(pad + label_w, y, row_h, value, body, INK)
            y += row_h
        return y + pad * 0.5

    y = pad
    if not data["meta"]:  # Metadata JewelCraft (Project, Date) уже несёт имя и дату
        text(pad, y, title * 1.4, data["title"], title, INK)
        y += title * 1.4
        text(pad, y, row_h, data["date"], body, MUTED)
        y += row_h + pad * 0.5

    preview_rect = None
    if preview_size:
        pw, ph = preview_size
        preview_rect = (pad + (inner - pw) / 2, y, pw, ph)
        y += ph + pad * 0.6

    if data["meta"]:
        y = pairs(y, data["meta"])

    overflow = 0.0
    if data["gems"]:
        y = heading(y, "Gems")
        rows = [GEM_HEADER, *data["gems"], data["foot"]]
        widths = [max(_text_width(r[i], body) for r in rows) + 2 * cell for i in range(len(GEM_HEADER))]
        overflow = sum(widths) / inner
        extra = max(0.0, inner - sum(widths)) / len(widths)
        widths = [w + extra for w in widths]
        xs = [pad + sum(widths[:i]) for i in range(len(widths))]

        def table_row(y, row, fill=None):
            if fill:
                rect(pad, y, inner, row_h, fill)
            for i, value in enumerate(row):
                if i < TEXT_COLUMNS:
                    text(xs[i] + cell, y, row_h, value, body, INK)
                else:
                    text(xs[i] + widths[i] - cell, y, row_h, value, body, INK, right=True)

        table_row(y, GEM_HEADER, HEAD)
        y += row_h
        for row in data["gems"]:
            table_row(y, row)
            rect(pad, y + row_h - k, inner, k, LINE)
            y += row_h
        table_row(y, data["foot"], HEAD)
        y += row_h + pad * 0.5

    if data["mats"]:
        y = pairs(heading(y, "Materials"), data["mats"])
    if data["notes"]:
        y = pairs(heading(y, "Notes"), data["notes"])

    return ops, ceil(y + pad * 0.5), preview_rect, overflow


def _draw(ops, width, height):
    """Рисует ops в offscreen, возвращает массив (height, width, 4) uint8, строки снизу вверх."""
    offscreen = gpu.types.GPUOffScreen(width, height)
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    projection = Matrix(((2 / width, 0, 0, -1), (0, 2 / height, 0, -1), (0, 0, 1, 0), (0, 0, 0, 1)))
    try:
        with offscreen.bind():
            fb = gpu.state.active_framebuffer_get()
            fb.clear(color=PAGE)
            with gpu.matrix.push_pop():
                gpu.matrix.load_matrix(Matrix.Identity(4))
                gpu.matrix.load_projection_matrix(projection)
                gpu.state.blend_set('ALPHA')
                for op in ops:
                    if op[0] == "rect":
                        _, x, ytop, w, h, color = op
                        y0, y1 = height - ytop - h, height - ytop
                        batch = batch_for_shader(shader, 'TRIS', {"pos": ((x, y0), (x + w, y0), (x + w, y1), (x, y1))},
                                                 indices=((0, 1, 2), (0, 2, 3)))
                        shader.uniform_float("color", color)
                        batch.draw(shader)
                    else:
                        _, x, ybase, txt, size, color = op
                        blf.size(FONT, size)
                        blf.color(FONT, *color)
                        blf.position(FONT, x, height - ybase, 0)
                        blf.draw(FONT, txt)
                gpu.state.blend_set('NONE')
            buffer = fb.read_color(0, 0, width, height, 4, 0, 'UBYTE')
    finally:
        offscreen.free()
    return np.array(buffer, dtype=np.uint8).reshape(height, width, 4)


OVERSAMPLE = 3  # рендерим крупнее целевого размера, чтобы после обрезки по модели хватило пикселей


def _resize(pixels, width, height):
    src_h, src_w = pixels.shape[:2]
    image = bpy.data.images.new("jewel_report_scale", src_w, src_h, alpha=True)
    try:
        image.pixels.foreach_set(np.ascontiguousarray(pixels, dtype=np.float32).ravel())
        image.scale(width, height)
        out = np.empty(width * height * 4, dtype=np.float32)
        image.pixels.foreach_get(out)
    finally:
        bpy.data.images.remove(image)
    return out.reshape(height, width, 4)


def _render_preview(context, max_w, max_h):
    """Превью текущего вида: обрезано по границам модели и вписано в max_w x max_h. None, если вид пуст."""
    import tempfile

    pkg = _jewelcraft_package()
    asset = importlib.import_module(f"{pkg}.lib.asset")
    region = context.region
    render_h = min(max_h * OVERSAMPLE, 4000)
    render_w = round(region.width * render_h / region.height)
    with tempfile.TemporaryDirectory() as tempdir:
        path = Path(tempdir) / "design_report_preview.png"
        asset.render_preview(render_w, render_h, path, format="PNG")
        pixels = _load_pixels(path)

    ys, xs = np.nonzero(pixels[..., 3] > 0.02)
    if not len(ys):
        return None
    margin = round(0.02 * max(xs.max() - xs.min(), ys.max() - ys.min()))
    y0, y1 = max(ys.min() - margin, 0), min(ys.max() + margin + 1, pixels.shape[0])
    x0, x1 = max(xs.min() - margin, 0), min(xs.max() + margin + 1, pixels.shape[1])
    crop = pixels[y0:y1, x0:x1]

    # композитим на фон листа до масштабирования: иначе на краях альфы появляется тёмная кайма
    alpha = crop[..., 3:4]
    rgba = np.ones_like(crop)
    rgba[..., :3] = crop[..., :3] * alpha + PAGE[0] * (1.0 - alpha)

    fit = min(max_w / rgba.shape[1], max_h / rgba.shape[0])
    return _resize(rgba, max(1, round(rgba.shape[1] * fit)), max(1, round(rgba.shape[0] * fit)))


def _load_pixels(filepath):
    image = bpy.data.images.load(str(filepath))
    try:
        w, h = image.size
        pixels = np.empty(w * h * 4, dtype=np.float32)
        image.pixels.foreach_get(pixels)
    finally:
        bpy.data.images.remove(image)
    return pixels.reshape(h, w, 4)


def _paste(canvas, pixels, rect):
    height = canvas.shape[0]
    x, ytop, w, h = (round(v) for v in rect)
    row = height - ytop - h
    area = canvas[row:row + h, x:x + w]
    alpha = pixels[..., 3:4]
    rgb = pixels[..., :3] * alpha + area[..., :3].astype(np.float32) / 255.0 * (1.0 - alpha)
    area[..., :3] = np.clip(rgb * 255.0 + 0.5, 0, 255).astype(np.uint8)


def _save_png(canvas, filepath):
    h, w = canvas.shape[:2]
    image = bpy.data.images.new("jewel_design_report", w, h, alpha=True)
    try:
        image.pixels.foreach_set((canvas.astype(np.float32) / 255.0).ravel())
        image.file_format = 'PNG'
        image.filepath_raw = str(filepath)
        image.save()
    finally:
        bpy.data.images.remove(image)


class WM_OT_jewel_design_report_png(Operator):
    bl_idname = "wm.jewel_design_report_png"
    bl_label = "Save Design Report (PNG)"
    bl_description = "Save a PNG summary of gems, carats, weight and notes (data from JewelCraft)"

    width: IntProperty(name="Width", default=1600, min=800, soft_max=4000, subtype='PIXEL')
    use_preview: BoolProperty(name="Preview", description="Include viewport preview image", default=True)
    preview_height: IntProperty(name="Preview Height", default=560, min=100, soft_max=2000, subtype='PIXEL')
    filepath: StringProperty(subtype='FILE_PATH', options={'SKIP_SAVE', 'HIDDEN'})

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.prop(self, "width")
        row = layout.row(heading="Preview")
        row.prop(self, "use_preview", text="")
        sub = row.row()
        sub.enabled = self.use_preview
        sub.prop(self, "preview_height", text="")

    def execute(self, context):
        pkg = _jewelcraft_package()
        if pkg is None:
            self.report({'ERROR'}, "JewelCraft is not enabled")
            return {'CANCELLED'}
        report = _collect(pkg)
        if report is None:
            self.report({'ERROR'}, "Nothing to report")
            return {'CANCELLED'}

        data = _sheet_data(report)
        width = self.width
        inner = width - 2 * 48 * width / 1600.0

        preview_pixels = None
        preview_size = None
        if self.use_preview:
            if context.space_data is None or context.space_data.type != 'VIEW_3D' or context.region is None:
                self.report({'WARNING'}, "No 3D viewport in context, preview skipped")
            else:
                preview_pixels = _render_preview(context, int(inner), self.preview_height)
                if preview_pixels is None:
                    self.report({'WARNING'}, "Nothing visible in the viewport, preview skipped")
                else:
                    preview_size = (preview_pixels.shape[1], preview_pixels.shape[0])

        scale = 1.0
        for _attempt in range(3):
            ops, height, preview_rect, overflow = _layout(width, scale, data, preview_size)
            if overflow <= 1.0:
                break
            scale *= 0.97 / overflow

        canvas = _draw(ops, width, height)
        if preview_pixels is not None:
            _paste(canvas, preview_pixels, preview_rect)

        filepath = Path(self.filepath).with_suffix(".png")
        filepath.parent.mkdir(parents=True, exist_ok=True)
        _save_png(canvas, filepath)
        self.report({'INFO'}, f"Saved {filepath}")
        return {'FINISHED'}

    def invoke(self, context, event):
        directory = bpy.path.abspath(context.scene.jewel_report_dir).strip()
        if directory:
            name = f"{Path(bpy.data.filepath).stem} Report.png" if bpy.data.is_saved else "Design Report.png"
            self.filepath = str(Path(directory) / name)
        elif bpy.data.is_saved:
            blend_path = Path(bpy.data.filepath)
            self.filepath = str(blend_path.parent / f"{blend_path.stem} Report.png")
        else:
            self.filepath = str(Path.home() / "Design Report.png")

        if event.ctrl or not (directory or bpy.data.is_saved):
            context.window_manager.fileselect_add(self)
            return {'RUNNING_MODAL'}
        return self.execute(context)


def register():
    bpy.utils.register_class(WM_OT_jewel_design_report_png)
    bpy.types.Scene.jewel_report_dir = StringProperty(
        name="Report Folder", subtype='DIR_PATH',
        description="Folder for the PNG report; empty saves next to the .blend file")


def unregister():
    del bpy.types.Scene.jewel_report_dir
    bpy.utils.unregister_class(WM_OT_jewel_design_report_png)
