# Lysgrupper og væg-lampeudtag i 0.59.81

## Flere fysiske lampesteder på samme tænding

To eller flere lampesteder, som tænder samtidigt, skal fortsat være separate fysiske symboler. De kan have forskellig placering, kabelvej, montage og artikel, men deler samme afbryderkanal og tilhørsbogstav.

Arbejdsgangen er:

1. Markér lampestederne med `Ctrl`-klik eller en markeringsramme.
2. Vælg `Samme tænding…` i den kontekstuelle værktøjslinje.
3. Vælg den konkrete afbryder og fysiske betjening.
4. Programmet tildeler alle valgte lampesteder samme relation. En ledig afbryderkanal får automatisk næste frie bogstav.

Ændringen gemmes som én fortrydelseshandling. Hvis et lampested allerede tilhørte en anden tænding, flyttes det til den valgte funktion, og et gammelt bogstav ryddes kun, når det ikke længere bruges andre steder.

Et fysisk PL-lampested med flere uafhængige udgange kræver fortsat den normale tilknytningsguide, så den konkrete udgang kan vælges entydigt.

## Lampeudtag på væg

`Lampeudtag på væg (alm. dåse)` findes under Belysning. Det viser et lampestedskryds med en kort stamme frem til væggens montagepunkt.

- Symbolet snapper og orienterer sig som andet vægudstyr.
- Kabel kan afsluttes ved selve vægdåsen eller det synlige symbolpunkt.
- Symbolet har én tænding og kan indgå i `Samme tænding` sammen med andre lampesteder.
- Det åbner ikke PL-dåsekonfiguratoren og gemmer ingen PL-indføringer, Wago-samlinger eller PL-lederplan.
- Artikel eller stykliste er valgfri og tilknyttes den konkrete fysiske forekomst.
