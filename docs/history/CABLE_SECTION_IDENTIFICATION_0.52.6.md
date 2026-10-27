# Kabelafsnit – tydelig identifikation (0.52.6)

Når et eksisterende kabel redigeres via **Ruteføring pr. afsnit**, sammensættes navnet på hver fysisk tilslutning nu af både `gruppe/kreds` og `mærkning`, hvis de er udfyldt.

Eksempel: `G11 · UDTAG-SOVE → G11 · UDTAG-GANG-VÆRELSER`.

Det gør afsnitsvælgeren, højrekliksmenuen og statuslinjen entydige, selv når flere lampesteder ligger på samme gruppe. Hvis kun gruppe eller mærkning findes, vises kun det tilgængelige felt. Projektformatet er uændret.
