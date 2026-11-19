# ChartMate Windows x64 — 构建与测试说明

这是 Windows 桌面应用源码工程，不是已经编译好的 EXE。
原来的 Mac 工程和 APP 无需修改。不要用这个文件夹覆盖 Mac 版本。

## 支持范围

- Windows 10 22H2 / Windows 11，Intel 或 AMD x64 电脑。
- 不是 Windows ARM64 版，不支持 32 位系统。
- 16 GB RAM 为建议配置；8 GB 可能较慢。Whisper 使用 CPU 版本；不承诺实时转写。
- Ollama 使用随包分发的 Windows 原生运行时；GPU 能否加速取决于硬件与驱动，未在此交付环境验证。
- 安装包包含运行程序，不包含 AI 模型；首次启动约下载 4 GB 模型，之后可以离线使用。
- 建议目标电脑预留至少 15 GB 空间（包括应用运行时和模型）；首次下载前应用检查至少 7 GB 剩余空间。
- 安装程序会申请管理员权限，以安装应用和所需的 Microsoft Visual C++ 运行库。普通使用不要求管理员权限。

## 如果你只有目前的 M1 Mac

不要在 Mac 上运行 `build-mac.sh` 来生成 Windows 安装包。这个工程包含 Windows EXE、DLL、Python 打包及进程管理，需要在 Windows 环境完成构建和测试。

可选择：

1. 在一台 Windows x64 电脑上按下面的步骤构建；也可以请测试者协助执行这一次构建。
2. 使用包内的 GitHub Actions，让 GitHub 的 Windows 构建机生成安装包。你可以在 Mac 浏览器中操作；之后仍需 Windows 实机测试。

## 方法一：在 Windows 电脑构建

### 1. 安装构建工具（只有开发者需要）

安装 Python 3.12 64 位和 Node.js LTS。可从官方网站下载：

- https://www.python.org/downloads/windows/
- https://nodejs.org/

Python 安装时保留 Python Launcher，并勾选加入 PATH。关闭并重新打开终端。

如果电脑有 `winget`，也可以在 PowerShell 执行：

```powershell
winget install --exact --id Python.Python.3.12
winget install --exact --id OpenJS.NodeJS.LTS
```

安装完成后重新打开终端。无需 Conda、Homebrew、Visual Studio 或手动安装 Ollama。

### 2. 解压并开始构建

把 `ChartMate_Windows` 放在例如 `C:\ChartMate_Windows`。也支持包含空格的目录，但建议先用较短路径，避免 Windows 路径长度限制。

双击：

```
Build_ChartMate.cmd
```

也可以在该文件夹内打开 PowerShell 后运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-windows.ps1
```

这里的 `Bypass` 只作用于这次 PowerShell 进程，不会更改系统永久执行策略。

构建过程会：

1. 创建工程内独立的 `.build-venv`。
2. 按 `package-lock.json` 安装 Electron 构建依赖。
3. 下载 Whisper、FFmpeg、Ollama 的 Windows x64 运行时，校验下载摘要；保留配套 DLL 和上游目录结构。
4. 校验微软运行库安装程序的 Authenticode 签名，安装运行库（可能弹出 UAC 确认）。
5. 打包 Python 后端，执行自动化测试和真实 Windows 运行时检查。
6. 生成安装程序，再检查安装包旁的应用文件。
7. 显示 `Build complete.`，打开 `dist` 文件夹。

首次构建会下载较大的 Windows 运行时；建议构建电脑预留约 30 GB 可用空间。耗时和最终安装包大小以实际构建结果为准。

不要删除 `.build/downloads`：成功下载的文件会复用。FFmpeg 上游使用滚动发布，首次构建会将资产 URL、ID 和 SHA-256 记录到 `.build/downloads/windows-native-lock.json`。如果以后上游更新导致校验失败，保留报错并更新锁定信息，不要取消校验。

### 3. 找到结果

安装程序：

```
dist\ChartMate-Setup-0.1.0-win-x64.exe
```

未安装的测试应用：

```
dist\win-unpacked\ChartMate.exe
```

先测试安装程序，确保在没有开发环境的电脑也能运行。不要单独发送 `win-unpacked` 中的 `ChartMate.exe`，它依赖旁边的文件。

## 方法二：在 Mac 上通过 GitHub Actions 构建

已附配置：`.github/workflows/windows-build.yml`。它使用 Windows x64 构建机，只支持手动触发；不会自动发布安装包。

1. 在你自己的 GitHub 账号中创建仓库。
2. 把 `ChartMate_Windows` 文件夹**里面的内容**提交到仓库根目录。根目录应直接包含 `package.json`、`backend`、`desktop`、`scripts`；不要再多套一层文件夹。
3. 确认 `.github/workflows/windows-build.yml` 也提交了。Mac Finder 默认可能不显示这个目录；可用 GitHub Desktop 提交解压后的整个工程，或在 Finder 按 Command+Shift+. 显示隐藏文件后核对。
4. 在 GitHub 仓库打开 **Actions → Build ChartMate Windows → Run workflow**。
5. 构建成功后，在运行页面的 **Artifacts** 下载 `ChartMate-Windows-x64`。
6. 解压 Artifact，里面的 `ChartMate-Setup-0.1.0-win-x64.exe` 才是发给测试者的安装程序。

本次交付没有创建你的 GitHub 仓库，也没有执行云端构建。Actions 的可用额度及费用以你的账号为准。无须上传任何录音、患者资料、模型文件或账号凭证；仓库仅需源码工程。

## 最终测试者的操作

1. 运行 `ChartMate-Setup-0.1.0-win-x64.exe`，按向导安装；必要时允许微软运行库安装。
2. 从开始菜单或桌面启动 ChartMate。
3. 点击 **Download Models & Start**，联网等待一次性模型下载。
4. 点击 **Start Recording** → **Stop & Transcribe**。
5. 核对转写，点击 **Extract with Local AI**，核对字段后添加到表格。
6. 保存需要的音频、TXT、CSV 或 JSON。退出前导出，当前工作不会自动保存。

麦克风不可用时，从应用 **Help → Microphone Permissions** 打开 Windows 设置，允许麦克风访问以及桌面应用访问。

模型目录位于当前用户的：

```
%APPDATA%\ChartMate\models
```

应用菜单 **ChartMate → Model Folder** 可直接打开。模型不写到 Program Files，也不使用用户自己安装的 Ollama。卸载默认保留用户数据和模型；重装可复用。若明确不再需要，可在退出应用后手动删除此目录。

## 已验证和未验证

交付环境是 Linux，没有 Windows 桌面。

已通过：9 项 Node 测试、29 项 Python 测试；下载校验/续传、换行匹配、原文引用、动态端口相关逻辑；Python/JavaScript 语法检查。

Windows Job Object 进程回收集成测试在本环境明确跳过，会在 Windows 构建时运行。还增加 Windows 运行时检查：EXE 架构、Whisper 启动、WebM/MP4 解码、Ollama 启动、冻结 Python 后端和本地接口权限。

尚未验证：PowerShell 完整构建、Windows 安装程序、Electron 窗口、麦克风、真实模型推理、显卡驱动、SmartScreen 体验。以构建结果和 `WINDOWS_TEST_CHECKLIST.md` 的实机记录为准，不能把源码测试当成安装包已经能用。

## 签名与分发

默认是未做 Windows 代码签名的内部测试包。Windows 可能显示未知发布者或 SmartScreen 提示；应核对文件来源并记录提示，不要关闭 Defender 或系统安全保护。

公开分发前应配置自己的 Windows 代码签名证书，并在干净的 Windows x64 电脑完成安装测试。仅拥有 Apple Developer 证书不能替代 Windows 签名。

构建错误请保留最后 30–50 行日志。不要反复重装 Python、删除已下载模型或覆盖能用的 Mac 项目。
