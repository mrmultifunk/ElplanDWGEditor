# Performance i 0.59.78

Version 0.59.78 reducerer arbejdet i de mest brugte musegestusser uden at ændre projektdata eller snap-resultater.

## Symboltræk

Selve symbolets position opdateres stadig straks. Afhængige mærkninger og tilsluttede kabelkurver køres gennem en 16 ms single-shot timer og samles pr. kabel, så mange rå museevents ikke udløser samme arbejde gentagne gange. Ved slip udføres den endelige kabelcache og den præcise mærkningsplacering.

Mærkningen bruger under trækket sin senest kendte retning. Derved undgås gentagne rumtest, vægsøgninger og symbolprimitive-beregninger. Retningen beregnes på ny ved afslutningen.

## Snap under aktive gestusser

Ved træk og fortløbende placering af lyssymboler oprettes én kandidatliste over synlige lyssymboler. Den flyttede gruppe eller den gennemsigtige preview-forekomst er udeladt. Efter hver ny placering fornyes listen, så næste symbol stadig kan snappe til det netop placerede.

Ved kabeltegning og flytning af kabelknæk caches andre kabelruter, kabelpunkter og symbolporte. Kabelruter har desuden en afgrænsningsboks, så ruter langt fra markøren frasorteres før projektion mod linjestykkerne.

## Hover og opslag

Kædefremhævning for kabler anvender en symmetrisk differens mellem tidligere og ønsket fremhævning. Kun kabler, der skifter tilstand, animeres. Symbolopslag ved kabelankre går først gennem hovedvinduets UID-indeks og falder kun tilbage til en lineær søgning, hvis grafikelementet endnu ikke findes.

## Sikkerhed

Alle gestus-cacher ryddes ved afslutning, annullering og sceneskift. Projektets eksisterende koordinater og forbindelsesposter er fortsat den autoritative model.
