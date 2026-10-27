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
    core_source=open(core.__file__,encoding="utf-8").read()
    assert '0.0 if typ=="upright_text" else placement.rotation' in core_source
    assert '0.0 if typ=="upright_text" else pl.rotation' in core_source

    qt_source=Path(core.__file__).with_name("qt_graphics.py").read_text(encoding="utf-8")
    assert 'elif kind == "upright_text"' in qt_source
    assert "True,self.placement.rotation" in qt_source
