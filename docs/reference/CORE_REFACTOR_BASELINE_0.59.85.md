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
`cable_route_*`-hjælpere er derfor placeret sammen med kabelsektionerne, mens
PL-normalisering ligger under leder- og montagekontrollen. Dermed har den
planlagte modulgraf ingen kendte cykler før første flytning.

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

### Fase 2.4 – cables

Gennemført 17. november 2026 uden ændring af programadfærd:

- 53 uændrede kabeldefinitioner flyttet ud af `core_logic.py`
- kabeldomænet opdelt i `categories`, `connections`, `geometry`, `sections` og `lengths`
- `normalize_hex_color` flyttet til det lille fællesmodul `elplan_core/appearance.py`, så kabelkategorier ikke afhænger af facaden
- basale tilslutninger ligger under både geometri og sektioner, mens længder ligger over dem; opdelingen fjerner den ellers skjulte cykel mellem geometri og sektionsberegning
- alle tidligere navne re-eksporteres fortsat fra `core_logic.py`
- 61 flyttede eller omplacerede definitioner er verificeret AST-identiske med udgangspunktet
- 875 tests og alle tre importkontrakter består
- `core_logic.py` reduceret videre til 6.974 linjer og 210 definitioner
- den resterende modulplan har fortsat 0 kendte cykler
- syv Linux-målinger gav en median på 335 ms mod 319 ms efter fase 2.3; Windows-målingen forbliver den autoritative reference

### Fase 2.5 – symbols

Gennemført 17. november 2026 uden ændring af programadfærd:

- symbolregister og kombisymboler flyttet til `elplan_core/symbols/registry.py`
- al ren symbolvektorgeometri, porte, montagepunkter og vægsnap flyttet til `elplan_core/symbols/geometry.py`
- symbolmærkning og clipboard-serialisering flyttet til `elplan_core/symbols/clipboard.py`
- fem rene relationsnormaliseringer og to PL-dåsenormaliseringer flyttet som nødvendige, nedadgående forudsætninger; den resterende logik bliver fortsat flyttet i fase 2.6 og 2.7
- 43 funktioner og 9 modulkonstanter er verificeret AST-identiske med udgangspunktet
- alle tidligere navne re-eksporteres fortsat fra `core_logic.py`
- 878 tests og alle tre importkontrakter består
- `core_logic.py` reduceret videre til 6.075 linjer og 167 definitioner
- den resterende modulplan har fortsat 0 kendte cykler
- syv Linux-målinger gav en median på 303 ms, svarende til den oprindelige Linux-reference

### Fase 2.6 – associations

Gennemført 17. november 2026 uden ændring af programadfærd:

- 25 funktioner til afbryderkanaler, lysudgange, bogstaver, visning og fælles lystilknytning flyttet til `elplan_core/associations.py`
- de fem normaliseringsfunktioner, som blev flyttet som clipboard-forudsætning i fase 2.5, ligger nu sammen med resten af relationsdomænet
- alle 30 funktioner i modulet er verificeret AST-identiske med udgangspunktet
- modulet afhænger kun nedad mod symbolregister/geometri, kabelrotation, modeller og konstanter
- alle tidligere navne re-eksporteres fortsat fra `core_logic.py`
- 881 tests og alle tre importkontrakter består
- `core_logic.py` reduceret videre til 5.741 linjer og 142 definitioner
- den resterende modulplan har fortsat 0 kendte cykler
- elleve Linux-målinger gav en median på 290 ms, uden importtidsregression

### Fase 2.7 – PL-dåser og montagerapport

Gennemført 17. november 2026 uden ændring af programadfærd:

- PL-dåsens normalisering, indføringer og stabile referencer flyttet til `elplan_core/pl_box/model.py`
- kabelben, lederprofiler, tændingskrav og forslag flyttet til `elplan_core/pl_box/wiring.py`
- Wago-samlinger, terminalbelastning og montagekontrol flyttet til `elplan_core/pl_box/wago.py`
- den komplette ReportLab-baserede montagerapport flyttet til `elplan_core/export/pl_report.py`
- 55 funktioner og 7 modulkonstanter er verificeret AST-identiske med udgangspunktet
- alle tidligere navne re-eksporteres fortsat fra `core_logic.py`
- tre ældre kildekodetests peger nu på de respektive nye moduler; Qt-koden er uændret
- 883 tests og alle tre importkontrakter består
- `core_logic.py` reduceret videre til 3.954 linjer og 87 definitioner
- alle fire nye moduler er under 800 linjer, og den resterende modulplan har 0 kendte cykler
- elleve Linux-målinger gav en median på 286 ms, uden importtidsregression

### Fase 2.8 – artikel- og BOM-logik

- Artikelkatalog, pakningsberegning og kabelartikelbindinger ligger i `bom/articles.py`; montage og indkøbssegmentering ligger i `bom/procurement.py`.
- Styklistemodellen ligger i `bom/assemblies.py`, den delte rumafgrænsning i `bom/scope.py` og BOM-beregning, sporbarhed og projektkontrol i `bom/build.py`.
- 47 funktioner er flyttet. Kun stien til det eksisterende JSON-katalog er tilpasset; der er stadig én cache og en Python-fallback til builds uden JSON-filen.
- `core_logic.py` er reduceret fra 3.954 til 2.412 linjer og fra 87 til 40 definitioner. De gamle navne re-eksporteres stadig, og API-manifestet er uændret.
- 145 målrettede tests blev kørt direkte via Python, inklusive alle referenceoutput og nye tests for katalogets JSON-sti, cache og fallback. Der er ingen kendte modulcykler.
- Importtidsmedian på Linux: 266 ms mod 272 ms for fase 2.7 (11 målinger pr. version i samme miljø).
- Fuld pytest-suite, `lint-imports` og Windows-pakning er ikke kørt i dette miljø. Den fulde lokale regression afventer `tools/verify_refactor.ps1`.

### Fase 2.9 – CAD, DXF og PDF

- CAD-indlæsning, tegneenheder og vektorudtræk ligger i `elplan_core/cad_io.py`.
- DXF-skrivning, visningsudsnit/papirlayout, visuelle outputprofiler og PDF-eksport ligger i hver sit modul under `elplan_core/export/`.
- Kabelmærkning og visuelle kabelbaner ligger i `elplan_core/cables/visual.py`, så eksporten ikke behøver importere facaden.
- 35 funktioner og én konstant er flyttet uændret og re-eksporteret fra `core_logic.py`. Facaden er nu 803 linjer med fem funktionsdefinitioner. Windows-print er stadig i facaden til fase 2.10.
- 178 målrettede tests blev kørt direkte via Python, inklusive golden-tests, API-manifest og ny DXF-genindlæsning. DWG-kaldet til ODA er testet med en erstatning; ODA-konverteren er ikke kørt. Statisk importkontrol fandt ingen cykler eller lagbrud.
- Importtidsmedian på Linux: 275 ms mod 267 ms for fase 2.8 (11 målinger pr. version i samme miljø).
- Fuld pytest-suite og `lint-imports` afventer fortsat et miljø med projektets udviklingsafhængigheder.

### Fase 2.10 – Windows-print

- `print_vector_windows` er flyttet uændret til `elplan_core/platform/printing.py` og re-eksporteres fortsat fra `core_logic.py`.
- Importkontrakten undtager kun printmodulets fem direkte pywin32-afhængigheder. Arkitekturtesten kontrollerer, at importerne udelukkende ligger inde i Windows-printfunktionen, og at facaden kan indlæses med Qt og pywin32 blokeret.
- 183 målrettede tests blev kørt direkte via Python. En simuleret Windows-printer verificerer A3/landskab, mærkning og korrekt afslutning af printjobbet. En fysisk Windows-printer er ikke testet.
- Importtidsmedian på Linux: 276 ms mod 275 ms for fase 2.9 (11 målinger pr. version i samme miljø).
- `core_logic.py` er nu 433 linjer med fire hjælpefunktioner. Flyttefasen er afsluttet; de resterende hjælpere og facadeimporter hører til oprydningen.
- Fuld pytest-suite og `lint-imports` afventer fortsat projektets udviklingsafhængigheder.
