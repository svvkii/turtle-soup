# 部署到腾讯云 CloudBase 云托管（国内直连 · 有免费额度）

> 适合：想让微信群里的人**点开即快**、且**不用自己电脑常开**。
> 云托管支持 WebSocket / 自定义端口 / Dockerfile，正是我们需要的。

## 费用（重要）

| 项 | 价格 | 说明 |
|---|---|---|
| CPU | 0.055 元/(核·小时) | |
| 内存 | 0.032 元/(GB·小时) | |
| 出网流量 | 0.8 元/GB | 文字游戏流量极小 |
| 缩容到 0 | **不计费** | 无请求时自动缩到 0 |
| **免费体验版** | **3000 点/月**（约 ¥3 等值） | 每个账号 1 个，需兑换码 |

**结论**：把「运行模式」设为**始终自动扩缩容、最小实例 0**，空闲不花钱；免费额度够一群朋友玩很久（偶尔首次访问有几秒冷启动）。
若想零冷启动（最小实例 1），约 **¥21/月**，免费额度不够，需要个人版（¥19.9/月，40000 点）。

## 一、准备

1. 注册并**实名认证**腾讯云账号：https://cloud.tencent.com
2. 打开云开发控制台：https://tcb.cloud.tencent.com
3. **领取免费体验版兑换码**（购买页有领取入口）→ 创建一个云开发环境（地域建议**上海**）

## 二、部署（Git 部署，最省事）

代码已在你 GitHub：`svvkii/turtle-soup`（含 Dockerfile）

1. 控制台 → 你的环境 → **云托管** → **新建服务**
2. 部署方式选 **Git 部署** → 授权绑定 GitHub → 选择仓库 `svvkii/turtle-soup`、分支 `main`
3. 构建配置：
   - 构建方式：**Dockerfile**（仓库根目录已有，无需改动）
   - **容器端口：`7860`**
4. **环境变量**（服务配置里添加）：

```
OPENAI_BASE_URL = https://api-inference.modelscope.cn/v1
OPENAI_API_KEY  = ms-954340fc-fbba-430c-b51b-7a58e9c1e555
OPENAI_MODEL    = Qwen/Qwen3.8-Flash-Next
LLM_EXTRA_BODY  = {"enable_thinking": false}
DEFAULT_ROOM    = HALL
PUZZLE_SOURCE   = bank_first
```

> ⚠️ `LLM_EXTRA_BODY` 必须加，否则 Qwen 思考模式会导致请求超时。
> 部署时 `python import_bank.py` 会在线拉取题库（构建命令已在 Dockerfile 里？没有的话在云托管「构建命令」加：`pip install -r requirements.txt && python import_bank.py`）。

5. **运行模式**：始终自动扩缩容
   - 最小实例数：`0`（省额度）
   - 最大实例数：`2`
6. 点部署 → 等构建完成 → 得到默认域名：
   `https://<服务名>-<随机>.上海地域.app.tcloudbase.com`

## 三、验证

浏览器打开：
```
https://你的域名/healthz
```
应返回：
```json
{"ok":true,"llm":true,"model":"Qwen/Qwen3.8-Flash-Next","puzzles":195,"default_room":"HALL"}
```

然后打开根域名 → 填昵称 → 进房间 → 开汤。把域名发到微信群即可。

## 四、常见问题

| 问题 | 处理 |
|---|---|
| 构建失败 | 看「云托管 → 服务 → 构建日志」；确认 Dockerfile 在仓库根目录 |
| 部署后 502 / 打不开 | 容器端口必须是 **7860**（和 Dockerfile 的 `EXPOSE 7860` 一致） |
| `/healthz` 显示 `llm:false` | 检查环境变量名拼写（全大写），或 `OPENAI_API_KEY` 没填 |
| 提问很慢/超时 | 确认 `LLM_EXTRA_BODY={"enable_thinking": false}` 已配置 |
| 首访慢几秒 | 最小实例 0 导致冷启动；想消除就设最小实例 1（产生费用） |
| WebSocket 连不上 | 云托管默认支持；确认用 `https://` 域名（前端会自动走 wss） |
| 免费额度用完 | 控制台看「套餐用量」；不够就升级个人版 ¥19.9/月 |

## 备注

- 代码仓库：https://github.com/svvkii/turtle-soup
- 换模型：只改环境变量 `OPENAI_MODEL`（MagicScope 现成模型：`Qwen/Qwen3.5-27B`、`deepseek-ai/DeepSeek-V4-Pro` 等）
- 题库：自带 7 道；构建时自动在线拉取 ~188 道（`import_bank.py`）
