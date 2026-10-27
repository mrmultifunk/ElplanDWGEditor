# 0.59.45 – Spotgrupper og lampested

## Model

Hvert spot kan have `spot_group_id` og `spot_group_name`. Felterne er adskilt fra
`group`, som fortsat er den elektriske gruppe/kreds. En spotgruppe er derfor kun
en logisk arbejdsgruppe.

## Arbejdsgang

- Markér flere spots og vælg **Gruppér / omdøb…**.
- **Vælg gruppe** markerer alle medlemmer igen.
- **Opløs gruppe** fjerner gruppen, men bevarer en eksisterende lampestedstilknytning.
- **Tilknyt lampested…** og **Frakobl** udvides automatisk til hele gruppen.
- Spot-række og spot-felt tildeles automatisk en ny spotgruppe ved placering.
- En gruppe kan ikke splittes via disse handlinger, hvis et medlem er låst.

Kopi/indsæt af flere gruppemedlemmer bevarer deres indbyrdes gruppering med et
nyt id, mens eksterne lampestedsrelationer nulstilles.

## Downlightkabel

Grundkataloget indeholder kabelartikel 5401046168: SOLAR SELECT H05V2V2-F
3G1,5, 90 °C, hvid, 100 m. Kabelspecifikationen er fortsat `3G1,5`; anvendelsen
ligger i artikelmetadata/kategorien Downlight.
