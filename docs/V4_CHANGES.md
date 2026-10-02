# Corrections Windows v4 — 1er octobre 2026

Cette passe poursuit l'application PySide6 existante. Elle ne reconstruit pas les
observations aéronautiques et conserve le moteur et les deux catalogues carburant.

## Interface et données

- Effacer vide le vol commun, les données de tous les messages, la sélection de
  sauvegarde, les corrections d'aperçu et les métadonnées Finder/carburant.
  Bibliothèque de pilotes, pseudo principal, préférences, favoris, designs,
  historique et vols sauvegardés sont conservés. Les pilotes du vol sont mémorisés
  avant de retirer leur sélection courante.
- Une tentative de copie invalide garde le presse-papiers intact, souligne les
  champs, affiche une indication textuelle à gauche et place le focus sur le
  premier champ concerné. Accentuation rouge brève, sans animation continue.
- La molette sur un sélecteur fermé ou un champ numérique/date est redirigée vers
  le formulaire. Les listes ouvertes et le clavier conservent leur navigation.
- Les pays acceptent codes et noms FR/EN, avec alias Romania/România et Moldavie.
  Le libellé local donne un nom et un code lisibles sous Windows ; le presse-papiers
  conserve le drapeau Unicode Discord.
- Sept présentations, huit choix d'emojis, personnalisation guidée avec titre,
  pied de message et présentation. L'ancien éditeur de variables et ses fichiers
  restent accessibles. Le générateur limite le résultat à six emojis ; une
  modification manuelle dépassant cette limite bloque la copie.
- Interface globale français/anglais, français par défaut. L'ancien réglage
  finder_language migre vers language ; RO retombe sur FR. Les valeurs métier des
  sélecteurs restent stables et les messages opérationnels restent en anglais.
- Le décor de carte bancaire possède son propre indicateur joke_seen, enregistré
  avant son affichage. La case intro_seen ne contrôle que le message de bienvenue.
  Les anciens profils sont considérés comme ayant déjà vu la plaisanterie.
- Rapport local avec aperçu et export ZIP. Seuls les textes saisis et les images
  sélectionnées avec consentement sont inclus ; aucun envoi réseau, journal,
  historique ou capture automatique.

## Finder

- Entrée lance la recherche ; une suggestion ouverte garde la priorité.
- Saisie des durées : 10h, 7 heures, 9h30, 03:00, 60 min. Pour conserver le sens
  historique, un nombre seul reste en minutes, unité annoncée dans l'interface.
- Min/max stricts, durée cible avec tolérance explicite ; modification des filtres
  invalide les anciens résultats. Dates et fuseaux sont dans les horaires avancés,
  indépendants du choix des routes historiques. Fuseau système proposé s'il est
  IANA valide, sinon UTC ; aucun décalage Paris fixe.
- Voir plus conserve l'ordre déterministe avec une horloge figée par recherche.
  Le compteur distingue candidats, correspondances, profils disponibles et
  profils masqués par diversité. Décocher la diversité donne accès aux autres
  profils ; le plafond de travail de 20 000 reste signalé avec demande d'affinement.
- Filtre par types du catalogue RFS fourni, activé dans l'interface. Le catalogue
  de 63 appareils ne constitue pas une vérification de la version actuelle du jeu.
  La correspondance explicite figure dans finder/rfs_catalogue.py. Les variantes
  cargo/passagers partageant un code ICAO restent indéterminées. Trois entrées
  (737-100, Concorde, C-5B) restent sans correspondance prise en charge, sans
  remplacement inventé. La sélection carburant n'infère pas de variante depuis
  un type observé.

## Couverture de la base livrée

Comptages effectués en lecture seule sur aviation.sqlite, sans télécharger ou
reconstruire le Parquet. Un profil exploitable exige une durée et au moins trois
traces complètes :

| Recherche | Profils présents | Profils exploitables | Observations | Traces complètes |
|---|---:|---:|---:|---:|
| Air India vers LFPG/CDG | 2 | 0 | 13 | 0 |
| LRIA, départ ou arrivée | 92 | 0 | 1 731 | 0 |
| UUEE, départ ou arrivée | 89 | 1 | 723 | 5 |

Ces résultats concernent les observations historiques disponibles, et ne prouvent
pas l'absence de vols réels. Pas de route fabriquée, de filtre désactivé en silence
ou de nouvelle dépendance à une API en direct.

## Carburant

IDs stables conservés, noms seuls dans le sélecteur. Formules, arrondis et choix du
dégagement le plus proche inchangés. Le taux d'atterrissage numérique reçoit
ft/min à l'affichage ; une unité déjà présente n'est pas ajoutée une seconde fois.

## Validation

Les preuves finales (suite de tests, vérifications natives, empreintes, contrôle
des archives et migration des données) sont consignées dans le bilan de livraison.
Les événements de molette sont testés par Qt ; aucun essai matériel de pavé tactile
ne doit être déduit de ces tests. Les captures natives utilisent uniquement les
widgets de l'application avec des données de validation isolées.
