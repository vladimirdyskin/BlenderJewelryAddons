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
import struct
import sys

import bpy
from mathutils import Vector

DEFAULT_HOST = "https://preview.dyskin.net"
DEFAULT_ROOT = "~/Sites/pretty-web"
# iPhone Safari kills the tab above ~1 GB of decoded geometry (seen with a 7M triangle scene)
DEFAULT_MAX_TRIANGLES = 1_000_000
DECIMATE_MIN_TRIANGLES = 10_000  # lighter objects are exported as they are
TEMP_DECIMATE = "PR_TEMP_DECIMATE"
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
    project_slug: bpy.props.StringProperty(name="Slug")
    publish_status: bpy.props.StringProperty()
    publish_error: bpy.props.StringProperty()


class PrettyRulerPublishPreferences(bpy.types.AddonPreferences):
    # inside the suite __package__ is the extension id, so this is the suite's preferences entry
    bl_idname = __package__

    host: bpy.props.StringProperty(name="Host", default=DEFAULT_HOST)
    # one web root per machine: the folder the static server publishes
    publish_root: bpy.props.StringProperty(name="Web Root", subtype='DIR_PATH', default=DEFAULT_ROOT)
    max_triangles: bpy.props.IntProperty(
        name="Max Triangles", default=DEFAULT_MAX_TRIANGLES, min=0, soft_max=5_000_000,
        description="Decimate heavy meshes on publish to stay under this total (0 = unlimited)")

    def draw(self, context):
        self.layout.prop(self, "host")
        self.layout.prop(self, "publish_root")
        self.layout.prop(self, "max_triangles")


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


def get_max_triangles():
    prefs = _prefs()
    return prefs.max_triangles if prefs else DEFAULT_MAX_TRIANGLES


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
    # copy whatever differs from the template, regardless of the version number
    for n in names:
        src = os.path.join(VIEWER_DIR, n)
        dst = os.path.join(project_dir, n)
        if os.path.isfile(dst) and _sha1(dst) == _sha1(src):
            continue
        shutil.copyfile(src, dst + ".tmp")
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


def _triangle_counts(scene):
    """[(obj, triangles)] of the visible mesh objects as the exporter sees them: evaluated
    (modifiers applied), without Geometry Nodes instances (those pass through Decimate anyway)."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    out = []
    for obj in scene.objects:
        if obj.type != 'MESH' or not obj.visible_get():  # what use_visible exports
            continue
        ev = obj.evaluated_get(depsgraph)
        me = ev.to_mesh()
        try:
            out.append((obj, len(me.loop_triangles)))
        finally:
            ev.to_mesh_clear()
    return out


def _decimate_for_budget(scene, budget):
    """Temporary Decimate modifiers on the heavy meshes so the export stays near `budget`
    triangles. Returns (touched objects, estimated exported triangles or None when untouched).
    FONT/CURVE objects take no Decimate and are rarely heavy, so only meshes are considered."""
    counts = _triangle_counts(scene)
    total = sum(n for _, n in counts)
    if budget <= 0 or total <= budget:
        return [], None
    ratio = budget / total
    touched = []
    estimate = total
    for obj, n in counts:
        if n <= DECIMATE_MIN_TRIANGLES or obj.mode == 'EDIT':
            continue
        try:
            mod = obj.modifiers.new(TEMP_DECIMATE, 'DECIMATE')
        except Exception:
            mod = None  # linked / overridden object
        if mod is None:
            continue
        mod.decimate_type = 'COLLAPSE'
        mod.ratio = ratio
        mod.use_collapse_triangulate = True
        touched.append(obj)
        estimate -= n - int(n * ratio)
    if not touched:
        return [], None
    print("Pretty Ruler Publish: decimated %d objects to %s of %s triangles (ratio %.2f)" % (
        len(touched), format(estimate, ","), format(total, ","), ratio))
    return touched, estimate


def _remove_temp_decimate(objs):
    for obj in objs:
        mod = obj.modifiers.get(TEMP_DECIMATE)
        if mod is not None:
            obj.modifiers.remove(mod)


FLAT_PROP = "pr_flat"


def _is_faceted(me):
    """Evaluated mesh reads as faceted: every face flat, or most edges sharp (Smooth by Angle on gems)."""
    if not len(me.polygons):
        return False
    faces = me.attributes.get("sharp_face")
    if faces is not None:
        flags = [False] * len(me.polygons)
        faces.data.foreach_get("value", flags)
        if all(flags):
            return True
    edges = me.attributes.get("sharp_edge")
    if edges is not None and len(me.edges):
        flags = [False] * len(me.edges)
        edges.data.foreach_get("value", flags)
        return sum(flags) * 2 >= len(flags)
    return False


def _faceted_mesh_names():
    """Names of the mesh datablocks whose evaluated geometry is faceted (incl. Geometry Nodes
    instance sources). glTF meshes keep the datablock name, so the GLB can be tagged by name."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    names = set()
    seen = set()
    for inst in depsgraph.object_instances:
        obj = inst.object
        if obj.type != 'MESH' or obj.original.data is None:
            continue
        name = obj.original.data.name
        if name in seen:
            continue
        seen.add(name)
        me = obj.to_mesh()
        try:
            if _is_faceted(me):
                names.add(name)
        finally:
            obj.to_mesh_clear()
    return names


def _tag_flat_meshes(glb_path, names):
    """Write `extras.pr_flat = 1` into the GLB's JSON chunk for meshes with those names; the viewer
    then rebuilds per-face normals for them. The exporter itself drops mesh extras for evaluated
    and instanced meshes, hence the post-processing."""
    if not names:
        return
    with open(glb_path, "rb") as f:
        data = f.read()
    json_len, = struct.unpack_from("<I", data, 12)
    gltf = json.loads(data[20:20 + json_len])
    for mesh in gltf.get("meshes", []):
        if mesh.get("name") in names:
            mesh.setdefault("extras", {})[FLAT_PROP] = 1
    body = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    body += b" " * (-len(body) % 4)
    rest = data[20 + json_len:]
    out = struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(body) + len(rest)) + struct.pack("<I4s", len(body), b"JSON") + body + rest
    _write_atomic(glb_path, out)


def _export_glb(scene, path):
    """Returns the estimated exported triangle count when decimation kicked in, else None."""
    # the exporter appends ".glb" when missing, so the temp name keeps the extension
    tmp = os.path.join(os.path.dirname(path), "scene.tmp.glb")
    touched, tris = _decimate_for_budget(scene, get_max_triangles())
    flat_names = _faceted_mesh_names()
    try:
        result = bpy.ops.export_scene.gltf(
            filepath=tmp,
            export_format='GLB',
            export_apply=True,
            use_visible=True,
            export_yup=True,
            export_cameras=False,
            export_lights=False,
            export_animations=False,
            export_texcoords=False,  # the viewer uses no textures
            # flat-shaded sculpts triple the vertex count when normals are exported (3 per triangle);
            # without them the exporter merges vertices and the viewer rebuilds creased normals
            export_normals=False,
            export_image_format='WEBP',
            export_gn_mesh=True,  # Geometry Nodes instances (chains, pave stones)
            # Draco: ~10x smaller files; Tailscale Funnel delivers only ~0.4 MB/s
            export_draco_mesh_compression_enable=True,
            export_draco_mesh_compression_level=6,
            export_draco_position_quantization=14,
            export_draco_normal_quantization=10,
        )
    finally:
        # the scene is never saved here, but the user's stack must come back as it was
        _remove_temp_decimate(touched)
    if 'FINISHED' not in result or not os.path.isfile(tmp):
        raise RuntimeError("glTF export failed: %s" % result)
    _tag_flat_meshes(tmp, flat_names)
    os.replace(tmp, path)
    return tris


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
    tris = _export_glb(scene, glb_path)
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
        "__PR_VIEWER__": str(viewer_version or 0),  # cache-busting query for viewer.js
        "__PR_IMAGE__": "%spreview.jpg?v=%s" % (url, preview_hash[:10]) if url and preview_hash else "",
    })

    props.publish_status = "%s · %s · %d dims" % (
        now.strftime("%H:%M:%S"), _fmt_size(os.path.getsize(glb_path)), len(dims))
    if tris is not None:
        props.publish_status += " · %.1fM tris" % (tris / 1e6)
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


def unregister():
    if hasattr(bpy.types.Scene, "pretty_ruler_publish"):
        del bpy.types.Scene.pretty_ruler_publish
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
