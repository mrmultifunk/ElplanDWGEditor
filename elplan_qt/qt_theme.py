from __future__ import annotations

import sys
from string import Template

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import QApplication, QProxyStyle, QStyle, QStyleFactory

import core_logic as core

def _system_prefers_dark(app: QApplication | None = None) -> bool:
    """Best-effort Windows/Qt color-scheme detection without hard Qt-version coupling."""
    app = app or QApplication.instance()
    if app is None:
        return False
    try:
        hints = app.styleHints()
        getter = getattr(hints, "colorScheme", None)
        if callable(getter):
            scheme = getter()
            dark_enum = getattr(getattr(Qt, "ColorScheme", object), "Dark", None)
            if dark_enum is not None:
                return scheme == dark_enum
            if "dark" in str(scheme).lower():
                return True
    except Exception:
        pass
    # Older Qt builds on Windows may not expose colorScheme(). Read the same
    # per-user setting Windows uses for application appearance before falling
    # back to the current Qt palette.
    if sys.platform.startswith("win"):
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                value,_kind=winreg.QueryValueEx(key,"AppsUseLightTheme")
            return int(value)==0
        except Exception:
            pass
    try:
        return app.palette().color(QPalette.ColorRole.Window).lightness() < 128
    except Exception:
        return False


def _resolved_dark_mode(mode: str, app: QApplication | None = None) -> bool:
    mode = core.normalize_appearance_mode(mode)
    return _system_prefers_dark(app) if mode == "system" else mode == "dark"


def _application_dark() -> bool:
    app = QApplication.instance()
    return bool(app.property("elplanDarkMode")) if app is not None else False


def _canvas_dark() -> bool:
    app = QApplication.instance()
    return bool(app.property("elplanCanvasDark")) if app is not None else False


def _theme_color(light: str, dark: str) -> QColor:
    return QColor(dark if _application_dark() else light)


def _canvas_color(light: str, dark: str) -> QColor:
    return QColor(dark if _canvas_dark() else light)


def _application_stylesheet(dark: bool, canvas_dark: bool = False) -> str:
    """One tokenized stylesheet for light/dark mode.

    Keeping both appearances in one template prevents the dark theme from
    silently drifting away as new controls are added to the application.
    Technical drawing colors are handled separately from UI colors.
    """
    t = {
        "window": "#171a1f" if dark else "#f3f5f7",
        "surface": "#20242a" if dark else "#ffffff",
        "surface2": "#252a31" if dark else "#f8fafc",
        "surface3": "#2b3139" if dark else "#f1f4f7",
        "input": "#1d2127" if dark else "#ffffff",
        "disabled_bg": "#24282e" if dark else "#f0f2f4",
        "text": "#e5e9ef" if dark else "#1f2933",
        "text2": "#c7ced7" if dark else "#27313c",
        "muted": "#98a4b3" if dark else "#687480",
        "disabled": "#68727f" if dark else "#9aa2ac",
        "border": "#3b434d" if dark else "#c7cfd9",
        "border2": "#333a43" if dark else "#d8dde4",
        "border3": "#46505c" if dark else "#aab6c3",
        "accent": "#72a8df" if dark else "#315f8f",
        "accent_strong": "#8bbcf0" if dark else "#174f88",
        "accent_bg": "#26384b" if dark else "#edf3fb",
        "accent_bg2": "#2b435e" if dark else "#dceafa",
        "accent_border": "#55779c" if dark else "#9ebbe0",
        "selection": "#31577d" if dark else "#dceafa",
        "selection_text": "#f4f8fc" if dark else "#173f68",
        "positive": "#79c3bb" if dark else "#356a68",
        "warning": "#f0a15d" if dark else "#a74400",
        "danger": "#f08c8c" if dark else "#a83232",
        "danger_bg": "#3b2528" if dark else "#fffafa",
        "info_bg": "#24374d" if dark else "#eaf2fc",
        "info_border": "#456584" if dark else "#b7cde9",
        "tooltip": "#25282d" if dark else "#fffdf2",
        "tooltip_border": "#59616b" if dark else "#c9c2a4",
        "scroll": "#20242a" if dark else "#f4f6f8",
        "scroll_handle": "#4a535e" if dark else "#c6cdd5",
        "scroll_hover": "#606b78" if dark else "#aeb8c3",
        "canvas": "#1b2026" if (dark and canvas_dark) else "#ffffff",
        "hover_card": "#20252c" if dark else "#ffffff",
        "hover_bom": "#253343" if dark else "#f0f6fc",
        "assistant_warn": "#382d20" if dark else "#fffaf0",
    }
    template = Template(r"""
        QMainWindow, QDialog, QMessageBox { background: $window; color: $text; }
        QWidget { color: $text; font-size: 12px; }

        QMenuBar { background: $surface; border-bottom: 1px solid $border2; padding: 2px 6px; spacing: 2px; }
        QMenuBar::item { padding: 5px 9px; border-radius: 4px; background: transparent; }
        QMenuBar::item:selected { background: $accent_bg; color: $accent_strong; }
        QMenuBar::item:disabled { color: $disabled; }
        QMenu { background: $surface; color: $text; border: 1px solid $border; padding: 5px; }
        QMenu::item { padding: 6px 28px 6px 9px; border-radius: 4px; }
        QMenu::item:selected { background: $accent_bg2; color: $selection_text; }
        QMenu::item:disabled { color: $disabled; }
        QMenu::separator { height: 1px; background: $border2; margin: 5px 6px; }

        QToolBar#mainToolbar { background: $surface; border: 0; border-bottom: 1px solid $border2; spacing: 4px; padding: 5px 7px; }
        QToolBar#mainToolbar::separator { background: $border2; width: 1px; margin: 5px 4px; }
        QToolBar#mainToolbar QToolButton { color: $text2; background: transparent; border: 1px solid transparent; border-radius: 5px; padding: 5px 8px; min-height: 24px; }
        QToolBar#mainToolbar QToolButton:hover { background: $accent_bg; border-color: $accent_border; color: $accent_strong; }
        QToolBar#mainToolbar QToolButton:pressed, QToolBar#mainToolbar QToolButton:checked { background: $accent_bg2; border-color: $accent_border; color: $accent_strong; }
        QToolBar#mainToolbar QToolButton:disabled { color: $disabled; background: transparent; }

        QToolBar#contextToolbar { background: $surface2; border: 0; border-bottom: 1px solid $border2; spacing: 3px; padding: 3px 7px; }
        QToolBar#contextToolbar::separator { background: $border2; width: 1px; margin: 4px 5px; }
        QToolBar#contextToolbar QToolButton { color: $text2; background: transparent; border: 1px solid transparent; border-radius: 5px; padding: 4px 7px; min-height: 22px; }
        QToolBar#contextToolbar QToolButton:hover { background: $accent_bg; border-color: $accent_border; color: $accent_strong; }
        QToolBar#contextToolbar QToolButton:pressed, QToolBar#contextToolbar QToolButton:checked { background: $accent_bg2; border-color: $accent_border; color: $accent_strong; }
        QToolBar#contextToolbar QComboBox { min-width: 135px; max-width: 210px; min-height: 18px; padding-top: 3px; padding-bottom: 3px; }
        QLabel#contextToolbarCaption { color: $muted; font-size: 11px; font-weight: 700; padding: 0 6px 0 2px; }

        QDockWidget { color: $text; font-weight: 600; }
        QDockWidget::title { text-align: left; background: $surface2; border-bottom: 1px solid $border2; padding: 7px 9px; font-weight: 600; }
        QDockWidget::close-button, QDockWidget::float-button { border: 0; background: transparent; padding: 2px; border-radius: 3px; }
        QDockWidget::close-button:hover, QDockWidget::float-button:hover { background: $accent_bg; }
        QDockWidget > QWidget { background: $window; }

        QTabWidget::pane { background: $surface; border: 1px solid $border; border-radius: 6px; top: -1px; }
        QTabBar::tab { background: $surface3; color: $muted; border: 1px solid $border; border-bottom: 0; padding: 7px 15px; min-width: 78px; border-top-left-radius: 5px; border-top-right-radius: 5px; margin-right: 2px; }
        QTabBar::tab:selected { background: $surface; color: $accent_strong; font-weight: 600; }
        QTabBar::tab:hover:!selected { background: $accent_bg; }
        QTabBar::tab:disabled { color: $disabled; background: $disabled_bg; }

        QGroupBox { background: $surface; border: 1px solid $border2; border-radius: 7px; margin-top: 14px; padding: 11px 9px 9px 9px; font-weight: 600; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: $text2; background: $surface; }
        QGroupBox:disabled { color: $disabled; background: $disabled_bg; border-color: $border2; }
        QGroupBox::title:disabled { color: $disabled; background: $disabled_bg; }

        QFrame#inspectorHeader { background: $surface2; border: 0; border-bottom: 1px solid $border2; }
        QLabel#inspectorEyebrow { color: $muted; font-size: 9px; font-weight: 700; letter-spacing: 0.5px; }
        QLabel#inspectorTitle { color: $text; font-size: 14px; font-weight: 700; }
        QLabel#inspectorHint { color: $muted; font-size: 10px; }
        QFrame#inspectorSummaryCard { background: $surface; border: 0; border-bottom: 1px solid $border2; padding: 2px; }
        QLabel#inspectorSummaryKind { color: $accent; background: $accent_bg; border: 1px solid $accent_border; border-radius: 7px; padding: 2px 6px; font-size: 9px; font-weight: 700; }
        QLabel#inspectorSummaryIdentity { color: $text; font-size: 13px; font-weight: 700; }
        QLabel#inspectorSummaryRoute { color: $text2; font-size: 11px; }
        QLabel#inspectorSummaryChip { color: $muted; background: $surface3; border: 1px solid $border2; border-radius: 7px; padding: 2px 6px; font-size: 9px; font-weight: 600; }

        QFrame#workflowBar { background: $surface; border: 1px solid $accent_border; border-radius: 10px; }
        QLabel#workflowMode { color: $accent_strong; background: $accent_bg; border: 1px solid $accent_border; border-radius: 8px; padding: 4px 7px; min-width: 72px; font-size: 9px; font-weight: 700; }
        QLabel#workflowTitle { color: $text; font-size: 12px; font-weight: 700; }
        QLabel#workflowDetail { color: $muted; font-size: 10px; }
        QPushButton#workflowPrimaryButton { color: #ffffff; background: #2f6fac; border: 1px solid #3f7cb8; border-radius: 6px; padding: 5px 9px; font-weight: 600; }
        QPushButton#workflowPrimaryButton:hover { background: #3c7dbb; border-color: #5a90c5; color: #ffffff; }
        QPushButton#workflowQuietButton { color: $text2; background: $surface2; border: 1px solid $border2; border-radius: 6px; padding: 5px 8px; }
        QPushButton#workflowQuietButton:hover { background: $accent_bg; border-color: $accent_border; color: $accent_strong; }

        QFrame#cableCategoryStrip { background: $surface; border: 1px solid $border2; border-radius: 10px; }
        QLabel#cableCategoryStripTitle { color: $muted; font-size: 9px; font-weight: 800; letter-spacing: 0.7px; padding: 0 3px; }
        QScrollArea#cableCategoryScroll, QWidget#cableCategoryStripContent { background: transparent; border: 0; }
        QToolButton#cableCategoryChip { color: $text2; background: $surface2; border: 1px solid $border2; border-radius: 8px; padding: 4px 7px; min-height: 22px; font-size: 10px; font-weight: 600; }
        QToolButton#cableCategoryChip:hover { background: $accent_bg; border-color: $accent_border; color: $accent_strong; }
        QToolButton#cableCategoryChip[categoryVisible="false"] { color: $disabled; background: $disabled_bg; border-color: $border2; }
        QToolButton#cableCategoryChip[categoryVisible="true"] { color: $text; }
        QToolButton#cableCategoryConfigure { color: $muted; background: transparent; border: 1px solid transparent; border-radius: 8px; padding: 3px 7px; font-size: 16px; font-weight: 700; }
        QToolButton#cableCategoryConfigure:hover { color: $accent_strong; background: $accent_bg; border-color: $accent_border; }
        QGraphicsView#miniMapView { background: $surface; border: 1px solid $accent_border; border-radius: 10px; }

        QFrame#dialogHeader { background: transparent; border: 0; border-bottom: 1px solid $border2; padding-bottom: 7px; }
        QLabel#dialogEyebrow { color: $muted; font-size: 9px; font-weight: 700; letter-spacing: 0.6px; }
        QLabel#dialogTitleLarge { color: $text; font-size: 18px; font-weight: 700; }
        QLabel#dialogSubtitle { color: $muted; font-size: 11px; }
        QWidget#disclosureSection { background: transparent; border: 0; }
        QToolButton#disclosureHeader { color: $text2; background: $surface2; border: 1px solid $border2; border-radius: 6px; padding: 6px 8px; text-align: left; font-weight: 600; }
        QToolButton#disclosureHeader:hover { background: $accent_bg; border-color: $accent_border; color: $accent_strong; }

        QWidget#welcomePage { background: $window; }
        QLabel#welcomeEyebrow { color: $accent; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
        QLabel#welcomeTitle { color: $text; font-size: 27px; font-weight: 700; }
        QLabel#welcomeSubtitle { color: $muted; font-size: 12px; }
        QLabel#welcomeHint { color: $muted; font-size: 10px; }
        QFrame#welcomeCard { background: $surface; border: 1px solid $border2; border-radius: 9px; }
        QPushButton#recentProjectButton { text-align: left; background: transparent; border: 1px solid transparent; border-radius: 7px; padding: 9px 11px; min-height: 38px; }
        QPushButton#recentProjectButton:hover { background: $accent_bg; border-color: $accent_border; color: $accent_strong; }

        QFrame#toastOverlay { background: $surface; border: 1px solid $accent_border; border-radius: 8px; }
        QFrame#toastOverlay[kind="success"] { border-color: $positive; }
        QFrame#toastOverlay[kind="warning"] { border-color: $warning; }
        QLabel#toastText { color: $text; font-weight: 600; }
        QLabel#toastIcon { color: $accent; font-size: 15px; font-weight: 700; min-width: 18px; }
        QFrame#toastOverlay[kind="success"] QLabel#toastIcon { color: $positive; }
        QFrame#toastOverlay[kind="warning"] QLabel#toastIcon { color: $warning; }

        QWidget#busyOverlay { background: rgba(8, 12, 18, 158); }
        QFrame#busyCard { background: $surface; border: 1px solid $accent_border; border-radius: 14px; }
        QLabel#busyEyebrow { color: $accent; font-size: 10px; font-weight: 700; }
        QLabel#busyTitle { color: $text; font-size: 19px; font-weight: 700; }
        QLabel#busyDetail { color: $muted; font-size: 11px; }
        QProgressBar#busyProgress { min-height: 6px; max-height: 6px; border: 0; border-radius: 3px; background: $surface3; }
        QProgressBar#busyProgress::chunk { background: $accent; border-radius: 3px; }

        QFrame#detailPanel, QWidget#previewPanel, QFrame#switchConductorCard { background: $surface; border: 1px solid $border2; border-radius: 7px; }
        QScrollArea { background: transparent; border: 0; }
        QScrollArea > QWidget > QWidget { background: transparent; }

        QLabel { background: transparent; color: $text2; }
        QLabel#sectionTitle, QLabel#dialogTitle { color: $text; font-weight: 700; }
        QLabel#sectionTitle { font-size: 14px; } QLabel#dialogTitle { font-size: 15px; }
        QLabel#sectionHint, QLabel#subtleText { color: $muted; font-size: 11px; }
        QLabel#accentText { color: $accent; font-weight: 600; }
        QLabel#positiveText { color: $positive; font-weight: 600; }
        QLabel#dangerText { color: $danger; font-weight: 600; }
        QLabel#warningText { color: $warning; font-size: 11px; }
        QLabel#infoBanner { color: $text; background: $info_bg; border: 1px solid $info_border; border-radius: 6px; padding: 7px; font-weight: 600; }
        QLabel#statusPill, QLabel#storageStatusPill { color: $muted; background: $surface3; border: 1px solid $border2; border-radius: 8px; padding: 2px 7px; margin: 1px 3px; }
        QLabel#storageStatusPill[statusState="synced"] { color: $accent; border-color: $accent_border; }
        QLabel#storageStatusPill[statusState="conflict"] { color: $warning; border-color: $warning; font-weight: 700; }

        QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox, QPlainTextEdit {
            color: $text; background: $input; border: 1px solid $border; border-radius: 5px; padding: 5px 7px; min-height: 18px;
            selection-background-color: $selection; selection-color: $selection_text;
        }
        QLineEdit:hover, QDoubleSpinBox:hover, QSpinBox:hover, QComboBox:hover, QPlainTextEdit:hover { border-color: $border3; }
        QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus { border: 1px solid $accent_border; background: $input; }
        QLineEdit:disabled, QDoubleSpinBox:disabled, QSpinBox:disabled, QComboBox:disabled, QPlainTextEdit:disabled { color: $disabled; background: $disabled_bg; border-color: $border2; }
        QLineEdit:read-only { background: $surface2; color: $muted; }

        QDoubleSpinBox[elplanChevron="true"], QSpinBox[elplanChevron="true"] { padding-right: 28px; }
        QDoubleSpinBox[elplanChevron="true"]::up-button, QSpinBox[elplanChevron="true"]::up-button { subcontrol-origin: border; subcontrol-position: top right; width: 22px; background: $surface3; border-left: 1px solid $border; border-bottom: 1px solid $border2; border-top-right-radius: 4px; }
        QDoubleSpinBox[elplanChevron="true"]::down-button, QSpinBox[elplanChevron="true"]::down-button { subcontrol-origin: border; subcontrol-position: bottom right; width: 22px; background: $surface3; border-left: 1px solid $border; border-bottom-right-radius: 4px; }
        QDoubleSpinBox[elplanChevron="true"]::up-button:hover, QSpinBox[elplanChevron="true"]::up-button:hover, QDoubleSpinBox[elplanChevron="true"]::down-button:hover, QSpinBox[elplanChevron="true"]::down-button:hover { background: $accent_bg; }
        QDoubleSpinBox[elplanChevron="true"]::up-button:pressed, QSpinBox[elplanChevron="true"]::up-button:pressed, QDoubleSpinBox[elplanChevron="true"]::down-button:pressed, QSpinBox[elplanChevron="true"]::down-button:pressed { background: $accent_bg2; }
        QDoubleSpinBox[elplanChevron="true"]::up-button:disabled, QSpinBox[elplanChevron="true"]::up-button:disabled, QDoubleSpinBox[elplanChevron="true"]::down-button:disabled, QSpinBox[elplanChevron="true"]::down-button:disabled { background: $disabled_bg; border-left-color: $border2; }

        QComboBox { padding-right: 30px; }
        QComboBox::drop-down { subcontrol-origin: border; subcontrol-position: top right; width: 24px; background: $surface3; border: 0; border-left: 1px solid $border; border-top-right-radius: 4px; border-bottom-right-radius: 4px; }
        QComboBox::drop-down:hover { background: $accent_bg; } QComboBox::drop-down:pressed { background: $accent_bg2; }
        QComboBox::drop-down:disabled { background: $disabled_bg; border-left-color: $border2; }
        QComboBox[elplanChevron="true"]::down-arrow { image: none; width: 0; height: 0; }
        QComboBox QAbstractItemView { background: $surface; color: $text; border: 1px solid $border; selection-background-color: $selection; selection-color: $selection_text; outline: 0; padding: 3px; }

        QCheckBox, QRadioButton { spacing: 7px; color: $text2; }
        QCheckBox::indicator, QRadioButton::indicator { width: 16px; height: 16px; }
        QCheckBox:hover, QRadioButton:hover { color: $accent_strong; }
        QCheckBox:disabled, QRadioButton:disabled { color: $disabled; }

        QPushButton { color: $text2; background: $surface2; border: 1px solid $border; border-radius: 5px; padding: 6px 10px; min-height: 18px; font-weight: 500; }
        QPushButton:hover { background: $accent_bg; border-color: $accent_border; color: $accent_strong; }
        QPushButton:focus { border: 1px solid $accent_border; } QPushButton:pressed { background: $accent_bg2; border-color: $accent_border; }
        QPushButton:disabled { color: $disabled; background: $disabled_bg; border-color: $border2; }
        QPushButton#primaryButton { color: #ffffff; background: #2f6fac; border-color: #3f7cb8; font-weight: 600; }
        QPushButton#primaryButton:hover { background: #3c7dbb; border-color: #5a90c5; color: #ffffff; }
        QPushButton#primaryButton:pressed { background: #285f93; border-color: #285f93; }
        QPushButton#primaryButton:disabled { color: #d5dde6; background: #53677b; border-color: #53677b; }
        QPushButton#quietButton { background: transparent; border-color: transparent; color: $accent; padding-left: 7px; padding-right: 7px; }
        QPushButton#quietButton:hover { background: $accent_bg; border-color: transparent; }
        QPushButton#quietButton:disabled { color: $disabled; background: transparent; border-color: transparent; }
        QFrame#propertyWorkflowTabs { background: $surface; border: 0; }
        QPushButton#propertyWorkflowTab { background: $surface2; color: $muted; border: 1px solid $border2; border-radius: 5px; padding: 6px 5px; font-weight: 600; }
        QPushButton#propertyWorkflowTab:hover { color: $accent_strong; background: $accent_bg; border-color: $accent_border; }
        QPushButton#propertyWorkflowTab:checked { color: #ffffff; background: #2f6fac; border-color: #3f7cb8; }
        QPushButton#dangerButton { color: $danger; background: $danger_bg; border-color: $danger; }
        QPushButton#dangerButton:hover { background: $accent_bg; }
        QPushButton#dangerButton:disabled { color: $disabled; background: $disabled_bg; border-color: $border2; }
        QPushButton#iconButton { min-width: 26px; max-width: 34px; padding: 4px; font-size: 15px; font-weight: 600; }
        QDialogButtonBox QPushButton { min-width: 82px; }

        QListWidget, QListView { color: $text; background: $surface; border: 1px solid $border2; border-radius: 5px; padding: 3px; outline: 0; selection-background-color: $selection; selection-color: $selection_text; }
        QListWidget:focus, QListView:focus { border-color: $accent_border; }
        QListWidget:disabled, QListView:disabled { color: $disabled; background: $disabled_bg; border-color: $border2; }
        QListWidget::item, QListView::item { border: 1px solid transparent; border-radius: 6px; padding: 4px; }
        QListWidget::item:hover, QListView::item:hover { background: $accent_bg; border-color: $accent_border; }
        QListWidget::item:selected, QListView::item:selected { background: $selection; border-color: $accent_border; color: $selection_text; }

        QTableView, QTableWidget { background: $surface; alternate-background-color: $surface2; color: $text; border: 1px solid $border2; border-radius: 5px; gridline-color: $border2; selection-background-color: $selection; selection-color: $selection_text; outline: 0; }
        QTableView:focus, QTableWidget:focus { border-color: $accent_border; }
        QTableView::item, QTableWidget::item { padding: 4px 6px; border: 0; }
        QTableView::item:hover, QTableWidget::item:hover { background: $accent_bg; }
        QTableView::item:selected:!active, QTableWidget::item:selected:!active { background: $selection; color: $selection_text; }
        QHeaderView::section { color: $text2; background: $surface3; border: 0; border-right: 1px solid $border2; border-bottom: 1px solid $border; padding: 6px 8px; font-weight: 600; }
        QHeaderView::section:hover { background: $accent_bg; }
        QTableCornerButton::section { background: $surface3; border: 0; border-right: 1px solid $border2; border-bottom: 1px solid $border; }

        QSlider::groove:horizontal { height: 4px; background: $border2; border-radius: 2px; }
        QSlider::handle:horizontal { width: 14px; margin: -5px 0; border-radius: 7px; background: #5d89b9; }
        QSlider::handle:horizontal:hover { background: #6fa1d4; } QSlider::sub-page:horizontal { background: #6f94bc; border-radius: 2px; }

        QProgressBar { color: $text2; background: $surface3; border: 1px solid $border; border-radius: 5px; text-align: center; min-height: 18px; }
        QProgressBar::chunk { background: #4f80b3; border-radius: 4px; }
        QSplitter::handle { background: $border2; }
        QSplitter::handle:hover { background: $accent_border; }

        QStatusBar { color: $muted; background: $surface; border-top: 1px solid $border2; }
        QGraphicsView { background: $canvas; border: 0; }
        QToolTip { color: $text; background: $tooltip; border: 1px solid $tooltip_border; padding: 5px; }
        QScrollBar:vertical { background: $scroll; width: 12px; margin: 0; }
        QScrollBar::handle:vertical { background: $scroll_handle; min-height: 28px; border-radius: 5px; margin: 2px; }
        QScrollBar::handle:vertical:hover { background: $scroll_hover; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        QScrollBar:horizontal { background: $scroll; height: 12px; margin: 0; }
        QScrollBar::handle:horizontal { background: $scroll_handle; min-width: 28px; border-radius: 5px; margin: 2px; }
        QScrollBar::handle:horizontal:hover { background: $scroll_hover; }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

        QFrame#cableAssistantPopup { background: $hover_card; border: 1px solid $accent_border; border-radius: 8px; }
        QFrame#cableMarkingPopup { background: $hover_card; border: 1px solid $accent_border; border-radius: 10px; }
        QFrame#cableAssistantPopup[warning="true"] { border: 2px solid #d59b35; background: $assistant_warn; }
        QLabel#cableAssistantTitle { color: $accent_strong; font-weight: 700; font-size: 10pt; }
        QLabel#cableAssistantMessage { color: $text2; } QLabel#cableAssistantHint { color: $muted; font-size: 8.5pt; }

        QFrame#hoverInfoPopup { background: $hover_card; border: 1px solid $border3; border-radius: 10px; }
        QLabel#hoverTitle { color: $text; font-size: 12px; font-weight: 700; background: transparent; }
        QFrame#hoverMarkingCard { background: $accent_bg; border: 1px solid $accent_border; border-radius: 7px; }
        QLabel#hoverMarkingCaption { color: $accent; font-size: 8px; font-weight: 700; background: transparent; }
        QLabel#hoverMarkingValue { color: $text; font-size: 15px; font-weight: 800; background: transparent; }
        QLabel#hoverMarkingExtra { color: $text2; font-size: 10px; font-weight: 600; background: transparent; }
        QLabel#hoverSubtitle { color: $muted; font-size: 10px; background: transparent; }
        QLabel#hoverDetails { color: $text2; font-size: 10px; background: transparent; }
        QFrame#hoverBomCard { background: $hover_bom; border: 1px solid $border; border-radius: 7px; }
        QLabel#hoverBomTitle { color: $accent; font-size: 10px; font-weight: 700; background: transparent; }
        QLabel#hoverBomText { color: $text2; font-size: 9.5px; background: transparent; }
    """)
    return template.substitute(t)

class ElplanProxyStyle(QProxyStyle):
    """Small visual fixes on top of Fusion.

    Qt style sheets can make native arrow glyphs hard to see on some Windows
    setups.  Draw the small directional indicators ourselves so spin boxes and
    combo boxes stay readable regardless of the Windows theme or DPI setting.
    """

    _ARROW_COLOR = QColor("#34414e")
    _ARROW_DISABLED_COLOR = QColor("#9aa2ac")

    def drawPrimitive(self, element, option, painter, widget=None):
        arrow_elements = {
            QStyle.PrimitiveElement.PE_IndicatorArrowUp,
            QStyle.PrimitiveElement.PE_IndicatorArrowDown,
            QStyle.PrimitiveElement.PE_IndicatorArrowLeft,
            QStyle.PrimitiveElement.PE_IndicatorArrowRight,
        }
        if element not in arrow_elements:
            return super().drawPrimitive(element, option, painter, widget)

        rect = option.rect
        if rect.width() < 4 or rect.height() < 4:
            return super().drawPrimitive(element, option, painter, widget)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        enabled = bool(option.state & QStyle.StateFlag.State_Enabled)
        try:
            arrow_color = option.palette.color(QPalette.ColorRole.Text) if enabled else option.palette.color(QPalette.ColorRole.Mid)
        except Exception:
            arrow_color = self._ARROW_COLOR if enabled else self._ARROW_DISABLED_COLOR
        pen = QPen(arrow_color)
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        cx = rect.center().x()
        cy = rect.center().y()
        half = max(2.0, min(4.0, min(rect.width(), rect.height()) * 0.22))
        path = QPainterPath()
        if element == QStyle.PrimitiveElement.PE_IndicatorArrowUp:
            path.moveTo(cx - half, cy + half * 0.45)
            path.lineTo(cx, cy - half * 0.55)
            path.lineTo(cx + half, cy + half * 0.45)
        elif element == QStyle.PrimitiveElement.PE_IndicatorArrowDown:
            path.moveTo(cx - half, cy - half * 0.45)
            path.lineTo(cx, cy + half * 0.55)
            path.lineTo(cx + half, cy - half * 0.45)
        elif element == QStyle.PrimitiveElement.PE_IndicatorArrowLeft:
            path.moveTo(cx + half * 0.45, cy - half)
            path.lineTo(cx - half * 0.55, cy)
            path.lineTo(cx + half * 0.45, cy + half)
        else:
            path.moveTo(cx - half * 0.45, cy - half)
            path.lineTo(cx + half * 0.55, cy)
            path.lineTo(cx - half * 0.45, cy + half)
        painter.drawPath(path)
        painter.restore()


def _install_application_style(app: QApplication) -> None:
    """Install our deterministic Fusion-derived style."""
    base = QStyleFactory.create("Fusion")
    app.setStyle(ElplanProxyStyle(base) if base is not None else ElplanProxyStyle())

def _apply_application_palette(app: QApplication, mode: str = "light") -> None:
    """Apply the resolved light/dark palette while preserving technical colors."""
    # Resolve System before swapping to Fusion, otherwise an older Qt build that
    # lacks colorScheme() would only see Fusion's default light palette.
    dark=_resolved_dark_mode(mode,app)
    _install_application_style(app)
    if sys.platform.startswith("win"):
        app.setFont(QFont("Segoe UI", 9))
    app.setProperty("elplanDarkMode",dark)
    p=QPalette()
    if dark:
        p.setColor(QPalette.ColorRole.Window,QColor("#171a1f")); p.setColor(QPalette.ColorRole.WindowText,QColor("#e5e9ef"))
        p.setColor(QPalette.ColorRole.Base,QColor("#1d2127")); p.setColor(QPalette.ColorRole.AlternateBase,QColor("#252a31"))
        p.setColor(QPalette.ColorRole.ToolTipBase,QColor("#25282d")); p.setColor(QPalette.ColorRole.ToolTipText,QColor("#e5e9ef"))
        p.setColor(QPalette.ColorRole.Text,QColor("#e5e9ef")); p.setColor(QPalette.ColorRole.PlaceholderText,QColor("#7f8a98"))
        p.setColor(QPalette.ColorRole.Link,QColor("#7fb4eb")); p.setColor(QPalette.ColorRole.LinkVisited,QColor("#a8a0df"))
        p.setColor(QPalette.ColorRole.Button,QColor("#252a31")); p.setColor(QPalette.ColorRole.ButtonText,QColor("#e5e9ef")); p.setColor(QPalette.ColorRole.BrightText,QColor("#ffffff"))
        p.setColor(QPalette.ColorRole.Highlight,QColor("#31577d")); p.setColor(QPalette.ColorRole.HighlightedText,QColor("#f4f8fc"))
        disabled=QColor("#68727f")
    else:
        p.setColor(QPalette.ColorRole.Window,QColor("#f3f5f7")); p.setColor(QPalette.ColorRole.WindowText,QColor("#202124"))
        p.setColor(QPalette.ColorRole.Base,QColor("#ffffff")); p.setColor(QPalette.ColorRole.AlternateBase,QColor("#f3f5f7"))
        p.setColor(QPalette.ColorRole.ToolTipBase,QColor("#fffbe8")); p.setColor(QPalette.ColorRole.ToolTipText,QColor("#202124"))
        p.setColor(QPalette.ColorRole.Text,QColor("#202124")); p.setColor(QPalette.ColorRole.PlaceholderText,QColor("#8a949f"))
        p.setColor(QPalette.ColorRole.Link,QColor("#2f6fac")); p.setColor(QPalette.ColorRole.LinkVisited,QColor("#5a5e9a"))
        p.setColor(QPalette.ColorRole.Button,QColor("#e9edf2")); p.setColor(QPalette.ColorRole.ButtonText,QColor("#202124")); p.setColor(QPalette.ColorRole.BrightText,QColor("#ffffff"))
        p.setColor(QPalette.ColorRole.Highlight,QColor("#cfe0fa")); p.setColor(QPalette.ColorRole.HighlightedText,QColor("#202124"))
        disabled=QColor("#8b929c")
    for role in (QPalette.ColorRole.WindowText,QPalette.ColorRole.Text,QPalette.ColorRole.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled,role,disabled)
    app.setPalette(p)


