// Actual UI/engine with missing Web APIs explicitly emulated; no claim to run an old browser binary.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{
 const port=Number(process.argv[2]),browser=await chromium.launch({headless:true,...(process.env.RFS_TEST_BROWSER?{channel:process.env.RFS_TEST_BROWSER}:{})});
 const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 await page.exposeFunction('testRequest',async(id,method,payload)=>{
  const response=await fetch(`http://127.0.0.1:${port}/rpc`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({method,args:JSON.parse(payload)})});
  await page.evaluate(({id,envelope})=>window.androidReply(id,envelope),{id,envelope:await response.json()});
 });
 await page.addInitScript(()=>{Intl.DisplayNames=undefined;String.prototype.replaceAll=undefined;window.Android={countryNames:()=>JSON.stringify({FR:'France',RO:'Romania',TR:'Turkey',US:'United States',GB:'United Kingdom'}),request:(...args)=>window.testRequest(...args)};});
 await page.goto(`http://127.0.0.1:${port}/index.html`);await page.waitForFunction(()=>Boolean(model));
 await page.evaluate(async()=>{model.state.language='en';model.state.intro_seen=true;model.state.joke_seen=true;model.state.tutorial_seen=true;setResult(await rpc('save',stateArgs()));screen='flight';paint();});
 assert.equal(await page.evaluate(()=>new Intl.DisplayNames(['en'],{type:'region'}).of('RO')),'Romania');
 assert.equal(await page.evaluate(()=> 'a.b.a.b'.replaceAll('.','X')),'aXbXaXb');
 assert.equal(await page.evaluate(()=> 'abc'.replaceAll('','-')),'-a-b-c-');
 assert.equal(await page.evaluate(()=> 'aba'.replaceAll('a','$&x')),'axbax');
 assert.equal(await page.evaluate(()=> 'aa'.replaceAll(/a/g,'b')),'bb');
 assert.equal(await page.evaluate(()=>{try{'a'.replaceAll(/a/,'b');return false;}catch(error){return error instanceof TypeError;}}),true);
 await page.locator('[data-action="flight-aircraft-open"]').click();await page.locator('#flight-aircraft-dialog').waitFor();await page.locator('#flight-aircraft-search').fill('A320');assert((await page.locator('#flight-aircraft-results').innerText()).includes('A320'));await page.locator('[data-action="flight-aircraft-close"]').click();
 await page.evaluate(()=>openCountry('flight-departure_icao'));await page.locator('#country-search').fill('Romania');assert((await page.locator('#country-results').innerText()).includes('Romania'));assert(!(await page.locator('#country-results').innerText()).includes('Roumanie'));await page.locator('[data-action="country-close"]').click();
 assert.deepEqual(errors,[]);console.log(JSON.stringify({emulated_missing_apis:true,local_english_country_names:true,replaceAll_literal_and_regexp:true,aircraft_modal:true,no_page_errors:true}));await browser.close();
})().catch(error=>{console.error(error);process.exit(1);});
