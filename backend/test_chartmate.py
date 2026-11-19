import io,sys,wave,unittest,json
from pathlib import Path
from unittest.mock import patch
import extraction,server
class Checks(unittest.TestCase):
 def test_fields(self):
  r=extraction.extract('Fetal heart rate: 140 bpm; Blood pressure: 118/76; Temperature: 36.8 C; Cervix: 6 cm; Plan: review fetal heart rate in 30 minutes.')
  self.assertEqual(r['fields']['fhr']['value'],'140 bpm');self.assertEqual(r['fields']['diastolic']['value'],'76');self.assertEqual(r['fields']['temperature']['value'],'36.8 C');self.assertEqual(r['fields']['plan']['value'],'review fetal heart rate in 30 minutes');self.assertNotIn('pulse',r['fields'])
 def test_uncertainty_conflict_negation(self):
  r=extraction.extract('FHR: 140; FHR: 160; Correction: cervix is 7 cm; No fetal heart rate was obtained; Pain relief: declined; Deceleration: none')
  self.assertTrue(r['fields']['fhr']['conflict']);self.assertEqual(r['fields']['fhr']['value'],'');self.assertNotIn('cervix',r['fields']);self.assertEqual(len(r['unmatched']),2);self.assertEqual(r['fields']['deceleration']['value'],'none')
 def test_long_recording_no_truncation(self):
  audio=io.BytesIO()
  with wave.open(audio,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0\0'*16000*361)
  actual_run=server.subprocess.run;seen=[]
  def run(cmd,**kwargs):
   if '-otxt' not in cmd:return actual_run(cmd,**kwargs)
   with wave.open(cmd[cmd.index('-f')+1],'rb') as w:seen.append(w.getnframes()/w.getframerate())
   Path(cmd[cmd.index('-of')+1]+'.txt').write_text('segment '+str(len(seen)))
   return type('Result',(),{'returncode':0})()
  with patch.object(server.subprocess,'run',side_effect=run):r=server.transcribe(audio.getvalue())
  self.assertEqual(seen,[120,120,120,1]);self.assertEqual(r['duration_seconds'],361);self.assertIn('segment 4',r['text'])
if __name__=='__main__':unittest.main()
