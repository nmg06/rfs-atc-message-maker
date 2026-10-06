// Each scenario has an isolated temporary profile and local server.
const {spawn}=require('node:child_process');const path=require('node:path');
const root=path.resolve(__dirname,'../..');
(async()=>{
 for(const test of process.argv.slice(2).length?process.argv.slice(2):['ui_browser.cjs','experience_browser.cjs','help_browser.cjs','web_browser.cjs','updates_backup_browser.cjs','finder_exclusions_browser.cjs','compatibility_browser.cjs']){
  const server=spawn(process.env.RFS_TEST_PYTHON||'python',[path.join(__dirname,'ui_server.py')],{cwd:root,windowsHide:true});
  let buffer='';server.stderr.on('data',data=>process.stderr.write(data));
  try{
   const port=await new Promise((resolve,reject)=>{server.stdout.on('data',data=>{buffer+=data;const line=buffer.split('\n')[0];if(line.includes('}')){try{resolve(JSON.parse(line).port);}catch(e){reject(e);}}});server.on('exit',code=>reject(Error('Server exited: '+code)));});
   const code=await new Promise(resolve=>{const child=spawn(process.execPath,[path.join(__dirname,test),String(port)],{cwd:root,env:process.env,stdio:'inherit',windowsHide:true});child.on('exit',resolve);});
   if(code!==0)throw Error(test+' failed: '+code);
  }finally{server.kill();}
 }
})().catch(e=>{console.error(e);process.exit(1);});
