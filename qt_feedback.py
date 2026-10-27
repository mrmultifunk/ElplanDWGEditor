from __future__ import annotations

"""Non-modal feedback and polished full-window project loading feedback."""

from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QPropertyAnimation, QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


class ToastOverlay(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("toastOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        self.icon = QLabel("✓", self)
        self.icon.setObjectName("toastIcon")
        self.label = QLabel("", self)
        self.label.setObjectName("toastText")
        self.label.setWordWrap(True)
        layout.addWidget(self.icon)
        layout.addWidget(self.label, 1)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._animate_out)
        self._opacity=QGraphicsOpacityEffect(self); self.setGraphicsEffect(self._opacity)
        self._fade=QPropertyAnimation(self._opacity,b"opacity",self); self._fade.setDuration(150); self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_hides_on_finish = False
        self._fade.finished.connect(self._on_fade_finished)
        self._slide=QPropertyAnimation(self,b"pos",self); self._slide.setDuration(150); self._slide.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.hide()

    def _on_fade_finished(self) -> None:
        if self._fade_hides_on_finish:
            self._fade_hides_on_finish = False
            self.hide()

    def _animate_out(self) -> None:
        self._fade.stop(); self._fade_hides_on_finish = True
        self._fade.setDuration(130); self._fade.setStartValue(float(self._opacity.opacity())); self._fade.setEndValue(0.0)
        self._fade.start()

    def show_message(self, text: str, *, kind: str = "success", timeout: int = 2200) -> None:
        kind = kind if kind in {"success", "info", "warning"} else "info"
        self.setProperty("kind", kind)
        self.icon.setText({"success": "✓", "info": "i", "warning": "!"}[kind])
        self.label.setText(str(text))
        self.style().unpolish(self)
        self.style().polish(self)
        self.adjustSize()
        parent = self.parentWidget()
        if parent is not None:
            max_w = min(520, max(280, parent.width() - 80))
            self.setMaximumWidth(max_w)
            self.adjustSize()
            x = max(20, (parent.width() - self.width()) // 2)
            y = max(20, parent.height() - self.height() - 64)
            self.move(x, y)
        final_pos=self.pos()
        self.raise_(); self.show()
        self._fade.stop(); self._slide.stop(); self._fade_hides_on_finish = False
        self._opacity.setOpacity(0.18)
        self.move(final_pos+QPoint(0,8))
        self._fade.setDuration(150); self._fade.setStartValue(0.18); self._fade.setEndValue(1.0)
        self._slide.setStartValue(self.pos()); self._slide.setEndValue(final_pos)
        self._fade.start(); self._slide.start()
        self.timer.start(max(700, int(timeout)))


class ProjectLoadIndicator(QWidget):
    """Small blueprint-inspired animated indicator for project/CAD loading."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("projectLoadIndicator")
        self.setFixedSize(76, 76)
        self._angle = 0.0
        self._success = False
        self._timer = QTimer(self)
        self._timer.setInterval(32)
        self._timer.timeout.connect(self._tick)

    def _tick(self) -> None:
        self._angle = (self._angle + 7.0) % 360.0
        self.update()

    def start(self) -> None:
        self._success = False
        self._angle = 0.0
        if not self._timer.isActive():
            self._timer.start()
        self.update()

    def success(self) -> None:
        self._success = True
        self._timer.stop()
        self.update()

    def stop(self) -> None:
        self._timer.stop()

    def _accent(self) -> QColor:
        color = self.palette().color(QPalette.ColorRole.Highlight)
        return color if color.isValid() else QColor("#4f8bc9")

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        accent = self._accent()
        muted = self.palette().color(QPalette.ColorRole.Mid)
        text = self.palette().color(QPalette.ColorRole.WindowText)
        center = self.rect().center()

        # Quiet halo so the animation reads clearly in both light and dark mode.
        halo = QColor(accent)
        halo.setAlpha(28 if not self._success else 38)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(center, 33, 33)

        arc_rect = QRectF(5.5, 5.5, 65.0, 65.0)
        if self._success:
            ring = QPen(accent, 3.0)
            ring.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(ring)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(arc_rect, 0, 360 * 16)
        else:
            base = QColor(muted); base.setAlpha(88)
            painter.setPen(QPen(base, 2.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawArc(arc_rect, 0, 360 * 16)
            sweep = QPen(accent, 3.2)
            sweep.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(sweep)
            painter.drawArc(arc_rect, int(-self._angle * 16), int(-112 * 16))

        if self._success:
            check = QPen(accent, 4.0)
            check.setCapStyle(Qt.PenCapStyle.RoundCap)
            check.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(check)
            painter.drawLine(25, 39, 34, 48)
            painter.drawLine(34, 48, 52, 28)
            return

        # Minimal floor-plan sheet: clear enough to read as an Elplan project,
        # without introducing image assets or theme-specific artwork.
        sheet = QColor(text); sheet.setAlpha(205)
        pen = QPen(sheet, 2.0)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(23, 20, 31, 37), 3.5, 3.5)
        detail = QColor(accent); detail.setAlpha(220)
        painter.setPen(QPen(detail, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(30, 28, 47, 28)
        painter.drawLine(30, 34, 39, 34)
        painter.drawLine(39, 34, 39, 47)
        painter.drawLine(39, 41, 48, 41)
        painter.drawLine(30, 48, 35, 48)


class LoadStageIndicator(QWidget):
    """Three-stage project opening track: project data -> drawing -> workspace."""

    LABELS = ("Projektdata", "Tegning", "Arbejdsflade")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("loadStageIndicator")
        self._stage = 0
        self._complete = False
        self.setMinimumHeight(42)
        self.setMaximumHeight(46)

    def set_stage(self, stage: int, *, complete: bool = False) -> None:
        self._stage = max(0, min(2, int(stage)))
        self._complete = bool(complete)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        accent = self.palette().color(QPalette.ColorRole.Highlight)
        muted = self.palette().color(QPalette.ColorRole.Mid)
        text = self.palette().color(QPalette.ColorRole.WindowText)
        w = max(1, self.width())
        left, right = 18.0, float(w - 18)
        step = (right - left) / 2.0
        xs = (left, left + step, right)
        y = 12.0

        line_muted = QColor(muted); line_muted.setAlpha(100)
        painter.setPen(QPen(line_muted, 2.0))
        painter.drawLine(int(xs[0]), int(y), int(xs[2]), int(y))

        done_to = 2 if self._complete else self._stage
        if done_to > 0:
            painter.setPen(QPen(accent, 2.4))
            painter.drawLine(int(xs[0]), int(y), int(xs[done_to]), int(y))

        font = painter.font(); font.setPointSizeF(max(7.5, font.pointSizeF() - 0.5)); painter.setFont(font)
        for idx, (x, label) in enumerate(zip(xs, self.LABELS)):
            done = self._complete or idx < self._stage
            active = (not self._complete and idx == self._stage)
            dot = QColor(accent) if (done or active) else QColor(muted)
            dot.setAlpha(255 if (done or active) else 145)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(dot)
            radius = 5.0 if active else 4.0
            painter.drawEllipse(QPoint(int(x), int(y)), int(radius), int(radius))
            label_color = QColor(text if (done or active) else muted)
            label_color.setAlpha(230 if (done or active) else 165)
            painter.setPen(label_color)
            rect = QRectF(x - 68, 22, 136, 18)
            painter.drawText(rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, label)


class BusyOverlay(QWidget):
    """Full-window project/CAD loading state with a short polished animation.

    Loading remains synchronous because scene construction manipulates Qt graphics
    objects.  The animation therefore deliberately acts as visual feedback rather
    than fake percentage progress; it advances whenever the loading workflow pumps
    Qt events between real stages.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("busyOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        if parent is not None:
            parent.installEventFilter(self)

        self._is_project_open = False
        self._hiding = False
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._fade_out)
        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self._fade = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.finished.connect(self._fade_finished)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.addStretch(1)

        row = QHBoxLayout()
        row.addStretch(1)
        self.card = QFrame(self)
        self.card.setObjectName("busyCard")
        self.card.setMinimumWidth(430)
        self.card.setMaximumWidth(620)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(24, 22, 24, 21)
        card_layout.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(16)
        self.indicator = ProjectLoadIndicator(self.card)
        top.addWidget(self.indicator, 0, Qt.AlignmentFlag.AlignTop)

        copy = QVBoxLayout()
        copy.setContentsMargins(0, 2, 0, 0)
        copy.setSpacing(4)
        self.eyebrow = QLabel("PROJEKT", self.card)
        self.eyebrow.setObjectName("busyEyebrow")
        self.title = QLabel("Åbner projekt…", self.card)
        self.title.setObjectName("busyTitle")
        self.detail = QLabel("", self.card)
        self.detail.setObjectName("busyDetail")
        self.detail.setWordWrap(True)
        copy.addWidget(self.eyebrow)
        copy.addWidget(self.title)
        copy.addWidget(self.detail)
        top.addLayout(copy, 1)
        card_layout.addLayout(top)

        self.stages = LoadStageIndicator(self.card)
        card_layout.addWidget(self.stages)
        self.progress = QProgressBar(self.card)
        self.progress.setObjectName("busyProgress")
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        card_layout.addWidget(self.progress)
        row.addWidget(self.card)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)
        self.hide()

    def eventFilter(self, watched, event):
        if watched is self.parentWidget() and event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            parent = self.parentWidget()
            if parent is not None:
                self.setGeometry(parent.rect())
        return super().eventFilter(watched, event)

    @staticmethod
    def _stage_for_detail(detail: str) -> int:
        text = str(detail or "").casefold()
        if any(token in text for token in ("arbejdsflade", "plantegning", "scene")):
            return 2
        if any(token in text for token in ("dwg", "dxf", "cad", "lag", "geometri", "tegning")):
            return 1
        return 0

    def show_busy(self, title: str, detail: str = "") -> None:
        self._hide_timer.stop()
        self._fade.stop()
        self._hiding = False
        title_text = str(title or "Arbejder…")
        self._is_project_open = "projekt" in title_text.casefold()
        self.eyebrow.setText("PROJEKT" if self._is_project_open else "TEGNING")
        self.title.setText(title_text)
        self.detail.setText(str(detail or ""))
        self.stages.set_stage(self._stage_for_detail(detail))
        self.progress.setRange(0, 0)
        self.indicator.start()
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())
        self.raise_()
        self._opacity.setOpacity(0.0)
        self.show()
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self._fade.setDuration(180)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)
        self._fade.start()

    def set_detail(self, detail: str) -> None:
        text = str(detail or "")
        self.detail.setText(text)
        self.stages.set_stage(self._stage_for_detail(text))

    def hide_busy(self, *, success: bool = False, detail: str = "") -> None:
        if not self.isVisible():
            return
        self._hide_timer.stop()
        if success:
            self.indicator.success()
            self.stages.set_stage(2, complete=True)
            self.progress.setRange(0, 100)
            self.progress.setValue(100)
            self.title.setText("Projekt klar" if self._is_project_open else "Tegning klar")
            self.detail.setText(str(detail or "Klar til at arbejde."))
            # Keep the success state just long enough to register; no blocking wait.
            self._hide_timer.start(360)
        else:
            self.indicator.stop()
            self._fade_out()

    def _fade_out(self) -> None:
        if not self.isVisible():
            return
        self._fade.stop()
        self._hiding = True
        self._fade.setDuration(220)
        self._fade.setStartValue(float(self._opacity.opacity()))
        self._fade.setEndValue(0.0)
        self._fade.start()

    def _fade_finished(self) -> None:
        if self._hiding:
            self._hiding = False
            self.indicator.stop()
            self.hide()
            self._opacity.setOpacity(1.0)
