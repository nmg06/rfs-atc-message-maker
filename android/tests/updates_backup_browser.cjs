// UI integration with real portable backup engine; network answers are explicitly simulated offline.
const {chromium}=require('playwright');const assert=require('node:assert/strict');
(async()=>{
 const port=Number(process.argv[2]),browser=await chromium.launch({headless:true,...(process.env.RFS_TEST_BROWSER?{channel:process.env.RFS_TEST_BROWSER}:{})});
 const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[],nativeCalls=[];let importStarted=null,releaseImport=null;
 page.on('pageerror',e=>errors.push(e.message));
 await page.exposeFunction('testRequest',async(id,method,payload)=>{
  nativeCalls.push(method);
  if(method==='native.importApply'&&importStarted){const started=importStarted;importStarted=null;await new Promise(resolve=>{releaseImport=resolve;started();});}
  const response=await fetch(`http://127.0.0.1:${port}/rpc`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({method,args:JSON.parse(payload)})});
  await page.evaluate(({id,envelope})=>window.androidReply(id,envelope),{id,envelope:await response.json()});
 });
 await page.addInitScript(()=>window.Android={request:(...args)=>window.testRequest(...args)});
 await page.goto(`http://127.0.0.1:${port}/index.html`);await page.waitForFunction(()=>Boolean(model));
 await page.evaluate(async()=>{model.state.language='en';model.state.intro_seen=true;model.state.joke_seen=true;model.state.tutorial_seen=true;model.state.flight.callsign='LOCAL-KEEP';model.state.flight.departure_icao='LFPG';model.state.preview_edits={'ATC REQUEST':'Keep my edited local message'};setResult(await rpc('save',stateArgs()));screen='flight';paint();});
 await page.locator('#settings-open').click();await page.waitForFunction(()=>!document.querySelector('#updates-enabled').disabled);
 assert.equal(await page.locator('#updates-enabled').isChecked(),false);
 assert.equal(await page.evaluate(async()=> (await rpc('native.updatesTestCount')).requests),0);
 await page.locator('#updates-enabled').check();await page.waitForFunction(()=>document.querySelector('#updates-status').textContent.includes('Check unavailable'));
 assert.equal(await page.evaluate(async()=> (await rpc('native.updatesTestCount')).requests),1);
 await page.reload();await page.waitForFunction(()=>Boolean(model));await page.locator('#settings-open').click();await page.waitForFunction(()=>!document.querySelector('#updates-enabled').disabled);
 assert.equal(await page.locator('#updates-enabled').isChecked(),true);assert.equal(await page.evaluate(async()=> (await rpc('native.updatesTestCount')).requests),1);
 await page.locator('#updates-enabled').uncheck();await page.locator('#updates-check').click();await page.waitForFunction(()=>!document.querySelector('#updates-check').disabled);
 assert.equal(await page.evaluate(async()=> (await rpc('native.updatesTestCount')).requests),2);
 await page.evaluate(async()=>{const backup=JSON.parse((await rpc('export')).text);backup.source.platform='windows';backup.payload.state.flight.callsign='REMOTE-FLIGHT';backup.payload.state.preview_edits={'ATC REQUEST':'Keep imported manual message'};await rpc('native.importTestSelect',{text:JSON.stringify(backup)});});
 await page.locator('#import').click();await page.locator('#backup-import-dialog').waitFor();assert((await page.locator('#backup-import-dialog').innerText()).includes('Windows'));
 await page.setViewportSize({width:320,height:640});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),320);
 // Delay the actual apply RPC. Android's Back entry point must keep the
 // modal open until commit completes, rather than sending an accidental cancel.
 const importReady=new Promise(resolve=>{importStarted=resolve;});
 await page.locator('#backup-merge').click();await importReady;
 const cancelledBefore=nativeCalls.filter(method=>method==='native.importCancel').length;
 assert.equal(await page.evaluate(()=>window.goBack()),true);
 assert.equal(await page.locator('#backup-import-dialog').isVisible(),true);
 assert.equal(await page.locator('#backup-import-dialog').getAttribute('data-applying'),'true');
 assert.equal(await page.locator('#backup-cancel').isDisabled(),true);
 assert.equal(await page.evaluate(()=>model.state.flight.callsign),'LOCAL-KEEP');
 assert.equal(nativeCalls.filter(method=>method==='native.importCancel').length,cancelledBefore);
 releaseImport();await page.waitForFunction(()=>screen==='flight'&&!document.querySelector('#backup-import-dialog'));
 assert.equal(await page.evaluate(()=>model.state.flight.callsign),'LOCAL-KEEP');assert.equal(await page.evaluate(()=>model.state.preview_edits['ATC REQUEST']),'Keep my edited local message');
 assert(await page.evaluate(()=>model.state.saved_flights.some(r=>r.flight.callsign==='REMOTE-FLIGHT')));
 const exported=await page.evaluate(async()=>JSON.parse((await rpc('export')).text));assert.equal(exported.format,'rfs-flightdeck-backup');assert.equal(exported.schema_version,1);
 await page.reload();await page.waitForFunction(()=>Boolean(model));assert.equal(await page.evaluate(()=>model.state.flight.callsign),'LOCAL-KEEP');
 await page.locator('#settings-open').click();await page.waitForFunction(()=>!document.querySelector('#updates-enabled').disabled);assert.equal(await page.locator('#updates-enabled').isChecked(),false);
 assert(!/Mises à jour|Fusionner|Reprendre une sauvegarde/.test(await page.locator('main').innerText()));assert.deepEqual(errors,[]);
 await page.screenshot({path:'build/updates-backup-phone-0.4.2.png'});
 console.log(JSON.stringify({updates_default_off:true,daily_throttle:true,manual_offline:true,portable_merge:true,back_during_apply_guarded:true,drafts_preserved:true,phone320:true}));await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
