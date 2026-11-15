# Lampesteder med flere udgange i 0.59.80

## Fysisk objekt og logiske tændinger

Et lampested er fortsat ét fysisk objekt med én position, én PL-dåse, ét sæt kabelindføringer og én artikel-/styklistebinding. Objektet kan nu indeholde flere logiske udgange, eksempelvis `Pendel` og `Spots`. Hver udgang har højst ét tilhørsbogstav.

Det undgår overlappende symboler og fordoblede BOM-mængder, samtidig med at tændledere og afbryderkanaler kan beskrives entydigt.

## Arbejdsgang

1. Vælg lampestedet.
2. Vælg `+ Tilføj tænding` i Egenskaber.
3. Dobbeltklik på en udgang for at give den et tydeligt navn.
4. Start lystilknytning fra den ønskede afbryderkanal.
5. Klik lampestedet og vælg den relevante udgang.
6. Gem hele sessionen med `Enter`, eller annullér med `Esc`.

Et lille antal på symbolet viser, at lampestedet har flere udgange. Den kompakte mærkning viser eksempelvis `T1:a · T2:b`.

## PL-dåse, spots og eksport

PL-dåsens lederkrav samler tilhørsbogstaverne fra alle udgange, men selve dåsen og dens kabelindføringer oprettes kun én gang. En spotgruppe kan følge én bestemt udgang og arver kun dennes bogstav.

PDF- og CAD-mærkning viser alle udgange. BOM og Excel behandler lampestedet som én fysisk forekomst, så artikelantal ikke påvirkes af antallet af logiske tændinger.

## Projektformat

`light_outputs` er en liste af poster med felterne `id`, `name` og `association`. Det gamle `associations`-felt gemmes fortsat med første udgangs bogstav for bagudkompatibilitet. Ved indlæsning migreres gamle flerbogstavsdata til én udgang pr. bogstav.
