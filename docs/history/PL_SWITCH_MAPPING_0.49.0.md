# PL-loftdåse – afbryderkanaler og tændingskontrol 0.49.0

## Formål
0.49.0 kobler den eksisterende tilhørslogik (`a`, `b`, `c` ...) sammen med den fysiske lederplan i PL-loftdåsen.

Et tilhørsforhold beskriver **hvad** der skal styres. Lederplanen beskriver **hvordan** den konkrete kabelleder bruges.

## Kabelmærkning
I PL-dialogen vises nu både kabel-ID og kabellets ekstra mærkning, fx:

`K12 · Kombi køkken → PL01`

Kabelspecifikationen vises separat.

## Konkrete afbryderkanaler
Hver fysisk/logisk afbryderkanal identificeres stabilt som:

`<symbol-uid>:<kanalindeks>`

Dermed kan et kombisymbol med flere moduler skelnes som fx:

- Tænding a ← Modul 1 · 1-polet
- Tænding b ← Modul 2 · krone · tænding 1
- Tænding c ← Modul 2 · krone · tænding 2

Den menneskelige relation er stadig `a/b/c`, mens den stabile kanalidentitet peger på den konkrete betjening.

## Kabelvej
Når et kabel fysisk forbinder afbryderen/kombisymbolet direkte med lampestedets PL-dåse, bindes den forventede tænding til det konkrete kabelben.

PL-dialogen viser status for hver forventet tænding:

- ✓ korrekt tildelt
- ⚠ mangler leder
- ⚠ tildelt på forkert kabelben
- ⛔ flere ledere på samme direkte afbryderudgang
- ◇ korrespondance/krydsning kræver manuel terminalkontrol
- • tilhørsforhold findes, men direkte kabelvej til PL-dåsen er ikke fundet

## Én leder = én funktion
En fysisk lederende har kun ét `function`-felt i datamodellen. Hvis en leder ændres fra fx `Tænding a` til `Tænding b`, **erstattes** den gamle funktion; den kan ikke samtidig være begge tændinger.

Flere forskellige ledere må godt være i samme elektriske samling. Det er nødvendigt, hvis fx én tænding skal føres videre fra PL-dåsen til et andet lampested.

## Korrespondance og krydsning
Tilhørsforholdet kan identificere, hvilket lampested en korrespondance/krydsning vedrører, men bogstavet alene fortæller ikke:

- fælles terminal
- korrespondanceledere
- terminalrækkefølge
- forsyningsretning

0.49.0 gætter derfor ikke på disse terminalforløb. De markeres som manuel kontrol. En senere terminalmodel kan bygge videre på samme kanalidentitet.
