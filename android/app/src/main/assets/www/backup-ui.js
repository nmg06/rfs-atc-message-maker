'use strict';
(() => {
 const baseAction=action;
 function showImport(value) {
  const detail=value.import_preview, summary=detail.summary||detail, source=detail.source||{};
  const count=(...keys)=>keys.map(k=>summary[k]).find(v=>typeof v==='number')||0;
  const platform=String(source.platform||'');
  const platformName=platform.startsWith('windows')?'Windows':platform.startsWith('android')?'Android':t('Sauvegarde locale','Local backup');
  const dialog=document.createElement('dialog');dialog.id='backup-import-dialog';dialog.className='aircraft-dialog';
  dialog.innerHTML=`<h2>${t('Reprendre une sauvegarde','Restore a backup')}</h2><p>${esc(platformName)}${source.version?' · '+esc(source.version):''}</p><p>${t('Vols sauvegardés','Saved flights')} : ${count('saved_flights','flights')} · ${t('Historique','History')} : ${count('history')} · ${t('Designs','Designs')} : ${count('designs')}</p><p>${t('Fusionner conserve votre vol en cours et ajoute les collections. Les versions différentes sont gardées. Remplacer reprend les données de ce fichier. Dans les deux cas, une sauvegarde préalable est conservée sur cet appareil.','Merge keeps your current flight and adds collections. Different versions are retained. Replace restores this file’s data. Both options keep a pre-import backup on this device.')}</p><div class="actions"><button id="backup-merge" class="primary">${t('Fusionner les données','Merge data')}</button><button id="backup-replace">${t('Remplacer les données','Replace data')}</button><button id="backup-cancel">${t('Annuler','Cancel')}</button></div><p id="backup-import-status" role="status"></p>`;
  let applying=false, applied=false;
  dialog.addEventListener('close',()=>{dialog.remove();if(!applied)rpc('native.importCancel').catch(fail);});
  dialog.querySelector('#backup-cancel').onclick=()=>dialog.close();
  dialog.addEventListener('click',async event=>{
   if(!['backup-merge','backup-replace'].includes(event.target.id)||applying)return;
   const mode=event.target.id==='backup-merge'?'merge':'replace';
   if(mode==='replace'&&!confirm(t('Remplacer le vol et les collections de cet appareil par cette sauvegarde ?','Replace this device’s flight and collections with this backup?')))return;
   applying=true;dialog.dataset.applying='true';dialog.querySelectorAll('button').forEach(b=>b.disabled=true);
   try {
    await rpc('save',stateArgs());
    const result=await rpc('native.importApply',{token:value.token,mode});setResult(result);applied=true;dialog.close();
    revision++;finderRows=[];finderResponse=null;finderVisible=0;fuelResult=null;screen='flight';paint();
    toast(t('Données reprises. Une copie avant import est conservée.','Data restored. A pre-import copy is retained.'));
   }catch(error){dialog.querySelector('#backup-import-status').textContent=t('Import impossible. Les données actuelles restent conservées.','Import failed. Current data is retained.');fail(error);}
   finally{applying=false;delete dialog.dataset.applying;dialog.querySelectorAll('button').forEach(b=>b.disabled=false);}
  });
  dialog.addEventListener('cancel',event=>{if(applying)event.preventDefault();});
  document.body.append(dialog);dialog.showModal();dialog.querySelector('#backup-merge').focus();
 }
 action=async function(el) {
  if(el.dataset.action!=='import')return baseAction(el);
  try{await rpc('save',stateArgs());const value=await rpc('native.import');if(value.import_preview)showImport(value);}catch(error){fail(error);}
 };
 const baseBack=window.goBack;
 window.goBack=function(...args){if($('backup-import-dialog')?.dataset.applying==='true')return true;return baseBack?.(...args);};
})();
