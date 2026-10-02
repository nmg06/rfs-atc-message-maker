# Calculateur de carburant RFS — spécification de transfert

Ce dossier permet de réintégrer dans une autre application le calcul actuellement utilisé par **RFS Fuel Helper**, sans Discord, token, serveur ou dépendance externe.

Il s'agit d'une estimation pour **Real Flight Simulator**. Ce calcul n'est pas un outil de préparation de vol réel.

## Entrées

- `aircraft_id` : identifiant stable provenant de `aircraft_fuel_data.json` ;
- `hours` : durée de vol planifiée, nombre fini strictement supérieur à zéro ;
- `arrival_icao` : code ICAO facultatif utilisé pour chercher un dégagement statique.

L'interface doit afficher une liste/autocomplétion fondée sur les identifiants et noms du JSON. Elle ne doit pas laisser une correspondance ambiguë choisir silencieusement le mauvais avion.

Le message historique du bot recommande d'ajouter **20 à 30 minutes** au temps produit par le planificateur RFS avant de saisir `hours`. Cette correction est une consigne pour l'utilisateur : le moteur ne l'ajoute pas automatiquement.

## Constantes exactes

| Constante | Valeur |
|---|---:|
| Multiplicateur de consommation au roulage | 1,4 |
| Roulage départ | 6 min |
| Roulage arrivée | 4 min |
| Contingence | 5 % du carburant trajet |
| Réserve finale | 30 min à la consommation de croisière |
| Vitesse de calcul vers le dégagement | 450 kt |
| Temps d'approche ajouté au dégagement | 15 min |

## Formules

Soit :

- `B` = consommation de croisière de l'avion en kg/h ;
- `H` = durée planifiée en heures ;
- `D` = distance vers l'alternate retenu en NM.

```text
taxi_rate        = B × 1.4
taxi_out         = taxi_rate × 6 / 60
trip             = B × H
contingency      = trip × 0.05
final_reserve    = B × 30 / 60
taxi_in          = taxi_rate × 4 / 60

alternate_time   = D / 450 + 15 / 60
alternate_fuel   = B × alternate_time

total_block_fuel = taxi_out
                 + trip
                 + contingency
                 + alternate_fuel
                 + final_reserve
                 + taxi_in
```

Si aucun ICAO n'est fourni, ou si l'ICAO n'existe pas dans `airport_alternates.json`, `alternate_fuel = 0`. Dans ce cas, on n'ajoute pas les 15 minutes d'approche.

Si plusieurs dégagements existent pour l'arrivée, sélectionner la distance `distance_nm` minimale. Les distances sont statiques et exprimées en milles nautiques.

Formule condensée lorsqu'un dégagement existe :

```text
total = B × [1.4 × (6 + 4) / 60 + 1.05 × H + 30 / 60 + D / 450 + 15 / 60]
```

## Exemple contrôlé

Entrées : Airbus A220-300, `B = 1 950 kg/h`, `H = 5 h`, arrivée `EGLL`. Le dégagement le plus proche configuré est `EGKK`, à 30 NM.

| Bloc | Valeur exacte | Affichage actuel |
|---|---:|---:|
| Taxi départ | 273 kg | 273 kg |
| Trajet | 9 750 kg | 9 750 kg |
| Contingence | 487,5 kg | 488 kg |
| Alternate | 617,5 kg | 618 kg |
| Réserve finale | 975 kg | 975 kg |
| Taxi arrivée | 182 kg | 182 kg |
| **Total bloc** | **12 285 kg** | **12 285 kg** |

Le bot Python affiche chaque bloc au kilogramme le plus proche avec l'arrondi « half to even ». Conserver les valeurs non arrondies pendant tout le calcul et arrondir uniquement pour l'affichage.

## Endurance et erreurs

`max_endurance` est au format `HH:MM`. Si `hours` dépasse cette valeur, afficher un avertissement indiquant qu'une escale ravitaillement est nécessaire. Cet avertissement ne modifie pas le total.

Refuser proprement : durée nulle/négative/non finie, avion inconnu ou consommation absente/invalide. Un ICAO sans alternate reste autorisé, avec carburant alternate nul et un message explicite.

## Données fournies

- `aircraft_fuel_data.json` : 63 avions et leurs consommations actives ;
- `airport_alternates.json` : 64 arrivées et leurs candidats ;
- `fuel_calculator.py` : implémentation autonome de référence ;
- `test_fuel_calculator.py` : tests de l'exemple et des erreurs ;
- `PROMPT_A_COPIER.md` : consigne prête pour une autre conversation.

Les taux sont ceux du bot actuel. La majorité provient de la liste fournie par l'utilisateur. Le BelugaXL utilise une estimation explicitement signalée ; les champs `burn_confidence` et `burn_note` ne doivent pas être supprimés de l'application.

Les dix destinations marquées `recovered_original` viennent de la récupération du bot. Les entrées `later_static_addition` et `real_routes_addition` sont des ajouts ultérieurs. Tous les alternates sont des suggestions statiques RFS : météo, NOTAM, piste, masse et performances ne sont pas vérifiés en temps réel.
