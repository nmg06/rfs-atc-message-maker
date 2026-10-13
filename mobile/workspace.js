'use strict';
(() => {
 const tr=(fr,en)=>webT(fr,en),safe=value=>String(value||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const previousRender=render,previousTab=switchTab,previousSave=saveState;
 let canSave=true;
 function decorate(){
  for(const field of document.querySelectorAll('.field')){const label=field.querySelector('label'),input=field.querySelector('input,select,textarea');if(label&&input?.id)label.htmlFor=input.id;}
  const active=document.querySelector('.tab-btn.active');document.querySelectorAll('.tab-btn').forEach(button=>button.setAttribute('aria-current',button===active?'page':'false'));
  const strip=document.getElementById('web-flight-strip');if(!strip)return;
  strip.innerHTML=`<div><p class="route-label">${tr('VOTRE ESPACE DE PRÉPARATION','YOUR PREPARATION SPACE')}</p><h1>${tr('Un vol à votre rythme.','A flight at your pace.')}</h1><p>${tr('Trajet d’abord. Le message vient ensuite.','Route first. Your message comes next.')}</p><small class="web-save" role="status">${tr('Enregistré dans ce navigateur','Saved in this browser')}</small></div><div class="web-route"><strong>${safe(state.dep_icao.trim().toUpperCase()||'DEP')}</strong><span aria-hidden="true"> → </span><strong>${safe(state.arr_icao.trim().toUpperCase()||'ARR')}</strong></div>`;
  if(!canSave)strip.querySelector('.web-save').textContent=tr('Sauvegarde indisponible : gardez cette page ouverte.','Saving unavailable: keep this page open.');
  const home=document.getElementById('web-home');if(home)home.textContent=tr('← Accueil','← Home');
  const title=document.getElementById('web-presentation-title');if(title)title.textContent=tr('Design, longueur et emojis','Design, length and emojis');
 }
 render=()=>{previousRender();decorate();};
 switchTab=name=>{previousTab(name);decorate();};
 saveState=()=>{previousSave();try{canSave=localStorage.getItem(STORAGE_KEY)===JSON.stringify(state);}catch{canSave=false;}};
 document.addEventListener('DOMContentLoaded',()=>{
  const container=document.querySelector('.container');container.insertAdjacentHTML('afterbegin','<section class="web-flight-strip" id="web-flight-strip" aria-label="Flight"></section>');
  const form=document.getElementById('panel-form'),[configuration,flight]=form.querySelectorAll(':scope > .card');flight.classList.add('web-route-card');form.insertBefore(flight,configuration);
  const disclosure=document.createElement('details');disclosure.className='web-disclosure';disclosure.innerHTML='<summary id="web-presentation-title"></summary>';const grids=configuration.querySelectorAll('.grid-2');
  for(const grid of grids){for(const id of ['design','length','emojis']){const el=grid.querySelector('#'+id);if(el)disclosure.append(el.closest('.field'));}if(!grid.children.length)grid.remove();}configuration.append(disclosure);
  const note=document.getElementById('web-prototype-note');if(note)note.classList.add('web-note');
  const home=document.createElement('a');home.id='web-home';home.className='web-home';home.href='../index.html';document.querySelector('.brand').append(home);
  document.getElementById('preview_text').setAttribute('role','region');document.getElementById('preview_text').setAttribute('aria-label','Discord preview');document.querySelector('[onclick="togglePreview()"]')?.setAttribute('aria-label',tr('Ouvrir ou fermer l’aperçu','Open or close preview'));
  document.getElementById('web-language').addEventListener('change',decorate);decorate();
  if(location.hash==='#help')FlightdeckHelp.open('flight','faq');
 });
})();
