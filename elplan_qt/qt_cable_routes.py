from __future__ import annotations

"""Qt overview for physical cable routes grouped by circuit.

Kept outside qt_app.py so the main window only owns the integration hooks. The
actual route graph is derived in cable_routes.py and can later be reused by PDF
or spreadsheet reports without importing Qt.
"""

from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QKeySequence, QPainter, QPainterPath, QPalette, QPen, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from elplan_project.cable_routes import CableRouteGroup, CableRouteTreeRow, cable_route_plain_text
from elplan_qt.qt_table_utils import _configure_resizable_table
from elplan_qt.qt_widgets import _resize_dialog, _set_role


ROLE_CABLE_UIDS = int(Qt.ItemDataRole.UserRole)
ROLE_ROUTE_TEXT = ROLE_CABLE_UIDS + 1


def _fmt_length(value: float | None) -> str:
    return "—" if value is None else f"{float(value):.1f} m"


class CableRouteFlowWidget(QWidget):
    """Read-only graphical route tree with clickable nodes and branches."""

    routeSelected = Signal(object, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._groups: list[CableRouteGroup] = []
        self._hits: list[tuple[QRectF, list[str], str]] = []
        self._selected = -1
        self._hover = -1
        self.setMouseTracking(True)
        self.setMinimumWidth(760)
        self.setMinimumHeight(240)

    @staticmethod
    def _leaf_count(row: CableRouteTreeRow) -> int:
        if not row.children:
            return 1
        return max(1, sum(CableRouteFlowWidget._leaf_count(child) for child in row.children))

    @staticmethod
    def _max_depth(row: CableRouteTreeRow) -> int:
        if not row.children:
            return int(row.depth)
        return max(int(row.depth), *(CableRouteFlowWidget._max_depth(child) for child in row.children))

    def set_groups(self, groups: list[CableRouteGroup]) -> None:
        self._groups = list(groups or [])
        self._selected = -1
        self._hover = -1
        max_depth = 1
        total_h = 28
        for group in self._groups:
            group_leaves = 0
            for component in group.components:
                group_leaves += self._leaf_count(component.tree)
                max_depth = max(max_depth, self._max_depth(component.tree))
            total_h += max(128, 82 + group_leaves * 72) + 14
        self.setMinimumSize(max(760, 210 + max_depth * 190), max(240, total_h))
        self.resize(self.minimumSize())
        self.update()

    def selected_route_text(self) -> str:
        if 0 <= self._selected < len(self._hits):
            return str(self._hits[self._selected][2] or "")
        return ""

    def _colors(self):
        palette = self.palette()
        bg = palette.color(self.backgroundRole())
        base = palette.color(QPalette.ColorRole.Base)
        text = palette.color(QPalette.ColorRole.Text)
        muted = palette.color(QPalette.ColorRole.PlaceholderText)
        border = palette.color(QPalette.ColorRole.Mid)
        return bg, base, text, muted, border

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        _bg, base, text, muted, border = self._colors()
        self._hits = []
        y = 12.0
        node_w, node_h = 118.0, 40.0
        x_step = 190.0

        title_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        node_font = QFont("Segoe UI", 9, QFont.Weight.DemiBold)
        edge_font = QFont("Segoe UI", 7.5, QFont.Weight.Medium)
        hint_font = QFont("Segoe UI", 8)

        for group in self._groups:
            leaves = sum(self._leaf_count(c.tree) for c in group.components)
            card_h = max(128.0, 82.0 + leaves * 72.0)
            card = QRectF(8, y, max(self.width() - 16, 720), card_h)
            card_fill = QColor(base); card_fill.setAlpha(238)
            card_border = QColor(border); card_border.setAlpha(150)
            p.setPen(QPen(card_border, 1.0)); p.setBrush(card_fill); p.drawRoundedRect(card, 12, 12)

            p.setFont(title_font); p.setPen(text)
            p.drawText(QRectF(card.left()+16, card.top()+10, 240, 24), Qt.AlignmentFlag.AlignVCenter, group.circuit_id)
            p.setFont(hint_font); p.setPen(muted)
            p.drawText(QRectF(card.left()+250, card.top()+10, card.width()-270, 24), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                       f"{group.cable_count} fysiske kabler · {_fmt_length(group.total_length_m)}")
            group_hit = QRectF(card.left()+10, card.top()+7, card.width()-20, 30)
            self._hits.append((group_hit, list(group.cable_uids), group.circuit_id))

            cursor_y = card.top() + 58.0
            for component in group.components:
                if len(group.components) > 1:
                    p.setFont(edge_font); p.setPen(muted)
                    p.drawText(QPointF(card.left()+18, cursor_y-8), f"DELNET {component.index}")
                    cursor_y += 12

                positions: dict[int, tuple[float, float, list[str], str]] = {}
                leaf_y = cursor_y

                def layout(row: CableRouteTreeRow, captions: list[str]):
                    nonlocal leaf_y
                    children = list(row.children)
                    child_positions = []
                    clean = row.cycle_target_caption if row.cycle and row.cycle_target_caption else row.node_caption.replace(" ↻", "")
                    current_captions = captions + ([clean] if row.depth else [])
                    if not children:
                        cy = leaf_y
                        leaf_y += 72.0
                    else:
                        for child in children:
                            layout(child, current_captions)
                            child_positions.append(positions[id(child)][1])
                        cy = sum(child_positions) / len(child_positions)
                    cx = card.left() + 24.0 + float(row.depth) * x_step
                    route_captions = [component.root_caption] if row.depth == 0 else current_captions
                    route_text = " → ".join(route_captions) + (" ↻" if row.cycle else "")
                    positions[id(row)] = (cx, cy, list(row.path_cable_uids), f"{group.circuit_id}: {route_text}")

                layout(component.tree, [component.root_caption])

                def draw_edges(row: CableRouteTreeRow):
                    px, py, _uids, _rt = positions[id(row)]
                    parent_rect = QRectF(px, py-node_h/2, node_w, node_h)
                    for child in row.children:
                        cx, cy, _cuids, _crt = positions[id(child)]
                        child_rect = QRectF(cx, cy-node_h/2, node_w, node_h)
                        start = QPointF(parent_rect.right(), parent_rect.center().y())
                        end = QPointF(child_rect.left(), child_rect.center().y())
                        path = QPainterPath(start)
                        bend = max(26.0, (end.x()-start.x()) * 0.46)
                        path.cubicTo(QPointF(start.x()+bend,start.y()), QPointF(end.x()-bend,end.y()), end)
                        edge_pen = QPen(QColor("#5e88ad"), 2.0)
                        if child.cycle:
                            edge_pen.setStyle(Qt.PenStyle.DashLine)
                        edge_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                        p.setPen(edge_pen); p.setBrush(Qt.BrushStyle.NoBrush); p.drawPath(path)
                        edge_label = " · ".join(x for x in (child.cable_id or "Kabel", child.cable_spec, _fmt_length(child.length_m)) if x and x != "—")
                        mid = path.pointAtPercent(0.5)
                        fm = p.fontMetrics()
                        p.setFont(edge_font); fm = p.fontMetrics()
                        ew = fm.horizontalAdvance(edge_label) + 12
                        er = QRectF(mid.x()-ew/2, mid.y()-10, ew, 19)
                        label_fill = QColor(base); label_fill.setAlpha(245)
                        p.setPen(QPen(card_border, 0.8)); p.setBrush(label_fill); p.drawRoundedRect(er, 6, 6)
                        p.setPen(muted); p.drawText(er, Qt.AlignmentFlag.AlignCenter, edge_label)
                        draw_edges(child)

                draw_edges(component.tree)

                def draw_nodes(row: CableRouteTreeRow):
                    x, cy, uids, route_text = positions[id(row)]
                    rect = QRectF(x, cy-node_h/2, node_w, node_h)
                    hit_index = len(self._hits)
                    self._hits.append((rect.adjusted(-4,-4,4,4), list(uids), route_text))
                    active = hit_index == self._selected
                    hover = hit_index == self._hover
                    fill = QColor("#dceafa") if active else (QColor("#edf3fb") if hover else QColor(base))
                    outline = QColor("#2f6fac") if active else (QColor("#6e9bc5") if hover else card_border)
                    if self.palette().color(QPalette.ColorRole.Window).lightness() < 128:
                        fill = QColor("#2b435e") if active else (QColor("#26384b") if hover else QColor(base))
                        outline = QColor("#72a8df") if active else (QColor("#55779c") if hover else card_border)
                    p.setPen(QPen(outline, 1.8 if (active or hover) else 1.0)); p.setBrush(fill); p.drawRoundedRect(rect, 9, 9)
                    dot = QColor("#2f6fac") if not row.cycle else QColor("#b7791f")
                    p.setPen(Qt.PenStyle.NoPen); p.setBrush(dot); p.drawEllipse(QRectF(rect.left()+9, rect.center().y()-4, 8, 8))
                    p.setFont(node_font); p.setPen(text)
                    p.drawText(rect.adjusted(23,2,-6,-2), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, row.node_caption)
                    for child in row.children:
                        draw_nodes(child)

                draw_nodes(component.tree)
                cursor_y = max(cursor_y + 72.0, leaf_y + 4.0)
            y += card_h + 14.0
        p.end()

    def _hit_index(self, pos) -> int:
        point = QPointF(pos)
        for idx, (rect, _uids, _text) in enumerate(self._hits):
            if rect.contains(point):
                return idx
        return -1

    def mouseMoveEvent(self, event) -> None:
        idx = self._hit_index(event.position())
        if idx != self._hover:
            self._hover = idx
            self.setCursor(Qt.CursorShape.PointingHandCursor if idx >= 0 else Qt.CursorShape.ArrowCursor)
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = -1
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self._hit_index(event.position())
            if idx >= 0:
                self._selected = idx
                _rect, uids, route_text = self._hits[idx]
                self.routeSelected.emit(list(uids), str(route_text or ""))
                self.update()
                event.accept()
                return
        super().mousePressEvent(event)


class CableRoutesDialog(QDialog):
    """Modeless route browser that can highlight derived cable paths on the plan."""

    def __init__(
        self,
        parent=None,
        *,
        snapshot_provider: Callable[[], list[CableRouteGroup]],
        highlight_callback: Callable[[list[str]], None] | None = None,
        marking_provider: Callable[[], list[dict]] | None = None,
        marking_edit_callback: Callable[[str], None] | None = None,
        marking_mode_callback: Callable[[], None] | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Kabeltræk / ruteforløb")
        self.setModal(False)
        _resize_dialog(self, 1040, 700)
        self._snapshot_provider = snapshot_provider
        self._highlight_callback = highlight_callback
        self._marking_provider = marking_provider
        self._marking_edit_callback = marking_edit_callback
        self._marking_mode_callback = marking_mode_callback
        self._groups: list[CableRouteGroup] = []
        self._filtered_groups: list[CableRouteGroup] = []
        self._building = False

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 12)
        root.setSpacing(9)

        title = QLabel("Kabeltræk")
        title.setObjectName("dialogTitle")
        root.addWidget(title)
        hint = QLabel(
            "Visningen bygges automatisk af de fysiske kabler. Gruppe/kreds er den logiske streng, "
            "mens hvert K-nummer fortsat er et selvstændigt kabel med egen type og længde."
        )
        hint.setWordWrap(True)
        hint.setObjectName("subtleText")
        root.addWidget(hint)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Søg gruppe, lampested, kabel-ID eller kabeltype…")
        self.search.setClearButtonEnabled(True)
        filters.addWidget(self.search, 1)
        self.group_combo = QComboBox()
        self.group_combo.setMinimumWidth(190)
        filters.addWidget(self.group_combo)
        self.auto_highlight = QCheckBox("Fremhæv ved valg")
        self.auto_highlight.setChecked(True)
        filters.addWidget(self.auto_highlight)
        refresh = _set_role(QPushButton("Opdatér"), "quietButton")
        refresh.clicked.connect(self.refresh)
        filters.addWidget(refresh)
        root.addLayout(filters)

        self.summary = QLabel("")
        self.summary.setObjectName("sectionHint")
        root.addWidget(self.summary)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        flow_page = QWidget()
        flow_layout = QVBoxLayout(flow_page)
        flow_layout.setContentsMargins(0, 6, 0, 0)
        self.flow_scroll = QScrollArea()
        self.flow_scroll.setWidgetResizable(False)
        self.flow_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.flow = CableRouteFlowWidget()
        self.flow_scroll.setWidget(self.flow)
        flow_layout.addWidget(self.flow_scroll, 1)
        flow_hint = QLabel("Klik på en node for at fremhæve kabelvejen dertil. Klik på gruppeoverskriften for at fremhæve hele gruppen.")
        flow_hint.setObjectName("subtleText"); flow_hint.setWordWrap(True); flow_layout.addWidget(flow_hint)
        self.tabs.addTab(flow_page, "Flow")

        tree_page = QWidget()
        tree_layout = QVBoxLayout(tree_page)
        tree_layout.setContentsMargins(0, 6, 0, 0)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Forløb / installationspunkt", "Kabel", "Type", "Længde"])
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setAlternatingRowColors(True)
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        tree_layout.addWidget(self.tree, 1)
        tree_hint = QLabel("Klik på en gruppe for at fremhæve hele gruppen, eller på et punkt for at fremhæve ruten fra tavlen/roden dertil.")
        tree_hint.setObjectName("subtleText")
        tree_hint.setWordWrap(True)
        tree_layout.addWidget(tree_hint)
        self.tabs.addTab(tree_page, "Træ")

        list_page = QWidget()
        list_layout = QVBoxLayout(list_page)
        list_layout.setContentsMargins(0, 6, 0, 0)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Gruppe/kreds", "Kabeltræk", "Kabler", "Kabeltype", "Længde"])
        _configure_resizable_table(self.table, "cable_routes_overview", (110, 430, 180, 170, 95))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        list_layout.addWidget(self.table, 1)
        list_hint = QLabel("Én linje pr. ende/forgrening. Fælles stræk gentages med vilje, så hver rute kan læses som Tavle → X → X → X.")
        list_hint.setObjectName("subtleText")
        list_hint.setWordWrap(True)
        list_layout.addWidget(list_hint)
        self.tabs.addTab(list_page, "Liste")

        marking_page = QWidget()
        marking_layout = QVBoxLayout(marking_page)
        marking_layout.setContentsMargins(0, 6, 0, 0)
        marking_intro = QLabel("Mærkning er altid aktivt styret af brugeren. Forslag vises kun som hjælp; intet kabel ændres, før du åbner det og klikker Anvend.")
        marking_intro.setObjectName("subtleText"); marking_intro.setWordWrap(True); marking_layout.addWidget(marking_intro)
        self.marking_table = QTableWidget(0, 6)
        self.marking_table.setHorizontalHeaderLabels(["Status", "Kabel", "Gruppe/kreds", "Fra → til", "Ekstra mærkning", "Forslag"])
        _configure_resizable_table(self.marking_table, "cable_marking_overview", (76, 82, 110, 260, 220, 260))
        self.marking_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.marking_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.marking_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.marking_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.marking_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        marking_layout.addWidget(self.marking_table, 1)
        mark_actions = QHBoxLayout()
        self.mark_selected = QPushButton("Mærk valgt på plantegningen")
        self.mark_selected.clicked.connect(self._edit_selected_marking)
        mark_actions.addWidget(self.mark_selected)
        start_marking = _set_role(QPushButton("Start grafisk mærkning"), "quietButton")
        start_marking.clicked.connect(self._start_graphical_marking)
        start_marking.setEnabled(self._marking_mode_callback is not None)
        mark_actions.addWidget(start_marking)
        mark_actions.addStretch(1)
        self.marking_summary = QLabel(""); self.marking_summary.setObjectName("sectionHint"); mark_actions.addWidget(self.marking_summary)
        marking_layout.addLayout(mark_actions)
        self.tabs.addTab(marking_page, "Mærkning")

        bottom = QHBoxLayout()
        self.copy_selected = _set_role(QPushButton("Kopiér valgte rute"), "quietButton")
        self.copy_selected.clicked.connect(self._copy_selected)
        bottom.addWidget(self.copy_selected)
        copy_all = _set_role(QPushButton("Kopiér alle"), "quietButton")
        copy_all.clicked.connect(self._copy_all)
        bottom.addWidget(copy_all)
        bottom.addStretch(1)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.close)
        bottom.addWidget(close)
        root.addLayout(bottom)

        self.search.textChanged.connect(self._apply_filters)
        self.group_combo.currentIndexChanged.connect(self._apply_filters)
        self.flow.routeSelected.connect(self._flow_selection_changed)
        self.tree.itemSelectionChanged.connect(self._tree_selection_changed)
        self.table.itemSelectionChanged.connect(self._table_selection_changed)
        self.marking_table.itemSelectionChanged.connect(self._marking_selection_changed)
        self.marking_table.itemDoubleClicked.connect(lambda _item:self._edit_selected_marking())
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.search.setFocus)

        self.refresh()

    def refresh(self) -> None:
        try:
            groups = list(self._snapshot_provider() or [])
        except Exception:
            groups = []
        self._groups = groups
        previous = str(self.group_combo.currentData() or "") if self.group_combo.count() else ""
        self._building = True
        self.group_combo.clear()
        self.group_combo.addItem("Alle grupper", "")
        for group in groups:
            self.group_combo.addItem(group.circuit_id, group.circuit_id)
        idx = self.group_combo.findData(previous)
        self.group_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._building = False
        self._apply_filters()

    def _group_matches(self, group: CableRouteGroup, query: str) -> bool:
        if not query:
            return True
        haystack = [group.circuit_id]
        for path in group.paths:
            haystack.extend([path.route_text, path.cable_text, path.spec_text])
        return query in " ".join(haystack).casefold()

    def _apply_filters(self, *_args) -> None:
        if self._building:
            return
        query = self.search.text().strip().casefold()
        selected_group = str(self.group_combo.currentData() or "")
        self._filtered_groups = [
            group for group in self._groups
            if (not selected_group or group.circuit_id == selected_group) and self._group_matches(group, query)
        ]
        self.flow.set_groups(self._filtered_groups)
        self._populate_tree()
        self._populate_table()
        self._populate_marking_table()
        cables = sum(group.cable_count for group in self._filtered_groups)
        paths = sum(len(group.paths) for group in self._filtered_groups)
        self.summary.setText(
            f"{len(self._filtered_groups)} gruppe{'r' if len(self._filtered_groups) != 1 else ''} · "
            f"{cables} fysiske kabler · {paths} læsbare rute{'r' if paths != 1 else ''}"
        )


    def _filtered_marking_rows(self) -> list[dict]:
        if self._marking_provider is None:
            return []
        try:
            rows=list(self._marking_provider() or [])
        except Exception:
            rows=[]
        query=self.search.text().strip().casefold()
        selected_group=str(self.group_combo.currentData() or "")
        out=[]
        for row in rows:
            if selected_group and str(row.get("circuit_id","") or "") != selected_group:
                continue
            hay=" ".join(str(row.get(key,"") or "") for key in ("cable_id","circuit_id","route","marking","suggestion")).casefold()
            if query and query not in hay:
                continue
            out.append(row)
        return out

    def _populate_marking_table(self) -> None:
        rows=self._filtered_marking_rows()
        self._building=True
        self.marking_table.setRowCount(len(rows))
        marked=0
        for r,row in enumerate(rows):
            is_marked=bool(row.get("marked")); marked+=1 if is_marked else 0
            values=["✓ Mærket" if is_marked else "+ Mangler", str(row.get("cable_id","") or "Kabel"), str(row.get("circuit_id","") or "—"), str(row.get("route","") or "—"), str(row.get("marking","") or "—"), str(row.get("suggestion","") or "—")]
            for c,value in enumerate(values):
                item=QTableWidgetItem(value)
                if c==0:
                    item.setData(ROLE_CABLE_UIDS,[str(row.get("uid","") or "")])
                    item.setData(ROLE_ROUTE_TEXT,str(row.get("uid","") or ""))
                self.marking_table.setItem(r,c,item)
        self._building=False
        self.marking_summary.setText(f"{marked}/{len(rows)} mærket" if rows else "Ingen kabler")
        self.mark_selected.setEnabled(bool(rows) and self._marking_edit_callback is not None)

    def _marking_selection_changed(self) -> None:
        if self._building:return
        row=self.marking_table.currentRow()
        item=self.marking_table.item(row,0) if row>=0 else None
        if item is not None:self._highlight(item.data(ROLE_CABLE_UIDS) or [])

    def _selected_marking_uid(self) -> str:
        row=self.marking_table.currentRow()
        item=self.marking_table.item(row,0) if row>=0 else None
        uids=item.data(ROLE_CABLE_UIDS) if item is not None else []
        return str((uids or [""])[0] or "")

    def _edit_selected_marking(self) -> None:
        uid=self._selected_marking_uid()
        if uid and self._marking_edit_callback is not None:
            self.close(); self._marking_edit_callback(uid)

    def _start_graphical_marking(self) -> None:
        if self._marking_mode_callback is not None:
            self.close(); self._marking_mode_callback()

    def _populate_tree(self) -> None:
        self._building = True
        self.tree.clear()
        for group in self._filtered_groups:
            total = _fmt_length(group.total_length_m)
            group_item = QTreeWidgetItem([group.circuit_id, f"{group.cable_count} kabler", "", total])
            group_item.setData(0, ROLE_CABLE_UIDS, list(group.cable_uids))
            group_item.setData(0, ROLE_ROUTE_TEXT, group.circuit_id)
            font = group_item.font(0)
            font.setBold(True)
            group_item.setFont(0, font)
            self.tree.addTopLevelItem(group_item)
            multiple = len(group.components) > 1
            for component in group.components:
                parent = group_item
                if multiple:
                    comp_item = QTreeWidgetItem([f"Delnet {component.index} · rod: {component.root_caption}", "", "", ""])
                    comp_item.setData(0, ROLE_CABLE_UIDS, list(component.cable_uids))
                    comp_item.setData(0, ROLE_ROUTE_TEXT, f"{group.circuit_id}: {component.root_caption}")
                    group_item.addChild(comp_item)
                    parent = comp_item
                root_row = component.tree
                root_item = QTreeWidgetItem([root_row.node_caption, "Start", "", ""])
                root_item.setToolTip(0, root_row.node_detail_caption)
                root_item.setData(0, ROLE_CABLE_UIDS, [])
                root_item.setData(0, ROLE_ROUTE_TEXT, f"{group.circuit_id}: {root_row.node_caption}")
                parent.addChild(root_item)
                self._add_tree_children(group.circuit_id, root_item, root_row, [root_row.node_caption])
            group_item.setExpanded(True)
        self.tree.expandToDepth(2)
        self._building = False

    def _add_tree_children(self, circuit_id: str, parent_item: QTreeWidgetItem, row: CableRouteTreeRow, captions: list[str]) -> None:
        for child in row.children:
            item = QTreeWidgetItem([
                child.node_caption,
                child.cable_id or "—",
                child.cable_spec or "—",
                _fmt_length(child.length_m),
            ])
            item.setToolTip(0, child.node_detail_caption)
            item.setData(0, ROLE_CABLE_UIDS, list(child.path_cable_uids))
            clean_caption = child.cycle_target_caption if child.cycle and child.cycle_target_caption else child.node_caption.replace(" ↻", "")
            route_text = " → ".join(captions + [clean_caption]) + (" ↻" if child.cycle else "")
            item.setData(0, ROLE_ROUTE_TEXT, f"{circuit_id}: {route_text}")
            parent_item.addChild(item)
            self._add_tree_children(circuit_id, item, child, captions + [clean_caption])

    def _populate_table(self) -> None:
        rows = [(group, path) for group in self._filtered_groups for path in group.paths]
        self._building = True
        self.table.setRowCount(len(rows))
        for row, (group, path) in enumerate(rows):
            values = [group.circuit_id, path.route_text, path.cable_text or "—", path.spec_text or "—", _fmt_length(path.length_m)]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 4:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if col == 0:
                    item.setData(ROLE_CABLE_UIDS, list(path.cable_uids))
                    item.setData(ROLE_ROUTE_TEXT, f"{group.circuit_id}: {path.route_text}")
                self.table.setItem(row, col, item)
        self._building = False

    def _highlight(self, cable_uids) -> None:
        if not self.auto_highlight.isChecked() or self._highlight_callback is None:
            return
        uids = [str(x) for x in (cable_uids or []) if str(x)]
        if uids:
            self._highlight_callback(uids)

    def _flow_selection_changed(self, cable_uids, route_text: str) -> None:
        if self._building:
            return
        self._flow_route_text = str(route_text or "")
        self._highlight(cable_uids or [])

    def _tree_selection_changed(self) -> None:
        if self._building:
            return
        items = self.tree.selectedItems()
        if not items:
            return
        self._highlight(items[0].data(0, ROLE_CABLE_UIDS) or [])

    def _table_selection_changed(self) -> None:
        if self._building:
            return
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        if item is not None:
            self._highlight(item.data(ROLE_CABLE_UIDS) or [])

    def _selected_route_text(self) -> str:
        if self.tabs.currentIndex() == 0:
            return self.flow.selected_route_text() or str(getattr(self, "_flow_route_text", "") or "")
        if self.tabs.currentIndex() == 1:
            items = self.tree.selectedItems()
            return str(items[0].data(0, ROLE_ROUTE_TEXT) or "") if items else ""
        if self.tabs.currentIndex() == 2:
            row = self.table.currentRow()
            item = self.table.item(row, 0) if row >= 0 else None
            return str(item.data(ROLE_ROUTE_TEXT) or "") if item is not None else ""
        return ""

    def _copy_selected(self) -> None:
        text = self._selected_route_text()
        if text:
            QApplication.clipboard().setText(text)

    def _copy_all(self) -> None:
        text = cable_route_plain_text(self._filtered_groups)
        if text:
            QApplication.clipboard().setText(text)
