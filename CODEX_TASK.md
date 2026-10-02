# Mission Codex — Message Maker

Tu travailles sur une application Windows personnelle appelée **Message Maker**.

## Objectif
Transformer un formulaire simple en e-mail ou message naturel, prêt à envoyer, sans devoir ouvrir ChatGPT à chaque fois.

## Entrées
- destinataire
- organisme / fonction
- format : e-mail ou message
- type de demande
- ton
- longueur
- contexte
- ce que l'utilisateur veut demander / dire
- détails importants
- option « Bonjour déjà dit dans le fil »

## Sortie
- objet d'e-mail si nécessaire
- message prêt à copier
- texte modifiable avant copie

## Style attendu
- français naturel
- professionnel sans être froid
- pas trop formel
- éviter les longues phrases administratives
- ne pas répéter « Bonjour » dans le même fil si l'option est désactivée
- éviter « Je me permets… » partout
- privilégier des formulations comme « J'aurais une petite question concernant… » ou « Je voulais savoir comment cela fonctionne… »
- ne pas prétendre connaître une procédure que l'utilisateur demande justement à clarifier
- ne jamais inventer une information absente du formulaire

## Priorités UX
1. Génération en moins de 30 secondes.
2. Interface claire, sans jargon.
3. Ne jamais perdre le texte saisi si une erreur se produit.
4. Prévisualisation toujours éditable.
5. Bouton Copier très visible.
6. Historique local.
7. Fonctionnement hors ligne par défaut.

## V2 à implémenter
- moteur de génération par blocs plutôt que templates rigides
- suppression automatique des répétitions
- 2 variantes : « naturelle » et « plus courte »
- boutons : Raccourcir / Plus naturel / Plus professionnel
- contacts favoris
- profils : École/CFA, RH/entreprise, administration, SAV, personnel
- signature personnalisable
- langues FR / EN / RO
- presets personnalisés
- import/export des paramètres JSON
- autosave du brouillon
- raccourci Ctrl+Entrée = Générer
- thème clair/sombre si maintenable
- validation des champs non bloquante
- logs locaux dans `data/app.log`

## Mode IA optionnel
L'IA ne doit jamais être obligatoire.

Prévoir une architecture permettant plus tard un mode IA optionnel :
- désactivé par défaut
- aucune clé API en dur
- stockage local sûr si activé
- fallback automatique vers le moteur hors ligne si l'appel échoue
- envoyer uniquement les champs du formulaire courant, jamais tout l'historique
- expliquer clairement à l'utilisateur quand des données seront envoyées à un service externe

## Robustesse
- gérer JSON absent/corrompu
- créer automatiquement `data/`
- ne jamais crasher si historique vide
- tester accents/apostrophes
- tester chemins Windows avec espaces
- Python 3.11+
- ne pas sur-ingénierer

## Packaging Windows
Ajouter :
- `requirements.txt` seulement si nécessaire
- `build_exe.bat`
- construction avec PyInstaller
- sortie `dist/MessageMaker.exe`
- ne rien télécharger automatiquement pour une icône

## Travail demandé
1. Lire et lancer l'application existante.
2. Reproduire toutes les fonctions actuelles.
3. Corriger les bugs.
4. Refactoriser proprement.
5. Implémenter les améliorations V2 utiles.
6. Tester les principaux parcours.
7. Construire l'exécutable Windows si possible.
8. À la fin, résumer les fichiers modifiés, les tests effectués et les éventuels problèmes restants.

Avance de manière autonome jusqu'à obtenir une application locale stable et utilisable. Ne demande pas confirmation pour chaque petite modification.
