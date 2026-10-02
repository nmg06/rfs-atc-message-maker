Le projet actuel "Message Maker" ne correspond pas à ma demande.

Je ne veux PAS un générateur général de mails administratifs ou professionnels.

Je veux transformer complètement cette application en :

RFS ATC MESSAGE MAKER

C'est une application Windows personnelle pour générer automatiquement mes messages Discord pour Real Flight Simulator (RFS).

Commence par inspecter entièrement le projet actuel avant de modifier quoi que ce soit.

SUPPRIMER / REMPLACER L'INTERFACE ACTUELLE

Les champs génériques actuels comme :
- Profil
- Langue du message
- Format E-mail
- Destinataire
- Fonction / organisme
- Type de demande
- Ton
- Ajouter Bonjour
- Objet de mail

ne servent pas pour cette application et doivent être retirés de l'interface principale.

L'application doit être spécialisée uniquement dans RFS et l'ATC.


==================================================
1. TYPES DE MESSAGES
==================================================

Ajouter un sélecteur principal "Message type" avec :

1. ATC REQUEST
2. AIRBORNE
3. ARRIVAL BOARD
4. FLIGHT COMPLETED
5. ATC ACTIVE
6. ATC OFFLINE
7. FLIGHT PLAN
8. DISPATCH FORM

Les champs visibles doivent changer automatiquement selon le type choisi.


==================================================
2. PROFIL PAR DÉFAUT
==================================================

Pilot name / RFS username :
n1chita

Le programme doit mémoriser cette valeur.

Pour les anciens templates où "NIKA" était utilisé, prévoir un paramètre permettant de choisir entre :
- n1chita
- NIKA

mais utiliser n1chita par défaut.


==================================================
3. ATC REQUEST
==================================================

Champs :

Airline
Aircraft
Callsign
Radio callsign facultatif
Departure ICAO
Departure city
Departure country / flag
Arrival ICAO
Arrival city
Arrival country / flag
Gate
Pushback
Runway
Cruise FL
Route distance facultative
ETE facultatif
Server facultatif

Sortie EXACTE dans ce style :

╭───────────────────────────╮
　　　ATC REQUEST
╰───────────────────────────╯

AIRLINE
✈ n1chita │ AIRCRAFT
CALLSIGN : CALLSIGN

🛫 DEPARTURE ICAO • CITY FLAG
　↘
🛬 ARRIVAL ICAO • CITY FLAG

ICAO　　 : DEPARTURE
STATUS　 : Gate X • Parking
PUSHBACK : in X minutes
RUNWAY　 : XX
CRUISE　 : FLXXX
ROUTE　　: XXXX NM
ETE　　　: XhXXm

Requesting Ground and Tower for departure at XXXX.

「REQUESTING ATC」

@RFS ATC

Les champs facultatifs ne doivent pas laisser de lignes vides ou de placeholders dans le résultat.


==================================================
4. AIRBORNE
==================================================

Champs :

Airline
Aircraft
Callsign
Departure
Arrival
Runway used
Cruise FL
Distance
ETE
Climbing target :
- to TOC
- waypoint personnalisé
ATC controller facultatif
Option "No ATC available"

Template :

╭───────────────────────────╮
　　　　AIRBORNE
╰───────────────────────────╯

...

STATUS　: Airborne
RUNWAY　: XX
CLIMBING : to TOC
CRUISE　 : FLXXX
ROUTE　　: XXXX NM
ETE　　　: XhXXm

Si contrôleur :
Big thanks to @CONTROLLER for the ATC on the ground and the departure 🙏

Sinon :
No ATC available for departure.


==================================================
5. ARRIVAL BOARD
==================================================

IMPORTANT :
Le texte ARRIVAL BOARD doit être réellement centré mathématiquement dans l'encadré.

Utiliser exactement :

╭───────────────────────────╮
       ARRIVAL BOARD       
╰───────────────────────────╯

Champs :

Airline
Aircraft
Callsign
Departure
Arrival
Status
ETE
Distance remaining
Runway
Approach facultatif
ATC positions

Cases permettant de masquer :
- ETE
- STAR
- Fuel
- altitude

Par défaut, ne pas afficher Fuel, STAR ou altitude.

Template habituel :

STATUS　: Descent
ETE　　 : ~10 min
DIST　　: 20 NM
APPROACH: RWY 16R
ATC　　 : GROUND & TOWER

「REQUESTING ATC REPORT」

@RFS ATC

IMPORTANT :
Toujours laisser UNE ligne vide entre
「REQUESTING ATC REPORT」
et
@RFS ATC

Ajouter un mode :
GO-AROUND / SECOND ATTEMPT

qui peut produire par exemple :

STATUS : Go-around procedure • first landing attempt unsuccessful
DIST : 10 NM
APPROACH : RWY 16R • second attempt


==================================================
6. FLIGHT COMPLETED
==================================================

Je préfère maintenant une version COURTE.

Template :

╭─────── ATC • ARRIVED ───────╮

📡 RJAA • TOKYO NARITA 🇯🇵

✈️ AIR INDIA • A330-900neo
CALLSIGN : AIC186
ROUTE    : CYVR → RJAA

RUNWAY   : 16R
STATUS   : AT GATE 13
FLIGHT   : 9h59m

Thanks for ATC 🙏 @Eden

╰────────────────────────────╯

Champs :
Airport
City
Flag
Airline
Aircraft
Callsign
Route departure/arrival
Runway
Gate
Flight time
Controller

Option :
No ATC available

Ne PAS afficher par défaut :
Passengers
Cargo
Fuel
Touchdown

Prévoir éventuellement une option "Detailed version" pour les ajouter.


==================================================
7. ATC ACTIVE
==================================================

Format compact.

Champs :
Airport ICAO
City
Flag
Positions
Server
Duration
Departures counter
Inbound counter
Free sentence

Exemple :

🟢 ATC ACTIVE
🇬🇧 EGLL • LONDON HEATHROW
🎧 GROUND + TOWER
⏱️ DURATION: 1h
🛫 DEPARTURES: 0
🛬 INBOUNDS: 0

Flying from or into Heathrow? Send your route or callsign.

IMPORTANT :
Ne jamais ajouter automatiquement @RFS ATC aux messages ATC ACTIVE.

Maximum 6 emojis.


==================================================
8. ATC OFFLINE
==================================================

Format compact :

🔴 ATC CLOSED
🇩🇪 EDDF • FRANKFURT
🎧 GROUND + TOWER
⏱️ DURATION: 1h20
🛫 DEPARTURES: 10+
🛬 INBOUNDS: 0

Thanks to everyone who joined the session!

Compteur departures saisi manuellement.
Ne jamais l'inventer.


==================================================
9. FLIGHT PLAN
==================================================

Format EXACT :

✈️ Flight Plan ✈️

Route : CYVR - RJAA
Distance : 4056.2 nm
Departure Runway : 26L
Arrival Runway : 16R
Aircraft : Airbus A330-900neo
Airline : Air India
Estimated Flight Time : 10h 20m
Pax : 290
Cargo : 10000 kg
Fuel : 68200 kg

Champs correspondants.


==================================================
10. DISPATCH FORM
==================================================

Format :

👤 Pilot Name- n1chita
🌐 RFS Server- ATC Report
📡 Call Sign / Flight Number- AIC186
✈️ Aircraft- A330-900neo
🎨 Livery- Air India
🛫 Departure Airport- CYVR
🛬 Arrival Airport- RJAA
⏱️ Estimated Flight Time- 10:20

Prévoir aussi des champs facultatifs :
Passengers
Cargo
Meals


==================================================
11. INTERFACE
==================================================

Je veux une vraie petite application Windows moderne.

À gauche :
formulaire dynamique.

À droite :
aperçu Discord en temps réel.

Boutons :
- Generate
- Copy message
- Clear
- Save preset
- Load preset
- History

L'aperçu doit se mettre à jour pendant que je remplis le formulaire.

Prévoir un mode sombre par défaut.

Les valeurs fréquentes doivent être mémorisées :
- Pilot name
- Server
- Airlines
- Aircraft
- airports récemment utilisés
- controllers récemment utilisés


==================================================
12. RÈGLES IMPORTANTES
==================================================

Ne jamais inventer une donnée manquante.

Si Runway, Gate, FL, distance, fuel, etc. manque :
- soit masquer la ligne si elle est facultative ;
- soit afficher clairement dans le formulaire qu'elle doit être remplie.

Le programme ne doit jamais générer automatiquement une fausse valeur.

Maximum 6 emojis dans les messages Discord.

Messages finaux en anglais.

Interface du programme en français.

Respecter exactement les espacements et les encadrés.

Ne pas modifier automatiquement les ICAO.

Sauvegarde locale uniquement.

Pas besoin d'API ou d'Internet pour générer ces templates.

Ne pas hardcoder des numéros de vol fictifs.


==================================================
13. AMÉLIORATIONS UTILES
==================================================

Ajouter :

- compteur automatique du nombre d'emojis ;
- avertissement rouge si > 6 ;
- bouton "Copy";
- bouton pour dupliquer un message précédent ;
- historique local ;
- favoris / presets par airline ;
- conversion automatique "10 h 20" → "10h20m" selon le template ;
- validation ICAO = exactement 4 caractères ;
- validation FL ;
- validation runway ;
- validation distance numérique ;
- drapeaux sélectionnables ;
- possibilité de masquer certaines lignes.

Ajouter un petit panneau "Current flight" permettant de réutiliser les données entre les messages.

Exemple :
je crée un ATC REQUEST CYVR → RJAA,
puis quand je passe sur AIRBORNE ou ARRIVAL BOARD,
Airline / Aircraft / Callsign / Route doivent déjà être remplis.

C'est extrêmement important.


==================================================
14. DONNÉES D'UN VOL
==================================================

Créer une notion de "Current Flight".

Elle contient :
Airline
Aircraft
Livery
Callsign
Flight number
Departure
Arrival
Departure runway
Arrival runway
Gate departure
Gate arrival
Cruise FL
Distance
Estimated flight time
Passengers
Cargo
Fuel

Ces données restent disponibles pendant tout le vol.

ATC REQUEST, AIRBORNE, ARRIVAL BOARD, FLIGHT COMPLETED, FLIGHT PLAN et DISPATCH FORM utilisent les mêmes données.

Je ne veux PAS devoir retaper la route et l'avion à chaque message.


==================================================
15. CODE ET FIABILITÉ
==================================================

Garder Python si le projet est déjà en Python.

Structurer correctement le code :
UI séparée
templates séparés
validation séparée
storage séparé

Ne pas mettre toute l'application dans un seul main.py énorme.

Créer des sauvegardes avant refactorisation.

Tester tous les templates.

Vérifier que les caractères Unicode :
╭ ╮ ╰ ╯
→
✈
📡
fonctionnent correctement sous Windows et dans Discord.

Construire un .exe avec PyInstaller à la fin.

Le .exe doit fonctionner sans Python installé.


==================================================
16. OBJECTIF FINAL
==================================================

Je veux pouvoir faire :

ouvrir l'application
→ sélectionner ATC REQUEST
→ choisir le vol actuel
→ remplir gate/runway/pushback
→ Copy

puis plus tard :

AIRBORNE
→ les infos du même vol sont déjà là
→ remplir runway / climb
→ Copy

puis :

ARRIVAL BOARD
→ remplir distance / ETE / runway
→ Copy

puis :

FLIGHT COMPLETED
→ remplir gate / flight time / controller
→ Copy

Le tout doit prendre quelques secondes.

Ce projet est un outil RFS / Discord.
Ce n'est pas un générateur de mails administratifs.

Commence par transformer l'application actuelle dans ce sens.
Teste le résultat toi-même avant de me rendre le projet.