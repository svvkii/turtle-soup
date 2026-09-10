# 部署清单

> ⚠️ **2026-09 实测：Hugging Face 免费层已不支持 Docker Space**（返回 402：
> *hosting Gradio and Docker Spaces on free cpu-basic requires a PRO subscription*）。
> 免费路线改用下面的「方案 0（本机+隧道）」或「方案 B（Render/ClawCloud，需 GitHub）」。

---

## 方案 0：本机运行 + Cloudflare 隧道（零账号、免费，电脑需开着）✅ 已跑通

```powershell
# 1) 启动服务（本机 7860）
cd turtle_soup_web
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 7860

# 2) 另开一个窗口，开公网隧道（首次用 cloudflared，见下）
cloudflared tunnel --url http://127.0.0.1:7860
# 输出里 https://xxxx.trycloudflare.com 就是可发微信群的地址
```

说明：地址是临时的，每次重启会变；电脑关机/休眠即失效。适合内部朋友圈快速开玩。

---

## 原 Hugging Face 方案（现需 PRO，付费）

> 免费 CPU 不再支持 Docker/Gradio Space。若你愿意开 HF PRO，下列步骤仍适用。

## 0) 准备（约 5 分钟）

- [ ] 注册 https://huggingface.co
- [ ] 注册 https://modelscope.cn → 账号中心 → 生成「访问令牌」(`ms-` 开头)
- [ ] 本机装有 git（`git --version` 能跑通；没配过身份先执行：
      `git config --global user.name "xx"` / `git config --global user.email "xx@xx.com"`）

## 1) 创建 Space（1 分钟）

1. HF 首页 → **New Space**
2. 名称：`turtle-soup`，SDK 选 **Docker**，模板选 **Blank**
3. 可见性建议 **Public**（微信群好友打开链接即玩，无需注册 HF）
   > ⚠️ Public 会公开 `puzzles_extra.json`（来源 AGPL 题库）。介意就删掉该文件再推送，
   > 或改 Private（但好友需注册 HF 并被授权）。

## 2) 推送代码（一条命令）

```powershell
cd turtle_soup_web
.\deploy_hf.ps1 -Space 你的用户名/turtle-soup
```

脚本会自动：clone Space 仓库 → 复制项目文件（排除 .venv/.env/测试）→ commit → push。
之后每次更新代码，重跑同一条命令即可。

## 3) 配置环境变量（Space 页面 → Settings → Variables and secrets）

| 名称 | 类型 | 值 |
|---|---|---|
| `OPENAI_API_KEY` | **Secret** | `ms-xxxxxxxx`（魔搭令牌） |
| `OPENAI_BASE_URL` | Variable | `https://api-inference.modelscope.cn/v1` |
| `OPENAI_MODEL` | Variable | `Qwen/Qwen3.8-Flash-Next`（实测可用；也可 `Qwen/Qwen3.5-27B` / `deepseek-ai/DeepSeek-V4-Pro`） |
| `LLM_EXTRA_BODY` | Variable | `{"enable_thinking": false}` |
| `DEFAULT_ROOM` | Variable | `HALL` |
| `PUZZLE_SOURCE` | Variable | `bank_first` |

保存后 Space 自动重建（约 2~3 分钟）。

## 4) 验证

1. 打开 `https://<用户名>-<space名>.hf.space/healthz`
   → 应返回 `{"ok":true,"llm":true,"puzzles":195,"default_room":"HALL",...}`
2. 打开首页 → 填昵称 → 进入房间 → 「🫕 开一锅」
3. 把 `https://<用户名>-<space名>.hf.space` 发到微信群，好友点开即玩

## 注意事项

- **休眠**：免费 CPU 实例空闲 48h 后休眠，首次访问冷启动 30~60s；重启后房间清空（题库仍在）
- **常驻不休眠**：改用 ClawCloud Run（GitHub 登录送每月 $5 额度）或 Northflank 部署同一 Dockerfile
- **换模型**：到期/欠费只需在 Space Variables 里改 `OPENAI_MODEL`
- **Render 部署**：推 GitHub → New Web Service → Runtime Python →
  Build `pip install -r requirements.txt`，Start `uvicorn main:app --host 0.0.0.0 --port $PORT`，
  环境变量同上（空闲 15 分钟休眠）

## 更新题库

```powershell
python import_bank.py        # 重新抓取在线题库 / 或编辑 puzzles_extra.json
.\deploy_hf.ps1 -Space 你的用户名/turtle-soup
```
