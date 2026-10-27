# Teknisk gennemgang – Elplan DWG Editor 0.36.1

Denne gennemgang er lavet på 0.36.0 med fokus på stabilitet, dataintegritet, rendering og performance. Sikre fejlrettelser er inkluderet i 0.36.1; større arkitektur-/ydelsesændringer er bevidst ikke blandet ind i vedligeholdelsesudgaven.

## Rettet i 0.36.1

- Sikker håndtering af ikke-gemte ændringer ved Åbn og Afslut.
- Transactional CAD-load: parse før aktiv model/scene skiftes.
- Atomisk gemning af projektfil og brugerindstillinger.
- Strengere validering af projektgeometri og objekt-id'er.
- Ingen globale custom-symbol sideeffekter fra afviste projektfiler.
- Relative CAD/DXF-kildestier virker relativt til projektfilen og bevares korrekt ved Gem som.
- Manglende/relokeret CAD-kilde markeres som en projektændring.
- Symbol- og annotationslag følges nu konsistent i editoren.
- Sletning af symbol rydder dangling kabel-, spot- og a/b/c-referencer; Undo gendanner dem.
- Dirty/Undo-status er bedre synkroniseret med den faktisk gemte projektstate.
- Windows-start springer `pip install` over, når afhængigheder allerede findes.

## Næste tekniske prioriteter

### 1. Kabel-lanes – performance
`cable_visual_paths()` sammenligner i dag kabelsegmenter parvist. Det er robust og simpelt, men vokser omtrent kvadratisk. På denne udviklingsmaskine tog en beregning omtrent:

- 100 separate segmenter: ~3 ms; 100 fuldt overlappende: ~10 ms
- 200 separate: ~13 ms; 200 overlappende: ~39 ms
- 500 separate: ~79 ms; 500 overlappende: ~236 ms

Da beregningen også bruges ved zoom/redraw, bør næste optimering være spatial/linje-bucketing og caching, før projekter med mange hundrede kabelsegmenter bliver normale.

### 2. Windows direkte print har stadig separat renderer
PDF og Preview deler nu samme outputpipeline, men direkte Windows-print er stadig en selvstændig GDI-renderer. Det giver en reel risiko for ny visuel drift i tekststørrelser, Auto/Minimal/Skjult og modulvise a/b/c-labels. Den bør enten dele flere output-primitiver med PDF-rendereren eller refaktoreres til én fælles layoutmodel.

### 3. `legacy_core.py` er blevet for stor
Filen er over 7.000 linjer og indeholder både aktiv geometri/PDF/core-kode og den gamle Tkinter-GUI. Qt-programmet importerer derfor også Tkinter-runtime, selv om den gamle GUI ikke bruges. En 0.37-refaktor bør splitte mindst:

- symbolbibliotek/geometri
- associationer
- kabelgeometri/lane-layout
- CAD I/O
- PDF/print-output
- gammel Tkinter-app (arkiv eller separat modul)

Det vil reducere regressionsrisiko og gøre testning lettere.

### 4. Crash recovery/autosave mangler i Qt-versionen
Den gamle Tkinter-app havde recovery/autosave-kode, men den funktion er ikke koblet ind i den aktive Qt-app. Projektgemning er nu atomisk, men arbejde siden sidste manuelle gemning kan stadig mistes ved et crash/strømsvigt. En diskret recovery-fil med fx 60–120 sekunders interval er en oplagt næste robusthedsforbedring.

### 5. Store CAD-filer indlæses på GUI-tråden
DWG/DXF parsing og sceneopbygning kan gøre vinduet midlertidigt ufølsomt på store plantegninger. På sigt bør parsing/primitiv-ekstraktion flyttes til en worker, eller sceneopbygning batch'es, mens brugerfladen viser reel fremdrift.

## Teststatus

PySide6 er ikke installeret i det Linux-baserede udviklingsmiljø, så de interaktive Qt-tests kan ikke afvikles her. Python-syntaks, projektmodel, associationer, snap-/layoutmatematik, PDF-paritet, kabel-lanes og de nye stabilitetstests køres som ikke-GUI regressionstest før pakning.
