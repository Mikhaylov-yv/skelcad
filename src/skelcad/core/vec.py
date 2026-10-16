"""Небольшая векторная арифметика для правил и генераторов (без numpy)."""

from __future__ import annotations

import math

from skelcad.core.model import Vec2, Vec3


def sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def norm(a: Vec3) -> float:
    return math.sqrt(dot(a, a))


def unit(a: Vec3) -> Vec3:
    n = norm(a) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


def project_out(p: Vec3, axis: Vec3) -> Vec3:
    """Убрать из вектора составляющую вдоль оси (проекция на плоскость ⟂ axis)."""
    a = unit(axis)
    k = dot(p, a)
    return (p[0] - k * a[0], p[1] - k * a[1], p[2] - k * a[2])


def dist_point_segment(p: Vec2, a: Vec2, b: Vec2) -> float:
    ax, ay = b[0] - a[0], b[1] - a[1]
    t = max(0.0, min(1.0, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / (ax * ax + ay * ay or 1)))
    return math.dist(p, (a[0] + t * ax, a[1] + t * ay))


def dist_point_segment_perp(p: Vec3, a: Vec3, b: Vec3, axis: Vec3) -> float:
    """Расстояние от точки до отрезка в проекции на плоскость, перпендикулярную оси."""
    p2, a2, b2 = (project_out(v, axis) for v in (p, a, b))
    ab = sub(b2, a2)
    denom = dot(ab, ab) or 1.0
    t = max(0.0, min(1.0, dot(sub(p2, a2), ab) / denom))
    q = (a2[0] + t * ab[0], a2[1] + t * ab[1], a2[2] + t * ab[2])
    return norm(sub(p2, q))


def ceil_to(x: float, step: float) -> float:
    return math.ceil(x / step) * step
