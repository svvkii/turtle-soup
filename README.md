---
title: Turtle Soup
emoji: 🥣
colorFrom: yellow
colorTo: orange
sdk: docker
app_port: 7860
pinned: false
---

# 海龟汤 H5 多人房间

在微信群里发一条链接，好友点开就能在同一个房间玩海龟汤：LLM 出题主持，玩家提问「是/否」，还原真相。

- 后端：FastAPI + WebSocket（房间内实时同步）
- 前端：原生 HTML/JS，手机优先，微信内置浏览器直接可用
- **内置经典题库**：7 道经典海龟汤，无主题时优先出题库题（不消耗 LLM、零成本、质量稳定），用完自动转 LLM 现出
- LLM：任意 OpenAI 兼容接口（默认 DeepSeek V4 Flash）
- 状态：内存房间，6 小时无活动自动回收（无需数据库）

## 接入免费 LLM：魔搭 ModelScope（推荐）

魔搭 API-Inference 每天约 **2000 次免费调用**，OpenAI 兼容接口，**零代码切换**：

1. 注册 https://modelscope.cn → 账号中心生成「访问令牌 / SDK Token」（`ms-` 开头）
2. 在目标模型页（DeepSeek / Qwen 系列）确认 API-Inference 的模型 ID，形如 `deepseek-ai/DeepSeek-V4-Flash`
3. `.env` 改三行：
   ```bash
   OPENAI_BASE_URL=https://api-inference.modelscope.cn/v1
   OPENAI_API_KEY=ms-xxxxxxxx
   OPENAI_MODEL=deepseek-ai/DeepSeek-V4-Flash
   ```

额度测算：一局海龟汤 ≈ 出题 1 次（**题库出题 0 次**）+ 每个提问 1 次 + 猜底/提示若干 → 2000 次/天足够一个群玩一整天。配合 HF Spaces 免费托管 = **全程零成本**。

（配额细节以官方文档为准：https://modelscope.cn/docs/model-service/API-Inference/limits）

## 本地运行

```bash
cd turtle_soup_web
python -m venv .venv && .venv\Scripts\activate     # Windows
pip install -r requirements.txt
copy .env.example .env                              # 填入 OPENAI_API_KEY
uvicorn main:app --host 0.0.0.0 --port 7860 --env-file .env
```

浏览器打开 http://localhost:7860 ，创建房间 → 复制链接。

环境变量：

| 变量 | 说明 | 默认 |
|---|---|---|
| `OPENAI_BASE_URL` | OpenAI 兼容接口地址 | `https://api.deepseek.com/v1` |
| `OPENAI_API_KEY` | API Key | 无（必填） |
| `OPENAI_MODEL` | 模型名 | `deepseek-v4.1-flash-expires-on-0910` |
| `PUZZLE_SOURCE` | 出题策略：`bank_first` 题库优先、`bank` 仅题库、`llm` 仅 AI、`random` | `bank_first` |
| `DEFAULT_ROOM` | 默认单房间代码（永久存在，不参与过期清理） | `HALL` |
| `PORT` | 监听端口 | `7860` |

> `deepseek-v4.1-flash-expires-on-0910` 为限时模型，9 月 10 日到期后改环境变量即可换模型。

## 内置题库与自定义

- 题库文件：`puzzles.py`（7 道经典海龟汤，含汤面/汤底/关键要素/3 条提示）
- 无主题开局：优先出题库题；题库轮完自动重置，或转 LLM 现出
- 指定主题（如 `开汤 医院`）：直接走 LLM 生成
- 导入的题目若无预置提示，点「提示」时由 LLM 现场生成（需配置 API Key）

**一键导入在线题库**（已实测 188 道，去重后与本项目 7 道合计 195 道）：

```bash
python import_bank.py                 # 默认抓取 soupai 的 network_soupai.json
python import_bank.py 本地题库.json    # 也可导入本地/自定义 JSON
```

脚本会把结果写入 `puzzles_extra.json`，启动时自动加载。支持 `{puzzle,answer}` / `{surface,truth}` / `{question,answer}` 等字段。

> ⚠️ 默认题库来源 [astrbot_plugin_soupai](https://github.com/KONpiGG/astrbot_plugin_soupai) 为 AGPL-3.0，导入内容仅供个人自用；对外发布请替换为原创或有授权的题目。

**追加自己的题**：在 `puzzles_extra.json` 里按下面格式手动添加即可：

```json
[
  {
    "id": "my-1",
    "title": "标题",
    "genre": "本格",
    "surface": "汤面",
    "truth": "汤底",
    "key_points": ["关键要素"],
    "hints": ["提示1", "提示2", "提示3"]
  }
]
```

## 免费云部署（三选一）

> 👉 **推荐直接看 [DEPLOY.md](DEPLOY.md)（含一键推送脚本 `deploy_hf.ps1`）**

### 方案 A：Hugging Face Spaces（最省事，推荐）

1. 注册 https://huggingface.co ，New Space → SDK 选 **Docker** → 模板 Blank
2. 把本目录文件推到该 Space 仓库（或网页上传）：
   ```bash
   git clone https://huggingface.co/spaces/<你的用户名>/<space名>
   cp -r turtle_soup_web/* <space名>/
   cd <space名> && git add . && git commit -m "init" && git push
   ```
3. Space 页面 → Settings → **Variables and secrets** 添加：
   - `OPENAI_API_KEY`（secret）
   - `OPENAI_BASE_URL`、`OPENAI_MODEL`（variable，按需）
4. 等构建完成，访问 `https://<用户名>-<space名>.hf.space`

> 免费 CPU 实例：空闲 48 小时后休眠，首次访问冷启动约 30~60 秒；重启后房间清空。

### 方案 B：Render（GitHub 一键，免费）

1. 把本目录推到 GitHub 仓库
2. Render → New → **Web Service** → 连接该仓库
   - Root Directory：`turtle_soup_web`（若仓库根就是本目录则留空）
   - Runtime：Python，Plan：**Free**
   - Build：`pip install -r requirements.txt`
   - Start：`uvicorn main:app --host 0.0.0.0 --port $PORT`
3. Environment → 添加 `OPENAI_API_KEY`（以及 `OPENAI_BASE_URL` / `OPENAI_MODEL`）
4. 也可用仓库内 `render.yaml` Blueprint 部署

> 免费档空闲 15 分钟休眠，冷启动约 50 秒；支持 WebSocket。

### 方案 C：ClawCloud Run / Northflank（有免费额度、不休眠）

适合想要 24 小时在线、不冷启动的场景：

1. **ClawCloud Run**（GitHub 注册送每月 $5 额度）：Create App → Docker → 填本仓库 / 构建 `Dockerfile` → 端口 `7860` → 配环境变量
2. **Northflank**（免费套餐）：Create Service → Build from repo（Dockerfile）→ 端口 `7860` → 配环境变量

## 自己的服务器 / 群晖 NAS

```bash
cd turtle_soup_web
copy .env.example .env    # 填 Key
docker compose up -d --build
```

如需域名 + HTTPS，用 Nginx/Caddy 反代到 `7860`；**WebSocket 需要 `Upgrade`/`Connection` 头透传**（Caddy 自动处理，Nginx 需 `proxy_set_header Upgrade $http_upgrade;`）。

## 微信内使用注意

- 页面走 HTTPS 时自动用 `wss://`，微信内置浏览器可直接连
- 分享：点「分享」复制链接，在群里粘贴；或用右上角「···」转发页面
- 未接入公众号 JS-SDK 时，微信可能提示「非官方网页」，不影响使用
- 群里每人点链接进入同一房间即可实时对战

## 玩法

- **默认单房间模式**：所有人打开首页 → 填昵称 → 「进入房间」，全在同一个房间（`HALL`）；把首页链接直接甩群里即可
- 「创建独立房间 / 房间码加入」折叠在首页备用区，多房间功能保留（`DEFAULT_ROOM` 环境变量可改默认房名）
- 房主点「🫕 开一锅」→ 默认从内置题库出题；输入 `开汤 医院` 指定主题则走 AI 现出
- `提问 xxx`：汤主回答 是 / 否 / 无关 / 是也不是
- `猜汤底 xxx`：给出完整推理，返回还原度评分，命中即揭晓
- `提示` / `汤面` / `揭晓` / `结束`

## 接口

| 路径 | 说明 |
|---|---|
| `GET /` | 首页（创建/加入） |
| `GET /r/{code}` | 房间页 |
| `POST /api/rooms` | 创建房间 `{name}` |
| `GET /api/rooms/{code}` | 房间信息 |
| `GET /healthz` | 健康检查（含 LLM 是否配置） |
| `WS /ws/{code}?pid=&name=` | 房间实时通道 |
