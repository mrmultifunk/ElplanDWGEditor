from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


def test_version_0597():
    assert APP_VERSION == core.APP_VERSION == "0.59.76"


def test_pl_entry_cards_prioritize_full_cable_marking():
    source = Path("qt_pl_box.py").read_text(encoding="utf-8")
    assert "def _draw_port_cable_label" in source
    assert "def _wrap_port_label" in source
    assert "QFontMetricsF" in source
    assert "display[:38]" not in source
    assert "body_w=min(690.0" in source
    assert "port_w=min(205.0 if exploded else 222.0" in source
    assert "port_h=80.0+14.0*t" in source


def test_pl_display_contains_user_extra_marking():
    class Cable:
        cable_id = "K17"
        circuit_id = "G11"
        label = "UDTAG-GANG-SPEJL"

    assert core.cable_pl_display(Cable()) == "K17 · G11 · UDTAG-GANG-SPEJL"
