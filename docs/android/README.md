# RFS Flightdeck — Android

Première application Android hors ligne, développée à côté de Windows dans
`android/`. Le prototype `mobile/index.html` reste séparé et incomplet. État vérifié et
limites : [PARITY.md](PARITY.md). Audit et choix :
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Architecture

Une Activity Android Java affiche une nouvelle interface mobile HTML/CSS/JS
locale. Chaquopy 16.1.0 embarque CPython 3.11 et les mêmes moteurs Python que Windows :
génération, validation, pilotes, Finder, mapping et calcul carburant.
Seuls les libellés Qt ont un adaptateur Android. Pas de React, Capacitor, npm
en production, PySide6, serveur ou EXE Windows exécuté sur Android.

Le presse-papiers, le partage texte, les sélecteurs de documents/images et les
exports utilisent Android. L'APK contient tous les scripts, styles, icônes,
données SQLite/JSON et fuseaux IANA. Aucune police/CDN externe, télémétrie,
permission générale de stockage. Depuis 0.4, Internet sert uniquement aux couches
satellite/vents facultatives ; aucune requête fournisseur sans activation. Le formulaire externe
facultatif s'ouvre uniquement à la demande dans le navigateur du téléphone.

Android 7.0 minimum (API 24), appareils **ARM64** et émulateurs **x86_64**,
avec **Android System WebView / Chrome 80 minimum** et les API locales vérifiées
au démarrage. Un moteur trop ancien affiche une aide locale et conserve les
données ; mettez à jour WebView avant de relancer. Les essais natifs documentés
utilisent API 35, pas tous les modèles de téléphone.
L'APK debug universelle contient les deux architectures, environ
106 Mo pour le build local du 7 octobre, avec la base enrichie de 138 Mo
décompressée. Prévoir au moins 500 Mo libres pour l'installation et la base privée.

Candidate Flightdeck `0.4.3-flightdeck`, identifiant `com.nmg06.rfsatc` conservé.
Catalogue d'avions recherchable dans le vol, variante unique Finder préremplie
dans Fuel, recherches mises en cache et boutons Voir plus/Voir moins.
Dans le Finder, `10` signifie 10 heures ; les formats explicites restent acceptés.
[Guide d'installation Windows/Android et état iPhone](../INSTALLATION.md).

Cette version ajoute la carte vectorielle hors ligne avec les mêmes 242 frontières
Natural Earth que Windows, trajet orthodromique partagé, glissement/zoom au doigt,
pincement et cadrage conservé. Choisir les pays puis **Trouver ces vols** transmet
les critères au Finder local ; les autres filtres restent actifs. Les couches
satellite/vents sont disponibles en option sur Android depuis 0.4, désactivés au
départ. EOX 2025, vents Open-Meteo par pression/hauteur AMSL, date UTC, cache et
rafraîchissement limité ; requêtes sur une file distincte du moteur. Les fonctions
principales restent hors ligne. Voir [bilan 0.4](PROGRESS_0.4.md).

Le conteneur natif réserve l'espace des barres système, de l'encoche et du clavier.
Le bouton paramètres devient une croix et revient à l'écran/position précédents.
Les détails Finder sont lisibles ; résultats conservés à l'ajout des pages,
géométrie allégée pendant les gestes et densité Canvas limitée à 1,75.
Les saisies sont sauvegardées après 180 ms et lors de la navigation/mise en veille,
sans renvoyer toute la bibliothèque à chaque caractère. Le vol reste conservé
sans utiliser le bouton Sauver ; ce bouton nomme un vol pour le rappeler ensuite.

Dans **Bibliothèque** : renommage/suppression des vols et favoris, ajout/modification/
suppression des pilotes connus avec préférences, gestion des designs et nettoyage
de l'historique. Supprimer un vol sauvegardé garde le vol actuel. Les drapeaux
disposent d'un catalogue recherchable par nom/code, et les panneaux ouverts restent
ouverts lors des changements du formulaire.

PUSHBACK/TAXI partagent maintenant les designs/longueurs/emojis, designs personnels
et règles de groupes/parallèle ; ATIS utilise la même présentation et valide
ICAO, lettre d'information, piste et QNH. Ces trois modèles sont des extensions
Android, sans équivalent Windows servant de référence.

## Construire

Depuis 0.4.1, un tutoriel de huit rubriques et 30 questions fréquentes suit la
langue choisie. On peut passer l’aide puis la retrouver dans les paramètres.
Les alertes de validation ouvrent les champs concernés ; Vérifier avant copie
permet de choisir une copie libre, avec alertes conservées. Voir [utilisation](../HELP.md).

Les contenus bilingues viennent de `help_content.py`. `scripts/export_help.py`
produit les mêmes fichiers locaux pour Android et le prototype web, avec les
constantes et références du calcul Fuel web dérivées automatiquement du PC.

Prérequis de développement uniquement : Git, Python **3.11**, JDK **17**,
Android SDK avec platform 35/build-tools 35.0.0 et licences acceptées. JDK 21
fonctionne également pour le build local. Certaines versions récentes du
gestionnaire SDK demandent JDK 21 pour installer les composants.
Internet sert au téléchargement initial des outils/dépendances de build.
À l'utilisation, seules les couches satellite/vents activées et le formulaire
externe facultatif demandent une connexion.

Depuis la racine du dépôt, PowerShell :

```powershell
python -m pip install tzdata==2026.4
python scripts/prepare_android.py
$env:ANDROID_HOME = 'C:\Android\Sdk' # votre SDK
$env:JAVA_HOME = 'C:\Java\jdk-17'    # votre JDK
$env:RFS_BUILD_PYTHON = (Get-Command python).Source
.\android\gradlew.bat -p android assembleDebug assembleDebugAndroidTest
```

Linux/macOS :

```sh
python -m pip install tzdata==2026.4
python scripts/prepare_android.py
export ANDROID_HOME=/path/to/android-sdk
export JAVA_HOME=/path/to/jdk-17
export RFS_BUILD_PYTHON="$(command -v python)"
chmod +x android/gradlew
cd android
./gradlew --no-daemon assembleDebug assembleDebugAndroidTest
```

APK : **`android/app/build/outputs/apk/debug/app-debug.apk`**.
Pour la future APK de distribution signée, consultez [SIGNING.md](SIGNING.md).
Le workflow manuel de candidate ne publie rien automatiquement.
Gradle 8.9 est fourni par le wrapper avec contrôle SHA-256. Les versions AGP,
Chaquopy, WebKit et tzdata sont épinglées. Les sources partagées et leurs hashes
sont préparés automatiquement dans `app/build/generated` ; ne les modifiez pas.
Python de build doit être 3.11 pour compiler le bytecode à l'avance ; un build
avec 3.12 peut réussir mais annonce qu'il embarque les sources Python.

Le workflow **Android offline APK** (`.github/workflows/android.yml`) construit
l'APK et l'artefact **RFS-ATC-Android-debug**, puis exécute les tests sur un
émulateur API 35. Il ne publie aucune release ni application Google Play.
Les workflows Windows ne sont pas modifiés. Une future release pourra joindre
le ZIP Windows et l'APK ; la signature release et sa clé restent à configurer.
L'APK debug locale et celle de GitHub peuvent avoir des signatures différentes :
exportez vos données avant de désinstaller pour changer de provenance.

Build et installation vérifiés le 3 octobre 2026 sur émulateur API 35 en mode
avion : moteurs, Finder/Fuel, carte locale/frontières, presse-papiers, arrêt complet/relance du processus
et affichage du vol restauré passent.
[Exécution Flightdeck 0.3 et artefacts](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37151621335),
commit `6bdc5a8`, trois tests natifs ; [bilan de livraison](PROGRESS_0.3.md).
La version 0.4 est également installée et testée le 4 octobre 2026 : quatre
tests principaux en mode avion, arrêt complet/reprise, puis services réels
facultatifs et notification/icône séparément. Toutes ces vérifications passent.
[Exécution 0.4 et artefacts](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37202466420),
code testé `e217bb3` ; [preuves et limites physiques](PROGRESS_0.4.md).
La base gzip est embarquée sous `assets/aviation.database` pour éviter que AAPT
décompresse/renomme automatiquement les fichiers portant l'extension `.gz`.
`scripts/verify_android_apk.py` vérifie le contenu réel et les seules permissions
attendues pour la version actuelle, détaillées plus bas.

## Installer et utiliser

Téléchargez/récupérez l'APK, ouvrez-la sur le téléphone et autorisez cette source
à installer des applications. Avec ADB :

```sh
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n com.nmg06.rfsatc/.MainActivity
```

Le premier lancement décompresse la base locale puis initialise Python.
Onglets : Vol, Carte, Messages, Aperçu, Finder, Fuel, Bibliothèque ; paramètres en haut.
Les champs et préférences sont enregistrés après chaque modification.
La copie utilise le vrai presse-papiers Android ; collez ensuite dans Discord.
Avec **Vérifier avant copie** activé, les erreurs et limites empêchent la copie.
Désactivez cette option pour copier un texte incomplet avec alertes conservées.

## Stockage et sauvegarde

Le stockage privé `/data/user/0/com.nmg06.rfsatc/files/` contient
`rfs_android.json` et `aviation.sqlite`. Les préférences FR/EN/thème, pseudo,
pilotes, vol, champs des messages, aperçus édités, vols enregistrés, historique,
favoris, designs, critères Finder et dernières entrées Fuel sont conservés.
Le cadrage et les pays sélectionnés sur la carte sont également conservés.

**Importer les 4 fichiers PC** ouvre le sélecteur Android avec sélection multiple.
Copier auparavant les fichiers `rfs_state.json`, `rfs_history.json`, `rfs_presets.json`
et `rfs_designs.json` depuis le dossier `data` d'une application PC fermée normalement,
puis sélectionner les quatre ensemble. Les noms doivent rester identiques.
Tout le lot est validé avant remplacement ; limite totale 2 Mo et copie locale
`.before-import.json` conservée. Les anciennes préférences de langue PC sont adaptées.
Ne pas sélectionner un journal, la base Finder ou le dossier entier.
L'écriture JSON est atomique ; un fichier corrompu est conservé pour récupération.
L'historique garde les 200 dernières entrées.

Paramètres > Exporter une sauvegarde utilise le sélecteur Android. La 0.4.2
exporte le format commun `rfs-flightdeck-backup`, importable également sur PC.
Importer montre un résumé puis propose **Fusionner** ou **Remplacer** et valide
le JSON (limite 2 Mo). Une
sauvegarde privée antérieure à l'import est également conservée. Une
désinstallation/effacement des données supprime tout : exportez avant.
Les sauvegardes cloud Android sont désactivées.

Les préférences de vérification des mises à jour sont natives et propres à
l’appareil. Elles sont désactivées au départ, indépendantes du mode avion et
absentes de la sauvegarde transférée. Le réseau HTTPS GitHub est utilisé
uniquement après action manuelle ou activation de la vérification quotidienne.
Les drapeaux Internet satellite/vents restent également ceux de l’appareil cible
après import. [Guide mises à jour et transfert](../UPDATES_AND_TRANSFER.md).

L'ancien import d'un seul état Windows reste disponible : sélectionnez `data/rfs_state.json`.
Les vols/pilotes/préférences de ce fichier sont adaptés, mais l'historique,
les favoris et les designs des fichiers Windows séparés ne sont pas importés
automatiquement. Les designs JSON s'importent séparément dans Paramètres.

## Flight Finder

`android/bundled/aviation.sqlite.gz` contient le snapshot SQLite local fourni,
94 892 032 octets décompressés. Son manifeste contrôle la taille et SHA-256 ;
copie dans le stockage privé au premier lancement, recherche en lecture seule.
Aucun téléchargement. Tous les critères publics du moteur PC sont exposés,
avec pages de 100 résultats. **UTILISER CE VOL** appelle le mapping PC et préserve
les champs manuels inconnus. Vérifiez portes, pistes, pilotes et carburant gardés.

Ce sont des données historiques, pas des horaires actuels. Une partie des durées
du snapshot est compatible avec l'estimation distance/390 kt + 15 minutes ;
les détails l'indiquent sans présenter les bornes arithmétiques comme de la
précision observée. Les pistes affichées sont celles disponibles dans la base,
pas celles utilisées par le vol. Aucun résultat synthétique n'est ajouté.
Sources/licences : `android/bundled/`, `docs/licenses/`, intégrées à l'APK.

Changer intentionnellement le snapshot de développement :

```sh
python scripts/prepare_android.py --database /path/to/aviation.sqlite
```

Le script vérifie intégrité/schema, compresse de façon déterministe et copie les
notices fournies à côté de la base. L'APK n'inclut pas le pipeline ETL/réseau.

## RFS Fuel Helper

Les 63 variantes et 64 arrivées proviennent automatiquement des fichiers suivis
`docs/fuel/reference/`. `fuel/data/` est une copie générée de ces références,
également livrée pour que Windows fonctionne depuis un clone neuf.
Le calculateur PC, les alternates statiques et l'arrondi half-even sont conservés.
A220-300 / 5 h / EGLL : **12 285 kg**, EGKK à 30 NM.
Appliquer avion + carburant recalcule les entrées actuelles et conserve le détail
non arrondi avec le vol. Arrivée inconnue : alternate à zéro, sans donnée inventée.
**Outil pour RFS/simulation uniquement, jamais pour préparer un vol réel.**

## Rapports et images

Le rapport ZIP est local : uniquement les textes saisis et, après consentement,
jusqu'à cinq images choisies via le sélecteur Android (10 Mo/image maximum).
Aucun journal, vol ou image ajouté/envoyé automatiquement. Les images choisies
pour un rapport ne sont pas conservées après recréation de l'écran/activité.

## Tests

```sh
python scripts/prepare_android.py
python -m unittest discover -s android/tests -v
python -m unittest discover -s tests -v
node --check android/app/src/main/assets/www/app.js
cd android
./gradlew connectedDebugAndroidTest
```

La suite Android compare 1 344 combinaisons de messages PC, validations/groupes,
la recherche et le mapping réels, les 63 avions, restauration/import et absence
de réseau. L'instrumentation teste démarrage, base embarquée, Finder, Fuel,
relance d'activité et presse-papiers natif.
`scripts/test_android_restart.py` vérifie en plus l'arrêt complet du processus,
la conservation du JSON et le rendu WebView restauré en mode avion, exclusivement
sur un émulateur dédié (il réinstalle l'application de test).
Pour le parcours UI sur ordinateur,
`python android/tests/ui_server.py` affiche un port local temporaire ; dans un
autre terminal : `node android/tests/ui_browser.cjs PORT screenshot.png`
(profil de test neuf pour l'accueil), puis `node android/tests/experience_browser.cjs PORT`.
(Playwright avec Chromium installé, ou `RFS_TEST_BROWSER=chrome`). Ce serveur
de test ne fait pas partie de l'APK.

## Limites

PUSHBACK/TAXI/ATIS sont des extensions Android sans équivalent dans le schéma PC :
leurs champs, validation, longueur/emojis, designs personnels et opérations
multi-pilotes de départ sont portés et testés, sans prétendre une parité PC inexistante.
Les composants carburant et certains avertissements techniques ne sont pas tous
traduits. Les extensions utilisent désormais les présentations et groupes décrits
plus haut ; les anciennes limitations 0.2/0.3 ne s'appliquent plus.
Les sélecteurs/photos/partage et le confort sur les divers téléphones physiques
restent à confirmer. Les portes ne sont pas présentes dans la base aviation ;
la longueur/surface des pistes n'autorise pas une affectation automatique pour un
avion/une compagnie. iOS demande une chaîne Apple distincte, absente de cet hôte.

## Personnalisation et préparation sans ATC

Dix palettes partagées PC/Android, chacune avec un mode clair/sombre ; trois
icônes de lanceur Android. La vitesse d'actualisation de l'icône dépend du lanceur.
Le bouton retour ferme le dialogue actif avant de changer d'écran.
Le carnet conserve les sessions démarrées/pausées/terminées par l'utilisateur,
avec durée chronométrée et trajet. Aucune heure de vol n'est déduite des recherches.
Les idées Court/Nuit définissent seulement la durée du Finder et gardent ses autres
critères ; résultats exclusivement issus de la base historique.

Le rappel de préparation est local, facultatif, à une date choisie, pour le vol
actuel. Android 13+ demande l'autorisation uniquement lors de sa programmation.
Un seul rappel remplaçable ; annulation dans Paramètres. Horaire approximatif,
potentiellement retardé par économie de batterie ; pas d'alarme exacte ni recherche
de vol/météo en arrière-plan. Reprogrammé après redémarrage si encore futur ;
après un arrêt forcé Android, reprogrammez-le dans les Paramètres. Les réglages du
canal Android permettent aussi de couper le son/les notifications.

Permissions 0.4 : `INTERNET`, `POST_NOTIFICATIONS`, `RECEIVE_BOOT_COMPLETED` et
permission de signature propre au paquet, ajoutée par AndroidX pour protéger les
receivers internes. Pas de localisation, contacts, compte, photos globales ou stockage.

Accueil : billet fictif affiché avant sa conclusion ; aucune saisie ni paiement.
Après cette première présentation, la blague ne se rejoue pas toute seule.
Paramètres > Revoir la blague de bienvenue permet de la revoir volontairement.
Sur Windows : Aide et suggestions > Revoir la blague.

## Catalogue de routes du 7 octobre 2026

Flight Finder propose aussi un catalogue distinct de routes récentes observées.
Le moteur et la base sont les mêmes sur PC et Android. Les valeurs absentes
(avion/durée) restent inconnues ; les valeurs manuelles du vol sont conservées.
Voir [sources, utilisation et vérifications](../DATA_ENRICHMENT_2026-10-07.md).
APK de test reconstruite : `android/app/build/outputs/apk/debug/app-debug.apk`.
La nouvelle APK doit encore être essayée sur téléphone physique avant publication.
