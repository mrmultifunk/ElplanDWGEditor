# Kabelkategoridefinitioner – 0.50.20

Kabelkategorier har nu feltet `description`, som gemmes i projektets `cable_categories`.

## Standarddefinitioner

- Stikkontakter: Kabel til indendørs stikkontakter.
- Udendørs stikkontakter: Kabel til udendørs stikkontakter.
- Udendørs lys: Kabel til udendørs belysning.
- Lampesteder: Forsynings- og installationskabel til lampesteder.
- Mellemkabel: Kabel mellem lampesteder på forskellige grupper.
- Tændkabel: Kabel fra afbryder til lampested.
- Spots: Kabel til spots og downlights.
- Ladeboks: Kabel til ladeboks.
- Hvidevarer / faste forbrugere: Kabel til hvidevarer og andre faste elektriske forbrugere.
- Data / netværk: Kabel til data- og netværksinstallationer.
- Øvrige: Kabler som ikke passer i en af de øvrige kategorier.

Standarddefinitionen bruges ved migrering, hvis et ældre standardkategori-record ikke har feltet `description`. Hvis feltet findes – også som tom tekst – bevares brugerens valg.
