# Windows / Android — parité vérifiée

Référence : GitHub main `8747e0e5b4985eb6ddd540919ca659dca0b32622`.
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
| Presse-papiers Android / partage natif | OK | partiel | Code natif et instrumentation construits ; exécution Android en cours |
| Rapport local / images choisies avec consentement | OK | partiel | ZIP/sélecteur natif implémentés ; test appareil restant |
| Introduction / blague une seule fois | OK | partiel | Billet factice non interactif adapté ; drapeaux séparés conservés |
| Sans compte/API/CDN/télémétrie | OK | OK | Ressources locales, sockets interdits dans tests, aucune permission Internet déclarée |
| APK debug construite | N/A | OK | assembleDebug + assembleDebugAndroidTest réussis localement |
| Installation / démarrage / mode avion / fermeture processus / copie native | N/A | partiel | Tests instrumentés prêts ; contrôle Android réel encore requis |
| Carte Flightdeck de la livraison locale séparée | hors GitHub main | non porté | Code non substitué silencieusement à la référence GitHub |

## Résultats enregistrés

- Windows : 71 tests de référence réussis, environnement complet Qt + ETL.
- Android Python : 12 tests initiaux réussis (dont 1 344 combinaisons de messages).
  Deux contrôles ajoutés : import des objets imbriqués et sources sans remise à
  zéro Finder ; résultat mis à jour après exécution.
- UI Playwright, 390×844 : navigation, champs, validation, dernier caractère copié,
  Finder 100→200/transfert, Fuel A220, rechargement, FR→EN réussis, zéro erreur JS.
- Build : `android/gradlew.bat -p android assembleDebug assembleDebugAndroidTest`,
  `BUILD SUCCESSFUL`, APK debug produite. Voir README pour les prérequis.
- Téléphone physique : aucun connecté pendant ce travail. Les contrôles moteur/
  navigateur ne prouvent pas l'installation ou le fonctionnement sur Android.
