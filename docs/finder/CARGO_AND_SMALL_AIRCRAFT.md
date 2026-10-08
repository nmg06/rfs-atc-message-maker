# Cargo, petits avions et horaires publiés — 8 octobre 2026

La base livrée contient déjà des vols d’opérateurs cargo et des petits appareils.
Le catalogue de modèles est plus large que la couverture des vols : une entrée
ne garantit pas qu’un profil de vol soit disponible pour cet avion.

Le sélecteur PC et Android affiche désormais le nombre de **profils historiques
recherchables** par code ICAO. Les types avec des profils apparaissent en premier,
mais tous les modèles restent sélectionnables, y compris ceux affichant « Aucun
profil de vol ». Le nom Cessna 172 provient du catalogue RFS fourni ; la référence
ICAO utilisait auparavant le nom d’un constructeur sous licence, moins facile à
retrouver. Les variantes cargo/passagers partageant un code restent regroupées.

Le compteur concerne toute la base avant les autres filtres, la diversification
et les limites de résultats. Il ne représente ni des vols individuels ni un
programme actuel garanti. La recherche « FedEx » reconnaît également le nom
« Federal Express » de la référence dans les modes historique et routes récentes.

## Couverture vérifiée de la base livrée

Voir [COVERAGE_2026-10-08.json](COVERAGE_2026-10-08.json), obtenu en lecture seule
sur la base embarquée, SHA-256
`5df24e6a17b16458ba67c46d24b22f6178644ebdd3619ea0a5a713a351a2a1cb`.
La petite base de développement ignorée par Git est plus ancienne ; les paquets
PC et Android utilisent la base figée de `android/bundled`, pas cette copie.

| Recherche | Profils historiques recherchables avant les autres filtres |
| --- | ---: |
| Federal Express / FedEx (FDX) | 1 057 |
| United Parcel Service (UPS) | 1 034 |
| Cargolux (CLX) | 97 |
| Cessna 172 (C172) | 72 |
| Cessna 208 Caravan (C208) | 430 |
| Cirrus SR22 (SR22) | 8 |
| DHC-6 Twin Otter (DHC6) | 20 |
| Cessna 152 (C152) | 0 |

Le catalogue RFS fourni contient 63 entrées. Pour 54, le code ICAO associé
possède des profils recherchables, sans prouver la variante exacte. Les neuf
entrées restantes sont AN-225, 707-320C, 737-100, 747-200B, Concorde, DC-8-61,
C-5B, MD-81 et Tu-154M : elles n’ont aucun profil pour leur code, ou n’ont pas de
mapping pris en charge. Les appareils historiques demanderont des archives
explicitement datées plutôt qu’un faux programme contemporain.

Les profils détaillés concernent janvier à juin 2026. Le catalogue distinct de
21 053 routes observées va jusqu’au 7 octobre, mais ne connaît ni avion ni durée :
il n’est pas ajouté aux compteurs par appareil. Aucune donnée existante n’a été
remplacée ni supprimée pour cette amélioration.

## Pourquoi l’aviation légère reste moins couverte

La [source MrAirspace](https://github.com/MrAirspace/aircraft-flight-schedules)
précise que son traitement privilégie les vols commerciaux et que certains
petits aérodromes sont absents de sa résolution d’aéroports. Notre import
conservateur demande également un opérateur référencé, deux aéroports différents,
une trace de 15 à 1 200 minutes et plusieurs observations. Les vols privés sans
compagnie connue, les tours de piste et les avions rares sont donc moins bien
représentés. Un résultat absent ne signifie pas que l’avion ne vole pas.

Ne pas attribuer une fausse compagnie ou inventer des routes pour remplir le
catalogue. Pour enrichir l’aviation générale, une source dédiée et une résolution
plus précise des petits aérodromes sont nécessaires, dans un jeu de données
séparé permettant de vérifier l’identité, les coordonnées et la provenance.

## Sources officielles candidates, vérifiées le 8 octobre

- [Lufthansa Cargo](https://www.lufthansa-cargo.com/de/network/flugplan) propose
  un programme des 21 prochains jours, actualisé quotidiennement, avec exports
  CSV, XLSX et XML. Sa recherche comprend aussi des transports en camion : il
  faut distinguer ces services des vols lors d’un éventuel import.
- [Emirates](https://www.emirates.com/english/book/flight-schedules/) propose une
  recherche d’horaires. Cette page ne suffit pas à établir l’existence d’un
  téléchargement complet et réutilisable de tout son programme.
- [IATA SDEP](https://www.iata.org/en/services/data/passenger-traffic/schedule-data-exchange-program/)
  échange des programmes sous accord avec les compagnies contributrices. Ce
  programme n’est pas une base ouverte librement téléchargeable pour Flightdeck.

**Aucun de ces programmes officiels n’a été importé dans cette étape.** Avant de
les redistribuer dans l’APK, vérifier les droits de réutilisation et les données
réelles. Un prochain import devra conserver les profils ADS-B, dater chaque
programme et séparer `OBSERVED_PROFILE`, `OBSERVED_ROUTE` et `PUBLISHED_SCHEDULE`.
Il devra traiter les périodes de validité, fuseaux, partage de codes, services
au sol et doublons. Les données inconnues devront rester inconnues. Les fichiers
seront préparés au build pour conserver la recherche hors connexion.

## Vérification reproductible

```powershell
python scripts/audit_finder_coverage.py chemin/aviation.sqlite --output build/coverage.json
python -m unittest discover -s tests -v
python scripts/prepare_android.py
python -m unittest discover -s android/tests -v
```

Les régressions vérifient les compteurs face au moteur, les modèles sans profils,
le nom Cessna, l’alias FedEx dans les deux modes, les libellés anglais et
l’affichage Android. La base reste en lecture seule.
