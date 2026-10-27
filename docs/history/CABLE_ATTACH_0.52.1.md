# CABLE_ATTACH 0.52.1

## Formål

Det skal være muligt at opdage et glemt lampested efter kabelruten allerede er tegnet og koble lampestedet fysisk på kablet uden at slette eller tegne kabelstrækningen om.

## Brugerflow

1. Vælg et eksisterende lampested.
2. Klik **Tilknyt eksisterende kabel…** under *Kabler ved symbol*, eller højreklik lampestedet og vælg samme handling.
3. Musemarkøren skifter til kryds, og statuslinjen beder brugeren klikke direkte på den ønskede kabelstrækning.
4. Klikket vælger præcis hvilket kabelsegment der skal bruges. Esc annullerer.

## Geometri

- Ligger lampestedets fysiske port ved en fri kabelende, flyttes enden til porten og forbindelsen registreres som start/slut. Det giver ét PL-kabelben.
- Ligger porten midt på ruten, indsættes et nyt fysisk waypoint med `symbol_connection`. Det giver en gennemgående forbindelse og dermed to PL-kabelben.
- Ortogonale kabler får lokale 90°-doglegs; fri routing går direkte via porten.
- Eksisterende forbindelsesindeks forskydes/remappes, så andre symbolankre ikke går tabt.
- Er den valgte rute langt fra lampestedet, kræves brugerbekræftelse før geometrien ændres.

## Data og Undo

Der tilføjes ingen nye projektfelter. Funktionen bruger `CablePlacement.symbol_connections`. Hele kabeltilstanden gemmes før/efter og håndteres af den eksisterende `EditCableCommand`, så Undo/Redo virker som ved øvrig kabelredigering. PL-dåsens indføringsvalg ændres ikke automatisk.

## Arkitektur

Den Qt-specifikke interaktion ligger i `qt_cable_attach.py` som `CableAttachMixin`. Den rene geometri ligger i `core_logic.attach_symbol_to_existing_cable()` og kan testes uden PySide6.
