# Vérification et publication

L'application génère les messages et conserve ses données localement. L'introduction
humoristique ne contient aucun champ bancaire, paiement, collecte ou transmission.

Le dépôt contient des workflows GitHub Actions pour les tests Windows, Bandit,
l'audit des dépendances et CodeQL. Ils seront exécutés après publication du dépôt
et activation des Actions. Leurs résultats ne sont pas présentés comme déjà réussis.

GitHub Code scanning est disponible pour les dépôts publics :
https://docs.github.com/en/code-security/concepts/code-scanning/code-scanning

Un résultat de scan est un indicateur, pas une garantie d'absence de toute faille.
Un SHA-256 permet de vérifier l'intégrité du ZIP, pas de certifier qu'il est sûr.
Le paquet Windows fourni n'est pas signé numériquement.

Avant une release : exécuter les tests et les scans, examiner les alertes, construire
le paquet, analyser aussi les fichiers distribués avec votre antivirus, puis publier
le ZIP et son SHA-256 avec les résultats datés des vérifications réellement réalisées.
Ne jamais publier `data/`, qui peut contenir les vols et messages personnels.

## Déploiement gratuit sur GitHub

1. Créer votre dépôt, y ajouter le code et choisir une licence adaptée à votre projet.
2. Activer Actions et consulter les résultats de Tests et CodeQL.
3. Créer une Release et joindre le ZIP Windows complet ainsi que son SHA-256.
4. Les utilisateurs extraient tout le ZIP puis ouvrent l'exécutable.

Aucun dépôt ni fichier n'est publié automatiquement par l'application.
# Vérifications locales du 1er octobre 2026

- Tests automatisés : 51 réussis, y compris le calcul carburant des 63 avions comparé au moteur fourni.
- `pip-audit -r requirements.txt` : aucune vulnérabilité connue signalée.
- Bandit sur le code applicatif : aucune alerte restante de niveau moyen/haut.
  Quatre exceptions ciblées sont documentées : URL HTTPS fixes/allowlist et SQL dont
  seuls des fragments constants sont assemblés, avec valeurs utilisateur paramétrées.
- Les workflows GitHub sont préparés, mais leurs résultats ne sont pas inventés :
  ils doivent réellement s'exécuter dans votre dépôt après publication.
- Aucun token Discord, aucune clé API et aucune saisie bancaire ne sont nécessaires.
  La plaisanterie d'accueil est un décor non éditable qui se ferme dès une interaction.

Ces contrôles ne certifient pas une absence absolue de défaut. L'exécutable n'est pas
signé numériquement ; Windows SmartScreen peut afficher un avertissement de réputation.
