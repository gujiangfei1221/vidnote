"""
视频下载模块
使用 yt-dlp Python API 从小红书、B站、抖音、YouTube 等平台下载视频。
"""

from pathlib import Path

from config import FFMPEG_PATH


# 支持的平台示例（yt-dlp 实际支持超过 1000 个平台）
SUPPORTED_PLATFORMS = {
    "xhs": "小红书 (xiaohongshu.com / xhslink.com)",
    "bilibili": "哔哩哔哩 (bilibili.com)",
    "douyin": "抖音 (douyin.com / iesdouyin.com)",
    "youtube": "YouTube (youtube.com / youtu.be)",
    "twitter": "X/Twitter (twitter.com / x.com)",
}


def _load_ytdlp():
    """懒加载 yt-dlp，避免未使用下载功能时提前失败。"""
    try:
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import DownloadError
        return YoutubeDL, DownloadError
    except Exception as exc:
        raise RuntimeError(
            "未安装 yt-dlp Python 模块\n"
            "请运行: pip install yt-dlp"
        ) from exc


def _build_progress_hook(progress_callback):
    if not progress_callback:
        return None

    def hook(status):
        if status.get("status") == "downloading":
            total = status.get("total_bytes") or status.get("total_bytes_estimate") or 0
            downloaded = status.get("downloaded_bytes") or 0
            percent = (downloaded / total * 100.0) if total else 0.0
            speed = status.get("_speed_str") or "未知速度"
            eta = status.get("_eta_str") or "--:--"
            progress_callback(percent, speed, eta)
        elif status.get("status") == "finished":
            progress_callback(100.0, "", "00:00")

    return hook


def _common_opts() -> dict:
    return {
        "noplaylist": True,
        "no_warnings": True,
        "quiet": True,
        "ffmpeg_location": FFMPEG_PATH,
    }


def _resolve_downloaded_file(info: dict, output_dir: Path, ydl) -> str | None:
    candidates = []

    for item in info.get("requested_downloads", []):
        filepath = item.get("filepath")
        if filepath:
            candidates.append(Path(filepath))

    for key in ("filepath", "_filename"):
        value = info.get(key)
        if value:
            candidates.append(Path(value))

    try:
        prepared = Path(ydl.prepare_filename(info))
        candidates.append(prepared)
        candidates.append(prepared.with_suffix(".mp4"))
    except Exception:
        pass

    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)

    mp4_files = sorted(output_dir.glob("*.mp4"), key=lambda f: f.stat().st_mtime)
    if mp4_files:
        return str(mp4_files[-1])

    all_files = sorted((f for f in output_dir.iterdir() if f.is_file()), key=lambda f: f.stat().st_mtime)
    if all_files:
        return str(all_files[-1])

    return None


def get_video_info(url: str) -> dict:
    """
    获取视频基本信息（标题、时长等），不下载文件。

    Args:
        url: 视频链接

    Returns:
        {"title": str, "duration": int, "thumbnail": str, "uploader": str}
    """
    YoutubeDL, DownloadError = _load_ytdlp()
    opts = {
        **_common_opts(),
        "skip_download": True,
    }

    try:
        with YoutubeDL(opts) as ydl:
            data = ydl.extract_info(url, download=False)
    except DownloadError as exc:
        raise RuntimeError(f"获取视频信息失败: {exc}") from exc

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
    YoutubeDL, DownloadError = _load_ytdlp()
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    opts = {
        **_common_opts(),
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "outtmpl": str(out_dir / "%(title)s.%(ext)s"),
    }

    hook = _build_progress_hook(progress_callback)
    if hook:
        opts["progress_hooks"] = [hook]

    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = _resolve_downloaded_file(info, out_dir, ydl)
    except DownloadError as exc:
        raise RuntimeError(f"yt-dlp 下载失败: {exc}") from exc

    if not downloaded_file:
        raise RuntimeError("下载完成但找不到视频文件，请检查输出目录")

    return downloaded_file
