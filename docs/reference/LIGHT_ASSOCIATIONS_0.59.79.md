# Lystilhørsforhold i 0.59.79

## Grundregel

Et lampested repræsenterer én tændt elektrisk udgang og har derfor højst ét synligt tilhørsbogstav. Flere fysiske afbrydere kan dele samme bogstav, når de indgår i korrespondance eller krydsning.

Hvis ét fysisk lampeudtag skal levere to uafhængigt tændte udgange, oprettes to lampesteder. Det gør både afbryderrelationer, tændledere, PL-dåser og eksport entydige.

## Kanalidentitet

Hver fysisk afbryderbetjening identificeres internt som `<symbol-uid>:<kanalindeks>`. Bogstavet `a`, `b`, `c` osv. er en læsbar funktionsmærkning og ikke relationens tekniske identitet. Derfor kan bogstaver ændres uden at blande kanalrækkefølgen i kroneafbrydere, 4-tryk og kombisymboler.

## Arbejdsgang

1. Vælg en afbryder.
2. Vælg den ønskede række i kanaloversigten og dobbeltklik eller vælg `Redigér valgt betjening…`.
3. Klik et eller flere lampesteder på planen. Blå er valgt, turkis er ledig, og orange flyttes fra en anden tænding.
4. Tryk `Enter` for at gemme hele sessionen som én handling eller `Esc` for at gendanne udgangspunktet.

En omtilknytning erstatter lampestedets tidligere bogstav. Den opretter aldrig en skjult flerbogstavsrelation.

## Projektkontrol

Projektkontrollen rapporterer lampesteder uden relation, afbryderkanaler uden lampesteder, relationer uden en gyldig afbryderkanal og ældre data med flere bogstaver på ét lampested.
