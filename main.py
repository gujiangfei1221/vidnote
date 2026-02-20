#!/usr/bin/env python3
"""
短视频 AI 知识萃取工具
─────────────────────
输入一个短视频文件，自动：
1. 提取音频（ffmpeg）
2. 语音转文字（whisper.cpp + Metal 加速）
3. 文本清洗 + 繁简转换
4. AI 知识萃取（硅基流动 DeepSeek-V3.2）
5. 关键帧截图（ffmpeg）
6. 输出图文并茂的 Markdown 笔记（支持 Obsidian）

使用方法：
    python main.py --input video.mp4
    python main.py --input video.mp4 --model large-v3-turbo
    python main.py --watch ~/Downloads/videos
"""

import argparse
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

# 确保项目根目录在 Python 路径中
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from config import (
    check_dependencies,
    OUTPUT_DIR,
    WHISPER_MODEL_PATH,
    SUPPORTED_VIDEO_EXTENSIONS,
    PROJECT_ROOT,
    OBSIDIAN_VAULT_PATH,
    OBSIDIAN_NOTE_DIR,
    OBSIDIAN_ATTACHMENT_DIR,
)
from processor.audio import extract_audio
from processor.transcribe import transcribe, transcribe_with_timestamps
from processor.clean import clean_transcript
from processor.summarize import summarize, extract_keyframes
from processor.keyframes import capture_keyframes


def _format_seconds(seconds: float) -> str:
    """将秒数格式化为 HH:MM:SS。"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _build_timestamped_text(segments: list[dict]) -> str:
    """将分段数据构建为带时间戳的文本。"""
    lines = []
    for seg in segments:
        ts = _format_seconds(seg["start"])
        lines.append(f"[{ts}] {seg['text']}")
    return "\n".join(lines)


def _build_plain_text(segments: list[dict]) -> str:
    """将分段数据合并为纯文本。"""
    return " ".join(seg["text"] for seg in segments)


def process_video(
    video_path: str,
    model_path: str | None = None,
    output_dir: str | None = None,
    language: str = "auto",
    keep_wav: bool = False,
) -> str:
    """
    处理单个视频文件的完整流程。

    Args:
        video_path: 视频文件路径
        model_path: Whisper 模型文件路径
        output_dir: 输出目录
        language: 语言代码
        keep_wav: 是否保留中间 WAV 文件

    Returns:
        输出的 Markdown 文件路径
    """
    video = Path(video_path).resolve()
    out_dir = Path(output_dir or OUTPUT_DIR).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "═" * 60)
    print(f"📹 开始处理: {video.name}")
    print("═" * 60 + "\n")

    start_time = time.time()

    # ─── Step 1: 提取音频 ───
    wav_path = str(out_dir / f"{video.stem}.wav")
    wav_path = extract_audio(str(video), wav_path)
    print()

    # ─── Step 2: 带时间戳的语音转文字 ───
    segments = transcribe_with_timestamps(wav_path, model_path=model_path, language=language)
    print()

    # ─── Step 3: 文本清洗 ───
    plain_text = _build_plain_text(segments)
    clean_text = clean_transcript(plain_text)

    # 构建带时间戳的清洗文本（用于关键帧提取）
    timestamped_text = _build_timestamped_text(segments)
    # 对时间戳文本也做繁简转换
    from opencc import OpenCC
    _t2s = OpenCC("t2s")
    timestamped_text = _t2s.convert(timestamped_text)
    print()

    # 保存转录文本
    transcript_path = out_dir / f"{video.stem}_转录.txt"
    transcript_path.write_text(clean_text, encoding="utf-8")
    print(f"📝 转录文本已保存: {transcript_path.name}")

    # 保存带时间戳的转录（调试用）
    ts_path = out_dir / f"{video.stem}_时间轴.txt"
    ts_path.write_text(timestamped_text, encoding="utf-8")
    print(f"📝 时间轴文本已保存: {ts_path.name}")

    # ─── Step 4: AI 总结 ───
    summary = summarize(clean_text)
    print()

    # ─── Step 5: 关键帧提取 ───
    keyframes_data = extract_keyframes(timestamped_text)
    print()

    # ─── Step 6: 关键帧截图 ───
    screenshots_dir = out_dir / f"{video.stem}_screenshots"
    enriched_keyframes = []
    if keyframes_data:
        enriched_keyframes = capture_keyframes(
            video_path=str(video),
            keyframes=keyframes_data,
            output_dir=str(screenshots_dir),
        )
        print()

    # ─── Step 7: 生成 Markdown ───
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_filename = f"{video.stem}_总结_{timestamp_str}.md"
    md_path = out_dir / md_filename

    md_content = _build_markdown(
        video=video,
        model_path=model_path,
        summary=summary,
        keyframes=enriched_keyframes,
        clean_text=clean_text,
        use_obsidian_links=False,  # output 目录用标准 Markdown
    )
    md_path.write_text(md_content, encoding="utf-8")

    # ─── Step 8: 同步到 Obsidian（如果配置了）───
    obsidian_md_path = None
    if OBSIDIAN_VAULT_PATH and Path(OBSIDIAN_VAULT_PATH).is_dir():
        obsidian_md_path = _sync_to_obsidian(
            video=video,
            model_path=model_path,
            summary=summary,
            keyframes=enriched_keyframes,
            clean_text=clean_text,
            screenshots_dir=screenshots_dir,
        )

    elapsed = time.time() - start_time

    print("═" * 60)
    print(f"🎉 处理完成!")
    print(f"   耗时: {elapsed:.1f} 秒")
    print(f"   总结文件: {md_path}")
    if obsidian_md_path:
        print(f"   Obsidian: {obsidian_md_path}")
    print("═" * 60)

    # 终端显示总结预览
    print(f"\n{'─' * 40}")
    print("📋 总结预览:")
    print(f"{'─' * 40}")
    print(summary)
    print(f"{'─' * 40}\n")

    # 清理临时 WAV 文件
    if not keep_wav:
        wav_file = Path(wav_path)
        if wav_file.exists():
            wav_file.unlink()
            print(f"🗑️  已清理临时文件: {wav_file.name}")

    return str(md_path)


def _build_markdown(
    video: Path,
    model_path: str | None,
    summary: str,
    keyframes: list[dict],
    clean_text: str,
    use_obsidian_links: bool = False,
    attachment_subdir: str = "",
) -> str:
    """构建 Markdown 文档内容。"""
    model_name = Path(model_path or WHISPER_MODEL_PATH).stem.replace("ggml-", "")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"# 📹 {video.stem}\n",
        f"> 生成时间: {now}  ",
        f"> 源文件: `{video.name}`  ",
        f"> 模型: whisper ({model_name})\n",
        "---\n",
        summary,
        "",
    ]

    # 关键帧部分
    if keyframes:
        lines.append("\n---\n")
        lines.append("## 📸 关键时刻\n")

        for i, kf in enumerate(keyframes, 1):
            ts = kf.get("time", "")
            title = kf.get("title", "")
            desc = kf.get("summary", "")
            img_filename = kf.get("image_filename")

            lines.append(f"### 🔑 {i}. {title}")
            lines.append(f"> **{desc}**\n")

            if img_filename:
                if use_obsidian_links:
                    # Obsidian 双链 wikilink 格式
                    lines.append(f"![[{attachment_subdir}/{img_filename}]]")
                else:
                    # 标准 Markdown 图片引用
                    lines.append(f"![{title}]({video.stem}_screenshots/{img_filename})")

            lines.append(f"*⏱️ 时间戳: {ts}*\n")

    # 原始转录
    lines.extend([
        "\n---\n",
        "## 📜 原始转录文本\n",
        "<details>",
        "<summary>点击展开完整转录</summary>\n",
        clean_text,
        "\n</details>",
    ])

    return "\n".join(lines)


def _sync_to_obsidian(
    video: Path,
    model_path: str | None,
    summary: str,
    keyframes: list[dict],
    clean_text: str,
    screenshots_dir: Path,
) -> str | None:
    """
    将笔记和截图同步到 Obsidian Vault。
    """
    vault_path = Path(OBSIDIAN_VAULT_PATH)
    note_dir = vault_path / OBSIDIAN_NOTE_DIR
    note_dir.mkdir(parents=True, exist_ok=True)

    # 附件目录
    attachment_base = vault_path / OBSIDIAN_ATTACHMENT_DIR
    attachment_dir = attachment_base / video.stem
    attachment_dir.mkdir(parents=True, exist_ok=True)

    print(f"📂 同步到 Obsidian Vault...")
    print(f"   笔记目录: {note_dir}")
    print(f"   附件目录: {attachment_dir}")

    # 复制截图到 Obsidian 附件目录
    if screenshots_dir.is_dir():
        for img_file in screenshots_dir.glob("*.jpg"):
            dest = attachment_dir / img_file.name
            shutil.copy2(img_file, dest)

    # 构建 Obsidian 相对路径
    # Obsidian wikilink 使用相对于 vault 的路径
    rel_attachment = f"{OBSIDIAN_ATTACHMENT_DIR}/{video.stem}"

    # 生成 Obsidian 格式的 Markdown
    md_content = _build_markdown(
        video=video,
        model_path=model_path,
        summary=summary,
        keyframes=keyframes,
        clean_text=clean_text,
        use_obsidian_links=True,
        attachment_subdir=rel_attachment,
    )

    md_path = note_dir / f"{video.stem}.md"
    md_path.write_text(md_content, encoding="utf-8")

    print(f"✅ Obsidian 笔记已同步: {md_path.name}")

    return str(md_path)


def main():
    parser = argparse.ArgumentParser(
        description="🎬 短视频 AI 知识萃取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  python main.py --input video.mp4\n"
            "  python main.py --input video.mp4 --model large-v3-turbo\n"
            "  python main.py --input video.mp4 --language zh\n"
            "  python main.py --watch ~/Downloads/videos\n"
        ),
    )

    parser.add_argument(
        "--input", "-i",
        type=str,
        help="输入视频文件路径",
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        default=None,
        help="Whisper 模型名称 (base/small/medium/large-v3-turbo)，默认使用配置中的模型",
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default=None,
        help=f"输出目录，默认: {OUTPUT_DIR}",
    )
    parser.add_argument(
        "--language", "-l",
        type=str,
        default="auto",
        help="语言代码 (zh/en/ja/auto)，默认: auto (自动检测)",
    )
    parser.add_argument(
        "--keep-wav",
        action="store_true",
        help="保留中间生成的 WAV 文件",
    )
    parser.add_argument(
        "--watch", "-w",
        type=str,
        default=None,
        help="监听模式：监控指定目录，自动处理新增视频文件",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="仅检查依赖是否就绪",
    )

    args = parser.parse_args()

    # ─── 仅检查依赖 ───
    if args.check:
        print("🔍 检查依赖状态...\n")
        errors = check_dependencies()
        if errors:
            for err in errors:
                print(err)
                print()
            sys.exit(1)
        else:
            print("✅ 所有依赖均已就绪!")
            if OBSIDIAN_VAULT_PATH:
                print(f"📂 Obsidian Vault: {OBSIDIAN_VAULT_PATH}")
            else:
                print("ℹ️  Obsidian 未配置（可选，在 .env 中设置 OBSIDIAN_VAULT_PATH）")
            sys.exit(0)

    # ─── 监听模式 ───
    if args.watch:
        errors = check_dependencies()
        if errors:
            print("❌ 依赖检查未通过:\n")
            for err in errors:
                print(err)
                print()
            sys.exit(1)

        from watcher import start_watching

        model_path = _resolve_model_path(args.model)
        start_watching(
            watch_dir=args.watch,
            model_path=model_path,
            output_dir=args.output_dir,
            language=args.language,
        )
        return

    # ─── 单文件处理模式 ───
    if not args.input:
        parser.print_help()
        print("\n❌ 请指定输入视频文件: --input video.mp4")
        sys.exit(1)

    errors = check_dependencies()
    if errors:
        print("❌ 依赖检查未通过:\n")
        for err in errors:
            print(err)
            print()
        sys.exit(1)

    input_path = Path(args.input).resolve()
    if not input_path.is_file():
        print(f"❌ 视频文件不存在: {input_path}")
        sys.exit(1)

    if input_path.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
        print(
            f"⚠️  文件格式 '{input_path.suffix}' 可能不受支持。"
            f"支持的格式: {', '.join(SUPPORTED_VIDEO_EXTENSIONS)}"
        )

    model_path = _resolve_model_path(args.model)

    try:
        process_video(
            video_path=str(input_path),
            model_path=model_path,
            output_dir=args.output_dir,
            language=args.language,
            keep_wav=args.keep_wav,
        )
    except Exception as e:
        print(f"\n❌ 处理失败: {e}")
        sys.exit(1)


def _resolve_model_path(model_name: str | None) -> str | None:
    """将模型名称解析为完整路径。"""
    if model_name is None:
        return None

    if Path(model_name).is_file():
        return model_name

    model_path = PROJECT_ROOT / "models" / f"ggml-{model_name}.bin"
    if model_path.is_file():
        return str(model_path)

    print(f"⚠️  模型文件未找到: {model_path}")
    print(f"   将使用默认模型: {WHISPER_MODEL_PATH}")
    return None


if __name__ == "__main__":
    main()
