'use strict';
// Requests go through the native, allowlisted service, outside the engine queue.
const tileCache=new Map(),tilePending=new Set(),tileFailed=new Map(),windCache=new Map();
let onlineTimer=null,windData=null,windKey='',windPending=false,onlineEpoch=0;
const pressureLevels=[850,700,500,400,300,250,200,150];
const plainMapPage=mapPage;
mapPage=()=>plainMapPage()+`<details><summary>${t('Satellite et vents · Internet facultatif','Satellite and wind · optional Internet')}</summary><p class="hint">${t('Désactivés au départ. Les fonctions principales restent hors ligne. Seuls les emplacements de la carte sont transmis aux fournisseurs ; aucune donnée pilote.','Initially disabled. Core features stay offline. Only map locations go to providers; no pilot data.')}</p><label class="check"><input id="satellite-toggle" type="checkbox" ${model.state.map_settings.satellite?'checked':''}>${t('Satellite EOX 2025','EOX 2025 satellite')}</label><label class="check"><input id="winds-toggle" type="checkbox" ${model.state.map_settings.winds?'checked':''}>${t('Vents en altitude Open-Meteo','Open-Meteo upper-air wind')}</label><label for="wind-level">${t('Niveau de pression','Pressure level')}</label><select id="wind-level">${pressureLevels.map(v=>`<option value="${v}" ${v===(model.state.map_settings.wind_level||250)?'selected':''}>${v} hPa</option>`).join('')}</select><p id="online-status" class="hint" role="status"></p><p class="hint">EOX Sentinel-2 cloudless 2025 · CC BY-NC-SA 4.0 · Copernicus. Open-Meteo · CC BY 4.0. ${t('Prévisions du monde réel, pouvant différer de RFS. Hauteurs géopotentielles en mètres AMSL. Le niveau de pression n’est pas une altitude fixe. Aucun changement des durées ou du carburant.','Real-world forecasts may differ from RFS. Geopotential heights in metres AMSL. A pressure level is not a fixed altitude. Flight durations and fuel remain unchanged.')}</p></details>`;
function onlineStatus(text){if($('online-status'))$('online-status').textContent=text;}
function tilePosition(lat,lon,z){const n=2**z;return [(lon+180)/360*n,(1-Math.log(Math.tan(Math.PI/4+Math.max(-85.051,Math.min(85.051,lat))*Math.PI/360))/Math.PI)/2*n];}
function tileWorld(z,x,y){const n=2**z;return [x/n*360-180,(y/n*2-1)*180];}
function visibleTiles(map){const z=Math.max(0,Math.min(15,Math.floor(Math.log2(map.scale()*360/256)))),n=2**z;
 const tl=map.world([0,0]),br=map.world([map.canvas.clientWidth,map.canvas.clientHeight]);
 const x0=Math.floor((tl[0]+180)/360*n),x1=Math.floor((br[0]+180)/360*n),y0=Math.max(0,Math.floor((tl[1]+180)/360*n)),y1=Math.min(n-1,Math.floor((br[1]+180)/360*n));
 const rows=[];for(let y=y0;y<=y1;y++)for(let x=x0;x<=x1;x++){if(rows.length>=20)return rows;rows.push({z,x:((x%n)+n)%n,worldX:x,y,key:`${z}/${((x%n)+n)%n}/${y}`});}return rows;
}
function onlinePaintTiles(map,w,h){if(!model.state.map_settings.satellite)return false;let painted=false;const c=map.ctx,s=map.scale();for(const tile of visibleTiles(map)){const image=tileCache.get(tile.key);if(!image)continue;const [x,y]=tileWorld(tile.z,tile.worldX,tile.y),size=360/2**tile.z*s;c.drawImage(image,w/2+(x-map.center[0])*s,h/2+(y-map.center[1])*s,size+1,size+1);painted=true;}return painted;}
function scheduleOnline(){clearTimeout(onlineTimer);if(!mobileMap)return;onlineTimer=setTimeout(()=>fetchOnline().catch(e=>onlineStatus(t('Service indisponible : carte locale conservée. ','Service unavailable: local map retained. ')+e.message)),350);}
async function fetchOnline(){const map=mobileMap;if(!map||map.dead)return;const v=model.state.map_settings,epoch=onlineEpoch;
 if(!v.satellite&&!v.winds){await rpc('native.online',{enabled:false});return;}
 await rpc('native.online',{enabled:true});if(epoch!==onlineEpoch)return;
 if(v.satellite){for(const tile of visibleTiles(map)){if(tileCache.has(tile.key)||tilePending.has(tile.key)||(tileFailed.get(tile.key)||0)>Date.now())continue;if(tilePending.size>=6)break;tilePending.add(tile.key);
  rpc('native.tile',tile).then(r=>{if(epoch!==onlineEpoch)return;const image=new Image();image.onload=()=>{tileCache.set(tile.key,image);while(tileCache.size>48)tileCache.delete(tileCache.keys().next().value);if(mobileMap)mobileMap.draw();};image.src=r.data;}).catch(()=>{tileFailed.set(tile.key,Date.now()+30000);onlineStatus(t('Satellite indisponible : carte locale conservée.','Satellite unavailable: local map retained.'));}).finally(()=>{tilePending.delete(tile.key);if(epoch===onlineEpoch&&mobileMap&&!map.dead)scheduleOnline();});}
 }
 if(v.winds&&!windPending){const level=v.wind_level||250,points=[];for(let y=1;y<=3;y++)for(let x=1;x<=4;x++){const p=map.world([map.canvas.clientWidth*x/5,map.canvas.clientHeight*y/4]);const lat=MapProjection.latitude(p[1]);if(Math.abs(lat)<=85)points.push([Math.round(lat*2)/2,Math.round(MapProjection.longitude(p[0])*2)/2]);}
  if(!points.length)return;const key=JSON.stringify([level,points]);const cached=windCache.get(key);if(cached&&Date.now()-cached.time<900000){if(!windData||windKey!==key){windData=cached.data;windKey=key;map.draw();}showWindInfo(cached.data);return;}
  windPending=true;try{const result=await rpc('native.wind',{points,level});if(epoch!==onlineEpoch)return;windCache.set(key,{data:result,time:Date.now()});while(windCache.size>4)windCache.delete(windCache.keys().next().value);windData=result;windKey=key;map.draw();onlineStatus(`${level} hPa · ${result.samples[0].time} · ${t('hauteurs','heights')} ${Math.round(Math.min(...result.samples.map(s=>s.height_m)))}–${Math.round(Math.max(...result.samples.map(s=>s.height_m)))} m AMSL`);}finally{windPending=false;}
 }
}
function showWindInfo(data){onlineStatus(`${data.level} hPa · ${data.samples[0].time} · ${t('hauteurs','heights')} ${Math.round(Math.min(...data.samples.map(s=>s.height_m)))}–${Math.round(Math.max(...data.samples.map(s=>s.height_m)))} m AMSL`);}
setInterval(()=>{if(mobileMap&&model.state.map_settings.winds)fetchOnline().catch(()=>onlineStatus(t('Actualisation indisponible. Dernière prévision conservée.','Refresh unavailable. Last forecast retained.')));},60000);
function paintWinds(map){if(!model.state.map_settings.winds||!windData||windData.level!==(model.state.map_settings.wind_level||250))return;const c=map.ctx,s=map.scale(),w=map.canvas.clientWidth,h=map.canvas.clientHeight;c.save();c.strokeStyle=getComputedStyle(document.documentElement).getPropertyValue('--accent').trim();c.fillStyle=c.strokeStyle;c.lineWidth=2;c.font='11px system-ui';
 for(const sample of windData.samples){const x=w/2+(sample.longitude-map.center[0])*s,y=h/2+(MapProjection.y(sample.latitude)-map.center[1])*s;if(x<0||x>w||y<0||y>h)continue;const a=sample.direction*Math.PI/180,dx=-Math.sin(a)*20,dy=Math.cos(a)*20;c.beginPath();c.moveTo(x-dx/2,y-dy/2);c.lineTo(x+dx/2,y+dy/2);c.stroke();const angle=Math.atan2(dy,dx);c.beginPath();c.moveTo(x+dx/2,y+dy/2);c.lineTo(x+dx/2-7*Math.cos(angle-.5),y+dy/2-7*Math.sin(angle-.5));c.lineTo(x+dx/2-7*Math.cos(angle+.5),y+dy/2-7*Math.sin(angle+.5));c.closePath();c.fill();c.fillText(Math.round(sample.speed)+' kt',x+12,y+16);}
 c.restore();}
const offlineDraw=OfflineRouteMap.prototype.draw;
OfflineRouteMap.prototype.draw=function(){offlineDraw.call(this);scheduleOnline();};
const offlinePaint=OfflineRouteMap.prototype.paint;
OfflineRouteMap.prototype.paint=function(){offlinePaint.call(this);paintWinds(this);};
const offlineStop=stopMobileMap;
stopMobileMap=()=>{onlineEpoch++;clearTimeout(onlineTimer);windData=null;offlineStop();rpc('native.online',{enabled:false}).catch(()=>{});};
document.addEventListener('change',async e=>{if(!['satellite-toggle','winds-toggle','wind-level'].includes(e.target.id))return;try{
 if(e.target.id==='wind-level')model.state.map_settings.wind_level=Number(e.target.value);
 else model.state.map_settings[e.target.id==='satellite-toggle'?'satellite':'winds']=e.target.checked;
 await rpc('persist',stateArgs());mobileMap?.draw();scheduleOnline();
 }catch(error){fail(error);}});
