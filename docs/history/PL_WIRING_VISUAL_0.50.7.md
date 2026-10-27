# PL-lederfordeling 0.50.7

## Planlagt og eksklusiv Wago

En Wago-samling kan nu oprettes **før lederne er fordelt**. **Ny Wago…** viser de fysiske/logiske terminalfunktioner på det valgte lampeudtag, også når der endnu ikke er ledere på funktionen. En tom Wago bevares som en planlagt samling, kan få artikelnummer og kan flyttes i PL-dåsen.

Når en Wago findes for en funktion, er den **eksklusiv**: alle kabelledere der senere tildeles funktionen føres ind i Wago-muffen. Der tegnes og beregnes altid kun **én bro fra Wago til lampeudtaget**. Direkte kabelledere og Wago-bro kan derfor ikke længere forekomme parallelt på samme terminal.

Hvis en ny leder gør den valgte Wago-artikel for lille, foreslår dialogen at skifte til den mindste passende indbyggede WAGO 221-variant.

## Automatisk grafisk routing

Lange lederforløb får nu automatiske routing-spor. Top- og bundindføringer behandles i separate zoner, og sporene sorteres efter slutpunktets højde. Det giver mere parallel føring af PE/N/L/tændinger og reducerer antallet af kryds. Sporene tegnes fortsat med bløde Bézier-bøjninger, mens korte forbindelser og manuelt flyttede Wago-muffer bruger direkte bløde kurver.

## Montagekontrol

Under Wago-rækken vises en kompakt **Montagekontrol** med:

- fysisk belastning pr. lampeudtagsterminal, fx `N 1/2`
- markering af terminaler der fødes via Wago
- antal kabelledere i Wago-samlingen
- valgt Wago-artikel og nødvendige/tilgængelige porte
- kendte fejl fra tændingsmapping og terminalkapacitet
- advarsler for aktive ikke-fordelte ledere og manuel korrespondance/krydsning

Status vises grøn når der ikke er kendte montagefejl, gul ved forhold der kræver opmærksomhed og rød ved en fysisk/logisk konflikt.

## Projektdata

Der tilføjes ingen nye felter i 0.50.7. `pl_box_splices` kan allerede gemme `position` og `article_no`. Den eneste ændring er semantikken: findes en Wago for en funktion, repræsenterer den nu hele samlingen for funktionen.
