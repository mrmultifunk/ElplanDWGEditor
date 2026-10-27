# Vedligeholdelses-/arkitekturpas 0.54.3

## Formål

0.54.3 fortsætter den gradvise opdeling af Qt-applikationen uden at omskrive fungerende domænelogik eller ændre projektformatet. Fokus er lav regressionsrisiko, tydelige featuregrænser og mindre arbejde ved almindelig opstart.

## Ny modulopdeling

- `qt_articles.py` ejer artikelimportguide, artikelredigering, prisdialog, produktpreview, artikelvælger, styklisteeditor og BOM-manager samt LK-synkroniseringstråden.
- `qt_pl_box.py` ejer PL-kabelindføringsdiagram, lederfordelingsdiagram og PL-dåsekonfigurator.
- `qt_widgets.py` ejer de fælles QComboBox/QSpinBox/QDoubleSpinBox/QFormLayout/QDialogButtonBox-varianter samt rolle-, dialogstørrelses- og farveknaphjælpere.
- `qt_app.py` er reduceret fra 10.788 linjer i 0.54.2 til ca. 6.000 linjer og står i højere grad for hovedvindue og workflow-orkestrering.

## Lazy loading / startup

`qt_articles` og `qt_pl_box` importeres ikke på modulniveau i `qt_app.py`. De indlæses lokalt, når brugeren åbner Artikler/BOM, kabelartikelvælgeren eller PL-dåsekonfiguratoren. Dermed undgår normal opstart at indlæse bl.a. artikel-netværkskode og flere tusinde linjer dialog-/paint-kode, før funktionerne faktisk bruges.

Ubrugte imports, der fulgte de flyttede features, er fjernet fra `qt_app.py`.

## Regression og arkitekturværn

Eksisterende source-contract-tests peger nu på det modul, der faktisk ejer funktionen. Nye tests kontrollerer:

- at `qt_app.py` forbliver under 6.200 linjer,
- at `qt_articles.py`, `qt_pl_box.py` og `qt_widgets.py` findes,
- at artikel- og PL-modulerne ikke top-level-importeres af `qt_app.py`,
- at featuremodulerne ikke importerer `qt_app` tilbage.

## Projektformat

Ingen migration. 0.54.3 gemmer samme datastrukturer som 0.54.2; kun versionsstemplet opdateres ved næste gemning.
