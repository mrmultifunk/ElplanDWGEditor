# Sikkerhedsnet for opdeling af `core_logic.py`

Baseline er etableret på version 0.59.85 før den første funktionsflytning.
Denne fase ændrer ingen produktionslogik og flytter endnu ingen definitioner.

## Lokal kvalitetskontrol uden GitHub Actions

GitHub Actions forbliver fjernet. Den samlede Windows-kontrol køres lokalt:

```powershell
python -m pip install -r requirements-dev.txt
.\tools\verify_refactor.ps1
```

Den første autoritative Windows-importbaseline optages én gang med:

```powershell
.\tools\verify_refactor.ps1 -CaptureWindowsImportBaseline
```

Scriptet kører pytest, golden-tests, importkontrakter, afhængighedsanalyse og
importtidsmåling. Almindelige pushes starter derfor ingen betalte CI-minutter.

## Testbaseline

- 200 testfiler og 862 indsamlede tests
- 862 bestået i Linux/Python 3.12/PySide6 6.12 med `QT_QPA_PLATFORM=offscreen`
- Tre import-linter-kontrakter består: ingen Qt, ingen win32 og korrekt lagdeling
- Den autoritative Windows-baseline skal fortsat bekræftes med scriptet ovenfor

Ældre tests med forældede antagelser er opdateret til den allerede gældende
adfærd: udvidede Excel-kolonner, semantisk zoom, flerklik-tilknytning, lazy BOM,
modulopdelt tema og 0.59.85's udskudte valgshændelse. Qt-tests lukker nu vinduet
uden en usynlig gem-dialog i offscreen-tilstand.

## Golden-fixture

`tests/fixtures/core_golden_project.elplan.json` indeholder to rum, fem
symboler, parallelle kabelruter, lysrelationer, PL-dåse, Wago, montageprofiler,
artikelbindinger, en stykliste og indkøbsstatus. Den tilhørende artikelbase
ligger i `tests/fixtures/core_golden_articles.json`.

Golden-testene låser følgende adfærd:

- fuldt kanonisk `build_bom`-resultat samt læsbart nøgleuddrag
- `cable_visual_layout`, inklusive parallelle baner og samlingspunkt
- `load_document`, CAD-ekstents og kanonisk hash af `extract_cad_primitives`
- PDF-sideantal, sidestørrelse og udtrukket tekst
- 348 offentlige facade-navne med funktions- og klassesignaturer

## Afhængighedsbaseline

`python tools/analyze_core_dependencies.py` måler aktuelt:

- 8.765 linjer
- 299 topniveau-definitioner
- 655 interne afhængigheder
- 209 definitioner foreløbigt fordelt på målpakkens moduler
- 90 definitioner, som skal klassificeres før de pågældende flytninger
- 0 cykler i den korrigerede, foreløbige modulplan

Analysen fandt to cykler i den oprindelige arbejdsliste. Tre
`cable_route_*`-hjælpere er derfor placeret sammen med kabelsektionerne, og
tværgående PL-kontrol er udskilt som `pl_box.status`. Dermed har den planlagte
modulgraf ingen kendte cykler før første flytning.

## Importtid

Den første Linux-reference var 302 ms. En efterfølgende treprøvers måling gav
median 366 ms. Tallet er kun diagnostisk; Windows-tallet fra brugerens normale
udviklingsmiljø bliver den autoritative reference og håndhæves ikke på tværs af
operativsystemer.

## GitHub-strategi

- Ingen Actions-workflow og ingen automatisk kørsel pr. push
- Lokal fuld kontrol før publicering
- Én samlet sikkerhedsnetændring og derefter højst én PR pr. flyttetrin
- Undermoduler kan være separate commits i samme PR
- Ingen mellem-pushes alene for at afprøve tests

## Fremdrift

### Fase 2.1 – constants og models

Gennemført 17. november 2026 uden ændring af programadfærd:

- øverste fælleskonstanter flyttet til `elplan_core/constants.py`
- de fem dataklasser flyttet til `elplan_core/models.py`
- alle tidligere navne re-eksporteres fortsat fra `core_logic.py`
- `core_logic.py` reduceret fra 8.765 til 8.363 linjer og fra 299 til 294 definitioner
- den resterende modulplan har fortsat 0 kendte cykler

### Fase 2.2 – settings og platform/oda

Gennemført 17. november 2026 uden ændring af programadfærd:

- maskinlokal indlæsning, atomisk lagring og normalisering flyttet til `elplan_core/settings.py`
- ODA File Converter-detektion og opsætning flyttet til `elplan_core/platform/oda.py`
- alle tidligere navne re-eksporteres fortsat fra `core_logic.py`
- artikelbibliotekets direkte indstillingskald og monkeypatch-test peger på det nye modul
- `core_logic.py` reduceret videre til 8.185 linjer og 284 definitioner
- den resterende modulplan har fortsat 0 kendte cykler

### Fase 2.3 – rooms

Gennemført 17. november 2026 uden ændring af programadfærd:

- 13 funktioner til rumgeometri, rumtekster og rumfordelt kabellængde flyttet til `elplan_core/rooms.py`
- 8 uændrede kabeltilslutnings-/sektionshjælpere flyttet til `elplan_core/cables/sections.py` som nødvendig, nedadgående afhængighed
- alle tidligere navne re-eksporteres fortsat fra `core_logic.py`
- lagkontrakten beskriver nu den faktiske retning `rooms → cables → models → constants`
- `core_logic.py` reduceret videre til 7.828 linjer og 263 definitioner
- den resterende modulplan har fortsat 0 kendte cykler
