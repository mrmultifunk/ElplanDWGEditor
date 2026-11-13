## 0.59.75 - PL-dåse feltregistrering

- PL-dåse-konfiguratoren kan nu hente feltregistreringer direkte fra `pl-daase` via dens read-only API.
- Serveradresse og API-token konfigureres under `Indstillinger → Integrationer`; tokenet gemmes kun lokalt og kommer aldrig med i projektfilen.
- Importen viser altid en forhåndsvisning af de seks fysiske indføringer, PWA'ens kabeltekst og eventuelle noter, før noget anvendes.
- Et Elplan-kabelben foreslås kun, når kabeltypen giver ét entydigt match. Ved flere mulige kabler kræves et manuelt valg.
- PWA'ens tælleretning kan omsættes til PL-dåsens fysiske orientering, og importerede fotos kan vises med markører for indføring 1–6.
- Feltregistreringen og den valgte fysiske kabelplacering gemmes sammen med PL-dåsen og kan opdateres eller afkobles senere.
- PWA-data kan ikke oprette eller ændre lederfunktioner, lampeudtagsklemmer, gennemsløjfninger eller WAGO-samlinger. De funktioner forbliver udelukkende i Elplans lederfordeling.

## 0.59.74 - Tavler, jordforbindelse og forsyningskabler

- Symbolpaletten har fået den særskilte gruppe `Tavler / forsyning`, som samler fordelingsanlæg, gruppetavle og de nye symboler.
- Nyt vektorsymbol `Målertavle` med tydelig målercirkel, M-mærkning og tre kabel-snap-punkter.
- Nyt vektorsymbol `Hovedjordforbindelse` med standardiseret jordgrafik, tilslutningspunkt og eget grønne CAD-lag `EL-JORDING`.
- Kabelvælgeren har fået `1G2,5`, `1G6` og `1G10` til beskyttelsesledere og potentialudligning.
- Kabelvælgeren har fået `4X10` som stik-/hovedledning. X-betegnelsen behandles udtrykkeligt uden gul/grøn PE-leder og vises som brun, sort, grå og blå.
- Den primære kabeltype-dropdown og kabelafsnitseditoren bruger nu samme centrale liste, så alle nye kabeltyper er synlige både ved oprettelse og redigering.
- Nye kabelkategorier `Udligning / beskyttelsesleder` og `Stikledning / hovedledning` kan vælges, filtreres og lagstyres på samme måde som eksisterende kabelkategorier.
- Eksisterende projekter får de to nye standardkategorier én gang ved åbning; brugerens eksisterende kategorier og tilpasninger bevares.

## 0.59.73 - Artikeltypefilter og ensartede symbolmærkninger

- BOM-fanen har fået et dynamisk `Artikeltype`-filter baseret på de typer, der faktisk findes i den aktuelle BOM.
- Artikler kan sorteres og grupperes efter samme brugerrettede type.
- BOM-tabellen viser `Type/kategori` som selvstændig kolonne.
- Kategoriseringen kombinerer artikelmetadata, beskrivelsen, kildetypen og komponentens rolle i styklisten.
- `uden tangent` og `uden afdækning` behandles eksplicit, så afbryder- og stikkontaktindsatse ikke fejlkategoriseres.
- Excel får en filterbar `Type/kategori`-kolonne og eksporterer kun de artikeltyper, som er synlige efter det aktuelle BOM-filter.
- Rumopdelt Excel, CSV, PDF-preview og udskrift følger samme artikeltypefilter som BOM-tabellen.
- Filterlinjen er delt i to rækker, så de nye valg ikke gør BOM-toppen kompakt eller uoverskuelig.
- `3F+N+PE` har nu samme synlige højde og afstand til væggen som de øvrige stikkontakter ved samme symbolstørrelse, uden at eksisterende placeringers historiske væganker flyttes.
- De forenklede dobbelt- og tredobbelte stikkontakter viser `2` og `3` centreret i buen i stedet for ved symbolstammen.
- Alle interne symbolmærkninger (`2`, `3`, `4`, `3N`, `N`, `VV`, `L` og `R`) bruger nu samme centrerede, fede og rotationsuafhængige tekst i editor, palette, PDF, DXF/DWG og direkte udskrift.
- Symbolgennemgangen har fået regressionstest for geometri, vægjustering, kvartdrejninger og gyldige bounding boxes for hele det indbyggede symbolbibliotek.

## 0.59.72 - Effektiv artikel- og styklistehåndtering

- Artikelmodellen skelner nu mellem forbrugsenhed, salgsenhed, antal pr. salgsenhed, mindste bestilling og en læsbar pakningsbeskrivelse.
- BOM-priser multipliceres med det korrekte grundlag: faktisk forbrug ved styk-/meterpris og afrundet indkøbsantal ved pakke-/rullepris.
- Eksisterende kabelartikler med `package_length_m` migreres automatisk til den nye model uden at ændre deres legacy-enhed eller projektdata.
- Artikelredigering og import-/eksportformat v4 understøtter alle pakningsfelter, og pakningen vises i artikelpreview og prisdialog.
- BOM har fået fanen `Kontrol` med fejl, advarsler, forslag og hurtigfiltre for manglende artikel, forældet pris og pakningsproblemer.
- `Hvor bruges?` viser både konkrete projektkilder og alle globale styklister, der indeholder den valgte artikel; projektforekomster kan åbnes direkte på planen.
- Styklisteeditorens komponentformular er flyttet til et kompakt sidepanel, skjult som standard. Tabellen får dermed markant mere højde, og flere komponentrækker kan fjernes på én gang.

## 0.59.71 - Læsbar 3-polet stikkontakt

- Den interne `3N`-mærkning i symbolet **Stikkontakt 3F+N+PE** står nu altid vandret og læsbart, også når symbolet roteres til en lodret væg.
- Mærkningen er centreret i stikkontaktbuen og reduceret til en kompakt størrelse, så den ikke længere kolliderer med symbolstammen eller kabelføringen.
- Samme rotationsregel bruges i editoren, symbolpaletten, PDF, DXF/DWG og direkte Windows-udskrift.
- Der er tilføjet regressionstest for både symbolgeometri og en 90° roteret DXF-eksport.

## 0.59.70 - WAGO-priser som stykpris

- WAGO-samlemuffer beregnes nu konsekvent som pris pr. fysisk muffe, selv når en webshop kalder en hel salgsæske for `1 stk.`.
- Pakkestørrelser fra URL, sidetitel, strukturerede produktdata og synlig webshoptekst genkendes før prisestimatet gemmes.
- De dokumenterede WAGO-underpakninger ligger som fallback i artikeldataene; en normal reel enkeltstykpris divideres ikke.
- Automatiske WAGO-webshoppriser fra prisbog v4 kasseres ved første indlæsning, så gamle pakkepriser ikke fortsætter i BOM, hover eller PDF.
- Manuelle priser bevares altid og har fortsat prioritet over automatiske estimater.
- Allerede oprettede `articles.json`-databaser får de reviderede WAGO-stykpriser og pakningsmetadata uden at påvirke andre artikler.

## 0.59.69 - BOM pr. rum i PDF

- Udskriftsforhåndsvisningen viser valget `Medtag BOM pr. rum`, når BOM-fanen står på `Alle rum`.
- Valget er slået til som standard og regenererer previewet straks, når det ændres.
- Den samlede BOM forbliver første og autoritative del af PDF'en; derefter følger en separat femkolonners BOM med delsum for hvert rum.
- Rumsektioner fortsætter automatisk over sider og genbruger tabeloverskrifterne uden at tvinge ét helt papirark pr. lille rum.
- Rumdata følger samme hurtigfilter, kabelvalg, sortering og inkl./ekskl. moms som hoved-BOM'en og Excel-eksporten.
- PDF'en forklarer kort, at additive ekstra BOM-rum kan få summen af rum til at overstige projekttotalen.
- Ved valg af ét konkret rum på BOM-fanen vises kun dette rum, og det overflødige rumopdelingsvalg skjules.

## 0.59.68 - Enkel BOM-udskrift med preview

- BOM-fanen har fået én tydelig handling, `Udskriv / PDF…`, som altid viser den endelige A4-rapport før gemning eller udskrift.
- Previewet viser flere sider samlet og kan skifte mellem tilpasning til side og bredde.
- Den printvenlige BOM er reduceret til de fem vigtigste kolonner: varenummer, beskrivelse, antal, enhedspris og beløb.
- Totaler vises pr. valuta, og manglende priser eller artikeltilknytninger opsummeres kort uden at gøre listen tung.
- Aktuelt rum, hurtigfilter, kabelvisning, sortering og global momsvisning genbruges direkte fra BOM-fanen.
- `Gem som PDF…` kopierer præcis det previewede dokument, mens `Udskriv…` åbner systemets printervalg og udskriver de valgte sider.
- Excel og CSV bruger nu samme fælles filtrerede datagrundlag som previewet.

## 0.59.67 - Rumnavne i PDF og udskrift

- PDF-generatoren modtager nu projektets rumdata, så synlige rumnavne kommer med i både preview og den gemte PDF.
- Rumnavn, rummærkning/ID og rumafgrænsning følger fortsat hver sit valg i Vis-menuen.
- Hele-plan-udsnittet medregner synlige rumteksters anker og eventuelle rumafgrænsninger, så frit flyttede rumnavne ikke udelades.
- Direkte Windows-udskrift bruger samme rumdata og synlighedsvalg som PDF-eksporten.
- Rumtekster tegnes med fast fysisk skriftstørrelse og skalerer derfor ikke uhensigtsmæssigt med CAD-planen.

## 0.59.66 - Hurtigere og mere handlingsorienteret lederfordeling

- Lederfanen har fået en kompakt problemnavigator, der samler konflikter, manglende tændledere, overfyldte klemmer, manglende gennemsløjfningsdestinationer og ufordelte aktive ledere.
- `Næste uløste` og genvejen `F8` springer direkte til den relevante leder eller klemme og fremhæver hele den elektriske funktion i grafikken.
- En synlig symbolforklaring skelner mellem forbundet, allokeret ved anden kabelende, ufordelt, konflikt, manuel kontrol, reserve og ikke tilsluttet.
- `Foreslå fordeling…` viser en forhåndsvisning med individuelle afkrydsninger; ingen lederforbindelser foretages automatisk.
- Entydige allokeringer ved den anden kabelende samt PE og N er sikre, forhåndsvalgte forslag. Brun som fast fase kræver altid aktiv kontrol, fordi brun også kan være tændledning.
- Manglende direkte tændinger foreslås kun på deres dokumenterede kabelben og foretrækker sort, grå, rød eller hvid frem for typiske forsyningsfarver.
- Konflikter langs samme fysiske kabel bliver aldrig foreslået automatisk, men vises som klikbare fejl til manuel afklaring.
- Kabelbred anvendelse beregnes nu én gang pr. reel lederændring og genbruges af diagram, navigator, valgtekst og forslag.
- PL-diagrammet cacher normaliseret lederprofil, terminalprofil og opslag mellem ændringer; hover og markering genopbygger derfor ikke længere de samme domænedata.
- Redundante genoptegninger ved uændret kompakt/eksploderet visning og uændret ledervalg springes over.

## 0.59.65 - Gennemsløjfninger og tydeligere ledergrafik

- Samlemuffer uden bro til det lokale lampeudtag kan tildeles tændleder, mellemleder 1/2, PE, N, L, reserve eller ikke tilsluttet.
- Tænd- og mellemledere knyttes eksplicit til et andet lampested og dets tilhørsbogstav; direkte/sammenhængende kabelveje foreslås først.
- Mellemleder 1 og 2 gemmes som forskellige elektriske funktions-id'er og kan derfor ikke blandes i samme muffe.
- Gennemsløjfninger til et andet lampested kan ikke ved en fejl forbindes videre til det lokale lampeudtags klemme.
- Eksisterende tænd-/mellemledersamlinger uden destinations-id markeres til manuel kontrol i stedet for at blive ændret automatisk.
- Lederkurvernes top- og bundzoner har fået reel afstand og vandret forskydning, så næsten ens ruter ikke tegnes oven i hinanden.
- Løse lederender holdes tættere ved deres egen indføring og laver ikke længere store Bézier-løkker gennem montagefladen.
- Et blåt grafisk kædeled erstatter `?`, når samme leder allerede har en funktion ved kablets anden ende. Hover viser funktionen og understreger, at den lokale fysiske forbindelse stadig mangler.

## 0.59.64 - Mere tabelplads i styklisteeditoren

- Komponenttabellen er nu styklisteeditorens primære, fleksible område og har en sikret brugbar minimumshøjde.
- Klassifikation/navneparametre og Beskrivelse/note er foldbare og starter sammenfoldet.
- Formularen Tilføj eller opdatér komponent kan også foldes sammen efter brug.
- Ny handling `Maksimér tabel` skjuler alle tre sekundære områder med ét klik.
- Foldetilstanden huskes mellem åbninger, mens samtlige styklistefelter og data bevares uændret.

## 0.59.63 - Pris i symbol-hover og samlede indstillinger

- Symbol-hover viser artikelpris, eventuel linjesum, styklistepris og samlet symbolpris i det globale momsvalg.
- Valutaer summeres separat, og manglende priser vises med en kompakt dækningsadvarsel.
- Styklister bruger kun aktive komponenter; fravalgte valgfrie komponenter medregnes ikke, og en stykliste erstatter fortsat direkte artikelrækker for samme symboldel.
- Nyt kategoriseret panel under `Værktøjer → Indstillinger…` samler Visning, Priser og BOM samt Lager og synkronisering.
- Momsvalget i indstillingspanelet og Artikler/BOM deler fortsat nøglen `price_vat_mode`; priser lagres uændret ekskl. moms.
- Pris-overlayet til symbol-hover caches efter katalogets og prisbogens filsignatur, så gentagne hovers ikke genbehandler hele artikelbasen.

## 0.59.62 - Rumoversigt i Excel og kabel-filter i BOM

- Excel-eksport med Alle rum får et nyt ark, `Rumoversigt`, med delsummer pr. rum og valuta.
- Rumoversigten viser antal forskellige artikler, linjer med/uden pris, delsum og prisdækning.
- Den autoritative projekttotal forbliver på `BOM`; rumarket advarer om additive ekstra BOM-rum, så rumdelsummer ikke forveksles med projekttotalen.
- Detaljearket `BOM pr. rum` bevares som filterbar Excel-tabel og placeres efter Rumoversigt.
- Nyt hurtigvalg `Vis kabler` genberegner BOM, mangelliste, totaler, kilder og eksport uden kabelbidrag, når det slås fra.
- Kabeltilknytninger og projektdata ændres ikke af filteret.

## 0.59.61 - Prissammenligning og valgfri momsvisning

- Ét globalt valg i Artikler og BOM skifter prisvisningen mellem ekskl. og inkl. moms og huskes lokalt på pc'en.
- Valget bruges konsekvent i artikeloversigter, previews, prisredigering, styklister, BOM-tabeller, totaler og CSV-/Excel-eksport.
- Prisbog og BOM-model gemmer fortsat autoritative priser ekskl. moms; inkl. moms er kun et visnings-, input- og eksportlag.
- Artikler med webshopobservationer kan sammenlignes på tværs af WATTOO, LavprisEL og Greenline med billigste pris, forskel, kontroltidspunkt, matchgrundlag og direkte produktlink.
- Pakkepriser normaliseres fortsat til BOM-enheden, mens den oprindelige pakkepris vises separat, så forhandlere sammenlignes på et retvisende grundlag.
- Manuel prisredigering bevarer webshopobservationer og automatisk estimatproveniens.

## 0.59.60 - Separat artikeldata i OneDrive

- Artikelkatalog, prisbog og globale styklister kan nu flyttes til en selvstændig synkroniseret mappe, fx `OneDrive/Elplan/Artikeldata`.
- Artikeldataene er fortsat globale og projektafhængige; projektlager og projektfiler ændres ikke af flytningen.
- Indstillinger, logs og katalogcache forbliver lokale på den enkelte pc, mens kun de autoritative artikeldata synkroniseres.
- Eksisterende lokale data kopieres og flettes ind i målplaceringen. Måldata sikkerhedskopieres først og har forrang ved konflikter, så en eksisterende fælles database ikke rulles tilbage.
- Den tidligere dataplacering slettes ikke automatisk og kan derfor bruges som sikkerhedskopi.

## 0.59.59 - Skalerbar kabel- og mærkningsvisning

- Kabel-layoutets broad-phase kopierer ikke længere den resterende segmentliste for hvert segment. Spredte kabelplaner behandles derfor reelt næsten lineært i stedet for stadig at få skjult kvadratisk overhead.
- Fælles kabelafgange ved symbolterminaler og legacy-koordinater findes nu via terminalopslag og et lokalt koordinatgitter frem for at sammenligne alle kabelender med alle andre.
- Mærkninger og tændingsforhold bruger et eksakt rumligt indeks til kollisionskontrol. Kun nærliggende symboler og mærkninger undersøges, mens placering og tæt-plan-fallback er uændret.
- Allerede opbyggede mærkningsgrafikker genbruges under zoom, så native Qt-tekst- og path-items ikke slettes og oprettes igen, medmindre indhold, tema eller semantisk zoomniveau faktisk ændrer sig.
- Tændingsforhold ved afbrydermoduler genbruger ligeledes deres grafik mellem zoomtrin og køres kun gennem det billigere positionslayout.
- Syntetisk kontrol med 4.000 spredte kabler faldt fra ca. 14,2 s i 0.59.58 til ca. 0,05 s i testmiljøet. Mærkningslayout med 1.000 spredte elementer faldt fra ca. 2,3 s til ca. 0,09 s.

## 0.59.58 - Ydelse og tydeligere flerstik

- Parallel-kabel-layout bruger nu en konservativ geometrisk broad-phase før den præcise overlaptest, så uvedkommende kabelsegmenter ikke længere sammenlignes parvist. Det reducerer kraftigt CPU-forbruget på større kabelplaner uden at ændre den visuelle lane-logik.
- Zoom-opdateringer samles over et lidt længere interval, så trackpad/musehjul ikke udløser tunge kabel- og annotationsberegninger midt i hvert zoom-burst.
- Mini-navigatoren genberegner ikke længere hele scenens extents ved ren zoom; kun viewport-markeringen genmales.
- Zoomens statuslinje opdateres uden samtidig at genberegne workflow-overlayet.
- Tallet `2`/`3` på dobbelte og tredobbelte stikkontakter er gjort ca. 29 % større og en anelse bedre centreret, så det står tydeligere i både editor og PDF.

## 0.59.57 - Diskrete tændingsforhold i PDF

- Afbrydernes a/b/c-tændingsforhold bruger nu en særskilt, mere printvenlig PDF-stil.
- Kapslerne har mindre tekst, markant mindre vandret/lodret padding og ingen tvungen minimumsbredde.
- Baggrund og kant er gjort lysere og tyndere, mens den blå tekst bevarer tydelig identitet.
- Mærkningen ligger lidt tættere på det fysiske afbrydermodul og fylder derfor mindre visuelt på tætte plantegninger.
- Skærmvisningen er uændret; ændringen gælder PDF/preview, hvor relationen er støtteinformation frem for et aktivt redigeringsgreb.

## 0.59.57 - PDF følger den aktuelle visning

- PDF/print respekterer nu Vis-menuens hurtigfiltre, så skjulte kabler, patchkabler, symboler, CAD og tekst ikke dukker op igen i output.
- `Aktuel visning` center-beskæres ikke længere til papirets aspekt. Hele viewportens venstre/højre/top/bund bevares og skaleres ind på siden.
- Udskriftsforhåndsvisning bruger samme synlighed og fit-inside-regel som den gemte PDF.
- Kabel-lane-layout i PDF/print beregnes kun ud fra faktisk synlige kabelkategorier.

## 0.59.57 - Rumnavn og rummærkning kan vises separat

- Nyt visningsvalg **Vis rummærkning** under Rum.
- Rummets navn kan forblive synligt, mens mærkning/ID som `R01` skjules på plantegningen.
- Projekter uden en tidligere præference bruger den roligere standard med kun rumnavn.
- Den skjulte mærkning bevares uændret i projektdata og bruges fortsat i BOM, rapporter og kabelmærkning.
- Rumafgrænsning, rumnavn og rummærkning kan nu styres uafhængigt.

## 0.59.57 - Rumafgrænsning kan skjules igen

- **Vis rumafgrænsninger** afspejler nu den faktiske synlighed, også mens rumredigering er aktiv.
- Hvis rumafgrænsninger skjules under **Redigér rumafgrænsning**, afsluttes redigeringstilstanden automatisk, så polygonerne faktisk forsvinder.
- Rumtekster forbliver uafhængige og kan fortsat være synlige uden polygonerne.
- De nye knækpunkter fra 0.59.50 er uændrede.

## 0.59.57 - Flere knækpunkter på eksisterende rum

- Eksisterende rum kan få nye polygonpunkter uden at blive tegnet om.
- I aktiv rumredigering indsætter dobbeltklik på en side et nyt knækpunkt på den nærmeste kant.
- Højreklik på en rumside har også `Tilføj knækpunkt her`.
- Det nye punkt bruger samme væg- og 0/90-graders snap som øvrige rumhjørner.
- Tilføjelse af knækpunkt følger Undo/Redo.

## 0.59.57 - Cloud-opstart hotfix

- Retter opstartsfejlen i 0.59.48: `ProjectCollaborationMixin` var importeret, men ikke koblet på `MainWindow`.
- Cloud-/låsetilstanden og dens UI kan nu initialiseres korrekt ved programstart.
- Tilføjer en regressionstest specifikt for mixin-wiring samt startup/shutdown-hooks.

## 0.59.57 - Cloud-sikker projektredigering

- Strukturerede projekter bruger nu `project.lock` med heartbeat, computer og sessions-id.
- Aktiv fremmed projektlås giver skrivebeskyttet åbning i stedet for samtidig skrivning.
- Eksterne ændringer af `project.elplan.json` registreres løbende via indholdshash.
- Gem stoppes ved ekstern konflikt, så en OneDrive/Syncthing-revision ikke overskrives utilsigtet.
- Statuslinjen viser Lokal, Synkroniseret mappe eller Konflikt.
- Før en ekstern projektversion indlæses, oprettes automatisk en revisionsbackup af aktuelle in-memory projektdata og CAD.
- Normalt luk af programmet frigiver projektlåsen; gamle heartbeat-låse bliver automatisk betragtet som forældede.

## 0.59.47 - Valgfrit projektlager og projektmigration

- Valgfrit projektlager: klassisk frit filvalg, lokalt projektbibliotek eller synkroniseret mappe/OneDrive.
- OneDrive bruges som almindelig lokal synkroniseret mappe; ingen Microsoft-login/API kræves.
- Ny struktureret projektmappe med `project.elplan.json`, `drawing/`, `backups/`, `exports/` og `project-info.json`.
- Første Gem efter åbning af en ny DWG/DXF bruger automatisk projektbiblioteket, hvis det er aktiveret.
- Eksisterende projekter kan migreres via Fil > Projektlager > Migrér aktuelt projekt til projektlager.
- Migration kopierer projektets aktuelle in-memory data, DWG/DXF og eksisterende backupmapper, men sletter aldrig originalen.
- Nye plantegningsrevisioner gemmer backup i den strukturerede `backups/`-mappe; legacy-projekter bruger fortsat `Elplan_backups`.

## 0.59.57 - Automatisk revisionsbackup ved plantegningsopdatering

- `Opdatér plantegning…` opretter nu obligatorisk en backup af både den nuværende CAD-revision og projektets aktuelle in-memory tilstand før udskiftning.
- Backup-parret gemmes samlet i `Elplan_backups/<tidspunkt>_før_plantegningsopdatering/`.
- Backup-projektet peger direkte på backup-CAD-filen og kan derfor åbnes som et selvstændigt restore point.
- Ved genindlæsning af samme filsti eksporteres den stadig indlæste gamle CAD-revision fra hukommelsen, så en DWG/DXF der allerede er overskrevet på disken ikke erstatter original-backuppen.
- Hvis en af backupfilerne ikke kan oprettes, afbrydes opdateringen og det aktive projekt ændres ikke.

## 0.59.45 - Opdatér eksisterende plantegning

- Nyt **Fil → Opdatér plantegning…** genindlæser den nuværende DWG/DXF eller vælger en revideret fil uden at oprette et nyt projekt.
- Symboler, kabler, spotgrupper, rum, tekster, styklister og artikelbindinger bevarer deres koordinater og relationer.
- Den nye CAD-fil parses helt før den aktive baggrund udskiftes; en defekt fil efterlader projektet urørt.
- Aktuel zoom/arbejdsposition bevares under opdateringen.
- Nye CAD-lag bliver tilgængelige automatisk; eksisterende lagvisning bevares hvor lagene stadig findes.
- Meget store ændringer i CAD-nulpunkt eller skala udløser en sikkerhedsadvarsel før udskiftning.

## 0.59.45 - Kabeltræksoverblik ved hover

- Hele kabeltrækkets længde vises nu som en fast, kompakt statuslinje i kabelinspektøren, når et eksisterende kabelstykke er valgt.
- Den detaljerede længdesektion kan fortsat være foldet sammen; totalen for hele kabeltrækket er stadig synlig.
- Hover over ét kabelstykke giver nu en meget afdæmpet halo på alle synlige fysiske kabelstykker med samme `route_chain_uid`.
- Den eksisterende animerede hover-effekt på selve kabelstykket er uændret og forbliver den primære markering.
- Enkeltstående kabeltræk får ikke ekstra kæde-halo, og skjulte kabelkategorier forbliver skjulte.

## 0.59.43 - Samlet længde for kabeltræk

- Kabelinspektøren viser nu både længden af det markerede fysiske kabelstykke og den samlede længde for hele kabeltrækket.
- Hele kabeltrækket beregnes ud fra `route_chain_uid`, så kun de fysiske kabler fra samme tegnede streng summeres.
- Begge længder viser både rutelængde og længde inkl. projektets reserve.
- Legacy-kabler uden `route_chain_uid` behandles som selvstændige kabler og bliver aldrig fejlagtigt summeret sammen.
- Under aktiv tegning vises fortsat den aktuelle preview-længde for kabelstrengen.

## 0.59.42 - UI/UX-oprydning og lazy refresh

- Artikler/BOM refresher nu kun den synlige topfane ved åbning; skjulte faner bygges først, når de faktisk vælges.
- Senest anvendte Artikler/BOM-fane huskes på tværs af åbninger, mens kontekstuelle åbninger fra symbol/rum stadig går direkte til den relevante fane.
- Hjælpeteksten øverst i Artikler/BOM er flyttet til en kompakt fold-ud-sektion, så arbejdsfladen får mere plads.
- Stykliste-, kabel- og artikelintroer er forkortet uden at fjerne information; tekniske lagringsstier ligger nu i tooltip i stedet for permanent på skærmen.
- Artikler/BOM-faner bruger et roligere dokument-tab-layout og har forklarende tooltips.
- Kabelinspektørens fold-ud-sektioner har ikke længere dobbelte GroupBox-rammer/overskrifter, og den synlige rutesektion er gjort mere kompakt.
- Ingen ændringer i projektformat, BOM-beregning, artikeldata eller kabeldata.

## 0.59.41 - Spotgruppeflytning og spot-snap

- Flytning af ét spot i en spotgruppe flytter hele gruppen med samme forskydning og som én Undo/Redo-handling.
- Låste gruppemedlemmer blokerer samlet flytning, så gruppen ikke kan blive splittet.
- Spot-snap til andre spots er eksplicit prioriteret ved placering/flytning; gruppens egne spots ignoreres som snap-reference.

## 0.59.40 - Kabelkategori: Spots

- `Spots` er standard-kabelkategori med separat visning og migration til ældre projekter.

## 0.59.39 - Vandret/lodret snap for spotrækker

- Spotrækker snapper blødt til 0°/90° med Alt som midlertidig fri vinkel.

## 0.59.38 - Spotgrupper og downlightkabel

- Vedvarende spotgrupper, samlet Spot → lampested-tilknytning og downlight-kabelartikel blev tilføjet.

## 0.59.37 - Programikon

- Nyt Elplan-programikon indbygget som PNG og Windows ICO.
- Ikonet bruges som applikations- og vinduesikon; Windows får eget AppUserModelID for korrekt taskbar-identitet.

## 0.59.36 - Kompakt PL-grafik

- Lederfordelingen åbner nu i en ny kompakt visning, hvor lederforløbet får mere plads og visuel prioritet.
- Wago- og samlemuffekort er markant mindre, mere neutrale og viser kun funktion, lederantal og kapacitetsbadge i standardvisningen.
- Lampeudtagets terminalpanel er smallere og fysisk lavere; terminalrækker, klemmer og labels er reduceret uden at ændre den elektriske model.
- Sekundære Wago-/terminaldetaljer skjules i kompakt visning og vises på hover.
- Ny Kompakt/Detaljeret-toggle genskaber den informationsrige visning ved behov.
- Detaljeret visning bevarer artikelnummer, pladsforbrug, ekstra terminaltekst og Wago-samlingstekst.
- Ingen ændringer i lederfordeling, Wago-regler, terminalkapacitet eller gemt projektdata.

## 0.59.35 - Animeret projektåbning

- Den eksisterende fuldskærms busy-overlay er redesignet til en kort, moderne projektåbningsanimation frem for et separat splash-vindue.
- Blueprint-inspireret projektindikator med roterende accent under indlæsning og checkmark ved succes.
- Tre faktiske statusfaser vises: **Projektdata**, **Tegning** og **Arbejdsflade**. Fasen følger de eksisterende reelle load-statusbeskeder.
- Overlayet fader blødt ind og viser kort **Projekt klar** / **Tegning klar**, før det fader væk uden en blokerende ventepause.
- Indlæsning bruger fortsat en indetermineret progressbar; der vises ikke et falsk procenttal for operationer, som ikke rapporterer stabil fremdrift.
- Samme animation bruges ved både Elplan-projekt og direkte DWG/DXF-åbning.

## 0.59.34 - Hurtigere Artikler og BOM

- Fjernet gentagen normalisering af hele artikelkataloget under åbning af Artikler og BOM.
- Optimeret kernedatakatalogets load/merge, så allerede normaliserede bruger- og grunddata ikke beriges igen efter merge.
- Tilføjet hurtig pris-overlaysti til allerede normaliserede kernedata og prisbog.
- Artikelbrowserens søgeindeks genbruger nu det allerede prisberigede katalog i stedet for at anvende priser endnu en gang.
- Datakvalitetsaudit er gjort lazy og køres først, når Datakvalitet eller et kvalitetsfilter faktisk bruges.
- BOM-refresh genbruger den allerede beregnede ufiltrerede BOM i stedet for at bygge BOM/kildedata igen kun for filtertællingen.
- Stykliste-navneanalyse kan genbruge et fælles artikelopslag i stedet for at bygge et 3k+ opslag pr. stykliste.
- Benchmark på 3.539 kernedata-artikler reducerer den synkrone data-hot-path ved første åbning fra ca. 6,0 s til ca. 1,3 s i buildmiljøet.

## 0.59.33 - Samspil mellem stykliste og navnehjælp

- Type, Opbygning, Funktion/udførelse, System/serie, Montering, Farve og Ekstra tekst er nu direkte redigerbare i **Stykliste**-vinduet.
- Styklisteeditoren og **Navneassistent** arbejder på præcis de samme strukturerede værdier; ændringer fra assistenten føres tilbage til hovedvinduet.
- **Dan navn** er en eksplicit handling. Parametre overskriver aldrig et manuelt navn automatisk.
- Statuslinjen i navnefeltet viser om navnet matcher parametrene eller er et manuelt navn med et separat navneforslag.
- **Udfyld fra stykliste** kan genfortolke det aktuelle navn og de aktuelle komponenter både i hovedvinduet og i assistenten.
- Kategori og Variant er tydeliggjort som frie ekstra biblioteksfelter; Type/System/Farve osv. skal ligge i de strukturerede navneparametre.
- Genererede navne er gjort mere kompakte og følger den eksisterende stil, fx `2×1M FUGA SLIM Forfra Stikkontakt Med jord Koksgrå`, mens filterværdien stadig er den kanoniske `LK FUGA SLIM`.
- Styklistebibliotekets schema forbliver v4; ingen datamigration er nødvendig.

## 0.59.32 - Struktureret navngivning og styklistefiltre

- Brugerfladen bruger nu konsekvent **Stykliste** / **Styklister** for det globale BOM-opskriftsbibliotek; betegnelsen montage er fjernet fra denne arbejdsgang.
- Navneassistenten er udvidet til Type, Opbygning, Funktion/udførelse, System/serie, Montering, Farve og valgfri ekstra tekst.
- **System / serie** er ikke længere et frit tekstfelt. Listen er kurateret efter reelle LK/Schneider-betegnelser og skelner mellem produktprogrammer, installationssystemer/-varianter, designserier og Wiser.
- Verificerede valg omfatter bl.a. LK FUGA, LK FUGA AIR, LK FUGA AIR SLIM, SLIM, SOFT, PURE, CHOICE, BASE 63, BASELINE 50, SOFTLINE 63/68, LK OPUS 66/74, LK CLIC'LINE og Wiser. SOFTLINE 63/68 markeres som ældre serier.
- Gamle korte navne som `FUGA SLIM` kan stadig genkendes, men normaliseres til den officielle betegnelse `LK FUGA SLIM`.
- Navneparametrene gemmes struktureret i styklistebiblioteket (schema v4) og påvirker ikke det frie navn eller BOM-beregningen.
- Styklistebiblioteket har nye filterfelter for Type, Opbygning, Funktion, System/serie, Montering og Farve samt egne sorterbare kolonner for de samme parametre.
- Ældre styklister uden strukturerede felter forsøges udfyldt konservativt fra navn og artikelmetadata, så de kan filtreres uden tvungen migration.
- **Ryd navneparametre** gør det muligt at beholde et helt manuelt navn uden strukturerede filterværdier.
- Kernedata-/portabilitetseksport bevarer de nye navneparametre.

## 0.59.31 - Navneassistent til styklister / montager

- Montageeditoren har fået en separat **Navneassistent…**, mens navnefeltet fortsat altid kan redigeres manuelt.
- Navneforslag bygges af fem enkle dele: Type, Udførelse, System/serie, Farve og valgfri ekstra tekst.
- Dropdownfelterne er redigerbare, så egne betegnelser kan bruges uden at ændre programmet.
- Assistenten viser navnet som preview og ændrer først montagen, når **Brug navn** vælges.
- **Udfyld fra montage** laver konservative forslag ud fra eksisterende navn, kategori/variant og artikelmetadata.
- Eksisterende navnekonventioner som `2X1M FUGA SLIM FORFRA STIKKONTAKT KOKSGRÅ` kan opdeles til 2×1M / FUGA SLIM / Stikkontakt / Koksgrå med restteksten bevaret som ekstra tekst.
- Navneassistenten ændrer ingen BOM-data, artikelbindinger, kategori eller montagevariant.

## 0.59.30 - Stykliste-/montagehåndtering 2.0

- Styklister er løftet til montager med kategori, variant, tags, beskrivelse og montagenote.
- Montageeditoren viser aktive/faste/valgfrie komponenter, montagepris og projektpåvirkning.
- Valgfrie komponenter kan gemmes i montagen og slås til/fra; fravalgte komponenter tæller ikke i BOM eller sporbarhed.
- Montagebiblioteket kan søges og filtreres efter kategori og kun anvendte montager.
- Biblioteket viser komponentantal, anvendelser i aktuelt projekt, montagepris og metadata.
- Ny handling “Vis anvendelser på plan” fremhæver alle symbolforekomster som bruger den valgte montage.
- BOM-montagevisningen viser nu kategori og variant.
- Montagevælgeren viser aktive komponenter samt kategori/variant for hurtigere identifikation.
- Globalt montagebiblioteksformat er hævet til version 3; ældre styklister migreres automatisk.

## 0.59.29 - Artikelbrowser 2.0

- Artikeldatabasen har fået produktivitetsvisninger for Favoritter, Senest anvendte, Brugt i projekt og Kræver datakontrol.
- Favoritter og seneste artikler gemmes globalt på tværs af projekter; valgte/tilknyttede artikler huskes automatisk som senest anvendte.
- Facetfiltrene er nu kaskaderende: hvert felt viser kun værdier, der stadig kan give resultater med de øvrige aktive filtre, inklusive antal træffere.
- Fritekstsøgning bruger et forberegnet indeks og relevansrangering. Præcist artikelnummer, EAN og EL-nr. prioriteres foran beskrivelsesmatch; favoritter, projektartikler og seneste bruges kun som produktivitetsboost.
- Dansk søgetekst er mere tolerant over for å/aa/a, ø/o og 1½M/1,5M.
- Artikelpreviewet har Favorit-knap og direkte navigation mellem artikler i samme variantgruppe.
- Artikelpreviewet viser også hvilke globale styklister den valgte artikel indgår i.
- Den kompakte ArticlePicker har samme favorit-/seneste-/projektscopes og relevansrangering.
- Nyt filter 'Kun komplette data' kan skjule artikler med fejl/advarsler fra Datakvalitet.
- Artikelbasens tabel har en diskret favoritmarkering og ny separat layoutnøgle, så gamle kolonnebredder ikke forstyrrer det nye layout.
- Benchmarket mod 3.539 kernedata-artikler: søgeindeks ca. 0,3 s ved åbning, typiske søgninger ca. 7-13 ms.

## 0.59.28 - BOM UX, styklister og sporbarhed

- BOM-fanen har nu tre arbejdsvisninger: Artikler, Styklister / montager og Kilder.
- Artikellisten viser Kilde / stykliste direkte på hver samlet BOM-linje.
- Dynamisk gruppering efter rum, kategori, gruppe/kreds, stykliste/kilde eller fabrikat.
- Kollapsbare grupper viser antal artikler og summeret pris pr. gruppe.
- Hurtigfiltre for manglende pris, styklister, direkte/manuelle bidrag, kabler og advarsler.
- Ny BOM-sporbarhed viser hver konkret kilde: stykliste, symbol-del, Wago eller kabelstræk.
- 'Hvor kommer linjen fra?' åbner kilderne for den valgte artikel og kan navigere til én konkret forekomst på plantegningen.
- Styklistevisningen viser kun montager som faktisk bruges i det aktuelle rum/filter, med brugstal, rum, artikelindhold og pris.
- Excel/CSV har fået kolonnen Kilde / stykliste, og eksport følger det aktive hurtigfilter.
- Den autoritative build_bom-beregning er uændret; sporbarhed er et separat lag og kan derfor ikke dobbelttælle materialer.

## 0.59.27 - Korrekt pakningspris / stykpris

- Webshoppriser registrerer nu både rå salgs-pakkepris og normaliseret BOM-enhedspris.
- Pakke-/blisterstørrelser som 10, 12, 50 og 100 stk. udledes fra entydig URL/titel/pakningstekst.
- En WAGO-pakke til 331 kr. med 100 stk. bliver derfor 3,31 kr./stk. inkl. moms, ikke 331 kr./stk.
- Tvetydige variant-/pakningssider afvises i stedet for at gætte på stykprisen.
- Pris-cacheformat er hævet til v2, så gamle fejlagtige cachefund ikke genbruges.
- Prisbogformat er hævet til v4; gamle automatiske webshopestimater invalideres ved indlæsning, mens manuelle priser bevares.
- Prisdialogen viser både normaliseret enhedspris og rå pakningspris/pakningsstørrelse.

## 0.59.26 - Summeret pris i den aktuelle BOM-visning

- BOM-fanen viser nu en separat, tydelig **Summeret pris ekskl. moms (aktuel visning)** direkte under tabellen.
- Summen følger det aktive rumfilter og beregnes kun af de linjer, der vises i den aktuelle BOM.
- Hvis en eller flere viste BOM-linjer mangler pris, markeres summen tydeligt som ufuldstændig med antal manglende prislinjer.
- Eksisterende linjesummer, prisstatus og eksport er uændret.

## 0.59.25 - Responsiv skalering af prisopdateringsdialog
- Dialogen **Opdatér webshoppriser** bruger nu et responsivt 2×2 valg-layout i stedet for fem knapper på én linje.
- Knaptekster klippes ikke længere ved større Windows DPI-/fontskalering.
- Minimumsstørrelse, tekstombrydning og knaphøjder er gjort DPI-robuste, og **Annuller** står separat.

## 0.59.25 - Multi-source webshoppriser og sikker prisestimering
- Ny **Opdatér priser…**-funktion i Artikeldatabasen med WATTOO, LavprisEL og Greenline som separate prisproviders.
- Prisopslag matcher konservativt på EAN først, derefter EL-nr. og til sidst producentens artikelnummer. Tekstlig lighed alene accepteres ikke som automatisk prismatch.
- Webshopobservationer gemmes separat pr. kilde med pris inkl. moms, omregnet pris ekskl. moms, URL, matchgrundlag, dato og pris-enhed. Elplans BOM-priser forbliver ekskl. moms.
- Automatisk estimat bruger median ved mindst tre valide kilder, gennemsnit ved to og én enkelt kilde med lav sikkerhed, når kun én sikker observation findes.
- Prisbogformatet er hævet til v3. Manuel prisoverride har fortsat altid prioritet og røres aldrig af webshopopdateringen; de automatiske observationer og estimatet kan opdateres uafhængigt.
- Prisdialogen viser de gemte webshopobservationer, og artikelpreview viser antal kilder samt estimatets sikkerhed.
- Prisopdatering kan begrænses til **Kun artikler i BOM**, **Kun uden pris**, **Forældede > 7 dage** eller **Alle artikler**. Hele databasen kræver ekstra bekræftelse.
- Alle webshopkald er sekventielle med ca. 1,0–1,8 sek. tilfældig pause, 24 timers cache og backoff ved HTTP 403/429/5xx. Allerede hentede observationer bevares i cache ved annullering.
- Kendte direkte produktlinks bruges før søgning. Webshop-søgning prøver offentlige søgeruter og accepterer kun den fundne produktside efter identitetsvalidering.
- Kernedataeksport bevarer prisbog v3 inklusive observationer og manuel pris.

## 0.59.23 - Prisestimat, manuel prisoverride og BOM-prisgrundlag
- Prisbog v2 adskiller `estimated_price` og `manual_price`. Manuel pris har altid prioritet, mens estimatet bevares separat og kan opdateres senere.
- Eksisterende prisbogsposter migreres automatisk: gamle `Manuel ...`-priser bliver manuelle overrides; øvrige priser bliver estimater.
- Prisdata gemmes globalt pr. artikel og separat fra LK-/producentmetadata, så LK-synkronisering aldrig overskriver en manuel pris.
- Prisdialogen viser både estimat og manuel pris med separate kilder/datoer samt tydelig anvendt pris. Pris pr. stk., m, rulle, pakke eller sæt understøttes.
- Artikeldatabase og standardbibliotek viser anvendt pris, Prisstatus, Priskilde og Pris opdateret. Estimater markeres med `~` i pris-kolonnen.
- BOM bruger den effektive pris og viser Prisstatus samt pris-enhed. Kabel med pris pr. meter beregnes på faktisk meterbehov, også når artikelens leveringsenhed er rulle.
- Excel/CSV-BOM eksporterer Estimeret pris, Manuel pris, Anvendt enhedspris, Pris pr., Prisstatus, Priskilde, Pris opdateret og Linjesum.
- Artikeludvekslingsformat v3 kan importere/eksportere kilde-estimater med valuta, pris-enhed, kilde og dato. Manuelle priser forbliver i den separate prisbog.

## 0.59.22 - Filtervenlig Excel-BOM pr. rum
- Excel-eksport ved **Alle rum** får en separat fane `BOM pr. rum`, hvor hver række har præcis ét konkret rum i kolonnen `Rum`. Excels almindelige tabel-filter kan derfor vælge fx kun Køkken, Gang eller Stue.
- Den eksisterende `BOM`-fane bevares som autoritativ samlet projekttotal. Det forhindrer dobbeltoptælling i totalen, når et symbol både ligger fysisk i ét rum og manuelt er tilføjet et ekstra BOM-rum.
- Rumfanens mængder beregnes med den eksisterende rum-BOM-logik. Kabler fordeles derfor efter den faktiske rutelængde i hvert rum, og manuelle ekstra BOM-rum respekteres.
- `Uden rum` får sin egen konkrete filterværdi på rumfanen. Ved eksport af ét allerede valgt rum oprettes den ekstra rumfane ikke, fordi hovedfanen allerede er entydig.

## 0.59.21 - Produktsemantik, familie/variant og eksplicit kompatibilitet
- Ny produktsemantisk model adskiller hvad en artikel **er** (`product_family`, `product_variant`) fra hvad den **kan bruges sammen med** (`compatibility`). Producentens/legacy `design_family` bevares som `design_family_raw` på dåser og bruges ikke længere som produktidentitet.
- LK FUGA AIR-dåser klassificeres efter produktidentitet. Almindelige forfra-, indstøbnings- og indmuringsdåser bliver `LK FUGA AIR / Standard`, AIR SLIM-forfradåser bliver `LK FUGA AIR / SLIM`, og brandsikre AIR-forfradåser får varianten `Brandsikker`.
- 504D3010/3015/3020/3025 er rettet som almindelig AIR/Standard. 504D3510/3515/3520/3525 holdes separat som AIR/SLIM. Den manglende 504D3020 er tilføjet til de medfølgende grunddata.
- Standard AIR indstøbnings-/indmuringsdåser kan have SLIM under struktureret kompatibilitet uden at blive klassificeret som SLIM. Betinget kompatibilitet bevares som note.
- Artikelbrowser, artikelvælger og redigering bruger Produktfamilie + Variant som primære facetter; kompatibilitet vises separat. Legacy Design er kun provenance.
- Variantgrupper bruger nu produktfamilie + egen variant og kan derfor ikke gruppere Standard og SLIM som samme identitet blot fordi de deler kompatible rammeserier.
- Datakvalitets-audit finder historiske tilfælde hvor kompatible designserier er blevet brugt som produktidentitet, blandede familie/variant-serier samt AIR-dåser med manglende/modstridende variant.
- JSON/CSV-udveksling bevarer produktfamilie, variant, struktureret kompatibilitet og semantisk provenance.

## 0.59.20 - Skånsom LK-synkronisering og rate-limit-beskyttelse
- Alle kald til LK.dk er nu sekventielle. Produktdetaljer, kategoritræ og fallback-probing bruger højst én forbindelse ad gangen; `workers`-parameteren bevares kun af hensyn til bagudkompatibilitet og tvinges til 1.
- Der indsættes som standard en tilfældig pause på ca. 0,8–1,5 sek. mellem netværkskald, så trafikken ikke kommer i bursts.
- Normal synkronisering genbruger produktsider/databaseposter i op til 14 dage og katalogindekset i op til 24 timer. Cacheformat v2 migreres direkte til v3, så eksisterende cache ikke kasseres ved opgradering.
- HTTP 403, 429 og 5xx håndteres centralt med stigende backoff (5 s → 15 s → 45 s → 120 s) og respekt for `Retry-After`. Hvis LK fortsat afviser trafikken, stoppes hele synkroniseringen i stedet for at fortsætte gennem resten af kataloget.
- Synkroniseringsdialogen viser tydeligt, når LK begrænser trafikken, og forklarer at databasen ikke ændres ved en afbrudt synkronisering.
- Nyt persistent checkpoint gemmer færdige referencer undervejs. En afbrudt fuld genhentning kan derfor fortsætte senere og genbruge de produktsider, der allerede blev hentet før blokeringen.
- Et friskt katalogindeks kan genbruges selv ved fuld genhentning; produktsiderne genhentes stadig. Det reducerer unødige kategori-kald ved genoptagelse.
- Hvis selve LK-katalogets startside ikke kan hentes, stoppes synkroniseringen straks. Programmet starter ikke længere en fallback-probe over hundredvis af kategorier ved en generel netværks-/DNS-fejl.
- Synkroniseringsresultatet viser nu forbindelseantal, pauseinterval, rate-limit-hændelser, samlet backoff og antal poster genbrugt fra checkpoint.

## 0.59.19 - Artikelrelationer, variantgrupper og struktureret datakvalitet
- Artikeldatabasen har fået en kontrolleret, producentuafhængig standardtaksonomi ved siden af producentens originale kategori. LK FUGA, OPUS, IHC, Actassi/Lexcom, KNX, Nordtronic, WAGO og kabler placeres i stabile hoved-/underkategorier uden at overskrive kildedata.
- Artikler får strukturerede tekniske egenskaber (`technical_specs`) udledt konservativt fra eksplicitte felter og tydelig producenttekst. Manuelt verificerede værdier gemmes separat som overrides og vinder over automatisk udledning.
- Variantgrupper bygges automatisk ud fra producent, serie, type/design, modul og et renset grundproduktnavn. Farve/CCT/montage vises som variantakser; grupper kan tilsidesættes manuelt.
- Ny "Relationer…"-dialog viser varianter, bekræftede relationer og særskilte kompatibilitetsforslag. Forslag gemmes aldrig automatisk som kompatibilitet; brugeren skal aktivt bekræfte dem.
- Relationsforslag prioriterer eksplicitte systemnavne i producentteksten over importerede serie-/designfelter, så fx CLIC'LINE ikke foreslås som FUGA-kompatibelt på grund af stale metadata.
- Bekræftede artikelrelationer understøtter kompatibilitet, tilbehør, krav, erstatning, alternativ og del-af. Relationer opdateres ved omdøbning og fjernes sikkert ved sletning af målartiklen.
- Artikelvælger og Artikeldatabase kan filtrere på standardkategori og viser kategori, funktion, tekniske egenskaber samt variantkontekst direkte i preview.
- Datakvalitets-audit validerer nu også standardkategori, strukturerede egenskaber, variantgrupper og relationers målartikler. Hver artikel får en transparent score 0-100 samt status God/Kontrollér/Kræver kontrol.
- Artikelbibliotekets JSON/CSV-udvekslingsformat er hævet til version 2 og kan bevare manuelle tekniske egenskaber, variantgruppe-overrides og bekræftede relationer. Artikeldatabasens interne skemaversion er tilsvarende hævet til 2; version 1 indlæses fortsat automatisk.

## 0.59.18 - Robust LK-import og kildedatanormalisering
- LK-synkroniseringen har fået et separat konservativt normaliseringslag mellem webparser og artikeldatabase.
- Billed-/webaktiver som `_1`, `_2`, `_web`, `_angle` og `_image` afvises som produktreferencer og kan ikke længere oprettes som artikler.
- Produktnummeret fra et eksplicit `vnr`-kald prioriteres over nabo-/varianttekst på LK-siden, så variantdata ikke fejltilknyttes et andet varenummer.
- Farve læses først fra det dedikerede producentfelt, ensrettes til en stabil taksonomi og webtekst som `LK nummer ... Kopier`, kabellængder og konfigurationer afvises som farver.
- Materialeord som stål/kobber bliver ikke automatisk farve i ældre poster; verificerede design-/finishfelter bevares. Rå producentfarve kan bevares i `color_raw`.
- Moduldata valideres konservativt. Mål, meterdata og værdier som `451200M`/`600x400M` fjernes fra `module_size`; dokumenterede FUGA-værdier samt Resi9 `Nx13M`/`Nx18M` accepteres. Rå ugyldige værdier kan bevares i `module_size_raw`.
- En LK-sync rydder samtidig kendt forurening i eksisterende LK-poster før merge, men ændrer ikke brugerens egne/manuelle artikler.
- LK-cacheformatet er hævet, så gamle forurenede cacheposter ikke genindføres efter opgradering.
- Beskrivelser får kun teknisk spacing-normalisering; producentens nomenklatur omskrives ikke.

## 0.59.17 - Artikeldata-audit og konservative facetter
- Ny ikke-destruktiv Datakvalitet-fane i Artikler og BOM med audit af aktiv database eller medfølgende grunddata.
- Audit finder bl.a. ugyldige moduler, farvevarianter, manglende EAN/EL-LM/billeder, dublerede identiteter, statusspredning og overlappende kategorier.
- Modulfortolkningen accepterer nu kun plausible modulværdier; mål og produktnumre som 100 m / 451200M bliver ikke længere til modulfiltre.
- Farvefilteret samler kun trivielle stave-/spacingvarianter og bevarer producentens rå farvebetegnelse.
- Antracit mappes ikke længere automatisk til Koksgrå; producentens farvebegreb bevares.
- Audit kan eksporteres som CSV og ændrer aldrig artikeldata automatisk.

## 0.59.16 - Projektkontrol, rum-dashboard og BOM ↔ plantegning
- Ny Projektkontrol finder manglende BOM-artikler, kabelartikler/-typer, PL-ledere uden funktion, kabler uden ekstra mærkning og symboler uden for rum. Dobbeltklik/Gå til zoomer direkte til objektet.
- Nyt Rum-dashboard viser fysiske symboler, ekstra BOM-symboler, afbrydere, stikkontakter, lampesteder, spots, grupper/kredse, kabler/kabellængde og den aktuelle rum-BOM.
- Rum kan fokuseres direkte fra dashboardet; øvrige el-objekter dæmpes uden at ændre lag eller projektdata.
- BOM-rækker kan nu dobbeltklikkes eller vælges med "Vis på plan" for at fremhæve alle konkrete symbol-/kabelforekomster bag artiklen.
- Symboler kan få additive "Ekstra BOM-rum". Det fysiske rum og gruppe/kreds ændres ikke, og "Alle rum" dobbelttæller aldrig artiklen.
- Rumfiltreret BOM, CSV og Excel respekterer de ekstra BOM-rum.

## 0.59.15 - Formateret Excel-eksport af BOM
- BOM kan nu eksporteres direkte som `.xlsx` ved siden af den eksisterende CSV-eksport.
- Excel-arket indeholder en rigtig Excel-tabel med autofilter, fastfrosset tabeloverskrift, tilpassede kolonnebredder og numeriske antal-/prisfelter.
- Det aktive rumfilter og den valgte BOM-sortering følger med i både Excel- og CSV-eksport.
- Ikke-tilknyttede symboldele/kabelstræk placeres på et separat `Ikke tilknyttet`-ark i Excel-filen.
- Eksporten er dependency-free og kræver ikke lokal Excel/Office-installation.

## 0.59.14 - Wago-valgvindue polish
- Wago-valget i PL-dåsekonfiguratoren er opdelt visuelt i WAGO 221 og WAGO 2273 / P100.
- Hver variant viser produktpreview, antal tilslutningspunkter og om den passer til den aktuelle samling.
- For små varianter forbliver synlige som kapacitetsvejledning, men kan ikke vælges ved en fejl.
- Højresiden viser valgt artikel, kapacitet, aktuelt behov og ledig reserve samt et ét-kliks valg af standardanbefalingen.
- 2273/P100 forklares eksplicit som PUSH WIRE til massive/entrådede ledere; standardanbefalingen forbliver 221-serien.


## 0.59.13 - WAGO 221-billeder og 2273-valg i PL-boks
- Tilføjet indbyggede artikelpreview-billeder for WAGO 221-serien samt lokal billed-fallback i artikel/BOM-preview.
- Tilføjet indbyggede preview-billeder for WAGO 2273 / P100-serien.
- WAGO 2273 / P100 kan nu vælges direkte som artikel i PL-dåsekonfiguratorens Wago-dialog.
- Standardanbefalinger bevarer 221-serien som default af hensyn til bagudkompatibilitet.

# 0.59.12

- BOM har fået et egentligt **Vis rum**-filter: **Alle rum** bevarer den normale samlede BOM, mens et valgt rum viser og summerer kun de bidrag, der fysisk hører til rummet.
- Symbol-/Wago-artikler filtreres efter placeringspunkt; kabelartikler fordeles efter den faktiske del af kabelruten inde i rummets polygon i stedet for at tælle hele kablet i hvert rum.
- Nyt **Uden rum**-valg viser artikler og kabellængder uden for definerede rum.
- BOM CSV-eksport følger det aktive rumfilter. Rum-sortering og hover-billedpreview bevares.
- Artikeldatabasen er udvidet med WAGO 2273/P100: 2273-202, 2273-203, 2273-204, 2273-205 og 2273-208 med LM-/EAN-data, links og officielle WAGO-billeder.
- Eksisterende WAGO 221-412, 221-413, 221-415 og 221-420 har fået officielle WAGO-produktbilleder; 221-412/-413/-415 har også verificerede LM-numre.
- Ingen projektschemamigration; rumfiltreringen beregnes dynamisk.

# 0.59.11

- BOM-listen har fået et egentligt **Rum**-felt. En samlet artikellinje viser alle definerede rum, som bidrager til artikelnummeret; kabelartikler bruger de rum, som det fysiske kabel faktisk løber igennem.
- Nyt **Sortér efter**-felt i BOM med bl.a. Rum, Artikelnummer, Beskrivelse og Fabrikat. Sortering ændrer ikke BOM-mængder eller artikelgruppering.
- Hover kort over en BOM-linje viser et produktbillede ved cursoren efter en kort forsinkelse. Popup'en bruger den eksisterende artikelbilled-cache/online-fallback og tager hverken fokus eller museklik.
- BOM CSV-eksport har fået en **Rum**-kolonne med samme rumkontekst som UI'et.
- Ingen projektschemamigration; rumoplysninger beregnes dynamisk ud fra eksisterende rum-, symbol-, kabel- og artikelbindinger.

# 0.59.10

- Ny tydelig **Samlemuffe / sløjfe**-handling i PL-lederfordelingen til at samle kabelledere uden forbindelse til lampeudtaget.
- Hovedvisningen skelner nu mellem **+ Wago → udtag** og **+ Samlemuffe / sløjfe**.
- Højreklik på terminal/funktion kan oprette enten en Wago med bro til udtaget eller en ren samlemuffe uden bro.
- **Administrér Wago…** har separate oprettelsesmenuer for Wago → udtag og samlemuffe/sløjfe.
- Ren samlemuffe vises som **SAMLEMUFFE** / **ingen udtag** og bruger ingen terminalplads på lampeudtaget.
- Wago-editoren kan senere aktivt ændre en samlemuffe til en samling med bro til udtaget; intet ændres automatisk.
- Ingen ændring af projektschema eller `pl_box_splices`; 0.59.9 er direkte rollback.

# 0.59.9

- Wago-håndtering i PL-lederfordelingen er nu funktionsbaseret: højreklik på terminalen eller arbejd direkte fra den valgte leder.
- Drop af leder på en terminal med eksisterende Wago giver eksplicit valg mellem **Direkte**, **Via eksisterende Wago** og **Opret ny Wago**.
- Drop direkte på Wago og højreklik på leder/Wago er gjort mere målrettet; klik på en Wago uden valgt leder åbner redigering.
- Den gamle Wago-dropdown er fjernet fra hovedvisningen og erstattet af kompakt kapacitetsstatus, **+ Wago for valgt funktion** og **Administrér Wago…**.
- Wago-grafikken viser nu funktion, lederantal, bro/sløjfe, artikel og anvendte/tilgængelige Wago-pladser.
- Kapacitetsadvarslen bruger en konkret handling som **Opret Wago N og forbind**; intet oprettes uden brugerens godkendelse.
- Wago-redigeringsdialogen er sprogligt forenklet og tager udgangspunkt i den elektriske funktion.
- Ingen ændring af projektschema eller Wago-datastruktur; 0.59.8 er direkte rollback.

# 0.59.8

- PL-lederfordeling: kabelkort har nu en separat tekstzone og lederzone, så lederstumper ikke overlapper kabelmærkning.
- Kabelmærkning har fortsat højeste prioritet; kategori/type/side samles i en kompakt footer og må afkortes før mærkningen.
- Montagekontrol er reduceret til en kompakt statuslinje med **Vis kontrol** til tekniske detaljer.
- Ingen ændringer i Wago-logik, lederdata eller projektschema.
- 0.59.7 kan bruges direkte som rollback-version; projektfiler er kompatible begge veje for denne patch.

# 0.59.7

- PL-lederfordelingens seks kabelindføringskort prioriterer nu den fulde kabelmærkning.
- Kortene bruger mere af den disponible vandrette plads og bliver lidt højere på normale/store dialoger.
- Lange kabelmærkninger brydes intelligent over op til to linjer; ved ekstra lange mærkninger kan visningen gå til tre kompakte linjer og reducere fonten gradvist i stedet for at afkorte teksten.
- Den tidligere faste `display[:38]`-afkortning er fjernet. Kategori og kabeltype/ben bevares som sekundær information under mærkningen.
- Ingen ændringer i PL-forbindelser, kabeldata, BOM eller projektschema.

# 0.59.6

- Kabelmærkning foreslår nu lampestedernes egne mærkninger for fysiske kabler mellem to lampeudtag, når rummet ikke giver en fler-rums rute.
- Forslaget bruger kun `Placement.label`; gruppe/kreds ændres eller kopieres aldrig ind i den ekstra mærkning.
- Ved 0–1 gennemløbet rum prioriteres lampeudtagsforslaget; ved flere rum prioriteres fortsat den faktiske rumsekvens.
- Samme forslag bruges i direkte kabel-egenskaber, grafisk Mærk kabler og Kabeltræk → Mærkning.
- Forslag udfylder fortsat kun editoren og gemmes først ved brugerens eksplicitte Anvend.

# 0.59.5

- Rumtegning kombinerer nu CAD-væg-snap med vandret/lodret ortho-hjælp. Hvis den valgte væg kan skæres 0°/90° fra sidste rumhjørne tæt ved cursoren, bruges selve væg/akse-krydset, så punktet både ligger præcist på væggen og giver en præcis vandret/lodret rumlinje.
- Samme kombinerede væg/ortho-snap bruges ved efterfølgende redigering af rumhjørner. **Alt** slår ortho-hjælpen fra, men beholder CAD-væg-snap, så skrå rumlinjer fortsat er lette at lave.
- Hvert rum har nu en valgfri farvenuance. Nye rum får automatisk forskellige, rolige nuancer; eksisterende rum beholder deres nuværende farve.
- Rumdialogen har grafiske farveprøver. Nuancen bruges kun til rumtekst, omrids og redigeringshåndtag og påvirker ikke kabler, symboler, lag eller snap.
- Rumoversigten viser en lille farveprøve ved hvert rum, og rumdata/farve kan redigeres via rumtekst/konturens kontekstmenu.
- Tilføjet regressionstests for kombineret CAD-væg + ortho-snap og per-rum farvedata.

# 0.59.4

- Rettet crash/regression ved valg og redigering af eksisterende kabler efter oprydningen af kabelpanelet.
- Fjernet aktive referencer til de udfasede widgets `cable_selected_label` og `cable_dock`.
- Kabel-context-menuen åbner nu det fælles Egenskaber/Inspector-panel direkte.
- Kabelmærkning og tilknytning af lampested til eksisterende kabel lukker igen et aktivt kabeltegneflow korrekt.
- Tilføjet regressionstests for den unified cable inspector-arkitektur.

# 0.59.3

- Rumredigering er gjort mere direkte: dobbeltklik på en synlig rumkontur aktiverer redigering af netop det rum og viser hjørnehåndtagene.
- Når rumkonturen er skjult, åbner dobbeltklik på rumteksten i stedet afgrænsningsredigeringen. Dobbeltklik på teksten mens konturen er synlig beholder redigering af navn/mærkning.
- Ny blød vandret/lodret assistance ved både tegning af nye rum og flytning af eksisterende hjørnepunkter. Hjælpen bruger en skærmbaseret tolerance og viser cyan guides/snap-feedback.
- Skrå rumlinjer er fortsat fuldt understøttet: flyt uden for hjælpetolerancen eller hold **Alt** for eksplicit fri/skrå retning.
- Rigtige CAD-væg-snap har fortsat prioritet under rumskitse, og EL-RUM påvirker fortsat ikke symbol- eller kabelsnap.
- Synlige rumflader fanger ikke klik inde i rummet; hit-test er begrænset til selve konturen, så symboler og kabler under rumlaget fortsat kan vælges.

# 0.59.2

- Kabel-egenskaberne er ryddet op i to tydelige kontekster: **nyt kabel** og **valgt fysisk kabel**. Tegne-/snap-indstillinger skjules, når et eksisterende kabel redigeres.
- Ved valgt kabel står **Mærkning** først, efterfulgt af Kabeldata, Rute, Artikel/BOM og Længde. Avancerede visnings-/ID-data er foldet væk som standard.
- **Første kabel-ID** er fjernet fra normalvisningen. Programmet vælger fortsat automatisk næste ledige ID; den manuelle mulighed hedder nu **Start-ID** og findes kun under Avancerede kabeldata med en tydelig forklaring.
- **Automatisk mærkning** er omdøbt til **Vis kabel-ID + type på tegningen**, så den ikke forveksles med Ekstra mærkning.
- Ekstra mærkning er ikke længere en skjult standard for nye kabler. Nye kabler oprettes uden Ekstra mærkning; den sættes kun via en aktiv mærkningshandling.
- Kabelpanelet kræver ikke længere vandret scrolling: QFormLayout-rækker kan wrappe, den horisontale scrollbar er slået fra, og forslag til kabelmærkning vises i et responsivt 2-kolonne-grid med kompakte tekster/tooltips.
- Kabelpanelets UI er flyttet til `qt_cable_panel.py`, så `qt_app.py` forbliver mindre og lettere at vedligeholde.
- Ingen projektdatamigration.

# 0.59.1

- Når et eksisterende kabel markeres, vises nu en dedikeret **Mærkning**-sektion direkte i Egenskaber/Kabel-panelet.
- Aktuel **Ekstra mærkning** kan redigeres og gemmes med **Anvend mærkning** uden at aktivere den grafiske Mærk kabler-tilstand.
- Rum- og fra/til-forslag vises som chips; et klik udfylder kun feltet og ændrer intet før brugeren aktivt vælger **Anvend mærkning**.
- Den direkte handling bruger samme sikre label-only mekanisme som den grafiske arbejdsgang og kan derfor ikke ændre kabel-ID eller gruppe/kreds.
- Den grafiske **Mærk kabler**-tilstand og **Kabeltræk / ruteforløb → Mærkning** er bevaret uændret som supplerende workflows.
- Det gamle Ekstra mærkning-felt i den generelle Kabeldata-form skjules for eksisterende valgte kabler, så der kun er ét tydeligt sted at mærke dem; feltet bruges fortsat som standard for nye kabler.
- Ingen projektmigration; funktionen bruger fortsat det eksisterende `CablePlacement.label`-felt.

# 0.59.0

- Ny **Mærk kabler**-tilstand direkte på plantegningen. Den er opt-in og ændrer aldrig data automatisk.
- Fysiske kabler viser kun i mærkningstilstand en kompakt status-chip: `+` for umærket eller den eksisterende ekstra mærkning.
- Klik på et kabel åbner et ikke-modalt mærkningskort ved arbejdsområdet med låst kabel-ID, gruppe/kreds og fra→til-kontekst.
- Rum-, rum-ID- og fra/til-forslag fungerer kun som chips, der udfylder tekstfeltet. Først **Anvend** skriver til `CablePlacement.label`.
- **Spring over** navigerer uden ændring; valgfri **gå til næste umærkede** prioriterer kabler i samme gruppe/kreds.
- Højreklik på et kabel har nu **Mærk kabel…**.
- **Kabeltræk / ruteforløb** har fået fanen **Mærkning** med status, nuværende mærkning, forslag og direkte navigation til det fysiske kabel.
- Den normale valgte-kabel-badge undertrykkes i mærkningstilstand, så status-chip og editor ikke konkurrerer visuelt.
- Arbejdsgangen ændrer eksplicit ikke kabel-ID, gruppe/kreds, kabeltype, rute, artikel eller BOM.
- Ingen projektmigration; funktionen bruger det eksisterende `label`-felt.

# 0.58.4

- Eksisterende rumpolygoner kan nu åbnes direkte til geometri-redigering via **højreklik på rumteksten → Redigér afgrænsning**. Programmet aktiverer Rumredigering, viser polygonen og vælger rummet, så de trækbare hjørnepunkter vises med det samme.
- **Rumoversigt** har fået en separat **Redigér afgrænsning**-knap; dialogen lukkes automatisk, så polygonen kan redigeres direkte på plantegningen.
- Hvis en rumtekst allerede er valgt, går **Redigér rumafgrænsninger** direkte til den valgte polygon i stedet for kun at vise alle omrids.
- Dobbeltklik på en polygon i Rumredigering vælger dens geometri/hjørnepunkter; redigering af navn/mærkning er fortsat en separat handling.
- Hjørnetræk gemmes fortsat som Undo/Redo-kompatible ændringer i rummets `points`; rumtekst, kabeldata og symboldata påvirkes ikke.

# 0.58.3

- Rumtekst og rumafgrænsning har nu uafhængig synlighed: **Vis rumtekster** er til som standard, **Vis rumafgrænsninger** er fra som standard. Rumredigering viser kun afgrænsningen midlertidigt.
- Tegning af et nyt rum aktiverer ikke længere permanent Rumredigering; den færdige polygon kan derfor straks forblive skjult, mens teksten står tilbage.
- Semiautomatisk symbolnavngivning fra rum er fjernet. Symbolmærkninger forbliver brugerens ansvar.
- Ny **Mærk kabler efter rum…** analyserer hvert fysisk kabel geometrisk og foreslår kun den ekstra kabelmærkning. Ét rum giver fx `Køkken`; flere rum giver fx `Køkken → Gang → Stue`.
- Kabelmærkningsdialogen har preview, tre formater (rumnavn, rummærkning, begge) og beskytter eksisterende ekstra mærkninger som standard.
- Rumbaseret kabelmærkning ændrer eksplicit hverken `cable_id` eller `circuit_id` / gruppe-kreds.
- Rumoversigten viser nu både symbol- og kabelantal pr. rum.
- Geometrien bruger præcise kabel/rum-skæringer frem for fast sampling, så resultatet ikke afhænger af tegningens målestok.
- Ingen projektmigration; `room_labels_visible` er et valgfrit visningsvalg med standard `true`.

# 0.58.2

- Snap-isolering for rum: `EL-RUM` kan ikke bruges som væg-snap for symboler eller kabler.
- Defensivt værn i `QtSnapEngine`, så rumgeometri ignoreres selv hvis den ved en senere refaktor utilsigtet leveres som CAD-primitiv.
- Regressionstest bekræfter både, at en synlig/redigerbar rumkant ikke påvirker symbolplacering, og at snap til rigtige CAD-vægge fortsat virker.
- Ingen projektmigration eller ændring af rumdata.

# 0.58.1

- Rettet crash efter afslutning af rumskitse: rumdialogerne bruger nu den fælles keyword-baserede `configure_modern_dialog()` API korrekt.
- Rettet samme fejl i dialogerne for semiautomatisk mærkning og rumoversigt.
- Fjernet PySide6 `RuntimeWarning` fra toast-animationer ved at bruge én stabil `finished`-forbindelse i stedet for gentagne `disconnect/connect`.

## 0.58.0

- Nyt projektlag **EL-RUM** med brugerdefinerede rum som polygoner oven på CAD-plantegningen.
- **Rum**-værktøj i hovedværktøjslinjen: klik langs vægge, wall-snap, Enter/dobbeltklik/højreklik afslutter og Backspace fjerner seneste punkt.
- Rumnavn og valgfri mærkning gemmes pr. rum; rumteksten har egen koordinat og kan flyttes frit uden at ændre polygonen.
- Kun rumteksten er synlig som standard. Afgrænsninger vises i **Redigér rum** eller via **Vis rumafgrænsninger**.
- Valgt rumafgrænsning får trækbare hjørnehåndtag i redigeringstilstand; ændringer kan fortrydes/gentages.
- Ny **Rumoversigt** med zoom, redigering, sletning og symbolantal pr. rum.
- Ny semiautomatisk rummærkning: symboler findes geometrisk i rummet og kan få sekventielle mærkninger fra rummets prefix; eksisterende mærkninger bevares som standard.
- Symbol-hover og PL-hover kan vise hvilket rum objektet ligger i. Skitserede rum bruges også som førstevalg til at holde symbolmærkning på den rigtige side af væggen.
- Projektformatet udvides bagudkompatibelt med `rooms[]`; ældre projekter åbner med tomt rumlag.

## 0.57.5

- Kabel-hoverkortet har nu et separat, højkontrast **KABELMÆRKNING**-kort umiddelbart under overskriften. Kabel-ID/mærkning vises stort og tydeligt, og eventuel ekstra mærkning vises direkte nedenunder.
- Gruppe/kreds, fra→til, kategori, type og længde er fortsat sekundær information, så identifikationen ikke drukner i detaljerne.
- Hoverkortet vises fortsat ved den aktuelle museposition og følger cursoren langs kablet.
- Ingen ændring af kabeldata eller projektschema.

## 0.57.4

- PL-hoverkortets overskrift viser nu både gruppe/kreds og lampestedets mærkning, fx `PL-dåse · G11 · UDTAG-GANG-SOVE`, så dåsen kan identificeres direkte i overskriften.
- Artikeldatabasen er nu den primære arbejdsgang for symboltilknytning: dobbeltklik på en artikel tilknytter den direkte til den aktuelt valgte fysiske symbol-del.
- Artikeldatabasen viser et tydeligt destinationskort (`Tilknytter til: … → fysisk del`), antal pr. del samt en stor `Tilknyt valgt artikel`-knap.
- `Find i Artikeldatabase…` fra Tilknytning-fanen åbner den fulde søgbare database og fokuserer søgefeltet. Den gamle combo er kun bevaret som sekundært `Hurtigvalg`.
- Artikelredigering er gjort eksplicit via `Redigér artikel…`; dobbeltklik redigerer ikke længere kernedata ved et uheld.
- Hvis den valgte del bruger en stykliste, spørger direkte artikeltilknytning før den skifter til manuel konfiguration. Kabelartikler afvises tydeligt og henvises til Kabler-fanen.
- Ingen projektschemamigration; eksisterende `placement_articles` / `placement_assemblies` bruges uændret.

## 0.57.3

- Rettet hover-regression efter modulopdeling: `QCursor` importeres nu korrekt i `qt_hover.py`, så de grafiske symbol-/PL-hoverkort faktisk kan vises igen.
- Symbol- og PL-hoverkort må igen vises under almindelig symbolplacering; drag, kabeltegning, tekst/pattern/calibrering, tilhørsforhold og åbne context-menuer undertrykker stadig popup sikkert.
- Kabel-hoverkort åbner hurtigere og placeres ved den aktuelle museposition. Mens musen bevæges langs kablet følger popup-kortet cursoren og holdes inden for skærmens arbejdsområde.
- Det tidligere in-scene kabelbadge vises ikke længere ved almindelig hover, så informationen ikke duplikeres. Ved valgt kabel kan selection-badget fortsat vises.
- Den flydende kabelkategori-chipbjælke er fjernet fra canvas. `Vis → Kabelkategorier` er fortsat den entydige vis/skjul-kontrol.
- Ingen ændring af projekt-, kabel-, PL- eller BOM-schema.

## 0.57.2

- Navigator/mini-kort er nu skjult som standard og renderer kun CAD-linjer, fysiske kabler, små symbolmarkører og den aktuelle viewport. Tekst, mærkninger og øvrige screen-space overlays tegnes ikke i navigatoren.
- De eksisterende hover-popups for symboler og PL-lampesteder er gendannet også for valgte objekter. Drag, aktiv tegnearbejdsgang og context-menu undertrykker fortsat popup sikkert.
- Ekstra kabelmærkning er fjernet fra den permanente kabeltekst på plantegning/print og vises i stedet i kabel-hover sammen med ID, type, gruppe/kreds, længde og endepunkter. Datafeltet er uændret og kan fortsat redigeres i Egenskaber.

# 0.57.1

- PL-dåsekonfigurator: lederfordelingen er nu den tydelige primære arbejdsflade.
- Tændleder-overblik er sammenklappet som standard til en ca. 42 px kompakt hjælpelinje og kan foldes ud efter behov.
- Lederdiagrammet har større minimumshøjde.
- Lampeudtagets terminalpanel har én overskrift og en kort terminalforklaring; fuld produkttekst findes som tooltip.
- Nederste valgstatus har sin egen reserverede zone og kolliderer ikke længere med kabelindføring 4-6.
- Ekstern/duplikeret ledervalgstekst over diagrammet er fjernet fra layoutet.
- Lederfarve-reference vises kun sammen med den avancerede tabel.
- Ingen ændring af elektrisk model, PL-ledningsdata, Wago, kabelmodel eller BOM.

# 0.57.0

## Visual interaction / “bling”

- Kabler får en diskret animeret flow-markering ved hover, valg og aktiv gruppesporing.
- Symbolvalg giver en kort selection-pulse ud over den eksisterende vedvarende glow.
- Snap-punkter får en kort skærmfast “pop”-animation, så magnetisk snap er tydeligt uden at forstyrre tegningen.
- Gruppefokus afsløres sekventielt fra tavle/ende gennem kabelnettet; **Spor valgt gruppe** kan holde flowet aktivt gennem kredsen.
- Kabel-hover viser et flydende badge med kabel-ID, type, beregnet længde og gruppe/kreds.
- Smart symbol-tooltip er udvidet til alle almindelige symboler, men undertrykkes ved selection, drag, aktivt tegneværktøj, mouse-grab og åben kontekstmenu/pop-up, så den ikke kolliderer med eksisterende funktioner eller Egenskaber-panelet.
- **Zoom til valg** animerer viewporten roligt til valgt kabel/symbol/multivalg.
- Ny valgfri **Navigator / mini-kort** viser hele CAD-scenen samt den aktuelle viewport og kan bruges til hurtig navigation.
- Status-toasts glider/fader nu diskret ind og ud.
- PL-dåsekonfiguratoren har valgfri **Eksploderet visning** og animerer en ny manuel lederforbindelse ind på diagrammet. Der oprettes fortsat ingen forbindelser automatisk.
- Flydende workspace-elementer har fået en subtil elevation/depth, mens selve CAD-tegningen forbliver flad og teknisk.
- Hover/tooltip-controlleren er flyttet til `qt_hover.py`, så `qt_app.py` fortsat holdes under arkitekturgrænsen.
- Ingen ændring af projektets elektriske/BOM-datamodel; visuelle transienter gemmes ikke.

# 0.56.2

- Tilføjet **Nordtronic 98425033 – Lampeudtag med Zigbee lysdæmper** til den indbyggede artikeldatabase med EAN 5704629006065, producentlinks og tekniske metadata.
- Ny PL-udtagstype **Nordtronic lampeudtag m. Zigbee dimmer** med fysiske terminaler **P, COM, PE, N, ~ og L**.
- Lampestedets eksisterende tændings-/tilhørsforhold vises fysisk på **P-inputtet**; COM og dæmpet udgang er egne manuelle funktioner.
- Avanceret ledertabel og Wago-/montagevisning forstår de nye COM- og dæmpet-udgangsfunktioner.
- Lampeudtag kan nu få en **valgfri eksplicit BOM-artikel**. Ingen artikel tildeles automatisk, og ubundne lampeudtag giver ingen ny manglende-BOM-advarsel.
- Den neutrale PL-start er uændret: ingen PE/N/L/P/COM/~ forbindes automatisk.
- Ingen projektschemaændring ud over versionsstemplet; eksisterende `lamp_outlet_type`-felt bruges til den nye profil.

# 0.56.1

- Ny flydende **kabelkategori-chiplinje** direkte på tegnefladen. Hver chip viser kategoriens farve/kontur og tydelig vist/skjult tilstand og styrer de eksisterende kategori-lag.
- Kabeltræk-overblikket har fået en ny **Flow**-fane som standard med klikbare installationsnoder, bløde forbindelser og kabel-ID/type/længde pr. fysisk stræk. Forgreninger vises grafisk i stedet for kun som tabel/trætekst.
- PL-dåsekonfiguratorens ledergrafik har fået fysisk montageside, indvendig kant, montagepunkter, kategoriaccent på kabelkort, separat lampeudtag og `x/y FORDELT`-status.
- PL-lederplanens neutrale start er bevaret og gjort eksplicit i grafikken: ingen forbindelser laves automatisk.
- Korte **120–150 ms** hover-/selection-animationer på kabler og symboler samt diskret fade-in af inspector-summary. Animationer er rent visuelle.
- Ingen projektschemaændring ud over versionsstemplet.

# 0.56.0

- Ny flydende **arbejdsgangslinje** på tegnefladen for kabeltegning, symbolplacering, tekst, spots, kalibrering og lystilhørsforhold.
- Kabelarbejdsgangen viser live gruppe/kreds, kabeltype, kabel-ID samt antal punkter/tilslutninger og har direkte **Fortryd punkt**, **Afslut kabel** og **Esc**.
- Valgt kabel får kosmetisk halo og tydelige endepunktsmarkører; samme gruppe/kreds vises som sekundær kontekst, mens resten af installationen tones ned.
- Nyt kompakt summary-kort i Egenskaber-panelet viser kabel-ID, fra→til, gruppe/kreds, kabeltype og længde eller tilsvarende symbolidentifikation.
- Ny **Fokusér valgt gruppe** (`Ctrl+Shift+F`) fra Vis-menu og kontekstværktøjslinje. Fokus er rent visuelt og gemmes ikke i projektdata.
- Gruppefokus nulstilles ved åbning af et andet projekt/CAD, men overlever almindelig scene-refresh i det aktuelle projekt.
- Visuel workspace-logik er isoleret i `qt_visual_workspace.py`; `qt_app.py` holdes fortsat under arkitekturgrænsen på 6.200 linjer.
- Ingen projektschemaændring ud over versionsstemplet.

# 0.55.3

- **Vis → Kabelkategorier** viser nu tilstanden eksplicit som `VIST` / `SKJULT` på hver kategori i stedet for at være afhængig af Qt/Windows-menuens svagt synlige checkmark.
- Undermenuens titel viser samtidig et samlet overblik som fx `Kabelkategorier (8/11 vist)`.
- Tilstandsteksten opdateres straks ved klik, og tooltip viser også den aktuelle synlighed. Kategoriens farveikon bevares.
- Ingen ændring af kabeldata eller projektschema ud over versionsstemplet.

# 0.55.2

- Nyt **Kabeltræk / ruteforløb** under Værktøjer. Overblikket afledes direkte af de fysiske 0.55-kabler og gemmer ingen parallel rutedatabase.
- Ny **Træ**-visning grupperer efter gruppe/kreds, vælger gruppetavle/fordelingstavle som naturlig rod og viser forgreninger uden at flade dem ud til én kunstig kabelstreng.
- Ny **Liste**-visning viser læsbare ruter som `Tavle → PL01 → PL02 → PL03`, én række pr. ende/forgrening, med kabel-ID'er, kabeltyper og længde når tegningens skala er kendt.
- Klik på en gruppe eller rute fremhæver de tilsvarende fysiske kabelsegmenter på plantegningen; dialogen er modeless og kan derfor stå åben under arbejdet.
- Søgning og gruppefilter gør det muligt hurtigt at finde et lampested, kabel-ID, kabeltype eller gruppe/kreds. Ruter kan kopieres enkeltvis eller samlet som tekst.
- Frie kabelender, flere adskilte delnet i samme gruppe og ring/sløjfe-forløb håndteres eksplicit, så visningen ikke mister kabler eller går i loop.
- Kabeltræk-overblikket opdateres automatisk, når fysiske kabler tilføjes, slettes eller redigeres, mens dialogen er åben.
- Ingen projektschemaændring ud over versionsstemplet; funktionen er en ren afledt visning.

# 0.55.1

- PL-dåsens lederfordeling starter nu helt ufordelt. Ingen ledere, heller ikke PE eller blå N, forbindes automatisk ved første åbning.
- Eksisterende gemte lederforbindelser bevares uændret ved projektåbning.
- Knappen `Sæt standard PE/N` er fjernet fra konfiguratoren, så alle forbindelser oprettes bevidst af brugeren.
- `Nulstil lederplan` rydder nu alle lederfunktioner og Wago-samlinger i stedet for at genetablere PE/N.

# 0.55.0
- Ny kabeldomænemodel: ét `CablePlacement` repræsenterer nu ét fysisk kabel mellem højst to installationspunkter.
- En sammenhængende tegnehandling som `Tavle → PL01 → PL02 → PL03` opretter automatisk tre selvstændige kabler i én Undo-handling.
- Nyt `circuit_id` holder gruppe/kreds fælles for den logiske kabelstreng, mens `route_chain_uid` kobler de segmenter sammen, som blev tegnet i samme arbejdsgang.
- Kabeltype, artikelbinding, rute og længde kan konfigureres individuelt pr. fysisk kabel. Gruppe/kreds opdateres samlet på samme tegnede streng.
- Kabel-ID'er tildeles individuelt og fortløbende; migration reserverer eksisterende ID'er for at undgå kollisioner.
- BOM-kabelvælgeren viser fysisk kabel-ID, gruppe/kreds, fra→til, kabeltype og længde. Artikelbinding er fortsat eksplicit pr. kabel-UID.
- Kabellængderapporten viser nu **Gruppe/kreds** og **Fra → til** for hvert fysisk kabel.
- PL-dåsevisningen medtager gruppe/kreds og behandler nye indgående/udgående kabler som separate kabelender.
- Automatisk migration af gamle flerpunkt-kabler: lokal kabeltype/ruteføring materialiseres på de nye fysiske kabler, og PL-indføringer, lederfordeling samt Wago-medlemmer remappes til nye kabel-UID'er.
- En ensartet gammel kabelartikel kopieres til alle migrerede segmenter; ved gamle blandede kabeltyper nulstilles den tvetydige fælles artikelbinding i stedet for at gætte.
- Global søgning indekserer nu også kabelgruppe/kreds og fra→til.
- Regressionspakke: 401 beståede tests, 11 Qt-runtime-tests skipped i miljø uden PySide6.

# 0.54.3
- Større vedligeholdelses-/arkitekturpas uden projektformatændring.
- Artikelbibliotek, artikelvælger og BOM-dialoger er flyttet fra `qt_app.py` til `qt_articles.py`.
- PL-dåsekonfigurator, kabelindføringsgrafik og lederfordelingsgrafik er flyttet til `qt_pl_box.py`.
- Fælles deterministiske Qt-kontroller og små widget-hjælpere er flyttet til `qt_widgets.py`, så featuremoduler ikke behøver afhænge af hovedvinduet.
- `qt_app.py` er reduceret fra ca. 10.800 til ca. 6.000 linjer.
- Artikel/BOM- og PL-moduler lazy-loades først, når funktionerne åbnes; artikel-/netværksimports fjernes derfor fra normal hovedvinduesopstart.
- Nye arkitekturtests beskytter modulgrænserne, lazy loading og størrelsesgrænsen for `qt_app.py`.
- Hele regressionspakken er opdateret til de nye modulgrænser.

# 0.54.2
- Nyt **Kabeltype pr. afsnit**: samme kabel kan fx være 3G1,5 frem til et lampested og 5G1,5 videre til det næste uden at resten af kabelstrækningen ændres.
- Kabelværktøjets tidligere *Ruteføring pr. afsnit* er udvidet til **Indstillinger pr. afsnit** med både lokal ruteføring og lokal kabeltype.
- Afsnitsvælgeren viser gruppe/kreds + mærkning, effektiv kabeltype og ruteføring; højreklik direkte på kabelstrækket giver samme kabeltypegenvej.
- Nyt valgfrit `CablePlacement.spec_section_overrides`, lagret med stabile symbol-UID/port-par og global `cable_spec` som fallback/default.
- PL-dåsekonfigurator og lederfordeling bruger effektiv kabeltype pr. kabelben; en 3G→5G-overgang kan derfor have forskelligt antal/farver ledere på de to indføringer.
- Blandede kabeltyper får diskrete type-labels pr. fysisk afsnit på tegning samt i PDF/print/DXF.
- Kabellængderapportens materialesummer opdeler nu meter efter effektiv kabeltype.
- BOM er konservativ ved blandede kabeltyper: én global kabelartikel tælles ikke fejlagtigt over hele ruten; meter pr. type rapporteres i stedet som manglende afsnitsvis artikeltilknytning.

# 0.54.1
- Rettet zoom-regression efter 0.54.0-startsiden: `fitInView()` køres nu først efter at tegnefladen er den synlige side i det centrale workspace, så Windows ikke efterlader en stale/fejlskaleret transform, der kan blokere zoom ind.
- Zoomlogikken er samlet i `CadGraphicsView.zoom_by_factor()` og bruges både af musehjul og tastatur, med faste grænser og korrekt cursor-/centerankring.
- Nye genveje **Ctrl++ / Ctrl+=** for Zoom ind og **Ctrl+-** for Zoom ud; de findes også under Vis.
- Nyt fuld-vindue **Åbner projekt…**-overlay med projektnavn, aktuel indlæsningsfase og indeterminate progressbar. Brugeren kan ikke længere være i tvivl om, at programmet arbejder.
- Indlæsningsfeedback følger nu faserne projektfil → CAD-data → lag/geometri → sceneopbygning og bruges også ved direkte åbning af DWG/DXF.
- Projekt-/CAD-åbningsflowet er flyttet til `qt_project_open.py`, så `qt_app.py` fortsat holdes under vedligeholdelsesgrænsen.
- Ingen projektformatændring.

# 0.54.0
- Ny **Ctrl+F** global søgning efter gruppe/kreds, mærkning, kabel-ID, kabelmærkning, kabeltype og fritekst; valgt resultat markeres og centreres på tegningen.
- Ny **Ctrl+Shift+P** kommando-palette kombinerer objektsøgning med almindelige programhandlinger som Gem, Kabelværktøj, PL-rapport, BOM og kabelkategorier.
- Ny startside med Åbn projekt, Nyt fra DWG/DXF og seneste projekter; kan åbnes igen via Vis → Startside uden at lukke aktiv tegning.
- Progressive fold-ud sektioner reducerer støj i inspector: symbolernes udseende/placering samt kabelvisning og længde/rapport vises kun efter behov.
- Fælles dialogfundament anvendes nu på Artikelvælger, Artikler/BOM, PL-dåse og Kabelkategorier med ensartet header, spacing og light/dark styling.
- Små ikke-modale toast-beskeder bruges til succesfeedback ved bl.a. Gem, BOM-opdatering, kabeltilknytning, lokal kabelruteføring og nulstilling af panel-layout.
- Fælles tabeller får flytbare kolonner, dobbelklik på overskrift for auto-fit samt højreklik på tabeloverskriften for Tilpas/Nulstil kolonner.
- Hover-BOM caches pr. symbol og invalides ved projekt/BOM/PL-ændringer, så gentagne hover-opslag er billigere.
- Nye moduler `qt_search.py`, `qt_welcome.py` og `qt_feedback.py` holder søgning, startside og feedback ude af `qt_app.py`.
- Ingen projektformatændring.

# 0.53.0
- Nyt fælles GUI-fundament i `qt_ui.py` med standardiserede marginer, spacing, panelbredder og hjælpefunktioner til paneler, formularer og docks.
- Hovedværktøjslinjen er reduceret til de vigtigste globale handlinger, så tegnefladen får mere visuel ro.
- Ny kontekstuel værktøjslinje skifter automatisk efter valg: kabel får bl.a. kategori/ruteføring, symbol får relevante symbolhandlinger, multivalg får fælles handlinger, og tomt valg får generelle tegneværktøjer.
- Kategori- og global ruteføringsændring fra kontekstlinjen er Undo/Redo-kompatibel; global ruteføring rydder bevidst lokale afsnits-overrides på samme måde som Kabelværktøjets globale valg.
- Symbol-/objektegenskaber og kabeldata er samlet i én højre **Egenskaber**-inspector med kontekstafhængige sider i stedet for to separate permanente docks.
- Valg af et eksisterende kabel viser kabelsiden uden at aktivere kabeltegnetilstand. Aktiv kabeltegning er nu en separat tilstand og kan afsluttes uden at skjule inspector-panelet.
- Symboler og Lag er fortsat docks i venstre side og kan tabbes/skjules; fælles dockopsætning er standardiseret.
- Vinduesgeometri, dockplacering og panelstørrelser gemmes maskinlokalt og gendannes ved næste start. Ny **Vis → Nulstil panel-layout** gendanner standardlayoutet.
- `qt_window_geometry` og `qt_window_state` er markeret maskinlokale og følger ikke med `.elplancore`-eksport/import.
- Nyt `qt_workspace.py` indeholder main-window chrome, inspector, kontekstværktøjslinje og layoutpersistens, så `qt_app.py` ikke vokser med GUI-fundamentet.
- Ingen projektformatændring.

# 0.52.7
- Rettet PL-dåsekonfiguratorens **Lederfordeling** på lave skærme: den grafiske lederplan tegnede tidligere altid efter mindst 620 px højde, selv om widgetten efter 0.52.4 kunne være lavere. Bundindføringer og nederste del af lampeudtaget blev derfor klippet.
- Lederdiagrammets geometri er nu reelt responsiv og bruger den faktiske tilgængelige højde. Kabelkort, PL-dåse, Wago-forløb og klemrække komprimeres kontrolleret, så hele arbejdsfladen forbliver synlig.
- **OK / Annuller / Anvend** forbliver samtidig faste nederst uden for fanens scrollområde.
- Minimumshøjden for lederdiagrammet er justeret til 470 px, mens større vinduer fortsat udnytter ekstra plads.
- Ingen projektformatændring.

# 0.52.6
- **Ruteføring pr. afsnit** viser nu både gruppe/kreds og mærkning for begge nabotilslutninger, fx `G11 · UDTAG-SOVE → G11 · UDTAG-GANG-VÆRELSER`.
- Samme tydelige identifikation bruges i kabellets højrekliksmenu og i statusbeskeder ved afsnitsvis rutekonvertering.
- Hvis kun ét af felterne findes, bruges det alene; dubletter undgås automatisk.
- Ingen projektformatændring.

# 0.52.5
- Rettet kritisk regression ved projektåbning: `CableSignals.contextRequested` manglede, fordi signalet ved en fejl var placeret i `ItemSignals`. Projekter med kabler kunne derfor fejle under opbygning af grafikscenen.
- `CableSignals` har nu igen det tre-argumenters kontekstsignal, som kabel-højreklik og afsnitsruteføring bruger.
- `ItemSignals` er samtidig korrigeret tilbage til sit to-argumenters symbol-kontekstsignal.
- Tilføjet regressionstest, som kontrollerer signalernes placering og signaturer, så fejlen ikke kan snige sig ind igen.
- Projektformatet er uændret.

# 0.52.4

- PL-dåsekonfiguratoren viser nu **gruppe/kreds + mærkning** sammen i den overordnede identifikation og i Tændleder-overblikkets aktuelle lampested.
- Tændlederanalysens referencer til andre lampesteder langs samme kabel bruger også begge felter, fx `G11 · T.V. BAD2`, så konflikt-/brugsinformation er entydig.
- PL-dåserapporten viser nu `Gruppe/kreds` og `Mærkning` som eksplicitte felter i hvert montagearks overskrift.
- Lederfordelingsfanen er lagt i et lodret scrollområde, så **OK / Annuller / Anvend** altid forbliver synlige uden for scrollområdet.
- PL-dialogens startstørrelse begrænses til skærmens faktiske arbejdsområde, og ledergrafikkens minimumshøjde er reduceret fra 610 til 470 px.
- Ingen projektformatændring.

# 0.52.3

- Et kabel kan nu have **blandet ruteføring**: et enkelt fysisk afsnit mellem to nabotilslutninger kan være Fri/diagonal, mens resten fx fortsat er Ortogonal (90°).
- Nyt **Ruteføring pr. afsnit** i Kabelværktøjets *Valgt kabel*, med navngivne connection-to-connection-afsnit og **Anvend på afsnit**.
- Højreklik direkte på et kabelafsnit giver hurtigvalg mellem **Fri / diagonal for dette afsnit** og **Ortogonal (90°) for dette afsnit**.
- Afsnitskonvertering ændrer kun geometrien mellem de valgte fysiske tilslutninger og remapper efterfølgende `symbol_connections`; øvrige kabelafsnit bevares.
- Kabellets globale `orthogonal` er fortsat standard. Global ændring i Kabelværktøjet betyder bevidst hele kablet og nulstiller lokale overrides.
- Nyt valgfrit `CablePlacement.route_section_modes`, lagret med stabile symbol-UID/port-par frem for polyline-indeks.
- Hvis et nyt lampested kobles ind midt i et lokalt overstyret afsnit, deles overriden automatisk og bevares på begge nye delafsnit.
- Manuelle knækpunkter i et lokalt afsnit følger afsnittets egen ruteføringsregel ved efterfølgende redigering.
- GUI-interaktionen er isoleret i `qt_cable_sections.py` som del af oprydningsretningen fra 0.52.0.

# 0.52.2

- Nyt **Tændleder-overblik** i PL-dåsekonfiguratorens Lederfordeling, som samler lederfarvernes funktion langs hele samme kabel på tværs af flere lampesteder.
- 7G/5G/3G-ledere vises visuelt med status som ledig tændleder, anvendt tænding, anden funktion, typisk forsyning eller konflikt.
- Gul/grøn, blå og brun prioriteres ikke som nye tændledere; anbefalingen vælger først blandt sort, grå, rød og hvid, når de findes og er ledige.
- Flere kabler i samme PL-dåse kan vælges direkte i overblikket; valg af en leder følger automatisk lederens kabel.
- Genbrug af samme farve til en **anden tænding** på samme kabel udløser en tydelig advarsel med kendte lampesteder. Typiske forsyningsledere giver også en bevidsthedsadvarsel ved tændledervalg.
- Ingen projektformatændring. Analyse og anbefaling beregnes fra eksisterende kabel- og `pl_box_wiring`-data.
- PL-hjælpen er isoleret i `qt_pl_usage.py`, så `qt_app.py` fortsat holdes under den arkitekturgrænse, der blev indført i 0.52.0.

# 0.52.1

- Nyt intuitivt workflow til at koble et **eksisterende lampested på et allerede tegnet kabel**: vælg lampested → *Tilknyt eksisterende kabel…* → klik direkte på kabelstrækningen. Samme handling findes via højreklik på lampestedet.
- Et lampested ved en fri kabelende bliver automatisk kabellets start/slut og giver dermed ét fysisk PL-kabelben; et lampested midt på ruten bliver en gennemgående forbindelse med to kabelben.
- Ortogonal routing bevares ved at indsætte lokale 90°-knæk; fri/diagonal routing føres direkte via lampestedets fysiske port. Eksisterende symboltilslutninger remappes og bevares.
- Ved stor afstand mellem kabelrute og lampested spørger programmet før kabelgeometrien trækkes hen til symbolet. **Esc** annullerer tilknytningsværktøjet.
- Tilknytningen er Undo/Redo-kompatibel og kræver ingen nye projektfelter. PL-dåsekonfiguratoren ser straks det nye kabelben, som derefter kan placeres i indføring 1-6.
- Ny funktion er isoleret i `qt_cable_attach.py`, så arkitektur-/oprydningsarbejdet fra 0.52.0 fortsat holder `qt_app.py` under den aftalte størrelsesgrænse.

# 0.52.0

- Første kontrollerede arkitektur-/oprydningspas: theme engine flyttet til `qt_theme.py`, hover-preview/popup til `qt_hover.py`; `qt_app.py` reduceret uden workflow-/projektformatbrud.
- Fjernet dubleret `MainWindow._cable_symbol_caption()` og tilføjet arkitekturtest mod dublerede MainWindow-metoder.
- Rettet eksisterende kabels **Ortogonal ↔ Fri/diagonal** skift: *Anvend ændringer* konverterer nu den faktiske centerlinje/geometri, ikke kun routing-flaget. Fysiske symboltilslutninger remappes og Undo gendanner den oprindelige rute.
- Kabelværktøjets ruteføringshjælp fortæller nu eksplicit, når et valgt eksisterende kabel vil få konverteret geometrien.
- Zoom-afhængige tunge rebuilds coalesces med 32 ms timer for roligere wheel/trackpad-zoom.
- Global artikeldatabase caches efter filidentitet/timestamp/størrelse; gentagne hover/BOM/opslag undgår unødig disk-I/O og normalisering, men returnerer fortsat defensive kopier.
- Light/dark/system og teknisk PDF/print-semantik er bevaret. Ingen nye obligatoriske projektfelter.

# 0.51.1

- Rettet PL-dåsefejl hvor **Ny Wago…** kunne blive grå efter at de tilgængelige funktioner allerede havde en Wago. Knappen forbliver nu aktiv, så længe lampeudtaget har mindst én gyldig terminalfunktion.
- Flere fysiske Wago-samlinger kan nu oprettes på **samme funktion** (fx flere N-, PE-, L- eller tændings-Wago'er).
- Wago-medlemmer er eksplicitte pr. samling; en Wago overtager ikke længere automatisk alle ledere med samme funktion.
- Direkte ledere, Wago'er med bro og rene Wago-sløjfer kan kombineres på samme funktion. Hver Wago-bro tæller én fysisk terminalplads, mens en ren sløjfe tæller nul.
- Lederfordelingsgrafikken er opdateret til at tegne flere Wago-blokke og flere broer til samme terminal uden at overskrive hinanden.
- Wago-listen nummererer dubletter på samme funktion, fx **Wago 1/3**, så de er lettere at skelne under redigering.
- Automatisk terminalkapacitets-hjælp opretter en ekstra Wago uden at overskrive eksisterende manuelle Wago-samlinger.
- Dark mode-arbejdet fra 0.51.0 er med i 0.51.1 uændret: Lys/Mørk/Følg Windows, separat mørk tegneflade, mørk PL-konfigurator og lyst teknisk print/PDF-output.

# 0.51.0

- Nyt samlet **Vis → Udseende** med **Lys**, **Mørk** og **Følg Windows** samt live skift uden genstart.
- **Ctrl+Alt+D** skifter hurtigt mellem lys og mørk; **Mørk tegneflade** kan vælges separat fra resten af brugerfladen.
- Udseendet er maskinlokalt (`appearance_mode` og `dark_canvas`) og følger derfor brugeren/computeren i stedet for projektfilen. Indstillingerne er bevidst udeladt fra portable kernedata.
- Mørkt tema dækker menuer, værktøjslinjer, docks, faner, formularer, tabeller, lister, knapper, statuslinje, scrollbars, tooltips, kabelassistent, hover-kort og øvrige centrale Qt-flader.
- CAD-tegnefladen har en særskilt skærmkontrast for mørke DWG-linjer, symboler, kabler og fritekst samt mørktilpassede snapmarkører, håndtag, guides og annotationer. De gemte projekt-/eksportfarver ændres ikke.
- PL-dåsekonfiguratorens **Kabelindføringer** og **Lederfordeling** er mørktilpasset med bevarede semantiske farver for PE/N/L, lederfarver, Wago, terminalstatus og kabelkategorier.
- Symbolpalettens ikoner og standardværktøjsikoner regenereres ved temaskift, så de forbliver læselige uden genstart.
- **Følg Windows** bruger Qt's systemfarveskema, med Windows-registry fallback, og reagerer på systemets temasignal når Qt/platformen understøtter det.
- Print-preview får mørk omgivelser i mørkt tema, men selve papirarket forbliver hvidt. PDF, print, PL-rapport og andet teknisk output bruger fortsat originale projektfarver og påvirkes ikke af dark mode.
- Ingen ændring af projektformat eller projektdataschema. Eksisterende brugere starter fortsat i lyst tema.

# 0.50.22

- Kabelkategorien vises nu direkte på hvert kabelkort i **PL-dåsekonfigurator → Lederfordeling**.
- Kategorien placeres mellem kabel-ID og kabeltype/kabelben, svarende til den markerede placering i brugerens eksempel.
- En kort farve-/konturprøve følger kategoriens centrale indstillinger, så eksempelvis Tændkabel og Mellemkabel kan skelnes visuelt.
- Projektets egne kabelkategorier sendes nu også til lederfordelingsgrafikken; ingen ny projektdata eller migration er nødvendig.

# 0.50.21

- Kabelkategorier vises nu direkte i **PL-dåsekonfiguratoren → Kabelindføringer**.
- Kabelben-listen viser kategoriens navn og en lille farve-/konturprøve sammen med kabel-ID, kabeltype og fysisk indføring.
- Den valgte indføring har fået et separat **Kategori**-felt med kategoriens definition som tooltip.
- PL-dåsens grafiske indføringskort viser kategorinavn samt farve/linjetype, og kabelkappens kategori-stribe følger kategoriens konfigurerede kontur.
- En kompakt kategorioversigt viser kun de kategorier, der faktisk forekommer ved det aktuelle lampested.
- Projektets egne brugerdefinerede kabelkategorier understøttes automatisk; ingen ny projektdata eller migration er nødvendig.

# 0.50.20

- Kabelkategorier har nu en vedvarende **definition/beskrivelse** ud over navn, farve og linjetype.
- **Tændkabel** defineres som *kabel fra afbryder til lampested*.
- **Mellemkabel** defineres som *kabel mellem lampesteder på forskellige grupper*.
- Definitionen vises i Kabelværktøjet, som tooltip i kategori-dropdownen og i **Vis → Kabelkategorier**.
- **Konfigurér kabelkategorier…** har fået en redigerbar Definition-kolonne, så egne kategorier også kan dokumenteres.
- Standarddefinitioner udfyldes automatisk på ældre standardkategorier uden at overskrive brugerens egne definitioner eller visuelle indstillinger.
- Rettet 0.50.19-migrationen, så slettede Mellemkabel/Tændkabel-kategorier ikke genoprettes ved senere versionsopgraderinger.

# 0.50.19

- Tilføjet standardkategorien **Mellemkabel**.
- Tilføjet standardkategorien **Tændkabel**.
- Begge kategorier har egen standardfarve/linjetype og fungerer på samme kategori-lagssystem som de øvrige kabelkategorier.
- Projekter fra før 0.50.19 får de to kategorier tilføjet ved første åbning uden at eksisterende kategoriindstillinger ændres.

# 0.50.18

- Ny kabelkategori pr. kabel med standarderne **Stikkontakter, Udendørs stikkontakter, Udendørs lys, Lampesteder, Spots, Ladeboks, Hvidevarer / faste forbrugere, Data / netværk og Øvrige**.
- Egne kategorier kan oprettes, omdøbes og slettes. Kabler fra slettede kategorier flyttes til **Øvrige**.
- Farve og linjetype/kontur konfigureres **pr. kategori** og synkroniseres til kategoriens kabler.
- Kategorien vælges direkte i Kabelværktøjet. Farve og linjetype kan også ændres der og påvirker hele den valgte kategori.
- Ny **Vis → Kabelkategorier**-menu med direkte vis/skjul for hver kategori samt genvej til konfiguration.
- Kabelkategorier ligger på egentlige kombinerede lag (`EL-KABLER-KAT-*`, `EL-LEDNINGER-KAT-*`, `EL-PATCHKABLER-KAT-*`) og vises også i Lag-panelet.
- Kategori-lag respekteres i skærmvisning, PDF/print og DXF-output.
- Nyt projektfelt `cable_categories` og nyt kabelfelt `cable_category`; gamle projekter migreres til **Øvrige** uden at ændre eksisterende kabelfarver ved åbning.

# 0.50.17

- Ny **Fil → Åbn seneste…**-menu med op til otte senest anvendte Elplan-projekter.
- Listen opdateres ved åbning, import og gemning; senest brugte projekt ligger altid øverst.
- Manglende/flyttede projektfiler fjernes automatisk fra listen.
- **Ctrl+Shift+O** åbner det senest anvendte projekt.
- Den almindelige Åbn-dialog starter i mappen for det senest anvendte projekt.
- Seneste projektstier er fortsat maskinlokale og medtages ikke i kernedataeksport.
- Ingen ændring af projektets datamodel.

# 0.50.16

- PL-hoverens grafiske miniature viser nu **indføringsnummer 1-6 tydeligt direkte ved hver fysisk indføring**.
- Portbadges er flyttet ind i previewets synlige område, så især indføring 1-3 og 4-6 ikke klippes ved top/bund.
- Kabel-ID er fjernet fra selve illustrationen; kabelnummer og ekstra mærkning står fortsat tydeligt i tekstoversigten ved siden af.
- Ingen ændring af projektets datamodel.

# 0.50.15

- PL-hover viser **Kabelnr.** eksplicit for hver anvendt indføring i tekstoversigten.
- Ekstra kabelmærkning vises separat under kabelnummeret.
- Ingen ændring af projektets datamodel.

# 0.50.14

- Projektroden er ryddet op: tests er flyttet til `tests/`, versionsnoter/audits til `docs/history/`, referencemateriale til `docs/reference/` og demo/templates til `examples/`.
- Hover-popup er redesignet som et mere visuelt kort med klar titel, undertitel, grafisk preview og separat BOM-felt.
- PL-hover viser en miniature af kabelindføringsgrafikken med port 1-6, kabelkappe, gennemføring og 3G/5G/7G-preview.
- Symbol-hover viser et symbolpreview; kabel-hover viser en lille fysisk kabelpreview.
- Popup viser nu de faktiske tilknyttede **styklister og artikler** for den konkrete symbolforekomst, inkl. styklisternes underliggende artikler og Wago-artikler.
- Ingen ændring af projektets datamodel.

# 0.50.13

- Ny diskret hover-popup efter 0,5 s på lampesteder med **kabelindføring 1-6** og fysisk PL-orientering.
- PL-hover viser kabel-ID/mærkning, kabeltype, kabelbenets side, ledige porte og evt. manglende placering — ikke lederfordelingen.
- Symboler med konkret artikel-/styklistebinding viser en kompakt **Artikel/BOM tilknyttet**-popup ved hover.
- Kabler med kabelartikelbinding viser tilsvarende kabelartikelnummer og beskrivelse ved hover.
- Symboler/kabler uden artikeldata får ingen ekstra BOM-popup, så visningen forbliver rolig.
- Ingen ændring af projektets datamodel.

# 0.50.12

- PL-dåserapporten har fået et nyt dedikeret afsnit **Lederfordeling - fysisk montage**.
- Hver fysisk leder vises med **indføring, kabel-ID, farve og montagedestination**.
- Destination skelner tydeligt mellem **direkte lampeudtagsklemme**, **Wago med bro**, **ren Wago-sløjfe**, **løs leder** og **manglende fysisk klemme**.
- Lederfarver vises som grafiske farveprøver; PE vises grøn/gul og hvid leder får mørk kontrast.
- Rapportlayoutet er ændret til **én PL-dåse pr. A4-side** for at give plads til op til 42 kendte 7G-ledere i to kolonner.
- Wago, terminalbelastning og montagekontrol er fortsat med på samme side.
- Ingen nye projektfelter.

# 0.50.11

- PL-dåsens fysiske orientering kan vælges i **0° / 90° / 180° / 270°** relativt til plantegningens top.
- Indføring 1-6, kabelvisualisering, gennemføringer og monteringsører følger den valgte orientering.
- Ny **PL-dåserapport** under Værktøjer samt genvejsknap i PL-egenskaberne.
- Rapporten eksporteres som A4-PDF og viser orientering, kabelindføringer, lampeudtag, Wago og montagekontrol.
- Nyt projektfelt `pl_box_orientation`; ældre projekter får automatisk 0°.

# 0.50.10

- Kabelenden inde i PL-dåsen viser nu en kort **3G/5G/7G-lederpreview**, så kabelopbygningen kan aflæses direkte i fanen Kabelindføringer.
- Yderkappen afsluttes visuelt ved en afisoleringskant, hvorefter lederne faner blødt ud inde i dåsen.
- Previewet genbruger `cable_conductor_preset`, så farverne er identiske med lederfordelingen og ikke vedligeholdes som en separat profil.
- PE vises grøn med gul markering; hvid/grå får mørk kontrastkant for læsbarhed.
- Ukendte kabelopbygninger får fortsat ingen gættede lederfarver.
- Ingen ændringer i projektets datamodel.

# 0.50.9

- Fanen **Kabelindføringer** har fået en mere fysisk og læsbar grafik omkring de seks indføringer.
- Hver indføring viser nu et kort kabelstykke mellem kabelkortet og PL-dåsen samt en tydelig rund gennemføringsmuffe/knockout i dåsekanten.
- Tildelte kabelben vises som mørke installationskabler med refleks og farvet identifikationsstribe, og kabelstumpen fortsætter synligt et lille stykke ind i dåsen.
- Ledige indføringer viser kun den tomme knockout; valgt ledig indføring får en diskret stiplet placeringsguide.
- Valgt indføring fremhæves nu også direkte på kabelgennemføringen.
- Ingen ændringer i datamodellen.

# 0.50.8

- Wago-samlinger har nu to tydelige montageformer: **Wago → lampeudtag** eller **kun sløjfe i PL-dåsen**.
- En ren Wago-sløjfe har **ingen bro til lampestedet** og optager derfor ingen terminalplads i lampeudtaget.
- Kun de eksplicit valgte ledere går i en ren Wago-sløjfe; øvrige ledere med samme funktion kan fortsat gå direkte til lampestedet.
- Løse, endnu ikke fordelte ledere kan vælges direkte i Wago-editoren og tildeles funktionen uden først at blive lagt på lampestedets terminal.
- En leder kan trækkes eller klikkes direkte på en Wago-blok for at føje den til samlingen. Højreklik tilbyder også **Sløjf leder i Wago uden lampested…**.
- Wago-editoren har ny afkrydsning **Forbind Wago til lampeudtaget med én bro**. Fjernes markeringen, bliver samlingen en ren intern sløjfe.
- WAGO-artikelforslaget og portkontrollen tager nu kun højde for broen, når Wago'en faktisk er forbundet til lampestedet.
- Fjernes en ren Wago-sløjfe, frigøres dens medlemsledere i stedet for automatisk at flytte dem til lampeudtaget.
- Tændingsledere i en ren Wago-sløjfe tæller ikke som en færdig forbindelse frem til lampestedets tændingsklemme.
- `pl_box_splices` har nyt valgfrit felt `connects_to_outlet`; ældre projekter fortolkes automatisk som `true` og bevarer derfor den hidtidige Wago-adfærd.

# 0.50.7

- **Ny Wago…** kan nu bruges allerede før lederfordelingen er udført; tomme Wago-samlinger bevares som planlagte samlinger.
- Wago er nu **eksklusiv pr. funktion**: findes en Wago, går alle kabelledere med funktionen ind i Wago'en, og kun én bro går videre til lampeudtaget.
- Nye ledere på en funktion med eksisterende Wago tilføjes automatisk til samlingen. Hvis den valgte Wago-artikel bliver for lille, foreslås en større 221-variant.
- Afmarkering/fjernelse af en enkelt leder fra en Wago frigør lederens funktion i stedet for at lade den falde tilbage som direkte terminalleder.
- Ny automatisk grafisk routing fordeler lange lederforløb i top-/bundspor sorteret efter slutpunkt og reducerer kryds.
- Ny kompakt **Montagekontrol** viser fysisk terminalbelastning, Wago-portkapacitet, tændingskrav og kendte fejl/advarsler.
- Ingen nye projektfelter; eksisterende `pl_box_splices`, `position` og `article_no` genbruges.

# 0.50.6

- Hover på en leder, terminal eller Wago fremhæver nu hele den elektriske forbindelse og toner øvrige forbindelser ned.
- Lederkurver har fået brede hit-zoner, så hover, valg og højreklik virker direkte på selve lederforløbet.
- Højreklik på en leder giver hurtig **Frigør**, **Flyt til terminal**, **Tilføj til Wago**, **Fjern fra Wago** og **Redigér Wago**.
- Wago-muffer kan trækkes frit rundt inde i PL-dåsen med musen. Den manuelle placering gemmes på Wago-samlingen som relative `position.x/y`-koordinater.
- Højreklik på Wago giver **Redigér**, **Nulstil Wago-placering** og **Fjern Wago**.
- Redigering eller automatisk udvidelse af en eksisterende Wago bevarer dens manuelle placering.

# 0.50.5

- Valgt leder kan nu frigøres direkte med **Delete** eller **Backspace** i den grafiske PL-ledereditor.
- Den grafiske kabelkappe mellem kabelkortet og PL-dåsen er fjernet; kun de faktiske farvede ledere vises ved indføringen.
- Lederforløbene bruger nu én sammenhængende Bézier-kurve uden et hårdt `lineTo`-knæk, så bøjningerne bliver tydeligere og blødere.
- WAGO 221-412, 221-413, 221-415 og 221-420 er tilføjet til det indbyggede artikelbibliotek med producentdata og EAN/GTIN.
- En Wago-samling kan nu gemme et konkret `article_no`. Wago-editoren foreslår den mindste passende 221-variant ud fra antal valgte kabelleder(e) + bro til lampeudtaget, men artikelvalget kan ændres.
- Wago-samlinger med valgt artikel tælles nu direkte med i BOM. Samlinger uden artikel vises som manglende BOM-dele i stedet for at blive skjult.

# 0.50.4

- Wago-samlinger er nu **manuelle og redigerbare** i PL-lederfordelingen.
- Ny kompakt Wago-række med **Ny Wago…**, **Redigér…** og **Fjern Wago**.
- En Wago gemmer præcist hvilke fysiske ledere der indgår i samlingen; øvrige ledere på samme funktion kan fortsat gå direkte til lampeudtaget.
- Når brugeren forsøger at tildele flere fysiske terminaltilslutninger end lampeudtaget tillader, vises en **advarsel** med mulighed for **Tilføj Wago** eller **Annuller**.
- Wiser / dæmpbar håndhæver **maks. 2 terminaltilslutninger**, og LK klassisk **maks. 4**. En Wago tæller som én terminaltilslutning via sin korte bro.
- Ny tydelig knap **Frigør valgt leder**, så en enkelt leders tilknytning til en klemme kan fjernes uden at nulstille resten af lederplanen.
- Wago-medlemmer kan redigeres med checkbokse; fjernelse af Wago bevarer ledernes funktion og advarer hvis terminalen derefter bliver overfyldt.
- Projektformatet har nyt felt `pl_box_splices` på lampesteder. Feltet normaliseres, reconciles mod aktuelle kabelledere og nulstilles ved kopiering af et lampested.

# 0.50.3

- De grafiske bokse **Reserve**, **Frigør / ikke fordelt** og **Ikke tilsluttet** er fjernet; disse ledere vises nu som løse ender.
- **LK Wiser / dæmpbar** har terminalgrænse på **maks. 2 ledere pr. terminal**.
- **LK klassisk lampeudtag** har terminalgrænse på **maks. 4 ledere pr. terminal**.
- Første Wago-visning blev introduceret som automatisk grafik ved overfyldte terminaler.
- Brun lederfarve er `#a87943`.

# 0.50.2

- Lederne går nu længere lodret ud fra indføringerne, før de bøjer, så forbindelserne er nemmere at følge.
- Parkeringsfelterne nederst i PL-dåsen er flyttet, så de ikke ligger visuelt bag de nederste ledergreb.
- Ikke fordelte ledere går nu til feltet **Frigør / ikke fordelt** i stedet for at ende som frie spørgsmålstegn.
- Brun lederfarve er justeret til en lysere brun (`#a87943`) for bedre læsbarhed.
- Ingen ændring af projektets `pl_box_entries`, `pl_box_wiring`, tilhørsforhold eller lampeudtagstype.

# 0.50.1

- Lampeudtagets klemmer er flyttet ud af PL-dåsen og vises som en separat klemrække til højre.
- Lederforløb er gjort markant tykkere og får en lys kontrastkant, så farverne kan følges ved kryds.
- Hvid leder får fortsat mørk kontur, og gul/grøn PE får tydelig gul stipling oven på grøn.
- Flere ledere på samme funktion får separate grafiske indgangspunkter i den samme klemmerække i stedet for at ende oven i hinanden.
- Valgt leder får større greb og kraftigere visuel fremhævelse.
- Kabelkortene er kompakteret en smule, mens lederenderne ved de seks indføringer er gjort større.
- Reserve, Ikke tilsluttet og Frigør/ikke fordelt holdes visuelt adskilt fra de fysiske lampeudtagsklemmer.
- Ingen ændring af projektets `pl_box_entries`, `pl_box_wiring`, tilhørsforhold eller lampeudtagstype.

# 0.50.0

- PL-ledereditoren er redesignet fra abstrakte funktionskort til en fysisk lampeudtags-/terminalvisning.
- Nyt lampestedfelt `lamp_outlet_type`: Generisk PL, LK klassisk og LK Wiser/dæmpbar.
- LK klassisk tegnes med klemmerne **N · L · PE · M1 · M2**.
- Wiser/dæmpbar tegnes med **PE · N · styret/dæmpet udgang · L**.
- M1/M2 og Wiser-udgangen kobles til eksisterende tændingstilhørsforhold og konkrete afbryderkanaler.
- Hvis udtagstypen mangler fysisk klemme til et tilhørsforhold, vises en tydelig advarsel direkte i grafikken.
- Reserve, Ikke tilsluttet og Frigør/ikke fordelt er sekundære parkeringsfelter i stedet for store 'klemmer'.
- Lederne trækkes fortsat direkte fra de farvede lederender til den fysiske terminal.
- Detaljetabellerne er skjult som standard bag **Vis tabel / avanceret**, som skifter til **Skjul tabel / avanceret** når panelet er åbent.
- Eksisterende `pl_box_wiring` bevares ved skift af lampeudtagstype.

# 0.49.1

- Lederfordelingens PL-dåse er nu den primære grafiske arbejdsflade.
- Kabelben tegnes som kabelkapper direkte ved de seks fysiske indføringer.
- Hver 3G/5G/7G-leder tegnes som en farvet lederstreng, der faner ind i dåsen.
- Tildelte ledere tegnes helt frem til grafiske samleklemmer.
- Ikke-fordelte ledere vises som frie ender med `?`.
- Samleklemmer viser tilsluttede lederfarver og status for forventede tændinger.
- Tændingsklemmer viser konkret afbryderkanal fra 0.49.0-mappingen.
- Drag-and-drop: en leder kan trækkes direkte til den ønskede samleklemme; klik → klik er bevaret.
- Detaljetabellerne er skjult som standard bag **Vis detaljer / tabel**.
- Datamodellen er uændret fra 0.49.0.

# 0.49.0

- PL-dåsen viser kabel-ID sammen med kabellets ekstra mærkning.
- Ny konkret mapping mellem lampestedets tilhørsforhold og de fysiske/logiske afbryderkanaler i kombisymboler.
- Stabil kanalidentitet baseret på symbol-UID + kanalindeks.
- Direkte kabelvej bruges til at kontrollere tændingslederen mod korrekt kabelben.
- Ny tabel **Forventede tændinger fra tilhørsforhold** med status for manglende/forkert/dublerede tildelinger.
- Én fysisk leder kan kun have én funktion; ny tænding erstatter den gamle på samme leder.
- Korrespondance/krydsning markeres til manuel terminalkontrol.
- Egenskaber viser også status for forventede tændinger.

# 0.48.1

- 7G-profil ændret til **gul/grøn, blå, brun, sort, grå, rød og hvid**.
- Blå leder i 7G foreslås nu som N; gul/grøn fortsat som PE.
- Lederfordelingen er gjort direkte grafisk: klik en farvet leder og derefter den ønskede samling i PL-tegningen.
- Alle relevante samlinger vises som klikbare mål, også når de endnu ikke har ledere.
- Valg i grafikken og tabellen synkroniseres begge veje.
- 0.48.0-data med `num1..num6` migreres kompatibelt til blå/brun/sort/grå/rød/hvid, så gemte funktioner og noter bevares.

# 0.48.0

- Ny fane **Lederfordeling** i PL-loftdåse-dialogen.
- 3G genkendes som gul/grøn PE + blå + brun.
- 5G genkendes som gul/grøn PE + blå + brun + sort + grå.
- 7G genkendes som gul/grøn PE + seks nummererede sorte ledere (1–6).
- Hvert kabelben får sin egen lederliste, så Side A og Side B på et gennemgående kabel kan planlægges separat i dåsen.
- Funktion/samling kan vælges som PE, N, fast L, tænding pr. lystilhørsforhold, reserve eller ikke tilsluttet.
- Tændingssamlinger forbindes grafisk til lampestedets L-terminal, fx `Tænding a → L(a)`.
- Gul/grøn PE og blå N foreslås automatisk; aktive ledere fordeles ikke automatisk.
- Ny vektorgrafisk ledervisning med farvede/nummererede ledere og samlingsskinner.
- Egenskaber viser lederplan-status sammen med PL-indføringsstatus.
- `pl_box_wiring` gemmes pr. lampested og valideres mod aktuelle kabelben/kabelspecifikationer.
- Kopiér/indsæt nulstiller både PL-indføringer og lederplan.

# 0.47.0

- Ny grafisk **PL loftdåse – kabelindføringer** for lampesteder i loft.
- Dobbeltklik på et lampested åbner den 6-ports PL-konfigurator.
- Ny vektorillustration af PL-dåsen uden mål, så visningen skalerer rent.
- Et gennemgående kabel registreres fysisk som to kabelben (Side A/Side B); et endende kabel som ét.
- Kabelben kan placeres via klik/knap eller drag-and-drop til indføring 1–6.
- Automatisk forslag fordeler kabelben efter deres udgående retning i plantegningen.
- Dialogen advarer ved flere end seks nødvendige kabelindføringer og viser ikke-placerede kabelben.
- Egenskaber viser løbende `PL-dåse: x / 6` og har direkte konfigurationsknap.
- PL-data gemmes pr. lampested og valideres mod de faktiske kabeltilslutninger ved projektgemning.
- Kopiér/indsæt af lampesteder kopierer ikke fysiske PL-kabelreferencer.

# 0.46.2

- Nyt dedikeret lag `EL-PATCHKABLER`.
- Kabelværktøjets Type har nu **Kabel / Patchkabel / Ledning**.
- Hurtig visning har separat **Patchkabler**-knap.
- **Kabler**-knappen påvirker almindelige kabler/ledninger, mens patchkabler kan vises uafhængigt.
- `Vis alt` aktiverer også patchkabler.
- Patchkabellaget bevares i projektfiler og DXF-eksport.
- Eksisterende kabler kan flyttes til patchkabellaget via **Anvend kabeldata** uden at miste kabel-ID, geometri, artikel, BOM eller forbindelser.

# 0.46.1
- Tilføjet HELUKABEL HELUKAT 600IND CAT.7 S/FTP PUR ROBUSTFLEX (art. 802184) som patch-/Ethernetkabel på metermål.
- Kabelartiklen indeholder producentbekræftet EAN, produktlink, datablad og direkte HELUKABEL-produktfoto.
- Artiklen matcher kabelpreset `CAT7 S/FTP` og kan derfor tilknyttes netværkskabler og medregnes i BOM som meter.

# 0.46.0

- Ny hurtig visning i hovedværktøjslinjen: **Plan, Symboler, Kabler, Tekst og Vis alt**. Filtrene ændrer ikke projektets individuelle lagvalg.
- Hurtigvisning huskes som brugerindstilling og kan nulstilles med ét klik.
- Kabelmodellen har fået individuel `color` og `line_style`; ældre projekter migrerer implicit til rød/fuldt optrukket.
- Kabelværktøjet kan vælge farve samt Fuldt optrukket, Stiplet, Prikket eller Streg-prik for nye og eksisterende kabler.
- Kabelstil gengives i Qt-editoren, PDF/print og DXF, uden at påvirke kabelgeometri, parallelbaner, længde eller BOM.
- Nyt **Patchpanel / datacentral (12 porte)** på EL-TELE-DATA med 12 separate kabelsnapporte.
- Nye kabeltype-presets til CAT6 U/UTP, CAT6A F/UTP og CAT7 S/FTP.

# 0.45.5

- Ny **Importguide…** direkte i Artikeldatabase ved siden af bibliotek-importen.
- Guiden forklarer JSON/CSV-format, flette-regler, obligatoriske/anbefalede felter samt Excel-faldgruber for EAN/EL-nr.
- Ny feltoversigt viser JSON-feltnavn, dansk CSV-kolonne, krav, beskrivelse og eksempel for alle understøttede importfelter.
- Guiden kan gemme komplette **JSON- og CSV-templates** direkte fra programmet.
- Templates og guide drives af samme skemadefinition som importeren, så feltnavne ikke kan drive fra hinanden.
- Medfølgende `article_library_template.json` og `article_library_template.csv` er opdateret til 0.45.5 og indeholder alle dokumenterede felter.

# 0.45.4

- **Standardbibliotek** er fjernet fra Artikler og BOM. **Artikeldatabase** er nu den eneste synlige og autoritative artikelbase.
- Artikeldatabase har fået samme produktfoto-preview og detaljer som det tidligere Standardbibliotek.
- De avancerede filtre (fabrikat, type, design, modul, farve, diameter, CCT, IP og kun med pris) arbejder nu direkte på hele artikeldatabasen, inkl. LK-synkroniserede og manuelt importerede poster.
- Manuel artikeloprettelse/redigering understøtter nu også produktlink, leverandørlink, datablad, billede-URL og kilde.
- Ny **Importér bibliotek…** understøtter JSON og CSV. JSON er det anbefalede native format; CSV er beregnet til Excel/leverandørlister.
- Import kan enten **Flet sikkert** (tilføj nye og udfyld kun tomme felter) eller **Opdatér eksisterende** (ikke-tomme importværdier må erstatte eksisterende metadata).
- Før artikelimport oprettes automatisk en backup af den globale `articles.json`. Projektbindinger og prisbog ændres ikke af bibliotekimporten.
- Ny **Eksportér bibliotek…** kan skrive hele artikeldatabasen som native JSON eller semikolonsepareret UTF-8 CSV.
- Skjulte artikel-snapshots fra gamle globale styklister flyttes automatisk ind i Artikeldatabase, så UI/BOM ikke arbejder med en skjult sekundær artikelkilde.

# 0.45.3

- LK-produktsider hentes nu parallelt med op til 8 samtidige forbindelser.
- Produkthentning bruger kortere timeout (8 s); kun fejlende sider genforsøges, én gang.
- Ny lokal `lk_catalog_cache.json`: produktsider genbruges i op til 7 dage, katalogindeks i op til 6 timer.
- Nyligt synkroniserede LK-rækker i kernedatabasen kan bruges som cache efter opgradering fra 0.45.2.
- Synkroniseringsdialogen tilbyder Hurtig synkronisering og Fuld genhentning.
- Fremdrift viser behandlet/total, aktive samtidige forbindelser, cache-genbrug og fejl til genforsøg.
- Cache gemmes løbende under lange synkroniseringer, så en annulleret kørsel stadig kan genbruge allerede hentede produktsider uden at ændre artikelbasen.
- Fallback-scan af LK-kategori-ID'er kører også parallelt, når den er nødvendig.

# 0.45.2

- Rettet LK-katalogsynkronisering efter ændring i LK's legacy-katalogmarkup.
- Produktnumre opdages nu også fra produktbilleder (`/foto/jpg/<LK-nr>.jpg`) og fra alle relevante HTML-attributter, ikke kun `href`/`onclick`.
- EAN- og LK-nummer-discovery kan nu supplere hinanden; den rigeste metadata-post bevares ved dubletter.
- Direkte LK-nummer fundet via katalogbillede kan bruges sikkert som fallback, hvis den gamle detaljeside ikke gentager varenummeret i teksten.
- Generiske katalogbilleder uden cifre (fx `Fuga.jpg`) filtreres fra.
- Tilføjet regressionstests for den markup, der udløste fejlen “ingen produktreferencer blev fundet”.

# 0.45.1

- Artikel databasen kan nu synkroniseres direkte med LK/Schneider-onlinekataloget via **Synkronisér LK.dk…**.
- Synkroniseringen crawler LK's server-renderede katalogindeks, følger kategorier og produktvarianter og importerer én global artikelpost pr. LK-varenummer.
- Importerede felter omfatter bl.a. beskrivelse, LK-nr., EL-nr., EAN, serie, kategori, farve, status når kataloget angiver den, produktlink og direkte LK-produktfoto.
- Officielle LK-felter opdateres ved ny synkronisering, mens brugerens egne grossistlinks, egne noter og den separate prisbog bevares.
- Før hver synkronisering oprettes en tidsstemplet backup af den globale `articles.json`.
- Databasen ændres ikke ved afbrudt/fejlet synkronisering, og en mistænkeligt lille kataloghøst afvises som sikkerhedsforanstaltning.
- **Artikel database** er flyttet fra `QTableWidget` til `QTableView + ArticleTableModel`, så flere tusinde katalogposter ikke genskaber de tidligere søge-/refresh-frysninger.
- Artikel database har fået et letvægts-søgefelt og viser antal filtrerede/total poster.
- Projekt-/kernedata-adskillelsen fra 0.45.0 er uændret: LK-kataloget gemmes kun i globale kernedata, aldrig i projektfilen.
- Version hævet til 0.45.1.

# 0.45.0

- Kernedata og projektdata er nu eksplicit adskilt.
- Ny global artikelbase `articles.json` under brugerens Elplan-datamappe; den seedes fra den medfølgende standarddatabase og får automatisk nye standardartikler ved programopdatering uden at overskrive brugerens gemte poster.
- Artikel database, globale styklister, prisbog, custom-symboler og portable programindstillinger kan eksporteres/importeres som `.elplancore`.
- Ét projekt og dets DWG/DXF kan eksporteres/importeres separat som `.elplanproj`.
- Begge pakkeformater bruger manifest og SHA-256-checksummer.
- Import af kernedata laver automatisk en backup af eksisterende kernedata.
- Projektpakker bruger relativ CAD-sti efter import og indeholder en afhængighedsliste, men ingen artikel-/stykliste-database.
- Gamle projektfelter `article_catalog`, `bom_assemblies` og `custom_symbols` migreres automatisk til kernedata ved åbning og gemmes ikke længere i nye projektfiler.
- Projektets konkrete instansbindinger (`placement_articles`, `placement_assemblies`, `cable_instance_articles`) forbliver projektafhængige.
- Artikel/BOM-fanen **Projektbibliotek** er omdøbt til **Artikel database** og arbejder nu direkte mod kernedata.
- Projektformat/version hævet til 0.45.0.

# 0.44.5

- Kabelværktøjet har nu en eksplicit **Ruteføring**-vælger: `Fri / diagonal` eller `Ortogonal (90°)`.
- `Fri / diagonal` er standard for nye kabler og huskes som brugerindstilling.
- I fri tilstand forbindes hvert klik direkte med næste punkt uden automatisk L-knæk.
- Eksisterende kabler beholder deres gemte rutetilstand og kan skiftes mellem fri og ortogonal via Valgt kabel → Anvend kabeldata.
- Diagonale kabler understøtter fortsat symbol-snap, kabelrute-snap, sløjfning, parallelle visningsbaner, korrekt geometrisk længde og fri efterredigering.
- Tilføjet GUI-uafhængig rutefunktion og regressionstests for diagonal tegning, længde og parallelle diagonale kabelbaner.

# 0.44.4

- Rettet den egentlige årsag til at parallelle kabelbaner kunne forblive visuelt sammenfaldende: under opstart kunne `cable_snap_routes` udsende et signal før parallel-kontrollerne var gendannet, hvilket gemte `cable_parallel_lanes=false` og `5 px` tilbage i app-indstillingerne.
- Kabelværktøjets indstillinger gendannes nu atomisk med blokerede Qt-signaler.
- Engangsreparation nulstiller de fejlgemte 0.44.0-0.44.3 parallel-indstillinger til de tilsigtede standarder (parallelle baner til, 10 px, bundle-mærker/fokus til). Efter markøren respekteres brugerens egne valg igen.
- Parallelgeometrien fra 0.44.3 er bevaret; rettelsen sørger nu for at den faktisk er aktiveret.

## 0.44.4

- Parallelbanens beregnede visningspath skubbes nu direkte ind i hvert `CableItem`; Qt-renderingen er ikke længere afhængig af et indirekte cache-opslag under `refresh()`.
- Valg af et kabel kollapser ikke længere den visuelle parallelbane tilbage på den logiske centerlinje. Centerlinjen bruges kun under aktiv handle-redigering.
- Tilføjet regressionstest med de faktiske G01/K01-koordinater fra en brugerprojektfil: samme gruppetavleport, samme første lange segment, to tydeligt forskellige renderbaner ved 6 % zoom.
- Ingen ændring af gemt kabelgeometri, længder, artikler eller BOM.

## 0.44.2

- Fælles fysisk start/slutpunkt er nu autoritativt for visuel kabel-fan-out; parallelvisning afhænger ikke længere kun af segment-overlap.
- Kabler fra samme symbolport/tavleudgang og samme retning får stabile separate baner allerede umiddelbart efter ankeret.
- Samme fallback virker også for frie kabelender, der ligger på samme koordinat.
- Kollineære delsegmenter efter et fælles anker arver fan-out-banen, så forskellige interne knækpunkter ikke får kablerne til at smelte sammen.
- Fysiske mellemtilslutninger på sløjfede kabler holdes nu på den præcise symbolport i den kosmetiske parallelvisning; banen fletter ind og ud omkring ankeret.
- Nye regressionstests dækker 2 og 6 kabler fra samme tavleport samt mellemtilslutninger.

## 0.44.1

- Rettet parallelvisning, hvor to eller flere kabler kunne se ud som én streg trods aktiv lane-separation.
- Fælles-rute-detektionen er nu skærmbaseret/tolerant i stedet for næsten CAD-eksakt. Små koordinatafvigelser, forskellige kollineære knækpunkter og små vinkelafvigelser genkendes som samme visuelle føringsvej.
- Kabler fra samme tavle-/symbolpunkt faner nu ud selv når deres efterfølgende centerlinjer ikke er numerisk identiske.
- Separate parallelle ruter uden visuelt overlap bundtes fortsat ikke.
- Tilføjet regressionstests for tavle-fan-out, fuzzy centerlinjer, små vinkelafvigelser og forskellig segmentering.

## 0.44.0

- Større forbedring af mange/parallelle kabler: kabler på samme logiske rute fordeles i stabile, individuelle skærmbaner.
- Lane-rækkefølgen er nu deterministisk efter kabel-ID/uid og ændres ikke tilfældigt ved ændret projektorden.
- Baneafstand kan justeres direkte i Kabelværktøj (5–18 px) og påvirker kun visningen, aldrig gemt geometri eller længde.
- Nye kabler kan snappe direkte til eksisterende kabelruters logiske centerlinje, så flere fysiske kabler nemt kan genbruge samme føringsvej.
- Ved 3+ kabler på et fælles stræk vises en diskret ×N-markering med tooltip over de involverede kabel-ID'er.
- Nyt fokusvalg toner ikke-relaterede kabler ned, når ét symbol vælges, så fx seks kabler ved et lampested kan aflæses isoleret.
- Valgt kabel viser nu hvilken parallel bane det ligger på, fx bane 3/6, og kabel-tooltip viser parallelgruppen.
- PDF/print bruger fortsat samme rent visuelle lane-princip; BOM, artikeltilknytning og længdeberegning er uændret.
- Tilføjet regressionstests for seks parallelle kabler, stabil lane-rækkefølge, delte delstræk og uændret logisk geometri.

## 0.43.3

- Rettet regression i kabelredigering: blå geometriske knæk kan igen flyttes frit, også når de ligger mellem to fysiske symboltilslutninger.
- 90°-føring indsætter nu automatisk lokale dogleg-knæk i stedet for at låse et rutepunkt i både X og Y.
- Grønne symboltilslutninger forbliver absolut låst til symbolporten under efterredigering.
- Symbolforbindelsesindeks remappes automatisk, når kabelredigering indsætter ekstra geometripunkter.
- Et tidligere symbol-snap nulstilles korrekt, når et blåt håndtag trækkes væk fra symbolet igen.
- Tilføjet regressionstests for fri ruteredigering mellem låste ankre.

## 0.43.2

- Rettet kabelredigering, så fysiske symboltilslutninger er låste ankre og ikke kan trækkes væk fra symbolet.
- Grønne tilslutningshandles er nu ikke-flytbare; den fysiske tilslutning flyttes kun ved at flytte selve symbolet.
- Redigering af blå geometriske knækpunkter må ikke længere flytte et tilstødende fysisk symbolanker ved ortogonal 90°-føring.
- Frie kabelendepunkter bruger en indeksstabil redigering, når kablet indeholder fysiske tilslutninger, så forbindelsesindeks ikke forskydes.
- Ved projektåbning repareres eventuelle gemte kabelankre fra 0.43.0/0.43.1 automatisk tilbage til den registrerede symbolport.
- Efter en kabelgeometri-redigering udføres et ekstra anker-check som sikkerhedsnet.
- Ingen manuel datamigrering er nødvendig.

## 0.43.1

- Ny interaktiv kabel-assistent med små, ikke-modale popups ved symboltilslutninger.
- Popup'en kræver aldrig et svar; almindelig sløjfning kan fortsætte med klik direkte på næste punkt.
- Hurtighandlinger: **Afslut her**, **Afslut + nyt herfra**, **Kun forbi** og **Fortryd punkt**.
- **Afslut + nyt herfra** afslutter det aktuelle kabel og starter næste kabel fra præcis samme fysiske symboltilslutning uden ekstra klik.
- Assistenten viser eksisterende kabel-ID'er ved det valgte symbol og advarer ved gentagen tilslutning af samme symbol på det aktive kabel.
- Geometriske knækpunkter lukker automatisk en gammel hjælpepoppup.
- Assistenten kan slås til/fra i Kabelværktøj; valget gemmes i globale programindstillinger.
- Ingen ændring af projektets kabeldataformat ud over versionsnummeret.

## 0.43.0

- Kabelmodellen understøtter nu sløjfning: samme kabel-ID kan være fysisk tilsluttet et vilkårligt antal symboler langs én samlet rute.
- Nye kabeldata gemmer `symbol_connections` som ordnede forbindelser til konkrete rutepunkter; legacy `start_symbol_uid`/`end_symbol_uid` bevares og holdes synkroniserede.
- Ældre projekter migreres automatisk: eksisterende start-/sluttilslutninger bliver til første/sidste post i `symbol_connections`.
- Kabelværktøjet fortsætter samme kabel efter klik på et symbol. Enter/højreklik afslutter hele kablet; Backspace fjerner sidste brugerklik inklusive automatisk 90°-hjørne.
- Kabelpanelet viser nu det fysiske forløb, fx `Tavle → L01 → L02 → Stikkontakt`, samt antal tilslutningssteder.
- Fysiske kabeltilslutninger vises som grønne redigeringspunkter, mens almindelige geometriske knækpunkter fortsat er blå. Et fysisk tilslutningspunkt kan ikke slettes ved et utilsigtet højreklik.
- Egenskaber for et markeret symbol viser nu hvilke kabler der starter, ender eller er gennemgående ved symbolet, med genvej til at vælge kablet.
- Flyttes et symbol, følger alle kabeltilslutninger til symbolet med, også når forbindelsen ligger midt på kablet.
- Automatisk start af et helt nyt kabel efter afslutning er nu valgfri og som standard slået fra, så sløjfning ikke forveksles med nye kabel-ID'er.
- LK/FUGA-artikler får automatisk direkte produktfoto-URL fra LK's eget varenummerbaserede katalog. Billeder hentes fortsat lazy, caches lokalt og falder tilbage til produktsiden/skematisk preview ved fejl.
- Projektformat/version hævet til 0.43.0.

## 0.42.5

- Rettet regression hvor `BomManagerDialog._fmt_qty()` manglede `@staticmethod`, så Artikler og BOM kunne crashe med `TypeError` under første BOM-opdatering.
- Rettelsen gælder både selvstændig åbning af Artikler og BOM og åbning fra et markeret symbol.
- Tilføjet regressionstest, der sikrer at antalsformateringen fortsat kan kaldes både fra klassen og gennem en dialoginstans.
- Ingen ændringer i projektdata eller BOM-regler.
- Projektformat/version hævet til 0.42.5; ingen manuel datamigrering er nødvendig.

## 0.42.4

- Kabelværktøjet er ombygget til et scrollbar panel, så alle funktioner er tilgængelige på mindre skærme og ved høj DPI.
- Kabeldata, tegne-/snapvalg, valgt kabel, Artikel/BOM og længdeestimat er samlet i tydeligere grupper.
- Kabelartikler kan nu tilknyttes direkte fra Kabelværktøj via den filtrerbare artikelvælger. Vælgeren viser kun kabelartikler.
- En artikel kan vælges til et eksisterende valgt kabel eller til præcis det næste nye kabel. Et valg til et nyt kabel forbruges én gang og nulstilles derefter, så ingen artikel tildeles automatisk til efterfølgende kabelstræk.
- Kabelværktøjet lukker automatisk, når brugeren forlader kabelarbejdet med Esc/Annuller, vælger et symbol eller starter et andet tegneværktøj.
- Egenskaber-panelet vises og hæves automatisk, når ét symbol markeres på tegningen.
- Projektformat/version hævet til 0.42.4; ingen manuel datamigrering er nødvendig.

## 0.42.3

- BOM-tilknytninger er ændret fra typebaserede til instansbaserede: en artikel/stykliste gælder nu kun det konkrete symbol, brugeren vælger.
- Et symbol af samme type får ikke længere automatisk de samme BOM-artikler. Eksempel: 1 tilknyttet stikkontakt blandt 19 giver 1 stk. i BOM og 18 ikke-tilknyttede symboldele.
- Kabelartikler tilknyttes nu hvert enkelt kabelstræk via et stabilt kabel-id i stedet for automatisk til alle stræk med samme kabeltype/specifikation.
- BOM viser en tydelig advarsel med antal symboldele og kabelstræk uden artikel/stykliste.
- Den separate kontroltabel viser fortsat type, del/specifikation, behov og bemærkning for ikke-tilknyttede elementer.
- Ældre typebaserede `symbol_articles`, `symbol_assemblies` og `cable_articles` bevares i projektfilen som legacy-data, men anvendes ikke automatisk af BOM i 0.42.3.
- Nye projektfelter er `placement_articles`, `placement_assemblies` og `cable_instance_articles`.
- Kabler har nu et stabilt `uid`, som genereres automatisk ved indlæsning af ældre projekter og gemmes næste gang projektet gemmes.
- Projektformat/version hævet til 0.42.3.

## 0.42.2

- Samlet GUI-audit af hele den aktive Qt-applikation med fokus på konsistens, læsbarhed og tydeligt visuelt hierarki uden tilsigtede funktionsændringer.
- Formularer bruger nu fælles label-/feltalignment, spacing og field-growth via én fælles `QFormLayout`.
- Dialogknapper bruger fælles primær/sekundær/destruktiv styling; standardtekster som Cancel/Save/Close oversættes til dansk i programmets egne dialoger.
- Spinbox-stylingen er afgrænset til programmets egne talbokse, så Qt-oprettede standarddialoger beholder deres native pile. Programmets talbokse tegner fortsat deterministiske op-/ned-chevrons.
- Programmets comboboxe tegner nu også en deterministisk dropdown-chevron; Qt-oprettede standarddialoger påvirkes ikke af denne overtegning.
- Artikelvælger og Standardbibliotek har tydeligere filter- og previewpaneler, mere ensartet spacing og klare primær-/sekundærhandlinger.
- Artikelredigering er opdelt i Grunddata, Klassifikation samt Links og note i stedet for én lang formular.
- Stykliste-, BOM- og kabeldialoger har fået ensartede sektionsoverskrifter, tabeller, hjælpetekster, destructive actions og knaphierarki.
- Egenskaber-, Symboler-, Lag- og Kabel-docks er poleret med ensartede gruppebokse, farvevælgere, status-/hjælpetekster og sekundære værktøjsknapper.
- Tabelhjælperen giver alle relevante tabeller ens rækkehøjde, skjult lodret header, alternating rows, resizable headers og pixel-scroll.
- Globalt lyst tema er udvidet med hover/focus/disabled/read-only states, combobox-popups, list views/completers, checkboxes, tabeller, scrollbars, tooltips, statusbar og dock-knapper.
- Store dialoger tilpasses skærmens available geometry, så de ikke åbner uden for arbejdsområdet på mindre skærme.
- Ny `GUI_AUDIT_0.42.2.md` dokumenterer gennemgangen og de områder, der er visuelt verificeret statisk.
- Projektformat/version hævet til 0.42.2; ingen manuel datamigrering er nødvendig.

## 0.42.1

- Retter spinbox-pilene på Windows, hvor 0.41.6/0.42.0 kunne vise knapzonen uden selve op-/ned-glyfferne.
- `QSpinBox` og `QDoubleSpinBox` tegner nu deres chevrons som sidste trin i widgettens egen `paintEvent`, efter Qt/Fusion/QSS har malet kontrollen.
- Løsningen er derfor ikke afhængig af, om `QStyleSheetStyle` videresender de native pil-primitiver på den aktuelle Windows-/DPI-kombination.
- Klikområder, tastaturbetjening, mouse wheel, hover/pressed styling og eksisterende værdilogik er uændret.
- Projektformat/version hævet til 0.42.1; ingen manuel datamigrering er nødvendig.

## 0.42.0

- Større intern vedligeholdelses- og oprydningsrunde uden tilsigtede ændringer af arbejdsgangen.
- Den aktive Qt-applikation bruger nu `core_logic.py` som GUI-uafhængig kerne og importerer ikke længere den historiske Tkinter-applikation ved normal opstart.
- `legacy_core.py` er reduceret til et lille kompatibilitetslag; den gamle Tkinter-frontend ligger isoleret i `legacy_tk_app.py` og indlæses kun ved eksplicit legacy-brug.
- Fælles atomisk filskrivning/JSON-håndtering er samlet i `storage_utils.py`, så projekt- og brugerbibliotek ikke vedligeholder hver sin kopi af samme persistence-kode.
- Artikel-søgeindeks er samlet i `article_index.py` og genbruges af både artikelvælger og Standardbibliotek.
- BOM-dialogens sammensmeltede artikelkatalog og artikelopslag caches mellem refresh-forbrugere og invalideres kun, når artikler/priser ændres.
- Modelbaserede tabelhjælpere, kolonnebredder og dialoggeometri er flyttet til `qt_table_utils.py`, hvilket reducerer ansvar og størrelse i `qt_app.py`.
- Produktfoto-requests bruger nu den aktuelle `APP_VERSION` i User-Agent i stedet for et hardkodet versionsnummer.
- Ny roterende logfil i brugerens Elplan-datafolder (`logs/elplan.log`) registrerer uventede Python-fejl og gør opstarts-/runtime-problemer lettere at diagnosticere.
- `start_windows.bat` viser logfilens placering ved runtime-fejl.
- Testpakken er rettet mod den aktive `core_logic` og udvidet med arkitektur-/storage-tests. 97 tests består i det aktuelle miljø; 11 Qt-runtime-tests springes over uden PySide6.
- Projektformat/version hævet til 0.42.0; ingen manuel datamigrering er nødvendig.

## 0.41.6

- Talbokse (`QSpinBox`/`QDoubleSpinBox`) har nu en tydelig separat knapzone med synlige op-/ned-pile, hover og pressed feedback.
- Ny Fusion-baseret `ElplanProxyStyle` tegner retningspile med fast kontrast, så Windows-tema og DPI ikke kan gøre dem usynlige.
- ComboBox-felter har fået en tydeligere dropdown-zone og bedre hover/pressed feedback.
- Tabeller har fået fælles visuel styling med roligere grid, tydelige tabelhoveder, hover og markering.
- Fokusmarkering på knapper/inputfelter er gjort mere konsekvent.
- Vandrette scrollbars matcher nu de lodrette og har tydelig hover-feedback.
- GUI-polishen ændrer ikke projektdata eller arbejdsgange.
- Projektformat/version hævet til 0.41.6.

## 0.41.5

- Artikelvælgeren er omskrevet fra `QTableWidget` til `QTableView` + `QAbstractTableModel`.
- Standardbiblioteket bruger samme modelbaserede tabel og genopretter ikke længere tusindvis af Qt-celleobjekter ved filtrering.
- Filtrering udskifter nu kun modellens rækkeliste; sortering håndteres direkte i modellen.
- Eksisterende kolonnebredder, auto-fit, nulstilling, tooltips, enkelt-/multivalg og valg-genoprettelse er bevaret.
- Nulstilling af filtre blokkerer signaler, så kun én opdatering udføres.
- Produktpreview venter 300 ms før onlineopslag og afbryder forældede requests ved hurtigt artikelskift.
- Projektformat/version hævet til 0.41.5.

## 0.41.4

- Artikelvælgerens kolonner er nu frit brugerjusterbare ved at trække i tabelhovedet.
- Kolonnebredder gemmes globalt og genbruges i alle projekter.
- Ny **Tilpas kolonner** auto-fit samt **Nulstil bredder**.
- Fuld celletekst vises som tooltip, hvis en kolonne er smallere end indholdet.
- Samme fleksible tabeladfærd er ført til Standardbibliotek, Projektbibliotek, Styklister, Tilknytning og BOM.
- Artikelvælgerens og BOM-vinduets størrelse/placering huskes mellem åbninger.
- Vandret pixel-scroll gør brede artikeldata lettere at navigere.
- Projektformat/version hævet til 0.41.4.

## 0.41.3

- Global prisbog (`article_prices.json`) i brugerens Elplan-datafolder.
- Pris/prisestimat pr. artikel: enhedspris ekskl. moms, valuta, pristype, kilde, kontroldato og note.
- Pris kan redigeres direkte fra Standardbibliotek og Projektbibliotek og genbruges på tværs af projekter.
- Artikelvælgeren viser pris og kan filtrere til kun artikler med pris.
- Stykliste-editoren viser enhedspris, linjesum og samlet styklistepris.
- BOM viser enhedspris, linjesum og samlet estimeret materialeværdi; kabelruller og afmålt kabel prissættes efter den beregnede BOM-mængde.
- BOM CSV indeholder pris, valuta, pristype, priskilde og kontroldato.
- Projektformat/version hævet til 0.41.3.

## 0.41.2

- Artikelvælgeren er optimeret med forberegnet søgeindeks, 180 ms debounce og chunked tabelopdatering, så GUI'en ikke låser ved søgning.
- Samme responsive søgeprincip er tilføjet Standardbibliotek-fanen.
- Styklister er nu globale for brugeren og gemmes i AppData i stedet for i det enkelte projekt.
- Eksisterende projektafhængige styklister migreres automatisk til det globale bibliotek ved åbning.
- Globale styklister gemmer snapshots af deres anvendte artikler, så brugerdefinerede artikler også kan genbruges i andre projekter.
- Projekter gemmer fortsat deres stykliste-tilknytninger pr. symbol/fysisk modul, men ikke selve stykliste-definitionerne.
- Sletning af en global stykliste advarer nu om, at den også forsvinder fra andre projekters styklistevælger.
- Projektformat/version hævet til 0.41.2.

## 0.41.1

- Systematisk krydstjek af centrale LK FUGA-indsatse mod Schneider/LK-producentdata og den aktuelle 20-års garantiliste.
- `501D0412` er kompletteret med EL-nr. `1017056224`, EAN `5703302157087`, 2M-/stikkontaktfilterdata og direkte Lemvigh-Müller-reference.
- Alle 78 fysiske (ikke rene paknings-) produktvarianter i garantilistens FUGA-kerne er nu dækket og har verificeret EL-nr./EAN.
- Tilføjet manglende EDB-, hospital-, sidejord-, pindjord-, korrespondance-, træk-/nøgleafbryder- og klasse 1/2-varianter.
- Tilføjet nyere/verificerede LED-/timer-stikkontakter samt 2M EDB-indsats og flere tilhørende afdækninger fra LK/Lemvigh-Müller.
- Rene BULK-/DETAILFORPAKNING-SKU'er er bevidst ikke lagt ind som separate standardartikler endnu, for at undgå dubletter i artikelvælgeren.
- Standardbiblioteket indeholder nu **438 artikler**: 323 Schneider Electric / Lauritz Knudsen, 77 Nordtronic A/S og 38 Waskönig+Walter.
- Projektformat/version hævet til 0.41.1.

## 0.41.0

- Stykliste-editorens simple artikel-dropdown er erstattet af en stor **filtrerbar artikelvælger** med fritekstsøgning, fabrikat, produkttype, serie/design, modul, farve, status og **Kun med EAN**.
- Artikelvælgeren har sortérbare kolonner, artikelpreview, EAN, EL-/LM-nr. samt direkte knapper til producent- og leverandørside. Dobbeltklik vælger artiklen direkte.
- Standardbibliotekets tabel er også gjort sortérbar og viser nu EAN som selvstændig kolonne. Projektbibliotek og BOM viser ligeledes EAN, og BOM-CSV indeholder EAN, EL-/LM-nr., producentlink og leverandørlink.
- Projektartikler kan nu gemme både **Produktlink** og **Leverandørlink**.
- Artikeldata er datavasket: beskrivelser, modulnotation, kategorier og statusbetegnelser er strømlinet på tværs af LK, Nordtronic og Waskönig+Walter.
- LK-artikler bruger producentens LK-produktlink som primær produktside (`lk.dk`), mens verificerede Lemvigh-Müller-links bevares separat som leverandørside.
- FUGA tangent-/afdækningsbiblioteket er gennemgået systematisk og udvidet med bl.a. EDB-, nøgleafbryder-, PIR-, trækafbryder-, timer-, timerstikkontakt-, hospital-/LED- og lampeudtagsafdækninger. Kun verificerede artikelnumre/EAN/EL-nr. er lagt ind; manglende metadata gættes ikke.
- Standardbiblioteket indeholder nu **397 artikler**: 282 Schneider Electric / Lauritz Knudsen, 77 Nordtronic A/S og 38 Waskönig+Walter.
- Projektformat/version hævet til 0.41.0.

## 0.40.0

- Standardartikelpreview kan nu vise rigtige produktfotos/produktillustrationer fra registrerede onlinekilder med lokal disk-cache og automatisk fallback til den skematiske vektorillustration.
- LK/Schneider-artikler med EL-nr. har fået Lemvigh-Müller-produktkilde, og udvalgte verificerede varer har direkte billedlink.
- Nordtronic A/S er tilføjet som standardproducent med 77 verificerede artikler i første batch: Quick Install G2, Uni Install G2, fronter, Low Profile Flexible G2-varianter og Zigbee-lyssteueringsprodukter.
- Standardbiblioteket indeholder nu 294 artikler: 179 Schneider Electric / Lauritz Knudsen, 38 Waskönig+Walter og 77 Nordtronic A/S.
- Artikelmetadata er udvidet med produkt-/billedside, datablad, billedkilde samt tekniske felter som diameter, hulmål, CCT, effekt, IP, form og miljø.
- Standardbiblioteket har nye filtre for **Diameter**, **CCT** og **IP**; de eksisterende søgefelter søger også i de nye tekniske specifikationer.
- Preview-panelet har knapper til **Åbn produktkilde**, **Datablad** og **Opdatér foto**.
- Produktfotos redistribueres ikke i program-pakken; de hentes ved behov og caches lokalt på brugerens PC.
- Projektformat/version hævet til 0.40.0.

## 0.39.0

- Tilføjet genbrugelige BOM-styklister med navn, beskrivelse og flere artikelrækker/mængder.
- Ny fane **Styklister** i Artikler/BOM med opret, redigér, duplikér og slet.
- En fysisk symboldel kan nu vælge en stykliste som aktiv BOM-kilde eller fortsat bruge manuel artikelkonfiguration.
- Manuel konfiguration bevares, selv når en stykliste aktiveres, så man kan skifte frem og tilbage uden datatab.
- Ny **Gem manuel som stykliste…**-funktion.
- Styklister er dynamiske: redigering af en stykliste opdaterer automatisk BOM for alle dele, der bruger den.
- Kombisymboler kan vælge stykliste individuelt pr. fysisk modul, stikkontakt og fællesdel.
- Nye projektfelter `bom_assemblies` og `symbol_assemblies`.
- Projektformat/version hævet til 0.39.0.

## 0.38.2

- Artikelbrowseren har fået separate filtre for fabrikat, produkttype, designfamilie, modulstørrelse og farve.
- Tilføjet skematisk grafisk artikelpreview med centrale specifikationer; virker offline og kræver ikke produktfotos.
- Artikelvælgere i symbol- og kabeltilknytning er nu søgbare med indeholder-match.
- Artikelmetadata udvidet med `product_type`, `design_family`, `module_size`, `color` og `mounting_type`; ældre poster får facetter udledt automatisk.
- Tilføjet komplet basisserie af LK FUGA SLIM designrammer: 1M, 1½M, 2×1M og 2½M i hvid, koksgrå og stålmetallic.
- Tilføjet manglende SLIM teknisk monteringsramme 2½M (560D0725).
- Projektformat/version hævet til 0.38.2.

## 0.38.1

- Komplet LK FUGA AIR SLIM-forfradåseserie tilføjet til standardbiblioteket: 1, 1½, 2 og 2½ modul.
- LK-numre/EL-numre/EAN verificeret mod LK/Schneider og Lemvigh-Müller.
- Hulsav er bevidst ikke tilføjet som artikel.
- Standardbiblioteket indeholder nu 204 artikler, heraf 166 LK/Schneider og 38 Waskönig+Walter.
- Projektformat/version hævet til 0.38.1.

## 0.38.0

- Indbygget prædefineret artikelbibliotek med LK FUGA, LK Wiser og Waskönig+Walter.
- Standardbiblioteket er søgbart på artikelnummer, beskrivelse, serie, kategori, EL-nr., EAN og status.
- 201 standardartikler følger programmet (163 Schneider Electric/Lauritz Knudsen og 38 Waskönig+Walter-kabelvarer).
- Standardartikler kopieres først ind i projektets eget artikelbibliotek, når de bruges/importeres; projekter forbliver dermed selvbærende uden at blive unødigt store.
- Projektartikler bevarer nu metadata som serie, kategori, EL-nr., EAN, status, kabelspecifikation, kilde og pakkelængde.
- Ny BOM-fane `Kabeltyper`: en tegnet kabeltype/specifikation kan tilknyttes en konkret Waskönig+Walter-vare.
- Afmålte kabelvarer beregnes direkte i meter ud fra rutelængde inkl. reserve. Rullevarer beregnes som hele ruller, afrundet efter at alle relevante kabelstræk er summeret.
- BOM-tabellen viser beregningsgrundlaget for kabelvarer, fx `86,4 m behov → 1 × 100 m`.
- Kabeltyper uden artikel vises sammen med øvrige manglende BOM-dele.
- CSV-eksporten omfatter nu også kabelartikler og beregningsgrundlag.
- Nyt projektfelt `cable_articles` gemmer kabeltype/specifikation -> artikelnummer.
- Projektformat/version hævet til 0.38.0.

## 0.37.0

Artikler og BOM:

- Nyt projektbaseret artikelbibliotek med artikelnummer, beskrivelse, fabrikat, enhed og note.
- Stikkontakter og afbrydere kan få en eller flere artikler tilknyttet med mængde pr. fysisk del.
- Kombisymboler opdeles i **Modul 1, Modul 2, ...**, stikkontaktdel og en valgfri **Fælles / ramme / tilbehør**-del.
- Modulopdelingen følger den fysiske kombistruktur fra lystilhørs-guiden; en krone er ét fysisk artikelmodul selv om den har to tændingskanaler.
- To ens moduler i samme kombisymbol kan have forskellige artikeltilknytninger.
- `Stikkontakt med enpolet afbryder` opdeles også i afbryderdel, stikkontaktdel og valgfri fællesdel.
- Ny **Værktøjer → Artikler / BOM…** (`Ctrl+B`) med faner for Tilknytning, Artikelbibliotek og BOM.
- Egenskaber viser artikelstatus på det valgte understøttede symbol og har genvej til tilknytningen.
- BOM summerer alle placerede stikkontakter/afbrydere pr. artikelnummer og viser separat obligatoriske symboldele uden artikel.
- BOM kan eksporteres som UTF-8 CSV med semikolonseparator.
- Artikelbibliotek og symboltilknytninger gemmes i `.elplan.json`, så projektet er selvbærende.

## 0.36.1

Stabilitets- og vedligeholdelsesgennemgang:

- Åbn projekt/DWG/DXF og luk program spørger nu sikkert om ikke-gemte ændringer med **Gem / Kassér / Annuller**.
- CAD-filer parses før det aktive projekt udskiftes, så en defekt fil ikke efterlader model og scene i hver sin tilstand.
- Projektfiler og brugerindstillinger gemmes atomisk via midlertidig fil + `os.replace`, så en afbrudt skrivning ikke efterlader halv JSON.
- Projektindlæsning validerer nu NaN/Inf, ugyldige størrelser, kabelpunkter/-porte og dublerede id'er.
- En afvist/korrupt projektfil registrerer ikke længere brugerdefinerede kombisymboler globalt.
- Relative CAD/DXF-stier opløses relativt til projektfilen. **Gem som** genberegner relative CAD-links, så en projektkopi ikke peger på en forkert fil.
- Hvis en manglende CAD-fil lokaliseres manuelt, markeres projektet som ændret, så den reparerede sti kan gemmes.
- Lagvisning for symbolmærkninger er synkroniseret med både symbollag og `EL-TEKST`, så skjulte symboler ikke efterlader flydende labels.
- Sletning af symboler rydder nu dangling kabelreferencer, spot→lampested og forældreløse a/b/c-relationer; Undo gendanner referencebilledet.
- Undo tilbage til den gemte tilstand kan igen fjerne `*` fra titlen, uden at overse ikke-undo projektændringer.
- `start_windows.bat` geninstallerer ikke længere requirements ved hver opstart; installation køres kun, når nødvendige pakker mangler.
- Små døde imports i de aktive Qt-moduler er fjernet.

## 0.36.0

- Automatisk visuel adskillelse af kabler/ledninger, der deler samme rute.
- Parallelle kabelstræk fordeles i symmetriske lanes, så flere kabler ikke smelter sammen til én streg.
- Kabler samles igen præcist i det logiske tilslutningspunkt ved symboler og får et kort fan-in/fan-out.
- Lane-afstanden er kosmetisk/skærmbaseret og påvirker ikke gemt geometri eller kabellængdeberegning.
- Ved valg/redigering vises det aktive kabel på sin oprindelige centerlinje, så redigeringshandles er entydige.
- PDF-preview, PDF-eksport og Windows-print bruger samme parallelle kabelvisning.
- Kabelmærkninger følger den visuelt adskilte bane.

## 0.35.8

Preview / PDF-paritet:

- Udskriftsforhåndsvisningen renderer ikke længere `QGraphicsScene` direkte.
- Preview genererer i stedet en midlertidig PDF med præcis samme `export_vector_pdf()`-pipeline og viser den via Qt PDF.
- Fritekst, CAD-tekst, symboltekst, kabelmærkninger og a/b/c-annotationer får derfor samme fysiske størrelse og placering i Preview som i den gemte PDF.
- Papirmargen og beskæring/fill-page kommer nu direkte fra PDF-siden; den gamle vilkårlige 8 px preview-margen er fjernet.
- Dæmpning af plantegningen og Auto/Minimal/Tydelig/Skjult sendes gennem samme outputparametre som PDF-eksporten.
- Preview rasteriseres kun til skærmvisning; selve Gem PDF er fortsat vektorbaseret.

## 0.35.7

PDF/output-paritet:

- Fritekst i PDF bruger nu samme punktstørrelsesformel som Qt-editoren (`height × 0,065`) i stedet for at blive skaleret med hele CAD→papir-faktoren.
- CAD-tekst bruger samme 0,65-faktor som Qt, og intern symboltekst samme 0,60-faktor. De gamle hårde 3–24/4–24 pt clamps er fjernet.
- PDF-annotationer bruger nu samme visuelle Auto/Minimal/Tydelig/Skjult-profiler og semantiske zoomtrin som editoren.
- Sekundær mærkning skjules i PDF ved oversigtszoom på samme måde som på skærmen.
- Kabelmærkning er justeret til editorens faste ca. 8 pt størrelse og placering.
- Afbryderrelationer eksporteres pr. fysisk modul/kanal i stedet for den gamle samlede a/b/c-tekst.
- Fælles `annotation_visual_profile()` anvendes af både Qt-visning og PDF for at forhindre ny drift mellem de to renderere.

## 0.35.6

- Nye CAD-hjælpelinjer og magnetisk X/Y-snap ved redigering af kabelknæk.
- Kabelknæk kan flugte med andre kabelknæk og relevante symbolporte; kabelendepunkter beholder prioriteret snap til symbol/væg.
- Fritekst har nu samme type snaplinjer både ved første placering og ved efterfølgende flytning.
- Midlertidige snaplinjer ryddes altid ved afsluttet træk og gemmes aldrig i projekt/eksport.
- `3N` i symbolet **Stikkontakt 3F+N+PE** er gjort større og centreret i halvcirklen.
- Symboltekstændringen påvirker ikke den fysiske mating-bredde, der bruges til vægsnap.

## 0.35.5

Tilhørsforhold / afbrydervisualisering:

- Under tilknytning markeres den **konkrete fysiske afbryder/betjening** med en orange halo. På kombiafbrydere følger markeringen det aktuelle modul i guiden.
- Den stiplede guide til musen starter nu fra den aktuelle fysiske betjening i stedet for fra centrum af hele kombisymbolet.
- Guide-teksten placeres ved den aktuelle betjening, så det er tydeligt hvilket modul/tænding der er aktiv.
- Afbrydernes a/b/c-tilhørsforhold vises nu direkte ud for de fysiske afbrydermoduler. En kombi med fx 1P=b, 1P=c og korrespondance=a viser derfor b, c og a ved de respektive moduler.
- Krone, dobbelt korrespondance og 4-tryk samler flere logiske kanaler ved det samme fysiske modul, fx `a · b`.
- Den tidligere samlede a/b/c-tekst i den rumplacerede mærkning er fjernet for afbrydere for at undgå dobbelte/misvisende relationstekster. Lys/lampesteder beholder deres normale tilhørsvisning.

## 0.35.4

Zoom-stabilitet:

- Retter en fejl hvor wheel-events med lodret delta = 0 blev tolket som zoom ud.
- Vandrette/syntetiske wheel-events og touchpad ScrollBegin/ScrollEnd uden reel bevægelse ændrer ikke længere zoom.
- High-resolution touchpad pixel-scroll giver nu et glat, begrænset zoomtrin.
- Zoomgrænsen beregnes mod den faktiske view-transform, så intern zoomtilstand ikke kan drive fra visningen.

## 0.35.3

- Kombiafbrydere gemmer nu en stabil kanal→tilhørsforhold-mapping pr. fysisk betjening i stedet for at udlede modulrækkefølgen fra en alfabetisk sorteret a/b/c-liste.
- Retter især kombinationer som **1-polet + 1-polet + korrespondance**, hvor korrespondancedelen kan genbruge et ældre bogstav (fx `a`), mens de to 1-polede har fx `b` og `c`, uden at kanalrækkefølgen bliver byttet rundt.
- Tilknytningsguiden viser nu den konkrete kombidel, fx **Modul 1 · 1-polet**, **Modul 2 · 1-polet** og **Modul 3 · korrespondance**.
- Efterfølgende redigering vælger den fysiske betjening direkte, så hver del af en kombiafbryder kan få og beholde sit eget tilhørsforhold.
- Korrespondance/krydsning i kombisymboler bevarer samme genbrugslogik som selvstændige korrespondance-/krydsningsafbrydere.
- Kanalrækkefølgen gemmes i projektfilen som `association_channels`; ældre projekter uden feltet migreres automatisk ud fra deres eksisterende tilhørsforhold.
- Undo/redo, Ryd tilhørsforhold og kopiering/indsætning er opdateret, så den nye kanalmapping ikke bliver hængende eller mistes.

## 0.35.2

- Rettet fritekstskalering i Qt-editoren: den skjulte minimumsgrænse på 9 pt er fjernet, så fritekst reelt kan blive mindre end ca. 100 tegneenheder.
- Teksthøjde kan nu indtastes fra 1,0 til 5000,0 tegneenheder med decimaler.
- PDF/forhåndsvisning og legacy-rendering har samme lavere minimum, så små tekststørrelser vises mere konsistent.
- Eksisterende projekter ændres ikke; deres gemte teksthøjder bevares.

## 0.35.1

- Retter flertrinsguiden for kroneafbryder: efter første lampested går guiden automatisk videre til tænding 2.
- Samme guidelogik gælder dobbelt korrespondance, 4 trykkontakter og kombisymboler med flere uafhængige betjeninger.
- Retter en vigtig korrespondancefejl: når en ny korrespondance-/krydsningsafbryder genbruger et eksisterende tilhørsforhold, fjernes bogstavet ikke længere fra lampestedet.
- Korrespondance og krydsning genbruger automatisk et entydigt eksisterende tilhørsforhold; ved flere muligheder spørger programmet.
- Efter fuldført flertrinsguide afsluttes værktøjet automatisk, kildeafbryderen genvælges, og Egenskaber/Anvend ændringer er igen umiddelbart tilgængelig.
- Egenskaber forklarer nu tydeligt, at lystilhørsforhold gemmes straks, mens “Anvend ændringer” gælder de almindelige symbolegenskaber.

## 0.35.0

- Nyt kabellængdeestimat baseret på den faktiske tegnede polyline/rute inkl. alle knækpunkter.
- Automatisk enhedsregistrering fra DWG/DXF `$INSUNITS` for almindelige lineære enheder som mm, cm, m, inch og foot.
- Projektindstilling til manuelt at angive tegningens enhed, hvis CAD-filen ikke har en pålidelig enhedsangivelse.
- Ny kalibreringsfunktion: klik to kendte punkter på plantegningen og indtast den virkelige afstand i meter. Den beregnede skala gemmes i projektet.
- Global kabelreserve i procent gemmes pr. projekt; standard er 10 %.
- Kabelværktøjet viser live rutelængde og estimeret længde inkl. reserve under tegning og ved valg/redigering af eksisterende kabler.
- Ny samlet kabellængderapport med ID, type, kabeltype, rutelængde og længde inkl. reserve for hvert stræk.
- Rapporten summerer materialebehov pr. kabel-/ledningstype og viser samlet længde.
- Længdeberegningen gætter ikke på skalaen: ved ukendt/enhedsløs CAD kræves manuel enhedsregistrering eller kalibrering.

## 0.34.0

- Stor GUI-oprydning med roligere og mere moderne visuel stil.
- Ny klassisk menulinje: Fil, Rediger, Værktøjer og Vis.
- Hovedværktøjslinjen er reduceret til de funktioner, der bruges under tegnearbejde.
- Symboler og Lag deler nu venstre sidepanel som faner i stedet for at være stablet lodret.
- Symbolpaletten har fået søgefelt, kompakt placering/størrelsesblok og bedre udnyttelse af pladsen.
- Egenskaber er samlet i tydelige sektioner og ligger i et scrollbart panel.
- Startbredder for venstre/højre arbejdsområder er justeret for mere plads til plantegningen.
- Statuslinjen viser nu zoom og antal symboler som diskrete statusfelter.
- Eksisterende funktioner, herunder Auto-mærkning og Lys-snap, er bevaret.

## 0.33.0

- Nye dynamiske vandrette/lodrette hjælpelinjer ved placering og flytning af belysning, lampesteder og spots.
- Magnetisk center-snap til eksisterende synlige belysningssymboler med zoomuafhængig skærmtolerance.
- X- og Y-retning snapper uafhængigt, så præcise rækker og kolonner er nemme at opbygge.
- Hjælpelinjer er midlertidige og gemmes ikke i projektet.
- Spot-række og Spot-rektangel snapper også start-/slutpunkt til eksisterende belysningslinjer.
- Ny checkbar **Lys-snap**-knap i topbjælken. Indstillingen er aktiv som standard og gemmes i app-indstillingerne.
- Gruppeflytning ignorerer de øvrige valgte symboler som snap-referencer, så gruppen ikke snapper til sig selv.

## 0.32.1

- Auto-visningen viser nu `a/b/c`-tilhørsforhold allerede ved fuld plantegning/oversigtszoom.
- Tilhørsforholdet tegnes ved oversigtszoom som lille blå tekst uden baggrund/chip, så det kan aflæses uden at dominere plantegningen.
- Gruppe/kreds forbliver den primære diskrete mærkning; valgfri mærkning og Spot→lampested kommer fortsat først frem ved tættere zoom eller valg.
- De egentlige relationslinjer er fortsat valg-baserede for at undgå visuel støj.

## 0.32.0

- Ny semantisk **Auto**-mærkning med væsentligt mindre visuel støj.
- Ved meget langt zoom skjules automatisk symbolmærkning helt.
- Ved oversigtszoom vises kun Gruppe/kreds som lille tekst uden den tidligere dominerende chip.
- Valgfri mærkning, `a/b/c` og Spot→lampested kommer gradvist frem ved tættere zoom; valg af symbol viser fuld detalje.
- **Minimal** viser nu kun primær Gruppe/kreds.
- Ny visning **Skjult** skjuler al automatisk symbolmærkning og normal relationsoversigt.
- Ny checkbar **Mærkning**-knap i topbjælken til hurtigt at skjule/vise mærkning og vende tilbage til senest brugte visning.
- Normale relation/tilhørsforholdslinjer er gjort tyndere og mere transparente og skjules sammen med mærkningen i Skjult-visning.
- Enkeltplacerede spots bruger nu den dedikerede Spotstørrelse i både preview og faktisk placering.
- Et enkeltplaceret spot vælges automatisk efter placering, så **Spot → lampested → Tilknyt lampested…** straks kan bruges fra Egenskaber.
- Aktiv Spot→lampested-picker virker fortsat også når normal mærkning er skjult.

## 0.31.2

- Auto-mærkning er gjort markant mindre dominerende ved hel-plantegning/oversigtszoom.
- Auto har nu flere zoomniveauer:
  - meget langt zoom: meget kompakt Gruppe/kreds; a/b/c skjules kun ved ekstremt langt zoom
  - normal oversigt: mindre Gruppe/kreds og mindre a/b/c
  - mellemzoom: større og mere læsbare chips
  - valgt symbol / Tydelig: fuld størrelse og alle detaljer
- Valgfri `Mærkning` og Spot→lampested-info skjules tidligere i oversigtszoom, mens primær Gruppe/kreds bevares.
- Chip-padding, kant og baggrundsopacitet skaleres også med zoom, så mærkninger ikke bliver store hvide blokke over en hel plantegning.
- Ny automatisk **rumsideplacering** for mærkning.
- For vægmonterede symboler bruges montagepunkt, symbolretning og nærmeste væg til at vælge den side, der mest sandsynligt er rummet symbolet sidder i.
- Hvis symbolets centrum ligger tydeligt på én side af væggen, placeres mærkningen på samme side.
- Ved symboler placeret direkte på væglinjen bruges symbolgeometri/væg-normal som retning; ved tvivl vælges den side med mere fri CAD-plads.
- Rumsideplacering kan slås til/fra under `Lag → Mærkning / tilhørsforhold`.

## 0.31.1

- Hotfix: rettet opstartsfejl i 0.31.0, hvor `QGraphicsItemGroup` ikke var importeret i `qt_graphics.py`.
- `start_windows.bat` kontrollerer nu også returværdien fra `python main.py`.
- Ved runtime-fejl holdes CMD-vinduet åbent med `pause`, så traceback kan læses/screenshot'es i stedet for at vinduet bare forsvinder.
- Afhængighedsinstallation giver ligeledes en tydelig fejlblok og pause.

## 0.31.0

- Mærkningsrenderingen er bygget om til native Qt-grafikdele i stedet for custom painter. Gruppe/kreds vises nu igen stabilt og tydeligt som en kompakt hvid/grøn primær chip.
- Valgfri mærkning vises som en mindre sekundær chip, a/b/c som separat blå chip, og spots får en turkis `↳ <lampested>` chip.
- Tilhørsforhold er ændret til en egentlig mange-til-mange model:
  - én afbryderbetjening (`a`) kan tilknyttes flere lampesteder/lamper
  - ét lampested kan samtidig have flere tilhørsforhold (`a, b, c`)
  - klik på et lys under en aktiv betjening toggler det til/fra samme tilhørsforhold
- Afbryderens `association_capacity` bruges nu kun til antal uafhængige betjeninger, ikke antal lampesteder.
- For krone-/multi-afbrydere kan man vælge hvilken eksisterende betjening der skal redigeres eller vælge `+ Ny betjening`.
- Hvis første valgte lampested allerede har et tilhørsforhold, kan man vælge mellem nyt tilhørsforhold eller at dele et eksisterende, fx ved korrespondance.
- Aktive relationer vises med kraftigere blå målmarkering, og samme betjening kan redigeres på flere lys uden at forlade værktøjet.
- Valg af afbryder eller lampested viser diskrete blå relationslinjer til alle modparter, der deler a/b/c.
- Spot → lampested er nu en separat, synlig relation:
  - linked spots viser `↳ Gxx`/lampested som turkis chip
  - valg af et lampested viser turkise linjer til alle tilknyttede spots
  - valg af et spot viser dets lampested og sibling-spots
  - Egenskaber har et særskilt `Spot → lampested`-panel med Tilknyt/Frakobl
  - spot-pattern fremhæver mulige lampesteder turkis efter placering
- Spots der har et lampested arver fortsat alle lampestedets a/b/c-forhold og kan derfor vise flere tilhørsforhold.

## 0.30.9

- Byttet mærkningshierarkiet om: **Gruppe/kreds er nu den primære mærkning**.
- `G01`, `G12` osv. vises som den tydelige, mørkegrønne hovedtekst.
- Det valgfrie felt `Mærkning` er nu sekundær information og vises som et mindre, diskret badge.
- Auto-visning bevarer Gruppe/kreds ved oversigtszoom og kan skjule den valgfrie mærkning for at reducere overlap.
- Egenskabspanelet og direkte mærkningseditor viser nu `Gruppe/kreds (primær)` før `Mærkning (valgfri)`.
- Opdelte kombisymboler prioriterer ligeledes gruppe/kreds pr. afbryder-/stikmodul.
- Fritekst i Qt-vieweren bruger nu screen-space rendering, så rumnavne og noter ikke bliver mikroskopiske ved oversigtszoom.
- Fritekst har fået større minimumsstørrelse og en mere læsbar standardvægt.
- Standardhøjden for ny fritekst er hævet fra 200 til 240 tegningsenheder. Eksisterende projekters gemte teksthøjde bevares.

## 0.30.8

- Eksisterende kabler/ledninger er nu valgbare og kan redigeres efter placering.
- Ved valg af kabel vises faste blå redigeringshåndtag ved ender og knækpunkter.
- Kabelender kan trækkes og snapper igen til symbolers forbindelsespunkter eller vægge; logiske symbolforbindelser opdateres samtidig.
- Ortogonale kabelender og knæk bruger den eksisterende 90° polyline-motor, så redigering kan bevare ortogonal routing.
- Dobbeltklik direkte på et valgt kabel tilføjer et knækpunkt på nærmeste segment.
- Højreklik på et indre blåt knækpunkt fjerner det. Ortogonale kabler bevarer 90°-føring ved fjernelse.
- Kabelværktøjet skifter til redigering af det valgte kabel og kan ændre type, kabelspecifikation, ID, ekstra mærkning, linjetykkelse, automatisk mærkning og ortogonal/fri routing.
- Kabelgeometri og kabelegenskaber understøtter Undo/Redo.
- Delete kan nu også slette valgte kabler med Undo/Redo.
- Ny mærkningsvisning med tre niveauer: Auto, Tydelig og Minimal.
- Mærkning har et nyt visuelt hierarki: primær mærkning med smal hvid halo, gruppe/kreds i et diskret grøngråt badge og tilhørsforhold i et separat tydeligt blåt badge.
- Auto-visning skjuler sekundær gruppe/kreds ved langt zoom for at reducere overlap; valg af et symbol viser midlertidigt fuld detalje.
- Tilhørsforhold forbliver synlige i Auto/Minimal, så a/b/c er let at aflæse selv ved oversigtszoom.

## 0.30.7

- Ny valgmulighed **Brug også dæmpning i PDF og udskrift** under Plantegning / baggrund.
- PDF, print-preview og direkte Windows-udskrift kan nu bruge samme matte/grå CAD-baggrund som Qt-vieweren, mens el-symboler, kabler og mærkninger forbliver i fuld kontrast.
- Eksportdæmpning implementeres som neutral grå i stedet for printerafhængig transparens, så resultatet bliver stabilt på både PDF og fysiske printere.
- Vægsnap ved ny symbolplacering har fået hysterese: symbolet låser midlertidigt på den valgte væglinje og hopper ikke straks til nabolinjer/hjørner.
- Vægmonterede symboler vælger automatisk 0/180°-siden ud fra hvilken side af væggen cursoren befinder sig på. Man behøver derfor langt sjældnere at rotere stikkontakter/kombisymboler manuelt før placering.
- Symbol-til-symbol-snap er gjort lidt mindre aggressivt for vægmonterede symboler.
- Den automatiske vægorientering bevares mellem mouse-move events, så symbolpreviewet ikke nulstiller rotationen for hvert event.
- Zoom under symbolplacering er rettet: preview-symbolet bruges som eksplicit zoom-anker, så det bliver på samme sted på skærmen under musehjulszoom.
- Uden aktiv symbolplacering zoomes der fortsat omkring musemarkøren.

## 0.30.6

- Nyt **Kabelværktøj** som dockbart arbejdsområde i stedet for en engangs-dialog.
- Kabeltype, kabel-ID, kabelmærkning, linjetykkelse, ortogonal/fri føring og snap kan ændres samlet og live under kabeltegning.
- Kabelværktøjet kan fortsætte automatisk med næste kabel og genererer næste `Kxx` / `Lxx`.
- Backspace fjerner sidste knækpunkt; højreklik/Enter afslutter aktuelt kabel; Esc annullerer aktuelt kabel uden at lukke værktøjspanelet.
- Kabelværktøj-knappen forbliver visuelt markeret, mens værktøjet er åbent.
- Ny **Fremhæv elplan**-funktion: DWG/DXF-baggrunden kan dæmpes uden at påvirke el-symboler, mærkning, kabler eller PDF/print.
- Lagpanelet har justerbar `Plantegning / baggrund`-tydelighed med Mat / Normal / Fuld presets.
- Elektriske symboler er gjort en anelse kraftigere på skærmen.
- Mærkning har tydeligere visuelt hierarki: selve mærkningen er stærkere, gruppe/kreds mere afdæmpet, og tilhørsforhold er tydeligere blå/bold.
- Baggrundsdæmpningen er en ren viewer-indstilling og ændrer ikke eksport/print.

## 0.30.5

- Rettet fejl hvor et symbol kunne hoppe/snappes blot ved at klikke på det. Snap aktiveres nu først efter en reel drag-bevægelse.
- Mærkninger er gjort mindre dominerende: gruppe/kreds vises mindre og mere afdæmpet, hvid baggrundsboks er fjernet, og annotationen placeres med fast skærmafstand uden for symbolgeometrien.
- Annotationer repositioneres ved zoom, så afstand til symbolet forbliver visuelt konstant.
- Tilhørsforhold har nu tydelig 2-trins workflow: tryk først **Tilknyt lys**, klik en orange fremhævet afbryder og klik derefter et blåt fremhævet lys. Hvis en afbryder allerede er valgt, springes trin 1 automatisk over. Der vises samtidig en guide-linje og tydelige statusbeskeder.
- Krone-/multi-afbrydere bliver i tilknytningstilstand indtil alle nødvendige tilhørsforhold er valgt.
- Egenskabspanelet viser antal anvendte/mulige tilhørsforhold og aktiverer kun Tilknyt-knappen på relevante afbrydere.

## 0.30.4

- Migreret spot-række og Spot-rektangel til Qt med live preview, valgfri spotstørrelse og tilknytning til lampested.
- Migreret fri tekst: placering, flytning, dobbeltklik-redigering og Undo/Redo.
- Direkte dobbeltklik-redigering af symbolmærkning og gruppe/kreds, inkl. kombisymbolernes opdelt/fælles mærkning.
- Copy/paste for flere valgte symboler og tekstobjekter; relative placeringer bevares.
- Forbedret multi-select med rubber-band, gruppeflytning, gruppe-rotation og gruppe-sletning.
- PDF-eksport, direkte udskrift og Qt-print-preview med A4/A3, orientering og Aktuel visning/Hele tegningen.
- Eksisterende vektorbaseret PDF/printmotor fra 0.24.x genbruges.

## 0.30.3

- Qt-symbolkonfigurator med live preview, automatisk palettenavn, gemte skabeloner og favorit-symboler.
- Migreret kombisymbolernes fælles/opdelte mærkning til Qt-egenskabspanelet.
- Ny Rotér +90°-handling med Ctrl+R og QUndoStack.
- Ny Qt-kabel/ledning-værktøj med ortogonal tegning, kabeltyper, automatisk ID, kabelmærkning og snap til symbolporte/vægge.
- Logiske kabelender følger igen symboler, når de flyttes eller roteres.
- Migreret afbryder ↔ lys-tilhørsforhold med automatisk a/b/c-nummerering og krone-/multi-afbryderkapacitet.
- Ryd tilhørsforhold og Undo/Redo for relationer.
- Farve, linjetykkelse, låsning og kombi-felter er udvidet i Qt-egenskabspanelet.

## 0.30.2

- Første interaktive Qt-milepæl med grafisk symbolpalette.
- Nye symboler placeres direkte i `QGraphicsScene` med kontinuerlig placering og Esc for afslutning.
- Qt-native snap-pipeline til synlig CAD/vægge og eksisterende el-symboler med VÆG/SYMBOL-feedback.
- Eksisterende symboler snapper også under direkte Qt-drag.
- Undo/Redo via `QUndoStack` for symbolplacering, flytning og sletning.
- Palette og snap genbruger den validerede vektorgeometri/projektmodel fra legacy-core.

## 0.30.1

- Rettet Qt UI på Windows med mørkt systemtema: appen bruger nu en eksplicit lys Fusion-palette.
- Rettet næsten usynlig tekst på toolbar, docks, felter og knapper.
- CAD-vieweren har nu eksplicit hvid baggrund i både scene og view.
- Tilføjet tydelige farver for normale, hover, checked og disabled kontroller.

# Changelog

## 0.30.1

- Første PySide6/Qt-version.
- Ny QMainWindow med dockable lag- og egenskabspaneler.
- Ny QGraphicsScene/QGraphicsView-baseret CAD-viewer.
- Statisk CAD geometri aggregeres pr. lag for at reducere antal Qt graphics items markant.
- Eksisterende 0.24.x projektformat kan åbnes og gemmes.
- Eksisterende symboler, kabler, fritekst og annotationer vises.
- Symboler kan vælges, flyttes og få redigeret basale egenskaber.
- Zoom, pan og fit-to-view er Qt-native.
- ODA File Converter-konfiguration genbruger den eksisterende kerne.
