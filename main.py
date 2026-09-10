# -*- coding: utf-8 -*-
"""海龟汤 H5 多人房间服务（FastAPI + WebSocket）。"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

logger = logging.getLogger("uvicorn.error")

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent / ".env")
except Exception:
    pass

import prompts
import puzzles
from llm import LLMClient

BASE_DIR = Path(__file__).parent
STATIC_DIR = BASE_DIR / "static"

ROOM_TTL = 6 * 3600
MAX_ROOMS = 500
MAX_PLAYERS = 30
MAX_HISTORY = 300
MAX_LLM_PER_MIN = 25
CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
DEFAULT_ROOM_CODE = os.getenv("DEFAULT_ROOM", "HALL").upper()

app = FastAPI(title="海龟汤 H5")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
llm = LLMClient()
PUZZLE_SOURCE = os.getenv("PUZZLE_SOURCE", "bank_first").lower()
_used_puzzle_ids: set[str] = set()

JUDGMENT_CN = {"yes": "✅ 是", "no": "❌ 否", "irrelevant": "🤷 无关", "both": "🤔 是也不是"}


def now() -> float:
    return time.time()


def gen_code() -> str:
    for _ in range(200):
        code = "".join(random.choice(CODE_CHARS) for _ in range(4))
        if code not in rooms:
            return code
    raise RuntimeError("房间已满")


@dataclass
class Player:
    pid: str
    name: str
    ws: WebSocket | None = None
    is_host: bool = False
    last_seen: float = field(default_factory=now)

    def public(self) -> dict:
        return {"pid": self.pid, "name": self.name, "is_host": self.is_host, "online": self.ws is not None}


@dataclass
class Game:
    title: str = ""
    genre: str = "本格"
    surface: str = ""
    truth: str = ""
    key_points: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    hint_used: int = 0
    qa: list[dict] = field(default_factory=list)
    guesses: list[dict] = field(default_factory=list)
    solved: bool = False
    starter: str = ""

    def public(self) -> dict:
        return {
            "active": bool(self.surface) and not self.solved,
            "title": self.title,
            "genre": self.genre,
            "surface": self.surface,
            "hint_used": self.hint_used,
            "hint_total": len(self.hints),
            "question_count": len(self.qa),
            "guess_count": len(self.guesses),
            "starter": self.starter,
        }

    def qa_digest(self, limit: int = 20) -> str:
        if not self.qa:
            return "（暂无提问）"
        return "\n".join(f"{q['name']}：{q['q']} → {q['a']}" for q in self.qa[-limit:])


class Room:
    def __init__(self, code: str) -> None:
        self.code = code
        self.players: dict[str, Player] = {}
        self.history: list[dict] = []
        self.game: Game | None = None
        self.created = now()
        self.last_active = now()
        self.llm_stamps: list[float] = []
        self.lock = asyncio.Lock()

    def online_players(self) -> list[Player]:
        return [p for p in self.players.values() if p.ws is not None]

    def public_players(self) -> list[dict]:
        return [p.public() for p in self.players.values()]

    def add_history(self, item: dict) -> None:
        self.history.append(item)
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]

    async def broadcast(self, payload: dict, remember: bool = False) -> None:
        if remember:
            self.add_history(payload)
        dead: list[str] = []
        for pid, player in self.players.items():
            if player.ws is None:
                continue
            try:
                await player.ws.send_json(payload)
            except Exception:
                dead.append(pid)
        for pid in dead:
            self.players[pid].ws = None

    async def send(self, player: Player, payload: dict) -> None:
        if player.ws is not None:
            try:
                await player.ws.send_json(payload)
            except Exception:
                player.ws = None

    async def broadcast_players(self) -> None:
        await self.broadcast({"type": "players", "players": self.public_players()})

    async def broadcast_game(self) -> None:
        await self.broadcast({"type": "game", "game": self.game.public() if self.game else None})

    async def system(self, text: str) -> None:
        await self.broadcast({"type": "msg", "role": "system", "name": "系统", "text": text, "ts": now()}, remember=True)

    async def bot(self, text: str) -> None:
        await self.broadcast({"type": "msg", "role": "bot", "name": "汤主", "text": text, "ts": now()}, remember=True)

    async def chat(self, player: Player, text: str) -> None:
        await self.broadcast(
            {"type": "msg", "role": "player", "name": player.name, "text": text, "ts": now()},
            remember=True,
        )

    def check_llm_rate(self) -> bool:
        cutoff = now() - 60
        self.llm_stamps = [t for t in self.llm_stamps if t > cutoff]
        if len(self.llm_stamps) >= MAX_LLM_PER_MIN:
            return False
        self.llm_stamps.append(now())
        return True


rooms: dict[str, Room] = {}


def cleanup_rooms() -> None:
    expired = [
        code
        for code, room in rooms.items()
        if code != DEFAULT_ROOM_CODE and now() - room.last_active > ROOM_TTL
    ]
    for code in expired:
        rooms.pop(code, None)
    stale_cutoff = now() - 6 * 3600
    for room in rooms.values():
        stale = [
            pid
            for pid, p in room.players.items()
            if p.ws is None and p.last_seen < stale_cutoff
        ]
        for pid in stale:
            room.players.pop(pid, None)


def ensure_default_room() -> Room:
    room = rooms.get(DEFAULT_ROOM_CODE)
    if room is None:
        room = Room(DEFAULT_ROOM_CODE)
        rooms[DEFAULT_ROOM_CODE] = room
    return room


async def cleanup_loop() -> None:
    while True:
        await asyncio.sleep(600)
        cleanup_rooms()


@app.on_event("startup")
async def _startup() -> None:
    ensure_default_room()
    asyncio.create_task(cleanup_loop())


class CreateRoom(BaseModel):
    name: str = ""


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/r/{code}")
async def room_page(code: str) -> FileResponse:
    return FileResponse(STATIC_DIR / "room.html")


@app.get("/healthz")
async def healthz() -> JSONResponse:
    return JSONResponse(
        {
            "ok": True,
            "rooms": len(rooms),
            "llm": llm.ready,
            "model": llm.model,
            "puzzles": len(puzzles.all_puzzles()),
            "default_room": DEFAULT_ROOM_CODE,
        }
    )


@app.get("/api/rooms/{code}")
async def room_info(code: str) -> JSONResponse:
    code = code.upper()
    if code == DEFAULT_ROOM_CODE:
        ensure_default_room()
    room = rooms.get(code)
    if not room:
        return JSONResponse({"exists": False}, status_code=404)
    return JSONResponse(
        {
            "exists": True,
            "code": room.code,
            "players": room.public_players(),
            "has_game": bool(room.game and room.game.surface and not room.game.solved),
        }
    )


@app.post("/api/rooms")
async def create_room(body: CreateRoom) -> JSONResponse:
    cleanup_rooms()
    if len(rooms) >= MAX_ROOMS:
        return JSONResponse({"error": "房间数量已达上限，请稍后再试"}, status_code=503)
    name = (body.name or "").strip()[:12] or "汤友"
    code = gen_code()
    room = Room(code)
    rooms[code] = room
    return JSONResponse({"code": code, "name": name})


def game_from_dict(data: dict, starter: str) -> Game | None:
    surface = str(data.get("surface", "")).strip()
    truth = str(data.get("truth", "")).strip()
    if not surface or not truth:
        return None
    return Game(
        title=str(data.get("title", "无名之汤"))[:20],
        genre=str(data.get("genre", "本格")),
        surface=surface,
        truth=truth,
        key_points=[str(k) for k in data.get("key_points", [])][:10],
        hints=[str(h) for h in data.get("hints", [])][:3],
        starter=starter,
    )


def announce_text(game: Game, source: str, theme: str) -> str:
    return (
        f"━━━ 🥣 海龟汤 ·《{game.title}》 ━━━\n"
        f"[{game.genre}] {source} · 主题：{theme or '随机'}\n\n"
        f"【汤面】\n{game.surface}\n\n"
        "发送「提问 xxx」开始推理，「猜汤底 xxx」还原真相，「提示」可求助。"
    )


async def start_round(room: Room, theme: str, starter: str) -> None:
    use_bank = not theme and PUZZLE_SOURCE in ("bank_first", "bank", "random")
    if use_bank:
        data = puzzles.pick_unused(_used_puzzle_ids)
        game = game_from_dict(data, starter) if data else None
        if game is not None and data is not None:
            _used_puzzle_ids.add(str(data.get("id", "")))
            room.game = game
            await room.system(f"{starter} 从题库里端出了一碗汤 📚")
            await room.bot(announce_text(game, "📚 题库", theme))
            await room.broadcast_game()
            return
        if PUZZLE_SOURCE == "bank":
            await room.system("题库已用完，且 PUZZLE_SOURCE=bank 未启用 AI 出题")
            return

    if not llm.ready:
        await room.system("题库已用完且服务器未配置 LLM（OPENAI_API_KEY）")
        return
    if not room.check_llm_rate():
        await room.system("本房间请求太频繁，请稍后再试")
        return
    await room.system(f"{starter} 架起了汤锅，正在熬汤…🔑")
    try:
        data = await llm.chat_json(
            prompts.PUZZLE_SYSTEM,
            prompts.PUZZLE_USER.format(theme=theme or "随机"),
        )
    except Exception as e:
        await room.system(f"出题失败：{e}")
        return
    game = game_from_dict(data, starter)
    if game is None:
        await room.system("生成的谜题不完整，请重新开局")
        return
    room.game = game
    await room.bot(announce_text(game, "🤖 AI 现出", theme))
    await room.broadcast_game()


async def run_judge(room: Room, player: Player, question: str) -> None:
    game = room.game
    assert game is not None
    if any(q["q"] == question for q in game.qa):
        prev = next(q for q in game.qa if q["q"] == question)
        await room.system(f"（{player.name} 的问题之前问过啦）{JUDGMENT_CN.get(prev['a'], prev['a'])}")
        return
    await room.chat(player, f"提问：{question}")
    await room.broadcast({"type": "typing", "on": True})
    system = (
        prompts.JUDGE_SYSTEM.replace("{surface}", game.surface)
        .replace("{truth}", game.truth)
        .replace("{key_points}", "、".join(game.key_points) or "无")
    )
    try:
        data = await llm.chat_json(system, f"【已有问答】\n{game.qa_digest()}\n\n【玩家新提问】{question}")
    except Exception as e:
        await room.system(f"判定失败：{e}")
        await room.broadcast({"type": "typing", "on": False})
        return
    finally:
        await room.broadcast({"type": "typing", "on": False})

    judgment = str(data.get("judgment", "irrelevant")).lower()
    reply = str(data.get("reply", "")).strip()
    label = JUDGMENT_CN.get(judgment, "🤷 无关")
    game.qa.append({"name": player.name, "q": question, "a": judgment})
    text = f"{label}"
    if reply:
        text += f"｜{reply}"
    await room.bot(text)
    if data.get("solved"):
        await reveal(room, solved_by=player.name)


async def run_guess(room: Room, player: Player, guess: str) -> None:
    game = room.game
    assert game is not None
    await room.chat(player, f"猜汤底：{guess}")
    await room.broadcast({"type": "typing", "on": True})
    system = (
        prompts.GUESS_SYSTEM.replace("{surface}", game.surface)
        .replace("{truth}", game.truth)
        .replace("{key_points}", "、".join(game.key_points) or "无")
    )
    try:
        data = await llm.chat_json(system, f"【已有问答】\n{game.qa_digest(10)}\n\n【玩家的汤底猜测】{guess}")
    except Exception as e:
        await room.system(f"判定失败：{e}")
        return
    finally:
        await room.broadcast({"type": "typing", "on": False})

    score = max(0, min(100, int(data.get("score", 0) or 0)))
    reply = str(data.get("reply", "")).strip()
    game.guesses.append({"name": player.name, "text": guess, "score": score})
    bar = "█" * (score // 10) + "░" * (10 - score // 10)
    text = f"🎯 {player.name} 的还原度：{score}/100 [{bar}]"
    if reply:
        text += f"\n{reply}"
    if data.get("solved"):
        await room.bot(text)
        await reveal(room, solved_by=player.name)
        return
    if score >= 80:
        text += "\n非常接近了！补齐关键细节！"
    await room.bot(text)


async def reveal(room: Room, solved_by: str = "") -> None:
    game = room.game
    if game is None:
        return
    text = prompts.REVEAL.format(title=game.title, surface=game.surface, truth=game.truth)
    if solved_by:
        text += f"\n\n🎉 {solved_by} 还原了真相！"
    text += f"\n本局共提问 {len(game.qa)} 次，尝试猜底 {len(game.guesses)} 次。"
    game.solved = True
    await room.bot(text)
    await room.broadcast_game()


async def handle_say(room: Room, player: Player, raw: str) -> None:
    text = raw.strip()[:500]
    if not text:
        return
    room.last_active = now()
    game = room.game
    active = bool(game and game.surface and not game.solved)

    starts = {
        "start": ("开汤", "海龟汤", "开局", "开一局"),
        "ask": ("提问", "问：", "问 "),
        "guess": ("猜汤底", "猜底", "猜：", "猜 "),
        "hint": ("提示", "汤提示"),
        "reveal": ("揭晓", "揭晓汤底"),
        "surface": ("汤面", "看汤面"),
        "end": ("结束", "结束游戏", "掀桌"),
    }

    def match(key: str) -> str | None:
        for prefix in starts[key]:
            if text == prefix:
                return ""
            if text.startswith(prefix):
                return text[len(prefix):].strip(" ：:")
        return None

    if not active:
        theme = match("start")
        if theme is not None:
            async with room.lock:
                if room.game and room.game.surface and not room.game.solved:
                    await room.system("本房间已有一局进行中")
                    return
                await start_round(room, theme, player.name)
            return
        await room.chat(player, text)
        return

    for key, handler in (
        ("surface", None),
        ("hint", None),
        ("reveal", None),
        ("end", None),
        ("ask", "ask"),
        ("guess", "guess"),
    ):
        arg = match(key)
        if arg is None:
            continue
        if key == "surface":
            await room.bot(f"🥣《{game.title}》汤面：\n{game.surface}")
            return
        if key == "hint":
            total = len(game.hints) or 3
            if game.hint_used >= total:
                await room.system("提示已经用完啦（每局最多 3 条）")
                return
            if game.hints:
                hint = game.hints[game.hint_used]
            else:
                if not llm.ready:
                    await room.system("该题暂无预置提示，且服务器未配置 LLM")
                    return
                if not room.check_llm_rate():
                    await room.system("本房间请求太频繁，请稍后再试")
                    return
                system = (
                    prompts.HINT_SYSTEM.replace("{surface}", game.surface)
                    .replace("{truth}", game.truth)
                    .replace("{hint_index}", str(game.hint_used + 1))
                )
                try:
                    async with room.lock:
                        hint = (
                            await llm.chat(system, "请给出一条提示", json_mode=False)
                        ).strip()[:120]
                except Exception as e:
                    await room.system(f"提示生成失败：{e}")
                    return
            game.hint_used += 1
            await room.bot(f"💡 提示 {game.hint_used}/{total}：{hint}")
            return
        if key == "reveal":
            await reveal(room)
            return
        if key == "end":
            game.solved = True
            await room.system(f"🧹 {player.name} 掀桌了本局")
            await room.broadcast_game()
            return
        if not arg:
            await room.system("格式：提问 xxx / 猜汤底 xxx")
            return
        if not llm.ready:
            await room.system("服务器未配置 LLM，请联系管理员")
            return
        if not room.check_llm_rate():
            await room.system("本房间请求太频繁，请稍后再试")
            return
        async with room.lock:
            if handler == "ask":
                await run_judge(room, player, arg)
            else:
                await run_guess(room, player, arg)
        return

    await room.chat(player, text)


@app.websocket("/ws/{code}")
async def ws_endpoint(ws: WebSocket, code: str) -> None:
    code = code.upper()
    room = rooms.get(code)
    if room is None and code == DEFAULT_ROOM_CODE:
        room = ensure_default_room()
    await ws.accept()
    if room is None:
        await ws.send_json({"type": "fatal", "text": "房间不存在或已过期"})
        await ws.close()
        return

    pid = (ws.query_params.get("pid") or "").strip()
    name = (ws.query_params.get("name") or "").strip()[:12] or "汤友"

    player = room.players.get(pid) if pid else None
    if player is None:
        pid = pid or f"p{int(now()*1000)%10**9}{random.randint(100,999)}"
        player = Player(pid=pid, name=name, is_host=not room.players)
        room.players[pid] = player
    player.ws = ws
    player.last_seen = now()
    if not any(p.is_host for p in room.players.values()):
        player.is_host = True
    room.last_active = now()

    await ws.send_json(
        {
            "type": "init",
            "you": {"pid": player.pid, "name": player.name, "is_host": player.is_host},
            "room": code,
            "players": room.public_players(),
            "history": room.history,
            "game": room.game.public() if room.game else None,
            "llm": llm.ready,
        }
    )
    await room.broadcast_players()
    await room.system(f"👋 {player.name} 加入了房间")

    try:
        while True:
            data: dict[str, Any] = await ws.receive_json()
            player.last_seen = now()
            if data.get("type") == "say":
                await handle_say(room, player, str(data.get("text", "")))
            elif data.get("type") == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("ws loop error")
    finally:
        if player.ws is ws:
            player.ws = None
            player.last_seen = now()
        await room.broadcast_players()
        await room.system(f"👋 {player.name} 离开了房间")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "7860")))
