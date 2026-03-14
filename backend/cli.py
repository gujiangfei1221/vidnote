"""
VidNote CLI 模块
支持通过命令行直接调用视频处理功能。

用法：
    api_backend process <url>           # 下载 + 完整处理
    api_backend download <url>          # 仅下载视频
    api_backend info <url>              # 获取视频信息
"""

import argparse
import json
import sys
import time
from pathlib import Path


def _print_progress(step: int, total: int, label: str, detail: str = ""):
    """终端进度输出。"""
    bar_len = 30
    filled = int(bar_len * step / total)
    bar = "█" * filled + "░" * (bar_len - filled)
    print(f"\r  [{bar}] {step}/{total} {label}  {detail}", end="", flush=True)
    if step == total:
        print()


def cmd_info(args):
    """获取视频信息。"""
    from processor.downloader import get_video_info

    try:
        info = get_video_info(args.url)
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False))
        else:
            print(f"❌ 获取视频信息失败: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps({"success": True, **info}, ensure_ascii=False, indent=2))
    else:
        print(f"  标题: {info.get('title', 'N/A')}")
        print(f"  作者: {info.get('uploader', 'N/A')}")
        print(f"  时长: {info.get('duration', 0)}s")
        print(f"  平台: {info.get('platform', 'N/A')}")


def cmd_download(args):
    """下载视频。"""
    from config import OUTPUT_DIR
    from processor.downloader import download_video

    out_dir = args.output or OUTPUT_DIR

    if not args.json:
        print(f"  下载目录: {out_dir}")

    def on_progress(percent, speed, eta):
        if not args.json:
            bar_len = 30
            filled = int(bar_len * percent / 100)
            bar = "█" * filled + "░" * (bar_len - filled)
            print(f"\r  [{bar}] {percent:.1f}% {speed} ETA {eta}  ", end="", flush=True)

    try:
        video_path = download_video(args.url, out_dir, progress_callback=on_progress)
        if not args.json:
            print(f"\n  ✅ 下载完成: {video_path}")
        else:
            print(json.dumps({"success": True, "video_path": video_path}, ensure_ascii=False, indent=2))
    except Exception as e:
        if not args.json:
            print(f"\n  ❌ 下载失败: {e}", file=sys.stderr)
        else:
            print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False))
        sys.exit(1)


def cmd_process(args):
    """完整处理流程：下载 → 音频提取 → 转录 → AI 总结 → 关键帧 → Markdown。"""
    from config import OUTPUT_DIR, WHISPER_MODEL_PATH, PROJECT_ROOT
    from processor.audio import extract_audio
    from processor.transcribe import transcribe_with_timestamps
    from processor.clean import clean_transcript
    from processor.summarize import summarize, extract_keyframes
    from processor.keyframes import capture_keyframes
    from processor.downloader import download_video
    from opencc import OpenCC

    out_dir = Path(args.output or OUTPUT_DIR).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    is_json = args.json

    start_time = time.time()

    # ── Step 0: 下载 ──
    if not is_json:
        print("\n══════════════════════════════════════")
        print(f"  VidNote - 视频知识萃取")
        print("══════════════════════════════════════\n")
        print(f"  🔗 {args.url}")
        print(f"  📁 {out_dir}\n")
        _print_progress(0, 5, "下载视频")

    def on_progress(percent, speed, eta):
        if not is_json:
            bar_len = 20
            filled = int(bar_len * percent / 100)
            bar = "█" * filled + "░" * (bar_len - filled)
            print(f"\r  [{bar}] {percent:.1f}% {speed} ETA {eta}  ", end="", flush=True)

    try:
        video_path = download_video(args.url, str(out_dir), progress_callback=on_progress)
    except Exception as e:
        if is_json:
            print(json.dumps({"success": False, "stage": "download", "error": str(e)}, ensure_ascii=False))
        else:
            print(f"\n  ❌ 下载失败: {e}", file=sys.stderr)
        sys.exit(1)

    if not is_json:
        print()

    video = Path(video_path).resolve()

    # ── Step 1: 音频提取 ──
    if not is_json:
        _print_progress(1, 5, "音频提取")
    wav_path = str(out_dir / f"{video.stem}.wav")
    wav_path = extract_audio(str(video), wav_path)

    # ── Step 2: 语音转录 ──
    if not is_json:
        _print_progress(2, 5, "语音转录")

    model_path = None
    if args.model:
        mp = PROJECT_ROOT / "models" / f"ggml-{args.model}.bin"
        if mp.is_file():
            model_path = str(mp)

    segments = transcribe_with_timestamps(wav_path, model_path=model_path, language=args.language)

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
    (out_dir / f"{video.stem}_转录.txt").write_text(clean_text, encoding="utf-8")
    (out_dir / f"{video.stem}_时间轴.txt").write_text(timestamped_text, encoding="utf-8")

    # ── Step 3: AI 总结 ──
    if not is_json:
        _print_progress(3, 5, "AI 总结")
    summary = summarize(clean_text)

    # ── Step 4: 关键帧分析 ──
    if not is_json:
        _print_progress(4, 5, "关键帧分析")
    keyframes_data = extract_keyframes(timestamped_text)

    # ── Step 5: 关键截图 ──
    if not is_json:
        _print_progress(5, 5, "关键截图")
    screenshots_dir = out_dir / f"{video.stem}_screenshots"
    enriched_keyframes = []
    if keyframes_data:
        enriched_keyframes = capture_keyframes(
            video_path=str(video),
            keyframes=keyframes_data,
            output_dir=str(screenshots_dir),
        )

    # ── 生成 Markdown ──
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

    # ── 输出结果 ──
    if is_json:
        result = {
            "success": True,
            "elapsed": round(elapsed, 1),
            "md_path": str(md_path),
            "summary": summary,
            "transcript": clean_text,
            "keyframes": [
                {
                    "time": kf.get("time", ""),
                    "title": kf.get("title", ""),
                    "summary": kf.get("summary", ""),
                    "image_path": kf.get("image_path"),
                }
                for kf in enriched_keyframes
            ],
            "output_dir": str(out_dir),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"\n══════════════════════════════════════")
        print(f"  ✅ 处理完成! 耗时 {elapsed:.1f} 秒")
        print(f"  📄 {md_path}")
        print(f"══════════════════════════════════════")
        print(f"\n{'─' * 40}")
        print(f"  📋 总结预览:")
        print(f"{'─' * 40}")
        print(summary[:500])
        if len(summary) > 500:
            print("  ...")
        print(f"{'─' * 40}\n")


def cli_main():
    """CLI 入口。"""
    parser = argparse.ArgumentParser(
        prog="vidnote",
        description="VidNote - 视频知识萃取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  vidnote info  https://bilibili.com/video/BVxxx\n"
            "  vidnote process https://bilibili.com/video/BVxxx -o ./notes\n"
            "  vidnote process https://bilibili.com/video/BVxxx --json\n"
            "  vidnote download https://bilibili.com/video/BVxxx\n"
        ),
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # ── process ──
    p_process = subparsers.add_parser("process", help="下载并处理视频（完整流程）")
    p_process.add_argument("url", help="视频链接")
    p_process.add_argument("-o", "--output", default=None, help="输出目录")
    p_process.add_argument("-l", "--language", default="auto", help="语言 (zh/en/auto)")
    p_process.add_argument("-m", "--model", default=None, help="Whisper 模型名称")
    p_process.add_argument("--json", action="store_true", help="输出 JSON 格式（供程序调用）")

    # ── download ──
    p_download = subparsers.add_parser("download", help="仅下载视频")
    p_download.add_argument("url", help="视频链接")
    p_download.add_argument("-o", "--output", default=None, help="输出目录")
    p_download.add_argument("--json", action="store_true", help="输出 JSON 格式")

    # ── info ──
    p_info = subparsers.add_parser("info", help="获取视频信息（不下载）")
    p_info.add_argument("url", help="视频链接")
    p_info.add_argument("--json", action="store_true", help="输出 JSON 格式")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    commands = {
        "process": cmd_process,
        "download": cmd_download,
        "info": cmd_info,
    }

    commands[args.command](args)
