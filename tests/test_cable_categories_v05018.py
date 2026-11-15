from pathlib import Path

import ezdxf

import core_logic as core
from project_model import ProjectDocument, APP_VERSION


def test_version_05020():
    assert APP_VERSION == core.APP_VERSION == "0.59.81"


def test_default_categories_cover_requested_installation_groups():
    rows=core.default_cable_category_records()
    names={r["name"] for r in rows}
    assert "Stikkontakter" in names
    assert "Udendørs stikkontakter" in names
    assert "Udendørs lys" in names
    assert "Lampesteder" in names
    assert "Mellemkabel" in names
    assert "Tændkabel" in names
    assert "Spots" in names
    assert "Ladeboks" in names
    assert all(r["line_style"] in core.CABLE_LINE_STYLES for r in rows)
    assert all(str(r["color"]).startswith("#") for r in rows)


def test_cable_category_is_persisted_and_has_real_visibility_layer(tmp_path):
    project=ProjectDocument.from_cad(tmp_path/'plan.dxf')
    project.cables=[core.CablePlacement(points=[(0,0),(10,0)],cable_category='light_points')]
    effective=core.cable_effective_layer(project.cables[0])
    project.layer_visibility[effective]=False
    path=tmp_path/'p.elplan.json'
    project.path=path
    project.save()
    loaded=ProjectDocument.load(path)
    assert loaded.cables[0].cable_category=='light_points'
    assert loaded.layer_visibility[effective] is False
    assert core.cable_visible_in_layers(loaded.cables[0],loaded.layer_visibility) is False
    assert loaded.raw['cable_categories']


def test_legacy_base_layer_visibility_is_fallback_until_category_layer_exists():
    cable=core.CablePlacement(points=[(0,0),(1,0)],layer=core.CABLE_LAYER,cable_category='spots')
    effective=core.cable_effective_layer(cable)
    vis={core.CABLE_LAYER:False}
    assert core.cable_visible_in_layers(cable,vis) is False
    vis[effective]=True
    assert core.cable_visible_in_layers(cable,vis) is True


def test_category_layer_is_used_for_dxf_export():
    doc=ezdxf.new('R2010')
    msp=doc.modelspace()
    cable=core.CablePlacement(points=[(0,0),(10,0)],layer=core.CABLE_LAYER,cable_category='outdoor_lighting',color='#15803d',line_style='dashdot')
    core.add_cable_to_dxf(msp,cable)
    entity=list(msp)[0]
    assert entity.dxf.layer==core.cable_effective_layer(cable)
    assert '-KAT-OUTDOOR-LIGHTING' in entity.dxf.layer


def test_qt_ui_exposes_category_assignment_configuration_and_layer_menu():
    source=Path('qt_app.py').read_text(encoding='utf-8') + Path('qt_cable_panel.py').read_text(encoding='utf-8')
    assert 'class CableCategoryDialog' in source
    assert 'self.cable_category_combo = QComboBox()' in source
    assert 'Konfigurér kabelkategorier…' in source
    assert 'view_menu.addMenu("Kabelkategorier")' in source
    assert 'core.cable_effective_layer(cable)' in source
    assert 'Farve og linjetype styres normalt via kabelkategorien' in source


def test_legacy_project_gets_new_interconnect_and_switch_cable_categories(tmp_path):
    import json
    path=tmp_path/'legacy.elplan.json'
    data={
        'version':'0.50.18',
        'source_file':'',
        'cable_categories':[
            {'id':'sockets','name':'Stikkontakter','color':'#112233','line_style':'solid'},
            {'id':'other','name':'Øvrige','color':'#d00000','line_style':'solid'},
        ],
        'placements':[], 'cables':[], 'texts':[], 'layer_visibility':{},
    }
    path.write_text(json.dumps(data),encoding='utf-8')
    loaded=ProjectDocument.load(path)
    by_id={row['id']:row for row in loaded.raw['cable_categories']}
    assert 'interconnect' in by_id
    assert by_id['interconnect']['name']=='Mellemkabel'
    assert 'switch_cable' in by_id
    assert by_id['switch_cable']['name']=='Tændkabel'
    # Existing category customization is preserved.
    assert by_id['sockets']['color']=='#112233'
