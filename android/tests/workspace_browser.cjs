const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs');
const {go}=require('./navigation.cjs');
(async()=>{
 const port=Number(process.argv[2]),browser=await chromium.launch({headless:true,...(process.env.RFS_TEST_BROWSER?{channel:process.env.RFS_TEST_BROWSER}:{})});
 const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[],remote=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(!r.url().startsWith(`http://127.0.0.1:${port}/`))remote.push(r.url());});
 await page.exposeFunction('testRequest',async(id,method,payload)=>{
  const response=await fetch(`http://127.0.0.1:${port}/rpc`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({method,args:JSON.parse(payload)})});
  await page.evaluate(({id,envelope})=>window.androidReply(id,envelope),{id,envelope:await response.json()});
 });
 await page.addInitScript(()=>window.Android={request:(...args)=>window.testRequest(...args)});
 try{
  await page.goto(`http://127.0.0.1:${port}/index.html`);await page.waitForFunction(()=>Boolean(model));
  await page.evaluate(async()=>{Object.assign(model.state,{intro_seen:true,joke_seen:true,tutorial_seen:true,language:'en'});model.state.finder_filters={rfs_only:true,diversify:false};setResult(await rpc('bootstrap',stateArgs()));screen='flight';paint();});
  assert(await page.locator('#cockpit').isVisible());assert.equal(await page.locator('#nav-tools').isVisible(),false);
  await page.locator('[data-workspace="prep-field"][data-field-key="departure_icao"]').click();
  assert.equal(await page.evaluate(()=>document.activeElement.id),'flight-departure_icao');
  await page.locator('[data-workspace="prep-field"][data-field-key="fuel"]').click();
  await page.waitForFunction(()=>screen==='fuel');assert(await page.locator('#aircraft-search').isVisible());
  await go(page,'flight');
  for(const width of [320,390,768,1366]){await page.setViewportSize({width,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width);}
  await page.setViewportSize({width:390,height:844});await go(page,'finder');
  assert(await page.locator('#finder-empty').isVisible());await page.locator('#finder-aircraft-picker').click();
  if(!await page.locator('#finder-aircraft-query').count())console.error(await page.evaluate(()=>({toast:$('toast').textContent,aircraft:meta.finder_aircraft?.length})),errors);
  assert.equal(await page.locator('#finder-aircraft-query').inputValue(),'');
  assert.equal(await page.locator('[data-workspace-aircraft="C152"]').locator('..').textContent().then(v=>v.includes('No flight profiles')),true);
  assert(await page.locator('[data-workspace-aircraft="C172"]').locator('..').textContent().then(v=>v.includes('Cessna')&&v.includes('flight profiles')));
  const total=await page.evaluate(()=>meta.finder_aircraft.length);
  assert(total>100);assert.equal(await page.locator('[data-workspace-aircraft]').count(),total);
  await page.locator('#finder-aircraft-options').hover();await page.mouse.wheel(0,450);
  await page.waitForFunction(()=>$('finder-aircraft-options').scrollTop>100);
  await page.locator('[data-workspace-aircraft="A20N"]').check();await page.locator('[data-workspace-aircraft="B789"]').check();
  await page.locator('#finder-aircraft-query').fill('Boeing');assert(await page.locator('[data-workspace-aircraft="B789"]').isVisible());
  await page.locator('[data-workspace="aircraft-close"]').click();assert.equal(await page.locator('.aircraft-chips button').count(),2);
  await page.locator('#finder-origin').fill('LFPG');await page.locator('#search').click();
  await page.waitForFunction(()=>!finderBusy&&finderRows.length>1);
  assert(await page.evaluate(()=>finderRows.every(r=>['A20N','B789'].includes(r.aircraft))));
  await page.locator('#result-0 [data-workspace="compare-add"]').click();await page.locator('#result-1 [data-workspace="compare-add"]').click();
  await page.locator('#compare-jump').click();assert.equal(await page.locator('.comparison thead th').count(),3);
  await page.reload();await page.waitForFunction(()=>Boolean(model));await go(page,'finder');
  assert.equal(await page.locator('.aircraft-chips button').count(),2);assert.equal(await page.locator('.comparison thead th').count(),3);
  await page.locator('[data-workspace="aircraft-remove"][data-code="A20N"]').click();assert.equal(await page.locator('.aircraft-chips button').count(),1);
  await page.locator('[data-workspace="compare-remove"]').first().click();assert.equal(await page.locator('.comparison thead th').count(),2);
  await page.locator('[data-workspace="duration"][data-min="7"]').click();assert.equal(await page.locator('#finder-min_minutes').inputValue(),'7');assert.equal(await page.locator('#finder-max_minutes').inputValue(),'12');
  await go(page,'map');await page.waitForFunction(()=>countryGeometry?.length===242);assert(!await page.locator('#satellite-toggle').isChecked());
  await page.locator('#nav-more').click();assert(await page.locator('#nav-tools').isVisible());assert.equal(await page.evaluate(()=>window.goBack()),true);assert(!await page.locator('#nav-tools').isVisible());
  await go(page,'flight');await page.locator('#flight-departure_icao').fill('LFPG');await page.locator('#flight-arrival_icao').fill('KJFK');await page.locator('#flight-callsign').fill('UX123');
  await page.evaluate(()=>flushEdits());await page.evaluate(()=>window.scrollTo(0,0));fs.mkdirSync('build/ux-audit',{recursive:true});
  await page.screenshot({path:'build/ux-audit/android-phone.png'});
  await page.setViewportSize({width:1366,height:900});await page.screenshot({path:'build/ux-audit/android-desktop.png'});
  await page.locator('#settings-open').click();assert.equal(await page.locator('[data-action="replay-joke"]').count(),0);
  const immediate=await page.evaluate(()=>{const input=$('state-theme');input.value='Clair';input.dispatchEvent(new Event('change',{bubbles:true}));const selected=meta.visual_themes.find(v=>v.id===model.state.visual_theme);return {actual:getComputedStyle(document.documentElement).getPropertyValue('--bg'),expected:selected.light.bg};});
  assert.equal(immediate.actual,immediate.expected,'Theme must change before the storage reply');
  await page.evaluate(()=>flushEdits());
  await page.reload();await page.waitForFunction(()=>Boolean(model));assert.equal(await page.locator('[data-action="welcome-joke"]').count(),0);
  assert.deepEqual(errors,[]);assert.deepEqual(remote,[]);
  console.log(JSON.stringify({pass:true,complete_aircraft_list:total,multiple_aircraft:true,comparison_restart:true,tools_back:true,offline:true,responsive:4}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
