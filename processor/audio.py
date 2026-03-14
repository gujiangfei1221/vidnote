"""
音频提取模块
使用 ffmpeg 从视频文件中提取音频，转为 whisper.cpp 标准输入格式。
"""

import subprocess
import shlex
from pathlib import Path

from config import FFMPEG_PATH


def extract_audio(video_path: str, output_wav: str | None = None) -> str:
    """
    从视频文件提取音频，转为 16kHz mono WAV 格式。

    Args:
        video_path: 视频文件路径
        output_wav: 输出 WAV 文件路径（可选，默认在同目录生成）

    Returns:
        生成的 WAV 文件路径

    Raises:
        FileNotFoundError: 视频文件不存在
        RuntimeError: ffmpeg 执行失败
    """
    video = Path(video_path).resolve()

    if not video.is_file():
        raise FileNotFoundError(f"视频文件不存在: {video}")

    if output_wav is None:
        output_wav = str(video.with_suffix(".wav"))

    # 构建 ffmpeg 命令
    # -y: 覆盖输出文件
    # -i: 输入文件
    # -ar 16000: 采样率 16kHz
    # -ac 1: 单声道
    # -c:a pcm_s16le: 16-bit PCM 编码
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", str(video),
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        str(output_wav),
    ]

    print(f"[audio] Extracting audio: {video.name}")
    print(f"[audio] Command: {shlex.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5分钟超时
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg 执行失败 (退出码: {result.returncode})\n"
                f"错误信息: {result.stderr}"
            )

        output_file = Path(output_wav)
        size_mb = output_file.stat().st_size / (1024 * 1024)
        print(f"[audio] Done: {output_file.name} ({size_mb:.1f} MB)")

        return str(output_file)

    except FileNotFoundError:
        raise RuntimeError(
            f"未找到 ffmpeg: {FFMPEG_PATH}\n"
            f"请运行: brew install ffmpeg"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("ffmpeg 执行超时（超过5分钟），请检查视频文件")
