# SPDX-License-Identifier: GPL-3.0-or-later

"""Управляющая петля рундиста камня для каста под Subdivision Surface.

Петля — замкнутый контур в плоскости XY камня из точек (x, y, corner) против часовой
стрелки при взгляде с +Z. Острая вершина (corner, crease 1) на шаге подразделения стоит
на месте, гладкая переходит в (P[i-1] + 6 P[i] + P[i+1]) / 8, новая точка ребра — середина;
предел гладкой вершины — (P[i-1] + 4 P[i] + P[i+1]) / 6. Значит предел петли — равномерный
кубический B-сплайн, а у острой вершины C с соседом P — фантомная точка 2C - P: кривая
проходит через C по касательной к CP и делает в C излом.

Чистая математика без регистрации в Blender.
"""

from __future__ import annotations

from math import atan2, ceil, floor, hypot, inf, pi, radians

# Огранка: (острых углов — самые крутые повороты контура рундиста; гладких точек на участке
# между соседними углами, без углов — во всей петле; участок-отрезок остаётся без точек).
# По ним из шаблонов parametric_gems/assets/gems.blend (копия JewelCraft 3.0.0) посчитаны
# CUT_LOOPS: tools/test_gem_outline.py -- --table
CUT_SPECS = {
    "ROUND": (0, 8),
    "OVAL": (0, 8),
    "CUSHION": (0, 12),
    "PEAR": (1, 5),
    "MARQUISE": (2, 3),
    "PRINCESS": (4, 0),
    "BAGUETTE": (4, 0),
    "SQUARE": (4, 0),
    "EMERALD": (8, 0),
    "ASSCHER": (8, 0),
    "RADIANT": (8, 0),
    "FLANDERS": (8, 0),
    "OCTAGON": (8, 0),
    "HEART": (2, 4),
    "TRILLION": (3, 2),
    "TRILLIANT": (9, 1),
    "TRIANGLE": (3, 0),
}

# Петли огранок: габарит XY шаблона (x0, y0, x1, y1) и точки (x, y, corner) в его координатах.
CUT_LOOPS = {
    "ROUND": ((-0.5, -0.5, 0.5, 0.5), (
        (0.554107, 0.0, False),
        (0.391813, 0.391813, False),
        (0.0, 0.554107, False),
        (-0.391813, 0.391813, False),
        (-0.554107, 0.0, False),
        (-0.391813, -0.391813, False),
        (0.0, -0.554107, False),
        (0.391813, -0.391813, False),
    )),
    "OVAL": ((-0.3125, -0.5, 0.3125, 0.5), (
        (0.349063, 0.0, False),
        (0.238796, 0.399605, False),
        (0.0, 0.548431, False),
        (-0.238796, 0.399605, False),
        (-0.349063, 0.0, False),
        (-0.238796, -0.399605, False),
        (0.0, -0.548431, False),
        (0.238796, -0.399605, False),
    )),
    "CUSHION": ((-0.5, -0.5, 0.5, 0.5), (
        (0.530528, 0.0, False),
        (0.443796, 0.352299, False),
        (0.352299, 0.443796, False),
        (0.0, 0.530528, False),
        (-0.352299, 0.443796, False),
        (-0.443796, 0.352299, False),
        (-0.530528, 0.0, False),
        (-0.443796, -0.352299, False),
        (-0.352299, -0.443796, False),
        (0.0, -0.530528, False),
        (0.352299, -0.443796, False),
        (0.443796, -0.352299, False),
    )),
    "PEAR": ((-0.3125, -0.5, 0.3125, 0.5), (
        (0.389098, 0.336715, False),
        (0.0, 0.579142, False),
        (-0.389098, 0.336715, False),
        (-0.234733, -0.271945, False),
        (0.0, -0.5, True),
        (0.234733, -0.271945, False),
    )),
    "MARQUISE": ((-0.25, -0.5, 0.25, 0.5), (
        (0.290261, 0.0, False),
        (0.170485, 0.348656, False),
        (0.0, 0.5, True),
        (-0.170485, 0.348656, False),
        (-0.290261, 0.0, False),
        (-0.170485, -0.348656, False),
        (0.0, -0.5, True),
        (0.170485, -0.348656, False),
    )),
    "PRINCESS": ((-0.5, -0.5, 0.5, 0.5), (
        (0.5, 0.5, True),
        (-0.5, 0.5, True),
        (-0.5, -0.5, True),
        (0.5, -0.5, True),
    )),
    "BAGUETTE": ((-0.25, -0.5, 0.25, 0.5), (
        (0.25, 0.5, True),
        (-0.25, 0.5, True),
        (-0.25, -0.5, True),
        (0.25, -0.5, True),
    )),
    "SQUARE": ((-0.5, -0.5, 0.5, 0.5), (
        (0.5, 0.5, True),
        (-0.5, 0.5, True),
        (-0.5, -0.5, True),
        (0.5, -0.5, True),
    )),
    "EMERALD": ((-0.357143, -0.5, 0.357143, 0.5), (
        (0.357143, 0.406857, True),
        (0.264, 0.5, True),
        (-0.264, 0.5, True),
        (-0.357143, 0.406857, True),
        (-0.357143, -0.406857, True),
        (-0.264, -0.5, True),
        (0.264, -0.5, True),
        (0.357143, -0.406857, True),
    )),
    "ASSCHER": ((-0.5, -0.5, 0.5, 0.5), (
        (0.5, 0.32, True),
        (0.319953, 0.5, True),
        (-0.319953, 0.5, True),
        (-0.5, 0.32, True),
        (-0.5, -0.32, True),
        (-0.319953, -0.5, True),
        (0.319953, -0.5, True),
        (0.5, -0.32, True),
    )),
    "RADIANT": ((-0.5, -0.5, 0.5, 0.5), (
        (0.5, 0.35, True),
        (0.35, 0.5, True),
        (-0.35, 0.5, True),
        (-0.5, 0.35, True),
        (-0.5, -0.35, True),
        (-0.35, -0.5, True),
        (0.35, -0.5, True),
        (0.5, -0.35, True),
    )),
    "FLANDERS": ((-0.5, -0.5, 0.5, 0.5), (
        (0.5, 0.277164, True),
        (0.277164, 0.5, True),
        (-0.277164, 0.5, True),
        (-0.5, 0.277164, True),
        (-0.5, -0.277164, True),
        (-0.277164, -0.5, True),
        (0.277164, -0.5, True),
        (0.5, -0.277164, True),
    )),
    "OCTAGON": ((-0.5, -0.5, 0.5, 0.5), (
        (0.5, 0.207107, True),
        (0.207107, 0.5, True),
        (-0.207107, 0.5, True),
        (-0.5, 0.207107, True),
        (-0.5, -0.207107, True),
        (-0.207107, -0.5, True),
        (0.207107, -0.5, True),
        (0.5, -0.207107, True),
    )),
    "HEART": ((-0.5, -0.580025, 0.5, 0.370169), (
        (0.599366, 0.122653, False),
        (0.329471, 0.40137, False),
        (0.087714, 0.356463, False),
        (0.0, 0.251297, True),
        (-0.087714, 0.356463, False),
        (-0.329471, 0.40137, False),
        (-0.599366, 0.122653, False),
        (-0.263262, -0.419865, False),
        (0.0, -0.580025, True),
        (0.263262, -0.419865, False),
    )),
    "TRILLION": ((-0.5, -0.57735, 0.5, 0.394395), (
        (0.438569, -0.03415, False),
        (0.5, 0.288675, True),
        (0.18971, 0.396886, False),
        (-0.18971, 0.396886, False),
        (-0.5, 0.288675, True),
        (-0.438568, -0.03415, False),
        (-0.248858, -0.362738, False),
        (0.0, -0.57735, True),
        (0.248858, -0.362738, False),
    )),
    "TRILLIANT": ((-0.5, -0.577351, 0.5, 0.352981), (
        (0.494177, 0.171809, True),
        (0.5, 0.288675, True),
        (0.395879, 0.342065, True),
        (0.0, 0.35662, False),
        (-0.395879, 0.342065, True),
        (-0.5, 0.288675, True),
        (-0.494177, 0.171809, True),
        (-0.308839, -0.178315, False),
        (-0.098298, -0.513874, True),
        (0.0, -0.577351, True),
        (0.098298, -0.513874, True),
        (0.308839, -0.178315, False),
    )),
    "TRIANGLE": ((-0.57735, -0.666667, 0.57735, 0.333334), (
        (0.57735, 0.333333, True),
        (-0.57735, 0.333333, True),
        (0.0, -0.666667, True),
    )),
}

_SAMPLES = 300           # образцов на участок контура при подгонке
_L2_STEPS = 15           # шагов МНК до минимакса
_STEPS = 215             # всего шагов подгонки
_TANGENT_WEIGHT = 0.05   # доля касательной невязки (иначе точки ползут вдоль кривой)
_WEIGHT_FLOOR = 0.01     # пол весов Лоусона: ни один образец не выпадает из подгонки
_FALLBACK_CORNER = radians(40.0)  # запасной путь: поворот оболочки круче — острый угол,
_FALLBACK_TURN = radians(45.0)    # одна гладкая точка на 45° поворота участка


def _turn(a, b, c) -> float:
    """Поворот ломаной в точке b, радианы, + против часовой."""
    ux, uy = b[0] - a[0], b[1] - a[1]
    vx, vy = c[0] - b[0], c[1] - b[1]
    return atan2(ux * vy - uy * vx, ux * vx + uy * vy)


def _area2(points) -> float:
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1]))


def _segment_distance(p, a, b) -> float:
    vx, vy = b[0] - a[0], b[1] - a[1]
    length2 = vx * vx + vy * vy
    t = 0.0 if length2 == 0.0 else min(1.0, max(0.0, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / length2))
    return hypot(p[0] - a[0] - vx * t, p[1] - a[1] - vy * t)


def _basis(s: float):
    """Веса четырёх опор пролёта кубического B-сплайна, их 1-я и 2-я производные."""
    t = 1.0 - s
    s2, s3 = s * s, s * s * s
    return (
        (t * t * t / 6.0, (3.0 * s3 - 6.0 * s2 + 4.0) / 6.0, (-3.0 * s3 + 3.0 * s2 + 3.0 * s + 1.0) / 6.0, s3 / 6.0),
        (-0.5 * t * t, 1.5 * s2 - 2.0 * s, -1.5 * s2 + s + 0.5, 0.5 * s2),
        (t, 3.0 * s - 2.0, 1.0 - 3.0 * s, s),
    )


class _Piece:
    """Кусок предела с m неизвестными гладкими точками: вся петля без углов (a is None)
    или участок между острыми вершинами a и b. Опора пролёта — (индекс неизвестной или -1,
    множитель, постоянная часть)."""

    def __init__(self, m: int, a=None, b=None):
        self.m = m
        self.closed = a is None
        self.spans = m if self.closed else m + 1
        if self.closed:
            return
        zero = (0.0, 0.0)
        first = (0, -1.0, (2.0 * a[0], 2.0 * a[1])) if m else (-1, 0.0, (2.0 * a[0] - b[0], 2.0 * a[1] - b[1]))
        last = (m - 1, -1.0, (2.0 * b[0], 2.0 * b[1])) if m else (-1, 0.0, (2.0 * b[0] - a[0], 2.0 * b[1] - a[1]))
        self.supports = [first, (-1, 0.0, a), *((i, 1.0, zero) for i in range(m)), (-1, 0.0, b), last]

    def span(self, u: float):
        """Четыре опоры пролёта с параметром u и локальный параметр."""
        if self.closed:
            j = floor(u)
            return [((j + k - 1) % self.m, 1.0, (0.0, 0.0)) for k in range(4)], u - j
        u = min(max(u, 0.0), float(self.spans))
        j = min(int(u), self.spans - 1)
        return self.supports[j:j + 4], u - j

    def evaluate(self, points, u: float):
        """Точка кривой, 1-я и 2-я производные."""
        supports, s = self.span(u)
        result = []
        for weights in _basis(s):
            x = y = 0.0
            for w, (i, factor, (cx, cy)) in zip(weights, supports):
                if i >= 0:
                    x += w * factor * points[i][0]
                    y += w * factor * points[i][1]
                x += w * cx
                y += w * cy
            result.append((x, y))
        return result

    def project(self, points, q, u: float) -> float:
        """Параметр ближайшей к q точки кривой (Ньютон от u)."""
        for _ in range(6):
            (px, py), (dx, dy), (ddx, ddy) = self.evaluate(points, u)
            ex, ey = px - q[0], py - q[1]
            slope = dx * dx + dy * dy + ex * ddx + ey * ddy
            if slope <= 1e-12:
                slope = dx * dx + dy * dy + 1e-12
            step = max(-0.5, min(0.5, -(ex * dx + ey * dy) / slope))
            u += step
            if not self.closed:
                u = min(max(u, 0.0), float(self.spans))
            if abs(step) < 1e-10:
                break
        return u


def _solve(matrix, rhs):
    """Гаусс с выбором главного элемента (матрица и правая часть портятся)."""
    n = len(rhs)
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(matrix[r][c]))
        matrix[c], matrix[p] = matrix[p], matrix[c]
        rhs[c], rhs[p] = rhs[p], rhs[c]
        for r in range(c + 1, n):
            f = matrix[r][c] / matrix[c][c]
            if f:
                row, pivot = matrix[r], matrix[c]
                for k in range(c, n):
                    row[k] -= f * pivot[k]
                rhs[r] -= f * rhs[c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (rhs[r] - sum(matrix[r][k] * x[k] for k in range(r + 1, n))) / matrix[r][r]
    return x


def _samples(poly, closed: bool, gamma: float):
    """Образцы на ломаной (вершины и равномерно по рёбрам) и доли пути до них: по длине,
    при gamma > 0 — ещё и по повороту (параметр гуще там, где контур круче)."""
    chain = poly + poly[:1] if closed else poly
    lengths = [hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(chain, chain[1:])]
    count = len(poly)
    bends = [0.0 if not closed and i in (0, count - 1)
             else abs(_turn(poly[i - 1], poly[i], poly[(i + 1) % count])) for i in range(count)]
    edge_bends = [(bends[i] + bends[(i + 1) % count]) * 0.5 for i in range(len(lengths))]
    total, bend_total = sum(lengths), sum(edge_bends)
    if bend_total < 1e-9:
        gamma = 0.0
    step = total / _SAMPLES
    points, fractions = [], []
    length = bend = 0.0
    for (a, b), l, t in zip(zip(chain, chain[1:]), lengths, edge_bends):
        k = max(2, ceil(l / step))
        for i in range(k):
            f = i / k
            points.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
            by_bend = (bend + t * f) / bend_total if gamma else 0.0
            fractions.append(((length + l * f) / total + gamma * by_bend) / (1.0 + gamma))
        length += l
        bend += t
    if not closed:
        points.append(poly[-1])
        fractions.append(1.0)
    return points, fractions


def _fit_samples(piece: _Piece, poly, samples, params):
    """Подгонка по образцам: сначала МНК по расстоянию до кривой (нормаль + доля касательной,
    параметры — проекции образцов), затем минимакс весами Лоусона. Лучшее по двусторонней
    оценке: невязки образцов и расстояние кривой до ломаной."""
    m = piece.m
    size = 2 * m
    edges = list(zip(poly, poly[1:] + poly[:1])) if piece.closed else list(zip(poly, poly[1:]))
    weights = [1.0] * len(samples)
    points = None
    best = (inf, None)
    for step in range(_STEPS):
        matrix = [[0.0] * size for _ in range(size)]
        rhs = [0.0] * size
        for q, u, weight in zip(samples, params, weights):
            supports, s = piece.span(u)
            coefficients = {}
            cx = cy = 0.0
            for w, (i, factor, (px, py)) in zip(_basis(s)[0], supports):
                if i >= 0:
                    coefficients[i] = coefficients.get(i, 0.0) + w * factor
                cx += w * px
                cy += w * py
            if points is None:
                directions = ((1.0, 0.0, weight), (0.0, 1.0, weight))
            else:
                tx, ty = piece.evaluate(points, u)[1]
                length = hypot(tx, ty) or 1.0
                tx, ty = tx / length, ty / length
                directions = ((-ty, tx, weight), (tx, ty, weight * _TANGENT_WEIGHT))
            for dx, dy, w in directions:
                row = [(2 * i, c * dx) for i, c in coefficients.items()]
                row += [(2 * i + 1, c * dy) for i, c in coefficients.items()]
                target = dx * (q[0] - cx) + dy * (q[1] - cy)
                for i, ci in row:
                    rhs[i] += w * ci * target
                    line = matrix[i]
                    for j, cj in row:
                        line[j] += w * ci * cj
        for i in range(size):
            matrix[i][i] += 1e-12
        z = _solve(matrix, rhs)
        points = [(z[2 * i], z[2 * i + 1]) for i in range(m)]

        residuals = []
        for k, q in enumerate(samples):
            params[k] = piece.project(points, q, params[k])
            p = piece.evaluate(points, params[k])[0]
            residuals.append(hypot(p[0] - q[0], p[1] - q[1]))
        score = max(residuals)
        for k in range(piece.spans * 8 + (0 if piece.closed else 1)):
            p = piece.evaluate(points, k / 8.0)[0]
            score = max(score, min(_segment_distance(p, a, b) for a, b in edges))
        if score < best[0]:
            best = (score, points)

        if step >= _L2_STEPS - 1:
            mean = sum(w * r for w, r in zip(weights, residuals)) / sum(weights) or 1.0
            weights = [w * (r + 1e-9 * mean) / mean for w, r in zip(weights, residuals)]
            norm = len(weights) / sum(weights)
            weights = [max(w * norm, _WEIGHT_FLOOR) for w in weights]
    return best


def _fit_piece(piece: _Piece, poly):
    """Гладкие точки куска под ломаную: лучшая из подгонок от двух стартовых параметризаций
    (по длине и по длине с поворотом)."""
    best = (inf, None)
    for gamma in (0.0, 1.0):
        samples, fractions = _samples(poly, piece.closed, gamma)
        result = _fit_samples(piece, poly, samples, [f * piece.spans for f in fractions])
        if result[0] < best[0]:
            best = result
    return best[1]


def _from_axis(points, center):
    """Замкнутый контур с началом на пересечении с лучом +X из центра."""
    cx, cy = center
    best = None
    for i in range(len(points)):
        (ax, ay), (bx, by) = points[i - 1], points[i]
        if (ay - cy) * (by - cy) <= 0.0 and ay != by:
            x = ax + (bx - ax) * (cy - ay) / (by - ay)
            if x > cx and (best is None or x > best[0]):
                best = (x, i)
    x, i = best
    eps = 1e-9 * max(abs(p[0] - cx) + abs(p[1] - cy) for p in points)
    rest = points[i:] + points[:i]
    return [(x, cy)] + [p for p in rest if hypot(p[0] - x, p[1] - cy) > eps]


def _symmetrize(loop, outline, center):
    """Зеркальная симметрия петли там, где симметричен контур (оси через центр габарита):
    точка усредняется с зеркальным образом своей пары. Сама подгонка симметрию не держит:
    у минимакса есть сдвиги, не меняющие максимум, и шум float уводит по ним. Если пары
    не находятся (петля устроена несимметрично), петля остаётся как есть."""
    size = max(max(p[axis] for p in outline) - min(p[axis] for p in outline) for axis in (0, 1))
    edges = list(zip(outline, outline[1:] + outline[:1]))
    for axis in (0, 1):
        c = center[axis]

        def mirrored(p):
            return (2.0 * c - p[0], p[1]) if axis == 0 else (p[0], 2.0 * c - p[1])

        if max(min(_segment_distance(mirrored(p), a, b) for a, b in edges) for p in outline) > 1e-3 * size:
            continue
        pairs = []
        for p in loop:
            q = mirrored(p)
            pairs.append(min((i for i, r in enumerate(loop) if r[2] == p[2]),
                             key=lambda i: hypot(loop[i][0] - q[0], loop[i][1] - q[1])))
        images = [mirrored(loop[j]) for j in pairs]
        if any(pairs[j] != i or hypot(m[0] - p[0], m[1] - p[1]) > 1e-2 * size
               for i, (j, p, m) in enumerate(zip(pairs, loop, images))):
            continue
        loop = [((p[0] + m[0]) * 0.5, (p[1] + m[1]) * 0.5, p[2]) for p, m in zip(loop, images)]
    return loop


def _canonical(loop, center):
    """Петля с первой точкой на наименьшем полярном угле [0, 2π) от центра (точка чуть ниже
    луча +X из-за шума float32 считается лежащей на нём)."""
    cx, cy = center

    def angle(p):
        a = atan2(p[1] - cy, p[0] - cx)
        return a + 2.0 * pi if a < -1e-5 else max(a, 0.0)

    first = min(range(len(loop)), key=lambda i: angle(loop[i]))
    return loop[first:] + loop[:first]


def fit_loop(outline, corners, count) -> list[tuple[float, float, bool]]:
    """Петля под плотный замкнутый контур outline [(x, y), ...]: corners — индексы его острых
    вершин, count — гладких точек на участке между соседними углами (число или список
    по участкам в порядке углов; без углов — точек во всей петле). Участку-отрезку точки
    не нужны. Возвращает [(x, y, corner)] против часовой стрелки с первой точкой на наименьшем
    полярном угле от центра габарита; зеркально симметричный контур (оси через центр
    габарита, допуск 0.1 % размера) даёт симметричную петлю."""
    points = [(float(p[0]), float(p[1])) for p in outline]
    n = len(points)
    if n < 3:
        raise ValueError("Outline needs at least 3 points")
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    center = ((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5)
    corners = sorted(set(corners))
    loop = []
    if not corners:
        if count < 3:
            raise ValueError("A loop without corners needs at least 3 points")
        loop = [(x, y, False) for x, y in _fit_piece(_Piece(count), _from_axis(points, center))]
    else:
        counts = [count] * len(corners) if isinstance(count, int) else list(count)
        for k, c in enumerate(corners):
            span = (corners[(k + 1) % len(corners)] - c) % n or n
            poly = [points[(c + i) % n] for i in range(span + 1)]
            loop.append((poly[0][0], poly[0][1], True))
            if counts[k] and span > 1:
                piece = _Piece(counts[k], poly[0], poly[-1])
                loop.extend((x, y, False) for x, y in _fit_piece(piece, poly))
    if _area2(points) < 0.0:
        loop.reverse()
    return _canonical(_symmetrize(loop, points, center), center)


def _convex_hull(points):
    """Выпуклая оболочка против часовой стрелки; почти совпадающие вершины слиты, вершины
    почти на прямой (шум float32, поворот меньше 0.01°) убраны."""
    unique = sorted(set(points))
    if len(unique) < 3:
        raise ValueError("Mesh has no area in XY")

    def chain(seq):
        out = []
        for p in seq:
            while len(out) >= 2 and ((out[-1][0] - out[-2][0]) * (p[1] - out[-2][1])
                                     - (out[-1][1] - out[-2][1]) * (p[0] - out[-2][0])) <= 0.0:
                out.pop()
            out.append(p)
        return out[:-1]

    hull = chain(unique) + chain(reversed(unique))
    eps = 1e-5 * max(unique[-1][0] - unique[0][0], max(p[1] for p in unique) - min(p[1] for p in unique))
    merged = []
    for p in hull:
        if not merged or hypot(p[0] - merged[-1][0], p[1] - merged[-1][1]) > eps:
            merged.append(p)
    if len(merged) > 3 and hypot(merged[0][0] - merged[-1][0], merged[0][1] - merged[-1][1]) <= eps:
        merged.pop()
    straight = radians(0.01)
    return [p for i, p in enumerate(merged) if abs(_turn(merged[i - 1], p, merged[(i + 1) % len(merged)])) > straight]


def _hull_loop(points) -> list[tuple[float, float, bool]]:
    """Запасной путь: выпуклая оболочка, острые углы по порогу поворота, гладкие точки
    по суммарному повороту участка."""
    hull = _convex_hull(points)
    n = len(hull)
    turns = [_turn(hull[i - 1], p, hull[(i + 1) % n]) for i, p in enumerate(hull)]
    corners = [i for i, t in enumerate(turns) if t >= _FALLBACK_CORNER]
    if not corners:
        return fit_loop(hull, [], round(2.0 * pi / _FALLBACK_TURN))
    counts = []
    for k, c in enumerate(corners):
        span = (corners[(k + 1) % len(corners)] - c) % n or n
        bend = sum(turns[(c + i) % n] for i in range(1, span))
        counts.append(max(0, ceil(bend / _FALLBACK_TURN - 0.05)))  # меньше 2.25° — отрезок
    return fit_loop(hull, corners, counts)


def limit_curve(loop, steps: int = 64) -> list[tuple[float, float, float, float]]:
    """Предел петли (кривая SubD) плотной выборкой: steps точек на пролёт, от узла первой точки
    по ходу петли. Пролёт i..i+1 — кривая Безье: узел K = P[i] у острой вершины и
    (P[i-1] + 4 P[i] + P[i+1]) / 6 у гладкой, ручки (2 P[i] + P[i+1]) / 3 и (P[i] + 2 P[i+1]) / 3
    (запись того же B-сплайна с фантомными точками, что в _Piece; совпадает до 1e-15).
    Возвращает [(x, y, tx, ty)], касательная единичная по ходу петли; в острой вершине —
    биссектриса направлений двух сторон."""
    n = len(loop)
    p = [(x, y) for x, y, _ in loop]
    knots = [p[i] if loop[i][2] else ((p[i - 1][0] + 4.0 * p[i][0] + p[(i + 1) % n][0]) / 6.0,
                                      (p[i - 1][1] + 4.0 * p[i][1] + p[(i + 1) % n][1]) / 6.0) for i in range(n)]

    def unit(x, y):
        length = hypot(x, y) or 1.0
        return x / length, y / length

    out = []
    for i in range(n):
        (ax, ay), (dx, dy) = p[i], p[(i + 1) % n]
        b0, b3 = knots[i], knots[(i + 1) % n]
        b1 = ((2.0 * ax + dx) / 3.0, (2.0 * ay + dy) / 3.0)
        b2 = ((ax + 2.0 * dx) / 3.0, (ay + 2.0 * dy) / 3.0)
        for k in range(steps):
            t = k / steps
            s = 1.0 - t
            w = (s * s * s, 3.0 * s * s * t, 3.0 * s * t * t, t * t * t)
            dw = (-3.0 * s * s, 3.0 * s * (s - 2.0 * t), 3.0 * t * (2.0 * s - t), 3.0 * t * t)
            x = sum(c * b[0] for c, b in zip(w, (b0, b1, b2, b3)))
            y = sum(c * b[1] for c, b in zip(w, (b0, b1, b2, b3)))
            tx, ty = unit(sum(c * b[0] for c, b in zip(dw, (b0, b1, b2, b3))),
                          sum(c * b[1] for c, b in zip(dw, (b0, b1, b2, b3))))
            if k == 0 and loop[i][2]:
                ix, iy = unit(ax - p[i - 1][0], ay - p[i - 1][1])
                tx, ty = unit(ix + tx, iy + ty)
            out.append((x, y, tx, ty))
    return out


def gem_loop(obj) -> list[tuple[float, float, bool]]:
    """Петля под рундист камня в локальных координатах объекта-меша. Огранка — obj["gem"]["cut"]
    (так пишут parametric_gems и JewelCraft), размер и положение — габарит XY вершин меша.
    Неизвестная огранка или меш без неё — по выпуклой оболочке вершин."""
    mesh = obj.data
    co = [0.0] * (3 * len(mesh.vertices))
    mesh.vertices.foreach_get("co", co)
    if not co:
        raise ValueError(f"{obj.name}: mesh has no vertices")
    xs, ys = co[0::3], co[1::3]
    gem = obj.get("gem")
    cut = str(gem.get("cut", "")).upper() if hasattr(gem, "get") else ""
    if cut not in CUT_LOOPS:
        return _hull_loop(list(zip(xs, ys)))
    (x0, y0, x1, y1), loop = CUT_LOOPS[cut]
    left, bottom = min(xs), min(ys)
    sx = (max(xs) - left) / (x1 - x0)
    sy = (max(ys) - bottom) / (y1 - y0)
    return [(left + (x - x0) * sx, bottom + (y - y0) * sy, corner) for x, y, corner in loop]
