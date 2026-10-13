# Enrichissement du Flight Finder — 6 octobre 2026

La candidate enrichit l’historique avec Q1 et Q2 2026 de la même source
d’observations. Les données restent embarquées et consultables hors connexion.
Le schéma SQLite, les critères de recherche et le transfert « Utiliser ce vol »
restent compatibles avec Windows et Android.

## Choix retenu

[MrAirspace](https://github.com/MrAirspace/aircraft-flight-schedules/releases)
publie des traces ADS-B transformées en vols. Le dernier trimestre public vérifié
le 6 octobre reste Q2 2026, publié le 11 juillet. Q1, publié le 11 avril, ajoute
un historique hivernal réel ; il ne rend pas la base plus récente.

Les deux fichiers ont été téléchargés sans compte et vérifiés :

| Entrée | Taille | SHA-256 |
| --- | ---: | --- |
| Q1 2026 | 840 340 093 octets | `12ec161c7f1739934053d743625bb48e86b3785c3fcb0549b0e08ae93b1199ce` |
| Q2 2026 | 911 949 077 octets | `2bef8bc41b9c5fc0708271859362a10d9a703a15ad57863e7e934bf3738226db` |

La fenêtre historique de cette reconstruction est explicitement de **181 jours**
par rapport à la dernière observation des sources. Le comportement générique de
l’importeur reste de 90 jours si aucune option n’est fournie. Le filtrage par
trimestre de départ retire les chevauchements des Parquet.

La fraîcheur reste liée aux dates des vols : la date de reconstruction, le
6 octobre, n’est jamais utilisée comme date d’observation. Les vols historiques
ne deviennent pas des horaires commerciaux actuels.

## Contrôles de qualité

Les mêmes validations s’appliquent aux deux trimestres :

- aéroports identifiés de manière conservatrice, compagnie connue et codes valides ;
- déduplication par avion transpondeur, minute UTC de départ et paire d’aéroports ;
- au moins trois observations pour conserver un profil ;
- au moins trois traces complètes, dont les deux extrémités sont au sol, pour une durée exploitable ;
- médiane et percentiles calculés uniquement sur ces traces complètes ;
- modèle d’avion réellement observé, avec liste des types et type modal en cas de variation.

Aucune durée, aucun avion, aucun numéro commercial ni horaire de service n’est
inventé. Les numéros obtenus à partir d’un callsign gardent leur provenance
« dérivé du callsign » ; ils ne constituent pas la preuve d’un numéro commercial.
Les durées restent des durées estimées en vol, sans temps de roulage. Les pistes
de référence ne sont pas les pistes réellement utilisées.

La base Q2 précédente est conservée dans
`build/data-audit-2026-10-06/aviation-Q2-before.sqlite` avec le SHA-256
`4a2de0a7a2a9626ee8bb6d458baa2ec52820c5fa068e6a9ae4a7a6f91fb28b57`.

## Mesures de la candidate finale

La comparaison finale validée est enregistrée dans
`docs/data-enrichment-2026-10-06.json` :

| Métrique | 0.4.2 (Q2) | 0.4.3 finale (Q1 + Q2) | Évolution |
| --- | ---: | ---: | ---: |
| Observations retenues | 4 078 484 | 7 891 468 | +93,5 % |
| Profils totaux | 135 554 | 203 627 | +50,2 % |
| Durées observées (≥ 3 traces complètes) | 59 552 | 92 952 | +56,1 % |
| Profils RFS avec durée observée | 44 231 | 68 603 | +55,1 % |
| Durées estimées héritées conservées | 76 002 | 73 213 | 4 093 promues en observées |
| Profils recherchables Finder | 135 554 | 166 165 | +22,6 % (+30 611) |
| Clés de routes (callsign/origin/dest) | 114 157 | 167 381 | +46,6 % (+53 224) |
| Routes recherchables perdues | - | 0 | 0 perte |
| Taille SQLite brute | 94 892 032 o | 134 565 888 o | 134,6 Mo (compacté VACUUM) |
| Taille bundle gzip | 24 479 491 o | 33 800 294 o | 33,8 Mo (+9,3 Mo) |
| Intégrité & clés étrangères | ok / 0 erreur | ok / 0 erreur | Validé |

L'overlay conservateur (`scripts/apply_legacy_estimates_overlay.py`) préserve 100 % des
anciennes routes de la 0.4.2 sans inventer de formule : 71 105 profils sur clés exactes
et 2 108 profils de routes dont le type d'avion modal a évolué entre Q2 et Q1+Q2.
Leur provenance reste strictement `ESTIMATED_DISTANCE_HEURISTIC`, affichée en toute
transparence dans l'interface sans faux percentiles. 4 093 anciennes estimations ont
été promues en durées réelles observées grâce à l'historique étendu de 181 jours.


## Reconstruction reproductible

Les petites références du 30 septembre sont figées dans
`finder/source-data/reference-snapshot-2026-09-30.zipdata` (archive ZIP, 5,35 Mo).
Le manifest versionné donne les URL d’origine, dates de récupération, tailles et
SHA-256 de chaque entrée. L’archive évite qu’une modification ultérieure des CSV
distants change silencieusement les données d’entrée.

```powershell
python -m pip install -r requirements-etl.txt
python scripts/rebuild_historical_finder.py --cache build/finder-inputs --output build/finder-rebuild/aviation.sqlite --download
python -m unittest tests.test_finder_historical_etl tests.test_finder.ImporterTests -v
```

Le téléchargement est une action de construction explicite. Avec un cache
complet, omettre `--download`. Un cache modifié est refusé et conservé. Les Parquet
totalisent 1,75 Go et l’agrégation peut utiliser des fichiers temporaires sur
disque ; prévoir plusieurs Go libres. DuckDB utilise par défaut 512 Mo et un
thread dans ce script, réglables avec `--memory-mb` et `--threads`.

L’importeur écrit un fichier `.building`, effectue les contrôles SQLite, puis
remplace uniquement la sortie demandée. Une sortie candidate séparée est
recommandée avant de remplacer un ensemble distribué. La logique et les entrées
sont reproductibles ; `built_at` et les métadonnées de reconstruction peuvent
changer le hash binaire d’un nouveau build.

Pour comparer deux ensembles en lecture seule :

```powershell
python scripts/compare_finder_snapshots.py --before build/data-audit-2026-10-06/aviation-Q2-before.sqlite --after build/finder-rebuild/aviation.sqlite --report build/finder-rebuild/comparison.json
```

## Licences et attributions

Les observations sont dérivées de [adsb.lol](https://github.com/adsblol) par
MrAirspace, sous [ODbL 1.0](https://github.com/MrAirspace/aircraft-flight-schedules/blob/main/LICENSE-ODbL.txt).
La base dérivée et ses instructions de reconstruction sont distribuées avec cette
licence et leurs attributions. Le champ `AC_Type_Detailed` provenant de
l’enrichissement adsbdb reste exclu.

Les références [OurAirports](https://ourairports.com/data/) sont dans le domaine
public. Les références compagnie et modèle de
[Virtual Radar Server](https://github.com/vradarserver/standing-data/blob/main/LICENSE)
sont sous CC0 1.0. Les limites de fuseaux timezone-boundary-builder /
OpenStreetMap sont sous ODbL ; les versions des dépendances sont enregistrées
dans le rapport. Ces licences de données ne remplacent pas la licence du code.

## Autres sources auditées, non ajoutées aux profils

[CatchFlights](https://github.com/catchflights/routes) publie au 6 octobre un
export de 127 168 routes observées sous ODbL, d’environ 2,32 Mo compressés.
Un filtre conservateur (une seule paire candidate, au moins trois jours et trois
observations, confiance publiée supérieure ou égale à 0,95, deux aéroports connus,
trajet direct) conserve 21 130 routes, dont 3 542 clés absentes de tous les profils
Q2. Ce sont des routes sans durée ni modèle d’avion. Les colonnes compagnie et
numéro de vol sont vides dans cet export ; un préfixe reconnu reste une déduction.
Les dates de première et dernière preuve ne sont pas le départ et l’arrivée
d’un même vol. Cette source pourra alimenter un catalogue distinct de routes,
mais elle n’est pas mélangée aux profils complets de cette candidate.

Le référentiel de routes Virtual Radar Server contient 620 393 lignes. Après
normalisation des liaisons directes avec codes connus, 495 070 clés sont absentes
des profils Q2. Il n’a ni date d’observation ni durée ni avion : ces références
ne sont pas présentées comme autant de vols historiques observés.

OpenFlights est ancien (routes arrêtées en 2014). Les jeux ouverts OpenSky
audités sont également plus anciens que Q2 ou nécessitent un accès différent.
Les rapports BTS américains peuvent fournir des vols déclarés plus récents,
mais demanderaient un import et une provenance propres ; ils ne fournissent pas
directement les mêmes callsigns et modèles. Aucun de ces ensembles n’est injecté
dans le mode « vols observés » actuel.

