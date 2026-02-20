"""
AI 总结模块
调用硅基流动 API 进行知识萃取和文本总结。
"""

import json
import re
import requests

from config import (
    SILICONFLOW_API_KEY,
    SILICONFLOW_API_URL,
    SILICONFLOW_MODEL,
    SUMMARY_SYSTEM_PROMPT,
    KEYFRAME_SYSTEM_PROMPT,
)


def _call_api(system_prompt: str, user_content: str, max_tokens: int = 2048) -> str:
    """
    调用硅基流动 API 的通用方法。

    Args:
        system_prompt: 系统提示词
        user_content: 用户输入内容
        max_tokens: 最大输出 token 数

    Returns:
        AI 生成的文本
    """
    if not SILICONFLOW_API_KEY or SILICONFLOW_API_KEY == "your_api_key_here":
        raise ValueError(
            "❌ 未配置硅基流动 API Key\n"
            "请在 .env 文件中设置 SILICONFLOW_API_KEY"
        )

    headers = {
        "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": SILICONFLOW_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.3,
        "max_tokens": max_tokens,
        "stream": False,
    }

    try:
        response = requests.post(
            SILICONFLOW_API_URL,
            headers=headers,
            json=payload,
            timeout=60,
        )

        if response.status_code != 200:
            error_detail = ""
            try:
                error_detail = json.dumps(response.json(), ensure_ascii=False, indent=2)
            except Exception:
                error_detail = response.text[:500]
            raise RuntimeError(
                f"API 请求失败 (HTTP {response.status_code})\n详情: {error_detail}"
            )

        result = response.json()
        content = result["choices"][0]["message"]["content"]

        usage = result.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", "N/A")
        completion_tokens = usage.get("completion_tokens", "N/A")
        print(f"   tokens: 输入 {prompt_tokens}, 输出 {completion_tokens}")

        return content

    except requests.exceptions.ConnectionError:
        raise RuntimeError("❌ 无法连接到硅基流动 API\n请检查网络连接")
    except requests.exceptions.Timeout:
        raise RuntimeError("❌ API 请求超时（超过60秒）\n请稍后重试")
    except KeyError as e:
        raise RuntimeError(
            f"❌ API 响应格式异常，缺少字段: {e}\n"
            f"原始响应: {response.text[:500]}"
        )


def summarize(transcript: str) -> str:
    """
    调用 AI 对转录文本进行知识萃取。

    Args:
        transcript: 清洗后的转录文本

    Returns:
        AI 生成的 Markdown 格式总结
    """
    if not transcript.strip():
        return "⚠️ 转录文本为空，无法生成总结。"

    print(f"🤖 正在调用 AI 总结...")
    print(f"   模型: {SILICONFLOW_MODEL}")
    print(f"   文本长度: {len(transcript)} 字符")

    content = _call_api(
        system_prompt=SUMMARY_SYSTEM_PROMPT,
        user_content=f"以下是短视频的转录文本，请进行知识萃取：\n\n{transcript}",
    )

    print(f"✅ AI 总结完成")
    return content


def extract_keyframes(timestamped_text: str) -> list[dict]:
    """
    调用 AI 从带时间戳的转录文本中提取关键时间点。

    Args:
        timestamped_text: 带时间戳的转录文本（如 "[00:01:25] 这里讲到了..."）

    Returns:
        关键帧列表: [{"time": "00:01:25", "title": "...", "summary": "..."}, ...]
    """
    if not timestamped_text.strip():
        return []

    print(f"🎯 正在提取关键时间点...")
    print(f"   模型: {SILICONFLOW_MODEL}")

    content = _call_api(
        system_prompt=KEYFRAME_SYSTEM_PROMPT,
        user_content=f"以下是带时间戳的视频转录文本：\n\n{timestamped_text}",
        max_tokens=1024,
    )

    # 从 AI 返回中解析 JSON
    # AI 可能返回 ```json ... ``` 包裹的内容，需要提取
    json_match = re.search(r"\[.*\]", content, re.DOTALL)
    if not json_match:
        print(f"⚠️  AI 未返回有效的 JSON 格式，原始输出:\n{content[:500]}")
        return []

    try:
        keyframes = json.loads(json_match.group())
        print(f"✅ 提取到 {len(keyframes)} 个关键时间点")
        return keyframes
    except json.JSONDecodeError as e:
        print(f"⚠️  JSON 解析失败: {e}\n原始输出:\n{content[:500]}")
        return []
