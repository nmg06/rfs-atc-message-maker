# Flightdeck 0.4 — confort téléphone et préparation de vol

Demande du 4 octobre 2026. Travail à côté de Windows ; onglets conservés pour
cette étape. Aucune release publique automatique.

## Plan vérifiable

1. Corriger les insets Android avec un conteneur autour de la WebView : barres
   système, encoche, clavier, portrait/paysage. Tester les limites natives.
2. Menu paramètres ↔ croix animé, retour à l'écran et au défilement précédents ;
   retour Android ferme d'abord le dialogue. Séparer sauvegarde et gros rendus.
3. Détails Finder lisibles, cartes espacées et rendu progressif des résultats.
   Géométrie simplifiée pour les interactions, détails après arrêt du geste.
4. Vol orienté préparation : accès Finder/Fuel/carte, pistes locales consultables,
   portes inconnues explicitement signalées, aucune affectation opérationnelle
   inventée. Journal chronométré des vols réellement confirmés par l'utilisateur.
5. Dix couleurs partagées Windows/Android, recherche dans les sélecteurs, icônes
   Android et rappels locaux facultatifs. Aucun rappel sans activation explicite.
6. Satellite/vent Android facultatifs et désactivés initialement : mêmes sources
   PC, HTTPS limité aux fournisseurs, cache borné et requêtes séparées du moteur.
   Messages/Finder/Fuel/carte locale restent utilisables en mode avion.
7. Construire APK/Windows, tester et fournir un guide GitHub simple avec liens
   vérifiés. Décrire honnêtement les limites Apple et appareil physique.

Références : [insets Android](https://developer.android.com/develop/ui/views/layout/edge-to-edge),
[notifications](https://developer.android.com/develop/ui/compose/notifications/notification-permission),
[EOX](https://maps.eox.at/), [Open-Meteo](https://open-meteo.com/en/docs).

## Ce qui fonctionne

- Menu paramètres animé ↔ croix, retour à l'écran et à la position précédents,
  fermeture du dialogue par Retour et sauvegarde finale avant sortie.
- Détails Finder en langage lisible, marges de 20 px, résultats déjà montés gardés
  lors de Voir plus/moins. Défilement optimisé par rendu des cartes visibles.
- Carte : densité Canvas bornée à 1,75, frontières simplifiées pendant les gestes,
  détail après leur arrêt ; options satellite/vent, sources et replis locaux.
- Vol orienté préparation : résumé du trajet, accès rapide Finder/Fuel/carte,
  idées Court/Nuit basées sur les vrais critères Finder, pistes locales consultables.
- Carnet chronométré explicite avec pause/reprise, sessions conservées et vols
  terminés confirmés. Aucune heure déduite des recherches ou des vols seulement choisis.
- Dix palettes partagées Windows/Android, clair/sombre et barre de défilement
  assortie. Trois icônes Android, rappel de préparation local facultatif.
- Sélecteurs recherchables, recherche SQLite aéroports/compagnies, détails carburant
  lisibles. Sauvegarde après 180 ms/navigation, sans bibliothèque renvoyée par caractère.
- Brouillons de design/signalement conservés ; introduction humoristique en deux
  étapes Android et bouton Revoir sur les deux plateformes. Qt ignore les événements
  de méthode de saisie vides qui pouvaient fermer le décor avant une action utilisateur.

Les onglets existants sont conservés. Aucun téléchargement de base, compte,
télémétrie ou permission générale de stockage. Les formules Fuel et moteurs de
messages Windows restent la référence ; les couches météo ne les modifient pas.

## Fichiers principaux

- `android/app/src/main/assets/www/experience.js`, `online-map.js`, `app.js`,
  `app.css`, `map.js`, `index.html` : interface, sauvegarde, détails, carte.
- `MainActivity.java`, `OnlineMap.java`, `FlightReminder.java`, manifeste et icônes :
  conteneur avec insets, pont local, services facultatifs, notifications/lanceur.
- `visual_themes.py`, `flight_planning.py`, `map_services.py` : catalogue partagé,
  pistes/carnet et règles des fournisseurs extraites du service Qt.
- `appearance.py`, `storage.py`, `ui.py`, `flightdeck.py`, `dialogs.py` : palettes
  Windows et accueil, sans remplacer PySide6.
- `android_engine.py`, `scripts/prepare_android.py`, tests Python/Playwright/natifs,
  `scripts/test_android_connected.py`, workflow Android : export automatique,
  stockage privé, logique et tests bornés avec diagnostics.
- `docs/INSTALLATION.md`, `DISTRIBUTION.md`, README Android/parité/README principal :
  téléchargement, premiers pas, sauvegardes, dépannage, builds et limites.

## Vérifications

| Contrôle | Résultat |
|---|---|
| Windows, suite complète historique et ajouts | 116 tests passent, 46,8 s localement |
| Android Python | 25 tests passent ; 1 344 combinaisons PC et 504 extensions |
| UI classique et nouveau parcours | Deux parcours passent ; zéro erreur JS |
| Nouveau parcours | Menu/position, Finder lisible, palettes, sélecteurs, pistes, carnet, relance, brouillons, dernier caractère avant sortie, blague avant conclusion et relecture |
| Carte sur Chrome, densité simulée ×3 | Dessins mesurés à 0,5–1,8 ms ; pas une garantie sur téléphone physique |
| APK locale | assembleDebug + assembleDebugAndroidTest réussis ; 62 132 906 octets |
| Contenu APK | Base 94 892 032 octets, SHA-256 vérifié, 242 frontières et scripts locaux présents, quatre permissions attendues |
| Windows empaqueté | Démarrage, FR/EN, sombre/clair, Finder 577 résultats, Fuel 12 285 kg, carte 97 points et frontières passent dans un profil temporaire |
| Android installé API 35, mode avion | Quatre tests principaux passent : moteur/Finder/Fuel/relance, presse-papiers exact, carte réelle, viewport hors barres ; notification/icône vérifiées séparément en dernier |
| Arrêt complet/reprise | Même JSON privé, formulaire WebView rendu, EJU149U et carburant 12285 conservés |
| Services réels Android, activation explicite | Un test passe : JPEG EOX et vent 250 hPa, UTC/hauteur AMSL |
| Analyse locale Bandit | Aucun résultat de gravité moyenne/haute ; résultats faibles conservés dans le journal |

Preuve installée sur le code `e217bb3b2dd5aa288bf3a2d48a6d34bbba5f5846` :
[Android 0.4](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37202466420),
[Windows 0.4](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37202466582),
[tests et dépendances](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37202466338)
et [CodeQL](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37202466373) réussissent.
Les quatre tests principaux sont rejoués après réinstallation, puis le processus
est arrêté et relancé. Le test en ligne attend la connexion Wi-Fi réelle après
le mode avion ; le test des icônes/notifications est exécuté en dernier, car un
changement de composant peut relancer les tâches Android. Aucun test historique
n'est supprimé. La fermeture native détruit sa WebView ; les tests sont bornés
et retiennent logcat en échec. Ces précautions du banc de test ne garantissent
pas encore la fluidité sur tous les téléphones.

## Téléchargements vérifiés

- [APK Android 0.4](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37202466420/artifacts/11303686722).
- [ZIP Windows 0.4](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37202466582/artifacts/11302894282).
- [Installation simple et dépannage](../INSTALLATION.md).

Ces artefacts demandent une connexion GitHub et expirent après 30 jours.
Les sources sont sur la branche `feat/flightdeck-map-performance` et la
[PR 2](https://github.com/nmg06/rfs-atc-message-maker/pull/2). Aucune fusion/release publique.

## Commandes et livraison locale

Depuis la racine du dépôt, après les prérequis du README Android :

```powershell
python scripts/prepare_android.py
.\android\gradlew.bat -p android assembleDebug assembleDebugAndroidTest
python -m PyInstaller --noconfirm --clean RFSATCMessageMaker.spec
python scripts/package_windows.py --archive dist/RFSFlightdeck-Windows-0.4.0-x64-test.zip
```

APK générée : `android/app/build/outputs/apk/debug/app-debug.apk`.
Livraison utilisateur : `../livraison-flightdeck/RFSFlightdeck-Android-0.4.0-debug.apk`,
ZIP Windows `../livraison-flightdeck/RFSFlightdeck-Windows-0.4.0-x64-test.zip`,
application extraite `../livraison-flightdeck/PC-0.4/RFSFlightdeck/RFSATCMessageMaker.exe`.
Les anciennes livraisons sont conservées, avec copie du profil de test avant reprise.
Les APK locales conservent la même signature debug ; celle de GitHub peut différer.

## Ce qui reste

- Tester sur le téléphone de l'utilisateur : clavier/paysage/encoches variées,
  confort du défilement et des couches en ligne, import multiple/photos/partage.
- Rappels : vérifier l'arrivée à l'heure prévue, l'économie de batterie et le reboot
  sur appareil physique. Pas d'alertes vent ni recommandations automatiques en arrière-plan.
- Les pistes publiques sont consultables ; aucune base des portes/affectations
  RFS, contraintes avion/compagnie ou performances permettant une sélection fiable.
- Satellite annuel/non commercial ; disponibilité externe. Vents : échantillons,
  prévisions réelles pouvant différer du jeu ; pas d'ajustement automatique Fuel/ETE.
- Quelques libellés techniques restent non traduits ; icône Windows fixe et carnet/
  rappels nouveaux limités à Android. Import/export natif doit être essayé sur téléphone.
- Clé Android de distribution stable et release publique à préparer avec le propriétaire.
- iPhone : hôte Python iOS ou port du moteur, Mac/Xcode/signature Apple et tests
  spécifiques nécessaires ; aucune application iOS installable livrée sur cet hôte.

Prochaine étape : vérifier cette APK sur le téléphone concerné, puis traiter
les sélecteurs/partage et écarts physiques recensés avant une distribution publique.
