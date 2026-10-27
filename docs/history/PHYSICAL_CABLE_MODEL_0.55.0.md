# Fysisk kabelmodel 0.55.0

## Formål
Tidligere kunne ét `CablePlacement` repræsentere en hel sløjfe gennem flere lampesteder. Det gjorde individuel kabeltype, BOM-artikel, længde, PL-ben og senere redigering unødigt komplekst. 0.55.0 gør den fysiske virkelighed til den primære model: ét kabelobjekt går mellem højst to installationspunkter.

## Model
- `circuit_id`: logisk gruppe/kreds, fælles for kabelstrengen.
- `route_chain_uid`: teknisk kobling mellem fysiske kabler oprettet i samme tegnehandling.
- `uid`: stabil identitet for det enkelte fysiske kabel og nøgle til BOM-artikelbinding.
- `cable_id`, `cable_spec`, `orthogonal`, `points`: individuelle egenskaber for det fysiske kabel.
- `symbol_connections`: højst to forbindelser og kun ved kabelrutens endepunkter i den nye model.

## Tegning
Brugeren må fortsat klikke flere installationspunkter i én arbejdsgang. Den midlertidige tegnerute kan derfor være flerpunkt, men ved afslutning splittes den før persistence. Alle segmenter tilføjes med én `AddCableBatchCommand`, så Undo stadig føles som én tegnehandling.

## BOM
`cable_instance_articles` bindes til fysisk kabel-UID. Hvert kabel har sin egen beregnede længde og artikel, hvorefter BOM kan aggregere samme artikel til meter eller hele ruller. Dette gør det muligt at have fx 5G1,5 frem til et lampested og 3G1,5 videre uden afsnits-overrides.

## PL-dåser
Et gammelt gennemgående kabel kunne give `before` og `after` ved samme PL. Efter migration peger hver side i stedet på sit eget kabel-UID med `leg=endpoint`. Indføringer, lederfordeling og Wago-medlemmer migreres efter samme mapping.

## Legacy-migration
`split_cable_into_physical_segments()` opdeler gamle kabler ved symbolforbindelser og materialiserer gamle `route_section_modes`/`spec_section_overrides`. Første segment beholder gammel UID af hensyn til eksisterende referencer; øvrige segmenter får nye UID'er. Projektmodellen remapper de PL-referencer, der flyttes til nye segmenter.

Kabel-ID'er fra den gamle fil reserveres inden split, så en migration af `K01` ikke opretter et nyt `K02`, hvis `K02` allerede findes. En fælles artikelbinding kopieres kun, når den gamle kabeltype var entydig.

## Kompatibilitet
Legacy-afsnitsfunktionerne findes fortsat som kompatibilitetslag og migrationshjælp, men den normale 0.55.0-GUI skjuler afsnitspanelet: det valgte objekt er allerede det fysiske afsnit.
