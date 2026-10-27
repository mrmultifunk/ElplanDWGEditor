# Artikel-audit 0.59.21

Kørt med 0.59.21-validatoren mod den normaliserede kernedatabase fra 26-08-2026.

## Samlet resultat

- Artikler: 3539
- Fejl: 7
- Advarsler: 274
- Info: 732
- Berørte artikler: 207
- Rene artikler: 3332 (94.2 %)
- Gennemsnitlig kvalitetsscore: 86.5/100

## Semantiske fund

- Kompatibilitet tidligere brugt som identitet: **6** — 504D6010, 504D601020, 504D601520, 504D6020, 504D602520, 504D8015
- Legacy Design modsiger produktvariant: **3** — 504D3010, 504D3015, 504D3025
- AIR-dåse uden entydig variant: **0**
- AIR SLIM-navn modsiger variant: **0**
- SLIM-produkt klassificeret Standard: **0**
- Kildeserie blander familie og variant: **0**
- Produktfamilie kunne ikke udledes sikkert: **9** — 70010000, 70020000, 70030000, 70040000, 70070000, 70080000, 70090000, 70900000, 70920000

De semantiske advarsler er ikke destruktive: den kontrollerede model bruges i programmet, mens den gamle værdi bevares som rå provenance til gennemgang.
