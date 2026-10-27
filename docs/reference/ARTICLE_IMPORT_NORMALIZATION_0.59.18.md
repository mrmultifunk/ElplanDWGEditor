# Artikelimport-normalisering 0.59.18

0.59.18 flytter datakvalitetsreglerne ind i selve LK/Schneider-importen. Formålet er, at en senere katalogsynkronisering ikke genintroducerer de fejl, som blev fundet i kernedata-auditen fra 0.59.17.

## Pipeline

1. **Discovery** accepterer kun plausible produktreferencer. Billedvarianter og webaktiver (`_1`, `_2`, `_web`, `_angle`, `_image`, brochure-/appikoner osv.) bliver ikke planlagt som produkter.
2. **Parser** foretrækker felter fra tilstødende HTML-noder. Et eksplicit `vnr` er autoritativt for varenummeret og beskytter mod at en variant-/nabopost overtager identiteten.
3. **Normalisering** kører før cache/database. Farve, modul og beskrivelsesspacing valideres konservativt.
4. **Merge** normaliserer også eksisterende LK-poster. Kendte sikre artefakter fjernes, mens brugerens egne/manuelle artikler ikke ændres.
5. **Cache** bruger formatversion 2, så gamle 0.45.x/0.59.17-produktposter ikke genbruges urenset.

## Farve

- `color` er den stabile, normaliserede farve/finish.
- Den dedikerede producentværdi kan bevares som `color_raw`.
- Webtekst, kabellængder og konfigurationer som *uden afdækning* er ikke farver.
- Materialeord som stål/kobber antages ikke at være farver i gamle poster uden finish-kontekst.
- En ny/ukendt producentfarve må hellere ligge som rå kildedata end blive gættet til en eksisterende farve.

## Modul

- `module_size` accepterer halve moduler i realistisk område samt dokumenterede Resi9-rækker `1–4 × 13M/18M`.
- `451200M`, mål som `600×400M`, kabellængder og lignende afvises.
- Rå afviste værdier kan bevares som `module_size_raw`.
- Beskrivelsestekst må kun bruges ved entydig modulkontekst (`mod`, `modul` eller stort `M`). Lille `m` behandles som meter.

## Datatab

Normaliseringen omskriver ikke producentens produktnavn semantisk. Beskrivelser får kun mekanisk whitespace/`·`-oprydning. Tvivlsomme facetværdier fjernes fra facetfeltet i stedet for at blive gættet; relevante rå producentværdier kan fortsat bevares separat.
