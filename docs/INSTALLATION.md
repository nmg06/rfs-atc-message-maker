# Installer et utiliser RFS Flightdeck

[Read this guide in English](INSTALLATION_EN.md).

Flightdeck aide à **trouver un vol, préparer le carburant et créer des messages RFS**.
Vous pouvez l'utiliser sans ATC. Ancien nom : RFS ATC Message Maker.
Les fonctions principales fonctionnent hors ligne, sans compte ni télémétrie.
Python n'est pas nécessaire pour installer les fichiers proposés ici.

## Choisir son téléchargement

| Votre appareil | Fichier à choisir | État |
|---|---|---|
| PC Windows 10/11, 64 bits | ZIP Windows | Version de test portable |
| Android 7 ou plus, ARM64 | APK Android | Version de test installable |
| iPhone / iPad | Aucun pour l'instant | Version iOS non disponible |

**Téléchargements 0.4.1 vérifiés : [Android](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37211011918/artifacts/11306218305) · [Windows](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37211011938/artifacts/11305999753).**
Connectez-vous à GitHub, cliquez sur votre lien puis décompressez le ZIP reçu.
Ces fichiers de test expirent le 3 novembre 2026 ; les instructions ci-dessous
permettent de retrouver un build plus récent.

Les fichiers de test sont dans **GitHub Actions**, sur la branche
**feat/flightdeck-map-performance**. Le [bilan 0.4.1](android/PROGRESS_0.4.1.md)
donne les liens des builds vérifiés et les limites connues.

1. Ouvrez [les téléchargements Windows](https://github.com/nmg06/rfs-atc-message-maker/actions/workflows/flightdeck.yml) ou [Android](https://github.com/nmg06/rfs-atc-message-maker/actions/workflows/android.yml).
2. Choisissez une exécution **verte**, sur la branche **feat/flightdeck-map-performance**.
3. Descendez jusqu'à **Artifacts**. Touchez **RFSFlightdeck-Windows-x64-test** pour Windows, ou **RFS-ATC-Android-debug** pour Android.
4. Décompressez le ZIP téléchargé : il contient le paquet Windows ou **app-debug.apk**.

**GitHub demande un compte pour télécharger ces artefacts. L'application n'en
demande aucun.** Les fichiers expirent après 30 jours. Utilisez un build plus
récent vérifié, ou demandez au propriétaire de relancer le build.
Évitez les exécutions rouges : leurs tests ont échoué.

Une future release GitHub pourra proposer des liens permanents, sans compte.
Aucune nouvelle release publique n'est publiée automatiquement.
Voir [préparer une distribution](DISTRIBUTION.md).

## Installer sur Windows

1. Décompressez le ZIP GitHub, puis le ZIP Windows qu'il contient, dans **un nouveau dossier**.
2. Ouvrez **RFSFlightdeck**, puis **RFSATCMessageMaker.exe**. L'ancien nom du fichier est conservé.
3. Gardez **_internal**, **finder-data** et les autres fichiers à côté de l'EXE.
4. Pour un accès rapide, créez un raccourci de cet EXE sur le Bureau.

Les données restent dans **data**, à côté de l'EXE, sauf si la variable
RFS_MESSAGE_MAKER_DATA_DIR désigne un autre dossier. Un dossier local hors
OneDrive évite les ralentissements de synchronisation.

Pour reprendre une ancienne version, fermez normalement les deux applications,
sauvegardez l'ancien dossier **data**, puis copiez ses quatre fichiers
**rfs_state.json**, **rfs_history.json**, **rfs_presets.json**, **rfs_designs.json**
dans le nouveau dossier **data**. Gardez l'ancien paquet pour revenir en arrière.

## Installer sur Android

Vous pouvez télécharger le ZIP GitHub sur le téléphone, le décompresser dans
**Fichiers** et ouvrir **app-debug.apk**. Depuis le PC :

1. Branchez le téléphone en USB et choisissez **Transfert de fichiers** dans sa notification USB.
2. Dans l'Explorateur, copiez l'APK dans **Stockage interne > Download / Téléchargements** du téléphone.
3. Sur le téléphone, ouvrez **Fichiers > Téléchargements**, puis touchez l'APK.
4. Autorisez **Installer depuis cette source** si demandé, puis **Installer** et **Ouvrir**.
5. Ensuite, retrouvez **RFS Flightdeck** dans la liste des applications. Vous pouvez placer l'icône sur l'écran d'accueil.

La copie locale 0.4.1 s'appelle **RFSFlightdeck-Android-0.4.1-debug.apk**.
Prévoir environ 250 Mo libres. Le premier lancement prépare la base embarquée :
laissez cette étape se terminer. Aucun téléchargement de base n'est nécessaire.
Essayez en mode avion : Finder, carburant, messages, copie et carte locale restent disponibles.

**Pour mettre à jour, installez la nouvelle APK par-dessus l'ancienne.**
Exportez une sauvegarde dans les Paramètres avant toute désinstallation :
désinstaller efface les données privées. Deux environnements de build peuvent
avoir des signatures debug différentes. Si Android refuse la mise à jour pour
cette raison, sauvegardez avant de désinstaller. Les APK locales 0.3 et 0.4
de cette livraison utilisent la même clé.

## Préparer son premier vol

1. Ouvrez **Finder**, choisissez compagnie, aéroports ou pays, puis recherchez. Dans la durée minimum, **10 signifie 10 heures**.
2. Touchez **Détails**, puis **Utiliser ce vol**. Les informations inconnues ne remplacent pas inutilement vos champs manuels.
3. Ouvrez **Fuel**, vérifiez avion, durée et arrivée. Une variante unique est reprise automatiquement ; un type ambigu demande un choix. Calculez, puis **Appliquer avion + carburant**.
4. Dans **Vol**, vérifiez vos informations. **Préparation au sol** montre les pistes présentes dans la base. Choisissez les pistes et portes disponibles dans RFS : aucune affectation n'est inventée.
5. Pour l'ATC, ouvrez **Texte**, choisissez le message, puis **Aperçu > Copier**. Collez ensuite dans Discord ou RFS.

Dans **ARRIVAL BOARD**, **ETE restante = 5 min** signifie une arrivée prévue
dans environ cinq minutes. Ce champ est distinct de la **durée estimée du vol**,
qui représente le trajet complet et sert à préremplir le calcul carburant.

Le vol actuel est sauvegardé après la saisie et avant de changer d'écran ou de
quitter avec Retour. **Sauver le vol** crée une entrée nommée dans la Bibliothèque.
Attendez **Enregistré** avant d'arrêter brutalement l'application.
Les brouillons de design et de signalement sont aussi conservés.

Le bouton en haut à droite ouvre les **Paramètres**, devient une croix et revient
à l'écran précédent. Dix palettes claires/sombres existent sur Android et PC.
Android propose trois icônes et un rappel local facultatif du vol actuel.
Le carnet Android chronomètre uniquement les vols que vous démarrez et confirmez
terminés ; une recherche n'ajoute aucune heure.

Le rappel demande l'autorisation de notification quand vous le programmez.
Son horaire est approximatif selon Android et l'économie d'énergie.
Il n'effectue aucune recherche ou météo en arrière-plan.
Après un arrêt forcé Android, reprogrammez le rappel dans les Paramètres.

Pour revoir la blague manquée : Android **Paramètres > Revoir la blague de bienvenue** ;
Windows **Aide et suggestions > Revoir la blague**. Aucun paiement ni saisie bancaire.

## Carte, satellite et vents

La carte locale affiche frontières et trajet. Glissez, pincez pour zoomer ou
utilisez +/−. Choisissez deux pays puis **Trouver ces vols** pour remplir Finder.
Certains trajets ne figurent pas dans la base et donnent zéro résultat.

Sur Windows et Android 0.4, **Satellite EOX 2025** et **Vents Open-Meteo** sont des
options Internet désactivées au départ. Activez-les dans les options de carte.
Les téléchargements se font en arrière-plan, les caches sont limités.
Sans Internet ou en panne, la carte locale reste disponible.

Le satellite est une mosaïque annuelle de 2025, pas une image en direct.
EOX : CC BY-NC-SA 4.0, usage non commercial.
Les vents sont des prévisions du monde réel pouvant différer de RFS :
niveau de pression, date UTC et hauteurs géopotentielles en mètres AMSL sont affichés.
Une pression n'est pas une altitude fixe. Ils ne changent pas les durées Finder
ni les formules Fuel Helper. Les outils sont destinés à la simulation.

## Sauvegarder ou transférer ses réglages

Android **Paramètres > Exporter une sauvegarde** crée un JSON à conserver ailleurs.
**Importer** restaure une sauvegarde. **Importer les 4 fichiers PC** accepte les
quatre JSON cités plus haut, copiés depuis une application PC fermée.
Le lot est validé avant remplacement ; une copie avant import est conservée.
Le sélecteur multiple reste à vérifier sur téléphone physique.

Les photos d'un signalement sont choisies avec le sélecteur Android.
Aucune permission générale de stockage ni envoi automatique.
Internet sert aux couches cartographiques facultatives, sans compte ni suivi.

## Si quelque chose ne fonctionne pas

| Problème | Que faire |
|---|---|
| Je ne trouve pas le téléchargement | Connectez-vous à GitHub, ouvrez une exécution verte, descendez jusqu'à Artifacts |
| Windows ne trouve pas ses fichiers | Décompressez le paquet entier ; gardez _internal et finder-data à côté de l'EXE |
| Le raccourci ouvre une vieille version | Créez un raccourci vers l'EXE du nouveau dossier |
| Android refuse l'installation | Vérifiez Android 7, téléphone ARM64, espace libre et autorisation depuis Fichiers |
| Android refuse la mise à jour | Vérifiez la signature ; exportez avant toute désinstallation |
| Premier lancement long | Laissez finir la copie de la base locale ; elle ne demande pas Internet |
| Finder ne trouve aucun vol | Réduisez les filtres. La base est historique ; certains trajets n'y figurent pas |
| Fuel ne sélectionne pas l'avion | Choisissez la variante RFS dans la liste recherchable si le type est ambigu |
| Satellite ou vent indisponible | Vérifiez Internet et les options ; la carte locale reste utilisable |
| Le rappel arrive en retard | Vérifiez notifications et économie d'énergie ; les alarmes sont approximatives |
| L'icône tarde à changer | Certains lanceurs mettent quelques secondes à actualiser leur liste |
| Un problème persiste | Paramètres > Signaler un problème : étapes, téléphone/version Android, rapport local à partager volontairement |

## Et iPhone ?

**Aucune version iPhone installable n'est livrée.** Une APK est réservée à Android.
Le prototype mobile/index.html ne possède pas la parité avec Flightdeck.
Le port iOS demande un hôte Python compatible ou un port du moteur, un Mac avec
Xcode, la signature Apple et des tests iOS. Ces outils ne sont pas disponibles
sur ce poste Windows.

Voir [parité](android/PARITY.md), [architecture/build Android](android/README.md)
et [preuves 0.4](android/PROGRESS_0.4.md) pour les limites précises.

## Tutoriel et copie libre

[Comprendre les rubriques, rechercher les 30 questions et choisir les contrôles de copie](HELP.md).
Vous pouvez passer le tutoriel et le retrouver dans Aide ou Paramètres.
