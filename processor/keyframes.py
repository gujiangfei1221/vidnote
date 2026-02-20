"""
关键帧截图模块
使用 ffmpeg 从视频中截取关键时间点的画面。
"""

import subprocess
import shlex
from pathlib import Path

from config import FFMPEG_PATH


def capture_frame(
    video_path: str,
    timestamp: str,
    output_path: str,
) -> str | None:
    """
    使用 ffmpeg 从视频的指定时间点截取一帧画面。

    Args:
        video_path: 视频文件路径
        timestamp: 时间戳 (HH:MM:SS 格式)
        output_path: 输出图片路径

    Returns:
        成功返回图片路径，失败返回 None
    """
    cmd = [
        FFMPEG_PATH,
        "-ss", timestamp,
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",  # 高质量
        "-y",         # 覆盖已有文件
        str(output_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            print(f"   ⚠️  截图失败 [{timestamp}]: {result.stderr[:200]}")
            return None

        if Path(output_path).is_file() and Path(output_path).stat().st_size > 0:
            return str(output_path)
        else:
            print(f"   ⚠️  截图文件为空 [{timestamp}]")
            return None

    except Exception as e:
        print(f"   ⚠️  截图异常 [{timestamp}]: {e}")
        return None


def capture_keyframes(
    video_path: str,
    keyframes: list[dict],
    output_dir: str,
) -> list[dict]:
    """
    批量截取关键帧画面。

    Args:
        video_path: 视频文件路径
        keyframes: AI 返回的关键帧列表 [{"time": "HH:MM:SS", "title": "...", "summary": "..."}, ...]
        output_dir: 截图输出目录

    Returns:
        增强后的关键帧列表（新增 "image_path" 字段）
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    video_name = Path(video_path).stem
    print(f"📸 正在截取 {len(keyframes)} 个关键帧...")

    results = []
    for i, kf in enumerate(keyframes):
        timestamp = kf.get("time", "00:00:00")
        # 文件名: 时间戳转为安全格式
        safe_time = timestamp.replace(":", "_")
        img_filename = f"{video_name}_{safe_time}.jpg"
        img_path = out_dir / img_filename

        result = capture_frame(video_path, timestamp, str(img_path))

        kf_copy = dict(kf)
        if result:
            kf_copy["image_path"] = str(img_path)
            kf_copy["image_filename"] = img_filename
            print(f"   ✅ [{timestamp}] {kf.get('title', '')}")
        else:
            kf_copy["image_path"] = None
            kf_copy["image_filename"] = None

        results.append(kf_copy)

    success_count = sum(1 for r in results if r["image_path"])
    print(f"📸 截图完成: {success_count}/{len(keyframes)} 成功")

    return results
