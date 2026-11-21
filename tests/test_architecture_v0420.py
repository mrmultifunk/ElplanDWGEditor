from pathlib import Path

from elplan_catalog.article_index import build_article_search_index
from elplan_shared.storage_utils import atomic_write_json, read_json


def test_active_qt_code_uses_split_core_not_legacy_frontend():
    qt = Path("elplan_qt/qt_app.py").read_text(encoding="utf-8")
    graphics = Path("elplan_qt/qt_graphics.py").read_text(encoding="utf-8")
    model = Path("elplan_project/project_model.py").read_text(encoding="utf-8")
    assert "import core_logic as core" in qt
    assert "import core_logic as core" in graphics
    assert "import core_logic as core" in model
    assert "import legacy_core as core" not in qt + graphics + model


def test_legacy_core_is_lazy_compatibility_layer():
    legacy = Path("legacy_core.py").read_text(encoding="utf-8")
    assert "from elplan_legacy.legacy_tk_app import ElplanEditor" in legacy
    assert "def __getattr__" in legacy
    assert len(legacy.splitlines()) < 100


def test_article_search_index_precomputes_facets_and_text():
    rows = build_article_search_index([
        {"article_no": "501D0412", "description": "FUGA afdækning", "manufacturer": "LK", "ean": "123"},
        {"article_no": "K1", "description": "Kabel", "kind": "cable"},
    ], include_cables=False)
    assert len(rows) == 1
    assert rows[0]["article_no"] == "501D0412"
    assert "501d0412" in rows[0]["_search_blob"]
    assert "fuga afdækning" in rows[0]["_search_blob"]


def test_shared_atomic_json_storage(tmp_path):
    target = tmp_path / "nested" / "data.json"
    atomic_write_json(target, {"value": 7})
    assert read_json(target, None) == {"value": 7}
    target.write_text("not json", encoding="utf-8")
    assert read_json(target, {"fallback": True}) == {"fallback": True}


def test_bom_catalog_is_cached_between_refresh_consumers():
    source = Path("elplan_qt/qt_articles.py").read_text(encoding="utf-8")
    assert "self._catalog_cache=None" in source
    assert "def _invalidate_catalog_cache(self):" in source
    assert "if self._catalog_cache is None:" in source
    assert "if self._catalog_lookup_cache is None:" in source
