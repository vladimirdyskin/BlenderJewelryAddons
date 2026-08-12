from __future__ import annotations

import importlib
import os
import sys
from math import pi
from pathlib import Path

import bmesh
import bpy


if os.environ.get("PARAMETRIC_GEMS_TEST_INSTALLED") == "1":
    parametric_gems = importlib.import_module("bl_ext.user_default.parametric_gems")
else:
    ADDON_DIR = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(ADDON_DIR.parent))
    parametric_gems = importlib.import_module("parametric_gems")


def assert_close(actual: float, expected: float, tolerance: float = 1e-6) -> None:
    if abs(actual - expected) > tolerance:
        raise AssertionError(f"Expected {expected}, got {actual}")


def main() -> None:
    parametric_gems.register()

    icon_items = bpy.types.UILayout.bl_rna.functions["operator"].parameters["icon"].enum_items
    if "LOOP_BACK" not in icon_items:
        raise AssertionError("Default button icon is unavailable")
    if "CURVE_BEZCIRCLE" not in icon_items:
        raise AssertionError("Circle size panel icon is unavailable")

    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0

    result = bpy.ops.mesh.parametric_gem_add(
        "EXEC_DEFAULT",
        length_mm=12.0,
        width_mm=6.0,
        girdle_percent=4.0,
        crown_percent=13.0,
        pavilion_percent=40.0,
        stone="DIAMOND",
    )
    if result != {"FINISHED"}:
        raise AssertionError(f"Create operator failed: {result}")

    first = bpy.context.object
    assert first is not None
    assert first.parametric_gem.is_parametric
    assert first["gem"]["cut"] == "MARQUISE"
    assert first["gem"]["stone"] == "DIAMOND"
    assert len(first.data.vertices) == 87
    assert len(first.data.polygons) == 87
    assert_close(first.dimensions.x, 6.0)
    assert_close(first.dimensions.y, 12.0)
    assert_close(first.dimensions.z, 3.42)
    assert_close(first.parametric_gem.depth_mm, 3.42)

    second = first.copy()
    second.data = first.data.copy()
    scene.collection.objects.link(second)
    second.select_set(True)
    first.select_set(True)
    bpy.context.view_layer.objects.active = first

    scene.parametric_gem_settings.affect_selected = True
    first.parametric_gem.width_mm = 7.0

    assert_close(second.parametric_gem.width_mm, 7.0)
    assert_close(first.dimensions.x, 7.0)
    assert_close(second.dimensions.x, 7.0)

    first.parametric_gem.depth_mm = 4.2
    assert_close(first.parametric_gem.depth_mm, 4.2)
    assert_close(second.parametric_gem.depth_mm, 4.2)
    assert_close(first.dimensions.z, 4.2)
    assert_close(second.dimensions.z, 4.2)

    result = bpy.ops.object.parametric_gem_copy_to_selected()
    if result != {"FINISHED"}:
        raise AssertionError(f"Batch copy operator failed: {result}")

    result = bpy.ops.object.parametric_gem_bake()
    if result != {"FINISHED"}:
        raise AssertionError(f"Bake operator failed: {result}")
    if first.parametric_gem.is_parametric:
        raise AssertionError("Bake did not disable parametric editing")
    if "gem" not in first:
        raise AssertionError("Bake removed JewelCraft metadata")

    for cut, spec in parametric_gems._CUT_SPECS.items():
        length = 10.0
        width = length * spec.base_width / spec.base_length
        result = bpy.ops.mesh.parametric_gem_add(
            "EXEC_DEFAULT",
            cut=cut,
            length_mm=length,
            width_mm=width,
            girdle_percent=spec.girdle_percent,
            crown_percent=spec.crown_percent,
            pavilion_percent=spec.pavilion_percent,
        )
        if result != {"FINISHED"}:
            raise AssertionError(f"Create operator failed for {cut}: {result}")

        gem = bpy.context.object
        source_vertices, source_faces = parametric_gems._load_template(spec.mesh_name)
        expected_depth = width * (
            spec.girdle_percent + spec.crown_percent + spec.pavilion_percent
        ) / 100.0

        if gem["gem"]["cut"] != cut:
            raise AssertionError(f"Wrong JewelCraft cut metadata for {cut}")
        if len(gem.data.vertices) != len(source_vertices):
            raise AssertionError(f"Wrong vertex count for {cut}")
        if len(gem.data.polygons) != len(source_faces):
            raise AssertionError(f"Wrong face count for {cut}")
        assert_close(gem.dimensions.x, width, tolerance=1e-5)
        assert_close(gem.dimensions.y, length, tolerance=1e-5)
        assert_close(gem.dimensions.z, expected_depth, tolerance=1e-5)

        cast_result = bpy.ops.object.parametric_cast_add("EXEC_DEFAULT")
        if cast_result != {"FINISHED"}:
            raise AssertionError(f"Cast operator failed for {cut}: {cast_result}")

        cast = bpy.context.object
        if cast is None or not cast.parametric_cast.is_parametric:
            raise AssertionError(f"Cast was not created for {cut}")
        if cast.parametric_cast.source_gem is not gem or cast.parent is not gem:
            raise AssertionError(f"Cast link is invalid for {cut}")
        assert_close(cast.dimensions.z, 1.5, tolerance=1e-5)
        if cast.dimensions.x <= gem.dimensions.x or cast.dimensions.y <= gem.dimensions.y:
            raise AssertionError(f"Cast does not surround the gem for {cut}")

        bm = bmesh.new()
        bm.from_mesh(cast.data)
        if any(not edge.is_manifold for edge in bm.edges):
            bm.free()
            raise AssertionError(f"Cast is non-manifold for {cut}")
        if abs(bm.calc_volume(signed=True)) <= 1e-6:
            bm.free()
            raise AssertionError(f"Cast has zero volume for {cut}")
        bm.verts.ensure_lookup_table()
        pending = [bm.verts[0]]
        connected = {bm.verts[0]}
        while pending:
            vertex = pending.pop()
            for edge in vertex.link_edges:
                other = edge.other_vert(vertex)
                if other not in connected:
                    connected.add(other)
                    pending.append(other)
        if len(connected) != len(bm.verts):
            bm.free()
            raise AssertionError(f"Cast has disconnected components for {cut}")
        bm.free()

        original_cast_width = cast.dimensions.x
        gem.parametric_gem.width_mm *= 1.05
        if cast.dimensions.x <= original_cast_width:
            raise AssertionError(f"Linked cast did not follow gem dimensions for {cut}")

    gem.parametric_gem.cut = "ROUND"
    if gem["gem"]["cut"] != "ROUND" or len(gem.data.vertices) != 153:
        raise AssertionError("Changing cut did not rebuild the gem as Round")

    bpy.ops.mesh.parametric_gem_add(
        "EXEC_DEFAULT",
        cut="OVAL",
        length_mm=10.0,
        width_mm=5.0,
        girdle_percent=8.0,
        crown_percent=15.0,
        pavilion_percent=35.0,
    )
    reset_gem = bpy.context.object
    reset_gem.parametric_gem.cut = "ROUND"
    assert_close(reset_gem.dimensions.x, 5.0)
    assert_close(reset_gem.dimensions.y, 10.0)
    assert_close(reset_gem.parametric_gem.girdle_percent, 8.0)

    result = bpy.ops.object.parametric_gem_reset_defaults()
    if result != {"FINISHED"}:
        raise AssertionError(f"Default operator failed: {result}")
    round_spec = parametric_gems._CUT_SPECS["ROUND"]
    assert_close(reset_gem.dimensions.x, 10.0)
    assert_close(reset_gem.dimensions.y, 10.0)
    assert_close(reset_gem.parametric_gem.girdle_percent, round_spec.girdle_percent, tolerance=1e-5)
    assert_close(reset_gem.parametric_gem.crown_percent, round_spec.crown_percent, tolerance=1e-5)
    assert_close(reset_gem.parametric_gem.pavilion_percent, round_spec.pavilion_percent, tolerance=1e-5)

    marquise_spec = parametric_gems._CUT_SPECS["MARQUISE"]
    bpy.ops.mesh.parametric_gem_add(
        "EXEC_DEFAULT",
        cut="MARQUISE",
        length_mm=10.0,
        width_mm=5.0,
        girdle_percent=marquise_spec.girdle_percent,
        crown_percent=marquise_spec.crown_percent,
        pavilion_percent=marquise_spec.pavilion_percent,
    )
    reference_gem = bpy.context.object
    template_mesh = bpy.data.meshes.new("Cast Template Mesh")
    template_mesh.from_pydata(
        [
            (-3.0, -5.5, -2.0),
            (3.0, -5.5, -2.0),
            (3.0, 5.5, -2.0),
            (-3.0, 5.5, -2.0),
            (-3.0, -5.5, 0.0),
            (3.0, -5.5, 0.0),
            (3.0, 5.5, 0.0),
            (-3.0, 5.5, 0.0),
        ],
        [],
        [
            (0, 3, 2, 1),
            (4, 5, 6, 7),
            (0, 1, 5, 4),
            (1, 2, 6, 5),
            (2, 3, 7, 6),
            (3, 0, 4, 7),
        ],
    )
    template = bpy.data.objects.new("Marquise Cast Template", template_mesh)
    scene.collection.objects.link(template)
    template.select_set(True)
    reference_gem.select_set(True)
    bpy.context.view_layer.objects.active = reference_gem

    register_result = bpy.ops.object.parametric_cast_template_register()
    if register_result != {"FINISHED"}:
        raise AssertionError(f"Cast template registration failed: {register_result}")
    if not template.parametric_cast_template.is_template:
        raise AssertionError("Cast template flag was not set")
    if scene.parametric_gem_settings.cast_template is not template:
        raise AssertionError("Registered cast template was not activated")
    assert_close(template.parametric_cast_template.reference_width_mm, 5.0)
    assert_close(template.parametric_cast_template.reference_length_mm, 10.0)

    bpy.ops.mesh.parametric_gem_add(
        "EXEC_DEFAULT",
        cut="MARQUISE",
        length_mm=12.0,
        width_mm=6.0,
        girdle_percent=marquise_spec.girdle_percent,
        crown_percent=marquise_spec.crown_percent,
        pavilion_percent=marquise_spec.pavilion_percent,
    )
    target_large = bpy.context.object
    bpy.ops.mesh.parametric_gem_add(
        "EXEC_DEFAULT",
        cut="MARQUISE",
        length_mm=8.0,
        width_mm=4.0,
        girdle_percent=marquise_spec.girdle_percent,
        crown_percent=marquise_spec.crown_percent,
        pavilion_percent=marquise_spec.pavilion_percent,
    )
    target_small = bpy.context.object
    target_large.select_set(True)

    place_result = bpy.ops.object.parametric_cast_instances_place()
    if place_result != {"FINISHED"}:
        raise AssertionError(f"Cast instance placement failed: {place_result}")
    linked_instances = [
        obj
        for obj in scene.objects
        if getattr(obj, "parametric_cast_instance", None) is not None
        and obj.parametric_cast_instance.is_instance
    ]
    if len(linked_instances) != 2:
        raise AssertionError(f"Expected two linked cast instances, got {len(linked_instances)}")

    large_instance = next(
        obj for obj in linked_instances if obj.parametric_cast_instance.source_gem is target_large
    )
    small_instance = next(
        obj for obj in linked_instances if obj.parametric_cast_instance.source_gem is target_small
    )
    if large_instance.data is not template.data or small_instance.data is not template.data:
        raise AssertionError("Cast instances do not share the template mesh")
    assert_close(large_instance.dimensions.x, template.dimensions.x * 1.2, tolerance=1e-5)
    assert_close(large_instance.dimensions.y, template.dimensions.y * 1.2, tolerance=1e-5)
    assert_close(large_instance.dimensions.z, template.dimensions.z * 1.2, tolerance=1e-5)
    assert_close(small_instance.dimensions.x, template.dimensions.x * 0.8, tolerance=1e-5)
    assert_close(small_instance.dimensions.y, template.dimensions.y * 0.8, tolerance=1e-5)
    assert_close(small_instance.dimensions.z, template.dimensions.z * 0.8, tolerance=1e-5)

    target_large.parametric_gem.width_mm = 7.0
    assert_close(large_instance.dimensions.x, template.dimensions.x * 1.4, tolerance=1e-5)
    assert_close(large_instance.dimensions.y, template.dimensions.y * 1.2, tolerance=1e-5)
    assert_close(
        large_instance.dimensions.z,
        template.dimensions.z * target_large.parametric_gem.depth_mm / reference_gem.parametric_gem.depth_mm,
        tolerance=1e-5,
    )

    bpy.ops.curve.primitive_bezier_circle_add(radius=8.5, location=(3.0, -2.0, 1.0))
    circle = bpy.context.object
    circle.rotation_euler = (pi * 0.5, 0.0, 0.0)
    circle.scale = (1.2, 1.2, 1.2)
    bpy.context.view_layer.update()
    original_location = circle.location.copy()
    original_rotation = circle.rotation_euler.copy()
    original_scale = circle.scale.copy()
    assert_close(circle.parametric_circle_size.diameter_mm, 20.4, tolerance=1e-5)
    assert_close(circle.parametric_circle_size.circumference_mm, 10.2 * 2.0 * pi, tolerance=1e-5)

    circle.parametric_circle_size.diameter_mm = 24.0
    assert_close(circle.parametric_circle_size.diameter_mm, 24.0, tolerance=1e-5)
    assert_close(circle.parametric_circle_size.circumference_mm, 24.0 * pi, tolerance=1e-5)
    if circle.location != original_location or circle.rotation_euler != original_rotation or circle.scale != original_scale:
        raise AssertionError("Circle resize changed the object transform")

    circle.parametric_circle_size.circumference_mm = 50.0
    assert_close(circle.parametric_circle_size.circumference_mm, 50.0, tolerance=1e-5)
    assert_close(circle.parametric_circle_size.diameter_mm, 50.0 / pi, tolerance=1e-5)

    parametric_gems.unregister()
    if hasattr(bpy.types.Object, "parametric_gem"):
        raise AssertionError("Unregister left Object.parametric_gem behind")
    if hasattr(bpy.types.Object, "parametric_cast_template"):
        raise AssertionError("Unregister left Object.parametric_cast_template behind")
    if hasattr(bpy.types.Object, "parametric_cast_instance"):
        raise AssertionError("Unregister left Object.parametric_cast_instance behind")
    if hasattr(bpy.types.Object, "parametric_circle_size"):
        raise AssertionError("Unregister left Object.parametric_circle_size behind")

    print("Parametric Gems smoke test passed")


if __name__ == "__main__":
    main()
