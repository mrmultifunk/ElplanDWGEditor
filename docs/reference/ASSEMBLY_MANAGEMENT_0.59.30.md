# Stykliste-/montagehåndtering 2.0 — 0.59.30

## Datamodel

En montage har stabilt `id`, `name`, `description`, `category`, `variant`, `tags`, `notes` og `items`.

Hver komponent har `article_no`, `qty` og kan desuden have `role`, `optional` og `included`. Faste komponenter er altid aktive. En valgfri komponent med `included=false` bevares i biblioteket, men indgår ikke i BOM, projektkontrol, sporbarhed eller styklistepris.

## UX

Styklistebiblioteket understøtter søgning, kategorifilter, filter på anvendte montager, styklistepris og direkte fremhævning af anvendelser på plantegningen. Editorens montagepreview viser faste/valgfrie/aktive komponenter og den økonomiske påvirkning i aktuelt projekt.
