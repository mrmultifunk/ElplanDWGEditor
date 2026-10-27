from __future__ import annotations

"""Responsive cable inspector/panel layout.

The panel deliberately separates *drawing defaults* from *editing an existing
physical cable*.  This keeps the selected-cable inspector focused on the
properties that actually apply to that cable, while advanced drawing settings
stay out of the way until the user asks for them.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import core_logic as core
from qt_ui import DisclosureSection, tune_form_layout, tune_panel_layout
from qt_widgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QSpinBox,
    _set_color_button,
    _set_role,
)


class CablePanelMixin:
    """Build and switch the unified cable inspector between draw/edit context."""

    def _create_cable_dock(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        # A property panel should adapt to its dock width instead of asking the
        # user to pan sideways.  Long helper text wraps and advanced rows fold.
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        widget = QWidget()
        widget.setMinimumWidth(0)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        root = tune_panel_layout(QVBoxLayout(widget))

        self.cable_new_intro = QLabel(
            "Tegn en kabelstreng gennem de fysiske tilslutningssteder. Hvert stræk gemmes som sit eget kabel; gruppe/kreds kan deles af hele strengen."
        )
        self.cable_new_intro.setWordWrap(True)
        self.cable_new_intro.setObjectName("sectionHint")
        root.addWidget(self.cable_new_intro)

        # Selected-cable marking is intentionally first: naming is a frequent,
        # explicit user action and should not be buried below drawing defaults.
        root.addWidget(self._create_selected_cable_marking_panel())

        self.cable_data_group = QGroupBox("Kabeldata")
        data_root = QVBoxLayout(self.cable_data_group)
        data_root.setContentsMargins(10, 10, 10, 10)
        data_root.setSpacing(8)
        form = tune_form_layout(QFormLayout())
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self.cable_type_combo = QComboBox()
        self.cable_type_combo.addItems(["Kabel", "Patchkabel", "Ledning"])
        self.cable_category_combo = QComboBox()
        category_row = QWidget()
        category_layout = QHBoxLayout(category_row)
        category_layout.setContentsMargins(0, 0, 0, 0)
        category_layout.setSpacing(6)
        category_layout.addWidget(self.cable_category_combo, 1)
        category_edit = _set_role(QPushButton("Redigér…"), "quietButton")
        category_edit.clicked.connect(self.open_cable_categories_dialog)
        category_layout.addWidget(category_edit)

        self.cable_spec_combo = QComboBox()
        self.cable_spec_combo.setEditable(True)
        self.cable_spec_combo.addItems([
            "3G1,5", "3G2,5", "5G1,5", "5G2,5", "5G4", "5G6", "7G1,5",
            "CAT6 U/UTP", "CAT6A F/UTP", "CAT7 S/FTP",
        ])
        self.cable_group_edit = QLineEdit()
        self.cable_group_edit.setPlaceholderText("fx G05")
        self.cable_group_edit.setToolTip(
            "Logisk gruppe/kreds. Ved en tegnet streng opdateres gruppen samlet, mens hvert fysisk kabel fortsat er selvstændigt."
        )
        form.addRow("Kategori", category_row)
        form.addRow("Kabeltype", self.cable_spec_combo)
        form.addRow("Gruppe/kreds", self.cable_group_edit)
        data_root.addLayout(form)

        self.cable_category_definition = QLabel()
        self.cable_category_definition.setWordWrap(True)
        self.cable_category_definition.setObjectName("sectionHint")
        data_root.addWidget(self.cable_category_definition)

        self.cable_apply_selected = QPushButton("Anvend kabelændringer")
        self.cable_apply_selected.setObjectName("primaryButton")
        self.cable_apply_selected.clicked.connect(self.apply_selected_cable_properties)
        self.cable_apply_selected.setEnabled(False)
        self.cable_apply_selected.hide()
        data_root.addWidget(self.cable_apply_selected)
        root.addWidget(self.cable_data_group)

        self.cable_route_group = QGroupBox("Rute")
        route_root = QVBoxLayout(self.cable_route_group)
        route_root.setContentsMargins(9, 8, 9, 8)
        route_root.setSpacing(5)
        route_row = QHBoxLayout()
        route_row.setSpacing(6)
        route_row.addWidget(QLabel("Ruteføring"))
        self.cable_route_mode_combo = QComboBox()
        self.cable_route_mode_combo.addItem("Fri / diagonal", "free")
        self.cable_route_mode_combo.addItem("Ortogonal (90°)", "orthogonal")
        self.cable_route_mode_combo.setToolTip(
            "For et valgt kabel ændrer Anvend kabelændringer hele dette fysiske kabels ruteform."
        )
        route_row.addWidget(self.cable_route_mode_combo, 1)
        route_root.addLayout(route_row)
        self.cable_route_hint = QLabel("Fri / diagonal er standard. Klik ekstra punkter, hvor kabelvejen skal knække.")
        self.cable_route_hint.setWordWrap(True)
        self.cable_route_hint.setObjectName("sectionHint")
        route_root.addWidget(self.cable_route_hint)
        root.addWidget(self.cable_route_group)

        # New-cable-only drawing helpers.  They are folded by default and are
        # hidden completely when an existing cable is selected.
        drawing_group = QWidget()
        drawing_layout = QVBoxLayout(drawing_group)
        drawing_layout.setContentsMargins(4, 3, 4, 4)
        drawing_layout.setSpacing(5)
        self.cable_snap_symbols = QCheckBox("Snap til symboler / forbindelsespunkter")
        self.cable_snap_walls = QCheckBox("Snap til vægge")
        self.cable_snap_routes = QCheckBox("Snap til eksisterende kabelruter")
        self.cable_snap_routes.setToolTip(
            "Snapper nye knæk til centerlinjen på eksisterende kabler. Parallelle kabler kan dermed dele rute uden at dele data."
        )
        self.cable_assistant_enabled = QCheckBox("Interaktiv kabel-assistent")
        self.cable_assistant_enabled.setToolTip("Vis små hjælpekort ved fysiske symboltilslutninger under tegning.")
        self.cable_continuous = QCheckBox("Start automatisk et nyt kabel efter afslutning")
        for cb in (
            self.cable_snap_symbols,
            self.cable_snap_walls,
            self.cable_snap_routes,
            self.cable_assistant_enabled,
            self.cable_continuous,
        ):
            drawing_layout.addWidget(cb)
        drawing_hint = QLabel("Gælder kun mens du tegner nye kabler. Eksisterende kabler påvirkes ikke.")
        drawing_hint.setWordWrap(True)
        drawing_hint.setObjectName("sectionHint")
        drawing_layout.addWidget(drawing_hint)
        self.cable_drawing_disclosure = DisclosureSection("Tegning og snap", drawing_group, expanded=False)
        root.addWidget(self.cable_drawing_disclosure)

        # Compatibility field: extra marking is no longer a new-cable default.
        # It stays as an internal target for old settings/tests, but is never
        # surfaced in the panel and new cables are always created blank.
        self.cable_label_edit = QLineEdit(widget)
        self.cable_label_edit.hide()

        advanced_group = QWidget()
        advanced_root = QVBoxLayout(advanced_group)
        advanced_root.setContentsMargins(4, 3, 4, 4)
        advanced_root.setSpacing(7)
        advanced_form = tune_form_layout(QFormLayout())
        advanced_form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self.cable_id_edit = QLineEdit()
        self.cable_id_edit.setPlaceholderText("automatisk")
        self.cable_id_row = QWidget()
        id_layout = QHBoxLayout(self.cable_id_row)
        id_layout.setContentsMargins(0, 0, 0, 0)
        id_layout.setSpacing(6)
        id_layout.addWidget(self.cable_id_edit, 1)
        self.cable_next_id_button = _set_role(QPushButton("Næste"), "quietButton")
        self.cable_next_id_button.clicked.connect(self._set_next_cable_id)
        id_layout.addWidget(self.cable_next_id_button)
        self.cable_id_field_label = QLabel("Start-ID")
        advanced_form.addRow(self.cable_id_field_label, self.cable_id_row)

        self.cable_auto_label = QCheckBox("Vis kabel-ID + type på tegningen")
        self.cable_auto_label.setToolTip(
            "Styrer den kompakte automatiske planmærkning (fx K12 · 5G1,5). Ekstra mærkning håndteres separat og kun efter aktiv brugerhandling."
        )
        advanced_form.addRow("Planvisning", self.cable_auto_label)
        advanced_form.addRow("Objekttype", self.cable_type_combo)

        self.cable_width_spin = QDoubleSpinBox()
        self.cable_width_spin.setRange(.05, 5.0)
        self.cable_width_spin.setDecimals(2)
        self.cable_width_spin.setSingleStep(.05)
        advanced_form.addRow("Linjetykkelse [mm]", self.cable_width_spin)

        self.cable_color = QPushButton(core.DEFAULT_CABLE_COLOR)
        _set_color_button(self.cable_color, core.DEFAULT_CABLE_COLOR)
        self.cable_color.setToolTip("Farven styres normalt af kabelkategorien.")
        self.cable_color.clicked.connect(self.choose_cable_color)
        advanced_form.addRow("Farve", self.cable_color)

        self.cable_line_style = QComboBox()
        for style, label in core.CABLE_LINE_STYLES.items():
            self.cable_line_style.addItem(label, style)
        self.cable_line_style.setToolTip("Visuel linjetype på skærm og i PDF/print.")
        advanced_form.addRow("Linjetype", self.cable_line_style)
        advanced_root.addLayout(advanced_form)

        self.cable_id_hint = QLabel(
            "ID vælges automatisk. Start-ID bruges kun, hvis du bevidst vil starte den næste tegnede kabelstreng ved et bestemt nummer; efterfølgende fysiske kabelstykker nummereres videre."
        )
        self.cable_id_hint.setWordWrap(True)
        self.cable_id_hint.setObjectName("sectionHint")
        advanced_root.addWidget(self.cable_id_hint)
        category_hint = QLabel("Farve og linjetype styres normalt via kabelkategorien.")
        category_hint.setWordWrap(True)
        category_hint.setObjectName("sectionHint")
        advanced_root.addWidget(category_hint)
        self.cable_advanced_disclosure = DisclosureSection("Avancerede kabeldata", advanced_group, expanded=False)
        root.addWidget(self.cable_advanced_disclosure)

        visual_group = QWidget()
        visual_layout = QVBoxLayout(visual_group)
        visual_layout.setContentsMargins(4, 3, 4, 4)
        visual_layout.setSpacing(6)
        self.cable_parallel_lanes = QCheckBox("Adskil fælles kabelruter i parallelle baner")
        self.cable_parallel_lanes.setToolTip("Kun visuel forskydning. Kabelgeometri, længde og forbindelser ændres ikke.")
        visual_layout.addWidget(self.cable_parallel_lanes)
        lane_row = QHBoxLayout()
        lane_row.setSpacing(6)
        lane_row.addWidget(QLabel("Baneafstand"))
        self.cable_lane_gap_spin = QSpinBox()
        self.cable_lane_gap_spin.setRange(5, 18)
        self.cable_lane_gap_spin.setSuffix(" px")
        self.cable_lane_gap_spin.setToolTip("Afstand på skærmen mellem kabler, der følger samme logiske rute.")
        lane_row.addWidget(self.cable_lane_gap_spin)
        lane_row.addStretch(1)
        visual_layout.addLayout(lane_row)
        self.cable_bundle_badges_enabled = QCheckBox("Vis ×N på fælles ruter med 3+ kabler")
        self.cable_focus_related = QCheckBox("Fremhæv kabler ved valgt symbol")
        self.cable_focus_related.setToolTip("Kabler ved det valgte symbol forbliver tydelige, mens øvrige kabler tones ned.")
        visual_layout.addWidget(self.cable_bundle_badges_enabled)
        visual_layout.addWidget(self.cable_focus_related)
        visual_hint = QLabel("Kun visning. De fysiske kabler forbliver individuelle.")
        visual_hint.setWordWrap(True)
        visual_hint.setObjectName("sectionHint")
        visual_layout.addWidget(visual_hint)
        self.cable_visual_disclosure = DisclosureSection("Parallel visning", visual_group, expanded=False)
        root.addWidget(self.cable_visual_disclosure)

        self.cable_draw_status_host = QWidget()
        status_layout = QVBoxLayout(self.cable_draw_status_host)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(5)
        self.cable_tool_status = QLabel("Klar")
        self.cable_tool_status.setWordWrap(True)
        self.cable_tool_status.setObjectName("infoBanner")
        status_layout.addWidget(self.cable_tool_status)
        self.cable_route_label = QLabel("Forløb: —")
        self.cable_route_label.setWordWrap(True)
        self.cable_route_label.setObjectName("subtleText")
        status_layout.addWidget(self.cable_route_label)
        root.addWidget(self.cable_draw_status_host)

        # Kept for compatibility with the now-retired multi-section cable model.
        self.cable_section_group = QGroupBox("Indstillinger pr. afsnit")
        self.cable_section_group.setVisible(False)
        self.cable_section_combo = QComboBox()
        self.cable_section_route_combo = QComboBox()
        self.cable_section_route_combo.addItem("Fri / diagonal", "free")
        self.cable_section_route_combo.addItem("Ortogonal (90°)", "orthogonal")
        self.cable_section_apply = _set_role(QPushButton("Anvend på afsnit"), "quietButton")
        self.cable_section_apply.clicked.connect(self.apply_selected_cable_section_route)
        self.cable_section_spec_combo = QComboBox()
        self.cable_section_spec_combo.setEditable(True)
        self.cable_section_spec_combo.addItems(list(core.CABLE_SPEC_PRESETS) + ["CAT6 U/UTP", "CAT6A F/UTP", "CAT7 S/FTP"])
        self.cable_section_spec_apply = _set_role(QPushButton("Anvend kabeltype"), "quietButton")
        self.cable_section_spec_apply.clicked.connect(self.apply_selected_cable_section_spec)
        self.cable_section_hint = QLabel("")

        article_group = QGroupBox("Artikel / BOM")
        article_layout = QVBoxLayout(article_group)
        article_layout.setSpacing(6)
        self.cable_article_label = QLabel("Ingen artikel tilknyttet")
        self.cable_article_label.setWordWrap(True)
        self.cable_article_label.setObjectName("subtleText")
        article_layout.addWidget(self.cable_article_label)
        article_actions = QHBoxLayout()
        self.cable_choose_article = QPushButton("Vælg artikel…")
        self.cable_choose_article.setObjectName("primaryButton")
        self.cable_choose_article.clicked.connect(self.choose_cable_article)
        self.cable_clear_article = _set_role(QPushButton("Fjern"), "dangerButton")
        self.cable_clear_article.clicked.connect(self.clear_cable_article)
        article_actions.addWidget(self.cable_choose_article, 1)
        article_actions.addWidget(self.cable_clear_article)
        article_layout.addLayout(article_actions)
        article_hint = QLabel("Artikel og BOM-længde gælder kun det konkrete fysiske kabel.")
        article_hint.setWordWrap(True)
        article_hint.setObjectName("sectionHint")
        article_layout.addWidget(article_hint)
        root.addWidget(article_group)

        # 0.59.45: keep the complete pull length visible even when the detailed
        # length/report section is folded. This is the value most useful while
        # inspecting a physical cable piece.
        self.cable_chain_summary_label = QLabel("Hele kabeltrækket: —")
        self.cable_chain_summary_label.setObjectName("infoBanner")
        self.cable_chain_summary_label.setWordWrap(True)
        self.cable_chain_summary_label.setVisible(False)
        self.cable_chain_summary_label.setToolTip(
            "Samlet længde for alle fysiske kabelstykker i samme tegnede kabeltræk."
        )
        root.addWidget(self.cable_chain_summary_label)

        length_group = QGroupBox("Længdeestimat")
        length_layout = QVBoxLayout(length_group)
        length_layout.setSpacing(6)
        self.cable_length_scale_label = QLabel("Skala: —")
        self.cable_length_scale_label.setWordWrap(True)
        self.cable_live_length_label = QLabel("Markeret kabelstykke: —")
        self.cable_live_length_label.setObjectName("accentText")
        self.cable_chain_length_label = QLabel("Hele kabeltrækket: —")
        self.cable_chain_length_label.setObjectName("accentText")
        self.cable_chain_length_label.setWordWrap(True)
        self.cable_chain_length_label.setToolTip(
            "Summerer alle fysiske kabelstykker, der blev tegnet som samme sammenhængende kabeltræk."
        )
        length_layout.addWidget(self.cable_length_scale_label)
        length_layout.addWidget(self.cable_live_length_label)
        length_layout.addWidget(self.cable_chain_length_label)
        length_buttons = QHBoxLayout()
        scale_btn = _set_role(QPushButton("Skala / reserve…"), "quietButton")
        scale_btn.clicked.connect(self.show_cable_length_settings)
        report_btn = _set_role(QPushButton("Rapport…"), "quietButton")
        report_btn.clicked.connect(self.show_cable_length_report)
        length_buttons.addWidget(scale_btn)
        length_buttons.addWidget(report_btn)
        length_layout.addLayout(length_buttons)
        self.cable_length_disclosure = DisclosureSection("Længde og rapport", length_group, expanded=False)
        root.addWidget(self.cable_length_disclosure)

        self.cable_draw_controls = QWidget()
        draw_root = QVBoxLayout(self.cable_draw_controls)
        draw_root.setContentsMargins(0, 0, 0, 0)
        draw_root.setSpacing(7)
        start = QPushButton("Start / nyt kabel")
        start.setObjectName("primaryButton")
        start.clicked.connect(self._start_cable_from_panel)
        draw_root.addWidget(start)
        actions = QHBoxLayout()
        actions.setSpacing(6)
        finish = QPushButton("Afslut")
        finish.clicked.connect(self.view.finish_cable)
        undo_point = _set_role(QPushButton("Sidste knæk"), "quietButton")
        undo_point.clicked.connect(self.view.remove_last_cable_point)
        cancel_current = _set_role(QPushButton("Annuller"), "dangerButton")
        cancel_current.clicked.connect(self._cancel_current_cable)
        actions.addWidget(finish)
        actions.addWidget(undo_point)
        actions.addWidget(cancel_current)
        draw_root.addLayout(actions)
        keys = QLabel("Klik = næste punkt · Enter/højreklik = afslut streng · Backspace = sidste punkt · Esc = luk værktøj")
        keys.setWordWrap(True)
        keys.setObjectName("sectionHint")
        draw_root.addWidget(keys)
        root.addWidget(self.cable_draw_controls)
        root.addStretch(1)

        scroll.setWidget(widget)
        self.cable_page = scroll
        self.inspector_stack.addWidget(scroll)

        # Live updates while drawing/editing.
        self.cable_type_combo.currentTextChanged.connect(self._cable_type_changed)
        self.cable_category_combo.currentIndexChanged.connect(self._cable_category_changed)
        self.cable_spec_combo.currentTextChanged.connect(self._cable_panel_changed)
        self.cable_group_edit.textChanged.connect(self._cable_panel_changed)
        self.cable_id_edit.textChanged.connect(self._cable_panel_changed)
        self.cable_label_edit.textChanged.connect(self._cable_panel_changed)
        self.cable_width_spin.valueChanged.connect(self._cable_panel_changed)
        self.cable_line_style.currentIndexChanged.connect(self._cable_line_style_changed)
        self.cable_auto_label.toggled.connect(self._cable_panel_changed)
        self.cable_route_mode_combo.currentIndexChanged.connect(self._cable_route_mode_changed)
        self.cable_snap_symbols.toggled.connect(self._cable_panel_changed)
        self.cable_snap_walls.toggled.connect(self._cable_panel_changed)
        self.cable_snap_routes.toggled.connect(self._cable_panel_changed)
        self.cable_snap_routes.toggled.connect(self._cable_visual_settings_changed)
        self.cable_assistant_enabled.toggled.connect(self._cable_assistant_toggled)
        self.cable_parallel_lanes.toggled.connect(self._cable_visual_settings_changed)
        self.cable_lane_gap_spin.valueChanged.connect(self._cable_visual_settings_changed)
        self.cable_bundle_badges_enabled.toggled.connect(self._cable_visual_settings_changed)
        self.cable_focus_related.toggled.connect(self._cable_visual_settings_changed)

        # Restore defaults/settings atomically.
        from PySide6.QtCore import QSignalBlocker
        self._loading_cable_panel = True
        restore_widgets = (
            self.cable_type_combo, self.cable_category_combo, self.cable_spec_combo,
            self.cable_group_edit, self.cable_label_edit, self.cable_width_spin,
            self.cable_line_style, self.cable_auto_label, self.cable_route_mode_combo,
            self.cable_snap_symbols, self.cable_snap_walls, self.cable_snap_routes,
            self.cable_assistant_enabled, self.cable_parallel_lanes,
            self.cable_lane_gap_spin, self.cable_bundle_badges_enabled,
            self.cable_focus_related, self.cable_continuous,
        )
        blockers = [QSignalBlocker(w) for w in restore_widgets]
        try:
            saved_type = str(self.project.raw.get("cable_type", "Kabel") or "Kabel")
            if saved_type not in core.CABLE_TYPES:
                saved_type = "Kabel"
            self.cable_type_combo.setCurrentText(saved_type)
            self._populate_cable_category_combo(str(self.project.raw.get("cable_category", core.DEFAULT_CABLE_CATEGORY) or core.DEFAULT_CABLE_CATEGORY))
            self.cable_spec_combo.setCurrentText(str(self.project.raw.get("cable_spec", "3G1,5") or "3G1,5"))
            self.cable_group_edit.setText(str(self.project.raw.get("cable_circuit_id", "") or ""))
            # Extra marking is intentionally not restored as a default for new cables.
            self.cable_label_edit.setText("")
            self.cable_width_spin.setValue(float(self.project.raw.get("cable_line_width", .35) or .35))
            self._apply_category_style_to_panel()
            self.cable_auto_label.setChecked(True)
            route_mode = str(self.app_settings.get("cable_route_mode", "free") or "free").strip().lower()
            route_idx = self.cable_route_mode_combo.findData("orthogonal" if route_mode == "orthogonal" else "free")
            self.cable_route_mode_combo.setCurrentIndex(max(0, route_idx))
            self.cable_snap_symbols.setChecked(True)
            self.cable_snap_walls.setChecked(True)
            self.cable_snap_routes.setChecked(bool(self.app_settings.get("cable_snap_routes", True)))
            self.cable_assistant_enabled.setChecked(bool(self.app_settings.get("cable_assistant_enabled", True)))
            self.cable_parallel_lanes.setChecked(bool(self.app_settings.get("cable_parallel_lanes", True)))
            try:
                self.cable_lane_gap_spin.setValue(int(self.app_settings.get("cable_lane_gap_px", 10)))
            except Exception:
                self.cable_lane_gap_spin.setValue(10)
            self.cable_bundle_badges_enabled.setChecked(bool(self.app_settings.get("cable_bundle_badges", True)))
            self.cable_focus_related.setChecked(bool(self.app_settings.get("cable_focus_related", True)))
            self.cable_continuous.setChecked(False)
        finally:
            blockers.clear()
            self._loading_cable_panel = False
        self._set_next_cable_id()
        self._set_cable_panel_context(None)
        self._refresh_cable_article_ui()
        self._refresh_cable_length_ui()

    def _set_cable_panel_context(self, cable) -> None:
        """Show only controls relevant to a new route or a selected physical cable."""
        selected = cable is not None
        if hasattr(self, "cable_new_intro"):
            self.cable_new_intro.setVisible(not selected)
        if hasattr(self, "cable_drawing_disclosure"):
            self.cable_drawing_disclosure.setVisible(not selected)
        if hasattr(self, "cable_draw_status_host"):
            self.cable_draw_status_host.setVisible(not selected)
        if hasattr(self, "cable_draw_controls"):
            self.cable_draw_controls.setVisible(not selected)
        if hasattr(self, "cable_apply_selected"):
            self.cable_apply_selected.setVisible(selected)
        if hasattr(self, "cable_id_field_label"):
            self.cable_id_field_label.setText("Kabel-ID" if selected else "Start-ID")
        if hasattr(self, "cable_next_id_button"):
            self.cable_next_id_button.setVisible(not selected)
        if hasattr(self, "cable_id_hint"):
            if selected:
                self.cable_id_hint.setText("Kabel-ID er den fysiske kabelidentifikation. Ret den kun, hvis kablet bevidst skal omnummereres.")
            else:
                self.cable_id_hint.setText(
                    "ID vælges automatisk. Start-ID er kun en avanceret mulighed, hvis næste kabelstreng bevidst skal starte ved et bestemt nummer; resten nummereres videre automatisk."
                )
        if hasattr(self, "cable_data_group"):
            self.cable_data_group.setTitle("Valgt kabel" if selected else "Nyt kabel")
