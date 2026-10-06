from __future__ import annotations

from pathlib import Path
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import jewelry_suite
from jewelry_suite import pretty_ruler as pr


def pts(*points: tuple[float, float, float]) -> list[str]:
    return pr._stroke_key(points).split(";")


A = pts((0, 0, 0), (1, 0, 0))
B = pts((0, 1, 0), (1, 1, 0))
C = pts((0, 2, 0), (1, 2, 0))
B_MOVED = pts((0, 1, 0), (3, 1, 0))
ANGLE = pts((0, 0, 0), (0, 0, 1), (1, 0, 1))

# Удаление линейки: флаги остальных не съезжают
assert pr._match_flags([(A, True), (B, False), (C, True)], [A, C]) == [True, True]
assert pr._match_flags([(A, True), (B, False), (C, True)], [B, C]) == [False, True]
# Перетащили один конец: флаг остаётся
assert pr._match_flags([(A, True), (B, False)], [A, B_MOVED]) == [True, False]
# Новая линейка включена; угол не сопоставляется с размером по общей точке
assert pr._match_flags([(A, False)], [A, C]) == [False, True]
assert pr._match_flags([(A, False)], [ANGLE]) == [True]
# Одинаковые линейки разбираются по одной
assert pr._match_flags([(A, False), (A, True)], [A, A]) == [False, True]

jewelry_suite.register()
assert pr._handle is not None, "draw handler must be active right after register"
assert bpy.app.timers.is_registered(pr._sync_timer)

props = bpy.context.scene.pretty_ruler
props.enabled = False
assert pr.draw_callback() is None  # выключено — выходит до обращения к региону
props.enabled = True
assert len(props.items) == len(pr.get_ruler_strokes())

jewelry_suite.unregister()
assert pr._handle is None
assert not bpy.app.timers.is_registered(pr._sync_timer)

print("PRETTY_RULER_TEST", {"match_flags": "ok", "handler": "ok", "timer": "ok"})
