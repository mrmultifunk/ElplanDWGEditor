from __future__ import annotations

"""Opt-in graphical workflow for assigning *extra* cable markings.

The workflow deliberately never changes circuit/group, cable IDs or cable types.
Suggestions may be generated from rooms/endpoints, but they are only copied to
``CablePlacement.label`` after an explicit Apply action from the user.
"""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QCursor, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import core_logic as core
from qt_commands import EditCableCommand
from qt_graphics import CableItem
from qt_widgets import _set_role


def _compact_suggestion_caption(caption: str) -> str:
    """Keep visual suggestion buttons readable in a narrow inspector."""
    text = str(caption or "").strip()
    head, sep, value = text.partition(" · ")
    if not sep:
        return text[:30] + ("…" if len(text) > 30 else "")
    value = value.strip()
    if len(value) > 28:
        value = value[:27].rstrip() + "…"
    return f"{head}\n{value}" if value else head



class CableMarkingPopup(QFrame):
    """Small non-modal marking card anchored to the drawing viewport."""

    def __init__(self, window):
        super().__init__(window.view.viewport())
        self.window = window
        self.cable = None
        self.setObjectName("cableMarkingPopup")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(360)
        self.setMaximumWidth(460)
        self.hide()

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        top = QHBoxLayout()
        self.title = QLabel("Kabel")
        self.title.setStyleSheet("font-weight:700; font-size:14px;")
        top.addWidget(self.title, 1)
        self.close_btn = _set_role(QPushButton("×"), "iconButton")
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setToolTip("Luk mærkningskortet. Mærkningstilstanden forbliver aktiv.")
        self.close_btn.clicked.connect(self.hide)
        top.addWidget(self.close_btn)
        root.addLayout(top)

        self.context = QLabel("")
        self.context.setObjectName("subtleText")
        self.context.setWordWrap(True)
        root.addWidget(self.context)

        suggest_title = QLabel("FORSLAG · klik udfylder kun feltet")
        suggest_title.setObjectName("sectionHint")
        root.addWidget(suggest_title)
        self.suggestion_host = QWidget()
        self.suggestion_layout = QGridLayout(self.suggestion_host)
        self.suggestion_layout.setContentsMargins(0, 0, 0, 0)
        self.suggestion_layout.setSpacing(6)
        root.addWidget(self.suggestion_host)

        mark_title = QLabel("EKSTRA KABELMÆRKNING")
        mark_title.setObjectName("sectionHint")
        root.addWidget(mark_title)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Skriv mærkning…")
        self.edit.setClearButtonEnabled(True)
        self.edit.returnPressed.connect(self._apply)
        root.addWidget(self.edit)

        self.next_after_apply = QCheckBox("Gå til næste umærkede kabel efter Anvend")
        self.next_after_apply.setChecked(True)
        root.addWidget(self.next_after_apply)

        actions = QHBoxLayout()
        self.skip_btn = _set_role(QPushButton("Spring over"), "quietButton")
        self.skip_btn.clicked.connect(self._skip)
        actions.addWidget(self.skip_btn)
        self.clear_btn = _set_role(QPushButton("Ryd felt"), "quietButton")
        self.clear_btn.setToolTip("Rydder kun tekstfeltet. Kablet ændres først, når du klikker Anvend.")
        self.clear_btn.clicked.connect(self.edit.clear)
        actions.addWidget(self.clear_btn)
        actions.addStretch(1)
        self.apply_btn = QPushButton("Anvend")
        self.apply_btn.setDefault(True)
        self.apply_btn.clicked.connect(self._apply)
        actions.addWidget(self.apply_btn)
        root.addLayout(actions)

        warning = QLabel("Kun Ekstra mærkning ændres · kabel-ID og gruppe/kreds er låst i denne arbejdsgang")
        warning.setObjectName("subtleText")
        warning.setWordWrap(True)
        root.addWidget(warning)

    def _clear_suggestions(self):
        while self.suggestion_layout.count():
            item = self.suggestion_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def set_cable(self, cable) -> None:
        self.cable = cable
        if cable is None:
            self.hide()
            return
        cid = str(getattr(cable, "cable_id", "") or "Kabel")
        circuit = str(getattr(cable, "circuit_id", "") or "").strip() or "Uden gruppe"
        route = self.window._cable_marking_endpoint_text(cable)
        self.title.setText(f"{cid}  ·  {circuit}")
        self.context.setText(route or "Frit kabel")
        self.edit.setText(str(getattr(cable, "label", "") or ""))
        self.edit.selectAll()

        self._clear_suggestions()
        suggestions = self.window._cable_marking_suggestions(cable)
        if not suggestions:
            placeholder = QLabel("Ingen automatiske forslag · skriv frit")
            placeholder.setObjectName("subtleText")
            self.suggestion_layout.addWidget(placeholder, 0, 0, 1, 2)
        else:
            for index, (caption, value) in enumerate(suggestions[:4]):
                btn = _set_role(QPushButton(_compact_suggestion_caption(caption)), "quietButton")
                btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                btn.setMinimumWidth(0)
                btn.setToolTip(f"{caption}\nUdfyld feltet med: {value}\nIntet gemmes før Anvend.")
                btn.clicked.connect(lambda _checked=False, text=value: self._use_suggestion(text))
                self.suggestion_layout.addWidget(btn, index // 2, index % 2)
        self.adjustSize()

    def _use_suggestion(self, text: str) -> None:
        self.edit.setText(str(text or ""))
        self.edit.setFocus()
        self.edit.selectAll()

    def show_near_cursor(self) -> None:
        self.adjustSize()
        viewport = self.window.view.viewport()
        pos = viewport.mapFromGlobal(QCursor.pos()) + QPoint(14, 14)
        max_x = max(6, viewport.width() - self.width() - 6)
        max_y = max(6, viewport.height() - self.height() - 6)
        pos.setX(max(6, min(pos.x(), max_x)))
        pos.setY(max(6, min(pos.y(), max_y)))
        self.move(pos)
        self.show()
        self.raise_()
        self.edit.setFocus()

    def show_at_viewport_center(self) -> None:
        self.adjustSize()
        viewport = self.window.view.viewport()
        x = max(6, (viewport.width() - self.width()) // 2)
        y = max(6, min(viewport.height() - self.height() - 6, viewport.height() // 2 - self.height() // 2))
        self.move(x, y)
        self.show(); self.raise_(); self.edit.setFocus()

    def _apply(self) -> None:
        cable = self.cable
        if cable is None:
            return
        self.window._apply_graphical_cable_marking(cable, self.edit.text())
        if self.next_after_apply.isChecked():
            self.window._advance_cable_marking(cable)
        else:
            self.set_cable(cable)

    def _skip(self) -> None:
        if self.cable is not None:
            self.window._advance_cable_marking(self.cable)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.window.act_cable_marking.setChecked(False)
            event.accept()
            return
        super().keyPressEvent(event)


class CableMarkingMixin:
    """Main-window integration for graphical opt-in cable marking."""

    def _create_selected_cable_marking_panel(self) -> QWidget:
        """Build the direct marking editor shown whenever an existing cable is selected.

        This is intentionally separate from the full cable-data Apply action: the
        button below can only write ``CablePlacement.label`` (Ekstra mærkning).
        Suggestions merely fill the editor until the user explicitly applies one.
        """
        panel = QGroupBox("Mærkning")
        self.cable_selected_marking_panel = panel
        panel.setObjectName("selectedCableMarkingPanel")
        panel.setVisible(False)
        root = QVBoxLayout(panel)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(7)

        self.selected_cable_marking_context = QLabel("Vælg et kabel")
        self.selected_cable_marking_context.setObjectName("sectionHint")
        self.selected_cable_marking_context.setWordWrap(True)
        root.addWidget(self.selected_cable_marking_context)

        self.selected_cable_marking_edit = QLineEdit()
        self.selected_cable_marking_edit.setPlaceholderText("Ekstra mærkning…")
        self.selected_cable_marking_edit.setClearButtonEnabled(True)
        self.selected_cable_marking_edit.setToolTip(
            "Kun Ekstra mærkning redigeres her. Kabel-ID og gruppe/kreds ændres ikke."
        )
        self.selected_cable_marking_edit.returnPressed.connect(
            self._apply_selected_cable_marking_from_inspector
        )
        root.addWidget(self.selected_cable_marking_edit)

        suggestion_title = QLabel("FORSLAG · klik udfylder kun feltet")
        suggestion_title.setObjectName("sectionHint")
        root.addWidget(suggestion_title)
        self.selected_cable_marking_suggestion_host = QWidget()
        self.selected_cable_marking_suggestion_layout = QGridLayout(
            self.selected_cable_marking_suggestion_host
        )
        self.selected_cable_marking_suggestion_layout.setContentsMargins(0, 0, 0, 0)
        self.selected_cable_marking_suggestion_layout.setSpacing(6)
        root.addWidget(self.selected_cable_marking_suggestion_host)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        self.selected_cable_marking_open = _set_role(
            QPushButton("Grafisk mærkning…"), "quietButton"
        )
        self.selected_cable_marking_open.setToolTip(
            "Åbn den grafiske Mærk kabler-arbejdsgang for dette kabel."
        )
        self.selected_cable_marking_open.clicked.connect(
            self._open_selected_cable_marking_workflow
        )
        actions.addWidget(self.selected_cable_marking_open)
        actions.addStretch(1)
        self.selected_cable_marking_apply = QPushButton("Anvend mærkning")
        self.selected_cable_marking_apply.setObjectName("primaryButton")
        self.selected_cable_marking_apply.setToolTip(
            "Gem kun Ekstra mærkning på det valgte kabel."
        )
        self.selected_cable_marking_apply.clicked.connect(
            self._apply_selected_cable_marking_from_inspector
        )
        actions.addWidget(self.selected_cable_marking_apply)
        root.addLayout(actions)

        guard = QLabel("Kun Ekstra mærkning · kabel-ID og gruppe/kreds forbliver uændret")
        guard.setObjectName("subtleText")
        guard.setWordWrap(True)
        root.addWidget(guard)
        return panel

    def _sync_selected_cable_marking_editor(self, cable) -> None:
        """Switch between new-cable default marking and direct selected-cable marking."""
        legacy = getattr(self, "cable_label_edit", None)
        if legacy is not None:
            legacy.hide()  # Extra mærkning er aldrig en skjult standard for nye kabler.
        self._refresh_selected_cable_marking_panel(cable)

    def _clear_selected_cable_marking_suggestions(self) -> None:
        layout = getattr(self, "selected_cable_marking_suggestion_layout", None)
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _refresh_selected_cable_marking_panel(self, cable) -> None:
        panel = getattr(self, "cable_selected_marking_panel", None)
        edit = getattr(self, "selected_cable_marking_edit", None)
        if panel is None or edit is None:
            return
        self._clear_selected_cable_marking_suggestions()
        if cable is None:
            panel.setVisible(False)
            edit.clear()
            return

        panel.setVisible(True)
        cid = str(getattr(cable, "cable_id", "") or "Kabel")
        circuit = str(getattr(cable, "circuit_id", "") or "").strip() or "Uden gruppe"
        route = self._cable_marking_endpoint_text(cable)
        context = getattr(self, "selected_cable_marking_context", None)
        if context is not None:
            context.setText(f"{cid} · {circuit} · {route}")
        edit.blockSignals(True)
        edit.setText(str(getattr(cable, "label", "") or ""))
        edit.blockSignals(False)

        layout = self.selected_cable_marking_suggestion_layout
        suggestions = self._cable_marking_suggestions(cable)
        if suggestions:
            for index, (caption, value) in enumerate(suggestions[:4]):
                btn = _set_role(QPushButton(_compact_suggestion_caption(caption)), "quietButton")
                btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                btn.setMinimumWidth(0)
                btn.setToolTip(f"{caption}\nUdfyld feltet med: {value}\nIntet gemmes før Anvend mærkning.")
                btn.clicked.connect(
                    lambda _checked=False, text=value: self._fill_selected_cable_marking(text)
                )
                layout.addWidget(btn, index // 2, index % 2)
        else:
            placeholder = QLabel("Ingen forslag · skriv frit")
            placeholder.setObjectName("subtleText")
            layout.addWidget(placeholder, 0, 0, 1, 2)

    def _fill_selected_cable_marking(self, text: str) -> None:
        edit = getattr(self, "selected_cable_marking_edit", None)
        if edit is None:
            return
        edit.setText(str(text or ""))
        edit.setFocus()
        edit.selectAll()

    def _apply_selected_cable_marking_from_inspector(self) -> None:
        cable = getattr(self, "selected_cable", None)
        edit = getattr(self, "selected_cable_marking_edit", None)
        if cable is None or edit is None:
            return
        # Explicit user action; the shared helper only writes CablePlacement.label.
        self._apply_graphical_cable_marking(cable, edit.text())

    def _open_selected_cable_marking_workflow(self) -> None:
        cable = getattr(self, "selected_cable", None)
        if cable is None:
            return
        self.start_cable_marking(str(getattr(cable, "uid", "") or ""), show_editor=True)

    def _create_cable_marking_actions(self) -> None:
        self._cable_marking_active = False
        self._cable_marking_popup = None
        from PySide6.QtGui import QAction
        self.act_cable_marking = QAction("Mærk kabler", self, checkable=True)
        self.act_cable_marking.setShortcut(QKeySequence("Ctrl+Alt+M"))
        self.act_cable_marking.setToolTip(
            "Grafisk kabelmærkning på plantegningen. Programmet foreslår, men ændrer intet før du klikker Anvend."
        )
        self.act_cable_marking.toggled.connect(self._cable_marking_toggled)

    def _cable_marking_project_changed(self) -> None:
        self._cable_marking_active = False
        popup = getattr(self, "_cable_marking_popup", None)
        if popup is not None:
            popup.hide(); popup.cable = None
        action = getattr(self, "act_cable_marking", None)
        if action is not None:
            action.blockSignals(True); action.setChecked(False); action.blockSignals(False)

    def _ensure_cable_marking_popup(self) -> CableMarkingPopup:
        popup = getattr(self, "_cable_marking_popup", None)
        if popup is None:
            popup = CableMarkingPopup(self)
            self._cable_marking_popup = popup
        return popup

    def _sync_cable_marking_items(self) -> None:
        active = bool(getattr(self, "_cable_marking_active", False))
        for item in getattr(self, "cable_items", {}).values():
            if hasattr(item, "set_marking_mode"):
                item.set_marking_mode(active)

    def _stop_cable_marking_for_other_tool(self) -> None:
        action=getattr(self,"act_cable_marking",None)
        if bool(getattr(self,"_cable_marking_active",False)) and action is not None and action.isChecked():
            action.setChecked(False)

    def _cable_marking_toggled(self, checked: bool) -> None:
        if checked and self.doc is None:
            self.act_cable_marking.blockSignals(True); self.act_cable_marking.setChecked(False); self.act_cable_marking.blockSignals(False)
            return
        self._cable_marking_active = bool(checked)
        if checked:
            # This is a selection/edit workflow, not a drawing tool. Close tools that
            # can legitimately own the next cable click.
            self._pending_cable_attach_symbol_uid = ""
            self.view.cancel_tool(emit_signal=False)
            if self._cable_tool_is_open():
                self.close_cable_tool()
            self._clear_hover_info()
            self.view.unsetCursor()
            self._sync_cable_marking_items()
            self._set_status("Kabelmærkning aktiv · klik et kabel · vælg forslag eller skriv frit · Anvend gemmer · Esc afslutter")
        else:
            popup = getattr(self, "_cable_marking_popup", None)
            if popup is not None:
                popup.hide(); popup.cable = None
            self._sync_cable_marking_items()
            self._set_status("Kabelmærkning afsluttet.")
        if hasattr(self, "_refresh_workflow_bar"):
            self._refresh_workflow_bar()

    def start_cable_marking(self, cable_uid: str = "", *, show_editor: bool = False) -> None:
        if not getattr(self, "act_cable_marking", None):
            return
        if not self.act_cable_marking.isChecked():
            self.act_cable_marking.setChecked(True)
        if cable_uid:
            cable = self._cable_by_uid(cable_uid)
            if cable is not None:
                self._focus_cable_for_marking(cable, open_editor=show_editor)

    def _handle_cable_item_click(self, item: CableItem, scene_pos) -> bool:
        # Existing attach-to-cable mode has explicit ownership of the next cable
        # click and therefore takes priority if a future caller enables both.
        if str(getattr(self, "_pending_cable_attach_symbol_uid", "") or ""):
            return super()._handle_cable_item_click(item, scene_pos)
        if bool(getattr(self, "_cable_marking_active", False)):
            self._focus_cable_for_marking(item.cable, open_editor=True, zoom=False)
            return True
        return super()._handle_cable_item_click(item, scene_pos)

    def _cable_marking_endpoint_text(self, cable) -> str:
        rows = sorted(core.cable_symbol_connections(cable), key=lambda r: int(r.get("point_index", 0) or 0))
        captions = []
        for row in rows:
            uid = str(row.get("symbol_uid", "") or "")
            caption = self._cable_symbol_caption(uid) if uid else "Fri ende"
            if caption and caption not in captions:
                captions.append(caption)
        if len(captions) >= 2:
            return f"{captions[0]} → {captions[-1]}"
        if len(captions) == 1:
            return f"{captions[0]} → Fri ende"
        return "Fri ende → Fri ende"

    def _cable_marking_suggestions(self, cable) -> list[tuple[str, str]]:
        values: list[tuple[str, str]] = []
        rooms = list(getattr(self.project, "rooms", []) or [])
        room_hits = core.cable_rooms(cable, rooms) if rooms else []
        room_uids = {str(getattr(room, "uid", "") or id(room)) for room in room_hits}
        room_count = len(room_uids)
        # Mere end ét forskelligt fysisk gennemløbet rum er et stærkt signal og
        # får derfor førsteprioritet. Ved 0-1 rum kan et kabel mellem to
        # lampesteder ofte navngives mere intuitivt ud fra lampeudtagenes mærkning.
        room_name = core.cable_room_marking(cable, rooms, "name") if room_hits else ""
        room_code = core.cable_room_marking(cable, rooms, "code") if room_hits else ""
        light_marking = core.cable_light_endpoint_marking(
            cable, list(getattr(self.project, "placements", []) or [])
        )
        endpoints = self._cable_marking_endpoint_text(cable)

        if light_marking and room_count <= 1:
            values.append((f"Lampeudtag · {light_marking}", light_marking))
        if room_name:
            values.append((f"Rum · {room_name}", room_name))
        if room_code and room_code != room_name:
            values.append((f"Rum-ID · {room_code}", room_code))
        if light_marking and room_count > 1:
            values.append((f"Lampeudtag · {light_marking}", light_marking))
        if endpoints and "Fri ende → Fri ende" not in endpoints:
            values.append((f"Fra/til · {endpoints}", endpoints))
        if room_name and endpoints:
            first = endpoints.split(" → ", 1)[0].strip()
            combined = f"{first} → {room_name}" if first and first not in room_name else room_name
            if combined not in {value for _caption, value in values}:
                values.append((f"Kontekst · {combined}", combined))
        out=[]; seen=set()
        for caption, value in values:
            value=str(value or "").strip()
            if not value or value in seen: continue
            seen.add(value); out.append((caption,value))
        return out

    def _focus_cable_for_marking(self, cable, *, open_editor: bool, zoom: bool = True) -> None:
        item = self.cable_items.get(id(cable))
        if item is not None:
            self.scene.clearSelection(); item.setSelected(True)
            if zoom:
                try:
                    rect=item.sceneBoundingRect().adjusted(-140,-140,140,140)
                    self.view.animate_to_scene_rect(rect)
                except Exception:
                    pass
        if open_editor:
            popup=self._ensure_cable_marking_popup(); popup.set_cable(cable)
            popup.show_near_cursor() if QCursor.pos() else popup.show_at_viewport_center()

    def _apply_graphical_cable_marking(self, cable, text: str) -> None:
        new = str(text or "").strip()
        old = str(getattr(cable, "label", "") or "").strip()
        if new == old:
            self._set_status(f"{getattr(cable,'cable_id','Kabel')}: mærkning uændret")
            return
        self.undo_stack.push(EditCableCommand(self, cable, {"label": old}, {"label": new}, "Mærk kabel"))
        item = self.cable_items.get(id(cable))
        if item is not None and hasattr(item, "set_marking_mode"):
            item.set_marking_mode(True)
        verb = f"mærket '{new}'" if new else "mærkning ryddet"
        message=f"{getattr(cable,'cable_id','Kabel')} {verb} · gruppe/kreds er uændret"
        if hasattr(self,"_notify"): self._notify(message,kind="success")
        else:self._set_status(message)
        self._refresh_cable_routes_dialog()

    def _advance_cable_marking(self, current) -> None:
        cables=list(self.project.cables or [])
        if not cables:return
        circuit=str(getattr(current,"circuit_id","") or "")
        try:start=cables.index(current)
        except ValueError:start=-1
        ordered=cables[start+1:]+cables[:start+1]
        same=[c for c in ordered if str(getattr(c,"circuit_id","") or "")==circuit and not str(getattr(c,"label","") or "").strip()]
        other=[c for c in ordered if not str(getattr(c,"label","") or "").strip()]
        target=(same or other)
        popup=self._ensure_cable_marking_popup()
        if not target:
            popup.hide()
            self._set_status("Alle kabler har en ekstra mærkning · mærkningstilstanden er stadig aktiv")
            return
        cable=target[0]
        self._focus_cable_for_marking(cable,open_editor=False,zoom=True)
        popup.set_cable(cable); popup.show_at_viewport_center()

    def _cable_marking_rows(self) -> list[dict]:
        rows=[]
        for cable in self.project.cables:
            label=str(getattr(cable,"label","") or "").strip()
            suggestions=self._cable_marking_suggestions(cable)
            rows.append({
                "uid":str(getattr(cable,"uid","") or ""),
                "cable_id":str(getattr(cable,"cable_id","") or "Kabel"),
                "circuit_id":str(getattr(cable,"circuit_id","") or "") or "Uden gruppe/kreds",
                "route":self._cable_marking_endpoint_text(cable),
                "marking":label,
                "suggestion":suggestions[0][1] if suggestions else "",
                "marked":bool(label),
            })
        return rows

    def _cable_marking_from_routes(self, cable_uid: str) -> None:
        uid=str(cable_uid or "")
        self.start_cable_marking()
        cable=self._cable_by_uid(uid) if uid else None
        if cable is None:return
        self.raise_(); self.activateWindow(); self._focus_cable_for_marking(cable,open_editor=False,zoom=True)
        popup=self._ensure_cable_marking_popup(); popup.set_cable(cable); popup.show_at_viewport_center()
