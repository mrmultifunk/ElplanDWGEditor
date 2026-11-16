# Responsivt symbolvalg i 0.59.85

Symbolvalg er opdelt i en hurtig interaktionsfase og en efterfølgende informationsfase.

## Klik og flytning

Når museknappen trykkes ned, håndterer tegnefladen kun markering og forberedelse af et eventuelt træk. Opbygning af Egenskaber venter til museknappen slippes. Hvis markøren flyttes, sættes panelopdateringen på pause, indtil flytningen er afsluttet.

Flere `selectionChanged`-signaler fra samme handling samles. Det gælder blandt andet Qt's ryd/markér-sekvens, multivalg og programmatisk genvalg.

## Indekser og dovne data

- Kabler er indekseret efter symbol-id, så et træk kun finder kabler, der faktisk er fysisk tilsluttet symbolet.
- Kabelartikelkatalog og prisbog indlæses ikke ved almindeligt symbolvalg.
- Symbol-BOM beregnes først, når arbejdssporet **Indkøb** vises.
- Uændret visuel fokus genbruger den eksisterende opacitet i stedet for at opdatere hele tegningen.

Optimeringerne ændrer ikke projektdata, fortrydelse, kabelankre, BOM-mængder eller eksport.
