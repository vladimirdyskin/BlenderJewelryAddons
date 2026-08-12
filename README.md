# Blender Jewelry Add-ons

Blender extensions for parametric jewelry modeling.

## Extensions

### Parametric Gems

Creates editable gemstone meshes with standard facet layouts, parametric dimensions,
JewelCraft metadata, linked cast templates, and ring diameter controls.

Requires Blender 5.2 or newer.

### Jewel Tools

Provides mesh face layout tools, Geometry Nodes helpers, and high-resolution viewport
snapshots.

Requires Blender 4.2 or newer.

### Pretty Ruler Overlay

Draws configurable distance and angle graphics over Blender's native Measure tool,
including arrows, extension lines, leader labels, and per-measurement visibility.

Requires Blender 5.1 or newer.

## Installation

1. Download the required ZIP from the latest GitHub release.
2. In Blender, open **Edit > Preferences > Extensions**.
3. Open the menu in the top-right corner and choose **Install from Disk**.
4. Select the downloaded ZIP and enable the extension.

Do not unpack the ZIP before installation.

## Development

The repository contains three independent Blender extensions:

- `parametric_gems`
- `jewel_tools`
- `pretty_ruler_overlay`

Build packages with Blender:

```sh
blender --command extension build --source-dir parametric_gems --output-dir dist
blender --command extension build --source-dir jewel_tools --output-dir dist
blender --command extension build --source-dir pretty_ruler_overlay --output-dir dist
```

Or build all three archives with Python 3.11 or newer:

```sh
python tools/package_extensions.py
```

## License

The extensions are distributed under GPL-3.0-or-later. See each extension manifest
and the notices included with bundled assets.
