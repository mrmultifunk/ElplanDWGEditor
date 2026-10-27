# GUI Foundation 0.53.0

## Formål

Version 0.53.0 er første kontrollerede GUI-modernisering. Fokus er de fire grundtrin: fælles UI-system, roligere hovedvindue, én samlet inspector og en kontekstuel værktøjslinje. Funktionaliteten og projektformatet skal være kompatibelt med 0.52.x.

## 1. Fælles UI-fundament

`qt_ui.py` indeholder standardmål og fælles hjælpefunktioner til panelmarginer, spacing, formularer, docks og inspector-header. `qt_theme.py` er fortsat den centrale light/dark/style-kilde. Målet er at undgå nye lokale hardcodede GUI-standarder i featurekode.

## 2. Roligere hovedvindue

Den faste værktøjslinje er reduceret til globale handlinger, der giver mening uanset valg. Symboler og Lag er venstre docks og kan tabbes/skjules. Tegnefladen er visuelt centrum. Dockplacering og størrelser huskes lokalt.

## 3. Samlet Egenskaber-inspector

Højre side har én `Egenskaber`-dock med en stack af kontekstuelle sider. Symbol-/objektegenskaber og kabeldata bruger samme plads i stedet for separate permanente højrepaneler. Valg af kabel viser kabelsiden, men aktiverer ikke kabeltegning. Større specialflows, fx PL-lederfordeling, forbliver dialoger.

## 4. Kontekstuel værktøjslinje

`Kontekst`-værktøjslinjen ændrer sig efter markering og aktiv arbejdsmodus. Et kabel giver hurtig adgang til kategori, global ruteføring og flere kabeldata; et symbol giver relevante symbolhandlinger; multivalg viser fælles handlinger; uden enkeltvalg vises generelle tegneværktøjer. Ændringer, der redigerer projektdata, bruger Undo/Redo.

## Layoutpersistens og portability

`qt_window_geometry` og `qt_window_state` er maskinlokale app-indstillinger. De følger ikke projektfiler eller `.elplancore`. Brugeren kan vælge **Vis → Nulstil panel-layout** for at gendanne standardarbejdspladsen.
