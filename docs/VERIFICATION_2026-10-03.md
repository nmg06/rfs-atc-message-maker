# Livraison vérifiée — 3 octobre 2026

**Ce document conserve les preuves de la livraison 0.2.** La version 0.3 et ses
nouveaux téléchargements sont documentés dans [PROGRESS_0.3.md](android/PROGRESS_0.3.md)
et [INSTALLATION.md](INSTALLATION.md) : carte Android locale, bibliothèque/import
PC, extensions de messages et correction des traducteurs Qt (114 tests Windows,
22 tests Android, trois tests natifs et reprise du processus sur API 35).

Nom affiché : **RFS Flightdeck**. Version Android `0.2.0-flightdeck`.
Les paquets ci-dessous correspondent au commit
`fb9640f5ca83695924cb9d602c56c7e66bd5afc7` de `feat/flightdeck-map-performance`.
Les changements sont dans les PR [Android #1](https://github.com/nmg06/rfs-atc-message-maker/pull/1)
et [Flightdeck #2](https://github.com/nmg06/rfs-atc-message-maker/pull/2), cette dernière
reposant sur la première. Ils ne sont pas encore fusionnés dans `main`.
Aucune nouvelle release publique, publication de store ou migration du profil quotidien.

## Télécharger et installer

| Système | Fichier vérifié | Installation |
| --- | --- | --- |
| Windows x64 | [Artefact ZIP](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37135488231/artifacts/11278727220) | Extraire l'artefact puis le ZIP portable dans un nouveau dossier, lancer `RFSFlightdeck/RFSATCMessageMaker.exe` avec ses dossiers voisins |
| Android API 24+, ARM64 / x86_64 | [Artefact APK](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37135488244/artifacts/11278442657) | Extraire l'artefact, transférer `app-debug.apk`, ouvrir puis autoriser cette source pour l'installation |
| iPhone / iPad | Aucun paquet iOS | Portage et chaîne de build Apple restent à réaliser |

Connexion GitHub nécessaire pour les artefacts, expiration **2 novembre 2026**.
L'application n'a pas besoin d'un compte. Guide complet : [INSTALLATION.md](INSTALLATION.md).

## Preuves

- [Contrôles Windows](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37135488245) :
  113 tests réussis, audit des dépendances, Bandit sans problème moyen/élevé et build EXE.
- [Paquet Windows](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37135488231) :
  vrai EXE autonome démarré dans un profil temporaire. Finder local LFPG/max120 :
  **577 correspondances** ; Fuel A220-300/5h/EGLL : **12 285 kg** ; carte locale
  LFPG→KJFK : **97 points**, ressources terrestres chargées.
- [Android](https://github.com/nmg06/rfs-atc-message-maker/actions/runs/37135488244) :
  16 tests Python, 1 344 combinaisons de génération comparées au moteur Windows,
  syntaxe JavaScript, APK réellement construite et ressources/permissions vérifiées.
  Installation sur émulateur API 35, **deux tests natifs**, vraie copie Android,
  Finder et Fuel locaux, puis arrêt complet du processus et relance.
  Résultat du contrôle de reprise :

```json
{"airplane_mode": true, "instrumentation_tests": 2, "process_restart_persistent": true, "restored_webview_rendered": true, "callsign": "EJU149U", "fuel": "12285"}
```

- Parcours mobile Playwright 390×844 : formulaires, validation, aperçu édité/copié,
  pages Finder 100→200→100→200, transfert, catalogue vol→Fuel, sauvegarde/rechargement,
  changement FR→EN ; zéro erreur JavaScript.
- [Mesures Finder](finder-performance.json) : mêmes réponses/classement/avertissements
  que la version précédente ; Air France **3,82 s → 0,155 s**, page suivante **0,016 s**.
  Ce sont des mesures sur ce poste avec les critères enregistrés, pas une garantie universelle.
- Fournisseurs cartographiques testés réellement : six tuiles satellite rendues et
  17 points de vent à 250 hPa, date UTC/altitude et composante arrière/de face affichées.

## Construire depuis la racine

Prérequis Android détaillés dans [Android README](android/README.md) :
Python 3.11, JDK 17/21, SDK 35 et variables `ANDROID_HOME`, `JAVA_HOME`, `RFS_BUILD_PYTHON`.

```powershell
.\android\gradlew.bat -p android assembleDebug
```

Sortie : `android/app/build/outputs/apk/debug/app-debug.apk`.

Windows, Python avec les dépendances de `requirements.txt` :

```powershell
python -m PyInstaller --noconfirm --clean RFSATCMessageMaker.spec
python scripts/package_windows.py
```

Sortie : `dist/RFSFlightdeck-Windows-x64-test.zip`.
Les workflows reconstruisent les paquets sans publier de release.

## Limites

- Aucun téléphone physique connecté : les preuves Android portent sur l'émulateur API 35.
- APK debug : une clé de distribution stable reste à configurer ; exporter les données
  avant une désinstallation ou un changement de signature.
- Carte/frontières/zoom et sélection pays disponibles sur Windows. Satellite et
  vents sont facultatifs avec Internet, désactivés par défaut ; prévisions du monde
  réel pouvant différer de RFS, sans changement des formules Fuel ou des durées historiques.
- Carte/satellite/vents absents de l'APK. Certaines fonctions de bibliothèque,
  traductions, options de présentation et parcours de partage/photos restent partiels :
  [PARITY.md](android/PARITY.md) fournit l'état précis.
- Des sorties natives intermittentes sans traceback ont été observées dans deux
  exécutions Windows Qt offscreen, tandis que les suites complètes locales et d'autres
  exécutions du même code passent. Les diagnostics natifs sont activés dans les tests
  pour identifier la cause ; aucun test ni assertion n'est retiré.
