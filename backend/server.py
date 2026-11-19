#!/usr/bin/env python3
"""Loopback-only recording transcription. Python 3.9+, stdlib only."""
from extraction import FIELDS, ALERTS
from native_subprocess import run_native
from local_llm import extract_local, MODEL as LLM_MODEL
import json, os, secrets, shutil, subprocess, tempfile, threading, time, wave
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
ROOT = Path(__file__).resolve().parent
WHISPER = Path(os.environ.get('WHISPER_CPP_DIR', str(ROOT.parent / 'whisper.cpp'))).expanduser().resolve()
MODEL = Path(os.environ.get('WHISPER_MODEL', str(WHISPER / 'models/ggml-base.en.bin'))).expanduser().resolve()
CLI = Path(os.environ.get('CHARTMATE_WHISPER_CLI', str(WHISPER / 'build/bin/whisper-cli')))
FFMPEG = os.environ.get('CHARTMATE_FFMPEG') or shutil.which('ffmpeg')
PORT = int(os.environ.get('CHARTMATE_PORT', '8765'))
TOKEN = os.environ.get('CHARTMATE_TOKEN') or secrets.token_urlsafe(32)
DESKTOP = os.environ.get('CHARTMATE_DESKTOP') == '1'
LOCK = threading.Lock()
MAX_BYTES = 128 * 1024 * 1024
MAX_SECONDS = 1800
PROCESS_FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

def status():
    problems = []
    if not CLI.is_file() or not os.access(CLI, os.X_OK): problems.append('whisper-cli executable not found: ' + str(CLI))
    if not MODEL.is_file(): problems.append('Model not found: ' + str(MODEL))
    if not FFMPEG or not os.access(FFMPEG, os.X_OK): problems.append('Audio converter missing. Reinstall ChartMate.' if DESKTOP else 'FFmpeg not found. Run brew install ffmpeg in Terminal.')
    return dict(ready=not problems, problems=problems, model=MODEL.name, extraction_model=LLM_MODEL, token=TOKEN, max_seconds=MAX_SECONDS, fields=[dict(group=g, key=k, label=l, alert=ALERTS.get(k,"")) for g,k,l,_ in FIELDS])

def transcribe(payload):
    with tempfile.TemporaryDirectory(prefix='chartmate_') as tmp:
        tmp = Path(tmp); source = tmp/'recording'; wav = tmp/'audio.wav'; output = tmp/'result'
        source.write_bytes(payload)
        result = run_native([FFMPEG, '-nostdin','-hide_banner','-loglevel','error','-y','-i',str(source),'-t',str(MAX_SECONDS + 1),'-ar','16000','-ac','1','-c:a','pcm_s16le',str(wav)], capture_output=True, creationflags=PROCESS_FLAGS, timeout=180)
        if result.returncode: raise ValueError('Audio decoding failed. Record again or try another browser.')
        with wave.open(str(wav),'rb') as w:
            duration=w.getnframes()/w.getframerate()
        if duration < .4: raise ValueError('Recording too short. Record at least one second.')
        if duration > MAX_SECONDS + .5: raise ValueError('Recording exceeds 30 minutes. Split it into shorter recordings.')
        start=time.monotonic(); texts=[]; segments=[]
        # Bound each Whisper invocation to 120 seconds of audio; preserve all samples.
        with wave.open(str(wav),'rb') as audio:
            rate=audio.getframerate(); frames=rate*120; offset=0
            while True:
                data=audio.readframes(frames)
                if not data: break
                index=len(segments); piece=tmp/f'part_{index}.wav'; output=tmp/f'part_{index}'
                with wave.open(str(piece),'wb') as w:
                    w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(data)
                result=run_native([str(CLI),'-m',str(MODEL),'-f',str(piece),'-l','en','-t','4','-otxt','-of',str(output)],cwd=str(WHISPER),capture_output=True,creationflags=PROCESS_FLAGS,timeout=900)
                if result.returncode or not output.with_suffix('.txt').exists():
                    raise RuntimeError(f'Transcription failed in segment {index+1}. Download the audio and retry.')
                text=output.with_suffix('.txt').read_text(encoding='utf-8').strip()
                seconds=len(data)/(2*rate)
                segments.append(dict(start_seconds=offset,end_seconds=round(offset+seconds,2),text=text))
                texts.append(text);offset+=seconds
                piece.unlink();output.with_suffix('.txt').unlink()
        return dict(text='\n'.join(texts), segments=segments, duration_seconds=round(duration,2), processing_seconds=round(time.monotonic()-start,2), model=MODEL.name)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass
    def allowed(self):
        return self.headers.get('Host') in (f'127.0.0.1:{PORT}', f'localhost:{PORT}') and (not DESKTOP or secrets.compare_digest(self.headers.get('X-ChartMate-Desktop',''),TOKEN))
    def reply(self, code, body, content_type='application/json; charset=utf-8'):
        if not isinstance(body,bytes): body=json.dumps(body,ensure_ascii=False).encode()
        self.send_response(code);self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):pass
    def do_GET(self):
        if not self.allowed(): return self.reply(403,{'error':'Local access only'})
        path=urlsplit(self.path).path
        if path=='/api/status':return self.reply(200,status())
        files={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/table.js':('table.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8')}
        if path not in files:return self.reply(404,{'error':'Not found'})
        name,mime=files[path];self.reply(200,(ROOT/'static'/name).read_bytes(),mime)
    def do_POST(self):
        origin=self.headers.get('Origin')
        if not self.allowed() or (origin and origin not in (f'http://127.0.0.1:{PORT}',f'http://localhost:{PORT}')) or not secrets.compare_digest(self.headers.get('X-ChartMate-Token',''),TOKEN):
            return self.reply(403,{'error':'Unauthorized request. Refresh the local page.'})
        if self.path=='/api/extract':
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=200000: return self.reply(413,{'error':'Text must be under 200 KB.'})
                self.connection.settimeout(30)
                body=json.loads(self.rfile.read(length))
                text=body.get('text','')
                if not isinstance(text,str) or not text.strip():raise ValueError('Enter a transcript first.')
                if not LOCK.acquire(blocking=False):return self.reply(409,{'error':'A model is already processing. Wait for transcription/extraction to finish.'})
                try:return self.reply(200,extract_local(text))
                finally:LOCK.release()
            except ValueError as e:return self.reply(400,{'error':str(e)})
            except RuntimeError as e:return self.reply(503,{'error':str(e)})
            except Exception:return self.reply(500,{'error':'Local extraction failed. Check Ollama and retry.'})
        if self.path!='/api/transcribe':return self.reply(404,{'error':'Not found'})
        try:length=int(self.headers.get('Content-Length','0'))
        except ValueError:return self.reply(400,{'error':'Invalid file length'})
        if not 0<length<=MAX_BYTES:return self.reply(413,{'error':'Recording is empty or exceeds 128 MB'})
        state=status()
        if not state['ready']:return self.reply(503,{'error':'\n'.join(state['problems'])})
        if not LOCK.acquire(blocking=False):return self.reply(409,{'error':'Another recording is being transcribed. Try again later.'})
        try:
            self.connection.settimeout(60)
            payload=self.rfile.read(length)
            if len(payload)!=length:raise ValueError('Incomplete audio upload')
            self.reply(200,transcribe(payload))
        except ValueError as e:self.reply(400,{'error':str(e)})
        except subprocess.TimeoutExpired:self.reply(504,{'error':'Processing timed out. Use a shorter recording or a smaller model.'})
        except Exception as e:self.reply(500,{'error':str(e)})
        finally:LOCK.release()

def main():
    global PORT
    httpd=ThreadingHTTPServer(('127.0.0.1',PORT),Handler)
    PORT=httpd.server_address[1]
    print(json.dumps({'event':'ready','port':PORT}),flush=True)
    try:httpd.serve_forever()
    except KeyboardInterrupt:pass
    finally:httpd.server_close()

if __name__=='__main__':main()
