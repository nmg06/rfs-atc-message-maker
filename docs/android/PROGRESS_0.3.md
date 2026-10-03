# Flightdeck 0.3.0 — deuxième étape Android

## Modifications

- Carte hors ligne dans `android/app/src/main/assets/www/map.js` : frontières
  locales, route depuis les aéroports de la SQLite, déplacement, zoom/pincement,
  choix des pays et recherche Finder, cadrage conservé.
- `map_geometry.py` extrait exactement les fonctions de la carte Windows ;
  `route_map.py` les importe. `scripts/prepare_android.py` transforme automatiquement
  les données Natural Earth existantes en ressource JavaScript embarquée.
- Bibliothèque : vols/favoris renommables et supprimables, pilotes éditables,
  préférences conservées, designs gérables, historique nettoyable. Catalogue des
  pays/drapeaux recherchable ; panneaux ouverts conservés pendant l'édition.
- Import PC complet par quatre JSON explicitement sélectionnés, validation globale,
  sauvegarde avant remplacement, reprise des anciennes langues. Pas de lecture
  automatique du profil PC ni de permission générale de stockage.
- PUSHBACK/TAXI/ATIS utilisent la présentation commune du moteur Windows,
  avec groupes de pilotes et parallèle sur les messages de départ.
- Provenance des durées Finder identique à Windows : observé/estimé/non vérifié.
- Windows : deux traducteurs Qt conservés pendant la vie de QApplication au lieu
  de créations/suppressions répétées, réinstallation évitée si langue inchangée.
  Une violation d'accès native a été reproduite au constructeur de QTranslator ;
  la correction passe trois suites complètes et un contrôle des dialogues traduits.

## Vérifications locales

- Windows : 114 tests, trois suites complètes réussies après correction.
- Android Python : 22 tests ; 1 344 générations PC et 504 combinaisons supplémentaires,
  SQLite locale, carte, bibliothèque, préférences, export/import/redémarrage.
- Parcours téléphone Playwright : voir `android/tests/ui_browser.cjs` ; les requêtes
  de la carte sont vérifiées locales et les résultats restent ceux du moteur réel.
- Build debug et tests natifs : `android/gradlew.bat -p android assembleDebug assembleDebugAndroidTest`.
- Contrôle de l'APK : `python scripts/verify_android_apk.py ... --aapt ...` compare
  la carte embarquée à la source Windows et vérifie toujours l'absence de permissions.

L'installation sur l'émulateur, trois tests natifs et la fermeture complète/relance
sont exécutées par GitHub Actions ; leur résultat sera lié après achèvement.

## Encore à vérifier / développer

- Sélecteurs de documents/photos et choix d'une application de partage sur téléphone physique.
- Quelques textes techniques FR/EN et adaptation de l'introduction humoristique.
- Satellite et vents Android, qui restent absents ; aucune permission Internet ajoutée.
- iPhone : aucun hôte Python iOS/build Apple disponible dans cette chaîne Windows/Android.
