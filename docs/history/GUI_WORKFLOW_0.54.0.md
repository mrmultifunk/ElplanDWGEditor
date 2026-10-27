# GUI Workflow 0.54.0

Version 0.54.0 fortsætter GUI-moderniseringen fra 0.53.0 med punkterne 5-12: hurtig søgning, startside, mere ensartede dialoger, progressive avancerede sektioner, ikke-modale feedbackbeskeder, fælles visuel styling, ensartet tabeladfærd og målrettede performanceforbedringer.

## Søgning og kommandoer

- **Ctrl+F** åbner global projektsøgning efter gruppe/kreds, mærkning, kabel-ID, ekstra kabelmærkning, kabeltype og fritekst.
- **Ctrl+Shift+P** åbner en kommando-palette, som både kan finde objekter og starte almindelige handlinger.
- Et valgt søgeresultat markeres og centreres direkte på tegningen.

## Startside

Programmet åbner nu på en egentlig startside med **Åbn projekt**, **Nyt fra DWG/DXF** og de seneste projekter. Startside kan altid åbnes igen fra Vis-menuen uden at lukke det aktive projekt.

## Progressiv visning og dialoger

Sjældnere felter er flyttet bag tydelige fold-ud sektioner. Symbolinspectorens størrelse/rotation/farve/linjetykkelse ligger under **Udseende og placering**, og kabelinspectorens parallelvisning samt længderapport er tilsvarende foldbare. De store artikel/BOM/PL/kabelkategori-dialoger bruger det fælles dialogfundament.

## Feedback og tabeller

Succeshandlinger som Gem, BOM-opdatering, kabeltilknytning og lokal rutekonvertering bruger små ikke-modale toast-beskeder i stedet for at kræve ekstra klik. Alle tabeller, der bruger den fælles tabelhelper, får flytbare kolonner, dobbelklik på kolonneoverskrift for auto-fit og højreklik på overskriften for **Tilpas kolonner** / **Nulstil bredder**.

## Performance

Hover-BOM-indhold caches pr. symbol og nulstilles kun ved relevante BOM/PL/projektændringer. Det reducerer gentagen normalisering og artikelopslag under almindelig musebevægelse. Eksisterende zoom-coalescing og modelbaserede artikeltabeller fra tidligere versioner bevares.

Der er ingen nye projektfelter i 0.54.0.
