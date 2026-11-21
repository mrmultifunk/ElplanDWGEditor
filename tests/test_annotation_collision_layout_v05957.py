from pathlib import Path

from annotation_layout import choose_label_origin, rects_overlap

ROOT=Path(__file__).resolve().parents[1]


def test_collision_layout_keeps_label_outside_symbol_and_existing_metadata():
    symbol=(40,40,60,60)
    existing=(65,44,90,56)
    x,y,side,rect=choose_label_origin(
        (50,50),symbol,24,10,
        blockers=[symbol],occupied=[existing],preferred="right",gap=5,collision_padding=1,
    )
    assert not rects_overlap(rect,symbol,1)
    assert not rects_overlap(rect,existing,1)
    assert side in {"left","above","below","right"}


def test_collision_layout_avoids_neighbour_symbol_as_hard_blocker():
    own=(40,40,60,60)
    neighbour=(64,35,88,65)
    _x,_y,_side,rect=choose_label_origin(
        (50,50),own,22,9,
        blockers=[own,neighbour],preferred="right",gap=4,collision_padding=1,
    )
    assert not rects_overlap(rect,own,1)
    assert not rects_overlap(rect,neighbour,1)


def test_qt_and_pdf_use_shared_collision_layout():
    app=(ROOT/"qt_app.py").read_text(encoding="utf-8")
    qt=(ROOT/"qt_annotation_layout.py").read_text(encoding="utf-8")
    pdf=(ROOT/"elplan_core"/"export"/"pdf.py").read_text(encoding="utf-8")
    assert "layout_symbol_metadata" in app
    assert "choose_label_origin" in qt
    assert "symbol_blockers" in pdf
    assert "metadata_occupied" in pdf
    assert "choose_label_origin(" in pdf
