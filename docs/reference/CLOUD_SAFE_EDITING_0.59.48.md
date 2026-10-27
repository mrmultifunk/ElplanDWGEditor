# Cloud-sikker projektredigering 0.59.57

Strukturerede projekter bruger `project.lock` som en lille heartbeat-lås. En aktiv
redigeringssession opdaterer låsen hvert 15. sekund. En anden computer tilbydes
skrivebeskyttet åbning, når en frisk fremmed lås findes. Gamle/crashede låse
betragtes som forældede efter tre minutter og kan overtages automatisk.

Projektfilen overvåges med indholdshash. Hvis OneDrive/Syncthing eller en anden
proces ændrer `project.elplan.json`, markeres status som `Konflikt`, normal Gem
stoppes, og brugeren kan vælge at indlæse den eksterne revision. Før den eksterne
revision erstatter den indlæste revision, oprettes en tidsstemplet backup i
projektets `backups/`-mappe med både in-memory Elplan-data og den indlæste CAD.

Statuslinjen viser `Lokal`, `Synkroniseret mappe` eller `Konflikt`.
