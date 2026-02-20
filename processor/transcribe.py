"""
语音转文字模块
调用本地编译的 whisper.cpp 进行语音识别。
"""

import re
import subprocess
import shlex
from pathlib import Path

from config import WHISPER_CPP_PATH, WHISPER_MODEL_PATH

# ANSI 转义序列的字节模式（用于在解码前剥离颜色代码）
_ANSI_ESCAPE_BYTES = re.compile(rb"\x1b\[[0-9;]*m")


def transcribe(
    wav_path: str,
    model_path: str | None = None,
    language: str = "auto",
) -> str:
    """
    使用 whisper.cpp 将 WAV 音频转录为文字。

    Args:
        wav_path: WAV 音频文件路径（16kHz, mono）
        model_path: Whisper 模型文件路径（可选，使用默认配置）
        language: 语言代码，默认 "auto" 自动检测

    Returns:
        转录的原始文本

    Raises:
        FileNotFoundError: WAV 文件或模型不存在
        RuntimeError: whisper.cpp 执行失败
    """
    wav = Path(wav_path).resolve()
    model = Path(model_path or WHISPER_MODEL_PATH).resolve()

    if not wav.is_file():
        raise FileNotFoundError(f"音频文件不存在: {wav}")

    if not model.is_file():
        raise FileNotFoundError(
            f"Whisper 模型不存在: {model}\n"
            f"请下载模型文件到 models/ 目录"
        )

    # 构建 whisper.cpp 命令
    cmd = [
        WHISPER_CPP_PATH,
        "-m", str(model),
        "-f", str(wav),
        "-l", language,
        "--no-timestamps",       # 不输出时间戳
        "-t", "4",               # 线程数
        "-np",                   # --no-prints: 禁用额外日志输出
    ]

    print(f"🎙️  正在转录音频: {wav.name}")
    model_name = model.stem.replace("ggml-", "")
    print(f"   模型: {model_name} | 语言: {language}")
    print(f"   命令: {shlex.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=600,  # 10分钟超时
        )

        # 先剥离 ANSI 转义序列的原始字节，再解码为 UTF-8
        clean_stdout = _ANSI_ESCAPE_BYTES.sub(b"", result.stdout)
        stdout_text = clean_stdout.decode("utf-8", errors="ignore")
        stderr_text = result.stderr.decode("utf-8", errors="replace")

        if result.returncode != 0:
            raise RuntimeError(
                f"whisper.cpp 执行失败 (退出码: {result.returncode})\n"
                f"错误信息: {stderr_text}"
            )

        # whisper.cpp 将转录内容输出到 stdout
        transcript = stdout_text.strip()

        if not transcript:
            # 尝试从 stderr 检查是否有有用信息
            print(f"⚠️  转录结果为空，whisper stderr: {stderr_text[:500]}")
            return ""

        word_count = len(transcript)
        print(f"✅ 转录完成: {word_count} 个字符")

        return transcript

    except FileNotFoundError:
        raise RuntimeError(
            f"未找到 whisper-cli: {WHISPER_CPP_PATH}\n"
            f"请编译 whisper.cpp 或设置 WHISPER_CPP_PATH 环境变量"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("whisper.cpp 执行超时（超过10分钟），请考虑使用更小的模型")
