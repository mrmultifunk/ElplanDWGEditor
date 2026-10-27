# Performance 0.59.59

Denne version fortsætter den sikre visningsoptimering fra 0.59.58. Projektdata,
kabelgeometri, BOM og PDF-regler er uændrede.

## Kabel-layout

0.59.58 indførte en konservativ bounding-box sweep før den præcise
segmenttest. En Python-listeslice i den indre løkke kopierede imidlertid stadig
hele den resterende liste for hvert segment. 0.59.59 bruger indeksbaseret
iteration og undgår kopieringen.

Endepunkts-fan-out brugte desuden en separat all-pairs-sammenligning. Den er
erstattet af to konservative kandidatopslag:

- eksakt `(symbol_uid, symbol_port)` for autoritative terminaler;
- naboceller i et koordinatgitter for legacy-endepunkter.

Den eksisterende præcise anker- og retningstest er fortsat autoritativ.

## Mærkningslayout

Kollisionsmotoren bruger et eksakt uniformt gitter. Rektangler returneres i
oprindelig indsættelsesrækkefølge, så kandidatvalg og fallback for tætte planer
er deterministisk og visuelt kompatibelt med 0.59.58.

Qt-mærkninger cacher en render-signatur bestående af synligt indhold,
visningsprofil, valgt tilstand og tema. Ved almindelig zoom inden for samme
semantiske niveau genbruges child-items; kun scene-position og fælles
kollisionslayout opdateres.

## Kontrol

- 220 randomiserede kabelplaner gav identiske paths, metadata og grupper i
  0.59.58 og 0.59.59.
- 80 randomiserede mærkningsscenarier gav identiske valgte koordinater med og
  uden det rumlige indeks.
- 4.000 spredte enkeltsegmentskabler: ca. 14,2 s → ca. 0,05 s.
- 1.000 spredte mærkninger: ca. 2,3 s → ca. 0,09 s.

