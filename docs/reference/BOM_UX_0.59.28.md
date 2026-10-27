# BOM UX 0.59.28

## Princip
`build_bom()` er fortsat den eneste autoritative mængdeberegning. `bom_source_breakdown()` og `bom_assembly_usage()` er read-only forklaringslag, der aldrig lægges oven i BOM-totalen.

## Visninger
- **Artikler**: samlet BOM med Kilde / stykliste, dynamisk gruppering og hurtigfiltre.
- **Styklister**: anvendte globale styklister i aktuelt scope, med brugstal, rum, børn og priser.
- **Kilder**: én række pr. konkret bidrag fra stykliste, direkte binding, Wago eller kabel.

## Navigation
En artikel kan åbnes med **Hvor kommer linjen fra?**. En konkret kilde indeholder placement- eller cable-UID og kan derfor vælges/zoomes på plantegningen uden at ændre projektdata.

## Filtre og gruppering
Gruppering: Rum, kategori, gruppe/kreds, stykliste/kilde og fabrikat. Hurtigfiltre: manglende pris, fra stykliste, direkte/manuelt, kabler og advarsler. Den viste totalsum følger rum + hurtigfilter.

## Eksport
Excel/CSV inkluderer `Kilde / stykliste`. Eksport af hoved-BOM følger det aktive hurtigfilter. Rumfanen i Excel bevarer én konkret rumværdi pr. række.
