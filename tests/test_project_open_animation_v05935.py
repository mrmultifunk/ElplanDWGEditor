from pathlib import Path

from project_model import APP_VERSION
import core_logic as core

ROOT = Path(__file__).resolve().parents[1]


def test_version_05935():
    assert APP_VERSION == core.APP_VERSION == "0.59.74"


def test_project_open_overlay_has_polished_animation_and_real_stages():
    feedback = (ROOT / "qt_feedback.py").read_text(encoding="utf-8")
    opening = (ROOT / "qt_project_open.py").read_text(encoding="utf-8")
    theme = (ROOT / "qt_theme.py").read_text(encoding="utf-8")
    assert "class ProjectLoadIndicator" in feedback
    assert "class LoadStageIndicator" in feedback
    assert "QPropertyAnimation" in feedback
    assert '("Projektdata", "Tegning", "Arbejdsflade")' in feedback
    assert 'self.title.setText("Projekt klar"' in feedback
    assert "self._hide_timer.start(360)" in feedback
    assert 'self._update_busy("Gør arbejdsfladen klar…")' in opening
    assert "self._end_busy(success=True" in opening
    assert "QLabel#busyEyebrow" in theme


def test_animation_does_not_fake_percentage_progress_during_loading():
    feedback = (ROOT / "qt_feedback.py").read_text(encoding="utf-8")
    assert "self.progress.setRange(0, 0)" in feedback
    assert "fake percentage progress" in feedback
