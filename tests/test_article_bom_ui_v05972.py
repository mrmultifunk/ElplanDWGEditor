from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


def test_version_and_article_bom_ui_contract():
    assert APP_VERSION == core.APP_VERSION == "0.59.84"
    source=Path(__file__).resolve().parents[1].joinpath("qt_articles.py").read_text(encoding="utf-8")
    assert "class ArticleUsageDialog" in source
    assert 'QPushButton("Hvor bruges?")' in source
    assert 'self.bom_view_tabs.addTab(quality_page,"Kontrol")' in source
    assert 'QPushButton("Vis komponentpanel")' in source
    assert "self.work_splitter=QSplitter" in source
    assert 'QAbstractItemView.SelectionMode.ExtendedSelection' in source
    for field in ("consumption_unit","sales_unit","sales_package_quantity","minimum_order_quantity","package_label"):
        assert field in source
