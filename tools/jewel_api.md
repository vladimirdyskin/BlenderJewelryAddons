# jewel — stone settings as short programs

A piece is a Python program of named parts. Each part is one object carrying a live Geometry Nodes stack
`My_Stone → My_Stone_Prongs → My_Stone_Cast → My_Setting_Bool`. Verbs add or update modifiers and set
their inputs; nothing is baked, everything stays editable with sliders. Re-running updates the scene.

## Verbs (each returns the object; `ob` = object or its name)

- `stone(name, cut="Round", width=2.0, length=None, material=None, at=(0, 0, 0), **inputs)` — create/reuse object `name` with My_Stone; `length=None`: Round → width, other cuts → standard proportion; `at` = location
- `prongs(ob, tip="Round", d=None, **inputs)` — My_Stone_Prongs; `tip` Round | Claw, `d` = prong diameter
- `cast(ob, type="Wall", **inputs)` — My_Stone_Cast; `type` Wall | Bezel | Basket
- `seat(ob, **inputs)` — My_Setting_Bool: seats the stone, unions the metal into one closed shell
- `points(ob, pts=None)` — prong places: `[(x, y), ...]` mm in object space (snapped to the girdle), `"default"` writes the default places for editing, `None` clears (nodes use defaults)
- `use_library(path)` — explicit .blend with the node groups (otherwise found in the asset libraries)

## Keywords (`**inputs`) → socket, default, meaning

Lengths mm, angles degrees, `%` in percent. Object/material/collection values: the datablock or its name.

| verb | keyword | socket | default | meaning |
|---|---|---|---|---|
| stone | `cut` | Cut | Round | Round, Emerald (also Oval, Pear, Cushion, Marquise, Princess, Baguette, Square, Asscher, Radiant, Flanders, Octagon, Heart, Trillion, Trilliant, Triangle) |
| | `width` / `length` | Width / Length | 2 / 3 | stone size X / Y |
| | `set` | Set | False | stone is set: claws lie on the crown, bezel lip closes over it |
| | `tilt` | Tilt | 3° | outward lean of prongs and cast |
| | `below_culet` | Below Culet | 0.4 | metal reaches this far below the culet |
| | `subdivision` | Subdivision | 2 | smoothing level of prongs/cast |
| | `show_stone` | ShowStone | True | show the stone |
| | `diam` / `outline` | Diam / Outline | built-in | custom unit stone / outline object |
| | `stone_material` | Stone Material | none | = `material`; set → stone becomes a mesh copy, JewelCraft no longer sees it |
| prongs | `tip` | Tip | Round | Round post or Claw |
| | `d` | ø | 0.5 | prong diameter |
| | `count` / `angle` | Count / ° Z | 4 / 45° | Round cut only: number and rotation of prongs |
| | `intersection` | Intersection | 25 | % of d overlapping the girdle |
| | `above_table` | Above Table | 0 | prong top above the table |
| | `set_cover` / `set_height` | Set Cover / Set Height | 40 / 80 | with `set`: % of crown covered / knuckle height |
| | `claw_length` / `claw_tip` | Claw Length / Claw Tip | 0.9 / 15 | Claw: tip length × d / tip thickness % |
| | `aim_center` | Aim Center | 0 | outline cuts: turn the prong from the outline normal (0) towards the stone centre (100 %) |
| | `smooth`, `material`, `stones` | | True, none, none | shading, metal material, take the stone from another object |
| cast | `type` | Type | Wall | Wall, Bezel (closed rim), Basket (two rails) |
| | `z_offset` / `xy_offset` | Z Offset / XY Offset | -0.15 / -0.05 | wall top vs girdle / wall vs girdle outline |
| | `cast_thickness` | Cast Thickness | 0.4 | wall / rail thickness |
| | `cast_bool`, `height_bool`, `offset_bool` | CastBool, HeightBool, OffsetBool | True, 0.4, 0 | Wall: slot on, slot height, slot shift |
| | `wall`, `seat`, `height`, `bezel_cover` | Wall, Seat, Height, Bezel Cover | 0.45, 0.3, 60, 15 | Bezel: wall, seat ledge, height % of crown, lip cover % |
| | `bezel_cutter`, `show_cutter` | Bezel Cutter, ShowCutter | none, False | Bezel: own cutter, show it |
| | `rail`, `rail_shape` | Rail, Rail Shape | 0.5, Round | Basket: rail height, Round or Flat |
| | `upper_rail` | Upper Rail | True | Basket: off → only the lower rail |
| | `smooth`, `material`, `stones` | | True, none, none | as prongs |
| seat | `cutter` | Cutter | auto | seat cutter object (auto from stone) |
| | `bool_cutter` | BoolCutter | True | union all metal, then cut |
| | `bool_object` / `bool_collection` | BoolObject / BoolCollection | none | extra cutters subtracted from the metal |
| | `smooth`, `realize_all`, `show_cutter` | Smooth, Realize All, ShowCutter | True, False, False | |

## Rules

1. One stone = one object. Name it; every later verb addresses it by that name.
2. Call `stone()` first; then `prongs`, `cast`, `seat` in any order — the stack order is fixed.
3. A verb writes only the arguments it gets (plus its named defaults: `cut/width/length`, `tip`, `type`); deleting a keyword from the program keeps the last value.
4. Use only keywords from the table; an unknown keyword, menu item or datablock name raises `ValueError`.
5. Bezel and Basket need no `prongs()`. Use `seat()` on every setting meant for casting.
6. Stone axes: width along X, length along Y, girdle at z = 0, table up (+Z); place parts with `at`.
7. Re-run the whole program after each edit; it never duplicates objects or modifiers.

## Example — earring

```python
stone("Emerald", cut="Emerald", width=8, length=10, set=True)
prongs("Emerald", tip="Claw", d=0.9, set_cover=40)
cast("Emerald", type="Wall", cast_thickness=0.6)
seat("Emerald")
stone("Top", cut="Round", width=2, at=(0, 7.2, 0), set=True)
cast("Top", type="Bezel", wall=0.4)
seat("Top")
```
