# PL-lederfordeling 0.50.4

## Mål

Forenkle grafikken for ikke-tilsluttede ledere og begynde at tage højde for fysiske begrænsninger i lampeudtaget.

## Ændringer

- De tre bokse **Reserve**, **Frigør / ikke fordelt** og **Ikke tilsluttet** er fjernet fra den grafiske visning.
- Ledere med disse funktioner vises nu som **løse ender** i PL-dåsen med små markører (`R`, `X`, `?`).
- **LK Wiser / dæmpbar** har nu en indbygget terminalgrænse på **maks. 2 ledere pr. terminal**.
- **LK klassisk lampeudtag** har nu en indbygget terminalgrænse på **maks. 4 ledere pr. terminal**.
- Hvis antallet af ledere på en terminal overskrider grænsen, vises der automatisk en **Wago-muffe i PL-dåsen**, og terminalkortet markeres med **via Wago i PL-dåse**.
- Wago-mufferne er grafiske/hjælpende og genbruger de eksisterende funktions-id'er (`pe`, `n`, `l`, `switch:x`). Datamodellen er derfor fortsat uændret.

## Datamodel

Ingen nye felter. `pl_box_entries`, `pl_box_wiring` og `lamp_outlet_type` er uændrede.
