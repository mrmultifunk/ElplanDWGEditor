from pathlib import Path

import core_logic as core
from project_model import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


class _FakePath:
    def moveTo(self,*_args):pass
    def lineTo(self,*_args):pass
    def close(self):pass
    def rect(self,*_args):pass


class _FakeCanvas:
    def __init__(self,*_args,**_kwargs):
        self.texts=[]
        self.drawn_paths=0

    def beginPath(self):return _FakePath()
    def drawString(self,_x,_y,value):self.texts.append(str(value))
    def drawPath(self,*_args,**_kwargs):self.drawn_paths+=1
    def __getattr__(self,_name):return lambda *_args,**_kwargs:None


def _render(monkeypatch,room,**kwargs):
    canvas=_FakeCanvas()
    monkeypatch.setattr(core.pdfcanvas,"Canvas",lambda *_args,**_kwargs:canvas)
    core.export_vector_pdf("ignored.pdf",[],[],rooms=[room],**kwargs)
    return canvas


def test_version_v05967():
    assert APP_VERSION == core.APP_VERSION == "0.59.78"


def test_pdf_renders_room_name_and_keeps_code_independent(monkeypatch):
    room=core.RoomPlacement(
        name="Køkken",code="R01",points=[(0,0),(100,0),(100,100),(0,100)],
        label_x=30,label_y=60,
    )
    names=_render(monkeypatch,room,room_labels_visible=True,room_codes_visible=False)
    assert names.texts == ["Køkken"]

    names_and_codes=_render(monkeypatch,room,room_labels_visible=True,room_codes_visible=True)
    assert names_and_codes.texts == ["R01 · Køkken"]


def test_pdf_room_visibility_and_boundary_are_separate(monkeypatch):
    room=core.RoomPlacement(
        name="Stue",code="R02",points=[(0,0),(100,0),(100,100),(0,100)],
        label_x=30,label_y=60,
    )
    boundary_only=_render(
        monkeypatch,room,room_labels_visible=False,room_boundaries_visible=True,
    )
    assert boundary_only.texts == []
    assert boundary_only.drawn_paths == 1

    hidden_layer=_render(
        monkeypatch,room,layer_visibility={core.ROOM_LAYER:False},
        room_labels_visible=True,room_boundaries_visible=True,
    )
    assert hidden_layer.texts == []
    assert hidden_layer.drawn_paths == 0


def test_qt_pdf_preview_export_and_print_pass_room_state():
    source=(ROOT / "qt_app.py").read_text(encoding="utf-8")
    assert source.count("rooms=self.project.rooms") >= 2
    assert "rooms=self.window.project.rooms" in source
    assert source.count('room_labels_visible=bool(') >= 3
    assert source.count('room_codes_visible=bool(') >= 3
    assert source.count('room_boundaries_visible=bool(') >= 3
