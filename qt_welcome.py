from __future__ import annotations

"""Welcome/start page for projects and recent files."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class WelcomePage(QWidget):
    def __init__(self, parent, *, open_project, open_cad, open_recent, show_canvas):
        super().__init__(parent)
        self.setObjectName("welcomePage")
        self._open_recent = open_recent
        self._show_canvas = show_canvas

        shell = QVBoxLayout(self)
        shell.setContentsMargins(34, 30, 34, 30)
        shell.setSpacing(18)

        eyebrow = QLabel("ELPLAN DWG EDITOR", self)
        eyebrow.setObjectName("welcomeEyebrow")
        shell.addWidget(eyebrow)
        title = QLabel("Elektrisk plantegning, uden unødig støj", self)
        title.setObjectName("welcomeTitle")
        title.setWordWrap(True)
        shell.addWidget(title)
        subtitle = QLabel("Åbn et eksisterende projekt eller start direkte fra en DWG/DXF. Dine seneste projekter ligger klar nedenfor.", self)
        subtitle.setObjectName("welcomeSubtitle")
        subtitle.setWordWrap(True)
        shell.addWidget(subtitle)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        open_btn = QPushButton("Åbn projekt…", self)
        open_btn.setObjectName("primaryButton")
        open_btn.clicked.connect(open_project)
        actions.addWidget(open_btn)
        cad_btn = QPushButton("Nyt fra DWG/DXF…", self)
        cad_btn.clicked.connect(open_cad)
        actions.addWidget(cad_btn)
        self.back_btn = QPushButton("Tilbage til tegning", self)
        self.back_btn.setObjectName("quietButton")
        self.back_btn.clicked.connect(show_canvas)
        self.back_btn.hide()
        actions.addWidget(self.back_btn)
        actions.addStretch(1)
        shell.addLayout(actions)

        recent_title = QLabel("Seneste projekter", self)
        recent_title.setObjectName("sectionTitle")
        shell.addWidget(recent_title)

        frame = QFrame(self)
        frame.setObjectName("welcomeCard")
        self.recent_layout = QVBoxLayout(frame)
        self.recent_layout.setContentsMargins(10, 10, 10, 10)
        self.recent_layout.setSpacing(4)
        shell.addWidget(frame)
        shell.addStretch(1)

        hint = QLabel("Tip: Ctrl+F søger i tegningen · Ctrl+Shift+P åbner kommando-paletten", self)
        hint.setObjectName("welcomeHint")
        shell.addWidget(hint)

    def set_has_project(self, value: bool) -> None:
        self.back_btn.setVisible(bool(value))

    def set_recent(self, paths: list[str]) -> None:
        while self.recent_layout.count():
            item = self.recent_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not paths:
            empty = QLabel("Ingen seneste projekter endnu.", self)
            empty.setObjectName("sectionHint")
            self.recent_layout.addWidget(empty)
            return
        for path_value in paths[:6]:
            path = Path(path_value)
            name = path.name[:-len(".elplan.json")] if path.name.lower().endswith(".elplan.json") else path.stem
            button = QPushButton(name, self)
            button.setObjectName("recentProjectButton")
            button.setToolTip(str(path))
            parent = path.parent.name or str(path.parent)
            button.setText(f"{name}\n{parent}")
            button.clicked.connect(lambda _checked=False, p=str(path): self._open_recent(p))
            self.recent_layout.addWidget(button)


class WelcomeUiMixin:
    def _create_central_pages(self) -> None:
        canvas = self.takeCentralWidget() or self.view
        self.central_stack = QStackedWidget(self)
        self.welcome_page = WelcomePage(
            self,
            open_project=self.open_project,
            open_cad=self.open_cad,
            open_recent=self.open_recent_project,
            show_canvas=self._show_canvas_page,
        )
        self.central_stack.addWidget(self.welcome_page)
        self.central_stack.addWidget(canvas)
        self.setCentralWidget(self.central_stack)
        self._refresh_welcome_page()
        self._show_welcome_page()

    def _refresh_welcome_page(self) -> None:
        if not hasattr(self, "welcome_page"):
            return
        paths = self._recent_project_paths(True) if hasattr(self, "_recent_project_paths") else []
        self.welcome_page.set_recent(paths)
        self.welcome_page.set_has_project(bool(getattr(self, "doc", None)))

    def _show_welcome_page(self) -> None:
        if hasattr(self, "central_stack") and hasattr(self, "welcome_page"):
            self._refresh_welcome_page()
            self.central_stack.setCurrentWidget(self.welcome_page)
            if hasattr(self, "context_caption"):
                self.context_caption.setText("Startside")

    def _show_canvas_page(self) -> None:
        if hasattr(self, "central_stack") and hasattr(self, "view"):
            self.central_stack.setCurrentWidget(self.view)
            if hasattr(self, "_refresh_context_toolbar"):
                self._refresh_context_toolbar()
