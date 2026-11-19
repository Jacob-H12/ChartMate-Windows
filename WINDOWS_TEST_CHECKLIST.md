# Windows acceptance checklist (not yet completed)

- [ ] Build on Windows x64 with Python 3.12 and Node.js; no Conda dependency.
- [ ] Build from a directory with spaces, then launch from Program Files.
- [ ] Windows process guard test and both runtime audits pass.
- [ ] Install on a clean Windows 10 22H2 / Windows 11 PC with no Python, Node, FFmpeg, Whisper or Ollama.
- [ ] Microsoft runtime prerequisite succeeds (including already-installed newer runtime).
- [ ] Start from desktop/Start menu with no console windows flashing.
- [ ] First-time download, interrupted download retry, low-space message, offline relaunch.
- [ ] Microphone allow/deny and recovery through Windows Settings.
- [ ] Record/play/transcribe; test >120 seconds; compare line breaks and spaces in extraction.
- [ ] Export audio, TXT, CSV, all drafts, session JSON; restore JSON; print/PDF.
- [ ] Cancel close with unsaved work; app services still work.
- [ ] Close or force-kill ChartMate while downloading/transcribing; its backend and model processes terminate.
- [ ] Independent Ollama installation remains untouched and running.
- [ ] Double launch focuses the existing window.
- [ ] Uninstall/reinstall preserves model directory and does not touch other Ollama models.
- [ ] Record RAM, CPU/GPU, transcription latency and extraction latency.
- [ ] Test intended public-release signature and SmartScreen behavior before broad distribution.
