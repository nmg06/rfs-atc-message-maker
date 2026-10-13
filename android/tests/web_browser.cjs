const {chromium}=require('playwright');const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.RFS_TEST_BROWSER?{channel:process.env.RFS_TEST_BROWSER}:{})});
 const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(`http://127.0.0.1:${process.argv[2]}/prototype/index.html`);
 await page.locator('.fd-help').waitFor();await page.locator('.fd-help [data-help="close"]').first().click();
 await page.locator('#web-language').selectOption('en');assert.equal(await page.locator('html').getAttribute('lang'),'en');
 await page.locator('#web-help').click();assert.equal(await page.locator('[data-faq]').count(),30);await page.locator('#fd-help-search').fill('ETE 5');assert.equal(await page.locator('[data-faq]:visible').count(),1);await page.locator('.fd-help [data-help="close"]').first().click();
 await page.locator('#tab-preview').click();await page.locator('#web-strict-copy').uncheck();await page.reload();assert.equal(await page.locator('#web-strict-copy').isChecked(),false);assert.equal(await page.locator('.fd-help').count(),0);assert.equal(await page.locator('#web-language').inputValue(),'en');
 for(const type of ['ATC REQUEST','AIRBORNE','ARRIVAL BOARD','FLIGHT COMPLETED']){
  await page.locator('#msg_type').selectOption(type);const text=await page.locator('body').innerText();assert(!/Piste de départ|Piste utilisée|Piste d’arrivée|Piste atterrissage|Contrôleur ATC|Informations du message|Avion \/ Modèle|Réserve finale/i.test(text));
 }
 await page.locator('#tab-fuel').click();await page.locator('#fuel_aircraft').selectOption('airbus_a220_300');await page.locator('#fuel_hours').fill('5h');await page.locator('#fuel_arrival').fill('EGLL');
 assert.equal(await page.evaluate(()=>webFuelResult.total),12285);
 await page.locator('#web-fuel-apply').click();assert.equal(await page.locator('#aircraft').inputValue(),'Airbus A220-300');
 await page.locator('#web-context-help').click();assert.equal(await page.locator('#fd-help-topic').inputValue(),'flight');
 await page.setViewportSize({width:320,height:640});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),320);
 await page.screenshot({path:'build/web-help-0.4.1.png'});assert.deepEqual(errors,[]);console.log(JSON.stringify({web:true,english:true,faq:30,copy_choice_restart:true,reference_fuel_kg:12285}));await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
