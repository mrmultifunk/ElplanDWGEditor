from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


def test_version_05014():
    assert APP_VERSION == core.APP_VERSION == "0.59.77"


def test_distribution_root_is_organized():
    root=Path(__file__).resolve().parents[1]
    assert (root / "tests").is_dir()
    assert (root / "docs" / "history").is_dir()
    assert (root / "docs" / "reference").is_dir()
    assert (root / "examples").is_dir()
    assert not list(root.glob("test_*.py"))
    assert len(list(root.glob("*.md"))) <= 4


def test_hover_cards_have_visual_preview_and_detailed_bom():
    root=Path(__file__).resolve().parents[1]
    source=(root / "qt_app.py").read_text(encoding="utf-8")
    hover=(root / "qt_hover.py").read_text(encoding="utf-8")
    hover_bom=(root / "hover_bom.py").read_text(encoding="utf-8")
    assert "class _HoverPreviewWidget" in hover
    assert 'self._mode=="pl"' in hover
    assert 'self._mode=="symbol"' in hover
    assert 'self._mode=="cable"' in hover
    assert "def _placement_hover_bom_html" in hover
    assert "Stykliste:" in hover_bom
    assert "core.bom_assembly_effective_items" in hover_bom
