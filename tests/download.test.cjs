'use strict';
const test=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs/promises');const os=require('node:os');const path=require('node:path');const {createHash}=require('node:crypto');
const {downloadModel,validFile,readNDJSON,secureFetch}=require('../desktop/download.cjs');
const data=Buffer.from('synthetic-model-data');
const model={url:'https://models.example/test',bytes:data.length,sha256:createHash('sha256').update(data).digest('hex')};
async function temp(t){const dir=await fs.mkdtemp(path.join(os.tmpdir(),'chartmate-'));t.after(()=>fs.rm(dir,{recursive:true,force:true}));return path.join(dir,'model.bin');}
test('download verifies hash and atomically installs; installed model works offline',async t=>{
 const file=await temp(t);let calls=0;
 await downloadModel(model,file,()=>{},undefined,async()=>{calls++;return new Response(data);});
 assert.equal(await validFile(file,model),true);
 await downloadModel(model,file,()=>{},undefined,async()=>{throw Error('offline');});assert.equal(calls,1);
});
test('resume interrupted download validates range and combines only remaining bytes',async t=>{
 const file=await temp(t);await fs.writeFile(file+'.part',data.subarray(0,7));
 await downloadModel(model,file,()=>{},undefined,async(_url,opts)=>{assert.equal(opts.headers.Range,'bytes=7-');return new Response(data.subarray(7),{status:206,headers:{'content-range':`bytes 7-${data.length-1}/${data.length}`}});});
 assert.deepEqual(await fs.readFile(file),data);
});
test('server ignoring Range replaces partial file instead of appending',async t=>{
 const file=await temp(t);await fs.writeFile(file+'.part',data.subarray(0,7));
 await downloadModel(model,file,()=>{},undefined,async()=>new Response(data));assert.deepEqual(await fs.readFile(file),data);
});
test('bad checksum is rejected and corrupt partial removed',async t=>{
 const file=await temp(t);await assert.rejects(downloadModel(model,file,()=>{},undefined,async()=>new Response(Buffer.alloc(data.length))),/checksum/);
 await assert.rejects(fs.stat(file),{code:'ENOENT'});await assert.rejects(fs.stat(file+'.part'),{code:'ENOENT'});
});
test('bad range cannot corrupt existing partial bytes',async t=>{
 const file=await temp(t);await fs.writeFile(file+'.part',data.subarray(0,7));
 await assert.rejects(downloadModel(model,file,()=>{},undefined,async()=>new Response(data.subarray(7),{status:206,headers:{'content-range':`bytes 0-${data.length-1}/${data.length}`}})),/range/);
 assert.deepEqual(await fs.readFile(file+'.part'),data.subarray(0,7));
});
test('HTTP errors do not install a model',async t=>{
 const file=await temp(t);await assert.rejects(downloadModel(model,file,()=>{},undefined,async()=>new Response('bad',{status:503})),/HTTP 503/);await assert.rejects(fs.stat(file),{code:'ENOENT'});
});
test('redirects cannot downgrade TLS',async()=>{
 await assert.rejects(secureFetch('https://models.example/a',{},async()=>new Response(null,{status:302,headers:{location:'http://models.example/a'}})),/HTTPS/);
});
test('stream parser handles split JSON, unicode and final line without newline',async()=>{
 const raw=Buffer.from('{"status":"准备"}\n{"status":"success"}');const events=[];
 async function* stream(){for(let i=0;i<raw.length;i+=2)yield raw.subarray(i,i+2);}
 await readNDJSON(stream(),e=>events.push(e));assert.deepEqual(events,[{status:'准备'},{status:'success'}]);
});
test('corrupt NDJSON is rejected',async()=>{
 async function* stream(){yield Buffer.from('{oops}\n');}await assert.rejects(readNDJSON(stream(),()=>{}),SyntaxError);
});
