from __future__ import annotations

"""PL-box configuration and conductor-distribution graphics.

The painter-heavy PL UI is lazy-loaded by ``qt_app`` when a lamp outlet is
configured, keeping the main-window module focused on orchestration.
"""

import html
import math
import uuid
from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QEasingCurve, Qt, QSignalBlocker, QPointF, QRectF, QSize, Signal, QVariantAnimation
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QIcon, QKeySequence, QPainter, QPainterPath, QPainterPathStroker, QPen, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QFrame, QGroupBox, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox,
    QPushButton, QScrollArea, QTabWidget, QTableWidget, QTableWidgetItem, QToolTip, QVBoxLayout, QWidget,
)

import core_logic as core
from elplan_shared.resources import APP_ROOT
from elplan_catalog import user_library
from elplan_qt.qt_pl_usage import SwitchConductorUsageCard, SwitchConductorUsageMixin
from elplan_qt.qt_theme import _application_dark
from elplan_qt.qt_ui import configure_modern_dialog
from elplan_qt.qt_widgets import QComboBox, QDialogButtonBox, QFormLayout, _resize_dialog, _set_role

class PLBoxDiagramWidget(QWidget):
    """Skalerbar vektorvisning af en 6-indførings PL-loftdåse."""

    portSelected = Signal(int)
    legDropped = Signal(int, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(430, 500)
        self.setAcceptDrops(True)
        self._entries = {}
        self._legs = []
        self._selected_port = 1
        self._port_rects = {}
        self._orientation = 0
        self._category_records = core.default_cable_category_records()

    @staticmethod
    def _leg_identity(row):
        return (str(row.get("cable_uid", "") or ""), int(row.get("point_index", 0) or 0), str(row.get("leg", "") or ""))

    def set_orientation(self, orientation):
        self._orientation=core.normalize_pl_box_orientation(orientation)
        self._port_rects={}
        self.update()

    def set_state(self, entries, legs, selected_port=None, orientation=None, categories=None):
        self._entries = core.normalize_pl_box_entries(entries)
        self._legs = [dict(x) for x in (legs or [])]
        if selected_port is not None:
            self._selected_port = max(1, min(core.PL_BOX_ENTRY_COUNT, int(selected_port)))
        if orientation is not None:
            self._orientation=core.normalize_pl_box_orientation(orientation)
        if categories is not None:
            self._category_records=core.normalize_cable_category_records(categories)
        self.update()

    def _category_for_leg(self, leg):
        cid=core.normalize_cable_category_id((leg or {}).get("cable_category",core.DEFAULT_CABLE_CATEGORY))
        return core.cable_category_record(self._category_records,cid)

    @staticmethod
    def _category_pen_style(value):
        return {
            "dash":Qt.PenStyle.DashLine,
            "dot":Qt.PenStyle.DotLine,
            "dashdot":Qt.PenStyle.DashDotLine,
        }.get(core.normalize_cable_line_style(value),Qt.PenStyle.SolidLine)

    def _geometry(self):
        w = max(360.0, float(self.width()))
        h = max(430.0, float(self.height()))
        cx = w * 0.50
        layout=core.pl_box_port_layout(self._orientation)
        uses_sides=any(side in {"left","right"} for side,_idx in layout.values())
        port_w=min(108.0,w*0.21) if not uses_sides else min(118.0,w*0.23)
        # Ekstra højde giver plads til kabelkategori direkte på hvert indføringskort.
        port_h=70.0
        reserve_x=2.0*(port_w+24.0) if uses_sides else 0.0
        body_d=min(h*0.39,245.0,(w-reserve_x)*0.78 if uses_sides else w*0.48)
        body_d=max(180.0,body_d)
        body=QRectF(cx-body_d/2,h*0.31,body_d,body_d)
        gap=4.0
        group_w=port_w*3+gap*2
        gx=cx-group_w/2
        top_y=max(68.0,body.top()-port_h-18.0)
        bottom_y=min(h-port_h-70.0,body.bottom()+18.0)
        group_h=port_h*3+gap*2
        gy=body.center().y()-group_h/2.0
        left_x=max(4.0,body.left()-port_w-18.0)
        right_x=min(w-port_w-4.0,body.right()+18.0)
        ports={}
        for port,(side,index) in layout.items():
            if side=="top":
                ports[port]=QRectF(gx+index*(port_w+gap),top_y,port_w,port_h)
            elif side=="bottom":
                ports[port]=QRectF(gx+index*(port_w+gap),bottom_y,port_w,port_h)
            elif side=="left":
                ports[port]=QRectF(left_x,gy+index*(port_h+gap),port_w,port_h)
            else:
                ports[port]=QRectF(right_x,gy+index*(port_h+gap),port_w,port_h)
        return body, ports

    def _leg_for_entry(self, entry):
        if not entry:
            return None
        target = (str(entry.get("cable_uid","")), int(entry.get("point_index",0) or 0), str(entry.get("leg","")))
        for leg in self._legs:
            if self._leg_identity(leg) == target:
                return leg
        return None

    @staticmethod
    def _port_side(body, rect):
        if rect.bottom() <= body.top()+2.0:return "top"
        if rect.top() >= body.bottom()-2.0:return "bottom"
        if rect.right() <= body.left()+2.0:return "left"
        return "right"

    def _port_connector_geometry(self, body, port, rect):
        side=self._port_side(body,rect)
        if side=="top":
            x=rect.center().x(); start=QPointF(x,rect.bottom()-1.0); edge=QPointF(x,body.top()); inside=QPointF(x,body.top()+22.0); gland=QRectF(x-18.0,body.top()-10.0,36.0,20.0); direction=QPointF(0.0,1.0)
        elif side=="bottom":
            x=rect.center().x(); start=QPointF(x,rect.top()+1.0); edge=QPointF(x,body.bottom()); inside=QPointF(x,body.bottom()-22.0); gland=QRectF(x-18.0,body.bottom()-10.0,36.0,20.0); direction=QPointF(0.0,-1.0)
        elif side=="left":
            y=rect.center().y(); start=QPointF(rect.right()-1.0,y); edge=QPointF(body.left(),y); inside=QPointF(body.left()+22.0,y); gland=QRectF(body.left()-10.0,y-18.0,20.0,36.0); direction=QPointF(1.0,0.0)
        else:
            y=rect.center().y(); start=QPointF(rect.left()+1.0,y); edge=QPointF(body.right(),y); inside=QPointF(body.right()-22.0,y); gland=QRectF(body.right()-10.0,y-18.0,20.0,36.0); direction=QPointF(-1.0,0.0)
        return start,edge,inside,gland,side,direction

    def _draw_conductor_preview(self, painter, body, port, rect, leg, selected=False):
        """Vis en kort 3G/5G/7G-ledervifte hvor kabelkappen åbner inde i PL-dåsen."""
        if not leg:return
        cores=core.cable_conductor_preset(str(leg.get("cable_spec") or ""))
        if not cores:return
        _start,_edge,jacket_end,_gland,_side,direction=self._port_connector_geometry(body,port,rect)
        dx,dy=direction.x(),direction.y(); px,py=-dy,dx
        tip=QPointF(jacket_end.x()+dx*34.0,jacket_end.y()+dy*34.0)
        count=len(cores); spacing=0.0 if count<=1 else min(8.5,42.0/max(1,count-1)); total=spacing*(count-1)
        if selected:
            halo=QPen(QColor(37,99,235,38),8.5); halo.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(halo)
            for idx in range(count):
                offset=-total/2.0+idx*spacing
                end=QPointF(tip.x()+px*offset,tip.y()+py*offset)
                painter.drawLine(jacket_end,end)
        for idx,meta in enumerate(cores):
            offset=-total/2.0+idx*spacing
            startp=QPointF(jacket_end.x()+px*offset*0.10,jacket_end.y()+py*offset*0.10)
            endp=QPointF(tip.x()+px*offset,tip.y()+py*offset)
            cp1=QPointF(startp.x()+dx*11.0,startp.y()+dy*11.0)
            cp2=QPointF(endp.x()-dx*8.0,endp.y()-dy*8.0)
            path=QPainterPath(startp); path.cubicTo(cp1,cp2,endp)
            color=QColor(str(meta.get("color") or "#64748b"))
            outline=QPen(QColor("#aab5c1") if _application_dark() else QColor("#475569"),5.5); outline.setCapStyle(Qt.PenCapStyle.RoundCap); outline.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(outline); painter.setBrush(Qt.BrushStyle.NoBrush); painter.drawPath(path)
            pen=QPen(color,3.7); pen.setCapStyle(Qt.PenCapStyle.RoundCap); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen); painter.drawPath(path)
            if str(meta.get("core_id") or "")=="pe":
                stripe=QPen(QColor("#facc15"),1.35); stripe.setStyle(Qt.PenStyle.DashLine); stripe.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(stripe); painter.drawPath(path)
        if abs(dx)<0.5:
            cut=QRectF(jacket_end.x()-8.5,jacket_end.y()-3.2,17.0,6.4); inner=cut.adjusted(3.0,1.5,-3.0,-1.5)
        else:
            cut=QRectF(jacket_end.x()-3.2,jacket_end.y()-8.5,6.4,17.0); inner=cut.adjusted(1.5,3.0,-1.5,-3.0)
        painter.setPen(QPen(QColor("#273444"),1.0)); painter.setBrush(QColor("#526171")); painter.drawRoundedRect(cut,3.2,3.2)
        painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QColor("#1f2937")); painter.drawRoundedRect(inner,2.0,2.0)

    def _draw_entry_connector(self, painter, body, port, rect, leg, selected):
        start,edge,inside,gland,side,direction=self._port_connector_geometry(body,port,rect)
        category=self._category_for_leg(leg) if leg else {}
        accent=QColor(str(category.get("color") or (leg or {}).get("color") or "#b91c1c")); dx,dy=direction.x(),direction.y(); px,py=-dy,dx
        accent_style=self._category_pen_style(category.get("line_style") or (leg or {}).get("line_style"))
        dark=_application_dark()
        if leg:
            if selected:
                halo=QPen(QColor(74,144,226,80) if dark else QColor(37,99,235,55),23.0); halo.setCapStyle(Qt.PenCapStyle.RoundCap); painter.setPen(halo); painter.drawLine(start,inside)
            if dark:
                edge_pen=QPen(QColor("#84909d"),18.5); edge_pen.setCapStyle(Qt.PenCapStyle.RoundCap); painter.setPen(edge_pen); painter.drawLine(start,inside)
            jacket=QPen(QColor("#202833") if dark else QColor("#273444"),16.0); jacket.setCapStyle(Qt.PenCapStyle.RoundCap); painter.setPen(jacket); painter.drawLine(start,inside)
            face=QPen(QColor("#526171"),11.0); face.setCapStyle(Qt.PenCapStyle.RoundCap); painter.setPen(face); painter.drawLine(start,inside)
            for offset,color,width,is_category in ((-2.7,QColor(255,255,255,90),2.0,False),(2.8,accent,2.8,True)):
                a=QPointF(start.x()+px*offset,start.y()+py*offset); b=QPointF(inside.x()+px*offset,inside.y()+py*offset)
                pen=QPen(color,width,accent_style if is_category else Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap)
                painter.setPen(pen); painter.drawLine(a,b)
            self._draw_conductor_preview(painter,body,port,rect,leg,selected)
        elif selected:
            guide=QPen(QColor(37,99,235,95),2.0,Qt.PenStyle.DashLine); painter.setPen(guide); painter.drawLine(start,edge)
        ring_border=QColor("#5aa1ed") if (selected and dark) else (QColor("#2563eb") if selected else ((QColor("#8c99a7") if dark else QColor("#475569")) if leg else (QColor("#66717e") if dark else QColor("#94a3b8"))))
        ring_fill=(QColor("#46515d") if dark else QColor("#dbe4ec")) if leg else (QColor("#272d34") if dark else QColor("#f1f5f9"))
        painter.setPen(QPen(ring_border,2.2 if selected else 1.4)); painter.setBrush(ring_fill); painter.drawEllipse(gland)
        inner=gland.adjusted(6.0,5.0,-6.0,-5.0) if side in {"top","bottom"} else gland.adjusted(5.0,6.0,-5.0,-6.0)
        painter.setPen(QPen((QColor("#9aa6b4") if dark else QColor("#334155")) if leg else (QColor("#59636f") if dark else QColor("#cbd5e1")),1.1)); painter.setBrush((QColor("#20262d") if dark else QColor("#334155")) if leg else (QColor("#1d2228") if dark else QColor("#ffffff"))); painter.drawEllipse(inner)
        if leg:
            core_rect=inner.adjusted(3.0,2.0,-3.0,-2.0) if side in {"top","bottom"} else inner.adjusted(2.0,3.0,-2.0,-3.0)
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QColor("#526171")); painter.drawEllipse(core_rect)
            if side in {"top","bottom"}:
                stripe=QRectF(core_rect.center().x()+1.0,core_rect.top()+1.0,3.4,max(2.0,core_rect.height()-2.0))
            else:
                stripe=QRectF(core_rect.left()+1.0,core_rect.center().y()+1.0,max(2.0,core_rect.width()-2.0),3.4)
            painter.setBrush(accent); painter.drawRoundedRect(stripe,1.5,1.5)
        else:
            painter.setPen(QPen(QColor("#94a3b8"),1.2))
            if side in {"top","bottom"}:painter.drawLine(QPointF(inner.left()+4,inner.center().y()),QPointF(inner.right()-4,inner.center().y()))
            else:painter.drawLine(QPointF(inner.center().x(),inner.top()+4),QPointF(inner.center().x(),inner.bottom()-4))
        if leg:
            if side in {"top","bottom"}:collar=QRectF(start.x()-9.0,start.y()-5.0,18.0,10.0)
            else:collar=QRectF(start.x()-5.0,start.y()-9.0,10.0,18.0)
            painter.setPen(QPen(QColor("#334155"),1.0)); painter.setBrush(QColor("#64748b")); painter.drawRoundedRect(collar,4,4)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        body, ports = self._geometry()
        self._port_rects = ports
        dark=_application_dark()
        text_main=QColor("#dbe3ec") if dark else QColor("#334155")
        text_muted=QColor("#a3afbc") if dark else QColor("#64748b")
        body_fill=QColor("#262d35") if dark else QColor("#f8fafc")
        inner_fill=QColor("#1b2026") if dark else QColor("#ffffff")
        card_fill=QColor("#242a31") if dark else QColor("#ffffff")
        card_selected=QColor("#243a52") if dark else QColor("#eff6ff")
        header_fill=QColor("#303844") if dark else QColor("#f1f5f9")
        header_selected=QColor("#2d4c6c") if dark else QColor("#dbeafe")

        # 0.50.12: kabelindføringen fortsætter nu med en kort 3G/5G/7G-ledervifte
        # inde i dåsen, så yderkappe, afisolering og lederopbygning kan aflæses visuelt.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(15, 23, 42, 18))
        painter.drawRoundedRect(body.adjusted(4,4,4,4), 18, 18)

        outline = QPen(QColor("#7f8b98") if dark else QColor("#475569")); outline.setWidthF(2.0)
        painter.setPen(outline); painter.setBrush(body_fill)
        painter.drawRoundedRect(body, 16, 16)
        circle_d = body.width()*0.72
        circle = QRectF(body.center().x()-circle_d/2, body.center().y()-circle_d/2, circle_d, circle_d)
        painter.setBrush(inner_fill); painter.drawEllipse(circle)
        lug_w,lug_h=48.0,56.0
        if core.normalize_pl_box_orientation(self._orientation) in {0,180}:
            lugs=[QRectF(body.left()-lug_w+5,body.center().y()-lug_h/2,lug_w,lug_h),QRectF(body.right()-5,body.center().y()-lug_h/2,lug_w,lug_h)]
        else:
            lugs=[QRectF(body.center().x()-lug_h/2,body.top()-lug_w+5,lug_h,lug_w),QRectF(body.center().x()-lug_h/2,body.bottom()-5,lug_h,lug_w)]
        for lug in lugs:
            painter.setBrush(body_fill); painter.setPen(outline); painter.drawRoundedRect(lug,8,8)
            painter.setBrush(inner_fill); painter.drawEllipse(QRectF(lug.center().x()-5,lug.center().y()-5,10,10))
        painter.drawLine(QPointF(circle.center().x()-12,circle.center().y()),QPointF(circle.center().x()+12,circle.center().y()))
        painter.drawLine(QPointF(circle.center().x(),circle.center().y()-12),QPointF(circle.center().x(),circle.center().y()+12))

        # Kabelstykker og gennemføringer tegnes før kortene, så de ser ud til at ligge bag dem.
        for port, rect in ports.items():
            entry = self._entries.get(str(port))
            leg = self._leg_for_entry(entry)
            self._draw_entry_connector(painter, body, port, rect, leg, port == self._selected_port)

        font = QFont("Segoe UI", 9)
        painter.setFont(font)
        for port, rect in ports.items():
            entry = self._entries.get(str(port))
            leg = self._leg_for_entry(entry)
            selected = port == self._selected_port
            shadow = QRectF(rect.adjusted(1.5, 2.0, 1.5, 2.0))
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QColor(15, 23, 42, 12)); painter.drawRoundedRect(shadow, 6, 6)
            pen = QPen((QColor("#5aa1ed") if dark else QColor("#2563eb")) if selected else (QColor("#728091") if dark else QColor("#64748b"))); pen.setWidthF(2.6 if selected else 1.5)
            painter.setPen(pen); painter.setBrush(card_selected if selected else card_fill)
            painter.drawRoundedRect(rect, 5, 5)
            header = QRectF(rect.left()+1.5, rect.top()+1.5, rect.width()-3.0, 18.0)
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(header_selected if selected else header_fill)
            painter.drawRoundedRect(header, 4, 4)
            painter.setPen(QPen(QColor("#46515d") if dark else QColor("#cbd5e1"),1.0))
            y = rect.center().y()
            painter.drawLine(QPointF(rect.left()+5,y),QPointF(rect.right()-5,y))

            painter.setPen(text_main)
            painter.drawText(QRectF(rect.left(),rect.top()+3,rect.width(),18),Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignTop,f"{port}")
            if leg:
                cid=str(leg.get("cable_display") or leg.get("cable_id") or "Kabel")
                spec=str(leg.get("cable_spec") or "")
                category=self._category_for_leg(leg)
                category_color=QColor(str(category.get("color") or leg.get("color") or "#b91c1c"))
                painter.setPen(category_color)
                painter.drawText(QRectF(rect.left()+3,rect.top()+21,rect.width()-6,17),Qt.AlignmentFlag.AlignCenter,cid[:24])
                painter.setPen(text_muted)
                if spec:
                    painter.drawText(QRectF(rect.left()+3,rect.top()+37,rect.width()-6,14),Qt.AlignmentFlag.AlignCenter,spec[:18])
                # Lille kategoriindikator: farve + kategoriens kontur + navn.
                sample_y=rect.top()+57.0
                sample_pen=QPen(category_color,2.2); sample_pen.setStyle(self._category_pen_style(category.get("line_style")))
                painter.setPen(sample_pen); painter.drawLine(QPointF(rect.left()+7,sample_y),QPointF(rect.left()+23,sample_y))
                painter.setPen(QColor("#b4bec9") if dark else QColor("#475569")); painter.setFont(QFont("Segoe UI",7))
                painter.drawText(QRectF(rect.left()+27,rect.top()+50,rect.width()-31,16),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,str(category.get("name") or "Øvrige")[:18])
                painter.setFont(font)
            else:
                painter.setPen(QColor("#788493") if dark else QColor("#94a3b8"))
                painter.drawText(QRectF(rect.left()+3,rect.top()+28,rect.width()-6,24),Qt.AlignmentFlag.AlignCenter,"Ledig")

        painter.setFont(QFont("Segoe UI", 8))
        for port, rect in ports.items():
            entry=self._entries.get(str(port)); leg=self._leg_for_entry(entry)
            if not leg: continue
            category=self._category_for_leg(leg)
            caption=f"{leg.get('cable_display') or leg.get('cable_id') or 'Kabel'} · {leg.get('leg_caption','')}\n{category.get('name') or 'Øvrige'}"
            painter.setPen(QColor(str(category.get("color") or leg.get("color") or "#b91c1c")))
            side=self._port_side(body,rect)
            if side=="top":
                label_rect=QRectF(rect.left()-8,max(2.0,rect.top()-50),rect.width()+16,44); align=Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignBottom
            elif side=="bottom":
                label_rect=QRectF(rect.left()-8,rect.bottom()+6,rect.width()+16,44); align=Qt.AlignmentFlag.AlignHCenter|Qt.AlignmentFlag.AlignTop
            elif side=="left":
                label_rect=QRectF(max(2.0,rect.left()-148),rect.top()-4,140,rect.height()+8); align=Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter
            else:
                label_rect=QRectF(rect.right()+8,rect.top()-4,min(140.0,self.width()-rect.right()-10.0),rect.height()+8); align=Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter
            painter.drawText(label_rect,align|Qt.TextFlag.TextWordWrap,caption)
        # Orienteringen refererer altid til plantegningens top, så montøren kan
        # sætte dåsen ens i dialog, rapport og fysisk montage.
        painter.setPen(text_muted); painter.setFont(QFont("Segoe UI",7))
        painter.drawText(QRectF(8,8,self.width()-16,22),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,f"Plantegning op ↑ · Fysisk orientering {core.normalize_pl_box_orientation(self._orientation)}°")
        painter.end()

    def _port_at(self, pos):
        if not self._port_rects:
            _body, self._port_rects = self._geometry()
        for port, rect in self._port_rects.items():
            if rect.contains(pos):
                return int(port)
        return 0

    def mousePressEvent(self, event):
        port=self._port_at(event.position())
        if port:
            self._selected_port=port
            self.portSelected.emit(port)
            self.update()
            event.accept(); return
        super().mousePressEvent(event)

    def dragEnterEvent(self, event):
        source=event.source()
        if isinstance(source,QListWidget) and source.currentItem() is not None:
            event.acceptProposedAction(); return
        event.ignore()

    def dragMoveEvent(self, event):
        if self._port_at(event.position()): event.acceptProposedAction()
        else: event.ignore()

    def dropEvent(self, event):
        port=self._port_at(event.position())
        source=event.source()
        item=source.currentItem() if isinstance(source,QListWidget) else None
        leg=item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if port and isinstance(leg,dict):
            self._selected_port=port
            self.portSelected.emit(port)
            self.legDropped.emit(port,dict(leg))
            event.acceptProposedAction(); return
        event.ignore()

class PLWiringDiagramWidget(QWidget):
    """Stor grafisk arbejdsflade for lederfordelingen i en PL-loftdåse.

    Lampeudtagets fysiske klemrække er den primære editor. Farvede ledere kan
    vælges, trækkes eller højreklikkes, og manuelle Wago-samlinger kan placeres
    frit i PL-dåsen. Hover fremhæver den komplette elektriske forbindelse.
    """

    conductorSelected=Signal(object)
    functionAssigned=Signal(object,str)
    conductorAction=Signal(object,str)
    spliceMoved=Signal(str,float,float)
    spliceAction=Signal(str,str)
    functionAction=Signal(str,str)

    def __init__(self, parent=None):
        super().__init__(parent)
        # Geometrien er responsiv, så 470 px viser hele montagevisningen.
        self.setMinimumSize(780, 470)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._entries={}
        self._legs=[]
        self._wiring=[]
        self._splices=[]
        self._associations=[]
        self._requirements=[]
        self._external_allocations={}
        self._destination_labels={}
        self._outlet_type="generic"
        # 0.50.22: lederfordelingsgrafikken bruger de samme projektkategorier
        # som Kabelindføringer, så hvert kabelkort kan vise kategoriens navn,
        # farve og kontur direkte under kabel-ID'et.
        self._category_records=core.default_cable_category_records()
        self._selected_key=None
        self._hover_key=None
        self._hover_function=None
        self._focus_function=""
        self._drag_key=None
        self._drag_pos=None
        self._hit_conductors=[]
        self._hit_wire_paths=[]
        self._hit_functions=[]
        self._hit_function_paths=[]
        self._hit_splices=[]
        self._conductor_centers={}
        self._function_rects={}
        self._wago_drag_id=None
        self._wago_drag_fid=""
        self._wago_drag_start=None
        self._wago_drag_offset=QPointF()
        self._wago_drag_half=QPointF(80.0,32.0)
        self._wago_drag_moved=False
        self._wago_drag_override={}
        self._exploded=False
        # 0.59.45: compact is the default PL presentation. Detailed mode keeps
        # the richer Wago/terminal annotations available on demand.
        self._detail_mode=False
        self._flash_key=None; self._flash_progress=1.0
        self._flash_anim=QVariantAnimation(self); self._flash_anim.setDuration(260); self._flash_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._flash_anim.valueChanged.connect(self._set_flash_progress); self._flash_anim.finished.connect(self._finish_flash)
        # Normaliserede profiler og opslag ændres kun ved en reel lederændring.
        # De genbruges ved hover/markering, hvor paintEvent ellers blev tvunget
        # til at genopbygge hele domænet for hvert visuelt fokus-skift.
        self._state_cache={}
        self._rebuild_state_cache()
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_exploded(self, enabled: bool) -> None:
        enabled=bool(enabled)
        if self._exploded==enabled:return
        self._exploded=enabled; self.update()

    def set_detail_mode(self, enabled: bool) -> None:
        """Switch between compact and detailed PL graphics without touching wiring state."""
        enabled=bool(enabled)
        if self._detail_mode==enabled:return
        self._detail_mode=enabled
        QToolTip.hideText()
        self.update()

    def detail_mode(self) -> bool:
        return bool(getattr(self,"_detail_mode",False))

    def _set_flash_progress(self,value) -> None:
        try:self._flash_progress=max(0.0,min(1.0,float(value)))
        except Exception:self._flash_progress=1.0
        self.update()

    def _finish_flash(self) -> None:
        self._flash_key=None; self._flash_progress=1.0; self.update()

    def flash_connection(self,key) -> None:
        self._flash_key=tuple(key) if key else None; self._flash_progress=0.0
        self._flash_anim.stop(); self._flash_anim.setStartValue(0.0); self._flash_anim.setEndValue(1.0); self._flash_anim.start()

    @staticmethod
    def _leg_key(row):
        return (str(row.get("cable_uid","") or ""), int(row.get("point_index",0) or 0), str(row.get("leg","") or ""))

    def set_state(self, entries, legs, wiring, associations=None, requirements=None, outlet_type="generic", splices=None, cable_categories=None, external_allocations=None, destination_labels=None):
        new_entries=core.normalize_pl_box_entries(entries)
        new_legs=[dict(x) for x in (legs or [])]
        new_categories=self._category_records if cable_categories is None else core.normalize_cable_category_records(cable_categories)
        new_wiring=core.reconcile_pl_box_wiring(wiring,new_legs)
        new_splices=core.reconcile_pl_box_splices(splices or [],new_wiring,new_legs)
        new_associations=core.normalize_associations(associations or [])
        new_requirements=[dict(x) for x in (requirements or []) if isinstance(x,dict)]
        new_external={tuple(k):dict(v) for k,v in (external_allocations or {}).items() if len(tuple(k))==4 and isinstance(v,dict)}
        new_destinations={str(k):str(v) for k,v in (destination_labels or {}).items() if str(k or "")}
        new_outlet_type=core.normalize_pl_outlet_type(outlet_type)
        changed=any((
            new_entries!=self._entries,new_legs!=self._legs,new_categories!=self._category_records,
            new_wiring!=self._wiring,new_splices!=self._splices,new_associations!=self._associations,
            new_requirements!=self._requirements,new_external!=self._external_allocations,
            new_destinations!=self._destination_labels,new_outlet_type!=self._outlet_type,
        ))
        self._entries=new_entries
        self._legs=new_legs
        if cable_categories is not None:
            self._category_records=new_categories
        self._wiring=new_wiring
        self._splices=new_splices
        self._associations=new_associations
        self._requirements=new_requirements
        self._external_allocations=new_external
        self._destination_labels=new_destinations
        self._outlet_type=new_outlet_type
        valid={core.pl_box_conductor_key(x) for x in core.pl_box_conductors(self._legs)}
        if self._selected_key not in valid:self._selected_key=None
        if self._hover_key not in valid:self._hover_key=None
        if self._drag_key not in valid:
            self._drag_key=None; self._drag_pos=None
        if changed:
            self._rebuild_state_cache(); self.update()

    def _rebuild_state_cache(self):
        """Cache state-derived structures used by every hover repaint."""
        profile=core.pl_outlet_profile(self._outlet_type,self._associations)
        leg_by_key={self._leg_key(x):x for x in self._legs}
        port_leg={}
        for port,entry in self._entries.items():
            key=(str(entry.get("cable_uid","")),int(entry.get("point_index",0) or 0),str(entry.get("leg","")))
            leg=leg_by_key.get(key)
            if leg is not None:port_leg[int(port)]=leg
        conductors=core.pl_box_conductors(self._legs)
        self._state_cache={
            "profile":profile,"leg_by_key":leg_by_key,"port_leg":port_leg,"conductors":conductors,
            "conductor_meta":{core.pl_box_conductor_key(x):x for x in conductors},
            "wiring":{core.pl_box_conductor_key(x):x for x in self._wiring},
        }

    def _category_for_leg(self,leg):
        cid=core.normalize_cable_category_id((leg or {}).get("cable_category",core.DEFAULT_CABLE_CATEGORY))
        return core.cable_category_record(self._category_records,cid)

    def set_selected_conductor(self,key):
        new_key=tuple(key) if key else None
        if self._selected_key==new_key:return
        self._selected_key=new_key
        self._focus_function=""
        self.update()

    def set_focus_function(self,function_id):
        """Hold en funktion fremhævet, fx fra problemnavigatoren."""
        fid=str(function_id or "")
        if self._focus_function==fid:return
        self._focus_function=fid; self.update()

    def _hit_conductor(self,pos):
        for rect,key in reversed(self._hit_conductors):
            if rect.contains(pos): return tuple(key)
        for path,key in reversed(self._hit_wire_paths):
            if path.contains(pos): return tuple(key)
        return None

    def _hit_function(self,pos):
        for rect,fid in reversed(self._hit_functions):
            if rect.contains(pos): return str(fid)
        for path,fid in reversed(self._hit_function_paths):
            if path.contains(pos): return str(fid)
        return None

    def _hit_splice(self,pos):
        for rect,sid,fid in reversed(self._hit_splices):
            if rect.contains(pos): return str(sid),str(fid),QRectF(rect)
        return None

    def _function_for_key(self,key):
        key=tuple(key or ())
        return next((str(row.get("function","") or "") for row in self._wiring if core.pl_box_conductor_key(row)==key),"")

    def _hover_connection_function(self):
        if self._hover_key is not None:
            fid=self._function_for_key(self._hover_key)
            if fid:return fid
        return str(self._hover_function or self._focus_function or "")

    def _splice_for_key(self,key):
        key=tuple(key or ())
        return next((x for x in self._splices if key in core.pl_splice_member_keys(x)),None)

    def _splices_for_function(self,fid):
        fid=str(fid or "")
        return [x for x in self._splices if str(x.get("function","") or "")==fid]

    def _function_caption(self,fid):
        return core.pl_wiring_function_caption(str(fid or ""),self._associations,self._outlet_type).split(" → ",1)[0]

    def _splice_caption(self,splice):
        fid=str((splice or {}).get("function","") or "")
        label=self._function_caption(fid)
        members=len(core.pl_splice_member_keys(splice or {}))
        article=str((splice or {}).get("article_no","") or "").strip()
        connects=bool((splice or {}).get("connects_to_outlet",True))
        if connects:
            mode="→ udtag"
        else:
            destination_uid=str((splice or {}).get("destination_light_uid","") or "")
            destination=self._destination_labels.get(destination_uid,"")
            assoc=str((splice or {}).get("destination_association","") or "")
            role=core.normalize_pl_passthrough_role((splice or {}).get("conductor_role"),fid)
            requires_destination=role in {"switch","traveller_1","traveller_2"}
            mode="samlemuffe · "+("til "+destination if destination else ("⚠ destination mangler" if requires_destination else "intern samling"))
        suffix=f" · {article}" if article else ""
        return f"Wago {label} · {members} ledere · {mode}{suffix}"

    def _show_function_context_menu(self,fid,global_pos):
        fid=str(fid or "")
        if not fid:return
        menu=QMenu(self)
        caption=self._function_caption(fid)
        if self._selected_key is not None:
            direct=menu.addAction(f"Forbind valgt leder direkte til {caption}")
            direct.triggered.connect(lambda:self.functionAssigned.emit(tuple(self._selected_key),fid))
            splices=self._splices_for_function(fid)
            outlet_splices=[x for x in splices if bool(x.get("connects_to_outlet",True))]
            loop_splices=[x for x in splices if not bool(x.get("connects_to_outlet",True))]
            if outlet_splices:
                via_menu=menu.addMenu("Forbind via eksisterende Wago → lampeudtag")
                for splice in outlet_splices:
                    sid=str(splice.get("id","") or "")
                    act=via_menu.addAction(self._splice_caption(splice))
                    act.triggered.connect(lambda _checked=False,sid=sid:self.conductorAction.emit(tuple(self._selected_key),f"add_to_splice:{sid}"))
            if loop_splices:
                loop_menu=menu.addMenu("Saml i eksisterende samlemuffe · ingen udtag")
                for splice in loop_splices:
                    sid=str(splice.get("id","") or "")
                    act=loop_menu.addAction(self._splice_caption(splice))
                    act.triggered.connect(lambda _checked=False,sid=sid:self.conductorAction.emit(tuple(self._selected_key),f"add_to_splice:{sid}"))
            menu.addSeparator()
        create=menu.addAction(f"+ Opret Wago for {caption} → lampeudtag…")
        create.triggered.connect(lambda:self.functionAction.emit(fid,"new"))
        create_loop=menu.addAction(f"+ Opret samlemuffe for {caption} · ingen forbindelse til udtag…")
        create_loop.triggered.connect(lambda:self.functionAction.emit(fid,"new_loop"))
        splices=self._splices_for_function(fid)
        if splices:
            menu.addSeparator()
            for splice in splices:
                sid=str(splice.get("id","") or "")
                sub=menu.addMenu(self._splice_caption(splice))
                edit=sub.addAction("Redigér Wago…"); edit.triggered.connect(lambda _checked=False,sid=sid:self.spliceAction.emit(sid,"edit"))
                reset=sub.addAction("Nulstil placering"); reset.triggered.connect(lambda _checked=False,sid=sid:self.spliceAction.emit(sid,"reset_position"))
                remove=sub.addAction("Fjern Wago"); remove.triggered.connect(lambda _checked=False,sid=sid:self.spliceAction.emit(sid,"remove"))
        menu.exec(global_pos)

    def _show_drop_function_menu(self,key,fid,global_pos):
        """Vis kun et valg, når Wago faktisk er relevant for drop-handlingen."""
        fid=str(fid or ""); key=tuple(key or ())
        splices=self._splices_for_function(fid)
        if not splices:
            self.functionAssigned.emit(key,fid); return
        menu=QMenu(self)
        caption=self._function_caption(fid)
        direct=menu.addAction(f"Direkte til {caption}")
        direct.triggered.connect(lambda:self.functionAssigned.emit(key,fid))
        outlet_splices=[x for x in splices if bool(x.get("connects_to_outlet",True))]
        loop_splices=[x for x in splices if not bool(x.get("connects_to_outlet",True))]
        if outlet_splices:
            via=menu.addMenu("Via eksisterende Wago → lampeudtag")
            for splice in outlet_splices:
                sid=str(splice.get("id","") or "")
                act=via.addAction(self._splice_caption(splice))
                act.triggered.connect(lambda _checked=False,sid=sid:self.conductorAction.emit(key,f"add_to_splice:{sid}"))
        if loop_splices:
            via_loop=menu.addMenu("I samlemuffe · ingen forbindelse til udtag")
            for splice in loop_splices:
                sid=str(splice.get("id","") or "")
                act=via_loop.addAction(self._splice_caption(splice))
                act.triggered.connect(lambda _checked=False,sid=sid:self.conductorAction.emit(key,f"add_to_splice:{sid}"))
        existing_for_key=self._splice_for_key(key)
        if existing_for_key is None:
            menu.addSeparator()
            create=menu.addAction(f"+ Opret ny Wago for {caption} og forbind…")
            create.triggered.connect(lambda:self.conductorAction.emit(key,f"new_wago_for:{fid}"))
        menu.exec(global_pos)

    def _show_conductor_context_menu(self,key,global_pos):
        key=tuple(key); self._selected_key=key; self.setFocus(Qt.FocusReason.MouseFocusReason); self.conductorSelected.emit(key); self.update()
        fid=self._function_for_key(key)
        menu=QMenu(self)
        detach=menu.addAction("Frigør leder    Delete")
        detach.setEnabled(bool(fid)); detach.triggered.connect(lambda:self.functionAssigned.emit(key,""))
        menu.addSeparator()
        profile=core.pl_outlet_profile(self._outlet_type,self._associations)
        seen=set()
        for terminal in profile.get("terminals",[]):
            target=str(terminal.get("function_id","") or "")
            if not target or target in seen:continue
            seen.add(target)
            label=str(terminal.get("label") or self._function_title(target))
            subtitle=str(terminal.get("subtitle") or "")
            action=menu.addAction(f"Flyt til {label}"+(f" · {subtitle}" if subtitle else ""))
            action.setCheckable(True); action.setChecked(target==fid)
            action.triggered.connect(lambda _checked=False,target=target:self.functionAssigned.emit(key,target))
        menu.addSeparator()
        splice=self._splice_for_key(key)
        if splice is not None:
            remove=menu.addAction("Fjern fra Wago og frigør leder")
            remove.triggered.connect(lambda:self.conductorAction.emit(key,"remove_wago"))
            edit=menu.addAction("Redigér Wago-samling…")
            edit.triggered.connect(lambda:self.conductorAction.emit(key,"edit_wago"))
        else:
            if fid and fid in seen:
                matching=self._splices_for_function(fid)
                if matching:
                    via=menu.addMenu("Flyt til eksisterende Wago")
                    for row in matching:
                        sid=str(row.get("id","") or "")
                        act=via.addAction(self._splice_caption(row))
                        act.triggered.connect(lambda _checked=False,sid=sid:self.conductorAction.emit(key,f"add_to_splice:{sid}"))
                caption=self._function_caption(fid)
                add=menu.addAction(f"+ Opret ny Wago for {caption}…")
                add.triggered.connect(lambda:self.conductorAction.emit(key,f"new_wago_for:{fid}"))
            loop=menu.addAction("Saml leder i samlemuffe / Wago uden forbindelse til lampeudtaget…")
            loop.triggered.connect(lambda:self.conductorAction.emit(key,"loop_wago"))
        menu.exec(global_pos)

    def _show_splice_context_menu(self,sid,global_pos):
        sid=str(sid or "")
        menu=QMenu(self)
        splice=next((x for x in self._splices if str(x.get("id","") or "")==sid),None)
        if splice is not None and self._selected_key is not None and tuple(self._selected_key) not in core.pl_splice_member_keys(splice):
            add=menu.addAction("Forbind valgt leder til denne Wago")
            add.triggered.connect(lambda:self.conductorAction.emit(tuple(self._selected_key),f"add_to_splice:{sid}"))
            menu.addSeparator()
        edit=menu.addAction("Redigér Wago…"); edit.triggered.connect(lambda:self.spliceAction.emit(sid,"edit"))
        if splice is not None and not bool(splice.get("connects_to_outlet",True)):
            destination=menu.addAction("Skift ledertype / tilhørende lampested…")
            destination.triggered.connect(lambda:self.spliceAction.emit(sid,"destination"))
        reset=menu.addAction("Nulstil Wago-placering"); reset.triggered.connect(lambda:self.spliceAction.emit(sid,"reset_position"))
        menu.addSeparator()
        remove=menu.addAction("Fjern Wago"); remove.triggered.connect(lambda:self.spliceAction.emit(sid,"remove"))
        menu.exec(global_pos)

    def _compact_hover_tooltip(self, splice_hit=None, fid=""):
        """Return detailed text for compact graphics without permanently occupying canvas space."""
        if self.detail_mode():
            return ""
        if splice_hit is not None:
            sid=str(splice_hit[0] or "")
            splice=next((x for x in self._splices if str(x.get("id","") or "")==sid),None)
            if splice is not None:
                members=len(core.pl_splice_member_keys(splice))
                article=str(splice.get("article_no","") or "").strip() or "Ingen artikel"
                connects=bool(splice.get("connects_to_outlet",True))
                mode="Bro til lampeudtag" if connects else "Kun samlemuffe / sløjfe"
                needed=core.pl_wago_required_ports(members,connects)
                cap=core.pl_wago_article_capacity(article)
                cap_text=f"{needed}/{cap} pladser" if cap else f"{needed}/? pladser"
                return f"{self._splice_caption(splice)}\n{cap_text} · {article}\n{mode}"
        fid=str(fid or "")
        if fid:
            profile=core.pl_outlet_profile(self._outlet_type,self._associations)
            terminal=next((x for x in profile.get("terminals",[]) if str(x.get("function_id","") or "")==fid),None)
            if terminal:
                label=str(terminal.get("label") or self._function_title(fid))
                subtitle=str(terminal.get("subtitle") or "")
                extra=self._function_subtitle(fid)
                cap=int(terminal.get("capacity") or 0)
                lines=[f"{label} · {subtitle}" if subtitle else label]
                if extra and extra!=subtitle: lines.append(extra)
                if cap: lines.append(f"Kapacitet: {cap} leder(e)/bro(er)")
                return "\n".join(lines)
        return ""

    def _external_allocation_tooltip(self,key):
        hint=self._external_allocations.get(tuple(key or ()),{})
        functions=list(hint.get("functions",[]) or [])
        if not functions:return ""
        labels=[core.pl_wiring_function_caption(fid).split(" → ",1)[0] for fid in functions]
        places=[]
        for row in hint.get("usages",[]) or []:
            place=str(row.get("placement") or "Lampested")
            if place not in places:places.append(place)
        status="Konflikt: flere funktioner på samme leder" if hint.get("conflict") else "Allokeret ved kablets anden ende"
        where=("\nVed: "+", ".join(places[:4])) if places else ""
        return status+"\n"+" / ".join(labels)+where+"\nLederen er endnu ikke fysisk forbundet i denne dåse."

    def contextMenuEvent(self,event):
        pos=QPointF(event.pos())
        splice=self._hit_splice(pos)
        if splice is not None:
            self._show_splice_context_menu(splice[0],event.globalPos()); event.accept(); return
        key=self._hit_conductor(pos)
        if key is not None:
            self._show_conductor_context_menu(key,event.globalPos()); event.accept(); return
        fid=self._hit_function(pos)
        if fid is not None:
            self._show_function_context_menu(fid,event.globalPos()); event.accept(); return
        super().contextMenuEvent(event)

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:
            pos=event.position()
            splice=self._hit_splice(pos)
            if splice is not None:
                sid,fid,rect=splice
                self._wago_drag_id=sid; self._wago_drag_fid=fid; self._wago_drag_start=QPointF(pos)
                self._wago_drag_offset=QPointF(pos.x()-rect.center().x(),pos.y()-rect.center().y())
                self._wago_drag_half=QPointF(rect.width()/2.0+8.0,rect.height()/2.0+8.0)
                self._wago_drag_moved=False
                self.setFocus(Qt.FocusReason.MouseFocusReason); self.setCursor(Qt.CursorShape.SizeAllCursor)
                event.accept(); return
            key=self._hit_conductor(pos)
            if key is not None:
                self._selected_key=key
                self._focus_function=""
                self._drag_key=key
                self._drag_pos=QPointF(pos)
                self.setFocus(Qt.FocusReason.MouseFocusReason)
                self.conductorSelected.emit(key)
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                self.update(); event.accept(); return
            fid=self._hit_function(pos)
            if fid is not None and self._selected_key is not None:
                self.functionAssigned.emit(tuple(self._selected_key),fid)
                event.accept(); return
        super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        pos=event.position()
        if self._drag_key is not None and bool(event.buttons() & Qt.MouseButton.LeftButton):
            self._drag_pos=QPointF(pos)
            self._hover_function=self._hit_function(pos)
            self.update(); event.accept(); return
        if self._wago_drag_id is not None and bool(event.buttons() & Qt.MouseButton.LeftButton):
            if self._wago_drag_start is not None:
                distance=math.hypot(pos.x()-self._wago_drag_start.x(),pos.y()-self._wago_drag_start.y())
                if distance>=4.0:self._wago_drag_moved=True
            if self._wago_drag_moved:
                body,_ports,_terminal=self._geometry()
                center=QPointF(pos.x()-self._wago_drag_offset.x(),pos.y()-self._wago_drag_offset.y())
                # Hold hele Wago-blokken inde i PL-dåsen med en lille margen.
                margin_x=max(20.0,self._wago_drag_half.x()); margin_y=max(20.0,self._wago_drag_half.y())
                center.setX(max(body.left()+margin_x,min(body.right()-margin_x,center.x())))
                center.setY(max(body.top()+margin_y,min(body.bottom()-margin_y,center.y())))
                self._wago_drag_override[str(self._wago_drag_id)]=center
                self.setCursor(Qt.CursorShape.SizeAllCursor); self.update(); event.accept(); return
        splice=self._hit_splice(pos)
        new_key=None if splice is not None else self._hit_conductor(pos)
        new_function=splice[1] if splice is not None else self._hit_function(pos)
        if new_key!=self._hover_key or new_function!=self._hover_function:
            self._hover_key=new_key; self._hover_function=new_function; self.update()
            tip=self._external_allocation_tooltip(new_key) if new_key is not None else self._compact_hover_tooltip(splice,new_function)
            if tip:
                QToolTip.showText(event.globalPosition().toPoint(),tip,self)
            else:
                QToolTip.hideText()
        if new_key is not None:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif splice is not None:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        elif new_function is not None and self._selected_key is not None:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and self._drag_key is not None:
            splice=self._hit_splice(event.position())
            fid=None if splice is not None else self._hit_function(event.position())
            key=tuple(self._drag_key)
            self._drag_key=None; self._drag_pos=None; self._hover_function=None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            if splice is not None:
                self.conductorAction.emit(key,f"add_to_splice:{splice[0]}")
            elif fid is not None:
                self._show_drop_function_menu(key,fid,event.globalPosition().toPoint())
            self.update(); event.accept(); return
        if event.button()==Qt.MouseButton.LeftButton and self._wago_drag_id is not None:
            sid=str(self._wago_drag_id); fid=str(self._wago_drag_fid or "")
            moved=bool(self._wago_drag_moved)
            if moved:
                body,_ports,_terminal=self._geometry()
                center=self._wago_drag_override.get(sid)
                if center is not None and body.width()>0 and body.height()>0:
                    nx=max(0.0,min(1.0,(center.x()-body.left())/body.width()))
                    ny=max(0.0,min(1.0,(center.y()-body.top())/body.height()))
                    self.spliceMoved.emit(sid,float(nx),float(ny))
            elif self._selected_key is not None and fid:
                # Klik på Wago-blokken føjer den valgte leder direkte til selve
                # samlingen. For en ren sløjfe betyder det ingen lampestedbro.
                self.conductorAction.emit(tuple(self._selected_key),f"add_to_splice:{sid}")
            elif sid:
                # Uden valgt leder fungerer et almindeligt klik som den naturlige
                # vej til at inspicere/redigere den fysiske Wago.
                self.spliceAction.emit(sid,"edit")
            self._wago_drag_id=None; self._wago_drag_fid=""; self._wago_drag_start=None
            self._wago_drag_moved=False; self._wago_drag_override.pop(sid,None)
            self.setCursor(Qt.CursorShape.ArrowCursor); self.update(); event.accept(); return
        super().mouseReleaseEvent(event)

    def leaveEvent(self,event):
        if self._drag_key is None and self._wago_drag_id is None:
            self._hover_key=None; self._hover_function=None; QToolTip.hideText(); self.setCursor(Qt.CursorShape.ArrowCursor); self.update()
        super().leaveEvent(event)

    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape and (self._drag_key is not None or self._wago_drag_id is not None):
            sid=str(self._wago_drag_id or "")
            self._drag_key=None; self._drag_pos=None; self._hover_function=None
            self._wago_drag_id=None; self._wago_drag_fid=""; self._wago_drag_start=None; self._wago_drag_moved=False
            if sid:self._wago_drag_override.pop(sid,None)
            self.setCursor(Qt.CursorShape.ArrowCursor); self.update(); event.accept(); return
        if event.key() in (Qt.Key.Key_Delete,Qt.Key.Key_Backspace) and self._selected_key is not None:
            # Samme sikre frigørelse som knappen: dialogen fjerner også lederen
            # fra en eventuel Wago-samling via den normale assignment-rute.
            self.functionAssigned.emit(tuple(self._selected_key),"")
            event.accept(); return
        super().keyPressEvent(event)

    def _geometry(self):
        """Geometri for 0.50.1: PL-dåsen til venstre, klemrækken tydeligt ved siden af.

        Hovedgrebet er at stoppe med at lægge klemmerne oven i lederbundtet. Der
        reserveres derfor en fast højre kolonne til lampeudtaget, mens de seks
        kabelindføringer stadig ligger fysisk over/under selve PL-dåsen.
        """
        # Brug den faktiske widgethøjde; tidligere blev der altid regnet med
        # mindst 620 px, hvilket klippede bundindføringerne på lave skærme.
        w=max(780.0,float(self.width())); h=max(470.0,float(self.height()))
        exploded=bool(getattr(self,"_exploded",False))
        # Reserver en lille statuszone nederst. Tidligere blev hjælpeteksten
        # malet oven på kabelindføring 4-6 på lave/høje layoutkombinationer.
        footer_h=30.0
        detailed=self.detail_mode()
        outer=26.0 if exploded else 18.0
        terminal_gap=58.0 if exploded else (26.0 if detailed else 18.0)
        if detailed:
            terminal_w=min(350.0 if exploded else 365.0,max(245.0 if exploded else 265.0,w*(0.29 if exploded else 0.31)))
        else:
            # Compact view deliberately gives conductor routing more horizontal room.
            terminal_w=min(300.0,max(220.0,w*0.245))
        # Udnyt den ledige bredde til kabelkortene før vi gør teksten mindre.
        # Ved ca. 1200 px arbejdsbredde giver det typisk 200-220 px pr. kort,
        # mens små vinduer fortsat falder responsivt tilbage.
        body_w=min(690.0,max(400.0,w-2*outer-terminal_gap-terminal_w))
        total=body_w+terminal_gap+terminal_w; left=max(outer,(w-total)/2.0)

        compact=h<590.0; t=max(0.0,min(1.0,(h-470.0)/120.0))
        # 0.59.8: kabelmærkningen er den vigtigste information på et
        # indføringskort. Kortene får derfor lidt mere højde på normale/store
        # dialoger, så en lang fysisk mærkning kan vises over op til to linjer
        # uden at kategori/specifikation skubber den væk.
        port_h=80.0+14.0*t; top_y=12.0+6.0*t
        port_body_gap=18.0+10.0*t; bottom_margin=22.0+20.0*t
        body_top=top_y+port_h+port_body_gap
        bottom_y=max(body_top+245.0,h-port_h-bottom_margin-footer_h)
        body_bottom=max(body_top+250.0,bottom_y-port_body_gap)
        body_bottom=min(body_bottom,h-port_h-footer_h-8.0)
        body=QRectF(left,body_top,body_w,max(250.0,body_bottom-body_top))

        port_gap=18.0 if exploded else 8.0; port_w=min(205.0 if exploded else 222.0,(body.width()-port_gap*2)/3.0)
        group_w=port_w*3+port_gap*2; gx=body.center().x()-group_w/2.0
        # 0.52.7 brugte: bottom_y=min(h-port_h-8.0,...) og terminal_bottom=min(h-6.0,max(...). Nu reserveres footer_h.
        bottom_y=min(h-port_h-footer_h-8.0,max(body.bottom()+port_body_gap,bottom_y))
        ports={
            1:QRectF(gx,top_y,port_w,port_h),
            2:QRectF(gx+port_w+port_gap,top_y,port_w,port_h),
            3:QRectF(gx+(port_w+port_gap)*2,top_y,port_w,port_h),
            4:QRectF(gx,bottom_y,port_w,port_h),
            5:QRectF(gx+port_w+port_gap,bottom_y,port_w,port_h),
            6:QRectF(gx+(port_w+port_gap)*2,bottom_y,port_w,port_h),
        }
        if detailed:
            terminal_top=max(42.0,body.top()-(18.0 if compact else 30.0))
            terminal_bottom=min(h-footer_h-6.0,max(terminal_top+230.0,h-footer_h-(10.0 if compact else 18.0)))
            terminal_h=max(220.0,terminal_bottom-terminal_top)
        else:
            # A genuinely compact outlet: keep the terminal stack centred and
            # physically shorter instead of redistributing all free height.
            terminal_h=max(252.0,min(318.0,body.height()*0.72))
            terminal_top=max(42.0,body.center().y()-terminal_h/2.0)
            terminal_top=min(terminal_top,h-footer_h-6.0-terminal_h)
        terminal=QRectF(body.right()+terminal_gap,terminal_top,terminal_w,terminal_h)
        return body,ports,terminal

    @staticmethod
    def _wrap_port_label(text, metrics, width, max_lines=2):
        """Bryd en kabelmærkning uden at elidere/afkorte selve teksten.

        Der brydes helst ved mellemrum, separatorer og bindestreger. Hvis en
        enkelt del stadig er for lang, brydes den ved nærmeste tegn, så hele
        brugerens mærkning altid kan tegnes.
        """
        text=str(text or "").strip()
        if not text:
            return [""]
        if metrics.horizontalAdvance(text) <= width:
            return [text]
        lines=[]; rest=text
        break_chars=set(" -·→/\\")
        while rest and len(lines)<max_lines-1:
            lo,hi=1,len(rest)
            best=1
            while lo<=hi:
                mid=(lo+hi)//2
                if metrics.horizontalAdvance(rest[:mid])<=width:
                    best=mid; lo=mid+1
                else:
                    hi=mid-1
            cut=best
            # Gå lidt tilbage efter et naturligt brud, men undgå at lave en
            # meget kort første linje.
            floor=max(1,int(best*0.58))
            for idx in range(best-1,floor-1,-1):
                if rest[idx] in break_chars:
                    cut=idx+1; break
            line=rest[:cut].rstrip()
            rest=rest[cut:].lstrip()
            if line: lines.append(line)
        if rest: lines.append(rest)
        return lines

    @staticmethod
    def _port_card_layout(rect, port):
        """Inddel et kabelkort i tekstzone og separat lederzone.

        Topindføringer har lederudgang nederst i kortet, mens bundindføringer
        har lederudgang øverst. Teksten flyttes derfor væk fra den fysiske
        lederzone, så kabelmærkning og farvede lederstumper aldrig tegnes oven
        i hinanden.
        """
        conductor_band=19.0
        pad=4.0
        if int(port)<=3:
            content_top=rect.top()+pad
            content_bottom=rect.bottom()-conductor_band-2.0
        else:
            content_top=rect.top()+conductor_band+2.0
            content_bottom=rect.bottom()-pad
        content_h=max(38.0,content_bottom-content_top)
        meta_h=15.0
        label_h=max(28.0,content_h-meta_h-2.0)
        badge=QRectF(rect.left()+6,content_top+1.0,24,20)
        label=QRectF(rect.left()+36,content_top,rect.width()-41,label_h)
        meta=QRectF(rect.left()+36,content_top+label_h+1.0,rect.width()-41,meta_h)
        return {"badge":badge,"label":label,"meta":meta,"conductor_band":conductor_band}

    def _draw_port_cable_label(self,p,rect,text,color,label_rect=None):
        """Tegn hele kabelmærkningen med størst mulig læsbar font."""
        label_rect=QRectF(label_rect) if label_rect is not None else QRectF(rect.left()+36,rect.top()+3,rect.width()-41,31)
        base=p.font()
        for size in (8.4,8.1,7.8,7.5,7.2,6.9,6.6,6.3):
            font=QFont(base); font.setPointSizeF(size); font.setBold(True)
            metrics=QFontMetricsF(font)
            lines=self._wrap_port_label(text,metrics,label_rect.width(),2)
            line_h=metrics.height()
            if len(lines)<=2 and all(metrics.horizontalAdvance(line)<=label_rect.width()+0.5 for line in lines) and line_h*len(lines)<=label_rect.height()+1.0:
                p.setPen(color); p.setFont(font)
                if len(lines)==1:
                    p.drawText(label_rect,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,lines[0])
                else:
                    y=label_rect.top()+(label_rect.height()-line_h*2)/2.0
                    for line in lines:
                        p.drawText(QRectF(label_rect.left(),y,label_rect.width(),line_h+1),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,line)
                        y+=line_h
                return
        # Ekstremt lange brugerlabels: gå ned til tre kompakte linjer før vi
        # accepterer at selve kortets fysiske størrelse er den sidste grænse.
        # Dermed bevares hele mærkningen også ved usædvanligt lange navne.
        for size in (6.2,5.9,5.6,5.3):
            font=QFont(base); font.setPointSizeF(size); font.setBold(True); metrics=QFontMetricsF(font)
            lines=self._wrap_port_label(text,metrics,label_rect.width(),3)
            line_h=metrics.height()
            if len(lines)<=3 and all(metrics.horizontalAdvance(line)<=label_rect.width()+0.5 for line in lines) and line_h*len(lines)<=label_rect.height()+1.0:
                p.setPen(color); p.setFont(font)
                y=label_rect.top()+(label_rect.height()-line_h*len(lines))/2.0
                for line in lines:
                    p.drawText(QRectF(label_rect.left(),y,label_rect.width(),line_h+1),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,line)
                    y+=line_h
                return
        font=QFont(base); font.setPointSizeF(5.1); font.setBold(True); metrics=QFontMetricsF(font)
        lines=self._wrap_port_label(text,metrics,label_rect.width(),3)
        p.setPen(color); p.setFont(font)
        line_h=min(9.0,metrics.height()); y=label_rect.top()+(label_rect.height()-line_h*len(lines))/2.0
        for line in lines:
            p.drawText(QRectF(label_rect.left(),y,label_rect.width(),line_h+1),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,line)
            y+=line_h

    def _function_title(self,fid):
        fid=str(fid or "")
        if fid=="":return "IKKE FORDELT"
        if fid=="pe":return "PE"
        if fid=="n":return "N"
        if fid=="l":return "FAST FASE L"
        if fid=="com":return "COM"
        if fid=="dimmed_out":return "DÆMPET UDGANG ~"
        if fid=="reserve":return "RESERVE"
        if fid=="unused":return "IKKE TILSLUTTET"
        if fid.startswith("switch:"):
            letter=fid.split(":",1)[1]
            if core.normalize_pl_outlet_type(self._outlet_type)=="nordtronic_zigbee":
                return f"P · TRYK {letter}" if letter and letter!="lamp" else "P · TRYKINDGANG"
            return f"TÆNDING {letter}" if letter and letter!="lamp" else "TÆNDING"
        if fid.startswith("traveller:"):
            bits=fid.split(":"); letter=bits[1] if len(bits)>1 else ""; index=bits[2] if len(bits)>2 else "1"
            return f"MELLEMLEDER {index}"+(f" · {letter}" if letter else "")
        if fid.startswith("custom:"):return fid.split(":",1)[1].upper()
        return core.pl_wiring_function_caption(fid,outlet_type=self._outlet_type).upper()

    def _function_subtitle(self,fid):
        fid=str(fid or "")
        if fid=="pe":return "Lampested PE"
        if fid=="n":return "Lampested N"
        if fid=="l":return "Permanent forsyning"
        if fid=="com":return "Fælles/reference til lavspændingstryk"
        if fid=="dimmed_out":return "Dæmpet udgang til lampelast"
        if fid=="reserve":return "Ledig leder"
        if fid=="unused":return "Afsluttet / isoleret"
        if fid=="":return "Vælg funktion"
        if fid.startswith("switch:"):
            req=[r for r in self._requirements if str(r.get("function_id","") or "")==fid and r.get("direct")]
            if len(req)==1:
                r=req[0]
                source=" · ".join(x for x in [str(r.get("source_mark","") or ""),str(r.get("channel_caption","") or "")] if x)
                return source or "Afbryderkanal"
            letter=fid.split(":",1)[1]
            return f"Lampested L({letter})" if letter and letter!="lamp" else "Lampested L"
        if fid.startswith("traveller:"):
            bits=fid.split(":"); letter=bits[1] if len(bits)>1 else ""; index=bits[2] if len(bits)>2 else "1"
            return f"Mellemleder {index} i tændingskreds {letter}" if letter else f"Mellemleder {index}"
        return ""

    @staticmethod
    def _compact_function_label(fid):
        fid=str(fid or "")
        if fid.startswith("switch:"):
            letter=fid.split(":",1)[1]
            return f"T {letter}" if letter and letter!="lamp" else "T"
        if fid.startswith("traveller:"):
            bits=fid.split(":"); letter=bits[1] if len(bits)>1 else ""; index=bits[2] if len(bits)>2 else "1"
            return "ML "+((letter+"/") if letter else "")+index
        return {"pe":"PE","n":"N","l":"L","reserve":"R","unused":"X"}.get(fid,fid.upper())

    def _requirement_state(self,fid):
        rows=[r for r in self._requirements if str(r.get("function_id","") or "")==str(fid or "")]
        if not rows:return ""
        states={str(r.get("state","") or "") for r in rows}
        for state in ("duplicate","wrong_cable","missing","manual","ok"):
            if state in states:return state
        return next(iter(states),"")

    @staticmethod
    def _target_palette(fid,state,active=False,hover=False):
        # Farverne er betydningsbærende og ligger tæt på almindelig dansk
        # installationsnotation. I mørk tilstand bruges mørke tonede flader,
        # men den semantiske PE/N/L-farve bevares i kant og ledergrafik.
        dark=_application_dark()
        if dark:
            if fid=="pe": fill,border=("#26331f","#88bd4d")
            elif fid=="n": fill,border=("#203249","#5b9df2")
            elif fid=="l": fill,border=("#382e1d","#c4925a")
            elif fid=="com": fill,border=("#2f2440","#a78bfa")
            elif fid=="dimmed_out": fill,border=("#3b2b1c","#f0a34a")
            elif fid=="reserve": fill,border=("#282e35","#8d99a8")
            elif fid=="unused": fill,border=("#242a30","#737f8d")
            elif fid=="": fill,border=("#382d20","#e5a34a")
            else: fill,border=("#262d35","#8592a1")
        else:
            if fid=="pe": fill,border=("#ecfccb","#65a30d")
            elif fid=="n": fill,border=("#dbeafe","#2563eb")
            elif fid=="l": fill,border=("#fef3c7","#92400e")
            elif fid=="reserve": fill,border=("#f1f5f9","#64748b")
            elif fid=="unused": fill,border=("#f8fafc","#94a3b8")
            elif fid=="": fill,border=("#fff7ed","#f59e0b")
            else: fill,border=("#f8fafc","#475569")
        if state=="ok": border="#4fb970" if dark else "#16a34a"
        elif state in {"missing","wrong_cable"}: border="#e3a04f" if dark else "#d97706"
        elif state=="duplicate": border="#ef7777" if dark else "#dc2626"
        elif state=="manual": border="#b68af2" if dark else "#7c3aed"
        if active:
            fill,border=(("#263b4e","#59b7ea") if dark else ("#e0f2fe","#0284c7"))
        elif hover:
            fill="#293948" if dark else "#f0f9ff"
        return QColor(fill),QColor(border)

    @staticmethod
    def _draw_core(painter, center, meta, radius=7.5, selected=False, hover=False, dimmed=False, emphasized=False):
        color=QColor(str(meta.get("color","#64748b") or "#64748b"))
        if dimmed:color.setAlpha(72)
        dark=_application_dark()
        outline=QColor("#4bc2f1") if selected else (QColor("#aeb8c4") if dark and not hover else (QColor("#334155") if not hover else QColor("#55c7f3")))
        if dimmed:outline.setAlpha(80)
        elif emphasized and not selected:outline=QColor("#0ea5e9")
        painter.setPen(QPen(outline,2.8 if selected else (2.2 if emphasized and not dimmed else 1.3))); painter.setBrush(color)
        painter.drawEllipse(QRectF(center.x()-radius,center.y()-radius,radius*2,radius*2))
        core_id=str(meta.get("core_id","") or "")
        if core_id=="pe":
            # Gul/grøn vises med to tydelige farver i stedet for kun et label.
            yellow=QColor("#facc15"); yellow.setAlpha(72 if dimmed else 255)
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(yellow)
            painter.drawPie(QRectF(center.x()-radius+1,center.y()-radius+1,(radius-1)*2,(radius-1)*2),45*16,180*16)
        if str(meta.get("color_name","")).lower()=="hvid":
            white=QColor("#ffffff"); white.setAlpha(78 if dimmed else 255)
            edge=QColor("#64748b"); edge.setAlpha(80 if dimmed else 255)
            painter.setPen(QPen(edge,1.0)); painter.setBrush(white); painter.drawEllipse(QRectF(center.x()-radius+1,center.y()-radius+1,(radius-1)*2,(radius-1)*2))
        text_color=QColor(str(meta.get("text_color","#ffffff") or "#ffffff")); text_color.setAlpha(75 if dimmed else 255)
        painter.setPen(text_color)
        f=painter.font(); f.setPointSizeF(6.3); f.setBold(True); painter.setFont(f)
        label=str(meta.get("short_label") or meta.get("label") or "")
        if len(label)<=3:
            painter.drawText(QRectF(center.x()-radius,center.y()-radius,radius*2,radius*2),Qt.AlignmentFlag.AlignCenter,label)

    @staticmethod
    def _draw_external_allocation_marker(painter,center,hint,dimmed=False):
        """Tegn et kædeled: brugt andetsteds, men endnu ikke samlet lokalt."""
        conflict=bool((hint or {}).get("conflict"))
        color=QColor("#ef7777" if (_application_dark() and conflict) else ("#dc2626" if conflict else ("#63b3ed" if _application_dark() else "#2563eb")))
        if dimmed:color.setAlpha(75)
        fill=QColor("#20262d") if _application_dark() else QColor("#ffffff")
        fill.setAlpha(90 if dimmed else 255)
        painter.save(); painter.translate(center); painter.rotate(-28)
        painter.setPen(QPen(color,2.0)); painter.setBrush(fill)
        painter.drawRoundedRect(QRectF(-10.5,-5.0,12.5,10.0),5.0,5.0)
        painter.drawRoundedRect(QRectF(-2.0,-5.0,12.5,10.0),5.0,5.0)
        painter.restore()

    @staticmethod
    def _auto_route_guides(body,starts,targets):
        """Fordel lange lederforløb i rolige grafiske spor med færre kryds.

        Top- og bundindføringer får hver sin routing-zone. Inden for zonen
        sorteres sporene efter slutpunktets Y-position, så ledere der skal til
        samme/tilstødende terminaler løber mere parallelt og krydser mindre.
        """
        guides={}; center_y=body.center().y()
        groups={"top":[],"bottom":[]}
        for key,end in (targets or {}).items():
            start=starts.get(key)
            if start is None or end is None:continue
            if float(end.x()-start.x())<150.0:continue
            groups["top" if start.y()<center_y else "bottom"].append((key,QPointF(start),QPointF(end)))
        for name,rows in groups.items():
            if not rows:continue
            # Slutmål først og fysisk indføringsrækkefølge derefter giver en
            # stabil rute, når dialogen genberegnes.
            rows.sort(key=lambda item:(item[2].y(),item[1].x()))
            if name=="top":
                lo=body.top()+50.0; hi=max(lo+12.0,center_y-18.0); base_x=body.right()-178.0
            else:
                lo=min(body.bottom()-62.0,center_y+18.0); hi=max(lo+12.0,body.bottom()-50.0); base_x=body.right()-132.0
            n=len(rows)
            for idx,(key,start,end) in enumerate(rows):
                lane_y=(lo+hi)/2.0 if n==1 else lo+(hi-lo)*(idx/(n-1))
                # Stop før målet, og sørg samtidig for at sporet ligger tydeligt
                # til højre for indføringen. Flyttede Wago'er tæt på indføringen
                # bruger fortsat den almindelige direkte Bézier-kurve.
                # En lille vandret forskydning pr. spor forhindrer, at kurver
                # med næsten samme start/slut ligger præcist oven på hinanden.
                gx=min(base_x-(n-1-idx)*5.0,end.x()-58.0)
                gx=max(start.x()+64.0,gx)
                if gx<end.x()-24.0:
                    guides[key]=QPointF(gx,lane_y)
        return guides

    @staticmethod
    def _draw_curve(painter,start,end,color,width=5.8,selected=False,alpha=245,emphasized=False,dimmed=False,guide=None,progress=1.0):
        """Tegn en tydelig leder; valgfrit routing-spor giver færre kryds."""
        c=QColor(color)
        if dimmed:
            alpha=min(int(alpha),72); width=max(3.2,float(width)*0.76)
        c.setAlpha(alpha)
        path=QPainterPath(start)
        direction=1.0 if end.x()>=start.x() else -1.0
        vertical_dir=1.0 if end.y()>=start.y() else -1.0
        if guide is not None:
            guide=QPointF(guide)
            first_vertical=max(48.0,min(98.0,abs(guide.y()-start.y())*0.58+22.0))
            cp1=QPointF(start.x(),start.y()+(1.0 if guide.y()>=start.y() else -1.0)*first_vertical)
            cp2=QPointF(guide.x()-direction*64.0,guide.y())
            path.cubicTo(cp1,cp2,guide)
            cp3=QPointF(guide.x()+direction*58.0,guide.y())
            final_run=min(112.0,max(62.0,abs(end.x()-guide.x())*0.48))
            cp4=QPointF(end.x()-direction*final_run,end.y())
            path.cubicTo(cp3,cp4,end)
        elif abs(end.x()-start.x())<90.0 and abs(end.y()-start.y())<90.0:
            # Korte, løse lederender skal ikke lave en stor Bézier-løkke.
            mid_y=(start.y()+end.y())/2.0
            path.cubicTo(QPointF(start.x(),mid_y),QPointF(end.x(),mid_y),end)
        else:
            # Én sammenhængende Bézier-kurve til korte eller frit flyttede mål.
            vertical_run=max(54.0,min(112.0,abs(end.y()-start.y())*0.42+26.0))
            cp1=QPointF(start.x(),start.y()+vertical_dir*vertical_run)
            horizontal_run=min(128.0,max(82.0,abs(end.x()-start.x())*0.31))
            cp2=QPointF(end.x()-direction*horizontal_run,end.y())
            path.cubicTo(cp1,cp2,end)

        render_path=path
        try:progress=max(0.0,min(1.0,float(progress)))
        except Exception:progress=1.0
        if progress<0.995:
            # Qt has no universally available trimmed-path API across our supported builds.
            # Approximate the visible part with pointAtPercent; hit testing still uses the full path.
            partial=QPainterPath(path.pointAtPercent(0.0)); steps=max(3,int(42*max(progress,0.08)))
            for i in range(1,steps+1):partial.lineTo(path.pointAtPercent(progress*i/steps))
            render_path=partial
        halo_alpha=70 if dimmed else 225
        if _application_dark():
            # På mørke diagrammer får sorte/mørke ledere en lys kant, mens
            # øvrige ledere får en mørk kant. Så kan både sort og hvid aflæses.
            halo_color=QColor("#b7c0ca") if c.lightness()<82 else QColor("#12171d")
            halo_color.setAlpha(70 if dimmed else (185 if c.lightness()<82 else 215))
        else:
            halo_color=QColor(255,255,255,halo_alpha)
        halo=QPen(halo_color,width+4.2+(2.0 if selected else 0.0))
        halo.setCapStyle(Qt.PenCapStyle.RoundCap); halo.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(halo); painter.setBrush(Qt.BrushStyle.NoBrush); painter.drawPath(render_path)
        if c.lightness()>235:
            under_color=QColor("#64748b"); under_color.setAlpha(80 if dimmed else 255)
            under=QPen(under_color,width+2.2+(1.8 if selected else 0.0))
            under.setCapStyle(Qt.PenCapStyle.RoundCap); under.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(under); painter.drawPath(render_path)
        if emphasized and not dimmed:
            glow_color=QColor(color); glow_color.setAlpha(78)
            glow=QPen(glow_color,width+6.2)
            glow.setCapStyle(Qt.PenCapStyle.RoundCap); glow.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(glow); painter.drawPath(render_path)
        if selected:
            focus=QPen(QColor(56,189,248,105),width+4.8)
            focus.setCapStyle(Qt.PenCapStyle.RoundCap); focus.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(focus); painter.drawPath(render_path)
        pen=QPen(c,width+1.8 if selected else width+(1.0 if emphasized and not dimmed else 0.0))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen); painter.drawPath(render_path)
        if QColor(color).name().lower()=="#16a34a":
            stripe_color=QColor("#facc15"); stripe_color.setAlpha(75 if dimmed else 255)
            stripe=QPen(stripe_color,max(1.8,width*0.36))
            stripe.setStyle(Qt.PenStyle.DashLine); stripe.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(stripe); painter.drawPath(render_path)
        return path

    def _terminal_layout(self, terminal_panel, profile):
        """Placér terminalerne som en lodret, ekstern klemrække til højre.

        Compact mode reduces the visual mass of the outlet block while detailed
        mode keeps the previous roomy presentation.
        """
        terminals=list(profile.get("terminals") or [])
        detailed=self.detail_mode()
        title_h=52.0 if detailed else 39.0
        bottom_pad=12.0 if detailed else 8.0
        gap=6.0 if detailed else 4.0
        side_pad=12.0 if detailed else 8.0
        inner=terminal_panel.adjusted(side_pad,title_h,-side_pad,-bottom_pad)
        count=max(1,len(terminals))
        min_row=43.0 if detailed else 31.0
        row_h=max(min_row,(inner.height()-gap*(count-1))/count)
        items=[]
        for idx,terminal in enumerate(terminals):
            rect=QRectF(inner.left(),inner.top()+idx*(row_h+gap),inner.width(),row_h)
            items.append((dict(terminal),rect))
        return terminal_panel,items

    @staticmethod
    def _terminal_connected_keys(fid,wiring,conductor_meta):
        rows=[k for k,m in conductor_meta.items() if fid and str(wiring.get(k,{}).get("function","") or "")==fid]
        rows.sort(key=lambda k:(str(conductor_meta[k].get("cable_display") or conductor_meta[k].get("cable_id") or ""),
                                str(conductor_meta[k].get("leg_caption") or ""),
                                str(conductor_meta[k].get("core_id") or "")))
        return rows

    def _terminal_anchor_map(self,terminal_items,wiring,conductor_meta,wago_map=None):
        """Fordel terminalindgange mellem direkte ledere og alle Wago-broer.

        Flere Wago'er kan have samme funktion. Hver Wago med bro bruger derfor
        én fysisk klemmeplads, mens rene sløjfer ikke bruger en terminalplads.
        """
        by_key={}; fallback={}; slots={}; wago_outlet={}
        wago_map=wago_map or {}
        for terminal,rect in terminal_items:
            fid=str(terminal.get("function_id","") or "")
            if not fid: continue
            connected=self._terminal_connected_keys(fid,wiring,conductor_meta)
            infos=[info for info in wago_map.values() if str(info.get("function_id","") or "")==fid]
            member_keys=set()
            outlet_infos=[]
            for info in infos:
                member_keys.update(info.get("members",[]) or [])
                if bool(info.get("connects_to_outlet",True)):outlet_infos.append(info)
            direct=[k for k in connected if k not in member_keys]
            count=max(1,len(direct)+len(outlet_infos))
            span=min(rect.height()-14.0,max(0.0,(count-1)*13.0))
            y0=rect.center().y()-span/2.0
            anchors=[]
            for idx in range(count):
                y=rect.center().y() if count==1 else y0+(span/(count-1))*idx
                anchors.append(QPointF(rect.left()+13.0,y))
            fallback[fid]=anchors[0]
            slots[fid]=anchors
            for key,anchor in zip(direct,anchors):by_key[key]=anchor
            for offset,info in enumerate(outlet_infos):
                idx=len(direct)+offset
                wago_outlet[str(info.get("id","") or "")]=anchors[idx] if idx<len(anchors) else anchors[-1]
        return by_key,fallback,slots,wago_outlet

    @staticmethod
    def _function_color(fid):
        fid=str(fid or "")
        if fid=="pe": return "#16a34a"
        if fid=="n": return "#2563eb"
        if fid=="l": return "#a87943"
        if fid=="com": return "#7c3aed"
        if fid=="dimmed_out": return "#d97706"
        if fid.startswith("switch:"): return "#475569"
        if fid.startswith("traveller:"): return "#64748b"
        return "#64748b"

    def _wago_layout(self,body,terminal_items,wiring,conductor_meta,splices):
        """Placér alle manuelle Wago-samlinger, også flere på samme funktion."""
        terminal_by_fid={str(t.get("function_id","") or ""):dict(t) for t,_r in terminal_items}
        rows=[]
        for splice in core.normalize_pl_box_splices(splices):
            fid=str(splice.get("function","") or "")
            terminal=terminal_by_fid.get(fid)
            connects=bool(splice.get("connects_to_outlet",True))
            if not fid or (connects and terminal is None):continue
            if terminal is None:
                terminal={
                    "label":self._compact_function_label(fid),
                    "subtitle":core.pl_wiring_function_caption(fid),
                    "capacity":0,
                }
            members=[k for k in core.pl_splice_member_keys(splice) if k in conductor_meta and str(wiring.get(k,{}).get("function","") or "")==fid]
            destination_uid=str(splice.get("destination_light_uid","") or "")
            destination_caption=self._destination_labels.get(destination_uid,"")
            rows.append((fid,dict(terminal),members,str(splice.get("id","") or ""),str(splice.get("article_no","") or ""),core.normalize_pl_splice_position(splice.get("position")),connects,destination_uid,destination_caption,str(splice.get("destination_association","") or ""),str(splice.get("conductor_role","") or "")))
        if not rows:return {}
        detailed=self.detail_mode()
        if detailed:
            box_w=min(176.0,max(146.0,body.width()*0.28)); box_h=60.0; gap=10.0
        else:
            # Compact Wago cards behave as secondary connection nodes, not panels.
            box_w=min(132.0,max(108.0,body.width()*0.20)); box_h=38.0; gap=7.0
        auto_x=body.right()-box_w-18.0
        auto_y=max(body.top()+56.0,body.center().y()-(len(rows)*(box_h+gap)-gap)/2.0)
        out={}
        for idx,(fid,terminal,members,sid,article_no,position,connects,destination_uid,destination_caption,destination_association,conductor_role) in enumerate(rows):
            override=self._wago_drag_override.get(sid)
            if override is not None:center=QPointF(override)
            elif position is not None:center=QPointF(body.left()+float(position["x"])*body.width(),body.top()+float(position["y"])*body.height())
            else:center=QPointF(auto_x+box_w/2.0,auto_y+idx*(box_h+gap)+box_h/2.0)
            cx=max(body.left()+box_w/2.0+8.0,min(body.right()-box_w/2.0-8.0,center.x()))
            cy=max(body.top()+box_h/2.0+8.0,min(body.bottom()-box_h/2.0-8.0,center.y()))
            rect=QRectF(cx-box_w/2.0,cy-box_h/2.0,box_w,box_h)
            count=len(members)
            anchor_step=10.0 if detailed else 7.0
            span=min(rect.height()-(14.0 if detailed else 10.0),max(0.0,(count-1)*anchor_step)); y0=rect.center().y()-span/2.0
            input_anchors=[]
            for i in range(count):
                ay=rect.center().y() if count==1 else y0+(span/(count-1))*i
                input_anchors.append(QPointF(rect.left()+(11.0 if detailed else 8.0),ay))
            article_capacity=core.pl_wago_article_capacity(article_no)
            needed_ports=max(1,core.pl_wago_required_ports(len(members),connects))
            out[sid]={"id":sid,"function_id":fid,"rect":rect,"input_anchors":input_anchors,"output_anchor":QPointF(rect.right()-(11.0 if detailed else 8.0),rect.center().y()),
                      "members":members,"capacity":int(terminal.get("capacity") or 0),"label":str(terminal.get("label") or ""),
                      "subtitle":str(terminal.get("subtitle") or ""),"article_no":article_no,"article_capacity":article_capacity,"needed_ports":needed_ports,
                      "color":self._function_color(fid),"position":position,"connects_to_outlet":bool(connects),
                      "destination_light_uid":destination_uid,"destination_caption":destination_caption,
                      "destination_association":destination_association,"conductor_role":conductor_role}
        return out

    def _draw_wago_blocks(self,p,wago_map,wiring,highlight_fid=""):
        dark=_application_dark()
        selected_function=""
        if self._selected_key is not None:
            selected_function=str(wiring.get(tuple(self._selected_key),{}).get("function","") or "")
        for _sid,info in (wago_map or {}).items():
            fid=str(info.get("function_id","") or "")
            rect=QRectF(info["rect"])
            active=(fid==selected_function)
            hover=(fid==self._hover_function or fid==highlight_fid)
            dimmed=bool(highlight_fid and fid!=highlight_fid)
            detailed=self.detail_mode()
            if dark:
                border=QColor("#e0a24e") if not active else QColor("#58b9e8")
                fill=(QColor("#352b20") if detailed else QColor("#292e34")) if not active else QColor("#263b4e")
                title_color=QColor("#f6c36f") if not active else QColor("#8ed4f2")
                detail_color=QColor("#dba05b") if not active else QColor("#72c2e8")
                muted=QColor("#aeb8c3")
                socket_fill=QColor("#20262d"); socket_border=QColor("#c88a3e")
                badge_fill=QColor("#242a31"); badge_border=QColor("#6b7785")
            else:
                border=QColor("#d97706") if not active else QColor("#0284c7")
                fill=(QColor("#fff7ed") if detailed else QColor("#f8fafc")) if not active else QColor("#e0f2fe")
                title_color=QColor("#92400e") if not active else QColor("#0c4a6e")
                detail_color=QColor("#7c2d12") if not active else QColor("#0369a1")
                muted=QColor("#64748b")
                socket_fill=QColor("#ffffff"); socket_border=QColor("#92400e")
                badge_fill=QColor("#ffffff"); badge_border=QColor("#94a3b8")
            if dimmed:border.setAlpha(85); fill.setAlpha(90)
            if not detailed and not active and not hover:
                border.setAlpha(185); fill.setAlpha(205)
            p.setPen(QPen(border,2.4 if active or hover else (1.4 if detailed else 1.0))); p.setBrush(fill); p.drawRoundedRect(rect,8 if detailed else 6,8 if detailed else 6)

            # Wago/samlemuffe is intentionally a secondary object in compact mode.
            connects=bool(info.get("connects_to_outlet",True))
            member_count=len(info.get('members',[]) or [])
            destination=str(info.get("destination_caption") or "").strip()
            destination_assoc=str(info.get("destination_association") or "").strip()
            role=core.normalize_pl_passthrough_role(info.get("conductor_role"),fid)
            requires_destination=role in {"switch","traveller_1","traveller_2"}
            destination_short=destination or ("⚠ destination mangler" if requires_destination else "intern samling")
            article_no=str(info.get('article_no') or '')
            needed=int(info.get('needed_ports',0) or 0); cap=int(info.get('article_capacity',0) or 0)
            if detailed:
                p.setPen(title_color); f=p.font(); f.setPointSizeF(7.5); f.setBold(True); p.setFont(f)
                block_title=f"WAGO · {info['label']}" if connects else f"SAMLEMUFFE · {info['label']}"
                p.drawText(QRectF(rect.left()+23,rect.top()+4,rect.width()-52,14),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,block_title)
                mode_text=f"{member_count} ledere + 1 bro" if connects else f"{member_count} ledere · til {destination_short}"
                p.setPen(detail_color); f.setPointSizeF(6.2); f.setBold(False); p.setFont(f)
                p.drawText(QRectF(rect.left()+23,rect.top()+20,rect.width()-46,12),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,mode_text)
                port_text=f"{needed}/{cap} pladser" if cap else f"{needed}/? pladser"
                article_text=article_no or "ingen artikel"
                p.setPen(muted); f.setPointSizeF(5.8); p.setFont(f)
                p.drawText(QRectF(rect.left()+23,rect.top()+34,rect.width()-46,12),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,f"{port_text} · {article_text}")
                badge=QRectF(rect.right()-38,rect.top()+5,30,16)
            else:
                p.setPen(title_color); f=p.font(); f.setPointSizeF(6.8); f.setBold(True); p.setFont(f)
                block_title=f"WAGO {info['label']}" if connects else f"MUFFE {info['label']}"
                p.drawText(QRectF(rect.left()+17,rect.top()+4,rect.width()-48,13),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,block_title)
                p.setPen(muted); f.setPointSizeF(5.7); f.setBold(False); p.setFont(f)
                compact_meta=f"{member_count}+bro" if connects else f"{member_count} ledere · "+(f"→ {destination_assoc}" if destination and destination_assoc else ("mål?" if requires_destination else "intern"))
                p.drawText(QRectF(rect.left()+17,rect.top()+19,rect.width()-43,11),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,compact_meta)
                badge=QRectF(rect.right()-34,rect.top()+5,27,14)
            p.setPen(QPen(badge_border,1.0)); p.setBrush(badge_fill); p.drawRoundedRect(badge,5,5)
            p.setPen(title_color); f.setPointSizeF(5.8 if detailed else 5.4); f.setBold(True); p.setFont(f)
            p.drawText(badge,Qt.AlignmentFlag.AlignCenter,f"{needed}/{cap or '?'}")

            self._hit_functions.append((QRectF(rect),fid))
            self._hit_splices.append((QRectF(rect),str(info.get("id") or ""),fid))
            for anchor in info['input_anchors']:
                p.setPen(QPen(socket_border,1.2)); p.setBrush(socket_fill)
                radius=5.5 if detailed else 4.2
                p.drawEllipse(QRectF(anchor.x()-radius,anchor.y()-radius,radius*2,radius*2))
            if connects:
                out_anchor=QPointF(info['output_anchor'])
                p.setPen(QPen(socket_border,1.2)); p.setBrush(QColor(info['color']))
                radius=6.0 if detailed else 4.8
                p.drawEllipse(QRectF(out_anchor.x()-radius,out_anchor.y()-radius,radius*2,radius*2))
            if dimmed:
                veil=QColor("#171c22") if dark else QColor("#ffffff"); veil.setAlpha(150 if dark else 145)
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(veil); p.drawRoundedRect(rect,8,8)
            elif highlight_fid and fid==highlight_fid:
                p.setPen(QPen(QColor("#55c7f3") if dark else QColor("#0ea5e9"),2.6)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawRoundedRect(rect.adjusted(-2,-2,2,2),9,9)

    def _draw_terminal_block(self,p,terminal_panel,profile,terminal_items,wiring,conductor_meta,anchor_by_key,slot_map,wago_map=None,highlight_fid=""):
        dark=_application_dark()
        text_main=QColor("#e7edf4") if dark else QColor("#0f172a")
        text_secondary=QColor("#c7d0da") if dark else QColor("#334155")
        text_muted=QColor("#9aa7b5") if dark else QColor("#64748b")
        disabled_text=QColor("#697582") if dark else QColor("#94a3b8")
        panel_border=QColor("#596574") if dark else QColor("#64748b")
        label_fill=QColor("#20262d") if dark else QColor("#ffffff")
        disabled_fill=QColor("#242a30") if dark else QColor("#f8fafc")
        disabled_border=QColor("#424b55") if dark else QColor("#cbd5e1")
        socket_edge=QColor("#9aa7b5") if dark else QColor("#334155")
        empty_socket=QColor("#1c2228") if dark else QColor("#ffffff")

        p.setPen(QPen(panel_border,1.8)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawRoundedRect(terminal_panel,12,12)
        detailed=self.detail_mode()
        p.setPen(text_main); f=p.font(); f.setPointSizeF(10.0 if detailed else 8.2); f.setBold(True); p.setFont(f)
        title_rect=QRectF(terminal_panel.left()+10,terminal_panel.top()+5,terminal_panel.width()-20,21 if detailed else 18)
        p.drawText(title_rect,Qt.AlignmentFlag.AlignCenter,"LAMPEUDTAG · "+str(profile.get("short") or "Lampeudtag"))
        compact_hint=str(profile.get("compact_hint") or profile.get("hint") or "")
        if detailed:
            p.setPen(text_muted); f.setPointSizeF(6.8); f.setBold(False); p.setFont(f)
            p.drawText(QRectF(terminal_panel.left()+14,terminal_panel.top()+29,terminal_panel.width()-28,16),Qt.AlignmentFlag.AlignCenter,compact_hint)

        target_rects={}; target_anchors={}
        selected_function=""
        if self._selected_key is not None:
            selected_function=str(wiring.get(tuple(self._selected_key),{}).get("function","") or "")

        wago_map=wago_map or {}
        for terminal,rect in terminal_items:
            fid=str(terminal.get("function_id","") or "")
            disabled=not bool(fid)
            state=self._requirement_state(fid) if fid else ""
            active=(bool(fid) and self._selected_key is not None and fid==selected_function)
            hover=(bool(fid) and fid==self._hover_function)
            fill,border=self._target_palette(fid,state,active,hover)
            if disabled: fill,border=disabled_fill,disabled_border
            if not detailed and not active and not hover:
                fill.setAlpha(150)
            p.setPen(QPen(border,3.0 if active or hover else (1.4 if detailed else 1.0))); p.setBrush(fill); p.drawRoundedRect(rect,7 if detailed else 6,7 if detailed else 6)

            label_w=56.0 if detailed else 42.0
            label_margin=5.0 if detailed else 4.0
            label_box=QRectF(rect.right()-label_w-8,rect.top()+label_margin,label_w,rect.height()-2*label_margin)
            p.setPen(QPen(border,1.2)); p.setBrush(label_fill if not disabled else disabled_fill); p.drawRoundedRect(label_box,7,7)
            p.setPen(text_main if not disabled else disabled_text); f=p.font(); f.setPointSizeF(12.0 if detailed else 9.5); f.setBold(True); p.setFont(f)
            p.drawText(label_box,Qt.AlignmentFlag.AlignCenter,str(terminal.get("label") or "—"))

            text_left=rect.left()+(31.0 if detailed else 25.0); text_right=label_box.left()-5.0
            p.setPen(text_secondary if not disabled else disabled_text); f.setPointSizeF(7.2 if detailed else 6.4); f.setBold(True); p.setFont(f)
            subtitle=str(terminal.get("subtitle") or "")
            p.drawText(QRectF(text_left,rect.top()+(6 if detailed else 3),max(20.0,text_right-text_left),18 if detailed else rect.height()-6),Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft,subtitle)
            if detailed and fid.startswith("switch:"):
                source=self._function_subtitle(fid)
                if source and source!=str(terminal.get("subtitle") or ""):
                    p.setPen(text_muted); f.setPointSizeF(6.3); f.setBold(False); p.setFont(f)
                    p.drawText(QRectF(text_left,rect.top()+24,max(20.0,text_right-text_left),14),Qt.AlignmentFlag.AlignTop|Qt.AlignmentFlag.AlignLeft|Qt.TextFlag.TextWordWrap,source[:68])

            connected=self._terminal_connected_keys(fid,wiring,conductor_meta) if fid else []
            capacity=int(terminal.get("capacity") or 0) if terminal.get("capacity") else 0
            wago_infos=[info for info in wago_map.values() if str(info.get("function_id","") or "")==fid]
            member_keys=set()
            outlet_wagos=[]; loop_wagos=[]
            for info in wago_infos:
                member_keys.update(info.get("members",[]) or [])
                (outlet_wagos if bool(info.get("connects_to_outlet",True)) else loop_wagos).append(info)
            uses_wago=bool(outlet_wagos); has_loop_wago=bool(loop_wagos)
            direct=[k for k in connected if k not in member_keys]
            anchors=slot_map.get(fid,[]) if fid else []
            if fid and not anchors:anchors=[QPointF(rect.left()+13,rect.center().y())]
            for idx,anchor in enumerate(anchors):
                key=direct[idx] if idx<len(direct) else None
                is_wago_slot=idx>=len(direct) and (idx-len(direct))<len(outlet_wagos)
                meta=conductor_meta.get(key,{}) if key is not None else {}
                c=QColor(str(meta.get("color","#ffffff") or "#ffffff")) if key is not None else empty_socket
                if is_wago_slot:c=QColor(self._function_color(fid))
                p.setPen(QPen(border if key is None else socket_edge,1.5)); p.setBrush(c)
                socket_r=7.5 if detailed else 5.5
                p.drawEllipse(QRectF(anchor.x()-socket_r,anchor.y()-socket_r,socket_r*2,socket_r*2))
                if key is not None and str(meta.get("core_id","") or "")=="pe":
                    pe_r=6.2 if detailed else 4.6
                    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#facc15")); p.drawPie(QRectF(anchor.x()-pe_r,anchor.y()-pe_r,pe_r*2,pe_r*2),45*16,180*16)
                if key is not None and str(meta.get("color_name","")).lower()=="hvid":
                    white_r=6.0 if detailed else 4.5
                    p.setPen(QPen(QColor("#7d8996") if dark else QColor("#64748b"),1.0)); p.setBrush(QColor("#ffffff")); p.drawEllipse(QRectF(anchor.x()-white_r,anchor.y()-white_r,white_r*2,white_r*2))
            if fid and not connected and not outlet_wagos:
                anchor=QPointF(rect.left()+13,rect.center().y())
                empty_r=7.5 if detailed else 5.5
                p.setPen(QPen(disabled_text,1.3)); p.setBrush(empty_socket); p.drawEllipse(QRectF(anchor.x()-empty_r,anchor.y()-empty_r,empty_r*2,empty_r*2))

            if capacity:
                badge=QRectF(label_box.left()-(42 if detailed else 32),rect.top()+(5 if detailed else 4),36 if detailed else 28,16 if detailed else 14)
                terminal_count=len(direct)+len(outlet_wagos)
                if dark:
                    if terminal_count>capacity:
                        bfill,bborder,btxt=QColor("#3a2427"),QColor("#ef7777"),QColor("#ffaaaa")
                    elif uses_wago:
                        bfill,bborder,btxt=QColor("#382d20"),QColor("#e3a04f"),QColor("#f2b765")
                    elif has_loop_wago:
                        bfill,bborder,btxt=QColor("#292f36"),QColor("#7e8996"),QColor("#b9c3ce")
                    else:
                        bfill,bborder,btxt=QColor("#223247"),QColor("#5b8fd0"),QColor("#9ec8f7")
                else:
                    if terminal_count>capacity:
                        bfill,bborder,btxt=QColor("#fef2f2"),QColor("#dc2626"),QColor("#991b1b")
                    elif uses_wago:
                        bfill,bborder,btxt=QColor("#fff7ed"),QColor("#d97706"),QColor("#92400e")
                    elif has_loop_wago:
                        bfill,bborder,btxt=QColor("#f8fafc"),QColor("#94a3b8"),QColor("#475569")
                    else:
                        bfill,bborder,btxt=QColor("#eff6ff"),QColor("#93c5fd"),QColor("#1d4ed8")
                p.setPen(QPen(bborder,1.0)); p.setBrush(bfill); p.drawRoundedRect(badge,5,5)
                p.setPen(btxt); f=p.font(); f.setPointSizeF(6.2 if detailed else 5.5); f.setBold(True); p.setFont(f)
                p.drawText(badge,Qt.AlignmentFlag.AlignCenter,f"{terminal_count}/{capacity}")
                if detailed and uses_wago:
                    p.setPen(QColor("#e9aa5a") if dark else QColor("#92400e")); f.setPointSizeF(6.0); f.setBold(True); p.setFont(f)
                    count_text=f" · {len(outlet_wagos)} samlinger" if len(outlet_wagos)>1 else ""
                    p.drawText(QRectF(text_left,rect.bottom()-15,max(20.0,text_right-text_left),12),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,f"Wago {str(terminal.get('label') or '')} · {len(member_keys)} ledere{count_text}")
                elif detailed and has_loop_wago:
                    p.setPen(text_muted); f.setPointSizeF(6.0); f.setBold(False); p.setFont(f)
                    count_text=f" · {len(loop_wagos)} samlinger" if len(loop_wagos)>1 else ""
                    p.drawText(QRectF(text_left,rect.bottom()-15,max(20.0,text_right-text_left),12),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,f"Wago-sløjfe · {len(member_keys)} ledere{count_text}")

            icon={"ok":"✓","missing":"!","wrong_cable":"!","duplicate":"×","manual":"◇"}.get(state,"")
            if icon:
                if dark:
                    icon_color={"ok":"#6dcc84","missing":"#efad5a","wrong_cable":"#efad5a","duplicate":"#ef7777","manual":"#be99ef"}.get(state,"#9aa7b5")
                else:
                    icon_color={"ok":"#15803d","missing":"#b45309","wrong_cable":"#b45309","duplicate":"#b91c1c","manual":"#7c3aed"}.get(state,"#64748b")
                p.setPen(QColor(icon_color)); f.setPointSizeF(10); f.setBold(True); p.setFont(f)
                p.drawText(QRectF(label_box.left()-22,rect.top()+2,18,18),Qt.AlignmentFlag.AlignCenter,icon)
            if highlight_fid and fid and fid!=highlight_fid:
                veil=QColor("#171c22") if dark else QColor("#ffffff"); veil.setAlpha(160 if dark else 168)
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(veil); p.drawRoundedRect(rect,8,8)
            elif highlight_fid and fid==highlight_fid:
                p.setPen(QPen(QColor("#55c7f3") if dark else QColor("#0ea5e9"),2.8)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawRoundedRect(rect.adjusted(-2,-2,2,2),9,9)
            if fid:
                target_rects[fid]=QRectF(rect); target_anchors[fid]=QPointF(rect.left()+13,rect.center().y()); self._hit_functions.append((QRectF(rect),fid))
        return terminal_panel,target_rects,target_anchors

    def paintEvent(self,event):
        super().paintEvent(event)
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing,True)
        dark=_application_dark()
        text_main=QColor("#e7edf4") if dark else QColor("#0f172a")
        text_secondary=QColor("#c8d1db") if dark else QColor("#475569")
        text_muted=QColor("#9aa7b5") if dark else QColor("#64748b")
        body_fill=QColor("#252c34") if dark else QColor("#f8fafc")
        body_border=QColor("#6f7c8a") if dark else QColor("#475569")
        panel_fill=QColor("#20262d") if dark else QColor("#ffffff")
        panel_border=QColor("#46515e") if dark else QColor("#cbd5e1")
        card_fill=QColor("#252b32") if dark else QColor("#ffffff")
        empty_card_fill=QColor("#22272e") if dark else QColor("#f8fafc")
        card_border=QColor("#586574") if dark else QColor("#64748b")
        badge_fill=QColor("#465566") if dark else QColor("#334155")
        badge_empty=QColor("#65717f") if dark else QColor("#94a3b8")
        body,ports,terminal_area=self._geometry()
        cache=self._state_cache
        profile=cache.get("profile") or core.pl_outlet_profile(self._outlet_type,self._associations)
        port_leg=cache.get("port_leg",{})
        conductors=cache.get("conductors",[])
        conductor_meta=cache.get("conductor_meta",{})
        wiring=cache.get("wiring",{})
        self._hit_conductors=[]; self._hit_wire_paths=[]; self._hit_functions=[]; self._hit_function_paths=[]; self._hit_splices=[]; self._conductor_centers={}
        highlight_fid=self._hover_connection_function()
        wire_stroker=QPainterPathStroker(); wire_stroker.setWidth(16.0)

        # PL-dåsen og klemrækken er to separate grafiske objekter.
        # 0.56.1: selve montagefladen tegnes som et fysisk objekt med en diskret
        # ydre skygge, indvendig kant og fire montagepunkter. Det giver dybde og
        # gør det nemmere at skelne kabelkort, dåse og lampeudtag uden at gøre
        # ledergrafikken dekorativ eller elektrisk misvisende.
        shadow=QRectF(body).translated(0,4)
        shadow_color=QColor(0,0,0,42 if dark else 26)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(shadow_color); p.drawRoundedRect(shadow,25,25)
        p.setPen(QPen(body_border,2.0)); p.setBrush(body_fill); p.drawRoundedRect(body,24,24)
        inner=body.adjusted(7,7,-7,-7)
        inner_border=QColor("#3b4651") if dark else QColor("#dbe2e9")
        p.setPen(QPen(inner_border,1.0)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawRoundedRect(inner,19,19)
        for sx,sy in ((body.left()+18,body.top()+18),(body.right()-18,body.top()+18),(body.left()+18,body.bottom()-18),(body.right()-18,body.bottom()-18)):
            p.setPen(QPen(QColor("#738191") if dark else QColor("#94a3b8"),1.1)); p.setBrush(QColor("#1f252c") if dark else QColor("#eef2f6")); p.drawEllipse(QRectF(sx-4,sy-4,8,8))

        known=len(conductor_meta); assigned=sum(1 for key in conductor_meta if str(wiring.get(key,{}).get("function","") or ""))
        p.setPen(text_muted); f=p.font(); f.setPointSizeF(7.0); f.setBold(True); p.setFont(f)
        p.drawText(QRectF(body.left()+34,body.top()+8,body.width()-160,18),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,"PL LOFTDÅSE · MONTAGESIDE")
        status_rect=QRectF(body.right()-122,body.top()+8,88,20)
        complete=bool(known and assigned==known)
        status_fill=QColor("#234a39") if (dark and complete) else (QColor("#e7f6ed") if complete else (QColor("#313944") if dark else QColor("#eef2f6")))
        status_border=QColor("#57a878") if complete else (QColor("#596675") if dark else QColor("#cbd5e1"))
        status_text=QColor("#8dd5a6") if (dark and complete) else (QColor("#17633a") if complete else text_secondary)
        p.setPen(QPen(status_border,1.0)); p.setBrush(status_fill); p.drawRoundedRect(status_rect,7,7)
        p.setPen(status_text); f.setPointSizeF(6.8); f.setBold(True); p.setFont(f); p.drawText(status_rect,Qt.AlignmentFlag.AlignCenter,f"{assigned}/{known} FORDELT" if known else "INGEN LEDERE")

        terminal_panel,terminal_items=self._terminal_layout(terminal_area,profile)
        terminal_shadow=QRectF(terminal_panel).translated(0,2)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(0,0,0,30 if dark else 18)); p.drawRoundedRect(terminal_shadow,12,12)
        p.setPen(QPen(panel_border,1.2)); p.setBrush(panel_fill); p.drawRoundedRect(terminal_panel,12,12)
        core_positions={}
        # Kabelkort + tykke, farvede lederstumper fra kortet ind i PL-dåsen.
        for port,rect in ports.items():
            leg=port_leg.get(port)
            # Kabelkappen blev tidligere tegnet som en tyk streg midt gennem
            # ledergruppen og lignede derfor en ekstra kappe omkring den
            # midterste leder. I lederfordelingen vises nu kun de faktiske
            # farvede ledere ved indføringen.
            p.setPen(QPen(card_border,1.3)); p.setBrush(card_fill if leg is not None else empty_card_fill); p.drawRoundedRect(rect,7,7)
            if leg is not None:
                accent_rec=self._category_for_leg(leg); accent_color=QColor(str(accent_rec.get("color") or core.DEFAULT_CABLE_COLOR))
                if dark and accent_color.lightness()<82: accent_color=accent_color.lighter(210)
                accent_pen=QPen(accent_color,4.0); accent_pen.setCapStyle(Qt.PenCapStyle.RoundCap); accent_pen.setStyle(PLBoxDiagramWidget._category_pen_style(accent_rec.get("line_style")))
                p.setPen(accent_pen); p.drawLine(QPointF(rect.left()+2,rect.top()+9),QPointF(rect.left()+2,rect.bottom()-9))
            card_layout=self._port_card_layout(rect,port)
            badge=card_layout["badge"]; p.setPen(Qt.PenStyle.NoPen); p.setBrush(badge_fill if leg is not None else badge_empty); p.drawRoundedRect(badge,5,5)
            p.setPen(QColor("#ffffff")); f=p.font(); f.setPointSizeF(8); f.setBold(True); p.setFont(f); p.drawText(badge,Qt.AlignmentFlag.AlignCenter,str(port))
            if leg is None:
                p.setPen(text_muted); f.setPointSizeF(7.2); f.setBold(False); p.setFont(f); p.drawText(card_layout["label"],Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft,"Ledig indføring"); continue
            display=str(leg.get("cable_display") or leg.get("cable_id") or "Kabel"); spec=str(leg.get("cable_spec") or ""); side=str(leg.get("leg_caption") or "")
            category=self._category_for_leg(leg)
            category_name=str(category.get("name") or "Øvrige")
            category_color=QColor(str(category.get("color") or core.DEFAULT_CABLE_COLOR))
            if dark and category_color.lightness()<82:
                category_color=category_color.lighter(225)
            # Hele kabelmærkningen vises. Den må ikke længere blive skåret af
            # med et fast antal tegn; kortet bruger bredde, linjebrud og til
            # sidst en moderat mindre font for at bevare hele brugerens tekst.
            self._draw_port_cable_label(p,rect,display,text_main,card_layout["label"])

            # Sekundær information samles i én kompakt footer. Kabelmærkningen
            # får dermed altid sin egen zone, mens kategori/type/side må elideres
            # før selve brugerens mærkning.
            meta_rect=card_layout["meta"]
            category_pen=QPen(category_color,2.6); category_pen.setCapStyle(Qt.PenCapStyle.RoundCap); category_pen.setStyle(PLBoxDiagramWidget._category_pen_style(category.get("line_style")))
            p.setPen(category_pen); p.drawLine(QPointF(meta_rect.left(),meta_rect.center().y()),QPointF(meta_rect.left()+15,meta_rect.center().y()))
            meta_text=" · ".join(x for x in [category_name,spec,side] if x)
            p.setPen(text_muted); f.setPointSizeF(6.4); f.setBold(False); p.setFont(f)
            fm=QFontMetricsF(f); available=max(12.0,meta_rect.width()-20.0)
            meta_text=fm.elidedText(meta_text,Qt.TextElideMode.ElideRight,available)
            p.drawText(QRectF(meta_rect.left()+20,meta_rect.top(),available,meta_rect.height()),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,meta_text)
            cores=[x for x in conductors if self._leg_key(x)==self._leg_key(leg)]
            if not cores:
                p.setPen(QColor("#f0aa61") if dark else QColor("#b45309")); p.drawText(rect.adjusted(36,0,-5,0),Qt.AlignmentFlag.AlignBottom|Qt.AlignmentFlag.AlignLeft,"Ukendt lederopbygning"); continue
            spacing=min(27.0,(rect.width()-18.0)/max(1,len(cores))); total=spacing*(len(cores)-1); x0=rect.center().x()-total/2
            entry_y=body.top()+30.0 if port<=3 else body.bottom()-30.0; external_y=rect.bottom()-7.0 if port<=3 else rect.top()+7.0
            for i,meta in enumerate(cores):
                center=QPointF(x0+i*spacing,entry_y); ext=QPointF(x0+i*spacing,external_y); key=core.pl_box_conductor_key(meta)
                core_positions[key]=center; self._conductor_centers[key]=center
                lead_color=QColor(str(meta.get("color","#64748b")))
                fid=str(wiring.get(key,{}).get("function","") or "")
                dimmed=bool(highlight_fid and fid!=highlight_fid)
                emphasized=bool(highlight_fid and fid==highlight_fid)
                if dimmed:lead_color.setAlpha(70)
                # 5+ px gør farven synlig allerede før selve fordelingskurven.
                # På mørk UI får sorte/mørke ledere en lys kant; hvide ledere
                # beholder den mørke kant. Det er kun skærmkontrast.
                if lead_color.lightness()>235 or (dark and lead_color.lightness()<82):
                    under=QColor("#b7c0ca") if dark and lead_color.lightness()<82 else QColor("#64748b")
                    under.setAlpha(75 if dimmed else 255)
                    p.setPen(QPen(under,7.4)); p.drawLine(ext,center)
                p.setPen(QPen(lead_color,6.2 if emphasized else 5.4)); p.drawLine(ext,center)
                if str(meta.get("core_id","") or "")=="pe":
                    stripe_color=QColor("#facc15"); stripe_color.setAlpha(75 if dimmed else 255)
                    stripe=QPen(stripe_color,2.2 if emphasized else 2.0); stripe.setStyle(Qt.PenStyle.DashLine); p.setPen(stripe); p.drawLine(ext,center)

        wago_map=self._wago_layout(body,terminal_items,wiring,conductor_meta,self._splices)
        anchor_by_key,fallback_anchors,slot_map,wago_outlet_anchors=self._terminal_anchor_map(terminal_items,wiring,conductor_meta,wago_map)
        wago_anchor_by_key={}
        for _sid,info in wago_map.items():
            for key,anchor in zip(info.get("members",[]),info.get("input_anchors",[])):
                wago_anchor_by_key[key]=QPointF(anchor)

        # Fysiske typebegrænsninger vises som særskilte røde felter i dåsen.
        unsupported=list(profile.get("unsupported_switches") or [])
        unsupported_rects={}
        if unsupported:
            uw=min(205.0,body.width()*0.38); uh=34.0; ux=body.right()-uw-16; uy=body.top()+42
            for idx,fid in enumerate(unsupported):
                r=QRectF(ux,uy+idx*(uh+5),uw,uh); unsupported_rects[fid]=r
                p.setPen(QPen(QColor("#ef7777") if dark else QColor("#dc2626"),1.5)); p.setBrush(QColor("#3a2427") if dark else QColor("#fef2f2")); p.drawRoundedRect(r,6,6)
                p.setPen(QColor("#ffaaaa") if dark else QColor("#991b1b")); f=p.font(); f.setPointSizeF(6.8); f.setBold(True); p.setFont(f)
                letter=fid.split(":",1)[1] if ":" in fid else fid
                p.drawText(r.adjusted(7,2,-6,-2),Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft,f"⚠ Tænding {letter}: ingen fysisk klemme")
                fallback_anchors[fid]=QPointF(r.right()-8,r.center().y())

        # Automatisk grafisk routing: lange forbindelser får et roligt spor
        # baseret på slutpunktets højde. Det reducerer især kryds mellem de
        # mange parallelle PE/N/L-forbindelser fra top- og bundindføringer.
        route_targets={}
        for key in conductor_meta:
            fid=str(wiring.get(key,{}).get("function","") or "")
            if key in wago_anchor_by_key:route_targets[key]=QPointF(wago_anchor_by_key[key])
            elif key in anchor_by_key:route_targets[key]=QPointF(anchor_by_key[key])
            elif fid in fallback_anchors:route_targets[key]=QPointF(fallback_anchors[fid])
        route_guides=self._auto_route_guides(body,core_positions,route_targets)

        # De tykke ledere tegnes først. Ved hover fremhæves hele den elektriske
        # forbindelse, mens de øvrige forbindelser tones ned.
        loose_markers=[]
        for key,meta in conductor_meta.items():
            start=core_positions.get(key)
            if start is None: continue
            fid=str(wiring.get(key,{}).get("function","") or ""); flash=(tuple(key)==getattr(self,"_flash_key",None)); selected=(tuple(key)==self._selected_key) or flash
            dimmed=bool(highlight_fid and fid!=highlight_fid)
            emphasized=bool(highlight_fid and fid==highlight_fid) or flash
            draw_progress=float(getattr(self,"_flash_progress",1.0)) if flash else 1.0
            if key in wago_anchor_by_key:
                path=self._draw_curve(p,start,wago_anchor_by_key[key],str(meta.get("color","#64748b")),6.2,selected,250 if selected else 238,emphasized,dimmed,route_guides.get(key),draw_progress)
            elif key in anchor_by_key:
                path=self._draw_curve(p,start,anchor_by_key[key],str(meta.get("color","#64748b")),6.2,selected,250 if selected else 238,emphasized,dimmed,route_guides.get(key),draw_progress)
            elif fid in fallback_anchors:
                path=self._draw_curve(p,start,fallback_anchors[fid],str(meta.get("color","#64748b")),6.2,selected,250 if selected else 238,emphasized,dimmed,route_guides.get(key),draw_progress)
            else:
                marker={"reserve":"R","unused":"X","":"?"}.get(fid,"?")
                # Løse ender bliver ved deres egen indføring. Tidligere blev de
                # trukket ind mod midten, hvor både kurver og ?-markører kunne
                # ligge oven på andre ledere.
                top=start.y()<body.center().y()
                x_end=max(body.left()+28.0,min(body.right()-28.0,start.x()+30.0))
                base=42.0 if top else -42.0
                extra={"reserve":-8.0,"unused":8.0,"":0.0}.get(fid,0.0)
                y_end=max(body.top()+34.0,min(body.bottom()-34.0,start.y()+base+extra))
                end=QPointF(x_end,y_end)
                path=self._draw_curve(p,start,end,str(meta.get("color","#64748b")),5.8 if fid in {"reserve","unused",""} else 5.6,selected,240 if fid in {"reserve","unused",""} else 235,emphasized,dimmed,None,draw_progress)
                loose_markers.append((QPointF(end),marker,dict(self._external_allocations.get(tuple(key),{})),dimmed))
            if path is not None:
                self._hit_wire_paths.append((wire_stroker.createStroke(path),key))

        # Markørerne tegnes efter alle lederkurver. Et blåt kædeled betyder, at
        # samme fysiske leder allerede har en funktion ved kablets anden ende;
        # et ? betyder fortsat helt ufordelt.
        for end,marker,allocation,dimmed in loose_markers:
            if allocation.get("functions"):
                self._draw_external_allocation_marker(p,end,allocation,dimmed)
                continue
            marker_pen=(QColor("#8895a3") if dark else QColor("#94a3b8")) if marker!="?" else (QColor("#e8ab53") if dark else QColor("#f59e0b"))
            marker_text=(QColor("#c3ccd6") if dark else QColor("#64748b")) if marker!="?" else (QColor("#efb765") if dark else QColor("#b45309"))
            if dimmed:marker_pen.setAlpha(75); marker_text.setAlpha(75)
            marker_fill=QColor("#20262d") if dark else QColor("#ffffff"); marker_fill.setAlpha(90 if dimmed else 255)
            p.setPen(QPen(marker_pen,1.5)); p.setBrush(marker_fill); p.drawEllipse(QRectF(end.x()-8,end.y()-8,16,16))
            p.setPen(marker_text); f=p.font(); f.setPointSizeF(7.6); f.setBold(True); p.setFont(f)
            p.drawText(QRectF(end.x()-8,end.y()-8,16,16),Qt.AlignmentFlag.AlignCenter,marker)

        # Wago-blokke tegnes oven på lederforløbene og forbindes videre til
        # selve lampeudtaget. Hover på leder, terminal eller Wago følger samme
        # funktions-id og fremhæver derfor hele forbindelsen.
        self._draw_wago_blocks(p,wago_map,wiring,highlight_fid)
        for sid,info in wago_map.items():
            fid=str(info.get("function_id","") or "")
            terminal_anchor=wago_outlet_anchors.get(str(sid))
            if terminal_anchor is not None:
                dimmed=bool(highlight_fid and fid!=highlight_fid); emphasized=bool(highlight_fid and fid==highlight_fid)
                path=self._draw_curve(p,QPointF(info.get("output_anchor")),QPointF(terminal_anchor),str(info.get("color","#64748b")),4.2,False,210,emphasized,dimmed)
                if path is not None:self._hit_function_paths.append((wire_stroker.createStroke(path),fid))

        # Terminalrækkerne tegnes til sidst oven på ledernes ender.
        _panel,target_rects,_target_anchors=self._draw_terminal_block(p,terminal_panel,profile,terminal_items,wiring,conductor_meta,anchor_by_key,slot_map,wago_map,highlight_fid)
        # Funktionens primære hit-rect er terminalen; Wago'erne har deres egne
        # hit-zoner via _hit_splices og behøver ikke overskrive hinanden her.
        self._function_rects={**target_rects,**unsupported_rects}

        # Store ledergreb ved indføringerne gør både farve og klikområde tydeligt.
        for key,meta in conductor_meta.items():
            center=core_positions.get(key)
            if center is None: continue
            selected=(tuple(key)==self._selected_key); hover=(tuple(key)==self._hover_key)
            fid=str(wiring.get(key,{}).get("function","") or "")
            dimmed=bool(highlight_fid and fid!=highlight_fid); emphasized=bool(highlight_fid and fid==highlight_fid)
            self._draw_core(p,center,meta,11.5 if selected else 10.0,selected,hover,dimmed,emphasized)
            self._hit_conductors.append((QRectF(center.x()-17,center.y()-17,34,34),key))

        if self._drag_key is not None and self._drag_pos is not None:
            start=self._conductor_centers.get(tuple(self._drag_key)); meta=conductor_meta.get(tuple(self._drag_key),{})
            if start is not None: self._draw_curve(p,start,QPointF(self._drag_pos),str(meta.get("color","#0ea5e9")),6.4,True,210)

        if self._selected_key is not None:
            meta=conductor_meta.get(tuple(self._selected_key),{}); wr=wiring.get(tuple(self._selected_key),{})
            cable=str(meta.get("cable_display") or meta.get("cable_id") or "Kabel"); cname=str(meta.get("color_name") or meta.get("display") or meta.get("core_id") or "leder")
            fid=str(wr.get("function","") or ""); text=f"{cable} · {cname}  →  {self._function_title(fid)}"
            p.setPen(text_secondary); f=p.font(); f.setPointSizeF(8.1); f.setBold(True); p.setFont(f)
            p.drawText(QRectF(12,self.height()-27,self.width()-24,20),Qt.AlignmentFlag.AlignCenter,text)

class PLBoxDialog(SwitchConductorUsageMixin, QDialog):
    """Konfigurator for de seks fysiske kabelindføringer i et PL-lampested."""

    def __init__(self, parent, placement, cables, apply_callback=None, placements=None, cable_categories=None):
        super().__init__(parent)
        self.placement=placement
        self.cables=list(cables or [])
        self.placements=list(placements or [])
        self.cable_categories=core.normalize_cable_category_records(cable_categories)
        self.apply_callback=apply_callback
        self.legs=core.cable_legs_at_symbol(self.cables,placement.uid)
        self.entries=core.reconcile_pl_box_entries(getattr(placement,"pl_box_entries",{}),self.legs)
        self.wiring=core.reconcile_pl_box_wiring(getattr(placement,"pl_box_wiring",[]),self.legs)
        self.splices=core.reconcile_pl_box_splices(getattr(placement,"pl_box_splices",[]),self.wiring,self.legs)
        self.outlet_type=core.normalize_pl_outlet_type(getattr(placement,"lamp_outlet_type","generic"))
        self.orientation=core.normalize_pl_box_orientation(getattr(placement,"pl_box_orientation",0))
        self.field_record=core.normalize_pl_field_record(getattr(placement,"pl_field_record",{}))
        self.selected_conductor_key=None
        self.requirements=core.pl_expected_switch_connections(placement,self.placements,self.cables)
        self.selected_port=1
        configure_modern_dialog(self,title="PL loftdåse – kabelindføringer og lampeudtag",minimum_size=(900,600))
        _resize_dialog(self,1240,820)

        root=QVBoxLayout(self); root.setContentsMargins(12,12,12,12); root.setSpacing(10)
        head=QHBoxLayout()
        title=QLabel("PL loftdåse"); title.setObjectName("sectionTitle"); head.addWidget(title)
        head.addStretch(1)
        group=str(getattr(placement,"group","") or "").strip()
        label=str(getattr(placement,"label","") or "").strip()
        ident=core.placement_identification_caption(placement)
        self.head_ident=QLabel(ident); self.head_ident.setObjectName("accentText")
        self.head_ident.setToolTip(f"Gruppe/kreds: {group or '—'}\nMærkning: {label or '—'}")
        head.addWidget(self.head_ident)
        root.addLayout(head)
        self.status_label=QLabel(); self.status_label.setWordWrap(True); root.addWidget(self.status_label)

        field_row=QHBoxLayout(); field_row.setSpacing(7)
        field_title=QLabel("Feltregistrering:"); field_title.setObjectName("sectionTitle"); field_row.addWidget(field_title)
        self.field_status=QLabel(); self.field_status.setWordWrap(True); field_row.addWidget(self.field_status,1)
        self.field_import_btn=QPushButton("Hent / opdatér fra PWA…"); self.field_import_btn.clicked.connect(self._import_field_record); field_row.addWidget(self.field_import_btn)
        self.field_photos_btn=_set_role(QPushButton("Vis fotos…"),"quietButton"); self.field_photos_btn.clicked.connect(self._show_field_photos); field_row.addWidget(self.field_photos_btn)
        self.field_unlink_btn=_set_role(QPushButton("Fjern tilknytning"),"quietButton"); self.field_unlink_btn.clicked.connect(self._unlink_field_record); field_row.addWidget(self.field_unlink_btn)
        root.addLayout(field_row)

        self.tabs=QTabWidget(); root.addWidget(self.tabs,1)

        # --- Kabelindføringer -------------------------------------------------
        entry_tab=QWidget(); entry_root=QVBoxLayout(entry_tab); entry_root.setContentsMargins(8,8,8,8); entry_root.setSpacing(8)
        orientation_row=QHBoxLayout(); orientation_row.setSpacing(8)
        orientation_label=QLabel("Fysisk orientering:"); orientation_label.setObjectName("sectionTitle"); orientation_row.addWidget(orientation_label)
        self.orientation_combo=QComboBox()
        for angle,caption in core.PL_BOX_ORIENTATIONS.items():self.orientation_combo.addItem(caption,angle)
        oi=self.orientation_combo.findData(self.orientation); self.orientation_combo.setCurrentIndex(max(0,oi)); self.orientation_combo.setMinimumWidth(285)
        self.orientation_combo.setToolTip("Orienteringen er relativ til plantegningens top og ændrer kun den fysiske placering af indføring 1-6 - ikke kabeltilknytningerne.")
        self.orientation_combo.currentIndexChanged.connect(self._orientation_changed); orientation_row.addWidget(self.orientation_combo)
        self.orientation_rotate_btn=_set_role(QPushButton("Rotér 90°"),"quietButton"); self.orientation_rotate_btn.clicked.connect(self._rotate_orientation); orientation_row.addWidget(self.orientation_rotate_btn)
        orientation_note=QLabel("Visning set fra rummet/mod montagesiden"); orientation_note.setObjectName("subtleText"); orientation_row.addWidget(orientation_note)
        orientation_row.addStretch(1); entry_root.addLayout(orientation_row)
        body=QHBoxLayout(); body.setSpacing(14)
        self.diagram=PLBoxDiagramWidget(); self.diagram.set_orientation(self.orientation); body.addWidget(self.diagram,3)

        side=QVBoxLayout(); side.setSpacing(8)
        sh=QLabel("Kabelben ved lampestedet"); sh.setObjectName("sectionTitle"); side.addWidget(sh)
        hint=QLabel("Et gennemgående kabel bruger to indføringer (Side A + Side B). Træk et kabelben til en indføring, eller brug knappen nedenfor.")
        hint.setWordWrap(True); hint.setObjectName("sectionHint"); side.addWidget(hint)
        self.category_legend=QLabel(); self.category_legend.setWordWrap(True); self.category_legend.setObjectName("subtleText")
        self.category_legend.setToolTip("Kabelkategorierne er de samme som på plantegningen. Farve og kontur styres via Vis → Kabelkategorier / Konfigurér kabelkategorier…")
        side.addWidget(self.category_legend)
        self.leg_list=QListWidget(); self.leg_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.leg_list.setDragEnabled(True); self.leg_list.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.leg_list.itemSelectionChanged.connect(self._leg_selection_changed)
        side.addWidget(self.leg_list,1)

        self.unplaced_label=QLabel(); self.unplaced_label.setWordWrap(True); side.addWidget(self.unplaced_label)
        actions=QHBoxLayout()
        self.place_btn=QPushButton("Placér i valgt indføring"); self.place_btn.clicked.connect(self._place_selected)
        self.remove_btn=_set_role(QPushButton("Fjern fra indføring"),"quietButton"); self.remove_btn.clicked.connect(self._remove_selected_port)
        actions.addWidget(self.place_btn,1); actions.addWidget(self.remove_btn)
        side.addLayout(actions)

        detail=QGroupBox("Valgt indføring")
        form=QFormLayout(detail); form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.port_value=QLabel("1")
        self.cable_value=QLabel("Ledig"); self.cable_value.setWordWrap(True)
        self.type_value=QLabel("—"); self.type_value.setWordWrap(True)
        self.category_value=QLabel("—"); self.category_value.setWordWrap(True)
        self.leg_value=QLabel("—")
        self.note_edit=QLineEdit(); self.note_edit.setPlaceholderText("Valgfri montagenote")
        self.note_edit.editingFinished.connect(self._save_note)
        form.addRow("Indføring",self.port_value); form.addRow("Kabel",self.cable_value); form.addRow("Type",self.type_value); form.addRow("Kategori",self.category_value); form.addRow("Forbindelse",self.leg_value); form.addRow("Note",self.note_edit)
        side.addWidget(detail)
        body.addLayout(side,2)
        entry_root.addLayout(body,1)
        entry_actions=QHBoxLayout()
        self.auto_btn=QPushButton("Fordel automatisk"); self.auto_btn.clicked.connect(self._auto_assign)
        self.clear_btn=_set_role(QPushButton("Ryd placeringer"),"quietButton"); self.clear_btn.clicked.connect(self._clear_entries)
        entry_actions.addWidget(self.auto_btn); entry_actions.addWidget(self.clear_btn); entry_actions.addStretch(1)
        entry_root.addLayout(entry_actions)
        self.tabs.addTab(entry_tab,"Kabelindføringer")

        # --- Lederfordeling ---------------------------------------------------
        # 0.50.1: lampeudtagets klemrække er den primære editor. Tabellerne er
        # kun en valgfri detalje-/kontrolvisning og er skjult som standard.
        # Lederfanen kan blive høj på mindre skærme. Scroll kun selve fanens
        # indhold, så OK/Annuller/Anvend altid bliver stående synligt nederst.
        wiring_tab=QScrollArea(); wiring_tab.setWidgetResizable(True); wiring_tab.setFrameShape(QFrame.Shape.NoFrame)
        wiring_tab.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        wiring_page=QWidget(); wiring_root=QVBoxLayout(wiring_page); wiring_root.setContentsMargins(8,7,8,7); wiring_root.setSpacing(5)
        wiring_tab.setWidget(wiring_page)
        profile_row=QHBoxLayout(); profile_row.setSpacing(8)
        profile_label=QLabel("Lampeudtag:"); profile_label.setObjectName("sectionTitle"); profile_row.addWidget(profile_label)
        self.outlet_type_combo=QComboBox()
        for key,caption in core.PL_OUTLET_TYPES.items(): self.outlet_type_combo.addItem(caption,key)
        idx=self.outlet_type_combo.findData(self.outlet_type); self.outlet_type_combo.setCurrentIndex(max(0,idx)); self.outlet_type_combo.setMinimumWidth(245)
        self.outlet_type_combo.currentIndexChanged.connect(self._outlet_type_changed); profile_row.addWidget(self.outlet_type_combo)
        self.graphics_detail_btn=_set_role(QPushButton("Kompakt"),"quietButton"); self.graphics_detail_btn.setCheckable(True)
        self.graphics_detail_btn.setToolTip("Kompakt er standard og prioriterer lederforløbet. Slå til for flere Wago- og terminaldetaljer.")
        profile_row.addWidget(self.graphics_detail_btn)
        self.exploded_btn=_set_role(QPushButton("Eksploderet visning"),"quietButton"); self.exploded_btn.setCheckable(True)
        self.exploded_btn.setToolTip("Giver ekstra afstand mellem kabler, PL-dåse og lampeudtag uden at ændre nogen forbindelser.")
        profile_row.addWidget(self.exploded_btn)
        self.outlet_profile_hint=QLabel(); self.outlet_profile_hint.setObjectName("subtleText"); self.outlet_profile_hint.setWordWrap(False); profile_row.addWidget(self.outlet_profile_hint,1)
        wiring_root.addLayout(profile_row)
        wiring_hint=QLabel("Vælg eller træk en farvet leder → klemme  ·  højreklik for flere handlinger  ·  Ingen forbindelser laves automatisk")
        wiring_hint.setWordWrap(False); wiring_hint.setObjectName("sectionHint"); wiring_root.addWidget(wiring_hint)
        status_row=QHBoxLayout(); status_row.setSpacing(10)
        self.wiring_status_label=QLabel(); self.wiring_status_label.setWordWrap(False); status_row.addWidget(self.wiring_status_label,1)
        assoc=core.light_output_associations(placement)
        self.wiring_assoc_label=QLabel("Tændinger: "+(", ".join(assoc) if assoc else "ingen"))
        self.wiring_assoc_label.setObjectName("subtleText"); self.wiring_assoc_label.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter); status_row.addWidget(self.wiring_assoc_label)
        wiring_root.addLayout(status_row)

        # Handlingslinjen omsætter status til konkrete, klikbare opgaver. Den
        # fylder kun én række og lader lederdiagrammet beholde hovedparten af
        # højden, også på mindre skærme.
        issue_row=QHBoxLayout(); issue_row.setSpacing(7)
        issue_title=QLabel("Næste opgave:"); issue_title.setObjectName("sectionTitle"); issue_row.addWidget(issue_title)
        self.wiring_issue_combo=QComboBox(); self.wiring_issue_combo.setMinimumWidth(310)
        self.wiring_issue_combo.setToolTip("Vælg et problem for at fremhæve den relevante leder eller klemme.")
        self.wiring_issue_combo.activated.connect(self._workflow_issue_selected); issue_row.addWidget(self.wiring_issue_combo,1)
        self.wiring_next_issue_btn=QPushButton("Næste uløste")
        self.wiring_next_issue_btn.setToolTip("Spring til næste uløste punkt (F8)")
        self.wiring_next_issue_btn.clicked.connect(self._next_wiring_issue); issue_row.addWidget(self.wiring_next_issue_btn)
        self.wiring_suggest_btn=QPushButton("Foreslå fordeling…")
        self.wiring_suggest_btn.setToolTip("Vis sikre og mulige forslag. Intet ændres før du godkender forhåndsvisningen.")
        self.wiring_suggest_btn.clicked.connect(self._show_wiring_suggestions); issue_row.addWidget(self.wiring_suggest_btn)
        self.wiring_legend_btn=_set_role(QPushButton("Symboler ▾"),"quietButton")
        legend_menu=QMenu(self.wiring_legend_btn)
        for caption in (
            "✓  Forbundet / korrekt", "🔗  Allokeret ved anden kabelende",
            "?  Helt ufordelt", "⚠  Advarsel eller konflikt",
            "◇  Planlagt / kræver manuel kontrol", "R  Reserve", "X  Ikke tilsluttet",
        ):
            action=legend_menu.addAction(caption); action.setEnabled(False)
        self.wiring_legend_btn.setMenu(legend_menu)
        self.wiring_legend_btn.setToolTip("Forklaring af de grafiske statusmarkører i lederdiagrammet.")
        issue_row.addWidget(self.wiring_legend_btn)
        wiring_root.addLayout(issue_row)
        self._wiring_issue_shortcut=QShortcut(QKeySequence("F8"),self)
        self._wiring_issue_shortcut.activated.connect(self._next_wiring_issue)

        self.switch_conductor_card=SwitchConductorUsageCard()
        self.switch_conductor_card.set_location(getattr(placement,"group","") or "", getattr(placement,"label","") or "")
        self.switch_conductor_card.cableChanged.connect(self._switch_usage_cable_changed)
        wiring_root.addWidget(self.switch_conductor_card)
        # Selection-status findes direkte i ledergrafikkens reserverede bundzone;
        # behold label-objektet for eksisterende logik/tests, men brug ikke en
        # ekstra vertikal tekstlinje over den primære editor.
        self.wiring_selection_label=QLabel("Ingen leder valgt")
        self.wiring_selection_label.setObjectName("accentText"); self.wiring_selection_label.setWordWrap(True); self.wiring_selection_label.hide()

        self.wiring_diagram=PLWiringDiagramWidget(); self.wiring_diagram.setMinimumHeight(535); wiring_root.addWidget(self.wiring_diagram,1)
        self.graphics_detail_btn.toggled.connect(self._pl_graphics_detail_toggled)
        self.exploded_btn.toggled.connect(self.wiring_diagram.set_exploded)
        self.wiring_diagram.set_detail_mode(False)

        # Wago håndteres primært i selve ledergrafikken: drop på en terminal,
        # drop på en eksisterende Wago eller højreklik på terminalen. Den gamle
        # combo beholdes skjult som kompatibilitetskontrol for eksisterende kode.
        self.wago_combo=QComboBox(); self.wago_combo.currentIndexChanged.connect(self._wago_selection_changed); self.wago_combo.hide()
        self.wago_new_btn=QPushButton("Ny Wago…"); self.wago_new_btn.clicked.connect(self._new_wago); self.wago_new_btn.hide()
        self.wago_edit_btn=QPushButton("Redigér…"); self.wago_edit_btn.clicked.connect(self._edit_selected_wago); self.wago_edit_btn.hide()
        self.wago_remove_btn=QPushButton("Fjern Wago"); self.wago_remove_btn.clicked.connect(self._remove_selected_wago); self.wago_remove_btn.hide()

        wago_row=QHBoxLayout(); wago_row.setSpacing(8)
        wago_label=QLabel("Wago:"); wago_label.setObjectName("sectionTitle"); wago_row.addWidget(wago_label)
        self.wago_summary_label=QLabel("Ingen Wago-samlinger")
        self.wago_summary_label.setObjectName("subtleText"); self.wago_summary_label.setWordWrap(False)
        self.wago_summary_label.setToolTip("Wago oprettes lettest ved at vælge en leder og højreklikke på terminalen, eller ved at trække lederen til en eksisterende Wago.")
        wago_row.addWidget(self.wago_summary_label,1)
        self.wago_for_selected_btn=QPushButton("+ Wago → udtag")
        self.wago_for_selected_btn.setToolTip("Vælg en leder med funktion først. Opretter en Wago med én fysisk bro videre til den tilsvarende klemme på lampeudtaget.")
        self.wago_for_selected_btn.clicked.connect(self._new_wago_for_selected_function); wago_row.addWidget(self.wago_for_selected_btn)
        self.wago_loop_btn=QPushButton("+ Samlemuffe / sløjfe")
        self.wago_loop_btn.setToolTip("Saml kabelledere i en Wago uden forbindelse til lampeudtaget. Intet forbindes automatisk til udtaget.")
        self.wago_loop_btn.clicked.connect(self._new_loop_wago_for_selected_function); wago_row.addWidget(self.wago_loop_btn)
        self.wago_manage_btn=_set_role(QPushButton("Administrér Wago…"),"quietButton")
        self.wago_manage_btn.setToolTip("Vis eksisterende Wago-samlinger, redigér dem eller opret en ny for en bestemt terminalfunktion.")
        self.wago_manage_btn.clicked.connect(self._show_wago_manage_menu); wago_row.addWidget(self.wago_manage_btn)
        wiring_root.addLayout(wago_row)

        # Montagekontrol er vigtig, men sekundær i forhold til ledergrafikken.
        # Hovedvisningen viser derfor kun en kompakt status; den tekniske
        # terminal/Wago-detaljering foldes først ud på brugerens initiativ.
        montage_row=QHBoxLayout(); montage_row.setSpacing(8)
        self.montage_summary_label=QLabel(); self.montage_summary_label.setObjectName("subtleText"); self.montage_summary_label.setWordWrap(False)
        self.montage_summary_label.setToolTip("Kompakt montagekontrol. Vælg Vis kontrol for terminal-, Wago- og tændingsdetaljer.")
        montage_row.addWidget(self.montage_summary_label,1)
        self.montage_details_btn=_set_role(QPushButton("Vis kontrol"),"quietButton"); self.montage_details_btn.setCheckable(True)
        self.montage_details_btn.toggled.connect(self._toggle_montage_details); montage_row.addWidget(self.montage_details_btn)
        wiring_root.addLayout(montage_row)
        self.montage_status_label=QLabel(); self.montage_status_label.setWordWrap(True); self.montage_status_label.setObjectName("subtleText")
        self.montage_status_label.setToolTip("Detaljeret montagekontrol viser fysisk terminalbelastning, Wago-størrelse og tændingskrav.")
        self.montage_status_label.hide(); wiring_root.addWidget(self.montage_status_label)

        wactions=QHBoxLayout()
        self.wiring_detach_btn=_set_role(QPushButton("Frigør valgt leder"),"quietButton"); self.wiring_detach_btn.clicked.connect(self._detach_selected_conductor); self.wiring_detach_btn.setEnabled(False)
        self.wiring_reset_btn=_set_role(QPushButton("Nulstil lederplan"),"quietButton"); self.wiring_reset_btn.clicked.connect(self._reset_wiring)
        self.wiring_details_btn=_set_role(QPushButton("Vis tabel / avanceret"),"quietButton"); self.wiring_details_btn.setCheckable(True)
        wactions.addWidget(self.wiring_detach_btn); wactions.addWidget(self.wiring_reset_btn); wactions.addStretch(1); wactions.addWidget(self.wiring_details_btn)
        wiring_root.addLayout(wactions)

        self.wiring_unknown_label=QLabel(); self.wiring_unknown_label.setWordWrap(True); self.wiring_unknown_label.setObjectName("accentText"); wiring_root.addWidget(self.wiring_unknown_label)

        self.wiring_details_panel=QWidget(); details_root=QHBoxLayout(self.wiring_details_panel); details_root.setContentsMargins(0,0,0,0); details_root.setSpacing(12)
        req_box=QGroupBox("Forventede tændinger fra tilhørsforhold")
        req_layout=QVBoxLayout(req_box)
        self.requirements_table=QTableWidget(0,4)
        self.requirements_table.setHorizontalHeaderLabels(["Status","Tænding","Afbryderkanal","Kabel"])
        self.requirements_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.requirements_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.requirements_table.verticalHeader().setVisible(False)
        rh=self.requirements_table.horizontalHeader(); rh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents); rh.setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch); rh.setSectionResizeMode(3,QHeaderView.ResizeMode.Stretch)
        self.requirements_table.setMinimumHeight(190); req_layout.addWidget(self.requirements_table)
        details_root.addWidget(req_box,2)

        conductor_box=QGroupBox("Detaljeret lederliste")
        conductor_layout=QVBoxLayout(conductor_box)
        self.wiring_table=QTableWidget(0,6)
        self.wiring_table.setHorizontalHeaderLabels(["Indføring","Kabel","Side","Leder","Farve","Funktion / samling"])
        self.wiring_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.wiring_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.wiring_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.wiring_table.itemSelectionChanged.connect(self._wiring_table_selection_changed)
        self.wiring_table.verticalHeader().setVisible(False)
        hdr=self.wiring_table.horizontalHeader(); hdr.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents); hdr.setSectionResizeMode(5,QHeaderView.ResizeMode.Stretch)
        self.wiring_table.setMinimumHeight(190); conductor_layout.addWidget(self.wiring_table)
        details_root.addWidget(conductor_box,3)
        self.wiring_details_panel.hide()
        self.wiring_details_btn.toggled.connect(self._toggle_wiring_details)
        wiring_root.addWidget(self.wiring_details_panel)

        note=QLabel("Lederfarver: 3G = gul/grøn · blå · brun · 5G = gul/grøn · blå · brun · sort · grå · 7G = gul/grøn · blå · brun · sort · grå · rød · hvid. Kabelartikel/datablad har altid forrang.")
        note.setWordWrap(True); note.setObjectName("sectionHint"); note.hide(); self.wiring_details_btn.toggled.connect(note.setVisible); wiring_root.addWidget(note)
        self.tabs.addTab(wiring_tab,"Lederfordeling")

        footer=QHBoxLayout(); footer.addStretch(1)
        self.buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Apply)
        self.buttons.accepted.connect(self._accept); self.buttons.rejected.connect(self.reject)
        apply_btn=self.buttons.button(QDialogButtonBox.StandardButton.Apply)
        if apply_btn is not None: apply_btn.clicked.connect(self._apply)
        footer.addWidget(self.buttons); root.addLayout(footer)

        self.diagram.portSelected.connect(self._select_port)
        self.diagram.legDropped.connect(self._drop_leg)
        self.wiring_diagram.conductorSelected.connect(self._diagram_conductor_selected)
        self.wiring_diagram.functionAssigned.connect(self._diagram_function_assigned)
        self.wiring_diagram.conductorAction.connect(self._diagram_conductor_action)
        self.wiring_diagram.spliceMoved.connect(self._diagram_splice_moved)
        self.wiring_diagram.spliceAction.connect(self._diagram_splice_action)
        self.wiring_diagram.functionAction.connect(self._diagram_function_action)
        self._refresh()

    @staticmethod
    def _identity(row):
        return (str(row.get("cable_uid","")),int(row.get("point_index",0) or 0),str(row.get("leg","")))

    def _leg_for_entry(self, entry):
        if not entry:return None
        target=(str(entry.get("cable_uid","")),int(entry.get("point_index",0) or 0),str(entry.get("leg","")))
        return next((x for x in self.legs if self._identity(x)==target),None)

    def _entry_port_for_leg(self, leg):
        key=self._identity(leg)
        for port,entry in self.entries.items():
            if (str(entry.get("cable_uid","")),int(entry.get("point_index",0) or 0),str(entry.get("leg","")))==key:
                return int(port)
        return 0

    def _orientation_changed(self):
        self.orientation=core.normalize_pl_box_orientation(self.orientation_combo.currentData() if hasattr(self,"orientation_combo") else self.orientation)
        if hasattr(self,"diagram"):self.diagram.set_orientation(self.orientation)

    def _rotate_orientation(self):
        self.orientation=core.normalize_pl_box_orientation(self.orientation+90)
        if hasattr(self,"orientation_combo"):
            idx=self.orientation_combo.findData(self.orientation)
            if idx>=0:self.orientation_combo.setCurrentIndex(idx)

    def _refresh_field_status(self):
        record=core.normalize_pl_field_record(self.field_record)
        if not record:
            self.field_status.setObjectName("subtleText"); self.field_status.setText("Ikke tilknyttet")
            self.field_photos_btn.setEnabled(False); self.field_unlink_btn.setEnabled(False)
        else:
            filled=sum(core.pl_field_entry_state(row)!="unregistered" for row in record.get("entries",[]))
            photos=len(record.get("photos",[]) or []); ref=str(record.get("ref","") or "").strip()
            self.field_status.setObjectName("positiveText"); self.field_status.setText(
                f"{record.get('name') or record.get('box_id')} · {filled}/6 registreret"+(f" · mod {ref}" if ref else "")+f" · {photos} foto(s)"
            )
            self.field_photos_btn.setEnabled(bool(photos)); self.field_unlink_btn.setEnabled(True)
        self.field_status.style().unpolish(self.field_status); self.field_status.style().polish(self.field_status)

    def _import_field_record(self):
        from elplan_qt.qt_pl_field import PLFieldImportDialog
        dlg=PLFieldImportDialog(self,cable_legs=self.legs,current_entries=self.entries,current_record=self.field_record,orientation=self.orientation)
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        # Importen ændrer kun fysisk kabelplacering og feltmetadata. Den rører
        # aldrig self.wiring eller self.splices.
        self.entries=core.reconcile_pl_box_entries(dlg.result_entries,self.legs)
        self.field_record=core.normalize_pl_field_record(dlg.result_record)
        self.orientation=core.normalize_pl_box_orientation(dlg.result_orientation)
        idx=self.orientation_combo.findData(self.orientation)
        if idx>=0:self.orientation_combo.setCurrentIndex(idx)
        self._refresh()

    def _show_field_photos(self):
        if not core.normalize_pl_field_record(self.field_record):return
        from elplan_qt.qt_pl_field import PLFieldPhotoDialog
        PLFieldPhotoDialog(self,self.field_record).exec()

    def _unlink_field_record(self):
        if not self.field_record:return
        if QMessageBox.question(self,"Feltregistrering","Fjern tilknytningen og den importerede feltmetadata? De nuværende kabelplaceringer og lederfordelingen bevares.")!=QMessageBox.StandardButton.Yes:return
        self.field_record={}; self._refresh_field_status()
        if hasattr(self,"diagram"):self.diagram.set_orientation(self.orientation)

    def _category_for_leg(self,leg):
        cid=core.normalize_cable_category_id((leg or {}).get("cable_category",core.DEFAULT_CABLE_CATEGORY))
        return core.cable_category_record(self.cable_categories,cid)

    def _destination_labels(self):
        return {
            str(getattr(p,"uid","") or ""):core.placement_identification_caption(p)
            for p in self.placements
            if str(getattr(p,"symbol","") or "")=="light_connection" and str(getattr(p,"uid","") or "")
        }

    def _passthrough_targets(self):
        """Lampesteder/funktioner for en leder, der kun passerer denne dåse."""
        current_uid=str(getattr(self.placement,"uid","") or "")
        current_chains=set(); direct=set()
        for cable in self.cables:
            uids={str(x.get("symbol_uid","") or "") for x in core.cable_symbol_connections(cable)}
            if current_uid not in uids:continue
            direct.update(uid for uid in uids if uid and uid!=current_uid)
            chain=core.cable_route_chain_key(cable)
            if chain:current_chains.add(chain)
        chain_targets=set()
        if current_chains:
            for cable in self.cables:
                if core.cable_route_chain_key(cable) not in current_chains:continue
                chain_targets.update(str(x.get("symbol_uid","") or "") for x in core.cable_symbol_connections(cable))
        rows=[]
        for target in self.placements:
            uid=str(getattr(target,"uid","") or "")
            if not uid or uid==current_uid or str(getattr(target,"symbol","") or "")!="light_connection":continue
            ident=core.placement_identification_caption(target)
            rank=0 if uid in direct else (1 if uid in chain_targets else 2)
            route_hint="Direkte kabelvej" if rank==0 else ("Samme kabelrute" if rank==1 else "Andet lampested")
            outputs=core.light_output_records(target)
            for output in outputs:
                association=str(output.get("association","") or "")
                if not association:continue
                output_suffix=f" · {output.get('name')}" if len(outputs)>1 else ""
                rows.append({
                    "uid":uid,"association":association,"rank":rank,
                    "caption":f"{route_hint} · {ident}{output_suffix} · tænding {association}",
                })
        rows.sort(key=lambda row:(int(row["rank"]),str(row["caption"]).casefold()))
        return rows

    def _choose_passthrough_identity(self,seed_key=None,preferred_fid="",existing=None):
        """Vælg elektrisk rolle og det lampested, gennemsløjfningen tilhører."""
        existing=dict(existing or {})
        parts=core.pl_passthrough_function_parts(str(existing.get("function") or preferred_fid or ""))
        role=str(existing.get("conductor_role") or parts.get("role") or "")
        seed=tuple(seed_key or ())
        if not role and len(seed)==4:
            role={"pe":"pe","blue":"n","brown":"l"}.get(str(seed[3] or "").lower(),"switch")
        if role not in core.PL_PASSTHROUGH_ROLES:role="switch"
        target_uid=str(existing.get("destination_light_uid","") or "")
        target_assoc=str(existing.get("destination_association","") or parts.get("association","") or "")
        targets=self._passthrough_targets()

        dlg=QDialog(self); dlg.setWindowTitle("Gennemsløjfning · ledertype og lampested"); dlg.resize(570,270)
        root=QVBoxLayout(dlg)
        intro=QLabel("Samlemuffen forbindes ikke til dette lampeudtag. Vælg hvad lederen bruges til, og hvilket lampested/tændingskreds den tilhører.")
        intro.setWordWrap(True); root.addWidget(intro)
        form=QFormLayout(); role_combo=QComboBox(); target_combo=QComboBox()
        role_order=("switch","traveller_1","traveller_2","pe","n","l","reserve","unused")
        for key in role_order:role_combo.addItem(core.PL_PASSTHROUGH_ROLES[key],key)
        for row in targets:target_combo.addItem(row["caption"],(row["uid"],row["association"]))
        role_idx=role_combo.findData(role); role_combo.setCurrentIndex(max(0,role_idx))
        target_idx=target_combo.findData((target_uid,target_assoc))
        if target_idx<0 and target_assoc:
            target_idx=next((i for i,row in enumerate(targets) if row["association"]==target_assoc),-1)
        target_combo.setCurrentIndex(target_idx if target_idx>=0 else (0 if target_combo.count() else -1))
        form.addRow("Ledertype",role_combo); form.addRow("Tilhører lampested",target_combo); root.addLayout(form)
        hint=QLabel(); hint.setObjectName("sectionHint"); hint.setWordWrap(True); root.addWidget(hint)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        ok_button=buttons.button(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject); root.addWidget(buttons)

        def update_state(_index=None):
            selected_role=str(role_combo.currentData() or "")
            needs_target=selected_role in {"switch","traveller_1","traveller_2"}
            target_combo.setEnabled(needs_target)
            valid=(not needs_target) or target_combo.currentIndex()>=0
            if ok_button is not None:ok_button.setEnabled(valid)
            if needs_target and not targets:
                hint.setText("Der findes endnu ikke et andet lampested med tilhørsbogstav. Opret tilhørsforholdet først.")
                hint.setObjectName("accentText")
            elif needs_target:
                hint.setText("Direkte og sammenhængende kabelveje foreslås øverst. Mellemleder 1 og 2 holdes elektrisk adskilt.")
                hint.setObjectName("sectionHint")
            else:
                hint.setText("PE, N, L og reserve kræver ikke et lampested som destination.")
                hint.setObjectName("sectionHint")
            hint.style().unpolish(hint); hint.style().polish(hint)
        role_combo.currentIndexChanged.connect(update_state); update_state()
        if dlg.exec()!=QDialog.DialogCode.Accepted:return None
        selected_role=str(role_combo.currentData() or "")
        destination_uid=""; destination_association=""
        if selected_role in {"switch","traveller_1","traveller_2"}:
            data=target_combo.currentData()
            if not isinstance(data,(tuple,list)) or len(data)!=2:return None
            destination_uid=str(data[0] or ""); destination_association=str(data[1] or "")
        fid=core.pl_passthrough_function(selected_role,destination_association)
        if not fid:return None
        return {
            "function":fid,"conductor_role":selected_role,
            "destination_light_uid":destination_uid,
            "destination_association":destination_association,
        }

    def _external_allocation_hints(self):
        """Kortlæg lokalt tomme ledere, der allerede bruges i den anden ende."""
        current_uid=str(getattr(self.placement,"uid","") or "")
        local_functions={core.pl_box_conductor_key(row):str(row.get("function","") or "") for row in self.wiring}
        usages={}
        for leg in self.legs:
            cable_uid=str(leg.get("cable_uid","") or "")
            if cable_uid and cable_uid not in usages:
                usages[cable_uid]=core.cable_switch_conductor_usage(
                    cable_uid,self.placements,self.cables,
                    current_placement_uid=current_uid,current_wiring=self.wiring,
                )
        out={}
        for meta in core.pl_box_conductors(self.legs):
            key=core.pl_box_conductor_key(meta)
            if local_functions.get(key):continue
            usage=usages.get(str(key[0]),{})
            row=next((x for x in usage.get("cores",[]) if str(x.get("core_id") or "")==str(key[3])),{})
            external=[dict(x) for x in row.get("usages",[]) if str(x.get("placement_uid") or "")!=current_uid]
            functions=[]
            for item in external:
                fid=str(item.get("function") or "")
                if fid and fid not in functions:functions.append(fid)
            if functions:out[key]={"functions":functions,"usages":external,"conflict":len(functions)>1}
        return out

    @staticmethod
    def _category_icon(record):
        pm=QPixmap(36,14); pm.fill(Qt.GlobalColor.transparent)
        painter=QPainter(pm); painter.setRenderHint(QPainter.RenderHint.Antialiasing,True)
        color=QColor(str((record or {}).get("color") or core.DEFAULT_CABLE_COLOR))
        pen=QPen(color,3.0); pen.setCapStyle(Qt.PenCapStyle.RoundCap); pen.setStyle(PLBoxDiagramWidget._category_pen_style((record or {}).get("line_style")))
        painter.setPen(pen); painter.drawLine(QPointF(3,7),QPointF(33,7)); painter.end()
        return QIcon(pm)

    def _refresh_category_legend(self):
        counts={}
        order=[]
        for leg in self.legs:
            rec=self._category_for_leg(leg); cid=str(rec.get("id") or core.DEFAULT_CABLE_CATEGORY)
            if cid not in counts: order.append(cid); counts[cid]=0
            counts[cid]+=1
        if not order:
            self.category_legend.setText("Kabelkategorier: ingen kabler ved lampestedet")
            return
        parts=[]
        for cid in order:
            rec=core.cable_category_record(self.cable_categories,cid)
            color=html.escape(str(rec.get("color") or core.DEFAULT_CABLE_COLOR))
            name=html.escape(str(rec.get("name") or cid))
            parts.append(f'<span style="color:{color}; font-weight:700">●</span> {name} ×{counts[cid]}')
        self.category_legend.setText("<b>Kabelkategorier:</b> "+" &nbsp; ".join(parts))

    def _refresh(self):
        self.entries=core.reconcile_pl_box_entries(self.entries,self.legs)
        status=core.pl_box_status(self.entries,self.legs)
        text=f"{status['used']} / {status['capacity']} indføringer anvendt · {status['required']} nødvendige kabelben"
        if status["overflow"]:
            text += f" · ⚠ {status['overflow']} kabelben mere end dåsen har plads til"
            self.status_label.setObjectName("dangerText")
        elif status["unplaced"]:
            text += f" · {status['unplaced']} endnu ikke placeret"
            self.status_label.setObjectName("accentText")
        else:
            text += " · Alle kabelben er placeret"
            self.status_label.setObjectName("positiveText")
        wiring_status=core.pl_box_wiring_status(self.wiring,self.legs)
        if wiring_status["known"]:
            text += f" · Lederplan {wiring_status['assigned']}/{wiring_status['known']} fordelt"
            if wiring_status["live_unassigned"]:
                text += f" (⚠ {wiring_status['live_unassigned']} aktive uden funktion)"
        elif wiring_status["unknown_legs"]:
            text += " · Lederplan: ukendt kabelopbygning"
        req_summary=core.pl_wiring_requirement_summary(self.requirements,self.wiring,self.splices)
        if req_summary["required"]:
            text += f" · Tændinger {req_summary['ok']}/{req_summary['required']}"
            if req_summary["missing"] or req_summary["wrong_cable"] or req_summary["duplicate"]:
                text += " ⚠"
        self.status_label.setText(text); self.status_label.style().unpolish(self.status_label); self.status_label.style().polish(self.status_label)
        self._refresh_field_status()

        self._refresh_category_legend()
        current_key=None
        cur=self.leg_list.currentItem()
        if cur is not None and isinstance(cur.data(Qt.ItemDataRole.UserRole),dict): current_key=self._identity(cur.data(Qt.ItemDataRole.UserRole))
        self.leg_list.blockSignals(True); self.leg_list.clear()
        selected_row=-1
        for i,leg in enumerate(self.legs):
            cid=str(leg.get("cable_display") or leg.get("cable_id") or "Kabel")
            spec=str(leg.get("cable_spec") or "")
            category=self._category_for_leg(leg)
            category_name=str(category.get("name") or "Øvrige")
            port=self._entry_port_for_leg(leg)
            placement=f"Indføring {port}" if port else "Ikke placeret"
            txt=f"{cid}"+(f" · {spec}" if spec else "")+f" · {category_name} · {leg.get('leg_caption','')}  →  {placement}"
            item=QListWidgetItem(self._category_icon(category),txt); item.setData(Qt.ItemDataRole.UserRole,dict(leg))
            definition=str(category.get("description") or "").strip()
            item.setToolTip(f"{category_name}"+(f" — {definition}" if definition else ""))
            self.leg_list.addItem(item)
            if current_key is not None and self._identity(leg)==current_key:selected_row=i
        self.leg_list.blockSignals(False)
        if selected_row>=0:self.leg_list.setCurrentRow(selected_row)
        elif self.leg_list.count():self.leg_list.setCurrentRow(0)
        unplaced=core.pl_box_unplaced_legs(self.entries,self.legs)
        self.unplaced_label.setText(f"Ikke placeret: {len(unplaced)}" if unplaced else "Alle registrerede kabelben er placeret.")
        self.diagram.set_state(self.entries,self.legs,self.selected_port,self.orientation,self.cable_categories)
        self._refresh_detail()
        self._refresh_wiring()

    @staticmethod
    def _conductor_identity(row):
        return core.pl_box_conductor_key(row)

    def _port_for_conductor(self,row):
        leg_key=(str(row.get("cable_uid","")),int(row.get("point_index",0) or 0),str(row.get("leg","")))
        for port,entry in self.entries.items():
            key=(str(entry.get("cable_uid","")),int(entry.get("point_index",0) or 0),str(entry.get("leg","")))
            if key==leg_key:return int(port)
        return 0

    def _refresh_workflow_issues(self,external_allocations=None):
        if not hasattr(self,"wiring_issue_combo"):return
        current=str(self.wiring_issue_combo.currentData(Qt.ItemDataRole.UserRole) or "")
        issues=core.pl_wiring_workflow_issues(
            self.legs,self.wiring,self.requirements,self.splices,self.outlet_type,
            core.light_output_associations(self.placement),external_allocations or {},
        )
        self._wiring_issues=issues
        blocker=QSignalBlocker(self.wiring_issue_combo); self.wiring_issue_combo.clear()
        icons={"error":"⛔","warning":"⚠","review":"◇"}
        for issue in issues:
            self.wiring_issue_combo.addItem(
                f"{icons.get(str(issue.get('severity') or ''),'•')} {issue.get('title') or 'Kontrollér lederplan'}",
                str(issue.get("id") or ""),
            )
            index=self.wiring_issue_combo.count()-1
            self.wiring_issue_combo.setItemData(index,str(issue.get("detail") or issue.get("title") or ""),Qt.ItemDataRole.ToolTipRole)
        idx=self.wiring_issue_combo.findData(current)
        self.wiring_issue_combo.setCurrentIndex(idx if idx>=0 else (0 if issues else -1))
        del blocker
        if issues:
            self.wiring_issue_combo.setEnabled(True); self.wiring_next_issue_btn.setEnabled(True)
        else:
            self.wiring_issue_combo.addItem("✓ Ingen uløste punkter","")
            self.wiring_issue_combo.setEnabled(False); self.wiring_next_issue_btn.setEnabled(False)
        self.wiring_suggest_btn.setEnabled(bool(core.pl_wiring_suggestions(
            self.legs,self.wiring,self.requirements,external_allocations or {},
        )))

    def _workflow_issue(self,index=None):
        if not getattr(self,"_wiring_issues",None):return None
        if index is None:index=self.wiring_issue_combo.currentIndex()
        issue_id=str(self.wiring_issue_combo.itemData(int(index),Qt.ItemDataRole.UserRole) or "") if int(index)>=0 else ""
        return next((row for row in self._wiring_issues if str(row.get("id") or "")==issue_id),None)

    def _focus_workflow_issue(self,index=None):
        issue=self._workflow_issue(index)
        if issue is None:return
        key=issue.get("conductor_key")
        fid=str(issue.get("function_id") or "")
        if key:
            key=tuple(key); self.wiring_diagram.set_selected_conductor(key)
            self._update_wiring_selection_label(key)
            for row in range(self.wiring_table.rowCount()):
                item=self.wiring_table.item(row,0)
                if item is not None and tuple(item.data(Qt.ItemDataRole.UserRole) or ())==key:
                    blocker=QSignalBlocker(self.wiring_table); self.wiring_table.selectRow(row); del blocker
                    if self.wiring_details_panel.isVisible():self.wiring_table.scrollToItem(item,QAbstractItemView.ScrollHint.PositionAtCenter)
                    break
        else:
            self.wiring_diagram.set_selected_conductor(None); self._update_wiring_selection_label(None)
        self.wiring_diagram.set_focus_function(fid)

    def _workflow_issue_selected(self,index):
        self._focus_workflow_issue(int(index))

    def _next_wiring_issue(self):
        count=len(getattr(self,"_wiring_issues",[]) or [])
        if not count:return
        index=(self.wiring_issue_combo.currentIndex()+1)%count
        self.wiring_issue_combo.setCurrentIndex(index); self._focus_workflow_issue(index)

    def _show_wiring_suggestions(self):
        external=dict(getattr(self,"_current_external_allocations",{}) or self._external_allocation_hints())
        suggestions=core.pl_wiring_suggestions(self.legs,self.wiring,self.requirements,external)
        if not suggestions:
            QMessageBox.information(self,"Forslag til lederfordeling","Der er ingen entydige eller relevante forslag til den aktuelle lederplan.")
            return

        dlg=QDialog(self); dlg.setWindowTitle("Forslag til lederfordeling · forhåndsvisning"); dlg.resize(830,430)
        root=QVBoxLayout(dlg)
        intro=QLabel("Sikre forslag er valgt på forhånd. Forslag markeret 'Kontrollér' kræver et aktivt valg. Intet ændres, før du vælger Anvend valgte; ændringerne gemmes først med Anvend eller OK i PL-konfiguratoren.")
        intro.setWordWrap(True); root.addWidget(intro)
        table=QTableWidget(len(suggestions),4)
        table.setHorizontalHeaderLabels(["Anvend","Leder","Forslag","Grundlag"])
        table.verticalHeader().setVisible(False); table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for row,suggestion in enumerate(suggestions):
            checked=QTableWidgetItem("Sikkert" if suggestion.get("confidence")=="safe" else "Kontrollér")
            checked.setFlags((checked.flags()|Qt.ItemFlag.ItemIsUserCheckable)&~Qt.ItemFlag.ItemIsEditable)
            checked.setCheckState(Qt.CheckState.Checked if suggestion.get("checked") else Qt.CheckState.Unchecked)
            checked.setData(Qt.ItemDataRole.UserRole,dict(suggestion)); table.setItem(row,0,checked)
            for column,value in enumerate((suggestion.get("conductor_caption"),suggestion.get("function_caption"),suggestion.get("reason")),1):
                item=QTableWidgetItem(str(value or "")); item.setFlags(item.flags()&~Qt.ItemFlag.ItemIsEditable); table.setItem(row,column,item)
        header=table.horizontalHeader(); header.setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents); header.setSectionResizeMode(2,QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3,QHeaderView.ResizeMode.Stretch); table.resizeRowsToContents(); root.addWidget(table,1)
        note=QLabel("Bemærk: Brun → fast fase er aldrig forhåndsvalgt, da brun også kan være tændledning. Kabelartikel, dokumentation og gældende installationsregler har altid forrang.")
        note.setObjectName("sectionHint"); note.setWordWrap(True); root.addWidget(note)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        apply_button=buttons.button(QDialogButtonBox.StandardButton.Ok)
        if apply_button is not None:apply_button.setText("Anvend valgte")
        buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject); root.addWidget(buttons)
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        selected=[]
        for row in range(table.rowCount()):
            item=table.item(row,0)
            if item is not None and item.checkState()==Qt.CheckState.Checked:
                data=item.data(Qt.ItemDataRole.UserRole)
                if isinstance(data,dict):selected.append(dict(data))
        if not selected:return

        applied=[]
        for suggestion in selected:
            key=tuple(suggestion.get("conductor_key") or ())
            fid=str(suggestion.get("function_id") or "")
            current=next((str(row.get("function") or "") for row in self.wiring if core.pl_box_conductor_key(row)==key),"")
            if current==fid:continue
            if current:continue  # Beskyt mod ændringer, mens forhåndsvisningen var åben.
            if self._assign_function_with_capacity_check(key,fid):applied.append(key)
        self._refresh_wiring()
        if applied:
            self._diagram_conductor_selected(applied[0]); self.wiring_diagram.flash_connection(applied[0])

    def _refresh_wiring(self):
        if not hasattr(self,"wiring_table"):
            return
        self.wiring=core.reconcile_pl_box_wiring(self.wiring,self.legs)
        self.splices=core.reconcile_pl_box_splices(self.splices,self.wiring,self.legs)
        # Kabelbred anvendelse er relativt dyr at udlede. Beregn den én gang
        # pr. reel lederændring og del resultatet mellem diagram, navigator,
        # markeringstekst og forslagspreview.
        external_allocations=self._external_allocation_hints()
        self._current_external_allocations=external_allocations
        status=core.pl_box_wiring_status(self.wiring,self.legs)
        if status["known"]:
            txt=f"{status['assigned']} / {status['known']} ledere har funktion"
            if status["live_unassigned"]:
                txt+=f" · ⚠ {status['live_unassigned']} aktive ledere mangler funktion/samling"
                self.wiring_status_label.setObjectName("accentText")
            else:
                txt+=" · Lederplan komplet"
                self.wiring_status_label.setObjectName("positiveText")
        elif status["unknown_legs"]:
            txt="Ingen kendte 3G/5G/7G-ledere kunne udledes endnu."
            self.wiring_status_label.setObjectName("accentText")
        else:
            txt="Ingen kabler er tilsluttet lampestedet."
            self.wiring_status_label.setObjectName("subtleText")
        req_summary=core.pl_wiring_requirement_summary(self.requirements,self.wiring,self.splices)
        if req_summary["required"]:
            txt+=f" · Tændinger {req_summary['ok']}/{req_summary['required']} korrekt placeret"
            if req_summary["missing"]:txt+=f" · ⚠ {req_summary['missing']} mangler leder"
            if req_summary["wrong_cable"]:txt+=f" · ⚠ {req_summary['wrong_cable']} på forkert kabelben"
            if req_summary["duplicate"]:txt+=f" · ⛔ {req_summary['duplicate']} dublettildeling(er)"
        if req_summary["manual"]:
            txt+=f" · {req_summary['manual']} korrespondance/krydsning kræver manuel terminalkontrol"
        capacity_issues=core.pl_outlet_capacity_issues(self.outlet_type,core.light_output_associations(self.placement),self.wiring,self.splices)
        if capacity_issues:
            txt+=" · ⛔ " + "; ".join(f"{x['label']} {x['terminal_count']}/{x['capacity']}" for x in capacity_issues) + " – tilføj/redigér Wago"
            self.wiring_status_label.setObjectName("accentText")
        self.wiring_status_label.setText(txt); self.wiring_status_label.style().unpolish(self.wiring_status_label); self.wiring_status_label.style().polish(self.wiring_status_label)

        # Vis den konkrete afbryderkanal bag hvert tilhørsforhold. Kun direkte
        # kabelveje bliver hårde krav; korrespondance/krydsning markeres som
        # manuel topologi, fordi tilhørsbogstavet ikke beskriver terminalerne.
        statuses=req_summary["statuses"]
        self.requirements_table.setRowCount(len(statuses))
        state_visual={
            "ok":("✓","#166534"), "missing":("⚠","#b45309"),
            "wrong_cable":("⚠","#b45309"), "duplicate":("⛔","#b91c1c"),
            "manual":("◇","#7c3aed"), "related":("•","#64748b"),
        }
        for rr,req in enumerate(statuses):
            icon,color=state_visual.get(str(req.get("state","")),("•","#64748b"))
            letter=str(req.get("association","") or "")
            source=" · ".join(x for x in [str(req.get("source_mark","") or ""),str(req.get("channel_caption","") or "")] if x)
            cable=str(req.get("cable_display","") or ("Ingen direkte kabelvej" if not req.get("direct") else "Kabel"))
            output_name=str(req.get("light_output_name","") or "")
            req_label=(f"P · tryk {letter}" if letter else "P · trykindgang") if core.normalize_pl_outlet_type(self.outlet_type)=="nordtronic_zigbee" else (f"Tænding {letter}" if letter else "Tænding")
            if output_name:req_label+=f" · {output_name}"
            vals=[icon,req_label,source,cable]
            for cc,val in enumerate(vals):
                item=QTableWidgetItem(val); item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setToolTip(str(req.get("detail","") or ""))
                if cc==0:item.setForeground(QBrush(QColor(color)))
                self.requirements_table.setItem(rr,cc,item)
        if not statuses:
            self.requirements_table.setRowCount(1)
            item=QTableWidgetItem("Ingen konkrete afbryderkanaler kunne udledes fra tilhørsforhold + kabelvej.")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.requirements_table.setSpan(0,0,1,4); self.requirements_table.setItem(0,0,item)

        conductors=core.pl_box_conductors(self.legs)
        wmap={core.pl_box_conductor_key(x):x for x in self.wiring}
        conductors.sort(key=lambda x:(self._port_for_conductor(x) or 99,str(x.get("cable_id","")),str(x.get("leg","")),str(x.get("core_id",""))))
        self.wiring_table.setRowCount(len(conductors))
        known_options=core.pl_wiring_function_options(core.light_output_associations(self.placement),self.outlet_type)
        detailed_options=[]
        for fid,caption in known_options:
            req=[x for x in self.requirements if str(x.get("function_id","") or "")==fid and x.get("direct")]
            if len(req)==1:
                r0=req[0]
                source=" · ".join(x for x in [str(r0.get("source_mark","") or ""),str(r0.get("channel_caption","") or "")] if x)
                if core.normalize_pl_outlet_type(self.outlet_type)=="nordtronic_zigbee" and str(fid).startswith("switch:"):
                    caption=f"P · tryk {r0.get('association','')} ← {source}"
                else:
                    caption=f"Tænding {r0.get('association','')} ← {source}"
            detailed_options.append((fid,caption))
        for r,meta in enumerate(conductors):
            key=core.pl_box_conductor_key(meta); wr=wmap.get(key,{})
            port=self._port_for_conductor(meta)
            values=[str(port) if port else "—",str(meta.get("cable_display") or meta.get("cable_id") or "Kabel"),str(meta.get("leg_caption") or ""),str(meta.get("display") or meta.get("label") or meta.get("core_id") or ""),str(meta.get("color_name") or "")]
            for c,value in enumerate(values):
                item=QTableWidgetItem(value); item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if c==0:item.setData(Qt.ItemDataRole.UserRole,key)
                if c==3:
                    item.setBackground(QBrush(QColor(str(meta.get("color","#64748b")))))
                    item.setForeground(QBrush(QColor(str(meta.get("text_color","#ffffff")))))
                self.wiring_table.setItem(r,c,item)
            combo=QComboBox()
            for fid,caption in detailed_options:combo.addItem(caption,fid)
            current=str(wr.get("function","") or "")
            idx=combo.findData(current)
            if idx<0 and current:
                combo.addItem(core.pl_wiring_function_caption(current,core.light_output_associations(self.placement),self.outlet_type),current); idx=combo.count()-1
            combo.setCurrentIndex(max(0,idx))
            combo.setToolTip("Én fysisk leder kan kun have én funktion. Vælger du en anden tænding, erstatter den den tidligere funktion på denne leder.")
            combo.currentIndexChanged.connect(lambda _i,key=key,combo=combo:self._wiring_combo_changed(key,combo))
            self.wiring_table.setCellWidget(r,5,combo)

        unknown=[]
        for leg in self.legs:
            if not core.cable_conductor_preset(str(leg.get("cable_spec","") or "")):
                unknown.append(f"{leg.get('cable_display') or leg.get('cable_id') or 'Kabel'} · {leg.get('cable_spec') or 'uden specifikation'} · {leg.get('leg_caption') or ''}")
        if unknown:
            self.wiring_unknown_label.setText("⚠ Lederopbygning ikke genkendt for: "+"; ".join(unknown)+". Programmet understøtter automatisk 3G, 5G og 7G.")
            self.wiring_unknown_label.show()
        else:
            self.wiring_unknown_label.hide()
        profile=core.pl_outlet_profile(self.outlet_type,core.light_output_associations(self.placement))
        self.outlet_profile_hint.setText(str(profile.get("compact_hint") or profile.get("hint") or ""))
        self.outlet_profile_hint.setToolTip(str(profile.get("hint") or ""))
        unsupported=list(profile.get("unsupported_switches") or [])
        if unsupported:
            labels=[x.split(":",1)[1] if ":" in x else x for x in unsupported]
            self.wiring_status_label.setText(self.wiring_status_label.text()+" · ⚠ Valgt lampeudtag mangler fysisk klemme til tænding "+", ".join(labels))
            self.wiring_status_label.setObjectName("accentText")
            self.wiring_status_label.style().unpolish(self.wiring_status_label); self.wiring_status_label.style().polish(self.wiring_status_label)
        self._refresh_wago_controls()
        self._refresh_montage_status()
        self._refresh_switch_conductor_usage(preserve_combo=True)
        self._refresh_workflow_issues(external_allocations)
        self.wiring_diagram.set_state(
            self.entries,self.legs,self.wiring,core.light_output_associations(self.placement),
            self.requirements,self.outlet_type,self.splices,self.cable_categories,
            external_allocations,self._destination_labels(),
        )
        row=self.wiring_table.currentRow()
        if row>=0:
            item=self.wiring_table.item(row,0)
            if item is not None:
                key=item.data(Qt.ItemDataRole.UserRole); self.wiring_diagram.set_selected_conductor(key); self._update_wiring_selection_label(key)
        else:
            self._update_wiring_selection_label(None)

    def _toggle_montage_details(self,expanded):
        expanded=bool(expanded)
        if hasattr(self,"montage_status_label"):
            self.montage_status_label.setVisible(expanded)
        if hasattr(self,"montage_details_btn"):
            self.montage_details_btn.setText("Skjul kontrol" if expanded else "Vis kontrol")

    def _refresh_montage_status(self):
        if not hasattr(self,"montage_status_label"):return
        status=core.pl_montage_status(
            self.outlet_type,core.light_output_associations(self.placement),
            self.wiring,self.splices,self.requirements,self.legs,
        )
        parts=[]
        for row in status.get("terminals",[]):
            state=str(row.get("state") or "")
            icon={"ok":"✓","planned":"◇","empty":"○","error":"⛔"}.get(state,"•")
            cap=row.get("capacity"); count=int(row.get("terminal_count",0) or 0)
            load=f"{count}/{cap}" if cap else str(count)
            extra=""
            if row.get("has_wago"):
                wc=int(row.get("wago_count",1) or 1)
                extra=f" · Wago×{wc}→udtag · {int(row.get('assigned_count',0) or 0)} leder(e)"
            elif row.get("has_loop_wago"):
                lc=int(row.get("loop_wago_count",1) or 1)
                extra=f" · Samlemuffe×{lc} · ingen udtag"
            parts.append(f"{row.get('label') or row.get('function_id')} {load} {icon}{extra}")
        wago_parts=[]
        for row in status.get("wago",[]):
            fid=str(row.get("function_id") or "")
            label=core.pl_wiring_function_caption(fid,core.light_output_associations(self.placement),self.outlet_type).split(" → ",1)[0]
            article=str(row.get("article_no") or "artikel?")
            needed=int(row.get("needed_ports",0) or 0); cap=int(row.get("article_capacity",0) or 0)
            icon="✓" if row.get("state")=="ok" else ("⛔" if row.get("state")=="error" else "⚠")
            port_text=f"{needed}/{cap}" if cap else f"{needed}/?"
            mode="→ udtag" if row.get("connects_to_outlet",True) else "samlemuffe · ingen udtag"
            wago_parts.append(f"Wago {label} {mode}: {article} {port_text} {icon}")
        text="Montagekontrol: "+(" · ".join(parts) if parts else "ingen terminaler")
        if wago_parts:text+="   |   "+" · ".join(wago_parts)
        if status.get("errors"):
            text+="   |   ⛔ "+"; ".join(status.get("errors") or [])
        elif status.get("warnings"):
            text+="   |   ⚠ "+"; ".join(status.get("warnings") or [])
        else:
            text+="   |   Klar til montage ✓"
        role={"error":"dangerText","warning":"accentText","ready":"positiveText"}.get(str(status.get("state") or ""),"subtleText")
        self.montage_status_label.setObjectName(role); self.montage_status_label.setText(text)
        self.montage_status_label.style().unpolish(self.montage_status_label); self.montage_status_label.style().polish(self.montage_status_label)

        # Kort status på hovedbilledet; detaljer ligger bag Vis kontrol.
        errors=list(status.get("errors") or []); warnings=list(status.get("warnings") or [])
        if errors:
            summary=f"⛔ Montagekontrol · {len(errors)} fejl"+(f" · {len(warnings)} advarsel(er)" if warnings else "")
        elif warnings:
            live=int(status.get("live_unassigned",0) or 0)
            summary=f"⚠ Montagekontrol · {len(warnings)} advarsel(er)"+(f" · {live} aktive ledere uden funktion" if live else "")
        else:
            summary="✓ Montagekontrol · klar til montage"
        if hasattr(self,"montage_summary_label"):
            self.montage_summary_label.setObjectName(role); self.montage_summary_label.setText(summary)
            self.montage_summary_label.style().unpolish(self.montage_summary_label); self.montage_summary_label.style().polish(self.montage_summary_label)

    def _wago_selection_changed(self):
        sid=str(self.wago_combo.currentData() or "") if hasattr(self,"wago_combo") else ""
        enabled=bool(sid)
        if hasattr(self,"wago_edit_btn"):self.wago_edit_btn.setEnabled(enabled)
        if hasattr(self,"wago_remove_btn"):self.wago_remove_btn.setEnabled(enabled)

    def _selected_wago_context(self):
        key=tuple(self.selected_conductor_key or ())
        if len(key)!=4:return key,"",None
        fid=next((str(x.get("function","") or "") for x in self.wiring if core.pl_box_conductor_key(x)==key),"")
        splice=next((x for x in self.splices if key in core.pl_splice_member_keys(x)),None)
        return key,fid,splice

    def _new_wago_for_selected_function(self):
        key,fid,splice=self._selected_wago_context()
        if splice is not None:
            self._edit_wago_members(str(splice.get("function","") or ""),str(splice.get("id","") or ""),seed_keys=[key]); return
        if not fid:
            QMessageBox.information(self,"Wago","Vælg først en leder og giv den en funktion/klemme. Du kan også højreklikke direkte på PE, N, L, P, COM eller ~ i grafikken og vælge 'Opret Wago'.")
            return
        self._edit_wago_members(fid,None,seed_keys=[key],default_connects=True)

    def _loop_wago_function_choices(self):
        """Returnér de fysiske terminalfunktioner, der kan bruges som elektrisk identitet for en ren samlemuffe."""
        profile=core.pl_outlet_profile(self.outlet_type,core.light_output_associations(self.placement))
        choices=[]; seen=set()
        for terminal in profile.get("terminals",[]):
            fid=str(terminal.get("function_id","") or "")
            if not fid or fid in seen:continue
            seen.add(fid); choices.append(fid)
        return choices

    def _new_loop_wago(self,seed_key=None,preferred_fid=""):
        """Opret en ren Wago-samlemuffe uden bro til lampeudtaget.

        Brugeren vælger/har valgt den elektriske funktion, men ``connects_to_outlet``
        er altid False ved oprettelsen. Den kan senere ændres eksplicit i
        Wago-editoren.
        """
        seed_key=tuple(seed_key or ())
        suggested={}
        if len(seed_key)==4 and not str(preferred_fid or ""):
            hint=self._external_allocation_hints().get(seed_key,{})
            functions=list(hint.get("functions",[]) or [])
            if len(functions)==1:
                preferred_fid=functions[0]
                parts=core.pl_passthrough_function_parts(preferred_fid)
                remote=next((x for x in hint.get("usages",[]) if str(x.get("function") or "")==preferred_fid),{})
                suggested={
                    "function":preferred_fid,"conductor_role":parts.get("role",""),
                    "destination_light_uid":str(remote.get("placement_uid") or ""),
                    "destination_association":parts.get("association",""),
                }
        identity=self._choose_passthrough_identity(seed_key,preferred_fid,suggested)
        if identity is None:return
        target_fid=str(identity.get("function") or "")
        seeds=[seed_key] if len(seed_key)==4 else []
        self._edit_wago_members(target_fid,None,seed_keys=seeds,default_connects=False,splice_metadata=identity)

    def _new_loop_wago_for_selected_function(self):
        key,fid,splice=self._selected_wago_context()
        if splice is not None:
            if not bool(splice.get("connects_to_outlet",True)):
                self._edit_wago_members(str(splice.get("function","") or ""),str(splice.get("id","") or ""),seed_keys=[key]); return
            QMessageBox.information(self,"Samlemuffe","Den valgte leder ligger allerede i en Wago med forbindelse til lampeudtaget. Redigér eller frigør den eksisterende Wago først.")
            return
        self._new_loop_wago(key if len(key)==4 else None,fid)

    def _select_wago_in_combo(self,sid):
        sid=str(sid or "")
        idx=self.wago_combo.findData(sid) if hasattr(self,"wago_combo") else -1
        if idx>=0:self.wago_combo.setCurrentIndex(idx)

    def _show_wago_manage_menu(self):
        menu=QMenu(self)
        create_menu=menu.addMenu("+ Opret Wago → lampeudtag")
        loop_menu=menu.addMenu("+ Opret samlemuffe / sløjfe · ingen udtag")
        choose_loop=loop_menu.addAction("Vælg ledertype og tilhørende lampested…")
        choose_loop.triggered.connect(lambda:self._new_loop_wago())
        profile=core.pl_outlet_profile(self.outlet_type,core.light_output_associations(self.placement))
        seen=set()
        for terminal in profile.get("terminals",[]):
            fid=str(terminal.get("function_id","") or "")
            if not fid or fid in seen:continue
            seen.add(fid)
            caption=core.pl_wiring_function_caption(fid,core.light_output_associations(self.placement),self.outlet_type).split(" → ",1)[0]
            act=create_menu.addAction(caption)
            act.triggered.connect(lambda _checked=False,fid=fid:self._edit_wago_members(fid,None,default_connects=True))
        if not seen:
            create_menu.setEnabled(False)
        if self.splices:
            menu.addSeparator()
            counts={}; totals={}
            for splice in self.splices:
                fid=str(splice.get("function","") or ""); totals[fid]=totals.get(fid,0)+1
            for splice in self.splices:
                sid=str(splice.get("id","") or ""); fid=str(splice.get("function","") or "")
                counts[fid]=counts.get(fid,0)+1
                function=core.pl_wiring_function_caption(fid,core.light_output_associations(self.placement),self.outlet_type).split(" → ",1)[0]
                members=len(core.pl_splice_member_keys(splice)); article=str(splice.get("article_no","") or "")
                needed=core.pl_wago_required_ports(members,bool(splice.get("connects_to_outlet",True))); cap=core.pl_wago_article_capacity(article)
                ordinal=f" {counts[fid]}/{totals[fid]}" if totals[fid]>1 else ""
                mode="→ udtag" if bool(splice.get("connects_to_outlet",True)) else "samlemuffe · ingen udtag"
                sub=menu.addMenu(f"Wago {function}{ordinal} · {needed}/{cap or '?'} · {mode}")
                edit=sub.addAction("Redigér…")
                edit.triggered.connect(lambda _checked=False,sid=sid,fid=fid:self._edit_wago_members(fid,sid))
                if not bool(splice.get("connects_to_outlet",True)):
                    destination=sub.addAction("Skift ledertype / tilhørende lampested…")
                    destination.triggered.connect(lambda _checked=False,splice=splice:self._change_loop_splice_identity(splice))
                remove=sub.addAction("Fjern Wago")
                def do_remove(_checked=False,sid=sid):
                    self._select_wago_in_combo(sid); self._remove_selected_wago()
                remove.triggered.connect(do_remove)
        else:
            none=menu.addAction("Ingen eksisterende Wago-samlinger"); none.setEnabled(False)
        anchor=self.wago_manage_btn.mapToGlobal(self.wago_manage_btn.rect().bottomLeft()) if hasattr(self,"wago_manage_btn") else self.mapToGlobal(self.rect().center())
        menu.exec(anchor)

    def _refresh_wago_controls(self):
        if not hasattr(self,"wago_combo"):return
        current=str(self.wago_combo.currentData() or "")
        blocker=QSignalBlocker(self.wago_combo); self.wago_combo.clear()
        summaries=[]
        if not self.splices:
            self.wago_combo.addItem("Ingen Wago-samlinger","")
        else:
            # Nummerér Wago'er inden for samme funktion, så flere N/PE/L/etc.
            # er lette at skelne i kompatibilitets-comboen og montagekontrollen.
            counts={}; totals={}
            for splice in self.splices:
                fid=str(splice.get("function","") or ""); totals[fid]=totals.get(fid,0)+1
            for splice in self.splices:
                sid=str(splice.get("id","") or ""); fid=str(splice.get("function","") or "")
                counts[fid]=counts.get(fid,0)+1
                members=core.pl_splice_member_keys(splice)
                occ=core.pl_terminal_occupancy(fid,self.wiring,self.splices)
                terminal_cap=core.pl_outlet_terminal_capacity(self.outlet_type,core.light_output_associations(self.placement),fid)
                function=core.pl_wiring_function_caption(fid,core.light_output_associations(self.placement),self.outlet_type)
                short_function=function.split(" → ",1)[0]
                ordinal=f" · Wago {counts[fid]}/{totals[fid]}" if totals.get(fid,0)>1 else ""
                suffix=f" · terminal {occ['terminal_count']}/{terminal_cap}" if terminal_cap else ""
                article_no=str(splice.get("article_no","") or "").strip()
                article_suffix=f" · {article_no}" if article_no else " · ⚠ ingen artikel"
                connects=bool(splice.get("connects_to_outlet",True))
                destination=self._destination_labels().get(str(splice.get("destination_light_uid","") or ""),"")
                destination_assoc=str(splice.get("destination_association","") or "")
                role=core.normalize_pl_passthrough_role(splice.get("conductor_role"),fid)
                requires_destination=role in {"switch","traveller_1","traveller_2"}
                mode="→ udtag" if connects else ("samlemuffe → "+destination if destination else ("samlemuffe · ⚠ destination mangler" if requires_destination else "samlemuffe · intern samling"))
                self.wago_combo.addItem(f"{function}{ordinal} · {mode} · {len(members)} ledere{article_suffix}{suffix}",sid)
                needed=core.pl_wago_required_ports(len(members),connects); cap=core.pl_wago_article_capacity(article_no)
                summaries.append(f"{short_function} {needed}/{cap or '?'}"+(" → udtag" if connects else f" · {mode}"))
        idx=self.wago_combo.findData(current)
        self.wago_combo.setCurrentIndex(idx if idx>=0 else 0)
        del blocker
        self._wago_selection_changed()

        if hasattr(self,"wago_summary_label"):
            if summaries:
                shown=summaries[:5]; extra=len(summaries)-len(shown)
                self.wago_summary_label.setText(" · ".join(shown)+(f" · +{extra} flere" if extra else ""))
                self.wago_summary_label.setToolTip("Wago-samlinger: "+" · ".join(summaries)+". Højreklik på en terminal eller brug Administrér Wago for detaljer.")
            else:
                self.wago_summary_label.setText("Ingen Wago-samlinger · højreklik på en terminal for at oprette")
        key,fid,splice=self._selected_wago_context()
        if hasattr(self,"wago_for_selected_btn"):
            if splice is not None:
                function=core.pl_wiring_function_caption(str(splice.get("function","") or ""),core.light_output_associations(self.placement),self.outlet_type).split(" → ",1)[0]
                self.wago_for_selected_btn.setText(f"Redigér Wago {function}"); self.wago_for_selected_btn.setEnabled(True)
            elif fid:
                function=core.pl_wiring_function_caption(fid,core.light_output_associations(self.placement),self.outlet_type).split(" → ",1)[0]
                self.wago_for_selected_btn.setText(f"+ Wago {function} → udtag"); self.wago_for_selected_btn.setEnabled(True)
            else:
                self.wago_for_selected_btn.setText("+ Wago → udtag"); self.wago_for_selected_btn.setEnabled(False)
        if hasattr(self,"wago_loop_btn"):
            if splice is not None and not bool(splice.get("connects_to_outlet",True)):
                function=core.pl_wiring_function_caption(str(splice.get("function","") or ""),core.light_output_associations(self.placement),self.outlet_type).split(" → ",1)[0]
                self.wago_loop_btn.setText(f"Redigér samlemuffe {function}"); self.wago_loop_btn.setEnabled(True)
            elif splice is not None:
                self.wago_loop_btn.setText("+ Samlemuffe / sløjfe"); self.wago_loop_btn.setEnabled(False)
                self.wago_loop_btn.setToolTip("Den valgte leder ligger allerede i en Wago med forbindelse til lampeudtaget. Redigér eller frigør den først.")
            else:
                self.wago_loop_btn.setText("+ Samlemuffe / sløjfe")
                self.wago_loop_btn.setEnabled(True)
                self.wago_loop_btn.setToolTip("Saml kabelledere i en Wago uden forbindelse til lampeudtaget. Intet forbindes automatisk til udtaget.")

        profile=core.pl_outlet_profile(self.outlet_type,core.light_output_associations(self.placement))
        can_new=any(str(t.get("function_id","") or "") for t in profile.get("terminals",[]))
        self.wago_new_btn.setEnabled(can_new)
        if hasattr(self,"wago_manage_btn"):self.wago_manage_btn.setEnabled(can_new or bool(self.splices))

    def _splices_for_function(self,fid):
        fid=str(fid or "")
        return [x for x in self.splices if str(x.get("function","") or "")==fid]

    def _splice_for_function(self,fid):
        """Kompatibilitetshjælper: returnér første Wago på funktionen."""
        rows=self._splices_for_function(fid)
        return rows[0] if rows else None

    def _remove_key_from_splices(self,key):
        """Fjern kun medlemsreferencen; planlagte/tomme Wago'er bevares."""
        key=tuple(key or ())
        out=[]
        for splice in self.splices:
            item=dict(splice)
            members=[k for k in core.pl_splice_member_keys(splice) if k!=key]
            item["members"]=[core.pl_box_conductor_ref(k) for k in members]
            out.append(item)
        self.splices=core.normalize_pl_box_splices(out)

    def _confirm_wago_article_capacity(self,splice,member_count):
        """Sørg for at Wago-artiklen kan rumme medlemmer og evt. lampestedbro."""
        splice=dict(splice or {})
        article_no=str(splice.get("article_no","") or "").strip()
        connects=bool(splice.get("connects_to_outlet",True))
        needed=max(1,core.pl_wago_required_ports(member_count,connects))
        ports=core.pl_wago_article_capacity(article_no)
        if not article_no or not ports or ports>=needed:
            return splice
        recommended=core.pl_recommended_wago_article(member_count,connects)
        if not recommended:
            QMessageBox.warning(self,"Wago",f"Den valgte Wago {article_no} har {ports} pladser, men samlingen kræver {needed}. Der findes ingen større indbygget Wago-artikel til denne samling.")
            return None
        suffix=" inkl. bro til lampeudtaget" if connects else " uden forbindelse til lampestedet"
        box=QMessageBox(self); box.setIcon(QMessageBox.Icon.Warning); box.setWindowTitle("Wago er for lille")
        box.setText(f"Wago {article_no} har {ports} tilslutningspunkter, men samlingen kræver {needed}{suffix}.")
        box.setInformativeText(f"Skift Wago-artiklen til {recommended}?")
        change_btn=box.addButton(f"Skift til {recommended}",QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Annuller",QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton()!=change_btn:return None
        splice["article_no"]=recommended
        return splice

    def _capacity_warning_and_add_wago(self,fid,key,wiring_after):
        """Advar ved fuld terminal og tilbyd en ekstra fysisk Wago.

        Den nye Wago samler kun de direkte ledere, som ikke allerede ligger i
        andre Wago'er. Eksisterende samlinger bevares urørt. Dermed fungerer den
        automatiske hjælp også efter at flere Wago'er på samme funktion er
        blevet understøttet.
        """
        cap=core.pl_outlet_terminal_capacity(self.outlet_type,core.light_output_associations(self.placement),fid)
        if not cap:return True
        splices_after=core.reconcile_pl_box_splices(self.splices,wiring_after,self.legs)
        occ=core.pl_terminal_occupancy(fid,wiring_after,splices_after)
        if occ["terminal_count"]<=cap:return True
        profile=core.pl_outlet_profile(self.outlet_type,core.light_output_associations(self.placement))
        terminal=next((t for t in profile.get("terminals",[]) if str(t.get("function_id","") or "")==fid),{})
        label=str(terminal.get("label") or core.pl_wiring_function_caption(fid,core.light_output_associations(self.placement),self.outlet_type))
        direct=list(occ.get("direct",[]) or [])
        outlet_count=int(occ.get("splice_count",0) or 0)
        if not direct:
            QMessageBox.warning(self,"Terminalen er fuld",f"Terminal {label} bruger allerede {occ['terminal_count']}/{cap} tilslutninger via Wago-broer. Opret/redigér Wago-samlingerne manuelt og saml dem anderledes.")
            return False
        proposed_count=outlet_count+1
        if proposed_count>cap:
            QMessageBox.warning(self,"Terminalen er fuld",f"Terminal {label} kan maksimalt have {cap} tilslutninger. Selv hvis de {len(direct)} direkte ledere samles i en ny Wago, vil der være {proposed_count}/{cap} Wago-broer/tilslutninger. Redigér eller saml de eksisterende Wago'er.")
            return False
        box=QMessageBox(self); box.setIcon(QMessageBox.Icon.Warning); box.setWindowTitle("Terminalen er fuld")
        box.setText(f"Terminal {label} kan maksimalt have {cap} ledere/tilslutninger.")
        box.setInformativeText(f"Denne tilslutning giver {occ['terminal_count']}/{cap}. Saml de {len(direct)} direkte leder(e) i en Wago for {label} og forbind Wago'en til lampeudtaget med én bro? Eksisterende Wago'er ændres ikke.")
        add_btn=box.addButton(f"Opret Wago {label} og forbind",QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Annuller",QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton()!=add_btn:return False
        article_no=core.pl_recommended_wago_article(len(direct),True)
        if not article_no:
            QMessageBox.warning(self,"Wago",f"De {len(direct)} direkte ledere + én bro kan ikke rummes i én af de indbyggede Wago-artikler. Opret samlingerne manuelt.")
            return False
        item={
            "id":uuid.uuid4().hex,"function":fid,
            "members":[core.pl_box_conductor_ref(k) for k in direct],
            "article_no":article_no,"note":"","connects_to_outlet":True,
        }
        item=self._confirm_wago_article_capacity(item,len(direct))
        if item is None:return False
        self.splices=core.reconcile_pl_box_splices(list(self.splices)+[item],wiring_after,self.legs)
        return True

    def _assign_function_with_capacity_check(self,key,fid):
        key=tuple(key); fid=str(fid or "")
        before=next((str(r.get("function","") or "") for r in self.wiring if core.pl_box_conductor_key(r)==key),"")
        if before==fid:return True
        if fid and not self._confirm_switch_conductor_assignment(key,fid):
            return False
        old_splices=deepcopy(self.splices); old_wiring=deepcopy(self.wiring)
        if before:self._remove_key_from_splices(key)
        wiring_after=core.assign_pl_conductor_function(self.wiring,self.legs,key,fid)
        # Flere Wago'er på samme funktion er nu eksplicitte samlinger. En ny
        # funktionstildeling går derfor direkte til terminalen, medmindre den
        # fysiske kapacitet kræver at brugeren opretter/udvider en Wago.
        if fid and not self._capacity_warning_and_add_wago(fid,key,wiring_after):
            self.splices=old_splices; self.wiring=old_wiring; return False
        self.wiring=wiring_after
        self.splices=core.reconcile_pl_box_splices(self.splices,self.wiring,self.legs)
        return True

    def _detach_selected_conductor(self):
        key=tuple(self.selected_conductor_key or ())
        if len(key)!=4:return
        self._remove_key_from_splices(key)
        self.wiring=core.assign_pl_conductor_function(self.wiring,self.legs,key,"")
        self.selected_conductor_key=key
        self._refresh_wiring(); self._diagram_conductor_selected(key)

    def _new_wago(self):
        selected_fid=""
        if self.selected_conductor_key:
            selected_fid=next((str(x.get("function","") or "") for x in self.wiring if core.pl_box_conductor_key(x)==tuple(self.selected_conductor_key)),"")
        profile=core.pl_outlet_profile(self.outlet_type,core.light_output_associations(self.placement))
        available=[]; seen=set()
        for terminal in profile.get("terminals",[]):
            fid=str(terminal.get("function_id","") or "")
            if not fid or fid in seen:continue
            seen.add(fid); available.append(fid)
        if not available:
            QMessageBox.information(self,"Wago","Det valgte lampeudtag har ingen terminalfunktioner, der kan bruges til en Wago-samling."); return
        if selected_fid in available:
            available.remove(selected_fid); available.insert(0,selected_fid)
        counts={fid:len(self._splices_for_function(fid)) for fid in available}
        captions=[]
        for fid in available:
            base=core.pl_wiring_function_caption(fid,core.light_output_associations(self.placement),self.outlet_type)
            suffix=f" · {counts[fid]} eksisterende" if counts[fid] else ""
            captions.append(base+suffix)
        caption,ok=QInputDialog.getItem(self,"Ny Wago-samling","Vælg terminal/funktion til den nye fysiske Wago:",captions,0,False)
        if not ok:return
        idx=captions.index(caption); self._edit_wago_members(available[idx],None)

    def _edit_selected_wago(self):
        sid=str(self.wago_combo.currentData() or "")
        splice=next((x for x in self.splices if str(x.get("id","") or "")==sid),None)
        if splice is None:return
        self._edit_wago_members(str(splice.get("function","") or ""),sid)

    def _edit_wago_members(self,fid,sid=None,seed_keys=None,default_connects=None,splice_metadata=None):
        fid=str(fid or "")
        existing=next((x for x in self.splices if str(x.get("id","") or "")==str(sid or "")),None)
        splice_metadata=dict(splice_metadata or {})
        if existing is not None and not splice_metadata:
            splice_metadata={
                key:existing.get(key,"") for key in
                ("conductor_role","destination_light_uid","destination_association")
            }
        meta_map={core.pl_box_conductor_key(x):x for x in core.pl_box_conductors(self.legs)}
        function_by_key={core.pl_box_conductor_key(row):str(row.get("function","") or "") for row in self.wiring}
        existing_members=set(core.pl_splice_member_keys(existing)) if existing else set()
        seeds={tuple(k) for k in (seed_keys or []) if k}
        existing_id=str((existing or {}).get("id","") or "")
        used_elsewhere=set()
        for splice in self.splices:
            if str(splice.get("id","") or "")==existing_id:continue
            used_elsewhere.update(core.pl_splice_member_keys(splice))
        # Vis ledere med den valgte funktion samt løse ledere, men ikke ledere
        # der allerede fysisk ligger i en anden Wago. Én leder kan kun være i
        # én samling ad gangen; den kan flyttes ved at trække den til en anden.
        candidates=[]
        for row in self.wiring:
            key=core.pl_box_conductor_key(row); current_fid=str(row.get("function","") or "")
            if key in used_elsewhere and key not in existing_members and key not in seeds:continue
            if current_fid in {"",fid} or key in existing_members or key in seeds:
                candidates.append(key)
        current=set(existing_members); current.update(seeds)
        connects_initial=(bool(existing.get("connects_to_outlet",True)) if existing is not None else (True if default_connects is None else bool(default_connects)))
        current_article=str((existing or {}).get("article_no","") or "").strip()
        try:
            article_catalog={a["article_no"]:a for a in user_library.load_core_article_catalog()}
        except Exception:
            article_catalog={a["article_no"]:a for a in core.load_predefined_article_catalog()}
        wago_articles=[]
        for article_no,ports in sorted(core.PL_WAGO_ARTICLE_PORTS.items(),key=lambda kv:(0 if str(kv[0]).startswith("221-") else 1,kv[1],kv[0])):
            art=dict(article_catalog.get(article_no,{}) or {})
            description=str(art.get("description","") or f"WAGO {article_no}")
            series=("221" if str(article_no).startswith("221-") else "2273 / P100")
            wago_articles.append({"article_no":article_no,"ports":int(ports),"description":description,"series":series,"article":art})

        while True:
            function=core.pl_wiring_function_caption(fid,core.light_output_associations(self.placement),self.outlet_type)
            short_function=function.split(" → ",1)[0]
            dlg=QDialog(self); dlg.setWindowTitle(("Redigér" if existing else "Opret")+f" Wago · {short_function}"); dlg.resize(620,540)
            lay=QVBoxLayout(dlg)
            info=QLabel(
                f"<b>Wago for {short_function}</b><br>Vælg de fysiske ledere, der skal samles. Programmet foreslår en Wago-størrelse ud fra antal ledere og en eventuel bro til lampeudtaget. Både WAGO 221 og WAGO 2273 / P100 kan vælges som artikel."
            )
            info.setWordWrap(True); lay.addWidget(info)
            connect_check=QCheckBox(f"Forbind samlingen videre til {short_function}-klemmen med én bro")
            connect_check.setChecked(bool(connects_initial)); lay.addWidget(connect_check)
            local_terminal_ids={str(x.get("function_id","") or "") for x in core.pl_outlet_profile(self.outlet_type,core.light_output_associations(self.placement)).get("terminals",[]) if str(x.get("function_id","") or "")}
            if fid not in local_terminal_ids:
                connect_check.setChecked(False); connect_check.setEnabled(False)
                connect_check.setToolTip("Denne funktion tilhører et andet lampested og kan derfor ikke forbindes til det lokale lampeudtag.")
            mode_hint=QLabel(); mode_hint.setObjectName("sectionHint"); mode_hint.setWordWrap(True); lay.addWidget(mode_hint)

            members_title=QLabel("Ledere i samlingen"); members_title.setObjectName("sectionTitle"); lay.addWidget(members_title)
            lst=QListWidget(); lay.addWidget(lst,1)
            if not candidates:
                placeholder=QListWidgetItem("Ingen egnede ledere endnu – Wago'en kan stadig oprettes som planlagt samling.")
                placeholder.setFlags(placeholder.flags() & ~Qt.ItemFlag.ItemIsSelectable & ~Qt.ItemFlag.ItemIsEnabled)
                lst.addItem(placeholder)
            else:
                for key in candidates:
                    meta=meta_map.get(key,{})
                    cable=str(meta.get("cable_display") or meta.get("cable_id") or "Kabel")
                    side=str(meta.get("leg_caption") or ""); color=str(meta.get("color_name") or meta.get("display") or meta.get("core_id") or "leder")
                    original=function_by_key.get(key,"")
                    status="tildelt" if original==fid else "løs"
                    item=QListWidgetItem(" · ".join(x for x in [cable,side,color,status] if x)); item.setData(Qt.ItemDataRole.UserRole,key)
                    item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable); item.setCheckState(Qt.CheckState.Checked if key in current else Qt.CheckState.Unchecked)
                    lst.addItem(item)

            # Produktvælger: serie først, derefter fysisk variant. Det gør forskellen
            # mellem 221 og 2273/P100 synlig uden en lang teknisk dropdown.
            selector_box=QGroupBox("Wago-type")
            selector_lay=QHBoxLayout(selector_box)
            series_tabs=QTabWidget(); series_tabs.setMinimumWidth(390)
            series_lists={}
            item_by_article={}
            for series,title in (("221","221 · universel med vippepal"),("2273 / P100","2273 / P100 · PUSH WIRE")):
                page=QWidget(); page_lay=QVBoxLayout(page); page_lay.setContentsMargins(6,6,6,6)
                series_note=QLabel(
                    "221: kompakt fjedersamlemuffe med vippepal – egnet som generelt installationsvalg."
                    if series=="221" else
                    "2273 / P100: PUSH WIRE til massive/entrådede ledere 0,5–2,5 mm²."
                )
                series_note.setObjectName("sectionHint"); series_note.setWordWrap(True); page_lay.addWidget(series_note)
                widget=QListWidget(); widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection); widget.setIconSize(QSize(74,52)); widget.setSpacing(3)
                page_lay.addWidget(widget,1); series_lists[series]=widget
                for row in [x for x in wago_articles if x["series"]==series]:
                    article_no=row["article_no"]; ports=row["ports"]; art=row["article"]
                    item=QListWidgetItem(f"{article_no} · {ports} pladser")
                    item.setData(Qt.ItemDataRole.UserRole,article_no)
                    local=str(art.get("image_local_path","") or "").strip()
                    if local:
                        path=Path(local); path=path if path.is_absolute() else APP_ROOT/path
                        pm=QPixmap(str(path))
                        if not pm.isNull():item.setIcon(QIcon(pm))
                    detail=("Vippearme · fleksibel/massiv" if series=="221" else "PUSH WIRE · massiv leder")
                    item.setToolTip(f"{row['description']}\n{detail}\nKapacitet: {ports} tilslutningspunkter")
                    widget.addItem(item); item_by_article[article_no]=item
                series_tabs.addTab(page,title)
            selector_lay.addWidget(series_tabs,1)

            preview=QFrame(); preview.setObjectName("summaryCard"); preview.setMinimumWidth(235); preview.setMaximumWidth(285)
            pv=QVBoxLayout(preview); pv.setContentsMargins(12,12,12,12)
            preview_image=QLabel(); preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter); preview_image.setMinimumHeight(120); preview_image.setObjectName("articlePreview")
            preview_title=QLabel("Ingen Wago valgt"); preview_title.setObjectName("sectionTitle"); preview_title.setWordWrap(True)
            preview_capacity=QLabel(); preview_capacity.setWordWrap(True)
            preview_desc=QLabel(); preview_desc.setObjectName("sectionHint"); preview_desc.setWordWrap(True)
            preview_fit=QLabel(); preview_fit.setWordWrap(True)
            recommended_btn=QPushButton("Vælg anbefalet")
            clear_article_btn=QPushButton("Ingen artikel / ryd valg")
            pv.addWidget(preview_image); pv.addWidget(preview_title); pv.addWidget(preview_capacity); pv.addWidget(preview_desc); pv.addWidget(preview_fit); pv.addStretch(1); pv.addWidget(recommended_btn); pv.addWidget(clear_article_btn)
            selector_lay.addWidget(preview)
            lay.addWidget(selector_box)
            article_hint=QLabel(); article_hint.setObjectName("sectionHint"); article_hint.setWordWrap(True); lay.addWidget(article_hint)

            manual_article=[bool(current_article)]
            selected_article=[current_article]

            def selected_keys():
                out=[]
                for i in range(lst.count()):
                    item=lst.item(i); key=item.data(Qt.ItemDataRole.UserRole)
                    if key and item.checkState()==Qt.CheckState.Checked:out.append(tuple(key))
                return out

            def article_record(article_no):
                return next((x for x in wago_articles if x["article_no"]==article_no),None)

            def set_selected_article(article_no, *, manual=True):
                article_no=str(article_no or "").strip(); selected_article[0]=article_no
                if manual:manual_article[0]=True
                # Kun én serievariant må være valgt ad gangen.
                for series,widget in series_lists.items():
                    blocker=QSignalBlocker(widget); widget.clearSelection(); del blocker
                row=article_record(article_no)
                if row:
                    widget=series_lists[row["series"]]; item=item_by_article.get(article_no)
                    if item is not None:
                        blocker=QSignalBlocker(widget); item.setSelected(True); widget.setCurrentItem(item); del blocker
                    series_tabs.setCurrentWidget(widget.parentWidget())
                refresh_article_preview()

            def refresh_article_preview():
                article_no=str(selected_article[0] or "").strip(); row=article_record(article_no)
                count=len(selected_keys()); connects=bool(connect_check.isChecked()); needed=max(1,core.pl_wago_required_ports(count,connects))
                if not row:
                    preview_image.clear(); preview_image.setText("Ingen\nartikel")
                    preview_title.setText("Ingen artikel valgt")
                    preview_capacity.setText(f"Behov: {needed} tilslutningspunkt(er)")
                    preview_desc.setText("Wago'en kan gemmes uden artikel, men vises som manglende artikel i BOM.")
                    preview_fit.setText("Vælg en variant til højre/venstre for BOM-kobling.")
                    return
                art=row["article"]; ports=row["ports"]
                local=str(art.get("image_local_path","") or "").strip(); pm=QPixmap()
                if local:
                    path=Path(local); path=path if path.is_absolute() else APP_ROOT/path
                    pm=QPixmap(str(path))
                if pm.isNull():preview_image.setText(row["series"]); preview_image.setPixmap(QPixmap())
                else:preview_image.setPixmap(pm.scaled(210,120,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
                preview_title.setText(f"{article_no} · {row['series']}")
                preview_capacity.setText(f"Kapacitet: {ports} · behov: {needed}")
                preview_desc.setText(row["description"] + ("\nPUSH WIRE: kun massive/entrådede ledere." if row["series"]!="221" else ""))
                if ports>=needed:
                    reserve=ports-needed
                    preview_fit.setText(f"✓ Passer · {reserve} ledig(e) plads(er)" if reserve else "✓ Passer præcist")
                else:
                    preview_fit.setText(f"⚠ For lille · mangler {needed-ports} plads(er)")

            def update_variant_availability(needed):
                for row in wago_articles:
                    item=item_by_article.get(row["article_no"]); ports=row["ports"]
                    if item is None:continue
                    prefix="✓" if ports>=needed else "×"
                    item.setText(f"{prefix} {row['article_no']} · {ports} pladser" + ("" if ports>=needed else f" · kræver {needed}"))
                    # Behold for små varianter synlige som læring, men gør dem ikke valgbare.
                    flags=item.flags()
                    if ports>=needed:item.setFlags(flags|Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable)
                    else:item.setFlags((flags|Qt.ItemFlag.ItemIsSelectable)&~Qt.ItemFlag.ItemIsEnabled)

            def update_recommendation(_value=None):
                count=len(selected_keys()); connects=bool(connect_check.isChecked())
                recommended=core.pl_recommended_wago_article(count,connects); needed=max(1,core.pl_wago_required_ports(count,connects))
                update_variant_availability(needed)
                if not manual_article[0] and recommended:
                    set_selected_article(recommended,manual=False)
                if connects:
                    mode_hint.setText(f"Samling for {short_function}: {count} kabelleder(e), og én fysisk bro går videre til lampeudtaget. Du kan oprette flere Wago'er på samme funktion.")
                    article_hint.setText(f"Behov: {needed} tilslutningspunkter. Standardanbefaling: {recommended or 'ingen indbygget variant stor nok'}. 2273/P100 kan vælges manuelt, når ledertypen passer.")
                else:
                    mode_hint.setText(f"Samlemuffe / sløjfe for {short_function}: {count} kabelleder(e) samles uden forbindelse til lampeudtaget.")
                    article_hint.setText(f"Behov: {needed} tilslutningspunkt(er). Standardanbefaling: {recommended or 'ingen indbygget variant stor nok'}. 2273/P100 kan vælges manuelt, når ledertypen passer.")
                recommended_btn.setText(f"Vælg anbefalet · {recommended}" if recommended else "Ingen anbefalet størrelse")
                recommended_btn.setEnabled(bool(recommended))
                refresh_article_preview()

            def list_selected(series):
                widget=series_lists[series]; item=widget.currentItem()
                if item is None or not bool(item.flags() & Qt.ItemFlag.ItemIsEnabled):return
                set_selected_article(item.data(Qt.ItemDataRole.UserRole),manual=True)

            for series,widget in series_lists.items():
                widget.itemSelectionChanged.connect(lambda s=series:list_selected(s))
            recommended_btn.clicked.connect(lambda:set_selected_article(core.pl_recommended_wago_article(len(selected_keys()),bool(connect_check.isChecked())),manual=True))
            clear_article_btn.clicked.connect(lambda:set_selected_article("",manual=True))
            lst.itemChanged.connect(update_recommendation); connect_check.toggled.connect(update_recommendation)
            if current_article:set_selected_article(current_article,manual=False)
            update_recommendation()

            buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject); lay.addWidget(buttons)
            if dlg.exec()!=QDialog.DialogCode.Accepted:return
            selected=selected_keys(); connects=bool(connect_check.isChecked())
            article_no=str(selected_article[0] or "").strip()
            if not article_no and not manual_article[0]:article_no=core.pl_recommended_wago_article(len(selected),connects)
            ports=core.pl_wago_article_capacity(article_no); needed=max(1,core.pl_wago_required_ports(len(selected),connects))
            if article_no and ports and ports<needed:
                recommended=core.pl_recommended_wago_article(len(selected),connects)
                suffix=" inkl. bro til lampeudtaget" if connects else " uden bro"
                QMessageBox.warning(self,"Wago",f"{article_no} har kun {ports} tilslutningspunkter, men samlingen kræver {needed}{suffix}. Vælg {recommended or 'en større Wago'}.")
                current=set(selected); current_article=article_no; connects_initial=connects; continue

            selected_set=set(selected)
            if fid.startswith(("switch:","traveller:")):
                checked=set()
                for key in selected_set:
                    current_fid=str(function_by_key.get(key,"") or "")
                    token=(str(key[0]),str(key[3]))
                    if current_fid==fid or token in checked:
                        continue
                    checked.add(token)
                    if not self._confirm_switch_conductor_assignment(key,fid):
                        return
            new_wiring=deepcopy(self.wiring)
            # Både Wago med bro og ren sløjfe bruger eksplicit medlemskab.
            # Valgte løse ledere får funktionen; afmarkerede ledere beholder
            # deres funktion og bliver blot direkte/ikke længere medlem her.
            for key in selected_set:
                new_wiring=core.assign_pl_conductor_function(new_wiring,self.legs,key,fid)

            new_id=str((existing or {}).get("id","") or uuid.uuid4().hex)
            others=[dict(x) for x in self.splices if str(x.get("id","") or "")!=new_id]
            new_splice={
                "id":new_id,"function":fid,"members":[core.pl_box_conductor_ref(k) for k in selected],
                "article_no":article_no,"note":str((existing or {}).get("note","") or ""),
                "connects_to_outlet":connects,
            }
            if not connects:
                new_splice.update({
                    "conductor_role":str(splice_metadata.get("conductor_role") or core.normalize_pl_passthrough_role("",fid)),
                    "destination_light_uid":str(splice_metadata.get("destination_light_uid") or ""),
                    "destination_association":str(splice_metadata.get("destination_association") or core.pl_passthrough_function_parts(fid).get("association","") or ""),
                })
            existing_position=core.normalize_pl_splice_position((existing or {}).get("position"))
            if existing_position is not None:new_splice["position"]=existing_position
            self.wiring=new_wiring
            self.splices=core.reconcile_pl_box_splices(others+[new_splice],self.wiring,self.legs)
            self._refresh_wiring()
            idx=self.wago_combo.findData(new_id)
            if idx>=0:self.wago_combo.setCurrentIndex(idx)
            return

    def _remove_selected_wago(self):
        sid=str(self.wago_combo.currentData() or ""); splice=next((x for x in self.splices if str(x.get("id","") or "")==sid),None)
        if splice is None:return
        fid=str(splice.get("function","") or "")
        connects=bool(splice.get("connects_to_outlet",True))
        proposed=[dict(x) for x in self.splices if str(x.get("id","") or "")!=sid]
        if not connects:
            text="Fjern den valgte samlemuffe? De ledere der kun er samlet i denne Wago frigøres og bliver løse i PL-dåsen; de flyttes ikke automatisk til lampeudtaget."
            if QMessageBox.question(self,"Fjern samlemuffe",text)!=QMessageBox.StandardButton.Yes:return
            members=set(core.pl_splice_member_keys(splice))
            new_wiring=deepcopy(self.wiring)
            for key in members:
                new_wiring=core.assign_pl_conductor_function(new_wiring,self.legs,key,"")
            self.wiring=new_wiring; self.splices=core.reconcile_pl_box_splices(proposed,self.wiring,self.legs); self._refresh_wiring(); return
        cap=core.pl_outlet_terminal_capacity(self.outlet_type,core.light_output_associations(self.placement),fid)
        occ=core.pl_terminal_occupancy(fid,self.wiring,proposed)
        text="Fjern den valgte Wago-samling? Lederne forbliver tildelt samme funktion og går derefter direkte til lampeudtaget."
        if cap and occ["terminal_count"]>cap:text+=f"\n\n⚠ Terminalen vil derefter være overfyldt: {occ['terminal_count']}/{cap}."
        if QMessageBox.question(self,"Fjern Wago",text)!=QMessageBox.StandardButton.Yes:return
        self.splices=proposed; self._refresh_wiring()

    def _outlet_type_changed(self):
        self.outlet_type=core.normalize_pl_outlet_type(self.outlet_type_combo.currentData())
        self._refresh_wiring()

    def _pl_graphics_detail_toggled(self,checked):
        detailed=bool(checked)
        self.graphics_detail_btn.setText("Detaljeret" if detailed else "Kompakt")
        self.graphics_detail_btn.setToolTip(
            "Detaljeret viser artikelnummer, pladsforbrug og ekstra terminaltekst." if detailed
            else "Kompakt prioriterer lederforløbet; hold musen over Wago/klemmer for detaljer."
        )
        self.wiring_diagram.set_detail_mode(detailed)

    def _toggle_wiring_details(self,checked):
        self.wiring_details_panel.setVisible(bool(checked))
        self.wiring_details_btn.setText("Skjul tabel / avanceret" if checked else "Vis tabel / avanceret")

    def _update_wiring_selection_label(self,key=None):
        if not hasattr(self,"wiring_selection_label"):
            return
        key=tuple(key) if key else None
        self.selected_conductor_key=key
        if key and hasattr(self,"switch_conductor_card"):
            uid=str(key[0] or "")
            if uid and self.switch_conductor_card.current_cable_uid()!=uid:
                self._refresh_switch_conductor_usage(selected_uid=uid)
        if not key:
            self.wiring_selection_label.setText("Ingen leder valgt · start med en farvet leder ved en kabelindføring")
            if hasattr(self,"wiring_detach_btn"):self.wiring_detach_btn.setEnabled(False)
            return
        meta={core.pl_box_conductor_key(x):x for x in core.pl_box_conductors(self.legs)}.get(key,{})
        wr=next((x for x in self.wiring if core.pl_box_conductor_key(x)==key),{})
        cable=str(meta.get("cable_display") or meta.get("cable_id") or "Kabel")
        side=str(meta.get("leg_caption") or "")
        color=str(meta.get("color_name") or meta.get("display") or meta.get("label") or meta.get("core_id") or "leder")
        fid=str(wr.get("function","") or "")
        function=core.pl_wiring_function_caption(fid,core.light_output_associations(self.placement),self.outlet_type)
        if not fid:
            allocation=dict(getattr(self,"_current_external_allocations",{}).get(key,{}) or {})
            functions=list(allocation.get("functions",[]) or [])
            if functions:
                remote=" / ".join(core.pl_wiring_function_caption(x).split(" → ",1)[0] for x in functions)
                function=f"Lokalt ikke forbundet · allerede allokeret som {remote}"
        splice=next((x for x in self.splices if key in core.pl_splice_member_keys(x)),None)
        wago_text=("Wago→udtag" if bool(splice.get("connects_to_outlet",True)) else "Samlemuffe · ingen udtag") if splice is not None else ""
        bits=[cable,side,color,"→ "+function,wago_text]
        self.wiring_selection_label.setText(" · ".join(x for x in bits if x))
        if hasattr(self,"wiring_detach_btn"):self.wiring_detach_btn.setEnabled(bool(fid))

    def _wiring_table_selection_changed(self):
        row=self.wiring_table.currentRow()
        if row<0:return
        item=self.wiring_table.item(row,0)
        key=item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if key:
            key=tuple(key); self.wiring_diagram.set_selected_conductor(key); self._update_wiring_selection_label(key)

    def _diagram_conductor_selected(self,key):
        key=tuple(key); self._update_wiring_selection_label(key)
        if hasattr(self,"wago_for_selected_btn"):self._refresh_wago_controls()
        for row in range(self.wiring_table.rowCount()):
            item=self.wiring_table.item(row,0)
            if item is not None and tuple(item.data(Qt.ItemDataRole.UserRole) or ())==key:
                self.wiring_table.selectRow(row)
                self.wiring_table.scrollToItem(item,QAbstractItemView.ScrollHint.PositionAtCenter)
                break

    def _diagram_function_assigned(self,key,function_id):
        key=tuple(key); fid=str(function_id or "")
        if not self._assign_function_with_capacity_check(key,fid):
            self._refresh_wiring(); self._diagram_conductor_selected(key); return
        self._refresh_wiring(); self._diagram_conductor_selected(key); self.wiring_diagram.flash_connection(key)

    def _diagram_conductor_action(self,key,action):
        key=tuple(key); action=str(action or "")
        fid=next((str(x.get("function","") or "") for x in self.wiring if core.pl_box_conductor_key(x)==key),"")
        splice=next((x for x in self.splices if key in core.pl_splice_member_keys(x)),None)

        if action.startswith("new_wago_for:"):
            target_fid=action.split(":",1)[1]
            if not target_fid:return
            self._edit_wago_members(target_fid,None,seed_keys=[key],default_connects=True)
            return

        if action.startswith("add_to_splice:"):
            sid=action.split(":",1)[1]
            target=next((x for x in self.splices if str(x.get("id","") or "")==sid),None)
            if target is None:return
            target_fid=str(target.get("function","") or "")
            if fid and fid!=target_fid:
                answer=QMessageBox.question(self,"Flyt leder til Wago",f"Lederen er allerede tildelt {core.pl_wiring_function_caption(fid,core.light_output_associations(self.placement),self.outlet_type)}.\n\nSkift funktionen og flyt lederen til den valgte Wago?")
                if answer!=QMessageBox.StandardButton.Yes:return
            old_wiring=deepcopy(self.wiring); old_splices=deepcopy(self.splices)
            self._remove_key_from_splices(key)
            new_wiring=core.assign_pl_conductor_function(self.wiring,self.legs,key,target_fid)
            updated=dict(target)
            members=list(core.pl_splice_member_keys(updated))
            if key not in members:members.append(key)
            updated["members"]=[core.pl_box_conductor_ref(k) for k in members]
            updated=self._confirm_wago_article_capacity(updated,len(members))
            if updated is None:
                self.wiring=old_wiring; self.splices=old_splices; return
            others=[dict(x) for x in self.splices if str(x.get("id","") or "")!=sid]
            self.wiring=new_wiring
            self.splices=core.reconcile_pl_box_splices(others+[updated],self.wiring,self.legs)
            self._refresh_wiring(); self._diagram_conductor_selected(key); return

        if action=="loop_wago":
            self._new_loop_wago(key,fid)
            return

        if action=="add_wago":
            if not fid:
                QMessageBox.information(self,"Wago","Tildel først lederen en funktion/klemme, eller vælg 'Sløjf leder i Wago uden lampested'."); return
            self._edit_wago_members(fid,None,seed_keys=[key])
            return
        if action=="edit_wago":
            if splice is not None:self._edit_wago_members(str(splice.get("function","") or ""),str(splice.get("id","") or ""),seed_keys=[key])
            return
        if action=="remove_wago":
            if splice is None:return
            connects=bool(splice.get("connects_to_outlet",True))
            text=("Fjern lederen fra Wago'en og frigør dens funktion?" if connects else "Fjern lederen fra samlemuffen og frigør dens funktion?")
            if QMessageBox.question(self,"Wago",text)!=QMessageBox.StandardButton.Yes:return
            self._remove_key_from_splices(key)
            self.wiring=core.assign_pl_conductor_function(self.wiring,self.legs,key,"")
            self.splices=core.reconcile_pl_box_splices(self.splices,self.wiring,self.legs)
            self._refresh_wiring(); self._diagram_conductor_selected(key)

    def _diagram_function_action(self,fid,action):
        fid=str(fid or ""); action=str(action or "")
        if not fid:return
        if action=="new":
            seed=[]
            key=tuple(self.selected_conductor_key or ())
            if len(key)==4 and not any(key in core.pl_splice_member_keys(x) for x in self.splices):seed=[key]
            self._edit_wago_members(fid,None,seed_keys=seed,default_connects=True)
        elif action=="new_loop":
            seed=[]
            key=tuple(self.selected_conductor_key or ())
            if len(key)==4 and not any(key in core.pl_splice_member_keys(x) for x in self.splices):seed=[key]
            self._new_loop_wago(seed[0] if seed else None,fid)

    def _diagram_splice_moved(self,sid,x,y):
        sid=str(sid or ""); changed=False; out=[]
        for splice in self.splices:
            item=dict(splice)
            if str(item.get("id","") or "")==sid:
                item["position"]={"x":max(0.0,min(1.0,float(x))),"y":max(0.0,min(1.0,float(y)))}; changed=True
            out.append(item)
        if changed:
            self.splices=core.reconcile_pl_box_splices(out,self.wiring,self.legs)
            self._refresh_wiring()

    def _change_loop_splice_identity(self,splice):
        splice=dict(splice or {})
        if not splice or bool(splice.get("connects_to_outlet",True)):return
        members=list(core.pl_splice_member_keys(splice))
        identity=self._choose_passthrough_identity(members[0] if members else None,str(splice.get("function") or ""),splice)
        if identity is None:return
        new_fid=str(identity.get("function") or "")
        old_fid=str(splice.get("function") or "")
        if new_fid!=old_fid and new_fid.startswith(("switch:","traveller:")):
            checked=set()
            for key in members:
                token=(str(key[0]),str(key[3]))
                if token in checked:continue
                checked.add(token)
                if not self._confirm_switch_conductor_assignment(key,new_fid):return
        new_wiring=deepcopy(self.wiring)
        for key in members:new_wiring=core.assign_pl_conductor_function(new_wiring,self.legs,key,new_fid)
        updated=dict(splice); updated.update(identity); updated["function"]=new_fid; updated["connects_to_outlet"]=False
        sid=str(updated.get("id") or "")
        others=[dict(row) for row in self.splices if str(row.get("id") or "")!=sid]
        self.wiring=new_wiring
        self.splices=core.reconcile_pl_box_splices(others+[updated],self.wiring,self.legs)
        self._refresh_wiring()

    def _diagram_splice_action(self,sid,action):
        sid=str(sid or ""); action=str(action or "")
        splice=next((x for x in self.splices if str(x.get("id","") or "")==sid),None)
        if splice is None:return
        if action=="edit":
            self._edit_wago_members(str(splice.get("function","") or ""),sid); return
        if action=="destination":
            self._change_loop_splice_identity(splice); return
        if action=="remove":
            idx=self.wago_combo.findData(sid)
            if idx>=0:self.wago_combo.setCurrentIndex(idx)
            self._remove_selected_wago(); return
        if action=="reset_position":
            out=[]
            for row in self.splices:
                item=dict(row)
                if str(item.get("id","") or "")==sid:item.pop("position",None)
                out.append(item)
            self.splices=core.reconcile_pl_box_splices(out,self.wiring,self.legs); self._refresh_wiring()

    def _wiring_combo_changed(self,key,combo):
        fid=str(combo.currentData() or ""); key=tuple(key)
        if not self._assign_function_with_capacity_check(key,fid):
            self._refresh_wiring(); self._diagram_conductor_selected(key); return
        self._refresh_wiring(); self._diagram_conductor_selected(key)


    def _reset_wiring(self):
        if self.wiring and QMessageBox.question(self,"Lederfordeling","Nulstil lederplanen? Alle lederforbindelser og Wago-samlinger ryddes, så lederplanen bliver helt ufordelt.")!=QMessageBox.StandardButton.Yes:
            return
        self.wiring=core.reconcile_pl_box_wiring([],self.legs)
        self.splices=[]
        self._refresh_wiring()

    def _select_port(self,port):
        self._save_note(); self.selected_port=int(port); self._refresh_detail(); self.diagram.set_state(self.entries,self.legs,self.selected_port,self.orientation,self.cable_categories)

    def _refresh_detail(self):
        port=str(self.selected_port); entry=self.entries.get(port); leg=self._leg_for_entry(entry)
        self.port_value.setText(port)
        if leg:
            cid=str(leg.get("cable_display") or leg.get("cable_id") or "Kabel")
            category=self._category_for_leg(leg); category_name=str(category.get("name") or "Øvrige")
            category_color=html.escape(str(category.get("color") or core.DEFAULT_CABLE_COLOR))
            self.cable_value.setText(cid)
            self.type_value.setText(str(leg.get("cable_spec") or "—"))
            self.category_value.setText(f'<span style="color:{category_color}; font-weight:700">●</span> <b>{html.escape(category_name)}</b>')
            self.category_value.setToolTip(str(category.get("description") or ""))
            self.leg_value.setText(str(leg.get("leg_caption") or "—"))
            self.note_edit.setText(str(entry.get("note","") or "")); self.remove_btn.setEnabled(True)
        else:
            self.cable_value.setText("Ledig"); self.type_value.setText("—"); self.category_value.setText("—"); self.category_value.setToolTip(""); self.leg_value.setText("—"); self.note_edit.setText(""); self.remove_btn.setEnabled(False)
        self.note_edit.setEnabled(bool(entry))

    def _save_note(self):
        entry=self.entries.get(str(self.selected_port))
        if entry is not None:
            entry["note"]=self.note_edit.text().strip()

    def _leg_selection_changed(self):
        item=self.leg_list.currentItem(); leg=item.data(Qt.ItemDataRole.UserRole) if item else None
        if isinstance(leg,dict):
            port=self._entry_port_for_leg(leg)
            if port:
                self._select_port(port)

    def _place_leg(self,port,leg,ask_replace=True):
        if not isinstance(leg,dict):return
        port=max(1,min(core.PL_BOX_ENTRY_COUNT,int(port)))
        key=self._identity(leg)
        existing=self.entries.get(str(port))
        if existing is not None:
            old=self._leg_for_entry(existing)
            if old is not None and self._identity(old)!=key and ask_replace:
                answer=QMessageBox.question(self,"PL-dåse",f"Indføring {port} er allerede optaget af {old.get('cable_display') or old.get('cable_id') or 'et kabel'}.\n\nVil du erstatte placeringen?")
                if answer!=QMessageBox.StandardButton.Yes:return
        # Et fysisk kabelben må kun optage én indføring.
        for p,e in list(self.entries.items()):
            if (str(e.get("cable_uid","")),int(e.get("point_index",0) or 0),str(e.get("leg","")))==key:
                self.entries.pop(p,None)
        self.entries[str(port)]={"cable_uid":key[0],"point_index":key[1],"leg":key[2],"note":str((existing or {}).get("note","") or "") if existing and self._leg_for_entry(existing) and self._identity(self._leg_for_entry(existing))==key else ""}
        self.selected_port=port; self._refresh()

    def _place_selected(self):
        item=self.leg_list.currentItem(); leg=item.data(Qt.ItemDataRole.UserRole) if item else None
        if not isinstance(leg,dict):
            QMessageBox.information(self,"PL-dåse","Vælg et kabelben i listen først."); return
        self._place_leg(self.selected_port,leg)

    def _drop_leg(self,port,leg):
        self._place_leg(port,leg)

    def _remove_selected_port(self):
        self._save_note(); self.entries.pop(str(self.selected_port),None); self._refresh()

    def _auto_assign(self):
        self._save_note(); self.entries=core.auto_assign_pl_box_entries(self.legs,self.entries); self._refresh()

    def _clear_entries(self):
        if not self.entries:return
        if QMessageBox.question(self,"PL-dåse","Ryd alle seks indføringsplaceringer? Kablerne på plantegningen slettes ikke.")!=QMessageBox.StandardButton.Yes:return
        self.entries={}; self._refresh()

    def _apply(self):
        self._save_note(); self.entries=core.reconcile_pl_box_entries(self.entries,self.legs)
        self.wiring=core.reconcile_pl_box_wiring(self.wiring,self.legs)
        self.splices=core.reconcile_pl_box_splices(self.splices,self.wiring,self.legs)
        if callable(self.apply_callback): self.apply_callback(deepcopy(self.entries),deepcopy(self.wiring),self.outlet_type,deepcopy(self.splices),self.orientation,deepcopy(self.field_record))

    def _accept(self):
        self._apply(); self.accept()
