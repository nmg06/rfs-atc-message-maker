/* Local compatibility bootstrap. ES5 so unsupported engines can fail clearly. */
(function (global) {
 'use strict';
 if (!String.prototype.replaceAll) Object.defineProperty(String.prototype, 'replaceAll', {configurable:true,writable:true,value:function(search,replacement) {
  if (this == null) throw new TypeError('String required');
  if (search instanceof RegExp) {if (!search.global) throw new TypeError('Global regular expression required');return String(this).replace(search,replacement);}
  var escaped=String(search).replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
  return String(this).replace(new RegExp(escaped,'g'),replacement);
 }});
 if (global.Intl && !Intl.DisplayNames) {
  var names={};try {if(global.Android && Android.countryNames)names=JSON.parse(Android.countryNames());}catch(ignored){}
  Intl.DisplayNames=function(){this.of=function(code){var key=String(code).toUpperCase();return names[key]||key;};};
 }
 var nativeBridge=global.Android && typeof Android.compatibilityReady==='function';
 if (document.documentElement.getAttribute('data-flightdeck-probe')==='true') {
  var supported=Boolean(global.Intl && Intl.DisplayNames && global.ResizeObserver && global.HTMLDialogElement && HTMLDialogElement.prototype.showModal && Array.prototype.flatMap);
  if(nativeBridge)Android.compatibilityReady(supported);
  return;
 }
 if(!nativeBridge)return;
 var running=false, queued=false;
 function resumed() {
  if(typeof model==='undefined'||!model){setTimeout(resumed,100);return;}
  if(running){queued=true;return;}running=true;
  rpc('native.resume').then(function(value){
   images=value.images||[];
   var waiting=document.getElementById('native-recovery-dialog');
   if(value.pending) {
    if(!waiting){waiting=document.createElement('dialog');waiting.id='native-recovery-dialog';waiting.className='aircraft-dialog';waiting.textContent=t('Reprise de la sélection Android en cours…','Resuming the Android selection…');waiting.addEventListener('cancel',function(event){event.preventDefault();});document.body.appendChild(waiting);waiting.showModal();}
   }else if(waiting){waiting.close();waiting.remove();}
   var results=value.completed||[];if(!results.length)return;
   return rpc('bootstrap').then(function(result){
    setResult(result);paint();
    results.forEach(function(item){
     var response=item.response||{};if(!response.ok){fail(Error(response.error||t('Opération interrompue.','Operation interrupted.')));return;}
     var detail=response.result||{};
     if(detail.import_preview){document.dispatchEvent(new CustomEvent('flightdeck-import-resume',{detail:detail}));return;}
     if(detail.cancelled){toast(t('Sélection annulée. Vos données sont conservées.','Selection cancelled. Your data is retained.'));return;}
     if(item.mode==='images'){screen='settings';paint();toast(t('Images sélectionnées : rouvrez le signalement pour les retrouver.','Images selected: reopen your report to find them.'));}
     else if(item.mode==='reminder')toast(t('Rappel programmé.','Reminder scheduled.'));
     else if(detail.saved)toast(t('Fichier enregistré.','File saved.'));
     else if(item.mode==='importApply'||item.mode==='pcImport')toast(t('Données reprises.','Data restored.'));
    });
   });
  }).catch(function(error){fail(error);}).then(function(){running=false;if(queued){queued=false;resumed();}});
 }
 global.FlightdeckNativeResume=resumed;
 document.addEventListener('DOMContentLoaded',function(){
  function ready(){if(typeof model==='undefined'||!model){setTimeout(ready,100);return;}var back=global.goBack;global.goBack=function(){if(document.getElementById('native-recovery-dialog'))return true;return back&&back.apply(this,arguments);};resumed();}
  ready();
 });
})(window);
