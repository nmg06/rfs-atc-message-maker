# RFS Flightdeck 0.4.2 — sauvegardes et mises à jour

Compte rendu du 4 octobre 2026. La version de test se construit sur Windows et Android. Les vérifications ci-dessous portent sur le commit `58495ee1c78cb68df5e73e15fa1bf3f6fd5f8601`.

## Ce qui a été ajouté

- **Une sauvegarde commune PC ↔ Android.** Un seul fichier JSON transporte le vol actuel, les vols sauvegardés, les pilotes, les préférences, l’historique, les designs et les aperçus modifiés. Les anciens exports Android et les quatre fichiers JSON PC restent acceptés.
- **Un aperçu avant importation.** L’application présente la provenance et le nombre d’éléments avant de proposer **Fusionner** ou **Remplacer**.
- **Ajouter sans perdre le brouillon actuel.** Les conflits restent disponibles sous des entrées distinctes. Un autre vol en cours est conservé dans les vols sauvegardés, avec son aperçu et sa présentation. Réimporter la même sauvegarde ne multiplie pas ces entrées.
- **Remplacer avec une copie de sécurité.** Une sauvegarde locale datée précède l’importation. Sur Windows, un journal permet de restaurer les quatre fichiers après une écriture interrompue. Sur Android, le fichier principal est remplacé de façon atomique.
- **Conserver les particularités Android.** PUSHBACK, TAXI et ATIS restent présents dans les données. Le PC affiche un type qu’il sait générer et conserve la sélection Android pour un transfert de retour.
- **Vérifier les mises à jour.** La consultation de GitHub est facultative. La vérification automatique demande un choix explicite et ses réglages restent propres à chaque appareil. Importer une sauvegarde n’autorise pas cette connexion, ni le satellite ou les vents, sur l’autre appareil.

Ce transfert reste manuel : exporter sur un appareil, transférer le fichier, puis importer sur l’autre. Il ne crée pas de synchronisation permanente.

## Construire depuis le dépôt

Prérequis et configuration : [README Android](README.md).

Android, depuis la racine du dépôt, dans PowerShell :

```powershell
python scripts/prepare_android.py
cd android
.\gradlew.bat --no-daemon assembleDebug
```

Sur Linux ou macOS, remplacer la dernière commande par `./gradlew --no-daemon assembleDebug`.

APK construite et vérifiée : `android/app/build/outputs/apk/debug/app-debug.apk`.

Windows, depuis la racine du dépôt :

```powershell
python -m PyInstaller --noconfirm RFSATCMessageMaker.spec
python scripts/package_windows.py --archive dist/RFSFlightdeck-Windows-0.4.2-x64-test.zip
```

## Vérification et limites

- **149 tests Windows : OK** sur [GitHub](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37234427405). Les 148 tests initiaux locaux et les 9 + 4 tests ciblés après correction passent également. Aucun test existant supprimé.
- **29 tests du moteur Android : OK**, avec la vraie SQLite, les règles de messages et les formules Fuel PC.
- **5 parcours navigateur : OK**, dont 320 px, FR/EN, redémarrage, copie, tutoriel, import avec aperçu, fusion et protection du bouton Retour pendant l’import.
- **567 cas Fuel web : OK**, comparés aux composants Python de référence.
- **APK installée sur Android 15 (API 35) : OK**, quatre tests en mode avion puis quatre après réinstallation. Un arrêt forcé/redémarrage conserve le JSON et le formulaire affiché : callsign EJU149U, carburant 12 285 kg. Presse-papiers natif et zones système vérifiés.
- **Options natives connectées : OK**, satellite EOX, vents Open-Meteo et vérification HTTPS des releases GitHub. Les contrôles hors ligne vérifient zéro requête de mise à jour sans choix préalable ; un ancien cache ne propose pas de retélécharger la version installée.
- **Paquet Windows : OK**, EXE réellement démarré avec un profil isolé, Finder réel (577 résultats), Fuel (12 285 kg), carte et aide.
- **Bandit et audit des dépendances : OK** ; CodeQL passe. Le contrôle local des sources ne relève aucun problème moyen/élevé.

Téléchargements vérifiés : **[APK Android](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37234427403/artifacts/11314783690) · [ZIP Windows](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37234427393/artifacts/11315221754)**. Connectez-vous à GitHub puis décompressez le ZIP reçu. Ces artefacts expirent le 3 novembre 2026 ; [installation pas à pas](../INSTALLATION.md).

Preuve Android : [build et installation hors ligne](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37234427403) · [rapports](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37234427403/artifacts/11315336528). Preuve Windows : [build et démarrage](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37234427393).

La copie locale livrée est `livraison-flightdeck/RFSFlightdeck-Android-0.4.2-debug.apk`, à côté du dépôt. Taille : 62 180 134 octets. SHA-256 : `6d2fd399ef11738ccf6c57eb590082a8ebe5641c25f9e59620dc5e33c6315ddb`. Signature debug locale : `67ca61bae82b1f6fa3ef5fce04b675b57273a69faee18f5aa4d67f1f26dc25cd`, identique à l’APK locale 0.4.1. Les clés debug GitHub peuvent différer ; sauvegardez avant une désinstallation.

Fichiers principaux créés : `backup_bundle.py`, `app_version.py`, `updates.py`, `update_dialog.py`, `UpdateChecker.java`, `backup-ui.js`, `updates-ui.js` et les tests associés. Adaptations : `storage.py`, `ui.py`, le moteur/bridge Android, la sauvegarde différée JS et la préparation/vérification des builds. Les calculs de messages, Finder et Fuel conservent leur moteur Python existant.

Les nouveaux contrôles couvrent aussi les imports invalides ou trop gros, les conflits et réimports, les quatre fichiers PC après une interruption, les types Android et aperçus conservés au retour, et deux sauvegardes simultanées. Le consentement réseau et les chronomètres actifs restent propres à l’appareil.

Les sélecteurs de fichiers et les transferts n’ont pas encore été vérifiés sur un téléphone physique. La synchronisation automatique par Wi-Fi/QR code reste à développer. Le port iPhone reste à réaliser et nécessite une adaptation du moteur Python, un environnement Mac/Xcode et des essais iOS.

Aucune nouvelle release publique, publication Google Play ou publication App Store n’a été effectuée. Les notifications de mise à jour pourront annoncer les versions effectivement publiées sur GitHub ; un artefact de test ne constitue pas une nouvelle release.
