"""Run native Windows smoke tests on the exact bundled runtime, without PATH helpers."""
import json
import os
from pathlib import Path
import queue
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import wave

ROOT=Path(__file__).resolve().parents[1]

def pe_machine(file):
 with open(file,'rb') as f:
  if f.read(2)!=b'MZ':raise ValueError('Not a Windows executable: '+str(file))
  f.seek(0x3c);offset=struct.unpack('<I',f.read(4))[0];f.seek(offset)
  if f.read(4)!=b'PE\0\0':raise ValueError('Invalid PE signature: '+str(file))
  return struct.unpack('<H',f.read(2))[0]

def main():
 if sys.platform!='win32':raise SystemExit('Run this audit on Windows x64.')
 runtime=Path(sys.argv[1]).resolve();layout=json.loads((runtime/'layout.json').read_text())
 backend=runtime/'backend/chartmate-server.exe'
 for file in [backend]+[runtime/layout[k] for k in ('whisper','ffmpeg','ollama')]:
  if pe_machine(file)!=0x8664:raise RuntimeError('Wrong executable architecture: '+str(file))
 opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
 def get(url,headers=None):
  with opener.open(urllib.request.Request(url,headers=headers or {}),timeout=2) as r:return json.load(r)
 with tempfile.TemporaryDirectory(prefix='chartmate-audit-') as tmp:
  tmp=Path(tmp);(tmp/'home').mkdir()
  env={k:v for k,v in os.environ.items() if not k.startswith(('CHARTMATE_','WHISPER_','OLLAMA_','PYTHON'))}
  system=Path(os.environ['SystemRoot'])
  env.update(PATH=str(system/'System32')+';'+str(system),HOME=str(tmp/'home'),USERPROFILE=str(tmp/'home'),CHARTMATE_PARENT_PID=str(os.getpid()))
  flags={'env':env,'creationflags':subprocess.CREATE_NO_WINDOW}
  subprocess.run([runtime/layout['whisper'],'--help'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30,**flags)
  for ext in ('webm','m4a'):
   out=tmp/(ext+'.wav')
   subprocess.run([runtime/layout['ffmpeg'],'-v','error','-i',ROOT/f'tests/fixtures/tone.{ext}','-ar','16000','-ac','1','-c:a','pcm_s16le',out],check=True,timeout=30,**flags)
   with wave.open(str(out)) as w:assert w.getframerate()==16000 and w.getnchannels()==1 and w.getnframes()>10000
  with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  children=[]
  try:
   native_env={**env,'OLLAMA_HOST':f'127.0.0.1:{port}','OLLAMA_MODELS':str(tmp/'models'),'OLLAMA_NO_CLOUD':'1'}
   p=subprocess.Popen([backend,'--supervise',runtime/layout['ollama'],'serve'],env=native_env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW);children.append(p)
   for _ in range(100):
    if p.poll() is not None:raise RuntimeError('Bundled Ollama exited. Check runtime DLLs and Windows version.')
    try:get(f'http://127.0.0.1:{port}/api/tags');break
    except (OSError,urllib.error.URLError):time.sleep(.3)
   else:raise RuntimeError('Bundled Ollama startup timed out.')
   token='chartmate-audit-token'
   server_env={**env,'CHARTMATE_PORT':'0','CHARTMATE_TOKEN':token,'CHARTMATE_DESKTOP':'1','CHARTMATE_FFMPEG':str(runtime/layout['ffmpeg']),'CHARTMATE_WHISPER_CLI':str(runtime/layout['whisper'])}
   p=subprocess.Popen([backend],env=server_env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW);children.append(p)
   ready=queue.Queue()
   threading.Thread(target=lambda:ready.put(p.stdout.readline()),daemon=True).start()
   try:line=ready.get(timeout=30)
   except queue.Empty:raise RuntimeError('Frozen Python startup timed out.')
   if not line:raise RuntimeError('Frozen Python exited before readiness.')
   serverport=json.loads(line)['port'];url=f'http://127.0.0.1:{serverport}/api/status'
   assert get(url,{'X-ChartMate-Desktop':token})['token']==token
   try:get(url)
   except urllib.error.HTTPError as e:assert e.code==403
   else:raise AssertionError('Unauthenticated desktop request was accepted.')
  finally:
   for p in children:
    if p.poll() is None:p.terminate()
   for p in children:p.wait(timeout=10)
 print('PASS: x64 PE files, Whisper startup, WebM/MP4 decoding, private Ollama, frozen Python and API access control.')
 print('Still required: installer, GUI, microphone, real model inference and offline tests on a clean Windows PC.')

if __name__=='__main__':main()
