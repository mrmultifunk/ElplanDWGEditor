from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import core_logic as core
from elplan_core.bom import articles, assemblies, build, procurement, scope


def test_bom_modules_are_reexported_through_core_facade():
    for module, names in (
        (articles, ("article_packaging", "normalize_article_catalog", "load_predefined_article_catalog")),
        (assemblies, ("normalize_bom_assemblies", "bom_assembly_usage", "normalize_symbol_article_bindings")),
        (build, ("build_bom", "bom_source_breakdown", "project_control_issues")),
        (procurement, ("placement_procurement_context", "bom_purchase_segment_key")),
        (scope, ("placement_bom_room_uids", "placement_matches_bom_room")),
    ):
        for name in names:
            assert getattr(core, name) is getattr(module, name)


def test_bundled_catalog_reads_repo_json_once_and_returns_fresh_rows():
    target = Path(__file__).resolve().parents[1] / "predefined_articles.json"
    cache = articles._predefined_article_catalog_cached
    cache.cache_clear()
    try:
        with patch.object(Path, "read_text", autospec=True) as read:
            read.return_value = '{"articles": [{"article_no": "test-json", "description": "Testartikel"}]}'
            rows = articles.load_predefined_article_catalog()
            assert rows[0]["article_no"] == "test-json"
            rows[0]["description"] = "Lokal ændring"
            assert core.load_predefined_article_catalog()[0]["description"] == "Testartikel"
        read.assert_called_once_with(target, encoding="utf-8")
        assert core._predefined_article_catalog_cached is cache
    finally:
        cache.cache_clear()


def test_bundled_catalog_uses_python_fallback_without_json():
    from predefined_articles_data import ARTICLES

    cache = articles._predefined_article_catalog_cached
    cache.cache_clear()
    try:
        with patch.object(Path, "read_text", autospec=True, side_effect=FileNotFoundError):
            rows = articles.load_predefined_article_catalog()
        assert rows
        assert rows == articles.normalize_article_catalog(ARTICLES)
    finally:
        cache.cache_clear()
