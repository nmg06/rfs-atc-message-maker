# DATA_SOURCES.md — Sources de données du Flight Finder

Version 0.1 — vérifications faites le 2026-09-30 (recherche web + lecture de pages).

## 0. Comment lire ce document

Chaque affirmation porte un niveau de confiance :

- **[V]** lu directement sur la page officielle de la source (README, page de licence, doc).
- **[T]** rapporté par une source tierce (projet GitHub, article, comparateur). À reconfirmer avant d'en dépendre.
- **[?]** non vérifié. Ne pas en faire une hypothèse d'architecture.

Limites de cette vérification, à connaître :

1. Aucun dataset n'a été téléchargé. Les noms de colonnes de MrAirspace viennent du README, pas d'un `DESCRIBE` sur un vrai fichier Parquet. **La toute première tâche de Codex est de le faire** (voir CODEX_TASK.md, étape 1).
2. Les conditions d'utilisation complètes de Rortos, AeroDataBox (Article 5), FlightAware et adsbdb n'ont pas été lues en entier. Seuls des extraits ou des citations de tiers ont été vus.
3. Les prix des API changent vite et diffèrent d'une page à l'autre (voir §10 et §11).

Ceci n'est pas un avis juridique.

---

## 1. Vue d'ensemble

| Source | Rôle dans le projet | Licence | Redistribuable ? | Phase |
|---|---|---|---|---|
| OurAirports | Aéroports, pistes, pays, continents, fréquences | Domaine public | Oui | 1 |
| MrAirspace aircraft-flight-schedules | Vols observés (ADS-B), cœur du moteur | ODbL 1.0 | Oui, mais share-alike | 1 |
| VRS standing-data (Virtual Radar Server) | Compagnies, validation callsign→route, modèles | CC0 | Oui | 1 |
| timezonefinder + timezone-boundary-builder | Fuseau IANA de chaque aéroport | Code MIT, données ODbL | Données : share-alike | 1 |
| DuckDB | Moteur ETL sur Parquet | MIT | n/a (outil) | 1 (ETL) |
| OpenFlights | Fallback historique uniquement | ODbL | Oui, share-alike | Non retenu en Phase 1 |
| catchflights/routes | Routes dérivées d'ADS-B (raccourci possible) | ODbL | Oui, share-alike | Optionnel, non fiable à ce stade |
| Flight Plan Database | Génération de route avec waypoints après sélection | CGU propres, simulation uniquement | Non | 2 |
| AeroDataBox | "Live / Today" optionnel | Commercial, CGU propres | Non (cache encadré) | 3 |
| FlightAware AeroAPI | "Live / Today" optionnel | Commercial, palier Personal restreint | Non | 3 |
| adsbdb | À NE PAS copier dans la base | CGU restrictives [T] | Non | Exclu |
| Rortos / RFS | Liste des avions/liveries RFS | Propriétaire | Non | Saisie manuelle vérifiée |

---

## 2. OurAirports

**Fournit.** Aéroports (`airports.csv`), pistes (`runways.csv`), fréquences, navaids, pays, régions. Le dictionnaire de données documente notamment : `ident`, `icao_code`, `iata_code`, `type`, `latitude_deg`, `longitude_deg`, `elevation_ft`, `continent`, `iso_country`, `iso_region`, `municipality`, `scheduled_service`. Pour les pistes : `le_ident`/`he_ident`, longueur, largeur, surface, `lighted`, `closed`, caps vrais (`*_heading_degT`), seuils décalés. [V]

**Pas de colonne fuseau horaire.** Le dictionnaire de données ne contient aucun champ timezone. Il faut donc dériver l'IANA à partir des coordonnées (voir §5). [V]

**Fraîcheur.** Export régénéré chaque nuit. La page de téléchargement affichait des fichiers modifiés le 28 septembre 2026. GitHub ne met à jour la date que si le contenu change. [V]

**Licence.** Domaine public, sans garantie d'exactitude ni d'aptitude à l'usage. Dépôt : `davidmegginson/ourairports-data`. [V]

**Taille.** `airports.csv` ≈ 12,7 Mo, `runways.csv` ≈ 4,0 Mo, `airport-frequencies.csv` ≈ 1,3 Mo (au 28 sept. 2026). Environ 86 000 aéroports et 48 000 pistes selon un listing tiers. [V]+[T]

**Import.** Téléchargement HTTP des CSV depuis `https://davidmegginson.github.io/ourairports-data/` (ou clone du dépôt). Aucune clé. Rafraîchissement mensuel suffisant.

**Limites.**
- Base communautaire : erreurs possibles (pistes fermées non à jour, codes manquants).
- `continent` est défini par aéroport ("principalement situé"). Les cas limites (Russie, Turquie, Caucase, Kazakhstan, Égypte/Sinaï) doivent être testés et corrigés par une table `continent_overrides` maintenue par nous. [V]+hypothèse à tester
- Les codes IATA ne sont pas garantis uniques (aéroports fermés). Préférer l'ICAO comme clé métier.
- Les pistes listées sont les pistes **existantes**, jamais la piste **en service**.

**Redistribuable.** Oui, sans condition.

**Verdict.** Source de référence pour aéroports et pistes. Retenue.

---

## 3. MrAirspace / aircraft-flight-schedules

URL : `https://github.com/MrAirspace/aircraft-flight-schedules`

**Fournit.** Un fichier Parquet par trimestre (à partir de 2024), construit à partir des positions ADS-B du réseau adsb.lol. Colonnes documentées dans le README : `ICAO_Hex`, `Reg`, `AC_Type`, `AC_Type_Description`, `AC_Type_Detailed` (nouveau depuis 2026 Q1, distingue les variantes passagers/cargo/VIP pour les avions commerciaux), `Airline` (code ICAO dérivé du callsign), `Callsign`, puis pour origine et destination : `Track_*_Lat`, `Track_*_Lon`, `Track_*_FL_Ft` (vaut "ground" ou un niveau de vol), `Track_*_DateTime_UTC`, `Track_*_ApplicableAirports`, et `Route_Validation_Based_on_Callsign`. Les coordonnées d'origine/destination sont présentes depuis 2025. [V]

**Ce que les heures signifient vraiment.** Ce sont des heures de piste approximatives en UTC : décollage pour le départ, toucher des roues pour l'arrivée. Quand la couverture ADS-B est insuffisante, l'heure est celle du début ou de la fin de la trace, pas celle de la piste. Seul le dernier toucher compte en cas de remise de gaz. [V]

**Conséquence majeure : ce ne sont pas des horaires programmés.** Ce sont des vols observés. La "durée" calculable est une durée **airborne** (décollage → atterrissage), pas un temps bloc. Le dataset n'est pas un planning de compagnie, même si son nom contient "schedules".

**Fraîcheur.** Publication trimestrielle, avec chevauchement entre trimestres : ne pas utiliser `drop_duplicates()`, filtrer plutôt sur le mois de `Track_Origin_DateTime_UTC` selon le trimestre du fichier (méthode indiquée dans le README). [V] À l'heure de cette vérification, vérifier la dernière release disponible avant tout import.

**Licence.** ODbL 1.0 (fichier `LICENSE-ODbL.txt` dans le dépôt). Le README remercie et cite adsb.lol, VRS standing-data et adsbdb comme sources. [V]

**Taille.** Environ 10 à 15 millions de vols et 500 000 aéronefs par trimestre ; ≈ 3 Go en CSV, moins de 1 Go en Parquet par trimestre (chiffres du README). [V]

**Import.** Télécharger 1 à 2 trimestres (les plus récents), lire avec DuckDB (`read_parquet`, avec push-down de projection et de filtres), agréger, produire une base SQLite compacte. Ne jamais convertir en JSON.

**Limites connues (toutes documentées par l'auteur).** [V]
- **Couverture ADS-B inégale.** Elle s'améliore (le README signale une hausse en Amérique du Sud, Afrique et Asie début 2026) mais reste limitée. Conséquence directe : une recherche "Afrique → Asie" aura moins de résultats et moins de fiabilité qu'une recherche en Europe. L'interface doit l'afficher.
- **Traces incomplètes** : des aéroports peuvent être multiples ou absents (`-`). La colonne `Route_Validation_Based_on_Callsign` sert à trancher.
- **Brouillage GPS** (spoofing) : aéroport d'arrivée faux possible.
- **Doublons** : jusqu'à environ 10 % sur des routes comme FRA–DXB dans les données 2024 ; nettement réduit depuis 2025 Q2 (environ 95 % et plus de précision sur DXB–FRA).
- **Aviation générale** : précision moindre, liste d'aéroports orientée commercial.
- **Un point à confirmer :** le README renvoie vers `MrAirspace/aircraft-flight-logs/releases` pour les téléchargements, pas vers son propre dépôt. Vérifier où se trouvent réellement les fichiers.
- **Enrichissement par adsbdb :** les types détaillés des avions commerciaux viennent de l'API publique adsbdb. Si les CGU d'adsbdb restreignent la réutilisation (voir §6), la colonne `AC_Type_Detailed` peut poser un risque juridique indirect. Ne pas bâtir de fonction critique dessus en Phase 1.
- **Hors données publiques** : sièges, piste probable, heures locales ne sont proposées que "sur demande" à l'auteur. Ne pas les supposer disponibles.

**Redistribuable.** Oui, sous ODbL (attribution + share-alike). Voir §12.

**Verdict.** Cœur du moteur. Retenue, avec règles de qualité strictes (CODEX_TASK, étape 2).

---

## 4. adsb.lol (amont de MrAirspace)

**Fournit.** Historique ADS-B communautaire. Un projet tiers indique que `adsb.lol globe_history` est publié sous ODbL 1.0. [T]

**Rôle.** Aucun import direct en Phase 1 : le traitement brut (centaines de Go) n'est pas nécessaire puisque MrAirspace fait déjà l'extraction. À citer en attribution.

---

## 5. Fuseaux horaires : timezonefinder + timezone-boundary-builder

**Fournit.** Conversion latitude/longitude → identifiant IANA (ex. `Europe/Paris`), hors ligne, sans simplification des polygones. [V]

**Licence.** Le code de `timezonefinder` est MIT ; les données viennent de `evansiroky/timezone-boundary-builder`, sous ODbL. Les frontières dérivent d'OpenStreetMap. Un intégrateur indique qu'afficher le fuseau dans une réponse d'API est une "Produced Work" qui ne demande qu'une attribution. [V]+[T]

**Import.** Étape ETL : pour chaque aéroport, `timezone_at(lng, lat)`, stockage de `tz_iana` et de la version de la lib/données dans `tz_source`. Cas sans résultat (plateformes offshore, terrains en mer) : `tz_iana = NULL`, et l'interface affiche "fuseau inconnu" plutôt que de deviner.

**Règle.** Les décalages (UTC+1, UTC+2) ne sont **jamais** stockés ni codés en dur. Seul l'identifiant IANA est stocké ; l'offset est calculé au moment de la requête avec la base tzdata de la plateforme, épinglée et mise à jour régulièrement.

---

## 6. Virtual Radar Server — standing-data (et adsbdb)

URL : `https://github.com/vradarserver/standing-data`

**Fournit.** CSV communautaires : `airlines`, `airports`, `aircraft`, `model-type`, `routes` (callsign → route), `countries`, etc. La structure observée est `routes/schema-01/{lettre}/{code}-{all|digit}.csv` et `airlines/schema-01/airlines.csv`. [V]

**Licence.** CC0 1.0 (fichier `LICENSE` du dépôt). [V] Un projet tiers note que le fichier compilé `StandingData.sqb` a été écarté faute de licence de données claire (licence BSD-3 sur le logiciel seulement) : **utiliser les CSV du dépôt, pas le `.sqb`**. [T]

**Taille.** D'après une mesure tierce : archive complète ≈ 7 Mo ; `routes/schema-01` ≈ 19 Mo de CSV répartis en 1 576 fichiers (≈ 4,6 Mo compressés). [T]

**Limites.** Base **communautaire** (soumissions d'utilisateurs VRS), donc qualité variable. Un callsign peut correspondre à plusieurs tronçons (mesure tierce : ≈ 5,5 % des routes). Sert à **valider**, pas à faire foi.

**Redistribuable.** Oui (CC0).

**adsbdb — à ne pas copier.** Un projet tiers cite les conditions d'adsbdb : ses données de route ne peuvent pas être copiées, publiées ou intégrées à d'autres bases sans permission explicite de l'auteur. [T] Pour cette raison, le Flight Finder **n'interroge pas adsbdb et n'en stocke rien**. Les routes de validation viennent de VRS (CC0).

**Verdict.** Retenue pour compagnies et validation de routes.

---

## 7. OpenFlights

**Fournit.** Routes (`routes.dat`), compagnies, avions, aéroports. [V]

**Fraîcheur.** Les routes sont gelées : le fournisseur tiers a cessé les mises à jour en **juin 2014** (67 663 routes, 3 321 aéroports, 548 compagnies). Le site lui-même indique que ces données n'ont plus qu'une valeur historique. La copie GitHub n'est mise à jour que sporadiquement. [V]

**Licence.** ODbL pour la base, Database Contents License pour le contenu. Certaines données compagnies/avions proviennent de Wikipédia (GFDL possible). [V]

**Verdict.** **Non retenu** pour les routes (12 ans de retard). Utilisable au mieux comme table d'alias de noms de compagnies, et encore : VRS couvre ce besoin sans obligation share-alike supplémentaire. Ne pas l'utiliser pour prétendre qu'une route est "réelle aujourd'hui".

---

## 8. catchflights/routes (raccourci éventuel, non retenu par défaut)

**Fournit.** Des releases quotidiennes de routes dérivées de traces ADS-B (par exemple 115 085 routes au 30 septembre 2026), sous ODbL, issues de adsb.lol et MrAirspace. Un `manifest.json` décrit les colonnes. [V]

**Pourquoi pas par défaut.** Dépôt personnel sans étoiles ni historique, un seul mainteneur, colonnes non inspectées, et il n'apporte pas les horaires locaux ni les patterns dont on a besoin. À garder comme **outil de recoupement** (une route présente chez nous et absente chez eux est suspecte), pas comme dépendance.

---

## 9. Flight Plan Database (Phase 2)

**Fournit.** Un site et une API de plans de vol pour la simulation : recherche de plans, générateur de route (`auto/generate`), données de navigation. [V]

**Conditions.** Les données sont "pour la navigation simulée uniquement", jamais pour le vol réel ; l'usage de l'API doit respecter les CGU générales et les conditions API, et le service peut réduire les limites ou révoquer l'accès. [V] (Les pages de CGU consultées paraissaient anciennes : à relire avant usage.)

**Limites de débit.** Un wrapper tiers indique 100 requêtes/jour par IP sans clé et 2 500 avec clé. Certaines routes exigent une clé. [T]

**Règles pour nous.** Clé uniquement côté serveur. Appel seulement **après** sélection d'un vol, sur action explicite de l'utilisateur. Ne pas persister les plans renvoyés tant que les CGU n'autorisent pas clairement le cache. Fonction facultative : si l'API disparaît, le Finder continue de marcher.

---

## 10. AeroDataBox (Phase 3, optionnel)

**Fournit.** Statut de vol, horaires, historique, avions, aéroports, via RapidAPI ou API.Market, et aussi en direct sur leur site. La couverture est "étendue mais pas mondiale" et peut inclure des estimations dérivées d'ADS-B. [V]

**Coûts.** Plan gratuit limité (600 unités/mois sur Basic chez les marketplaces), payants à partir de quelques dollars par mois. Les montants exacts **divergent selon les pages** (5 $, 5,35 $, 7,50 $, 8 $, 19 $ selon canal et date) : à reconfirmer au moment de s'abonner. [V]+[T]

**Conditions.** Le fournisseur renvoie à l'Article 5 de ses conditions pour la **mise en cache, la durée de conservation et l'attribution**, et a récemment modifié ses conditions (usage commercial, B2B, cache, attribution). Non lu en détail. [V] Le sous-licenciement (un tiers qui extrait et redistribue les données dérivées) exige un plan spécifique. [V]

**Règle pour nous.** Jamais dans le chemin critique. Interface `LiveProvider` avec un drapeau de fonctionnalité ; clé côté serveur ; cache conforme aux CGU ; résultat affiché comme "Live check" avec l'heure de la vérification ; en cas d'échec, message neutre et le Finder reste intact.

---

## 11. FlightAware AeroAPI (Phase 3, optionnel)

**Conditions.** Le palier **Personal** limite le stockage et la distribution d'œuvres dérivées à un usage **personnel ou académique** ; l'historique et les alertes n'y sont pas inclus. Les paliers Standard/Premium couvrent l'usage commercial. [V]

**Coûts.** Personal : jusqu'à environ 5 $ de crédit gratuit par mois. Le minimum mensuel du palier Standard est rapporté à 100 $ par une source et 200 $ par une autre : **contradiction non résolue**. [T]

**Verdict pour un outil utilisé par d'autres joueurs.** Une appli partagée dans une communauté n'est très probablement pas un "usage personnel". Le palier gratuit ne convient donc pas à un déploiement public. C'est la raison de plus pour garder Live hors du cœur du produit.

---

## 12. Conséquences de la licence ODbL sur l'architecture

Ce qui suit est une lecture technique de la licence, pas un conseil juridique.

- L'ODbL distingue la **base dérivée** (une base modifiée ou agrégée à partir des données) de l'**œuvre produite** (le résultat d'une requête : texte, image…). [V]
- L'**usage interne** d'une base dérivée au sein d'une organisation n'est pas un usage public et ne déclenche pas le share-alike. [V]
- Le share-alike s'applique à une base dérivée **utilisée publiquement**. Et si une œuvre produite depuis une base dérivée est utilisée publiquement, cette base est considérée comme utilisée publiquement. [V]
- La FAQ d'OpenStreetMap précise que le destinataire d'une œuvre produite peut demander une copie de la base et des bases dérivées utilisées ; vous devez la fournir sur demande, ou les moyens de la reconstruire. Les conditions appliquées à l'œuvre produite restent libres. [V]

**Ce que cela implique pour ton projet.**

1. Garder les grosses bases **côté serveur** reste la bonne stratégie : le navigateur ne reçoit que des œuvres produites (résultats de recherche), jamais la base.
2. Si le service est accessible à d'autres joueurs, prévoir que `aviation.sqlite` (dérivée de données ODbL) puisse être fournie **sur demande** sous ODbL. Ce sont des données ouvertes à la base ; ce qui reste privé, c'est ton **code**, ton **pipeline** et tes **données RFS propres**.
3. Séparer physiquement en deux fichiers : `aviation.sqlite` (dérivée ODbL) et `rfs_compat.sqlite` (propriétaire, issue de ta vérification manuelle). L'ODbL prévoit que l'assemblage d'une base dérivée avec d'autres contenus en "base collective" n'impose pas l'ODbL à l'ensemble. [V]
4. Afficher l'attribution dans une page "Données & licences" et dans le pied des résultats.
5. Ne jamais envoyer de dump complet au navigateur (mode hors-ligne complet exclu).

Si le projet reste strictement privé (toi seul), ces contraintes sont très allégées ; elles reviennent dès qu'un autre joueur utilise l'outil.

**Textes d'attribution à afficher :**

- "Airport & runway data: OurAirports (public domain)."
- "Flight observations: MrAirspace/aircraft-flight-schedules, derived from adsb.lol ADS-B data, ODbL 1.0."
- "Airline and route-validation data: Virtual Radar Server standing data (CC0)."
- "Time zone boundaries: timezone-boundary-builder, © OpenStreetMap contributors, ODbL 1.0."

---

## 13. DuckDB

**Rôle.** Outil d'ETL uniquement. Lit directement des Parquet (glob, plusieurs fichiers), avec push-down de projection (seulement les colonnes utiles) et de filtres (zonemaps), lit aussi en HTTP. Licence MIT. Clients Python, Node (Neo), WASM. [V]

**Décision.** DuckDB produit la base agrégée ; l'application interroge une **base SQLite** en lecture seule. Raisons : l'agrégat final est petit, SQLite est pris en charge par toutes les piles possibles (le projet existant n'a pas encore été inspecté), et aucune dépendance native supplémentaire n'est imposée au backend. Si, après audit, le backend est Python ou Node, DuckDB en runtime reste possible mais n'apporte rien de décisif.

---

## 14. RFS / Rortos

**Ce qui est public et vérifié.**
- Conditions d'utilisation : `https://www.rortos.com/terms-of-use/` (seuls des extraits ont été lus, dont l'interdiction de vendre ou d'échanger le "Content"). Contact support indiqué sur les stores : `rfs@rortos.com`. [V]
- Le jeu se décrit comme comprenant plus de 60 modèles d'avions. [V]
- Les liveries ont un type **REAL** ou **VIRTUAL** dans le jeu, et les joueurs peuvent en créer : Rortos fournit des gabarits PSD par avion sur `https://realflightsimulator.org/liveries`, les fichiers valides apparaissent en jeu sous 3 jours ouvrés, et les gabarits sont mis à jour régulièrement (p. ex. 737-800 v11 le 21 juillet 2026). [V]

**Ce qui n'existe pas (à notre connaissance).** Aucune liste publique, machine-lisible et officielle des combinaisons avion × compagnie disponibles. Le jeu propose aussi des vols "en temps réel" ; la façon dont RFS choisit ses propres vols n'est pas documentée publiquement. [V]

**Conséquences.**
- La compatibilité RFS repose sur **deux tables tenues à la main** (`rfs_type_map`, `rfs_liveries`), chaque ligne avec `verified`, `verified_date`, `source`.
- Une combinaison n'est "disponible dans RFS" que si `verified = 1`. Sinon l'interface affiche "non vérifié".
- Les liveries créées par des joueurs changent avec le temps : la date de vérification est donc obligatoire et un écart d'ancienneté doit s'afficher.
- Pas de scraping, pas d'extraction de fichiers du jeu, pas de copie massive d'images. Si tu veux de la donnée officielle, la bonne voie est un message à Rortos.

---

## 15. Matrice de fraîcheur affichable

| Donnée | Champ affiché | Origine de la date |
|---|---|---|
| Aéroports/pistes | "Airports: OurAirports, retrieved YYYY-MM-DD" | `dataset_versions.retrieved_at` |
| Observations de vol | "Observed from YYYY-MM-DD to YYYY-MM-DD; last seen YYYY-MM-DD" | `covers_from`, `covers_to`, `last_seen_utc` |
| Compatibilité RFS | "Verified YYYY-MM-DD" ou "Not verified" | `rfs_*.verified_date` |
| Live check | "Checked HH:MM (source)" | horodatage de l'appel |

## 16. Liste des points non résolus

1. Emplacement exact des releases MrAirspace (lien du README vers un autre dépôt).
2. Format réel de `Track_*_ApplicableAirports` et de `Route_Validation_Based_on_Callsign` (délimiteur, casse, valeur pour "inconnu").
3. CGU adsbdb vis-à-vis de la colonne `AC_Type_Detailed`.
4. CGU Rortos sur les outils tiers qui manipulent des données liées à RFS.
5. Article 5 des CGU AeroDataBox (cache) et prix du palier Standard de FlightAware.
6. Continents "limites" d'OurAirports (Russie, Turquie, Caucase…).
