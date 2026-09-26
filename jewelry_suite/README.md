# Jewelry Suite

A unified Blender extension for jewelry modeling and technical presentation.

Included modules:

- Parametric gemstones and linked cast templates
- Ring size curve controls
- Mesh face layout tools
- Non-destructive Geometry Nodes subdivision along local X for Curve modifiers
- Linked mesh optimization for identical gem objects
- Linked mesh optimization for repeated prong forms
- Geometry Nodes graph helpers
- High-resolution viewport snapshots
- Pretty Ruler Overlay

The extension targets Blender 5.2 or newer.

## Development

The `jewelry_suite` package links to the module sources in this repository. Install the
package directory as a symbolic link in Blender's `extensions/user_default` directory.
Changes to the source modules are available after reloading the extension. Build release
archives with `python tools/package_extensions.py` from the repository root so the links
are resolved into regular files.

## Installation

Install the packaged ZIP using Blender's **Preferences > Extensions > Install from Disk**.
