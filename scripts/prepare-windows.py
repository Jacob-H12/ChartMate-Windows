"""Fetch native x64 distributions, verify release digests, preserve vendor layouts."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'runtime'
CACHE=ROOT/'.build/downloads'
FIXED={
 'whisper':{'url':'https://github.com/ggml-org/whisper.cpp/releases/download/v1.7.6/whisper-bin-x64.zip','sha256':'0d2eca299c248f965bd0341bcb219db4b433c7f0c0ce2200d4df85765e8156a9'},
 'ollama':{'url':'https://github.com/ollama/ollama/releases/download/v0.40.16/ollama-windows-amd64.zip','sha256':'50fcf5ad54277f2fa5d173ebfc93bcb017adbc0c9ef2314daabc96ca9e6aa64e'}
}

def digest(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def download(url,dest,sha=None):
 if dest.exists():
  if not sha or digest(dest)==sha:return
  dest.unlink()
 partial=dest.with_suffix(dest.suffix+'.part')
 # curl is available in the supported Windows releases. An incomplete download is never installed.
 subprocess.run(['curl.exe','--fail','--location','--retry','3','--proto','=https','--proto-redir','=https','--output',str(partial),url],check=True)
 if sha and digest(partial)!=sha:
  partial.unlink();raise RuntimeError('Checksum mismatch: '+dest.name)
 partial.replace(dest)

def safe_extract(archive,target):
 with zipfile.ZipFile(archive) as z:
  for item in z.infolist():
   p=PurePosixPath(item.filename.replace('\\','/'))
   if p.is_absolute() or '..' in p.parts or any(':' in x for x in p.parts):raise ValueError('Unsafe ZIP path: '+item.filename)
  z.extractall(target)

def resolve_assets():
 lock=CACHE/'windows-native-lock.json'
 if lock.exists():return json.loads(lock.read_text())
 assets=json.loads(json.dumps(FIXED))
 url='https://api.github.com/repos/FFmpeg-Builds/FFmpeg-Builds/releases/tags/latest'
 req=urllib.request.Request(url,headers={'User-Agent':'ChartMate-build'})
 with urllib.request.urlopen(req,timeout=60) as r:release=json.load(r)
 name='ffmpeg-n8.1-latest-win64-lgpl-shared-8.1.zip'
 a=next(a for a in release['assets'] if a['name']==name)
 sha=a.get('digest','')
 if not sha.startswith('sha256:'):raise RuntimeError('FFmpeg release has no SHA-256 digest; refusing an unchecked executable download.')
 assets['ffmpeg']={'url':a['browser_download_url'],'sha256':sha[7:],'release_id':release['id'],'asset_id':a['id']}
 lock.write_text(json.dumps(assets,indent=2));return assets

def one_exe(folder,name):
 found=list(folder.rglob(name))
 if len(found)!=1:raise RuntimeError(f'Unexpected distribution: expected one {name}, found {len(found)}')
 return found[0].relative_to(RUNTIME).as_posix()

def main():
 if sys.platform!='win32':raise SystemExit('Run this build step on Windows x64.')
 for p in (CACHE,RUNTIME,RUNTIME/'licenses'):p.mkdir(parents=True,exist_ok=True)
 assets=resolve_assets();stamp=RUNTIME/'windows-native-build.json'
 if not stamp.exists() or json.loads(stamp.read_text()).get('assets')!=assets:
  for name,asset in assets.items():
   archive=CACHE/(name+'-'+asset['sha256'][:12]+'.zip')
   print('Preparing '+name,flush=True);download(asset['url'],archive,asset['sha256'])
   target=RUNTIME/name
   if target.exists():shutil.rmtree(target)
   target.mkdir();safe_extract(archive,target)
  layout={name:one_exe(RUNTIME/name,exe) for name,exe in [('whisper','whisper-cli.exe'),('ffmpeg','ffmpeg.exe'),('ollama','ollama.exe')]}
  (RUNTIME/'layout.json').write_text(json.dumps(layout,indent=2))
  stamp.write_text(json.dumps({'assets':assets},indent=2))
 download('https://aka.ms/vs/17/release/vc_redist.x64.exe',RUNTIME/'vc_redist.x64.exe')
 notices={
  'whisper-MIT.txt':'https://raw.githubusercontent.com/ggml-org/whisper.cpp/v1.7.6/LICENSE',
  'ollama-MIT.txt':'https://raw.githubusercontent.com/ollama/ollama/v0.40.16/LICENSE',
  'Qwen3-Apache-2.0.txt':'https://huggingface.co/Qwen/Qwen3-4B/raw/main/LICENSE'
 }
 for name,url in notices.items():download(url,RUNTIME/'licenses'/name)
 shutil.copy2(CACHE/'windows-native-lock.json',RUNTIME/'licenses/windows-native-lock.json')
 print('Native downloads ready. Microsoft signature verification runs in the build script.')

if __name__=='__main__':main()
