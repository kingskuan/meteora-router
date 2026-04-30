# Meteora Router

Meteora DLMM auto rebalance bot. V0.1 自用版本。

## Stack
- TypeScript + Node 20
- @meteora-ag/dlmm SDK
- Telegraf (TG bot)
- Supabase (state)
- Railway (deploy)

## Roadmap
- ✅ Step 1: TG bot skeleton
- ⬜ Step 2: Supabase schema + 读链上仓位
- ⬜ Step 3: 开仓 / 关仓 + Jupiter swap
- ⬜ Step 4: 巡检 + rebalance + claim
- ⬜ Step 5: 部署 + UptimeRobot

## Deploy

1. Fork 这个 repo (private)
2. Railway → New Project → Deploy from GitHub Repo
3. 在 Variables 里参考 `.env.example` 配置环境变量
4. Railway 自动 build + start
5. TG 给你的 bot 发 `/ping` 测试

## TG Commands

- `/ping` - 测试连接
- `/status` - 钱包状态
- `/help` - 帮助

更多命令在后续 step 加入。
