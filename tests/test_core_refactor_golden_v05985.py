from __future__ import annotations

import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

import core_logic as core
from project_model import ProjectDocument


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
GOLDEN = ROOT / "tests" / "golden"


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _rounded(value):
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, dict):
        return {str(key): _rounded(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_rounded(item) for item in value]
    return value


def _project_and_articles():
    project = ProjectDocument.load(FIXTURES / "core_golden_project.elplan.json")
    articles = _json(FIXTURES / "core_golden_articles.json")
    return project, articles


def test_refactor_fixture_exercises_real_project_features():
    project, articles = _project_and_articles()
    assert len(project.placements) == 5
    assert len(project.cables) == 3
    assert len(project.rooms) == 2
    assert len(articles["catalog"]) == 8
    lamp = next(row for row in project.placements if row.uid == "light-01")
    assert len(lamp.pl_box_entries) == 2
    assert lamp.pl_box_splices[0]["article_no"] == "WAGO-221-413"
    assert project.raw["placement_assemblies"]["sw-01"]["symbol"] == "asm-switch-standard"


def test_build_bom_matches_golden_output():
    project, article_data = _project_and_articles()
    rows, missing = core.build_bom(
        project.placements,
        article_data["catalog"],
        project.raw.get("placement_articles", {}),
        cables=project.cables,
        cable_bindings=project.raw.get("cable_instance_articles", {}),
        metres_per_unit=article_data["metres_per_unit"],
        reserve_percent=article_data["reserve_percent"],
        assemblies=article_data["assemblies"],
        assembly_bindings=project.raw.get("placement_assemblies", {}),
        rooms=project.rooms,
        placement_room_additions=project.raw.get("placement_bom_room_additions", {}),
    )
    expected = _json(GOLDEN / "build_bom.json")
    canonical = json.dumps(
        {"rows": rows, "missing": missing},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    assert hashlib.sha256(canonical.encode("utf-8")).hexdigest() == expected["canonical_sha256"]
    selected = (
        "article_no", "qty", "quantity_to_buy", "unit", "unit_price", "line_total",
        "line_total_to_buy", "mounting_zone", "mounting_height_mm", "material_color",
        "already_purchased", "detail", "purchase_summary",
    )
    summary = [_rounded({key: row.get(key) for key in selected}) for row in rows]
    assert {"row_count": len(rows), "missing": missing, "rows": summary} == {
        key: expected[key] for key in ("row_count", "missing", "rows")
    }


def test_cable_visual_layout_matches_golden_output():
    project, _articles = _project_and_articles()
    paths, metadata, joints = core.cable_visual_layout(project.cables, 60.0)
    uid_by_object_id = {id(cable): cable.uid for cable in project.cables}
    actual = _rounded({
        "paths": {
            uid_by_object_id[key]: value
            for key, value in sorted(paths.items(), key=lambda item: uid_by_object_id[item[0]])
        },
        "meta": {
            uid_by_object_id[key]: value
            for key, value in sorted(metadata.items(), key=lambda item: uid_by_object_id[item[0]])
        },
        "joints": joints,
    })
    assert actual == _json(GOLDEN / "cable_visual_layout.json")


def test_load_document_and_extract_cad_primitives_match_golden_output():
    document = core.load_document(ROOT / "examples" / "demo_floor.dxf")
    primitives, counts = core.extract_cad_primitives(document)
    canonical_rows = [
        {"kind": primitive.kind, "layer": primitive.layer, "data": primitive.data}
        for primitive in primitives
    ]
    canonical = json.dumps(
        canonical_rows,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    actual = {
        "document_extents": _rounded(core.document_extents(document)),
        "primitive_count": len(primitives),
        "counts": counts,
        "layers": dict(sorted(Counter(primitive.layer for primitive in primitives).items())),
        "canonical_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }
    assert actual == _json(GOLDEN / "cad_primitives.json")


def test_export_vector_pdf_text_and_pages_match_golden_output():
    project, _articles = _project_and_articles()
    document = core.load_document(ROOT / "examples" / "demo_floor.dxf")
    primitives, _counts = core.extract_cad_primitives(document)
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "golden.pdf"
        core.export_vector_pdf(
            target,
            primitives,
            project.placements,
            cables=project.cables,
            texts=project.texts,
            rooms=project.rooms,
            room_labels_visible=True,
            room_codes_visible=True,
            room_boundaries_visible=True,
            paper="A4",
            orientation="Auto",
            annotation_mode="Tydelig",
        )
        reader = PdfReader(str(target))
        text_lines = []
        for page in reader.pages:
            text_lines.extend(
                " ".join(line.split())
                for line in (page.extract_text() or "").splitlines()
                if line.strip()
            )
        actual = {
            "page_count": len(reader.pages),
            "page_sizes_points": [
                [round(float(page.mediabox.width), 3), round(float(page.mediabox.height), 3)]
                for page in reader.pages
            ],
            "text_lines": text_lines,
        }
    assert actual == _json(GOLDEN / "export_vector_pdf.json")
