"""
文本清洗模块
去除 whisper.cpp 转录输出中的时间戳和冗余信息，并将繁体中文转为简体。
"""

import re

from opencc import OpenCC

# 繁体 → 简体转换器（t2s = Traditional to Simplified）
_t2s = OpenCC("t2s")


def clean_transcript(raw_text: str) -> str:
    """
    清洗转录文本，去除时间戳和冗余信息，并将繁体转为简体。

    Args:
        raw_text: whisper.cpp 输出的原始文本

    Returns:
        清洗后的简体中文纯文本
    """
    if not raw_text:
        return ""

    text = raw_text

    # 去除 SRT 格式时间戳: [00:00.000 --> 00:05.000]
    text = re.sub(r"\[[\d:.]+\s*-->\s*[\d:.]+\]\s*", "", text)

    # 去除 VTT 格式时间戳: 00:00.000 --> 00:05.000
    text = re.sub(r"\d{2}:\d{2}[:.]\d{3}\s*-->\s*\d{2}:\d{2}[:.]\d{3}\s*", "", text)

    # 去除方括号中的时间信息: [00:00:05]
    text = re.sub(r"\[\d{2}:\d{2}:\d{2}\]", "", text)

    # 去除行号（SRT 格式）
    text = re.sub(r"^\d+\s*$", "", text, flags=re.MULTILINE)

    # 去除 whisper.cpp 特有的控制标记
    text = re.sub(r"\[BLANK_AUDIO\]", "", text)
    text = re.sub(r"\[MUSIC\]", "", text)
    text = re.sub(r"\(music\)", "", text, flags=re.IGNORECASE)

    # 去除 ANSI 颜色代码
    text = re.sub(r"\x1b\[[0-9;]*m", "", text)

    # 合并多个空行为一个
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 去除每行首尾空白
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)

    # 合并为连贯段落（将单独的短行合并）
    paragraphs = []
    current = []
    for line in text.splitlines():
        if not line:
            if current:
                paragraphs.append(" ".join(current))
                current = []
        else:
            current.append(line)
    if current:
        paragraphs.append(" ".join(current))

    result = "\n\n".join(paragraphs)

    # 繁体中文 → 简体中文
    result = _t2s.convert(result)

    print(f"🧹 文本清洗完成: {len(raw_text)} → {len(result)} 字符（已转为简体）")

    return result
