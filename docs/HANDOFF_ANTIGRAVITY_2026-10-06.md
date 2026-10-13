# Reprise Antigravity — 6 octobre 2026

## Dépôt et état réel

Projet : `nmg06/rfs-atc-message-maker`, application RFS Flightdeck.
Dossier : `C:/Users/nmosn/OneDrive/Desktop/claude code 1/flightdeck-next`.
Branche : `feat/flightdeck-map-performance`.
PR draft : https://github.com/nmg06/rfs-atc-message-maker/pull/2
Dernier commit poussé avant cette étape : `01769456f924129d6c1d3f60db5ab24067d84ce7`.

**Les modifications 0.4.3 sont locales, non commitées/non poussées.** Voir
`git status --short`. Ne pas les annuler. La version source est maintenant 0.4.3,
Android versionCode 7. Aucun nouveau tag, merge, release publique ou message
Discord. L’utilisateur veut finir PC/mobile avant publication et publiera lui-même
le texte Discord avec des photos.

## Réalisé et vérifié

- Windows/Android : bouton **Calculer le fuel** auprès du champ carburant.
  Réutilise Fuel Helper et les mêmes formules ; reprend avion, durée totale et
  arrivée. ETE restante 5 min ne devient jamais la durée Fuel. Aucun carburant
  appliqué automatiquement. Variantes ambiguës à sélectionner explicitement.
- Android : protection des saisies et de la dernière navigation pendant une
  préparation Fuel/sauvegarde retardée ; ancien résultat Fuel effacé si les
  entrées changent ; nouvelle saisie prioritaire sur une réponse ancienne.
- Finder PC/Android : champ **Éviter ces aéroports**, ICAO/IATA multiples,
  espaces/virgules/points-virgules, exclusion aux deux extrémités, codes invalides
  ou inconnus signalés. Filtres conservés. Réponses Android obsolètes ignorées.
- Android : WebView minimum 80 + sonde locale, fallbacks DisplayNames/replaceAll,
  chargement initial neutre. Sessions SAF/import/export/rappel persistées dans
  AtomicFile privé, résultats liés à une génération de page. Images validées
  ensemble avant ajout ; rapport avec snapshot consenti.
- Signature : configuration release exige une clé stable ; vérificateur refuse
  APK debug/signature inattendue. Workflow manuel de candidate Windows/Android
  créé, sans publication. **Clé privée et secrets GitHub pas configurés.**

Preuves fraîches de cette étape :

- **156 tests Windows PASS**, `build/windows-tests-043.log`. Les nouveaux tests
  ETL ont été ajoutés ensuite : relancer la suite finale après gel.
- Tests raccourci Qt **2 PASS**, après correction du fixture `arrival_ete`.
- **31 tests moteur Android PASS** (dernier périmètre du raccourci).
- Tests Finder PC/Qt **5 PASS**.
- Scénario navigateur `finder_exclusions_browser.cjs` PASS : vraie SQLite,
  VIDP/VABB, persistance, FR/EN, affichage 320 px, courses Fuel et navigation,
  aucune requête distante.
- `experience_browser.cjs` PASS, `build/experience-043.log` : retour, sauvegarde,
  redémarrage, carnet, carte, double clic/Back pendant sauvegarde retardée.
- `compatibility_browser.cjs`, `updates_backup_browser.cjs` PASS ; fallbacks
  supplémentaires Node 8 cas PASS.
- Windows EXE **compilé** :
  `dist/candidate-043/RFSATCMessageMaker/RFSATCMessageMaker.exe`.
  `build/windows-build-043.log`. **Pas encore empaqueté ni smoke-testé avec la
  nouvelle base.** Ne pas présenter ce dossier comme livraison finale.
- Java application Android compile. Première compilation des tests a échoué
  `LifecycleCompatibilityTest.java:115` (setClipData retourne void). Le fixture
  est corrigé, **compilation à relancer**. `build/android-java-043.log` contient
  encore l’échec antérieur, pas une preuve de succès final.
- **Quatre nouveaux tests instrumentés non exécutés** : lifecycle, import/export,
  images/rapport, rappel, WebView, remplacement DB avec profil conservé.

## Base enrichie : décision à terminer AVANT remplacement

La base embarquée actuelle dans `android/bundled` reste celle de 0.4.2.
La reconstruction Q1+Q2 a terminé, intégrité/foreign keys OK :

- `build/data-audit-2026-10-06/aviation-Q1-Q2.sqlite` : 137 445 376 octets.
- gzip candidate : même dossier, `aviation-Q1-Q2.sqlite.gz` : 37 097 129 octets.
- Ancienne sauvegardée : `aviation-Q2-before.sqlite`, 94 892 032 octets,
  SHA256 `4a2de0a7a2a9626ee8bb6d458baa2ec52820c5fa068e6a9ae4a7a6f91fb28b57`.
- Candidate pure : **203 627 profils** (ancien 135 554), **92 952 durées issues
  d’au moins 3 traces complètes** (ancien 59 552), **7 891 468 observations**
  (ancien 4 078 484). Dernière observation reste **30 juin 2026**.
- Aucune ancienne route observée ou clé de route avec durée observée perdue.
  Profils compatibles avions RFS avec durée observée : 44 231 → 68 603.
- Air France ~0,198 s ; pagination ~0,027 s. Recherche générale plafonnée à
  20 000 reste ~5–6 s : ne pas promettre toutes les recherches instantanées.

**Piège important** : l’ancienne base contient 76 002 durées ajoutées après
import. Toutes sont numériquement compatibles avec le détecteur existant
`ESTIMATED_DISTANCE_HEURISTIC` de `finder/provenance.py` ; cela ne prouve pas
quel script les a créées. La nouvelle candidate pure laisse les durées manquantes
inconnues et ferait perdre certaines recherches basées sur ces estimations.

Proposition en discussion, **non implémentée/non approuvée comme solution finale** :
overlay conservateur copiant seulement l’ancienne `duration_min` sur la même clé
exacte encore inconnue, sans formule nouvelle, sans faux percentiles, provenance
du snapshot conservée. 71 114 clés correspondantes restent sans durée, 2 201
ont maintenant une durée observée ; 2 687 cas ont un changement de type modal/clé
avion. Évaluer leur conservation distincte sans attribuer arbitrairement un avion.
Ne pas remplacer le bundle avant d’avoir validé cette compatibilité et les tests.

Sources et reconstruction : `finder/source-data/`,
`scripts/rebuild_historical_finder.py`, `scripts/compare_finder_snapshots.py`,
`tests/test_finder_historical_etl.py`, `docs/data-enrichment-2026-10-06.md` et JSON.
Tests ETL ciblés 9 PASS puis 4 manifest revérifiés. CSV gelés dans archive publique
5,35 Mo. Parquet Q1 840 Mo dans build ; Q2 est dans le cache mainteneur (voir
rapport/manifeste). Aucun téléchargement runtime, donnée CatchFlights/VRS récente
**non ajoutée** au bundle. Limites ETL DuckDB 512 Mo/1 thread ; mémoire Python
totale plus élevée. Garder candidats et anciennes sauvegardes.

## Étapes restantes, dans cet ordre

1. Résoudre la conservation des estimations héritées, tester provenance,
   recherche/mapping/pagination et zéro perte indésirable. Mettre à jour mesures.
2. Geler base et sources, puis `python scripts/prepare_android.py --database
   CHEMIN_BASE_FINALE` pour générer bundle et manifest. Ne pas empaqueter les
   Parquet, archives de construction ou profils privés.
3. Relancer Windows, moteur Android et les **7 scénarios navigateur** du runner.
4. Construire APK et APK tests, vérifier assets/hash/permissions/signature.
5. GitHub Actions API35 : core, redémarrage, **nouvelle suite lifecycle**, puis
   online et optional/icons. Workflow Android inclut déjà lifecycle avant online.
   Corriger jusqu’au succès réel. Le SDK local n’a pas de system image utilisable :
   l’AVD existant pointe vers un dossier supprimé, tentatives arrêtées sans modifier
   l’AVD. Aucun téléphone physique connecté.
6. Empaqueter Windows avec la base finale, EXE smoke-test sur profil isolé.
7. Captures réelles PC/Android, texte Discord naturel prêt à copier, docs
   installation/parité/bilan avec preuves exactes. Script de captures Android
   prêt mais non exécuté : `build/capture-android-043.cjs`.
8. Nouvelle livraison 0.4.3 à côté des anciennes, sauvegarde avant transfert de
   profil, raccourci nouveau dossier. Commit/push et description PR, pas release
   publique. Ne pas modifier/supprimer l’ancienne application quotidienne.
9. Avant officialisation : gestes fichiers/photos/partage/clavier/paysage sur
   téléphone ; clé privée stable, APK release et deuxième mise à jour même clé.

Commandes générales depuis la racine :

```powershell
python -m unittest discover -s tests -v
python -m unittest discover -s android/tests -v
node android/tests/run_browser.cjs
.\android\gradlew.bat -p android --no-daemon assembleDebug assembleDebugAndroidTest
python scripts/verify_android_apk.py android/app/build/outputs/apk/debug/app-debug.apk --aapt CHEMIN_SDK/build-tools/35.0.0/aapt.exe
python scripts/package_windows.py --dist dist/candidate-043/RFSATCMessageMaker --archive dist/RFSFlightdeck-Windows-0.4.3-x64-test.zip
```

Pour build local, `JAVA_HOME` = `C:/Users/nmosn/.cache/rfs-android/tools/jdk/jdk-21.0.12.1+1`,
`ANDROID_HOME` = `C:/Users/nmosn/.cache/rfs-android/tools/android-sdk`,
`GRADLE_USER_HOME` = `C:/Users/nmosn/.gradle` (cache existant).
Python/Node disponibles :

- Python Qt/PyInstaller : `C:/Users/nmosn/Documents/Codex/2026-09-29/ouvre-le-projet-message-maker-que/work/message-maker/.venv/Scripts/python.exe`.
- Python sans Qt : `C:/Users/nmosn/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`.
- Node : `C:/Users/nmosn/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe`.
- `NODE_PATH` : `C:/Users/nmosn/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules`.
- Navigateur tests : `RFS_TEST_BROWSER=chrome`, `RFS_TEST_PYTHON`=Python sans Qt,
  `RFS_TEST_NODE`=Node ; `QT_QPA_PLATFORM=offscreen` et profil `RFS_MESSAGE_MAKER_DATA_DIR`
  isolé dans build. `RFS_BUILD_PYTHON`=Python de build (3.11 recommandé ; local 3.12
  compile mais avertit que les .pyc Android 3.11 ne sont pas précompilés).

## Fichiers installables déjà livrés

**Dernière APK livrée reste 0.4.2**, pas encore de nouvelle APK 0.4.3 :
`C:/Users/nmosn/OneDrive/Desktop/claude code 1/livraison-flightdeck/RFSFlightdeck-Android-0.4.2-debug.apk`.
PC livré : `livraison-flightdeck/PC-0.4.2/RFSFlightdeck/` et ZIP 0.4.2.
Raccourci bureau « RFS Flightdeck - nouvelle version » cible encore ce PC 0.4.2.
Les anciennes versions et leurs données sont conservées.

Lire aussi `docs/RELEASE_READINESS.md`, `docs/android/SIGNING.md` et PARITY.
La chaîne release signée reste à configurer/tester. Utiliser les futurs tags
`flightdeck-X.Y.Z` : les tags `v*` déclenchent l’ancien workflow public Windows.
iPhone pas installable ; web reste prototype sans Finder SQLite. Aucun faux
statut terminé, aucune publication automatique, aucun message envoyé à Discord.
