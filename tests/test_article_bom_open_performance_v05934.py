from pathlib import Path

import core_logic as core
from elplan_catalog import user_library


def test_fast_price_overlay_matches_safe_overlay_for_normalized_rows():
    rows = core.normalize_article_catalog([
        {
            "article_no": "A1", "description": "Test artikel", "manufacturer": "Test", "unit": "stk",
            "estimated_price": 12.0, "estimated_price_source": "Katalog",
        },
        {"article_no": "A2", "description": "Anden artikel", "manufacturer": "Test", "unit": "stk"},
    ])
    prices = user_library.normalize_article_prices({
        "A1": {"manual_price": 9.5, "manual_price_source": "Manuel", "price_currency": "DKK", "price_unit": "stk"},
        "A2": {"estimated_price": 4.0, "estimated_price_source": "Web", "price_currency": "DKK", "price_unit": "stk"},
    })
    safe = user_library.apply_article_prices(rows, prices)
    fast = user_library.apply_article_prices(rows, prices, assume_normalized=True, prices_normalized=True)
    for idx in range(2):
        for key in ("article_no","description","manufacturer","unit","estimated_price","manual_price","effective_price","unit_price","price_kind","price_status","price_source","price_currency","price_unit"):
            assert fast[idx].get(key) == safe[idx].get(key)
    assert fast[0]["unit_price"] == 9.5
    assert fast[1]["unit_price"] == 4.0


def test_bom_dialog_open_path_avoids_redundant_full_catalog_work():
    source = Path("elplan_qt/qt_articles.py").read_text(encoding="utf-8")
    block = source[source.index("class BomManagerDialog"):]
    assert "self._refresh_all(normalize_state=False)" in block
    assert "assume_normalized=True,prices_normalized=True" in block
    assert "build_article_search_index(self._available_catalog())" in block
    assert "self.tabs.currentChanged.connect(self._top_level_tab_changed)" in block
    refresh = block[block.index("    def _refresh_all"):block.index("    def _library_enriched_rows")]
    assert "_run_article_quality_audit()" not in refresh
    bom = block[block.index("    def _refresh_bom(self"):block.index("    def _bom_export_filename")]
    assert "total_unfiltered=len(rows)" in bom
    assert "self._bom_data(selected_room)[0]" not in bom


def test_stykliste_naming_can_reuse_article_lookup_mapping():
    from elplan_catalog import assembly_naming

    lookup = {
        "X1": {"article_no": "X1", "description": "LK FUGA SLIM stikkontakt koksgrå"},
    }
    record = {"name": "", "items": [{"article_no": "X1", "qty": 1}]}
    fields = assembly_naming.infer_assembly_name_fields(record, lookup)
    assert fields["product_type"] == "Stikkontakt"
    assert fields["system_series"] == "LK FUGA SLIM"
    assert fields["color"] == "Koksgrå"
