# Windows / Android — parité vérifiée

Référence initiale : GitHub main `8747e0e5b4985eb6ddd540919ca659dca0b32622`.
La branche Flightdeck ajoute la version desktop locale vérifiée (103 tests
conservant les 71 tests initiaux) et ses améliorations, avec les mêmes moteurs
purs exportés automatiquement dans Android. Les formules Fuel restent identiques.
Vérifications du 3 octobre 2026. `OK` = comportement implémenté et testé ;
`partiel` = limite connue ou validation Android restante ; `non porté` = absent.
L'interface téléphone est nouvelle ; les moteurs Windows sont réutilisés sans
modification et le prototype mobile est conservé.

| Fonction | Windows | Android | Preuve / limite |
|---|---|---|---|
| ATC REQUEST, AIRBORNE, ARRIVAL BOARD, FLIGHT COMPLETED | OK | OK | Moteur identique, tests de génération |
| ATC ACTIVE, ATC OFFLINE, FLIGHT PLAN, DISPATCH FORM | OK | OK | 1 344 combinaisons au total, exception Dispatch conservée |
| PUSHBACK / TAXI / ATIS demandés | non porté | partiel | Génération/validation réelles ; extensions sans référence PC, présentation/groupes incomplets |
| Compagnie, avion, callsign, routes, portes, pistes, FL, ETE, charge, fuel | OK | OK | Tous les champs du schéma, navigation conserve le vol |
| Pushback, contrôleur, climb, STAR, go-around, champs conditionnels | OK | OK | Schéma et moteurs PC ; tests procédures |
| Pilotes multiples et sélection par type | OK | OK | Champs/choix portés ; moteur testé |
| Opérations indépendantes, groupe, parallèle, décalé | OK | OK | Deux choix départ/arrivée, règles PC inchangées |
| Sept designs / trois longueurs / huit styles emojis | OK | OK | Parité 8×7×3×8 ; règles du moteur PC |
| Designs guidés/expert / import-export JSON | OK | partiel | Enregistrement/rendu/validation testés ; sélecteur natif à vérifier |
| Aperçu éditable / validation / limites / alignement Discord | OK | OK | Test copie éditée, 2 000 caractères/6 emojis ; parcours UI |
| Historique compact / duplication | OK | OK | Compaction PC, conservation/restauration testées ; 200 entrées |
| Vols sauvegardés / rappel / favoris | OK | partiel | Sauvegarde/restauration testées ; supprimer/renommer à compléter |
| Bibliothèque pilotes / préférences | OK | partiel | Ajout/rappel/choix conservés ; suggestions/gestion desktop incomplètes |
| FR/EN / sombre-clair / 249 pays-drapeaux | OK | partiel | Changement langue testé ; quelques textes techniques non traduits |
| Finder SQLite local / critères / pagination | OK avec base externe | OK | Snapshot embarqué, 577 résultats LFPG ≤2h, pages 100→200 ; parité PC |
| UTILISER CE VOL / conservation des inconnues | OK | OK | Mapping PC identique ; UI et champs manuels testés |
| Fuseaux / DST / avertissements / pistes disponibles | OK | partiel | Moteurs PC, détails/sources ; provenance durées du snapshot limitée |
| 63 avions / 64 arrivées / alternates / formules Fuel | OK | OK | Tous les avions comparés ; A220 /5h/EGLL =12 285 kg |
| Appliquer avion + fuel / détails exacts | OK | OK | Moteur/UI testés, recalcul avant application |
| Stockage privé / écriture atomique / relance | JSON local | OK | Nouvelle instance moteur et rechargement UI conservent les collections |
| Export-import sauvegarde / import état PC | fichiers séparés | partiel | Validation/restauration testées ; état PC seul, autres fichiers séparés |
| Presse-papiers Android | OK | OK | Texte édité copié exactement sur émulateur API 35, mode avion |
| Partage natif | OK | partiel | Intent Android implémenté ; choix d'une application destinataire à vérifier |
| Rapport local / images choisies avec consentement | OK | partiel | ZIP/sélecteur natif implémentés ; test appareil restant |
| Introduction / blague une seule fois | OK | partiel | Billet factice non interactif adapté ; drapeaux séparés conservés |
| Sans compte/API/CDN/télémétrie | OK | OK | Ressources locales, sockets interdits dans tests, aucune permission Internet déclarée |
| APK debug construite | N/A | OK | assembleDebug + assembleDebugAndroidTest réussis localement |
| Installation / démarrage / mode avion / fermeture processus / copie native | N/A | OK | APK installée API 35, tests natifs, force-stop/relance et UI réelle vérifiés |
| Catalogue avion recherchable dans le vol / préremplissage Fuel | OK | OK | 63 variantes ; variante Finder unique reprise ; choix requis si ambigu |
| Finder numérique en heures / pages en cache / Voir moins | OK | OK | Parseur UI dédié ; pas de requête répétée ; résultats conservés |
| Carte Flightdeck, frontières, sélection pays / zoom | OK | non porté | Desktop natif Qt, tests FR→RO et ressources incluses |
| Satellite / vents par altitude facultatifs | OK avec Internet | non porté | Deux fournisseurs vérifiés ; Android conserve zéro permission Internet |

## Résultats enregistrés

- Windows : 113 tests réussis, dont les 71 initiaux et 103 tests Flightdeck, environnement Qt + ETL.
- Android Python : 16 tests réussis (dont 1 344 combinaisons de messages), import
  des objets imbriqués et sources sans remise à zéro Finder compris.
- UI Playwright, 390×844 : navigation, champs, validation, dernier caractère copié,
  Finder 100→200→100→200/transfert, catalogue vol→Fuel A220, rechargement, FR→EN ; zéro erreur JS.
- Build : `android/gradlew.bat -p android assembleDebug assembleDebugAndroidTest`,
  `BUILD SUCCESSFUL`, APK debug produite. Voir README pour les prérequis.
- Téléphone physique : aucun connecté pendant ce travail. Les contrôles moteur/
  navigateur ne prouvent pas l'installation ou le fonctionnement sur Android.

- Android réel sur émulateur API 35 : deux tests instrumentés passent, puis
  réinstallation dédiée, même instrumentation et arrêt complet du processus.
  Relance : vol EJU149U et fuel 12285 conservés, formulaire WebView visible,
  JSON privé identique, mode avion activé, Wi-Fi/données désactivés.
  [Exécution GitHub réussie](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37129848910),
  commit testé `7e684f3975e9d4ec21726e43dbe9a9d026e71a8e`.
- Vérification de l'APK elle-même : ressources UI présentes, base embarquée
  décompressable à 94 892 032 octets et SHA-256 vérifié, aucune permission.
  `scripts/verify_android_apk.py` est exécuté avant mise à disposition de l'artefact.
- Les contrôles Windows GitHub initiaux (71 tests, dépendances, analyse, build EXE)
  et Android installée passent sur `9013687` ; workflows Windows existants conservés.
  La recherche Flightdeck optimisée est comparée à la version précédente sur la
  vraie base : mêmes lignes, scores, avertissements et pages. Mesures :
  [finder-performance.json](../finder-performance.json).
