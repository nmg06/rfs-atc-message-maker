'use strict';
// Device-local permission: imported flight backups never enable network checks.
(() => {
 let policy=null, loading=false, started=false;
 const originalPaint=paint;
 function message(result) {
  if(!result?.status)return t('Aucune vérification effectuée.','No check performed yet.');
  if(result.status==='available')return t('Nouvelle version disponible : ','New version available: ')+result.version;
  if(result.status==='up_to_date')return t('Votre version est à jour parmi les versions publiques compatibles.','Your version is up to date among compatible public releases.');
  if(result.status==='no_release')return t('Aucune version publique compatible trouvée. Les fichiers de test restent dans GitHub Actions.','No compatible public release found. Test files remain in GitHub Actions.');
  return t('Vérification indisponible. Vérifiez votre connexion et réessayez plus tard. Votre vol reste accessible.','Check unavailable. Check your connection and try again later. Your flight remains accessible.');
 }
 function draw() {
  if(screen!=='settings'||!model)return;
  let card=$('updates-card');
  if(!card){card=document.createElement('section');card.className='card';card.id='updates-card';$('content').append(card);}
  card.innerHTML=`<h2>${t('Mises à jour','Updates')}</h2><p>${t('Version installée','Installed version')} : ${esc(policy?.version||'0.4.2-flightdeck')}</p><label class="check"><input id="updates-enabled" type="checkbox" ${policy?.enabled?'checked':''} ${!policy?'disabled':''}>${t('Vérifier à l’ouverture, au plus une fois par jour','Check on launch, at most once a day')}</label><p class="hint">${t('Facultatif : consulte seulement les versions publiques sur GitHub. Aucun vol ni pilote envoyé. Sans connexion, les fonctions locales restent disponibles. Le téléchargement et l’installation restent votre choix.','Optional: checks public GitHub releases only. No flight or pilot data sent. Local tools remain available offline. You choose whether to download and install.')}</p><p id="updates-status" role="status">${esc(loading?t('Vérification…','Checking…'):message(policy?.last_result))}</p><div class="actions"><button id="updates-check" ${loading||!policy?'disabled':''}>${t('Vérifier maintenant','Check now')}</button>${policy?.last_result?.status==='available'?`<button id="updates-download" class="primary">${t('Télécharger la mise à jour','Download update')}</button>`:''}</div>`;
 }
 async function check(automatic) {
  if(loading)return;loading=true;draw();
  try {
   const result=await rpc('native.updatesCheck',{automatic});
   policy=await rpc('native.updatesGet');
   if(result.status==='available')toast(message(result));
  } catch(e){fail(e);} finally{loading=false;draw();}
 }
 function initialise() {
  if(started||!model)return;started=true;
  rpc('native.updatesGet').then(value=>{policy=value;draw();if(policy.enabled)check(true);}).catch(error=>{started=false;fail(error);});
 }
 paint=function(...args){originalPaint(...args);initialise();draw();};
 document.addEventListener('change',async event=>{
  if(event.target.id!=='updates-enabled')return;
  const chosen=event.target.checked;
  try{policy=await rpc('native.updatesConfigure',{enabled:chosen});draw();if(chosen)check(true);}catch(e){fail(e);draw();}
 });
 document.addEventListener('click',async event=>{
  const button=event.target.closest('button');if(!button||button.disabled)return;
  if(button.id==='updates-check')return check(false);
  if(button.id==='updates-download')try{await rpc('native.updatesOpen',{url:policy.last_result.download_url});}catch(e){fail(e);}
 });
 initialise();draw();
})();
