# RFS Flightdeck

Ancien nom : RFS ATC Message Maker. Messages Discord, Flight Finder local,
RFS Fuel Helper et aperçu cartographique pour Real Flight Simulator.
Les fonctions principales Windows et Android fonctionnent sans compte ni Internet.

**Vous voulez installer l'application ?** Il suffit de télécharger le ZIP Windows
ou l'APK Android : Python n'est pas nécessaire. Le [guide pas à pas](docs/INSTALLATION.md)
explique les boutons de téléchargement, l'installation, le premier vol et les
solutions aux problèmes fréquents. Aucune version iPhone installable actuellement.

**[Téléchargement et installation Windows / Android / état iPhone](docs/INSTALLATION.md)**

**[Tutoriel, 30 questions fréquentes et copie libre](docs/HELP.md)** — aide
consultable dans l’application, que l’on peut passer et retrouver ensuite.

Les améliorations Flightdeck sont sur `feat/flightdeck-map-performance`, la première
APK sur `feat/android-offline`. Les workflows produisent des artefacts de test,
sans publier automatiquement une nouvelle release.

## Utiliser

Ouvrez `RFSATCMessageMaker.exe` dans le paquet téléchargé. Gardez le dossier
`RFSFlightdeck` entier : l'exécutable utilise les fichiers de `_internal`.
Le paquet est autonome : Python n'est pas nécessaire pour l'utiliser.
Il cible Windows 10/11 64 bits.

Pour préparer un vol sans ATC, commencez par Flight Finder, utilisez le vol choisi,
puis ouvrez Fuel Helper. Les messages restent facultatifs. Le guide d'installation
explique aussi le carnet Android, les palettes et les rappels.

1. Sélectionnez `ATC REQUEST` et renseignez le panneau `Vol actuel`.
2. Complétez la porte, la piste, le pushback et les autres champs signalés par `*`.
3. Cliquez sur `Copier le message`. La confirmation apparaît sur le bouton ; le texte est conservé dans l'historique.
4. Passez à `AIRBORNE`, `ARRIVAL BOARD` puis `FLIGHT COMPLETED` : les données
   du vol restent remplies. `Sauver le vol` permet aussi de le rappeler plus tard.

L'aperçu se met à jour pendant la saisie et reste modifiable. `Générer` recrée
le texte à partir des champs. `Effacer` vide le vol courant et les informations
des messages, en conservant pilotes, préférences et vols sauvegardés.
Le pseudo RFS `n1chita` est proposé par défaut ; `NIKA` est disponible.

Les données et journaux locaux sont dans `data/`, à côté du script ou du fichier
exécutable. Les fichiers JSON de l'ancienne application restent intacts.

## Construction et tests

Une première application **Android installable et hors ligne** existe désormais
dans `android/`, à côté de Windows : moteurs Python partagés, Flight Finder avec
base embarquée, Fuel Helper, carte locale/frontières, bibliothèque, import des
quatre fichiers PC, stockage privé et copie native. Depuis Android 0.4 : marges
Android corrigées, retour des paramètres, détails Finder lisibles, carnet chronométré,
dix palettes PC/Android, icônes et rappel local facultatif. Satellite/vents en
option Internet, désactivés au départ. L'APK debug est
construite et testée sur émulateur API 35, y compris en mode avion et après arrêt
complet du processus. [Installation, build et limites](docs/android/README.md) ;
[parité détaillée](docs/android/PARITY.md). Le workflow **Android offline APK**
fournit l'artefact `RFS-ATC-Android-debug` sans publication de release automatique.
La 0.4.1 ajoute tutoriel et 30 questions bilingues, copie libre facultative,
avertissements cliquables et défilement des avions corrigé.
[État et tests 0.4.1](docs/android/PROGRESS_0.4.1.md) · [English installation guide](docs/INSTALLATION_EN.md).

[État et tests 0.4.2](docs/android/PROGRESS_0.4.2.md).

La 0.4.2 ajoute une vérification facultative des mises à jour et une sauvegarde
commune PC–Android, avec fusion, aperçu avant import et récupération après
interruption. [Mises à jour et transfert des données](docs/UPDATES_AND_TRANSFER.md).
La synchronisation automatique et l’application iOS restent à développer.

`build_exe.bat` crée un environnement Python local, installe PySide6 et
PyInstaller, puis construit le paquet dans `dist\RFSATCMessageMaker`.
La construction utilise `RFSATCMessageMaker.spec`, qui évite un conflit entre
la DLL ICU de Windows et une DLL homonyme détectée dans le PATH.
Ne reconstruisez pas avec une commande PyInstaller qui ignore ce fichier.

```powershell
python -m unittest discover -s tests -v
python main.py
```

Le code est séparé entre `ui.py`, `templates.py`, `validation.py`,
`rfs_schema.py` et `storage.py`. Les messages générés sont en anglais ; les
champs d'interface et la validation suivent le choix global français/anglais.

## Nouveautés Windows

- Mode sombre complet, listes et formulaires compris ; icône et lancement direct par raccourci.
- Sept présentations prêtes à choisir, trois longueurs et huit choix d'emojis.
  Personnalisation guidée sans variables ; l'éditeur expert et le partage JSON restent disponibles.
- Aperçu sans marques techniques ; `Encadrés alignés` ajoute uniquement au presse-papiers
  le bloc monospace que Discord interprète pour conserver le centrage.
- Pilotes mémorisés et proposés dans `Pseudo RFS` ; `Pilotes du vol` permet de rappeler
  un pilote et de cocher les types de messages où l'afficher. Le message reste commun,
  avec une ligne groupée pour les noms, callsigns, avions et pistes.
- Opérations indépendantes, en groupe, parallèles ou décalées, séparées départ/arrivée.
- 249 pays dans le sélecteur de drapeaux, procédures dont go-around, historique compact.
- Introduction humoristique avec un formulaire factice non éditable : aucune donnée
  bancaire ne peut être saisie, stockée ni envoyée. Ce décor n'apparaît qu'une fois,
  même si le message de bienvenue reste activé aux ouvertures suivantes.
- Signalement local : aperçu et export d'un rapport partageable, avec images
  facultatives choisies explicitement. Aucun envoi automatique.

## Flight Finder local

Le bouton **Flight Finder** ouvre la recherche sur la base externe
`finder-data/aviation.sqlite`, à côté de l'exécutable. Une version issue des observations
2026 Q2 est fournie séparément des bibliothèques du programme. Elle ne représente pas
les horaires actuels. Certaines recherches Air India retournent zéro résultat faute
de traces complètes suffisantes : le programme n'invente pas de correspondance.

Les critères sont facultatifs. **UTILISER CE VOL** remplit les valeurs connues du vol
commun sans effacer les champs manuels inconnus ; vérifiez les anciennes pistes,
portes, autres pilotes et données carburant. Détails et reconstruction :
[docs/finder/README.md](docs/finder/README.md).

## Carburant — RFS Fuel Helper

**Estimation pour RFS / simulation uniquement — ne pas utiliser pour préparer un vol réel.**

Le bouton **Carburant** utilise le catalogue fourni de 63 avions et 64 arrivées.
Sélectionnez explicitement la variante, la durée et éventuellement l'arrivée. Les
composants sont séparés, le dégagement le plus proche et la provenance sont affichés.
Aucune consommation manquante n'est remplacée ; aucune marge de 20–30 minutes n'est
ajoutée automatiquement. Les formules correspondent au moteur fourni et l'arrondi
half-even n'est appliqué qu'à l'affichage.

Exemple : A220-300, 5 h, EGLL → EGKK à 30 NM : **12 285 kg**.
**Appliquer avion + carburant au vol** transfère la variante et le total affiché ;
le détail non arrondi est conservé avec le vol. Les alternates sont statiques, sans
contrôle météo, NOTAM, performances ou disponibilité des pistes.

Le vieux `CODEX_TASK.md` racine est historique. Les spécifications Finder valables
sont sous `docs/finder/`, et le transfert carburant sous `docs/fuel/reference/`.

## Partage

Distribuez le dossier portable complet (pas le seul `.exe`), avec `finder-data/`
et ses licences pour le Finder. Ne publiez jamais le dossier personnel `data/`.
Les sources, workflows GitHub et données publiques peuvent être partagés séparément.
Voir `SECURITY.md`. La carte Windows ajoute des frontières locales et deux options
Internet explicites : satellite EOX et vents Open-Meteo. Le prototype PWA reste
historique ; aucune version native iPhone n'est livrée. Android est documenté séparément.

## Note sur les emojis

Le `DISPATCH FORM` conserve les huit pictogrammes de son modèle et l'exception
sans limite ajoutée par l'utilisateur. Les autres messages restent limités à six
emojis. Le design Minimal conserve les emojis sélectionnés ; choisissez
`Sans emojis` pour les supprimer explicitement.

Le menu **Aide > Formulaire en ligne — problème ou suggestion** ouvre le formulaire
Google Forms fourni. Le rapport local avec captures reste disponible séparément.
