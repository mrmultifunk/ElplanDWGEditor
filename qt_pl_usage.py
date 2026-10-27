from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, Signal, QSignalBlocker
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget


class SwitchConductorUsageStrip(QWidget):
    """Compact visual overview of conductor use on one physical cable."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cores: list[dict] = []
        self.setMinimumHeight(58)
        self.setMaximumHeight(68)

    def set_cores(self, cores) -> None:
        self._cores = [dict(x) for x in (cores or []) if isinstance(x, dict)]
        self.update()

    @staticmethod
    def _switch_caption(fid: str) -> str:
        fid = str(fid or "")
        if fid.startswith("traveller:"):
            bits=fid.split(":")
            letter=bits[1] if len(bits)>1 else ""
            index=bits[2] if len(bits)>2 else "1"
            return f"Mellemleder {index}" + (f" · {letter}" if letter else "")
        if not fid.startswith("switch:"):
            return fid
        token = fid.split(":", 1)[1]
        return "Tænding" if token in {"", "lamp"} else f"Tænding {token}"

    def _status_caption(self, row: dict) -> str:
        status = str(row.get("status") or "")
        switches = [str(x) for x in row.get("control_functions", row.get("switch_functions", []))]
        if status == "conflict":
            return "⚠ " + " + ".join(self._switch_caption(x).replace("Tænding ", "") for x in switches)
        if status == "used_switch":
            return " / ".join(self._switch_caption(x) for x in switches)
        if status == "assigned_other":
            funcs = [str(x) for x in row.get("other_functions", [])]
            short = {"pe": "PE", "n": "N", "l": "Fast L", "reserve": "Reserve", "unused": "Ikke tilsl."}
            return " / ".join(short.get(x, x) for x in funcs[:2]) or "Anden funktion"
        if status == "typical_supply":
            return str(row.get("supply_caption") or "Typisk forsyning")
        return "Ledig tændleder"

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        palette = self.palette()
        text = palette.color(self.foregroundRole())
        muted = palette.color(self.foregroundRole()); muted.setAlpha(175)
        base = palette.color(self.backgroundRole())
        alt = palette.color(self.backgroundRole())
        if base.lightness() < 128:
            alt = QColor(43, 52, 64)
        else:
            alt = QColor(248, 250, 252)

        rows = self._cores
        if not rows:
            p.setPen(muted)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Ingen genkendt 3G/5G/7G-lederprofil")
            return

        margin = 3.0; gap = 5.0
        usable = max(1.0, self.width() - margin * 2 - gap * (len(rows) - 1))
        chip_w = usable / len(rows)
        chip_h = min(52.0, max(44.0, self.height() - 6.0))
        y = (self.height() - chip_h) / 2.0
        status_colors = {
            "available": QColor("#16a34a"),
            "used_switch": QColor("#2563eb"),
            "conflict": QColor("#dc2626"),
            "assigned_other": QColor("#d97706"),
            "typical_supply": QColor("#64748b"),
        }
        for i, row in enumerate(rows):
            x = margin + i * (chip_w + gap)
            rect = QRectF(x, y, chip_w, chip_h)
            status = str(row.get("status") or "available")
            accent = status_colors.get(status, QColor("#64748b"))
            fill = QColor(alt)
            if status in {"available", "used_switch", "conflict"}:
                tint = QColor(accent); tint.setAlpha(22 if base.lightness() >= 128 else 34)
                # Manually blend to avoid relying on composition modes.
                fill = QColor(
                    int((alt.red() * (255 - tint.alpha()) + tint.red() * tint.alpha()) / 255),
                    int((alt.green() * (255 - tint.alpha()) + tint.green() * tint.alpha()) / 255),
                    int((alt.blue() * (255 - tint.alpha()) + tint.blue() * tint.alpha()) / 255),
                )
            pen = QPen(accent, 1.25)
            p.setPen(pen); p.setBrush(QBrush(fill)); p.drawRoundedRect(rect, 6, 6)

            sw = QRectF(rect.left() + 7, rect.top() + 9, 14, 14)
            core_color = QColor(str(row.get("color") or "#64748b"))
            p.setPen(QPen(QColor("#475569"), 0.8)); p.setBrush(QBrush(core_color)); p.drawEllipse(sw)
            if str(row.get("core_id") or "") == "pe":
                p.setPen(QPen(QColor("#facc15"), 2.4));
                p.drawLine(sw.left() + 2, sw.bottom() - 3, sw.right() - 2, sw.top() + 3)

            label = str(row.get("color_name") or row.get("label") or row.get("core_id") or "Leder")
            p.setPen(text); p.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
            p.drawText(QRectF(sw.right() + 5, rect.top() + 5, max(1, rect.right() - sw.right() - 9), 19),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)
            p.setPen(accent if status != "typical_supply" else muted); p.setFont(QFont("Segoe UI", 7))
            p.drawText(QRectF(rect.left() + 7, rect.top() + 27, max(1, rect.width() - 14), 18),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self._status_caption(row))


class SwitchConductorUsageCard(QFrame):
    """Compact, collapsible planning aid for switched-conductor reuse.

    Lederfordelingen er PL-dialogens primære arbejdsflade. Derfor vises denne
    kabelbrede planlægningshjælp kun som en lav statuslinje som standard; det
    grafiske farve-overblik kan foldes ud efter behov.
    """
    cableChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("switchConductorCard")
        self._expanded = False
        root = QVBoxLayout(self); root.setContentsMargins(8, 4, 8, 4); root.setSpacing(3)

        head = QHBoxLayout(); head.setSpacing(7)
        title = QLabel("Tændlederhjælp"); title.setObjectName("sectionTitle"); head.addWidget(title)
        self.location = QLabel(); self.location.setObjectName("subtleText"); self.location.setMaximumWidth(230)
        self.location.setToolTip("Aktuelt lampested vist som gruppe/kreds og mærkning.")
        head.addWidget(self.location)
        self.cable_combo = QComboBox(); self.cable_combo.setMinimumWidth(170); self.cable_combo.setMaximumWidth(300)
        self.cable_combo.currentIndexChanged.connect(self._emit_cable); head.addWidget(self.cable_combo)
        head.addStretch(1)
        self.recommendation = QLabel(); self.recommendation.setObjectName("positiveText"); head.addWidget(self.recommendation)
        self.expand_btn = QToolButton(); self.expand_btn.setText("Vis overblik"); self.expand_btn.setCheckable(True)
        self.expand_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.expand_btn.setArrowType(Qt.ArrowType.RightArrow)
        self.expand_btn.setToolTip("Vis/skjul Tændleder-overblik for hele det valgte kabel.")
        self.expand_btn.toggled.connect(self.set_expanded); head.addWidget(self.expand_btn)
        root.addLayout(head)

        self.details = QWidget()
        details_root = QVBoxLayout(self.details); details_root.setContentsMargins(0, 1, 0, 1); details_root.setSpacing(2)
        self.hint = QLabel("Farverne viser brug på hele samme kabel; det er kun planlægningshjælp.")
        self.hint.setObjectName("sectionHint"); self.hint.setWordWrap(False); details_root.addWidget(self.hint)
        self.strip = SwitchConductorUsageStrip(); details_root.addWidget(self.strip)
        root.addWidget(self.details)
        self.set_expanded(False)
        self.setToolTip("Overblikket er en planlægningshjælp. Den konkrete kabelartikel/datablad og gældende installationsregler har altid forrang.")

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = bool(expanded)
        self.details.setVisible(self._expanded)
        if self.expand_btn.isChecked() != self._expanded:
            blocker = QSignalBlocker(self.expand_btn)
            self.expand_btn.setChecked(self._expanded)
            del blocker
        self.expand_btn.setArrowType(Qt.ArrowType.DownArrow if self._expanded else Qt.ArrowType.RightArrow)
        self.expand_btn.setText("Skjul overblik" if self._expanded else "Vis overblik")
        # Den sammenklappede hjælper må ikke stjæle højden fra lederdiagrammet.
        self.setMaximumHeight(142 if self._expanded else 42)
        self.updateGeometry()

    def set_location(self, group: str = "", label: str = "") -> None:
        parts=[]
        for value in (str(group or "").strip(), str(label or "").strip()):
            if value and value not in parts:
                parts.append(value)
        caption=" · ".join(parts) if parts else "Lampested"
        self.location.setText(f"Lampested: {caption}")
        self.location.setToolTip(f"Lampested: {caption}")

    def _emit_cable(self, _index: int) -> None:
        self.cableChanged.emit(str(self.cable_combo.currentData() or ""))

    def current_cable_uid(self) -> str:
        return str(self.cable_combo.currentData() or "")

    def set_cables(self, rows, selected_uid: str = "") -> None:
        current = str(selected_uid or self.current_cable_uid() or "")
        blocker = QSignalBlocker(self.cable_combo)
        self.cable_combo.clear()
        for row in rows or []:
            uid = str(row.get("cable_uid") or "")
            if uid:
                self.cable_combo.addItem(str(row.get("display") or "Kabel"), uid)
        idx = self.cable_combo.findData(current)
        self.cable_combo.setCurrentIndex(idx if idx >= 0 else (0 if self.cable_combo.count() else -1))
        del blocker
        self.setVisible(self.cable_combo.count() > 0)

    def set_usage(self, usage: dict) -> None:
        usage = dict(usage or {})
        self.strip.set_cores(usage.get("cores", []))
        recommended = str(usage.get("recommended_core_id") or "")
        rec_row = next((x for x in usage.get("cores", []) if str(x.get("core_id") or "") == recommended), None)
        if usage.get("conflicts"):
            self.recommendation.setObjectName("dangerText")
            self.recommendation.setText(f"⚠ {len(usage.get('conflicts') or [])} konflikt(er)")
        elif rec_row:
            self.recommendation.setObjectName("positiveText")
            self.recommendation.setText(f"Næste ledige: {rec_row.get('color_name') or rec_row.get('label') or recommended}")
        elif usage.get("cores"):
            self.recommendation.setObjectName("accentText")
            self.recommendation.setText("Ingen fri standardleder")
        else:
            self.recommendation.setObjectName("subtleText")
            self.recommendation.setText("Ukendt lederprofil")
        self.recommendation.style().unpolish(self.recommendation)
        self.recommendation.style().polish(self.recommendation)

class SwitchConductorUsageMixin:
    """PL-dialog helpers for cable-wide switched-conductor planning."""

    def _switch_usage_cables(self):
        import core_logic as core
        rows=[]; seen=set()
        for leg in self.legs:
            uid=str(leg.get("cable_uid","") or "")
            if not uid or uid in seen:
                continue
            spec=str(leg.get("cable_spec","") or "")
            if not core.cable_conductor_preset(spec):
                continue
            seen.add(uid)
            display=str(leg.get("cable_display") or leg.get("cable_id") or "Kabel")
            if spec: display += f" · {spec}"
            rows.append({"cable_uid":uid,"display":display})
        def rank(row):
            cable=next((c for c in self.cables if str(getattr(c,"uid","") or "")==row["cable_uid"]),None)
            spec=str(getattr(cable,"cable_spec","") or "").upper() if cable is not None else ""
            return (0 if "7G" in spec else (1 if "5G" in spec else 2), str(row.get("display") or ""))
        rows.sort(key=rank)
        return rows

    def _switch_usage_cable_changed(self,_uid=None):
        self._refresh_switch_conductor_usage(preserve_combo=True)

    def _refresh_switch_conductor_usage(self, selected_uid=None, preserve_combo=False):
        import core_logic as core
        if not hasattr(self,"switch_conductor_card"):
            return
        rows=self._switch_usage_cables()
        current=str(selected_uid or (self.switch_conductor_card.current_cable_uid() if preserve_combo else "") or "")
        if not current and self.selected_conductor_key:
            current=str(tuple(self.selected_conductor_key)[0] or "")
        self.switch_conductor_card.set_cables(rows,current)
        uid=self.switch_conductor_card.current_cable_uid()
        if not uid:
            self.switch_conductor_card.set_usage({})
            return
        usage=core.cable_switch_conductor_usage(
            uid,self.placements,self.cables,
            current_placement_uid=str(getattr(self.placement,"uid","") or ""),
            current_wiring=self.wiring,
        )
        self.switch_conductor_card.set_usage(usage)

    def _confirm_switch_conductor_assignment(self,key,fid):
        import core_logic as core
        from PySide6.QtWidgets import QMessageBox
        fid=str(fid or ""); key=tuple(key or ())
        if not fid.startswith(("switch:","traveller:")) or len(key)!=4:
            return True
        advice=core.cable_switch_conductor_assignment_advice(
            key[0],key[3],fid,self.placements,self.cables,
            current_placement_uid=str(getattr(self.placement,"uid","") or ""),
            current_wiring=self.wiring,
        )
        row=advice.get("core") or {}
        color=str(row.get("color_name") or row.get("label") or key[3])
        conflicts=list(advice.get("conflicting_switch_functions") or [])
        if conflicts:
            labels=[core.pl_wiring_function_caption(x).split(" → ",1)[0] for x in conflicts]
            places=[]
            for item in row.get("usages",[]):
                if str(item.get("function") or "") in conflicts:
                    place=str(item.get("placement") or "Lampested")
                    if place not in places: places.append(place)
            where=(" ved "+", ".join(places[:4])) if places else ""
            target=core.pl_wiring_function_caption(fid,getattr(self.placement,"associations",[])).split(" → ",1)[0]
            text=(f"{color} på dette kabel er allerede registreret som {', '.join(labels)}{where}.\n\n"
                  f"Vil du alligevel bruge samme lederfarve som {target} her?")
            return QMessageBox.question(self,"Tændleder er allerede i brug",text)==QMessageBox.StandardButton.Yes
        if advice.get("typical_supply") and not advice.get("same_switch_already_used"):
            supply=str(row.get("supply_caption") or "typisk forsyningsleder")
            target=core.pl_wiring_function_caption(fid,getattr(self.placement,"associations",[])).split(" → ",1)[0]
            text=(f"{color} er markeret som {supply} og bliver derfor normalt ikke foreslået som ny tændleder.\n\n"
                  f"Vil du bevidst bruge den som {target}?")
            return QMessageBox.question(self,"Typisk forsyningsleder",text)==QMessageBox.StandardButton.Yes
        return True
