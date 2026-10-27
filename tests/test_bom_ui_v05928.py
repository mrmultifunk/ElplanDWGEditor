from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SRC=(ROOT/'qt_articles.py').read_text(encoding='utf-8')
XLSX=(ROOT/'bom_xlsx_export.py').read_text(encoding='utf-8')


def test_bom_has_article_assembly_and_source_views():
    assert '"Styklister"' in SRC
    assert '"Kilder"' in SRC
    assert 'self.bom_group_by' in SRC
    assert 'self.bom_quick_filter' in SRC
    assert 'self.bom_show_cables' in SRC
    assert 'Hvor kommer linjen fra?' in SRC


def test_bom_article_table_exposes_source_or_assembly_column():
    assert '"Kilde / stykliste"' in SRC
    assert '("Kilde / stykliste", "source_summary", "text")' in XLSX
