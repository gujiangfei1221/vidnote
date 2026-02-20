"""
文件夹监听模块
监控指定目录，当有新视频文件下载进来时自动触发处理流程。
"""

import sys
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

sys.path.insert(0, str(Path(__file__).parent.resolve()))

from config import SUPPORTED_VIDEO_EXTENSIONS


class VideoHandler(FileSystemEventHandler):
    """视频文件事件处理器"""

    def __init__(
        self,
        model_path: str | None = None,
        output_dir: str | None = None,
        language: str = "auto",
    ):
        super().__init__()
        self.model_path = model_path
        self.output_dir = output_dir
        self.language = language
        self._processing = set()  # 正在处理的文件集合，防止重复触发

    def on_created(self, event):
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # 检查是否是支持的视频格式
        if file_path.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
            return

        # 防止重复处理
        if str(file_path) in self._processing:
            return

        self._processing.add(str(file_path))

        # 等待文件写入完成（下载中的文件可能还在写入）
        print(f"\n📥 检测到新视频: {file_path.name}")
        print("   等待文件写入完成...")
        self._wait_for_file_complete(file_path)

        try:
            from main import process_video

            process_video(
                video_path=str(file_path),
                model_path=self.model_path,
                output_dir=self.output_dir,
                language=self.language,
            )
        except Exception as e:
            print(f"❌ 处理失败 [{file_path.name}]: {e}")
        finally:
            self._processing.discard(str(file_path))

    @staticmethod
    def _wait_for_file_complete(path: Path, check_interval: float = 2.0, stable_count: int = 3):
        """
        等待文件写入完成。
        通过检查文件大小是否稳定来判断。
        """
        last_size = -1
        stable = 0

        while stable < stable_count:
            time.sleep(check_interval)
            try:
                current_size = path.stat().st_size
                if current_size == last_size:
                    stable += 1
                else:
                    stable = 0
                    last_size = current_size
            except FileNotFoundError:
                return  # 文件被删除


def start_watching(
    watch_dir: str,
    model_path: str | None = None,
    output_dir: str | None = None,
    language: str = "auto",
):
    """
    开始监听指定目录。

    Args:
        watch_dir: 要监听的目录路径
        model_path: Whisper 模型路径
        output_dir: 输出目录
        language: 语言代码
    """
    watch_path = Path(watch_dir).resolve()

    if not watch_path.is_dir():
        print(f"❌ 监听目录不存在: {watch_path}")
        sys.exit(1)

    handler = VideoHandler(
        model_path=model_path,
        output_dir=output_dir,
        language=language,
    )
    observer = Observer()
    observer.schedule(handler, str(watch_path), recursive=False)
    observer.start()

    print(f"\n👀 监听模式已启动")
    print(f"   目录: {watch_path}")
    print(f"   支持格式: {', '.join(SUPPORTED_VIDEO_EXTENSIONS)}")
    print(f"   按 Ctrl+C 停止\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 监听已停止")
        observer.stop()

    observer.join()
