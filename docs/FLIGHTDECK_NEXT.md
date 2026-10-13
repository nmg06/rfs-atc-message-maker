# Flightdeck : carte et réactivité

Demande du 3 octobre 2026, après livraison Android. La copie de développement
part de la version Flightdeck locale vérifiée, avec les 71 tests GitHub conservés
et ses tests supplémentaires : **103 tests de référence passent**.
Le profil et l'EXE quotidiens ne sont pas modifiés. Branche séparée de l'Android.

## Changements implémentés

1. Mesurer Air France / pages et changement clair-sombre sur la vraie base locale.
   Résoudre les compagnies via l'index SQLite, garder population/classement et
   calculer une fois par recherche. Pages suivantes en mémoire, boutons voir
   plus/moins sans refaire le SQL. Invalidation sur modification des critères/base.
2. Dans les champs min/max/cible du Finder, un nombre seul signifie des heures
   (10 = 10 h), avec libellé explicite ; tolérances restent en minutes. Conserver
   les anciens formats explicites et le parseur bas niveau historique.
3. Catalogue de recherche des 63 variantes dans le vol courant. Préremplir Fuel
   depuis le vol, y compris un type Finder si sa correspondance RFS est unique.
   Les types ambigus demandent le choix parmi leurs variantes, sans inventer
   une consommation. Déclarer et conserver l'origine du choix.
4. Carte vectorielle locale : frontières Natural Earth, pays identifiables,
   zoom jusqu'au niveau détaillé, zoom centré sous le pointeur, sélection de
   pays départ/arrivée et transfert immédiat vers les critères Finder.
   Le trajet du vol reste basé sur les aéroports réellement sélectionnés.
5. Satellite facultatif : tuiles visibles uniquement, chargement asynchrone,
   cache borné, attribution du fournisseur et repli sur la carte locale en panne.
6. Vents facultatifs : prévisions Open-Meteo, niveaux de pression/altitudes,
   flèches sur la zone affichée et le trajet, date UTC visible et rafraîchissement
   raisonnable avec cache. Distinguer ces prévisions de la météo RFS ; afficher
   le vent arrière/de face sans modifier les durées historiques ou le calcul Fuel.
7. Thème : conserver le style Qt, éviter reconstructions, afficher puis différer
   l'enregistrement ; mesurer la latence et conserver les champs/aperçus.
8. Nom affiché **RFS Flightdeck**, identifiants et dossiers de données conservés
   pour éviter une migration involontaire. Build Windows d'essai séparé et tests.

Ce bilan décrit l'étape 0.3. Depuis 0.4, Android propose aussi satellite et vents
facultatifs avec permission Internet ; ils restent désactivés tant que l'utilisateur
ne les choisit pas. Les fonctions principales restent hors ligne.

## Vérifications et mesures

- Suite Windows : **114 tests passent**, aucun test historique supprimé ; trois suites
  complètes après correction du cycle des traducteurs Qt.
- Android : **22 tests Python**, parité des 1 344 générations et 504 extensions,
  Finder cache, préremplissage avion/carburant, carte locale, bibliothèque et import PC.
  Trois tests natifs et arrêt/relance passent sur API 35 en mode avion :
  [bilan 0.3](android/PROGRESS_0.3.md). Les couches Internet sont exclues de l'APK.
- Comparaison avec le code Flightdeck public précédent, même SQLite et même heure :
  Air France **3,82 s → 0,155 s**, page suivante **0,016 s** ; France→Roumanie
  **7,86 s → 0,152 s**. Toutes les réponses comparées sont identiques, y compris
  ordre, scores, avertissements, décompte et pagination. Détails : [mesures](finder-performance.json).
- Changement de thème et traitement du rafraîchissement : environ **0,4 s**
  sur ce poste, écriture différée. Ce n'est pas une garantie de zéro délai sur tout PC.
- Vérification sur les vrais fournisseurs : six tuiles EOX rendues, 17 points
  Open-Meteo à 250 hPa, altitude géopotentielle et prévision datée. Les flèches
  représentent des échantillons, sans inventer une météo continue ou une météo RFS.
- Sélection FR→RO : critères du Finder transmis, vol actuel conservé.
- Le parseur de durée Fuel Windows est extrait dans `fuel/duration.py` et partagé
  avec Android : nombres simples en heures, décimales, HH:MM et heures/minutes
  donnent les mêmes résultats. Le calcul Android accepte aussi `330min` explicite.

Les noms des EXE, fichiers de profil et package Android sont conservés. Le nom
affiché devient RFS Flightdeck. Les livraisons restent des paquets d'essai
séparés ; l'installation quotidienne n'est pas modifiée.

## Construire / distribuer

Windows : `python -m PyInstaller --noconfirm --clean RFSATCMessageMaker.spec`, puis
`python scripts/package_windows.py`. Sortie : `dist/RFSFlightdeck-Windows-x64-test.zip`.
APK : `android/gradlew.bat -p android assembleDebug` ; sortie
`android/app/build/outputs/apk/debug/app-debug.apk`.

[Instructions d'installation Windows, Android, état iPhone](INSTALLATION.md).
Le workflow Windows d'essai construit, emballe la base publique, lance le test
de démarrage dans un profil temporaire et met le ZIP en artefact. Les workflows
de release existants sont conservés, aucune nouvelle release n'est déclenchée.

## Limites restantes

- Pays sans vols dans la base : résultat vide, pas de vol synthétique.
- Frontières Natural Earth 50m : zoom possible, sans ajouter rues/bâtiments aux données vectorielles.
- Satellite EOX 2025 : service externe, mosaïque annuelle, cache mémoire de 128 tuiles,
  licence non commerciale et disponibilité dépendant du fournisseur ; aucun téléchargement massif.
- Vent : prévision horaire réelle, grille visible et trajet, huit recherches en cache,
  rafraîchissement toutes les 15 min seulement si activé. Les formules Fuel et durées historiques restent inchangées.
- Android 0.4 : satellite/vents facultatifs ajoutés ; [preuves et limites](android/PROGRESS_0.4.md).
  iOS natif non construit. Les nombres de tests ci-dessus correspondent à l'étape 0.3.
