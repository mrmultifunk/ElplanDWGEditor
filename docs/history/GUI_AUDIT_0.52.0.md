# GUI-gennemgang 0.52.0

Denne gennemgang fokuserer på konsistens og vedligeholdelse frem for et redesign.

## Ændret nu

- Temaet er centraliseret i én theme engine, så nye widgets ikke skal have separate light/dark-regler spredt i hovedvinduet.
- Hover-kort er flyttet til et selvstændigt grafisk modul. Det reducerer koblingen mellem hover-visualisering og MainWindow.
- Kabelværktøjets tekst omkring ruteføring er gjort kontekstafhængig: ved et valgt eksisterende kabel står det nu eksplicit, at et skift mellem Fri/diagonal og Ortogonal konverterer geometrien ved **Anvend ændringer**, og at Undo kan gendanne den.
- Hurtige zoombevægelser er gjort roligere ved at samle tunge visuelle rebuilds.

## Kontrolleret

- Light/dark/system bruger fortsat samme tekniske semantik for kabel-, leder-, Wago- og terminalfarver.
- PDF/print og PL-rapport er fortsat uafhængige af dark mode.
- Sidepanelerne kan fortsat tabbes: Symboler/Lag til venstre og Egenskaber/Kabelværktøj til højre.
- Primære handlinger bruger fortsat `primaryButton`, destruktive handlinger `dangerButton` og sekundære handlinger `quietButton`.
- Tabeller og combo/spin controls beholder de fælles hover/focus/disabled states og de deterministiske chevrons.

## Næste sikre kandidater

1. Flyt `PLBoxDialog`, `PLBoxDiagramWidget` og `PLWiringDiagramWidget` til et dedikeret `qt_pl.py` modul.
2. Flyt BOM/artikel-dialoger til `qt_bom.py`/`qt_articles.py`.
3. Flyt fil-/recent-project workflows ud af `MainWindow` til en lille service/controller.
4. Profilér scene-hit-testing og kabel-overlays på meget store projekter før yderligere mikrooptimering.

De punkter er bevidst ikke tvunget ind i samme version; ændringerne skal fortsat kunne regressionstestes i små trin.
