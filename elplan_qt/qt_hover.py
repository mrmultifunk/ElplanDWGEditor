from __future__ import annotations

import html
import math

from PySide6.QtCore import Qt, QPoint, QPointF, QRectF, QSize
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

import core_logic as core
from elplan_catalog import price_display
from elplan_catalog import user_library
from elplan_catalog.hover_bom import build_hover_bom_html
from elplan_qt.qt_graphics import symbol_icon
from elplan_qt.qt_theme import _application_dark, _theme_color

class _HoverPreviewWidget(QWidget):
    """Kompakt, rent visuel preview til hover-kort på plantegningen."""

    def __init__(self,parent=None):
        super().__init__(parent)
        self._mode=""
        self._data={}
        self.setFixedSize(190,132)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents,True)

    def set_content(self,mode: str,data=None) -> None:
        self._mode=str(mode or "")
        self._data=dict(data or {})
        self.setVisible(bool(self._mode))
        self.update()

    @staticmethod
    def _leg_identity(row):
        return (str(row.get("cable_uid","") or ""),int(row.get("point_index",0) or 0),str(row.get("leg","") or ""))

    @staticmethod
    def _side_point(body: QRectF, side: str, index: int):
        fractions=(0.22,0.50,0.78); t=fractions[max(0,min(2,int(index)))]
        if side=="top": return QPointF(body.left()+body.width()*t,body.top()),QPointF(body.left()+body.width()*t,body.top()-24)
        if side=="bottom": return QPointF(body.left()+body.width()*t,body.bottom()),QPointF(body.left()+body.width()*t,body.bottom()+24)
        if side=="left": return QPointF(body.left(),body.top()+body.height()*t),QPointF(body.left()-24,body.top()+body.height()*t)
        return QPointF(body.right(),body.top()+body.height()*t),QPointF(body.right()+24,body.top()+body.height()*t)

    def _draw_pl(self,p: QPainter,rect: QRectF) -> None:
        body=QRectF(rect.center().x()-45,rect.center().y()-43,90,86)
        dark=_application_dark()
        outline=QColor("#8b99a8") if dark else QColor("#52657a")
        body_fill=QColor("#2c333b") if dark else QColor("#f8fafc")
        inner_fill=QColor("#1d2228") if dark else QColor("#ffffff")
        muted=QColor("#9ca9b8") if dark else QColor("#64748b")
        p.setPen(QPen(outline,1.5)); p.setBrush(body_fill); p.drawRoundedRect(body,13,13)
        # Indvendig cirkel gør miniaturen genkendelig som den samme PL-grafik som i konfiguratoren.
        inner=QRectF(body.center().x()-27,body.center().y()-27,54,54)
        p.setPen(QPen(QColor("#697685") if dark else QColor("#94a3b8"),1.1)); p.setBrush(inner_fill); p.drawEllipse(inner)
        p.setPen(QPen(muted,1.0));
        p.drawLine(QPointF(inner.center().x()-5,inner.center().y()),QPointF(inner.center().x()+5,inner.center().y()))
        p.drawLine(QPointF(inner.center().x(),inner.center().y()-5),QPointF(inner.center().x(),inner.center().y()+5))

        orientation=core.normalize_pl_box_orientation(self._data.get("orientation",0))
        layout=core.pl_box_port_layout(orientation)
        entries=core.normalize_pl_box_entries(self._data.get("entries",{}))
        legs=[dict(x) for x in (self._data.get("legs",[]) or [])]
        leg_lookup={self._leg_identity(x):x for x in legs}
        for port in range(1,7):
            side,index=layout.get(port,("top",port-1))
            edge,outside=self._side_point(body,side,index)
            entry=entries.get(str(port)); leg=leg_lookup.get(self._leg_identity(entry),{}) if entry else {}
            used=bool(entry and leg)
            accent=QColor(str(leg.get("color") or "#3b82f6")) if used else (QColor("#586371") if dark else QColor("#cbd5e1"))
            if used:
                # Kabelkappe med highlight + identifikationsstribe.
                cable=QPen(QColor("#334155"),9.5); cable.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(cable); p.drawLine(outside,edge)
                face=QPen(QColor("#64748b"),5.8); face.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(face); p.drawLine(outside,edge)
                stripe=QPen(accent,1.7); stripe.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(stripe); p.drawLine(outside,edge)
            # Gennemføring.
            p.setPen(QPen((QColor("#9ca9b8") if dark else QColor("#64748b")) if used else (QColor("#5c6774") if dark else QColor("#b7c3d1")),1.1)); p.setBrush((QColor("#46515e") if dark else QColor("#e2e8f0")) if used else inner_fill);
            p.drawEllipse(QRectF(edge.x()-5.5,edge.y()-5.5,11,11))
            if used:
                # Kort 3G/5G/7G preview lige indenfor dåsen.
                cores=core.cable_conductor_preset(str(leg.get("cable_spec") or "")) or []
                dx=body.center().x()-edge.x(); dy=body.center().y()-edge.y(); length=max(1.0,math.hypot(dx,dy)); dx/=length; dy/=length; px,py=-dy,dx
                count=len(cores); spacing=2.7 if count>1 else 0.0; total=spacing*(count-1)
                for ci,meta in enumerate(cores):
                    off=-total/2+ci*spacing
                    a=QPointF(edge.x()+dx*6+px*off*0.2,edge.y()+dy*6+py*off*0.2)
                    b=QPointF(edge.x()+dx*20+px*off,edge.y()+dy*20+py*off)
                    pen=QPen(QColor(str(meta.get("color") or "#64748b")),2.0); pen.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(pen); p.drawLine(a,b)
                    if str(meta.get("core_id") or "")=="pe":
                        pe=QPen(QColor("#facc15"),0.8); pe.setStyle(Qt.PenStyle.DashLine); p.setPen(pe); p.drawLine(a,b)
            # 0.50.16: indføringsnummeret 1-6 er den vigtigste identifikation i
            # PL-miniaturen. Badgen ligger halvvejs mellem dåsekant og kabelende,
            # så især top- og bundnumrene ikke klippes af previewets kant.
            badge_center=QPointF((outside.x()+edge.x())/2.0,(outside.y()+edge.y())/2.0)
            badge_rect=QRectF(badge_center.x()-8,badge_center.y()-8,16,16)
            p.setPen(QPen(QColor("#d8e1ea") if dark else QColor("#ffffff"),1.2)); p.setBrush(QColor("#3d719f") if (used and dark) else (QColor("#315f8f") if used else (QColor("#3b434d") if dark else QColor("#e2e8f0")))); p.drawEllipse(badge_rect)
            p.setPen(QColor("#ffffff") if used else (QColor("#d0d7df") if dark else QColor("#475569"))); f=p.font(); f.setPointSizeF(7.0); f.setBold(True); p.setFont(f)
            p.drawText(badge_rect,Qt.AlignmentFlag.AlignCenter,str(port))

    def _draw_cable(self,p: QPainter,rect: QRectF) -> None:
        y=rect.center().y()-8; left=rect.left()+18; right=rect.right()-18
        accent=QColor(str(self._data.get("color") or "#3b82f6"))
        p.setPen(QPen(QColor(49,65,85,35),15,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap)); p.drawLine(QPointF(left,y),QPointF(right,y))
        p.setPen(QPen(QColor("#334155"),11,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap)); p.drawLine(QPointF(left,y),QPointF(right,y))
        p.setPen(QPen(QColor("#64748b"),7,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap)); p.drawLine(QPointF(left,y),QPointF(right,y))
        p.setPen(QPen(accent,2.3,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap)); p.drawLine(QPointF(left,y+1),QPointF(right,y+1))
        spec=str(self._data.get("spec") or "Kabel")
        p.setPen(_theme_color("#475569","#c5ced8")); f=p.font(); f.setPointSizeF(8); f.setBold(True); p.setFont(f)
        p.drawText(QRectF(rect.left()+10,y+18,rect.width()-20,22),Qt.AlignmentFlag.AlignCenter,spec)

    def _draw_symbol(self,p: QPainter,rect: QRectF) -> None:
        code=str(self._data.get("symbol") or "")
        if code:
            pix=symbol_icon(code,96).pixmap(QSize(92,92))
            target=QRectF(rect.center().x()-46,rect.top()+8,92,92).toRect()
            p.drawPixmap(target,pix)
        p.setPen(_theme_color("#64748b","#aeb9c5")); f=p.font(); f.setPointSizeF(7.2); f.setBold(True); p.setFont(f)
        p.drawText(QRectF(rect.left()+8,rect.bottom()-24,rect.width()-16,18),Qt.AlignmentFlag.AlignCenter,"ARTIKEL / STYKLISTE")

    def paintEvent(self,event):
        super().paintEvent(event)
        if not self._mode:return
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing,True)
        rect=QRectF(self.rect()).adjusted(1,1,-1,-1)
        p.setPen(QPen(_theme_color("#d8e1eb","#3e4752"),1)); p.setBrush(_theme_color("#f7f9fc","#242a31")); p.drawRoundedRect(rect,9,9)
        inner=rect.adjusted(5,5,-5,-5)
        if self._mode=="pl":self._draw_pl(p,inner)
        elif self._mode=="cable":self._draw_cable(p,inner)
        elif self._mode=="symbol":self._draw_symbol(p,inner)


class _HoverInfoPopup(QFrame):
    """Visuelt hover-kort til kabelindføringer og artikel-/styklisteoverblik."""

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setObjectName("hoverInfoPopup")
        root=QVBoxLayout(self); root.setContentsMargins(12,10,12,11); root.setSpacing(7)
        self.title=QLabel(); self.title.setObjectName("hoverTitle"); self.title.setWordWrap(True); root.addWidget(self.title)
        # Cable marking gets its own high-contrast identity card.  It is kept
        # separate from the ordinary detail list so the user can read the cable
        # marking immediately at whole-plan zoom without hunting through text.
        self.marking_frame=QFrame(); self.marking_frame.setObjectName("hoverMarkingCard")
        marking_l=QVBoxLayout(self.marking_frame); marking_l.setContentsMargins(9,6,9,7); marking_l.setSpacing(1)
        self.marking_caption=QLabel("KABELMÆRKNING"); self.marking_caption.setObjectName("hoverMarkingCaption"); marking_l.addWidget(self.marking_caption)
        self.marking_value=QLabel(); self.marking_value.setObjectName("hoverMarkingValue"); self.marking_value.setWordWrap(True); marking_l.addWidget(self.marking_value)
        self.marking_extra=QLabel(); self.marking_extra.setObjectName("hoverMarkingExtra"); self.marking_extra.setWordWrap(True); marking_l.addWidget(self.marking_extra)
        root.addWidget(self.marking_frame)
        self.subtitle=QLabel(); self.subtitle.setObjectName("hoverSubtitle"); self.subtitle.setWordWrap(True); root.addWidget(self.subtitle)
        self.body_row=QHBoxLayout(); self.body_row.setSpacing(10); root.addLayout(self.body_row)
        self.preview=_HoverPreviewWidget(self); self.body_row.addWidget(self.preview,0,Qt.AlignmentFlag.AlignTop)
        self.details=QLabel(); self.details.setObjectName("hoverDetails"); self.details.setTextFormat(Qt.TextFormat.RichText); self.details.setWordWrap(True); self.details.setMinimumWidth(190); self.details.setMaximumWidth(310); self.body_row.addWidget(self.details,1,Qt.AlignmentFlag.AlignTop)
        self.bom_frame=QFrame(); self.bom_frame.setObjectName("hoverBomCard")
        bom_l=QVBoxLayout(self.bom_frame); bom_l.setContentsMargins(9,7,9,7); bom_l.setSpacing(3)
        self.bom_title=QLabel("▣  Artikler / styklister"); self.bom_title.setObjectName("hoverBomTitle"); bom_l.addWidget(self.bom_title)
        self.bom=QLabel(); self.bom.setObjectName("hoverBomText"); self.bom.setTextFormat(Qt.TextFormat.RichText); self.bom.setWordWrap(True); self.bom.setMaximumWidth(500); bom_l.addWidget(self.bom)
        root.addWidget(self.bom_frame)
        # Popup colors follow the global appearance theme.

    def show_content(self, content: dict, global_pos: QPoint) -> None:
        data=dict(content or {})
        self.title.setText(str(data.get("title") or ""))
        marking=str(data.get("marking") or "").strip()
        marking_extra=str(data.get("marking_extra") or "").strip()
        self.marking_value.setText(marking)
        self.marking_extra.setText(marking_extra)
        self.marking_extra.setVisible(bool(marking_extra))
        self.marking_frame.setVisible(bool(marking))
        subtitle=str(data.get("subtitle") or "")
        self.subtitle.setText(subtitle); self.subtitle.setVisible(bool(subtitle))
        details=str(data.get("details_html") or "")
        self.details.setText(details); self.details.setVisible(bool(details))
        mode=str(data.get("preview_mode") or "")
        self.preview.set_content(mode,data.get("preview_data") or {})
        bom=str(data.get("bom_html") or "")
        self.bom.setText(bom); self.bom_frame.setVisible(bool(bom))
        self.adjustSize()
        self.move_near_cursor(global_pos)
        self.show(); self.raise_()

    def move_near_cursor(self, global_pos: QPoint) -> None:
        """Place the card beside the live cursor while keeping it on-screen."""
        try:
            global_pos=QPoint(global_pos)
        except Exception:
            global_pos=QCursor.pos()
        pos=global_pos+QPoint(18,20)
        try: screen=QApplication.screenAt(global_pos)
        except Exception: screen=QApplication.primaryScreen()
        if screen is not None:
            area=screen.availableGeometry()
            x=min(max(area.left()+4,pos.x()),max(area.left()+4,area.right()-self.width()-4))
            y=min(max(area.top()+4,pos.y()),max(area.top()+4,area.bottom()-self.height()-4))
            pos=QPoint(x,y)
        self.move(pos)



class HoverInfoMixin:
    """Collision-safe controller for the delayed smart hover card.

    Legacy symbol/lampested hover previews remain available even when an object
    is selected. Drag/drawing/context-menu interactions still suppress hover
    cards so the popup never steals an active editing gesture.
    """

    @staticmethod
    def _hover_data_path_signature(path):
        try:
            stat=path.stat()
            return str(path),int(stat.st_mtime_ns),int(stat.st_size)
        except OSError:
            return str(path),0,0

    def _hover_article_lookup(self) -> dict:
        """Cache the price-overlay catalogue until either source file changes."""
        signature=(
            self._hover_data_path_signature(user_library.article_catalog_path()),
            self._hover_data_path_signature(user_library.article_prices_path()),
        )
        if signature != getattr(self,"_hover_price_lookup_signature",None):
            catalog=user_library.load_core_article_catalog()
            prices=user_library.load_article_prices()
            priced=user_library.apply_article_prices(
                catalog,prices,assume_normalized=True,prices_normalized=True,
            )
            self._hover_price_lookup={str(row.get("article_no","") or ""):row for row in priced}
            self._hover_price_lookup_signature=signature
            # Cached HTML contains price values and must follow the same source signature.
            getattr(self,"_hover_bom_cache",{}).clear()
        return getattr(self,"_hover_price_lookup",{})

    def _effective_hover_assemblies(self) -> list[dict]:
        lookup={a["id"]:a for a in core.normalize_bom_assemblies(getattr(self,"global_bom_assemblies",[]) or [])}
        for row in core.normalize_bom_assemblies(self.project.raw.get("bom_assemblies",[])):
            lookup.setdefault(row["id"],row)
        return list(lookup.values())

    def _placement_hover_bom_html(self, placement) -> str:
        """Show effective article/assembly prices for this exact symbol instance."""
        if placement is None:return ""
        uid=str(getattr(placement,"uid","") or "").strip()
        mode=price_display.normalize_vat_mode(getattr(self,"app_settings",{}).get("price_vat_mode"))
        cached=getattr(self,"_hover_bom_cache",{}).get(uid) if uid else None
        if isinstance(cached,tuple) and len(cached)==2 and cached[0]==mode:
            return cached[1]
        result=build_hover_bom_html(
            symbol=str(getattr(placement,"symbol","") or ""),placement_uid=uid,placement=placement,
            article_lookup=self._hover_article_lookup(),
            article_bindings=self.project.raw.get("placement_articles",{}),
            assembly_bindings=self.project.raw.get("placement_assemblies",{}),
            assemblies=self._effective_hover_assemblies(),vat_mode=mode,
        )
        if uid:self._hover_bom_cache[uid]=(mode,result)
        return result

    def _cable_hover_payload(self, item) -> dict:
        cable=getattr(item,"cable",None)
        if cable is None:return {}
        uid=str(getattr(cable,"uid","") or "")
        article_no=self._cable_article_bindings().get(uid,"")
        lookup={a["article_no"]:a for a in self._cable_article_catalog()} if article_no else {}
        art=lookup.get(article_no,{}) if article_no else {}
        cable_name=str(getattr(cable,"cable_id","") or "Kabel")
        circuit=str(getattr(cable,"circuit_id","") or "").strip()
        specs=core.cable_effective_specs(cable)
        spec=" / ".join(specs) if specs else str(getattr(cable,"cable_spec","") or "").strip()
        endpoint_names=[self._cable_symbol_caption(r.get("symbol_uid","")) for r in core.cable_symbol_connections(cable)]
        endpoints=" → ".join(endpoint_names) if endpoint_names else "frie ender"
        desc=str(art.get("description","") or "").strip()
        maker=str(art.get("manufacturer","") or "").strip()
        bom=""
        if article_no:
            bom=f"<span style='color:#315f8f'>●</span>&nbsp; <b>{html.escape(article_no)}</b>"
            if desc:bom+=f" · {html.escape(desc[:100])}"
        details=[]
        category=self._cable_category_record(getattr(cable,"cable_category",core.DEFAULT_CABLE_CATEGORY))["name"]
        extra=str(getattr(cable,"label","") or "").strip()
        factor,_source=self._length_scale_info()
        length=core.cable_length_metres(cable,factor) if factor is not None else None
        if circuit:details.append(f"<b>Gruppe/kreds:</b> {html.escape(circuit)}")
        details.append(f"<b>Fra → til:</b> {html.escape(endpoints)}")
        details.append(f"<b>Kategori:</b> {html.escape(category)}")
        if spec:details.append(f"<b>Type:</b> {html.escape(spec)}")
        if length is not None:details.append(f"<b>Længde:</b> {html.escape(self._fmt_metres(length))}")
        if maker:details.append(f"<b>Fabrikat:</b> {html.escape(maker)}")
        return {
            "title":f"Kabel · {cable_name}",
            "marking":cable_name,
            "marking_extra":f"Ekstra mærkning · {extra}" if extra else "",
            "subtitle":f"Fysisk kabel · {endpoints}",
            "preview_mode":"cable",
            "preview_data":{"spec":spec,"color":str(getattr(cable,"color","") or "#3b82f6")},
            "details_html":"<br>".join(details),
            "bom_html":bom,
        }

    def _clear_hover_info(self) -> None:
        if hasattr(self,"_hover_info_timer"): self._hover_info_timer.stop()
        self._hover_info_target=None
        if hasattr(self,"_hover_info_popup"): self._hover_info_popup.hide()

    def _hover_workflow_blocks(self, kind: str) -> bool:
        """Return True only for workflows that genuinely conflict with hover cards.

        Symbol placement intentionally does *not* block the legacy symbol/PL
        preview: the popup is transparent for mouse events and therefore cannot
        steal a placement click. Cable drawing, text/pattern/calibration and
        association workflows still suppress hover help to keep those gestures
        visually quiet and unambiguous.
        """
        if not hasattr(self,"_workflow_state"):
            return False
        try:
            state=dict(self._workflow_state() or {})
        except Exception:
            return False
        if not bool(state.get("active",False)):
            return False
        mode=str(state.get("mode","") or "").upper()
        if str(kind)=="symbol" and mode=="PLACERING":
            return False
        return True

    def _hover_info_enter(self, kind: str, item) -> None:
        if getattr(self,"_pending_cable_attach_symbol_uid",""):return
        if QApplication.activePopupWidget() is not None:return
        if self._hover_workflow_blocks(kind):return
        try:
            if item is None or bool(getattr(item,"_dragging",False)):return
            if self.scene.mouseGrabberItem() is not None:return
        except Exception:pass
        self._hover_info_timer.stop(); self._hover_info_popup.hide(); self._hover_info_target=(str(kind),item)
        # Cable information should be immediate enough to be useful at whole-plan
        # zoom; symbol/PL cards retain the calmer legacy delay.
        self._hover_info_timer.start(180 if str(kind)=="cable" else 500)

    def _hover_info_move(self, kind: str, item, global_pos=None) -> None:
        """Keep an already visible cable card anchored beside the cursor."""
        target=self._hover_info_target
        if target is None or target[0]!=str(kind) or target[1] is not item:
            return
        popup=getattr(self,"_hover_info_popup",None)
        if popup is None or not popup.isVisible():
            return
        try:
            pos=QPoint(global_pos) if global_pos is not None else QCursor.pos()
        except Exception:
            pos=QCursor.pos()
        popup.move_near_cursor(pos)

    def _hover_info_leave(self, kind: str, item) -> None:
        target=self._hover_info_target
        if target is not None and target[0]==str(kind) and target[1] is item:self._clear_hover_info()

    def _show_hover_info_popup(self) -> None:
        target=self._hover_info_target
        if target is None:return
        if QApplication.activePopupWidget() is not None:return
        kind,item=target
        if self._hover_workflow_blocks(kind):
            self._clear_hover_info(); return
        try:
            if bool(getattr(item,"_dragging",False)) or self.scene.mouseGrabberItem() is not None:
                self._clear_hover_info(); return
            if item is None or item.scene() is None or not item.isVisible():return
        except RuntimeError:
            self._clear_hover_info(); return
        content=self._symbol_hover_payload(item) if kind=="symbol" else self._cable_hover_payload(item) if kind=="cable" else {}
        if not content:self._hover_info_popup.hide(); return
        self._hover_info_popup.show_content(content,QCursor.pos())
