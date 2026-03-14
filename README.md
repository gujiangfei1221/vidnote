# 🎬 VidNote — 视频知识萃取工具

输入一个视频链接，自动下载、语音转录、AI 总结，输出图文并茂的 Markdown 笔记。

> 支持 **小红书、B站、抖音、YouTube** 等 1000+ 平台 · 本地 whisper.cpp 转录 · Apple Silicon Metal GPU 加速

---

## ✨ 功能特性

- ⬇️ **全网视频下载** — 内置 yt-dlp，粘贴链接一键下载
- 🎙️ **本地语音转录** — whisper.cpp + Metal GPU 加速，隐私安全
- 🤖 **AI 知识萃取** — 硅基流动 DeepSeek，自动提炼核心要点
- 📸 **关键帧截图** — AI 识别关键时间点，自动截取配图
- 📝 **Markdown 输出** — 结构化图文笔记，方便 Obsidian 归档
- 🖥️ **桌面应用** — 现代化 Electron 界面，拖拽 + 流式进度
- 💻 **CLI 支持** — 命令行直接调用，支持 JSON 输出，方便 AI 集成

---

## 🔄 处理流程

```
视频链接 (B站/小红书/YouTube/...)
    │
    ▼ ① yt-dlp
本地视频文件 (.mp4)
    │
    ▼ ② ffmpeg
16kHz Mono WAV 音频
    │
    ▼ ③ whisper.cpp (Metal 加速)
带时间戳的转录文本
    │
    ▼ ④ 文本清洗 + 繁简转换
纯净转录文本
    │
    ├─▼ ⑤ AI 知识总结 (DeepSeek)
    │  Markdown 格式的知识萃取
    │
    └─▼ ⑥ AI 关键帧分析 + ffmpeg 截图
       图文并茂的完整笔记
```

---

## 📁 工程结构

```
vidnote/
├── backend/                 # Python 后端
│   ├── api.py               #   入口（CLI + Electron JSON API）
│   ├── cli.py               #   CLI 命令行模块
│   ├── config.py            #   配置管理
│   ├── requirements.txt     #   Python 依赖
│   └── processor/           #   核心处理模块
│       ├── audio.py         #     音频提取 (ffmpeg)
│       ├── transcribe.py    #     语音转文字 (whisper.cpp)
│       ├── downloader.py    #     视频下载 (yt-dlp)
│       ├── clean.py         #     文本清洗 + 繁简转换
│       ├── summarize.py     #     AI 总结 + 关键帧提取
│       └── keyframes.py     #     关键帧截图 (ffmpeg)
│
├── app/                     # Electron 桌面前端
│   ├── main.js              #   主进程
│   ├── renderer.js          #   渲染进程
│   ├── index.html           #   页面
│   ├── styles.css           #   样式
│   └── package.json         #   Node.js 依赖
│
├── scripts/                 # 构建脚本
│   ├── build-mac.sh         #   macOS 一键打包
│   └── build-win.bat        #   Windows 一键打包
│
├── .env.example             # 配置模板
├── .github/workflows/       # CI/CD
└── README.md
```

---

## 🚀 快速开始

### 前置依赖

- macOS (Apple Silicon) 或 Windows
- Python 3.11+
- Node.js 18+
- [硅基流动](https://siliconflow.cn/) API Key

### 方式一：一键打包（推荐）

```bash
# macOS
./scripts/build-mac.sh

# Windows（管理员权限运行）
scripts\build-win.bat
```

脚本会自动安装所有依赖、编译 whisper.cpp、下载模型、打包 Electron 应用。

### 方式二：开发模式

```bash
# 1. 安装系统依赖
brew install ffmpeg cmake

# 2. 创建 Python 环境
conda create -n vidnote python=3.11 -y
conda activate vidnote
pip install -r backend/requirements.txt

# 3. 编译 whisper.cpp（Metal 加速）
mkdir -p vendor
git clone https://github.com/ggerganov/whisper.cpp.git vendor/whisper.cpp
cd vendor/whisper.cpp
cmake -B build -DWHISPER_METAL=ON
cmake --build build --config Release -j$(sysctl -n hw.physicalcpu)
cd ../..

# 4. 下载 Whisper 模型
mkdir -p models
curl -L -o models/ggml-base.bin \
  "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"

# 5. 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的硅基流动 API Key

# 6. 启动桌面应用
cd app && npm install && npm start
```

---

## 💻 CLI 命令行用法

打包后的 `api_backend` 二进制同时支持桌面应用和命令行调用：

```bash
# 查看帮助
./api_backend --help

# 获取视频信息（不下载）
./api_backend info "https://www.bilibili.com/video/BVxxx"

# 仅下载视频
./api_backend download "https://www.bilibili.com/video/BVxxx" -o ./videos

# 完整处理（下载 → 转录 → AI 总结 → Markdown）
./api_backend process "https://www.bilibili.com/video/BVxxx"
./api_backend process "https://www.bilibili.com/video/BVxxx" -o ./notes -l zh
```

### JSON 输出（用于程序集成 / AI Skill）

```bash
./api_backend info "https://bilibili.com/video/BVxxx" --json
./api_backend process "https://bilibili.com/video/BVxxx" --json
```

返回结构化 JSON：

```json
{
  "success": true,
  "elapsed": 45.2,
  "md_path": "/path/to/output/xxx_总结.md",
  "summary": "## 核心主题\n...",
  "transcript": "完整转录文本...",
  "keyframes": [
    {"time": "00:01:23", "title": "...", "summary": "..."}
  ]
}
```

### CLI 参数一览

| 命令 | 参数 | 说明 |
|------|------|------|
| `process <url>` | | 完整处理流程 |
| | `-o, --output` | 输出目录 |
| | `-l, --language` | 语言 (zh/en/auto)，默认 auto |
| | `-m, --model` | Whisper 模型名称 |
| | `--json` | 输出 JSON 格式 |
| `download <url>` | | 仅下载视频 |
| | `-o, --output` | 输出目录 |
| | `--json` | 输出 JSON |
| `info <url>` | | 获取视频信息 |
| | `--json` | 输出 JSON |

---

## 🧠 模型选择指南

| 模型 | 大小 | 速度 | 准确率 | 适用场景 |
|------|------|------|--------|----------|
| `tiny` | 75 MB | ⚡⚡⚡ | ★★☆ | 快速预览 |
| `base` | 141 MB | ⚡⚡ | ★★★ | **推荐**，速度与质量平衡 |
| `small` | 466 MB | ⚡ | ★★★★ | 较高准确率 |
| `large-v3-turbo` | 1.5 GB | 🐢 | ★★★★★ | 最高准确率 |

---

## 🛠️ 配置项

所有配置通过 `.env` 文件或环境变量设置：

```env
# 硅基流动 API（必填）
SILICONFLOW_API_KEY=sk-xxxxx

# 可选
SILICONFLOW_MODEL=deepseek-ai/DeepSeek-V3.2
FFMPEG_PATH=ffmpeg
WHISPER_CPP_PATH=./vendor/whisper.cpp/build/bin/whisper-cli
WHISPER_MODEL_PATH=./models/ggml-base.bin
OUTPUT_DIR=./output
```

---

## 📄 License

MIT
