from __future__ import annotations

"""Shared UI primitives for the Qt application.

0.53.0 deliberately keeps visual rules out of feature dialogs.  The values in
this module are the single source of truth for panel spacing, minimum widths and
small reusable headers.  Feature modules should use these helpers instead of
inventing new pixel values.
"""

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDockWidget,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QDialog,
)


@dataclass(frozen=True)
class UiMetrics:
    panel_margin: int = 10
    panel_spacing: int = 8
    compact_spacing: int = 6
    section_spacing: int = 7
    toolbar_icon: int = 18
    left_dock_min: int = 260
    inspector_min: int = 320
    left_dock_default: int = 285
    inspector_default: int = 350


UI = UiMetrics()


def tune_panel_layout(layout: QLayout, *, compact: bool = False, bottom: int | None = None) -> QLayout:
    """Apply the standard panel rhythm to a layout and return it for chaining."""
    margin = UI.panel_margin
    layout.setContentsMargins(margin, margin, margin, margin if bottom is None else int(bottom))
    if hasattr(layout, "setSpacing"):
        layout.setSpacing(UI.compact_spacing if compact else UI.panel_spacing)
    return layout


def tune_form_layout(layout: QFormLayout) -> QFormLayout:
    layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    layout.setHorizontalSpacing(10)
    layout.setVerticalSpacing(UI.section_spacing)
    return layout


def prepare_dock(dock: QDockWidget, *, minimum_width: int, object_name: str) -> QDockWidget:
    """Give all docks the same capabilities and predictable sizing."""
    dock.setObjectName(object_name)
    dock.setMinimumWidth(int(minimum_width))
    dock.setFeatures(
        QDockWidget.DockWidgetFeature.DockWidgetClosable
        | QDockWidget.DockWidgetFeature.DockWidgetMovable
        | QDockWidget.DockWidgetFeature.DockWidgetFloatable
    )
    return dock


def make_inspector_header(parent: QWidget | None = None) -> tuple[QFrame, QLabel, QLabel, QLabel]:
    """Compact shared header for the unified right-side inspector."""
    frame = QFrame(parent)
    frame.setObjectName("inspectorHeader")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(11, 9, 11, 9)
    layout.setSpacing(2)

    eyebrow = QLabel("EGENSKABER", frame)
    eyebrow.setObjectName("inspectorEyebrow")
    title = QLabel("Intet valgt", frame)
    title.setObjectName("inspectorTitle")
    title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    hint = QLabel("Vælg et objekt på tegningen.", frame)
    hint.setObjectName("inspectorHint")
    hint.setWordWrap(True)

    layout.addWidget(eyebrow)
    layout.addWidget(title)
    layout.addWidget(hint)
    return frame, eyebrow, title, hint


def make_context_caption(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setObjectName("contextToolbarCaption")
    label.setMinimumWidth(105)
    return label


def configure_modern_dialog(dialog: QDialog, *, title: str | None = None, size: tuple[int,int] | None = None, minimum_size: tuple[int,int] | None = None) -> QDialog:
    """Apply the shared dialog identity without constraining feature layouts."""
    dialog.setProperty("elplanModernDialog", True)
    if title:
        dialog.setWindowTitle(str(title))
    if minimum_size:
        dialog.setMinimumSize(int(minimum_size[0]), int(minimum_size[1]))
    if size:
        dialog.resize(int(size[0]), int(size[1]))
    return dialog


def make_dialog_header(title: str, subtitle: str = "", *, eyebrow: str = "") -> QFrame:
    frame = QFrame()
    frame.setObjectName("dialogHeader")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 4)
    layout.setSpacing(3)
    if eyebrow:
        e = QLabel(str(eyebrow), frame)
        e.setObjectName("dialogEyebrow")
        layout.addWidget(e)
    t = QLabel(str(title), frame)
    t.setObjectName("dialogTitleLarge")
    t.setWordWrap(True)
    layout.addWidget(t)
    if subtitle:
        sub = QLabel(str(subtitle), frame)
        sub.setObjectName("dialogSubtitle")
        sub.setWordWrap(True)
        layout.addWidget(sub)
    return frame


class DisclosureSection(QWidget):
    """Small progressive-disclosure container used by inspectors/dialogs."""
    def __init__(self, title: str, content: QWidget, *, expanded: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("disclosureSection")
        self._content = content
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)
        self.button = QToolButton(self)
        self.button.setObjectName("disclosureHeader")
        self.button.setText(str(title))
        self.button.setCheckable(True)
        self.button.setChecked(bool(expanded))
        self.button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.button.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)
        self.button.toggled.connect(self._toggled)
        root.addWidget(self.button)
        root.addWidget(content)
        content.setVisible(bool(expanded))

    def _toggled(self, checked: bool) -> None:
        self.button.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)
        self._content.setVisible(bool(checked))

    def setExpanded(self, expanded: bool) -> None:
        self.button.setChecked(bool(expanded))

    def isExpanded(self) -> bool:
        return self.button.isChecked()
