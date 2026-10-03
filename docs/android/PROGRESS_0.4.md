# Flightdeck 0.4 — confort téléphone et préparation de vol

Demande du 4 octobre 2026. Travail à côté de Windows ; onglets conservés pour
cette étape. Aucune release publique automatique.

## Plan vérifiable

1. Corriger les insets Android avec un conteneur autour de la WebView : barres
   système, encoche, clavier, portrait/paysage. Tester les limites natives.
2. Menu paramètres ↔ croix animé, retour à l'écran et au défilement précédents ;
   retour Android ferme d'abord le dialogue. Séparer sauvegarde et gros rendus.
3. Détails Finder lisibles, cartes espacées et rendu progressif des résultats.
   Géométrie simplifiée pour les interactions, détails après arrêt du geste.
4. Vol orienté préparation : accès Finder/Fuel/carte, pistes locales consultables,
   portes inconnues explicitement signalées, aucune affectation opérationnelle
   inventée. Journal chronométré des vols réellement confirmés par l'utilisateur.
5. Dix couleurs partagées Windows/Android, recherche dans les sélecteurs, icônes
   Android et rappels locaux facultatifs. Aucun rappel sans activation explicite.
6. Satellite/vent Android facultatifs et désactivés initialement : mêmes sources
   PC, HTTPS limité aux fournisseurs, cache borné et requêtes séparées du moteur.
   Messages/Finder/Fuel/carte locale restent utilisables en mode avion.
7. Construire APK/Windows, tester et fournir un guide GitHub simple avec liens
   vérifiés. Décrire honnêtement les limites Apple et appareil physique.

Références : [insets Android](https://developer.android.com/develop/ui/views/layout/edge-to-edge),
[notifications](https://developer.android.com/develop/ui/compose/notifications/notification-permission),
[EOX](https://maps.eox.at/), [Open-Meteo](https://open-meteo.com/en/docs).

Les résultats et limites seront complétés après vérification.
