# Artikeldatabase 0.45.4

## Formål

0.45.4 samler artikelarbejdet i én global **Artikeldatabase**. Det tidligere UI-koncept "Standardbibliotek" er fjernet. Artikeldatabasen er kernedata og deles af alle projekter på PC'en.

## Native JSON-format

Det anbefalede udvekslingsformat er JSON:

```json
{
  "format": "ElplanDWGEditor article library",
  "format_version": 1,
  "application_version": "0.45.4",
  "articles": [
    {
      "article_no": "ABC123",
      "description": "Eksempelartikel",
      "manufacturer": "Eksempel A/S",
      "unit": "stk",
      "ean": "5700000000000",
      "el_no": "1234567890",
      "product_type": "Afbryder / betjening",
      "image_url": "https://example.invalid/abc123.jpg"
    }
  ]
}
```

Import accepterer også en ren JSON-liste med artikelobjekter og legacy-formatet `{"articles": [...]}`.

## CSV

CSV er tænkt til Excel og leverandørudtræk. Eksport skrives som UTF-8 med BOM og semikolon. Import forsøger automatisk at opdage semikolon, komma eller tabulator og genkender både engelske feltnavne og almindelige danske overskrifter.

Minimumskravet er et artikelnummer. Øvrige felter er valgfrie.

## Konflikter

- **Flet sikkert**: nye artikler tilføjes; på eksisterende artikler udfyldes kun felter, som er tomme.
- **Opdatér eksisterende**: nye artikler tilføjes; ikke-tomme værdier fra importfilen må overskrive eksisterende artikelmetadata.

En tom værdi i importfilen sletter aldrig eksisterende metadata.

Før import oprettes en tidsstemplet backup af `articles.json`.

## Billeder

Artikel-preview bruger i prioriteret rækkefølge lokal billedcache, `image_url` og derefter produktsiden som fallback. Manuelt oprettede artikler kan derfor få produktfoto ved blot at angive en direkte billede-URL eller en produktside.
