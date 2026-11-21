from __future__ import annotations

"""Global project search and command palette for the Qt application.

The implementation is intentionally independent from qt_app.py.  Search entries
are built from the project model and resolved back to graphics items only when a
result is activated.  This keeps Ctrl+F/Ctrl+Shift+P fast even on larger plans.
"""

from dataclasses import dataclass
from typing import Callable, Iterable

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

import core_logic as core
from elplan_qt.qt_ui import configure_modern_dialog, make_dialog_header


@dataclass(frozen=True)
class SearchEntry:
    kind: str
    key: str
    title: str
    subtitle: str = ""
    keywords: str = ""
    command: Callable[[], None] | None = None

    @property
    def haystack(self) -> str:
        return " ".join((self.kind, self.title, self.subtitle, self.keywords)).casefold()


_KIND_LABELS = {
    "command": "KOMMANDO",
    "symbol": "SYMBOL",
    "cable": "KABEL",
    "text": "TEKST",
}


class SearchDialog(QDialog):
    def __init__(self, parent, entries: Iterable[SearchEntry], *, commands: bool = True):
        super().__init__(parent)
        self._all = list(entries)
        self._visible: list[SearchEntry] = []
        self._selected: SearchEntry | None = None
        title = "Søg og gå til" if not commands else "Søg / kommando"
        subtitle = (
            "Søg efter gruppe, mærkning, kabel-ID, kabeltype eller tekst på tegningen."
            if not commands
            else "Find et objekt eller start en handling uden at lede i menuerne."
        )
        configure_modern_dialog(self, title=title, size=(760, 560), minimum_size=(560, 360))
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)
        root.addWidget(make_dialog_header(title, subtitle, eyebrow="HURTIG ADGANG"))

        self.search = QLineEdit(self)
        self.search.setClearButtonEnabled(True)
        self.search.setPlaceholderText(
            "Skriv fx G11, UDTAG-SOVE, 7G1,5, K12…" if not commands else "Skriv fx G11, PL rapport, kabel, UDTAG-SOVE…"
        )
        self.search.textChanged.connect(self._refresh)
        self.search.returnPressed.connect(self._accept_current)
        root.addWidget(self.search)

        self.list = QListWidget(self)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list.setWordWrap(True)
        self.list.itemActivated.connect(lambda *_: self._accept_current())
        self.list.itemDoubleClicked.connect(lambda *_: self._accept_current())
        root.addWidget(self.list, 1)

        footer = QHBoxLayout()
        self.count = QLabel("", self)
        self.count.setObjectName("sectionHint")
        footer.addWidget(self.count)
        footer.addStretch(1)
        cancel = QPushButton("Luk", self)
        cancel.setObjectName("quietButton")
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        root.addLayout(footer)

        self._refresh("")
        self.search.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def _score(self, entry: SearchEntry, query: str) -> tuple[int, str]:
        if not query:
            # Commands first in the palette, objects first in object search is
            # handled by the order supplied by the mixin.
            return (10, entry.title.casefold())
        words = [w for w in query.casefold().split() if w]
        title = entry.title.casefold()
        subtitle = entry.subtitle.casefold()
        hay = entry.haystack
        if not all(w in hay for w in words):
            return (999, title)
        score = 50
        for word in words:
            if title.startswith(word):
                score -= 20
            elif word in title:
                score -= 12
            elif word in subtitle:
                score -= 6
        return (score, title)

    def _refresh(self, text: str) -> None:
        query = str(text or "").strip()
        ranked = []
        for entry in self._all:
            score = self._score(entry, query)
            if score[0] < 999:
                ranked.append((score, entry))
        ranked.sort(key=lambda pair: pair[0])
        self._visible = [entry for _score, entry in ranked[:160]]
        self.list.clear()
        for entry in self._visible:
            label = _KIND_LABELS.get(entry.kind, entry.kind.upper())
            text = f"{label}   {entry.title}" + (f"\n{entry.subtitle}" if entry.subtitle else "")
            item = QListWidgetItem(text)
            if entry.subtitle:
                item.setToolTip(entry.subtitle)
            item.setData(Qt.ItemDataRole.UserRole, entry.key)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)
        self.count.setText(f"{len(self._visible)} resultater" if query else f"{len(self._all)} tilgængelige")

    def _accept_current(self) -> None:
        row = self.list.currentRow()
        if 0 <= row < len(self._visible):
            self._selected = self._visible[row]
            self.accept()

    def selected_entry(self) -> SearchEntry | None:
        return self._selected


class SearchUiMixin:
    """MainWindow mixin for search, command palette and result focus."""

    def _project_search_entries(self) -> list[SearchEntry]:
        entries: list[SearchEntry] = []
        for p in getattr(self.project, "placements", []) or []:
            group = str(getattr(p, "group", "") or "").strip()
            label = str(getattr(p, "label", "") or "").strip()
            name = core.symbol_display_name(str(getattr(p, "symbol", "") or ""))
            ident = " · ".join(x for x in (group, label) if x)
            title = f"{ident} — {name}" if ident else name
            assoc = core.association_display(p)
            subtitle = " · ".join(x for x in (name, f"Tilhør.: {assoc}" if assoc else "") if x)
            entries.append(SearchEntry("symbol", str(p.uid), title, subtitle, f"{group} {label} {assoc}"))
        placement_by_uid={str(p.uid):p for p in (getattr(self.project,"placements",[]) or [])}
        for cable in getattr(self.project, "cables", []) or []:
            cable_id = str(getattr(cable, "cable_id", "") or "").strip()
            circuit = str(getattr(cable, "circuit_id", "") or "").strip()
            extra = str(getattr(cable, "label", "") or "").strip()
            spec = str(getattr(cable, "cable_spec", "") or "").strip()
            category = core.cable_category_record(
                self.project.raw.get("cable_categories", []),
                getattr(cable, "cable_category", core.DEFAULT_CABLE_CATEGORY),
            ).get("name", "")
            endpoints=[]
            for conn in core.cable_symbol_connections(cable):
                p=placement_by_uid.get(str(conn.get("symbol_uid","") or ""))
                if p is None:continue
                ident=" · ".join(x for x in (str(getattr(p,"group","") or "").strip(),str(getattr(p,"label","") or "").strip()) if x)
                endpoints.append(ident or core.symbol_display_name(str(getattr(p,"symbol","") or "")))
            endpoint_text=" → ".join(endpoints)
            title = " · ".join(x for x in (cable_id or "Kabel", circuit, extra) if x)
            subtitle = " · ".join(x for x in (endpoint_text, spec, str(category or "")) if x)
            entries.append(SearchEntry("cable", str(cable.uid), title, subtitle, f"{cable_id} {circuit} {extra} {endpoint_text} {spec} {category}"))
        for text in getattr(self.project, "texts", []) or []:
            value = str(getattr(text, "text", "") or "").strip()
            entries.append(SearchEntry("text", str(text.uid), value[:120] or "Tom tekst", "Fritekst", value))
        return entries

    def _command_entries(self) -> list[SearchEntry]:
        rows: list[tuple[str, str, Callable[[], None], str]] = [
            ("Åbn projekt…", "Fil", self.open_project, "open projekt"),
            ("Åbn DWG/DXF…", "Fil", self.open_cad, "dwg dxf cad"),
            ("Gem projekt", "Fil", lambda: self.save_project(False), "save gem"),
            ("Gem som…", "Fil", lambda: self.save_project(True), "save as"),
            ("Startside", "Vis", self._show_welcome_page, "velkomst recent"),
            ("Tilpas visning", "Vis", self.view.fit_scene, "zoom fit"),
            ("Nulstil panel-layout", "Vis", self.reset_main_window_layout, "dock inspector panel"),
            ("Kabelværktøj", "Værktøjer", lambda: self.act_cable.setChecked(True), "kabel cable"),
            ("Kabelkategorier…", "Værktøjer", self.open_cable_categories_dialog, "kategori lag farve"),
            ("PL-dåserapport…", "Værktøjer", self.export_pl_box_report, "pl rapport montage"),
            ("Artikler / BOM…", "Værktøjer", self.open_bom_manager, "artikel stykliste bom"),
            ("Symbolkonfigurator…", "Værktøjer", self.open_symbol_configurator, "kombi symbol"),
        ]
        return [SearchEntry("command", f"cmd:{i}", title, section, keywords, callback) for i, (title, section, callback, keywords) in enumerate(rows)]

    def open_global_search(self) -> None:
        if not getattr(self, "doc", None):
            self._show_welcome_page()
            return
        dlg = SearchDialog(self, self._project_search_entries(), commands=False)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            entry = dlg.selected_entry()
            if entry is not None:
                self._activate_search_entry(entry)

    def open_command_palette(self) -> None:
        entries = self._command_entries()
        if getattr(self, "doc", None):
            entries += self._project_search_entries()
        dlg = SearchDialog(self, entries, commands=True)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            entry = dlg.selected_entry()
            if entry is not None:
                self._activate_search_entry(entry)

    def _activate_search_entry(self, entry: SearchEntry) -> None:
        if entry.kind == "command":
            if entry.command is not None:
                entry.command()
            return
        self._show_canvas_page()
        self.scene.clearSelection()
        item = None
        if entry.kind == "symbol":
            item = self.symbol_items.get(entry.key)
        elif entry.kind == "text":
            item = self.text_items.get(entry.key)
        elif entry.kind == "cable":
            cable = next((x for x in self.project.cables if str(getattr(x, "uid", "")) == entry.key), None)
            if cable is not None:
                item = self.cable_items.get(id(cable))
        if item is None:
            return
        item.setSelected(True)
        try:
            self.view.ensureVisible(item, 120, 120)
            self.view.centerOn(item)
        except Exception:
            pass
        notify = getattr(self, "_notify", None)
        message = f"Fundet: {entry.title}"
        if callable(notify):
            notify(message, kind="info", timeout=1500)
        else:
            self._set_status(message)
