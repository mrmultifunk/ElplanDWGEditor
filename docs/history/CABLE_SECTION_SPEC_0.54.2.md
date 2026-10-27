# Kabeltype pr. fysisk afsnit — 0.54.2

Et enkelt `CablePlacement` kan nu skifte kabeltype mellem to fysiske nabotilslutninger uden at resten af kabelstrækningen ændres. Det er beregnet til sløjfede kabelruter gennem flere lampesteder, hvor et enkelt afsnit fx skal være `5G1,5`, mens de øvrige fortsat er `3G1,5`.

## Brugerflade

I Kabelværktøjet er **Ruteføring pr. afsnit** udvidet og omdøbt til **Indstillinger pr. afsnit**. Afsnitsvælgeren viser begge tilslutningers gruppe/kreds + mærkning samt effektiv kabeltype og ruteføring. For det valgte afsnit kan brugeren ændre både ruteføring og kabeltype. Højreklik direkte på kabelstrækket giver samme kabeltypevalg som genvej.

Når et kabel har blandede typer, vises den effektive kabeltype som en lille label på hvert fysisk afsnit på tegningen. Den fælles kabel-ID/mærkning forbliver kabellets hovedidentitet. PDF, print og DXF viser samme afsnitsvise kabeltypeinformation.

## Datamodel

`CablePlacement` har fået det valgfrie felt `spec_section_overrides`. Hver post bruger samme stabile, retningsløse symbol-UID/port-par som `route_section_modes` og indeholder `cable_spec`. Kabellets eksisterende `cable_spec` er fortsat global/default type.

Et gammelt projekt uden feltet åbner derfor uændret. Hvis en lokal værdi sættes lig den globale standard, fjernes den eksplicitte override igen.

## PL-dåser

`cable_legs_at_symbol()` bruger nu kabeltypens effektive værdi på hvert enkelt kabelben. Et lampested på overgangen 3G → 5G kan derfor vise tre ledere på den ene side og fem på den anden. Lederfordeling, Wago-logik og PL-rapport får automatisk den rigtige kabelprofil pr. indføring.

Hvis et nyt lampested efterfølgende indsættes midt i et afsnit med lokal kabeltype, arver begge nye delafsnit den eksisterende override.

## Længder og BOM

Kabellængderapportens materialesummer fordeler nu meter pr. effektiv kabeltype. En blandet kabelrute kan derfor bidrage med fx både 3G1,5 og 5G1,5.

Den eksisterende artikelbinding er stadig kabel-UID-baseret og kan derfor ikke sandfærdigt repræsentere flere kabelartikler på samme kabelobjekt. Ved blandet kabeltype tæller BOM derfor ikke én global kabelartikel over hele strækket; i stedet rapporteres de faktiske meter pr. type som manglende afsnitsvis artikeltilknytning. Det er bevidst konservativt for at undgå en forkert materialeliste.
