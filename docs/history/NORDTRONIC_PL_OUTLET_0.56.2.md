# Nordtronic PL lampeudtag – 0.56.2

## Produkt
- Nordtronic A/S varenr. **98425033**
- EAN **5704629006065**
- Zigbee 3.0 bagkantsdæmper, 5–200 W LED
- PL-/Euro-dåse, IP20

## PL-model
Den nye `nordtronic_zigbee`-profil viser P, COM, PE, N, dæmpet udgang (`dimmed_out`) og L. Lampestedets første eksisterende `switch:<association>`-funktion bruges på P-terminalen, så den etablerede kontrol af afbrydertilhørsforhold og kabelben bevares. COM og dæmpet udgang er egne manuelle funktioner.

Der oprettes ingen lederfunktioner automatisk.

## BOM
`light_connection` har nu en valgfri BOM-del `outlet`. Det gør det muligt at tilknytte 98425033 til en konkret symbolforekomst uden at indføre automatisk artikelvalg eller obligatoriske manglende-artikel-advarsler.
