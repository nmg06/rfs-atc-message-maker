// Real public page: responsive install flow, keyboard, languages and draft safety.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.RFS_TEST_BROWSER?{channel:process.env.RFS_TEST_BROWSER}:{})});
 const page=await browser.newPage({viewport:{width:1366,height:900}}),errors=[],remote=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(!r.url().startsWith(`http://127.0.0.1:${process.argv[2]}/`))remote.push(r.url());});
 await page.addInitScript(()=>localStorage.setItem('rfs_mobile_state_v1',JSON.stringify({callsign:'DRAFT-DO-NOT-LOSE',dep_icao:'LFPG'})));
 await page.goto(`http://127.0.0.1:${process.argv[2]}/site/index.html`);
 assert.equal(await page.locator('#resume-draft').isVisible(),true);
 await page.locator('#platform-windows').click();assert((await page.locator('#installation').innerText()).includes('RFSATCMessageMaker.exe'));
 await page.locator('#platform-windows').press('ArrowRight');assert.equal(await page.locator('#platform-ios').getAttribute('aria-selected'),'true');assert(!(await page.locator('#installation').innerText()).includes('Télécharger pour Android'));
 await page.locator('#platform-ios').press('Home');assert.equal(await page.locator('#platform-android').getAttribute('aria-selected'),'true');
 assert((await page.locator('#installation .button').getAttribute('href')).includes('37626682395'));
 await page.locator('#site-language').click();assert.equal(await page.locator('html').getAttribute('lang'),'en');
 assert(!/Choisissez|départ|téléchargez|Vos questions|Votre prochain/.test(await page.locator('body').innerText()));
 await page.locator('#site-theme').click();await page.reload();assert.equal(await page.locator('body').evaluate(el=>el.classList.contains('dark')),true);assert.equal(await page.locator('html').getAttribute('lang'),'en');
 assert.equal(await page.evaluate(()=>JSON.parse(localStorage.getItem('rfs_mobile_state_v1')).callsign),'DRAFT-DO-NOT-LOSE');
 for(const width of [320,390,768,1366]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width);}
 await page.setViewportSize({width:1366,height:900});await page.screenshot({path:'build/ux-audit/site-desktop.png'});
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:'build/ux-audit/site-phone.png'});
 await page.goto(`http://127.0.0.1:${process.argv[2]}/site/mobile/index.html`);if(await page.locator('.fd-help').count())await page.locator('.fd-help [data-help="close"]').first().click();
 assert.equal(await page.locator('#callsign').inputValue(),'DRAFT-DO-NOT-LOSE');assert.equal(await page.locator('label[for="callsign"]').count(),1);
 await page.screenshot({path:'build/ux-audit/web-phone.png'});assert.deepEqual(errors,[]);assert.deepEqual(remote,[]);
 const blocked=await browser.newPage();await blocked.addInitScript(()=>{Object.defineProperty(Storage.prototype,'getItem',{value(){throw Error('Blocked');}});Object.defineProperty(Storage.prototype,'setItem',{value(){throw Error('Blocked');}});});
 const blockedErrors=[];blocked.on('pageerror',e=>blockedErrors.push(e.message));await blocked.goto(`http://127.0.0.1:${process.argv[2]}/site/index.html`);await blocked.locator('#site-language').click();await blocked.locator('#platform-windows').click();assert.equal(await blocked.locator('html').getAttribute('lang'),'en');assert.deepEqual(blockedErrors,[]);
 console.log(JSON.stringify({site:true,keyboard_tabs:true,bilingual:true,draft_preserved:true,storage_optional:true,responsive_widths:[320,390,768,1366],remote_requests:remote.length}));await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
