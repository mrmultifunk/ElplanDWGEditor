from __future__ import annotations

"""Read-only PL-dåse PWA import and photo preview dialogs."""

from copy import deepcopy

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

import core_logic as core
import pl_daase_api
from qt_ui import configure_modern_dialog, make_dialog_header
from qt_widgets import QComboBox


def _identity(row) -> tuple[str,int,str]:
    raw=row if isinstance(row,dict) else {}
    return (str(raw.get("cable_uid","") or ""),int(raw.get("point_index",0) or 0),str(raw.get("leg","") or ""))


def _leg_caption(leg) -> str:
    raw=leg if isinstance(leg,dict) else {}
    cable=str(raw.get("cable_display") or raw.get("cable_id") or "Kabel")
    spec=str(raw.get("cable_spec","") or "").strip()
    side=str(raw.get("leg_caption","") or "").strip()
    return " · ".join(x for x in (cable,spec,side) if x)


class PLFieldImportDialog(QDialog):
    """Preview and map PWA cable entries to existing Elplan cable legs."""

    def __init__(self,parent,*,cable_legs,current_entries,current_record=None,orientation=0):
        super().__init__(parent)
        self.legs=[dict(row) for row in (cable_legs or []) if isinstance(row,dict)]
        self.current_entries=core.normalize_pl_box_entries(current_entries)
        self.current_record=core.normalize_pl_field_record(current_record)
        self.result_entries=deepcopy(self.current_entries)
        self.result_record=deepcopy(self.current_record)
        self.result_orientation=core.normalize_pl_box_orientation(orientation)
        self.boxes=[]; self.mapping_combos=[]
        configure_modern_dialog(self,title="Hent kabelindføringer fra PL-dåse",minimum_size=(940,620),size=(1120,720))
        root=QVBoxLayout(self); root.setContentsMargins(16,14,16,14); root.setSpacing(10)
        root.addWidget(make_dialog_header(
            "Feltregistrering fra PL-dåse",
            "Vælg en registreret dåse og match dens seks fysiske indføringer med de kabelben, der allerede findes ved lampestedet. Lederfordelingen ændres ikke.",
            eyebrow="READ-ONLY API",
        ))
        select_row=QHBoxLayout(); select_row.setSpacing(8)
        select_row.addWidget(QLabel("Dåse:")); self.box_combo=QComboBox(); self.box_combo.setMinimumWidth(310); self.box_combo.currentIndexChanged.connect(self._populate); select_row.addWidget(self.box_combo,1)
        self.reload_btn=QPushButton("Hent igen"); self.reload_btn.clicked.connect(self._load); select_row.addWidget(self.reload_btn)
        select_row.addWidget(QLabel("Orientering:")); self.orientation_combo=QComboBox()
        for angle,caption in core.PL_BOX_ORIENTATIONS.items():self.orientation_combo.addItem(caption,angle)
        idx=self.orientation_combo.findData(self.result_orientation); self.orientation_combo.setCurrentIndex(max(0,idx)); self.orientation_combo.setMinimumWidth(270); select_row.addWidget(self.orientation_combo)
        root.addLayout(select_row)
        self.meta=QLabel("Henter registreringer…"); self.meta.setWordWrap(True); self.meta.setObjectName("sectionHint"); root.addWidget(self.meta)
        self.table=QTableWidget(6,6); self.table.setHorizontalHeaderLabels(["Indf.","Feltfunktion","Feltkabel","Feltnote","Elplan-kabelben","Status"])
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection); self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.table.verticalHeader().setVisible(False)
        header=self.table.horizontalHeader(); header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents); header.setSectionResizeMode(4,QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0,55); root.addWidget(self.table,1)
        note=QLabel("PWA-funktionen bruges kun som dokumentation og matchhjælp. Den overføres ikke til lederfunktioner, lampeudtag eller WAGO-samlinger.")
        note.setWordWrap(True); note.setObjectName("accentText"); root.addWidget(note)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        self.ok_button=buttons.button(QDialogButtonBox.StandardButton.Ok); self.ok_button.setText("Anvend kabelindføringer"); self.ok_button.setEnabled(False)
        buttons.accepted.connect(self._accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        QTimer.singleShot(0,self._load)

    def _load(self):
        settings=core.load_app_settings(); url=str(settings.get("pl_daase_url","") or ""); token=str(settings.get("pl_daase_token","") or "")
        self.reload_btn.setEnabled(False); self.ok_button.setEnabled(False); self.meta.setText("Kontakter PL-dåse-serveren…")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result=pl_daase_api.fetch_export(url,token,timeout=15); self.boxes=list(result.get("boxes",[]))
            wanted=str(self.current_record.get("box_id","") or "")
            self.box_combo.blockSignals(True); self.box_combo.clear()
            for box in self.boxes:
                filled=sum(core.pl_field_entry_state(row)!="unregistered" for row in box.get("entries",[]))
                caption=str(box.get("name") or box.get("box_id") or "PL-dåse")
                ref=str(box.get("ref","") or "").strip()
                self.box_combo.addItem(caption+(f" · {ref}" if ref else "")+f" · {filled}/6",str(box.get("box_id","") or ""))
            index=self.box_combo.findData(wanted) if wanted else 0
            self.box_combo.setCurrentIndex(max(0,index)); self.box_combo.blockSignals(False)
            self._populate(); self.ok_button.setEnabled(bool(self.boxes))
            if not self.boxes:self.meta.setText("Serveren indeholder ingen aktive PL-dåser.")
        except (ValueError,pl_daase_api.PLDaaseApiError) as exc:
            self.boxes=[]; self.box_combo.clear(); self.meta.setObjectName("dangerText"); self.meta.setText(str(exc)); self._clear_table()
        finally:
            QApplication.restoreOverrideCursor(); self.reload_btn.setEnabled(True)
            self.meta.style().unpolish(self.meta); self.meta.style().polish(self.meta)

    def _selected_box(self):
        box_id=str(self.box_combo.currentData() or "")
        return next((row for row in self.boxes if str(row.get("box_id","") or "")==box_id),None)

    def _clear_table(self):
        self.mapping_combos=[]
        for row in range(6):
            self.table.removeCellWidget(row,4)
            for col in range(6):self.table.setItem(row,col,QTableWidgetItem(""))

    def _current_leg(self,position):
        entry=self.current_entries.get(str(position)); key=_identity(entry)
        return next((leg for leg in self.legs if _identity(leg)==key),None)

    def _populate(self):
        box=self._selected_box(); self.mapping_combos=[]
        if not box:self._clear_table(); return
        ref=str(box.get("ref","") or "").strip(); note=str(box.get("note","") or "").strip(); photos=len(box.get("photos",[]) or [])
        self.meta.setObjectName("sectionHint"); self.meta.setText(
            f"<b>{box.get('name') or box.get('box_id')}</b> · står med ansigtet mod: <b>{ref or 'ikke angivet'}</b> · {photos} foto(s)"+(f"<br>{note}" if note else "")
        )
        by_position={int(row.get("position",0)):row for row in box.get("entries",[]) if isinstance(row,dict)}
        occupied={_identity(entry) for entry in self.current_entries.values()}; suggested=set()
        for row_index,position in enumerate(range(1,7)):
            field=by_position.get(position,{"position":position}); state=core.pl_field_entry_state(field); current=self._current_leg(position)
            values=(str(position),str(field.get("function","") or "") or "—",str(field.get("cable","") or "") or "—",str(field.get("note","") or "") or "—")
            for col,value in enumerate(values):self.table.setItem(row_index,col,QTableWidgetItem(value))
            combo=QComboBox()
            combo.addItem("Behold nuværende" if current is not None else "Vælg kabelben…",{"action":"keep"})
            combo.addItem("Ledig / fjern kabel",{"action":"clear"})
            for leg in self.legs:combo.addItem(_leg_caption(leg),{"action":"leg","key":list(_identity(leg))})
            status=""
            if state=="unregistered":
                combo.setCurrentIndex(0); status="Ikke registreret · beholdes"
            elif state=="empty":
                combo.setCurrentIndex(1); status="Registreret som tom"
            elif current is not None:
                wanted={"action":"leg","key":list(_identity(current))}; idx=next((i for i in range(combo.count()) if combo.itemData(i)==wanted),0); combo.setCurrentIndex(idx); status="Eksisterende kabel"
            else:
                candidate=core.pl_field_suggested_leg(field,self.legs,occupied|suggested)
                if candidate is not None:
                    wanted={"action":"leg","key":list(_identity(candidate))}; idx=next((i for i in range(combo.count()) if combo.itemData(i)==wanted),0); combo.setCurrentIndex(idx); suggested.add(_identity(candidate)); status="Entydigt typeforslag"
                else:
                    combo.setCurrentIndex(0); status="Vælg kabelben" if str(field.get("cable","") or "").strip() else "Kontrollér manuelt"
            self.table.setCellWidget(row_index,4,combo); self.table.setItem(row_index,5,QTableWidgetItem(status)); self.mapping_combos.append((position,field,combo))
        self.table.resizeRowsToContents(); self.meta.style().unpolish(self.meta); self.meta.style().polish(self.meta)

    def _accept(self):
        box=self._selected_box()
        if not box:return
        selected=[]
        unresolved=[]
        for position,field,combo in self.mapping_combos:
            data=combo.currentData() or {}
            if data.get("action")=="leg":selected.append((position,tuple(data.get("key") or [])))
            elif data.get("action")=="keep" and self._current_leg(position) is None and core.pl_field_entry_state(field)=="cable":
                unresolved.append(position)
        if unresolved:
            numbers=", ".join(str(position) for position in unresolved)
            QMessageBox.warning(
                self,"PL-dåse",
                f"Vælg det konkrete Elplan-kabelben for indføring {numbers}. "
                "Kabeltypen gav ikke et entydigt match.",
            )
            return
        keys=[key for _position,key in selected]
        if len(keys)!=len(set(keys)):
            QMessageBox.warning(self,"PL-dåse","Det samme kabelben er valgt til mere end én indføring."); return
        entries=deepcopy(self.current_entries); leg_by_key={_identity(leg):leg for leg in self.legs}
        for position,field,combo in self.mapping_combos:
            data=combo.currentData() or {}; action=str(data.get("action","") or "")
            if action=="keep":continue
            if action=="clear":entries.pop(str(position),None); continue
            key=tuple(data.get("key") or [])
            leg=leg_by_key.get(key)
            if leg is None:continue
            for port,entry in list(entries.items()):
                if _identity(entry)==key:entries.pop(port,None)
            old=self.current_entries.get(str(position),{})
            note=str(field.get("note","") or "").strip() or str(old.get("note","") or "")
            entries[str(position)]={"cable_uid":key[0],"point_index":int(key[1]),"leg":key[2],"note":note}
        self.result_entries=core.reconcile_pl_box_entries(entries,self.legs)
        self.result_record=core.normalize_pl_field_record(box)
        self.result_orientation=core.normalize_pl_box_orientation(self.orientation_combo.currentData())
        self.accept()


class PLFieldPhotoDialog(QDialog):
    def __init__(self,parent,record):
        super().__init__(parent); self.record=core.normalize_pl_field_record(record); self.original=QPixmap()
        settings=core.load_app_settings(); self.token=str(settings.get("pl_daase_token","") or ""); self.source_url=str(self.record.get("source_url") or settings.get("pl_daase_url","") or "")
        configure_modern_dialog(self,title="PL-dåse – feltfotos",minimum_size=(720,520),size=(980,760))
        root=QVBoxLayout(self); root.setContentsMargins(14,14,14,14); root.setSpacing(9)
        head=QHBoxLayout(); head.addWidget(QLabel(f"<b>{self.record.get('name') or 'PL-dåse'}</b>")); head.addWidget(QLabel(f"Retning: {self.record.get('ref') or '—'}")); head.addStretch(1)
        self.photo_combo=QComboBox();
        for index,photo in enumerate(self.record.get("photos",[]) or [],1):self.photo_combo.addItem(f"Foto {index}/{len(self.record.get('photos',[]))}",str(photo.get("id","") or ""))
        self.photo_combo.currentIndexChanged.connect(self._load); head.addWidget(self.photo_combo); root.addLayout(head)
        self.status=QLabel(""); self.status.setWordWrap(True); root.addWidget(self.status)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); self.image=QLabel("Ingen fotos"); self.image.setAlignment(Qt.AlignmentFlag.AlignCenter); scroll.setWidget(self.image); root.addWidget(scroll,1)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close); buttons.rejected.connect(self.reject); buttons.clicked.connect(self.accept); root.addWidget(buttons)
        QTimer.singleShot(0,self._load)

    def _selected_photo(self):
        photo_id=str(self.photo_combo.currentData() or "")
        return next((row for row in self.record.get("photos",[]) if str(row.get("id","") or "")==photo_id),None)

    def _load(self):
        photo=self._selected_photo()
        if not photo:self.image.setText("Ingen fotos i feltregistreringen."); return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor); self.status.setText("Henter foto…")
        try:
            raw=pl_daase_api.fetch_photo(photo.get("url",""),self.token,source_url=self.source_url,timeout=15)
            pix=QPixmap();
            if not pix.loadFromData(raw,"JPEG"):raise pl_daase_api.PLDaaseApiError("Fotoet kunne ikke afkodes.")
            painter=QPainter(pix); pen=QPen(QColor("#f59e0b")); pen.setWidth(max(3,int(round(min(pix.width(),pix.height())*.006)))); painter.setPen(pen)
            font=QFont(); font.setBold(True); font.setPixelSize(max(18,int(round(min(pix.width(),pix.height())*.035)))); painter.setFont(font)
            for marker in photo.get("markers",[]) or []:
                x=float(marker.get("x",0))*pix.width(); y=float(marker.get("y",0))*pix.height(); radius=max(14,min(pix.width(),pix.height())*.025)
                painter.setBrush(QColor(245,158,11,210)); painter.drawEllipse(int(x-radius),int(y-radius),int(radius*2),int(radius*2)); painter.setPen(QColor("#111827")); painter.drawText(int(x-radius),int(y-radius),int(radius*2),int(radius*2),Qt.AlignmentFlag.AlignCenter,str(marker.get("position","") or "")); painter.setPen(pen)
            painter.end(); self.original=pix; self._show_scaled(); self.status.setText(f"{pix.width()} × {pix.height()} px · markører viser indføring 1–6")
        except pl_daase_api.PLDaaseApiError as exc:
            self.status.setObjectName("dangerText"); self.status.setText(str(exc)); self.image.setText("Fotoet kunne ikke hentes.")
        finally:
            QApplication.restoreOverrideCursor(); self.status.style().unpolish(self.status); self.status.style().polish(self.status)

    def _show_scaled(self):
        if self.original.isNull():return
        target=self.image.size()
        self.image.setPixmap(self.original.scaled(max(100,target.width()-8),max(100,target.height()-8),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self,event):
        super().resizeEvent(event); self._show_scaled()
