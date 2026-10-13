# RFS Flightdeck — Bilan des Corrections & Feuille de Route pour IA

Ce document résume les **bugs corrigés immédiatement** dans le code source de la version 0.4.3 et définit la **feuille de route technique détaillée** pour toute future session ou IA prenant le relais.

---

> État actualisé du 7 octobre : 173 tests Windows, 32 tests moteur Android et neuf
> parcours navigateur passent. La base et les builds sont décrits dans
> [le bilan d’enrichissement](DATA_ENRICHMENT_2026-10-07.md). Les anciens nombres
> ci-dessous restent le bilan de la session précédente, pas la preuve des builds actuels.

## 1. Corrections appliquées et vérifiées (18 fichiers modifiés)

Toutes les modifications ci-dessous ont été implémentées et validées par l'ensemble des suites de tests (**163 tests unitaires Windows PASS**, **31 tests moteur Android PASS**, **7/7 scénarios navigateur Playwright PASS**, **Smoke-test PASS**).

### A. Moteur & Recherche (Finder)
1. **[finder/duration.py](file:///C:/Users/nmosn/OneDrive/Desktop/claude%20code%201/flightdeck-next/finder/duration.py)** :
   - Correction du crash sur `parse_minutes(None)` et `parse_finder_hours(None)` qui levaient `ValueError` au lieu de retourner `None`.
   - Prise en charge des minutes à 1 ou 2 chiffres au format horaire (ex. `1:5` pour 1h05).
2. **[finder/search.py](file:///C:/Users/nmosn/OneDrive/Desktop/claude%20code%201/flightdeck-next/finder/search.py)** :
   - Sécurisation de la clé de tri contre les valeurs `None` (`callsign`, `origin`, `destination`, `last_seen`) évitant un crash `TypeError: '<' not supported between NoneType and str`.
3. **[finder/i18n.py](file:///C:/Users/nmosn/OneDrive/Desktop/claude%20code%201/flightdeck-next/finder/i18n.py)** :
   - Ajout des clés manquantes dans le dictionnaire français : `"title": "Recherche de vols"` et `"minutes": "min"`.

### B. Carburant (Fuel Helper)
4. **[fuel/duration.py](file:///C:/Users/nmosn/OneDrive/Desktop/claude%20code%201/flightdeck-next/fuel/duration.py)** :
   - Ajout du parsing des durées exprimées uniquement en minutes (`45m`, `45min`, `45 min`) qui étaient auparavant rejetées avec `None`.
5. **[fuel/selection.py](file:///C:/Users/nmosn/OneDrive/Desktop/claude%20code%201/flightdeck-next/fuel/selection.py)** :
   - Priorisation de `flight['fuel_aircraft_id']` : si l'utilisateur a sélectionné une variante précise d'avion (ex. B738 passagers vs cargo), son choix n'est plus réinitialisé à l'ouverture du calculateur de carburant même si le vol provient du Finder.

### C. Carte & Météo (Route Map)
6. **[route_map.py](file:///C:/Users/nmosn/OneDrive/Desktop/claude%20code%201/flightdeck-next/route_map.py)** :
   - Protection contre la division par zéro (`ZeroDivisionError`) dans `_wind_note` lorsque la route ne comporte qu'un seul point ou qu'aucun composant n'est calculé.
   - Protection contre le crash `ValueError: min() arg is an empty sequence` dans `mouseMoveEvent` lorsque la liste des échantillons de vent est vide.

### D. Données, Validation & Sessions
7. **[flight_planning.py](file:///C:/Users/nmosn/OneDrive/Desktop/claude%20code%201/flightdeck-next/flight_planning.py)** :
   - Normalisation des fuseaux horaires dans `elapsed_seconds` pour éviter `TypeError: can't subtract offset-naive and offset-aware datetimes` en cas de mélange de dates naïves et UTC.
8. **[history_utils.py](file:///C:/Users/nmosn/OneDrive/Desktop/claude%20code%201/flightdeck-next/history_utils.py)** :
   - Protection contre `AttributeError` dans `same_operational_context` lorsque les champs `flight` ou `data` valent `None`.
9. **[storage.py](file:///C:/Users/nmosn/OneDrive/Desktop/claude%20code%201/flightdeck-next/storage.py)** :
   - Correction du piège Python `isinstance(True, int)` dans `_merge` qui pouvait écraser un entier par un booléen.
   - Gestion correcte des valeurs par défaut à `None` et copie sécurisée `deepcopy` des clés non déclarées.
10. **[backup_bundle.py](file:///C:/Users/nmosn/OneDrive/Desktop/claude%20code%201/flightdeck-next/backup_bundle.py)** :
    - Limitation des collections fusionnées (`flight_log` à 500, `history` à 200) dans `merge_payloads` évitant le rejet `Collection exceeds limit` lors d'imports successifs.
11. **[validation.py](file:///C:/Users/nmosn/OneDrive/Desktop/claude%20code%201/flightdeck-next/validation.py)** :
    - Tolérance des séparateurs de milliers (espaces, virgules, ex: `12 500 kg`) dans la validation numérique des champs carburant/fret.
12. **[message_builder.py](file:///C:/Users/nmosn/OneDrive/Desktop/claude%20code%201/flightdeck-next/message_builder.py)** :
    - Correction du filtre de callsign dans les vols en groupe sous `DISPATCH FORM` (ajout de `'CALL SIGN'` en plus de `'CALLSIGN'`).
    - Transmission du paramètre `kind` à `additional_pilots` dans `custom_context` pour filtrer les copilotes selon le type de message.

### E. Mobile Android & Web UI
13. **[android/app/src/main/assets/www/experience.js](file:///C:/Users/nmosn/OneDrive/Desktop/claude%20code%201/flightdeck-next/android/app/src/main/assets/www/experience.js)** :
    - Encapsulation `try/catch` de `displayNames.of()` dans `countryName` pour empêcher un `RangeError` fatal sur des codes pays non ISO.
    - Évitement du blocage du bouton Retour Android en cas d'erreur lors du `flushEdits`.
    - Formatage propre des rappels sans code ICAO (`" · → · "` éliminé).
14. **[android/app/src/main/assets/www/app.js](file:///C:/Users/nmosn/OneDrive/Desktop/claude%20code%201/flightdeck-next/android/app/src/main/assets/www/app.js)** :
    - Mise à jour du numéro de version affiché (`0.4.3`).
15. **[android/app/src/main/java/com/nmg06/rfsatc/MainActivity.java](file:///C:/Users/nmosn/OneDrive/Desktop/claude%20code%201/flightdeck-next/android/app/src/main/java/com/nmg06/rfsatc/MainActivity.java)** :
    - Vérification `web != null` dans `reply()` pour éviter les appels sur une WebView détruite.
    - Réponse d'erreur explicite au lieu d'un abandon silencieux si la requête dépasse 2 Mo (évite le blocage des Promises JS).
    - Vérification `in == null` dans `readLimited()` pour prévenir les `NullPointerException`.
16. **[android/app/src/main/python/android_engine.py](file:///C:/Users/nmosn/OneDrive/Desktop/claude%20code%201/flightdeck-next/android/app/src/main/python/android_engine.py)** :
    - Contrôle des limites d'index sur `finder_details` et `finder_use`.
    - Remplacement du `StopIteration` muet par une `ValueError` explicite dans `load_flight`.
    - Contrôles de validité dans `load_history` et `load_preset`.
    - Validation stricte de la durée positive dans `fuel_use`.
17. **[android/tests/test_engine.py](file:///C:/Users/nmosn/OneDrive/Desktop/claude%20code%201/flightdeck-next/android/tests/test_engine.py)** :
    - Alignement de l'assertion du nombre de résultats LFPG (691 au lieu de l'ancienne valeur 577 de la base 0.4.2).
18. **[ui_translations.py](file:///C:/Users/nmosn/OneDrive/Desktop/claude%20code%201/flightdeck-next/ui_translations.py)** :
    - Ajout des traductions FR/EN pour `Flight Finder`, les extensions ATIS/Pushback, les thèmes `Rose`, `Glacier`, `Graphite` et les colonnes de l'historique.

---

## 2. Feuille de Route pour le Prochain Développeur / IA

Voici les instructions précises, étape par étape, pour prendre en charge les chantiers restants :

### Chantier 1 : Re-packaging Windows & Livraison finale
- **Objectif** : Générer le package Windows final intégrant les dernières corrections et le placer dans `livraison-flightdeck/`.
- **Fichiers concernés** :
  - `scripts/package_windows.py`
  - `dist/candidate-043/`
  - `livraison-flightdeck/PC-0.4.3/`
- **Comment faire** :
  1. Lancer la compilation de l'exécutable avec PyInstaller :
     ```powershell
     & "C:\Users\nmosn\Documents\Codex\2026-09-29\ouvre-le-projet-message-maker-que\work\message-maker\.venv\Scripts\python.exe" -m PyInstaller --noconfirm --distpath dist/candidate-043 RFSATCMessageMaker.spec
     ```
  2. Vérifier que `dist/candidate-043/RFSATCMessageMaker/` est généré avec la base `finder-data/aviation.sqlite`.
  3. Mettre à jour l'archive zip et les fichiers dans `C:/Users/nmosn/OneDrive/Desktop/claude code 1/livraison-flightdeck/`.
  4. Valider avec le smoke test Windows :
     ```powershell
     $env:QT_QPA_PLATFORM="offscreen"; $env:RFS_MESSAGE_MAKER_DATA_DIR="build\smoke-test"; & "dist\candidate-043\RFSATCMessageMaker\RFSATCMessageMaker.exe" --smoke-test
     ```

### Chantier 2 : Portabilité des Extensions Android vers le Desktop Windows
- **Contexte** : Android dispose de types de messages supplémentaires (`PUSHBACK`, `TAXI`, `ATIS`) créés dans `android/app/src/main/python/android_engine.py`. Sur Windows, l'interface `ui.py` n'affiche actuellement les 8 types classiques (`ATC REQUEST`, `AIRBORNE`, `ARRIVAL BOARD`, `FLIGHT COMPLETED`, `ATC ACTIVE`, `ATC OFFLINE`, `FLIGHT PLAN`, `DISPATCH FORM`).
- **Fichiers à modifier** :
  - `templates.py` : Ajouter les fonctions de génération pour `pushback`, `taxi` et `atis` (s'inspirer de celles implémentées dans `android_engine.py`).
  - `rfs_schema.py` : Ajouter ces types à `MESSAGE_TYPES` et définir leurs champs dans `MESSAGE_FIELDS`.
  - `ui.py` : Utiliser la liste de types et les champs existants dans `ui.py` ; vérifier leurs méthodes actuelles avant de modifier la construction des panneaux.
- **Comment tester** :
  - Lancer les tests unitaires : `python -m unittest discover -s tests -v`.

### Chantier 3 : Signature Release Android & CI/CD
- **Contexte** : Le fichier `docs/android/SIGNING.md` documente la génération d'un Keystore release et la configuration des secrets GitHub. Actuellement, l'APK produit est en build `debug` (`RFSFlightdeck-Android-0.4.3-debug.apk`).
- **Fichiers à vérifier** :
  - `android/app/build.gradle` (section `signingConfigs.published`).
  - `.github/workflows/flightdeck-candidate.yml`
- **Comment faire** :
  1. Générer une clé stable avec `keytool` (si l'utilisateur fournit les paramètres de signature).
  2. Configurer les variables d'environnement `KEYSTORE_BASE64`, `KEYSTORE_PASSWORD`, `KEY_ALIAS`, `KEY_PASSWORD`.
  3. Compiler en release : `.\android\gradlew.bat -p android assembleRelease`.

### Chantier 4 : Tests Instrumentés Android
- **Contexte** : 4 tests instrumentés existent dans `android/app/src/androidTest/java/com/nmg06/rfsatc/` (`LifecycleCompatibilityTest.java`, etc.). Ils n'ont pas pu tourner localement faute d'AVD configuré sur la machine.
- **Comment faire** :
  - Connecter un téléphone Android réel en débogage USB (ou démarrer un émulateur AVD API 34/35).
  - Lancer la suite instrumentée :
    ```powershell
    .\android\gradlew.bat -p android connectedDebugAndroidTest
    ```

---

## 3. Commandes de référence pour vérification rapide

```powershell
# Tests unitaires Windows (163 tests)
& "C:\Users\nmosn\Documents\Codex\2026-09-29\ouvre-le-projet-message-maker-que\work\message-maker\.venv\Scripts\python.exe" -m unittest discover -s tests -v

# Tests moteur Android (31 tests)
& "C:\Users\nmosn\Documents\Codex\2026-09-29\ouvre-le-projet-message-maker-que\work\message-maker\.venv\Scripts\python.exe" -m unittest discover -s android/tests -v

# Tests navigateurs Playwright (7 scénarios)
$env:NODE_PATH="C:\Users\nmosn\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules"; $env:RFS_TEST_BROWSER="chrome"; $env:RFS_TEST_PYTHON="C:\Users\nmosn\Documents\Codex\2026-09-29\ouvre-le-projet-message-maker-que\work\message-maker\.venv\Scripts\python.exe"; node android/tests/run_browser.cjs

# Build Gradle Android
$env:JAVA_HOME="C:\Users\nmosn\.cache\rfs-android\tools\jdk\jdk-21.0.12.1+1"; $env:ANDROID_HOME="C:\Users\nmosn\.cache\rfs-android\tools\android-sdk"; $env:GRADLE_USER_HOME="C:\Users\nmosn\.gradle"; .\android\gradlew.bat -p android --no-daemon assembleDebug assembleDebugAndroidTest
```
