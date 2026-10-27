# PL-lederfordeling – grafisk arbejdsflade (0.49.1)

0.49.1 ændrer Lederfordeling fra primært tabelarbejde til en grafisk montagevisning.

## Grafisk PL-dåse

- Hvert placeret kabelben vises som en kabelkappe ved den konkrete indføring 1–6.
- Kabelkortet viser kabel-ID + ekstra mærkning, kabelspecifikation og Side A/Side B/ende.
- 3G/5G/7G-lederne vises som individuelle farvede lederstrenge gennem kabelhalsen og ind i dåsen.
- Ikke-fordelte aktive ledere vises med en fri lederende og `?`.
- Tildelte ledere tegnes som farvede kurver helt frem til deres samleklemme.

## Samleklemmer

PE, N, Fast fase L, de aktuelle tændinger, Reserve, Ikke tilsluttet og Ikke fordelt vises som grafiske klemmer. Klemmerne viser små farvede forbindelsespunkter for de ledere, der ligger i samme elektriske samling.

Tændinger viser den konkrete afbryderkanal fra 0.49.0, når den kan udledes, eksempelvis `TÆNDING a` med undertitlen `Kombi K01 · Modul 2 · krone tænding 1`.

Kravstatus markeres direkte på klemmen: korrekt, manglende, forkert kabelben, dublet eller manuel terminalkontrol.

## Arbejdsgang

1. Klik en farvet leder og klik derefter på en samleklemme, eller
2. træk lederen direkte til samleklemmen.

Under træk følger den farvede leder markøren og mål-klemmen fremhæves. `Esc` annullerer et igangværende træk.

Én fysisk leder kan fortsat kun have én funktion. Tildeling til en ny samling erstatter den gamle funktion på samme leder.

## Detaljevisning

De eksisterende tabeller er bevaret som præcis kontrolvisning, men er skjult som standard bag **Vis detaljer / tabel**. Dermed er den grafiske PL-dåse hovedarbejdsfladen.

Datamodellen er uændret fra 0.49.0, så eksisterende projekter og lederplaner kan åbnes uden migration.
