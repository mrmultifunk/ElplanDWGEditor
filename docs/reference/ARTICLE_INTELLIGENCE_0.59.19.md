# Artikelrelationer og strukturerede artikeldata 0.59.19

0.59.19 lægger et generelt, producentuafhængigt lag oven på artikelkilderne. Kildedata bliver ikke omskrevet: producentens `category`, `description`, `manufacturer`, farve- og moduldata bevares, mens Elplan tilføjer kontrollerede metadata til søgning, variantgrupper, relationer og kvalitet.

## Kontrolleret taksonomi

`category_normalized` er en stabil Elplan-kategori med hovedgruppe og underkategori. Den afledes ud fra eksplicit produkttype, producentkategori, serie og tydelige produktord. Manuelt valgt standardkategori har prioritet, hvis den findes i programmets kontrollerede liste. `category_group` og `subcategory` afledes af standardkategorien.

## Tekniske egenskaber

`technical_specs` er et JSON-objekt med strukturerede egenskaber, fx modul, farve, montage, spænding, strøm, polkonfiguration, jord, smart-protokol, IP, CCT, effekt og kabeldata. Kun eksplicitte eller stærkt evidensbaserede værdier udledes. Fx må `Cat. 6A` ikke blive tolket som 6 ampere.

Brugeren kan gemme verificerede overrides i `technical_specs_manual`. De flettes oven i de automatisk udledte værdier og slettes ikke ved ny katalogsynkronisering.

## Variantgrupper

En variantgruppe betyder "samme grundprodukt i andre varianter" - ikke mekanisk kompatibilitet. Standardnøglen bruger producent, serie, produkttype/design, modul og et produktnavn hvor kendte variantværdier som farve og CCT er fjernet. `variant_axes` viser hvilke egenskaber der faktisk varierer i gruppen. `variant_group_manual` kan bruges til at tilsidesætte den automatiske gruppering.

## Relationer

Bekræftede relationer gemmes som en liste af objekter med `type`, `target_article_no`, valgfri `source` og valgfri `note`. Understøttede typer er kompatibel, tilbehør, kræver, erstatning, alternativ og del-af.

Kompatibilitetsforslag beregnes dynamisk ud fra kontrolleret kategori, producent, serie/design og modul. Eksplicitte systemnavne i produktteksten (fx FUGA, OPUS eller CLIC'LINE) har forrang over importerede serie-/designfelter, fordi ældre kildedata kan indeholde stale metadata. Forslag er kun kandidater og bliver aldrig skrevet til databasen uden en eksplicit brugerhandling.

## Datakvalitet

Auditten er fortsat ikke-destruktiv. Ud over identitet, EAN/EL-nr., kilder, farver og moduler kontrollerer den nu ukategoriserede/ugyldige standardkategorier, manglende strukturerede egenskaber, variantgrupper der krydser kategorier og relationer til manglende målartikler.

Der beregnes en transparent artikel-score 0-100. Fejl vægter mest, advarsler mindre, og informationsfund er begrænset, så katalogbrede oprydningsnoter ikke kan dominere en ellers brugbar artikel.
