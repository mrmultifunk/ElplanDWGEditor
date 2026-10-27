from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


def test_version_05925():
    assert APP_VERSION == core.APP_VERSION == "0.59.73"


def test_price_scope_dialog_uses_responsive_grid_instead_of_messagebox_button_row():
    source = (Path(__file__).parents[1] / "qt_articles.py").read_text(encoding="utf-8")
    assert "class _RetailPriceScopeDialog(QDialog):" in source
    assert 'add_choice("Kun artikler i BOM", "bom", 0, 0, True)' in source
    assert 'add_choice("Kun uden pris", "missing", 0, 1)' in source
    assert 'add_choice("Forældede > 7 dage", "stale", 1, 0)' in source
    assert 'add_choice("Alle artikler", "all", 1, 1)' in source
    assert "button.setMinimumWidth(230)" in source
    assert "scope_dialog=_RetailPriceScopeDialog(self)" in source
    assert 'box.addButton("Kun artikler i BOM"' not in source
