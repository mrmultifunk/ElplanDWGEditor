# PL-lederfordeling 0.50.6

## Forbindelses-hover

Hover på en lederende, selve lederkurven, en fysisk terminal eller en Wago-samling udleder den relevante funktions-id (`pe`, `n`, `l`, `switch:x`). Alle ledere og Wago-broer med samme funktion fremhæves, mens øvrige forbindelser tones ned.

## Højreklik på leder

Højreklik vælger lederen og viser en genvejsmenu med:

- **Frigør leder**
- **Flyt til** de terminaler som findes på det valgte lampeudtag
- **Tilføj leder til Wago-samling…**
- **Fjern leder fra Wago-samling**
- **Redigér Wago-samling…**

Alle terminalflytninger går gennem den eksisterende kapacitetskontrol, så Wiser fortsat håndhæver 2 og LK klassisk 4 fysiske terminaltilslutninger.

## Flytbare Wago-muffer

Et venstreklik og træk på selve Wago-blokken flytter den inde i PL-dåsen. Et almindeligt klik uden bevægelse kan stadig bruges som funktionsmål for en valgt leder. Placeringen gemmes som relative koordinater i Wago-samlingens `position`-felt.

Højreklik på Wago giver **Redigér**, **Nulstil Wago-placering** og **Fjern Wago**.

## Projektdata

`pl_box_splices` er fortsat den eksisterende liste fra 0.50.4. 0.50.6 tilføjer kun det valgfrie underfelt `position` på en Wago-samling; ældre projekter kræver ingen konvertering.
