# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from math import pi
from pathlib import Path
from typing import NamedTuple

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty
from bpy.types import Menu, Object, Operator, Panel, PropertyGroup
from mathutils import Matrix, Vector


_TEMPLATE_CACHE: dict[str, tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]] = {}
_UPDATE_GUARD = False
_CAST_UPDATE_GUARD = False
_CAST_INSTANCE_UPDATE_GUARD = False

_CAST_DEFAULT_CLEARANCE = 0.15
_CAST_DEFAULT_WALL_THICKNESS = 0.65
_CAST_DEFAULT_HEIGHT = 1.5
_CAST_DEFAULT_TOP_OFFSET = 0.2
_CAST_DEFAULT_RAIL_HEIGHT = 0.4
_CAST_DEFAULT_BOTTOM_SCALE = 60.0
_CAST_DEFAULT_SUPPORT_COUNT = 4
_CAST_DEFAULT_SUPPORT_WIDTH = 0.7


class CutSpec(NamedTuple):
    name: str
    mesh_name: str
    base_width: float
    base_length: float
    girdle_bottom: float
    girdle_top: float
    crown_top: float
    pavilion_bottom: float

    @property
    def girdle_percent(self) -> float:
        return (self.girdle_top - self.girdle_bottom) / self.base_width * 100.0

    @property
    def crown_percent(self) -> float:
        return (self.crown_top - self.girdle_top) / self.base_width * 100.0

    @property
    def pavilion_percent(self) -> float:
        return (self.girdle_bottom - self.pavilion_bottom) / self.base_width * 100.0


_CUT_SPECS = {
    "ROUND": CutSpec("Round", "Round", 1.0, 1.0, 0.0, 0.026999999, 0.174765408, -0.430823237),
    "OVAL": CutSpec("Oval", "Oval", 0.625, 1.0, 0.0, 0.023443084, 0.110969022, -0.271652102),
    "CUSHION": CutSpec("Cushion", "Cushion", 1.0, 1.0, -0.036082, 0.03156, 0.168323144, -0.51834321),
    "PEAR": CutSpec("Pear", "Pear", 0.625, 1.0, 0.0, 0.023443084, 0.110969022, -0.271652102),
    "MARQUISE": CutSpec("Marquise", "Marquise", 0.5, 1.0, 0.0, 0.017049512, 0.080704741, -0.197565153),
    "PRINCESS": CutSpec("Princess", "Princess", 1.0, 1.0, 0.0, 0.026000001, 0.159042552, -0.572603762),
    "BAGUETTE": CutSpec("Baguette", "Baguette", 0.5, 1.0, 0.0, 0.020000003, 0.120000005, -0.222012565),
    "SQUARE": CutSpec("Square", "Square", 1.0, 1.0, 0.0, 0.030000007, 0.183104709, -0.476217419),
    "EMERALD": CutSpec("Emerald", "Emerald", 0.714285135, 1.0, 0.0, 0.02142857, 0.104759686, -0.361876398),
    "ASSCHER": CutSpec("Asscher", "Asscher", 0.99999994, 0.999999285, 0.0, 0.029999999, 0.207979545, -0.532134891),
    "RADIANT": CutSpec("Radiant", "Radiant", 1.0, 1.0, 0.0, 0.023, 0.15812172, -0.552452385),
    "FLANDERS": CutSpec("Flanders", "Flanders", 1.0, 1.0, 0.0, 0.040275082, 0.216103494, -0.499303997),
    "OCTAGON": CutSpec("Octagon", "Octagon", 1.0, 1.0, 0.0, 0.016158301, 0.185605347, -0.473251879),
    "HEART": CutSpec("Heart", "Heart", 1.0, 0.950194836, 0.0, 0.028006261, 0.146071643, -0.404978514),
    "TRILLION": CutSpec("Trillion", "Trillion", 0.99999994, 0.971745133, 0.0, 0.031659383, 0.120167762, -0.401195467),
    "TRILLIANT": CutSpec("Trilliant", "Trilliant", 1.0, 0.930331707, 0.0, 0.035397325, 0.185548931, -0.330609143),
    "TRIANGLE": CutSpec("Triangle", "Triangle", 1.154700756, 1.000000358, 0.0, 0.037824187, 0.142209366, -0.390385389),
}

_CUT_ITEMS = tuple(
    (identifier, spec.name, f"Standard {spec.name.lower()} facet layout")
    for identifier, spec in _CUT_SPECS.items()
)

_STONE_ITEMS = (
    ("DIAMOND", "Diamond", ""),
    ("ALEXANDRITE", "Alexandrite", ""),
    ("AMETHYST", "Amethyst", ""),
    ("AQUAMARINE", "Aquamarine", ""),
    ("CITRINE", "Citrine", ""),
    ("CUBIC_ZIRCONIA", "Cubic Zirconia", ""),
    ("EMERALD", "Emerald", ""),
    ("GARNET", "Garnet", ""),
    ("MORGANITE", "Morganite", ""),
    ("PERIDOT", "Peridot", ""),
    ("QUARTZ", "Quartz", ""),
    ("RUBY", "Ruby", ""),
    ("SAPPHIRE", "Sapphire", ""),
    ("SPINEL", "Spinel", ""),
    ("TANZANITE", "Tanzanite", ""),
    ("TOPAZ", "Topaz", ""),
    ("TOURMALINE", "Tourmaline", ""),
    ("ZIRCON", "Zircon", ""),
)


def _asset_path() -> Path:
    return Path(__file__).resolve().parent / "assets" / "gems.blend"


def _load_template(mesh_name: str) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    cached = _TEMPLATE_CACHE.get(mesh_name)
    if cached is not None:
        return cached

    path = _asset_path()
    if not path.exists():
        raise FileNotFoundError(f"Gem template library not found: {path}")

    with bpy.data.libraries.load(str(path)) as (_, data_to):
        data_to.meshes = [mesh_name]

    mesh = data_to.meshes[0]
    if mesh is None:
        raise RuntimeError(f"Mesh template not found: {mesh_name}")

    vertices = [tuple(vertex.co) for vertex in mesh.vertices]
    faces = [tuple(polygon.vertices) for polygon in mesh.polygons]
    bpy.data.meshes.remove(mesh)

    cached = vertices, faces
    _TEMPLATE_CACHE[mesh_name] = cached
    return cached


def _cut_geometry(
    cut: str,
    length_mm: float,
    width_mm: float,
    girdle_percent: float,
    crown_percent: float,
    pavilion_percent: float,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    spec = _CUT_SPECS[cut]
    source_vertices, faces = _load_template(spec.mesh_name)

    width = width_mm
    length = length_mm
    girdle_height = width * girdle_percent / 100.0
    crown_height = width * crown_percent / 100.0
    pavilion_depth = width * pavilion_percent / 100.0

    scale_x = width / spec.base_width
    scale_y = length / spec.base_length
    base_girdle_height = spec.girdle_top - spec.girdle_bottom
    base_crown_height = spec.crown_top - spec.girdle_top
    base_pavilion_depth = spec.girdle_bottom - spec.pavilion_bottom

    vertices: list[tuple[float, float, float]] = []
    for x, y, z in source_vertices:
        if z < spec.girdle_bottom:
            pavilion_factor = (spec.girdle_bottom - z) / base_pavilion_depth
            z_new = -pavilion_factor * pavilion_depth
        elif z <= spec.girdle_top:
            girdle_factor = (z - spec.girdle_bottom) / base_girdle_height
            z_new = girdle_factor * girdle_height
        else:
            crown_factor = (z - spec.girdle_top) / base_crown_height
            z_new = girdle_height + crown_factor * crown_height

        vertices.append((x * scale_x, y * scale_y, z_new))

    return vertices, faces


def _signed_area(points: list[Vector]) -> float:
    return 0.5 * sum(
        point.x * points[(index + 1) % len(points)].y
        - points[(index + 1) % len(points)].x * point.y
        for index, point in enumerate(points)
    )


def _cross_2d(origin: Vector, first: Vector, second: Vector) -> float:
    return (first.x - origin.x) * (second.y - origin.y) - (first.y - origin.y) * (second.x - origin.x)


def _convex_hull(points: list[Vector]) -> list[Vector]:
    unique = sorted({(round(point.x, 9), round(point.y, 9)) for point in points})
    vectors = [Vector(point) for point in unique]
    if len(vectors) <= 3:
        return vectors

    lower: list[Vector] = []
    for point in vectors:
        while len(lower) >= 2 and _cross_2d(lower[-2], lower[-1], point) <= 1e-10:
            lower.pop()
        lower.append(point)

    upper: list[Vector] = []
    for point in reversed(vectors):
        while len(upper) >= 2 and _cross_2d(upper[-2], upper[-1], point) <= 1e-10:
            upper.pop()
        upper.append(point)

    return lower[:-1] + upper[:-1]


def _base_girdle_outline(cut: str) -> list[Vector]:
    spec = _CUT_SPECS[cut]
    source_vertices, _ = _load_template(spec.mesh_name)
    tolerance = max(0.0001, spec.base_width * 0.0001)
    if cut == "HEART":
        points = [
            Vector((x, y))
            for x, y, z in source_vertices
            if abs(z - spec.girdle_bottom) <= tolerance
        ]
    else:
        band_points = [
            Vector((x, y))
            for x, y, z in source_vertices
            if spec.girdle_bottom - tolerance <= z <= spec.girdle_top + tolerance
        ]
        points = _convex_hull(band_points)
    if len(points) < 3:
        raise RuntimeError(f"Could not extract the girdle outline for {spec.name}")

    center = sum(points, Vector((0.0, 0.0))) / len(points)
    points.sort(key=lambda point: (point - center).angle_signed(Vector((1.0, 0.0))))
    if _signed_area(points) < 0.0:
        points.reverse()
    return points


def _scaled_girdle_outline(gem: Object) -> list[Vector]:
    props = gem.parametric_gem
    spec = _CUT_SPECS[props.cut]
    scale_x = props.width_mm / spec.base_width
    scale_y = props.length_mm / spec.base_length
    return [Vector((point.x * scale_x, point.y * scale_y)) for point in _base_girdle_outline(props.cut)]


def _parallel_outlines(
    points: list[Vector],
    inner_distance: float,
    outer_distance: float,
    miter_limit: float = 2.5,
) -> tuple[list[Vector], list[Vector]]:
    inner: list[Vector] = []
    outer: list[Vector] = []

    for index, point in enumerate(points):
        previous = points[index - 1]
        following = points[(index + 1) % len(points)]
        incoming = (point - previous).normalized()
        outgoing = (following - point).normalized()
        normal_in = Vector((incoming.y, -incoming.x))
        normal_out = Vector((outgoing.y, -outgoing.x))
        bisector = normal_in + normal_out

        if bisector.length_squared < 1e-12:
            for distance, target in ((inner_distance, inner), (outer_distance, outer)):
                target.append(point + normal_out * distance)
            continue

        bisector.normalize()
        denominator = bisector.dot(normal_out)
        miter_ratio = float("inf") if denominator <= 1e-6 else 1.0 / denominator

        if miter_ratio > miter_limit:
            for distance, target in ((inner_distance, inner), (outer_distance, outer)):
                target.append(point + normal_in * distance)
                target.append(point + normal_out * distance)
        else:
            for distance, target in ((inner_distance, inner), (outer_distance, outer)):
                target.append(point + bisector * distance * miter_ratio)

    return inner, outer


def _subdivide_parallel_outlines(
    inner: list[Vector],
    outer: list[Vector],
    maximum_segment_length: float = 0.25,
) -> tuple[list[Vector], list[Vector]]:
    refined_inner: list[Vector] = []
    refined_outer: list[Vector] = []
    for index, outer_point in enumerate(outer):
        following = (index + 1) % len(outer)
        segment_length = (outer[following] - outer_point).length
        subdivisions = max(1, int(segment_length / maximum_segment_length) + 1)
        for step in range(subdivisions):
            factor = step / subdivisions
            refined_outer.append(outer_point.lerp(outer[following], factor))
            refined_inner.append(inner[index].lerp(inner[following], factor))
    return refined_inner, refined_outer


def _support_segment_indices(outer: list[Vector], support_count: int, support_width_mm: float) -> set[int]:
    lengths = [
        (outer[(index + 1) % len(outer)] - point).length
        for index, point in enumerate(outer)
    ]
    perimeter = sum(lengths)
    if perimeter <= 1e-9:
        return set()

    midpoints: list[float] = []
    distance = 0.0
    for length in lengths:
        midpoints.append(distance + length * 0.5)
        distance += length

    selected: set[int] = set()
    for support_index in range(support_count):
        anchor = perimeter * support_index / support_count
        distances = [
            min(abs(midpoint - anchor), perimeter - abs(midpoint - anchor))
            for midpoint in midpoints
        ]
        nearest = min(range(len(distances)), key=distances.__getitem__)
        selected.add(nearest)
        half_width = support_width_mm * 0.5
        selected.update(index for index, value in enumerate(distances) if value <= half_width)
    return selected


def _cast_geometry(
    gem: Object,
    clearance_mm: float,
    wall_thickness_mm: float,
    height_mm: float,
    top_offset_mm: float,
    rail_height_mm: float,
    bottom_scale_percent: float,
    support_count: int,
    support_width_mm: float,
) -> tuple[list[tuple[float, float, float]], list[tuple[int, ...]]]:
    outline = _scaled_girdle_outline(gem)
    top_inner, top_outer = _parallel_outlines(
        outline,
        clearance_mm - wall_thickness_mm,
        clearance_mm,
    )
    if len(top_inner) != len(top_outer):
        raise RuntimeError("Cast outlines have incompatible topology")
    top_inner, top_outer = _subdivide_parallel_outlines(top_inner, top_outer)

    center = sum(outline, Vector((0.0, 0.0))) / len(outline)
    bottom_scale = bottom_scale_percent / 100.0
    bottom_inner = [center + (point - center) * bottom_scale for point in top_inner]
    bottom_outer = [center + (point - center) * bottom_scale for point in top_outer]

    top_z = -top_offset_mm
    bottom_z = top_z - height_mm
    rail_height = min(rail_height_mm, height_mm * 0.45)
    vertices = (
        [(point.x, point.y, top_z) for point in top_inner]
        + [(point.x, point.y, top_z) for point in top_outer]
        + [(point.x, point.y, top_z - rail_height) for point in top_inner]
        + [(point.x, point.y, top_z - rail_height) for point in top_outer]
        + [(point.x, point.y, bottom_z + rail_height) for point in bottom_inner]
        + [(point.x, point.y, bottom_z + rail_height) for point in bottom_outer]
        + [(point.x, point.y, bottom_z) for point in bottom_inner]
        + [(point.x, point.y, bottom_z) for point in bottom_outer]
    )

    count = len(top_inner)
    top_inner_top = 0
    top_outer_top = count
    top_inner_bottom = count * 2
    top_outer_bottom = count * 3
    bottom_inner_top = count * 4
    bottom_outer_top = count * 5
    bottom_inner_bottom = count * 6
    bottom_outer_bottom = count * 7
    support_segments = _support_segment_indices(top_outer, support_count, support_width_mm)
    faces: list[tuple[int, ...]] = []
    for index in range(count):
        following = (index + 1) % count
        faces.extend(
            (
                (top_outer_top + index, top_outer_top + following, top_inner_top + following, top_inner_top + index),
                (top_outer_top + index, top_outer_bottom + index, top_outer_bottom + following, top_outer_top + following),
                (top_inner_top + index, top_inner_top + following, top_inner_bottom + following, top_inner_bottom + index),
                (bottom_outer_top + index, bottom_outer_bottom + index, bottom_outer_bottom + following, bottom_outer_top + following),
                (bottom_inner_top + index, bottom_inner_top + following, bottom_inner_bottom + following, bottom_inner_bottom + index),
                (bottom_outer_bottom + following, bottom_outer_bottom + index, bottom_inner_bottom + index, bottom_inner_bottom + following),
            )
        )

        if index not in support_segments:
            faces.extend(
                (
                    (top_outer_bottom + following, top_outer_bottom + index, top_inner_bottom + index, top_inner_bottom + following),
                    (bottom_outer_top + index, bottom_outer_top + following, bottom_inner_top + following, bottom_inner_top + index),
                )
            )
            continue

        faces.extend(
            (
                (top_outer_bottom + index, bottom_outer_top + index, bottom_outer_top + following, top_outer_bottom + following),
                (top_inner_bottom + index, top_inner_bottom + following, bottom_inner_top + following, bottom_inner_top + index),
            )
        )
        if (index - 1) % count not in support_segments:
            faces.append(
                (top_outer_bottom + index, top_inner_bottom + index, bottom_inner_top + index, bottom_outer_top + index)
            )
        if following not in support_segments:
            faces.append(
                (top_outer_bottom + following, bottom_outer_top + following, bottom_inner_top + following, top_inner_bottom + following)
            )

    return vertices, faces


def _linked_casts(gem: Object) -> list[Object]:
    casts: list[Object] = []
    for obj in bpy.data.objects:
        props = getattr(obj, "parametric_cast", None)
        if props is not None and props.is_parametric and props.source_gem is gem:
            casts.append(obj)
    return casts


def rebuild_cast_object(obj: Object) -> None:
    props = obj.parametric_cast
    gem = props.source_gem
    if not props.is_parametric or obj.type != "MESH" or gem is None:
        return
    if not gem.parametric_gem.is_parametric:
        return

    vertices, faces = _cast_geometry(
        gem,
        props.clearance_mm,
        props.wall_thickness_mm,
        props.height_mm,
        props.top_offset_mm,
        props.rail_height_mm,
        props.bottom_scale_percent,
        props.support_count,
        props.support_width_mm,
    )

    if obj.data.users > 1:
        obj.data = obj.data.copy()

    obj.scale = (1.0, 1.0, 1.0)
    mesh = obj.data
    spec = _CUT_SPECS[gem.parametric_gem.cut]
    mesh.name = f"Parametric {spec.mesh_name} Cast"
    if obj.name.startswith("Parametric "):
        obj.name = f"Parametric {spec.mesh_name} Cast"
    mesh.clear_geometry()
    mesh.from_pydata(vertices, [], faces)
    mesh.validate(verbose=False, clean_customdata=False)
    mesh.update(calc_edges=True)
    for polygon in mesh.polygons:
        polygon.use_smooth = False

    obj["parametric_cast_version"] = 2
    obj.update_tag(refresh={"DATA"})


def rebuild_linked_casts(gem: Object) -> None:
    for cast in _linked_casts(gem):
        rebuild_cast_object(cast)


def _matrix_to_list(matrix: Matrix) -> list[float]:
    return [value for row in matrix for value in row]


def _matrix_from_list(values) -> Matrix:
    if values is None or len(values) != 16:
        return Matrix.Identity(4)
    return Matrix(tuple(tuple(values[row * 4 + column] for column in range(4)) for row in range(4)))


def _register_cast_template(template: Object, gem: Object) -> None:
    props = template.parametric_cast_template
    gem_props = gem.parametric_gem
    relative_matrix = gem.matrix_world.inverted_safe() @ template.matrix_world

    props.is_template = True
    props.cut = gem_props.cut
    props.reference_length_mm = gem_props.length_mm
    props.reference_width_mm = gem_props.width_mm
    props.reference_depth_mm = gem_props.depth_mm
    template["parametric_cast_template_version"] = 1
    template["parametric_cast_template_matrix"] = _matrix_to_list(relative_matrix)
    template["parametric_cast_template_data"] = {
        "cut": props.cut,
        "reference_length_mm": props.reference_length_mm,
        "reference_width_mm": props.reference_width_mm,
        "reference_depth_mm": props.reference_depth_mm,
    }


def _instance_scale_factors(template: Object, gem: Object) -> tuple[float, float, float]:
    template_props = template.parametric_cast_template
    gem_props = gem.parametric_gem
    if min(
        template_props.reference_width_mm,
        template_props.reference_length_mm,
        template_props.reference_depth_mm,
    ) <= 0.0:
        raise RuntimeError("Cast template reference dimensions are invalid")
    return (
        gem_props.width_mm / template_props.reference_width_mm,
        gem_props.length_mm / template_props.reference_length_mm,
        gem_props.depth_mm / template_props.reference_depth_mm,
    )


def rebuild_cast_instance(instance: Object) -> None:
    props = instance.parametric_cast_instance
    template = props.template_object
    gem = props.source_gem
    if not props.is_instance or template is None or gem is None:
        return
    if not template.parametric_cast_template.is_template or not gem.parametric_gem.is_parametric:
        return
    if template.parametric_cast_template.cut != gem.parametric_gem.cut:
        return

    scale_x, scale_y, scale_z = _instance_scale_factors(template, gem)
    relative_matrix = _matrix_from_list(template.get("parametric_cast_template_matrix"))
    scale_matrix = Matrix.Diagonal((scale_x, scale_y, scale_z, 1.0))

    instance.data = template.data
    instance.parent = gem
    instance.matrix_parent_inverse = Matrix.Identity(4)
    instance.matrix_basis = scale_matrix @ relative_matrix
    instance["parametric_cast_instance_version"] = 1
    instance["parametric_cast_instance_data"] = {
        "template": template.name,
        "source_gem": gem.name,
    }
    instance.update_tag(refresh={"OBJECT", "DATA"})


def _linked_cast_instances(gem: Object) -> list[Object]:
    instances: list[Object] = []
    for obj in bpy.data.objects:
        props = getattr(obj, "parametric_cast_instance", None)
        if props is not None and props.is_instance and props.source_gem is gem:
            instances.append(obj)
    return instances


def rebuild_linked_cast_instances(gem: Object) -> None:
    for instance in _linked_cast_instances(gem):
        rebuild_cast_instance(instance)


def _create_or_update_cast_instance(template: Object, gem: Object, collection) -> tuple[Object, bool]:
    linked = _linked_cast_instances(gem)
    instance = linked[0] if linked else None
    created = instance is None
    if instance is None:
        instance = template.copy()
        instance.data = template.data
        collection.objects.link(instance)
        instance.name = f"{template.name} Instance"

    template_props = instance.parametric_cast_template
    template_props.is_template = False
    for key in (
        "parametric_cast_template_version",
        "parametric_cast_template_matrix",
        "parametric_cast_template_data",
    ):
        if key in instance:
            del instance[key]
    props = instance.parametric_cast_instance
    props.is_instance = True
    props.template_object = template
    props.source_gem = gem
    rebuild_cast_instance(instance)
    return instance, created


def _set_jewelcraft_metadata(obj: Object) -> None:
    props = obj.parametric_gem
    obj["gem"] = {"cut": props.cut, "stone": props.stone}
    obj["parametric_gem_version"] = 1


def rebuild_object(obj: Object, scene: bpy.types.Scene) -> None:
    props = obj.parametric_gem
    if not props.is_parametric or obj.type != "MESH":
        return

    vertices, faces = _cut_geometry(
        props.cut,
        props.length_mm,
        props.width_mm,
        props.girdle_percent,
        props.crown_percent,
        props.pavilion_percent,
    )

    if obj.data.users > 1:
        obj.data = obj.data.copy()

    obj.scale = (1.0, 1.0, 1.0)
    mesh = obj.data
    spec = _CUT_SPECS[props.cut]
    mesh.name = f"Parametric {spec.mesh_name}"
    if obj.name.startswith("Parametric "):
        obj.name = f"Parametric {spec.mesh_name}"
    mesh.clear_geometry()
    mesh.from_pydata(vertices, [], faces)
    mesh.update(calc_edges=True)
    for polygon in mesh.polygons:
        polygon.use_smooth = False

    _set_jewelcraft_metadata(obj)
    obj.update_tag(refresh={"DATA"})
    rebuild_linked_casts(obj)
    rebuild_linked_cast_instances(obj)


def _update_parameter(props: "ParametricGemProperties", context: bpy.types.Context, property_name: str, rebuild: bool = True) -> None:
    global _UPDATE_GUARD

    if _UPDATE_GUARD or not props.is_parametric:
        return

    obj = props.id_data
    if not isinstance(obj, Object):
        return

    targets = [obj]
    settings = context.scene.parametric_gem_settings
    if settings.affect_selected and context.view_layer.objects.active is obj:
        targets.extend(
            candidate
            for candidate in context.selected_objects
            if candidate is not obj
            and candidate.type == "MESH"
            and candidate.parametric_gem.is_parametric
        )

    _UPDATE_GUARD = True
    try:
        source_value = getattr(props, property_name)
        for target in targets:
            target_props = target.parametric_gem
            if target is not obj:
                setattr(target_props, property_name, source_value)
            if rebuild:
                rebuild_object(target, context.scene)
            else:
                _set_jewelcraft_metadata(target)
    finally:
        _UPDATE_GUARD = False

    if rebuild:
        context.view_layer.update()


def _update_length(self, context):
    _update_parameter(self, context, "length_mm")


def _update_width(self, context):
    _update_parameter(self, context, "width_mm")


def _update_girdle(self, context):
    _update_parameter(self, context, "girdle_percent")


def _update_crown(self, context):
    _update_parameter(self, context, "crown_percent")


def _update_pavilion(self, context):
    _update_parameter(self, context, "pavilion_percent")


def _update_stone(self, context):
    _update_parameter(self, context, "stone", rebuild=False)


def _update_cut(self, context):
    global _UPDATE_GUARD

    if _UPDATE_GUARD or not self.is_parametric:
        return

    obj = self.id_data
    if not isinstance(obj, Object):
        return

    targets = [obj]
    settings = context.scene.parametric_gem_settings
    if settings.affect_selected and context.view_layer.objects.active is obj:
        targets.extend(
            candidate
            for candidate in context.selected_objects
            if candidate is not obj
            and candidate.type == "MESH"
            and candidate.parametric_gem.is_parametric
        )

    _UPDATE_GUARD = True
    try:
        for target in targets:
            props = target.parametric_gem
            props.cut = self.cut
            rebuild_object(target, context.scene)
    finally:
        _UPDATE_GUARD = False

    context.view_layer.update()


def _update_add_cut(self, context):
    spec = _CUT_SPECS[self.cut]
    self.width_mm = self.length_mm * spec.base_width / spec.base_length
    self.girdle_percent = spec.girdle_percent
    self.crown_percent = spec.crown_percent
    self.pavilion_percent = spec.pavilion_percent


def _get_depth(self) -> float:
    total_percent = self.girdle_percent + self.crown_percent + self.pavilion_percent
    return self.width_mm * total_percent / 100.0


def _set_depth(self, value: float) -> None:
    if self.width_mm <= 0.0:
        return

    fixed_percent = self.girdle_percent + self.crown_percent
    pavilion_percent = value / self.width_mm * 100.0 - fixed_percent
    self.pavilion_percent = max(0.01, pavilion_percent)


def _curve_control_coordinates(obj: Object) -> list[Vector]:
    if obj.type != "CURVE":
        return []
    coordinates: list[Vector] = []
    for spline in obj.data.splines:
        if spline.type == "BEZIER":
            coordinates.extend(point.co.copy() for point in spline.bezier_points)
        else:
            coordinates.extend(point.co.xyz.copy() for point in spline.points)
    return coordinates


def _curve_local_center(obj: Object) -> Vector:
    coordinates = _curve_control_coordinates(obj)
    if not coordinates:
        return Vector((0.0, 0.0, 0.0))
    minimum = Vector(tuple(min(point[axis] for point in coordinates) for axis in range(3)))
    maximum = Vector(tuple(max(point[axis] for point in coordinates) for axis in range(3)))
    return (minimum + maximum) * 0.5


def _curve_radius_world(obj: Object) -> float:
    coordinates = _curve_control_coordinates(obj)
    if not coordinates:
        return 0.0
    center_world = obj.matrix_world @ _curve_local_center(obj)
    return max(((obj.matrix_world @ point) - center_world).length for point in coordinates)


def _resize_curve_radius(obj: Object, target_radius: float) -> None:
    current_radius = _curve_radius_world(obj)
    if obj.type != "CURVE" or current_radius <= 1e-9 or target_radius <= 0.0:
        return

    factor = target_radius / current_radius
    center = _curve_local_center(obj)
    for spline in obj.data.splines:
        if spline.type == "BEZIER":
            for point in spline.bezier_points:
                point.co = center + (point.co - center) * factor
                point.handle_left = center + (point.handle_left - center) * factor
                point.handle_right = center + (point.handle_right - center) * factor
        else:
            for point in spline.points:
                coordinate = center + (point.co.xyz - center) * factor
                point.co = (*coordinate, point.co.w)

    obj.data.update_tag()
    obj.update_tag(refresh={"DATA"})


def _get_curve_radius(self) -> float:
    obj = self.id_data
    return _curve_radius_world(obj) if isinstance(obj, Object) else 0.0


def _set_curve_radius(self, value: float) -> None:
    obj = self.id_data
    if isinstance(obj, Object):
        _resize_curve_radius(obj, value)


def _get_curve_diameter(self) -> float:
    return _get_curve_radius(self) * 2.0


def _set_curve_diameter(self, value: float) -> None:
    if value > 0.0:
        _set_curve_radius(self, value * 0.5)


def _get_curve_circumference(self) -> float:
    return _get_curve_radius(self) * 2.0 * pi


def _set_curve_circumference(self, value: float) -> None:
    if value > 0.0:
        _set_curve_radius(self, value / (2.0 * pi))


def _update_cast_parameter(props: "ParametricCastProperties", context: bpy.types.Context, property_name: str) -> None:
    global _CAST_UPDATE_GUARD

    if _CAST_UPDATE_GUARD or not props.is_parametric:
        return

    obj = props.id_data
    if not isinstance(obj, Object):
        return

    targets = [obj]
    settings = context.scene.parametric_gem_settings
    if settings.affect_selected and context.view_layer.objects.active is obj:
        targets.extend(
            candidate
            for candidate in context.selected_objects
            if candidate is not obj
            and candidate.type == "MESH"
            and candidate.parametric_cast.is_parametric
        )

    _CAST_UPDATE_GUARD = True
    try:
        source_value = getattr(props, property_name)
        for target in targets:
            if target is not obj:
                setattr(target.parametric_cast, property_name, source_value)
            rebuild_cast_object(target)
    finally:
        _CAST_UPDATE_GUARD = False

    context.view_layer.update()


def _update_cast_clearance(self, context):
    _update_cast_parameter(self, context, "clearance_mm")


def _update_cast_wall_thickness(self, context):
    _update_cast_parameter(self, context, "wall_thickness_mm")


def _update_cast_height(self, context):
    _update_cast_parameter(self, context, "height_mm")


def _update_cast_top_offset(self, context):
    _update_cast_parameter(self, context, "top_offset_mm")


def _update_cast_rail_height(self, context):
    _update_cast_parameter(self, context, "rail_height_mm")


def _update_cast_bottom_scale(self, context):
    _update_cast_parameter(self, context, "bottom_scale_percent")


def _update_cast_support_count(self, context):
    _update_cast_parameter(self, context, "support_count")


def _update_cast_support_width(self, context):
    _update_cast_parameter(self, context, "support_width_mm")


class ParametricCircleSizeProperties(PropertyGroup):
    diameter_mm: FloatProperty(
        name="Diameter (mm)",
        description="World-space diameter of the active circular curve",
        min=0.001,
        soft_max=1000.0,
        precision=3,
        get=_get_curve_diameter,
        set=_set_curve_diameter,
    )
    circumference_mm: FloatProperty(
        name="Circumference (mm)",
        description="Mathematical circumference calculated as 2 pi times radius",
        min=0.001,
        soft_max=10000.0,
        precision=3,
        get=_get_curve_circumference,
        set=_set_curve_circumference,
    )


class ParametricGemProperties(PropertyGroup):
    is_parametric: BoolProperty(default=False, options={"HIDDEN"})
    cut: EnumProperty(
        name="Cut",
        items=_CUT_ITEMS,
        default="MARQUISE",
        update=_update_cut,
    )
    stone: EnumProperty(name="Stone", items=_STONE_ITEMS, default="DIAMOND", update=_update_stone)
    length_mm: FloatProperty(
        name="Length (mm)",
        default=10.0,
        min=0.01,
        soft_max=100.0,
        precision=3,
        update=_update_length,
    )
    width_mm: FloatProperty(
        name="Width (mm)",
        default=5.0,
        min=0.01,
        soft_max=100.0,
        precision=3,
        update=_update_width,
    )
    depth_mm: FloatProperty(
        name="Depth (mm)",
        description="Total gem depth; editing it recalculates pavilion depth",
        min=0.001,
        soft_max=100.0,
        precision=3,
        get=_get_depth,
        set=_set_depth,
    )
    girdle_percent: FloatProperty(
        name="Girdle Height (%)",
        description="Maximum girdle height as a percentage of gem width",
        default=3.41,
        min=0.01,
        soft_max=15.0,
        precision=2,
        update=_update_girdle,
    )
    crown_percent: FloatProperty(
        name="Crown Height (%)",
        description="Crown height as a percentage of gem width",
        default=12.73,
        min=0.01,
        soft_max=40.0,
        precision=2,
        update=_update_crown,
    )
    pavilion_percent: FloatProperty(
        name="Pavilion Depth (%)",
        description="Pavilion depth as a percentage of gem width",
        default=39.51,
        min=0.01,
        soft_max=80.0,
        precision=2,
        update=_update_pavilion,
    )


class ParametricCastProperties(PropertyGroup):
    is_parametric: BoolProperty(default=False, options={"HIDDEN"})
    source_gem: PointerProperty(name="Source Gem", type=Object)
    clearance_mm: FloatProperty(
        name="Outer Gap (mm)",
        description="Horizontal clearance from the girdle outline to the outside of the upper rail",
        default=_CAST_DEFAULT_CLEARANCE,
        min=0.001,
        soft_max=2.0,
        precision=3,
        update=_update_cast_clearance,
    )
    wall_thickness_mm: FloatProperty(
        name="Rail Width (mm)",
        description="Horizontal width of the upper and lower gallery rails",
        default=_CAST_DEFAULT_WALL_THICKNESS,
        min=0.1,
        soft_max=5.0,
        precision=3,
        update=_update_cast_wall_thickness,
    )
    height_mm: FloatProperty(
        name="Basket Height (mm)",
        description="Vertical distance from the top of the upper rail to the bottom of the lower rail",
        default=_CAST_DEFAULT_HEIGHT,
        min=0.1,
        soft_max=10.0,
        precision=3,
        update=_update_cast_height,
    )
    top_offset_mm: FloatProperty(
        name="Below Girdle (mm)",
        description="Distance from the lower girdle edge to the top of the cast",
        default=_CAST_DEFAULT_TOP_OFFSET,
        min=0.0,
        soft_max=5.0,
        precision=3,
        update=_update_cast_top_offset,
    )
    rail_height_mm: FloatProperty(
        name="Rail Height (mm)",
        description="Vertical thickness of both gallery rails",
        default=_CAST_DEFAULT_RAIL_HEIGHT,
        min=0.05,
        soft_max=2.0,
        precision=3,
        update=_update_cast_rail_height,
    )
    bottom_scale_percent: FloatProperty(
        name="Lower Gallery (%)",
        description="Size of the lower gallery as a percentage of the upper gallery",
        default=_CAST_DEFAULT_BOTTOM_SCALE,
        min=10.0,
        max=95.0,
        precision=1,
        update=_update_cast_bottom_scale,
    )
    support_count: IntProperty(
        name="Support Count",
        description="Number of inclined supports between the gallery rails",
        default=_CAST_DEFAULT_SUPPORT_COUNT,
        min=3,
        max=16,
        update=_update_cast_support_count,
    )
    support_width_mm: FloatProperty(
        name="Support Width (mm)",
        description="Width of each inclined support along the gallery perimeter",
        default=_CAST_DEFAULT_SUPPORT_WIDTH,
        min=0.1,
        soft_max=3.0,
        precision=3,
        update=_update_cast_support_width,
    )


class ParametricCastTemplateProperties(PropertyGroup):
    is_template: BoolProperty(default=False, options={"HIDDEN"})
    cut: EnumProperty(name="Cut", items=_CUT_ITEMS, default="MARQUISE")
    reference_length_mm: FloatProperty(name="Reference Length (mm)", default=10.0, min=0.001, precision=3)
    reference_width_mm: FloatProperty(name="Reference Width (mm)", default=5.0, min=0.001, precision=3)
    reference_depth_mm: FloatProperty(name="Reference Depth (mm)", default=3.0, min=0.001, precision=3)


class ParametricCastInstanceProperties(PropertyGroup):
    is_instance: BoolProperty(default=False, options={"HIDDEN"})
    template_object: PointerProperty(name="Cast Template", type=Object)
    source_gem: PointerProperty(name="Source Gem", type=Object)


class ParametricGemSettings(PropertyGroup):
    affect_selected: BoolProperty(
        name="Affect Selected",
        description="Apply each changed parameter to all selected parametric gems",
        default=False,
    )
    cast_template: PointerProperty(
        name="Cast Template",
        description="Registered mesh used for linked cast instances",
        type=Object,
    )


class MESH_OT_parametric_gem_add(Operator):
    bl_idname = "mesh.parametric_gem_add"
    bl_label = "Add Parametric Gem"
    bl_description = "Create an editable parametric gemstone"
    bl_options = {"REGISTER", "UNDO"}

    cut: EnumProperty(name="Cut", items=_CUT_ITEMS, default="MARQUISE", update=_update_add_cut)
    length_mm: FloatProperty(name="Length (mm)", default=10.0, min=0.01, precision=3)
    width_mm: FloatProperty(name="Width (mm)", default=5.0, min=0.01, precision=3)
    girdle_percent: FloatProperty(name="Girdle Height (%)", default=3.41, min=0.01, precision=2)
    crown_percent: FloatProperty(name="Crown Height (%)", default=12.73, min=0.01, precision=2)
    pavilion_percent: FloatProperty(name="Pavilion Depth (%)", default=39.51, min=0.01, precision=2)
    stone: EnumProperty(name="Stone", items=_STONE_ITEMS, default="DIAMOND")

    def execute(self, context):
        global _UPDATE_GUARD

        spec = _CUT_SPECS[self.cut]
        mesh = bpy.data.meshes.new(f"Parametric {spec.mesh_name}")
        obj = bpy.data.objects.new(f"Parametric {spec.mesh_name}", mesh)
        context.collection.objects.link(obj)
        obj.location = context.scene.cursor.location

        for selected in context.selected_objects:
            selected.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj

        props = obj.parametric_gem
        _UPDATE_GUARD = True
        try:
            props.is_parametric = True
            props.cut = self.cut
            props.stone = self.stone
            props.length_mm = self.length_mm
            props.width_mm = self.width_mm
            props.girdle_percent = self.girdle_percent
            props.crown_percent = self.crown_percent
            props.pavilion_percent = self.pavilion_percent
        finally:
            _UPDATE_GUARD = False

        rebuild_object(obj, context.scene)
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class OBJECT_OT_parametric_gem_rebuild(Operator):
    bl_idname = "object.parametric_gem_rebuild"
    bl_label = "Rebuild Parametric Gem"
    bl_description = "Rebuild the active gem from its stored parameters"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == "MESH" and obj.parametric_gem.is_parametric

    def execute(self, context):
        rebuild_object(context.object, context.scene)
        return {"FINISHED"}


class OBJECT_OT_parametric_gem_reset_defaults(Operator):
    bl_idname = "object.parametric_gem_reset_defaults"
    bl_label = "Default"
    bl_description = "Restore the standard aspect ratio and height proportions for the selected cut"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == "MESH" and obj.parametric_gem.is_parametric

    def execute(self, context):
        global _UPDATE_GUARD

        active = context.object
        targets = [active]
        if context.scene.parametric_gem_settings.affect_selected:
            targets.extend(
                obj
                for obj in context.selected_objects
                if obj is not active
                and obj.type == "MESH"
                and obj.parametric_gem.is_parametric
            )

        _UPDATE_GUARD = True
        try:
            for obj in targets:
                props = obj.parametric_gem
                spec = _CUT_SPECS[props.cut]
                props.width_mm = props.length_mm * spec.base_width / spec.base_length
                props.girdle_percent = spec.girdle_percent
                props.crown_percent = spec.crown_percent
                props.pavilion_percent = spec.pavilion_percent
                rebuild_object(obj, context.scene)
        finally:
            _UPDATE_GUARD = False

        context.view_layer.update()
        return {"FINISHED"}


class OBJECT_OT_parametric_gem_copy_to_selected(Operator):
    bl_idname = "object.parametric_gem_copy_to_selected"
    bl_label = "Copy All to Selected"
    bl_description = "Copy all parameters from the active gem to selected parametric gems"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == "MESH" and obj.parametric_gem.is_parametric

    def execute(self, context):
        global _UPDATE_GUARD

        source = context.object.parametric_gem
        targets = [
            obj
            for obj in context.selected_objects
            if obj is not context.object
            and obj.type == "MESH"
            and obj.parametric_gem.is_parametric
        ]

        _UPDATE_GUARD = True
        try:
            for obj in targets:
                props = obj.parametric_gem
                props.cut = source.cut
                props.stone = source.stone
                props.length_mm = source.length_mm
                props.width_mm = source.width_mm
                props.girdle_percent = source.girdle_percent
                props.crown_percent = source.crown_percent
                props.pavilion_percent = source.pavilion_percent
                rebuild_object(obj, context.scene)
        finally:
            _UPDATE_GUARD = False

        context.view_layer.update()

        self.report({"INFO"}, f"Updated {len(targets)} selected gem(s)")
        return {"FINISHED"}


class OBJECT_OT_parametric_cast_template_register(Operator):
    bl_idname = "object.parametric_cast_template_register"
    bl_label = "Register Selected Mesh as Cast Template"
    bl_description = "Register the other selected mesh relative to the active standard parametric gem"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        gem = context.object
        if gem is None or gem.type != "MESH" or not gem.parametric_gem.is_parametric:
            return False
        return any(obj is not gem and obj.type == "MESH" for obj in context.selected_objects)

    def execute(self, context):
        gem = context.object
        candidates = [obj for obj in context.selected_objects if obj is not gem and obj.type == "MESH"]
        if len(candidates) != 1:
            self.report({"ERROR"}, "Select exactly one cast mesh in addition to the active standard gem")
            return {"CANCELLED"}

        template = candidates[0]
        _register_cast_template(template, gem)
        context.scene.parametric_gem_settings.cast_template = template
        self.report(
            {"INFO"},
            f"Registered {template.name} for {gem.parametric_gem.cut} at "
            f"{gem.parametric_gem.width_mm:.3f} x {gem.parametric_gem.length_mm:.3f} x "
            f"{gem.parametric_gem.depth_mm:.3f} mm",
        )
        return {"FINISHED"}


class OBJECT_OT_parametric_cast_instances_place(Operator):
    bl_idname = "object.parametric_cast_instances_place"
    bl_label = "Place Cast Instances on Selected Gems"
    bl_description = "Create linked cast instances with proportional XYZ scaling on selected gems"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        template = context.scene.parametric_gem_settings.cast_template
        if template is None or not template.parametric_cast_template.is_template:
            return False
        return any(
            obj.type == "MESH" and obj.parametric_gem.is_parametric
            for obj in context.selected_objects
        )

    def execute(self, context):
        template = context.scene.parametric_gem_settings.cast_template
        template_cut = template.parametric_cast_template.cut
        gems = [
            obj
            for obj in context.selected_objects
            if obj.type == "MESH"
            and obj.parametric_gem.is_parametric
            and obj.parametric_gem.cut == template_cut
        ]
        skipped = sum(
            1
            for obj in context.selected_objects
            if obj.type == "MESH"
            and obj.parametric_gem.is_parametric
            and obj.parametric_gem.cut != template_cut
        )
        if not gems:
            self.report({"ERROR"}, f"No selected {template_cut} gems")
            return {"CANCELLED"}

        instances: list[Object] = []
        created = 0
        for gem in gems:
            collection = gem.users_collection[0] if gem.users_collection else context.collection
            instance, was_created = _create_or_update_cast_instance(template, gem, collection)
            instances.append(instance)
            created += int(was_created)

        for obj in context.selected_objects:
            obj.select_set(False)
        for instance in instances:
            instance.select_set(True)
        context.view_layer.objects.active = instances[0]
        context.view_layer.update()

        message = f"Created {created}, updated {len(instances) - created} linked cast instance(s)"
        if skipped:
            message += f"; skipped {skipped} gem(s) with another cut"
        self.report({"INFO"}, message)
        return {"FINISHED"}


class OBJECT_OT_parametric_cast_instance_rebuild(Operator):
    bl_idname = "object.parametric_cast_instance_rebuild"
    bl_label = "Update Cast Instance"
    bl_description = "Update the active linked cast instance from its template and source gem"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == "MESH" and obj.parametric_cast_instance.is_instance

    def execute(self, context):
        rebuild_cast_instance(context.object)
        context.view_layer.update()
        return {"FINISHED"}


class OBJECT_OT_parametric_cast_add(Operator):
    bl_idname = "object.parametric_cast_add"
    bl_label = "Create Casts for Selected Gems"
    bl_description = "Create or update one linked open cast for every selected parametric gem"
    bl_options = {"REGISTER", "UNDO"}

    clearance_mm: FloatProperty(
        name="Outer Gap (mm)",
        default=_CAST_DEFAULT_CLEARANCE,
        min=0.001,
        precision=3,
    )
    wall_thickness_mm: FloatProperty(
        name="Rail Width (mm)",
        default=_CAST_DEFAULT_WALL_THICKNESS,
        min=0.1,
        precision=3,
    )
    height_mm: FloatProperty(
        name="Basket Height (mm)",
        default=_CAST_DEFAULT_HEIGHT,
        min=0.1,
        precision=3,
    )
    rail_height_mm: FloatProperty(
        name="Rail Height (mm)",
        default=_CAST_DEFAULT_RAIL_HEIGHT,
        min=0.05,
        precision=3,
    )
    bottom_scale_percent: FloatProperty(
        name="Lower Gallery (%)",
        default=_CAST_DEFAULT_BOTTOM_SCALE,
        min=10.0,
        max=95.0,
        precision=1,
    )
    support_count: IntProperty(
        name="Support Count",
        default=_CAST_DEFAULT_SUPPORT_COUNT,
        min=3,
        max=16,
    )
    support_width_mm: FloatProperty(
        name="Support Width (mm)",
        default=_CAST_DEFAULT_SUPPORT_WIDTH,
        min=0.1,
        precision=3,
    )
    top_offset_mm: FloatProperty(
        name="Below Girdle (mm)",
        default=_CAST_DEFAULT_TOP_OFFSET,
        min=0.0,
        precision=3,
    )

    @classmethod
    def poll(cls, context):
        return any(
            obj.type == "MESH" and obj.parametric_gem.is_parametric
            for obj in context.selected_objects
        )

    def execute(self, context):
        global _CAST_UPDATE_GUARD

        gems = [
            obj
            for obj in context.selected_objects
            if obj.type == "MESH" and obj.parametric_gem.is_parametric
        ]
        casts: list[Object] = []
        created = 0

        _CAST_UPDATE_GUARD = True
        try:
            for gem in gems:
                linked = _linked_casts(gem)
                if linked:
                    cast = linked[0]
                else:
                    spec = _CUT_SPECS[gem.parametric_gem.cut]
                    mesh = bpy.data.meshes.new(f"Parametric {spec.mesh_name} Cast")
                    cast = bpy.data.objects.new(f"Parametric {spec.mesh_name} Cast", mesh)
                    collection = gem.users_collection[0] if gem.users_collection else context.collection
                    collection.objects.link(cast)
                    cast.parent = gem
                    cast.location = (0.0, 0.0, 0.0)
                    cast.rotation_euler = (0.0, 0.0, 0.0)
                    cast.scale = (1.0, 1.0, 1.0)
                    props = cast.parametric_cast
                    props.is_parametric = True
                    props.source_gem = gem
                    props.clearance_mm = self.clearance_mm
                    props.wall_thickness_mm = self.wall_thickness_mm
                    props.height_mm = self.height_mm
                    props.top_offset_mm = self.top_offset_mm
                    props.rail_height_mm = self.rail_height_mm
                    props.bottom_scale_percent = self.bottom_scale_percent
                    props.support_count = self.support_count
                    props.support_width_mm = self.support_width_mm
                    created += 1

                rebuild_cast_object(cast)
                casts.append(cast)
        finally:
            _CAST_UPDATE_GUARD = False

        for obj in context.selected_objects:
            obj.select_set(False)
        for cast in casts:
            cast.select_set(True)
        if casts:
            context.view_layer.objects.active = casts[0]

        context.view_layer.update()
        self.report({"INFO"}, f"Created {created}, updated {len(casts) - created} cast(s)")
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class OBJECT_OT_parametric_cast_rebuild(Operator):
    bl_idname = "object.parametric_cast_rebuild"
    bl_label = "Rebuild Parametric Cast"
    bl_description = "Rebuild the active cast from its stored parameters and linked gem"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == "MESH" and obj.parametric_cast.is_parametric

    def execute(self, context):
        rebuild_cast_object(context.object)
        context.view_layer.update()
        return {"FINISHED"}


class OBJECT_OT_parametric_cast_reset_defaults(Operator):
    bl_idname = "object.parametric_cast_reset_defaults"
    bl_label = "Default Cast"
    bl_description = "Restore the default open cast dimensions"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == "MESH" and obj.parametric_cast.is_parametric

    def execute(self, context):
        global _CAST_UPDATE_GUARD

        active = context.object
        targets = [active]
        if context.scene.parametric_gem_settings.affect_selected:
            targets.extend(
                obj
                for obj in context.selected_objects
                if obj is not active
                and obj.type == "MESH"
                and obj.parametric_cast.is_parametric
            )

        _CAST_UPDATE_GUARD = True
        try:
            for obj in targets:
                props = obj.parametric_cast
                props.clearance_mm = _CAST_DEFAULT_CLEARANCE
                props.wall_thickness_mm = _CAST_DEFAULT_WALL_THICKNESS
                props.height_mm = _CAST_DEFAULT_HEIGHT
                props.top_offset_mm = _CAST_DEFAULT_TOP_OFFSET
                props.rail_height_mm = _CAST_DEFAULT_RAIL_HEIGHT
                props.bottom_scale_percent = _CAST_DEFAULT_BOTTOM_SCALE
                props.support_count = _CAST_DEFAULT_SUPPORT_COUNT
                props.support_width_mm = _CAST_DEFAULT_SUPPORT_WIDTH
                rebuild_cast_object(obj)
        finally:
            _CAST_UPDATE_GUARD = False

        context.view_layer.update()
        return {"FINISHED"}


class OBJECT_OT_parametric_cast_bake(Operator):
    bl_idname = "object.parametric_cast_bake"
    bl_label = "Bake Parametric Cast"
    bl_description = "Keep the current mesh and remove parametric cast editing"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == "MESH" and obj.parametric_cast.is_parametric

    def execute(self, context):
        obj = context.object
        obj.parametric_cast.is_parametric = False
        obj.parametric_cast.source_gem = None
        if "parametric_cast_version" in obj:
            del obj["parametric_cast_version"]
        return {"FINISHED"}


class OBJECT_OT_parametric_gem_bake(Operator):
    bl_idname = "object.parametric_gem_bake"
    bl_label = "Bake Parametric Gem"
    bl_description = "Keep the current mesh and remove parametric editing"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == "MESH" and obj.parametric_gem.is_parametric

    def execute(self, context):
        obj = context.object
        obj.parametric_gem.is_parametric = False
        if "parametric_gem_version" in obj:
            del obj["parametric_gem_version"]
        return {"FINISHED"}


def _draw_cast_controls(layout, context) -> None:
    obj = context.object
    props = obj.parametric_cast
    gem = props.source_gem
    settings = context.scene.parametric_gem_settings

    layout.use_property_split = True
    layout.use_property_decorate = False
    layout.label(text=f"Source: {gem.name if gem is not None else 'Missing'}", icon="MESH_ICOSPHERE")
    layout.prop(props, "clearance_mm")
    layout.prop(props, "wall_thickness_mm")
    layout.prop(props, "height_mm")
    layout.prop(props, "top_offset_mm")
    layout.prop(props, "rail_height_mm")
    layout.prop(props, "bottom_scale_percent")
    layout.prop(props, "support_count")
    layout.prop(props, "support_width_mm")

    layout.separator()
    layout.prop(settings, "affect_selected")
    layout.operator("object.parametric_cast_reset_defaults", icon="LOOP_BACK")
    row = layout.row(align=True)
    row.operator("object.parametric_cast_rebuild", icon="FILE_REFRESH")
    row.operator("object.parametric_cast_bake", icon="CHECKMARK")


def _draw_cast_instance_controls(layout, context) -> None:
    props = context.object.parametric_cast_instance
    template = props.template_object
    gem = props.source_gem
    layout.label(text="Linked Cast Instance", icon="LINKED")
    layout.label(text=f"Template: {template.name if template is not None else 'Missing'}")
    layout.label(text=f"Gem: {gem.name if gem is not None else 'Missing'}")
    if template is not None and gem is not None:
        scale_x, scale_y, scale_z = _instance_scale_factors(template, gem)
        layout.label(text=f"Scale XYZ: {scale_x:.4f}, {scale_y:.4f}, {scale_z:.4f}")
    layout.operator("object.parametric_cast_instance_rebuild", icon="FILE_REFRESH")


def _draw_cast_template_controls(layout, context) -> None:
    props = context.object.parametric_cast_template
    settings = context.scene.parametric_gem_settings
    layout.label(text="Registered Cast Template", icon="MESH_GRID")
    layout.prop(props, "cut")
    layout.prop(props, "reference_width_mm")
    layout.prop(props, "reference_length_mm")
    layout.prop(props, "reference_depth_mm")
    layout.prop(settings, "cast_template")


def _draw_circle_size_controls(layout, context) -> None:
    obj = context.object
    props = obj.parametric_circle_size
    layout.use_property_split = True
    layout.use_property_decorate = False
    layout.label(text="Ring Size Curve", icon="CURVE_BEZCIRCLE")
    layout.prop(props, "diameter_mm")
    layout.prop(props, "circumference_mm")


def _draw_creation_controls(layout, context) -> None:
    settings = context.scene.parametric_gem_settings
    layout.separator()
    layout.operator("mesh.parametric_gem_add", icon="MESH_ICOSPHERE")
    cast_box = layout.box()
    cast_box.label(text="Linked Cast Instances", icon="LINKED")
    cast_box.prop(settings, "cast_template")
    cast_box.operator("object.parametric_cast_template_register", icon="BOOKMARKS")
    cast_box.operator("object.parametric_cast_instances_place", icon="DUPLICATE")


def _draw_gem_controls(layout, context) -> None:
    obj = context.object
    if obj is not None and obj.type == "CURVE":
        _draw_circle_size_controls(layout, context)
        _draw_creation_controls(layout, context)
        return
    if obj is not None and obj.type == "MESH" and obj.parametric_cast_instance.is_instance:
        _draw_cast_instance_controls(layout, context)
        _draw_creation_controls(layout, context)
        return
    if obj is not None and obj.type == "MESH" and obj.parametric_cast_template.is_template:
        _draw_cast_template_controls(layout, context)
        _draw_creation_controls(layout, context)
        return
    if obj is not None and obj.type == "MESH" and obj.parametric_cast.is_parametric:
        _draw_cast_controls(layout, context)
        _draw_creation_controls(layout, context)
        return

    if obj is None or obj.type != "MESH" or not obj.parametric_gem.is_parametric:
        _draw_creation_controls(layout, context)
        return

    props = obj.parametric_gem
    settings = context.scene.parametric_gem_settings

    layout.use_property_split = True
    layout.use_property_decorate = False
    layout.prop(props, "cut")
    layout.prop(props, "stone")

    dimensions = layout.column(heading="Dimensions")
    dimensions.prop(props, "length_mm")
    dimensions.prop(props, "width_mm")
    dimensions.prop(props, "depth_mm")

    proportions = layout.column(heading="Height / Width")
    proportions.prop(props, "girdle_percent")
    proportions.prop(props, "crown_percent")
    proportions.prop(props, "pavilion_percent")

    total_percent = props.girdle_percent + props.crown_percent + props.pavilion_percent
    total_depth = props.width_mm * total_percent / 100.0
    layout.label(text=f"Total depth: {total_depth:.3f} mm ({total_percent:.2f}%)")

    layout.separator()
    layout.prop(settings, "affect_selected")
    layout.operator("object.parametric_gem_copy_to_selected", icon="PASTEDOWN")
    layout.operator("object.parametric_gem_reset_defaults", icon="LOOP_BACK")

    row = layout.row(align=True)
    row.operator("object.parametric_gem_rebuild", icon="FILE_REFRESH")
    row.operator("object.parametric_gem_bake", icon="CHECKMARK")

    _draw_creation_controls(layout, context)


class VIEW3D_PT_parametric_gems(Panel):
    bl_label = "Parametric Gems"
    bl_idname = "VIEW3D_PT_parametric_gems"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Jewelry"

    def draw(self, context):
        _draw_gem_controls(self.layout, context)


class OBJECT_PT_parametric_gems(Panel):
    bl_label = "Parametric Gem"
    bl_idname = "OBJECT_PT_parametric_gems"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    def draw(self, context):
        _draw_gem_controls(self.layout, context)


def _menu_add(self: Menu, context: bpy.types.Context) -> None:
    self.layout.operator(MESH_OT_parametric_gem_add.bl_idname, icon="MESH_ICOSPHERE")


_CLASSES = (
    ParametricCircleSizeProperties,
    ParametricGemProperties,
    ParametricCastProperties,
    ParametricCastTemplateProperties,
    ParametricCastInstanceProperties,
    ParametricGemSettings,
    MESH_OT_parametric_gem_add,
    OBJECT_OT_parametric_gem_rebuild,
    OBJECT_OT_parametric_gem_reset_defaults,
    OBJECT_OT_parametric_gem_copy_to_selected,
    OBJECT_OT_parametric_cast_template_register,
    OBJECT_OT_parametric_cast_instances_place,
    OBJECT_OT_parametric_cast_instance_rebuild,
    OBJECT_OT_parametric_cast_add,
    OBJECT_OT_parametric_cast_rebuild,
    OBJECT_OT_parametric_cast_reset_defaults,
    OBJECT_OT_parametric_cast_bake,
    OBJECT_OT_parametric_gem_bake,
    VIEW3D_PT_parametric_gems,
    OBJECT_PT_parametric_gems,
)


def register() -> None:
    for cls in _CLASSES:
        bpy.utils.register_class(cls)

    bpy.types.Object.parametric_gem = PointerProperty(type=ParametricGemProperties)
    bpy.types.Object.parametric_circle_size = PointerProperty(type=ParametricCircleSizeProperties)
    bpy.types.Object.parametric_cast = PointerProperty(type=ParametricCastProperties)
    bpy.types.Object.parametric_cast_template = PointerProperty(type=ParametricCastTemplateProperties)
    bpy.types.Object.parametric_cast_instance = PointerProperty(type=ParametricCastInstanceProperties)
    bpy.types.Scene.parametric_gem_settings = PointerProperty(type=ParametricGemSettings)
    bpy.types.VIEW3D_MT_mesh_add.append(_menu_add)


def unregister() -> None:
    bpy.types.VIEW3D_MT_mesh_add.remove(_menu_add)
    del bpy.types.Scene.parametric_gem_settings
    del bpy.types.Object.parametric_cast_instance
    del bpy.types.Object.parametric_cast_template
    del bpy.types.Object.parametric_cast
    del bpy.types.Object.parametric_circle_size
    del bpy.types.Object.parametric_gem

    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)

    _TEMPLATE_CACHE.clear()


if __name__ == "__main__":
    register()
