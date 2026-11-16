"""Предпросмотр в открытом Blender: ортогональные кадры workbench с временной камеры.

Сцена пользователя не меняется: камера удаляется, настройки рендера возвращаются. Скрытое во вьюпорте
и картинки-подложки (Empty типа Image) в кадр не попадают.

    ns = {}; exec(open(путь).read(), ns)
    ns["preview"]("/tmp/piece", views=("front", "side"), center=(0, 0, -1), size=17, up=(0, -1, 0))
    -> /tmp/piece_front.png, /tmp/piece_side.png

Камни связки My_Stone лежат площадкой по +Z, поэтому «front» — взгляд с +Z. up — что в кадре вверху
(для груши остриём по -Y: up=(0, -1, 0)). size — сторона кадра в мм, она же масштаб для compare.py.
Всегда смотреть не только front / back: стыки и низ деталей видны только в side и q34.
"""
import bpy
from mathutils import Matrix, Vector

VIEWS = {"front": (0, 0, 1), "back": (0, 0, -1), "side": (1, 0, 0), "q34": (0.75, 0.25, 0.6), "q34_left": (-0.75, 0.25, 0.6)}


def preview(out, views=("front", "back", "side", "q34"), center=(0, 0, 0), size=20.0, res=900, up=(0, 1, 0)):
    sc = bpy.context.scene
    r, d = sc.render, sc.display.shading
    keep = (r.engine, r.resolution_x, r.resolution_y, r.resolution_percentage, r.filepath, sc.camera,
            d.light, d.color_type, d.show_cavity, r.image_settings.file_format)
    cam = bpy.data.objects.new("_preview_cam", bpy.data.cameras.new("_preview_cam"))
    sc.collection.objects.link(cam)
    cam.data.type, cam.data.ortho_scale, cam.data.clip_end = "ORTHO", size, 1000
    sc.camera = cam
    r.engine, r.resolution_x, r.resolution_y, r.resolution_percentage = "BLENDER_WORKBENCH", res, res, 100
    r.image_settings.file_format = "PNG"
    d.light, d.color_type, d.show_cavity = "MATCAP", "SINGLE", True
    hidden = [o for o in sc.objects if not o.hide_render
              and (o.hide_get() or (o.type == "EMPTY" and o.empty_display_type == "IMAGE"))]
    for o in hidden:
        o.hide_render = True
    files = []
    try:
        for v in views:
            z = Vector(VIEWS[v]).normalized()
            x = Vector(up).cross(z).normalized()
            m = Matrix((x, z.cross(x), z)).transposed().to_4x4()
            m.translation = Vector(center) + z * 200
            cam.matrix_world = m
            r.filepath = "%s_%s.png" % (out, v)
            bpy.ops.render.render(write_still=True)
            files.append(r.filepath)
    finally:
        for o in hidden:
            o.hide_render = False
        (r.engine, r.resolution_x, r.resolution_y, r.resolution_percentage, r.filepath, sc.camera,
         d.light, d.color_type, d.show_cavity, r.image_settings.file_format) = keep
        data = cam.data
        bpy.data.objects.remove(cam)
        bpy.data.cameras.remove(data)
    return files
