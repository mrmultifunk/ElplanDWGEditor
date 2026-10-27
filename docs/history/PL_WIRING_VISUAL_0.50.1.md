# PL-lederfordeling 0.50.1 – ekstern klemrække

0.50.1 er en ren visuel/ergonomisk forbedring af **Lederfordeling** i PL-loftdåse-konfiguratoren. Datamodellen er uændret.

## Nyt hovedlayout

- Selve PL-dåsen ligger til venstre og viser de seks kabelindføringer samt de frie lederforløb.
- Lampeudtaget/klemrækken ligger som et separat grafisk objekt til højre for dåsen.
- Lederne løber derfor ud af dåsen og direkte til en tydeligt mærket klemmerække i stedet for at forsvinde ind under en terminalblok midt i dåsen.

## Tydeligere ledere

- Fordelingslederne tegnes ca. 6 px brede i normal tilstand.
- Der tegnes en lys kontrastkant under lederne, så krydsende forløb kan adskilles.
- Hvid leder får mørk kontur.
- Gul/grøn PE tegnes grøn med gul stiplet markering.
- Valgt leder bliver endnu tykkere og får en diskret cyan fokusmarkering.
- Lederpunkterne ved kabelindføringerne er større og har et større klik-/træk-område.

## Flere ledere på samme klemme

Når flere ledere har samme funktion, f.eks. flere PE- eller N-ledere, får hver leder sit eget **grafiske indgangspunkt** langs venstre side af den samme klemmerække. Det er en dokumentationsvisning og ikke en angivelse af produktets præcise antal skrue-/fjederhuller. Formålet er at gøre det entydigt, hvilke farvede ledere der ender på hvilken elektrisk klemme.

## Interaktion

Klik → klik og drag-and-drop er uændret: vælg/træk en farvet leder og klik/slip på hele den ønskede klemmerække. Reserve, Ikke tilsluttet og Frigør/ikke fordelt er fortsat sekundære mål og ligger inde i PL-dåsen.

## Kompatibilitet

Ingen projektdata ændres. 0.50.0-projekter kan åbnes direkte, og de eksisterende lederfunktioner gengives blot med det nye layout.
