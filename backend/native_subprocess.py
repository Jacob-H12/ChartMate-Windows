"""Prevent frozen Python's DLL search path from contaminating native tools."""
import os
import subprocess
import sys

def run_native(args, **kwargs):
    if os.name == 'nt' and getattr(sys, 'frozen', False):
        import ctypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
        kernel.SetDllDirectoryW.restype = ctypes.c_int
        if not kernel.SetDllDirectoryW(None):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return subprocess.run(args, **kwargs)
        finally:
            kernel.SetDllDirectoryW(sys._MEIPASS)
    return subprocess.run(args, **kwargs)
