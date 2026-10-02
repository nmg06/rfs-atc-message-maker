# Révision des modifications utilisateur — 2 octobre 2026

Cette version part des sources réelles modifiées après la v4, et conserve le
thème Avionique Sobre sombre/clair, l'éditeur de designs à onglets, la gestion
des captures et l'exception sans limite d'emojis du Dispatch Form ajoutés depuis.
La base Finder actuelle est conservée sans reconstruction ni changement de données.

- Nettoyage des propriétés CSS non prises en charge par Qt, contraste du thème
  clair, focus et états désactivés, champs éditables dans les listes déroulantes.
- Marges régulières, séparation des cartes, aperçu monospace ciblé, bouton Copier
  principal sur toute la largeur et bouton Générer secondaire.
- Tableaux Finder aérés ; navigation au clavier conservée ; événements de molette
  transmis à Qt, y compris les deltas en pixels des pavés tactiles.
- Le design Minimal conserve les emojis et drapeaux sélectionnés. Sans emojis
  reste le réglage explicite de suppression. Les autres messages restent limités
  à six pictogrammes ; le Dispatch Form conserve l'exception utilisateur.
- Conversion guidée vers avancée conservant {{message}}, donc les données du
  prochain vol. L'import d'un texte figé reste accessible sous un libellé explicite.
- Aide > Formulaire en ligne — problème ou suggestion ouvre exactement le lien
  Google Forms fourni, sur clic uniquement. Aucun rapport n'est envoyé automatiquement.
- Rapport local défilable avec fermeture accessible, aperçu du JSON, gestion des
  images indisponibles et consentement à confirmer après ajout de pièces jointes.
- Traductions FR/EN complétées pour les nouveaux écrans de rapport et de designs.
- Les erreurs de sauvegarde sont propagées aux traitements existants : elles ne
  sont plus silencieusement considérées comme une réussite.

Le démarrage et les données sont vérifiés dans des dossiers de test isolés.
Les tests simulent une molette et des deltas de pavé tactile ; ils ne constituent
pas un essai matériel. L'ouverture du navigateur est vérifiée par interception
du lien, sans soumettre le formulaire Google.
