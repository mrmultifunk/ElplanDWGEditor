# Elplan DWG Editor

Windows-program til planlægning og dokumentation af elektriske installationer direkte på DWG- og DXF-plantegninger.

**Aktuel version:** `0.59.79`
**Platform:** Windows 10/11 · Python 3.11 eller 3.12

## Hvad kan programmet?

- Visning af DWG/DXF med lagstyring, zoom, dæmpning og printvenligt output.
- Placering og redigering af el-symboler med vægsnap, hjælpelinjer og relationer.
- Fysiske kabelruter med knækpunkter, kabeltyper, længdeberegning og rumfordeling.
- Konfiguration af PL-loftdåser, lampeudtag, ledere, WAGO-samlinger og gennemsløjfninger.
- Read-only import af fysiske kabelindføringer, noter og feltfotos fra `pl-daase`-PWA'en.
- Rumtegning, rumnavne, rumfiltrering og BOM pr. rum.
- Fælles artikeldatabase, genbrugelige styklister og eksplicit artikeltilknytning.
- Priser inkl. eller ekskl. moms, forhandlersammenligning og pakke-/stykpriser.
- BOM med søgning, kategorifilter, gruppering, sporbarhed og mangelliste.
- Eksport til Excel, CSV, PDF, DXF/DWG samt direkte udskrift med preview.

## Installation og start

1. Installer [Python](https://www.python.org/downloads/) 3.11 eller 3.12.
2. Hent eller klon dette repository.
3. Kør `start_windows.bat`.

Første start opretter automatisk `.venv` og installerer de nødvendige Python-pakker. Efterfølgende starter programmet uden at kontakte nettet, når afhængighederne allerede er installeret.

```powershell
git clone https://github.com/mrmultifunk/ElplanDWGEditor.git
cd ElplanDWGEditor
.\start_windows.bat
```

DXF kan åbnes direkte. Import af DWG kræver [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter).

## Artikler, priser og styklister

Åbn **Værktøjer → Artikler / BOM…** eller brug `Ctrl+B`.

- **Artikeldatabase** indeholder programmets basisartikler og brugerens egne/importerede artikler.
- **Styklister** er genbrugelige montager med faste og valgfrie komponenter.
- **Tilknytning** forbinder en artikel eller stykliste med en konkret symboldel eller et kabel.
- **BOM** summerer de eksplicitte tilknytninger og viser manglende artikelvalg.
- **Kontrol** finder blandt andet manglende artikler, forældede priser og ufuldstændige pakningsdata.

BOM kan filtreres efter rum og artikeltype, eksempelvis dåser, rammer, afdækninger, indsatser, tangenter, kabler og samlemuffer. Det aktive filter følger med i eksporten.

## Data og lagring

Programkode og brugerdata holdes adskilt:

| Data | Placering |
| --- | --- |
| Kildekode | Dette Git-repository |
| Projekter | Valgt projektmappe eller fælles projektlager |
| Artikler, priser og styklister | Lokal Elplan-mappe eller separat OneDrive-mappe |
| Indstillinger, cache og logs | Lokal brugerprofil på pc'en |

Den globale artikeldatabase er uafhængig af projekterne. Dens placering vælges under **Fil → Lager og synkronisering → Artikeldata…**. Projektfiler, artikeldata og lokale indstillinger er udelukket fra Git via `.gitignore`.

## Udvikling

Installer udviklingsafhængighederne og kør tests fra projektroden:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Nye funktioner bør som udgangspunkt reducere klik, gøre redigering mere forudsigelig eller forbedre overblikket uden at gøre brugerfladen unødigt CAD-tung. Se [CONTRIBUTING.md](CONTRIBUTING.md) for kode- og testprincipper.

## Dokumentation

- [CHANGELOG.md](CHANGELOG.md) – versionshistorik og ændringer
- [MIGRATION.md](MIGRATION.md) – migration og kompatibilitet mellem versioner
- [CONTRIBUTING.md](CONTRIBUTING.md) – udviklingsprincipper og modulstruktur
- [Artikelbibliotek](docs/reference/ARTICLE_LIBRARY.md) – artikeldata og importformat
- [Projektlager](docs/reference/PROJECT_STORAGE_0.59.47.md) – placering og flytning af projekter
- [Cloud-sikker redigering](docs/reference/CLOUD_SAFE_EDITING_0.59.48.md) – samarbejde og revisionsbackup
- [Performance](docs/reference/PERFORMANCE_0.59.59.md) – aktuelle optimeringsprincipper

Detaljer om hver udgave hører hjemme i [CHANGELOG.md](CHANGELOG.md), ikke på projektets forside.
