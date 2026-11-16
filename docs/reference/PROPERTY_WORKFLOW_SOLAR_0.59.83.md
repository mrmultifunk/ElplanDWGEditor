# Opgavebaseret Egenskaber og solceller i 0.59.83

## Tre arbejdsspor

Egenskaber-panelet er opdelt efter brugerens aktuelle opgave:

| Spor | Indhold | Gemmemåde |
| --- | --- | --- |
| **Forbind** | Afbryder/lys, spots, kabler og PL-dåse | Direkte gennem den valgte guide |
| **Data** | Gruppe, mærkning, udseende, lås og kombidata | **Anvend ændringer** |
| **Indkøb** | Montage, højde, materialefarve, lagerstatus og BOM | **Anvend ændringer** eller artikel-dialog |

Afbrydere, lampesteder og spots åbner i **Forbind**. Andre symboler åbner i **Data**. Hvis brugeren selv vælger eksempelvis **Indkøb**, bevares dette spor ved næste symbolvalg, så flere forekomster kan registreres i samme arbejdsgang.

## Solcellesymboler

Paletgruppen **Solceller / energi** indeholder:

- **Solcellepanel(er)** – cellegitter og understel, tre kabelporte og fri placering.
- **Solcelleinverter** – grafisk DC/AC-opdeling, fire kabelporte og mulighed for vægsnap.
- **Solcellebatteri** – batterikapsling, terminaler, tre kabelporte og mulighed for vægsnap.

Symbolerne ligger på `EL-SOLCELLER`. De er rene vektorer og bevarer derfor geometrien i skærmvisning, PDF, print og DXF/DWG. En artikel eller stykliste tilknyttes den konkrete forekomst under **Indkøb**.

## Afgrænsning

Versionen introducerer symbolerne og den enkle fysiske dokumentation. Automatisk dimensionering af PV-strenge, DC-beskyttelse, invertereffekt og batterikapacitet er ikke en del af denne version.
