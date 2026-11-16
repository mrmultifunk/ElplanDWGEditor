# Hurtig og sikker lystilknytning i 0.59.84

En lystilknytning er nu en tydelig redigeringssession med to mulige afslutninger:

- **Gem tilknytning** beholder alle til- og fravalg som én fortrydelig ændring.
- **Annuller** eller `Esc` gendanner relationerne fra før sessionen blev startet.

Gem er tilgængelig både i arbejdslinjen over tegningen og i `Forbind` under `Lystilhørsforhold`. `Enter` og `Ctrl+Enter` udfører samme handling i hele hovedvinduet, også når fokus ligger i højrepanelet.

## Arbejdsgang

1. Vælg afbryderen og den fysiske betjening.
2. Vælg **Tilføj / fjern lys…**.
3. Klik de fremhævede lampesteder, lamper eller frie spots til eller fra.
4. Vælg **Gem tilknytning**, eller tryk `Enter`/`Ctrl+Enter`.

Når arbejdsgangen startes fra et lys, vælges først den orange afbryder. Gem bliver først aktiv, når programmet kender den konkrete afbryder og betjening.

## Respons

Mens sessionen er aktiv, bruges symbolerne kun som klikmål. Et klik skifter derfor ikke udvalg, åbner ikke et nyt Egenskaber-panel og kan ikke begynde et træk. Programmet opdaterer kun mærkningen på den valgte afbryder, det ændrede lys og spots, der arver lampestedets relation. Den samlede panel- og metadataopdatering udføres én gang ved afslutning.

Projekt- og eksportformatet er ikke ændret.
