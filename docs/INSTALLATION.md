# Installer RFS Flightdeck

Ancien nom : RFS ATC Message Maker. Le nom change, les fichiers de données et
l'identifiant Android restent compatibles. Versions de test, sans compte dans
l'application, sans télémétrie. Aucune publication Google Play/App Store.

## Télécharger depuis GitHub

Paquets vérifiés le **3 octobre 2026**, version `0.3.0-flightdeck` :

- [Télécharger Windows x64](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37151621344/artifacts/11284226950).
- [Télécharger Android APK](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37151621335/artifacts/11283749270).
- [Preuves 0.3, commandes et limites](android/PROGRESS_0.3.md).

Ces liens correspondent au commit `6bdc5a8` et expirent le **2 novembre 2026**.
Leur téléchargement demande une connexion GitHub. Pour retrouver les builds suivants :

Sur https://github.com/nmg06/rfs-atc-message-maker/actions :

1. Choisissez **Flightdeck Windows test package** pour le PC, ou **Android offline APK** pour Android.
2. Ouvrez une exécution verte de la branche `feat/flightdeck-map-performance`.
3. En bas, dans **Artifacts**, téléchargez `RFSFlightdeck-Windows-x64-test` ou `RFS-ATC-Android-debug`.
4. Décompressez l'artefact. Les fichiers utiles sont le ZIP portable Windows et `app-debug.apk`.

GitHub demande une connexion pour télécharger ses artefacts ; l'application
elle-même n'en demande aucune. Les artefacts expirent après 30 jours. Le workflow
peut être relancé depuis **Run workflow**. Une future release permettra des liens
de téléchargement durables ; aucune release publique n'est créée automatiquement
par ces nouveaux workflows. La première branche Android `feat/android-offline`
fournit également une APK testée, avant les améliorations Flightdeck.

## Windows 10/11, 64 bits

1. Décompressez `RFSFlightdeck-Windows-x64-test.zip` dans un **nouveau dossier** local.
2. Ouvrez `RFSFlightdeck/RFSATCMessageMaker.exe`.
3. Gardez `_internal`, `finder-data` et `docs` à côté de l'exécutable. Le seul EXE ne suffit pas.
4. Python n'est pas nécessaire. Finder et Fuel Helper utilisent les données incluses.

Pour tester une nouvelle version, gardez votre ancien dossier intact. Ses quatre
fichiers `data/rfs_state.json`, `rfs_history.json`, `rfs_presets.json`,
`rfs_designs.json` peuvent être copiés dans le nouveau dossier `data` **après avoir
fermé normalement l'ancienne application et fait une copie de sauvegarde**.
N'écrasez pas un dossier déjà ouvert dans une autre version.

Les données restent dans `data` à côté de l'EXE, sauf si
`RFS_MESSAGE_MAKER_DATA_DIR` désigne un autre dossier. Un dossier local hors
OneDrive évite les ralentissements de synchronisation.

## Android 7 ou plus, ARM64 / x86_64

1. Téléchargez et décompressez l'artefact pour obtenir `app-debug.apk` (la copie locale peut s'appeler `RFSFlightdeck-Android-0.3.0-debug.apk`).
2. Branchez le téléphone au PC avec un câble USB, déverrouillez-le et choisissez **Transfert de fichiers** dans sa notification USB.
3. Sur le PC, ouvrez le téléphone dans l'Explorateur et copiez l'APK dans **Stockage interne > Download / Téléchargements**.
4. Sur le téléphone, ouvrez **Fichiers > Téléchargements**, puis touchez l'APK. Autorisez **Installer depuis cette source** si Android le demande et appuyez sur **Installer**.
5. Touchez **Ouvrir**, ou retrouvez **RFS Flightdeck** dans la liste des applications du téléphone. Vous pourrez ajouter son icône à l'écran d'accueil.
6. Testez en mode avion : messages, copie, carte/frontières, Finder et Fuel Helper restent disponibles. Le premier lancement initialise la base embarquée et peut être plus long.

APK debug destinée aux essais. La signature debug d'un build local et celle d'un
autre environnement de build peuvent différer. Si Android refuse une mise à jour
pour incompatibilité de signature, exportez les données **avant** de désinstaller.
Une désinstallation efface le stockage privé. Une future APK de distribution
nécessitera une clé stable détenue par le propriétaire du projet.

Dans **Paramètres**, export/import permet de sauvegarder les données privées.
Le bouton **Importer les 4 fichiers PC** accepte `rfs_state.json`, `rfs_history.json`,
`rfs_presets.json` et `rfs_designs.json`, préalablement copiés depuis le dossier
`data` d'une application PC fermée. Le lot est validé avant remplacement ; le
sélecteur multiple reste à vérifier sur téléphone physique. Aucune permission
Internet ou accès général au stockage n'est demandée par l'APK.

## iPhone / iPad

**Aucune application iOS installable n'est livrée pour l'instant.** Une APK est
réservée à Android. Le vieux prototype `mobile/index.html` n'a pas la parité avec
Flightdeck et ne remplace pas l'application native hors ligne.

Le moteur Android utilise Chaquopy, qui ne fournit pas le même hôte Python pour
iOS. Une vraie version iPhone demandera un hôte Python compatible iOS ou un port
du moteur, puis un Mac avec Xcode et la signature Apple. TestFlight et App Store
requièrent aussi la configuration Apple correspondante. Ne promettez pas un
fichier iPhone utilisable depuis le build Windows/Android actuel.

## Carte et Internet

Windows : carte vectorielle, frontières, zoom et sélection des pays fonctionnent
hors ligne. Choisissez les deux pays puis **Trouver ces vols** : Finder reçoit les
critères et recherche uniquement dans la base réelle, sans inventer de vol.

**Satellite 2025** et les **vents par niveau de pression** sont des options
Internet désactivées au départ. Les téléchargements se font en arrière-plan.
Les images EOX sont sous CC BY-NC-SA 4.0, pour l'usage non commercial ; les vents
Open-Meteo sont des prévisions du monde réel, qui peuvent différer de RFS. Les
altitudes sont en mètres AMSL ; le niveau de pression n'est pas une altitude fixe.
Les vents ne changent pas les durées historiques ni les formules Fuel Helper.
Android possède aussi la carte vectorielle, les frontières, le zoom/pincement,
le trajet et la sélection des pays hors ligne. Les options satellite et vents
restent uniquement sur Windows.

Voir [Android](android/README.md), [parité](android/PARITY.md) et
[changements Flightdeck](FLIGHTDECK_NEXT.md) pour les détails et limites.
