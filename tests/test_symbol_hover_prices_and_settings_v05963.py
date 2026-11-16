from pathlib import Path
from types import SimpleNamespace

from hover_bom import build_hover_bom_html, build_hover_bom_model


ROOT=Path(__file__).resolve().parents[1]


def _placement():
    return SimpleNamespace(pl_box_splices=[], associations=[])


def test_direct_article_hover_shows_unit_line_and_vat_aware_symbol_total():
    lookup={
        "A1":{"article_no":"A1", "description":"Dobbelt stikkontakt", "effective_price":10, "price_currency":"DKK", "price_unit":"stk"},
    }
    common=dict(
        symbol="socket", placement_uid="p1", placement=_placement(), article_lookup=lookup,
        article_bindings={"p1":{"symbol":[{"article_no":"A1", "qty":2}]}},
        assembly_bindings={}, assemblies=[],
    )
    net=build_hover_bom_html(vat_mode="excl", **common)
    gross=build_hover_bom_html(vat_mode="incl", **common)
    assert "10,00 DKK/stk" in net
    assert "20,00 DKK i alt" in net
    assert "Symboltotal ekskl. moms:</b> 20,00 DKK" in net
    assert "12,50 DKK/stk" in gross
    assert "Symboltotal inkl. moms:</b> 25,00 DKK" in gross


def test_bound_assembly_replaces_direct_rows_and_uses_only_active_components():
    lookup={
        "DIRECT":{"article_no":"DIRECT", "effective_price":999, "price_currency":"DKK"},
        "FRAME":{"article_no":"FRAME", "description":"Ramme", "effective_price":20, "price_currency":"DKK"},
        "OPTION":{"article_no":"OPTION", "effective_price":50, "price_currency":"DKK"},
    }
    assemblies=[{
        "id":"asm", "name":"Komplet montage", "items":[
            {"article_no":"FRAME", "qty":2},
            {"article_no":"OPTION", "qty":1, "optional":True, "included":False},
        ],
    }]
    common=dict(
        symbol="socket", placement_uid="p1", placement=_placement(), article_lookup=lookup,
        article_bindings={"p1":{"symbol":[{"article_no":"DIRECT", "qty":1}]}},
        assembly_bindings={"p1":{"symbol":"asm"}}, assemblies=assemblies,
    )
    model=build_hover_bom_model(**common)
    html=build_hover_bom_html(vat_mode="excl", **common)
    assert [item["article_no"] for item in model["sections"][0]["items"]] == ["FRAME"]
    assert model["totals_by_currency"] == {"DKK":40.0}
    assert "Komplet montage" in html and "styklistepris ekskl. moms: <b>40,00 DKK" in html
    assert "DIRECT" not in html and "OPTION" not in html


def test_hover_totals_keep_currencies_separate_and_report_missing_price():
    lookup={
        "DK":{"article_no":"DK", "effective_price":8, "price_currency":"DKK"},
        "EU":{"article_no":"EU", "effective_price":3, "price_currency":"EUR"},
        "MISS":{"article_no":"MISS", "description":"Pris afventer"},
    }
    html=build_hover_bom_html(
        symbol="socket", placement_uid="p1", placement=_placement(), article_lookup=lookup,
        article_bindings={"p1":{"symbol":[
            {"article_no":"DK", "qty":1}, {"article_no":"EU", "qty":2}, {"article_no":"MISS", "qty":1},
        ]}},
        assembly_bindings={}, assemblies=[], vat_mode="excl",
    )
    assert "8,00 DKK" in html and "6,00 EUR" in html
    assert "pris mangler" in html
    assert "pris på 2/3 artikelrækker" in html


def test_shared_settings_panel_and_hover_cache_are_wired_to_one_global_vat_key():
    app=(ROOT/"qt_app.py").read_text(encoding="utf-8")
    hover=(ROOT/"qt_hover.py").read_text(encoding="utf-8")
    settings=(ROOT/"qt_settings.py").read_text(encoding="utf-8")
    articles=(ROOT/"qt_articles.py").read_text(encoding="utf-8")
    assert "ApplicationSettingsMixin" in app
    assert 'QAction("Indstillinger…"' in app
    assert 'tools_menu.addAction(self.act_settings)' in app
    for category in ("Visning", "Priser og BOM", "Lager og synkronisering"):
        assert category in settings
    assert '"price_vat_mode"' in settings and '"price_vat_mode"' in articles
    assert "user_library.apply_article_prices" in hover
    assert "_hover_price_lookup_signature" in hover
    assert "build_hover_bom_html" in hover
    assert len(app.splitlines()) <= 6980
