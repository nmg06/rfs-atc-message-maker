// Shipped Android UI + real bundled SQLite, using only the local test bridge.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const port=Number(process.argv[2]),base=`http://127.0.0.1:${port}`;
 const request=async(method,args={})=>(await(await fetch(base+'/rpc',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({method,args})})).json());
 const boot=await request('bootstrap');assert(boot.ok);
 const state=boot.result.value.state;Object.assign(state,{intro_seen:true,joke_seen:true,tutorial_seen:true,language:'en'});
 assert((await request('save',{state})).ok);
 const browser=await chromium.launch({headless:true,...(process.env.RFS_TEST_BROWSER?{channel:process.env.RFS_TEST_BROWSER}:{})});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[],remote=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(!r.url().startsWith(base+'/'))remote.push(r.url());});
  let finderDelay=0,holdFuel=false,releaseFuel=null,fuelPreparations=0,holdUpdate=false,releaseUpdate=null;
  await page.exposeFunction('testRequest',async(id,method,payload)=>{const envelope=await request(method,JSON.parse(payload));if(method==='finder'&&finderDelay)await new Promise(resolve=>setTimeout(resolve,finderDelay));if(method==='fuel_prepare'){fuelPreparations++;if(holdFuel)await new Promise(resolve=>releaseFuel=resolve);}if(method==='update'&&holdUpdate)await new Promise(resolve=>releaseUpdate=resolve);await page.evaluate(({id,envelope})=>window.androidReply(id,envelope),{id,envelope});});
  await page.addInitScript(()=>window.Android={request:(id,method,payload)=>window.testRequest(id,method,payload)});
  await page.goto(base+'/index.html');await page.locator('#flight-callsign').waitFor();
  await page.locator('[data-screen="finder"]').click();
  await page.locator('#finder-origin').fill('VIDP');
  assert(await page.locator('#finder-excluded_airports').isVisible());
  assert.equal(await page.locator('#finder-excluded_airports').locator('..').locator('label').textContent(),'Avoid these airports (ICAO / IATA)');
  await page.locator('#finder-excluded_airports').fill('vabb; BOM');
  await page.locator('#search').click();await page.waitForFunction(()=>finderResponse&&!finderBusy);
  const count=await page.evaluate(()=>finderResponse.available);assert(count>0);
  assert(await page.evaluate(()=>finderRows.every(r=>r.origin==='VIDP'&&r.origin!=='VABB'&&r.destination!=='VABB')));
  await page.reload();await page.locator('[data-screen="finder"]').click();
  assert.equal(await page.locator('#finder-origin').inputValue(),'VIDP');
  assert.equal(await page.locator('#finder-excluded_airports').inputValue(),'vabb; BOM');
  await page.locator('#finder-excluded_airports').fill('VABB INVALID');
  await page.locator('#search').click();await page.waitForFunction(()=>!finderBusy&&document.querySelector('#finder-excluded_airports').getAttribute('aria-invalid')==='true');
  assert.equal(await page.locator('#finder-results').textContent(),'');
  assert.match(await page.locator('#finder-status').textContent(),/up to 50 airport codes/);
  assert.equal(await page.evaluate(()=>document.activeElement.id),'finder-excluded_airports');
  await page.locator('#finder-excluded_airports').fill('ZZZA');
  await page.locator('#search').click();await page.waitForFunction(()=>!finderBusy&&document.querySelector('#finder-status').textContent.includes('not found in the local database'));
  assert.match(await page.locator('#finder-status').textContent(),/ZZZA/);
  // A delayed response for an earlier filter must not repopulate stale cards.
  await page.locator('#finder-excluded_airports').fill('VABB');finderDelay=250;
  await page.locator('#search').click();await page.waitForFunction(()=>finderBusy);
  await page.locator('#finder-excluded_airports').fill('VABB EGLL');
  await page.waitForFunction(()=>!finderBusy);finderDelay=0;
  assert.equal(await page.locator('#finder-results').textContent(),'');
  await page.locator('#search').click();await page.waitForFunction(()=>finderResponse&&!finderBusy);
  assert(await page.evaluate(()=>finderRows.every(r=>!['VABB','EGLL'].includes(r.destination))));
  // Field shortcut uses the total flight duration, never five remaining minutes.
  await page.locator('[data-screen="flight"]').click();
  await page.locator('#flight-aircraft').fill('Airbus A220-300');
  await page.locator('#flight-arrival_icao').fill('EGLL');
  await page.evaluate(()=>{model.state.per_type['ARRIVAL BOARD'].arrival_ete='5 min';});
  await page.locator('#flight-estimated_flight_time').locator('xpath=ancestor::details').evaluate(el=>el.open=true);
  await page.locator('#flight-estimated_flight_time').fill('5h');
  await page.setViewportSize({width:320,height:844});
  const fuelInputBox=await page.locator('#flight-fuel').boundingBox();
  const fuelShortcutBox=await page.locator('[data-action="open-fuel"]').boundingBox();
  assert(fuelShortcutBox.height>=48&&fuelShortcutBox.x>=0&&fuelShortcutBox.x+fuelShortcutBox.width<=320);
  assert(Math.abs(fuelInputBox.width-fuelShortcutBox.width)<1);
  assert.equal(await page.locator('[data-action="open-fuel"]').textContent(),'Calculate fuel');
  await page.locator('[data-action="open-fuel"]').click();await page.locator('#fuel-duration').waitFor();
  assert.equal(await page.locator('#fuel-duration').inputValue(),'5h');
  assert.equal(await page.locator('#fuel-arrival').inputValue(),'EGLL');
  assert.equal(await page.evaluate(()=>model.state.fuel_inputs.aircraft),'airbus_a220_300');
  assert.equal(await page.locator('#aircraft-chosen').textContent(),'Airbus A220-300');
  assert.equal(await page.locator('[data-action="open-fuel"]').count(),0);
  await page.locator('[data-action="fuel-calculate"]').click();await page.waitForFunction(()=>fuelResult!==null);
  assert(await page.locator('[data-action="fuel-use"]').isVisible());
  await page.locator('[data-screen="flight"]').click();
  // Keep the first real preparation response pending while the old form is
  // edited. The latest revision must survive and fuel must be prepared again.
  await page.evaluate(()=>flushEdits());const preparationsBefore=fuelPreparations;holdFuel=true;
  await page.locator('[data-action="open-fuel"]').click();
  while(!releaseFuel)await page.waitForTimeout(10);
  await page.locator('#flight-estimated_flight_time').fill('6h');
  await page.locator('#flight-callsign').fill('LATEST-DURING-FUEL');
  holdFuel=false;releaseFuel();releaseFuel=null;
  await page.waitForFunction(()=>screen==='fuel'&&navigationTarget===null&&pending.size===0);
  assert.equal(await page.locator('#fuel-duration').inputValue(),'6h');
  assert.equal(await page.evaluate(()=>model.state.flight.callsign),'LATEST-DURING-FUEL');
  assert.equal(fuelPreparations-preparationsBefore,2);
  assert.equal(await page.evaluate(()=>revision===savedRevision),true);
  assert.equal(await page.evaluate(()=>fuelResult),null);
  assert.equal(await page.locator('#fuel-result').textContent(),'');
  await page.locator('[data-screen="flight"]').click();
  // A newer screen choice while that retry flush is pending must cancel fuel.
  await page.evaluate(()=>{window.cancelledFuelPaints=[];const previousPaint=paint;paint=()=>{window.cancelledFuelPaints.push(screen);return previousPaint();};});
  await page.evaluate(()=>flushEdits());holdFuel=true;
  await page.locator('[data-action="open-fuel"]').click();
  while(!releaseFuel)await page.waitForTimeout(10);
  holdUpdate=true;await page.locator('#flight-callsign').fill('LATEST-AFTER-CANCEL');
  holdFuel=false;releaseFuel();releaseFuel=null;
  while(!releaseUpdate)await page.waitForTimeout(10);
  await page.evaluate(()=>{navigate('messages');});
  holdUpdate=false;releaseUpdate();releaseUpdate=null;
  await page.waitForFunction(()=>navigationTarget===null&&pending.size===0);
  assert.equal(await page.evaluate(()=>screen),'messages');
  assert.equal(await page.evaluate(()=>model.state.flight.callsign),'LATEST-AFTER-CANCEL');
  assert.equal(await page.evaluate(()=>window.cancelledFuelPaints.includes('fuel')),false);
  // A new flight with absent duration/arrival must not inherit another trip.
  await page.locator('[data-screen="flight"]').click();
  await page.locator('#flight-estimated_flight_time').fill('');await page.locator('#flight-arrival_icao').fill('');
  await page.locator('[data-action="open-fuel"]').click();await page.locator('#fuel-duration').waitFor();
  assert.equal(await page.locator('#fuel-duration').inputValue(),'');
  assert.equal(await page.locator('#fuel-arrival').inputValue(),'');
  assert.equal(await page.locator('#fuel-result').textContent(),'');
  // Helper edits are deliberately kept when the flight context is unchanged.
  await page.locator('#fuel-duration').fill('7h');await page.locator('#fuel-arrival').fill('LFPG');
  await page.locator('[data-screen="flight"]').click();await page.locator('[data-action="open-fuel"]').click();
  await page.locator('#fuel-duration').waitFor();
  assert.equal(await page.locator('#fuel-duration').inputValue(),'7h');
  assert.equal(await page.locator('#fuel-arrival').inputValue(),'LFPG');
  await page.locator('#settings-open').click();await page.locator('#state-language').selectOption('fr');
  await page.waitForFunction(()=>model.state.language==='fr'&&meta.finder_fields.excluded_airports.label.startsWith('Éviter'));
  await page.locator('#settings-open').click();await page.locator('[data-screen="finder"]').click();
  assert.match(await page.locator('#finder-excluded_airports').locator('..').locator('label').textContent(),/Éviter/);
  assert.deepEqual(errors,[]);assert.deepEqual(remote,[]);
  console.log(JSON.stringify({finderExclusions:true,realVidpMatches:count,persistence:true,invalidNotIgnored:true,staleResponseIgnored:true,fuelShortcutTotalDuration:true,fuelShortcutFits320px:true,fuelPendingEditPreserved:true,fuelRetryCancelledByNavigation:true,fuelStaleResultCleared:true,fuelMissingFieldsCleared:true,fuelManualSameContextPreserved:true,frEn:true,offline:true}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
