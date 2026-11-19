import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

@unittest.skipUnless(os.name=='nt','Windows Job Object integration requires Windows')
class WindowsGuardTests(unittest.TestCase):
 def test_parent_exit_kills_supervised_descendant(self):
  # Use a heartbeat file to verify descendants stop, rather than checking only the wrapper PID.
  with tempfile.TemporaryDirectory() as tmp:
   beat=Path(tmp)/'beat.txt'
   worker="import pathlib,time; p=pathlib.Path("+repr(str(beat))+");\nwhile True:\n p.write_text(str(time.time())); time.sleep(.1)"
   entry=str(Path(__file__).with_name('desktop_entry.py'))
   parent_code="import subprocess,os,sys,time; p=subprocess.Popen([sys.executable,"+repr(entry)+",'--supervise',sys.executable,'-c',"+repr(worker)+"],env={**os.environ,'CHARTMATE_PARENT_PID':str(os.getpid())}); print(p.pid,flush=True); time.sleep(60)"
   parent=subprocess.Popen([sys.executable,'-c',parent_code],stdout=subprocess.PIPE,text=True)
   try:
    for _ in range(100):
     if beat.exists():break
     time.sleep(.1)
    self.assertTrue(beat.exists(),'Supervised child failed to start')
    parent.terminate();parent.wait(timeout=10);time.sleep(1)
    before=beat.read_text();time.sleep(.5)
    self.assertEqual(before,beat.read_text(),'Child survived its launcher')
   finally:
    if parent.poll() is None:parent.terminate();parent.wait(timeout=10)

if __name__=='__main__':unittest.main()
