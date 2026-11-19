"""Windows process-tree cleanup using an app-owned kill-on-close Job Object."""
import ctypes
from ctypes import wintypes
import os
import threading

_JOB = None

def install_guard(parent_pid):
    global _JOB
    if os.name != 'nt':
        raise RuntimeError('Windows guard called on another platform')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    SIZE_T = ctypes.c_size_t
    class BASIC(ctypes.Structure):
        _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64), ('PerJobUserTimeLimit', ctypes.c_int64),
                    ('LimitFlags', wintypes.DWORD), ('MinimumWorkingSetSize', SIZE_T),
                    ('MaximumWorkingSetSize', SIZE_T), ('ActiveProcessLimit', wintypes.DWORD),
                    ('Affinity', SIZE_T), ('PriorityClass', wintypes.DWORD), ('SchedulingClass', wintypes.DWORD)]
    class IO(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in ('ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount')]
    class EXTENDED(ctypes.Structure):
        _fields_ = [('BasicLimitInformation', BASIC), ('IoInfo', IO), ('ProcessMemoryLimit', SIZE_T),
                    ('JobMemoryLimit', SIZE_T), ('PeakProcessMemoryUsed', SIZE_T), ('PeakJobMemoryUsed', SIZE_T)]
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.OpenProcess.argtypes = [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE,wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    job = kernel.CreateJobObjectW(None, None)
    if not job:raise ctypes.WinError(ctypes.get_last_error())
    limits = EXTENDED();limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
    if not kernel.SetInformationJobObject(job,9,ctypes.byref(limits),ctypes.sizeof(limits)):
        error=ctypes.get_last_error();kernel.CloseHandle(job);raise ctypes.WinError(error)
    if not kernel.AssignProcessToJobObject(job,kernel.GetCurrentProcess()):
        error=ctypes.get_last_error();kernel.CloseHandle(job);raise ctypes.WinError(error)
    _JOB = job  # Non-inheritable handle remains open for this process's lifetime.
    if parent_pid > 1:
        parent = kernel.OpenProcess(0x00100000,False,parent_pid)  # SYNCHRONIZE only
        if not parent:os._exit(1)
        def wait():
            result=kernel.WaitForSingleObject(parent,0xFFFFFFFF)
            kernel.CloseHandle(parent)
            # Exiting closes our only job handle and kills our descendants.
            os._exit(0 if result == 0 else 1)
        threading.Thread(target=wait,daemon=True).start()
