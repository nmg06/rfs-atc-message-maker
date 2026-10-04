# RFS Flightdeck 0.4.2 — sauvegardes et mises à jour

Compte rendu du 4 octobre 2026. Les builds et la vérification complète sont encore en cours ; les résultats et liens de téléchargement seront ajoutés après leur contrôle.

## Ce qui a été ajouté

- **Une sauvegarde commune PC ↔ Android.** Un seul fichier JSON transporte le vol actuel, les vols sauvegardés, les pilotes, les préférences, l’historique, les designs et les aperçus modifiés. Les anciens exports Android et les quatre fichiers JSON PC restent acceptés.
- **Un aperçu avant importation.** L’application présente la provenance et le nombre d’éléments avant de demander d’ajouter les données ou de remplacer le profil.
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

APK attendue après un build réussi : `android/app/build/outputs/apk/debug/app-debug.apk`.

Windows, depuis la racine du dépôt :

```powershell
python -m PyInstaller --noconfirm RFSATCMessageMaker.spec
python scripts/package_windows.py --archive dist/RFSFlightdeck-Windows-0.4.2-x64-test.zip
```

## Vérification et limites

Les tests ciblés du noyau de sauvegarde, du moteur et des transferts persistés passent. **Les suites complètes, les builds Windows/Android et les vérifications natives sont en cours à cet instant.** Leur bilan final reste à compléter.

Les sélecteurs de fichiers et les transferts n’ont pas encore été vérifiés sur un téléphone physique. La synchronisation automatique par Wi-Fi/QR code reste à développer. Le port iPhone reste à réaliser et nécessite une adaptation du moteur Python, un environnement Mac/Xcode et des essais iOS.

Aucune nouvelle release publique, publication Google Play ou publication App Store n’a été effectuée. Les notifications de mise à jour pourront annoncer les versions effectivement publiées sur GitHub ; un artefact de test ne constitue pas une nouvelle release.
