# Mises à jour et données entre appareils

La 0.4.2 ajoute une vérification facultative des versions publiques et une
sauvegarde commune entre Windows et Android. Le Finder, Fuel, les messages et
les données locales restent utilisables sans Internet.

## Savoir qu’une nouvelle version existe

Sur PC : **Aide → Mises à jour**. Sur Android : **Paramètres → Mises à jour**.
**Vérifier maintenant** consulte les releases publiques du dépôt GitHub.
Vous pouvez activer une vérification à l’ouverture, au plus une fois par jour.
Elle est désactivée au départ et s’effectue sans bloquer le lancement.

L’application distingue une version disponible, une version déjà à jour,
l’absence de release compatible et une vérification indisponible. Sans
connexion, elle ne peut pas découvrir une version nouvelle. Les versions de
test dans Actions ne sont pas annoncées comme des releases publiques.
Le bouton Télécharger n’apparaît que pour une version plus récente avec un
fichier compatible ; il ouvre le téléchargement GitHub dans le navigateur.
Aucune installation silencieuse et aucun envoi de vols ou de pilotes.

La préférence de connexion appartient à chaque appareil. Une sauvegarde
importée n’active pas les vérifications, le satellite ou les vents sur un
appareil qui ne les avait pas activés.

## Retrouver ses données sur PC et Android

1. Sur l’appareil de départ, choisissez **Exporter une sauvegarde**.
2. Transférez **rfs-flightdeck-backup.json** par USB ou avec votre moyen habituel.
3. Sur l’autre appareil, choisissez **Importer une sauvegarde** et ce fichier.
4. Vérifiez les collections annoncées, puis choisissez **Fusionner** ou **Remplacer**.

**Fusionner** conserve le vol en cours et ajoute pilotes, vols, historique,
favoris et designs. Si le vol importé diffère du brouillon local, il reste
accessible dans les vols sauvegardés, avec son aperçu édité. Les variantes
différentes sont gardées ; répéter le même import ne les multiplie pas.
**Remplacer** reprend le contenu de la sauvegarde, après confirmation.
Une copie de récupération est conservée dans les deux cas.

Les anciennes sauvegardes Android et les quatre JSON Windows restent
acceptés. Windows ne propose pas les trois types Android supplémentaires :
leurs données sont gardées pour un retour vers Android. Les interfaces
propres à une plateforme ne sont pas ajoutées par l’import.

Le transfert fonctionne dans les deux sens. Il reste **manuel** : les
appareils ne se synchronisent pas automatiquement en arrière-plan. Le
prototype web ne participe pas encore à ce transfert complet.

## Ce qui est prévu ensuite

La synchronisation sur le même Wi-Fi devra ajouter un appairage explicite,
un secret par paire, une connexion chiffrée et des choix de résolution des
conflits. Le format commun et la fusion constituent sa première étape ; aucun
faux bouton de synchronisation n’est livré.

iPhone nécessite toujours un port du moteur actuel vers iOS et un environnement
Mac/Xcode, puis des essais réels de SQLite, copie, import et reprise. Une APK
Android ne fonctionne pas sur iPhone. La chaîne iOS n’est pas disponible ici.

## Préparer les futures releases

Une version publique stable doit contenir des fichiers portant sa version :
**RFSFlightdeck-Android-0.4.2.apk** et
**RFSFlightdeck-Windows-0.4.2-x64.zip**, par exemple pour le tag **v0.4.2**.
Les versions doivent augmenter et la signature Android doit rester identique.
Les anciens ZIP historiques, brouillons et préversions sont ignorés.
Aucune nouvelle release n’est publiée automatiquement par ce travail.

Sur Windows, les copies de récupération et le journal d’import se trouvent
dans le dossier **data**. Un import interrompu est restauré à l’ouverture
suivante. Sur Android, la sauvegarde privée précédant l’import est conservée
et le fichier principal est remplacé de façon atomique.
