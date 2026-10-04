# Corrections et aide — étape 0.4.1

Demandes conservées depuis les derniers messages : langue sans mélange,
défilement des sélecteurs, copie libre facultative et avertissements cliquables,
tutoriel de rubrique que l’on peut passer/revoir, 30 questions fréquentes,
explications communes PC/Android/web. Vérifier les autres écrans concernés.

Déjà livrés en 0.4 : zones de sécurité Android, menu paramètres avec retour,
Finder local et pagination, durée numérique en heures, choix de variante avion
et transfert vers Fuel, sauvegarde automatique, dix palettes PC/Android,
carte avec frontières, satellite et vents optionnels, carnet, rappel local,
icônes Android et guides de téléchargement. Les tests d’un téléphone physique
restent à faire par l’utilisateur ; iOS natif n’est pas livré.

À conserver explicitement : pas de vols inventés, pas de portes ou d’affectation
de piste devinées, pas de météo RFS prétendument identique aux données réelles,
pas de notifications ou requêtes de fond sans choix, pas de release publique
automatique. Le prototype web n’a pas la parité complète des applications.

ETE 5 min dans ARRIVAL BOARD signifie une arrivée dans environ cinq minutes.
La durée totale du vol reste un autre champ utilisé par Fuel Helper.

Vérifications locales du 4 octobre 2026 : 122 tests Windows et 27 tests du
moteur Android passent. Les trois parcours Android dans Chrome et le parcours
prototype web passent : langue, aide, FAQ, avertissements, copie libre et reprise.
567 combinaisons de calcul Fuel web sont comparées aux composants exacts du PC.

Les deux premières constructions Windows et Android ont réussi. Les APK app et
androidTest sont compilées en 0.4.1 (versionCode 5). Une reconstruction finale
et la vérification du paquet restent en cours ; les tests natifs 0.4.1 ne sont
pas encore confirmés. Aucune installation sur téléphone physique n’est affirmée.

Le build Windows GitHub, les 122 tests, l’audit de dépendances et CodeQL passent
sur `9628391`. Le premier test Android échoue sur le focus du presse-papiers :
le rapport réel identifie une fenêtre **Application Not Responding: com.android.launcher3**
au-dessus de Flightdeck, qui est visible et réveillé. Le test vérifie désormais
ce cas exact et ferme uniquement ce lanceur bloqué sur matériel d’émulateur.
Les assertions de focus, lecture du presse-papiers, copie libre et alertes sont
conservées ; aucune modification correspondante de l’application livrée.

Source de l’aide : `help_content.py`. Adaptateurs : `help_dialog.py`,
`assets/help-ui.js`, Android et `mobile/help-adapter.js`. Les préférences
`strict_validation` et `tutorial_seen` restent dans les sauvegardes locales.
Le correctif de molette est commun dans `ux.py` ; les palettes traduites gardent
leurs identifiants canoniques. Le Fuel web auparavant sans fonctions effectives
utilise les constantes et JSON PC exportés, sans modifier le calcul Windows.
