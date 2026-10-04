# RFS Flightdeck 0.4.1 — aide et corrections

Le tutoriel couvre huit rubriques avec quatre étapes chacune. On peut le passer,
le revoir et rechercher 30 questions fréquentes en français ou anglais.
Les explications sont communes au PC, à Android et au prototype web ; les
fonctions propres à Android sont indiquées. Aucun compte ni téléchargement
n’est nécessaire pour consulter cette aide.

## Changements réellement opérationnels

- Palettes et commandes traduites en anglais ; les textes saisis restent conservés.
- Molette et pavé tactile utilisables dans la liste des avions, son en-tête et
  ses limites, sans changer le modèle ni faire défiler le formulaire derrière.
- Vérifier avant copie : activé au départ, désactivable et conservé après reprise.
  La copie libre garde votre texte, le format Discord choisi et les alertes.
- Avertissements cliquables vers le champ ou l’aperçu ; les alertes de groupe
  ramènent à la liste des pilotes. Un aperçu vide ne peut pas être copié.
- Tutoriel contextualisé et FAQ disponibles dans Aide sur PC, Paramètres sur
  Android et Aide dans le prototype. Retour ferme également l’aide sur téléphone.
- Fuel du prototype web : fonctions auparavant absentes, désormais reliées aux
  données et constantes exportées du PC. Formules et calcul Windows inchangés.
- ETE 5 min dans ARRIVAL BOARD = arrivée dans environ cinq minutes ; la durée
  totale utilisée par Fuel reste un champ distinct.

## Vérifications

122 tests Windows, 27 tests du moteur Android et quatre parcours navigateur
passent. 567 combinaisons Fuel web/PC ont les mêmes composants exacts à 10⁻⁶ kg.
Sept rubriques Android et les paramètres ont été contrôlés en anglais ; six
fenêtres Qt supplémentaires ne contiennent aucun libellé français du catalogue.
Le paquet Windows lancé réellement vérifie Finder (577 profils LFPG ≤ 2h),
Fuel A220/5h/EGLL = 12 285 kg, carte (97 points), 30 questions, dix noms anglais
et copie libre avec avertissements.

Le code fonctionnel et les tests natifs sont vérifiés sur
`dde24bb0617f3317eaff5317e7a04562d1e4e57d` :

- [Android installé](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37208845779) :
  quatre tests en mode avion, réinstallation avec quatre nouveaux tests,
  arrêt complet/reprise avec JSON identique et formulaire rendu (EJU149U,
  fuel 12285). FAQ anglaise dans la vraie WebView, presse-papiers réel et copie
  d’un message incomplet sont vérifiés.
- Un test supplémentaire vérifie les vrais fournisseurs EOX/Open-Meteo après
  activation volontaire du réseau ; un dernier vérifie notification anglaise
  et changement d’icône réversible.
- [Windows construit et lancé](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37208845771),
  [tests/dépendances](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37208845769)
  et [CodeQL](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37208845816) réussis.

Les dernières retouches concernent les explications, le guide d’installation
anglais et l’orientation du prototype vers les fonctions effectivement disponibles.

Un premier échec du presse-papiers était causé par une fenêtre ANR du lanceur
`com.android.launcher3` au-dessus de Flightdeck. Le test ferme uniquement ce
lanceur confirmé bloqué, sur matériel d’émulateur. Les assertions réelles de
focus, copie et conservation sont maintenues. Les parcours de reprise indiquent
explicitement que l’introduction et le tutoriel ont été passés.

## Télécharger et construire

[APK Android 0.4.1](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37208845779/artifacts/11305352951) ·
[Windows 0.4.1](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37208845771/artifacts/11305298080).
Connexion GitHub requise ; artefacts de test disponibles jusqu’au 3 novembre 2026.
[Installation en français](../INSTALLATION.md) · [English](../INSTALLATION_EN.md).

Depuis la racine du dépôt :

```powershell
python scripts/prepare_android.py
cd android
.\gradlew.bat --no-daemon assembleDebug
```

APK : `android/app/build/outputs/apk/debug/app-debug.apk` (versionCode 5).
Pour Windows : `python -m PyInstaller --noconfirm RFSATCMessageMaker.spec`,
puis `python scripts/package_windows.py`.

## Fichiers et données

`help_content.py` est la source unique de l’aide ; `help_dialog.py` et
`assets/help-ui.js` sont ses interfaces. `scripts/export_help.py` produit les
ressources locales ; `scripts/export_web_fuel.py` dérive les références Fuel.
`strict_validation` et `tutorial_seen` restent dans les sauvegardes locales.
`ux.py` corrige la molette pour toutes les listes concernées. Les identifiants
canoniques des préférences et les moteurs Windows sont conservés.

## Ce qui reste

- Téléphone physique : confort du défilement, clavier/paysage, partage, photos,
  import multiple et livraison réelle des rappels selon la batterie.
- iOS natif : non porté ; chaîne Mac/Xcode/signature et adaptation du moteur nécessaires.
- Prototype web : Finder SQLite absent, interface et contrôles moins complets.
- Portes et affectations de pistes : données absentes ; seules les pistes
  réelles disponibles sont listées, sans affectation inventée.
- Notifications de recherche/météo en arrière-plan : non ajoutées ; rappel
  volontaire seulement. Après Forcer l’arrêt, reprogrammez-le.
- Distribution publique : signature Android stable et validation physique
  nécessaires ; aucune nouvelle release, fusion ou publication de store effectuée.

Les demandes des derniers messages restent suivies ici et dans la parité :
affichage sûr Android, retour des paramètres, fluidité, Finder/pagination,
durée numérique, choix d’avion et Fuel, sauvegarde automatique, dix palettes,
carte/frontières/satellite/vents facultatifs, carnet, rappel, icônes, blague,
langue, copie libre, tutoriel et FAQ. Prochaine étape : vérifier cette livraison
sur le téléphone utilisé et traiter les écarts concrets avant distribution publique.
