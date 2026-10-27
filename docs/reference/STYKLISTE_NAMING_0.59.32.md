# Stykliste-navngivning 0.59.32

Stykliste-navnet er fortsat fri tekst. Ved siden af navnet kan der gemmes strukturerede parametre:

- Type
- Opbygning
- Funktion / udførelse
- System / serie
- Montering
- Farve
- Ekstra tekst

De strukturerede værdier bruges til filtrering og sortering i styklistebiblioteket og ændrer ikke BOM-indholdet.

## Kurateret System / serie

System-/seriefeltet er kontrolleret i stedet for frit tekstfelt. Listen er baseret på LK/Schneider Electric-produkt- og systemmateriale og skelner mellem forskellige typer navne:

- LK FUGA — produktprogram
- LK FUGA AIR — installationssystem
- LK FUGA AIR SLIM — installationsvariant
- LK FUGA SLIM, SOFT, PURE, CHOICE, BASE 63 og BASELINE 50 — FUGA-designserier
- LK FUGA SOFTLINE 63 og 68 — reelle ældre FUGA-designserier
- LK OPUS 66 og LK OPUS 74 — produktprogrammer
- LK CLIC'LINE — produktprogram
- Wiser — smart home-system

Betegnelsen `Original` er bevidst ikke et system/serie-valg; den kan anvendes som Funktion/udførelse for relevante produkter.

Hvis en bruger har et specialtilfælde, kan det almindelige stykliste-navn fortsat skrives helt manuelt. Ukendte fritekstværdier bliver ikke gemt som struktureret system-/seriefilter.
