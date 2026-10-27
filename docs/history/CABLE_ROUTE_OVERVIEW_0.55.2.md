# Kabeltræk / ruteforløb — 0.55.2

## Formål
Give et hurtigt installations-overblik oven på 0.55-modellen, hvor hvert `CablePlacement` er ét fysisk kabel, uden at introducere en ny vedligeholdelseskrævende kabelstreng-model.

## Afledt netværk
`cable_routes.py` bygger ved behov en multigraf pr. `circuit_id`. Symboltilslutninger er noder og fysiske kabler er kanter. Gruppetavle/fordelingstavle foretrækkes som rod. Hvis en gruppe ikke har en tavle, vælges et fysisk endepunkt deterministisk. Frie kabelender får syntetiske noder alene i visningen.

Hver sammenhængende komponent bliver sit eget delnet. Trævisningen viser hver fysisk kabelkant én gang. Ring-/sløjfeforbindelser markeres med `↻` i stedet for at rekursere uendeligt. Listevisningen genererer læsbare rod-til-ende-ruter og gentager bevidst fælles stræk ved forgreninger.

## Qt-integration
`qt_cable_routes.py` indeholder en modeless dialog med Træ/Liste, søgning, gruppefilter, kopiering og navigation til plantegningen. `qt_app.py` lazy-loader dialogen, så den ikke påvirker normal startup. Klik på en rute vælger de relevante eksisterende `CableItem`-objekter; der oprettes ingen særlige highlight-geometrier eller projektdata.

## Længder
Hvis hovedvinduet kender meter pr. tegneenhed, vises summeret fysisk rutelængde. Ellers vises `—`; overblikket kræver ikke kalibrering for at fungere.

## Projektformat
Ingen nye felter. `circuit_id`, kabel-UID, kabeltype og `symbol_connections` fra 0.55-modellen er eneste input.
