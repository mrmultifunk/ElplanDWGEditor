from __future__ import annotations

"""Room sketching/overlay UI for the electrical plan workspace.

Rooms are project data, but their boundary is deliberately a quiet editing aid:
by default only the movable room label is visible. The polygon becomes visible
while room editing is active or when the user explicitly enables boundaries.
"""

from copy import deepcopy
from dataclasses import asdict

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QAction, QColor, QBrush, QFont, QIcon, QKeySequence, QPainter, QPainterPath, QPainterPathStroker, QPen, QPixmap, QUndoCommand
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox, QPushButton, QInputDialog,
    QSpinBox, QVBoxLayout, QGraphicsPathItem, QGraphicsSimpleTextItem, QGraphicsItem, QGraphicsEllipseItem,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QGroupBox, QGridLayout,
)

import core_logic as core
from elplan_catalog import user_library
from elplan_qt.qt_commands import EditCableCommand
from elplan_qt.qt_ui import configure_modern_dialog
from elplan_shared.interaction_math import room_axis_assist, room_wall_axis_snap, room_nearest_edge_insert


ROOM_COLOR_PALETTE = (
    ("Petrol", "#0f766e"),
    ("Turkis", "#14b8a6"),
    ("Blå", "#3b82f6"),
    ("Indigo", "#6366f1"),
    ("Lilla", "#8b5cf6"),
    ("Rosa", "#ec4899"),
    ("Orange", "#f97316"),
    ("Gylden", "#d4a017"),
    ("Grøn", "#22c55e"),
    ("Skifer", "#64748b"),
)


def _mapped_point(x: float, y: float) -> QPointF:
    return QPointF(float(x), -float(y))


def room_scene_rect(room: core.RoomPlacement) -> QRectF:
    pts=[_mapped_point(x,y) for x,y in (room.points or [])]
    if not pts:return QRectF()
    xs=[p.x() for p in pts]; ys=[p.y() for p in pts]
    return QRectF(min(xs),min(ys),max(xs)-min(xs),max(ys)-min(ys))


class RoomVertexHandle(QGraphicsEllipseItem):
    def __init__(self,boundary,index:int):
        super().__init__(-5,-5,10,10,boundary)
        self.boundary=boundary; self.index=int(index); self._before=None
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations,True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,False)
        self.setZValue(4); self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.refresh_style()

    def refresh_style(self):
        c=QColor(getattr(self.boundary.room,'color','#0f766e')); pen=QPen(c); pen.setCosmetic(True); pen.setWidthF(1.6); self.setPen(pen)
        fill=QColor('#ffffff'); fill.setAlpha(235); self.setBrush(QBrush(fill))

    def mousePressEvent(self,event):
        self._before=deepcopy(list(self.boundary.room.points or [])); self.boundary._clear_vertex_guides(); super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        super().mouseMoveEvent(event)
        free=bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
        pos,gx,gy=self.boundary._assisted_vertex_position(self.index,self.pos(),free_angle=free)
        if pos!=self.pos():self.setPos(pos)
        self.boundary._show_vertex_guides(pos,gx,gy); self.boundary._vertex_live_moved(self.index,pos)
    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event)
        free=bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
        pos,gx,gy=self.boundary._assisted_vertex_position(self.index,self.pos(),free_angle=free)
        if pos!=self.pos():self.setPos(pos)
        self.boundary._vertex_live_moved(self.index,pos); self.boundary._clear_vertex_guides()
        before=self._before; self._before=None
        after=deepcopy(list(self.boundary.room.points or []))
        if before is not None and before!=after and callable(self.boundary.vertex_callback):self.boundary.vertex_callback(self.boundary.room,before,after)


class RoomBoundaryItem(QGraphicsPathItem):
    def __init__(self, room, edit_callback, delete_callback, vertex_callback=None, mark_callback=None, boundary_edit_callback=None, wall_snap_callback=None):
        super().__init__()
        self.room=room; self.edit_callback=edit_callback; self.delete_callback=delete_callback; self.vertex_callback=vertex_callback; self.mark_callback=mark_callback; self.boundary_edit_callback=boundary_edit_callback; self.wall_snap_callback=wall_snap_callback
        self._handles=[]
        self._vertex_guides=QGraphicsPathItem(self); self._vertex_guides.setZValue(2); self._vertex_guides.hide()
        guide_pen=QPen(QColor('#67e8f9')); guide_pen.setCosmetic(True); guide_pen.setWidthF(1.3); guide_pen.setStyle(Qt.PenStyle.DotLine); self._vertex_guides.setPen(guide_pen); self._vertex_guides.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        self.setZValue(-80)
        self.setAcceptHoverEvents(True); self.setAcceptedMouseButtons(Qt.MouseButton.AllButtons)
        self._hover=False; self._edit_mode=False
        self.setToolTip('Dobbeltklik på rumkonturen for at redigere afgrænsningen · i redigering: dobbeltklik på en side for nyt knækpunkt')
        self.refresh_geometry(); self.refresh_style()

    def refresh_geometry(self):
        pts=list(self.room.points or [])
        path=QPainterPath()
        if pts:
            path.moveTo(_mapped_point(*pts[0]))
            for p in pts[1:]:path.lineTo(_mapped_point(*p))
            if len(pts)>=3:path.closeSubpath()
        self.setPath(path)
        self._sync_handles()

    def _vertex_live_moved(self,index,pos):
        pts=list(self.room.points or [])
        if not (0<=int(index)<len(pts)):return
        pts[int(index)]=(float(pos.x()),float(-pos.y())); self.room.points=pts
        path=QPainterPath()
        if pts:
            path.moveTo(_mapped_point(*pts[0]))
            for p in pts[1:]:path.lineTo(_mapped_point(*p))
            if len(pts)>=3:path.closeSubpath()
        self.setPath(path)

    def _view_scale(self):
        try:
            views=self.scene().views() if self.scene() is not None else []
            if views:return max(abs(float(views[0].transform().m11())),1e-9)
        except Exception:pass
        return 1.0

    def shape(self):
        # The translucent room fill is visual only.  Hit-testing stays on a
        # narrow outline so a visible room never blocks symbols/cables inside it.
        stroker=QPainterPathStroker(); stroker.setWidth(max(2.0,10.0/self._view_scale()))
        return stroker.createStroke(self.path())

    def _assisted_vertex_position(self,index,pos,free_angle=False):
        pts=list(self.room.points or []); i=int(index)
        if len(pts)<2 or not (0<=i<len(pts)):
            return QPointF(pos),None,None
        # CAD-væggen er det fysiske snapmål, men callbacken kombinerer den med
        # 0/90°-hjælp når væg/akse-krydset ligger tæt på cursoren. Alt beholder
        # væg-snap, men slår kun selve ortho-hjælpen fra.
        if callable(self.wall_snap_callback):
            snapped=self.wall_snap_callback(self.room,i,QPointF(pos),bool(free_angle))
            if snapped is not None:
                return snapped
        if free_angle:
            return QPointF(pos),None,None
        neighbours=[]
        for j in {(i-1)%len(pts),(i+1)%len(pts)}:
            neighbours.append(_mapped_point(*pts[j]))
        tol=12.0/self._view_scale()
        x,y,gx,gy,_label=room_axis_assist(float(pos.x()),float(pos.y()),[(p.x(),p.y()) for p in neighbours],tol,disabled=False)
        return QPointF(x,y),gx,gy

    def _show_vertex_guides(self,pos,gx,gy):
        if gx is None and gy is None:
            self._clear_vertex_guides(); return
        pts=[_mapped_point(*p) for p in (self.room.points or [])]; ext=24.0/self._view_scale(); path=QPainterPath()
        if gy is not None:
            xs=[p.x() for p in pts]+[float(pos.x())]; path.moveTo(min(xs)-ext,float(gy)); path.lineTo(max(xs)+ext,float(gy))
        if gx is not None:
            ys=[p.y() for p in pts]+[float(pos.y())]; path.moveTo(float(gx),min(ys)-ext); path.lineTo(float(gx),max(ys)+ext)
        self._vertex_guides.setPath(path); self._vertex_guides.show()

    def _clear_vertex_guides(self):
        self._vertex_guides.hide(); self._vertex_guides.setPath(QPainterPath())

    def _sync_handles(self):
        need=bool(self._edit_mode and self.isSelected())
        if not need:
            for h in self._handles:h.hide()
            return
        while len(self._handles)<len(self.room.points):self._handles.append(RoomVertexHandle(self,len(self._handles)))
        for i,h in enumerate(self._handles):
            if i<len(self.room.points):h.index=i; h.setPos(_mapped_point(*self.room.points[i])); h.show()
            else:h.hide()

    def _insert_vertex_at_scene_pos(self,scene_pos):
        before=deepcopy(list(self.room.points or []))
        hit=room_nearest_edge_insert(before,float(scene_pos.x()),float(scene_pos.y()))
        if hit is None:return False
        insert_index,cad_point=hit
        after=deepcopy(before); after.insert(int(insert_index),(float(cad_point[0]),float(cad_point[1])))
        if after==before:return False
        self.room.points=after; self.refresh_geometry(); self.setSelected(True); self._sync_handles()
        if callable(self.vertex_callback):self.vertex_callback(self.room,before,deepcopy(after))
        return True

    def set_edit_mode(self, enabled: bool):
        self._edit_mode=bool(enabled)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,self._edit_mode)
        if not self._edit_mode:self._clear_vertex_guides()
        self.refresh_style(); self._sync_handles()

    def refresh_style(self):
        c=QColor(getattr(self.room,'color','#0f766e'))
        pen=QPen(c); pen.setCosmetic(True); pen.setStyle(Qt.PenStyle.DashLine)
        pen.setWidthF(2.2 if (self._hover or self.isSelected()) else 1.3)
        self.setPen(pen)
        fill=QColor(c); fill.setAlpha(30 if self._edit_mode else 12)
        self.setBrush(QBrush(fill))
        for handle in self._handles:
            handle.refresh_style()

    def hoverEnterEvent(self,event):
        self._hover=True; self.refresh_style(); super().hoverEnterEvent(event)
    def hoverLeaveEvent(self,event):
        self._hover=False; self.refresh_style(); super().hoverLeaveEvent(event)
    def itemChange(self,change,value):
        out=super().itemChange(change,value)
        if change==QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:self.refresh_style(); self._sync_handles()
        return out
    def mouseDoubleClickEvent(self,event):
        # First double-click enters boundary editing. Once selected in edit mode,
        # double-clicking the outline adds a new draggable breakpoint.
        if self._edit_mode and self.isSelected():
            if self._insert_vertex_at_scene_pos(self.mapToScene(event.pos())):
                event.accept(); return
        if callable(self.boundary_edit_callback):self.boundary_edit_callback(self.room)
        elif self._edit_mode:self.setSelected(True); self._sync_handles()
        event.accept()
    def contextMenuEvent(self,event):
        menu=QMenu(); boundary=menu.addAction('Redigér afgrænsning'); add_vertex=menu.addAction('Tilføj knækpunkt her'); edit=menu.addAction('Rumdata / farve…'); mark=menu.addAction('Mærk kabler efter rum…'); menu.addSeparator(); delete=menu.addAction('Slet rum')
        chosen=menu.exec(event.screenPos())
        if chosen is boundary:
            if callable(self.boundary_edit_callback):self.boundary_edit_callback(self.room)
            else:self.setSelected(True); self._sync_handles()
        elif chosen is add_vertex:
            if not self._edit_mode and callable(self.boundary_edit_callback):self.boundary_edit_callback(self.room)
            self.setSelected(True); self._insert_vertex_at_scene_pos(event.scenePos())
        elif chosen is edit and callable(self.edit_callback):self.edit_callback(self.room)
        elif chosen is mark and callable(self.mark_callback):self.mark_callback(self.room)
        elif chosen is delete and callable(self.delete_callback):self.delete_callback(self.room)
        event.accept()


class RoomLabelItem(QGraphicsSimpleTextItem):
    def __init__(self, room, moved_callback, edit_callback, delete_callback, mark_callback=None, boundary_edit_callback=None, boundary_item=None, dashboard_callback=None):
        super().__init__()
        self.room=room; self.moved_callback=moved_callback; self.edit_callback=edit_callback; self.delete_callback=delete_callback; self.mark_callback=mark_callback; self.boundary_edit_callback=boundary_edit_callback; self.boundary_item=boundary_item; self.dashboard_callback=dashboard_callback
        self._press_pos=None
        self._show_code=False
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations,True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,True)
        self.setZValue(420)
        self.setAcceptHoverEvents(True)
        self.refresh()

    def set_show_code(self,show: bool):
        show=bool(show)
        if self._show_code==show:return
        self._show_code=show
        self.refresh()

    def refresh(self):
        name=str(getattr(self.room,'name','') or '').strip()
        code=str(getattr(self.room,'code','') or '').strip()
        if self._show_code and code:
            label=f"{code} · {name}" if name else code
        else:
            label=name or "Rum"
        self.setText(label)
        f=QFont('Segoe UI',9,QFont.Weight.DemiBold); self.setFont(f)
        self.setBrush(QBrush(QColor(getattr(self.room,'color','#0f766e'))))
        self.setToolTip(f"Rum: {getattr(self.room,'name','')}\nMærkning: {getattr(self.room,'code','') or '—'}\nTræk teksten for at flytte den\nNår omridset er skjult: dobbeltklik på teksten for at redigere afgrænsningen")
        self.setPos(_mapped_point(self.room.label_x,self.room.label_y))

    def mousePressEvent(self,event):
        self._press_pos=QPointF(self.pos()); super().mousePressEvent(event)
    def mouseReleaseEvent(self,event):
        before=self._press_pos; super().mouseReleaseEvent(event)
        after=QPointF(self.pos())
        if before is not None and before!=after and callable(self.moved_callback):
            self.moved_callback(self.room,(float(before.x()),float(-before.y())),(float(after.x()),float(-after.y())))
        self._press_pos=None
    def mouseDoubleClickEvent(self,event):
        boundary_visible=bool(self.boundary_item is not None and self.boundary_item.isVisible())
        if not boundary_visible and callable(self.boundary_edit_callback):
            self.boundary_edit_callback(self.room)
        elif callable(self.edit_callback):
            self.edit_callback(self.room)
        event.accept()
    def contextMenuEvent(self,event):
        menu=QMenu()
        dashboard=menu.addAction('Rum-dashboard…')
        boundary_edit=menu.addAction('Redigér afgrænsning')
        edit=menu.addAction('Rumdata / farve…')
        mark=menu.addAction('Mærk kabler efter rum…')
        menu.addSeparator(); delete=menu.addAction('Slet rum')
        chosen=menu.exec(event.screenPos())
        if chosen is dashboard and callable(self.dashboard_callback):self.dashboard_callback(self.room)
        elif chosen is boundary_edit and callable(self.boundary_edit_callback):self.boundary_edit_callback(self.room)
        elif chosen is edit and callable(self.edit_callback):self.edit_callback(self.room)
        elif chosen is mark and callable(self.mark_callback):self.mark_callback(self.room)
        elif chosen is delete and callable(self.delete_callback):self.delete_callback(self.room)
        event.accept()


class RoomEditDialog(QDialog):
    def __init__(self,parent,room=None,default_code='',default_color='#0f766e'):
        super().__init__(parent); configure_modern_dialog(self, title='Rum', size=(540,330))
        root=QVBoxLayout(self); root.setContentsMargins(18,16,18,16); root.setSpacing(10)
        intro=QLabel('Navnet vises på plantegningen. Mærkningen er valgfri og kan bruges som kort rum-id ved kabelmærkning og rapporter.')
        intro.setWordWrap(True); root.addWidget(intro)
        form=QFormLayout(); self.name=QLineEdit(str(getattr(room,'name','') or '')); self.name.setPlaceholderText('fx Køkken')
        self.code=QLineEdit(str(getattr(room,'code','') or default_code)); self.code.setPlaceholderText('fx R01 eller KØK')
        form.addRow('Rumnavn',self.name); form.addRow('Mærkning',self.code); root.addLayout(form)

        color_label=QLabel('Farvenuance'); color_label.setStyleSheet('font-weight:600;') ; root.addWidget(color_label)
        color_hint=QLabel('Nuancen bruges diskret til rumtekst, omrids og redigeringshåndtag. Den påvirker ikke lag, kabler eller snap.')
        color_hint.setWordWrap(True); color_hint.setObjectName('mutedText'); root.addWidget(color_hint)
        self._color_buttons=[]; self._selected_color=str(getattr(room,'color','') or default_color or ROOM_COLOR_PALETTE[0][1])
        swatches=QHBoxLayout(); swatches.setSpacing(7)
        for name,value in ROOM_COLOR_PALETTE:
            b=QPushButton('✓' if value.lower()==self._selected_color.lower() else '')
            b.setFixedSize(30,30); b.setCheckable(True); b.setChecked(value.lower()==self._selected_color.lower())
            b.setToolTip(name); b.setAccessibleName(f'Rumfarve: {name}')
            b.setStyleSheet(self._swatch_style(value,b.isChecked()))
            b.clicked.connect(lambda checked=False,v=value:self._select_color(v))
            swatches.addWidget(b); self._color_buttons.append((b,value))
        swatches.addStretch(1); root.addLayout(swatches)
        self.color_preview=QLabel(); self.color_preview.setObjectName('mutedText'); root.addWidget(self.color_preview); self._refresh_color_preview()

        hint=QLabel('Rumteksten kan flyttes frit på plantegningen efter oprettelse.'); hint.setObjectName('mutedText'); root.addWidget(hint)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self.name.setFocus()

    @staticmethod
    def _swatch_style(value,selected):
        border='3px solid #f8fafc' if selected else '1px solid #64748b'
        return f'QPushButton{{background:{value}; border:{border}; border-radius:8px; color:white; font-weight:800;}} QPushButton:hover{{border:2px solid #e2e8f0;}}'

    def _select_color(self,value):
        self._selected_color=str(value)
        for button,color in self._color_buttons:
            selected=color.lower()==self._selected_color.lower(); button.blockSignals(True); button.setChecked(selected); button.setText('✓' if selected else ''); button.setStyleSheet(self._swatch_style(color,selected)); button.blockSignals(False)
        self._refresh_color_preview()

    def _refresh_color_preview(self):
        name=next((n for n,v in ROOM_COLOR_PALETTE if v.lower()==self._selected_color.lower()),'Egen nuance')
        self.color_preview.setText(f'Valgt: {name}')
        self.color_preview.setStyleSheet(f'color:{self._selected_color}; font-weight:700;')

    def selected_color(self):return str(self._selected_color or ROOM_COLOR_PALETTE[0][1])

    def accept(self):
        if not self.name.text().strip():
            QMessageBox.information(self,'Rum','Angiv et rumnavn.'); return
        super().accept()


class RoomCableMarkDialog(QDialog):
    """Preview og sikker anvendelse af rum-baseret *ekstra* kabelmærkning."""
    def __init__(self,parent,cables,rooms,room_filter=None):
        super().__init__(parent); self.cables=list(cables or []); self.rooms=list(rooms or []); self.room_filter=room_filter
        configure_modern_dialog(self, title='Mærk kabler efter rum', size=(760,540))
        root=QVBoxLayout(self); root.setContentsMargins(18,16,18,16); root.setSpacing(10)
        scope=core.room_display_text(room_filter) if room_filter is not None else 'Alle definerede rum'
        title=QLabel(f'Kabelmærkning · {scope}'); title.setStyleSheet('font-weight:700; font-size:15px;'); root.addWidget(title)
        info=QLabel('Programmet følger hvert fysisk kabel gennem de skitserede rum og foreslår kun feltet Ekstra mærkning. Kabel-ID og gruppe/kreds ændres aldrig.')
        info.setWordWrap(True); root.addWidget(info)
        form=QFormLayout()
        self.style=QComboBox(); self.style.addItem('Rumnavne  ·  Køkken → Gang → Stue','name'); self.style.addItem('Rummærkninger  ·  R01 → R02 → R03','code'); self.style.addItem('Mærkning + navn  ·  R01 · Køkken → R02 · Gang','display')
        form.addRow('Format',self.style); root.addLayout(form)
        self.overwrite=QCheckBox('Overskriv eksisterende ekstra kabelmærkning'); self.overwrite.setChecked(False); root.addWidget(self.overwrite)
        self.summary=QLabel(); self.summary.setObjectName('mutedText'); root.addWidget(self.summary)
        self.preview=QListWidget(); self.preview.setAlternatingRowColors(True); root.addWidget(self.preview,1)
        hint=QLabel('Tip: Et kabel helt i ét rum får ét rumnavn. Krydses flere rum, vises de i kabelrutens rækkefølge med →. Kabler uden for definerede rum ændres ikke.')
        hint.setWordWrap(True); hint.setObjectName('mutedText'); root.addWidget(hint)
        self.style.currentIndexChanged.connect(self._refresh); self.overwrite.toggled.connect(self._refresh); self._refresh()
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def style_id(self):return str(self.style.currentData() or 'name')
    def marking_for(self,cable):return core.cable_room_marking(cable,self.rooms,self.style_id())
    def _refresh(self,*_):
        self.preview.clear(); applicable=0; protected=0
        for cable in self.cables:
            proposed=self.marking_for(cable)
            if not proposed:continue
            current=str(getattr(cable,'label','') or '').strip(); cid=str(getattr(cable,'cable_id','') or 'Kabel')
            circuit=str(getattr(cable,'circuit_id','') or '—')
            if current and not self.overwrite.isChecked():
                text=f'{cid}  ·  {circuit}    {current}   [beholdes]' ; protected+=1
            else:
                text=f'{cid}  ·  {circuit}    {current or "—"}  →  {proposed}' ; applicable+=1
            self.preview.addItem(text)
        self.summary.setText(f'{applicable} kabelmærkninger kan opdateres' + (f' · {protected} eksisterende mærkninger beskyttes' if protected else ''))


class AddRoomCommand(QUndoCommand):
    def __init__(self,window,room):super().__init__('Tegn rum'); self.window=window; self.room=room
    def redo(self):self.window._add_room(self.room)
    def undo(self):self.window._remove_room(self.room.uid)
class DeleteRoomCommand(QUndoCommand):
    def __init__(self,window,room,index):super().__init__('Slet rum'); self.window=window; self.room=room; self.index=index
    def redo(self):self.window._remove_room(self.room.uid)
    def undo(self):self.window._add_room(self.room,self.index)
class EditRoomCommand(QUndoCommand):
    def __init__(self,window,uid,before,after,text='Redigér rum',already_applied=False):
        super().__init__(text); self.window=window; self.uid=uid; self.before=deepcopy(before); self.after=deepcopy(after); self.skip=already_applied
    def redo(self):
        if self.skip:self.skip=False; return
        self.window._apply_room_state(self.uid,self.after)
    def undo(self):self.window._apply_room_state(self.uid,self.before)



class PlacementBomRoomsDialog(QDialog):
    """Vælg additive ekstra BOM-rum for ét fysisk symbol."""
    def __init__(self,parent,placement,rooms,current_room_uids):
        super().__init__(parent); self.placement=placement; self.rooms=list(rooms or [])
        configure_modern_dialog(self,title='Ekstra BOM-rum',size=(560,500))
        root=QVBoxLayout(self); root.setContentsMargins(18,16,18,16); root.setSpacing(9)
        physical=core.room_for_point(self.rooms,float(getattr(placement,'x',0.0)),float(getattr(placement,'y',0.0))) if self.rooms else None
        physical_text=core.room_display_text(physical) if physical is not None else 'Uden rum'
        title=QLabel(f"{core.symbol_display_name(str(getattr(placement,'symbol','') or ''))} · fysisk rum: {physical_text}")
        title.setStyleSheet('font-weight:700; font-size:14px;'); root.addWidget(title)
        info=QLabel('Vælg ét eller flere ekstra rum som dette symbol også skal tælle med i. Den fysiske placering, gruppe/kreds og den samlede Alle rum-BOM ændres ikke.')
        info.setWordWrap(True); root.addWidget(info)
        self.list=QListWidget(); root.addWidget(self.list,1)
        current=set(str(x) for x in (current_room_uids or [])); physical_uid=str(getattr(physical,'uid','') or '') if physical is not None else ''
        for room in sorted(self.rooms,key=lambda r:core.room_display_text(r).casefold()):
            uid=str(getattr(room,'uid','') or '')
            if uid==physical_uid:continue
            item=QListWidgetItem(core.room_display_text(room)); item.setData(Qt.ItemDataRole.UserRole,uid)
            item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable); item.setCheckState(Qt.CheckState.Checked if uid in current else Qt.CheckState.Unchecked)
            self.list.addItem(item)
        if self.list.count()==0:
            item=QListWidgetItem('Ingen andre definerede rum'); item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled); self.list.addItem(item)
        hint=QLabel('Eksempel: køleskab fysisk i Gang + ekstra BOM-rum Køkken → artiklen vises i begge rum-BOM’er, men kun én gang i Alle rum.')
        hint.setWordWrap(True); hint.setObjectName('mutedText'); root.addWidget(hint)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)
    def selected_room_uids(self):
        out=[]
        for i in range(self.list.count()):
            item=self.list.item(i); uid=str(item.data(Qt.ItemDataRole.UserRole) or '')
            if uid and item.checkState()==Qt.CheckState.Checked:out.append(uid)
        return out


class RoomDashboardDialog(QDialog):
    def __init__(self,window,room):
        super().__init__(window); self.window=window; self.room=room
        configure_modern_dialog(self,title=f"Rum-dashboard · {core.room_display_text(room)}",size=(900,650))
        root=QVBoxLayout(self); root.setContentsMargins(18,16,18,16); root.setSpacing(10)
        title=QLabel(core.room_display_text(room)); title.setStyleSheet('font-weight:700; font-size:17px;'); root.addWidget(title)
        self.summary=QLabel(); self.summary.setWordWrap(True); self.summary.setObjectName('accentText'); root.addWidget(self.summary)
        self.groups=QLabel(); self.groups.setWordWrap(True); self.groups.setObjectName('mutedText'); root.addWidget(self.groups)
        stats=QGroupBox('Overblik'); grid=QGridLayout(stats); self.stat_labels={}
        labels=(('switches','Afbrydere'),('sockets','Stikkontakter'),('light_connections','Lampesteder'),('spots','Spots'),('physical_symbols','Fysiske symboler'),('extra_bom_symbols','Ekstra BOM-symboler'))
        for idx,(key,caption) in enumerate(labels):
            box=QLabel(); box.setAlignment(Qt.AlignmentFlag.AlignCenter); box.setStyleSheet('font-weight:700; font-size:15px; padding:8px;')
            grid.addWidget(QLabel(caption),0 if idx<3 else 2,idx%3); grid.addWidget(box,1 if idx<3 else 3,idx%3); self.stat_labels[key]=box
        root.addWidget(stats)
        bom_title=QLabel('BOM for rummet'); bom_title.setStyleSheet('font-weight:700;'); root.addWidget(bom_title)
        self.bom=QTableWidget(0,5); self.bom.setHorizontalHeaderLabels(['Artikel','Beskrivelse','Fabrikat','Antal','Enhed']); self.bom.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers); self.bom.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows); self.bom.horizontalHeader().setStretchLastSection(True); self.bom.setColumnWidth(0,130); self.bom.setColumnWidth(1,360); self.bom.setColumnWidth(2,160); self.bom.setColumnWidth(3,90); root.addWidget(self.bom,1)
        row=QHBoxLayout(); focus=QPushButton('Vis kun dette rum'); focus.clicked.connect(self._focus); row.addWidget(focus)
        zoom=QPushButton('Zoom til rum'); zoom.clicked.connect(lambda:self.window.zoom_to_room(self.room)); row.addWidget(zoom)
        bom=QPushButton('Åbn rum-BOM…'); bom.clicked.connect(self._open_bom); row.addWidget(bom)
        edit=QPushButton('Redigér rum…'); edit.clicked.connect(self._edit); row.addWidget(edit); row.addStretch(1); root.addLayout(row)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close); buttons.rejected.connect(self.reject); buttons.accepted.connect(self.accept); root.addWidget(buttons)
        self.refresh()
    def refresh(self):
        data=self.window._room_dashboard_data(self.room)
        for key,label in self.stat_labels.items():label.setText(str(data.get(key,0)))
        cable_text=data.get('cable_length_text','—')
        self.summary.setText(f"{data.get('physical_symbols',0)} fysiske symboler · {data.get('extra_bom_symbols',0)} ekstra BOM-symboler · {data.get('cable_count',0)} kabler · {cable_text}")
        groups=data.get('groups',[]); self.groups.setText('Grupper/kredse: '+(', '.join(groups) if groups else '—'))
        rows=data.get('bom_rows',[]); self.bom.setRowCount(len(rows))
        for r,row in enumerate(rows):
            values=[row.get('article_no',''),row.get('description',''),row.get('manufacturer',''),self.window._fmt_qty(row.get('qty',0)) if hasattr(self.window,'_fmt_qty') else str(row.get('qty',0)),row.get('unit','')]
            for c,value in enumerate(values):self.bom.setItem(r,c,QTableWidgetItem(str(value)))
    def _focus(self):
        self.window.focus_room(self.room.uid); self.accept()
    def _open_bom(self):
        self.accept(); self.window.open_bom_manager_for_room(self.room.uid)
    def _edit(self):
        self.window.edit_room(self.room); self.refresh()


class RoomManagerDialog(QDialog):
    def __init__(self,parent):
        super().__init__(parent); self.window=parent; configure_modern_dialog(self, title='Rum', size=(620,520))
        root=QVBoxLayout(self); root.setContentsMargins(16,14,16,14); root.setSpacing(8)
        info=QLabel('Rum bruges som et stille logisk lag oven på plantegningen. Rumtekster og afgrænsninger kan vises uafhængigt; afgrænsninger vises midlertidigt i redigeringstilstand.')
        info.setWordWrap(True); root.addWidget(info)
        self.list=QListWidget(); root.addWidget(self.list,1)
        row=QHBoxLayout();
        for text,handler in [('Dashboard',self._dashboard),('Zoom til',self._zoom),('Redigér afgrænsning',self._boundary),('Rumdata / farve…',self._edit),('Mærk kabler…',self._mark),('Slet',self._delete)]:
            b=QPushButton(text); b.clicked.connect(handler); row.addWidget(b)
        root.addLayout(row)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close); buttons.rejected.connect(self.reject); buttons.accepted.connect(self.accept); root.addWidget(buttons)
        self._refresh(); self.list.itemDoubleClicked.connect(lambda _item:self._edit())
    def _selected(self):
        item=self.list.currentItem(); uid=str(item.data(Qt.ItemDataRole.UserRole) or '') if item else ''
        return next((r for r in self.window.project.rooms if r.uid==uid),None)
    def _refresh(self):
        self.list.clear()
        for room in self.window.project.rooms:
            symbols=len(self.window._placements_in_room(room)); cables=len(self.window._cables_in_room(room)); item=QListWidgetItem(f"{core.room_display_text(room)}    ·    {symbols} symboler · {cables} kabler")
            pix=QPixmap(12,12); pix.fill(QColor(getattr(room,'color','#14b8a6'))); item.setIcon(QIcon(pix))
            item.setData(Qt.ItemDataRole.UserRole,room.uid); self.list.addItem(item)
    def _dashboard(self):
        room=self._selected()
        if room:self.accept(); self.window.open_room_dashboard(room)
    def _zoom(self):
        room=self._selected();
        if room:self.window.zoom_to_room(room)
    def _boundary(self):
        room=self._selected()
        if room:
            # Dialogen er modal; luk den før scene-håndtagene aktiveres.
            self.accept(); self.window.edit_room_boundary(room,zoom=True)
    def _edit(self):
        room=self._selected();
        if room:self.window.edit_room(room); self._refresh()
    def _mark(self):
        room=self._selected();
        if room:self.window.mark_cables_by_rooms(room); self._refresh()
    def _delete(self):
        room=self._selected();
        if room:self.window.delete_room(room); self._refresh()


class RoomUiMixin:
    def _create_room_actions(self):
        self.act_room_draw=QAction("Rum",self); self.act_room_draw.setShortcut(QKeySequence("Ctrl+Shift+R")); self.act_room_draw.setToolTip("Skitser et rum som polygon oven på plantegningen. Enter/dobbeltklik afslutter."); self.act_room_draw.triggered.connect(self.start_room_sketch)
        self.act_room_edit=QAction("Redigér rumafgrænsninger",self,checkable=True); self.act_room_edit.setToolTip("Vis rumafgrænsninger og gør polygonernes hjørnepunkter redigerbare. Vælg et rum eller højreklik på rumteksten."); self.act_room_edit.toggled.connect(self._room_edit_toggled)
        self.act_room_labels=QAction("Vis rumnavne",self,checkable=True); self.act_room_labels.setChecked(bool(self.project.raw.get("room_labels_visible",True))); self.act_room_labels.setToolTip("Vis eller skjul rummenes navne. Påvirker ikke rumafgrænsningerne eller rummets gemte mærkning."); self.act_room_labels.toggled.connect(self._room_labels_toggled)
        self.act_room_codes=QAction("Vis rummærkning",self,checkable=True); self.act_room_codes.setChecked(bool(self.project.raw.get("room_codes_visible",False))); self.act_room_codes.setToolTip("Vis rummets korte mærkning/ID foran navnet, fx R01 · Køkken. Når den er skjult, bevares mærkningen stadig i projektdata, BOM, rapporter og kabelmærkning."); self.act_room_codes.toggled.connect(self._room_codes_toggled)
        self.act_room_boundaries=QAction("Vis rumafgrænsninger",self,checkable=True); self.act_room_boundaries.setChecked(bool(self.project.raw.get("room_boundaries_visible",False))); self.act_room_boundaries.setToolTip("Vis eller skjul rummenes polygoner. Rumnavnene forbliver synlige. Skjuler du afgrænsninger under rumredigering, afsluttes redigeringstilstanden samtidig."); self.act_room_boundaries.toggled.connect(self._room_boundaries_toggled)
        self.act_room_cable_mark=QAction("Mærk kabler efter rum…",self); self.act_room_cable_mark.setToolTip("Foreslå ekstra kabelmærkning ud fra hvilke rum hvert fysisk kabel går igennem. Gruppe/kreds ændres ikke."); self.act_room_cable_mark.triggered.connect(lambda:self.mark_cables_by_rooms())
        self.act_room_dashboard=QAction("Rum-dashboard…",self); self.act_room_dashboard.setToolTip("Se installation, grupper, kabler og rum-BOM for ét rum."); self.act_room_dashboard.triggered.connect(lambda:self.open_room_dashboard())
        self.act_room_focus_clear=QAction("Afslut rumfokus",self); self.act_room_focus_clear.setEnabled(False); self.act_room_focus_clear.triggered.connect(lambda:self.focus_room(""))
        self.act_room_manager=QAction("Rumoversigt…",self); self.act_room_manager.setToolTip("Se, redigér og zoom til rum samt mærk kabler ud fra rumforløb."); self.act_room_manager.triggered.connect(self.open_room_manager)

    def _add_room_tools_menu(self,tools_menu):
        menu=tools_menu.addMenu("Rum"); menu.addAction(self.act_room_draw); menu.addAction(self.act_room_edit); menu.addSeparator(); menu.addAction(self.act_room_labels); menu.addAction(self.act_room_codes); menu.addAction(self.act_room_boundaries); menu.addSeparator(); menu.addAction(self.act_room_dashboard); menu.addAction(self.act_room_cable_mark); menu.addAction(self.act_room_manager); menu.addAction(self.act_room_focus_clear)

    def _selected_rooms_from_scene(self):
        rooms=[]; seen=set()
        for item in self.scene.selectedItems():
            if not isinstance(item,(RoomBoundaryItem,RoomLabelItem)):continue
            room=getattr(item,"room",None)
            if room is not None and room.uid not in seen:seen.add(room.uid); rooms.append(room)
        return rooms

    def _show_room_selection_inspector(self,rooms,selected_symbols,selected_cables):
        if len(rooms)!=1 or selected_symbols or selected_cables:return False
        room=rooms[0]; count=len(self._placements_in_room(room)); cable_count=len(self._cables_in_room(room)); self.prop_title.setText(core.room_display_text(room))
        if hasattr(self,"prop_hint"):self.prop_hint.setText("Rumtekst kan trækkes frit. Højreklik på teksten → Redigér afgrænsning for at flytte polygonens hjørner.")
        self.prop_assoc.setText(f"Rum · {count} symboler · {cable_count} kabler"); self.combo_group.hide(); self._enable_properties(False)
        self._show_inspector_page("properties",title=core.room_display_text(room),hint=f"{count} symboler · {cable_count} kabler · højreklik på rumteksten for polygonredigering."); self._update_inspector_summary(); self._refresh_context_toolbar(); return True

    def _init_room_ui_state(self):
        self.room_boundary_items={}; self.room_label_items={}; self.room_edit_mode=False; self._focus_room_id=""

    def _room_project_changed(self):
        self.room_edit_mode=False; self._focus_room_id=""
        if hasattr(self,"act_room_focus_clear"):
            self.act_room_focus_clear.setEnabled(False); self.act_room_focus_clear.setText("Afslut rumfokus")
        if hasattr(self,"act_room_edit"):
            self.act_room_edit.blockSignals(True); self.act_room_edit.setChecked(False); self.act_room_edit.blockSignals(False)
        if hasattr(self,"act_room_labels"):
            self.act_room_labels.blockSignals(True); self.act_room_labels.setChecked(bool(self.project.raw.get('room_labels_visible',True))); self.act_room_labels.blockSignals(False)
        if hasattr(self,"act_room_codes"):
            self.act_room_codes.blockSignals(True); self.act_room_codes.setChecked(bool(self.project.raw.get('room_codes_visible',False))); self.act_room_codes.blockSignals(False)
        if hasattr(self,"act_room_boundaries"):
            self.act_room_boundaries.blockSignals(True); self.act_room_boundaries.setChecked(bool(self.project.raw.get('room_boundaries_visible',False))); self.act_room_boundaries.blockSignals(False)

    def _rebuild_room_graphics(self):
        for room in self.project.rooms:self._create_room_graphics(room)

    def _next_room_code(self):
        used={str(getattr(r,'code','') or '').upper() for r in self.project.rooms}
        n=1
        while f'R{n:02d}' in used:n+=1
        return f'R{n:02d}'

    def _next_room_color(self):
        # Cycle through calm but distinguishable nuances; the user can always
        # choose another one in the room dialog. Existing rooms keep their color.
        return ROOM_COLOR_PALETTE[len(self.project.rooms)%len(ROOM_COLOR_PALETTE)][1]

    def start_room_sketch(self):
        self._stop_cable_marking_for_other_tool()
        # Tegneværktøjets egen preview viser den nye polygon. Vi aktiverer ikke
        # den persistente Rumredigering, så færdige omrids straks kan forblive skjult.
        self.view.start_room_tool()
        self._set_status('Tegn rum: klik langs afgrænsningen · vandret/lodret hjælpes automatisk · Alt = fri/skrå linje · Enter/dobbeltklik afslutter · Backspace fortryder punkt')

    def _room_sketch_finished(self,points):
        pts=[(float(x),float(y)) for x,y in (points or [])]
        if len(pts)<3:return
        dlg=RoomEditDialog(self,None,self._next_room_code(),self._next_room_color())
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        cx,cy=core.room_polygon_centroid(pts)
        room=core.RoomPlacement(name=dlg.name.text().strip(),code=dlg.code.text().strip(),points=pts,label_x=cx,label_y=cy,color=dlg.selected_color())
        self.undo_stack.push(AddRoomCommand(self,room)); self._set_status(f"Rum oprettet: {core.room_display_text(room)} · flyt teksten ved at trække den")

    def _create_room_graphics(self,room):
        boundary=RoomBoundaryItem(room,self.edit_room,self.delete_room,self._room_vertices_moved,self.mark_cables_by_rooms,self.edit_room_boundary,self._room_vertex_wall_snap); label=RoomLabelItem(room,self._room_label_moved,self.edit_room,self.delete_room,self.mark_cables_by_rooms,self.edit_room_boundary,boundary,self.open_room_dashboard)
        self.scene.addItem(boundary); self.scene.addItem(label)
        self.room_boundary_items[room.uid]=boundary; self.room_label_items[room.uid]=label
        self.generated_layer_items[core.ROOM_LAYER].extend([boundary,label]); self._refresh_room_visibility()

    def _add_room(self,room,index=None):
        if any(r.uid==room.uid for r in self.project.rooms):return
        if index is None or index<0 or index>len(self.project.rooms):self.project.rooms.append(room)
        else:self.project.rooms.insert(index,room)
        self._create_room_graphics(room); self.project.dirty=True; self._update_title(); self._rebuild_layer_list()

    def _remove_room(self,uid):
        self.project.rooms=[r for r in self.project.rooms if r.uid!=uid]
        for mapping in (self.room_boundary_items,self.room_label_items):
            item=mapping.pop(uid,None)
            if item is not None and item.scene() is not None:self.scene.removeItem(item)
        self.generated_layer_items[core.ROOM_LAYER]=[x for x in self.generated_layer_items.get(core.ROOM_LAYER,[]) if getattr(getattr(x,'room',None),'uid','')!=uid]
        additions=core.normalize_placement_bom_room_additions(self.project.raw.get('placement_bom_room_additions',{}))
        cleaned={puid:[ruid for ruid in rids if ruid!=uid] for puid,rids in additions.items()}
        self.project.raw['placement_bom_room_additions']={puid:rids for puid,rids in cleaned.items() if rids}
        if str(getattr(self,'_focus_room_id','') or '')==str(uid):self.focus_room('')
        self.project.dirty=True; self._update_title(); self._rebuild_layer_list()

    def _apply_room_state(self,uid,state):
        room=next((r for r in self.project.rooms if r.uid==uid),None)
        if room is None:return
        for key,value in state.items():
            if hasattr(room,key):setattr(room,key,deepcopy(value))
        b=self.room_boundary_items.get(uid); l=self.room_label_items.get(uid)
        if b:b.refresh_geometry(); b.refresh_style()
        if l:l.refresh()
        self.project.dirty=True; self._update_title(); self._refresh_room_visibility()

    def _room_label_moved(self,room,before,after):
        if before==after:return
        room.label_x,room.label_y=after; self.project.dirty=True; self._update_title()
        self.undo_stack.push(EditRoomCommand(self,room.uid,{"label_x":before[0],"label_y":before[1]},{"label_x":after[0],"label_y":after[1]},'Flyt rumtekst',already_applied=True))

    def _room_vertex_wall_snap(self,room,index,scene_pos,free_angle=False):
        """Snap an edited room vertex to real CAD walls, optionally with ortho.

        EL-RUM is never part of the snap engine, so this can only target the
        underlying plan geometry. The return coordinates are scene coordinates.
        """
        engine=getattr(self.view,'snap_engine',None)
        if engine is None:return None
        scale=max(float(self.view.current_scale()),1e-9); raw=(float(scene_pos.x()),float(-scene_pos.y()))
        wall=engine.nearest_wall(raw[0],raw[1],20.0/scale)
        if wall is None:return None
        x,y=float(wall[0]),float(wall[1]); gx=gy=None
        if not free_angle:
            try:segment=engine.segments[int(wall[5])][:4]
            except Exception:segment=None
            if segment is not None:
                pts=list(getattr(room,'points',[]) or []); i=int(index); candidates=[]
                if len(pts)>=2 and 0<=i<len(pts):
                    for j in {(i-1)%len(pts),(i+1)%len(pts)}:
                        hit=room_wall_axis_snap(raw[0],raw[1],pts[j],segment,14.0/scale)
                        if hit is not None:candidates.append(hit)
                if candidates:
                    x,y,gx_cad,gy_cad,_label=min(candidates,key=lambda q:(q[0]-raw[0])**2+(q[1]-raw[1])**2)
                    gx=gx_cad; gy=(-gy_cad if gy_cad is not None else None)
        return QPointF(float(x),float(-y)),gx,gy

    def _room_vertices_moved(self,room,before,after):
        if before==after:return
        room.points=deepcopy(after); self.project.dirty=True; self._update_title()
        self.undo_stack.push(EditRoomCommand(self,room.uid,{"points":before},{"points":after},'Redigér rumafgrænsning',already_applied=True))

    def edit_room_boundary(self,room,zoom=False):
        """Enter polygon editing and select *room* so its vertex handles appear."""
        if room is None:return
        if hasattr(self,'act_room_edit') and not self.act_room_edit.isChecked():
            self.act_room_edit.setChecked(True)  # toggled() refreshes visibility/editability
        else:self.room_edit_mode=True; self._refresh_room_visibility()
        boundary=self.room_boundary_items.get(getattr(room,'uid',''))
        if boundary is None:return
        self.scene.clearSelection(); boundary.setSelected(True); boundary._sync_handles()
        if zoom:self.zoom_to_room(room)
        self._set_status(f"Redigér afgrænsning: {core.room_display_text(room)} · træk hjørnepunkter · dobbeltklik på en side for nyt knækpunkt · vandret/lodret hjælpes automatisk · Alt = fri/skrå · Ctrl+Z fortryder")

    def edit_room(self,room):
        before=asdict(room); dlg=RoomEditDialog(self,room)
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        after=deepcopy(before); after['name']=dlg.name.text().strip(); after['code']=dlg.code.text().strip(); after['color']=dlg.selected_color()
        if after==before:return
        self.undo_stack.push(EditRoomCommand(self,room.uid,before,after))

    def delete_room(self,room):
        if QMessageBox.question(self,'Slet rum',f"Slet {core.room_display_text(room)}?\nSymboler og kabler slettes ikke.")!=QMessageBox.StandardButton.Yes:return
        try:index=self.project.rooms.index(room)
        except ValueError:return
        self.undo_stack.push(DeleteRoomCommand(self,room,index))

    def _room_edit_toggled(self,checked):
        selected=self._selected_rooms_from_scene() if checked else []
        self.room_edit_mode=bool(checked); self._refresh_room_visibility()
        if checked and len(selected)==1:
            boundary=self.room_boundary_items.get(selected[0].uid)
            if boundary is not None:
                self.scene.clearSelection(); boundary.setSelected(True); boundary._sync_handles()
                self._set_status(f"Redigér afgrænsning: {core.room_display_text(selected[0])} · træk hjørnepunkter · dobbeltklik på en side for nyt knækpunkt · vandret/lodret hjælpes automatisk · Alt = fri/skrå · Ctrl+Z fortryder")
                return
        self._set_status('Rumredigering aktiv · vælg en rumafgrænsning · træk hjørner eller dobbeltklik på en side for nyt knækpunkt' if checked else 'Rumredigering afsluttet · rumomrids skjules igen efter visningsvalget')

    def _room_labels_toggled(self,checked):
        self.project.raw['room_labels_visible']=bool(checked); self.project.dirty=True; self._update_title(); self._refresh_room_visibility()

    def _room_codes_toggled(self,checked):
        # Visual preference only: room.code is not modified. The marking remains
        # available to BOM/report/cable logic even when hidden on the drawing.
        self.project.raw['room_codes_visible']=bool(checked); self.project.dirty=True; self._update_title(); self._refresh_room_visibility()

    def _room_boundaries_toggled(self,checked):
        checked=bool(checked)
        self.project.raw['room_boundaries_visible']=checked
        # Boundary editing temporarily forces the polygon visible. If the user
        # explicitly chooses to hide boundaries, that intent must win: leave
        # edit mode as well so the outline can actually disappear.
        if not checked and self.room_edit_mode:
            self.room_edit_mode=False
            if hasattr(self,'act_room_edit'):
                self.act_room_edit.blockSignals(True); self.act_room_edit.setChecked(False); self.act_room_edit.blockSignals(False)
            for item in self.room_boundary_items.values():
                item.setSelected(False)
            self._set_status('Rumafgrænsninger skjult · rumtekster forbliver synlige')
        self.project.dirty=True; self._update_title(); self._refresh_room_visibility()

    def _refresh_room_visibility(self):
        layer_visible=bool(self.project.layer_visibility.get(core.ROOM_LAYER,True))
        text_visible=bool(self.project.raw.get('room_labels_visible',True))
        codes_visible=bool(self.project.raw.get('room_codes_visible',False))
        # Redigering viser midlertidigt polygonerne uanset normal omrids-visning.
        # The QAction mirrors what is ACTUALLY visible, not only the persisted
        # preference, so it never looks unchecked while edit mode shows outlines.
        boundaries=bool(self.room_edit_mode or self.project.raw.get('room_boundaries_visible',False))
        for item in self.room_boundary_items.values():item.setVisible(layer_visible and boundaries); item.set_edit_mode(self.room_edit_mode)
        for item in self.room_label_items.values():
            item.set_show_code(codes_visible)
            item.setVisible(layer_visible and text_visible)
        if hasattr(self,'act_room_labels'):
            self.act_room_labels.blockSignals(True); self.act_room_labels.setChecked(text_visible); self.act_room_labels.blockSignals(False)
        if hasattr(self,'act_room_codes'):
            self.act_room_codes.blockSignals(True); self.act_room_codes.setChecked(codes_visible); self.act_room_codes.blockSignals(False)
        if hasattr(self,'act_room_boundaries'):
            self.act_room_boundaries.blockSignals(True); self.act_room_boundaries.setChecked(boundaries); self.act_room_boundaries.blockSignals(False)

    def room_for_point(self,x,y):return core.room_for_point(self.project.rooms,x,y)
    def room_for_placement(self,placement):return self.room_for_point(float(placement.x),float(placement.y))
    def _placements_in_room(self,room):return [p for p in self.project.placements if core.room_contains_point(room,p.x,p.y)]
    def _cables_in_room(self,room):
        uid=str(getattr(room,'uid','') or '')
        return [c for c in self.project.cables if any(str(getattr(r,'uid','') or '')==uid for r in core.cable_rooms(c,self.project.rooms))]

    def _placement_extra_bom_room_uids(self,placement):
        additions=core.normalize_placement_bom_room_additions(self.project.raw.get('placement_bom_room_additions',{}))
        return list(additions.get(str(getattr(placement,'uid','') or ''),[]) or [])

    def edit_placement_bom_rooms(self,placement):
        if placement is None:return
        if not self.project.rooms:
            QMessageBox.information(self,'Ekstra BOM-rum','Definér mindst ét rum først.'); return
        before=self._placement_extra_bom_room_uids(placement)
        dlg=PlacementBomRoomsDialog(self,placement,self.project.rooms,before)
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        after=dlg.selected_room_uids()
        if before==after:return
        self._set_placement_bom_rooms(str(getattr(placement,'uid','') or ''),after)

    def _set_placement_bom_rooms(self,placement_uid,room_uids):
        uid=str(placement_uid or '').strip()
        additions=core.normalize_placement_bom_room_additions(self.project.raw.get('placement_bom_room_additions',{}))
        clean=[]; valid={str(getattr(r,'uid','') or '') for r in self.project.rooms}
        for room_uid in room_uids or []:
            room_uid=str(room_uid or '').strip()
            if room_uid in valid and room_uid not in clean:clean.append(room_uid)
        if clean:additions[uid]=clean
        else:additions.pop(uid,None)
        self.project.raw['placement_bom_room_additions']=additions; self.project.dirty=True; self._hover_bom_cache.clear(); self._update_title(); self._selection_changed()
        if hasattr(self,'_notify'):
            self._notify('Ekstra BOM-rum opdateret.' if clean else 'Ekstra BOM-rum ryddet.',kind='success',timeout=1400)

    def _room_dashboard_data(self,room):
        physical=list(self._placements_in_room(room)); room_uid=str(getattr(room,'uid','') or '')
        additions=core.normalize_placement_bom_room_additions(self.project.raw.get('placement_bom_room_additions',{}))
        physical_uids={str(getattr(p,'uid','') or '') for p in physical}
        extra=[p for p in self.project.placements if room_uid in additions.get(str(getattr(p,'uid','') or ''),[]) and str(getattr(p,'uid','') or '') not in physical_uids]
        switches=sockets=0; light_connections=sum(1 for p in physical if str(getattr(p,'symbol','') or '')=='light_connection'); spots=sum(1 for p in physical if str(getattr(p,'symbol','') or '')=='spot')
        for placement in physical:
            for part in core.bom_symbol_parts(str(getattr(placement,'symbol','') or '')):
                if part.get('kind')=='switch':switches+=1
                elif part.get('kind')=='socket':sockets+=1
        cables=self._cables_in_room(room); groups=set()
        for placement in physical+extra:
            groups.update(self._placement_groups(placement) if hasattr(self,'_placement_groups') else [])
        for cable in cables:
            value=str(getattr(cable,'circuit_id','') or '').strip()
            if value:groups.add(value)
        factor,_desc=self._length_scale_info(); cable_length=None
        if factor is not None:
            cable_length=sum(float(core.polyline_room_lengths(getattr(c,'points',[]) or [],self.project.rooms).get(room_uid,0.0))*float(factor) for c in self.project.cables)
        catalog=user_library.load_core_article_catalog(); reserve=self._length_reserve_percent()
        rows,_missing=core.build_bom(self.project.placements,catalog,self.project.raw.get('placement_articles',{}),self.project.cables,self.project.raw.get('cable_instance_articles',{}),factor,reserve,getattr(self,'global_bom_assemblies',[]),self.project.raw.get('placement_assemblies',{}),rooms=self.project.rooms,room_filter_uid=room_uid,placement_room_additions=additions)
        return {'physical_symbols':len(physical),'extra_bom_symbols':len(extra),'switches':switches,'sockets':sockets,'light_connections':light_connections,'spots':spots,'cable_count':len(cables),'cable_length_text':(self._fmt_metres(cable_length) if cable_length is not None else 'Kabellængde —'),'groups':sorted(groups,key=str.casefold),'bom_rows':rows}

    def open_room_dashboard(self,room=None):
        if room is None:
            selected=self._selected_rooms_from_scene() if hasattr(self,'scene') else []
            room=selected[0] if len(selected)==1 else None
        if room is None:
            if not self.project.rooms:
                QMessageBox.information(self,'Rum-dashboard','Definér mindst ét rum først.'); return
            captions=[core.room_display_text(r) for r in self.project.rooms]
            caption,ok=QInputDialog.getItem(self,'Rum-dashboard','Vælg rum:',captions,0,False)
            if not ok:return
            room=self.project.rooms[captions.index(caption)]
        RoomDashboardDialog(self,room).exec()

    def focus_room(self,room_uid):
        uid=str(room_uid or '').strip(); self._focus_room_id=uid
        if hasattr(self,'act_room_focus_clear'):
            self.act_room_focus_clear.setEnabled(bool(uid)); self.act_room_focus_clear.setText('Afslut rumfokus' + (f" · {core.room_display_text(next((r for r in self.project.rooms if str(getattr(r,'uid','') or '')==uid),None))}" if uid else ''))
        if hasattr(self,'_apply_visual_emphasis'):self._apply_visual_emphasis()
        if hasattr(self,'_notify'):
            room=next((r for r in self.project.rooms if str(getattr(r,'uid','') or '')==uid),None)
            self._notify(f"Rumfokus: {core.room_display_text(room)}" if room is not None else 'Rumfokus afsluttet.',kind='info',timeout=1400)

    def zoom_to_room(self,room):
        rect=room_scene_rect(room); self.view.animate_to_scene_rect(rect.adjusted(-120,-120,120,120))

    def open_room_manager(self):RoomManagerDialog(self).exec()

    def mark_cables_by_rooms(self,room=None):
        if not self.project.rooms:
            QMessageBox.information(self,'Kabelmærkning','Definér mindst ét rum først.'); return
        cables=list(self.project.cables)
        if room is not None:cables=self._cables_in_room(room)
        candidates=[c for c in cables if core.cable_room_marking(c,self.project.rooms,'name')]
        if not candidates:
            QMessageBox.information(self,'Kabelmærkning','Ingen kabler i dette område løber gennem de definerede rum.'); return
        dlg=RoomCableMarkDialog(self,candidates,self.project.rooms,room)
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        overwrite=dlg.overwrite.isChecked(); changed=0
        self.undo_stack.beginMacro('Mærk kabler efter rum')
        try:
            for cable in candidates:
                proposed=dlg.marking_for(cable).strip(); current=str(getattr(cable,'label','') or '').strip()
                if not proposed or proposed==current or (current and not overwrite):continue
                # Bevidst kun ``label``: cable_id og circuit_id kan ikke ændres af denne funktion.
                self.undo_stack.push(EditCableCommand(self,cable,{'label':current},{'label':proposed},'Rumbaseret kabelmærkning')); changed+=1
        finally:self.undo_stack.endMacro()
        self._set_status(f'{changed} kabelmærkninger opdateret efter rum · gruppe/kreds er uændret')


    def _room_annotation_direction(self,placement):
        room=self.room_for_placement(placement)
        if room is None:return None
        cx,cy=core.room_polygon_centroid(room.points); dx=float(cx)-float(placement.x); dy=float(cy)-float(placement.y)
        length=(dx*dx+dy*dy)**0.5
        return (dx/length,dy/length) if length>1e-9 else None
