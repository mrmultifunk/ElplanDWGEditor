from pathlib import Path

import core_logic as core


def test_print_relation_tag_profile_is_quiet_and_compact():
    overview = core.output_switch_association_tag_profile(True)
    detail = core.output_switch_association_tag_profile(False)

    # A single letter must no longer be forced into the old 20 pt wide pill.
    assert overview["min_width"] == 0.0
    assert detail["min_width"] == 0.0
    assert detail["pad_x"] < 2.5
    assert detail["pad_y"] <= 0.25
    assert detail["font_size"] < 6.5
    assert detail["fill_alpha"] <= 0.55
    assert detail["border_alpha"] < 0.50
    assert detail["line_width"] < 0.4


def test_pdf_switch_relation_uses_compact_font(tmp_path):
    fitz = __import__("pytest").importorskip("fitz")
    switch = core.Placement(
        symbol="switch_1", x=500.0, y=500.0, size=180.0,
        association_channels=["b"], associations=["b"],
    )
    cad = [
        core.CADPrimitive("line", "0", (0.0, 0.0, 1000.0, 0.0)),
        core.CADPrimitive("line", "0", (1000.0, 0.0, 1000.0, 1000.0)),
    ]
    out = tmp_path / "association.pdf"
    core.export_vector_pdf(out, cad, [switch], paper="A4", orientation="Landskab", annotation_mode="Tydelig")

    doc = fitz.open(out)
    spans = []
    for block in doc[0].get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            spans.extend(line.get("spans", []))
    tags = [span for span in spans if span.get("text", "").strip() == "b"]
    assert tags
    assert abs(float(tags[0]["size"]) - 6.2) < 0.08


def test_version_is_05954():
    root = Path(__file__).resolve().parents[1]
    assert 'APP_VERSION = "0.59.74"' in (root / "project_model.py").read_text(encoding="utf-8")
