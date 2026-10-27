from pathlib import Path


def _qt_articles_source():
    return (Path(__file__).resolve().parents[1] / "qt_articles.py").read_text(encoding="utf-8")


def test_bom_tab_has_distinct_current_view_total_label():
    src = _qt_articles_source()
    assert 'self.bom_total_label=QLabel(f"Summeret pris {price_display.vat_caption(self.price_vat_mode)} (aktuel visning): —")' in src
    assert 'root.addLayout(total_row)' in src


def test_bom_total_uses_current_rows_and_warns_about_missing_prices():
    src = _qt_articles_source()
    assert 'totals_by_currency=defaultdict(float); priced_lines=0' in src
    assert 'len(rows)-priced_lines' in src
    assert 'viste linjer mangler pris' in src
    assert 'self.bom_total_label.setText(f"Summeret pris {vat_caption} (aktuel visning): {price_text}{coverage}")' in src
    assert 'price_display.to_display_amount(value,getattr(self,"price_vat_mode","excl"))' in src
