# Intégration RFS Fuel Helper

Application inspectée : Python 3.13, PySide6, persistance JSON locale dans `storage.Store`.
Le vol commun est `state['flight']` ; les messages lisent son champ `fuel` en kg.
Le Finder ne calcule pas le carburant et ne fournit pas de taux de consommation.

Les cinq fichiers utiles du ZIP ont été inspectés : spécification, moteur de
référence, tests, catalogue avions et alternates. `reference/` conserve le transfert
original. Le calcul sera isolé dans `fuel/`, sans Discord ni service réseau.

Contrat : choix explicite d'un identifiant stable, formule inchangée, aucun arrondi
intermédiaire ; arrondi half-even uniquement à l'affichage. La durée conseillée
supplémentaire de 20–30 minutes reste une consigne, jamais un ajout automatique.
Le bouton de transfert explicite met à jour le carburant du vol existant et conserve
le détail non arrondi ainsi que la provenance dans `fuel_calculation`.

Les variantes ambiguës ne sont pas résolues automatiquement. Un appareil issu du
Finder peut suggérer une recherche, mais l'utilisateur doit choisir la variante
exacte si aucun nom/identifiant exact n'existe.

Texte permanent : « Estimation pour RFS / simulation uniquement — ne pas utiliser
pour préparer un vol réel. » Les alternates restent statiques, sans vérification
météo/NOTAM/piste/masse/performance. Les champs de confiance et les notes du catalogue
restent visibles, notamment l'estimation BelugaXL.
