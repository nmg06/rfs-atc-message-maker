# Catalogue de vols enrichi — 13 octobre 2026

Historical ADS-B profiles are not current scheduled flights. Airline/callsign/route
keys grew from 167,381 to 344,667 (2.059 times).
All 203,627 existing profile rows and 21,061 recent observed-route rows are preserved.
199,145 historical keys have a searchable duration. Other added keys
have unknown duration: never use partial timestamp spans as airborne flight times.

| Added quarter | New distinct keys |
|---|---:|
| 2025_Q4 | 50638 |
| 2025_Q3 | 30365 |
| 2025_Q2 | 19253 |
| 2025_Q1 | 31074 |
| 2024_Q4 | 29075 |
| 2024_Q3 | 16881 |

The separate DGCA Air India summer 2026 programme contains 1,573 seasonal variants,
785 distinct flight-number/route pairs, 770 flight numbers, and 1,988 published
movements from 37 pages. Validity ends on 24 October 2026. Local times, intermediate
stops and generic aircraft families are retained. 399 variants have a duration
from unambiguous paired domestic published times (scheduled block time, not an
observed airborne median). No foreign or overnight duration has been guessed.

Sources:
https://github.com/MrAirspace/aircraft-flight-schedules (ODbL 1.0, adsb.lol)
https://ourairports.com/data/ (public domain)
https://github.com/vradarserver/standing-data (CC0)
https://github.com/evansiroky/timezone-boundary-builder (ODbL 1.0)
https://public-prd-dgca.s3.ap-south-1.amazonaws.com/InventoryList/airOperation/certification/scheduled/domestic/AirIndiaLtd_SS_2026.pdf
https://public-prd-dgca.s3.ap-south-1.amazonaws.com/InventoryList/airOperation/certification/scheduled/domestic/AirIndiaflightSchedule-INT.pdf

DGCA facts: attribution to Directorate General of Civil Aviation, Government of
India. Public approved schedules do not prove actual operation. No licence grant
for the original PDFs is asserted; only normalised timetable facts are included.
Full build evidence, preserved-row checks and input hashes: aviation.report.json.
No account, network call or downloaded data is needed to search the bundled base.


## Reproduire l'ajout sans perdre les données

Le manifeste `finder/source-data/source-manifest-enrichment-2026-10-13.json` fige
les six fichiers Parquet par URL, taille et SHA-256. Les références sont celles de
`reference-snapshot-2026-09-30.zipdata`, déjà figées dans le dépôt.

1. Vérifier/télécharger les fichiers avec `scripts/download_release_dataset.py`.
2. Construire chaque trimestre avec `finder.importer` et un manifeste propre.
   Les données 2024 exigent `--legacy-2024` : l'immatriculation publiée identifie
   l'avion et l'absence d'état au sol interdit de calculer une durée complète.
3. Installer les faits DGCA avec `scripts/install_published_services.py` vers une
   nouvelle copie de la base précédente. `scripts/parse_dgca_schedules.py` permet
   de reconstruire les faits depuis les PDF, avec contrôle de la colonne physique
   arrivée/départ, des pages et des numéros de ligne.
4. Fusionner avec `scripts/merge_historical_profiles.py` vers un fichier neuf.
   La clé airline/callsign/origin/destination n'est ajoutée qu'une fois. Les anciennes
   lignes restent intactes, y compris leurs variantes historiques. Les contrôles
   EXCEPT, intégrité SQLite et clés étrangères précèdent la promotion.
5. Embarquer le candidat validé avec `python scripts/prepare_android.py --database
   build/enrichment-2026-10-12/final/aviation.sqlite`.

Le rapport en `android/bundled/aviation.report.json` contient le SHA-256 du candidat
et de la base précédente. Le trimestre 2024 Q2 a été téléchargé pour recherche,
mais **n'est pas intégré** : Q3/Q4 suffisent pour dépasser le ×2. Aucun nombre
n'est gonflé en comptant deux fois les variantes ou les observations quotidiennes.

La base ne fournit pas de portes vérifiées ni d'affectations ATC. Les pistes
OurAirports restent consultables dans Préparation au sol et nécessitent un choix
conforme au simulateur. Aucun gate/piste n'est inventé ou affecté automatiquement.
