from __future__ import annotations

import json

import bpy


def rounded_xy(vertex) -> tuple[float, float]:
    return round(vertex.co.x, 6), round(vertex.co.y, 6)


def main() -> None:
    analysis = []
    for obj in sorted((obj for obj in bpy.data.objects if obj.type == "MESH"), key=lambda item: item.name):
        mesh = obj.data
        groups: dict[tuple[float, float], list] = {}
        for vertex in mesh.vertices:
            groups.setdefault(rounded_xy(vertex), []).append(vertex)

        lower_indices: set[int] = set()
        upper_indices: set[int] = set()
        for vertices in groups.values():
            zero_vertices = [vertex for vertex in vertices if abs(vertex.co.z) <= 1e-5]
            positive_vertices = [vertex for vertex in vertices if vertex.co.z > 1e-5]
            if not zero_vertices or not positive_vertices:
                continue
            lower_indices.update(vertex.index for vertex in zero_vertices)
            upper_indices.update(vertex.index for vertex in positive_vertices)

        upper_z = [mesh.vertices[index].co.z for index in upper_indices]
        crown_z = [
            vertex.co.z
            for vertex in mesh.vertices
            if vertex.co.z > 1e-5 and vertex.index not in upper_indices
        ]
        negative_z = [vertex.co.z for vertex in mesh.vertices if vertex.co.z < -1e-5]

        analysis.append({
            "name": obj.name,
            "dimensions": [round(value, 9) for value in obj.dimensions],
            "vertices": len(mesh.vertices),
            "faces": len(mesh.polygons),
            "lower_girdle_count": len(lower_indices),
            "upper_girdle_count": len(upper_indices),
            "upper_girdle_min": round(min(upper_z), 9) if upper_z else None,
            "upper_girdle_max": round(max(upper_z), 9) if upper_z else None,
            "crown_min": round(min(crown_z), 9) if crown_z else None,
            "crown_max": round(max(crown_z), 9) if crown_z else None,
            "pavilion_bottom": round(min(negative_z), 9) if negative_z else None,
            "upper_indices": sorted(upper_indices),
            "vertex_groups": [group.name for group in obj.vertex_groups],
            "attributes": [
                [attribute.name, attribute.domain, attribute.data_type]
                for attribute in mesh.attributes
            ],
            "object_properties": list(obj.keys()),
            "mesh_properties": list(mesh.keys()),
            "z_histogram": (
                [
                    [z_value, sum(1 for vertex in mesh.vertices if round(vertex.co.z, 6) == z_value)]
                    for z_value in sorted({round(vertex.co.z, 6) for vertex in mesh.vertices})
                ]
                if obj.name == "Cushion"
                else None
            ),
        })

    print("TEMPLATE_ANALYSIS=" + json.dumps(analysis, separators=(",", ":")))


if __name__ == "__main__":
    main()
