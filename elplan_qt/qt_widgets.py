from __future__ import annotations

"""Shared Qt controls and small widget helpers.

These controls used to live in ``qt_app.py``.  Keeping them here prevents
feature modules from depending on the main-window module and makes lazy-loaded
dialog modules possible without circular imports.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import (
    QApplication, QDialog, QPushButton,
    QComboBox as _QtQComboBox,
    QDialogButtonBox as _QtQDialogButtonBox,
    QDoubleSpinBox as _QtQDoubleSpinBox,
    QFormLayout as _QtQFormLayout,
    QSpinBox as _QtQSpinBox,
)

import core_logic as core

class _AlwaysVisibleSpinArrowMixin:
    """Paint spin-box chevrons after Qt/QSS has painted the control.

    QStyleSheetStyle can consume the native arrow primitives on Windows when
    the up/down button subcontrols are styled.  Painting the two chevrons as
    the final step of the widget paint event makes their visibility
    deterministic across Windows themes and DPI settings while leaving the
    native clickable subcontrols intact.
    """

    _SPIN_ARROW_COLOR = QColor("#334155")
    _SPIN_ARROW_DISABLED_COLOR = QColor("#9aa2ac")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setProperty("elplanChevron", True)

    def _paint_visible_spin_arrows(self) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        palette = self.palette()
        color = palette.color(QPalette.ColorRole.Text) if self.isEnabled() else palette.color(QPalette.ColorRole.Mid)
        pen = QPen(color)
        pen.setWidthF(1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Keep the glyphs inside the 22 px QSS button strip.  Coordinates are
        # logical pixels, so Qt scales them correctly on high-DPI displays.
        zone_width = min(22.0, max(16.0, self.width() * 0.24))
        cx = self.width() - zone_width / 2.0 - 1.0
        half = max(2.5, min(4.0, zone_width * 0.18))
        top_cy = self.height() * 0.28
        bottom_cy = self.height() * 0.72

        for cy, direction in ((top_cy, -1.0), (bottom_cy, 1.0)):
            path = QPainterPath()
            path.moveTo(cx - half, cy - direction * half * 0.38)
            path.lineTo(cx, cy + direction * half * 0.62)
            path.lineTo(cx + half, cy - direction * half * 0.38)
            painter.drawPath(path)
        painter.end()

class QDoubleSpinBox(_AlwaysVisibleSpinArrowMixin, _QtQDoubleSpinBox):
    """QDoubleSpinBox with deterministic visible up/down arrows."""

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        self._paint_visible_spin_arrows()

class QSpinBox(_AlwaysVisibleSpinArrowMixin, _QtQSpinBox):
    """QSpinBox with deterministic visible up/down arrows."""

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        self._paint_visible_spin_arrows()

class QComboBox(_QtQComboBox):
    """QComboBox with a deterministic chevron independent of Windows/QSS."""

    _ARROW_COLOR = QColor("#334155")
    _ARROW_DISABLED_COLOR = QColor("#9aa2ac")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setProperty("elplanChevron", True)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        palette = self.palette()
        pen = QPen(palette.color(QPalette.ColorRole.Text) if self.isEnabled() else palette.color(QPalette.ColorRole.Mid))
        pen.setWidthF(1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        cx = self.width() - 12.5
        cy = self.height() * 0.50
        half = 3.4
        path = QPainterPath()
        path.moveTo(cx - half, cy - 1.4)
        path.lineTo(cx, cy + 2.0)
        path.lineTo(cx + half, cy - 1.4)
        painter.drawPath(path)
        painter.end()

class QFormLayout(_QtQFormLayout):
    """Consistent form layout used by every editor/dialog in the Qt UI."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFieldGrowthPolicy(_QtQFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        self.setHorizontalSpacing(12)
        self.setVerticalSpacing(8)

class QDialogButtonBox(_QtQDialogButtonBox):
    """Dialog buttons with a predictable primary/destructive hierarchy."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCenterButtons(False)
        QTimer.singleShot(0, self._apply_role_styles)

    def addButton(self, *args, **kwargs):
        button = super().addButton(*args, **kwargs)
        QTimer.singleShot(0, self._apply_role_styles)
        return button

    def _apply_role_styles(self) -> None:
        # Qt's default button captions are English unless a Qt translation pack
        # is installed. Translate only untouched defaults; custom captions such
        # as “Vælg artikel” and “Gem og luk” are preserved.
        defaults = {
            _QtQDialogButtonBox.StandardButton.Cancel: ("cancel", "Annuller"),
            _QtQDialogButtonBox.StandardButton.Close: ("close", "Luk"),
            _QtQDialogButtonBox.StandardButton.Save: ("save", "Gem"),
            _QtQDialogButtonBox.StandardButton.Yes: ("yes", "Ja"),
            _QtQDialogButtonBox.StandardButton.No: ("no", "Nej"),
            _QtQDialogButtonBox.StandardButton.Apply: ("apply", "Anvend"),
            _QtQDialogButtonBox.StandardButton.Reset: ("reset", "Nulstil"),
        }
        for standard, (english, danish) in defaults.items():
            button = self.button(standard)
            if button is not None and button.text().replace("&", "").strip().casefold() == english:
                button.setText(danish)

        accept_roles = {
            _QtQDialogButtonBox.ButtonRole.AcceptRole,
            _QtQDialogButtonBox.ButtonRole.YesRole,
            _QtQDialogButtonBox.ButtonRole.ApplyRole,
        }
        for button in self.buttons():
            role = self.buttonRole(button)
            if role in accept_roles:
                button.setObjectName("primaryButton")
            elif role == _QtQDialogButtonBox.ButtonRole.DestructiveRole:
                button.setObjectName("dangerButton")
            elif button.objectName() in {"primaryButton", "dangerButton"}:
                button.setObjectName("")
            button.style().unpolish(button)
            button.style().polish(button)

def _set_role(widget, role: str):
    """Assign a visual role without scattering local stylesheets through the UI."""
    widget.setObjectName(role)
    return widget

def _resize_dialog(dialog: QDialog, width: int, height: int) -> None:
    """Choose a comfortable initial size without opening outside the work area."""
    screen = dialog.parentWidget().screen() if dialog.parentWidget() is not None else QApplication.primaryScreen()
    if screen is not None:
        area = screen.availableGeometry()
        width = min(int(width), max(420, area.width() - 80))
        height = min(int(height), max(320, area.height() - 80))
    dialog.resize(int(width), int(height))

def _set_color_button(button: QPushButton, value: str) -> None:
    """Make colour selectors read as colour selectors while keeping the hex value legible."""
    value = core.normalize_hex_color(value)
    button.setText(value)
    color = QColor(value)
    luminance = 0.2126 * color.red() + 0.7152 * color.green() + 0.0722 * color.blue()
    text = "#17202a" if luminance > 165 else "#ffffff"
    button.setStyleSheet(
        f"QPushButton {{ background:{value}; color:{text}; border:1px solid #8f99a5; font-weight:600; }}"
        f"QPushButton:hover {{ border:2px solid #4d7fb6; }}"
        f"QPushButton:disabled {{ background:#e8ebef; color:#98a0aa; border:1px solid #d5dae0; }}"
    )
