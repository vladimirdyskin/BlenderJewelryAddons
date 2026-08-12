from __future__ import annotations

import addon_utils
import bpy


MODULE_NAME = "bl_ext.user_default.parametric_gems"

default_enabled, loaded = addon_utils.check(MODULE_NAME)
if not loaded:
    module = addon_utils.enable(MODULE_NAME, default_set=True, persistent=True)
    if module is None:
        raise RuntimeError(f"Could not enable extension: {MODULE_NAME}")

bpy.ops.wm.save_userpref()

result = {
    "module": MODULE_NAME,
    "default_enabled_before": default_enabled,
    "loaded_before": loaded,
    "enabled_now": MODULE_NAME in bpy.context.preferences.addons,
    "registered_now": hasattr(bpy.types.Object, "parametric_gem"),
}
