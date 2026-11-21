from __future__ import annotations

"""Project quality/control dashboard and plan navigation helpers."""

from collections import Counter

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

import core_logic as core
from elplan_catalog import user_library
from elplan_qt.qt_graphics import CableItem, ElectricalSymbolItem
from elplan_qt.qt_ui import configure_modern_dialog


def _placement_caption(placement) -> str:
    ident=" · ".join(x for x in (
        str(getattr(placement,"group","") or "").strip(),
        str(getattr(placement,"label","") or "").strip(),
    ) if x)
    return ident or core.symbol_display_name(str(getattr(placement,"symbol","") or ""))


def collect_project_control_issues(window) -> list[dict]:
    return core.project_control_issues(
        window.project.placements,window.project.cables,window.project.rooms,
        window.project.raw,getattr(window,"global_bom_assemblies",[]) or [])


class ProjectControlDialog(QDialog):
    def __init__(self,window):
        super().__init__(window); self.window=window; self._issues=[]
        configure_modern_dialog(self,title="Projektkontrol",size=(980,650))
        root=QVBoxLayout(self); root.setContentsMargins(18,16,18,16); root.setSpacing(10)
        title=QLabel("Hvad mangler i projektet?"); title.setStyleSheet("font-weight:700; font-size:16px;"); root.addWidget(title)
        hint=QLabel("Kontrollen ændrer ikke projektet. Dobbeltklik på en linje for at gå direkte til objektet på plantegningen.")
        hint.setWordWrap(True); hint.setObjectName("mutedText"); root.addWidget(hint)
        row=QHBoxLayout(); self.summary=QLabel(); self.summary.setObjectName("accentText"); row.addWidget(self.summary,1)
        row.addWidget(QLabel("Vis")); self.filter=QComboBox(); self.filter.addItem("Alle","all"); self.filter.addItem("Fejl","error"); self.filter.addItem("Advarsler","warning"); self.filter.addItem("Kontrolpunkter","info"); self.filter.currentIndexChanged.connect(self._render); row.addWidget(self.filter)
        refresh=QPushButton("Opdater"); refresh.clicked.connect(self.refresh); row.addWidget(refresh); root.addLayout(row)
        self.table=QTableWidget(0,4); self.table.setHorizontalHeaderLabels(["Status","Område","Objekt / problem","Detalje"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection); self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False); self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0,100); self.table.setColumnWidth(1,120); self.table.setColumnWidth(2,300)
        self.table.itemDoubleClicked.connect(lambda _item:self._go_to()); root.addWidget(self.table,1)
        actions=QHBoxLayout(); go=QPushButton("Gå til valgt"); go.clicked.connect(self._go_to); actions.addWidget(go); actions.addStretch(1); root.addLayout(actions)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close); buttons.rejected.connect(self.reject); buttons.accepted.connect(self.accept); root.addWidget(buttons)
        self.refresh()

    def refresh(self):
        self._issues=collect_project_control_issues(self.window); self._render()

    def _render(self,*_):
        current=str(self.filter.currentData() or "all")
        rows=[x for x in self._issues if current=="all" or x["severity"]==current]
        self.table.setRowCount(len(rows)); self._visible=rows
        labels={"error":"Fejl","warning":"Advarsel","info":"Kontrol"}
        colors={"error":"#ef4444","warning":"#f59e0b","info":"#38bdf8"}
        for r,issue in enumerate(rows):
            values=[labels.get(issue["severity"],issue["severity"]),issue["category"],issue["title"],issue["detail"]]
            for c,value in enumerate(values):
                item=QTableWidgetItem(str(value)); item.setData(Qt.ItemDataRole.UserRole,r)
                if c==0:item.setForeground(QColor(colors.get(issue["severity"],"#94a3b8")))
                self.table.setItem(r,c,item)
        counts=Counter(x["severity"] for x in self._issues)
        if not self._issues:self.summary.setText("✓ Ingen kendte kontrolpunkter")
        else:self.summary.setText(f"{counts['error']} fejl · {counts['warning']} advarsler · {counts['info']} kontrolpunkter")

    def _go_to(self):
        row=self.table.currentRow()
        if row<0 or row>=len(getattr(self,"_visible",[])):return
        self.window.navigate_project_issue(self._visible[row])
        self.raise_(); self.activateWindow()


class ProjectControlMixin:
    def open_project_control(self):
        ProjectControlDialog(self).exec()

    def _select_scene_objects(self,placement_uids=None,cable_uids=None,zoom=True):
        placement_uids={str(x) for x in (placement_uids or []) if str(x)}; cable_uids={str(x) for x in (cable_uids or []) if str(x)}
        self.scene.blockSignals(True)
        try:
            self.scene.clearSelection()
            for uid in placement_uids:
                item=self.symbol_items.get(uid)
                if item is not None:item.setSelected(True)
            for cable in self.project.cables:
                if str(getattr(cable,"uid","") or "") in cable_uids:
                    item=self.cable_items.get(id(cable))
                    if item is not None:item.setSelected(True)
        finally:self.scene.blockSignals(False)
        self._selection_changed()
        if zoom and (placement_uids or cable_uids):self.zoom_to_selection()

    def navigate_project_issue(self,issue):
        kind=str((issue or {}).get("object_type","") or ""); uid=str((issue or {}).get("uid","") or "")
        if kind=="placement":self._select_scene_objects([uid],[],True)
        elif kind=="cable":self._select_scene_objects([], [uid],True)

    def highlight_bom_article(self,article_no,room_uid=""):
        sources=core.bom_article_source_uids(
            article_no,self.project.placements,self.project.raw.get("placement_articles",{}),
            self.project.rooms,self.project.cables,self.project.raw.get("cable_instance_articles",{}),
            getattr(self,"global_bom_assemblies",[]),self.project.raw.get("placement_assemblies",{}),
            room_filter_uid=room_uid,placement_room_additions=self.project.raw.get("placement_bom_room_additions",{}))
        self._bom_highlight_placement_uids=set(sources.get("placement_uids",[])); self._bom_highlight_cable_uids=set(sources.get("cable_uids",[]))
        self._select_scene_objects(self._bom_highlight_placement_uids,self._bom_highlight_cable_uids,True)
        if hasattr(self,"_apply_visual_emphasis"):self._apply_visual_emphasis()
        count=len(self._bom_highlight_placement_uids)+len(self._bom_highlight_cable_uids)
        if hasattr(self,"_notify"):
            self._notify(f"{article_no}: {count} forekomst(er) fremhævet på plantegningen." if count else f"Ingen synlige forekomster fundet for {article_no}.",kind="info" if count else "warning")
        return count

    def clear_bom_article_highlight(self):
        self._bom_highlight_placement_uids=set(); self._bom_highlight_cable_uids=set()
        if hasattr(self,"_apply_visual_emphasis"):self._apply_visual_emphasis()
