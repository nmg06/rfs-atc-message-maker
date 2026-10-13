# Mettre Flightdeck à disposition

La [préversion 0.4.4](https://github.com/nmg06/rfs-flightdeck/releases/tag/flightdeck-0.4.4)
propose des liens directs Windows ZIP et Android APK. Aucun compte GitHub n'est
nécessaire. Les artefacts Actions restent des builds temporaires distincts.
Le [guide d'installation](INSTALLATION.md) explique quel fichier choisir.

Chaque publication doit passer les tests, la construction réelle, le contrôle du
contenu des archives et des signatures. `scripts/public_package.py` refuse les
fichiers de profil personnel et les clés privées dans les archives publiques.
Le paquet public est construit avant toute copie du profil local du propriétaire.

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
