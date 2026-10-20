# SPDX-License-Identifier: GPL-3.0-or-later
"""Pretty Ruler Publish: GLB + dimensions.json + manifest.json into a static web folder.

Depends on Pretty Ruler (`Scene.pretty_ruler`, registered earlier in the suite); owns
`Scene.pretty_ruler_publish`. The viewer files are copied from `ruler_viewer/` next to
this module into the project folder.
"""

import datetime
import hashlib
import html
import json
import math
import os
import random
import re
import shutil
import string
import sys

import bpy
from bpy.app.handlers import persistent
from mathutils import Vector

DEFAULT_HOST = "https://mac-mini-2.tail06351a.ts.net"
DEFAULT_ROOT = "~/Sites/pretty-web"
VIEWER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ruler_viewer")
SENSOR_WIDTH = 36.0  # Blender viewport sensor width used for ortho scale / fov
_VERSION_RE = re.compile(r"<!--\s*pretty-ruler-viewer\s+v(\d+)\s*-->")

_publishing = False


# ---------------------------------------------------------------------------
# Ruler data -> dimensions list of the dimensions.json contract
# ---------------------------------------------------------------------------

def ruler_module(scene):
    """The module that registered `Scene.pretty_ruler`, wherever it lives."""
    return sys.modules[type(scene.pretty_ruler).__module__]


def to_gltf(v):
    """Blender Z-up (x, y, z) -> glTF Y-up (x, z, -y)."""
    return [v.x, v.z, -v.y]


def _object_visible(obj):
    if obj is None:
        return False
    try:
        if bpy.app.background:
            return not obj.hide_get()
        return obj.visible_get()
    except Exception:
        return True


def collect_dimensions(scene):
    """Native rulers (ids `r-<sha1 of stroke key>`) plus linked dimensions (ids `l-<index>`).

    Labels reproduce what the viewport draws: distance `<value><unit_suffix>`,
    angle `<value>°` (the "∠ " prefix exists only in the suite's list names).
    """
    props = scene.pretty_ruler
    rp = ruler_module(scene)
    fmt = "{:." + str(props.decimals) + "f}"
    hidden = {it.key for it in props.items if not it.enabled}
    out = []

    for pts in rp.get_ruler_strokes():
        key = rp._stroke_key(pts)
        if len(pts) == 2:
            value = (pts[1] - pts[0]).length
            kind = "distance"
            label = fmt.format(value) + props.unit_suffix
        elif len(pts) == 3:
            v1 = pts[0] - pts[1]
            v2 = pts[2] - pts[1]
            if v1.length == 0 or v2.length == 0:
                continue
            value = math.degrees(v1.angle(v2))
            kind = "angle"
            label = fmt.format(value) + "°"
        else:
            continue
        out.append({
            "id": "r-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:8],
            "type": kind,
            "points": [to_gltf(p) for p in pts],
            "value": value,
            "label": label,
            "enabled": key not in hidden,
        })

    cache = {}
    for i, link in enumerate(props.links):
        pts = rp.link_points(link, cache)
        if pts is None:
            continue
        value = (pts[1] - pts[0]).length
        out.append({
            "id": "l-%d" % i,
            "type": "distance",
            "linked": True,
            "kind": link.kind,
            "points": [to_gltf(p) for p in pts],
            "value": value,
            "label": fmt.format(value) + props.unit_suffix,
            "enabled": bool(link.enabled and _object_visible(link.obj_a) and _object_visible(link.obj_b)),
        })
    return out


# ---------------------------------------------------------------------------
# Properties / preferences
# ---------------------------------------------------------------------------

class PrettyRulerPublishProps(bpy.types.PropertyGroup):
    publish_on_save: bpy.props.BoolProperty(name="Publish on Save", default=False)
    project_slug: bpy.props.StringProperty(name="Slug")
    publish_status: bpy.props.StringProperty()
    publish_error: bpy.props.StringProperty()


class PrettyRulerPublishPreferences(bpy.types.AddonPreferences):
    # inside the suite __package__ is the extension id, so this is the suite's preferences entry
    bl_idname = __package__

    host: bpy.props.StringProperty(name="Host", default=DEFAULT_HOST)
    # one web root per machine: the folder the static server publishes
    publish_root: bpy.props.StringProperty(name="Web Root", subtype='DIR_PATH', default=DEFAULT_ROOT)

    def draw(self, context):
        self.layout.prop(self, "host")
        self.layout.prop(self, "publish_root")


def _prefs():
    addon = bpy.context.preferences.addons.get(__package__)
    return addon.preferences if addon else None


def get_host():
    prefs = _prefs()
    host = prefs.host if prefs else DEFAULT_HOST
    return host.rstrip("/")


def get_publish_root():
    prefs = _prefs()
    root = prefs.publish_root if prefs and prefs.publish_root else DEFAULT_ROOT
    return os.path.expanduser(root)


def ensure_slug(props):
    if not props.project_slug:
        base = os.path.splitext(os.path.basename(bpy.data.filepath))[0] or "untitled"
        base = re.sub(r"[^a-z0-9]", "-", base.lower())
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
        props.project_slug = base + "-" + suffix
    return props.project_slug


# ---------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------

def _write_atomic(path, data):
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def _sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _viewer_version(index_path):
    try:
        with open(index_path, encoding="utf-8") as f:
            m = _VERSION_RE.search(f.readline())
    except OSError:
        return None
    return int(m.group(1)) if m else None


def _sync_viewer(project_dir):
    """Copy viewer scripts into the project folder when missing or outdated. Returns viewer version.

    index.html is not copied here: `_write_index` regenerates it from the template on every publish.
    """
    dst_index = os.path.join(project_dir, "index.html")
    src_index = os.path.join(VIEWER_DIR, "index.html")
    if not os.path.isfile(src_index):
        print("Pretty Ruler Publish: viewer folder missing (%s), skipping viewer copy" % VIEWER_DIR)
        return _viewer_version(dst_index)
    names = [n for n in os.listdir(VIEWER_DIR)
             if n != "index.html" and os.path.isfile(os.path.join(VIEWER_DIR, n))]
    src_ver = _viewer_version(src_index) or 0
    dst_ver = _viewer_version(dst_index)
    outdated = dst_ver is None or src_ver > dst_ver
    missing = any(not os.path.isfile(os.path.join(project_dir, n)) for n in names)
    if outdated or missing:
        for n in names:
            dst = os.path.join(project_dir, n)
            shutil.copyfile(os.path.join(VIEWER_DIR, n), dst + ".tmp")
            os.replace(dst + ".tmp", dst)
    return _viewer_version(src_index)


def _write_index(project_dir, values):
    """index.html from the viewer template with the `__PR_*__` placeholders (Open Graph) filled.

    Without an image URL the og:image / twitter:image lines are dropped.
    """
    src_index = os.path.join(VIEWER_DIR, "index.html")
    if not os.path.isfile(src_index):
        return
    with open(src_index, encoding="utf-8") as f:
        text = f.read()
    if not values["__PR_IMAGE__"]:
        text = re.sub(r"^.*(?:og:image|twitter:image).*\n", "", text, flags=re.M)
    for key, val in values.items():
        text = text.replace(key, html.escape(val, quote=True))
    _write_atomic(os.path.join(project_dir, "index.html"), text.encode("utf-8"))


def _export_glb(path):
    # the exporter appends ".glb" when missing, so the temp name keeps the extension
    tmp = os.path.join(os.path.dirname(path), "scene.tmp.glb")
    result = bpy.ops.export_scene.gltf(
        filepath=tmp,
        export_format='GLB',
        export_apply=True,
        use_visible=True,
        export_yup=True,
        export_cameras=False,
        export_lights=False,
        export_animations=False,
        export_image_format='WEBP',
        export_gn_mesh=True,  # Geometry Nodes instances (chains, pave stones)
    )
    if 'FINISHED' not in result or not os.path.isfile(tmp):
        raise RuntimeError("glTF export failed: %s" % result)
    os.replace(tmp, path)


def _find_view3d():
    """(window, area, region, space) of the first 3D viewport, or None."""
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type != 'VIEW_3D':
                continue
            for space in area.spaces:
                if space.type == 'VIEW_3D' and space.region_3d is not None:
                    region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                    if region is not None:
                        return win, area, region, space
    return None


def _frame_rulers(scene, space, rv3d):
    """Aim the view at the bounding sphere of the ruler points (that is where the piece is).
    Returns False when there are no rulers. Viewport extent along the larger side is
    2 * dist * 36 / lens; dist = r * lens / 12 leaves air around the piece (ruler points
    usually sit inside the model, so the sphere underestimates it)."""
    pts = [p for pts in ruler_module(scene).get_ruler_strokes() for p in pts]
    if not pts:
        return False
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    radius = max((hi - lo).length * 0.5, 1.0)
    rv3d.view_location = (lo + hi) * 0.5
    rv3d.view_distance = radius * space.lens / 12.0
    return True


def _render_preview(scene, path):
    """OpenGL render of the 3D viewport into a 1200x630 JPEG (GUI only). Returns its sha1 or None.

    The POST_PIXEL ruler overlay is not part of offscreen viewport renders, so the preview
    shows the model only. Never raises: a failed preview just means no og:image.
    """
    if bpy.app.background:
        return None
    found = _find_view3d()
    if found is None:
        return None
    win, area, region, space = found
    rv3d = space.region_3d
    r = scene.render
    ims = r.image_settings
    saved = (r.resolution_x, r.resolution_y, r.resolution_percentage,
             ims.file_format, ims.quality, ims.color_mode)
    # the thumbnail is for clients: no grid/axes/cursor, model framed; the user's view is restored
    saved_view = (rv3d.view_location.copy(), rv3d.view_rotation.copy(), rv3d.view_distance,
                  space.overlay.show_overlays)
    tmp = os.path.join(os.path.dirname(path), "preview.tmp.jpg")
    try:
        r.resolution_x, r.resolution_y, r.resolution_percentage = 1200, 630, 100
        ims.file_format, ims.quality, ims.color_mode = 'JPEG', 85, 'RGB'
        space.overlay.show_overlays = False
        # exec path from Python: no render window is opened (checked in Blender 5.2)
        with bpy.context.temp_override(window=win, area=area, region=region):
            if not _frame_rulers(scene, space, rv3d):
                bpy.ops.view3d.view_all(center=False)
            result = bpy.ops.render.opengl(view_context=True, write_still=False)
        if 'FINISHED' not in result:
            raise RuntimeError("render.opengl: %s" % result)
        bpy.data.images["Render Result"].save_render(filepath=tmp, scene=scene)
        os.replace(tmp, path)
    except Exception as e:
        print("Pretty Ruler Publish: preview skipped - %s: %s" % (type(e).__name__, e))
        return None
    finally:
        # file_format first: color_mode choices depend on it
        r.resolution_x, r.resolution_y, r.resolution_percentage = saved[:3]
        ims.file_format, ims.quality, ims.color_mode = saved[3:]
        rv3d.view_location, rv3d.view_rotation, rv3d.view_distance = saved_view[:3]
        space.overlay.show_overlays = saved_view[3]
    return _sha1(path)


def _collect_view():
    if bpy.app.background:
        return None
    found = _find_view3d()
    if found is None:
        return None
    space = found[3]
    rv3d = space.region_3d
    lens = space.lens
    position = rv3d.view_matrix.inverted().translation
    up = rv3d.view_rotation @ Vector((0.0, 1.0, 0.0))
    return {
        "position": to_gltf(position),
        "target": to_gltf(rv3d.view_location),
        "up": to_gltf(up),
        "perspective": rv3d.is_perspective,
        # viewport uses CAMERA_PARAM_ZOOM_INIT_PERSP = 2: visible extent along the larger
        # side is 2 * dist * sensor / lens (measured with location_3d_to_region_2d)
        "orthoScale": 2.0 * rv3d.view_distance * SENSOR_WIDTH / lens,
        "viewDistance": rv3d.view_distance,
        "fovDeg": math.degrees(2.0 * math.atan(SENSOR_WIDTH / lens)),
        "lens": lens,
    }


def _collect_style(rp):
    return {
        "endcap": rp.endcap_style,
        "tickLength": rp.tick_length,
        "arrowSize": rp.arrow_size,
        "lineWidth": rp.line_width,
        "fontSize": rp.font_size,
        "decimals": rp.decimals,
        "unitSuffix": rp.unit_suffix,
        "smallLeaderLength": rp.small_leader_length,
        "textGap": rp.text_gap,
        "extensionLines": rp.extension_lines,
        "extOffset": rp.ext_offset,
        "extGap": rp.ext_gap,
        "extAutoSide": rp.ext_auto_side,
        "arcRadius": rp.arc_radius,
        "lineColor": [*rp.line_color, 1.0],
        "textColor": [*rp.text_color, 1.0],
        "linkColor": [*rp.link_color, 1.0],
        "bgColor": [*rp.bg_color, rp.bg_alpha],
        "textBg": rp.text_bg,
    }


def _fmt_size(n):
    if n >= 1 << 20:
        return "%.1f MB" % (n / (1 << 20))
    return "%.0f KB" % (n / 1024)


def publish(scene, context=None):
    """Write scene.glb, dimensions.json and manifest.json. Returns the project folder path."""
    if getattr(scene, "pretty_ruler", None) is None:
        raise RuntimeError("Pretty Ruler (Jewelry Suite) is not loaded")
    props = scene.pretty_ruler_publish
    slug = ensure_slug(props)
    project_dir = os.path.join(get_publish_root(), slug)
    os.makedirs(project_dir, exist_ok=True)

    viewer_version = _sync_viewer(project_dir)

    glb_path = os.path.join(project_dir, "scene.glb")
    _export_glb(glb_path)
    preview_hash = _render_preview(scene, os.path.join(project_dir, "preview.jpg"))

    now = datetime.datetime.now().astimezone()
    saved_at = now.isoformat(timespec="seconds")
    dims = collect_dimensions(scene)
    dims_doc = {
        "version": 1,
        "savedAt": saved_at,
        "units": "mm",
        "coordinateSpace": "gltf-y-up",
        "view": _collect_view(),
        "style": _collect_style(scene.pretty_ruler),
        "dimensions": dims,
    }
    dims_path = os.path.join(project_dir, "dimensions.json")
    _write_atomic(dims_path, json.dumps(dims_doc, ensure_ascii=False, indent=1).encode("utf-8"))

    manifest = {
        "version": 1,
        "savedAt": saved_at,
        "blendName": os.path.basename(bpy.data.filepath) or "untitled",
        "units": "mm",
        "sceneHash": _sha1(glb_path),
        "dimensionsHash": _sha1(dims_path),
        "viewerVersion": viewer_version,
        "previewHash": preview_hash,
    }
    _write_atomic(os.path.join(project_dir, "manifest.json"),
                  json.dumps(manifest, indent=1).encode("utf-8"))

    # link previews (Open Graph): WhatsApp caches per image URL, hence the ?v= cache buster
    blend_name = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
    host = get_host()
    url = "%s/%s/" % (host, slug) if host else ""
    _write_index(project_dir, {
        "__PR_TITLE__": re.sub(r"[_-]+", " ", blend_name) if blend_name else "Untitled",
        "__PR_DESCRIPTION__": "3D preview with dimensions · %d dimensions · updated %s" % (
            len(dims), now.strftime("%Y-%m-%d %H:%M")),
        "__PR_URL__": url,
        "__PR_IMAGE__": "%spreview.jpg?v=%s" % (url, preview_hash[:10]) if url and preview_hash else "",
    })

    props.publish_status = "%s · %s · %d dims" % (
        now.strftime("%H:%M:%S"), _fmt_size(os.path.getsize(glb_path)), len(dims))
    props.publish_error = ""
    return project_dir


def run_publish(scene):
    """publish() with reentrancy guard and error capture into props. Returns error string or ''."""
    global _publishing
    if _publishing:
        return ""
    _publishing = True
    try:
        publish(scene)
        return ""
    except Exception as e:
        msg = "%s: %s" % (type(e).__name__, e)
        scene.pretty_ruler_publish.publish_error = msg
        print("Pretty Ruler Publish: failed - " + msg)
        return msg
    finally:
        _publishing = False


@persistent
def on_save_post(dummy):
    try:
        scene = bpy.context.scene
        props = getattr(scene, "pretty_ruler_publish", None)
        if props is None or not props.publish_on_save or getattr(scene, "pretty_ruler", None) is None:
            return
        run_publish(scene)
    except Exception as e:
        print("Pretty Ruler Publish: save_post handler error - %s" % e)


# ---------------------------------------------------------------------------
# Operators / UI
# ---------------------------------------------------------------------------

class PRETTYRULER_OT_publish(bpy.types.Operator):
    bl_idname = "pretty_ruler.publish"
    bl_label = "Publish Now"
    bl_description = "Export GLB, dimensions and manifest to the web folder"

    def execute(self, context):
        err = run_publish(context.scene)
        if err:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}
        self.report({'INFO'}, "Published: " + context.scene.pretty_ruler_publish.publish_status)
        return {'FINISHED'}


class PRETTYRULER_OT_copy_link(bpy.types.Operator):
    bl_idname = "pretty_ruler.copy_link"
    bl_label = "Copy Link"
    bl_description = "Copy the viewer URL to the clipboard"

    def execute(self, context):
        slug = ensure_slug(context.scene.pretty_ruler_publish)
        link = "%s/%s/" % (get_host(), slug)
        context.window_manager.clipboard = link
        self.report({'INFO'}, link)
        return {'FINISHED'}


class VIEW3D_PT_pretty_ruler_publish(bpy.types.Panel):
    """Sub-panel of the Pretty Ruler panel."""
    bl_label = "Publish"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Jewelry"
    bl_parent_id = "VIEW3D_PT_pretty_ruler"

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, "pretty_ruler")

    def draw(self, context):
        layout = self.layout
        p = context.scene.pretty_ruler_publish
        layout.prop(p, "publish_on_save")
        layout.label(text="Slug: " + (p.project_slug or "(generated on first publish)"))
        row = layout.row(align=True)
        row.operator("pretty_ruler.publish", icon='EXPORT')
        row.operator("pretty_ruler.copy_link", icon='COPYDOWN')
        if p.publish_status:
            layout.label(text=p.publish_status)
        if p.publish_error:
            layout.label(text=p.publish_error, icon='ERROR')


_CLASSES = (
    PrettyRulerPublishProps,
    PrettyRulerPublishPreferences,
    PRETTYRULER_OT_publish,
    PRETTYRULER_OT_copy_link,
    VIEW3D_PT_pretty_ruler_publish,
)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.pretty_ruler_publish = bpy.props.PointerProperty(type=PrettyRulerPublishProps)
    if on_save_post not in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.append(on_save_post)


def unregister():
    if on_save_post in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.remove(on_save_post)
    if hasattr(bpy.types.Scene, "pretty_ruler_publish"):
        del bpy.types.Scene.pretty_ruler_publish
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
