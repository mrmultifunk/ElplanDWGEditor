# Teknisk gennemgang – 0.42.0

Dato: 2026-08-21

## Formål

0.42.0 er en konservativ oprydningsrunde efter den hurtige funktionsudvikling i 0.3x/0.41.x. Målet er at gøre kommende ændringer sikrere og hurtigere uden at omskrive brugerfladen eller projektformatet unødigt.

## Gennemførte ændringer

### 1. Aktiv kerne adskilt fra gammel GUI

Tidligere lå både domænelogik, CAD/PDF-funktioner og den gamle Tkinter-applikation i `legacy_core.py` (~7.950 linjer). Den aktive Qt-version importerede derfor en fil, som også indeholdt tusindvis af linjer ubrugt legacy-GUI.

Nu:

- `core_logic.py` indeholder den GUI-uafhængige kerne.
- `qt_app.py`, `qt_graphics.py`, `project_model.py` og `user_library.py` bruger `core_logic` direkte.
- `legacy_core.py` er et lille kompatibilitetslag.
- `legacy_tk_app.py` indeholder kun den arkiverede Tkinter-frontend og indlæses lazy ved eksplicit legacy-brug.

Det reducerer koblingen mellem gammel og ny frontend og gør det tydeligere, hvilke funktioner der faktisk er en del af den aktive applikation.

### 2. Persistence samlet

Atomisk skrivning fandtes tidligere i både `project_model.py` og `user_library.py` med næsten samme implementation. Den er samlet i `storage_utils.py`, som også tilbyder robust JSON-læsning.

Fordele:

- én implementation af `fsync` + atomisk `os.replace`;
- ens fejlhåndtering for projektdata, priser og globale styklister;
- mindre risiko for, at to persistence-veje udvikler sig forskelligt.

### 3. Artikelindeks samlet

Artikelvælgeren og Standardbiblioteket byggede næsten identiske facet-/søgefelter hver for sig. `article_index.py` bygger nu det fælles in-memory søgeindeks.

Det gør artikeldataflowet enklere og sikrer, at nye søgefelter kan tilføjes ét sted.

### 4. BOM-katalog cachet

`BomManagerDialog._available_catalog()` blev tidligere genberegnet ved flere efterfølgende refresh-funktioner. Det omfattede dictionary-merge, deep-copy, prisoverlay, normalisering og sortering.

0.42.0 cacher:

- det sammensmeltede katalog;
- artikelnummer → artikel-opslag.

Cachen invalideres eksplicit, når projektartikler, standardprisvisning eller øvrige katalogdata ændres.

### 5. Qt-tabelinfrastruktur udskilt

`ArticleTableModel`, kolonnebredde-persistence, auto-fit/nulstilling og dialoggeometri ligger nu i `qt_table_utils.py` i stedet for i toppen af `qt_app.py`.

Det ændrer ikke brugeroplevelsen, men reducerer ansvaret i hoved-GUI-modulet.

### 6. Fejllogning

Ny `app_logging.py` opretter en roterende logfil:

`%APPDATA%\ElplanDWGEditor\logs\elplan.log`

Loggen registrerer uventede top-level Python-fejl. `start_windows.bat` viser placeringen ved runtime-fejl. Det er især nyttigt ved fejl, der kun kan reproduceres på den installerede Windows/PySide6-maskine.

## Aktuel struktur

Aktive hovedmoduler, ekskl. tests/genereret artikeldata:

| Modul | Ca. linjer | Ansvar |
|---|---:|---|
| `qt_app.py` | 5.866 | hovedvindue, dialoger og Qt-workflows |
| `core_logic.py` | 3.605 | domænelogik, CAD, symboler, BOM, eksport |
| `qt_graphics.py` | 1.916 | scene/view, grafikobjekter, snap/interaktion |
| `project_model.py` | 248 | projektmodel, load/save og dirty-state |
| `qt_table_utils.py` | 204 | tabelmodel og persistent tabel-UI |
| `qt_commands.py` | 191 | undo/redo-kommandoer |
| `user_library.py` | 160 | global prisbog/styklister |
| øvrige små moduler | <100 hver | storage, logging, artikelindeks, matematik |

## Resterende teknisk gæld

### Høj prioritet

1. **`MainWindow` er fortsat meget stor** (~3.700 linjer som klasse). Næste sikre refaktor bør udskille projekt-I/O, egenskabspanel og kabel-workflow i mindre controllere/services uden at ændre GUI-layoutet.
2. **`BomManagerDialog` er ~930 linjer.** Katalog/service-logik kan senere flyttes ud af dialogen, så GUI-koden primært håndterer widgets/signaler.
3. **Windows/PySide6 integrationstest.** 11 GUI-tests kan ikke køres i det nuværende Linux-miljø uden PySide6. En fast Windows-smoke-test bør indgå før releases.

### Mellem prioritet

4. `qt_app.py` har fortsat en del lokale `setStyleSheet()`-kald. De bør gradvist erstattes af object names/properties og fælles tema-regler.
5. Nogle små/static tabeller bruger fortsat `QTableWidget`. Det er acceptabelt for få rækker, men Projektbibliotek kan på sigt flyttes til samme modelarkitektur som Standardbiblioteket, hvis kataloget vokser markant.
6. `core_logic.py` og CAD-renderingen bruger flere brede `except Exception` omkring tredjeparts-CAD-entiteter. Mange er bevidste robusthedsgrænser, men de vigtigste bør logges/narrowes, så fejl ikke skjules helt.
7. Den genererede Python-fallback til artikelbiblioteket duplikerer JSON-data. Det er bevidst for pakkede builds, men build-flowet bør på sigt generere fallback automatisk fra JSON som en eksplicit build-step.

## Hvad der bevidst ikke er gjort i 0.42.0

- Ingen stor omskrivning af `MainWindow` i én release.
- Ingen ændringer af symbolgeometri, kabelalgoritmer eller projektfelter.
- Ingen ændringer af BOM-beregningsregler.
- Ingen ændringer af brugerens gemte globale styklister/prisbog.
- Ingen fjernelse af legacy-frontenden; den er isoleret, så kompatibiliteten bevares.

## Teststatus

- `python -m compileall`: bestået.
- `pytest`: **97 passed, 11 skipped** i udviklingsmiljøet.
- De 11 skipped tests kræver Qt/PySide6-runtime.
- Nye 0.42.0-tests dækker core-opdeling, lazy legacy-kompatibilitet, artikelindeks, fælles atomisk JSON-storage og BOM-katalogcache-strukturen.

## Anbefalet næste refaktor

Næste oprydning bør være mindre og målrettet frem for endnu en stor samlet ændring. Første kandidat er at udskille `MainWindow`-ansvar i denne rækkefølge:

1. projekt open/save/recent/autosave;
2. selection/properties-controller;
3. cable-controller;
4. eksport/print-controller.

Efter hver udskillelse bør Windows/PySide6 smoke-test køres, før næste del flyttes.
