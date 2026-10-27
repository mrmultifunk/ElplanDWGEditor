# Bidrag til Elplan DWG Editor

Projektets primære mål er at være et enkelt visualiseringsværktøj til elplaner. Nye funktioner bør derfor som udgangspunkt reducere klik, gøre placering/redigering mere forudsigelig eller forbedre visningen uden at gøre brugerfladen CAD-tung.

## Lokal udvikling

1. Installer Python 3.11 eller nyere.
2. Kør `python -m pip install -r requirements.txt`.
3. Start programmet med `python main.py` eller `start_windows.bat`.
4. Kør hele testsuiten fra projektroden med `pytest -q`.
5. Tests ligger samlet i `tests/`; versionsnoter og audits ligger i `docs/history/`.

DWG-import kræver ODA File Converter. DXF kan bruges uden ODA.

## Principper

- Bevar en enkel standardarbejdsgang.
- Nye avancerede indstillinger bør have fornuftige defaults og helst ikke være nødvendige for almindeligt arbejde.
- Symboler, kabler og tekst skal fortsat være vektorbaserede.
- Eksisterende projektfiler bør så vidt muligt kunne åbnes efter opdateringer.
- Tilføj eller opdater en test ved fejlrettelser, især for snap, eksport og projektformat.

## Qt-modulgrænser fra 0.53.0

`qt_app.py` er fortsat hovedcontrolleren, men nyt kode bør ikke automatisk placeres dér:

- `qt_ui.py`: fælles GUI-metrics og små layout-/dock-primitiver. Hardcodede marginer og standardpanelmål bør som udgangspunkt ikke spredes i featurekode.
- `qt_workspace.py`: hovedvinduets chrome, samlet inspector, kontekstværktøjslinje og maskinlokal workspace-layout.
- `qt_theme.py`: palette, QSS, system/light/dark og fælles Qt-style.
- `qt_hover.py`: ikke-modale hover-kort og deres preview-tegning.
- `qt_cable_panel.py`: responsivt kabelværktøj/inspector-layout; hold tegne-defaults og valgt-kabel-redigering adskilt.
- `qt_cable_attach.py`: målrettet interaktionsflow for efterfølgende fysisk kobling af symbol til eksisterende kabel.
- `qt_cable_sections.py`: GUI-flow for lokale connection-to-connection-indstillinger på samme kabel, herunder ruteføring og kabeltype.
- `qt_graphics.py`: scene-items, CAD-view, snap og interaktiv geometri.
- `qt_commands.py`: Undo/Redo-kommandoer.
- `qt_table_utils.py`: fælles tabelmodel/kolonneadfærd.
- `core_logic.py`: Qt-uafhængig domænelogik som skal kunne enhedstestes uden GUI.

Hvis en ny funktion kan udtrykkes uden Qt, skal den som udgangspunkt ligge i `core_logic.py` eller et andet rent domænemodul. Store nye dialogfamilier bør få eget Qt-modul i stedet for at udvide `MainWindow` yderligere.

## 0.54.x GUI-moduler

- `qt_search.py`: global projektsøgning og command palette.
- `qt_welcome.py`: startside og seneste projekter i central workspace.
- `qt_feedback.py`: ikke-modal toast-feedback og det fuld-vindue busy-overlay.
- `qt_project_open.py`: projekt-/CAD-åbningsflow, indlæsningsfaser og tydelig busy-feedback.
- `qt_ui.py`: fælles dialogheader og progressive `DisclosureSection`-komponenter.

Nye globale GUI-funktioner skal som udgangspunkt placeres i et lille featuremodul frem for direkte i `MainWindow`.
