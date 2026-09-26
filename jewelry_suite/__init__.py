# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from . import face_tools, gems, gn_instance_face, gn_subdivide_x, hires_snapshot, link_gems, pretty_ruler, surface_pave, ui_panel


_MODULES = (
    gems,
    face_tools,
    gn_instance_face,
    gn_subdivide_x,
    hires_snapshot,
    link_gems,
    surface_pave,
    ui_panel,
    pretty_ruler,
)

_registered_modules: list[object] = []


def register() -> None:
    if _registered_modules:
        return

    try:
        for module in _MODULES:
            module.register()
            _registered_modules.append(module)
    except Exception:
        for module in reversed(_registered_modules):
            try:
                module.unregister()
            except Exception:
                pass
        _registered_modules.clear()
        raise


def unregister() -> None:
    modules = tuple(_registered_modules) or _MODULES
    first_error: Exception | None = None

    for module in reversed(modules):
        try:
            module.unregister()
        except Exception as exc:
            if first_error is None:
                first_error = exc

    _registered_modules.clear()
    if first_error is not None:
        raise first_error


if __name__ == "__main__":
    register()
