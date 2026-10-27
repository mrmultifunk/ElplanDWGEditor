# Artikeldata-audit 0.59.17

Auditten er ikke-destruktiv. Producentens rå værdier ændres ikke.

## Aktuel medfølgende grunddatabase

- 449 artikler
- 0 ugyldige EAN-kontrolcifre
- 0 dublerede EAN i de medfølgende data
- 100 artikler mangler EAN/GTIN
- 129 artikler mangler EL-/LM-nummer
- 104 artikler mangler direkte/lokalt produktbillede
- 40 artikler bruger `Uden afdækning` i feltet Farve; dette er en variant-/konfigurationstilstand og bør ikke være en farve
- 25 beskrivelser indeholder store `m`-mål, fx 100 m / 500 m. De er korrekte produktdata, men må aldrig fortolkes som FUGA-moduler
- 19 rå statusbetegnelser kan repræsenteres med 4 stabile statusgrupper (Aktiv, Legacy, Udfaset, Udgået), mens producent-/erstatningsdetaljer bevares separat
- `Schneider Electric / Lauritz Knudsen` bruges på 323 artikler. Det bør på sigt splittes i officiel producent og brand, fx `manufacturer=Schneider Electric`, `brand=LK`, uden at produktnavne som LK FUGA omskrives
- To kategoriområder kræver manuel taksonomigennemgang: `LK FUGA · Afbrydere` vs. `LK FUGA · Afbrydere og betjening`, samt almindelige FUGA- vs. Wiser-tangentkategorier

### Hvor mangler EAN især?

- Waskönig+Walter kabler: 38
- Wiser · Enheder: 27
- LK FUGA Wiser · Tangenter og afdækninger: 23
- Øvrige LK/Wiser: 11
- Nordtronic: 1

### Hvor mangler billeder især?

- Nordtronic: 66
- Waskönig+Walter: 38

### Hvor mangler EL-/LM-numre især?

- Nordtronic: 78
- Waskönig+Walter: 38
- Schneider Electric / LK: 11
- WAGO: 1
- HELUKABEL: 1

## Normaliseringsprincip til næste trin

Hver egenskab bør skelne mellem producent-/kildedata og Elplans søge-/filterværdi. Eksempel:

- `manufacturer_raw` / `manufacturer`
- `brand_raw` / `brand`
- `category_raw` / `category_normalized`
- `series_raw` / `series_normalized`
- `color_raw` / `color_normalized` / `color_family`
- `module_raw` / `module_normalized`
- `status_raw` / `status_normalized`

Rå producentdata må aldrig overskrives af en automatisk normalisering.

## Safe fixes i 0.59.17

- Modul-parseren accepterer kun plausible 0,5-trins modulstørrelser og kontrollerede flerfeltsformer. Fx `451200M` og kabelmål som `100 m` bliver ikke længere modulfiltre.
- Farvefilteret samler kun trivielle forskelle i store/små bogstaver og spacing.
- Semantiske farver slås ikke sammen uden producentgrundlag; fx mappes `Antracit` ikke automatisk til `Koksgrå`.
