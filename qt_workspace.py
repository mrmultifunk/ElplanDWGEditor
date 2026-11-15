from __future__ import annotations

"""Main-window workspace/inspector chrome.

This module contains the 0.53.x GUI foundation: the calm fixed toolbar, the
selection-aware context toolbar, the unified right-side inspector, and
machine-local dock/window layout persistence. Feature-specific editors stay in
qt_app.py and are merely hosted here.
"""

from PySide6.QtCore import QByteArray, QSignalBlocker, QSize, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QStackedWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

import core_logic as core
from qt_commands import EditCableCommand
from qt_graphics import CableItem, ElectricalSymbolItem
from qt_ui import UI, make_context_caption, make_inspector_header, prepare_dock
from qt_visual_workspace import InspectorSummaryCard


class WorkspaceUiMixin:
    """Reusable main-window chrome independent from drawing feature code."""

    @staticmethod
    def _cable_category_menu_text(name: str, visible: bool) -> str:
        # QAction-checkmarken er ikke tydelig på alle Windows/Qt themes, især når
        # handlingen samtidig har kategoriens farveikon. Tilstanden står derfor
        # altid eksplicit i teksten og kan aflæses uden at tolke ikon/checkmark.
        return f"{name}  ·  {'VIST' if visible else 'SKJULT'}"

    def _update_cable_category_menu_summary(self) -> None:
        menu = getattr(self, "cable_categories_menu", None)
        if menu is None:
            return
        categories = self._cable_categories()
        visible_count = sum(1 for rec in categories if self._cable_category_is_visible(rec["id"]))
        menu.setTitle(f"Kabelkategorier ({visible_count}/{len(categories)} vist)")
        menu.setToolTip(
            f"{visible_count} af {len(categories)} kabelkategorier er vist. "
            "Klik en kategori for at vise/skjule den."
        )

    def _cable_category_menu_toggled(self, action: QAction, category_id: str, checked: bool) -> None:
        self._set_cable_category_visible(category_id, checked)
        rec = self._cable_category_record(category_id)
        action.setText(self._cable_category_menu_text(rec["name"], checked))
        definition = str(rec.get("description", "") or "").strip()
        style_label = core.CABLE_LINE_STYLES.get(rec["line_style"], rec["line_style"])
        state = f"Tilstand: {'VIST' if checked else 'SKJULT'}"
        action.setToolTip("\n".join(part for part in (state, definition, style_label) if part))

    def _refresh_cable_categories_menu(self) -> None:
        menu = getattr(self, "cable_categories_menu", None)
        if menu is None:
            return
        menu.clear()
        for rec in self._cable_categories():
            visible = self._cable_category_is_visible(rec["id"])
            action = QAction(self._cable_category_menu_text(rec["name"], visible), self, checkable=True)
            action.setChecked(visible)
            pix = QPixmap(12, 12)
            pix.fill(QColor(rec["color"]))
            action.setIcon(QIcon(pix))
            definition = str(rec.get("description", "") or "").strip()
            style_label = core.CABLE_LINE_STYLES.get(rec["line_style"], rec["line_style"])
            state = f"Tilstand: {'VIST' if visible else 'SKJULT'}"
            action.setToolTip("\n".join(part for part in (state, definition, style_label) if part))
            action.toggled.connect(
                lambda checked, a=action, cid=rec["id"]: self._cable_category_menu_toggled(a, cid, checked)
            )
            menu.addAction(action)
        menu.addSeparator()
        menu.addAction(self.act_cable_categories)
        self._update_cable_category_menu_summary()

    def _create_toolbar(self) -> None:
        # The fixed row is intentionally short. Rare actions live in menus or
        # appear in the context row only when they are relevant.
        tb = QToolBar("Hovedværktøjer", self)
        tb.setObjectName("mainToolbar")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setIconSize(QSize(UI.toolbar_icon, UI.toolbar_icon))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, tb)
        self.main_toolbar = tb

        tb.addAction(self.act_open_project)
        tb.addAction(self.act_save)
        tb.addSeparator()
        tb.addAction(self.act_undo)
        tb.addAction(self.act_redo)
        tb.addSeparator()
        tb.addAction(self.act_global_search)
        tb.addSeparator()
        tb.addAction(self.act_cable)
        tb.addAction(self.act_cable_marking)
        tb.addAction(self.act_text)
        tb.addAction(self.act_room_draw)
        tb.addSeparator()
        tb.addAction(self.act_fit)
        tb.addAction(self.act_preview)

        ctx = QToolBar("Kontekst", self)
        ctx.setObjectName("contextToolbar")
        ctx.setMovable(False)
        ctx.setFloatable(False)
        ctx.setIconSize(QSize(UI.toolbar_icon, UI.toolbar_icon))
        ctx.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, ctx)
        self.context_toolbar = ctx

        self.context_caption = make_context_caption("Tegn")
        self.context_caption_action = ctx.addWidget(self.context_caption)
        self.act_ctx_focus_group = QAction("Fokusér gruppe", self)
        self.act_ctx_focus_group.setToolTip("Dæmp alt uden for den valgte gruppe/kreds. Klik igen for at afslutte fokus.")
        self.act_ctx_focus_group.triggered.connect(lambda _checked=False: self.toggle_selected_group_focus())
        ctx.addAction(self.act_ctx_focus_group)
        self.act_ctx_trace_group=QAction("Spor gruppe",self); self.act_ctx_trace_group.setToolTip("Vis forbindelsesvejen sekventielt fra tavlen.")
        self.act_ctx_trace_group.triggered.connect(lambda _checked=False:self.trace_selected_circuit()); ctx.addAction(self.act_ctx_trace_group)
        self.act_ctx_zoom_selection=QAction("Zoom til",self); self.act_ctx_zoom_selection.triggered.connect(lambda _checked=False:self.zoom_to_selection()); ctx.addAction(self.act_ctx_zoom_selection)

        # Dedicated actions are used so hiding context buttons never hides the
        # corresponding menu actions elsewhere in the application.
        self.act_ctx_spot_line = QAction("Spot-række", self)
        self.act_ctx_spot_line.triggered.connect(self.start_spot_line_dialog)
        self.act_ctx_spot_rect = QAction("Spot-felt", self)
        self.act_ctx_spot_rect.triggered.connect(self.start_spot_rect_dialog)
        self.act_ctx_lighting_snap = QAction("Lys-snap", self, checkable=True)
        self.act_ctx_lighting_snap.setChecked(self.act_lighting_snap.isChecked())
        self.act_ctx_lighting_snap.toggled.connect(self.act_lighting_snap.setChecked)
        self.act_lighting_snap.toggled.connect(self.act_ctx_lighting_snap.setChecked)
        self.ctx_general_actions = [self.act_ctx_spot_line, self.act_ctx_spot_rect, self.act_ctx_lighting_snap]
        for action in self.ctx_general_actions:
            ctx.addAction(action)

        self.act_ctx_rotate = QAction("Rotér 90°", self)
        self.act_ctx_rotate.triggered.connect(self.rotate_selected_90)
        self.act_ctx_associate = QAction("Tilknyt lys", self)
        self.act_ctx_associate.triggered.connect(self.start_association_mode)
        self.act_ctx_same_switch = QAction("Samme tænding…", self)
        self.act_ctx_same_switch.setToolTip("Saml de valgte fysiske lampesteder på én afbryderkanal uden at lægge symbolerne oven i hinanden.")
        self.act_ctx_same_switch.triggered.connect(self.group_selected_lights_same_switch)
        self.act_ctx_pl = QAction("PL-dåse…", self)
        self.act_ctx_pl.setToolTip("Åbn PL-dåsekonfiguratoren for det valgte lampested.")
        self.act_ctx_pl.triggered.connect(self.open_pl_box_for_selection)
        self.act_ctx_bom = QAction("Artikler…", self)
        self.act_ctx_bom.setToolTip("Vis eller redigér artikler/stykliste for det valgte symbol.")
        self.act_ctx_bom.triggered.connect(self.open_bom_for_selection)
        self.act_ctx_delete = QAction("Slet", self)
        self.act_ctx_delete.triggered.connect(self.delete_selected_symbols)
        self.ctx_symbol_actions = [
            self.act_ctx_rotate,
            self.act_ctx_associate,
            self.act_ctx_same_switch,
            self.act_ctx_pl,
            self.act_ctx_bom,
        ]
        for action in self.ctx_symbol_actions:
            ctx.addAction(action)

        ctx.addSeparator()
        self.context_cable_category = QComboBox()
        self.context_cable_category.setToolTip(
            "Kabelkategori for det valgte kabel. Ændringen gemmes straks og kan fortrydes."
        )
        self.context_cable_category_action = ctx.addWidget(self.context_cable_category)
        self.context_cable_route = QComboBox()
        self.context_cable_route.addItem("Fri / diagonal", "free")
        self.context_cable_route.addItem("Ortogonal (90°)", "orthogonal")
        self.context_cable_route.setToolTip(
            "Global ruteføring for det valgte kabel. Lokale afsnitsvalg redigeres i Egenskaber."
        )
        self.context_cable_route_action = ctx.addWidget(self.context_cable_route)
        self.act_ctx_cable_panel = QAction("Flere kabeldata…", self)
        self.act_ctx_cable_panel.triggered.connect(lambda: self._show_inspector_page("cable"))
        ctx.addAction(self.act_ctx_cable_panel)
        ctx.addAction(self.act_ctx_delete)

        self.context_cable_category.currentIndexChanged.connect(self._context_cable_category_changed)
        self.context_cable_route.currentIndexChanged.connect(self._context_cable_route_changed)
        self._context_toolbar_loading = False
        self._refresh_context_toolbar()

    def _context_selected_cable(self):
        selected = [x for x in self.scene.selectedItems() if isinstance(x, CableItem)]
        symbols = [x for x in self.scene.selectedItems() if isinstance(x, ElectricalSymbolItem)]
        return selected[0].cable if len(selected) == 1 and not symbols else None

    def _refresh_context_toolbar(self) -> None:
        if not hasattr(self, "context_toolbar"):
            return
        symbols = [x for x in self.scene.selectedItems() if isinstance(x, ElectricalSymbolItem)]
        cables = [x for x in self.scene.selectedItems() if isinstance(x, CableItem)]
        total = len(symbols) + len(cables)
        cable = cables[0].cable if len(cables) == 1 and not symbols else None
        symbol = symbols[0].placement if len(symbols) == 1 and not cables else None

        for action in self.ctx_general_actions + self.ctx_symbol_actions:
            action.setVisible(False)
        self.context_cable_category_action.setVisible(False)
        self.context_cable_route_action.setVisible(False)
        self.act_ctx_cable_panel.setVisible(False)
        self.act_ctx_delete.setVisible(False)
        self.act_ctx_delete.setEnabled(True)
        self.act_ctx_delete.setToolTip("Slet valgte objekter. Handlingen kan fortrydes.")
        if hasattr(self, "act_ctx_focus_group"):
            self.act_ctx_focus_group.setVisible(False)
        if hasattr(self,"act_ctx_trace_group"):self.act_ctx_trace_group.setVisible(False)
        if hasattr(self,"act_ctx_zoom_selection"):self.act_ctx_zoom_selection.setVisible(False)

        if cable is not None:
            title = core.cable_display_label(cable) or cable.cable_id or "Kabel"
            self.context_caption.setText(f"Kabel · {title}")
            self._context_toolbar_loading = True
            try:
                blocker = QSignalBlocker(self.context_cable_category)
                self.context_cable_category.clear()
                for rec in self._cable_categories():
                    self.context_cable_category.addItem(rec["name"], rec["id"])
                    idx = self.context_cable_category.count() - 1
                    self.context_cable_category.setItemData(
                        idx, str(rec.get("description", "") or ""), Qt.ItemDataRole.ToolTipRole
                    )
                idx = self.context_cable_category.findData(
                    core.normalize_cable_category_id(
                        getattr(cable, "cable_category", core.DEFAULT_CABLE_CATEGORY)
                    )
                )
                self.context_cable_category.setCurrentIndex(max(0, idx))
                del blocker

                blocker = QSignalBlocker(self.context_cable_route)
                mode = "orthogonal" if bool(cable.orthogonal) else "free"
                idx = self.context_cable_route.findData(mode)
                self.context_cable_route.setCurrentIndex(max(0, idx))
                del blocker
            finally:
                self._context_toolbar_loading = False
            self.context_cable_category_action.setVisible(True)
            self.context_cable_route_action.setVisible(True)
            self.act_ctx_cable_panel.setVisible(True)
            self.act_ctx_delete.setVisible(True)
            self.act_ctx_zoom_selection.setVisible(True); self.act_ctx_trace_group.setVisible(bool(str(getattr(cable,"circuit_id","") or "").strip()))
        elif symbol is not None:
            ident = " · ".join(
                x for x in (str(symbol.group or "").strip(), str(symbol.label or "").strip()) if x
            )
            self.context_caption.setText(
                core.symbol_display_name(symbol.symbol) + (f" · {ident}" if ident else "")
            )
            self.act_ctx_rotate.setVisible(True)
            role = core.association_role(symbol.symbol)
            self.act_ctx_associate.setVisible(role in ("switch", "light"))
            self.act_ctx_pl.setVisible(symbol.symbol == "light_connection")
            self.act_ctx_bom.setVisible(core.bom_supported_symbol(symbol.symbol))
            self.act_ctx_delete.setVisible(True)
            unlocked=not bool(getattr(symbol,"locked",False))
            self.act_ctx_delete.setEnabled(unlocked)
            self.act_ctx_delete.setToolTip(
                "Lås symbolet op i Egenskaber før det slettes."
                if not unlocked else "Slet det valgte symbol. Handlingen kan fortrydes."
            )
            self.act_ctx_zoom_selection.setVisible(True); self.act_ctx_trace_group.setVisible(bool(self._selected_focus_group()))
        elif total > 1:
            light_items=[item for item in symbols if core.light_can_share_switch_group(item.placement)]
            same_switch_ready=bool(not cables and len(symbols)>=2 and len(light_items)==len(symbols))
            self.context_caption.setText(f"{len(symbols)} lampesteder valgt" if same_switch_ready else f"{total} objekter valgt")
            self.act_ctx_same_switch.setVisible(same_switch_ready)
            self.act_ctx_delete.setEnabled(True); self.act_ctx_delete.setToolTip("Slet alle ulåste valgte objekter.")
            self.act_ctx_delete.setVisible(True); self.act_ctx_zoom_selection.setVisible(True)
        elif self._cable_tool_is_open():
            cid = self.cable_id_edit.text().strip() if hasattr(self, "cable_id_edit") else ""
            self.context_caption.setText("Tegner kabel" + (f" · {cid}" if cid else ""))
            self.act_ctx_lighting_snap.setVisible(True)
        else:
            self.context_caption.setText("Tegn")
            for action in self.ctx_general_actions:
                action.setVisible(True)
        if hasattr(self, "_refresh_focus_actions"):
            self._refresh_focus_actions()

    def _context_cable_category_changed(self, *_args) -> None:
        if getattr(self, "_context_toolbar_loading", False):
            return
        cable = self._context_selected_cable()
        if cable is None:
            return
        cid = core.normalize_cable_category_id(
            self.context_cable_category.currentData() or core.DEFAULT_CABLE_CATEGORY
        )
        if cid == core.normalize_cable_category_id(
            getattr(cable, "cable_category", core.DEFAULT_CABLE_CATEGORY)
        ):
            return
        before = CableItem.state(cable)
        after = dict(before)
        rec = self._cable_category_record(cid)
        after.update({"cable_category": rec["id"], "color": rec["color"], "line_style": rec["line_style"]})
        self.undo_stack.push(EditCableCommand(self, cable, before, after, "Skift kabelkategori"))
        self._refresh_context_toolbar()

    def _context_cable_route_changed(self, *_args) -> None:
        if getattr(self, "_context_toolbar_loading", False):
            return
        cable = self._context_selected_cable()
        if cable is None:
            return
        new_orthogonal = str(self.context_cable_route.currentData() or "free") == "orthogonal"
        old_orthogonal = bool(cable.orthogonal)
        if new_orthogonal == old_orthogonal:
            return
        before = CableItem.state(cable)
        after = dict(before)
        points, connections = core.convert_cable_route_mode_geometry(
            before.get("points", []),
            before.get("symbol_connections", []),
            from_orthogonal=old_orthogonal,
            to_orthogonal=new_orthogonal,
        )
        after.update(
            {
                "orthogonal": new_orthogonal,
                "points": points,
                "symbol_connections": connections,
                "route_section_modes": [],
            }
        )
        self.undo_stack.push(EditCableCommand(self, cable, before, after, "Skift kabelruteføring"))
        self._refresh_context_toolbar()

    def _create_inspector_dock(self) -> None:
        self.inspector_dock = prepare_dock(
            QDockWidget("Egenskaber", self),
            minimum_width=UI.inspector_min,
            object_name="inspectorDock",
        )
        shell = QWidget()
        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        header, self.inspector_eyebrow, self.inspector_title, self.inspector_hint = make_inspector_header(shell)
        shell_layout.addWidget(header)
        self.inspector_summary = InspectorSummaryCard(shell)
        shell_layout.addWidget(self.inspector_summary)
        self.inspector_stack = QStackedWidget(shell)
        shell_layout.addWidget(self.inspector_stack, 1)
        self.inspector_dock.setWidget(shell)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.inspector_dock)
        self.act_properties.toggled.connect(self.inspector_dock.setVisible)
        self.inspector_dock.visibilityChanged.connect(self._inspector_visibility_changed)
        # Temporary compatibility alias for old feature helpers.
        self.properties_dock = self.inspector_dock

    def _inspector_visibility_changed(self, visible: bool) -> None:
        if hasattr(self, "act_properties"):
            blocker = QSignalBlocker(self.act_properties)
            self.act_properties.setChecked(bool(visible))
            del blocker
        if not visible and self._cable_tool_is_open():
            self._cable_mode_enabled = False
            if getattr(self.view, "_cable_active", False):
                self.view.cancel_tool(emit_signal=False)
            if hasattr(self, "act_cable"):
                blocker = QSignalBlocker(self.act_cable)
                self.act_cable.setChecked(False)
                del blocker
            if hasattr(self, "cable_assistant_popup"):
                self.cable_assistant_popup.hide()

    def _show_inspector_page(
        self,
        page: str,
        *,
        title: str | None = None,
        hint: str | None = None,
        reveal: bool = True,
    ) -> None:
        page = "cable" if page == "cable" else "properties"
        widget = getattr(self, "cable_page", None) if page == "cable" else getattr(self, "properties_page", None)
        if widget is not None and hasattr(self, "inspector_stack"):
            self.inspector_stack.setCurrentWidget(widget)
        if hasattr(self, "inspector_eyebrow"):
            self.inspector_eyebrow.setText("KABEL" if page == "cable" else "EGENSKABER")
            if title is not None:
                self.inspector_title.setText(str(title))
            elif page == "cable":
                self.inspector_title.setText("Kabelværktøj")
            else:
                self.inspector_title.setText("Symbol / objekt")
            if hint is not None:
                self.inspector_hint.setText(str(hint))
            elif page == "cable":
                self.inspector_hint.setText("Tegn nyt kabel eller redigér det valgte kabel.")
            else:
                self.inspector_hint.setText("Valget på tegningen styrer indholdet her.")
        if reveal and hasattr(self, "inspector_dock"):
            self.inspector_dock.show()
            self.inspector_dock.raise_()

    def _cable_tool_is_open(self) -> bool:
        return bool(getattr(self, "_cable_mode_enabled", False))

    def _restore_main_window_layout(self) -> bool:
        data = core.load_app_settings()
        restored = False
        geometry = str(data.get("qt_window_geometry", "") or "")
        state = str(data.get("qt_window_state", "") or "")
        try:
            if geometry:
                restored = bool(
                    self.restoreGeometry(QByteArray.fromBase64(geometry.encode("ascii")))
                ) or restored
            if state:
                restored = bool(
                    self.restoreState(QByteArray.fromBase64(state.encode("ascii")), 1)
                ) or restored
        except Exception:
            restored = False
        return restored

    def _save_main_window_layout(self) -> None:
        try:
            data = core.load_app_settings()
            data["qt_window_geometry"] = bytes(self.saveGeometry().toBase64()).decode("ascii")
            data["qt_window_state"] = bytes(self.saveState(1).toBase64()).decode("ascii")
            core.save_app_settings(data)
            self.app_settings = data
        except Exception:
            pass

    def reset_main_window_layout(self) -> None:
        for dock in (
            getattr(self, "palette_dock", None),
            getattr(self, "layers_dock", None),
            getattr(self, "inspector_dock", None),
        ):
            if dock is not None:
                dock.show()
        if hasattr(self, "palette_dock") and hasattr(self, "layers_dock"):
            self.tabifyDockWidget(self.palette_dock, self.layers_dock)
            self.palette_dock.raise_()
        if hasattr(self, "inspector_dock"):
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.inspector_dock)
            self._show_inspector_page("properties", reveal=True)
            self.resizeDocks(
                [self.palette_dock, self.inspector_dock],
                [UI.left_dock_default, UI.inspector_default],
                Qt.Orientation.Horizontal,
            )
        (self._notify("Panel-layout nulstillet.", kind="info") if hasattr(self,"_notify") else self._set_status("Panel-layout nulstillet."))
