'use strict';
// This remains a limited prototype; the shared guide identifies app-only tools.
let webLanguage = localStorage.getItem('flightdeck-language') === 'en' ? 'en' : 'fr';
const webT = (fr,en)=>webLanguage==='en'?en:fr;
const webLabels = {
 'ICAO arrivée':'Arrival ICAO','Choisir un avion / variante…':'Choose aircraft / variant…','Nouveau':'New flight','📝 Vol & Saisie':'📝 Flight & input','⛽ Carburant':'⛽ Fuel','👁 Aperçu':'👁 Preview',
 'Type de message':'Message type','ATC REQUEST (Départ / Porte)':'ATC REQUEST (Departure / Gate)','AIRBORNE (En vol)':'AIRBORNE (In flight)','ARRIVAL BOARD (Arrivée)':'ARRIVAL BOARD (Arrival)','FLIGHT COMPLETED (Vol terminé)':'FLIGHT COMPLETED (Arrived)',
 'Pseudo RFS':'RFS name','Classique':'Classic','Moderne':'Modern','Pilote':'Pilot','Longueur':'Length','Court':'Short','Moyen':'Medium','Détaillé':'Detailed','Alternatif':'Alternative','Sans emojis':'No emojis',
 'Vol actuel':'Current flight','Compagnie':'Airline','Avion / Modèle':'Aircraft / Model','Niveau de vol':'Flight level','ICAO Départ':'Departure ICAO','Ville départ':'Departure city','ICAO Arrivée':'Arrival ICAO','Ville arrivée':'Arrival city','Durée prévue':'Total duration',
 'Informations du message':'Message details','Calculateur de Carburant RFS':'RFS fuel calculator','Estimation basée sur les données réelles RFS • Simulation uniquement, jamais pour un vol réel.':'Estimate based on RFS data • Simulation only, never for real flights.',
 'Avion / Variante RFS':'RFS aircraft / Variant','-- Choisir un avion / variante --':'-- Choose aircraft / variant --','Durée estimée':'Estimated duration','Dégagement (NM)':'Alternate (NM)','Calculer le carburant':'Calculate fuel','Détail du carburant estimé':'Estimated fuel breakdown','Composant':'Component','Masse (kg)':'Mass (kg)',
 'Taxi départ (6 min × 1,4)':'Taxi out (6 min × 1.4)','Trajet (Trip Fuel)':'Trip fuel','Contingence (5 % du trajet)':'Contingency (5% of trip)','Alternate (dégagement)':'Alternate','Réserve finale (30 min)':'Final reserve (30 min)','Taxi arrivée (4 min × 1,4)':'Taxi in (4 min × 1.4)','TOTAL BLOC':'TOTAL BLOCK',
 '✓ Appliquer cet avion et carburant au vol':'✓ Apply aircraft and fuel to flight','Aperçu Discord':'Discord preview','En direct':'Live','Le message se construit pendant la saisie…':'Your message is built as you type…','📋 Copier le message':'📋 Copy message','Copié dans le presse-papiers ! ✓':'Copied to clipboard! ✓','Copié ! ✓':'Copied! ✓',
 'Porte / Gate':'Gate','Piste de départ':'Departure runway','Serveur':'Server','Piste utilisée':'Runway used','Contrôleur ATC':'ATC controller',"Piste d'arrivée":'Arrival runway','Statut':'Status','Approche':'Approach','Piste atterrissage':'Landing runway',
 'Ex: FL350 ou 350':'E.g. FL350 or 350','Ex: Londres':'E.g. London','Ex: 5h30 ou 5.5':'E.g. 5h30 or 5.5'
};
const originals = new WeakMap();
function translateWebUI() {
 document.documentElement.lang=webLanguage;
 const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
 for(let node=walker.nextNode();node;node=walker.nextNode()){
  if(node.parentElement.closest('script,style,.fd-help,#preview_text'))continue;
  const raw=node.textContent,trim=raw.trim();
  if(webLabels[trim])originals.set(node,{fr:trim,en:webLabels[trim]});else {const original=Object.keys(webLabels).find(key=>webLabels[key]===trim);if(original)originals.set(node,{fr:original,en:trim});}
  const row=originals.get(node);if(row){const result=raw.replace(trim,row[webLanguage]);if(result!==raw)node.textContent=result;}
 }
 for(const el of document.querySelectorAll('[placeholder]')){
  if(!el.dataset.placeholderFr)el.dataset.placeholderFr=el.placeholder;
  const original=el.dataset.placeholderFr;
  el.placeholder=webLanguage==='en'?(webLabels[original]||original.replace(/^Ex:/,'E.g.')):original;
 }
 const count=document.getElementById('char_count');if(count)count.textContent=count.textContent.replace(/car\.|chars\./,webT('car.','chars.'));
 document.getElementById('web-help').textContent=webT('Aide','Help');
 document.getElementById('web-context-help').textContent=webT('Comprendre cet écran','Understand this screen');
 document.getElementById('web-prototype-note').textContent=webT('Prototype web limité. Pour Flight Finder hors ligne et Fuel Helper complet, utilisez les applications Windows ou Android.','Limited web prototype. For offline Flight Finder and the full Fuel Helper, use the Windows or Android apps.');
 document.getElementById('web-copy-label').textContent=webT('Vérifier avant copie','Check before copying');
 document.getElementById('web-copy-hint').textContent=webT('Désactivez pour copier un texte incomplet. Appuyez sur un avertissement pour remplir le champ.','Disable to copy incomplete text. Tap a warning to fill its field.');
}
FlightdeckHelp.init({prototype:true,language:()=>webLanguage,hasSeen:()=>localStorage.getItem('flightdeck-tutorial-seen')==='yes',seen:()=>localStorage.setItem('flightdeck-tutorial-seen','yes'),navigate:(topic,target)=>{
 const section=topic==='fuel'?'fuel':topic==='preview'?'preview':'form';switchTab(section);
 const ids={departure_icao:'dep_icao',estimated_flight_time:'ete',arrival_ete:'ete'};
 const field=document.getElementById(ids[target]||target);if(field){field.scrollIntoView({block:'center'});field.focus();}
}});
const webBaseRender=render;
render=()=>{webBaseRender();if(document.getElementById('web-help')){translateWebUI();webValidation();}};
const webBaseDynamic=updateDynamicFields;
updateDynamicFields=()=>{webBaseDynamic();if(document.getElementById('web-help'))translateWebUI();};
const webBaseToast=showToast;
showToast=message=>webBaseToast(webLanguage==='en'?(webLabels[message]||message):message);
const webBaseReset=resetForm;
resetForm=()=>{if(confirm(webT('Voulez-vous effacer le vol actuel ?','Clear the current flight?'))){for(const key of['airline','aircraft','callsign','cruise_fl','dep_icao','dep_city','arr_icao','arr_city','distance','ete','gate','dep_runway','arr_runway']){const el=document.getElementById(key);if(el){el.value='';state[key]='';}}render();}};
function webValidation(){
 const issues=[];
 for(const key of ['airline','aircraft','callsign','dep_icao','arr_icao']){
  const el=document.getElementById(key);if(!el.value.trim())issues.push({key,text:webT('À compléter : ','Required: ')+(el.closest('.field').querySelector('label').textContent.replace('*','').trim())});
  else if(['dep_icao','arr_icao'].includes(key)&&!/^[A-Za-z]{4}$/.test(el.value.trim()))issues.push({key,text:webT('ICAO : quatre lettres','ICAO: four letters')});
 }
 const message=document.getElementById('preview_text').textContent;
 if(message.length>2000)issues.push({key:'preview_text',text:webT('Plus de 2 000 caractères','Over 2,000 characters')});
 const parent=document.getElementById('web-issues');parent.replaceChildren();
 for(const issue of issues){const button=document.createElement('button');button.className='btn btn-secondary';button.textContent=issue.text;button.onclick=()=>{switchTab(issue.key==='preview_text'?'preview':'form');const el=document.getElementById(issue.key);el.scrollIntoView({block:'center'});el.focus();};parent.append(button);}
 return issues;
}
const webBaseCopy=copyMessage;
copyMessage=()=>{const issues=webValidation();if(document.getElementById('web-strict-copy').checked&&issues.length){switchTab('preview');document.getElementById('web-issues').scrollIntoView({block:'center'});return;}if(document.getElementById('preview_text').textContent.trim())webBaseCopy();};
document.addEventListener('DOMContentLoaded',()=>{
 const header=document.querySelector('header');header.insertAdjacentHTML('beforeend','<select id="web-language" aria-label="Language"><option value="fr">Français</option><option value="en">English</option></select><button class="btn btn-secondary" id="web-help"></button>');
 document.querySelector('.container').insertAdjacentHTML('afterbegin','<p id="web-prototype-note"></p><button class="btn btn-secondary" id="web-context-help"></button>');
 document.querySelector('#panel-preview .card').insertAdjacentHTML('beforeend','<label style="display:flex;gap:10px;align-items:center;margin:14px 0"><input style="width:auto" id="web-strict-copy" type="checkbox"><span id="web-copy-label"></span></label><p id="web-copy-hint"></p><div id="web-issues" style="display:grid;gap:8px;margin:12px 0"></div>');
 const control=document.getElementById('web-language');control.value=webLanguage;control.onchange=()=>{webLanguage=control.value;localStorage.setItem('flightdeck-language',webLanguage);translateWebUI();webValidation();};
 document.getElementById('web-strict-copy').checked=localStorage.getItem('flightdeck-strict-copy')!=='false';
 document.getElementById('web-strict-copy').onchange=event=>localStorage.setItem('flightdeck-strict-copy',event.target.checked);
 document.getElementById('web-help').onclick=()=>FlightdeckHelp.open('flight','faq');
 document.getElementById('web-context-help').onclick=()=>FlightdeckHelp.open(document.getElementById('panel-fuel').classList.contains('active')?'fuel':document.getElementById('panel-preview').classList.contains('active')?'preview':'flight');
 translateWebUI();webValidation();FlightdeckHelp.maybeOffer();
});
