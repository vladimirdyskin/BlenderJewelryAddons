from __future__ import annotations

import importlib
import sys

import bpy


SUITE_MODULE = "bl_ext.user_default.jewelry_suite"
SUITE_SUBMODULES = (
    "gems",
    "face_tools",
    "gn_instance_face",
    "hires_snapshot",
    "link_gems",
    "gn_subdivide_x",
    "design_report_png",
    "pave_layout",
    "pave_live",
    "surface_pave",
    "ui_panel",
    "pretty_ruler",
)
LEGACY_MODULES = (
    "bl_ext.user_default.parametric_gems",
    "bl_ext.user_default.jewel_tools",
    "bl_ext.user_default.pretty_ruler_overlay",
    "pretty_ruler_overlay",
)


def disable_addon(module_name: str) -> None:
    if module_name in bpy.context.preferences.addons:
        bpy.ops.preferences.addon_disable(module=module_name)


def cleanup_partial_surface_pave() -> None:
    module = sys.modules.get(f"{SUITE_MODULE}.surface_pave")
    if module is None:
        return
    live = getattr(module, "pave_live", None)
    if live is not None:
        try:
            live.unregister()
        except Exception:
            pass
    if hasattr(bpy.types.Scene, "jewel_pave_surface"):
        del bpy.types.Scene.jewel_pave_surface
    if hasattr(bpy.types.Object, "jewel_pave"):
        del bpy.types.Object.jewel_pave
    for cls in reversed(getattr(module, "_CLASSES", ())):
        if getattr(bpy.types, cls.__name__, None) is cls:
            bpy.utils.unregister_class(cls)


enabled_legacy = [
    module_name
    for module_name in LEGACY_MODULES
    if module_name in bpy.context.preferences.addons
]
suite_was_enabled = SUITE_MODULE in bpy.context.preferences.addons

for module_name in enabled_legacy:
    disable_addon(module_name)

bpy.ops.preferences.addon_refresh()
if SUITE_MODULE in sys.modules:
    module = sys.modules[SUITE_MODULE]
    if suite_was_enabled:
        bpy.ops.preferences.addon_disable(module=SUITE_MODULE)
    else:
        cleanup_partial_surface_pave()
    for suffix in SUITE_SUBMODULES:
        submodule = sys.modules.get(f"{SUITE_MODULE}.{suffix}")
        if submodule is not None:
            importlib.reload(submodule)
    importlib.reload(module)

sys.modules.pop(f"{SUITE_MODULE}.subdivide_axis", None)

try:
    enable_result = bpy.ops.preferences.addon_enable(module=SUITE_MODULE)
    if "FINISHED" not in enable_result:
        raise RuntimeError(f"Unable to enable {SUITE_MODULE}: {enable_result}")
except Exception:
    cleanup_partial_surface_pave()
    for module_name in enabled_legacy:
        bpy.ops.preferences.addon_enable(module=module_name)
    bpy.ops.wm.save_userpref()
    raise

bpy.ops.wm.save_userpref()

result = {
    "blend": bpy.data.filepath,
    "enabled": SUITE_MODULE in bpy.context.preferences.addons,
    "legacy_enabled": [
        module_name
        for module_name in LEGACY_MODULES
        if module_name in bpy.context.preferences.addons
    ],
    "properties": {
        "parametric_gem": hasattr(bpy.types.Object, "parametric_gem"),
        "jewel_snap": hasattr(bpy.types.Scene, "jewel_snap"),
        "jewel_pave": hasattr(bpy.types.Object, "jewel_pave"),
        "pretty_ruler": hasattr(bpy.types.Scene, "pretty_ruler"),
    },
    "panels": {
        "parametric_gems": hasattr(bpy.types, "VIEW3D_PT_parametric_gems"),
        "jewel_tools": hasattr(bpy.types, "VIEW3D_PT_jewel_tools"),
        "surface_pave": hasattr(bpy.types, "VIEW3D_PT_surface_pave"),
        "pretty_ruler": hasattr(bpy.types, "VIEW3D_PT_pretty_ruler"),
    },
}
