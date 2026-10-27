# Artikler/BOM performance — 0.59.34

## Problem

Ved ca. 3.500 artikler udførte 0.59.33 flere fulde katalogpassager synkront ved dialogåbning: kernedata blev normaliseret gentagne gange, pris-overlay normaliserede kataloget to gange, søgeindekset gentog pris-overlayet, og datakvalitetsaudit blev kørt selv uden at fanen blev åbnet.

## Ændringer

- Normaliserede kernedata genbruges direkte under første UI-refresh.
- Bundled/stored catalog merge undgår en redundant helkatalog-normalisering.
- `apply_article_prices(..., assume_normalized=True, prices_normalized=True)` bruges kun på den kontrollerede UI-hot-path. Den sikre standardadfærd er bevaret for øvrige callers.
- Søgeindekset bygges fra `_available_catalog()` og gentager ikke pris-overlay.
- Datakvalitetsaudit er lazy.
- BOM-filterstatus genbruger den allerede beregnede BOM.
- Stykliste-navngivning kan bruge et fælles article lookup.

## Benchmark

Med kernedatafilen på 3.539 artikler i buildmiljøet:

- 0.59.33 data-hot-path: ca. 6,0 s
- 0.59.34 data-hot-path: ca. 1,3 s

Målingen dækker de synkrone dataoperationer, ikke Qt-rendering. Reopening i samme proces drager desuden fordel af den eksisterende katalogcache.
