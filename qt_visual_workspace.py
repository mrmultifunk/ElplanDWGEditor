from __future__ import annotations

"""Visual workspace helpers for 0.56.x.

The module deliberately owns presentation-only state: active-workflow feedback,
selection emphasis, group focus and the compact inspector summary. It does not
write project data.
"""

from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QEvent, QPointF, QRectF, QTimer, Qt, Signal, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import core_logic as core
from qt_graphics import CadLayerItem, CableItem, ElectricalSymbolItem


class WorkflowBar(QFrame):
    finishRequested = Signal()
    undoRequested = Signal()
    cancelRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("workflowBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        root = QHBoxLayout(self)
        root.setContentsMargins(10, 7, 8, 7)
        root.setSpacing(8)

        self.mode = QLabel("AKTIV")
        self.mode.setObjectName("workflowMode")
        self.mode.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.mode)

        text = QVBoxLayout()
        text.setSpacing(0)
        self.title = QLabel("Arbejdsgang")
        self.title.setObjectName("workflowTitle")
        self.detail = QLabel("")
        self.detail.setObjectName("workflowDetail")
        self.detail.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        text.addWidget(self.title)
        text.addWidget(self.detail)
        root.addLayout(text, 1)

        self.undo_button = QPushButton("Fortryd punkt")
        self.undo_button.setObjectName("workflowQuietButton")
        self.undo_button.clicked.connect(lambda _checked=False: self.undoRequested.emit())
        root.addWidget(self.undo_button)

        self.finish_button = QPushButton("Afslut")
        self.finish_button.setObjectName("workflowPrimaryButton")
        self.finish_button.clicked.connect(lambda _checked=False: self.finishRequested.emit())
        root.addWidget(self.finish_button)

        self.cancel_button = QPushButton("Esc")
        self.cancel_button.setObjectName("workflowQuietButton")
        self.cancel_button.setToolTip("Afslut den aktive arbejdsgang")
        self.cancel_button.clicked.connect(lambda _checked=False: self.cancelRequested.emit())
        root.addWidget(self.cancel_button)
        self.hide()

    def set_state(self, state: dict | None) -> None:
        state = dict(state or {})
        active = bool(state.get("active", False))
        self.setVisible(active)
        if not active:
            return
        self.mode.setText(str(state.get("mode", "AKTIV") or "AKTIV").upper())
        self.title.setText(str(state.get("title", "Arbejdsgang") or "Arbejdsgang"))
        self.detail.setText(str(state.get("detail", "") or ""))
        self.undo_button.setVisible(bool(state.get("undo", False)))
        self.undo_button.setEnabled(bool(state.get("undo_enabled", True)))
        self.finish_button.setVisible(bool(state.get("finish", False)))
        self.finish_button.setText(str(state.get("finish_text", "Afslut") or "Afslut"))
        self.cancel_button.setText(str(state.get("cancel_text", "Esc") or "Esc"))


class CableCategoryStrip(QFrame):
    """Floating, glanceable visibility controls for cable categories.

    The strip mirrors the layer/category visibility state only.  It never owns
    project data; MainWindow remains the source of truth and receives toggles
    through ``visibilityChanged``.
    """

    visibilityChanged = Signal(str, bool)
    configureRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cableCategoryStrip")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._buttons: dict[str, QToolButton] = {}
        self._records: list[dict] = []

        root = QHBoxLayout(self)
        root.setContentsMargins(7, 5, 6, 5)
        root.setSpacing(5)
        title = QLabel("KABLER")
        title.setObjectName("cableCategoryStripTitle")
        root.addWidget(title)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("cableCategoryScroll")
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setFixedHeight(34)
        self.scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._content = QWidget()
        self._content.setObjectName("cableCategoryStripContent")
        self._layout = QHBoxLayout(self._content)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self._layout.addStretch(1)
        self.scroll.setWidget(self._content)
        root.addWidget(self.scroll, 1)

        self.configure_button = QToolButton()
        self.configure_button.setObjectName("cableCategoryConfigure")
        self.configure_button.setText("⋯")
        self.configure_button.setToolTip("Konfigurér kabelkategorier")
        self.configure_button.clicked.connect(lambda _checked=False: self.configureRequested.emit())
        root.addWidget(self.configure_button)
        self.hide()

    @staticmethod
    def _sample_icon(record: dict, visible: bool) -> QIcon:
        pm = QPixmap(24, 14)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor(str(record.get("color") or "#64748b")) if visible else QColor("#94a3b8")
        pen = QPen(color, 3.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        line_style = str(record.get("line_style") or "solid")
        pen.setStyle({
            "dash": Qt.PenStyle.DashLine,
            "dot": Qt.PenStyle.DotLine,
            "dashdot": Qt.PenStyle.DashDotLine,
        }.get(line_style, Qt.PenStyle.SolidLine))
        painter.setPen(pen)
        painter.drawLine(3, 7, 21, 7)
        if not visible:
            slash = QPen(QColor("#64748b"), 1.6)
            slash.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(slash)
            painter.drawLine(5, 12, 19, 2)
        painter.end()
        return QIcon(pm)

    def set_categories(self, records, visible_provider) -> None:
        records = [dict(x) for x in (records or [])]
        signature = [(str(r.get("id", "")), str(r.get("name", ""))) for r in records]
        old_signature = [(str(r.get("id", "")), str(r.get("name", ""))) for r in self._records]
        if signature != old_signature:
            while self._layout.count():
                item = self._layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
            self._buttons.clear()
            for rec in records:
                cid = str(rec.get("id") or "")
                button = QToolButton()
                button.setObjectName("cableCategoryChip")
                button.setCheckable(True)
                button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                button.setText(str(rec.get("name") or cid or "Kategori"))
                button.setProperty("categoryId", cid)
                button.toggled.connect(lambda checked, category_id=cid: self.visibilityChanged.emit(category_id, bool(checked)))
                self._layout.addWidget(button)
                self._buttons[cid] = button
            self._layout.addStretch(1)
            self._records = records
        else:
            self._records = records

        for rec in records:
            cid = str(rec.get("id") or "")
            button = self._buttons.get(cid)
            if button is None:
                continue
            visible = bool(visible_provider(cid))
            button.blockSignals(True)
            button.setChecked(visible)
            button.setIcon(self._sample_icon(rec, visible))
            button.setProperty("categoryVisible", visible)
            button.setToolTip(
                f"{rec.get('name') or cid} · {'vist' if visible else 'skjult'}\n"
                "Klik for at ændre synlighed."
            )
            button.style().unpolish(button)
            button.style().polish(button)
            button.blockSignals(False)
        self.setVisible(bool(records))


class InspectorSummaryCard(QFrame):
    """Compact at-a-glance object identity above the inspector forms."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("inspectorSummaryCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 9)
        root.setSpacing(5)

        top = QHBoxLayout()
        top.setSpacing(7)
        self.kind = QLabel("OBJEKT")
        self.kind.setObjectName("inspectorSummaryKind")
        self.identity = QLabel("—")
        self.identity.setObjectName("inspectorSummaryIdentity")
        self.identity.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        top.addWidget(self.kind)
        top.addWidget(self.identity, 1)
        root.addLayout(top)

        self.route = QLabel("")
        self.route.setObjectName("inspectorSummaryRoute")
        self.route.setWordWrap(True)
        root.addWidget(self.route)

        chips = QHBoxLayout()
        chips.setSpacing(5)
        self.chip_a = QLabel("")
        self.chip_b = QLabel("")
        self.chip_c = QLabel("")
        for chip in (self.chip_a, self.chip_b, self.chip_c):
            chip.setObjectName("inspectorSummaryChip")
            chips.addWidget(chip)
        chips.addStretch(1)
        root.addLayout(chips)
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)
        self._fade = QVariantAnimation(self)
        self._fade.setDuration(130); self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.valueChanged.connect(lambda value: self._opacity_effect.setOpacity(float(value)))
        self.hide()

    def clear(self) -> None:
        self.hide()

    def show_data(self, *, kind: str, identity: str, route: str = "", chips=()) -> None:
        was_hidden=not self.isVisible()
        self.kind.setText(str(kind or "OBJEKT").upper())
        self.identity.setText(str(identity or "—"))
        self.route.setText(str(route or ""))
        self.route.setVisible(bool(str(route or "").strip()))
        values = [str(x or "").strip() for x in chips]
        for label, value in zip((self.chip_a, self.chip_b, self.chip_c), values + ["", "", ""]):
            label.setText(value)
            label.setVisible(bool(value))
        self.show()
        if was_hidden:
            self._fade.stop(); self._fade.setStartValue(0.55); self._fade.setEndValue(1.0); self._fade.start()


class MiniMapView(QWidget):
    """Minimal electrical navigator with no labels or screen-space annotations.

    The old mini-map reused the live QGraphicsScene directly. Items such as cable
    labels and annotations ignore view transforms, so their text overwhelmed the
    tiny preview. This widget deliberately renders only CAD linework, physical
    cables, symbol positions and the current viewport.
    """

    centerRequested = Signal(object)

    def __init__(self, scene, main_view, parent=None):
        super().__init__(parent)
        self._scene = scene
        self._main_view = main_view
        self._overview_rect = QRectF()
        self._scale = 1.0
        self._offset = QPointF()
        self.setObjectName("miniMapView")
        self.setFixedSize(190, 118)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.refresh_overview()

    def _content_rect(self) -> QRectF:
        rect = QRectF()
        try:
            items = list(self._scene.items())
        except Exception:
            return rect
        # Prefer actual CAD geometry because CadLayerItem._path excludes CAD text.
        for item in items:
            if not item.isVisible():
                continue
            if isinstance(item, CadLayerItem):
                try: r = item.sceneTransform().map(item._path).boundingRect()
                except Exception: r = item.sceneBoundingRect()
            elif isinstance(item, CableItem):
                try: r = item.sceneTransform().map(item.path()).boundingRect()
                except Exception: r = item.sceneBoundingRect()
            elif isinstance(item, ElectricalSymbolItem):
                try:
                    pt = item.sceneBoundingRect().center()
                    r = QRectF(pt.x()-1.0, pt.y()-1.0, 2.0, 2.0)
                except Exception:
                    continue
            else:
                continue
            if r.isNull() or r.isEmpty():
                continue
            rect = QRectF(r) if rect.isNull() else rect.united(r)
        return rect

    def refresh_overview(self) -> None:
        rect = self._content_rect()
        if rect.isNull() or rect.isEmpty():
            try: rect = self._main_view.mapToScene(self._main_view.viewport().rect()).boundingRect()
            except Exception: rect = QRectF(0, 0, 1, 1)
        margin=max(rect.width(),rect.height())*0.025+1.0
        self._overview_rect=rect.adjusted(-margin,-margin,margin,margin)
        self.update()

    def _prepare_mapping(self, target: QRectF) -> None:
        src=self._overview_rect
        if src.isNull() or src.isEmpty():
            self._scale=1.0; self._offset=QPointF(target.left(),target.top()); return
        sx=target.width()/max(src.width(),1e-9); sy=target.height()/max(src.height(),1e-9)
        self._scale=max(1e-9,min(sx,sy))
        used_w=src.width()*self._scale; used_h=src.height()*self._scale
        self._offset=QPointF(target.center().x()-used_w/2-src.left()*self._scale,
                             target.center().y()-used_h/2-src.top()*self._scale)

    def _map_scene_point(self, point: QPointF) -> QPointF:
        return QPointF(point.x()*self._scale+self._offset.x(), point.y()*self._scale+self._offset.y())

    def _map_scene_rect(self, rect: QRectF) -> QRectF:
        a=self._map_scene_point(rect.topLeft()); b=self._map_scene_point(rect.bottomRight())
        return QRectF(a,b).normalized()

    def paintEvent(self,event) -> None:
        QWidget.paintEvent(self,event)
        painter=QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing,True)
        outer=QRectF(self.rect()).adjusted(0.5,0.5,-0.5,-0.5)
        try: dark=QColor(self._main_view.backgroundBrush().color()).lightness()<100
        except Exception: dark=False
        painter.setPen(QPen(QColor("#4c5968") if dark else QColor("#c6d0dc"),1.0))
        painter.setBrush(QColor(26,31,37,232) if dark else QColor(250,252,254,242))
        painter.drawRoundedRect(outer,8,8)
        target=outer.adjusted(8,8,-8,-8)
        self._prepare_mapping(target)

        # CAD linework only – CAD text is intentionally omitted.
        painter.save()
        painter.translate(self._offset); painter.scale(self._scale,self._scale)
        cad_pen=QPen(QColor(125,139,154,130) if dark else QColor(108,122,137,115),0.0); cad_pen.setCosmetic(True)
        painter.setPen(cad_pen); painter.setBrush(Qt.BrushStyle.NoBrush)
        try: items=list(self._scene.items())
        except Exception: items=[]
        for item in items:
            if not item.isVisible() or not isinstance(item,CadLayerItem): continue
            try: painter.drawPath(item.sceneTransform().map(item._path))
            except Exception: pass
        cable_pen=QPen(QColor("#5fa7e8") if dark else QColor("#2f6fa8"),1.15); cable_pen.setCosmetic(True)
        painter.setPen(cable_pen)
        for item in items:
            if not item.isVisible() or not isinstance(item,CableItem): continue
            try: painter.drawPath(item.sceneTransform().map(item.path()))
            except Exception: pass
        painter.restore()

        # Symbols are tiny locator dots; no IDs, labels, categories or BOM data.
        symbol_pen=QPen(QColor("#dce6ef") if dark else QColor("#334155"),1.0); symbol_pen.setCosmetic(True)
        painter.setPen(symbol_pen); painter.setBrush(QColor("#8fbfe8") if dark else QColor("#ffffff"))
        for item in items:
            if not item.isVisible() or not isinstance(item,ElectricalSymbolItem): continue
            try: c=self._map_scene_point(item.sceneBoundingRect().center())
            except Exception: continue
            painter.drawEllipse(c,2.0,2.0)

        # Current viewport is the only overlay information.
        try: visible=self._main_view.mapToScene(self._main_view.viewport().rect()).boundingRect()
        except Exception: visible=QRectF()
        if not visible.isNull() and not visible.isEmpty():
            view_rect=self._map_scene_rect(visible)
            accent=QColor(114,168,223,220); fill=QColor(114,168,223,30)
            pen=QPen(accent,1.3); pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen); painter.setBrush(fill); painter.drawRoundedRect(view_rect,3,3)
        painter.end()

    def mousePressEvent(self,event) -> None:
        if event.button()==Qt.MouseButton.LeftButton:
            pos=event.position()
            if self._scale>1e-9:
                scene_pos=QPointF((pos.x()-self._offset.x())/self._scale,(pos.y()-self._offset.y())/self._scale)
                self.centerRequested.emit(scene_pos)
            event.accept(); return
        super().mousePressEvent(event)


class VisualWorkspaceMixin:
    """Presentation-only behavior shared by MainWindow."""

    def _migrate_visual_workspace_settings(self, settings: dict) -> dict:
        data=dict(settings or {})
        if not bool(data.get("navigator_hidden_default_v0572",False)):
            data["show_navigator"]=False
            data["navigator_hidden_default_v0572"]=True
            core.save_app_settings(data)
        return data

    _FOCUS_GROUP_DIM = 0.16
    _FOCUS_GROUP_SYMBOL_DIM = 0.22
    _SELECTED_CABLE_PEER = 0.52
    _SELECTED_CABLE_OTHER = 0.14
    _SELECTED_SYMBOL_OTHER = 0.30

    def _create_visual_workspace(self) -> None:
        self._focus_group_id = ""
        self._trace_group_id = ""
        self._trace_order = []
        self._trace_reveal_count = 0
        self._trace_persistent_flow=False
        self._trace_timer=QTimer(self); self._trace_timer.setInterval(85); self._trace_timer.timeout.connect(self._advance_trace_reveal)
        self.workflow_bar = WorkflowBar(self.view.viewport())
        self.workflow_bar.finishRequested.connect(self._workflow_finish)
        self.workflow_bar.undoRequested.connect(self._workflow_undo)
        self.workflow_bar.cancelRequested.connect(self._workflow_cancel)
        self.cable_category_strip = CableCategoryStrip(self.view.viewport())
        self.cable_category_strip.visibilityChanged.connect(self._visual_category_visibility_changed)
        self.cable_category_strip.configureRequested.connect(self.open_cable_categories_dialog)
        self.navigator=MiniMapView(self.scene,self.view,self.view.viewport())
        self.navigator.centerRequested.connect(self._navigator_center_requested)
        self.navigator.setVisible(bool(getattr(getattr(self,"act_navigator",None),"isChecked",lambda:True)()))
        self._apply_overlay_depth(self.workflow_bar,18,3)
        self._apply_overlay_depth(self.cable_category_strip,14,2)
        self._apply_overlay_depth(self.navigator,16,3)
        self.view.viewport().installEventFilter(self)
        self._refresh_cable_category_strip()
        # The category chip strip duplicated Vis → Kabelkategorier and consumed
        # valuable drawing space. Keep the object for backwards/test compatibility
        # but never paint it on the canvas.
        self.cable_category_strip.hide()
        self._position_workflow_bar()
        self._refresh_workflow_bar()

    def _reset_visual_workspace_transients(self) -> None:
        """Clear presentation-only state before switching project/CAD scene."""
        self._focus_group_id = ""
        timer = getattr(self, "_trace_timer", None)
        if timer is not None:
            timer.stop()
        self._trace_group_id = ""
        self._trace_order = []
        self._trace_reveal_count = 0
        self._trace_persistent_flow = False

    @staticmethod
    def _apply_overlay_depth(widget, blur: float=16.0, y: float=3.0) -> None:
        effect=QGraphicsDropShadowEffect(widget); effect.setBlurRadius(float(blur)); effect.setOffset(0.0,float(y)); effect.setColor(QColor(0,0,0,55)); widget.setGraphicsEffect(effect)

    def _navigator_center_requested(self, scene_pos) -> None:
        try:self.view.centerOn(QPointF(scene_pos)); self.view.viewport().update(); self.navigator.update()
        except Exception:pass

    def toggle_navigator(self, checked: bool) -> None:
        nav=getattr(self,"navigator",None)
        if nav is None:return
        nav.setVisible(bool(checked))
        if checked:nav.refresh_overview(); nav.raise_()
        self._position_workflow_bar()

    def refresh_navigator(self) -> None:
        nav=getattr(self,"navigator",None)
        if nav is not None and nav.isVisible():nav.refresh_overview()

    def eventFilter(self, watched, event):
        if watched is getattr(getattr(self, "view", None), "viewport", lambda: None)():
            if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
                self._position_workflow_bar()
        try:
            return super().eventFilter(watched, event)
        except AttributeError:
            return False

    def _position_workflow_bar(self) -> None:
        bar = getattr(self, "workflow_bar", None)
        viewport = getattr(getattr(self, "view", None), "viewport", lambda: None)()
        if bar is None or viewport is None:
            return
        width = max(360, min(820, int(viewport.width()) - 28))
        if viewport.width() < 420:
            width = max(280, int(viewport.width()) - 16)
        bar.setFixedWidth(width)
        bar.adjustSize()
        bar.move(max(8, (viewport.width() - width) // 2), 10)
        bar.raise_()
        strip = getattr(self, "cable_category_strip", None)
        if strip is not None and strip.isVisible():
            strip_width = max(300, min(1060, int(viewport.width()) - 24))
            strip.setFixedWidth(strip_width)
            strip.adjustSize()
            y = 10 if not bar.isVisible() else bar.geometry().bottom() + 7
            strip.move(max(8, (viewport.width() - strip_width) // 2), y)
            strip.raise_()
        nav=getattr(self,"navigator",None)
        if nav is not None and nav.isVisible():
            nav.move(max(8,viewport.width()-nav.width()-14),max(8,viewport.height()-nav.height()-14)); nav.raise_()

    def _refresh_cable_category_strip(self) -> None:
        strip = getattr(self, "cable_category_strip", None)
        if strip is None or not hasattr(self, "_cable_categories"):
            return
        strip.set_categories(self._cable_categories(), self._cable_category_is_visible)
        strip.hide()
        self._position_workflow_bar()

    def _visual_category_visibility_changed(self, category_id: str, visible: bool) -> None:
        self._set_cable_category_visible(category_id, visible)
        self._refresh_cable_category_strip()

    def _workflow_state(self) -> dict:
        view = getattr(self, "view", None)
        if view is None:
            return {"active": False}

        if bool(getattr(view, "_cable_active", False)):
            meta = dict(getattr(view, "_cable_meta", {}) or {})
            group = ""
            spec = ""
            cid = ""
            if hasattr(self, "cable_group_edit"):
                group = self.cable_group_edit.text().strip()
            if hasattr(self, "cable_spec_combo"):
                spec = self.cable_spec_combo.currentText().strip()
            if hasattr(self, "cable_id_edit"):
                cid = self.cable_id_edit.text().strip()
            group = group or str(meta.get("circuit_id", "") or "").strip()
            spec = spec or str(meta.get("cable_spec", "") or "").strip()
            cid = cid or str(meta.get("cable_id", "") or "").strip()
            points = len(getattr(view, "_cable_click_stack", []) or [])
            connections = len(getattr(view, "_cable_connections", []) or [])
            details = [x for x in (group, spec, cid) if x]
            details.append(f"{points} punkt{'er' if points != 1 else ''}")
            if connections:
                details.append(f"{connections} tilslutning{'er' if connections != 1 else ''}")
            return {
                "active": True,
                "mode": "KABELTRÆK",
                "title": "Tegn kabelstreng",
                "detail": "  ·  ".join(details),
                "undo": True,
                "undo_enabled": points > 0,
                "finish": points >= 2,
                "finish_text": "Afslut kabel",
                "cancel_text": "Esc · luk",
            }

        if bool(getattr(self,"_cable_marking_active",False)):
            marked=sum(1 for c in getattr(self.project,"cables",[]) if str(getattr(c,"label","") or "").strip())
            total=len(getattr(self.project,"cables",[]) or [])
            return {
                "active": True,
                "mode": "KABELMÆRKNING",
                "title": "Mærk fysiske kabler",
                "detail": f"{marked}/{total} mærket · klik et kabel · forslag anvendes kun efter Anvend",
                "finish": False,
                "undo": False,
                "cancel_text": "Esc · afslut",
            }

        if bool(getattr(view,"_room_active",False)):
            points=len(getattr(view,"_room_points",[]) or [])
            return {
                "active": True,
                "mode": "RUM",
                "title": "Skitser rumafgrænsning",
                "detail": f"{points} punkt{'er' if points != 1 else ''} · klik langs væggene · Enter/dobbeltklik afslutter",
                "undo": True,
                "undo_enabled": points > 0,
                "finish": points >= 3,
                "finish_text": "Afslut rum",
                "cancel_text": "Esc · annullér",
            }

        if str(getattr(view, "_placement_code", "") or ""):
            code = str(view._placement_code)
            return {
                "active": True,
                "mode": "PLACERING",
                "title": core.symbol_display_name(code),
                "detail": "Klik på tegningen for at placere · Esc afslutter",
                "finish": False,
                "undo": False,
                "cancel_text": "Esc · afslut",
            }

        if getattr(view, "_text_tool", None) is not None:
            return {
                "active": True,
                "mode": "TEKST",
                "title": "Placér tekst",
                "detail": "Klik på tegningen for at placere teksten",
                "finish": False,
                "undo": False,
                "cancel_text": "Esc · annullér",
            }

        pattern = str(getattr(view, "_pattern_kind", "") or "")
        if pattern:
            title = "Spot-felt" if pattern == "rect" else "Spot-række"
            started = getattr(view, "_pattern_start", None) is not None
            return {
                "active": True,
                "mode": "SPOTS",
                "title": title,
                "detail": "Vælg modstående hjørne" if started and pattern == "rect" else ("Vælg slutpunkt" if started else "Vælg startpunkt"),
                "finish": False,
                "undo": False,
                "cancel_text": "Esc · annullér",
            }

        if bool(getattr(view, "_calibration_active", False)):
            return {
                "active": True,
                "mode": "KALIBRERING",
                "title": "Kabellængdeskala",
                "detail": "Klik to punkter med kendt afstand",
                "finish": False,
                "undo": False,
                "cancel_text": "Esc · annullér",
            }

        if str(getattr(self, "association_source_uid", "") or "") or bool(getattr(self, "association_pick_source", False)):
            return {
                "active": True,
                "mode": "TILHØRSFORHOLD",
                "title": "Tilknyt lys og afbryder",
                "detail": "Klik på det fremhævede mål · Esc afslutter",
                "finish": False,
                "undo": False,
                "cancel_text": "Esc · afslut",
            }
        return {"active": False}

    def _refresh_workflow_bar(self) -> None:
        bar = getattr(self, "workflow_bar", None)
        if bar is None:
            return
        bar.set_state(self._workflow_state())
        self._position_workflow_bar()

    def _workflow_finish(self) -> None:
        if bool(getattr(self.view,"_room_active",False)):
            self.view.finish_room()
        elif bool(getattr(self.view, "_cable_active", False)):
            self.view.finish_cable()
        self._refresh_workflow_bar()

    def _workflow_undo(self) -> None:
        if bool(getattr(self.view,"_room_active",False)):
            self.view.remove_last_room_point()
        elif bool(getattr(self.view, "_cable_active", False)):
            self.view.remove_last_cable_point()
            if hasattr(self, "_update_cable_tool_status"):
                self._update_cable_tool_status()
        self._refresh_workflow_bar()

    def _workflow_cancel(self) -> None:
        if bool(getattr(self,"_cable_marking_active",False)) and hasattr(self,"act_cable_marking"):
            self.act_cable_marking.setChecked(False)
        else:
            self.view.cancel_tool()
        self._refresh_workflow_bar()

    def zoom_to_selection(self) -> None:
        items=list(self.scene.selectedItems())
        if not items:
            if hasattr(self,"_notify"):self._notify("Vælg et symbol eller kabel først.",kind="warning")
            return
        rect=QRectF()
        for item in items:
            try:r=item.sceneBoundingRect()
            except Exception:continue
            rect=QRectF(r) if rect.isNull() else rect.united(r)
        if rect.isNull() or rect.isEmpty():return
        margin=max(20.0,max(rect.width(),rect.height())*0.45)
        rect=rect.adjusted(-margin,-margin,margin,margin)
        if self.view.animate_to_scene_rect(rect,padding_px=110.0) and hasattr(self,"_notify"):
            self._notify("Zoomer til valgte objekt.",kind="info",timeout=1200)

    def _trace_cable_order(self, group: str) -> list[int]:
        cables=[c for c in self.project.cables if str(getattr(c,"circuit_id","") or "").strip()==str(group or "").strip()]
        if not cables:return []
        by_uid={str(p.uid):p for p in self.project.placements}
        edges=[]; adjacency={}
        for c in cables:
            conns=core.cable_symbol_connections(c)
            ordered=sorted(conns,key=lambda r:int(r.get("point_index",0) or 0))
            a=str(ordered[0].get("symbol_uid","") or "") if ordered else ""
            b=str(ordered[-1].get("symbol_uid","") or "") if ordered else ""
            edges.append((c,a,b)); adjacency.setdefault(a,[]).append((c,b)); adjacency.setdefault(b,[]).append((c,a))
        start=""
        for uid,p in by_uid.items():
            if uid in adjacency and str(getattr(p,"symbol","") or "") in {"group_board","distribution_board"}:start=uid; break
        if not start:
            endpoints=[uid for uid,rows in adjacency.items() if uid and len(rows)==1]
            start=endpoints[0] if endpoints else next((uid for uid in adjacency if uid),"")
        seen=set(); order=[]; queue=[start] if start else []
        seen_nodes=set(queue)
        while queue:
            uid=queue.pop(0)
            for cable,other in adjacency.get(uid,[]):
                key=id(cable)
                if key in seen:continue
                seen.add(key); order.append(key)
                if other and other not in seen_nodes:seen_nodes.add(other); queue.append(other)
        for c in cables:
            if id(c) not in seen:order.append(id(c))
        return order

    def trace_selected_circuit(self) -> None:
        group=self._selected_focus_group()
        if not group:
            if hasattr(self,"_notify"):self._notify("Det valgte objekt har ingen gruppe/kreds at spore.",kind="warning")
            return
        self._focus_group_id=group; self._trace_group_id=group; self._trace_order=self._trace_cable_order(group); self._trace_reveal_count=0; self._trace_persistent_flow=True
        self._trace_timer.stop(); self._apply_visual_emphasis()
        if self._trace_order:self._trace_timer.start()
        if hasattr(self,"_notify"):self._notify(f"Sporer {group} fra tavle gennem kabeltrækket.",kind="info",timeout=1700)
        self._refresh_focus_actions()

    def _advance_trace_reveal(self) -> None:
        self._trace_reveal_count=min(len(self._trace_order),self._trace_reveal_count+1); self._apply_visual_emphasis()
        if self._trace_reveal_count>=len(self._trace_order):
            self._trace_timer.stop()
            if not bool(getattr(self,"_trace_persistent_flow",False)):
                self._trace_group_id=""; self._trace_order=[]; self._trace_reveal_count=0; self._apply_visual_emphasis()

    def clear_trace_circuit(self) -> None:
        self._trace_timer.stop(); self._trace_group_id=""; self._trace_order=[]; self._trace_reveal_count=0; self._trace_persistent_flow=False; self._apply_visual_emphasis()

    def _selected_focus_group(self) -> str:
        selected_cables = [x for x in self.scene.selectedItems() if isinstance(x, CableItem)]
        selected_symbols = [x for x in self.scene.selectedItems() if isinstance(x, ElectricalSymbolItem)]
        if len(selected_cables) == 1 and not selected_symbols:
            return str(getattr(selected_cables[0].cable, "circuit_id", "") or "").strip()
        if len(selected_symbols) == 1 and not selected_cables:
            p = selected_symbols[0].placement
            direct = str(getattr(p, "group", "") or "").strip()
            if direct:
                return direct
            # A symbol without its own group can still sit on a grouped cable.
            uid = str(getattr(p, "uid", "") or "")
            for cable in self.project.cables:
                if any(str(r.get("symbol_uid", "") or "") == uid for r in core.cable_symbol_connections(cable)):
                    group = str(getattr(cable, "circuit_id", "") or "").strip()
                    if group:
                        return group
        return ""

    def focus_selected_group(self) -> None:
        group = self._selected_focus_group()
        if not group:
            if hasattr(self, "_notify"):
                self._notify("Det valgte objekt har ingen gruppe/kreds at fokusere på.", kind="warning")
            self._refresh_focus_actions()
            return
        self._focus_group_id = group
        self._trace_group_id=group; self._trace_order=self._trace_cable_order(group); self._trace_reveal_count=0; self._trace_persistent_flow=False
        self._trace_timer.stop(); self._apply_visual_emphasis()
        if self._trace_order:self._trace_timer.start()
        self._refresh_focus_actions()
        if hasattr(self, "_set_status"):
            self._set_status(f"Fokus: {group} · øvrige symboler og kabler er dæmpet.")

    def clear_group_focus(self) -> None:
        if not str(getattr(self, "_focus_group_id", "") or ""):
            return
        self._focus_group_id = ""
        self._trace_timer.stop(); self._trace_group_id=""; self._trace_order=[]; self._trace_reveal_count=0; self._trace_persistent_flow=False
        self._apply_visual_emphasis()
        self._refresh_focus_actions()
        if hasattr(self, "_set_status"):
            self._set_status("Gruppefokus afsluttet.")

    def toggle_selected_group_focus(self) -> None:
        current = str(getattr(self, "_focus_group_id", "") or "")
        selected = self._selected_focus_group()
        if current and (not selected or selected == current):
            self.clear_group_focus()
        else:
            self.focus_selected_group()

    def _refresh_focus_actions(self) -> None:
        group = str(getattr(self, "_focus_group_id", "") or "")
        selected = self._selected_focus_group()
        action = getattr(self, "act_focus_group", None)
        if action is not None:
            action.setEnabled(bool(selected) or bool(group))
            action.setChecked(bool(group))
            action.setText(f"Afslut fokus · {group}" if group else (f"Fokusér gruppe · {selected}" if selected else "Fokusér valgt gruppe"))
        ctx = getattr(self, "act_ctx_focus_group", None)
        if ctx is not None:
            ctx.setVisible(bool(selected) or bool(group))
            ctx.setText(f"Afslut fokus · {group}" if group else (f"Fokusér {selected}" if selected else "Fokusér gruppe"))

    @staticmethod
    def _placement_groups(placement) -> set[str]:
        values = {
            str(getattr(placement, "group", "") or "").strip(),
            str(getattr(placement, "socket_group", "") or "").strip(),
        }
        switch_group = str(getattr(placement, "switch_group", "") or "")
        values.update(part.strip() for part in switch_group.split(","))
        return {v for v in values if v}

    def _group_symbol_uids(self, group: str) -> set[str]:
        group = str(group or "").strip()
        if not group:
            return set()
        uids = {
            str(p.uid)
            for p in self.project.placements
            if group in self._placement_groups(p)
        }
        for cable in self.project.cables:
            if str(getattr(cable, "circuit_id", "") or "").strip() != group:
                continue
            for rec in core.cable_symbol_connections(cable):
                uid = str(rec.get("symbol_uid", "") or "")
                if uid:
                    uids.add(uid)
        return uids

    def _apply_visual_emphasis(self) -> None:
        """Apply presentation-only opacity hierarchy.

        Priority: explicit group focus > selected cable > legacy selected-symbol
        cable focus > normal view. Visibility is never changed here.
        """
        focus_group = str(getattr(self, "_focus_group_id", "") or "").strip()
        selected_cables = [x for x in self.scene.selectedItems() if isinstance(x, CableItem)]
        selected_symbols = [x for x in self.scene.selectedItems() if isinstance(x, ElectricalSymbolItem)]
        selected_cable = selected_cables[0].cable if len(selected_cables) == 1 and not selected_symbols else None

        cable_opacity = {id(c): 1.0 for c in self.project.cables}
        symbol_opacity = {str(p.uid): 1.0 for p in self.project.placements}
        bom_placements=set(getattr(self,"_bom_highlight_placement_uids",set()) or set())
        bom_cables=set(getattr(self,"_bom_highlight_cable_uids",set()) or set())
        focus_room=str(getattr(self,"_focus_room_id","") or "").strip()

        if bom_placements or bom_cables:
            for cable in self.project.cables:
                uid=str(getattr(cable,"uid","") or "")
                cable_opacity[id(cable)]=1.0 if uid in bom_cables else 0.09
            for p in self.project.placements:
                symbol_opacity[str(p.uid)]=1.0 if str(p.uid) in bom_placements else 0.12
        elif focus_room:
            for cable in self.project.cables:
                room_uids={str(getattr(r,"uid","") or "") for r in core.cable_rooms(cable,self.project.rooms)}
                cable_opacity[id(cable)]=1.0 if focus_room in room_uids else 0.10
            for p in self.project.placements:
                room=core.room_for_point(self.project.rooms,float(getattr(p,"x",0.0)),float(getattr(p,"y",0.0)))
                symbol_opacity[str(p.uid)]=1.0 if str(getattr(room,"uid","") or "")==focus_room else 0.12
        elif focus_group:
            focus_uids = self._group_symbol_uids(focus_group)
            trace_group=str(getattr(self,"_trace_group_id","") or "")
            trace_order=list(getattr(self,"_trace_order",[]) or [])
            reveal=int(getattr(self,"_trace_reveal_count",0) or 0)
            revealed=set(trace_order[:reveal]) if trace_group==focus_group and trace_order else set()
            for cable in self.project.cables:
                group = str(getattr(cable, "circuit_id", "") or "").strip()
                if group!=focus_group:cable_opacity[id(cable)]=self._FOCUS_GROUP_DIM
                elif revealed and id(cable) not in revealed:cable_opacity[id(cable)]=0.22
                else:cable_opacity[id(cable)]=1.0
            if revealed:
                revealed_uids=set()
                for cable in self.project.cables:
                    if id(cable) in revealed:
                        revealed_uids.update(str(r.get("symbol_uid","") or "") for r in core.cable_symbol_connections(cable))
                for p in self.project.placements:
                    uid=str(p.uid); symbol_opacity[uid]=1.0 if uid in revealed_uids else (0.40 if uid in focus_uids else self._FOCUS_GROUP_SYMBOL_DIM)
            else:
                for p in self.project.placements:
                    symbol_opacity[str(p.uid)] = 1.0 if str(p.uid) in focus_uids else self._FOCUS_GROUP_SYMBOL_DIM
        elif selected_cable is not None:
            group = str(getattr(selected_cable, "circuit_id", "") or "").strip()
            peer_uids = self._group_symbol_uids(group) if group else {
                str(r.get("symbol_uid", "") or "") for r in core.cable_symbol_connections(selected_cable)
            }
            for cable in self.project.cables:
                if cable is selected_cable:
                    cable_opacity[id(cable)] = 1.0
                elif group and str(getattr(cable, "circuit_id", "") or "").strip() == group:
                    cable_opacity[id(cable)] = self._SELECTED_CABLE_PEER
                else:
                    cable_opacity[id(cable)] = self._SELECTED_CABLE_OTHER
            for p in self.project.placements:
                symbol_opacity[str(p.uid)] = 0.92 if str(p.uid) in peer_uids else self._SELECTED_SYMBOL_OTHER
        else:
            legacy_uid = ""
            if (
                len(selected_symbols) == 1
                and hasattr(self, "cable_focus_related")
                and self.cable_focus_related.isChecked()
            ):
                legacy_uid = str(selected_symbols[0].placement.uid)
            if legacy_uid:
                for cable in self.project.cables:
                    related = any(
                        str(r.get("symbol_uid", "") or "") == legacy_uid
                        for r in core.cable_symbol_connections(cable)
                    )
                    cable_opacity[id(cable)] = 1.0 if related else 0.14

        trace_group=str(getattr(self,"_trace_group_id","") or "")
        trace_revealed=set((getattr(self,"_trace_order",[]) or [])[:int(getattr(self,"_trace_reveal_count",0) or 0)])
        for cable in self.project.cables:
            item = self.cable_items.get(id(cable))
            if item is not None:
                item.setOpacity(float(cable_opacity.get(id(cable), 1.0)))
                group=str(getattr(cable,"circuit_id","") or "").strip()
                trace_active=bool(trace_group and group==trace_group and (not trace_revealed or id(cable) in trace_revealed))
                if hasattr(item,"set_trace_active"):item.set_trace_active(trace_active)
        for p in self.project.placements:
            opacity = float(symbol_opacity.get(str(p.uid), 1.0))
            item = self.symbol_items.get(str(p.uid))
            if item is not None:
                item.setOpacity(opacity)
            ann = self.annotation_items.get(str(p.uid))
            if ann is not None:
                ann.setOpacity(opacity)
        if hasattr(self,"room_label_items"):
            for uid,item in self.room_label_items.items():
                item.setOpacity(1.0 if not focus_room or str(uid)==focus_room else 0.18)
        if hasattr(self,"room_boundary_items"):
            for uid,item in self.room_boundary_items.items():
                item.setOpacity(1.0 if not focus_room or str(uid)==focus_room else 0.18)
        self._refresh_focus_actions()
        nav=getattr(self,"navigator",None)
        if nav is not None and nav.isVisible():nav.viewport().update()

    def _update_inspector_summary(self, *, cable=None, placement=None) -> None:
        card = getattr(self, "inspector_summary", None)
        if card is None:
            return
        if cable is not None:
            identity = str(getattr(cable, "cable_id", "") or "Kabel").strip()
            spec = str(getattr(cable, "cable_spec", "") or "—").strip()
            group = str(getattr(cable, "circuit_id", "") or "—").strip()
            connections = core.cable_symbol_connections(cable)
            names = [self._cable_symbol_caption(r.get("symbol_uid", "")) for r in connections]
            route = " → ".join(x for x in names if x) or "Fri kabelrute"
            factor, _source = self._length_scale_info() if hasattr(self, "_length_scale_info") else (None, "")
            length = core.cable_length_metres(cable, factor) if factor is not None else None
            length_text = self._fmt_metres(length) if length is not None and hasattr(self, "_fmt_metres") else "Længde —"
            card.show_data(
                kind="KABEL",
                identity=identity,
                route=route,
                chips=(f"Gruppe {group}", spec, length_text),
            )
            return
        if placement is not None:
            identity = str(getattr(placement, "group", "") or getattr(placement, "label", "") or core.symbol_display_name(placement.symbol)).strip()
            secondary = " · ".join(
                x for x in (str(getattr(placement, "group", "") or "").strip(), str(getattr(placement, "label", "") or "").strip()) if x
            )
            chips = [core.symbol_display_name(placement.symbol)]
            if getattr(placement, "locked", False):
                chips.append("Låst")
            card.show_data(kind="SYMBOL", identity=identity, route=secondary if secondary != identity else "", chips=chips)
            return
        card.clear()
