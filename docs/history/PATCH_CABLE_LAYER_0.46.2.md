# Patchkabellag – 0.46.2

## Formål

Patchkabler kan nu behandles som en selvstændig visningskategori uden at skabe en ny kabeldatamodel.

## Lag

- `EL-KABLER` – almindelige installationskabler
- `EL-PATCHKABLER` – patch-/netværkskabler som brugeren vælger som Patchkabel
- `EL-LEDNINGER` – ledninger

## Hurtig visning

Hovedværktøjslinjen indeholder nu **Patchkabler** ved siden af **Kabler**. Filtrene ligger oven på projektets egentlige lagtilstand og ændrer derfor ikke Lag-panelets checkbokse.

**Kabler** styrer almindelige kabler og ledninger. **Patchkabler** styrer kun `EL-PATCHKABLER`. **Vis alt** tænder begge igen.

## Eksisterende projekter

Gamle kabler flyttes ikke automatisk. CAT6/CAT7 kan også være fast installationskabel, så en automatisk migration ville kunne være forkert. Markér et eksisterende kabel, vælg **Patchkabel** under Type og tryk **Anvend kabeldata**.

## Data og output

Lagvalget gemmes i `CablePlacement.layer` og følger derfor med projektfil, DXF, PDF/print-lagfiltrering, BOM og længdeberegning.
