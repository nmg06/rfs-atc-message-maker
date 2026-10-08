const {go}=require('./navigation.cjs');
// Actual shipped UI and bundled route evidence, isolated local profile.
const {chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{
 const base=`http://127.0.0.1:${Number(process.argv[2])}`;
 const request=async(method,args={})=>(await(await fetch(base+'/rpc',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({method,args})})).json());
 const boot=await request('bootstrap');assert(boot.ok);
 const state=boot.result.value.state;
 Object.assign(state,{intro_seen:true,joke_seen:true,tutorial_seen:true,language:'en'});
 Object.assign(state.flight,{aircraft:'Airbus A350-900',estimated_flight_time:'5h',fuel:'12000'});
 assert((await request('save',{state})).ok);
 const browser=await chromium.launch({headless:true,...(process.env.RFS_TEST_BROWSER?{channel:process.env.RFS_TEST_BROWSER}:{})});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[],remote=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(!r.url().startsWith(base+'/'))remote.push(r.url());});
  await page.exposeFunction('testRequest',async(id,method,payload)=>{const envelope=await request(method,JSON.parse(payload));await page.evaluate(({id,envelope})=>window.androidReply(id,envelope),{id,envelope});});
  await page.addInitScript(()=>window.Android={request:(id,method,payload)=>window.testRequest(id,method,payload)});
  await page.goto(base+'/index.html');await page.locator('#flight-callsign').waitFor();
  await go(page,'finder');
  await page.locator('#finder-route_catalog').check();await page.locator('#finder-airline').fill('AFR');
  await page.locator('#search').click();await page.waitForFunction(()=>finderResponse&&!finderBusy);
  assert(await page.evaluate(()=>finderRows.length>0&&finderRows.every(r=>r.duration_min===null&&r.aircraft===null)));
  const text=await page.locator('#result-0').textContent();
  assert.match(text,/Unknown duration/);assert.match(text,/Unknown aircraft/);assert(!text.includes('0 min'));
  await page.locator('#result-0 [data-action="finder-details"]').click();
  await page.waitForFunction(()=>document.querySelector('#finder-detail-0').textContent.includes('Airline inferred'));
  assert(!(await page.locator('#finder-detail-0').textContent()).includes('Durée'));
  await page.locator('#result-0 [data-action="finder-use"]').click();await page.locator('#flight-callsign').waitFor();
  assert.equal(await page.locator('#flight-aircraft').inputValue(),'Airbus A350-900');
  assert.equal(await page.evaluate(()=>model.state.flight.estimated_flight_time),'5h');
  assert.equal(await page.evaluate(()=>model.state.flight.fuel),'12000');
  const failedSave=await page.evaluate(async()=>{
   const previousFlush=flushEdits,previousRpc=rpc;let finishes=0;
   flushEdits=async()=>{throw new Error('Forced test save failure');};
   rpc=async(method,args)=>{if(method==='native.finish'){finishes++;return{};}return previousRpc(method,args);};
   try{goBack();await new Promise(resolve=>setTimeout(resolve,30));return{finishes,fuel:model.state.flight.fuel};}
   finally{flushEdits=previousFlush;rpc=previousRpc;}
  });
  assert.equal(failedSave.finishes,0);assert.equal(failedSave.fuel,'12000');
  await page.reload();await page.locator('#flight-callsign').waitFor();
  assert.equal(await page.evaluate(()=>model.state.flight.selected_flight.status),'OBSERVED_ROUTE');
  assert.equal(await page.evaluate(()=>model.state.flight.fuel),'12000');
  assert.deepEqual(errors,[]);assert.deepEqual(remote,[]);
  console.log('PASS recent route UI: unknown fields, English details, mapping, restart, no remote requests');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
