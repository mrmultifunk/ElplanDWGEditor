# GUI-audit – Elplan DWG Editor 0.42.2

## Formål

0.42.2 er en konservativ visuel gennemgang af hele den aktive PySide6/Qt-brugerflade. Målet er at få samme type kontrol til at se og opføre sig ens overalt, gøre primære handlinger lettere at finde og reducere lokale stylesheet-lapper. Projektdata, tegnegeometri og beregningslogik er ikke ændret som del af auditten.

## Gennemgåede områder

- Hovedvindue, menulinje, primær værktøjslinje og statusbar.
- Dock-panelerne Symboler, Lag, Egenskaber og Kabelværktøj.
- Symbolkonfigurator og live-preview.
- Udskriftsforhåndsvisning.
- Artikelvælger, artikelredigering og prisdialog.
- Artikler/BOM med fanerne Tilknytning, Styklister, Kabeltyper, Standardbibliotek, Projektbibliotek og BOM.
- Stykliste-editor.
- Kabellængde-/skaladialog og kabellængderapport.
- Dialogerne for fritekst, mærkning, spot-række og spot-rektangel.
- Tabeller, lister, completer-/dropdown-lister, scrollbars, sliders, checkboxes, linjefelter, spinboxes og comboboxes.
- Hover-, focus-, pressed-, disabled- og read-only states i det fælles lyse tema.

## Centrale ændringer

### Fælles formularsystem

Alle formularer bruger samme feltvækst, label-alignment og afstande. Det fjerner variationer mellem små hjælpevinduer og store BOM-/artikel-dialoger.

### Knaphierarki

Knapper er opdelt i tre visuelle roller:

- Primær: den vigtigste handling i det aktuelle område, fx Gem, Tilføj, Tilknyt eller Anvend.
- Sekundær/quiet: hjælpehandlinger som filtre, kolonneværktøjer, rapport, links og nulstilling.
- Destruktiv: Slet, Fjern, Frakobl, Ryd tilknytning og annullering af aktivt arbejde.

Programmets egne QDialogButtonBox-dialoger får samme hierarki automatisk.

### Talbokse og dropdowns

Programmets QSpinBox/QDoubleSpinBox tegner selv de synlige op-/ned-chevrons efter Qt har malet kontrollen. QSS-stylingen af pilzonerne er nu afgrænset med en widget-property, så Qt-oprettede standarddialoger ikke får tomme pilzoner.

Programmets QComboBox bruger samme princip til dropdown-chevron. Kun programmets egne comboboxe undertrykker den native pil; Qt-oprettede standarddialoger beholder den native rendering.

### Dialoger og panelsammensætning

Store dialoger får en skærmbegrænset startstørrelse. Artikelredigeringen er opdelt i meningsfulde grupper, filterområder ligger i egentlige gruppebokse, og previewområder har en tydelig afgrænset flade. Kabelværktøjet undgår dobbelt titel og har klarere status, længdeestimat og handlingsgrupper.

### Tabeller og lister

Fælles tabelkonfiguration giver ens rækkehøjde, alternating rows, skjult lodret header, brugerstyrede kolonnebredder og ens headeralignment. Modelbaserede artikeltabeller fra 0.41.5 er bevaret.

## Test og begrænsning

Den statiske/regressionsmæssige testsuite dækker GUI-struktur og relevante kodeveje. Det aktuelle buildmiljø har ikke PySide6 installeret, så egentlige Qt-runtime-/pixeltests kan ikke køres her. Derfor bør 0.42.2 stadig visuelt kontrolleres på den Windows-maskine og DPI-skalering, programmet normalt bruges på.

OS-native fil-, farve- og printerdialoger er bevidst ikke tvunget ind i et specialtegnet tema; de følger platformens normale udseende.
