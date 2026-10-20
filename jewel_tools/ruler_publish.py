# SPDX-License-Identifier: GPL-3.0-or-later
"""Pretty Ruler Publish: GLB + dimensions.json + manifest.json into a static web folder.

Depends on Pretty Ruler (`Scene.pretty_ruler`, registered earlier in the suite); owns
`Scene.pretty_ruler_publish`. The viewer files are copied from `ruler_viewer/` next to
this module into the project folder.
"""

import datetime
import hashlib
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
    publish_root: bpy.props.StringProperty(name="Web Root", subtype='DIR_PATH', default="~/Sites/pretty-web")
    project_slug: bpy.props.StringProperty(name="Slug")
    publish_status: bpy.props.StringProperty()
    publish_error: bpy.props.StringProperty()


class PrettyRulerPublishPreferences(bpy.types.AddonPreferences):
    # inside the suite __package__ is the extension id, so this is the suite's preferences entry
    bl_idname = __package__

    host: bpy.props.StringProperty(name="Host", default=DEFAULT_HOST)

    def draw(self, context):
        self.layout.prop(self, "host")


def get_host():
    addon = bpy.context.preferences.addons.get(__package__)
    host = addon.preferences.host if addon else DEFAULT_HOST
    return host.rstrip("/")


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
    """Copy viewer files into the project folder when missing or outdated. Returns viewer version."""
    dst_index = os.path.join(project_dir, "index.html")
    src_index = os.path.join(VIEWER_DIR, "index.html")
    if not os.path.isfile(src_index):
        print("Pretty Ruler Publish: viewer folder missing (%s), skipping viewer copy" % VIEWER_DIR)
        return _viewer_version(dst_index)
    names = [n for n in os.listdir(VIEWER_DIR) if os.path.isfile(os.path.join(VIEWER_DIR, n))]
    src_ver = _viewer_version(src_index) or 0
    dst_ver = _viewer_version(dst_index)
    outdated = dst_ver is None or src_ver > dst_ver
    missing = any(not os.path.isfile(os.path.join(project_dir, n)) for n in names)
    if outdated or missing:
        for n in names:
            dst = os.path.join(project_dir, n)
            shutil.copyfile(os.path.join(VIEWER_DIR, n), dst + ".tmp")
            os.replace(dst + ".tmp", dst)
    return _viewer_version(dst_index)


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
    )
    if 'FINISHED' not in result or not os.path.isfile(tmp):
        raise RuntimeError("glTF export failed: %s" % result)
    os.replace(tmp, path)


def _find_view3d():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type != 'VIEW_3D':
                continue
            for space in area.spaces:
                if space.type == 'VIEW_3D' and space.region_3d is not None:
                    return space
    return None


def _collect_view():
    if bpy.app.background:
        return None
    space = _find_view3d()
    if space is None:
        return None
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
    project_dir = os.path.join(os.path.expanduser(bpy.path.abspath(props.publish_root)), slug)
    os.makedirs(project_dir, exist_ok=True)

    viewer_version = _sync_viewer(project_dir)

    glb_path = os.path.join(project_dir, "scene.glb")
    _export_glb(glb_path)

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
    }
    _write_atomic(os.path.join(project_dir, "manifest.json"),
                  json.dumps(manifest, indent=1).encode("utf-8"))

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
        layout.prop(p, "publish_root")
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
