const {go}=require('./navigation.cjs');
// Real UI + shared engines: English help, skip/replay, warning focus and free copy.
const {chromium}=require('playwright');const assert=require('node:assert/strict');
(async()=>{
 const port=Number(process.argv[2]),browser=await chromium.launch({headless:true,...(process.env.RFS_TEST_BROWSER?{channel:process.env.RFS_TEST_BROWSER}:{})});
 const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.exposeFunction('testRequest',async(id,method,payload)=>{
  const response=await fetch(`http://127.0.0.1:${port}/rpc`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({method,args:JSON.parse(payload)})});
  await page.evaluate(({id,envelope})=>window.androidReply(id,envelope),{id,envelope:await response.json()});
 });
 await page.addInitScript(()=>window.Android={request:(...args)=>window.testRequest(...args)});
 await page.goto(`http://127.0.0.1:${port}/index.html`);await page.waitForFunction(()=>Boolean(model));
 await page.evaluate(async()=>{model.state.language='en';model.state.intro_seen=true;model.state.tutorial_seen=false;model.state.message_type='ATC REQUEST';model.state.flight.departure_icao='';model.state.presentation.discord_aligned=false;model.state.preview_edits={'ATC REQUEST':'My incomplete flight Z'};model.state.strict_validation=true;setResult(await rpc('bootstrap',stateArgs()));screen='flight';paint();});
 await page.locator('.fd-help').waitFor();assert((await page.locator('.fd-help').textContent()).includes('Your cockpit, at your pace'));
 await page.locator('.fd-help [data-help="next"]').click();assert((await page.locator('.fd-help').textContent()).includes('Choose your aircraft'));
 await page.locator('.fd-help [data-help="close"]').first().click();await page.waitForFunction(()=>model.state.tutorial_seen);
 await go(page,'preview');assert(await page.locator('#copy').isDisabled());
 const index=await page.evaluate(()=>rendered.issues.findIndex(v=>v.field==='departure_icao'));
 await page.locator(`[data-issue-index="${index}"]`).click();await page.waitForFunction(()=>document.activeElement?.id==='flight-departure_icao');assert.equal(await page.evaluate(()=>screen),'flight');
 await go(page,'preview');await page.locator('#state-strict_validation').uncheck();await page.waitForFunction(()=>rendered.can_copy);
 assert.equal(await page.locator('#preview').inputValue(),'My incomplete flight Z');assert(await page.locator('[data-issue-index]').count()>0);
 await page.locator('#copy').click();await page.waitForFunction(()=>model.history[0]?.message==='My incomplete flight Z');
 await page.reload();await page.waitForFunction(()=>Boolean(model));assert.equal(await page.evaluate(()=>model.state.strict_validation),false);assert.equal(await page.locator('.fd-help').count(),0);
 await page.locator('#settings-open').click();assert((await page.locator('#state-visual_theme').textContent()).includes('Avionics'));assert(!(await page.locator('#state-visual_theme').textContent()).includes('Crépuscule'));
 await page.locator('[data-help-mode="faq"]').click();assert.equal(await page.locator('[data-faq]').count(),30);await page.locator('#fd-help-search').fill('ETE 5');assert.equal(await page.locator('[data-faq]:visible').count(),1);await page.locator('[data-faq]:visible summary').click();assert((await page.locator('[data-faq]:visible').textContent()).includes('about five minutes'));
 await page.locator('.fd-help [data-help="close"]').first().click();await page.locator('#settings-open').click();
 for(const section of ['flight','messages','preview','finder','fuel','map','library']){
  await go(page,section);await page.waitForFunction(v=>screen===v,section);
  const text=await page.locator('main').innerText();assert(!/Crépuscule|Avionique|Dégagement|Paramètres|Vérifier avant copie|Comprendre cet écran|Rechercher parmi|À compléter|réserve finale/i.test(text),`${section}: French UI leaked`);
  await page.locator('.context-help').click();assert.equal(await page.locator('#fd-help-topic').inputValue(),section);await page.locator('.fd-help [data-help="close"]').first().click();
 }
 await page.setViewportSize({width:320,height:640});await page.locator('.context-help').click();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),320);
 await page.screenshot({path:'build/phone-help-0.4.1.png'});assert.deepEqual(errors,[]);
 console.log(JSON.stringify({pass:true,english_sections:7,faq:30,skip_replay:true,warning_focus:true,free_copy_restart:true}));await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
