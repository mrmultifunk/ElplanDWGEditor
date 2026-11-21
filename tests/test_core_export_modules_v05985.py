from __future__ import annotations

from unittest.mock import patch

import ezdxf

import core_logic as core
from elplan_core import cad_io
from elplan_core.cables import visual
from elplan_core.export import dxf_writer, extents, output_profiles, pdf


def test_cad_and_export_modules_are_reexported_through_core_facade():
    for module, names in (
        (cad_io, ("load_document", "drawing_unit_info", "document_extents", "extract_cad_primitives")),
        (visual, ("cable_display_label", "cable_plan_label", "cable_visual_layout", "cable_visual_paths")),
        (dxf_writer, ("ensure_layers", "add_placement_to_dxf", "add_cable_to_dxf", "add_free_text_to_dxf")),
        (extents, ("print_extents", "fit_view_extents", "page_layout", "resolve_page_size")),
        (output_profiles, ("output_equivalent_view_scale", "annotation_visual_profile")),
        (pdf, ("export_vector_pdf",)),
    ):
        for name in names:
            assert getattr(core, name) is getattr(module, name)


def test_dxf_writer_round_trip_keeps_symbol_cable_and_text(tmp_path):
    document = ezdxf.new("R2018", units=4)
    dxf_writer.ensure_layers(document)
    symbol = core.Placement("light_connection", 100, 200, color="#112233")
    cable = core.CablePlacement(
        points=[(100, 200), (100, 300)], cable_id="K-01",
        cable_spec="3G1,5", auto_label=True, line_style="dash", color="#336699",
    )
    space = document.modelspace()
    dxf_writer.add_placement_to_dxf(space, symbol)
    dxf_writer.add_cable_to_dxf(space, cable)
    dxf_writer.add_free_text_to_dxf(space, core.TextPlacement(text="Montage", x=150, y=200))
    path = tmp_path / "export.dxf"
    document.saveas(path)

    loaded = cad_io.load_document(path)
    output = loaded.modelspace()
    assert cad_io.drawing_unit_info(loaded) == (4, "mm", .001)
    lines = list(output.query("LINE"))
    assert lines and all(e.dxf.layer == core.symbol_layer(symbol.symbol) for e in lines)
    assert all(e.dxf.true_color == 0x112233 for e in lines)
    exported_cable, = output.query("LWPOLYLINE")
    assert list(exported_cable.get_points("xy")) == cable.points
    assert exported_cable.dxf.linetype == "DASHED"
    assert exported_cable.dxf.true_color == 0x336699
    assert [e.text for e in output.query("MTEXT")] == ["K-01 · 3G1,5"]
    assert [(e.dxf.text, e.dxf.layer) for e in output.query("TEXT")] == [("Montage", core.FREE_TEXT_LAYER)]


def test_dwg_loading_still_dispatches_to_oda_reader():
    with patch.object(cad_io.odafc, "readfile") as read:
        assert core.load_document("installation.DWG") is read.return_value
        read.assert_called_once_with("installation.DWG")
