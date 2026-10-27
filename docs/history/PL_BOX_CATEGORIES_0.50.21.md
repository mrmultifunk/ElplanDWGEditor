# PL-dåse og kabelkategorier — 0.50.21

Kabelkategorien følger nu det fysiske kabelben helt ind i PL-dåsekonfiguratoren. `cable_legs_at_symbol()` medtager `cable_category` og `line_style`, mens dialogen får projektets aktuelle `cable_categories`, så brugerdefinerede kategorier kan opløses korrekt.

I **Kabelindføringer** vises kategori på tre niveauer: som samlet kategorioversigt, på hvert kabelben i listen og i detaljerne for den valgte indføring. Den grafiske PL-dåse viser desuden kategoriens navn samt dens farve og kontur på kabelmarkeringen.

PL-konfiguratoren ændrer ikke kategorien. Kategorien vedligeholdes fortsat centralt i kabelværktøjet/kategori-menuen, så der kun findes én sandhed for kategori, farve, kontur og lag.
