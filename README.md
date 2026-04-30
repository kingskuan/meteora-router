# Meteora Router

Meteora DLMM auto rebalance bot. V0.1 自用版本。

## Stack
- TypeScript + Node 20
- @meteora-ag/dlmm SDK
- Telegraf (TG bot)
- Railway Postgres (state, 同机房 <5ms)
- Railway (deploy)

## Roadmap
- ✅ Step 1: TG bot skeleton + Postgres
- ⬜ Step 2: 完整 schema + 读链上仓位
- ⬜ Step 3: 开仓 / 关仓 + Jupiter swap
- ⬜ Step 4: 巡检 + rebalance + claim
- ⬜ Step 5: 部署 + UptimeRobot

## Deploy on Railway

### 1. 创建项目
- Railway → New Project → Deploy from GitHub Repo → 选你的 repo
- 等 build 跑完 (会失败,因为还没 DB)

### 2. 加 Postgres
- 同一个 Project → New → Database → **Add PostgreSQL**
- 等 30 秒,Postgres 起来

### 3. 注入 DATABASE_URL
- 点 bot 服务 → Variables
- 点 **+ New Variable** → 选 **Add Reference** → Postgres → `DATABASE_URL`
- 这样会自动注入,内网连接,延迟 <5ms

### 4. 加其他环境变量
参考 `.env.example`:
- `HELIUS_RPC_URL`
- `WALLET_PRIVATE_KEY`
- `TG_BOT_TOKEN`
- `TG_OWNER_ID`

### 5. Redeploy
- 加完 env 后 Railway 自动重启
- 看 Logs:应该看到 `🗄️ DB schema ready`、`🤖 TG bot launched`
- TG 收到 "🚀 Meteora Router 上线"

## TG Commands
- `/ping` - 测试连接
- `/status` - 钱包 + DB 状态
- `/help` - 帮助
