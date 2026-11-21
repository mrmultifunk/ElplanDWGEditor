import json
from pathlib import Path

from elplan_catalog import article_exchange


def test_json_roundtrip_preserves_article_metadata(tmp_path):
    rows=[{
        "article_no":"ABC-123","description":"Test artikel","manufacturer":"TestCo",
        "ean":"5700000000000","image_url":"https://example.test/image.jpg",
        "datasheet_url":"https://example.test/data.pdf","product_type":"Afbryder / betjening",
    }]
    path=tmp_path/"library.json"
    article_exchange.save_article_library_json(path,rows,app_version="0.45.4")
    raw=json.loads(path.read_text(encoding="utf-8"))
    assert raw["format"]==article_exchange.FORMAT_NAME
    assert raw["application_version"]=="0.45.4"
    bundle=article_exchange.load_article_library(path)
    assert bundle.source_format=="JSON"
    assert bundle.articles[0]["article_no"]=="ABC-123"
    assert bundle.articles[0]["image_url"].endswith("image.jpg")
    assert bundle.articles[0]["datasheet_url"].endswith("data.pdf")


def test_csv_import_accepts_danish_headers_and_semicolon(tmp_path):
    path=tmp_path/"library.csv"
    path.write_text(
        "Artikelnummer;Beskrivelse;Fabrikat;EAN;Billede\n"
        "A1;Min artikel;Firma;1234567890123;https://example.test/a1.jpg\n",
        encoding="utf-8-sig",
    )
    bundle=article_exchange.load_article_library(path)
    assert len(bundle.articles)==1
    art=bundle.articles[0]
    assert art["article_no"]=="A1"
    assert art["description"]=="Min artikel"
    assert art["manufacturer"]=="Firma"
    assert art["ean"]=="1234567890123"
    assert art["image_url"].endswith("a1.jpg")


def test_safe_merge_only_fills_missing_fields():
    current=[{"article_no":"A1","description":"Lokalt navn","manufacturer":"","ean":"111"}]
    incoming=[{"article_no":"A1","description":"Import navn","manufacturer":"Firma","ean":"222"},
              {"article_no":"A2","description":"Ny"}]
    merged,stats=article_exchange.merge_article_catalog(current,incoming,mode="fill_missing")
    lookup={r["article_no"]:r for r in merged}
    assert lookup["A1"]["description"]=="Lokalt navn"
    assert lookup["A1"]["manufacturer"]=="Firma"
    assert lookup["A1"]["ean"]=="111"
    assert lookup["A2"]["description"]=="Ny"
    assert stats["added"]==1 and stats["updated"]==1


def test_overwrite_merge_replaces_nonempty_imported_fields():
    current=[{"article_no":"A1","description":"Gammel","manufacturer":"Firma A","ean":"111"}]
    incoming=[{"article_no":"a1","description":"Ny","manufacturer":"","ean":"222"}]
    merged,stats=article_exchange.merge_article_catalog(current,incoming,mode="overwrite")
    art=merged[0]
    assert art["article_no"]=="A1"  # stable existing key spelling
    assert art["description"]=="Ny"
    assert art["manufacturer"]=="Firma A"  # blank import never erases data
    assert art["ean"]=="222"
    assert stats["updated"]==1


def test_qt_source_uses_one_article_database_tab():
    src=(Path(__file__).resolve().parents[1] / "elplan_qt/qt_articles.py").read_text(encoding="utf-8")
    init=src[src.index("class BomManagerDialog"):src.index("    # ---- faner",src.index("class BomManagerDialog"))]
    assert "self._build_library_tab()" in init
    assert "self._build_predefined_tab()" not in init
    build=src[src.index("    def _build_library_tab"):src.index("    def _sync_lk_catalog",src.index("    def _build_library_tab"))]
    assert 'self.tabs.addTab(tab,"Artikeldatabase")' in build
    assert "ArticleVisualPreview" in build
    assert "Importér bibliotek…" in build
    assert "Eksportér bibliotek…" in build
    assert "Ny artikel…" in build


def test_manual_article_editor_has_image_and_datasheet_fields():
    src=(Path(__file__).resolve().parents[1] / "elplan_qt/qt_articles.py").read_text(encoding="utf-8")
    block=src[src.index("class ArticleEditDialog"):src.index("class ArticlePriceDialog")]
    assert 'self.image_url=QLineEdit' in block
    assert 'self.datasheet_url=QLineEdit' in block
    assert 'links.addRow("Billede-URL",self.image_url)' in block
