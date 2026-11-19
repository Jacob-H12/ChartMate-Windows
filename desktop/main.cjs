'use strict';
const {app,BrowserWindow,ipcMain,session,dialog,Menu,shell,systemPreferences,powerSaveBlocker}=require('electron');
const path=require('node:path');
const fs=require('node:fs');const fsp=fs.promises;
const net=require('node:net');const {spawn}=require('node:child_process');
const {randomBytes}=require('node:crypto');const {pathToFileURL}=require('node:url');
const {validFile,downloadModel,readNDJSON}=require('./download.cjs');
const models=require('./models.json');
const IS_WIN=process.platform==='win32';
const executable=name=>name+(IS_WIN?'.exe':'');
let nativeLayout;
let win,origin='',busy=false,shutting=false,aborter,ollamaPort,blocker;
let latest={phase:'checking',message:'Checking local models…'};
const processes=new Set();const token=randomBytes(32).toString('hex');
const setupURL=pathToFileURL(path.join(__dirname,'setup.html')).href;
const runtime=app.isPackaged?path.join(process.resourcesPath,'runtime'):path.join(__dirname,'../runtime');
let modelDir,speechPath;
function send(s){latest=s;if(win&&!win.isDestroyed()&&win.webContents.getURL()===setupURL)win.webContents.send('setup:status',s);}
function fail(e){send({phase:'error',heading:'Setup needs attention',message:e.message,detail:'Check your connection and free disk space, then click Retry. Your existing models are kept.'});}
function envForChild(){
  const env={...process.env};
  for(const key of Object.keys(env))if(/^(OLLAMA_|WHISPER_|CHARTMATE_|DYLD_|PYTHON)/.test(key)||['HTTP_PROXY','ALL_PROXY','http_proxy','all_proxy'].includes(key))delete env[key];
  return env;
}
function child(exe,args,env){
  const backend=path.join(runtime,'backend',executable('chartmate-server'));
  const wrapped=exe!==backend;
  const p=spawn(wrapped?backend:exe,wrapped?['--supervise',exe,...args]:args,{env:{...envForChild(),...env,CHARTMATE_PARENT_PID:String(process.pid)},cwd:path.dirname(exe),stdio:['ignore','pipe','pipe'],detached:!IS_WIN,windowsHide:true});
  processes.add(p);p.stderr.on('data',()=>{}); // Never persist transcripts or model prompts in logs.
  p.on('error',()=>{});
  p.on('exit',()=>{
    if(!shutting&&origin&&win&&!win.isDestroyed()){
      dialog.showMessageBox(win,{type:'error',message:'A local service stopped.',detail:'Export your current work before quitting. Reopen ChartMate to restart the services.'}).catch(()=>{});
    }
  });
  return p;
}
async function stopServices(){
  aborter?.abort();
  const children=[...processes];processes.clear();
  const signal=(p,s)=>{if(p.pid&&p.exitCode===null&&!p.signalCode)try{if(IS_WIN)p.kill();else process.kill(-p.pid,s);}catch(e){if(e.code!=='ESRCH')throw e;}};
  for(const p of children)signal(p,'SIGTERM');
  await new Promise(r=>setTimeout(r,500));
  for(const p of children)signal(p,'SIGKILL');
}
function freePort(){return new Promise((resolve,reject)=>{const s=net.createServer();s.on('error',reject);s.listen(0,'127.0.0.1',()=>{const p=s.address().port;s.close(()=>resolve(p));});});}
async function localFetch(url,options={}){return fetch(url,{...options,redirect:'error',signal:options.signal||AbortSignal.timeout(10000)});}
async function startOllama(){
  ollamaPort=await freePort();
  const config=JSON.parse(await fsp.readFile(path.join(runtime,'layout.json'),'utf8'));nativeLayout=config;
  const exe=path.resolve(runtime,config.ollama);
  if(!exe.startsWith(runtime+path.sep))throw Error('Invalid bundled model service path.');
  const engineHome=path.join(app.getPath('userData'),'engine-home');await fsp.mkdir(engineHome,{recursive:true});
  const p=child(exe,['serve'],{HOME:engineHome,USERPROFILE:engineHome,OLLAMA_HOST:`127.0.0.1:${ollamaPort}`,OLLAMA_MODELS:path.join(modelDir,'ollama'),OLLAMA_NO_CLOUD:'1',OLLAMA_KEEP_ALIVE:'0',OLLAMA_MAX_LOADED_MODELS:'1',OLLAMA_NUM_PARALLEL:'1'});
  p.stdout.on('data',()=>{});
  let spawnError;p.on('error',e=>{spawnError=e;});
  for(let n=0;n<120;n++){
    if(shutting)throw Error('Closing ChartMate.');
    if(spawnError)throw Error('Bundled model service could not start: '+spawnError.message);
    if(p.exitCode!==null||p.signalCode)throw Error('Bundled model service stopped during startup. Reinstall ChartMate or check available memory.');
    try{const r=await localFetch(`http://127.0.0.1:${ollamaPort}/api/version`,{signal:AbortSignal.timeout(700)});if(r.ok){await r.json();return;}}catch{}
    await new Promise(r=>setTimeout(r,250));
  }
  throw Error('The local model service did not become ready.');
}
async function hasTextModel(){
  const r=await localFetch(`http://127.0.0.1:${ollamaPort}/api/tags`);
  if(!r.ok)throw Error('Cannot inspect installed text models.');
  return (await r.json()).models?.some(m=>m.name===models.text.tag)||false;
}
async function pullText(){
  let success=false;
  const r=await localFetch(`http://127.0.0.1:${ollamaPort}/api/pull`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:models.text.tag,stream:true}),signal:aborter.signal});
  if(!r.ok)throw Error('Text model download failed. Check your connection and retry.');
  await readNDJSON(r.body,s=>{
    if(s.error)throw Error(s.error);
    if(s.status==='success')success=true;
    send({phase:'downloading',heading:'Downloading text model',message:s.status||'Preparing Qwen3…',percent:s.total?Math.round(100*(s.completed||0)/s.total):undefined,detail:s.total?`${((s.completed||0)/1e9).toFixed(2)} / ${(s.total/1e9).toFixed(2)} GB (current layer)`:''});
  });
  if(!success||!await hasTextModel())throw Error('Text model download did not finish. Click Retry.');
}
async function launchBackend(){
  send({phase:'starting',heading:'Starting ChartMate',message:'Models are ready. Opening your workspace…'});
  const p=child(path.join(runtime,'backend',executable('chartmate-server')),[],{
    CHARTMATE_PORT:'0',CHARTMATE_TOKEN:token,CHARTMATE_DESKTOP:'1',CHARTMATE_OLLAMA_PORT:String(ollamaPort),
    CHARTMATE_LLM_MODEL:models.text.tag,WHISPER_MODEL:speechPath,
    WHISPER_CPP_DIR:path.dirname(path.join(runtime,nativeLayout.whisper)),CHARTMATE_WHISPER_CLI:path.join(runtime,nativeLayout.whisper),
    CHARTMATE_FFMPEG:path.join(runtime,nativeLayout.ffmpeg)
  });
  const port=await new Promise((resolve,reject)=>{
    let buf='';const timer=setTimeout(()=>reject(Error('ChartMate service startup timed out.')),30000);
    p.once('error',e=>{clearTimeout(timer);reject(e);});
    p.once('exit',()=>{clearTimeout(timer);reject(Error('ChartMate service could not start.'));});
    p.stdout.on('data',chunk=>{
      buf+=chunk.toString();if(buf.length>65536){clearTimeout(timer);reject(Error('Invalid service startup response.'));return;}
      let n;while((n=buf.indexOf('\n'))>=0){const line=buf.slice(0,n);buf=buf.slice(n+1);try{const v=JSON.parse(line);if(v.event==='ready'&&Number.isInteger(v.port)&&v.port>0&&v.port<65536){clearTimeout(timer);resolve(v.port);}}catch{}}
    });
  });
  const candidate=`http://127.0.0.1:${port}`;
  const r=await localFetch(candidate+'/api/status',{headers:{'X-ChartMate-Desktop':token}});
  const state=await r.json();if(!r.ok||state.token!==token||!state.ready)throw Error(state.problems?.join('\n')||'Local service verification failed.');
  origin=candidate;await win.loadURL(origin+'/');
}
async function prepare(download=false){
  if(busy)return;busy=true;aborter=new AbortController();
  blocker=powerSaveBlocker.start('prevent-app-suspension');
  try{
    send({phase:'checking',message:'Checking local models. Large files may take a moment to verify…'});
    if(!ollamaPort)await startOllama();
    const speechOK=await validFile(speechPath,models.speech);const textOK=await hasTextModel();
    if((!speechOK||!textOK)&&!download){send({phase:'needs-download',heading:'One-time model setup',message:'Download the local models to get started. No accounts or API keys are needed.',detail:'Downloads can be retried after an interruption.'});return;}
    if(!speechOK||!textOK){
      const st=await fsp.statfs(modelDir);if(st.bavail*st.bsize<models.minimumFreeBytes)throw Error('At least 7 GB of free disk space is required for setup.');
      if(!speechOK)await downloadModel(models.speech,speechPath,(done,total,message)=>send({phase:'downloading',heading:'Downloading speech model',message:message||'Whisper medium.en',percent:Math.round(100*done/total),detail:`${(done/1e9).toFixed(2)} / ${(total/1e9).toFixed(2)} GB`}),aborter.signal);
      if(!textOK)await pullText();
    }
    await launchBackend();
  }catch(e){if(!shutting){origin='';await stopServices();ollamaPort=undefined;fail(e);}}
  finally{busy=false;if(blocker!==undefined&&powerSaveBlocker.isStarted(blocker))powerSaveBlocker.stop(blocker);}
}
function setupSender(e){return !!win&&e.sender===win.webContents&&e.senderFrame?.url===setupURL;}
if(!app.requestSingleInstanceLock())app.quit();
else{
  app.on('second-instance',()=>{if(win){if(win.isMinimized())win.restore();win.focus();}});
  app.whenReady().then(async()=>{
    if(!IS_WIN||process.arch!=='x64'){dialog.showErrorBox('Unsupported platform','This build requires Windows 10 22H2 or Windows 11 on an Intel/AMD x64 PC.');app.quit();return;}
    modelDir=path.join(app.getPath('userData'),'models');await fsp.mkdir(modelDir,{recursive:true});speechPath=path.join(modelDir,models.speech.file);
    win=new BrowserWindow({width:1280,height:900,minWidth:820,minHeight:650,title:'ChartMate',backgroundColor:'#f4f7f3',webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true}});
    const ses=session.defaultSession;
    ses.webRequest.onBeforeSendHeaders((details,cb)=>{
      const headers={...details.requestHeaders};
      if(origin&&details.url.startsWith(origin+'/'))headers['X-ChartMate-Desktop']=token;
      cb({requestHeaders:headers});
    });
    ses.setPermissionCheckHandler((wc,permission,_requestingOrigin,details)=>{
      const trusted=wc===win.webContents&&origin&&wc.getURL().startsWith(origin+'/');
      return !!trusted&&permission==='media'&&(!details.mediaType||details.mediaType==='audio');
    });
    ses.setPermissionRequestHandler(async(wc,permission,cb,details)=>{
      const trusted=wc===win.webContents&&origin&&wc.getURL().startsWith(origin+'/')&&details.isMainFrame!==false;
      if(!trusted||permission!=='media'||details.mediaTypes?.some(t=>t!=='audio'))return cb(false);
      try{cb(IS_WIN?true:await systemPreferences.askForMediaAccess('microphone'));}catch{cb(false);}
    });
    ses.on('will-download',(_event,item)=>{
      item.setSaveDialogOptions({title:'Save ChartMate Export',defaultPath:path.join(app.getPath('documents'),path.basename(item.getFilename()))});
    });
    win.webContents.setWindowOpenHandler(()=>({action:'deny'}));
    win.webContents.on('will-navigate',(e,url)=>{if(url!==setupURL&&url!==origin+'/')e.preventDefault();});
    win.webContents.on('will-prevent-unload',e=>{
      const choice=dialog.showMessageBoxSync(win,{type:'question',buttons:['Keep Working','Discard & Close'],defaultId:0,cancelId:0,message:'Leave this workspace?',detail:'Unsaved recordings, transcripts and table changes will be lost. Export anything you want to keep first.'});
      if(choice===1)e.preventDefault();
    });
    win.webContents.on('did-finish-load',()=>{if(win.webContents.getURL()===setupURL)send(latest);});
    ipcMain.handle('setup:start',e=>{if(setupSender(e))void prepare(true);});
    ipcMain.handle('setup:retry',e=>{if(setupSender(e))void prepare(true);});
    ipcMain.handle('setup:folder',e=>{if(setupSender(e))return shell.openPath(modelDir);});
    Menu.setApplicationMenu(Menu.buildFromTemplate([
      {label:'ChartMate',submenu:[{role:'about'},{label:'Model Folder',click:()=>shell.openPath(modelDir)},{type:'separator'},{role:'quit'}]},
      {role:'editMenu'},{label:'View',submenu:[{role:'resetZoom'},{role:'zoomIn'},{role:'zoomOut'},{role:'togglefullscreen'}]},
      {label:'Help',submenu:[{label:'Microphone Permissions',click:()=>shell.openExternal('ms-settings:privacy-microphone')},{label:'Third-party Notices',click:()=>shell.openPath(app.isPackaged?path.join(process.resourcesPath,'THIRD_PARTY.md'):path.join(__dirname,'../THIRD_PARTY.md'))}]}
    ]));
    await win.loadURL(setupURL);await prepare(false);
  }).catch(e=>{dialog.showErrorBox('ChartMate could not open',e.message);app.quit();});
  app.on('window-all-closed',()=>app.quit());
  app.on('before-quit',e=>{
    // Let the window's unsaved-work confirmation run before terminating services.
    if(win&&!win.isDestroyed()){e.preventDefault();win.close();return;}
    if(!shutting){e.preventDefault();shutting=true;void stopServices().finally(()=>app.quit());}
  });
}
