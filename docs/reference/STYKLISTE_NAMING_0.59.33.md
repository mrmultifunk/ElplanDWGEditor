# Stykliste-navngivning 0.59.33

## Princip

- **Navn** er frit og kan altid redigeres manuelt.
- **Navneparametre** er strukturerede felter til filter/sortering og til at danne et navneforslag.
- **Navneassistent** er en guidet editor for de samme parametre; den har ikke sit eget separate datasæt.
- **Kategori** og **Variant** er frie ekstra biblioteksfelter og bør ikke gentage Type, System/serie, Opbygning eller Farve.

## Strukturerede felter

Type, Opbygning, Funktion/udførelse, System/serie, Montering, Farve og valgfri Ekstra tekst.

System/serie gemmes kanonisk, fx `LK FUGA SLIM`. I det genererede navn bruges den kortere læsevenlige form `FUGA SLIM`.

## Arbejdsgang

1. Redigér parametrene direkte i Stykliste-vinduet eller åbn Navneassistent.
2. Brug **Udfyld fra stykliste** hvis navn/komponenter skal genfortolkes.
3. Brug **Dan navn** hvis navneforslaget skal kopieres til Navn.
4. Redigér derefter Navn frit hvis nødvendigt; parametrene bevares som filterdata.
