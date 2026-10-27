# Produktsemantisk artikelmodel 0.59.21

## Formål
Produktidentitet og kompatibilitet må ikke blandes. Modellen har derfor tre uafhængige dimensioner:

- `product_family`: stabil familie, fx `LK FUGA AIR`.
- `product_variant`: produktets egen udførelse, fx `Standard`, `SLIM` eller `Brandsikker`.
- `compatibility`: strukturerede, verificerede forhold til designserier/montagesystemer/andre familier.

`design_family_raw` er legacy/provenance og må ikke bruges som autoritativ identitet for dåser.

## Evidensprioritet
Manuel verificering > gemt kontrolleret semantik > verificeret artikelserie > produktnavn > producentens rå serie. Kompatibilitetstekst bruges kun til kompatibilitet.

## LK FUGA AIR
- 504D3010/3015/3020/3025: familie `LK FUGA AIR`, variant `Standard`.
- 504D3510/3515/3520/3525: familie `LK FUGA AIR`, variant `SLIM`.
- 504D3110/3115/3120/3125: familie `LK FUGA AIR`, variant `Brandsikker`.
- Kendte AIR indstøbnings-/indmuringsdåser: familie `LK FUGA AIR`, variant `Standard`; SLIM kan optræde som kompatibilitet, ikke identitet.

## Validator
Auditten markerer bl.a. kompatibilitet brugt som identitet, legacy design/variant-konflikter, manglende AIR-variant og blandede familie-/variant-seriefelter. Automatiske korrektioner ændrer ikke rå provenance.
