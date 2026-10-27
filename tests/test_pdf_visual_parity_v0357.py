import math
from pathlib import Path

import pytest
fitz = pytest.importorskip("fitz")

import core_logic as core


def _span_sizes(pdf_path: Path):
    doc=fitz.open(pdf_path)
    out={}
    for block in doc[0].get_text('dict')['blocks']:
        for line in block.get('lines',[]):
            for span in line.get('spans',[]):
                text=span.get('text','').strip()
                if text:
                    out.setdefault(text,[]).append(float(span['size']))
    return out


def test_shared_output_font_formulas():
    assert math.isclose(core.output_free_text_font_size(100),6.5)
    assert math.isclose(core.output_free_text_font_size(300),19.5)
    assert math.isclose(core.output_cad_text_font_size(300,0.1),19.5)
    assert math.isclose(core.output_symbol_text_font_size(100,0.1),6.0)
    assert math.isclose(core.output_equivalent_view_scale(0.075),0.1)


def test_annotation_profile_matches_overview_contract():
    overview=core.annotation_visual_profile('Auto',0.12,False)
    detail=core.annotation_visual_profile('Auto',0.25,False)
    assert overview['primary']==5.9
    assert overview['assoc']==5.6
    assert detail['primary']==7.5
    assert core.annotation_visual_profile('Minimal',0.5,False)['primary']==6.1


def test_pdf_free_text_is_screen_space_not_cad_scaled(tmp_path):
    # Wide extents force a small CAD->page scale. Free text must nevertheless
    # stay at the exact Qt point size (300*0.065 = 19.5 pt).
    cad=[
        core.CADPrimitive('line','0',(0.0,0.0,10000.0,0.0)),
        core.CADPrimitive('line','0',(10000.0,0.0,10000.0,8000.0)),
        core.CADPrimitive('text','0',(1000.0,6000.0,'CADTXT',300.0,0.0)),
    ]
    text=core.TextPlacement(text='FRITXT',x=3000.0,y=5000.0,height=300.0)
    out=tmp_path/'parity.pdf'
    ext=core.print_extents(cad,[],texts=[text])
    _page,_effective,scale,*_=core.page_layout(ext,'A3','Landskab')
    core.export_vector_pdf(out,cad,[],texts=[text],paper='A3',orientation='Landskab',annotation_mode='Auto')
    spans=_span_sizes(out)
    assert abs(spans['FRITXT'][0]-19.5)<0.05
    expected_cad=core.output_cad_text_font_size(300.0,scale)
    assert abs(spans['CADTXT'][0]-expected_cad)<0.08


def test_pdf_auto_overview_hides_secondary_label(tmp_path):
    cad=[core.CADPrimitive('line','0',(0.0,0.0,10000.0,8000.0))]
    light=core.Placement(symbol='light_connection',x=5000,y=4000,size=300,group='G01',label='LYS-01',associations=['a'])
    out=tmp_path/'auto.pdf'
    core.export_vector_pdf(out,cad,[light],paper='A3',orientation='Landskab',annotation_mode='Auto')
    spans=_span_sizes(out)
    assert 'G01' in spans
    assert 'a' in spans
    assert 'LYS-01' not in spans
