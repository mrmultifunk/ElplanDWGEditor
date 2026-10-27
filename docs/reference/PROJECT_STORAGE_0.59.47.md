# Projektlager 0.59.57

Elplan er fortsat local-first. Projektlageret kan slås fra og programmet fungerer da som før.
Et synkroniseret projektlager er en almindelig lokal mappe, fx OneDrive, som OneDrive-klienten selv synkroniserer.

Ny projektstruktur:

```
Projekt/
  project.elplan.json
  project-info.json
  drawing/
    plantegning.dwg
  backups/
  exports/
```

Eksisterende projekter migreres ved at kopiere projektdata og CAD til den nye struktur. Originalerne slettes ikke.
