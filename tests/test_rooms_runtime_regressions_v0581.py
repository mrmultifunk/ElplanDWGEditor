from pathlib import Path


def test_room_dialogs_use_keyword_only_modern_dialog_api():
    src = Path("qt_rooms.py").read_text(encoding="utf-8")
    assert "configure_modern_dialog(self, title='Rum', size=(" in src
    assert "configure_modern_dialog(self, title='Mærk kabler efter rum', size=(760,540))" in src
    assert "configure_modern_dialog(self, title='Rum', size=(620,520))" in src
    assert "configure_modern_dialog(self,'Rum',520,260)" not in src


def test_toast_does_not_disconnect_finished_signal_dynamically():
    src = Path("qt_feedback.py").read_text(encoding="utf-8")
    assert "_fade.finished.connect(self._on_fade_finished)" in src
    assert "_fade.finished.disconnect" not in src
    assert "_fade_hides_on_finish" in src
