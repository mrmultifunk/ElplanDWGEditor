# PL-lederfordeling 0.50.5

## Delete / Backspace

Når en leder er valgt i den grafiske ledereditor, frigør **Delete** eller **Backspace** lederens funktion. Den samme sikre kodevej som knappen **Frigør valgt leder** bruges, så lederen også fjernes fra en eventuel Wago-samling.

## Visuel oprydning

Den tidligere brede kabelkappe mellem kabelkortet og PL-dåsen er fjernet. Den lå visuelt bag den midterste leder og kunne ligne en ekstra isoleringskappe.

Lederkurverne består nu af én kontinuerlig cubic Bézier-kurve. Første kontrolpunkt holder lederen næsten lodret ud fra indføringen, og det sidste kontrolpunkt giver et næsten vandret indløb mod terminalen. Der er derfor ikke længere et hårdt knæk mellem et lige stykke og kurven.

## Wago-artikler og BOM

Det indbyggede artikelbibliotek indeholder nu WAGO 221-serien:

- `221-412` – 2-leder
- `221-413` – 3-leder
- `221-415` – 5-leder
- `221-420` – 10-leder

En Wago-samling gemmer nu valgfrit `article_no`. Wago-editoren viser artikelvælger og foreslår den mindste passende variant ud fra **antal kabelleder(e) + én bro til lampeudtaget**. Brugeren kan stadig vælge en anden kompatibel artikel.

`build_bom()` tæller én valgt Wago-artikel pr. gemt Wago-samling. En Wago-samling uden artikelnummer vises i listen over manglende BOM-dele.
