"""
AI 总结模块
调用硅基流动 API 进行知识萃取和文本总结。
"""

import json
import requests

from config import (
    SILICONFLOW_API_KEY,
    SILICONFLOW_API_URL,
    SILICONFLOW_MODEL,
    SUMMARY_SYSTEM_PROMPT,
)


def summarize(transcript: str) -> str:
    """
    调用硅基流动 DeepSeek-V3.2 模型对转录文本进行知识萃取。

    Args:
        transcript: 清洗后的转录文本

    Returns:
        AI 生成的 Markdown 格式总结

    Raises:
        ValueError: API Key 未配置
        RuntimeError: API 调用失败
    """
    if not SILICONFLOW_API_KEY or SILICONFLOW_API_KEY == "your_api_key_here":
        raise ValueError(
            "❌ 未配置硅基流动 API Key\n"
            "请在 .env 文件中设置 SILICONFLOW_API_KEY"
        )

    if not transcript.strip():
        return "⚠️ 转录文本为空，无法生成总结。"

    print(f"🤖 正在调用 AI 总结...")
    print(f"   模型: {SILICONFLOW_MODEL}")
    print(f"   文本长度: {len(transcript)} 字符")

    headers = {
        "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": SILICONFLOW_MODEL,
        "messages": [
            {
                "role": "system",
                "content": SUMMARY_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": f"以下是短视频的转录文本，请进行知识萃取：\n\n{transcript}",
            },
        ],
        "temperature": 0.3,  # 低温度保证确定性输出
        "max_tokens": 2048,
        "stream": False,
    }

    try:
        response = requests.post(
            SILICONFLOW_API_URL,
            headers=headers,
            json=payload,
            timeout=60,  # 60秒超时
        )

        if response.status_code != 200:
            error_detail = ""
            try:
                error_json = response.json()
                error_detail = json.dumps(error_json, ensure_ascii=False, indent=2)
            except Exception:
                error_detail = response.text[:500]

            raise RuntimeError(
                f"API 请求失败 (HTTP {response.status_code})\n"
                f"详情: {error_detail}"
            )

        result = response.json()
        summary = result["choices"][0]["message"]["content"]

        # 统计 token 使用量
        usage = result.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", "N/A")
        completion_tokens = usage.get("completion_tokens", "N/A")
        print(f"✅ AI 总结完成 (输入: {prompt_tokens} tokens, 输出: {completion_tokens} tokens)")

        return summary

    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            "❌ 无法连接到硅基流动 API\n"
            "请检查网络连接"
        )
    except requests.exceptions.Timeout:
        raise RuntimeError(
            "❌ API 请求超时（超过60秒）\n"
            "请稍后重试"
        )
    except KeyError as e:
        raise RuntimeError(
            f"❌ API 响应格式异常，缺少字段: {e}\n"
            f"原始响应: {response.text[:500]}"
        )
