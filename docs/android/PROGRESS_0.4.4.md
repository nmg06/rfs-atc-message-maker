# Flightdeck 0.4.4 — livraison du 13 octobre 2026

La base contient 344 667 clés historiques airline/callsign/origin/destination,
contre 167 381 au départ : 177 286 ajouts, ratio 2,059. Les 203 627 lignes de
profils précédentes et les 21 061 routes observées restent intactes. 199 145
clés ont une durée recherchable. Les données sans durée ne passent pas un
filtre de durée ou d'heure d'arrivée. Aucun gate ou runway ATC n'est inventé.

Un catalogue Air India distinct reprend les faits des 37 pages DGCA été 2026 :
785 couples numéro–trajet et 1 573 variantes saisonnières. Les horaires locaux,
jours, dates, familles génériques et escales restent identifiés. Fin de validité :
24 octobre 2026. Il ne s'agit pas d'une couverture annuelle ou d'un horaire en direct.

Le nom GitHub choisi est **rfs-flightdeck**. Le contrôle des mises à jour cible
ce dépôt et le canal préversion. Les premiers clients 0.4.3 doivent suivre les
liens directs du guide pour passer au nouveau dépôt.

Le ZIP historique public contenait un profil utilisateur (historique et vols
sauvegardés, introduction déjà vue). Ce problème vient du paquet distribué,
pas d'une connexion à GitHub. La nouvelle chaîne refuse ces fichiers, les
sauvegardes privées et les clés de signature. Les defaults PC/Android/web sont
vides ; une mise à jour conserve les données déjà présentes sur l'appareil.

## Construction réalisée

Windows : `python -m PyInstaller --noconfirm --distpath build/enrichment-2026-10-12/windows-dist --workpath build/enrichment-2026-10-12/pyinstaller RFSATCMessageMaker.spec`

Archive : `python scripts/package_windows.py --dist build/enrichment-2026-10-12/windows-dist/RFSATCMessageMaker --archive build/enrichment-2026-10-12/public/RFSFlightdeck-Windows-0.4.4-x64.zip`

Android, dans `android/` : `gradlew.bat --offline --no-daemon assembleDebug assembleDebugAndroidTest`

APK construite : `android/app/build/outputs/apk/debug/app-debug.apk`.
Copie à télécharger : `RFSFlightdeck-Android-0.4.4-debug.apk`.
Package Android `com.nmg06.rfsatc`, versionCode 8, versionName `0.4.4-flightdeck`.
Signature debug locale conservée ; clé définitive et téléphone physique restant.
Le [guide](../INSTALLATION.md) explique la mise à jour par-dessus l'ancienne APK.

## Contrôles

Les rapports de la base vérifient intégrité SQLite, clés étrangères et comparaison
EXCEPT des anciennes lignes. Le ZIP est contrôlé avant/après compression. Le
bytecode réellement embarqué dans l'EXE est comparé aux sources pour Finder,
updates, version, storage et dialogue de mise à jour, pour éviter de livrer une
ancienne construction. Les moteurs et parcours sont testés hors réseau ; les
couches satellite/vents restent facultatives et nécessitent Internet.

Les mesures ne garantissent pas la même vitesse sur tous les appareils. Sur
cette machine, Air France donne 4 304 résultats distincts en 0,864 s, puis une
page supplémentaire en 0,019 s grâce au cache. Un filtre par avion utilise
maintenant l'index d'avion plutôt qu'un scan de classement de toute la base.

Les essais sur téléphone physique et la signature de production restent à faire.
La synchronisation automatique PC–Android, les gates vérifiés et iOS ne sont pas
livrés ; export/import manuel et pistes de référence sont disponibles.
