from __future__ import annotations
import sys
import os
import json
import uuid
import math
import re
import tempfile
import html
from datetime import date
from collections import defaultdict
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import Qt, QSignalBlocker, QSize, QPointF, QRectF, QTimer, Signal
from PySide6.QtPdf import QPdfDocument
from PySide6.QtGui import QAction, QActionGroup, QColor, QCursor, QKeySequence, QUndoStack, QPainter, QPainterPath, QBrush, QPen, QFont, QPixmap, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QDialog,
    QDockWidget,
    QFrame,
    QFileDialog,
    QGraphicsScene,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsEllipseItem,
    QGraphicsSimpleTextItem,
    QGridLayout,
    QHeaderView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QInputDialog,
    QScrollArea,
    QSlider,
    QStatusBar,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import core_logic as core
from elplan_catalog import user_library
from elplan_project import portability
from elplan_project import project_storage
from elplan_shared.app_logging import configure_logging, install_exception_hook
from elplan_qt.qt_table_utils import _configure_resizable_table
from elplan_project.project_model import ProjectDocument, APP_VERSION
from elplan_qt.qt_graphics import (
    AnnotationItem, CableItem, CadGraphicsView, CadLayerItem, ElectricalSymbolItem, FreeTextItem,
    QtSnapEngine, symbol_icon,
)
from elplan_qt.qt_commands import (
    AddSymbolCommand, DeleteSymbolCommand, MoveSymbolCommand, EditSymbolCommand,
    AddCableCommand, AddCableBatchCommand, CableArticleBindingsCommand, EditCableCommand, DeleteCableCommand, AssociationCommand, AddTextCommand, DeleteTextCommand,
    EditTextCommand, SpotParentCommand,
)
from elplan_qt.qt_hover import HoverInfoMixin, _HoverInfoPopup
from elplan_qt.qt_cable_attach import CableAttachMixin
from elplan_qt.qt_cable_marking import CableMarkingMixin
from elplan_qt.qt_cable_panel import CablePanelMixin
from elplan_qt.qt_cable_sections import CableSectionRoutingMixin
from elplan_qt.qt_theme import (
    _resolved_dark_mode, _application_dark, _canvas_dark,
    _application_stylesheet, _apply_application_palette,
)
from elplan_qt.qt_ui import (
    UI, tune_panel_layout, tune_form_layout, prepare_dock, DisclosureSection,
    configure_modern_dialog,
)
from elplan_qt.qt_workspace import WorkspaceUiMixin
from elplan_qt.qt_rooms import RoomUiMixin, RoomBoundaryItem, RoomLabelItem, DeleteRoomCommand
from elplan_qt.qt_visual_workspace import VisualWorkspaceMixin
from elplan_qt.qt_search import SearchUiMixin
from elplan_qt.qt_welcome import WelcomeUiMixin
from elplan_qt.qt_annotation_layout import layout_symbol_metadata, refresh_switch_association_badges
from elplan_qt.qt_project_open import ProjectOpenMixin
from elplan_qt.qt_project_storage import ProjectStorageDialog, configure_core_data_storage as run_core_data_storage_dialog
from elplan_qt.qt_settings import ApplicationSettingsMixin
from elplan_qt.qt_project_control import ProjectControlMixin
from elplan_qt.qt_project_collaboration import ProjectCollaborationMixin
from elplan_qt.qt_spots import SpotUiMixin
from elplan_qt.qt_feedback import BusyOverlay, ToastOverlay
from elplan_qt.qt_widgets import QComboBox, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QSpinBox, _resize_dialog, _set_color_button, _set_role

APP_NAME = "Elplan DWG Editor Qt"


def _load_app_icon() -> QIcon:
    """Load the application icon from bundled assets when available."""
    roots = [Path(__file__).resolve().parents[1]]
    try:
        if getattr(sys, "frozen", False):
            roots.insert(0, Path(sys.executable).resolve().parent)
    except Exception:
        pass
    tried: set[str] = set()
    for root in roots:
        for rel in (Path("assets/app_icon.ico"), Path("assets/app_icon.png"), Path("app_icon.ico"), Path("app_icon.png")):
            candidate = (root / rel).resolve()
            key = str(candidate)
            if key in tried or not candidate.exists():
                continue
            tried.add(key)
            icon = QIcon(str(candidate))
            if not icon.isNull():
                return icon
    return QIcon()


def _register_windows_app_id() -> None:
    """Ensure Windows uses the program's own taskbar identity/icon."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            f"Elplan.DWGEditor.Qt.{APP_VERSION}"
        )
    except Exception:
        pass



class CableAssistantPopup(QFrame):
    """Non-modal helper shown beside cable connection clicks.

    The user can simply keep drawing; the popup never requires confirmation.
    Its actions are shortcuts for the less common decisions at a physical
    installation point.
    """

    finishRequested = Signal()
    undoRequested = Signal()
    passByRequested = Signal()
    restartRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cableAssistantPopup")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(310)
        self.setMaximumWidth(390)
        # Styling is application-theme driven; do not pin this helper to light mode.
        root=QVBoxLayout(self); root.setContentsMargins(10,8,10,9); root.setSpacing(5)
        top=QHBoxLayout(); top.setSpacing(6)
        self.title=QLabel(""); self.title.setObjectName("cableAssistantTitle")
        self.close_button=_set_role(QPushButton("×"),"iconButton")
        self.close_button.setFixedSize(26,24); self.close_button.setToolTip("Skjul kabel-assistent")
        self.close_button.clicked.connect(self.hide)
        top.addWidget(self.title,1); top.addWidget(self.close_button)
        root.addLayout(top)
        self.message=QLabel(""); self.message.setObjectName("cableAssistantMessage"); self.message.setWordWrap(True)
        root.addWidget(self.message)
        self.hint=QLabel("Klik videre for at fortsætte samme kabel."); self.hint.setObjectName("cableAssistantHint"); self.hint.setWordWrap(True)
        root.addWidget(self.hint)
        actions=QGridLayout(); actions.setHorizontalSpacing(5); actions.setVerticalSpacing(5)
        self.finish_button=QPushButton("Afslut her"); self.finish_button.setObjectName("primaryButton")
        self.restart_button=_set_role(QPushButton("Afslut + nyt herfra"),"quietButton")
        self.pass_button=_set_role(QPushButton("Kun forbi"),"quietButton")
        self.undo_button=_set_role(QPushButton("Fortryd punkt"),"quietButton")
        self.finish_button.clicked.connect(self.finishRequested)
        self.restart_button.clicked.connect(self.restartRequested)
        self.pass_button.clicked.connect(self.passByRequested)
        self.undo_button.clicked.connect(self.undoRequested)
        actions.addWidget(self.finish_button,0,0); actions.addWidget(self.restart_button,0,1)
        actions.addWidget(self.pass_button,1,0); actions.addWidget(self.undo_button,1,1)
        root.addLayout(actions)
        self._timer=QTimer(self); self._timer.setSingleShot(True); self._timer.timeout.connect(self.hide)
        self.hide()

    def show_event(self, anchor, *, title: str, message: str, hint: str = "", first: bool = False, warning: bool = False) -> None:
        self.title.setText(str(title or "Kabel-assistent"))
        self.message.setText(str(message or ""))
        self.hint.setText(str(hint or "Klik videre for at fortsætte samme kabel."))
        self.finish_button.setVisible(not first)
        self.restart_button.setVisible(not first)
        self.pass_button.setVisible(not first)
        self.undo_button.setText("Annuller start" if first else "Fortryd punkt")
        self.setProperty("warning",bool(warning))
        self.style().unpolish(self); self.style().polish(self)
        self.adjustSize()
        parent=self.parentWidget()
        if parent is not None:
            a=anchor if isinstance(anchor,QPointF) else QPointF(parent.width()/2,parent.height()/2)
            # Prefer the side with most free viewport space so the helper does
            # not cover the next likely connection point in a dense plan.
            x=int(a.x()+14) if a.x() < parent.width()/2 else int(a.x()-self.width()-14)
            y=int(a.y()+14) if a.y() < parent.height()/2 else int(a.y()-self.height()-14)
            x=max(8,min(x,max(8,parent.width()-self.width()-8)))
            y=max(8,min(y,max(8,parent.height()-self.height()-8)))
            self.move(x,y)
        self.show(); self.raise_()
        self._timer.start(7000)






class ComboConfiguratorDialog(QDialog):
    """Qt port of the 0.21.x symbol configurator."""

    def __init__(self, parent=None, settings: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Symbolkonfigurator")
        _resize_dialog(self,720,620)
        self.settings = dict(settings or {})
        self.templates = core.normalize_combo_template_records(self.settings.get("combo_templates", []))
        self.result_code = ""
        self.result_name = ""
        self.pin_favorite = False
        self._name_manual = False
        self.module_boxes: list[QComboBox] = []

        root = QHBoxLayout(self); root.setContentsMargins(14,14,14,14); root.setSpacing(12)
        left = QVBoxLayout(); left.setSpacing(9)
        right = QVBoxLayout(); right.setSpacing(9)
        root.addLayout(left, 1)
        root.addLayout(right, 1)

        template_group = QGroupBox("Gemte skabeloner")
        tl = QGridLayout(template_group)
        self.template_combo = QComboBox()
        tl.addWidget(self.template_combo, 0, 0, 1, 3)
        b_load = QPushButton("Indlæs")
        b_save = _set_role(QPushButton("Gem"), "primaryButton")
        b_delete = _set_role(QPushButton("Slet"), "dangerButton")
        tl.addWidget(b_load, 1, 0); tl.addWidget(b_save, 1, 1); tl.addWidget(b_delete, 1, 2)
        left.addWidget(template_group)

        modules_group = QGroupBox("Afbrydermoduler")
        self.modules_layout = QVBoxLayout(modules_group); self.modules_layout.setSpacing(6)
        left.addWidget(modules_group, 1)
        add_btn = _set_role(QPushButton("+ Tilføj afbryder"), "quietButton")
        add_btn.clicked.connect(self._add_module)
        left.addWidget(add_btn)

        socket_row = QFormLayout()
        self.socket_combo = QComboBox()
        self.socket_combo.addItems(list(core.CUSTOM_SOCKET_TYPES.keys()))
        self.socket_combo.currentTextChanged.connect(self._definition_changed)
        socket_row.addRow("Stikkontakt", self.socket_combo)
        left.addLayout(socket_row)

        name_group = QGroupBox("Symbolpalette")
        ng = QGridLayout(name_group)
        self.name_edit = QLineEdit()
        self.name_edit.textEdited.connect(self._manual_name)
        auto_btn = _set_role(QPushButton("Auto"), "quietButton")
        auto_btn.clicked.connect(self._enable_auto_name)
        self.pin_check = QCheckBox("Fastgør som favorit")
        ng.addWidget(QLabel("Navn i symbolpaletten"), 0, 0, 1, 2)
        ng.addWidget(self.name_edit, 1, 0); ng.addWidget(auto_btn, 1, 1)
        ng.addWidget(self.pin_check, 2, 0, 1, 2)
        left.addWidget(name_group)

        self.preview = QLabel()
        self.preview.setMinimumSize(260, 320)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setObjectName("previewPanel")
        preview_heading=QLabel("Live preview"); preview_heading.setObjectName("sectionTitle"); right.addWidget(preview_heading)
        right.addWidget(self.preview, 1)
        self.info = QLabel("1–6 afbrydere. Stikkontakten er valgfri.")
        self.info.setWordWrap(True); self.info.setObjectName("subtleText")
        right.addWidget(self.info)
        buttons = QDialogButtonBox()
        self.place_btn = buttons.addButton("Gem og placér", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        right.addWidget(buttons)

        b_load.clicked.connect(self._load_template)
        b_save.clicked.connect(self._save_template)
        b_delete.clicked.connect(self._delete_template)
        self.template_combo.currentTextChanged.connect(lambda _x: None)

        self._add_module()
        self._add_module()
        self._refresh_templates()
        self._definition_changed()

    def _module_code(self, box: QComboBox) -> str:
        return core.CUSTOM_SWITCH_TYPES.get(box.currentText(), "switch_1")

    def modules(self) -> list[str]:
        return [self._module_code(b) for b in self.module_boxes]

    def socket_kind(self) -> str:
        return core.CUSTOM_SOCKET_TYPES.get(self.socket_combo.currentText(), "none")

    def code(self) -> str:
        return core.make_custom_combo_code(self.modules(), self.socket_kind())

    def _add_module(self, switch_name: str = "1-polet afbryder") -> None:
        if len(self.module_boxes) >= core.CUSTOM_COMBO_MAX_MODULES:
            QApplication.beep()
            return
        row = QWidget()
        lay = QHBoxLayout(row); lay.setContentsMargins(0, 0, 0, 0)
        label = QLabel(f"A{len(self.module_boxes)+1}")
        box = QComboBox(); box.addItems(list(core.CUSTOM_SWITCH_TYPES.keys()))
        if switch_name in core.CUSTOM_SWITCH_TYPES:
            box.setCurrentText(switch_name)
        remove = _set_role(QPushButton("×"), "iconButton"); remove.setMaximumWidth(34); remove.setToolTip("Fjern afbrydermodul")
        lay.addWidget(label); lay.addWidget(box, 1); lay.addWidget(remove)
        self.modules_layout.addWidget(row)
        self.module_boxes.append(box)
        box.currentTextChanged.connect(self._definition_changed)
        remove.clicked.connect(lambda _=False, w=row, b=box: self._remove_module(w, b))
        self._definition_changed()

    def _remove_module(self, widget: QWidget, box: QComboBox) -> None:
        if len(self.module_boxes) <= 1:
            return
        if box in self.module_boxes:
            self.module_boxes.remove(box)
        widget.deleteLater()
        self._renumber_rows()
        self._definition_changed()

    def _renumber_rows(self) -> None:
        for i in range(self.modules_layout.count()):
            w = self.modules_layout.itemAt(i).widget()
            if w is not None:
                lab = w.findChild(QLabel)
                if lab: lab.setText(f"A{i+1}")

    def _manual_name(self, _text: str) -> None:
        self._name_manual = True

    def _enable_auto_name(self) -> None:
        self._name_manual = False
        self._definition_changed()

    def _definition_changed(self, *_args) -> None:
        try:
            code = self.code()
        except Exception:
            return
        auto = core.custom_combo_auto_name(self.modules(), self.socket_kind())
        if not self._name_manual:
            blocker = QSignalBlocker(self.name_edit)
            self.name_edit.setText(auto)
            del blocker
        self.preview.setPixmap(symbol_icon(code, 250).pixmap(QSize(250, 250)))
        cap = core.association_capacity(code)
        self.info.setText(f"{len(self.module_boxes)} afbrydermodul(er) · {cap} lystilhørsforhold · "
                          f"{'uden stikkontakt' if self.socket_kind() == 'none' else 'med stikkontakt'}")

    def _persist_templates(self) -> None:
        data = core.load_app_settings()
        data["combo_templates"] = list(self.templates)
        core.save_app_settings(data)

    def _refresh_templates(self, select: str = "") -> None:
        blocker = QSignalBlocker(self.template_combo)
        self.template_combo.clear()
        self.template_combo.addItems([x.get("name", "") for x in self.templates])
        if select:
            self.template_combo.setCurrentText(select)
        del blocker

    def _apply_code(self, code: str, template_name: str = "") -> None:
        parsed = core.parse_custom_combo_symbol(code)
        if not parsed:
            return
        modules, socket_kind = parsed
        # Clear rows
        while self.modules_layout.count():
            item = self.modules_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.module_boxes.clear()
        reverse = {v:k for k,v in core.CUSTOM_SWITCH_TYPES.items()}
        for mod in modules:
            self._add_module(reverse.get(mod, "1-polet afbryder"))
        reverse_socket = {v:k for k,v in core.CUSTOM_SOCKET_TYPES.items()}
        self.socket_combo.setCurrentText(reverse_socket.get(socket_kind, "Ingen stikkontakt"))
        if template_name:
            self._name_manual = True
            self.name_edit.setText(template_name)
        else:
            self._name_manual = False
        self._definition_changed()

    def _load_template(self) -> None:
        name = self.template_combo.currentText().strip()
        rec = next((x for x in self.templates if x.get("name") == name), None)
        if rec:
            self._apply_code(rec.get("code", ""), name)

    def _save_template(self) -> None:
        try:
            code = self.code()
        except Exception as exc:
            QMessageBox.warning(self, "Skabelon", str(exc)); return
        name = self.name_edit.text().strip() or core.custom_combo_auto_name(self.modules(), self.socket_kind())
        rec = {"name": name, "code": code}
        idx = next((i for i,x in enumerate(self.templates) if x.get("name") == name), None)
        if idx is None: self.templates.append(rec)
        else: self.templates[idx] = rec
        self.templates = core.normalize_combo_template_records(self.templates)
        self._persist_templates()
        self._refresh_templates(name)

    def _delete_template(self) -> None:
        name = self.template_combo.currentText().strip()
        if not name: return
        self.templates = [x for x in self.templates if x.get("name") != name]
        self._persist_templates()
        self._refresh_templates()

    def _accept(self) -> None:
        try:
            code = self.code()
        except Exception as exc:
            QMessageBox.warning(self, "Symbolkonfigurator", str(exc)); return
        name = self.name_edit.text().strip() or core.custom_combo_auto_name(self.modules(), self.socket_kind())
        self.result_code = code
        self.result_name = name
        self.pin_favorite = self.pin_check.isChecked()
        self.accept()

class PrintPreviewCanvas(QWidget):
    """WYSIWYG preview rendered from the exact same PDF pipeline as export.

    Older versions rendered the live QGraphicsScene directly into the preview
    widget. Screen-space items (free text, annotations, cable labels, etc.) use
    ``ItemIgnoresTransformations`` in the editor, so their physical size inside
    a small preview widget could never reliably match the page-space sizes used
    by ReportLab. 0.35.8 therefore builds a temporary PDF with
    ``core.export_vector_pdf`` and rasterises that page for display. The preview
    is consequently a real representation of what "Gem PDF" will produce.
    """
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.paper = "A3"
        self.orientation = "Landskab"
        self.scope = "Aktuel visning"
        self.setMinimumSize(520, 420)
        self._temp_dir = tempfile.TemporaryDirectory(prefix="elplan_preview_")
        self._preview_pdf = str(Path(self._temp_dir.name) / "preview.pdf")
        self._pdf = QPdfDocument(self)
        self._pdf.statusChanged.connect(self._pdf_status_changed)
        self._page_image = None
        self._page_ratio = 1.0
        self._error = ""

    def set_options(self, paper: str, orientation: str, scope: str) -> None:
        self.paper = paper; self.orientation = orientation; self.scope = scope
        self.regenerate()

    def regenerate(self) -> None:
        """Rebuild preview through the production PDF renderer."""
        self._error = ""
        self._page_image = None
        try:
            ext = self.window._print_extents(self.scope) if self.scope == "Aktuel visning" else None
            core.export_vector_pdf(
                self._preview_pdf,
                self.window.cad_primitives,
                self.window.project.placements,
                self.window.project.cables,
                self.window._output_layer_visibility(),
                self.paper,
                self.orientation,
                texts=self.window.project.texts,
                extents_override=ext,
                # "Aktuel visning" skal bevare hele viewporten. Den gamle
                # fill-page-adfærd center-beskærede siderne for at matche
                # papirets aspekt og var derfor ikke WYSIWYG.
                fill_page=False,
                cad_opacity=self.window._output_cad_opacity(),
                annotation_mode=self.window.annotation_display_mode,
                rooms=self.window.project.rooms,
                room_labels_visible=bool(self.window.project.raw.get("room_labels_visible",True)),
                room_codes_visible=bool(self.window.project.raw.get("room_codes_visible",False)),
                room_boundaries_visible=bool(
                    self.window.room_edit_mode or self.window.project.raw.get("room_boundaries_visible",False)
                ),
            )
            self._pdf.close()
            error = self._pdf.load(self._preview_pdf)
            if error != QPdfDocument.Error.None_:
                raise RuntimeError(f"PDF-preview kunne ikke indlæses ({error}).")
            if self._pdf.status() == QPdfDocument.Status.Ready:
                self._render_loaded_pdf()
            # QPdfDocument may briefly report Loading. statusChanged completes
            # the rasterisation in that case without falling back to the old live-scene renderer.
        except Exception as exc:
            self._error = str(exc)
        self.update()

    def _pdf_status_changed(self, status) -> None:
        if status == QPdfDocument.Status.Ready:
            try:
                self._render_loaded_pdf()
                self._error = ""
            except Exception as exc:
                self._error = str(exc)
            self.update()
        elif status == QPdfDocument.Status.Error:
            self._page_image = None
            self._error = f"PDF-preview kunne ikke indlæses ({self._pdf.error()})."
            self.update()

    def _render_loaded_pdf(self) -> None:
        if self._pdf.pageCount() < 1:
            raise RuntimeError("PDF-preview indeholder ingen side.")
        pts = self._pdf.pagePointSize(0)
        self._page_ratio = max(float(pts.width()), 1.0) / max(float(pts.height()), 1.0)
        # Render at substantially higher resolution than the preview widget.
        # It is only a display bitmap; the actual export remains vector PDF.
        render_w = 1800
        render_h = max(1, int(round(render_w / max(self._page_ratio, 1e-9))))
        if render_h > 1800:
            render_h = 1800
            render_w = max(1, int(round(render_h * self._page_ratio)))
        image = self._pdf.render(0, QSize(render_w, render_h))
        if image.isNull():
            raise RuntimeError("PDF-preview gav et tomt billede.")
        self._page_image = image

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        dark=_application_dark()
        painter.fillRect(self.rect(), QColor("#14181d") if dark else QColor("#d9dde3"))
        margin = 24
        avail_w=max(20,self.width()-2*margin); avail_h=max(20,self.height()-2*margin)
        ratio=max(float(self._page_ratio),1e-9)
        if avail_w/avail_h > ratio:
            ph=avail_h; pw=ph*ratio
        else:
            pw=avail_w; ph=pw/ratio
        page_rect=QRectF((self.width()-pw)/2,(self.height()-ph)/2,pw,ph)

        # Small paper shadow + border. The white page itself comes from the PDF,
        # including its true 5 mm margin, rather than an arbitrary preview inset.
        shadow=QRectF(page_rect); shadow.translate(4,4)
        painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QBrush(QColor(0,0,0,35))); painter.drawRect(shadow)
        painter.setPen(QPen(QColor("#5c6672") if dark else QColor("#9aa2ad"),1)); painter.setBrush(QBrush(QColor("#ffffff"))); painter.drawRect(page_rect)

        if self._page_image is not None:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.drawImage(page_rect, self._page_image)
        elif self._error:
            painter.setPen(QColor("#ef9a9a") if dark else QColor("#8b2f2f"))
            painter.drawText(page_rect.adjusted(20,20,-20,-20), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                             "Forhåndsvisning kunne ikke genereres:\n" + self._error)
        else:
            painter.setPen(QColor("#b0bac5") if dark else QColor("#5f6874"))
            painter.drawText(page_rect, Qt.AlignmentFlag.AlignCenter, "Genererer forhåndsvisning…")
        painter.end()

    def close_preview(self) -> None:
        try:
            self._pdf.close()
        except Exception:
            pass
        try:
            self._temp_dir.cleanup()
        except Exception:
            pass

class PrintPreviewDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window=window
        self.setWindowTitle("Udskriftsforhåndsvisning")
        _resize_dialog(self,900,700)
        root=QVBoxLayout(self); root.setContentsMargins(14,14,14,14); root.setSpacing(10)
        controls_box=QGroupBox("Udskriftsindstillinger")
        controls=QHBoxLayout(controls_box); controls.setSpacing(8)
        self.paper=QComboBox(); self.paper.addItems(["A4","A3"])
        self.orientation=QComboBox(); self.orientation.addItems(["Auto","Portræt","Landskab"])
        self.scope=QComboBox(); self.scope.addItems(list(core.PRINT_SCOPES))
        self.dim_cad=QCheckBox("Dæmp plantegning")
        self.dim_cad.setChecked(window.print_cad_dimming)
        self.dim_cad.setToolTip("Brug den valgte baggrundstydelighed fra Lag-panelet i PDF og udskrift.")
        self.paper.setCurrentText(str(window.project.raw.get("paper_size","A3") or "A3"))
        self.orientation.setCurrentText(str(window.project.raw.get("page_orientation","Landskab") or "Landskab"))
        self.scope.setCurrentText(str(window.project.raw.get("print_scope","Aktuel visning") or "Aktuel visning"))
        controls.addWidget(QLabel("Papir")); controls.addWidget(self.paper)
        controls.addWidget(QLabel("Retning")); controls.addWidget(self.orientation)
        controls.addWidget(QLabel("Område")); controls.addWidget(self.scope)
        controls.addWidget(self.dim_cad)
        controls.addStretch(1)
        root.addWidget(controls_box)
        self.canvas=PrintPreviewCanvas(window); root.addWidget(self.canvas,1)
        buttons=QHBoxLayout(); buttons.addStretch(1)
        pdf=QPushButton("Gem PDF…"); prn=_set_role(QPushButton("Udskriv…"), "primaryButton"); close=QPushButton("Luk")
        buttons.addWidget(pdf); buttons.addWidget(prn); buttons.addWidget(close); root.addLayout(buttons)
        def changed(*_):
            self.canvas.set_options(self.paper.currentText(),self.orientation.currentText(),self.scope.currentText())
        self.paper.currentTextChanged.connect(changed); self.orientation.currentTextChanged.connect(changed); self.scope.currentTextChanged.connect(changed)
        self.dim_cad.toggled.connect(lambda checked:(self.window._print_cad_dimming_changed(checked), changed()))
        pdf.clicked.connect(lambda: self.window.export_pdf(self.paper.currentText(),self.orientation.currentText(),self.scope.currentText()))
        prn.clicked.connect(lambda: self.window.print_plan(self.paper.currentText(),self.orientation.currentText(),self.scope.currentText()))
        close.clicked.connect(self.accept)
        self.finished.connect(lambda _result: self.canvas.close_preview())
        changed()











class CableCategoryDialog(QDialog):
    """Projektets kabelkategorier: navn, farve, kontur og synlighed."""

    def __init__(self,parent,categories,layer_visibility,cables=None):
        super().__init__(parent)
        configure_modern_dialog(self,title="Kabelkategorier",size=(930,500),minimum_size=(760,420))
        self._categories=core.normalize_cable_category_records(categories)
        self._layer_visibility=dict(layer_visibility or {})
        self._counts=defaultdict(int)
        for cable in cables or []:
            self._counts[core.normalize_cable_category_id(getattr(cable,"cable_category",core.DEFAULT_CABLE_CATEGORY))]+=1

        root=QVBoxLayout(self); root.setSpacing(10)
        title=QLabel("Kabelkategorier og visuelle lag"); title.setObjectName("dialogTitle"); root.addWidget(title)
        hint=QLabel("Hver kategori er et separat lag-niveau. Vis/skjul her eller fra Vis → Kabelkategorier. Farve og linjetype gælder alle kabler i kategorien og følger med PDF/print/DXF.")
        hint.setWordWrap(True); hint.setObjectName("sectionHint"); root.addWidget(hint)

        self.table=QTableWidget(0,6,self)
        self.table.setHorizontalHeaderLabels(["Vis","Kategori","Definition","Farve","Kontur","Kabler"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4,QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5,QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.table,1)

        row=QHBoxLayout(); row.setSpacing(6)
        add=_set_role(QPushButton("Ny kategori"),"quietButton"); add.clicked.connect(self._add_category)
        delete=_set_role(QPushButton("Slet kategori"),"dangerButton"); delete.clicked.connect(self._delete_selected)
        defaults=_set_role(QPushButton("Tilføj manglende standardkategorier"),"quietButton"); defaults.clicked.connect(self._add_defaults)
        row.addWidget(add); row.addWidget(delete); row.addWidget(defaults); row.addStretch(1); root.addLayout(row)

        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self._populate()

    def _category_visible(self,cid):
        return all(self._layer_visibility.get(core.cable_category_layer_name(base,cid),self._layer_visibility.get(base,True)) for base in (core.CABLE_LAYER,core.WIRE_LAYER,core.PATCH_CABLE_LAYER))

    def _populate(self):
        self.table.setRowCount(0)
        for rec in self._categories:
            row=self.table.rowCount(); self.table.insertRow(row)
            vis=QTableWidgetItem(); vis.setFlags(vis.flags()|Qt.ItemFlag.ItemIsUserCheckable); vis.setCheckState(Qt.CheckState.Checked if self._category_visible(rec["id"]) else Qt.CheckState.Unchecked); vis.setData(Qt.ItemDataRole.UserRole,rec["id"]); self.table.setItem(row,0,vis)
            name=QTableWidgetItem(str(rec["name"])); name.setData(Qt.ItemDataRole.UserRole,rec["id"]); self.table.setItem(row,1,name)
            definition=QTableWidgetItem(str(rec.get("description","") or "")); definition.setToolTip(str(rec.get("description","") or "")); self.table.setItem(row,2,definition)
            color=QPushButton(str(rec["color"])); _set_color_button(color,str(rec["color"])); color.setProperty("category_id",rec["id"]); color.clicked.connect(lambda _=False,b=color:self._choose_color(b)); self.table.setCellWidget(row,3,color)
            style=QComboBox()
            for key,label in core.CABLE_LINE_STYLES.items(): style.addItem(label,key)
            idx=style.findData(rec["line_style"]); style.setCurrentIndex(max(0,idx)); style.setProperty("category_id",rec["id"]); self.table.setCellWidget(row,4,style)
            count=QTableWidgetItem(str(self._counts.get(rec["id"],0))); count.setFlags(count.flags()&~Qt.ItemFlag.ItemIsEditable); count.setTextAlignment(Qt.AlignmentFlag.AlignCenter); self.table.setItem(row,5,count)

    def _choose_color(self,button):
        current=QColor(core.normalize_hex_color(button.text(),core.DEFAULT_CABLE_COLOR))
        chosen=QColorDialog.getColor(current,self,"Vælg kategorifarve")
        if chosen.isValid(): _set_color_button(button,chosen.name())

    def _read_records(self):
        out=[]
        for row in range(self.table.rowCount()):
            cid=str(self.table.item(row,1).data(Qt.ItemDataRole.UserRole) or self.table.item(row,0).data(Qt.ItemDataRole.UserRole) or "")
            name=str(self.table.item(row,1).text() or "").strip() or "Kategori"
            description=str(self.table.item(row,2).text() or "").strip()
            color_widget=self.table.cellWidget(row,3); style_widget=self.table.cellWidget(row,4)
            out.append({"id":cid,"name":name,"description":description,"color":core.normalize_hex_color(color_widget.text(),core.DEFAULT_CABLE_COLOR),"line_style":core.normalize_cable_line_style(style_widget.currentData())})
        return core.normalize_cable_category_records(out)

    def _add_category(self):
        self._categories=self._read_records()
        cid="custom_"+uuid.uuid4().hex[:8]
        self._categories.append({"id":cid,"name":"Ny kategori","description":"Egen kabelkategori.","color":"#64748b","line_style":"solid"})
        self._populate(); self.table.selectRow(self.table.rowCount()-1); self.table.editItem(self.table.item(self.table.rowCount()-1,1))

    def _delete_selected(self):
        row=self.table.currentRow()
        if row<0:return
        cid=str(self.table.item(row,1).data(Qt.ItemDataRole.UserRole) or "")
        if cid==core.DEFAULT_CABLE_CATEGORY:
            QMessageBox.information(self,"Kabelkategorier","Kategorien 'Øvrige' beholdes som fallback og kan ikke slettes."); return
        count=int(self._counts.get(cid,0))
        msg=f"Slet kategorien? {count} kabel{'er' if count!=1 else ''} flyttes til 'Øvrige'." if count else "Slet kategorien?"
        if QMessageBox.question(self,"Kabelkategorier",msg)!=QMessageBox.StandardButton.Yes:return
        self.table.removeRow(row)

    def _add_defaults(self):
        current=self._read_records(); seen={r["id"] for r in current}
        for rec in core.default_cable_category_records():
            if rec["id"] not in seen: current.append(rec)
        self._categories=current; self._populate()

    def result_data(self):
        records=self._read_records()
        visible={}
        for row in range(self.table.rowCount()):
            cid=str(self.table.item(row,1).data(Qt.ItemDataRole.UserRole) or "")
            visible[cid]=self.table.item(row,0).checkState()==Qt.CheckState.Checked
        return records,visible

class MainWindow(ProjectOpenMixin, HoverInfoMixin, VisualWorkspaceMixin, WorkspaceUiMixin, ProjectCollaborationMixin, ProjectControlMixin, RoomUiMixin, SearchUiMixin, WelcomeUiMixin, ApplicationSettingsMixin, CableSectionRoutingMixin, CablePanelMixin, CableMarkingMixin, CableAttachMixin, SpotUiMixin, QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._init_project_collaboration_state()
        icon = _load_app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)
        self.resize(1600, 950)
        self.setMinimumSize(900, 600)
        self.setDockOptions(
            QMainWindow.DockOption.AnimatedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.AllowNestedDocks
        )
        self.project = ProjectDocument()
        # Materialisér den globale artikelbase i kernedatamappen. Nye versioner
        # kan tilføje standardartikler uden at overskrive brugerens egne edits.
        self.global_article_catalog=user_library.load_core_article_catalog()
        self.global_bom_assemblies=deepcopy(user_library.load_global_bom_assemblies())
        self.doc = None
        self.cad_primitives = []
        self.layer_items: dict[str, CadLayerItem] = {}
        self.symbol_items: dict[str, ElectricalSymbolItem] = {}
        self.annotation_items: dict[str, AnnotationItem] = {}
        self.text_items: dict[str, FreeTextItem] = {}
        self.generated_layer_items: dict[str, list] = defaultdict(list)
        self._init_room_ui_state()
        self._bom_highlight_placement_uids=set(); self._bom_highlight_cable_uids=set()
        self._loading_properties = False
        self._group_drag_anchor_uid = ""
        self._group_drag_before: dict[str, tuple[float,float,float]] = {}
        self._group_drag_sync = False
        self._group_drag_blocked = False
        self._symbol_drag_cables: dict[str,list[core.CablePlacement]] = {}
        self._symbol_drag_cables_changed = False
        self._cables_by_symbol_uid: dict[str,list[tuple[core.CablePlacement,dict]]] = {}
        self._symbol_drag_visual_uids: set[str] = set()
        self._last_selected_annotation_uids: set[str] = set()
        self.spot_parent_pending: list[str] = []
        # Single spots placed from the palette are selected immediately so their
        # Spot → lampested relation can be assigned just like pattern-created spots.
        self.last_individual_spot_uid = ""
        self.spot_link_overlays: list = []
        self.spot_link_paths: list = []
        self.relation_overview_items: list = []
        self.association_target_overlays: list[QGraphicsRectItem] = []
        self.association_target_overlay_by_uid: dict[str,QGraphicsRectItem] = {}
        self.association_guide: QGraphicsPathItem | None = None
        self.association_badge: QGraphicsSimpleTextItem | None = None
        self.association_source_overlay: QGraphicsEllipseItem | None = None
        self.switch_association_badges: list[QGraphicsItem] = []
        self._switch_badge_render_signature = None
        self.snap_engine: QtSnapEngine | None = None
        self.undo_stack = QUndoStack(self)
        self.undo_stack.cleanChanged.connect(self._undo_clean_changed)
        self.association_source_uid = ""
        self.association_active_letter = ""
        self.association_force_new = False
        self.association_pick_source = False
        # Førstegangs-guiden går automatisk gennem alle uafhængige betjeninger
        # på fx krone, dobbelt korrespondance, 4-tryk og kombisymboler.
        self.association_guided_setup = False
        self.association_channel_index = 0
        self._association_session_before = None
        self._association_session_dirty_before = False
        self.cable_items: dict[int, CableItem] = {}
        self._cable_chain_hover_uids: set[str] = set()
        self._cable_visual_cache: dict[int, list[tuple[float,float]]] = {}
        self._cable_visual_meta: dict[int, dict] = {}
        self._cable_parallel_groups: list[dict] = []
        self._cable_bundle_badges: list[QGraphicsItem] = []
        self._cable_visual_cache_scale = 0.0
        self.app_settings = core.load_app_settings()
        # 0.44.4: repair the cable-visual settings once.  0.44.0-0.44.3 could
        # accidentally persist parallel lanes as disabled during widget setup.
        repaired_settings = core.normalize_cable_visual_settings(self.app_settings)
        if repaired_settings != self.app_settings:
            core.save_app_settings(repaired_settings)
        self.app_settings = self._migrate_visual_workspace_settings(repaired_settings)
        # 0.51.0: appearance is machine-local, never project data. Existing
        # users stay in light mode until they choose Dark/System explicitly.
        self.appearance_mode = core.normalize_appearance_mode(self.app_settings.get("appearance_mode", "light"))
        self.dark_canvas = core.normalize_dark_canvas(self.app_settings.get("dark_canvas", True), True)
        core.register_custom_symbol_records(self.app_settings.get("custom_symbols", []))
        self.favorite_symbols = [c for c in self.app_settings.get("favorite_symbols", []) if c in core.SYMBOL_NAMES_BY_CODE]
        self.combo_templates = core.normalize_combo_template_records(self.app_settings.get("combo_templates", []))
        try:
            self.cad_background_opacity = max(0.20, min(1.0, float(self.app_settings.get("cad_background_opacity", 0.55))))
        except Exception:
            self.cad_background_opacity = 0.55
        self.print_cad_dimming = bool(self.app_settings.get("print_cad_dimming", False))
        self.annotation_display_mode = str(self.app_settings.get("annotation_display_mode", "Auto"))
        if self.annotation_display_mode not in ("Auto","Tydelig","Minimal","Skjult"):
            self.annotation_display_mode = "Auto"
        previous_mode = str(self.app_settings.get("annotation_last_visible_mode", "Auto"))
        self.annotation_last_visible_mode = previous_mode if previous_mode in ("Auto","Tydelig","Minimal") else "Auto"
        if self.annotation_display_mode != "Skjult":
            self.annotation_last_visible_mode = self.annotation_display_mode
        self.annotation_room_placement = bool(self.app_settings.get("annotation_room_placement", True))
        self.lighting_alignment_snap = bool(self.app_settings.get("lighting_alignment_snap", True))
        # Hurtig visning ligger oven på projektets egentlige lagtilstand. Det er
        # derfor sikkert at skjule hele kategorier midlertidigt uden at ændre
        # de individuelle checkbokse i Lag-panelet.
        self.quick_visibility = {
            "cad": bool(self.app_settings.get("quick_show_cad", True)),
            "symbols": bool(self.app_settings.get("quick_show_symbols", True)),
            "cables": bool(self.app_settings.get("quick_show_cables", True)),
            "patch_cables": bool(self.app_settings.get("quick_show_patch_cables", True)),
            "text": bool(self.app_settings.get("quick_show_text", True)),
        }
        self.selected_cable = None
        self._pending_cable_article_no = ""
        self._pending_cable_restart_anchor = None
        # 0.52.1: et eksisterende lampested kan kobles på en eksisterende
        # kabelstrækning med et enkelt efterfølgende klik på kablet.
        self._pending_cable_attach_symbol_uid = ""
        self._last_cable_assistant_event = None
        self._loading_cable_panel = False
        self._cable_tool_rearming = False
        # 0.53.0: cable editing lives in the unified inspector.  This flag
        # tracks drawing mode independently from whichever inspector page is visible.
        self._cable_mode_enabled = False

        core.detect_oda_exec_path()

        self.scene = QGraphicsScene(self)
        self.scene.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.BspTreeIndex)
        self.scene.setBackgroundBrush(QColor("#ffffff"))
        self.view = CadGraphicsView(self.scene, self)
        self.view.setBackgroundBrush(QColor("#ffffff"))
        # 0.50.13: fælles hover-info. Efter 0,5 s på et lampested vises den
        # fysiske kabelindføring; øvrige symboler/kabler viser kun BOM-info,
        # når der faktisk er tilknyttet artikler/styklister.
        self._hover_info_target = None
        self._hover_bom_cache = {}
        self._hover_info_popup = _HoverInfoPopup(self)
        self._hover_info_timer = QTimer(self); self._hover_info_timer.setSingleShot(True)
        self._hover_info_timer.timeout.connect(self._show_hover_info_popup)
        # Zoom can emit many updates per wheel/trackpad gesture. Heavy cable-lane
        # and annotation rebuilds are coalesced into one frame-sized refresh;
        # status text still updates immediately.
        self._zoom_visual_refresh_timer=QTimer(self); self._zoom_visual_refresh_timer.setSingleShot(True); self._zoom_visual_refresh_timer.setInterval(80)
        self._zoom_visual_refresh_timer.timeout.connect(self._refresh_zoom_dependent_visuals)
        # Selection and symbol movement can generate many events in one gesture.
        # Metadata collision layout is global, so coalesce it instead of blocking
        # every click/drag frame with a complete plan-wide recalculation.
        self._symbol_metadata_refresh_timer=QTimer(self); self._symbol_metadata_refresh_timer.setSingleShot(True); self._symbol_metadata_refresh_timer.setInterval(45)
        self._symbol_metadata_refresh_timer.timeout.connect(self._refresh_switch_association_badges)
        # Keep the symbol itself under the pointer while dependent graphics are
        # coalesced to at most one update per display frame.
        self._symbol_drag_visual_timer=QTimer(self); self._symbol_drag_visual_timer.setSingleShot(True); self._symbol_drag_visual_timer.setInterval(16)
        self._symbol_drag_visual_timer.timeout.connect(self._flush_symbol_drag_visuals)
        # Selection must never block the mouse-down event that starts a symbol
        # drag.  Coalesce scene signals and build the inspector after release.
        self._selection_refresh_timer=QTimer(self); self._selection_refresh_timer.setSingleShot(True); self._selection_refresh_timer.setInterval(28)
        self._selection_refresh_timer.timeout.connect(self._flush_queued_selection_changed)
        self._selection_refresh_pending=False
        self._selection_last_signature=None
        self._symbol_pointer_down=False
        self._symbol_drag_active=False
        self.view.set_lighting_alignment_enabled(self.lighting_alignment_snap)
        self.setCentralWidget(self.view)
        self.cable_assistant_popup = CableAssistantPopup(self.view.viewport())
        self.cable_assistant_popup.finishRequested.connect(self._cable_assistant_finish)
        self.cable_assistant_popup.undoRequested.connect(self._cable_assistant_undo)
        self.cable_assistant_popup.passByRequested.connect(self._cable_assistant_pass_by)
        self.cable_assistant_popup.restartRequested.connect(self._cable_assistant_restart)
        self.scene.selectionChanged.connect(self._queue_selection_changed)
        self.view.zoomChanged.connect(self._zoom_changed)
        self.view.placementRequested.connect(self._placement_requested)
        self.view.cableFinished.connect(self._cable_finished)
        self.view.cablePreviewChanged.connect(self._cable_preview_changed)
        self.view.cablePointCommitted.connect(self._cable_point_committed)
        self.view.calibrationFinished.connect(self._length_calibration_finished)
        self.view.mouseSceneMoved.connect(self._association_mouse_moved)
        self.view.associationFinishRequested.connect(self._finish_active_association)
        self.view.textPlacementRequested.connect(self._text_placement_requested)
        self.view.patternFinished.connect(self._spot_pattern_finished)
        self.view.roomFinished.connect(self._room_sketch_finished)
        self.view.roomPreviewChanged.connect(lambda _pts:self._refresh_workflow_bar())
        self.view.toolCancelled.connect(self._view_tool_cancelled)

        self._create_actions()
        self._create_central_pages()
        self._create_menu_bar()
        self._create_toolbar()
        self._create_symbol_palette_dock()
        self._create_layers_dock()
        # Symboler og Lag deler det samme venstre arbejdsområde som faner.
        # Det frigør markant mere højde til symbolpaletten og holder sidepanelet roligt.
        self.tabifyDockWidget(self.palette_dock, self.layers_dock)
        self.palette_dock.raise_()
        # 0.53.0: ét samlet højre sidepanel. Symbol- og kabeldata skifter side
        # efter kontekst i stedet for at konkurrere som separate docks.
        self._create_inspector_dock()
        self._create_properties_dock()
        self._create_cable_dock()
        self._show_inspector_page("properties", reveal=False)
        # Gendan brugerens panelplacering/størrelser. Første opstart får et roligt
        # standardlayout med tegningen som den klart største flade.
        if not self._restore_main_window_layout():
            self.resizeDocks([self.palette_dock, self.inspector_dock], [UI.left_dock_default, UI.inspector_default], Qt.Orientation.Horizontal)
        self.setStatusBar(QStatusBar())
        self.status_zoom = QLabel("100%")
        self.status_zoom.setObjectName("statusPill")
        self.status_objects = QLabel("0 symboler")
        self.status_objects.setObjectName("statusPill")
        self.statusBar().addPermanentWidget(self.status_objects)
        self._setup_project_collaboration_ui()
        self.statusBar().addPermanentWidget(self.status_zoom)
        self.toast_overlay = ToastOverlay(self)
        self.busy_overlay = BusyOverlay(self)
        self._create_visual_workspace()
        self._set_status("Klar · Åbn et projekt eller en DWG/DXF for at begynde.")
        self._update_title()
        self._apply_stylesheet()
        self._apply_canvas_appearance(refresh_items=False)

    def _resolved_dark_theme(self) -> bool:
        return _resolved_dark_mode(self.appearance_mode, QApplication.instance())

    def _apply_canvas_appearance(self, refresh_items: bool = True) -> None:
        """Apply screen-only drawing colors without touching project/export data."""
        app=QApplication.instance()
        dark_canvas=bool(self._resolved_dark_theme() and self.dark_canvas)
        if app is not None:
            app.setProperty("elplanCanvasDark",dark_canvas)
        bg=QColor("#1b2026") if dark_canvas else QColor("#ffffff")
        self.scene.setBackgroundBrush(bg); self.view.setBackgroundBrush(bg)
        try:self.view.refresh_theme()
        except Exception:pass
        if not refresh_items:
            return
        # CAD and symbols derive their display contrast dynamically. Cables and
        # free text cache their pens/brushes and therefore get an explicit refresh.
        for item in self.scene.items():
            try:
                if isinstance(item,CableItem):
                    item.refresh(update_handles=False)
                elif isinstance(item,(FreeTextItem,AnnotationItem)):
                    item.refresh()
                else:
                    item.update()
            except Exception:
                try:item.update()
                except Exception:pass
        try:self._populate_symbol_palette()
        except Exception:pass
        try:self._rebuild_cable_bundle_badges()
        except Exception:pass
        try:self._refresh_switch_association_badges()
        except Exception:pass
        try:
            if getattr(self,"association_pick_source",False):
                self._refresh_association_source_picker()
            elif getattr(self,"association_source_uid",""):
                self._refresh_association_visuals()
        except Exception:
            pass
        self.view.viewport().update()

    def _update_appearance_actions(self) -> None:
        mapping={
            "light":getattr(self,"act_appearance_light",None),
            "dark":getattr(self,"act_appearance_dark",None),
            "system":getattr(self,"act_appearance_system",None),
        }
        for mode,action in mapping.items():
            if action is not None:
                blocker=QSignalBlocker(action); action.setChecked(mode==self.appearance_mode); del blocker
        action=getattr(self,"act_dark_canvas",None)
        if action is not None:
            blocker=QSignalBlocker(action); action.setChecked(bool(self.dark_canvas)); del blocker
            action.setEnabled(self._resolved_dark_theme())
            action.setToolTip("Brug mørk tegneflade med automatisk skærmkontrast. PDF/print ændres ikke." if self._resolved_dark_theme() else "Aktiveres når mørkt udseende er valgt.")

    def _apply_appearance(self, *, persist: bool = True) -> None:
        app=QApplication.instance()
        if app is not None:
            _apply_application_palette(app,self.appearance_mode)
        if persist:
            data=core.load_app_settings(); data["appearance_mode"]=self.appearance_mode; data["dark_canvas"]=bool(self.dark_canvas)
            core.save_app_settings(data); self.app_settings=data
        self._apply_stylesheet()
        self._refresh_action_icons()
        self._apply_canvas_appearance(refresh_items=True)
        self._update_appearance_actions()
        try:self._hover_info_popup.hide()
        except Exception:pass
        self._set_status(f"Udseende: {core.APPEARANCE_MODES.get(self.appearance_mode,self.appearance_mode)}"+(" · mørk tegneflade" if self._resolved_dark_theme() and self.dark_canvas else ""))

    def _set_appearance_mode(self, mode: str) -> None:
        mode=core.normalize_appearance_mode(mode)
        if mode==self.appearance_mode:
            self._update_appearance_actions(); return
        self.appearance_mode=mode
        self._apply_appearance(persist=True)

    def _toggle_dark_canvas(self, checked: bool) -> None:
        self.dark_canvas=bool(checked)
        self._apply_appearance(persist=True)

    def _toggle_light_dark(self) -> None:
        self._set_appearance_mode("light" if self._resolved_dark_theme() else "dark")

    def _system_appearance_changed(self, *_args) -> None:
        if self.appearance_mode=="system":
            self._apply_appearance(persist=False)

    def _refresh_action_icons(self) -> None:
        """Regenerate native toolbar icons after a live palette switch."""
        try:
            style=self.style()
            mapping=(
                (getattr(self,"act_open_project",None),QStyle.StandardPixmap.SP_DialogOpenButton),
                (getattr(self,"act_open_cad",None),QStyle.StandardPixmap.SP_DirOpenIcon),
                (getattr(self,"act_update_cad",None),QStyle.StandardPixmap.SP_BrowserReload),
                (getattr(self,"act_save",None),QStyle.StandardPixmap.SP_DialogSaveButton),
                (getattr(self,"act_undo",None),QStyle.StandardPixmap.SP_ArrowBack),
                (getattr(self,"act_redo",None),QStyle.StandardPixmap.SP_ArrowForward),
                (getattr(self,"act_delete",None),QStyle.StandardPixmap.SP_TrashIcon),
            )
            for action,pixmap in mapping:
                if action is not None:
                    action.setIcon(style.standardIcon(pixmap))
        except Exception:
            pass

    def _apply_stylesheet(self) -> None:
        # Global tokenized theme: every ordinary Qt control/dialog shares the
        # same palette. Technical print/PDF pages remain deliberately paper-white.
        target=QApplication.instance() or self
        target.setStyleSheet(_application_stylesheet(self._resolved_dark_theme(),bool(self.dark_canvas)))

    def _cable_categories(self) -> list[dict]:
        records=core.normalize_cable_category_records(self.project.raw.get("cable_categories",[]))
        self.project.raw["cable_categories"]=records
        return records

    def _cable_category_record(self,category_id=None) -> dict:
        cid=category_id
        if cid is None and hasattr(self,"cable_category_combo"):
            cid=self.cable_category_combo.currentData()
        return core.cable_category_record(self._cable_categories(),cid or core.DEFAULT_CABLE_CATEGORY)

    def _cable_category_is_visible(self,category_id: str) -> bool:
        cid=core.normalize_cable_category_id(category_id)
        return all(self.project.layer_visibility.get(core.cable_category_layer_name(base,cid),self.project.layer_visibility.get(base,True)) for base in (core.CABLE_LAYER,core.WIRE_LAYER,core.PATCH_CABLE_LAYER))

    def _cable_layer_visible(self,cable: core.CablePlacement) -> bool:
        return core.cable_visible_in_layers(cable,self.project.layer_visibility)

    def _sync_cable_category_styles(self) -> None:
        categories=self._cable_categories()
        valid={r["id"] for r in categories}
        for cable in self.project.cables:
            cid=core.normalize_cable_category_id(getattr(cable,"cable_category",core.DEFAULT_CABLE_CATEGORY))
            if cid not in valid: cid=core.DEFAULT_CABLE_CATEGORY
            rec=core.cable_category_record(categories,cid)
            cable.cable_category=rec["id"]
            cable.color=rec["color"]
            cable.line_style=rec["line_style"]
            item=self.cable_items.get(id(cable)) if hasattr(self,"cable_items") else None
            if item is not None:item.refresh()

    def _reindex_cable_category_layers(self) -> None:
        if not hasattr(self,"generated_layer_items"):return
        # Fjern kabel-items fra deres gamle genererede lag og registrér dem igen
        # under den kombinerede type+kategori-layer.
        cable_item_set=set(self.cable_items.values()) if hasattr(self,"cable_items") else set()
        for layer in list(self.generated_layer_items):
            self.generated_layer_items[layer]=[x for x in self.generated_layer_items[layer] if x not in cable_item_set]
            if not self.generated_layer_items[layer] and layer not in self.layer_items:
                self.generated_layer_items.pop(layer,None)
        for cable in self.project.cables:
            item=self.cable_items.get(id(cable))
            if item is not None:self.generated_layer_items[core.cable_effective_layer(cable)].append(item)
        self._rebuild_layer_list()
        self._apply_quick_visibility()

    def _populate_cable_category_combo(self,selected=None) -> None:
        if not hasattr(self,"cable_category_combo"):return
        wanted=core.normalize_cable_category_id(selected if selected is not None else self.cable_category_combo.currentData() or self.project.raw.get("cable_category",core.DEFAULT_CABLE_CATEGORY))
        blocker=QSignalBlocker(self.cable_category_combo)
        self.cable_category_combo.clear()
        for rec in self._cable_categories():
            self.cable_category_combo.addItem(rec["name"],rec["id"])
            idx=self.cable_category_combo.count()-1
            self.cable_category_combo.setItemData(idx,str(rec.get("description","") or ""),Qt.ItemDataRole.ToolTipRole)
        idx=self.cable_category_combo.findData(wanted)
        if idx<0:idx=self.cable_category_combo.findData(core.DEFAULT_CABLE_CATEGORY)
        self.cable_category_combo.setCurrentIndex(max(0,idx)); del blocker
        self._apply_category_style_to_panel()

    def _apply_category_style_to_panel(self) -> None:
        if not hasattr(self,"cable_category_combo"):return
        rec=self._cable_category_record(self.cable_category_combo.currentData())
        _set_color_button(self.cable_color,rec["color"])
        idx=self.cable_line_style.findData(rec["line_style"])
        blocker=QSignalBlocker(self.cable_line_style); self.cable_line_style.setCurrentIndex(max(0,idx)); del blocker
        definition=str(rec.get("description","") or "").strip()
        if hasattr(self,"cable_category_definition"):
            self.cable_category_definition.setText(definition or "—")
            self.cable_category_definition.setToolTip(definition)
        self.cable_category_combo.setToolTip(definition)
        self.cable_color.setToolTip(f"Styres af kabelkategorien '{rec['name']}'. Redigér via Kabelkategorier…")
        self.cable_line_style.setToolTip(f"Styres af kabelkategorien '{rec['name']}'. Redigér via Kabelkategorier…")

    def _cable_category_changed(self,*_args) -> None:
        if getattr(self,"_loading_cable_panel",False):return
        self._apply_category_style_to_panel()
        if self.selected_cable is None:
            self.project.raw["cable_category"]=str(self.cable_category_combo.currentData() or core.DEFAULT_CABLE_CATEGORY)
        self._cable_panel_changed()

    def open_cable_categories_dialog(self) -> None:
        dlg=CableCategoryDialog(self,self._cable_categories(),self.project.layer_visibility,self.project.cables)
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        records,visibility=dlg.result_data()
        old_ids={r["id"] for r in self._cable_categories()}; new_ids={r["id"] for r in records}
        removed=old_ids-new_ids
        self.project.raw["cable_categories"]=records
        for cable in self.project.cables:
            if core.normalize_cable_category_id(getattr(cable,"cable_category",core.DEFAULT_CABLE_CATEGORY)) in removed:
                cable.cable_category=core.DEFAULT_CABLE_CATEGORY
        for rec in records:
            checked=bool(visibility.get(rec["id"],True))
            for base in (core.CABLE_LAYER,core.WIRE_LAYER,core.PATCH_CABLE_LAYER):
                self.project.layer_visibility[core.cable_category_layer_name(base,rec["id"])]=checked
        self._sync_cable_category_styles()
        self._reindex_cable_category_layers()
        self._populate_cable_category_combo(getattr(self.selected_cable,"cable_category",None) if self.selected_cable is not None else self.project.raw.get("cable_category",core.DEFAULT_CABLE_CATEGORY))
        self._refresh_cable_categories_menu()
        self.project.dirty=True; self._update_title()
        self._set_status("Kabelkategorier opdateret · farver, konturer og lagvisning er anvendt.")

    def _set_cable_category_visible(self,category_id: str,visible: bool) -> None:
        cid=core.normalize_cable_category_id(category_id)
        for base in (core.CABLE_LAYER,core.WIRE_LAYER,core.PATCH_CABLE_LAYER):
            self.project.layer_visibility[core.cable_category_layer_name(base,cid)]=bool(visible)
        self._apply_quick_visibility(); self._rebuild_layer_list(); self.project.dirty=True; self._update_title()
        rec=self._cable_category_record(cid)
        self._set_status(f"Kabelkategori: {rec['name']} {'vist' if visible else 'skjult'}.")
        self._update_cable_category_menu_summary()
        if hasattr(self,"_refresh_cable_category_strip"):
            self._refresh_cable_category_strip()

    def _create_actions(self) -> None:
        self.act_open_project = QAction("Åbn projekt", self)
        self.act_open_project.setShortcut(QKeySequence.StandardKey.Open)
        self.act_open_project.triggered.connect(self.open_project)
        self.act_open_cad = QAction("Åbn DWG/DXF", self)
        self.act_open_cad.triggered.connect(self.open_cad)
        self.act_update_cad = QAction("Opdatér plantegning…", self)
        self.act_update_cad.setToolTip("Genindlæs den nuværende DWG/DXF eller vælg en revideret fil uden at miste Elplan-data.")
        self.act_update_cad.triggered.connect(self.update_cad)
        self.act_project_storage = QAction("Projektlager…", self)
        self.act_project_storage.setToolTip("Vælg om projekter gemmes som hidtil, i et lokalt projektbibliotek eller i en synkroniseret mappe som OneDrive.")
        self.act_project_storage.triggered.connect(self.configure_project_storage)
        self.act_core_data_storage = QAction("Artikeldata…", self)
        self.act_core_data_storage.setToolTip("Flyt det globale artikelkatalog, prisbogen og globale styklister til en separat OneDrive-mappe.")
        self.act_core_data_storage.triggered.connect(self.configure_core_data_storage)
        self.act_settings = QAction("Indstillinger…", self)
        self.act_settings.setToolTip("Globale indstillinger samlet efter visning, priser/BOM og lager.")
        self.act_settings.triggered.connect(self.open_application_settings)
        self.act_migrate_project = QAction("Migrér aktuelt projekt til projektlager…", self)
        self.act_migrate_project.setToolTip("Kopiér det aktive projekt, plantegningen og eksisterende backups til den nye projektmappe-struktur.")
        self.act_migrate_project.triggered.connect(self.migrate_current_project_to_storage)
        self.act_global_search = QAction("Søg i tegning…", self)
        self.act_global_search.setShortcut(QKeySequence.StandardKey.Find)
        self.act_global_search.setToolTip("Søg efter gruppe, mærkning, kabel-ID, kabeltype eller tekst og gå direkte til objektet.")
        self.act_global_search.triggered.connect(self.open_global_search)
        self.act_command_palette = QAction("Søg / kommando…", self)
        self.act_command_palette.setShortcut(QKeySequence("Ctrl+Shift+P"))
        self.act_command_palette.setToolTip("Find objekter eller start en handling direkte fra tastaturet.")
        self.act_command_palette.triggered.connect(self.open_command_palette)
        self.act_welcome = QAction("Startside", self)
        self.act_welcome.setShortcut(QKeySequence("Ctrl+Shift+H"))
        self.act_welcome.triggered.connect(self._show_welcome_page)
        self.act_save = QAction("Gem", self)
        self.act_save.setShortcut(QKeySequence.StandardKey.Save)
        self.act_save.triggered.connect(self.save_project)
        self.act_save_as = QAction("Gem som…", self)
        self.act_save_as.triggered.connect(lambda: self.save_project(save_as=True))
        # Enter used to work only while the drawing view had keyboard focus.
        # Keep this window-scoped action disabled outside an association
        # session, so tables and buttons can no longer swallow the save key.
        self.act_finish_association=QAction("Gem tilknytning",self)
        self.act_finish_association.setShortcuts([
            QKeySequence(Qt.Key.Key_Return),QKeySequence(Qt.Key.Key_Enter),
            QKeySequence("Ctrl+Return"),QKeySequence("Ctrl+Enter"),
        ])
        self.act_finish_association.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
        self.act_finish_association.setEnabled(False)
        self.act_finish_association.triggered.connect(self._finish_active_association)
        self.addAction(self.act_finish_association)
        self.act_export_core = QAction("Eksportér kernedata…", self)
        self.act_export_core.setToolTip("Eksportér artikelbase, globale styklister, prisbog og portable programindstillinger til én fil.")
        self.act_export_core.triggered.connect(self.export_core_data_package)
        self.act_import_core = QAction("Importér kernedata…", self)
        self.act_import_core.setToolTip("Importér kernedata fra en anden PC. Eksisterende kernedata sikkerhedskopieres først.")
        self.act_import_core.triggered.connect(self.import_core_data_package)
        self.act_export_project_package = QAction("Eksportér projektpakke…", self)
        self.act_export_project_package.setToolTip("Pak kun det aktuelle projekt og dets DWG/DXF til flytning eller backup.")
        self.act_export_project_package.triggered.connect(self.export_project_package)
        self.act_import_project_package = QAction("Importér projektpakke…", self)
        self.act_import_project_package.setToolTip("Pak et projekt og dets DWG/DXF ud til en valgt mappe og åbn projektet.")
        self.act_import_project_package.triggered.connect(self.import_project_package)
        self.act_fit = QAction("Tilpas visning", self)
        self.act_fit.setShortcut(QKeySequence(Qt.Key.Key_Home))
        self.act_fit.triggered.connect(self.view.fit_scene)
        self.act_zoom_in = QAction("Zoom ind", self)
        self.act_zoom_in.setShortcuts([QKeySequence("Ctrl++"), QKeySequence("Ctrl+=")])
        self.act_zoom_in.setShortcutVisibleInContextMenu(True)
        self.act_zoom_in.triggered.connect(self.view.zoom_in)
        self.act_zoom_out = QAction("Zoom ud", self)
        self.act_zoom_out.setShortcut(QKeySequence("Ctrl+-"))
        self.act_zoom_out.setShortcutVisibleInContextMenu(True)
        self.act_zoom_out.triggered.connect(self.view.zoom_out)
        self.act_focus_elplan = QAction("Fremhæv elplan", self)
        self.act_focus_elplan.setCheckable(True)
        self.act_focus_elplan.setChecked(self.cad_background_opacity < 0.95)
        self.act_focus_elplan.setToolTip("Dæmp DWG/DXF-baggrunden, så el-symboler, mærkninger og kabler står tydeligere.")
        self.act_focus_elplan.toggled.connect(self._toggle_elplan_focus)
        self.act_focus_group = QAction("Fokusér valgt gruppe", self, checkable=True)
        self.act_focus_group.setShortcut(QKeySequence("Ctrl+Shift+F"))
        self.act_focus_group.setToolTip("Dæmp øvrige symboler og kabler og behold den valgte gruppe/kreds tydelig.")
        self.act_focus_group.triggered.connect(lambda _checked=False: self.toggle_selected_group_focus())
        self.act_trace_circuit=QAction("Spor valgt gruppe",self)
        self.act_trace_circuit.setShortcut(QKeySequence("Ctrl+Shift+T")); self.act_trace_circuit.setToolTip("Animer forbindelsesvejen fra tavlen gennem den valgte gruppe/kreds.")
        self.act_trace_circuit.triggered.connect(lambda _checked=False:self.trace_selected_circuit())
        self.act_zoom_selection=QAction("Zoom til valg",self)
        self.act_zoom_selection.setShortcut(QKeySequence("Ctrl+Shift+Z")); self.act_zoom_selection.triggered.connect(lambda _checked=False:self.zoom_to_selection())
        self.act_navigator=QAction("Navigator / mini-kort",self,checkable=True)
        self.act_navigator.setChecked(bool(self.app_settings.get("show_navigator",False)))
        self.act_navigator.toggled.connect(self._navigator_action_changed)
        self.act_annotations = QAction("Mærkning", self)
        self.act_annotations.setCheckable(True)
        self.act_annotations.setShortcut(QKeySequence("Ctrl+M"))
        self.act_annotations.setChecked(self.annotation_display_mode != "Skjult")
        self.act_annotations.setToolTip("Vis/skjul al symbolmærkning og tilhørsforhold på plantegningen.")
        self.act_annotations.toggled.connect(self._toggle_annotations)

        # 0.51.0: samlet udseende-menu. Temaet er maskinlokalt og kan skiftes
        # live uden at påvirke projektets farver eller PDF/print.
        self.appearance_group=QActionGroup(self); self.appearance_group.setExclusive(True)
        self.act_appearance_light=QAction("Lys",self,checkable=True); self.act_appearance_light.setData("light")
        self.act_appearance_dark=QAction("Mørk",self,checkable=True); self.act_appearance_dark.setData("dark")
        self.act_appearance_system=QAction("Følg Windows",self,checkable=True); self.act_appearance_system.setData("system")
        for _mode,_action in (("light",self.act_appearance_light),("dark",self.act_appearance_dark),("system",self.act_appearance_system)):
            self.appearance_group.addAction(_action); _action.setChecked(self.appearance_mode==_mode)
            _action.triggered.connect(lambda checked,mode=_mode: checked and self._set_appearance_mode(mode))
        self.act_dark_canvas=QAction("Mørk tegneflade",self,checkable=True)
        self.act_dark_canvas.setChecked(bool(self.dark_canvas)); self.act_dark_canvas.toggled.connect(self._toggle_dark_canvas)
        self.act_toggle_dark=QAction("Skift lys / mørk",self); self.act_toggle_dark.setShortcut(QKeySequence("Ctrl+Alt+D")); self.act_toggle_dark.triggered.connect(self._toggle_light_dark)
        self.addAction(self.act_toggle_dark)
        self._update_appearance_actions()

        # Hurtig visning: midlertidige kategori-filtre oven på de egentlige lag.
        self.act_quick_cad = QAction("Plan", self, checkable=True)
        self.act_quick_cad.setChecked(self.quick_visibility["cad"]); self.act_quick_cad.setToolTip("Vis/skjul hele DWG/DXF-plantegningen uden at ændre de enkelte lag.")
        self.act_quick_symbols = QAction("Symboler", self, checkable=True)
        self.act_quick_symbols.setChecked(self.quick_visibility["symbols"]); self.act_quick_symbols.setToolTip("Vis/skjul alle el-symboler midlertidigt.")
        self.act_quick_cables = QAction("Kabler", self, checkable=True)
        self.act_quick_cables.setChecked(self.quick_visibility["cables"]); self.act_quick_cables.setToolTip("Vis/skjul almindelige kabel- og ledningslag midlertidigt. Patchkabler styres separat.")
        self.act_quick_patch_cables = QAction("Patchkabler", self, checkable=True)
        self.act_quick_patch_cables.setChecked(self.quick_visibility["patch_cables"]); self.act_quick_patch_cables.setToolTip("Vis/skjul kun EL-PATCHKABLER uden at ændre de øvrige kabellag.")
        self.act_quick_text = QAction("Tekst", self, checkable=True)
        self.act_quick_text.setChecked(self.quick_visibility["text"]); self.act_quick_text.setToolTip("Vis/skjul mærkninger, tilhørsforhold og fritekst midlertidigt.")
        for _key,_action in (("cad",self.act_quick_cad),("symbols",self.act_quick_symbols),("cables",self.act_quick_cables),("patch_cables",self.act_quick_patch_cables),("text",self.act_quick_text)):
            _action.toggled.connect(lambda checked, key=_key: self._quick_visibility_changed(key, checked))
        self.act_quick_all = QAction("Vis alt", self)
        self.act_quick_all.setToolTip("Slå alle hurtige visningskategorier til igen.")
        self.act_quick_all.triggered.connect(self._quick_visibility_show_all)

        self.act_layers = QAction("Lag", self, checkable=True)
        self.act_layers.setChecked(True)
        self.act_properties = QAction("Egenskaber", self, checkable=True)
        self.act_properties.setChecked(True)
        self.act_properties.setToolTip("Vis/skjul det fælles Egenskaber-panel for symboler og kabler.")
        self.act_reset_layout = QAction("Nulstil panel-layout", self)
        self.act_reset_layout.setToolTip("Gendan standardplacering og størrelse for Symboler, Lag og Egenskaber.")
        self.act_reset_layout.triggered.connect(self.reset_main_window_layout)
        self.act_oda = QAction("ODA File Converter…", self)
        self.act_oda.triggered.connect(self.select_oda)
        self.act_palette = QAction("Symboler", self, checkable=True)
        self.act_palette.setChecked(True)
        self.act_undo = self.undo_stack.createUndoAction(self, "Fortryd")
        self.act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.act_redo = self.undo_stack.createRedoAction(self, "Gentag")
        self.act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self.act_delete = QAction("Slet", self)
        self.act_delete.setShortcut(QKeySequence(Qt.Key.Key_Delete))
        self.act_delete.triggered.connect(self.delete_selected_symbols)

        self.act_rotate = QAction("Rotér +90°", self)
        self.act_rotate.setShortcut(QKeySequence("Ctrl+R"))
        self.act_rotate.triggered.connect(self.rotate_selected_90)

        self.act_cable = QAction("Kabelværktøj", self)
        self.act_cable.setShortcut(QKeySequence("Ctrl+K"))
        self.act_cable.setCheckable(True)
        self.act_cable.setToolTip("Åbn kabelværktøjet. Knappen forbliver markeret, mens kabelværktøjet er aktivt.")
        self.act_cable.toggled.connect(self._cable_action_toggled)
        self.act_cable_routes = QAction("Kabeltræk / ruteforløb…", self)
        self.act_cable_routes.setToolTip("Vis gruppevise kabeltræk som træ og som Tavle → X → X-liste. Klik på en rute for at fremhæve kablerne på plantegningen.")
        self.act_cable_routes.triggered.connect(self.show_cable_routes_overview)
        self._create_cable_marking_actions()
        self.act_length_settings = QAction("Kabellængder / skala…", self)
        self.act_length_settings.triggered.connect(self.show_cable_length_settings)
        self.act_length_report = QAction("Kabellængderapport…", self)
        self.act_length_report.triggered.connect(self.show_cable_length_report)
        self.act_cable_categories = QAction("Konfigurér kabelkategorier…", self)
        self.act_cable_categories.setToolTip("Opret, omdøb og konfigurér kabelkategorier samt farve, kontur og lagvisning.")
        self.act_cable_categories.triggered.connect(self.open_cable_categories_dialog)
        self.act_pl_box_report = QAction("PL-dåserapport…", self)
        self.act_pl_box_report.setToolTip("Eksportér en A4-montagerapport med fysisk orientering, kabelindføringer, tydelig lederfordeling, Wago og montagekontrol for alle PL-dåser.")
        self.act_pl_box_report.triggered.connect(self.export_pl_box_report)
        self.act_bom = QAction("Artikler / BOM…", self)
        self.act_bom.setShortcut(QKeySequence("Ctrl+B"))
        self.act_bom.setToolTip("Tilknyt artikler til stikkontakter/afbrydere og opbyg en samlet BOM.")
        self.act_bom.triggered.connect(self.open_bom_manager)
        self.act_project_control=QAction("Projektkontrol…",self)
        self.act_project_control.setShortcut(QKeySequence("Ctrl+Shift+K"))
        self.act_project_control.setToolTip("Find manglende artikler, kabeldata, PL-lederfordeling, mærkning og objekter uden rum – og gå direkte til problemet.")
        self.act_project_control.triggered.connect(self.open_project_control)

        self.act_associate = QAction("Tilknyt lys", self)
        self.act_associate.triggered.connect(self.start_association_mode)
        self.act_clear_assoc = QAction("Ryd tilhør.", self)
        self.act_clear_assoc.triggered.connect(self.clear_selected_associations)

        self.act_configurator = QAction("Symbolkonfigurator…", self)
        self.act_configurator.triggered.connect(self.open_symbol_configurator)

        self.act_copy = QAction("Kopiér", self)
        self.act_copy.setShortcut(QKeySequence.StandardKey.Copy)
        self.act_copy.triggered.connect(self.copy_selected)
        self.act_paste = QAction("Indsæt", self)
        self.act_paste.setShortcut(QKeySequence.StandardKey.Paste)
        self.act_paste.triggered.connect(self.paste_clipboard)
        self.act_select_all = QAction("Vælg alle symboler", self)
        self.act_select_all.setShortcut(QKeySequence.StandardKey.SelectAll)
        self.act_select_all.triggered.connect(self.select_all_symbols)

        self.act_text = QAction("Tekst…", self)
        self.act_text.triggered.connect(self.start_text_dialog)
        self._create_room_actions()
        self.act_spot_line = QAction("Spot-række…", self)
        self.act_spot_line.triggered.connect(self.start_spot_line_dialog)
        self.act_spot_rect = QAction("Spot-rektangel…", self)
        self.act_spot_rect.triggered.connect(self.start_spot_rect_dialog)

        self.act_lighting_snap = QAction("Lys-snap", self)
        self.act_lighting_snap.setCheckable(True)
        self.act_lighting_snap.setChecked(self.lighting_alignment_snap)
        self.act_lighting_snap.setToolTip("Dynamiske vandrette/lodrette hjælpelinjer. Spots prioriterer snap til andre spots ved placering og flytning")
        self.act_lighting_snap.toggled.connect(self._lighting_alignment_snap_changed)

        self.act_preview = QAction("Forhåndsvis…", self)
        self.act_preview.setShortcut(QKeySequence("Ctrl+P"))
        self.act_preview.triggered.connect(self.open_print_preview)
        self.act_pdf = QAction("PDF…", self)
        self.act_pdf.triggered.connect(self.export_pdf)
        self.act_print = QAction("Udskriv…", self)
        self.act_print.triggered.connect(self.print_plan)
        self.act_cancel_tool = QAction("Annuller værktøj", self)
        self.act_cancel_tool.setShortcut(QKeySequence("Esc"))
        self.act_cancel_tool.triggered.connect(self.cancel_active_tool)
        self.addAction(self.act_cancel_tool)
        self.addAction(self.act_copy); self.addAction(self.act_paste); self.addAction(self.act_select_all)

        # Korte tekster i værktøjslinjen; de fulde handlinger findes stadig i menuerne.
        self.act_open_project.setText("Åbn")
        self.act_open_project.setToolTip("Åbn Elplan-projekt (Ctrl+O)")
        self.act_open_cad.setText("DWG/DXF")
        self.act_save_as.setText("Gem som…")
        self.act_rotate.setText("Rotér 90°")
        self.act_cable.setText("Kabel")
        self.act_spot_line.setText("Spot-række")
        self.act_spot_rect.setText("Spot-felt")
        self.act_associate.setText("Tilknyt")
        self.act_preview.setText("Preview")
        self.act_fit.setText("Tilpas")
        self.act_focus_elplan.setText("Fremhæv")

        self._refresh_action_icons()

    def _create_menu_bar(self) -> None:
        """Klassiske menuer holder sjældne funktioner væk fra den primære værktøjslinje."""
        bar = self.menuBar()
        bar.setNativeMenuBar(False)

        file_menu = bar.addMenu("Fil")
        file_menu.addAction(self.act_open_project)
        self.recent_projects_menu=file_menu.addMenu("Åbn seneste…")
        self.recent_projects_menu.setToolTip("Åbn et af de senest anvendte Elplan-projekter")
        self.recent_projects_menu.aboutToShow.connect(self._refresh_recent_projects_menu)
        self._refresh_recent_projects_menu()
        file_menu.addAction(self.act_open_cad)
        file_menu.addAction(self.act_update_cad)
        file_menu.addSeparator()
        storage_menu=file_menu.addMenu("Lager og synkronisering")
        storage_menu.addAction(self.act_project_storage)
        storage_menu.addAction(self.act_core_data_storage)
        storage_menu.addSeparator()
        storage_menu.addAction(self.act_migrate_project)
        file_menu.addSeparator()
        file_menu.addAction(self.act_save)
        file_menu.addAction(self.act_save_as)
        file_menu.addSeparator()
        transfer_menu=file_menu.addMenu("Overfør / backup")
        transfer_menu.addAction(self.act_export_core)
        transfer_menu.addAction(self.act_import_core)
        transfer_menu.addSeparator()
        transfer_menu.addAction(self.act_export_project_package)
        transfer_menu.addAction(self.act_import_project_package)
        file_menu.addSeparator()
        file_menu.addAction(self.act_preview)
        file_menu.addAction(self.act_pdf)
        file_menu.addAction(self.act_print)
        file_menu.addSeparator()
        file_menu.addAction(self.act_oda)
        file_menu.addSeparator()
        exit_action = QAction("Afslut", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = bar.addMenu("Rediger")
        edit_menu.addAction(self.act_undo)
        edit_menu.addAction(self.act_redo)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_copy)
        edit_menu.addAction(self.act_paste)
        edit_menu.addAction(self.act_select_all)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_global_search)
        edit_menu.addAction(self.act_command_palette)
        edit_menu.addSeparator()
        edit_menu.addAction(self.act_delete)
        edit_menu.addAction(self.act_rotate)

        tools_menu = bar.addMenu("Værktøjer")
        tools_menu.addAction(self.act_text)
        self._add_room_tools_menu(tools_menu)
        tools_menu.addAction(self.act_cable)
        tools_menu.addAction(self.act_cable_marking)
        tools_menu.addAction(self.act_cable_routes)
        tools_menu.addAction(self.act_length_settings)
        tools_menu.addAction(self.act_length_report)
        tools_menu.addAction(self.act_cable_categories)
        tools_menu.addAction(self.act_pl_box_report)
        tools_menu.addAction(self.act_project_control)
        tools_menu.addAction(self.act_bom)
        tools_menu.addSeparator()
        tools_menu.addAction(self.act_spot_line)
        tools_menu.addAction(self.act_spot_rect)
        tools_menu.addAction(self.act_lighting_snap)
        tools_menu.addSeparator()
        tools_menu.addAction(self.act_associate)
        tools_menu.addAction(self.act_clear_assoc)
        tools_menu.addSeparator()
        tools_menu.addAction(self.act_configurator)
        tools_menu.addSeparator()
        tools_menu.addAction(self.act_settings)

        view_menu = bar.addMenu("Vis")
        view_menu.addAction(self.act_welcome)
        view_menu.addAction(self.act_fit)
        view_menu.addAction(self.act_zoom_in)
        view_menu.addAction(self.act_zoom_out)
        view_menu.addAction(self.act_focus_elplan)
        view_menu.addAction(self.act_focus_group)
        view_menu.addAction(self.act_trace_circuit)
        view_menu.addAction(self.act_zoom_selection)
        view_menu.addAction(self.act_navigator)
        view_menu.addAction(self.act_annotations)
        appearance_menu=view_menu.addMenu("Udseende")
        appearance_menu.setToolTip("Skift mellem lys/mørk brugerflade. Teknisk print/PDF bevarer papirfarverne.")
        appearance_menu.addAction(self.act_appearance_light); appearance_menu.addAction(self.act_appearance_dark); appearance_menu.addAction(self.act_appearance_system)
        appearance_menu.addSeparator(); appearance_menu.addAction(self.act_dark_canvas); appearance_menu.addAction(self.act_toggle_dark)
        quick_menu=view_menu.addMenu("Hurtig visning")
        quick_menu.addAction(self.act_quick_cad); quick_menu.addAction(self.act_quick_symbols); quick_menu.addAction(self.act_quick_cables); quick_menu.addAction(self.act_quick_patch_cables); quick_menu.addAction(self.act_quick_text)
        quick_menu.addSeparator(); quick_menu.addAction(self.act_quick_all)
        room_view_menu=view_menu.addMenu("Rum")
        room_view_menu.setToolTip("Vis rumnavn, rummærkning og rumafgrænsning uafhængigt.")
        room_view_menu.addAction(self.act_room_labels); room_view_menu.addAction(self.act_room_codes); room_view_menu.addAction(self.act_room_boundaries); room_view_menu.addSeparator(); room_view_menu.addAction(self.act_room_focus_clear)
        self.cable_categories_menu=view_menu.addMenu("Kabelkategorier")
        self.cable_categories_menu.setToolTip("Vis/skjul kabelkategorier direkte på lag-niveau.")
        self.cable_categories_menu.aboutToShow.connect(self._refresh_cable_categories_menu)
        self._refresh_cable_categories_menu()
        view_menu.addSeparator()
        view_menu.addAction(self.act_palette)
        view_menu.addAction(self.act_layers)
        view_menu.addAction(self.act_properties)
        view_menu.addAction(self.act_reset_layout)

    def _create_symbol_palette_dock(self) -> None:
        self.palette_dock = prepare_dock(QDockWidget("Symboler", self), minimum_width=UI.left_dock_min, object_name="symbolPaletteDock")
        widget = QWidget()
        layout = tune_panel_layout(QVBoxLayout(widget), compact=True)

        # Kategori + konfigurator ligger på én linje i stedet for to store kontroller.
        top = QHBoxLayout()
        self.palette_category = QComboBox()
        self._refresh_palette_categories()
        self.palette_category.currentTextChanged.connect(self._populate_symbol_palette)
        top.addWidget(self.palette_category, 1)
        self.configurator_button = _set_role(QPushButton("Konfigurér…"), "quietButton")
        self.configurator_button.setObjectName("quietButton")
        self.configurator_button.setToolTip("Opret eller redigér kombinerede symboler")
        self.configurator_button.clicked.connect(self.open_symbol_configurator)
        top.addWidget(self.configurator_button)
        layout.addLayout(top)

        self.palette_search = QLineEdit()
        self.palette_search.setPlaceholderText("Søg symbol…")
        self.palette_search.setClearButtonEnabled(True)
        self.palette_search.textChanged.connect(self._populate_symbol_palette)
        layout.addWidget(self.palette_search)

        placement_group = QGroupBox("Placering")
        pg = QGridLayout(placement_group)
        pg.setHorizontalSpacing(6)
        pg.setVerticalSpacing(6)
        pg.addWidget(QLabel("Standard"), 0, 0)
        self.palette_size = QDoubleSpinBox()
        self.palette_size.setRange(10.0, 100000.0)
        self.palette_size.setDecimals(0)
        self.palette_size.setValue(200.0)
        self.palette_size.setSingleStep(25.0)
        self.palette_size.setSuffix(" mm")
        pg.addWidget(self.palette_size, 0, 1, 1, 3)

        pg.addWidget(QLabel("Spot"), 1, 0)
        minus = _set_role(QPushButton("−"), "iconButton")
        minus.setMaximumWidth(32)
        minus.setToolTip("Mindre spot")
        minus.clicked.connect(lambda: self.adjust_spot_size_quick(.90))
        self.spot_size_quick = QDoubleSpinBox()
        self.spot_size_quick.setRange(20, 5000)
        self.spot_size_quick.setDecimals(0)
        self.spot_size_quick.setValue(150)
        self.spot_size_quick.setSuffix(" mm")
        plus = _set_role(QPushButton("+"), "iconButton")
        plus.setMaximumWidth(32)
        plus.setToolTip("Større spot")
        plus.clicked.connect(lambda: self.adjust_spot_size_quick(1.10))
        self.spot_size_quick.editingFinished.connect(lambda: self.adjust_spot_size_quick(None))
        pg.addWidget(minus, 1, 1)
        pg.addWidget(self.spot_size_quick, 1, 2)
        pg.addWidget(plus, 1, 3)
        pg.setColumnStretch(2, 1)
        layout.addWidget(placement_group)

        list_header = QHBoxLayout()
        palette_heading=QLabel("Symboler"); palette_heading.setObjectName("sectionTitle"); list_header.addWidget(palette_heading)
        list_header.addStretch(1)
        self.palette_count = QLabel("")
        self.palette_count.setObjectName("sectionHint")
        list_header.addWidget(self.palette_count)
        layout.addLayout(list_header)

        self.palette_list = QListWidget()
        self.palette_list.setViewMode(QListView.ViewMode.IconMode)
        self.palette_list.setIconSize(QSize(56, 56))
        self.palette_list.setGridSize(QSize(108, 90))
        self.palette_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.palette_list.setMovement(QListView.Movement.Static)
        self.palette_list.setWordWrap(True)
        self.palette_list.setSpacing(2)
        self.palette_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.palette_list.itemClicked.connect(self._palette_symbol_clicked)
        layout.addWidget(self.palette_list, 1)

        hint = QLabel("Klik et symbol for at placere · Esc afslutter")
        hint.setObjectName("sectionHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.palette_dock.setWidget(widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.palette_dock)
        self.act_palette.toggled.connect(self.palette_dock.setVisible)
        self.palette_dock.visibilityChanged.connect(self.act_palette.setChecked)
        self._populate_symbol_palette()

    def _refresh_palette_categories(self) -> None:
        if not hasattr(self, "palette_category"):
            return
        current = self.palette_category.currentText()
        blocker = QSignalBlocker(self.palette_category)
        self.palette_category.clear()
        self.palette_category.addItem("Favoritter")
        self.palette_category.addItems(list(core.SYMBOL_GROUPS.keys()))
        if current:
            self.palette_category.setCurrentText(current)
        else:
            self.palette_category.setCurrentText("Afbrydere")
        if self.palette_category.currentIndex() < 0:
            self.palette_category.setCurrentText("Afbrydere")
        del blocker

    def _populate_symbol_palette(self, *_args) -> None:
        if not hasattr(self, "palette_list"):
            return
        category = self.palette_category.currentText() if hasattr(self, "palette_category") else ""
        if category == "Favoritter":
            mapping = {core.symbol_display_name(code): code for code in self.favorite_symbols if code in core.SYMBOL_NAMES_BY_CODE}
        else:
            mapping = core.SYMBOL_GROUPS.get(category, {})

        query = self.palette_search.text().strip().casefold() if hasattr(self, "palette_search") else ""
        rows = [(name, code) for name, code in mapping.items() if not query or query in name.casefold()]
        self.palette_list.clear()
        for name, code in rows:
            item = QListWidgetItem(symbol_icon(code, 56), name)
            item.setData(Qt.ItemDataRole.UserRole, code)
            item.setToolTip(name)
            self.palette_list.addItem(item)
        if hasattr(self, "palette_count"):
            self.palette_count.setText(f"{len(rows)}")

    def _palette_symbol_clicked(self, item: QListWidgetItem) -> None:
        code = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if not code:
            return
        size = float(self.spot_size_quick.value()) if code=="spot" and hasattr(self,"spot_size_quick") else float(self.palette_size.value())
        self._stop_cable_marking_for_other_tool()
        if self._cable_tool_is_open(): self.close_cable_tool()
        self.view.start_symbol_placement(code, size, core.DEFAULT_SYMBOL_COLOR, 0.25, 0.0)
        self._set_status(f"Placér: {core.symbol_display_name(code)} · klik på tegningen · Esc afslutter")

    def adjust_spot_size_quick(self,factor=None)->None:
        base=float(self.spot_size_quick.value())
        if factor is not None:
            base=max(20.0,round(base*float(factor)/5.0)*5.0)
            self.spot_size_quick.setValue(base)
        spots=[x for x in self.scene.selectedItems() if isinstance(x,ElectricalSymbolItem) and x.placement.symbol=="spot" and not x.placement.locked]
        if spots:
            self.undo_stack.beginMacro("Ændr spotstørrelse")
            try:
                for item in spots:
                    before=self._symbol_state(item.placement); after=dict(before); after["size"]=base
                    self.undo_stack.push(EditSymbolCommand(self,item.placement.uid,before,after,"Spotstørrelse"))
            finally:self.undo_stack.endMacro()
        else:
            self.project.raw["spot_default_size"]=base
        self.project.dirty=True; self._update_title()

    def _save_app_symbol_settings(self) -> None:
        data = core.load_app_settings()
        data["custom_symbols"] = core.custom_symbol_records()
        data["combo_templates"] = list(self.combo_templates)
        data["favorite_symbols"] = list(self.favorite_symbols)
        core.save_app_settings(data)
        self.app_settings = data

    def open_symbol_configurator(self) -> None:
        settings = dict(self.app_settings)
        settings["combo_templates"] = list(self.combo_templates)
        dlg = ComboConfiguratorDialog(self, settings)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        display = core.register_custom_symbol(dlg.result_code, dlg.result_name)
        if not display:
            QMessageBox.warning(self, "Symbolkonfigurator", "Kunne ikke oprette kombisymbolet.")
            return
        self.combo_templates = list(dlg.templates)
        if dlg.pin_favorite and dlg.result_code not in self.favorite_symbols:
            self.favorite_symbols.append(dlg.result_code)
        self._save_app_symbol_settings()
        self._refresh_palette_categories()
        self.palette_category.setCurrentText("Kombi")
        self._populate_symbol_palette()
        # Start placement immediately, matching the legacy configurator workflow.
        size = float(self.palette_size.value())
        self._stop_cable_marking_for_other_tool()
        if self._cable_tool_is_open(): self.close_cable_tool()
        self.view.start_symbol_placement(dlg.result_code, size, core.DEFAULT_SYMBOL_COLOR, 0.25, 0.0)
        self._set_status(f"Placér: {display} · Esc afslutter")

    def _create_layers_dock(self) -> None:
        self.layers_dock = prepare_dock(QDockWidget("Lag", self), minimum_width=UI.left_dock_min, object_name="layersDock")
        widget = QWidget()
        layout = tune_panel_layout(QVBoxLayout(widget))

        bg_group = QGroupBox("Plantegning")
        bg_layout = QVBoxLayout(bg_group)
        bg_layout.setSpacing(6)
        bg_row = QHBoxLayout()
        bg_row.addWidget(QLabel("Baggrund"))
        bg_row.addStretch(1)
        self.cad_opacity_value = QLabel(f"{round(self.cad_background_opacity*100):d}%")
        self.cad_opacity_value.setObjectName("sectionHint")
        self.cad_opacity_value.setMinimumWidth(34)
        bg_row.addWidget(self.cad_opacity_value)
        bg_layout.addLayout(bg_row)
        self.cad_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.cad_opacity_slider.setRange(20, 100)
        self.cad_opacity_slider.setSingleStep(5)
        self.cad_opacity_slider.setPageStep(10)
        self.cad_opacity_slider.setValue(round(self.cad_background_opacity*100))
        self.cad_opacity_slider.setToolTip("Dæmp DWG/DXF uden at påvirke el-symboler og kabler.")
        self.cad_opacity_slider.valueChanged.connect(self._cad_opacity_changed)
        bg_layout.addWidget(self.cad_opacity_slider)
        presets = QHBoxLayout()
        for label, value in (("Mat", 40), ("Normal", 55), ("Fuld", 100)):
            button = _set_role(QPushButton(label), "quietButton")
            button.clicked.connect(lambda _=False, v=value: self.cad_opacity_slider.setValue(v))
            presets.addWidget(button)
        bg_layout.addLayout(presets)
        self.print_cad_dimming_check = QCheckBox("Samme dæmpning i PDF/print")
        self.print_cad_dimming_check.setChecked(self.print_cad_dimming)
        self.print_cad_dimming_check.setToolTip("Brug den valgte baggrundstydelighed i PDF og udskrift.")
        self.print_cad_dimming_check.toggled.connect(self._print_cad_dimming_changed)
        bg_layout.addWidget(self.print_cad_dimming_check)
        layout.addWidget(bg_group)

        label_group = QGroupBox("Mærkning")
        ll = QVBoxLayout(label_group)
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Visning"))
        self.annotation_mode_combo = QComboBox()
        self.annotation_mode_combo.addItems(["Auto", "Minimal", "Tydelig", "Skjult"])
        self.annotation_mode_combo.setCurrentText(self.annotation_display_mode)
        self.annotation_mode_combo.setToolTip(
            "Auto bruger zoomniveauet. Minimal viser kun Gruppe/kreds. "
            "Tydelig viser alle oplysninger. Skjult fjerner al mærkning."
        )
        self.annotation_mode_combo.currentTextChanged.connect(self._annotation_mode_changed)
        mode_row.addWidget(self.annotation_mode_combo, 1)
        ll.addLayout(mode_row)
        self.annotation_room_check = QCheckBox("Hold mærkning på rummets side af væggen")
        self.annotation_room_check.setChecked(self.annotation_room_placement)
        self.annotation_room_check.setToolTip("Forsøger automatisk at holde mærkningen inde i samme rum som symbolet.")
        self.annotation_room_check.toggled.connect(self._annotation_room_placement_changed)
        ll.addWidget(self.annotation_room_check)
        ah = QLabel("Auto viser Gruppe/kreds og a/b/c diskret i oversigten og flere detaljer ved indzoomning.")
        ah.setObjectName("sectionHint")
        ah.setWordWrap(True)
        ll.addWidget(ah)
        layout.addWidget(label_group)

        layers_header = QHBoxLayout()
        layers_heading=QLabel("DWG/DXF-lag"); layers_heading.setObjectName("sectionTitle"); layers_header.addWidget(layers_heading)
        layers_header.addStretch(1)
        self.layer_count_label = QLabel("")
        self.layer_count_label.setObjectName("sectionHint")
        layers_header.addWidget(self.layer_count_label)
        layout.addLayout(layers_header)

        self.layers_list = QListWidget()
        self.layers_list.itemChanged.connect(self._layer_changed)
        layout.addWidget(self.layers_list, 1)
        self.layers_dock.setWidget(widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.layers_dock)
        self.act_layers.toggled.connect(self.layers_dock.setVisible)
        self.layers_dock.visibilityChanged.connect(self.act_layers.setChecked)

    def _create_properties_dock(self) -> None:
        # Symbol/object side of the unified inspector.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        widget = QWidget()
        outer = tune_panel_layout(QVBoxLayout(widget), bottom=12)

        self.prop_title = QLabel("Intet symbol valgt")
        self.prop_title.setObjectName("sectionTitle")
        outer.addWidget(self.prop_title)
        self.prop_hint = QLabel("Vælg et symbol på tegningen for at redigere det.")
        self.prop_hint.setObjectName("sectionHint")
        self.prop_hint.setWordWrap(True)
        outer.addWidget(self.prop_hint)
        # The shared inspector header now carries this information. Keep the
        # labels as internal compatibility targets without duplicating it visually.
        self.prop_title.hide(); self.prop_hint.hide()

        # Egenskaber er opdelt efter den opgave brugeren er i gang med. Det
        # reducerer den lange formular til tre stabile og let genkendelige spor.
        self.properties_workflow_bar=QFrame()
        self.properties_workflow_bar.setObjectName("propertyWorkflowTabs")
        workflow_layout=QVBoxLayout(self.properties_workflow_bar)
        workflow_layout.setContentsMargins(0,0,0,6); workflow_layout.setSpacing(5)
        workflow_buttons=QHBoxLayout(); workflow_buttons.setSpacing(4)
        self.properties_workflow_buttons={}
        for key,label in (("connect","Forbind"),("data","Data"),("purchase","Indkøb")):
            button=QPushButton(label)
            button.setObjectName("propertyWorkflowTab")
            button.setCheckable(True)
            button.clicked.connect(lambda _checked=False,k=key:self._set_properties_workflow(k,user=True))
            workflow_buttons.addWidget(button,1)
            self.properties_workflow_buttons[key]=button
        workflow_layout.addLayout(workflow_buttons)
        self.properties_workflow_hint=QLabel("")
        self.properties_workflow_hint.setObjectName("sectionHint")
        self.properties_workflow_hint.setWordWrap(True)
        workflow_layout.addWidget(self.properties_workflow_hint)
        outer.addWidget(self.properties_workflow_bar)
        self._properties_workflow="connect"
        self._properties_workflow_user_choice=False
        self._properties_current_placement=None
        self._properties_multi_spots=False

        self.basic_group = QGroupBox("Identifikation")
        form = tune_form_layout(QFormLayout(self.basic_group))
        self.prop_label = QLineEdit()
        self.prop_group = QLineEdit()
        form.addRow("Gruppe/kreds", self.prop_group)
        form.addRow("Mærkning", self.prop_label)
        outer.addWidget(self.basic_group)

        appearance_group = QGroupBox("")
        appearance_form = tune_form_layout(QFormLayout(appearance_group))
        self.prop_size = QDoubleSpinBox()
        self.prop_size.setRange(1, 100000)
        self.prop_size.setDecimals(1)
        self.prop_size.setSuffix(" mm")
        self.prop_rotation = QDoubleSpinBox()
        self.prop_rotation.setRange(-3600, 3600)
        self.prop_rotation.setDecimals(1)
        self.prop_rotation.setSuffix("°")
        self.prop_line_width = QDoubleSpinBox()
        self.prop_line_width.setRange(0.05, 5.0)
        self.prop_line_width.setDecimals(2)
        self.prop_line_width.setSingleStep(0.05)
        self.prop_line_width.setSuffix(" mm")
        self.prop_color = QPushButton("#d00000"); _set_color_button(self.prop_color,"#d00000")
        self.prop_color.clicked.connect(self.choose_property_color)
        self.prop_locked = QCheckBox("Lås placering og fysisk redigering")
        self.prop_locked.setToolTip(
            "Forhindrer flytning, rotation, sletning og fysisk omkonfiguration. "
            "Lystilhørsforhold, spotrelationer og artikler kan stadig redigeres."
        )
        appearance_form.addRow("Størrelse", self.prop_size)
        appearance_form.addRow("Rotation", self.prop_rotation)
        appearance_form.addRow("Linjetykkelse", self.prop_line_width)
        appearance_form.addRow("Farve", self.prop_color)
        appearance_form.addRow("", self.prop_locked)
        self.prop_appearance_disclosure = DisclosureSection("Udseende og placering", appearance_group, expanded=False)
        outer.addWidget(self.prop_appearance_disclosure)

        procurement_group=QGroupBox("")
        procurement_form=tune_form_layout(QFormLayout(procurement_group))
        self.prop_mounting_zone=QComboBox()
        for value,label in core.MOUNTING_ZONE_OPTIONS:self.prop_mounting_zone.addItem(label,value)
        self.prop_mounting_zone.currentIndexChanged.connect(self._mounting_zone_changed)
        self.prop_mounting_height=QDoubleSpinBox(); self.prop_mounting_height.setRange(0,10000)
        self.prop_mounting_height.setDecimals(0); self.prop_mounting_height.setSingleStep(50); self.prop_mounting_height.setSuffix(" mm")
        self.prop_mounting_height.setSpecialValueText("Ikke angivet")
        self.prop_material_color=QComboBox(); self.prop_material_color.setEditable(True)
        for value in core.MATERIAL_COLOR_PRESETS:self.prop_material_color.addItem(value or "Ikke angivet",value)
        self.prop_material_color.setToolTip("Ønsket farve på ramme/afdækning. Feltet bruges til segmentering og indkøb; artikelvalget ændres ikke automatisk.")
        self.prop_already_purchased=QCheckBox("Allerede købt / på lager")
        self.prop_already_purchased.setToolTip("Markerer alle artikler og styklistekomponenter fra dette symbol som allerede købt i BOM og eksport.")
        procurement_form.addRow("Monteringsprofil",self.prop_mounting_zone)
        procurement_form.addRow("Præcis højde",self.prop_mounting_height)
        procurement_form.addRow("Materialefarve",self.prop_material_color)
        procurement_form.addRow("",self.prop_already_purchased)
        procurement_note=QLabel("Profil, højde, farve og indkøbsstatus følger den konkrete symbolforekomst og bliver separate, filterbare felter i Excel.")
        procurement_note.setWordWrap(True); procurement_note.setObjectName("sectionHint"); procurement_form.addRow(procurement_note)
        self.procurement_disclosure=DisclosureSection("Montage og indkøb",procurement_group,expanded=False)
        outer.addWidget(self.procurement_disclosure)

        self.combo_group = QGroupBox("")
        cg = QFormLayout(self.combo_group)
        cg.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.prop_combo_mode = QComboBox()
        self.prop_combo_mode.addItems(list(core.COMBO_LABEL_MODES))
        self.prop_switch_label = QLineEdit()
        self.prop_switch_label.setPlaceholderText("fx S1,S2,S3")
        self.prop_switch_group = QLineEdit()
        self.prop_switch_group.setPlaceholderText("fx G1,G1,G2")
        self.prop_socket_label = QLineEdit()
        self.prop_socket_group = QLineEdit()
        cg.addRow("Type", self.prop_combo_mode)
        cg.addRow("Afbrydere · mærkning", self.prop_switch_label)
        cg.addRow("Afbrydere · gruppe", self.prop_switch_group)
        cg.addRow("Stik · mærkning", self.prop_socket_label)
        cg.addRow("Stik · gruppe", self.prop_socket_group)
        self.combo_disclosure=DisclosureSection("Kombi-mærkning",self.combo_group,expanded=False)
        outer.addWidget(self.combo_disclosure)
        self.combo_disclosure.hide()

        self.assoc_group = QGroupBox("Lystilhørsforhold")
        al = QVBoxLayout(self.assoc_group)
        al.setSpacing(7)
        self.prop_assoc = QLabel("—")
        self.prop_assoc.setWordWrap(True)
        self.prop_assoc.setObjectName("accentText")
        al.addWidget(self.prop_assoc)
        self.assoc_channels_table=QTableWidget(0,3)
        self.assoc_channels_table.setHorizontalHeaderLabels(["Betjening","Bogstav","Lampesteder"])
        self.assoc_channels_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.assoc_channels_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.assoc_channels_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.assoc_channels_table.verticalHeader().setVisible(False)
        self.assoc_channels_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        self.assoc_channels_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents)
        self.assoc_channels_table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
        self.assoc_channels_table.cellDoubleClicked.connect(lambda _row,_col:self._start_selected_association_channel())
        self.assoc_channels_table.setToolTip("Vælg en fysisk betjening og dobbeltklik for at redigere dens lampesteder.")
        al.addWidget(self.assoc_channels_table)
        self.light_outputs_table=QTableWidget(0,3)
        self.light_outputs_table.setHorizontalHeaderLabels(["Udgang","Bogstav","Navn"])
        self.light_outputs_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.light_outputs_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.light_outputs_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.light_outputs_table.verticalHeader().setVisible(False)
        self.light_outputs_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents)
        self.light_outputs_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents)
        self.light_outputs_table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
        self.light_outputs_table.cellDoubleClicked.connect(lambda _row,_col:self._rename_selected_light_output())
        self.light_outputs_table.setToolTip("Dobbeltklik på en udgang for at give den et tydeligt navn.")
        al.addWidget(self.light_outputs_table)
        self.light_outputs_actions=QWidget()
        light_outputs_layout=QHBoxLayout(self.light_outputs_actions)
        light_outputs_layout.setContentsMargins(0,0,0,0)
        self.light_output_add_button=QPushButton("+ Tilføj tænding")
        self.light_output_add_button.clicked.connect(self._add_light_output)
        self.light_output_remove_button=_set_role(QPushButton("Fjern valgt"),"dangerButton")
        self.light_output_remove_button.clicked.connect(self._remove_selected_light_output)
        light_outputs_layout.addWidget(self.light_output_add_button,1)
        light_outputs_layout.addWidget(self.light_output_remove_button)
        al.addWidget(self.light_outputs_actions)
        self.light_outputs_table.hide(); self.light_outputs_actions.hide()
        ar = QHBoxLayout()
        self.assoc_button = QPushButton("Tilføj / fjern lys…")
        self.assoc_button.clicked.connect(self._start_selected_association_channel)
        self.clear_assoc_button = _set_role(QPushButton("Ryd"), "dangerButton")
        self.clear_assoc_button.clicked.connect(self.clear_selected_associations)
        ar.addWidget(self.assoc_button, 1)
        ar.addWidget(self.clear_assoc_button)
        self.assoc_edit_actions=QWidget()
        self.assoc_edit_actions.setLayout(ar)
        ar.setContentsMargins(0,0,0,0)
        al.addWidget(self.assoc_edit_actions)
        self.assoc_session_actions=QWidget()
        session_row=QHBoxLayout(self.assoc_session_actions)
        session_row.setContentsMargins(0,0,0,0)
        self.assoc_save_button=_set_role(QPushButton("Gem tilknytning"),"primaryButton")
        self.assoc_save_button.setToolTip("Gem alle ændringer i den aktive tilknytningssession (Enter eller Ctrl+Enter).")
        self.assoc_save_button.clicked.connect(self._finish_active_association)
        self.assoc_cancel_button=_set_role(QPushButton("Annuller"),"quietButton")
        self.assoc_cancel_button.setToolTip("Fortryd hele den aktive tilknytningssession (Esc).")
        self.assoc_cancel_button.clicked.connect(self.cancel_active_tool)
        session_row.addWidget(self.assoc_save_button,1)
        session_row.addWidget(self.assoc_cancel_button)
        self.assoc_session_actions.hide()
        al.addWidget(self.assoc_session_actions)
        self.assoc_note = QLabel(
            "Vælg en betjening i tabellen, vælg Tilføj / fjern lys, og klik derefter "
            "lampesteder på tegningen. Enter gemmer; Esc annullerer."
        )
        self.assoc_note.setWordWrap(True)
        self.assoc_note.setObjectName("sectionHint")
        al.addWidget(self.assoc_note)
        # Relationer er den primære opgave for afbrydere og lys. Vis dem før
        # generelle metadata; skjul hele sektionen for symboler uden lysrolle.
        outer.addWidget(self.assoc_group)
        self.assoc_group.hide()

        self.spot_parent_group = QGroupBox("Spotgruppe / lampested")
        spl = QVBoxLayout(self.spot_parent_group)
        spl.setSpacing(7)
        self.spot_group_value = QLabel("Gruppe: —")
        self.spot_group_value.setWordWrap(True)
        self.spot_group_value.setObjectName("accentText")
        spl.addWidget(self.spot_group_value)
        sgr = QHBoxLayout()
        self.spot_group_button = QPushButton("Gruppér / omdøb…")
        self.spot_group_button.setToolTip("Saml de valgte spots i én vedvarende spotgruppe, eller omdøb den eksisterende gruppe.")
        self.spot_group_button.clicked.connect(self.group_selected_spots)
        self.spot_group_select_button = _set_role(QPushButton("Vælg gruppe"), "quietButton")
        self.spot_group_select_button.clicked.connect(self.select_spot_group)
        self.spot_group_clear_button = _set_role(QPushButton("Opløs gruppe"), "dangerButton")
        self.spot_group_clear_button.clicked.connect(self.dissolve_spot_group)
        sgr.addWidget(self.spot_group_button, 1)
        sgr.addWidget(self.spot_group_select_button)
        sgr.addWidget(self.spot_group_clear_button)
        spl.addLayout(sgr)
        self.spot_parent_value = QLabel("Lampested: —")
        self.spot_parent_value.setWordWrap(True)
        self.spot_parent_value.setObjectName("positiveText")
        spl.addWidget(self.spot_parent_value)
        spr = QHBoxLayout()
        self.spot_parent_link_button = QPushButton("Tilknyt lampested…")
        self.spot_parent_link_button.setToolTip("Hvis et valgt spot er grupperet, tilknyttes hele spotgruppen samlet.")
        self.spot_parent_link_button.clicked.connect(self.start_spot_parent_for_selection)
        self.spot_parent_unlink_button = _set_role(QPushButton("Frakobl"), "dangerButton")
        self.spot_parent_unlink_button.clicked.connect(self.unlink_selected_spots)
        spr.addWidget(self.spot_parent_link_button, 1)
        spr.addWidget(self.spot_parent_unlink_button)
        spl.addLayout(spr)
        note=QLabel("Spotgrupper er logiske grupper. De ændrer ikke gruppe/kreds. Kobles ét grupperet spot til et lampested, følger hele spotgruppen med.")
        note.setWordWrap(True); note.setObjectName("sectionHint"); spl.addWidget(note)
        self.spot_parent_group.hide()
        outer.addWidget(self.spot_parent_group)

        self.bom_group = QGroupBox("")
        bgl = QVBoxLayout(self.bom_group)
        bgl.setSpacing(7)
        self.bom_summary = QLabel("—")
        self.bom_summary.setWordWrap(True)
        self.bom_summary.setObjectName("accentText")
        bgl.addWidget(self.bom_summary)
        self.bom_assign_button = QPushButton("Tilknyt artikler…")
        self.bom_assign_button.clicked.connect(self.open_bom_for_selection)
        bgl.addWidget(self.bom_assign_button)
        self.bom_room_summary=QLabel("BOM-rum: —"); self.bom_room_summary.setWordWrap(True); self.bom_room_summary.setObjectName("subtleText"); bgl.addWidget(self.bom_room_summary)
        self.bom_room_button=_set_role(QPushButton("Ekstra BOM-rum…"),"quietButton"); self.bom_room_button.setToolTip("Lad dette symbol tælle med i et ekstra rums BOM uden at flytte det fysisk eller ændre gruppe/kreds."); self.bom_room_button.clicked.connect(self.edit_bom_rooms_for_selection); bgl.addWidget(self.bom_room_button)
        note=QLabel("Tilknytningen gælder kun dette konkrete symbol. Ekstra BOM-rum er additive og ændrer ikke symbolplacering, gruppe/kreds eller Alle rum-totalen.")
        note.setWordWrap(True); note.setObjectName("sectionHint")
        bgl.addWidget(note)
        self.bom_disclosure=DisclosureSection("Artikler / BOM",self.bom_group,expanded=False)
        self.bom_disclosure.hide()
        outer.addWidget(self.bom_disclosure)

        self.symbol_cables_group = QGroupBox("Kabler ved symbol")
        scgl = QVBoxLayout(self.symbol_cables_group); scgl.setSpacing(7)
        self.symbol_cables_summary = QLabel("—")
        self.symbol_cables_summary.setWordWrap(True); self.symbol_cables_summary.setObjectName("subtleText")
        scgl.addWidget(self.symbol_cables_summary)
        self.symbol_cables_attach = _set_role(QPushButton("Tilknyt eksisterende kabel…"), "primaryButton")
        self.symbol_cables_attach.setToolTip("Vælg derefter kabelstrækningen direkte på tegningen. Lampestedet bliver et fysisk tilslutningspunkt på det eksisterende kabel.")
        self.symbol_cables_attach.clicked.connect(self.start_cable_attach_for_selection)
        self.symbol_cables_attach.hide(); scgl.addWidget(self.symbol_cables_attach)
        scr = QHBoxLayout(); scr.setSpacing(6)
        self.symbol_cables_combo = QComboBox(); scr.addWidget(self.symbol_cables_combo,1)
        self.symbol_cables_select = _set_role(QPushButton("Vælg kabel"), "quietButton")
        self.symbol_cables_select.clicked.connect(self._select_connected_cable_from_properties)
        scr.addWidget(self.symbol_cables_select)
        scgl.addLayout(scr)
        self.symbol_cables_group.hide()
        outer.addWidget(self.symbol_cables_group)

        self.pl_box_group = QGroupBox("PL-loftdåse")
        pbl = QVBoxLayout(self.pl_box_group); pbl.setSpacing(7)
        self.pl_box_summary = QLabel("—")
        self.pl_box_summary.setWordWrap(True); self.pl_box_summary.setObjectName("accentText")
        pbl.addWidget(self.pl_box_summary)
        pbr=QHBoxLayout(); pbr.setSpacing(6)
        self.pl_box_button = QPushButton("Konfigurer PL-dåse…")
        self.pl_box_button.clicked.connect(self.open_pl_box_for_selection); pbr.addWidget(self.pl_box_button,1)
        self.pl_box_report_button=_set_role(QPushButton("Rapport…"),"quietButton")
        self.pl_box_report_button.setToolTip("Eksportér samlet A4-montagerapport med tydelig lederfordeling for alle PL-dåser i projektet.")
        self.pl_box_report_button.clicked.connect(self.export_pl_box_report); pbr.addWidget(self.pl_box_report_button)
        pbl.addLayout(pbr)
        pbh=QLabel("Viser de seks fysiske kabelindføringer og lederfordelingen i PL-loftdåsen. Et gennemgående kabel bruger to indføringer.")
        pbh.setWordWrap(True); pbh.setObjectName("sectionHint"); pbl.addWidget(pbh)
        self.pl_box_group.hide()
        outer.addWidget(self.pl_box_group)

        self.apply_button = QPushButton("Anvend ændringer")
        self.apply_button.setObjectName("primaryButton")
        self.apply_button.clicked.connect(self.apply_properties)
        self.delete_symbol_button = _set_role(QPushButton("Slet symbol"), "dangerButton")
        self.delete_symbol_button.setToolTip("Slet det valgte symbol. Handlingen kan fortrydes med Ctrl+Z.")
        self.delete_symbol_button.clicked.connect(self.delete_selected_symbols)
        self.property_actions_widget=QWidget()
        property_actions=QHBoxLayout(self.property_actions_widget); property_actions.setContentsMargins(0,0,0,0); property_actions.setSpacing(7)
        property_actions.addWidget(self.apply_button,1); property_actions.addWidget(self.delete_symbol_button)
        outer.addWidget(self.property_actions_widget)
        outer.addStretch(1)

        scroll.setWidget(widget)
        self.properties_page = scroll
        self.inspector_stack.addWidget(scroll)
        self._enable_properties(False)
        self._apply_properties_workflow_visibility()

    def _property_workflow_has_content(self,key:str,placement=None,*,multi_spots:bool=False)->bool:
        key=str(key or "")
        if multi_spots:return key=="connect"
        if placement is None:return False
        if key in {"data","purchase"}:return True
        role=core.association_role(getattr(placement,"symbol",""))
        if role in ("switch","light") or placement.symbol in {"spot","light_connection"}:return True
        # The connection index is maintained with the cable visual cache, so
        # workflow availability never has to scan every physical cable.
        uid=str(getattr(placement,"uid","") or "")
        return bool(self._cables_by_symbol_uid.get(uid,[]))

    def _set_properties_workflow(self,key:str,*,user:bool=False)->None:
        key=key if key in {"connect","data","purchase"} else "data"
        if user:self._properties_workflow_user_choice=True
        self._properties_workflow=key
        p=getattr(self,"_properties_current_placement",None)
        if user and key=="purchase" and p is not None:
            self._refresh_selected_symbol_bom_ui(p)
        for name,button in getattr(self,"properties_workflow_buttons",{}).items():
            button.setChecked(name==key)
        hints={
            "connect":"Tilknyt funktioner, lampesteder, spots og kabler.",
            "data":"Redigér mærkning, gruppe, udseende og symboldata.",
            "purchase":"Angiv montage, materialevalg, lagerstatus og artikler.",
        }
        if hasattr(self,"properties_workflow_hint"):
            self.properties_workflow_hint.setText(hints[key])
        self._apply_properties_workflow_visibility()

    def _apply_properties_workflow_visibility(self)->None:
        if not hasattr(self,"properties_workflow_bar"):return
        p=getattr(self,"_properties_current_placement",None)
        multi=bool(getattr(self,"_properties_multi_spots",False))
        has_selection=bool(p is not None or multi)
        self.properties_workflow_bar.setVisible(has_selection)
        for name,button in getattr(self,"properties_workflow_buttons",{}).items():
            button.setEnabled(self._property_workflow_has_content(name,p,multi_spots=multi))
        if not has_selection:
            for widget in (
                self.assoc_group,self.spot_parent_group,self.symbol_cables_group,self.pl_box_group,
                self.basic_group,self.prop_appearance_disclosure,self.combo_disclosure,
                self.procurement_disclosure,self.bom_disclosure,self.property_actions_widget,
            ):widget.hide()
            return
        key=getattr(self,"_properties_workflow","data")
        symbol=str(getattr(p,"symbol","") or "") if p is not None else ""
        role=core.association_role(symbol) if p is not None else None

        # Forbind
        self.assoc_group.setVisible(key=="connect" and role in ("switch","light"))
        self.spot_parent_group.setVisible(key=="connect" and (multi or symbol in {"spot","light_connection"}))
        cables_relevant=bool(
            p is not None and self._property_workflow_has_content("connect",p)
            and (symbol in {"light_connection","wall_light_outlet"} or self.symbol_cables_combo.count()>0)
        )
        self.symbol_cables_group.setVisible(key=="connect" and cables_relevant)
        self.pl_box_group.setVisible(key=="connect" and symbol=="light_connection")

        # Data
        self.basic_group.setVisible(key=="data" and p is not None)
        self.prop_appearance_disclosure.setVisible(key=="data" and p is not None)
        self.combo_disclosure.setVisible(key=="data" and p is not None and core.is_combo_symbol(symbol))

        # Indkøb
        self.procurement_disclosure.setVisible(key=="purchase" and p is not None)
        bom_relevant=bool(p is not None and (core.bom_supported_symbol(symbol) or self.project.rooms))
        self.bom_disclosure.setVisible(key=="purchase" and bom_relevant)
        self.property_actions_widget.setVisible(key in {"data","purchase"} and p is not None)

    def _enable_properties(self, enabled: bool) -> None:
        for w in (self.prop_label, self.prop_group, self.prop_size, self.prop_rotation, self.prop_line_width,
                  self.prop_color, self.prop_locked, self.apply_button, self.delete_symbol_button, self.prop_combo_mode,
                  self.prop_mounting_zone, self.prop_mounting_height, self.prop_material_color, self.prop_already_purchased,
                  self.prop_switch_label, self.prop_switch_group, self.prop_socket_label, self.prop_socket_group,
                  self.assoc_button, self.clear_assoc_button):
            w.setEnabled(enabled)

    def _mounting_zone_changed(self,*_args) -> None:
        if getattr(self,"_loading_properties",False):return
        if not hasattr(self,"prop_mounting_height") or float(self.prop_mounting_height.value())>0:return
        defaults={"floor":300.0,"switch":1100.0}
        value=defaults.get(str(self.prop_mounting_zone.currentData() or ""))
        if value is not None:self.prop_mounting_height.setValue(value)

    def _cached_article_catalog(self, *, refresh: bool = False) -> list[dict]:
        """Return the materialized article catalog used by the inspector.

        Loading the global catalog creates a defensive copy of thousands of
        rows. Selection changes must stay instant, so refresh only after an
        article/BOM operation that can actually have changed the catalog.
        """
        if refresh or not hasattr(self,"global_article_catalog"):
            self.global_article_catalog=user_library.load_core_article_catalog()
            self._cable_article_catalog_cache=None
        return self.global_article_catalog

    def open_bom_manager(self) -> None:
        selected=self._selected_symbol_item()
        focus_uid=selected.placement.uid if selected is not None and core.bom_supported_symbol(selected.placement.symbol) else ""
        from elplan_qt.qt_articles import BomManagerDialog
        dlg=BomManagerDialog(self,focus_uid)
        result=dlg.exec(); self.clear_bom_article_highlight()
        if result==QDialog.DialogCode.Accepted:
            self._cached_article_catalog(refresh=True)
            self._hover_bom_cache.clear()
            self._selection_changed()
            self._notify("Artikeltilknytninger/BOM opdateret.", kind="success")

    def open_bom_manager_for_room(self,room_uid) -> None:
        from elplan_qt.qt_articles import BomManagerDialog
        dlg=BomManagerDialog(self,"",initial_room_uid=str(room_uid or ""))
        result=dlg.exec(); self.clear_bom_article_highlight()
        if result==QDialog.DialogCode.Accepted:
            self._cached_article_catalog(refresh=True)
            self._hover_bom_cache.clear(); self._selection_changed(); self._notify("Rum-BOM opdateret.",kind="success")

    def edit_bom_rooms_for_selection(self) -> None:
        selected=self._selected_symbol_item()
        if selected is None:return
        self.edit_placement_bom_rooms(selected.placement)

    def _refresh_selected_bom_room_summary(self,placement) -> None:
        if not hasattr(self,'bom_room_summary'):return
        physical=self.room_for_placement(placement) if hasattr(self,'room_for_placement') else None
        physical_text=core.room_display_text(physical) if physical is not None else 'Uden rum'
        additions=core.normalize_placement_bom_room_additions(self.project.raw.get('placement_bom_room_additions',{}))
        by_uid={str(getattr(r,'uid','') or ''):r for r in self.project.rooms}
        extra=[core.room_display_text(by_uid[uid]) for uid in additions.get(str(getattr(placement,'uid','') or ''),[]) if uid in by_uid]
        self.bom_room_summary.setText(f"Fysisk: {physical_text}" + (f" · ekstra BOM-rum: {', '.join(extra)}" if extra else " · ingen ekstra BOM-rum"))
        self.bom_room_button.setEnabled(bool(self.project.rooms))

    def _refresh_selected_symbol_bom_ui(self,placement)->None:
        """Materialize the symbol BOM only while Indkøb is actually used."""
        if placement is None:return
        if core.bom_supported_symbol(placement.symbol):
            effective_assemblies={a["id"]:a for a in core.normalize_bom_assemblies(self.global_bom_assemblies)}
            for assembly in core.normalize_bom_assemblies(self.project.raw.get("bom_assemblies",[])):
                effective_assemblies.setdefault(assembly["id"],assembly)
            self.bom_summary.setText(core.bom_binding_summary(
                placement.symbol,self._cached_article_catalog(),self.project.raw.get("placement_articles",{}),
                list(effective_assemblies.values()),self.project.raw.get("placement_assemblies",{}),binding_key=placement.uid,
            ))
            self._refresh_selected_bom_room_summary(placement)
            self.bom_assign_button.setEnabled(True)
        elif self.project.rooms:
            self.bom_summary.setText("Denne symboltype har ingen direkte BOM-dele, men du kan stadig angive ekstra BOM-rum som projektkontekst.")
            self._refresh_selected_bom_room_summary(placement)
            self.bom_assign_button.setEnabled(False)

    def open_bom_for_selection(self) -> None:
        selected=self._selected_symbol_item()
        if selected is None or not core.bom_supported_symbol(selected.placement.symbol):
            return
        from elplan_qt.qt_articles import BomManagerDialog
        dlg=BomManagerDialog(self,selected.placement.uid)
        result=dlg.exec(); self.clear_bom_article_highlight()
        if result==QDialog.DialogCode.Accepted:
            self._cached_article_catalog(refresh=True)
            self._hover_bom_cache.clear()
            self._selection_changed()
            self._notify(f"Artikler opdateret for det valgte {core.symbol_display_name(selected.placement.symbol)}-symbol.", kind="success")

    def choose_cable_color(self) -> None:
        current=QColor(core.normalize_hex_color(self.cable_color.text(),core.DEFAULT_CABLE_COLOR))
        chosen=QColorDialog.getColor(current,self,"Vælg kategorifarve")
        if not chosen.isValid():return
        cid=str(self.cable_category_combo.currentData() or core.DEFAULT_CABLE_CATEGORY) if hasattr(self,"cable_category_combo") else core.DEFAULT_CABLE_CATEGORY
        categories=self._cable_categories()
        for rec in categories:
            if rec["id"]==cid: rec["color"]=chosen.name(); break
        self.project.raw["cable_categories"]=categories
        _set_color_button(self.cable_color,chosen.name())
        self._sync_cable_category_styles(); self._cable_panel_changed(); self.project.dirty=True; self._update_title()

    def _cable_line_style_changed(self,*_args) -> None:
        if getattr(self,"_loading_cable_panel",False):return
        if not hasattr(self,"cable_category_combo"):return
        cid=str(self.cable_category_combo.currentData() or core.DEFAULT_CABLE_CATEGORY)
        style=core.normalize_cable_line_style(self.cable_line_style.currentData())
        categories=self._cable_categories()
        for rec in categories:
            if rec["id"]==cid: rec["line_style"]=style; break
        self.project.raw["cable_categories"]=categories
        self._sync_cable_category_styles(); self._cable_panel_changed(); self.project.dirty=True; self._update_title()

    def choose_property_color(self) -> None:
        item = self._selected_symbol_item()
        current = QColor(item.placement.color if item else "#d00000")
        chosen = QColorDialog.getColor(current, self, "Vælg symbolfarve")
        if chosen.isValid():
            _set_color_button(self.prop_color, chosen.name())

    def cancel_active_tool(self) -> None:
        was_cable = bool(getattr(self.view,"_cable_active",False))
        was_assoc = bool(self.association_source_uid or self.association_pick_source)
        was_cable_attach = bool(getattr(self,"_pending_cable_attach_symbol_uid","") or "")
        self._pending_cable_attach_symbol_uid = ""
        if was_assoc:
            source_uid=str(self.association_source_uid or "")
            self._finish_association_mode(source_uid,"Tilknytningen blev annulleret.",commit=False)
        else:
            self.association_source_uid = ""
            self.association_active_letter = ""
            self.association_force_new = False
            self.association_pick_source = False
            self.association_guided_setup = False
            self.association_channel_index = 0
            self._association_session_before=None
            self._association_session_dirty_before=False
            self._sync_association_session_ui()
        self.spot_parent_pending = []
        self._clear_association_visuals()
        self._refresh_switch_association_badges()
        self._clear_spot_link_visuals()
        self.view.cancel_tool(emit_signal=False)
        self.view.unsetCursor()
        if was_assoc:
            return
        if was_cable_attach:
            self._set_status("Tilknytning til eksisterende kabel annulleret.")
            return
        if self._cable_tool_is_open():
            self.close_cable_tool()
        else:
            self._set_status("Værktøj afsluttet.")

    def _view_tool_cancelled(self) -> None:
        if bool(getattr(self,"_cable_marking_active",False)) and hasattr(self,"act_cable_marking") and self.act_cable_marking.isChecked():
            self.act_cable_marking.setChecked(False)
            return
        selected=self._selected_symbol_item()
        if selected is not None and selected.placement.symbol=="spot":
            self._set_status("Spot valgt · brug ‘Tilknyt lampested…’ i Egenskaber for at vælge spot-tilhørsforhold")
        elif self._cable_tool_is_open():
            self.close_cable_tool()
        else:
            self._set_status("Vælg et symbol, kabel eller en handling.")

    def _set_status(self, text: str) -> None:
        self.statusBar().showMessage(text)
        if hasattr(self, "_refresh_workflow_bar"): self._refresh_workflow_bar()

    def _navigator_action_changed(self,checked: bool) -> None:
        data=core.load_app_settings(); data["show_navigator"]=bool(checked); core.save_app_settings(data); self.app_settings=data
        if hasattr(self,"toggle_navigator"):self.toggle_navigator(bool(checked))

    def _notify(self, text: str, *, kind: str = "success", timeout: int = 2200) -> None:
        """Non-modal feedback for successful/low-risk operations."""
        self._set_status(text)
        toast = getattr(self, "toast_overlay", None)
        if toast is not None:
            toast.show_message(text, kind=kind, timeout=timeout)

    def _update_title(self) -> None:
        name = project_storage.project_name_from_path(getattr(self.project,"path",None),getattr(self.project,"source_file",None))
        dirty = " *" if self.project.dirty else ""
        suffix = f" — {name}" if name else ""
        collab = self._collaboration_title_suffix() if hasattr(self,"_collaboration_title_suffix") else ""
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}{suffix}{dirty}{collab}")

    def _undo_clean_changed(self, clean: bool) -> None:
        # Undo tilbage til den gemte tilstand skal også fjerne * i titlen.
        # Ikke-undo ændringer (lag, kalibrering m.m.) bevares som dirty, fordi
        # de vil få dokumentet til at afvige fra den gemte snapshot.
        if clean and self.project.matches_saved_state():
            self.project.dirty = False
        elif not clean:
            self.project.dirty = True
        self._update_title()

    def _refresh_zoom_dependent_visuals(self) -> None:
        """Coalesced redraw for geometry whose screen-space spacing depends on zoom."""
        self._rebuild_cable_visual_cache(refresh_items=True)
        for ann in self.annotation_items.values():
            ann.refresh()
        self._refresh_switch_association_badges()
        if self.association_pick_source:
            self._refresh_association_source_picker()
        elif self.association_source_uid:
            self._refresh_association_visuals()

    def _zoom_changed(self, zoom: float) -> None:
        # Keep the UI responsive during wheel/trackpad bursts. Restarting a
        # 32-ms single-shot timer collapses dozens of expensive redraws into
        # the final state of the current gesture.
        if hasattr(self,"_zoom_visual_refresh_timer"):
            self._zoom_visual_refresh_timer.start()
        else:
            self._refresh_zoom_dependent_visuals()
        if hasattr(self, "status_zoom"):
            self.status_zoom.setText(f"{zoom * 100:.0f}%")
        if hasattr(self, "status_objects"):
            self.status_objects.setText(f"{len(self.project.placements)} symboler · {len(self.project.rooms)} rum")
        # Zoom changes only the viewport rectangle; navigator content extents do
        # not change. Repainting it is cheap, while refresh_overview() scans the
        # complete graphics scene. Likewise, updating the status text must not
        # rebuild the workflow overlay for every wheel event.
        nav=getattr(self,"navigator",None)
        if nav is not None and nav.isVisible():
            nav.update()
        self.statusBar().showMessage(f"CAD {len(self.cad_primitives):,} objekter · zoom {zoom:.2f}×".replace(",", "."))

    def select_oda(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Vælg ODAFileConverter.exe", "", "ODA File Converter (ODAFileConverter.exe)")
        if path:
            if core.set_oda_exec_path(path):
                QMessageBox.information(self, "ODA", "ODA File Converter er konfigureret.")
            else:
                QMessageBox.warning(self, "ODA", "Den valgte fil er ikke ODAFileConverter.exe.")

    def _confirm_discard_changes(self, action: str = "fortsætte") -> bool:
        """Spørg før et projekt med ikke-gemte ændringer erstattes eller lukkes."""
        if not self.project.dirty:
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Ikke gemte ændringer")
        box.setText("Projektet indeholder ændringer, der ikke er gemt.")
        box.setInformativeText(f"Vil du gemme ændringerne, før du {action}?")
        box.setStandardButtons(
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel
        )
        box.setDefaultButton(QMessageBox.StandardButton.Save)
        answer = box.exec()
        if answer == QMessageBox.StandardButton.Save:
            return bool(self.save_project())
        if answer == QMessageBox.StandardButton.Discard:
            return True
        return False

    def _resolve_project_source(self, project: ProjectDocument) -> Path | None:
        """Understøt både absolutte og projekt-relative CAD-stier."""
        raw = str(project.source_file or "").strip()
        if not raw:
            return None
        source = Path(raw).expanduser()
        if not source.is_absolute() and project.path is not None:
            source = project.path.parent / source
        return source

    def _recent_project_paths(self, existing_only: bool = True) -> list[str]:
        return core.normalize_recent_project_paths(self.app_settings.get("recent_projects",[]),8,existing_only)

    def _save_recent_project_paths(self, paths) -> None:
        data=core.load_app_settings()
        data["recent_projects"]=core.normalize_recent_project_paths(paths,8,False)
        core.save_app_settings(data)
        self.app_settings=data

    def _remember_recent_project(self, path) -> None:
        if not path:return
        normalized=core.normalize_recent_project_paths([str(path)],1,False)
        if not normalized:return
        current=core.normalize_recent_project_paths(self.app_settings.get("recent_projects",[]),8,False)
        target=normalized[0]; target_key=os.path.normcase(target)
        merged=[target]+[x for x in current if os.path.normcase(x)!=target_key]
        self._save_recent_project_paths(merged[:8])
        if hasattr(self,"recent_projects_menu"):
            self._refresh_recent_projects_menu()
        self._refresh_welcome_page()

    def _forget_recent_project(self, path) -> None:
        normalized=core.normalize_recent_project_paths([str(path)],1,False)
        key=os.path.normcase(normalized[0]) if normalized else os.path.normcase(str(path))
        current=core.normalize_recent_project_paths(self.app_settings.get("recent_projects",[]),8,False)
        keep=[x for x in current if os.path.normcase(x)!=key]
        self._save_recent_project_paths(keep)
        if hasattr(self,"recent_projects_menu"):
            self._refresh_recent_projects_menu()
        self._refresh_welcome_page()

    def _clear_recent_projects(self) -> None:
        self._save_recent_project_paths([])
        if hasattr(self,"recent_projects_menu"):
            self._refresh_recent_projects_menu()
        self._refresh_welcome_page()

    def _refresh_recent_projects_menu(self) -> None:
        menu=getattr(self,"recent_projects_menu",None)
        if menu is None:return
        menu.clear()
        stored=core.normalize_recent_project_paths(self.app_settings.get("recent_projects",[]),8,False)
        paths=core.normalize_recent_project_paths(stored,8,True)
        if paths!=stored:
            self._save_recent_project_paths(paths)
        if not paths:
            empty=menu.addAction("Ingen seneste projekter")
            empty.setEnabled(False)
            return
        for index,value in enumerate(paths,1):
            path=Path(value)
            name=path.name[:-len(".elplan.json")] if path.name.lower().endswith(".elplan.json") else path.stem
            parent=path.parent.name or str(path.parent)
            label=f"{index}. {name}   —   {parent}".replace("&","&&")
            action=menu.addAction(label)
            action.setToolTip(str(path)); action.setStatusTip(str(path))
            if index==1:
                action.setShortcut(QKeySequence("Ctrl+Shift+O"))
                action.setShortcutVisibleInContextMenu(True)
            action.triggered.connect(lambda checked=False,p=str(path):self.open_recent_project(p))
        menu.addSeparator()
        clear_action=menu.addAction("Ryd liste")
        clear_action.triggered.connect(self._clear_recent_projects)

    def _load_cad_and_scene(self, source: str, project: ProjectDocument | None = None) -> None:
        self._update_busy("Indlæser og fortolker CAD-data…")
        self._hover_bom_cache.clear()
        # Indlæs og parse først. En defekt DWG/DXF må ikke erstatte projektmodellen
        # mens den gamle tegning stadig står på skærmen.
        new_doc = core.load_document(source)
        self._update_busy("Forbereder lag og geometri…")
        new_primitives, counts = core.extract_cad_primitives(new_doc)
        candidate = project if project is not None else self.project
        self.project = candidate
        self._room_project_changed()
        self._cable_marking_project_changed()
        self.project.raw["cable_categories"]=core.normalize_cable_category_records(self.project.raw.get("cable_categories",[]))
        if hasattr(self,"_refresh_cable_category_strip"):
            self._refresh_cable_category_strip()
        # Ældre projekter kan have individuelle kabelfarver fra før kategorierne.
        # De bevares ved åbning og migreres først, når brugeren aktivt vælger/ændrer kategori.
        # 0.45.0: kernedata og projektdata er adskilt. Ældre projekter
        # migreres sikkert til den globale kernedatamappe ved åbning.
        try:
            migration=user_library.migrate_legacy_project_core_data(self.project.raw)
            if migration.get("changed"):
                self.global_bom_assemblies=deepcopy(user_library.load_global_bom_assemblies())
                self.app_settings=core.load_app_settings()
                self.project.dirty=True
        except Exception:
            # Helperen fjerner kun en kategori efter vellykket persistens. Hvis
            # fx disken er skrivebeskyttet, bliver de resterende legacy-data i
            # projektet og kan forsøges migreret igen senere.
            pass
        self.doc = new_doc
        self.cad_primitives = new_primitives
        self.snap_engine = QtSnapEngine(self.cad_primitives, lambda layer: self.project.layer_visibility.get(layer, True))
        self.view.set_snap_engine(self.snap_engine)
        if hasattr(self, "palette_size"):
            try:self.palette_size.setValue(float(self.project.raw.get("default_symbol_size",200.0)))
            except Exception:pass
        if hasattr(self,"spot_size_quick"):
            try:self.spot_size_quick.setValue(float(self.project.raw.get("spot_default_size",150.0)))
            except Exception:pass
        if hasattr(self,"cable_spec_combo"):
            _saved_type=str(self.project.raw.get("cable_type","Kabel") or "Kabel")
            if _saved_type not in core.CABLE_TYPES: _saved_type="Kabel"
            self.cable_type_combo.setCurrentText(_saved_type)
            self._populate_cable_category_combo(str(self.project.raw.get("cable_category",core.DEFAULT_CABLE_CATEGORY) or core.DEFAULT_CABLE_CATEGORY))
            self.cable_spec_combo.setCurrentText(str(self.project.raw.get("cable_spec","3G1,5") or "3G1,5"))
            self.cable_label_edit.setText(str(self.project.raw.get("cable_label","") or ""))
            try:self.cable_width_spin.setValue(float(self.project.raw.get("cable_line_width",.35) or .35))
            except Exception:pass
            self._set_next_cable_id()
            self._update_cable_tool_status()
        self._refresh_cable_length_ui()
        self._refresh_palette_categories()
        self._populate_symbol_palette()
        # 0.43.2: fysiske kabeltilslutninger er absolutte symbolankre. Reparer
        # eventuelle projekter, der er blevet gemt efter den tidligere edit-fejl.
        if self._repair_cable_symbol_anchors():
            self.project.dirty=True
        self.undo_stack.clear(); self.undo_stack.setClean()
        self._update_busy("Opbygger plantegningen…")
        self._rebuild_scene()
        # 0.54.1: QGraphicsView lives in a stacked central workspace. fitInView
        # must run after the canvas page is visible; fitting while the welcome
        # page owns the stack can yield a stale/invalid transform and make
        # subsequent zoom-in appear blocked.
        self._show_canvas_page()
        QApplication.processEvents()
        self.view.fit_scene()
        self.view.setFocus(Qt.FocusReason.OtherFocusReason)
        self._refresh_welcome_page()
        self._notify(f"Indlæst: {len(self.project.placements)} symboler · {len(self.project.cables)} kabler", kind="info", timeout=1800)

    def _rebuild_scene(self) -> None:
        self._clear_hover_info()
        self._visual_emphasis_signature=None
        self._selection_last_signature=None
        self._selection_refresh_pending=False
        if hasattr(self,"_selection_refresh_timer"):self._selection_refresh_timer.stop()
        self._bom_highlight_placement_uids=set(); self._bom_highlight_cable_uids=set()
        self.view.scene_will_reset()
        # Scene.clear() destroys overlay C++ objects; drop Python references first.
        self.switch_association_badges.clear()
        self._switch_badge_render_signature=None
        self._cable_bundle_badges.clear()
        self.association_target_overlays.clear()
        self.association_target_overlay_by_uid.clear()
        self.association_guide=None
        self.association_badge=None
        self.association_source_overlay=None
        self.scene.clear()
        self.layer_items.clear(); self.symbol_items.clear(); self.annotation_items.clear(); self.text_items.clear(); self.room_boundary_items.clear(); self.room_label_items.clear(); self.generated_layer_items.clear(); self.cable_items.clear()
        self._cable_chain_hover_uids.clear()
        grouped: dict[str, list] = defaultdict(list)
        for primitive in self.cad_primitives:
            grouped[primitive.layer].append(primitive)
        for layer, prims in grouped.items():
            item = CadLayerItem(layer, prims)
            item.setOpacity(self.cad_background_opacity)
            visible = self.project.layer_visibility.get(layer, True) and self._quick_visible("cad")
            item.setVisible(visible)
            self.scene.addItem(item)
            self.layer_items[layer] = item

        self._rebuild_room_graphics()

        for placement in self.project.placements:
            item = ElectricalSymbolItem(placement)
            self._wire_symbol_item(item)
            layer = core.symbol_layer(placement.symbol)
            item.setVisible(self.project.layer_visibility.get(layer, True) and self._quick_visible("symbols"))
            self.scene.addItem(item)
            self.symbol_items[placement.uid] = item
            self.generated_layer_items[layer].append(item)
            annotation = AnnotationItem(placement, self.edit_annotation_direct, item, self.view.current_scale, lambda: self.annotation_display_mode, self._spot_parent_label, self._annotation_room_direction)
            annotation.setVisible(item.isVisible() and self.project.layer_visibility.get(core.META_LAYER, True) and self._quick_visible("text"))
            self.scene.addItem(annotation)
            self.annotation_items[placement.uid] = annotation
            self.generated_layer_items[core.META_LAYER].append(annotation)

        for cable in self.project.cables:
            item = CableItem(cable, self._snap_cable_vertex, self.view.current_scale, self._cable_visual_points, lambda c: self._fmt_metres(self._points_length_metres(c.points)))
            self._wire_cable_item(item)
            item.setVisible(self._cable_layer_visible(cable) and self._quick_cable_visible(cable))
            self.scene.addItem(item)
            self.generated_layer_items[core.cable_effective_layer(cable)].append(item)
            self.cable_items[id(cable)] = item
        self._rebuild_cable_visual_cache(refresh_items=True)
        for text in self.project.texts:
            item = FreeTextItem(text)
            self._wire_text_item(item)
            item.setVisible(self.project.layer_visibility.get(core.FREE_TEXT_LAYER, True) and self._quick_visible("text"))
            self.scene.addItem(item)
            self.generated_layer_items[core.FREE_TEXT_LAYER].append(item)
            self.text_items[text.uid] = item

        self._refresh_room_visibility()
        self._rebuild_layer_list()
        self._refresh_switch_association_badges()
        self._apply_quick_visibility()
        if hasattr(self, "_apply_visual_emphasis"): self._apply_visual_emphasis()
        if hasattr(self, "status_objects"):
            self.status_objects.setText(f"{len(self.project.placements)} symboler")
        if hasattr(self,"refresh_navigator"):QTimer.singleShot(0,self.refresh_navigator)

    def _wire_symbol_item(self, item: ElectricalSymbolItem) -> None:
        item.signals.moved.connect(self._symbol_moved)
        item.signals.clicked.connect(self._symbol_clicked)
        item.signals.pointerPressed.connect(self._symbol_pointer_pressed)
        item.signals.pointerReleased.connect(self._symbol_pointer_released)
        item.signals.doubleClicked.connect(self._symbol_double_clicked)
        item.signals.contextRequested.connect(self._symbol_context_menu)
        item.signals.dragStarted.connect(self._symbol_drag_started)
        item.signals.dragFinished.connect(self._symbol_drag_finished)
        item.signals.hoverEntered.connect(lambda obj:self._hover_info_enter("symbol",obj))
        item.signals.hoverMoved.connect(lambda obj,pos:self._hover_info_move("symbol",obj,pos))
        item.signals.hoverLeft.connect(lambda obj:self._hover_info_leave("symbol",obj))
        item.snapper = self._snap_moving_symbol
        item.workflow_click_only=bool(self.association_source_uid or self.association_pick_source)

    def _wire_cable_item(self, item: CableItem) -> None:
        item.signals.editStarted.connect(self._cable_handle_edit_started)
        item.signals.editFinished.connect(self._cable_handle_edit_finished)
        item.signals.editRequested.connect(self._cable_insert_breakpoint)
        item.signals.selected.connect(self._cable_selected)
        item.signals.hoverEntered.connect(self._cable_hover_enter)
        item.signals.hoverMoved.connect(lambda obj,pos:self._hover_info_move("cable",obj,pos))
        item.signals.hoverLeft.connect(self._cable_hover_leave)
        item.signals.contextRequested.connect(self._cable_context_menu)
        item.click_handler = self._handle_cable_item_click
        if hasattr(item,"set_marking_mode"):
            item.set_marking_mode(bool(getattr(self,"_cable_marking_active",False)))

    def _set_cable_chain_hover(self, hovered_item: CableItem | None, active: bool) -> None:
        """Subtly highlight every visible cable piece from the same drawn pull."""
        cable=getattr(hovered_item,"cable",None) if hovered_item is not None else None
        chain_key=core.cable_route_chain_key(cable) if cable is not None else ""
        members=core.cable_route_chain_members(cable,self.project.cables) if cable is not None else []
        # A one-piece pull needs no secondary highlight; the normal cable hover
        # animation already communicates it better.
        wanted={str(getattr(row,"uid","") or "") for row in members} if chain_key and len(members)>1 and active else set()
        changed=self._cable_chain_hover_uids.symmetric_difference(wanted)
        if not changed:
            return
        by_uid={str(getattr(getattr(obj,"cable",None),"uid","") or ""):obj for obj in getattr(self,"cable_items",{}).values()}
        for uid in changed:
            obj=by_uid.get(uid)
            if obj is not None and hasattr(obj,"set_chain_highlight"):
                obj.set_chain_highlight(uid in wanted)
        self._cable_chain_hover_uids=wanted

    def _cable_hover_enter(self, item: CableItem) -> None:
        self._set_cable_chain_hover(item,True)
        self._hover_info_enter("cable",item)

    def _cable_hover_leave(self, item: CableItem) -> None:
        self._set_cable_chain_hover(item,False)
        self._hover_info_leave("cable",item)

    @staticmethod
    def _hover_leg_identity(row) -> tuple[str,int,str]:
        if not isinstance(row,dict):return ("",0,"")
        return (str(row.get("cable_uid","") or ""),int(row.get("point_index",0) or 0),str(row.get("leg","") or ""))

    def _pl_entry_hover_payload(self, placement) -> dict:
        legs=core.cable_legs_at_symbol(self.project.cables,str(getattr(placement,"uid","") or ""))
        entries=core.reconcile_pl_box_entries(getattr(placement,"pl_box_entries",{}),legs)
        leg_lookup={self._hover_leg_identity(x):x for x in legs}
        group=str(getattr(placement,"group","") or "").strip()
        label=str(getattr(placement,"label","") or "").strip()
        # PL-popupens overskrift skal identificere den fysiske dåse entydigt.
        # Gruppe/kreds alene er ikke nok, fordi flere lampesteder kan dele gruppe.
        ident=" · ".join(x for x in (group,label) if x) or "Lampested"
        orientation=core.normalize_pl_box_orientation(getattr(placement,"pl_box_orientation",0))
        orient_caption=core.PL_BOX_ORIENTATIONS.get(orientation,f"{orientation}°")
        used=[]; free=[]
        for port in range(1,7):
            entry=entries.get(str(port))
            if not entry:
                free.append(str(port)); continue
            leg=leg_lookup.get(self._hover_leg_identity(entry),{})
            cable_id=str(leg.get("cable_id") or "").strip()
            extra=str(leg.get("cable_extra_label") or "").strip()
            display=str(leg.get("cable_display") or cable_id or "Kabel")
            spec=str(leg.get("cable_spec") or "").strip()
            side=str(leg.get("leg_caption") or core.PL_BOX_LEG_CAPTIONS.get(str(entry.get("leg","") or ""),"")).strip()
            # Kabelnummeret står nu som sit eget, visuelt fremhævede felt. Det gør
            # det entydigt, også når kabellet samtidig har en ekstra mærkning.
            number_text=cable_id or display
            row=(f"<b><span style='color:#315f8f'>{port}</span></b>&nbsp;&nbsp;"
                 f"<span style='color:#64748b'>Kabelnr.</span>&nbsp;<b style='color:#244e79'>{html.escape(number_text)}</b>")
            if extra and extra!=cable_id:
                row+=f"<br>&nbsp;&nbsp;&nbsp;&nbsp;<span style='color:#64748b'>Mærkning:</span> <b>{html.escape(extra)}</b>"
            secondary=" · ".join(x for x in (spec,side) if x)
            if secondary:
                row+=f"<br>&nbsp;&nbsp;&nbsp;&nbsp;<span style='color:#64748b'>{html.escape(secondary)}</span>"
            used.append(row)
        details="<br>".join(used) if used else "<span style='color:#94a3b8'>Ingen kabelben placeret endnu</span>"
        if free:details+=f"<br><span style='color:#94a3b8'>Ledige: {', '.join(free)}</span>"
        unplaced=core.pl_box_unplaced_legs(entries,legs)
        if unplaced:details+=f"<br><span style='color:#b45309'><b>⚠ {len(unplaced)} kabelben mangler placering</b></span>"
        procurement=core.placement_procurement_context(placement)
        details+=f"<br><b>Montage:</b> {html.escape(procurement['mounting_summary'])}"
        details+=f"<br><b>Indkøb:</b> {html.escape(procurement['purchase_status'])}"
        room=self.room_for_placement(placement)
        room_suffix=f" · Rum: {core.room_display_text(room)}" if room is not None else ""
        return {
            "title":f"PL-dåse · {ident}",
            "subtitle":f"Kabelindføringer · {len(entries)}/6 anvendt · {orient_caption}{room_suffix}",
            "preview_mode":"pl",
            "preview_data":{"entries":entries,"legs":legs,"orientation":orientation},
            "details_html":details,
            "bom_html":self._placement_hover_bom_html(placement),
        }

    def _symbol_hover_payload(self, item: ElectricalSymbolItem) -> dict:
        placement=getattr(item,"placement",None)
        if placement is None:return {}
        if str(getattr(placement,"symbol","") or "")=="light_connection":
            return self._pl_entry_hover_payload(placement)
        bom=self._placement_hover_bom_html(placement)
        symbol=str(getattr(placement,"symbol","") or "")
        name=core.symbol_display_name(symbol)
        group=str(getattr(placement,"group","") or "").strip(); label=str(getattr(placement,"label","") or "").strip()
        ident=str(group or label or "").strip()
        uid=str(getattr(placement,"uid","") or "")
        connected=sum(1 for cable in self.project.cables if any(str(r.get("symbol_uid","") or "")==uid for r in core.cable_symbol_connections(cable)))
        details=[]
        if group:details.append(f"<b>Gruppe:</b> {html.escape(group)}")
        if label and label!=group:details.append(f"<b>Mærkning:</b> {html.escape(label)}")
        procurement=core.placement_procurement_context(placement)
        details.append(f"<b>Montage:</b> {html.escape(procurement['mounting_summary'])}")
        details.append(f"<b>Indkøb:</b> {html.escape(procurement['purchase_status'])}")
        if symbol=="spot":
            spot_group_name=str(getattr(placement,"spot_group_name","") or "").strip()
            if spot_group_name:
                gid=str(getattr(placement,"spot_group_id","") or "")
                details.append(f"<b>Spotgruppe:</b> {html.escape(spot_group_name)} ({len(self._spot_group_members(gid))} spots)")
            parent_uid=str(getattr(placement,"parent_light_uid","") or "")
            parent=self._placement_by_uid(parent_uid) if parent_uid else None
            if parent is not None:
                parent_name=str(parent.group or parent.label or "Lampested")
                details.append(f"<b>Lampested:</b> {html.escape(parent_name)}")
        if connected:details.append(f"<b>Kabler:</b> {connected}")
        room=self.room_for_placement(placement)
        if room is not None:details.append(f"<b>Rum:</b> {html.escape(core.room_display_text(room))}")
        return {
            "title":name+(f" · {ident}" if ident else ""),
            "subtitle":"Hurtigt overblik · klik for fulde egenskaber",
            "preview_mode":"symbol",
            "preview_data":{"symbol":symbol},
            "details_html":"<br>".join(details) if details else "<span style='color:#64748b'>Ingen ekstra mærkning eller kabeltilslutninger.</span>",
            "bom_html":bom,
        }

    def _quick_visible(self, key: str) -> bool:
        return bool(getattr(self,"quick_visibility",{}).get(str(key),True))

    def _quick_cable_visible(self, cable: core.CablePlacement) -> bool:
        """Hurtigfilter pr. kabelkategori uden at ændre projektets lagvalg."""
        if str(getattr(cable,"layer","") or "") == core.PATCH_CABLE_LAYER:
            return self._quick_visible("patch_cables")
        return self._quick_visible("cables")

    def _quick_visibility_changed(self,key: str,checked: bool) -> None:
        if not hasattr(self,"quick_visibility"):
            return
        self.quick_visibility[str(key)]=bool(checked)
        data=core.load_app_settings(); data[f"quick_show_{key}"]=bool(checked); core.save_app_settings(data); self.app_settings=data
        self._apply_quick_visibility()
        label={"cad":"plantegning","symbols":"symboler","cables":"kabler","patch_cables":"patchkabler","text":"tekst"}.get(str(key),str(key))
        self._set_status(f"Hurtig visning: {label} {'vist' if checked else 'skjult'} · Lag-panelets valg er uændrede.")

    def _quick_visibility_show_all(self) -> None:
        actions=(("cad",self.act_quick_cad),("symbols",self.act_quick_symbols),("cables",self.act_quick_cables),("patch_cables",self.act_quick_patch_cables),("text",self.act_quick_text))
        for key,action in actions:
            blocker=QSignalBlocker(action); action.setChecked(True); del blocker
            self.quick_visibility[key]=True
        data=core.load_app_settings()
        for key,_ in actions: data[f"quick_show_{key}"]=True
        core.save_app_settings(data); self.app_settings=data
        self._apply_quick_visibility(); self._set_status("Hurtig visning: alt vist.")

    def _apply_quick_visibility(self) -> None:
        cad_on=self._quick_visible("cad"); symbols_on=self._quick_visible("symbols"); text_on=self._quick_visible("text")
        for layer,item in getattr(self,"layer_items",{}).items():
            item.setVisible(cad_on and self.project.layer_visibility.get(layer,True))
        meta_on=text_on and self.project.layer_visibility.get(core.META_LAYER,True)
        for placement in self.project.placements:
            item=self.symbol_items.get(placement.uid)
            layer_on=self.project.layer_visibility.get(core.symbol_layer(placement.symbol),True)
            if item is not None: item.setVisible(symbols_on and layer_on)
            ann=self.annotation_items.get(placement.uid)
            if ann is not None: ann.setVisible(symbols_on and layer_on and meta_on)
        for cable in self.project.cables:
            item=self.cable_items.get(id(cable))
            if item is not None: item.setVisible(self._quick_cable_visible(cable) and self._cable_layer_visible(cable))
        for item in getattr(self,"text_items",{}).values():
            item.setVisible(text_on and self.project.layer_visibility.get(core.FREE_TEXT_LAYER,True))
        for badge in getattr(self,"switch_association_badges",{}).values() if isinstance(getattr(self,"switch_association_badges",{}),dict) else getattr(self,"switch_association_badges",[]):
            try: badge.setVisible(symbols_on and text_on)
            except Exception: pass
        if hasattr(self,"_rebuild_cable_visual_cache"):
            self._rebuild_cable_visual_cache(refresh_items=True)
        if hasattr(self,"_apply_cable_focus"): self._apply_cable_focus()
        self._refresh_room_visibility()

    def _sync_symbol_annotation_visibility(self) -> None:
        """Synkronisér symbol og mærkning med både symbollag og EL-TEKST."""
        meta_visible = self.project.layer_visibility.get(core.META_LAYER, True) and self._quick_visible("text")
        for placement in self.project.placements:
            item = self.symbol_items.get(placement.uid)
            if item is None:
                continue
            symbol_visible = self.project.layer_visibility.get(core.symbol_layer(placement.symbol), True) and self._quick_visible("symbols")
            item.setVisible(symbol_visible)
            annotation = self.annotation_items.get(placement.uid)
            if annotation is not None:
                annotation.setVisible(symbol_visible and meta_visible)

    def _cable_visual_points(self, cable: core.CablePlacement):
        return self._cable_visual_cache.get(id(cable), cable.points)

    def _clear_cable_bundle_badges(self) -> None:
        for item in list(getattr(self,"_cable_bundle_badges",[]) or []):
            try:
                if item.scene() is self.scene:
                    self.scene.removeItem(item)
            except Exception:
                pass
        self._cable_bundle_badges=[]

    def _rebuild_cable_bundle_badges(self) -> None:
        self._clear_cable_bundle_badges()
        if not hasattr(self,"cable_bundle_badges_enabled") or not self.cable_bundle_badges_enabled.isChecked():
            return
        for group in getattr(self,"_cable_parallel_groups",[]) or []:
            count=int(group.get("count",0) or 0)
            if count<3:
                continue
            try:
                x,y=map(float,group.get("point",(0.0,0.0)))
            except Exception:
                continue
            label=QGraphicsSimpleTextItem(f"×{count}")
            label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations,True)
            label.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            label.setBrush(QBrush(QColor("#f0a2a2") if _canvas_dark() else QColor("#8f1d1d")))
            label.setFont(QFont("Segoe UI",8,QFont.Weight.DemiBold))
            label.setZValue(78)
            pos=QPointF(x,-y)
            label.setPos(pos+QPointF(5,-16))
            ids=", ".join(str(v) for v in group.get("cable_ids",[]) if str(v).strip())
            label.setToolTip(f"{count} kabler deler denne rute"+(f": {ids}" if ids else ""))
            bg=QGraphicsRectItem(label.boundingRect().adjusted(-3,-1,3,1))
            bg.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations,True)
            bg.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            bg.setBrush(QBrush(QColor(42,48,55,235) if _canvas_dark() else QColor(255,255,255,235)))
            bg.setPen(QPen(QColor("#5a6673") if _canvas_dark() else QColor("#d8dee8")))
            bg.setZValue(77)
            bg.setPos(label.pos())
            bg.setToolTip(label.toolTip())
            self.scene.addItem(bg); self.scene.addItem(label)
            self._cable_bundle_badges.extend((bg,label))

    def _current_symbol_focus_uid(self) -> str:
        if not hasattr(self,"cable_focus_related") or not self.cable_focus_related.isChecked():
            return ""
        selected=[x for x in self.scene.selectedItems() if isinstance(x,ElectricalSymbolItem)]
        return str(selected[0].placement.uid) if len(selected)==1 else ""

    def _apply_cable_focus(self, symbol_uid: str | None=None) -> None:
        self._apply_visual_emphasis()

    def _cable_visual_settings_changed(self,*_args) -> None:
        if getattr(self,"_loading_cable_panel",False):
            return
        if not all(hasattr(self,n) for n in ("cable_parallel_lanes","cable_lane_gap_spin","cable_bundle_badges_enabled","cable_focus_related")):
            return
        data=core.load_app_settings()
        data["cable_parallel_lanes"]=bool(self.cable_parallel_lanes.isChecked())
        data["cable_lane_gap_px"]=int(self.cable_lane_gap_spin.value())
        data["cable_bundle_badges"]=bool(self.cable_bundle_badges_enabled.isChecked())
        data["cable_focus_related"]=bool(self.cable_focus_related.isChecked())
        if hasattr(self,"cable_snap_routes"):
            data["cable_snap_routes"]=bool(self.cable_snap_routes.isChecked())
        core.save_app_settings(data); self.app_settings=data
        self._rebuild_cable_visual_cache(refresh_items=True)
        self._apply_cable_focus()

    def _rebuild_cable_visual_cache(self, refresh_items: bool=False) -> None:
        """Build stable screen-space lanes for cables sharing one route.

        Lane spacing is cosmetic and never changes saved cable geometry, length
        or BOM.  A logical centreline is therefore safe to reuse for many cables.
        """
        connection_index=defaultdict(list)
        for cable in self.project.cables:
            for rec in core.cable_symbol_connections(cable):
                uid=str(rec.get("symbol_uid","") or "")
                if uid:connection_index[uid].append((cable,rec))
        self._cables_by_symbol_uid=dict(connection_index)
        try:
            scale=max(float(self.view.current_scale()),1e-9)
        except Exception:
            scale=1.0
        visible=[c for c in self.project.cables if self._quick_cable_visible(c) and self._cable_layer_visible(c)]
        lanes=not hasattr(self,"cable_parallel_lanes") or self.cable_parallel_lanes.isChecked()
        gap_px=int(self.cable_lane_gap_spin.value()) if hasattr(self,"cable_lane_gap_spin") else 10
        gap_world=(float(gap_px)/scale) if lanes else 0.0
        paths,meta,groups=core.cable_visual_layout(visible,gap_world,fan_length=max(18.0,float(gap_px)*2.1)/scale)
        self._cable_visual_cache=paths
        self._cable_visual_meta=meta
        self._cable_parallel_groups=groups
        for c in self.project.cables:
            self._cable_visual_cache.setdefault(id(c),[(float(x),float(y)) for x,y in c.points])
            self._cable_visual_meta.setdefault(id(c),{"lane_index":0,"lane_count":1,"max_parallel":1,"peer_ids":[]})
        self._cable_visual_cache_scale=scale
        for cable in self.project.cables:
            item=self.cable_items.get(id(cable))
            if item is None:
                continue
            # Push the exact calculated path into the graphics item.  The item
            # no longer has to rediscover its lane through an indirect cache
            # lookup during refresh, which was the missing link seen in the
            # user's real G01/K01 project.
            item.set_visual_points(self._cable_visual_cache.get(id(cable),cable.points),refresh=False)
            meta=self._cable_visual_meta.get(id(cable),{})
            count=max(1,int(meta.get("lane_count",1) or 1))
            base=f"{str(cable.cable_id or 'Kabel')} · {str(cable.cable_spec or '—')}"
            if count>1:
                peers=", ".join(str(v) for v in meta.get("peer_ids",[]) if str(v).strip())
                base+=f"\nParallel rute: bane {int(meta.get('lane_index',0))+1}/{count}"
                if peers: base+=f"\nFælles med: {peers}"
            item.setToolTip("")
        if refresh_items:
            for item in self.cable_items.values():
                item.refresh()
        self._rebuild_cable_bundle_badges()
        self._apply_cable_focus()

    def _snap_cable_vertex(self, item: CableItem, index: int, raw_cad):
        x,y=map(float,raw_cad)
        kind=""; uid=""; port=0
        endpoint=index in (0,len(item.cable.points)-1)
        # Endpoint attachment to a symbol/wall has priority over cosmetic alignment.
        if endpoint and self.snap_engine is not None:
            x,y,kind,uid,port=self.snap_engine.snap_connection(
                self.scene,(x,y),self.view.current_scale(),
                snap_symbols=self.cable_snap_symbols.isChecked() if hasattr(self,"cable_snap_symbols") else True,
                snap_walls=self.cable_snap_walls.isChecked() if hasattr(self,"cable_snap_walls") else True,
            )
        if not kind and hasattr(self,"cable_snap_routes") and self.cable_snap_routes.isChecked():
            route=self.view.snap_to_existing_cable_route(x,y,active_item=item,tolerance_px=13.0)
            if route is not None:
                x,y=float(route[0]),float(route[1]); kind="KABELRUTE"
        if not kind:
            x,y,align_kind=self.view._cable_alignment_snap(item,index,x,y)
            kind=align_kind
        else:
            self.view._clear_alignment_guides()
        self.view._show_snap_feedback(QPointF(x,-y),kind)
        return x,y,uid,port,kind

    def _cable_handle_edit_started(self, item: CableItem, _before: dict) -> None:
        self.view.begin_cable_interaction_snapshot(item)

    def _cable_handle_edit_finished(self, item: CableItem, before: dict, after: dict) -> None:
        self.view.end_cable_interaction_snapshot()
        self.view._clear_snap_feedback()
        # Sikkerhedsnet oven på de låste handles: en fysisk forbindelse skal altid
        # ende præcis i symbolporten, også hvis et ældre projekt allerede var skævt.
        if self._anchor_cable_connections(item.cable):
            item.refresh(update_handles=True)
            after=CableItem.state(item.cable)
        if before!=after:
            self.undo_stack.push(EditCableCommand(self,item.cable,before,after,"Redigér kabelgeometri",already_applied=True))
            self._rebuild_cable_visual_cache(refresh_items=True)
        self._load_selected_cable_into_panel(item.cable)

    def _cable_insert_breakpoint(self, item: CableItem, scene_pos: QPointF) -> None:
        before=CableItem.state(item.cable)
        if item.insert_breakpoint(scene_pos):
            after=CableItem.state(item.cable)
            self.undo_stack.push(EditCableCommand(self,item.cable,before,after,"Tilføj kabelknæk",already_applied=True))
            self._rebuild_cable_visual_cache(refresh_items=True)
            self._load_selected_cable_into_panel(item.cable)

    def _cable_selected(self, item: CableItem) -> None:
        self.selected_cable=item.cable
        self._load_selected_cable_into_panel(item.cable)
        self._update_inspector_summary(cable=item.cable)
        self._apply_visual_emphasis()
        title = core.cable_display_label(item.cable) or item.cable.cable_id or "Kabel"
        self._show_inspector_page("cable", title=title, hint="Redigér kabeldata, kategori eller ruteføring. Kabeltegning startes separat med Kabel-værktøjet.")
        self._refresh_context_toolbar()

    def _snap_moving_symbol(self, item: ElectricalSymbolItem, proposed_scene: QPointF):
        if self._group_drag_blocked and item.placement.uid == self._group_drag_anchor_uid:
            old=self._group_drag_before.get(item.placement.uid)
            if old is not None:
                marker=QPointF(float(old[0]),-float(old[1]))
                self.view._show_snap_feedback(marker,"SPOTGRUPPE LÅST")
                return marker,float(old[2]),"SPOTGRUPPE LÅST"
        if self.snap_engine is None:
            return proposed_scene, item.placement.rotation, ""
        raw = (float(proposed_scene.x()), float(-proposed_scene.y()))
        cursor = (float(self.view.last_mouse_scene.x()), float(-self.view.last_mouse_scene.y()))
        (x, y), rot, kind = self.snap_engine.snap_pose(self.scene, item.placement.symbol, item.placement.size,
                                                       item.placement.rotation, raw, self.view.current_scale(),
                                                       ignore_uid=item.placement.uid, cursor_cad=cursor)
        ignore_group = set(self._group_drag_before) if self._group_drag_before else {item.placement.uid}
        x, y, align_kind = self.view._lighting_alignment_snap(item.placement.symbol, x, y, item.placement.uid, ignore_group)
        if align_kind:
            kind = " + ".join(dict.fromkeys([part for part in (kind.split(" + ") if kind else []) + align_kind.split(" + ") if part]))
        mounts = core.symbol_mount_points(item.placement.symbol, item.placement.size)
        if kind and mounts:
            lx, ly = core.rotate_point(mounts[0][0], mounts[0][1], rot)
            marker = QPointF(x+lx, -(y+ly))
        else:
            marker = QPointF(x, -y)
        self.view._show_snap_feedback(marker, kind)
        return QPointF(x, -y), rot, kind

    def _placement_requested(self, code: str, x: float, y: float, rotation: float) -> None:
        # A single spot uses the dedicated spot size control, just like spot rows/rectangles.
        size=float(self.spot_size_quick.value()) if code=="spot" and hasattr(self,"spot_size_quick") else float(self.palette_size.value())
        placement = core.Placement(symbol=code, x=x, y=y, rotation=rotation,
                                   size=size, line_width=0.25, color=core.DEFAULT_SYMBOL_COLOR)
        self.undo_stack.push(AddSymbolCommand(self, placement, f"Placér {core.symbol_display_name(code)}"))
        preview=getattr(self.view,"_preview_item",None)
        if preview is not None and code in core.LIGHT_ASSOCIATION_SYMBOLS:
            # Consecutive placements should snap to the symbol just added while
            # still excluding the translucent preview itself.
            self.view.begin_lighting_alignment_snapshot({preview.placement.uid})
        if code=="spot":
            self.project.raw["spot_default_size"]=size
            self.last_individual_spot_uid=placement.uid
            # Selecting the freshly placed spot exposes Spot → lampested immediately.
            # The placement preview remains active, so the user may either continue
            # placing spots or click “Tilknyt lampested…” in Egenskaber.
            self.scene.clearSelection()
            item=self.symbol_items.get(placement.uid)
            if item is not None:
                item.setSelected(True)
            self._set_status("Spot placeret og valgt · vælg ‘Tilknyt lampested…’ i Egenskaber, eller placér næste spot · Esc afslutter")

    def _add_placement(self, placement: core.Placement, index: int | None = None) -> None:
        if any(p.uid == placement.uid for p in self.project.placements):
            return
        if index is None or index < 0 or index > len(self.project.placements):
            self.project.placements.append(placement)
        else:
            self.project.placements.insert(index, placement)
        item = ElectricalSymbolItem(placement)
        self._wire_symbol_item(item)
        layer = core.symbol_layer(placement.symbol)
        visible = self.project.layer_visibility.get(layer, True)
        item.setVisible(visible)
        self.scene.addItem(item)
        self.symbol_items[placement.uid] = item
        self.generated_layer_items[layer].append(item)
        annotation = AnnotationItem(placement, self.edit_annotation_direct, item, self.view.current_scale, lambda: self.annotation_display_mode, self._spot_parent_label, self._annotation_room_direction)
        annotation.setVisible(visible and self.project.layer_visibility.get(core.META_LAYER, True))
        self.scene.addItem(annotation)
        self.annotation_items[placement.uid] = annotation
        self.generated_layer_items[core.META_LAYER].append(annotation)
        self._refresh_switch_association_badges()
        self.project.dirty = True
        self._update_title()
        self._rebuild_layer_list()

    def _remove_placement(self, uid: str) -> None:
        item = self.symbol_items.pop(uid, None)
        placement = next((p for p in self.project.placements if p.uid == uid), None)
        if placement is None:
            return
        self.project.placements = [p for p in self.project.placements if p.uid != uid]
        if item is not None:
            layer = core.symbol_layer(placement.symbol)
            if item in self.generated_layer_items.get(layer, []): self.generated_layer_items[layer].remove(item)
            if item.scene() is not None: self.scene.removeItem(item)
        ann = self.annotation_items.pop(uid, None)
        if ann is not None:
            if ann in self.generated_layer_items.get(core.META_LAYER, []): self.generated_layer_items[core.META_LAYER].remove(ann)
            if ann.scene() is not None: self.scene.removeItem(ann)
        self._refresh_switch_association_badges()
        self.project.dirty = True
        self._update_title()

    def _symbol_reference_snapshot(self) -> dict:
        """Capture relations that can point at a symbol before it is deleted."""
        return {
            "associations": self._association_snapshot(),
            "spot_parents": self._spot_parent_snapshot(),
            "cables": [
                (
                    cable,
                    str(getattr(cable, "start_symbol_uid", "") or ""),
                    int(getattr(cable, "start_symbol_port", 0) or 0),
                    str(getattr(cable, "end_symbol_uid", "") or ""),
                    int(getattr(cable, "end_symbol_port", 0) or 0),
                    deepcopy(core.cable_symbol_connections(cable)),
                )
                for cable in self.project.cables
            ],
        }

    def _cleanup_after_symbol_removed(self, uid: str) -> None:
        """Remove dangling cable/spot references and orphan a/b/c relations."""
        for cable in self.project.cables:
            rows=[dict(r) for r in core.cable_symbol_connections(cable) if str(r.get("symbol_uid","") or "") != uid]
            core.set_cable_symbol_connections(cable,rows)
        for placement in self.project.placements:
            if str(getattr(placement, "parent_light_uid", "") or "") == uid:
                placement.parent_light_uid = ""
                placement.parent_light_output_id = ""
                placement.associations = []
        self._cleanup_orphan_associations()
        self._rebuild_cable_visual_cache(refresh_items=True)
        for ann in self.annotation_items.values():
            ann.refresh()
        self._refresh_switch_association_badges()

    def _restore_symbol_reference_snapshot(self, state: dict) -> None:
        self._apply_association_state(state.get("associations", {}))
        self._apply_spot_parent_state(state.get("spot_parents", {}))
        for cable_state in state.get("cables", []):
            if len(cable_state) < 5:
                continue
            cable, start_uid, start_port, end_uid, end_port = cable_state[:5]
            if cable not in self.project.cables:
                continue
            if len(cable_state) >= 6:
                core.set_cable_symbol_connections(cable,deepcopy(cable_state[5]))
            else:
                cable.start_symbol_uid = start_uid; cable.start_symbol_port = start_port
                cable.end_symbol_uid = end_uid; cable.end_symbol_port = end_port
                core.set_cable_symbol_connections(cable,core.cable_symbol_connections(cable))
            item = self.cable_items.get(id(cable))
            if item is not None:
                item.refresh()
        self._rebuild_cable_visual_cache(refresh_items=True)

    def _set_symbol_pose(self, uid: str, pose) -> None:
        item = self.symbol_items.get(uid)
        if item is None:
            return
        x, y, rot = pose
        item.set_pose_silent(x, y, rot)
        ann = self.annotation_items.get(uid)
        if ann: ann.refresh()
        self._refresh_switch_association_badges()
        self._refresh_connected_cables(uid)
        self.project.dirty = True
        self._update_title()

    def _symbol_drag_started(self, item, old_pose) -> None:
        self._symbol_drag_active=True
        self._selection_refresh_timer.stop()
        self._symbol_drag_visual_timer.stop()
        self._symbol_drag_visual_uids.clear()
        self._symbol_drag_cables={}
        self._symbol_drag_cables_changed=False
        selected=[x for x in self.scene.selectedItems() if isinstance(x,ElectricalSymbolItem) and not x.placement.locked]
        if item not in selected:
            selected=[item]

        # 0.59.57: A spotgruppe behaves as one physical layout unit while it is
        # moved.  Expand every selected grouped spot to all members before the
        # drag snapshot is created; the existing multi-symbol drag path then
        # preserves the group's internal geometry and gives us one undo macro.
        expanded={x.placement.uid:x for x in selected}
        grouped_members=[]
        for selected_item in list(selected):
            p=selected_item.placement
            if p.symbol!="spot":
                continue
            gid=str(getattr(p,"spot_group_id","") or "").strip()
            if not gid:
                continue
            for member in self._spot_group_members(gid):
                grouped_members.append(member)
                member_item=self.symbol_items.get(member.uid)
                if member_item is not None:
                    expanded[member.uid]=member_item

        self._group_drag_anchor_uid=item.placement.uid
        self._group_drag_blocked=any(bool(getattr(p,"locked",False)) for p in grouped_members)
        if self._group_drag_blocked:
            # Never split a logical group because one member is locked.  The
            # snapper keeps the anchor at its original pose for this gesture.
            members={p.uid:p for p in grouped_members}
            members[item.placement.uid]=item.placement
            self._group_drag_before={uid:(float(p.x),float(p.y),float(p.rotation)) for uid,p in members.items()}
            self._set_status("Spotgruppen indeholder låste spots · lås hele gruppen op før den flyttes")
            return

        self._group_drag_before={x.placement.uid:(float(x.placement.x),float(x.placement.y),float(x.placement.rotation)) for x in expanded.values()}
        drag_uids=set(self._group_drag_before)
        self._symbol_drag_cables={}
        # The cable connection index is rebuilt whenever cable geometry/data
        # changes. Starting a drag is therefore O(connected cables), not a scan
        # of every cable and every connection in the project.
        for uid in drag_uids:
            seen=set(); connected=[]
            for cable,_rec in self._cables_by_symbol_uid.get(uid,[]):
                if id(cable) in seen:continue
                seen.add(id(cable)); connected.append(cable)
            self._symbol_drag_cables[uid]=connected
        self.view.begin_lighting_alignment_snapshot(drag_uids)
        self._clear_spot_link_visuals(); self._clear_relation_overview()

    def _symbol_drag_finished(self, item: ElectricalSymbolItem, old_pose, new_pose) -> None:
        self._symbol_drag_visual_timer.stop()
        self._flush_symbol_drag_visuals()
        self.view.end_lighting_alignment_snapshot()
        self.view._clear_snap_feedback()
        if self.snap_engine is not None:
            self.snap_engine.clear_wall_lock(item.placement.uid)
        before=dict(self._group_drag_before)
        blocked=bool(self._group_drag_blocked)
        self._group_drag_before={}; self._group_drag_anchor_uid=""; self._group_drag_blocked=False
        if blocked:
            self._symbol_drag_cables={}; self._symbol_drag_cables_changed=False
            return
        if not before:
            before={item.placement.uid:tuple(old_pose)}
        changed=[]
        for uid,old in before.items():
            current=self.symbol_items.get(uid)
            if current is None: continue
            now=(float(current.placement.x),float(current.placement.y),float(current.placement.rotation))
            if tuple(round(v,8) for v in old)!=tuple(round(v,8) for v in now):
                changed.append((uid,old,now))
        if not changed:
            self._symbol_drag_cables={}; self._symbol_drag_cables_changed=False
            return
        if self._symbol_drag_cables_changed:
            self._rebuild_cable_visual_cache(refresh_items=True)
            if self.selected_cable is not None:
                self._load_selected_cable_into_panel(self.selected_cable)
        self._symbol_drag_cables={}; self._symbol_drag_cables_changed=False
        for uid,_old,_now in changed:
            annotation=self.annotation_items.get(uid)
            if annotation is not None:annotation.reposition()
        self._symbol_metadata_refresh_timer.start()
        selected=self._selected_symbol_item()
        if selected is not None:
            self._refresh_spot_link_visuals(selected.placement)
            self._refresh_relation_overview(selected.placement)
        self.project.dirty=True; self._update_title()
        self.undo_stack.beginMacro("Flyt symboler" if len(changed)>1 else "Flyt symbol")
        try:
            for uid,old,now in changed:
                self.undo_stack.push(MoveSymbolCommand(self,uid,old,now,already_applied=True))
        finally:
            self.undo_stack.endMacro()

    def delete_selected_symbols(self) -> None:
        selected_symbol_items=[x for x in self.scene.selectedItems() if isinstance(x,ElectricalSymbolItem)]
        locked_symbols=[x for x in selected_symbol_items if x.placement.locked]
        symbols=[x for x in selected_symbol_items if not x.placement.locked]
        texts=[x for x in self.scene.selectedItems() if isinstance(x,FreeTextItem)]
        cables=[x for x in self.scene.selectedItems() if isinstance(x,CableItem)]
        rooms=self._selected_rooms_from_scene()
        if not symbols and not texts and not cables and not rooms:
            if locked_symbols:
                QMessageBox.information(
                    self,"Symbolet er låst",
                    "Det valgte symbol kan ikke slettes, mens det er låst.\n\n"
                    "Fjern markeringen 'Lås placering og fysisk redigering' i Egenskaber, "
                    "vælg 'Anvend ændringer', og slet derefter symbolet."
                )
            return
        # Removing several selected graphics items normally emits one expensive
        # selectionChanged event per item. Keep the operation atomic and update
        # the inspector once when the undo macro is complete.
        selection_blocker=QSignalBlocker(self.scene)
        self.undo_stack.beginMacro("Slet valgte objekter")
        try:
            for item in symbols:
                try:index=self.project.placements.index(item.placement)
                except ValueError:index=len(self.project.placements)
                self.undo_stack.push(DeleteSymbolCommand(self,item.placement,index))
            for item in texts:
                try:index=self.project.texts.index(item.source)
                except ValueError:index=len(self.project.texts)
                self.undo_stack.push(DeleteTextCommand(self,item.source,index))
            for item in cables:
                try:index=self.project.cables.index(item.cable)
                except ValueError:index=len(self.project.cables)
                self.undo_stack.push(DeleteCableCommand(self,item.cable,index))
            for room in rooms:
                try:index=self.project.rooms.index(room)
                except ValueError:index=len(self.project.rooms)
                self.undo_stack.push(DeleteRoomCommand(self,room,index))
        finally:
            self.undo_stack.endMacro()
            del selection_blocker
        self._selection_changed()
        if locked_symbols:
            self._notify(f"{len(locked_symbols)} låst symbol blev ikke slettet.",kind="warning")

    def _next_cable_id(self, prefix: str = "K") -> str:
        used = set()
        for c in self.project.cables:
            cid = str(getattr(c, "cable_id", "") or "")
            if cid.startswith(prefix) and cid[len(prefix):].isdigit():
                used.add(int(cid[len(prefix):]))
        n = 1
        while n in used:
            n += 1
        return f"{prefix}{n:02d}"

    def _allocate_cable_ids(self, count: int, first_id: str = "", prefix: str = "K") -> list[str]:
        """Allocate unique visible IDs for one user-drawn physical cable chain."""
        count=max(0,int(count or 0))
        if count<=0:return []
        used={str(getattr(c,"cable_id","") or "").strip() for c in self.project.cables if str(getattr(c,"cable_id","") or "").strip()}
        first=str(first_id or "").strip() or self._next_cable_id(prefix)
        out=[]
        match=re.match(r"^(.*?)(\d+)$",first)
        if match:
            stem=match.group(1); width=len(match.group(2)); number=int(match.group(2))
            candidate=first
            while len(out)<count:
                while candidate in used:
                    number+=1; candidate=f"{stem}{number:0{width}d}"
                out.append(candidate); used.add(candidate)
                number+=1; candidate=f"{stem}{number:0{width}d}"
        else:
            candidate=first; suffix=1
            while len(out)<count:
                if candidate not in used:
                    out.append(candidate); used.add(candidate)
                suffix+=1; candidate=f"{first}-{suffix}"
        return out

    def _annotation_visual_centroid(self, placement: core.Placement) -> tuple[float,float]:
        """Approximate the symbol's visual direction from its local vector geometry."""
        pts=[]
        try:
            for prim in core.symbol_primitives(placement.symbol,placement.size):
                kind=prim[0]
                if kind=="line":
                    pts.extend(((float(prim[1]),float(prim[2])),(float(prim[3]),float(prim[4]))))
                elif kind in ("circle","arc"):
                    pts.append((float(prim[1]),float(prim[2])))
                elif kind=="polyline":
                    pts.extend((float(x),float(y)) for x,y in prim[1])
                elif kind in {"text","upright_text"}:
                    pts.append((float(prim[1]),float(prim[2])))
        except Exception:
            return (0.0,0.0)
        if not pts:
            return (0.0,0.0)
        cx=sum(x for x,_ in pts)/len(pts)
        cy=sum(y for _,y in pts)/len(pts)
        try:
            return core.rotate_point(cx,cy,float(placement.rotation))
        except Exception:
            return (cx,cy)

    def _annotation_room_direction(self, placement: core.Placement) -> tuple[float,float]:
        """Return a preferred direction in *scene coordinates* for the annotation.

        Priority:
        1. If the symbol centre is visibly on one side of a nearby wall, place
           the annotation on the same side (inside the room containing it).
        2. For offset wall mount-points (socket/combo), use the vector from the
           physical wall mount point toward the symbol body.
        3. Use the asymmetric visual direction of the symbol (useful for switches).
        4. Fall back to the side with more free CAD space.
        """
        if not self.annotation_room_placement:
            return (1.0,0.0)
        # Explicitly sketched rooms are authoritative. Fall back to the historical
        # wall heuristic only when no room polygon owns the symbol.
        real_room_direction=self._room_annotation_direction(placement)
        if real_room_direction is not None:
            return (real_room_direction[0],-real_room_direction[1])
        px=float(placement.x); py=float(placement.y)
        size=max(float(placement.size),1.0)
        wall=None
        if self.snap_engine is not None:
            try:
                wall=self.snap_engine.nearest_wall(px,py,max(size*1.35,180.0))
            except Exception:
                wall=None

        # Physical mounting point -> symbol body is usually the room direction
        # for sockets and combination symbols.
        mounts=core.placement_mount_points(placement)
        if mounts:
            mx,my=min(mounts,key=lambda q:math.hypot(q[0]-px,q[1]-py))
            dx=px-mx; dy=py-my
            length=math.hypot(dx,dy)
            if length>size*.12:
                return (dx/length,-dy/length)

        visual=self._annotation_visual_centroid(placement)
        vlen=math.hypot(*visual)

        if wall is not None:
            wx,wy,angle=wall[0],wall[1],float(wall[2])
            # If symbol centre is not directly on the wall, that side is the
            # strongest indication of which room owns the symbol.
            dx=px-wx; dy=py-wy
            dist=math.hypot(dx,dy)
            if dist>size*.06:
                return (dx/dist,-dy/dist)

            # Otherwise choose one of the wall normals. Align it with the
            # symbol's asymmetric geometry when possible.
            a=math.radians(angle)
            n1=(-math.sin(a), math.cos(a))
            n2=(-n1[0],-n1[1])
            if vlen>size*.045:
                normal=n1 if (visual[0]*n1[0]+visual[1]*n1[1]) >= (visual[0]*n2[0]+visual[1]*n2[1]) else n2
                return (normal[0],-normal[1])

            # Last wall fallback: choose the side with fewer nearby CAD
            # segments, which normally means the open room rather than the wall.
            def density(normal):
                score=0.0
                for distance in (size*.55,size*.9,size*1.3):
                    sx=px+normal[0]*distance
                    sy=py+normal[1]*distance
                    try:
                        hit=self.snap_engine.nearest_wall(sx,sy,size*.22)
                    except Exception:
                        hit=None
                    if hit is not None:
                        score+=1.0
                return score
            normal=n1 if density(n1)<=density(n2) else n2
            return (normal[0],-normal[1])

        if vlen>size*.045:
            return (visual[0]/vlen,-visual[1]/vlen)

        return (1.0,0.0)

    def _lighting_alignment_snap_changed(self, checked: bool) -> None:
        self.lighting_alignment_snap = bool(checked)
        self.view.set_lighting_alignment_enabled(self.lighting_alignment_snap)
        data = core.load_app_settings()
        data["lighting_alignment_snap"] = self.lighting_alignment_snap
        core.save_app_settings(data)
        self.app_settings = data
        self._set_status(
            "Lys-snap: hjælpelinjer og magnetisk justering aktiv" if checked
            else "Lys-snap slået fra"
        )

    def _annotation_room_placement_changed(self, checked: bool) -> None:
        self.annotation_room_placement=bool(checked)
        data=core.load_app_settings()
        data["annotation_room_placement"]=self.annotation_room_placement
        core.save_app_settings(data)
        self.app_settings=data
        for ann in self.annotation_items.values():
            ann.refresh()
        self._refresh_switch_association_badges()
        self._set_status(
            "Mærkning placeres automatisk på rumside" if checked
            else "Automatisk rumsideplacering er slået fra"
        )

    def _set_annotation_mode(self, mode: str, *, status: bool = True) -> None:
        mode=str(mode)
        if mode not in ("Auto","Tydelig","Minimal","Skjult"):
            mode="Auto"
        self.annotation_display_mode=mode
        if mode != "Skjult":
            self.annotation_last_visible_mode=mode
        data=core.load_app_settings()
        data["annotation_display_mode"]=mode
        data["annotation_last_visible_mode"]=self.annotation_last_visible_mode
        core.save_app_settings(data)
        self.app_settings=data

        if hasattr(self,"annotation_mode_combo") and self.annotation_mode_combo.currentText()!=mode:
            blocker=QSignalBlocker(self.annotation_mode_combo)
            self.annotation_mode_combo.setCurrentText(mode)
            del blocker
        if hasattr(self,"act_annotations") and self.act_annotations.isChecked()!=(mode!="Skjult"):
            blocker=QSignalBlocker(self.act_annotations)
            self.act_annotations.setChecked(mode!="Skjult")
            del blocker
        for ann in self.annotation_items.values():
            ann.refresh()
        self._refresh_switch_association_badges()
        selected=self._selected_symbol_item() if hasattr(self,"scene") else None
        if mode=="Skjult":
            self._clear_relation_overview()
            self._clear_spot_link_visuals()
        elif selected is not None:
            self._refresh_spot_link_visuals(selected.placement)
            self._refresh_relation_overview(selected.placement)
        if status:
            self._set_status("Al mærkning og normal tilhørsvisning skjult" if mode=="Skjult" else f"Mærkningsvisning: {mode}")

    def _annotation_mode_changed(self, mode: str) -> None:
        self._set_annotation_mode(mode)

    def _toggle_annotations(self, checked: bool) -> None:
        if checked:
            self._set_annotation_mode(self.annotation_last_visible_mode or "Auto")
        else:
            self._set_annotation_mode("Skjult")

    def _print_cad_dimming_changed(self, checked: bool) -> None:
        self.print_cad_dimming=bool(checked)
        if hasattr(self,"print_cad_dimming_check") and self.print_cad_dimming_check.isChecked()!=self.print_cad_dimming:
            blocker=QSignalBlocker(self.print_cad_dimming_check)
            self.print_cad_dimming_check.setChecked(self.print_cad_dimming)
            del blocker
        data=core.load_app_settings()
        data["print_cad_dimming"]=self.print_cad_dimming
        core.save_app_settings(data)
        self.app_settings=data
        state="aktiv" if self.print_cad_dimming else "fra"
        self._set_status(f"Dæmpning i PDF/udskrift: {state}")

    def _output_cad_opacity(self) -> float:
        return self.cad_background_opacity if self.print_cad_dimming else 1.0

    def _toggle_elplan_focus(self, checked: bool) -> None:
        target = 55 if checked else 100
        if hasattr(self,"cad_opacity_slider"):
            blocker=QSignalBlocker(self.cad_opacity_slider)
            self.cad_opacity_slider.setValue(target)
            del blocker
        self._cad_opacity_changed(target)

    def _cad_opacity_changed(self, value: int) -> None:
        value=max(20,min(100,int(value)))
        self.cad_background_opacity=value/100.0
        if hasattr(self,"cad_opacity_value"):
            self.cad_opacity_value.setText(f"{value}%")
        if hasattr(self,"act_focus_elplan"):
            blocker=QSignalBlocker(self.act_focus_elplan)
            self.act_focus_elplan.setChecked(value < 95)
            del blocker
        for item in self.layer_items.values():
            item.setOpacity(self.cad_background_opacity)
        data=core.load_app_settings()
        data["cad_background_opacity"]=self.cad_background_opacity
        core.save_app_settings(data)
        self.app_settings=data
        self._set_status(
            f"Plantegningens tydelighed: {value}% · el-symboler, mærkning og kabler forbliver 100%"
        )

    @staticmethod
    def _fixed_length_units() -> dict[str, tuple[str, float]]:
        return {
            "mm": ("millimeter", 0.001),
            "cm": ("centimeter", 0.01),
            "m": ("meter", 1.0),
            "in": ("tommer", 0.0254),
            "ft": ("fod", 0.3048),
        }

    def _length_reserve_percent(self) -> float:
        try:
            return max(0.0, float(self.project.raw.get("cable_length_reserve_percent", 10.0)))
        except Exception:
            return 10.0

    def _length_scale_info(self) -> tuple[float | None, str]:
        """Return metres/drawing-unit and a short source description."""
        mode = str(self.project.raw.get("cable_length_unit_mode", "auto") or "auto")
        fixed = self._fixed_length_units()
        if mode in fixed:
            label, factor = fixed[mode]
            return factor, f"{label} (projekt)"
        if mode == "calibrated":
            try:
                factor = float(self.project.raw.get("cable_length_m_per_unit", 0.0) or 0.0)
            except Exception:
                factor = 0.0
            if factor > 0:
                return factor, "kalibreret på tegningen"
            return None, "kalibrering mangler"
        if self.doc is not None:
            _code, unit_label, factor = core.drawing_unit_info(self.doc)
            if factor is not None:
                return float(factor), f"{unit_label} (fra DWG/DXF)"
            return None, "$INSUNITS er ikke angivet"
        return None, "ingen tegning indlæst"

    @staticmethod
    def _fmt_metres(value: float | None) -> str:
        if value is None:
            return "—"
        return (f"{float(value):.2f}".replace(".", ",") + " m")

    def _points_length_metres(self, points) -> float | None:
        factor, _source = self._length_scale_info()
        if factor is None:
            return None
        return core.polyline_length(points) * factor

    def _refresh_cable_length_ui(self, points=None) -> None:
        if not hasattr(self, "cable_length_scale_label"):
            return
        factor, source = self._length_scale_info()
        reserve = self._length_reserve_percent()
        if factor is None:
            self.cable_length_scale_label.setText(f"Skala: mangler · {source} · reserve {reserve:g}%")
        else:
            self.cable_length_scale_label.setText(f"Skala: {source} · reserve {reserve:g}%")

        # ``points`` is supplied while a new cable string is being drawn. A
        # selected persisted cable is one physical piece; its route_chain_uid
        # identifies all pieces from the same cable pull.
        preview = points is not None
        cable = None if preview else self.selected_cable
        local_points = points if preview else (cable.points if cable is not None else None)
        base = self._points_length_metres(local_points) if local_points else None
        estimate = None if base is None else base * (1.0 + reserve / 100.0)

        if preview:
            if local_points and base is None:
                self.cable_live_length_label.setText("Aktuelt kabeltræk: skala mangler")
            elif base is not None:
                self.cable_live_length_label.setText(
                    f"Aktuelt kabeltræk: {self._fmt_metres(base)} · inkl. reserve: {self._fmt_metres(estimate)}"
                )
            else:
                self.cable_live_length_label.setText("Aktuelt kabeltræk: —")
            if hasattr(self, "cable_chain_length_label"):
                self.cable_chain_length_label.setVisible(False)
            if hasattr(self,"cable_chain_summary_label"):
                self.cable_chain_summary_label.setVisible(False)
            return

        if cable is not None:
            if base is None:
                self.cable_live_length_label.setText("Markeret kabelstykke: skala mangler" if local_points else "Markeret kabelstykke: —")
            else:
                self.cable_live_length_label.setText(
                    f"Markeret kabelstykke: {self._fmt_metres(base)} · inkl. reserve: {self._fmt_metres(estimate)}"
                )

            members = core.cable_route_chain_members(cable, self.project.cables)
            chain_base = core.cable_route_chain_length_metres(cable, self.project.cables, factor)
            chain_est = core.cable_route_chain_estimated_length_metres(
                cable, self.project.cables, factor, reserve
            )
            count = len(members)
            piece_word = "kabelstykke" if count == 1 else "kabelstykker"
            if chain_base is None:
                chain_text=f"Hele kabeltrækket ({count} {piece_word}): skala mangler"
                chain_summary=chain_text
            else:
                chain_text=(
                    f"Hele kabeltrækket ({count} {piece_word}): {self._fmt_metres(chain_base)} · "
                    f"inkl. reserve: {self._fmt_metres(chain_est)}"
                )
                chain_summary=(
                    f"Hele kabeltrækket · {self._fmt_metres(chain_base)}"
                    f"  |  inkl. reserve {self._fmt_metres(chain_est)}"
                    + (f"  |  {count} kabelstykker" if count>1 else "")
                )
            if hasattr(self, "cable_chain_length_label"):
                self.cable_chain_length_label.setVisible(True)
                self.cable_chain_length_label.setText(chain_text)
            if hasattr(self,"cable_chain_summary_label"):
                self.cable_chain_summary_label.setText(chain_summary)
                self.cable_chain_summary_label.setVisible(True)
            return

        self.cable_live_length_label.setText("Markeret kabelstykke: —")
        if hasattr(self, "cable_chain_length_label"):
            self.cable_chain_length_label.setVisible(True)
            self.cable_chain_length_label.setText("Hele kabeltrækket: —")
        if hasattr(self,"cable_chain_summary_label"):
            self.cable_chain_summary_label.setVisible(False)

    def _cable_preview_changed(self, points) -> None:
        if getattr(self.view, "_cable_active", False) and points:
            self._refresh_cable_length_ui(points)
        elif self.selected_cable is not None:
            self._refresh_cable_length_ui(self.selected_cable.points)
        else:
            self._refresh_cable_length_ui()
        self._update_cable_tool_status()

    def show_cable_length_settings(self) -> None:
        if self.doc is None:
            QMessageBox.information(self, "Kabellængder", "Åbn først en DWG/DXF eller et projekt.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Kabellængder · skala og reserve")
        dialog.setMinimumWidth(470)
        root = QVBoxLayout(dialog)

        _code, detected_label, detected_factor = core.drawing_unit_info(self.doc)
        detected = QLabel(
            f"DWG/DXF-enhed: {detected_label}" +
            ("" if detected_factor is not None else " · ingen sikker metrisk skala registreret")
        )
        detected.setWordWrap(True)
        detected.setObjectName("subtleText")
        root.addWidget(detected)

        form = QFormLayout()
        unit_combo = QComboBox()
        unit_combo.addItem("Automatisk fra DWG/DXF", "auto")
        unit_combo.addItem("Millimeter (mm)", "mm")
        unit_combo.addItem("Centimeter (cm)", "cm")
        unit_combo.addItem("Meter (m)", "m")
        unit_combo.addItem("Tommer (in)", "in")
        unit_combo.addItem("Fod (ft)", "ft")
        try:
            calibrated_factor = float(self.project.raw.get("cable_length_m_per_unit", 0.0) or 0.0)
        except Exception:
            calibrated_factor = 0.0
        if calibrated_factor > 0:
            unit_combo.addItem("Kalibreret på tegningen", "calibrated")
        current_mode = str(self.project.raw.get("cable_length_unit_mode", "auto") or "auto")
        idx = unit_combo.findData(current_mode)
        unit_combo.setCurrentIndex(idx if idx >= 0 else 0)

        reserve = QDoubleSpinBox()
        reserve.setRange(0.0, 200.0); reserve.setDecimals(1); reserve.setSingleStep(1.0); reserve.setSuffix(" %")
        reserve.setValue(self._length_reserve_percent())
        form.addRow("Tegningsenhed", unit_combo)
        form.addRow("Global reserve", reserve)
        root.addLayout(form)

        hint = QLabel("Kalibrering: klik to punkter med en kendt afstand på plantegningen og indtast derefter den virkelige længde i meter.")
        hint.setWordWrap(True); hint.setObjectName("subtleText")
        root.addWidget(hint)
        calibrate = _set_role(QPushButton("Kalibrer på tegningen…"), "primaryButton")
        root.addWidget(calibrate)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        root.addWidget(buttons)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)

        start_calibration = {"value": False}
        def _calibrate():
            start_calibration["value"] = True
            dialog.accept()
        calibrate.clicked.connect(_calibrate)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.project.raw["cable_length_unit_mode"] = str(unit_combo.currentData() or "auto")
        self.project.raw["cable_length_reserve_percent"] = float(reserve.value())
        self.project.dirty = True
        self._update_title()
        self._refresh_cable_length_ui()
        if start_calibration["value"]:
            QTimer.singleShot(0, self.start_length_calibration)

    def start_length_calibration(self) -> None:
        if self.doc is None:return
        self._stop_cable_marking_for_other_tool(); self.view.start_calibration_tool()
        self._set_status("Kalibrering · klik første punkt og derefter andet punkt med kendt afstand · Esc annullerer")

    def _length_calibration_finished(self, payload: dict) -> None:
        try:
            drawing_distance = float(payload.get("drawing_distance", 0.0))
        except Exception:
            drawing_distance = 0.0
        if drawing_distance <= 1e-12:
            QMessageBox.warning(self, "Kalibrering", "De to punkter skal have en målbar afstand.")
            return
        real_m, ok = QInputDialog.getDouble(
            self, "Kalibrering",
            f"Afstanden på tegningen er {drawing_distance:.4g} tegneenheder.\n\nIndtast den virkelige afstand [m]:",
            1.0, 0.0001, 1000000.0, 4,
        )
        if not ok or real_m <= 0:
            self._set_status("Kalibrering annulleret.")
            return
        factor = float(real_m) / drawing_distance
        self.project.raw["cable_length_unit_mode"] = "calibrated"
        self.project.raw["cable_length_m_per_unit"] = factor
        self.project.raw["cable_length_calibration_drawing_distance"] = drawing_distance
        self.project.raw["cable_length_calibration_real_m"] = float(real_m)
        self.project.dirty = True
        self._update_title()
        self._refresh_cable_length_ui()
        QMessageBox.information(
            self, "Kalibrering gemt",
            "Kabellængdeskalaen er nu kalibreret for dette projekt.\n\n"
            f"1 tegneenhed = {factor:.8g} m"
        )
        self._set_status("Kabellængdeskala kalibreret.")

    def _cable_routes_snapshot(self):
        """Build the read-only route overview from the current physical cables."""
        from elplan_project.cable_routes import build_cable_route_groups
        factor, _source = self._length_scale_info()
        return build_cable_route_groups(self.project.placements, self.project.cables, factor)

    def _highlight_cable_route_uids(self, cable_uids) -> None:
        """Select all physical cables belonging to a route shown in the overview."""
        wanted={str(uid or "") for uid in (cable_uids or []) if str(uid or "")}
        if not wanted:
            return
        self.scene.clearSelection()
        selected=0
        hidden=0
        for cable in self.project.cables:
            uid=str(getattr(cable,"uid","") or "")
            if uid not in wanted:
                continue
            item=self.cable_items.get(id(cable))
            if item is None:
                continue
            item.setSelected(True)
            selected+=1
            if not item.isVisible():
                hidden+=1
        if selected:
            suffix=f" · {hidden} skjult af lag/visningsfilter" if hidden else ""
            self._set_status(f"Kabeltræk fremhævet · {selected} fysisk{'e' if selected!=1 else ''} kabelstykke{'r' if selected!=1 else ''}{suffix}")

    def _refresh_cable_routes_dialog(self) -> None:
        dialog=getattr(self,"_cable_routes_dialog",None)
        if dialog is None:
            return
        try:
            if dialog.isVisible():
                dialog.refresh()
        except RuntimeError:
            self._cable_routes_dialog=None

    def show_cable_routes_overview(self) -> None:
        if not self.project.cables:
            QMessageBox.information(self,"Kabeltræk","Projektet indeholder endnu ingen kabler.")
            return
        existing=getattr(self,"_cable_routes_dialog",None)
        try:
            if existing is not None and existing.isVisible():
                existing.refresh(); existing.raise_(); existing.activateWindow()
                return
        except RuntimeError:
            self._cable_routes_dialog=None
        from elplan_qt.qt_cable_routes import CableRoutesDialog
        dialog=CableRoutesDialog(self,snapshot_provider=self._cable_routes_snapshot,highlight_callback=self._highlight_cable_route_uids,
            marking_provider=self._cable_marking_rows,marking_edit_callback=self._cable_marking_from_routes,marking_mode_callback=lambda:self.start_cable_marking())
        self._cable_routes_dialog=dialog
        def _clear_dialog_ref(*_args):
            if getattr(self,"_cable_routes_dialog",None) is dialog:
                self._cable_routes_dialog=None
        dialog.finished.connect(_clear_dialog_ref)
        dialog.show(); dialog.raise_(); dialog.activateWindow()

    def show_cable_length_report(self) -> None:
        if self.doc is None:
            QMessageBox.information(self, "Kabellængderapport", "Åbn først et projekt eller en DWG/DXF.")
            return
        factor, source = self._length_scale_info()
        if factor is None:
            QMessageBox.information(
                self, "Kabellængderapport",
                "Der kan ikke beregnes meter endnu, fordi tegningens skala/enhed ikke er kendt.\n\n"
                "Vælg Værktøjer → Kabellængder / skala… og vælg en enhed eller kalibrer på tegningen."
            )
            return
        reserve = self._length_reserve_percent()
        cables = list(self.project.cables)
        dialog = QDialog(self)
        dialog.setWindowTitle("Kabellængderapport")
        _resize_dialog(dialog,860,620)
        root = QVBoxLayout(dialog)
        info = QLabel(f"Skala: {source} · global reserve: {reserve:g}% · {len(cables)} fysiske kabel-/ledningsstykker")
        info.setWordWrap(True); info.setObjectName("subtleText")
        root.addWidget(info)

        table = QTableWidget(len(cables), 8)
        table.setHorizontalHeaderLabels(["ID", "Gruppe/kreds", "Fra → til", "Type", "Kabeltype", "Punkter", "Rutelængde", "Inkl. reserve"])
        _configure_resizable_table(table,"cable_length_report",(80,100,220,80,160,70,110,110))
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        totals: dict[tuple[str, str], list[float]] = defaultdict(lambda: [0.0, 0.0])
        grand_base = 0.0; grand_est = 0.0
        for row, cable in enumerate(cables):
            type_name = "Ledning" if cable.layer == core.WIRE_LAYER else "Kabel"
            effective_specs=core.cable_effective_specs(cable)
            spec = " / ".join(effective_specs) if effective_specs else str(cable.cable_spec or "—")
            base = core.cable_length_metres(cable, factor) or 0.0
            est = core.cable_estimated_length_metres(cable, factor, reserve) or 0.0
            grand_base += base; grand_est += est
            by_spec=core.cable_length_by_spec_metres(cable,factor) or {spec:base}
            for local_spec,local_base in by_spec.items():
                totals[(type_name, local_spec)][0] += float(local_base)
                totals[(type_name, local_spec)][1] += float(local_base)*(1.0+max(0.0,float(reserve))/100.0)
            endpoint_names=[self._cable_symbol_caption(r.get("symbol_uid","")) for r in core.cable_symbol_connections(cable)]
            endpoints=" → ".join(endpoint_names) if endpoint_names else "frie ender"
            values = [
                str(cable.cable_id or "—"),str(getattr(cable,"circuit_id","") or "—"),endpoints,
                type_name,spec,str(len(cable.points)),self._fmt_metres(base),self._fmt_metres(est),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col in (5,6,7): item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(row, col, item)
        header = table.horizontalHeader()
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        root.addWidget(table, 1)

        summary_title = QLabel("Materialesummer")
        summary_title.setObjectName("sectionTitle")
        root.addWidget(summary_title)
        summary = QTableWidget(len(totals) + 1, 4)
        summary.setHorizontalHeaderLabels(["Type", "Kabeltype", "Rutelængde", "Inkl. reserve"])
        _configure_resizable_table(summary,"cable_length_summary",(90,300,120,120))
        summary.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for row, ((type_name, spec), (base, est)) in enumerate(sorted(totals.items(), key=lambda x: (x[0][0], x[0][1]))):
            for col, value in enumerate([type_name, spec, self._fmt_metres(base), self._fmt_metres(est)]):
                item = QTableWidgetItem(value)
                if col >= 2: item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                summary.setItem(row, col, item)
        total_row = len(totals)
        vals = ["I alt", "", self._fmt_metres(grand_base), self._fmt_metres(grand_est)]
        for col, value in enumerate(vals):
            item = QTableWidgetItem(value)
            font = item.font(); font.setBold(True); item.setFont(font)
            if col >= 2: item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            summary.setItem(total_row, col, item)
        sheader = summary.horizontalHeader()
        sheader.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        summary.setMaximumHeight(190)
        root.addWidget(summary)

        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(dialog.reject)
        root.addWidget(close)
        dialog.exec()

    def export_pl_box_report(self) -> None:
        boxes=[p for p in self.project.placements if str(getattr(p,"symbol","") or "")=="light_connection"]
        if not boxes:
            QMessageBox.information(self,"PL-dåserapport","Projektet indeholder ingen PL-lampesteder endnu.")
            return
        base="PL-daaserapport"
        try:
            if getattr(self.project,"path",None):
                stem=Path(self.project.path).name
                if stem.endswith(".elplan.json"):stem=stem[:-12]
                elif "." in stem:stem=Path(stem).stem
                if stem:base=f"{stem}_PL-daaserapport"
        except Exception:
            pass
        path,_=QFileDialog.getSaveFileName(self,"Gem PL-dåserapport",base+".pdf","PDF (*.pdf)")
        if not path:return
        if not str(path).lower().endswith(".pdf"):path=str(path)+".pdf"
        project_name=""
        try:
            if getattr(self.project,"path",None):project_name=Path(self.project.path).stem.replace(".elplan","")
            elif getattr(self.project,"source_file",None):project_name=Path(self.project.source_file).stem
        except Exception:
            project_name=""
        try:
            core.export_pl_box_report_pdf(path,self.project.placements,self.project.cables,project_name or "Elplan-projekt")
        except Exception as exc:
            QMessageBox.critical(self,"PL-dåserapport",f"Rapporten kunne ikke oprettes:\n{exc}")
            return
        self._set_status(f"PL-dåserapport gemt: {path}")
        QMessageBox.information(self,"PL-dåserapport",f"Rapport med {len(boxes)} PL-dåse(r) er gemt:\n{path}")

    def _cable_article_catalog(self,*,refresh:bool=False) -> list[dict]:
        """Merged, priced catalogue used by the compact cable article picker."""
        cached=getattr(self,"_cable_article_catalog_cache",None)
        if cached is not None and not refresh:return cached
        merged={a["article_no"]:deepcopy(a) for a in user_library.load_core_article_catalog()}
        for art in user_library.load_global_bom_articles():
            merged[art["article_no"]]=deepcopy(art)
        self._cable_article_catalog_cache=user_library.apply_article_prices(merged.values(),user_library.load_article_prices())
        return self._cable_article_catalog_cache

    def _ensure_project_article(self, article_no: str) -> bool:
        """Ensure a selected article exists in the global core article database."""
        article_no=str(article_no or "").strip()
        if not article_no:return False
        catalog=user_library.load_core_article_catalog()
        if any(a["article_no"]==article_no for a in catalog):return True
        src=next((a for a in core.load_predefined_article_catalog() if a.get("article_no")==article_no),None)
        if src is None:return False
        catalog.append(deepcopy(src))
        user_library.save_core_article_catalog(catalog)
        self._cable_article_catalog_cache=None
        return True

    def _cable_article_bindings(self) -> dict[str,str]:
        return core.normalize_cable_article_bindings(self.project.raw.get("cable_instance_articles",{}))

    def _refresh_cable_article_ui(self) -> None:
        if not hasattr(self,"cable_article_label"):return
        lookup={a["article_no"]:a for a in self._cable_article_catalog()}
        if self.selected_cable is not None:
            uid=str(getattr(self.selected_cable,"uid","") or "")
            article_no=self._cable_article_bindings().get(uid,"")
            prefix="Tilknyttet til valgt fysisk kabel"
        else:
            article_no=str(getattr(self,"_pending_cable_article_no","") or "")
            prefix="Til næste kabel"
        art=lookup.get(article_no,{})
        if article_no:
            desc=str(art.get("description","") or "")
            spec=str(art.get("cable_spec","") or "")
            detail=" · ".join(x for x in (article_no,spec,desc) if x)
            self.cable_article_label.setText(f"{prefix}: {detail}")
        else:
            self.cable_article_label.setText(
                "Ingen artikel tilknyttet til valgt kabel" if self.selected_cable is not None
                else "Ingen artikel valgt til næste kabel"
            )
        self.cable_clear_article.setEnabled(bool(article_no))
        self.cable_choose_article.setEnabled(self.doc is not None)

    def choose_cable_article(self) -> None:
        if self.doc is None:return
        current=""
        if self.selected_cable is not None:
            current=self._cable_article_bindings().get(str(getattr(self.selected_cable,"uid","") or ""),"")
        else:
            current=str(self._pending_cable_article_no or "")
        from elplan_qt.qt_articles import ArticlePickerDialog
        dlg=ArticlePickerDialog(self,self._cable_article_catalog(),"Vælg kabelartikel",current,kind_filter="cable")
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        article_no=dlg.selected_article_no()
        if not article_no:return
        if self.selected_cable is not None:
            uid=str(getattr(self.selected_cable,"uid","") or "")
            if not uid:return
            self._ensure_project_article(article_no)
            bindings=self._cable_article_bindings(); bindings[uid]=article_no
            self.project.raw["cable_instance_articles"]=bindings
            self.project.dirty=True; self._update_title()
        else:
            # A pending choice is UI state only and is consumed by exactly one
            # newly drawn cable. Nothing is written to the project until the
            # cable actually exists.
            self._pending_cable_article_no=article_no
        self._refresh_cable_article_ui()
        self._set_status("Kabelartikel valgt. Tilknytningen gælder kun dette kabelstræk.")

    def clear_cable_article(self) -> None:
        changed=False
        if self.selected_cable is not None:
            uid=str(getattr(self.selected_cable,"uid","") or "")
            bindings=self._cable_article_bindings()
            if uid in bindings:
                bindings.pop(uid,None); self.project.raw["cable_instance_articles"]=bindings; changed=True
        elif self._pending_cable_article_no:
            self._pending_cable_article_no=""
        if changed:
            self.project.dirty=True; self._update_title()
        self._refresh_cable_article_ui()

    def _set_next_cable_id(self) -> None:
        if not hasattr(self,"cable_id_edit"):return
        _typ=self.cable_type_combo.currentText()
        prefix="L" if _typ=="Ledning" else ("P" if _typ=="Patchkabel" else "K")
        self.cable_id_edit.setText(self._next_cable_id(prefix))

    def _cable_is_orthogonal(self) -> bool:
        if not hasattr(self,"cable_route_mode_combo"):
            return False
        return str(self.cable_route_mode_combo.currentData() or "free") == "orthogonal"

    def _set_cable_route_mode(self, orthogonal: bool) -> None:
        if not hasattr(self,"cable_route_mode_combo"):
            return
        wanted="orthogonal" if bool(orthogonal) else "free"
        idx=self.cable_route_mode_combo.findData(wanted)
        if idx < 0:
            idx=0
        blocker=QSignalBlocker(self.cable_route_mode_combo)
        try:
            self.cable_route_mode_combo.setCurrentIndex(idx)
        finally:
            del blocker

    def _cable_route_mode_changed(self,*_args) -> None:
        if getattr(self,"_loading_cable_panel",False):
            return
        # New-cable route preference is global and remembered. Editing an
        # existing cable changes only that cable once Apply is pressed.
        if self.selected_cable is None:
            data=core.load_app_settings()
            data["cable_route_mode"]="orthogonal" if self._cable_is_orthogonal() else "free"
            core.save_app_settings(data)
            self.app_settings=dict(data)
            self.project.raw["cable_orthogonal"]=self._cable_is_orthogonal()
        self._cable_panel_changed()

    def _cable_type_changed(self,*_args) -> None:
        if getattr(self,"_loading_cable_panel",False):
            return
        # New-cable mode gets the next matching K/L number automatically.
        if self.selected_cable is None:
            self._set_next_cable_id()
        self._cable_panel_changed()

    def _cable_panel_changed(self,*_args) -> None:
        if not hasattr(self,"cable_spec_combo") or getattr(self,"_loading_cable_panel",False):return
        if self.selected_cable is None:
            self.project.raw["cable_type"]=self.cable_type_combo.currentText()
            self.project.raw["cable_category"]=str(self.cable_category_combo.currentData() or core.DEFAULT_CABLE_CATEGORY)
            self.project.raw["cable_spec"]=self.cable_spec_combo.currentText().strip()
            self.project.raw["cable_circuit_id"]=self.cable_group_edit.text().strip()
            self.project.raw["cable_label"]=""  # Extra mærkning er altid en aktiv, separat brugerhandling.
            self.project.raw["cable_line_width"]=float(self.cable_width_spin.value())
            # Farve/linjetype er kategoridata; felterne beholdes kun som cache/kompatibilitet.
            self.project.raw["cable_color"]=core.normalize_hex_color(self.cable_color.text(),core.DEFAULT_CABLE_COLOR)
            self.project.raw["cable_line_style"]=core.normalize_cable_line_style(self.cable_line_style.currentData())
        if getattr(self.view,"_cable_active",False):
            _typ=self.cable_type_combo.currentText()
            layer=core.WIRE_LAYER if _typ=="Ledning" else (core.PATCH_CABLE_LAYER if _typ=="Patchkabel" else core.CABLE_LAYER)
            self.view.update_cable_settings(
                layer=layer,
                line_width=float(self.cable_width_spin.value()),
                label="",
                cable_spec=self.cable_spec_combo.currentText().strip(),
                cable_id=self.cable_id_edit.text().strip(),
                circuit_id=self.cable_group_edit.text().strip(),
                auto_label=self.cable_auto_label.isChecked(),
                orthogonal=self._cable_is_orthogonal(),
                color=core.normalize_hex_color(self.cable_color.text(),core.DEFAULT_CABLE_COLOR),
                line_style=core.normalize_cable_line_style(self.cable_line_style.currentData()),
                cable_category=str(self.cable_category_combo.currentData() or core.DEFAULT_CABLE_CATEGORY),
                snap_symbols=self.cable_snap_symbols.isChecked(),
                snap_walls=self.cable_snap_walls.isChecked(),
                snap_routes=self.cable_snap_routes.isChecked(),
            )
            self._update_cable_tool_status()
        if hasattr(self,"context_toolbar"):
            self._refresh_context_toolbar()

    def _cable_route_summary(self, cable: core.CablePlacement | None = None) -> str:
        if cable is not None:
            connections=core.cable_symbol_connections(cable)
        elif getattr(self.view,"_cable_active",False):
            connections=core.normalize_cable_symbol_connections(getattr(self.view,"_cable_connections",[]),len(getattr(self.view,"_cable_points",[]) or []))
        else:
            connections=[]
        if not connections:
            return "Forløb: ingen fysiske tilslutningssteder endnu"
        labels=[self._cable_symbol_caption(r.get("symbol_uid","")) for r in connections]
        shown=labels[:8]
        text=" → ".join(shown)
        if len(labels)>len(shown): text+=f" → … (+{len(labels)-len(shown)})"
        return f"Forløb: {text} · {len(labels)} tilslutningssted"+("er" if len(labels)!=1 else "")

    def _update_cable_tool_status(self) -> None:
        if not hasattr(self,"cable_tool_status"):return
        if getattr(self.view,"_cable_active",False):
            cid=self.cable_id_edit.text().strip() or "—"
            spec=self.cable_spec_combo.currentText().strip() or "—"
            mode="90°" if self._cable_is_orthogonal() else "fri/diagonal"
            snaps=[]
            if self.cable_snap_symbols.isChecked():snaps.append("symbol")
            if self.cable_snap_walls.isChecked():snaps.append("væg")
            if hasattr(self,"cable_snap_routes") and self.cable_snap_routes.isChecked():snaps.append("kabelrute")
            connection_count=len(getattr(self.view,"_cable_connections",[]) or [])
            group=self.cable_group_edit.text().strip() or "uden gruppe"
            physical=max(0,connection_count-1)
            self.cable_tool_status.setText(
                f"Tegner kabelstreng · {group} · {spec} · næste ID {cid} · {physical} fysisk"
                f" kabelstykke{'r' if physical!=1 else ''} · snap: {', '.join(snaps) if snaps else 'fra'}"
            )
            if hasattr(self,"cable_route_label"):self.cable_route_label.setText(self._cable_route_summary())
        else:
            self.cable_tool_status.setText("Klar — tryk Start / nyt kabel")
            if hasattr(self,"cable_route_label"):
                self.cable_route_label.setText(self._cable_route_summary(self.selected_cable) if self.selected_cable is not None else "Forløb: —")
        if hasattr(self, "_refresh_workflow_bar"): self._refresh_workflow_bar()

    def _cable_assistant_toggled(self, checked: bool) -> None:
        if getattr(self,"_loading_cable_panel",False):
            return
        if not checked and hasattr(self,"cable_assistant_popup"):
            self.cable_assistant_popup.hide()
        data=core.load_app_settings()
        data["cable_assistant_enabled"]=bool(checked)
        core.save_app_settings(data)
        self.app_settings=data

    def _cable_symbol_caption(self, uid: str) -> str:
        p=self._placement_by_uid(str(uid or ""))
        if p is None:
            return "Symbol"
        name=core.symbol_display_name(p.symbol)
        ident=str(p.group or p.label or "").strip()
        return f"{name} · {ident}" if ident else name

    def _existing_cables_at_symbol(self, uid: str) -> list[str]:
        out=[]
        target=str(uid or "")
        if not target:
            return out
        for cable in self.project.cables:
            if any(str(r.get("symbol_uid","") or "")==target for r in core.cable_symbol_connections(cable)):
                out.append(str(cable.cable_id or cable.cable_spec or "Kabel"))
        return out

    def _cable_point_committed(self, payload) -> None:
        rec=dict(payload or {})
        self._last_cable_assistant_event=rec
        popup=getattr(self,"cable_assistant_popup",None)
        if popup is None:
            return
        if str(rec.get("kind","") or "").upper()!="SYMBOL":
            popup.hide()
            return
        if not hasattr(self,"cable_assistant_enabled") or not self.cable_assistant_enabled.isChecked():
            popup.hide()
            return
        uid=str(rec.get("symbol_uid","") or "")
        if bool(rec.get("is_first",False)) and uid and hasattr(self,"cable_group_edit") and not self.cable_group_edit.text().strip():
            placement=self._placement_by_uid(uid)
            inferred=str(getattr(placement,"group","") or "").strip() if placement is not None else ""
            if inferred:
                self.cable_group_edit.setText(inferred)
        caption=self._cable_symbol_caption(uid)
        cid=str(rec.get("cable_id","") or self.cable_id_edit.text().strip() or "Kabel")
        spec=str(rec.get("cable_spec","") or self.cable_spec_combo.currentText().strip())
        count=max(0,int(rec.get("connection_count",0) or 0))
        first=bool(rec.get("is_first",False))
        warning=bool(rec.get("already_connected",False))
        if first:
            message=f"Start registreret ved {caption}."
            hint="Klik et knækpunkt eller næste symbol for at fortsætte kabelstrengen. Hvert symbol-til-symbol-stykke bliver et selvstændigt kabel."
        else:
            physical=max(0,count-1)
            message=f"✓ {caption} er føjet til kabelstrengen. {physical} fysisk{'e' if physical!=1 else ''} kabelstykke{'r' if physical!=1 else ''} klar."
            hint="Klik videre til næste installationspunkt, eller afslut strengen. De færdige stykker kan bagefter konfigureres individuelt."
        existing=self._existing_cables_at_symbol(uid)
        if existing:
            shown=", ".join(existing[:4])
            if len(existing)>4: shown+=f" +{len(existing)-4}"
            message+=f"\nEksisterende kabler ved symbolet: {shown}."
        if warning:
            message+="\nBemærk: symbolet er allerede registreret tidligere på det aktive kabel."
        try:
            sx,sy=rec.get("scene_point",(0.0,0.0))
            anchor=QPointF(self.view.mapFromScene(QPointF(float(sx),float(sy))))
        except Exception:
            anchor=QPointF(self.view.viewport().rect().center())
        popup.show_event(
            anchor, title=f"{cid}{' · '+spec if spec else ''}", message=message, hint=hint, first=first, warning=warning
        )
        self._update_cable_tool_status()

    def _cable_assistant_finish(self) -> None:
        if hasattr(self,"cable_assistant_popup"): self.cable_assistant_popup.hide()
        if getattr(self.view,"_cable_active",False):
            self.view.finish_cable()

    def _cable_assistant_undo(self) -> None:
        if hasattr(self,"cable_assistant_popup"): self.cable_assistant_popup.hide()
        if getattr(self.view,"_cable_active",False):
            self.view.remove_last_cable_point()
            self._update_cable_tool_status()
            self._set_status("Sidste kabelpunkt blev fjernet. Fortsæt med at tegne kabelstrengen.")

    def _cable_assistant_pass_by(self) -> None:
        if hasattr(self,"cable_assistant_popup"): self.cable_assistant_popup.hide()
        if getattr(self.view,"_cable_active",False):
            self.view.convert_last_cable_connection_to_waypoint()
            self._update_cable_tool_status()
            self._set_status("Punktet beholdes som ruteknæk, men er ikke længere en fysisk symboltilslutning.")

    def _cable_assistant_restart(self) -> None:
        rec=dict(getattr(self,"_last_cable_assistant_event",None) or {})
        if not getattr(self.view,"_cable_active",False) or bool(rec.get("is_first",False)):
            return
        if len(getattr(self.view,"_cable_points",[]) or []) < 2:
            self._set_status("Kablet skal have mindst to forskellige rutepunkter før et nyt kabel kan startes herfra.")
            return
        self._pending_cable_restart_anchor={
            "cad_point": tuple(rec.get("cad_point",(0.0,0.0))),
            "symbol_uid": str(rec.get("symbol_uid","") or ""),
            "symbol_port": max(0,int(rec.get("symbol_port",0) or 0)),
        }
        if hasattr(self,"cable_assistant_popup"): self.cable_assistant_popup.hide()
        self.view.finish_cable()

    def _start_cable_from_assistant_anchor(self, anchor: dict) -> None:
        if not self._cable_tool_is_open():
            return
        self._start_cable_from_panel()
        if not getattr(self.view,"_cable_active",False):
            return
        self.view.seed_cable_start(
            anchor.get("cad_point",(0.0,0.0)),
            str(anchor.get("symbol_uid","") or ""),
            int(anchor.get("symbol_port",0) or 0),
        )
        self._set_status(f"{self.cable_id_edit.text().strip() or 'Nyt kabel'} startet fra samme tilslutningssted. Klik næste punkt.")

    def _cable_action_toggled(self, checked: bool) -> None:
        if checked:
            self.open_cable_tool()
        else:
            self.close_cable_tool()

    def _cable_dock_visibility_changed(self, visible: bool) -> None:
        # Compatibility hook kept for older tests/plugins. Cable mode is no
        # longer represented by a separate dock in 0.53.0.
        if not visible and self._cable_tool_is_open():
            self.close_cable_tool()

    def open_cable_tool(self) -> None:
        if self.doc is None:
            QMessageBox.information(self,"Kabelværktøj","Åbn først en DWG/DXF eller et projekt.")
            blocker=QSignalBlocker(self.act_cable); self.act_cable.setChecked(False); del blocker
            return
        self._stop_cable_marking_for_other_tool(); self._cable_mode_enabled = True
        self._show_inspector_page("cable", title="Ny kabelstreng", hint="Klik tilslutningssteder i rækkefølge. Programmet opretter ét fysisk kabel mellem hvert par. Esc afslutter værktøjet.")
        blocker=QSignalBlocker(self.act_cable); self.act_cable.setChecked(True); del blocker
        # Refresh saved defaults each time without destroying user's current selections.
        if not self.cable_id_edit.text().strip():
            self._set_next_cable_id()
        if not getattr(self.view,"_cable_active",False):
            self._start_cable_from_panel()
        else:
            self._update_cable_tool_status()
        self._refresh_context_toolbar()

    def _start_cable_from_panel(self) -> None:
        if self.doc is None:return
        if hasattr(self,"cable_assistant_popup"): self.cable_assistant_popup.hide()
        self._last_cable_assistant_event=None
        # Drawing a new cable is a distinct context from editing a selected one.
        # Clearing selection prevents the contextual toolbar from showing stale
        # cable properties while the user is placing a new route.
        self.scene.clearSelection()
        self.selected_cable=None
        if hasattr(self,"_set_cable_panel_context"): self._set_cable_panel_context(None)
        if hasattr(self,"cable_apply_selected"):self.cable_apply_selected.setEnabled(False)
        self._refresh_cable_article_ui()
        # Starting a new cable deliberately discards an unfinished preview.
        if getattr(self.view,"_cable_active",False):
            self.view.cancel_tool(emit_signal=False)
        _typ=self.cable_type_combo.currentText()
        layer=core.WIRE_LAYER if _typ=="Ledning" else (core.PATCH_CABLE_LAYER if _typ=="Patchkabel" else core.CABLE_LAYER)
        cid=self.cable_id_edit.text().strip()
        if not cid:
            self._set_next_cable_id(); cid=self.cable_id_edit.text().strip()
        self.view.start_cable_tool(
            layer=layer,
            line_width=float(self.cable_width_spin.value()),
            label="",
            cable_spec=self.cable_spec_combo.currentText().strip(),
            cable_id=cid,
            auto_label=self.cable_auto_label.isChecked(),
            orthogonal=self._cable_is_orthogonal(),
            circuit_id=self.cable_group_edit.text().strip(),
            color=core.normalize_hex_color(self.cable_color.text(),core.DEFAULT_CABLE_COLOR),
            line_style=core.normalize_cable_line_style(self.cable_line_style.currentData()),
            cable_category=str(self.cable_category_combo.currentData() or core.DEFAULT_CABLE_CATEGORY),
            snap_symbols=self.cable_snap_symbols.isChecked(),
            snap_walls=self.cable_snap_walls.isChecked(),
            snap_routes=self.cable_snap_routes.isChecked(),
        )
        self._update_cable_tool_status()
        self._set_status(
            "Kabelværktøj aktivt · klik fysiske tilslutningssteder/knæk i rækkefølge · "
            "hvert stræk mellem tilslutninger bliver et selvstændigt kabel · højreklik/Enter afslutter kabelstrengen · Backspace fjerner sidste brugerklik"
        )

    def _cancel_current_cable(self) -> None:
        if hasattr(self,"cable_assistant_popup"): self.cable_assistant_popup.hide()
        self._pending_cable_restart_anchor=None
        if getattr(self.view,"_cable_active",False):
            self.view.cancel_tool(emit_signal=False)
        self._update_cable_tool_status()
        self._set_status("Aktuel kabelstreng annulleret. Kabelværktøjet er stadig åbent.")

    def close_cable_tool(self) -> None:
        if hasattr(self,"cable_assistant_popup"): self.cable_assistant_popup.hide()
        self._pending_cable_restart_anchor=None
        if getattr(self.view,"_cable_active",False):
            self.view.cancel_tool(emit_signal=False)
        # Et endnu ikke brugt artikelvalg må ikke hænge ved og blive tildelt et
        # senere kabel ved et uheld.
        self._pending_cable_article_no=""
        self._cable_mode_enabled = False
        blocker=QSignalBlocker(self.act_cable); self.act_cable.setChecked(False); del blocker
        self._update_cable_tool_status()
        self._refresh_cable_article_ui()
        # Inspector stays available; leaving a tool must not make the whole
        # editing surface jump or disappear.
        selected_symbols=[x for x in self.scene.selectedItems() if isinstance(x,ElectricalSymbolItem)]
        selected_cables=[x for x in self.scene.selectedItems() if isinstance(x,CableItem)]
        if len(selected_cables)==1 and not selected_symbols:
            cable=selected_cables[0].cable
            self._show_inspector_page("cable", title=core.cable_display_label(cable) or cable.cable_id or "Kabel", hint="Eksisterende kabel valgt.")
        else:
            self._show_inspector_page("properties", title="Intet valgt" if not selected_symbols else core.symbol_display_name(selected_symbols[0].placement.symbol), reveal=True)
        self._refresh_context_toolbar()
        self._set_status("Kabelværktøj afsluttet.")

    def start_cable_dialog(self) -> None:
        # Compatibility alias from the first Qt migration versions.
        self.open_cable_tool()
        return

    def _cable_finished(self, data: dict) -> None:
        try:
            chain = core.CablePlacement(**data)
            core.set_cable_symbol_connections(chain,core.cable_symbol_connections(chain))
        except Exception as exc:
            QMessageBox.warning(self, "Kabel", str(exc))
            self._update_cable_tool_status()
            return

        # Gruppe/kreds gælder den logiske streng, mens de konkrete stykker er
        # selvstændige kabler. Hvis gruppen ikke blev angivet, må den kun
        # auto-udledes når alle tilsluttede symboler peger på samme gruppe.
        if not str(getattr(chain,"circuit_id","") or "").strip():
            groups=[]
            for conn in core.cable_symbol_connections(chain):
                placement=self._placement_by_uid(str(conn.get("symbol_uid","") or ""))
                value=str(getattr(placement,"group","") or "").strip() if placement is not None else ""
                if value and value not in groups:groups.append(value)
            if len(groups)==1:
                chain.circuit_id=groups[0]

        # The drawing gesture may pass several installation points, but the
        # persisted model never does: one CablePlacement == one physical cable.
        physical=core.split_cable_into_physical_segments(chain)
        _typ=self.cable_type_combo.currentText() if hasattr(self,"cable_type_combo") else "Kabel"
        prefix="L" if _typ=="Ledning" else ("P" if _typ=="Patchkabel" else "K")
        ids=self._allocate_cable_ids(len(physical),str(getattr(chain,"cable_id","") or ""),prefix)
        for cable,cid in zip(physical,ids):
            cable.cable_id=cid
            cable.circuit_id=str(getattr(chain,"circuit_id","") or "").strip()
            cable.route_chain_uid=str(getattr(chain,"route_chain_uid","") or getattr(chain,"uid","") or uuid.uuid4().hex)
            cable.route_section_modes=[]
            cable.spec_section_overrides=[]

        if not physical:
            self._update_cable_tool_status(); return

        pending_article=str(getattr(self,"_pending_cable_article_no","") or "")
        if pending_article:
            self._ensure_project_article(pending_article)
            bindings_before=self._cable_article_bindings(); bindings_after=dict(bindings_before)
            # Initial article choice applies to every newly created physical
            # cable in this one gesture. They can then be changed independently.
            for cable in physical:
                bindings_after[str(getattr(cable,"uid","") or "")]=pending_article
            self.undo_stack.beginMacro("Tegn kabelstreng" if len(physical)>1 else "Tegn kabel")
            try:
                self.undo_stack.push(AddCableBatchCommand(self,physical,"Tilføj fysiske kabler"))
                self.undo_stack.push(CableArticleBindingsCommand(self,bindings_before,bindings_after,"Tilknyt kabelartikel"))
            finally:
                self.undo_stack.endMacro()
            self._pending_cable_article_no=""
        else:
            self.undo_stack.push(AddCableBatchCommand(self,physical,"Tegn kabelstreng" if len(physical)>1 else "Tegn kabel"))

        restart_anchor=getattr(self,"_pending_cable_restart_anchor",None)
        self._pending_cable_restart_anchor=None
        if restart_anchor and self._cable_tool_is_open():
            self._set_next_cable_id()
            QTimer.singleShot(0,lambda a=dict(restart_anchor):self._start_cable_from_assistant_anchor(a))
        elif self._cable_tool_is_open() and self.cable_continuous.isChecked():
            self._set_next_cable_id()
            QTimer.singleShot(0,self._start_cable_from_panel)
        else:
            self._update_cable_tool_status()
            factor=self._length_scale_info()[0]
            total=sum((core.cable_length_metres(c,factor) or 0.0) for c in physical) if factor is not None else None
            suffix=f" · {self._fmt_metres(total)}" if total is not None else ""
            group=str(getattr(chain,"circuit_id","") or "").strip()
            group_text=f" · {group}" if group else ""
            self._set_status(f"{len(physical)} fysisk{'e' if len(physical)!=1 else ''} kabelstykke{'r' if len(physical)!=1 else ''} gemt{group_text}{suffix}.")
        self._refresh_cable_length_ui(chain.points)

    def _add_cable(self, cable: core.CablePlacement, index: int | None = None) -> None:
        if any(c is cable for c in self.project.cables):
            return
        rec=self._cable_category_record(getattr(cable,"cable_category",core.DEFAULT_CABLE_CATEGORY))
        cable.cable_category=rec["id"]; cable.color=rec["color"]; cable.line_style=rec["line_style"]
        cable.route_section_modes=core.normalize_cable_route_section_modes(getattr(cable,"route_section_modes",[]))
        cable.spec_section_overrides=core.normalize_cable_spec_section_overrides(
            getattr(cable,"spec_section_overrides",[]),getattr(cable,"cable_spec","")
        )
        core.set_cable_symbol_connections(cable,core.cable_symbol_connections(cable))
        if index is None or not (0 <= index <= len(self.project.cables)):
            self.project.cables.append(cable)
        else:
            self.project.cables.insert(index,cable)
        item = CableItem(cable,self._snap_cable_vertex,self.view.current_scale,self._cable_visual_points,lambda c:self._fmt_metres(self._points_length_metres(c.points)))
        self._wire_cable_item(item)
        item.setVisible(self._cable_layer_visible(cable) and self._quick_cable_visible(cable))
        self.scene.addItem(item)
        self.generated_layer_items[core.cable_effective_layer(cable)].append(item)
        self.cable_items[id(cable)] = item
        self._rebuild_cable_visual_cache(refresh_items=True)
        self.project.dirty = True
        self._update_title()
        self._rebuild_layer_list()
        self._refresh_cable_length_ui(cable.points)
        self._refresh_cable_routes_dialog()

    def _apply_cable_state(self,cable: core.CablePlacement,state:dict)->None:
        old_effective=core.cable_effective_layer(cable)
        for key,value in state.items():
            if hasattr(cable,key):
                setattr(cable,key,deepcopy(value))
        cable.points=[tuple(map(float,p)) for p in cable.points]
        cable.cable_category=core.normalize_cable_category_id(getattr(cable,"cable_category",core.DEFAULT_CABLE_CATEGORY))
        rec=self._cable_category_record(cable.cable_category); cable.cable_category=rec["id"]; cable.color=rec["color"]; cable.line_style=rec["line_style"]
        cable.route_section_modes=core.normalize_cable_route_section_modes(getattr(cable,"route_section_modes",[]))
        cable.spec_section_overrides=core.normalize_cable_spec_section_overrides(
            getattr(cable,"spec_section_overrides",[]),getattr(cable,"cable_spec","")
        )
        core.set_cable_symbol_connections(cable,getattr(cable,"symbol_connections",[]))
        new_effective=core.cable_effective_layer(cable)
        item=self.cable_items.get(id(cable))
        if item is not None:
            if old_effective!=new_effective:
                if item in self.generated_layer_items.get(old_effective,[]):self.generated_layer_items[old_effective].remove(item)
                self.generated_layer_items[new_effective].append(item)
            item.setVisible(self._cable_layer_visible(cable) and self._quick_cable_visible(cable))
            item.refresh()
        self._rebuild_cable_visual_cache(refresh_items=True)
        if old_effective!=new_effective:
            self._rebuild_layer_list()
        self.project.dirty=True
        self._update_title()
        self._refresh_cable_length_ui(cable.points)
        if self.selected_cable is cable:
            self._load_selected_cable_into_panel(cable)
        self._refresh_cable_routes_dialog()

    def _load_selected_cable_into_panel(self,cable: core.CablePlacement|None)->None:
        self.selected_cable=cable
        if hasattr(self,"_set_cable_panel_context"): self._set_cable_panel_context(cable)
        self._loading_cable_panel=True
        try:
            if cable is None:
                self.cable_apply_selected.setEnabled(False)
                self._sync_selected_cable_marking_editor(None)
                if hasattr(self,"cable_route_hint"):
                    self.cable_route_hint.setText("Fri / diagonal er standard for nye kabler. Klik ekstra punkter, hvor den fysiske kabelvej skal knække.")
                self._refresh_cable_section_controls(None)
                self._refresh_cable_article_ui()
                self._refresh_cable_length_ui([])
                return
            self._pending_cable_article_no=""
            factor, _source = self._length_scale_info()
            base = core.cable_length_metres(cable, factor)
            estimate = core.cable_estimated_length_metres(cable, factor, self._length_reserve_percent())
            length_text = (
                f" · {self._fmt_metres(base)} / {self._fmt_metres(estimate)} inkl. reserve"
                if base is not None else " · længdeskala mangler"
            )
            connection_count=len(core.cable_symbol_connections(cable))
            lane_meta=getattr(self,"_cable_visual_meta",{}).get(id(cable),{})
            lane_count=max(1,int(lane_meta.get("lane_count",1) or 1))
            lane_text=(f" · parallel bane {int(lane_meta.get('lane_index',0))+1}/{lane_count}" if lane_count>1 else "")
            route_text="90°" if bool(cable.orthogonal) else "fri/diagonal"
            spec_text=str(cable.cable_spec or "").strip() or "uden kabeltype"
            category_name=self._cable_category_record(getattr(cable,"cable_category",core.DEFAULT_CABLE_CATEGORY))["name"]
            group_text=str(getattr(cable,"circuit_id","") or "").strip() or "uden gruppe"
            connections=core.cable_symbol_connections(cable)
            endpoint_names=[self._cable_symbol_caption(r.get("symbol_uid","")) for r in connections]
            endpoint_text=" → ".join(endpoint_names) if endpoint_names else "frie ender"
            # The unified inspector header/summary owns selected-cable identity.
            self.cable_apply_selected.setEnabled(True)
            if hasattr(self,"cable_route_hint"):
                self.cable_route_hint.setText("Eksisterende fysisk kabel: kabeltype, artikel og rute gælder kun dette kabelstykke. Gruppe/kreds opdateres på hele den tegnede streng. Undo gendanner den tidligere rute, kabeltype og gruppe.")
            self.cable_type_combo.setCurrentText("Ledning" if cable.layer==core.WIRE_LAYER else ("Patchkabel" if cable.layer==core.PATCH_CABLE_LAYER else "Kabel"))
            self._populate_cable_category_combo(getattr(cable,"cable_category",core.DEFAULT_CABLE_CATEGORY))
            self.cable_spec_combo.setCurrentText(str(cable.cable_spec or ""))
            self.cable_group_edit.setText(str(getattr(cable,"circuit_id","") or ""))
            self.cable_id_edit.setText(str(cable.cable_id or ""))
            self.cable_label_edit.setText(str(cable.label or ""))
            self._sync_selected_cable_marking_editor(cable)
            self.cable_width_spin.setValue(float(cable.line_width))
            _set_color_button(self.cable_color,core.normalize_hex_color(getattr(cable,"color",core.DEFAULT_CABLE_COLOR),core.DEFAULT_CABLE_COLOR))
            _style=core.normalize_cable_line_style(getattr(cable,"line_style",core.DEFAULT_CABLE_LINE_STYLE)); _idx=self.cable_line_style.findData(_style); self.cable_line_style.setCurrentIndex(max(0,_idx))
            self.cable_auto_label.setChecked(bool(cable.auto_label))
            self._set_cable_route_mode(bool(cable.orthogonal))
            self._refresh_cable_section_controls(cable)
        finally:
            self._loading_cable_panel=False
        self._update_cable_tool_status()
        self._refresh_cable_article_ui()
        self._refresh_cable_length_ui(cable.points if cable is not None else None)

    def apply_selected_cable_properties(self)->None:
        cable=self.selected_cable
        if cable is None:return
        before=CableItem.state(cable)
        after=dict(before)
        new_orthogonal=self._cable_is_orthogonal()
        new_spec=self.cable_spec_combo.currentText().strip()
        after.update({
            "layer":core.WIRE_LAYER if self.cable_type_combo.currentText()=="Ledning" else (core.PATCH_CABLE_LAYER if self.cable_type_combo.currentText()=="Patchkabel" else core.CABLE_LAYER),
            "cable_category":str(self.cable_category_combo.currentData() or core.DEFAULT_CABLE_CATEGORY),
            "cable_spec":new_spec,
            "cable_id":self.cable_id_edit.text().strip(),
            "circuit_id":self.cable_group_edit.text().strip(),
            "line_width":float(self.cable_width_spin.value()),
            "color":core.normalize_hex_color(self.cable_color.text(),core.DEFAULT_CABLE_COLOR),
            "line_style":core.normalize_cable_line_style(self.cable_line_style.currentData()),
            "auto_label":self.cable_auto_label.isChecked(),
            "orthogonal":new_orthogonal,
        })
        # 0.55: selected cable is already one physical span; there is no
        # second section layer to maintain.
        after["spec_section_overrides"]=[]
        after["route_section_modes"]=[]
        old_orthogonal=bool(before.get("orthogonal",False))
        if old_orthogonal != new_orthogonal:
            # Den globale kontrol betyder bevidst "hele kablet". Lokale
            # afsnits-overrides nulstilles derfor, så resultatet er entydigt.
            after["route_section_modes"]=[]
            points,connections=core.convert_cable_route_mode_geometry(
                before.get("points",[]),before.get("symbol_connections",[]),
                from_orthogonal=old_orthogonal,to_orthogonal=new_orthogonal,
            )
            after["points"]=points
            after["symbol_connections"]=connections
        new_group=str(after.get("circuit_id","") or "").strip()
        chain_uid=str(before.get("route_chain_uid","") or getattr(cable,"route_chain_uid","") or "")
        peers=[]
        if chain_uid and str(before.get("circuit_id","") or "").strip()!=new_group:
            for other in self.project.cables:
                if other is cable or str(getattr(other,"route_chain_uid","") or "")!=chain_uid:
                    continue
                peer_before=CableItem.state(other)
                if str(peer_before.get("circuit_id","") or "").strip()==new_group:
                    continue
                peer_after=dict(peer_before); peer_after["circuit_id"]=new_group
                peers.append((other,peer_before,peer_after))
        if before!=after or peers:
            if peers:self.undo_stack.beginMacro("Redigér kabel og gruppe/kreds")
            try:
                if before!=after:
                    self.undo_stack.push(EditCableCommand(self,cable,before,after,"Redigér kabelegenskaber"))
                for other,peer_before,peer_after in peers:
                    self.undo_stack.push(EditCableCommand(self,other,peer_before,peer_after,"Opdatér gruppe/kreds på kabelstreng"))
            finally:
                if peers:self.undo_stack.endMacro()
            if peers:
                self._set_status(f"Gruppe/kreds {new_group or '—'} er opdateret på alle {len(peers)+1} kabelstykker i strengen.")

    def _remove_cable(self, cable: core.CablePlacement) -> None:
        self.project.cables = [c for c in self.project.cables if c is not cable]
        if self.selected_cable is cable:
            self._load_selected_cable_into_panel(None)
        item = self.cable_items.pop(id(cable), None)
        if item is not None:
            if item in self.generated_layer_items.get(core.cable_effective_layer(cable), []):
                self.generated_layer_items[core.cable_effective_layer(cable)].remove(item)
            if item.scene() is not None:
                self.scene.removeItem(item)
        self._rebuild_cable_visual_cache(refresh_items=True)
        self._rebuild_layer_list()
        self.project.dirty = True
        self._update_title()
        self._refresh_cable_routes_dialog()

    def _cable_by_uid(self, uid: str):
        return next((c for c in self.project.cables if str(getattr(c,"uid","") or "")==str(uid or "")),None)

    def _refresh_symbol_cables_group(self, placement) -> None:
        if not hasattr(self,"symbol_cables_group"):
            return
        rows=[]
        uid=str(getattr(placement,"uid","") or "") if placement is not None else ""
        is_light=bool(placement is not None and str(getattr(placement,"symbol","") or "") in {"light_connection","wall_light_outlet"})
        for cable,rec in self._cables_by_symbol_uid.get(uid,[]):
            idx=int(rec.get("point_index",-1)); last=max(0,len(cable.points)-1)
            if idx==0 and idx==last: role="tilsluttet"
            elif idx==0: role="starter her"
            elif idx==last: role="ender her"
            else: role="gennemgående"
            rows.append((cable,role,idx))
        self.symbol_cables_combo.blockSignals(True); self.symbol_cables_combo.clear()
        for cable,role,_idx in rows:
            label=core.cable_display_label(cable) or str(cable.cable_id or "Kabel")
            specs=core.cable_effective_specs(cable)
            spec=" / ".join(specs) if specs else str(cable.cable_spec or "").strip()
            text=f"{label}"+(f" · {spec}" if spec else "")+f" · {role}"
            self.symbol_cables_combo.addItem(text,str(cable.uid))
        self.symbol_cables_combo.blockSignals(False)
        self.symbol_cables_combo.setEnabled(bool(rows))
        self.symbol_cables_select.setEnabled(bool(rows))
        if hasattr(self,"symbol_cables_attach"):
            self.symbol_cables_attach.setVisible(is_light)
            self.symbol_cables_attach.setEnabled(is_light and not bool(getattr(placement,"locked",False)))
        if rows:
            self.symbol_cables_summary.setText(f"{len(rows)} kabelforbindelse{'r' if len(rows)!=1 else ''} ved dette symbol. Gennemgående betyder, at samme kabel fortsætter videre efter symbolet.")
            self.symbol_cables_group.show()
        elif is_light:
            self.symbol_cables_summary.setText("Ingen kabler er fysisk tilsluttet dette lampested endnu. Du kan koble det på en allerede tegnet kabelstrækning uden at tegne kablet om.")
            self.symbol_cables_group.show()
        else:
            self.symbol_cables_summary.setText("Ingen kabler er fysisk tilsluttet dette symbol.")
            self.symbol_cables_group.hide()

    def _refresh_pl_box_group(self, placement) -> None:
        if not hasattr(self,"pl_box_group"):
            return
        if placement is None or str(getattr(placement,"symbol","") or "") != "light_connection":
            self.pl_box_group.hide(); return
        legs=core.cable_legs_at_symbol(self.project.cables,placement.uid)
        status=core.pl_box_status(getattr(placement,"pl_box_entries",{}),legs)
        wiring_status=core.pl_box_wiring_status(getattr(placement,"pl_box_wiring",[]),legs)
        outlet_caption=core.PL_OUTLET_TYPES.get(core.normalize_pl_outlet_type(getattr(placement,"lamp_outlet_type","generic")),"Generisk PL")
        orientation=core.normalize_pl_box_orientation(getattr(placement,"pl_box_orientation",0))
        text=f"PL-dåse: {status['used']} / {status['capacity']} indføringer anvendt · {outlet_caption} · orientering {orientation}°"
        if status["overflow"]:
            text += f" · ⚠ {status['required']} kabelben kræver {status['overflow']} ekstra indføring(er)"
            self.pl_box_summary.setObjectName("dangerText")
        elif status["unplaced"]:
            text += f" · {status['unplaced']} kabelben ikke placeret"
            self.pl_box_summary.setObjectName("accentText")
        elif status["required"]:
            text += " · komplet"
            self.pl_box_summary.setObjectName("positiveText")
        else:
            text += " · ingen kabler tilsluttet"
            self.pl_box_summary.setObjectName("subtleText")
        if wiring_status["known"] and not wiring_status["configured"]:
            text += " · Lederplan ikke konfigureret"
            if not status["overflow"]: self.pl_box_summary.setObjectName("accentText")
        elif wiring_status["known"]:
            text += f" · Ledere {wiring_status['assigned']}/{wiring_status['known']} fordelt"
            if wiring_status["live_unassigned"]:
                text += f" · ⚠ {wiring_status['live_unassigned']} aktive uden funktion"
                if not status["overflow"]: self.pl_box_summary.setObjectName("accentText")
        elif wiring_status["unknown_legs"]:
            text += " · ⚠ ukendt lederopbygning"
            if not status["overflow"]: self.pl_box_summary.setObjectName("accentText")
        requirements=core.pl_expected_switch_connections(placement,self.project.placements,self.project.cables)
        req_summary=core.pl_wiring_requirement_summary(requirements,core.reconcile_pl_box_wiring(getattr(placement,"pl_box_wiring",[]),legs),core.reconcile_pl_box_splices(getattr(placement,"pl_box_splices",[]),getattr(placement,"pl_box_wiring",[]),legs))
        if req_summary["required"]:
            text += f" · Tændinger {req_summary['ok']}/{req_summary['required']}"
            if req_summary["missing"] or req_summary["wrong_cable"] or req_summary["duplicate"]:
                text += " ⚠"
                if not status["overflow"]: self.pl_box_summary.setObjectName("accentText")
        if req_summary["manual"]:
            text += f" · {req_summary['manual']} korrespondance/krydsning manuel"
        normalized_wiring=core.reconcile_pl_box_wiring(getattr(placement,"pl_box_wiring",[]),legs)
        splices=core.reconcile_pl_box_splices(getattr(placement,"pl_box_splices",[]),normalized_wiring,legs)
        if splices:text += f" · Wago {len(splices)}"
        capacity_issues=core.pl_outlet_capacity_issues(getattr(placement,"lamp_outlet_type","generic"),core.light_output_associations(placement),normalized_wiring,splices)
        if capacity_issues:
            text += " · ⛔ terminalkapacitet overskredet"
            if not status["overflow"]: self.pl_box_summary.setObjectName("dangerText")
        self.pl_box_summary.setText(text)
        self.pl_box_summary.style().unpolish(self.pl_box_summary); self.pl_box_summary.style().polish(self.pl_box_summary)
        self.pl_box_button.setEnabled(not bool(getattr(placement,"locked",False)))
        self.pl_box_group.show()

    def _apply_pl_box_config(self, placement, entries, wiring, outlet_type=None, splices=None, orientation=None, field_record=None) -> None:
        if placement is None or placement.symbol != "light_connection":
            return
        self._hover_bom_cache.pop(str(getattr(placement,"uid","") or ""),None)
        legs=core.cable_legs_at_symbol(self.project.cables,placement.uid)
        normalized_entries=core.reconcile_pl_box_entries(entries,legs)
        normalized_wiring=core.reconcile_pl_box_wiring(wiring,legs)
        normalized_splices=core.reconcile_pl_box_splices(splices if splices is not None else getattr(placement,"pl_box_splices",[]),normalized_wiring,legs)
        before=self._symbol_state(placement)
        after=deepcopy(before)
        after["pl_box_entries"]=deepcopy(normalized_entries)
        after["pl_box_wiring"]=deepcopy(normalized_wiring)
        after["pl_box_splices"]=deepcopy(normalized_splices)
        after["pl_box_orientation"]=core.normalize_pl_box_orientation(orientation if orientation is not None else getattr(placement,"pl_box_orientation",0))
        after["lamp_outlet_type"]=core.normalize_pl_outlet_type(outlet_type if outlet_type is not None else getattr(placement,"lamp_outlet_type","generic"))
        after["pl_field_record"]=deepcopy(core.normalize_pl_field_record(
            field_record if field_record is not None else getattr(placement,"pl_field_record",{})
        ))
        if before != after:
            self.undo_stack.push(EditSymbolCommand(self,placement.uid,before,after,"Konfigurer PL-dåse"))
        else:
            placement.pl_box_entries=deepcopy(normalized_entries)
            placement.pl_box_wiring=deepcopy(normalized_wiring)
            placement.pl_box_splices=deepcopy(normalized_splices)
            placement.pl_box_orientation=after["pl_box_orientation"]
            placement.lamp_outlet_type=after["lamp_outlet_type"]
            placement.pl_field_record=deepcopy(after["pl_field_record"])
            self._refresh_pl_box_group(placement)

    # Kompatibilitetswrapper for ældre interne kald/tests.
    def _apply_pl_box_entries(self, placement, entries) -> None:
        self._apply_pl_box_config(placement,entries,getattr(placement,"pl_box_wiring",[]),splices=getattr(placement,"pl_box_splices",[]),orientation=getattr(placement,"pl_box_orientation",0))

    def open_pl_box_dialog(self, placement) -> None:
        if placement is None or placement.symbol != "light_connection":
            return
        if bool(getattr(placement,"locked",False)):
            QMessageBox.information(self,"PL-dåse","Lampestedet er låst. Lås symbolet op i Egenskaber før PL-dåsen ændres.")
            return
        from elplan_qt.qt_pl_box import PLBoxDialog
        dlg=PLBoxDialog(self,placement,self.project.cables,lambda entries,wiring,outlet_type,splices,orientation,field_record:self._apply_pl_box_config(placement,entries,wiring,outlet_type,splices,orientation,field_record),placements=self.project.placements,cable_categories=self._cable_categories())
        dlg.exec()
        self._refresh_pl_box_group(placement)

    def open_pl_box_for_selection(self) -> None:
        item=self._selected_symbol_item()
        if item is not None:
            self.open_pl_box_dialog(item.placement)

    def _select_connected_cable_from_properties(self) -> None:
        if not hasattr(self,"symbol_cables_combo"):
            return
        cable=self._cable_by_uid(str(self.symbol_cables_combo.currentData() or ""))
        if cable is None:return
        item=self.cable_items.get(id(cable))
        if item is None:return
        self.scene.clearSelection(); item.setSelected(True)
        self._selection_changed()

    def _placement_by_uid(self, uid: str):
        item=self.symbol_items.get(str(uid or ""))
        if item is not None:
            return item.placement
        return next((p for p in self.project.placements if p.uid == uid), None)

    def _anchor_cable_connections(self, cable: core.CablePlacement, only_uid: str | None = None) -> bool:
        """Lås alle registrerede kabelpunkter til deres faktiske symbolporte.

        Kun frie geometripunkter ved siden af et anker må justeres for at bevare
        90°-føring. Et andet fysisk anker flyttes aldrig som bivirkning.
        """
        rows=core.cable_symbol_connections(cable)
        if not rows or not cable.points:
            return False
        pts=[tuple(map(float,p)) for p in cable.points]
        connected_indices={int(r.get("point_index",-1)) for r in rows}
        changed=False
        for rec in rows:
            uid=str(rec.get("symbol_uid","") or "")
            if only_uid is not None and uid != str(only_uid):
                continue
            placement=self._placement_by_uid(uid)
            if placement is None:
                continue
            ports=core.placement_connection_ports(placement)
            if not ports:
                continue
            idx=int(rec.get("point_index",-1))
            if not (0 <= idx < len(pts)):
                continue
            port=min(max(int(rec.get("symbol_port",0) or 0),0),len(ports)-1)
            target=(float(ports[port][0]),float(ports[port][1]))
            old=pts[idx]
            if math.hypot(target[0]-old[0],target[1]-old[1]) <= 1e-12:
                continue
            if bool(cable.orthogonal):
                if idx>0 and (idx-1) not in connected_indices:
                    prev=pts[idx-1]
                    was_h=abs(old[0]-prev[0]) >= abs(old[1]-prev[1])
                    pts[idx-1]=(prev[0],target[1]) if was_h else (target[0],prev[1])
                if idx<len(pts)-1 and (idx+1) not in connected_indices:
                    nxt=pts[idx+1]
                    was_h=abs(nxt[0]-old[0]) >= abs(nxt[1]-old[1])
                    pts[idx+1]=(nxt[0],target[1]) if was_h else (target[0],nxt[1])
            pts[idx]=target
            changed=True
        if changed:
            cable.points=pts
            core.set_cable_symbol_connections(cable,rows)
        return changed

    def _repair_cable_symbol_anchors(self) -> bool:
        """Reparer alle fysiske kabelankre, fx efter projekter gemt i 0.43.0/0.43.2."""
        changed=False
        for cable in self.project.cables:
            changed=self._anchor_cable_connections(cable) or changed
        return changed

    def _refresh_connected_cables(self, uid: str, *, finalize: bool = True) -> bool:
        """Følg et flyttet symbol for alle tilslutninger langs samme kabel."""
        drag_candidates=self._symbol_drag_cables.get(str(uid)) if self._symbol_drag_cables else None
        candidates=drag_candidates if drag_candidates is not None else self.project.cables
        changed=[]
        for cable in candidates:
            if self._anchor_cable_connections(cable,uid):
                changed.append(cable)
        if changed and finalize:
            self._rebuild_cable_visual_cache(refresh_items=True)
            if self.selected_cable is not None:
                self._load_selected_cable_into_panel(self.selected_cable)
        elif changed:
            # During drag, only repaint the physical cables that actually moved.
            # Stable parallel lanes and bundle badges are rebuilt once on release.
            self._symbol_drag_cables_changed=True
            for cable in changed:
                item=self.cable_items.get(id(cable))
                if item is not None:
                    item.set_visual_points(cable.points,refresh=False)
                    item.refresh(update_handles=False)
        return bool(changed)

    def rotate_selected_90(self) -> None:
        selected = [x for x in self.scene.selectedItems() if isinstance(x, ElectricalSymbolItem) and not x.placement.locked]
        if not selected:
            self._set_status("Vælg et symbol først.")
            return
        self.undo_stack.beginMacro("Rotér symboler +90°" if len(selected) > 1 else "Rotér symbol +90°")
        try:
            for item in selected:
                p = item.placement
                old = (p.x, p.y, p.rotation)
                new = (p.x, p.y, (p.rotation + 90.0) % 360.0)
                self.undo_stack.push(MoveSymbolCommand(self, p.uid, old, new, already_applied=False))
        finally:
            self.undo_stack.endMacro()

    def _association_snapshot(self) -> dict[str, dict]:
        return {
            p.uid: {
                "associations": list(core.normalize_associations(getattr(p, "associations", []))),
                "association_channels": list(core.association_channel_letters(p)) if core.association_role(p.symbol)=="switch" else [],
                "light_outputs": [dict(row) for row in core.light_output_records(p)] if p.symbol=="light_connection" else [],
                "parent_light_output_id": str(getattr(p,"parent_light_output_id","") or "") if p.symbol=="spot" else "",
            }
            for p in self.project.placements
        }

    def _apply_association_state(self, state: dict[str, dict]) -> None:
        for p in self.project.placements:
            if p.uid not in state:
                continue
            value=state[p.uid]
            # Backwards compatibility with old undo snapshots that were bare lists.
            if isinstance(value,dict):
                if p.symbol=="light_connection":
                    p.light_outputs=core.normalize_light_outputs(
                        value.get("light_outputs",[]),value.get("associations",[])
                    )
                    core.sync_light_outputs(p,p.light_outputs)
                else:
                    p.associations=(
                        core.normalize_light_associations(value.get("associations",[]))
                        if core.association_role(p.symbol)=="light"
                        else core.normalize_associations(value.get("associations",[]))
                    )
                if core.association_role(p.symbol)=="switch":
                    p.association_channels=core.normalize_association_channels(
                        p.symbol,value.get("association_channels",[]),p.associations
                    )
                    core.sync_association_channels(p,p.association_channels)
                else:
                    p.association_channels=[]
                if p.symbol=="spot":p.parent_light_output_id=str(value.get("parent_light_output_id","") or "")
            else:
                if p.symbol=="light_connection":
                    p.light_outputs=core.normalize_light_outputs([],value)
                    core.sync_light_outputs(p,p.light_outputs)
                else:
                    p.associations=(
                        core.normalize_light_associations(value)
                        if core.association_role(p.symbol)=="light"
                        else core.normalize_associations(value)
                    )
                if core.association_role(p.symbol)=="switch":
                    p.association_channels=core.normalize_association_channels(p.symbol,[],p.associations)
                    core.sync_association_channels(p,p.association_channels)
            if p.symbol=="light_connection":
                symbol_item=self.symbol_items.get(p.uid)
                if symbol_item is not None:symbol_item.refresh_geometry()
        self._sync_spot_parent_associations()
        for ann in self.annotation_items.values():
            ann.refresh()
        self._refresh_switch_association_badges()
        self.project.dirty = True
        self._update_title()
        self._selection_changed()

    def _clear_relation_overview(self) -> None:
        for item in list(self.relation_overview_items):
            if item is not None and item.scene() is not None:
                self.scene.removeItem(item)
        self.relation_overview_items.clear()

    def _refresh_relation_overview(self, selected: core.Placement | None) -> None:
        self._clear_relation_overview()
        if self.annotation_display_mode=="Skjult":
            return
        if selected is None:
            return
        # Spots with a parent use the teal Spot→lampested overview instead.
        if selected.symbol=="spot" and str(getattr(selected,"parent_light_uid","") or ""):
            return
        role=core.association_role(selected.symbol)
        if role not in ("switch","light"):
            return
        letters=set(core.light_output_associations(selected) if role=="light" else core.normalize_associations(selected.associations))
        if not letters:
            return
        source_item=self.symbol_items.get(selected.uid)
        if source_item is None:
            return
        start=source_item.sceneBoundingRect().center()
        targets=[]
        for p in self.project.placements:
            if p.uid==selected.uid:
                continue
            other_role=core.association_role(p.symbol)
            if role=="switch" and other_role!="light":
                continue
            if role=="light" and other_role!="switch":
                continue
            # Linked spots are represented through the lampested relation.
            if role=="switch" and p.symbol=="spot" and str(getattr(p,"parent_light_uid","") or ""):
                continue
            other_letters=(core.light_output_associations(p) if other_role=="light" else core.normalize_associations(p.associations))
            shared=letters.intersection(other_letters)
            if not shared:
                continue
            item=self.symbol_items.get(p.uid)
            if item is None or not item.isVisible():
                continue
            targets.append((p,item,shared))
        for p,item,shared in targets:
            path=QPainterPath(start)
            path.lineTo(item.sceneBoundingRect().center())
            line=QGraphicsPathItem(path)
            pen=QPen(QColor(75,131,189,145)); pen.setCosmetic(True); pen.setWidthF(0.85); pen.setStyle(Qt.PenStyle.DotLine)
            line.setPen(pen); line.setZValue(1390); line.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self.scene.addItem(line); self.relation_overview_items.append(line)

    def _sync_spot_parent_associations(self) -> None:
        by_uid = {p.uid: p for p in self.project.placements}
        for p in self.project.placements:
            parent_uid = str(getattr(p, "parent_light_uid", "") or "")
            if not parent_uid:
                continue
            parent = by_uid.get(parent_uid)
            if parent is None or parent.symbol != "light_connection":
                p.parent_light_uid = ""
                p.parent_light_output_id = ""
            else:
                output=core.light_output_by_id(parent,getattr(p,"parent_light_output_id","") or "")
                p.parent_light_output_id=str(output.get("id","") or "")
                p.associations=core.normalize_light_associations([output.get("association","")])

    def _cleanup_orphan_associations(self) -> None:
        switch_letters = set(); light_letters = set()
        for p in self.project.placements:
            vals = (core.light_output_associations(p) if core.association_role(p.symbol)=="light" else core.normalize_associations(getattr(p,"associations",[])))
            if core.association_role(p.symbol) == "switch": switch_letters.update(vals)
            elif core.association_role(p.symbol) == "light": light_letters.update(vals)
        valid = switch_letters & light_letters
        for p in self.project.placements:
            role=core.association_role(p.symbol)
            if role=="switch":
                channels=[a if a in valid else "" for a in core.association_channel_letters(p)]
                core.sync_association_channels(p,channels)
            elif role=="light":
                if p.symbol=="light_connection":
                    rows=core.light_output_records(p)
                    for row in rows:
                        if row.get("association","") not in valid:row["association"]=""
                    core.sync_light_outputs(p,rows)
                else:
                    p.associations=core.normalize_light_associations([a for a in core.normalize_associations(p.associations) if a in valid])
                p.association_channels=[]
        self._sync_spot_parent_associations()

    def _clear_association_visuals(self) -> None:
        for overlay in list(self.association_target_overlays):
            if overlay.scene() is not None:
                self.scene.removeItem(overlay)
        self.association_target_overlays.clear()
        self.association_target_overlay_by_uid.clear()
        if self.association_guide is not None and self.association_guide.scene() is not None:
            self.scene.removeItem(self.association_guide)
        if self.association_badge is not None and self.association_badge.scene() is not None:
            self.scene.removeItem(self.association_badge)
        if self.association_source_overlay is not None and self.association_source_overlay.scene() is not None:
            self.scene.removeItem(self.association_source_overlay)
        self.association_guide = None
        self.association_badge = None
        self.association_source_overlay = None

    def _refresh_association_source_picker(self) -> None:
        self._clear_association_visuals()
        scale = max(self.view.current_scale(), 1e-9)
        margin = 7.0 / scale
        for p in self.project.placements:
            if core.association_role(p.symbol) != "switch":
                continue
            item = self.symbol_items.get(p.uid)
            if item is None or not item.isVisible():
                continue
            rect = item.sceneBoundingRect().adjusted(-margin, -margin, margin, margin)
            overlay = QGraphicsRectItem(rect)
            pen = QPen(QColor("#e28a20"))
            pen.setCosmetic(True); pen.setWidthF(1.5); pen.setStyle(Qt.PenStyle.DashLine)
            overlay.setPen(pen)
            overlay.setBrush(QBrush(QColor(226, 138, 32, 20)))
            overlay.setZValue(1450)
            overlay.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self.scene.addItem(overlay)
            self.association_target_overlays.append(overlay)
        self.association_badge = QGraphicsSimpleTextItem("1. Klik en afbryder")
        self.association_badge.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.association_badge.setBrush(QBrush(QColor("#f0ad59") if _canvas_dark() else QColor("#a45c08")))
        self.association_badge.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        self.association_badge.setZValue(1460)
        if self.view.last_mouse_scene is not None:
            self.association_badge.setPos(self.view.last_mouse_scene + QPointF(10.0/scale, -24.0/scale))
        else:
            self.association_badge.setPos(self.view.mapToScene(self.view.viewport().rect().center()))
        self.scene.addItem(self.association_badge)

    def _association_anchor(self, source: core.Placement, channel_index: int):
        item=self.symbol_items.get(source.uid)
        if item is None:
            return None, 0.0
        rec=core.association_channel_module(source.symbol, source.size, channel_index)
        if rec is None:
            return item.sceneBoundingRect().center(), max(source.size*0.25,1.0)
        _module_no,_base,x,y,radius,_indices=rec
        return item.mapToScene(QPointF(x,-y)), max(float(radius)*1.65, source.size*0.18)

    def _clear_switch_association_badges(self) -> None:
        for badge in list(self.switch_association_badges):
            if badge.scene() is not None:
                self.scene.removeItem(badge)
        self.switch_association_badges.clear()
        self._switch_badge_render_signature=None

    def _refresh_switch_association_badges(self) -> None:
        refresh_switch_association_badges(self)

    def _association_target_allowed(self,p:core.Placement)->bool:
        if core.association_role(p.symbol)!="light":
            return False
        # Spots that belong to a lampested inherit its relations and should be
        # controlled via the lampested rather than creating a duplicate direct link.
        if p.symbol=="spot" and str(getattr(p,"parent_light_uid","") or ""):
            return False
        return True

    def _association_target_count(self,letter:str)->int:
        if not letter:return 0
        return sum(
            sum(1 for row in core.light_output_records(p) if str(row.get("association","") or "")==letter)
            for p in self.project.placements if self._association_target_allowed(p)
        )

    def _association_target_caption(self,letter:str)->str:
        targets=[]
        for p in self.project.placements:
            if not self._association_target_allowed(p):continue
            ident=" · ".join(x for x in (str(getattr(p,"group","") or "").strip(),str(getattr(p,"label","") or "").strip()) if x)
            outputs=[row for row in core.light_output_records(p) if str(row.get("association","") or "")==str(letter or "")]
            for output in outputs:
                suffix=f" / {output.get('name')}" if len(core.light_output_records(p))>1 else ""
                targets.append((ident or core.symbol_display_name(p.symbol))+suffix)
        if not targets:return "Ingen"
        shown=targets[:2]
        return ", ".join(shown)+(f" +{len(targets)-2}" if len(targets)>2 else "")

    def _refresh_association_channel_table(self,p:core.Placement|None) -> None:
        table=self.assoc_channels_table
        table.setRowCount(0)
        if p is None or core.association_role(getattr(p,"symbol",""))!="switch":
            table.hide(); return
        records=core.association_channel_records(p)
        table.setRowCount(len(records)); table.show()
        preferred=self.association_channel_index if self.association_source_uid==p.uid else core.first_unassigned_association_channel(p)
        if preferred is None:preferred=0
        for row,rec in enumerate(records):
            letter=str(rec.get("association","") or "")
            values=[str(rec.get("channel_caption","") or f"Betjening {row+1}"),letter or "Ledig",self._association_target_caption(letter) if letter else "Ingen"]
            for col,value in enumerate(values):
                cell=QTableWidgetItem(value); cell.setData(Qt.ItemDataRole.UserRole,int(rec.get("channel_index",row)))
                if col==1:cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row,col,cell)
        table.resizeRowsToContents()
        table_height=min(190,34+max(1,len(records))*31)
        table.setMinimumHeight(table_height); table.setMaximumHeight(table_height)
        if records:
            row=max(0,min(int(preferred),len(records)-1)); table.setCurrentCell(row,0)

    def _refresh_light_outputs_table(self,p:core.Placement|None) -> None:
        table=self.light_outputs_table
        table.setRowCount(0)
        is_outlet=bool(p is not None and p.symbol=="light_connection")
        table.setVisible(is_outlet); self.light_outputs_actions.setVisible(is_outlet)
        if not is_outlet:return
        outputs=core.light_output_records(p)
        table.setRowCount(len(outputs))
        for row,output in enumerate(outputs):
            values=[f"T{row+1}",str(output.get("association","") or "Ledig"),str(output.get("name","") or f"Tænding {row+1}")]
            for col,value in enumerate(values):
                cell=QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole,str(output.get("id","") or ""))
                if col in (0,1):cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row,col,cell)
        table.resizeRowsToContents()
        height=min(190,34+max(1,len(outputs))*31)
        table.setMinimumHeight(height); table.setMaximumHeight(height)
        if outputs:table.setCurrentCell(0,0)
        self.light_output_add_button.setEnabled(True)
        self.light_output_remove_button.setEnabled(len(outputs)>1)

    def _selected_light_output_id(self)->str:
        row=self.light_outputs_table.currentRow()
        item=self.light_outputs_table.item(row,0) if row>=0 else None
        return str(item.data(Qt.ItemDataRole.UserRole) or "") if item is not None else ""

    def _add_light_output(self)->None:
        item=self._selected_symbol_item(); p=item.placement if item is not None else None
        if p is None or p.symbol!="light_connection":return
        before=self._association_snapshot(); rows=core.light_output_records(p)
        used={str(row.get("id","") or "") for row in rows}; index=len(rows)+1
        output_id=f"out{index}"
        while output_id in used:index+=1; output_id=f"out{index}"
        rows.append({"id":output_id,"name":f"Tænding {len(rows)+1}","association":""})
        core.sync_light_outputs(p,rows); after=self._association_snapshot()
        self.undo_stack.push(AssociationCommand(self,before,after,"Tilføj tænding til lampested"))
        self._set_status(f"Lampestedet har nu {len(rows)} uafhængige tændinger, men tæller stadig som ét fysisk udtag.")

    def _remove_selected_light_output(self)->None:
        item=self._selected_symbol_item(); p=item.placement if item is not None else None
        if p is None or p.symbol!="light_connection":return
        rows=core.light_output_records(p)
        if len(rows)<=1:return
        output_id=self._selected_light_output_id() or str(rows[-1].get("id","") or "")
        target=next((row for row in rows if str(row.get("id","") or "")==output_id),rows[-1])
        if target.get("association",""):
            answer=QMessageBox.question(self,"Fjern tænding",f"{target.get('name','Tændingen')} har tilhørsbogstav {target.get('association')}. Vil du fjerne udgangen?")
            if answer!=QMessageBox.StandardButton.Yes:return
        before=self._association_snapshot(); rows=[row for row in rows if str(row.get("id","") or "")!=output_id]
        core.sync_light_outputs(p,rows)
        for spot in self.project.placements:
            if spot.symbol=="spot" and str(getattr(spot,"parent_light_uid","") or "")==p.uid and str(getattr(spot,"parent_light_output_id","") or "")==output_id:
                replacement=rows[0]; spot.parent_light_output_id=str(replacement.get("id","") or ""); spot.associations=core.normalize_light_associations([replacement.get("association","")])
        after=self._association_snapshot(); self.undo_stack.push(AssociationCommand(self,before,after,"Fjern tænding fra lampested"))

    def _rename_selected_light_output(self)->None:
        item=self._selected_symbol_item(); p=item.placement if item is not None else None
        if p is None or p.symbol!="light_connection":return
        output_id=self._selected_light_output_id(); rows=core.light_output_records(p)
        output=next((row for row in rows if str(row.get("id","") or "")==output_id),None)
        if output is None:return
        name,ok=QInputDialog.getText(self,"Navngiv tænding","Navn, fx Pendel eller Spots:",text=str(output.get("name","") or ""))
        if not ok:return
        name=str(name or "").strip()
        if not name:return
        before=self._association_snapshot(); output["name"]=name; core.sync_light_outputs(p,rows); after=self._association_snapshot()
        self.undo_stack.push(AssociationCommand(self,before,after,"Navngiv tænding"))

    def _selected_association_channel_index(self,p:core.Placement)->int:
        row=self.assoc_channels_table.currentRow()
        if row>=0:
            item=self.assoc_channels_table.item(row,0)
            if item is not None:
                try:return max(0,min(int(item.data(Qt.ItemDataRole.UserRole)),core.association_capacity(p.symbol)-1))
                except (TypeError,ValueError):pass
        next_index=core.first_unassigned_association_channel(p)
        return int(next_index if next_index is not None else 0)

    def _start_selected_association_channel(self)->None:
        item=self._selected_symbol_item()
        if item is None or core.association_role(item.placement.symbol)!="switch":
            self.start_association_mode(); return
        self._activate_association_source(item,self._selected_association_channel_index(item.placement))

    def _refresh_association_visuals(self,*,refresh_badges:bool=True) -> None:
        self._clear_association_visuals()
        source=self._placement_by_uid(self.association_source_uid)
        source_item=self.symbol_items.get(self.association_source_uid)
        if source is None or source_item is None:return
        scale=max(self.view.current_scale(),1e-9)
        margin=7.0/scale
        active=str(self.association_active_letter or "")
        source_anchor,source_radius=self._association_anchor(source,self.association_channel_index)
        if source_anchor is not None:
            self.association_source_overlay=QGraphicsEllipseItem(
                source_anchor.x()-source_radius, source_anchor.y()-source_radius,
                source_radius*2.0, source_radius*2.0
            )
            spen=QPen(QColor("#e58a14")); spen.setCosmetic(True); spen.setWidthF(2.6); spen.setStyle(Qt.PenStyle.SolidLine)
            self.association_source_overlay.setPen(spen); self.association_source_overlay.setBrush(QBrush(QColor(245,158,11,32)))
            self.association_source_overlay.setZValue(1455); self.association_source_overlay.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self.scene.addItem(self.association_source_overlay)
        for p in self.project.placements:
            if not self._association_target_allowed(p):
                continue
            item=self.symbol_items.get(p.uid)
            if item is None or not item.isVisible():continue
            rect=item.sceneBoundingRect().adjusted(-margin,-margin,margin,margin)
            overlay=QGraphicsRectItem(rect)
            self._style_association_target_overlay(p,overlay,active)
            overlay.setZValue(1450); overlay.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self.scene.addItem(overlay); self.association_target_overlays.append(overlay)
            self.association_target_overlay_by_uid[p.uid]=overlay

        self.association_guide=QGraphicsPathItem()
        pen=QPen(QColor("#2b84d6")); pen.setCosmetic(True); pen.setWidthF(1.2); pen.setStyle(Qt.PenStyle.DashLine)
        self.association_guide.setPen(pen); self.association_guide.setZValue(1440)
        self.association_guide.setAcceptedMouseButtons(Qt.MouseButton.NoButton); self.scene.addItem(self.association_guide)

        if active:
            caption=core.association_channel_caption(source.symbol,self.association_channel_index)
            label=f"{caption} · {active}: blå=valgt · turkis=ledig · orange=flyttes"
        elif self.association_guided_setup:
            cap=core.association_capacity(source.symbol)
            step=self.association_channel_index+1
            caption=core.association_channel_caption(source.symbol,self.association_channel_index)
            label=f"{caption} · {step}/{cap}: klik lys"
        else:
            label="Klik første lys · nyt/eksisterende tilhørsforhold"
        self.association_badge=QGraphicsSimpleTextItem(label)
        self.association_badge.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations,True)
        self.association_badge.setBrush(QBrush(QColor("#8bc7f2") if _canvas_dark() else QColor("#155f9f")))
        self.association_badge.setFont(QFont("Segoe UI",8,QFont.Weight.DemiBold)); self.association_badge.setZValue(1460)
        c=source_anchor if source_anchor is not None else source_item.sceneBoundingRect().center()
        self.association_badge.setPos(c+QPointF(12.0/scale,-28.0/scale)); self.scene.addItem(self.association_badge)
        if refresh_badges:self._refresh_switch_association_badges()
        elif not self.association_source_uid:self._symbol_metadata_refresh_timer.start()
        if self.view.last_mouse_scene is not None:self._association_mouse_moved(self.view.last_mouse_scene)

    def _style_association_target_overlay(
        self,p:core.Placement,overlay:QGraphicsRectItem,active:str|None=None
    )->None:
        active=str(self.association_active_letter if active is None else active or "")
        target_letters=core.light_output_associations(p)
        linked=bool(active and active in target_letters)
        occupied=bool(target_letters and not linked)
        color="#126bc4" if linked else ("#d97706" if occupied else "#0f9f91")
        pen=QPen(QColor(color)); pen.setCosmetic(True); pen.setWidthF(2.0 if linked else 1.3)
        pen.setStyle(Qt.PenStyle.SolidLine if linked else Qt.PenStyle.DashLine)
        overlay.setPen(pen)
        fill=QColor(color); fill.setAlpha(55 if linked else 18)
        overlay.setBrush(QBrush(fill))

    def _refresh_association_target_visual(self,target:core.Placement)->None:
        """Repaint one changed target without rebuilding every hit outline."""
        overlay=self.association_target_overlay_by_uid.get(target.uid)
        if overlay is None:
            self._refresh_association_visuals(refresh_badges=False)
            return
        self._style_association_target_overlay(target,overlay)
        overlay.update()
        if self.view.last_mouse_scene is not None:self._association_mouse_moved(self.view.last_mouse_scene)

    def _association_mouse_moved(self, scene_pos: QPointF) -> None:
        if self.association_pick_source:
            if self.association_badge is not None:
                scale=max(self.view.current_scale(),1e-9)
                self.association_badge.setPos(scene_pos + QPointF(10.0/scale,-24.0/scale))
            return
        if not self.association_source_uid or self.association_guide is None:
            return
        source_item = self.symbol_items.get(self.association_source_uid)
        if source_item is None:
            return
        source=self._placement_by_uid(self.association_source_uid)
        start,_radius=self._association_anchor(source,self.association_channel_index) if source is not None else (None,0.0)
        if start is None:
            start=source_item.sceneBoundingRect().center()
        path = QPainterPath(start)
        path.lineTo(scene_pos)
        self.association_guide.setPath(path)

    def _choose_switch_association_channel(self,p:core.Placement)->tuple[str,int]|None:
        channels=core.association_channel_letters(p)
        cap=core.association_capacity(p.symbol)
        assigned=[(i,letter) for i,letter in enumerate(channels) if letter]
        next_index=core.first_unassigned_association_channel(p)
        if not assigned:
            return "", (next_index if next_index is not None else 0)
        if cap<=1:
            return assigned[0][1],assigned[0][0]

        options=[]; mapping=[]
        if next_index is not None:
            caption=core.association_channel_caption(p.symbol,next_index)
            options.append(f"+ Fortsæt med {caption}")
            mapping.append(("__NEW__",next_index))
        for i,letter in assigned:
            options.append(f"{core.association_channel_caption(p.symbol,i)}: {letter}")
            mapping.append((letter,i))
        choice,ok=QInputDialog.getItem(
            self,"Vælg betjening",
            "Vælg den fysiske betjening, du vil tilknytte/redigere. "
            "Kombisymboler holder nu hvert modul adskilt.",
            options,0,False
        )
        if not ok:return None
        try:return mapping[options.index(choice)]
        except Exception:return mapping[0] if mapping else ("",0)

    def _choose_light_output(self,target:core.Placement,active_letter:str="")->str|None:
        outputs=core.light_output_records(target)
        if len(outputs)<=1:return str(outputs[0].get("id","") or "")
        if active_letter:
            matches=[row for row in outputs if str(row.get("association","") or "")==active_letter]
            if len(matches)==1:return str(matches[0].get("id","") or "")
        options=[]; mapping=[]
        for index,row in enumerate(outputs,1):
            assoc=str(row.get("association","") or "ledig")
            options.append(f"T{index} · {row.get('name') or f'Tænding {index}'} · {assoc}")
            mapping.append(str(row.get("id","") or ""))
        choice,ok=QInputDialog.getItem(
            self,"Vælg tænding","Lampestedet har flere uafhængige udgange. Vælg den udgang, afbryderen skal betjene:",options,0,False
        )
        if not ok:return None
        try:return mapping[options.index(choice)]
        except Exception:return mapping[0] if mapping else None

    def _choose_first_target_letter(
        self,target:core.Placement,*,source:core.Placement,channel_index:int,output_id:str=""
    )->str|None:
        source_existing=set(core.normalize_associations(source.associations))
        output=core.light_output_by_id(target,output_id) if target.symbol=="light_connection" else core.light_output_records(target)[0]
        existing=[
            letter for letter in core.normalize_associations([output.get("association","")])
            if letter not in source_existing
        ]
        new_letter=core.next_association_letter(self.project.placements)
        prefer_existing=core.association_channel_prefers_existing(source.symbol,channel_index)

        # Korrespondance/krydsning skal normalt dele samme funktion. Hvis der kun
        # findes ét muligt tilhørsforhold på lampestedet, er valget entydigt og
        # guiden kan fortsætte uden en unødvendig dialog.
        if prefer_existing and len(existing)==1:
            return existing[0]
        if not existing:
            return new_letter

        existing_options=[f"Brug eksisterende ({letter})" for letter in existing]
        new_option=f"Nyt tilhørsforhold ({new_letter})"
        options=(existing_options+[new_option]) if prefer_existing else ([new_option]+existing_options)
        explanation=(
            "Korrespondance/krydsning deler normalt samme tilhørsforhold. "
            "Vælg eksisterende, hvis afbryderne skal betjene samme lys."
            if prefer_existing else
            "Vælg nyt tilhørsforhold for en uafhængig tænding, eller del et eksisterende tilhørsforhold."
        )
        choice,ok=QInputDialog.getItem(
            self,"Lampested har allerede tilhørsforhold",explanation,options,0,False
        )
        if not ok:return None
        if choice.startswith("Nyt"):return new_letter
        for letter in existing:
            if f"({letter})" in choice:return letter
        return existing[0] if prefer_existing else new_letter

    def _sync_association_session_ui(self)->None:
        """Keep save/cancel controls and click-only canvas behavior in sync."""
        active=bool(self.association_source_uid or self.association_pick_source)
        can_save=bool(self.association_source_uid)
        self.view.set_association_mode_active(can_save)
        action=getattr(self,"act_finish_association",None)
        if action is not None:action.setEnabled(can_save)
        edit_actions=getattr(self,"assoc_edit_actions",None)
        if edit_actions is not None:edit_actions.setVisible(not active)
        session_actions=getattr(self,"assoc_session_actions",None)
        if session_actions is not None:session_actions.setVisible(active)
        save_button=getattr(self,"assoc_save_button",None)
        if save_button is not None:
            save_button.setEnabled(can_save)
            save_button.setText("Gem tilknytning" if can_save else "Vælg afbryder på tegningen…")
        for symbol_item in self.symbol_items.values():
            if bool(getattr(symbol_item,"workflow_click_only",False))!=active:
                symbol_item.workflow_click_only=active
        if hasattr(self,"_refresh_workflow_bar"):self._refresh_workflow_bar()

    def _refresh_association_annotations(self,*uids:str)->None:
        """Refresh only labels whose relation changed; defer global layout."""
        wanted={str(uid or "") for uid in uids if str(uid or "")}
        for uid in wanted:
            ann=self.annotation_items.get(uid)
            if ann is not None:ann.refresh()
        # Collision layout and the complete switch-badge pass are deliberately
        # deferred until commit/cancel. The active overlay already gives live
        # feedback, so a plan-wide layout after every target click adds latency
        # without helping the current decision.
        if not self.association_source_uid:self._symbol_metadata_refresh_timer.start()

    def _finish_association_mode(self,source_uid:str,status:str,*,commit:bool=True)->None:
        before=self._association_session_before
        dirty_before=bool(self._association_session_dirty_before)
        after=None
        if commit and before is not None:
            self._cleanup_orphan_associations()
            after=self._association_snapshot()
        self.association_source_uid=""
        self.association_active_letter=""
        self.association_force_new=False
        self.association_pick_source=False
        self.association_guided_setup=False
        self.association_channel_index=0
        self._association_session_before=None
        self._association_session_dirty_before=False
        self._sync_association_session_ui()
        self._clear_association_visuals()
        self._refresh_switch_association_badges()
        self.view.unsetCursor()
        if not commit and before is not None:
            self._apply_association_state(before)
            self.project.dirty=dirty_before; self._update_title()
        elif commit and before is not None and before!=after:
            self.undo_stack.push(AssociationCommand(self,before,after,"Redigér lystilhørsforhold"))
        elif before is not None:
            self.project.dirty=dirty_before; self._update_title()
        self._set_status(status)
        if source_uid:
            QTimer.singleShot(0,lambda uid=source_uid:self._reselect_uid(uid))

    def _activate_association_source(self,item:ElectricalSymbolItem,channel_index:int|None=None)->None:
        p=item.placement
        channels=core.association_channel_letters(p)
        cap=core.association_capacity(p.symbol)
        if channel_index is None:
            choice=self._choose_switch_association_channel(p)
        else:
            idx=max(0,min(int(channel_index),max(0,cap-1)))
            choice=(channels[idx] if idx<len(channels) and channels[idx] else "__NEW__",idx)
        if choice is None:
            self._finish_association_mode(p.uid,"Tilknytningsguiden blev annulleret.",commit=False)
            return
        active,channel_index=choice

        self.association_pick_source=False
        self.association_source_uid=p.uid
        # Guidet opsætning bruges kun når der mangler fysiske kanaler.
        self.association_guided_setup=(cap>1 and (not any(channels) or active=="__NEW__"))
        self.association_channel_index=channel_index
        self.association_active_letter="" if active in ("","__NEW__") else active
        self.association_force_new=False
        self._association_session_before=self._association_snapshot()
        self._association_session_dirty_before=bool(self.project.dirty)

        self.view.cancel_tool(emit_signal=False); self.view.setCursor(Qt.CursorShape.CrossCursor)
        self.view.setFocus(Qt.FocusReason.OtherFocusReason)
        self._sync_association_session_ui()
        self._refresh_association_visuals()
        caption=core.association_channel_caption(p.symbol,self.association_channel_index)
        if self.association_active_letter:
            count=self._association_target_count(self.association_active_letter)
            self._set_status(
                f"{caption} · tilhørsforhold {self.association_active_letter} · {count} lys. "
                "Klik BLÅ lys til/fra · Enter gemmer · Esc annullerer"
            )
        elif self.association_guided_setup:
            completed=core.assigned_association_channel_count(p)
            self._set_status(
                f"Tilknyt lys — {caption} ({completed+1}/{cap}): klik et BLÅT lampested/lampe."
            )
        else:
            self._set_status(
                f"{caption}: klik første BLÅ lampested/lampe. "
                "Enter gemmer hele ændringen · Esc annullerer."
            )

    def start_association_mode(self)->None:
        self._stop_cable_marking_for_other_tool(); item=self._selected_symbol_item()
        if item is not None and core.association_role(item.placement.symbol)=="switch":
            self._activate_association_source(item,self._selected_association_channel_index(item.placement));return
        self.association_source_uid=""
        self.association_active_letter=""
        self.association_force_new=False
        self.association_guided_setup=False
        self.association_channel_index=0
        self._association_session_before=None
        self._association_session_dirty_before=False
        self.association_pick_source=True
        self._sync_association_session_ui()
        self.view.cancel_tool(emit_signal=False); self.view.setCursor(Qt.CursorShape.CrossCursor)
        self._refresh_association_source_picker()
        self._set_status(
            "Tilknyt lys — trin 1: klik en ORANGE afbryder. "
            "Flerfunktionsafbrydere guides automatisk gennem alle tændinger."
        )

    def _finish_active_association(self)->None:
        source=self._placement_by_uid(self.association_source_uid)
        if source is None:return
        assigned=core.assigned_association_channel_count(source)
        targets=sum(self._association_target_count(letter) for letter in core.association_channel_letters(source) if letter)
        self._finish_association_mode(
            source.uid,
            f"Tilknytning gemt · {assigned}/{core.association_capacity(source.symbol)} betjeninger · {targets} lampested(er).",
            commit=True,
        )

    def _symbol_double_clicked(self,item:ElectricalSymbolItem)->None:
        """Dobbeltklik på et lampested åbner PL-dåsens fysiske indføringer."""
        if item is None or item.placement.symbol != "light_connection":
            return
        self.scene.clearSelection(); item.setSelected(True)
        self.open_pl_box_dialog(item.placement)

    def _symbol_clicked(self,item:ElectricalSymbolItem)->None:
        if self.association_pick_source:
            if core.association_role(item.placement.symbol)!="switch":
                self._set_status("Klik på en ORANGE fremhævet afbryder · Esc afslutter")
                return
            self.scene.clearSelection(); item.setSelected(True); self._activate_association_source(item);return

        if self.spot_parent_pending:
            target=item.placement
            if target.symbol!="light_connection":
                self._set_status("Spot → lampested: klik på et TURKIS fremhævet lampested · Esc afslutter")
                return
            output_id=self._choose_light_output(target)
            if output_id is None:return
            output=core.light_output_by_id(target,output_id)
            before=self._spot_parent_snapshot()
            pending=set(self.spot_parent_pending)
            linked=0
            for p in self.project.placements:
                if p.uid in pending and p.symbol=="spot":
                    p.parent_light_uid=target.uid
                    p.parent_light_output_id=output_id
                    p.associations=core.normalize_light_associations([output.get("association","")])
                    linked+=1
            after=self._spot_parent_snapshot()
            self.undo_stack.push(SpotParentCommand(self,before,after,"Tilknyt spots til lampested"))
            self.spot_parent_pending=[]
            self._clear_spot_link_visuals()
            self.view.unsetCursor()
            for ann in self.annotation_items.values():ann.refresh()
            self._refresh_spot_link_visuals(target)
            ident=str(target.group or target.label or "lampested")
            extra=f" · {output.get('name')} · tilhørsforhold {output.get('association')}" if output.get("association","") else f" · {output.get('name')}"
            self._set_status(f"{linked} spot(s) tilknyttet {ident}{extra}.")
            QTimer.singleShot(0,lambda:self._reselect_uid(target.uid))
            return

        if not self.association_source_uid:return
        source=self._placement_by_uid(self.association_source_uid)
        target=item.placement
        if source is None:
            self.association_source_uid=""; self.association_active_letter=""; return
        if target.uid==source.uid:return
        if not self._association_target_allowed(target):
            if target.symbol=="spot" and getattr(target,"parent_light_uid",""):
                self._set_status("Dette spot følger et lampested. Tilknyt afbryderen til lampestedet i stedet.")
            else:
                self._set_status("Klik på et BLÅT fremhævet lampested eller en lampe · Esc afslutter")
            return

        active=str(self.association_active_letter or "")
        output_id=self._choose_light_output(target,active)
        if output_id is None:return
        new_channel_created=False
        channel_index=min(
            max(self.association_channel_index,0),
            max(0,core.association_capacity(source.symbol)-1)
        )
        if not active:
            channels=core.association_channel_letters(source)
            if channel_index >= len(channels):
                self._set_status("Den valgte afbryderkanal findes ikke længere.")
                return
            active=self._choose_first_target_letter(
                target,source=source,channel_index=channel_index,output_id=output_id
            )
            if active is None:return
            new_channel_created=not bool(channels[channel_index])
            if new_channel_created:
                core.set_association_channel(source,channel_index,active)
            self.association_active_letter=active
            self.association_force_new=False

        chosen_output=core.light_output_by_id(target,output_id)
        target_vals=core.normalize_light_associations([chosen_output.get("association","")])
        if new_channel_created:
            # Når et nyt afbrydertrin kobles på et allerede eksisterende
            # tilhørsforhold (typisk korrespondance/krydsning), skal lampestedets
            # bogstav BEVARES. Kanal->bogstav-mappingen på kombiafbryderen gemmes
            # separat og kan derfor ikke længere blive ødelagt af alfabetisk sortering.
            if active not in target_vals:
                if target.symbol=="light_connection":core.set_light_output_association(target,output_id,active)
                else:target.associations=[active]
            action="Tilknyt"
        elif active in target_vals:
            if target.symbol=="light_connection":core.set_light_output_association(target,output_id,"")
            else:target.associations=[]
            action="Fjern"
        else:
            if target.symbol=="light_connection":core.set_light_output_association(target,output_id,active)
            else:target.associations=[active]
            action="Flyt" if target_vals else "Tilknyt"

        self._sync_spot_parent_associations()
        self.project.dirty=True; self._update_title()
        affected=[source.uid,target.uid]
        if target.symbol=="light_connection":
            affected.extend(p.uid for p in self.project.placements if str(getattr(p,"parent_light_uid","") or "")==target.uid)
        self._refresh_association_annotations(*affected)

        # Ved førstegangsopsætning af flerfunktions-/kombiafbrydere går guiden
        # videre til den næste FYSISKE, endnu tomme kanal. Kanalrækkefølgen er
        # uafhængig af om bogstaverne fx ender som b, c, a.
        if self.association_guided_setup and new_channel_created and action=="Tilknyt":
            cap=core.association_capacity(source.symbol)
            completed=core.assigned_association_channel_count(source)
            next_index=core.first_unassigned_association_channel(source)
            if next_index is not None:
                self.association_active_letter=""
                self.association_channel_index=next_index
                self._refresh_association_visuals(refresh_badges=False)
                next_caption=core.association_channel_caption(source.symbol,next_index)
                self._set_status(
                    f"{completed}/{cap} betjeninger gemt · fortsæt med {next_caption} "
                    f"({completed+1}/{cap}): klik et BLÅT lampested/lampe."
                )
                return

            summary=core.association_display(source) or ", ".join(core.normalize_associations(source.associations))
            self._finish_association_mode(
                source.uid,
                f"Tilknytningsguide færdig: {cap}/{cap} betjeninger ({summary}). "
                "Hvert kombimodul er gemt separat.",
                commit=True,
            )
            return

        if new_channel_created:
            # The first click establishes the active letter, so every target
            # changes from neutral/occupied to a letter-specific state.
            self._refresh_association_visuals(refresh_badges=False)
        else:
            self._refresh_association_target_visual(target)
        count=self._association_target_count(active)
        caption=core.association_channel_caption(source.symbol,channel_index)
        self._set_status(
            f"{caption} · {active}: {count} lys valgt. "
            "Klik BLÅ lys til/fra · Enter gemmer · Esc annullerer"
        )

    def _reselect_uid(self, uid: str) -> None:
        blocker=QSignalBlocker(self.scene)
        for item in self.scene.selectedItems():
            item.setSelected(False)
        item = self.symbol_items.get(uid)
        if item:
            item.setSelected(True)
        del blocker
        # Exactly one inspector rebuild after a workflow, even when the
        # selection already pointed at the source symbol.
        self._selection_changed()

    def clear_selected_associations(self) -> None:
        item = self._selected_symbol_item()
        if item is None:
            self._set_status("Vælg en afbryder eller et lys.")
            return
        p = item.placement
        has_association=bool(core.light_output_associations(p) if core.association_role(p.symbol)=="light" else core.normalize_associations(p.associations))
        if not has_association:
            self._set_status("Det valgte symbol har ingen tilhørsforhold.")
            return
        before = self._association_snapshot()
        if p.symbol=="light_connection":
            rows=core.light_output_records(p)
            for row in rows:row["association"]=""
            core.sync_light_outputs(p,rows)
        else:p.associations=[]
        if core.association_role(p.symbol)=="switch":
            p.association_channels=[""]*core.association_capacity(p.symbol)
        self._cleanup_orphan_associations()
        after = self._association_snapshot()
        self.undo_stack.push(AssociationCommand(self, before, after, "Ryd tilhørsforhold"))

    def group_selected_lights_same_switch(self) -> None:
        """Saml flere fysiske lyspunkter på én konkret afbryderkanal."""
        items=[x for x in self.scene.selectedItems() if isinstance(x,ElectricalSymbolItem)]
        lights=[x.placement for x in items]
        if len(lights)<2 or any(not core.light_can_share_switch_group(p) for p in lights):
            QMessageBox.information(
                self,"Samme tænding",
                "Vælg mindst to entydige lampesteder. Et lampested med flere uafhængige udgange skal tilknyttes via den normale tilknytningsguide."
            ); return
        channels=[]
        for switch in self.project.placements:
            if core.association_role(getattr(switch,"symbol",""))!="switch":
                continue
            ident=" · ".join(x for x in (str(getattr(switch,"group","") or "").strip(),str(getattr(switch,"label","") or "").strip()) if x)
            ident=ident or core.symbol_display_name(switch.symbol)
            for rec in core.association_channel_records(switch):
                letter=str(rec.get("association","") or "")
                target_count=self._association_target_count(letter) if letter else 0
                state=f"{letter} · {target_count} lys" if letter else "ledig"
                caption=f"{ident} · {rec.get('channel_caption') or 'Betjening'} · {state}"
                channels.append((caption,switch,int(rec.get("channel_index",0)),letter))
        if not channels:
            QMessageBox.information(self,"Samme tænding","Projektet har ingen afbryderkanaler. Placér en afbryder først."); return

        current={a for p in lights for a in core.light_output_associations(p)}
        preferred=next((i for i,row in enumerate(channels) if row[3] and row[3] in current),0)
        options=[row[0] for row in channels]
        choice,ok=QInputDialog.getItem(
            self,"Samme tænding",
            f"Vælg den afbryderbetjening, som de {len(lights)} fysiske lampesteder skal følge:",
            options,preferred,False
        )
        if not ok:return
        try:_caption,switch,channel_index,letter=channels[options.index(choice)]
        except (ValueError,IndexError):return

        before=self._association_snapshot()
        if not letter:
            letter=core.next_association_letter(self.project.placements)
            core.set_association_channel(switch,channel_index,letter)
        changed=core.set_lights_shared_association(lights,letter)
        self._cleanup_orphan_associations()
        after=self._association_snapshot()
        if before!=after:
            self.undo_stack.push(AssociationCommand(self,before,after,"Saml lampesteder på samme tænding"))
        caption=core.association_channel_caption(switch.symbol,channel_index)
        ident=" · ".join(x for x in (str(getattr(switch,"group","") or "").strip(),str(getattr(switch,"label","") or "").strip()) if x) or core.symbol_display_name(switch.symbol)
        self._notify(
            f"{len(lights)} lampesteder følger nu {ident} · {caption} ({letter})." if changed or before!=after else f"Lampestederne fulgte allerede {ident} · {caption} ({letter}).",
            kind="success"
        )

    # ---------- Free text / direct label editing ----------
    def start_text_dialog(self) -> None:
        if self.doc is None:
            QMessageBox.information(self, "Tekst", "Åbn først en DWG/DXF eller et projekt.")
            return
        dlg=QDialog(self); dlg.setWindowTitle("Tilføj tekst"); dlg.setMinimumWidth(440)
        form=QFormLayout(dlg)
        text=QLineEdit()
        height=QDoubleSpinBox(); height.setRange(1,5000); height.setDecimals(1); height.setSingleStep(10.0); height.setSuffix(" mm")
        height.setValue(float(self.project.raw.get("default_text_height",240.0) or 240.0))
        rot=QDoubleSpinBox(); rot.setRange(-360,360); rot.setValue(0); rot.setSuffix("°")
        color=QPushButton("#202020"); _set_color_button(color,"#202020")
        def choose():
            c=QColorDialog.getColor(QColor(color.text()),dlg,"Tekstfarve")
            if c.isValid():_set_color_button(color,c.name())
        color.clicked.connect(choose)
        form.addRow("Tekst",text); form.addRow("Teksthøjde",height); form.addRow("Rotation [°]",rot); form.addRow("Farve",color)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        form.addRow(buttons); buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject)
        text.setFocus()
        if dlg.exec()!=QDialog.DialogCode.Accepted or not text.text().strip():return
        self.project.raw["default_text_height"]=float(height.value())
        self._stop_cable_marking_for_other_tool()
        if self._cable_tool_is_open(): self.close_cable_tool()
        self.view.start_text_tool(text=text.text().strip(),height=float(height.value()),rotation=float(rot.value()),color=color.text())
        self._set_status("Placér tekst: klik på tegningen · Esc annullerer")

    def _text_placement_requested(self, data: dict) -> None:
        item=core.TextPlacement(text=str(data.get("text","")),x=float(data.get("x",0)),y=float(data.get("y",0)),
                                height=float(data.get("height",200)),rotation=float(data.get("rotation",0)),
                                color=core.normalize_hex_color(data.get("color","#202020")))
        self.undo_stack.push(AddTextCommand(self,item))

    def _wire_text_item(self,item:FreeTextItem)->None:
        item.snapper=self._snap_moving_text
        item.signals.moved.connect(self._text_moved)
        item.signals.dragFinished.connect(self._text_drag_finished)
        item.signals.doubleClicked.connect(lambda it:self.edit_free_text(it.source))

    def _snap_moving_text(self,item:FreeTextItem,proposed_scene:QPointF)->QPointF:
        x=float(proposed_scene.x()); y=float(-proposed_scene.y())
        x,y,kind=self.view._text_alignment_snap(x,y,getattr(item.source,"uid",""))
        self.view._show_snap_feedback(QPointF(x,-y),kind)
        return QPointF(x,-y)

    def _add_text(self,item:core.TextPlacement,index:int|None=None)->None:
        if any(x.uid==item.uid for x in self.project.texts):return
        if index is None or not (0<=index<=len(self.project.texts)):self.project.texts.append(item)
        else:self.project.texts.insert(index,item)
        gi=FreeTextItem(item); self._wire_text_item(gi)
        gi.setVisible(self.project.layer_visibility.get(core.FREE_TEXT_LAYER,True) and self._quick_visible("text"))
        self.scene.addItem(gi); self.text_items[item.uid]=gi
        self.generated_layer_items[core.FREE_TEXT_LAYER].append(gi)
        self.project.dirty=True; self._update_title(); self._rebuild_layer_list()

    def _remove_text(self,uid:str)->None:
        source=next((x for x in self.project.texts if x.uid==uid),None)
        if source is None:return
        self.project.texts=[x for x in self.project.texts if x.uid!=uid]
        gi=self.text_items.pop(uid,None)
        if gi is not None:
            if gi in self.generated_layer_items.get(core.FREE_TEXT_LAYER,[]):self.generated_layer_items[core.FREE_TEXT_LAYER].remove(gi)
            if gi.scene() is not None:self.scene.removeItem(gi)
        self.project.dirty=True; self._update_title()

    def _text_state(self,item:core.TextPlacement)->dict:
        return {"text":item.text,"x":float(item.x),"y":float(item.y),"height":float(item.height),
                "rotation":float(item.rotation),"color":core.normalize_hex_color(item.color)}

    def _apply_text_state(self,uid:str,state:dict)->None:
        src=next((x for x in self.project.texts if x.uid==uid),None)
        if src is None:return
        for k,v in state.items():
            if hasattr(src,k):setattr(src,k,deepcopy(v))
        src.color=core.normalize_hex_color(src.color)
        gi=self.text_items.get(uid)
        if gi:gi.refresh()
        self.project.dirty=True; self._update_title()

    def _text_moved(self,item:FreeTextItem)->None:
        self.project.dirty=True; self._update_title()

    def _text_drag_finished(self,item:FreeTextItem,old,new)->None:
        self.view._clear_snap_feedback()
        if tuple(round(float(v),8) for v in old)==tuple(round(float(v),8) for v in new):return
        before=self._text_state(item.source); before["x"],before["y"]=old
        after=self._text_state(item.source)
        self.undo_stack.push(EditTextCommand(self,item.source.uid,before,after,"Flyt tekst"))

    def edit_free_text(self,item:core.TextPlacement)->None:
        dlg=QDialog(self); dlg.setWindowTitle("Redigér tekst"); dlg.setMinimumWidth(440)
        form=QFormLayout(dlg)
        text=QLineEdit(item.text)
        height=QDoubleSpinBox(); height.setRange(1,5000); height.setDecimals(1); height.setSingleStep(10.0); height.setValue(item.height); height.setSuffix(" mm")
        rot=QDoubleSpinBox(); rot.setRange(-360,360); rot.setValue(item.rotation); rot.setSuffix("°")
        color=QPushButton(core.normalize_hex_color(item.color)); _set_color_button(color,item.color)
        def choose():
            c=QColorDialog.getColor(QColor(color.text()),dlg,"Tekstfarve")
            if c.isValid():_set_color_button(color,c.name())
        color.clicked.connect(choose)
        form.addRow("Tekst",text); form.addRow("Højde",height); form.addRow("Rotation",rot); form.addRow("Farve",color)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        form.addRow(buttons); buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject)
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        before=self._text_state(item); after=dict(before)
        after.update({"text":text.text(),"height":float(height.value()),"rotation":float(rot.value()),"color":color.text()})
        if before!=after:self.undo_stack.push(EditTextCommand(self,item.uid,before,after,"Redigér tekst"))

    def edit_annotation_direct(self,p:core.Placement)->None:
        dlg=QDialog(self); dlg.setWindowTitle("Redigér mærkning"); dlg.setMinimumWidth(500)
        form=QFormLayout(dlg)
        label=QLineEdit(p.label); group=QLineEdit(p.group)
        form.addRow("Gruppe/kreds (primær)",group)
        form.addRow("Mærkning (valgfri)",label)
        mode=None; swl=swg=sol=sog=None
        if core.is_combo_symbol(p.symbol):
            mode=QComboBox(); mode.addItems(list(core.COMBO_LABEL_MODES)); mode.setCurrentText(core.normalize_combo_label_mode(p.label_mode))
            swl=QLineEdit(getattr(p,"switch_label","") or ""); swg=QLineEdit(getattr(p,"switch_group","") or "")
            sol=QLineEdit(getattr(p,"socket_label","") or ""); sog=QLineEdit(getattr(p,"socket_group","") or "")
            form.addRow("Kombi-mærkning",mode); form.addRow("Afbryder(e) – mærkning",swl); form.addRow("Afbryder(e) – gruppe",swg)
            form.addRow("Stik – mærkning",sol); form.addRow("Stik – gruppe",sog)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        form.addRow(buttons); buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject)
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        before=self._symbol_state(p); after=dict(before)
        after["label"]=label.text().strip(); after["group"]=group.text().strip()
        if mode is not None:
            after.update({"label_mode":core.normalize_combo_label_mode(mode.currentText()),
                          "switch_label":swl.text().strip(),"switch_group":swg.text().strip(),
                          "socket_label":sol.text().strip(),"socket_group":sog.text().strip()})
        if before!=after:self.undo_stack.push(EditSymbolCommand(self,p.uid,before,after,"Redigér mærkning"))

    # ---------- Spot line / rectangular pattern ----------
    def _spot_size_default(self)->float:
        try:return max(20.0,float(self.project.raw.get("spot_default_size",150.0) or 150.0))
        except Exception:return 150.0

    def start_spot_line_dialog(self)->None:
        if self.doc is None:return
        dlg=QDialog(self); dlg.setWindowTitle("Spot-række"); dlg.setMinimumWidth(420); form=QFormLayout(dlg)
        count=QSpinBox(); count.setRange(2,24); count.setValue(int(self.project.raw.get("spot_row_count",4) or 4))
        size=QDoubleSpinBox(); size.setRange(20,5000); size.setValue(self._spot_size_default()); size.setSuffix(" mm")
        link=QCheckBox("Tilknyt rækken til et lampested bagefter"); link.setChecked(True)
        form.addRow("Antal spots",count); form.addRow("Spotstørrelse",size); form.addRow("",link)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        form.addRow(buttons); buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject)
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        config={"count":count.value(),"size":float(size.value()),"link":link.isChecked()}
        self.project.raw["spot_row_count"]=count.value(); self.project.raw["spot_default_size"]=float(size.value())
        self._stop_cable_marking_for_other_tool()
        if self._cable_tool_is_open(): self.close_cable_tool()
        self.view.start_spot_pattern("line",config)
        self._set_status("Spot-række: klik start- og slutpunkt · snapper til andre spots og vandret/lodret · Alt = fri vinkel · Esc annullerer")

    def start_spot_rect_dialog(self)->None:
        if self.doc is None:return
        dlg=QDialog(self); dlg.setWindowTitle("Spot-rektangel"); dlg.setMinimumWidth(420); form=QFormLayout(dlg)
        cols=QSpinBox(); cols.setRange(2,20); cols.setValue(int(self.project.raw.get("spot_rect_columns",3) or 3))
        rows=QSpinBox(); rows.setRange(2,20); rows.setValue(int(self.project.raw.get("spot_rect_rows",2) or 2))
        size=QDoubleSpinBox(); size.setRange(20,5000); size.setValue(self._spot_size_default()); size.setSuffix(" mm")
        link=QCheckBox("Tilknyt mønstret til et lampested bagefter"); link.setChecked(True)
        form.addRow("Kolonner",cols); form.addRow("Rækker",rows); form.addRow("Spotstørrelse",size); form.addRow("",link)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        form.addRow(buttons); buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject)
        if dlg.exec()!=QDialog.DialogCode.Accepted:return
        if cols.value()*rows.value()>200:
            QMessageBox.warning(self,"Spot-rektangel","Vælg højst 200 spots pr. mønster.");return
        config={"cols":cols.value(),"rows":rows.value(),"size":float(size.value()),"link":link.isChecked()}
        self.project.raw["spot_rect_columns"]=cols.value(); self.project.raw["spot_rect_rows"]=rows.value(); self.project.raw["spot_default_size"]=float(size.value())
        self._stop_cable_marking_for_other_tool()
        if self._cable_tool_is_open(): self.close_cable_tool()
        self.view.start_spot_pattern("rect",config)
        self._set_status("Spot-rektangel: klik to modstående hjørner · Esc annullerer")

    def _spot_pattern_finished(self,kind:str,start,end,config:dict)->None:
        if kind=="rect":
            pts=CadGraphicsView._rect_points(start,end,config.get("cols",3),config.get("rows",2))
        else:
            pts=CadGraphicsView._row_points(start,end,config.get("count",4))
        if not pts:return
        new=[]
        spot_group_id=uuid.uuid4().hex
        spot_group_name=self._next_spot_group_name()
        self.undo_stack.beginMacro(f"Placér {len(pts)} spots")
        try:
            for x,y in pts:
                p=core.Placement(symbol="spot",x=float(x),y=float(y),size=float(config.get("size",150)),
                                 line_width=.25,color=core.DEFAULT_SYMBOL_COLOR,
                                 spot_group_id=spot_group_id,spot_group_name=spot_group_name)
                new.append(p.uid); self.undo_stack.push(AddSymbolCommand(self,p,"Placér spot"))
        finally:self.undo_stack.endMacro()
        if config.get("link"):
            self.spot_parent_pending=list(new)
            self.view.setCursor(Qt.CursorShape.CrossCursor)
            self._refresh_spot_parent_picker()
            self._set_status(
                f"Spot → lampested: {len(new)} nye spot(s). Klik et TURKIS fremhævet lampested · Esc springer over"
            )
        else:
            self._set_status(f"{len(pts)} spots placeret som {spot_group_name}.")

    def _spot_parent_snapshot(self)->dict:
        return {
            p.uid:{
                "parent_light_uid":str(getattr(p,"parent_light_uid","") or ""),
                "parent_light_output_id":str(getattr(p,"parent_light_output_id","") or ""),
                "associations":list(core.normalize_associations(p.associations)),
                "spot_group_id":str(getattr(p,"spot_group_id","") or ""),
                "spot_group_name":str(getattr(p,"spot_group_name","") or ""),
            }
            for p in self.project.placements if p.symbol=="spot"
        }

    def _apply_spot_parent_state(self,state:dict)->None:
        for p in self.project.placements:
            if p.uid in state:
                value=state[p.uid]
                if isinstance(value,dict):
                    p.parent_light_uid=str(value.get("parent_light_uid","") or "")
                    p.parent_light_output_id=str(value.get("parent_light_output_id","") or "")
                    p.associations=core.normalize_light_associations(value.get("associations",[]))
                    p.spot_group_id=str(value.get("spot_group_id","") or "")
                    p.spot_group_name=str(value.get("spot_group_name","") or "")
                else:
                    # Backwards compatible with old undo snapshots: (parent, associations).
                    parent,assoc=value; p.parent_light_uid=str(parent); p.parent_light_output_id=""; p.associations=core.normalize_light_associations(assoc)
                ann=self.annotation_items.get(p.uid)
                if ann:ann.refresh()
        self.project.dirty=True; self._update_title()
        self._selection_changed()

    # ---------- Copy / paste / multi-select ----------
    def select_all_symbols(self)->None:
        for item in self.symbol_items.values():
            if item.isVisible():item.setSelected(True)

    def copy_selected(self)->None:
        symbols=[x for x in self.scene.selectedItems() if isinstance(x,ElectricalSymbolItem)]
        texts=[x for x in self.scene.selectedItems() if isinstance(x,FreeTextItem)]
        if not symbols and not texts:
            self._set_status("Intet at kopiere.");return
        data={"symbols":[asdict(x.placement) for x in symbols],"texts":[asdict(x.source) for x in texts]}
        QApplication.clipboard().setText("ELPLAN_QT_CLIP_V1\n"+json.dumps(data,ensure_ascii=False))
        self._set_status(f"Kopieret: {len(symbols)} symbol(er), {len(texts)} tekstobjekt(er).")

    def paste_clipboard(self)->None:
        raw=QApplication.clipboard().text()
        if not raw.startswith("ELPLAN_QT_CLIP_V1\n"):
            self._set_status("Udklipsholderen indeholder ikke Elplan-objekter.");return
        try:data=json.loads(raw.split("\n",1)[1])
        except Exception:return
        sym=data.get("symbols",[]); txt=data.get("texts",[])
        copied_group_counts={}
        for rec in sym:
            gid=str(rec.get("spot_group_id","") or "")
            if gid:copied_group_counts[gid]=copied_group_counts.get(gid,0)+1
        copied_group_remap={}
        coords=[(float(x.get("x",0)),float(x.get("y",0))) for x in sym+txt]
        if coords:
            cx=sum(x for x,_ in coords)/len(coords); cy=sum(y for _,y in coords)/len(coords)
            if self.view.last_mouse_scene is not None:
                tx=float(self.view.last_mouse_scene.x()); ty=float(-self.view.last_mouse_scene.y())
                dx,dy=tx-cx,ty-cy
            else:dx=dy=250.0
        else:dx=dy=250.0
        added_uids=[]; added_text=[]
        self.undo_stack.beginMacro("Indsæt")
        try:
            for rec in sym:
                rec=dict(rec); rec["uid"]=uuid.uuid4().hex; rec["x"]=float(rec.get("x",0))+dx; rec["y"]=float(rec.get("y",0))+dy
                rec["associations"]=[]; rec["association_channels"]=[]
                rec["light_outputs"]=[dict(row,association="") for row in core.normalize_light_outputs(rec.get("light_outputs",[]),[],ensure_one=rec.get("symbol")=="light_connection")] if rec.get("symbol")=="light_connection" else []
                rec["parent_light_uid"]=""; rec["parent_light_output_id"]=""; rec["pl_box_entries"]={}; rec["pl_box_wiring"]=[]; rec["pl_box_splices"]=[]; rec["pl_field_record"]={}; rec["lamp_outlet_type"]=core.normalize_pl_outlet_type(rec.get("lamp_outlet_type","generic")); rec["locked"]=False
                old_gid=str(rec.get("spot_group_id","") or "")
                if rec.get("symbol")=="spot" and old_gid and copied_group_counts.get(old_gid,0)>=2:
                    rec["spot_group_id"]=copied_group_remap.setdefault(old_gid,uuid.uuid4().hex)
                else:
                    rec["spot_group_id"]=""; rec["spot_group_name"]=""
                p=core.Placement(**{k:v for k,v in rec.items() if k in core.Placement.__dataclass_fields__})
                added_uids.append(p.uid); self.undo_stack.push(AddSymbolCommand(self,p,"Indsæt symbol"))
            for rec in txt:
                rec=dict(rec); rec["uid"]=uuid.uuid4().hex; rec["x"]=float(rec.get("x",0))+dx; rec["y"]=float(rec.get("y",0))+dy
                x=core.TextPlacement(**{k:v for k,v in rec.items() if k in core.TextPlacement.__dataclass_fields__})
                added_text.append(x.uid); self.undo_stack.push(AddTextCommand(self,x,"Indsæt tekst"))
        finally:self.undo_stack.endMacro()
        self.scene.clearSelection()
        for uid in added_uids:
            if uid in self.symbol_items:self.symbol_items[uid].setSelected(True)
        for uid in added_text:
            if uid in self.text_items:self.text_items[uid].setSelected(True)

    # ---------- PDF / print preview ----------
    def _output_layer_visibility(self) -> dict[str, bool]:
        """Kombinér projektlag og Vis-menuens hurtigfiltre til PDF/print."""
        visibility={str(k):bool(v) for k,v in dict(self.project.layer_visibility or {}).items()}
        if not self._quick_visible("cad"):
            for prim in self.cad_primitives:
                layer=str(getattr(prim,"layer","") or "0")
                visibility[layer]=False
        if not self._quick_visible("symbols"):
            for placement in self.project.placements:
                visibility[core.symbol_layer(placement.symbol)]=False
        if not self._quick_visible("cables"):
            for cable in self.project.cables:
                if str(getattr(cable,"layer","") or "") != core.PATCH_CABLE_LAYER:
                    visibility[core.cable_effective_layer(cable)]=False
        if not self._quick_visible("patch_cables"):
            for cable in self.project.cables:
                if str(getattr(cable,"layer","") or "") == core.PATCH_CABLE_LAYER:
                    visibility[core.cable_effective_layer(cable)]=False
        if not self._quick_visible("text"):
            visibility[core.FREE_TEXT_LAYER]=False
            visibility[core.META_LAYER]=False
        return visibility

    def _print_extents(self,scope:str):
        if scope=="Aktuel visning":return self.view.viewport_cad_extents()
        return core.print_extents(
            self.cad_primitives,self.project.placements,self.project.cables,
            self._output_layer_visibility(),self.project.texts,self.project.rooms,
            bool(self.project.raw.get("room_labels_visible",True)),
            bool(self.room_edit_mode or self.project.raw.get("room_boundaries_visible",False)),
        )

    def open_print_preview(self)->None:
        if self.doc is None:return
        PrintPreviewDialog(self).exec()

    def export_pdf(self,paper:str|None=None,orientation:str|None=None,scope:str|None=None)->None:
        if self.doc is None:return
        paper=paper or str(self.project.raw.get("paper_size","A3") or "A3")
        orientation=orientation or str(self.project.raw.get("page_orientation","Landskab") or "Landskab")
        scope=scope or str(self.project.raw.get("print_scope","Aktuel visning") or "Aktuel visning")
        path,_=QFileDialog.getSaveFileName(self,"Gem PDF","elplan.pdf","PDF (*.pdf)")
        if not path:return
        if not path.lower().endswith(".pdf"):path+=".pdf"
        try:
            ext=self._print_extents(scope) if scope=="Aktuel visning" else None
            core.export_vector_pdf(path,self.cad_primitives,self.project.placements,self.project.cables,
                                   self._output_layer_visibility(),paper,orientation,
                                   texts=self.project.texts,extents_override=ext,fill_page=False,
                                   cad_opacity=self._output_cad_opacity(),
                                   annotation_mode=self.annotation_display_mode,
                                   rooms=self.project.rooms,
                                   room_labels_visible=bool(self.project.raw.get("room_labels_visible",True)),
                                   room_codes_visible=bool(self.project.raw.get("room_codes_visible",False)),
                                   room_boundaries_visible=bool(self.room_edit_mode or self.project.raw.get("room_boundaries_visible",False)))
            self.project.raw.update({"paper_size":paper,"page_orientation":orientation,"print_scope":scope})
            self._set_status(f"PDF gemt: {Path(path).name}")
        except Exception as exc:QMessageBox.critical(self,"PDF-eksport",str(exc))

    def print_plan(self,paper:str|None=None,orientation:str|None=None,scope:str|None=None)->None:
        if self.doc is None:return
        paper=paper or str(self.project.raw.get("paper_size","A3") or "A3")
        orientation=orientation or str(self.project.raw.get("page_orientation","Landskab") or "Landskab")
        scope=scope or str(self.project.raw.get("print_scope","Aktuel visning") or "Aktuel visning")
        try:
            ext=self._print_extents(scope) if scope=="Aktuel visning" else None
            printer=core.print_vector_windows(self.cad_primitives,self.project.placements,self.project.cables,
                                              self._output_layer_visibility(),paper,orientation,
                                              extents_override=ext,texts=self.project.texts,fill_page=False,
                                              cad_opacity=self._output_cad_opacity(),rooms=self.project.rooms,
                                              room_labels_visible=bool(self.project.raw.get("room_labels_visible",True)),
                                              room_codes_visible=bool(self.project.raw.get("room_codes_visible",False)),
                                              room_boundaries_visible=bool(self.room_edit_mode or self.project.raw.get("room_boundaries_visible",False)))
            self.project.raw.update({"paper_size":paper,"page_orientation":orientation,"print_scope":scope})
            self._set_status(f"Sendt til printer: {printer}")
        except Exception as exc:QMessageBox.critical(self,"Udskrivning",str(exc))

    def _rebuild_layer_list(self) -> None:
        blocker = QSignalBlocker(self.layers_list)
        self.layers_list.clear()
        layers = sorted(set(self.layer_items) | set(self.generated_layer_items),key=lambda x:core.cable_category_layer_label(x,self._cable_categories()).casefold())
        for layer in layers:
            display=core.cable_category_layer_label(layer,self._cable_categories())
            entry = QListWidgetItem(display)
            entry.setData(Qt.ItemDataRole.UserRole,layer)
            entry.setToolTip(layer if display!=layer else "")
            entry.setFlags(entry.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            entry.setCheckState(Qt.CheckState.Checked if self.project.layer_visibility.get(layer, True) else Qt.CheckState.Unchecked)
            self.layers_list.addItem(entry)
        if hasattr(self, "layer_count_label"):
            self.layer_count_label.setText(f"{len(layers)}")
        del blocker

    def _layer_changed(self, item: QListWidgetItem) -> None:
        layer = str(item.data(Qt.ItemDataRole.UserRole) or item.text())
        visible = item.checkState() == Qt.CheckState.Checked
        self.project.layer_visibility[layer] = visible
        if layer in self.layer_items:
            self.layer_items[layer].setVisible(visible)
        for graphics_item in self.generated_layer_items.get(layer, []):
            graphics_item.setVisible(visible)
        # En mærkning må ikke blive hængende alene, når symbolets lag skjules.
        # Omvendt skal EL-TEKST kunne skjule mærkning uden at skjule symbolet.
        self._sync_symbol_annotation_visibility()
        self._apply_quick_visibility()
        if layer == core.ROOM_LAYER:
            self._refresh_room_visibility()
        if layer in (core.CABLE_LAYER, core.PATCH_CABLE_LAYER, core.WIRE_LAYER) or "-KAT-" in layer:
            self._rebuild_cable_visual_cache(refresh_items=True)
            if hasattr(self,"_refresh_cable_categories_menu"): self._refresh_cable_categories_menu()
            if hasattr(self,"_refresh_cable_category_strip"): self._refresh_cable_category_strip()
        self._refresh_switch_association_badges()
        self.project.dirty = True
        self._update_title()

    def _selection_signature(self):
        rows=[]
        for item in self.scene.selectedItems():
            if isinstance(item,ElectricalSymbolItem):
                rows.append(("symbol",str(item.placement.uid)))
            elif isinstance(item,CableItem):
                rows.append(("cable",str(getattr(item.cable,"uid","") or id(item.cable))))
            else:
                room=getattr(item,"room",None)
                rows.append(("room",str(getattr(room,"uid","") or id(item))))
        return tuple(sorted(rows))

    def _queue_selection_changed(self)->None:
        """Coalesce scene signals without delaying a pending symbol drag."""
        self._selection_refresh_pending=True
        self._selection_refresh_timer.stop()
        if self._symbol_pointer_down or self._symbol_drag_active:
            return
        self._selection_refresh_timer.setInterval(28)
        self._selection_refresh_timer.start()

    def _flush_queued_selection_changed(self)->None:
        if self._symbol_pointer_down or self._symbol_drag_active:
            return
        if not self._selection_refresh_pending:
            return
        signature=self._selection_signature()
        self._selection_refresh_pending=False
        if signature==self._selection_last_signature:
            return
        self._selection_changed()

    def _symbol_pointer_pressed(self,_item)->None:
        self._symbol_pointer_down=True
        self._selection_refresh_timer.stop()

    def _symbol_pointer_released(self,_item,was_dragging:bool)->None:
        self._symbol_pointer_down=False
        self._symbol_drag_active=False
        if self._selection_refresh_pending:
            # Let Qt finish the release/paint event first. A click therefore
            # opens Egenskaber immediately afterwards, while a drag never has
            # to wait for the inspector during mouse movement.
            self._selection_refresh_timer.setInterval(0 if not was_dragging else 12)
            self._selection_refresh_timer.start()

    def _selection_changed(self) -> None:
        if hasattr(self,"_selection_refresh_timer"):self._selection_refresh_timer.stop()
        self._selection_refresh_pending=False
        self._selection_last_signature=self._selection_signature()
        selected_symbols=[x for x in self.scene.selectedItems() if isinstance(x,ElectricalSymbolItem)]
        selected_cables=[x for x in self.scene.selectedItems() if isinstance(x,CableItem)]
        selected_rooms=self._selected_rooms_from_scene()
        self._properties_current_placement=None
        self._properties_multi_spots=False
        if hasattr(self,"properties_workflow_bar"):self._apply_properties_workflow_visibility()
        # Annotation detail is adaptive: selected symbols temporarily reveal
        # full detail even when the overview is in Auto mode. Only the old and
        # new selection can have changed detail; refreshing every label made
        # selection noticeably slower on larger plans.
        selected_annotation_uids={x.placement.uid for x in selected_symbols}
        for uid in selected_annotation_uids | self._last_selected_annotation_uids:
            ann=self.annotation_items.get(uid)
            if ann is not None:ann.refresh()
        self._last_selected_annotation_uids=selected_annotation_uids
        self._symbol_metadata_refresh_timer.start()
        self._clear_spot_link_visuals()
        self._clear_relation_overview()
        self.spot_parent_group.hide()
        self.bom_disclosure.hide()
        self.assoc_group.hide()
        self.assoc_channels_table.hide()
        self.light_outputs_table.hide(); self.light_outputs_actions.hide()
        if hasattr(self,"symbol_cables_group"):self.symbol_cables_group.hide()
        if hasattr(self,"pl_box_group"):self.pl_box_group.hide()
        self._apply_visual_emphasis()
        if self._show_room_selection_inspector(selected_rooms,selected_symbols,selected_cables):return

        if len(selected_cables)==1 and not selected_symbols:
            cable=selected_cables[0].cable
            self.prop_title.setText("Kabel / ledning valgt")
            if hasattr(self, "prop_hint"):
                self.prop_hint.setText("Kabelegenskaber redigeres i det fælles Egenskaber-panel.")
            self.prop_assoc.setText("—")
            self.combo_disclosure.hide()
            self._enable_properties(False)
            self._load_selected_cable_into_panel(cable)
            self._update_inspector_summary(cable=cable)
            title=core.cable_display_label(cable) or cable.cable_id or "Kabel"
            self._show_inspector_page("cable", title=title, hint="Kategori, ruteføring, artikel og kabeldata for det valgte kabel.")
            self._refresh_context_toolbar()
            return

        if selected_cables:
            self._load_selected_cable_into_panel(None)

        selected=selected_symbols
        if len(selected)>1 and not selected_cables and not selected_rooms and all(x.placement.symbol=="spot" for x in selected):
            spots=[x.placement for x in selected]
            count=len(spots)
            self.prop_title.setText(f"{count} spots valgt")
            if hasattr(self,"prop_hint"):self.prop_hint.setText("Gruppér spots eller tilknyt dem samlet til et lampested.")
            self.prop_assoc.setText("—"); self.combo_disclosure.hide(); self._enable_properties(False)
            self._show_inspector_page("properties",title=f"{count} spots valgt",hint="Spotgruppe og lampested kan håndteres samlet her.")
            self.spot_parent_group.show(); self._refresh_spot_group_controls(spots)
            self._properties_multi_spots=True
            expanded=self._expand_spots_to_groups(spots)
            parents={str(getattr(p,"parent_light_uid","") or "") for p in expanded if str(getattr(p,"parent_light_uid","") or "")}
            if len(parents)==1:
                parent=self._placement_by_uid(next(iter(parents)))
                ident=str(parent.group or parent.label or "Lampested") if parent is not None else "Lampested ?"
                self.spot_parent_value.setText(f"Lampested: {ident} · {len(expanded)} spot(s) i valgt gruppe/udvalg")
            elif parents:
                self.spot_parent_value.setText("Lampested: Flere forskellige lampesteder")
            else:
                self.spot_parent_value.setText("Lampested: Ikke tilknyttet")
            self.spot_parent_link_button.setEnabled(True)
            self.spot_parent_unlink_button.setEnabled(bool(parents))
            self._properties_workflow_user_choice=False
            self._set_properties_workflow("connect")
            self._update_inspector_summary(); self._refresh_context_toolbar(); return
        if len(selected) != 1:
            count=len(selected)+len(selected_cables)+len(selected_rooms)
            self.prop_title.setText(f"{count} objekter valgt" if count else "Intet symbol valgt")
            if hasattr(self, "prop_hint"):
                self.prop_hint.setText("Flere objekter valgt." if count else "Vælg et symbol på tegningen for at redigere det.")
            self.prop_assoc.setText("—")
            self.spot_parent_value.setText("Lampested: —")
            if hasattr(self,"spot_group_value"):self.spot_group_value.setText("Gruppe: —")
            self.combo_disclosure.hide()
            self._enable_properties(False)
            if not self._cable_tool_is_open():
                self._show_inspector_page(
                    "properties",
                    title=f"{count} objekter valgt" if count else "Intet valgt",
                    hint="Vælg ét objekt for at se og redigere dets egenskaber." if not count else "Fælles handlinger findes i den kontekstuelle værktøjslinje.",
                    reveal=False,
                )
            self._update_inspector_summary()
            self._refresh_context_toolbar()
            return

        # Et symbolvalg forlader aktiv kabeltegning, men højre side forsvinder
        # ikke. Den skifter blot kontekst til symbolets egenskaber.
        if self._cable_tool_is_open():
            self.close_cable_tool()
        item=selected[0]
        p=item.placement
        self._properties_current_placement=p
        self._update_inspector_summary(placement=p)
        ident=" · ".join(x for x in (str(p.group or "").strip(), str(p.label or "").strip()) if x)
        self._show_inspector_page(
            "properties",
            title=core.symbol_display_name(p.symbol),
            hint=(ident if ident else "Redigér symboldata og relationer her."),
        )
        self._refresh_symbol_cables_group(p)
        self._refresh_pl_box_group(p)
        self._loading_properties=True
        self.prop_title.setText(core.symbol_display_name(p.symbol))
        if hasattr(self, "prop_hint"):
            self.prop_hint.setText("Redigér felterne nedenfor og vælg Anvend ændringer.")
        self.prop_label.setText(p.label)
        self.prop_group.setText(p.group)
        self.prop_size.setValue(p.size)
        self.prop_rotation.setValue(p.rotation)
        self.prop_line_width.setValue(float(p.line_width))
        _set_color_button(self.prop_color, core.normalize_hex_color(p.color))
        self.prop_locked.setChecked(p.locked)
        zone=core.normalize_mounting_zone(getattr(p,"mounting_zone",""))
        zone_index=self.prop_mounting_zone.findData(zone); self.prop_mounting_zone.setCurrentIndex(max(0,zone_index))
        self.prop_mounting_height.setValue(float(core.normalize_mounting_height_mm(getattr(p,"mounting_height_mm",None)) or 0.0))
        material_color=core.normalize_material_color(getattr(p,"material_color",""))
        color_index=self.prop_material_color.findData(material_color)
        if color_index>=0:self.prop_material_color.setCurrentIndex(color_index)
        else:self.prop_material_color.setCurrentText(material_color)
        self.prop_already_purchased.setChecked(core.normalize_already_purchased(getattr(p,"already_purchased",False)))
        role=core.association_role(p.symbol)
        preferred_workflow="connect" if (
            role in ("switch","light") or p.symbol in {"spot","light_connection"}
        ) else "data"
        current_workflow=getattr(self,"_properties_workflow","data")
        if not getattr(self,"_properties_workflow_user_choice",False) or not self._property_workflow_has_content(current_workflow,p):
            if not self._property_workflow_has_content(current_workflow,p):
                self._properties_workflow_user_choice=False
            target_workflow=preferred_workflow
        else:
            target_workflow=current_workflow
        self.assoc_group.setVisible(role in ("switch","light"))
        assoc_text=core.association_display(p)
        if role=="switch":
            cap=core.association_capacity(p.symbol)
            channels=core.association_channel_letters(p)
            assigned=[(i,a) for i,a in enumerate(channels) if a]
            detail=" · ".join(
                f"{core.association_channel_caption(p.symbol,i)} = {a} ({self._association_target_count(a)} lys)"
                for i,a in assigned
            )
            base=f"{assoc_text or 'Ingen'}   ({len(assigned)}/{cap} betjeninger)"
            self.prop_assoc.setText(base + (f" · {detail}" if detail else ""))
        elif role=="light":
            if p.symbol=="light_connection":
                outputs=core.light_output_records(p)
                assigned=sum(1 for row in outputs if row.get("association","") )
                self.prop_assoc.setText(f"Fysisk lampested: {len(outputs)} tænding(er) · {assigned} tilknyttet · {assoc_text or 'ingen'}")
            else:
                vals=core.normalize_light_associations(p.associations)
                self.prop_assoc.setText(f"Lys: {assoc_text or 'ingen tilknytning'}"+(" · ét lyssymbol = én tænding" if vals else ""))
        else:self.prop_assoc.setText("—")
        self._refresh_association_channel_table(p)
        self._refresh_light_outputs_table(p)

        if target_workflow=="purchase":self._refresh_selected_symbol_bom_ui(p)
        else:self.bom_disclosure.hide()

        if p.symbol=="spot":
            self.spot_parent_group.show(); self._refresh_spot_group_controls([p])
            parent_uid=str(getattr(p,"parent_light_uid","") or "")
            parent=self._placement_by_uid(parent_uid) if parent_uid else None
            if parent is None:
                self.spot_parent_value.setText("Lampested: Ikke tilknyttet")
                self.spot_parent_unlink_button.setEnabled(False)
            else:
                ident=str(parent.group or parent.label or "Lampested")
                gid=str(getattr(p,"spot_group_id","") or "")
                siblings=len(self._spot_group_members(gid)) if gid else len(self._linked_spots(parent.uid))
                output=core.light_output_by_id(parent,getattr(p,"parent_light_output_id","") or "")
                assoc=str(output.get("association","") or "")
                extra=f" · {output.get('name')}" if len(core.light_output_records(parent))>1 else ""
                if assoc:extra+=f" · {assoc}"
                self.spot_parent_value.setText(f"Lampested: {ident} · {siblings} spot(s){extra}")
                self.spot_parent_unlink_button.setEnabled(True)
            self.spot_parent_link_button.setEnabled(True)
        elif p.symbol=="light_connection":
            self.spot_parent_group.show()
            linked=self._linked_spots(p.uid)
            group_ids={str(getattr(s,"spot_group_id","") or "") for s in linked if str(getattr(s,"spot_group_id","") or "")}
            ungrouped=sum(1 for s in linked if not str(getattr(s,"spot_group_id","") or ""))
            group_text=f"{len(group_ids)} spotgruppe(r)" + (f" + {ungrouped} ugrupperet" if ungrouped else "")
            self.spot_group_value.setText(f"Grupper: {group_text}" if linked else "Grupper: Ingen")
            self.spot_parent_value.setText(f"Lampested: {len(linked)} tilknyttede spot(s)")
            self.spot_group_button.setEnabled(False); self.spot_group_select_button.setEnabled(False); self.spot_group_clear_button.setEnabled(False)
            self.spot_parent_link_button.setEnabled(False)
            self.spot_parent_unlink_button.setEnabled(False)

        self._refresh_spot_link_visuals(p)
        self._refresh_relation_overview(p)

        is_combo=core.is_combo_symbol(p.symbol)
        self.combo_disclosure.setVisible(is_combo)
        if is_combo:
            self.prop_combo_mode.setCurrentText(core.normalize_combo_label_mode(getattr(p,"label_mode","Fælles")))
            self.prop_switch_label.setText(getattr(p,"switch_label","") or "")
            self.prop_switch_group.setText(getattr(p,"switch_group","") or "")
            self.prop_socket_label.setText(getattr(p,"socket_label","") or "")
            self.prop_socket_group.setText(getattr(p,"socket_group","") or "")
        self._loading_properties=False
        self._enable_properties(True)
        self.delete_symbol_button.setEnabled(not p.locked)
        self.delete_symbol_button.setToolTip(
            "Symbolet er låst. Fjern markeringen 'Lås placering og fysisk redigering' og anvend ændringen før sletning."
            if p.locked else "Slet det valgte symbol. Handlingen kan fortrydes med Ctrl+Z."
        )
        if role=="switch":
            self.assoc_button.setText("Tilføj / fjern lys…")
            self.assoc_button.setToolTip("Redigér lampestederne for den valgte fysiske betjening.")
            self.assoc_note.setText(
                "Vælg en betjening i tabellen, vælg Tilføj / fjern lys, og klik derefter "
                "lampesteder på tegningen. Enter gemmer; Esc annullerer."
            )
        elif role=="light":
            self.assoc_button.setText("Tilknyt til afbryder…")
            self.assoc_button.setToolTip("Vælg den afbryder og betjening, der skal styre dette lys.")
            self.assoc_note.setText(
                "Vælg Tilknyt til afbryder, klik en orange afbryder og vælg dens betjening. "
                "Klik derefter dette eller andre lys til/fra."
            )
        self.assoc_button.setEnabled(role in ("switch","light"))
        has_assoc=bool(core.light_output_associations(p) if role=="light" else core.normalize_associations(p.associations))
        self.clear_assoc_button.setEnabled(has_assoc)

        self._set_properties_workflow(target_workflow)

        self.selected_cable=None
        if hasattr(self,"_set_cable_panel_context"): self._set_cable_panel_context(None)
        if hasattr(self,"cable_apply_selected"):
            self.cable_apply_selected.setEnabled(False)
        self._refresh_context_toolbar()

    def _selected_symbol_item(self) -> ElectricalSymbolItem | None:
        selected = [x for x in self.scene.selectedItems() if isinstance(x, ElectricalSymbolItem)]
        return selected[0] if len(selected) == 1 else None

    def _symbol_state(self, p: core.Placement) -> dict:
        return {
            "label": p.label, "group": p.group, "size": float(p.size), "rotation": float(p.rotation),
            "line_width": float(p.line_width), "color": core.normalize_hex_color(p.color),
            "mounting_zone": core.normalize_mounting_zone(getattr(p,"mounting_zone","")),
            "mounting_height_mm": core.normalize_mounting_height_mm(getattr(p,"mounting_height_mm",None)),
            "material_color": core.normalize_material_color(getattr(p,"material_color","")),
            "already_purchased": core.normalize_already_purchased(getattr(p,"already_purchased",False)),
            "locked": bool(p.locked), "label_mode": core.normalize_combo_label_mode(getattr(p, "label_mode", "Fælles")),
            "switch_label": getattr(p, "switch_label", "") or "", "switch_group": getattr(p, "switch_group", "") or "",
            "socket_label": getattr(p, "socket_label", "") or "", "socket_group": getattr(p, "socket_group", "") or "",
            "pl_box_entries": deepcopy(core.normalize_pl_box_entries(getattr(p, "pl_box_entries", {}))),
            "pl_box_wiring": deepcopy(core.normalize_pl_box_wiring(getattr(p, "pl_box_wiring", []))),
            "pl_box_splices": deepcopy(core.normalize_pl_box_splices(getattr(p, "pl_box_splices", []))),
            "pl_box_orientation": core.normalize_pl_box_orientation(getattr(p, "pl_box_orientation", 0)),
            "lamp_outlet_type": core.normalize_pl_outlet_type(getattr(p, "lamp_outlet_type", "generic")),
            "pl_field_record": deepcopy(core.normalize_pl_field_record(getattr(p, "pl_field_record", {}))),
        }

    def _apply_symbol_state(self, uid: str, state: dict) -> None:
        item = self.symbol_items.get(uid)
        if item is None:
            return
        p = item.placement
        for key, value in state.items():
            if hasattr(p, key):
                setattr(p, key, deepcopy(value))
        p.rotation = float(p.rotation) % 360.0
        p.color = core.normalize_hex_color(p.color)
        p.mounting_zone=core.normalize_mounting_zone(getattr(p,"mounting_zone",""))
        p.mounting_height_mm=core.normalize_mounting_height_mm(getattr(p,"mounting_height_mm",None))
        p.material_color=core.normalize_material_color(getattr(p,"material_color",""))
        p.already_purchased=core.normalize_already_purchased(getattr(p,"already_purchased",False))
        self._hover_bom_cache.pop(str(getattr(p,"uid","") or ""),None)
        item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not p.locked)
        item.set_pose_silent(p.x, p.y, p.rotation)
        item.refresh_geometry()
        ann = self.annotation_items.get(uid)
        if ann: ann.refresh()
        self._refresh_connected_cables(uid)
        self._refresh_switch_association_badges()
        self.project.dirty = True
        self._update_title()
        if item.isSelected():
            self._selection_changed()

    def apply_properties(self) -> None:
        item = self._selected_symbol_item()
        if item is None:
            return
        p = item.placement
        before = self._symbol_state(p)
        after = dict(before)
        material_color_text=self.prop_material_color.currentText()
        material_color_value=(self.prop_material_color.currentData()
                              if self.prop_material_color.currentIndex()>=0
                              and self.prop_material_color.itemText(self.prop_material_color.currentIndex())==material_color_text
                              else material_color_text)
        after.update({
            "label": self.prop_label.text().strip(),
            "group": self.prop_group.text().strip(),
            "size": float(self.prop_size.value()),
            "rotation": float(self.prop_rotation.value()) % 360.0,
            "line_width": float(self.prop_line_width.value()),
            "color": core.normalize_hex_color(self.prop_color.text()),
            "locked": self.prop_locked.isChecked(),
            "mounting_zone": core.normalize_mounting_zone(self.prop_mounting_zone.currentData()),
            "mounting_height_mm": core.normalize_mounting_height_mm(self.prop_mounting_height.value()),
            "material_color": core.normalize_material_color(material_color_value),
            "already_purchased": self.prop_already_purchased.isChecked(),
        })
        if core.is_combo_symbol(p.symbol):
            after.update({
                "label_mode": core.normalize_combo_label_mode(self.prop_combo_mode.currentText()),
                "switch_label": self.prop_switch_label.text().strip(),
                "switch_group": self.prop_switch_group.text().strip(),
                "socket_label": self.prop_socket_label.text().strip(),
                "socket_group": self.prop_socket_group.text().strip(),
            })
        if before == after:
            return
        self.undo_stack.push(EditSymbolCommand(self, p.uid, before, after, "Redigér symbolegenskaber"))

    def _flush_symbol_drag_visuals(self) -> None:
        uids=set(self._symbol_drag_visual_uids)
        self._symbol_drag_visual_uids.clear()
        if not uids:
            return
        changed={}
        for uid in uids:
            annotation=self.annotation_items.get(uid)
            if annotation is not None:
                annotation.reposition_fast()
            candidates=self._symbol_drag_cables.get(uid) if self._symbol_drag_cables else self.project.cables
            for cable in candidates or ():
                if self._anchor_cable_connections(cable,uid):
                    changed[id(cable)]=cable
        if not changed:
            return
        self._symbol_drag_cables_changed=True
        for cable in changed.values():
            cable_item=self.cable_items.get(id(cable))
            if cable_item is not None:
                cable_item.set_visual_points(cable.points,refresh=False)
                cable_item.refresh(update_handles=False)

    def _symbol_moved(self, item: ElectricalSymbolItem) -> None:
        if self._group_drag_before and item.placement.uid==self._group_drag_anchor_uid and not self._group_drag_sync:
            self._group_drag_sync=True
            try:
                ax0,ay0,_=self._group_drag_before[item.placement.uid]
                dx=item.placement.x-ax0; dy=item.placement.y-ay0
                for uid,(x0,y0,r0) in self._group_drag_before.items():
                    if uid==item.placement.uid:continue
                    other=self.symbol_items.get(uid)
                    if other is not None:
                        other.set_pose_silent(x0+dx,y0+dy,r0)
                        self._symbol_drag_visual_uids.add(uid)
            finally:
                self._group_drag_sync=False
        self._symbol_drag_visual_uids.add(item.placement.uid)
        if not self._symbol_drag_visual_timer.isActive():
            self._symbol_drag_visual_timer.start()

    def export_core_data_package(self) -> None:
        summary=portability.core_data_summary()
        suggested=f"Elplan_kernedata_{date.today().isoformat()}{portability.CORE_EXTENSION}"
        path,_=QFileDialog.getSaveFileName(self,"Eksportér kernedata",suggested,f"Elplan kernedata (*{portability.CORE_EXTENSION})")
        if not path:return
        if not path.lower().endswith(portability.CORE_EXTENSION):path += portability.CORE_EXTENSION
        try:
            target=portability.export_core_data(path,APP_VERSION)
        except Exception as exc:
            QMessageBox.critical(self,"Kernedata",f"Kernedata kunne ikke eksporteres:\n{exc}")
            return
        QMessageBox.information(
            self,"Kernedata eksporteret",
            f"Kernedata er samlet i én fil:\n{target}\n\n"
            f"Artikelbase: {summary['articles']} artikler\n"
            f"Globale styklister: {summary['assemblies']}\n"
            f"Priser/prisestimeringer: {summary['prices']}\n\n"
            "Projektfiler og DWG/DXF er ikke med i denne pakke."
        )

    def import_core_data_package(self) -> None:
        path,_=QFileDialog.getOpenFileName(self,"Importér kernedata","",f"Elplan kernedata (*{portability.CORE_EXTENSION})")
        if not path:return
        box=QMessageBox(self); box.setIcon(QMessageBox.Icon.Question); box.setWindowTitle("Importér kernedata")
        box.setText("Hvordan skal de importerede kernedata behandles?")
        box.setInformativeText(
            "Erstat er bedst ved flytning til en ny PC. Flet bevarer lokale poster og lader den importerede version vinde ved samme artikel-/stykliste-ID.\n\n"
            "Programmet laver automatisk en backup af de nuværende kernedata før import."
        )
        replace_btn=box.addButton("Erstat kernedata",QMessageBox.ButtonRole.AcceptRole)
        merge_btn=box.addButton("Flet med eksisterende",QMessageBox.ButtonRole.ActionRole)
        cancel_btn=box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(replace_btn); box.exec()
        clicked=box.clickedButton()
        if clicked is cancel_btn or clicked is None:return
        replace=clicked is replace_btn
        try:
            result=portability.import_core_data(path,replace=replace,app_version=APP_VERSION)
            self.app_settings=core.load_app_settings()
            core.register_custom_symbol_records(self.app_settings.get("custom_symbols",[]))
            self._cached_article_catalog(refresh=True)
            self.global_bom_assemblies=deepcopy(user_library.load_global_bom_assemblies())
            self._refresh_palette_categories(); self._populate_symbol_palette(); self._refresh_cable_article_ui()
        except Exception as exc:
            QMessageBox.critical(self,"Kernedata",f"Kernedata kunne ikke importeres:\n{exc}")
            return
        QMessageBox.information(
            self,"Kernedata importeret",
            f"Importen er færdig.\n\nArtikelbase: {result['articles']} artikler\n"
            f"Globale styklister: {result['assemblies']}\nPriser/prisestimeringer: {result['prices']}\n\n"
            f"Backup af tidligere kernedata:\n{result['backup']}\n\n"
            "Nogle rene GUI-indstillinger anvendes først næste gang programmet startes."
        )

    def export_project_package(self) -> None:
        if self.project.path is None or self.project.dirty:
            if not self.save_project():return
        source=self._resolve_project_source(self.project)
        if source is None or not source.is_file():
            QMessageBox.warning(self,"Projektpakke","Projektets DWG/DXF-kilde kan ikke findes. Find eller åbn kildetegningen før eksport.")
            return
        base=self.project.path.stem.replace(".elplan","") if self.project.path else "projekt"
        suggested=str((self.project.path.parent if self.project.path else Path.cwd()) / f"{base}{portability.PROJECT_EXTENSION}")
        path,_=QFileDialog.getSaveFileName(self,"Eksportér projektpakke",suggested,f"Elplan projektpakke (*{portability.PROJECT_EXTENSION})")
        if not path:return
        if not path.lower().endswith(portability.PROJECT_EXTENSION):path += portability.PROJECT_EXTENSION
        try:
            target=portability.export_project_package(self.project.path,source,path,APP_VERSION)
        except Exception as exc:
            QMessageBox.critical(self,"Projektpakke",f"Projektpakken kunne ikke oprettes:\n{exc}")
            return
        QMessageBox.information(
            self,"Projektpakke eksporteret",
            f"Projekt og kildetegning er samlet i:\n{target}\n\n"
            "Pakken indeholder ikke artikelbase, globale styklister, prisbog eller programindstillinger. "
            "Eksportér kernedata separat, hvis den anden PC også skal have disse."
        )

    def import_project_package(self) -> None:
        path,_=QFileDialog.getOpenFileName(self,"Importér projektpakke","",f"Elplan projektpakke (*{portability.PROJECT_EXTENSION})")
        if not path:return
        if not self._confirm_discard_changes("importerer et andet projekt"):return
        try:
            manifest=portability.inspect_project_package(path)
        except Exception as exc:
            QMessageBox.critical(self,"Projektpakke",f"Projektpakken er ugyldig:\n{exc}")
            return
        base_dir=QFileDialog.getExistingDirectory(self,"Vælg mappe til det importerede projekt")
        if not base_dir:return
        name=str(manifest.get("project_name","") or Path(path).stem).strip() or "Elplan-projekt"
        safe_name="".join(ch if ch not in '<>:"/\\|?*' else '_' for ch in name).strip(" .") or "Elplan-projekt"
        destination=Path(base_dir)/safe_name
        if destination.exists() and any(destination.iterdir()):
            if QMessageBox.question(self,"Projektpakke",f"Mappen findes allerede og indeholder filer:\n{destination}\n\nVil du importere hertil alligevel?")!=QMessageBox.StandardButton.Yes:return
        try:
            result=portability.import_project_package(path,destination)
            project=ProjectDocument.load(result["project"])
            source=self._resolve_project_source(project)
            if source is None or not source.is_file():raise FileNotFoundError("Den udpakkede DWG/DXF-kilde kunne ikke findes.")
            self._load_cad_and_scene(str(source),project=project)
            self._remember_recent_project(project.path or result.get("project"))
            self._update_title()
        except Exception as exc:
            QMessageBox.critical(self,"Projektpakke",f"Projektpakken kunne ikke importeres:\n{exc}")
            return
        deps=(result.get("manifest",{}) or {}).get("dependencies",{}) if isinstance(result,dict) else {}
        missing_articles=[]
        available={a["article_no"] for a in user_library.load_core_article_catalog()}
        for no in deps.get("article_numbers",[]) if isinstance(deps,dict) else []:
            if no not in available:missing_articles.append(no)
        known_assemblies={a["id"] for a in user_library.load_global_bom_assemblies()}
        missing_assemblies=[aid for aid in (deps.get("assembly_ids",[]) if isinstance(deps,dict) else []) if aid not in known_assemblies]
        missing_bits=[]
        if missing_articles:missing_bits.append(f"{len(missing_articles)} artikelnumre")
        if missing_assemblies:missing_bits.append(f"{len(missing_assemblies)} styklister")
        suffix=("\n\nBemærk: Projektet refererer til " + " og ".join(missing_bits) + " som ikke findes i denne PC's kernedata. Importér også kernedata fra den anden PC." if missing_bits else "")
        QMessageBox.information(self,"Projekt importeret",f"Projektet er pakket ud og åbnet fra:\n{destination}{suffix}")

    def configure_project_storage(self, *, prefer_synced: bool = False) -> bool:
        mode, root = project_storage.configured_storage(self.app_settings)
        dlg=ProjectStorageDialog(self,mode=mode,root=str(root or ""),prefer_synced=prefer_synced)
        if dlg.exec()!=QDialog.DialogCode.Accepted:
            return False
        new_mode,new_root=dlg.values()
        data=core.load_app_settings()
        data["project_storage_mode"]=new_mode
        data["project_storage_root"]=new_root if new_mode!=project_storage.MODE_LEGACY else ""
        core.save_app_settings(data); self.app_settings=data
        label={project_storage.MODE_LEGACY:"Frit filvalg",project_storage.MODE_LOCAL:"Lokalt projektbibliotek",project_storage.MODE_SYNCED:"Synkroniseret projektbibliotek"}.get(new_mode,new_mode)
        self._notify(f"Projektlager: {label}",kind="success")
        return True

    def configure_core_data_storage(self) -> bool:
        return run_core_data_storage_dialog(self)

    def _structured_project_name_suggestion(self) -> str:
        return project_storage.project_name_from_path(getattr(self.project,"path",None),self._resolve_project_source(self.project) or getattr(self.project,"source_file",None))

    def _create_current_project_in_storage(self, *, migrate: bool) -> bool:
        mode, root = project_storage.configured_storage(self.app_settings)
        if mode==project_storage.MODE_LEGACY or root is None:
            if not self.configure_project_storage(prefer_synced=migrate):
                return False
            mode, root = project_storage.configured_storage(self.app_settings)
            if mode==project_storage.MODE_LEGACY or root is None:
                return False
        source=self._resolve_project_source(self.project)
        if source is None or not Path(source).is_file():
            QMessageBox.warning(self,"Projektlager","Projektets DWG/DXF kan ikke findes. Find eller åbn plantegningen før projektet flyttes til projektlageret.")
            return False
        suggestion=self._structured_project_name_suggestion()
        name,ok=QInputDialog.getText(self,"Projektmappe","Projektnavn",text=suggestion)
        if not ok or not str(name).strip(): return False
        action="Migrerer projekt…" if migrate else "Opretter projekt…"
        self._begin_busy(action,project_storage.sanitize_project_name(name))
        old_path=getattr(self.project,"path",None)
        old_source=str(self.project.source_file or "")
        try:
            result=project_storage.create_structured_project(
                storage_root=root,project_name=name,project_data=self.project.to_dict(),source_cad=source,
                storage_mode=mode,original_project_path=old_path,copy_existing_backups=bool(migrate),
            )
            self.project.path=result.layout.project_file
            self.project.source_file=result.source_reference
            # Save once through ProjectDocument as well so its saved snapshot/dirty
            # state matches the newly structured copy exactly.
            self.project.save(result.layout.project_file)
            project_storage.touch_project_info(self.project.path,source_file=self.project.source_file)
            self._adopt_saved_project_collaboration(self.project.path)
            if old_path:
                self._forget_recent_project(old_path)
            self._remember_recent_project(self.project.path)
            self.undo_stack.setClean(); self._update_title(); self._refresh_welcome_page()
            suffix=f" · {result.copied_backup_items} backup-elementer kopieret" if result.copied_backup_items else ""
            self._notify(f"Projekt gemt i projektlager: {result.layout.root.name}{suffix}",kind="success",timeout=3200)
            self._end_busy(success=True,detail=result.layout.root.name)
            return True
        except Exception as exc:
            self.project.path=old_path; self.project.source_file=old_source
            self._end_busy()
            QMessageBox.critical(self,"Projektlager",f"Projektet kunne ikke oprettes i projektlageret. Originalen er ikke ændret.\n\n{exc}")
            return False

    def migrate_current_project_to_storage(self) -> None:
        if not (getattr(self.project,"source_file","") or getattr(self.project,"path",None)):
            QMessageBox.information(self,"Migrér projekt","Åbn et projekt eller en DWG/DXF først."); return
        if self.project.dirty and QMessageBox.question(
            self,"Migrér projekt","Projektets aktuelle, også ikke-gemte, Elplan-data kopieres med til den nye placering.\n\nFortsæt?",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.Yes
        )!=QMessageBox.StandardButton.Yes:
            return
        self._create_current_project_in_storage(migrate=True)

    def save_project(self, save_as: bool = False) -> bool:
        if self.association_source_uid:
            # A save is an explicit commit point. Never write a half-finished
            # relation session without first turning it into one undoable edit.
            self._finish_active_association()
        elif self.association_pick_source:
            self._finish_association_mode("","Tilknytningsværktøjet blev afsluttet.",commit=False)
        target = self.project.path
        if not save_as and target is not None and not self._can_write_current_project():
            return False
        if target is None and not save_as:
            mode, root = project_storage.configured_storage(self.app_settings)
            if mode!=project_storage.MODE_LEGACY and root is not None:
                return self._create_current_project_in_storage(migrate=False)
        old_source = str(self.project.source_file or "")
        resolved_source = self._resolve_project_source(self.project)
        if save_as or target is None:
            suggested = str(target) if target else "projekt.elplan.json"
            path, _ = QFileDialog.getSaveFileName(self, "Gem Elplan-projekt", suggested, "Elplan projekt (*.elplan.json)")
            if not path:
                return False
            target = Path(path)
            if not str(target).lower().endswith(".elplan.json"):
                target = Path(str(target) + ".elplan.json")

            # Et relativt CAD-link er relativt til projektfilens mappe. Ved
            # 'Gem som' skal linket derfor genberegnes, ellers peger kopien
            # pludselig på en forkert fil næste gang den åbnes.
            if old_source and not Path(old_source).expanduser().is_absolute() and resolved_source is not None:
                try:
                    self.project.source_file = os.path.relpath(str(resolved_source), str(target.parent))
                except (OSError, ValueError):
                    self.project.source_file = str(resolved_source)
        try:
            self.project.save(target)
            project_storage.touch_project_info(target,source_file=self.project.source_file)
            if save_as or self._project_lock_path is None:
                self._adopt_saved_project_collaboration(target)
            else:
                self._note_project_saved_for_collaboration(target)
            self._remember_recent_project(target)
            self.undo_stack.setClean()
            self._update_title()
            self._notify(f"Projekt gemt: {target.name}", kind="success")
            return True
        except Exception as exc:
            self.project.source_file = old_source
            QMessageBox.critical(self, "Kunne ikke gemme", str(exc))
            return False

    def closeEvent(self, event) -> None:
        if not self._confirm_discard_changes("lukker programmet"):
            event.ignore()
            return
        self._save_main_window_layout()
        self._release_current_project_lock()
        event.accept()

def run() -> int:
    configure_logging(user_library.user_data_dir() / "logs")
    install_exception_hook()
    _register_windows_app_id()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    icon = _load_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    app.setOrganizationName("Elplan")
    settings=core.load_app_settings()
    appearance=core.normalize_appearance_mode(settings.get("appearance_mode","light"))
    _apply_application_palette(app,appearance)
    window = MainWindow()
    # Qt 6 exposes a live OS color-scheme signal on supported platforms. System
    # mode follows it immediately; older Qt builds simply resolve at startup.
    try:
        signal=getattr(app.styleHints(),"colorSchemeChanged",None)
        if signal is not None: signal.connect(window._system_appearance_changed)
    except Exception:
        pass
    window.show()
    return app.exec()
