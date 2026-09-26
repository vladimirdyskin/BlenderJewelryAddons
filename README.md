# Jewelry Suite

One Blender extension for parametric jewelry modeling and technical presentation.

## Included Modules

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

1. Download the `jewelry_suite` ZIP from the latest GitHub release.
2. In Blender, open **Edit > Preferences > Extensions**.
3. Open the menu in the top-right corner and choose **Install from Disk**.
4. Select the downloaded ZIP and enable the extension.

Do not unpack the ZIP before installation.

## Development

The repository contains one extension package composed from separate source modules:

- `jewelry_suite` - unified extension entry point
- `parametric_gems` - gemstone source module
- `jewel_tools` - modeling tools source modules
- `pretty_ruler_overlay` - drafting overlay source module

Build the archive with Python 3.11 or newer:

```sh
python tools/package_extensions.py
```

Use this repository builder instead of Blender's direct extension build command. The
development package uses symbolic links to keep module sources synchronized, and the
repository builder resolves those links into regular files inside the release ZIP.

## License

The extensions are distributed under GPL-3.0-or-later. See each extension manifest
and the notices included with bundled assets.
