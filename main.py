#!/usr/bin/env python3
"""
短视频 AI 知识萃取工具
─────────────────────
输入一个短视频文件，自动：
1. 提取音频（ffmpeg）
2. 语音转文字（whisper.cpp + Metal 加速）
3. 文本清洗
4. AI 知识萃取（硅基流动 DeepSeek-V3.2）
5. 输出 Markdown 总结

使用方法：
    python main.py --input video.mp4
    python main.py --input video.mp4 --model large-v3-turbo
    python main.py --watch ~/Downloads/videos
"""

import argparse
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
)
from processor.audio import extract_audio
from processor.transcribe import transcribe
from processor.clean import clean_transcript
from processor.summarize import summarize


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

    # ─── Step 2: 语音转文字 ───
    raw_text = transcribe(wav_path, model_path=model_path, language=language)
    print()

    # ─── Step 3: 文本清洗 ───
    clean_text = clean_transcript(raw_text)
    print()

    # 保存转录文本（用于调试）
    transcript_path = out_dir / f"{video.stem}_转录.txt"
    transcript_path.write_text(clean_text, encoding="utf-8")
    print(f"📝 转录文本已保存: {transcript_path.name}")

    # ─── Step 4: AI 总结 ───
    summary = summarize(clean_text)
    print()

    # ─── Step 5: 输出结果 ───
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_filename = f"{video.stem}_总结_{timestamp}.md"
    md_path = out_dir / md_filename

    # 构建完整的 Markdown 文档
    md_content = (
        f"# 📹 {video.stem}\n\n"
        f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n"
        f"> 源文件: `{video.name}`  \n"
        f"> 模型: whisper ({Path(model_path or WHISPER_MODEL_PATH).stem.replace('ggml-', '')})\n\n"
        f"---\n\n"
        f"{summary}\n\n"
        f"---\n\n"
        f"## 📜 原始转录文本\n\n"
        f"<details>\n"
        f"<summary>点击展开完整转录</summary>\n\n"
        f"{clean_text}\n\n"
        f"</details>\n"
    )

    md_path.write_text(md_content, encoding="utf-8")

    elapsed = time.time() - start_time

    print("═" * 60)
    print(f"🎉 处理完成!")
    print(f"   耗时: {elapsed:.1f} 秒")
    print(f"   总结文件: {md_path}")
    print("═" * 60)

    # 在终端显示总结预览
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
            sys.exit(0)

    # ─── 监听模式 ───
    if args.watch:
        # 先检查依赖
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

    # 检查依赖
    errors = check_dependencies()
    if errors:
        print("❌ 依赖检查未通过:\n")
        for err in errors:
            print(err)
            print()
        sys.exit(1)

    # 验证输入文件
    input_path = Path(args.input).resolve()
    if not input_path.is_file():
        print(f"❌ 视频文件不存在: {input_path}")
        sys.exit(1)

    if input_path.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
        print(
            f"⚠️  文件格式 '{input_path.suffix}' 可能不受支持。"
            f"支持的格式: {', '.join(SUPPORTED_VIDEO_EXTENSIONS)}"
        )

    # 解析模型路径
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

    # 如果已经是完整路径
    if Path(model_name).is_file():
        return model_name

    # 尝试在 models/ 目录下查找
    model_path = PROJECT_ROOT / "models" / f"ggml-{model_name}.bin"
    if model_path.is_file():
        return str(model_path)

    print(f"⚠️  模型文件未找到: {model_path}")
    print(f"   将使用默认模型: {WHISPER_MODEL_PATH}")
    return None


if __name__ == "__main__":
    main()
