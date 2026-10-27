# PL-lederfordeling 0.50.4 – manuelle Wago-samlinger

## Formål

Version 0.50.4 ændrer Wago-funktionen fra automatisk grafik til en bevidst montagebeslutning, som brugeren kan redigere.

## Terminalkapacitet

- **LK Wiser / dæmpbar:** maks. 2 fysiske tilslutninger pr. terminal.
- **LK klassisk lampeudtag:** maks. 4 fysiske tilslutninger pr. terminal.
- En Wago-samling tæller som **én** fysisk tilslutning i lampeudtaget via en kort bro fra Wago til terminalen.
- Ledere som ikke er med i Wago-samlingen går direkte til terminalen og tæller hver for sig.

## Arbejdsgang ved overfyldt terminal

Når en bruger forsøger at tildele en leder til en terminal, og den nye tilslutning vil overskride terminalens kapacitet, udføres tildelingen ikke med det samme. Der vises i stedet en advarsel med:

- **Tilføj Wago** – opretter eller udvider en Wago-samling for den pågældende funktion og reducerer terminalforbruget til et gyldigt niveau.
- **Annuller** – bevarer den eksisterende lederplan.

Den automatisk foreslåede Wago kan bagefter redigeres manuelt.

## Manuel redigering

Wago-rækken i lederfordelingen indeholder:

- **Ny Wago…** – vælg en funktion og derefter de konkrete ledere som skal samles.
- **Redigér…** – tilføj eller fjern enkelte ledere fra den valgte Wago.
- **Fjern Wago** – fjerner selve samlingen, men bevarer ledernes elektriske funktion. Hvis dette overfylder en terminal, vises en advarsel.

En Wago-samling skal indeholde mindst to kabelledere.

## Frigørelse af enkeltleder

Når en leder er valgt i grafikken eller tabellen, kan **Frigør valgt leder** bruges til at fjerne netop denne leders funktion/klemmetilknytning. Hvis lederen indgik i en Wago, fjernes den samtidig fra samlingen. Resten af lederplanen bevares.

## Projektdata

Lampesteder har nu feltet `pl_box_splices`. Hver post indeholder:

- stabilt Wago-id
- elektrisk funktion (`n`, `pe`, `l`, `switch:a` osv.)
- konkrete lederreferencer (`cable_uid`, `point_index`, `leg`, `core_id`)
- valgfri note

Ved kabelændringer reconciles Wago-medlemmer mod de aktuelle fysiske ledere. En leder kan kun være medlem af én Wago-samling.
