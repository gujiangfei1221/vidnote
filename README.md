# 🎬 短视频 AI 知识萃取工具

输入一个短视频文件，自动提取语音、转录为文字，并调用 AI 大模型进行知识萃取与总结。

> 专为 **Apple Silicon Mac** 优化，使用 whisper.cpp Metal 加速实现高性能本地语音转录。

---

## ✨ 功能特性

- 🎙️ **本地语音转录** — 基于 whisper.cpp，Metal GPU 加速，隐私安全
- 🤖 **AI 知识萃取** — 调用硅基流动 DeepSeek-V3.2，自动提炼核心要点
- 📝 **Markdown 输出** — 结构化总结 + 原始转录文本，方便归档
- 👀 **监听模式** — 监控文件夹，新增视频自动处理
- 🎯 **开箱即用** — CLI 命令行操作，简单易用

---

## 📁 工程结构

```
asragent/
├── main.py                  # CLI 入口，串联完整处理流程
├── config.py                # 配置管理（路径、API Key、Prompt 等）
├── watcher.py               # 文件夹监听模式（watchdog）
├── .env                     # 环境变量配置（API Key 填在这里）
├── .gitignore               # Git 忽略规则
├── requirements.txt         # Python 依赖清单
│
├── processor/               # 🔧 核心处理模块
│   ├── __init__.py
│   ├── audio.py             #   └─ 音频提取（ffmpeg: 视频 → 16kHz WAV）
│   ├── transcribe.py        #   └─ 语音转文字（调用 whisper.cpp）
│   ├── clean.py             #   └─ 文本清洗（去除时间戳、控制符等）
│   └── summarize.py         #   └─ AI 总结（调用硅基流动 API）
│
├── models/                  # 🧠 Whisper 模型文件
│   └── ggml-base.bin        #   └─ base 模型（141MB，已下载）
│
├── vendor/                  # 📦 第三方本地编译依赖
│   └── whisper.cpp/         #   └─ whisper.cpp 源码 + 编译产物
│       ├── build/           #       ├─ cmake 编译输出
│       │   └── bin/         #       │   └─ whisper-cli（转录可执行文件）
│       ├── models/          #       ├─ 原始模型目录（未使用）
│       └── ...              #       └─ 源码文件
│
└── output/                  # 📄 处理结果输出目录（自动创建）
    ├── xxx_总结_时间戳.md    #   └─ AI 总结 Markdown
    └── xxx_转录.txt          #   └─ 原始转录文本
```

### 关于 `vendor/` 目录

`vendor/` 是存放**第三方本地编译依赖**的目录。目前只包含 [whisper.cpp](https://github.com/ggerganov/whisper.cpp) —— 一个高性能的 C/C++ 语音识别引擎。

之所以将它放在项目内（而非全局安装），是因为：
1. **版本可控** — 确保编译版本与项目代码兼容
2. **Metal 加速** — 编译时开启了 Apple Silicon GPU 加速（`-DWHISPER_METAL=ON`）
3. **自包含** — 项目拷贝到其他 Mac 上只需重新编译即可运行

> ⚠️ `vendor/` 已加入 `.gitignore`，不会被提交到 Git 仓库。在新机器上需要重新克隆和编译（见下方安装步骤）。

---

## 🔄 处理流程

```
视频文件 (.mp4/.mov/...)
    │
    ▼ ① ffmpeg
16kHz Mono WAV 音频
    │
    ▼ ② whisper.cpp (Metal 加速)
带时间戳的转录文本
    │
    ▼ ③ 文本清洗
纯净的转录文本
    │
    ▼ ④ 硅基流动 API (DeepSeek-V3.2)
Markdown 格式的知识总结
    │
    ▼ ⑤ 输出
终端显示 + .md 文件保存
```

---

## 🚀 快速开始

### 前置依赖

- macOS (Apple Silicon)
- [Homebrew](https://brew.sh/)
- [Miniconda](https://docs.conda.io/en/latest/miniconda.html)
- [硅基流动](https://siliconflow.cn/) 账号及 API Key

### 1. 安装系统依赖

```bash
brew install ffmpeg cmake
```

### 2. 创建 Python 环境

```bash
conda create -n asragent python=3.11 -y
conda activate asragent
pip install -r requirements.txt
```

### 3. 编译 whisper.cpp

```bash
# 克隆
mkdir -p vendor
git clone https://github.com/ggerganov/whisper.cpp.git vendor/whisper.cpp

# 编译（开启 Metal GPU 加速）
cd vendor/whisper.cpp
cmake -B build -DWHISPER_METAL=ON
cmake --build build --config Release -j$(sysctl -n hw.physicalcpu)
cd ../..
```

### 4. 下载 Whisper 模型

```bash
mkdir -p models

# base 模型（141MB，速度与质量平衡）
curl -L -o models/ggml-base.bin \
  "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin"

# 可选：其他模型
# tiny (75MB, 最快)    → ggml-tiny.bin
# small (466MB)        → ggml-small.bin
# large-v3-turbo (最准) → ggml-large-v3-turbo.bin
```

### 5. 配置 API Key

编辑 `.env` 文件：

```env
SILICONFLOW_API_KEY=sk-你的硅基流动API密钥
```

### 6. 验证安装

```bash
python main.py --check
# 应输出: ✅ 所有依赖均已就绪!
```

---

## 📖 使用方法

### 基础用法

```bash
# 处理单个视频
python main.py --input video.mp4

# 指定语言（跳过自动检测，更快）
python main.py --input video.mp4 --language zh

# 使用更大的模型（更准确）
python main.py --input video.mp4 --model large-v3-turbo

# 保留中间生成的 WAV 文件
python main.py --input video.mp4 --keep-wav

# 指定输出目录
python main.py --input video.mp4 --output-dir ~/Documents/notes
```

### 监听模式

自动监控文件夹，有新视频时自动处理：

```bash
python main.py --watch ~/Downloads/videos
# 按 Ctrl+C 停止
```

### 所有参数

| 参数 | 缩写 | 说明 | 默认值 |
|------|------|------|--------|
| `--input` | `-i` | 输入视频文件路径 | — |
| `--model` | `-m` | Whisper 模型 (tiny/base/small/large-v3-turbo) | base |
| `--output-dir` | `-o` | 输出目录 | `./output` |
| `--language` | `-l` | 语言代码 (zh/en/ja/auto) | auto |
| `--keep-wav` | — | 保留中间 WAV 文件 | 否 |
| `--watch` | `-w` | 监听模式目录 | — |
| `--check` | — | 仅检查依赖状态 | — |

---

## 🧠 模型选择指南

| 模型 | 大小 | 速度 | 准确率 | 适用场景 |
|------|------|------|--------|----------|
| `tiny` | 75 MB | ⚡⚡⚡ | ★★☆ | 快速预览，M4 秒出 |
| `base` | 141 MB | ⚡⚡ | ★★★ | **推荐**，速度与质量平衡 |
| `small` | 466 MB | ⚡ | ★★★★ | 需要更高准确率 |
| `large-v3-turbo` | 1.5 GB | 🐢 | ★★★★★ | 最高准确率 |

---

## 🛠️ 高级配置

所有配置项均可通过 `.env` 文件或环境变量设置：

```env
# 硅基流动 API（必填）
SILICONFLOW_API_KEY=sk-xxxxx

# 可选配置
FFMPEG_PATH=ffmpeg
WHISPER_CPP_PATH=./vendor/whisper.cpp/build/bin/whisper-cli
WHISPER_MODEL_PATH=./models/ggml-base.bin
SILICONFLOW_MODEL=deepseek-ai/DeepSeek-V3.2
OUTPUT_DIR=./output
```

---

## 📄 License

MIT
