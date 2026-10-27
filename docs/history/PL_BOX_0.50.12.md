# PL-dåse 0.50.12 - tydelig lederfordeling i rapport

## Lederfordeling - fysisk montage

PL-dåserapporten viser nu den komplette kendte lederfordeling som et selvstændigt montageafsnit. Hver række svarer til én fysisk leder og viser:

- indføringsnummer 1-6
- kabel-ID
- fysisk lederfarve
- den endelige montagedestination

Destinationen beskriver om lederen går **direkte til lampeudtaget**, indgår i en **Wago med én bro til udtaget**, ligger i en **ren Wago-sløjfe**, er **løs/ikke fordelt**, eller er tildelt en funktion som ikke findes fysisk på det valgte lampeudtag.

Farverne tegnes direkte i PDF'en. Gul/grøn PE har både grøn og gul markering, og hvid leder får mørk kontrast, så rapporten også er anvendelig på almindelig hvid A4.

## Ét lampested pr. side

Rapporten bruger nu én PL-dåse pr. A4-side. Lederlisten fordeles i to kolonner med op til 21 ledere i hver, hvilket dækker seks kendte 7G-indføringer (42 ledere). Det giver samtidig plads til:

- fysisk orientering af PL-dåsen
- kabelindføring 1-6
- Wago-samlinger
- terminalbelastning
- montagefejl og advarsler

Ukendte kabelopbygninger gættes ikke; de markeres i stedet som **Ukendt lederopbygning - kontroller kabelartikel/datablad**.

Der er ingen ændringer i projektets datamodel.
