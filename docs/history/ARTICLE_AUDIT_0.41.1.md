# Artikeldata-audit 0.41.1 — LK FUGA

## Grundlag

Auditten sammenligner standardbiblioteket med:

- LK FUGA-produktkataloget på lk.dk / LK's onlinekatalog.
- Schneider/LK's liste over produkter omfattet af 20 års garanti (køb efter 1. januar 2024), som indeholder varenr., EL-nr. og EAN.
- Lemvigh-Müller som sekundær kontrol af udvalgte aktive/legacy produkter og leverandørstatus.

LK oplyser selv, at FUGA-serien består af knap 500 produkter. Biblioteket er derfor fortsat et kurateret installations-/BOM-bibliotek og ikke et garanteret spejl af samtlige historiske reservedele og pakningsnumre.

## 501D0412

501D0412 fandtes allerede i 0.41.0, men uden de metadata som artikelvælgerens filtre er afhængige af. I 0.41.1 er posten kompletteret:

- LK nr.: 501D0412
- Beskrivelse: dobbelt stikkontakt for to tændinger, 2M, uden afdækning
- EL-nr.: 1017056224
- EAN: 5703302157087
- Produkttype: Stikkontakt / udtag
- Modul: 2M
- Farve/udførelse: Uden afdækning

De direkte tilhørende 2M-afdækninger 500D5012, 500D6012, 500D8012 samt antibakteriel 580D6012 er også tilføjet.

## Garantiliste-krydstjek

Garantilisten indeholder 119 FUGA/LK-referencer i den kontrollerede kerne:

- 78 er egentlige fysiske produktvarianter.
- 41 er BULK-/DETAILFORPAKNING-varenumre af produkter, der også findes i normal udførelse.

0.41.0 manglede 28 af de 78 fysiske varianter. De er tilføjet i 0.41.1, og eksisterende poster i samme referencegrundlag har fået verificeret EL-nr./EAN og filtermetadata.

Pakningsvarianterne er foreløbig ikke oprettet som separate standardartikler, fordi det giver mange visuelt identiske dubletter i styklistevælgeren. Hvis indkøbs-BOM senere skal skelne mellem detail-, standard- og bulkpakning, bør det modelleres som et separat pakningsniveau i stedet for at blande dem ind i den normale komponentliste.

## Yderligere fund

Ved stikprøver i LK-onlinekataloget og Lemvigh-Müller blev yderligere mangler fundet uden for garantilistens kerne, bl.a.:

- 501D0022 — dobbelt EDB-stikkontakt 2M uden afdækning (legacy/udgået hos LM).
- 500D5022 / 500D6022 / 500D8022 — tilhørende 2M EDB-afdækninger.
- 541D0721 — EDB-stikkontakt med programmerbar LED, 1½M.
- 541D0731 / 541D6731 — hospitalsstikkontakt med programmerbar LED, 1½M.
- 541D6212 — dobbelt stikkontakt med LED, 2M, hvid.
- 506D0712 — timer-stikkontakt, 1½M, uden afdækning.

Disse er tilføjet med verificeret metadata, hvor kilden eksponerede oplysningerne. For 500D6022 er EL/EAN bevidst efterladt tomt, fordi den fundne producentvisning ikke eksponerede værdierne entydigt; værdier er ikke gættet.

## Fortsat audit

For et reelt komplet FUGA-bibliotek bør de resterende områder gennemgås familievis: dåser, underlag, designrammer, tekniske rammer, elektronik, data/antenne, Wiser, tilbehør og reservedele. Det bør samtidig besluttes, om historiske/udgåede artikler og paknings-SKU'er skal være skjult som standard eller ligge i en separat "Legacy / indkøb"-visning.
