#!/usr/bin/env python3
"""
Electron 桌面应用的 Python 后端接口。
通过 stdin/stdout 以 JSON 格式与 Electron 主进程通信。

协议：
- 输入：每行一条 JSON 命令
- 输出：每行一条 JSON 事件（进度/结果/错误）
"""

import json
import sys
import time
import os
import importlib
import io
from pathlib import Path

# 确保项目根目录在 Python 路径中
sys.path.insert(0, str(Path(__file__).parent.resolve()))

# Windows 下强制 stdout/stderr 使用 UTF-8，避免 GBK 编码导致 emoji/中文崩溃
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def emit(event_type: str, **data):
    """向 stdout 输出一条 JSON 事件。"""
    msg = {"type": event_type, **data}
    # ensure_ascii=True：中文转为 \uXXXX 纯 ASCII 序列
    # 彻底避免 Windows stdout 编码(GBK/cp936)导致乱码
    line = json.dumps(msg, ensure_ascii=True)
    sys.stdout.buffer.write((line + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


def reload_config():
    """重新加载配置模块，让当前后端进程立即读取最新 .env。"""
    import config as config_module
    return importlib.reload(config_module)


def handle_check_deps(params: dict):
    """检查依赖状态。"""
    reload_config()
    from config import check_dependencies, WHISPER_MODEL_PATH, WHISPER_CPP_PATH, FFMPEG_PATH
    errors = check_dependencies()
    emit("deps_result",
         ok=len(errors) == 0,
         errors=errors,
         paths={
             "ffmpeg": FFMPEG_PATH,
             "whisper_cpp": WHISPER_CPP_PATH,
             "whisper_model": WHISPER_MODEL_PATH,
         })


def handle_get_video_info(params: dict):
    """获取视频基本信息（不下载）。"""
    url = params.get("url", "")
    if not url:
        emit("error", message="请提供视频链接")
        return
    try:
        from processor.downloader import get_video_info
        info = get_video_info(url)
        emit("video_info", **info)
    except Exception as e:
        emit("error", message=str(e))


def handle_download_video(params: dict):
    """下载视频并返回本地路径。"""
    url = params.get("url", "")
    output_dir = params.get("output_dir", None)

    if not url:
        emit("error", message="请提供视频链接")
        return

    try:
        from config import OUTPUT_DIR
        from processor.downloader import download_video

        out_dir = output_dir or OUTPUT_DIR
        emit("download_progress", percent=0, speed="", eta="", detail="正在解析视频链接...")

        def on_progress(percent, speed, eta):
            emit("download_progress",
                 percent=round(percent, 1),
                 speed=speed,
                 eta=eta,
                 detail=f"下载中 {percent:.1f}% · {speed} · 剩余 {eta}")

        video_path = download_video(url, out_dir, progress_callback=on_progress)
        emit("download_done", video_path=video_path, success=True)

    except Exception as e:
        emit("error", message=str(e))


def handle_process_video(params: dict):
    """处理视频文件。"""
    video_path = params.get("video_path", "")
    language = params.get("language", "auto")
    model_name = params.get("model", None)
    output_dir = params.get("output_dir", None)

    if not video_path or not Path(video_path).is_file():
        emit("error", message=f"视频文件不存在: {video_path}")
        return

    try:
        from config import OUTPUT_DIR, WHISPER_MODEL_PATH, PROJECT_ROOT
        from processor.audio import extract_audio
        from processor.transcribe import transcribe_with_timestamps
        from processor.clean import clean_transcript
        from processor.summarize import summarize, extract_keyframes
        from processor.keyframes import capture_keyframes
        from opencc import OpenCC

        video = Path(video_path).resolve()
        out_dir = Path(output_dir or OUTPUT_DIR).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)

        # 解析模型路径
        model_path = None
        if model_name:
            mp = PROJECT_ROOT / "models" / f"ggml-{model_name}.bin"
            if mp.is_file():
                model_path = str(mp)

        start_time = time.time()

        # Step 1: 音频提取
        emit("progress", step=1, total=5, label="音频提取", detail="正在从视频中提取音频...")
        wav_path = str(out_dir / f"{video.stem}.wav")
        wav_path = extract_audio(str(video), wav_path)

        # Step 2: 语音转录
        emit("progress", step=2, total=5, label="语音转录", detail="正在使用 whisper.cpp 转录...")
        segments = transcribe_with_timestamps(wav_path, model_path=model_path, language=language)

        # 构建文本
        _t2s = OpenCC("t2s")

        plain_text = " ".join(seg["text"] for seg in segments)
        clean_text = clean_transcript(plain_text)

        ts_lines = []
        for seg in segments:
            h = int(seg["start"] // 3600)
            m = int((seg["start"] % 3600) // 60)
            s = int(seg["start"] % 60)
            ts_lines.append(f"[{h:02d}:{m:02d}:{s:02d}] {seg['text']}")
        timestamped_text = _t2s.convert("\n".join(ts_lines))

        # 保存转录文本
        transcript_path = out_dir / f"{video.stem}_转录.txt"
        transcript_path.write_text(clean_text, encoding="utf-8")

        ts_path = out_dir / f"{video.stem}_时间轴.txt"
        ts_path.write_text(timestamped_text, encoding="utf-8")

        # Step 3: AI 总结
        emit("progress", step=3, total=5, label="AI 总结", detail="正在调用 AI 进行知识萃取...")
        summary = summarize(clean_text)

        # Step 4: 关键帧提取
        emit("progress", step=4, total=5, label="关键帧分析", detail="正在分析关键时间点...")
        keyframes_data = extract_keyframes(timestamped_text)

        # Step 5: 截图
        emit("progress", step=5, total=5, label="关键截图", detail="正在截取关键帧画面...")
        screenshots_dir = out_dir / f"{video.stem}_screenshots"
        enriched_keyframes = []
        if keyframes_data:
            enriched_keyframes = capture_keyframes(
                video_path=str(video),
                keyframes=keyframes_data,
                output_dir=str(screenshots_dir),
            )

        # 生成 Markdown
        from datetime import datetime
        model_display = Path(model_path or WHISPER_MODEL_PATH).stem.replace("ggml-", "")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

        md_lines = [
            f"# 📹 {video.stem}\n",
            f"> 生成时间: {now}  ",
            f"> 源文件: `{video.name}`  ",
            f"> 模型: whisper ({model_display})\n",
            "---\n",
            summary,
            "",
        ]

        if enriched_keyframes:
            md_lines.append("\n---\n")
            md_lines.append("## 📸 关键时刻\n")
            for i, kf in enumerate(enriched_keyframes, 1):
                ts = kf.get("time", "")
                title = kf.get("title", "")
                desc = kf.get("summary", "")
                img_filename = kf.get("image_filename")
                md_lines.append(f"### 🔑 {i}. {title}")
                md_lines.append(f"> **{desc}**\n")
                if img_filename:
                    md_lines.append(f"![{title}]({video.stem}_screenshots/{img_filename})")
                md_lines.append(f"*⏱️ 时间戳: {ts}*\n")

        md_lines.extend([
            "\n---\n",
            "## 📜 原始转录文本\n",
            "<details>",
            "<summary>点击展开完整转录</summary>\n",
            clean_text,
            "\n</details>",
        ])

        md_content = "\n".join(md_lines)
        md_filename = f"{video.stem}_总结_{timestamp_str}.md"
        md_path = out_dir / md_filename
        md_path.write_text(md_content, encoding="utf-8")

        # 清理临时 WAV
        wav_file = Path(wav_path)
        if wav_file.exists():
            wav_file.unlink()

        elapsed = time.time() - start_time

        # 返回结果
        emit("result",
             success=True,
             elapsed=round(elapsed, 1),
             md_path=str(md_path),
             md_content=md_content,
             summary=summary,
             transcript=clean_text,
             keyframes=[
                 {
                     "time": kf.get("time", ""),
                     "title": kf.get("title", ""),
                     "summary": kf.get("summary", ""),
                     "image_path": kf.get("image_path"),
                 }
                 for kf in enriched_keyframes
             ],
             output_dir=str(out_dir))

    except Exception as e:
        emit("error", message=str(e))


def handle_save_config(params: dict):
    """保存用户配置到 .env 文件。"""
    reload_config()
    from config import PROJECT_ROOT
    env_path = PROJECT_ROOT / ".env"
    env_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    for key, value in params.items():
        if key.startswith("_"):
            continue
        lines.append(f"{key}={value}")

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    reload_config()
    emit("config_saved", ok=True)


def handle_load_config(params: dict):
    """读取当前配置。"""
    reload_config()
    from config import (
        SILICONFLOW_API_KEY, SILICONFLOW_MODEL,
        WHISPER_MODEL_PATH, WHISPER_CPP_PATH,
        FFMPEG_PATH, OUTPUT_DIR, PROJECT_ROOT,
    )

    # 列出可用模型
    models_dir = PROJECT_ROOT / "models"
    available_models = []
    if models_dir.is_dir():
        for f in models_dir.glob("ggml-*.bin"):
            name = f.stem.replace("ggml-", "")
            size_mb = f.stat().st_size / (1024 * 1024)
            available_models.append({"name": name, "size_mb": round(size_mb, 1)})

    emit("config",
         SILICONFLOW_API_KEY=SILICONFLOW_API_KEY,
         SILICONFLOW_MODEL=SILICONFLOW_MODEL,
         WHISPER_MODEL_PATH=WHISPER_MODEL_PATH,
         WHISPER_CPP_PATH=WHISPER_CPP_PATH,
         FFMPEG_PATH=FFMPEG_PATH,
         OUTPUT_DIR=OUTPUT_DIR,
         available_models=available_models)


def handle_list_history(params: dict):
    """列出历史处理记录。"""
    from config import OUTPUT_DIR
    out_dir = Path(params.get("output_dir", OUTPUT_DIR))

    records = []
    if out_dir.is_dir():
        for md_file in sorted(out_dir.glob("*_总结_*.md"), reverse=True):
            stat = md_file.stat()
            # 读取前几行获取摘要
            try:
                content = md_file.read_text(encoding="utf-8")
                title = md_file.stem.rsplit("_总结_", 1)[0]
            except Exception:
                title = md_file.stem
                content = ""

            # 检查是否有截图目录
            screenshots_dir = out_dir / f"{title}_screenshots"
            screenshot_count = len(list(screenshots_dir.glob("*.jpg"))) if screenshots_dir.is_dir() else 0

            records.append({
                "filename": md_file.name,
                "title": title,
                "path": str(md_file),
                "size_kb": round(stat.st_size / 1024, 1),
                "modified": stat.st_mtime,
                "screenshot_count": screenshot_count,
                "content": content,
            })

    emit("history", records=records)


def api_main():
    """Electron JSON API 模式：从 stdin 读取 JSON 命令并分发处理。"""
    emit("ready", message="Python 后端已就绪")

    handlers = {
        "check_deps": handle_check_deps,
        "process_video": handle_process_video,
        "save_config": handle_save_config,
        "load_config": handle_load_config,
        "list_history": handle_list_history,
        "download_video": handle_download_video,
        "get_video_info": handle_get_video_info,
    }

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            cmd = json.loads(line)
            action = cmd.get("action", "")
            params = cmd.get("params", {})

            handler = handlers.get(action)
            if handler:
                handler(params)
            else:
                emit("error", message=f"未知命令: {action}")

        except json.JSONDecodeError as e:
            emit("error", message=f"JSON 解析失败: {e}")
        except Exception as e:
            emit("error", message=f"处理异常: {e}")


def main():
    """入口分流：有命令行参数 → CLI 模式，无参数 → Electron JSON API 模式。"""
    if len(sys.argv) > 1:
        from cli import cli_main
        cli_main()
    else:
        api_main()


if __name__ == "__main__":
    main()

