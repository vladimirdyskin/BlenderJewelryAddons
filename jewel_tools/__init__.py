# Jewel Tools Blender extension.
# Extension metadata is defined in blender_manifest.toml.

from . import face_tools, gn_instance_face, hires_snapshot, ui_panel

_modules = (face_tools, gn_instance_face, hires_snapshot, ui_panel)


def register():
    for m in _modules:
        m.register()


def unregister():
    for m in reversed(_modules):
        m.unregister()
