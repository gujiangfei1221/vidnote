"""
视频下载模块
使用 yt-dlp 从小红书、B站、抖音、YouTube 等平台下载视频。
"""

import subprocess
import re
import sys
from pathlib import Path


# 支持的平台示例（yt-dlp 实际支持超过 1000 个平台）
SUPPORTED_PLATFORMS = {
    "xhs": "小红书 (xiaohongshu.com / xhslink.com)",
    "bilibili": "哔哩哔哩 (bilibili.com)",
    "douyin": "抖音 (douyin.com / iesdouyin.com)",
    "youtube": "YouTube (youtube.com / youtu.be)",
    "twitter": "X/Twitter (twitter.com / x.com)",
}


def _get_ytdlp_path() -> str:
    """获取 yt-dlp 可执行文件路径。"""
    # 优先使用当前 Python 环境中的 yt-dlp
    python_dir = Path(sys.executable).parent
    candidates = [
        str(python_dir / "yt-dlp"),
        "/opt/miniconda3/envs/asragent/bin/yt-dlp",
        "/opt/miniforge3/envs/asragent/bin/yt-dlp",
        "yt-dlp",
    ]
    for p in candidates:
        if Path(p).is_file():
            return p
    return "yt-dlp"


def get_video_info(url: str) -> dict:
    """
    获取视频基本信息（标题、时长等），不下载文件。

    Args:
        url: 视频链接

    Returns:
        {"title": str, "duration": int, "thumbnail": str, "uploader": str}
    """
    ytdlp = _get_ytdlp_path()
    cmd = [
        ytdlp,
        "--dump-json",
        "--no-playlist",
        "--no-warnings",
        url,
    ]

    result = subprocess.run(cmd, capture_output=True, timeout=30)
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"获取视频信息失败: {stderr[:300]}")

    import json
    data = json.loads(result.stdout.decode("utf-8", errors="ignore"))
    return {
        "title": data.get("title", "未知标题"),
        "duration": data.get("duration", 0),
        "thumbnail": data.get("thumbnail", ""),
        "uploader": data.get("uploader", ""),
        "ext": data.get("ext", "mp4"),
    }


def download_video(
    url: str,
    output_dir: str,
    progress_callback=None,
) -> str:
    """
    使用 yt-dlp 下载视频。

    Args:
        url: 视频链接（支持小红书、B站、抖音、YouTube 等）
        output_dir: 输出目录
        progress_callback: 进度回调函数(percent: float, speed: str, eta: str)

    Returns:
        下载后的视频文件路径

    Raises:
        RuntimeError: 下载失败
    """
    ytdlp = _get_ytdlp_path()
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 输出文件模板：标题.扩展名
    output_template = str(out_dir / "%(title)s.%(ext)s")

    cmd = [
        ytdlp,
        "--no-playlist",          # 不下载播放列表
        "--no-warnings",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",  # 优先 mp4
        "--merge-output-format", "mp4",
        "--output", output_template,
        "--newline",              # 每行输出进度（便于解析）
        url,
    ]

    print(f"[downloader] cmd: {' '.join(cmd)}")

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
        )

        downloaded_file = None

        for line in process.stdout:
            line = line.strip()
            if not line:
                continue

            print(f"[yt-dlp] {line}")

            # 解析下载进度: [download]  45.2% of   50.00MiB at   1.23MiB/s ETA 00:27
            progress_match = re.match(
                r"\[download\]\s+([\d.]+)%\s+of\s+[\d.]+\S+\s+at\s+([\d.]+\S+)\s+ETA\s+(\S+)",
                line
            )
            if progress_match and progress_callback:
                percent = float(progress_match.group(1))
                speed = progress_match.group(2)
                eta = progress_match.group(3)
                progress_callback(percent, speed, eta)

            # 解析最终文件路径
            # [Merger] Merging formats into "path/to/file.mp4"
            merge_match = re.search(r'Merging formats into "(.+?)"', line)
            if merge_match:
                downloaded_file = merge_match.group(1)

            # [download] Destination: path/to/file.mp4
            dest_match = re.search(r'\[download\] Destination: (.+)', line)
            if dest_match:
                downloaded_file = dest_match.group(1).strip()

            # Already downloaded
            already_match = re.search(r'\[download\] (.+) has already been downloaded', line)
            if already_match:
                downloaded_file = already_match.group(1).strip()

        process.wait()

        if process.returncode != 0:
            raise RuntimeError(f"yt-dlp 下载失败（退出码 {process.returncode}）")

        # 如果没有从输出中捕获到路径，扫描目录找最新文件
        if not downloaded_file or not Path(downloaded_file).is_file():
            mp4_files = sorted(out_dir.glob("*.mp4"), key=lambda f: f.stat().st_mtime)
            if mp4_files:
                downloaded_file = str(mp4_files[-1])

        if not downloaded_file or not Path(downloaded_file).is_file():
            raise RuntimeError("下载完成但找不到视频文件，请检查输出目录")

        return downloaded_file

    except FileNotFoundError:
        raise RuntimeError(
            "未找到 yt-dlp 命令\n"
            "请运行: conda activate asragent && pip install yt-dlp"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("下载超时")
