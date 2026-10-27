# LK-katalogsynkronisering – 0.45.3

## Formål

0.45.3 reducerer tiden til en fuld LK-synkronisering uden at ændre artikelmodellens officielle felter eller merge-regler.

## Pipeline

1. LK-katalogindekset crawles som tidligere. Et vellykket indeks gemmes i cache i op til 6 timer.
2. Produktreferencer behandles med op til 8 samtidige worker-tråde.
3. En produktside får 8 sekunders timeout. En succesfuld side hentes ikke igen i samme synkronisering.
4. Kun fejlende produktsider lægges i genforsøgskøen, maksimalt én ekstra gang.
5. Succesfuldt parsede produktposter cachelagres i `lk_catalog_cache.json` i op til 7 dage.
6. Ved hurtig synkronisering kan friske poster fra cachen eller fra den eksisterende kernedatabase genbruges uden ny produkthentning. Nye produktreferencer hentes altid.
7. Ved fuld genhentning ignoreres både produktcache og database-seed.

## Cache og dataintegritet

Cachefilen er ikke kernedata og eksporteres derfor ikke i `.elplancore`. Den kan altid slettes; næste synkronisering genopbygger den. Artikelbasen ændres fortsat først, når hele katalogindsamlingen er afsluttet og valideret. Cache må derimod gerne gemmes løbende, fordi den kun er en accelerationsmekanisme.

Et cache-entry gemmes kun, hvis produktsiden kunne parses til et gyldigt LK-artikelnummer. Fejlende eller ufortolkelige sider bliver derfor ikke låst fast som gyldig cache.

## Hurtig vs. fuld

**Hurtig synkronisering** er standardvalget. Friske produktposter kan genbruges i op til 7 dage, mens nye referencer hentes straks. Det giver især stor gevinst ved gentagne synkroniseringer eller umiddelbart efter opgradering fra 0.45.2.

**Fuld genhentning** bruges, når man eksplicit vil genlæse alle LK-produktsider fra nettet, fx efter større katalogændringer.

## Fremdrift

Under produktfasen vises eksempelvis:

`Henter LK-artikler… 1.284 / 4.932 · 8 samtidige · 18 fejl til genforsøg · 620 fra cache`

Efter afslutning vises desuden antal netværkshentninger, cache/database-genbrug og genforsøg.
