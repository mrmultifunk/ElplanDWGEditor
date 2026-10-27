# Hover-overblik og projektstruktur 0.50.14

## Visuelt hover-kort

Hover-popup'en er ændret fra en tekstboks til et kompakt visuelt kort med titel, kontekst, grafisk preview og et separat BOM-område.

### PL-dåse

PL-previewet genbruger den visuelle idé fra kabelindføringsfanen: port 1-6, kabelkappe, gennemføring og kort 3G/5G/7G-ledervifte. Teksten ved siden af viser kabel-ID/mærkning, kabelspecifikation og kabelben. Lederfordelingen vises fortsat ikke.

### Symbol / kabel

Symboler med BOM-binding viser symbolgrafik. Kabler med artikelbinding viser en fysisk kabelminiature med kabeltype.

## Artikler og styklister

Popup'en viser nu de konkrete bindinger på symbolforekomsten: direkte artikler, valgte styklister med navn og de underliggende artikler samt Wago-artikler på PL-dåser.

## Projektstruktur

- `tests/`: alle automatiske tests
- `docs/history/`: versionsnoter og audits
- `docs/reference/`: længerevarende reference-/biblioteksnoter
- `examples/`: demo-projekt, demo-DXF og artikelbibliotektemplates

Kør fortsat programmet fra rodmappen med `start_windows.bat`.
