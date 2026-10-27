from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPathItem, QGraphicsSimpleTextItem

import core_logic as core
from annotation_layout import RectSpatialIndex, choose_label_origin, preferred_side_from_vector
from qt_theme import _canvas_dark


def prepare_switch_badge(item, *, placement_uid: str, anchor: QPointF,
                         width_px: float, height_px: float, preferred: str) -> None:
    """Attach layout metadata to a fixed-screen-size switch relation badge."""
    item._elplan_placement_uid = str(placement_uid or "")
    item._elplan_anchor_scene = QPointF(anchor)
    item._elplan_width_px = float(width_px)
    item._elplan_height_px = float(height_px)
    item._elplan_preferred_side = str(preferred or "right")


def _rect_tuple(rect) -> tuple[float, float, float, float]:
    return float(rect.left()), float(rect.top()), float(rect.right()), float(rect.bottom())


def layout_symbol_metadata(annotation_items, symbol_items, switch_badges, scale: float) -> None:
    """Lay out all automatic symbol metadata as one collision-aware layer.

    Relation chips are kept closest to their physical switch module. Group/circuit,
    marking and ordinary relation annotations are then placed around the remaining
    free sides. Symbol silhouettes are hard blockers in both passes.
    """
    scale = max(abs(float(scale or 1.0)), 1e-9)
    visible_symbols = {
        uid: item for uid, item in dict(symbol_items or {}).items()
        if item is not None and item.scene() is not None and item.isVisible()
    }
    blockers = [_rect_tuple(item.sceneBoundingRect()) for item in visible_symbols.values()]
    occupied: list[tuple[float, float, float, float]] = []
    # Screen-sized metadata becomes scene-sized through 1/scale.  A grid near
    # that size keeps collision checks local without changing exact overlap
    # decisions or the deterministic candidate order.
    cell_size=max(48.0/scale,1e-6)
    blocker_index=RectSpatialIndex(blockers,cell_size=cell_size)
    occupied_index=RectSpatialIndex(cell_size=cell_size)

    # Small a/b/c relation tags have first choice because they identify a physical
    # switch module and should stay close to the symbol.
    for badge in list(switch_badges or []):
        if badge is None or badge.scene() is None or not badge.isVisible():
            continue
        uid = str(getattr(badge, "_elplan_placement_uid", "") or "")
        symbol_item = visible_symbols.get(uid)
        anchor = getattr(badge, "_elplan_anchor_scene", None)
        if symbol_item is None or anchor is None:
            continue
        width = max(1.0, float(getattr(badge, "_elplan_width_px", 1.0))) / scale
        height = max(1.0, float(getattr(badge, "_elplan_height_px", 1.0))) / scale
        source = _rect_tuple(symbol_item.sceneBoundingRect())
        preferred = str(getattr(badge, "_elplan_preferred_side", "right") or "right")
        x, y, _side, rect = choose_label_origin(
            (float(anchor.x()), float(anchor.y())), source, width, height,
            blockers=blockers, occupied=occupied, preferred=preferred,
            blocker_index=blocker_index, occupied_index=occupied_index,
            gap=(5.0 if preferred in {"above", "below"} else 7.0) / scale,
            collision_padding=1.6 / scale, y_down=True,
        )
        badge.setPos(QPointF(x, y)); occupied.append(rect); occupied_index.add(rect)

    # Main symbol annotation blocks share the same occupied map. This includes
    # group/circuit, secondary marking, light associations and spot-parent chips.
    for uid, ann in dict(annotation_items or {}).items():
        if ann is None or ann.scene() is None or not ann.isVisible():
            continue
        symbol_item = visible_symbols.get(uid)
        if symbol_item is None:
            continue
        bounds = ann.boundingRect()
        width = max(1.0, float(bounds.width())) / scale
        height = max(1.0, float(bounds.height())) / scale
        source_rect = symbol_item.sceneBoundingRect()
        source = _rect_tuple(source_rect)
        try:
            dx, dy = ann.position_direction_provider(ann.placement) if callable(ann.position_direction_provider) else (1.0, 0.0)
            preferred = preferred_side_from_vector(float(dx), float(dy), y_down=True)
        except Exception:
            preferred = "right"
        anchor = source_rect.center()
        overview = ann._mode() == "Auto" and scale < 0.145 and not ann._is_selected()
        x, y, _side, rect = choose_label_origin(
            (float(anchor.x()), float(anchor.y())), source, width, height,
            blockers=blockers, occupied=occupied, preferred=preferred,
            blocker_index=blocker_index, occupied_index=occupied_index,
            gap=(3.5 if overview else 7.0) / scale,
            collision_padding=1.8 / scale, y_down=True,
        )
        ann.setPos(QPointF(x, y)); occupied.append(rect); occupied_index.add(rect)


def refresh_switch_association_badges(window) -> None:
    """Reuse unchanged switch badges and only rerun their zoom layout."""
    scale=max(window.view.current_scale(),1e-9)
    meta_visible=bool(window.project.layer_visibility.get(core.META_LAYER,True))
    if window.annotation_display_mode in ("Skjult","Minimal") or not meta_visible:
        signature=("hidden",window.annotation_display_mode,meta_visible)
        if signature!=window._switch_badge_render_signature:
            window._clear_switch_association_badges(); window._switch_badge_render_signature=signature
        layout_symbol_metadata(window.annotation_items,window.symbol_items,window.switch_association_badges,scale)
        return

    overview=window.annotation_display_mode=="Auto" and scale<0.145
    dark=_canvas_dark(); specs=[]
    for placement in window.project.placements:
        if core.association_role(placement.symbol)!="switch":continue
        item=window.symbol_items.get(placement.uid)
        if item is None or not item.isVisible():continue
        channels=core.association_channel_letters(placement)
        for _module_no,_base,x,y,_radius,indices in core.association_module_layout(placement.symbol,placement.size):
            letters=[channels[i] for i in indices if i<len(channels) and channels[i]]
            active=placement.uid==window.association_source_uid and window.association_channel_index in indices
            if not letters and not active:continue
            text=" · ".join(letters) if letters else "…"
            anchor=item.mapToScene(QPointF(x,-y)); rect=item.sceneBoundingRect()
            preferred="below" if rect.width()>rect.height()*1.12 else "right"
            specs.append((placement.uid,text,active,anchor,preferred))

    signature=("visible",overview,dark,tuple(
        (uid,text,active,float(anchor.x()),float(anchor.y()),preferred)
        for uid,text,active,anchor,preferred in specs
    ))
    if signature==window._switch_badge_render_signature:
        layout_symbol_metadata(window.annotation_items,window.symbol_items,window.switch_association_badges,scale)
        return

    window._clear_switch_association_badges()
    for uid,text,active,anchor,preferred in specs:
        font=QFont("Segoe UI",5.6 if overview else 7.0,QFont.Weight.DemiBold)
        probe=QGraphicsSimpleTextItem(text); probe.setFont(font); bounds=probe.boundingRect()
        pad_x=3.0 if overview else 4.0; pad_y=0.5 if overview else 1.2
        path=QPainterPath(); path.addRoundedRect(QRectF(0,0,bounds.width()+2*pad_x,bounds.height()+2*pad_y),4,4)
        badge=QGraphicsPathItem(path); badge.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations,True)
        if active:
            pen=QPen(QColor("#e0a04d") if dark else QColor("#d97706"))
            fill=QColor(58,45,31,235) if dark else QColor(255,247,230,235)
            foreground=QColor("#f2b665") if dark else QColor("#a65000")
        else:
            pen=QPen(QColor(104,154,197,160 if overview else 220) if dark else QColor(122,164,199,150 if overview else 205))
            fill=QColor(37,51,65,175 if overview else 235) if dark else QColor(245,250,255,165 if overview else 225)
            foreground=QColor(157,202,239,200 if overview else 240) if dark else QColor(45,91,132,190 if overview else 235)
        pen.setCosmetic(True); pen.setWidthF(1.0 if overview else 1.2)
        badge.setPen(pen); badge.setBrush(QBrush(fill)); badge.setZValue(530); badge.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        label=QGraphicsSimpleTextItem(text,badge); label.setFont(font); label.setBrush(QBrush(foreground)); label.setPos(pad_x,pad_y); label.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        width=bounds.width()+2*pad_x; height=bounds.height()+2*pad_y
        prepare_switch_badge(badge,placement_uid=uid,anchor=anchor,width_px=width,height_px=height,preferred=preferred)
        window.scene.addItem(badge); window.switch_association_badges.append(badge)
    window._switch_badge_render_signature=signature
    layout_symbol_metadata(window.annotation_items,window.symbol_items,window.switch_association_badges,scale)
