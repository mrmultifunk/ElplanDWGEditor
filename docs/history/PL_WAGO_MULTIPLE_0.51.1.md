# PL-dåse – flere Wago-samlinger (0.51.1)

## Formål

Installatøren skal kunne planlægge den fysiske PL-dåse uden en kunstig begrænsning på én Wago pr. funktion. Version 0.51.1 tillader derfor vilkårligt mange Wago'er, også flere med samme elektriske funktion.

## Datamodel

`pl_box_splices` er fortsat en liste af samlinger med `id`, `function`, `members`, `article_no`, `connects_to_outlet` og evt. `position`. Forskellen er, at `function` ikke længere er unik. `id` er den fysiske identitet. En fysisk leder må fortsat kun være medlem af én Wago.

Medlemmer er eksplicitte i både bro- og sløjfetilstand. Det gør fx to separate N-Wago'er entydige.

## Terminalbelastning

- Direkte leder til terminal: 1 plads.
- Wago med bro til udtag: 1 plads pr. Wago.
- Wago kun til intern sløjfe: 0 pladser.

Montagekontrollen må gerne rapportere overbelastning, men manuel oprettelse af ekstra Wago'er blokeres ikke.

## UI

**Ny Wago…** forbliver aktiv, så længe udtaget har en gyldig funktion. Funktionsvælgeren viser hvor mange Wago'er der allerede findes på funktionen. Wago-listen nummererer flere samlinger på samme funktion. Lederdiagrammet placerer og tegner hver Wago efter dens eget `id`.

## Dark mode

0.51.1 bygger direkte videre på 0.51.0 og indeholder hele dark mode-implementeringen. Wago-blokkene bruger fortsat de mørktilpassede semantiske farver.
