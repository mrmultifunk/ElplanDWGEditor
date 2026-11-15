from __future__ import annotations

import uuid

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsRectItem, QInputDialog, QMessageBox

import core_logic as core
from qt_commands import SpotParentCommand
from qt_graphics import ElectricalSymbolItem


class SpotUiMixin:
    """Spot grouping and Spot → lampested workflow."""

    def _selected_spots(self, *, unlocked_only: bool = False) -> list[core.Placement]:
        spots=[
            x.placement for x in self.scene.selectedItems()
            if isinstance(x,ElectricalSymbolItem) and x.placement.symbol=="spot"
        ]
        if not spots:
            item=self._selected_symbol_item()
            if item is not None and item.placement.symbol=="spot":
                spots=[item.placement]
        if unlocked_only:
            spots=[p for p in spots if not p.locked]
        return spots

    def _spot_group_members(self, group_id: str) -> list[core.Placement]:
        gid=str(group_id or "").strip()
        if not gid:return []
        return [
            p for p in self.project.placements
            if p.symbol=="spot" and str(getattr(p,"spot_group_id","") or "")==gid
        ]

    def _expand_spots_to_groups(self, spots: list[core.Placement]) -> list[core.Placement]:
        out={p.uid:p for p in spots if p.symbol=="spot"}
        for p in list(out.values()):
            gid=str(getattr(p,"spot_group_id","") or "")
            if gid:
                for member in self._spot_group_members(gid):out[member.uid]=member
        return list(out.values())

    def _next_spot_group_name(self) -> str:
        used={str(getattr(p,"spot_group_name","") or "").strip().casefold() for p in self.project.placements if p.symbol=="spot"}
        index=1
        while f"spotgruppe {index}".casefold() in used:index+=1
        return f"Spotgruppe {index}"

    def _spot_group_summary(self, spots: list[core.Placement]) -> str:
        if not spots:return "Gruppe: —"
        gids={str(getattr(p,"spot_group_id","") or "") for p in spots if str(getattr(p,"spot_group_id","") or "")}
        ungrouped=sum(1 for p in spots if not str(getattr(p,"spot_group_id","") or ""))
        if len(gids)==1 and not ungrouped:
            gid=next(iter(gids)); members=self._spot_group_members(gid)
            name=next((str(getattr(p,"spot_group_name","") or "").strip() for p in members if str(getattr(p,"spot_group_name","") or "").strip()),"Spotgruppe")
            return f"Gruppe: {name} · {len(members)} spot(s)"
        if not gids:
            return f"Gruppe: Ikke grupperet · {len(spots)} spot(s) valgt"
        parts=[]
        for gid in sorted(gids):
            members=self._spot_group_members(gid); name=next((str(getattr(p,"spot_group_name","") or "").strip() for p in members if str(getattr(p,"spot_group_name","") or "").strip()),"Spotgruppe")
            parts.append(f"{name} ({len(members)})")
        if ungrouped:parts.append(f"{ungrouped} ugrupperet")
        return "Grupper: " + " · ".join(parts)

    def _refresh_spot_group_controls(self, spots: list[core.Placement]) -> None:
        if not hasattr(self,"spot_group_value"):return
        self.spot_group_value.setText(self._spot_group_summary(spots))
        gids={str(getattr(p,"spot_group_id","") or "") for p in spots if str(getattr(p,"spot_group_id","") or "")}
        unlocked=any(not p.locked for p in spots)
        self.spot_group_button.setEnabled(bool(spots) and unlocked)
        self.spot_group_select_button.setEnabled(len(gids)==1)
        self.spot_group_clear_button.setEnabled(bool(gids) and unlocked)

    def group_selected_spots(self) -> None:
        spots=self._selected_spots(unlocked_only=True)
        if not spots:
            self._set_status("Vælg ét eller flere ulåste spots først.");return
        expanded=self._expand_spots_to_groups(spots)
        if any(p.locked for p in expanded):
            QMessageBox.information(self,"Spotgruppe","Mindst ét spot i den berørte spotgruppe er låst. Lås gruppens spots op før gruppen ændres.")
            return
        parent_ids={str(getattr(p,"parent_light_uid","") or "") for p in expanded if str(getattr(p,"parent_light_uid","") or "")}
        if len(parent_ids)>1:
            QMessageBox.warning(self,"Spotgruppe","De valgte spots er koblet til forskellige lampesteder. Frakobl eller saml lampestedstilknytningen først.")
            return
        gids={str(getattr(p,"spot_group_id","") or "") for p in spots if str(getattr(p,"spot_group_id","") or "")}
        same_group=len(gids)==1 and all(str(getattr(p,"spot_group_id","") or "") in gids for p in spots)
        existing_gid=next(iter(gids)) if same_group else ""
        if existing_gid:
            members=self._spot_group_members(existing_gid)
            default=next((str(getattr(p,"spot_group_name","") or "").strip() for p in members if str(getattr(p,"spot_group_name","") or "").strip()),self._next_spot_group_name())
            target_spots=members
            target_gid=existing_gid
            title="Omdøb spotgruppe"
        else:
            target_spots=expanded
            target_gid=uuid.uuid4().hex
            # If precisely one existing group participates, extend that group instead of creating a needless replacement id.
            source_gids={str(getattr(p,"spot_group_id","") or "") for p in expanded if str(getattr(p,"spot_group_id","") or "")}
            if len(source_gids)==1:
                target_gid=next(iter(source_gids)); target_spots=self._expand_spots_to_groups(spots)
                members=self._spot_group_members(target_gid)
                default=next((str(getattr(p,"spot_group_name","") or "").strip() for p in members if str(getattr(p,"spot_group_name","") or "").strip()),self._next_spot_group_name())
            else:
                default=self._next_spot_group_name()
            title="Gruppér spots"
        name,ok=QInputDialog.getText(self,title,"Navn på spotgruppe:",text=default)
        if not ok:return
        name=str(name or "").strip() or default
        before=self._spot_parent_snapshot()
        inherited_parent=next(iter(parent_ids)) if parent_ids else ""
        parent=self._placement_by_uid(inherited_parent) if inherited_parent else None
        for spot in target_spots:
            if spot.locked:continue
            spot.spot_group_id=target_gid; spot.spot_group_name=name
            if parent is not None:
                spot.parent_light_uid=parent.uid; spot.associations=core.normalize_light_associations(parent.associations)
        after=self._spot_parent_snapshot()
        if before!=after:self.undo_stack.push(SpotParentCommand(self,before,after,"Gruppér spots"))
        self._refresh_spot_group_controls(self._selected_spots())
        self._set_status(f"{len(target_spots)} spot(s) samlet i {name}.")

    def select_spot_group(self) -> None:
        spots=self._selected_spots()
        gids={str(getattr(p,"spot_group_id","") or "") for p in spots if str(getattr(p,"spot_group_id","") or "")}
        if len(gids)!=1:return
        members=self._spot_group_members(next(iter(gids)))
        self.scene.clearSelection()
        for p in members:
            item=self.symbol_items.get(p.uid)
            if item is not None and item.isVisible():item.setSelected(True)
        self._set_status(f"{len(members)} spot(s) i gruppen valgt.")

    def dissolve_spot_group(self) -> None:
        spots=self._selected_spots(unlocked_only=True)
        gids={str(getattr(p,"spot_group_id","") or "") for p in spots if str(getattr(p,"spot_group_id","") or "")}
        if not gids:return
        all_members=[p for gid in gids for p in self._spot_group_members(gid)]
        if any(p.locked for p in all_members):
            QMessageBox.information(self,"Spotgruppe","En valgt spotgruppe indeholder låste spots. Lås dem op før gruppen opløses.")
            return
        members=all_members
        before=self._spot_parent_snapshot()
        for spot in members:
            spot.spot_group_id=""; spot.spot_group_name=""
        after=self._spot_parent_snapshot()
        if before!=after:self.undo_stack.push(SpotParentCommand(self,before,after,"Opløs spotgruppe"))
        self._refresh_spot_group_controls(self._selected_spots())
        self._set_status(f"{len(members)} spot(s) er ikke længere grupperet. Lampestedstilknytningen er bevaret.")

    def _spot_parent_label(self, spot: core.Placement) -> str:
        uid=str(getattr(spot,"parent_light_uid","") or "")
        if not uid:
            return ""
        parent=self._placement_by_uid(uid)
        if parent is None:
            return "↳ Lampested ?"
        ident=str(getattr(parent,"group","") or getattr(parent,"label","") or "Lampested").strip()
        return f"↳ {ident}"

    def _linked_spots(self, parent_uid: str) -> list[core.Placement]:
        return [
            p for p in self.project.placements
            if p.symbol=="spot" and str(getattr(p,"parent_light_uid","") or "")==str(parent_uid)
        ]

    def _clear_spot_link_visuals(self) -> None:
        for item in list(self.spot_link_overlays)+list(self.spot_link_paths):
            if item is not None and item.scene() is not None:
                self.scene.removeItem(item)
        self.spot_link_overlays.clear()
        self.spot_link_paths.clear()

    def _spot_link_highlight(self, item: ElectricalSymbolItem, color="#169c96") -> None:
        scale=max(self.view.current_scale(),1e-9)
        margin=7.0/scale
        rect=item.sceneBoundingRect().adjusted(-margin,-margin,margin,margin)
        overlay=QGraphicsRectItem(rect)
        pen=QPen(QColor(color)); pen.setCosmetic(True); pen.setWidthF(1.5); pen.setStyle(Qt.PenStyle.DashLine)
        overlay.setPen(pen); overlay.setBrush(QBrush(QColor(22,156,150,20)))
        overlay.setZValue(1420); overlay.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.scene.addItem(overlay); self.spot_link_overlays.append(overlay)

    def _refresh_spot_link_visuals(self, selected: core.Placement | None = None) -> None:
        self._clear_spot_link_visuals()
        if self.annotation_display_mode=="Skjult":
            return
        if selected is None:
            return
        parent=None
        spots=[]
        if selected.symbol=="spot":
            parent_uid=str(getattr(selected,"parent_light_uid","") or "")
            parent=self._placement_by_uid(parent_uid) if parent_uid else None
            if parent is not None:
                gid=str(getattr(selected,"spot_group_id","") or "")
                spots=self._spot_group_members(gid) if gid else self._linked_spots(parent.uid)
        elif selected.symbol=="light_connection":
            parent=selected
            spots=self._linked_spots(parent.uid)
        else:
            return
        if parent is None:
            return
        parent_item=self.symbol_items.get(parent.uid)
        if parent_item is None:
            return
        self._spot_link_highlight(parent_item)
        start=parent_item.sceneBoundingRect().center()
        for spot in spots:
            item=self.symbol_items.get(spot.uid)
            if item is None or not item.isVisible():
                continue
            self._spot_link_highlight(item)
            path=QPainterPath(start)
            path.lineTo(item.sceneBoundingRect().center())
            line=QGraphicsPathItem(path)
            pen=QPen(QColor(22,156,150,155)); pen.setCosmetic(True); pen.setWidthF(0.9); pen.setStyle(Qt.PenStyle.DotLine)
            line.setPen(pen); line.setZValue(1410); line.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self.scene.addItem(line); self.spot_link_paths.append(line)

    def _refresh_spot_parent_picker(self) -> None:
        self._clear_spot_link_visuals()
        for p in self.project.placements:
            if p.symbol!="light_connection":
                continue
            item=self.symbol_items.get(p.uid)
            if item is None or not item.isVisible():
                continue
            self._spot_link_highlight(item)

    def start_spot_parent_for_selection(self) -> None:
        spots=self._selected_spots(unlocked_only=True)
        expanded=self._expand_spots_to_groups(spots)
        if any(p.locked for p in expanded):
            QMessageBox.information(self,"Spot → lampested","En valgt spotgruppe indeholder låste spots. Lås dem op før hele gruppen tilknyttes.")
            return
        spots=expanded
        if not spots:
            self._set_status("Vælg først ét eller flere ulåste spots.")
            return
        self.spot_parent_pending=[p.uid for p in spots]
        self.association_source_uid=""
        self.association_active_letter=""
        self.association_pick_source=False
        self.association_guided_setup=False
        self.association_channel_index=0
        self._clear_association_visuals()
        self.view.cancel_tool(emit_signal=False)
        self.view.setCursor(Qt.CursorShape.CrossCursor)
        self._refresh_spot_parent_picker()
        self._set_status(
            f"Spot → lampested: {len(spots)} spot(s) valgt. Klik et TURKIS fremhævet lampested · Esc afslutter"
        )

    def unlink_selected_spots(self) -> None:
        spots=self._selected_spots(unlocked_only=True)
        expanded=self._expand_spots_to_groups(spots)
        if any(p.locked for p in expanded):
            QMessageBox.information(self,"Spot → lampested","En valgt spotgruppe indeholder låste spots. Lås dem op før hele gruppen frakobles.")
            return
        spots=expanded
        if not spots:return
        before=self._spot_parent_snapshot()
        for spot in spots:
            spot.parent_light_uid=""
            # A detached spot keeps no inherited light associations. It can still
            # be associated directly later if desired.
            spot.associations=[]
        after=self._spot_parent_snapshot()
        self.undo_stack.push(SpotParentCommand(self,before,after,"Frakobl spots fra lampested"))
        self._clear_spot_link_visuals()
        for ann in self.annotation_items.values():ann.refresh()
        self._selection_changed()

