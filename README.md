# Meteora Router V0.1 Step 3

Meteora DLMM 自动化路由 + 风控 bot.

## 安全机制

- **DRY_RUN 默认 ON**:首次部署不会真发交易,只在 logs 显示 "would send"
- **/auto 默认 OFF**:即使 DRY_RUN 关掉,bot 也不会自动开仓,需 `/auto on`
- **首次开仓二次确认**:全自动模式下第一次开仓必须 TG 回复 `/confirm`
- **单笔本金硬上限**:`MAX_POSITION_USD` (默认 $200),代码层面拦截
- **Hard SL**:任一仓位 < -8% 自动平仓 + bot 进入 paused
- **`/pause` `/emergency` 命令**:随时可以一键停 / 一键全平

## 推荐部署流程

1. 上传代码 → Railway 自动 build
2. Variables 加好 6 个 env(参考 `.env.example`)
3. **保持 `DRY_RUN=true`** 第一次部署
4. TG `/scan` 看打分,验证逻辑
5. TG `/auto on` 让 bot 自己跑一段(模拟,不会真花钱)
6. 看 logs:每个"would send tx"都是它本来要做的真实操作
7. 一切正常后 → Railway 改 `DRY_RUN=false` → redeploy → 上实盘

## 命令清单

```
查询:
  /status           整体状态
  /pool [addr]      池子详情 + 打分
  /scan             扫描白名单池打分排序
  /positions        仓位详情
  /pnl              盈亏报表

控制:
  /auto on|off      全自动开关
  /open <addr> <usd>   手动开仓
  /close <pos_pk>      手动关仓
  /pause /resume       暂停/恢复
  /emergency           紧急全平
  /confirm /cancel     确认/取消待执行操作

候选池管理:
  /addpool <addr>      加入候选
  /rmpool <addr>       移除候选
```

## 关键参数(env 可调)

| 参数 | 默认 | 说明 |
|---|---|---|
| `DRY_RUN` | true | 是否模拟模式 |
| `MAX_POSITION_USD` | 200 | 单笔最大投入 |
| `MAX_OPEN_POSITIONS` | 2 | 最多同时持仓 |
| `HARD_SL_PCT` | 8 | Stop loss 触发(%)|
| `EMERGENCY_DUMP_PCT` | 15 | Token 急跌保护(30min) |
| `POOL_COOLDOWN_MINUTES` | 60 | 关仓后冷却期 |

## 候选池 V0.1 白名单

仅以下 token mint 之间的 DLMM 池子会被纳入候选:
- SOL
- USDC
- USDT

bin_step 必须 20-100 bps;TVL ≥ $500k;Volume ≥ $200k;APR ≥ 20%(USDC/USDT 池子 ≥ 5%)。
