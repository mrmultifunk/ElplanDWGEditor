# Dark mode 0.51.0

## Formål

Dark mode er implementeret som et **arbejds-/skærmtema**, ikke som en ny tegningsstandard. Målet er at reducere lysbelastningen ved længere tids arbejde og samtidig bevare den tekniske betydning af farver, linjetyper, lederfarver og printoutput.

## Udseendetilstande

Under **Vis → Udseende** findes tre gensidigt udelukkende tilstande:

- **Lys** – klassisk lys brugerflade og hvid tegneflade.
- **Mørk** – mørk brugerflade; tegnefladen kan være mørk eller hvid via **Mørk tegneflade**.
- **Følg Windows** – den aktive lys/mørk-tilstand bestemmes af Qt/Windows.

**Ctrl+Alt+D** er en hurtig skiftefunktion mellem lys og mørk. Systemtilstanden bruger Qt's `colorScheme` når den findes, og Windows' `AppsUseLightTheme` som fallback. Hvis platformen udsender et temasignal, opdateres det åbne program uden genstart.

## Lokal indstilling – ikke projektdata

`appearance_mode` og `dark_canvas` gemmes i appens maskinlokale indstillinger. De er bevidst føjet til listen over ikke-portable indstillinger. Et projekt ser derfor ikke pludselig mørkt ud, blot fordi det er oprettet på en anden computer, og `.elplancore` flytter ikke brugerens personlige tema.

Der er ingen nye felter i projektmodellen og ingen projektmigration i 0.51.0.

## Global Qt-tematisering

Den centrale palette og stylesheet dækker de almindelige Qt-komponenter i programmet: hovedvindue, menu/menu-bar, værktøjslinje, docks, tabulatorer, gruppebokse, labels, tekstfelter, combobox/spinbox, check/radio, knapper, lister, tabeller/header, sliders, progress bars, splittere, statusbar, scrollbars, tooltips, kabelassistent og hover/BOM-kort.

Standardikoner og symbolpalette regenereres efter et live temaskift, så ikoner ikke beholder en kontrast, der hørte til det forrige tema.

## CAD-tegnefladen

En mørk CAD-tegneflade giver et særligt problem: en stor del af eksisterende DWG- og eldata er tegnet med sort eller meget mørke farver. At ændre disse data ville være forkert. I stedet anvendes en **display-only kontrastfunktion** under paint:

- meget mørke DWG-linjer vises lysere,
- meget mørke symboler får skærmkontrast/underlay,
- mørke kabler og fritekster får en synlig skærmvariant,
- snapmarkører, kabelpunkter, hjælpelinjer og annotationschips har mørktilpassede kontraster.

De originale QColor-/projektværdier skrives ikke tilbage. PDF/DXF/print bruger derfor fortsat de tekniske farver, der er valgt i projektet.

## PL-dåsekonfigurator

**Kabelindføringer** og **Lederfordeling** er ikke blot lagt ind i en mørk container; deres egne QPainter-grafikker har mørke paletter. Følgende semantik bevares:

- PE er fortsat gul/grøn, N blå, L/brun og tændledere følger deres faktiske lederfarve,
- hvid og sort leder får kontrastkant/halo, så begge kan ses,
- Wago beholder orange identitet og særskilt valgt/hover-status,
- terminaler bevarer PE/N/L- og statusfarver,
- kabelkategoriers brugerdefinerede farve og kontur bevares og kontrastforbedres kun på skærmen, når det er nødvendigt.

Dette er vigtigt, fordi farverne i PL-visningen er information og ikke pynt.

## Hover-kort og dialoger

De grafiske PL-, symbol- og kabelpreviews i hover-kort bruger palette-/temaafhængige flader og tekst. BOM/stykliste-information følger samme mørke kortdesign. Lokale gamle hardcodede hvide popup-styles er fjernet, så popup'en skifter sammen med resten af programmet.

## Print, PDF og rapport

Dark mode må ikke blive en skjult outputindstilling. Derfor:

- print-previewets **omgivelser** kan være mørke,
- den simulerede papirside er altid hvid,
- PDF- og Windows-printfunktionerne modtager ingen dark-mode-parametre,
- PL-dåserapporten fortsætter med hvidt papir og sine faste rapportfarver.

Det gør det muligt at arbejde i et mørkt miljø uden at ændre kundens/installerens dokumentation.

## Regressionstest

0.51.0 har regressionstests for versions- og indstillingsnormalisering, ikke-portable temaindstillinger, menu-/genvejskontrakten, mørk CAD-skærmkontrast samt invarianten om, at eksport/print er papirbaseret og uafhængig af temaet.
