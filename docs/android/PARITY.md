# Windows / Android — parité vérifiée

Référence initiale : GitHub main `8747e0e5b4985eb6ddd540919ca659dca0b32622`.
La branche Flightdeck ajoute la version desktop locale vérifiée (103 tests
conservant les 71 tests initiaux) et ses améliorations, avec les mêmes moteurs
purs exportés automatiquement dans Android. Les formules Fuel restent identiques.
Référence 0.3 du 3 octobre, complétée par les vérifications 0.4 du 4 octobre 2026. `OK` = comportement implémenté et testé ;
`partiel` = limite connue ou validation Android restante ; `non porté` = absent.
L'interface téléphone est nouvelle ; les moteurs Windows sont réutilisés sans
modification et le prototype mobile est conservé.

| Fonction | Windows | Android | Preuve / limite |
|---|---|---|---|
| ATC REQUEST, AIRBORNE, ARRIVAL BOARD, FLIGHT COMPLETED | OK | OK | Moteur identique, tests de génération |
| ATC ACTIVE, ATC OFFLINE, FLIGHT PLAN, DISPATCH FORM | OK | OK | 1 344 combinaisons au total, exception Dispatch conservée |
| PUSHBACK / TAXI / ATIS demandés | non porté | OK (extensions) | 504 combinaisons de présentation ; designs personnels et groupes PUSHBACK/TAXI validés, sans référence PC |
| Compagnie, avion, callsign, routes, portes, pistes, FL, ETE, charge, fuel | OK | OK | Tous les champs du schéma, navigation conserve le vol |
| Pushback, contrôleur, climb, STAR, go-around, champs conditionnels | OK | OK | Schéma et moteurs PC ; tests procédures |
| Pilotes multiples et sélection par type | OK | OK | Champs/choix portés ; moteur testé |
| Opérations indépendantes, groupe, parallèle, décalé | OK | OK | Deux choix départ/arrivée, règles PC inchangées |
| Sept designs / trois longueurs / huit styles emojis | OK | OK | Parité 8×7×3×8 ; règles du moteur PC |
| Designs guidés/expert / import-export JSON | OK | partiel | Enregistrement/rendu/validation testés ; sélecteur natif à vérifier |
| Aperçu éditable / validation / limites / alignement Discord | OK | OK | Test copie éditée, 2 000 caractères/6 emojis ; parcours UI |
| Historique compact / duplication | OK | OK | Compaction PC, conservation/restauration testées ; 200 entrées |
| Vols sauvegardés / rappel / favoris | OK | OK | Renommer/supprimer/rappeler, collisions et redémarrage testés ; vol actuel conservé |
| Bibliothèque pilotes / préférences | OK | OK | Ajouter/modifier/supprimer, choix des messages, rappel et préférences conservés après édition du vol |
| FR/EN / sombre-clair / 249 pays-drapeaux | OK | partiel | Changement langue testé ; quelques textes techniques non traduits |
| Finder SQLite local / critères / pagination | OK avec base externe | OK | Snapshot embarqué, 577 résultats LFPG ≤2h, pages 100→200 ; parité PC |
| UTILISER CE VOL / conservation des inconnues | OK | OK | Mapping PC identique ; UI et champs manuels testés |
| Fuseaux / DST / avertissements / pistes disponibles | OK | OK | Moteurs PC, sources, distinction observé/estimé/non vérifié partagée ; bornes estimées jamais appelées percentiles |
| 63 avions / 64 arrivées / alternates / formules Fuel | OK | OK | Tous les avions comparés ; A220 /5h/EGLL =12 285 kg |
| Appliquer avion + fuel / détails exacts | OK | OK | Moteur/UI testés, recalcul avant application |
| Stockage privé / écriture atomique / relance | JSON local | OK | Nouvelle instance moteur et rechargement UI conservent les collections |
| Export-import sauvegarde / import état PC | fichiers séparés | partiel | Les 4 fichiers PC sont désormais importables, validation globale/rollback/migration testés ; sélection multiple native à vérifier sur téléphone |
| Presse-papiers Android | OK | OK | Texte édité copié exactement sur émulateur API 35, mode avion |
| Partage natif | OK | partiel | Intent Android implémenté ; choix d'une application destinataire à vérifier |
| Rapport local / images choisies avec consentement | OK | partiel | ZIP/sélecteur natif implémentés ; test appareil restant |
| Introduction / blague une seule fois / revoir | OK | OK | Décor avant conclusion, reprise sans relecture automatique ; bouton Revoir et tests UI ; aucun champ bancaire éditable |
| Fonctions principales sans compte/API/CDN/télémétrie | OK | OK | Ressources locales, sockets interdits dans les tests moteur ; Internet facultatif pour satellite/vents uniquement depuis 0.4 |
| APK debug construite | N/A | OK | assembleDebug + assembleDebugAndroidTest réussis localement |
| Installation / démarrage / mode avion / fermeture processus / copie native | N/A | OK | APK installée API 35, tests natifs, force-stop/relance et UI réelle vérifiés |
| Catalogue avion recherchable dans le vol / préremplissage Fuel | OK | OK | 63 variantes ; variante Finder unique reprise ; choix requis si ambigu |
| Finder numérique en heures / pages en cache / Voir moins | OK | OK | Parseur UI dédié ; pas de requête répétée ; résultats conservés |
| Carte Flightdeck, frontières, sélection pays / zoom | OK | OK | Canvas local, 242 frontières, géométrie PC partagée ; zoom/pincement/pays→Finder/reprise testés et carte réelle contrôlée sur APK installée API 35 |
| Satellite / vents par altitude facultatifs | OK avec Internet | partiel | Fournisseurs PC partagés, JPEG EOX et vent 250 hPa/UTC/AMSL testés depuis Android installé ; confort de superposition sur téléphone physique restant |
| Menu animé / retour écran et défilement | N/A | OK | Parcours téléphone, retour Android et fermeture du dialogue |
| Dix palettes claires/sombres | OK | OK | Catalogue partagé, contraste des accents, persistance et UI testés |
| Préparation hors ATC / pistes locales | OK | OK | Consultation sans affectation ; aucune porte ou compatibilité avion/compagnie inventée |
| Carnet chronométré / statistiques | non porté | OK | Sessions explicites, pause/reprise/terminer et fermeture testées ; recherches exclues |
| Trois icônes de lanceur | icône fixe | OK | Océan → défaut vérifié sur APK installée ; délai propre au lanceur et trois icônes seulement |
| Rappel local facultatif | non porté | partiel | Programmation, publication réelle et annulation testées ; livraison à l'heure prévue/batterie/reboot sur téléphone physique restante |
| Marges barres système/encoche/clavier | N/A | partiel | Bornes du viewport portrait vérifiées avec insets API 35 ; clavier/paysage et autres appareils restent à vérifier |

## Résultats enregistrés

- Windows : 114 tests réussis, dont les 71 initiaux et 103 tests Flightdeck ; trois exécutions complètes après correction du cycle des traducteurs Qt.
- Android Python : 22 tests réussis (1 344 combinaisons PC et 504 extensions), import
  des objets imbriqués et sources sans remise à zéro Finder compris.
- UI Playwright, 390×844 : navigation, champs, validation, dernier caractère copié,
  Finder 100→200→100→200/transfert, catalogue vol→Fuel A220, rechargement, FR→EN ; zéro erreur JS.
  Nouveau parcours : carte/frontières/zoom/pincement/reprise/pays→Finder, bibliothèque,
  préférences pilotes et drapeaux recherchables. Les preuves 0.3.0 complètent la livraison précédente.
- Build : `android/gradlew.bat -p android assembleDebug assembleDebugAndroidTest`,
  `BUILD SUCCESSFUL`, APK debug produite. Voir README pour les prérequis.
- Téléphone physique : aucun connecté pendant ce travail. Les contrôles moteur/
  navigateur ne prouvent pas l'installation ou le fonctionnement sur Android.

- Android 0.3 sur émulateur API 35 : trois tests instrumentés passent, dont la carte
  WebView réelle (242 frontières, trajet de 97 points, identification de la France), puis
  réinstallation dédiée, même instrumentation et arrêt complet du processus.
  Relance : vol EJU149U et fuel 12285 conservés, formulaire WebView visible,
  JSON privé identique, mode avion activé, Wi-Fi/données désactivés.
  [Exécution Flightdeck 0.3 réussie](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37151621335),
  commit testé `6bdc5a830d43470c86a164aedf9e0861ae8a8a1c`.
- Vérification de l'APK 0.3 elle-même : ressources UI présentes, base embarquée
  décompressable à 94 892 032 octets et SHA-256 vérifié, aucune permission.
  `scripts/verify_android_apk.py` est exécuté avant mise à disposition de l'artefact.
- Les contrôles Windows GitHub initiaux (71 tests, dépendances, analyse, build EXE)
  et Android installée passent sur `9013687` ; workflows Windows existants conservés.
  La recherche Flightdeck optimisée est comparée à la version précédente sur la
  vraie base : mêmes lignes, scores, avertissements et pages. Mesures :
  [finder-performance.json](../finder-performance.json).

## Étape 0.4

116 tests Windows et 25 tests Android Python passent. Le nouveau parcours UI
vérifie le retour au défilement exact, les détails Finder sans JSON, sauvegarde
sans bouton et reprise, pistes réelles, carnet, palettes et sélecteurs recherchables.
Dessin Canvas mesuré à 0,5–1,8 ms sur Chrome avec densité simulée ×3, sans
garantie identique sur chaque appareil. Tests natifs et sources en ligne :
[état et preuves 0.4](PROGRESS_0.4.md).

Quatre tests natifs principaux 0.4 passent sur API 35 en mode avion, puis seconde
instrumentation, arrêt complet/reprise avec JSON identique et formulaire rendu.
Un test supplémentaire active explicitement Internet sur l'émulateur dédié et
vérifie les vrais fournisseurs. Le cinquième test natif, notification/icône,
est exécuté séparément en dernier et passe également.
[Exécution 0.4 réussie](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37163877211).
Ces preuves ne remplacent pas les essais sur le téléphone de l'utilisateur.
