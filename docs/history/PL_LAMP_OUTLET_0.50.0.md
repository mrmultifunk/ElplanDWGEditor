# Lampesteds-/lampeudtagseditor 0.50.0

0.50.0 redesigner PL-dåsens **Lederfordeling** efter de fysiske klemmer på almindelige lampeudtag. Målet er, at montøren kan aflæse installationen som et lampeudtag i stedet for som abstrakte funktionsbokse.

## Lampeudtagstyper

Lampestedet har nu feltet `lamp_outlet_type` med tre visninger:

- `generic` — **Generisk PL / samleklemmer**: PE, N, fast L og én tændingsklemme pr. tilhørsforhold.
- `lk_classic` — **LK klassisk lampeudtag**: fysisk klemrække **N · L · PE · M1 · M2**. M1 og M2 følger de første to tændingstilhørsforhold. Flere tændinger markeres som manglende fysisk klemme.
- `wiser_dimmer` — **LK Wiser / dæmpbar**: fysisk klemrække **PE · N · styret/dæmpet udgang · L**. Visningen har én fysisk styret udgang; yderligere tændingstilhørsforhold markeres som ikke understøttet af den valgte klemrække.

Visningstypen kan ændres uden at slette `pl_box_wiring`. Lederplanen gemmer fortsat de generiske elektriske funktioner (`pe`, `n`, `l`, `switch:a` osv.); udtagstypen bestemmer kun, hvordan de fysiske klemmer præsenteres og valideres visuelt.

## Grafisk arbejdsgang

1. Vælg eller træk en farvet leder fra kabelindføringen.
2. Slip den på den mærkede fysiske klemme i lampeudtaget.
3. Kontroller status ved tændingsklemmen og de eksisterende tilhørsforhold.

Kabel-ID, ekstra kabelmærkning, kabeltype og Side A/Side B vises fortsat ved indføringen. Lederfarverne er de eksisterende 3G/5G/7G-profiler.

**Reserve**, **Ikke tilsluttet** og **Frigør / ikke fordelt** er nu små sekundære parkeringsfelter og ligner ikke fysiske terminaler.

## Tilhørsforhold og afbryderkanaler

Eksisterende `association_channels` og tændingskrav fra 0.49.0 bruges uændret. En M1/M2- eller Wiser-udgang kan derfor vise den konkrete tænding og den konkrete afbryderkanal, fx `a · Kombi K01 · Modul 1 · 1-polet`.

Hvis den valgte lampeudtagstype har færre fysiske tændingsklemmer end lampestedets tilhørsforhold, vises en rød advarsel direkte i grafikken. Programmet gætter ikke på en alternativ fysisk klemme.

## Tabel / avanceret

De eksisterende tabeller med forventede tændinger og detaljeret lederliste er bevaret. De er skjult som standard og åbnes med **Vis tabel / avanceret**. Knappen skifter til **Skjul tabel / avanceret**, når panelet er åbent.

## Kompatibilitet

Eksisterende 0.49.x-projekter får automatisk `lamp_outlet_type = generic`. `pl_box_entries`, `pl_box_wiring`, kabel-UID'er og tilhørsforhold ændres ikke. Når en bruger vælger en anden udtagstype og trykker Anvend/OK, gemmes kun det nye typefelt sammen med den eksisterende PL-konfiguration.
