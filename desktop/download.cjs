'use strict';
const fs = require('node:fs');
const fsp = fs.promises;
const {createHash} = require('node:crypto');
const {pipeline} = require('node:stream/promises');
const {Readable, Transform} = require('node:stream');
const path = require('node:path');
async function sha256(file) {
  const hash = createHash('sha256');
  for await (const chunk of fs.createReadStream(file)) hash.update(chunk);
  return hash.digest('hex');
}
async function validFile(file, model) {
  try { return (await fsp.stat(file)).size === model.bytes && await sha256(file) === model.sha256; }
  catch (e) { if(e.code === 'ENOENT') return false; throw e; }
}
async function secureFetch(url, options, fetcher=fetch) {
  for(let n=0;n<8;n++) {
    if(new URL(url).protocol !== 'https:') throw Error('Model downloads require HTTPS.');
    const r=await fetcher(url,{...options,redirect:'manual'});
    if([301,302,303,307,308].includes(r.status)) {
      const next=r.headers.get('location');await r.body?.cancel();
      if(!next)throw Error('Invalid download redirect.');url=new URL(next,url).href;continue;
    }
    return r;
  }
  throw Error('Too many model download redirects.');
}
async function downloadModel(model, file, progress, signal, fetcher=fetch) {
  await fsp.mkdir(path.dirname(file),{recursive:true});
  if(await validFile(file,model))return;
  const partial=file+'.part';
  let offset=await fsp.stat(partial).then(s=>s.size).catch(e=>{if(e.code==='ENOENT')return 0;throw e;});
  if(offset===model.bytes) {
    if(await sha256(partial)===model.sha256){await fsp.rename(partial,file);return;}
    await fsp.rm(partial);offset=0;
  }
  if(offset>model.bytes){await fsp.rm(partial);offset=0;}
  const r=await secureFetch(model.url,{signal,headers:offset?{Range:`bytes=${offset}-`}:{}},fetcher);
  if(![200,206].includes(r.status)){await r.body?.cancel();throw Error(`Speech model download failed (HTTP ${r.status}). Retry when connected.`);}
  if(r.status===200)offset=0;
  else {
    const range=/^bytes (\d+)-(\d+)\/(\d+)$/.exec(r.headers.get('content-range')||'');
    if(!range||Number(range[1])!==offset||Number(range[3])!==model.bytes){await r.body?.cancel();throw Error('Unexpected download range. Partial data was not changed.');}
  }
  let received=offset;
  const meter=new Transform({transform(chunk,_enc,cb){
    received+=chunk.length;
    if(received>model.bytes)return cb(Error('Speech model exceeded expected size.'));
    progress(received,model.bytes);cb(null,chunk);
  }});
  await pipeline(Readable.fromWeb(r.body),meter,fs.createWriteStream(partial,{flags:offset?'a':'w',mode:0o600}),{signal});
  if(received!==model.bytes)throw Error('Download incomplete. Click Retry to resume.');
  progress(received,model.bytes,'Verifying download…');
  if(await sha256(partial)!==model.sha256){await fsp.rm(partial);throw Error('Speech model checksum failed. Click Retry to download a fresh copy.');}
  await fsp.rename(partial,file);
}
async function readNDJSON(body, callback) {
  const decoder=new TextDecoder();let pending='';
  for await(const chunk of body){
    pending+=decoder.decode(chunk,{stream:true});
    if(pending.length>2*1024*1024)throw Error('Unexpected model service response.');
    let n;while((n=pending.indexOf('\n'))>=0){const line=pending.slice(0,n).trim();pending=pending.slice(n+1);if(line)callback(JSON.parse(line));}
  }
  pending+=decoder.decode();if(pending.trim())callback(JSON.parse(pending));
}
module.exports={sha256,validFile,secureFetch,downloadModel,readNDJSON};
