# Elplan DWG Editor

Et Windows-orienteret planlægningsværktøj til elektriske installationer på DWG/DXF-plantegninger. Programmet samler symbolplacering, kabelruter, PL-dåser, rum, artikler, styklister, priser og BOM-eksport i én arbejdsgang.

**Aktuel version: 0.59.73**

## Hurtig start

1. Installer Python 3.11 eller nyere.
2. Kør `python -m pip install -r requirements.txt`.
3. Start med `python main.py` eller `start_windows.bat`.
4. Kør test med `python -m pytest -q` efter ændringer.

Brugerens projekter, lokale indstillinger og globale artikel-/prisdata er bevidst ikke en del af Git-repositoriet. Artikeldatabasen kan fortsat ligge separat i en synkroniseret OneDrive-mappe.

## Artikeltypefilter i BOM og Excel — 0.59.73

BOM-fanen kan nu filtrere og sortere efter en kort, praktisk artikeltype som **Dåser**, **Rammer**, **Afdækninger**, **Tangenter**, **Indsatser**, **Stikkontakter og udtag**, **Kabler** eller **Samlemuffer og klemmer**. Typen vises som sin egen kolonne og kan også bruges til gruppering.

Kategoriseringen bruger både artikeldata og komponentens rolle i en stykliste. Derfor kan en afbryderartikel med rollen *Indsats* adskilles fra dens tangent, og tekster som *uden tangent* eller *uden afdækning* giver ikke falske kategorier.

Excel-eksporten følger det valgte artikeltypefilter og indeholder samtidig kolonnen **Type/kategori** med Excels almindelige tabel-filter og sortering. CSV og BOM-PDF følger også den aktuelle filtrerede visning.

## Effektiv artikel- og styklistehåndtering — 0.59.72

Artikler kan nu skelne mellem **forbrugsenhed** og **salgsenhed**, herunder antal pr. pakke/rulle og mindste bestilling. BOM'en viser fortsat det reelle behov, men beregner en pakkepris på det afrundede indkøbsantal og en styk-/meterpris på det faktiske forbrug. Ældre kabelruller udledes automatisk af deres eksisterende pakkelængde.

BOM har fået fanen **Kontrol** og hurtigfiltre for manglende artikler, forældede priser og pakningsdata. Artikeldatabasen har samtidig fået **Hvor bruges?**, som samler aktuelle forekomster og globale styklister for én artikel.

Styklisteeditoren er gjort tabelcentreret: komponentformularen ligger i et kompakt sidepanel, som er skjult som standard, kan åbnes med et dobbeltklik og skjules igen med **Maksimér tabel**. Flere tabelrækker kan markeres og fjernes samlet.

## Læsbar 3-polet stikkontakt — 0.59.71

Symbolet **Stikkontakt 3F+N+PE** har nu en kompakt `3N`-mærkning, som følger stikkontaktens placering, men altid står vandret. Derfor forbliver mærkningen læsbar på både vandrette og lodrette vægge uden at ligge oven i symbolstammen. Visning, PDF, DXF/DWG og direkte print bruger samme regel.

## WAGO-priser som stykpris — 0.59.70

WAGO-samlemuffer vises og summeres nu altid pr. fysisk muffe i BOM, symbol-hover, styklister, prissammenligning, udskrift og PDF. Prisimporten finder pakkestørrelser i både URL, sidetitel, strukturerede produktdata og synlig tekst. Hvis en grossist beskriver en hel salgsæske som `1 stk.`, bruges den kendte WAGO-underpakning som sikker fallback; almindelige enkeltstykpriser forbliver uændrede.

Ved opgradering fjernes gamle automatiske WAGO-estimater, der kan være pakkepriser. Manuelle priser bevares. De tre indbyggede 221-stykprisestimater genindlæses automatisk i eksisterende artikelbaser, så BOM'en straks har et fornuftigt stykprisgrundlag, og en senere webshopopdatering kan erstatte dem med aktuelle normaliserede observationer.

## BOM pr. rum i PDF — 0.59.69

Når BOM-visningen står på **Alle rum**, er **Medtag BOM pr. rum** nu slået til som standard i udskriftsforhåndsvisningen. PDF'en starter fortsat med den autoritative samlede BOM og tilføjer derefter en enkel sektion for hvert rum med de samme fem kolonner og en tydelig delsum. Små rum kan dele side, mens større tabeller fortsætter naturligt over flere sider med gentagne kolonneoverskrifter.

Rumopdelingen bruger præcis samme rum-, kabel-, pris-, moms- og hurtigfilterlogik som Excel-eksporten. En kort forklaring gør opmærksom på, at summen af rum kan overstige projekttotalen, når en fysisk vare med vilje er tilføjet til et ekstra BOM-rum. Hvis ét konkret rum allerede er valgt på BOM-fanen, vises kun dette rum som hidtil.

## Enkel BOM-udskrift med preview — 0.59.68

BOM-fanen har nu **Udskriv / PDF…**, som altid åbner en A4-forhåndsvisning før output. Herfra kan den samme viste BOM enten sendes direkte til printeren eller gemmes som PDF. Den printvenlige liste indeholder bevidst kun varenummer, beskrivelse, antal, enhedspris og beløb samt en tydelig total og korte advarsler om manglende priser eller artikeltilknytninger.

Preview, PDF og udskrift følger den aktuelle BOM-visning: valgt rum, hurtigfilter, synlige/skjulte kabler, sortering og det globale valg mellem priser inkl. eller ekskl. moms. Excel- og CSV-eksporten er bevaret til de mere detaljerede data.

## Rumnavne i PDF og udskrift — 0.59.67

PDF-preview, PDF-eksport og direkte udskrift medtager nu projektets rumlag. **Vis rumnavne**, **Vis rummærkning** og **Vis rumafgrænsninger** forbliver tre uafhængige valg, så et rent rumnavn kan vises uden rum-ID eller polygon. Rumtekster beholder en fast, læsbar fysisk størrelse i output og følger både `EL-RUM`-lagets synlighed og den aktuelle rumvisning.

## Effektiv PL-lederfordeling — 0.59.66

Lederfordelingen har nu en kompakt, klikbar problemnavigator. `Næste uløste` eller `F8` springer direkte til den relevante leder eller klemme, mens `Foreslå fordeling…` viser sikre og mulige valg i en forhåndsvisning. Der forbindes fortsat aldrig ledere uden brugerens godkendelse. Hover og markering genbruger desuden de normaliserede PL-data, så den grafiske arbejdsflade reagerer hurtigere.

## Gennemsløjfninger og tydeligere ledergrafik — 0.59.65

En samlemuffe uden forbindelse til det lokale lampeudtag får nu sin egen elektriske identitet. Vælg **Tændleder**, **Mellemleder 1/2**, PE, N, L eller reserve og – for tænd-/mellemledere – det lampested og tilhørsbogstav, som forbindelsen faktisk tilhører. Direkte og sammenhængende kabelveje foreslås øverst. Mellemlederne gemmes som to adskilte net, så de ikke kan samles ved en fejl.

PL-grafikken bruger større, reelt adskilte routingzoner, så parallelle lederkurver ikke falder oven i hinanden. En lokalt løs leder, der allerede er allokeret ved kablets anden ende, afsluttes med et blåt kædeled i stedet for `?`; hover viser funktion og lampested. Markeringen er kun information – lederen skal stadig forbindes fysisk i den aktuelle dåse.

## Pris i symbol-hover og samlede indstillinger — 0.59.63

Symbol-hover viser nu både pris pr. artikel, linjesum ved flere styk, styklistepris og en samlet symbolpris. Prisvisningen følger det samme globale valg mellem **ekskl. moms** og **inkl. moms** som Artikler/BOM og eksport. Manglende priser og prisdækning markeres direkte i hover-kortet, og valutaer summeres hver for sig.

Et nyt panel under **Værktøjer → Indstillinger…** samler globale valg i områderne **Visning**, **Priser og BOM** samt **Lager og synkronisering**. Det eksisterende momsvalg i Artikler/BOM er bevaret som hurtigvalg, men begge steder skriver til præcis samme globale indstilling. Projektlager og de uafhængige globale artikeldata kan desuden åbnes fra lagerområdet.

Hoverens artikel- og prisopslag genbruges, indtil artikelkataloget eller prisbogen faktisk ændrer sig. Det undgår gentagen normalisering af hele kataloget, når flere symboler inspiceres.

## Rumoversigt i Excel og kabel-filter i BOM — 0.59.62

Excel-eksport med **Alle rum** indeholder nu tre pris- og materialelag: den autoritative samlede **BOM**, en kompakt **Rumoversigt** med delsummer og prisdækning pr. rum/valuta samt den detaljerede **BOM pr. rum**. Rumoversigten gør det hurtigt at sammenligne rummene, men markerer samtidig, at summen af rum kan overstige projekttotalen, når en fysisk installation med vilje tæller med i et ekstra BOM-rum.

BOM-fanen har desuden fået hurtigvalget **Vis kabler**. Når det slås fra, genberegnes artikelrækker, mangelliste, priser og totaler helt uden kabelbidrag; Excel- og CSV-eksport følger det samme valg. Kabeltilknytningerne ændres eller slettes ikke.

## Prissammenligning og valgfri momsvisning — 0.59.61

I **Artikler og BOM** kan prisvisningen nu skiftes samlet mellem **ekskl. moms** og **inkl. moms**. Valget gælder artikeloversigter, prisredigering, styklister, BOM-totaler samt CSV- og Excel-eksport og huskes på den aktuelle pc. De autoritative priser gemmes fortsat ekskl. moms, så eksisterende priser, projekter og beregninger bevarer præcis samme betydning.

For artikler med hentede webshoppriser åbner **Sammenlign forhandlere…** en særskilt sammenligning af WATTOO, LavprisEL og Greenline. Priser sammenlignes pr. normaliseret enhed og separat pr. valuta/enhed; den billigste fremhæves, prisforskellen vises, og den oprindelige pakkepris bevares ved siden af stykprisen. Forhandlerens produktside kan åbnes direkte fra tabellen.

## Separat artikeldata i OneDrive — 0.59.60

Under **Fil → Lager og synkronisering → Artikeldata…** kan det globale artikelkatalog, prisbogen og de globale styklister flyttes til en særskilt synkroniseret mappe, fx `OneDrive/Elplan/Artikeldata`. Artikeldataene deles fortsat af alle projekter, men ligger aldrig i det enkelte projekt eller i projektlagerets mappestruktur.

Ved flytning flettes lokale og allerede eksisterende måldata. Målplaceringen sikkerhedskopieres først og har forrang ved konflikter; manglende lokale artikler, priser og styklister tilføjes. Den gamle placering slettes ikke. Indstillinger, logs og cache forbliver lokale på pc'en.

## UI/UX-oprydning og organisering — 0.59.57

0.59.57 er et konsoliderings-pass uden nye projektfunktioner. **Artikler og BOM** genopbygger nu kun den fane, brugeren faktisk ser, husker senest brugte arbejdsfane og skjuler den lange grundforklaring bag en diskret fold-ud-hjælp. Kabelinspektøren er samtidig gjort roligere ved at fjerne dobbelte rammer og overskrifter i de foldbare sektioner. Projektdata og beregningslogik er uændrede.

## Animeret projektåbning — 0.59.35

Projekt- og CAD-åbning har nu en diskret fuldskærmsanimation med et blueprint-inspireret projektikon, faktiske procestrin (**Projektdata → Tegning → Arbejdsflade**), blød fade ind og en kort **Projekt klar**-afslutning. Der vises fortsat indetermineret fremdrift i stedet for et opdigtet procenttal, fordi CAD-parsing og sceneopbygning ikke leverer pålidelige procentdata. Animationen ændrer ikke projektdata eller selve indlæsningsrækkefølgen.

## Ydelsesoptimering af Artikler og BOM — 0.59.34

0.59.34 fokuserer udelukkende på at gøre Artikler/BOM hurtigere at åbne og opdatere. Katalognormalisering, pris-overlay, søgeindeks, datakvalitet og BOM-filtertælling genbruger nu allerede beregnede data langt mere aggressivt. Funktionaliteten og de autoritative BOM-totaler er uændrede.

## Samlet navngivning i styklisteeditoren — 0.59.33

Navneparametrene er nu direkte redigerbare i selve styklisteeditoren og deles én-til-én med Navneassistenten. **Udfyld fra stykliste** genfortolker aktuelt navn og komponenter, mens **Dan navn** er den eksplicitte handling der erstatter navnefeltet. Manuelle navne er fortsat fuldt understøttet. Kategori/Variant er tydeliggjort som frie ekstra biblioteksfelter, så system/serie, type, opbygning og farve ikke skal indtastes to steder. Genererede navne bruger den kompakte visning `FUGA SLIM`, mens det strukturerede filterfelt fortsat gemmer den verificerede værdi `LK FUGA SLIM`.

## Strukturerede stykliste-navne — 0.59.32

Styklister kan nu have strukturerede navneparametre for **Type, Opbygning, Funktion, System/serie, Montering og Farve** samtidig med et helt frit manuelt navn. Parametrene bruges direkte til sortering og filtrering i styklistebiblioteket. System/serie vælges fra en kurateret liste med dokumenterede LK/Schneider-betegnelser, så eksempelvis AIR ikke forveksles med FUGA-designserier som SLIM, SOFT, PURE og CHOICE. Brug **Ryd navneparametre** hvis en stykliste kun skal have et manuelt navn.

## Navneassistent til styklister / montager — 0.59.31

Montageeditoren kan nu danne et konsistent navneforslag ud fra Type, Udførelse, System/serie, Farve og ekstra tekst. Assistenten er frivillig: den ændrer først navnet ved **Brug navn**, og det almindelige navnefelt kan altid redigeres frit bagefter. Dropdowns er redigerbare og kan forsigtigt forudfyldes fra den eksisterende montage.

## Stykliste-/montagehåndtering 2.0 — 0.59.30

0.59.30 gør globale styklister til et egentligt montagebibliotek med kategori, variant, tags, noter, faste/valgfrie komponenter, anvendelsestælling, montagepris og navigation tilbage til plantegningen. Valgfrie komponenter kan være gemt i montagen uden at blive medtaget i BOM, indtil de aktiveres.

## Artikelbrowser 2.0 0.59.29

Artikeldatabasen har nu kaskaderende facetter, Favoritter, Senest anvendte og Brugt i projekt. Søgning rangerer sikre identitetsmatch højest og bruger favorit/projekt/seneste som sekundære produktivitetssignaler. Variantgrupper kan navigeres direkte i previewet, og det vises hvilke styklister en artikel indgår i.

## BOM UX og sporbarhed 0.59.28

BOM'en kan nu bruges som både materialeliste og forklaringslag. Artikler viser hvilke styklister/kilder der har skabt dem, anvendte styklister kan foldes ud som montager, og den nye Kilder-visning kan gå direkte tilbage til det konkrete symbol eller kabel på plantegningen. Den eksisterende BOM-total er fortsat autoritativ og ændres ikke af de nye visninger.

## Pakningspriser 0.59.27

Webshopprisimporten skelner mellem salgs-pakke og fysisk BOM-enhed. Fx bliver en æske med 100 WAGO-muffer til 331 kr. normaliseret til 3,31 kr./stk. inkl. moms. Tvetydige pakningssider afvises. Manuelle priser har fortsat højeste prioritet.

## BOM-summering 0.59.26

BOM-fanen viser en fremhævet summeret pris ekskl. moms for den aktuelle visning. Summen følger det valgte rumfilter og advarer, hvis nogle af de viste linjer ikke har pris.

## Webshoppriser fra WATTOO, LavprisEL og Greenline 0.59.25

Artikeldatabasen kan nu hente offentlige webshoppriser via **Opdatér priser…**. Match foretages på EAN, EL-nr. eller producentnummer; produktnavn alene er ikke nok. Hver observation gemmes med kilde, URL, dato og både pris inkl. og ekskl. moms. Det automatiske BOM-estimat gemmes ekskl. moms og beregnes robust på tværs af de valide kilder. En manuel pris har fortsat altid prioritet og kan ikke overskrives af prisopdateringen. Brug helst **Kun artikler i BOM**, **Kun uden pris** eller **Forældede > 7 dage** for at holde trafikken til webshops lav.

## Prisestimat og manuelle priser 0.59.23

Artikeldatabasen kan nu have både et **estimeret prisniveau** og en separat **manuel pris**. Den manuelle pris har altid prioritet i BOM og eksport, men estimatet slettes ikke og kan derfor fortsat opdateres fra en import/kilde senere. Prisdata gemmes i den globale prisbog og påvirkes ikke af LK-synkronisering. Artikeldatabase og standardbibliotek viser prisstatus, kilde og opdateringsdato; estimater markeres med `~`. Excel/CSV-BOM indeholder både estimat, manuel pris, anvendt pris, pris-enhed, kilde, dato og linjesum. Kabelpriser pr. meter beregnes på det faktiske meterbehov.

## Filterbar Excel-BOM pr. rum 0.59.22

Ved Excel-eksport med **Alle rum** oprettes nu både den autoritative samlede `BOM`-fane og en separat **`BOM pr. rum`**-fane. På rumfanen indeholder kolonnen `Rum` præcis ét konkret rum pr. række, så Excels almindelige autofilter kan vælge et enkelt rum direkte. Kabelmængder fordeles efter den faktiske kabellængde i rummet, og manuelle ekstra BOM-rum respekteres. Den samlede BOM forbliver separat, så additive rumtilknytninger ikke giver en misvisende projekttotal.

## Projektkontrol, rum-dashboard og BOM-navigation 0.59.16

- `Værktøjer → Projektkontrol…` samler handlingsorienterede mangler og kan hoppe direkte til objektet.
- `Værktøjer → Rum → Rum-dashboard…` viser installation, grupper, kabler og BOM for ét rum samt kan aktivere rumfokus.
- I BOM kan en artikel dobbeltklikkes eller vælges med **Vis på plan** for at se alle konkrete forekomster på plantegningen.
- Et valgt symbol kan under **Artikler / BOM → Ekstra BOM-rum…** tælle med i et ekstra rum uden at blive flyttet eller skifte gruppe/kreds. Det er nyttigt til fx køleskab/fryser/ovn, som fysisk står i Gang men skal indgå i Køkkenets rum-BOM.

## Formateret Excel-eksport af BOM 0.59.15

BOM-fanen kan nu eksportere den aktuelle visning direkte som **Excel (.xlsx)** samtidig med at den eksisterende **CSV**-eksport bevares. Excel-eksporten følger det aktive rumfilter og den valgte sortering og opretter en rigtig Excel-tabel med autofilter, fastfrosset overskrift, passende kolonnebredder samt numeriske felter for antal, enhedspris og linjesum. Eventuelle ikke-tilknyttede dele placeres på et separat ark, så hoved-BOM'en forbliver ren og filtrerbar.

# Elplan DWG Editor 0.59.12 — Qt/PySide6


## Rumfiltreret BOM og WAGO P100 0.59.12

BOM-listen har nu et synligt **Vis rum**-felt. **Alle rum** viser den normale samlede BOM som før. Vælges et konkret rum, genberegnes listen til kun de symbolartikler, Wago-samlinger og den faktiske kabellængde, der fysisk ligger i det valgte rum. **Uden rum** viser bidrag uden for definerede rumpolygoner. Sortering og hover-billedpreview fungerer fortsat uafhængigt af filteret, og CSV-eksport følger det aktive rumfilter.

Artikeldatabasen er samtidig udvidet med WAGO **2273 / P100** PUSH WIRE-samlemufferne 2273-202, -203, -204, -205 og -208 med LM-/EAN-data, producent-/leverandørlinks og officielle WAGO-produktbilleder. De eksisterende 221-412, 221-413, 221-415 og 221-420 har også fået officielle WAGO-billeder, så BOM/Artikeldatabase-hover kan vise produktfoto.


## BOM: Rum og produktfoto ved hover 0.59.11

BOM-listen har nu en **Rum**-kolonne og et synligt **Sortér efter**-felt. Artikler for symboler får rummets navn/mærkning fra den definerede rumpolygon; kabelartikler får alle rum, som det fysiske kabel faktisk løber igennem. Samme artikelnummer forbliver én samlet BOM-linje, så mængder og prisberegning er uændret. Bidrag uden for definerede rum vises som **Uden rum**.

Hold musen kort over en artikelrække i BOM'en for at få et billed-popup ved cursoren. Det bruger den samme produktfoto/cache-motor som Artikeldatabasen og falder tilbage til den skematiske artikelillustration, hvis et onlinefoto ikke er tilgængeligt. Popup'en er kun visuel og tager ikke fokus eller museklik. CSV-eksporten indeholder også Rum-kolonnen.


## Samlemuffe / sløjfe-Wago 0.59.10

PL-dåsens Wago-arbejdsgang har nu en tydelig, separat **Samlemuffe / sløjfe**-funktion til kabelledere, der skal samles i dåsen **uden forbindelse til lampeudtaget**. Brug **+ Samlemuffe / sløjfe**, højreklik på en terminal/funktion eller **Administrér Wago… → Opret samlemuffe / sløjfe**. En samlemuffe bruger den eksisterende `connects_to_outlet = false`-tilstand, så der oprettes ingen bro og ingen terminalplads på lampeudtaget forbruges.

Samlemuffen vises tydeligt som **SAMLEMUFFE · N/PE/L/P/...** med teksten **ingen udtag** i ledergrafikken. Valgte kabelledere kan tilføjes/fjernes og Wago-artikel kan ændres som før. Hvis samlingen senere skal føres videre til lampeudtaget, åbnes **Redigér samlemuffe** og brugeren aktiverer eksplicit broen til den relevante klemme. Intet elektrisk forbindes automatisk. Projekt-/Wago-formatet er uændret, så 0.59.9 kan bruges som direkte rollback-build.


## Wago-arbejdsgang 0.59.9

PL-dåsens Wago-håndtering er gjort funktionsbaseret og flyttet tættere på selve ledergrafikken. Højreklik på en terminal som **PE, N, L, P, COM eller ~** for at oprette/redigere en Wago for netop den funktion. Trækkes en leder til en terminal, der allerede har Wago, kan brugeren vælge **Direkte**, **Via eksisterende Wago** eller **Opret ny Wago**. Drop direkte på en eksisterende Wago forbinder til samlingen som før.

Den gamle lange Wago-dropdown er fjernet fra hovedvisningen og findes kun skjult som kompatibilitetskontrol. I stedet vises en kompakt status, fx `N 4/5 · PE 3/5`, samt **+ Wago for valgt funktion** og **Administrér Wago…**. Wago-blokkene i grafikken viser funktion, lederantal, eventuel bro, artikel og fysisk kapacitetsforbrug. Klik på en Wago uden valgt leder åbner redigering; med en valgt leder forbindes lederen til den Wago.

Ingen Wago oprettes eller omkobles automatisk. Ved terminalkapacitetsproblem får brugeren et eksplicit valg som **Opret Wago N og forbind**. Projektformat og `pl_box_splices` er uændret, så 0.59.8 kan bruges direkte som rollback-build.

## PL-layoutpatch 0.59.8

Lederfordelingen prioriterer nu kabelmærkning endnu tydeligere. Kabelkortenes tekst og lederudgang har separate zoner, og den lange montagekontrol er sammenklappet som standard. Patchen ændrer ikke projektformat eller Wago-logik og kan derfor rulles tilbage til 0.59.7 uden konvertering.


## Fuld kabelmærkning i PL-lederfordeling (0.59.7)

Kabelindføringskortene i PL-dåsens **Lederfordeling** bruger nu mere af den disponible bredde, og kabelmærkningen har førsteprioritet. Lange mærkninger brydes automatisk over flere kompakte linjer med responsiv fontstørrelse i stedet for at blive skåret af efter et fast antal tegn. Kategori, kabeltype og kabelben vises fortsat som sekundær information.


## Kabelmærkning fra lampeudtag (0.59.6)

Når et fysisk kabel går mellem to lampesteder og rumgeometrien ikke giver en fler-rums rute, foreslår kabelmærkningen nu den **ekstra mærkning** ud fra lampestedernes egne mærkninger, fx `UDTAG-KØKKEN → UDTAG-GANG`. Forslaget bruger kun symbolernes mærkningsfelt — aldrig gruppe/kreds — og anvendes fortsat kun efter en aktiv brugerhandling. Samme centrale forslag bruges i Egenskaber, grafisk kabelmærkning og Kabeltræk → Mærkning.

## Rum: kombineret væg/ortho-snap og farvenuancer (0.59.5)

Rumværktøjet kan nu holde et nyt eller redigeret rumsegment præcist vandret/lodret **samtidig med**, at endepunktet snapper til en rigtig CAD-væg. Når cursoren ligger tæt på det relevante væg/akse-kryds, bruges krydset; ellers beholdes almindeligt væg-snap eller fri/skrå geometri. Hold **Alt** for at slå ortho-hjælpen fra uden at miste væg-snap. EL-RUM er fortsat aldrig et snapmål for symboler eller kabler.

Hvert rum kan samtidig få sin egen diskrete farvenuance. Vælg farveprøven i **Rumdata / farve…**; den bruges til rumtekst, omrids og redigeringshåndtag. Nye rum roterer automatisk gennem en rolig palette, mens eksisterende projekters rumfarver bevares.

## Kabelpanel-stabilitet (0.59.4)

0.59.4 retter en regression fra kabelpanelets overgang til det fælles Inspector-panel. Valg, geometri-redigering, breakpoint og context-menu bruger nu samme panelarkitektur uden referencer til den gamle separate kabel-dock.


## Mere intuitiv rumredigering (0.59.3)

Rum kan nu redigeres direkte fra tegningen. Hvis rumomridset er synligt, dobbeltklikkes på konturen for at vise hjørnehåndtagene. Hvis omridset er skjult, dobbeltklikkes på rumteksten. Under både ny skitse og efterfølgende hjørneredigering hjælper programmet blødt med vandrette/lodrette linjer. Flyt uden for hjælpetolerancen eller hold **Alt** for fri/skrå geometri. Rigtige CAD-vægge har fortsat prioritet som snapmål, og rumlaget indgår aldrig i symbol-/kabelsnap.


## Opryddet kabel-egenskabspanel (0.59.2)

Kabelpanelet skelner nu tydeligt mellem **tegning af nye kabler** og **redigering af et valgt fysisk kabel**. Når et eksisterende kabel markeres, skjules indstillinger for snap, kabel-assistent og automatisk opstart af næste kabel. Panelet fokuserer i stedet på **Mærkning → Kabeldata → Rute → Artikel/BOM → Længde**, mens mindre brugte indstillinger ligger under **Avancerede kabeldata**.

Kabel-ID tildeles fortsat automatisk. Den tidligere tekst **Første kabel-ID** er erstattet af den avancerede mulighed **Start-ID**: den bruges kun, hvis næste tegnede kabelstreng bevidst skal starte ved et bestemt nummer. De efterfølgende fysiske kabelstykker nummereres videre automatisk. **Ekstra mærkning er aldrig længere en standard for nye kabler**; nye kabler starter tomme og mærkes kun, når brugeren aktivt gør det via valgt kabel, grafisk mærkning eller Kabeltræk-listen.

Panelet er samtidig gjort responsivt uden vandret scrolling. Lange formularrækker kan wrappe, og forslag til mærkning vises som kompakte visuelle knapper i et grid frem for én bred række.

## Direkte kabelmærkning ved valg (0.59.1)

Når et eksisterende kabel markeres på plantegningen, vises nu en tydelig **Mærkning**-sektion direkte i kabel-egenskaberne. Her kan **Ekstra mærkning** skrives eller vælges fra rum-/fra→til-forslag og gemmes med **Anvend mærkning**. Forslag udfylder kun tekstfeltet; intet gemmes automatisk. Den direkte mærkningshandling kan kun ændre kabellets `label` og ændrer aldrig kabel-ID eller gruppe/kreds.

Den grafiske **Mærk kabler**-tilstand og fanen **Kabeltræk / ruteforløb → Mærkning** findes fortsat som supplerende værktøjer til henholdsvis arbejde direkte på tegningen og systematisk gennemgang af mange kabler. Fra 0.59.2 starter nye kabler altid uden Ekstra mærkning; mærkning sker kun ved en aktiv brugerhandling.

## Grafisk kabelmærkning (0.59.0)

**Mærk kabler** er en opt-in arbejdsgang direkte på plantegningen. Mens tilstanden er aktiv, får hvert fysisk kabel en kompakt status-chip: `+` betyder, at Ekstra mærkning er tom, mens et mærket kabel viser den godkendte tekst. Klik på et kabel for at åbne et ikke-modalt mærkningskort med kabel-ID, gruppe/kreds og fra→til som låst kontekst. Rum- og fra/til-forslag er kun genveje til at udfylde tekstfeltet; **intet ændres før brugeren klikker Anvend**. `Spring over` går videre uden at skrive data, og valget om at gå til næste umærkede kabel prioriterer samme gruppe først.

Arbejdsgangen skriver udelukkende til kabellets eksisterende **Ekstra mærkning** (`label`). Kabel-ID, gruppe/kreds, kabeltype, rute, artikel og BOM ændres aldrig. Højreklik på et kabel giver **Mærk kabel…**, og **Kabeltræk / ruteforløb → Mærkning** viser mærkningsstatus, forslag og direkte navigation til hvert fysisk kabel. Den tidligere batchfunktion **Mærk kabler efter rum…** findes fortsat som et eksplicit preview-værktøj.


## Rumlag, separat synlighed og kabelmærkning (0.58.x)

Rum er egentlige projektområder på laget **EL-RUM**. Brug **Rum** i hovedværktøjslinjen eller **Værktøjer → Rum → Rum** og klik langs rummets vægge; Enter, dobbeltklik eller højreklik afslutter polygonen, mens Backspace fjerner sidste punkt. Rumskitsen snapper til CAD-vægge, men rumgeometri kan aldrig blive snapmål for almindelige symboler eller kabler.

**Vis rumtekster** og **Vis rumafgrænsninger** er uafhængige. Standardvisningen er rumtekst **til** og afgrænsning **fra**. **Redigér rum** viser polygonerne midlertidigt og giver trækbare hjørnepunkter; når redigering afsluttes, vender visningen tilbage til brugerens normale omridsvalg. Rumteksten har sin egen position og kan trækkes væk fra symboler uden at ændre polygonen. EL-RUM-laget kan fortsat skjule både tekst og geometri samlet.

Eksisterende rum kan efter oprettelse formes om direkte: **højreklik på rumteksten → Redigér afgrænsning** viser polygonen og dens trækbare hjørnepunkter. Alternativt bruges **Værktøjer → Rum → Rumoversigt → Redigér afgrænsning**. Hjørnetræk understøtter Undo/Redo og ændrer kun rummets geometri.
Symbolmærkninger er fra 0.58.3 igen fuldt brugerdefinerede — rumfunktionen navngiver ikke symboler. Rumgeometrien kan i stedet bruges til **Mærk kabler efter rum…**. Funktionen følger hvert fysisk kabel gennem polygonerne og foreslår kun feltet **Ekstra mærkning**, fx `Køkken` eller `Køkken → Gang → Stue`. Formatet kan være rumnavn, kort rummærkning eller begge dele. Eksisterende kabelmærkninger bevares som standard. **Kabel-ID og gruppe/kreds ændres aldrig.**

**Rumoversigt…** viser både symbol- og kabelantal pr. rum og kan zoome, redigere, slette eller åbne kabelmærknings-preview for et valgt rum. Symbol- og PL-hover kan fortsat vise rumkontekst, og rumgeometrien bruges fortsat til at holde visuel symboltekst på rummets side af væggen; dette ændrer ikke selve symbolmærkningen.


## Artikeltilknytning fra Artikeldatabasen (0.57.4)

Når et symbol og en fysisk BOM-del er valgt, viser **Artikeldatabasen** nu tydeligt hvor en artikel vil blive tilknyttet. Dobbeltklik på en artikel eller brug **Tilknyt valgt artikel** for at tilknytte den direkte. **Find i Artikeldatabase…** fra Tilknytning-fanen skifter direkte til den søgbare database. Den tidligere combo findes kun som sekundært hurtigvalg, mens artikelredigering sker eksplicit via **Redigér artikel…**.

PL-dåsens hoverkort viser samtidig både gruppe/kreds og mærkning i overskriften, så flere lampesteder på samme gruppe kan skelnes med det samme.

## PL-lederfordeling i fokus (0.57.1)

PL-dåsekonfiguratorens **Lederfordeling** er gjort markant mere arbejdsorienteret. Tændleder-overblikket er nu en kompakt, sammenklappelig hjælpelinje som standard, mens selve lederdiagrammet får mere vertikal plads. Lampeudtagets grafiske terminalpanel viser kun en kort klemmeforklaring; den fulde produkttekst er flyttet til tooltip. En reserveret statuszone nederst forhindrer desuden hjælpetekst/valgstatus i at ligge oven på kabelindføringerne. Den detaljerede lederfarve-note vises kun sammen med den avancerede tabel.

Der er ingen ændringer i PL-ledningsdata, Wago-modellen, kabelmodellen eller BOM.

## Visual Interaction / “bling” (0.57.0)

0.57.0 udbygger Visual Workspace med animationer og navigation, der samtidig giver funktionel feedback. Kabler viser diskret flow ved hover/selection og kan spores gruppevis fra tavlen; symboler får selection-pulse, snap får et kort “pop”, og **Zoom til valg** bevæger viewporten glat til det aktuelle objekt. Kabel-hoverbadges viser ID, kabeltype, beregnet længde og gruppe/kreds.

**Navigator / mini-kort** er fra 0.57.2 skjult som standard og viser kun CAD-linjer, fysiske kabler, små symbolmarkører og den aktuelle viewport — ingen mærkningstekst. De eksisterende symbol- og PL-hoverkort vises igen også på valgte objekter; de undertrykkes kun under drag, aktive tegneværktøjer, mouse-grab og åbne menuer/popups.

**0.57.3 hover/arbejdsflade:** Symbol- og PL-hoverkortene er igen aktive, også mens et symbolplaceringsværktøj er valgt. Kabel-hoverkort vises efter en kort forsinkelse ved den aktuelle museposition og følger cursoren langs kablet. Den tidligere flydende kabelkategori-chipbjælke er fjernet fra selve tegnefladen; kategorisynlighed styres fortsat via **Vis → Kabelkategorier**.

PL-dåsekonfiguratoren har desuden fået en valgfri eksploderet visning og en kort animation, når brugeren manuelt forbinder en leder. Der er fortsat **ingen automatisk/pre-forbundet lederfordeling**. Alle 0.57.0-funktionerne er præsentationslag og ændrer ikke projektets elektriske/BOM-model.

## Nordtronic Zigbee lampeudtag (0.56.2)

0.56.2 tilføjer **Nordtronic lampeudtag med Zigbee lysdæmper, varenr. 98425033 / EAN 5704629006065** til den indbyggede artikeldatabase og som fysisk udtagstype i PL-dåsekonfiguratoren. Profilen viser særskilte terminaler for **P, COM, PE, N, dæmpet udgang (~) og L**. P bruges som fysisk trykindgang for lampestedets tilhørsforhold; COM og den dæmpede udgang er selvstændige manuelle lederfunktioner.

PL-konfiguratoren opretter fortsat **ingen forbindelser automatisk**. Lampeudtag er samtidig gjort til en valgfri eksplicit BOM-del, så artiklen kan tilknyttes det konkrete lampested uden automatisk artikelvalg eller nye manglende-BOM-advarsler i eksisterende projekter.


## Visual Workspace – flow, chips og animationer (0.56.1)

0.56.1 fortsætter den visuelle arbejdsflade uden at ændre installationsmodellen. En ny flydende **kabelkategori-linje** ligger direkte på tegnefladen med klikbare chips, kategoriens faktiske farve/kontur og en tydelig skjult tilstand. Chipsene styrer de samme eksisterende kategori-lag som Vis-menuen, så der oprettes ingen parallel synlighedsmodel.

**Kabeltræk / ruteforløb** har fået en ny **Flow**-fane som standard. Gruppe/kreds vises som et visuelt netværk med installationspunkter som noder, bløde forbindelser og kabel-ID, type og længde på hvert fysisk stræk. Forgreninger bliver synlige som rigtige grene, og klik på gruppe eller node fremhæver de tilsvarende fysiske kabler på plantegningen. Træ- og listevisningen er fortsat tilgængelige.

PL-dåsens ledergrafik har fået en mere fysisk montageside med dybde, montagepunkter, tydeligt separat lampeudtag, kategoriaccent på kabelkort og en kompakt `x/y FORDELT`-status. Den neutrale start er uændret: **ingen ledere forbindes automatisk**.

Hover og selection på symboler/kabler animeres diskret over ca. **120–150 ms**, og inspector-summary fader kort ind ved et nyt valg. Animationerne ændrer kun præsentation og skriver ingen data til projektet.


## Visual Workspace (0.56.0)

0.56.0 gør arbejdsfladen mere visuel uden at ændre installations- eller projektdatastrukturen. En ny flydende **arbejdsgangslinje** øverst på tegnefladen viser tydeligt, når kabeltegning, symbolplacering, tekst, spotmønster, kalibrering eller lystilhørsforhold er aktivt. Ved kabeltegning viser den bl.a. gruppe/kreds, kabeltype, kabel-ID og antal punkter/tilslutninger samt direkte handlinger til **Fortryd punkt**, **Afslut kabel** og **Esc**.

Valg af et fysisk kabel har fået et tydeligt visuelt hierarki: det valgte kabel får en diskret halo og markerede endepunkter, kabler i samme gruppe/kreds bevares som sekundær kontekst, og øvrige kabler/symboler tones ned. Højre **Egenskaber**-panel har fået et kompakt summary-kort med objekt-ID, fra→til, gruppe/kreds, kabeltype og længde (når skala kendes), før de detaljerede felter.

Ny **gruppefokus** kan aktiveres fra Vis-menuen, kontekstværktøjslinjen eller `Ctrl+Shift+F`. Fokus bevarer den valgte gruppe/kreds tydelig og dæmper øvrige symboler, mærkninger og kabler. Tilstanden er kun præsentation, gemmes ikke i projektet og nulstilles, når et andet projekt eller en anden CAD-tegning åbnes.


## Tydelig synlighed for kabelkategorier (0.55.3)

**Vis → Kabelkategorier** viser nu hver kategori med en eksplicit `VIST` eller `SKJULT`-tilstand. Det gør menuen entydig på Windows/themes, hvor Qt's normale checkmark kan være svært at se ved siden af kategoriens farveikon. Selve undermenuen viser også hvor mange kategorier der er synlige, fx `Kabelkategorier (8/11 vist)`.


## Kabeltræk / ruteforløb (0.55.2)

Under **Værktøjer → Kabeltræk / ruteforløb…** kan installationens fysiske kabelsegmenter ses som et gruppevist netværk uden at oprette nye projektdata. **Træ**-fanen viser forgreninger fra gruppetavle/fordelingstavle og ned gennem installationspunkterne. **Liste**-fanen viser de samme net som hurtigt læsbare ruter, fx `Tavle → PL01 → PL02 → PL03`, sammen med kabel-ID'er, kabeltyper og beregnet længde, hvis projektets tegneenhed/skala er kendt.

Klik på en gruppe fremhæver alle dens fysiske kabler på plantegningen; klik på et enkelt punkt/rute fremhæver kun den relevante vej fra tavlen/roden. Dialogen er modeless og kan blive stående under tegning/redigering. Søgning kan matche gruppe/kreds, installationspunkt, kabel-ID og kabeltype. Forgreninger bliver til flere læsbare ruter i listevisningen, mens trævisningen bevarer den faktiske struktur. Frie ender, adskilte delnet og sløjfer/ringe vises også.

Kabeltræk-overblikket er **kun afledt af `CablePlacement` + symboltilslutninger**. BOM, PL-dåser, tegning og kabeltræk bruger derfor fortsat samme fysiske kabelobjekter som eneste sandhedskilde.


## Fysiske kabler og logiske grupper/kredse (0.55.0)

0.55.0 omlægger kabelmodellen, så **ét `CablePlacement` nu er ét fysisk kabel mellem højst to installationspunkter**. Brugeren kan stadig tegne en hel streng i én arbejdsgang, fx `Tavle → PL01 → PL02 → PL03`, men den gemmes automatisk som tre selvstændige kabler. De deler `circuit_id` (gruppe/kreds) og et internt `route_chain_uid`, mens kabeltype, artikel/BOM-binding, rute og længde ligger på hvert fysisk kabel.

Det betyder, at et kabel mellem `PL02 → PL03` kan ændres fra fx `5G1,5` til `3G1,5` uden at ændre de øvrige kabler i gruppen. Gruppe/kreds kan ændres fra et valgt kabel og opdateres samlet på de kabelstykker, der blev tegnet som samme streng. Kabel-ID'er tildeles individuelt og fortløbende. BOM arbejder fortsat med eksplicit artikelbinding pr. kabel-UID og summerer derefter meter/ruller på tværs af de konkrete kabler. Kabellængderapporten viser nu også **Gruppe/kreds** og **Fra → til**.

PL-dåsen ser ikke længere et gennemgående kabel med “Side A/Side B” som den normale nye model. Ved et lampested mødes i stedet to eller flere selvstændige kabelender, hver med eget kabel-ID, type, artikel og lederprofil. Det gør lederfordeling og montagevisning mere direkte.

### Automatisk migration fra 0.54.x og ældre

Gamle flerpunkt-kabler splittes ved projektåbning i fysiske kabler. Gamle `spec_section_overrides` og `route_section_modes` materialiseres som almindelig kabeltype/ruteføring på de nye segmenter, og PL-indføringer, lederfordeling samt Wago-medlemmer remappes til de nye kabel-UID'er. En ensartet gammel kabelartikel kopieres til alle de fysiske segmenter; ved et gammelt kabel med blandede kabeltyper gætter programmet bevidst ikke på artikelbindingen. Migrerede projekter markeres som ændrede og gemmes i det aktuelle 0.55.x-format ved næste Gem. Eksisterende kabel-ID'er reserveres, så nye segment-ID'er ikke kolliderer med fx et allerede eksisterende `K02`.

Se `docs/history/PHYSICAL_CABLE_MODEL_0.55.0.md` for schema- og migrationsdetaljer.


## Manuel PL-lederfordeling (0.55.1)

Nye PL-dåser starter med en helt tom lederplan. Programmet pre-forbinder ikke længere PE, N eller andre ledere; hver fysisk leder skal aktivt forbindes af brugeren i PL-dåsekonfiguratoren. Allerede gemte forbindelser i eksisterende projekter bevares.


## Vedligeholdelse, kodeopdeling og startup (0.54.3)

0.54.3 er et rent vedligeholdelses-/arkitekturpas uden ændring af projektformatet. Den store `qt_app.py` er reduceret fra ca. 10.800 til ca. 6.000 linjer ved at flytte artikel-/BOM-dialogerne til `qt_articles.py`, PL-dåse/lederfordelingsgrafikken til `qt_pl_box.py` og de fælles Qt-kontroller til `qt_widgets.py`. Hovedvinduet står dermed primært for orkestrering i stedet for at eje alle feature-dialoger.

De tunge artikel/BOM- og PL-moduler importeres nu først, når den relevante funktion åbnes. Det reducerer unødvendig parsing/import ved normal programstart og projektåbning. Samtidig er en række artikel-, netværks- og widget-imports fjernet fra `qt_app.py`, fordi de ikke længere bruges dér.

Regressionspakken er opdateret til de nye modulgrænser, og nye arkitekturtests sikrer bl.a., at `qt_app.py` holdes under 6.200 linjer, at artikel/PL-modulerne forbliver lazy-loadede, og at de nye featuremoduler ikke importerer `qt_app` tilbage og dermed skaber cirkulære afhængigheder. Se `docs/history/MAINTENANCE_0.54.3.md`.


## Kabeltype pr. afsnit (0.54.2 · historisk, migreres i 0.55.0)

Et eksisterende kabel kan nu skifte kabeltype **kun mellem to fysiske nabotilslutninger**. Markér kablet og brug **Egenskaber → Valgt kabel → Indstillinger pr. afsnit**: vælg fx `G11 · UDTAG-SOVE → G11 · UDTAG-GANG`, sæt **Kabeltype = 5G1,5** og tryk **Anvend kabeltype**. Resten af kabelruten beholder sin globale/default type. Samme valg findes ved højreklik direkte på kabelafsnittet.

Når et kabel har blandede typer, vises en lille kabeltype-label på hvert fysisk afsnit. PL-dåser bruger den effektive type pr. kabelben, så en overgang fra 3G til 5G giver korrekt 3-/5-lederprofil på hver sin side af lampestedet. PDF/print/DXF og kabellængderapporten følger også afsnitsværdierne.

Afsnitsvalget gemmes i det valgfrie `CablePlacement.spec_section_overrides` med stabile symbol-UID/port-par. Gamle projekter åbner uændret. Se `docs/history/CABLE_SECTION_SPEC_0.54.2.md`.


## Zoom og tydelig projektindlæsning (0.54.1)

0.54.1 retter en regression fra den nye startside/centrale workspace i 0.54.0: plantegningen blev tilpasset, mens selve QGraphicsView stadig kunne være skjult bag startsiden. På Windows kunne det efterlade en forkert/stale view-transform, så **zoom ind med musehjulet virkede som om det var blokeret**. Scenen vises nu først, hvorefter *Tilpas visning* køres med den rigtige viewport-størrelse. Selve zoomkoden er samtidig samlet i én robust funktion, og **Ctrl++ / Ctrl+=** samt **Ctrl+-** giver en tastaturgenvej til zoom ind/ud.

Når et projekt åbnes, vises nu et tydeligt, centreret **Åbner projekt…**-overlay over hele programmet med projektnavn, aktuel fase og en indeterminate progressindikator. Faser som *Indlæser projektfil*, *Indlæser CAD-data*, *Forbereder lag og geometri* og *Opbygger plantegningen* vises direkte i overlayet. Det gamle statusfelt nederst opdateres fortsat, men er ikke længere den eneste feedback. Overlayet blokerer samtidig utilsigtet redigering, mens projektet indlæses.

Åbningsflowet ligger i det separate `qt_project_open.py`, så feedbacklogikken ikke gør `qt_app.py` større. Der er ingen projektformatændring. Se `docs/history/ZOOM_LOADING_0.54.1.md`.

## GUI Workflow – søgning, startside og progressive værktøjer (0.54.0)

0.54.0 fortsætter GUI-moderniseringen fra 0.53.0 med de resterende punkter. **Ctrl+F** åbner global søgning i gruppe/kreds, mærkning, kabel-ID, ekstra kabelmærkning, kabeltype og fritekst. **Ctrl+Shift+P** åbner en kommando-palette, som både kan finde objekter og starte almindelige funktioner. Et objektresultat markeres og centreres direkte på tegningen.

Programmet åbner nu på en egentlig **startside** med Åbn projekt, Nyt fra DWG/DXF og op til seks seneste projekter. Startsiden kan altid åbnes igen via **Vis → Startside**, uden at det aktive projekt lukkes.

Inspector og større arbejdsflader bruger mere **progressive disclosure**: de vigtigste felter står fremme, mens sjældnere indstillinger foldes ud efter behov. Symbolernes størrelse/rotation/farve/linjetykkelse ligger under *Udseende og placering*, og kabelinspectorens parallelvisning samt længde/rapport er foldbare. Artikelvælger, Artikler/BOM, PL-dåse og Kabelkategorier er koblet på det fælles dialogfundament.

Succeshandlinger som Gem, BOM-opdatering, kabeltilknytning og lokal rutekonvertering kan nu give små **ikke-modale toast-beskeder**. Fælles tabeller har ensartet kolonneadfærd: kolonner kan flyttes, dobbelklik på en overskrift auto-tilpasser bredden, og højreklik på overskriften giver *Tilpas kolonner* / *Nulstil bredder*. Hover-BOM caches pr. symbol, så gentagne hover-opslag ikke genberegner samme artikeldata.

Der er ingen projektformatændring. Se `docs/history/GUI_WORKFLOW_0.54.0.md`.


## GUI Foundation – roligere arbejdsflade og kontekstuel redigering (0.53.0)

0.53.0 samler de første fire trin i den planlagte GUI-modernisering uden at ændre projektformatet. Brugerfladen har nu et fælles UI-fundament i `qt_ui.py` med standardmål for marginer, afstande, panelbredder og fælles panel-/formularopsætning. Light/dark-varianter bruger fortsat det centrale themesystem i `qt_theme.py`, som også har fået fælles styling til inspector-header og kontekstværktøjslinje.

Hovedvinduet er gjort roligere, så plantegningen får mere plads. Den faste værktøjslinje indeholder kun de mest almindelige globale handlinger, mens en separat **Kontekst**-linje skifter indhold efter det valgte objekt. Ved et kabel vises bl.a. kategori og global ruteføring; ved et symbol vises relevante symbolhandlinger, og uden markering vises generelle tegnehandlinger.

Højre side bruger nu én samlet **Egenskaber**-inspector i stedet for separate permanente paneler til symboler og kabelværktøj. Inspectorens indhold skifter automatisk mellem symbol-/objektegenskaber og kabeldata. Den avancerede PL-konfigurator og andre større arbejdsdialoger forbliver selvstændige. Aktiv kabeltegning er samtidig adskilt fra blot at have kabelsiden synlig, så valg af et kabel ikke utilsigtet starter tegnetilstand.

Symboler og lag er fortsat docks i venstre side og kan tabbes/skjules. Panelplacering, dockstørrelser og vinduesgeometri gemmes maskinlokalt og gendannes ved næste start. **Vis → Nulstil panel-layout** gendanner standardarbejdspladsen. Layoutdata eksporteres ikke med projektet eller portable kernedata. Se `docs/history/GUI_FOUNDATION_0.53.0.md`.


## Responsiv PL-lederfordeling (0.52.7)

PL-dåsekonfiguratorens grafiske **Lederfordeling** tilpasser sig nu den faktiske vindueshøjde. Efter skærmtilpasningen i 0.52.4 kunne diagramwidgetten blive lavere end 620 px, men den interne tegnegeometri fortsatte med at bruge 620 px som minimum. Det betød, at især bundindføring 4-6 og den nederste del af lampeudtaget kunne blive tegnet uden for den synlige flade.

I 0.52.7 skaleres luft, kabelkort og PL-dåsens højde kontrolleret, når vinduet er lavt. Alle seks indføringer og hele klemrækken holdes inden for selve diagrammet, samtidig med at **OK / Annuller / Anvend** fortsat er faste nederst i dialogen. På større skærme bruges den ekstra højde som før. Ingen projektformatændring.



## Tydeligere identifikation i Ruteføring pr. afsnit (0.52.6)

Kabelværktøjets **Ruteføring pr. afsnit** viser nu både **gruppe/kreds og mærkning** for hver fysisk tilslutning, når begge oplysninger findes. Et afsnit kan derfor fx vises som `G11 · UDTAG-SOVE → G11 · UDTAG-GANG-VÆRELSER` i stedet for blot `G11 → G11`. Det samme navn bruges i kabellets højrekliksmenu og statusbeskeder, så det er tydeligt præcis mellem hvilke lampesteder den lokale 90°/fri-diagonal-konvertering udføres. Ingen projektformatændring.

## Projektåbning / kabel-kontekstmenu rettet (0.52.5)

Version 0.52.5 retter en regression fra 0.52.3, hvor kabelklassens Qt-signal `contextRequested` ved en fejl var blevet deklareret på symbolsignalerne i stedet for `CableSignals`. Resultatet var, at projekter med kabler kunne fejle under opbygning af tegningen med fejlen `CableSignals object has no attribute contextRequested`. Signalet ligger nu på den korrekte klasse, og symbolernes eget to-argumenters kontekstsignal er samtidig gendannet. Projektformatet er uændret.


## PL-identifikation og skærmtilpasning (0.52.4)

PL-dåsekonfiguratoren viser nu **gruppe/kreds og mærkning sammen** i stedet for at gruppe/kreds skjuler mærkningen. Det gælder både dialogens identifikation og **Tændleder-overblikket**. Når tændlederanalysen refererer til andre lampesteder langs samme kabel, bruges samme entydige format, fx `G11 · T.V. BAD2`.

**PL-dåserapporten** har tilsvarende fået eksplicitte felter for `Gruppe/kreds` og `Mærkning` i hvert montagearks overskrift. Det gør udskriften lettere at koble til plantegningen og den fysiske dåse under montage.

Lederfordelingsfanen er samtidig gjort robust på mindre/lavere skærme. Selve fanens indhold kan nu rulle lodret, mens dialogens **OK / Annuller / Anvend**-knapper altid bliver stående synligt nederst. Den grafiske lederfordeling har fået et lavere minimumshøjdekrav, og dialogens startstørrelse tilpasses Windows' reelle arbejdsområde inklusive proceslinjen. Der er ingen ændring af projektformatet. Se `docs/history/PL_IDENTIFICATION_LAYOUT_0.52.4.md`.


## Blandet ruteføring på samme kabel (0.52.3)

Et eksisterende kabel kan nu have **forskellig ruteføring på forskellige fysiske afsnit**. Det løser fx et kabel, der går gennem flere lampesteder, hvor kun strækket mellem to bestemte lampesteder skal ændres fra **Ortogonal (90°)** til **Fri / diagonal**, mens resten af kabelruten forbliver 90°.

Når et kabel med mindst to fysiske tilslutningssteder vælges, vises **Ruteføring pr. afsnit** under *Valgt kabel*. Afsnittet vælges med navnene på de to nabotilslutninger og kan derefter konverteres med **Anvend på afsnit**. Som hurtig genvej kan man højreklikke direkte på kabelstrækket mellem tilslutningerne og vælge *Fri / diagonal for dette afsnit* eller *Ortogonal (90°) for dette afsnit*.

Den eksisterende globale **Ruteføring** beholder sin betydning som standard for hele kablet. Ændres den på et valgt eksisterende kabel, konverteres hele kabelruten og lokale overrides nulstilles. Kabelværktøjet viser **blandet** ruteføring, når mindst ét afsnit afviger fra standarden.

Afsnitsvalget gemmes stabilt via symbol-UID/port-par i det nye valgfrie felt `route_section_modes`, ikke via skrøbelige polyline-indeks. Eksisterende symboltilslutninger remappes ved konvertering, Undo/Redo understøttes, og hvis et nyt lampested senere indsættes midt i et afsnit med override, arver de to nye delafsnit samme lokale ruteføring. Se `docs/history/CABLE_SECTION_ROUTING_0.52.3.md`.


## Tændleder-overblik langs hele kablet (0.52.2)

PL-dåsekonfiguratorens **Lederfordeling** har nu et kompakt **Tændleder-overblik**, som samler lederanvendelsen på tværs af alle lampesteder langs det samme fysiske kabel. Det er især lavet til 7G-kabler, der passerer mange PL-dåser, så brugeren ikke skal huske manuelt om sort, grå, rød eller hvid allerede er taget i brug som tændleder tidligere på kabelstrækningen.

Hver lederfarve vises som et lille visuelt statuskort: **Ledig tændleder**, allerede brugt som fx **Tænding a**, anden kendt funktion eller konflikt. Hvis samme farve er registreret som forskellige tændinger forskellige steder på samme kabel, markeres det tydeligt som en konflikt. Når flere kabler mødes i samme PL-dåse, kan det relevante kabel vælges direkte i overblikket; vælger man en leder i grafikken, følger overblikket automatisk det pågældende kabel.

Gul/grøn, blå og brun er bevidst ikke med i automatisk anbefaling af næste tændleder. Gul/grøn vises som **PE / beskyttelsesleder**, blå som **typisk N** og brun som **typisk fast L**. Programmet foreslår derfor først ledige farver blandt sort, grå, rød og hvid. Hvis brugeren forsøger at genbruge en farve, som allerede er registreret som en anden tænding på samme kabel, vises en bekræftelsesadvarsel med de berørte lampesteder. Tilsvarende gives en bevidsthedsadvarsel ved valg af en typisk forsyningsleder som tændleder. Funktionen er planlægningshjælp; kabelartikel/datablad og gældende installationsregler har altid forrang.

Der tilføjes ingen nye projektfelter. Den tværgående analyse beregnes ud fra de eksisterende `pl_box_wiring`-data og kabeltilslutninger. GUI-hjælpen ligger i det separate modul `qt_pl_usage.py`, så oprydningsretningen fra 0.52.0 fortsættes. Se `docs/history/PL_SWITCH_CONDUCTOR_USAGE_0.52.2.md`.


## Tilknyt eksisterende lampested til eksisterende kabel (0.52.1)

Et allerede placeret **lampested** kan nu kobles fysisk på en kabelstrækning, der allerede er tegnet. Vælg lampestedet og brug **Egenskaber → Kabler ved symbol → Tilknyt eksisterende kabel…**; klik derefter direkte på den ønskede kabelstrækning. Samme handling findes ved højreklik på lampestedet. **Esc** annullerer værktøjet.

Hvis lampestedet ligger ved en fri kabelende, behandles det intuitivt som kabellets start/slut, så PL-dåsen får ét kabelben. Hvis lampestedet ligger midt på kabelruten, indsættes et fysisk gennemgående tilslutningspunkt, så PL-dåsen får de korrekte to kabelben. Ortogonale kabler får lokale 90°-knæk, mens fri/diagonal routing føres direkte gennem lampestedets tilslutningspunkt. Eksisterende kabelender og andre symboltilslutninger bevares og deres punktindeks remappes automatisk. Hele ændringen kan fortrydes med Undo.

Hvis lampestedet ligger tydeligt væk fra den valgte kabelrute, spørger programmet før geometrien trækkes hen til lampestedet. Efter tilknytning viser PL-dåsekonfiguratoren automatisk det nye kabelben som **ikke placeret**, indtil installatøren vælger fysisk indføring 1-6. Der tilføjes ingen nye obligatoriske projektfelter.

Interaktionskoden er lagt i det nye modul `qt_cable_attach.py`, så oprydningsretningen fra 0.52.0 fortsættes i stedet for at gøre `qt_app.py` større. Se `docs/history/CABLE_ATTACH_0.52.1.md`.


## Vedligeholdelse, GUI-polish og korrekt kabelrutekonvertering (0.52.0)

0.52.0 er et målrettet vedligeholdelses-/arkitekturpas før næste større funktionsrunde. `qt_app.py` er begyndt opdelt i mindre ansvar: **tema/light-dark-system** ligger nu i `qt_theme.py`, og de grafiske **hover-kort** ligger i `qt_hover.py`. En gammel dobbeltdefinition i `MainWindow` er fjernet, og nye arkitekturtests beskytter mod samme type sammenfald fremover. Der er bevidst ikke lavet en stor risikabel omskrivning af PL/BOM i samme omgang.

Performance er forbedret på to konkrete steder. Zoom-afhængige rebuilds af kabelbaner/annotationer samles nu i et kort **32 ms** refresh-vindue, så hurtig wheel/trackpad-zoom ikke gentager de tunge beregninger for hvert signal. Den globale artikeldatabase caches samtidig efter filens sti/timestamp/størrelse, så hover/BOM/artikelvalg ikke behøver genlæse og normalisere hele kataloget ved gentagne opslag.

Fejlen i **Kabelværktøjet** er også rettet: hvis et eksisterende kabel ændres fra **Ortogonal (90°)** til **Fri / diagonal**, ændres nu både routing-flaget **og selve kabelgeometrien** ved *Anvend ændringer*. Automatiske 90°-hjørner konverteres til direkte segmenter, mens fysiske symboltilslutninger/endepunkter bevares og remappes til de nye rutepunkter. Skift den anden vej indsætter 90°-hjørner mellem de eksisterende waypoints. Hele ændringen er undo/redo-kompatibel. Kabelværktøjets hjælpetekst forklarer nu også dette direkte, når et eksisterende kabel er valgt.

Der er **ingen nye obligatoriske projektfelter** i 0.52.0. Se `docs/history/MAINTENANCE_0.52.0.md` og `docs/history/GUI_AUDIT_0.52.0.md`.


## Flere manuelle Wago-samlinger i PL-dåsen (0.51.1)

Fejlen hvor **Ny Wago…** blev deaktiveret efter den første/efter én Wago pr. funktion er rettet. Installatøren kan nu oprette **vilkårligt mange fysiske Wago-samlinger**, også flere på samme elektriske funktion som N, PE, L eller samme tænding. Hver Wago har sit eget artikelvalg, medlemsliste, bro/sløjfe-tilstand og grafiske placering i PL-dåsen.

Wago-medlemskab er nu eksplicit: kun de afkrydsede ledere hører til den konkrete Wago. Direkte ledere og flere Wago'er kan derfor eksistere side om side på samme funktion. Hver Wago med bro til lampeudtaget optager én fysisk terminalplads; rene Wago-sløjfer optager ingen terminalplads. Montagekontrollen tæller alle broer og viser stadig overfyldte terminaler som fejl i stedet for at blokere manuel montageplanlægning.

**Dark mode-funktionerne fra 0.51.0 er med uændret i 0.51.1**: Lys/Mørk/Følg Windows, separat mørk tegneflade, mørktilpasset PL-konfigurator samt uændret lyst PDF/print-output. Se `docs/history/PL_WAGO_MULTIPLE_0.51.1.md` og `docs/history/DARK_MODE_0.51.0.md`.


## Gennemtænkt mørkt udseende (0.51.0)

Programmet har nu et samlet udseendesystem under **Vis → Udseende** med **Lys**, **Mørk** og **Følg Windows**. Temaet kan skiftes uden genstart, og **Ctrl+Alt+D** skifter hurtigt mellem lys og mørk. I mørk tilstand kan **Mørk tegneflade** slås til eller fra separat, så brugerfladen kan være mørk, mens selve plantegningen fortsat vises på hvid baggrund.

Mørk tilstand er gennemført på tværs af hovedvindue, menuer, værktøjslinjer, docks, faner, formularfelter, tabeller, lister, scrollbars, statuslinje, dialoger, kabelassistent og hover-kort. PL-dåsekonfiguratorens **Kabelindføringer** og **Lederfordeling** har særskilt mørk grafik, så lederfarver, terminaltyper, Wago-samlinger og kabelkategoriers farver stadig kan aflæses som tekniske informationer og ikke blot bliver omfarvet dekorativt.

På den mørke CAD-tegneflade bruges kun en **skærmkontrast** til meget mørke DWG-linjer, symboler, kabler, tekst, snapmarkører og hjælpelinjer. Projektets gemte farver ændres ikke. Det betyder eksempelvis, at et sort kabel stadig er sort i projektdata og på teknisk output, selv om det vises lidt lysere på en mørk skærmbaggrund for at være synligt.

**PDF, print, PL-dåserapporter og øvrigt papiroutput påvirkes ikke af dark mode.** Print-previewets område omkring papiret bliver mørkt, men selve A4/A3-siden forbliver hvid og bruger projektets originale tekniske farver. Dermed kan dark mode bruges som arbejdsindstilling uden risiko for at ændre afleveringsmaterialet.

Udseendet er en **maskinlokal brugerindstilling** og gemmes ikke i projektet eller i portable kernedata. **Følg Windows** anvender Qt/Windows' systemtema og kan følge et temas skift løbende, når platformen leverer signalet. Eksisterende installationer starter fortsat i lyst tema, indtil brugeren selv vælger andet. Se `docs/history/DARK_MODE_0.51.0.md` for de tekniske principper.

## Kabelkategori i Lederfordeling (0.50.22)

Kabelkortene i **PL-dåsekonfigurator → Lederfordeling** viser nu kabelkategorien direkte under kabel-ID'et. Kategorien vises med både navn og en kort farve-/konturprøve, der følger projektets centrale kabelkategoriindstillinger. Kabeltype og kabelben står fortsat nederst på kortet.

Det gør især **Tændkabel** og **Mellemkabel** synlige i den grafiske lederkonfigurator uden at blande kategorien sammen med selve lederfunktionen. Egne brugerdefinerede kategorier vises på samme måde.

## Kabelkategorier i PL-dåsekonfiguratoren (0.50.21)

Fanen **Kabelindføringer** i PL-dåsekonfiguratoren viser nu den samme kabelkategori som på plantegningen. Hvert kabelben viser kategorinavn sammen med kabel-ID/type, og den valgte indføring har et separat **Kategori**-felt med kategoriens definition som tooltip.

Selve PL-grafikken bruger kategoriens **farve og kontur** som en diskret markering på kabelkappen og viser kategorinavnet direkte i indføringskortet. Over kabelben-listen vises desuden en kompakt oversigt over de kategorier, som faktisk forekommer i den aktuelle PL-dåse, eksempelvis **Tændkabel** eller **Mellemkabel**.

Kategorierne redigeres fortsat centralt via kabelkategori-menuen; PL-konfiguratoren er en visning af den eksisterende kategori og opretter ikke en separat PL-specifik kategori. Egne brugerdefinerede kategorier vises derfor også automatisk.

## Definitioner på kabelkategorier (0.50.20)

Alle kabelkategorier har nu en kort **definition**, som vises direkte i Kabelværktøjet, som tooltip i kategori-listen og i **Vis → Kabelkategorier**. Definitionen kan også redigeres sammen med kategoriens navn, farve og kontur i **Konfigurér kabelkategorier…**.

De to vigtigste definitioner er fastlagt som:

- **Tændkabel** = kabel fra afbryder til lampested.
- **Mellemkabel** = kabel mellem lampesteder på forskellige grupper.

Eksisterende projekter får automatisk standarddefinitionerne på standardkategorier, hvis de ikke allerede har en definition. Egne beskrivelser bevares.


## Nye kabelkategorier: Mellemkabel og Tændkabel (0.50.19)

Standardlisten over kabelkategorier er udvidet med **Mellemkabel** og **Tændkabel**. De fungerer på samme måde som de øvrige kategorier: hver kategori kan få sin egen farve og kontur/linjetype, kan vises/skjules direkte fra **Vis → Kabelkategorier**, og ligger på sit eget kategori-lag.

Ældre projekter får de to nye kategorier tilføjet automatisk første gang de åbnes i 0.50.19, uden at eksisterende kategoriindstillinger overskrives. Efter projektet er gemt i 0.50.19 kan kategorierne fortsat slettes eller ændres som normalt.


## Kabelkategorier på lag-niveau (0.50.18)

Kabler kan nu tildeles en anvendelseskategori som **Stikkontakter**, **Udendørs stikkontakter**, **Udendørs lys**, **Lampesteder**, **Spots**, **Ladeboks**, **Hvidevarer / faste forbrugere**, **Data / netværk** eller **Øvrige**. Egne kategorier kan også oprettes og omdøbes.

Hver kategori har fælles **farve** og **kontur/linjetype** (fuldt optrukket, stiplet, prikket eller streg-prik). Kategorien vælges direkte i Kabelværktøjet, og dens stil kan redigeres samme sted eller via **Værktøjer → Konfigurér kabelkategorier…**.

Kategorierne er implementeret på **lag-niveau**. **Vis → Kabelkategorier** kan derfor vise/skjule hele anvendelsesgrupper, og de samme kategori-lag findes i Lag-panelet. PDF/print respekterer lagtilstanden, og DXF-output placerer kabler på separate kategori-lag. Se `docs/history/CABLE_CATEGORIES_0.50.18.md`.


## Åbn seneste projekter (0.50.17)

Menuen **Fil → Åbn seneste…** viser nu op til otte senest anvendte Elplan-projekter. Listen opdateres ved åbning, import og gemning, manglende filer ryddes automatisk væk, og listen kan nulstilles direkte fra menuen. Det senest anvendte projekt kan åbnes med **Ctrl+Shift+O**. Den normale **Åbn**-dialog starter samtidig i mappen for det senest anvendte projekt.

Seneste projektstier gemmes kun som maskinlokal programindstilling og eksporteres fortsat ikke med kernedata.

## Tydelige indføringsnumre i PL-hover (0.50.16)

PL-popupens grafiske miniature viser nu de fysiske **indføringsnumre 1-6** tydeligt direkte ved kabelindføringerne. Nummerbadges er flyttet ind i det synlige previewområde og gjort en anelse større, så især de øverste og nederste indføringer ikke bliver klippet.

Kabel-ID vises **ikke længere på selve illustrationen**. Kabelnummer, ekstra mærkning, kabeltype og kabelben står fortsat i tekstoversigten ved siden af, så grafikken kan bruges til fysisk portidentifikation uden visuel støj.

## Tydeligt kabelnummer i PL-hover (0.50.15)

PL-popupens tekstoversigt viser **Kabelnr.** som et separat fremhævet felt for hver anvendt indføring, mens ekstra kabelmærkning vises på sin egen linje.

## Visuelle hover-kort og ryddelig projektstruktur (0.50.14)

Projektmappen er ryddet op: tests ligger nu i `tests/`, historiske versionsnoter/audits i `docs/history/`, aktuelle referencenoter i `docs/reference/` og demo-/templatefiler i `examples/`. Dermed er antallet af filer i programmets rod reduceret markant uden at ændre programmets startfiler.

Hover-overblikket er samtidig redesignet som et visuelt kort. PL-dåser viser nu en lille grafisk kabelindføringspreview med de seks porte, kabelkapper, gennemføringer og 3G/5G/7G-ledervifte sammen med den kompakte tekstoversigt. Symboler og kabler med BOM-data får tilsvarende et grafisk preview.

I stedet for kun en kort BOM-status viser popup'en nu de **faktiske artikler og styklister på den konkrete symbolforekomst**. Styklister vises med navn og de underliggende artikler; direkte artikelbindinger og Wago-artikler vises også med artikelnummer, antal og beskrivelse.


## Hover-overblik for PL-dåser og artikeltilknytninger (0.50.13)

Plantegningen har nu en diskret hover-popup med 0,5 sekunders forsinkelse. På et **lampested/PL-dåse** viser den den fysiske kabelindføring 1-6, kabel-ID/mærkning, kabeltype, kabelbenets side, ledige indføringer og fysisk orientering — **uden lederfordelingen**.

På øvrige symboler og kabler vises hover-popup kun, når den konkrete forekomst har en tilknyttet **artikel eller stykliste/BOM**. Det giver et hurtigt visuelt overblik uden at gøre plantegningen permanent mere teksttung.


## Tydelig lederfordeling i PL-dåserapporten (0.50.12)

PL-dåserapporten er udvidet med et dedikeret afsnit **Lederfordeling - fysisk montage**. Hver fysisk leder vises med indføringsnummer, kabel-ID, lederfarve og den faktiske montagedestination: direkte klemme, Wago med én bro til udtaget, ren Wago-sløjfe eller løs/ikke fordelt leder. Farverne vises som små kabelprøver, så rapporten kan bruges direkte ved montage.

Rapporten bruger nu **én PL-dåse pr. A4-side**. Det giver plads til op til 42 kendte 7G-ledere (seks indføringer) fordelt i to læsbare kolonner, samtidig med at fysisk orientering, kabelindføringer, Wago-samlinger, terminalbelastning og montagekontrol stadig er synlige. Se `docs/history/PL_BOX_0.50.12.md`.

## Fysisk PL-orientering og montagerapport (0.50.11)

PL-dåsens **fysiske orientering kan vælges i 0°, 90°, 180° eller 270° relativt til plantegningens top**. Indføring 1-6 roterer visuelt med dåsen, inklusive monteringsører, kabelstumper, gennemføringer og 3G/5G/7G-preview. Kabeltilknytningerne ændres ikke, når dåsen roteres.

Under **Værktøjer → PL-dåserapport…** kan hele projektets PL-dåser eksporteres som en udskriftsvenlig A4-PDF. Grundrapporten viser fysisk orientering, port 1-6 med kabel-ID/type, lampeudtagstype, Wago-samlinger og montagekontrol. Se `docs/history/PL_BOX_0.50.11.md`.


## Synlig 3G/5G/7G-lederopbygning ved kabelenden (0.50.10)

Fanen **Kabelindføringer** viser nu ikke kun kabelkappen og gennemføringen. Inde i PL-dåsen stopper yderkappen ved en tydelig afisoleringskant, hvorefter en kort **3G-, 5G- eller 7G-ledervifte** bliver synlig. Lederfarverne hentes fra den samme kabelprofil som lederfordelingen: gul/grøn, blå, brun samt sort/grå og ved 7G også rød/hvid. PE vises grøn med gul markering, og lyse ledere får kontrastkant. Ukendte kabelopbygninger vises fortsat uden gættede ledere. Se `docs/history/PL_BOX_0.50.10.md`.

## Mere fysisk kabelindføringsgrafik i PL-dåsen (0.50.9)

Fanen **Kabelindføringer** er gjort mere fysisk og appellerende. Et placeret kabelben vises nu som et egentligt **mørkt installationskabel** fra kabelkortet, gennem en rund **knockout/gennemføringsmuffe** og et lille stykke ind i selve PL-dåsen. Kablet har en smal farvet identifikationsstribe, mens ledige indføringer kun viser den tomme knockout. Se `docs/history/PL_BOX_0.50.9.md`.


## Wago-sløjfer uden forbindelse til lampestedet (0.50.8)

Wago-editoren kan nu bruges til **rene sløjfer/samlinger inde i PL-dåsen**. I Wago-dialogen vælges det med afkrydsningen **Forbind Wago til lampeudtaget med én bro**. Når den er slået fra, går de valgte kabelledere kun ind i Wago-muffen; der tegnes ingen bro til lampeudtaget, og samlingen optager ingen plads på lampestedets terminal.

Det er ikke længere nødvendigt først at tildele en løs leder til lampestedet. Løse ledere kan vælges direkte i Wago-editoren, og en valgt leder kan også trækkes/klikkes direkte på en Wago-blok. Højreklik på en leder har desuden **Sløjf leder i Wago uden lampested…**. Wago-artikelforslaget tager automatisk højde for, om der skal reserveres én port til en lampestedbro eller ej.

Ældre Wago-samlinger fungerer uændret: mangler det nye felt `connects_to_outlet`, fortolkes samlingen som en traditionel Wago med én bro til udtaget. Se `docs/history/PL_WIRING_VISUAL_0.50.8.md`.

## Planlagt Wago, eksklusiv Wago-bro, auto-routing og montagekontrol (0.50.7)

Wago-samlinger kan nu oprettes **på forhånd**, også før nogen leder er tildelt terminalen. Når en Wago findes for PE, N, L eller en tænding, går **alle kabelledere for funktionen gennem Wago'en**, og der går altid kun **én bro videre til lampeudtaget**. Nye ledere der tildeles funktionen føjes automatisk til den eksisterende Wago, og en for lille Wago-artikel udløser forslag om en større variant.

Ledereditoren har samtidig fået en første automatisk routingmotor. Lange forbindelser fordeles i separate top-/bundspor og sorteres efter deres slutpunkt, så parallelle forbindelser krydser mindre og bliver lettere at følge. Under Wago-rækken vises desuden en ny **Montagekontrol** med terminalbelastning, Wago-portkapacitet, tændingsstatus og kendte montagefejl/advarsler. Se `docs/history/PL_WIRING_VISUAL_0.50.7.md`.

## Forbindelses-hover, højreklik og flytbare Wago-muffer (0.50.6)

PL-ledereditoren har nu tre hurtigere arbejdsformer. Når musen holdes over en leder, en terminal eller en Wago-samling, fremhæves **hele den elektriske forbindelse**, mens de øvrige lederforløb tones ned. Hit-zonen følger også selve lederkurven, så man ikke behøver ramme den lille lederende.

Et **højreklik på en leder** åbner en kompakt menu med Frigør, direkte flytning til de fysiske terminaler samt Tilføj/Fjern/Redigér Wago. De normale kapacitetskontroller og advarslen ved overfyldning bruges stadig.

Wago-muffer kan nu **trækkes frit rundt inde i PL-dåsen**. Placeringen gemmes som relative `x/y`-koordinater i den eksisterende Wago-samling, så den følger dialogens størrelse. Højreklik på Wago giver også Redigér, Nulstil placering og Fjern. Se `docs/history/PL_WIRING_VISUAL_0.50.6.md`.


## Blødere lederføring, Delete-frigørelse og Wago-artikler (0.50.5)

PL-lederfordelingen er finpudset igen. Når en farvet leder er valgt i grafikken, kan den nu frigøres med **Delete** eller **Backspace**. Den tidligere grafiske kabelkappe ved indføringen er fjernet, så kun de faktiske farvede ledere står tilbage.

Lederforløbene tegnes nu som én sammenhængende Bézier-kurve fra indføring til klemme/Wago. Det giver en mere naturlig bøjning og fjerner det synlige hårde knæk.

WAGO-serien er samtidig koblet ind i artikel/BOM-flowet. De indbyggede artikler **221-412**, **221-413**, **221-415** og **221-420** kan vælges på en Wago-samling. Editorens forslag tager højde for, at der ud over de valgte kabelledere skal være én forbindelse videre til lampeudtaget. Det valgte artikelnummer gemmes på `pl_box_splices`, og samlingen medtages derefter i BOM. Mangler artikelvalget, vises samlingen som en manglende BOM-del.

Se `docs/history/PL_WIRING_VISUAL_0.50.5.md`.

## Fysisk lampeudtag og terminalbaseret lederfordeling (0.50.0)

PL-dialogens **Lederfordeling** er redesignet omkring selve lampeudtagets fysiske klemrække. Vælg **Generisk PL**, **LK klassisk** eller **LK Wiser / dæmpbar**. LK klassisk vises som **N · L · PE · M1 · M2**, mens Wiser/dæmpbar vises som **PE · N · styret udgang · L**. Farvede ledere trækkes direkte fra kabelindføringen til den mærkede klemme.

Reserve/ikke tilsluttet er flyttet til små sekundære parkeringsfelter, og tændinger der ikke kan rummes af den valgte fysiske udtagstype markeres direkte i grafikken. De eksisterende tabeller er stadig tilgængelige via **Vis tabel / avanceret**, men er skjult som standard. Se `docs/history/PL_LAMP_OUTLET_0.50.0.md`.


## Grafisk lederfordeling i PL-dåsen (0.49.1)

Lederfordeling er nu bygget op omkring selve PL-dåsen i stedet for tabellen. Kabelben vises som kabelkapper ved indføring 1–6, og 3G/5G/7G-lederne faner visuelt ud inde i dåsen. Tildelte ledere tegnes helt frem til grafiske samleklemmer for PE, N, Fast fase, tændinger, reserve osv. Tændingsklemmer viser den konkrete afbryderkanal fra tilhørsforholdene.

En leder kan **trækkes direkte** til en klemme eller vælges med klik → klik. De gamle tabeller er bevaret bag **Vis detaljer / tabel**, men er skjult som standard. Se `docs/history/PL_WIRING_VISUAL_0.49.1.md`.


## Afbryderkanaler og tændingskontrol i PL-dåsen (0.49.0)

- PL-dialogen viser nu kabel-ID **og ekstra kabelmærkning**.
- Eksisterende tilhørsforhold kobles til den konkrete afbryderkanal i 1-polet/krone/kombi-symboler.
- Direkte kabelvej fra afbryder til lampested identificeres og bruges til at kontrollere, at tændingslederen ligger på det forventede kabelben.
- Én fysisk leder kan kun have én funktion; ændring til en anden tænding erstatter den gamle funktion.
- Manglende, forkert placerede og dublerede direkte tændingsledere markeres grafisk.
- Korrespondance/krydsning identificeres, men terminalforløbet markeres som manuelt i stedet for at blive gættet.
- Se `docs/history/PL_SWITCH_MAPPING_0.49.0.md`.


## Visuel lederfordeling i PL-loftdåser (0.48.1)

PL-konfiguratorens fane **Lederfordeling** bruger nu den ønskede generelle 7G-profil: **gul/grøn, blå, brun, sort, grå, rød og hvid**. 3G forbliver gul/grøn + blå + brun, og 5G gul/grøn + blå + brun + sort + grå. Den konkrete kabelartikels datablad har altid forrang, hvis et produkt afviger.

Tildelingen kan nu udføres direkte i grafikken: **klik på en farvet leder ved kabelindføringen og klik derefter på den ønskede samling** inde i PL-dåsen. Mulige samlinger vises hele tiden som klikbare mål, også før de er taget i brug. Tabellen med Funktion / samling er bevaret som alternativ præcis redigering og synkroniseres med den grafiske markering.

Gul/grøn foreslås som PE og blå som N for 3G, 5G og 7G. Brun, sort, grå, rød og hvid får ingen automatisk aktiv funktion; tændinger og fast fase vælges bevidst. Eksisterende 0.48.0-planer med nummererede 7G-ledere migreres til de nye farve-id'er uden at miste gemte funktioner/noter.

## PL-loftdåse / kabelindføringer (0.47.0)

Lampesteder (`light_connection`) kan nu dokumenteres som en fysisk PL-loftdåse med seks kabelindføringer. Dobbeltklik på lampestedet, eller brug **Konfigurer PL-dåse…** i Egenskaber. Dialogen viser en skalerbar vektortegning med indføring 1–3 øverst og 4–6 nederst.

- Et kabel der starter/ender ved lampestedet bruger én indføring.
- Et gennemgående/sløjfet kabel bruger to indføringer: **Side A** og **Side B**.
- Kabelben kan trækkes fra listen til en port eller placeres med knappen.
- **Fordel automatisk** foreslår porte ud fra kabelretningen i plantegningen.
- Status viser anvendte, ikke placerede og eventuelle overskydende kabelben.
- PL-placeringerne følger kabel-UID'er og valideres ved projektgemning, så døde kabelreferencer ikke gemmes videre.
- Fysisk PL-data kopieres ikke med et kopieret lampested.


## Patchkabler på eget lag (0.46.2)

Patchkabler er nu en selvstændig kabeltype i Kabelværktøjet og gemmes på laget `EL-PATCHKABLER`. Hurtig visning har en særskilt **Patchkabler**-knap, så patchkabler kan skjules uden at skjule almindelige installationskabler eller ledninger.

- **Kabel** → `EL-KABLER`
- **Patchkabel** → `EL-PATCHKABLER`
- **Ledning** → `EL-LEDNINGER`

Et eksisterende kabel kan flyttes til patchkabellaget ved at markere det, vælge **Patchkabel** under Type og trykke **Anvend kabeldata**. Kabelgeometri, artikeltilknytning, længde, BOM og symbolforbindelser bevares.



## Netværks-patchkabel på metermål (0.46.1)

- Tilføjer **HELUKABEL HELUKAT 600IND CAT.7 S/FTP PUR ROBUSTFLEX**, art. **802184**, som indbygget kabelartikel.
- Artiklen er afmålt (`unit = m`, `package_length_m = 0`) og matcher kabelpreset **CAT7 S/FTP**.
- Officielt HELUKABEL-produktlink, EAN, datablad og produktfoto er medtaget, så Artikeldatabase viser samme preview som øvrige billedartikler.
- Nye bundtede basisartikler flettes automatisk ind i eksisterende kernedata ved opstart; brugerens eksisterende artikelredigeringer overskrives ikke.

## Hurtig visning, kabelstil og patchpanel (0.46.0)

Hovedværktøjslinjen har nu **Plan · Symboler · Kabler · Tekst · Vis alt** som hurtige, midlertidige visningsfiltre. Filtrene ligger oven på de egentlige lagvalg og ændrer derfor ikke checkboksene i Lag-panelet. De huskes som brugerindstillinger og kan altid nulstilles med **Vis alt**. Hurtigvisning er en editorfunktion; PDF/print styres fortsat af de egentlige projektlag.

Kabelværktøjet har fået **Farve** og **Linjetype** pr. kabel. Linjetyperne er Fuldt optrukket, Stiplet, Prikket og Streg-prik. Nye kabler bruger de aktuelle standardvalg; eksisterende kabler kan ændres individuelt via **Valgt kabel → Anvend kabeldata**. Farve/linjetype følger med i projektfilen og anvendes i editor, PDF/print og DXF. Ældre projekter får automatisk rød/fuldt optrukket som kompatible standarder.

Symbolpaletten indeholder nu **Patchpanel / datacentral (12 porte)** på `EL-TELE-DATA`. Symbolet har 12 individuelle snap-/kabelporte (2×6), så Ethernet-kabler kan afsluttes separat i panelet. Kabeltypefeltet har desuden CAT6 U/UTP, CAT6A F/UTP og CAT7 S/FTP som hurtige presets; feltet er fortsat frit redigerbart.

## Guide og templates til artikelimport (0.45.5)

I **Artikler og BOM → Artikeldatabase** findes nu **Importguide…** ved siden af **Importér bibliotek…**. Guiden beskriver JSON/CSV-importen, viser alle understøttede felter og markerer `article_no` / Artikelnummer som eneste obligatoriske felt. Den viser også komplette JSON- og CSV-eksempler.

Fra guiden kan man gemme en aktuel **JSON-template** eller **CSV-template**. De genereres fra samme feltskema som importeren, så dokumentation, kolonneoverskrifter og importlogik følger hinanden. Der medfølger desuden `examples/article_library/article_library_template.json`, `examples/article_library/article_library_template.csv` og `docs/history/ARTICLE_IMPORT_GUIDE_0.45.5.md` i programpakken.

## Én samlet Artikeldatabase (0.45.4)

Fra 0.45.4 findes der kun én artikelvisning i **Artikler og BOM → Artikeldatabase**. Det tidligere Standardbibliotek er fjernet fra brugerfladen. De indbyggede basisartikler, LK-synkroniserede artikler, kabelartikler og manuelt oprettede/importerede poster ligger alle i den samme globale kernedatabase `articles.json`.

Artikeldatabase har produktfoto-preview, producenter-/leverandør-/databladlinks, prisredigering og de avancerede filtre fra det tidligere Standardbibliotek. Tabellen er fortsat modelbaseret, så flere tusinde artikler kan filtreres uden at oprette tusindvis af tunge Qt-celler.

**Ny artikel…** opretter artikler manuelt. Ud over artikelnummer, beskrivelse, fabrikant, serie, type osv. kan man angive produktlink, leverandørlink, datablad og direkte billede-URL.

**Importér bibliotek…** læser:

- JSON: native/rekommenderet format. Accepterer både `{"articles":[...]}` og en simpel liste af artikelobjekter.
- CSV: UTF-8/Excel-venligt; komma, semikolon eller tabulator opdages automatisk. Danske kolonnenavne som `Artikelnummer`, `Beskrivelse`, `Fabrikat`, `EL-nr.`, `Billede` m.fl. genkendes.

Ved import kan man vælge **Flet sikkert** eller **Opdatér eksisterende**. Der tages automatisk backup af artikelbasen før import. **Eksportér bibliotek…** kan skrive samme database som JSON eller CSV. Prisbog og projektbindinger er fortsat separate kernedata/projektdata og ændres ikke af artikelbibliotek-importen.

## Produktsemantisk artikelmodel (0.59.21)

Artikeldatabasen skelner nu mellem **Produktfamilie**, **Produktvariant** og **Kompatibilitet**. De to første beskriver produktets egen identitet; kompatibilitet beskriver kun hvilke designserier, montagesystemer eller produktfamilier varen kan anvendes sammen med. Et kompatibelt design må derfor aldrig automatisk blive produktets egen variant.

Et centralt eksempel er LK FUGA AIR: den almindelige 504D3010-familie vises som `LK FUGA AIR / Standard`, mens 504D3510-familien vises som `LK FUGA AIR / SLIM`. AIR indstøbnings- og indmuringsdåser kan samtidig være kompatible med SLIM-rammer uden selv at være SLIM-dåser. Historiske Design-værdier på dåser bevares som rå provenance og kontrolleres af Datakvalitet.

Artikelbrowser og artikelvælger har separate filtre for Familie og Variant. Kompatibilitet vises separat i artikelinformationen, og bekræftede kompatibilitetsdata kan eksporteres/importeres i både JSON og CSV.

## Skånsom LK-katalogsynkronisering (0.59.20)

Den aktuelle LK-synkronisering prioriterer stabil adgang frem for maksimal hastighed. **Alle** requests til LK.dk køres én ad gangen, inklusive produktdetaljer, kategoritræ og fallback-søgning. Mellem netværkskald lægges som standard ca. **0,8–1,5 sek.** tilfældig pause.

**Skånsom synkronisering** er standardvalget. Katalogindekset kan genbruges i op til 24 timer, mens friske produktsider og nyligt kontrollerede LK-rækker kan genbruges i op til 14 dage. **Fuld genhentning (skånsom)** genhenter produktsiderne, men kan stadig genbruge et friskt katalogindeks for at undgå unødige kategori-kald.

Ved HTTP **403**, **429** eller gentagne **5xx** svar sættes synkroniseringen automatisk på pause med stigende backoff. Et eventuelt `Retry-After`-header respekteres. Hvis LK fortsat afviser trafikken efter backoff, stopper hele synkroniseringen, så programmet ikke fortsætter med tusindvis af kald under en blokering.

Fremskridt gemmes løbende i `lk_catalog_cache.json`. En afbrudt fuld genhentning kan derfor fortsætte senere og genbruge de produktsider, der allerede var færdige. Hvis selve katalogets startside ikke kan hentes, udføres der ikke en stor fallback-probe. Artikelbasen ændres først, når en komplet og plausibel synkronisering er afsluttet.

## Hurtigere LK-katalogsynkronisering (0.45.3)

LK-synkroniseringen henter nu op til 8 produktsider parallelt. Produktrequests bruger 8 sekunders timeout og genforsøges kun, hvis den konkrete side fejler. En lokal `lk_catalog_cache.json` gemmer nyligt hentede LK-poster i op til 7 dage, og katalogindekset kan genbruges i op til 6 timer. Nyligt synkroniserede LK-rækker i `articles.json` kan også bruges som startcache efter opgradering fra 0.45.2.

Dialogen tilbyder **Hurtig synkronisering** og **Fuld genhentning**. Hurtig synkronisering genbruger frisk cache og henter nye/forældede poster; fuld genhentning ignorerer cache og henter alle fundne produktsider igen. Statusfeltet viser løbende antal behandlede produkter, samtidige forbindelser, cache-genbrug og fejl der venter på genforsøg.


## LK-katalogsynkronisering (0.45.2)

Under **Artikler og BOM → Artikel database** findes **Synkronisér LK.dk…**. Funktionen henter LK/Schneiders onlinekatalog og fletter produkterne ind i den globale kernedatabase `articles.json`. Projektfiler ændres ikke.

Synkroniseringen opdaterer producentfelter som beskrivelse, LK-/EL-/EAN-numre, serie/kategori, farve, status når den kan konstateres, produktlink og produktfoto. Lokale grossistlinks, egne noter og den separate prisbog bevares. Før databasen skrives, oprettes automatisk en backup under `ElplanDWGEditor/backups`.

Første fulde synkronisering kan tage nogle minutter. Den kan annulleres uden at ændre databasen. Artikel database bruger fra 0.45.2 en modelbaseret tabel med søgning, så et stort LK-katalog kan håndteres uden tusindvis af `QTableWidgetItem`-objekter.

## Portable kernedata og projektpakker (0.45.0)

0.45.0 adskiller programmets **kernedata** fra **projektdata**. Under **Fil → Overfør / backup** findes fire nye handlinger:

- **Eksportér kernedata…** → `.elplancore` med den globale artikelbase, globale styklister, prisbog/prisestimeringer, custom-symboler og portable programindstillinger. Maskinspecifikke stier som ODA File Converter og seneste projektstier eksporteres ikke.
- **Importér kernedata…** → kan erstatte eller flette kernedata. Før import oprettes automatisk en backup under brugerens Elplan-datamappe.
- **Eksportér projektpakke…** → `.elplanproj` med præcis ét `.elplan.json`-projekt og dets DWG/DXF-kilde. Kernedata medtages ikke.
- **Importér projektpakke…** → pakker projekt og CAD-kilde ud i en selvstændig mappe, omskriver CAD-linket til en relativ sti og åbner projektet.

Projektpakken indeholder kun en afhængighedsliste med artikelnumre/stykliste-ID'er, så programmet kan advare, hvis den anden PC mangler de tilhørende kernedata. Pakkeformaterne er ZIP-baserede med manifest og SHA-256-checksummer.

### Datagrænse fra 0.45.0

**Kernedata** ligger bruger-globalt og deles mellem alle projekter: artikelbase, styklister, priser, custom-symbolbibliotek og portable standardindstillinger. **Projektdata** indeholder plantegningens symboler, kabler, tekster, lagtilstand og de konkrete artikel-/styklistebindinger.

Gamle projekter med indlejret `article_catalog`, `bom_assemblies` eller `custom_symbols` migreres automatisk til kernedata ved åbning. En kategori fjernes først fra projektet, når den er gemt sikkert i kernedata. Ved næste projektsave skrives det rene 0.45-format.


## Fri / diagonal kabelruteføring (0.44.5)

**0.44.5:** Kabelværktøjet har nu en tydelig rutetilstand med **Fri / diagonal** som standard for nye kabler og **Ortogonal (90°)** som alternativ. I fri tilstand forbindes hvert brugerklik direkte med næste punkt, så kabeltræk kan føres diagonalt som i en fysisk installation. Symbol-/kabelrute-snap, sløjfning, parallelle baner, længdeberegning, PDF-visning og efterredigering bruger samme kabelmodel i begge tilstande. Eksisterende kabler beholder deres gemte `orthogonal`-værdi.

## Direkte parallel-rendering fra rigtige projekter (0.44.4)

**0.44.4:** Parallelberegningen skubbes nu direkte ind i hvert CableItem som den path Qt skal male. Det fjerner et indirekte cache-/refresh-led, som kunne få virkelige parallelkabler til stadig at blive vist på centerlinjen. Et valgt kabel beholder desuden sin visuelle bane; kun under aktiv handle-redigering vises centerlinjen midlertidigt. Rettelsen er reproduceret på det konkrete G01/K01-forløb fra en rigtig 0.44.2-projektfil.



## Parallelle og mange kabler (0.44.1)


**0.44.1:** Parallel-detektionen er gjort skærmbaseret og tolerant over for små CAD-afvigelser. Kabler, der visuelt ligger oven i hinanden, separeres nu også når centerlinjer har få pixels forskel, små vinkelafvigelser eller forskellige kollineære knækpunkter. Reelt separate ruter holdes fortsat adskilt.
Kabler, der følger samme logiske rute, kan nu vises som stabile parallelle skærmbaner med justerbar pixelafstand. Nye kabler kan snappe til en eksisterende kabelrutes centerlinje, så flere kabler genbruger samme føringsvej uden at brugeren skal ramme koordinaterne manuelt. Fælles stræk med mindst tre kabler får en diskret `×N`-markering, og et valgt symbol kan fokusere sine egne kabler ved at tone resten ned. Alt er rent visuelt/snap: hvert kabel beholder eget ID, kabeltype, artikel, symboltilslutninger og længde.


## Fri kabelrute med låste symbolankre (0.43.3)

Efterredigering af kabler kombinerer nu to krav: grønne fysiske tilslutningspunkter bliver siddende på deres symbolporte, mens blå geometriske knæk kan trækkes frit. Hvis et blåt knæk flyttes til en position, der ikke kan forbindes direkte ortogonalt til de faste naboer, indsætter programmet automatisk et eller to ekstra blå dogleg-punkter. Dermed kan kabelvejen ændres uden at kablet snapper ud af symbolerne.

## Låste kabelankre ved redigering (0.43.2)

Fysiske kabeltilslutninger vises fortsat som grønne punkter, men er nu låste ankre til den registrerede symbolport. De blå geometriske knækpunkter kan redigeres frit uden at trække et fysisk anker væk fra symbolet. Projekter gemt med den tidligere redigeringsfejl repareres automatisk ved åbning.

## Interaktiv kabel-assistent (0.43.1)

Når et fysisk symbol klikkes under kabeltegning, vises en lille ikke-modal popup ved symbolet. Tilslutningen er allerede registreret, så brugeren kan ignorere popup'en og klikke videre. Popup'en giver hurtige valg til **Afslut her**, **Afslut + nyt herfra**, **Kun forbi** og **Fortryd punkt**. Den viser samtidig eksisterende kabler ved symbolet og advarer, hvis samme symbol allerede er registreret på det aktive kabel. Assistenten kan slås fra i Kabelværktøj og husker valget globalt.

0.43.1 bygger videre på kabelmodellen, så ét fysisk kabel kan sløjfes gennem flere installationspunkter uden at blive opdelt i kunstige kabelstræk. Et kabel har fortsat ét ID, én type, én artikel og én samlet længde, men gemmer nu alle fysiske symboltilslutninger langs ruten. Kabelværktøjet viser forløbet, og markerede symboler viser hvilke kabler der starter, ender eller går gennem symbolet. Ældre projekters start-/sluttilslutninger migreres automatisk. LK/FUGA-artikler får desuden direkte produktfoto fra LK's eget varenummerbaserede katalog med lokal cache og eksisterende fallback.

0.42.5 er en stabilitetsrettelse til Artikler og BOM. En regressionsfejl i BOM-dialogens antalsformatering kunne få hele dialogen til at lukke med TypeError, både ved selvstændig åbning og ved åbning fra et symbol. Fejlen er rettet uden ændringer i projektdata eller arbejdsgang. Forbedringerne fra 0.42.4 til kabelarbejdsgangen er bevaret.

0.42.3 ændrer BOM-systemet til eksplicitte tilknytninger pr. fysisk symbol og pr. kabelstræk. En artikel eller stykliste, der tilknyttes ét symbol, gælder kun dette ene symbol; tilsvarende gælder en kabelartikel kun det valgte kabelstræk. BOM'en foretager dermed ingen automatisk tildeling ud fra symboltype eller kabeltype. Ikke-tilknyttede BOM-relevante symboldele og kabler vises i stedet som en kontrol/advarsel.

0.41.6 er en generel GUI-polish: talboksenes op-/ned-pile er gjort tydelige og robuste på Windows, dropdown-felter og tabeller har fået bedre kontrast og feedback, og vandrette/lodrette scrollbars er visuelt strømlinet. Funktionalitet og arbejdsgange er ellers bevaret.

0.41.5 gør artikelvælgeren og Standardbiblioteket modelbaserede (`QTableView` + `QAbstractTableModel`), så filtrering og sortering ikke længere genopbygger tusindvis af tabelceller. Produktpreview er desuden forsinket kort og gamle billedrequests afbrydes ved hurtigt artikelskift. Kolonnebredder, tooltips, prisbog og globale styklister er bevaret.
0.41.1 fortsætter datavasken af artikelbiblioteket med en systematisk LK FUGA-kontrol. 501D0412 og de øvrige centrale FUGA-indsatse har nu verificeret EL-nr./EAN og filtermetadata, og flere manglende stikkontakt-/afbrydervarianter samt tilhørende afdækninger er tilføjet.

0.40.0 udvider standardartikelbiblioteket med **online produktfotos/tegninger med lokal cache** og et første verificeret **Nordtronic**-sortiment. LK-artikler kan hente illustration fra Lemvigh-Müller, mens Nordtronic-artikler bruger producentens egne produktsider/billeder. Hvis nettet eller billedet ikke er tilgængeligt, bruges den eksisterende skematiske vektorillustration automatisk.

0.39.0 tilføjer **genbrugelige styklister** til artikel-/BOM-systemet. En stykliste er en opskrift med flere artikler og mængder, fx indsats + tangent + teknisk ramme + designramme + dåse. Hver fysisk symboldel kan enten bruge en stykliste eller den eksisterende manuelle artikelkonfiguration. Kombisymboler behandles fortsat modul for modul.

0.38.2 gør artikelbrowseren mere filtrerbar og tilføjer FUGA SLIM-designrammer. 0.38.1 kompletterer LK FUGA AIR SLIM-forfradåserne med 1, 1½, 2 og 2½ modul (hulsav ikke medtaget). 0.38.0 introducerer standardbiblioteket for **LK FUGA/Wiser** og **Waskönig+Walter-kabler**.

## Artikeldatabase

Under **Værktøjer → Artikler / BOM…** findes fem faner: **Tilknytning, Styklister, Kabler, Artikeldatabase og BOM**.

**Artikeldatabase** er den eneste artikelbase i brugerfladen. Den indeholder både programmets indbyggede basisposter, LK-synkroniserede artikler, Waskönig+Walter/Nordtronic-poster og brugerens egne/importerede artikler. Der er ikke længere et separat Standardbibliotek.

Databasen kan filtreres på bl.a. fabrikat, type, design, modul, farve, diameter, CCT og IP. Valgt artikel vises med produktfoto/skematiske fallback, metadata og direkte links til producent, leverandør og datablad.

Produktillustrationer **bundles ikke i programmet**. Artikelbrowseren henter dem fra den registrerede produktkilde ved behov og gemmer en lokal cache. Manuelt oprettede artikler kan bruge en direkte `image_url` eller produktside.

For kabler vælges en artikel eksplicit pr. fysisk kabel. Samme kabel kan gå gennem flere tilslutningssteder uden at få nyt kabel-ID. En afmålt artikel giver meter i BOM. En rulleartikel beregnes som `ceil(samlet estimeret længde / rullelængde)`, efter at alle stræk med samme artikelnummer er summeret.

0.36.1 er en vedligeholdelsesudgave med fokus på stabilitet og dataintegritet: sikker håndtering af ikke-gemte ændringer, atomisk projekt-/indstillingsgemning, strengere validering af projektdata, robuste relative CAD-stier, oprydning af relationer ved sletning, mere korrekt lagstyring samt hurtigere Windows-opstart når afhængighederne allerede er installeret.

0.36.0 tilføjer automatisk grafisk separation af parallelle kabler. Når flere kabler deler samme stræk, vises de i separate lanes med et kort fan-in/fan-out ved tilslutningspunkterne. Den logiske kabelrute og kabellængden ændres ikke. PDF/preview/print følger samme visning.


0.35.8 gør Udskriftsforhåndsvisning WYSIWYG ved at vise den samme midlertidige PDF, som eksportmotoren genererer. Dermed matcher Preview PDF-eksportens tekststørrelser, mærkninger, margen, udsnit og dæmpning. Funktionerne fra 0.35.7 er bevaret.

## Styklister

Under **Værktøjer → Artikler / BOM… → Styklister** kan der oprettes, redigeres, duplikeres og slettes genbrugelige artikelopskrifter.

- En stykliste kan indeholde et vilkårligt antal artikler med mængde pr. enhed.
- **Find artikel…** åbner en stor artikelvælger med søgning, filtre, sortérbare kolonner, preview, EAN/EL-nr. og producent-/leverandørlinks.
- Under **Tilknytning** kan den valgte fysiske del sættes til en gemt stykliste med ét klik.
- Den manuelle artikelkonfiguration gemmes separat og kan aktiveres igen med **Brug manuel**.
- **Gem manuel som stykliste…** opretter hurtigt en skabelon ud fra en eksisterende manuel opsætning.
- Når en stykliste redigeres, slår ændringen automatisk igennem på alle symboldele, som bruger den.
- Kombisymboler kan bruge forskellige styklister på Modul 1, Modul 2, korrespondancedel, stikkontakt og fælles/ramme/tilbehør.

Stykliste-definitionerne gemmes som **kernedata** og kan bruges på tværs af projekter. Projektet gemmer kun den konkrete tilknytning (`placement_assemblies`) mellem en fysisk symboldel og en global stykliste.

## Artikler og BOM

Åbn **Værktøjer → Artikler / BOM…** eller brug `Ctrl+B`.

- **Artikelbibliotek:** opret artikelnummer, beskrivelse, fabrikat, enhed og note.
- **Tilknytning:** vælg et konkret symbol i projektet, derefter den fysiske del og tilknyt én eller flere artikler eller en stykliste. Tilknytningen gælder kun det valgte symbol.
- **Kombisymboler:** vises som `Modul 1`, `Modul 2`, osv. samt stikkontakt og en valgfri fællesdel til fx ramme/dåse/tilbehør.
- **BOM:** summerer kun eksplicit tilknyttede artikler/styklister og viser samtidig symboldele og kabler, der endnu ikke har en tilknytning.
- **Eksport:** BOM kan eksporteres som en formateret Excel-tabel (`.xlsx`) eller som UTF-8 CSV med semikolonseparator.

Artikelopsætningen gælder det konkrete valgte symbol i det aktuelle projekt og gemmes sammen med projektfilen. To ens fysiske moduler i samme kombisymbol har separate del-id'er og kan derfor tildeles forskellige artikler, hvis det er nødvendigt.


## PDF-visuel paritet

- Fritekst bruger nu samme faste punktstørrelse som editoren og bliver ikke længere ganget med hele PDF-sidens CAD-skala.
- CAD-tekst og intern symboltekst bruger samme 0,65/0,60-skalering som Qt-rendereren.
- Auto/Minimal/Tydelig/Skjult respekteres i PDF, inklusive de samme semantiske zoomgrænser for primær/sekundær mærkning.
- Kabelmærkning bruger samme ca. 8 pt visuelle profil som editoren.
- Afbrydernes a/b/c vises ved de konkrete fysiske moduler i PDF, også for kombiafbrydere.



## Snaplinjer ved kabelredigering og fritekst

- Når et kabelknæk trækkes under redigering, vises midlertidige vandrette/lodrette hjælpelinjer og punktet snapper til andre synlige kabelknæk og relevante symbolporte.
- Kabelendepunkter prioriterer fortsat den eksisterende elektriske snap til symboler og vægge.
- Fritekst snapper vandret/lodret til andre friteksters placeringspunkter både ved første placering og ved senere flytning.
- Snap-tolerancen er skærmbaseret, så hjælpelinjerne føles ens ved forskellige zoomniveauer.
- Hjælpelinjer er kun visuelle og gemmes ikke i projektet eller i eksport.

## Stikkontakt 3F+N+PE

Den interne `3N`-angivelse er gjort større og flyttet ind i centrum af halvcirklen. Symbolgeometrien til vægsnap er holdt uændret, så den større tekst ikke ændrer afstand/snap mellem vægmonterede symboler.


## Afbryder → lys-guide

Guiden skelner nu mellem **førstegangsopsætning** og **redigering af en eksisterende betjening**:

- **Kroneafbryder:** vælg lampested for tænding 1; guiden går derefter automatisk videre til tænding 2 og afslutter efter andet valg.
- **Dobbelt korrespondance:** samme to-trinsforløb, men eksisterende korrespondancetilhørsforhold kan genbruges.
- **4 trykkontakter:** guiden går automatisk gennem alle fire betjeninger.
- **Kombisymboler:** alle uafhængige afbryderfunktioner gennemgås i rækkefølge, også krone-/korrespondancemoduler.
- **Korrespondance og krydsning:** hvis lampestedet kun har ét eksisterende tilhørsforhold, genbruges det automatisk. Ved flere mulige tilhørsforhold spørger programmet.
- **1-polet/tryk:** én betjening forbliver aktiv efter første valg, så samme betjening kan tilknyttes flere lampesteder.

Når en flertrinsguide er færdig, afsluttes værktøjet automatisk og afbryderen genvælges. Tilhørsforhold gemmes ved hvert klik; **Anvend ændringer** bruges fortsat til de almindelige felter som gruppe, mærkning, størrelse osv.


## Kabellængder

Kabelværktøjet måler nu den faktiske tegnede rute gennem alle kabelknæk. Længden vises live under tegning og opdateres, når et eksisterende kabel redigeres.

- **Automatisk skala:** programmet læser `$INSUNITS` fra DWG/DXF, når filen har en kendt lineær enhed.
- **Manuel enhed:** mm, cm, m, inch og foot kan vælges direkte i **Værktøjer → Kabellængder / skala…**.
- **Kalibrering:** vælg **Kalibrer på tegningen…**, klik to punkter med kendt afstand og indtast den virkelige afstand i meter.
- **Reserve:** en global procent gemmes i projektet; standarden er 10 %.
- **Rapport:** **Værktøjer → Kabellængderapport…** viser alle kabel-/ledningsstræk og summerer materialebehov pr. kabeltype.

Hvis CAD-filen er enhedsløs eller har ukendt `$INSUNITS`, viser programmet bevidst ikke et meterestimat, før enheden er valgt eller tegningen er kalibreret.


## Lys-snap og hjælpelinjer

Ved placering og flytning af symboler i kategorien **Belysning** vises nu midlertidige vandrette/lodrette hjælpelinjer, når symbolets centrum nærmer sig en eksisterende synlig belysningsenhed.

- X og Y snapper uafhængigt, så et punkt kan flugte lodret med ét lys og vandret med et andet.
- Snap-tolerancen er skærmbaseret (ca. 11 px), så funktionen føles ens ved alle zoomniveauer.
- Referencer begrænses til synlige belysningssymboler i/omkring den aktuelle visning for at undgå uventede snaps på tværs af hele huset.
- Hjælpelinjerne er kun visuelle og gemmes ikke i projektfilen.
- **Spot-række** og **Spot-rektangel** kan også snappe deres start-/slutpunkt til eksisterende belysningslinjer.
- Funktionen kan slås til/fra med den nye checkbare **Lys-snap**-knap i topbjælken og huskes mellem programstarter.

## Semantisk mærkningsvisning

Standardvisningen **Auto** bruger nu tydeligere zoomniveauer:

- **Ekstremt langt zoom:** automatisk mærkning skjules helt.
- **Hele plantegningen / oversigtszoom:** primær **Gruppe/kreds** samt `a/b/c` vises som små, diskrete tekster uden store baggrundschips.
- **Arbejdszoom:** valgfri mærkning kommer frem, mens `a/b/c` bliver tydeligere.
- **Detaljezoom:** Spot→lampested og øvrige detaljer kommer frem.
- **Valgt symbol:** fuld relevant information vises midlertidigt uanset zoom.

Visningsmåder under **Lag → Mærkning / tilhørsforhold**:

- **Auto** — anbefalet, adaptiv efter zoom og valg.
- **Minimal** — kun primær Gruppe/kreds.
- **Tydelig** — alle detaljer.
- **Skjult** — skjuler al automatisk symbolmærkning og normal relationsvisning.

Topbjælken har desuden knappen **Mærkning**, som hurtigt kan slå al mærkning fra og tilbage til den senest valgte visning.

## Mindre dominerende tilhørsforhold

Normale relationslinjer vises kun i forbindelse med valg/arbejde og er gjort tyndere og mere transparente. I **Skjult** visning fjernes også den normale relationsoversigt. Aktive link-værktøjer kan stadig fremhæve gyldige mål, så tilknytning fortsat kan udføres.

## Enkeltplacerede spots

Spots placeret direkte fra symbolpaletten bruger nu den dedikerede **Spotstørrelse** og bliver automatisk valgt efter placering. Dermed er panelet **Spot → lampested** straks tilgængeligt i Egenskaber, og knappen **Tilknyt lampested…** kan bruges på samme måde som for spots oprettet med Spot-række eller Spot-rektangel.

Du kan fortsat placere flere enkeltspots efter hinanden; det senest placerede spot er det valgte.

## Mærkning placeres ind i rummet

Indstillingen **Placér automatisk på rummets side af væggen** er bevaret. Programmet forsøger at placere mærkningen på samme side af væggen som symbolet/rummet ved hjælp af montagepunkt, nærmeste væg og symbolretning.

## Øvrige funktioner

- mange-til-mange afbryder ↔ lampested relationer
- Spot → lampested relation og nedarvning af lampestedets tilhørsforhold
- redigerbare kabler og knækpunkter
- Kabelværktøj
- grafisk symbolpalette og symbolkonfigurator
- stabil vægsnap
- spot-række og Spot-rektangel
- fri tekst
- copy/paste og multi-select
- dæmpet CAD-baggrund, valgfrit også i PDF/print
- PDF, udskrift og print-preview

## Installation

Kør:

```bat
start_windows.bat
```

DWG kræver fortsat ODA File Converter. DXF fungerer uden ODA.
### 0.44.4 – parallelle kabler
Kabelværktøjets visuelle indstillinger initialiseres nu uden signal-sideeffekter. Installationer opgraderet fra 0.44.0-0.44.3 får én automatisk reparation af de fejlgemte standarder: parallelle baner aktiveres med 10 px baneafstand.

### 0.57.2 – roligere plantegning og navigator
Navigatoren er opt-in og viser kun et minimalt grafisk overblik. Symbol- og PL-hoverkort er bevaret som hurtig visuel inspektion. Ekstra kabelmærkning gemmes stadig på kablet, men vises ved hover frem for permanent på plantegningen.
