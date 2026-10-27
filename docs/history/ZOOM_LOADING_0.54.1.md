# Zoom og projektindlæsning – 0.54.1

## Zoom
0.54.0 introducerede en central `QStackedWidget` med startside og tegneflade. Ved projektåbning blev scenen bygget og `fit_scene()` kaldt, mens startsiden stadig var den synlige stack-side. På nogle Windows-layouts kunne `QGraphicsView` derfor have en ikke-endelig eller stale viewport-geometri under `fitInView`, hvilket gav en transform som efterfølgende gjorde zoom ind upålidelig.

0.54.1 bygger scenen uden at fitte, skifter derefter eksplicit til tegnefladen, processerer layout-events og kalder først derefter `fit_scene()`. `zoom_by_factor()` er den fælles transformvej for musehjul og tastatur.

## Indlæsningsfeedback
`BusyOverlay` dækker hovedvinduet under synkron projekt-/CAD-indlæsning. Det viser operationstitel, projektnavn/fase og en indeterminate progressbar. Overlayet vises og paints med `QApplication.processEvents()` før de tunge synkrone faser starter, så brugeren altid får umiddelbar feedback.

Filvælgeren til en manglende DWG/DXF vises uden overlay, hvorefter overlayet genoptages, så den native dialog aldrig skjules.

## Kompatibilitet
Ingen nye projektfelter.
