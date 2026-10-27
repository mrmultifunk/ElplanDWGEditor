# Vedligeholdelses-/arkitekturpas 0.52.0

0.52.0 er bevidst en vedligeholdelsesversion. Målet er at gøre den voksende Qt-applikation lettere at ændre uden at ændre brugerens projektdata eller den etablerede arbejdsgang.

## Modulopdeling

`qt_app.py` var før dette pas ca. 11.200 linjer og rummede både hovedvindue, theme engine, hover-tegning og domænelogik. Første sikre udtræk er nu gennemført:

- `qt_theme.py` ejer light/dark/system-detektion, applikationsstylesheet, palette og Fusion-proxy style.
- `qt_hover.py` ejer hover-kortets grafiske preview og popup-container.
- `qt_app.py` er reduceret til ca. 10.700 linjer uden ændring af de offentlige workflows.

Der er ikke forsøgt en risikabel total omskrivning. De næste naturlige kandidater til senere udtræk er PL-konfiguratoren og BOM/artikel-dialogerne.

## Oprydning

- Dobbeltdefinitionen af `MainWindow._cable_symbol_caption()` er fjernet.
- En arkitekturtest kontrollerer nu, at `MainWindow` ikke får dublerede metode-navne igen.
- Tema- og hover-source-tests følger de nye moduler i stedet for at kræve, at alt ligger i `qt_app.py`.

## Performance

- Zoom-afhængige rebuilds af parallelle kabelbaner, annotationer og tilhørsforholds-overlay coalesces nu med en 32 ms single-shot timer. Zoomprocent/status opdateres stadig øjeblikkeligt, men et hurtigt hjul-/trackpad-burst udløser ikke længere et tungt rebuild for hvert enkelt signal.
- Den globale artikeldatabase caches ud fra brugerfilens sti, ændringstid og størrelse. Hover-kort, BOM og artikelvælger undgår dermed gentagen JSON-læsning og normalisering. Callers modtager fortsat en defensiv kopi, og cache opdateres ved gemning eller ekstern filændring.

## Kabelruteføring

Fejlen hvor et eksisterende kabel kunne få flaget ændret fra Ortogonal til Fri/diagonal uden at selve geometrien ændrede sig er rettet. Ved **Anvend ændringer** konverteres den fysiske centerlinje nu også. Symboltilslutninger remappes til de nye punktindekser, og Undo gendanner den tidligere geometri.

Ældre ortogonale projekter gemte ikke eksplicit hvilke 90°-hjørner der var automatisk genereret. Konverteringen bruger derfor en konservativ rekonstruktion: fysiske symboltilslutninger og endepunkter bevares altid, mens typiske auto-hjørner mellem bruger-waypoints fjernes.

## Projektformat

Ingen nye obligatoriske projektfelter er introduceret i 0.52.0. Eksisterende 0.51.x-projekter kan åbnes uden datamigration ud over normal versionsopdatering ved gemning.
