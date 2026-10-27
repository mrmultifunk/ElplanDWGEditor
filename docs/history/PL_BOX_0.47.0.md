# PL-loftdåse – 0.47.0

## Formål
Give montøren en fysisk, grafisk oversigt over hvilke kabler der går ind og ud af en PL-loftdåses seks kabelindføringer.

## Åbning
- Dobbeltklik på et lampested (`light_connection`).
- Eller vælg lampestedet og tryk **Konfigurer kabelindføringer…** i Egenskaber.

## Fysisk model
Indføring 1–3 er øverst og 4–6 nederst. Et kabel ved et endepunkt bruger ét kabelben. Et kabel der passerer gennem lampestedet bruger to: Side A og Side B. Samme fysiske kabel-ID kan derfor korrekt optræde i to indføringer.

## Dialog
Venstre side er en nytegnet Qt-vektorillustration af PL-dåsen. Højre side viser alle faktiske kabelben ved lampestedet, deres kabel-ID, specifikation, side og aktuelle port.

Handlinger:
- træk kabelben til en indføring
- vælg kabelben + **Placér i valgt indføring**
- **Fjern fra indføring**
- **Fordel automatisk** efter kabelretning
- **Ryd placeringer** uden at slette kabler
- valgfri note pr. indføring
- **Anvend**, **OK**, **Annuller**

## Robusthed
PL-referencer peger på kabel-UID, kabelside og forbindelsespunkt. Ved ændringer i kabelruten forsøges forbindelsen genfundet ud fra kabel-UID + side. Referencer til slettede kabler filtreres ved visning og gemning.

## Begrænsning i 0.47.0
Versionen dokumenterer kabelindføringer, ikke de interne L/N/PE-/WAGO-lederforbindelser i dåsen.
