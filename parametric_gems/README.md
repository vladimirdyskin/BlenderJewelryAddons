# Parametric Gems

Blender 5.2 extension for creating editable gemstone meshes.

## Cuts

- Round, Oval, Cushion, Pear, Marquise, Princess, Baguette, Square, Emerald,
  Asscher, Radiant, Flanders, Octagon, Heart, Trillion, Trilliant, and Triangle.
- Standard facet topology based on the JewelCraft 3.0.0 templates.
- Editable length, width, and total depth in millimeters.
- Editable girdle, crown, and pavilion heights as percentages of gem width.
- Editing total depth preserves girdle and crown heights and recalculates pavilion depth.
- JewelCraft-compatible `gem` object metadata.
- Optional live propagation to selected parametric gems.

## Linked cast templates

- Registers a custom cast mesh relative to a standard parametric gem.
- Creates true linked mesh instances for selected gems of the same cut.
- Scales each instance proportionally in X, Y, and Z from gem width, length,
  and total depth.
- Preserves the template's relative position and orientation around the gem.
- Rebuilds instance transforms automatically when the source gem changes.

## Ring size curve

- Shows diameter and mathematical circumference for the active curve object.
- Editing either value resizes all curve control points uniformly in world scale.
- Preserves object location, rotation, scale, and Geometry Nodes modifiers.
- Supports Bezier, NURBS, and poly curve control points.

## Usage

1. Open the `Jewelry` tab in the 3D View sidebar.
2. Click `Add Parametric Gem` and choose a cut.
3. Edit parameters in the sidebar or Object Properties.
4. Enable `Affect Selected` to propagate each edited value to selected parametric gems.
5. Use `Default` to restore the selected cut's standard aspect ratio and height proportions.
6. Fit a custom cast mesh around a standard parametric gem.
7. Keep the standard gem active, select the cast mesh as well, and click
   `Register Selected Mesh as Cast Template`.
8. Select target gems of the same cut and click `Place Cast Instances on Selected Gems`.
9. Use the Bake buttons when parametric editing is no longer needed.
10. Select a circular curve and edit `Diameter` or `Circumference` in the same
    `Jewelry` sidebar panel to control ring size.

## Development install

The extension source stays in this directory. Blender loads it through a symbolic link in the `user_default` extension repository.

## Asset notice

`assets/gems.blend` is copied from JewelCraft 3.0.0 by Mikhail Rachinskiy and is used under GPL-3.0-or-later.
