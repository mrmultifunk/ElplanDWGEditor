import json
from pathlib import Path

from elplan_catalog import article_exchange


def test_import_guide_schema_has_one_required_key_and_unique_fields():
    rows=article_exchange.ARTICLE_FIELD_GUIDE
    keys=[r[0] for r in rows]
    assert keys[0]=='article_no'
    assert len(keys)==len(set(keys))
    required=[r[0] for r in rows if r[2]=='Påkrævet']
    assert required==['article_no']
    assert {'description','manufacturer','ean','el_no','image_url','datasheet_url','cable_spec'} <= set(keys)


def test_generated_json_template_roundtrips(tmp_path):
    path=tmp_path/'template.json'
    article_exchange.save_article_template_json(path,app_version='0.45.5')
    raw=json.loads(path.read_text(encoding='utf-8'))
    assert raw['format']==article_exchange.FORMAT_NAME
    assert raw['application_version']=='0.45.5'
    bundle=article_exchange.load_article_library(path)
    assert len(bundle.articles)==1
    art=bundle.articles[0]
    assert art['article_no']=='ABC-123'
    assert art['description']
    assert art['ean']=='5703302157070'
    assert art['image_url'].startswith('https://')


def test_generated_csv_template_uses_documented_headers_and_roundtrips(tmp_path):
    path=tmp_path/'template.csv'
    article_exchange.save_article_template_csv(path)
    text=path.read_text(encoding='utf-8-sig')
    header=text.splitlines()[0]
    assert 'Artikelnummer' in header
    assert 'Montagetype' in header
    assert 'Billedkilde' in header
    assert 'Pakkelængde [m]' in header
    bundle=article_exchange.load_article_library(path)
    assert len(bundle.articles)==1
    art=bundle.articles[0]
    assert art['article_no']=='ABC-123'
    assert art['mounting_type']=='Forfradåse'
    assert art['package_length_m']==100.0
    assert art['image_source']=='Producent'


def test_qt_article_database_exposes_import_guide_and_template_buttons():
    src=(Path(__file__).resolve().parents[1] / 'elplan_qt/qt_articles.py').read_text(encoding='utf-8')
    build=src[src.index('    def _build_library_tab'):src.index('    def _sync_lk_catalog',src.index('    def _build_library_tab'))]
    assert 'Importguide…' in build
    assert 'self._show_article_import_guide' in build
    dialog=src[src.index('class ArticleImportGuideDialog'):src.index('class ArticleEditDialog')]
    assert 'Gem JSON-template…' in dialog
    assert 'Gem CSV-template…' in dialog
    assert 'ARTICLE_FIELD_GUIDE' in dialog
    assert 'article_template_record' in dialog
