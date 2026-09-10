# -*- coding: utf-8 -*-
"""真实 LLM 连通性 + 出题/判定自测（读取 .env）。"""

import asyncio
import time

from dotenv import load_dotenv

load_dotenv()

import prompts
from llm import LLMClient, extract_json


async def main() -> None:
    client = LLMClient()
    print("ready =", client.ready)
    print("base  =", client.base_url)
    print("model =", client.model)
    print("resp_fmt =", client.use_response_format)

    t = time.time()
    data = await client.chat_json(
        prompts.PUZZLE_SYSTEM, prompts.PUZZLE_USER.format(theme="医院")
    )
    print(f"出题耗时 = {time.time()-t:.1f}s")
    print("title   =", data.get("title"))
    print("genre   =", data.get("genre"))
    print("surface =", str(data.get("surface"))[:50])
    print("truth   =", str(data.get("truth"))[:50])
    print("keys    =", data.get("key_points"))
    print("hints   =", data.get("hints"))

    # 判定自测：拿刚出的题问一个关键问题
    judge_sys = (
        prompts.JUDGE_SYSTEM.replace("{surface}", str(data.get("surface")))
        .replace("{truth}", str(data.get("truth")))
        .replace("{key_points}", "、".join(data.get("key_points") or []) or "无")
    )
    t = time.time()
    j = await client.chat_json(judge_sys, "【玩家新提问】这件事发生在医院里吗？")
    print(f"判定耗时 = {time.time()-t:.1f}s")
    print("judgment =", j)
    print("LIVE LLM OK")


if __name__ == "__main__":
    asyncio.run(main())
