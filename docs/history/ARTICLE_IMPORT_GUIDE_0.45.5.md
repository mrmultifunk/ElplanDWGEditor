# Artikelimport – JSON / CSV (0.45.5)

I **Artikler og BOM → Artikeldatabase → Importguide…** findes den samme guide direkte i programmet. Guiden genereres fra samme feltskema som templates, så feltnavne ikke skal holdes manuelt synkroniseret flere steder.

## Minimum

Hver artikel skal have et unikt **Artikelnummer** (`article_no`). `Beskrivelse` og `Fabrikat` anbefales. Mangler `unit`, bruges `stk`.

## JSON

JSON er det anbefalede format, fordi alle metadata kan bevares. Programmet accepterer både:

```json
{"articles": [{"article_no": "ABC-123", "description": "Eksempel"}]}
```

og en simpel liste:

```json
[{"article_no": "ABC-123", "description": "Eksempel"}]
```

Brug **Gem JSON-template…** i Importguide for en komplet eksempelpost med alle understøttede felter.

## CSV

CSV er praktisk til Excel og leverandørlister. Semikolon, komma og tabulator accepteres. Den genererede template bruger semikolon og danske kolonnenavne. Kolonner, der ikke skal bruges, kan fjernes.

EAN og EL-nr. bør formateres som tekst i Excel for at undgå tab af foranstillede nuller.

Brug **Gem CSV-template…** i Importguide for en komplet template med alle understøttede felter.

## Fletning

- **Flet sikkert**: tilføjer nye artikler og udfylder kun tomme felter på eksisterende artikler.
- **Opdatér eksisterende**: ikke-tomme importværdier kan erstatte eksisterende metadata.
- Tomme importfelter sletter aldrig eksisterende værdier.
- Der tages backup af `articles.json` før import.

## Felter

Den komplette og aktuelle feltliste findes i programmets **Importguide → Felter** og drives af `article_exchange.ARTICLE_FIELD_GUIDE`.
