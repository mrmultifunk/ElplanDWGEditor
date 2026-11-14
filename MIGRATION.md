## 0.59.75 → 0.59.76

- Projektformat, symbolplaceringer, kabler, artikelbase, prisbog og styklister er uændrede. Eksisterende projekter åbnes direkte uden migrering.
- Optimeringen ændrer kun, hvornår grafik og afledte kabelspor genberegnes under symboltræk; de gemte koordinater og fysiske kabelpunkter er fortsat autoritative.
- Låste symboler følger samme sikkerhedsregel som før, men brugerfladen viser nu årsagen, når en sletning afvises.
- GitHub Actions-workflowet er fjernet fra repositoryet. Det påvirker ikke programmet eller lokale tests.

## 0.59.74 → 0.59.75

- Projektets PL-lampesteder kan nu indeholde det valgfrie felt `pl_field_record` med PWA-dåsens stabile id, tekst for de seks indføringer, noter, fotoadresser og markører.
- Feltregistreringen er bevidst adskilt fra `pl_box_wiring` og `pl_box_splices`. Opgradering, hentning og opdatering fra PWA'en ændrer derfor ikke eksisterende lederfunktioner, lampeudtagsklemmer eller WAGO-samlinger.
- Eksisterende projekter kræver ingen migrering. Feltet oprettes først, når en bruger aktivt knytter en PWA-registrering til en PL-dåse.
- Serveradresse og API-token er lokale programindstillinger. Tokenet skrives ikke i projektfil, PDF, Excel, CSV eller andre eksporter.
- Integrationens API-kald er read-only. Elplan sender ingen projekt- eller lederdata tilbage til PWA'en.
- Artikelbase, prisbog, styklister, kabelmodel og OneDrive-placering er uændrede.

## 0.59.73 → 0.59.74

- Projektformatet er fortsat bagudkompatibelt. De to nye standardkategorier `Udligning / beskyttelsesleder` og `Stikledning / hovedledning` føjes én gang til kategorilisten i projekter gemt før 0.59.74.
- Eksisterende kabelkategorier, farver og linjetyper ændres ikke. Når projektet først er gemt i 0.59.74, kan de nye kategorier også slettes eller tilpasses uden at blive gendannet ved næste åbning.
- `Målertavle` og `Hovedjordforbindelse` er nye vektorsymbolkoder og kræver ingen ændring af eksisterende symbolplaceringer.
- De nye 1G- og 4X10-profiler påvirker kun nye eller redigerede kabelvalg. Eksisterende kabelbetegnelser og lederfordelinger omskrives ikke.
- Artikelbase, prisbog, styklister og OneDrive-placering er uændrede.

## 0.59.72 → 0.59.73

- Projektformat, artikelbase, prisbog og globale styklister er uændrede.
- `Type/kategori` beregnes ved visning og eksport ud fra eksisterende artikelmetadata og styklisteroller; der skrives ingen nye obligatoriske projektfelter.
- Eksisterende projekter og OneDrive-baserede artikeldata kan åbnes direkte uden migrering.
- Excel-filer får én ekstra kolonne. Eksisterende Excel-/CSV-import påvirkes ikke, fordi BOM-eksport ikke bruges som autoritativ artikelimport.
- Gemte symbolkoordinater og størrelser ændres ikke. `3F+N+PE` beholder sit historiske væganker på `1,48 × size`; kun den synlige grundform og dens kropsport forskydes, så vægjusteringen matcher de øvrige stikkontakter.
- Kabler, der er tilknyttet `3F+N+PE`-symbolets kropsport, følger automatisk den korrigerede synlige tilslutning. Der kræves ingen manuel projekt- eller databasemigrering.
- Interne symbolmærkninger ændrer kun rendering og gemmer ingen nye projektfelter.

## 0.59.71 → 0.59.72

- Projektformatet er uændret, og eksisterende projekter kan åbnes direkte.
- Den globale artikelbase opgraderes automatisk til format v3. Manglende pakningsfelter udledes forsigtigt af den eksisterende `unit` og, for kabelruller, `package_length_m`.
- Artikelimport/-eksport bruger format v4. Ældre JSON- og CSV-filer kan stadig importeres; nye pakningsfelter er valgfrie.
- Prisbogens format er uændret. Eksisterende manuelle og automatiske priser bevares.
- Styklistebibliotekets containerformat hæves til v5, men eksisterende styklister og artikelreferencer normaliseres uden manuel konvertering.
- OneDrive-/synkroniseret artikelplacering fortsætter uændret; migreringen sker i den valgte globale datamappe.

## 0.59.70 → 0.59.71

- Projektformat, symbolplaceringer og artikeldata er uændrede; eksisterende projekter kan åbnes direkte.
- Ændringen gælder kun tegningen af den interne `3N`-mærkning på `socket_3fn`. Gemte rotationer og symbolkoordinater ændres ikke.
- Ingen database-, artikeldata- eller OneDrive-migrering er nødvendig.

## 0.59.69 → 0.59.70

- Projektformat, rum, styklister og artikeltilknytninger er uændrede.
- Prisbogens format opgraderes automatisk fra v4 til v5. Gamle automatiske WAGO-webshopestimater fjernes, fordi de kan være for hele forpakningen; eventuelle manuelle priser bevares.
- WAGO-prisestimater i den globale artikelbase opdateres automatisk til de indbyggede stykpriser. Andre artikelposter og brugerrettelser berøres ikke.
- Næste webshopopdatering henter nye observationer med den forbedrede pakningsnormalisering. Ingen manuel database- eller OneDrive-migrering er nødvendig.

## 0.59.68 → 0.59.69

- Projektformat, rumgeometri, artikelbase, prisbog og styklister er uændrede.
- BOM pr. rum beregnes ved eksport fra de eksisterende rum og artikeltilknytninger; der gemmes ingen nye projektfelter.
- Eksisterende ekstra BOM-rum og kabelmængder bevares og behandles efter samme regler som i Excel-eksporten.
- Ingen database- eller OneDrive-migrering er nødvendig.

## 0.59.67 → 0.59.68

- Projektformat, artikelbase, prisbog og styklister er uændrede; eksisterende projekter kan åbnes direkte.
- BOM-PDF'en beregnes fra den eksisterende BOM og gemmer ingen nye projektdata.
- Det globale valg mellem inkl. og ekskl. moms bruges kun til visning og output; autoritative priser gemmes fortsat ekskl. moms.
- Ingen database- eller OneDrive-migrering er nødvendig.

## 0.59.66 → 0.59.67

- Projektformatet og rumdata er uændrede; eksisterende projekter kan åbnes direkte.
- Patchen ændrer kun output-renderingen og bruger de eksisterende felter `rooms`, `room_labels_visible`, `room_codes_visible` og `room_boundaries_visible`.
- Ingen database-, artikeldata- eller OneDrive-migrering er nødvendig.

## 0.59.65 → 0.59.66

- Projektformatet er uændret; eksisterende projekter kan åbnes direkte.
- Problemnavigatoren og forslagssystemet arbejder kun på den lokale redigeringskopi i PL-dialogen. Data gemmes først ved `Anvend` eller `OK` som hidtil.
- Sikre forslag er forhåndsvalgt i previewet, men anvendes aldrig uden brugerens godkendelse. Forslag mærket `Kontrollér` er ikke forhåndsvalgt.
- Eksisterende lederfordelinger, Wago-samlinger og gennemsløjfningsdestinationer ændres ikke automatisk.
- Brun leder foreslås kun som et manuelt kontrolpunkt; programmet antager ikke, at den er fast fase.
- Der kræves ingen database- eller OneDrive-migrering.

## 0.59.64 → 0.59.65

`pl_box_splices` kan nu indeholde de valgfrie felter `conductor_role`, `destination_light_uid` og `destination_association`, når `connects_to_outlet` er `false`. Ældre projekter åbner uden datatab. Eksisterende tænd-/mellemledersamlinger uden et stabilt destinations-id ændres ikke automatisk, men markeres i montagekontrollen, indtil brugeren vælger det korrekte lampested.

Mellemledere bruger funktions-id'erne `traveller:<tilhørsbogstav>:1` og `traveller:<tilhørsbogstav>:2`. Ældre builds kender ikke disse nye identiteter og bør derfor kun bruges som rollback på en projektkopi, hvis nye mellemledersamlinger allerede er gemt.

## 0.59.16

Projektformatet får ét valgfrit topniveau-felt: `placement_bom_room_additions`. Det indeholder kun additive rum-id'er pr. symbol-UID og ændrer ikke `Placement`, rumgeometri, kabelmodel eller artikelbindinger. Ældre 0.59.15 kan ignorere feltet og bevarer det ved normal roundtrip, så rollback er fortsat praktisk.

## 0.59.11 → 0.59.12

Ingen datamigration. Rumfilteret i BOM beregner symbol-/Wago-bidrag fra placering og kabelmængder fra den faktiske geometri inde i rumpolygonerne. Der gemmes ingen rumfordeling i BOM-data. Artikeldatabasens nye WAGO/P100-data er kernedata og påvirker ikke projektformatet. Et projekt fra 0.59.12 kan derfor åbnes i 0.59.11; et eventuelt artikelvalg af en ny P100-type vil blot fremstå som et ukendt artikelnummer i en ældre database, hvis den gamle build ikke har samme kernedata.

## 0.59.10 → 0.59.11

Ingen datamigration. BOM-rumfelt, sortering og billed-hover beregnes kun i UI/eksport ud fra eksisterende rum og artikelbindinger. Projektformat, BOM-bindinger, kabler og PL-data er uændret; 0.59.10 kan bruges som direkte rollback.

## 0.59.9 → 0.59.10

Ingen datamigration. 0.59.10 gør den allerede understøttede `connects_to_outlet = false` Wago-tilstand til en tydelig **Samlemuffe / sløjfe**-arbejdsgang i UI'et. Projektformat, Wago-ID, medlemsreferencer, artikelnummer og bro/sløjfe-flag er uændret. Et projekt gemt i 0.59.10 kan åbnes i 0.59.9; brug gerne en kopi af projektfilen under test.

## 0.59.8 → 0.59.9

Ingen datamigration. Patchen ændrer kun Wago-arbejdsgangen og PL-grafikken; eksisterende `pl_box_splices`, Wago-artikler, lederfordeling og projektfelter gemmes i samme format. Et projekt gemt i 0.59.9 kan derfor åbnes igen i 0.59.8, hvis denne UI-patch skal rulles tilbage. Som altid anbefales en kopi af projektfilen under test af nye builds.

## 0.59.7 → 0.59.8

Ingen datamigration. 0.59.8 er en isoleret PL-layoutpatch. Projektformat, Wago-data og lederfordeling er uændret, så det er sikkert at lukke projektet og starte 0.59.7 igen, hvis layoutpatchen giver problemer. Gem gerne en kopi af projektfilen som almindelig forsigtighed ved test af nye builds.

## 0.59.6 → 0.59.7

Ingen projektschemamigration. Ændringen er udelukkende responsiv tegning af kabelindføringskortene i PL-lederfordelingen; eksisterende kabelmærkninger, PL-forbindelser og lederplaner bevares uændret.

## 0.59.5 → 0.59.6

Ingen projektschemamigration. Ændringen vedrører kun forslag til ekstra kabelmærkning. Eksisterende kabel-ID, gruppe/kreds og ekstra mærkninger bevares uændret.

## 0.59.4 → 0.59.5

Ingen tvungen projektmigration. `RoomPlacement.color` fandtes allerede og bevares for eksisterende rum; nye rum får blot en farvenuance fra den nye palette. Rum-snap ændrer kun editorens interaktion og ikke den gemte geometri, medmindre brugeren aktivt tegner eller flytter et rumhjørne. EL-RUM forbliver udelukket fra symbol-/kabelsnap.

## 0.59.3 → 0.59.4

Ingen projektschemamigration. Versionen retter kun kabelpanelets runtime-integration efter overgangen fra separat kabel-dock til det fælles Inspector-panel.

## 0.59.2 → 0.59.3

Ingen projektdatamigration. Rumgeometrien gemmes uændret. Versionen ændrer kun interaktionen med rumkonturer og tilføjer blød vandret/lodret tegne-/redigeringshjælp.

## 0.59.1 → 0.59.2

Ingen projektdatamigration. Ændringen rydder kun op i kabel-egenskabs-/tegnepanelet. Eksisterende kabel-ID, gruppe/kreds, Ekstra mærkning, artikler og geometri bevares. Den tidligere projektdefault `cable_label` bruges ikke længere til nye kabler; nye kabler starter uden Ekstra mærkning, så mærkning fortsat kræver en aktiv brugerhandling.

## 0.59.0 → 0.59.1

Ingen projektdatamigration. 0.59.1 tilføjer kun en direkte editor for det eksisterende `CablePlacement.label` / **Ekstra mærkning**, når et kabel er valgt. Forslag gemmes ikke automatisk, og den nye handling kan ikke ændre kabel-ID, gruppe/kreds, kabeltype, geometri, artikel eller BOM.

## 0.58.4 → 0.59.0

Ingen projektdatamigration. Grafisk kabelmærkning bruger udelukkende det eksisterende `CablePlacement.label` / **Ekstra mærkning**. Forslag gemmes ikke, og kabel-ID, gruppe/kreds, kabeltype, geometri, artikel- og BOM-bindinger ændres ikke af mærkningsarbejdsgangen.

## 0.58.3 → 0.58.4

Ingen projektdatamigration. Eksisterende `rooms[].points` bruges uændret; 0.58.4 tilføjer kun tydeligere GUI-adgang til at redigere polygonens hjørner efter oprettelse.

## 0.58.2 → 0.58.3

Ingen projektmigration. Rumtekst og rumafgrænsning kan nu vises uafhængigt; det valgfrie `room_labels_visible` antages `true`, hvis feltet ikke findes. Den tidligere semiautomatiske symbolmærkning er fjernet fra brugerfladen. Ny rumbaseret kabelmærkning skriver kun til kabellets eksisterende `label` / **Ekstra mærkning** og ændrer ikke kabel-ID, gruppe/kreds, geometri eller BOM-data.

## 0.58.1 → 0.58.2

Ingen projektmigration. 0.58.2 strammer kun snap-isoleringen mellem `EL-RUM` og CAD-vægge.

## 0.58.0 → 0.58.1

Ingen projektmigration. 0.58.1 er en runtime-fejlrettelse for rumdialoger og toast-feedback.

## 0.57.5 → 0.58.0

Projektformatet udvides med den valgfrie liste `rooms`. Hvert rum gemmer `uid`, `name`, `code`, polygonens CAD-koordinater i `points`, den uafhængige tekstposition `label_x`/`label_y` samt visningsfarve. Ældre projekter uden `rooms` åbner uændret med et tomt rumlag. `room_boundaries_visible` er et valgfrit projektvalg; mangler det, er afgrænsninger skjult som standard.

Eksisterende symbol-, kabel-, PL- og BOM-data ændres ikke. Rummets tilhørsforhold til symboler beregnes geometrisk ved behov og gemmes derfor ikke som en skrøbelig symbol→rum-reference.

## 0.57.4 → 0.57.5

Ingen projektschemamigration. Ændringen er udelukkende præsentation af eksisterende kabel-ID og ekstra mærkning i hoverkortet.

## 0.57.3 → 0.57.4

Ingen projektschemamigration. Ændringerne vedrører kun PL-hoveridentifikation og artikel/BOM-brugerfladen. Eksisterende symbolartikler, styklister, kabelartikler og globale artikeldata indlæses uændret.

## 0.57.2 → 0.57.3

Ingen projektschemamigration. Ændringerne er udelukkende præsentations-/hoveradfærd. Kabelkategori-chipbjælken vises ikke længere på canvas; kabelkategoriers synlighed og projektdata bevares uændret.


## 0.57.1 → 0.57.2

Ingen projektschemamigration. Navigatorens maskinlokale standard sættes én gang til skjult ved første start af 0.57.2; brugeren kan derefter slå den til igen via Vis-menuen. Ekstra kabelmærkning forbliver gemt i projektet, men er ikke længere en permanent plantegningslabel.
# 0.57.1
Ingen projektschemamigration. Ændringerne er rene layout-/præsentationsændringer i PL-dåsekonfiguratorens lederfordeling. Eksisterende PL-forbindelser, Wago-samlinger og lampeudtagstyper indlæses uændret. Ved næste Gem opdateres kun versionsstemplet til 0.57.1.

# 0.57.0
Ingen projektschemamigration. Kabel-flow, selection-pulse, snap-feedback, gruppesporing, mini-kort, smooth zoom, smart hover, toasts samt PL-dåsens eksploderede visning/forbindelsesanimation er rene præsentationsfunktioner. Gruppe-/trace-state, mini-kortets viewport, hover-state og animationer gemmes ikke i projektfilen. Eksisterende PL-lederforbindelser og den manuelle forbindelsesmodel er uændret. Ved næste Gem opdateres kun versionsstemplet til 0.57.0.

# 0.56.2
Ingen projektmigration. Den nye Nordtronic-profil bruger det eksisterende `lamp_outlet_type`-felt og de eksisterende generiske PL-lederfunktioner. Nye funktions-id'er `com` og `dimmed_out` gemmes kun, hvis brugeren selv tildeler dem. Lampeudtagets nye BOM-del er valgfri og kræver ingen binding i eksisterende projekter. Ved næste Gem opdateres kun versionsstemplet til 0.56.2.

# 0.56.1
Ingen projektmigration. Kabelkategori-chips, grafisk kabel-flow, den opdaterede PL-montagegrafik og hover/selection-animationer er præsentationsfunktioner. De bruger eksisterende kabelkategorier, fysiske kabler og PL-lederdata som eneste datakilde. Ved næste Gem opdateres kun det almindelige versionsstempel til 0.56.1.

# 0.56.0
Ingen projektmigration. Arbejdsgangslinje, kabel-selection, inspector-summary og gruppefokus er præsentations-/GUI-funktioner. Der gemmes ingen fokus-, selection- eller workflow-data i projektfilen. Ved næste Gem opdateres kun det almindelige versionsstempel til 0.56.0.

# 0.55.2
Ingen projektmigration. Kabeltræk/ruteforløb er en rent afledt visning, som bygger gruppevise træer og ruter direkte af eksisterende fysiske `CablePlacement`-objekter og deres symboltilslutninger. Der gemmes ingen ekstra rute- eller træstruktur i projektfilen. Ved næste Gem opdateres kun det almindelige versionsstempel til 0.55.2.

# 0.55.0
0.55.0 ændrer kabelschemaets semantik: **ét kabelobjekt er ét fysisk kabel**. Nye valgfrie felter er `circuit_id` (gruppe/kreds) og `route_chain_uid` (sammenhæng mellem kabler tegnet som samme streng). `route_section_modes` og `spec_section_overrides` beholdes i dataklassen som legacy-kompatibilitet, men nye/migrerede fysiske kabler gemmer dem tomme; `orthogonal` og `cable_spec` er autoritative pr. kabel.

Ved åbning af projekter fra 0.54.x eller ældre splittes et flerpunkt-kabel automatisk mellem nabotilslutninger. Første segment beholder den gamle kabel-UID, mens efterfølgende segmenter får nye UID'er og ledige kabel-ID'er. Gamle PL-referencer (`pl_box_entries`, `pl_box_wiring`, `pl_box_splices[].members`) remappes fra `before/after` til det relevante nye kabels `endpoint`.

Gamle afsnitsvise kabeltyper og ruteføringsvalg materialiseres på de nye kabler. En fælles kabelartikel kopieres til alle nye segmenter, hvis kabeltypen var ensartet. Hvis det gamle kabel havde blandede kabeltyper, fjernes den tvetydige fælles kabelartikelbinding under migrationen, så brugeren kan vælge korrekt artikel pr. fysisk kabel.

Migreringen sker ved indlæsning, projektet markeres som ændret, og næste Gem skriver 0.55.0-format. Selve CAD-geometrien og den samlede kabelvej bevares.

# 0.54.3
Ingen projektmigration. 0.54.3 ændrer kun intern Qt-kodeopdeling og importstrategi. Projektdata, kabelafsnitsdata, PL-data, artikelbindinger og eksportformat er uændret i forhold til 0.54.2.

# 0.54.2
`CablePlacement` har fået det **valgfrie** felt `spec_section_overrides` til kabeltype pr. fysisk afsnit mellem to nabotilslutninger. Eksisterende projekter mangler feltet og åbner derfor uændret med tom liste; kabellets eksisterende `cable_spec` er fortsat global/default type.

Overrides bruger stabile symbol-UID/port-par på samme måde som `route_section_modes`. Et projekt ændres ikke blot ved at blive åbnet. Gemmes et projekt med afsnitsvise kabeltyper i en ældre programversion, kan metadataene gå tabt, selv om selve kabelgeometrien stadig kan ses.

# 0.54.1
Ingen projektmigration. Ændringerne vedrører kun QGraphicsView-zoom, rækkefølgen mellem visning og fit samt et maskinlokalt indlæsnings-overlay. Projektdata og eksportformat er uændret.

# 0.54.0
Ingen projektmigration. Global søgning, startside, progressive inspector-sektioner, toast-feedback, dialogfundament og tabeladfærd er udelukkende GUI-/arbejdsfladeændringer. Der gemmes ingen nye projektfelter.

Startsiden og panel-/dialogvalg er maskinlokale. Eksisterende projekter åbnes uden ændring.

# 0.53.0
Ingen projektmigration. GUI-moderniseringen ændrer ikke projektschemaet. Den samlede inspector og kontekstværktøjslinjen er kun arbejdsflade/UI.

Vinduesgeometri og docklayout gemmes i de maskinlokale app-indstillinger som `qt_window_geometry` og `qt_window_state`. De eksporteres ikke med `.elplancore` og indgår ikke i projektfiler. Et ældre lokalt docklayout kan blive erstattet af 0.53.0-standardlayoutet første gang den nye workspace-struktur bruges; **Vis → Nulstil panel-layout** kan altid gendanne standarden.

# 0.52.5
Ingen projektmigration. Fejlrettelsen vedrører kun Qt-signaldefinitionerne for kabel- og symbolgrafik. Projekter fra 0.52.3/0.52.4 kan åbnes direkte.

# 0.52.4

Ingen projektmigration er nødvendig. Ændringerne vedrører kun visning/rapportering af eksisterende `Placement.group` og `Placement.label` samt et mere skærmrobust layout i PL-dåsekonfiguratoren. Ingen nye felter gemmes i projektet.

# 0.52.3

`CablePlacement` har fået det **valgfrie** felt `route_section_modes` til lokal ruteføring mellem to fysiske nabotilslutninger. Eksisterende projekter mangler feltet og åbner derfor uændret med tom liste; kabellets eksisterende `orthogonal`-værdi er fortsat standard for hele ruten. Feltet skrives kun, når brugeren aktivt laver afsnitsvis ruteføring.

Overrides identificeres med symbol-UID/port-par og ikke polyline-indeks. Derfor kræves ingen migration af eksisterende `points` eller `symbol_connections`. Hvis projektet senere åbnes og gemmes i en ældre programversion, som ikke kender `route_section_modes`, kan de lokale ruteføringsmetadata gå tabt, selv om den allerede tegnede polylinegeometri fortsat kan være synlig.

# 0.52.2

Ingen projektmigration er nødvendig. Tændleder-overblikket er en afledt visning, der analyserer eksisterende `CablePlacement`, `symbol_connections` og `pl_box_wiring`. Der gemmes ingen separat global lederstatus; derfor kan gamle projekter straks få overblikket, så snart deres PL-lederplaner indeholder tændlederfunktioner.

# 0.52.1

Ingen projektmigration er nødvendig. Funktionen til at koble et eksisterende lampested på et eksisterende kabel bruger den allerede eksisterende `symbol_connections`-struktur på kablet. Når forbindelsen indsættes midt på en polyline, remappes eksisterende `point_index`-referencer automatisk. PL-dåsens eksisterende indføringsdata ændres ikke automatisk; det nye kabelben vises som ikke placeret, indtil indføring 1-6 vælges.

## 0.51.1 → 0.52.0 – Vedligeholdelse og kabelrutekonvertering

Der er **ingen nye obligatoriske projektfelter**. Tema-/hover-modulopdelingen og performance-cachen er interne programændringer.

Når brugeren aktivt ændrer et eksisterende kabel mellem **Ortogonal (90°)** og **Fri / diagonal** og trykker *Anvend ændringer*, konverteres selve centerlinjen nu. Det er en brugerinitieret redigering og gemmes som almindelige `points` + `orthogonal`; gamle projekter ændres ikke blot ved at blive åbnet. Fysiske `symbol_connections` remappes automatisk til de nye punktindekser.

## 0.51.0 → 0.51.1 – Flere Wago-samlinger pr. funktion

Der er ingen ændring af feltnavne eller filformat, men Wago-semantikken er udvidet. `pl_box_splices[].function` er ikke længere unik, så flere Wago'er kan have samme N/PE/L/tændingsfunktion. De gemte `members` på hver Wago bliver den autoritative fysiske medlemsliste.

Eksisterende projekter bevarer deres Wago-ID, artikel, bro/sløjfe-tilstand, position og gemte medlemmer. Projekter gemt af 0.50.7–0.51.0 har allerede fået de dengang automatisk samlede ledere skrevet ind i `members`, så de åbner med samme fysiske samling. Nye ledere til samme funktion føjes fra 0.51.1 ikke automatisk til en eksisterende Wago; de kan tilføjes manuelt til den ønskede samling.

Dark mode-indstillingerne fra 0.51.0 er fortsat maskinlokale og kræver ingen projektmigration.

## 0.50.22 → 0.51.0 – Mørkt udseende

Der er **ingen projektmigration og ingen ændring af projektschemaet**. Dark mode er en lokal arbejdsindstilling og må ikke påvirke den tekniske tegning.

- Eksisterende brugere fortsætter i **Lys**, indtil de aktivt vælger Mørk eller Følg Windows.
- `appearance_mode` og `dark_canvas` gemmes i de maskinlokale app-indstillinger og eksporteres/importeres ikke via `.elplancore`.
- Mørk CAD-baggrund ændrer kun skærmvisningen. Gemte farver på DWG, symboler, kabler, kategorier og tekst bevares uændret.
- PDF, print og PL-dåserapport forbliver papirbaserede med hvid side og de originale tekniske farver.
- Valget **Følg Windows** kan ændre det aktive tema ved et senere Windows-temaskift uden at skrive noget til projektfilen.

## 0.50.18 → 0.50.19 – Mellemkabel og Tændkabel

Ved åbning af et projekt fra før 0.50.19 tilføjes standardkategorierne `interconnect` (**Mellemkabel**) og `switch_cable` (**Tændkabel**) hvis de mangler. Eksisterende kategorier, farver og linjetyper bevares uændret. Når projektet efterfølgende er gemt i 0.50.19, behandles de som almindelige brugerredigerbare kategorier.

## 0.50.17 → 0.50.18 – Kabelkategorier

- Nyt kabelfelt `cable_category`. Mangler feltet, bruges kategorien **Øvrige**.
- Nyt projektfelt `cable_categories` med kategori-id, navn, farve og linjetype. Mangler feltet, oprettes standardkategorierne automatisk.
- Kategoriers synlighed gemmes i det eksisterende `layer_visibility` via kombinerede kategori-lag. Ældre `EL-KABLER`/`EL-LEDNINGER`/`EL-PATCHKABLER`-synlighed bruges som fallback, indtil en kategori har fået sin egen lagtilstand.
- Ældre kablers individuelle farve og linjetype bevares ved ren åbning/gemning. Når brugeren aktivt konfigurerer eller flytter dem til en kategori, overtager kategoriens fælles stil.

## 0.50.12 → 0.50.13 – Hover-overblik

Ingen datamigrering. Hover-popupperne læser eksisterende `pl_box_entries`, `placement_articles`, `placement_assemblies` og `cable_instance_articles` direkte.

## 0.50.10 → 0.50.12 – Fysisk PL-orientering og rapport

- Nyt placeringsfelt `pl_box_orientation` med værdierne 0, 90, 180 eller 270.
- Manglende felt migreres automatisk til 0°.
- Orienteringen ændrer kun den fysiske portvisning; eksisterende kabelindføringer, lederfordeling og Wago-data bevares.
- Ny A4-PDF-rapport kan eksporteres for alle PL-lampesteder i projektet.

## 0.50.9 → 0.50.10 – Kabelende-preview

Ingen datamigrering. 3G/5G/7G-lederpreviewet i fanen Kabelindføringer er rent grafisk og udledes ved visning fra eksisterende `cable_spec`.

## 0.50.7 → 0.50.9 – Wago med eller uden lampestedbro

Ingen manuel konvertering er nødvendig. Wago-samlinger har fået det valgfrie felt `connects_to_outlet`.

- Mangler feltet i et ældre projekt, fortolkes det som `true`, så den eksisterende 0.50.7-adfærd bevares: alle ledere med funktionen går gennem Wago'en og én bro går til lampeudtaget.
- Sættes feltet til `false`, er Wago'en en ren intern sløjfe. Kun de eksplicit gemte `members` går i samlingen, og der er ingen forbindelse til lampestedets terminal.

`article_no`, `position`, `members`, kabelreferencer og den øvrige lederplan bevares uændret.

## 0.50.6 → 0.50.7 – Eksklusiv Wago-semantik

Ingen manuel filkonvertering er nødvendig. Når et projekt fra 0.50.4–0.50.6 indeholder en Wago på en funktion, samler 0.50.7 automatisk **alle aktuelt tildelte ledere med samme funktion** i denne Wago. Det betyder, at en tidligere kombination af delvis Wago-samling + direkte terminalledere bliver fortolket som én samlet Wago med én bro til udtaget.

Tomme, planlagte Wago-samlinger er nu tilladt. Eksisterende `article_no` og `position` bevares. Hvis den eksisterende artikel efter den eksklusive samling er for lille, markeres det i Montagekontrol og ved næste tilslutning tilbydes en passende større WAGO 221-variant.

## 0.50.5 → 0.50.6 – Manuel Wago-position

Ingen manuel migrering er nødvendig. Eksisterende Wago-samlinger uden `position` placeres automatisk som tidligere. Når brugeren trækker en Wago i PL-dåsen, gemmes et valgfrit felt `position: {"x": ..., "y": ...}` med relative koordinater mellem 0 og 1. Feltet bevares ved efterfølgende Wago-redigering.

## 0.50.4 → 0.50.5 – Wago-artikel på BOM

Ingen manuel migrering er nødvendig. Eksisterende `pl_box_splices` uden artikelnummer bevares og vises som **manglende artikel** i BOM, indtil samlingen redigeres. Nye/redigerede Wago-samlinger kan gemme feltet `article_no`, f.eks. `221-413` eller `221-415`.

## 0.50.3 → 0.50.4 – PL Wago-samlinger

Lampesteder kan nu indeholde `pl_box_splices`. Ældre projekter kræver ingen manuel migrering; manglende felt fortolkes som en tom liste. Wago-data refererer til de samme stabile kabel-/lederidentiteter som `pl_box_wiring` og fjernes automatisk, hvis den refererede leder ikke længere findes eller har skiftet funktion.

# 0.50.0 → 0.50.1

Ingen manuel migration er nødvendig. 0.50.1 ændrer kun den grafiske præsentation og hit-zoner i PL-dialogens **Lederfordeling**. Eksisterende `pl_box_entries`, `pl_box_wiring`, kabelreferencer, lederfunktioner, tilhørsforhold og `lamp_outlet_type` bevares uændret.

# 0.49.1 → 0.50.0

Ingen manuel migration er nødvendig. Eksisterende lampesteder får standardtypen `generic`, så den eksisterende 0.49.x-lederplan kan åbnes uændret. Når brugeren vælger **LK klassisk** eller **LK Wiser / dæmpbar** og gemmer, tilføjes kun feltet `lamp_outlet_type` til lampestedet.

`pl_box_entries`, `pl_box_wiring`, kabel-ID/UID, lederfunktioner og tilhørsforhold bevares. Udtagstypen er en fysisk/visuel terminalprofil; den omskriver ikke de gemte elektriske funktioner. Kopiering af et lampested beholder valgt lampeudtagstype, men nulstiller fortsat de konkrete kabelindføringer og lederforbindelser.

# 0.49.0 → 0.49.1

Ingen projektmigration er nødvendig. 0.49.1 ændrer kun den grafiske editor for eksisterende `pl_box_entries` og `pl_box_wiring`. Gemte kabelindføringer, lederfunktioner, tilhørsforhold og afbryderkanaler bevares uændret.

# 0.48.1 → 0.49.0

Ingen manuel projektkonvertering er nødvendig. Afbryderkanalernes stabile identitet udledes af eksisterende symbol-UID og kanalrækkefølge, og eksisterende `association_channels`/`pl_box_wiring` bevares. Kabellets eksisterende `label` bruges som ekstra mærkning i PL-dialogen.

# 0.48.0 → 0.48.1

Ingen manuel migration er nødvendig. Hvis et projekt allerede har en lederplan oprettet i 0.48.0 for et 7G-kabel, konverteres de gamle interne leder-id'er `num1..num6` ved indlæsning/reconciliation til **blå, brun, sort, grå, rød og hvid**. Gemte funktioner og noter bevares.

3G/5G-data ændres ikke. Kabelruter, PL-indføringer, artikler og BOM påvirkes ikke.

# 0.47.0 → 0.48.0

Ingen manuel migration er nødvendig. Eksisterende `pl_box_entries` bevares. Lederplanen (`pl_box_wiring`) starter tom i ældre projekter og gemmes først, når PL-konfiguratoren anvendes. Programmet kan på dialogtid udlede standardlederne fra 3G/5G/7G-kabelspecifikationen; dette ændrer ikke projektfilen før brugeren trykker Anvend/OK.

Eksisterende kabel-, artikel-, BOM- og lystilhørsforholdsdata ændres ikke.

# 0.46.2 → 0.47.0

Ingen manuel migrering er nødvendig. Eksisterende lampesteder får automatisk en tom PL-konfiguration. Eksisterende kabelruter bruges direkte til at finde de kabelben, der kan placeres i de seks indføringer. PL-data gemmes først, når brugeren konfigurerer et lampested.

Eksisterende projekt-, artikel-, BOM- og kabeldata ændres ikke.

# 0.46.1 → 0.46.2

Ingen automatisk omklassificering af eksisterende kabler udføres. Det er bevidst, fordi en CAT6/CAT7-specifikation også kan være et fast installationskabel og derfor ikke nødvendigvis er et patchkabel.

Nye patchkabler vælges som **Type = Patchkabel** og gemmes på `EL-PATCHKABLER`. Et eksisterende kabel kan markeres og ændres til **Patchkabel** med **Anvend kabeldata**. Alle øvrige kabeldata bevares.

# 0.46.0 → 0.46.1

Ingen projektmigration er nødvendig. Ved første opstart udvider kernedatabasen automatisk `articles.json` med den nye basisartikel 802184, hvis den ikke allerede findes. En eksisterende brugerredigeret artikel med samme artikelnummer bevares.

# 0.45.5 → 0.46.0

Ingen manuel migration er nødvendig. Ældre kabler uden `color`/`line_style` indlæses som rød og fuldt optrukket. Hurtig visning er en global brugerindstilling og ændrer ikke gemte projektlag. Patchpanel er et nyt symbol og kræver ingen konvertering af eksisterende projekter.

# 0.45.3

Ingen projekt- eller kernedatamigration er nødvendig. Første hurtige LK-synkronisering kan genbruge LK-artikler i `articles.json`, hvis deres `source_checked` er højst 7 dage gammelt. En ny cachefil oprettes automatisk i brugerdataområdet og er kun en performance-cache; den er ikke nødvendig for backup eller PC-flytning.

## 0.44.5 → 0.45.0

0.45.0 indfører en bevidst adskillelse mellem kernedata og projektdata. Ingen manuel konvertering er nødvendig.

- Ved åbning af et ældre projekt flyttes projektets indlejrede `article_catalog` til den globale artikelbase.
- Gamle `bom_assemblies` flyttes til det globale styklistebibliotek.
- Gamle `custom_symbols` flyttes til de globale programindstillinger.
- En legacy-kategori fjernes først fra projektets runtime-data efter en vellykket skrivning til kernedata. Hvis kernedatamappen ikke kan skrives, bevares den pågældende legacy-data i projektet.
- Projektets konkrete relationer `placement_articles`, `placement_assemblies` og `cable_instance_articles` forbliver i projektet.
- Ved næste gemning indeholder projektfilen ikke længere artikelbase, globale styklister eller custom-symbolbibliotek.
- DWG/DXF-linket kan fortsat være relativt. Projektpakke-import i 0.45.0 opretter automatisk en relativ reference mellem den udpakkede projektfil og CAD-kilden.

For flytning til en anden PC anbefales: eksportér først **kernedata** (`.elplancore`) og derefter de ønskede **projektpakker** (`.elplanproj`). Importér kernedata én gang på den nye PC og derefter de enkelte projektpakker.

## 0.44.4 → 0.44.5

Ingen manuel migrering er nødvendig. Eksisterende kabler beholder deres gemte `orthogonal`-flag. Den nye standard **Fri / diagonal** gælder kun nye kabler, medmindre brugeren aktivt ændrer et eksisterende kabel og anvender ændringen. Kabelpunkter, symboltilslutninger, artikler, BOM-data og længdekalibrering ændres ikke.

## 0.44.2 → 0.44.4

Ingen manuel migrering er nødvendig. 0.44.4 ændrer kun hvordan den allerede beregnede kosmetiske parallelbane afleveres til Qt-renderingen. Projektdata og kabelgeometri ændres ikke.

## 0.44.1 → 0.44.2

Ingen manuel migrering er nødvendig. 0.44.2 ændrer kun den kosmetiske parallelvisning. Gemte kabelpunkter, tilslutninger, artikler, BOM-data og beregnede længder ændres ikke. Fysiske kabelankre bruges nu som visuelle fan-out-grupper.

## 0.44.0 → 0.44.1

Ingen manuel migrering er nødvendig. 0.44.1 ændrer kun den kosmetiske detektion af fælles kabelruter. Gemte kabelpunkter, tilslutninger, længder, artikler og BOM-data ændres ikke.

## 0.43.3 → 0.44.0

Ingen manuel migrering er nødvendig. 0.44.0 ændrer kun kabelvisning og snap-adfærd. Parallelle baner, ×N-mærker og fokus gemmes som globale programindstillinger; de eksisterende kabelpunkter, symboltilslutninger, kabelartikler, BOM-data og længder ændres ikke. Snap til eksisterende kabelrute bruger den gemte logiske centerlinje og opretter ikke automatiske artikel- eller kabeltilknytninger.

## 0.43.2 → 0.43.3

Ingen manuel migrering er nødvendig. Kabeldataformatet er uændret. Versionen ændrer kun efterredigering af kabelgeometri: fysiske symbolankre forbliver låste, mens frie ruteknæk igen kan flyttes frit med automatisk indsættelse af nødvendige 90°-doglegs.

## 0.43.1 → 0.43.2

Ingen manuel migrering er nødvendig. Fysiske kabeltilslutninger behandles nu som låste symbolankre. Hvis et projekt blev gemt i 0.43.0/0.43.1 efter at et anker var blevet trukket væk under kabelredigering, reparerer 0.43.2 automatisk punktet tilbage til den registrerede symbolport ved åbning. Kabel-ID, type, artikeltilknytning, længde og øvrige forbindelser bevares.

## 0.43.0 → 0.43.1

Ingen manuel migrering er nødvendig. 0.43.1 tilføjer kun den interaktive kabel-assistent og ændrer ikke strukturen for kabelruter, symboltilslutninger, artikler eller BOM. Eksisterende 0.43.0-projekter kan åbnes direkte.

## 0.42.5 → 0.43.0

- Ingen manuel migrering er nødvendig. Eksisterende kabler med `start_symbol_uid`/`end_symbol_uid` konverteres automatisk til den nye liste `symbol_connections`, når projektet indlæses.
- Samme kabel kan herefter have flere fysiske tilslutninger undervejs. Kabel-ID, kabeltype, artikelbinding og længde bevares på det samlede kabelobjekt.
- De gamle start-/slutfelter beholdes i projektfilen som kompatibilitetsfelter og synkroniseres med første/sidste tilslutning.
- Eksisterende `cable_instance_articles` ændres ikke; en artikel, der var tilknyttet et kabel, er fortsat tilknyttet det samme kabel efter migreringen.
- LK-produktfotos påvirker ikke projektformatet; foto-URL udledes ved runtime og billeder caches lokalt.

## 0.42.4 → 0.42.5

Ingen datamigrering er nødvendig. 0.42.5 retter kun en runtime-fejl i Artikler og BOM-dialogens antalsformatering. Eksisterende projekter, artikeltilknytninger, styklister og kabeltilknytninger bevares uændret.

## 0.42.3 → 0.42.4

- Ingen manuel projektmigrering er nødvendig.
- `cable_instance_articles` er fortsat det eksisterende instansbaserede felt; 0.42.4 gør blot tilknytningen tilgængelig direkte i Kabelværktøj.
- Et artikelvalg til et endnu ikke tegnet kabel er kun midlertidigt og gemmes først på det konkrete kabel-id, når kabelstrækket oprettes. Valget genbruges ikke automatisk.
- Projektformat/version er 0.42.4.

## 0.42.2 → 0.42.3

- BOM-tilknytninger er nu eksplicitte pr. fysisk symbol og pr. kabelstræk.
- Ældre typebaserede felter (`symbol_articles`, `symbol_assemblies`, `cable_articles`) kan ikke migreres sikkert til en bestemt fysisk forekomst, fordi de gamle data ikke fortæller, hvilken af fx 19 ens stikkontakter brugeren mente. Derfor anvendes de ikke automatisk i 0.42.3.
- De gamle felter bevares i projektdata som legacy-data; brugeren kan tilknytte de ønskede konkrete symboler/kabler igen i Artikler/BOM.
- Nye instansfelter: `placement_articles`, `placement_assemblies`, `cable_instance_articles`.
- Eksisterende kabler uden `uid` får automatisk et stabilt id ved indlæsning; id'et gemmes ved næste projektsave.
- Globale styklister ændres ikke og kan fortsat genbruges mellem projekter; det er kun valget af hvilken fysisk forekomst der bruger stykliste, som er projektafhængigt.
- Projektformat/version er 0.42.3.

## 0.42.1 → 0.42.2

- Ingen manuel projektmigrering er nødvendig.
- Ændringerne vedrører GUI-layout, fælles styling, kontroltegning og visuelt hierarki; projekt-, artikel-, BOM- og kabeldata er uændret.
- Eksisterende gemt vinduesgeometri og tabelkolonnebredder genbruges.
- Projektformat/version er 0.42.2.

## 0.42.0 → 0.42.1

- Ingen manuel projektmigrering er nødvendig.
- Ændringen vedrører kun visningen af op-/ned-pilene i Qt-talbokse.
- Projektformat/version er 0.42.1.

## 0.41.6 → 0.42.0

- Ingen manuel projektmigrering er nødvendig.
- Projektdata, artikelbindinger, kabler og globale styklister bruger samme felter som før; ændringerne er primært arkitektur, cache og fejllogning.
- Ved uventede runtime-fejl gemmes en roterende logfil under `%APPDATA%\ElplanDWGEditor\logs\elplan.log` på Windows.
- Den gamle Tkinter-frontend er isoleret som legacy-komponent og påvirker ikke normal Qt-brug.
- Projektformat/version er 0.42.0.

## 0.41.5 → 0.41.6

- Ingen manuel projektmigrering er nødvendig.
- Ændringerne er GUI-/temaændringer; projekt-, artikel- og styklisteformat er uændret.
- Eksisterende brugerindstillinger for vinduer og kolonnebredder genbruges.
- Projektformat/version er 0.41.6.

## 0.41.4 → 0.41.5

- Ingen manuel projektmigrering er nødvendig.
- Artikelvælgeren og Standardbiblioteket er internt skiftet til modelbaserede Qt-tabeller; projektdata og artikeldata ændres ikke.
- Eksisterende gemte kolonnebredder og vinduesgeometri genbruges.
- Projektformat/version er 0.41.5.

## 0.41.3 → 0.41.4

- Ingen destruktive projektændringer.
- Tabelbredder og artikelvinduesgeometri gemmes som brugerindstillinger og er derfor uafhængige af projektfilen.
- Projektformat/version er 0.41.4.

## 0.41.2 → 0.41.3

- Ingen manuel projektmigrering er nødvendig.
- Prisdata gemmes globalt i `%APPDATA%\ElplanDWGEditor\article_prices.json` på Windows og ikke i det enkelte projekt.
- Eksisterende projekter åbnes uændret; priser tilføjes som et globalt overlay på artikelnumrene.
- Projektformat/version er 0.41.3.

## 0.41.1 → 0.41.2

- Stykliste-definitioner flyttes fra projektets `bom_assemblies` til et globalt brugerbibliotek (`bom_assemblies.json` i ElplanDWGEditor-mappen under AppData).
- Gamle projektstyklister migreres automatisk ved projektåbning. Hvis AppData ikke kan skrives, beholdes legacy-data i projektet, så intet går tabt.
- `symbol_assemblies` forbliver projektafhængig, fordi den beskriver hvilket symbol/modul der bruger hvilken global stykliste.
- Globale styklister indeholder artikel-snapshots for deres referencer, så egne artikler kan overføres til nye projekter.
- Projektformat/version er 0.41.2.

## 0.41.0 → 0.41.1

- Ingen projektmigration er nødvendig.
- Standardartikelbiblioteket er udvidet og metadata er korrigeret; eksisterende projektartikler ændres ikke automatisk.
- Projektformat/version er 0.41.1.

## 0.40.x → 0.41.0

Ingen manuel migrering er nødvendig. Artikelmetadata er udvidet med separat `supplier_page`, og eksisterende projekter åbnes fortsat direkte. Nye standardartikler kopieres som hidtil først ind i projektets eget artikelbibliotek, når de faktisk anvendes. Styklister beholder deres eksisterende artikelnumre; den nye artikelvælger ændrer kun arbejdsgangen i GUI'en.

## 0.39.0 – Genbrugelige styklister

Ingen manuel migration er nødvendig. Ældre projekter åbnes med tomme styklister og fortsætter med at bruge deres eksisterende `symbol_articles` manuelt. Nye projekter kan desuden indeholde `bom_assemblies` (selve styklisteopskrifterne) og `symbol_assemblies` (valg af stykliste pr. symbol/fysisk del). Den manuelle konfiguration beholdes parallelt og slettes ikke, når en stykliste vælges.

## 0.38.2 – Artikelmetadata og filtrering

Ingen manuel migration er nødvendig. Eksisterende projekter åbnes som før. Nye facetfelter på artikler (`product_type`, `design_family`, `module_size`, `color`, `mounting_type`) er valgfrie og udledes automatisk fra eksisterende beskrivelse/serie/kategori, hvor det er muligt. Når en standardartikel kopieres til projektbiblioteket, følger de nye metadata med.

## 0.38.1 – Komplet FUGA AIR SLIM-forfradåseserie

Ingen manuel migration er nødvendig. Standardbiblioteket er udvidet med de manglende SLIM-forfradåser i 1, 1½ og 2½ modul; 2-modul-varen er samtidig opdateret med specifik produktkilde.

## 0.38.1 – Standardartikelbibliotek og kabelartikler

Ingen manuel migration er nødvendig. Projekter fra 0.37.x åbnes som før. Når de gemmes i 0.38.1, kan de desuden indeholde top-level feltet `cable_articles`, som knytter en kabeltype/specifikation til et artikelnummer.

Det indbyggede standardbibliotek ligger ikke automatisk i hvert projekt. En artikel kopieres til projektets `article_catalog`, når brugeren tilknytter eller importerer den. Derved forbliver projektfilen selvbærende, samtidig med at ubrugt standarddata ikke duplikeres.

Eksisterende `article_catalog` og `symbol_articles` bevares. Artikel-normaliseringen bevarer fra 0.38.1 også metadatafelter som serie, kategori, EL-nr., EAN, status og kabeldata.

## 0.37.0 – Artikler og BOM

Ingen manuel migration er nødvendig. Ældre projekter åbnes med tomt artikelbibliotek og uden artikeltilknytninger. Når projektet gemmes i 0.37.0, kan det indeholde de nye top-level felter `article_catalog` og `symbol_articles`. Eksisterende symbolposter ændres ikke.

## 0.36.1 – Stabilitet og dataintegritet

Ingen manuel migration er nødvendig. Eksisterende projekter åbnes fortsat. Projektfiler valideres dog strengere, så korrupte koordinater som NaN/Inf, ugyldige størrelser eller dublerede objekt-id'er afvises med en fejl i stedet for at blive indlæst i en ustabil scene. Relative `source_file`-stier understøttes nu korrekt i forhold til projektfilens mappe.

## 0.36.0 – Parallel kabelvisning

Ingen projektmigration er nødvendig. Kabelbaner er en ren visuel beregning og gemmes ikke som ekstra geometri. Eksisterende projekter åbnes uændret, og kabellængder beregnes fortsat fra de oprindelige kabelpunkter.

## 0.35.8 – WYSIWYG PDF-preview

Ingen projektmigration er nødvendig. Preview bruger nu den samme PDF-renderer som eksporten og påvirker ikke projektformatet.

## 0.35.7 – PDF-output

Ingen projektmigration er nødvendig. Ændringen vedrører kun rendering/eksport. Eksisterende teksthøjder og mærkningsdata fortolkes uændret; PDF'en bruger blot samme visuelle størrelsesregler som Qt-editoren.

## 0.35.6 – snaplinjer og 3F+N-symbol

Ingen projektmigration er nødvendig. Ændringerne vedrører kun interaktions-/visningslogik og symbolgrafik.

## 0.35.5 – grafisk afbrydertilhørsforhold

Ingen projektmigration er nødvendig. `association_channels` fra 0.35.3 bruges nu også til at placere a/b/c visuelt ved de korrekte fysiske afbrydermoduler.

## 0.35.4 – zoomstabilitet

Ingen projektmigrering er nødvendig. Ændringen vedrører kun input-/view-håndtering.

## 0.35.3 – kombiafbryder-kanaler

Nye projekter gemmer `association_channels` på afbrydersymboler. Feltet holder den fysiske kanalrækkefølge adskilt fra den ældre, sorterede `associations`-liste. Ældre projekter åbnes fortsat: hvis `association_channels` mangler, fordeles de eksisterende bogstaver sekventielt på afbryderens kanaler. Projektet opgraderes først permanent, når det gemmes igen.

## 0.32.1 — Whole-plan association visibility

Ingen projektmigrering nødvendig. Auto-visningen viser nu a/b/c allerede i oversigtsniveauet som kompakt tekst.

## 0.32.0 — Semantic annotation + single-spot linking

- Project format remains backward compatible; no placement schema migration is required.
- `annotation_display_mode` now accepts `Skjult` in addition to Auto/Minimal/Tydelig.
- `annotation_last_visible_mode` is stored in application settings so the toolbar visibility toggle can restore the previous mode.
- Spot `parent_light_uid` storage is unchanged. Single palette spots are now auto-selected after placement to expose the existing parent-link workflow.

## 0.31.2 — Adaptive annotation + room-side placement

- multi-level Auto annotation sizing for whole-plan readability
- secondary annotation suppression at overview zoom
- room-side inference for wall-mounted symbol annotations
- annotation placement based on mount point, wall side, symbol geometry and CAD free space
- user toggle for automatic room-side placement

## 0.31.0 — Many-to-many electrical relations

- robust native Qt annotation composition
- one switch channel can control many light points
- one light point can participate in many association letters
- explicit existing-vs-new relation choice for ambiguous linking
- spot→lampested relationship separated visually from a/b/c
- selection-time relation overview for switches, lights and spot groups

## 0.30.9 — Label semantics + readable free text

- Gruppe/kreds promoted to primary annotation
- optional Mærkning demoted to secondary annotation
- split combo annotations follow the same hierarchy
- free text uses screen-space rendering in Qt for overview readability

## 0.30.8 — Cable editing + annotation hierarchy

- selectable/editable existing cable items
- draggable endpoint/breakpoint handles
- endpoint resnap and logical connection updates
- cable-property editing through Cable Tool
- undo/redo for cable edits/deletion
- adaptive annotation detail modes
- distinct label/group/association visual roles

## 0.30.7 — Output dimming + placement stability

- optional CAD dimming in PDF/print/preview
- wall-snap hysteresis for placement and dragging
- cursor-side auto orientation for wall devices
- explicit zoom anchor during symbol placement

## 0.30.6 — Cable workspace + visual hierarchy

- persistent Qt cable workspace
- live cable settings and continuous cable drawing
- CAD background opacity / electrical-plan focus mode
- stronger on-screen symbol rendering
- clearer label/group/association hierarchy

## 0.30.5 — Interaction polish

- selection click no longer invokes snap/movement
- compact screen-space annotations
- guided switch/light association workflow

# Qt migration roadmap

## 0.30.0–0.30.2 — Viewer + interaction foundation

- Qt main window
- `QGraphicsScene` / `QGraphicsView`
- samlet CAD-geometri pr. lag
- åbning af eksisterende projekter / DWG / DXF
- lagvisning
- grafisk symbolpalette
- Qt-native snap
- symbolplacering og flytning
- `QUndoStack`

## 0.30.3 — Electrical editing

- symbolkonfigurator
- custom kombisymboler, skabeloner og favoritter
- Rotér +90°
- kabel / ledning
- ortogonal routing
- kabelsnap til symboler / vægge
- afbryder ↔ lys-tilhørsforhold
- kombisymbolernes fælles/opdelte mærkning

## 0.30.4 — Workflow + output

- spot-række
- rectangular spot pattern
- spotstørrelse som hurtigkontrol
- tilknyt spots til lampested
- fri tekst
- direkte mærkningsredigering
- copy/paste
- forbedret multi-select og gruppeflytning
- PDF-eksport
- direkte udskrift
- Qt print-preview

## Næste core-refaktor

Når funktionaliteten er stabil i Qt, kan `legacy_core.py` gradvist opdeles i GUI-neutrale moduler:

- `symbols`
- `cad`
- `project`
- `snap`
- `export`

Målet er at bevare projektkompatibilitet, mens den gamle Tkinter-afhængighed forsvinder trinvis.

## 0.44.4 – kabelvisningsindstillinger
Ved første start repareres en indstillingsfejl fra 0.44.0-0.44.3, som kunne have gemt parallelvisning som deaktiveret under GUI-initialisering. Reparationen sker én gang og ændrer ikke projektdata.
