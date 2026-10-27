# Portable data – 0.45.0

## Formål

Programdata er opdelt i to uafhængige transporttyper.

### Kernedata (`.elplancore`)

Indeholder:

- Global artikelbase (`articles.json`)
- Globale styklister (`bom_assemblies.json`)
- Prisbog/prisestimeringer (`article_prices.json`)
- Portable programindstillinger, herunder custom-symboler, favoritter og kabel-/visningsstandarder

Indeholder ikke:

- Projekter
- DWG/DXF
- ODA File Converter-sti
- Seneste projektstier og maskinspecifik vinduesplacering
- Logs eller produktfoto-cache

Ved import gemmes først en automatisk `.elplancore`-backup i `backups` under brugerens Elplan-datamappe.

### Projektpakke (`.elplanproj`)

Indeholder:

- Én `.elplan.json`-projektfil
- Projektets DWG/DXF-kilde
- Manifest med afhængige artikelnumre, stykliste-ID'er og custom-symbolkoder

Indeholder ikke selve artikelbasen, styklisterne, prisbogen eller programindstillingerne. Efter import ligger projekt og kildefil i separate undermapper, og projektets `source_file` er relativ.

## Anbefalet PC-flytning

1. På gammel PC: **Fil → Overfør / backup → Eksportér kernedata…**
2. Eksportér hvert aktivt projekt med **Eksportér projektpakke…**
3. På ny PC: importér `.elplancore` én gang.
4. Importér derefter de ønskede `.elplanproj`-filer.
5. ODA File Converter konfigureres lokalt på den nye PC, hvis DWG kræver det.

## Integritet

Begge pakker er ZIP-containere med `manifest.json`. Alle payload-filer har SHA-256-checksum og valideres før import. Stier i pakken kontrolleres mod path traversal.
