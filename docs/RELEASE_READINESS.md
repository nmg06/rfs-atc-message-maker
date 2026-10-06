# Vérifications avant publication — candidate 0.4.3

La version reste une candidate de test. La publication officielle sera faite
après les vérifications PC et Android, comme demandé. Aucun tag public, release
ou message Discord n’a été publié pendant cette étape.

## Corrections de cette étape

- **Calculer le fuel** auprès du champ carburant sur Windows et Android : avion,
  durée totale et arrivée repris depuis le vol. ETE restante distincte ; aucun
  carburant appliqué sans action explicite.
- Finder : aéroports à éviter visibles, ICAO/IATA, plusieurs codes, erreurs
  explicites, filtre conservé. Une réponse ancienne ne remplit plus des résultats
  après modification des critères.
- Retour rapide des paramètres : la dernière destination choisie est conservée
  pendant la sauvegarde. Les saisies pendant la préparation Fuel restent prioritaires.
- Android : export/import, permission de rappel et images conservés pendant la
  recréation de l’écran. L’aperçu d’import reste à confirmer ; validation de toutes
  les images avant ajout ; rapport fondé sur les images consenties au moment du clic.
- WebView : garde locale de compatibilité, noms de pays anglais et remplacement
  de texte avec fallbacks. Chargement initial sans phrase française imposée.
- Enrichissement historique Q1 + Q2 : [sources et mesures](data-enrichment-2026-10-06.md).

## Distribution

Les APK locales de test gardent la clé debug locale. Les runners GitHub peuvent
avoir une autre clé debug : exportez vos données avant de changer de provenance.
La future distribution exige une clé privée stable, jamais ajoutée au dépôt.
Le build release sans clé et la vérification d’une APK debug comme release sont
explicitement refusés. [Configuration de signature](android/SIGNING.md).

Le workflow manuel **Flightdeck signed release candidate** prépare un ZIP Windows
et une APK signée sans publier. Il reste à configurer la clé privée et ses secrets
GitHub, puis à tester cette APK signée. Les futurs tags `flightdeck-X.Y.Z` évitent
le déclenchement de l’ancien workflow de release Windows.

## Vérifications encore nécessaires avant officialisation

- Sélecteurs Android réels : choisir puis annuler un fichier/photo, partage vers
  Discord, clavier et paysage sur le téléphone physique. Les tests automatisés
  des callbacks et de la recréation ne remplacent pas ces gestes.
- Installer la future APK signée, relancer, importer une sauvegarde et vérifier
  une seconde mise à jour avec le même certificat.
- Confirmer l’affichage et la fluidité sur le téléphone de l’utilisateur et
  relire les captures et le texte Discord.

Les fonctions encore partielles restent indiquées dans [PARITY.md](android/PARITY.md).
iOS n’a pas de paquet installable. Le site garde son statut de prototype limité ;
il ne contient pas le Finder SQLite. Le transfert PC ↔ Android est manuel via
export/import, sans synchronisation automatique.
