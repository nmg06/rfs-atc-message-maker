# SEARCH_ENGINE.md — Moteur de recherche déterministe

Version 0.1 — 2026-09-30

Le moteur ne contient **aucun LLM, aucun aléa, aucun appel réseau**. Même entrée + même base + même horloge injectée = même sortie, octet pour octet.

Le pseudo-code est volontairement indépendant du langage (le projet existant n'a pas pu être inspecté). Les noms de tables viennent de DATABASE_SCHEMA.md.

---

## 1. Principes de conception

1. **Fonctions pures.** `search(criteria, db, clock, tz_db) -> SearchResponse`. L'horloge (`now_utc`) est **injectée**, jamais lue dans le moteur. Le fuseau du serveur n'est jamais utilisé.
2. **Deux étages.** (a) Récupération SQL des candidats avec tous les filtres durs. (b) Scoring et tri en code, dans une fonction pure testable.
3. **Filtres durs vs préférences.** Un critère est `require` (filtre) ou `prefer` (score). Les exclusions sont toujours des filtres.
4. **Explicabilité.** Chaque résultat porte les sous-scores normalisés et des codes de raison, pas les poids bruts.
5. **Honnêteté des données.** Un résultat ne dit jamais "programmé" ; il dit "observé" ou "basé sur un pattern observé".
6. **Dégradation contrôlée.** Trop peu de résultats → relâchement déterministe et déclaré (§9).

---

## 2. Entrée : `SearchCriteria` (v1)

```json
{
  "schema_version": 1,
  "search_mode": "flights",
  "user_tz": "Europe/Paris",

  "airline":   { "ids": [], "mode": "require" },
  "aircraft":  { "type_icao": [], "family_ids": [], "manufacturers": [], "mode": "require" },

  "origin":      { "airports": [], "countries": [], "continents": [], "groups": [] },
  "destination": { "airports": [], "countries": [], "continents": [], "groups": [] },
  "exclude":     { "airports": [], "countries": [], "continents": [], "groups": [], "applies_to": "either" },

  "duration_min": { "target": null, "min": null, "max": null, "tolerance": null, "fit_policy": "use_available" },
  "distance_nm":  { "min": null, "max": null },

  "time": {
    "mode": "sim_start",
    "departure": null,
    "arrival": null,
    "arrival_tolerance_min": 60
  },

  "international_only": false,
  "real_routes_only": true,

  "rfs": { "compatible_aircraft_only": false, "verified_livery_only": false },

  "limit": 10,
  "min_results": 5,
  "diversity": "route"
}
```

Sémantique des champs :

| Champ | Règle |
|---|---|
| `search_mode` | `flights` (patterns, avec heures) ou `routes` (liste de routes réelles distinctes, sans heures) |
| `airline.ids` | `airline_id` déjà résolus. Le front appelle `/suggest/airlines` pour résoudre "Air India", "AI" ou "AIC" |
| `aircraft.*` | union des trois listes ; voir scoring d'exactitude §7.4 |
| `origin` / `destination` | union logique des listes à l'intérieur d'un bloc ; ET entre blocs |
| `exclude.applies_to` | `either` (défaut : ni départ ni arrivée dans l'ensemble exclu), `origin`, `destination` |
| `duration_min.target` | durée airborne visée en minutes |
| `duration_min.min/max` | intervalle accepté |
| `duration_min.fit_policy` | utilisé seulement si `max` seul est donné : `use_available` (préférer les vols qui remplissent le temps dispo) ou `shortest` |
| `time.mode` | `sim_start` (défaut) ou `real_schedule` |
| `time.departure` | `{"kind":"in_minutes","value":30}` ou `{"kind":"at_local","date":"today|tomorrow|YYYY-MM-DD","time":"HH:MM","tz":"IANA"}` |
| `time.arrival` | `{"kind":"at_local", …}` uniquement |
| `real_routes_only` | Phase 1 : **doit être `true`** ; `false` renvoie l'erreur `NOT_SUPPORTED_PHASE1` |
| `diversity` | `none` ou `route` (max 2 résultats par (origine, destination, compagnie)) |

**Validation d'entrée stricte** (bibliothèque de schéma du projet) : listes limitées (≤ 50 éléments), nombres bornés (durée 0–1 440 min, distance 0–10 000 nm), fuseaux validés contre la base IANA, rejet de tout champ inconnu. Toutes les valeurs passent en **paramètres SQL liés**, jamais en concaténation.

---

## 3. Résolution du temps (correct vis-à-vis des fuseaux et de l'heure d'été)

Règle absolue : **aucun décalage en dur**. Tout passe par des identifiants IANA et une bibliothèque de fuseaux épinglée (`zoneinfo` + `tzdata` en Python ; `Temporal`, `Luxon` ou `Intl` en JS). Interdit : `+1`, `+2`, `timedelta(hours=1)` pour "la France".

### 3.1 Conversion d'une heure locale demandée en instant UTC

```
function local_to_utc(date_local, time_local, tz_iana):
    # date_local : 'YYYY-MM-DD' ; 'today'/'tomorrow' se résolvent dans tz_iana avec now_utc
    candidates = all instants whose wall-clock time in tz_iana equals (date_local, time_local)
    if len(candidates) == 0:       # heure inexistante (passage à l'heure d'été)
        return first valid instant AFTER the gap, flag = 'DST_GAP_SHIFTED'
    if len(candidates) == 2:       # heure ambiguë (retour à l'heure d'hiver)
        return the EARLIER instant, flag = 'DST_AMBIGUOUS_EARLIER'
    return candidates[0]
```

Cas à tester obligatoirement pour `Europe/Paris` en 2026 : passage à l'heure d'été le dimanche 29 mars (02:30 n'existe pas) et retour à l'heure d'hiver le dimanche 25 octobre (02:30 existe deux fois). Ajouter `America/New_York`, `Asia/Kolkata` (décalage de 5 h 30), `Australia/Lord_Howe` (30 min de DST), `Africa/Casablanca` (DST inversé autour du ramadan) et `Pacific/Kiritimati` (UTC+14).

Exemple : le 30 septembre 2026, "demain 07:00 à Paris" est le 1er octobre à 07:00 CEST, soit 05:00 UTC. Un code qui ajouterait un simple +1 h donnerait 06:00 UTC et serait faux d'une heure.

### 3.2 Mode `sim_start` (défaut)

L'utilisateur choisit quand il commence le vol dans le simulateur. Les horaires réels de la compagnie sont ignorés.

```
function resolve_sim_times(time, duration, now_utc, user_tz):
    dep_utc = None; arr_target_utc = None
    if time.departure:
        if kind == 'in_minutes':  dep_utc = now_utc + minutes(value)
        if kind == 'at_local':    dep_utc = local_to_utc(date, time, tz or user_tz)
    if time.arrival:
        arr_target_utc = local_to_utc(date, time, tz or user_tz)

    implied = None
    if dep_utc and arr_target_utc:
        implied = minutes_between(dep_utc, arr_target_utc)      # différence d'INSTANTS, donc sûre vis-à-vis du DST
        if implied <= 0: error 'ARRIVAL_BEFORE_DEPARTURE'
        if duration.target is None and duration.min is None and duration.max is None:
            duration.target = implied                            # la durée est DÉRIVÉE
        else if duration.target and abs(implied - duration.target) > tolerance(duration):
            warn 'TIME_INCONSISTENT' {implied, given: duration.target}
            # priorité déclarée : la durée explicite gagne, l'arrivée visée devient un critère souple de poids réduit
    return dep_utc, arr_target_utc, implied, warnings
```

Point important : **départ + arrivée + durée sont redondants.** Deux d'entre eux déterminent le troisième. L'exemple de la demande initiale (départ dans 30 minutes, arrivée demain 07:00 heure de Paris, durée ≈ 10 h) n'est cohérent que si l'heure actuelle est d'environ 20 h 30 à Paris. Dans tout autre cas, le moteur doit le détecter et le dire plutôt que de trier sur des critères contradictoires.

Pour chaque candidat : `arrival_utc = dep_utc + dur_median`. Affichage : heure locale à l'aéroport d'arrivée **et** heure locale de l'utilisateur, calculées avec `dest.tz_iana` et `user_tz`. Si `dest.tz_iana` est NULL, afficher l'UTC seul avec la mention "fuseau inconnu".

### 3.3 Mode `real_schedule` (option)

Projette l'horaire local typique du pattern sur les prochains jours.

```
function next_occurrences(pattern, now_utc, horizon_days=7, min_lead_min=10):
    tz = origin.tz_iana                       # si NULL → pattern exclu de ce mode
    local_today = date_of(now_utc, tz)
    for k in 0..horizon_days:
        d = local_today + k days
        if weekday(d) not in pattern.weekday_mask: continue     # weekday en date LOCALE
        dep_utc = local_to_utc(d, pattern.dep_local_min_median, tz)
        if dep_utc < now_utc + min_lead_min: continue
        arr_utc = dep_utc + pattern.dur_median_min
        yield Occurrence(dep_utc, arr_utc, basis='PATTERN_BASED')
```

Les occurrences sont libellées `PATTERN_BASED` ("basé sur les horaires observés") et jamais "programmé". Si la date cible tombe dans une autre saison IATA que la fenêtre d'observation, ajouter l'avertissement `SEASON_MISMATCH`.

---

## 4. Normalisation des entrées

- Aéroport : accepte ICAO (`LFPG`), IATA (`CDG`), ou l'`airport_id` choisi dans l'autocomplétion. Le backend résout en `airport_id` avant de chercher.
- Compagnie : alias normalisés (minuscules, sans accents) vers `airline_id` via `airline_aliases`.
- Avion : `aircraft_type_aliases` (`a321neo`, `a21n`, `a321 neo`) → `type_icao`. Les familles et constructeurs viennent d'`aircraft_families` / `aircraft_types.manufacturer`.
- Pays : ISO2. Continent : codes OurAirports (`AF`, `AS`, `EU`, …) après `continent_overrides`.
- Groupes géographiques : `geo_groups` (par exemple "EU27", "EEA", "ECAC", "Europe géographique"). L'interface doit dire quel sens de "Europe" est utilisé.

---

## 5. Récupération des candidats (SQL)

Tous les filtres durs sont en SQL, avec `ORDER BY` total pour que la troncature éventuelle soit déterministe.

```sql
SELECT *
FROM v_pattern_search
WHERE n_complete >= :min_complete                     -- config, défaut 3
  AND dur_median_min IS NOT NULL
  AND (:airline_n = 0      OR airline_id IN (:airline_ids))
  AND (:aircraft_n = 0     OR type_icao IN (:types) OR family_id IN (:families) OR manufacturer IN (:manufs))
  AND (:origin_n = 0       OR origin_icao IN (:o_airports) OR origin_country IN (:o_countries) OR origin_continent IN (:o_continents))
  AND (:dest_n = 0         OR dest_icao   IN (:d_airports) OR dest_country   IN (:d_countries) OR dest_continent   IN (:d_continents))
  AND NOT (origin_icao IN (:x_airports) OR origin_country IN (:x_countries) OR origin_continent IN (:x_continents))   -- si applies_to ∈ {either, origin}
  AND NOT (dest_icao   IN (:x_airports) OR dest_country   IN (:x_countries) OR dest_continent   IN (:x_continents))   -- si applies_to ∈ {either, destination}
  AND (:international = 0  OR origin_country <> dest_country)
  AND dur_median_min BETWEEN :dur_lo AND :dur_hi      -- bornes issues de min/max ou de target ± tolérance (§7.1)
  AND distance_nm    BETWEEN :dist_lo AND :dist_hi
ORDER BY n_obs DESC, last_seen_utc DESC, pattern_id ASC
LIMIT :hard_cap;                                      -- 20 000
```

Les blocs `IN (:liste)` vides sont supprimés par le constructeur de requête (paramètres liés, pas de chaînes assemblées). Les exclusions par groupe sont résolues en listes de pays avant la requête.

Pour les filtres "RFS compatible seulement" et "livery vérifiée seulement", le backend interroge `rfs_compat.sqlite` **avant** la requête principale et passe les `type_icao` / `airline_icao` admissibles comme listes.

---

## 6. Mode `routes`

Sert des demandes du type "montre-moi les routes réelles d'Air India avec l'A321neo". Même retrieval sur `route_stats` (au lieu de `flight_patterns`), groupé par (origine, destination), avec : compagnies, types observés, `n_obs` total, durée médiane, distance, `last_seen_utc`, et la liste des callsigns connus (depuis `flight_patterns`). Tri : `n_obs DESC, last_seen_utc DESC, origin_icao, dest_icao`. Pas de scoring temporel.

---

## 7. Scoring

Score final sur 0–100. Chaque sous-score `s_c` est dans [0, 1].

```
active = { c : critère c soft et renseigné }
quality = { frequency, recency, confidence }                  # toujours actifs

S = 100 * ( Σ_{c ∈ active} w_c * s_c  +  Σ_{q ∈ quality} w_q * s_q )
          / ( Σ_{c ∈ active} w_c      +  Σ_{q ∈ quality} w_q )
```

Les poids sont renormalisés sur les critères réellement actifs : si l'utilisateur ne donne pas d'heure d'arrivée, ce critère n'influence pas le score.

### 7.0 Poids par défaut (`config/finder.weights.yaml`)

| Critère | Poids |
|---|---|
| `duration` | 30 |
| `arrival_time` | 25 |
| `departure_time` (mode `real_schedule` seulement) | 15 |
| `aircraft` | 15 |
| `airline` (si `prefer`) | 10 |
| `distance` (si intervalle soft) | 10 |
| `frequency` | 10 |
| `recency` | 5 |
| `confidence` | 5 |

### 7.1 Durée

Soit `d = dur_median_min` du candidat.

- **Cible donnée** (`target = T`) : `tol = tolerance ?? max(30, 0.15 × T)` ; `s = max(0, 1 − |d − T| / tol)`.
- **Intervalle donné** (`min`, `max`) : `s = 1` si `d ∈ [min, max]`, sinon décroissance linéaire jusqu'à 0 à `tol` hors de l'intervalle, avec `tol = tolerance ?? max(20, 0.10 × (max − min))`.
- **`max` seul** (par exemple "j'ai 2 heures") : `fit_policy = use_available` → `s = d / max` si `d ≤ max` (le vol qui remplit le temps disponible est meilleur) ; `shortest` → `s = 1 − d / max`. Le défaut `use_available` est un **choix de produit** à valider ; il est configurable.

Plafond dur : un candidat dont `s_duration = 0` est éliminé. Les bornes SQL `dur_lo`/`dur_hi` du §5 sont donc `T ± tol` ou `min − tol`/`max + tol`.

### 7.2 Heure d'arrivée (mode `sim_start`)

`arrival_candidat = dep_utc + d`. `Δ = |arrival_candidat − arr_target_utc|` en minutes.
`s = max(0, 1 − Δ / tol_arr)`, `tol_arr = time.arrival_tolerance_min` (défaut 60). Éliminé si `s = 0`.

Si l'heure d'arrivée est **dérivée** (départ + arrivée donnés), le critère `arrival_time` est retiré et c'est `duration` qui porte l'information (évite de compter deux fois la même contrainte).

### 7.3 Heure de départ (mode `real_schedule`)

Pour chaque occurrence projetée (§3.3), calculer l'écart à la demande ; retenir l'occurrence qui maximise `s`. Même formule linéaire, tolérance par défaut 45 min.

### 7.4 Correspondance d'avion

- type exact demandé : `1.0`
- même famille : `0.7`
- même constructeur : `0.4`
- autre : `0` (éliminé si `mode = require`)

Si plusieurs niveaux sont fournis, prendre le meilleur niveau atteint.

### 7.5 Compagnie

`prefer` : `1` si la compagnie est dans la liste, sinon `0`. En `require` c'est un filtre, pas un score.

### 7.6 Qualité (toujours actifs)

- `frequency` : `s = min(1, ln(1 + n_obs) / ln(1 + N_ref))` avec `N_ref = 60`. Sature pour les vols très réguliers.
- `recency` : `s = 0.5 ^ (jours_depuis_last_seen / 30)` (demi-vie de 30 jours).
- `confidence` : `s = n_complete / n_obs` (part d'observations à trace complète, décollage et toucher sur piste).

### 7.7 Pénalités et avertissements (n'altèrent pas le score, s'affichent)

| Code | Condition |
|---|---|
| `LOW_OBSERVATIONS` | `n_obs < 5` |
| `STALE` | `last_seen` plus vieux que 45 jours |
| `LOW_COVERAGE_REGION` | origine ou destination dans une région à couverture ADS-B faible (liste maintenue dans la config) |
| `TZ_UNKNOWN` | un aéroport sans `tz_iana` |
| `MIXED_TYPES` | `type_mix_json` contient plusieurs types |
| `SEASON_MISMATCH` | mode `real_schedule`, saison IATA de la date cible ≠ saison de la fenêtre d'observation |
| `DURATION_IS_AIRBORNE` | toujours présent (la durée est décollage → atterrissage, pas temps bloc ni durée RFS) |

---

## 8. Tri, diversité, pagination

Tri total, stable et déterministe :

```
ORDER BY score DESC,
         n_obs DESC,
         last_seen_utc DESC,
         callsign ASC,
         origin_icao ASC,
         dest_icao ASC,
         pattern_id ASC
```

Score arrondi à 3 décimales avant comparaison (évite les divergences d'arrondi flottant entre plateformes).

Diversité (`diversity = route`) : après tri, garder au plus 2 résultats par (origine, destination, compagnie). Les résultats écartés sont comptés dans `meta.diversity_dropped`.

---

## 9. Relâchement déterministe si peu de résultats

Si `len(results) < min_results`, appliquer **dans cet ordre**, en s'arrêtant dès que `min_results` est atteint :

1. Tolérance de durée × 1.5.
2. Tolérance d'arrivée × 2.
3. Élargir `recency`/`STALE` : accepter `last_seen` jusqu'à 90 jours.
4. Transformer les critères `prefer` en absents (ils ne filtraient pas, mais ne comptent plus).

Jamais relâchés : exclusions, `require`, `real_routes_only`, filtres RFS. La réponse contient `meta.relaxations_applied = ["DURATION_TOL_x1.5", ...]` et l'interface le dit à l'utilisateur. Si même après relâchement il y a 0 résultat, la réponse contient `meta.empty_reason` (code) avec le critère qui élimine le plus de candidats (calculé en retirant les filtres un par un et en comptant).

---

## 10. Sortie : `SearchResponse`

```json
{
  "schema_version": 1,
  "meta": {
    "mode": "sim_start",
    "now_utc": "2026-09-30T18:30:00Z",
    "dep_utc": "2026-09-30T19:00:00Z",
    "arr_target_utc": "2026-10-01T05:00:00Z",
    "implied_duration_min": 600,
    "candidates_retrieved": 184,
    "results_returned": 10,
    "relaxations_applied": [],
    "warnings": [],
    "data": {
      "observed_from": "2026-06-01", "observed_to": "2026-09-15",
      "dataset_versions": [{ "source_id": "mrairspace", "version_label": "2026_Q2" }],
      "attributions": ["…"]
    }
  },
  "results": [
    {
      "pattern_id": 1234,
      "score": 87.4,
      "subscores": { "duration": 0.92, "arrival_time": 0.85, "aircraft": 1.0, "frequency": 0.78, "recency": 0.95, "confidence": 0.90 },
      "reasons": ["EXACT_AIRCRAFT", "DURATION_CLOSE", "ARRIVAL_WITHIN_TOLERANCE"],
      "warnings": ["DURATION_IS_AIRBORNE"],
      "flight": {
        "airline": { "icao": "AIC", "iata": "AI", "name": "Air India" },
        "callsign": "AIC…", "flight_number_iata": "AI…", "flight_number_source": "DERIVED_FROM_CALLSIGN",
        "aircraft": { "type_icao": "A21N", "manufacturer": "Airbus", "rfs_compat": "UNKNOWN" },
        "origin": { "icao": "…", "iata": "…", "tz_iana": "…" },
        "destination": { "icao": "…", "iata": "…", "tz_iana": "…" },
        "distance_nm": { "value": 0, "status": "DERIVED" },
        "duration_airborne_min": { "value": 0, "status": "OBSERVED", "p10": 0, "p90": 0 },
        "times": { "departure_utc": "…", "arrival_utc": "…", "basis": "SIM_START" },
        "freshness": { "n_obs": 0, "n_complete": 0, "last_seen_utc": "…" }
      }
    }
  ]
}
```

Le front **n'envoie jamais** les poids et ne les reçoit pas. Les sous-scores servent à l'explication visuelle ; ils ne permettent pas de reconstituer la formule exacte sans sonder massivement l'API (ce qui est limité par le rate-limit, voir SPEC §11).

---

## 11. Exemples de requêtes (correspondance avec la demande initiale)

### A. Air India, Airbus, environ 10 h, exclure EGLL et l'Europe

```json
{ "airline": { "ids": ["<AIC>"], "mode": "require" },
  "aircraft": { "manufacturers": ["Airbus"], "mode": "require" },
  "exclude": { "airports": ["EGLL"], "continents": ["EU"], "applies_to": "either" },
  "duration_min": { "target": 600 },
  "time": { "mode": "sim_start",
            "departure": { "kind": "in_minutes", "value": 30 },
            "arrival":   { "kind": "at_local", "date": "tomorrow", "time": "07:00", "tz": "Europe/Paris" } },
  "real_routes_only": true }
```

Comportements attendus : tout résultat est de compagnie Air India, de constructeur Airbus, sans EGLL ni aéroport d'Europe à l'origine ou à la destination ; la durée et l'arrivée sont scorées ; un avertissement `TIME_INCONSISTENT` est émis si `arrivée − départ` s'écarte de 10 h au-delà de la tolérance. "Exclure l'Europe" élimine aussi les vols *vers* l'Europe, ce qui, pour cette compagnie, peut retirer une grande partie des long-courriers : l'interface doit afficher le nombre de candidats éliminés par cette exclusion.

### B. Simple : 2 heures, A320neo, départ LFPG

```json
{ "origin": { "airports": ["LFPG"] },
  "aircraft": { "type_icao": ["A20N"], "mode": "require" },
  "duration_min": { "max": 120, "fit_policy": "use_available" } }
```

### C. Réel, 8 à 11 h, Afrique → Asie, Airbus, compagnie indifférente

```json
{ "origin": { "continents": ["AF"] }, "destination": { "continents": ["AS"] },
  "aircraft": { "manufacturers": ["Airbus"], "mode": "require" },
  "duration_min": { "min": 480, "max": 660 } }
```

Attendu : peu de résultats possibles (couverture ADS-B plus faible), avec `LOW_COVERAGE_REGION` si applicable. Le moteur doit le signaler plutôt que de combler avec des routes fictives.

### D. Mode routes : Air India, A321neo

```json
{ "search_mode": "routes",
  "airline": { "ids": ["<AIC>"], "mode": "require" },
  "aircraft": { "type_icao": ["A21N"], "mode": "require" } }
```

---

## 12. Tests obligatoires

**Unitaires (fonctions pures)** : chaque formule de §7 avec valeurs limites (0, tolérance exacte, dépassement) ; `local_to_utc` sur les cas DST de §3.1 ; médiane circulaire de minuit ; `weekday_mask` en date locale.

**Golden tests** : une base de fixture de ~30 patterns écrite à la main (`tests/fixtures/finder_fixture.sql`), avec 15 requêtes dont les résultats attendus sont figés (ordre exact et scores à 3 décimales).

**Déterminisme** : exécuter la même requête deux fois, puis sous `TZ=America/Los_Angeles` et `TZ=Asia/Tokyo` (variable d'environnement du processus), puis avec une locale différente : les sorties doivent être identiques octet pour octet.

**Propriétés** : (a) aucun résultat ne viole un filtre dur ; (b) score ∈ [0, 100] ; (c) tri total, sans égalité indéterminée ; (d) ajouter une exclusion ne fait jamais apparaître de nouveau résultat.

**Honnêteté des données** : un test vérifie qu'aucune réponse ne contient `ESTIMATE` ou `LIKELY` dans un champ destiné à Discord, et qu'aucun résultat ne porte le libellé "scheduled".

**Performance (objectif, non mesuré)** : p95 < 300 ms pour ≤ 20 000 candidats sur une machine modeste. À mesurer avec la vraie base.

---

## 13. Ce qui est volontairement hors du moteur en Phase 1

Estimation de durée pour des routes jamais observées (nécessiterait un modèle vitesse/vent, marqué `ESTIMATE`), piste "probable" selon le vent, liveries, vérification live. Les critères correspondants sont absents du schéma de requête v1 ou renvoient `NOT_SUPPORTED_PHASE1`.
