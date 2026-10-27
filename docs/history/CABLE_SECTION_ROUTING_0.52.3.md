# Kabelafsnit med individuel ruteføring – 0.52.3

Et fysisk kabel kan nu have **blandet ruteføring**. Kabellets normale `orthogonal`-felt er fortsat standarden for hele kablet, men et enkelt fysisk afsnit mellem to nabotilslutninger kan få sin egen tilstand: **Fri / diagonal** eller **Ortogonal (90°)**.

## Arbejdsgang

Når et eksisterende kabel med mindst to fysiske symboltilslutninger vælges, vises gruppen **Ruteføring pr. afsnit** i Kabelværktøjet. Afsnittene navngives efter de to nabotilslutninger, fx `LP01 → LP02`. Vælg afsnittet, vælg ruteføring og tryk **Anvend på afsnit**.

Som genvej kan brugeren højreklikke direkte på kabelstrækket mellem de to tilslutninger og vælge **Fri / diagonal for dette afsnit** eller **Ortogonal (90°) for dette afsnit**. Kun det klikkede fysiske afsnit konverteres.

Den globale **Ruteføring** i Kabelværktøjets sektion *Tegning og snap* betyder fortsat hele kablet. Hvis den ændres på et eksisterende kabel, konverteres hele ruten og lokale afsnits-overrides nulstilles.

## Projektdata

`CablePlacement` har fået det valgfrie felt `route_section_modes`. Hver post identificerer et fysisk afsnit med de stabile symbol-UID/port-par i begge ender og gemmer `mode = free|orthogonal`. Der gemmes kun en override, når afsnittet afviger fra kabellets globale standard.

Polyline-indeks gemmes ikke i override-feltet. Dermed overlever valget indsættelse/fjernelse af automatiske knæk. Hvis et nyt lampested efterfølgende kobles ind midt i et afsnit med lokal override, deles overriden automatisk i de to nye afsnit.

## Geometri og redigering

Konverteringen remapper `symbol_connections`, så PL-dåser og andre fysiske tilslutninger bliver på de samme symboler. Et frit afsnit kan derfor ligge mellem to ortogonale afsnit på samme kabel. Blå manuelle knækpunkter inde i et lokalt afsnit bruger afsnittets egen ruteføringsregel ved efterfølgende redigering.

Funktionen er Undo/Redo-kompatibel og ændrer ikke kabelkategori, artikelbinding, PL-indføringer eller lederfordeling.
