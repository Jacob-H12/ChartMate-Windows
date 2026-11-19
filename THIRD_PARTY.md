# ChartMate Windows component notices

This is an engineering research prototype, not an official WHO application or a validated clinical system.

- WHO Labour Care Guide field adaptation: CC BY-NC-SA 3.0 IGO; original reference remains in backend/reference. No WHO endorsement. Existing attribution and review notices are preserved in the UI.
- Electron / Node / Chromium: upstream distribution licenses and notices are retained by electron-builder.
- Python: PSF license. PyInstaller: its upstream license and bootloader distribution exception apply. The build embeds the Python runtime.
- whisper.cpp v1.7.6: MIT; official Windows x64 binaries from https://github.com/ggml-org/whisper.cpp/releases/tag/v1.7.6 . The complete archive layout and DLLs are retained.
- Ollama v0.40.16: MIT; official standalone Windows x64 package from https://github.com/ollama/ollama/releases/tag/v0.40.16 . Complete accompanying runtime files are retained.
- Whisper medium.en model: MIT, downloaded on first use from https://huggingface.co/ggerganov/whisper.cpp . Pinned URL and SHA-256 are in desktop/models.json.
- Qwen3 4B model: Apache 2.0; first-use download via the private local Ollama service. License source: https://huggingface.co/Qwen/Qwen3-4B/raw/main/LICENSE .
- FFmpeg: the n8.1 win64 LGPL shared build from https://github.com/FFmpeg-Builds/FFmpeg-Builds . The unmodified distribution, included license/docs and DLLs are retained. The exact asset ID, URL and SHA-256 used are saved in runtime/licenses/windows-native-lock.json. Corresponding FFmpeg sources: https://git.ffmpeg.org/ffmpeg.git ; build recipes and external library source versions: the FFmpeg-Builds repository. Preserve and review the upstream notices/source availability when distributing or changing this dependency.
- Microsoft Visual C++ Redistributable x64: Microsoft license terms apply. Downloaded from Microsoft's endpoint and checked for a valid Microsoft Authenticode signature before inclusion. Installed as a prerequisite by the elevated installer.

Downloaded license files are stored under Resources/runtime/licenses. No commercial license for the ChartMate-specific source is asserted by this generated prototype.
