from __future__ import annotations

from PySide6.QtWidgets import QInputDialog, QMenu, QMessageBox

import core_logic as core
from elplan_qt.qt_commands import EditCableCommand
from elplan_qt.qt_graphics import CableItem


class CableSectionRoutingMixin:
    """Compatibility helpers for cable route/spec editing.

    Since 0.55 one CablePlacement is already one physical cable. The old
    section API is kept so context menus/tests and migrated plugins continue to
    work, but edits are materialised on the selected cable itself.
    """

    def _cable_connection_name(self, row: dict) -> str:
        uid=str(row.get("symbol_uid","") or "")
        placement=self._placement_by_uid(uid) if uid else None
        if placement is None:
            return uid[:8] or "Tilslutning"
        group=str(getattr(placement,"group","") or "").strip()
        label=str(getattr(placement,"label","") or "").strip()
        # Afsnitsvælgeren skal kunne skelne mellem flere lampesteder på samme
        # gruppe/kreds. Vis derfor både gruppe/kreds og den frie mærkning, når
        # begge findes, i samme identifikationsformat som resten af PL-flowet.
        parts=[]
        for value in (group,label):
            if value and value not in parts:
                parts.append(value)
        if parts:
            return " · ".join(parts)
        return core.symbol_display_name(str(getattr(placement,"symbol","") or ""))

    def _cable_section_title(self, section: dict) -> str:
        return f"{self._cable_connection_name(section['a'])} → {self._cable_connection_name(section['b'])}"

    @staticmethod
    def _cable_section_key(section: dict) -> str:
        key=tuple(section.get("key") or ())
        if len(key)!=2:
            return ""
        return f"{key[0][0]}:{int(key[0][1])}|{key[1][0]}:{int(key[1][1])}"

    def _find_cable_section_by_key(self, cable, key):
        wanted=str(key or "")
        return next((row for row in core.cable_connection_sections(cable) if self._cable_section_key(row)==wanted),None)

    def _refresh_cable_section_controls(self, cable=None) -> None:
        combo=getattr(self,"cable_section_combo",None)
        mode_combo=getattr(self,"cable_section_route_combo",None)
        spec_combo=getattr(self,"cable_section_spec_combo",None)
        button=getattr(self,"cable_section_apply",None)
        spec_button=getattr(self,"cable_section_spec_apply",None)
        group=getattr(self,"cable_section_group",None)
        hint=getattr(self,"cable_section_hint",None)
        if combo is None or mode_combo is None:
            return
        previous=combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        sections=core.cable_connection_sections(cable) if cable is not None else []
        for section in sections:
            mode=core.cable_route_section_mode(cable,section["a"],section["b"])
            mode_label="Fri / diagonal" if mode=="free" else "Ortogonal (90°)"
            spec=core.cable_spec_for_section(cable,section["a"],section["b"])
            combo.addItem(f"{self._cable_section_title(section)}  ·  {spec or 'uden type'}  ·  {mode_label}",self._cable_section_key(section))
        if previous is not None:
            idx=combo.findData(previous)
            if idx>=0: combo.setCurrentIndex(idx)
        combo.blockSignals(False)
        enabled=bool(cable is not None and sections)
        if group is not None: group.setEnabled(enabled)
        combo.setEnabled(enabled); mode_combo.setEnabled(enabled)
        if spec_combo is not None: spec_combo.setEnabled(enabled)
        if button is not None: button.setEnabled(enabled)
        if spec_button is not None: spec_button.setEnabled(enabled)
        if hint is not None:
            hint.setText(
                "Vælg strækket mellem to nabotilslutninger. Kabeltype og ruteføring kan ændres kun på dette afsnit; resten af kablet forbliver uændret. "
                "Du kan også højreklikke direkte på kabelstrækket i tegningen."
                if enabled else
                "Afsnitsvise indstillinger bliver tilgængelige, når kablet har mindst to fysiske tilslutningssteder."
            )
        self._cable_section_selection_changed()

    def _cable_section_selection_changed(self, *_args) -> None:
        cable=getattr(self,"selected_cable",None)
        combo=getattr(self,"cable_section_combo",None)
        mode_combo=getattr(self,"cable_section_route_combo",None)
        spec_combo=getattr(self,"cable_section_spec_combo",None)
        if cable is None or combo is None or mode_combo is None:
            return
        section=self._find_cable_section_by_key(cable,combo.currentData())
        if section is None:
            return
        mode=core.cable_route_section_mode(cable,section["a"],section["b"])
        idx=mode_combo.findData(mode)
        if idx>=0:
            mode_combo.blockSignals(True); mode_combo.setCurrentIndex(idx); mode_combo.blockSignals(False)
        if spec_combo is not None:
            spec=core.cable_spec_for_section(cable,section["a"],section["b"])
            spec_combo.blockSignals(True); spec_combo.setCurrentText(spec); spec_combo.blockSignals(False)

    def _set_cable_section_route(self, cable, section: dict, mode: str, *, source: str = "panel") -> bool:
        mode=str(mode or "").strip().lower()
        if mode not in {"free","orthogonal"}:
            return False
        current=core.cable_route_section_mode(cable,section["a"],section["b"])
        if current==mode:
            self._set_status(f"Afsnittet {self._cable_section_title(section)} bruger allerede {'fri/diagonal' if mode=='free' else '90°'} ruteføring.")
            return False
        before=CableItem.state(cable)
        if core.cable_is_physical_segment(cable):
            points,connections=core.convert_cable_route_mode_geometry(
                cable.points,core.cable_symbol_connections(cable),
                from_orthogonal=bool(getattr(cable,"orthogonal",False)),to_orthogonal=(mode=="orthogonal"),
            )
            cable.points=points; core.set_cable_symbol_connections(cable,connections)
            cable.orthogonal=(mode=="orthogonal"); cable.route_section_modes=[]
            after=CableItem.state(cable)
            if before==after:return False
            self.undo_stack.push(EditCableCommand(self,cable,before,after,"Redigér fysisk kabelrute",already_applied=True))
            self._rebuild_cable_visual_cache(refresh_items=True); self._load_selected_cable_into_panel(cable)
            message=f"{getattr(cable,'cable_id','') or 'Kabel'}: {'Fri / diagonal' if mode=='free' else 'Ortogonal (90°)'} ruteføring."
            (self._notify(message,kind="success") if hasattr(self,"_notify") else self._set_status(message))
            return True
        points,connections=core.convert_cable_route_section_geometry(
            cable.points,core.cable_symbol_connections(cable),
            int(section["start_point_index"]),int(section["end_point_index"]),
            from_orthogonal=(current=="orthogonal"),to_orthogonal=(mode=="orthogonal"),
        )
        cable.points=points
        core.set_cable_symbol_connections(cable,connections)
        # Re-find endpoints after remapping. The stable key guarantees that the
        # same physical section is found even if one elbow disappeared/appeared.
        refreshed=self._find_cable_section_by_key(cable,self._cable_section_key(section))
        if refreshed is None:
            # Defensive rollback for malformed legacy data.
            self._apply_cable_state(cable,before)
            QMessageBox.warning(self,"Ruteføring pr. afsnit","Afsnittet kunne ikke genfindes efter geometrikonverteringen. Ingen ændringer er gemt.")
            return False
        core.set_cable_route_section_mode(cable,refreshed["a"],refreshed["b"],mode)
        after=CableItem.state(cable)
        if before==after:
            return False
        self.undo_stack.push(EditCableCommand(self,cable,before,after,"Redigér kabelafsnit",already_applied=True))
        self._rebuild_cable_visual_cache(refresh_items=True)
        self._load_selected_cable_into_panel(cable)
        message=f"{self._cable_section_title(refreshed)}: {'Fri / diagonal' if mode=='free' else 'Ortogonal (90°)'} · resten af kablet er uændret."
        if hasattr(self,"_notify"):
            self._notify(message,kind="success")
        else:
            self._set_status(message)
        return True

    def apply_selected_cable_section_route(self) -> None:
        cable=getattr(self,"selected_cable",None)
        combo=getattr(self,"cable_section_combo",None)
        mode_combo=getattr(self,"cable_section_route_combo",None)
        if cable is None or combo is None or mode_combo is None:
            return
        section=self._find_cable_section_by_key(cable,combo.currentData())
        if section is None:
            self._set_status("Vælg et gyldigt kabelafsnit først.")
            return
        self._set_cable_section_route(cable,section,str(mode_combo.currentData() or "free"),source="panel")

    def _set_cable_section_spec(self, cable, section: dict, cable_spec: str, *, source: str = "panel") -> bool:
        spec=str(cable_spec or "").strip()
        if not spec:
            QMessageBox.warning(self,"Kabeltype pr. afsnit","Angiv en kabeltype, fx 3G1,5 eller 5G1,5.")
            return False
        current=core.cable_spec_for_section(cable,section["a"],section["b"])
        if current==spec:
            self._set_status(f"Afsnittet {self._cable_section_title(section)} bruger allerede {spec}.")
            return False
        before=CableItem.state(cable)
        if core.cable_is_physical_segment(cable):
            cable.cable_spec=spec; cable.spec_section_overrides=[]
            after=CableItem.state(cable)
            if before==after:return False
            self.undo_stack.push(EditCableCommand(self,cable,before,after,"Redigér kabeltype",already_applied=True))
            self._rebuild_cable_visual_cache(refresh_items=True); self._load_selected_cable_into_panel(cable)
            message=f"{getattr(cable,'cable_id','') or 'Kabel'}: kabeltype {spec}."
            (self._notify(message,kind="success") if hasattr(self,"_notify") else self._set_status(message))
            return True
        core.set_cable_spec_for_section(cable,section["a"],section["b"],spec)
        after=CableItem.state(cable)
        if before==after:
            return False
        self.undo_stack.push(EditCableCommand(self,cable,before,after,"Redigér kabeltype på afsnit",already_applied=True))
        self._rebuild_cable_visual_cache(refresh_items=True)
        self._load_selected_cable_into_panel(cable)
        refreshed=self._find_cable_section_by_key(cable,self._cable_section_key(section)) or section
        message=f"{self._cable_section_title(refreshed)}: kabeltype {spec} · resten af kablet er uændret."
        if hasattr(self,"_notify"):
            self._notify(message,kind="success")
        else:
            self._set_status(message)
        return True

    def apply_selected_cable_section_spec(self) -> None:
        cable=getattr(self,"selected_cable",None)
        combo=getattr(self,"cable_section_combo",None)
        spec_combo=getattr(self,"cable_section_spec_combo",None)
        if cable is None or combo is None or spec_combo is None:
            return
        section=self._find_cable_section_by_key(cable,combo.currentData())
        if section is None:
            self._set_status("Vælg et gyldigt kabelafsnit først.")
            return
        self._set_cable_section_spec(cable,section,spec_combo.currentText(),source="panel")

    def _cable_context_menu(self, item: CableItem, scene_pos, screen_pos) -> None:
        cable=getattr(item,"cable",None)
        if cable is None:
            return
        if hasattr(self,"_clear_hover_info"):self._clear_hover_info()
        self.scene.clearSelection(); item.setSelected(True)
        click=(float(scene_pos.x()),float(-scene_pos.y()))
        nearest=core.nearest_cable_segment(cable.points,click)
        section=core.cable_route_section_at_segment(cable,int(nearest["segment_index"])) if nearest else None
        menu=QMenu(self)
        if section is None:
            unavailable=menu.addAction("Afsnitsvis ruteføring kræver to nabotilslutninger")
            unavailable.setEnabled(False)
            menu.addSeparator()
            mark=menu.addAction("Mærk kabel…")
            group=str(getattr(cable,"circuit_id","") or "").strip()
            trace=menu.addAction(f"Spor gruppe · {group}" if group else "Spor gruppe"); trace.setEnabled(bool(group))
            focus=menu.addAction(f"Fokusér gruppe · {group}" if group else "Fokusér gruppe"); focus.setEnabled(bool(group))
            zoom=menu.addAction("Zoom til kabel")
            chosen=menu.exec(screen_pos)
            if chosen is mark:self.start_cable_marking(str(getattr(cable,"uid","") or ""),show_editor=True)
            elif chosen is trace:self.trace_selected_circuit()
            elif chosen is focus:self.focus_selected_group()
            elif chosen is zoom:self.zoom_to_selection()
            return
        title=menu.addAction(f"Fysisk kabel · {self._cable_section_title(section)}"); title.setEnabled(False)
        current_spec=core.cable_spec_for_section(cable,section["a"],section["b"])
        spec_title=menu.addAction(f"Kabeltype: {current_spec or '—'}"); spec_title.setEnabled(False)
        menu.addSeparator()
        current=core.cable_route_section_mode(cable,section["a"],section["b"])
        free=menu.addAction("Fri / diagonal for dette kabel")
        ortho=menu.addAction("Ortogonal (90°) for dette kabel")
        free.setCheckable(True); ortho.setCheckable(True)
        free.setChecked(current=="free"); ortho.setChecked(current=="orthogonal")
        spec_menu=menu.addMenu("Kabeltype for dette kabel")
        spec_actions={}
        candidates=[]
        for value in (current_spec,str(getattr(cable,"cable_spec","") or ""),*core.CABLE_SPEC_PRESETS):
            value=str(value or "").strip()
            if value and value not in candidates:
                candidates.append(value)
        for value in candidates:
            action=spec_menu.addAction(value); action.setCheckable(True); action.setChecked(value==current_spec)
            spec_actions[action]=value
        spec_menu.addSeparator(); custom_spec=spec_menu.addAction("Anden kabeltype…")
        menu.addSeparator()
        open_panel=menu.addAction("Vis kablet i Kabelværktøj")
        mark=menu.addAction("Mærk kabel…")
        group=str(getattr(cable,"circuit_id","") or "").strip()
        trace=menu.addAction(f"Spor gruppe · {group}" if group else "Spor gruppe"); trace.setEnabled(bool(group))
        focus=menu.addAction(f"Fokusér gruppe · {group}" if group else "Fokusér gruppe"); focus.setEnabled(bool(group))
        zoom=menu.addAction("Zoom til kabel")
        chosen=menu.exec(screen_pos)
        if chosen is free:
            self._set_cable_section_route(cable,section,"free",source="context")
        elif chosen is ortho:
            self._set_cable_section_route(cable,section,"orthogonal",source="context")
        elif chosen in spec_actions:
            self._set_cable_section_spec(cable,section,spec_actions[chosen],source="context")
        elif chosen is custom_spec:
            value,ok=QInputDialog.getText(self,"Kabeltype","Kabeltype:",text=current_spec)
            if ok and str(value or "").strip():
                self._set_cable_section_spec(cable,section,str(value).strip(),source="context")
        elif chosen is mark:self.start_cable_marking(str(getattr(cable,"uid","") or ""),show_editor=True)
        elif chosen is trace:self.trace_selected_circuit()
        elif chosen is focus:self.focus_selected_group()
        elif chosen is zoom:self.zoom_to_selection()
        elif chosen is open_panel:
            self._load_selected_cable_into_panel(cable)
            self._show_inspector_page(
                "cable",
                title=core.cable_display_label(cable) or cable.cable_id or "Kabel",
                hint="Redigér kabeldata, mærkning, artikel eller ruteføring for det valgte fysiske kabel.",
            )
            idx=self.cable_section_combo.findData(self._cable_section_key(section))
            if idx>=0:self.cable_section_combo.setCurrentIndex(idx)
