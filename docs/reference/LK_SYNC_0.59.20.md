# Skånsom LK-synkronisering 0.59.20

## Formål

0.59.20 ændrer LK-importen fra parallel crawling til en konservativ, sekventiel klient. Målet er at minimere risikoen for midlertidig rate-limit/IP-blokering og samtidig gøre lange synkroniseringer robuste over for afbrydelser.

## Trafikpolitik

- Højst én aktiv request til LK.dk ad gangen.
- Standardpause mellem requests: 0,8–1,5 sek. med tilfældig variation.
- Produktcache/databaseposter genbruges ved normal sync i op til 14 dage.
- Katalogindeks genbruges i op til 24 timer.
- En fuld genhentning omgår produktcache, men må genbruge et friskt katalogindeks.
- Cache v2 fra 0.59.18/0.59.19 migreres til v3 uden at smide eksisterende produktdata væk.

## Rate-limit og backoff

`fetch_text()` bevarer HTTP-statuskoden via `CatalogHttpError`. `collect_catalog()` behandler HTTP 403, 429 og 5xx som signal om, at trafikken skal bremses. Standard backoff er 5, 15, 45 og 120 sekunder; et numerisk eller HTTP-date-baseret `Retry-After` kan forlænge pausen.

Hvis serveren fortsat afviser requests efter backoff-sekvensen, kastes `CatalogAccessLimitedError`. Crawlet stopper straks, cachen gemmes, og artikelbasen forbliver urørt.

## Checkpoint og genoptagelse

Cachen indeholder fra version 3 et `checkpoint` med katalogreferencer, kendte variantreferencer og færdige referencer. Checkpointet bruges kun, når det matcher sync-typen og katalogreferencerne og er højst 7 dage gammelt.

Ved en afbrudt fuld genhentning kan produktsider, som allerede blev færdige og gemt i produktcachen, genbruges ved næste fulde genhentning. Når hele crawlet er gennemført, nulstilles checkpointet.

## Fejlsikring

Hvis ingen katalogside overhovedet kan hentes, stoppes synkroniseringen før fallback-probing. Det forhindrer, at en generel netværks- eller DNS-fejl udløser hundredvis af ekstra requests.

## GUI

Dialogen **Synkronisér LK.dk…** bruger betegnelserne **Skånsom synkronisering** og **Fuld genhentning (skånsom)**. Fremdrift viser én forbindelse, cachegenbrug og checkpoint-resume. Resultatdialogen viser desuden pauseinterval, rate-limit-hændelser, samlet backoff og checkpoint-genbrug.
