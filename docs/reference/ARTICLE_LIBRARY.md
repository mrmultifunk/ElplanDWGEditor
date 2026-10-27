# Indbygget artikelbibliotek – 0.42.4

Biblioteket er kontrolleret 2026-08-21 mod producenternes og grossistens online produktinformation og gemmes i `predefined_articles.json` med en genereret Python-fallback til pakkede builds.

## Omfang

- **438** unikke artikler i alt.
- **323** Schneider Electric / Lauritz Knudsen: LK FUGA og Wiser.
- **38** Waskönig+Walter: DK05 Basic, N1XZ1/N1XZ1 Dca og PXILD.
- **77** Nordtronic A/S: første kuraterede installationsrelevante batch med bl.a. Quick Install G2, Uni Install G2, fronter, Low Profile Flexible G2 og Zigbee-lyssteueringsprodukter.

LK-delen omfatter afbrydere, stikkontakter/udtag, tangenter, afdækninger, dåser, rammer, tekniske montagerammer og Wiser-enheder. 0.41.0 indeholder en særskilt datavask af **tangenter og afdækninger**, inkl. almindelige afbrydertangenter, stik-/EDB-/hospitalafdækninger, nøgle-/træk-/PIR-/timerfunktioner, blænd-/tekstfelter, lampe-/komfurudtag samt relevante data-/antennevarianter.

Biblioteket er en vedligeholdelig arbejdsbaseline, ikke et live spejl af grossistens lager. Historiske specialvarianter kan fortsat eksistere uden for biblioteket. Der tilføjes ikke gættede varenummer-, EAN- eller EL-nr.-kombinationer.

## Navngivning og metadata

Artiklerne følger så vidt muligt en fælles struktur:

- producent/serie først i beskrivelsen (`LK FUGA · …`, `Nordtronic · …`, `Waskönig+Walter · …`)
- modulstørrelser som `1M`, `1½M`, `2M`, `2½M` osv.
- ensartede produkttyper, designfamilier og farvebetegnelser
- EAN og EL-/LM-nr. udfyldes, når værdien er verificeret
- `product_page` peger for LK på producentens LK-side, når muligt
- `supplier_page` bruges til en verificeret grossistside, primært Lemvigh-Müller

## Ydelse i 0.42.0

Artikel-søgeindekset er nu fælles for artikelvælgeren og Standardbiblioteket. BOM-dialogens samlede katalog (standardartikler + globale styklisteartikler + projektartikler + prisoverrides) caches under en refresh-cyklus og genberegnes kun, når katalog eller prisbog ændres. Det reducerer gentagen normalisering/kopiering, når flere faner opdateres efter samme handling.

## Ydelse i 0.41.5

Artikelvælgeren og Standardbiblioteket bruger nu `QTableView` + `QAbstractTableModel`. Filtrering udskifter modellens rækkeliste i stedet for at destruere og genoprette tusindvis af tabelceller. Det reducerer især låsninger ved søgning, filterskift og nulstilling af filtre. Produktpreview starter først onlineopslag efter en kort pause, og forældede requests afbrydes ved hurtigt artikelskift.

## Artikelvalg i styklister

Stykliste-editoren bruger i 0.41.0 en selvstændig artikelvælger i stedet for en lang dropdown. Den kan:

- fritekstsøge på artikelnummer, navn, EAN, EL-/LM-nr., serie og specifikationer
- filtrere på fabrikat, produkttype, serie/design, modul, farve og status
- begrænse resultatet til artikler med EAN
- sortere på alle viste kolonner
- vise produktpreview og centrale metadata før valg
- åbne producent- og leverandørside direkte
- vælge en række med dobbeltklik

## Produktfotos og tegninger

Artikelpreview kan hente et produktfoto/produktillustration ved behov. Verificerede billedkilder gemmes som metadata; billederne redistribueres ikke i ZIP-filen. Et hentet billede caches lokalt, og programmet falder tilbage til den skematiske vektorillustration, hvis onlinebilledet ikke kan hentes.

For LK er producentens produktside den primære produktreference, og previewet forsøger først LK's eget varenummerbaserede katalogfoto (`www1.lk.dk/katalog/foto/jpg/<varenr>.jpg`). Hvis det ikke findes, faldes der tilbage til produktsiden og derefter den skematiske vektorillustration. Lemvigh-Müller bevares som separat leverandørreference, hvor der findes et sikkert direkte match. Nordtronic bruger primært producentens egne produktsider og datablade.

## Filtrering

Standardbiblioteket kan filtreres på bl.a. fabrikat, produkttype, designfamilie, modulstørrelse, farve, diameter, CCT og IP-klasse. Nordtronic-produkter har desuden tekniske metadata som hulmål/diameter, effekt, form og miljø, hvor producentdata er tilgængelige.

## Datakilder og forbehold

Primære kilder er Schneider Electric/LK's danske produktinformation, Lemvigh-Müller, Waskönig+Walter og Nordtronics officielle produktdata. Producenter og grossister kan ændre produktstatus, URL'er og katalogdata. Kontrollér derfor altid den aktuelle produktside før bestilling.


## FUGA-krydstjek i 0.41.1

De centrale fysiske FUGA-produkter i Schneider/LK's 20-års garantiliste er krydstjekket mod standardbiblioteket. Rene BULK-/DETAIL-pakningsvarianter er ikke tilføjet som standardartikler, da de ellers giver mange dubletter af samme fysiske produkt i artikelvælgeren. 501D0412 er verificeret med EL-nr. 1017056224 og EAN 5703302157087.

## Global styklistebibliotek og hurtig søgning i 0.41.2

Styklister er ikke længere projektafhængige. De gemmes under brugerens ElplanDWGEditor/AppData-mappe og er tilgængelige i alle projekter på samme PC. Projektet gemmer kun stykliste-ID'et for den konkrete symbol-/kombidel. Globalfilen indeholder desuden snapshots af artikler som styklisterne bruger, så egne artikler kan genbruges.

Artikelvælgeren for styklister og Standardbibliotek-søgningen bruger et forberegnet søgeindeks, 180 ms debounce og tabelopdatering i små batches. Det undgår at genopbygge hele artikeltabellen for hvert tastetryk.


## Global prisbog i 0.41.3

Standard- og projektartikler kan få en global enhedspris/prisestimat ekskl. moms. Prisdata gemmes separat fra projekterne og følger artikelnummeret på tværs af projekter. Følgende metadata gemmes: `unit_price`, `price_currency`, `price_kind`, `price_source`, `price_checked` og `price_note`. BOM summerer kun priser inden for samme valuta og viser manglende pris som `—`.
