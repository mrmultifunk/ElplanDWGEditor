# PL kabelindføringer 0.50.10

## Mål

Skabe en naturlig grafisk overgang fra fanen **Kabelindføringer** til **Lederfordeling** ved at vise kabellets faktiske generelle lederopbygning allerede dér, hvor yderkappen ender inde i PL-dåsen.

## Ændringer

- Et kendt **3G**, **5G** eller **7G** kabel fortsætter nu fra gennemføringen til en kort synlig afisoleringszone inde i PL-dåsen.
- Yderkappen afsluttes med en tydelig skærekant.
- Lederne faner derefter blødt ud som separate farvede ledere.
- 3G: gul/grøn, blå, brun.
- 5G: gul/grøn, blå, brun, sort, grå.
- 7G: gul/grøn, blå, brun, sort, grå, rød, hvid.
- PE får gul stipling oven på grøn, og alle ledere får en diskret kontrastkant, så også hvid og grå er synlige på den lyse dåse.
- Den valgte indføring får en svag halo omkring lederviften, uden at farverne ændres.
- Ukendte kabelopbygninger returnerer fortsat ingen previewledere; programmet gætter ikke.

## Datamodel

Ingen ændringer. Previewet bruger `core.cable_conductor_preset()` og er kun en grafisk udvidelse af `PLBoxDiagramWidget`.
