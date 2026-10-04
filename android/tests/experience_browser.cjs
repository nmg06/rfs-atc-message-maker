const {chromium}=require('playwright');
const assert=require('node:assert/strict');
(async()=>{
 const port=Number(process.argv[2]),browser=await chromium.launch({headless:true,...(process.env.RFS_TEST_BROWSER?{channel:process.env.RFS_TEST_BROWSER}:{})});
 const page=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:3});
 const errors=[],requests=[];page.on('pageerror',e=>{errors.push(e.message);console.error(e.message);});
 await page.exposeFunction('testRequest',async(id,method,payload)=>{requests.push(method);if(method==='native.finish'){await page.evaluate(id=>window.androidReply(id,{ok:true,result:{}}),id);return;}const response=await fetch(`http://127.0.0.1:${port}/rpc`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({method,args:JSON.parse(payload)})});await page.evaluate(({id,envelope})=>window.androidReply(id,envelope),{id,envelope:await response.json()});});
 await page.addInitScript(()=>window.Android={request:(...args)=>window.testRequest(...args)});
 await page.goto(`http://127.0.0.1:${port}/index.html`);try{await page.locator('[data-action="welcome-joke"], [data-action="welcome-done"], #flight-callsign').first().waitFor({state:'attached'});}catch(e){console.error(await page.evaluate(()=>({loading:$('loading').textContent,screen,model:!!model,toast:$('toast').textContent})));await browser.close();throw e;}
 if(await page.locator('[data-action="welcome-joke"]').count()){await page.locator('[data-action="welcome-joke"]').click();await page.locator('[data-action="welcome-done"]').waitFor();}
 if(await page.locator('[data-action="welcome-done"]').count()){await page.locator('[data-action="welcome-done"]').click();await page.locator('.fd-help [data-help="close"]').first().click();await page.locator('#flight-callsign').waitFor({state:'attached'});}
 await page.evaluate(async()=>{model.state.language='fr';model.state.finder_filters={};model.state.flight.departure_icao='LFPG';model.state.flight.arrival_icao='KJFK';model.state.flight_log=[];model.state.active_session={};setResult(await rpc('bootstrap',stateArgs()));paint();});
 // Real menu returns to the exact tool and scroll position; reduced-motion CSS.
 await page.locator('[data-screen="finder"]').click();await page.locator('#finder-origin').fill('LFPG');await page.locator('#finder-max_minutes').fill('2h');
 await page.locator('#search').click();await page.waitForFunction(()=>finderRows.length===100);
 await page.locator('#result-0 [data-action="finder-details"]').click();
 await page.locator('#finder-detail-0 .finder-readable').waitFor();
 assert.equal(await page.locator('#finder-detail-0 pre').count(),0);
 assert((await page.locator('#finder-detail-0').textContent()).includes('Pistes répertoriées'));
 const pad=await page.locator('#result-0').evaluate(el=>getComputedStyle(el).paddingLeft);assert.equal(pad,'20px');
 await page.evaluate(()=>window.scrollTo(0,680));const previous=await page.evaluate(()=>window.scrollY);
 await page.locator('#settings-open').click();await page.waitForFunction(()=>screen==='settings');
 assert.equal(await page.locator('#settings-open').getAttribute('aria-expanded'),'true');
 await page.locator('#settings-open').click();await page.waitForFunction(()=>screen==='finder');
 assert.equal(await page.evaluate(()=>window.scrollY),previous);
 await page.locator('#settings-open').click();await page.locator('#state-visual_theme').selectOption('sunset');
 await page.waitForFunction(()=>getComputedStyle(document.documentElement).getPropertyValue('--accent')==='#ffb393');
 await page.locator('#settings-open').click();await page.locator('[data-screen="flight"]').click();
 // Consecutive keystrokes are saved once; immediate navigation flushes last byte.
 const before=requests.filter(v=>v==='update').length;
 await page.locator('#flight-callsign').pressSequentially('XYZ',{delay:10});
 await page.waitForTimeout(350);assert(requests.filter(v=>v==='update').length-before<=2);
 await page.locator('#flight-callsign').fill('LAST-BYTE-Z');await page.locator('[data-screen="map"]').click();
 await page.waitForFunction(()=>mobileMap?.data.route.length===97&&countryGeometry?.length===242);
 assert.equal(await page.evaluate(()=>mobileMap.canvas.width/mobileMap.canvas.clientWidth),1.75);
 assert(!requests.includes('native.tile'));assert(!requests.includes('native.wind'));
 const timing=await page.evaluate(async()=>{const values=[];for(let i=0;i<15;i++){mobileMap.zoomAt(i%2?1.05:1/1.05);const start=performance.now();mobileMap.paint();values.push(performance.now()-start);}return values;});
 await page.locator('[data-screen="flight"]').click();await page.locator('summary').filter({hasText:'Préparation au sol'}).click();await page.locator('[data-action="planning"]').click();
 await page.locator('#planning-output table').first().waitFor();assert((await page.locator('#planning-output').textContent()).includes('Portes : indisponibles'));
 await page.locator('[data-action="session"][data-operation="start"]').click();await page.waitForFunction(()=>Boolean(model.state.active_session.started_at));
 await page.reload();await page.waitForFunction(()=>Boolean(model.state.active_session.started_at));if(!await page.locator('#flight-callsign').count())console.error(await page.evaluate(()=>({screen,intro:model.state.intro_seen,tutorial:model.state.tutorial_seen,errors:$('toast').textContent})));assert.equal(await page.locator('#flight-callsign').inputValue(),'LAST-BYTE-Z');
 assert.equal(await page.evaluate(()=>model.state.visual_theme),'sunset');
 page.on('dialog',d=>d.accept());await page.locator('[data-action="session"][data-operation="finish"]').click();await page.waitForFunction(()=>model.state.flight_log.length===1);
 await page.locator('[data-experience="lookup-open"][data-target="flight-departure_icao"]').click();await page.locator('#lookup-query').fill('CDG');await page.locator('[data-experience="lookup-select"][data-code="LFPG"]').click();
 await page.locator('[data-screen="messages"]').click();await page.locator('[data-experience="search-select"][data-target="state-message_type"]').click();await page.locator('#select-query').fill('ATIS');await page.locator('[data-experience="select-option"]').click();await page.waitForFunction(()=>model.state.message_type==='ATIS');
 await page.locator('#settings-open').click();await page.evaluate(()=>window.goBack());await page.waitForFunction(()=>screen==='messages');
 // Drafts must survive settings navigation and a full UI restart without Save.
 await page.locator('#settings-open').click();
 await page.locator('[data-action="replay-joke"]').click();await page.locator('[data-action="welcome-joke"]').waitFor();assert((await page.locator('main').textContent()).includes('999 €'));assert(!(await page.locator('main').textContent()).includes('étaient une blague'));
 await page.locator('[data-action="welcome-joke"]').click();await page.waitForFunction(()=>document.querySelector('main').textContent.includes('Les 999 € étaient une blague'));await page.locator('[data-action="welcome-done"]').click();await page.waitForFunction(()=>screen==='settings');
 await page.locator('summary').filter({hasText:'Designs personnels'}).click();
 await page.locator('#design-name').fill('Brouillon sans bouton');await page.locator('#design-heading').fill('MON EN-TETE');
 await page.locator('summary').filter({hasText:'Signaler un problème'}).click();
 await page.locator('#report-summary').fill('Brouillon du signalement');
 await page.locator('#settings-open').click();await page.reload();await page.waitForFunction(()=>Boolean(model));await page.locator('#settings-open').click();
 assert.equal(await page.locator('#design-name').inputValue(),'Brouillon sans bouton');assert.equal(await page.locator('#design-heading').inputValue(),'MON EN-TETE');assert.equal(await page.locator('#report-summary').inputValue(),'Brouillon du signalement');
 await page.locator('#settings-open').click();await page.locator('[data-screen="flight"]').click();
 await page.locator('#flight-callsign').fill('EXIT-LAST-BYTE');await page.evaluate(()=>window.goBack());await page.waitForFunction(()=>pending.size===0);assert(requests.includes('native.finish'));
 await page.reload();await page.waitForFunction(()=>Boolean(model));assert.equal(await page.locator('#flight-callsign').inputValue(),'EXIT-LAST-BYTE');
 await page.setViewportSize({width:320,height:640});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),320);
 await page.locator('[data-screen="flight"]').click();await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:process.argv[3]||'build/phone-0.4.png'});
 assert.deepEqual(errors,[]);console.log(JSON.stringify({pass:true,menu_return:true,readable_details:true,autosave_restart:true,planning:true,log:true,searchable_lists:true,zero_online_requests:true,canvas_draw_ms:timing}));await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
