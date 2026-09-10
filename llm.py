# -*- coding: utf-8 -*-
"""OpenAI 兼容 LLM 客户端（默认 DeepSeek V4 Flash）。"""

from __future__ import annotations

import asyncio
import json
import os
import re

import httpx


def extract_json(text: str) -> dict | None:
    if not text:
        return None
    text = re.sub(r"```(?:json)?|```", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


class LLMClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv("OPENAI_MODEL", "deepseek-ai/DeepSeek-V3.2")
        self.timeout = float(os.getenv("LLM_TIMEOUT", "90"))
        # 部分服务商（如魔搭）对 response_format=json_object 支持不佳甚至会挂起，
        # 默认关闭；需要时设 LLM_JSON_MODE=1。extract_json 已能兜底解析。
        self.use_response_format = os.getenv("LLM_JSON_MODE", "0").strip() == "1"
        # 额外请求参数（JSON）。默认关闭 Qwen 系列思考模式，否则可能超时数十秒。
        # 若某模型不支持，请求 400 时会自动去掉这些参数重试。
        self.extra: dict = {}
        raw_extra = os.getenv("LLM_EXTRA_BODY", '{"enable_thinking": false}').strip()
        if raw_extra:
            try:
                parsed = json.loads(raw_extra)
                if isinstance(parsed, dict):
                    self.extra = parsed
            except json.JSONDecodeError:
                self.extra = {}

    @property
    def ready(self) -> bool:
        return bool(self.api_key)

    async def chat(self, system: str, user: str, json_mode: bool = True) -> str:
        if not self.ready:
            raise RuntimeError("未配置 OPENAI_API_KEY")
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.8,
        }
        if json_mode and self.use_response_format:
            payload["response_format"] = {"type": "json_object"}
        payload.update(self.extra)

        optional = [k for k in ("response_format",) if k in payload]
        optional += [k for k in self.extra if k in payload]

        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with httpx.AsyncClient(
            timeout=self.timeout,
            transport=httpx.AsyncHTTPTransport(local_address="0.0.0.0", retries=2),
        ) as client:
            last: httpx.Response | None = None
            for attempt in range(4):
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code == 429 or resp.status_code >= 500:
                    last = resp
                    await asyncio.sleep(1.5 * (attempt + 1))
                    continue
                if resp.status_code == 400 and optional:
                    payload.pop(optional.pop(0), None)
                    continue
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"] or ""
            if last is not None:
                last.raise_for_status()
            raise RuntimeError("LLM 请求失败")

    async def chat_json(self, system: str, user: str) -> dict:
        last = ""
        for _ in range(2):
            last = await self.chat(system, user, json_mode=True)
            data = extract_json(last)
            if data is not None:
                return data
        raise RuntimeError(f"LLM 返回格式异常：{last[:120]}")
