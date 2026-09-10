# -*- coding: utf-8 -*-
"""导入第三方海龟汤题库，转换为本项目的 puzzles_extra.json。

用法：
    python import_bank.py                    # 用默认在线题库（soupai network_soupai.json）
    python import_bank.py 本地文件.json       # 用本地 JSON
    python import_bank.py https://xxx.json   # 用自定义在线 JSON

支持输入格式（自动识别字段）：
    {"puzzle": "...", "answer": "..."}   或
    {"surface": "...", "truth": "..."}   或
    {"question": "...", "answer": "..."}

注意：默认题库来源仓库为 AGPL-3.0，生成的文件仅供个人自用；
对外发布请替换为原创或有授权的题目。
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

DEFAULT_URL = (
    "https://raw.githubusercontent.com/KONpiGG/"
    "astrbot_plugin_soupai/master/network_soupai.json"
)
OUT_PATH = Path(__file__).parent / "puzzles_extra.json"

SURFACE_KEYS = ("puzzle", "surface", "question", "汤面", "题面")
TRUTH_KEYS = ("answer", "truth", "汤底", "答案", "真相")


def load_source(src: str) -> list:
    if src.startswith(("http://", "https://")):
        req = urllib.request.Request(src, headers={"User-Agent": "turtle-soup-import/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
    else:
        raw = Path(src).read_text(encoding="utf-8", errors="ignore")
    data = json.loads(raw)
    if isinstance(data, dict):
        data = data.get("puzzles") or data.get("data") or data.get("list") or []
    return data if isinstance(data, list) else []


def normalize(item: dict, idx: int) -> dict | None:
    if not isinstance(item, dict):
        return None
    surface = next((str(item[k]).strip() for k in SURFACE_KEYS if item.get(k)), "")
    truth = next((str(item[k]).strip() for k in TRUTH_KEYS if item.get(k)), "")
    if len(surface) < 8 or len(truth) < 8:
        return None
    return {
        "id": f"bank-{idx}",
        "title": surface[:12],
        "genre": str(item.get("genre") or "本格"),
        "surface": surface,
        "truth": truth,
        "key_points": item.get("key_points") or [],
        "hints": item.get("hints") or [],
    }


def main() -> None:
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    print(f"source: {src}")
    try:
        raw_items = load_source(src)
    except Exception as e:
        print(f"加载失败：{e}")
        sys.exit(1)

    seen: set[str] = set()
    out: list[dict] = []
    for i, item in enumerate(raw_items):
        puzzle = normalize(item, i)
        if puzzle is None:
            continue
        if puzzle["surface"] in seen:
            continue
        seen.add(puzzle["surface"])
        out.append(puzzle)

    OUT_PATH.write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"导入 {len(out)} 道题 -> {OUT_PATH.name}（已去重）")


if __name__ == "__main__":
    main()
