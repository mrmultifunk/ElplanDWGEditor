# PL-loftdåse – lederfordeling 0.48.0

0.48.0 udvider PL-loftdåsen fra 0.47.0 med en lederplan pr. fysisk kabelben.

## Understøttede kabelopbygninger

- **3G**: gul/grøn PE, blå, brun.
- **5G**: gul/grøn PE, blå, brun, sort, grå.
- **7G**: gul/grøn PE + seks nummererede sorte ledere (1–6).

7G vises bevidst som nummererede sorte ledere frem for seks opdigtede farver. Det følger almindelig HD 308/producentpraksis for installations-/multilederkabler med syv ledere.

## Brugerflow

Dobbeltklik på et lampested og vælg fanen **Lederfordeling**. Hvert kabelben fra fanen Kabelindføringer foldes ud til sine fysiske ledere. Et gennemgående 5G-kabel giver derfor fem ledere på Side A og fem på Side B.

For hver leder vælges **Funktion / samling**:

- PE → lampested PE
- N → lampested N
- Fast fase L
- Tænding a/b/c/... → lampested L(a/b/c/...)
- Reserve
- Ikke tilsluttet

Tændingsvalgene følger lampestedets eksisterende lystilhørsforhold. Hvis lampestedet ikke har et bogstav endnu, vises en generisk **Tænding → lampested L**.

Ledere med samme funktion regnes som én planlagt samling i PL-dåsen og vises grafisk på samme samlingsskinne. Programmet laver ikke automatisk elektriske designvalg for aktive ledere. Gul/grøn PE og blå N foreslås som de entydige standardfunktioner; øvrige ledere skal vælges af brugeren.

## Grafisk visning

Fanen viser PL-dåsen med de seks fysiske kabelindføringer. Hvert kabelben viser sine lederfarver/numre, og fordelte ledere føres grafisk ind til deres valgte samling. Tændingssamlinger viser samtidig lampestedets L-terminal.

## Projektdata

Lederplanen gemmes som `pl_box_wiring` på det konkrete lampested og refererer til kabel-UID, kabelben og leder-id. Døde kabelreferencer og ledere der ikke længere findes efter ændring af kabelspecifikation, fjernes ved validering. Kopierede lampesteder arver ikke den fysiske lederplan.

Ældre projekter kræver ingen migration. De får først en gemt lederplan, når brugeren anvender PL-konfiguratoren.
