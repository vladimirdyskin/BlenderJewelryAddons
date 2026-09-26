# SPDX-License-Identifier: GPL-3.0-or-later

"""Deterministic, surface-following packing in world millimetres."""

from collections import defaultdict, deque
from dataclasses import dataclass
from math import ceil, cos, floor, pi, sin

from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree


MASK_NAME = "PaveMask"
MAX_SEED_SAMPLES = 250_000


@dataclass
class Sample:
    point: Vector
    normal: Vector
    weight: float


@dataclass
class Placement:
    surface_point: Vector
    center: Vector
    normal: Vector
    tangent: Vector


@dataclass
class Layout:
    placements: list
    pitch: float
    limited: bool


def tangent_axis(normal, preferred):
    tangent = preferred - normal * preferred.dot(normal)
    if tangent.length_squared < 1e-10:
        axis = min((Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))),
                   key=lambda value: abs(value.dot(normal)))
        tangent = axis - normal * axis.dot(normal)
    return tangent.normalized()


def _segment_distance_squared(point, start, end):
    edge = end - start
    if edge.length_squared < 1e-20:
        return (point - start).length_squared
    factor = max(0.0, min(1.0, (point - start).dot(edge) / edge.length_squared))
    return (point - start - edge * factor).length_squared


def _clip_triangle(points, weights, threshold):
    result = []
    for index in range(3):
        a, b = points[index - 1], points[index]
        wa, wb = weights[index - 1], weights[index]
        if (wa >= threshold) != (wb >= threshold):
            result.append(a.lerp(b, (threshold - wa) / (wb - wa)))
        if wb >= threshold:
            result.append(b)
    return result


class Surface:
    """An evaluated surface, including the piecewise-linear mask boundary."""

    def __init__(self, obj, depsgraph, threshold):
        group = obj.vertex_groups.get(MASK_NAME)
        if group is None:
            raise ValueError("Create a PaveMask with Paint Mask or Fill Surface first")
        if abs(obj.matrix_world.determinant()) < 1e-12:
            raise ValueError("The surface has a zero scale")
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
        try:
            mesh.calc_loop_triangles()
            if not mesh.loop_triangles:
                raise ValueError("The surface has no faces")
            matrix = obj.matrix_world
            normal_matrix = matrix.to_3x3().inverted().transposed()
            self.vertices = [matrix @ v.co for v in mesh.vertices]
            self.weights = [next((g.weight for g in v.groups if g.group == group.index), 0.0)
                            for v in mesh.vertices]
            self.triangles = [tuple(t.vertices) for t in mesh.loop_triangles]
            self.normals = [tuple((normal_matrix @ mesh.corner_normals[i].vector).normalized()
                                  for i in t.loops) for t in mesh.loop_triangles]
        finally:
            evaluated.to_mesh_clear()
        self.threshold = threshold
        self.bvh = BVHTree.FromPolygons(self.vertices, self.triangles, all_triangles=True)
        self.seed_triangles = []
        self.boundaries = []
        edge_counts = defaultdict(int)
        for triangle in self.triangles:
            points = [self.vertices[i] for i in triangle]
            weights = [self.weights[i] for i in triangle]
            clipped = _clip_triangle(points, weights, threshold)
            for index in range(1, len(clipped) - 1):
                a, b, c = clipped[0], clipped[index], clipped[index + 1]
                if (b - a).cross(c - a).length_squared > 1e-20:
                    self.seed_triangles.append((a, b, c))
            crossings = []
            for index in range(3):
                a, b = triangle[index - 1], triangle[index]
                edge_counts[tuple(sorted((a, b)))] += 1
                wa, wb = self.weights[a], self.weights[b]
                if (wa >= threshold) != (wb >= threshold):
                    crossings.append(self.vertices[a].lerp(self.vertices[b],
                                                          (threshold - wa) / (wb - wa)))
            if len(crossings) == 2:
                self.boundaries.append(tuple(crossings))
        if any(count > 2 for count in edge_counts.values()):
            raise ValueError("The surface has non-manifold edges; repair them before packing")
        for (a, b), count in edge_counts.items():
            if count != 1:
                continue
            pa, pb = self.vertices[a], self.vertices[b]
            wa, wb = self.weights[a], self.weights[b]
            if max(wa, wb) < threshold:
                continue
            if min(wa, wb) < threshold:
                crossing = pa.lerp(pb, (threshold - wa) / (wb - wa))
                pa, pb = (pa, crossing) if wa >= threshold else (crossing, pb)
            self.boundaries.append((pa, pb))
        self.boundary_tree = KDTree(len(self.boundaries)) if self.boundaries else None
        self.max_half_edge = 0.0
        for index, (a, b) in enumerate(self.boundaries):
            self.boundary_tree.insert((a + b) * 0.5, index)
            self.max_half_edge = max(self.max_half_edge, (b - a).length * 0.5)
        if self.boundary_tree:
            self.boundary_tree.balance()

    def sample(self, point):
        position, face_normal, index, _distance = self.bvh.find_nearest(point)
        if index is None:
            return None
        indices = self.triangles[index]
        a, b, c = (self.vertices[i] for i in indices)
        v0, v1, v2 = b - a, c - a, position - a
        d00, d01, d11 = v0.dot(v0), v0.dot(v1), v1.dot(v1)
        denominator = d00 * d11 - d01 * d01
        if abs(denominator) < 1e-20:
            return None
        u = (d11 * v2.dot(v0) - d01 * v2.dot(v1)) / denominator
        v = (d00 * v2.dot(v1) - d01 * v2.dot(v0)) / denominator
        factors = (1.0 - u - v, u, v)
        normal = sum((n * f for n, f in zip(self.normals[index], factors)), Vector())
        normal = normal.normalized() if normal.length_squared > 1e-12 else face_normal
        weight = sum(self.weights[i] * f for i, f in zip(indices, factors))
        return Sample(position, normal, weight)

    def fits(self, sample, clearance):
        if sample is None or sample.weight < self.threshold - 1e-6:
            return False
        if self.boundary_tree:
            for _center, index, _distance in self.boundary_tree.find_range(
                    sample.point, clearance + self.max_half_edge):
                if _segment_distance_squared(sample.point, *self.boundaries[index]) < clearance ** 2:
                    return False
        return True

    def seeds(self, pitch, anchor):
        yield anchor
        ordered = sorted(self.seed_triangles,
                         key=lambda tri: ((tri[0] + tri[1] + tri[2]) / 3.0 - anchor).length_squared)
        samples = 0
        for a, b, c in ordered:
            divisions = max(1, ceil(max((b - a).length, (c - a).length, (c - b).length)
                                    / (pitch * 0.75)))
            samples += divisions * (divisions + 1) // 2
            if samples > MAX_SEED_SAMPLES:
                raise ValueError("The layout is too large; use a larger diameter or a smaller mask")
            for i in range(divisions):
                for j in range(divisions - i):
                    yield a + (b - a) * ((i + 1.0 / 3.0) / divisions) + (c - a) * ((j + 1.0 / 3.0) / divisions)

    def advance(self, origin, tangent, angle, pitch, offset):
        arc = pitch
        origin_center = origin.point + origin.normal * offset
        for _attempt in range(5):
            current, axis = origin, tangent
            step = arc / 4.0
            for _segment in range(4):
                direction = axis * cos(angle) + current.normal.cross(axis) * sin(angle)
                projected = current.point + direction * step
                next_sample = self.sample(projected)
                if next_sample is None or next_sample.normal.dot(current.normal) < 0.5:
                    return None
                displacement = next_sample.point - current.point
                if displacement.dot(direction) < step * 0.2 or displacement.length > step * 1.5:
                    return None
                axis = current.normal.rotation_difference(next_sample.normal) @ axis
                axis = tangent_axis(next_sample.normal, axis)
                current = next_sample
            distance = (current.point + current.normal * offset - origin_center).length
            if abs(distance - pitch) < pitch * 0.00002:
                return current, axis
            if distance < pitch * 0.2:
                return None
            arc *= pitch / distance
            if arc > pitch * 3.0:
                return None
        return None


class _Spacing:
    def __init__(self, pitch):
        self.pitch = pitch
        self.cells = defaultdict(list)

    def key(self, center):
        return tuple(floor(value / self.pitch) for value in center)

    def neighbors(self, center):
        x, y, z = self.key(center)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    yield from self.cells.get((x + dx, y + dy, z + dz), ())

    def fits(self, center):
        return all((center - other).length_squared >= self.pitch ** 2
                   for other in self.neighbors(center))

    def adjust(self, surface, sample, tangent, offset):
        """Allow small row corrections where curvature closes a lattice loop."""
        original = sample
        for _iteration in range(24):
            center = sample.point + sample.normal * offset
            force = Vector()
            overlaps = False
            for other in self.neighbors(center):
                delta = center - other
                distance = delta.length
                if distance < self.pitch * 0.7:
                    return None
                if distance < self.pitch:
                    overlaps = True
                    force += delta * ((self.pitch * 1.0002 - distance) / distance)
            if not overlaps:
                axis = original.normal.rotation_difference(sample.normal) @ tangent
                return sample, tangent_axis(sample.normal, axis)
            force -= sample.normal * force.dot(sample.normal)
            projected = surface.sample(sample.point + force * 1.2)
            if (projected is None or projected.normal.dot(original.normal) < 0.8
                    or (projected.point - original.point).length > self.pitch * 0.35):
                return None
            sample = projected
        return None

    def add(self, center):
        self.cells[self.key(center)].append(center)


def pack(surface, *, diameter, envelope_radius, gap, border, offset, angle,
         preferred_axis, anchor, max_stones):
    """Grow hexagonal fronts, then seed remaining islands and curvature seams.

    Spherical envelopes conservatively separate the complete source gem, even
    on concave surfaces. Boundary distance also includes open mesh edges and
    small holes, which point-only or circumference-only mask tests can miss.
    """
    pitch = max(diameter, envelope_radius * 2.0) + gap
    spacing = _Spacing(pitch)
    placements = []
    frontier = deque()
    clearance = diameter * 0.5 + border

    def accept(sample, tangent):
        if sample is None:
            return False
        center = sample.point + sample.normal * offset
        if not spacing.fits(center):
            adjusted = spacing.adjust(surface, sample, tangent, offset)
            if adjusted is None:
                return False
            sample, tangent = adjusted
            center = sample.point + sample.normal * offset
        if not surface.fits(sample, clearance):
            return False
        spacing.add(center)
        placements.append(Placement(sample.point, center, sample.normal, tangent))
        frontier.append((sample, tangent))
        return True

    for seed in surface.seeds(pitch, anchor):
        sample = surface.sample(seed)
        if sample is None:
            continue
        axis = tangent_axis(sample.normal, preferred_axis)
        axis = axis * cos(angle) + sample.normal.cross(axis) * sin(angle)
        if not accept(sample, axis):
            continue
        while frontier:
            if len(placements) >= max_stones:
                return Layout(placements, pitch, True)
            current, tangent = frontier.popleft()
            for direction in range(6):
                candidate = surface.advance(current, tangent, direction * pi / 3.0,
                                            pitch * 1.0001, offset)
                if candidate is not None:
                    accept(*candidate)
                if len(placements) >= max_stones:
                    return Layout(placements, pitch, True)
    return Layout(placements, pitch, False)
