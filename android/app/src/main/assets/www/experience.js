'use strict';
// Small progressive improvements around the existing UI and Python engines.
let settingsReturn='flight',saveTimer=null,scrollPositions={},lookupSerial=0,savedRevision=0,editFlush=null;
let navigationIntent=0,navigationTarget=null;
const displayNames=new Intl.DisplayNames(['en'],{type:'region'});
countryName=(code,french)=>{try{return (lang()&&code)?displayNames.of(String(code).toUpperCase()):french;}catch{return french;}};
function applyVisualTheme(){
 const selected=meta?.visual_themes?.find(v=>v.id===model.state.visual_theme)||meta?.visual_themes?.[0];
 if(!selected)return;
 const colors=model.state.theme==='Clair'?selected.light:selected;
 for(const key of ['bg','card','field','text','muted','border','accent','accent_text'])
  document.documentElement.style.setProperty('--'+key.replaceAll('_','-'),colors[key]);
 document.querySelector('meta[name="theme-color"]').content=colors.bg;
 if(window.Android)rpc('native.appearance',{color:colors.bg,light:model.state.theme==='Clair',language:model.state.language}).catch(()=>{});
}
function saveStatus(dirty){if($('save-status'))$('save-status').textContent=dirty?t('Enregistrement…','Saving…'):t('✓ Enregistré sur ce téléphone','✓ Saved on this phone');}
async function flushEdits(){clearTimeout(saveTimer);saveTimer=null;let result;
 // Timer, navigation and lifecycle callbacks share one save. If typing
 // continues while it runs, await the latest revision before navigation/exit.
 while(model&&savedRevision!==revision){
  if(!editFlush){const current=revision;
   editFlush=rpc('update',stateArgs()).then(value=>{if(current===revision){savedRevision=current;setResult(value);updatePreviewUI();saveStatus(false);}return value;}).finally(()=>{editFlush=null;});
  }
  result=await editFlush;
 }
 return result;
}
changed=(clear=true)=>{revision++;if(clear)model.state.preview_edits={};saveStatus(true);clearTimeout(saveTimer);
 for(const id of ['copy','share'])if($(id))$(id).disabled=true;
 saveTimer=setTimeout(()=>flushEdits().catch(fail),180);route();};
window.flushState=()=>flushEdits().catch(fail);
window.addEventListener('pagehide',()=>window.flushState());
document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')window.flushState();});
const basePaint=paint;
paint=()=>{basePaint();applyVisualTheme();const settings=screen==='settings';$('settings-open').classList.toggle('is-close',settings);
 $('settings-open').setAttribute('aria-expanded',String(settings));$('settings-open').setAttribute('aria-label',settings?t('Fermer les paramètres','Close settings'):t('Ouvrir les paramètres','Open settings'));saveStatus(false);};
navigate=async next=>{const intent=++navigationIntent;try{scrollPositions[screen]=window.scrollY;if(next==='settings'&&screen!=='settings'&&navigationTarget!=='settings')settingsReturn=screen;
 navigationTarget=next;await flushEdits();if(intent!==navigationIntent)return;
 if(next==='fuel'){while(intent===navigationIntent){const current=revision,result=await rpc('fuel_prepare',stateArgs());if(intent!==navigationIntent)return;if(current!==revision){await flushEdits();continue;}const prepared=result.value.state.fuel_inputs;if(['aircraft','duration','arrival'].some(key=>model.state.fuel_inputs[key]!==prepared[key]))fuelResult=null;setResult(result);break;}}
 if(intent!==navigationIntent)return;screen=next;navigationTarget=null;paint();window.scrollTo(0,scrollPositions[next]||0);
 }catch(error){if(intent===navigationIntent){navigationTarget=null;fail(error);}}};
function toggleSettings(){navigate((navigationTarget||screen)==='settings'?settingsReturn:'settings');}
window.goBack=()=>{const dialog=document.querySelector('dialog[open]');if(dialog){dialog.close();return true;}
 const destination=navigationTarget||screen;
 if(destination==='settings'){navigate(settingsReturn);return true;}if(destination==='flight'){const intent=++navigationIntent;navigationTarget=null;flushEdits().then(()=>{if(intent===navigationIntent)return rpc('native.finish');}).catch(fail);return true;}navigate('flight');return true;};
const baseFlightPage=flightPage;
flightPage=()=>{
 const f=model.state.flight,session=model.state.active_session||{},log=model.state.flight_log||[];
 const total=log.reduce((n,v)=>n+v.seconds,0),duration=seconds=>`${Math.floor(seconds/3600)}h ${Math.floor(seconds%3600/60)}min`;
 let html=baseFlightPage().replace(t('Les informations suivent tous vos messages.','These details follow all your messages.'),
 t('Préparez votre vol. Les messages ATC restent facultatifs.','Prepare your flight. ATC messages remain optional.'));
 const quick=`<section class="card flight-overview"><div class="route-codes"><strong>${esc(f.departure_icao||'DEP')}</strong><span>→</span><strong>${esc(f.arrival_icao||'ARR')}</strong></div><p>${esc(f.airline||t('Compagnie à choisir','Choose airline'))} · ${esc(f.aircraft||t('Avion à choisir','Choose aircraft'))}</p><div class="actions"><button data-action="quick-finder">${t('Trouver un vol','Find a flight')}</button><button data-action="quick-fuel">${t('Carburant','Fuel')}</button><button data-action="open-map">${t('Carte','Map')}</button></div><p class="hint">${t('Envie d’un vol ?','Looking for a flight?')}</p><div class="actions"><button data-action="suggest-flight" data-min="1" data-max="3">${t('Court · 1–3 h','Short · 1–3 h')}</button><button data-action="suggest-flight" data-min="7" data-max="12">${t('Nuit · 7–12 h','Night · 7–12 h')}</button></div></section>`;
 html=html.replace('<section class="card">',quick+'<section class="card">');
 return html+`<details><summary>${t('Préparation au sol','Ground preparation')}</summary><p class="hint">${t('Pistes publiques disponibles dans la base locale. Vérifiez celles du jeu RFS : aucune piste n’est attribuée automatiquement. Les portes et contraintes compagnie/avion ne sont pas disponibles dans cette base.','Public runways in the local database. Check the RFS airport: no runway is assigned automatically. Gate and airline/aircraft restrictions are unavailable in this database.')}</p><button data-action="planning">${t('Consulter les aéroports','View airports')}</button><div id="planning-output"></div></details><section class="card"><h2>${t('Mon carnet de vol','My flight log')}</h2><p><strong>${log.length}</strong> ${t('vols terminés','completed flights')} · <strong>${duration(total)}</strong> ${t('chronométrées','timed')}</p>${session.flight?`<p>${esc(session.flight.departure_icao)} → ${esc(session.flight.arrival_icao)} · <strong id="flight-clock"></strong></p><div class="actions"><button data-action="session" data-operation="${session.started_at?'pause':'resume'}">${session.started_at?t('Pause','Pause'):t('Reprendre','Resume')}</button><button data-action="session" data-operation="finish">${t('Terminer ce vol','Complete flight')}</button></div>`:`<button data-action="session" data-operation="start">${t('Démarrer mon vol','Start my flight')}</button>`}<p class="hint">${t('Temps chronométré par vous, conservé après fermeture. Les recherches ne comptent pas comme des vols effectués.','Time recorded by you, retained after closing. Searches never count as completed flights.')}</p>${log.slice(0,5).map(v=>`<p class="hint">${esc(v.flight.departure_icao)} → ${esc(v.flight.arrival_icao)} · ${duration(v.seconds)}</p>`).join('')}</section>`;
};
function updateClock(){const el=$('flight-clock'),s=model?.state.active_session;if(el&&s){const seconds=s.seconds+(s.started_at?Math.max(0,(Date.now()-Date.parse(s.started_at))/1000):0);el.textContent=`${Math.floor(seconds/3600)}:${String(Math.floor(seconds%3600/60)).padStart(2,'0')}:${String(Math.floor(seconds%60)).padStart(2,'0')}`;}}
setInterval(updateClock,1000);
const baseSettingsPage=settingsPage;
settingsPage=()=>baseSettingsPage()+`<section class="card"><h2>${t('Personnaliser Flightdeck','Personalise Flightdeck')}</h2><label for="state-visual_theme">${t('Palette de couleurs','Colour palette')}</label><select id="state-visual_theme" data-scope="state" data-key="visual_theme">${meta.visual_themes.map(v=>`<option value="${v.id}" ${v.id===model.state.visual_theme?'selected':''}>${esc(v.name)}</option>`).join('')}</select><p class="hint">${t('Dix palettes, chacune en clair ou sombre. La même sélection existe sur PC.','Ten palettes, each with light and dark modes. The same selection is available on PC.')}</p><h3>${t('Icône du téléphone','Phone icon')}</h3><div class="actions"><button data-action="icon" data-icon="Default">${t('Avionique','Avionics')}</button><button data-action="icon" data-icon="Ocean">${t('Océan','Ocean')}</button><button data-action="icon" data-icon="Sunset">${t('Crépuscule','Sunset')}</button></div><h3>${t('Rappel de préparation','Preparation reminder')}</h3><p class="hint">${t('Un rappel local du vol actuel, uniquement à votre demande. Horaire approximatif selon Android, sans recherche ou météo en arrière-plan.','A local reminder for the current flight, only at your request. Approximate time depending on Android; no background flight search or weather polling.')}</p><input type="datetime-local" id="reminder-time" aria-label="${t('Date du rappel','Reminder date')}"><div class="actions"><button data-action="reminder">${t('Programmer ce rappel','Schedule reminder')}</button><button data-action="reminder-cancel">${t('Annuler le rappel','Cancel reminder')}</button></div></section>`;
function sourceDetails(sources){return sources.map(s=>`<p class="hint">${esc(s.name||s.source_id)} · ${esc(s.license_spdx||'')}<br>${esc(s.attribution_text||'')}</p>`).join('');}
function runwayTable(rows){return rows.length?`<table class="table"><thead><tr><th>${t('Pistes','Runways')}</th><th>${t('Longueur','Length')}</th><th>${t('Surface','Surface')}</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.le_ident)} / ${esc(r.he_ident)}</td><td>${r.length_ft?Math.round(r.length_ft*.3048)+' m':'—'}</td><td>${esc(r.surface||'—')}</td></tr>`).join('')}</tbody></table>`:`<p class="hint">${t('Aucune piste disponible dans ces données.','No runway available in these data.')}</p>`;}
function finderDetails(d,sources){const r=d.row;return`<div class="finder-readable"><h3>${esc(r.origin_name||r.origin)} → ${esc(r.destination_name||r.destination)}</h3><p>${esc(r.airline_name)} · ${esc(r.aircraft_model||r.aircraft||t('Avion inconnu','Unknown aircraft'))}</p><p>${r.duration_min==null?t('Durée inconnue','Unknown duration'):Math.round(r.duration_min)+' min'} · ${r.distance_nm?Math.round(r.distance_nm)+' NM':'—'}</p><p class="hint">${esc(d.duration.note)}</p>${d.warnings.map(w=>`<p class="danger">${esc(w)}</p>`).join('')}<p class="hint">${t('Observations historiques','Historical observations')} : ${r.n_obs} · ${esc(r.first_seen||'')} → ${esc(r.last_seen||'')}</p><h3>${esc(r.origin)} · ${t('Pistes répertoriées','Listed runways')}</h3>${runwayTable(d.runways.origin)}<h3>${esc(r.destination)} · ${t('Pistes répertoriées','Listed runways')}</h3>${runwayTable(d.runways.destination)}<p class="hint">${t('Ces pistes ne sont pas une affectation ATC. Aucune porte connue.','These runways are not an ATC assignment. No known gate.')}</p><details><summary>${t('Sources des données','Data sources')}</summary>${sourceDetails(sources)}</details></div>`;}
function planningHtml(result){return ['departure','arrival'].map(k=>{const p=result[k];return`<h3>${esc(p.airport?.icao||'—')} · ${esc(p.airport?.name||t('Aéroport introuvable','Airport not found'))}</h3>${runwayTable(p.runways)}<p class="hint">${t('Portes : indisponibles dans la base. Choisissez une porte disponible dans RFS.','Gates: unavailable in the database. Choose an available gate in RFS.')}</p>`;}).join('');}
function openSearchSelect(el){const options=[...el.options].map(v=>({value:v.value,label:v.textContent}));const dialog=document.createElement('dialog');dialog.className='aircraft-dialog';dialog.id='select-dialog';dialog.dataset.target=el.id||'';dialog._target=el;dialog._options=options;dialog.innerHTML=`<h2>${t('Choisir et rechercher','Choose and search')}</h2><input id="select-query" aria-label="${t('Rechercher','Search')}" autocomplete="off"><div id="select-results" class="search-items"></div><button data-experience="close-dialog">${t('Annuler','Cancel')}</button>`;dialog.addEventListener('close',()=>dialog.remove());document.body.append(dialog);dialog.showModal();selectResults('');$('select-query').focus();}
function selectResults(q){const d=$('select-dialog');$('select-results').innerHTML=d._options.map((v,i)=>({...v,i})).filter(v=>v.label.toLowerCase().includes(q.toLowerCase())).map(v=>`<button data-experience="select-option" data-index="${v.i}">${esc(v.label||t('Aucun','None'))}</button>`).join('')||`<p>${t('Aucun résultat','No result')}</p>`;}
function openLookup(target,kind){const d=document.createElement('dialog');d.id='lookup-dialog';d.dataset.target=target;d.dataset.kind=kind;d.className='aircraft-dialog';d.innerHTML=`<h2>${t('Choisir dans la base locale','Choose from local database')}</h2><input id="lookup-query" aria-label="${t('Nom ou code','Name or code')}" placeholder="Paris, CDG, LFPG…"><div id="lookup-results" class="search-items"></div><button data-experience="close-dialog">${t('Annuler','Cancel')}</button>`;d.addEventListener('close',()=>d.remove());document.body.append(d);d.showModal();lookup('');$('lookup-query').focus();}
async function lookup(query){const d=$('lookup-dialog'),seq=++lookupSerial;const r=await rpc('lookup',{kind:d.dataset.kind,query});if(seq!==lookupSerial||!$('lookup-dialog'))return;$('lookup-results').innerHTML=r.items.map(v=>`<button data-experience="lookup-select" data-code="${esc(v.code)}">${esc(v.code)} · ${esc(v.name)}</button>`).join('')||`<p>${t('Aucun résultat','No result')}</p>`;}
// Keep native select semantics/accessibility; add a searchable list on request.
const originalField=field;
field=(key,spec,value,scope,required=false,index='')=>{let html=originalField(key,spec,value,scope,required,index);const id=[scope,index,key].filter(Boolean).join('-');
 if(spec.kind==='choice'&&spec.choices.length>5)html=html.replace('</select>','</select>'+`<button class="quiet" data-experience="search-select" data-target="${id}">${t('Rechercher dans la liste','Search this list')}</button>`);
 if((scope==='flight'||scope==='finder')&&['departure_icao','arrival_icao','origin','destination','airline'].includes(key))html=html.replace('</div>',`<button class="quiet" data-experience="lookup-open" data-target="${id}" data-kind="${key==='airline'?'airline':'airport'}">${t('Choisir…','Choose…')}</button></div>`);
 return html;};
const baseFuelOutput=fuelOutput;
fuelOutput=()=>{const labels={taxi_out_kg:t('Roulage départ','Taxi out'),trip_kg:t('Vol','Trip'),contingency_kg:t('Marge','Contingency'),alternate_kg:t('Dégagement','Alternate'),final_reserve_kg:t('Réserve finale','Final reserve'),taxi_in_kg:t('Roulage arrivée','Taxi in')};let html=baseFuelOutput();
 for(const [key,label]of Object.entries(labels))html=html.replace(esc(key.replaceAll('_',' ')),label);
 const provenance=fuelResult.provenance;const start=html.indexOf('<pre>'),end=html.indexOf('</pre>',start);
 if(start>=0)html=html.slice(0,start)+`<p class="hint">${esc(provenance.catalogue_source||'RFS Fuel Helper')} · ${esc(provenance.catalogue_export_date||'')}</p><p class="hint">${esc(meta.fuel_catalogue_note||provenance.catalogue_note||'')}</p><table class="table">${Object.entries(fuelResult.components_exact).map(([k,v])=>`<tr><td>${labels[k]||esc(k)}</td><td>${v.toFixed(2)} kg</td></tr>`).join('')}</table>`+html.slice(end+6);return html;};
document.addEventListener('input',e=>{if(e.target.id==='select-query')selectResults(e.target.value);if(e.target.id==='lookup-query'){clearTimeout(lookup.timer);lookup.timer=setTimeout(()=>lookup(e.target.value).catch(fail),150);}});
document.addEventListener('change',e=>{if(['visual_theme','theme'].includes(e.target.dataset.key)){applyVisualTheme();mobileMap?.draw();}});
const baseDesignEditor=designEditor;
designEditor=()=>{const id=model.state.presentation.custom_id,draft=model.state.design_draft;if(!draft||draft.for_id!==id)return baseDesignEditor();const old=model.designs[id];model.designs[id]=draft.design;try{return baseDesignEditor();}finally{if(old)model.designs[id]=old;else delete model.designs[id];}};
const baseReportEditor=reportEditor;
reportEditor=()=>{let html=baseReportEditor();for(const key of ['summary','steps','expected','observed'])html=html.replace(`id="report-${key}" maxlength="20000"></textarea>`,`id="report-${key}" maxlength="20000">${esc(model.state.report_draft[key]||'')}</textarea>`);return html;};
document.addEventListener('input',e=>{if(e.target.id.startsWith('design-')){model.state.design_draft={for_id:model.state.presentation.custom_id,design:{name:$('design-name').value,guided:$('design-guided').checked,base_design:$('design-base').value,heading:$('design-heading').value,footer:$('design-footer').value,template:$('design-template').value}};changed(false);}if(['report-summary','report-steps','report-expected','report-observed'].includes(e.target.id)){model.state.report_draft=reportValue();changed(false);}});
document.addEventListener('click',e=>{if(e.target.closest('[data-action="new-design"]'))model.state.design_draft={};},true);
document.addEventListener('click',async e=>{const el=e.target.closest('button');if(!el)return;try{
 switch(el.dataset.experience){
 case 'search-select':openSearchSelect($(el.dataset.target));return;
 case 'close-dialog':el.closest('dialog').close();return;
 case 'select-option':{const d=$('select-dialog'),target=d._target;target.value=d._options[Number(el.dataset.index)].value;d.close();target.dispatchEvent(new Event('change',{bubbles:true}));return;}
 case 'lookup-open':openLookup(el.dataset.target,el.dataset.kind);return;
 case 'lookup-select':{const d=$('lookup-dialog'),target=$(d.dataset.target);target.value=el.dataset.code;d.close();target.dispatchEvent(new Event('input',{bubbles:true}));return;}
 }
 switch(el.dataset.action){
 case 'quick-finder':await navigate('finder');break;
 case 'quick-fuel':await navigate('fuel');break;
 case 'suggest-flight':model.state.finder_filters={...model.state.finder_filters,min_minutes:el.dataset.min,max_minutes:el.dataset.max};await navigate('finder');await runFinder(false);break;
 case 'planning':$('planning-output').innerHTML=planningHtml(await rpc('planning',stateArgs()));break;
 case 'session':await flushEdits();if(el.dataset.operation==='finish'&&!confirm(t('Confirmer ce vol terminé et ajouter son temps au carnet ?','Confirm completed flight and add its time to the log?')))return;await commandAction('session',{operation:el.dataset.operation});updateClock();break;
 case 'icon':await rpc('native.icon',{icon:el.dataset.icon});toast(t('Icône mise à jour. Le lanceur peut prendre quelques secondes.','Icon updated. Your launcher may take a few seconds.'));break;
 case 'reminder':{const when=new Date($('reminder-time').value).getTime();if(!Number.isFinite(when)||when<=Date.now())throw Error(t('Choisissez une date future.','Choose a future date.'));const f=model.state.flight;await rpc('native.reminder',{when,text:[f.callsign,f.departure_icao+' → '+f.arrival_icao,f.aircraft].filter(Boolean).join(' · ')});toast(t('Rappel programmé si les notifications sont autorisées.','Reminder scheduled if notifications are allowed.'));break;}
 case 'reminder-cancel':await rpc('native.reminderCancel');toast(t('Rappel annulé.','Reminder cancelled.'));break;
 }
 }catch(error){fail(error);}});
if(model)paint();

// Preserve already mounted results, particularly expanded details and scroll.
paintFinderRows=()=>{const container=$('finder-results');if(!container)return;let count=container.children.length;
 while(count>finderVisible){container.lastElementChild.remove();count--;}
 if(count<finderVisible)container.insertAdjacentHTML('beforeend',finderRows.slice(count,finderVisible).map((r,i)=>resultCard(r,count+i)).join(''));
 if($('finder-status'))$('finder-status').textContent=finderSummary();
 if($('more'))$('more').disabled=finderBusy||!(finderVisible<finderRows.length||finderResponse?.has_more);
 if($('less'))$('less').disabled=finderBusy||finderVisible<=100;};
