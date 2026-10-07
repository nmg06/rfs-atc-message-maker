# Sources figées du Flight Finder — 6 octobre 2026

Ce dossier sert uniquement à reconstruire la base. L’application embarque la
SQLite compressée ; elle ne télécharge aucun de ces fichiers pendant son utilisation.

Le manifest contient les URL d’origine, tailles, dates de récupération et SHA-256
des deux trimestres MrAirspace (Q1 et Q2 2026) et des références utilisées le
30 septembre 2026. Les Parquet ne sont pas ajoutés au dépôt : leurs tailles sont
840 340 093 et 911 949 077 octets.

`reference-snapshot-2026-09-30.zipdata` est une archive ZIP contenant les petites
références CSV exactes et la licence ODbL. Son extension évite de la confondre
avec une application à installer. SHA-256 :
`d0b44c0ff83dee89eb606c2ad227780733767b7ea75a6cc512a7e1587698f1e6`.

- [MrAirspace / aircraft-flight-schedules](https://github.com/MrAirspace/aircraft-flight-schedules) :
  observations dérivées d’ADS-B adsb.lol, [ODbL 1.0](https://github.com/MrAirspace/aircraft-flight-schedules/blob/main/LICENSE-ODbL.txt).
- [OurAirports](https://ourairports.com/data/) : aéroports, pistes, pays et régions,
  domaine public selon les conditions publiées.
- [Virtual Radar Server standing data](https://github.com/vradarserver/standing-data) :
  compagnies et modèles, [CC0 1.0](https://github.com/vradarserver/standing-data/blob/main/LICENSE).
- Les fuseaux viennent de timezone-boundary-builder / OpenStreetMap via
  timezonefinder et ses dépendances figées dans `requirements-etl.txt` (ODbL).

La base dérivée conserve ODbL 1.0 et les attributions. Le code de l’application
garde sa propre licence. `AC_Type_Detailed`, enrichi à partir d’adsbdb, reste
exclu de l’import.

Pour reconstruire sans remplacer immédiatement une base livrée :

```powershell
python -m pip install -r requirements-etl.txt
python scripts/rebuild_historical_finder.py --cache build/finder-inputs --output build/finder-rebuild/aviation.sqlite --download
```

`--download` concerne uniquement les deux gros fichiers de construction manquants.
Pour un cache déjà préparé, omettre ce drapeau. Tous les fichiers sont vérifiés
avant l’agrégation. Un fichier existant ne correspondant pas au manifest est
refusé et conservé.

La fenêtre est explicitement de 181 jours par rapport à la dernière observation
des sources, afin de couvrir Q1 et Q2 ; le filtrage par trimestre élimine leurs
chevauchements. La dernière observation reste au 30 juin 2026. La date de
reconstruction n’est pas présentée comme une observation récente.

