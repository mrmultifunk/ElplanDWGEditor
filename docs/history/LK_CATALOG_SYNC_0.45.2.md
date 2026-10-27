# LK-katalogsynkronisering – 0.45.2

## Formål

LK-artikler er kernedata og skal kunne opdateres uafhængigt af projekter. Funktionen **Synkronisér LK.dk…** importerer LK/Schneiders onlinekatalog til den globale `articles.json`.

## Datakilder

- Katalogindeks: `https://www1.lk.dk/katalog/nmkatalog.ph7`
- Produktdetaljer: LK's server-renderede katalogsider pr. varenummer/EAN
- Brugerrettet produktlink: `https://www.lk.dk/produkter?iid=<LK-nr>`
- Produktfoto: `https://www1.lk.dk/katalog/foto/jpg/<LK-nr>.jpg`

Det server-renderede katalog bruges til indeks/discovery, fordi det kan læses uden browser-JavaScript og omfatter de samme LK-produktfamilier, herunder LK One, LK FUGA, OPUS, Wiser, IHC m.fl.

## Merge-regler

Producentdata opdateres fra LK-kataloget. Følgende lokale data bevares:

- `supplier_page`
- brugerens egne noter
- prisbog/prisestimat (ligger separat i `article_prices.json`)
- ikke-LK-artikler

## Sikkerhed

- Databasen ændres først når hele kataloghøsten er færdig.
- Annullering eller netværksfejl efterlader databasen urørt.
- En mistænkeligt lille høst afvises.
- Før skrivning laves automatisk en tidsstemplet backup af artikelbasen.

## 0.45.2 – robust katalog-discovery

LK's legacy-kategorisider kan vise produktkort uden klassiske `vnr=`/`urlref=`-links. Produktets LK-nummer ligger i stedet ofte i produktbilledets filnavn, fx `/katalog/foto/jpg/588D6693.jpg`, mens andre templates lægger navigationen i `onmousedown` eller andre HTML-attributter. Synkroniseringen accepterer derfor nu alle disse discovery-former og sammenfletter EAN- og varenummerfund, så den rigeste metadata bevares.
