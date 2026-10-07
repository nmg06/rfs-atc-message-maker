# Enrichissement local — 7 octobre 2026

La nouvelle base conserve **203 627 profils historiques à l’identique**, et ajoute
**21 053 routes directes** avec des preuves ADS-B suffisamment répétées.
**3 195 combinaisons callsign/départ/arrivée** sont absentes des anciens profils.
Ces nombres ne représentent pas des vols supplémentaires chaque jour.

## Comment les utiliser

Dans Flight Finder sur PC ou Android, cochez **Routes récentes observées**.
Choisissez une compagnie, un pays ou un aéroport, puis recherchez. Les exclusions
ICAO/IATA, les pays, continents, régions, le callsign, les vols internationaux,
la pagination et « Utiliser ce vol » fonctionnent également dans ce catalogue.

Ce complément ne contient ni avion ni durée. Effacez ces filtres et les horaires,
ou revenez à la recherche habituelle pour filtrer les profils complets.
Sur PC, cocher le catalogue désactive le filtre « avions RFS uniquement ».
La compagnie est déduite du préfixe du callsign, sans garantie d’exploitation actuelle.
L’avertissement est affiché dans les résultats et les détails.

« Utiliser ce vol » transfère les informations disponibles. L’avion, la durée,
la quantité de carburant, les portes et les pistes manuellement renseignés sont
conservés : vérifiez-les pour le nouveau trajet. Le calcul de fuel précédent est
invalidé. Aucune durée, affectation de piste ou porte n’est inventée.

## Sources examinées et dates

- [MrAirspace](https://github.com/MrAirspace/aircraft-flight-schedules/releases) :
  la dernière publication vérifiée le 7 octobre est Q2 2026. Les profils complets
  utilisent Q1 + Q2, jusqu’au 30 juin. Aucun Q3 disponible dans les releases vérifiées.
- [CatchFlights, export du 7 octobre](https://github.com/catchflights/routes/releases/tag/routes-2026-10-07) :
  128 173 lignes avant sélection ; observations retenues du 22 août au 7 octobre à
  07:16:33 UTC. Export dérivé de traces ADS-B, **pas un horaire publié**.
  ODbL 1.0, contenus DBCL, attribution CatchFlights / adsb.lol / MrAirspace.
- [SFO Museum, septembre](https://github.com/sfomuseum-data/sfomuseum-data-flights-2026-09) :
  source intéressante pour un complément localisé SFO, sous CDLA-Permissive-1.0.
  Les exemples examinés présentent notamment des partages de code et des horaires
  prévus/estimés sans durée complète observée. **Non intégrée** dans cette étape ;
  demande un traitement distinct des opérateurs, vols commerciaux et doublons.
- Les archives ADS-B brutes mondiales sont très volumineuses. Aucun téléchargement
  de l’année complète ni dépendance réseau n’a été ajouté à l’application.

La base n’est pas présentée comme une liste exhaustive de tous les vols de 2026.
Les références d’aéroports/compagnies restent celles du snapshot du 30 septembre.

## Sélection prudente

Confiance de la source ≥0,95, un seul couple d’aéroports candidat, au moins trois
jours et trois observations, pas d’escale intermédiaire, deux aéroports distincts
connus, préfixe compagnie connu, dates valides. La confiance concerne une catégorie
de preuves de la source ; elle n’est pas la probabilité de réaliser ce vol demain.
107 084 lignes trop faibles/ambiguës et 36 autres lignes invalides ou sans compagnie
connue ne sont pas importées. Aucun avion ni durée artificiel ne complète ces lignes.

## Reproduction hors ligne

Le CSV compressé original et son manifest sont figés dans `finder/source-data/`.
SHA-256 : `ac314dfbee338f3b6bc5331ac4c85dbf1d9158d771d9694a304e2bb05313960c`.
La construction refuse un checksum différent et refuse d’écraser sa base d’entrée
ou un fichier de sortie existant. Le script ne contacte aucun service distant.

```powershell
python scripts/enrich_observed_routes.py --base BASELINE.sqlite --output aviation-enriched.sqlite --report enrichment-report.json
python scripts/prepare_android.py --database aviation-enriched.sqlite
python -m unittest discover -s tests -v
python -m unittest discover -s android/tests -v
node android/tests/run_browser.cjs
.\android\gradlew.bat -p android --offline --no-daemon assembleDebug assembleDebugAndroidTest
python -m PyInstaller --noconfirm --distpath dist/enrichment-2026-10-07 --workpath build/pyinstaller-enrichment-2026-10-07 RFSATCMessageMaker.spec
python scripts/package_windows.py --dist dist/enrichment-2026-10-07/RFSATCMessageMaker --archive dist/RFSFlightdeck-Windows-0.4.3-2026-10-07.zip
```

BASELINE.sqlite est la base Q1–Q2 avec overlay historique du 6 octobre, avant ce
complément. Le script ajoute une table indépendante ; il ne modifie aucune ligne
de `flight_patterns`. La comparaison vérifie tous les champs de chaque profil,
pas seulement le nombre de trajets. Les anciennes bases sans catalogue continuent
à fonctionner ; l’option routes récentes y donne un avertissement explicite.

## Preuves de cette étape

Le rapport exact est [data-enrichment-2026-10-07.json](data-enrichment-2026-10-07.json).
Intégrité SQLite OK, clés étrangères OK, zéro profil modifié ou supprimé.
Base candidate SHA-256 : `5df24e6a17b16458ba67c46d24b22f6178644ebdd3619ea0a5a713a351a2a1cb`.

173 tests Windows et 32 tests du moteur Android passent. Le parcours navigateur
spécifique aux routes récentes passe : anglais, champs inconnus, détails lisibles,
transfert, conservation après rechargement et aucune requête distante.
APK debug et APK de tests compilées ; contenu de la base embarquée vérifié.
L’APK est également installée et vérifiée sur émulateur API 35 au commit
`82bad6d` : cinq tests hors ligne, arrêt complet/reprise du processus, quatre tests
de cycle de vie (dont l’import après recréation), puis deux tests facultatifs en ligne
et de personnalisation passent. [Workflow Android réussi](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37626682395).
Les contrôles Windows, dépendances et CodeQL passent également sur ce commit.
Les essais sur téléphone physique restent à effectuer avant publication officielle.

Le prototype web public ne fournit pas le Finder SQLite Android : ce nouveau
catalogue concerne les applications PC et Android, pas le prototype.

Le paquet Windows autonome a été lancé avec `--smoke-test` : code de sortie 0,
691 profils historiques LFPG ≤2h et 88 routes Air France dans le nouveau catalogue,
exemple Fuel 12 285 kg, carte et aide bilingue chargées. Neuf parcours navigateur
passent. En cas d’échec de sauvegarde Android, Retour conserve l’écran et les
données saisies au lieu de fermer l’application.
