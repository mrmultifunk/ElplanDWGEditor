# PL-lederfordeling 0.50.9

## Ren Wago-sløjfe i PL-dåsen

En Wago kan nu enten være forbundet til lampeudtaget eller kun fungere som en intern samling/sløjfe i PL-dåsen.

I **Redigér Wago-samling** findes valget **Forbind Wago til lampeudtaget med én bro**:

- **Slået til:** Wago'en er eksklusiv for funktionen. Alle ledere med funktionen går gennem Wago'en, og kun én bro går til lampeudtaget.
- **Slået fra:** kun de afkrydsede ledere går i Wago'en. Der tegnes ingen bro til lampestedet, og Wago'en bruger ingen terminalplads i lampeudtaget.

Løse ledere kan vælges direkte i Wago-editoren. De får den valgte elektriske funktion, men ved ren sløjfe bliver de i Wago'en og går ikke videre til lampestedet.

## Direkte grafisk tilslutning

En leder kan trækkes eller klikkes direkte på Wago-blokken. Programmet føjer så lederen til netop denne samling. Højreklik på en leder giver desuden **Sløjf leder i Wago uden lampested…**, så en ren sløjfe kan oprettes uden først at forbinde lederen til en fysisk terminal.

## Terminal- og artikelkontrol

En ren Wago-sløjfe tæller ikke i lampestedets terminalbelastning. Wago-portbehovet beregnes som:

- Wago → lampeudtag: antal kabelledere + 1 bro
- ren Wago-sløjfe: kun antal kabelledere

WAGO 221-artikelforslaget følger samme regel.

Hvis en ren Wago-sløjfe fjernes, frigøres dens medlemsledere og bliver løse i PL-dåsen; de flyttes ikke automatisk til lampestedet.

Tændingsledere der kun ligger i en ren Wago-sløjfe opfylder heller ikke lampestedets krav om en tændingsleder frem til den fysiske tændingsklemme.

## Projektdata

`pl_box_splices` har fået feltet `connects_to_outlet`. Standardværdien er `true`, så alle eksisterende projekter åbnes med samme montagefortolkning som før.
