# Visning, kabelstil og patchpanel – 0.46.0

## Hurtig visning

Knapperne **Plan**, **Symboler**, **Kabler** og **Tekst** er visningsfiltre oven på Lag-panelet. Hvis et CAD-lag allerede er skjult i Lag, bliver det ved med at være skjult, når Plan slås fra og til. **Vis alt** aktiverer kun hurtigfiltrene; det tænder ikke individuelle projektlag, som brugeren selv har slået fra.

- Plan: alle importerede DWG/DXF-lag.
- Symboler: alle genererede el-symboler. Symbolmærkning skjules også, så tekst ikke hænger uden sit symbol.
- Kabler: EL-KABLER og EL-LEDNINGER samt parallel-/bundle-visning.
- Tekst: symbolmærkning/tilhørsforhold og EL-FRITEKST.

Hurtigfiltrene påvirker kun editorvisningen. PDF/print bruger fortsat Lag-panelets projektlag.

## Kabelstil

Hvert kabel gemmer `color` og `line_style`. Understøttede linjetyper er `solid`, `dash`, `dot` og `dashdot`. Farve og linjetype vises i editoren og eksporteres til PDF/print/DXF. Selve centerlinjen og længdeberegningen ændres ikke.

## Patchpanel

`patch_panel` ligger på EL-TELE-DATA. Det vises som en kompakt 2×6-port enhed og har 12 individuelle connection points. Ethernet-kabler kan derfor snappe til konkrete porte i stedet for ét fælles centrum.
