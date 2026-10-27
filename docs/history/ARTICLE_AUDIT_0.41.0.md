# Artikeldata-audit 0.41.0

Dato: 2026-08-21

Formålet med denne audit var at forbedre datakvaliteten i standardbiblioteket og gøre især LK FUGA tangenter/afdækninger praktiske i styklister.

## Regler anvendt

1. Ingen EAN eller EL-/LM-numre er konstrueret ud fra nummerserier; værdier gemmes kun, når de er verificeret i producent-/grossistdata.
2. LK-produktlink er producent-first: `https://www.lk.dk/produkter?iid=<LK-nr.>`.
3. En sikker Lemvigh-Müller produktside gemmes separat som `supplier_page`.
4. Beskrivelser normaliseres til samme sproglige struktur uden at ændre artikelidentiteten.
5. Udgåede/reservedelsprodukter kan bevares, fordi de er relevante ved renovering, men markeres med status når den kan fastslås.

## FUGA afdækningsaudit

0.41.0 udvider biblioteket med flere verificerede familier, bl.a.:

- standard hel-/halvtangenter og ældre 13 A-varianter
- blænddæksler og tekstfelt
- stikkontakt-, EDB-, LED- og hospitalafdækninger
- sidejord/pindjord, dobbelt- og afbrudte stikkontakter
- nøgleafbryder-, trækafbryder-, PIR- og timerafdækninger
- timerstikkontakt
- lampe-/5-leder lampe-/komfurudtag
- Keystone/Actassi/data/antennevarianter
- Wiser tangenter og afdækninger

Kataloget er væsentligt bredere end 0.40.0, men betegnes bevidst ikke som et juridisk/kommercielt komplet historisk spejl af alle FUGA-reservedele nogensinde. Hvis en special-/historisk artikel mangler, kan den oprettes manuelt og senere føjes til standardbiblioteket efter verifikation.
