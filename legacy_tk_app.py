from __future__ import annotations

"""Archived Tkinter frontend kept only for backwards compatibility.

All shared domain/CAD logic lives in :mod:`core_logic`; this module is loaded
lazily through ``legacy_core.ElplanEditor`` and is not part of normal Qt startup.
"""

import hashlib
import json
import math
import os
import re
import tempfile
import time
import webbrowser
import uuid
from pathlib import Path

import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk
import tkinter.font as tkfont

import ezdxf
from reportlab.lib.pagesizes import A3, A4, landscape, portrait
from ezdxf import bbox
from ezdxf.addons import odafc

import core_logic as _core

# The archived class was originally defined in the same module as the core.
# Populate its old global namespace without duplicating 3,600 lines of logic.
globals().update({name: getattr(_core, name) for name in dir(_core) if not name.startswith("__")})

class ElplanEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.app_settings=load_app_settings()
        # Brugerdefinerede kombisymboler er selvbeskrivende i deres symbolkode.
        # Navne gemmes separat for en pæn palette og genindlæses på tværs af projekter.
        register_custom_symbol_records(self.app_settings.get("custom_symbols",[]))
        saved_geometry=str(self.app_settings.get("window_geometry","") or "")
        if re.fullmatch(r"\d+x\d+(?:[+-]\d+[+-]\d+)?",saved_geometry):
            self.geometry(saved_geometry)
        else:
            self.geometry("1500x940")
        self.minsize(900,600)
        self.doc=None; self.file_path: str|None=None; self.project_path: str|None=None
        self._dirty=False; self._autosave_job=None
        self.extent=(0.0,0.0,1000.0,1000.0)
        self.cad_primitives: list[CADPrimitive]=[]; self.primitive_counts={}
        self.cad_text_items: list[tuple[int,float]]=[]
        self.placements: list[Placement]=[]
        self.cables: list[CablePlacement]=[]
        self.texts: list[TextPlacement]=[]
        self.selected_index: int|None=None
        # Multi-select gælder symboler. selected_index bruges kun ved præcis ét
        # valgt symbol, så det eksisterende egenskabspanel forbliver enkelt.
        self.selected_indices: set[int]=set()
        self.selected_cable_index: int|None=None
        self.selected_text_index: int|None=None
        self.selection_rect_start: tuple[int,int]|None=None
        self.selection_rect_active=False
        self.multi_drag_start_positions: dict[int,tuple[float,float]]={}
        self.drag_primary_symbol_index: int|None=None
        self.creation_history=[]  # legacy; rigtig Undo/Redo bruger snapshots nedenfor
        self.undo_stack=[]; self.redo_stack=[]; self.max_history=100
        self._history_restoring=False; self._drag_history_snapshot=None; self._drag_history_label=""
        self.current_cable_points: list[tuple[float,float]]=[]
        self.current_cable_start_uid=""; self.current_cable_end_uid=""
        self.current_cable_start_port=0; self.current_cable_end_port=0
        self.cable_preview_cursor: tuple[float,float]|None=None
        self.view_scale=1.0; self.offset_x=0.0; self.offset_y=0.0; self.pan_last=None; self.mode="select"
        # Alt-status spores eksplicit. Mouse-event.state er ikke stabil nok på tværs af
        # Tk/Windows builds til at bruge udokumenterede høje bits som snap-bypass.
        self._alt_down=False
        self.layer_visibility={}; self.original_layer_visibility={}; self.layer_tags={}
        self.dragging=False; self.drag_start_cad=None; self.drag_original_points=None
        self.selected_cable_vertex_index: int|None=None
        self.drag_vertex_original_index: int|None=None

        first=str(self.app_settings.get("symbol_category",next(iter(SYMBOL_GROUPS))))
        if first=="Kontakter":first="Afbrydere"
        if first not in SYMBOL_GROUPS:first=next(iter(SYMBOL_GROUPS))
        self.symbol_category=tk.StringVar(value=first)
        self.symbol_name=tk.StringVar(value=next(iter(SYMBOL_GROUPS[first])))
        self.default_symbol_size=500.0; self.default_symbol_line_width=0.25
        self.symbol_color_defaults={code: DEFAULT_SYMBOL_COLOR for code in SYMBOLS.values()}
        self.symbol_color=tk.StringVar(value=DEFAULT_SYMBOL_COLOR)
        self.symbol_size=tk.DoubleVar(value=self.default_symbol_size)
        self.symbol_line_width=tk.DoubleVar(value=self.default_symbol_line_width)
        self.symbol_layer_var=tk.StringVar(value=f"CAD-lag: {symbol_layer(SYMBOLS[self.symbol_name.get()])}")
        self.rotation=tk.DoubleVar(value=0.0)
        self.paper_size=tk.StringVar(value="A4"); self.page_orientation=tk.StringVar(value="Auto"); self.print_scope=tk.StringVar(value=DEFAULT_PRINT_SCOPE)
        # Mørkt tema er midlertidigt fjernet igen. Gemte mørke indstillinger fra 0.19.0 ignoreres.
        self.theme_mode=tk.StringVar(value=DEFAULT_THEME)
        self.print_preview_window=None; self._print_preview_canvas=None; self._print_preview_info_var=None; self._preview_redraw_job=None
        self.label_var=tk.StringVar(); self.group_var=tk.StringVar()
        self.combo_label_mode=tk.StringVar(value="Fælles")
        self.combo_switch_label=tk.StringVar(); self.combo_switch_group=tk.StringVar()
        self.combo_socket_label=tk.StringVar(); self.combo_socket_group=tk.StringVar()
        self.association_var=tk.StringVar(value="—")
        self.symbol_locked=tk.BooleanVar(value=False)
        self.association_source_uid=""
        self.annotation_style=tk.StringVar(value=DEFAULT_ANNOTATION_STYLE)
        self.annotation_font_size=tk.IntVar(value=DEFAULT_ANNOTATION_FONT_SIZE)
        self.annotation_auto_place=tk.BooleanVar(value=True)
        self._annotation_redraw_job=None
        self._placement_redraw_job=None
        self._cable_preview_job=None
        self.symbol_clipboard: Placement|None=None
        self.multi_symbol_clipboard: list[Placement]=[]
        self.last_canvas_mouse: tuple[int,int]|None=None
        # Smart duplikering: gentagne Ctrl+D bruger samme afstand. Hvis den
        # første kopi flyttes, bliver den endelige afstand genbrugt næste gang.
        self.last_duplicate_delta: tuple[float,float]|None=None
        self._duplicate_pending_uids: set[str]=set()
        self._duplicate_pending_base_delta: tuple[float,float]|None=None
        self._duplicate_pending_positions: dict[str,tuple[float,float]]={}
        self.cable_type=tk.StringVar(value="Kabel")
        self.cable_spec=tk.StringVar(value="3G1,5")
        self.cable_line_width=tk.DoubleVar(value=0.35)
        self.cable_label=tk.StringVar(value="")
        self.cable_auto_label=tk.BooleanVar(value=True)
        self.cable_orthogonal=tk.BooleanVar(value=True)
        # Én fælles symbol-snap indstilling styrer både symbol-sammenstilling
        # og kabel/ledning til symbolporte. Tidligere var de to skjulte indstillinger
        # uafhængige, hvilket var en væsentlig årsag til uforudsigelig snap.
        self.snap_to_symbols=tk.BooleanVar(value=True)
        self.snap_to_walls=tk.BooleanVar(value=True)
        self.snap_symbols_together=self.snap_to_symbols  # bagudkompatibelt alias
        self.continuous_placement=tk.BooleanVar(value=True)
        self.text_content=tk.StringVar(value="Rum")
        self.text_height=tk.DoubleVar(value=250.0)
        self.text_rotation=tk.DoubleVar(value=0.0)
        self.text_color=tk.StringVar(value="#202020")
        self.default_text_height=250.0
        self.default_text_color="#202020"
        # Spot-række: to klik definerer en ret linje, og spots fordeles jævnt.
        self.spot_default_size=200.0
        self.spot_size_var=tk.DoubleVar(value=self.spot_default_size)
        self.spot_row_count=tk.IntVar(value=4)
        self.spot_row_link_after=tk.BooleanVar(value=True)
        self.spot_row_start: tuple[float,float]|None=None
        self.spot_row_preview_end: tuple[float,float]|None=None
        self.spot_row_pending_uids: list[str]=[]
        # Rektangulært spotmønster: to modstående hjørner definerer området.
        self.spot_rect_columns=tk.IntVar(value=3)
        self.spot_rect_rows=tk.IntVar(value=2)
        self.spot_rect_link_after=tk.BooleanVar(value=True)
        self.spot_rect_start: tuple[float,float]|None=None
        self.spot_rect_preview_end: tuple[float,float]|None=None
        self.palette_cards={}
        usage_settings=self.app_settings
        try:
            self.spot_default_size=max(20.0,min(5000.0,float(usage_settings.get("spot_default_size",self.spot_default_size))))
        except Exception:
            self.spot_default_size=200.0
        self.spot_size_var.set(self.spot_default_size)
        self.combo_templates=normalize_combo_template_records(usage_settings.get("combo_templates",[]))
        self.favorite_symbols=[c for c in usage_settings.get("favorite_symbols",[]) if c in SYMBOL_NAMES_BY_CODE]
        self.recent_symbols=[c for c in usage_settings.get("recent_symbols",[]) if c in SYMBOL_NAMES_BY_CODE][:8]
        self.recent_projects=[str(x) for x in usage_settings.get("recent_projects",[]) if isinstance(x,str)][:MAX_RECENT_PROJECTS]
        self.show_annotations=tk.BooleanVar(value=bool(usage_settings.get("show_annotations",True)))
        self.show_associations=tk.BooleanVar(value=bool(usage_settings.get("show_associations",True)))
        self.show_cables_overlay=tk.BooleanVar(value=bool(usage_settings.get("show_cables_overlay",True)))
        self.quick_symbol_cards={}
        self.snap_segments=[]
        self.snap_grid={}; self.snap_grid_size=1.0; self.snap_long_segments=[]
        # Spatialt indeks over placerede el-symboler. Det bruges af hit-test,
        # kabelsnap og symbol-snap, så musebevægelse ikke scanner hele projektet.
        self.placement_snap_grid={}; self.placement_snap_grid_size=500.0; self.placement_snap_long=[]
        self.snap_marker=None; self.snap_marker_kind=""
        # Dirty redraw: under drag opdateres kun de objekter der faktisk ændres.
        self._dirty_symbol_indices=set(); self._dirty_cable_indices=set(); self._dirty_text_indices=set(); self._dirty_full_redraw=False
        # Mouse-motion throttling/performance diagnostics.
        self._motion_pending=None; self._motion_job=None; self._motion_last_process=0.0
        self._perf_motion_count=0; self._perf_window_start=time.perf_counter(); self._perf_fps=0.0
        self._perf_last_motion_ms=0.0; self._perf_last_snap_ms=0.0; self._perf_last_redraw_ms=0.0; self._perf_last_dirty_redraw_ms=0.0
        self._perf_last_zoom_ms=0.0; self._perf_last_pan_ms=0.0
        # Navigation batching: Windows/trackpads can generate far more events than
        # Tk can transform 10k+ vector-items smoothly. Aggregate to one transform/frame.
        self._zoom_pending_steps=0.0; self._zoom_pending_anchor=None; self._zoom_job=None
        self._pan_pending_dx=0.0; self._pan_pending_dy=0.0; self._pan_job=None
        self._navigation_settle_job=None; self._navigation_active=False
        self.perf_diagnostics=False; self._perf_update_job=None
        self.snap_feedback_kind=""
        # Live diagnose/feedback: viser den kandidat, som det næste klik faktisk bruger.
        self.snap_live_kind=""
        # Snap er en program-/arbejdsindstilling, ikke en projektegenskab.
        # 0.19.3 migrerer én gang fra de ældre versioner ved at aktivere begge
        # snaptyper. Det forhindrer gamle projekt-/settings-filer med et skjult
        # False-flag i at få snap til at se permanent defekt ud.
        snap_migration_done=bool(usage_settings.get("snap_0193_migrated",False))
        if not snap_migration_done:
            self.snap_to_symbols.set(True); self.snap_to_walls.set(True)
        else:
            old_symbol_snap=bool(usage_settings.get("snap_to_symbols",True)) or bool(usage_settings.get("snap_symbols_together",False))
            self.snap_to_symbols.set(old_symbol_snap)
            self.snap_to_walls.set(bool(usage_settings.get("snap_to_walls",True)))
        self.continuous_placement.set(bool(usage_settings.get("continuous_placement",self.continuous_placement.get())))
        if usage_settings.get("annotation_style") in ANNOTATION_STYLES:self.annotation_style.set(usage_settings["annotation_style"])
        try:self.annotation_font_size.set(max(7,min(10,int(usage_settings.get("annotation_font_size",self.annotation_font_size.get())))))
        except Exception:pass
        self.annotation_auto_place.set(bool(usage_settings.get("annotation_auto_place",self.annotation_auto_place.get())))
        if usage_settings.get("paper_size") in ("A4","A3"):self.paper_size.set(usage_settings["paper_size"])
        if usage_settings.get("page_orientation") in ("Auto","Portræt","Landskab"):self.page_orientation.set(usage_settings["page_orientation"])
        if usage_settings.get("print_scope") in PRINT_SCOPES:self.print_scope.set(usage_settings["print_scope"])
        self.layer_summary_var=tk.StringVar(value="Lag: ingen tegning")
        self.vector_status_var=tk.StringVar(value="Viewer: ægte CAD-vektorer")
        self.status_var=tk.StringVar(value="Åbn en DWG- eller DXF-fil for at starte.")
        self.mode_status_var=tk.StringVar(value="Tilstand: Vælg")
        self.snap_status_var=tk.StringVar(value="Snap: —")
        self.autosave_status_var=tk.StringVar(value="Autosave: klar")
        self.oda_status_var=tk.StringVar(value="DWG: kontrollerer ODA…"); self.oda_path=None
        self._configure_styles()
        self._build_ui(); self._apply_theme(redraw=False); self.after(50,self.refresh_oda_status)
        self.bind("<Delete>",lambda e:self.delete_selected())
        self.bind("<Escape>",self.on_escape)
        self.bind("<Control-c>",self.copy_selected_symbol)
        self.bind("<Control-C>",self.copy_selected_symbol)
        self.bind("<Control-v>",self.paste_symbol)
        self.bind("<Control-V>",self.paste_symbol)
        self.bind("<Control-z>",self.undo)
        self.bind("<Control-Z>",self.undo)
        self.bind("<Control-y>",self.redo)
        self.bind("<Control-Y>",self.redo)
        self.bind("<Control-Shift-Z>",self.redo)
        self.bind("<Control-r>",lambda e:self.rotate_selected())
        self.bind("<Control-R>",lambda e:self.rotate_selected())
        self.bind("<Control-d>",self.duplicate_selected)
        self.bind("<Control-D>",self.duplicate_selected)
        self.bind("<Control-a>",self.select_all_symbols)
        self.bind_all("<KeyPress-Alt_L>",self._alt_key_down,add="+")
        self.bind_all("<KeyPress-Alt_R>",self._alt_key_down,add="+")
        self.bind_all("<KeyRelease-Alt_L>",self._alt_key_up,add="+")
        self.bind_all("<KeyRelease-Alt_R>",self._alt_key_up,add="+")
        self.bind_all("<FocusOut>",self._alt_focus_out,add="+")
        self.bind("<Control-A>",self.select_all_symbols)
        self.bind("<Control-p>",lambda e:self.show_print_preview())
        self.bind("<Control-P>",lambda e:self.show_print_preview())
        self.bind("<Control-s>",lambda e:self.save_project(use_existing=True))
        self.bind("<Control-S>",lambda e:self.save_project(use_existing=True))
        self.bind("<Control-o>",lambda e:self.open_file())
        self.bind("<Control-O>",lambda e:self.open_file())
        self.bind("<Home>",lambda e:self.fit_view())
        self.protocol("WM_DELETE_WINDOW",self.on_close)
        for var in (self.snap_to_symbols,self.snap_to_walls):
            try:var.trace_add("write",lambda *_:self._update_snap_status())
            except Exception:pass
        self._update_mode_status(); self._update_snap_status()
        self.after(350,self._check_recovery)
        self._autosave_job=self.after(AUTOSAVE_INTERVAL_MS,self._autosave_tick)

    # ------------------------------------------------------ APP / UX STATE
    def _set_dirty(self, dirty=True):
        self._dirty=bool(dirty)
        name=Path(self.project_path or self.file_path).name if (self.project_path or self.file_path) else ""
        suffix=f" – {name}" if name else ""
        star=" *" if self._dirty else ""
        self.title(f"{APP_NAME} {APP_VERSION}{suffix}{star}")

    def _project_data(self):
        self.sync_cable_connections()
        return {
            "version":APP_VERSION,"source_file":self.file_path,
            "custom_symbols":custom_symbol_records(),
            "placements":[asdict(x) for x in self.placements],
            "cables":[asdict(x) for x in self.cables],
            "texts":[asdict(x) for x in self.texts],
            "layer_visibility":self.layer_visibility,
            "default_symbol_size":float(self.default_symbol_size),
            "spot_default_size":float(self.spot_default_size),
            "default_symbol_line_width":float(self.default_symbol_line_width),
            "symbol_color_defaults":self.symbol_color_defaults,
            "cable_type":self.cable_type.get(),"cable_spec":self.cable_spec.get(),
            "cable_line_width":float(self.cable_line_width.get()),"cable_label":self.cable_label.get(),
            "cable_auto_label":bool(self.cable_auto_label.get()),"cable_orthogonal":bool(self.cable_orthogonal.get()),
            "continuous_placement":bool(self.continuous_placement.get()),
            "default_text_height":float(self.default_text_height),"default_text_color":self.default_text_color,
            "annotation_style":self.annotation_style.get(),"annotation_font_size":int(self.annotation_font_size.get()),
            "annotation_auto_place":bool(self.annotation_auto_place.get()),
            "paper_size":self.paper_size.get(),"page_orientation":self.page_orientation.get(),"print_scope":self.print_scope.get(),
        }

    def _save_runtime_settings(self):
        data=load_app_settings()
        # Fjern 0.19.0's eksperimentelle temaindstilling, så programmet altid starter lyst.
        data.pop("theme_mode",None)
        data.update({
            "window_geometry":self.geometry(),"symbol_category":self.symbol_category.get(),
            "custom_symbols":custom_symbol_records(),
            "combo_templates":list(self.combo_templates),
            "favorite_symbols":list(self.favorite_symbols),"recent_symbols":list(self.recent_symbols[:8]),
            "recent_projects":list(self.recent_projects[:MAX_RECENT_PROJECTS]),
            "snap_to_symbols":bool(self.snap_to_symbols.get()),"snap_to_walls":bool(self.snap_to_walls.get()),
            "snap_symbols_together":bool(self.snap_to_symbols.get()),"snap_0193_migrated":True,
            "continuous_placement":bool(self.continuous_placement.get()),
            "spot_default_size":float(self.spot_default_size),
            "annotation_style":self.annotation_style.get(),"annotation_font_size":int(self.annotation_font_size.get()),
            "annotation_auto_place":bool(self.annotation_auto_place.get()),
            "paper_size":self.paper_size.get(),"page_orientation":self.page_orientation.get(),"print_scope":self.print_scope.get(),
            "show_annotations":bool(self.show_annotations.get()),"show_associations":bool(self.show_associations.get()),
            "show_cables_overlay":bool(self.show_cables_overlay.get()),
        })
        try:
            save_app_settings(data); self.app_settings=data
        except Exception:
            pass

    def _add_recent_project(self,path):
        if not path:return
        value=str(Path(path))
        self.recent_projects=[x for x in self.recent_projects if os.path.normcase(x)!=os.path.normcase(value)]
        self.recent_projects.insert(0,value); self.recent_projects=self.recent_projects[:MAX_RECENT_PROJECTS]
        self._save_runtime_settings(); self._rebuild_recent_projects_menu()

    def _rebuild_recent_projects_menu(self):
        if not hasattr(self,"recent_projects_menu"):return
        m=self.recent_projects_menu; m.delete(0,"end")
        existing=[x for x in self.recent_projects if Path(x).is_file()]
        if existing:
            for path in existing:
                pp=Path(path); label=f"{pp.name}  —  {pp.parent.name}" if pp.parent.name else pp.name
                m.add_command(label=label,command=lambda p=path:self._open_project_path(p))
            m.add_separator(); m.add_command(label="Ryd listen",command=self._clear_recent_projects)
            try:self.recent_projects_button.configure(state="normal")
            except Exception:pass
        else:
            m.add_command(label="Ingen seneste projekter",state="disabled")
            try:self.recent_projects_button.configure(state="disabled")
            except Exception:pass

    def _clear_recent_projects(self):
        self.recent_projects=[]; self._save_runtime_settings(); self._rebuild_recent_projects_menu()

    def _write_recovery(self):
        if not self.doc or not self.file_path:return False
        data=self._project_data(); data["_recovery_project_path"]=self.project_path; data["_recovery_saved_at"]=time.time()
        path=_recovery_file(); path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_suffix(".tmp"); tmp.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8"); tmp.replace(path)
        self.autosave_status_var.set("Autosave: "+time.strftime("%H:%M")); return True

    def _clear_recovery(self):
        try:_recovery_file().unlink(missing_ok=True)
        except Exception:pass

    def _autosave_tick(self):
        try:
            if self._dirty and self.doc:self._write_recovery()
        except Exception:
            self.autosave_status_var.set("Autosave: fejl")
        finally:
            try:self._autosave_job=self.after(AUTOSAVE_INTERVAL_MS,self._autosave_tick)
            except Exception:self._autosave_job=None

    def _check_recovery(self):
        path=_recovery_file()
        if not path.is_file() or self.doc:return
        try:
            data=json.loads(path.read_text(encoding="utf-8")); src=data.get("source_file")
            stamp=float(data.get("_recovery_saved_at",path.stat().st_mtime)); when=time.strftime("%d-%m-%Y %H:%M",time.localtime(stamp))
            if not src or not Path(src).is_file():
                self._clear_recovery(); return
        except Exception:
            self._clear_recovery(); return
        if messagebox.askyesno("Gendan automatisk gemt arbejde",f"Der blev fundet automatisk gemt arbejde fra {when}.\n\nVil du gendanne det?"):
            self._open_project_path(str(path),recovery=True)
        else:self._clear_recovery()

    def _confirm_discard_changes(self):
        if not self._dirty:return True
        choice=messagebox.askyesnocancel("Ikke-gemte ændringer","Der er ikke-gemte ændringer. Vil du gemme projektet først?")
        if choice is None:return False
        if choice is True:return bool(self.save_project(use_existing=True))
        self._clear_recovery(); return True

    def on_close(self):
        if not self._confirm_discard_changes():return
        self._save_runtime_settings(); self._clear_recovery()
        if self._autosave_job is not None:
            try:self.after_cancel(self._autosave_job)
            except Exception:pass
        self.destroy()

    def _update_mode_status(self):
        labels={"select":"Vælg / flyt","place":f"Placér {self.symbol_name.get()}","cable":"Tegn kabel/ledning","text":"Placér tekst","associate":"Tilknyt lys","spot_line":"Spot-række","spot_rect":"Spot-rektangel","spot_parent":"Tilknyt spots"}
        self.mode_status_var.set("Tilstand: "+labels.get(self.mode,self.mode))
        self._update_canvas_cursor()

    def _snap_live_label(self,kind=""):
        k=str(kind or "").lower()
        if "symbol" in k:return "SYMBOL"
        if "væg" in k or "vaeg" in k or "cad" in k:return "VÆG"
        return ""

    def _set_snap_live(self,kind=""):
        self.snap_live_kind=self._snap_live_label(kind)
        self._update_snap_status()

    def _update_snap_status(self):
        parts=[]
        if self.snap_to_walls.get():parts.append("væg")
        if self.snap_symbols_together.get() or self.snap_to_symbols.get():parts.append("symbol")
        text="Snap: "+(" + ".join(parts) if parts else "FRA")
        if getattr(self,"_alt_down",False):
            text+=" · MIDLERTIDIGT FRA (Alt)"
        elif getattr(self,"snap_live_kind",""):
            text+=f" · Nu: {self.snap_live_kind}"
        else:
            text+=" · Alt = fra midlertidigt"
        self.snap_status_var.set(text)
        self._save_runtime_settings() if hasattr(self,"canvas") else None

    def _update_canvas_cursor(self,snap_kind=""):
        if not hasattr(self,"canvas"):return
        cursor="arrow"
        if snap_kind and snap_kind!="fri":cursor="hand2"
        elif self.dragging or self.pan_last:cursor="fleur"
        elif self.mode in ("place","cable","associate"):cursor="crosshair"
        elif self.mode=="text":cursor="xterm"
        try:self.canvas.configure(cursor=cursor)
        except tk.TclError:pass

    def _toggle_overlays(self):
        self._save_runtime_settings()
        if self.doc:self.redraw_placements()

    # --------------------------------------------------------------- THEME
    def _theme_color(self, key: str) -> str:
        name=self.theme_mode.get() if hasattr(self,"theme_mode") and self.theme_mode.get() in THEMES else DEFAULT_THEME
        return THEMES[name].get(key,THEMES[DEFAULT_THEME].get(key,"#000000"))

    def _configure_styles(self):
        self.ui_style=ttk.Style(self)
        try:self.ui_style.theme_use("clam")
        except tk.TclError:pass
        self._configure_theme_styles()

    def _configure_theme_styles(self):
        if not hasattr(self,"ui_style"):return
        p=THEMES[self.theme_mode.get() if self.theme_mode.get() in THEMES else DEFAULT_THEME]; st=self.ui_style
        st.configure("TFrame",background=p["panel"])
        st.configure("Toolbar.TFrame",background=p["surface"],relief="flat",borderwidth=0)
        st.configure("Status.TFrame",background=p["surface_alt"])
        st.configure("TLabel",background=p["panel"],foreground=p["text"],font=("Segoe UI",9))
        st.configure("Toolbar.TLabel",background=p["surface"],foreground=p["text"],font=("Segoe UI",9))
        st.configure("ToolbarTitle.TLabel",background=p["surface"],foreground=p["text"],font=("Segoe UI Semibold",14))
        st.configure("Section.TLabel",background=p["panel"],foreground=p["text"],font=("Segoe UI Semibold",10))
        st.configure("Status.TLabel",background=p["surface_alt"],foreground=p["text"],font=("Segoe UI",9))
        st.configure("Muted.TLabel",background=p["panel"],foreground=p["muted"],font=("Segoe UI",9))
        st.configure("MutedToolbar.TLabel",background=p["surface"],foreground=p["muted"],font=("Segoe UI",8))
        st.configure("Accent.TLabel",background=p["panel"],foreground=p["accent"])
        st.configure("AccentStatus.TLabel",background=p["surface_alt"],foreground=p["accent"])
        st.configure("Success.TLabel",background=p["panel"],foreground=p["success"])
        st.configure("SuccessStatus.TLabel",background=p["surface_alt"],foreground=p["success"])
        st.configure("Title.TLabel",background=p["panel"],foreground=p["text"],font=("Segoe UI Semibold",16))
        button_bg=p.get("button",p["surface_alt"]); button_hover=p.get("button_hover",p["accent_soft"]); button_pressed=p.get("button_pressed",p["accent_soft"])
        st.configure("TButton",background=button_bg,foreground=p["text"],font=("Segoe UI Semibold",9),padding=(10,6),borderwidth=1,bordercolor=p["border"],lightcolor=p["border"],darkcolor=p["border"],relief="flat")
        st.map("TButton",background=[("active",button_hover),("pressed",button_pressed)],foreground=[("disabled",p["muted"])],bordercolor=[("active",p["accent"]),("focus",p["accent"]),("pressed",p["accent"])])
        st.configure("Primary.TButton",background=p["accent"],foreground="#ffffff",font=("Segoe UI Semibold",9),padding=(11,6),borderwidth=1,bordercolor=p["accent"],lightcolor=p["accent"],darkcolor=p["accent"],relief="flat")
        st.map("Primary.TButton",background=[("active","#1d4ed8"),("pressed","#1e40af")],foreground=[("disabled","#dbe4f5")])
        st.configure("Toolbar.TButton",background=button_bg,foreground=p["text"],font=("Segoe UI Semibold",9),padding=(10,6),borderwidth=1,bordercolor=p["border"],lightcolor=p["border"],darkcolor=p["border"],relief="flat")
        st.map("Toolbar.TButton",background=[("active",button_hover),("pressed",button_pressed)],bordercolor=[("active",p["accent"]),("focus",p["accent"]),("pressed",p["accent"])],foreground=[("disabled",p["muted"])])
        st.configure("TCheckbutton",background=p["panel"],foreground=p["text"],font=("Segoe UI",9)); st.map("TCheckbutton",background=[("active",p["panel"])])
        st.configure("Toolbar.TCheckbutton",background=p["surface"],foreground=p["text"],font=("Segoe UI",9)); st.map("Toolbar.TCheckbutton",background=[("active",p["surface"])])
        st.configure("TEntry",fieldbackground=p["surface"],foreground=p["text"],insertcolor=p["text"],bordercolor=p["border"],padding=(7,5),font=("Segoe UI",9))
        st.configure("TCombobox",fieldbackground=p["surface"],background=p["surface"],foreground=p["text"],arrowcolor=p["text"],bordercolor=p["border"],padding=(6,4),font=("Segoe UI",9))
        st.map("TCombobox",fieldbackground=[("readonly",p["surface"])],foreground=[("readonly",p["text"])],selectbackground=[("readonly",p["accent_soft"])],selectforeground=[("readonly",p["text"])])
        st.configure("TLabelframe",background=p["panel"],bordercolor=p["border"],relief="flat",borderwidth=1); st.configure("TLabelframe.Label",background=p["panel"],foreground=p["text"])
        st.configure("Toolbar.TLabelframe",background=p["surface"],bordercolor=p["border"]); st.configure("Toolbar.TLabelframe.Label",background=p["surface"],foreground=p["text"])
        st.configure("TMenubutton",background=button_bg,foreground=p["text"],bordercolor=p["border"],lightcolor=p["border"],darkcolor=p["border"],padding=(10,6),font=("Segoe UI Semibold",9),borderwidth=1,relief="flat"); st.map("TMenubutton",background=[("active",button_hover),("pressed",button_pressed)],bordercolor=[("active",p["accent"]),("focus",p["accent"]),("pressed",p["accent"])])
        st.configure("Vertical.TScrollbar",background=p["surface"],troughcolor=p["panel"],bordercolor=p["border"],arrowcolor=p["text"])

    def _theme_classic_widgets(self, widget=None):
        p=THEMES[self.theme_mode.get() if self.theme_mode.get() in THEMES else DEFAULT_THEME]
        widget=widget or self
        for child in widget.winfo_children():
            try:
                if isinstance(child,tk.Menu):
                    child.configure(background=p["surface"],foreground=p["text"],activebackground=p["accent_soft"],activeforeground=p["text"],selectcolor=p["accent"])
                elif isinstance(child,tk.Canvas):
                    if child is getattr(self,"canvas",None):child.configure(background=p["canvas"])
                    elif child is getattr(self,"sidebar_canvas",None):child.configure(background=p["panel"])
                    elif child is getattr(self,"_print_preview_canvas",None):child.configure(background=p["preview_bg"])
                    else:child.configure(background=p["surface"])
                elif isinstance(child,tk.Frame):child.configure(background=p["surface_alt"])
                elif isinstance(child,tk.Label):child.configure(background=p["surface_alt"],foreground=p["text"])
            except tk.TclError:pass
            self._theme_classic_widgets(child)

    def _apply_theme(self, redraw=True):
        if self.theme_mode.get() not in THEME_MODES:self.theme_mode.set(DEFAULT_THEME)
        p=THEMES[self.theme_mode.get()]
        try:self.configure(background=p["root"])
        except tk.TclError:pass
        self._configure_theme_styles()
        # Option-databasen holder højrekliksmenuer visuelt ens med resten af GUI'en.
        for pattern,value in (("*Menu.background",p["surface"]),("*Menu.foreground",p["text"]),("*Menu.activeBackground",p["accent_soft"]),("*Menu.activeForeground",p["text"])):
            try:self.option_add(pattern,value)
            except tk.TclError:pass
        self._theme_classic_widgets()
        try:self._rebuild_quick_symbols(); self._rebuild_symbol_palette()
        except Exception:pass
        if redraw and hasattr(self,"canvas"):
            if self.doc:self.rebuild_scene()
            else:
                self.canvas.delete("all"); self.canvas.create_text(max(1,self.canvas.winfo_width())/2,max(1,self.canvas.winfo_height())/2,text="Åbn en DWG- eller DXF-plantegning",fill=p["muted"],font=("Segoe UI",18),tags="placeholder")
        self._save_runtime_settings() if hasattr(self,"paper_size") else None
        try:
            if self.print_preview_window is not None and self.print_preview_window.winfo_exists():self._schedule_print_preview_redraw(0)
        except tk.TclError:
            self.print_preview_window=None; self._print_preview_canvas=None; self._print_preview_info_var=None

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        self.columnconfigure(1,weight=1); self.rowconfigure(1,weight=1)

        # 0.23.3: moderne, samlet topbar. Kontrollerne er opdelt i tre
        # kompakte linjer, så hele værktøjslinjen også fungerer på små skærme.
        appbar=ttk.Frame(self,padding=(12,7,12,7),style="Toolbar.TFrame")
        appbar.grid(row=0,column=0,columnspan=2,sticky="ew")
        appbar.columnconfigure(0,weight=1)

        fileline=ttk.Frame(appbar,style="Toolbar.TFrame")
        fileline.grid(row=0,column=0,sticky="ew")
        ttk.Label(fileline,text="Elplan",style="ToolbarTitle.TLabel").pack(side="left",padx=(0,5))
        ttk.Label(fileline,text=f"v{APP_VERSION}",style="MutedToolbar.TLabel").pack(side="left",padx=(0,14))
        self.open_drawing_button=ttk.Menubutton(fileline,text="Åbn")
        open_menu=tk.Menu(self.open_drawing_button,tearoff=False)
        open_menu.add_command(label="Åbn DWG/DXF…",command=self.open_file)
        open_menu.add_command(label="Åbn projekt…",command=self.open_project)
        self.open_drawing_button.configure(menu=open_menu)
        self.open_drawing_button.pack(side="left",padx=(0,5))
        self.save_project_button=ttk.Button(fileline,text="Gem",command=self.save_project,style="Toolbar.TButton")
        self.save_project_button.pack(side="left",padx=(0,5))
        self.recent_projects_button=ttk.Menubutton(fileline,text="Seneste")
        self.recent_projects_menu=tk.Menu(self.recent_projects_button,tearoff=False); self.recent_projects_button.configure(menu=self.recent_projects_menu)
        self.recent_projects_button.pack(side="left",padx=(0,12)); self._rebuild_recent_projects_menu()
        sep1=ttk.Separator(fileline,orient="vertical"); sep1.pack(side="left",fill="y",padx=(0,10),pady=2)
        self.undo_button=ttk.Button(fileline,text="Fortryd",command=self.undo,state="disabled",style="Toolbar.TButton")
        self.undo_button.pack(side="left",padx=(0,3))
        self.redo_button=ttk.Button(fileline,text="Gentag",command=self.redo,state="disabled",style="Toolbar.TButton")
        self.redo_button.pack(side="left")

        outputline=ttk.Frame(appbar,style="Toolbar.TFrame")
        outputline.grid(row=1,column=0,sticky="ew",pady=(5,0))
        ttk.Label(outputline,text="OUTPUT",style="MutedToolbar.TLabel").pack(side="left",padx=(0,8))
        self.preview_button=ttk.Button(outputline,text="Forhåndsvis",command=self.show_print_preview,style="Toolbar.TButton")
        self.preview_button.pack(side="left",padx=(0,4))
        self.pdf_button=ttk.Button(outputline,text="PDF",command=self.export_pdf,style="Primary.TButton")
        self.pdf_button.pack(side="left",padx=(0,4))
        self.print_button=ttk.Button(outputline,text="Udskriv",command=self.print_plan,style="Toolbar.TButton")
        self.print_button.pack(side="left",padx=(0,4))
        self.fit_button=ttk.Button(outputline,text="Tilpas visning",command=self.fit_view,style="Toolbar.TButton")
        self.fit_button.pack(side="left",padx=(0,4))
        more_btn=ttk.Menubutton(outputline,text="Mere")
        more_menu=tk.Menu(more_btn,tearoff=False)
        more_menu.add_command(label="Eksportér DXF…",command=self.export_dxf)
        more_menu.add_command(label="Eksportér DWG…",command=self.export_dwg)
        more_menu.add_separator()
        more_menu.add_command(label="Vis / skjul lag…",command=self.show_layers_window)
        more_menu.add_command(label="DWG / ODA-indstillinger…",command=self.show_oda_settings)
        more_btn.configure(menu=more_menu); more_btn.pack(side="left")

        # Print-/visningsblokken fra tegnefladen ligger nu permanent i topbaren.
        settings=ttk.Frame(appbar,style="Toolbar.TFrame")
        settings.grid(row=2,column=0,sticky="ew",pady=(6,0))
        ttk.Label(settings,text="SIDE",style="MutedToolbar.TLabel").pack(side="left",padx=(0,7))
        self.paper_combo=ttk.Combobox(settings,textvariable=self.paper_size,values=["A4","A3"],state="readonly",width=4)
        self.paper_combo.pack(side="left",padx=(0,4)); self.paper_combo.bind("<<ComboboxSelected>>",lambda e:self._save_runtime_settings())
        self.orientation_combo=ttk.Combobox(settings,textvariable=self.page_orientation,values=["Auto","Portræt","Landskab"],state="readonly",width=9)
        self.orientation_combo.pack(side="left",padx=(0,4)); self.orientation_combo.bind("<<ComboboxSelected>>",lambda e:self._save_runtime_settings())
        self.scope_combo=ttk.Combobox(settings,textvariable=self.print_scope,values=list(PRINT_SCOPES),state="readonly",width=13)
        self.scope_combo.pack(side="left",padx=(0,14)); self.scope_combo.bind("<<ComboboxSelected>>",lambda e:self._save_runtime_settings())
        sep2=ttk.Separator(settings,orient="vertical"); sep2.pack(side="left",fill="y",padx=(0,12),pady=2)
        ttk.Label(settings,text="VIS",style="MutedToolbar.TLabel").pack(side="left",padx=(0,5))
        ttk.Checkbutton(settings,text="Mærkning",style="Toolbar.TCheckbutton",variable=self.show_annotations,command=self._toggle_overlays).pack(side="left")
        ttk.Checkbutton(settings,text="Tilhør.",style="Toolbar.TCheckbutton",variable=self.show_associations,command=self._toggle_overlays).pack(side="left",padx=(5,0))
        ttk.Checkbutton(settings,text="Kabler",style="Toolbar.TCheckbutton",variable=self.show_cables_overlay,command=self._toggle_overlays).pack(side="left",padx=(5,0))
        self.view_toolbar=settings  # kompatibilitet med ældre GUI-tests/plugins
        self.appbar=appbar

        # Responsivt sidepanel: egenskaberne kan rulles, mens de vigtigste
        # symbolhandlinger er fastgjort nederst. Det gør GUI'en anvendelig på
        # mindre skærme og ved høj Windows-DPI skalering.
        sidebar_outer=ttk.Frame(self,padding=(8,8,5,8))
        sidebar_outer.grid(row=1,column=0,sticky="nsew")
        sidebar_outer.columnconfigure(0,weight=1); sidebar_outer.rowconfigure(1,weight=1)

        sidebar_header=ttk.Frame(sidebar_outer)
        sidebar_header.grid(row=0,column=0,sticky="ew",pady=(0,6))
        ttk.Label(sidebar_header,text="Værktøjer",style="Section.TLabel").pack(side="left")
        ttk.Label(sidebar_header,text="Rul for flere",style="Muted.TLabel").pack(side="right")

        scroll_host=ttk.Frame(sidebar_outer)
        scroll_host.grid(row=1,column=0,sticky="nsew")
        scroll_host.columnconfigure(0,weight=1); scroll_host.rowconfigure(0,weight=1)
        self.sidebar_canvas=tk.Canvas(scroll_host,width=300,highlightthickness=0,borderwidth=0,background=self._theme_color("panel"))
        self.sidebar_scrollbar=ttk.Scrollbar(scroll_host,orient="vertical",command=self.sidebar_canvas.yview)
        self.sidebar_canvas.configure(yscrollcommand=self.sidebar_scrollbar.set)
        self.sidebar_canvas.grid(row=0,column=0,sticky="nsew")
        self.sidebar_scrollbar.grid(row=0,column=1,sticky="ns")
        sidebar=ttk.Frame(self.sidebar_canvas,padding=(2,0,6,5))
        self.sidebar_window=self.sidebar_canvas.create_window((0,0),window=sidebar,anchor="nw")

        def sync_scrollregion(event=None):
            self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all"))
        def sync_sidebar_width(event):
            # Undgå vandret scrollbar: indholdet følger altid den synlige bredde.
            self.sidebar_canvas.itemconfigure(self.sidebar_window,width=max(230,event.width))
        sidebar.bind("<Configure>",sync_scrollregion)
        self.sidebar_canvas.bind("<Configure>",sync_sidebar_width)

        project_status=ttk.Frame(sidebar)
        project_status.pack(fill="x",pady=(0,7))
        ttk.Label(project_status,textvariable=self.layer_summary_var,style="Muted.TLabel").pack(anchor="w")
        ttk.Label(project_status,textvariable=self.vector_status_var,style="Success.TLabel").pack(anchor="w",pady=(1,0))

        # Grafisk symbolpalette: vælg kategori, klik derefter direkte på et
        # symbolkort. Et klik starter placering med det samme, så dropdown +
        # ekstra "Placér"-klik ikke længere er nødvendigt.
        palette_box=ttk.LabelFrame(sidebar,text="Symbolbibliotek",padding=6)
        self.palette_box=palette_box
        palette_box.pack(fill="x",pady=(0,7))

        # Hurtigvalg samler favoritter og senest anvendte symboler. Det holder
        # de daglige symboler ét klik væk uden at introducere flere menuer.
        self.quick_symbols_box=ttk.LabelFrame(palette_box,text="Hurtigvalg",padding=4)
        self.quick_symbols_box.pack(fill="x",pady=(0,6))
        self.quick_symbols_frame=tk.Frame(self.quick_symbols_box,background=self.cget("background"))
        self.quick_symbols_frame.pack(fill="x")
        ttk.Label(self.quick_symbols_box,text="★ favoritter først · højreklik et symbol for at fastgøre/fjerne",style="Muted.TLabel",wraplength=235).pack(anchor="w",pady=(3,0))
        self._rebuild_quick_symbols()

        palette_head=ttk.Frame(palette_box); palette_head.pack(fill="x")
        ttk.Label(palette_head,text="Kategori").pack(side="left")
        cat=ttk.Combobox(palette_head,textvariable=self.symbol_category,values=list(SYMBOL_GROUPS),state="readonly",width=19)
        cat.pack(side="right",fill="x",expand=True,padx=(6,0)); cat.bind("<<ComboboxSelected>>",self.on_symbol_category_change)
        ttk.Label(palette_box,text="Klik på et symbol for at placere. Esc afslutter.",style="Muted.TLabel",wraplength=245).pack(anchor="w",pady=(4,4))
        self.symbol_configurator_button=ttk.Button(palette_box,text="Konfigurér kombisymbol…",command=self.show_symbol_configurator,style="Toolbar.TButton")
        self.symbol_configurator_button.pack(fill="x",pady=(0,5))
        self.palette_frame=tk.Frame(palette_box,background=self.cget("background"))
        self.palette_frame.pack(fill="x")
        ttk.Checkbutton(palette_box,text="Placér flere af samme symbol",variable=self.continuous_placement).pack(anchor="w",pady=(5,0))

        self._rebuild_symbol_palette()
        self._update_symbol_configurator_visibility()

        # Egenskaberne er samlet i én tydelig boks. Titlen skifter mellem
        # standardværdier for nye symboler og det konkret valgte objekt.
        self.properties_frame=ttk.LabelFrame(sidebar,text="Egenskaber – nye symboler",padding=6)
        self.properties_frame.pack(fill="x",pady=(0,6))
        props=self.properties_frame
        self.properties_hint_var=tk.StringVar(value="Bruges til nye symboler")
        ttk.Label(props,textvariable=self.properties_hint_var,style="Muted.TLabel",wraplength=235).pack(anchor="w",pady=(0,5))
        ttk.Label(props,textvariable=self.symbol_layer_var,style="Muted.TLabel").pack(anchor="w",pady=(0,4))

        ttk.Label(props,text="Størrelse [tegneenheder]").pack(anchor="w")
        self.symbol_size_entry=ttk.Entry(props,textvariable=self.symbol_size)
        self.symbol_size_entry.pack(fill="x",pady=(2,4))
        self.symbol_size_entry.bind("<Return>",lambda e:self.apply_symbol_properties(show_error=True))
        self.symbol_size_entry.bind("<FocusOut>",lambda e:self.apply_symbol_properties())
        ttk.Label(props,text="Linjetykkelse [mm]").pack(anchor="w")
        self.symbol_line_width_entry=ttk.Entry(props,textvariable=self.symbol_line_width)
        self.symbol_line_width_entry.pack(fill="x",pady=(2,4))
        self.symbol_line_width_entry.bind("<Return>",lambda e:self.apply_symbol_properties(show_error=True))
        self.symbol_line_width_entry.bind("<FocusOut>",lambda e:self.apply_symbol_properties())
        ttk.Label(props,text="Farve").pack(anchor="w")
        color_row=ttk.Frame(props); color_row.pack(fill="x",pady=(2,5))
        self.symbol_color_swatch=tk.Label(color_row,textvariable=self.symbol_color,width=11,relief="sunken",bd=1)
        self.symbol_color_swatch.pack(side="left",fill="x",expand=True)
        ttk.Button(color_row,text="Vælg…",command=self.choose_symbol_color).pack(side="left",padx=(4,0))
        self._update_color_swatch()

        ttk.Label(props,text="Rotation [°]").pack(anchor="w")
        rot=ttk.Combobox(props,textvariable=self.rotation,values=[0,45,90,135,180,225,270,315],width=10)
        rot.pack(fill="x",pady=(2,5)); rot.bind("<<ComboboxSelected>>",lambda e:self.apply_symbol_properties())
        ttk.Label(props,text="Mærkning (valgfri)").pack(anchor="w")
        label_entry=ttk.Entry(props,textvariable=self.label_var); label_entry.pack(fill="x",pady=(2,5)); label_entry.bind("<FocusOut>",lambda e:self.apply_symbol_properties())
        ttk.Label(props,text="Gruppe/kreds (valgfri)").pack(anchor="w")
        group_entry=ttk.Entry(props,textvariable=self.group_var); group_entry.pack(fill="x",pady=(2,4)); group_entry.bind("<FocusOut>",lambda e:self.apply_symbol_properties())

        self.combo_properties_frame=ttk.LabelFrame(props,text="Kombi-mærkning",padding=5)
        ttk.Label(self.combo_properties_frame,text="Mærkningstype").pack(anchor="w")
        combo_mode=ttk.Combobox(self.combo_properties_frame,textvariable=self.combo_label_mode,values=list(COMBO_LABEL_MODES),state="readonly")
        combo_mode.pack(fill="x",pady=(2,4)); combo_mode.bind("<<ComboboxSelected>>",self._on_combo_label_mode_change)
        self.combo_split_frame=ttk.Frame(self.combo_properties_frame)
        self.combo_split_frame.pack(fill="x")
        ttk.Label(self.combo_split_frame,text="Afbryder(e) – mærkning").pack(anchor="w")
        e=ttk.Entry(self.combo_split_frame,textvariable=self.combo_switch_label); e.pack(fill="x",pady=(1,3)); e.bind("<FocusOut>",lambda ev:self.apply_symbol_properties())
        ttk.Label(self.combo_split_frame,text="Afbryder(e) – gruppe/kreds").pack(anchor="w")
        e=ttk.Entry(self.combo_split_frame,textvariable=self.combo_switch_group); e.pack(fill="x",pady=(1,3)); e.bind("<FocusOut>",lambda ev:self.apply_symbol_properties())
        ttk.Label(self.combo_split_frame,text="Stikkontakt – mærkning").pack(anchor="w")
        e=ttk.Entry(self.combo_split_frame,textvariable=self.combo_socket_label); e.pack(fill="x",pady=(1,3)); e.bind("<FocusOut>",lambda ev:self.apply_symbol_properties())
        ttk.Label(self.combo_split_frame,text="Stikkontakt – gruppe/kreds").pack(anchor="w")
        e=ttk.Entry(self.combo_split_frame,textvariable=self.combo_socket_group); e.pack(fill="x",pady=(1,2)); e.bind("<FocusOut>",lambda ev:self.apply_symbol_properties())
        self.combo_hint=ttk.Label(self.combo_properties_frame,text="Fælles bruger Mærkning/Gruppe ovenfor.",style="Muted.TLabel",wraplength=220)
        self.combo_hint.pack(anchor="w",pady=(3,0))

        self.association_heading=ttk.Label(props,text="Tilhørsforhold afbryder ↔ lys")
        self.association_heading.pack(anchor="w",pady=(2,0))
        self.association_value_label=ttk.Label(props,textvariable=self.association_var,style="Accent.TLabel")
        self.association_value_label.pack(anchor="w",pady=(1,4))
        self.lock_check=ttk.Checkbutton(props,text="Lås valgt symbol",variable=self.symbol_locked,command=self.toggle_selected_lock_from_panel)
        self.lock_check.pack(anchor="w",pady=(1,4))

        snap_box=ttk.Frame(props); snap_box.pack(fill="x",pady=(2,2))
        ttk.Checkbutton(snap_box,text="Snap til vægge",variable=self.snap_to_walls).pack(anchor="w")
        ttk.Checkbutton(snap_box,text="Snap til symboler / forbindelser",variable=self.snap_to_symbols).pack(anchor="w")

        ttk.Label(sidebar,text="Mærkningsvisning").pack(anchor="w")
        anno_row=ttk.Frame(sidebar); anno_row.pack(fill="x",pady=(2,2))
        anno=ttk.Combobox(anno_row,textvariable=self.annotation_style,values=list(ANNOTATION_STYLES),state="readonly",width=14)
        anno.pack(side="left",fill="x",expand=True); anno.bind("<<ComboboxSelected>>",lambda e:(self._save_runtime_settings(),self.redraw_annotations()))
        ttk.Label(anno_row,text="Skrift").pack(side="left",padx=(6,3))
        anno_size=ttk.Combobox(anno_row,textvariable=self.annotation_font_size,values=[7,8,9,10],state="readonly",width=4)
        anno_size.pack(side="left"); anno_size.bind("<<ComboboxSelected>>",lambda e:(self._save_runtime_settings(),self.redraw_annotations()))
        auto_row=ttk.Frame(sidebar); auto_row.pack(fill="x",pady=(1,2))
        ttk.Checkbutton(auto_row,text="Automatisk placering",variable=self.annotation_auto_place,command=lambda:(self._save_runtime_settings(),self.redraw_annotations())).pack(side="left")
        ttk.Label(sidebar,text="Auto placerer mærkningen dér, hvor den dækker mindst.",style="Muted.TLabel",wraplength=235).pack(anchor="w",pady=(0,5))

        # Kabelværktøjer og eksport ligger i det rullende område. De mest brugte
        # symbolhandlinger ligger derimod i den faste quickbar nedenfor.
        cable_row=ttk.Frame(sidebar); cable_row.pack(fill="x",pady=(6,1))
        ttk.Button(cable_row,text="Tegn kabel/ledning",command=self.start_cable_mode).pack(side="left",fill="x",expand=True)
        ttk.Button(cable_row,text="Indstillinger…",command=self.show_cable_settings).pack(side="left",padx=(4,0))
        ttk.Button(sidebar,text="Afslut aktuelt kabel",command=self.finish_cable).pack(fill="x",pady=2)

        ttk.Separator(sidebar).pack(fill="x",pady=7)
        ttk.Label(sidebar,text="Tip: Højreklik giver hurtige handlinger · Dobbeltklik åbner egenskaber · Alt deaktiverer snap midlertidigt.",justify="left",style="Muted.TLabel",wraplength=270).pack(anchor="w",pady=(2,8))

        # Bind musehjulet til alle almindelige widgets i det rullende panel.
        # Entry/Combobox undtages, så hjulet ikke ændrer værdier utilsigtet.
        def sidebar_wheel(event):
            if getattr(event,"delta",0):
                self.sidebar_canvas.yview_scroll(int(-event.delta/120),"units")
            elif getattr(event,"num",None)==4:
                self.sidebar_canvas.yview_scroll(-1,"units")
            elif getattr(event,"num",None)==5:
                self.sidebar_canvas.yview_scroll(1,"units")
            return "break"
        def bind_wheel_tree(widget):
            if not isinstance(widget,(ttk.Entry,ttk.Combobox,tk.Entry)):
                widget.bind("<MouseWheel>",sidebar_wheel,add="+")
                widget.bind("<Button-4>",sidebar_wheel,add="+")
                widget.bind("<Button-5>",sidebar_wheel,add="+")
            for child in widget.winfo_children():
                bind_wheel_tree(child)
        bind_wheel_tree(sidebar)
        self.sidebar_canvas.bind("<MouseWheel>",sidebar_wheel,add="+")
        self.sidebar_canvas.bind("<Button-4>",sidebar_wheel,add="+")
        self.sidebar_canvas.bind("<Button-5>",sidebar_wheel,add="+")

        # Fast handlingspanel: disse knapper kan aldrig rulle ud af skærmen.
        quick=ttk.LabelFrame(sidebar_outer,text="Hurtige handlinger",padding=5)
        quick.grid(row=2,column=0,sticky="ew",pady=(6,0))
        quick.columnconfigure(0,weight=1); quick.columnconfigure(1,weight=1)
        self.place_button=ttk.Button(quick,text="Placér",command=lambda:self.set_mode("place"),style="Primary.TButton")
        self.place_button.grid(row=0,column=0,sticky="ew",padx=(0,2),pady=2)
        self.select_button=ttk.Button(quick,text="Vælg / flyt",command=lambda:self.set_mode("select"))
        self.select_button.grid(row=0,column=1,sticky="ew",padx=(2,0),pady=2)
        self.copy_button=ttk.Button(quick,text="Kopiér",command=self.copy_selected_symbol)
        self.copy_button.grid(row=1,column=0,sticky="ew",padx=(0,2),pady=2)
        self.paste_button=ttk.Button(quick,text="Indsæt",command=self.paste_symbol)
        self.paste_button.grid(row=1,column=1,sticky="ew",padx=(2,0),pady=2)
        self.duplicate_button=ttk.Button(quick,text="Smart duplikér  Ctrl+D",command=self.duplicate_selected)
        self.duplicate_button.grid(row=2,column=0,columnspan=2,sticky="ew",pady=2)
        self.rotate_button=ttk.Button(quick,text="Rotér +90°",command=self.rotate_selected)
        self.rotate_button.grid(row=3,column=0,sticky="ew",padx=(0,2),pady=2)
        self.delete_button=ttk.Button(quick,text="Slet",command=self.delete_selected)
        self.delete_button.grid(row=3,column=1,sticky="ew",padx=(2,0),pady=2)
        self.associate_button=ttk.Button(quick,text="Tilknyt lys…",command=self.start_association_mode,state="disabled")
        self.associate_button.grid(row=4,column=0,sticky="ew",padx=(0,2),pady=(4,0))
        self.clear_association_button=ttk.Button(quick,text="Ryd tilhør.",command=self.clear_selected_associations,state="disabled")
        self.clear_association_button.grid(row=4,column=1,sticky="ew",padx=(2,0),pady=(4,0))
        self.text_button=ttk.Button(quick,text="Tekst…",command=self.start_text_tool)
        self.text_button.grid(row=5,column=0,sticky="ew",padx=(0,2),pady=(4,0))
        self.cable_button=ttk.Button(quick,text="Tegn kabel",command=self.start_cable_mode)
        self.cable_button.grid(row=5,column=1,sticky="ew",padx=(2,0),pady=(4,0))
        self.spot_row_button=ttk.Button(quick,text="Spot-række…",command=self.start_spot_row_tool)
        self.spot_row_button.grid(row=6,column=0,sticky="ew",padx=(0,2),pady=(4,0))
        self.spot_rect_button=ttk.Button(quick,text="Spot-rektangel…",command=self.start_spot_rect_tool)
        self.spot_rect_button.grid(row=6,column=1,sticky="ew",padx=(2,0),pady=(4,0))
        spot_size_row=ttk.Frame(quick); spot_size_row.grid(row=7,column=0,columnspan=2,sticky="ew",pady=(5,0))
        ttk.Label(spot_size_row,text="Spotstørrelse").pack(side="left")
        ttk.Button(spot_size_row,text="−",width=3,command=lambda:self.adjust_spot_size(.90)).pack(side="left",padx=(6,2))
        self.spot_size_combo=ttk.Combobox(spot_size_row,textvariable=self.spot_size_var,values=[75,100,125,150,175,200,225,250,300,350,400,500],width=7)
        self.spot_size_combo.pack(side="left",fill="x",expand=True)
        self.spot_size_combo.bind("<<ComboboxSelected>>",lambda e:self.apply_spot_size_value())
        self.spot_size_combo.bind("<Return>",lambda e:self.apply_spot_size_value())
        self.spot_size_combo.bind("<FocusOut>",lambda e:self.apply_spot_size_value(silent=True))
        ttk.Button(spot_size_row,text="+",width=3,command=lambda:self.adjust_spot_size(1.10)).pack(side="left",padx=(2,0))

        main=ttk.Frame(self); main.grid(row=1,column=1,sticky="nsew"); main.columnconfigure(0,weight=1); main.rowconfigure(0,weight=1)
        self.canvas=tk.Canvas(main,background=self._theme_color("canvas"),highlightthickness=0,cursor="arrow")
        self.canvas.grid(row=0,column=0,sticky="nsew")

        # Print- og overlaykontrollerne ligger i appbaren; tegnefladen holdes fri.

        # Hover-hjælp vises i statuslinjen i stedet for popups over tegningen.
        def bind_help(widget,message):
            widget.bind("<Enter>",lambda e,m=message:self.status_var.set(m),add="+")
        for widget,message in (
            (self.open_drawing_button,"Åbn en DWG/DXF-tegning eller et gemt Elplan-projekt (Ctrl+O åbner tegning)."),
            (self.save_project_button,"Gem projektet (Ctrl+S)."),
            (self.undo_button,"Fortryd seneste ændring (Ctrl+Z)."),
            (self.redo_button,"Gentag senest fortrudte ændring (Ctrl+Y)."),
            (self.preview_button,"Se den faktiske papirside før PDF eller udskrift (Ctrl+P)."),
            (self.fit_button,"Tilpas den synlige plantegning til tegnefladen (Home)."),
        ): bind_help(widget,message)
        self.canvas.bind("<MouseWheel>",self.on_mousewheel); self.canvas.bind("<ButtonPress-2>",self.pan_start); self.canvas.bind("<B2-Motion>",self.pan_move); self.canvas.bind("<ButtonRelease-2>",self.pan_end)
        # Højreklik på et symbol åbner kontekstmenu; højreklik på tomt område
        # bevarer den hurtige pan-funktion fra tidligere versioner.
        self.canvas.bind("<ButtonPress-3>",self.on_right_click); self.canvas.bind("<B3-Motion>",self.pan_move); self.canvas.bind("<ButtonRelease-3>",self.pan_end)
        self.canvas.bind("<Button-1>",self.left_click); self.canvas.bind("<Double-Button-1>",self.on_double_click); self.canvas.bind("<B1-Motion>",self.left_drag); self.canvas.bind("<ButtonRelease-1>",self.left_release)
        self.canvas.bind("<Motion>",self.on_canvas_motion)
        # Skjult performance-overlay til fejlsøgning/optimering.
        self.bind_all("<Control-Shift-F12>",self.toggle_performance_diagnostics,add="+")
        statusbar=ttk.Frame(main,padding=(8,5),style="Status.TFrame"); statusbar.grid(row=1,column=0,sticky="ew"); statusbar.columnconfigure(0,weight=1)
        ttk.Label(statusbar,textvariable=self.status_var,anchor="w",style="Status.TLabel").grid(row=0,column=0,sticky="ew",padx=(0,10))
        ttk.Label(statusbar,textvariable=self.mode_status_var,style="AccentStatus.TLabel").grid(row=0,column=1,sticky="e",padx=(4,8))
        ttk.Label(statusbar,textvariable=self.snap_status_var,style="Status.TLabel").grid(row=0,column=2,sticky="e",padx=(4,8))
        ttk.Label(statusbar,textvariable=self.autosave_status_var,style="SuccessStatus.TLabel").grid(row=0,column=3,sticky="e")
        self.canvas.create_text(500,350,text="Åbn en DWG- eller DXF-plantegning",fill=self._theme_color("muted"),font=("Segoe UI",18),tags="placeholder")

    def on_symbol_category_change(self,event=None):
        self._save_runtime_settings()
        names=list(SYMBOL_GROUPS.get(self.symbol_category.get(),{}))
        if self.symbol_name.get() not in names and names:
            self.symbol_name.set(names[0])
        self._rebuild_symbol_palette()
        self._update_symbol_configurator_visibility()
        self.on_symbol_name_change()

    def on_symbol_name_change(self,event=None):
        try:
            code=SYMBOLS[self.symbol_name.get()]
            self.symbol_layer_var.set(f"CAD-lag: {symbol_layer(code)}")
            if self.selected_index is None:
                self.symbol_color.set(self.symbol_color_defaults.get(code,DEFAULT_SYMBOL_COLOR))
                self._update_color_swatch()
            self._refresh_palette_selection(); self._update_combo_property_visibility()
            if self.mode=="place":self._update_mode_status()
        except Exception:
            self.symbol_layer_var.set("CAD-lag: —")

    def _valid_selected_indices(self) -> list[int]:
        if not self.selected_indices and self.selected_index is not None and 0<=self.selected_index<len(self.placements):
            self.selected_indices={self.selected_index}
        valid=sorted(i for i in self.selected_indices if 0<=i<len(self.placements))
        self.selected_indices=set(valid)
        if len(valid)==1:self.selected_index=valid[0]
        elif len(valid)!=1:self.selected_index=None
        return valid

    def _clear_symbol_selection(self):
        self.selected_indices.clear(); self.selected_index=None

    def _set_symbol_selection(self, indices, primary=None):
        valid=sorted({int(i) for i in indices if 0<=int(i)<len(self.placements)})
        self.selected_indices=set(valid)
        if len(valid)==1:self.selected_index=valid[0]
        else:self.selected_index=None
        self.selected_cable_index=None; self.selected_text_index=None; self.selected_cable_vertex_index=None
        if len(valid)==1:self._load_selected_symbol_controls()
        else:
            self._restore_default_symbol_controls(); self._update_properties_panel()
        if self.doc:self.redraw_placements()

    def select_all_symbols(self,event=None):
        if event is not None and self._focus_is_text_input():return None
        if not self.doc:return "break" if event is not None else None
        visible=[i for i,p in enumerate(self.placements) if self.layer_visibility.get(symbol_layer(p.symbol),True)]
        self._set_symbol_selection(visible)
        self.status_var.set(f"Valgt {len(visible)} symboler." if visible else "Ingen synlige symboler at vælge.")
        return "break" if event is not None else None

    def _alt_key_down(self,event=None):
        self._alt_down=True; self._update_snap_status()

    def _alt_key_up(self,event=None):
        self._alt_down=False; self._update_snap_status()

    def _alt_focus_out(self,event=None):
        # Undgå at Alt kan hænge fast, hvis fokus skifter mens tasten holdes.
        if self._alt_down:
            self._alt_down=False; self._update_snap_status()

    def _event_alt_pressed(self,event=None) -> bool:
        """Returnér kun den eksplicit sporede Alt-status.

        VIGTIGT: Mouse-event.state bruges bevidst ikke længere. På tværs af
        Windows/Tk-builds kan modifier-bits i museevents være platform-/layout-
        afhængige. Hvis et normalt museevent fejlagtigt blev tolket som Alt,
        blev *hele snapmotoren* bypasset -- hvilket præcis giver symptomet
        "ingen VÆG/SYMBOL feedback og ingen fysisk snap".

        Alt bypass styres nu udelukkende af de faktiske KeyPress/KeyRelease-
        bindings for Alt_L/Alt_R.
        """
        return bool(getattr(self,"_alt_down",False))

    def _draw_symbol_preview(self, canvas: tk.Canvas, code: str) -> None:
        """Tegn et lille vektor-preview direkte med Tk; ingen rasterikoner."""
        canvas.delete("all")
        w=int(canvas.cget("width")); h=int(canvas.cget("height"))
        x1,y1,x2,y2=symbol_local_bbox(code,100.0)
        bw=max(x2-x1,1e-9); bh=max(y2-y1,1e-9)
        scale=min((w-14)/bw,(h-12)/bh)
        cx=(x1+x2)/2.0; cy=(y1+y2)/2.0
        def pt(x,y): return (w/2+(x-cx)*scale, h/2-(y-cy)*scale)
        pen=self._theme_color("text")
        for prim in symbol_primitives(code,100.0):
            typ=prim[0]
            if typ=="line":
                canvas.create_line(*pt(prim[1],prim[2]),*pt(prim[3],prim[4]),fill=pen,width=1.4)
            elif typ=="circle":
                _,x,y,r=prim; sx,sy=pt(x,y); rr=r*scale
                canvas.create_oval(sx-rr,sy-rr,sx+rr,sy+rr,outline=pen,width=1.4)
            elif typ=="arc":
                _,x,y,r,a1,a2=prim; pts=[]; steps=max(10,int(abs(a2-a1)/8))
                for j in range(steps+1):
                    a=math.radians(a1+(a2-a1)*j/steps); pts.extend(pt(x+r*math.cos(a),y+r*math.sin(a)))
                canvas.create_line(*pts,fill=pen,width=1.4)
            elif typ=="polyline":
                pts=[]
                for x,y in prim[1]: pts.extend(pt(x,y))
                if len(pts)>=4: canvas.create_line(*pts,fill=pen,width=1.4)
            elif typ=="text":
                _,x,y,t,hh=prim; sx,sy=pt(x,y)
                fs=max(7,min(14,int(hh*scale*.8)))
                canvas.create_text(sx,sy,text=t,fill=pen,font=("Segoe UI",fs,"bold"))

    def _save_symbol_usage_settings(self):
        try:
            data=load_app_settings()
            data["favorite_symbols"]=list(self.favorite_symbols)
            data["recent_symbols"]=list(self.recent_symbols[:8])
            save_app_settings(data)
        except Exception:
            pass

    def _remember_recent_symbol(self, code: str):
        if code not in SYMBOL_NAMES_BY_CODE:return
        self.recent_symbols=[c for c in self.recent_symbols if c!=code]
        self.recent_symbols.insert(0,code); self.recent_symbols=self.recent_symbols[:8]
        self._save_symbol_usage_settings(); self._rebuild_quick_symbols()

    def toggle_favorite_symbol(self, code: str):
        if code not in SYMBOL_NAMES_BY_CODE:return
        if code in self.favorite_symbols:
            self.favorite_symbols=[c for c in self.favorite_symbols if c!=code]
            state="fjernet fra favoritter"
        else:
            self.favorite_symbols.append(code); state="fastgjort som favorit"
        self._save_symbol_usage_settings(); self._rebuild_quick_symbols(); self._rebuild_symbol_palette()
        self.status_var.set(f"{symbol_display_name(code)}: {state}.")

    def _quick_symbol_codes(self):
        out=[]
        for code in list(self.favorite_symbols)+list(self.recent_symbols):
            if code in SYMBOL_NAMES_BY_CODE and code not in out:out.append(code)
            if len(out)>=6:break
        return out

    def _rebuild_quick_symbols(self):
        if not hasattr(self,"quick_symbols_frame"):return
        for child in self.quick_symbols_frame.winfo_children():child.destroy()
        self.quick_symbol_cards={}
        codes=self._quick_symbol_codes()
        if not codes:
            ttk.Label(self.quick_symbols_frame,text="Dine senest brugte symboler vises her.",style="Muted.TLabel",wraplength=225).grid(row=0,column=0,columnspan=3,sticky="w",pady=2)
            return
        for col in range(3):self.quick_symbols_frame.grid_columnconfigure(col,weight=1,uniform="quick_symbol")
        for i,code in enumerate(codes):
            name=symbol_display_name(code); fav=code in self.favorite_symbols
            surf=self._theme_color("surface_alt"); border=self._theme_color("border"); fg=self._theme_color("text")
            card=tk.Frame(self.quick_symbols_frame,bd=0,highlightthickness=1,highlightbackground=border,background=surf,cursor="hand2")
            card.grid(row=i//3,column=i%3,sticky="nsew",padx=1,pady=1)
            preview=tk.Canvas(card,width=72,height=38,background=self._theme_color("surface"),highlightthickness=0,cursor="hand2")
            preview.pack(fill="x",padx=1,pady=(1,0)); self._draw_symbol_preview(preview,code)
            short=("★ " if fav else "")+name
            label=tk.Label(card,text=short,wraplength=76,justify="center",background=surf,foreground=fg,font=("Segoe UI",7),cursor="hand2")
            label.pack(fill="x",padx=1,pady=(0,2))
            left=lambda e,n=name:self.select_palette_symbol(n)
            right=lambda e,c=code:self.toggle_favorite_symbol(c)
            for widget in (card,preview,label):
                widget.bind("<Button-1>",left); widget.bind("<Button-3>",right)
            self.quick_symbol_cards[code]=(card,preview,label)

    def _rebuild_symbol_palette(self):
        if not hasattr(self,"palette_frame"): return
        for child in self.palette_frame.winfo_children(): child.destroy()
        self.palette_cards={}
        names=list(SYMBOL_GROUPS.get(self.symbol_category.get(),{}))
        for col in range(2): self.palette_frame.grid_columnconfigure(col,weight=1,uniform="palette")
        for i,name in enumerate(names):
            code=SYMBOLS[name]
            surf=self._theme_color("surface_alt"); border=self._theme_color("border"); fg=self._theme_color("text")
            card=tk.Frame(self.palette_frame,bd=0,highlightthickness=2,highlightbackground=border,highlightcolor=border,background=surf,cursor="hand2")
            card.grid(row=i//2,column=i%2,sticky="nsew",padx=2,pady=2)
            preview=tk.Canvas(card,width=112,height=54,background=self._theme_color("surface"),highlightthickness=0,cursor="hand2")
            preview.pack(fill="x",padx=2,pady=(2,0))
            label_text=("★ " if code in self.favorite_symbols else "")+name
            label=tk.Label(card,text=label_text,wraplength=112,justify="center",background=surf,foreground=fg,font=("Segoe UI",8),cursor="hand2")
            label.pack(fill="x",padx=2,pady=(1,3))
            self._draw_symbol_preview(preview,code)
            callback=lambda e,n=name:self.select_palette_symbol(n)
            card.bind("<Button-1>",callback); preview.bind("<Button-1>",callback); label.bind("<Button-1>",callback)
            fav_callback=lambda e,c=code:self.toggle_favorite_symbol(c)
            card.bind("<Button-3>",fav_callback); preview.bind("<Button-3>",fav_callback); label.bind("<Button-3>",fav_callback)
            def wheel(event):
                if getattr(event,"delta",0):self.sidebar_canvas.yview_scroll(int(-event.delta/120),"units")
                elif getattr(event,"num",None)==4:self.sidebar_canvas.yview_scroll(-1,"units")
                elif getattr(event,"num",None)==5:self.sidebar_canvas.yview_scroll(1,"units")
                return "break"
            for widget in (card,preview,label):
                widget.bind("<MouseWheel>",wheel,add="+"); widget.bind("<Button-4>",wheel,add="+"); widget.bind("<Button-5>",wheel,add="+")
            self.palette_cards[name]=(card,preview,label)
        self._refresh_palette_selection()
        try:self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all"))
        except Exception:pass

    def _refresh_palette_selection(self):
        if not hasattr(self,"palette_cards"): return
        chosen=self.symbol_name.get()
        for name,(card,preview,label) in self.palette_cards.items():
            active=(name==chosen and self.mode=="place")
            border=self._theme_color("accent") if active else self._theme_color("border")
            bg=self._theme_color("accent_soft") if active else self._theme_color("surface_alt")
            try:
                card.configure(highlightbackground=border,highlightcolor=border,background=bg)
                label.configure(background=bg)
            except Exception:pass

    def select_palette_symbol(self,name: str):
        if name not in SYMBOLS:return
        # Klik på palette betyder altid "jeg vil placere dette symbol".
        self.symbol_name.set(name)
        self._remember_recent_symbol(SYMBOLS[name])
        for category,items in SYMBOL_GROUPS.items():
            if name in items:
                if self.symbol_category.get()!=category:self.symbol_category.set(category)
                break
        if self.selected_index is not None:
            self.apply_symbol_properties()
        self._clear_symbol_selection(); self.selected_cable_index=None; self.selected_text_index=None
        self._restore_default_symbol_controls()
        self.on_symbol_name_change()
        self.set_mode("place")
        self.status_var.set(f"Placér {name}: klik flere steder · Esc afslutter.")

    def _update_symbol_configurator_visibility(self):
        if not hasattr(self,"symbol_configurator_button"):return
        try:
            if self.symbol_category.get()=="Kombi":
                if not self.symbol_configurator_button.winfo_manager():
                    self.symbol_configurator_button.pack(fill="x",pady=(0,5),before=self.palette_frame)
            elif self.symbol_configurator_button.winfo_manager():
                self.symbol_configurator_button.pack_forget()
        except tk.TclError:pass

    def _save_custom_symbol_library(self):
        try:
            data=load_app_settings(); data["custom_symbols"]=custom_symbol_records(); data["combo_templates"]=list(self.combo_templates); save_app_settings(data); self.app_settings=data
        except Exception:pass

    def show_symbol_configurator(self):
        """Modulbaseret konfigurator til kompakte lodrette afbryderrækker."""
        win=tk.Toplevel(self); win.title("Symbolkonfigurator – kombi / afbryderrække"); win.geometry("760x700"); win.minsize(650,600); win.transient(self); win.grab_set()
        root=ttk.Frame(win,padding=12); root.pack(fill="both",expand=True); root.columnconfigure(0,weight=1); root.columnconfigure(1,weight=1); root.rowconfigure(1,weight=1)
        ttk.Label(root,text="Byg et kompakt lodret symbol",font=("Segoe UI",13,"bold")).grid(row=0,column=0,columnspan=2,sticky="w",pady=(0,8))
        left=ttk.Frame(root); left.grid(row=1,column=0,sticky="nsew",padx=(0,12)); right=ttk.Frame(root); right.grid(row=1,column=1,sticky="nsew")

        # Gemte konfigurationer er skabeloner; de kan indlæses uden først at blive
        # placeret på tegningen. Det gør typiske kombinationer hurtige at genbruge.
        template_box=ttk.LabelFrame(left,text="Gemte skabeloner",padding=6); template_box.pack(fill="x",pady=(0,9))
        template_var=tk.StringVar(value="")
        template_combo=ttk.Combobox(template_box,textvariable=template_var,state="readonly")
        template_combo.pack(fill="x",pady=(0,5))
        template_buttons=ttk.Frame(template_box); template_buttons.pack(fill="x")
        for col in range(3): template_buttons.columnconfigure(col,weight=1)

        ttk.Label(left,text="Afbrydere (øverst → nederst)").pack(anchor="w")
        module_box=ttk.Frame(left); module_box.pack(fill="x",pady=(4,7))
        module_vars=[]; module_rows=[]
        socket_var=tk.StringVar(value="Stikkontakt")
        name_var=tk.StringVar(value="")
        name_manual={"value":False,"setting":False}
        pin_var=tk.BooleanVar(value=False)
        info_var=tk.StringVar(value="")

        preview=tk.Canvas(right,width=320,height=450,background=self._theme_color("surface"),highlightthickness=1,highlightbackground=self._theme_color("border")); preview.pack(fill="both",expand=True)
        ttk.Label(right,textvariable=info_var,style="Muted.TLabel",wraplength=305,justify="center").pack(fill="x",pady=(6,0))

        def current_modules():
            return [CUSTOM_SWITCH_TYPES.get(v.get(),"switch_1") for v in module_vars]
        def current_socket():
            return CUSTOM_SOCKET_TYPES.get(socket_var.get(),"none")
        def current_code():
            return make_custom_combo_code(current_modules(),current_socket())
        def auto_name():
            return custom_combo_auto_name(current_modules(),current_socket())
        def set_auto_name():
            name_manual["setting"]=True
            try:name_var.set(auto_name())
            finally:name_manual["setting"]=False
            name_manual["value"]=False
        def mark_name_manual(event=None):
            if not name_manual["setting"]:
                name_manual["value"]=True

        def redraw(*_):
            try:
                code=current_code(); self._draw_symbol_preview(preview,code)
                mods,sk=parse_custom_combo_symbol(code)
                caps=association_capacity(code); extra="med stik" if sk=="socket" else ("med jordstik" if sk=="socket_earth" else "uden stikkontakt")
                info_var.set(f"{len(mods)} afbrydermodul(er) · {extra} · {caps} tilhørsforhold")
                if not name_manual["value"]:
                    set_auto_name()
            except Exception as e:info_var.set(str(e))

        def rebuild_rows():
            for w in module_box.winfo_children():w.destroy()
            module_rows.clear()
            for i,var in enumerate(module_vars):
                row=ttk.Frame(module_box); row.pack(fill="x",pady=2); module_rows.append(row)
                ttk.Label(row,text=f"{i+1}.",width=3).pack(side="left")
                cb=ttk.Combobox(row,textvariable=var,values=list(CUSTOM_SWITCH_TYPES),state="readonly",width=29); cb.pack(side="left",fill="x",expand=True); cb.bind("<<ComboboxSelected>>",redraw)
                if len(module_vars)>1:
                    ttk.Button(row,text="×",width=3,command=lambda idx=i:remove_module(idx)).pack(side="left",padx=(4,0))
            redraw()
        def add_module():
            if len(module_vars)>=CUSTOM_COMBO_MAX_MODULES:
                self.bell(); info_var.set(f"Maks. {CUSTOM_COMBO_MAX_MODULES} afbrydermoduler."); return
            module_vars.append(tk.StringVar(value="1-polet afbryder")); rebuild_rows()
        def remove_module(idx):
            if len(module_vars)<=1:return
            module_vars.pop(idx); rebuild_rows()

        def apply_code(code: str, keep_template_name: str=""):
            parsed=parse_custom_combo_symbol(code)
            if not parsed:return
            mods,sk=parsed
            reverse_switch={v:k for k,v in CUSTOM_SWITCH_TYPES.items()}
            reverse_socket={v:k for k,v in CUSTOM_SOCKET_TYPES.items()}
            module_vars.clear(); module_vars.extend(tk.StringVar(value=reverse_switch.get(x,"1-polet afbryder")) for x in mods)
            socket_var.set(reverse_socket.get(sk,"Ingen stikkontakt"))
            name_manual["value"]=False
            rebuild_rows()
            if keep_template_name:
                # Skabelonnavnet må gerne være mere menneskeligt end autonavnet.
                name_manual["setting"]=True; name_var.set(keep_template_name); name_manual["setting"]=False; name_manual["value"]=True

        def refresh_templates(select_name=""):
            names=[x.get("name","") for x in self.combo_templates]
            template_combo.configure(values=names)
            if select_name in names:template_var.set(select_name)
            elif names:template_var.set(names[0])
            else:template_var.set("")
        def load_template():
            name=template_var.get().strip()
            rec=next((x for x in self.combo_templates if x.get("name")==name),None)
            if rec:apply_code(rec.get("code",""),name)
        def save_template():
            try:
                code=current_code(); name=name_var.get().strip() or auto_name()
                rec={"name":name,"code":code}
                existing=next((i for i,x in enumerate(self.combo_templates) if x.get("name")==name),None)
                if existing is None:self.combo_templates.append(rec)
                else:self.combo_templates[existing]=rec
                self.combo_templates=normalize_combo_template_records(self.combo_templates)
                self._save_custom_symbol_library(); refresh_templates(name)
                info_var.set(f"Skabelonen '{name}' er gemt.")
            except Exception as e:messagebox.showerror("Symbolkonfigurator",str(e),parent=win)
        def delete_template():
            name=template_var.get().strip()
            if not name:return
            self.combo_templates=[x for x in self.combo_templates if x.get("name")!=name]
            self._save_custom_symbol_library(); refresh_templates(); info_var.set(f"Skabelonen '{name}' er slettet.")

        ttk.Button(template_buttons,text="Indlæs",command=load_template).grid(row=0,column=0,sticky="ew",padx=(0,3))
        ttk.Button(template_buttons,text="Gem",command=save_template).grid(row=0,column=1,sticky="ew",padx=3)
        ttk.Button(template_buttons,text="Slet",command=delete_template).grid(row=0,column=2,sticky="ew",padx=(3,0))
        template_combo.bind("<<ComboboxSelected>>",lambda e:load_template())

        module_vars.extend([tk.StringVar(value="1-polet afbryder"),tk.StringVar(value="1-polet afbryder")])
        rebuild_rows()
        ttk.Button(left,text="+ Tilføj afbryder",command=add_module).pack(fill="x",pady=(0,10))
        ttk.Label(left,text="Stikkontakt nederst").pack(anchor="w")
        socket_cb=ttk.Combobox(left,textvariable=socket_var,values=list(CUSTOM_SOCKET_TYPES),state="readonly"); socket_cb.pack(fill="x",pady=(3,9)); socket_cb.bind("<<ComboboxSelected>>",redraw)
        ttk.Label(left,text="Navn i symbolpaletten").pack(anchor="w")
        name_row=ttk.Frame(left); name_row.pack(fill="x",pady=(3,3))
        name_entry=ttk.Entry(name_row,textvariable=name_var); name_entry.pack(side="left",fill="x",expand=True); name_entry.bind("<KeyRelease>",mark_name_manual)
        ttk.Button(name_row,text="Auto",width=6,command=lambda:(set_auto_name(),redraw())).pack(side="left",padx=(4,0))
        ttk.Label(left,text="Navnet følger automatisk de valgte afbrydere og stikkontakten. Skriv selv for at overskrive; Auto aktiverer automatisk navngivning igen.",style="Muted.TLabel",wraplength=320,justify="left").pack(anchor="w",pady=(0,6))
        ttk.Checkbutton(left,text="Fastgør som favorit i Hurtigvalg",variable=pin_var).pack(anchor="w",pady=(0,5))
        ttk.Label(left,text="1–6 afbrydere. Stikkontakten er valgfri. Symbolerne skaleres let i større rækker, så de forbliver kompakte uden at miste læsbarhed.",style="Muted.TLabel",wraplength=320,justify="left").pack(anchor="w",pady=(2,8))

        def save_and_place():
            try:
                code=current_code(); display=register_custom_symbol(code,name_var.get().strip() or auto_name())
                if not display:raise ValueError("Kunne ikke oprette symbolet.")
                if pin_var.get() and code not in self.favorite_symbols:
                    self.favorite_symbols.append(code); self._save_symbol_usage_settings()
                self._save_custom_symbol_library()
                if code not in self.symbol_color_defaults:self.symbol_color_defaults[code]=DEFAULT_SYMBOL_COLOR
                self.symbol_category.set("Kombi"); self.symbol_name.set(display); self._rebuild_symbol_palette(); self._rebuild_quick_symbols(); self._update_symbol_configurator_visibility(); self.on_symbol_name_change()
                win.grab_release(); win.destroy(); self.select_palette_symbol(display)
                self.status_var.set(f"Brugerdefineret symbol klar: {display}. Klik på tegningen for at placere det.")
            except Exception as e:messagebox.showerror("Symbolkonfigurator",str(e),parent=win)
        buttons=ttk.Frame(root); buttons.grid(row=2,column=0,columnspan=2,sticky="ew",pady=(12,0)); buttons.columnconfigure(0,weight=1); buttons.columnconfigure(1,weight=1)
        ttk.Button(buttons,text="Gem og placér",command=save_and_place).grid(row=0,column=0,sticky="ew",padx=(0,4))
        ttk.Button(buttons,text="Annuller",command=win.destroy).grid(row=0,column=1,sticky="ew",padx=(4,0))
        refresh_templates(); redraw(); self._apply_theme(redraw=False)

    def _update_color_swatch(self):
        c=normalize_hex_color(self.symbol_color.get())
        self.symbol_color.set(c)
        # Vælg sort/hvid tekst efter simpel luminans.
        r,g,b=int(c[1:3],16),int(c[3:5],16),int(c[5:7],16)
        fg="black" if (r*299+g*587+b*114)>150000 else "white"
        try:self.symbol_color_swatch.configure(background=c,foreground=fg)
        except Exception:pass

    def choose_symbol_color(self):
        initial=normalize_hex_color(self.symbol_color.get())
        chosen=colorchooser.askcolor(color=initial,title="Vælg symbolfarve",parent=self)[1]
        if not chosen:return
        self.symbol_color.set(normalize_hex_color(chosen)); self._update_color_swatch()
        indices=self._valid_selected_indices()
        if len(indices)>1:
            editable=[i for i in indices if not bool(getattr(self.placements[i],"locked",False))]
            if not editable:self.status_var.set("De valgte symboler er låst."); return
            before=self._capture_edit_state()
            for i in editable:self.placements[i].color=self.symbol_color.get()
            self._commit_history("Skift farve på flere symboler",before); self.redraw_placements(); self.status_var.set(f"Farve ændret på {len(editable)} symboler.")
        elif self.selected_index is not None:
            self.apply_symbol_properties()
        else:
            try:self.symbol_color_defaults[SYMBOLS[self.symbol_name.get()]]=self.symbol_color.get()
            except Exception:pass

    # ------------------------------------------------------------- LAYER UI
    def _init_layer_visibility(self,overrides=None):
        if not self.doc:
            self.layer_visibility={}; self.original_layer_visibility={}; self.layer_summary_var.set("Lag: ingen tegning"); return
        original={layer.dxf.name:bool(layer.is_on() and not layer.is_frozen()) for layer in self.doc.layers}
        self.original_layer_visibility=original; self.layer_visibility=dict(original)
        if overrides:
            migrated=dict(overrides)
            # 0.20 omdøber det genererede afbryderlag. Gamle projekters synlighed bevares.
            if SWITCH_LAYER not in migrated and LEGACY_SWITCH_LAYER in migrated:
                migrated[SWITCH_LAYER]=migrated[LEGACY_SWITCH_LAYER]
            for k,v in migrated.items():
                if k in self.layer_visibility:self.layer_visibility[k]=bool(v)
        self._update_layer_summary()

    def _update_layer_summary(self):
        if not self.layer_visibility:self.layer_summary_var.set("Lag: ingen tegning"); return
        self.layer_summary_var.set(f"Lag: {sum(self.layer_visibility.values())}/{len(self.layer_visibility)} synlige")

    def _layer_tag(self,name):
        if name not in self.layer_tags:
            self.layer_tags[name]="cadlayer_"+hashlib.sha1(name.encode("utf-8",errors="ignore")).hexdigest()[:12]
        return self.layer_tags[name]

    def set_layer_visibility(self,name,visible):
        if name not in self.layer_visibility:return
        self.layer_visibility[name]=bool(visible); self._update_layer_summary(); self._set_dirty(True)
        self.canvas.itemconfigure(self._layer_tag(name),state="normal" if visible else "hidden")
        self.redraw_annotations()

    def show_layers_window(self):
        if not self.doc:messagebox.showinfo("Lag","Åbn først en DWG- eller DXF-fil."); return
        win=tk.Toplevel(self); win.title("DWG/DXF- og el-lag"); win.geometry("470x680"); win.transient(self)
        top=ttk.Frame(win,padding=10); top.pack(fill="x")
        search=tk.StringVar(); ttk.Label(top,text="Søg lag").pack(anchor="w"); ttk.Entry(top,textvariable=search).pack(fill="x")
        outer=ttk.Frame(win); outer.pack(fill="both",expand=True,padx=10)
        c=tk.Canvas(outer,highlightthickness=0); sb=ttk.Scrollbar(outer,orient="vertical",command=c.yview); inner=ttk.Frame(c)
        inner.bind("<Configure>",lambda e:c.configure(scrollregion=c.bbox("all"))); c.create_window((0,0),window=inner,anchor="nw"); c.configure(yscrollcommand=sb.set)
        c.pack(side="left",fill="both",expand=True); sb.pack(side="right",fill="y")
        vars={}
        def rebuild(*_):
            for w in inner.winfo_children():w.destroy()
            q=search.get().casefold().strip()
            for name in sorted(self.layer_visibility,key=str.casefold):
                if q and q not in name.casefold():continue
                v=vars.setdefault(name,tk.BooleanVar(value=self.layer_visibility[name])); v.set(self.layer_visibility[name])
                ttk.Checkbutton(inner,text=name,variable=v,command=lambda n=name,v=v:self.set_layer_visibility(n,v.get())).pack(anchor="w",fill="x")
        def set_all(v):
            for n in self.layer_visibility:self.set_layer_visibility(n,v)
            rebuild()
        def restore():
            for n,v in self.original_layer_visibility.items():self.set_layer_visibility(n,v)
            rebuild()
        search.trace_add("write",rebuild); rebuild()
        buttons=ttk.Frame(win,padding=10); buttons.pack(fill="x")
        ttk.Button(buttons,text="Vis alle",command=lambda:set_all(True)).pack(side="left")
        ttk.Button(buttons,text="Skjul alle",command=lambda:set_all(False)).pack(side="left",padx=4)
        ttk.Button(buttons,text="Gendan oprindelig status",command=restore).pack(side="left",padx=4)
        ttk.Button(buttons,text="Luk",command=win.destroy).pack(side="right")

    # --------------------------------------------------------------- ODA/DWG
    def refresh_oda_status(self):
        self.oda_path=detect_oda_exec_path()
        if self.oda_path:self.oda_status_var.set(f"DWG: ODA fundet ({Path(self.oda_path).parent.name})")
        else:self.oda_status_var.set("DWG: ODA ikke fundet – DXF virker stadig")
        return self.oda_path

    def select_oda_executable(self):
        initial=os.environ.get("ProgramFiles",r"C:\Program Files")
        p=filedialog.askopenfilename(title="Vælg ODAFileConverter.exe",initialdir=initial,filetypes=[("ODA File Converter","ODAFileConverter.exe"),("Programmer","*.exe")])
        if not p:return False
        if not set_oda_exec_path(p):messagebox.showerror("Forkert fil","Vælg filen ODAFileConverter.exe."); return False
        self.refresh_oda_status(); return True

    def ensure_oda_ready(self,interactive=False):
        if self.refresh_oda_status():return True
        if not interactive:return False
        a=messagebox.askyesnocancel("DWG-understøttelse","ODA File Converter blev ikke fundet.\n\nJa: Vælg ODAFileConverter.exe manuelt.\nNej: Åbn den officielle downloadside.\nAnnuller: Fortsæt uden DWG.")
        if a is True:return self.select_oda_executable()
        if a is False:webbrowser.open(ODA_DOWNLOAD_URL)
        return False

    def show_oda_settings(self):
        cur=self.refresh_oda_status()
        if cur:
            if messagebox.askyesno("DWG / ODA",f"ODA File Converter er fundet her:\n\n{cur}\n\nVil du vælge en anden?"):self.select_oda_executable()
        else:self.ensure_oda_ready(True)

    def _friendly_error(self,e):
        txt=str(e)
        if isinstance(e,odafc.ODAFCNotInstalledError) or "ODAFileConverter" in txt:return "DWG kræver ODA File Converter. Brug 'DWG / ODA-indstillinger…'.\n\nDetaljer: "+txt
        return txt or repr(e)

    # ----------------------------------------------------------- DOCUMENT IO
    def open_file(self):
        if not self._confirm_discard_changes():return
        p=filedialog.askopenfilename(title="Åbn plantegning",filetypes=[("CAD-filer","*.dwg *.dxf"),("DWG","*.dwg"),("DXF","*.dxf")])
        if not p:return
        if Path(p).suffix.lower()==".dwg" and not self.ensure_oda_ready(True):return
        try:
            self.status_var.set("Indlæser og vektoriserer CAD-geometri…"); self.update_idletasks()
            self.doc=load_document(p); self.file_path=p; self.project_path=None; ensure_layers(self.doc); self.extent=document_extents(self.doc)
            self.cad_primitives,self.primitive_counts=extract_cad_primitives(self.doc)
            self._build_snap_index()
            self.placements=[]; self.cables=[]; self.texts=[]; self.creation_history=[]; self._clear_symbol_selection(); self.selected_cable_index=None; self.selected_text_index=None
            self.current_cable_points=[]; self._reset_history(); self._init_layer_visibility(); self._set_default_symbol_size(); self._restore_default_symbol_controls(); self.fit_view()
            self.vector_status_var.set((f"Viewer: {len(self.cad_primitives):,} vektorobjekter · Snap: canvas + {len(self.snap_segments):,} segmenter").replace(",","."))
            self._clear_recovery(); self._set_dirty(False); self.status_var.set(f"Indlæst: {Path(p).name} – separate el-lag er klar")
        except Exception as e:messagebox.showerror("Kunne ikke åbne filen",self._friendly_error(e)); self.status_var.set("Indlæsning mislykkedes.")

    def _set_default_symbol_size(self):
        if not self.doc:return
        u=int(self.doc.header.get("$INSUNITS",0) or 0)
        if u==6:value=.50
        elif u==4:value=500.0
        elif u==5:value=50.0
        elif u==1:value=20.0
        elif u==2:value=1.65
        else:
            x1,y1,x2,y2=self.extent; value=round(max(x2-x1,y2-y1)/45.0,3)
        self.default_symbol_size=float(value); self.symbol_size.set(float(value))
        self.default_symbol_line_width=0.25; self.symbol_line_width.set(0.25)
        # Fri tekst følger tegningens enhedssystem på samme måde som symbolerne.
        self.default_text_height=max(float(value)*0.40,1e-6); self.text_height.set(self.default_text_height)

    # ------------------------------------------------------ SYMBOL PROPERTIES
    def _combo_context_symbol(self):
        if self.selected_index is not None and 0<=self.selected_index<len(self.placements):
            return self.placements[self.selected_index].symbol
        try:return SYMBOLS[self.symbol_name.get()]
        except Exception:return ""

    def _update_combo_property_visibility(self):
        if not hasattr(self,"combo_properties_frame"):return
        show=is_combo_symbol(self._combo_context_symbol()) and len(self._valid_selected_indices())<=1
        try:
            if show and not self.combo_properties_frame.winfo_manager():
                self.combo_properties_frame.pack(fill="x",pady=(3,5),before=self.association_heading)
            elif not show and self.combo_properties_frame.winfo_manager():
                self.combo_properties_frame.pack_forget()
            split=normalize_combo_label_mode(self.combo_label_mode.get())=="Opdelt"
            if split:
                if not self.combo_split_frame.winfo_manager():self.combo_split_frame.pack(fill="x")
                self.combo_hint.configure(text="Opdelt viser separate mærkninger. For afbryderrækker kan flere afbrydere angives kommasepareret, fx S1,S2,S3 og G1,G1,G2.")
            else:
                if self.combo_split_frame.winfo_manager():self.combo_split_frame.pack_forget()
                self.combo_hint.configure(text="Fælles bruger Mærkning/Gruppe ovenfor.")
        except Exception:pass

    def _on_combo_label_mode_change(self,event=None):
        mode=normalize_combo_label_mode(self.combo_label_mode.get()); self.combo_label_mode.set(mode)
        if mode=="Opdelt":
            # UX: start med den fælles mærkning i begge dele, hvis brugeren ikke
            # allerede har skrevet separate værdier. Derefter kan de ændres frit.
            if not any((self.combo_switch_label.get().strip(),self.combo_switch_group.get().strip(),self.combo_socket_label.get().strip(),self.combo_socket_group.get().strip())):
                self.combo_switch_label.set(self.label_var.get().strip()); self.combo_switch_group.set(self.group_var.get().strip())
                self.combo_socket_label.set(self.label_var.get().strip()); self.combo_socket_group.set(self.group_var.get().strip())
        else:
            # Hvis de to dele stadig er identiske, kan de samles igen uden at
            # mærkningen skal tastes på ny.
            if not self.label_var.get().strip() and self.combo_switch_label.get().strip()==self.combo_socket_label.get().strip():
                self.label_var.set(self.combo_switch_label.get().strip())
            if not self.group_var.get().strip() and self.combo_switch_group.get().strip()==self.combo_socket_group.get().strip():
                self.group_var.set(self.combo_switch_group.get().strip())
        self._update_combo_property_visibility(); self.apply_symbol_properties()

    def _update_properties_panel(self):
        if not hasattr(self,"properties_frame"): return
        selected_symbols=self._valid_selected_indices()
        has_selection=(bool(selected_symbols) or self.selected_cable_index is not None or self.selected_text_index is not None)
        # Når et objekt er valgt skjules symbolpaletten midlertidigt. Det giver
        # egenskaberne plads med det samme, også på en lille skærm. Klik på tomt
        # område eller Esc bringer paletten tilbage.
        if hasattr(self,"palette_box"):
            try:
                if has_selection:
                    self.palette_box.pack_forget()
                elif not self.palette_box.winfo_manager():
                    self.palette_box.pack(fill="x",pady=(0,7),before=self.properties_frame)
            except Exception:pass
        if len(selected_symbols)>1:
            self.properties_frame.configure(text=f"Egenskaber – {len(selected_symbols)} symboler")
            self.properties_hint_var.set("Træk, kopiér, duplikér, rotér eller slet de valgte symboler samlet")
            self.symbol_layer_var.set("CAD-lag: flere symboler")
        elif self.selected_index is not None and 0<=self.selected_index<len(self.placements):
            p=self.placements[self.selected_index]
            name=symbol_display_name(p.symbol)
            self.properties_frame.configure(text=f"Egenskaber – {name}")
            self.properties_hint_var.set("Symbolet er låst – højreklik eller fjern låsen nedenfor" if bool(getattr(self.placements[selected_symbols[0]],"locked",False)) else "Ændringer gælder kun det valgte symbol")
            self.symbol_layer_var.set(f"CAD-lag: {symbol_layer(p.symbol)}")
        elif self.selected_cable_index is not None:
            self.properties_frame.configure(text="Egenskaber – kabel/ledning")
            self.properties_hint_var.set("Brug 'Indstillinger…' under kabelværktøjer")
        elif self.selected_text_index is not None:
            self.properties_frame.configure(text="Egenskaber – tekst")
            self.properties_hint_var.set("Dobbeltklik teksten for at redigere indhold og størrelse")
            self.symbol_layer_var.set(f"CAD-lag: {FREE_TEXT_LAYER}")
        else:
            self.properties_frame.configure(text="Egenskaber – nye symboler")
            self.properties_hint_var.set("Bruges som standard for nye symboler")
            try:self.symbol_layer_var.set(f"CAD-lag: {symbol_layer(SYMBOLS[self.symbol_name.get()])}")
            except Exception:self.symbol_layer_var.set("CAD-lag: —")
        # Tilhørsforhold vises kun som en kort status. Selve relationen laves med
        # knappen "Tilknyt lys…", så brugeren ikke skal administrere bogstaver manuelt.
        assoc_text="—"; can_link=False; can_clear=False
        if self.selected_index is not None and 0<=self.selected_index<len(self.placements):
            p=self.placements[self.selected_index]; vals=normalize_associations(getattr(p,"associations",[]))
            assoc_text=association_display(p) or "—"
            role=association_role(p.symbol); can_link=(role=="switch"); can_clear=bool(vals)
            if role=="switch":
                cap=association_capacity(p.symbol)
                assoc_text=(association_display(p) or "—") + (f"   ({len(vals)}/{cap})" if cap>1 else "")
        self.association_var.set(assoc_text)
        try:self.associate_button.configure(state="normal" if can_link else "disabled")
        except Exception:pass
        try:self.clear_association_button.configure(state="normal" if can_clear else "disabled")
        except Exception:pass
        try:
            self.lock_check.configure(state="normal" if len(selected_symbols)==1 else "disabled")
            if len(selected_symbols)!=1:self.symbol_locked.set(False)
        except Exception:pass
        self._update_combo_property_visibility()

    def _restore_default_symbol_controls(self):
        self.symbol_size.set(self.default_symbol_size); self.symbol_line_width.set(self.default_symbol_line_width)
        try:self.symbol_color.set(self.symbol_color_defaults.get(SYMBOLS[self.symbol_name.get()],DEFAULT_SYMBOL_COLOR))
        except Exception:self.symbol_color.set(DEFAULT_SYMBOL_COLOR)
        self._update_color_swatch()
        self.rotation.set(0.0); self.label_var.set(""); self.group_var.set("")
        self.combo_label_mode.set("Fælles"); self.combo_switch_label.set(""); self.combo_switch_group.set(""); self.combo_socket_label.set(""); self.combo_socket_group.set("")
        self.association_var.set("—"); self.symbol_locked.set(False)
        self._update_properties_panel(); self._refresh_palette_selection()

    def _load_selected_symbol_controls(self):
        if self.selected_index is None:return
        p=self.placements[self.selected_index]
        self.symbol_size.set(p.size); self.symbol_line_width.set(p.line_width); self.symbol_color.set(normalize_hex_color(p.color)); self._update_color_swatch(); self.rotation.set(p.rotation)
        if p.symbol=="spot": self.spot_size_var.set(float(p.size))
        self.label_var.set(p.label); self.group_var.set(p.group)
        self.combo_label_mode.set(normalize_combo_label_mode(getattr(p,"label_mode","Fælles")))
        self.combo_switch_label.set(getattr(p,"switch_label","") or ""); self.combo_switch_group.set(getattr(p,"switch_group","") or "")
        self.combo_socket_label.set(getattr(p,"socket_label","") or ""); self.combo_socket_group.set(getattr(p,"socket_group","") or "")
        self.association_var.set(association_display(p) or "—"); self.symbol_locked.set(bool(getattr(p,"locked",False)))
        # Palette viser typen på det valgte symbol uden at starte placering.
        name=symbol_display_name(p.symbol); self.symbol_name.set(name)
        for category,items in SYMBOL_GROUPS.items():
            if name in items:
                if self.symbol_category.get()!=category:
                    self.symbol_category.set(category); self._rebuild_symbol_palette()
                break
        self._update_properties_panel(); self._refresh_palette_selection()

    # --------------------------------------------------------- TILHØRSFORHOLD
    def _placement_by_uid(self, uid: str):
        for i,p in enumerate(self.placements):
            if getattr(p,"uid","")==uid:
                return i,p
        return None,None

    def _cleanup_orphan_associations(self):
        """Fjern bogstaver der ikke længere findes på både kontakt- og lyssiden."""
        switch_letters=set(); light_letters=set()
        for p in self.placements:
            vals=normalize_associations(getattr(p,"associations",[])); p.associations=vals
            if association_role(p.symbol)=="switch": switch_letters.update(vals)
            elif association_role(p.symbol)=="light": light_letters.update(vals)
        valid=switch_letters & light_letters
        for p in self.placements:
            if association_role(p.symbol) in ("switch","light"):
                p.associations=[a for a in normalize_associations(p.associations) if a in valid]
        self._sync_spot_parent_associations()

    def clear_selected_associations(self):
        if self.selected_index is None or not (0<=self.selected_index<len(self.placements)):
            self.status_var.set("Vælg først en afbryder eller et lys med tilhørsforhold."); return
        p=self.placements[self.selected_index]
        if bool(getattr(p,"locked",False)):
            self.status_var.set("Symbolet er låst. Lås det op før tilhørsforhold ændres."); return
        if not getattr(p,"associations",[]):
            self.status_var.set("Det valgte symbol har ingen tilhørsforhold."); return
        before=self._capture_edit_state(); old=association_display(p)
        p.associations=[]; self._cleanup_orphan_associations()
        self._commit_history("Ryd tilhørsforhold",before); self._load_selected_symbol_controls(); self.redraw_placements()
        self.status_var.set(f"Tilhørsforhold {old} fjernet.")

    def start_association_mode(self):
        if not self.doc or self.selected_index is None or not (0<=self.selected_index<len(self.placements)):
            self.status_var.set("Vælg først en afbryder."); return
        p=self.placements[self.selected_index]
        if bool(getattr(p,"locked",False)):
            self.status_var.set("Symbolet er låst. Lås det op før tilhørsforhold ændres."); return
        if association_role(p.symbol)!="switch":
            self.status_var.set("Tilhørsforhold oprettes fra en afbryder til et lys."); return
        cap=association_capacity(p.symbol); vals=normalize_associations(getattr(p,"associations",[]))
        if len(vals)>=cap:
            if not messagebox.askyesno("Tilhørsforhold",f"{symbol_display_name(p.symbol)} har allerede {association_display(p)}.\n\nVil du erstatte tilhørsforholdet?"):
                return
            before=self._capture_edit_state(); p.associations=[]; self._cleanup_orphan_associations(); self._commit_history("Nulstil tilhørsforhold",before)
        self.association_source_uid=p.uid; self.mode="associate"; self.dragging=False; self._update_mode_status()
        self.redraw_placements()
        remaining=association_capacity(p.symbol)-len(normalize_associations(p.associations))
        extra=f" ({remaining} tilknytninger mangler)" if association_capacity(p.symbol)>1 else ""
        self.status_var.set(f"Tilknyt lys: klik på lampeudtag/lampe{extra}. Esc afslutter.")

    def _assign_association_target(self, target_index: int):
        si,source=self._placement_by_uid(self.association_source_uid)
        if source is None or association_role(source.symbol)!="switch":
            self.mode="select"; self.association_source_uid=""; self._update_mode_status(); return
        if not (0<=target_index<len(self.placements)):
            return
        target=self.placements[target_index]
        if association_role(target.symbol)!="light":
            self.status_var.set("Klik på et lampeudtag eller en lampe for at oprette tilhørsforholdet."); return
        source_vals=normalize_associations(source.associations); target_vals=normalize_associations(target.associations)
        cap=association_capacity(source.symbol)
        if len(source_vals)>=cap:
            self.mode="select"; self.association_source_uid=""; self._update_mode_status(); self.status_var.set("Afbryderen har allerede alle sine tilhørsforhold."); return

        # Et eksisterende bogstav på lyset genbruges. Det gør korrespondance og
        # flere betjeningssteder intuitive: vælg næste kontakt og klik samme lys.
        letter=next((a for a in target_vals if a not in source_vals),"")
        if not letter:
            letter=next_association_letter(self.placements)
        before=self._capture_edit_state()
        source.associations=normalize_associations(source_vals+[letter])
        target.associations=normalize_associations(target_vals+[letter])
        self._sync_spot_parent_associations()
        self._commit_history(f"Tilknyt {letter}",before)
        self.selected_indices={si}; self.selected_index=si; self.selected_cable_index=None; self.selected_text_index=None
        remaining=cap-len(source.associations)
        if remaining>0:
            self.mode="associate"; self._load_selected_symbol_controls(); self.redraw_placements()
            self.status_var.set(f"Tilhørsforhold {letter} oprettet. Klik næste lampe for {symbol_display_name(source.symbol)} ({remaining} mangler).")
        else:
            self.mode="select"; self.association_source_uid=""; self._update_mode_status()
            self._load_selected_symbol_controls(); self.redraw_placements()
            self.status_var.set(f"Tilhørsforhold oprettet: {association_display(source)}.")

    def draw_association_targets(self):
        self.canvas.delete("association_target")
        if self.mode!="associate": return
        for i,p in enumerate(self.placements):
            if association_role(p.symbol)!="light" or not self.layer_visibility.get(symbol_layer(p.symbol),True): continue
            x1,y1,x2,y2=self.placement_screen_bbox(p,pad=5); pad=3
            self.canvas.create_rectangle(x1-pad,y1-pad,x2+pad,y2+pad,outline="#285d9b",dash=(4,3),width=1,tags=("association_target",f"assoc_target{i}"))
        self.canvas.tag_raise("association_target")

    # -------------------------------------------------------------- UNDO/REDO
    def _capture_edit_state(self):
        return {
            "placements":[asdict(p) for p in self.placements],
            "cables":[asdict(c) for c in self.cables],
            "texts":[asdict(t) for t in self.texts],
        }

    @staticmethod
    def _edit_state_key(state) -> str:
        return json.dumps(state,sort_keys=True,separators=(",",":"),ensure_ascii=False)

    def _restore_edit_state(self,state):
        self._history_restoring=True
        try:
            self.placements=[]
            for raw in state.get("placements",[]):
                item=dict(raw); item.setdefault("associations",[]); item["associations"]=normalize_associations(item.get("associations",[]))
                item.setdefault("label_mode","Fælles"); item.setdefault("switch_label",""); item.setdefault("switch_group",""); item.setdefault("socket_label",""); item.setdefault("socket_group",""); item["label_mode"]=normalize_combo_label_mode(item.get("label_mode"))
                self.placements.append(Placement(**item))
            self.cables=[]
            for raw in state.get("cables",[]):
                item=dict(raw); item["points"]=[tuple(q) for q in item.get("points",[])]
                self.cables.append(CablePlacement(**item))
            self.texts=[TextPlacement(**dict(raw)) for raw in state.get("texts",[])]
            self.creation_history=[("symbol",x) for x in self.placements]+[("cable",x) for x in self.cables]+[("text",x) for x in self.texts]
            self._clear_symbol_selection(); self.selected_cable_index=None; self.selected_text_index=None; self.selected_cable_vertex_index=None
            self.dragging=False; self._drag_history_snapshot=None; self._drag_history_label=""
            self._restore_default_symbol_controls()
            if self.doc:self.redraw_placements()
        finally:
            self._history_restoring=False
        self._update_undo_redo_buttons()

    def _commit_history(self,label: str, before_state) -> bool:
        if self._history_restoring or before_state is None:return False
        current=self._capture_edit_state()
        if self._edit_state_key(current)==self._edit_state_key(before_state):return False
        self.undo_stack.append((label,before_state))
        if len(self.undo_stack)>self.max_history:self.undo_stack=self.undo_stack[-self.max_history:]
        self.redo_stack.clear(); self._update_undo_redo_buttons(); self._set_dirty(True); return True

    def _reset_history(self):
        self.undo_stack=[]; self.redo_stack=[]; self._drag_history_snapshot=None; self._drag_history_label=""
        self._update_undo_redo_buttons()

    def _update_undo_redo_buttons(self):
        try:self.undo_button.configure(state="normal" if self.undo_stack else "disabled")
        except Exception:pass
        try:self.redo_button.configure(state="normal" if self.redo_stack else "disabled")
        except Exception:pass

    def undo(self,event=None):
        if event is not None and self._focus_is_text_input():return None
        if not self.undo_stack:
            self.status_var.set("Intet at fortryde.")
            return "break" if event is not None else None
        label,state=self.undo_stack.pop(); current=self._capture_edit_state(); self.redo_stack.append((label,current))
        self._restore_edit_state(state); self._set_dirty(True); self.status_var.set(f"Fortrød: {label}")
        return "break" if event is not None else None

    def redo(self,event=None):
        if event is not None and self._focus_is_text_input():return None
        if not self.redo_stack:
            self.status_var.set("Intet at gentage.")
            return "break" if event is not None else None
        label,state=self.redo_stack.pop(); current=self._capture_edit_state(); self.undo_stack.append((label,current))
        self._restore_edit_state(state); self._set_dirty(True); self.status_var.set(f"Gentog: {label}")
        return "break" if event is not None else None

    def apply_symbol_properties(self,event=None,show_error=False):
        """Opdatér kun det valgte symbol; uden valg opdateres standarden for nye."""
        # Ved multi-select bruges sidepanelet kun som status. Det forhindrer et
        # FocusOut-event i at ændre standarder eller ét tilfældigt symbol.
        if len(self._valid_selected_indices())>1:return True
        try:
            size=float(self.symbol_size.get()); lw=float(self.symbol_line_width.get())
            if not math.isfinite(size) or size<=0:raise ValueError("size")
            if not math.isfinite(lw) or lw<=0 or lw>5.0:raise ValueError("lineweight")
            rotation=float(self.rotation.get() or 0.0)
        except Exception:
            if show_error:messagebox.showerror("Symbol-egenskaber","Angiv en positiv symbolstørrelse og en linjetykkelse mellem 0 og 5 mm.")
            if self.selected_index is not None:self._load_selected_symbol_controls()
            else:self._restore_default_symbol_controls()
            return False
        if self.selected_index is not None:
            p=self.placements[self.selected_index]
            if bool(getattr(p,"locked",False)):
                # Fokus-skift i sidepanelet må ikke ved et uheld ændre et låst symbol.
                self._load_selected_symbol_controls()
                if show_error:self.status_var.set("Symbolet er låst. Lås det op via højreklik eller egenskaber.")
                return False
            combo_values=(normalize_combo_label_mode(self.combo_label_mode.get()),self.combo_switch_label.get().strip(),self.combo_switch_group.get().strip(),self.combo_socket_label.get().strip(),self.combo_socket_group.get().strip())
            new=(size,lw,rotation,self.label_var.get().strip(),self.group_var.get().strip(),normalize_hex_color(self.symbol_color.get()))+combo_values
            old=(float(p.size),float(p.line_width),float(p.rotation),p.label,p.group,normalize_hex_color(p.color),normalize_combo_label_mode(getattr(p,"label_mode","Fælles")),getattr(p,"switch_label",""),getattr(p,"switch_group",""),getattr(p,"socket_label",""),getattr(p,"socket_group",""))
            if new!=old:
                before=self._capture_edit_state()
                p.size,p.line_width,p.rotation,p.label,p.group,p.color,p.label_mode,p.switch_label,p.switch_group,p.socket_label,p.socket_group=new
                self._commit_history("Redigér symbol",before)
                self.redraw_placements(); self.status_var.set(f"Valgt symbol opdateret: {symbol_display_name(p.symbol)}.")
            self._update_properties_panel()
        else:
            self.default_symbol_size=size; self.default_symbol_line_width=lw
            try:self.symbol_color_defaults[SYMBOLS[self.symbol_name.get()]]=normalize_hex_color(self.symbol_color.get())
            except Exception:pass
        return True

    # ------------------------------------------------------------ VIEW / CAD
    def current_view_extents(self):
        """CAD-bounding box for det område, der faktisk er synligt i canvas.

        Bruges af PDF/udskrivning, så "Aktuel visning" matcher pan/zoom i
        editoren i stedet for altid at zoome tilbage til hele tegningen.
        """
        self.update_idletasks()
        cw=max(int(self.canvas.winfo_width()),1); ch=max(int(self.canvas.winfo_height()),1)
        # screen_to_cad håndterer den inverterede Y-akse.
        p1=self.screen_to_cad(0,0); p2=self.screen_to_cad(cw,ch)
        xmin=min(p1[0],p2[0]); xmax=max(p1[0],p2[0])
        ymin=min(p1[1],p2[1]); ymax=max(p1[1],p2[1])
        if xmax<=xmin:xmax=xmin+1.0
        if ymax<=ymin:ymax=ymin+1.0
        return (xmin,ymin,xmax,ymax)

    def _print_extents_for_scope(self):
        if self.print_scope.get()=="Hele tegningen":
            return print_extents(self.cad_primitives,self.placements,self.cables,self.layer_visibility,self.texts)
        return self.current_view_extents()

    def fit_view(self):
        """Fyld tegnefladen med den relevante, synlige plantegning.

        Fjerne CAD-outliers ignoreres, så et enkelt POINT/tekstobjekt ikke
        længere kan få selve huset til at fylde få procent af skærmen.
        """
        if not self.doc:return
        self.update_idletasks(); cw=max(self.canvas.winfo_width(),10); ch=max(self.canvas.winfo_height(),10)
        try:
            vxmin,vymin,vxmax,vymax=fit_view_extents(self.cad_primitives,self.placements,self.cables,self.layer_visibility,self.texts)
        except Exception:
            vxmin,vymin,vxmax,vymax=self.extent
        sx=max(vxmax-vxmin,1e-9); sy=max(vymax-vymin,1e-9)
        # Kun ca. 1,5 % margin: planen skal reelt fylde tegnefladen.
        self.view_scale=min(cw/sx,ch/sy)*.995
        oxmin,oymin,oxmax,oymax=self.extent
        sw=sx*self.view_scale; sh=sy*self.view_scale
        left=(cw-sw)/2.0; top=(ch-sh)/2.0
        # cad_to_screen bruger dokumentets oprindelige extents som koordinat-reference.
        self.offset_x=left-(vxmin-oxmin)*self.view_scale
        self.offset_y=top-(oymax-vymax)*self.view_scale
        self.rebuild_scene()

    def cad_to_screen(self,x,y):
        xmin,ymin,xmax,ymax=self.extent; return self.offset_x+(x-xmin)*self.view_scale, self.offset_y+(ymax-y)*self.view_scale

    def screen_to_cad(self,sx,sy):
        xmin,ymin,xmax,ymax=self.extent; return xmin+(sx-self.offset_x)/self.view_scale, ymax-(sy-self.offset_y)/self.view_scale

    def _cad_tags(self,layer):return ("scene","cad",self._layer_tag(layer))

    def rebuild_scene(self):
        self.canvas.delete("all")
        self.cad_text_items=[]
        if not self.doc:
            self.canvas.create_text(self.canvas.winfo_width()/2,self.canvas.winfo_height()/2,text="Åbn en DWG- eller DXF-plantegning",fill=self._theme_color("muted"),font=("Segoe UI",18)); return
        for prim in self.cad_primitives:self._draw_cad_primitive(prim)
        self.redraw_placements()
        self.draw_cable_preview()
        for n,v in self.layer_visibility.items():
            if not v:self.canvas.itemconfigure(self._layer_tag(n),state="hidden")

    def _draw_cad_primitive(self,p:CADPrimitive):
        tags=self._cad_tags(p.layer); fill=self._theme_color("cad"); width=1
        try:
            if p.kind=="line":
                x1,y1,x2,y2=p.data; a=self.cad_to_screen(x1,y1); b=self.cad_to_screen(x2,y2); self.canvas.create_line(*a,*b,fill=fill,width=width,tags=tags)
            elif p.kind=="circle":
                cx,cy,r=p.data; x,y=self.cad_to_screen(cx,cy); rr=r*self.view_scale; self.canvas.create_oval(x-rr,y-rr,x+rr,y+rr,outline=fill,width=width,tags=tags)
            elif p.kind=="arc":
                # Tk Canvas' native ARC er langt lettere end en polyline med mange segmenter
                # og skalerer fortsat som vektorgeometri ved zoom.
                cx,cy,r,a1,a2=p.data; delta=(a2-a1)%360 or 360
                sx,sy=self.cad_to_screen(cx,cy); rr=abs(r*self.view_scale)
                if delta>=359.999:
                    self.canvas.create_oval(sx-rr,sy-rr,sx+rr,sy+rr,outline=fill,width=width,tags=tags)
                else:
                    self.canvas.create_arc(sx-rr,sy-rr,sx+rr,sy+rr,start=float(a1),extent=float(delta),style=tk.ARC,outline=fill,width=width,tags=tags)
            elif p.kind=="polyline":
                pts=[]
                for x,y in p.data:pts.extend(self.cad_to_screen(x,y))
                if len(pts)>=4:self.canvas.create_line(*pts,fill=fill,width=width,tags=tags)
            elif p.kind=="point":
                x,y=self.cad_to_screen(*p.data); self.canvas.create_oval(x-1,y-1,x+1,y+1,fill=fill,outline=fill,tags=tags)
            elif p.kind=="text":
                x,y,t,h,rot=p.data; sx,sy=self.cad_to_screen(x,y); fs=max(6,min(36,int(abs(h*self.view_scale)*.75)))
                # CAD text is not part of scene transforms; it is repositioned once navigation settles.
                text_tags=("cad","cad_text",self._layer_tag(p.layer))
                item=self.canvas.create_text(sx,sy,text=t,anchor="sw",fill=fill,font=("Arial",fs),angle=-rot,tags=text_tags)
                self.cad_text_items.append((item,float(x),float(y),float(h),float(rot),p.layer))
        except tk.TclError:pass

    def _schedule_annotation_redraw(self,delay=45):
        """Debounce dyr mærknings-layout under hurtig zoom."""
        if self._annotation_redraw_job is not None:
            try:self.after_cancel(self._annotation_redraw_job)
            except Exception:pass
        self._annotation_redraw_job=self.after(delay,self._run_scheduled_annotation_redraw)

    def _run_scheduled_annotation_redraw(self):
        self._annotation_redraw_job=None
        self._update_cad_text_fonts()
        self.redraw_annotations()
        # Kabelknæk-håndtag skal være konstante i skærmpixel efter zoom.
        if self.selected_cable_index is not None:self._schedule_placement_redraw(0)

    def _update_cad_text_fonts(self):
        """Genplacér CAD-tekst efter navigation og opdatér fontstørrelse.

        CAD-tekst holdes udenfor det tunge ``scene``-tag. Under pan/zoom skjules
        teksten kortvarigt, så mange vektorelementer kan transformeres uden også
        at flytte/fontbehandle hvert tekstobjekt for hvert input-event.
        """
        alive=[]
        for entry in self.cad_text_items:
            try:
                if len(entry)>=6:
                    item,x,y,h,rot,layer=entry[:6]
                    sx,sy=self.cad_to_screen(float(x),float(y)); self.canvas.coords(item,sx,sy)
                    fs=max(6,min(36,int(abs(float(h)*self.view_scale)*.75)))
                    state="normal" if self.layer_visibility.get(layer,True) else "hidden"
                    self.canvas.itemconfigure(item,font=("Arial",fs),angle=-float(rot),state=state)
                    alive.append((item,float(x),float(y),float(h),float(rot),layer))
                else:
                    item,h=entry[:2]
                    fs=max(6,min(36,int(abs(float(h)*self.view_scale)*.75)))
                    self.canvas.itemconfigure(item,font=("Arial",fs),state="normal"); alive.append(entry)
            except (tk.TclError,ValueError,TypeError):
                pass
        self.cad_text_items=alive

    def _begin_navigation(self):
        if self._navigation_active:return
        self._navigation_active=True
        try:self.canvas.itemconfigure("cad_text",state="hidden")
        except tk.TclError:pass

    def _schedule_navigation_settle(self,delay=75):
        if self._navigation_settle_job is not None:
            try:self.after_cancel(self._navigation_settle_job)
            except Exception:pass
        self._navigation_settle_job=self.after(max(10,int(delay)),self._finish_navigation)

    def _finish_navigation(self):
        self._navigation_settle_job=None; self._navigation_active=False
        self._update_cad_text_fonts()
        self._schedule_annotation_redraw(0)

    def _zoom_annotation_items(self,cx,cy,factor):
        """Flyt screen-space labels ved zoom uden at skalere deres tekst/baggrund."""
        for item in self.canvas.find_withtag("annotation"):
            try:coords=self.canvas.coords(item)
            except tk.TclError:continue
            if len(coords)==2:
                x,y=coords; self.canvas.coords(item,cx+(x-cx)*factor,cy+(y-cy)*factor)
            elif len(coords)==4:
                l,t,r,b=coords; mx=(l+r)/2.0; my=(t+b)/2.0; w=r-l; h=b-t
                mx=cx+(mx-cx)*factor; my=cy+(my-cy)*factor
                self.canvas.coords(item,mx-w/2.0,my-h/2.0,mx+w/2.0,my+h/2.0)

    def _schedule_placement_redraw(self,delay=16,symbol_indices=None,cable_indices=None,text_indices=None,full=False):
        """Saml ændringer og tegn højst ca. én frame ad gangen under drag."""
        if full:self._dirty_full_redraw=True
        if symbol_indices is not None:self._dirty_symbol_indices.update(int(i) for i in symbol_indices)
        if cable_indices is not None:self._dirty_cable_indices.update(int(i) for i in cable_indices)
        if text_indices is not None:self._dirty_text_indices.update(int(i) for i in text_indices)
        if self._placement_redraw_job is not None:return
        self._placement_redraw_job=self.after(max(0,int(delay)),self._run_scheduled_placement_redraw)

    def _run_scheduled_placement_redraw(self):
        self._placement_redraw_job=None
        syms=set(self._dirty_symbol_indices); cabs=set(self._dirty_cable_indices); txts=set(self._dirty_text_indices); full=self._dirty_full_redraw
        self._dirty_symbol_indices.clear(); self._dirty_cable_indices.clear(); self._dirty_text_indices.clear(); self._dirty_full_redraw=False
        if full or (not syms and not cabs and not txts):self.redraw_placements()
        else:self.redraw_dirty(syms,cabs,txts)

    def _schedule_cable_preview(self,delay=16):
        if self._cable_preview_job is not None:return
        self._cable_preview_job=self.after(max(0,int(delay)),self._run_scheduled_cable_preview)

    def _run_scheduled_cable_preview(self):
        self._cable_preview_job=None
        self.draw_cable_preview()

    def on_mousewheel(self,event):
        if not self.doc:return
        self.clear_snap_feedback(); self._begin_navigation()
        try:
            d=float(event.delta)
            steps=(d/120.0) if abs(d)>=120.0 else (1.0 if d>0 else -1.0)
        except Exception:
            steps=1.0
        self._zoom_pending_steps+=steps
        self._zoom_pending_anchor=(int(event.x),int(event.y))
        if self._zoom_job is None:self._zoom_job=self.after(16,self._apply_pending_zoom)
        self._schedule_navigation_settle(90)
        return "break"

    def _apply_pending_zoom(self):
        self._zoom_job=None
        steps=self._zoom_pending_steps; self._zoom_pending_steps=0.0
        anchor=self._zoom_pending_anchor; self._zoom_pending_anchor=None
        if not self.doc or not anchor or abs(steps)<1e-9:return
        t0=time.perf_counter(); cx,cy=anchor
        steps=max(-6.0,min(6.0,steps)); requested=1.15**steps
        new=max(self.view_scale*.05,min(self.view_scale*50,self.view_scale*requested)); factor=new/self.view_scale
        if abs(factor-1.0)<1e-12:return
        self.canvas.scale("scene",cx,cy,factor,factor)
        self._zoom_annotation_items(cx,cy,factor)
        self.offset_x=cx-(cx-self.offset_x)*factor; self.offset_y=cy-(cy-self.offset_y)*factor; self.view_scale=new
        self._perf_last_zoom_ms=(time.perf_counter()-t0)*1000.0
        if abs(self._zoom_pending_steps)>1e-9 and self._zoom_job is None:self._zoom_job=self.after(16,self._apply_pending_zoom)

    def pan_start(self,event):
        self.clear_snap_feedback(); self._begin_navigation(); self.pan_last=(event.x,event.y)
        self._pan_pending_dx=0.0; self._pan_pending_dy=0.0; self._update_canvas_cursor()

    def pan_move(self,event):
        if not self.doc or not self.pan_last:return
        dx,dy=event.x-self.pan_last[0],event.y-self.pan_last[1]
        self.pan_last=(event.x,event.y); self._pan_pending_dx+=dx; self._pan_pending_dy+=dy
        if self._pan_job is None:self._pan_job=self.after(16,self._apply_pending_pan)
        self._schedule_navigation_settle(90)

    def _apply_pending_pan(self):
        self._pan_job=None
        dx,dy=self._pan_pending_dx,self._pan_pending_dy; self._pan_pending_dx=0.0; self._pan_pending_dy=0.0
        if not self.doc or (abs(dx)<1e-9 and abs(dy)<1e-9):return
        t0=time.perf_counter()
        self.canvas.move("scene",dx,dy); self.canvas.move("annotation",dx,dy)
        self.offset_x+=dx; self.offset_y+=dy
        self._perf_last_pan_ms=(time.perf_counter()-t0)*1000.0
        if (abs(self._pan_pending_dx)>1e-9 or abs(self._pan_pending_dy)>1e-9) and self._pan_job is None:self._pan_job=self.after(16,self._apply_pending_pan)

    def pan_end(self,event=None):
        if self._pan_job is not None:
            try:self.after_cancel(self._pan_job)
            except Exception:pass
            self._pan_job=None
        self._apply_pending_pan(); self.pan_last=None
        self._schedule_navigation_settle(25); self._update_canvas_cursor(self.snap_feedback_kind)

    # ------------------------------------------------------------- SNAP INDEX
    def _build_snap_index(self):
        """Byg et let spatialt indeks over rette CAD-segmenter til vægsnap."""
        segments=[]
        for prim in self.cad_primitives:
            if prim.layer in GENERATED_LAYERS:
                continue
            if prim.kind=="line":
                x1,y1,x2,y2=prim.data; segments.append((float(x1),float(y1),float(x2),float(y2),prim.layer))
            elif prim.kind=="polyline":
                pts=list(prim.data)
                for a,b in zip(pts,pts[1:]):
                    segments.append((float(a[0]),float(a[1]),float(b[0]),float(b[1]),prim.layer))
            elif prim.kind=="circle":
                cx,cy,r=map(float,prim.data); pts=_arc_points(cx,cy,r,0,360,48)
                for a,b in zip(pts,pts[1:]):segments.append((a[0],a[1],b[0],b[1],prim.layer))
            elif prim.kind=="arc":
                cx,cy,r,a1,a2=map(float,prim.data); delta=(a2-a1)%360 or 360; steps=max(8,int(delta/8))
                pts=_arc_points(cx,cy,r,a1,a1+delta,steps)
                for a,b in zip(pts,pts[1:]):segments.append((a[0],a[1],b[0],b[1],prim.layer))
        self.snap_segments=segments; self.snap_grid={}; self.snap_long_segments=[]
        xmin,ymin,xmax,ymax=self.extent
        self.snap_grid_size=max(max(xmax-xmin,ymax-ymin)/100.0,1e-9)
        cs=self.snap_grid_size
        for i,(x1,y1,x2,y2,_layer) in enumerate(segments):
            ix1=int(math.floor((min(x1,x2)-xmin)/cs)); ix2=int(math.floor((max(x1,x2)-xmin)/cs))
            iy1=int(math.floor((min(y1,y2)-ymin)/cs)); iy2=int(math.floor((max(y1,y2)-ymin)/cs))
            cells=(ix2-ix1+1)*(iy2-iy1+1)
            if cells>250:
                self.snap_long_segments.append(i); continue
            for ix in range(ix1,ix2+1):
                for iy in range(iy1,iy2+1):self.snap_grid.setdefault((ix,iy),[]).append(i)

    @staticmethod
    def _nearest_point_on_segment(px,py,x1,y1,x2,y2):
        dx=x2-x1; dy=y2-y1
        if dx==0 and dy==0:return x1,y1,math.hypot(px-x1,py-y1)
        t=max(0.0,min(1.0,((px-x1)*dx+(py-y1)*dy)/(dx*dx+dy*dy)))
        qx=x1+t*dx; qy=y1+t*dy
        return qx,qy,math.hypot(px-qx,py-qy)

    def _wall_snap_candidate(self,x,y,tol_cad):
        """Bagudkompatibel CAD-space forespørgsel til tests og hjælpefunktioner."""
        if not self.snap_segments:return None
        xmin,ymin,_,_=self.extent; cs=max(float(self.snap_grid_size),1e-12)
        ix1=int(math.floor((x-tol_cad-xmin)/cs)); ix2=int(math.floor((x+tol_cad-xmin)/cs))
        iy1=int(math.floor((y-tol_cad-ymin)/cs)); iy2=int(math.floor((y+tol_cad-ymin)/cs))
        ids=set(self.snap_long_segments)
        for ix in range(ix1,ix2+1):
            for iy in range(iy1,iy2+1):ids.update(self.snap_grid.get((ix,iy),()))
        best=None; bd=float(tol_cad)
        for i in ids:
            x1,y1,x2,y2,layer=self.snap_segments[i]
            if not self.layer_visibility.get(layer,True):continue
            qx,qy,d=self._nearest_point_on_segment(x,y,x1,y1,x2,y2)
            if d<=bd:best=(qx,qy,"væg/CAD");bd=d
        return best

    @staticmethod
    def _nearest_point_on_screen_segment(px,py,x1,y1,x2,y2):
        dx=x2-x1; dy=y2-y1
        den=dx*dx+dy*dy
        if den<=1e-18:return x1,y1,math.hypot(px-x1,py-y1),0.0
        t=max(0.0,min(1.0,((px-x1)*dx+(py-y1)*dy)/den))
        qx=x1+t*dx; qy=y1+t*dy
        return qx,qy,math.hypot(px-qx,py-qy),t

    def _wall_snap_candidate_screen_model(self,sx,sy,tol_px=SNAP_WALL_TOLERANCE_PX):
        """Fallback: find nærmeste *synlige* CAD-segment via modelgeometrien.

        Tidligere blev den endelige afstand vurderet i CAD-enheder. Det er
        matematisk tæt på det samme ved uniform zoom, men i praksis gav store
        extents, gamle DWG'er og gentagen canvas-zoom en dårlig brugeroplevelse.
        Den nye motor måler den faktiske afstand til det, brugeren ser.
        """
        if not self.snap_segments:return None
        rawx,rawy=self.screen_to_cad(float(sx),float(sy))
        tol_cad=float(tol_px)/max(float(self.view_scale),1e-12)
        xmin,ymin,_,_=self.extent; cs=max(float(self.snap_grid_size),1e-12)
        ix1=int(math.floor((rawx-tol_cad-xmin)/cs)); ix2=int(math.floor((rawx+tol_cad-xmin)/cs))
        iy1=int(math.floor((rawy-tol_cad-ymin)/cs)); iy2=int(math.floor((rawy+tol_cad-ymin)/cs))
        ids=set(self.snap_long_segments)
        for ix in range(ix1,ix2+1):
            for iy in range(iy1,iy2+1):ids.update(self.snap_grid.get((ix,iy),()))
        # Hvis en usædvanlig DWG/extents-kombination gør grid-opslaget tomt,
        # falder vi tilbage til alle segmenter i rimeligt store tegninger.
        if not ids and len(self.snap_segments)<=25000:
            ids=range(len(self.snap_segments))
        best=None; best_px=float(tol_px)+1e-9
        for i in ids:
            x1,y1,x2,y2,layer=self.snap_segments[i]
            if not self.layer_visibility.get(layer,True):continue
            a=self.cad_to_screen(x1,y1); b=self.cad_to_screen(x2,y2)
            qsx,qsy,dpx,t=self._nearest_point_on_screen_segment(float(sx),float(sy),a[0],a[1],b[0],b[1])
            if dpx<=best_px:
                qx=x1+(x2-x1)*t; qy=y1+(y2-y1)*t
                angle=math.degrees(math.atan2(y2-y1,x2-x1)) if abs(x2-x1)+abs(y2-y1)>1e-12 else 0.0
                best=(qx,qy,"væg/CAD",layer,angle,dpx); best_px=dpx
        return best

    @staticmethod
    def _wall_layer_priority(name: str) -> int:
        """Lavere tal = mere sandsynligt væglag.

        Den vedhæftede Revit/AutoCAD-plan bruger bl.a. ``Walls`` og
        ``Walls-1``…``Walls-4``. De prioriteres foran generelle kanter og
        møbel-/detailgeometri, så snap ikke føles tilfældigt i en tæt plan.
        """
        n=str(name or "").casefold().replace("_","-")
        if any(w in n for w in ("wall","væg","vaeg","mur")):return 0
        if "common edges" in n:return 1
        return 2

    @classmethod
    def _preferred_wall_layer_name(cls,name: str) -> bool:
        return cls._wall_layer_priority(name)<2

    def _canvas_item_layer(self,item) -> str:
        """Find oprindeligt CAD-lag for et canvas-item via dets lag-tag."""
        try: tags=set(self.canvas.gettags(item))
        except Exception:return ""
        for name,tag in self.layer_tags.items():
            if tag in tags:return name
        return ""

    def _canvas_wall_snap_candidate_screen(self,sx,sy,tol_px=SNAP_WALL_TOLERANCE_PX):
        """Snap direkte mod den CAD-geometri der faktisk er tegnet på canvas.

        Dette er den vigtigste ændring i 0.19.4: snap bruger samme pixel-
        koordinater og samme Tk-items som brugeren ser. Dermed kan zoom/pan,
        store DWG-extents eller små forskelle mellem udtrukket CAD-geometri og
        canvas aldrig få snap-resultatet til at afvige fra den synlige linje.
        """
        if "canvas" not in self.__dict__ or self.__dict__.get("canvas") is None:return None
        r=max(2.0,float(tol_px))
        try: ids=self.canvas.find_overlapping(float(sx)-r,float(sy)-r,float(sx)+r,float(sy)+r)
        except Exception:return None
        best_by_priority={0:None,1:None,2:None}
        for item in ids:
            try:
                tags=set(self.canvas.gettags(item))
                if "cad" not in tags:continue
                if self.canvas.itemcget(item,"state")=="hidden":continue
                typ=self.canvas.type(item)
                layer=self._canvas_item_layer(item)
                if layer and not self.layer_visibility.get(layer,True):continue
                coords=[float(v) for v in self.canvas.coords(item)]
            except Exception:
                continue
            # Vægge, polylines og hatch-konturer renderes som Tk LINE-items.
            # POINT/TEXT ignoreres bevidst. ARC/OVAL håndteres af model-fallback.
            if typ!="line" or len(coords)<4:continue
            for j in range(0,len(coords)-3,2):
                x1,y1,x2,y2=coords[j],coords[j+1],coords[j+2],coords[j+3]
                qx,qy,dpx,t=self._nearest_point_on_screen_segment(float(sx),float(sy),x1,y1,x2,y2)
                if dpx>r:continue
                cx,cy=self.screen_to_cad(qx,qy)
                # Screen-Y peger nedad; vend den igen ved beregning af CAD-vinkel.
                angle=math.degrees(math.atan2(-(y2-y1),x2-x1)) if abs(x2-x1)+abs(y2-y1)>1e-12 else 0.0
                cand=(cx,cy,"væg/CAD",layer,angle,dpx)
                pri=self._wall_layer_priority(layer)
                prev=best_by_priority[pri]
                if prev is None or dpx<prev[5]:best_by_priority[pri]=cand
        for pri in (0,1,2):
            if best_by_priority[pri] is not None:return best_by_priority[pri]
        return None

    def _wall_snap_candidate_screen(self,sx,sy,tol_px=SNAP_WALL_TOLERANCE_PX):
        """Fælles vægsnap: synligt canvas først, modelindeks som fallback."""
        cand=self._canvas_wall_snap_candidate_screen(sx,sy,tol_px)
        if cand is not None:return cand
        return self._wall_snap_candidate_screen_model(sx,sy,tol_px)

    def _screen_distance_to_placement(self,sx,sy,p):
        """Afstand i pixels til den synlige symbolvektor (ikke kun dens bbox)."""
        best=float("inf")
        def world(lx,ly):
            rx,ry=rotate_point(lx,ly,p.rotation); return p.x+rx,p.y+ry
        def segdist(a,b):
            nonlocal best
            ax,ay=self.cad_to_screen(*a); bx,by=self.cad_to_screen(*b)
            _qx,_qy,d,_t=self._nearest_point_on_screen_segment(float(sx),float(sy),ax,ay,bx,by)
            if d<best:best=d
        for prim in symbol_primitives(p.symbol,p.size):
            typ=prim[0]
            try:
                if typ=="line":segdist(world(prim[1],prim[2]),world(prim[3],prim[4]))
                elif typ=="polyline":
                    pts=[world(x,y) for x,y in prim[1]]
                    for a,b in zip(pts,pts[1:]):segdist(a,b)
                elif typ in ("circle","arc"):
                    if typ=="circle":
                        _,cx,cy,r=prim; a1,a2=0.0,360.0
                    else:
                        _,cx,cy,r,a1,a2=prim
                    delta=(float(a2)-float(a1))%360.0 or 360.0
                    steps=max(12,min(72,int(delta/6.0)+1))
                    pts=[]
                    for j in range(steps+1):
                        a=math.radians(float(a1)+delta*j/steps)
                        pts.append(world(cx+r*math.cos(a),cy+r*math.sin(a)))
                    for a,b in zip(pts,pts[1:]):segdist(a,b)
                elif typ=="text":
                    _,x,y,_t,h=prim; wx,wy=world(x,y); tx,ty=self.cad_to_screen(wx,wy)
                    best=min(best,math.hypot(float(sx)-tx,float(sy)-ty))
            except Exception:
                continue
        return best

    def _rebuild_placement_snap_index(self):
        """Byg et let CAD-space grid over symbolernes faktiske bounding boxes."""
        self.placement_snap_grid={}; self.placement_snap_long=[]
        if not self.placements:
            self.placement_snap_grid_size=500.0; return
        sizes=sorted(max(1.0,float(getattr(p,"size",500.0))) for p in self.placements)
        median=sizes[len(sizes)//2]
        try:
            xmin,ymin,xmax,ymax=self.extent; span=max(float(xmax-xmin),float(ymax-ymin),1.0)
        except Exception:
            xmin=ymin=0.0; span=max(median*100.0,1.0)
        cs=max(median*1.5,span/220.0,1.0); self.placement_snap_grid_size=cs
        for i,p in enumerate(self.placements):
            try:
                x1,y1,x2,y2=symbol_local_bbox(p.symbol,p.size)
                corners=[]
                for lx,ly in ((x1,y1),(x1,y2),(x2,y1),(x2,y2)):
                    rx,ry=rotate_point(lx,ly,p.rotation); corners.append((p.x+rx,p.y+ry))
                xs=[q[0] for q in corners]; ys=[q[1] for q in corners]
                bx1,bx2=min(xs),max(xs); by1,by2=min(ys),max(ys)
                ix1=int(math.floor((bx1-xmin)/cs)); ix2=int(math.floor((bx2-xmin)/cs))
                iy1=int(math.floor((by1-ymin)/cs)); iy2=int(math.floor((by2-ymin)/cs))
                cells=(ix2-ix1+1)*(iy2-iy1+1)
                if cells>120:
                    self.placement_snap_long.append(i); continue
                for ix in range(ix1,ix2+1):
                    for iy in range(iy1,iy2+1):self.placement_snap_grid.setdefault((ix,iy),[]).append(i)
            except Exception:
                self.placement_snap_long.append(i)

    def _placement_candidate_indices_cad(self,x,y,radius=0.0):
        placements=self.__dict__.get("placements",[])
        if not placements:return []
        # Headless unit-tests konstruerer enkelte hjælpeobjekter uden Tk/__init__.
        if "placement_snap_grid" not in self.__dict__ or "placement_snap_long" not in self.__dict__:
            return list(range(len(placements)))
        if not self.placement_snap_grid and not self.placement_snap_long:
            self._rebuild_placement_snap_index()
        try:xmin,ymin,_,_=self.extent
        except Exception:return list(range(len(placements)))
        cs=max(float(self.placement_snap_grid_size),1e-9); r=max(0.0,float(radius))
        ix1=int(math.floor((float(x)-r-xmin)/cs)); ix2=int(math.floor((float(x)+r-xmin)/cs))
        iy1=int(math.floor((float(y)-r-ymin)/cs)); iy2=int(math.floor((float(y)+r-ymin)/cs))
        ids=set(self.placement_snap_long)
        for ix in range(ix1,ix2+1):
            for iy in range(iy1,iy2+1):ids.update(self.placement_snap_grid.get((ix,iy),()))
        return sorted(i for i in ids if 0<=i<len(self.placements))

    def _placement_candidate_indices_screen(self,sx,sy,pad_px=0.0):
        x,y=self.screen_to_cad(float(sx),float(sy))
        radius=max(0.0,float(pad_px))/max(float(getattr(self,"view_scale",1.0) or 1.0),1e-12)
        return self._placement_candidate_indices_cad(x,y,radius)

    def _symbol_port_snap_candidate(self,sx,sy):
        """Find kabelsnap til symbol med direkte hit-test som første prioritet.

        Hvis cursoren er over den synlige symbol-bounding-box, snapper vi altid
        til den nærmeste logiske port. Det gør handlingen deterministisk: klik
        på et symbol == kabel er forbundet til symbolet. Hvis cursoren ikke er
        over et symbol, bruges en normal magnetzone omkring portene.
        """
        if not self.snap_to_symbols.get():return None

        # 1) Direkte hit på symbolkroppen. Dette bruger samme bbox som selection,
        # og er derfor uafhængigt af CAD-viewerens snapindeks.
        hit_i=None; hit_d=float("inf")
        try:
            hit_i,hit_d=self.find_symbol_at(float(sx),float(sy))
        except Exception:
            hit_i=None
        if hit_i is not None and 0<=hit_i<len(self.placements):
            p=self.placements[hit_i]
            if self.layer_visibility.get(symbol_layer(p.symbol),True):
                ports=placement_connection_ports(p)
                if ports:
                    ranked=[]
                    for qx,qy,port in ports:
                        psx,psy=self.cad_to_screen(qx,qy)
                        ranked.append((math.hypot(float(sx)-psx,float(sy)-psy),qx,qy,port))
                    d,qx,qy,port=min(ranked,key=lambda q:q[0])
                    return (qx,qy,"symbol",p.uid,int(port),hit_i,d)

        # 2) Magnetzone omkring alle synlige forbindelsespunkter.
        best=None; best_d=float(SNAP_SYMBOL_PORT_TOLERANCE_PX)+1e-9
        nearby=self._placement_candidate_indices_screen(sx,sy,SNAP_SYMBOL_PORT_TOLERANCE_PX+SNAP_SYMBOL_BODY_PAD_PX)
        for i in nearby:
            p=self.placements[i]
            if not self.layer_visibility.get(symbol_layer(p.symbol),True):continue
            for qx,qy,port in placement_connection_ports(p):
                psx,psy=self.cad_to_screen(qx,qy)
                d=math.hypot(float(sx)-psx,float(sy)-psy)
                if d<=best_d:
                    best=(qx,qy,"symbol",p.uid,int(port),i,d); best_d=d
        if best is not None:return best

        # 3) Lidt generøs bbox-fallback, særligt nyttig ved meget små symboler.
        body=[]
        for i in nearby:
            p=self.placements[i]
            if not self.layer_visibility.get(symbol_layer(p.symbol),True):continue
            try:x1,y1,x2,y2=self.placement_screen_bbox(p,pad=SNAP_SYMBOL_BODY_PAD_PX)
            except Exception:continue
            if not (x1<=sx<=x2 and y1<=sy<=y2):continue
            ports=placement_connection_ports(p)
            if not ports:continue
            ranked=[]
            for qx,qy,port in ports:
                psx,psy=self.cad_to_screen(qx,qy); d=math.hypot(float(sx)-psx,float(sy)-psy)
                ranked.append((d,qx,qy,port))
            d,qx,qy,port=min(ranked,key=lambda q:q[0])
            body.append((d,qx,qy,p.uid,port,i))
        if body:
            d,qx,qy,uid,port,i=min(body,key=lambda q:q[0])
            return (qx,qy,"symbol",uid,int(port),i,d)
        return None

    def snap_point_detail(self,sx,sy):
        """Fælles snapmotor til kabel-/ledningspunkter."""
        raw=self.screen_to_cad(sx,sy); x,y=raw
        sym=self._symbol_port_snap_candidate(sx,sy)
        if sym is not None:
            return sym[0],sym[1],sym[2],sym[3],int(sym[4])
        if self.snap_to_walls.get():
            wall=self._wall_snap_candidate_screen(sx,sy,SNAP_WALL_TOLERANCE_PX)
            if wall:return wall[0],wall[1],wall[2],"",0
        return x,y,"fri","",0

    def snap_point(self,sx,sy):
        x,y,kind,uid,_port=self.snap_point_detail(sx,sy)
        return x,y,kind,uid

    def _symbol_mate_candidate(self,symbol,size,rotation,origin,tol_cad,ignore_uid=""):
        """Find én stabil fysisk position ved snap mellem symboler."""
        if not self.snap_to_symbols.get():return None
        ignore_uids={ignore_uid} if isinstance(ignore_uid,str) and ignore_uid else set(ignore_uid or ())
        ox,oy=float(origin[0]),float(origin[1])
        best=None; best_px=float(SNAP_DEVICE_TOLERANCE_PX)+1e-9
        moving_is_wall=_is_wall_device(symbol)
        # Kandidater evalueres i skærmpixel. Det gør samme snapafstand gældende
        # ved alle zoomniveauer og undgår skiftende adfærd i store DWG'er.
        query_radius=max(float(size)*2.5,(SNAP_DEVICE_TOLERANCE_PX+SNAP_TOLERANCE_PX)/max(float(getattr(self,"view_scale",1.0) or 1.0),1e-12))
        for i in self._placement_candidate_indices_cad(ox,oy,query_radius):
            p=self.placements[i]
            if getattr(p,"uid","") in ignore_uids:continue
            if not self.layer_visibility.get(symbol_layer(p.symbol),True):continue
            candidates=[]
            if moving_is_wall and _is_wall_device(p.symbol):
                candidates.extend(wall_device_snap_origins(symbol,size,p,rotation))
            else:
                moving={}
                for name,(lx,ly) in symbol_mating_sites(symbol,size).items():
                    lx,ly=rotate_point(lx,ly,rotation); moving[name]=(ox+lx,oy+ly)
                fixed=placement_mating_sites(p); opposite={"left":"right","right":"left","top":"bottom","bottom":"top"}
                for mname,fname in opposite.items():
                    mx,my=moving[mname]; fx,fy=fixed[fname]
                    candidates.append((ox+fx-mx,oy+fy-my,"symbol-kant"))
            for tx,ty,label in candidates:
                dpx=math.hypot(tx-ox,ty-oy)*max(float(getattr(self,"view_scale",1.0) or 1.0),1e-12)
                limit=SNAP_DEVICE_TOLERANCE_PX if moving_is_wall and _is_wall_device(p.symbol) else SNAP_TOLERANCE_PX
                if dpx<=limit and dpx<best_px:
                    best=((tx,ty),label); best_px=dpx
        return best

    def _snap_mount_point_to_wall_screen(self,symbol,size,rotation,origin,cursor_screen=None,use_cursor_fallback=True):
        """Flyt symbol-origin så det egentlige montagepunkt rammer synlig CAD."""
        local=symbol_mount_points(symbol,size)
        if not local:return None
        ox,oy=float(origin[0]),float(origin[1]); best=None; best_px=SNAP_WALL_TOLERANCE_PX+1e-9
        rotated=[]
        for lx,ly in local:
            lx,ly=rotate_point(lx,ly,rotation); rotated.append((lx,ly))
            wx,wy=ox+lx,oy+ly; msx,msy=self.cad_to_screen(wx,wy)
            wall=self._wall_snap_candidate_screen(msx,msy,SNAP_WALL_TOLERANCE_PX)
            if wall and wall[5]<=best_px:
                best=((ox+wall[0]-wx,oy+wall[1]-wy),wall); best_px=wall[5]
        if best is not None:return best
        if use_cursor_fallback and cursor_screen is not None:
            wall=self._wall_snap_candidate_screen(float(cursor_screen[0]),float(cursor_screen[1]),SNAP_WALL_TOLERANCE_PX)
            if wall:
                candidates=[]
                for lx,ly in rotated:
                    no=(wall[0]-lx,wall[1]-ly)
                    s0=self.cad_to_screen(ox,oy); s1=self.cad_to_screen(*no)
                    candidates.append((math.hypot(s1[0]-s0[0],s1[1]-s0[1]),no))
                if candidates:return (min(candidates,key=lambda q:q[0])[1],wall)
        return None

    def _snap_mount_point_to_wall(self,symbol,size,rotation,origin,tol_cad,cursor_cad=None,use_cursor_fallback=True):
        """Kompatibilitets-wrapper; den nye interaktive motor arbejder i pixels."""
        local=symbol_mount_points(symbol,size)
        if not local:return None
        ox,oy=float(origin[0]),float(origin[1]); best=None; best_d=float(tol_cad)+1e-12
        rotated=[]
        for lx,ly in local:
            lx,ly=rotate_point(lx,ly,rotation); rotated.append((lx,ly))
            wx,wy=ox+lx,oy+ly; wall=self._wall_snap_candidate(wx,wy,tol_cad)
            if wall:
                d=math.hypot(wall[0]-wx,wall[1]-wy)
                if d<=best_d:best=(ox+wall[0]-wx,oy+wall[1]-wy);best_d=d
        if best is not None:return best
        if use_cursor_fallback and cursor_cad is not None:
            wall=self._wall_snap_candidate(float(cursor_cad[0]),float(cursor_cad[1]),tol_cad)
            if wall:
                return min(((math.hypot((wall[0]-lx)-ox,(wall[1]-ly)-oy),(wall[0]-lx,wall[1]-ly)) for lx,ly in rotated),key=lambda q:q[0])[1]
        return None

    def snap_symbol_pose(self,symbol,size,rotation,sx,sy,ignore_uid=""):
        """Returnér ((x,y), rotation, kind) for ny placering.

        Vægmonterede symboler orienteres automatisk efter den væg der fanges.
        Dette er afgørende på lodrette vægge: uden rotation ville stikkontaktens
        stamme ligge *langs* væggen i stedet for at ende vinkelret på den.
        """
        raw=self.screen_to_cad(sx,sy); origin=(float(raw[0]),float(raw[1])); rot=float(rotation)%360.0; kinds=[]
        # Hvis cursoren er tæt på en væg, orientér først symbolet efter væggen.
        cursor_wall=self._wall_snap_candidate_screen(sx,sy,SNAP_WALL_TOLERANCE_PX) if self.snap_to_walls.get() else None
        if cursor_wall is not None and _is_wall_device(symbol):
            rot=wall_device_rotation_for_wall(symbol,rot,cursor_wall[4])
        mate=self._symbol_mate_candidate(symbol,size,rot,origin,0.0,ignore_uid)
        if mate:
            origin,kind=mate; kinds.append(kind)
            # Hvis vi sætter vægudstyr sammen, arver det faste symbols rotation.
            if _is_wall_device(symbol):
                ignore_uids={ignore_uid} if isinstance(ignore_uid,str) and ignore_uid else set(ignore_uid or ())
                nearest=None; nd=float("inf")
                for i in self._placement_candidate_indices_cad(origin[0],origin[1],max(float(size)*3.0,1.0)):
                    p=self.placements[i]
                    if p.uid in ignore_uids or not _is_wall_device(p.symbol):continue
                    d=math.hypot(p.x-origin[0],p.y-origin[1])
                    if d<nd:nearest=p;nd=d
                if nearest is not None:
                    rot=float(nearest.rotation)%360.0
                    remate=self._symbol_mate_candidate(symbol,size,rot,raw,0.0,ignore_uid)
                    if remate:origin=remate[0]
            if self.snap_to_walls.get():
                wall_result=self._snap_mount_point_to_wall_screen(symbol,size,rot,origin,None,False)
                if wall_result is not None:
                    # Brug den faktiske vægvinkel til den endelige orientering.
                    if _is_wall_device(symbol):
                        rot2=wall_device_rotation_for_wall(symbol,rot,wall_result[1][4])
                        if abs(_angular_distance_deg(rot2,rot))>1e-9:
                            rot=rot2
                            remate=self._symbol_mate_candidate(symbol,size,rot,raw,0.0,ignore_uid)
                            if remate:origin=remate[0]
                            wall_result=self._snap_mount_point_to_wall_screen(symbol,size,rot,origin,None,False)
                    if wall_result is not None:origin=wall_result[0]; kinds.append("væg/CAD")
        elif self.snap_to_walls.get():
            wall_result=self._snap_mount_point_to_wall_screen(symbol,size,rot,origin,(sx,sy),True)
            if wall_result is not None:
                if _is_wall_device(symbol):
                    rot2=wall_device_rotation_for_wall(symbol,rot,wall_result[1][4])
                    if abs(_angular_distance_deg(rot2,rot))>1e-9:
                        rot=rot2
                        wall_result=self._snap_mount_point_to_wall_screen(symbol,size,rot,origin,(sx,sy),True)
                if wall_result is not None:origin=wall_result[0]; kinds.append("væg/CAD")
        return origin,rot," + ".join(dict.fromkeys(kinds)) if kinds else "fri"

    def snap_symbol_origin(self,symbol,size,rotation,sx,sy,ignore_uid=""):
        origin,_rot,kind=self.snap_symbol_pose(symbol,size,rotation,sx,sy,ignore_uid)
        return origin,kind

    def snap_symbol_cad_pose(self,symbol,size,rotation,origin,ignore_uid="",cursor_cad=None,cursor_screen=None,auto_orient=True):
        """Returnér ((x,y), rotation, kind) ved flytning af et symbol."""
        current=(float(origin[0]),float(origin[1])); rot=float(rotation)%360.0; kinds=[]
        if cursor_screen is None and cursor_cad is not None:
            cursor_screen=self.cad_to_screen(float(cursor_cad[0]),float(cursor_cad[1]))
        if auto_orient and cursor_screen is not None and self.snap_to_walls.get() and _is_wall_device(symbol):
            wall=self._wall_snap_candidate_screen(cursor_screen[0],cursor_screen[1],SNAP_WALL_TOLERANCE_PX)
            if wall is not None:rot=wall_device_rotation_for_wall(symbol,rot,wall[4])
        mate=self._symbol_mate_candidate(symbol,size,rot,current,0.0,ignore_uid)
        if mate:
            current,kind=mate;kinds.append(kind)
            if self.snap_to_walls.get():
                wall_result=self._snap_mount_point_to_wall_screen(symbol,size,rot,current,None,False)
                if wall_result is not None:current=wall_result[0];kinds.append("væg/CAD")
        elif self.snap_to_walls.get():
            wall_result=self._snap_mount_point_to_wall_screen(symbol,size,rot,current,cursor_screen,True)
            if wall_result is not None:
                if auto_orient and _is_wall_device(symbol):
                    rot2=wall_device_rotation_for_wall(symbol,rot,wall_result[1][4])
                    if abs(_angular_distance_deg(rot2,rot))>1e-9:
                        rot=rot2
                        wall_result=self._snap_mount_point_to_wall_screen(symbol,size,rot,current,cursor_screen,True)
                if wall_result is not None:current=wall_result[0];kinds.append("væg/CAD")
        return current,rot," + ".join(dict.fromkeys(kinds)) if kinds else "fri"

    def snap_symbol_cad_origin(self,symbol,size,rotation,origin,ignore_uid="",cursor_cad=None,cursor_screen=None):
        # Små headless unit-tests konstruerer objektet uden et Tk/canvas-transform.
        # Bevar en ren CAD-space fallback til disse og til eventuelle integrationskald.
        if not all(n in self.__dict__ for n in ("offset_x","offset_y","extent","view_scale")):
            current=(float(origin[0]),float(origin[1])); kinds=[]
            tol=SNAP_TOLERANCE_PX/max(float(getattr(self,"view_scale",1.0) or 1.0),1e-12)
            wall_tol=SNAP_WALL_TOLERANCE_PX/max(float(getattr(self,"view_scale",1.0) or 1.0),1e-12)
            mate=self._symbol_mate_candidate(symbol,size,rotation,current,tol,ignore_uid)
            if mate:current,kind=mate;kinds.append(kind)
            elif self.snap_to_walls.get():
                q=self._snap_mount_point_to_wall(symbol,size,rotation,current,wall_tol,cursor_cad,True)
                if q is not None:current=q;kinds.append("væg/CAD")
            return current," + ".join(dict.fromkeys(kinds)) if kinds else "fri"
        current,_rot,kind=self.snap_symbol_cad_pose(symbol,size,rotation,origin,ignore_uid,cursor_cad,cursor_screen,auto_orient=False)
        return current,kind

    def clear_snap_feedback(self):
        try:self.canvas.delete("snap_feedback")
        except Exception:pass
        self.snap_feedback_kind=""
        self._update_canvas_cursor()

    def draw_symbol_snap_feedback(self,symbol,size,rotation,origin,kind="",ignore_uids=None,show_preview=False):
        """PowerPoint-lignende hjælpelinjer og et diskret live snap-preview."""
        self.clear_snap_feedback()
        ignore=set(ignore_uids or ())
        ox,oy=origin; sites=symbol_mating_sites(symbol,size); mc=sites["center"]
        mcx,mcy=rotate_point(mc[0],mc[1],rotation); mcx+=ox; mcy+=oy
        msx,msy=self.cad_to_screen(mcx,mcy)
        x_best=None; y_best=None
        helper_radius=max(float(size)*4.0,20.0/max(float(getattr(self,"view_scale",1.0) or 1.0),1e-12))
        for i in self._placement_candidate_indices_cad(ox,oy,helper_radius):
            p=self.placements[i]
            if p.uid in ignore or not self.layer_visibility.get(symbol_layer(p.symbol),True):continue
            fc=placement_mating_sites(p)["center"]; fsx,fsy=self.cad_to_screen(*fc)
            dx=abs(fsx-msx); dy=abs(fsy-msy)
            if dx<=7 and (x_best is None or dx<x_best[0]):x_best=(dx,fsx,fsy)
            if dy<=7 and (y_best is None or dy<y_best[0]):y_best=(dy,fsx,fsy)
        if x_best:
            x=x_best[1]; y1=min(msy,x_best[2])-45; y2=max(msy,x_best[2])+45
            self.canvas.create_line(x,y1,x,y2,fill=self._theme_color("accent"),dash=(4,3),width=1,tags=("snap_feedback",))
        if y_best:
            y=y_best[2]; x1=min(msx,y_best[1])-45; x2=max(msx,y_best[1])+45
            self.canvas.create_line(x1,y,x2,y,fill=self._theme_color("accent"),dash=(4,3),width=1,tags=("snap_feedback",))

        if show_preview:
            cx,cy=self.cad_to_screen(ox,oy); pen=self._theme_color("muted")
            def scr(lx,ly):
                lx,ly=rotate_point(lx,ly,rotation); return cx+lx*self.view_scale,cy-ly*self.view_scale
            for prim in symbol_primitives(symbol,size):
                typ=prim[0]
                try:
                    if typ=="line":self.canvas.create_line(*scr(prim[1],prim[2]),*scr(prim[3],prim[4]),fill=pen,width=1,dash=(3,2),tags=("snap_feedback",))
                    elif typ=="circle":
                        _,x,y,r=prim; sx,sy=scr(x,y); rr=r*self.view_scale; self.canvas.create_oval(sx-rr,sy-rr,sx+rr,sy+rr,outline=pen,width=1,dash=(3,2),tags=("snap_feedback",))
                    elif typ=="arc":
                        _,x,y,r,a1,a2=prim; pts=[]; steps=max(10,int(abs(a2-a1)/8))
                        for j in range(steps+1):
                            a=math.radians(a1+(a2-a1)*j/steps); pts.extend(scr(x+r*math.cos(a),y+r*math.sin(a)))
                        self.canvas.create_line(*pts,fill=pen,width=1,dash=(3,2),tags=("snap_feedback",))
                    elif typ=="polyline":
                        pts=[]
                        for x,y in prim[1]:pts.extend(scr(x,y))
                        if len(pts)>=4:self.canvas.create_line(*pts,fill=pen,width=1,dash=(3,2),tags=("snap_feedback",))
                    elif typ=="text":
                        _,x,y,t,h=prim; sx,sy=scr(x,y); fs=max(7,min(28,int(h*self.view_scale*.8))); self.canvas.create_text(sx,sy,text=t,fill=pen,font=("Segoe UI",fs,"bold"),tags=("snap_feedback",))
                except tk.TclError:pass
        if kind and kind!="fri":
            mx,my=ox,oy
            if "væg" in kind.lower() or "CAD" in kind:
                local=symbol_mount_points(symbol,size)
                if local:
                    lx,ly=rotate_point(local[0][0],local[0][1],rotation); mx,my=ox+lx,oy+ly
            sx,sy=self.cad_to_screen(mx,my); label="SYMBOL" if "symbol" in kind else ("VÆG" if "væg" in kind.lower() or "CAD" in kind else "SNAP")
            self.canvas.create_oval(sx-7,sy-7,sx+7,sy+7,fill=self._theme_color("canvas"),outline=self._theme_color("snap"),width=2,tags=("snap_feedback",))
            self.canvas.create_line(sx-4,sy,sx+4,sy,fill=self._theme_color("snap"),width=2,tags=("snap_feedback",))
            self.canvas.create_line(sx,sy-4,sx,sy+4,fill=self._theme_color("snap"),width=2,tags=("snap_feedback",))
            self.canvas.create_text(sx+11,sy-10,text=label,anchor="sw",fill=self._theme_color("snap_text"),font=("Segoe UI",8,"bold"),tags=("snap_feedback",))
        self.canvas.tag_raise("snap_feedback")
        self.snap_feedback_kind=kind
        self._update_canvas_cursor(kind)

    def _orthogonal_tail(self,start,target):
        """Returnér punkter efter start, så forbindelsen bliver rent 90°."""
        tx,ty=target; sx,sy=start
        if not self.cable_orthogonal.get() or abs(tx-sx)<1e-12 or abs(ty-sy)<1e-12:
            return [(tx,ty)]
        dx,dy=tx-sx,ty-sy
        elbow=(tx,sy) if abs(dx)>=abs(dy) else (sx,ty)
        return [elbow,(tx,ty)]

    # -------------------------------------------------------------- FREE TEXT
    def start_text_tool(self):
        if not self.doc:
            messagebox.showinfo("Tekst","Åbn først en tegning.")
            return
        win=tk.Toplevel(self); win.title("Tilføj tekst"); win.transient(self); win.resizable(False,False)
        frm=ttk.Frame(win,padding=12); frm.pack(fill="both",expand=True)
        text_var=tk.StringVar(value=self.text_content.get() or "Rum")
        height_var=tk.DoubleVar(value=float(self.default_text_height))
        rot_var=tk.DoubleVar(value=0.0)
        color_var=tk.StringVar(value=self.default_text_color)
        ttk.Label(frm,text="Tekst").grid(row=0,column=0,sticky="w")
        ent=ttk.Entry(frm,textvariable=text_var,width=34); ent.grid(row=1,column=0,columnspan=2,sticky="ew",pady=(2,7)); ent.select_range(0,"end"); ent.focus_set()
        ttk.Label(frm,text="Teksthøjde [tegneenheder]").grid(row=2,column=0,sticky="w")
        ttk.Entry(frm,textvariable=height_var,width=12).grid(row=3,column=0,sticky="ew",pady=(2,7),padx=(0,5))
        ttk.Label(frm,text="Rotation").grid(row=2,column=1,sticky="w")
        ttk.Combobox(frm,textvariable=rot_var,values=[0,45,90,135,180,225,270,315],width=10).grid(row=3,column=1,sticky="ew",pady=(2,7))
        swatch=tk.Label(frm,text="Farve",relief="sunken",bd=1,width=12,background=normalize_hex_color(color_var.get()))
        swatch.grid(row=4,column=0,sticky="ew",pady=(1,8))
        def choose():
            c=colorchooser.askcolor(color=normalize_hex_color(color_var.get()),title="Vælg tekstfarve",parent=win)[1]
            if c:
                color_var.set(normalize_hex_color(c)); swatch.configure(background=color_var.get())
        ttk.Button(frm,text="Vælg farve…",command=choose).grid(row=4,column=1,sticky="ew",pady=(1,8))
        def go(event=None):
            text=text_var.get().strip()
            try:h=float(height_var.get()); r=float(rot_var.get() or 0.0)
            except Exception:
                messagebox.showerror("Tekst","Angiv en gyldig teksthøjde og rotation.",parent=win); return
            if not text or not math.isfinite(h) or h<=0:
                messagebox.showerror("Tekst","Skriv en tekst og angiv en positiv teksthøjde.",parent=win); return
            self.text_content.set(text); self.text_height.set(h); self.text_rotation.set(r); self.text_color.set(normalize_hex_color(color_var.get()))
            self.default_text_height=h; self.default_text_color=self.text_color.get()
            self._clear_symbol_selection(); self.selected_cable_index=None; self.selected_text_index=None
            self.mode="text"; self._update_mode_status(); self.redraw_placements(); win.destroy()
            self.status_var.set(f"Placér tekst '{text}': klik på tegningen · Esc afslutter.")
        ttk.Button(frm,text="Placér tekst",command=go).grid(row=5,column=0,columnspan=2,sticky="ew")
        win.bind("<Return>",go)

    def edit_selected_text(self):
        if self.selected_text_index is None or not (0<=self.selected_text_index<len(self.texts)):return
        item=self.texts[self.selected_text_index]
        win=tk.Toplevel(self); win.title("Redigér tekst"); win.transient(self); win.resizable(False,False)
        frm=ttk.Frame(win,padding=12); frm.pack(fill="both",expand=True)
        tv=tk.StringVar(value=item.text); hv=tk.DoubleVar(value=item.height); rv=tk.DoubleVar(value=item.rotation); cv=tk.StringVar(value=item.color)
        ttk.Label(frm,text="Tekst").grid(row=0,column=0,sticky="w"); e=ttk.Entry(frm,textvariable=tv,width=34); e.grid(row=1,column=0,columnspan=2,sticky="ew",pady=(2,7)); e.select_range(0,"end"); e.focus_set()
        ttk.Label(frm,text="Teksthøjde").grid(row=2,column=0,sticky="w"); ttk.Entry(frm,textvariable=hv,width=12).grid(row=3,column=0,sticky="ew",padx=(0,5),pady=(2,7))
        ttk.Label(frm,text="Rotation").grid(row=2,column=1,sticky="w"); ttk.Combobox(frm,textvariable=rv,values=[0,45,90,135,180,225,270,315],width=10).grid(row=3,column=1,sticky="ew",pady=(2,7))
        sw=tk.Label(frm,text="Farve",relief="sunken",bd=1,background=normalize_hex_color(cv.get())); sw.grid(row=4,column=0,sticky="ew",pady=(1,8))
        def choose():
            c=colorchooser.askcolor(color=normalize_hex_color(cv.get()),title="Vælg tekstfarve",parent=win)[1]
            if c:cv.set(normalize_hex_color(c)); sw.configure(background=cv.get())
        ttk.Button(frm,text="Vælg farve…",command=choose).grid(row=4,column=1,sticky="ew",pady=(1,8))
        def save(event=None):
            text=tv.get().strip()
            try:h=float(hv.get()); r=float(rv.get() or 0.0)
            except Exception:return messagebox.showerror("Tekst","Ugyldig teksthøjde eller rotation.",parent=win)
            if not text or h<=0:return messagebox.showerror("Tekst","Tekst og positiv højde er påkrævet.",parent=win)
            before=self._capture_edit_state(); item.text=text; item.height=h; item.rotation=r; item.color=normalize_hex_color(cv.get()); self._commit_history("Redigér tekst",before); win.destroy(); self.redraw_placements()
        ttk.Button(frm,text="Gem",command=save).grid(row=5,column=0,columnspan=2,sticky="ew"); win.bind("<Return>",save)

    # ------------------------------------------------------------ CABLE DRAW
    def _next_cable_id(self, layer: str) -> str:
        prefix="K" if layer==CABLE_LAYER else "L"
        used=[]
        for cable in self.cables:
            cid=str(getattr(cable,"cable_id","") or "").upper().strip()
            if cid.startswith(prefix) and cid[len(prefix):].isdigit():used.append(int(cid[len(prefix):]))
        return f"{prefix}{(max(used,default=0)+1):02d}"

    def _load_selected_cable_controls(self):
        if self.selected_cable_index is None:return
        c=self.cables[self.selected_cable_index]
        self.cable_type.set("Ledning" if c.layer==WIRE_LAYER else "Kabel")
        self.cable_line_width.set(float(c.line_width)); self.cable_label.set(str(getattr(c,"label","") or ""))
        self.cable_spec.set(str(getattr(c,"cable_spec","3G1,5") or "")); self.cable_auto_label.set(bool(getattr(c,"auto_label",True)))
        self.cable_orthogonal.set(bool(getattr(c,"orthogonal",False)))

    def _apply_cable_settings_to_selected(self):
        if self.selected_cable_index is None:return
        before=self._capture_edit_state(); c=self.cables[self.selected_cable_index]
        old_layer=c.layer; new_layer=CABLE_TYPES.get(self.cable_type.get(),CABLE_LAYER)
        c.layer=new_layer; c.line_width=float(self.cable_line_width.get()); c.label=self.cable_label.get().strip()
        c.cable_spec=self.cable_spec.get().strip(); c.auto_label=bool(self.cable_auto_label.get()); c.orthogonal=bool(self.cable_orthogonal.get())
        if c.auto_label and (not c.cable_id or (old_layer!=new_layer)):
            c.cable_id=self._next_cable_id(new_layer)
        self._commit_history("Redigér kabel/ledning",before); self.redraw_placements()

    def show_cable_settings(self):
        if self.selected_cable_index is not None:self._load_selected_cable_controls()
        win=tk.Toplevel(self); win.title("Redigér kabel / ledning" if self.selected_cable_index is not None else "Kabel / ledning"); win.transient(self); win.resizable(False,False)
        f=ttk.Frame(win,padding=14); f.pack(fill="both",expand=True); f.columnconfigure(1,weight=1)
        ttk.Label(f,text="Type").grid(row=0,column=0,sticky="w",pady=4)
        type_combo=ttk.Combobox(f,textvariable=self.cable_type,values=list(CABLE_TYPES),state="readonly",width=22); type_combo.grid(row=0,column=1,sticky="ew",pady=4)
        ttk.Label(f,text="Kabeltype / lederantal").grid(row=1,column=0,sticky="w",pady=4)
        ttk.Combobox(f,textvariable=self.cable_spec,values=list(CABLE_SPEC_PRESETS),width=22).grid(row=1,column=1,sticky="ew",pady=4)
        ttk.Label(f,text="Linjetykkelse [mm]").grid(row=2,column=0,sticky="w",pady=4)
        ttk.Entry(f,textvariable=self.cable_line_width,width=12).grid(row=2,column=1,sticky="ew",pady=4)
        ttk.Checkbutton(f,text="Automatisk mærkning (K01 · 3G1,5)",variable=self.cable_auto_label).grid(row=3,column=0,columnspan=2,sticky="w",pady=(4,2))
        ttk.Label(f,text="Ekstra mærkning (valgfri)").grid(row=4,column=0,sticky="w",pady=4)
        ttk.Entry(f,textvariable=self.cable_label,width=24).grid(row=4,column=1,sticky="ew",pady=4)
        layer_text=tk.StringVar(value=f"CAD-lag: {CABLE_TYPES[self.cable_type.get()]}")
        ttk.Label(f,textvariable=layer_text,style="Muted.TLabel").grid(row=5,column=0,columnspan=2,sticky="w",pady=(2,4))
        ttk.Checkbutton(f,text="Ortogonal tegning (auto 90°)",variable=self.cable_orthogonal).grid(row=6,column=0,columnspan=2,sticky="w",pady=2)
        ttk.Checkbutton(f,text="Snap til symboler / forbindelsespunkter",variable=self.snap_to_symbols).grid(row=7,column=0,columnspan=2,sticky="w",pady=2)
        ttk.Checkbutton(f,text="Snap til synlige vægge/CAD-linjer",variable=self.snap_to_walls).grid(row=8,column=0,columnspan=2,sticky="w",pady=(2,4))
        if self.selected_cable_index is not None:
            c=self.cables[self.selected_cable_index]
            ttk.Label(f,text=f"Aktuel automatisk ID: {c.cable_id or '(tildeles ved OK)'}",style="Muted.TLabel").grid(row=9,column=0,columnspan=2,sticky="w",pady=(2,4))
            ttk.Label(f,text="Tip: vælg kablet og træk de blå knækpunkter direkte i tegningen.",style="Muted.TLabel",wraplength=330).grid(row=10,column=0,columnspan=2,sticky="w",pady=(0,6))
        def type_changed(event=None):layer_text.set(f"CAD-lag: {CABLE_TYPES.get(self.cable_type.get(),CABLE_LAYER)}")
        type_combo.bind("<<ComboboxSelected>>",type_changed)
        def close():
            if not self.validate_cable_settings(True):return
            if self.selected_cable_index is not None:self._apply_cable_settings_to_selected()
            win.destroy()
        ttk.Button(f,text="OK",command=close).grid(row=11,column=0,columnspan=2,sticky="e")

    def validate_cable_settings(self,show_error=False):
        try:
            lw=float(self.cable_line_width.get())
            if not math.isfinite(lw) or lw<=0 or lw>5.0:raise ValueError
        except Exception:
            if show_error:messagebox.showerror("Kabel / ledning","Angiv en linjetykkelse mellem 0 og 5 mm.")
            return False
        if self.cable_type.get() not in CABLE_TYPES:self.cable_type.set("Kabel")
        if self.cable_auto_label.get() and not self.cable_spec.get().strip():
            if show_error:messagebox.showerror("Kabel / ledning","Angiv en kabeltype, f.eks. 3G1,5 eller 5G2,5, når automatisk mærkning er aktiv.")
            return False
        return True

    def _annotation_symbol_index_at(self, sx: int, sy: int):
        """Find symbol-ejeren af den synlige mærkning under musemarkøren."""
        try:
            cx=float(self.canvas.canvasx(sx)); cy=float(self.canvas.canvasy(sy))
            items=list(self.canvas.find_overlapping(cx-3,cy-3,cx+3,cy+3))
        except Exception:
            return None
        for item in reversed(items):
            tags=self.canvas.gettags(item)
            if "annotation" not in tags:
                continue
            for tag in tags:
                if tag.startswith("sym") and tag[3:].isdigit():
                    idx=int(tag[3:])
                    if 0<=idx<len(self.placements):
                        return idx
        return None

    def edit_symbol_annotation_inline(self, index: int, event=None):
        """Kompakt mærkningseditor åbnet direkte fra annotationen."""
        if not (0<=index<len(self.placements)):
            return
        pl=self.placements[index]
        if bool(getattr(pl,"locked",False)):
            self.status_var.set("Symbolet er låst. Lås det op før mærkningen ændres.")
            return
        win=tk.Toplevel(self); win.title("Redigér mærkning"); win.transient(self)
        win.resizable(False,False)
        f=ttk.Frame(win,padding=10); f.pack(fill="both",expand=True)
        label_v=tk.StringVar(value=pl.label); group_v=tk.StringVar(value=pl.group)
        row=0
        ttk.Label(f,text=symbol_display_name(pl.symbol),style="Section.TLabel").grid(row=row,column=0,columnspan=2,sticky="w",pady=(0,7)); row+=1
        if is_combo_symbol(pl.symbol) and normalize_combo_label_mode(getattr(pl,"label_mode","Fælles"))=="Opdelt":
            sw_l=tk.StringVar(value=getattr(pl,"switch_label","") or ""); sw_g=tk.StringVar(value=getattr(pl,"switch_group","") or "")
            so_l=tk.StringVar(value=getattr(pl,"socket_label","") or ""); so_g=tk.StringVar(value=getattr(pl,"socket_group","") or "")
            ttk.Label(f,text="Afbryder(e) mærkning").grid(row=row,column=0,sticky="w",pady=2); ttk.Entry(f,textvariable=sw_l,width=28).grid(row=row,column=1,sticky="ew",pady=2); row+=1
            ttk.Label(f,text="Afbryder(e) gruppe").grid(row=row,column=0,sticky="w",pady=2); ttk.Entry(f,textvariable=sw_g,width=28).grid(row=row,column=1,sticky="ew",pady=2); row+=1
            if combo_socket_kind(pl.symbol)!="none":
                ttk.Label(f,text="Stik mærkning").grid(row=row,column=0,sticky="w",pady=2); ttk.Entry(f,textvariable=so_l,width=28).grid(row=row,column=1,sticky="ew",pady=2); row+=1
                ttk.Label(f,text="Stik gruppe").grid(row=row,column=0,sticky="w",pady=2); ttk.Entry(f,textvariable=so_g,width=28).grid(row=row,column=1,sticky="ew",pady=2); row+=1
        else:
            sw_l=sw_g=so_l=so_g=None
            ttk.Label(f,text="Mærkning").grid(row=row,column=0,sticky="w",pady=2); e1=ttk.Entry(f,textvariable=label_v,width=28); e1.grid(row=row,column=1,sticky="ew",pady=2); row+=1
            ttk.Label(f,text="Gruppe/kreds").grid(row=row,column=0,sticky="w",pady=2); ttk.Entry(f,textvariable=group_v,width=28).grid(row=row,column=1,sticky="ew",pady=2); row+=1
        f.columnconfigure(1,weight=1)
        buttons=ttk.Frame(f); buttons.grid(row=row,column=0,columnspan=2,sticky="e",pady=(9,0))
        def save_and_close(event_=None):
            before=self._capture_edit_state()
            if sw_l is not None:
                pl.switch_label=sw_l.get().strip(); pl.switch_group=sw_g.get().strip(); pl.socket_label=so_l.get().strip(); pl.socket_group=so_g.get().strip()
            else:
                pl.label=label_v.get().strip(); pl.group=group_v.get().strip()
            self._commit_history("Redigér mærkning",before)
            self._set_symbol_selection([index]); self._load_selected_symbol_controls(); self.redraw_placements(); self.status_var.set("Mærkning opdateret.")
            win.destroy()
        ttk.Button(buttons,text="Annuller",command=win.destroy).pack(side="left",padx=(0,5))
        ttk.Button(buttons,text="Gem",command=save_and_close,style="Primary.TButton").pack(side="left")
        win.bind("<Escape>",lambda e:win.destroy()); win.bind("<Return>",save_and_close)
        try:
            if event is not None:
                x=int(getattr(event,"x_root",self.winfo_rootx()+int(event.x)))+12
                y=int(getattr(event,"y_root",self.winfo_rooty()+int(event.y)))+12
            else:
                x=self.winfo_rootx()+120; y=self.winfo_rooty()+120
            win.geometry(f"+{x}+{y}")
        except Exception:
            pass
        try:
            next(w for w in f.winfo_children() if isinstance(w,ttk.Entry)).focus_set()
        except Exception:
            pass

    def _selected_spot_indices(self):
        return [i for i in self._valid_selected_indices() if 0<=i<len(self.placements) and self.placements[i].symbol=="spot" and not bool(getattr(self.placements[i],"locked",False))]

    def _normalise_spot_size(self, value):
        try:v=float(value)
        except Exception:v=float(self.spot_default_size)
        return max(20.0,min(5000.0,v))

    def apply_spot_size_value(self, silent=False):
        value=self._normalise_spot_size(self.spot_size_var.get())
        self.spot_default_size=value; self.spot_size_var.set(round(value,2))
        indices=self._selected_spot_indices()
        if indices:
            before=self._capture_edit_state(); changed=0
            for i in indices:
                if abs(float(self.placements[i].size)-value)>1e-9:
                    self.placements[i].size=value; changed+=1
            if changed:
                self._commit_history(f"Skift spotstørrelse på {changed} spots",before); self.redraw_placements(); self._set_dirty(True)
                if self.selected_index is not None and self.selected_index in indices:self.symbol_size.set(value)
                if not silent:self.status_var.set(f"Spotstørrelse {value:g}: {changed} valgte spots ændret.")
            elif not silent:self.status_var.set(f"Spotstørrelse {value:g}: bruges til nye spots.")
        elif not silent:
            self.status_var.set(f"Spotstørrelse {value:g}: bruges til nye spots og spotmønstre.")
        self._save_runtime_settings()
        return value

    def adjust_spot_size(self, factor):
        value=self._normalise_spot_size(self.spot_size_var.get())
        # Afrund til 5 tegneenheder, så gentagne +/- klik giver pæne værdier.
        value=max(20.0,round((value*float(factor))/5.0)*5.0)
        self.spot_size_var.set(value); self.apply_spot_size_value()

    def start_spot_row_tool(self):
        if not self.doc:
            self.status_var.set("Åbn først en plantegning."); return
        dlg=tk.Toplevel(self); dlg.title("Spot-række"); dlg.transient(self); dlg.resizable(False,False)
        frame=ttk.Frame(dlg,padding=12); frame.pack(fill="both",expand=True)
        ttk.Label(frame,text="Placér spots på en ret linje",style="Section.TLabel").grid(row=0,column=0,columnspan=2,sticky="w",pady=(0,8))
        ttk.Label(frame,text="Antal spots").grid(row=1,column=0,sticky="w",pady=3)
        count_v=tk.IntVar(value=max(2,min(24,int(self.spot_row_count.get() or 4))))
        spin=ttk.Spinbox(frame,from_=2,to=24,textvariable=count_v,width=8); spin.grid(row=1,column=1,sticky="w",pady=3)
        ttk.Label(frame,text="Spotstørrelse").grid(row=2,column=0,sticky="w",pady=3)
        size_v=tk.DoubleVar(value=float(self.spot_default_size)); ttk.Entry(frame,textvariable=size_v,width=10).grid(row=2,column=1,sticky="w",pady=3)
        link_v=tk.BooleanVar(value=bool(self.spot_row_link_after.get()))
        ttk.Checkbutton(frame,text="Tilknyt rækken til et lampested bagefter",variable=link_v).grid(row=3,column=0,columnspan=2,sticky="w",pady=(5,7))
        ttk.Label(frame,text="Klik start og slut på tegningen. Spots fordeles med ens afstand langs linjen.",style="Muted.TLabel",wraplength=330).grid(row=4,column=0,columnspan=2,sticky="w")
        btns=ttk.Frame(frame); btns.grid(row=5,column=0,columnspan=2,sticky="e",pady=(10,0))
        def go():
            try:count=max(2,min(24,int(count_v.get())))
            except Exception:count=4
            self.spot_row_count.set(count); self.spot_row_link_after.set(bool(link_v.get()))
            self.spot_default_size=self._normalise_spot_size(size_v.get()); self.spot_size_var.set(self.spot_default_size); self._save_runtime_settings()
            self.spot_row_start=None; self.spot_row_preview_end=None; self.spot_row_pending_uids=[]
            self.mode="spot_line"; self._update_mode_status(); self._clear_symbol_selection(); self.selected_cable_index=None; self.selected_text_index=None
            self.canvas.delete("spot_row_preview"); self.status_var.set("Spot-række: klik første punkt på linjen. Esc afslutter."); dlg.destroy()
        ttk.Button(btns,text="Annuller",command=dlg.destroy).pack(side="left",padx=(0,5)); ttk.Button(btns,text="Start",command=go,style="Primary.TButton").pack(side="left")
        dlg.bind("<Return>",lambda e:go()); dlg.bind("<Escape>",lambda e:dlg.destroy())
        dlg.grab_set(); spin.focus_set()

    def _spot_row_points(self, start, end):
        n=max(2,int(self.spot_row_count.get() or 4))
        x1,y1=start; x2,y2=end
        return [(x1+(x2-x1)*i/(n-1), y1+(y2-y1)*i/(n-1)) for i in range(n)]

    def draw_spot_row_preview(self):
        self.canvas.delete("spot_row_preview")
        if self.mode!="spot_line" or self.spot_row_start is None or self.spot_row_preview_end is None:
            return
        pts=self._spot_row_points(self.spot_row_start,self.spot_row_preview_end)
        scr=[self.cad_to_screen(x,y) for x,y in pts]
        if len(scr)>1:
            flat=[v for q in scr for v in q]; self.canvas.create_line(*flat,fill=self._theme_color("accent"),dash=(4,4),width=1,tags=("spot_row_preview",))
        r=max(4,min(16,float(self.spot_default_size)*.16*self.view_scale))
        for sx,sy in scr:
            self.canvas.create_oval(sx-r,sy-r,sx+r,sy+r,outline="#d00000",width=1,tags=("spot_row_preview",))
        self.canvas.tag_raise("spot_row_preview")

    def start_spot_rect_tool(self):
        if not self.doc:
            self.status_var.set("Åbn først en plantegning."); return
        dlg=tk.Toplevel(self); dlg.title("Spot-rektangel"); dlg.transient(self); dlg.resizable(False,False)
        frame=ttk.Frame(dlg,padding=12); frame.pack(fill="both",expand=True)
        ttk.Label(frame,text="Fyld et rektangel med spots",style="Section.TLabel").grid(row=0,column=0,columnspan=2,sticky="w",pady=(0,8))
        ttk.Label(frame,text="Kolonner").grid(row=1,column=0,sticky="w",pady=3)
        cols_v=tk.IntVar(value=max(2,min(20,int(self.spot_rect_columns.get() or 3))))
        cols_spin=ttk.Spinbox(frame,from_=2,to=20,textvariable=cols_v,width=8); cols_spin.grid(row=1,column=1,sticky="w",pady=3)
        ttk.Label(frame,text="Rækker").grid(row=2,column=0,sticky="w",pady=3)
        rows_v=tk.IntVar(value=max(2,min(20,int(self.spot_rect_rows.get() or 2))))
        rows_spin=ttk.Spinbox(frame,from_=2,to=20,textvariable=rows_v,width=8); rows_spin.grid(row=2,column=1,sticky="w",pady=3)
        ttk.Label(frame,text="Spotstørrelse").grid(row=3,column=0,sticky="w",pady=3)
        size_v=tk.DoubleVar(value=float(self.spot_default_size)); ttk.Entry(frame,textvariable=size_v,width=10).grid(row=3,column=1,sticky="w",pady=3)
        link_v=tk.BooleanVar(value=bool(self.spot_rect_link_after.get()))
        ttk.Checkbutton(frame,text="Tilknyt mønstret til et lampested bagefter",variable=link_v).grid(row=4,column=0,columnspan=2,sticky="w",pady=(5,7))
        info=tk.StringVar(value="")
        ttk.Label(frame,textvariable=info,style="Muted.TLabel").grid(row=5,column=0,columnspan=2,sticky="w",pady=(0,4))
        ttk.Label(frame,text="Klik to modstående hjørner. De yderste spots placeres på de valgte hjørner, og resten fordeles jævnt.",style="Muted.TLabel",wraplength=350).grid(row=6,column=0,columnspan=2,sticky="w")
        def update_info(*_):
            try:c=max(2,min(20,int(cols_v.get()))); r=max(2,min(20,int(rows_v.get())))
            except Exception:c,r=3,2
            info.set(f"{c} × {r} = {c*r} spots")
        cols_v.trace_add("write",update_info); rows_v.trace_add("write",update_info); update_info()
        btns=ttk.Frame(frame); btns.grid(row=7,column=0,columnspan=2,sticky="e",pady=(10,0))
        def go():
            try:
                cols=max(2,min(20,int(cols_v.get()))); rows=max(2,min(20,int(rows_v.get())))
            except Exception:
                cols,rows=3,2
            if cols*rows>200:
                messagebox.showerror("Spot-rektangel","Vælg højst 200 spots pr. mønster.",parent=dlg); return
            self.spot_rect_columns.set(cols); self.spot_rect_rows.set(rows); self.spot_rect_link_after.set(bool(link_v.get()))
            self.spot_default_size=self._normalise_spot_size(size_v.get()); self.spot_size_var.set(self.spot_default_size); self._save_runtime_settings()
            self.spot_rect_start=None; self.spot_rect_preview_end=None; self.spot_row_pending_uids=[]
            self.mode="spot_rect"; self._update_mode_status(); self._clear_symbol_selection(); self.selected_cable_index=None; self.selected_text_index=None
            self.canvas.delete("spot_rect_preview"); self.status_var.set("Spot-rektangel: klik første hjørne. Esc afslutter."); dlg.destroy()
        ttk.Button(btns,text="Annuller",command=dlg.destroy).pack(side="left",padx=(0,5)); ttk.Button(btns,text="Start",command=go,style="Primary.TButton").pack(side="left")
        dlg.bind("<Return>",lambda e:go()); dlg.bind("<Escape>",lambda e:dlg.destroy())
        dlg.grab_set(); cols_spin.focus_set()

    def _spot_rect_points(self, start, end):
        cols=max(2,int(self.spot_rect_columns.get() or 3)); rows=max(2,int(self.spot_rect_rows.get() or 2))
        x1,y1=start; x2,y2=end
        pts=[]
        for row in range(rows):
            fy=row/(rows-1)
            y=y1+(y2-y1)*fy
            for col in range(cols):
                fx=col/(cols-1)
                x=x1+(x2-x1)*fx
                pts.append((x,y))
        return pts

    def draw_spot_rect_preview(self):
        self.canvas.delete("spot_rect_preview")
        if self.mode!="spot_rect" or self.spot_rect_start is None or self.spot_rect_preview_end is None:
            return
        x1,y1=self.spot_rect_start; x2,y2=self.spot_rect_preview_end
        sx1,sy1=self.cad_to_screen(x1,y1); sx2,sy2=self.cad_to_screen(x2,y2)
        self.canvas.create_rectangle(sx1,sy1,sx2,sy2,outline=self._theme_color("accent"),dash=(4,4),width=1,tags=("spot_rect_preview",))
        pts=self._spot_rect_points(self.spot_rect_start,self.spot_rect_preview_end)
        r=max(4,min(16,float(self.spot_default_size)*.16*self.view_scale))
        for x,y in pts:
            sx,sy=self.cad_to_screen(x,y)
            self.canvas.create_oval(sx-r,sy-r,sx+r,sy+r,outline="#d00000",width=1,tags=("spot_rect_preview",))
        self.canvas.tag_raise("spot_rect_preview")

    def _start_spot_parent_mode(self, spot_uids):
        self.spot_row_pending_uids=list(spot_uids)
        if not self.spot_row_pending_uids:
            self.mode="select"; self._update_mode_status(); return
        self.mode="spot_parent"; self._update_mode_status(); self.draw_spot_parent_targets()
        self.status_var.set("Spot-række: klik på et lampested (tilslutningssted for belysning). Esc springer tilknytningen over.")

    def draw_spot_parent_targets(self):
        self.canvas.delete("spot_parent_target")
        if self.mode!="spot_parent":return
        for i,p in enumerate(self.placements):
            if p.symbol!="light_connection" or not self.layer_visibility.get(symbol_layer(p.symbol),True):continue
            x1,y1,x2,y2=self.placement_screen_bbox(p,pad=6)
            self.canvas.create_rectangle(x1,y1,x2,y2,outline=self._theme_color("association"),dash=(4,3),width=2,tags=("spot_parent_target",f"sym{i}"))
        self.canvas.tag_raise("spot_parent_target")

    def _sync_spot_parent_associations(self):
        by_uid={p.uid:p for p in self.placements}
        for p in self.placements:
            parent_uid=str(getattr(p,"parent_light_uid","") or "")
            if not parent_uid:continue
            parent=by_uid.get(parent_uid)
            if parent is None or parent.symbol!="light_connection":
                p.parent_light_uid=""; continue
            p.associations=normalize_associations(getattr(parent,"associations",[]))

    def _assign_spot_parent(self, target_index):
        if not (0<=target_index<len(self.placements)):return
        target=self.placements[target_index]
        if target.symbol!="light_connection":
            self.status_var.set("Klik på et lampested (tilslutningssted for belysning)."); return
        before=self._capture_edit_state(); pending=set(self.spot_row_pending_uids)
        linked=0
        for p in self.placements:
            if p.uid in pending and p.symbol=="spot":
                p.parent_light_uid=target.uid; p.associations=normalize_associations(target.associations); linked+=1
        self._commit_history("Tilknyt spot-række til lampested",before)
        self.spot_row_pending_uids=[]; self.mode="select"; self.canvas.delete("spot_parent_target"); self._update_mode_status(); self.redraw_placements()
        extra=f" · tilhør. {association_display(target)}" if association_display(target) else " · bogstav synkroniseres når lampestedet tilknyttes en afbryder"
        self.status_var.set(f"{linked} spots tilknyttet lampested{extra}.")

    def start_cable_mode(self):
        if not self.doc:return
        if not self.validate_cable_settings(True):return
        self.apply_symbol_properties()
        self._clear_symbol_selection(); self.selected_cable_index=None; self.selected_text_index=None; self.current_cable_points=[]; self.current_cable_start_uid=""; self.current_cable_end_uid=""; self.current_cable_start_port=0; self.current_cable_end_port=0; self.cable_preview_cursor=None
        self.mode="cable"; self._update_mode_status(); self.redraw_placements(); self.draw_cable_preview()
        self.status_var.set("Kabel/ledning: klik første punkt. Ortogonal tegning og snap bruges efter valgte indstillinger.")

    def finish_cable(self):
        if self.mode!="cable":return
        if len(self.current_cable_points)<2:
            if self.current_cable_points:messagebox.showinfo("Kabel / ledning","Der skal mindst være to punkter.")
            return
        if not self.validate_cable_settings(True):return
        layer=CABLE_TYPES[self.cable_type.get()]
        cable=CablePlacement(points=[tuple(p) for p in self.current_cable_points],layer=layer,line_width=float(self.cable_line_width.get()),label=self.cable_label.get().strip(),cable_spec=self.cable_spec.get().strip(),cable_id=self._next_cable_id(layer) if self.cable_auto_label.get() else "",auto_label=bool(self.cable_auto_label.get()),start_symbol_uid=self.current_cable_start_uid,end_symbol_uid=self.current_cable_end_uid,start_symbol_port=int(self.current_cable_start_port),end_symbol_port=int(self.current_cable_end_port),orthogonal=bool(self.cable_orthogonal.get()))
        before=self._capture_edit_state()
        self.cables.append(cable); self.creation_history.append(("cable",cable))
        self._commit_history("Tilføj kabel/ledning",before)
        self.current_cable_points=[]; self.current_cable_start_uid=""; self.current_cable_end_uid=""; self.current_cable_start_port=0; self.current_cable_end_port=0; self.cable_preview_cursor=None; self.draw_cable_preview(); self.redraw_placements()
        auto=f" ({cable_display_label(cable)})" if cable_display_label(cable) else ""
        self.status_var.set(f"{self.cable_type.get()} tilføjet på lag {cable.layer}{auto}. Klik første punkt for næste forløb, eller Esc for at afslutte.")

    def cancel_cable(self):
        self.current_cable_points=[]; self.current_cable_start_uid=""; self.current_cable_end_uid=""; self.current_cable_start_port=0; self.current_cable_end_port=0; self.cable_preview_cursor=None; self.snap_marker=None; self.snap_marker_kind=""; self._set_snap_live(""); self.canvas.delete("cable_preview")

    def on_canvas_motion(self,event):
        """Throttle dyre hover/snap-beregninger til højst ca. 60 Hz."""
        x,y=int(event.x),int(event.y); self.last_canvas_mouse=(x,y); self._motion_pending=(x,y)
        now=time.perf_counter(); min_dt=1.0/60.0
        elapsed=now-self._motion_last_process
        if elapsed>=min_dt and self._motion_job is None:
            self._process_canvas_motion()
        elif self._motion_job is None:
            self._motion_job=self.after(max(1,int((min_dt-elapsed)*1000)),self._process_canvas_motion)

    def _process_canvas_motion(self):
        self._motion_job=None
        if self._motion_pending is None:return
        x,y=self._motion_pending; self._motion_pending=None; self._motion_last_process=time.perf_counter(); t0=self._motion_last_process
        self._perf_motion_count+=1
        snap_t0=None
        if self.mode=="place" and self.doc:
            try:
                code=SYMBOLS[self.symbol_name.get()]; size=float(self.spot_default_size if code=="spot" else self.default_symbol_size); rot=float(self.rotation.get() or 0.0)
                snap_t0=time.perf_counter()
                if self._alt_down:origin=self.screen_to_cad(x,y); snap_rot=rot; kind="fri"
                else:origin,snap_rot,kind=self.snap_symbol_pose(code,size,rot,x,y)
                self._perf_last_snap_ms=(time.perf_counter()-snap_t0)*1000.0
                self._set_snap_live(kind); self.draw_symbol_snap_feedback(code,size,snap_rot,origin,kind,show_preview=True)
            except Exception as exc:
                self._set_snap_live(""); self.clear_snap_feedback(); self.status_var.set(f"Snap-preview fejl: {exc}")
        elif self.mode=="cable":
            snap_t0=time.perf_counter()
            if self._alt_down:
                px,py=self.screen_to_cad(x,y); kind="fri"
            else:
                px,py,kind,_uid,_port=self.snap_point_detail(x,y)
            self._perf_last_snap_ms=(time.perf_counter()-snap_t0)*1000.0
            self._set_snap_live(kind); self.cable_preview_cursor=(px,py); self.snap_marker=(px,py) if kind!="fri" else None; self.snap_marker_kind=kind
            self._update_canvas_cursor(kind); self._schedule_cable_preview(16)
        elif self.mode=="spot_line" and self.spot_row_start is not None:
            self.spot_row_preview_end=self.screen_to_cad(x,y); self.draw_spot_row_preview()
        elif self.mode=="spot_rect" and self.spot_rect_start is not None:
            self.spot_rect_preview_end=self.screen_to_cad(x,y); self.draw_spot_rect_preview()
        elif not self.dragging:
            self._set_snap_live(""); self.clear_snap_feedback()
        self._perf_last_motion_ms=(time.perf_counter()-t0)*1000.0

    def draw_cable_preview(self):
        self.canvas.delete("cable_preview")
        if self.mode!="cable":return
        path=list(self.current_cable_points)
        if self.cable_preview_cursor is not None:
            if path:path.extend(self._orthogonal_tail(path[-1],self.cable_preview_cursor))
            else:path.append(self.cable_preview_cursor)
        pts=[]
        for x,y in path:pts.extend(self.cad_to_screen(x,y))
        if len(pts)>=4:self.canvas.create_line(*pts,fill="#d00000",width=_screen_line_width(float(self.cable_line_width.get() or .35)),dash=(5,3),tags=("scene","cable_preview"))
        for x,y in self.current_cable_points:
            sx,sy=self.cad_to_screen(x,y); self.canvas.create_oval(sx-3,sy-3,sx+3,sy+3,fill="#d00000",outline="",tags=("scene","cable_preview"))
        # Vis de egentlige forbindelsespunkter diskret i kabeltilstand.
        if self.snap_to_symbols.get():
            for p in self.placements:
                if not self.layer_visibility.get(symbol_layer(p.symbol),True):continue
                for x,y in placement_connection_points(p):
                    sx,sy=self.cad_to_screen(x,y); self.canvas.create_oval(sx-5,sy-5,sx+5,sy+5,outline=self._theme_color("snap"),width=1,tags=("scene","cable_preview"))
        if self.snap_marker is not None:
            sx,sy=self.cad_to_screen(*self.snap_marker); is_symbol=self.snap_marker_kind=="symbol"; color="#008b8b" if is_symbol else "#7b2cbf"
            self.canvas.create_oval(sx-7,sy-7,sx+7,sy+7,fill=self._theme_color("canvas"),outline=color,width=2,tags=("scene","cable_preview"))
            self.canvas.create_line(sx-4,sy,sx+4,sy,fill=color,width=2,tags=("scene","cable_preview"))
            self.canvas.create_line(sx,sy-4,sx,sy+4,fill=color,width=2,tags=("scene","cable_preview"))
            self.canvas.create_text(sx+10,sy-9,text="SYMBOL" if is_symbol else "VÆG",anchor="sw",fill=color,font=("Segoe UI",8,"bold"),tags=("scene","cable_preview"))

    def toggle_performance_diagnostics(self,event=None):
        self.perf_diagnostics=not bool(self.perf_diagnostics)
        if not self.perf_diagnostics:
            self.canvas.delete("perf_overlay")
            if self._perf_update_job is not None:
                try:self.after_cancel(self._perf_update_job)
                except Exception:pass
                self._perf_update_job=None
            self.status_var.set("Performance-diagnose skjult.")
        else:
            self._perf_window_start=time.perf_counter(); self._perf_motion_count=0
            self._update_performance_overlay()
            self.status_var.set("Performance-diagnose aktiv · Ctrl+Shift+F12 skjuler den igen.")
        return "break"

    def _update_performance_overlay(self):
        self._perf_update_job=None
        if not self.perf_diagnostics:return
        now=time.perf_counter(); dt=max(now-self._perf_window_start,1e-6)
        self._perf_fps=self._perf_motion_count/dt; self._perf_motion_count=0; self._perf_window_start=now
        try:ci=symbol_primitives.cache_info(); bi=symbol_local_bbox.cache_info()
        except Exception:ci=bi=None
        cache_txt=f"symcache {ci.hits}/{ci.misses}" if ci else "symcache —"
        info=(f"PERF  motion {self._perf_fps:4.0f} Hz · {self._perf_last_motion_ms:4.1f} ms  |  snap {self._perf_last_snap_ms:4.1f} ms\n"
              f"nav zoom {self._perf_last_zoom_ms:4.1f} ms · pan {self._perf_last_pan_ms:4.1f} ms  |  redraw {self._perf_last_redraw_ms:5.1f} · dirty {self._perf_last_dirty_redraw_ms:4.1f} ms\n"
              f"{cache_txt} · CAD {len(self.cad_primitives):,} · CAD-tekst {len(self.cad_text_items):,} · vægseg {len(self.snap_segments):,} · symboler {len(self.placements):,} · kabler {len(self.cables):,} · grid {len(self.placement_snap_grid):,}")
        self.canvas.delete("perf_overlay")
        font=("Segoe UI",8)
        tid=self.canvas.create_text(10,10,text=info,anchor="nw",justify="left",font=font,fill="#202020",tags=("perf_overlay",))
        bb=self.canvas.bbox(tid)
        if bb:
            rid=self.canvas.create_rectangle(bb[0]-5,bb[1]-4,bb[2]+5,bb[3]+4,fill="#fffdf2",outline="#888888",width=1,tags=("perf_overlay",))
            self.canvas.tag_lower(rid,tid)
        self.canvas.tag_raise("perf_overlay")
        self._perf_update_job=self.after(500,self._update_performance_overlay)

    def _focus_is_text_input(self) -> bool:
        w=self.focus_get()
        return isinstance(w,(tk.Entry,tk.Text,ttk.Entry,ttk.Combobox))

    def copy_selected_symbol(self,event=None):
        if event is not None and self._focus_is_text_input(): return None
        indices=self._valid_selected_indices()
        if not indices:
            self.status_var.set("Vælg først et eller flere symboler, der skal kopieres.")
            return "break" if event is not None else None
        if len(indices)==1 and self.selected_index is not None:
            self.apply_symbol_properties()
        selected=[self.placements[i] for i in indices]
        if len(selected)==1:
            p=selected[0]; payload=symbol_clipboard_payload(p)
            raw=asdict(p); raw["uid"]=uuid.uuid4().hex; raw["associations"]=[]; raw["association_channels"]=[]; raw["locked"]=False; raw["parent_light_uid"]=""
            self.symbol_clipboard=Placement(**raw); self.multi_symbol_clipboard=[]
            msg=f"Kopieret symbol: {symbol_display_name(p.symbol)}. Ctrl+V indsætter ved musemarkøren."
        else:
            payload=symbols_clipboard_payload(selected)
            self.multi_symbol_clipboard=[]
            for p in selected:
                raw=asdict(p); raw["uid"]=uuid.uuid4().hex; raw["associations"]=[]; raw["association_channels"]=[]; raw["locked"]=False; raw["parent_light_uid"]=""
                self.multi_symbol_clipboard.append(Placement(**raw))
            self.symbol_clipboard=None
            msg=f"Kopieret {len(selected)} symboler. Ctrl+V indsætter gruppen ved musemarkøren."
        try:
            self.clipboard_clear(); self.clipboard_append(payload); self.update_idletasks()
        except Exception:
            pass
        self.status_var.set(msg)
        return "break" if event is not None else None

    @staticmethod
    def _placements_centroid(items):
        if not items:return (0.0,0.0)
        return (sum(float(p.x) for p in items)/len(items),sum(float(p.y) for p in items)/len(items))

    def paste_symbol(self,event=None):
        if event is not None and self._focus_is_text_input(): return None
        if not self.doc:
            self.status_var.set("Åbn først en tegning.")
            return "break" if event is not None else None
        clip_text=""
        try:clip_text=self.clipboard_get()
        except Exception:pass
        group=placements_from_clipboard_payload(clip_text)
        if not group and self.multi_symbol_clipboard:
            group=[]
            for source in self.multi_symbol_clipboard:
                raw=asdict(source); raw["uid"]=uuid.uuid4().hex; raw["associations"]=[]; raw["association_channels"]=[]; raw["locked"]=False; raw["parent_light_uid"]=""; group.append(Placement(**raw))
        if group:
            if self.last_canvas_mouse is not None:
                tx,ty=self.screen_to_cad(*self.last_canvas_mouse)
            else:
                cx,cy=self._placements_centroid(group); delta=28.0/max(self.view_scale,1e-9); tx,ty=cx+delta,cy
            cx,cy=self._placements_centroid(group); dx,dy=tx-cx,ty-cy
            before=self._capture_edit_state(); first=len(self.placements); new=[]
            for source in group:
                raw=asdict(source); raw["uid"]=uuid.uuid4().hex; raw["associations"]=[]; raw["association_channels"]=[]; raw["locked"]=False; raw["parent_light_uid"]=""
                pl=Placement(**raw); pl.x+=dx; pl.y+=dy; self.placements.append(pl); self.creation_history.append(("symbol",pl)); new.append(len(self.placements)-1)
            self._commit_history("Indsæt symbolgruppe",before); self._set_symbol_selection(new); self.mode="select"; self.canvas.configure(cursor="arrow")
            self.status_var.set(f"Indsat {len(new)} symboler som gruppe. Træk gruppen for at finplacere.")
            return "break" if event is not None else None

        pl=placement_from_clipboard_payload(clip_text)
        if pl is None and self.symbol_clipboard is not None:
            raw=asdict(self.symbol_clipboard); raw["uid"]=uuid.uuid4().hex; pl=Placement(**raw)
        if pl is None:
            self.status_var.set("Clipboard indeholder ikke Elplan-symboler. Kopiér først med Ctrl+C.")
            return "break" if event is not None else None
        pl.uid=uuid.uuid4().hex; kind="fri"
        if self.last_canvas_mouse is not None:
            sx,sy=self.last_canvas_mouse
            try:
                (x,y),kind=self.snap_symbol_origin(pl.symbol,pl.size,pl.rotation,sx,sy)
                pl.x,pl.y=x,y
            except Exception:pass
        else:
            delta=28.0/max(self.view_scale,1e-9); pl.x+=delta; kind="offset"
        before=self._capture_edit_state(); self.placements.append(pl); self.creation_history.append(("symbol",pl)); self._commit_history("Indsæt symbol",before)
        idx=len(self.placements)-1; self._set_symbol_selection([idx]); self.mode="select"; self.canvas.configure(cursor="arrow")
        suffix=f" – snap: {kind}" if kind not in ("fri","offset") else ""
        self.status_var.set(f"Indsat kopi ved X={pl.x:.2f}, Y={pl.y:.2f}{suffix}. Træk for at finplacere.")
        return "break" if event is not None else None

    def duplicate_selected(self,event=None):
        """Smart duplikering af ét eller flere symboler med gentagelig afstand."""
        if event is not None and self._focus_is_text_input():return None
        indices=self._valid_selected_indices()
        if not indices:
            self.status_var.set("Vælg et eller flere symboler, der skal duplikeres.")
            return "break" if event is not None else None
        if len(indices)==1 and self.selected_index is not None:self.apply_symbol_properties()
        dx,dy=self.last_duplicate_delta or (28.0/max(self.view_scale,1e-9),0.0)
        before=self._capture_edit_state(); new_indices=[]; new_uids=set(); pending_positions={}
        for i in indices:
            source=self.placements[i]; raw=asdict(source); raw["uid"]=uuid.uuid4().hex; raw["associations"]=[]; raw["association_channels"]=[]; raw["locked"]=False; raw["parent_light_uid"]=""
            pl=Placement(**raw); pl.x+=dx; pl.y+=dy
            self.placements.append(pl); self.creation_history.append(("symbol",pl)); idx=len(self.placements)-1; new_indices.append(idx); new_uids.add(pl.uid); pending_positions[pl.uid]=(pl.x,pl.y)
        self._commit_history("Smart duplikér",before); self.last_duplicate_delta=(dx,dy)
        self._duplicate_pending_uids=new_uids; self._duplicate_pending_base_delta=(dx,dy); self._duplicate_pending_positions=pending_positions
        self._set_symbol_selection(new_indices); self.mode="select"; self.canvas.configure(cursor="arrow")
        self.status_var.set(f"Duplikeret {len(new_indices)} symbol{'er' if len(new_indices)!=1 else ''}. Flyt kopien én gang for at lære en ny gentagelsesafstand; Ctrl+D gentager.")
        return "break" if event is not None else None

    def _update_duplicate_spacing_after_move(self):
        if not self._duplicate_pending_uids or not self._duplicate_pending_base_delta:return
        current={p.uid:p for p in self.placements if p.uid in self._duplicate_pending_uids}
        if len(current)!=len(self._duplicate_pending_uids):return
        moves=[]
        for uid,p in current.items():
            old=self._duplicate_pending_positions.get(uid)
            if old:moves.append((p.x-old[0],p.y-old[1]))
        if moves:
            mdx=sum(q[0] for q in moves)/len(moves); mdy=sum(q[1] for q in moves)/len(moves)
            if math.hypot(mdx,mdy)>1e-9:
                bdx,bdy=self._duplicate_pending_base_delta; self.last_duplicate_delta=(bdx+mdx,bdy+mdy)
                self.status_var.set(f"Smart duplikering husker nu afstand ΔX={self.last_duplicate_delta[0]:.2f}, ΔY={self.last_duplicate_delta[1]:.2f}.")
        self._duplicate_pending_uids=set(); self._duplicate_pending_base_delta=None; self._duplicate_pending_positions={}


    # ------------------------------------------------------- INTERACTION/EDIT
    def set_mode(self,mode):
        self.clear_snap_feedback(); self.canvas.delete("selection_rect"); self.selection_rect_start=None; self.selection_rect_active=False
        if mode!="cable" and self.mode=="cable":self.cancel_cable()
        if mode!="associate" and self.mode=="associate":
            self.association_source_uid=""; self.canvas.delete("association_target")
        if mode=="place":
            if self.selected_index is not None:
                self.apply_symbol_properties()
                self._clear_symbol_selection(); self._restore_default_symbol_controls()
            elif self._valid_selected_indices():
                self._clear_symbol_selection(); self._restore_default_symbol_controls()
            else:
                # Bevar de værdier brugeren netop har valgt til det næste symbol.
                if not self.apply_symbol_properties(show_error=True):return
            self.selected_cable_index=None; self.selected_text_index=None
            self.mode="place"; self._update_mode_status(); self._refresh_palette_selection(); self._update_properties_panel(); self.redraw_placements()
            self.status_var.set(f"Placér {self.symbol_name.get()}: klik flere steder · Esc afslutter.")
        elif mode=="select":
            if self.selected_index is not None:self.apply_symbol_properties()
            self.mode="select"; self._update_mode_status(); self._refresh_palette_selection(); self._update_properties_panel(); self.status_var.set("Vælg symbol, tekst eller kabel. Klik og træk for at flytte.")

    def on_escape(self,event=None):
        self._set_snap_live(""); self.clear_snap_feedback(); self.canvas.delete("selection_rect"); self.selection_rect_start=None; self.selection_rect_active=False
        if self.mode=="cable":self.cancel_cable()
        if self.mode=="associate": self.association_source_uid=""; self.canvas.delete("association_target")
        if self.mode in ("spot_line","spot_rect","spot_parent"):
            self.spot_row_start=None; self.spot_row_preview_end=None; self.spot_rect_start=None; self.spot_rect_preview_end=None; self.spot_row_pending_uids=[]
            self.canvas.delete("spot_row_preview"); self.canvas.delete("spot_rect_preview"); self.canvas.delete("spot_parent_target")
        self.selected_cable_vertex_index=None; self.drag_vertex_original_index=None
        self.mode="select"; self._update_mode_status()
        if self._valid_selected_indices() or self.selected_cable_index is not None or self.selected_text_index is not None:
            self._clear_symbol_selection(); self.selected_cable_index=None; self.selected_text_index=None; self._restore_default_symbol_controls()
        self._refresh_palette_selection(); self._update_properties_panel(); self.redraw_placements() if self.doc else None
        self.status_var.set("Placering/valg afsluttet. Vælg et symbol i paletten eller et objekt på tegningen.")

    def on_double_click(self,event):
        if not self.doc or self.mode!="select":return
        annotation_i=self._annotation_symbol_index_at(event.x,event.y)
        if annotation_i is not None:
            self._set_symbol_selection([annotation_i]); self.edit_symbol_annotation_inline(annotation_i,event); return "break"
        sym_i,sym_d=self.find_symbol_at(event.x,event.y)
        text_i,text_d=self.find_text_at(event.x,event.y)
        if sym_i is not None and (text_i is None or sym_d<=text_d):
            self._set_symbol_selection([sym_i]); self.show_quick_symbol_properties(sym_i); return "break"
        if text_i is not None:
            self.selected_text_index=text_i; self._clear_symbol_selection(); self.selected_cable_index=None; self.redraw_placements(); self.edit_selected_text(); return "break"

    def toggle_selected_lock_from_panel(self):
        """Lås/lås op fra egenskabspanelet uden at ændre andre felter."""
        if self.selected_index is None or not (0<=self.selected_index<len(self.placements)):
            self.symbol_locked.set(False); return
        p=self.placements[self.selected_index]; new=bool(self.symbol_locked.get())
        if bool(getattr(p,"locked",False))==new:return
        before=self._capture_edit_state(); p.locked=new
        self._commit_history("Lås symbol" if new else "Lås symbol op",before)
        self._update_properties_panel(); self.redraw_placements()
        self.status_var.set(("Låst: " if new else "Låst op: ")+symbol_display_name(p.symbol))

    def set_symbol_locked(self, index:int, locked:bool):
        if not (0<=index<len(self.placements)):return
        p=self.placements[index]
        if bool(getattr(p,"locked",False))==bool(locked):return
        before=self._capture_edit_state(); p.locked=bool(locked)
        self._commit_history("Lås symbol" if locked else "Lås symbol op",before)
        if self.selected_index==index:self.symbol_locked.set(bool(locked))
        self._update_properties_panel(); self.redraw_placements()
        self.status_var.set(("Låst: " if locked else "Låst op: ")+symbol_display_name(p.symbol))

    def on_right_click(self,event):
        """Kontekstmenu på symboler; tomt område bruger fortsat højreklik-pan."""
        self.pan_last=None
        if not self.doc or self.mode!="select":
            self.pan_start(event); return
        i,d=self.find_symbol_at(event.x,event.y)
        if i is None:
            self.pan_start(event); return
        if i not in self._valid_selected_indices():self._set_symbol_selection([i])
        p=self.placements[i]; locked=bool(getattr(p,"locked",False))
        menu=tk.Menu(self,tearoff=False)
        menu.add_command(label="Hurtige egenskaber…",command=lambda:self.show_quick_symbol_properties(i))
        menu.add_separator()
        menu.add_command(label="Rotér +90°",command=self.rotate_selected,state="disabled" if locked else "normal")
        menu.add_command(label="Kopiér",command=self.copy_selected_symbol)
        menu.add_command(label="Smart duplikér",command=self.duplicate_selected)
        if association_role(p.symbol)=="switch":
            menu.add_command(label="Tilknyt lys…",command=self.start_association_mode,state="disabled" if locked else "normal")
        menu.add_separator()
        menu.add_command(label="Lås op" if locked else "Lås symbol",command=lambda:self.set_symbol_locked(i,not locked))
        menu.add_command(label="Slet",command=self.delete_selected,state="disabled" if locked else "normal")
        try:menu.tk_popup(event.x_root,event.y_root)
        finally:menu.grab_release()
        return "break"

    def show_quick_symbol_properties(self,index=None):
        """Kompakt egenskabsdialog ved dobbeltklik/højreklik."""
        if index is None:index=self.selected_index
        if index is None or not (0<=index<len(self.placements)):return
        self._set_symbol_selection([index]); p=self.placements[index]
        win=tk.Toplevel(self); win.title(f"Egenskaber – {symbol_display_name(p.symbol)}"); win.transient(self); win.resizable(False,False)
        try:win.geometry(f"+{self.winfo_pointerx()+12}+{self.winfo_pointery()+12}")
        except Exception:pass
        f=ttk.Frame(win,padding=12); f.pack(fill="both",expand=True); f.columnconfigure(1,weight=1)
        size=tk.DoubleVar(value=float(p.size)); lw=tk.DoubleVar(value=float(p.line_width)); rot=tk.DoubleVar(value=float(p.rotation))
        label=tk.StringVar(value=p.label); group=tk.StringVar(value=p.group); color=tk.StringVar(value=normalize_hex_color(p.color)); locked=tk.BooleanVar(value=bool(getattr(p,"locked",False)))
        combo_mode=tk.StringVar(value=normalize_combo_label_mode(getattr(p,"label_mode","Fælles")))
        combo_sw_label=tk.StringVar(value=getattr(p,"switch_label","") or ""); combo_sw_group=tk.StringVar(value=getattr(p,"switch_group","") or "")
        combo_so_label=tk.StringVar(value=getattr(p,"socket_label","") or ""); combo_so_group=tk.StringVar(value=getattr(p,"socket_group","") or "")
        ttk.Label(f,text="Størrelse").grid(row=0,column=0,sticky="w",pady=3); e_size=ttk.Entry(f,textvariable=size,width=18); e_size.grid(row=0,column=1,sticky="ew",pady=3)
        ttk.Label(f,text="Linjetykkelse [mm]").grid(row=1,column=0,sticky="w",pady=3); e_lw=ttk.Entry(f,textvariable=lw,width=18); e_lw.grid(row=1,column=1,sticky="ew",pady=3)
        ttk.Label(f,text="Rotation [°]").grid(row=2,column=0,sticky="w",pady=3); e_rot=ttk.Combobox(f,textvariable=rot,values=[0,45,90,135,180,225,270,315],width=15); e_rot.grid(row=2,column=1,sticky="ew",pady=3)
        ttk.Label(f,text="Mærkning").grid(row=3,column=0,sticky="w",pady=3); e_label=ttk.Entry(f,textvariable=label,width=18); e_label.grid(row=3,column=1,sticky="ew",pady=3)
        ttk.Label(f,text="Gruppe/kreds").grid(row=4,column=0,sticky="w",pady=3); e_group=ttk.Entry(f,textvariable=group,width=18); e_group.grid(row=4,column=1,sticky="ew",pady=3)
        combo_frame=ttk.LabelFrame(f,text="Kombi-mærkning",padding=5)
        combo_frame.grid(row=5,column=0,columnspan=2,sticky="ew",pady=(5,3))
        combo_frame.columnconfigure(1,weight=1)
        ttk.Label(combo_frame,text="Mærkningstype").grid(row=0,column=0,sticky="w",pady=2)
        combo_box=ttk.Combobox(combo_frame,textvariable=combo_mode,values=list(COMBO_LABEL_MODES),state="readonly",width=12); combo_box.grid(row=0,column=1,sticky="ew",pady=2)
        combo_split=ttk.Frame(combo_frame); combo_split.grid(row=1,column=0,columnspan=2,sticky="ew"); combo_split.columnconfigure(1,weight=1)
        ttk.Label(combo_split,text="Afbryder mærkning").grid(row=0,column=0,sticky="w",pady=2); ttk.Entry(combo_split,textvariable=combo_sw_label).grid(row=0,column=1,sticky="ew",pady=2)
        ttk.Label(combo_split,text="Afbryder gruppe").grid(row=1,column=0,sticky="w",pady=2); ttk.Entry(combo_split,textvariable=combo_sw_group).grid(row=1,column=1,sticky="ew",pady=2)
        ttk.Label(combo_split,text="Stik mærkning").grid(row=2,column=0,sticky="w",pady=2); ttk.Entry(combo_split,textvariable=combo_so_label).grid(row=2,column=1,sticky="ew",pady=2)
        ttk.Label(combo_split,text="Stik gruppe").grid(row=3,column=0,sticky="w",pady=2); ttk.Entry(combo_split,textvariable=combo_so_group).grid(row=3,column=1,sticky="ew",pady=2)
        def combo_visibility(*_):
            if not is_combo_symbol(p.symbol):
                combo_frame.grid_remove(); return
            combo_frame.grid()
            if normalize_combo_label_mode(combo_mode.get())=="Opdelt":combo_split.grid()
            else:combo_split.grid_remove()
        combo_box.bind("<<ComboboxSelected>>",combo_visibility); combo_visibility()

        ttk.Label(f,text="Farve").grid(row=6,column=0,sticky="w",pady=3)
        cframe=ttk.Frame(f); cframe.grid(row=6,column=1,sticky="ew",pady=3); cframe.columnconfigure(0,weight=1)
        swatch=tk.Label(cframe,textvariable=color,relief="sunken",bd=1); swatch.grid(row=0,column=0,sticky="ew")
        def refresh_swatch(*_):
            try:swatch.configure(background=normalize_hex_color(color.get()),foreground="#ffffff" if sum(int(normalize_hex_color(color.get())[i:i+2],16) for i in (1,3,5))<360 else "#000000")
            except Exception:pass
        def pick_color():
            chosen=colorchooser.askcolor(color=normalize_hex_color(color.get()),title="Vælg symbolfarve",parent=win)[1]
            if chosen:color.set(normalize_hex_color(chosen)); refresh_swatch()
        ttk.Button(cframe,text="Vælg…",command=pick_color).grid(row=0,column=1,padx=(4,0)); refresh_swatch()
        lock_cb=ttk.Checkbutton(f,text="Lås symbol",variable=locked); lock_cb.grid(row=7,column=0,columnspan=2,sticky="w",pady=(6,3))
        editors=[e_size,e_lw,e_rot,e_label,e_group]
        def update_states(*_):
            st="disabled" if locked.get() else "normal"
            for w in (e_size,e_lw,e_label,e_group):w.configure(state=st)
            e_rot.configure(state="disabled" if locked.get() else "normal")
        lock_cb.configure(command=update_states); update_states()
        def save(event=None):
            try:
                nsize=float(size.get()); nlw=float(lw.get()); nrot=float(rot.get() or 0)
                if nsize<=0 or not math.isfinite(nsize):raise ValueError
                if nlw<=0 or nlw>5 or not math.isfinite(nlw):raise ValueError
            except Exception:
                messagebox.showerror("Symbol-egenskaber","Angiv en positiv størrelse og linjetykkelse mellem 0 og 5 mm.",parent=win); return
            before=self._capture_edit_state(); was_locked=bool(getattr(p,"locked",False)); new_locked=bool(locked.get())
            # Et låst symbol kan låses op i dialogen, men ændres først samtidig hvis det faktisk låses op.
            if not was_locked or not new_locked:
                p.size=nsize; p.line_width=nlw; p.rotation=nrot; p.label=label.get().strip(); p.group=group.get().strip(); p.color=normalize_hex_color(color.get())
                if is_combo_symbol(p.symbol):
                    p.label_mode=normalize_combo_label_mode(combo_mode.get()); p.switch_label=combo_sw_label.get().strip(); p.switch_group=combo_sw_group.get().strip(); p.socket_label=combo_so_label.get().strip(); p.socket_group=combo_so_group.get().strip()
            p.locked=new_locked
            self._commit_history("Redigér symbol",before); win.destroy(); self._load_selected_symbol_controls(); self.redraw_placements()
        buttons=ttk.Frame(f); buttons.grid(row=8,column=0,columnspan=2,sticky="ew",pady=(8,0)); buttons.columnconfigure((0,1),weight=1)
        ttk.Button(buttons,text="Annuller",command=win.destroy).grid(row=0,column=0,sticky="ew",padx=(0,3))
        ttk.Button(buttons,text="Gem",command=save).grid(row=0,column=1,sticky="ew",padx=(3,0))
        win.bind("<Return>",save); win.bind("<Escape>",lambda e:win.destroy()); win.focus_force()

    def left_click(self,event):
        if not self.doc:return
        if self.mode=="spot_line":
            pt=self.screen_to_cad(event.x,event.y)
            if self.spot_row_start is None:
                self.spot_row_start=pt; self.spot_row_preview_end=pt; self.status_var.set("Spot-række: klik slutpunkt. Spots fordeles jævnt mellem punkterne."); return
            if math.hypot(pt[0]-self.spot_row_start[0],pt[1]-self.spot_row_start[1])<1e-6:
                self.status_var.set("Vælg et andet slutpunkt for spot-rækken."); return
            points=self._spot_row_points(self.spot_row_start,pt); before=self._capture_edit_state(); new_uids=[]
            size=float(self.spot_default_size); lw=float(self.default_symbol_line_width); color=self.symbol_color_defaults.get("spot",DEFAULT_SYMBOL_COLOR)
            group=self.group_var.get().strip()
            for x,y in points:
                pl=Placement(symbol="spot",x=x,y=y,size=size,line_width=lw,color=color,group=group); self.placements.append(pl); new_uids.append(pl.uid)
            self._commit_history(f"Placér {len(points)} spots på linje",before); self.spot_row_start=None; self.spot_row_preview_end=None; self.canvas.delete("spot_row_preview"); self.redraw_placements()
            if self.spot_row_link_after.get(): self._start_spot_parent_mode(new_uids)
            else:
                self.mode="select"; self._update_mode_status(); self.status_var.set(f"{len(points)} spots placeret på en ret linje.")
            return
        if self.mode=="spot_rect":
            pt=self.screen_to_cad(event.x,event.y)
            if self.spot_rect_start is None:
                self.spot_rect_start=pt; self.spot_rect_preview_end=pt; self.status_var.set("Spot-rektangel: klik modstående hjørne. Spots fordeles jævnt i området."); return
            if abs(pt[0]-self.spot_rect_start[0])<1e-6 or abs(pt[1]-self.spot_rect_start[1])<1e-6:
                self.status_var.set("Rektanglet skal have både bredde og højde. Vælg et andet hjørne."); return
            points=self._spot_rect_points(self.spot_rect_start,pt); before=self._capture_edit_state(); new_uids=[]
            size=float(self.spot_default_size); lw=float(self.default_symbol_line_width); color=self.symbol_color_defaults.get("spot",DEFAULT_SYMBOL_COLOR)
            group=self.group_var.get().strip()
            for x,y in points:
                pl=Placement(symbol="spot",x=x,y=y,size=size,line_width=lw,color=color,group=group); self.placements.append(pl); new_uids.append(pl.uid)
            self._commit_history(f"Placér {len(points)} spots i rektangel",before)
            self.spot_rect_start=None; self.spot_rect_preview_end=None; self.canvas.delete("spot_rect_preview"); self.redraw_placements()
            if self.spot_rect_link_after.get(): self._start_spot_parent_mode(new_uids)
            else:
                self.mode="select"; self._update_mode_status(); self.status_var.set(f"{len(points)} spots placeret i et rektangulært mønster.")
            return
        if self.mode=="spot_parent":
            target_i,_d=self.find_symbol_at(event.x,event.y)
            if target_i is None:
                self.status_var.set("Spot-række: klik direkte på et lampested. Esc springer tilknytning over."); return
            self._assign_spot_parent(target_i); return
        if self.mode=="place":
            if not self.apply_symbol_properties(show_error=True):return
            code=SYMBOLS[self.symbol_name.get()]; rotation=float(self.rotation.get() or 0)
            place_size=self.spot_default_size if code=="spot" else self.default_symbol_size
            if self._event_alt_pressed(event):
                x,y=self.screen_to_cad(event.x,event.y); snap_rotation=rotation; snap_kind="fri"
            else:
                (x,y),snap_rotation,snap_kind=self.snap_symbol_pose(code,place_size,rotation,event.x,event.y)
            pl=Placement(symbol=code,x=x,y=y,rotation=snap_rotation,size=place_size,label=self.label_var.get().strip(),group=self.group_var.get().strip(),
                         label_mode=normalize_combo_label_mode(self.combo_label_mode.get()),switch_label=self.combo_switch_label.get().strip(),switch_group=self.combo_switch_group.get().strip(),
                         socket_label=self.combo_socket_label.get().strip(),socket_group=self.combo_socket_group.get().strip(),
                         line_width=self.default_symbol_line_width,color=self.symbol_color_defaults.get(code,DEFAULT_SYMBOL_COLOR))
            before=self._capture_edit_state(); self.placements.append(pl); self.creation_history.append(("symbol",pl)); self._commit_history(f"Placér {self.symbol_name.get()}",before)
            self._clear_symbol_selection(); self.selected_cable_index=None; self.selected_text_index=None; self._remember_recent_symbol(code); self.clear_snap_feedback()
            suffix=f" · snap: {snap_kind}" if snap_kind!="fri" else ""
            if self.continuous_placement.get():
                self.status_var.set(f"Placeret {self.symbol_name.get()}{suffix}. Klik igen for næste · Esc afslutter.")
            else:
                self.mode="select"; self._set_symbol_selection([len(self.placements)-1]); self._update_mode_status(); self._refresh_palette_selection()
                self.status_var.set(f"Placeret {self.symbol_name.get()}{suffix}.")
            self.redraw_placements(); return
        if self.mode=="text":
            x,y=self.screen_to_cad(event.x,event.y)
            item=TextPlacement(self.text_content.get().strip(),x,y,float(self.text_height.get()),float(self.text_rotation.get()),normalize_hex_color(self.text_color.get()))
            before=self._capture_edit_state(); self.texts.append(item); self.creation_history.append(("text",item)); self._commit_history("Tilføj tekst",before)
            self.mode="select"; self.selected_text_index=len(self.texts)-1; self._clear_symbol_selection(); self.selected_cable_index=None; self._update_mode_status()
            self.redraw_placements(); self.status_var.set(f"Tekst placeret: {item.text}. Træk for at flytte eller dobbeltklik for at redigere.")
            return
        if self.mode=="cable":
            if self._event_alt_pressed(event):
                x,y=self.screen_to_cad(event.x,event.y); kind="fri"; symbol_uid=""; symbol_port=0
            else:
                x,y,kind,symbol_uid,symbol_port=self.snap_point_detail(event.x,event.y)
            if self._event_alt_pressed(event):symbol_port=0
            target=(x,y)
            if not self.current_cable_points:
                self.current_cable_points.append(target)
                self.current_cable_start_uid=symbol_uid if kind=="symbol" else ""
                self.current_cable_start_port=int(symbol_port) if kind=="symbol" else 0
                self.current_cable_end_uid=""; self.current_cable_end_port=0
            else:
                for q in self._orthogonal_tail(self.current_cable_points[-1],target):
                    if not self.current_cable_points or math.hypot(q[0]-self.current_cable_points[-1][0],q[1]-self.current_cable_points[-1][1])>1e-9:
                        self.current_cable_points.append(q)
                self.current_cable_end_uid=symbol_uid if kind=="symbol" else ""
                self.current_cable_end_port=int(symbol_port) if kind=="symbol" else 0
            self.cable_preview_cursor=None; self.snap_marker=None; self.snap_marker_kind=""; self.draw_cable_preview()
            suffix=f" – snapped til {kind}" if kind!="fri" else ""
            self.status_var.set(f"Kabel/ledning: {len(self.current_cable_points)} punkt(er){suffix}. Fortsæt eller afslut forløbet."); return
        if self.mode=="associate":
            target_i,_d=self.find_symbol_at(event.x,event.y)
            if target_i is None:
                self.status_var.set("Tilknyt lys: klik direkte på et lampeudtag eller en lampe. Esc afslutter."); return
            self._assign_association_target(target_i); return

        # Select mode: et allerede valgt kabel giver først adgang til sine knæk-håndtag.
        if self.selected_cable_index is not None:
            vi=self.find_cable_vertex_at(event.x,event.y,self.selected_cable_index)
            if vi is not None:
                self.selected_cable_vertex_index=vi; self.drag_vertex_original_index=vi; self.dragging=True
                self.drag_original_points=[tuple(q) for q in self.cables[self.selected_cable_index].points]
                self._drag_history_snapshot=self._capture_edit_state(); self._drag_history_label="Redigér kabelknæk"
                if vi in (0,len(self.cables[self.selected_cable_index].points)-1):
                    self.status_var.set("Redigerer kabelende. Træk hen på et symbol for at tilslutte; Alt = uden snap.")
                else:self.status_var.set(f"Redigerer knækpunkt {vi}. Træk håndtaget; ortogonale kabler bevarer 90°-føring.")
                self.redraw_placements(); return

        sym_i,sym_d=self.find_symbol_at(event.x,event.y)
        text_i,text_d=self.find_text_at(event.x,event.y)
        cab_i,cab_d=self.find_cable_at(event.x,event.y)
        shift=bool(int(getattr(event,"state",0) or 0)&0x0001)

        # Shift+klik tilføjer/fjerner symboler uden at starte flytning.
        if sym_i is not None and (text_i is None or sym_d<=text_d) and (cab_i is None or sym_d<=cab_d) and shift:
            current=set(self._valid_selected_indices())
            if sym_i in current:current.remove(sym_i)
            else:current.add(sym_i)
            self._set_symbol_selection(current)
            self.status_var.set(f"Valgt {len(current)} symboler." if current else "Markering ryddet.")
            return

        if text_i is not None and (sym_i is None or text_d<=sym_d) and (cab_i is None or text_d<=cab_d):
            self._clear_symbol_selection(); self.selected_text_index=text_i; self.selected_cable_index=None; self.dragging=True; self._restore_default_symbol_controls(); self._update_properties_panel()
            self._drag_history_snapshot=self._capture_edit_state(); self._drag_history_label="Flyt tekst"
            self.status_var.set(f"Valgt tekst: {self.texts[text_i].text} · træk for at flytte · dobbeltklik for at redigere")
            self.redraw_placements(); return

        if sym_i is not None and (cab_i is None or sym_d<=cab_d):
            current=set(self._valid_selected_indices())
            if sym_i not in current or not current:
                self._set_symbol_selection([sym_i]); current={sym_i}
            else:
                # Klik på et allerede multi-valgt symbol bevarer hele gruppen.
                self.selected_cable_index=None; self.selected_text_index=None
            movable={i for i in current if not bool(getattr(self.placements[i],"locked",False))}
            if bool(getattr(self.placements[sym_i],"locked",False)):
                self.dragging=False; self.drag_start_cad=None; self.multi_drag_start_positions={}; self.drag_primary_symbol_index=None
                self._drag_history_snapshot=None; self._drag_history_label=""
                if len(current)==1:self._load_selected_symbol_controls()
                else:self._update_properties_panel()
                self.status_var.set(f"Valgt: {symbol_display_name(self.placements[sym_i].symbol)} · låst · højreklik for at låse op")
                self.redraw_placements(); return
            self.dragging=True; self.drag_start_cad=self.screen_to_cad(event.x,event.y)
            self.multi_drag_start_positions={i:(self.placements[i].x,self.placements[i].y) for i in sorted(movable)}
            self.drag_primary_symbol_index=sym_i
            self._drag_history_snapshot=self._capture_edit_state(); self._drag_history_label="Flyt flere symboler" if len(movable)>1 else "Flyt symbol"
            if len(current)==1:self._load_selected_symbol_controls()
            else:self._update_properties_panel()
            self.status_var.set(f"{len(current)} symboler valgt · træk samlet · Shift+klik tilføjer/fjerner" if len(current)>1 else f"Valgt: {symbol_display_name(self.placements[sym_i].symbol)} · træk for at flytte · Delete sletter")
            self.redraw_placements(); return

        if cab_i is not None:
            self._clear_symbol_selection(); self.selected_cable_index=cab_i; self.selected_text_index=None; self.dragging=True; self._restore_default_symbol_controls(); self._load_selected_cable_controls(); self._update_properties_panel()
            self.drag_start_cad=self.screen_to_cad(event.x,event.y); self.drag_original_points=[tuple(q) for q in self.cables[cab_i].points]
            self._drag_history_snapshot=self._capture_edit_state(); self._drag_history_label="Flyt kabel/ledning"
            self.status_var.set(f"Valgt {cable_display_label(self.cables[cab_i]) or 'kabel/ledning'} – træk hele forløbet eller et blåt knækpunkt.")
            self.redraw_placements(); return

        # Tomt område starter markeringsramme. Et rent klik rydder markeringen.
        self.dragging=False; self.selection_rect_start=(int(event.x),int(event.y)); self.selection_rect_active=False; self.selection_rect_additive=shift
        self.canvas.delete("selection_rect"); self._drag_history_snapshot=None; self._drag_history_label=""

    def left_drag(self,event):
        if self.mode!="select":return
        if self.dragging:self._update_canvas_cursor()
        if self.selection_rect_start is not None:
            x0,y0=self.selection_rect_start
            if math.hypot(event.x-x0,event.y-y0)>=4:
                self.selection_rect_active=True; self.canvas.delete("selection_rect")
                self.canvas.create_rectangle(x0,y0,event.x,event.y,outline=self._theme_color("accent"),fill="",dash=(4,3),width=1,tags=("selection_rect",))
            return
        if not self.dragging:return

        selected=self._valid_selected_indices()
        movable_selected=sorted(self.multi_drag_start_positions) if self.multi_drag_start_positions else []
        if movable_selected and self.multi_drag_start_positions and self.drag_start_cad is not None:
            x,y=self.screen_to_cad(event.x,event.y); dx=x-self.drag_start_cad[0]; dy=y-self.drag_start_cad[1]
            primary=self.drag_primary_symbol_index if self.drag_primary_symbol_index in self.multi_drag_start_positions else movable_selected[0]
            p=self.placements[primary]; px0,py0=self.multi_drag_start_positions[primary]; desired=(px0+dx,py0+dy)
            ignore={self.placements[i].uid for i in selected}
            if self._event_alt_pressed(event):
                snapped,kind=desired,"fri"
            elif len(movable_selected)==1:
                snapped,snap_rot,kind=self.snap_symbol_cad_pose(p.symbol,p.size,p.rotation,desired,ignore,cursor_cad=(x,y),cursor_screen=(event.x,event.y),auto_orient=True)
                p.rotation=float(snap_rot)%360.0
            else:
                snapped,_snap_rot,kind=self.snap_symbol_cad_pose(p.symbol,p.size,p.rotation,desired,ignore,cursor_cad=(x,y),cursor_screen=(event.x,event.y),auto_orient=False)
            adx=snapped[0]-desired[0]; ady=snapped[1]-desired[1]
            for i in movable_selected:
                ox,oy=self.multi_drag_start_positions[i]; self.placements[i].x=ox+dx+adx; self.placements[i].y=oy+dy+ady
            self._set_snap_live(kind)
            self.draw_symbol_snap_feedback(p.symbol,p.size,p.rotation,(p.x,p.y),kind,ignore_uids=ignore,show_preview=False)
            self._schedule_placement_redraw(16,symbol_indices=movable_selected); return
        if self.selected_text_index is not None:
            x,y=self.screen_to_cad(event.x,event.y); self.texts[self.selected_text_index].x=x; self.texts[self.selected_text_index].y=y; self._schedule_placement_redraw(16,text_indices=[self.selected_text_index])
        elif self.selected_cable_index is not None and self.selected_cable_vertex_index is not None and self.drag_original_points:
            cable=self.cables[self.selected_cable_index]; vi=int(self.drag_vertex_original_index if self.drag_vertex_original_index is not None else self.selected_cable_vertex_index)
            if self._event_alt_pressed(event):
                x,y=self.screen_to_cad(event.x,event.y); kind="fri"; uid=""; port=0
            else:
                x,y,kind,uid,port=self.snap_point_detail(event.x,event.y)
            if vi in (0,len(self.drag_original_points)-1):
                cable.points=move_polyline_endpoint(self.drag_original_points,vi,(x,y),bool(cable.orthogonal))
                if vi==0:
                    cable.start_symbol_uid=uid if kind=="symbol" else ""; cable.start_symbol_port=int(port) if kind=="symbol" else 0
                    self.selected_cable_vertex_index=0
                else:
                    cable.end_symbol_uid=uid if kind=="symbol" else ""; cable.end_symbol_port=int(port) if kind=="symbol" else 0
                    self.selected_cable_vertex_index=len(cable.points)-1
            else:
                cable.points=move_polyline_vertex(self.drag_original_points,vi,(x,y),bool(cable.orthogonal))
                if cable.orthogonal:self.selected_cable_vertex_index=min(vi+1,max(1,len(cable.points)-2))
            self._set_snap_live(kind)
            self.snap_marker=(x,y) if kind!="fri" else None; self.snap_marker_kind=kind; self._update_canvas_cursor(kind)
            self._schedule_placement_redraw(16,cable_indices=[self.selected_cable_index])
        elif self.selected_cable_index is not None and self.drag_start_cad and self.drag_original_points:
            x,y=self.screen_to_cad(event.x,event.y); dx=x-self.drag_start_cad[0]; dy=y-self.drag_start_cad[1]
            self.cables[self.selected_cable_index].points=[(px+dx,py+dy) for px,py in self.drag_original_points]; self._schedule_placement_redraw(16,cable_indices=[self.selected_cable_index])

    def left_release(self,event):
        if self.selection_rect_start is not None:
            x0,y0=self.selection_rect_start; self.canvas.delete("selection_rect")
            if self.selection_rect_active:
                l,r=sorted((x0,event.x)); t,b=sorted((y0,event.y)); hits=[]
                for i,p in enumerate(self.placements):
                    if not self.layer_visibility.get(symbol_layer(p.symbol),True):continue
                    x1,y1,x2,y2=self.placement_screen_bbox(p,pad=1)
                    if not (x2<l or x1>r or y2<t or y1>b):hits.append(i)
                if getattr(self,"selection_rect_additive",False):hits=sorted(set(hits)|set(self._valid_selected_indices()))
                self._set_symbol_selection(hits)
                self.status_var.set(f"Valgt {len(hits)} symboler med markeringsramme." if hits else "Ingen symboler i markeringsrammen.")
            elif not getattr(self,"selection_rect_additive",False):
                self._clear_symbol_selection(); self.selected_cable_index=None; self.selected_text_index=None; self._restore_default_symbol_controls(); self.redraw_placements()
            self.selection_rect_start=None; self.selection_rect_active=False; return

        was_label=self._drag_history_label; before=self._drag_history_snapshot
        self.dragging=False; self.drag_start_cad=None; self.drag_original_points=None; self.drag_vertex_original_index=None
        self.multi_drag_start_positions={}; self.drag_primary_symbol_index=None
        self._drag_history_snapshot=None; self._drag_history_label=""; self._set_snap_live(""); self.clear_snap_feedback(); self._update_canvas_cursor()
        if self._placement_redraw_job is not None:
            try:self.after_cancel(self._placement_redraw_job)
            except Exception:pass
            self._placement_redraw_job=None
        if before is not None:
            changed=self._commit_history(was_label or "Flyt objekt",before)
            if changed:self._update_duplicate_spacing_after_move()
        if self.doc:self.redraw_placements()

    def find_symbol_at(self,sx,sy):
        best=None; bd=1e99
        candidates=self._placement_candidate_indices_screen(sx,sy,12.0)
        for i in candidates:
            p=self.placements[i]
            if not self.layer_visibility.get(symbol_layer(p.symbol),True):continue
            x1,y1,x2,y2=self.placement_screen_bbox(p,pad=9)
            if not (x1<=sx<=x2 and y1<=sy<=y2):continue
            cx,cy=self.cad_to_screen(p.x,p.y); d=math.hypot(sx-cx,sy-cy)
            if d<bd:best=i;bd=d
        return best,bd

    def find_text_at(self,sx,sy):
        best=None; bd=1e99
        if not self.layer_visibility.get(FREE_TEXT_LAYER,True):return best,bd
        for i,item in enumerate(self.texts):
            # Screen bbox approximates rotated text conservatively.
            cx,cy=self.cad_to_screen(item.x,item.y); h=max(8.0,float(item.height)*self.view_scale); w=max(h*.6*len(str(item.text)),h)
            r=.55*math.hypot(w,h)+7
            if abs(sx-cx)<=r and abs(sy-cy)<=r:
                d=math.hypot(sx-cx,sy-cy)
                if d<bd:best=i;bd=d
        return best,bd

    @staticmethod
    def _point_segment_distance(px,py,x1,y1,x2,y2):
        dx=x2-x1; dy=y2-y1
        if dx==0 and dy==0:return math.hypot(px-x1,py-y1)
        t=max(0.0,min(1.0,((px-x1)*dx+(py-y1)*dy)/(dx*dx+dy*dy)))
        qx=x1+t*dx; qy=y1+t*dy; return math.hypot(px-qx,py-qy)

    def find_cable_vertex_at(self,sx,sy,cable_index=None):
        """Returnér kabelpunkt tæt på musen, inkl. endepunkter til gen-tilslutning."""
        if cable_index is None:cable_index=self.selected_cable_index
        if cable_index is None or not (0<=cable_index<len(self.cables)):return None
        cable=self.cables[cable_index]
        best=None; bd=10.0
        for i,(x,y) in enumerate(cable.points):
            sx0,sy0=self.cad_to_screen(float(x),float(y)); d=math.hypot(sx-sx0,sy-sy0)
            if d<=bd:best=i;bd=d
        return best

    def find_cable_at(self,sx,sy):
        best=None; bd=1e99
        if not self.show_cables_overlay.get():return best,bd
        for i,cable in enumerate(self.cables):
            if not self.layer_visibility.get(cable.layer,True):continue
            pts=[self.cad_to_screen(float(x),float(y)) for x,y in cable.points]
            for a,b in zip(pts,pts[1:]):
                d=self._point_segment_distance(sx,sy,a[0],a[1],b[0],b[1])
                if d<8 and d<bd:best=i;bd=d
        return best,bd

    def sync_cable_connections(self):
        """Hold kabelender fysisk forbundet til den præcise symbolport."""
        by_uid={p.uid:p for p in self.placements if getattr(p,"uid","")}
        for cable in self.cables:
            if len(cable.points)<2:continue
            old=list(cable.points); new_start=None; new_end=None
            p=by_uid.get(getattr(cable,"start_symbol_uid","") or "")
            if p:
                pts=placement_connection_points(p)
                if pts:
                    pi=max(0,min(int(getattr(cable,"start_symbol_port",0) or 0),len(pts)-1)); new_start=pts[pi]
            p=by_uid.get(getattr(cable,"end_symbol_uid","") or "")
            if p:
                pts=placement_connection_points(p)
                if pts:
                    pi=max(0,min(int(getattr(cable,"end_symbol_port",0) or 0),len(pts)-1)); new_end=pts[pi]
            if new_start is not None:cable.points[0]=new_start
            if new_end is not None:cable.points[-1]=new_end
            if not getattr(cable,"orthogonal",False):continue
            if len(cable.points)==2 and (new_start is not None or new_end is not None):
                a,b=cable.points
                if abs(a[0]-b[0])>1e-9 and abs(a[1]-b[1])>1e-9:cable.points=[a,(b[0],a[1]),b]
                continue
            if len(cable.points)>=3 and new_start is not None:
                was_h=abs(old[1][0]-old[0][0])>=abs(old[1][1]-old[0][1])
                q=cable.points[1]; cable.points[1]=(q[0],new_start[1]) if was_h else (new_start[0],q[1])
            if len(cable.points)>=3 and new_end is not None:
                was_h=abs(old[-1][0]-old[-2][0])>=abs(old[-1][1]-old[-2][1])
                q=cable.points[-2]; cable.points[-2]=(q[0],new_end[1]) if was_h else (new_end[0],q[1])

    def _repair_legacy_cable_connections(self):
        """Genkend gamle kabelender som allerede ligger visuelt ved symboler.

        0.19.0-projektet fra den konkrete fejlrapport indeholder fx K01 med
        endepunkter få tegneenheder fra ladeboksen og gruppetavlen, men uden
        start/end_symbol_uid.  Denne migration tilføjer kun en relation når en
        entydig nærmeste port ligger tæt i forhold til symbolstørrelsen.
        """
        if not self.cables or not self.placements:return 0
        changed=0
        for cable in self.cables:
            if len(cable.points)<2:continue
            for which,point in (("start",cable.points[0]),("end",cable.points[-1])):
                uid_attr=f"{which}_symbol_uid"; port_attr=f"{which}_symbol_port"
                if getattr(cable,uid_attr,""):continue
                ranked=[]
                px,py=float(point[0]),float(point[1])
                for p in self.placements:
                    ports=placement_connection_ports(p)
                    if not ports:continue
                    threshold=max(40.0,min(float(p.size)*0.75,320.0))
                    for qx,qy,port in ports:
                        d=math.hypot(px-qx,py-qy)
                        if d<=threshold:ranked.append((d,threshold,p,port,qx,qy))
                if not ranked:continue
                ranked.sort(key=lambda q:q[0])
                best=ranked[0]
                # Undgå tvetydige auto-reparationer i meget tætte symbolgrupper.
                if len(ranked)>1 and ranked[1][0] <= best[0]*1.20+5.0:continue
                _d,_thr,p,port,qx,qy=best
                setattr(cable,uid_attr,p.uid); setattr(cable,port_attr,int(port))
                if which=="start":cable.points[0]=(qx,qy)
                else:cable.points[-1]=(qx,qy)
                changed+=1
        if changed:self.sync_cable_connections()
        return changed

    def redraw_dirty(self,symbol_indices=None,cable_indices=None,text_indices=None):
        """Opdater kun ændrede Canvas-objekter under interaktiv redigering."""
        t0=time.perf_counter(); symbol_indices=set(symbol_indices or ()); cable_indices=set(cable_indices or ()); text_indices=set(text_indices or ())
        # Flyttede symboler kan have logisk forbundne kabler.
        if symbol_indices:
            moved_uids={self.placements[i].uid for i in symbol_indices if 0<=i<len(self.placements)}
            self.sync_cable_connections()
            for ci,c in enumerate(self.cables):
                if c.start_symbol_uid in moved_uids or c.end_symbol_uid in moved_uids:cable_indices.add(ci)
            self._rebuild_placement_snap_index()
        selected=set(self._valid_selected_indices())
        for i in symbol_indices:
            if not (0<=i<len(self.placements)):continue
            self.canvas.delete(f"sym{i}"); self.draw_symbol_canvas(i,self.placements[i],i in selected)
        for i in text_indices:
            if not (0<=i<len(self.texts)):continue
            self.canvas.delete(f"text{i}"); self.draw_free_text_canvas(i,self.texts[i],i==self.selected_text_index)
        for i in cable_indices:
            if not (0<=i<len(self.cables)):continue
            self.canvas.delete(f"cable{i}")
            if self.show_cables_overlay.get():self.draw_cable_canvas(i,self.cables[i],i==self.selected_cable_index)
        for n,v in self.layer_visibility.items():
            if not v:self.canvas.itemconfigure(self._layer_tag(n),state="hidden")
        self._schedule_annotation_redraw(45)
        try:self.canvas.tag_raise("snap_feedback"); self.canvas.tag_raise("selection_rect"); self.canvas.tag_raise("perf_overlay")
        except Exception:pass
        self._perf_last_dirty_redraw_ms=(time.perf_counter()-t0)*1000.0

    def redraw_placements(self):
        t0=time.perf_counter()
        self.sync_cable_connections()
        selected_symbols=set(self._valid_selected_indices())
        self.canvas.delete("placement"); self.canvas.delete("cable"); self.canvas.delete("cable_handle"); self.canvas.delete("free_text")
        for i,p in enumerate(self.placements):self.draw_symbol_canvas(i,p,i in selected_symbols)
        for i,t in enumerate(self.texts):self.draw_free_text_canvas(i,t,i==self.selected_text_index)
        if self.show_cables_overlay.get():
            for i,c in enumerate(self.cables):self.draw_cable_canvas(i,c,i==self.selected_cable_index)
        self.redraw_annotations()
        self.draw_association_targets()
        self.draw_spot_parent_targets()
        for n,v in self.layer_visibility.items():
            if not v:self.canvas.itemconfigure(self._layer_tag(n),state="hidden")
        try:self.canvas.tag_raise("snap_feedback"); self.canvas.tag_raise("selection_rect"); self.canvas.tag_raise("perf_overlay")
        except Exception:pass
        self._rebuild_placement_snap_index()
        self._perf_last_redraw_ms=(time.perf_counter()-t0)*1000.0

    @staticmethod
    def _rect_overlap_area(a,b):
        x1=max(a[0],b[0]); y1=max(a[1],b[1]); x2=min(a[2],b[2]); y2=min(a[3],b[3])
        return max(0.0,x2-x1)*max(0.0,y2-y1)

    def _annotation_metrics(self,lines,compact=True):
        try: fs=max(7,min(10,int(self.annotation_font_size.get())))
        except Exception: fs=DEFAULT_ANNOTATION_FONT_SIZE
        font=tkfont.Font(family="Segoe UI",size=fs,weight="normal")
        clean=[str(v) for v in lines if str(v).strip()]
        text="\n".join(clean)
        line_h=max(font.metrics("linespace"),fs+2)
        text_w=max([font.measure(v) for v in clean] or [1])
        pad=1 if compact else 2
        return text,font,float(text_w+2*pad),float(line_h*len(clean)+2*pad),pad

    def _annotation_candidates(self,x,y,w,h,compact=True):
        gap=7 if compact else 9
        # Præference: højre/over, højre/under, venstre/over, venstre/under, centreret over/under.
        return [
            (x+gap,y-gap-h),
            (x+gap,y+gap),
            (x-gap-w,y-gap-h),
            (x-gap-w,y+gap),
            (x-w/2.0,y-gap-h-2),
            (x-w/2.0,y+gap+2),
            (x+gap*2,y-h/2.0),
            (x-gap*2-w,y-h/2.0),
        ]

    def _score_annotation_rect(self,rect,occupied,owner_tag="",candidate_index=0):
        l,t,r,b=rect; cw=max(1,self.canvas.winfo_width()); ch=max(1,self.canvas.winfo_height())
        score=float(candidate_index)*2.0
        # Hold mærkningen inde på viewporten.
        overflow=max(0,-l)+max(0,-t)+max(0,r-cw)+max(0,b-ch)
        score+=overflow*150.0
        for other in occupied:
            area=self._rect_overlap_area(rect,other)
            if area>0: score+=5000.0+area*20.0
        try:
            ids=self.canvas.find_overlapping(l,t,r,b)
        except tk.TclError:
            ids=()
        # find_overlapping bruger Canvas' eget spatialindeks og er derfor billigere
        # end at sammenligne mærkningen mod alle DWG-primitiver i Python.
        for item in ids:
            try:
                if self.canvas.itemcget(item,"state")=="hidden":continue
                tags=set(self.canvas.gettags(item))
            except tk.TclError:
                continue
            if owner_tag and owner_tag in tags:
                # Kabeltekst må gerne ligge tæt på sit eget kabel. Symboltekst må
                # stadig undgå sit eget symbol, så owner_tag gives kun for kabler.
                continue
            if "annotation" in tags: score+=3500.0
            elif "placement" in tags: score+=1800.0
            elif "cable_handle" in tags: score+=1200.0
            elif "cable" in tags: score+=650.0
            elif "cad" in tags: score+=70.0
        return score

    def _draw_annotation_box(self,x,y,lines,tags=(),compact=True,occupied=None,owner_tag=""):
        """Screen-space annotation med valgfri automatisk kollisionsfri placering."""
        if not lines:return None
        lines=[str(v) for v in lines if str(v).strip()]
        if not lines:return None
        text,font,w,h,pad=self._annotation_metrics(lines,compact)
        occupied=occupied if occupied is not None else []
        if bool(self.annotation_auto_place.get()):
            candidates=self._annotation_candidates(x,y,w,h,compact)
            scored=[]
            for n,(lx,ty) in enumerate(candidates):
                rect=(lx,ty,lx+w,ty+h)
                scored.append((self._score_annotation_rect(rect,occupied,owner_tag,n),rect))
            _score,rect=min(scored,key=lambda q:q[0])
        else:
            # Klassisk fast placering: lige over/højre for symbolets referencepunkt.
            lx=x+(7 if compact else 9); ty=y-(7 if compact else 9)-h
            rect=(lx,ty,lx+w,ty+h)
        lx,ty,rx,by=rect
        rect_item=self.canvas.create_rectangle(lx,ty,rx,by,fill=self._theme_color("annotation_bg"),outline="" if compact else self._theme_color("border"),width=1,tags=("annotation",)+tuple(tags))
        text_item=self.canvas.create_text(lx+pad,ty+pad,text=text,anchor="nw",justify="left",fill=self._theme_color("annotation_text"),font=font,tags=("annotation",)+tuple(tags))
        self.canvas.tag_lower(rect_item,text_item)
        occupied.append(rect)
        return rect

    def _draw_association_badge(self, placement: Placement, idx: int, occupied):
        text=association_display(placement)
        if not text:return None
        wx,wy=association_world_point(placement); x,y=self.cad_to_screen(wx,wy)
        font=tkfont.Font(family="Segoe UI",size=8,weight="bold")
        w=font.measure(text)+4; h=font.metrics("linespace")+2
        # Hold bogstavet tæt på symbolet, men flyt en smule hvis en anden badge
        # allerede ligger præcis samme sted.
        candidates=[(x,y-h),(x+5,y+3),(x-w-5,y-h),(x-w-5,y+3)]
        scored=[]
        for n,(lx,ty) in enumerate(candidates):
            rect=(lx,ty,lx+w,ty+h); score=n*2+sum(self._rect_overlap_area(rect,o)*100 for o in occupied)
            scored.append((score,rect))
        _score,rect=min(scored,key=lambda q:q[0]); l,t,r,b=rect
        bg=self.canvas.create_rectangle(l,t,r,b,fill=self._theme_color("annotation_bg"),outline="",tags=("annotation","association_badge",f"sym{idx}",self._layer_tag(META_LAYER)))
        tx=self.canvas.create_text(l+2,t+1,text=text,anchor="nw",fill=self._theme_color("association"),font=font,tags=("annotation","association_badge",f"sym{idx}",self._layer_tag(META_LAYER)))
        self.canvas.tag_lower(bg,tx); occupied.append(rect); return rect

    def redraw_annotations(self):
        if self._annotation_redraw_job is not None:
            try:self.after_cancel(self._annotation_redraw_job)
            except Exception:pass
            self._annotation_redraw_job=None
        self.canvas.delete("annotation")
        if not self.doc or not self.layer_visibility.get(META_LAYER,True):return
        style=self.annotation_style.get() if self.annotation_style.get() in ANNOTATION_STYLES else DEFAULT_ANNOTATION_STYLE
        compact=(style=="Kompakt")
        occupied=[]
        # Tilhørsbogstaver og mærkninger kan skjules hurtigt uden at ændre CAD-lag.
        if self.show_associations.get():
            for i,p in enumerate(self.placements):
                if not self.layer_visibility.get(symbol_layer(p.symbol),True):continue
                if association_display(p):self._draw_association_badge(p,i,occupied)
        if self.show_annotations.get():
            for i,p in enumerate(self.placements):
                if not self.layer_visibility.get(symbol_layer(p.symbol),True):continue
                lines=symbol_annotation_lines(p,style)
                if lines:
                    sx,sy=self.cad_to_screen(p.x,p.y)
                    self._draw_annotation_box(sx,sy,lines,(f"sym{i}",self._layer_tag(META_LAYER)),compact,occupied)
            if self.show_cables_overlay.get():
                for i,cable in enumerate(self.cables):
                    if not self.layer_visibility.get(cable.layer,True):continue
                    text=cable_display_label(cable)
                    if text:
                        x,y=cable_label_point(cable); sx,sy=self.cad_to_screen(x,y)
                        self._draw_annotation_box(sx,sy,[text],(f"cable{i}",self._layer_tag(META_LAYER)),True,occupied,owner_tag=f"cable{i}")
        self.canvas.tag_raise("annotation")

    def placement_screen_bbox(self,p: Placement,pad: float=0.0):
        x1,y1,x2,y2=symbol_local_bbox(p.symbol,p.size)
        corners=[(x1,y1),(x1,y2),(x2,y1),(x2,y2)]
        pts=[]
        for x,y in corners:
            x,y=rotate_point(x,y,p.rotation); pts.append(self.cad_to_screen(p.x+x,p.y+y))
        xs=[q[0] for q in pts]; ys=[q[1] for q in pts]
        return (min(xs)-pad,min(ys)-pad,max(xs)+pad,max(ys)+pad)

    def draw_symbol_canvas(self,idx,p,selected=False):
        layer=symbol_layer(p.symbol); cx,cy=self.cad_to_screen(p.x,p.y); pen=self._theme_color("accent") if selected else normalize_hex_color(p.color)
        width=_screen_line_width(p.line_width,selected); tags=("scene","placement",f"sym{idx}",self._layer_tag(layer))
        def scr(lx,ly):
            lx,ly=rotate_point(lx,ly,p.rotation); return cx+lx*self.view_scale,cy-ly*self.view_scale
        for prim in symbol_primitives(p.symbol,p.size):
            typ=prim[0]
            if typ=="line":self.canvas.create_line(*scr(prim[1],prim[2]),*scr(prim[3],prim[4]),fill=pen,width=width,tags=tags)
            elif typ=="circle":
                _,x,y,r=prim; sx,sy=scr(x,y); rr=r*self.view_scale; self.canvas.create_oval(sx-rr,sy-rr,sx+rr,sy+rr,outline=pen,width=width,tags=tags)
            elif typ=="arc":
                _,x,y,r,a1,a2=prim; pts=[]; delta=a2-a1; steps=max(12,int(abs(delta)/4))
                for j in range(steps+1):
                    a=math.radians(a1+delta*j/steps); pts.extend(scr(x+r*math.cos(a),y+r*math.sin(a)))
                self.canvas.create_line(*pts,fill=pen,width=width,tags=tags)
            elif typ=="polyline":
                pts=[]
                for x,y in prim[1]:pts.extend(scr(x,y))
                self.canvas.create_line(*pts,fill=pen,width=width,tags=tags)
            elif typ=="text":
                _,x,y,t,h=prim; sx,sy=scr(x,y); fs=max(7,min(40,int(h*self.view_scale*.8))); self.canvas.create_text(sx,sy,text=t,fill=pen,font=("Segoe UI",fs,"bold"),tags=tags)
        if selected:
            x1,y1,x2,y2=self.placement_screen_bbox(p,pad=6)
            self.canvas.create_rectangle(x1,y1,x2,y2,outline=self._theme_color("accent"),dash=(3,2),width=1,tags=tags)
            # Diskrete hjørnehåndtag gør markeringen tydelig uden at dominere.
            for hx,hy in ((x1,y1),(x2,y1),(x1,y2),(x2,y2)):
                self.canvas.create_rectangle(hx-2,hy-2,hx+2,hy+2,fill=self._theme_color("canvas"),outline=self._theme_color("accent"),width=1,tags=tags)
        if bool(getattr(p,"locked",False)):
            # Lille screen-space låsemarkør: synlig uden at dominere tegningen.
            x1,y1,x2,y2=self.placement_screen_bbox(p,pad=3); lx,ly=x2+8,y1+5
            self.canvas.create_rectangle(lx-4,ly-1,lx+4,ly+6,fill=self._theme_color("canvas"),outline=self._theme_color("muted"),width=1,tags=tags)
            self.canvas.create_arc(lx-3,ly-6,lx+3,ly+1,start=0,extent=180,style="arc",outline=self._theme_color("muted"),width=1,tags=tags)

    def draw_free_text_canvas(self,idx,item,selected=False):
        if not self.layer_visibility.get(FREE_TEXT_LAYER,True):return
        sx,sy=self.cad_to_screen(item.x,item.y); fs=max(1,min(160,int(abs(float(item.height))*self.view_scale*.78)))
        color=self._theme_color("accent") if selected else normalize_hex_color(item.color)
        tags=("scene","free_text",f"text{idx}",self._layer_tag(FREE_TEXT_LAYER))
        iid=self.canvas.create_text(sx,sy,text=str(item.text),fill=color,font=("Segoe UI",fs),angle=float(item.rotation),anchor="center",tags=tags)
        if selected:
            bb=self.canvas.bbox(iid)
            if bb:self.canvas.create_rectangle(bb[0]-5,bb[1]-4,bb[2]+5,bb[3]+4,outline=self._theme_color("accent"),dash=(3,2),width=1,tags=tags)

    def draw_cable_canvas(self,idx,cable,selected=False):
        if len(cable.points)<2:return
        pts=[]
        for x,y in cable.points:pts.extend(self.cad_to_screen(float(x),float(y)))
        pen=self._theme_color("accent") if selected else "#d00000"; width=_screen_line_width(cable.line_width,selected)
        tags=("scene","cable",f"cable{idx}",self._layer_tag(cable.layer))
        self.canvas.create_line(*pts,fill=pen,width=width,tags=tags)
        if selected:
            for vi,(x,y) in enumerate(cable.points):
                sx,sy=self.cad_to_screen(float(x),float(y)); active=(vi==self.selected_cable_vertex_index)
                endpoint=vi in (0,len(cable.points)-1); r=7 if active else (6 if endpoint else 5)
                if endpoint:
                    self.canvas.create_oval(sx-r,sy-r,sx+r,sy+r,fill=self._theme_color("canvas"),outline=self._theme_color("accent"),width=2,tags=("cable_handle",f"cable{idx}",self._layer_tag(cable.layer)))
                else:
                    self.canvas.create_rectangle(sx-r,sy-r,sx+r,sy+r,fill=self._theme_color("canvas"),outline=self._theme_color("accent"),width=2,tags=("cable_handle",f"cable{idx}",self._layer_tag(cable.layer)))

    def rotate_selected(self):
        indices=self._valid_selected_indices()
        if indices:
            editable=[i for i in indices if not bool(getattr(self.placements[i],"locked",False))]
            if not editable:
                self.status_var.set("Det valgte symbol er låst. Lås det op før rotation."); return
            before=self._capture_edit_state()
            for i in editable:self.placements[i].rotation=(self.placements[i].rotation+90)%360
            if len(indices)==1:
                p=self.placements[indices[0]]; self.rotation.set(p.rotation); msg=f"Roteret {symbol_display_name(p.symbol)} til {p.rotation:g}°."
            else:msg=f"Roteret {len(editable)} symboler +90°" + (f" · {len(indices)-len(editable)} låst" if len(editable)!=len(indices) else "") + "."
            self._commit_history("Rotér symboler" if len(editable)>1 else "Rotér symbol",before); self.redraw_placements(); self.status_var.set(msg); return
        if self.selected_text_index is not None:
            before=self._capture_edit_state(); item=self.texts[self.selected_text_index]; item.rotation=(item.rotation+90)%360
            self._commit_history("Rotér tekst",before); self.redraw_placements(); self.status_var.set(f"Roteret tekst til {item.rotation:g}°.")

    def delete_selected(self):
        indices=self._valid_selected_indices()
        if indices:
            editable=[i for i in indices if not bool(getattr(self.placements[i],"locked",False))]
            if not editable:
                self.status_var.set("Det valgte symbol er låst. Lås det op før sletning."); return
            before=self._capture_edit_state(); deleted=[self.placements[i] for i in editable]; deleted_uids={p.uid for p in deleted}
            for cable in self.cables:
                if cable.start_symbol_uid in deleted_uids:cable.start_symbol_uid=""; cable.start_symbol_port=0
                if cable.end_symbol_uid in deleted_uids:cable.end_symbol_uid=""; cable.end_symbol_port=0
            for i in sorted(editable,reverse=True):self.placements.pop(i)
            self.creation_history=[h for h in self.creation_history if not (h[0]=="symbol" and getattr(h[1],"uid","") in deleted_uids)]
            self._clear_symbol_selection(); self._cleanup_orphan_associations()
            self._commit_history(f"Slet {len(deleted)} symboler" if len(deleted)>1 else f"Slet {symbol_display_name(deleted[0].symbol)}",before)
            self._restore_default_symbol_controls(); self.redraw_placements(); return
        if self.selected_text_index is not None:
            before=self._capture_edit_state(); obj=self.texts.pop(self.selected_text_index)
            self.creation_history=[h for h in self.creation_history if h[1] is not obj]; self.selected_text_index=None
            self._commit_history("Slet tekst",before); self._restore_default_symbol_controls(); self.redraw_placements(); return
        if self.selected_cable_index is not None:
            before=self._capture_edit_state(); obj=self.cables.pop(self.selected_cable_index)
            self.creation_history=[h for h in self.creation_history if h[1] is not obj]; self.selected_cable_index=None
            self._commit_history("Slet kabel/ledning",before); self._restore_default_symbol_controls(); self.redraw_placements()

    def undo_last(self):
        # Bagudkompatibelt navn til ældre knapper/tests.
        return self.undo()

    # ---------------------------------------------------------- PRINT PREVIEW
    def _print_extents_for_scope_value(self, scope: str):
        if str(scope)=="Hele tegningen":
            return print_extents(self.cad_primitives,self.placements,self.cables,self.layer_visibility,self.texts)
        return self.current_view_extents()

    @staticmethod
    def _preview_segment_visible(a,b,ext):
        # Hurtig bbox-test. Selve previewet maskerer ikke via et rasterbillede og
        # forbliver derfor let; PDF'en bruger fortsat rigtig clip-path.
        xmin,ymin,xmax,ymax=ext
        return not (max(a[0],b[0])<xmin or min(a[0],b[0])>xmax or max(a[1],b[1])<ymin or min(a[1],b[1])>ymax)

    def _draw_print_preview(self, canvas, paper, orientation, scope):
        canvas.delete("all")
        if not self.doc:return
        self.sync_cable_connections(); self.update_idletasks()
        ext=self._print_extents_for_scope_value(scope); fill=(str(scope)=="Aktuel visning")
        page,effective,scale,ox,oy,draw_w,draw_h,margin=page_layout(ext,paper,orientation,PRINT_MARGIN_MM,fill_page=fill)
        pw,ph=page; xmin,ymin,xmax,ymax=effective
        cw=max(120,int(canvas.winfo_width())); ch=max(120,int(canvas.winfo_height())); outer=20
        ps=min(max(0.05,(cw-2*outer)/pw),max(0.05,(ch-2*outer)/ph))
        page_w=pw*ps; page_h=ph*ps; left=(cw-page_w)/2; top=(ch-page_h)/2
        pcol=self._theme_color("preview_bg"); canvas.configure(background=pcol)
        shadow=6; canvas.create_rectangle(left+shadow,top+shadow,left+page_w+shadow,top+page_h+shadow,fill=self._theme_color("shadow"),outline="",tags=("preview_page",))
        canvas.create_rectangle(left,top,left+page_w,top+page_h,fill="#ffffff",outline="",tags=("preview_page",))
        def pagept(px,py):return left+px*ps, top+(ph-py)*ps
        def mappt(x,y):return pagept(ox+(x-xmin)*scale,oy+(y-ymin)*scale)
        cad_pen="#16181b"; sym_sel="#202020"
        linew=max(1,0.45*ps)
        # CAD.
        for prim in self.cad_primitives:
            if not self.layer_visibility.get(prim.layer,True):continue
            try:
                if prim.kind=="line":
                    a=(prim.data[0],prim.data[1]); b=(prim.data[2],prim.data[3])
                    if self._preview_segment_visible(a,b,effective):canvas.create_line(*mappt(*a),*mappt(*b),fill=cad_pen,width=linew,tags=("preview_content",))
                elif prim.kind=="polyline":
                    pts=list(prim.data)
                    for a,b in zip(pts,pts[1:]):
                        if self._preview_segment_visible(a,b,effective):canvas.create_line(*mappt(*a),*mappt(*b),fill=cad_pen,width=linew,tags=("preview_content",))
                elif prim.kind in ("circle","arc"):
                    if prim.kind=="circle":cx,cy,r=prim.data; a1,a2=0.0,360.0
                    else:cx,cy,r,a1,a2=prim.data
                    delta=(a2-a1)%360 or 360; steps=max(18,int(delta/6)); pts=_arc_points(float(cx),float(cy),float(r),float(a1),float(a1)+delta,steps)
                    scr=[]
                    for q in pts:scr.extend(mappt(*q))
                    if len(scr)>=4:canvas.create_line(*scr,fill=cad_pen,width=linew,smooth=False,tags=("preview_content",))
                elif prim.kind=="point":
                    x,y=prim.data
                    if xmin<=x<=xmax and ymin<=y<=ymax:
                        sx,sy=mappt(x,y); canvas.create_oval(sx-1,sy-1,sx+1,sy+1,fill=cad_pen,outline=cad_pen,tags=("preview_content",))
                elif prim.kind=="text":
                    x,y,t,h,rot=prim.data
                    if xmin<=x<=xmax and ymin<=y<=ymax:
                        sx,sy=mappt(x,y); fs=max(5,min(24,int(abs(float(h)*scale*ps)*.78)))
                        canvas.create_text(sx,sy,text=str(t),anchor="sw",fill=cad_pen,font=("Arial",fs),angle=-float(rot),tags=("preview_content",))
            except Exception:pass
        # El-symboler.
        for pl in self.placements:
            if not self.layer_visibility.get(symbol_layer(pl.symbol),True):continue
            pen=normalize_hex_color(pl.color); lw=max(1,float(pl.line_width)/25.4*72.0*ps)
            def world(lx,ly):rx,ry=rotate_point(lx,ly,pl.rotation); return pl.x+rx,pl.y+ry
            for prim in symbol_primitives(pl.symbol,pl.size):
                typ=prim[0]
                try:
                    if typ=="line":canvas.create_line(*mappt(*world(prim[1],prim[2])),*mappt(*world(prim[3],prim[4])),fill=pen,width=lw,tags=("preview_content",))
                    elif typ in ("circle","arc"):
                        if typ=="circle":_,cx,cy,r=prim;a1,a2=0,360
                        else:_,cx,cy,r,a1,a2=prim
                        delta=a2-a1 if typ=="arc" else 360; steps=max(16,int(abs(delta)/6)); scr=[]
                        for j in range(steps+1):
                            aa=math.radians(a1+delta*j/steps); scr.extend(mappt(*world(cx+r*math.cos(aa),cy+r*math.sin(aa))))
                        if len(scr)>=4:canvas.create_line(*scr,fill=pen,width=lw,tags=("preview_content",))
                    elif typ=="polyline":
                        scr=[]
                        for q in prim[1]:scr.extend(mappt(*world(*q)))
                        if len(scr)>=4:canvas.create_line(*scr,fill=pen,width=lw,tags=("preview_content",))
                    elif typ=="text":
                        _,x,y,t,h=prim; sx,sy=mappt(*world(x,y)); fs=max(5,min(22,int(h*scale*ps)))
                        canvas.create_text(sx,sy,text=str(t),fill=pen,font=("Segoe UI",fs,"bold"),angle=-float(pl.rotation),tags=("preview_content",))
                except Exception:pass
            # Printmærkning svarer til PDF: fixed page-space, diskret hvid baggrund.
            assoc=association_display(pl)
            if assoc and self.layer_visibility.get(META_LAYER,True):
                ax,ay=association_world_point(pl); tx,ty=mappt(ax,ay); fs=max(5,int(7*ps));
                iid=canvas.create_text(tx,ty,text=assoc,anchor="sw",fill="#285d9b",font=("Segoe UI",fs,"bold"),tags=("preview_annotation",)); bb=canvas.bbox(iid)
                if bb:
                    bg=canvas.create_rectangle(bb[0]-1,bb[1]-1,bb[2]+1,bb[3]+1,fill="#ffffff",outline="",tags=("preview_annotation",)); canvas.tag_lower(bg,iid)
            lines=symbol_annotation_lines(pl,self.annotation_style.get())
            if lines and self.layer_visibility.get(META_LAYER,True):
                tx,ty=mappt(pl.x,pl.y); tx+=5*ps; ty-=5*ps; fs=max(5,int(max(5.5,min(8.0,float(self.annotation_font_size.get())-1.5))*ps)); text="\n".join(lines)
                iid=canvas.create_text(tx,ty,text=text,anchor="sw",justify="left",fill="#176b3a",font=("Segoe UI",fs),tags=("preview_annotation",)); bb=canvas.bbox(iid)
                if bb:
                    bg=canvas.create_rectangle(bb[0]-1,bb[1]-1,bb[2]+1,bb[3]+1,fill="#ffffff",outline="",tags=("preview_annotation",)); canvas.tag_lower(bg,iid)
        # Fri tekst.
        if self.layer_visibility.get(FREE_TEXT_LAYER,True):
            for item in self.texts:
                if not str(item.text).strip():continue
                sx,sy=mappt(item.x,item.y); fs=max(1,min(42,int(float(item.height)*scale*ps)))
                canvas.create_text(sx,sy,text=str(item.text),fill=normalize_hex_color(item.color),font=("Segoe UI",fs),angle=-float(item.rotation),tags=("preview_content",))
        # Kabler/ledninger + mærkning.
        for cable in self.cables:
            if not self.layer_visibility.get(cable.layer,True) or len(cable.points)<2:continue
            scr=[]
            for q in cable.points:scr.extend(mappt(*q))
            canvas.create_line(*scr,fill="#d00000",width=max(1,float(cable.line_width)/25.4*72.0*ps),tags=("preview_content",))
            text=cable_display_label(cable)
            if text and self.layer_visibility.get(META_LAYER,True):
                wx,wy=cable_label_point(cable); mx,my=mappt(wx,wy); fs=max(5,int(6*ps)); iid=canvas.create_text(mx+3*ps,my-3*ps,text=text,anchor="sw",fill="#176b3a",font=("Segoe UI",fs),tags=("preview_annotation",)); bb=canvas.bbox(iid)
                if bb:
                    bg=canvas.create_rectangle(bb[0]-1,bb[1]-1,bb[2]+1,bb[3]+1,fill="#ffffff",outline="",tags=("preview_annotation",)); canvas.tag_lower(bg,iid)
        # Hvid fysisk margen og diskret markering af det printbare område.
        plx,pty=pagept(margin,ph-margin); prx,pry=pagept(pw-margin,margin)
        # Marginmasker ligger over tegningen og efterligner PDF clip-path.
        canvas.create_rectangle(left,top,left+page_w,pty,fill="#ffffff",outline="",tags=("preview_mask",))
        canvas.create_rectangle(left,pry,left+page_w,top+page_h,fill="#ffffff",outline="",tags=("preview_mask",))
        canvas.create_rectangle(left,pty,plx,pry,fill="#ffffff",outline="",tags=("preview_mask",))
        canvas.create_rectangle(prx,pty,left+page_w,pry,fill="#ffffff",outline="",tags=("preview_mask",))
        canvas.create_rectangle(plx,pty,prx,pry,outline="#d2d5d9",dash=(3,3),width=1,tags=("preview_margin",))
        canvas.create_rectangle(left,top,left+page_w,top+page_h,outline=self._theme_color("page_border"),width=1,tags=("preview_page_border",))
        if self._print_preview_info_var is not None:
            mmw=pw/72*25.4; mmh=ph/72*25.4
            self._print_preview_info_var.set(f"{paper} · {mmw:.0f} × {mmh:.0f} mm · {scope} · {PRINT_MARGIN_MM:g} mm margen")

    def _schedule_print_preview_redraw(self,delay=40):
        if self._print_preview_canvas is None:return
        if self._preview_redraw_job is not None:
            try:self.after_cancel(self._preview_redraw_job)
            except Exception:pass
        self._preview_redraw_job=self.after(max(0,int(delay)),self._run_print_preview_redraw)

    def _run_print_preview_redraw(self):
        self._preview_redraw_job=None
        if self.print_preview_window is None or not self.print_preview_window.winfo_exists():return
        try:
            self._draw_print_preview(self._print_preview_canvas,self._preview_paper.get(),self._preview_orientation.get(),self._preview_scope.get())
        except Exception as exc:
            self._print_preview_info_var.set(f"Forhåndsvisning kunne ikke tegnes: {exc}")

    def _apply_print_preview_settings(self):
        self.paper_size.set(self._preview_paper.get()); self.page_orientation.set(self._preview_orientation.get()); self.print_scope.set(self._preview_scope.get()); self._save_runtime_settings()

    def _close_print_preview(self):
        if self._preview_redraw_job is not None:
            try:self.after_cancel(self._preview_redraw_job)
            except Exception:pass
            self._preview_redraw_job=None
        win=self.print_preview_window
        self._print_preview_canvas=None; self._print_preview_info_var=None; self.print_preview_window=None
        if win is not None:
            try:win.destroy()
            except tk.TclError:pass

    def show_print_preview(self):
        if not self.doc:
            messagebox.showinfo("Forhåndsvisning","Åbn først en DWG- eller DXF-tegning."); return
        if self.selected_index is not None:self.apply_symbol_properties()
        try:
            if self.print_preview_window is not None and self.print_preview_window.winfo_exists():
                self.print_preview_window.deiconify(); self.print_preview_window.lift(); self._schedule_print_preview_redraw(0); return
        except tk.TclError:
            self.print_preview_window=None; self._print_preview_canvas=None; self._print_preview_info_var=None
        win=tk.Toplevel(self); self.print_preview_window=win; win.title("Forhåndsvisning – PDF / udskrift"); win.geometry("1100x760"); win.minsize(760,540); win.transient(self)
        win.columnconfigure(1,weight=1); win.rowconfigure(0,weight=1)
        controls=ttk.Frame(win,padding=14); controls.grid(row=0,column=0,sticky="ns")
        ttk.Label(controls,text="Udskriftslayout",font=("Segoe UI",13,"bold")).pack(anchor="w",pady=(0,10))
        self._preview_paper=tk.StringVar(value=self.paper_size.get()); self._preview_orientation=tk.StringVar(value=self.page_orientation.get()); self._preview_scope=tk.StringVar(value=self.print_scope.get())
        ttk.Label(controls,text="Papir").pack(anchor="w"); pc=ttk.Combobox(controls,textvariable=self._preview_paper,values=["A4","A3"],state="readonly",width=18); pc.pack(fill="x",pady=(2,8))
        ttk.Label(controls,text="Orientering").pack(anchor="w"); oc=ttk.Combobox(controls,textvariable=self._preview_orientation,values=["Auto","Portræt","Landskab"],state="readonly",width=18); oc.pack(fill="x",pady=(2,8))
        ttk.Label(controls,text="Område").pack(anchor="w"); sc=ttk.Combobox(controls,textvariable=self._preview_scope,values=list(PRINT_SCOPES),state="readonly",width=18); sc.pack(fill="x",pady=(2,8))
        ttk.Separator(controls).pack(fill="x",pady=10)
        ttk.Label(controls,text=f"Fast margen: {PRINT_MARGIN_MM:g} mm",style="Muted.TLabel").pack(anchor="w")
        ttk.Label(controls,text="Aktuel visning bruger det udsnit, du ser i editoren. Justér zoom/pan i hovedvinduet hvis udsnittet skal ændres.",style="Muted.TLabel",wraplength=210,justify="left").pack(anchor="w",pady=(5,12))
        def use_settings():self._apply_print_preview_settings(); self._schedule_print_preview_redraw(0)
        for var in (self._preview_paper,self._preview_orientation,self._preview_scope):var.trace_add("write",lambda *_:use_settings())
        ttk.Button(controls,text="Gem PDF…",command=lambda:(self._apply_print_preview_settings(),self.export_pdf())).pack(fill="x",pady=(6,3))
        ttk.Button(controls,text="Udskriv…",command=lambda:(self._apply_print_preview_settings(),self.print_plan())).pack(fill="x",pady=3)
        ttk.Button(controls,text="Luk",command=self._close_print_preview).pack(fill="x",pady=(12,3))
        right=ttk.Frame(win,padding=(0,12,12,12)); right.grid(row=0,column=1,sticky="nsew"); right.columnconfigure(0,weight=1); right.rowconfigure(0,weight=1)
        self._print_preview_canvas=tk.Canvas(right,background=self._theme_color("preview_bg"),highlightthickness=0); self._print_preview_canvas.grid(row=0,column=0,sticky="nsew")
        self._print_preview_info_var=tk.StringVar(value="Forbereder forhåndsvisning…")
        ttk.Label(right,textvariable=self._print_preview_info_var,style="Muted.TLabel",anchor="center").grid(row=1,column=0,sticky="ew",pady=(7,0))
        self._print_preview_canvas.bind("<Configure>",lambda e:self._schedule_print_preview_redraw(60))
        win.protocol("WM_DELETE_WINDOW",self._close_print_preview)
        self._apply_theme(redraw=False); self._schedule_print_preview_redraw(0)

    # --------------------------------------------------------------- EXPORT
    def _doc_with_symbols(self):
        if not self.doc:raise RuntimeError("Ingen tegning er åbnet.")
        self.sync_cable_connections()
        out=ezdxf.new(self.doc.dxfversion,setup=True)
        try:
            from ezdxf.addons.importer import Importer
            imp=Importer(self.doc,out); imp.import_modelspace(); imp.finalize()
        except Exception:
            import copy; out=copy.deepcopy(self.doc)
        ensure_layers(out); msp=out.modelspace()
        for p in self.placements:add_placement_to_dxf(msp,p,self.annotation_style.get())
        for cable in self.cables:add_cable_to_dxf(msp,cable)
        for item in self.texts:add_free_text_to_dxf(msp,item)
        return out

    def export_pdf(self):
        if not self.doc:return
        if self.selected_index is not None:self.apply_symbol_properties()
        p=filedialog.asksaveasfilename(title="Eksportér PDF",defaultextension=".pdf",filetypes=[("PDF","*.pdf")])
        if not p:return
        try:
            ext=self._print_extents_for_scope_value(self.print_scope.get())
            fill=(self.print_scope.get()=="Aktuel visning")
            export_vector_pdf(p,self.cad_primitives,self.placements,self.cables,self.layer_visibility,
                              self.paper_size.get(),self.page_orientation.get(),self.annotation_style.get(),
                              self.annotation_font_size.get(),extents_override=ext,texts=self.texts,fill_page=fill)
            self.status_var.set(f"Eksporteret PDF: {Path(p).name} · {self.paper_size.get()} · {self.print_scope.get().lower()}")
        except Exception as e:messagebox.showerror("PDF-eksport mislykkedes",str(e))

    def print_plan(self):
        if not self.doc:return
        if self.selected_index is not None:self.apply_symbol_properties()
        if os.name!="nt":
            messagebox.showinfo("Udskrivning","Direkte udskrivning er beregnet til Windows. Brug 'PDF…' på dette system."); return
        try:
            import win32print
            printer=win32print.GetDefaultPrinter()
            ext=self._print_extents_for_scope_value(self.print_scope.get())
            if not messagebox.askokcancel(
                "Udskriv",
                f"Printer: {printer}\n\nFormat: {self.paper_size.get()} - {self.page_orientation.get()}\n"
                f"Område: {self.print_scope.get()}\nKun synlige lag udskrives.\n\nFortsæt?"
            ):return
            try:
                used=print_vector_windows(
                    self.cad_primitives,self.placements,self.cables,self.layer_visibility,
                    self.paper_size.get(),self.page_orientation.get(),self.annotation_style.get(),
                    self.annotation_font_size.get(),extents_override=ext,printer_name=printer,texts=self.texts,
                    fill_page=(self.print_scope.get()=="Aktuel visning")
                )
                self.status_var.set(f"Udskrift sendt til {used} · {self.paper_size.get()} · {self.print_scope.get().lower()}")
            except Exception as native_error:
                # Fallback er bevidst IKKE shell-verb 'print', fordi netop den vej
                # ofte tvinger A3-dokumenter over på printerens A4-standard. Lav
                # i stedet en korrekt dimensioneret PDF og åbn den, så brugeren
                # kan se/ændre driverens papirvalg manuelt.
                temp_dir=Path(tempfile.gettempdir())/"ElplanDWGEditor"; temp_dir.mkdir(parents=True,exist_ok=True)
                pdf_path=temp_dir/f"elplan_print_{int(time.time()*1000)}.pdf"
                export_vector_pdf(pdf_path,self.cad_primitives,self.placements,self.cables,self.layer_visibility,
                                  self.paper_size.get(),self.page_orientation.get(),self.annotation_style.get(),
                                  self.annotation_font_size.get(),extents_override=ext,texts=self.texts,
                                  fill_page=(self.print_scope.get()=="Aktuel visning"))
                try:os.startfile(str(pdf_path))
                except Exception:pass
                messagebox.showwarning(
                    "Direkte udskrivning kunne ikke gennemføres",
                    f"{native_error}\n\nEn {self.paper_size.get()}-PDF er åbnet i stedet. "
                    "Vælg printerens korrekte papirbakke/papirformat i udskriftsdialogen."
                )
        except Exception as e:messagebox.showerror("Udskrivning mislykkedes",str(e))

    def export_dxf(self):
        if not self.doc:return
        p=filedialog.asksaveasfilename(title="Eksportér DXF",defaultextension=".dxf",filetypes=[("DXF","*.dxf")])
        if not p:return
        try:self._doc_with_symbols().saveas(p); self.status_var.set(f"Eksporteret DXF: {Path(p).name}")
        except Exception as e:messagebox.showerror("Eksport mislykkedes",str(e))

    def export_dwg(self):
        if not self.doc:return
        if not self.ensure_oda_ready(True):return
        p=filedialog.asksaveasfilename(title="Eksportér DWG",defaultextension=".dwg",filetypes=[("DWG","*.dwg")])
        if not p:return
        try:odafc.export_dwg(self._doc_with_symbols(),p,replace=True); self.status_var.set(f"Eksporteret DWG: {Path(p).name}")
        except Exception as e:messagebox.showerror("Eksport mislykkedes",self._friendly_error(e))

    # --------------------------------------------------------------- PROJECT
    def save_project(self,use_existing=False):
        if not self.file_path:
            messagebox.showinfo("Projekt","Åbn først en tegning."); return False
        if self.selected_index is not None:self.apply_symbol_properties()
        p=self.project_path if (use_existing and self.project_path) else filedialog.asksaveasfilename(title="Gem projekt",defaultextension=".elplan.json",filetypes=[("Elplan-projekt","*.elplan.json"),("JSON","*.json")])
        if not p:return False
        try:
            Path(p).write_text(json.dumps(self._project_data(),indent=2,ensure_ascii=False),encoding="utf-8")
            self.project_path=str(p); self._add_recent_project(p); self._clear_recovery(); self._set_dirty(False)
            self.status_var.set(f"Projekt gemt: {Path(p).name}"); return True
        except Exception as e:
            messagebox.showerror("Kunne ikke gemme projekt",str(e)); return False

    def open_project(self):
        p=filedialog.askopenfilename(title="Åbn projekt",filetypes=[("Elplan-projekt","*.elplan.json"),("JSON","*.json")])
        if p:self._open_project_path(p)

    def _open_project_path(self,p,recovery=False):
        if not recovery and not self._confirm_discard_changes():return False
        try:
            data=json.loads(Path(p).read_text(encoding="utf-8")); src=data["source_file"]
            if not Path(src).is_file():
                messagebox.showinfo("Find tegning",f"Originalfilen blev ikke fundet:\n{src}\n\nVælg DWG/DXF-filen igen.")
                src=filedialog.askopenfilename(filetypes=[("CAD-filer","*.dwg *.dxf")])
                if not src:return False
            if Path(src).suffix.lower()==".dwg" and not self.ensure_oda_ready(True):return False
            self.status_var.set("Åbner projekt og opbygger vektorvisning…"); self.update_idletasks()
            self.doc=load_document(src); self.file_path=src; ensure_layers(self.doc); self.extent=document_extents(self.doc)
            self.cad_primitives,self.primitive_counts=extract_cad_primitives(self.doc); self._build_snap_index()
            register_custom_symbol_records(data.get("custom_symbols",[]))
            for raw in data.get("placements",[]):
                code=str(raw.get("symbol", "")) if isinstance(raw,dict) else ""
                if is_custom_combo_symbol(code):register_custom_symbol(code,None)
            # Nyregistreringer kan være relevante for palette/favoritter og farvestandarder.
            for code in SYMBOL_NAMES_BY_CODE:self.symbol_color_defaults.setdefault(code,DEFAULT_SYMBOL_COLOR)
            self.placements=[]
            for raw in data.get("placements",[]):
                item=dict(raw); item.setdefault("line_width",0.25); item.setdefault("color",DEFAULT_SYMBOL_COLOR); item.setdefault("associations",[]); item.setdefault("association_channels",[]); item.setdefault("locked",False); item.setdefault("parent_light_uid","")
                item.setdefault("label_mode","Fælles"); item.setdefault("switch_label",""); item.setdefault("switch_group",""); item.setdefault("socket_label",""); item.setdefault("socket_group","")
                item["label_mode"]=normalize_combo_label_mode(item.get("label_mode")); item["color"]=normalize_hex_color(item["color"]); item["associations"]=normalize_associations(item.get("associations",[])); self.placements.append(Placement(**item))
            self.cables=[]
            for raw in data.get("cables",[]):
                item=dict(raw); item["points"]=[tuple(q) for q in item.get("points",[])]; item.setdefault("label",""); item.setdefault("cable_spec",""); item.setdefault("cable_id",""); item.setdefault("auto_label",False); item.setdefault("start_symbol_uid",""); item.setdefault("end_symbol_uid",""); item.setdefault("start_symbol_port",0); item.setdefault("end_symbol_port",0); item.setdefault("orthogonal",False); self.cables.append(CablePlacement(**item))
            self.texts=[]
            for raw in data.get("texts",[]):
                item=dict(raw); item.setdefault("height",250.0); item.setdefault("rotation",0.0); item.setdefault("color","#202020"); item["color"]=normalize_hex_color(item["color"]); self.texts.append(TextPlacement(**item))
            self._clear_symbol_selection(); self.selected_cable_index=None; self.selected_text_index=None
            self.creation_history=[("symbol",x) for x in self.placements]+[("cable",x) for x in self.cables]+[("text",x) for x in self.texts]
            default_size=data.get("default_symbol_size",data.get("global_symbol_size"))
            if default_size is None and self.placements:default_size=self.placements[0].size
            if default_size is None:self._set_default_symbol_size(); default_size=self.default_symbol_size
            self.default_symbol_size=float(default_size); self.default_symbol_line_width=float(data.get("default_symbol_line_width",0.25))
            try:self.spot_default_size=self._normalise_spot_size(data.get("spot_default_size",self.spot_default_size))
            except Exception:pass
            self.spot_size_var.set(self.spot_default_size)
            loaded_colors=data.get("symbol_color_defaults",{})
            if isinstance(loaded_colors,dict):
                for code in self.symbol_color_defaults:
                    if code in loaded_colors:self.symbol_color_defaults[code]=normalize_hex_color(loaded_colors[code])
            self._restore_default_symbol_controls()
            if data.get("cable_type") in CABLE_TYPES:self.cable_type.set(data["cable_type"])
            if "cable_spec" in data:self.cable_spec.set(str(data["cable_spec"]))
            if "cable_line_width" in data:self.cable_line_width.set(float(data["cable_line_width"]))
            if "cable_label" in data:self.cable_label.set(str(data["cable_label"]))
            if "cable_auto_label" in data:self.cable_auto_label.set(bool(data["cable_auto_label"]))
            if "cable_orthogonal" in data:self.cable_orthogonal.set(bool(data["cable_orthogonal"]))
            # Snap er med vilje IKKE projektspecifikt. Ældre projektfiler kan
            # indeholde snap_to_* = false; de felter ignoreres fra 0.19.3.
            # Den aktuelle brugerindstilling fra programmet bevares.
            if "continuous_placement" in data:self.continuous_placement.set(bool(data["continuous_placement"]))
            self.default_text_height=float(data.get("default_text_height",250.0)); self.default_text_color=normalize_hex_color(data.get("default_text_color","#202020"))
            if data.get("annotation_style") in ANNOTATION_STYLES:self.annotation_style.set(data["annotation_style"])
            if "annotation_font_size" in data:
                try:self.annotation_font_size.set(max(7,min(10,int(data["annotation_font_size"]))))
                except Exception:pass
            if "annotation_auto_place" in data:self.annotation_auto_place.set(bool(data["annotation_auto_place"]))
            if data.get("paper_size") in ("A4","A3"):self.paper_size.set(data["paper_size"])
            if data.get("page_orientation") in ("Auto","Portræt","Landskab"):self.page_orientation.set(data["page_orientation"])
            if data.get("print_scope") in PRINT_SCOPES:self.print_scope.set(data["print_scope"])
            self.project_path=(str(data.get("_recovery_project_path")) if recovery and data.get("_recovery_project_path") else (None if recovery else str(p)))
            self._reset_history(); self._init_layer_visibility(data.get("layer_visibility")); self._rebuild_quick_symbols(); self._rebuild_symbol_palette(); self.fit_view()
            repaired=self._repair_legacy_cable_connections()
            if repaired:
                self.redraw_placements(); self.status_var.set(f"Projekt åbnet · {repaired} ældre kabeltilslutning(er) blev genkendt automatisk.")
            self._update_mode_status(); self._update_snap_status()
            self.vector_status_var.set((f"Viewer: {len(self.cad_primitives):,} vektorobjekter · Snap: canvas + {len(self.snap_segments):,} segmenter").replace(",","."))
            if recovery:
                self._set_dirty(True); self.status_var.set("Automatisk gemt arbejde blev gendannet. Gem projektet, når du er klar.")
            else:
                self._add_recent_project(p); self._clear_recovery(); self._set_dirty(False); self.status_var.set(f"Projekt åbnet: {Path(p).name}")
            return True
        except Exception as e:
            messagebox.showerror("Kunne ikke åbne projekt",str(e)); return False



def main():
    app=ElplanEditor(); app.mainloop()


if __name__=="__main__":main()
