# Version Windows v5 — 2 octobre 2026

Révision du thème utilisateur Avionique Sobre, lien Google Forms dans Aide,
rapport local défilable, traductions complétées, emojis du design Minimal
conservés et conversion des designs sans figer le vol. Voir `docs/V5_CHANGES.md`.

# Version Windows v4 — 1er octobre 2026

Effacement complet du vol, validation visible, défilement sans modification
accidentelle des sélecteurs, interface globale FR/EN, Finder simplifié avec
pagination et catalogue RFS, designs guidés, rapport local exportable et décor
bancaire montré une seule fois. Détails : `docs/V4_CHANGES.md`.

# Historique : version Windows intégrée v3 — 1er octobre 2026

## Ajoutés

- `finder/` : moteur local, SQLite, import DuckDB, fuseaux IANA/DST, classement,
  interface EN/FR/RO, transfert vers le vol commun et provenance.
- `fuel/` : adaptation du moteur RFS Fuel Helper, deux catalogues conservés,
  composants détaillés, alternates, endurance, choix explicite de variante et transfert.
- `appearance.py`, `country_data.py`, `country_picker.py`, `app_icon.py` : thème,
  249 pays et icône. `dialogs.py`, `message_builder.py`, `history_utils.py` :
  pilotes/designs/introduction, mise en forme et historique compact.
- Tests Finder, intégration Qt, carburant et nouvelles interactions ; contrôles
  GitHub CodeQL, Bandit et audit des dépendances ; script de packaging sans données privées.
- `docs/finder/` audit, décisions, schémas réellement inspectés, guide et validation ;
  `docs/fuel/` transfert de référence et note d'intégration.

## Modifiés

- `ui.py` : boutons Finder/Carburant, pilotes mémorisés, filtres par message,
  aperçu sans balises, cinq designs prêts à choisir, confirmation de copie.
- `storage.py` : conservation additive de la bibliothèque de pilotes, présentation,
  métadonnées Finder/carburant et historique dédoublonné, sans effacer les anciens vols.
- `rfs_schema.py` : procédures et descriptions ; `templates.py` est conservé.
- `main.py`, `requirements.txt`, `requirements-etl.txt`, `RFSATCMessageMaker.spec`,
  `lancer.bat`, README et sécurité : démarrage, vérification native, données embarquées
  carburant/tzdata et construction Windows.

## Vérifié

51 tests réussis ; 63 avions comparés au moteur carburant original ; exemple
A220-300/5h/EGLL = 12 285 kg. Base Finder réelle de 59 552 profils recherchables,
intégrité SQLite correcte, recherches LFPG testées et interfaces sombre/claire capturées.
L'audit des dépendances n'a signalé aucune vulnérabilité connue. Ce n'est pas une
certification de sécurité ni une validation pour l'aviation réelle.

## Limites connues

- Finder : observations 2026 Q2, pas des horaires actuels ; couverture inégale,
  notamment pour les exemples Air India sans assez de traces complètes.
- Carburant : données fournies et alternates statiques pour RFS uniquement ;
  estimation BelugaXL signalée, pas de météo/NOTAM/performance en temps réel.
- Version mobile/PWA, API live, recherche d'horaires publiés et livrées vérifiées reportées.
- EXE non signé : un avertissement SmartScreen reste possible.
- Le faux formulaire d'accueil ne permet aucune saisie ni collecte bancaire.
