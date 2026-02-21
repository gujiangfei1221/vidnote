"""
配置管理模块
集中管理所有路径、API 配置和运行参数。
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# 加载 .env 文件（开发模式从项目目录加载；打包模式可能不存在，静默跳过）
_default_root = Path(__file__).parent.resolve()
_env_file = _default_root / ".env"
if _env_file.is_file():
    load_dotenv(_env_file)

# ─── 项目根目录 ───
# 打包模式下由 Electron 主进程通过环境变量传入用户数据目录
PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", str(_default_root)))

# ─── FFmpeg ───
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")

# ─── whisper.cpp ───
WHISPER_CPP_PATH = os.getenv(
    "WHISPER_CPP_PATH",
    str(PROJECT_ROOT / "vendor" / "whisper.cpp" / "build" / "bin" / "whisper-cli"),
)
WHISPER_MODEL_PATH = os.getenv(
    "WHISPER_MODEL_PATH",
    str(PROJECT_ROOT / "models" / "ggml-base.bin"),
)

# ─── 硅基流动 API ───
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
SILICONFLOW_API_URL = os.getenv(
    "SILICONFLOW_API_URL",
    "https://api.siliconflow.cn/v1/chat/completions",
)
SILICONFLOW_MODEL = os.getenv("SILICONFLOW_MODEL", "deepseek-ai/DeepSeek-V3.2")

# ─── 输出目录 ───
OUTPUT_DIR = os.getenv("OUTPUT_DIR", str(PROJECT_ROOT / "output"))

# ─── Obsidian ───
OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", "")
OBSIDIAN_NOTE_DIR = os.getenv("OBSIDIAN_NOTE_DIR", "视频笔记")  # Vault 内的笔记子目录
OBSIDIAN_ATTACHMENT_DIR = os.getenv("OBSIDIAN_ATTACHMENT_DIR", "attachments")  # Vault 内的附件子目录

# ─── 支持的视频格式 ───
SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv"}

# ─── AI 总结 Prompt ───
SUMMARY_SYSTEM_PROMPT = (
    "你是一个知识萃取专家。请阅读以下短视频转录文本，以 Markdown 格式总结：\n"
    "1. **核心主题**\n"
    "2. **关键要点**（列表形式）\n"
    "3. **值得记录的金句或方法论**\n\n"
    "要求：\n"
    "- 语言精炼，保留原文关键信息\n"
    "- 使用中文输出\n"
    "- 如果转录文本中有口误或重复，请自动修正"
)

# ─── 关键帧提取 Prompt ───
KEYFRAME_SYSTEM_PROMPT = (
    "你是一个视频内容分析专家。我会给你一段带有时间戳的视频转录文本。\n"
    "请你从中提取 3~5 个最具代表性的核心知识点/关键时刻。\n\n"
    "**严格按照以下 JSON 格式返回，不要输出任何其他内容：**\n"
    "```json\n"
    "[\n"
    '  {"time": "HH:MM:SS", "title": "知识点标题", "summary": "一句话描述该片段的核心内容"},\n'
    '  {"time": "HH:MM:SS", "title": "知识点标题", "summary": "一句话描述"}\n'
    "]\n"
    "```\n\n"
    "要求：\n"
    "- time 必须是转录文本中实际出现的时间点\n"
    "- 选择信息量最大、最值得配图的时间点\n"
    "- title 简洁有力，summary 补充具体信息\n"
    "- 使用中文输出\n"
    "- 只返回 JSON，不要有前后缀说明文字"
)


def check_dependencies() -> list[str]:
    """
    检查所有必要的外部依赖是否就绪。
    返回错误信息列表，空列表表示一切正常。
    """
    errors = []

    # 检查 ffmpeg
    if os.system(f"which {FFMPEG_PATH} > /dev/null 2>&1") != 0:
        errors.append(
            f"❌ 未找到 ffmpeg，请运行: brew install ffmpeg\n"
            f"   或设置 FFMPEG_PATH 环境变量指向 ffmpeg 可执行文件"
        )

    # 检查 whisper.cpp
    if not Path(WHISPER_CPP_PATH).is_file():
        errors.append(
            f"❌ 未找到 whisper-cli: {WHISPER_CPP_PATH}\n"
            f"   请编译 whisper.cpp 或设置 WHISPER_CPP_PATH 环境变量"
        )

    # 检查模型文件
    if not Path(WHISPER_MODEL_PATH).is_file():
        errors.append(
            f"❌ 未找到 Whisper 模型文件: {WHISPER_MODEL_PATH}\n"
            f"   请下载模型或设置 WHISPER_MODEL_PATH 环境变量"
        )

    # 检查 API Key
    if not SILICONFLOW_API_KEY or SILICONFLOW_API_KEY == "your_api_key_here":
        errors.append(
            "❌ 未配置硅基流动 API Key\n"
            "   请在 .env 文件中设置 SILICONFLOW_API_KEY"
        )

    return errors
