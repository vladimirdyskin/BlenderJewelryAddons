# SPDX-License-Identifier: GPL-3.0-or-later

"""Fixed candidate positions with deferred mask-only preview updates."""

from array import array
from hashlib import blake2b
import json
from time import perf_counter

import bpy
from bpy.app.handlers import persistent

from .pave_layout import MASK_NAME, Surface


INTERVAL = 0.08
_dirty = False
_updating = False
_in_timer = False
_overlays = {}


def _source_key(context, source):
    if source is None:
        return "bundled-round"
    evaluated = source.evaluated_get(context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        digest = blake2b(digest_size=16)
        coords = array('f', [0.0]) * (len(mesh.vertices) * 3)
        mesh.vertices.foreach_get('co', coords)
        digest.update(coords.tobytes())
        digest.update(str([(tuple(p.vertices), p.material_index) for p in mesh.polygons]).encode())
        digest.update(str([m.name_full if m else None for m in mesh.materials]).encode())
        digest.update(str(dict(source.get('gem', {}))).encode())
        return digest.hexdigest()
    finally:
        evaluated.to_mesh_clear()


def _settings_key(context, surface):
    settings = surface.jewel_pave
    values = [1, settings.diameter, settings.gap, settings.border, settings.offset,
              settings.angle, settings.max_stones, settings.use_cursor,
              tuple(context.scene.cursor.location) if settings.use_cursor else None,
              _source_key(context, settings.gem)]
    return json.dumps(values)


def is_live(surface):
    output = surface.jewel_pave.output
    return (output is not None and output.get('jewelry_pave_owner') == surface
            and output.get('pave_layout_mode') == 'LIVE')


def prepare(context, surface, *, force=False):
    from .surface_pave import rebuild

    context.view_layer.update()
    sampled = Surface(surface, context.evaluated_depsgraph_get(), surface.jewel_pave.threshold)
    key = _settings_key(context, surface)
    output = surface.jewel_pave.output
    if (force or not is_live(surface) or output.get('pave_settings_key') != key
            or output.get('pave_geometry_key') != sampled.geometry_key()
            or any(abs(output.matrix_world[i][j] - (1.0 if i == j else 0.0)) > 1e-5
                   for i in range(4) for j in range(4))):
        output = rebuild(context, surface, full_surface=True)
        output['pave_settings_key'] = key
    refresh(context, surface, sampled=sampled)
    output.hide_set(False)
    return output


def refresh(context, surface, *, sampled=None):
    """Change selection only; point order, positions, rotations and IDs stay fixed."""
    global _updating, _dirty
    if not is_live(surface):
        raise ValueError("Press Paint to prepare a live layout")
    _updating = True
    try:
        context.view_layer.update()
        settings = surface.jewel_pave
        output = settings.output
        if output.get('pave_settings_key') != _settings_key(context, surface):
            raise ValueError("Settings changed; press Paint again")
        if sampled is None:
            sampled = Surface(surface, context.evaluated_depsgraph_get(), settings.threshold)
        if sampled.geometry_key() != output.get('pave_geometry_key'):
            raise ValueError("Surface changed; press Paint again")
        points = output.data.attributes.get('pave_surface_point')
        selection = output.data.attributes.get('pave_visible')
        if points is None or selection is None:
            raise ValueError("Live layout changed; press Paint again")
        clearance = settings.diameter * 0.5 + settings.border
        values = [sampled.fits(sampled.sample(point.vector), clearance) for point in points.data]
        previous = [False] * len(values)
        selection.data.foreach_get('value', previous)
        if previous != values:
            selection.data.foreach_set('value', values)
            output.data.update()
            output.update_tag(refresh={'DATA'})
        count = sum(values)
        if output.get('stone_count') != count:
            output['stone_count'] = count
        if output.get('pave_live_error'):
            output['pave_live_error'] = ""
        context.view_layer.update()
        _dirty = False
        return count
    finally:
        _updating = False


def _view_spaces(context):
    for window in context.window_manager.windows:
        if window.scene != context.scene:
            continue
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                yield area.spaces.active


def update_overlay(settings, context):
    surface = settings.id_data
    if surface.mode != 'WEIGHT_PAINT' or not settings.paint_state or not settings.live_preview:
        return
    saved = json.loads(settings.paint_state)
    for space in _view_spaces(context):
        key = space.as_pointer()
        if key not in _overlays:
            original = saved.get('overlay_opacity', space.overlay.weight_paint_mode_opacity)
            _overlays[key] = (space, original)
        space.overlay.weight_paint_mode_opacity = (max(_overlays[key][1], 0.5)
                                                   if settings.show_mask else 0.0)


def _restore_overlays():
    for space, opacity in _overlays.values():
        try:
            space.overlay.weight_paint_mode_opacity = opacity
        except ReferenceError:
            pass
    _overlays.clear()


def _active_surface(context):
    scene = getattr(context, "scene", None)
    if scene is None:
        return None
    surface = scene.jewel_pave_surface
    if (surface is None or surface != context.active_object or surface.mode != 'WEIGHT_PAINT'
            or not surface.jewel_pave.live_preview or not surface.jewel_pave.paint_state):
        return None
    group = surface.vertex_groups.active
    return surface if group and group.name == MASK_NAME else None


def _ensure_timer():
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=INTERVAL)


def start(context, surface):
    global _dirty
    state = json.loads(surface.jewel_pave.paint_state)
    if 'overlay_opacity' not in state:
        space = next(_view_spaces(context), None)
        state['overlay_opacity'] = space.overlay.weight_paint_mode_opacity if space else 1.0
        surface.jewel_pave.paint_state = json.dumps(state)
    update_overlay(surface.jewel_pave, context)
    output = surface.jewel_pave.output
    for space in _view_spaces(context):
        if space.local_view and surface.local_view_get(space):
            output.local_view_set(space, True)
    _dirty = True
    _ensure_timer()


def finish(context, surface):
    if surface.jewel_pave.live_preview and is_live(surface):
        try:
            refresh(context, surface)
        except (ValueError, RuntimeError) as error:
            surface.jewel_pave.output['pave_live_error'] = str(error)
    stop()


def stop():
    global _dirty
    if not _in_timer and bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    _dirty = False
    _restore_overlays()


def _tick():
    global _in_timer
    _in_timer = True
    started = perf_counter()
    try:
        context = bpy.context
        if getattr(context, "scene", None) is None:
            _restore_overlays()
            return INTERVAL
        surface = _active_surface(context)
        if surface is None:
            from .surface_pave import _restore_paint
            target = context.scene.jewel_pave_surface
            if target is not None and target.jewel_pave.paint_state:
                _restore_paint(context, target)
            _restore_overlays()
            return None
        if bpy.app.is_job_running('RENDER'):
            return INTERVAL
        update_overlay(surface.jewel_pave, context)
        if _dirty:
            refresh(context, surface)
            for window in context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'VIEW_3D':
                        area.tag_redraw()
        return max(INTERVAL, (perf_counter() - started) * 2.0)
    except (ValueError, RuntimeError, ReferenceError) as error:
        if 'surface' in locals() and surface is not None:
            try:
                if surface.jewel_pave.output is not None:
                    surface.jewel_pave.output['pave_live_error'] = str(error)
            except ReferenceError:
                pass
        return None
    finally:
        _in_timer = False


@persistent
def _on_update(scene, depsgraph):
    global _dirty
    if _updating:
        return
    surface = scene.jewel_pave_surface
    if surface is None or not surface.jewel_pave.paint_state or not surface.jewel_pave.live_preview:
        return
    if any(update.id.original in (surface, surface.data) for update in depsgraph.updates):
        _dirty = True


@persistent
def _on_history(_unused):
    global _dirty
    _dirty = True
    if _active_surface(bpy.context) is not None:
        _ensure_timer()
    else:
        stop()


@persistent
def _on_load_pre(_unused):
    stop()


@persistent
def _on_save(_unused):
    surface = _active_surface(bpy.context)
    if surface is not None:
        try:
            refresh(bpy.context, surface)
        except (ValueError, RuntimeError) as error:
            if surface.jewel_pave.output is not None:
                surface.jewel_pave.output['pave_live_error'] = str(error)


_HANDLERS = ((bpy.app.handlers.depsgraph_update_post, _on_update),
             (bpy.app.handlers.undo_post, _on_history),
             (bpy.app.handlers.redo_post, _on_history),
             (bpy.app.handlers.load_pre, _on_load_pre),
             (bpy.app.handlers.load_post, _on_history),
             (bpy.app.handlers.save_pre, _on_save),
             (bpy.app.handlers.render_init, _on_save))


def register():
    global _dirty
    for handlers, function in _HANDLERS:
        if function not in handlers:
            handlers.append(function)
    _dirty = True
    _ensure_timer()


def unregister():
    stop()
    for handlers, function in _HANDLERS:
        if function in handlers:
            handlers.remove(function)
