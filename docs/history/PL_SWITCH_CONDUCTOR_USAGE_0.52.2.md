# PL tændleder-overblik — 0.52.2

## Formål

Et flerlederkabel kan passere mange lampesteder. Brugeren skal kunne se, hvilke lederfarver der allerede er anvendt som tændledninger på samme fysiske kabel, uden at åbne hvert tidligere lampested.

## Beregning

`core_logic.cable_switch_conductor_usage()` finder alle PL-punkter, der er fysisk forbundet til det valgte `CablePlacement`, reconciler deres eksisterende `pl_box_wiring` mod de aktuelle kabelben og grupperer funktionerne efter `core_id`. Den aktuelle, endnu ikke gemte PL-dialogs lederplan kan gives som override, så overblikket opdateres live under redigering.

Status pr. farve er: `available`, `used_switch`, `assigned_other`, `typical_supply` eller `conflict`. En konflikt betyder, at samme lederfarve på samme kabel er registreret med mere end én `switch:*`-funktion.

## Anbefaling

Ved kendte 7G-profiler prioriteres ledige tændledere i rækkefølgen sort, grå, rød, hvid. PE, blå og brun er markeret som henholdsvis beskyttelsesleder, typisk N og typisk fast L og indgår ikke i den automatiske anbefaling. Det er kun planlægningshjælp og ikke en normkontrol.

## GUI

`qt_pl_usage.py` indeholder det visuelle statuskort samt mixin-logikken til PL-dialogen. Flere kabler kan vælges i kortet, og valg af en fysisk leder synkroniserer automatisk det viste kabel. Forsøg på at bruge en farve til en anden tænding end den, som allerede findes på samme kabel, giver en bekræftelsesadvarsel.

Ingen nye projektfelter er indført.
