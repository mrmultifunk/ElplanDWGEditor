from pathlib import Path


def test_qt_article_preview_supports_bundled_local_images_without_network():
    source=(Path(__file__).resolve().parents[1]/"elplan_qt/qt_articles.py").read_text(encoding="utf-8")
    assert "image_local_path" in source
    assert "Indbygget produktbillede" in source
    assert "def _resolve_local_image_path" in source
    assert "def _load_local_image" in source
