from pathlib import Path


def test_preview_uses_production_pdf_renderer():
    source = (Path(__file__).resolve().parents[1] / "qt_app.py").read_text(encoding="utf-8")
    start = source.index("class PrintPreviewCanvas")
    end = source.index("class PrintPreviewDialog", start)
    block = source[start:end]
    assert "core.export_vector_pdf(" in block
    assert "QPdfDocument" in block
    assert "scene.render(" not in block
    assert "annotation_mode=self.window.annotation_display_mode" in block
    assert "cad_opacity=self.window._output_cad_opacity()" in block
    assert "fill_page=False" in block


def test_version_is_0358():
    source = (Path(__file__).resolve().parents[1] / "project_model.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "0.59.83"' in source
