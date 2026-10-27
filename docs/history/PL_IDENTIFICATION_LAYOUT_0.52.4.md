# PL-identifikation og skærmtilpasning — 0.52.4

## Formål

Et PL-lampested skal kunne identificeres entydigt både på skærmen og på den udskrevne montagerapport. `gruppe/kreds` og brugerens `mærkning` vises derfor side om side, når begge findes.

## Tændleder-overblik

Det aktuelle lampested vises i Tændleder-overblikket som fx `G11 · T.V. BAD2`. Den kabelomspændende tændlederanalyse bruger samme identifikation, når den viser hvor en lederfarve allerede er anvendt. Dubletter undgås automatisk, hvis gruppe og mærkning er ens.

## PL-dåserapport

Hvert PL-montageark viser nu særskilt `Gruppe/kreds:` og `Mærkning:` i overskriften, samtidig med den kompakte samlede identifikation i titlen.

## Skærmtilpasning

Lederfordelingens indhold ligger i et `QScrollArea`, mens dialogens knapbjælke ligger uden for scrollområdet. Dermed kan en stor lederplan/Wago-konfiguration rulles uden at gemme OK, Annuller og Anvend under Windows-proceslinjen. Dialogens startstørrelse beregnes desuden via `_resize_dialog()` ud fra skærmens `availableGeometry()`.

Der er ingen ændringer i projektformatet.
