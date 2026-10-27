# Kabelkategorier og visuelle lag 0.50.18

## Formål

Kabler kan nu grupperes efter anvendelse i stedet for kun efter den tekniske type **Kabel / Patchkabel / Ledning**. Kategorien bruges både til hurtigt overblik og som et egentligt underlag i projektets lagstruktur.

Standardkategorierne er:

- Stikkontakter
- Udendørs stikkontakter
- Udendørs lys
- Lampesteder
- Spots
- Ladeboks
- Hvidevarer / faste forbrugere
- Data / netværk
- Øvrige

## Visuel stil

Hver kategori har én fælles **farve** og **kontur/linjetype**: fuldt optrukket, stiplet, prikket eller streg-prik. Ændres en kategoris stil, opdateres alle kabler i den kategori.

Kategorier kan oprettes, omdøbes og slettes. Slettes en kategori, flyttes dens kabler til **Øvrige**.

## Lag

Et kabel beholder fortsat sin tekniske basis-type internt, men vises på et kombineret kategori-lag, eksempelvis:

`EL-KABLER-KAT-LIGHT-POINTS`

Dermed kan en kategori vises/skjules direkte i **Lag**-panelet. Menuen **Vis → Kabelkategorier** ændrer de samme lagtilstande og er derfor ikke kun et midlertidigt grafisk filter.

Ved DXF-output oprettes tilsvarende kategori-lag. PDF/print respekterer også kategoriens lagtilstand, farve og linjetype.

## Projektformat

Nye felter:

- `CablePlacement.cable_category`
- projektfeltet `cable_categories` med id, navn, farve og linjetype

Synlighed gemmes som hidtil i `layer_visibility`, nu også med kategori-lag. Ældre projekter får automatisk kategorien **Øvrige**. Eksisterende individuelle kabelfarver ændres ikke alene ved åbning; de overtages først af kategoristilen, når brugeren aktivt ændrer/tilknytter kategorien.
