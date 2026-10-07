'use strict';
// Port of fuel/calculator.py, with constants and reference data exported from PC.
function calculateSourceFuel(id,hours,arrival){
 const data=window.FLIGHTDECK_FUEL,c=data.constants,a=data.aircraft.find(row=>row.id===id);
 if(!a||!Number.isFinite(hours)||hours<=0)throw Error(webT('Choisissez un avion et une durée positive.','Choose an aircraft and a positive duration.'));
 const burn=a.cruise_burn_kg_h;
 if(!Number.isFinite(burn)||burn<=0)throw Error(webT('Consommation invalide.','Invalid burn rate.'));
 const candidates=data.destinations[String(arrival||'').trim().toUpperCase()]?.candidates||[];
 const alternate=candidates.length?candidates.reduce((x,y)=>x.distance_nm<=y.distance_nm?x:y):null;
 const trip=hours*burn,alternateTime=alternate?alternate.distance_nm/c.ALTERNATE_CRUISE_SPEED_KT+c.ALTERNATE_APPROACH_MINUTES/60:0;
 const components={taxi_out_kg:burn*c.TAXI_BURN_RATE_MULTIPLIER*c.TAXI_OUT_MINUTES/60,trip_kg:trip,contingency_kg:trip*c.CONTINGENCY_RATE,alternate_kg:alternateTime*burn,final_reserve_kg:burn*c.FINAL_RESERVE_MINUTES/60,taxi_in_kg:burn*c.TAXI_BURN_RATE_MULTIPLIER*c.TAXI_IN_MINUTES/60};
 const total=Object.values(components).reduce((sum,value)=>sum+value,0);if(!Number.isFinite(total))throw Error(webT('Total trop grand.','Total is too large.'));
 return{aircraft:a,alternate,components,total};
}
function webDurationHours(value){
 const text=String(value||'').trim().toLowerCase(),match=text.match(/^(\d+)\s*(?:h|:)\s*(\d{1,2})\s*m?$/);
 if(match)return Number(match[2])<60?Number(match[1])+Number(match[2])/60:NaN;
 if(!text)return NaN;
 const number=text.replace(/h$/,'').replace(',','.');return /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(number)?Number(number):NaN;
}
let webFuelResult=null;
function calculateWebFuel(){
 const chosen=document.getElementById('fuel_aircraft').value,hours=webDurationHours(document.getElementById('fuel_hours').value),arrival=document.getElementById('fuel_arrival')?.value||'';
 webFuelResult=null;
 document.getElementById('fuel_results_card').style.display='block';
 for(const id of['res_taxi_out','res_trip','res_contingency','res_alternate','res_reserve','res_taxi_in','res_total'])document.getElementById(id).textContent='—';
 document.getElementById('web-fuel-apply').disabled=true;
 if(!chosen||!Number.isFinite(hours)||hours<=0){document.getElementById('web-fuel-note').textContent=webT('Choisissez une variante et une durée positive.','Choose a variant and a positive duration.');return;}
 try{
  webFuelResult=calculateSourceFuel(chosen,hours,arrival);
  const keys={res_taxi_out:'taxi_out_kg',res_trip:'trip_kg',res_contingency:'contingency_kg',res_alternate:'alternate_kg',res_reserve:'final_reserve_kg',res_taxi_in:'taxi_in_kg'};
  for(const[id,key]of Object.entries(keys))document.getElementById(id).textContent=webFuelResult.components[key].toLocaleString(webLanguage,{maximumFractionDigits:0})+' kg';
  document.getElementById('res_total').textContent=webFuelResult.total.toLocaleString(webLanguage,{maximumFractionDigits:0})+' kg';
  document.getElementById('fuel_alternate_nm').value=webFuelResult.alternate?.distance_nm||0;
  document.getElementById('web-fuel-note').textContent=webFuelResult.alternate?`${webT('Dégagement statique','Static alternate')}: ${webFuelResult.alternate.icao} · ${webFuelResult.alternate.distance_nm} NM. ${webT('Sans météo ni NOTAM.','No weather or NOTAM checks.')}`:webT('Arrivée absente ou inconnue : dégagement = 0 kg, sans approche ajoutée.','Missing or unknown arrival: alternate = 0 kg, without added approach.');
  document.getElementById('web-fuel-apply').disabled=false;
  state.web_fuel_inputs={aircraft:chosen,hours:document.getElementById('fuel_hours').value,arrival};saveState();
 }catch(error){document.getElementById('web-fuel-note').textContent=error.message;}
}
function applyFuelToFlight(){
 if(!webFuelResult)return;
 document.getElementById('aircraft').value=webFuelResult.aircraft.name;state.aircraft=webFuelResult.aircraft.name;
 state.fuel=Math.round(webFuelResult.total);render();switchTab('form');showToast(webT('Avion et carburant appliqués au vol.','Aircraft and fuel applied to flight.'));
}
document.addEventListener('DOMContentLoaded',()=>{
 const select=document.getElementById('fuel_aircraft');select.replaceChildren();
 for(const row of[{id:'',name:webT('Choisir un avion / variante…','Choose aircraft / variant…')},...window.FLIGHTDECK_FUEL.aircraft]){const option=document.createElement('option');option.value=row.id;option.textContent=row.name;select.append(option);}
 const previous=state.web_fuel_inputs||{};select.value=previous.aircraft||'';document.getElementById('fuel_hours').value=previous.hours||'';
 const distance=document.getElementById('fuel_alternate_nm');distance.readOnly=true;
 distance.closest('.field').insertAdjacentHTML('beforebegin',`<div class="field"><label for="fuel_arrival">${webT('ICAO arrivée','Arrival ICAO')}</label><input id="fuel_arrival" maxlength="4" list="web-fuel-arrivals"><datalist id="web-fuel-arrivals">${Object.keys(window.FLIGHTDECK_FUEL.destinations).map(id=>`<option value="${id}"></option>`).join('')}</datalist></div>`);
 document.getElementById('fuel_arrival').value=previous.arrival||document.getElementById('arr_icao').value;
 document.getElementById('fuel_arrival').addEventListener('input',calculateWebFuel);
 const apply=document.querySelector('[onclick="applyFuelToFlight()"]');apply.id='web-fuel-apply';apply.insertAdjacentHTML('beforebegin','<p id="web-fuel-note" style="margin:12px 0"></p>');
 const language=document.getElementById('web-language');language.addEventListener('change',calculateWebFuel);
 calculateWebFuel();
 translateWebUI();
});
