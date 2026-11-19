import os
import unittest
from unittest.mock import patch
import local_llm
import server

class DesktopTests(unittest.TestCase):
    def test_local_port_only(self):
        with patch.dict(os.environ,{'CHARTMATE_OLLAMA_PORT':'43219'}):
            self.assertEqual(local_llm.ollama_url(),'http://127.0.0.1:43219/api/chat')
        for port in ('https://example.org','0','65536','11434/api'):
            with self.subTest(port=port),patch.dict(os.environ,{'CHARTMATE_OLLAMA_PORT':port}):
                with self.assertRaises(ValueError):local_llm.ollama_url()
    def test_desktop_header_and_host(self):
        handler=object.__new__(server.Handler)
        with patch.object(server,'DESKTOP',True):
            handler.headers={'Host':f'127.0.0.1:{server.PORT}'}
            self.assertFalse(handler.allowed())
            handler.headers['X-ChartMate-Desktop']=server.TOKEN
            self.assertTrue(handler.allowed())
            handler.headers['Host']='attacker.example'
            self.assertFalse(handler.allowed())

if __name__=='__main__':unittest.main()
