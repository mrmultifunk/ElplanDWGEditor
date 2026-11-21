import ezdxf
from pathlib import Path

import core_logic as core


def test_socket_3fn_dxf_text_stays_horizontal_when_symbol_rotates():
    doc=ezdxf.new()
    placement=core.Placement(
        symbol="socket_3fn", x=100.0, y=200.0, size=80.0, rotation=90.0
    )

    core.add_placement_to_dxf(doc.modelspace(),placement)

    labels=[entity for entity in doc.modelspace().query("TEXT") if entity.dxf.text=="3N"]
    assert len(labels)==1
    assert float(labels[0].dxf.rotation)==0.0


def test_all_symbol_outputs_handle_upright_text_explicitly():
    root = Path(core.__file__).parent
    dxf_source = (root / "elplan_core/export/dxf_writer.py").read_text(encoding="utf-8")
    printing_source = (root / "elplan_core/platform/printing.py").read_text(encoding="utf-8")
    assert '0.0 if typ=="upright_text" else placement.rotation' in dxf_source
    assert '0.0 if typ=="upright_text" else pl.rotation' in printing_source

    qt_source=(Path(core.__file__).parent / "elplan_qt/qt_graphics.py").read_text(encoding="utf-8")
    assert 'elif kind in {"text", "upright_text"}' in qt_source
    assert 'if kind == "upright_text"' in qt_source
    assert "True,self.placement.rotation" in qt_source

    legacy_source=(Path(core.__file__).parent / "elplan_legacy/legacy_tk_app.py").read_text(encoding="utf-8")
    assert legacy_source.count('typ in {"text","upright_text"}') >= 5
    assert '0.0 if typ=="upright_text" else -float(pl.rotation)' in legacy_source
