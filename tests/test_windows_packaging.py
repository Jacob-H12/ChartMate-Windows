"""Platform-independent regression tests for Windows archive/path handling."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('prepare_windows',ROOT/'scripts/prepare-windows.py')
prep=importlib.util.module_from_spec(spec);spec.loader.exec_module(prep)

class Packaging(unittest.TestCase):
 def test_archive_keeps_dll_siblings_and_nested_paths(self):
  with tempfile.TemporaryDirectory(prefix='ChartMate path (test) ') as tmp:
   root=Path(tmp);archive=root/'native.zip';target=root/'runtime'
   with zipfile.ZipFile(archive,'w') as z:
    z.writestr('Release/whisper-cli.exe',b'fake');z.writestr('Release/whisper.dll',b'fake')
   prep.safe_extract(archive,target)
   with patch.object(prep,'RUNTIME',target):self.assertEqual(prep.one_exe(target,'whisper-cli.exe'),'Release/whisper-cli.exe')
   self.assertTrue((target/'Release/whisper.dll').exists())
 def test_archive_rejects_traversal_and_windows_drive_paths(self):
  for name in ('../escape','C:/escape','x/../../escape','\\\\server\\share\\escape'):
   with self.subTest(name=name),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);archive=root/'bad.zip'
    with zipfile.ZipFile(archive,'w') as z:z.writestr(name,b'fake')
    with self.assertRaises(ValueError):prep.safe_extract(archive,root/'target')
 def test_native_layout_ambiguity_fails(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   for name in ('a','b'):(root/name).mkdir();(root/name/'ollama.exe').touch()
   with self.assertRaises(RuntimeError):prep.one_exe(root,'ollama.exe')

if __name__=='__main__':unittest.main()
