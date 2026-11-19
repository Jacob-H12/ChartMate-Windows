"""Frozen server entry and parent watchdog for bundled child processes."""
import os
import signal
import subprocess
import sys
import threading
import time
from native_subprocess import run_native

def watch_parent():
    parent = int(os.environ.get('CHARTMATE_PARENT_PID', '0'))
    if parent <= 1:
        return
    while True:
        time.sleep(2)
        if os.getppid() != parent:
            # This process is a session/group leader created by Electron.
            # Terminate its own group, never a user-installed Ollama instance.
            if os.getpgrp() == os.getpid():
                os.killpg(os.getpgrp(), signal.SIGTERM)
            os._exit(0)

def main():
    if os.name == 'nt':
        from windows_process import install_guard
        install_guard(int(os.environ.get('CHARTMATE_PARENT_PID', '0')))
    else:
        threading.Thread(target=watch_parent, daemon=True).start()
    if len(sys.argv) > 2 and sys.argv[1] == '--supervise':
        child_env = os.environ.copy()
        # Do not leak the frozen Python loader's environment into native tools.
        for key in tuple(child_env):
            if key.startswith(('_PYI_', 'DYLD_')):
                child_env.pop(key, None)
        result = run_native(sys.argv[2:], env=child_env, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        sys.exit(result.returncode)
    import server
    server.main()

if __name__ == '__main__':
    main()
