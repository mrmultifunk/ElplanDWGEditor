from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict
from math import floor, hypot
from typing import Iterable, Sequence

Rect = tuple[float, float, float, float]


def normalize_rect(rect: Sequence[float]) -> Rect:
    x1, y1, x2, y2 = map(float, rect)
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


def expand_rect(rect: Sequence[float], padding: float) -> Rect:
    x1, y1, x2, y2 = normalize_rect(rect)
    p = max(0.0, float(padding))
    return x1 - p, y1 - p, x2 + p, y2 + p


def rect_from_origin(x: float, y: float, width: float, height: float) -> Rect:
    return normalize_rect((float(x), float(y), float(x) + max(0.0, float(width)), float(y) + max(0.0, float(height))))


def rects_overlap(a: Sequence[float], b: Sequence[float], padding: float = 0.0) -> bool:
    ax1, ay1, ax2, ay2 = expand_rect(a, padding)
    bx1, by1, bx2, by2 = normalize_rect(b)
    return ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1


def overlap_area(a: Sequence[float], b: Sequence[float]) -> float:
    ax1, ay1, ax2, ay2 = normalize_rect(a)
    bx1, by1, bx2, by2 = normalize_rect(b)
    return max(0.0, min(ax2, bx2) - max(ax1, bx1)) * max(0.0, min(ay2, by2) - max(ay1, by1))


class RectSpatialIndex:
    """Exact uniform-grid lookup for sparse label/symbol collision tests.

    Rectangles spanning an unusually large number of cells are kept in a
    small global bucket.  Query results retain insertion order, so dense-plan
    fallback scoring remains deterministic.
    """

    def __init__(self, rects: Iterable[Sequence[float]] = (), *, cell_size: float = 64.0):
        try:
            self.cell_size=max(abs(float(cell_size)),1e-9)
        except Exception:
            self.cell_size=64.0
        self._rects: list[Rect]=[]
        self._buckets: dict[tuple[int,int],list[int]]=defaultdict(list)
        self._global_indices: list[int]=[]
        for rect in rects:
            self.add(rect)

    def _cell_bounds(self, rect: Sequence[float]) -> tuple[int,int,int,int]:
        x1,y1,x2,y2=normalize_rect(rect)
        size=self.cell_size
        return floor(x1/size),floor(y1/size),floor(x2/size),floor(y2/size)

    def add(self, rect: Sequence[float]) -> Rect:
        normalized=normalize_rect(rect)
        index=len(self._rects)
        self._rects.append(normalized)
        x1,y1,x2,y2=self._cell_bounds(normalized)
        cell_count=(x2-x1+1)*(y2-y1+1)
        if cell_count>4096:
            self._global_indices.append(index)
            return normalized
        for cell_x in range(x1,x2+1):
            for cell_y in range(y1,y2+1):
                self._buckets[(cell_x,cell_y)].append(index)
        return normalized

    def query(self, rect: Sequence[float], padding: float = 0.0) -> list[Rect]:
        query_rect=expand_rect(rect,max(0.0,float(padding)))
        x1,y1,x2,y2=self._cell_bounds(query_rect)
        cell_count=(x2-x1+1)*(y2-y1+1)
        if cell_count>4096:
            candidates=set(range(len(self._rects)))
        else:
            candidates=set(self._global_indices)
            for cell_x in range(x1,x2+1):
                for cell_y in range(y1,y2+1):
                    candidates.update(self._buckets.get((cell_x,cell_y),()))
        return [self._rects[index] for index in sorted(candidates) if rects_overlap(query_rect,self._rects[index])]

    def __len__(self) -> int:
        return len(self._rects)


def preferred_side_from_vector(dx: float, dy: float, *, y_down: bool = False) -> str:
    dx = float(dx); dy = float(dy)
    if abs(dx) >= abs(dy):
        return "right" if dx >= 0 else "left"
    if y_down:
        return "below" if dy >= 0 else "above"
    return "above" if dy >= 0 else "below"


def _side_order(preferred: str) -> list[str]:
    preferred = preferred if preferred in {"right", "left", "above", "below"} else "right"
    adjacent = {
        "right": ["above", "below", "left"],
        "left": ["above", "below", "right"],
        "above": ["right", "left", "below"],
        "below": ["right", "left", "above"],
    }
    return [preferred, *adjacent[preferred]]


def label_candidate_origins(
    anchor: tuple[float, float],
    symbol_bounds: Sequence[float],
    width: float,
    height: float,
    *,
    preferred: str = "right",
    gap: float = 5.0,
    y_down: bool = False,
    rings: int = 8,
) -> list[tuple[float, float, str]]:
    """Return nearby label origins ordered from natural to increasingly displaced.

    Coordinates can be conventional page coordinates (y grows upwards) or Qt scene
    coordinates (y grows downwards). The generated rectangles are always outside the
    source symbol's silhouette before collision checks against neighbouring objects.
    """
    left, bottom, right, top = normalize_rect(symbol_bounds)
    ax, ay = map(float, anchor)
    width = max(0.1, float(width)); height = max(0.1, float(height))
    gap = max(0.0, float(gap)); rings = max(1, int(rings))
    step = max(4.0, min(14.0, max(width, height) * 0.42))
    tangent = max(3.5, min(11.0, min(width, height) * 0.55))
    shifts = [0.0, -tangent, tangent, -2*tangent, 2*tangent, -3*tangent, 3*tangent]
    out: list[tuple[float, float, str]] = []
    seen: set[tuple[int, int, str]] = set()

    for ring in range(rings):
        outward = gap + ring * step
        for side in _side_order(preferred):
            for shift in shifts:
                if side == "right":
                    x = right + outward
                    y = ay - height * .5 + shift
                elif side == "left":
                    x = left - outward - width
                    y = ay - height * .5 + shift
                elif side == "above":
                    x = ax - width * .5 + shift
                    y = (bottom - outward - height) if y_down else (top + outward)
                else:  # below
                    x = ax - width * .5 + shift
                    y = (top + outward) if y_down else (bottom - outward - height)
                key = (round(x * 1000), round(y * 1000), side)
                if key not in seen:
                    seen.add(key); out.append((x, y, side))
    return out


def _inside(rect: Rect, container: Sequence[float] | None) -> bool:
    if container is None:
        return True
    x1, y1, x2, y2 = normalize_rect(container)
    rx1, ry1, rx2, ry2 = normalize_rect(rect)
    return rx1 >= x1 and ry1 >= y1 and rx2 <= x2 and ry2 <= y2


def choose_label_origin(
    anchor: tuple[float, float],
    symbol_bounds: Sequence[float],
    width: float,
    height: float,
    *,
    blockers: Iterable[Sequence[float]] = (),
    occupied: Iterable[Sequence[float]] = (),
    blocker_index: RectSpatialIndex | None = None,
    occupied_index: RectSpatialIndex | None = None,
    preferred: str = "right",
    gap: float = 5.0,
    collision_padding: float = 1.2,
    y_down: bool = False,
    container: Sequence[float] | None = None,
) -> tuple[float, float, str, Rect]:
    """Pick a nearby label position without covering symbols or existing labels.

    Symbols are hard blockers. Previously placed metadata is also treated as occupied.
    A large candidate field is searched first; if an exceptionally dense drawing has
    no completely free slot, the geometrically least-overlapping candidate is chosen.
    """
    block = [] if blocker_index is not None else [normalize_rect(r) for r in blockers]
    used = [] if occupied_index is not None else [normalize_rect(r) for r in occupied]
    candidates = label_candidate_origins(anchor, symbol_bounds, width, height, preferred=preferred, gap=gap, y_down=y_down)
    pad = max(0.0, float(collision_padding))

    for x, y, side in candidates:
        rect = rect_from_origin(x, y, width, height)
        if not _inside(rect, container):
            continue
        nearby_block=blocker_index.query(rect,pad) if blocker_index is not None else block
        if any(rects_overlap(rect, other, pad) for other in nearby_block):
            continue
        nearby_used=occupied_index.query(rect,pad) if occupied_index is not None else used
        if any(rects_overlap(rect, other, pad) for other in nearby_used):
            continue
        return x, y, side, rect

    # Extremely dense fallback. Keep hard symbol overlap far more expensive than
    # metadata overlap and penalize leaving the printable/viewable container.
    ax, ay = map(float, anchor)
    best = None
    for rank, (x, y, side) in enumerate(candidates):
        rect = rect_from_origin(x, y, width, height)
        nearby_block=blocker_index.query(rect) if blocker_index is not None else block
        nearby_used=occupied_index.query(rect) if occupied_index is not None else used
        symbol_overlap = sum(overlap_area(rect, other) for other in nearby_block)
        metadata_overlap = sum(overlap_area(rect, other) for other in nearby_used)
        outside = 0.0 if _inside(rect, container) else width * height * 25.0
        cx = x + width * .5; cy = y + height * .5
        distance = hypot(cx - ax, cy - ay)
        score = symbol_overlap * 10000.0 + metadata_overlap * 1500.0 + outside + distance * .02 + rank * .001
        if best is None or score < best[0]:
            best = (score, x, y, side, rect)
    if best is None:
        rect = rect_from_origin(anchor[0] + gap, anchor[1] + gap, width, height)
        return rect[0], rect[1], preferred, rect
    return best[1], best[2], best[3], best[4]
