from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


def test_wago_selector_polish_has_series_tabs_preview_and_capacity_guidance():
    assert APP_VERSION == core.APP_VERSION == "0.59.78"
    source=(Path(__file__).resolve().parents[1]/"qt_pl_box.py").read_text(encoding="utf-8")
    for token in (
        '221 · universel med vippepal',
        '2273 / P100 · PUSH WIRE',
        'Wago-type',
        'Vælg anbefalet',
        'Ingen artikel / ryd valg',
        'Kapacitet:',
        'Behov:',
        'PUSH WIRE: kun massive/entrådede ledere.',
        'image_local_path',
    ):
        assert token in source
    assert 'QTabWidget' in source
    assert 'article_combo=QComboBox()' not in source


def test_pl_wago_catalog_exposes_both_series_but_keeps_221_default_recommendation():
    for article_no,ports in {
        '221-412':2,'221-413':3,'221-415':5,'221-420':10,
        '2273-202':2,'2273-203':3,'2273-204':4,'2273-205':5,'2273-208':8,
    }.items():
        assert core.pl_wago_article_capacity(article_no) == ports
    assert core.pl_recommended_wago_article(3, True) == '221-415'
