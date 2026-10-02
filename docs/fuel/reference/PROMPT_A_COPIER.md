Je veux intégrer dans mon application le calculateur de carburant de mon bot Discord **RFS Fuel Helper**.

J'ai joint le dossier `RFS_Fuel_Calculator_Transfer` contenant :

- `SPECIFICATION_FR.md` : comportement et formules exactes ;
- `aircraft_fuel_data.json` : catalogue de 63 avions ;
- `airport_alternates.json` : 64 aéroports d'arrivée et leurs alternates ;
- `fuel_calculator.py` : implémentation Python autonome de référence ;
- `test_fuel_calculator.py` : résultats attendus et cas d'erreur.

Inspecte d'abord mon application existante et identifie son langage, son architecture, son système de données et l'endroit approprié pour intégrer cette fonctionnalité. Ensuite, adapte le calcul au langage et à l'interface de l'application sans dépendre de Discord et sans modifier les autres fonctionnalités.

Contraintes :

1. Respecter exactement les constantes, formules, unités et règles d'alternate de `SPECIFICATION_FR.md`.
2. Utiliser les identifiants stables des avions et une liste/autocomplétion ; ne pas sélectionner silencieusement une variante ambiguë.
3. Conserver les valeurs exactes pendant le calcul et arrondir seulement l'affichage.
4. Afficher séparément taxi départ, trajet, contingence, alternate, réserve finale, taxi arrivée et total bloc.
5. Afficher l'alternate choisi, sa distance et l'avertissement d'endurance lorsqu'il s'applique.
6. Si l'arrivée est absente ou inconnue, mettre l'alternate à zéro et l'expliquer clairement.
7. Afficher en permanence : « Estimation pour RFS / simulation uniquement — ne pas utiliser pour préparer un vol réel. »
8. Préserver les champs de provenance et de confiance ; ne pas inventer ou remplacer une consommation manquante.
9. Tester au minimum l'exemple A220-300 / 5 h / EGLL, les entrées invalides, un avion inconnu, une arrivée inconnue, plusieurs alternates et le dépassement d'endurance.
10. Ne pas mettre de token, mot de passe ou secret dans le code ou les données.

À la fin, indique les fichiers modifiés, montre un exemple de résultat dans l'application et exécute les tests adaptés au projet.
