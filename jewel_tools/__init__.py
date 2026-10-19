# Jewel Tools Blender extension.
# Extension metadata is defined in blender_manifest.toml.

from . import curve_symmetry, face_tools, gn_instance_face, gn_subdivide_x, hires_snapshot, link_gems, metal_union, surface_pave, ui_panel

_modules = (face_tools, gn_instance_face, gn_subdivide_x, curve_symmetry, hires_snapshot, link_gems, metal_union, surface_pave, ui_panel)


def register():
    for m in _modules:
        m.register()


def unregister():
    for m in reversed(_modules):
        m.unregister()
