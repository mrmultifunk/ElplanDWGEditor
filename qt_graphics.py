from __future__ import annotations

import math
import uuid
from collections import defaultdict
from typing import Callable

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QPointF, QRectF, Qt, Signal, QObject, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QIcon, QPainter, QPainterPath, QPainterPathStroker, QPen, QBrush, QPixmap, QPalette
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QGraphicsDropShadowEffect,
    QApplication,
)

import core_logic as core
from interaction_math import wheel_zoom_factor, axis_alignment_snap, room_axis_assist, room_wall_axis_snap, spot_row_axis_assist


def _mapped_point(x: float, y: float) -> QPointF:
    return QPointF(float(x), -float(y))


def _cad_point(point: QPointF) -> tuple[float, float]:
    return float(point.x()), float(-point.y())


def _ui_is_dark() -> bool:
    app=QApplication.instance()
    return bool(app.property("elplanDarkMode")) if app is not None else False


def _canvas_is_dark() -> bool:
    app=QApplication.instance()
    return bool(app.property("elplanCanvasDark")) if app is not None else False


def _dark_canvas_contrast(color: QColor, *, preserve_hue: bool = True) -> QColor:
    """Screen-only contrast correction for user colors on the dark canvas.

    Project/export colors are never modified. Very dark colors get a brighter
    display variant with the same hue; saturated colors that already read well
    are left untouched.
    """
    c=QColor(color)
    if not _canvas_is_dark() or not c.isValid():
        return c
    if c.lightness() >= 78:
        return c
    if preserve_hue:
        h,s,l,a=c.getHsl()
        if h < 0:
            return QColor(210,218,228,a)
        out=QColor(); out.setHsl(h,max(45,s),max(145,l),a); return out
    return QColor(210,218,228,c.alpha())


def _canvas_text_color(light="#202124", dark="#d6dde6") -> QColor:
    return QColor(dark if _canvas_is_dark() else light)


def _qt_cable_pen_style(value: str):
    style=core.normalize_cable_line_style(value)
    return {
        "dash": Qt.PenStyle.DashLine,
        "dot": Qt.PenStyle.DotLine,
        "dashdot": Qt.PenStyle.DashDotLine,
    }.get(style, Qt.PenStyle.SolidLine)


def _arc_points(cx: float, cy: float, radius: float, a0: float, a1: float) -> list[QPointF]:
    sweep = (float(a1) - float(a0)) % 360.0
    if sweep == 0:
        sweep = 360.0
    steps = max(8, int(abs(sweep) / 8.0))
    out: list[QPointF] = []
    for i in range(steps + 1):
        a = math.radians(float(a0) + sweep * i / steps)
        out.append(_mapped_point(cx + radius * math.cos(a), cy + radius * math.sin(a)))
    return out


def _draw_symbol_primitives(
    painter: QPainter,
    primitives,
    color: QColor,
    selected: bool = False,
    upright_rotation: float = 0.0,
) -> None:
    pen = QPen(QColor("#2563eb") if selected else color)
    pen.setCosmetic(True)
    pen.setWidthF(2.35 if selected else 1.70)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for prim in primitives:
        kind = prim[0]
        try:
            if kind == "line":
                painter.drawLine(_mapped_point(prim[1], prim[2]), _mapped_point(prim[3], prim[4]))
            elif kind == "circle":
                _, cx, cy, r = prim
                painter.drawEllipse(QRectF(cx-r, -cy-r, 2*r, 2*r))
            elif kind == "arc":
                points = _arc_points(prim[1], prim[2], prim[3], prim[4], prim[5])
                if len(points) >= 2:
                    path = QPainterPath(points[0])
                    for point in points[1:]:
                        path.lineTo(point)
                    painter.drawPath(path)
            elif kind == "polyline":
                points = [_mapped_point(x, y) for x, y in prim[1]]
                if len(points) >= 2:
                    path = QPainterPath(points[0])
                    for point in points[1:]:
                        path.lineTo(point)
                    painter.drawPath(path)
            elif kind == "text":
                _, x, y, txt, h = prim
                painter.save()
                font = QFont("Segoe UI")
                font.setPointSizeF(max(1.0, h * 0.6))
                painter.setFont(font)
                painter.drawText(_mapped_point(x, y), str(txt))
                painter.restore()
            elif kind == "upright_text":
                _, x, y, txt, h = prim
                painter.save()
                painter.translate(_mapped_point(x, y))
                # ElectricalSymbolItem roterer hele item'et -placement.rotation.
                # Den modsatte lokale rotation holder mærkningen vandret.
                painter.rotate(float(upright_rotation))
                font = QFont("Segoe UI")
                font.setBold(True)
                font.setPointSizeF(max(1.0, h * 0.6))
                painter.setFont(font)
                metrics = QFontMetricsF(font)
                value = str(txt)
                baseline = (metrics.ascent() - metrics.descent()) * 0.5
                painter.drawText(QPointF(-metrics.horizontalAdvance(value) * 0.5, baseline), value)
                painter.restore()
        except Exception:
            continue


def symbol_icon(symbol: str, size_px: int = 72, color: str = "#d00000") -> QIcon:
    """Render a vector symbol into a compact Qt palette icon."""
    px = max(32, int(size_px))
    pix = QPixmap(px, px)
    app=QApplication.instance()
    bg=app.palette().color(QPalette.ColorRole.Base) if app is not None else QColor("#ffffff")
    pix.fill(bg)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    nominal = 500.0
    primitives = core.symbol_primitives(symbol, nominal)
    x1, y1, x2, y2 = core.symbol_local_bbox(symbol, nominal)
    width = max(x2 - x1, 1.0)
    height = max(y2 - y1, 1.0)
    margin = 9.0
    scale = min((px - 2 * margin) / width, (px - 2 * margin) / height)
    painter.translate(px / 2.0, px / 2.0)
    painter.scale(scale, scale)
    painter.translate(-(x1 + x2) / 2.0, (y1 + y2) / 2.0)
    icon_color=QColor(color)
    if _ui_is_dark() and icon_color.lightness()<78:
        h,sat,light,alpha=icon_color.getHsl()
        if h<0:
            icon_color=QColor(210,218,228,alpha)
        else:
            icon_color.setHsl(h,max(45,sat),max(145,light),alpha)
    _draw_symbol_primitives(painter, primitives, icon_color, False)
    painter.end()
    return QIcon(pix)


class CadLayerItem(QGraphicsItem):
    """One graphics item per CAD layer instead of thousands of scene items."""

    def __init__(self, layer: str, primitives: list[core.CADPrimitive]):
        super().__init__()
        self.layer = layer
        self._path = QPainterPath()
        self._texts: list[tuple[float, float, str, float, float]] = []
        self._points: list[tuple[float, float]] = []
        self._build(primitives)
        self._bounds = self._path.boundingRect()
        for x, y in self._points:
            self._bounds = self._bounds.united(QRectF(x - 2, -y - 2, 4, 4))
        for x, y, txt, height, _rot in self._texts:
            approx = max(height, 1.0) * max(len(txt), 1) * 0.6
            self._bounds = self._bounds.united(QRectF(x, -y - height, approx, height * 1.4))
        self.setZValue(-1000)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)

    def _line(self, p1: QPointF, p2: QPointF) -> None:
        self._path.moveTo(p1)
        self._path.lineTo(p2)

    def _poly(self, points: list[QPointF]) -> None:
        if len(points) < 2:
            return
        self._path.moveTo(points[0])
        for p in points[1:]:
            self._path.lineTo(p)

    def _build(self, primitives: list[core.CADPrimitive]) -> None:
        for prim in primitives:
            kind, data = prim.kind, prim.data
            try:
                if kind == "line":
                    self._line(_mapped_point(data[0], data[1]), _mapped_point(data[2], data[3]))
                elif kind == "polyline":
                    self._poly([_mapped_point(x, y) for x, y in data])
                elif kind == "circle":
                    cx, cy, r = data
                    self._path.addEllipse(QRectF(cx - r, -cy - r, 2 * r, 2 * r))
                elif kind == "arc":
                    self._poly(_arc_points(*data))
                elif kind == "point":
                    self._points.append((float(data[0]), float(data[1])))
                elif kind == "text":
                    self._texts.append((float(data[0]), float(data[1]), str(data[2]), float(data[3]), float(data[4])))
            except Exception:
                continue

    def boundingRect(self) -> QRectF:
        return self._bounds.adjusted(-2, -2, 2, 2)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        pen = QPen(QColor("#aeb8c4") if _canvas_is_dark() else QColor("#202124"))
        pen.setWidthF(0)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self._path)
        for x, y in self._points:
            p = _mapped_point(x, y)
            painter.drawLine(p + QPointF(-2, 0), p + QPointF(2, 0))
            painter.drawLine(p + QPointF(0, -2), p + QPointF(0, 2))
        for x, y, txt, height, rotation in self._texts:
            if not txt:
                continue
            painter.save()
            painter.translate(x, -y)
            painter.rotate(-rotation)
            font = QFont("Segoe UI")
            font.setPointSizeF(max(1.0, height * 0.65))
            painter.setFont(font)
            painter.drawText(QPointF(0, 0), txt)
            painter.restore()


class QtSnapEngine:
    """Scene-coordinate snap engine used directly by the Qt interaction pipeline."""

    def __init__(self, primitives: list[core.CADPrimitive], layer_visible: Callable[[str], bool]):
        self.layer_visible = layer_visible
        self.segments: list[tuple[float, float, float, float, str, bool]] = []
        self.grid: dict[tuple[int, int], set[int]] = defaultdict(set)
        self.cell_size = 500.0
        # Hysteresis locks prevent wall-mounted symbols from bouncing between
        # nearby/perpendicular CAD segments while the cursor is near a corner.
        self.wall_locks: dict[str, int] = {}
        self._build(primitives)

    def _build(self, primitives: list[core.CADPrimitive]) -> None:
        raw_segments: list[tuple[float, float, float, float, str, bool]] = []
        xs: list[float] = []
        ys: list[float] = []
        for prim in primitives:
            layer = prim.layer
            # EL-RUM is semantic overlay geometry, never a physical CAD wall.
            # Keep this explicit guard even though MainWindow currently builds the
            # snap engine from CAD primitives only; it prevents a later refactor
            # from accidentally making room boundaries magnetic for symbols/cables.
            if str(layer).casefold() == str(core.ROOM_LAYER).casefold():
                continue
            preferred = "wall" in layer.casefold() or "væg" in layer.casefold()
            try:
                if prim.kind == "line":
                    x1, y1, x2, y2 = map(float, prim.data[:4])
                    raw_segments.append((x1, y1, x2, y2, layer, preferred))
                    xs.extend((x1, x2)); ys.extend((y1, y2))
                elif prim.kind == "polyline":
                    pts = list(prim.data)
                    for a, b in zip(pts, pts[1:]):
                        x1, y1 = map(float, a); x2, y2 = map(float, b)
                        raw_segments.append((x1, y1, x2, y2, layer, preferred))
                        xs.extend((x1, x2)); ys.extend((y1, y2))
            except Exception:
                continue
        self.segments = raw_segments
        if xs and ys:
            diag = math.hypot(max(xs)-min(xs), max(ys)-min(ys))
            self.cell_size = max(150.0, min(1500.0, diag / 70.0 if diag > 0 else 500.0))
        for idx, (x1, y1, x2, y2, _layer, _preferred) in enumerate(self.segments):
            gx1 = math.floor(min(x1, x2) / self.cell_size); gx2 = math.floor(max(x1, x2) / self.cell_size)
            gy1 = math.floor(min(y1, y2) / self.cell_size); gy2 = math.floor(max(y1, y2) / self.cell_size)
            # Long construction lines are bounded to avoid pathological grids.
            if (gx2-gx1+1) * (gy2-gy1+1) > 2000:
                continue
            for gx in range(gx1, gx2 + 1):
                for gy in range(gy1, gy2 + 1):
                    self.grid[(gx, gy)].add(idx)

    @staticmethod
    def _nearest_on_segment(px, py, x1, y1, x2, y2):
        dx, dy = x2-x1, y2-y1
        den = dx*dx + dy*dy
        if den <= 1e-18:
            return x1, y1
        t = ((px-x1)*dx + (py-y1)*dy) / den
        t = min(1.0, max(0.0, t))
        return x1 + t*dx, y1 + t*dy

    def nearest_wall(self, x: float, y: float, tol_cad: float):
        r = max(float(tol_cad), 1e-9)
        gx1 = math.floor((x-r)/self.cell_size); gx2 = math.floor((x+r)/self.cell_size)
        gy1 = math.floor((y-r)/self.cell_size); gy2 = math.floor((y+r)/self.cell_size)
        ids: set[int] = set()
        for gx in range(gx1, gx2+1):
            for gy in range(gy1, gy2+1):
                ids.update(self.grid.get((gx, gy), ()))
        best = None
        best_score = float("inf")
        for idx in ids:
            x1, y1, x2, y2, layer, preferred = self.segments[idx]
            if not self.layer_visible(layer):
                continue
            nx, ny = self._nearest_on_segment(x, y, x1, y1, x2, y2)
            dist = math.hypot(nx-x, ny-y)
            if dist > r:
                continue
            # Prefer actual wall layers when equally close, but allow any visible line.
            score = dist * (0.75 if preferred else 1.0)
            if score < best_score:
                angle = math.degrees(math.atan2(y2-y1, x2-x1))
                best = (nx, ny, angle, layer, dist, idx)
                best_score = score
        return best

    def _wall_by_index(self, idx: int, x: float, y: float, tol_cad: float):
        try:
            x1,y1,x2,y2,layer,preferred=self.segments[int(idx)]
        except Exception:
            return None
        if not self.layer_visible(layer):
            return None
        nx,ny=self._nearest_on_segment(x,y,x1,y1,x2,y2)
        dist=math.hypot(nx-x,ny-y)
        if dist>float(tol_cad):
            return None
        angle=math.degrees(math.atan2(y2-y1,x2-x1))
        return (nx,ny,angle,layer,dist,int(idx))

    def clear_wall_lock(self, key: str = "") -> None:
        if key:
            self.wall_locks.pop(str(key),None)
        else:
            self.wall_locks.clear()

    def _stable_wall_hint(self, x: float, y: float, tol_cad: float, key: str):
        key=str(key or "")
        nearest=self.nearest_wall(x,y,tol_cad)
        locked=None
        lock_idx=self.wall_locks.get(key) if key else None
        if lock_idx is not None:
            # Release tolerance is deliberately larger than acquisition tolerance.
            locked=self._wall_by_index(lock_idx,x,y,tol_cad*1.65)
        chosen=nearest
        if locked is not None:
            if nearest is None:
                chosen=locked
            elif nearest[5]==locked[5]:
                chosen=nearest
            else:
                # Only jump to another wall if it is visibly closer. This avoids
                # rapid 90° flipping at corners and parallel wall lines.
                switch_margin=max(tol_cad*.28,1e-6)
                chosen=nearest if nearest[4]+switch_margin<locked[4] else locked
        if chosen is not None and key:
            self.wall_locks[key]=int(chosen[5])
        elif chosen is None and key:
            self.wall_locks.pop(key,None)
        return chosen

    def _nearby_symbols(self, scene, raw_cad, tol_cad: float, ignore_uid: str = ""):
        x, y = raw_cad
        r = max(tol_cad, 1.0)
        rect = QRectF(x-r, -y-r, 2*r, 2*r)
        out = []
        for item in scene.items(rect):
            if isinstance(item, ElectricalSymbolItem):
                if item.placement.uid == ignore_uid or not item.isVisible():
                    continue
                out.append(item)
        return out

    @staticmethod
    def _wall_oriented_rotation(symbol: str, size: float, current_rotation: float, wall_hint, cursor_cad, view_scale: float) -> float:
        """Choose a stable wall orientation and, for offset mount-points, the side closest to the cursor."""
        if wall_hint is None or not core._is_wall_device(symbol):
            return float(current_rotation)%360.0
        base=float(wall_hint[2])%180.0
        candidates=[base,(base+180.0)%360.0]
        cur=float(current_rotation)%360.0
        mounts=core.symbol_mount_points(symbol,size)
        if not mounts or cursor_cad is None:
            return min(candidates,key=lambda q:core._angular_distance_deg(q,cur))
        mx,my=mounts[0]
        # For symbols whose mount point is the centre (e.g. many switches),
        # cursor-side selection cannot distinguish 180° alternatives.
        if math.hypot(mx,my)<1e-9:
            return min(candidates,key=lambda q:core._angular_distance_deg(q,cur))
        scored=[]
        for candidate in candidates:
            rx,ry=core.rotate_point(mx,my,candidate)
            origin=(wall_hint[0]-rx,wall_hint[1]-ry)
            d=math.hypot(origin[0]-cursor_cad[0],origin[1]-cursor_cad[1])
            scored.append((d,candidate))
        scored.sort(key=lambda q:q[0])
        # Near the wall centreline, keep the user's/current side until the
        # cursor is clearly on the other side. This removes 180° flicker.
        hysteresis=6.0/max(abs(float(view_scale)),1e-9)
        if len(scored)>1 and scored[1][0]-scored[0][0]<hysteresis:
            return min(candidates,key=lambda q:core._angular_distance_deg(q,cur))
        return scored[0][1]

    def snap_pose(self, scene, symbol: str, size: float, rotation: float, raw_cad: tuple[float,float], view_scale: float,
                  ignore_uid: str = "", cursor_cad: tuple[float,float] | None = None):
        scale = max(abs(float(view_scale)), 1e-9)
        tol_symbol = (15.0 if core._is_wall_device(symbol) else 20.0) / scale
        tol_wall = 27.0 / scale
        ox, oy = map(float, raw_cad)
        rot = float(rotation) % 360.0
        kind_parts: list[str] = []

        # 1) Symbol-to-symbol snap using the validated legacy mating geometry.
        best_symbol = None
        best_d = float("inf")
        for fixed_item in self._nearby_symbols(scene, (ox, oy), max(tol_symbol, size*2.2), ignore_uid):
            fixed = fixed_item.placement
            candidates = []
            if core._is_wall_device(symbol) and core._is_wall_device(fixed.symbol):
                candidates = core.wall_device_snap_origins(symbol, size, fixed, rot)
            else:
                moving = {}
                for name, (lx, ly) in core.symbol_mating_sites(symbol, size).items():
                    lx, ly = core.rotate_point(lx, ly, rot)
                    moving[name] = (ox+lx, oy+ly)
                fixed_sites = core.placement_mating_sites(fixed)
                opposite = {"left":"right", "right":"left", "top":"bottom", "bottom":"top"}
                for mname, fname in opposite.items():
                    mx, my = moving[mname]; fx, fy = fixed_sites[fname]
                    candidates.append((ox+fx-mx, oy+fy-my, "symbol"))
            for tx, ty, _label in candidates:
                d = math.hypot(tx-ox, ty-oy)
                if d <= tol_symbol and d < best_d:
                    best_symbol = (tx, ty, fixed)
                    best_d = d
        if best_symbol:
            ox, oy, fixed = best_symbol
            if core._is_wall_device(symbol) and core._is_wall_device(fixed.symbol):
                rot = float(fixed.rotation) % 360.0
            kind_parts.append("SYMBOL")

        # 2) Wall snap. Auto-orient wall-mounted devices to the nearest visible CAD line.
        wall_hint = None
        lock_key=str(ignore_uid or symbol)
        if cursor_cad is not None:
            wall_hint = self._stable_wall_hint(cursor_cad[0],cursor_cad[1],tol_wall,lock_key)
        if wall_hint is not None and core._is_wall_device(symbol):
            rot = self._wall_oriented_rotation(symbol,size,rot,wall_hint,cursor_cad,scale)

        mounts = core.symbol_mount_points(symbol, size)
        best_wall = None
        best_wall_d = float("inf")

        if wall_hint is not None and mounts:
            # When the cursor has acquired a wall, that locked wall is the
            # authoritative placement surface. Do not let a second parallel
            # line or a corner steal the mount point from underneath it.
            if best_symbol is not None:
                # Preserve the symbol-to-symbol along-wall position where possible,
                # but project the mount point onto the SAME locked wall segment.
                for lx,ly in mounts:
                    rx,ry=core.rotate_point(lx,ly,rot)
                    wx,wy=ox+rx,oy+ry
                    cand=self._wall_by_index(wall_hint[5],wx,wy,tol_wall*1.65)
                    if cand and cand[4]<best_wall_d:
                        best_wall=(cand,rx,ry); best_wall_d=cand[4]
            if best_wall is None:
                choices=[]
                for lx,ly in mounts:
                    rx,ry=core.rotate_point(lx,ly,rot)
                    tx,ty=wall_hint[0]-rx,wall_hint[1]-ry
                    choices.append((math.hypot(tx-ox,ty-oy),tx,ty,rx,ry))
                _,tx,ty,rx,ry=min(choices,key=lambda v:v[0])
                best_wall=(wall_hint,rx,ry)
                ox,oy=tx,ty
        else:
            # No cursor-acquired wall: retain the traditional mount-point search.
            for lx, ly in mounts:
                rx, ry = core.rotate_point(lx, ly, rot)
                wx, wy = ox+rx, oy+ry
                cand = self.nearest_wall(wx, wy, tol_wall)
                if cand and cand[4] < best_wall_d:
                    best_wall = (cand, rx, ry)
                    best_wall_d = cand[4]

        if best_wall is not None and not (wall_hint is not None and mounts and best_symbol is None):
            cand, rx, ry = best_wall
            ox += cand[0] - (ox+rx)
            oy += cand[1] - (oy+ry)
        if best_wall is not None:
            kind_parts.append("VÆG")

        return (ox, oy), rot, " + ".join(dict.fromkeys(kind_parts)) if kind_parts else ""

    def snap_connection(self, scene, raw_cad: tuple[float, float], view_scale: float, ignore_uid: str = "",
                        snap_symbols: bool = True, snap_walls: bool = True):
        """Snap a cable endpoint to symbol ports and/or visible CAD geometry."""
        scale = max(abs(float(view_scale)), 1e-9)
        tol_symbol = 24.0 / scale
        tol_wall = 20.0 / scale
        x, y = map(float, raw_cad)

        if snap_symbols:
            best = None
            best_d = float("inf")
            for item in self._nearby_symbols(scene, (x, y), max(tol_symbol * 2.0, 150.0), ignore_uid):
                for px, py, port in core.placement_connection_ports(item.placement):
                    d = math.hypot(px - x, py - y)
                    if d <= tol_symbol and d < best_d:
                        best = (px, py, "SYMBOL", item.placement.uid, int(port))
                        best_d = d
                if item.contains(item.mapFromScene(_mapped_point(x, y))):
                    ports = core.placement_connection_ports(item.placement)
                    if ports:
                        px, py, port = min(ports, key=lambda q: math.hypot(q[0]-x, q[1]-y))
                        d = math.hypot(px-x, py-y)
                        if d < best_d:
                            best = (px, py, "SYMBOL", item.placement.uid, int(port))
                            best_d = d
            if best is not None:
                return best

        if snap_walls:
            wall = self.nearest_wall(x, y, tol_wall)
            if wall is not None:
                return (wall[0], wall[1], "VÆG", "", 0)
        return (x, y, "", "", 0)


class ItemSignals(QObject):
    moved = Signal(object)
    clicked = Signal(object)
    doubleClicked = Signal(object)
    contextRequested = Signal(object, object)
    dragStarted = Signal(object, object)
    dragFinished = Signal(object, object, object)
    hoverEntered = Signal(object)
    hoverMoved = Signal(object, object)
    hoverLeft = Signal(object)


class ElectricalSymbolItem(QGraphicsItem):
    def __init__(self, placement: core.Placement):
        super().__init__()
        self.placement = placement
        self.signals = ItemSignals()
        self._primitives = core.symbol_primitives(placement.symbol, placement.size)
        self._bbox = self._make_bbox()
        self.snapper: Callable | None = None
        self._suppress_snap = False
        self._drag_start_pose = None
        self._dragging = False
        self._press_screen = None
        self.setPos(placement.x, -placement.y)
        self.setRotation(-placement.rotation)
        flags = QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        if not placement.locked:
            flags |= QGraphicsItem.GraphicsItemFlag.ItemIsMovable
        flags |= QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        self.setFlags(flags)
        self.setZValue(100)
        # Hover-info håndteres centralt i MainWindow, så vi kan styre delay og
        # vise PL-kabelindføringer/BOM uden at Qt's standard-tooltip blander sig.
        self.setAcceptHoverEvents(True)
        self.setToolTip("")
        # 0.56.1: short local animations only. They change presentation, never
        # geometry/project data, and therefore remain cheap even on large plans.
        self._hover_progress = 0.0
        self._selection_progress = 0.0
        self._hover_anim = QVariantAnimation()
        self._hover_anim.setDuration(120); self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(lambda value: self._set_visual_progress("hover", value))
        self._selection_anim = QVariantAnimation()
        self._selection_anim.setDuration(150); self._selection_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._selection_anim.valueChanged.connect(lambda value: self._set_visual_progress("selection", value))
        # The actual soft glow is created lazily on first hover/selection.
        # QGraphicsDropShadowEffect works in device pixels, so the halo remains
        # equally readable at whole-plan zoom and close-up without changing the
        # symbol geometry, hit area or project colours.
        self._glow_effect: QGraphicsDropShadowEffect | None = None
        # 0.57.0: a single click confirmation pulse. The ring ignores view
        # transformations, so the feedback remains subtle and legible at any zoom.
        self._pulse_ring: QGraphicsEllipseItem | None = None
        self._pulse_anim = QVariantAnimation()
        self._pulse_anim.setDuration(360); self._pulse_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._pulse_anim.valueChanged.connect(self._update_selection_pulse)

    def _ensure_glow_effect(self) -> QGraphicsDropShadowEffect:
        effect=self._glow_effect
        if effect is None:
            effect=QGraphicsDropShadowEffect()
            effect.setOffset(0.0,0.0)
            effect.setBlurRadius(12.0)
            effect.setColor(QColor(37,99,235,0))
            effect.setEnabled(False)
            self.setGraphicsEffect(effect)
            self._glow_effect=effect
        return effect

    def _ensure_pulse_ring(self) -> QGraphicsEllipseItem:
        ring=self._pulse_ring
        if ring is None:
            ring=QGraphicsEllipseItem(self)
            ring.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations,True)
            ring.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            ring.setZValue(-1)
            ring.setBrush(Qt.BrushStyle.NoBrush)
            ring.hide()
            self._pulse_ring=ring
        return ring

    def _update_selection_pulse(self,value) -> None:
        try:progress=max(0.0,min(1.0,float(value)))
        except Exception:progress=1.0
        ring=self._ensure_pulse_ring()
        center=self._bbox.center()
        radius=9.0+18.0*progress
        ring.setRect(QRectF(-radius,-radius,radius*2.0,radius*2.0))
        ring.setPos(center)
        color=QColor(105,181,245,int(175*(1.0-progress))) if _canvas_is_dark() else QColor(37,99,235,int(150*(1.0-progress)))
        pen=QPen(color); pen.setCosmetic(True); pen.setWidthF(2.0-0.8*progress)
        ring.setPen(pen); ring.setOpacity(max(0.0,1.0-progress)); ring.setVisible(progress<0.995)

    def _start_selection_pulse(self) -> None:
        self._pulse_anim.stop(); self._pulse_anim.setStartValue(0.0); self._pulse_anim.setEndValue(1.0); self._pulse_anim.start()

    def _update_glow_effect(self) -> None:
        hover=max(0.0,min(1.0,float(getattr(self,"_hover_progress",0.0))))
        selected=max(0.0,min(1.0,float(getattr(self,"_selection_progress",0.0))))
        # Hover should be immediately legible; selection is a little stronger
        # and persists while the item remains selected.
        mix=max(hover*0.88,selected)
        if mix<=0.005:
            if self._glow_effect is not None:
                self._glow_effect.setEnabled(False)
            return
        effect=self._ensure_glow_effect()
        base=QColor("#60a5fa") if _canvas_is_dark() else QColor("#2563eb")
        base.setAlpha(int(42+148*mix))
        effect.setColor(base)
        effect.setBlurRadius(7.0+10.0*mix)
        effect.setEnabled(True)

    def set_marking_mode(self, enabled: bool) -> None:
        self._marking_mode=bool(enabled)
        self.refresh(update_handles=False)

    def _set_visual_progress(self, kind: str, value) -> None:
        try:
            progress=max(0.0,min(1.0,float(value)))
        except Exception:
            progress=0.0
        if kind=="hover": self._hover_progress=progress
        else: self._selection_progress=progress
        self._update_glow_effect()
        self.update()

    @staticmethod
    def _animate_to(animation: QVariantAnimation, current: float, target: float) -> None:
        animation.stop(); animation.setStartValue(float(current)); animation.setEndValue(float(target)); animation.start()

    def _make_bbox(self) -> QRectF:
        x1, y1, x2, y2 = core.symbol_local_bbox(self.placement.symbol, self.placement.size)
        return QRectF(x1, -y2, max(x2 - x1, 1.0), max(y2 - y1, 1.0)).adjusted(-8, -8, 8, 8)

    def refresh_geometry(self) -> None:
        self.prepareGeometryChange()
        self._primitives = core.symbol_primitives(self.placement.symbol, self.placement.size)
        self._bbox = self._make_bbox()
        self._suppress_snap = True
        self.setRotation(-self.placement.rotation)
        self._suppress_snap = False
        self.update()

    def set_pose_silent(self, x: float, y: float, rotation: float) -> None:
        self._suppress_snap = True
        self.placement.x = float(x); self.placement.y = float(y); self.placement.rotation = float(rotation) % 360.0
        self.setPos(float(x), -float(y))
        self.setRotation(-self.placement.rotation)
        self._suppress_snap = False
        self.update()

    def boundingRect(self) -> QRectF:
        return self._bbox

    def paint(self, painter: QPainter, option, widget=None) -> None:
        color=QColor(self.placement.color or "#d00000")
        visual=max(float(getattr(self,"_hover_progress",0.0))*0.82,float(getattr(self,"_selection_progress",0.0)))
        if visual>0.01:
            painter.save()
            painter.setOpacity(min(0.55,0.16+visual*0.36))
            _draw_symbol_primitives(
                painter,self._primitives,
                QColor("#78b7ee") if _canvas_is_dark() else QColor("#2e7fbd"),
                True,self.placement.rotation,
            )
            painter.restore()
        if _canvas_is_dark() and not self.isSelected() and color.lightness() < 78:
            # Thin pale underlay keeps black/dark custom symbols visible while
            # the actual configured color remains on top and unchanged in data.
            painter.save()
            halo=_dark_canvas_contrast(color,preserve_hue=False)
            pen=QPen(halo); pen.setCosmetic(True); pen.setWidthF(4.0); pen.setCapStyle(Qt.PenCapStyle.RoundCap); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen); painter.setBrush(Qt.BrushStyle.NoBrush)
            for prim in self._primitives:
                try:
                    kind=prim[0]
                    if kind=="line": painter.drawLine(_mapped_point(prim[1],prim[2]),_mapped_point(prim[3],prim[4]))
                    elif kind=="circle": painter.drawEllipse(QRectF(prim[1]-prim[3],-prim[2]-prim[3],2*prim[3],2*prim[3]))
                    elif kind=="arc":
                        pts=_arc_points(prim[1],prim[2],prim[3],prim[4],prim[5]); path=QPainterPath(pts[0]) if pts else QPainterPath()
                        for pt in pts[1:]: path.lineTo(pt)
                        painter.drawPath(path)
                    elif kind=="polyline":
                        pts=[_mapped_point(x,y) for x,y in prim[1]]; path=QPainterPath(pts[0]) if pts else QPainterPath()
                        for pt in pts[1:]: path.lineTo(pt)
                        painter.drawPath(path)
                except Exception: pass
            painter.restore()
        _draw_symbol_primitives(
            painter, self._primitives, _dark_canvas_contrast(color),
            self.isSelected(), self.placement.rotation,
        )

    def hoverEnterEvent(self, event) -> None:
        self._animate_to(self._hover_anim,self._hover_progress,1.0)
        self.signals.hoverEntered.emit(self)
        super().hoverEnterEvent(event)

    def hoverMoveEvent(self, event) -> None:
        try:self.signals.hoverMoved.emit(self,event.screenPos())
        except Exception:pass
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self._animate_to(self._hover_anim,self._hover_progress,0.0)
        self.signals.hoverLeft.emit(self)
        super().hoverLeaveEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        self.signals.doubleClicked.emit(self)
        event.accept()

    def contextMenuEvent(self, event) -> None:
        self.signals.contextRequested.emit(self, event.screenPos())
        event.accept()

    def mousePressEvent(self, event) -> None:
        self.signals.clicked.emit(self)
        self._drag_start_pose = (float(self.placement.x), float(self.placement.y), float(self.placement.rotation))
        self._dragging = False
        try:
            self._press_screen = event.screenPos()
        except Exception:
            self._press_screen = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start_pose is not None and not self._dragging:
            try:
                delta = event.screenPos() - self._press_screen if self._press_screen is not None else None
                if delta is not None and delta.manhattanLength() >= 4:
                    self._dragging = True
                    self.signals.dragStarted.emit(self, self._drag_start_pose)
            except Exception:
                self._dragging = True
                self.signals.dragStarted.emit(self, self._drag_start_pose)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        if self._drag_start_pose is not None and self._dragging:
            end = (float(self.placement.x), float(self.placement.y), float(self.placement.rotation))
            self.signals.dragFinished.emit(self, self._drag_start_pose, end)
        self._drag_start_pose = None
        self._dragging = False
        self._press_screen = None

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            target=1.0 if bool(value) else 0.0
            self._animate_to(self._selection_anim,self._selection_progress,target)
            if bool(value):
                QTimer.singleShot(0,self._start_selection_pulse)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene() is not None and not self._suppress_snap:
            # A plain selection click must never change the symbol position.
            # QGraphicsItem can propose a tiny move before the user's gesture
            # has exceeded the drag threshold; reject that proposal.
            if self._drag_start_pose is not None and not self._dragging:
                return self.pos()
            if self._dragging and self.snapper:
                try:
                    snapped_pos, snapped_rot, _kind = self.snapper(self, value)
                    if snapped_rot is not None and abs(float(snapped_rot)-float(self.placement.rotation)) > 1e-9:
                        self._suppress_snap = True
                        self.placement.rotation = float(snapped_rot) % 360.0
                        self.setRotation(-self.placement.rotation)
                        self._suppress_snap = False
                    return snapped_pos
                except Exception:
                    pass
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self.scene() is not None:
            pos = value
            self.placement.x = float(pos.x())
            self.placement.y = float(-pos.y())
            self.signals.moved.emit(self)
        return super().itemChange(change, value)


class CableSignals(QObject):
    editStarted = Signal(object, object)
    editFinished = Signal(object, object, object)
    editRequested = Signal(object, object)
    selected = Signal(object)
    hoverEntered = Signal(object)
    hoverMoved = Signal(object, object)
    hoverLeft = Signal(object)
    contextRequested = Signal(object, object, object)


class CablePointHandle(QGraphicsEllipseItem):
    def __init__(self, owner, index: int, endpoint: bool, connection: bool = False):
        radius = 5.4 if (endpoint or connection) else 4.2
        super().__init__(-radius, -radius, radius * 2, radius * 2, owner)
        self.owner = owner
        self.index = int(index)
        self.endpoint = bool(endpoint)
        self.connection = bool(connection)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setZValue(20)
        self._moving = False
        self._syncing = False
        self._update_style()

    def _update_style(self):
        dark=_canvas_is_dark()
        if self.connection:
            pen = QPen(QColor("#57c98d") if dark else QColor("#0b7a4b")); fill=QColor("#234a39") if dark else QColor("#dff5e8")
            self.setToolTip("Fysisk kabeltilslutning – låst til symbol. Flyt symbolet for at flytte tilslutningen.")
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
            self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            pen = QPen(QColor("#73b9f0") if dark else QColor("#1263a5")); fill=(QColor("#222a32") if self.endpoint else QColor("#294663")) if dark else (QColor("#ffffff") if self.endpoint else QColor("#dcecff"))
            self.setToolTip("Kabelendepunkt" if self.endpoint else "Geometrisk knækpunkt")
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        pen.setCosmetic(True); pen.setWidthF(1.4)
        self.setPen(pen); self.setBrush(QBrush(fill))

    def mousePressEvent(self, event) -> None:
        if self.connection:
            # Grønne handles repræsenterer en fysisk tilslutning og er ankre,
            # ikke almindelige ruteknæk. Ruten redigeres via de blå handles.
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton and not self.endpoint and not self.connection:
            self.owner.begin_handle_edit()
            self.owner.remove_breakpoint(self.index)
            self.owner.finish_handle_edit()
            event.accept()
            return
        self._moving = True
        self.owner.begin_handle_edit()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        if self._moving:
            self.owner.finish_handle_edit()
        self._moving = False

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and not self._syncing:
            return self.owner.constrain_handle_position(self, value)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and not self._syncing:
            self.owner.handle_moved(self, value)
        return super().itemChange(change, value)

    def set_pos_silent(self, point: QPointF) -> None:
        self._syncing = True
        try:
            self.setPos(point)
        finally:
            self._syncing = False


class CableItem(QGraphicsPathItem):
    def __init__(self, cable: core.CablePlacement, snapper=None, scale_provider=None, visual_points_provider=None, length_text_provider=None):
        super().__init__()
        self.cable = cable
        self.snapper = snapper
        self.scale_provider = scale_provider
        self.visual_points_provider = visual_points_provider
        self.length_text_provider = length_text_provider
        # 0.44.3: MainWindow pushes the already calculated visual cable path
        # directly into the item.  This avoids stale/indirect cache lookups in
        # the render path and guarantees that a calculated parallel lane is the
        # path Qt actually paints.
        self._visual_points_override: list[tuple[float,float]] | None = None
        self.signals = CableSignals()
        self.handles: list[CablePointHandle] = []
        self._edit_before = None
        # MainWindow kan midlertidigt overtage et kabelklik til intuitive
        # værktøjer (fx kobling af et eksisterende lampested til kabelruten).
        # Callback returnerer True, når klikket er håndteret og normal selection
        # derfor ikke skal køre.
        self.click_handler = None
        self.setZValue(50)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self._hover_progress = 0.0
        self._selection_progress = 0.0
        self._chain_hover_progress = 0.0
        self._hover_anim = QVariantAnimation()
        self._hover_anim.setDuration(120); self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(lambda value: self._set_visual_progress("hover", value))
        self._selection_anim = QVariantAnimation()
        self._selection_anim.setDuration(150); self._selection_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._selection_anim.valueChanged.connect(lambda value: self._set_visual_progress("selection", value))
        self._chain_hover_anim = QVariantAnimation()
        self._chain_hover_anim.setDuration(145); self._chain_hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._chain_hover_anim.valueChanged.connect(lambda value: self._set_visual_progress("chain", value))
        # 0.59.45: a deliberately subdued halo can mark all physical pieces in
        # the same cable pull while one piece is hovered. It never receives input.
        self.chain_hover_halo = QGraphicsPathItem(self)
        self.chain_hover_halo.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.chain_hover_halo.setZValue(-3)
        self.chain_hover_halo.hide()
        # 0.56.0: selection gets a dedicated cosmetic halo and endpoint anchors.
        # They are children of the cable so focus opacity still applies as one unit.
        self.selection_halo = QGraphicsPathItem(self)
        self.selection_halo.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.selection_halo.setZValue(-2)
        # 0.57.0: animated direction trace. This is presentation-only and is
        # active solely while hovering/selecting the cable.
        self.flow_overlay = QGraphicsPathItem(self)
        self.flow_overlay.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.flow_overlay.setZValue(-1)
        self.flow_overlay.hide()
        self._trace_active=False
        self._flow_anim=QVariantAnimation()
        self._flow_anim.setDuration(900); self._flow_anim.setStartValue(0.0); self._flow_anim.setEndValue(1.0); self._flow_anim.setLoopCount(-1)
        self._flow_anim.valueChanged.connect(self._update_flow_progress)
        self.selection_endpoints = []
        for _ in range(2):
            marker = QGraphicsEllipseItem(QRectF(-4.5, -4.5, 9.0, 9.0), self)
            marker.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
            marker.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            marker.setZValue(3)
            marker.hide()
            self.selection_endpoints.append(marker)
        self.hover_badge_bg=QGraphicsRectItem(self)
        self.hover_badge_bg.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations,True)
        self.hover_badge_bg.setAcceptedMouseButtons(Qt.MouseButton.NoButton); self.hover_badge_bg.setZValue(5); self.hover_badge_bg.hide()
        self.hover_badge_text=QGraphicsSimpleTextItem(self)
        self.hover_badge_text.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations,True)
        self.hover_badge_text.setAcceptedMouseButtons(Qt.MouseButton.NoButton); self.hover_badge_text.setZValue(6); self.hover_badge_text.setFont(QFont("Segoe UI",8,QFont.Weight.DemiBold)); self.hover_badge_text.hide()
        # 0.59.0: opt-in graphical cable-marking status chip. It exists only as
        # presentation and never writes data by itself.
        self._marking_mode=False
        self.marking_badge_bg=QGraphicsRectItem(self)
        self.marking_badge_bg.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations,True)
        self.marking_badge_bg.setAcceptedMouseButtons(Qt.MouseButton.NoButton); self.marking_badge_bg.setZValue(7); self.marking_badge_bg.hide()
        self.marking_badge_text=QGraphicsSimpleTextItem(self)
        self.marking_badge_text.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations,True)
        self.marking_badge_text.setAcceptedMouseButtons(Qt.MouseButton.NoButton); self.marking_badge_text.setZValue(8); self.marking_badge_text.setFont(QFont("Segoe UI",8,QFont.Weight.DemiBold)); self.marking_badge_text.hide()
        self.label_item = QGraphicsSimpleTextItem(self)
        self.label_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.label_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.label_item.setBrush(QBrush(_canvas_text_color("#0f6a3e","#8ad0a9")))
        self.label_item.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        self.label_item.setZValue(1)
        self.section_spec_labels: list[QGraphicsSimpleTextItem] = []
        self.refresh()

    def _set_visual_progress(self, kind: str, value) -> None:
        try:
            progress=max(0.0,min(1.0,float(value)))
        except Exception:
            progress=0.0
        if kind=="hover": self._hover_progress=progress
        elif kind=="chain": self._chain_hover_progress=progress
        else: self._selection_progress=progress
        self.refresh(update_handles=False)

    def set_chain_highlight(self, active: bool) -> None:
        """Softly mark this piece as belonging to the currently hovered cable pull."""
        target=1.0 if bool(active) else 0.0
        self._animate_to(self._chain_hover_anim,self._chain_hover_progress,target)

    @staticmethod
    def _animate_to(animation: QVariantAnimation, current: float, target: float) -> None:
        animation.stop(); animation.setStartValue(float(current)); animation.setEndValue(float(target)); animation.start()

    def _update_flow_progress(self,value) -> None:
        try:progress=float(value)
        except Exception:progress=0.0
        pen=self.flow_overlay.pen()
        pen.setDashOffset(-progress*18.0)
        self.flow_overlay.setPen(pen)
        self.flow_overlay.update()

    def set_trace_active(self,active: bool) -> None:
        self._trace_active=bool(active); self._sync_flow_animation()

    def _sync_flow_animation(self) -> None:
        active=bool(self._trace_active or self.isSelected() or float(getattr(self,"_hover_progress",0.0))>0.08)
        if active:
            if self._flow_anim.state()!=QAbstractAnimation.State.Running:self._flow_anim.start()
            self.flow_overlay.show()
        else:
            self._flow_anim.stop(); self.flow_overlay.hide()

    @staticmethod
    def state(cable: core.CablePlacement) -> dict:
        return {
            "points": [tuple(map(float, p)) for p in cable.points],
            "layer": str(cable.layer),
            "line_width": float(cable.line_width),
            "color": core.normalize_hex_color(getattr(cable,"color",core.DEFAULT_CABLE_COLOR),core.DEFAULT_CABLE_COLOR),
            "line_style": core.normalize_cable_line_style(getattr(cable,"line_style",core.DEFAULT_CABLE_LINE_STYLE)),
            "cable_category": core.normalize_cable_category_id(getattr(cable,"cable_category",core.DEFAULT_CABLE_CATEGORY)),
            "label": str(cable.label),
            "cable_spec": str(cable.cable_spec),
            "cable_id": str(cable.cable_id),
            "circuit_id": str(getattr(cable,"circuit_id","") or ""),
            "route_chain_uid": str(getattr(cable,"route_chain_uid","") or ""),
            "auto_label": bool(cable.auto_label),
            "start_symbol_uid": str(cable.start_symbol_uid),
            "end_symbol_uid": str(cable.end_symbol_uid),
            "start_symbol_port": int(cable.start_symbol_port),
            "end_symbol_port": int(cable.end_symbol_port),
            "orthogonal": bool(cable.orthogonal),
            "route_section_modes": [dict(r) for r in core.normalize_cable_route_section_modes(getattr(cable,"route_section_modes",[]))],
            "spec_section_overrides": [dict(r) for r in core.normalize_cable_spec_section_overrides(
                getattr(cable,"spec_section_overrides",[]),getattr(cable,"cable_spec","")
            )],
            "symbol_connections": [dict(r) for r in core.cable_symbol_connections(cable)],
        }

    def set_visual_points(self, points, *, refresh: bool = False) -> None:
        """Set the exact cosmetic path that Qt must paint for this cable.

        The saved ``cable.points`` remain the authoritative physical centreline.
        Parallel-lane separation is display-only.  Keeping the display path on
        the item itself makes zoom/refresh behaviour deterministic and avoids a
        second cache lookup during ``paint``/``refresh``.
        """
        if points is None:
            self._visual_points_override = None
        else:
            self._visual_points_override = [(float(x),float(y)) for x,y in points]
        if refresh:
            self.refresh()

    def display_points(self) -> list[tuple[float,float]]:
        # While a handle is actively dragged, show the logical centreline so the
        # handle and edited geometry coincide exactly.  Selection alone must NOT
        # collapse a cable back onto the centreline; doing so can visually merge
        # parallel cables again after a selection/refresh cycle.
        if self._edit_before is not None:
            return [(float(x),float(y)) for x,y in self.cable.points]
        if self._visual_points_override:
            return list(self._visual_points_override)
        # Backward-compatible fallback for callers/tests that still provide a
        # provider instead of an explicit path.
        if callable(self.visual_points_provider):
            try:
                pts=self.visual_points_provider(self.cable)
                if pts:
                    return [(float(x),float(y)) for x,y in pts]
            except Exception:
                pass
        return [(float(x),float(y)) for x,y in self.cable.points]

    def refresh(self, update_handles: bool = True) -> None:
        path = QPainterPath()
        display_points=self.display_points()
        if display_points:
            path.moveTo(_mapped_point(*display_points[0]))
            for p in display_points[1:]:
                path.lineTo(_mapped_point(*p))
        self.setPath(path)
        selected = self.isSelected()
        selection_mix=max(float(getattr(self,"_selection_progress",0.0)),0.06 if selected else 0.0)
        hover_mix=float(getattr(self,"_hover_progress",0.0))
        halo_mix=max(selection_mix,hover_mix*0.58)
        self.chain_hover_halo.setPath(path)
        self.selection_halo.setPath(path)
        self.flow_overlay.setPath(path)
        chain_mix=float(getattr(self,"_chain_hover_progress",0.0))
        if chain_mix>0.01:
            # The complete pull must be noticeable only after the user looks for it:
            # a wide but very transparent cosmetic stroke behind the actual cable.
            alpha=int((42 if _canvas_is_dark() else 32)*chain_mix)
            chain_color=QColor(112,190,240,alpha) if _canvas_is_dark() else QColor(33,112,181,alpha)
            chain_pen=QPen(chain_color); chain_pen.setCosmetic(True); chain_pen.setWidthF(7.0)
            chain_pen.setCapStyle(Qt.PenCapStyle.RoundCap); chain_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            self.chain_hover_halo.setPen(chain_pen); self.chain_hover_halo.show()
        else:
            self.chain_hover_halo.hide()
        flow_color=QColor(133,205,255,150) if _canvas_is_dark() else QColor(37,99,235,132)
        flow_pen=QPen(flow_color); flow_pen.setCosmetic(True); flow_pen.setWidthF(2.15); flow_pen.setCapStyle(Qt.PenCapStyle.RoundCap); flow_pen.setDashPattern([1.8,5.2])
        self.flow_overlay.setPen(flow_pen)
        self._sync_flow_animation()
        if halo_mix>0.01:
            alpha=int((96 if _canvas_is_dark() else 78)*halo_mix)
            halo_color = QColor(101,174,240,alpha) if _canvas_is_dark() else QColor(23,111,193,alpha)
            halo_pen = QPen(halo_color)
            halo_pen.setCosmetic(True)
            # 0.56.0 baseline was: halo_pen.setWidthF(8.0). 0.56.1 eases up to the same width.
            halo_pen.setWidthF(5.5+2.5*halo_mix)
            halo_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            halo_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            self.selection_halo.setPen(halo_pen)
            self.selection_halo.show()
        else:
            self.selection_halo.hide()
        endpoint_mix=selection_mix
        if endpoint_mix>0.01:
            endpoint_pen = QPen(QColor("#9bd0ff") if _canvas_is_dark() else QColor("#176fc1"))
            endpoint_pen.setCosmetic(True); endpoint_pen.setWidthF(1.7)
            endpoint_brush = QBrush(QColor("#263d54") if _canvas_is_dark() else QColor("#ffffff"))
            for marker, point in zip(self.selection_endpoints, (display_points[:1] + display_points[-1:]) if display_points else []):
                marker.setPen(endpoint_pen); marker.setBrush(endpoint_brush); marker.setOpacity(endpoint_mix)
                marker.setPos(_mapped_point(*point)); marker.show()
        else:
            for marker in self.selection_endpoints:
                marker.hide()
        cable_color=core.normalize_hex_color(getattr(self.cable,"color",core.DEFAULT_CABLE_COLOR),core.DEFAULT_CABLE_COLOR)
        display_color=_dark_canvas_contrast(QColor(cable_color))
        pen = QPen(QColor("#65aef0") if (selected and _canvas_is_dark()) else (QColor("#176fc1") if selected else display_color))
        pen.setCosmetic(True)
        base_width=max(3.0 if selected else 1.4, min(5.2 if selected else 4.5, float(self.cable.line_width) * (2.35 if selected else 1.9)))
        pen.setWidthF(base_width + (0.55 * hover_mix if not selected else 0.0))
        pen.setStyle(_qt_cable_pen_style(getattr(self.cable,"line_style",core.DEFAULT_CABLE_LINE_STYLE)))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        self.setPen(pen)
        label = core.cable_plan_label(self.cable)
        # Floating inspection badge: useful even when permanent cable labels are hidden.
        # Hover information is shown beside the mouse by MainWindow. Keep the
        # in-scene badge only for an explicitly selected cable so overview zoom
        # does not accumulate two competing labels.
        badge_mix=0.0 if self._marking_mode else selection_mix
        if display_points and badge_mix>0.12:
            bx,by=core.polyline_label_point(display_points)
            cable_id=str(getattr(self.cable,"cable_id","") or "Kabel")
            spec=str(getattr(self.cable,"cable_spec","") or "—")
            circuit=str(getattr(self.cable,"circuit_id","") or "").strip()
            extra=str(getattr(self.cable,"label","") or "").strip()
            length_text=""
            if callable(self.length_text_provider):
                try:
                    length_text=str(self.length_text_provider(self.cable) or "").strip()
                except Exception:
                    length_text=""
            badge_text=" · ".join(x for x in (cable_id,spec,length_text,circuit,extra) if x)
            self.hover_badge_text.setText(badge_text)
            self.hover_badge_text.setBrush(QBrush(_canvas_text_color("#173f68","#dceeff")))
            tr=self.hover_badge_text.boundingRect().adjusted(-7,-3,7,3)
            self.hover_badge_bg.setRect(tr)
            self.hover_badge_bg.setPen(QPen(QColor("#9ebbe0") if not _canvas_is_dark() else QColor("#55779c"),1.0))
            self.hover_badge_bg.setBrush(QBrush(QColor(255,255,255,238) if not _canvas_is_dark() else QColor(32,36,42,238)))
            pos=_mapped_point(bx,by)+QPointF(10,-34)
            self.hover_badge_bg.setPos(pos); self.hover_badge_text.setPos(pos+QPointF(7,3))
            self.hover_badge_bg.setOpacity(min(1.0,badge_mix)); self.hover_badge_text.setOpacity(min(1.0,badge_mix)); self.hover_badge_bg.show(); self.hover_badge_text.show()
        else:
            self.hover_badge_bg.hide(); self.hover_badge_text.hide()
        # Mærkningstilstand: one compact chip per physical cable. Unmarked cables
        # show '+'; marked cables show the approved extra marking. The chip does
        # not accept mouse input, so the cable itself remains the click target.
        if self._marking_mode and display_points:
            mx,my=core.polyline_label_point(display_points)
            approved=str(getattr(self.cable,"label","") or "").strip()
            chip=(approved[:30]+"…") if len(approved)>31 else (approved or "+")
            self.marking_badge_text.setText(chip)
            dark=_canvas_is_dark()
            marked=bool(approved)
            self.marking_badge_text.setBrush(QBrush(QColor("#d9fbe8") if dark and marked else QColor("#fff4cc") if dark else QColor("#14532d") if marked else QColor("#92400e")))
            br=self.marking_badge_text.boundingRect().adjusted(-8,-4,8,4)
            self.marking_badge_bg.setRect(br)
            border=QColor("#36a269") if marked else QColor("#d59a2f")
            fill=QColor(25,67,48,242) if dark and marked else (QColor(80,58,20,242) if dark else (QColor(236,253,245,246) if marked else QColor(255,251,235,246)))
            self.marking_badge_bg.setPen(QPen(border,1.2)); self.marking_badge_bg.setBrush(QBrush(fill))
            pos=_mapped_point(mx,my)+QPointF(9,9)
            self.marking_badge_bg.setPos(pos); self.marking_badge_text.setPos(pos+QPointF(8,4))
            self.marking_badge_bg.show(); self.marking_badge_text.show()
        else:
            self.marking_badge_bg.hide(); self.marking_badge_text.hide()
        self.label_item.setText(label)
        self.label_item.setBrush(QBrush(_canvas_text_color("#0f6a3e","#8ad0a9")))
        if display_points and label:
            x, y = core.polyline_label_point(display_points)
            self.label_item.setPos(_mapped_point(x, y) + QPointF(7, -17))
            self.label_item.show()
        else:
            self.label_item.hide()
        # Ved blandede kabeltyper får hvert fysisk afsnit en lille type-label.
        # Det gør fx 3G1,5 → 5G1,5 synligt direkte på plantegningen uden at
        # ændre kabel-ID'et eller oprette flere kunstige kabelobjekter.
        section_labels=core.cable_section_spec_labels(self.cable)
        while len(self.section_spec_labels)<len(section_labels):
            item=QGraphicsSimpleTextItem(self)
            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations,True)
            item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            item.setFont(QFont("Segoe UI",7,QFont.Weight.DemiBold))
            item.setZValue(2)
            self.section_spec_labels.append(item)
        label_points=display_points if len(display_points)==len(getattr(self.cable,"points",[]) or []) else list(getattr(self.cable,"points",[]) or [])
        for index,item in enumerate(self.section_spec_labels):
            if index>=len(section_labels):
                item.hide(); continue
            rec=section_labels[index]; section=rec.get("section",{})
            start=int(section.get("start_point_index",0) or 0); end=int(section.get("end_point_index",0) or 0)
            if 0<=start<end<len(label_points):
                x,y=core.polyline_label_point(label_points[start:end+1])
            else:
                x,y=rec.get("point",(0.0,0.0))
            item.setText(str(rec.get("cable_spec") or ""))
            item.setBrush(QBrush(_canvas_text_color("#7c3f00","#ffc47a")))
            item.setPos(_mapped_point(x,y)+QPointF(7,2))
            item.show()
        if update_handles:
            if selected:
                self.show_handles()
            else:
                self.hide_handles()

    def shape(self):
        stroker=QPainterPathStroker()
        try:
            scale=max(abs(float(self.scale_provider())),1e-9) if callable(self.scale_provider) else 1.0
        except Exception:
            scale=1.0
        stroker.setWidth(max(8.0/scale, float(self.cable.line_width)*2.0))
        return stroker.createStroke(self.path())

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            QTimer.singleShot(0, self._selection_refresh)
        return super().itemChange(change, value)

    def _selection_refresh(self) -> None:
        target=1.0 if self.isSelected() else 0.0
        self._animate_to(self._selection_anim,self._selection_progress,target)
        self._sync_flow_animation()
        self.refresh()
        if self.isSelected():
            self.signals.selected.emit(self)

    def hoverEnterEvent(self, event) -> None:
        self._animate_to(self._hover_anim,self._hover_progress,1.0)
        if self._flow_anim.state()!=QAbstractAnimation.State.Running:self._flow_anim.start()
        self.flow_overlay.show()
        self.signals.hoverEntered.emit(self)
        super().hoverEnterEvent(event)

    def hoverMoveEvent(self, event) -> None:
        try:self.signals.hoverMoved.emit(self,event.screenPos())
        except Exception:pass
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        self._animate_to(self._hover_anim,self._hover_progress,0.0)
        QTimer.singleShot(160,self._sync_flow_animation)
        self.signals.hoverLeft.emit(self)
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and callable(self.click_handler):
            try:
                if bool(self.click_handler(self, event.scenePos())):
                    event.accept()
                    return
            except Exception:
                pass
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        self.setSelected(True)
        self.signals.editRequested.emit(self, event.scenePos())
        event.accept()

    def contextMenuEvent(self, event) -> None:
        self.setSelected(True)
        self.signals.contextRequested.emit(self,event.scenePos(),event.screenPos())
        event.accept()

    def _point_orthogonal(self, index: int) -> bool:
        return core.cable_route_mode_for_point_index(self.cable,int(index)) == "orthogonal"

    def hide_handles(self) -> None:
        for handle in self.handles:
            if handle.scene() is not None:
                handle.hide()

    def show_handles(self) -> None:
        connection_indices={int(r.get("point_index",-1)) for r in core.cable_symbol_connections(self.cable)}
        if len(self.handles) != len(self.cable.points):
            for h in self.handles:
                if h.scene() is not None:
                    h.setParentItem(None); h.scene().removeItem(h)
            self.handles = []
            for index, point in enumerate(self.cable.points):
                endpoint = index in (0, len(self.cable.points)-1)
                h = CablePointHandle(self, index, endpoint, index in connection_indices)
                self.handles.append(h)
        for index, (x, y) in enumerate(self.cable.points):
            h = self.handles[index]
            h.index = index
            h.endpoint = index in (0, len(self.cable.points)-1)
            h.connection = index in connection_indices
            h._update_style()
            h.set_pos_silent(_mapped_point(x, y))
            h.show()

    def begin_handle_edit(self) -> None:
        if self._edit_before is None:
            self._edit_before = self.state(self.cable)
            self.signals.editStarted.emit(self, self._edit_before)

    def finish_handle_edit(self) -> None:
        if self._edit_before is None:
            return
        before = self._edit_before
        self._edit_before = None
        self.refresh(update_handles=True)
        after = self.state(self.cable)
        # Always notify the owner on mouse release so temporary snap guides are
        # cleared even when the handle ended exactly where it started.
        self.signals.editFinished.emit(self, before, after)

    def constrain_handle_position(self, handle: CablePointHandle, proposed: QPointF) -> QPointF:
        index = int(handle.index)
        before=self._edit_before or {}
        base_points=list(before.get("points",[tuple(p) for p in self.cable.points]))
        base_connections=core.normalize_cable_symbol_connections(
            before.get("symbol_connections",core.cable_symbol_connections(self.cable)),len(base_points)
        )
        locked_indices={int(r.get("point_index",-1)) for r in base_connections}
        # Fysiske forbindelser er absolutte ankre. Selv hvis Qt mod forventning
        # sender en positionsændring, returneres den gemte symbolposition.
        if index in locked_indices and 0 <= index < len(base_points):
            x,y=base_points[index]
            handle._snap_connection=(
                str(core.cable_connection_at(self.cable,index).get("symbol_uid","") if core.cable_connection_at(self.cable,index) else ""),
                int(core.cable_connection_at(self.cable,index).get("symbol_port",0) if core.cable_connection_at(self.cable,index) else 0),
                "SYMBOL",
            )
            return _mapped_point(x,y)
        x, y = _cad_point(proposed)
        # Et tidligere symbol-snap må ikke hænge ved, når håndtaget trækkes væk igen.
        handle._snap_connection = ("", 0, "")
        if callable(self.snapper):
            try:
                result = self.snapper(self, index, (x, y))
                x, y = result[0], result[1]
                uid = str(result[2] or "") if len(result) > 2 else ""
                port = int(result[3] or 0) if len(result) > 3 else 0
                kind = str(result[4] or "") if len(result) > 4 else ""
                handle._snap_connection = (uid, port, kind)
            except Exception:
                pass
        x,y=core.constrain_polyline_target_to_locked_neighbors(
            base_points,index,(x,y),locked_indices,self._point_orthogonal(index)
        )
        return _mapped_point(x, y)

    def handle_moved(self, handle: CablePointHandle, scene_value: QPointF) -> None:
        index=int(handle.index)
        if not (0 <= index < len(self.cable.points)):
            return
        x,y=_cad_point(scene_value)
        before=self._edit_before or {}
        base_points=list(before.get("points",[tuple(p) for p in self.cable.points]))
        base_connections=core.normalize_cable_symbol_connections(
            before.get("symbol_connections",core.cable_symbol_connections(self.cable)),len(base_points)
        )
        locked_indices={int(r.get("point_index",-1)) for r in base_connections}
        if index in locked_indices:
            # Fysiske symbolankre er absolutte. Brugeren redigerer ruten via de
            # blå knækpunkter; et grønt anker flyttes kun sammen med symbolet.
            self.cable.points=base_points
            core.set_cable_symbol_connections(self.cable,base_connections)
            self.refresh(update_handles=False)
            return

        # 0.43.3: Flyt det valgte frie punkt, men behold alle eksisterende naboer
        # som fast geometri. Ved 90°-føring indsættes lokale doglegs i stedet for
        # at fryse et knæk mellem to symbolankre.
        if index in (0,len(base_points)-1):
            moved,effective_index,delta=core.move_polyline_endpoint_flexible(
                base_points,index,(x,y),self._point_orthogonal(index)
            )
            rows=[]
            for row in base_connections:
                rec=dict(row); old_i=int(rec["point_index"])
                if index==0 and old_i>0:
                    rec["point_index"]=old_i+delta
                # Ved redigering af sidste frie endepunkt indsættes et eventuelt
                # dogleg umiddelbart før enden. Der findes ingen forbindelse på
                # selve den frie ende, og tidligere ankre beholder deres indeks.
                rows.append(rec)
        else:
            moved,effective_index,delta=core.move_polyline_vertex_flexible(
                base_points,index,(x,y),self._point_orthogonal(index)
            )
            rows=[]
            for row in base_connections:
                rec=dict(row); old_i=int(rec["point_index"])
                if old_i>index:
                    rec["point_index"]=old_i+delta
                rows.append(rec)

        self.cable.points=moved
        core.set_cable_symbol_connections(self.cable,rows)
        snap=getattr(handle,"_snap_connection",("",0,""))
        uid,port,kind=snap if len(snap)==3 else ("",0,"")
        core.replace_cable_connection(
            self.cable,effective_index,uid if kind=="SYMBOL" else "",port if kind=="SYMBOL" else 0
        )
        # Det aktive Qt-handle lever til mouseRelease. Ved release bygges hele
        # handle-sættet igen, så eventuelle nye dogleg-punkter bliver synlige.
        self.refresh(update_handles=False)

    def insert_breakpoint(self, scene_point: QPointF) -> bool:
        if len(self.cable.points) < 2:
            return False
        x, y = _cad_point(scene_point)
        best_i = None
        best_d = float("inf")
        best_pt = None
        for i, (a, b) in enumerate(zip(self.cable.points, self.cable.points[1:])):
            ax,ay=a; bx,by=b
            dx=bx-ax; dy=by-ay
            den=dx*dx+dy*dy
            if den <= 1e-12:
                px,py=ax,ay
            else:
                q=max(0.0,min(1.0,((x-ax)*dx+(y-ay)*dy)/den))
                px,py=ax+q*dx,ay+q*dy
            d=math.hypot(px-x,py-y)
            if d<best_d:
                best_d=d; best_i=i+1; best_pt=(px,py)
        if best_i is None:
            return False
        self.cable.points.insert(best_i,best_pt)
        core.shift_cable_connection_indices(self.cable,best_i,1)
        self.refresh()
        return True

    def remove_breakpoint(self, index: int) -> bool:
        if index <= 0 or index >= len(self.cable.points)-1 or len(self.cable.points) <= 2:
            return False
        if core.cable_connection_at(self.cable,index):
            return False
        prev=self.cable.points[index-1]
        nxt=self.cable.points[index+1]
        local_orthogonal=self._point_orthogonal(index)
        self.cable.points.pop(index)
        if local_orthogonal and not (math.isclose(prev[0],nxt[0]) or math.isclose(prev[1],nxt[1])):
            # Erstat det slettede geometriske hjørne med et nyt på samme indeks;
            # fysiske tilslutninger længere henne beholder derfor deres indeks.
            candidate=(nxt[0],prev[1])
            self.cable.points.insert(index,candidate)
        else:
            core.shift_cable_connection_indices(self.cable,index+1,-1)
        core.set_cable_symbol_connections(self.cable,core.cable_symbol_connections(self.cable))
        self.refresh()
        return True



class AnnotationItem(QGraphicsItemGroup):
    """Reliable screen-space annotation composed of native Qt graphics items.

    Gruppe/kreds = primary identifier.
    Optional Mærkning = secondary chip.
    a/b/c = blue association chip.
    Spot parent = teal link chip.
    """

    def __init__(self, placement: core.Placement, edit_callback=None, symbol_item=None,
                 scale_provider=None, mode_provider=None, spot_parent_provider=None,
                 position_direction_provider=None):
        super().__init__()
        self.placement = placement
        self.edit_callback = edit_callback
        self.symbol_item = symbol_item
        self.scale_provider = scale_provider
        self.mode_provider = mode_provider
        self.spot_parent_provider = spot_parent_provider
        self.position_direction_provider = position_direction_provider
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setHandlesChildEvents(False)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setZValue(500)
        self._children = []
        self._render_signature = None
        self.refresh()

    def _scale(self) -> float:
        try:
            return max(abs(float(self.scale_provider())),1e-9) if callable(self.scale_provider) else 1.0
        except Exception:
            return 1.0

    def _mode(self) -> str:
        try:
            mode=str(self.mode_provider() if callable(self.mode_provider) else "Auto")
        except Exception:
            mode="Auto"
        return mode if mode in ("Auto","Tydelig","Minimal","Skjult") else "Auto"

    def _is_selected(self) -> bool:
        return bool(self.symbol_item is not None and self.symbol_item.isSelected())

    @staticmethod
    def _csv_parts(value: str) -> list[str]:
        return [x.strip() for x in str(value or "").split(",")]

    def _compact_combo_group(self) -> str:
        p=self.placement
        groups=self._csv_parts(getattr(p,"switch_group","") or "")
        parts=[]
        for i,group in enumerate(groups,1):
            if group:
                parts.append(f"A{i}:{group}")
        socket=str(getattr(p,"socket_group","") or "").strip()
        if socket:
            parts.append(f"S:{socket}")
        return "  ".join(parts)

    def _combo_detail_lines(self) -> list[str]:
        p=self.placement
        groups=self._csv_parts(getattr(p,"switch_group","") or "")
        labels=self._csv_parts(getattr(p,"switch_label","") or "")
        count=max(len(groups),len(labels))
        lines=[]
        for i in range(count):
            group=groups[i] if i < len(groups) else ""
            label=labels[i] if i < len(labels) else ""
            bits=[x for x in (group,label) if x]
            if bits:
                lines.append(f"A{i+1}: " + " · ".join(bits))
        socket_group=str(getattr(p,"socket_group","") or "").strip()
        socket_label=str(getattr(p,"socket_label","") or "").strip()
        bits=[x for x in (socket_group,socket_label) if x]
        if bits:
            lines.append("S: " + " · ".join(bits))
        return lines

    def _spot_parent_text(self) -> str:
        if self.placement.symbol != "spot" or not getattr(self.placement,"parent_light_uid",""):
            return ""
        try:
            return str(self.spot_parent_provider(self.placement) or "") if callable(self.spot_parent_provider) else "↳ Lampested"
        except Exception:
            return "↳ Lampested"

    def _content(self):
        p=self.placement
        mode=self._mode()
        scale=self._scale()
        selected=self._is_selected()

        # “Skjult” is absolute: selection does not make labels reappear.
        if mode=="Skjult":
            return "","","",[],""

        assoc=core.association_display(p)
        # Switch relations are rendered next to the physical switch/module by
        # MainWindow. Keeping them out of the room-positioned annotation avoids
        # a misleading combined a/b/c label on multi-module combo switches.
        if core.association_role(p.symbol)=="switch":
            assoc=""
        group=str(getattr(p,"group","") or "").strip()
        label=str(getattr(p,"label","") or "").strip()
        primary=group or label
        secondary=label if group and label else ""

        # Semantic zoom in Auto mode:
        #   <0.055  extreme zoom-out: no persistent annotation
        #   0.055–0.145 whole-plan/overview: primary + compact a/b/c relation
        #   0.145–0.19 working zoom: primary + optional label + relation
        #   >=0.19 detail: spot parent and remaining details are also visible
        # Selecting a symbol temporarily reveals full information.
        if mode=="Auto" and scale<0.055 and not selected:
            return "","","",[],""

        if mode=="Minimal":
            secondary=""
            assoc=""

        show_secondary = bool(secondary) and (
            mode=="Tydelig" or selected or (mode=="Auto" and scale>=0.145)
        )
        # a/b/c is useful even in the whole-plan view.  In Auto it becomes
        # visible as soon as the primary annotation is visible; refresh()
        # renders it without a chip at overview zoom to keep visual noise low.
        show_assoc = bool(assoc) and (
            mode=="Tydelig" or selected or (mode=="Auto" and scale>=0.055)
        )

        split_combo = core.is_combo_symbol(p.symbol) and core.normalize_combo_label_mode(getattr(p,"label_mode","Fælles"))=="Opdelt"
        extra=[]
        if split_combo:
            if mode=="Tydelig" or selected or (mode=="Auto" and scale>=0.20):
                extra=self._combo_detail_lines()
                primary=""
                secondary=""
            else:
                primary=self._compact_combo_group() or primary
                secondary=""

        spot_parent=self._spot_parent_text()
        if not (mode=="Tydelig" or selected or (mode=="Auto" and scale>=0.21)):
            spot_parent=""
        if mode=="Minimal":
            spot_parent=""

        return primary,(secondary if show_secondary else ""),(assoc if show_assoc else ""),extra,spot_parent

    @staticmethod
    def _font(size: float, weight=QFont.Weight.Normal) -> QFont:
        f=QFont("Segoe UI")
        f.setPointSizeF(size)
        f.setWeight(weight)
        return f

    def _clear_children(self) -> None:
        for child in list(self.childItems()):
            child.setParentItem(None)
            if child.scene() is not None:
                child.scene().removeItem(child)

    def _add_text(self,text,x,y,font,color):
        item=QGraphicsSimpleTextItem(text,self)
        item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        item.setFont(font)
        item.setBrush(QBrush(color))
        item.setPos(x,y)
        return item

    def _add_chip(self,text,x,y,font,text_color,fill,border,pad_x=5,pad_y=2,radius=4):
        fm=QFontMetricsF(font)
        w=max(20.0,fm.horizontalAdvance(text)+2*pad_x)
        h=fm.height()+2*pad_y
        path=QPainterPath()
        path.addRoundedRect(QRectF(0,0,w,h),radius,radius)
        bg=QGraphicsPathItem(path,self)
        bg.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        pen=QPen(border); pen.setCosmetic(True); pen.setWidthF(1.0)
        bg.setPen(pen); bg.setBrush(QBrush(fill)); bg.setPos(x,y)
        txt=QGraphicsSimpleTextItem(text,bg)
        txt.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        txt.setFont(font); txt.setBrush(QBrush(text_color)); txt.setPos(pad_x,pad_y)
        return bg,w,h

    def _visual_profile(self):
        return core.annotation_visual_profile(self._mode(), self._scale(), self._is_selected())

    def refresh(self) -> None:
        primary,secondary,assoc,extra,spot_parent=self._content()
        profile=self._visual_profile()
        mode=self._mode(); scale=self._scale(); selected=self._is_selected()
        quiet_primary = (mode=="Minimal" or (mode=="Auto" and scale<0.145)) and not selected
        dark=_canvas_is_dark()
        quiet_assoc = bool(assoc) and mode=="Auto" and scale<0.145 and not selected
        profile_signature=tuple(
            (key,tuple(value) if isinstance(value,(list,tuple)) else value)
            for key,value in sorted(profile.items())
        )
        render_signature=(
            primary,secondary,assoc,tuple(extra),spot_parent,
            mode,selected,dark,quiet_primary,quiet_assoc,profile_signature,
        )
        has_content=bool(primary or secondary or assoc or extra or spot_parent)
        symbol_visible=True if self.symbol_item is None else self.symbol_item.isVisible()
        if render_signature==self._render_signature:
            # Zoom inside the same semantic profile only changes the scene-space
            # position.  Reuse the native text/path children instead of deleting
            # and recreating several QGraphicsItems per symbol.
            self.reposition()
            self.setVisible(has_content and symbol_visible)
            return

        self._clear_children()
        self._render_signature=render_signature
        x=0.0; y=0.0
        row_h=0.0
        alpha=int(profile["alpha"])
        primary_text=QColor("#b8e0cf") if dark else QColor("#174e39")
        primary_quiet=QColor(170,214,194,220) if dark else QColor(45,82,66,205)
        primary_fill=QColor(38,52,47,alpha) if dark else QColor(255,255,255,alpha)
        primary_border=QColor(89,122,107,min(220,alpha)) if dark else QColor(160,180,169,min(215,alpha))
        secondary_text=QColor("#c2cbd0") if dark else QColor("#69736f")
        secondary_fill=QColor(44,49,55,max(185,alpha-10)) if dark else QColor(248,249,249,max(170,alpha-12))
        secondary_border=QColor(82,91,99,max(170,alpha-20)) if dark else QColor(207,213,210,max(155,alpha-25))
        assoc_text=QColor(150,197,238,230) if dark else QColor(49,96,139,225)
        assoc_fill=QColor(37,56,75,max(185,alpha-15)) if dark else QColor(237,245,252,max(165,alpha-20))
        assoc_border=QColor(77,112,145,max(170,alpha-20)) if dark else QColor(135,171,202,max(155,alpha-28))
        spot_text=QColor(135,208,200,230) if dark else QColor(43,107,104,225)
        spot_fill=QColor(35,61,59,max(185,alpha-15)) if dark else QColor(237,248,247,max(165,alpha-20))
        spot_border=QColor(70,126,121,max(170,alpha-20)) if dark else QColor(151,194,191,max(155,alpha-28))

        if extra:
            font=self._font(profile["primary"]*.90,QFont.Weight.DemiBold)
            for line in extra:
                _bg,w,h=self._add_chip(
                    line,0,y,font,primary_text,
                    primary_fill,primary_border,
                    profile["pad_small"][0],profile["pad_small"][1],4
                )
                y+=h+profile["row_gap"]
        else:
            if primary:
                font=self._font(profile["primary"],QFont.Weight.DemiBold if quiet_primary else QFont.Weight.Bold)
                if quiet_primary:
                    txt=self._add_text(primary,x,y,font,primary_quiet)
                    br=txt.boundingRect(); w=br.width(); h=br.height()
                else:
                    _bg,w,h=self._add_chip(
                        primary,x,y,font,primary_text,
                        primary_fill,primary_border,
                        profile["pad_primary"][0],profile["pad_primary"][1],4
                    )
                x+=w+profile["gap"]
                row_h=max(row_h,h)
            if secondary:
                font=self._font(profile["secondary"],QFont.Weight.Medium)
                _bg,w,h=self._add_chip(
                    secondary,x,y,font,secondary_text,
                    secondary_fill,secondary_border,
                    profile["pad_small"][0],profile["pad_small"][1],4
                )
                x+=w
                row_h=max(row_h,h)
            if primary or secondary:
                y+=row_h+profile["row_gap"]

        if assoc:
            if quiet_assoc:
                # Whole-plan Auto view: keep the relation readable but do not
                # re-introduce the blue badge blocks that previously dominated
                # the drawing.  A compact screen-space text line is enough.
                font=self._font(max(4.8,profile["assoc"]*.90),QFont.Weight.DemiBold)
                quiet_color=QColor(139,185,224,205) if dark else QColor(49,96,139,190)
                txt=self._add_text(assoc,0,y,font,quiet_color)
                br=txt.boundingRect(); h=br.height()
            else:
                font=self._font(profile["assoc"],QFont.Weight.DemiBold)
                _bg,w,h=self._add_chip(
                    assoc,0,y,font,assoc_text,
                    assoc_fill,assoc_border,
                    profile["pad_small"][0],profile["pad_small"][1],5
                )
            y+=h+profile["row_gap"]

        if spot_parent:
            font=self._font(profile["spot"],QFont.Weight.Medium)
            _bg,w,h=self._add_chip(
                spot_parent,0,y,font,spot_text,
                spot_fill,spot_border,
                profile["pad_small"][0],profile["pad_small"][1],5
            )
            y+=h

        self.reposition()
        self.setVisible(has_content and symbol_visible)

    def reposition(self) -> None:
        scale=self._scale()
        if self.symbol_item is not None and self.symbol_item.scene() is not None:
            rect=self.symbol_item.sceneBoundingRect()
        else:
            rect=QRectF(self.placement.x,-self.placement.y,1,1)

        try:
            dx,dy=self.position_direction_provider(self.placement) if callable(self.position_direction_provider) else (1.0,0.0)
            dx=float(dx); dy=float(dy)
        except Exception:
            dx,dy=1.0,0.0
        length=math.hypot(dx,dy)
        if length<1e-9:
            dx,dy=1.0,0.0
        else:
            dx/=length; dy/=length

        # Local annotation dimensions are screen-space because this item ignores
        # transformations. Convert them to scene units only for positioning.
        bounds=self.boundingRect()
        visual_w=max(1.0,bounds.width())/scale
        visual_h=max(1.0,bounds.height())/scale

        # Fixed visual gap, slightly reduced in whole-plan overview.
        gap_px=3.5 if (self._mode()=="Auto" and scale<0.145 and not self._is_selected()) else 7.0
        gap=gap_px/scale

        # Use the dominant room direction. Horizontal placement is preferred
        # because these annotations are short and easier to scan beside walls.
        if abs(dx)>=abs(dy):
            if dx>=0:
                x=rect.right()+gap
            else:
                x=rect.left()-gap-visual_w
            # Bias vertically in the direction returned by the room heuristic,
            # but keep the text close to the symbol.
            y=rect.center().y()-visual_h*.45 + dy*min(visual_h*.35,10.0/scale)
        else:
            x=rect.center().x()-visual_w*.5
            if dy>=0:
                y=rect.bottom()+gap
            else:
                y=rect.top()-gap-visual_h

        self.setPos(x,y)

    def toHtml(self) -> str:
        primary,secondary,assoc,extra,spot_parent=self._content()
        return " ".join([primary,secondary,assoc,spot_parent]+extra)

    def mouseDoubleClickEvent(self,event) -> None:
        if callable(self.edit_callback):
            self.edit_callback(self.placement)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class TextSignals(QObject):
    moved = Signal(object)
    dragStarted = Signal(object, object)
    dragFinished = Signal(object, object, object)
    doubleClicked = Signal(object)


class FreeTextItem(QGraphicsSimpleTextItem):
    def __init__(self, item: core.TextPlacement):
        super().__init__(item.text)
        self.source = item
        self.signals = TextSignals()
        self._drag_start = None
        self._suppress = False
        self.snapper: Callable | None = None
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
                      QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges |
                      QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.setPos(item.x, -item.y); self.setRotation(-item.rotation); self.setBrush(QBrush(_dark_canvas_contrast(QColor(item.color))))
        font = QFont("Segoe UI")
        font.setPointSizeF(max(1.0, min(96.0, item.height * 0.065)))
        font.setWeight(QFont.Weight.Medium)
        self.setFont(font); self.setZValue(80)

    def refresh(self) -> None:
        self.setText(self.source.text)
        self.setBrush(QBrush(_dark_canvas_contrast(QColor(self.source.color))))
        font = QFont("Segoe UI")
        font.setPointSizeF(max(1.0, min(96.0, self.source.height * 0.065)))
        font.setWeight(QFont.Weight.Medium)
        self.setFont(font)
        self._suppress = True
        self.setPos(self.source.x, -self.source.y)
        self.setRotation(-self.source.rotation)
        self._suppress = False

    def mousePressEvent(self, event) -> None:
        self._drag_start = (float(self.source.x), float(self.source.y))
        self.signals.dragStarted.emit(self, self._drag_start)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        if self._drag_start is not None:
            end = (float(self.source.x), float(self.source.y))
            self.signals.dragFinished.emit(self, self._drag_start, end)
            self._drag_start = None

    def mouseDoubleClickEvent(self, event) -> None:
        self.signals.doubleClicked.emit(self)
        event.accept()

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and not self._suppress and self._drag_start is not None and callable(self.snapper):
            try:
                snapped = self.snapper(self, value)
                if isinstance(snapped, QPointF):
                    return snapped
            except Exception:
                pass
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and not self._suppress:
            self.source.x = float(value.x())
            self.source.y = float(-value.y())
            self.signals.moved.emit(self)
        return super().itemChange(change, value)


class CadGraphicsView(QGraphicsView):
    zoomChanged = Signal(float)
    mouseSceneMoved = Signal(object)
    placementRequested = Signal(str, float, float, float)
    cableFinished = Signal(object)
    cablePreviewChanged = Signal(object)
    cablePointCommitted = Signal(object)
    calibrationFinished = Signal(object)
    textPlacementRequested = Signal(object)
    patternFinished = Signal(str, object, object, object)
    roomFinished = Signal(object)
    roomPreviewChanged = Signal(object)
    toolCancelled = Signal()

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        # We handle zoom anchoring explicitly in wheelEvent. This avoids Qt
        # changing the anchor unexpectedly while a placement preview item is active.
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontSavePainterState, True)
        self._panning = False; self._pan_start = None; self._zoom = 1.0
        self.last_mouse_scene = QPointF()
        self.snap_engine: QtSnapEngine | None = None
        self._placement_code = ""; self._placement_size = 200.0; self._placement_rotation = 0.0
        self._placement_color = "#d00000"; self._placement_line_width = 0.25
        self._preview_item: ElectricalSymbolItem | None = None
        self._snap_marker: QGraphicsEllipseItem | None = None
        self._snap_text: QGraphicsSimpleTextItem | None = None
        self._snap_pulse_anim=QVariantAnimation(self); self._snap_pulse_anim.setDuration(220); self._snap_pulse_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._snap_pulse_anim.valueChanged.connect(self._update_snap_pulse)
        self._last_snap_signature=None
        self._nav_anim=QVariantAnimation(self); self._nav_anim.setDuration(280); self._nav_anim.setEasingCurve(QEasingCurve.Type.OutCubic); self._nav_anim.valueChanged.connect(self._apply_navigation_animation)
        self._nav_state=None
        self._lighting_alignment_enabled = True
        self._align_vline: QGraphicsPathItem | None = None
        self._align_hline: QGraphicsPathItem | None = None
        self._cable_active = False
        self._cable_points: list[tuple[float, float]] = []
        self._cable_preview: QGraphicsPathItem | None = None
        self._cable_orthogonal = True
        self._cable_meta: dict = {}
        self._cable_start_uid = ""
        self._cable_start_port = 0
        self._cable_last_snap = ("", 0)
        self._cable_connections: list[dict] = []
        self._cable_click_stack: list[int] = []
        self._cable_snap_symbols = True
        self._cable_snap_walls = True
        self._cable_snap_routes = True
        self._calibration_active = False
        self._calibration_start: tuple[float, float] | None = None
        self._calibration_preview: QGraphicsPathItem | None = None
        self._text_tool: dict | None = None
        self._pattern_kind = ""
        self._pattern_config: dict = {}
        self._pattern_start: tuple[float, float] | None = None
        self._pattern_snap_end: tuple[float, float] | None = None
        self._pattern_preview: QGraphicsPathItem | None = None
        self._room_active = False
        self._room_points: list[tuple[float,float]] = []
        self._room_preview: QGraphicsPathItem | None = None
        self._room_axis_guide: QGraphicsPathItem | None = None
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _update_snap_pulse(self,value) -> None:
        if self._snap_marker is None:return
        try:p=max(0.0,min(1.0,float(value)))
        except Exception:p=1.0
        radius=5.0+5.0*p
        self._snap_marker.setRect(QRectF(-radius,-radius,radius*2,radius*2))
        self._snap_marker.setOpacity(1.0-0.28*p)

    def _apply_navigation_animation(self,value) -> None:
        state=self._nav_state
        if not state:return
        try:t=max(0.0,min(1.0,float(value)))
        except Exception:t=1.0
        scale=state[0]+(state[1]-state[0])*t
        cx=state[2].x()+(state[3].x()-state[2].x())*t
        cy=state[2].y()+(state[3].y()-state[2].y())*t
        self.resetTransform(); self.scale(scale,scale); self._zoom=scale; self.centerOn(QPointF(cx,cy)); self.zoomChanged.emit(scale)
        if t>=0.999:self._nav_state=None

    def animate_to_scene_rect(self, rect: QRectF, *, padding_px: float=90.0) -> bool:
        if rect is None or rect.isNull() or rect.isEmpty():return False
        viewport=self.viewport().rect()
        if viewport.width()<20 or viewport.height()<20:return False
        rect=QRectF(rect); rect.adjust(-1,-1,1,1)
        target=min((viewport.width()-padding_px)/max(rect.width(),1e-6),(viewport.height()-padding_px)/max(rect.height(),1e-6))
        target=max(0.02,min(80.0,float(target)))
        start=max(0.02,float(self.current_scale()))
        center0=self.mapToScene(viewport.center()); center1=rect.center()
        self._nav_anim.stop(); self._nav_state=(start,target,center0,center1); self._nav_anim.setStartValue(0.0); self._nav_anim.setEndValue(1.0); self._nav_anim.start(); return True

    def set_snap_engine(self, engine: QtSnapEngine | None) -> None:
        self.snap_engine = engine

    def set_lighting_alignment_enabled(self, enabled: bool) -> None:
        self._lighting_alignment_enabled = bool(enabled)
        if not self._lighting_alignment_enabled:
            self._clear_alignment_guides()

    def refresh_theme(self) -> None:
        """Refresh temporary CAD helpers after a live light/dark switch."""
        guide_color=QColor("#5fd3ca") if _canvas_is_dark() else QColor("#0b8f87")
        for item in (self._align_vline,self._align_hline):
            if item is not None:
                pen=QPen(guide_color); pen.setCosmetic(True); pen.setWidthF(1.15); pen.setStyle(Qt.PenStyle.DashLine); item.setPen(pen)
        preview_color=QColor("#6da8ff") if _canvas_is_dark() else QColor("#2563eb")
        if self._pattern_preview is not None:
            pen=QPen(preview_color); pen.setCosmetic(True); pen.setWidthF(1.2); pen.setStyle(Qt.PenStyle.DashLine); self._pattern_preview.setPen(pen)
        if self._calibration_preview is not None:
            pen=QPen(preview_color); pen.setCosmetic(True); pen.setWidthF(1.5); pen.setStyle(Qt.PenStyle.DashLine); self._calibration_preview.setPen(pen)
        if self._room_preview is not None:
            room_color=QColor("#5eead4") if _canvas_is_dark() else QColor("#0f766e")
            pen=QPen(room_color); pen.setCosmetic(True); pen.setWidthF(1.8); pen.setStyle(Qt.PenStyle.DashLine); self._room_preview.setPen(pen)
        if self._cable_preview is not None:
            pen=self._cable_preview.pen(); pen.setColor(_dark_canvas_contrast(QColor(self._cable_meta.get("color",core.DEFAULT_CABLE_COLOR)))); self._cable_preview.setPen(pen)
        if self._snap_marker is not None:
            snap_color=QColor("#62d9d2") if _canvas_is_dark() else QColor("#008b8b")
            pen=QPen(snap_color); pen.setCosmetic(True); pen.setWidthF(2.0); self._snap_marker.setPen(pen)
            fill=QColor(snap_color); fill.setAlpha(52 if _canvas_is_dark() else 45); self._snap_marker.setBrush(QBrush(fill))
        if self._snap_text is not None:
            self._snap_text.setBrush(QBrush(QColor("#83e1dc") if _canvas_is_dark() else QColor("#006b6b")))
        self.viewport().update()

    def _axis_alignment_snap(self, x: float, y: float, candidates, tolerance_px: float = 11.0):
        """CAD-style independent X/Y alignment with temporary viewport guides."""
        scale=self.current_scale()
        tol=float(tolerance_px)/max(scale,1e-9)
        xmin,ymin,xmax,ymax=self.viewport_cad_extents()
        margin=40.0/max(scale,1e-9)
        visible=[]
        for point in candidates or ():
            try:px=float(point[0]); py=float(point[1])
            except (TypeError,ValueError,IndexError):continue
            if xmin-margin <= px <= xmax+margin and ymin-margin <= py <= ymax+margin:
                visible.append((px,py))
        sx,sy,gx,gy=axis_alignment_snap(float(x),float(y),visible,tol)
        self._show_alignment_guides(gx,gy)
        parts=[]
        if gx is not None:parts.append("LODRET")
        if gy is not None:parts.append("VANDRET")
        return float(sx),float(sy)," + ".join(parts)

    def _text_alignment_snap(self, x: float, y: float, ignore_uid: str = ""):
        candidates=[]
        for item in self.scene().items():
            if not isinstance(item,FreeTextItem) or not item.isVisible():
                continue
            if str(getattr(item.source,"uid","") or "") == str(ignore_uid or ""):
                continue
            candidates.append((float(item.source.x),float(item.source.y)))
        return self._axis_alignment_snap(x,y,candidates,10.0)

    def _cable_alignment_snap(self, active_item, index: int, x: float, y: float):
        """Align a dragged cable vertex to visible cable vertices and symbol ports."""
        candidates=[]
        active_points=[]
        try:
            active_points=list((active_item._edit_before or {}).get("points",active_item.cable.points))
        except Exception:
            active_points=list(getattr(getattr(active_item,"cable",None),"points",[]) or [])
        for i,p in enumerate(active_points):
            if i != int(index):candidates.append((float(p[0]),float(p[1])))
        for obj in self.scene().items():
            if isinstance(obj,CableItem) and obj is not active_item and obj.isVisible():
                for px,py in obj.cable.points:
                    candidates.append((float(px),float(py)))
            elif isinstance(obj,ElectricalSymbolItem) and obj.isVisible():
                try:
                    candidates.extend((float(px),float(py)) for px,py,_port in core.placement_connection_ports(obj.placement))
                except Exception:
                    pass
        return self._axis_alignment_snap(x,y,candidates,11.0)

    def _lighting_alignment_snap(self, symbol: str, x: float, y: float, ignore_uid: str = "", ignore_uids=None):
        """Snap lighting symbols to shared X/Y centre lines.

        For spots, visible spots are deliberately preferred over lampesteder and
        other lighting symbols.  This makes rows/groups easy to align with an
        existing spot layout while preserving the general lighting snap as a
        fallback.  Group members supplied through ``ignore_uids`` are excluded,
        so a moving spotgruppe cannot magnetise to itself.
        """
        if not self._lighting_alignment_enabled or symbol not in core.LIGHT_ASSOCIATION_SYMBOLS:
            self._clear_alignment_guides()
            return float(x), float(y), ""

        scale = self.current_scale()
        tol = 11.0 / max(scale, 1e-9)
        xmin, ymin, xmax, ymax = self.viewport_cad_extents()
        margin = 40.0 / max(scale, 1e-9)
        ignored = {str(ignore_uid)} if ignore_uid else set()
        if ignore_uids:
            ignored.update(str(uid) for uid in ignore_uids)

        candidates=[]
        for item in self.scene().items():
            if not isinstance(item, ElectricalSymbolItem):
                continue
            p=item.placement
            if p.uid in ignored or not item.isVisible() or p.symbol not in core.LIGHT_ASSOCIATION_SYMBOLS:
                continue
            px=float(p.x); py=float(p.y)
            if not (xmin-margin <= px <= xmax+margin and ymin-margin <= py <= ymax+margin):
                continue
            candidates.append((p.symbol,px,py))

        def best_axis(axis: str):
            target=float(x) if axis=="x" else float(y)
            # Spots have first choice when the object being aligned is a spot.
            pools=[]
            if symbol=="spot":
                pools.append([row for row in candidates if row[0]=="spot"])
                pools.append([row for row in candidates if row[0]!="spot"])
            else:
                pools.append(candidates)
            for pool in pools:
                best=None; best_d=float("inf")
                for code,px,py in pool:
                    value=px if axis=="x" else py
                    distance=abs(value-target)
                    if distance <= tol and distance < best_d:
                        best=(value,code); best_d=distance
                if best is not None:
                    return best
            return None

        hit_x=best_axis("x"); hit_y=best_axis("y")
        best_x=hit_x[0] if hit_x is not None else None
        best_y=hit_y[0] if hit_y is not None else None
        sx=float(best_x) if best_x is not None else float(x)
        sy=float(best_y) if best_y is not None else float(y)
        self._show_alignment_guides(best_x,best_y)

        parts=[]
        spot_reference=bool((hit_x and hit_x[1]=="spot") or (hit_y and hit_y[1]=="spot"))
        if spot_reference:
            parts.append("SPOT")
        if best_x is not None: parts.append("LODRET")
        if best_y is not None: parts.append("VANDRET")
        return sx,sy," · ".join(parts)

    def _ensure_alignment_lines(self) -> None:
        if self._align_vline is not None and self._align_hline is not None:
            return
        pen = QPen(QColor("#5fd3ca") if _canvas_is_dark() else QColor("#0b8f87"))
        pen.setCosmetic(True); pen.setWidthF(1.15); pen.setStyle(Qt.PenStyle.DashLine)
        self._align_vline = QGraphicsPathItem(); self._align_vline.setPen(pen); self._align_vline.setZValue(19000)
        self._align_hline = QGraphicsPathItem(); self._align_hline.setPen(pen); self._align_hline.setZValue(19000)
        self.scene().addItem(self._align_vline); self.scene().addItem(self._align_hline)

    def _show_alignment_guides(self, x_cad, y_cad) -> None:
        if x_cad is None and y_cad is None:
            self._clear_alignment_guides(); return
        self._ensure_alignment_lines()
        xmin, ymin, xmax, ymax = self.viewport_cad_extents()
        if x_cad is not None:
            path = QPainterPath(QPointF(float(x_cad), -float(ymax)))
            path.lineTo(QPointF(float(x_cad), -float(ymin)))
            self._align_vline.setPath(path); self._align_vline.show()
        else:
            self._align_vline.hide()
        if y_cad is not None:
            path = QPainterPath(QPointF(float(xmin), -float(y_cad)))
            path.lineTo(QPointF(float(xmax), -float(y_cad)))
            self._align_hline.setPath(path); self._align_hline.show()
        else:
            self._align_hline.hide()

    def _clear_alignment_guides(self) -> None:
        if self._align_vline is not None:
            self._align_vline.hide()
        if self._align_hline is not None:
            self._align_hline.hide()

    def scene_will_reset(self) -> None:
        # QGraphicsScene.clear() deletes the C++ graphics items; drop Python wrappers
        # first so later snap feedback never touches an already deleted Qt object.
        self._preview_item = None
        self._placement_code = ""
        self._snap_marker = None
        self._snap_text = None
        self._align_vline = None
        self._align_hline = None
        self._cable_preview = None
        self._cable_points = []
        self._cable_active = False
        self._calibration_preview = None
        self._calibration_start = None
        self._calibration_active = False
        self._text_tool = None
        self._pattern_kind = ""; self._pattern_config = {}; self._pattern_start = None; self._pattern_snap_end = None; self._pattern_preview = None
        self._room_active=False; self._room_points=[]; self._room_preview=None; self._room_axis_guide=None
        self.unsetCursor()

    def current_scale(self) -> float:
        return max(abs(float(self.transform().m11())), 1e-9)

    def viewport_cad_extents(self) -> tuple[float, float, float, float]:
        rect = self.mapToScene(self.viewport().rect()).boundingRect()
        xmin = float(rect.left()); xmax = float(rect.right())
        ymin = float(-rect.bottom()); ymax = float(-rect.top())
        return xmin, ymin, xmax, ymax

    def start_symbol_placement(self, code: str, size: float, color: str = "#d00000", line_width: float = 0.25, rotation: float = 0.0) -> None:
        self.cancel_tool(emit_signal=False)
        self._placement_code = str(code); self._placement_size = float(size); self._placement_color = str(color)
        self._placement_line_width = float(line_width); self._placement_rotation = float(rotation) % 360.0
        p = core.Placement(symbol=self._placement_code, x=0.0, y=0.0, size=self._placement_size,
                           rotation=self._placement_rotation, color=self._placement_color, line_width=self._placement_line_width)
        self._preview_item = ElectricalSymbolItem(p)
        self._preview_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self._preview_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self._preview_item.setOpacity(0.62); self._preview_item.setZValue(1000)
        self.scene().addItem(self._preview_item)
        if self.snap_engine is not None:
            self.snap_engine.clear_wall_lock(self._preview_item.placement.uid)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def start_text_tool(self, *, text: str, height: float, rotation: float = 0.0, color: str = "#202020") -> None:
        self.cancel_tool(emit_signal=False)
        self._text_tool = {
            "text": str(text), "height": float(height), "rotation": float(rotation),
            "color": str(color),
        }
        self.setCursor(Qt.CursorShape.CrossCursor)

    @staticmethod
    def _row_points(start, end, count: int):
        n=max(2,int(count)); x1,y1=start; x2,y2=end
        return [(x1+(x2-x1)*i/(n-1), y1+(y2-y1)*i/(n-1)) for i in range(n)]

    @staticmethod
    def _rect_points(start, end, cols: int, rows: int):
        cols=max(2,int(cols)); rows=max(2,int(rows)); x1,y1=start; x2,y2=end
        out=[]
        for r in range(rows):
            fy=r/(rows-1); y=y1+(y2-y1)*fy
            for c in range(cols):
                fx=c/(cols-1); x=x1+(x2-x1)*fx
                out.append((x,y))
        return out

    def start_room_tool(self) -> None:
        self.cancel_tool(emit_signal=False)
        self._room_active=True; self._room_points=[]; self.roomPreviewChanged.emit([])
        self._room_preview=QGraphicsPathItem()
        self._room_axis_guide=QGraphicsPathItem()
        color=QColor("#5eead4") if _canvas_is_dark() else QColor("#0f766e")
        pen=QPen(color); pen.setCosmetic(True); pen.setWidthF(1.8); pen.setStyle(Qt.PenStyle.DashLine)
        fill=QColor(color); fill.setAlpha(28)
        self._room_preview.setPen(pen); self._room_preview.setBrush(QBrush(fill)); self._room_preview.setZValue(1700)
        guide_pen=QPen(QColor("#67e8f9") if _canvas_is_dark() else QColor("#0891b2")); guide_pen.setCosmetic(True); guide_pen.setWidthF(1.3); guide_pen.setStyle(Qt.PenStyle.DotLine)
        self._room_axis_guide.setPen(guide_pen); self._room_axis_guide.setBrush(QBrush(Qt.BrushStyle.NoBrush)); self._room_axis_guide.setZValue(1701); self._room_axis_guide.hide()
        self.scene().addItem(self._room_preview); self.scene().addItem(self._room_axis_guide); self.setCursor(Qt.CursorShape.CrossCursor)

    def _snap_room_point(self, scene_pos: QPointF, *, free_angle: bool = False):
        raw=_cad_point(scene_pos); x,y=raw; kind=""; gx=gy=None
        scale=max(self.current_scale(),1e-9)
        wall=None
        if self.snap_engine is not None:
            wall=self.snap_engine.nearest_wall(float(raw[0]),float(raw[1]),20.0/scale)
        if wall is not None:
            x,y=float(wall[0]),float(wall[1]); kind="VÆG"
            # Væg-snap og ortho-hjælp må samarbejde.  Når den valgte CAD-væg
            # kan skæres vandret/lodret fra sidste rumhjørne, og cursoren er
            # tæt på dette kryds, bruger vi krydset. Punktet forbliver dermed
            # både præcist på CAD-væggen og præcist 0°/90°.
            if self._room_points and not free_angle:
                try:segment=self.snap_engine.segments[int(wall[5])][:4]
                except Exception:segment=None
                if segment is not None:
                    combined=room_wall_axis_snap(raw[0],raw[1],self._room_points[-1],segment,14.0/scale)
                    if combined is not None:
                        x,y,gx,gy,axis_kind=combined; kind=f"VÆG · {axis_kind}"
        elif self._room_points:
            # Uden væg-snap er hjælpen stadig blød: flyt uden for tolerancen
            # eller hold Alt for en helt fri/skrå rumlinje.
            tol=12.0/scale
            x,y,gx,gy,axis_kind=room_axis_assist(x,y,[self._room_points[-1]],tol,disabled=free_angle)
            if axis_kind:kind=axis_kind
        return x,y,kind,gx,gy

    def _update_room_axis_guide(self, x: float, y: float, gx, gy) -> None:
        guide=self._room_axis_guide
        if guide is None:return
        if not self._room_points or (gx is None and gy is None):
            guide.hide(); return
        prev=self._room_points[-1]; current=(float(x),float(y)); ext=22.0/self.current_scale(); path=QPainterPath()
        if gy is not None:
            left=min(prev[0],current[0])-ext; right=max(prev[0],current[0])+ext
            path.moveTo(_mapped_point(left,float(gy))); path.lineTo(_mapped_point(right,float(gy)))
        if gx is not None:
            low=min(prev[1],current[1])-ext; high=max(prev[1],current[1])+ext
            path.moveTo(_mapped_point(float(gx),low)); path.lineTo(_mapped_point(float(gx),high))
        guide.setPath(path); guide.show()

    def _update_room_preview(self, scene_pos: QPointF, modifiers=Qt.KeyboardModifier.NoModifier) -> None:
        if not self._room_active or self._room_preview is None:return
        free=bool(modifiers & Qt.KeyboardModifier.AltModifier)
        x,y,kind,gx,gy=self._snap_room_point(scene_pos,free_angle=free); pts=list(self._room_points)+[(x,y)]
        path=QPainterPath()
        if pts:
            path.moveTo(_mapped_point(*pts[0]))
            for p in pts[1:]:path.lineTo(_mapped_point(*p))
            if len(self._room_points)>=2:path.lineTo(_mapped_point(*self._room_points[0]))
        self._room_preview.setPath(path); self._update_room_axis_guide(x,y,gx,gy); self._show_snap_feedback(_mapped_point(x,y),kind)

    def _append_room_point(self, scene_pos: QPointF, modifiers=Qt.KeyboardModifier.NoModifier) -> None:
        if not self._room_active:return
        free=bool(modifiers & Qt.KeyboardModifier.AltModifier)
        x,y,kind,gx,gy=self._snap_room_point(scene_pos,free_angle=free)
        if self._room_points and math.hypot(x-self._room_points[-1][0],y-self._room_points[-1][1]) < 1e-6:return
        self._room_points.append((x,y)); self._show_snap_feedback(_mapped_point(x,y),kind); self._update_room_preview(scene_pos,modifiers); self.roomPreviewChanged.emit(list(self._room_points))

    def remove_last_room_point(self) -> None:
        if not self._room_active:return
        if self._room_points:self._room_points.pop()
        if self._room_preview is not None:self._update_room_preview(self.last_mouse_scene)
        self.roomPreviewChanged.emit(list(self._room_points))

    def finish_room(self) -> None:
        if not self._room_active:return
        pts=list(self._room_points)
        if len(pts)<3:return
        # Reject virtually zero-area polygons; they are almost always an accidental double-click.
        area=0.0
        for i,(x1,y1) in enumerate(pts):
            x2,y2=pts[(i+1)%len(pts)]; area+=x1*y2-x2*y1
        if abs(area)<1e-6:return
        self.cancel_tool(emit_signal=False); self.roomFinished.emit(pts)

    def start_spot_pattern(self, kind: str, config: dict) -> None:
        self.cancel_tool(emit_signal=False)
        self._pattern_kind = "rect" if str(kind) == "rect" else "line"
        self._pattern_config = dict(config or {})
        self._pattern_start = None
        self._pattern_snap_end = None
        self._pattern_preview = QGraphicsPathItem()
        pen=QPen(QColor("#6da8ff") if _canvas_is_dark() else QColor("#2563eb")); pen.setCosmetic(True); pen.setWidthF(1.2); pen.setStyle(Qt.PenStyle.DashLine)
        self._pattern_preview.setPen(pen); self._pattern_preview.setBrush(QBrush(Qt.BrushStyle.NoBrush)); self._pattern_preview.setZValue(1600)
        self.scene().addItem(self._pattern_preview)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def _pattern_points(self, end_cad):
        if self._pattern_start is None:
            return []
        if self._pattern_kind=="rect":
            return self._rect_points(self._pattern_start,end_cad,self._pattern_config.get("cols",3),self._pattern_config.get("rows",2))
        return self._row_points(self._pattern_start,end_cad,self._pattern_config.get("count",4))

    def _update_pattern_preview(self, scene_pos: QPointF, modifiers=Qt.KeyboardModifier.NoModifier) -> None:
        if not self._pattern_kind or self._pattern_preview is None or self._pattern_start is None:
            return
        raw_end=_cad_point(scene_pos)
        ex,ey,kind=self._lighting_alignment_snap("spot",raw_end[0],raw_end[1])
        if self._pattern_kind == "line":
            free_angle=bool(modifiers & Qt.KeyboardModifier.AltModifier)
            tol=14.0/max(self.current_scale(),1e-9)
            ex,ey,gx,gy,axis_kind=spot_row_axis_assist(ex,ey,self._pattern_start,tol,disabled=free_angle)
            if axis_kind:
                # Row-axis feedback takes visual priority while preserving any
                # independent lighting alignment on the free coordinate.
                self._show_alignment_guides(gx,gy)
                kind=(f"{kind} · {axis_kind}" if kind and axis_kind not in kind else axis_kind)
        end=(ex,ey); self._pattern_snap_end=end
        pts=self._pattern_points(end)
        self._show_snap_feedback(_mapped_point(ex,ey),kind)
        path=QPainterPath()
        if self._pattern_kind=="rect":
            x1,y1=self._pattern_start; x2,y2=end
            path.addRect(QRectF(min(x1,x2), -max(y1,y2), abs(x2-x1), abs(y2-y1)))
        elif pts:
            path.moveTo(_mapped_point(*pts[0]))
            for q in pts[1:]: path.lineTo(_mapped_point(*q))
        rr=max(5.0,float(self._pattern_config.get("size",150.0))*.12)
        for x,y in pts:
            path.addEllipse(QRectF(x-rr,-y-rr,2*rr,2*rr))
        self._pattern_preview.setPath(path)

    def start_calibration_tool(self) -> None:
        """Measure a known distance using two snapped CAD points."""
        self.cancel_tool(emit_signal=False)
        self._calibration_active = True
        self._calibration_start = None
        self._calibration_preview = QGraphicsPathItem()
        pen = QPen(QColor("#6da8ff") if _canvas_is_dark() else QColor("#2563eb")); pen.setCosmetic(True); pen.setWidthF(1.5); pen.setStyle(Qt.PenStyle.DashLine)
        self._calibration_preview.setPen(pen); self._calibration_preview.setZValue(1600)
        self.scene().addItem(self._calibration_preview)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def _snap_calibration_point(self, scene_pos: QPointF):
        raw = _cad_point(scene_pos)
        if self.snap_engine is None:
            return raw[0], raw[1], ""
        x, y, kind, _uid, _port = self.snap_engine.snap_connection(
            self.scene(), raw, self.current_scale(), snap_symbols=True, snap_walls=True
        )
        return float(x), float(y), str(kind or "")

    def _update_calibration_preview(self, scene_pos: QPointF) -> None:
        if not self._calibration_active or self._calibration_preview is None:
            return
        x, y, kind = self._snap_calibration_point(scene_pos)
        self._show_snap_feedback(_mapped_point(x, y), kind)
        path = QPainterPath()
        if self._calibration_start is not None:
            path.moveTo(_mapped_point(*self._calibration_start))
            path.lineTo(_mapped_point(x, y))
        self._calibration_preview.setPath(path)

    def _append_calibration_point(self, scene_pos: QPointF) -> None:
        x, y, kind = self._snap_calibration_point(scene_pos)
        if self._calibration_start is None:
            self._calibration_start = (x, y)
            self._show_snap_feedback(_mapped_point(x, y), kind)
            self._update_calibration_preview(scene_pos)
            return
        start = self._calibration_start
        distance = math.hypot(x - start[0], y - start[1])
        payload = {"start": start, "end": (x, y), "drawing_distance": float(distance)}
        self.cancel_tool(emit_signal=False)
        if distance > 1e-12:
            self.calibrationFinished.emit(payload)

    def start_cable_tool(self, *, layer: str, line_width: float, label: str, cable_spec: str,
                         cable_id: str, auto_label: bool, orthogonal: bool = False, circuit_id: str = "",
                         color: str = core.DEFAULT_CABLE_COLOR, line_style: str = core.DEFAULT_CABLE_LINE_STYLE,
                         cable_category: str = core.DEFAULT_CABLE_CATEGORY,
                         snap_symbols: bool = True, snap_walls: bool = True, snap_routes: bool = True) -> None:
        self.cancel_tool(emit_signal=False)
        self._cable_active = True
        self._cable_points = []
        self._cable_orthogonal = bool(orthogonal)
        self._cable_meta = {
            "layer": str(layer), "line_width": float(line_width), "label": str(label),
            "cable_spec": str(cable_spec), "cable_id": str(cable_id),
            "circuit_id": str(circuit_id or "").strip(),
            "route_chain_uid": uuid.uuid4().hex,
            "auto_label": bool(auto_label), "orthogonal": bool(orthogonal),
            "color": core.normalize_hex_color(color,core.DEFAULT_CABLE_COLOR),
            "line_style": core.normalize_cable_line_style(line_style),
            "cable_category": core.normalize_cable_category_id(cable_category),
        }
        self._cable_start_uid = ""
        self._cable_start_port = 0
        self._cable_last_snap = ("", 0)
        self._cable_connections = []
        self._cable_click_stack = []
        self._cable_snap_symbols = bool(snap_symbols)
        self._cable_snap_walls = bool(snap_walls)
        self._cable_snap_routes = bool(snap_routes)
        self._cable_preview = QGraphicsPathItem()
        pen = QPen(_dark_canvas_contrast(QColor(core.normalize_hex_color(color,core.DEFAULT_CABLE_COLOR)))); pen.setCosmetic(True); pen.setWidthF(1.5)
        pen.setStyle(_qt_cable_pen_style(line_style))
        self._cable_preview.setPen(pen); self._cable_preview.setZValue(1500)
        self.scene().addItem(self._cable_preview)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def update_cable_settings(self, *, layer=None, line_width=None, label=None, cable_spec=None, cable_id=None, circuit_id=None,
                              auto_label=None, orthogonal=None, color=None, line_style=None, cable_category=None,
                              snap_symbols=None, snap_walls=None, snap_routes=None) -> None:
        if layer is not None: self._cable_meta["layer"] = str(layer)
        if line_width is not None:
            self._cable_meta["line_width"] = float(line_width)
            if self._cable_preview is not None:
                pen = self._cable_preview.pen()
                pen.setWidthF(max(1.2, min(4.0, float(line_width) * 1.8)))
                self._cable_preview.setPen(pen)
        if label is not None: self._cable_meta["label"] = str(label)
        if cable_spec is not None: self._cable_meta["cable_spec"] = str(cable_spec)
        if cable_id is not None: self._cable_meta["cable_id"] = str(cable_id)
        if circuit_id is not None: self._cable_meta["circuit_id"] = str(circuit_id or "").strip()
        if auto_label is not None: self._cable_meta["auto_label"] = bool(auto_label)
        if color is not None:
            self._cable_meta["color"] = core.normalize_hex_color(color,core.DEFAULT_CABLE_COLOR)
            if self._cable_preview is not None:
                pen=self._cable_preview.pen(); pen.setColor(_dark_canvas_contrast(QColor(self._cable_meta["color"]))); self._cable_preview.setPen(pen)
        if line_style is not None:
            self._cable_meta["line_style"] = core.normalize_cable_line_style(line_style)
            if self._cable_preview is not None:
                pen=self._cable_preview.pen(); pen.setStyle(_qt_cable_pen_style(self._cable_meta["line_style"])); self._cable_preview.setPen(pen)
        if cable_category is not None:
            self._cable_meta["cable_category"] = core.normalize_cable_category_id(cable_category)
        if orthogonal is not None:
            self._cable_orthogonal = bool(orthogonal)
            self._cable_meta["orthogonal"] = bool(orthogonal)
        if snap_symbols is not None: self._cable_snap_symbols = bool(snap_symbols)
        if snap_walls is not None: self._cable_snap_walls = bool(snap_walls)
        if snap_routes is not None: self._cable_snap_routes = bool(snap_routes)
        if self._cable_active:
            self._update_cable_preview(self.last_mouse_scene)

    def remove_last_cable_point(self) -> None:
        if not self._cable_active or not self._cable_points:
            return
        # Backspace fjerner sidste brugerklik, ikke kun et automatisk 90°-hjørne.
        target_len=self._cable_click_stack.pop() if self._cable_click_stack else max(0,len(self._cable_points)-1)
        self._cable_points=self._cable_points[:target_len]
        self._cable_connections=[r for r in self._cable_connections if int(r.get("point_index",-1)) < target_len]
        if not self._cable_points:
            self._cable_start_uid = ""; self._cable_start_port = 0
        self._update_cable_preview(self.last_mouse_scene)

    @staticmethod
    def _nearest_point_on_polyline(x: float, y: float, points):
        best=None; best_d=float("inf")
        pts=list(points or [])
        for a,b in zip(pts,pts[1:]):
            try:
                x1,y1=map(float,a); x2,y2=map(float,b)
            except Exception:
                continue
            dx=x2-x1; dy=y2-y1; den=dx*dx+dy*dy
            if den<=1e-18:
                nx,ny=x1,y1
            else:
                t=max(0.0,min(1.0,((x-x1)*dx+(y-y1)*dy)/den))
                nx=x1+t*dx; ny=y1+t*dy
            d=math.hypot(nx-x,ny-y)
            if d<best_d:
                best_d=d; best=(nx,ny)
        return (best[0],best[1],best_d) if best is not None else None

    def snap_to_existing_cable_route(self, x: float, y: float, *, active_item=None, tolerance_px: float = 14.0):
        """Snap to the logical centreline of another visible cable.

        Parallel lane separation is intentionally ignored here: all cables that
        share a physical route should store the same logical centreline and are
        separated only by the visual lane renderer.
        """
        tol=float(tolerance_px)/max(self.current_scale(),1e-9)
        best=None; best_d=float("inf"); best_item=None
        for obj in self.scene().items():
            if not isinstance(obj,CableItem) or obj is active_item or not obj.isVisible():
                continue
            hit=self._nearest_point_on_polyline(float(x),float(y),getattr(obj.cable,"points",[]))
            if hit is None or hit[2]>tol or hit[2]>=best_d:
                continue
            best=(hit[0],hit[1]); best_d=hit[2]; best_item=obj
        if best is None:
            return None
        return best[0],best[1],best_item

    def _snap_cable_point(self, scene_pos: QPointF):
        raw = _cad_point(scene_pos)
        x,y=raw
        if self.snap_engine is not None and self._cable_snap_symbols:
            hit=self.snap_engine.snap_connection(
                self.scene(), raw, self.current_scale(), snap_symbols=True, snap_walls=False
            )
            if str(hit[2] or "").upper()=="SYMBOL":
                return hit
        if self._cable_snap_routes:
            route=self.snap_to_existing_cable_route(x,y,tolerance_px=14.0)
            if route is not None:
                return (route[0],route[1],"KABELRUTE","",0)
        if self.snap_engine is not None and self._cable_snap_walls:
            hit=self.snap_engine.snap_connection(
                self.scene(), raw, self.current_scale(), snap_symbols=False, snap_walls=True
            )
            if hit[2]:
                return hit
        return x,y,"","",0

    def _orthogonal_points_to(self, end: tuple[float, float]) -> list[tuple[float, float]]:
        # Historical method name kept for compatibility. In free/diagonal mode
        # this returns one direct segment; in orthogonal mode it returns the
        # legacy dominant-axis-first L route.
        start=self._cable_points[-1] if self._cable_points else None
        return core.cable_route_points_to(start,end,self._cable_orthogonal)

    def _update_cable_preview(self, scene_pos: QPointF) -> None:
        if not self._cable_active or self._cable_preview is None:
            return
        x, y, kind, uid, port = self._snap_cable_point(scene_pos)
        self._cable_last_snap = (uid, port)
        preview = list(self._cable_points)
        preview.extend(self._orthogonal_points_to((x, y)))
        path = QPainterPath()
        if preview:
            path.moveTo(_mapped_point(*preview[0]))
            for pt in preview[1:]:
                path.lineTo(_mapped_point(*pt))
        self._cable_preview.setPath(path)
        self._show_snap_feedback(_mapped_point(x, y), kind)
        self.cablePreviewChanged.emit(preview)

    def _emit_cable_point_committed(self, *, x: float, y: float, kind: str = "", uid: str = "", port: int = 0, seeded: bool = False, already_connected: bool = False) -> None:
        """Tell the main window about a user-level cable click.

        The graphics view owns geometry; the main window owns the interactive
        assistant UI.  A compact payload keeps those responsibilities separate
        and avoids any modal dialog inside the drawing engine.
        """
        point_index=len(self._cable_points)-1 if self._cable_points else -1
        self.cablePointCommitted.emit({
            "kind": str(kind or "POINT"),
            "symbol_uid": str(uid or ""),
            "symbol_port": max(0,int(port or 0)),
            "point_index": int(point_index),
            "cad_point": (float(x),float(y)),
            "scene_point": (float(x),float(-y)),
            "connection_count": len(self._cable_connections),
            "is_first": len(self._cable_click_stack) <= 1,
            "seeded": bool(seeded),
            "already_connected": bool(already_connected),
            "cable_id": str(self._cable_meta.get("cable_id","") or ""),
            "cable_spec": str(self._cable_meta.get("cable_spec","") or ""),
        })

    def seed_cable_start(self, cad_point, symbol_uid: str = "", symbol_port: int = 0) -> None:
        """Start the active cable at an already known physical connection.

        Used by the assistant's "Afslut + nyt herfra" shortcut.  It behaves
        exactly like the first normal symbol click, but does not require the
        user to hit the same symbol again.
        """
        if not self._cable_active or self._cable_points:
            return
        try:
            x,y=float(cad_point[0]),float(cad_point[1])
        except Exception:
            return
        uid=str(symbol_uid or "")
        port=max(0,int(symbol_port or 0))
        self._cable_click_stack.append(0)
        self._cable_points=[(x,y)]
        self._cable_start_uid=uid
        self._cable_start_port=port
        self._cable_connections=[]
        if uid:
            self._cable_connections=[{"point_index":0,"symbol_uid":uid,"symbol_port":port}]
        self._cable_last_snap=(uid,port) if uid else ("",0)
        self._update_cable_preview(_mapped_point(x,y))
        self._emit_cable_point_committed(x=x,y=y,kind="SYMBOL" if uid else "POINT",uid=uid,port=port,seeded=True)

    def convert_last_cable_connection_to_waypoint(self) -> None:
        """Keep the last geometry point but remove its physical symbol link."""
        if not self._cable_active or not self._cable_points:
            return
        idx=len(self._cable_points)-1
        self._cable_connections=[r for r in self._cable_connections if int(r.get("point_index",-1))!=idx]
        self._cable_connections=core.normalize_cable_symbol_connections(self._cable_connections,len(self._cable_points))
        if idx==0:
            self._cable_start_uid=""; self._cable_start_port=0
        self._cable_last_snap=("",0)
        self._update_cable_preview(self.last_mouse_scene)

    def _append_cable_point(self, scene_pos: QPointF) -> None:
        x, y, kind, uid, port = self._snap_cable_point(scene_pos)
        already_connected=bool(kind=="SYMBOL" and uid and any(str(r.get("symbol_uid","") or "")==str(uid) for r in self._cable_connections))
        self._cable_click_stack.append(len(self._cable_points))
        segment = self._orthogonal_points_to((x, y))
        if not self._cable_points:
            self._cable_points.append((x, y))
            self._cable_start_uid = uid if kind=="SYMBOL" else ""
            self._cable_start_port = int(port) if kind=="SYMBOL" else 0
        else:
            for pt in segment:
                if not self._cable_points or math.hypot(pt[0]-self._cable_points[-1][0], pt[1]-self._cable_points[-1][1]) > 1e-9:
                    self._cable_points.append(pt)
        if kind=="SYMBOL" and uid and self._cable_points:
            idx=len(self._cable_points)-1
            self._cable_connections=[r for r in self._cable_connections if int(r.get("point_index",-1))!=idx]
            self._cable_connections.append({"point_index":idx,"symbol_uid":str(uid),"symbol_port":max(0,int(port or 0))})
            self._cable_connections=core.normalize_cable_symbol_connections(self._cable_connections,len(self._cable_points))
        self._cable_last_snap = (uid if kind=="SYMBOL" else "", int(port) if kind=="SYMBOL" else 0)
        self._update_cable_preview(scene_pos)
        self._emit_cable_point_committed(x=x,y=y,kind=kind,uid=uid if kind=="SYMBOL" else "",port=port if kind=="SYMBOL" else 0,already_connected=already_connected)

    def finish_cable(self) -> None:
        if not self._cable_active:
            return
        data = None
        if len(self._cable_points) >= 2:
            data = dict(self._cable_meta)
            data["points"] = list(self._cable_points)
            connections=core.normalize_cable_symbol_connections(self._cable_connections,len(self._cable_points))
            data["symbol_connections"] = connections
            first=next((r for r in connections if int(r.get("point_index",-1))==0),{})
            last=next((r for r in connections if int(r.get("point_index",-1))==len(self._cable_points)-1),{})
            data["start_symbol_uid"] = str(first.get("symbol_uid","") or "")
            data["start_symbol_port"] = int(first.get("symbol_port",0) or 0)
            data["end_symbol_uid"] = str(last.get("symbol_uid","") or "")
            data["end_symbol_port"] = int(last.get("symbol_port",0) or 0)
        self.cancel_tool(emit_signal=False)
        self.cablePointCommitted.emit({"kind":"FINISHED"})
        if data is not None:
            self.cableFinished.emit(data)

    def cancel_tool(self, emit_signal: bool = True) -> None:
        if self._preview_item is not None:
            if self.snap_engine is not None:
                try:self.snap_engine.clear_wall_lock(self._preview_item.placement.uid)
                except Exception:pass
            if self._preview_item.scene() is not None:
                self.scene().removeItem(self._preview_item)
        if self._cable_preview is not None and self._cable_preview.scene() is not None:
            self.scene().removeItem(self._cable_preview)
        if self._pattern_preview is not None and self._pattern_preview.scene() is not None:
            self.scene().removeItem(self._pattern_preview)
        if self._calibration_preview is not None and self._calibration_preview.scene() is not None:
            self.scene().removeItem(self._calibration_preview)
        if self._room_preview is not None and self._room_preview.scene() is not None:
            self.scene().removeItem(self._room_preview)
        if self._room_axis_guide is not None and self._room_axis_guide.scene() is not None:
            self.scene().removeItem(self._room_axis_guide)
        self._preview_item = None; self._placement_code = ""
        self._cable_preview = None; self._cable_points = []; self._cable_connections = []; self._cable_click_stack = []; self._cable_active = False
        self.cablePreviewChanged.emit([])
        self._calibration_preview = None; self._calibration_start = None; self._calibration_active = False
        self._text_tool = None
        self._pattern_preview = None; self._pattern_start = None; self._pattern_snap_end = None; self._pattern_kind = ""; self._pattern_config = {}
        if self._room_active:self.roomPreviewChanged.emit([])
        self._room_preview=None; self._room_axis_guide=None; self._room_points=[]; self._room_active=False
        self._clear_snap_feedback(); self.unsetCursor()
        if emit_signal:
            self.toolCancelled.emit()

    def _show_snap_feedback(self, scene_pos: QPointF, kind: str) -> None:
        if not kind:
            self._clear_snap_feedback(); return
        if self._snap_marker is None:
            self._snap_marker = QGraphicsEllipseItem(QRectF(-5, -5, 10, 10))
            self._snap_marker.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
            self._snap_marker.setZValue(20000); self.scene().addItem(self._snap_marker)
            self._snap_text = QGraphicsSimpleTextItem("")
            self._snap_text.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
            self._snap_text.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
            self._snap_text.setZValue(20001); self.scene().addItem(self._snap_text)
        snap_color=QColor("#62d9d2") if _canvas_is_dark() else QColor("#008b8b")
        snap_text=QColor("#83e1dc") if _canvas_is_dark() else QColor("#006b6b")
        pen=QPen(snap_color); pen.setCosmetic(True); pen.setWidthF(2.0); self._snap_marker.setPen(pen)
        fill=QColor(snap_color); fill.setAlpha(52 if _canvas_is_dark() else 45); self._snap_marker.setBrush(QBrush(fill))
        self._snap_text.setBrush(QBrush(snap_text))
        signature=(round(float(scene_pos.x()),3),round(float(scene_pos.y()),3),str(kind))
        self._snap_marker.setPos(scene_pos); self._snap_marker.show()
        self._snap_text.setText(kind); self._snap_text.setPos(scene_pos + QPointF(8, -18)); self._snap_text.show()
        if signature!=self._last_snap_signature:
            self._last_snap_signature=signature
            self._snap_pulse_anim.stop(); self._snap_pulse_anim.setStartValue(0.0); self._snap_pulse_anim.setEndValue(1.0); self._snap_pulse_anim.start()

    def _clear_snap_feedback(self) -> None:
        if self._snap_marker is not None: self._snap_marker.hide(); self._snap_marker.setOpacity(1.0); self._snap_marker.setRect(QRectF(-5,-5,10,10))
        if self._snap_text is not None: self._snap_text.hide()
        self._snap_pulse_anim.stop(); self._last_snap_signature=None
        self._clear_alignment_guides()

    def _preview_pose(self, scene_pos: QPointF) -> None:
        if self._preview_item is None:
            return
        raw = _cad_point(scene_pos)
        rot = self._placement_rotation
        kind = ""
        if self.snap_engine is not None:
            (x, y), rot, kind = self.snap_engine.snap_pose(self.scene(), self._placement_code, self._placement_size,
                                                          rot, raw, self.current_scale(),
                                                          ignore_uid=self._preview_item.placement.uid, cursor_cad=raw)
        else:
            x, y = raw
        x, y, align_kind = self._lighting_alignment_snap(self._placement_code, x, y, self._preview_item.placement.uid)
        if align_kind:
            kind = " + ".join(dict.fromkeys([part for part in (kind.split(" + ") if kind else []) + align_kind.split(" + ") if part]))
        self._placement_rotation=float(rot)%360.0
        self._preview_item.set_pose_silent(x, y, self._placement_rotation)
        mount_pts = core.placement_mount_points(self._preview_item.placement)
        marker = _mapped_point(*(mount_pts[0] if mount_pts and "VÆG" in kind else (x, y)))
        self._show_snap_feedback(marker, kind)

    def zoom_by_factor(self, factor: float, anchor_view=None) -> bool:
        """Zoom reliably around a viewport point. Used by wheel and shortcuts.

        Keeping the actual transform change in one method avoids regressions when
        the QGraphicsView is moved between stacked central pages.
        """
        try:
            factor = float(factor)
        except (TypeError, ValueError):
            return False
        if factor <= 0.0:
            return False
        current_zoom = self.current_scale()
        new_zoom = current_zoom * factor
        if not (0.02 <= new_zoom <= 80.0):
            return False

        if self._preview_item is not None and self._preview_item.scene() is not None:
            anchor_scene = self._preview_item.scenePos()
            anchor_view = self.mapFromScene(anchor_scene)
        else:
            if anchor_view is None:
                anchor_view = self.viewport().rect().center()
            anchor_scene = self.mapToScene(anchor_view)

        self.scale(factor, factor)
        self._zoom = self.current_scale()
        after = self.mapToScene(anchor_view)
        delta = after - anchor_scene
        self.translate(delta.x(), delta.y())
        self.zoomChanged.emit(self._zoom)
        self.viewport().update()
        return True

    def zoom_in(self) -> None:
        self.zoom_by_factor(1.18)

    def zoom_out(self) -> None:
        self.zoom_by_factor(1.0 / 1.18)

    def wheelEvent(self, event) -> None:
        # Qt/trackpad drivers can emit zero-delta wheel phases. Never interpret
        # those as zoom-out, but do accept genuine positive and negative input.
        angle_y = event.angleDelta().y()
        pixel_y = event.pixelDelta().y()
        factor = wheel_zoom_factor(angle_y, pixel_y)
        if factor is None:
            event.accept()
            return
        anchor_view = event.position().toPoint()
        self.zoom_by_factor(factor, anchor_view)
        self.last_mouse_scene = self.mapToScene(anchor_view)
        event.accept()

    def mouseDoubleClickEvent(self,event) -> None:
        if self._room_active and event.button()==Qt.MouseButton.LeftButton:
            # The corresponding press has already committed the final vertex.
            self.finish_room(); event.accept(); return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True; self._pan_start = event.position().toPoint(); self.setCursor(Qt.CursorShape.ClosedHandCursor); event.accept(); return
        if event.button() == Qt.MouseButton.LeftButton and self._room_active:
            self._append_room_point(self.mapToScene(event.position().toPoint()),event.modifiers()); event.accept(); return
        if event.button() == Qt.MouseButton.RightButton and self._room_active:
            self.finish_room(); event.accept(); return
        if event.button() == Qt.MouseButton.LeftButton and self._text_tool is not None:
            x,y=_cad_point(self.mapToScene(event.position().toPoint()))
            x,y,kind=self._text_alignment_snap(x,y)
            data=dict(self._text_tool); data.update({"x":x,"y":y})
            self.textPlacementRequested.emit(data)
            self.cancel_tool()
            event.accept(); return
        if event.button() == Qt.MouseButton.LeftButton and self._calibration_active:
            self._append_calibration_point(self.mapToScene(event.position().toPoint()))
            event.accept(); return
        if event.button() == Qt.MouseButton.LeftButton and self._pattern_kind:
            raw=_cad_point(self.mapToScene(event.position().toPoint()))
            px,py,snap_kind=self._lighting_alignment_snap("spot",raw[0],raw[1])
            cad=(px,py)
            if self._pattern_start is None:
                self._pattern_start=cad
                self._pattern_snap_end=cad
                self._show_snap_feedback(_mapped_point(px,py),snap_kind)
                self._update_pattern_preview(self.mapToScene(event.position().toPoint()),event.modifiers())
            else:
                self._update_pattern_preview(self.mapToScene(event.position().toPoint()),event.modifiers())
                end=self._pattern_snap_end or cad
                start=self._pattern_start; config=dict(self._pattern_config); kind=self._pattern_kind
                self.cancel_tool(emit_signal=False)
                self.patternFinished.emit(kind,start,end,config)
            event.accept(); return
        if event.button() == Qt.MouseButton.LeftButton and self._cable_active:
            self._append_cable_point(self.mapToScene(event.position().toPoint()))
            event.accept(); return
        if event.button() == Qt.MouseButton.RightButton and self._cable_active:
            self.finish_cable(); event.accept(); return
        if event.button() == Qt.MouseButton.LeftButton and self._preview_item is not None:
            self._preview_pose(self.mapToScene(event.position().toPoint()))
            p = self._preview_item.placement
            self.placementRequested.emit(self._placement_code, float(p.x), float(p.y), float(p.rotation))
            if self.snap_engine is not None:
                self.snap_engine.clear_wall_lock(p.uid)
            event.accept(); return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        self.last_mouse_scene = self.mapToScene(event.position().toPoint())
        self.mouseSceneMoved.emit(self.last_mouse_scene)
        if self._panning and self._pan_start is not None:
            delta = event.position().toPoint() - self._pan_start; self._pan_start = event.position().toPoint()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y()); event.accept(); return
        if self._room_active:
            self._update_room_preview(self.last_mouse_scene,event.modifiers()); event.accept(); return
        if self._calibration_active:
            self._update_calibration_preview(self.last_mouse_scene); event.accept(); return
        if self._pattern_kind and self._pattern_start is not None:
            self._update_pattern_preview(self.last_mouse_scene,event.modifiers()); event.accept(); return
        if self._cable_active:
            self._update_cable_preview(self.last_mouse_scene); event.accept(); return
        if self._preview_item is not None:
            self._preview_pose(self.last_mouse_scene); event.accept(); return
        if self._text_tool is not None:
            x,y=_cad_point(self.last_mouse_scene)
            x,y,kind=self._text_alignment_snap(x,y)
            self._show_snap_feedback(_mapped_point(x,y),kind)
            event.accept(); return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._panning = False; self._pan_start = None
            self.setCursor(Qt.CursorShape.CrossCursor if self._preview_item is not None else Qt.CursorShape.ArrowCursor)
            event.accept(); return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape and (self._preview_item is not None or self._cable_active or self._calibration_active or self._text_tool is not None or self._pattern_kind or self._room_active):
            self.cancel_tool(); event.accept(); return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self._room_active:
            self.finish_room(); event.accept(); return
        if event.key() == Qt.Key.Key_Backspace and self._room_active:
            self.remove_last_room_point(); event.accept(); return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self._cable_active:
            self.finish_cable(); event.accept(); return
        if event.key() == Qt.Key.Key_Backspace and self._cable_active:
            self.remove_last_cable_point(); event.accept(); return
        super().keyPressEvent(event)

    def fit_scene(self, rect: QRectF | None = None) -> None:
        target = rect or self.scene().itemsBoundingRect()
        if target.isValid() and target.width() > 0 and target.height() > 0:
            self.fitInView(target.adjusted(-20, -20, 20, 20), Qt.AspectRatioMode.KeepAspectRatio)
            self._zoom = max(abs(self.transform().m11()), 1e-9); self.zoomChanged.emit(self._zoom)
