# Signature des APK distribuées

Une mise à jour Android conserve les données uniquement si l’identifiant de
l’application et la signature restent compatibles. Les APK debug de deux
ordinateurs ou de deux runners GitHub peuvent avoir des clés différentes.

## APK de test

`assembleDebug` reste disponible sans configuration particulière. Les builds
locaux utilisent la clé debug existante. Avant de remplacer une APK provenant
d’une autre source, exportez vos données dans **Paramètres > Sauvegarde**.
Si Android refuse la mise à jour pour une signature différente, gardez l’ancienne
application jusqu’à avoir vérifié votre export. Une désinstallation efface son
stockage privé ; vous pourrez ensuite importer le fichier dans la nouvelle app.

## Préparer une clé stable

Créer la clé une seule fois sur le poste du mainteneur, hors du dépôt et hors des
dossiers partagés. Ne jamais publier la clé ou ses mots de passe. Garder une
copie chiffrée séparée : perdre la clé empêcherait les mises à jour des APK signées.

Exemple avec les outils du JDK, en choisissant un chemin privé existant :

```powershell
keytool -genkeypair -keystore C:\chemin-prive\flightdeck-release.jks -alias flightdeck -keyalg RSA -keysize 3072 -validity 10000
keytool -list -v -keystore C:\chemin-prive\flightdeck-release.jks -alias flightdeck
```

Les mots de passe sont demandés par `keytool`. Relever l’empreinte SHA-256 du
certificat public et la conserver avec les informations de publication.

Configurer dans l’environnement du processus de build :

| Variable | Valeur |
|---|---|
| `RFS_ANDROID_KEYSTORE` | chemin absolu de la clé privée |
| `RFS_ANDROID_STORE_PASSWORD` | mot de passe du fichier |
| `RFS_ANDROID_KEY_ALIAS` | alias, par exemple `flightdeck` |
| `RFS_ANDROID_KEY_PASSWORD` | mot de passe de la clé |

Puis exécuter la commande habituelle avec `assembleRelease` :

```powershell
.\android\gradlew.bat -p android assembleRelease
python scripts/verify_android_apk.py android/app/build/outputs/apk/release/app-release.apk --aapt C:\Android\Sdk\build-tools\35.0.0\aapt.exe --require-release --apksigner C:\Android\Sdk\build-tools\35.0.0\apksigner.bat --expected-cert-sha256 EMPREINTE_SHA256_SANS_DEUX_POINTS
```

APK : `android/app/build/outputs/apk/release/app-release.apk`. Sans configuration
complète, le build release échoue explicitement. La vérification refuse une APK
debug, une signature invalide ou une empreinte inattendue.

## Construire sur GitHub

Le workflow manuel **Flightdeck signed release candidate** construit Windows et
Android et produit deux artefacts. Il ne publie aucune release et ne crée aucun tag.
Il devient disponible dans Actions après intégration du workflow à la branche
par défaut.

Dans l’environnement GitHub protégé `flightdeck-release`, définir les secrets
`RFS_ANDROID_KEYSTORE_BASE64`, `RFS_ANDROID_STORE_PASSWORD`,
`RFS_ANDROID_KEY_ALIAS`, `RFS_ANDROID_KEY_PASSWORD`, et la variable publique
`RFS_ANDROID_CERT_SHA256` (64 caractères hexadécimaux, sans deux-points).
Le fichier privé est restauré temporairement puis supprimé ; il n’entre dans
aucun artefact. Base64 est seulement un encodage, pas un chiffrement.

Pour la future publication Flightdeck, utiliser un tag **`flightdeck-X.Y.Z`**.
Les tags commençant par `v` déclenchent encore l’ancien workflow Windows
`release.yml`, conservé pour les versions historiques. La recherche de mises à
jour reconnaît les nouveaux tags Flightdeck et ignore les drafts/prereleases.

La clé de distribution définitive n’a pas encore été créée/configurée. La
candidate 0.4.3 fournie pour les essais reste une APK debug. Aucun test de la
chaîne de signature publique n’est revendiqué avant cette configuration.
