# Mettre Flightdeck à disposition

Pour l'instant, les boutons du [guide d'installation](INSTALLATION.md) donnent
accès aux fichiers de test GitHub Actions. Leur téléchargement demande un compte
GitHub et ils expirent après 30 jours. L'application ne demande aucun compte.

Pour proposer plus tard des liens publics durables, une release GitHub peut
contenir un ZIP Windows et une APK Android. Après publication, chaque fichier
dispose d'un lien direct ; les visiteurs n'ont pas besoin d'utiliser Actions.
Ne pas publier tant que les fichiers/version et signature ne sont pas approuvés.
Aucune nouvelle release n'a été publiée automatiquement par ce travail.

Avant une APK de distribution, conserver une clé Android privée stable et ses
mots de passe hors de Git. Le wrapper Gradle est déjà configuré ; les versions
actuelles restent debug et les clés de deux environnements peuvent différer.
Exporter les données avant toute désinstallation nécessaire pour changer de clé.
Une release Windows existante ne doit pas être remplacée par un artefact de test.

Texte simple proposé pour la future release :

> RFS Flightdeck aide à choisir un vol, calculer le carburant et préparer les
> messages RFS. Téléchargez le ZIP pour Windows ou l'APK pour Android. Le Finder,
> le carburant, les messages et la carte vectorielle fonctionnent hors ligne.
> Le satellite et les vents sont des options Internet. Version de simulation ;
> les observations historiques ne représentent pas les horaires actuels.

iPhone : aucun fichier installable. Le moteur partagé est Python ; Chaquopy
cible Android. Il faut un hôte Python iOS ou un port du moteur, un Mac avec
Xcode, puis vérifier SQLite, presse-papiers, import/export, carte, cycle de vie
et signature Apple. Il n'y a pas de Mac ni de chaîne Apple disponible sur cet
hôte Windows ; aucune APK renommée en IPA ne constitue un port iPhone.
