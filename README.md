# 🎬 VidNote

## 1. 介绍

一个本地优先的视频知识萃取工具，输入视频链接，自动下载、语音转录、AI 总结，输出图文并茂的 Markdown 笔记。

**主要特性：**
- **全网视频支持**：内置 yt-dlp，支持 B站、小红书、抖音、YouTube 等 1000+ 平台。
- **本地语音转录**：whisper.cpp + Apple Silicon Metal GPU 加速，数据不上传，隐私安全。
- **AI 知识萃取**：大模型自动提炼核心要点、关键金句和方法论。
- **关键帧截图**：AI 识别关键时间点，自动截取配图。
- **Markdown 输出**：结构化图文笔记，方便 Obsidian 等工具归档。
- **桌面应用 + CLI**：现代化 Electron 界面 & 命令行直接调用，支持 AI Skill 集成。

## 2. 怎么使用

### 桌面应用

前往 [Releases](https://github.com/gujiangfei/vidnote/releases) 下载对应平台的安装包（macOS DMG / Windows EXE / Linux AppImage），安装后打开应用，粘贴视频链接即可。

首次使用需配置 [硅基流动](https://siliconflow.cn/) API Key（用于 AI 总结）。

### 命令行 (CLI)

下载对应平台的 CLI 包（自包含所有依赖，解压即用）：

```bash
# 解压
tar -xzf vidnote-cli-linux-x64.tar.gz
cd vidnote-cli

# 配置 API Key
cp .env.example .env
vim .env  # 填入你的硅基流动 API Key

# 使用
./api_backend info "https://www.bilibili.com/video/BVxxx"           # 获取视频信息
./api_backend process "https://www.bilibili.com/video/BVxxx"        # 完整处理
./api_backend process "https://www.bilibili.com/video/BVxxx" --json # JSON 输出（供程序集成）
```

## 3. 免责声明

> **⚠️ 重要：请在使用前仔细阅读。**

- 本工具仅供**个人学习和研究**使用，用户应确保其使用行为符合当地法律法规。
- 本工具**不提供任何视频内容的存储或分发服务**，视频下载功能依赖于开源项目 [yt-dlp](https://github.com/yt-dlp/yt-dlp)，仅用于用户对**自己有权访问的内容**进行本地转录和笔记。
- **请勿**将本工具用于下载、传播受版权保护的内容，或用于任何商业用途。
- 因用户不当使用本工具而产生的一切法律责任，由用户自行承担，与本项目开发者无关。
- 本项目完全开源免费，不收取任何费用。

## 4. 打赏

如果这个开源小工具对你有帮助，欢迎打赏喝杯咖啡！

<img src="赞赏码.png" alt="赞赏码" width="300" />

## License

[MIT](LICENSE)
