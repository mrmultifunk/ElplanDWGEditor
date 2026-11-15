from __future__ import annotations

from copy import deepcopy
from PySide6.QtCore import QPointF, Qt
from PySide6.QtWidgets import QMenu, QMessageBox

import core_logic as core
from qt_commands import AddCableCommand, EditCableCommand, EditSymbolCommand, CableArticleBindingsCommand
from qt_graphics import CableItem


class CableAttachMixin:
    """Interaction flow for attaching an existing PL lamp point to an existing cable.

    Kept outside qt_app.py so the main window remains focused on composition and
    shared application state rather than one-off drawing tools.
    """

    def _symbol_context_menu(self, item: ElectricalSymbolItem, screen_pos) -> None:
        placement=getattr(item,"placement",None)
        if placement is None:return
        self._clear_hover_info()
        self.scene.clearSelection(); item.setSelected(True); self._selection_changed()
        menu=QMenu(self)
        attach=configure=None
        symbol=str(getattr(placement,"symbol","") or "")
        if symbol in {"light_connection","wall_light_outlet"}:
            attach=menu.addAction("Tilknyt til eksisterende kabel…")
            attach.setEnabled(not bool(getattr(placement,"locked",False)))
        if symbol=="light_connection":
            configure=menu.addAction("Konfigurer PL-dåse…")
            configure.setEnabled(not bool(getattr(placement,"locked",False)))
        if attach is not None or configure is not None:
            menu.addSeparator()
        group=self._selected_focus_group() if hasattr(self,"_selected_focus_group") else ""
        trace=menu.addAction(f"Spor gruppe · {group}" if group else "Spor gruppe")
        trace.setEnabled(bool(group))
        focus=menu.addAction(f"Fokusér gruppe · {group}" if group else "Fokusér gruppe")
        focus.setEnabled(bool(group))
        zoom=menu.addAction("Zoom til symbol")
        menu.addSeparator()
        delete=menu.addAction("Slet symbol")
        delete.setEnabled(not bool(getattr(placement,"locked",False)))
        delete.setToolTip("Lås symbolet op i Egenskaber før det slettes." if bool(getattr(placement,"locked",False)) else "Slet symbolet. Handlingen kan fortrydes.")
        chosen=menu.exec(screen_pos)
        if attach is not None and chosen is attach:
            self._start_cable_attach_mode(placement)
        elif configure is not None and chosen is configure:
            self.open_pl_box_dialog(placement)
        elif chosen is trace:
            self.trace_selected_circuit()
        elif chosen is focus:
            self.focus_selected_group()
        elif chosen is zoom:
            self.zoom_to_selection()
        elif chosen is delete:
            self.delete_selected_symbols()


    def start_cable_attach_for_selection(self) -> None:
        item=self._selected_symbol_item()
        if item is None or str(getattr(item.placement,"symbol","") or "") not in {"light_connection","wall_light_outlet"}:
            self._set_status("Vælg et lampested først.")
            return
        self._start_cable_attach_mode(item.placement)

    def _start_cable_attach_mode(self, placement) -> None:
        if placement is None or str(getattr(placement,"symbol","") or "") not in {"light_connection","wall_light_outlet"}:
            return
        if bool(getattr(placement,"locked",False)):
            QMessageBox.information(self,"Tilknyt kabel","Lampestedet er låst. Lås symbolet op før kabeltilknytningen ændres.")
            return
        # Luk andre interaktive værktøjer, men behold lampestedet valgt.
        self.association_source_uid=""; self.association_pick_source=False; self.spot_parent_pending=[]
        self._clear_association_visuals(); self._clear_spot_link_visuals(); self.view.cancel_tool(emit_signal=False)
        if self._cable_tool_is_open():
            self.close_cable_tool()
        self._clear_hover_info()
        self._pending_cable_attach_symbol_uid=str(placement.uid)
        self.view.setCursor(Qt.CursorShape.CrossCursor)
        ident=str(getattr(placement,"group","") or getattr(placement,"label","") or "Lampested").strip()
        self._set_status(f"Tilknyt {ident} til eksisterende kabel · klik direkte på den ønskede kabelstrækning · Esc annullerer")

    def _remap_pl_state_for_split(self, placement, old_cable_uid: str, target_cable, target_conn: dict) -> tuple[dict,dict]:
        """Return before/after symbol states when one cable endpoint gets a new UID."""
        before=self._symbol_state(placement)
        after=deepcopy(before)
        new_uid=str(getattr(target_cable,"uid","") or "")
        new_idx=int(target_conn.get("point_index",0) or 0)

        def remap(row):
            item=dict(row or {})
            if str(item.get("cable_uid","") or "")==str(old_cable_uid or ""):
                item["cable_uid"]=new_uid; item["point_index"]=new_idx; item["leg"]="endpoint"
            return item

        entries={}
        for port,row in core.normalize_pl_box_entries(after.get("pl_box_entries",{})).items():
            entries[port]=remap(row)
        after["pl_box_entries"]=core.normalize_pl_box_entries(entries)
        after["pl_box_wiring"]=core.normalize_pl_box_wiring([remap(row) for row in after.get("pl_box_wiring",[])])
        splices=[]
        for splice in core.normalize_pl_box_splices(after.get("pl_box_splices",[])):
            item=dict(splice); item["members"]=[remap(member) for member in splice.get("members",[]) or []]; splices.append(item)
        after["pl_box_splices"]=core.normalize_pl_box_splices(splices)
        return before,after

    def _handle_cable_item_click(self, item: CableItem, scene_pos: QPointF) -> bool:
        uid=str(getattr(self,"_pending_cable_attach_symbol_uid","") or "")
        if not uid:
            return False
        placement=self._placement_by_uid(uid)
        if placement is None:
            self._pending_cable_attach_symbol_uid=""; self.view.unsetCursor(); return True
        cable=getattr(item,"cable",None)
        if cable is None:return True
        if not cable.points or len(cable.points)<2:
            QMessageBox.information(self,"Tilknyt kabel","Det valgte kabel har ikke en gyldig rute.")
            return True

        click=(float(scene_pos.x()),float(-scene_pos.y()))
        clicked=core.nearest_cable_segment(cable.points,click)
        if clicked is None:return True
        seg=int(clicked["segment_index"])
        ports=core.placement_connection_ports(placement)
        if not ports:
            QMessageBox.information(self,"Tilknyt kabel","Lampestedet har ikke et fysisk kabeltilslutningspunkt.")
            return True
        scored=[]
        for px,py,port in ports:
            info=core.nearest_cable_segment(cable.points[seg:seg+2],(px,py))
            scored.append((float(info["distance"]) if info else float("inf"),float(px),float(py),int(port)))
        distance,px,py,port=min(scored,key=lambda row:row[0])
        distance_px=distance*max(float(self.view.current_scale()),1e-9)
        if distance_px>42.0:
            answer=QMessageBox.question(
                self,"Før kabel til lampested",
                "Lampestedets tilslutningspunkt ligger et stykke fra den valgte kabelrute.\n\n"
                "Skal kabelruten føres hen til lampestedet og deles i to fysiske kabler?\n"
                "De eksisterende endepunkter, gruppe/kreds og kabeldata bevares.",
                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self._set_status("Vælg en kabelstrækning tættere på lampestedet · Esc annullerer")
                return True

        # Work on a copy first. Inserting a new physical installation point into
        # one cable means the real model must replace it with two cables, not add
        # a third connection to the same CablePlacement.
        temp=deepcopy(cable)
        result=core.attach_symbol_to_existing_cable(temp,placement.uid,port,(px,py),segment_index=seg)
        status=str(result.get("status","") or "")
        if status=="occupied":
            QMessageBox.warning(self,"Tilknyt kabel","Det valgte kabelpunkt er allerede fysisk tilsluttet et andet symbol. Vælg et andet sted på kabelstrækningen.")
            return True
        if status=="already_attached":
            self._pending_cable_attach_symbol_uid=""; self.view.unsetCursor()
            self._set_status("Dette lampested er allerede tilsluttet det valgte kabel.")
            return True

        replacements=core.split_cable_into_physical_segments(temp)
        # Attaching to a free endpoint does not create a new physical span. The
        # existing cable simply gains that endpoint connection and keeps UID,
        # article binding, group/circuit and cable ID unchanged.
        if len(replacements)==1 and bool(result.get("endpoint")):
            replacement=replacements[0]
            replacement.cable_id=str(getattr(cable,"cable_id","") or "")
            replacement.circuit_id=str(getattr(cable,"circuit_id","") or "")
            replacement.route_chain_uid=str(getattr(cable,"route_chain_uid","") or getattr(cable,"uid","") or "")
            before_cable=CableItem.state(cable); after_cable=CableItem.state(replacement)
            if before_cable!=after_cable:
                self.undo_stack.push(EditCableCommand(self,cable,before_cable,after_cable,"Tilknyt lampested til kabelende"))
            self._pending_cable_attach_symbol_uid=""; self.view.unsetCursor()
            self._rebuild_cable_visual_cache(refresh_items=True)
            self._refresh_symbol_cables_group(placement); self._refresh_pl_box_group(placement)
            ann=self.annotation_items.get(placement.uid)
            if ann is not None:ann.refresh()
            group=str(getattr(cable,"circuit_id","") or "").strip(); suffix=f" · gruppe {group}" if group else ""
            message=f"Lampestedet er tilsluttet den frie kabelende{suffix}. Kablet forbliver ét fysisk kabel."
            (self._notify(message,kind="success") if hasattr(self,"_notify") else self._set_status(message))
            return True
        if len(replacements)<2:
            QMessageBox.warning(self,"Tilknyt kabel","Kabelstrækningen kunne ikke opdeles entydigt ved lampestedet.")
            return True

        # The first replacement keeps the original ID/UID. New pieces get the
        # next available cable IDs and inherit group/article until changed.
        first_id=str(getattr(cable,"cable_id","") or "").strip()
        layer=str(getattr(cable,"layer",core.CABLE_LAYER) or core.CABLE_LAYER)
        prefix="L" if layer==core.WIRE_LAYER else ("P" if layer==core.PATCH_CABLE_LAYER else "K")
        extra_ids=self._allocate_cable_ids(len(replacements)-1,"",prefix)
        replacements[0].cable_id=first_id
        for repl,new_id in zip(replacements[1:],extra_ids):
            repl.cable_id=new_id
        chain_uid=str(getattr(cable,"route_chain_uid","") or getattr(cable,"uid","") or "")
        for repl in replacements:
            repl.circuit_id=str(getattr(cable,"circuit_id","") or "")
            repl.route_chain_uid=chain_uid
            repl.route_section_modes=[]; repl.spec_section_overrides=[]

        before_cable=CableItem.state(cable)
        first_state=CableItem.state(replacements[0])

        # Existing PL boxes at the original endpoints may now point to a newly
        # created cable UID. Build undoable symbol-state remaps for those boxes.
        original_end_symbols={str(r.get("symbol_uid","") or "") for r in core.cable_symbol_connections(cable)}
        symbol_changes=[]
        for symbol_uid in original_end_symbols:
            p=self._placement_by_uid(symbol_uid)
            if p is None or str(getattr(p,"symbol","") or "")!="light_connection":continue
            target=None; target_conn=None
            for repl in replacements:
                conn=next((r for r in core.cable_symbol_connections(repl) if str(r.get("symbol_uid","") or "")==symbol_uid),None)
                if conn is not None:
                    target=repl; target_conn=conn; break
            if target is None or str(getattr(target,"uid","") or "")==str(getattr(cable,"uid","") or ""):
                continue
            before_state,after_state=self._remap_pl_state_for_split(p,str(getattr(cable,"uid","") or ""),target,target_conn)
            if before_state!=after_state:
                symbol_changes.append((p.uid,before_state,after_state))

        bindings_before=self._cable_article_bindings()
        bindings_after=dict(bindings_before)
        article_no=bindings_before.get(str(getattr(cable,"uid","") or ""),"")
        if article_no:
            for repl in replacements[1:]:
                bindings_after[str(getattr(repl,"uid","") or "")]=article_no

        self.undo_stack.beginMacro("Indsæt lampested i kabel")
        try:
            self.undo_stack.push(EditCableCommand(self,cable,before_cable,first_state,"Del kabel ved lampested"))
            for repl in replacements[1:]:
                self.undo_stack.push(AddCableCommand(self,repl,"Nyt fysisk kabelstykke"))
            for symbol_uid,before_state,after_state in symbol_changes:
                self.undo_stack.push(EditSymbolCommand(self,symbol_uid,before_state,after_state,"Opdatér PL-kabelreference"))
            if bindings_before!=bindings_after:
                self.undo_stack.push(CableArticleBindingsCommand(self,bindings_before,bindings_after,"Kopiér kabelartikel til nye stykker"))
        finally:
            self.undo_stack.endMacro()

        self._pending_cable_attach_symbol_uid=""; self.view.unsetCursor()
        self._rebuild_cable_visual_cache(refresh_items=True)
        self._refresh_symbol_cables_group(placement); self._refresh_pl_box_group(placement)
        ann=self.annotation_items.get(placement.uid)
        if ann is not None:ann.refresh()
        group=str(getattr(cable,"circuit_id","") or "").strip()
        suffix=f" · gruppe {group}" if group else ""
        message=f"Lampestedet er indsat som fysisk samlingspunkt: 1 kabel blev til {len(replacements)} selvstændige kabelstykker{suffix}."
        (self._notify(message,kind="success") if hasattr(self,"_notify") else self._set_status(message))
        return True
