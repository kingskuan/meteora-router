"""
Bounty Monitor v30.14.34
v30.14.34 (2026-05-27 升级 /analyze system prompt):
  • 🎯 Kings 实测发现 Sonnet 2 个误读:
    1. "funding 0.02-0.04% 反转 55%" - 错! LONG 一直 55%
    2. "OI 0-10 优势 44% 新发现" - 错! 历史已知反向规律
  • 🛠️ 升级 system prompt:
    - 加 LONG/SHORT 视角完整历史数据表 (15+ 维度)
    - 明确标 LONG vs SHORT funding 完全不同
    - 加 "LONG/SHORT 视角混淆陷阱" 提醒
    - 加 "已知币种" ($PLAY/$FHE/$GMT/$ALT)
    - 加 "绝对禁止的话" (反转/新发现/blacklist/立即停止)
    - 加 "样本 ≥30 + 跨 2 周一致" 才算真新发现
  • 影响: /analyze 不再生成"假反转"和"假新发现"

Bounty Monitor v30.14.33 (hotfix 2)
v30.14.33 hotfix 2 (2026-05-27 修 capture admin 检查 bug):
  • 🚨 实证 bug: _capture_cmd_output 用 chat_id=0 调用 cmd_diagnose
    - cmd_diagnose 内 admin 检查: str(0) != str(TG_ADMIN_CHAT_ID) → 立即 return "🔒 仅 admin 可用"
    - capture 只拿到 32 字符权限拒绝消息
    - Sonnet 收到空数据, 给"等待有效数据"输出
  • 🛠️ 修复: 用 TG_ADMIN_CHAT_ID 调用 cmd, 绕过权限检查
  • 部署铁律遗漏: 没真模拟 _capture_cmd_output 完整流程
  • ⚠️ 潜在新风险 (未修): 3 个诊断累计 60-180 秒
    - Sonnet timeout 60s 后才调用, 总时长 90-240s
    - 如果太慢可能 TG bot 用户感觉无响应
    - 观察后看是否需要拆成 /analyze_quick 版

v30.14.33 (2026-05-27 /analyze Sonnet 深度分析, Kings 新需求):
  • 🆕 /analyze admin 命令:
    - 自动跑 3 个核心诊断 (LONG diagnose + winrate score + SHORT winrate)
    - 拼接 → Claude Sonnet 4.5 深度分析
    - 跨周对比 (KV 快照) + 异常告警 + 新发现 + 推荐
    - ~30-60 秒, ~$0.03/次
  • 🆕 _call_sonnet() helper (复用 _call_haiku 模式, 改 model)
  • 🆕 _capture_cmd_output() helper:
    - 临时替换 send_tg_reply 把 cmd 输出捕获到字符串
    - 让 /analyze 能复用现成 cmd_diagnose / cmd_winrate
  • 🆕 KV:
    - analyze_snapshot_last (上次诊断快照, 跨次对比)
    - analyze_last_at (上次时间)
  • 🆕 Menu Bar 加 /analyze
  • ℹ️ 设计理由: Kings 不要 direct (env 关 999, 已证伪)

Bounty Monitor v30.14.32 (hotfix)
v30.14.32 hotfix (2026-05-26 修 dt NameError):
  • 🚨 CRITICAL fix: dt.fromisoformat → datetime.fromisoformat
  • 🚨 CRITICAL fix: dt.fromtimestamp → datetime.fromtimestamp
  • 🚨 CRITICAL fix: dt.strptime → datetime.strptime
  • 影响范围 (13 处):
    - settle_paper_positions (重灾, 每 10 min 都失败)
    - check_4h_alpha_recap / check_24h_recap (未触发, 潜在 bug)
    - push_daily_alpha_briefing (潜在 bug)
    - cmd_pnl (潜在 bug)
    - cmd_diagnose (try/except 救了)
  • 根因: 全局没定义 dt 别名, 我代码假设有
  • Kings 部署 v30.14.32 后 log 显示 [Settle] #1 entry_time 解析失败 N 次

v30.14.32 (2026-05-25 自动结算 + /pnl 升级):
  • 🆕 settle_paper_positions(conn) 自动结算 (方案 A 严格时间窗):
    - LONG (score/rebound): 1h 时间窗到, 用 1h close
    - SHORT (short/short_vip): 4h 时间窗到, 用 4h close
    - 止盈实时: LONG ≥+5% / SHORT ≤-3%
    - 止损实时: LONG ≤-3% / SHORT ≥+3%
    - 拉 5min K 线扫描 60 根 (5h 内)
  • 🆕 PnL 计算:
    - pnl_pct = close_pct × 10x (LONG) or -close_pct × 10x (SHORT)
    - pnl_usd = position_usd × pnl_pct / 100
    - 更新 paper_balance KV
  • 🆕 admin 私聊推平仓通知:
    - 含 ✅/❌/➖ + 出场理由 + PnL + 余额变化
  • 🆕 /pnl 升级:
    - 总 PnL + 胜率 (赢/输 N 单)
    - 余额变化 %
    - 持仓/已平数量分开显示
  • ⏰ 主循环每 10 min 调用 settle_paper_positions
  • ✅ Paper Trading 完整闭环: 入仓 → 跟踪 → 结算 → 余额更新

Bounty Monitor v30.14.31
v30.14.31 (2026-05-25 /pnl 命令 + Menu Bar + 启动 init):
  • 🆕 启动时 init Paper Trading (修 v30.14.30 admin 没收到欢迎):
    - 之前: init_paper_trading_db 只在第一个 60+ 信号时调用
    - 现在: main() 启动就 init, admin 立刻收到欢迎
  • 🆕 /pnl admin 命令 (纸上交易账户查询):
    - 当前余额 + 累计信号数 + 杠杆/仓位配置
    - 通道分布 (score/short/short_vip/rebound 每通道单数和 PnL)
    - 当前开仓 (前 10 单, 含持仓时长)
    - 最近完成 (Top 10, 含 PnL + 出场原因)
    - 鉴权: 仅 admin (跟 /diagnose /growth 同模式)
  • 🆕 TG Bot Menu Bar (左下角斜杠菜单):
    - setMyCommands API 设置 10 个命令
    - /start /help /top /defi /whale /pnl /winrate /diagnose /growth /about
    - 启动时调用, 用户在聊天框看到菜单选项
  • ⏳ v30.14.32 计划:
    - Tracker 自动结算 paper_positions.status (1h LONG / 4h SHORT 时间窗到)
    - 真正更新 balance (现在只入仓不结算, 永远 'open')

Bounty Monitor v30.14.30
v30.14.30 (2026-05-23 Paper Trading + 复盘编号化, Kings 产品方向变化):
  • 🆕 Paper Trading 纸上交易系统:
    - 初始本金 $1000 USDT, 杠杆 10x, 每单 10% × 余额
    - 全 4 通道入仓 (score + short + short_vip + rebound)
    - signal_no 全局递增 (#001, #002, ...)
    - 表 paper_positions + KV (paper_balance, paper_next_signal_no)
  • 🆕 推送架构 (Kings 明确要求):
    - 复盘帖 → 进频道 (公开教育, 含 #编号 + 精确时间)
    - 纸上开仓通知 → admin 私聊 (dogfood 内部数据)
    - 账户初始化 → admin 私聊一条欢迎
  • 🆕 24h 复盘文案改进 (进频道):
    - 加 #signal_no 编号 (例: 📊 LONG #042 复盘 · $XYZ)
    - 加精确入场时间 (2026-05-23 14:32 UTC)
    - 不含 paper trading 内部数据 (本金/PnL 留 admin 看)
  • 🆕 1h FOMO 复盘也加 #编号 + 精确时间 (Kings 追加要求, 统一体验):
    - "🔥 赏金哨 #042 · 1h 实战复盘"
    - 时间显示 "05-23 14:32 UTC 推送" 替代 "1h 前推送"
  • 🆕 新增 4h alpha 复盘 (check_4h_alpha_recap, 进频道):
    - 触发: signal_time 在 4-5h 前 + recap_4h_done=0
    - 数据: 4h 内 5min K 线找 peak/valley (48 根)
    - 文案: ⏰ {direction} #042 4h 复盘 · ${sym}
    - SHORT 4h 是黄金窗口 (历史 78% 胜率), 这个复盘特别有价值
    - LONG/rebound 1h 内 peak 提示
    - 加 recap_4h_done 字段 (ALTER TABLE if not exists)
  • ℹ️ 4h price_alert 复盘不动 (跟 paper trading 不同信号源)
  • ℹ️ 复盘体系最终架构 (3 个 sentinel alpha 复盘):
    - 1h FOMO ≥3% (选择性推, 选 alpha 兑现)
    - 4h alpha (全推, SHORT 黄金窗)
    - 24h recap (全推, 完整验证)
  • 🆕 admin 私聊开仓通知:
    - 含本金/杠杆/名义/通道/账户余额/当前开仓数
    - 用户看不到, 你 dogfood
  • ⏳ v30.14.31 计划:
    - /pnl admin 命令 (账户/胜率/通道分布)
    - Tracker 自动结算更新 balance
    - 未来接 Binance Futures 实盘

Bounty Monitor v30.14.29
v30.14.29 (2026-05-23 Daily Alpha Briefing, Kings 新需求):
  • 🆕 push_daily_alpha_briefing(): 每天北京 08:00 (UTC 0:00) admin 私聊推 alpha 报告
    B+C 组合:
    - 平日: 智能告警 (alpha 变化 ≥5% 或有新 VIP 时才推)
    - 周日: 完整周报 (所有规则 + VIP + 跨周对比)
  • 🆕 _compute_alpha_snapshot(conn, days): 计算关键 alpha 快照
    - LONG: 6 个核心维度 (score 段, 24h 段, cross, funding)
    - SHORT: 4 个核心维度 (cross, funding 区间, OI)
    - 用 sentinel_signals 表 + BN K 线反查
  • 🆕 KV keys:
    - alpha_snapshot_prev_week: 上周日快照, 跨周对比基准
    - alpha_snapshot_today: 今日快照, 每天更新
    - last_alpha_briefing_date: 防今天重复推
  • 🆕 SHORT VIP 信号区分 tracker channel='short_vip'
    - check_signal_trackers / _send_signal_tracker_alert / check_24h_recap 全兼容
  • ⏰ 触发条件:
    - now.hour == 0 (UTC 0:00 = 北京 8:00)
    - 今天没推过 (KV check)
  • 📊 报告含 VIP 信号 24h 后实测验证
  • 📝 推送到 TG_ADMIN_CHAT_ID, 不是频道

Bounty Monitor v30.14.28
v30.14.28 (2026-05-22 Morning Brief Square 纯化, Kings 重定义需求):
  • 🎯 Kings 要求: "不要 hashtag, 不要链接, 只要早报"
  • 🐛 修复 Morning Brief 推 Square 连续 2 天失败:
    - 5/21 code=20022 敏感词 (Haiku 自由发挥)
    - 5/22 code=220094 Hashtag 超限 (Haiku + hardcode 6 个超限)
  • 修改 build_square_text_for_morning_brief:
    - 砍 hardcode hashtag (#币圈早报 等 6 个)
    - 砍 @ 提及 (@币世赏金台)
    - 过滤 Haiku 正文里的 #xxx 和 @xxx (正则)
    - 截断兜底也不加 hashtag
  • Footer 只保留 "⚠️ 仅供研究, 不构成交易建议"
  • 影响范围: 仅 Morning Brief 进 Square, TG 频道推送不变

Bounty Monitor v30.14.27
v30.14.27 (2026-05-22 SHORT 三件套优化, 基于 /diagnose 30 short n=104):
  • 🆕 A: funding 0.02-0.04% 段 SHORT 跳过
    - 数据: 此段历史 SHORT 赢率 29% (n=21) ⚠️ 反向区
    - 仅 0-0.02% (未拥挤) 和 ≥0.04% (拥挤必爆) 是甜区
    - 加 log [SHORT/funding-skip]
  • 🆕 B: SHORT VIP 标记
    - 触发任一甜区维度自动加 "⭐⭐ VIP 高确定性" 标签:
      • cross ≥10 (历史 76%)
      • funding ≥0.04% (历史 79%)
      • OI 子分 ≥18 (历史 62%)
    - 不分流通道, 同一推送加 VIP 因子说明
    - 用户能看出"普通 SHORT" vs "VIP SHORT"
  • 🆕 D: SHORT/rebound/score 24h 自动复盘帖
    - 新函数 check_24h_recap, 复用 signal_tracker 表
    - 加 recap_done 字段 (ALTER TABLE if not exists)
    - 24-26h 后自动拉 24h K 线, 找 peak/valley + 复盘叙事
    - 含 verdict (✅胜/❌输/➖平), 最优出场点, 实战教训
    - 用户教育 + 频道 engagement, 真长期 alpha
  • ℹ️ 数据警告: SHORT VIP 各维度 n=8-24, 跨周复跑后才确诊
    - 6/19 跑 /diagnose 30 short 第 2 次确认

Bounty Monitor v30.14.26
v30.14.26 (2026-05-19 紧急修 /growth bug):
  • 🐛 /growth N 报 "'list' object has no attribute 'strip'":
    根因: cmd handler 传进来的 args 是 list 不是 str, 我之前直接 .strip().split()
    修复: isinstance 判断, 兼容 list 和 str

Bounty Monitor v30.14.25
v30.14.25 (2026-05-18 Kings 决策, 基于 /diagnose 30 + /winrate 30 score 双数据源):
  • 🎯 加 4 条避雷过滤规则到 score/direct 通道 (基于 n=500 数据):
    1. score >= 66 → watch (赢率仅 6%, 顶部 FOMO 陷阱)
    2. cross >= 10 → watch (赢率 0%, 双所确认是末日)
    3. funding 8h >= 0.04% → watch (赢率 19%, 多头拥挤)
    4. 24h 涨幅 5-10% → watch (赢率 12%, 接力盘重灾)
  • 🆕 新通道 "rebound" (超跌反弹):
    - 触发: score≥50 + 24h≤-5% + OI 1h≥30% + funding 干净
    - 数据依据: /diagnose 显示 24h≤-5% 段赢率 76% (n=58)
    - 跟 SHORT 反向 (SHORT 抓 24h>10%, rebound 抓 24h<-5%)
    - 文案: "🔄 超跌反弹候选 · 1h 内出场 · 止盈+5% · 止损-3%"
    - 同步 Square 用 hashtag #超跌反弹 #抄底
    - 入 signal_tracker LONG 模式 (复用 -3%/+5%/1h)
    - 4h 同币冷却
  • ℹ️ Kings 需在 Railway 把 SENTINEL_PUSH_THRESHOLD 改回 60 (从 999), 重开 LONG

Bounty Monitor v30.14.24
v30.14.24 (2026-05-18 终于修对 /diagnose 时间解析):
  • 🎯 v30.14.23 暴露样本字符串: '2026-05-16 02:54 UTC' (无秒 + 带 UTC 后缀)
    根因: 历史 sentinel_signals 数据时间字段不是 SQLite datetime('now') 直接写,
    是代码某处手动 strftime("%Y-%m-%d %H:%M UTC") 写的, 我之前 6 种格式都不匹配.
  • 修复:
    - 加 '%Y-%m-%d %H:%M' 格式 (无秒) 到 strptime 第二个尝试
    - 末尾 " UTC" / " GMT" 文本智能剔除
    - 现共 8 种格式 + fromisoformat 兜底

Bounty Monitor v30.14.23
v30.14.23 (2026-05-18 紧急修复 /diagnose 时间解析全失败):
  • 🐛 修 v30.14.22 跑 /diagnose 后仍"时间格式解析失败: 500/500":
    - 加 isinstance str 转换 (兼容 datetime 对象)
    - 扩展到 6 种 strptime 格式 + fromisoformat 兜底
    - 暴露失败样本字符串给 admin (sample_time), 找出第 7 种格式
  • 调试逻辑: 至少有一种格式能 fallback 解析

Bounty Monitor v30.14.22
v30.14.22 (2026-05-18 紧急修复 /diagnose 0 样本问题):
  • 🐛 修 /diagnose 反查后 0 条问题:
    根因: 老 sentinel_signals 数据 (v30.1 之前) signal_time 字段 NULL,
    fetch_close 直接 return None 跳过. 30 天数据里老条目占多数 → 全跳.
  • 修复: signal_time 用 COALESCE 回退到 recorded_at (NOT NULL).
  • 加多种时间格式兼容 (ISO / datetime / 含毫秒和时区).
  • 加调试统计: 失败时输出"无时间/无价格/格式解析/K 线反查 各失败几条", 不再黑盒.

Bounty Monitor v30.14.21
v30.14.21 (2026-05-16 Kings 决策, /diagnose 输赢双向诊断):
  • 🆕 /diagnose [days] [channel] (admin only):
    - 拉 sentinel_signals 历史数据 (默认 30 天)
    - 反查 24h K 线得 close_pct
    - LONG 视角: close ≥+3% 算赢, close ≤-3% 算输 (实战伤害定义)
    - SHORT 视角: close ≤-3% 算赢, close >0 算输
    - 切片 6 个维度: 评分段 / 24h 涨幅 / funding / OI 子分 / price 子分 / cross 子分
    - 标记 ✅ 甜区 (赢率 ≥60%) / 💀 重灾 (≤20%) / ⚠️ 弱区 (≤35%) / 样本小 (<5)
    - 列出输得最惨 + 赢得最好 Top 5 明细
  • 🛑 设计原则 (Claude push back 后):
    - 纯 Python 统计, 不接 LLM (避免幻觉 + 不可复现)
    - 不自动改阈值 (Kings 自己看完拍板)
    - 不做 AutoML (n=34-100 用 AutoML 必过拟合)
  • ℹ️ 数据源充足: sentinel_signals 无清理, 30 天数据完整

Bounty Monitor v30.14.20
v30.14.20 (2026-05-15 Kings 决策, 激活 SHORT 进频道):
  • 🟢 P0 SHORT 通道默认进频道: SENTINEL_SHORT_DOGFOOD 默认 1 → 0
    数据依据: 5/15 /winrate 7 short 显示 n=46 样本下:
      • 1h 做空胜率 72% / 均收益 +2.15%
      • 4h 做空胜率 67% / 均收益 +3.30% ⭐ 最强
      • 24h 胜率 50% / 均亏 -8.94% (反向 ≥+3% 高达 48% — 绝禁过夜)
    env SENTINEL_SHORT_DOGFOOD=1 可回退 admin 私聊
  • 🆕 SHORT 推送文案 (跟 long 分开):
    "🔻 FOMO 顶部空头信号 · 4h 内出场 · 严禁过夜"
    "🎯 止盈 -3% · 🚨 反向止损 +3%"
    "历史 4h 胜率 67%, 均 +3.30% (n=46)"
  • 🆕 signal_tracker 加 SHORT 模式:
    - SHORT 止盈: gain ≤ -3% → "🎯 SHORT 已下跌 3%"
    - SHORT 止损: gain ≥ +3% → "🚨 反向上涨 3%"
    - SHORT 时间止损: ≥ 235 min (4h-5min 缓冲) → "⏰ 4h 时间窗已到, 严禁过夜"
    - env TRACKER_SHORT_TP_PCT / SL_PCT / TIME_WINDOW_MIN 可调
  • 🆕 SHORT 同步发 Binance Square (跟 long 一致), 用做空 hashtag #做空 #FOMO顶部

Bounty Monitor v30.14.19
v30.14.19 (2026-05-15 Kings 决策, /winrate 加 SHORT 支持):
  • 🆕 /winrate short 命令: 查 SHORT dogfood 触发的所有信号胜率
    - 查询条件: push_channel='watch' AND score>=60 AND change_24h>10 (匹配 SHORT dogfood 触发)
    - 胜率反转: 1h close < entry 算胜 (做空赚)
    - 显示: 做空胜率 / close ≤-3% 命中率 / 反向 ≥+3% 止损位
    - 跳过对照组 (SHORT 没合适基准)
    - 跳过 cross 诊断 (对做空无意义)
    - Top/Bottom 反转语义 (谷越深越好, 峰越高越坏)
  • 修复 5/15 Kings 跑 /winrate short 返回普通 winrate 的问题 (原代码白名单只认 direct/score)

Bounty Monitor v30.14.18
v30.14.18 (2026-05-13 Kings 决策, 基于 /growth 数据):
  • 🔴 P0 频道减载: SENTINEL_PUSH_THRESHOLD 默认 50 → 60
    根因: /growth 显示 7 天合计 795 条 (113/天), score 占 531 (75/天) 严重过载.
    用户 653 个被刷屏 113 次/天, 是流失隐藏杀手.
    实测数据: 30h log 里 50+ 触发 48 次, 60+ 仅 7 次 → 提阈值减 85% score 推送.
    预期总推送: 113/天 → ~43/天 (减约 60%).
    env SENTINEL_PUSH_THRESHOLD 可调.
  • ℹ️ 备忘: 不加同币冷却, 因 SENTINEL_COOLDOWN_HOURS=4 已存在.

Bounty Monitor v30.14.17
v30.14.17 (2026-05-12 紧急修复, Claude 责任事故):
  • 🔴 v30.14.16 部署后 bot 无限重启:
    根因: cmd_growth str_replace 误吞了 cmd_search 函数声明行 (def 行),
    函数体留下成游离代码, 但 COMMANDS 字典引用 cmd_search 找不到 → NameError.
    py_compile 检查语法不查名字引用, 漏抓.
  • 🐛 修复: 在 snapshot_subscriber_count 之后补回 def cmd_search 声明行.
  • 💡 教训记下: 以后 str_replace 时 old_str 必须包含目标函数完整签名, 
    new_str 不能改函数声明; 改完后必须 grep -c "^def cmd_search" 验证函数数量没少.

v30.14.16 (2026-05-11 Kings 决策, 频道增长诊断):
  • 🆕 /growth 命令 (admin only): 频道订阅数 + 推送量 + 趋势对比
    数据来源: bot API getChatMemberCount + sentinel_signals/whale_alerts 表
    不依赖 MTProto, 不依赖个人账号, 100% 安全 (但拿不到 views/forwards)
  • 🆕 每天 23:59 北京 (UTC 15:00) 后台抓订阅数落 KV (供未来日变化对比)
  • cmd_help 加 /growth 入口

v30.14.15 (2026-05-11 Kings 决策, 基于 /winrate 7 数据驱动):
  • 🟢 P0 score 通道恢复进频道: SCORE_CHANNEL_DOGFOOD 默认 1 → 0
    依据: dogfood 2 周后 /winrate 7 显示 score 24h close 胜率 56% / 均收益 +4.19% / Alpha +11%,
    数据反转 (v30.13.6 时三窗口全负 → 现在 24h 显著正 alpha), 可重新进频道.
    env SCORE_CHANNEL_DOGFOOD=1 可强制回 dogfood.
  • 🔴 P0 收紧 direct 渠道门槛: SENTINEL_MAX_CHANGE_24H 默认 5 → 3
    根因: 5/11 winrate 显示 direct 24h close 胜率仅 24% / 均 -7.88%, n=99 可信.
    OI 暴涨 +25% 但 24h 价格 ≤5% 实际是杠杆已堆叠后, 散户接到顶部接力盘. 收紧到 ≤3% 抓更早期阶段.
    env SENTINEL_MAX_CHANGE_24H 可调.
  • 🐛 改 TG 频道和 Square 文案 (分 direct/score 两套):
    direct (24h close 胜率仅 24%): "1-4h 内出场, 严守 -3% 止损"
    score (24h close 胜率 56% Alpha +11%): "4-24h 内出场最佳"
    旧统一文案"1h 内出场" 误导订阅者, score 真正 Alpha 在 24h.
  • 🐛 修 /winrate 显示 "鲸鱼共振 0/100" 误导:
    鲸鱼维度早在 v30+ 已废 (components[whale]=0), 真正 15 分权重是 cross (BN+HL 共所一致).
    新文案明确 "鲸鱼维度早在 v30+ 已废" + "此处 0 触发属预期".

v30.14.14 (2026-05-11 Kings 决策, Morning Brief 数据源加固):
  • 🔴 P0 数据严格度校验: 必须 (movers≥3 或 events≥5) 才推送, 否则跳过返回 False, 
    主循环不写 KV 30min 后重试. 修复 5/11 Coingecko 429 + 中文源 410 双挂时, 
    Haiku 凭训练数据编"以太坊年跌 35%"的幻觉问题.
  • 🐛 Coingecko 加 retry (429 等 5/10s 重试 2 次) + 浏览器 UA. 
    旧 "Mozilla/5.0" 太通用被识别 bot.
  • 🐛 删除 cn.cointelegraph.com 默认源 (HTTP 410 Gone 永久死链). 用户可通过
    env MORNING_CN_RSS_URLS 自配中文源.
  • 🆕 新增 Coingecko Trending Top 7 作为热搜锚点 (替代中文源消失留的窟窿).
  • 🐛 prompt 加硬规则: "严格禁止任何上面数据里没有的数字 (例如年跌幅、季度数据、
    市值排名等, 我没给的就不要写)" — 反 LLM 幻觉.

v30.14.13 (2026-05-10 Kings 决策, 紧急修复):
  • 🔴 修复爆仓警报误推 (麻吉大哥 BTC $91 假爆仓):
    - 根因: HL fills API 在每笔清算交易的双方 (maker+taker) 都会附带 'liquidation' 字段,
      代码看到 liquidation != None 就判 is_liq=True. 但鲸鱼作为对手盘接盘侠时也会收到这字段.
    - 修复: 必须 liquidatedUser 字段等于本鲸鱼地址才算真爆仓. 加亏损 <$1K 二次过滤兜底.
  • 🐛 修鲸鱼活跃度周报误推频道 (Kings 5/11 决策):
    - 旧逻辑用 send_tg 推到 640 人公频, 含 'id: james_wynn' 内部 ID 和 'GitHub 编辑 whale_list.json'
      运维指令, 订阅者看到 confused. 改 admin 私推 (跟 InitialReport 一致模式).

v30.14.12 (2026-05-10 Kings 决策, Twitter 用户 @TheReality32 提需求):
  • 🆕 信号实时价格追踪 (Signal Tracker):
    - 信号推送时入队, SentinelFast 每 600s 检查所有 pending 追踪
    - 触发条件 (按优先级): 浮盈 ≥+5% / 浮亏 ≤-3% / 1h 时间到 (3 选 1, 先到的)
    - 文案严格"只给数据不写建议": "已触达 +5% 浮盈位, 自行判断是否止盈" 而非 "建议平仓"
    - 每信号只触发 1 次, 防刷屏
    - env 可调:
      * TRACKER_TAKE_PROFIT_PCT (默认 5.0)
      * TRACKER_STOP_LOSS_PCT (默认 -3.0)
      * TRACKER_TIME_WINDOW_MIN (默认 55, 留 5min 缓冲)
    - 新表 signal_tracker, 跟 sentinel_fomo_followup 平行 (独立去重独立逻辑)
    - 副作用清单: 不影响现有 FOMO 1h 复盘 / 24h 焦点 / 早报, 完全独立模块

v30.14.11 (2026-05-10 Kings 决策, AI Brief 修复 + 漏传第三版改动一并打包):
  • 🔴 修 AI Brief 24h 焦点重复内容问题:
    - 6h 冷却 → 12h (env AI_BRIEF_COOLDOWN_H 可调)
    - 触发条件: 24h 累计 ≥3 sentinel → "自上次 brief 后新增 ≥3 sentinel"
    - 静默兜底 18h → 24h (env AI_BRIEF_SILENCE_FALLBACK_H 可调)
  • 🐛 修 markdown 渗漏: AI Brief 和 Morning Brief 的 system prompt 加硬性禁令
    "绝对禁止 ** 加粗、## 标题、* 斜体", 防止 Haiku 写出 **赏金哨·24h焦点** 这种重复加粗
  • 🐛 修 Morning Brief KV 顺序 bug: kv_set 移到 push 成功之后, 防止推送失败但 KV
    锁住整天导致下一次主循环跳过

v30.14.10 (2026-05-10 Kings 决策, 多轮迭代):
  • 鲸鱼盈亏榜标题动态化 — 1 个时显示"24h 盈亏" (不写 Top), 2-4 个 "Top N",
    ≥5 个 "Top 5 精选". 修复新增鲸鱼前 24h 数据未满时榜单看起来像 bug 的问题.
  • 🆕 赏金哨·早报 (Morning Brief, 每天北京 11:00 / UTC 3:00):
    - 数据源: Coingecko Top 5 涨跌 + Cointelegraph 英文 RSS + 中文 RSS (Cointelegraph 中文版默认) + 链上独家锚点
    - Haiku 4.5 生成正文, 鲸群独家段硬编码 (避免 AI 编数字)
    - 跟 24h 焦点互补 (那个是触发驱动内部回顾, 这个是固定时间外部新闻)
    - 同步发币安广场 (__morning_brief__, 防重复每日 1 次)
    - 月成本 <$0.30
    - env 开关: MORNING_BRIEF_ENABLED=1 (默认开)
    - env 加源: MORNING_CN_RSS_URLS=url1,url2 (默认 cn.cointelegraph.com)
  • 🐛 hotfix tail 标签截断: alert_type "morning_brief" (13 字符) 被 make_tail 截到
    "morning_brie", 改用 "morning" (7 字符) 一刀切.
  • 🐛 hotfix prompt: 加约束"用词必须标准书面汉语, 不要造词", 防止 Haiku 写出"波澜"
    这种生造词. 加规则"中文头条优先, 英文头条翻译生硬就跳过", 减少机翻味.

v30.14.9 (2026-05-09 Kings 决策):
  • 移除 whale 4h 复盘 (信号未走完, 容易反向印象, 24h 已足够)
  • 修价格分注释 (实际满分 17 而非 24, 代码档位不动)
  • Sentinel score v2 shadow 继续收集中, 5/11 跑 /winrate v2

Bounty Monitor v27.0
v26.5 + 🐋 Hyperliquid 鲸鱼追踪:

v27.0 新增:
  • 鲸鱼 watchlist 实时追踪 (whale_list.json 配置, 手机端 GitHub 直接编辑)
  • 事件检测: 开仓 / 加仓 / 减仓 / 反手 / 平仓 / 清算临近
  • 起步名单 (6 个活跃 + 2 个待验证):
    - 🃏 麻吉大哥 (@machibigbrother, 清算王 335 次)
    - 🎴 麻吉小弟 (machismallbrother.eth)
    - 🇺🇸 特朗普内幕鲸鱼 (2 个地址)
    - 🤍 白鲸 White Whale (@TheWhiteWhaleHL, 4 个地址)
    - 🎯 James Wynn (@JamesWynnReal, 2 个地址)
    - 🕵️ 内幕老哥 qwatio (待验证)
  • 冷却机制: 同鲸鱼 30 分钟不重复推
  • 触发阈值: 仓位变化 >$500K 或 >10%
  • 数据源: Hyperliquid REST API (免费无限)
  • 存储: whale_positions 表 (历史快照) + whale_alerts 表 (冷却记录)

v26.5 历史:
  • 价格异动图表: 样式 6b 卡片式 + @币世赏金台 水印
  • 方案 B 温和版 caption

v26.4 历史:
  • 所有 alert 函数统一 HTML 转义 + 关键数字加粗

v26.3 历史:
  • Telegram HTML parse_mode + 自动转义 + 降级安全网

v26.2 历史:
  • Format A 格式 (圆圈数字前置)
  • 完整 URL 回归
  • Blue-chip bug 修复

v26.1 历史:
  • 数字编号 digest 格式
  • fmt_defi_compact / fmt_bounty_compact

v26 历史:
  • 尾行标签 + /v 命令 + SQLite 多线程 + 哑巴失败 + requirements.txt 锁版本

v25 历史:
v24 + 全面升级:
  • 数字编号 + 分隔线格式 (digest 推送) ← 分隔线已在 v26.2 移除
  • fmt_defi_compact / fmt_bounty_compact (紧凑格式)
  • 修复 sid 碰撞 bug (同 URL 不同产品)

v26 历史:
  • 尾行标签 (📎 bm-xxxx | v... | r... | src | type)
  • /v <short_id> 命令
  • SQLite 多线程安全
  • 哑巴失败报警
  • requirements.txt 锁版本

v25 历史:
v24 + 全面升级:

Bug 修复:
  • Barker payouts 解析增强
  • 移除 Binance CreatorPad (Browserless 不稳定, CEX/DEX Earn 已覆盖)
  • GitHub 403 - 支持 GITHUB_TOKEN + 降频
  • APY 变动只追踪 DeFiLlama (稳定 pool_id)

新增监控 (全部免 key 公开 API):
  • 稳定币脱锚警报 (CoinGecko: price < $0.995)
  • Binance 新币上线公告追踪
  • Snapshot 治理提案追踪 (Top 协议)
  • Perps 资金费率异动 (Hyperliquid 全量)
  • 跨链 APY 套利对比 (同协议跨链)

注: CEX Earn API 全部需签名, 继续使用 Barker 聚合

新增配置:
  GITHUB_TOKEN - GitHub API token (可选, 60→5000 req/h)
"""

import requests
import time
import re
import os
import json
import sqlite3
import traceback
import io
import threading
import hashlib
import html
from collections import OrderedDict
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
from datetime import timezone

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    print("[Warning] matplotlib not installed, weekly chart disabled")


# 🆕 v27.3.1: Python 3.12 兼容 — 替代 _utcnow() 避免 DeprecationWarning
def _utcnow():
    """返回 naive UTC datetime, 行为等同于 deprecated _utcnow()"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# 中文字体路径 (运行时下载到 /data 持久化)
CHINESE_FONT_URL = "https://github.com/StellarCN/scp_zh/raw/master/fonts/SimHei.ttf"
CHINESE_FONT_PATH = "/data/SimHei.ttf" if os.path.isdir("/data") else "SimHei.ttf"

def ensure_chinese_font():
    """确保中文字体可用 (首次运行下载)"""
    if not HAS_MATPLOTLIB:
        return None
    if os.path.exists(CHINESE_FONT_PATH):
        return CHINESE_FONT_PATH
    try:
        print(f"[Font] 下载中文字体到 {CHINESE_FONT_PATH}...")
        r = requests.get(CHINESE_FONT_URL, timeout=60)
        r.raise_for_status()
        with open(CHINESE_FONT_PATH, 'wb') as f:
            f.write(r.content)
        print(f"[Font] ✅ 已下载 ({len(r.content)/1024:.0f}KB)")
        return CHINESE_FONT_PATH
    except Exception as e:
        print(f"[Font] ❌ 下载失败: {e}")
        return None

# ============================================================
# 配置
# ============================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
# 🆕 v30.12: admin chat id (私人命令如 /winrate 仅 admin 可用)
TG_ADMIN_CHAT_ID = os.getenv("TG_ADMIN_CHAT_ID", "")


# 🆕 v30.13.1: 安全的环境变量数值读取
# 修复: 空字符串 env var (Railway 误创建空值变量) 导致 float("")/int("") crash bot
def _env_float(key, default):
    """读取 float env var, 空字符串/无效值时返回 default"""
    v = os.getenv(key, "")
    if not v or not v.strip():
        return float(default)
    try:
        return float(v)
    except (ValueError, TypeError):
        print(f"[Env] ⚠️ {key}='{v}' 无法转 float, 用默认 {default}")
        return float(default)


def _env_int(key, default):
    """读取 int env var, 空字符串/无效值时返回 default"""
    v = os.getenv(key, "")
    if not v or not v.strip():
        return int(default)
    try:
        return int(float(v))  # 通过 float 中转, 容忍 "5.0" 这种值
    except (ValueError, TypeError):
        print(f"[Env] ⚠️ {key}='{v}' 无法转 int, 用默认 {default}")
        return int(default)

BROWSERLESS_API = os.getenv("BROWSERLESS_API", "")
MIN_VALUE = _env_int("MIN_VALUE", "300")
CHECK_INTERVAL = _env_int("CHECK_INTERVAL", "1800")
# 🆕 v28.6: OI 告警最低门槛 (过滤小币噪音)
OI_MIN_USD = _env_int("OI_MIN_USD", "50000000")  # 默认 $50M, 可覆盖调低
DB_PATH = os.getenv("DB_PATH", "/data/bounty_monitor.db" if os.path.isdir("/data") else "bounty_monitor.db")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")  # v25: 可选, 提升 GitHub 限速
HACKERONE_USER = os.getenv("HACKERONE_USER", "")  # v25+: HackerOne API username
HACKERONE_TOKEN = os.getenv("HACKERONE_TOKEN", "")  # v25+: HackerOne API token
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")  # v25+: Firecrawl fallback scraper
HL_REFERRAL = "https://app.hyperliquid.xyz/join/KINGSSS"  # Hyperliquid 推荐链接

# TVL 报警阈值
TVL_WARN_PCT = _env_float("TVL_WARN_PCT", "20")     # 黄色预警
TVL_ALERT_PCT = _env_float("TVL_ALERT_PCT", "40")   # 红色报警
TVL_CRIT_PCT = _env_float("TVL_CRIT_PCT", "60")     # 紧急 Rug 报警
TVL_MIN_USD = _env_float("TVL_MIN_USD", "5000000")   # 只监控 TVL > $5M 的协议
TVL_TOP_N = _env_int("TVL_TOP_N", "200")             # 监控 Top N 协议

# ============================================================
# SQLite 持久化
# ============================================================
# v26: SQLite 跨线程锁 (bot 线程 / fetcher 线程 / 主循环共用 conn)
_db_lock = threading.RLock()

def init_db():
    # v26: check_same_thread=False 允许跨线程 (配合 _db_lock 保证安全)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    # 🆕 v30.12: 通用 KV 状态表 (重启后保留 daily_push / digest_fp 等状态, 防止 redeploy 重复推送)
    c.execute("""CREATE TABLE IF NOT EXISTS kv_state (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS seen_urls (
        url TEXT PRIMARY KEY,
        source TEXT,
        title TEXT,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS tvl_history (
        protocol TEXT,
        tvl REAL,
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (protocol, recorded_at)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS tvl_alerts (
        protocol TEXT,
        alert_type TEXT,
        drop_pct REAL,
        alerted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (protocol, alerted_at)
    )""")
    # v23: APY 历史追踪
    c.execute("""CREATE TABLE IF NOT EXISTS apy_history (
        pool_key TEXT,
        apy REAL,
        tvl REAL DEFAULT 0,
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (pool_key, recorded_at)
    )""")
    # v23: 倒计时已提醒记录
    c.execute("""CREATE TABLE IF NOT EXISTS deadline_alerts (
        url TEXT,
        alert_type TEXT,
        alerted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (url, alert_type)
    )""")
    # v24: 空投通知去重
    c.execute("""CREATE TABLE IF NOT EXISTS airdrop_alerts (
        slug TEXT PRIMARY KEY,
        alerted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    # v25: 通用去重表 (脱锚/上新/治理/资金费率)
    c.execute("""CREATE TABLE IF NOT EXISTS generic_alerts (
        alert_type TEXT,
        alert_key TEXT,
        alerted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (alert_type, alert_key)
    )""")
    # v25+: OI 历史追踪
    c.execute("""CREATE TABLE IF NOT EXISTS oi_history (
        symbol TEXT PRIMARY KEY,
        oi_value REAL,
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    # v25+: 价格历史 (用于异动检测)
    c.execute("""CREATE TABLE IF NOT EXISTS price_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        price REAL,
        oi_usd REAL DEFAULT 0,
        funding_rate REAL DEFAULT 0,
        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_price_symbol_time ON price_history(symbol, recorded_at)")
    # v25: 索引 (加速常用查询)
    c.execute("CREATE INDEX IF NOT EXISTS idx_seen_first ON seen_urls(first_seen)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_seen_source ON seen_urls(source)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_apy_recorded ON apy_history(pool_key, recorded_at DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_tvl_recorded ON tvl_history(protocol, recorded_at DESC)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_deadline_alerted ON deadline_alerts(alerted_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_generic_alerted ON generic_alerts(alerted_at)")
    conn.commit()
    return conn

def is_seen(conn, url):
    return conn.execute("SELECT 1 FROM seen_urls WHERE url=?", (url,)).fetchone() is not None

def mark_seen(conn, url, source="", title=""):
    try:
        conn.execute("INSERT OR IGNORE INTO seen_urls (url, source, title) VALUES (?,?,?)",
                      (url, source, title))
        conn.commit()
    except Exception:
        pass

def save_tvl(conn, protocol, tvl):
    try:
        conn.execute("INSERT OR REPLACE INTO tvl_history (protocol, tvl, recorded_at) VALUES (?,?,?)",
                      (protocol, tvl, datetime.now(timezone.utc).isoformat()))
        conn.commit()
    except Exception:
        pass

def get_prev_tvl(conn, protocol):
    """获取上一次记录的 TVL（至少 30 分钟前的最新记录）"""
    row = conn.execute("""
        SELECT tvl FROM tvl_history
        WHERE protocol=? AND recorded_at < datetime('now', '-25 minutes')
        ORDER BY recorded_at DESC LIMIT 1
    """, (protocol,)).fetchone()
    return row[0] if row else None

def was_alerted_recently(conn, protocol, hours=6):
    """检查最近 N 小时内是否已报过警"""
    row = conn.execute("""
        SELECT 1 FROM tvl_alerts
        WHERE protocol=? AND alerted_at > datetime('now', ? || ' hours')
    """, (protocol, f"-{hours}")).fetchone()
    return row is not None

def record_alert(conn, protocol, alert_type, drop_pct):
    try:
        conn.execute("INSERT INTO tvl_alerts (protocol, alert_type, drop_pct) VALUES (?,?,?)",
                      (protocol, alert_type, drop_pct))
        conn.commit()
    except Exception:
        pass

def cleanup_old_data(conn, days=7):
    """清理 N 天前的历史数据"""
    try:
        conn.execute("DELETE FROM tvl_history WHERE recorded_at < datetime('now', ? || ' days')", (f"-{days}",))
        conn.execute("DELETE FROM tvl_alerts WHERE alerted_at < datetime('now', ? || ' days')", (f"-{days}",))
        conn.execute("DELETE FROM apy_history WHERE recorded_at < datetime('now', ? || ' days')", (f"-{days}",))
        conn.execute("DELETE FROM deadline_alerts WHERE alerted_at < datetime('now', ? || ' days')", (f"-{days}",))
        conn.execute("DELETE FROM airdrop_alerts WHERE alerted_at < datetime('now', '-30 days')")
        conn.execute("DELETE FROM generic_alerts WHERE alerted_at < datetime('now', '-7 days')")
        conn.execute("DELETE FROM oi_history WHERE recorded_at < datetime('now', '-3 days')")
        conn.execute("DELETE FROM price_history WHERE recorded_at < datetime('now', '-35 days')")
        conn.commit()
    except Exception:
        pass

# v25: 通用去重 (用于脱锚/上新/治理/资金费率)
def is_alerted(conn, alert_type, alert_key, hours=24):
    """检查 N 小时内是否已通知过"""
    try:
        row = conn.execute(
            "SELECT 1 FROM generic_alerts WHERE alert_type=? AND alert_key=? AND alerted_at > datetime('now', ? || ' hours')",
            (alert_type, alert_key, f"-{hours}")
        ).fetchone()
        return row is not None
    except Exception:
        return False

def mark_alerted(conn, alert_type, alert_key):
    try:
        conn.execute(
            "INSERT OR REPLACE INTO generic_alerts (alert_type, alert_key, alerted_at) VALUES (?,?,?)",
            (alert_type, alert_key, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
    except Exception:
        pass


# 🆕 v30.12: 通用 KV 状态持久化 (跨重启保留 last_daily_push / digest_fp 等)
# 修复 redeploy 后重发问题: 启动横幅 / Top 5 / DoraHacks 汇总 / 每日提醒
def kv_get(conn, key, default=None):
    """从 kv_state 读 value (str). 不存在返回 default"""
    try:
        row = conn.execute("SELECT value FROM kv_state WHERE key=?", (key,)).fetchone()
        return row[0] if row else default
    except Exception:
        return default


def kv_set(conn, key, value):
    """写入 kv_state. value 自动转 str"""
    try:
        conn.execute(
            "INSERT INTO kv_state(key, value, updated_at) VALUES(?,?,datetime('now')) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, str(value))
        )
        conn.commit()
    except Exception as e:
        print(f"[KV] set {key} 错误: {e}")

# ============================================================
# 🆕 v26: Pipeline 尾行标签 + 反查注册表
# ============================================================
# 格式: 📎 bm-a7f3 | v1000 | r3 | immunefi | bounty
#   bm-xxxx = url 的 MD5 前 8 位 (稳定 ID, 跨 restart 不变)
#   v###    = 数字价值 (USD, 或 APY×100 for DeFi)
#   r#      = risk 分数 1-10
#   src     = 来源
#   type    = bounty / defi / hackathon / tvl / funding / listing / snapshot / depeg

# v26.3: HTML 格式助手 (Telegram parse_mode=HTML 所需)
def _esc(s):
    """HTML-escape 用户内容 (防止 < > & 破坏 Telegram HTML 解析)"""
    if s is None:
        return ""
    return html.escape(str(s), quote=False)

def _b(s):
    """Bold + HTML-escape. 用于关键数字 (APY/金额/价格变化等)"""
    return f"<b>{_esc(s)}</b>"

# 反查表: short_id -> 完整 bounty dict
# LRU 上限防内存爆炸
_BOUNTY_LOOKUP_MAX = 2000
_bounty_lookup = OrderedDict()
_lookup_lock = threading.Lock()

def short_id(url_or_key):
    """生成 8 字符稳定 ID (url 的 MD5 前缀)"""
    if not url_or_key:
        return "xxxxxxxx"
    h = hashlib.md5(str(url_or_key).encode("utf-8")).hexdigest()
    return h[:8]

def register_lookup(sid, data):
    """注册 short_id → 数据 (LRU)"""
    with _lookup_lock:
        if sid in _bounty_lookup:
            _bounty_lookup.move_to_end(sid)
        _bounty_lookup[sid] = data
        while len(_bounty_lookup) > _BOUNTY_LOOKUP_MAX:
            _bounty_lookup.popitem(last=False)

def get_lookup(sid):
    with _lookup_lock:
        return _bounty_lookup.get(sid)

def _sanitize_field(s, maxlen=20):
    """字段清洗: 去空格/管道符/HTML 危险字符, 限长 (v26.3)"""
    if s is None:
        return ""
    s = str(s).replace("|", "／").replace("\n", " ").strip()
    # v26.3: 顺便去除 <>& 防止尾行被误作 HTML
    s = s.replace("<", "").replace(">", "").replace("&", "")
    return s[:maxlen]

def make_tail(sid, v=0, r=0, src="", typ=""):
    """生成尾行标签. 调用前请先 register_lookup(sid, data)"""
    try:
        v_int = int(round(float(v or 0)))
    except (ValueError, TypeError):
        v_int = 0
    try:
        r_int = int(round(float(r or 0)))
    except (ValueError, TypeError):
        r_int = 0
    src_clean = _sanitize_field(src, 15).lower()
    typ_clean = _sanitize_field(typ, 12).lower()
    return f"📎 bm-{sid} | v{v_int} | r{r_int} | {src_clean} | {typ_clean}"

def tail_for_bounty(b):
    """为 bounty dict 生成尾行 + 注册反查"""
    # v26.1: 修复 sid 碰撞 (多个 CEX 共享同一 URL 如 binance.com/en/earn)
    # 用多字段组合做 hash input, 保证同平台不同产品的 sid 不撞
    key_parts = [
        str(b.get("u", "") or ""),
        str(b.get("symbol", "") or ""),
        str(b.get("org", "") or ""),
        str(b.get("project_name", "") or ""),
        str(b.get("chain", "") or ""),
        str(b.get("t", "") or "")[:50],  # title 作 fallback
    ]
    hash_input = "|".join(p for p in key_parts if p)
    sid = short_id(hash_input if hash_input else b.get("t", ""))
    v = b.get("v", 0) or 0
    # DeFi: 用 APY×100 作为 v 字段 (APY 12.5% → v=1250), 便于下游数字比较
    if b.get("apy", 0) and not b.get("v"):
        v = int(b["apy"] * 100)
    r = 0
    try:
        r = score_risk(b)  # score_risk 在下方定义, 此处延迟调用 OK
    except Exception:
        pass
    src = b.get("s", "") or b.get("org", "")
    # v26: 规范化 type 字段到稳定枚举 (下游可安全依赖)
    raw_type = (b.get("type", "") or "").lower().strip()
    if "hackathon" in raw_type or "hackathon" in (b.get("s", "") + " " + b.get("t", "")).lower():
        typ = "hackathon"
    elif b.get("apy", 0) > 0 or "yield" in raw_type or "earn" in raw_type or "savings" in raw_type:
        typ = "defi"
    elif "security" in raw_type or "audit" in raw_type:
        typ = "bounty"  # security bounty 也是 bounty
    elif raw_type in ("campaign", "quest", "boost"):
        typ = "campaign"
    elif raw_type:
        typ = raw_type.replace(" ", "_")[:12]
    else:
        typ = "bounty"
    register_lookup(sid, {**b, "_sid": sid, "_v": v, "_r": r, "_typ": typ})
    return make_tail(sid, v=v, r=r, src=src, typ=typ)

def tail_for_alert(alert_type, key, v=0, r=0, src="", extra=None):
    """为独立 alert (TVL/脱锚/资金费率等) 生成尾行"""
    sid = short_id(f"{alert_type}:{key}")
    data = {"_alert_type": alert_type, "_key": key, "_v": v, "_r": r, "_src": src}
    if extra:
        data.update(extra)
    register_lookup(sid, data)
    return make_tail(sid, v=v, r=r, src=src, typ=alert_type)

# ============================================================
# 🆕 v26: 哑巴失败检测 — fetcher 连续 24h 返回 0 条则告警
# ============================================================
_fetcher_drought_table = "fetcher_drought"  # 延迟在 init_db 后创建

def record_fetcher_result(conn, name, count):
    """记录 fetcher 单次结果. 若非零, 更新 last_nonzero_at"""
    try:
        with _db_lock:
            conn.execute("""CREATE TABLE IF NOT EXISTS fetcher_drought (
                name TEXT PRIMARY KEY,
                last_count INTEGER,
                last_nonzero_at TIMESTAMP,
                last_alerted_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
            now = datetime.now(timezone.utc).isoformat()
            if count > 0:
                conn.execute("""INSERT INTO fetcher_drought (name, last_count, last_nonzero_at, updated_at)
                    VALUES (?,?,?,?)
                    ON CONFLICT(name) DO UPDATE SET
                        last_count=excluded.last_count,
                        last_nonzero_at=excluded.last_nonzero_at,
                        updated_at=excluded.updated_at""",
                    (name, count, now, now))
            else:
                conn.execute("""INSERT INTO fetcher_drought (name, last_count, updated_at)
                    VALUES (?,?,?)
                    ON CONFLICT(name) DO UPDATE SET
                        last_count=excluded.last_count,
                        updated_at=excluded.updated_at""",
                    (name, count, now))
            conn.commit()
    except Exception as e:
        print(f"[Drought] record error: {e}")

def check_fetcher_droughts(conn, hours=24, cooldown_hours=12):
    """检查哪些 fetcher 连续 N 小时返回 0 条, 返回告警列表 (带冷却)"""
    alerts = []
    try:
        with _db_lock:
            rows = conn.execute("""SELECT name, last_count, last_nonzero_at, last_alerted_at
                FROM fetcher_drought""").fetchall()
        for name, last_count, last_nz, last_alert in rows:
            if last_count and last_count > 0:
                continue
            if not last_nz:
                continue
            try:
                nz_dt = datetime.fromisoformat(last_nz.replace("Z", "+00:00"))
            except Exception:
                continue
            drought_hours = (datetime.now(timezone.utc) - nz_dt).total_seconds() / 3600
            if drought_hours < hours:
                continue
            # 冷却检查
            if last_alert:
                try:
                    la_dt = datetime.fromisoformat(last_alert.replace("Z", "+00:00"))
                    if (datetime.now(timezone.utc) - la_dt).total_seconds() / 3600 < cooldown_hours:
                        continue
                except Exception:
                    pass
            alerts.append({"name": name, "hours": drought_hours})
            # 记录告警时间
            try:
                with _db_lock:
                    conn.execute("UPDATE fetcher_drought SET last_alerted_at=? WHERE name=?",
                        (datetime.now(timezone.utc).isoformat(), name))
                    conn.commit()
            except Exception:
                pass
    except Exception as e:
        print(f"[Drought] check error: {e}")
    return alerts

# ============================================================
# 🛡️ v23: 风险评分系统 (1-10, 1=最安全)
# ============================================================
BLUE_CHIP_PROTOCOLS = {
    "aave", "compound", "lido", "maker", "spark", "curve", "uniswap",
    "pendle", "morpho", "yearn", "convex", "balancer", "sushi",
    "pancakeswap", "gmx", "eigenlayer", "ethena", "sky",
}
TRUSTED_CEX = {
    "binance", "bybit", "okx", "gate", "gate.io", "bitget",
    "coinbase", "kraken", "kucoin", "htx",
}
# 已知审计过的协议 (可扩展)
AUDITED_PROTOCOLS = BLUE_CHIP_PROTOCOLS | {
    "aerodrome", "velodrome", "renzo", "kelp", "swell", "ether.fi",
    "hyperliquid", "jupiter", "kamino", "drift", "orca", "raydium",
    "stargate", "benqi", "trader-joe", "venus", "radiant",
}

def is_expired(b):
    """v25: 检查 bounty 是否已过期"""
    # title 含 "ended/Demo Day/Winners Announced/OpenClaw" 等结束关键词视为已结束
    title_lower = (b.get('t', '') or '').lower()
    if any(k in title_lower for k in ["submission ended", "winners announced", "已结束", "已截止"]):
        return True

    dl = b.get('deadline', '')
    # 无 deadline 的 hackathon 类型视为可疑 (保守过滤)
    if not dl or len(dl) < 10:
        if b.get('type') == 'Hackathon' or b.get('s') == 'DoraHacks':
            # 检查 start - 若 start 超过 60 天前, 视为过期
            start = b.get('start', '')
            if start and len(start) >= 10:
                try:
                    st_dt = datetime.strptime(start[:10].replace('/', '-'), '%Y-%m-%d')
                    if (datetime.now() - st_dt).days > 60:
                        return True
                except (ValueError, TypeError):
                    pass
        return False
    dl_str = dl[:10].replace('/', '-')
    try:
        dt = datetime.strptime(dl_str, '%Y-%m-%d')
        return dt.date() < datetime.now().date()
    except (ValueError, TypeError):
        return False

def score_risk(b):
    """风险评分 1-10 (1=最安全 10=最危险)"""
    score = 5
    apy = b.get('apy', 0)
    tvl = b.get('tvl', 0)
    org = (b.get('org', '') or '').lower().strip()

    # APY 风险: 越高越危险
    if apy > 200: score += 4
    elif apy > 100: score += 3
    elif apy > 50: score += 2
    elif apy > 20: score += 1
    elif apy < 5: score -= 1

    # TVL 安全: 越大越安全
    if tvl > 1e9: score -= 2
    elif tvl > 100e6: score -= 1
    elif tvl > 10e6: score -= 0
    elif tvl > 1e6: score += 1
    elif tvl > 0: score += 2  # TVL < 1M

    # 协议声誉
    if org in BLUE_CHIP_PROTOCOLS: score -= 2
    elif org in TRUSTED_CEX: score -= 1
    elif org in AUDITED_PROTOCOLS: score -= 1

    # 审计加分
    if b.get('audited'): score -= 1

    # 稳定币底层 vs 非稳定币
    symbol = (b.get('symbol', '') or '').upper()
    STABLES = {'USDC', 'USDT', 'DAI', 'USDE', 'FDUSD', 'TUSD', 'GHO', 'FRAX', 'LUSD', 'PYUSD', 'USDG', 'USD1', 'USDS', 'CRVUSD'}
    if symbol in STABLES: score -= 1  # 稳定币更安全

    return max(1, min(10, score))

def risk_label(score):
    """风险等级标签"""
    if score <= 2: return "🟢 低风险 Low Risk"
    if score <= 4: return "🟡 中低 Med-Low"
    if score <= 6: return "🟠 中等 Medium"
    if score <= 8: return "🔴 高风险 High Risk"
    return "⛔ 极高 Very High"

def risk_emoji(score):
    """简短风险 emoji"""
    if score <= 2: return "🟢"
    if score <= 4: return "🟡"
    if score <= 6: return "🟠"
    if score <= 8: return "🔴"
    return "⛔"

# ============================================================
# 📉 v23: APY 变动追踪
# ============================================================
def save_apy(conn, pool_key, apy, tvl=0):
    try:
        conn.execute("INSERT OR REPLACE INTO apy_history (pool_key, apy, tvl, recorded_at) VALUES (?,?,?,?)",
                      (pool_key, apy, tvl, datetime.now(timezone.utc).isoformat()))
        conn.commit()
    except Exception:
        pass

def get_prev_apy(conn, pool_key):
    """获取上次记录的 APY"""
    row = conn.execute("""
        SELECT apy, tvl FROM apy_history
        WHERE pool_key=? AND recorded_at < datetime('now', '-25 minutes')
        ORDER BY recorded_at DESC LIMIT 1
    """, (pool_key,)).fetchone()
    return row if row else None

def get_apy_7d_avg(conn, pool_key):
    """v25: 获取 7 天 APY 平均值 (用于历史对比)"""
    try:
        row = conn.execute("""
            SELECT AVG(apy), COUNT(*) FROM apy_history
            WHERE pool_key=? AND recorded_at > datetime('now', '-7 days')
        """, (pool_key,)).fetchone()
        if row and row[1] >= 3:  # 至少 3 个样本
            return row[0]
    except Exception:
        pass
    return None

def check_apy_changes(conn, all_b):
    """检测 APY 显著变化 (v25: 仅追踪 DeFiLlama, 其他源数据不稳定)"""
    alerts = []
    for b in all_b:
        # v25 fix: 只追踪 DeFiLlama (有稳定 pool_id), 其他源 APY 解析不稳
        if b.get('s') != 'DeFiLlama':
            continue
        if not is_defi(b):
            continue
        apy = b.get('apy', 0)
        tvl = b.get('tvl', 0)
        if apy <= 0:
            continue
        # 必须有 pool_id 作为稳定 key
        pool_id = b.get('pool_id', '')
        if not pool_id:
            continue
        # 必须有 org 和 symbol
        if not b.get('org') or not b.get('symbol'):
            continue

        # 过滤波动池
        if apy > 80:
            continue
        if tvl > 0 and tvl < 1e6:
            continue
        symbol = b.get('symbol', '') or ''
        if '-' in symbol or '/' in symbol:
            continue

        pool_key = f"defillama-{pool_id}"
        save_apy(conn, pool_key, apy, tvl)

        # v25: 存 7 天均值到 bounty dict 供格式化时显示
        avg_7d = get_apy_7d_avg(conn, pool_key)
        if avg_7d and avg_7d > 0:
            b['apy_7d_avg'] = avg_7d

        prev = get_prev_apy(conn, pool_key)
        if not prev:
            continue
        prev_apy, prev_tvl = prev
        if prev_apy <= 0 or prev_apy > 80:
            continue

        change_pct = ((apy - prev_apy) / prev_apy) * 100
        abs_change = abs(apy - prev_apy)

        # v24 fix: 同时要求 % 变化和绝对值变化
        # 上涨: >100% 且至少 +3pp
        # 下跌: >50% 且至少 -3pp
        if change_pct > 100 and abs_change >= 3:
            direction = "📈 上涨"
        elif change_pct < -50 and abs_change >= 3:
            direction = "📉 下跌"
        else:
            continue

        # 6 小时冷却
        cooldown_key = f"apy-{pool_key}"
        already = conn.execute(
            "SELECT 1 FROM deadline_alerts WHERE url=? AND alerted_at > datetime('now', '-6 hours')",
            (cooldown_key,)
        ).fetchone()
        if already:
            continue
        conn.execute("INSERT OR IGNORE INTO deadline_alerts (url, alert_type) VALUES (?,?)",
                     (cooldown_key, "apy_change"))
        conn.commit()

        alerts.append({
            "title": b['t'], "org": b.get('org', ''),
            "old_apy": prev_apy, "new_apy": apy,
            "change_pct": change_pct, "direction": direction,
            "url": b.get('u', ''), "symbol": symbol,
            "tvl": tvl,
        })
    return alerts

def send_apy_alerts(alerts):
    """v26.4: HTML 安全 + APY/TVL 加粗"""
    if not alerts:
        return
    alerts.sort(key=lambda x: abs(x['change_pct']), reverse=True)
    for a in alerts[:3]:
        old_str = f"{a['old_apy']:.2f}%"
        new_str = f"{a['new_apy']:.2f}%"
        ch_str = f"{a['change_pct']:+.0f}%"
        msg = f"{a['direction']} APY 大幅变动!\n\n"
        msg += f"📌 {_esc(a['title'])}\n"
        msg += f"📊 {old_str} → {_b(new_str)} ({_b(ch_str)})\n"
        if a.get('tvl', 0) > 0:
            tvl_str = f"${a['tvl']/1e6:.1f}M"
            msg += f"💰 TVL: {_b(tvl_str)}\n"
        msg += f"🔗 {_esc(a['url'])}"
        try:
            tail = tail_for_alert("apy_change", a.get('url', a.get('title', '')),
                v=int(a.get('new_apy', 0) * 100),
                r=min(10, max(1, int(a.get('new_apy', 0) / 10))),
                src=a.get('title', '').split()[0].lower() if a.get('title') else 'defi',
                extra={"old_apy": a.get('old_apy'), "new_apy": a.get('new_apy'),
                       "change_pct": a.get('change_pct'), "tvl": a.get('tvl')})
            msg += f"\n{tail}"
        except Exception as e:
            print(f"[Tail] apy_change error: {e}")
        send_tg(msg)
        time.sleep(1)

# ============================================================
# ⏰ v23: 截止倒计时提醒
# ============================================================
def check_deadline_countdowns(conn, all_b):
    """检测即将到期的活动"""
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # v25: UTC naive
    for b in all_b:
        deadline_str = b.get('deadline', '')
        if not deadline_str or len(deadline_str) < 10:
            continue
        try:
            deadline_dt = datetime.strptime(deadline_str[:10], '%Y-%m-%d')
        except ValueError:
            continue
        hours_left = (deadline_dt - now).total_seconds() / 3600
        url = b.get('u', '')
        if hours_left <= 0 or hours_left > 48:
            continue
        # 24h 提醒
        if hours_left <= 24:
            alert_key = f"{url}-24h"
            already = conn.execute("SELECT 1 FROM deadline_alerts WHERE url=? AND alert_type=?",
                                   (alert_key, "24h")).fetchone()
            if not already:
                conn.execute("INSERT OR IGNORE INTO deadline_alerts (url, alert_type) VALUES (?,?)",
                             (alert_key, "24h"))
                conn.commit()
                apy = b.get('apy', 0)
                val = b.get('v', 0)
                msg = f"⏰ 即将截止! Last {int(hours_left)}h!\n\n"
                msg += f"📌 {b['t']}\n"
                if apy > 0:
                    msg += f"📈 APY: {apy:.2f}%\n"
                elif val > 0:
                    msg += f"💰 ${val:,}\n"
                msg += f"📅 截止: {deadline_str}\n"
                msg += f"🔗 {b['u']}"
                send_tg(msg)
                time.sleep(1)

# ============================================================
# HTTP 请求 (带重试 + 退避)
# ============================================================
def fetch_with_retry(url, method="get", max_retries=3, timeout=30, **kwargs):
    """带指数退避的 HTTP 请求"""
    for attempt in range(max_retries):
        resp = None  # v25: 防御性初始化
        try:
            if method == "post":
                resp = requests.post(url, timeout=timeout, **kwargs)
            else:
                resp = requests.get(url, timeout=timeout, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError:
            status = resp.status_code if resp is not None else 0
            if status == 429:
                wait = min(60, 2 ** attempt * 5)
                print(f"[Retry] 429 限流, 等待 {wait}s: {url[:60]}")
                time.sleep(wait)
            elif status >= 500:
                wait = 2 ** attempt * 2
                print(f"[Retry] {status} 服务器错误, 等待 {wait}s: {url[:60]}")
                time.sleep(wait)
            else:
                print(f"[Retry] {status} 客户端错误, 跳过: {url[:60]}")
                return None
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            wait = 2 ** attempt * 2
            print(f"[Retry] 连接/超时错误 (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(wait)
    return None

def firecrawl_scrape(url):
    """v25+: Firecrawl fallback — 只在普通抓取内容不够时调用 (省 credit)"""
    if not FIRECRAWL_API_KEY:
        return None
    try:
        resp = requests.post(
            "https://api.firecrawl.dev/v1/scrape",
            headers={
                "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "url": url,
                "formats": ["markdown"],
                "onlyMainContent": True,
                "waitFor": 2000,
            },
            timeout=25,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("success") and data.get("data", {}).get("markdown"):
            content = data["data"]["markdown"]
            print(f"[Firecrawl] ✅ {url[:50]} → {len(content)} 字符")
            return content
    except Exception:
        pass
    return None

def jina_reader(url):
    """v25+: Jina Reader — 免费 markdown 抓取 (无需 key)"""
    try:
        resp = requests.get(
            f"https://r.jina.ai/{url}",
            headers={"Accept": "text/markdown", "User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        if resp.status_code == 200 and len(resp.text) > 200:
            print(f"[Jina] ✅ {url[:50]} → {len(resp.text)} 字符")
            return resp.text
    except Exception:
        pass
    return None

def smart_scrape(url, min_chars=500):
    """三层 fallback: requests → Jina Reader → Firecrawl"""
    # 1. 直接 requests
    text = ""
    try:
        resp = fetch_with_retry(url, timeout=10)
        if resp:
            text = resp.text or ""
    except Exception:
        pass
    if len(text) >= min_chars:
        return text
    # 2. Jina Reader (免费)
    jina = jina_reader(url)
    if jina and len(jina) >= min_chars:
        return jina
    # 3. Firecrawl (付费兜底)
    fc = firecrawl_scrape(url)
    if fc:
        return fc
    return text  # 返回最好的结果

def fetch_page_content(url, min_chars=500, **kwargs):
    """抓取页面内容: 先 requests, 内容 < min_chars 则 fallback Firecrawl"""
    text = ""
    try:
        resp = fetch_with_retry(url, timeout=15, **kwargs)
        if resp:
            text = resp.text or ""
    except Exception:
        pass
    if len(text) < min_chars:
        fc = firecrawl_scrape(url)
        if fc:
            return fc
    return text

# ============================================================
# Telegram 推送
# ============================================================
def send_tg(msg):
    """v30.8: 返回最后一个成功 chunk 的 message_id (无 TG/失败返回 None)"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"[TG] {msg[:200]}")
        return None
    last_msg_id = None
    try:
        chunks = []
        remaining = msg
        while len(remaining) > 4000:
            cut = remaining.rfind('\n\n', 0, 4000)
            if cut == -1:
                cut = remaining.rfind('\n', 0, 4000)
            if cut == -1:
                cut = 4000
            chunks.append(remaining[:cut])
            remaining = remaining[cut:].lstrip()
        if remaining:
            chunks.append(remaining)
        for chunk in chunks:
            r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }, timeout=10)
            if r.status_code == 400 and "parse" in r.text.lower():
                print(f"[TG] HTML parse 失败, 降级为纯文本: {r.text[:200]}")
                import re as _re
                plain = _re.sub(r'<[^>]+>', '', chunk)
                plain = plain.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
                r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": plain,
                    "disable_web_page_preview": True
                }, timeout=10)
            # v30.8: 提取 message_id (取每条返回的最新 id)
            if r.status_code == 200:
                try:
                    rj = r.json()
                    if rj.get("ok"):
                        last_msg_id = rj.get("result", {}).get("message_id") or last_msg_id
                except Exception:
                    pass
            time.sleep(0.5)
    except Exception as e:
        print(f"TG发送失败: {e}")
    return last_msg_id

def send_tg_photo(image_bytes, caption=""):
    """发送图片到 TG. v30.7: 返回 message_id (失败/无 TG 返回 None)"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"[TG Photo] {caption[:100]}")
        return None
    msg_id = None
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": caption[:1024],
                "parse_mode": "HTML",
            },
            files={"photo": ("chart.png", image_bytes, "image/png")},
            timeout=30
        )
        # 降级重试: HTML 解析失败 → 纯文本
        if r.status_code == 400 and "parse" in r.text.lower():
            print(f"[TG Photo] HTML 失败降级纯文本: {r.text[:200]}")
            import re as _re
            plain = _re.sub(r'<[^>]+>', '', caption)
            plain = plain.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
            r = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
                data={"chat_id": TELEGRAM_CHAT_ID, "caption": plain[:1024]},
                files={"photo": ("chart.png", image_bytes, "image/png")},
                timeout=30
            )
        # v30.7: 提取 message_id
        if r.status_code == 200:
            try:
                rj = r.json()
                if rj.get("ok"):
                    msg_id = rj.get("result", {}).get("message_id")
            except Exception:
                pass
    except Exception as e:
        print(f"TG图片发送失败: {e}")
    return msg_id


def send_tg_photo_url(photo_url, caption="", chat_id=None):
    """
    🆕 v28.4: 通过 URL 发图 (TG 自己去下载). 失败时降级为纯文本 caption.
    chat_id=None 用默认频道, 否则指定 chat (用于订阅者私推)
    """
    target_chat = chat_id if chat_id is not None else TELEGRAM_CHAT_ID
    if not TELEGRAM_TOKEN or not target_chat:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
            json={
                "chat_id": target_chat,
                "photo": photo_url,
                "caption": caption[:1024],
                "parse_mode": "HTML",
            },
            timeout=15
        )
        if r.status_code == 200:
            return True
        # HTML 解析失败 → 降级纯文本 caption
        if r.status_code == 400 and "parse" in r.text.lower():
            import re as _re
            plain = _re.sub(r'<[^>]+>', '', caption)
            plain = plain.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
            r2 = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
                json={"chat_id": target_chat, "photo": photo_url, "caption": plain[:1024]},
                timeout=15
            )
            return r2.status_code == 200
        # 图 URL 无效 / TG 拉不到 → 返回 False 让调用方降级
        print(f"[TG PhotoURL] 失败 {r.status_code}: {r.text[:200]}")
        return False
    except Exception as e:
        print(f"[TG PhotoURL] 异常: {e}")
        return False

# ============================================================
# 🤖 v24: TG Bot 命令系统
# ============================================================
LATEST_DATA = {"all_b": [], "last_scan": None, "scan_count": 0}
_data_lock = threading.Lock()  # v25: 保护 LATEST_DATA 并发读写

def _get_latest():
    """v25: 原子读取 LATEST_DATA 快照 (返回副本避免迭代竞态)"""
    with _data_lock:
        return list(LATEST_DATA["all_b"]), LATEST_DATA.get("last_scan"), LATEST_DATA.get("scan_count", 0)

def send_tg_reply(chat_id, msg):
    """回复指定 chat (用于命令响应). v28.0.1: HTML 模式 + 失败降级纯文本"""
    if not TELEGRAM_TOKEN:
        return
    try:
        # v25: 智能切分
        chunks = []
        remaining = msg
        while len(remaining) > 4000:
            cut = remaining.rfind('\n\n', 0, 4000)
            if cut == -1:
                cut = remaining.rfind('\n', 0, 4000)
            if cut == -1:
                cut = 4000
            chunks.append(remaining[:cut])
            remaining = remaining[cut:].lstrip()
        if remaining:
            chunks.append(remaining)
        for chunk in chunks:
            # v28.0.1: 默认 HTML 模式, 失败降级到纯文本
            r = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }, timeout=10)
            if r.status_code == 400 and "parse" in r.text.lower():
                # HTML 解析失败 — 降级纯文本
                import re as _re
                plain = _re.sub(r'<[^>]+>', '', chunk)
                plain = plain.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": plain,
                    "disable_web_page_preview": True
                }, timeout=10)
            time.sleep(0.3)
    except Exception as e:
        print(f"[Bot] 回复失败: {e}")

def cmd_help(chat_id, args):
    msg = """🤖 币世赏金台 Bot 命令

📋 数据查询:
/top [n] - 当前 Top N 高价值 Bounty (默认5)
/defi [n] - DeFi/CEX 高收益 Top N
/hackathon - 黑客松 Top 5
/airdrop - 7天内新协议追踪
/stats - 当前数据统计

🐋 鲸鱼 (v28):
/whale - 所有鲸鱼总览
/whale &lt;id&gt; - 鲸鱼详情 (例: /whale machi)
/subscribe &lt;id&gt; - 订阅鲸鱼 (有动作时私聊推送你)
/unsubscribe &lt;id&gt; - 取消订阅 (或 /unsubscribe all)
/mysubs - 我的订阅列表

🔍 搜索 / 反查:
/search &lt;关键词&gt; - 搜索 bounty
/risk &lt;token&gt; - 查询 token 相关收益+风险
/v &lt;short_id&gt; - 反查尾行标签 (例: /v a7f3)
/map - 🆕 4 区快照 (入场窗口/早发现/确认回踩/风险区)

⚙️ 其他:
/help - 显示此帮助
/about - 关于本 bot
/growth [days] - 📊 频道增长诊断 (admin only, 默认 7 天)
/diagnose [days] [channel] - 🔬 输/赢信号 setup 诊断 (admin only, 默认 30 天)"""
    send_tg_reply(chat_id, msg)

def cmd_about(chat_id, args):
    msg = """🤖 Bounty Monitor v24

监控 11+ 数据源:
• Immunefi / Superteam / DoraHacks
• HackQuest / Devpost / GitHub
• DeFiLlama / OKX Boost
• CEX/DEX 理财活动
• 200+ 协议 TVL 异动
• Top 10 稳定币流向
• 新协议空投追踪

每 30 分钟扫描，智能去重和风险评分。"""
    send_tg_reply(chat_id, msg)

def cmd_top(chat_id, args):
    all_b, _, _ = _get_latest()
    if not all_b:
        send_tg_reply(chat_id, "⏳ 数据未就绪，请等待首次扫描完成")
        return
    n = 5
    if args and args[0].isdigit():
        n = min(int(args[0]), 20)
    top = sorted([b for b in all_b if b.get('v', 0) >= MIN_VALUE],
                 key=lambda x: x.get('v', 0), reverse=True)[:n]
    if not top:
        send_tg_reply(chat_id, "暂无高价值 bounty")
        return
    msg = f"🏆 当前 Top {n} 高价值 Bounty:\n\n"
    for b in top:
        msg += f"💰 ${b['v']:,} | {b['s']}\n📋 {b['t'][:60]}\n🔗 {b['u']}\n\n"
    send_tg_reply(chat_id, msg.strip())

def cmd_defi(chat_id, args):
    all_b, _, _ = _get_latest()
    if not all_b:
        send_tg_reply(chat_id, "⏳ 数据未就绪")
        return
    n = 5
    if args and args[0].isdigit():
        n = min(int(args[0]), 15)
    defi = sorted([b for b in all_b if is_defi(b) and b.get('apy', 0) > 0],
                  key=lambda x: x['apy'], reverse=True)[:n]
    if not defi:
        send_tg_reply(chat_id, "暂无 DeFi 数据")
        return
    msg = f"💹 当前 Top {n} DeFi/CEX 收益:\n\n"
    for b in defi:
        msg += fmt_defi(b) + "\n\n"
    send_tg_reply(chat_id, msg.strip())

def cmd_hackathon(chat_id, args):
    all_b, _, _ = _get_latest()
    if not all_b:
        send_tg_reply(chat_id, "⏳ 数据未就绪")
        return
    hacks = sorted([b for b in all_b if b.get('type') == 'Hackathon' and b.get('v', 0) > 0],
                   key=lambda x: x['v'], reverse=True)[:5]
    if not hacks:
        send_tg_reply(chat_id, "暂无黑客松数据")
        return
    msg = "🏆 当前 Top 5 黑客松:\n\n"
    for b in hacks:
        msg += f"💰 ${b['v']:,} | {b['s']}\n📋 {b['t'][:60]}\n"
        if b.get('deadline'):
            msg += f"📅 {b['deadline']}\n"
        msg += f"🔗 {b['u']}\n\n"
    send_tg_reply(chat_id, msg.strip())

def cmd_airdrop(chat_id, args):
    send_tg_reply(chat_id, "⏳ 正在查询新协议...")
    protos = fetch_new_protocols()
    if not protos:
        send_tg_reply(chat_id, "暂无 7 天内新协议")
        return
    msg = "🪂 7 天内新协议:\n\n"
    for p in protos[:8]:
        token_tag = "🪙 无代币" if not p['has_token'] else "✅ 已发币"
        msg += f"📌 {p['name']} | {token_tag}\n"
        msg += f"💰 ${p['tvl']/1e6:.1f}M | 📂 {p['category']}\n"
        msg += f"📅 {p['listed_dt']}\n🔗 {p['url']}\n\n"
    send_tg_reply(chat_id, msg.strip())

def cmd_stats(chat_id, args):
    all_b, last, scan_count = _get_latest()
    if not all_b:
        send_tg_reply(chat_id, "⏳ 数据未就绪")
        return
    total = len(all_b)
    high_val = sum(1 for b in all_b if b.get('v', 0) >= MIN_VALUE)
    defi_count = sum(1 for b in all_b if is_defi(b))
    hacks = sum(1 for b in all_b if b.get('type') == 'Hackathon')
    chains = len(set(b.get('chain', '') for b in all_b if b.get('chain')))
    msg = f"""📊 当前数据统计

📋 总活动: {total}
💰 高价值 (≥${MIN_VALUE}): {high_val}
💹 DeFi/CEX 收益: {defi_count}
🏆 黑客松: {hacks}
⛓️ 涵盖链: {chains}
🕐 最后扫描: {last or '未知'}
🔢 累计扫描: {scan_count}"""
    send_tg_reply(chat_id, msg)

def _winrate_fetch_one(symbol, sig_price, start_ms, end_ms, interval, limit):
    """单次 K 线反查, 一次性返回 (high_pct, low_pct, close_pct).
    返回 None 如果失败. 用于并发执行."""
    try:
        r = requests.get(
            f"{BINANCE_FAPI}/fapi/v1/klines",
            params={
                "symbol": f"{symbol}USDT",
                "interval": interval,
                "startTime": start_ms,
                "endTime": end_ms,
                "limit": limit,
            },
            timeout=8
        )
        if r.status_code != 200:
            return None
        kl = r.json()
        if not kl:
            return None
        high = max(float(k[2]) for k in kl)
        low = min(float(k[3]) for k in kl)
        close = float(kl[-1][4])  # 最后一根 K 线收盘
        if sig_price <= 0:
            return None
        high_pct = (high - sig_price) / sig_price * 100
        low_pct = (low - sig_price) / sig_price * 100
        close_pct = (close - sig_price) / sig_price * 100
        return (high_pct, low_pct, close_pct)
    except Exception:
        return None


def cmd_winrate(chat_id, args):
    """🆕 v30.12: 赏金哨信号胜率统计 — 完整版 (仅 admin)

    新增 vs v30.12 初版:
      • 亏损样本 (≤-3% / ≤-5% / ≤-10%)
      • Close-based 胜率 (实战版, 信号 +1h close 价 vs 信号价)
      • 鲸鱼共振诊断 (含 0/1 拆分, 维度有效性)
      • 对照组 baseline (评分 30-49 未推送 vs 推送的, 证明 alpha)

    用法:
      /winrate          → 默认 7 天, 全通道
      /winrate 14       → 最近 14 天
      /winrate 7 direct → 仅 BN OI 直推
      /winrate 7 score  → 仅综合分通道
      /winrate 7 short  → 🆕 v30.14.19: SHORT dogfood 胜率 (做空视角)
    """
    # 🔐 admin 校验
    if not TG_ADMIN_CHAT_ID:
        send_tg_reply(chat_id,
            f"🔐 /winrate 是 admin 私人命令, 当前未配置.\n\n"
            f"你的 chat_id: <code>{chat_id}</code>\n\n"
            f"去 Railway 加环境变量:\n"
            f"<code>TG_ADMIN_CHAT_ID={chat_id}</code>\n\n"
            f"重部署后只有你能用 /winrate.")
        return
    if str(chat_id) != str(TG_ADMIN_CHAT_ID):
        return

    days = 7
    channel_filter = None
    v2_only = False  # 🆕 v30.14.4: shadow v2 子集对比
    short_mode = False  # 🆕 v30.14.19: SHORT dogfood 胜率查询
    for a in args:
        if a.isdigit():
            days = max(1, min(30, int(a)))
        elif a.lower() in ("direct", "score"):
            channel_filter = a.lower()
        elif a.lower() == "v2":
            v2_only = True
        elif a.lower() == "short":
            short_mode = True

    send_tg_reply(chat_id,
        f"⏳ 计算中... 拉最近 {days} 天信号 + 对照组 + 历史 K 线\n"
        f"(并发 10 worker, 约 30-60 秒)" + (
            "\n🔬 v2 shadow 子集 (方案 C AND 条件)" if v2_only else ""
        ))

    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        # 拉推送信号
        push_where = "push_channel IN ('direct', 'score') AND datetime(recorded_at) >= datetime('now', '-{} days')".format(days)
        if channel_filter:
            push_where = "push_channel='{}' AND datetime(recorded_at) >= datetime('now', '-{} days')".format(channel_filter, days)

        # 🆕 v30.14.19: SHORT 模式 — 查 SHORT dogfood 触发的样本
        # SHORT dogfood 条件 (line 9510-9514): score≥60 + OI≥30% + 24h>10%, push_channel='watch'
        # 这些信号没进频道, 只私聊 admin
        if short_mode:
            push_where = ("push_channel='watch' "
                          "AND score >= 60 "
                          "AND change_24h > 10 "
                          "AND datetime(recorded_at) >= datetime('now', '-{} days')").format(days)

        # 🆕 v2 子集: 包含 watch 通道但 v2_pass=1 的 (shadow 模式下重点)
        if v2_only:
            push_where += " AND score_components LIKE '%\"v2_pass\": 1%'"

        pushed_sigs = conn.execute(
            f"SELECT symbol, score, push_channel, price, recorded_at, whale_resonance "
            f"FROM sentinel_signals WHERE {push_where} "
            f"ORDER BY recorded_at DESC LIMIT 100"
        ).fetchall()

        # 🆕 对照组: 评分 30-49 未推送的 (push_channel='watch'), random 抽样
        # 🆕 v30.14.19: SHORT 模式不取对照组 (因为 SHORT 本身就是 watch + score≥60, 没合适基准)
        if short_mode:
            baseline_sigs = []
        else:
            baseline_sigs = conn.execute(
                "SELECT symbol, score, push_channel, price, recorded_at, whale_resonance "
                "FROM sentinel_signals "
                "WHERE push_channel='watch' AND datetime(recorded_at) >= datetime('now', ?) "
                "ORDER BY RANDOM() LIMIT 50",
                (f"-{days} days",)
            ).fetchall()
        conn.close()

        if not pushed_sigs:
            tip = " (SHORT dogfood)" if short_mode else f" (频道={channel_filter or '全部'})"
            send_tg_reply(chat_id,
                f"📭 最近 {days} 天没有推送信号\n{tip}\n\n"
                f"<i>SHORT dogfood 触发条件: score≥60 + OI 1h≥30% + 24h>10%</i>" if short_mode else
                f"📭 最近 {days} 天没有推送信号\n(频道={channel_filter or '全部'})")
            return

        windows = [("1h", 3600, 60, "1m"), ("4h", 14400, 48, "5m"), ("24h", 86400, 96, "15m")]
        # results[label][group] = [(symbol, score, high_pct, low_pct, close_pct, whale_res), ...]
        results = {w[0]: {"pushed": [], "baseline": []} for w in windows}

        # 准备所有任务
        def _build_tasks(sigs, group):
            tasks = []
            for sig in sigs:
                symbol, score, channel, sig_price, recorded_at, whale_res = sig
                if not sig_price or sig_price <= 0:
                    continue
                try:
                    t0 = datetime.strptime(recorded_at, "%Y-%m-%d %H:%M:%S")
                    start_ms = int(t0.replace(tzinfo=timezone.utc).timestamp() * 1000)
                except Exception:
                    continue
                now_ms = int(time.time() * 1000)
                for label, secs, limit, interval in windows:
                    end_ms = start_ms + secs * 1000
                    if end_ms > now_ms:
                        continue
                    tasks.append((symbol, score, sig_price, start_ms, end_ms,
                                  interval, limit, label, group, whale_res or 0))
            return tasks

        all_tasks = _build_tasks(pushed_sigs, "pushed") + _build_tasks(baseline_sigs, "baseline")

        # 并发 10 worker
        def _exec_task(t):
            symbol, score, sig_price, start_ms, end_ms, interval, limit, label, group, whale_res = t
            stats = _winrate_fetch_one(symbol, sig_price, start_ms, end_ms, interval, limit)
            if stats is None:
                return None
            high_pct, low_pct, close_pct = stats
            return (label, group, (symbol, score, high_pct, low_pct, close_pct, whale_res))

        with ThreadPoolExecutor(max_workers=10) as ex:
            futures = [ex.submit(_exec_task, t) for t in all_tasks]
            for fut in as_completed(futures):
                try:
                    res = fut.result(timeout=15)
                except Exception:
                    res = None
                if res:
                    label, group, data = res
                    results[label][group].append(data)

        # ===== 构造输出 =====
        msg_lines = [
            f"📊 <b>{'赏金哨 SHORT 胜率' if short_mode else '赏金哨胜率'}</b> · 最近 {days} 天",
            f"模式: {'🔻 SHORT dogfood (做空)' if short_mode else ('频道: ' + (channel_filter or '全部 (direct + score)'))}",
            f"推送 n={len(pushed_sigs)}" + ("" if short_mode else f" · 对照 n={len(baseline_sigs)}"),
            f"📍 数据源: 赏金哨合约信号",
            "",
        ]
        if short_mode:
            msg_lines.insert(2, "<i>触发: score≥60 + OI 1h≥30% + 24h>10% (FOMO 顶部空头)</i>")
            msg_lines.insert(3, "<i>胜利定义: close < entry (做空赚)</i>")
            msg_lines.append("")

        # === 1) Peak-based 胜率 (双向: 涨幅 + 跌幅) ===
        msg_lines.append("━━━━━━━━━━━━━━")
        msg_lines.append("🎯 <b>PEAK-BASED</b> (上帝视角)")
        msg_lines.append("━━━━━━━━━━━━━━")
        for label, _, _, _ in windows:
            samples = results[label]["pushed"]
            n = len(samples)
            if n == 0:
                msg_lines.append(f"<b>{label}</b>: 无完整样本")
                continue
            avg_high = sum(s[2] for s in samples) / n
            avg_low = sum(s[3] for s in samples) / n
            line = f"<b>{label}</b> n={n} · 均 peak {avg_high:+.2f}% / 谷 {avg_low:+.2f}%"
            # 涨幅 hits
            hits_up = []
            for thr in [3, 5, 10]:
                wins = sum(1 for s in samples if s[2] >= thr)
                hits_up.append(f"+{thr}%:{wins/n*100:.0f}%")
            line += f"\n  📈 " + " · ".join(hits_up)
            # 跌幅 hits (反向: low_pct ≤ -X)
            hits_down = []
            for thr in [3, 5, 10]:
                losses = sum(1 for s in samples if s[3] <= -thr)
                hits_down.append(f"-{thr}%:{losses/n*100:.0f}%")
            line += f"\n  📉 " + " · ".join(hits_down)
            msg_lines.append(line)
        msg_lines.append("")

        # === 2) Close-based 胜率 (实战版) ===
        msg_lines.append("━━━━━━━━━━━━━━")
        msg_lines.append("💼 <b>CLOSE-BASED</b> (实战版)")
        msg_lines.append("━━━━━━━━━━━━━━")
        if short_mode:
            msg_lines.append("(做空视角: close < entry 算胜)")
        else:
            msg_lines.append("(信号价 → 窗口末 K 线收盘价)")
        for label, _, _, _ in windows:
            samples = results[label]["pushed"]
            n = len(samples)
            if n == 0:
                continue
            if short_mode:
                # 🆕 v30.14.19: SHORT 视角, close < 0% 算胜
                wins = sum(1 for s in samples if s[4] < 0)
                avg_close = sum(s[4] for s in samples) / n
                line = f"<b>{label}</b> n={n}"
                line += f"\n  做空胜率 (close&lt;entry): <b>{wins/n*100:.0f}%</b> ({wins}/{n})"
                line += f"\n  均值收益 (做空 = -close): <b>{-avg_close:+.2f}%</b>"
                # SHORT 止盈: close ≤ -3% / -5%
                hit3 = sum(1 for s in samples if s[4] <= -3)
                hit5 = sum(1 for s in samples if s[4] <= -5)
                line += f"\n  close ≤-3%: {hit3/n*100:.0f}% · ≤-5%: {hit5/n*100:.0f}%"
                # SHORT 止损: close ≥ +3% (反向走势)
                stop3 = sum(1 for s in samples if s[4] >= 3)
                line += f"\n  🚨 反向 ≥+3% (止损位): {stop3/n*100:.0f}%"
            else:
                wins = sum(1 for s in samples if s[4] > 0)
                avg_close = sum(s[4] for s in samples) / n
                line = f"<b>{label}</b> n={n}"
                line += f"\n  胜率 (close&gt;entry): <b>{wins/n*100:.0f}%</b> ({wins}/{n})"
                line += f"\n  均值收益: <b>{avg_close:+.2f}%</b>"
                # 止盈 hit (close ≥ +3% / +5%)
                hit3 = sum(1 for s in samples if s[4] >= 3)
                hit5 = sum(1 for s in samples if s[4] >= 5)
                line += f"\n  close ≥+3%: {hit3/n*100:.0f}% · ≥+5%: {hit5/n*100:.0f}%"
            msg_lines.append(line)
        msg_lines.append("")

        # === 3) 共所一致性诊断 (v30.14.15: 鲸鱼维度早已 0 分, 真正的 15 分权重是 cross/共所) ===
        # 🆕 v30.14.19: SHORT 模式跳过 (对做空判断没意义)
        if not short_mode:
            msg_lines.append("━━━━━━━━━━━━━━")
            msg_lines.append("⚖️ <b>共所一致性 (cross) 诊断</b>")
            msg_lines.append("━━━━━━━━━━━━━━")
            msg_lines.append("<i>cross = BN + HL 两所 OI 都同向异动, 给 0/5/10/15 分</i>")
            # 用 1h 样本看. 注意: s[5] 原本读的 has_whale 字段, 现在解读为 has_cross
            # (实际查询里 has_whale 永远 0 因为鲸鱼维度已删, 所以这里 n_with 也总是 0)
            # TODO: 若想真显示 cross 命中率, 需 query 改读 components 里 cross>0
            samples_1h = results["1h"]["pushed"]
            with_whale = [s for s in samples_1h if s[5] == 1]
            no_whale = [s for s in samples_1h if s[5] == 0]
            n_with = len(with_whale)
            n_no = len(no_whale)
            msg_lines.append(f"含'鲸鱼共振'标记: {n_with} / {n_with+n_no}")
            if n_with == 0:
                msg_lines.append("ℹ️ <b>鲸鱼维度早在 v30+ 已废</b> (components[whale]=0)")
                msg_lines.append("→ 真正 15 分权重是 cross (共所一致性), 不是鲸鱼")
                msg_lines.append("→ 此处 0 触发属预期, 不代表评分系统有问题")
            elif n_no == 0:
                msg_lines.append("⚠️ 全部信号都标记含鲸鱼 (异常)")
            else:
                w_close = sum(1 for s in with_whale if s[4] > 0) / n_with * 100
                n_close = sum(1 for s in no_whale if s[4] > 0) / n_no * 100
                w_avg = sum(s[4] for s in with_whale) / n_with
                n_avg = sum(s[4] for s in no_whale) / n_no
                msg_lines.append(f"🐋 含标记 1h close 胜率: <b>{w_close:.0f}%</b> · 均 {w_avg:+.2f}%")
                msg_lines.append(f"⚪ 无标记 1h close 胜率: <b>{n_close:.0f}%</b> · 均 {n_avg:+.2f}%")
            msg_lines.append("")

        # === 4) 对照组 baseline (SHORT 模式无对照组, 跳过) ===
        if not short_mode:
            msg_lines.append("━━━━━━━━━━━━━━")
            msg_lines.append("🆚 <b>对照组 (评分 30-49 未推)</b>")
            msg_lines.append("━━━━━━━━━━━━━━")
        for label, _, _, _ in windows:
            p_samples = results[label]["pushed"]
            b_samples = results[label]["baseline"]
            if not p_samples or not b_samples:
                continue
            p_n = len(p_samples)
            b_n = len(b_samples)
            # 用 close-based 胜率比较
            p_win = sum(1 for s in p_samples if s[4] > 0) / p_n * 100
            b_win = sum(1 for s in b_samples if s[4] > 0) / b_n * 100
            p_avg = sum(s[4] for s in p_samples) / p_n
            b_avg = sum(s[4] for s in b_samples) / b_n
            line = f"<b>{label}</b> close 胜率"
            line += f"\n  推送 (n={p_n}): <b>{p_win:.0f}%</b> · 均 {p_avg:+.2f}%"
            line += f"\n  对照 (n={b_n}): {b_win:.0f}% · 均 {b_avg:+.2f}%"
            diff = p_win - b_win
            if diff >= 10:
                line += f"\n  ✅ Alpha: <b>+{diff:.0f}%</b>"
            elif diff >= 0:
                line += f"\n  ➖ Alpha 边际: +{diff:.0f}%"
            else:
                line += f"\n  ❌ 推送比未推还差 ({diff:.0f}%)"
            msg_lines.append(line)
        msg_lines.append("")

        # === 5) Top / Bottom ===
        if results["1h"]["pushed"]:
            if short_mode:
                # 🆕 v30.14.19: SHORT 反转 — 谷越深越好 (做空赚), 峰越高越坏 (做空亏)
                best = sorted(results["1h"]["pushed"], key=lambda x: x[3])[:3]  # 谷最深的 = SHORT 最佳
                worst = sorted(results["1h"]["pushed"], key=lambda x: -x[2])[:3]  # 峰最高的 = SHORT 最坏
                msg_lines.append("🏆 <b>SHORT 最佳 Top 3</b> (1h 谷):")
                for sym, sc, hp, lp, cp, wr in best:
                    msg_lines.append(f"  ${sym} ({sc}/100) → 谷 {lp:+.2f}% / close {cp:+.2f}%")
                msg_lines.append("")
                msg_lines.append("💀 <b>SHORT 最差 Bottom 3</b> (1h 峰, 反向上涨):")
                for sym, sc, hp, lp, cp, wr in worst:
                    msg_lines.append(f"  ${sym} ({sc}/100) → 峰 {hp:+.2f}% / close {cp:+.2f}%")
            else:
                best = sorted(results["1h"]["pushed"], key=lambda x: -x[2])[:3]
                worst = sorted(results["1h"]["pushed"], key=lambda x: x[3])[:3]
                msg_lines.append("🏆 <b>1h 最佳 Top 3</b> (peak):")
                for sym, sc, hp, lp, cp, wr in best:
                    wt = " 🐋" if wr == 1 else ""
                    msg_lines.append(f"  ${sym} ({sc}/100){wt} → peak {hp:+.2f}% / close {cp:+.2f}%")
                msg_lines.append("")
                msg_lines.append("💀 <b>1h 最差 Bottom 3</b> (谷):")
                for sym, sc, hp, lp, cp, wr in worst:
                    wt = " 🐋" if wr == 1 else ""
                    msg_lines.append(f"  ${sym} ({sc}/100){wt} → 谷 {lp:+.2f}% / close {cp:+.2f}%")

        if short_mode:
            msg_lines.extend([
                "",
                "⚠️ SHORT 视角胜率: close &lt; entry = 做空赚",
                "⚠️ 触发条件 score≥60 + OI 1h≥30% + 24h>10% (FOMO 顶部空头)",
                "⚠️ 当前 SHORT 是 dogfood, 不进频道",
            ])
        else:
            msg_lines.extend([
                "",
                "⚠️ Peak = 上帝视角 (实战胜率参考 close)",
                "⚠️ 单边 long, 信号触发时已涨, 存活者偏差",
            ])

        send_tg_reply(chat_id, "\n".join(msg_lines))

    except Exception as e:
        send_tg_reply(chat_id, f"❌ 计算失败: {str(e)[:200]}")
        print(f"[Winrate] error: {e}")
        import traceback; traceback.print_exc()



def cmd_growth(chat_id, args):
    """v30.14.16: /growth — 频道增长诊断 (admin 私聊用)
    可用数据 (Bot API 限制下能拿到的):
      1. 订阅数日变化 (getChatMemberCount + KV 历史)
      2. 各类推送量 (近 7d, sentinel_signals + whale_alerts + KV)
      3. 推送频次 vs 订阅增长相关性
    无法做到 (Bot API 不支持):
      • views / forwards / 单条推送转化率 (需 MTProto, 不在本版本)
    """
    # 鉴权: 仅 admin 可看
    if TG_ADMIN_CHAT_ID and str(chat_id) != str(TG_ADMIN_CHAT_ID):
        send_tg_reply(chat_id, "🔒 /growth 仅 admin 可用")
        return

    # 🆕 v30.14.26: 修 v30.14.16 bug — args 是 list 不是 str
    parts = args if isinstance(args, list) else (args or "").strip().split()
    days = 7
    if parts and parts[0].isdigit():
        days = max(1, min(30, int(parts[0])))

    # 1. 当前订阅数 (Bot API getChatMemberCount)
    cur_count = None
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChatMemberCount",
                params={"chat_id": TELEGRAM_CHAT_ID},
                timeout=10
            )
            if r.status_code == 200 and r.json().get("ok"):
                cur_count = r.json()["result"]
        except Exception as e:
            print(f"[Growth] 取订阅数错误: {e}")

    # 2. 落库今日订阅数 (供未来对比, KV 模式)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    today_str = datetime.now().strftime("%Y-%m-%d")
    if cur_count is not None:
        try:
            kv_set(conn, f"sub_count_{today_str}", str(cur_count))
        except Exception:
            pass

    # 3. 历史订阅数 (最近 N 天的快照)
    history = []
    for i in range(days + 1):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        v = kv_get(conn, f"sub_count_{d}")
        if v:
            try:
                history.append((d, int(v)))
            except Exception:
                pass
    history.sort()  # 升序 (旧 → 新)

    # 4. 推送量统计 (近 N 天)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    n_direct = 0
    n_score = 0
    n_whale = 0
    try:
        n_direct = conn.execute(
            "SELECT COUNT(*) FROM sentinel_signals "
            "WHERE push_channel='direct' AND datetime(recorded_at) >= ?",
            (cutoff,)
        ).fetchone()[0]
        n_score = conn.execute(
            "SELECT COUNT(*) FROM sentinel_signals "
            "WHERE push_channel='score' AND datetime(recorded_at) >= ?",
            (cutoff,)
        ).fetchone()[0]
        n_whale = conn.execute(
            "SELECT COUNT(*) FROM whale_alerts "
            "WHERE datetime(alerted_at) >= ?",
            (cutoff,)
        ).fetchone()[0]
    except Exception as e:
        print(f"[Growth] DB 查询错误: {e}")

    total_pushes = n_direct + n_score + n_whale
    avg_per_day = total_pushes / max(1, days)

    # 5. 渲染
    lines = [
        f"📊 <b>频道增长诊断</b> · 近 {days} 天",
        "",
    ]
    if cur_count is not None:
        lines.append(f"👥 当前订阅: <b>{cur_count}</b>")
    else:
        lines.append("👥 当前订阅: 取数失败")

    if len(history) >= 2:
        earliest = history[0]
        latest = history[-1]
        delta = latest[1] - earliest[1]
        span_days = (datetime.strptime(latest[0], "%Y-%m-%d") -
                     datetime.strptime(earliest[0], "%Y-%m-%d")).days
        sign = "+" if delta >= 0 else ""
        lines.append(f"📈 {span_days} 天变化: <b>{sign}{delta}</b> ({earliest[1]} → {latest[1]})")
        if span_days >= 1:
            daily_avg = delta / span_days
            lines.append(f"📊 日均增长: <b>{daily_avg:+.1f}</b> / 天")
    elif len(history) == 1:
        lines.append(f"📅 历史快照仅 1 天 ({history[0][0]}), 明天起可算日增")
    else:
        lines.append("📅 暂无历史快照, 今天起开始记录")
    lines.append("")

    # 推送量
    lines.append(f"📤 <b>推送量</b> ({days} 天合计 {total_pushes} 条, 日均 {avg_per_day:.1f})")
    lines.append(f"  ⚡ direct (BN OI 直推): {n_direct}")
    lines.append(f"  📊 score (综合分): {n_score}")
    lines.append(f"  🐋 whale (鲸鱼告警): {n_whale}")
    lines.append("")

    # 相关性提示 (粗略, 不精确)
    if len(history) >= 3 and total_pushes > 0:
        # 简单看趋势: 头一半 vs 后一半推送多的那段, 订阅有没有增长更快?
        mid_d = (datetime.now() - timedelta(days=days // 2)).strftime("%Y-%m-%d %H:%M:%S")
        try:
            first_half = conn.execute(
                "SELECT COUNT(*) FROM sentinel_signals "
                "WHERE push_channel IN ('direct','score') AND datetime(recorded_at) BETWEEN ? AND ?",
                (cutoff, mid_d)
            ).fetchone()[0]
            second_half = conn.execute(
                "SELECT COUNT(*) FROM sentinel_signals "
                "WHERE push_channel IN ('direct','score') AND datetime(recorded_at) >= ?",
                (mid_d,)
            ).fetchone()[0]
            lines.append(f"🔍 <b>趋势对比</b>")
            lines.append(f"  前半段推送 {first_half} / 后半段 {second_half}")
        except Exception:
            pass
        lines.append("")

    # 历史快照 (最近 7 天明细)
    if history:
        lines.append("📜 <b>订阅历史</b>")
        for d, v in history[-7:]:
            lines.append(f"  {d}: {v}")
        lines.append("")

    lines.append("<i>⚠️ Bot API 不支持单条 views/forwards 查询</i>")
    lines.append("<i>明日继续记录, 数据会越来越丰富</i>")

    conn.close()
    send_tg_reply(chat_id, "\n".join(lines))


def snapshot_subscriber_count():
    """v30.14.16: 后台线程每天 23:59 北京 (15:59 UTC) 抓一次订阅数落 KV.
    供 /growth 查日变化用. 失败静默跳过, 不影响其他模块.
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChatMemberCount",
            params={"chat_id": TELEGRAM_CHAT_ID},
            timeout=10
        )
        if r.status_code == 200 and r.json().get("ok"):
            count = r.json()["result"]
            today_str = datetime.now().strftime("%Y-%m-%d")
            conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            kv_set(conn, f"sub_count_{today_str}", str(count))
            conn.close()
            print(f"[Growth] 📸 订阅数快照: {count} → kv[sub_count_{today_str}]")
    except Exception as e:
        print(f"[Growth] 快照失败: {e}")


# 🆕 v30.14.17 紧急修复: v30.14.16 误把 cmd_growth 替换了 cmd_search 函数声明行 (函数体留下成游离代码)
# 补回 def 声明
# 🆕 v30.14.21: 输/赢信号对比诊断 — 找避雷区 + 甜区
# 设计原则: 纯统计, 不接 LLM. Kings 看完自己拍板改不改阈值.
# 切片维度: 评分段 / 24h 涨幅 / funding / score_components 子分
def cmd_diagnose(chat_id, args):
    """🆕 v30.14.21: /diagnose [days] [channel]
    输/赢信号 setup 双向画像, 找避雷区 + 甜区.
    用法:
      /diagnose         → 默认 30 天, 全通道
      /diagnose 14      → 最近 14 天
      /diagnose 30 score → 仅综合分通道
      /diagnose 30 short → SHORT dogfood (反向胜负)
    """
    # 鉴权
    if TG_ADMIN_CHAT_ID and str(chat_id) != str(TG_ADMIN_CHAT_ID):
        send_tg_reply(chat_id, "🔒 /diagnose 仅 admin 可用")
        return

    days = 30
    channel_filter = None
    short_mode = False
    for a in args:
        if a.isdigit():
            days = max(1, min(60, int(a)))
        elif a.lower() in ("direct", "score"):
            channel_filter = a.lower()
        elif a.lower() == "short":
            short_mode = True

    send_tg_reply(chat_id, f"🔬 诊断中... 拉 {days} 天数据 + K 线反查 (约 30-60s)")

    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        # 查询条件
        if short_mode:
            where = ("push_channel='watch' AND score >= 60 AND change_24h > 10 "
                     "AND datetime(recorded_at) >= datetime('now', ?)")
        elif channel_filter:
            where = f"push_channel='{channel_filter}' AND datetime(recorded_at) >= datetime('now', ?)"
        else:
            where = "push_channel IN ('direct','score') AND datetime(recorded_at) >= datetime('now', ?)"

        rows = conn.execute(
            f"SELECT symbol, score, change_24h, funding_binance, funding_hyperliquid, "
            f"score_components, price, "
            f"COALESCE(signal_time, recorded_at) AS effective_time, "
            f"push_channel "
            f"FROM sentinel_signals WHERE {where} "
            f"ORDER BY recorded_at DESC LIMIT 500",
            (f"-{days} days",)
        ).fetchall()
        conn.close()

        if not rows or len(rows) < 10:
            send_tg_reply(chat_id, f"📭 样本不足 (n={len(rows)}), 至少需 10 条. 改用更长 days 试试.")
            return

        # 反查每条 24h close (这是最耗时的步骤)
        from concurrent.futures import ThreadPoolExecutor
        from datetime import datetime as dt, timedelta as td

        # 调试计数器
        skip_reasons = {"no_time": 0, "no_price": 0, "parse_fail": 0, "kline_fail": 0, "ok": 0}

        def fetch_close(row):
            sym, score, ch24, fund_bn, fund_hl, comps_json, price, sig_time, channel = row
            if not sig_time:
                skip_reasons["no_time"] += 1
                return None
            if not price or price <= 0:
                skip_reasons["no_price"] += 1
                return None
            try:
                # 🆕 v30.14.23: 把 sig_time 转 str 兼容 datetime 对象
                if not isinstance(sig_time, str):
                    sig_time = str(sig_time)
                # 兼容多种时间格式 (UTC ISO / datetime 字符串)
                sig_t = None
                # 🆕 v30.14.24: 清理 - 去时区标记 (UTC/+00:00/Z), 兼容 '2026-05-16 02:54 UTC' 这种带秒的
                clean = sig_time.strip()
                # 去末尾的 " UTC" / " GMT" 等时区文本
                for tz in (" UTC", " GMT", "UTC", "Z"):
                    if clean.endswith(tz):
                        clean = clean[: -len(tz)].strip()
                        break
                # 去 + 前缀的时区
                clean = clean.split("+")[0].strip()
                # 第 1 轮: 用 strptime 试 8 种主流格式
                for fmt in (
                    "%Y-%m-%d %H:%M:%S",      # 2026-05-16 02:54:30
                    "%Y-%m-%d %H:%M",          # 2026-05-16 02:54  ← v30.14.24 新增 (Kings 数据真实格式)
                    "%Y-%m-%dT%H:%M:%S",       # 2026-05-16T02:54:30
                    "%Y-%m-%dT%H:%M:%S.%f",    # 2026-05-16T02:54:30.123456
                    "%Y-%m-%d %H:%M:%S.%f",    # 2026-05-16 02:54:30.123456
                    "%Y-%m-%dT%H:%M",          # 2026-05-16T02:54
                    "%Y-%m-%d",                # 2026-05-16
                    "%Y/%m/%d %H:%M:%S",       # 2026/05/16 02:54:30
                ):
                    try:
                        sig_t = datetime.strptime(clean[:26], fmt)
                        break
                    except Exception:
                        continue
                # 第 2 轮: 兜底, 尝试 fromisoformat
                if sig_t is None:
                    try:
                        sig_t = datetime.fromisoformat(clean.replace(" ", "T"))
                    except Exception:
                        pass
                # 第 3 轮: 最后兜底, 把 sample 暴露给 admin debug
                if sig_t is None:
                    if "sample_time" not in skip_reasons:
                        skip_reasons["sample_time"] = repr(sig_time)[:80]
                    skip_reasons["parse_fail"] += 1
                    return None

                end_t = sig_t + td(hours=24)
                start_ms = int(sig_t.timestamp() * 1000)
                end_ms = int(end_t.timestamp() * 1000)
                result = _winrate_fetch_one(sym, price, start_ms, end_ms, "1h", 25)
                if result is None:
                    skip_reasons["kline_fail"] += 1
                    return None
                high_pct, low_pct, close_pct = result
                # 解析 components
                try:
                    comps = json.loads(comps_json) if comps_json else {}
                except Exception:
                    comps = {}
                skip_reasons["ok"] += 1
                return {
                    "sym": sym, "score": score, "ch24": ch24,
                    "fund_bn": fund_bn, "fund_hl": fund_hl,
                    "close_pct": close_pct, "high_pct": high_pct, "low_pct": low_pct,
                    "oi_score": comps.get("oi", 0),
                    "price_score": comps.get("price", 0),
                    "funding_score": comps.get("funding", 0),
                    "cross_score": comps.get("cross", 0),
                    "channel": channel,
                }
            except Exception:
                skip_reasons["parse_fail"] += 1
                return None

        with ThreadPoolExecutor(max_workers=8) as ex:
            results = [r for r in ex.map(fetch_close, rows) if r is not None]

        n = len(results)
        if n < 10:
            # 🆕 加调试信息让 admin 知道为啥失败
            sample_info = ""
            if "sample_time" in skip_reasons:
                sample_info = f"\n样本时间字符串: <code>{skip_reasons['sample_time']}</code>"
            send_tg_reply(chat_id,
                f"📭 K 线反查后样本 {n} 条不足, 跳过原因:\n"
                f"  - 无时间字段: {skip_reasons['no_time']}\n"
                f"  - 无价格: {skip_reasons['no_price']}\n"
                f"  - 时间格式解析失败: {skip_reasons['parse_fail']}\n"
                f"  - K 线反查失败: {skip_reasons['kline_fail']}\n"
                f"  - 成功: {skip_reasons['ok']}\n"
                f"{sample_info}\n"
                f"\nSQL 查到 {len(rows)} 条, 但 K 线反查不够 10 条. "
                f"BN 可能限速或币种已下架. 改用更短 days 或等会再试."
            )
            return

        # 定义"赢"/"输" (24h close 视角)
        # SHORT 模式: close < -3% 算赢, close > 0 算输
        # LONG 模式: close > +3% 算赢, close < -3% 算输 (实战伤害定义)
        if short_mode:
            wins = [r for r in results if r["close_pct"] < -3]
            losses = [r for r in results if r["close_pct"] > 0]
            mode_str = "🔻 SHORT 视角 (close ≤ -3% 算赢, close > 0 算输)"
        else:
            wins = [r for r in results if r["close_pct"] > 3]
            losses = [r for r in results if r["close_pct"] < -3]
            mode_str = "📊 LONG 视角 (close ≥ +3% 算赢, close ≤ -3% 算输)"

        n_w = len(wins)
        n_l = len(losses)

        msg = [
            f"🔬 <b>输/赢信号对比诊断</b>",
            f"周期: 最近 {days} 天 · 总样本 n={n}",
            f"模式: {mode_str}",
            f"赢: {n_w} ({n_w/n*100:.0f}%) · 输: {n_l} ({n_l/n*100:.0f}%)",
            "",
        ]

        if n_w < 3 or n_l < 3:
            msg.append("⚠️ 赢或输的样本太少 (<3), 分布分析跳过")
            msg.append("→ 建议跑更长 days 累积样本")
            send_tg_reply(chat_id, "\n".join(msg))
            return

        # ============== 维度切片对比 ==============
        # 工具函数: 按 bucket 切, 算赢率
        def bucket_analysis(values_w, values_l, buckets, label, unit=""):
            """values_w, values_l: 维度数值. buckets: [(label, min, max), ...] 切片边界"""
            lines = [f"📊 <b>{label}</b>"]
            for blabel, bmin, bmax in buckets:
                w_count = sum(1 for v in values_w if bmin <= v < bmax)
                l_count = sum(1 for v in values_l if bmin <= v < bmax)
                total = w_count + l_count
                if total == 0:
                    win_rate = "—"
                    tag = ""
                else:
                    win_rate = f"{w_count/total*100:.0f}%"
                    if total >= 5:  # 样本 ≥5 才标记
                        if w_count / total >= 0.6:
                            tag = " ✅ 甜区"
                        elif w_count / total <= 0.2:
                            tag = " 💀 重灾"
                        elif w_count / total <= 0.35:
                            tag = " ⚠️ 弱区"
                        else:
                            tag = ""
                    else:
                        tag = " (样本小)"
                lines.append(f"  {blabel}{unit}: 赢 {w_count} / 输 {l_count} (赢率 {win_rate}){tag}")
            return lines

        # 1. 评分段
        msg.extend(bucket_analysis(
            [r["score"] for r in wins],
            [r["score"] for r in losses],
            [("60-65", 60, 66), ("66-70", 66, 71), ("71+", 71, 200)],
            "评分段"
        ))
        msg.append("")

        # 2. 24h 涨幅区间
        msg.extend(bucket_analysis(
            [r["ch24"] for r in wins],
            [r["ch24"] for r in losses],
            [("≤-5%", -100, -5), ("-5~0%", -5, 0), ("0-2%", 0, 2),
             ("2-3%", 2, 3), ("3-5%", 3, 5), ("5-10%", 5, 10), ("≥10%", 10, 1000)],
            "24h 涨幅"
        ))
        msg.append("")

        # 3. funding (取 max 两所)
        def max_fund(r):
            return max(abs(r["fund_bn"]), abs(r["fund_hl"]))
        msg.extend(bucket_analysis(
            [max_fund(r) * 100 for r in wins],  # 转 %
            [max_fund(r) * 100 for r in losses],
            [("0-0.005", 0, 0.005), ("0.005-0.02", 0.005, 0.02),
             ("0.02-0.04", 0.02, 0.04), ("≥0.04", 0.04, 100)],
            "funding 8h", unit="%"
        ))
        msg.append("")

        # 4. OI 子分 (评分组件里的 oi 分数, 0-25)
        msg.extend(bucket_analysis(
            [r["oi_score"] for r in wins],
            [r["oi_score"] for r in losses],
            [("0-10", 0, 11), ("11-17", 11, 18), ("18-25", 18, 26)],
            "OI 子分 (满分 25)"
        ))
        msg.append("")

        # 5. price 子分
        msg.extend(bucket_analysis(
            [r["price_score"] for r in wins],
            [r["price_score"] for r in losses],
            [("0-3", 0, 4), ("4-9", 4, 10), ("10-17", 10, 18)],
            "price 子分 (满分 17)"
        ))
        msg.append("")

        # 6. cross 共所一致性子分
        msg.extend(bucket_analysis(
            [r["cross_score"] for r in wins],
            [r["cross_score"] for r in losses],
            [("0", 0, 1), ("5", 5, 6), ("10", 10, 11), ("15", 15, 16)],
            "cross 共所一致性 (0/5/10/15)"
        ))
        msg.append("")

        # ============== 详细列表: 输得最惨 + 赢得最好 ==============
        msg.append("━━━━━━━━━━━━━━")
        msg.append("💀 <b>输得最惨 Top 5</b> (按 close_pct 升序)")
        worst = sorted(losses, key=lambda r: r["close_pct"])[:5]
        for r in worst:
            msg.append(f"  ${r['sym']} {r['score']}/100 · 24h={r['ch24']:+.1f}% · close={r['close_pct']:+.1f}%")
        msg.append("")
        msg.append("🏆 <b>赢得最好 Top 5</b>")
        best = sorted(wins, key=lambda r: -r["close_pct"])[:5]
        for r in best:
            msg.append(f"  ${r['sym']} {r['score']}/100 · 24h={r['ch24']:+.1f}% · close={r['close_pct']:+.1f}%")
        msg.append("")

        msg.append("━━━━━━━━━━━━━━")
        msg.append("ℹ️ <b>注意事项</b>")
        msg.append("• 样本 <5 的 bucket 不可靠")
        msg.append("• 不要单凭一次诊断改阈值, 跨周复跑验证")
        msg.append("• 改阈值后跑 2 周再评估效果")
        msg.append("• 这是纯统计, 非 LLM 决策, 你看完自己拍板")

        send_tg_reply(chat_id, "\n".join(msg))

    except Exception as e:
        send_tg_reply(chat_id, f"❌ 诊断错误: {e}")


def setup_tg_bot_menu():
    """🆕 v30.14.31: 设置 TG bot 的 commands menu bar (左下角斜杠菜单)"""
    if not TELEGRAM_TOKEN:
        print("[BotMenu] ⚠️ 无 TG token, 跳过")
        return
    # commands 列表 (TG 限 30 个, 我们 10 个)
    commands = [
        {"command": "start", "description": "🏠 主菜单"},
        {"command": "help", "description": "📚 帮助和命令列表"},
        {"command": "top", "description": "💰 最新高价值 bounty"},
        {"command": "defi", "description": "📊 DeFi 收益机会"},
        {"command": "whale", "description": "🐋 鲸鱼查询"},
        {"command": "pnl", "description": "💼 纸上交易账户 (admin)"},
        {"command": "analyze", "description": "🔬 Sonnet 深度分析 (admin)"},
        {"command": "winrate", "description": "📈 赏金哨胜率统计"},
        {"command": "diagnose", "description": "🔬 信号诊断 (admin)"},
        {"command": "growth", "description": "📊 频道增长 (admin)"},
        {"command": "about", "description": "ℹ️ 关于赏金哨"},
    ]
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setMyCommands",
            json={"commands": commands},
            timeout=10,
        )
        if r.status_code == 200 and r.json().get("ok"):
            print(f"[BotMenu] ✅ 设置 {len(commands)} 个菜单命令")
        else:
            print(f"[BotMenu] ❌ HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[BotMenu] ❌ {e}")


def cmd_pnl(chat_id, args):
    """🆕 v30.14.31: 纸上交易账户查询 (admin only)
    显示: 账户余额 + 当前开仓 + 已完成单 + 通道分布
    🆕 v30.14.32: 加总 PnL + 胜率 + 通道 ROI
    """
    if TG_ADMIN_CHAT_ID and str(chat_id) != str(TG_ADMIN_CHAT_ID):
        send_tg_reply(chat_id, "🔒 /pnl 仅 admin 可用")
        return

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    try:
        init_paper_trading_db(conn)
        balance = float(kv_get(conn, "paper_balance") or PAPER_INITIAL_BALANCE)
        next_no = int(kv_get(conn, "paper_next_signal_no") or 1)
        total_signals = next_no - 1

        # 🆕 v30.14.32: 总 PnL + 胜率统计 (已平仓单)
        stats = conn.execute(
            "SELECT COUNT(*), "
            "       COALESCE(SUM(pnl_usd), 0), "
            "       COALESCE(SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END), 0), "
            "       COALESCE(SUM(CASE WHEN pnl_usd < 0 THEN 1 ELSE 0 END), 0) "
            "FROM paper_positions WHERE status != 'open'"
        ).fetchone()
        closed_count, total_pnl, wins, losses = stats
        winrate = (wins / closed_count * 100) if closed_count > 0 else None
        balance_change_pct = (balance - PAPER_INITIAL_BALANCE) / PAPER_INITIAL_BALANCE * 100

        # 拉所有仓位
        open_rows = conn.execute(
            "SELECT signal_no, symbol, channel, direction, entry_price, entry_time, "
            "       position_usd, notional_usd "
            "FROM paper_positions WHERE status='open' "
            "ORDER BY signal_no DESC LIMIT 20"
        ).fetchall()

        closed_rows = conn.execute(
            "SELECT signal_no, symbol, channel, direction, pnl_usd, pnl_pct, exit_reason "
            "FROM paper_positions WHERE status != 'open' "
            "ORDER BY signal_no DESC LIMIT 10"
        ).fetchall()

        # 通道统计
        channel_stats = conn.execute(
            "SELECT channel, COUNT(*), COALESCE(SUM(pnl_usd), 0) "
            "FROM paper_positions GROUP BY channel"
        ).fetchall()

        # 构造文案
        lines = [
            "💼 <b>纸上交易账户</b>",
            "",
            f"💰 当前余额: <b>${balance:.2f}</b> ({balance_change_pct:+.2f}%)",
            f"📊 累计信号: {total_signals} 单 (已平 {closed_count}, 持仓 {len(open_rows)})",
            f"⚡ 杠杆: {PAPER_LEVERAGE}x · 每单 {int(PAPER_POSITION_PCT * 100)}% 本金",
        ]

        # 总 PnL + 胜率
        if closed_count > 0:
            pnl_emoji = "✅" if total_pnl > 0 else ("❌" if total_pnl < 0 else "➖")
            wr_str = f"{winrate:.0f}%" if winrate is not None else "—"
            lines.append(f"💸 总 PnL: {pnl_emoji} <b>${total_pnl:+.2f}</b> · 胜率 {wr_str} ({wins}W/{losses}L)")

        lines.append("")

        # 通道分布
        if channel_stats:
            lines.append("━━━━━━━━━━━━━━")
            lines.append("📡 通道分布:")
            for ch, cnt, pnl in channel_stats:
                pnl_tag = f" (PnL ${pnl:+.2f})" if pnl else ""
                lines.append(f"  {ch}: {cnt} 单{pnl_tag}")
            lines.append("")

        # 当前开仓
        if open_rows:
            lines.append("━━━━━━━━━━━━━━")
            lines.append(f"🔓 当前开仓 ({len(open_rows)}):")
            for row in open_rows[:10]:
                no, sym, ch, dir_, ep, et, pos, notional = row
                dir_emoji = "📈" if dir_ == "long" else "📉"
                # 算持仓时长
                try:
                    et_dt = datetime.fromisoformat(et.replace(" UTC", "").replace(" ", "T"))
                    hours = (_utcnow() - et_dt).total_seconds() / 3600
                    hold = f"{hours:.1f}h" if hours < 24 else f"{hours/24:.1f}d"
                except Exception:
                    hold = "?"
                lines.append(f"  #{no:03d} {dir_emoji} ${sym} ({ch}) · {hold}")
            if len(open_rows) > 10:
                lines.append(f"  ...还有 {len(open_rows)-10} 单")
            lines.append("")
        else:
            lines.append("🔓 当前无开仓\n")

        # 最近完成
        if closed_rows:
            lines.append("━━━━━━━━━━━━━━")
            lines.append("📜 最近完成 (Top 10):")
            for row in closed_rows:
                no, sym, ch, dir_, pnl, pct, reason = row
                pnl_emoji = "✅" if (pnl or 0) > 0 else ("❌" if (pnl or 0) < 0 else "➖")
                dir_label = "LONG" if dir_ == "long" else "SHORT"
                lines.append(f"  {pnl_emoji} #{no:03d} {dir_label} ${sym}: "
                             f"${pnl:+.2f} ({pct:+.2f}%) [{reason or '?'}]")
            lines.append("")
        else:
            lines.append("📜 还没完成的单 (v30.14.31 自动结算待加)\n")

        lines.append("ℹ️ <i>v30.14.31 dogfood 模式</i>")
        lines.append("ℹ️ <i>仓位自动结算: 1h LONG / 4h SHORT 时间窗到</i>")

        send_tg_reply(chat_id, "\n".join(lines))
    except Exception as e:
        send_tg_reply(chat_id, f"❌ /pnl 错误: {e}")
        print(f"[PnL] {e}")
    finally:
        conn.close()


def _call_sonnet(prompt, max_tokens=2000, system=None):
    """🆕 v30.14.33: 通用 Sonnet 调用 (更深分析). 失败返回 None"""
    if not ANTHROPIC_API_KEY:
        return None
    try:
        body = {
            "model": "claude-sonnet-4-5-20250929",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]
        }
        if system:
            body["system"] = system
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json=body,
            timeout=60
        )
        if r.status_code == 200:
            data = r.json()
            content = data.get("content", [])
            if content and content[0].get("type") == "text":
                return content[0].get("text", "").strip()
        else:
            print(f"[Sonnet] HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[Sonnet] {e}")
    return None


_capture_lock = threading.Lock()
_capture_thread_id = None  # 只对发起线程拦截
_capture_buffer = None


def _capture_cmd_output(cmd_func, args):
    """🆕 v30.14.33: 临时拦截 send_tg_reply 到字符串
    🆕 用 thread ID 隔离, 后台线程 (Paper 开仓/平仓/Briefing) 不受影响
    🆕 hotfix: 用 TG_ADMIN_CHAT_ID 调用 cmd, 绕过 admin 权限检查
    """
    global _capture_thread_id, _capture_buffer, send_tg_reply

    # 串行: 同时只允许一个 /analyze
    acquired = _capture_lock.acquire(timeout=5)
    if not acquired:
        return "(无法获取 capture lock, 可能并发冲突)"

    captured = []
    original = send_tg_reply
    my_tid = threading.get_ident()

    def fake_reply(chat_id, msg):
        # 只在发起 /analyze 的线程里拦截; 其他线程透传 original
        if threading.get_ident() == my_tid:
            captured.append(msg)
        else:
            original(chat_id, msg)

    try:
        _capture_thread_id = my_tid
        _capture_buffer = captured
        send_tg_reply = fake_reply
        # 🆕 用 admin chat_id, 绕过 cmd_* 内部权限检查 (否则会立刻 return "仅 admin 可用")
        admin_id = TG_ADMIN_CHAT_ID if TG_ADMIN_CHAT_ID else 0
        cmd_func(admin_id, args)
    except Exception as e:
        print(f"[Capture] {e}")
    finally:
        send_tg_reply = original
        _capture_thread_id = None
        _capture_buffer = None
        _capture_lock.release()

    return "\n\n".join(captured) if captured else "(无输出)"


def cmd_analyze(chat_id, args):
    """🆕 v30.14.33: /analyze admin 命令
    自动跑 3 个核心诊断 + Claude Sonnet 深度分析
      • /diagnose 30 long
      • /winrate 30 score
      • /winrate 7 short
    跨周对比 + 异常告警 + 新发现 + 推荐
    """
    if TG_ADMIN_CHAT_ID and str(chat_id) != str(TG_ADMIN_CHAT_ID):
        send_tg_reply(chat_id, "🔒 /analyze 仅 admin 可用")
        return

    if not ANTHROPIC_API_KEY:
        send_tg_reply(chat_id, "❌ ANTHROPIC_API_KEY 未配置, 无法调用 Sonnet")
        return

    send_tg_reply(chat_id, "⏳ <b>/analyze 启动</b>\n\n"
                            "拉取 3 份诊断 + Sonnet 深度分析中...\n"
                            "预计 30-60 秒, 请耐心等待")

    start_time = time.time()

    try:
        # 1. 跑 3 个诊断 (捕获输出)
        print("[Analyze] 拉取 /diagnose 30 long...")
        diag_text = _capture_cmd_output(cmd_diagnose, ["30"])

        print("[Analyze] 拉取 /winrate 30 score...")
        wr_score_text = _capture_cmd_output(cmd_winrate, ["30", "score"])

        print("[Analyze] 拉取 /winrate 7 short...")
        wr_short_text = _capture_cmd_output(cmd_winrate, ["7", "short"])

        # 长度检查
        total_chars = len(diag_text) + len(wr_score_text) + len(wr_short_text)
        print(f"[Analyze] 拉取完成, 总 {total_chars} 字符")

        # 2. 拉上次快照对比
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        try:
            last_snapshot_json = kv_get(conn, "analyze_snapshot_last")
            last_at = kv_get(conn, "analyze_last_at")
        finally:
            conn.close()

        last_summary = "(无上次快照, 这是首次跑 /analyze)"
        if last_snapshot_json:
            try:
                last_snap = json.loads(last_snapshot_json)
                # 截断每份避免太长
                last_summary = (
                    f"上次跑时间: {last_at}\n"
                    f"--- 上次 /diagnose ---\n{last_snap.get('diag', '')[:2000]}\n\n"
                    f"--- 上次 /winrate score ---\n{last_snap.get('wr_score', '')[:1500]}\n\n"
                    f"--- 上次 /winrate short ---\n{last_snap.get('wr_short', '')[:1500]}"
                )
            except Exception as e:
                print(f"[Analyze] 上次快照解析失败: {e}")

        # 3. 构造 Sonnet prompt
        system = """你是 Bounty Monitor 的资深数据分析师, 服务 Kings (@0xKingsKuan).

📚 历史已确诊事实 (不要标记为"新发现", 不要"反转"判断):

【LONG 视角 - /diagnose 30 long 数据】跨 7 周稳定:
• 评分 60-65: 24-25% 赢率 ⚠️ 弱区
• 评分 66-70: 6% 赢率 💀 重灾 (避雷)
• 24h ≤-5%: 75-76% 赢率 ✅ 甜区 (rebound 通道)
• 24h 5-10%: 12% 赢率 💀 重灾 (避雷)
• 24h ≥10%: 29% 赢率 ⚠️ 弱区
• funding 0-0.005%: 20% 赢率 💀 重灾
• funding 0.005-0.02%: 35% 赢率 (普通)
• funding 0.02-0.04%: 55% 赢率 ✅ LONG 一直就是这个数, 不是"反转"
• funding ≥0.04%: 22% 赢率 ⚠️ 弱区 (避雷)
• OI 0-10: 44% 赢率 ⭐ 反直觉规律 (历史多次确诊, 不是新发现)
• OI 11-17: 28% 赢率 ⚠️
• OI 18-25: 29% 赢率 ⚠️
• cross=10: 0% 赢率 💀 (避雷)
• cross=15: 0% 赢率 💀 (避雷)

【SHORT 视角 - /winrate 7 short 数据】跨 5 周稳定 (注意 SHORT close<entry 算赢):
• 4h close 胜率: 67-85% (均 72-75%) ✅ 主要 alpha (跨 5 周, 但本周可能波动)
• 24h close 胜率: 71-82% ✅
• 反向止损 ≥+3%: 22-29% (GMT/ALT 反弹币种主导)
• cross=10 SHORT 视角: 76-78% ✅ 甜区
• funding ≥0.04% SHORT: 69-79% ✅ 甜区 (跟 LONG 22% 完全不同!)
• funding 0.02-0.04% SHORT: 29% (反向区, 已跳过)
• OI 18-25 SHORT: 58-62%

【已知币种特征】
• $PLAY: 1 个月前主导 LONG 输面 (5 单 -57%), 现在可能不再活跃
• $FHE: 同期主导 LONG 赢面 (5 单 +37%)
• $GMT/$ALT: SHORT 反弹币种 (反向止损主因)

【绝对禁止的话】
❌ "反转/翻正" - 除非数据真的从 < 30% 变到 > 60% 跨 2 周
❌ "新发现" - 上面列表里的都不算新
❌ "立即 blacklist" - 单币种不该硬编码
❌ "立即停止" - 1 周数据不够, 至少 2 周复核

【你的任务】
1. **跨周对比**: 跟上次数据对比, 找变化 ≥5% 且样本 ≥30 的指标
2. **异常告警**: 哪个 alpha 真的在衰减 (vs 历史已知区间)
3. **真正的新规律**: 不在上面列表里的 (要求样本 ≥30 + 跨 2 周一致)
4. **推荐动作**: 具体且保守, 优先"等 X 周验证"而不是"立即执行"

【LONG/SHORT 视角混淆陷阱】
• /diagnose 30 long → close ≥+3% 算赢, close ≤-3% 算输 (LONG 视角)
• /winrate 7 short → close < entry 算赢 (SHORT 视角)
• 同一 funding 区间, LONG vs SHORT 视角完全不同!

【输出格式 - mobile-friendly, ≤600 字】
📊 Alpha 深度分析

🟢 跨周稳定 (无需操作):
• ...

🟡 数据变化 (关注):
• ...

🔴 异常告警 (建议动作):
• ...

🆕 真正新发现 (如果有, 必须不在历史列表):
• ...

💡 推荐:
1. ...
2. ...

要求: 中文回答, 引用具体数字, 优先保守建议"""

        user_prompt = f"""=== 本次数据 ===

--- /diagnose 30 long ---
{diag_text[:3500]}

--- /winrate 30 score ---
{wr_score_text[:2500]}

--- /winrate 7 short ---
{wr_short_text[:2500]}

=== 上次数据 (对比基准) ===
{last_summary[:5000]}

请按 system 要求输出深度分析."""

        # 4. 调用 Sonnet
        print(f"[Analyze] 调用 Sonnet (prompt ~{len(user_prompt)} 字符)...")
        sonnet_output = _call_sonnet(user_prompt, max_tokens=2000, system=system)
        elapsed = time.time() - start_time

        if not sonnet_output:
            send_tg_reply(chat_id, f"❌ Sonnet 调用失败, 耗时 {elapsed:.1f}s\n"
                                    "请稍后重试或检查 ANTHROPIC_API_KEY")
            return

        # 5. 推送结果
        header = f"📊 <b>/analyze 深度分析</b>\n"
        header += f"⏰ 耗时 {elapsed:.1f}s · Sonnet 4.5\n\n"

        # Sonnet 返回的可能含 markdown, 直接转给 TG (用 HTML mode 已经默认)
        # 但 Sonnet 可能输出 **bold** Markdown, 转 <b>
        formatted = sonnet_output
        import re as _re
        formatted = _re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', formatted)
        formatted = _re.sub(r'__(.+?)__', r'<b>\1</b>', formatted)

        full_msg = header + formatted

        # TG 单条限 4096 字符, 截断
        if len(full_msg) > 4000:
            full_msg = full_msg[:3950] + "\n\n<i>...(已截断)</i>"

        send_tg_reply(chat_id, full_msg)

        # 6. 保存本次快照 (供下次对比)
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        try:
            new_snapshot = {
                "diag": diag_text[:8000],
                "wr_score": wr_score_text[:5000],
                "wr_short": wr_short_text[:5000],
            }
            kv_set(conn, "analyze_snapshot_last", json.dumps(new_snapshot))
            kv_set(conn, "analyze_last_at", (_utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M (北京)"))
            conn.commit()
        finally:
            conn.close()

        print(f"[Analyze] ✅ 完成, {elapsed:.1f}s, 输出 {len(sonnet_output)} 字符")

    except Exception as e:
        elapsed = time.time() - start_time
        send_tg_reply(chat_id, f"❌ /analyze 错误: {e}\n耗时 {elapsed:.1f}s")
        print(f"[Analyze] error: {e}")


def cmd_search(chat_id, args):
    if not args:
        send_tg_reply(chat_id, "用法: /search &lt;关键词&gt;")
        return
    kw = " ".join(args).lower()
    all_b, _, _ = _get_latest()
    if not all_b:
        send_tg_reply(chat_id, "⏳ 数据未就绪")
        return
    matches = [b for b in all_b if kw in b.get('t', '').lower()
               or kw in b.get('org', '').lower()
               or kw in b.get('symbol', '').lower()][:8]
    if not matches:
        send_tg_reply(chat_id, f"未找到匹配 \"{kw}\" 的活动")
        return
    msg = f"🔍 \"{kw}\" 搜索结果 ({len(matches)} 个):\n\n"
    for b in matches:
        if is_defi(b):
            msg += f"💹 {b['t']} | APY {b.get('apy', 0):.1f}%\n"
        else:
            msg += f"📋 {b['t'][:60]}"
            if b.get('v'):
                msg += f" | ${b['v']:,}"
            msg += "\n"
        msg += f"🔗 {b['u']}\n\n"
    send_tg_reply(chat_id, msg.strip())

def cmd_risk(chat_id, args):
    if not args:
        send_tg_reply(chat_id, "用法: /risk &lt;token&gt;  例: /risk usdc")
        return
    token = args[0].upper()
    all_b, _, _ = _get_latest()
    if not all_b:
        send_tg_reply(chat_id, "⏳ 数据未就绪")
        return
    matches = [b for b in all_b if is_defi(b) and token in (b.get('symbol', '') or '').upper()]
    matches.sort(key=lambda x: score_risk(x))
    matches = matches[:8]
    if not matches:
        send_tg_reply(chat_id, f"未找到 {token} 相关收益")
        return
    msg = f"🛡️ {token} 收益机会 (按风险升序):\n\n"
    for b in matches:
        r = score_risk(b)
        msg += f"{risk_emoji(r)} Risk {r}/10 | {b.get('org','')}\n"
        msg += f"📈 APY: {b.get('apy', 0):.2f}% | TVL: ${b.get('tvl', 0)/1e6:.1f}M\n"
        msg += f"🔗 {b['u']}\n\n"
    send_tg_reply(chat_id, msg.strip())

def cmd_v(chat_id, args):
    """v26: 反查尾行标签对应的完整数据"""
    if not args:
        send_tg_reply(chat_id,
            "用法: /v &lt;short_id&gt;\n"
            "例: /v a7f3  (从推送尾行 📎 bm-a7f3 复制)\n\n"
            f"📦 当前缓存: {len(_bounty_lookup)} 条记录")
        return
    sid = args[0].strip().lower().replace("bm-", "")
    data = get_lookup(sid)
    if not data:
        send_tg_reply(chat_id,
            f"❌ 未找到 bm-{sid}\n"
            f"(可能已被 LRU 淘汰, 当前缓存 {len(_bounty_lookup)} 条)")
        return
    # 简洁展示关键字段
    def fmt(v):
        if isinstance(v, (list, dict)):
            return json.dumps(v, ensure_ascii=False)[:100]
        s = str(v)
        return s[:100]
    priority_keys = ['_sid', '_typ', '_v', '_r', 't', 's', 'org', 'apy', 'tvl',
                     'symbol', 'chain', 'deadline', 'remaining', 'type', 'region',
                     'u', 'url', '_alert_type', '_key', 'price', 'severity']
    lines = [f"📎 bm-{sid} 反查结果:\n"]
    seen = set()
    for k in priority_keys:
        if k in data and data[k] not in (None, "", 0, []):
            lines.append(f"  {k}: {fmt(data[k])}")
            seen.add(k)
    # 其他字段 (隐藏以_开头的元字段太多)
    other = [k for k in data.keys() if k not in seen and not k.startswith("_")]
    if other:
        lines.append("\n其他字段:")
        for k in other[:10]:
            lines.append(f"  {k}: {fmt(data[k])}")
    send_tg_reply(chat_id, "\n".join(lines))


# ============================================================
# 🆕 v28.0 /whale 命令 (鲸鱼主动查询)
# ============================================================
def _whale_query_conn():
    """为 bot 命令开一个连接 (避免和主循环竞争写锁). v28.2.1: 加 busy_timeout 防锁"""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=5.0)
    # 5 秒内等锁释放, 超时才报 "database is locked"
    try:
        conn.execute("PRAGMA busy_timeout = 5000")
    except Exception:
        pass
    return conn


def _whale_fmt_dist_pct(cp):
    """算距清算百分比字符串, 返回 (dist_pct, display_str)"""
    try:
        liq = float(cp.get("liq_px", 0) or 0)
        size_coin = float(cp.get("size_coin", 0) or 0)
        size_usd = float(cp.get("size_usd", 0) or 0)
        side = cp.get("side", "")
        if liq <= 0 or size_coin <= 0:
            return None, "—"
        market = size_usd / size_coin if size_coin > 0 else cp.get("entry_px", 0)
        if market <= 0:
            return None, "—"
        if side == "long":
            dist = (market - liq) / market * 100
        else:
            dist = (liq - market) / market * 100
        dist = max(0.01, dist)
        if dist < 3:
            return dist, f"🔴 {dist:.1f}%"
        if dist < 8:
            return dist, f"🟠 {dist:.1f}%"
        if dist < 15:
            return dist, f"🟡 {dist:.1f}%"
        return dist, f"🟢 {dist:.1f}%"
    except Exception:
        return None, "—"


def _whale_current_positions(conn, addresses):
    """从 whale_positions 表拉每个地址最新仓位"""
    positions = []
    for addr in addresses:
        rows = conn.execute(
            "SELECT coin, side, size_coin, size_usd, entry_px, liq_px, unrealized_pnl, leverage, recorded_at "
            "FROM whale_positions WHERE address=? "
            "AND recorded_at = (SELECT MAX(recorded_at) FROM whale_positions WHERE address=?)",
            (addr.lower(), addr.lower())
        ).fetchall()
        for r in rows:
            positions.append({
                "addr": addr, "coin": r[0], "side": r[1],
                "size_coin": r[2] or 0, "size_usd": r[3] or 0,
                "entry_px": r[4] or 0, "liq_px": r[5] or 0,
                "unrealized_pnl": r[6] or 0, "leverage": r[7] or 0,
                "recorded_at": r[8],
            })
    return positions


def _whale_pnl_one(conn, addresses, hours=24):
    """对单个鲸鱼 (含马甲所有地址) 算 24h delta. 返回 (cur_value, delta, pct) 或 (None, None, None)"""
    cutoff_dt = _utcnow() - timedelta(hours=hours)
    cutoff_str = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")
    window_start = (cutoff_dt - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
    window_end = (cutoff_dt + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")

    cur_total = 0.0
    prev_total = 0.0
    ok = 0
    for addr in addresses:
        addr = addr.lower()
        cur_row = conn.execute(
            "SELECT account_value FROM whale_account_values WHERE address=? "
            "ORDER BY recorded_at DESC LIMIT 1", (addr,)
        ).fetchone()
        prev_row = conn.execute(
            "SELECT account_value FROM whale_account_values "
            "WHERE address=? AND recorded_at BETWEEN ? AND ? "
            "ORDER BY ABS(strftime('%s', recorded_at) - strftime('%s', ?)) LIMIT 1",
            (addr, window_start, window_end, cutoff_str)
        ).fetchone()
        if not prev_row:
            prev_row = conn.execute(
                "SELECT account_value FROM whale_account_values "
                "WHERE address=? AND recorded_at <= ? "
                "ORDER BY recorded_at DESC LIMIT 1", (addr, cutoff_str)
            ).fetchone()
        if cur_row and prev_row:
            cur_total += float(cur_row[0] or 0)
            prev_total += float(prev_row[0] or 0)
            ok += 1

    if ok == 0 or prev_total <= 0:
        # 没有 24h 历史, 至少返回当前值
        if cur_row:
            return float(cur_row[0] or 0), None, None
        return None, None, None
    delta = cur_total - prev_total
    pct = (delta / prev_total * 100) if prev_total > 0 else 0
    return cur_total, delta, pct


def _whale_all_addresses(whale, all_whales):
    """找出一个主鲸 + 所有马甲的合并地址列表"""
    wid = whale.get("id") or whale.get("name", "")
    canonical = _whale_canonical_id(whale)
    if canonical != wid:
        # 是马甲 — 往上找主鲸再合
        primary = _whale_find_by_id(canonical, all_whales)
        if primary:
            return _whale_all_addresses(primary, all_whales), primary
    # 自己是主鲸, 收集所有 alias_of 指向自己的鲸鱼地址
    addrs = [a.lower() for a in whale.get("addresses", []) if a and a.startswith("0x")]
    aliases = []
    for w in all_whales:
        if w.get("alias_of") == wid:
            addrs.extend(a.lower() for a in w.get("addresses", []) if a and a.startswith("0x"))
            aliases.append(w.get("name", w.get("id", "")))
    return addrs, aliases


def cmd_whale(chat_id, args):
    """查询鲸鱼当前仓位 + 24h P&L + 清算距离"""
    conn = _whale_query_conn()
    try:
        whales = load_whale_list()
        active = [w for w in whales if w.get("active", True)]

        if not args:
            # 列表模式: 所有主鲸 summary
            primary_only = [w for w in active if not w.get("alias_of")]
            lines = [f"🐋 <b>鲸鱼总览</b> ({len(primary_only)} 个家族)\n"]
            for w in primary_only:
                wid = w.get("id", w.get("name", "?"))
                emoji = w.get("emoji", "🐋")
                name = w.get("name", wid)
                addrs, aliases = _whale_all_addresses(w, whales)

                # 🔧 v28.0.1: 持仓总市值 = 当前所有仓位的 size_usd 之和
                positions = _whale_current_positions(conn, addrs)
                positions = [p for p in positions if p["size_coin"] > 0]
                total_pos = sum(p["size_usd"] for p in positions)

                cur_val, delta, pct = _whale_pnl_one(conn, addrs)
                has_data = total_pos > 0 or (cur_val is not None and cur_val > 0)

                if has_data:
                    # 优先显示持仓市值 (对频繁清算鲸鱼更直观)
                    if total_pos > 0:
                        val_str = f"{_fmt_whale_size_usd(total_pos)} 持仓"
                    else:
                        val_str = f"{_fmt_whale_size_usd(cur_val)} 账户"
                    if delta is not None:
                        sign = "+" if delta >= 0 else "−"
                        color = "🟢" if delta >= 0 else "🔴"
                        delta_str = f"  {color} 24h {sign}{_fmt_whale_size_usd(abs(delta))} ({sign}{abs(pct):.1f}%)"
                    else:
                        delta_str = ""
                    alias_str = f" +{len(aliases)} 马甲" if aliases else ""
                    pos_cnt = f" · {len(positions)} 仓位" if positions else ""
                    lines.append(f"{emoji} <b>{_esc(name)}</b>{alias_str}  💰 {val_str}{pos_cnt}{delta_str}")
                    lines.append(f"   <i>/whale {wid}</i>")
                else:
                    lines.append(f"{emoji} <b>{_esc(name)}</b>  (数据未就绪)")
                    lines.append(f"   <i>/whale {wid}</i>")
            lines.append("\n💡 用 <code>/whale &lt;id&gt;</code> 查看详情 (例: /whale machi)")
            send_tg_reply(chat_id, "\n".join(lines))
            return

        # 详情模式: 模糊匹配 id 或名字
        query = " ".join(args).strip().lower()
        target = None
        for w in active:
            wid = (w.get("id") or "").lower()
            name = (w.get("name") or "").lower()
            if query == wid or query in wid or query in name:
                # 如果匹配到马甲, 指向主鲸
                canonical = _whale_canonical_id(w)
                if canonical != wid:
                    primary = _whale_find_by_id(canonical, whales)
                    if primary:
                        target = primary
                        break
                target = w
                break

        if not target:
            send_tg_reply(chat_id,
                f"❌ 未找到 '{_esc(query)}'\n\n"
                f"💡 用 /whale (不带参数) 看所有鲸鱼列表")
            return

        # 详情显示
        tid = target.get("id", "?")
        emoji = target.get("emoji", "🐋")
        name = target.get("name", tid)
        twitter = target.get("twitter", "")
        tags = target.get("tags", [])
        story = target.get("story", "")

        addrs, aliases = _whale_all_addresses(target, whales)

        lines = [f"{emoji} <b>{_esc(name)}</b>"]
        if tags:
            lines.append(f"🏷️ {' · '.join(_esc(t) for t in tags[:4])}")
        if twitter:
            lines.append(f"🐦 {_esc(twitter)}")
        if story:
            lines.append(f"📖 <i>{_esc(story[:120])}</i>")
        if aliases:
            lines.append(f"👥 含 {len(aliases)} 个马甲: {', '.join(_esc(a) for a in aliases)}")

        # 当前持仓
        positions = _whale_current_positions(conn, addrs)
        # 过滤掉已平仓的 (size_coin=0)
        positions = [p for p in positions if p["size_coin"] > 0]

        # 🔧 v28.0.1: 总持仓市值 = sum(positions.size_usd). 这比 account_value 更直观
        # (account_value 对频繁清算的鲸鱼会接近 0, 误导)
        total_position_usd = sum(p["size_usd"] for p in positions)

        # 账户 + 24h P&L
        cur_val, delta, pct = _whale_pnl_one(conn, addrs)
        if total_position_usd > 0:
            lines.append(f"\n💰 持仓总市值: <b>{_fmt_whale_size_usd(total_position_usd)}</b>")
            if cur_val is not None and cur_val > 0:
                lines.append(f"🏦 账户余额: {_fmt_whale_size_usd(cur_val)}")
            if delta is not None:
                sign = "+" if delta >= 0 else "−"
                color = "🟢" if delta >= 0 else "🔴"
                lines.append(f"📈 24h: {color} <b>{sign}{_fmt_whale_size_usd(abs(delta))}</b> ({sign}{abs(pct):.1f}%)")
        elif cur_val is not None:
            lines.append(f"\n💰 账户总值: <b>{_fmt_whale_size_usd(cur_val)}</b>")
            if delta is not None:
                sign = "+" if delta >= 0 else "−"
                color = "🟢" if delta >= 0 else "🔴"
                lines.append(f"📈 24h: {color} <b>{sign}{_fmt_whale_size_usd(abs(delta))}</b> ({sign}{abs(pct):.1f}%)")

        if positions:
            # 按 size_usd 排序
            positions.sort(key=lambda p: p["size_usd"], reverse=True)
            lines.append(f"\n📊 <b>当前持仓</b> ({len(positions)} 个):")
            for p in positions[:10]:
                side_emoji = "🟢" if p["side"] == "long" else "🔴"
                side_cn = "多" if p["side"] == "long" else "空"
                size_str = _fmt_whale_size_usd(p["size_usd"])
                lev_str = f" {p['leverage']:.0f}x" if p["leverage"] > 0 else ""
                _, dist_str = _whale_fmt_dist_pct(p)
                pnl = p["unrealized_pnl"]
                if pnl != 0:
                    pnl_sign = "+" if pnl > 0 else "−"
                    pnl_color = "🟢" if pnl > 0 else "🔴"
                    pnl_str = f"  浮{pnl_color}{pnl_sign}{_fmt_whale_size_usd(abs(pnl))}"
                else:
                    pnl_str = ""
                lines.append(f"  {side_emoji} {side_cn} <b>{_esc(p['coin'])}</b> {size_str}{lev_str}  清算{dist_str}{pnl_str}")
            if len(positions) > 10:
                lines.append(f"  <i>... 另 {len(positions) - 10} 个仓位未显示</i>")
        else:
            lines.append(f"\n📊 当前无持仓")

        lines.append(f"\n🔗 hypurrscan.io/address/{addrs[0]}" if addrs else "")
        lines.append(f"📲 开户: {HL_REFERRAL}")

        send_tg_reply(chat_id, "\n".join(lines))
    except Exception as e:
        print(f"[cmd_whale] 错误: {e}")
        import traceback; traceback.print_exc()
        send_tg_reply(chat_id, f"❌ 查询失败: {_esc(str(e)[:100])}")
    finally:
        try: conn.close()
        except Exception: pass


# ============================================================
# 🆕 v28.2 /subscribe /unsubscribe /mysubs (私聊推送订阅)
# ============================================================
def _resolve_whale_query(query, whales):
    """模糊匹配 whale id 或名字, 马甲自动跳主鲸. 返回主鲸 whale dict 或 None"""
    query = query.strip().lower()
    for w in whales:
        wid = (w.get("id") or "").lower()
        name = (w.get("name") or "").lower()
        if query == wid or query in wid or query in name:
            canonical = _whale_canonical_id(w)
            wid_self = w.get("id") or w.get("name", "")
            if canonical != wid_self:
                primary = _whale_find_by_id(canonical, whales)
                if primary:
                    return primary
            return w
    return None


def cmd_subscribe(chat_id, args):
    """订阅鲸鱼, 有新动作时私聊推送"""
    conn = _whale_query_conn()
    try:
        _init_whale_db(conn)
        whales = load_whale_list()
        active = [w for w in whales if w.get("active", True)]
        primary_only = [w for w in active if not w.get("alias_of")]

        if not args:
            # 无参数: 显示可订阅列表 + 用户当前订阅
            my_subs = [r[0] for r in conn.execute(
                "SELECT canonical_id FROM whale_subscriptions WHERE user_chat_id=?",
                (chat_id,)
            ).fetchall()]

            lines = [f"🐋 <b>订阅鲸鱼</b>\n\n"
                     f"📖 用法: <code>/subscribe &lt;id&gt;</code>\n"
                     f"📖 例: <code>/subscribe machi</code>\n"
                     f"📖 取消: <code>/unsubscribe &lt;id&gt;</code>\n\n"
                     f"💡 订阅后该鲸鱼有动作会<b>私聊</b>推送你 (频道仍然广播)\n\n"
                     f"<b>可订阅的鲸鱼:</b>"]
            for w in primary_only:
                wid = w.get("id", "?")
                emoji = w.get("emoji", "🐋")
                name = w.get("name", wid)
                mark = "✅" if wid in my_subs else "⚪"
                lines.append(f"{mark} {emoji} {_esc(name)}  <code>/subscribe {wid}</code>")
            if my_subs:
                lines.append(f"\n✅ = 你已订阅 ({len(my_subs)} 个)")
            lines.append(f"\n查看我订阅的: /mysubs")
            send_tg_reply(chat_id, "\n".join(lines))
            return

        query = " ".join(args)
        target = _resolve_whale_query(query, whales)
        if not target:
            send_tg_reply(chat_id, f"❌ 未找到 '{_esc(query)}'\n用 /subscribe 看完整列表")
            return

        canonical = target.get("id") or target.get("name", "")
        name = target.get("name", canonical)
        emoji = target.get("emoji", "🐋")

        # 插入订阅 (PRIMARY KEY 防重复)
        try:
            conn.execute(
                "INSERT INTO whale_subscriptions (user_chat_id, canonical_id, subscribed_at) "
                "VALUES (?, ?, ?)",
                (chat_id, canonical, _utcnow().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
            send_tg_reply(chat_id,
                f"✅ <b>已订阅</b> {emoji} {_esc(name)}\n\n"
                f"该鲸鱼动作 (开仓/加仓/清算) 会<b>第一时间私聊推送</b>你.\n\n"
                f"查看我的订阅: /mysubs\n取消: /unsubscribe {canonical}")
            print(f"[Subscribe] {chat_id} -> {canonical}")
        except sqlite3.IntegrityError:
            send_tg_reply(chat_id, f"💡 你已经订阅了 {emoji} {_esc(name)}")
    except Exception as e:
        print(f"[cmd_subscribe] 错误: {e}")
        import traceback; traceback.print_exc()
        send_tg_reply(chat_id, f"❌ 订阅失败: {_esc(str(e)[:100])}")
    finally:
        try: conn.close()
        except Exception: pass


def cmd_unsubscribe(chat_id, args):
    """取消订阅"""
    conn = _whale_query_conn()
    try:
        _init_whale_db(conn)  # v28.2.1: 首次调用时自动建表, 避免 'no such table' 错误
        if not args:
            send_tg_reply(chat_id, "用法: /unsubscribe &lt;id&gt;  (或 /unsubscribe all 取消全部)\n查看订阅: /mysubs")
            return
        query = " ".join(args).strip().lower()

        if query == "all":
            n = conn.execute("SELECT COUNT(*) FROM whale_subscriptions WHERE user_chat_id=?",
                             (chat_id,)).fetchone()[0]
            conn.execute("DELETE FROM whale_subscriptions WHERE user_chat_id=?", (chat_id,))
            conn.commit()
            send_tg_reply(chat_id, f"✅ 已取消全部 {n} 个订阅")
            return

        whales = load_whale_list()
        target = _resolve_whale_query(query, whales)
        if not target:
            # 也可能用户传的就是 canonical id
            canonical_guess = query
        else:
            canonical_guess = target.get("id") or target.get("name", "")

        name = target.get("name", canonical_guess) if target else canonical_guess
        emoji = target.get("emoji", "🐋") if target else "🐋"

        cursor = conn.execute(
            "DELETE FROM whale_subscriptions WHERE user_chat_id=? AND canonical_id=?",
            (chat_id, canonical_guess)
        )
        conn.commit()
        if cursor.rowcount > 0:
            send_tg_reply(chat_id, f"✅ 已取消订阅 {emoji} {_esc(name)}")
        else:
            send_tg_reply(chat_id, f"💡 你没有订阅 {emoji} {_esc(name)}")
    except Exception as e:
        print(f"[cmd_unsubscribe] 错误: {e}")
        send_tg_reply(chat_id, f"❌ 取消失败: {_esc(str(e)[:100])}")
    finally:
        try: conn.close()
        except Exception: pass


def cmd_mysubs(chat_id, args):
    """查看我的订阅"""
    conn = _whale_query_conn()
    try:
        _init_whale_db(conn)
        rows = conn.execute(
            "SELECT canonical_id, subscribed_at FROM whale_subscriptions "
            "WHERE user_chat_id=? ORDER BY subscribed_at DESC",
            (chat_id,)
        ).fetchall()
        if not rows:
            send_tg_reply(chat_id,
                "你还没订阅任何鲸鱼.\n\n用 /subscribe 查看可订阅列表")
            return

        whales = load_whale_list()
        lines = [f"🐋 <b>我的订阅</b> ({len(rows)} 个):\n"]
        for canonical, sub_time in rows:
            w = _whale_find_by_id(canonical, whales)
            if w:
                emoji = w.get("emoji", "🐋")
                name = w.get("name", canonical)
                lines.append(f"✅ {emoji} {_esc(name)}  <i>订阅于 {_esc(sub_time[:10])}</i>")
            else:
                lines.append(f"⚠️ {_esc(canonical)} <i>(鲸鱼已不在名单, 建议取消)</i>")
        lines.append(f"\n💡 取消订阅: /unsubscribe &lt;id&gt;")
        lines.append(f"💡 查看鲸鱼详情: /whale &lt;id&gt;")
        send_tg_reply(chat_id, "\n".join(lines))
    except Exception as e:
        print(f"[cmd_mysubs] 错误: {e}")
        send_tg_reply(chat_id, f"❌ 查询失败: {_esc(str(e)[:100])}")
    finally:
        try: conn.close()
        except Exception: pass


def notify_whale_subscribers(conn, canonical_id, alert_msg):
    """
    🆕 v28.2: 给某鲸鱼的所有订阅用户私聊推送告警
    失败静默 (某用户 block 了 bot 不影响其他人)
    🔧 v28.2.1: 表不存在时静默返回 0 (新部署还没人订阅的情况)
              + 检查 HTTP 状态码, 用户 block 自动清理订阅
    conn: 主循环传入的 DB 连接
    """
    try:
        # v28.2.1: 表不存在则静默返回 (没人订阅过)
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='whale_subscriptions' LIMIT 1"
        ).fetchone()
        if not table_exists:
            return 0

        rows = conn.execute(
            "SELECT user_chat_id FROM whale_subscriptions WHERE canonical_id=?",
            (canonical_id,)
        ).fetchall()
        if not rows:
            return 0
        prefix = f"🔔 <i>你订阅的鲸鱼有动作:</i>\n\n"
        pushed = 0
        blocked_users = []  # v28.2.1: 收集 block 用户后续清理
        for (user_id,) in rows:
            try:
                r = requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    json={
                        "chat_id": user_id,
                        "text": prefix + alert_msg,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                    timeout=8
                )
                # v28.2.1: 判断是否被 block (TG 返回 403 "bot was blocked by the user")
                if r.status_code == 200:
                    pushed += 1
                elif r.status_code == 403:
                    # 用户已 block bot, 标记清理
                    blocked_users.append(user_id)
                    print(f"[Notify] 🚫 user={user_id} 已 block bot, 将清理订阅")
                elif r.status_code == 400 and "parse" in r.text.lower():
                    # HTML 解析失败, 降级纯文本重推
                    import re as _re
                    plain = _re.sub(r'<[^>]+>', '', prefix + alert_msg)
                    plain = plain.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
                    r2 = requests.post(
                        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                        json={"chat_id": user_id, "text": plain,
                              "disable_web_page_preview": True},
                        timeout=8
                    )
                    if r2.status_code == 200:
                        pushed += 1
                else:
                    print(f"[Notify] ⚠️ user={user_id} HTTP {r.status_code}: {r.text[:100]}")
                time.sleep(0.1)  # 温柔一点, 避免 TG rate limit
            except Exception as e:
                print(f"[Notify] 私推失败 chat={user_id}: {e}")

        # v28.2.1: 自动清理 block 用户的订阅
        if blocked_users:
            placeholders = ",".join("?" for _ in blocked_users)
            try:
                conn.execute(
                    f"DELETE FROM whale_subscriptions WHERE user_chat_id IN ({placeholders})",
                    blocked_users
                )
                conn.commit()
                print(f"[Notify] 🧹 已清理 {len(blocked_users)} 个 block 用户的订阅")
            except Exception as e:
                print(f"[Notify] 清理 block 用户失败: {e}")

        if pushed > 0:
            print(f"[Notify] ✅ {canonical_id} 私推 {pushed} 个订阅者")
        return pushed
    except Exception as e:
        print(f"[Notify] 错误: {e}")
        return 0


COMMANDS = {
    "/start": cmd_help, "/help": cmd_help, "/about": cmd_about,
    "/top": cmd_top, "/defi": cmd_defi, "/hackathon": cmd_hackathon,
    "/airdrop": cmd_airdrop, "/stats": cmd_stats,
    "/search": cmd_search, "/risk": cmd_risk,
    "/v": cmd_v,  # v26: 尾行标签反查
    "/whale": cmd_whale,  # v28.0: 鲸鱼查询
    "/winrate": cmd_winrate,  # 🆕 v30.12: 赏金哨胜率统计
    "/growth": cmd_growth,  # 🆕 v30.14.16: 频道增长诊断 (admin only)
    "/diagnose": cmd_diagnose,  # 🆕 v30.14.21: 输/赢信号 setup 诊断 (admin only)
    "/pnl": cmd_pnl,  # 🆕 v30.14.31: 纸上交易账户 (admin only)
    "/analyze": cmd_analyze,  # 🆕 v30.14.33: 3 诊断 + Sonnet 深度分析 (admin only)
    "/subscribe": cmd_subscribe,    # v28.2: 订阅
    "/unsubscribe": cmd_unsubscribe, # v28.2
    "/mysubs": cmd_mysubs,          # v28.2
}

def tg_bot_poll_loop():
    """后台线程: 轮询 TG getUpdates 处理命令"""
    if not TELEGRAM_TOKEN:
        print("[Bot] 无 TG token, 命令系统禁用")
        return
    print("[Bot] 🤖 命令监听已启动")
    offset = 0
    while True:
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                params={"offset": offset, "timeout": 25, "allowed_updates": ["message"]},
                timeout=30
            )
            if resp.status_code != 200:
                time.sleep(5)
                continue
            data = resp.json()
            for update in data.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                text = (msg.get("text") or "").strip()
                chat_id = msg.get("chat", {}).get("id")
                if not text or not chat_id or not text.startswith("/"):
                    continue
                # 处理 /command@botname 形式
                parts = text.split()
                cmd = parts[0].split("@")[0].lower()
                args = parts[1:]
                handler = COMMANDS.get(cmd)
                if handler:
                    print(f"[Bot] {chat_id} -> {cmd} {args}")
                    try:
                        handler(chat_id, args)
                    except Exception as e:
                        print(f"[Bot] 命令 {cmd} 错误: {e}")
                        send_tg_reply(chat_id, f"❌ 命令出错: {e}")
        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            print(f"[Bot] 轮询错误: {e}")
            time.sleep(10)


# ============================================================
# 🆕 v28.5: 鲸鱼快速通道 (独立线程, 5 分钟 1 次)
# ============================================================
WHALE_FAST_POLL_INTERVAL = _env_int("WHALE_FAST_POLL_INTERVAL", "300")  # 5 分钟

def whale_fast_poll_loop():
    """
    🆕 v28.5: 鲸鱼独立扫描线程, 5 分钟 1 次 (原本主循环 30 分钟).
    把清算预警时效性从 30min 提升到 5min, bounty 等其他扫描不受影响.
    每个循环独立 SQLite 连接, 不和主循环/bot 线程共用连接.
    """
    print(f"[WhaleFast] 🐋 快速通道已启动 (每 {WHALE_FAST_POLL_INTERVAL // 60} 分钟扫描)")
    # 首次等待一下, 让主循环先跑完, DB 表都建好
    time.sleep(30)
    iteration = 0
    while True:
        iteration += 1
        try:
            conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10.0)
            try:
                conn.execute("PRAGMA busy_timeout = 10000")
            except Exception:
                pass
            try:
                whale_pushed = check_whale_positions(conn)
                if whale_pushed > 0:
                    print(f"[WhaleFast #{iteration}] ✅ 推送 {whale_pushed} 条鲸鱼动作")
            except Exception as e:
                print(f"[WhaleFast] check_whale_positions 错误: {e}")
                import traceback; traceback.print_exc()

            try:
                resonance_pushed = check_whale_resonance(conn)
                if resonance_pushed > 0:
                    print(f"[WhaleFast #{iteration}] ✅ 推送 {resonance_pushed} 条共振告警")
            except Exception as e:
                print(f"[WhaleFast] check_whale_resonance 错误: {e}")

            # 🆕 v29.0: 战绩追推扫描 (4h/24h 后自动复盘)
            # 🆕 v30.13.4: 默认关闭 (麻吉大哥 4h 复盘冗余, 加仓/减仓/橙红警已足够). 改 env=1 可恢复
            if os.getenv("WHALE_FOLLOWUP_ENABLED", "0") == "1":
                try:
                    followup_pushed = check_whale_alert_followups(conn)
                    if followup_pushed > 0:
                        print(f"[WhaleFast #{iteration}] ✅ 推送 {followup_pushed} 条战绩追推")
                except Exception as e:
                    print(f"[WhaleFast] check_whale_alert_followups 错误: {e}")

            conn.close()
        except Exception as e:
            print(f"[WhaleFast] 循环错误: {e}")
            import traceback; traceback.print_exc()

        time.sleep(WHALE_FAST_POLL_INTERVAL)


# ============================================================
# 📊 v24: 每周图表报告
# ============================================================
def generate_weekly_chart(conn, all_b):
    """v24 修复: 只统计 DeFi/CEX 收益, 支持中文标题"""
    if not HAS_MATPLOTLIB:
        print("[Weekly] matplotlib 未安装，跳过图表")
        return

    # 只筛 DeFi/CEX 收益
    defi_all = [b for b in all_b if is_defi(b)]
    if not defi_all:
        print("[Weekly] 无 DeFi 数据, 跳过")
        return

    try:
        # 加载中文字体
        font_path = ensure_chinese_font()
        cn_font = None
        if font_path:
            try:
                font_manager.fontManager.addfont(font_path)
                cn_font = font_manager.FontProperties(fname=font_path)
                plt.rcParams['font.sans-serif'] = [cn_font.get_name()]
                plt.rcParams['axes.unicode_minus'] = False
            except Exception as e:
                print(f"[Weekly] 字体加载失败: {e}")

        title_kw = {'fontproperties': cn_font} if cn_font else {}
        label_kw = {'fontproperties': cn_font} if cn_font else {}

        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        fig.suptitle('每周加密收益报告 Weekly Crypto Yield Report',
                     fontsize=14, fontweight='bold', **title_kw)

        # 1. Top 10 DeFi APY
        defi_sorted = sorted([b for b in defi_all if b.get('apy', 0) > 0],
                              key=lambda x: x['apy'], reverse=True)[:10]
        if defi_sorted:
            names = [f"{(b.get('symbol','') or '?')[:8]}\n{(b.get('org','') or '?')[:10]}" for b in defi_sorted]
            apys = [b['apy'] for b in defi_sorted]
            colors = ['#e74c3c' if a > 50 else '#f39c12' if a > 20 else '#2ecc71' for a in apys]
            axes[0, 0].barh(range(len(names)), apys, color=colors)
            axes[0, 0].set_yticks(range(len(names)))
            axes[0, 0].set_yticklabels(names, fontsize=8, **label_kw)
            axes[0, 0].set_xlabel('APY %', **label_kw)
            axes[0, 0].set_title('Top 10 最高收益 / Highest APY', **title_kw)
            axes[0, 0].invert_yaxis()

        # 2. 协议/平台分布 (只看 DeFi)
        platform_counts = {}
        for b in defi_all:
            p = b.get('org', '') or b.get('s', 'Other')
            if p:
                platform_counts[p] = platform_counts.get(p, 0) + 1
        top_platforms = sorted(platform_counts.items(), key=lambda x: x[1], reverse=True)[:8]
        if top_platforms:
            pnames, pcounts = zip(*top_platforms)
            axes[0, 1].pie(pcounts, labels=pnames, autopct='%1.0f%%',
                           textprops={'fontsize': 8, **({'fontproperties': cn_font} if cn_font else {})})
            axes[0, 1].set_title('协议分布 / Protocol Distribution', **title_kw)

        # 3. 风险分布 (只看 DeFi)
        risk_dist = {i: 0 for i in range(1, 11)}
        for b in defi_all:
            r = score_risk(b)
            risk_dist[r] = risk_dist.get(r, 0) + 1
        risk_labels = ['低\nLow\n1-2', '中低\nMed-L\n3-4', '中\nMed\n5-6', '高\nHigh\n7-8', '极高\nV-High\n9-10']
        risk_values = [
            risk_dist[1] + risk_dist[2],
            risk_dist[3] + risk_dist[4],
            risk_dist[5] + risk_dist[6],
            risk_dist[7] + risk_dist[8],
            risk_dist[9] + risk_dist[10],
        ]
        risk_colors = ['#2ecc71', '#f1c40f', '#e67e22', '#e74c3c', '#8e44ad']
        axes[1, 0].bar(range(len(risk_labels)), risk_values, color=risk_colors)
        axes[1, 0].set_xticks(range(len(risk_labels)))
        axes[1, 0].set_xticklabels(risk_labels, fontsize=8, **label_kw)
        axes[1, 0].set_title('风险分布 / Risk Distribution', **title_kw)
        axes[1, 0].set_ylabel('数量 Count', **label_kw)

        # 4. 各链平均 APY (只看 DeFi)
        chain_apy = {}
        for b in defi_all:
            if b.get('chain'):
                chain_apy.setdefault(b['chain'], []).append(b.get('apy', 0))
        if chain_apy:
            # 过滤掉只有1个池子的链
            top_chains = sorted(
                [(c, sum(a)/len(a)) for c, a in chain_apy.items() if len(a) >= 2],
                key=lambda x: x[1], reverse=True
            )[:10]
            if top_chains:
                cnames, cavgs = zip(*top_chains)
                axes[1, 1].barh(range(len(cnames)), cavgs, color='#3498db')
                axes[1, 1].set_yticks(range(len(cnames)))
                axes[1, 1].set_yticklabels(cnames, fontsize=8, **label_kw)
                axes[1, 1].set_xlabel('平均 APY %', **label_kw)
                axes[1, 1].set_title('各链平均收益 / Chain Avg APY', **title_kw)
                axes[1, 1].invert_yaxis()

        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)

        # 摘要
        defi_count = len(defi_all)
        with_apy = [b for b in defi_all if b.get('apy', 0) > 0]
        avg_apy = sum(b['apy'] for b in with_apy) / max(len(with_apy), 1)
        chains = len(set(b.get('chain', '') for b in defi_all if b.get('chain')))

        caption = (f"📊 每周报告 Weekly Report\n"
                   f"💹 DeFi/CEX 活动: {defi_count}\n"
                   f"📈 平均 APY: {avg_apy:.1f}% | ⛓️ {chains} 条链\n"
                   f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        send_tg_photo(buf.getvalue(), caption)
        print(f"[Weekly] ✅ 图表已发送 (DeFi: {defi_count}, 链: {chains})")
    except Exception as e:
        print(f"[Weekly] ❌ {e}")
        traceback.print_exc()

# ============================================================
# 💱 v24: 稳定币链上流向监控
# ============================================================
def fetch_stablecoin_flows():
    """监控稳定币跨链流向变化"""
    alerts = []
    try:
        resp = fetch_with_retry("https://stablecoins.llama.fi/stablecoins?includePrices=true",
                                headers={"User-Agent": "Mozilla/5.0"})
        if not resp:
            return alerts
        data = resp.json()
        stables = data.get("peggedAssets", [])

        # 只监控大稳定币
        BIG_STABLES = {"USDT", "USDC", "DAI", "USDE", "FDUSD", "GHO", "FRAX", "PYUSD", "USD1", "USDG"}

        for s in stables:
            symbol = s.get("symbol", "").upper()
            if symbol not in BIG_STABLES:
                continue
            name = s.get("name", symbol)
            circulating = s.get("circulating", {})
            total = circulating.get("peggedUSD", 0) or 0
            if total < 1e6:
                continue

            # 链级别变化
            chain_circ = s.get("chainCirculating", {})
            for chain, chain_data in chain_circ.items():
                current = chain_data.get("current", {}).get("peggedUSD", 0) or 0
                if current < 10e6:  # 忽略 < $10M
                    continue

            # 整体 24h 变化
            change_1d = 0
            # DeFiLlama stablecoins API 格式可能不同，做安全处理
            if isinstance(s.get("circulatingPrevDay"), dict):
                prev_day = s["circulatingPrevDay"].get("peggedUSD", 0) or 0
                if prev_day > 0:
                    change_1d = ((total - prev_day) / prev_day) * 100

            # 7d 变化
            change_7d = 0
            if isinstance(s.get("circulatingPrevWeek"), dict):
                prev_week = s["circulatingPrevWeek"].get("peggedUSD", 0) or 0
                if prev_week > 0:
                    change_7d = ((total - prev_week) / prev_week) * 100

            # 显著变化才报 (24h > 3% 或 7d > 10%)
            if abs(change_1d) > 3 or abs(change_7d) > 10:
                direction = "📈 流入 Inflow" if change_1d > 0 else "📉 流出 Outflow"
                alerts.append({
                    "symbol": symbol, "name": name,
                    "total": total, "change_1d": change_1d,
                    "change_7d": change_7d, "direction": direction,
                })

        if alerts:
            print(f"[Stablecoin] ✅ {len(alerts)} 个稳定币异动")
        else:
            print(f"[Stablecoin] ✅ 无显著异动")
    except Exception as e:
        print(f"[Stablecoin] ❌ {e}")
    return alerts

def send_stablecoin_alerts(conn, alerts):
    if not alerts:
        return
    # v25: 按 symbol + 变动幅度桶去重 (6h 冷却)
    fresh = []
    for a in alerts:
        bucket = int(abs(a['change_1d']) / 2) * 2  # 2%一档
        key = f"{a['symbol']}-{bucket}"
        if is_alerted(conn, "stablecoin", key, hours=6):
            continue
        mark_alerted(conn, "stablecoin", key)
        fresh.append(a)
    if not fresh:
        print("[Stablecoin] 已去重, 无新报警")
        return
    msg = "💱 稳定币异动 Stablecoin Flow Alert\n\n"
    top = sorted(fresh, key=lambda x: abs(x['change_1d']), reverse=True)[:5]
    for a in top:
        supply_str = f"${a['total']/1e9:.2f}B"
        ch_1d_str = f"{a['change_1d']:+.2f}%"
        msg += f"{a['direction']} {_esc(a['symbol'])}\n"
        msg += f"💰 Supply: {_b(supply_str)}\n"
        msg += f"📅 24h: {_b(ch_1d_str)}"
        if a['change_7d']:
            ch_7d_str = f"{a['change_7d']:+.2f}%"
            msg += f" | 7d: {_b(ch_7d_str)}"
        msg += "\n\n"
    try:
        if top:
            lead = top[0]
            tail = tail_for_alert("stableflow", lead['symbol'],
                v=int(abs(lead.get('change_1d', 0)) * 100),
                r=min(10, int(abs(lead.get('change_1d', 0)) / 2)),
                src=lead['symbol'],
                extra={"total": lead.get('total'), "batch_size": len(top)})
            msg += tail
    except Exception as e:
        print(f"[Tail] stableflow error: {e}")
    send_tg(msg.strip())

# ============================================================
# 🪂 v24: Airdrop 监控 (DeFiLlama 新协议追踪)
# ============================================================
def fetch_new_protocols():
    """监控 DeFiLlama 新上线协议 (潜在空投机会)"""
    results = []
    try:
        resp = fetch_with_retry("https://api.llama.fi/protocols",
                                headers={"User-Agent": "Mozilla/5.0"})
        if not resp:
            return results
        protocols = resp.json()
        if not isinstance(protocols, list):
            return results

        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)

        for p in protocols:
            # 检查是否有 listed 时间
            listed_at = p.get("listedAt")
            if not listed_at:
                continue
            try:
                listed_dt = datetime.fromtimestamp(listed_at, tz=timezone.utc)
            except (ValueError, TypeError, OSError):
                continue

            # 只看7天内新上线的
            if listed_dt < seven_days_ago:
                continue

            name = p.get("name", "Unknown")
            tvl = p.get("tvl", 0) or 0
            category = p.get("category", "")
            chains = p.get("chains", [])
            slug = p.get("slug", name.lower().replace(" ", "-"))
            change_1d = p.get("change_1d") or 0
            change_7d = p.get("change_7d") or 0

            # 只关注有一定 TVL 的
            if tvl < 100000:
                continue

            # v24 修复: 检查 symbol/gecko_id/cmcId 综合判断是否已发币
            symbol = (p.get("symbol", "") or "").strip()
            gecko_id = p.get("gecko_id")
            cmc_id = p.get("cmcId")
            # "-" 或空 = 无代币
            has_token = bool(
                (symbol and symbol != "-") or gecko_id or cmc_id
            )

            # 空投信号检测
            airdrop_signals = []
            desc = (p.get("description", "") or "").lower()
            if any(w in desc for w in ["airdrop", "points", "rewards", "incentive", "campaign"]):
                airdrop_signals.append("🎯 描述提到奖励/积分")
            if tvl > 10e6 and change_7d > 50:
                airdrop_signals.append("🚀 TVL 快速增长")
            if not has_token:
                airdrop_signals.append("🪙 无代币 (潜在空投)")
            if category in ("Liquid Staking", "Restaking", "Lending", "CDP", "Bridge"):
                airdrop_signals.append(f"📂 热门赛道: {category}")

            results.append({
                "name": name,
                "tvl": tvl,
                "category": category,
                "chains": chains[:5],
                "slug": slug,
                "listed_dt": listed_dt.strftime("%Y-%m-%d"),
                "change_1d": change_1d,
                "change_7d": change_7d,
                "has_token": has_token,
                "symbol": symbol if has_token else "",
                "airdrop_signals": airdrop_signals,
                "url": f"https://defillama.com/protocol/{slug}",
            })

        results.sort(key=lambda x: x['tvl'], reverse=True)
        print(f"[Airdrop] ✅ {len(results)} 个新协议 (7天内)")
    except Exception as e:
        print(f"[Airdrop] ❌ {e}")
    return results

def send_airdrop_alerts(conn, new_protocols):
    if not new_protocols:
        return
    # 过滤已通知过的
    fresh = []
    for p in new_protocols:
        slug = p.get('slug', '')
        if not slug:
            continue
        already = conn.execute("SELECT 1 FROM airdrop_alerts WHERE slug=?", (slug,)).fetchone()
        if not already:
            fresh.append(p)

    if not fresh:
        print(f"[Airdrop] 无新协议待通知 (全部已推送过)")
        return

    # 优先有空投信号的
    with_signals = [p for p in fresh if p['airdrop_signals']]
    without_signals = [p for p in fresh if not p['airdrop_signals']]
    to_push = (with_signals + without_signals)[:8]

    msg = "🪂 新协议追踪 New Protocol Alert\n"
    msg += "可能的空投/早期参与机会 Potential Airdrop\n\n"

    for p in to_push:
        token_tag = "🪙 无代币 No Token" if not p['has_token'] else "✅ 已发币"
        tvl_str = f"${p['tvl']/1e6:.1f}M"
        msg += f"📌 {_esc(p['name'])} | {token_tag}\n"
        msg += f"💰 TVL: {_b(tvl_str)}"
        if p['change_7d']:
            ch_str = f"{p['change_7d']:+.0f}%"
            msg += f" (7d: {_b(ch_str)})"
        msg += "\n"
        chains_str = ', '.join(p['chains'][:3])
        msg += f"📂 {_esc(p['category'])} | ⛓️ {_esc(chains_str)}\n"
        msg += f"📅 上线 Listed: {_esc(p['listed_dt'])}\n"
        if p['airdrop_signals']:
            signals_str = " | ".join(p['airdrop_signals'][:2])
            msg += f"🎯 {_esc(signals_str)}\n"
        msg += f"🔗 {_esc(p['url'])}\n\n"

    try:
        if to_push:
            lead = to_push[0]
            tail = tail_for_alert("airdrop", lead.get('slug', lead['name']),
                v=int(lead.get('tvl', 0) / 1e6),
                r=3 if lead.get('has_token') else 5,
                src=lead['name'],
                extra={"batch_size": len(to_push), "has_token": lead.get('has_token'),
                       "category": lead.get('category')})
            msg += tail
    except Exception as e:
        print(f"[Tail] airdrop error: {e}")

    send_tg(msg.strip())

    # 标记为已推送
    for p in to_push:
        try:
            conn.execute("INSERT OR IGNORE INTO airdrop_alerts (slug) VALUES (?)", (p['slug'],))
        except Exception:
            pass
    conn.commit()
    print(f"[Airdrop] ✅ 推送 {len(to_push)} 个新协议")

# ============================================================
# 通用工具
# ============================================================
def detect_type(title, desc=""):
    text = (title + " " + desc).lower()
    RULES = [
        (["security", "audit", "vulnerability", "bug bounty", "exploit"], "安全"),
        (["frontend", "ui", "react", "vue", "css"], "前端"),
        (["backend", "api", "server", "database"], "后端"),
        (["content", "write", "article", "blog", "document"], "内容"),
        (["design", "figma", "graphic"], "设计"),
        (["hackathon", "competition"], "黑客松"),
    ]
    for keywords, label in RULES:
        if any(k in text for k in keywords):
            return label
    return "其他"

def detect_region(title, desc="", org=""):
    text = (title + " " + desc + " " + org).lower()
    RULES = [
        (["india", "indian", "bangalore", "mumbai"], "🇮🇳 印度"),
        (["usa", "united states", "america", "new york", "sf", "silicon valley"], "🇺🇸 美国"),
        (["uk", "united kingdom", "london", "british"], "🇬🇧 英国"),
        (["latam", "latin america", "brazil", "mexico", "argentina"], "🌎 拉美"),
        (["asia", "singapore", "vietnam", "indonesia", "philippines"], "🌏 亚洲"),
        (["europe", "germany", "france", "spain"], "🇪🇺 欧洲"),
    ]
    for keywords, label in RULES:
        if any(k in text for k in keywords):
            return label
    return "🌍 全球"

# ============================================================
# 数据源: Immunefi
# ============================================================
def fetch_immunefi():
    results = []
    url = "https://raw.githubusercontent.com/infosec-us-team/Immunefi-Bug-Bounty-Programs-Unofficial/main/projects.json"
    try:
        resp = fetch_with_retry(url)
        if not resp:
            return results
        data = resp.json()
        items = data if isinstance(data, list) else []
        for item in items:
            project = item.get("project", item.get("id", "Unknown"))
            max_bounty = item.get("maximumBounty", 0) or 0
            slug = item.get("id", item.get("slug", ""))
            try:
                bounty = int(max_bounty)
            except (ValueError, TypeError):
                bounty = 0
            results.append({
                "t": project, "v": bounty,
                "u": f"https://immunefi.com/bug-bounty/{slug}/",
                "s": "Immunefi", "type": "安全", "region": "🌍 全球",
                "app": 0, "org": project, "deadline": ""
            })
        print(f"[Immunefi] ✅ {len(results)} 个")
    except Exception as e:
        print(f"[Immunefi] ❌ {e}")
    return results

# ============================================================
# 数据源: Superteam
# ============================================================
def fetch_superteam():
    results = []
    try:
        resp = fetch_with_retry("https://earn.superteam.fun/api/listings",
                                params={"type": "bounty", "isWinnersAnnounced": "false"})
        if not resp:
            return results
        data = resp.json()
        for item in data:
            value = item.get("rewardAmount") or 0
            slug = item.get("slug", "")
            title = item.get("title", "Unknown")
            org = item.get("sponsor", {}).get("name", "") if isinstance(item.get("sponsor"), dict) else ""
            deadline = item.get("deadline", "")[:10] if item.get("deadline") else ""
            submissions = item.get("_count", {}).get("Submission", 0) if isinstance(item.get("_count"), dict) else 0
            results.append({
                "t": title, "v": int(value),
                "u": f"https://earn.superteam.fun/listings/bounties/{slug}",
                "s": "Superteam", "type": detect_type(title),
                "region": detect_region(title, org),
                "app": submissions, "org": org, "deadline": deadline
            })
        print(f"[Superteam] ✅ {len(results)} 个")
    except Exception as e:
        print(f"[Superteam] ❌ {e}")
    return results

# ============================================================
# 数据源: HackerOne (Web3 过滤)
# ============================================================
WEB3_KEYWORDS = [
    "blockchain", "crypto", "web3", "defi", "smart contract", "ethereum",
    "solidity", "bitcoin", "btc", "nft", "dao", "dapp", "cryptocurrency",
    "wallet", "layer 2", "rollup", "zk", "token", "staking",
]

def fetch_hackerone():
    """v25+: HackerOne public programs, 过滤 Web3 相关"""
    results = []
    if not HACKERONE_USER or not HACKERONE_TOKEN:
        print("[HackerOne] ⚠️ 未配置 HACKERONE_USER/TOKEN, 跳过")
        return results
    try:
        # 分页抓取 public 项目
        url = "https://api.hackerone.com/v1/hackers/programs"
        all_programs = []
        page = 1
        while page <= 5:  # 最多 5 页 (~500 programs, 防止失控)
            resp = fetch_with_retry(
                url,
                auth=(HACKERONE_USER, HACKERONE_TOKEN),
                headers={"Accept": "application/json"},
                params={"page[number]": page, "page[size]": 100},
                timeout=15,
            )
            if not resp:
                break
            data = resp.json()
            programs = data.get("data", []) or []
            if not programs:
                break
            all_programs.extend(programs)
            # 最后一页
            links = data.get("links", {}) or {}
            if not links.get("next"):
                break
            page += 1

        for p in all_programs:
            attrs = p.get("attributes", {}) or {}
            # 只要公开 + 开放提交 + 提供 bounty
            if attrs.get("state") != "public_mode":
                continue
            if attrs.get("submission_state") != "open":
                continue
            if not attrs.get("offers_bounties"):
                continue

            handle = attrs.get("handle", "")
            name = attrs.get("name", handle)
            policy = (attrs.get("policy", "") or "").lower()
            combined = f"{name} {handle} {policy}".lower()

            # Web3 关键词过滤
            if not any(kw in combined for kw in WEB3_KEYWORDS):
                continue

            results.append({
                "t": name[:80],
                "v": 0,  # HackerOne 不直接给 bounty 金额
                "u": f"https://hackerone.com/{handle}",
                "s": "HackerOne",
                "type": "Security Bounty",
                "region": "🌍 全球",
                "app": 0,
                "org": name,
                "deadline": "",
            })
        print(f"[HackerOne] ✅ {len(results)} 个 Web3 相关 (共扫描 {len(all_programs)})")
    except Exception as e:
        print(f"[HackerOne] ❌ {e}")
    return results

# ============================================================
# ============================================================
# 数据源: HackenProof (Web3 审计赏金)
# ============================================================
def fetch_hackenproof():
    """
    HackenProof: Web3 审计赏金
    🆕 v29.0.1 修复 (反爬升级 + HTML 改版):
      - 用 smart_scrape (统一 fallback: requests → Jina → Firecrawl)
      - 兼容 HTML 链接 + Markdown 链接 [text](path) 两种格式
      - 宽松 regex: 同时匹配 /programs/X 和 /vendor/program 两种结构
      - 多个候选 URL 都试
    """
    results = []
    try:
        # 多个候选 entry URL — 改版后可能新结构
        entry_urls = [
            "https://hackenproof.com/programs",
            "https://hackenproof.com/programs?type=public",
        ]
        html = ""
        for url in entry_urls:
            html = smart_scrape(url, min_chars=500)
            if html and len(html) >= 500:
                break

        if not html or len(html) < 500:
            print("[HackenProof] ⚠️ 三层抓取都失败 (反爬 / 网站改版)")
            return results

        # 提取候选 program path. 兼容多种格式:
        #   1) HTML href: href="/programs/foo" 或 href="https://hackenproof.com/programs/foo"
        #   2) Markdown: [Foo Protocol](/programs/foo) 或 (https://hackenproof.com/programs/foo)
        #   3) 旧两段格式: hackenproof.com/category/program
        candidates = set()
        # 模式 A: 完整 URL
        for m in re.finditer(r'https?://hackenproof\.com(/[a-z0-9\-/]+)', html, re.IGNORECASE):
            candidates.add(m.group(1).rstrip('/'))
        # 模式 B: 相对路径 /programs/X 或 /program/X
        for m in re.finditer(r'(?:href=["\']|\]\()(/programs?/[a-z0-9\-]+)', html, re.IGNORECASE):
            candidates.add(m.group(1).rstrip('/'))

        # 过滤
        skip_paths = {'/programs', '/program', '/about', '/contact', '/terms', '/privacy',
                      '/login', '/register', '/hackers', '/faq', '/blog', '/pricing'}
        paths = []
        for c in candidates:
            if c.lower() in skip_paths:
                continue
            # 至少要有 2 段且不太长
            parts = [p for p in c.split('/') if p]
            if not parts or len(parts) > 4:
                continue
            paths.append(c)

        # 限制处理数量
        paths = list(dict.fromkeys(paths))[:30]

        if not paths:
            print(f"[HackenProof] ⚠️ 抓到内容但解析 0 条 path (HTML 长度 {len(html)})")
            return results

        for path in paths:
            full_url = f"https://hackenproof.com{path}"
            # 在 html 里找 path 附近的文字作为标题/奖金的上下文
            idx = html.find(path)
            block = html[max(0, idx-100):idx+500] if idx >= 0 else ""
            text = re.sub(r'<[^>]+>', ' ', block)
            text = re.sub(r'\s+', ' ', text)

            # 标题: path 末段 → 美化
            slug = [p for p in path.split('/') if p][-1]
            title = slug.replace('-', ' ').replace('_', ' ').title()

            # 奖金: 找 $X 或 X USD
            prize = 0
            prize_m = re.search(r'\$\s*([\d,]+(?:\.\d+)?)\s*(k|m|mil|million|thousand)?\b',
                                text, re.IGNORECASE)
            if prize_m:
                num_str = prize_m.group(1).replace(',', '')
                unit = (prize_m.group(2) or '').lower()
                try:
                    val = float(num_str)
                    if unit in ('m', 'mil', 'million'):
                        val *= 1_000_000
                    elif unit in ('k', 'thousand'):
                        val *= 1_000
                    prize = int(val)
                except Exception:
                    pass
            if 0 < prize < 100:
                prize = 0

            results.append({
                "t": title[:80], "v": prize,
                "u": full_url, "s": "HackenProof", "type": "Security Bounty",
                "region": "🌍 全球", "app": 0, "org": title[:40], "deadline": ""
            })

        print(f"[HackenProof] ✅ {len(results)} 个")
    except Exception as e:
        print(f"[HackenProof] ❌ {e}")
        import traceback; traceback.print_exc()
    return results

# ============================================================
# 数据源: Cantina (竞争性审计竞赛)
# ============================================================
def fetch_cantina():
    """Cantina: 审计竞赛 (SSR 页面, 直接 HTML 解析)"""
    results = []
    try:
        resp = fetch_with_retry("https://cantina.xyz/competitions", timeout=10,
                                headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"})
        html = resp.text if resp else ""
        if len(html) < 500:
            html = jina_reader("https://cantina.xyz/competitions") or ""
        if len(html) < 500:
            html = firecrawl_scrape("https://cantina.xyz/competitions") or ""
        if not html:
            print("[Cantina] ⚠️ 无法抓取内容")
            return results

        # 找竞赛链接 + 标题 + 奖金 (从 HTML 或 markdown)
        # HTML 模式: <a href="/competitions/UUID">... title ... $50,000 ... </a>
        # 找所有竞赛 URL
        urls = re.findall(r'https://cantina\.xyz/competitions/([a-f0-9\-]{20,})', html)
        urls = list(dict.fromkeys(urls))  # 去重保序

        for uid in urls:
            full_url = f"https://cantina.xyz/competitions/{uid}"
            # 找 URL 周围的文本块
            idx = html.find(uid)
            if idx == -1:
                continue
            block = html[idx:idx+800]
            # 清理 HTML 标签
            text = re.sub(r'<[^>]+>', ' ', block)
            text = re.sub(r'\s+', ' ', text)

            # 提取标题: ## 后或 title 附近的短文本
            title_m = re.search(r'##\s*(.{3,60}?)(?:\n|$)', block) or \
                      re.search(r'title["\s>]+([^<"]{3,60})', block, re.IGNORECASE)
            title = title_m.group(1).strip() if title_m else uid[:20]

            # 提取奖金
            prize_m = re.search(r'\\?\$?([\d,]+)\s*(?:in\s+)?(?:USD|USDC)', text, re.IGNORECASE)
            prize = 0
            if prize_m:
                digits = re.sub(r'[^\d]', '', prize_m.group(1))
                prize = int(digits) if digits else 0

            results.append({
                "t": title[:80], "v": prize,
                "u": full_url, "s": "Cantina", "type": "Audit Contest",
                "region": "🌍 全球", "app": 0, "org": "Cantina", "deadline": ""
            })

        print(f"[Cantina] ✅ {len(results)} 个")
    except Exception as e:
        print(f"[Cantina] ❌ {e}")
    return results

# ============================================================
# 数据源: Code4rena (审计竞赛)
# ============================================================
def fetch_code4rena():
    """Code4rena: 审计竞赛 (SSR 页面, 直接 HTML 解析)"""
    results = []
    try:
        resp = fetch_with_retry("https://code4rena.com/audits", timeout=10,
                                headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"})
        html = resp.text if resp else ""
        if len(html) < 1000:
            html = jina_reader("https://code4rena.com/audits") or ""
        if len(html) < 1000:
            html = firecrawl_scrape("https://code4rena.com/audits") or ""
        if not html:
            print("[Code4rena] ⚠️ 无法抓取内容")
            return results

        # 找审计链接: /audits/YYYY-MM-slug
        slugs = re.findall(r'(?:href=["\']|https://code4rena\.com)(/audits/\d{4}-\d{2}-[a-z0-9\-]+)', html)
        slugs = list(dict.fromkeys(slugs))  # 去重保序

        for slug in slugs:
            full_url = f"https://code4rena.com{slug}"
            idx = html.find(slug)
            if idx == -1:
                continue
            # 拿链接后方的文本块 (奖金在 slug 后面)
            block = html[idx:idx+800]
            text = re.sub(r'<[^>]+>', ' ', block)
            text = re.sub(r'\s+', ' ', text)

            # 标题: slug 转可读 (2026-04-intuition-mitigation-review → Intuition Mitigation Review)
            slug_parts = slug.split('/')[-1].split('-')[2:]  # 去掉 year-month
            title_from_slug = ' '.join(w.capitalize() for w in slug_parts)

            # 更好的标题: 从周围 HTML 提取
            title_m = re.search(r'(?:##|<h[23][^>]*>)\s*(.{3,80}?)(?:\n|<)', block)
            title = title_m.group(1).strip() if title_m else title_from_slug

            # 奖金: $XX,XXX in USDC
            prize_m = re.search(r'\\?\$?([\d,]+)\s*(?:in\s+)?(?:USD|USDC)', text, re.IGNORECASE)
            prize = 0
            if prize_m:
                digits = re.sub(r'[^\d]', '', prize_m.group(1))
                prize = int(digits) if digits else 0

            # 日期
            date_m = re.search(r'(\d{1,2}\s+\w{3}).*?[-–]\s*(\d{1,2}\s+\w{3}\s+\d{4}|\d{1,2}\s+\w{3})', text)
            deadline = ""
            if date_m:
                deadline = date_m.group(2).strip()

            results.append({
                "t": title[:80], "v": prize,
                "u": full_url, "s": "Code4rena", "type": "Audit Contest",
                "region": "🌍 全球", "app": 0, "org": "Code4rena",
                "deadline": deadline
            })

        print(f"[Code4rena] ✅ {len(results)} 个")
    except Exception as e:
        print(f"[Code4rena] ❌ {e}")
    return results

# ============================================================
# 数据源: Bountycaster (Farcaster 原生赏金)
# ============================================================
def fetch_bountycaster():
    """Bountycaster: Farcaster 生态赏金 (试 API → Jina fallback)"""
    results = []
    try:
        # 1. 试 API
        data = None
        resp = fetch_with_retry(
            "https://www.bountycaster.xyz/api/bounties",
            params={"status": "open", "limit": 20},
            timeout=10,
        )
        if resp and resp.headers.get("content-type", "").startswith("application/json"):
            try:
                data = resp.json()
            except Exception:
                pass

        if data and isinstance(data, (list, dict)):
            items = data if isinstance(data, list) else data.get("data", data.get("bounties", []))
            if not isinstance(items, list):
                items = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                title = item.get("title") or item.get("text") or item.get("name") or ""
                if not title:
                    continue
                bid = item.get("id") or item.get("uid") or ""
                reward = 0
                currency = "USD"
                for k in ["reward", "amount", "bountyAmount", "prize"]:
                    raw = item.get(k)
                    if raw:
                        try:
                            reward = int(float(str(raw).replace(",", "").replace("$", "")))
                        except Exception:
                            pass
                        if reward > 0:
                            break
                # 货币检测
                cur = item.get("currency") or item.get("token") or ""
                if cur:
                    currency = str(cur).upper()
                url = item.get("url") or f"https://www.bountycaster.xyz/bounty/{bid}"
                results.append({
                    "t": title[:80], "v": reward,
                    "u": url, "s": "Bountycaster", "type": "Farcaster Bounty",
                    "region": "🌍 全球", "app": 0,
                    "org": "Farcaster", "deadline": "",
                    "currency": currency,
                })
            print(f"[Bountycaster] ✅ {len(results)} 个 (API)")
        else:
            # 2. Jina fallback
            md = jina_reader("https://www.bountycaster.xyz")
            if not md:
                md = firecrawl_scrape("https://www.bountycaster.xyz") or ""
            if md:
                for m in re.finditer(
                    r'\[([^\]]{3,100})\]\((https://(?:www\.)?bountycaster\.xyz/bounty/[^\)]+)\)',
                    md
                ):
                    title, url = m.group(1), m.group(2)
                    context = md[m.end():m.end()+200]
                    reward_m = re.search(r'([\d.]+)\s*(USDC|ETH|USD)', context, re.IGNORECASE)
                    reward = 0
                    currency = "USD"
                    if reward_m:
                        try:
                            reward = int(float(reward_m.group(1)))
                        except Exception:
                            pass
                        currency = reward_m.group(2).upper()
                    results.append({
                        "t": title[:80], "v": reward,
                        "u": url, "s": "Bountycaster", "type": "Farcaster Bounty",
                        "region": "🌍 全球", "app": 0,
                        "org": "Farcaster", "deadline": "",
                        "currency": currency,
                    })
                seen = set()
                results = [r for r in results if not (r['u'] in seen or seen.add(r['u']))]
            print(f"[Bountycaster] ✅ {len(results)} 个 (Jina)")
    except Exception as e:
        print(f"[Bountycaster] ❌ {e}")
    return results

# ============================================================
# 数据源: GitHub
# ============================================================
def fetch_github():
    """v25: 使用 GITHUB_TOKEN + 合并查询降低限速"""
    results = []
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    # 合并查询: 一次请求覆盖所有关键词 (OR)
    query = '("bug bounty" OR "security bounty" OR "web3 bounty" OR "crypto bounty") in:title,body state:open'
    try:
        resp = fetch_with_retry(
            "https://api.github.com/search/issues",
            params={"q": query, "sort": "created", "order": "desc", "per_page": 100},
            headers=headers,
        )
        if not resp:
            print(f"[GitHub] ⚠️ 请求失败 (有 token: {bool(GITHUB_TOKEN)})")
            return results
        data = resp.json()
        for item in data.get("items", []):
            title = item.get("title", "")
            body = item.get("body", "") or ""
            url = item.get("html_url", "")
            value = 0
            matches = re.findall(r'\$[\d,]+(?:\.\d+)?|\d+\s*(?:USDC|USDT|USD|DAI)', f"{title} {body}")
            for m in matches:
                num = re.sub(r'[^\d]', '', m)
                if num:
                    value = max(value, int(num))
            repo = item.get("repository_url", "").split("/")[-1] if item.get("repository_url") else ""
            results.append({
                "t": title[:80], "v": value, "u": url,
                "s": "GitHub", "type": detect_type(title),
                "region": "🌍 全球", "app": item.get("comments", 0),
                "org": repo, "deadline": ""
            })
    except Exception as e:
        print(f"[GitHub] ❌ {e}")

    seen_urls = set()
    unique = [r for r in results if not (r['u'] in seen_urls or seen_urls.add(r['u']))]
    print(f"[GitHub] ✅ {len(unique)} 个 (token: {'✓' if GITHUB_TOKEN else '✗'})")
    return unique

# ============================================================
# 数据源: Devpost
# ============================================================
def fetch_devpost():
    results = []
    try:
        resp = fetch_with_retry("https://devpost.com/api/hackathons",
                                params={"status": "open", "order_by": "prize-amount"})
        if not resp:
            return results
        # v25+: Devpost 偶尔返回 HTML 而非 JSON
        ct = resp.headers.get("content-type", "")
        if "json" not in ct:
            print(f"[Devpost] ⚠️ 非 JSON 响应, 跳过 (content-type: {ct[:40]})")
            return results
        data = resp.json()
        for item in data.get("hackathons", []):
            title = item.get("title", "")
            prize_str = item.get("prize_amount", "$0")
            digits = re.sub(r'[^\d]', '', prize_str)
            prize = int(digits) if digits else 0
            url = item.get("url", "")
            org = item.get("organization_name", "")
            deadline = item.get("submission_period_dates", "").split(" - ")[-1] if item.get("submission_period_dates") else ""
            results.append({
                "t": title, "v": prize, "u": url,
                "s": "Devpost", "type": "Hackathon",
                "region": detect_region(title, org),
                "app": item.get("submissions_count", 0),
                "org": org, "deadline": deadline
            })
        print(f"[Devpost] ✅ {len(results)} 个")
    except Exception as e:
        print(f"[Devpost] ❌ {e}")
    return results

# ============================================================
# 数据源: DoraHacks
# ============================================================
def fetch_dorahacks_hackathon():
    """v25 fix: 不再因 prize=0 过滤, 保留所有正在进行的黑客松"""
    results = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json", "Referer": "https://dorahacks.io/hackathon"
        }
        resp = fetch_with_retry("https://dorahacks.io/api/hackathon/",
                                params={"page": 1, "page_size": 50}, headers=headers)
        if not resp:
            return results
        data = resp.json()
        if isinstance(data, dict):
            items = data.get("results", data.get("data", []))
        elif isinstance(data, list):
            items = data
        else:
            items = []

        for item in items:
            if not isinstance(item, dict):
                continue
            title = item.get("title") or item.get("name") or item.get("hackathon_name") or ""
            if not title:
                continue

            # v25: 扩展奖金字段尝试
            prize_raw = (item.get("prize_pool") or item.get("bonus_price") or
                         item.get("total_prize") or item.get("reward") or item.get("awards") or
                         item.get("bounty_amount") or item.get("prizes_total") or
                         item.get("total_award") or item.get("total_bounty") or
                         item.get("prize") or 0)
            try:
                prize = int(float(str(prize_raw).replace(",", "").replace("$", "").strip() or 0))
            except (ValueError, TypeError):
                prize = 0

            hack_id = item.get("id") or item.get("slug") or ""
            org_data = item.get("organization") or item.get("org") or {}
            org = (org_data.get("name", "") if isinstance(org_data, dict)
                   else str(org_data) if org_data else "")
            hackers = item.get("hackers_count") or item.get("participant_count") or item.get("participants") or 0

            # 时间 (v25: DoraHacks API 返回的是 Unix 时间戳整数)
            def _ts_to_date(v):
                """Unix 时间戳 或 ISO 字符串 → YYYY-MM-DD"""
                if not v:
                    return ""
                try:
                    if isinstance(v, (int, float)) and v > 1000000000:
                        return datetime.fromtimestamp(v).strftime("%Y-%m-%d")
                    if isinstance(v, str) and len(v) >= 10:
                        return v[:10].replace("/", "-")
                except (ValueError, TypeError, OSError):
                    pass
                return ""

            end_time_raw = (item.get("end_time") or item.get("vote_end_time") or
                            item.get("submit_end_time") or item.get("deadline") or "")
            start_time_raw = item.get("start_time") or item.get("submit_start_time") or ""
            deadline = _ts_to_date(end_time_raw)
            start = _ts_to_date(start_time_raw)
            end_time = deadline  # 兼容下游

            # v25 fix: 过滤已截止的黑客松
            if deadline:
                try:
                    dl_dt = datetime.strptime(deadline[:10].replace('/', '-'), "%Y-%m-%d")
                    if dl_dt.date() < datetime.now().date():
                        continue
                except (ValueError, TypeError):
                    pass

            # 状态/标签
            status = item.get("status") or item.get("state") or ""
            tags = item.get("tags") or item.get("categories") or []
            if isinstance(tags, list):
                tag_str = " · ".join(str(t.get("name") if isinstance(t, dict) else t) for t in tags[:3])
            else:
                tag_str = str(tags)[:40] if tags else ""

            # v25 fix: 通过 status/state 过滤已结束的黑客松
            status_lower = str(status).lower()
            if any(k in status_lower for k in ["ended", "closed", "finished", "completed", "past", "expired"]):
                continue

            # v25 fix: 数字 state - 常见含义: 0=未开始, 1/2=报名/提交中, 3=评审, 4/5=结束
            try:
                state_num = int(status)
                if state_num >= 3:
                    continue
            except (ValueError, TypeError):
                pass

            # v25 fix: winner_announced=True 说明已颁奖
            if item.get("winner_announced") is True:
                continue

            # v25 fix: submit_end_time (也是 Unix 时间戳)
            submit_end_raw = item.get("submit_end_time") or item.get("submission_end_time")
            submit_end = _ts_to_date(submit_end_raw)
            if submit_end:
                try:
                    se_dt = datetime.strptime(submit_end, "%Y-%m-%d")
                    if se_dt.date() < datetime.now().date():
                        continue
                    # 提交截止更准确 (vs showcase 日期)
                    deadline = submit_end
                except (ValueError, TypeError):
                    pass

            results.append({
                "t": title, "v": prize,
                "u": f"https://dorahacks.io/hackathon/{hack_id}" if hack_id else "https://dorahacks.io/hackathon",
                "s": "DoraHacks", "type": "Hackathon",
                "region": detect_region(title, org),
                "app": hackers, "org": org or tag_str,
                "deadline": deadline, "start": start,
                "status": status, "tags": tag_str,
            })

        # v25: 不再用 >300 过滤, 而是统计
        with_prize = sum(1 for r in results if r['v'] >= 300)
        no_prize = sum(1 for r in results if r['v'] == 0)
        print(f"[DoraHacks] ✅ {len(results)} 个 (有奖金: {with_prize}, 无公开奖金: {no_prize})")
    except Exception as e:
        print(f"[DoraHacks] ❌ {e}")
    return results

# ============================================================
# 数据源: HackQuest
# ============================================================
def fetch_hackquest():
    results = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        }
        resp = fetch_with_retry("https://www.hackquest.io/hackathons", headers=headers)
        if not resp:
            return results
        html = resp.text

        # v25+: Firecrawl fallback (JS 渲染页面抓不到内容时)
        if len(html) < 500:
            fc = firecrawl_scrape("https://www.hackquest.io/hackathons")
            if fc:
                html = fc

        # 方法1: __NEXT_DATA__
        next_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
        if next_match:
            nd = json.loads(next_match.group(1))
            page_props = nd.get("props", {}).get("pageProps", {})
            hackathons = page_props.get("hackathons") or []
            if not hackathons and isinstance(page_props.get("data"), dict):
                hackathons = page_props["data"].get("hackathons") or []
            for item in hackathons:
                if not isinstance(item, dict):
                    continue
                title = item.get("name", item.get("title", ""))
                prize_raw = item.get("totalPrize", item.get("prize", item.get("rewardAmount", 0))) or 0
                try:
                    prize = int(float(str(prize_raw).replace(",", "").replace("USD", "").strip()))
                except (ValueError, TypeError):
                    prize = 0
                slug = item.get("alias", item.get("id", item.get("slug", "")))
                end_time = item.get("endTime", item.get("end_time", item.get("submissionEndTime", "")))
                deadline = end_time[:10] if end_time and isinstance(end_time, str) else ""
                results.append({
                    "t": title, "v": prize,
                    "u": f"https://www.hackquest.io/hackathons/{slug}",
                    "s": "HackQuest", "type": "Hackathon",
                    "region": detect_region(title),
                    "app": item.get("participantsCount", item.get("participants", 0)) or 0,
                    "org": "HackQuest", "deadline": deadline
                })

        # 方法2: HTML fallback
        if not results:
            slugs = re.findall(r'href=["\'](?:https://www\.hackquest\.io)?/hackathons/([A-Za-z0-9_\-\u4e00-\u9fff%\.]+)["\']', html)
            slugs = list(dict.fromkeys(slugs))
            slugs = [s for s in slugs if not s.endswith(('.png', '.jpg', '.svg', '.webp'))]
            prizes_raw = re.findall(r'([\d,]+)\s*USD', html)
            prizes = []
            for p in prizes_raw:
                try:
                    prizes.append(int(p.replace(",", "")))
                except (ValueError, TypeError):
                    prizes.append(0)
            titles = re.findall(r'<h[23][^>]*>([^<]{3,80})</h[23]>', html)
            titles = [t.strip() for t in titles if t.strip()]
            for i, slug in enumerate(slugs[:30]):
                title = titles[i] if i < len(titles) else slug.replace("-", " ")
                prize = prizes[i] if i < len(prizes) else 0
                results.append({
                    "t": title, "v": prize,
                    "u": f"https://www.hackquest.io/hackathons/{slug}",
                    "s": "HackQuest", "type": "Hackathon",
                    "region": detect_region(title), "app": 0,
                    "org": "HackQuest", "deadline": ""
                })
        print(f"[HackQuest] ✅ {len(results)} 个")
    except Exception as e:
        print(f"[HackQuest] ❌ {e}")
    return results

# ============================================================
# 数据源: DeFiLlama Yields
# ============================================================
STABLE_SYMBOLS = {"USDC", "USDT", "DAI", "USDE", "FDUSD", "TUSD", "USDG",
                  "RLUSD", "USD1", "USDS", "FRAX", "LUSD", "CRVUSD", "GHO",
                  "ETH", "WETH", "WBTC", "BTC", "SOL", "BNB"}

PLATFORM_URLS = {
    "uniswap": "https://app.uniswap.org/explore/pools",
    "curve": "https://curve.fi",
    "aave": "https://app.aave.com/",
    "compound": "https://app.compound.finance/",
    "pendle": "https://app.pendle.finance/trade/markets",
    "morpho": "https://app.morpho.org/",
    "hyperliquid": "https://app.hyperion.xyz/",
    "hyperion": "https://app.hyperion.xyz/",
    "aerodrome": "https://aerodrome.finance/pools",
    "velodrome": "https://velodrome.finance/pools",
    "lido": "https://stake.lido.fi/",
    "yearn": "https://yearn.fi/vaults",
    "convex": "https://www.convexfinance.com/stake",
    "balancer": "https://app.balancer.fi/#/pools",
}

def fetch_defillama_yields():
    """v23: 全链 DeFi 收益 + 安全提示"""
    results = []
    try:
        resp = fetch_with_retry("https://yields.llama.fi/pools",
                                headers={"User-Agent": "Mozilla/5.0"})
        if not resp:
            return results
        pools = resp.json().get("data", [])

        # 底层资产分类
        STABLES = {'USDC', 'USDT', 'DAI', 'USDE', 'FDUSD', 'TUSD', 'GHO', 'FRAX',
                    'LUSD', 'CRVUSD', 'PYUSD', 'USDG', 'USD1', 'USDS', 'RLUSD'}
        MAJORS = {'ETH', 'WETH', 'STETH', 'WSTETH', 'CBETH', 'RETH', 'METH', 'EETH',
                  'WBTC', 'BTC', 'TBTC', 'CBBTC', 'SOL', 'MSOL', 'JITOSOL', 'BNSOL',
                  'BNB', 'AVAX', 'MATIC', 'POL'}

        for pool in pools:
            apy = pool.get("apy") or 0
            tvl = pool.get("tvlUsd") or 0
            symbol = pool.get("symbol", "")
            project = pool.get("project", "")
            chain = pool.get("chain", "")
            pool_id = pool.get("pool", "")

            # v23: 宽松筛选 — APY>5%, TVL>$100k, APY<1000%
            if apy < 5 or tvl < 100000 or apy > 1000:
                continue

            apy_base = pool.get("apyBase") or 0
            apy_reward = pool.get("apyReward") or 0
            il_risk = pool.get("ilRisk", "")
            exposure = pool.get("exposure", "")
            stablecoin = pool.get("stablecoin", False)

            # v26.2 修复: 底层资产识别 — 要求 LP 里所有 token 都是主流才算 Blue-chip
            # 老逻辑错在: JOKER-WETH 只要有 WETH 就被标 Blue-chip, 实际 JOKER 是山寨
            syms = set(s.upper() for s in symbol.replace("-", " ").replace("/", " ").split())
            if syms and all(s in STABLES for s in syms):
                asset_type = "🟢 稳定币 Stablecoin"
            elif syms and all(s in (STABLES | MAJORS) for s in syms):
                # 例如: ETH-USDC, WBTC-ETH, stETH-WETH 等纯主流/稳定组合
                asset_type = "🔵 主流资产 Blue-chip"
            else:
                # 任何一个 token 不在主流/稳定集合 → 山寨池
                # 例如: JOKER-WETH, MEME-USDC, XAUT-USDT (XAUT 是代币化黄金非稳定币)
                asset_type = "🟠 山寨/LP Altcoin/LP"

            # 收益来源分析
            if apy_base > 0 and apy_reward > 0:
                yield_source = f"基础 {apy_base:.1f}% + 奖励 {apy_reward:.1f}%"
            elif apy_reward > apy_base * 2:
                yield_source = f"⚠️ 主要靠奖励 Reward-heavy ({apy_reward:.1f}%)"
            else:
                yield_source = f"基础利率 Base yield ({apy_base:.1f}%)"

            # 安全标签
            proj_lower = project.lower()
            audited = proj_lower in AUDITED_PROTOCOLS
            is_blue_chip = proj_lower in BLUE_CHIP_PROTOCOLS

            safety_tags = []
            if is_blue_chip:
                safety_tags.append("✅ 蓝筹 Blue-chip")
            if audited:
                safety_tags.append("🔒 已审计 Audited")
            if stablecoin:
                safety_tags.append("💵 稳定币池")
            if il_risk == "yes":
                safety_tags.append("⚠️ 有无常损失 IL Risk")
            if apy_reward > apy_base * 3 and apy_reward > 10:
                safety_tags.append("⚠️ 奖励占比高，可能不可持续")
            if tvl < 1e6:
                safety_tags.append("⚠️ TVL<$1M 流动性低")

            platform_url = next((v for k, v in PLATFORM_URLS.items() if k in proj_lower),
                                f"https://defillama.com/yields/pool/{pool_id}")
            results.append({
                "t": f"{symbol} on {project}", "v": int(apy),
                "u": platform_url, "pool_id": pool_id,
                "s": "DeFiLlama", "type": "DeFi Yield", "region": "🌍 全球",
                "app": int(tvl / 1000), "org": project, "deadline": "",
                "apy": round(apy, 2), "apy_base": round(apy_base, 2),
                "apy_reward": round(apy_reward, 2),
                "tvl": int(tvl), "chain": chain, "symbol": symbol,
                "defillama_u": f"https://defillama.com/yields/pool/{pool_id}",
                # v23 新增安全字段
                "asset_type": asset_type,
                "yield_source": yield_source,
                "safety_tags": safety_tags,
                "audited": audited,
            })

        results.sort(key=lambda x: x["apy"], reverse=True)
        results = results[:80]  # 扩展到80个

        # 统计
        chains = set(r['chain'] for r in results)
        print(f"[DeFiLlama Yields] ✅ {len(results)} 个池 | {len(chains)} 条链: {', '.join(sorted(chains)[:8])}...")
    except Exception as e:
        print(f"[DeFiLlama Yields] ❌ {e}")
    return results

# ============================================================
# 🆕 数据源: DeFiLlama TVL 异常监控
# ============================================================
def fetch_tvl_anomalies(conn):
    """监控 DeFiLlama Top N 协议的 TVL 异常下跌"""
    alerts = []
    try:
        resp = fetch_with_retry("https://api.llama.fi/v2/protocols",
                                headers={"User-Agent": "Mozilla/5.0"})
        if not resp:
            return alerts
        protocols = resp.json()
        if not isinstance(protocols, list):
            return alerts

        # 只监控 TVL > 阈值的协议
        monitored = [p for p in protocols if (p.get("tvl") or 0) >= TVL_MIN_USD]
        monitored.sort(key=lambda x: x.get("tvl", 0), reverse=True)
        monitored = monitored[:TVL_TOP_N]

        checked = 0
        anomalies = 0
        for proto in monitored:
            name = proto.get("name", "Unknown")
            slug = proto.get("slug", name.lower().replace(" ", "-"))
            current_tvl = proto.get("tvl") or 0
            chain_tvls = proto.get("chainTvls", {})
            category = proto.get("category", "")
            logo = proto.get("logo", "")

            # 保存当前 TVL
            save_tvl(conn, slug, current_tvl)
            checked += 1

            # 获取上次记录
            prev_tvl = get_prev_tvl(conn, slug)
            if prev_tvl is None or prev_tvl <= 0:
                continue

            # 计算变化
            change_pct = ((current_tvl - prev_tvl) / prev_tvl) * 100
            drop_pct = abs(change_pct)

            # 只关心下跌
            if change_pct >= 0:
                continue

            # 判断报警级别
            if drop_pct >= TVL_CRIT_PCT:
                level = "🚨 CRITICAL"
                emoji = "🚨🚨🚨"
                desc = "可能 Rug Pull / Exploit"
            elif drop_pct >= TVL_ALERT_PCT:
                level = "🔴 ALERT"
                emoji = "🔴🔴"
                desc = "TVL 大幅下跌"
            elif drop_pct >= TVL_WARN_PCT:
                level = "🟡 WARNING"
                emoji = "🟡"
                desc = "TVL 异常下跌"
            else:
                continue

            anomalies += 1

            # 防止重复报警 (6小时内同协议不重复)
            if was_alerted_recently(conn, slug, hours=6):
                continue

            record_alert(conn, slug, level, drop_pct)

            # 1h 变化 (如果 API 提供)
            change_1h = proto.get("change_1h") or 0
            change_1d = proto.get("change_1d") or 0
            change_7d = proto.get("change_7d") or 0

            alert = {
                "name": name,
                "slug": slug,
                "category": category,
                "current_tvl": current_tvl,
                "prev_tvl": prev_tvl,
                "drop_pct": drop_pct,
                "level": level,
                "emoji": emoji,
                "desc": desc,
                "change_1h": change_1h,
                "change_1d": change_1d,
                "change_7d": change_7d,
                "url": f"https://defillama.com/protocol/{slug}",
            }
            alerts.append(alert)

        print(f"[TVL Monitor] ✅ 已检查 {checked} 个协议, 发现 {anomalies} 个异常, 新报警 {len(alerts)} 个")

    except Exception as e:
        print(f"[TVL Monitor] ❌ {e}")
        traceback.print_exc()
    return alerts

def send_tvl_alerts(alerts):
    """v26.4: 推送 TVL 异常报警 (HTML 安全 + 关键数字加粗)"""
    if not alerts:
        return

    # 按严重程度排序 (CRITICAL > ALERT > WARNING)
    severity = {"🚨 CRITICAL": 3, "🔴 ALERT": 2, "🟡 WARNING": 1}
    alerts.sort(key=lambda x: severity.get(x["level"], 0), reverse=True)

    for a in alerts:
        curr_tvl_str = f"${a['current_tvl']/1e6:.2f}M"
        prev_tvl_str = f"${a['prev_tvl']/1e6:.2f}M"
        drop_str = f"-{a['drop_pct']:.1f}%"

        msg = f"{a['emoji']} TVL 异常报警!\n\n"
        msg += f"📛 协议: {_esc(a['name'])}\n"
        msg += f"⚠️ 级别: {_esc(a['level'])}\n"
        msg += f"📉 描述: {_esc(a['desc'])}\n\n"
        msg += f"💰 当前 TVL: {_b(curr_tvl_str)}\n"
        msg += f"📊 上次 TVL: {_b(prev_tvl_str)}\n"
        msg += f"📉 下跌: {_b(drop_str)}\n\n"
        if a['change_1h']:
            ch_str = f"{a['change_1h']:+.1f}%"
            msg += f"⏱️ 1h: {_b(ch_str)}\n"
        if a['change_1d']:
            ch_str = f"{a['change_1d']:+.1f}%"
            msg += f"📅 24h: {_b(ch_str)}\n"
        if a['change_7d']:
            ch_str = f"{a['change_7d']:+.1f}%"
            msg += f"📆 7d: {_b(ch_str)}\n"
        msg += f"\n🏷️ 类别: {_esc(a['category'])}\n"
        msg += f"🔗 {_esc(a['url'])}"
        # v26: 尾行标签
        try:
            v_millions = int(a.get('current_tvl', 0) / 1e6)
            tail = tail_for_alert("tvl", a['name'],
                v=v_millions,
                r=min(10, int(abs(a.get('drop_pct', 0)) / 10)),
                src=a.get('name', ''),
                extra={"drop_pct": a.get('drop_pct'), "level": a.get('level')})
            msg += f"\n{tail}"
        except Exception as e:
            print(f"[Tail] TVL error: {e}")
        send_tg(msg)
        time.sleep(1)
        # v26: 尾行标签
        try:
            v_millions = int(a.get('current_tvl', 0) / 1e6)
            tail = tail_for_alert("tvl", a['name'],
                v=v_millions,
                r=min(10, int(abs(a.get('drop_pct', 0)) / 10)),
                src=a.get('name', ''),
                extra={"drop_pct": a.get('drop_pct'), "level": a.get('level')})
            msg += f"\n{tail}"
        except Exception as e:
            print(f"[Tail] TVL error: {e}")
        send_tg(msg)
        time.sleep(1)
        # v26: 尾行标签
        try:
            v_millions = int(a.get('current_tvl', 0) / 1e6)
            tail = tail_for_alert("tvl", a['name'],
                v=v_millions,
                r=min(10, int(abs(a.get('drop_pct', 0)) / 10)),
                src=a.get('name', ''),
                extra={"drop_pct": a.get('drop_pct'), "level": a.get('level')})
            msg += f"\n{tail}"
        except Exception as e:
            print(f"[Tail] TVL error: {e}")
        send_tg(msg)
        time.sleep(1)


# ============================================================
# 数据源: CEX/DEX 理财活动 (via Barker 聚合)
# ============================================================
CEX_EARN_URLS = {
    "binance": "https://www.binance.com/en/earn",
    "bybit": "https://www.bybit.com/earn",
    "gate": "https://www.gate.io/earn",
    "gate.io": "https://www.gate.io/earn",
    "bitget": "https://www.bitget.com/earning/savings",
    "mexc": "https://www.mexc.com/earn",
    "okx": "https://www.okx.com/earn",
    "kucoin": "https://www.kucoin.com/earn",
    "htx": "https://www.htx.com/earn",
    "huobi": "https://www.htx.com/earn",
    "coinbase": "https://www.coinbase.com/earn",
    "kraken": "https://www.kraken.com/features/staking-coins",
    "aave": "https://app.aave.com/",
    "compound": "https://app.compound.finance/",
    "pendle": "https://app.pendle.finance/trade/markets",
    "morpho": "https://app.morpho.org/",
    "lido": "https://stake.lido.fi/",
    "ethena": "https://app.ethena.fi/earn",
    "maker": "https://app.spark.fi/",
    "spark": "https://app.spark.fi/",
    "hyperliquid": "https://app.hyperliquid.xyz/",
    "jupiter": "https://jup.ag/earn",
    "kamino": "https://app.kamino.finance/",
    "drift": "https://app.drift.trade/earn",
    "orca": "https://www.orca.so/pools",
    "raydium": "https://raydium.io/liquidity/",
    "aerodrome": "https://aerodrome.finance/",
    "velodrome": "https://velodrome.finance/",
    "curve": "https://curve.fi/",
    "convex": "https://www.convexfinance.com/",
    "yearn": "https://yearn.fi/vaults",
    "uniswap": "https://app.uniswap.org/explore/pools",
    "pancakeswap": "https://pancakeswap.finance/liquidity/pools",
    "sushi": "https://www.sushi.com/earn",
    "gmx": "https://app.gmx.io/#/earn",
    "eigenlayer": "https://app.eigenlayer.xyz/",
    "symbiotic": "https://app.symbiotic.fi/",
    "kelp": "https://kelpdao.xyz/restake/",
    "renzo": "https://app.renzoprotocol.com/",
    "ether.fi": "https://app.ether.fi/",
    "swell": "https://app.swellnetwork.io/",
}

def _get_platform_url(platform_name):
    """根据平台名匹配实际 URL"""
    name = platform_name.lower().strip()
    # 精确匹配
    if name in CEX_EARN_URLS:
        return CEX_EARN_URLS[name]
    # 模糊匹配
    for key, url in CEX_EARN_URLS.items():
        if key in name or name in key:
            return url
    return ""

def fetch_cex_dex_earn():
    """从 Barker 聚合页面抓取 CEX/DEX 理财活动 (丰富版)"""
    results = []
    if not BROWSERLESS_API:
        print("[CEX/DEX Earn] ⚠️ 无 BROWSERLESS_API, 跳过")
        return results
    try:
        print("[CEX/DEX Earn] 开始请求 Barker 聚合页...")
        scrape_url = f"https://chrome.browserless.io/scrape?token={BROWSERLESS_API}"
        payload = {
            "url": "https://app.barker.money/campaigns",
            "elements": [{"selector": "body"}],
            "gotoOptions": {"waitUntil": "networkidle2", "timeout": 60000},
            "waitForTimeout": 8000
        }
        resp = requests.post(scrape_url, json=payload, timeout=180)
        if "usage limit" in resp.text or len(resp.text) < 500:
            # v25+: Firecrawl fallback
            fc = firecrawl_scrape("https://app.barker.money/campaigns")
            if fc and len(fc) > 500:
                print(f"[CEX/DEX Earn] Browserless 不可用, Firecrawl fallback ({len(fc)} 字符)")
                html = fc
            else:
                print("[CEX/DEX Earn] Browserless + Firecrawl 都不可用")
                return results
        else:
            data = resp.json()
            html = ""
            if "data" in data:
                for item in data["data"]:
                    for r in item.get("results", []):
                        html += r.get("html", "")
            if not html and "body" in data:
                html = data.get("body", "")

        print(f"[CEX/DEX Earn] HTML 长度: {len(html)}")
        if len(html) < 500:
            return results

        # ====== 解析策略 ======
        # v25 fix: 在块级标签位置插入卡片分隔符, 防止滑窗串到下一张卡
        CARD_SEP = " |||CARD||| "
        text_only = re.sub(
            r'<(?:div|li|tr|article|section|card)[^>]*>',
            CARD_SEP, html, flags=re.IGNORECASE
        )
        text_only = re.sub(r'<[^>]+>', ' ', text_only)
        text_only = re.sub(r'\s+', ' ', text_only)

        # 卡片边界位置 (用于限制滑窗)
        card_boundaries = [m.start() for m in re.finditer(r'\|\|\|CARD\|\|\|', text_only)]

        def _within_same_card(pos_a, pos_b):
            """判断两个位置是否在同一张卡内 (之间无分隔符)"""
            lo, hi = min(pos_a, pos_b), max(pos_a, pos_b)
            for bp in card_boundaries:
                if lo < bp < hi:
                    return False
            return True

        # 1. 提取所有 APY (核心锚点)
        apy_positions = [(m.start(), m.group(1)) for m in re.finditer(r'(\d+\.?\d*)\s*%', text_only)]

        # 2. 提取所有 token 名
        token_re = r'\b(USDT|USDC|USDE|USD1|USDG|USDS|DAI|FDUSD|TUSD|GHO|FRAX|LUSD|CRVUSD|RLUSD|BTC|ETH|SOL|BNB|XRP|AVAX|DOT|ADA|MATIC|ARB|OP|SUI|APT|TIA|JUP|WLD|PENDLE|ENA|ETHENA|EIGEN|AAVE|MKR|LINK|UNI|CRV|LDO|SSV|RPL|PYUSD|BGB|GT|MX|OKB|KCS)\b'
        token_positions = [(m.start(), m.group(1).upper()) for m in re.finditer(token_re, text_only, re.IGNORECASE)]

        # 3. 平台/协议名 (中英文) - 只捕获平台名 + 已知后缀 - 只捕获平台名 + 已知后缀
        PLATFORM_SUFFIXES = r'(?:\s*(?:主站|钱包|Wallet|Exchange|Launchpool|Launchpad|Earn|Savings|Staking|Simple Earn|DeFi|Web3|链上)?)?'
        platform_names = [
            "Binance", "Bybit", r"Gate\.?io?", "Bitget", "MEXC", "OKX",
            "KuCoin", "HTX", "Coinbase", "Kraken",
            "抹茶", "火币", "币安",
            "Aave", "Pendle", "Morpho", "Lido", "Ethena", "Spark",
            "Compound", "Curve", "Yearn", "Hyperliquid",
            "Jupiter", "Kamino", "Drift", "Orca", "Raydium",
            "Aerodrome", "EigenLayer", "Kelp", "Renzo",
            r"ether\.fi", "Swell", "GMX", "PancakeSwap", "Uniswap",
        ]
        platform_re = r'(' + '|'.join(p + PLATFORM_SUFFIXES for p in platform_names) + r')'
        platform_positions = [(m.start(), m.group(1).strip()) for m in re.finditer(platform_re, text_only, re.IGNORECASE)]

        # 4. 派息频率 (v25 fix: 分开匹配频率和动作, 不要求紧邻)
        payout_positions = [(m.start(), re.sub(r'\s+', '', m.group(0))) for m in re.finditer(
            r'(?:每\s*小\s*时|每\s*[日天]|每\s*周\s*[一二三四五六日]?|每\s*月|每\s*年|实\s*时)'
            r'(?:\s*(?:派息|结算|发放|到账))?'
            r'|(?:\d{4}-\d{2}-\d{2})\s*(?:派息|到期)'
            r'|(?:hourly|daily|weekly|monthly)\s*(?:payout|distribution|interest|reward)?',
            text_only, re.IGNORECASE)]
        # 过滤太短的 (如单独的 "每" 匹配)
        payout_positions = [(p, v) for p, v in payout_positions if len(v) >= 2]

        # 5. 剩余时间
        remaining_positions = [(m.start(), m.group(0)) for m in re.finditer(
            r'(?:还剩|剩余)\s*\d+\s*[天日小时分]|长期|永久|ongoing|no deadline',
            text_only, re.IGNORECASE)]

        # 6. 截止日期
        deadline_positions = [(m.start(), m.group(0)) for m in re.finditer(
            r'\d{4}-\d{2}-\d{2}', text_only)]

        # 7. 标签
        tag_positions = [(m.start(), m.group(0)) for m in re.finditer(
            r'(?:🔥|✨)?(?:新|热门|限时|推荐|NEW|HOT|热|TRENDING)', text_only, re.IGNORECASE)]

        # 8. 风险/条件提示
        condition_positions = [(m.start(), m.group(0)[:60]) for m in re.finditer(
            r'(?:中国大陆|KYC|不建议|风险高|仅限|限制|需要|最低|minimum)[^。\n]{0,80}',
            text_only, re.IGNORECASE)]

        # 9. 活动类型
        earn_type_positions = [(m.start(), m.group(0)) for m in re.finditer(
            r'(?:理财活动|Launchpool|Launchpad|Simple Earn|Flexible|Fixed|Staking|Savings|Lending|Vault|锁仓|活期|定期)',
            text_only, re.IGNORECASE)]

        print(f"[CEX/DEX Earn] 解析: APYs={len(apy_positions)} tokens={len(token_positions)} "
              f"platforms={len(platform_positions)} payouts={len(payout_positions)} "
              f"deadlines={len(deadline_positions)} conditions={len(condition_positions)}")

        # ====== 按卡片组装 ======
        # 以 APY 为锚点，向前查找最近的 token/platform，向后查找 payout/deadline/conditions
        SEARCH_RANGE = 2000  # 卡片内的字符范围

        for apy_pos, apy_str in apy_positions:
            try:
                apy_val = float(apy_str)
            except ValueError:
                continue
            # v25 fix: 上限收紧 80%, 过滤明显解析错误
            if apy_val < 0.1 or apy_val > 80:
                continue

            # 查找最近的 token (向前, 就近优先)
            token = ""
            for tp, tv in reversed(token_positions):
                if tp < apy_pos and apy_pos - tp < SEARCH_RANGE:
                    token = tv
                    break

            # 查找最近的 platform (向前, 就近优先)
            platform_raw = ""
            for pp, pv in reversed(platform_positions):
                if pp < apy_pos and apy_pos - pp < SEARCH_RANGE:
                    platform_raw = pv
                    break

            # v25: 必须同时有 platform 和 token
            if not platform_raw or not token:
                continue

            # 清洗平台名 → 标准化
            platform_clean = platform_raw.split(">")[-1].strip() if ">" in platform_raw else platform_raw.strip()
            # 抹茶 → MEXC
            platform_map = {"抹茶": "MEXC", "火币": "HTX", "币安": "Binance"}
            for cn, en in platform_map.items():
                if cn in platform_clean:
                    platform_clean = platform_clean.replace(cn, en)
                    break

            # 提取平台 base name (for URL lookup)
            platform_base = platform_clean.split()[0].lower() if platform_clean else ""
            for key in CEX_EARN_URLS:
                if key in platform_base or platform_base in key:
                    platform_base = key
                    break

            platform_url = _get_platform_url(platform_base) or _get_platform_url(platform_clean)
            if not platform_url and token:
                platform_url = f"https://www.google.com/search?q={platform_clean}+{token}+earn"

            # 查找派息频率 (同卡内)
            payout = ""
            for pp, pv in payout_positions:
                if abs(pp - apy_pos) < SEARCH_RANGE and _within_same_card(pp, apy_pos):
                    payout = pv
                    break

            # 查找剩余时间 (同卡内)
            remaining = ""
            for rp, rv in remaining_positions:
                if abs(rp - apy_pos) < SEARCH_RANGE and _within_same_card(rp, apy_pos):
                    remaining = rv
                    break

            # 查找截止日期 (同卡内)
            deadline = ""
            for dp, dv in deadline_positions:
                if abs(dp - apy_pos) < SEARCH_RANGE and _within_same_card(dp, apy_pos):
                    deadline = dv
                    break

            # 查找标签 (同卡内)
            tags = []
            for tp2, tv2 in tag_positions:
                if abs(tp2 - apy_pos) < SEARCH_RANGE and _within_same_card(tp2, apy_pos):
                    if "新" in tv2 or "NEW" in tv2.upper():
                        tags.append("✨新")
                    if "热" in tv2 or "HOT" in tv2.upper():
                        tags.append("🔥热门")
                    break

            # 查找条件/风险提示 (同卡内)
            conditions = ""
            for cp, cv in condition_positions:
                if abs(cp - apy_pos) < SEARCH_RANGE and _within_same_card(cp, apy_pos):
                    conditions = cv.strip()
                    break

            # 查找活动类型 (同卡内)
            earn_type = ""
            for ep, ev in earn_type_positions:
                if abs(ep - apy_pos) < SEARCH_RANGE and _within_same_card(ep, apy_pos):
                    earn_type = ev
                    break

            # CEX 判断
            CEX_NAMES = {"binance","bybit","gate","gate.io","bitget","mexc","okx","kucoin","htx","huobi","coinbase","kraken"}
            type_label = "CEX Yield" if platform_base in CEX_NAMES else "DeFi Yield"

            title = f"{token} on {platform_clean}" if token else platform_clean
            results.append({
                "t": title,
                "v": int(apy_val),
                "u": platform_url or "",
                "s": platform_clean.split()[0] if platform_clean else "Unknown",
                "type": type_label,
                "region": "🌍 全球",
                "app": 0,
                "org": platform_clean.split()[0] if platform_clean else "",
                "project_name": platform_clean,  # 完整平台描述 (Binance 主站, 抹茶 Launchpool)
                "deadline": deadline,
                "remaining": remaining,
                "apy": round(apy_val, 2),
                "tvl": 0,
                "chain": "",
                "symbol": token,
                "payout_freq": payout,
                "tags": tags,
                "conditions": conditions,
                "earn_type": earn_type,
            })

        # 去重 (同平台+同token 只保留最高 APY)
        seen_keys = set()
        unique = []
        results = sorted(results, key=lambda x: x.get("apy", 0), reverse=True)
        for r in results:
            key = f"{r.get('org','')}-{r.get('symbol','')}"
            if key not in seen_keys:
                seen_keys.add(key)
                unique.append(r)
        results = unique

        print(f"[CEX/DEX Earn] ✅ {len(results)} 个活动 (去重后)")
        for r in results[:3]:
            print(f"  Sample: {r['t']} | APY={r['apy']}% | {r.get('payout_freq','')} | {r.get('remaining','')}")
    except Exception as e:
        print(f"[CEX/DEX Earn] ❌ {e}")
        traceback.print_exc()
    return results

# ============================================================
# 数据源: OKX Boost
# ============================================================
def fetch_okx_boost():
    results = []
    try:
        url = f"https://web3.okx.com/priapi/v1/dapp/boost/launchpool/list?type=1&mode=1%2C2&t={int(time.time()*1000)}"
        headers = {
            "User-Agent": "Mozilla/5.0", "Accept": "application/json",
            "Referer": "https://web3.okx.com/boost/x-launch"
        }
        resp = fetch_with_retry(url, headers=headers, timeout=15)
        if not resp:
            return results
        data = resp.json()
        pools = data.get("data", {}).get("pools", [])
        for item in pools:
            times = item.get("times", {})
            join_end = times.get("joinEndTime", 0)
            deadline = datetime.fromtimestamp(join_end/1000).strftime("%Y-%m-%d") if join_end else "N/A"
            reward = item.get("reward", {})
            reward_amount = reward.get("amount", "N/A")
            reward_token = reward.get("token", "")
            reward_text = f"{reward_amount:,.0f} {reward_token}" if isinstance(reward_amount, (int, float)) else f"{reward_amount} {reward_token}"
            results.append({
                "t": item.get("name", "Unknown"), "v": 0,
                "u": f"https://web3.okx.com/boost/x-launch/{item.get('navName', '')}",
                "s": "OKX Boost", "type": "Airdrop", "region": "Global",
                "app": item.get("participants", 0), "org": "OKX",
                "deadline": deadline, "reward_text": reward_text
            })
        print(f"[OKX Boost] ✅ {len(results)} 个")
    except Exception as e:
        print(f"[OKX Boost] ❌ {e}")
    return results

# ============================================================
# 统计 + 格式化 (去重)
# ============================================================
def stats_summary(bounties, key, top_n=6):
    stats = {}
    for b in bounties:
        val = b.get(key, "其他")
        stats[val] = stats.get(val, 0) + 1
    items = sorted(stats.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return "\n".join(f"  {k}: {v}" for k, v in items)

def generate_hashtags(b):
    """v25: 生成 hashtag 提升 TG 搜索和传播"""
    tags = set()
    # 平台类型
    t = b.get('type', '')
    s = b.get('s', '')
    if 'Hackathon' in t or s == 'DoraHacks':
        tags.add('#Hackathon')
    if 'Bounty' in t or s in ('Immunefi', 'GitHub'):
        tags.add('#Bounty')
    if s == 'Immunefi' or '安全' in t or 'Security' in t:
        tags.add('#Security')
    if s == 'Superteam':
        tags.add('#Superteam')
    if b.get('type') in ('DeFi Yield', 'CEX Yield'):
        tags.add('#Yield')
        apy = b.get('apy', 0)
        if apy >= 20:
            tags.add('#HighAPY')
    # 链
    chain = (b.get('chain', '') or '').lower()
    for c in ('solana', 'ethereum', 'bsc', 'base', 'arbitrum', 'polygon', 'aptos', 'sui'):
        if c in chain:
            tags.add(f'#{c.capitalize()}')
            break
    # Token
    sym = (b.get('symbol', '') or '').upper()
    if sym and '-' not in sym and '/' not in sym and len(sym) <= 6:
        tags.add(f'#{sym}')
    # 价值
    if b.get('v', 0) >= 10000:
        tags.add('#HighValue')
    return ' '.join(sorted(tags)[:5])  # 最多5个

def fmt_bounty(b):
    """v26.3: 单条 Bounty 推送 — HTML 安全 + 金额加粗"""
    v = b.get('v', 0)
    # 第 1 行: 金额加粗 · 来源 · 类型
    bits = []
    if v:
        bits.append(f"💰 {_b(f'${v:,}')}")
    if b.get('s'):
        bits.append(f"📡 {_esc(b['s'])}")
    if b.get('type') and b['type'] not in ('N/A', ''):
        bits.append(f"🏷️ {_esc(b['type'])}")
    msg = " · ".join(bits) + "\n"

    # 第 2 行: 标题
    msg += f"📌 {_esc(b['t'])}\n"

    # 第 3 行: 区域 · 截止 · 参与
    line3 = []
    if b.get('region') and b['region'] != 'N/A':
        line3.append(f"📍 {_esc(b['region'])}")
    if b.get('deadline') and len(str(b['deadline'])) >= 10:
        dl_line = f"⏰ {_esc(b['deadline'])}"
        if b.get('remaining'):
            dl_line += f" ({_esc(b['remaining'])})"
        line3.append(dl_line)
    if b.get('app'):
        line3.append(f"👥 {b['app']:,} 人")
    if line3:
        msg += " · ".join(line3) + "\n"

    # 跨平台
    also = b.get('also_on', [])
    if also:
        msg += f"🔁 也在: {_esc(', '.join(also))}\n"

    # URL
    msg += f"🔗 {_esc(b['u'])}"

    # hashtags
    tags = generate_hashtags(b)
    if tags:
        msg += f"\n\n{_esc(tags)}"

    # 尾行
    try:
        msg += f"\n{tail_for_bounty(b)}"
    except Exception as e:
        print(f"[Tail] fmt_bounty error: {e}")
    return msg

def fmt_defi(b):
    """v26.3: 单条 DeFi 推送 — HTML 安全 + APY/TVL 加粗"""
    apy = b.get("apy", b.get("v", 0))
    platform = b.get("org", b.get("s", ""))
    project = b.get("project_name", "")
    token = b.get("symbol", "")

    risk = score_risk(b)
    r_emoji = risk_emoji(risk)
    risk_text = " ".join(risk_label(risk).split()[1:])

    # 第 1 行: emoji + 平台 · 币种 · APY (APY 加粗)
    name = project if (project and project != platform) else (platform or b.get('t', '')[:40])
    header = f"{r_emoji} {_esc(name)}"
    if token and token.upper() not in name.upper():
        header += f" · {_esc(token)}"
    header += f" · APY {_b(f'{apy:.2f}%')}"
    apy_tags = b.get("tags", [])
    if apy_tags:
        header += f" {_esc(''.join(apy_tags))}"
    msg = header + "\n"

    # 第 2 行: Risk + Chain + TVL
    line2 = [f"🛡️ Risk {risk}/10 {_esc(risk_text)}"]
    if b.get("chain"):
        line2.append(f"⛓️ {_esc(b['chain'])}")
    tvl = b.get("tvl", 0)
    if tvl > 0:
        if tvl >= 1e9:
            line2.append(f"💰 TVL {_b(f'${tvl/1e9:.2f}B')}")
        elif tvl >= 1e6:
            line2.append(f"💰 TVL {_b(f'${tvl/1e6:.1f}M')}")
        elif tvl >= 1e3:
            line2.append(f"💰 TVL {_b(f'${tvl/1e3:.0f}K')}")
        else:
            line2.append(f"💰 TVL {_b(f'${tvl:,.0f}')}")
    msg += " · ".join(line2) + "\n"

    # 第 3 行 (可选): 7 日均值
    avg_7d = b.get("apy_7d_avg")
    if avg_7d and avg_7d > 0:
        diff_pct = ((apy - avg_7d) / avg_7d) * 100
        arrow = "📊" if abs(diff_pct) < 5 else ("📈" if diff_pct > 0 else "📉")
        msg += f"{arrow} 7日均值: {avg_7d:.2f}% ({diff_pct:+.0f}%)\n"

    # 资产类型
    asset_type = b.get("asset_type", "")
    if asset_type and token:
        msg += f"🪙 {_esc(token)} ({_esc(asset_type)})\n"
    elif asset_type:
        msg += f"🪙 {_esc(asset_type)}\n"

    # 收益来源
    yield_source = b.get("yield_source", "")
    if yield_source:
        msg += f"💡 {_esc(yield_source)}\n"

    # 派息频率
    payout = b.get("payout_freq", "")
    if payout:
        msg += f"🔄 {_esc(payout)}\n"

    # 安全标签
    safety_tags = b.get("safety_tags", [])
    if safety_tags:
        msg += "🔐 " + " · ".join(_esc(t) for t in safety_tags[:3]) + "\n"

    # 条件
    conditions = b.get("conditions", "")
    if conditions:
        msg += f"⚠️ {_esc(conditions)}\n"

    # 截止
    deadline = b.get("deadline", "")
    remaining = b.get("remaining", "")
    if deadline or remaining:
        line = "⏰ "
        if deadline:
            line += _esc(deadline)
        if remaining:
            line += f" ({_esc(remaining)})"
        msg += line + "\n"

    # URL
    msg += f"🔗 {_esc(b['u'])}"
    if b.get("defillama_u"):
        msg += f"\n📊 {_esc(b['defillama_u'])}"

    # hashtags
    tags = generate_hashtags(b)
    if tags:
        msg += f"\n\n{_esc(tags)}"

    # 尾行
    try:
        msg += f"\n{tail_for_bounty(b)}"
    except Exception as e:
        print(f"[Tail] fmt_defi error: {e}")
    return msg

def fmt_campaign(b):
    """格式化活动推送"""
    msg = f"{'🔶' if b['s']=='OKX Boost' else '🟡'} {b['t']}\n"
    msg += f"奖励: {b.get('reward_text', 'N/A')}\n"
    msg += f"截止: {b.get('deadline', 'N/A')}\n"
    msg += f"参与: {b.get('app', 0):,} 人\n"
    msg += f"🔗 {b['u']}"
    # v26: 尾行标签
    try:
        msg += f"\n{tail_for_bounty(b)}"
    except Exception as e:
        print(f"[Tail] fmt_campaign error: {e}")
    return msg

# ============================================================
# 并发扫描引擎
# ============================================================
DEFI_SOURCES = {"DeFiLlama"}  # v25: Binance Earn 移除

def is_defi(b):
    """判断是否为 DeFi/CEX 理财类"""
    return b.get('s') in DEFI_SOURCES or b.get('type', '') in ("CEX Yield", "DeFi Yield")

# v25: 跨源去重聚类
_STOP_WORDS = {
    'the', 'a', 'an', 'and', 'or', 'of', 'for', 'to', 'in', 'on', 'at', 'by', 'with',
    'bounty', 'hackathon', 'program', 'open', 'new', '新', '赏金', '黑客松',
}

def _title_tokens(title):
    words = re.findall(r'[a-z0-9\u4e00-\u9fff]{2,}', (title or '').lower())
    return set(w for w in words if w not in _STOP_WORDS)

def _jaccard(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0

def cluster_duplicates(all_b, threshold=0.7):
    """v25: 跨源合并同一 bounty (Jaccard 相似度 > threshold)
    仅对 bounty/hackathon 聚类, DeFi 收益池不聚类 (每个池子独立)
    """
    if not all_b:
        return all_b
    defi = [b for b in all_b if is_defi(b)]
    others = [b for b in all_b if not is_defi(b)]
    # v25 fix: 按 URL 稳定排序, 保证同一 bounty 在不同扫描中选出相同 primary
    others.sort(key=lambda x: (x.get('u', ''), -x.get('v', 0)))
    tokenized = [(b, _title_tokens(b.get('t', ''))) for b in others]

    merged = set()
    results = []
    for i, (b1, t1) in enumerate(tokenized):
        if i in merged or not t1:
            if i not in merged:
                results.append(b1)
            continue
        cluster = [b1]
        for j in range(i + 1, len(tokenized)):
            if j in merged:
                continue
            b2, t2 = tokenized[j]
            if not t2 or b2.get('s') == b1.get('s'):
                continue
            if _jaccard(t1, t2) >= threshold:
                cluster.append(b2)
                merged.add(j)
        if len(cluster) > 1:
            primary = max(cluster, key=lambda x: x.get('v', 0))
            primary['also_on'] = sorted(set(c.get('s', '') for c in cluster if c.get('s') != primary.get('s')))
            results.append(primary)
        else:
            results.append(b1)

    removed = len(others) - len(results)
    if removed > 0:
        print(f"[Dedup] 合并 {removed} 条跨源重复 bounty")
    return results + defi

def run_all_fetchers(conn=None):
    """并发执行 (v25: 60s 硬超时熔断, 慢源不再拖全局)
    v26: conn 可选, 若传入则记录每个 fetcher 的结果数量 (哑巴失败检测)
    """
    fetchers = {
        "Immunefi": fetch_immunefi,
        "Superteam": fetch_superteam,
        "HackerOne": fetch_hackerone,
        "HackenProof": fetch_hackenproof,
        "Cantina": fetch_cantina,
        "Code4rena": fetch_code4rena,
        "Bountycaster": fetch_bountycaster,
        "GitHub": fetch_github,
        "Devpost": fetch_devpost,
        "DoraHacks": fetch_dorahacks_hackathon,
        "HackQuest": fetch_hackquest,
        "OKX Boost": fetch_okx_boost,
        "DeFiLlama Yields": fetch_defillama_yields,
        "CEX/DEX Earn": fetch_cex_dex_earn,
        # v25: Binance/Bybit/Bitget Earn 公开 API 在 Railway IP 被封禁,
        # Barker 聚合页已覆盖这些平台的 CEX Savings 数据
    }

    PER_FETCHER_TIMEOUT = 60  # 秒
    all_results = []
    errors = []
    per_fetcher_counts = {}  # v26: 每个 fetcher 的结果数
    start = time.time()

    with ThreadPoolExecutor(max_workers=6) as executor:
        future_to_name = {executor.submit(fn): name for name, fn in fetchers.items()}
        for future in as_completed(future_to_name, timeout=PER_FETCHER_TIMEOUT * 2):
            name = future_to_name[future]
            try:
                result = future.result(timeout=PER_FETCHER_TIMEOUT)
                all_results.extend(result)
                per_fetcher_counts[name] = len(result)
            except FuturesTimeout:
                errors.append(f"{name}: timeout>{PER_FETCHER_TIMEOUT}s")
                print(f"[Engine] ⏱️ {name} 超时熔断")
                future.cancel()
                per_fetcher_counts[name] = -1  # -1 = 超时, 不计入 drought
            except Exception as e:
                errors.append(f"{name}: {e}")
                print(f"[Engine] ❌ {name} 失败: {e}")
                per_fetcher_counts[name] = -1  # -1 = 异常, 不计入 drought

    elapsed = time.time() - start
    # v25: 全局过滤过期 bounty
    before = len(all_results)
    all_results = [b for b in all_results if not is_expired(b)]
    expired_count = before - len(all_results)

    # v26: 记录 fetcher 成功率 (只记真·成功返回 0 条 = 哑巴失败可疑; 异常/超时不记)
    if conn is not None:
        for name, cnt in per_fetcher_counts.items():
            if cnt >= 0:  # 过滤掉超时/异常
                try:
                    record_fetcher_result(conn, name, cnt)
                except Exception as e:
                    print(f"[Drought] record {name}: {e}")

    print(f"\n[Engine] ✅ 扫描完成: {len(all_results)} 条 (过滤过期 {expired_count}), 耗时 {elapsed:.1f}s, 错误 {len(errors)} 个")
    return all_results, errors, elapsed

# ============================================================
# 推送模板 (去重合并)
# ============================================================
def fmt_defi_compact(b):
    """v26.3: 紧凑版 DeFi (Format A) — HTML 安全 + APY 加粗"""
    apy = b.get("apy", b.get("v", 0))
    platform = b.get("org", b.get("s", ""))
    project = b.get("project_name", "")
    token = b.get("symbol", "")

    risk = 5
    try:
        risk = score_risk(b)
    except Exception:
        pass
    r_emoji = risk_emoji(risk)
    risk_text = " ".join(risk_label(risk).split()[1:])

    # 第 1 行: emoji + 平台 · 币种 · APY (APY 加粗)
    name = platform if platform else (project or b.get('t', '')[:40])
    header = f"{r_emoji} {_esc(name)}"
    if token and token.upper() not in name.upper():
        header += f" · {_esc(token)}"
    header += f" · APY {_b(f'{apy:.2f}%')}"
    msg = header + "\n"

    # 第 2 行: Risk + Chain + TVL
    line2 = [f"🛡️ Risk {risk}/10 {_esc(risk_text)}"]
    if b.get("chain"):
        line2.append(f"⛓️ {_esc(b['chain'])}")
    tvl = b.get("tvl", 0)
    if tvl > 0:
        if tvl >= 1e9:
            line2.append(f"💰 ${tvl/1e9:.2f}B")
        elif tvl >= 1e6:
            line2.append(f"💰 ${tvl/1e6:.1f}M")
        elif tvl >= 1e3:
            line2.append(f"💰 ${tvl/1e3:.0f}K")
        else:
            line2.append(f"💰 ${tvl:,.0f}")
    msg += " · ".join(line2) + "\n"

    # 第 3 行 (可选): 安全标签 (含 TVL<$1M 等, 必须 _esc 否则 HTML 炸)
    safety_tags = b.get("safety_tags", [])
    if safety_tags:
        msg += "🔐 " + " · ".join(_esc(t) for t in safety_tags[:3]) + "\n"

    # 第 4 行 (可选): 截止
    if b.get("deadline") and len(str(b["deadline"])) >= 10:
        line = f"⏰ {_esc(b['deadline'])}"
        if b.get("remaining"):
            line += f" ({_esc(b['remaining'])})"
        msg += line + "\n"

    # 第 5 行: 完整 URL (Telegram 会 auto-link, & 需要转义)
    msg += f"🔗 {_esc(b['u'])}\n"

    # 尾行标签 (纯文本, 已 sanitize, 无 HTML 风险)
    try:
        msg += tail_for_bounty(b)
    except Exception as e:
        print(f"[Tail] fmt_defi_compact error: {e}")
    return msg

def fmt_bounty_compact(b):
    """v26.3: 紧凑版 Bounty (Format A) — HTML 安全 + 金额加粗"""
    v = b.get('v', 0)
    # 第 1 行: 金额 (加粗) · 来源 · 类型
    bits = []
    if v:
        bits.append(f"💰 {_b(f'${v:,}')}")
    if b.get('s'):
        bits.append(f"📡 {_esc(b['s'])}")
    if b.get('type') and b['type'] not in ('N/A', ''):
        bits.append(f"🏷️ {_esc(b['type'])}")
    msg = " · ".join(bits) + "\n"

    # 第 2 行: 标题
    msg += f"📌 {_esc(b['t'])}\n"

    # 第 3 行 (可选): 截止 + 区域
    line3 = []
    if b.get('deadline') and len(str(b['deadline'])) >= 10:
        dl_line = f"⏰ {_esc(b['deadline'])}"
        if b.get('remaining'):
            dl_line += f" ({_esc(b['remaining'])})"
        line3.append(dl_line)
    if b.get('region') and b['region'] != 'N/A':
        line3.append(f"📍 {_esc(b['region'])}")
    if line3:
        msg += " · ".join(line3) + "\n"

    # 第 4 行 (可选): 跨平台
    also = b.get('also_on', [])
    if also:
        msg += f"🔁 也在: {_esc(', '.join(also))}\n"

    # 第 5 行: 完整 URL
    msg += f"🔗 {_esc(b['u'])}\n"

    # 尾行标签
    try:
        msg += tail_for_bounty(b)
    except Exception as e:
        print(f"[Tail] fmt_bounty_compact error: {e}")
    return msg

# v26.1: 圆圈数字 (最多 20)
_CIRCLED_NUMS = [
    "①","②","③","④","⑤","⑥","⑦","⑧","⑨","⑩",
    "⑪","⑫","⑬","⑭","⑮","⑯","⑰","⑱","⑲","⑳",
]

def _numbered_separator(i):
    """生成第 i 项的分隔线 (i 从 0 开始)"""
    num = _CIRCLED_NUMS[i] if i < len(_CIRCLED_NUMS) else f"({i+1})"
    return f"━━ {num} ━━━━━━━━━━━━━━"

def push_top_list(items, title, fmt_fn, top_n=5):
    """v26.2: 通用 Top N 推送 (圆圈数字前缀, 无分隔线, 避免手机换行问题)"""
    if not items:
        return
    parts = [title, ""]
    for i, b in enumerate(items[:top_n]):
        num = _CIRCLED_NUMS[i] if i < len(_CIRCLED_NUMS) else f"({i+1})"
        formatted = fmt_fn(b)
        # 把编号前置到第一行开头 (不是单独一行)
        first_nl = formatted.find("\n")
        if first_nl > 0:
            formatted = f"{num} {formatted[:first_nl]}\n{formatted[first_nl+1:]}"
        else:
            formatted = f"{num} {formatted}"
        parts.append(formatted)
        parts.append("")  # item 间空行
    send_tg("\n".join(parts).strip())
    time.sleep(1)

def push_initial_report(all_b, conn=None):
    """v25+: 启动只发简短状态. v28.3: 版本号改成动态读取
    🆕 v30.12: 改为仅 admin 私聊 + 24h 冷却 (防 redeploy 频道刷屏)"""
    all_b = [b for b in all_b if not is_expired(b)]
    high_val = [b for b in all_b if b.get('v', 0) >= MIN_VALUE]
    sources = len(set(b['s'] for b in all_b))

    msg = f"🚀 Bounty Monitor 启动完成!\n\n"
    msg += f"📋 总计: {len(all_b)} 条\n"
    msg += f"💰 高价值 (≥${MIN_VALUE}): {len(high_val)}\n"
    msg += f"📡 数据源: {sources} 个\n"
    msg += f"⏰ Top 5 摘要马上推送 ↓"

    # 🆕 v30.12: 仅 admin 私聊 (不再发频道, 避免每次 redeploy 刷屏)
    if not TG_ADMIN_CHAT_ID:
        # admin 未配置, 静默 (打日志但不发频道)
        print(f"[InitialReport] admin 未配置, 跳过启动通知 (避免频道刷屏)")
        return

    # 24h 冷却 (避免短时间内多次重启刷自己私聊)
    if conn is not None:
        last_str = kv_get(conn, "initial_report_time")
        if last_str:
            try:
                last_t = datetime.strptime(last_str, "%Y-%m-%d %H:%M:%S")
                if (datetime.now() - last_t).total_seconds() < 24 * 3600:
                    elapsed_h = (datetime.now() - last_t).total_seconds() / 3600
                    print(f"[InitialReport] ⏭️ {elapsed_h:.1f}h 前已发, 24h 冷却中, 跳过")
                    return
            except Exception:
                pass

    # 直接 POST 到 admin chat (不走 send_tg, 因为 send_tg 走频道)
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id": TG_ADMIN_CHAT_ID,
                "text": msg,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        print(f"[InitialReport] ✅ 已私聊 admin")
        if conn is not None:
            kv_set(conn, "initial_report_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as e:
        print(f"[InitialReport] 错误: {e}")

_LAST_BOUNTY_DIGEST_FINGERPRINT = None
_LAST_BOUNTY_DIGEST_TIME = None


def _compute_bounty_digest_fingerprint(all_b):
    """v30.10: 计算 Top 5 + DoraHacks 内容指纹, 内容相同时跳过推送"""
    try:
        valid = [b for b in all_b if not is_expired(b)]
        top5 = sorted([b for b in valid if b.get('v', 0) >= MIN_VALUE],
                      key=lambda x: x.get('v', 0), reverse=True)[:5]
        top5_urls = [b.get('u', '') for b in top5]
        dh_urls = sorted([b.get('u', '') for b in valid if b.get('s') == "DoraHacks"])
        sig = "|".join(top5_urls) + "##" + "|".join(dh_urls)
        return hashlib.md5(sig.encode()).hexdigest()
    except Exception:
        return None


def push_bounty_digest(all_b, conn=None, force=False):
    """v30.10: 每日 Bounty 摘要 (1 次/天 + 启动时, 内容相同自动去重)
    🆕 v30.12: fingerprint 持久化到 DB (重启后仍生效, 修复 redeploy 重发 Top 5 / DoraHacks 汇总)
    🆕 v30.13.2: 加绝对 18h 冷却 (修复 fp 不稳定导致 redeploy 仍重发的问题)"""
    global _LAST_BOUNTY_DIGEST_FINGERPRINT, _LAST_BOUNTY_DIGEST_TIME

    new_fp = _compute_bounty_digest_fingerprint(all_b)

    # 🆕 v30.12: 优先从 DB 读 (跨重启保留), 内存变量做 fallback
    last_fp = None
    last_time_str = None
    if conn is not None:
        last_fp = kv_get(conn, "bounty_digest_fp")
        last_time_str = kv_get(conn, "bounty_digest_time")
    if last_fp is None:
        last_fp = _LAST_BOUNTY_DIGEST_FINGERPRINT
    if last_time_str is None and _LAST_BOUNTY_DIGEST_TIME is not None:
        last_time_str = _LAST_BOUNTY_DIGEST_TIME.strftime("%Y-%m-%d %H:%M:%S")

    # 🆕 v30.13.2: 绝对 18h 冷却 (无视 fp) — 不管内容怎么变, 18h 内推过就不再推
    # 这是 redeploy 防刷屏的硬保护. 真正的"新内容"会通过日推 (UTC 1点) 自然出现.
    if not force and last_time_str:
        try:
            last_t = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M:%S")
            elapsed_h = (datetime.now() - last_t).total_seconds() / 3600
            if elapsed_h < 18:
                fp_status = "fp 一致" if last_fp == new_fp else "fp 不同但仍冷却"
                print(f"[BountyDigest] ⏭️ 绝对 18h 冷却 ({elapsed_h:.1f}h 前推过, {fp_status}), 跳过")
                return
        except Exception:
            pass

    # 内存 + DB 同步
    _LAST_BOUNTY_DIGEST_FINGERPRINT = new_fp
    _LAST_BOUNTY_DIGEST_TIME = datetime.now()
    if conn is not None and new_fp:
        kv_set(conn, "bounty_digest_fp", new_fp)
        kv_set(conn, "bounty_digest_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    # v25: 二次过滤过期
    all_b = [b for b in all_b if not is_expired(b)]

    # 全平台 Top 5 高价值 (用 push_top_list 获得数字编号 + 尾行)
    top5 = sorted([b for b in all_b if b.get('v', 0) >= MIN_VALUE],
                  key=lambda x: x.get('v', 0), reverse=True)[:5]
    push_top_list(top5, "🏆 当前 Top 5 高价值 Bounty", fmt_bounty_compact, 5)

    # DoraHacks 当前推送 (v25: 模仿邮件分组 - 最后机会 / 高奖金 / 进行中)
    today_str = datetime.now().strftime("%Y-%m-%d")
    seven_days = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    dh_all = [b for b in all_b if b['s'] == "DoraHacks"]
    if dh_all:
        # 1. 最后机会 (7 天内截止)
        last_chance = sorted(
            [b for b in dh_all if b.get('deadline') and today_str <= b['deadline'] <= seven_days],
            key=lambda x: x.get('deadline', '')
        )[:3]
        # 2. 高奖金 Top 3
        high_prize = sorted([b for b in dh_all if b['v'] >= 300],
                            key=lambda x: x.get('v', 0), reverse=True)[:3]
        # 3. 全部进行中 (按参与人数, 排除已显示的)
        shown_urls = {b['u'] for b in last_chance + high_prize}
        ongoing = sorted([b for b in dh_all if b['u'] not in shown_urls],
                         key=lambda x: x.get('app', 0), reverse=True)[:4]

        msg = "🟢 DoraHacks 黑客松汇总:\n\n"
        if last_chance:
            msg += "⏰ 最后机会 Last Chance:\n"
            for b in last_chance:
                prize = f"${b['v']:,}" if b['v'] >= 300 else "未公开"
                msg += f"  • {_esc(b['t'][:50])}\n"
                msg += f"    💰 {_b(prize)} | 📅 截止 {_esc(b['deadline'])}\n"
                msg += f"    🔗 {_esc(b['u'])}\n"
            msg += "\n"
        if high_prize:
            msg += "💎 高奖金 High Prize:\n"
            for b in high_prize:
                if b in last_chance:
                    continue
                prize_str = f"${b['v']:,}"
                msg += f"  • {_esc(b['t'][:50])}\n"
                msg += f"    💰 {_b(prize_str)} | 👥 {b.get('app', 0)} 人\n"
                msg += f"    🔗 {_esc(b['u'])}\n"
            msg += "\n"
        if ongoing:
            msg += "🚀 进行中 Ongoing:\n"
            for b in ongoing:
                tag = b.get('org') or b.get('tags', '')
                msg += f"  • {_esc(b['t'][:50])}\n"
                if tag:
                    msg += f"    🏷️ {_esc(str(tag)[:40])}"
                if b.get('deadline'):
                    msg += f" | 📅 {_esc(b['deadline'])}"
                msg += f"\n    🔗 {_esc(b['u'])}\n"
        send_tg(msg.strip())
        time.sleep(1)

def push_daily_digest(all_b, conn=None):
    """v26.1: 每日摘要 — 紧凑 + 数字编号格式 (专业终端风)"""
    # DeFi Top 3
    defi_daily = sorted([b for b in all_b if is_defi(b)],
                        key=lambda x: x.get("apy", x.get("v", 0)), reverse=True)[:3]
    push_top_list(defi_daily, "📅 每日提醒 · DeFi/CEX 高收益 Top 3", fmt_defi_compact, 3)

    # Superteam Top 5 (用紧凑格式)
    st = sorted([b for b in all_b if b['s'] == "Superteam"],
                key=lambda x: x.get('v') or 0, reverse=True)[:5]
    push_top_list(st, "📅 每日提醒 · Superteam Top 5", fmt_bounty_compact, 5)

    # 活动类 (OKX Boost)
    for source in ["OKX Boost"]:
        items = [b for b in all_b if b['s'] == source]
        if items:
            push_top_list(items, f"📅 每日提醒 · {source}", fmt_campaign, 5)

    # CEX/DEX 理财活动 Top 5 (紧凑版)
    cex_dex = sorted([b for b in all_b if b.get('type') in ('CEX Yield', 'DeFi Yield')
                      and b.get('s') != 'DeFiLlama'],
                     key=lambda x: x.get("apy", 0), reverse=True)[:5]
    push_top_list(cex_dex, "📅 每日提醒 · CEX/DEX 理财活动 Top 5", fmt_defi_compact, 5)

    # 🆕 v30.9: 同步发币安广场 (Top 3 Risk≤3 精选, 1 条/天)
    try:
        push_earn_to_square(all_b, conn)
    except Exception as e:
        print(f"[Square/Earn] 主循环错误: {e}")

# ============================================================
# 🆕 v25: 稳定币脱锚警报 (CoinGecko 公开 API)
# ============================================================
STABLECOIN_IDS = {
    "tether": "USDT", "usd-coin": "USDC", "dai": "DAI", "first-digital-usd": "FDUSD",
    "true-usd": "TUSD", "paxos-standard": "USDP", "frax": "FRAX", "ethena-usde": "USDE",
    "usdd": "USDD", "pyusd": "PYUSD", "crvusd": "crvUSD", "gho": "GHO",
    "resolv-usd": "USR", "ripple-usd": "RLUSD",
}

def check_stablecoin_depeg(conn):
    """检查稳定币脱锚 (< $0.995 或 > $1.005) - DeFiLlama /stablecoinprices"""
    alerts = []
    try:
        resp = fetch_with_retry(
            "https://stablecoins.llama.fi/stablecoinprices",
            timeout=15
        )
        if not resp:
            print("[Depeg] ❌ DeFiLlama 无响应")
            return alerts
        data = resp.json()
        # 返回历史数组 [{date, prices: {gecko_id: price}}], 取最新
        if not isinstance(data, list) or not data:
            print("[Depeg] ❌ 数据格式异常")
            return alerts
        latest = data[-1]
        prices = latest.get("prices", {}) or {}
        checked = 0
        for cg_id, symbol in STABLECOIN_IDS.items():
            price = prices.get(cg_id)
            if price is None:
                continue
            try:
                price = float(price)
            except (ValueError, TypeError):
                continue
            if price <= 0:
                continue
            checked += 1
            if price < 0.995 or price > 1.005:
                severity = "严重" if abs(price - 1.0) > 0.02 else "中等"
                alert_key = f"{symbol}-{severity}"
                if is_alerted(conn, "depeg", alert_key, hours=6):
                    continue
                mark_alerted(conn, "depeg", alert_key)
                alerts.append({
                    "symbol": symbol, "price": price, "change": 0, "severity": severity
                })
        print(f"[Depeg] ✅ 检查 {checked} 个稳定币, 发现 {len(alerts)} 个脱锚")
    except Exception as e:
        print(f"[Depeg] ❌ {e}")
    return alerts

def send_depeg_alerts(alerts):
    """v26.4: HTML 安全 + 价格加粗"""
    if not alerts:
        return
    for a in alerts:
        emoji = "🚨" if a['severity'] == "严重" else "⚠️"
        direction = "📉" if a['price'] < 1.0 else "📈"
        price_str = f"${a['price']:.4f}"
        dev_str = f"{(a['price']-1)*100:+.2f}%"
        msg = (f"{emoji} 稳定币脱锚警报 Depeg Alert\n\n"
               f"💱 {_esc(a['symbol'])}\n"
               f"{direction} 价格: {_b(price_str)} (偏离 {_b(dev_str)})\n"
               f"🎚️ 严重程度: {_esc(a['severity'])}\n"
               f"🔗 https://defillama.com/stablecoins")
        try:
            deviation_bp = int(abs(a['price'] - 1.0) * 10000)
            r = 9 if a['severity'] == "严重" else 6
            tail = tail_for_alert("depeg", a['symbol'], v=deviation_bp, r=r,
                src=a['symbol'], extra={"price": a['price'], "severity": a['severity']})
            msg += f"\n{tail}"
        except Exception as e:
            print(f"[Tail] depeg error: {e}")
        send_tg(msg)
        time.sleep(1)


# ============================================================
# 🆕 v25: Binance 新币上线公告追踪
# ============================================================
def fetch_binance_listings(conn):
    """抓取 Binance 新币上线公告 (type 48 = New Crypto Listing)"""
    alerts = []
    try:
        # Binance CMS API (公开, 无签名)
        url = "https://www.binance.com/bapi/composite/v1/public/cms/article/catalog/list/query"
        params = {
            "catalogId": "48",  # New Cryptocurrency Listing
            "pageNo": "1",
            "pageSize": "10"
        }
        resp = fetch_with_retry(url, params=params, timeout=15)
        if not resp:
            return alerts
        data = resp.json()
        articles = data.get("data", {}).get("articles", [])
        for article in articles[:5]:
            code = article.get("code", "")
            title = article.get("title", "")
            release_date = article.get("releaseDate", 0)
            if not code or not title:
                continue
            if is_alerted(conn, "binance_listing", code, hours=72):
                continue
            mark_alerted(conn, "binance_listing", code)
            # 只推最近 24h 的
            age_hours = (time.time() * 1000 - release_date) / 3600000
            if age_hours > 24:
                continue
            alerts.append({
                "exchange": "Binance",
                "title": title,
                "url": f"https://www.binance.com/en/support/announcement/{code}",
                "age_hours": age_hours,
            })
        print(f"[Binance Listing] ✅ {len(articles)} 个公告, {len(alerts)} 个新推送")
    except Exception as e:
        print(f"[Binance Listing] ❌ {e}")
    return alerts

def fetch_okx_listings(conn):
    """v25: OKX 新币上线公告"""
    alerts = []
    try:
        url = "https://www.okx.com/api/v5/support/announcements"
        resp = fetch_with_retry(url, params={"annType": "announcements-new-listings"}, timeout=15)
        if not resp:
            return alerts
        data = resp.json()
        details = (data.get("data") or [{}])[0].get("details", []) if data.get("data") else []
        for article in details[:5]:
            title = article.get("title", "")
            url_path = article.get("url", "")
            p_time = article.get("pTime", 0)
            if not title or not url_path:
                continue
            key = url_path.split("/")[-1][:60]
            if is_alerted(conn, "okx_listing", key, hours=72):
                continue
            mark_alerted(conn, "okx_listing", key)
            try:
                age_hours = (time.time() * 1000 - int(p_time)) / 3600000
            except Exception:
                age_hours = 0
            if age_hours > 24:
                continue
            alerts.append({
                "exchange": "OKX",
                "title": title,
                "url": url_path if url_path.startswith("http") else f"https://www.okx.com{url_path}",
                "age_hours": age_hours,
            })
        print(f"[OKX Listing] ✅ {len(alerts)} 个新推送")
    except Exception as e:
        print(f"[OKX Listing] ❌ {e}")
    return alerts

def send_listing_alerts(alerts):
    """v26.4: HTML 安全 + 发布时间加粗"""
    if not alerts:
        return
    for a in alerts:
        ex = a.get("exchange", "Binance")
        age_str = f"{a['age_hours']:.0f} 小时前"
        msg = (f"🆕 {_esc(ex)} 新币上线!\n\n"
               f"📋 {_esc(a['title'])}\n"
               f"🕐 发布: {_b(age_str)}\n"
               f"🔗 {_esc(a['url'])}")
        try:
            tail = tail_for_alert("listing", a['url'],
                v=int(a.get('age_hours', 0)), r=0,
                src=ex.lower(), extra={"title": a['title']})
            msg += f"\n{tail}"
        except Exception as e:
            print(f"[Tail] listing error: {e}")
        send_tg(msg)
        time.sleep(1)


# ============================================================
# 🆕 v25: Snapshot 治理提案追踪
# ============================================================
SNAPSHOT_SPACES = [
    "aave.eth", "uniswapgovernance.eth", "curve.eth", "balancer.eth",
    "ens.eth", "gitcoindao.eth", "gmx.eth", "lido-snapshot.eth",
    "stgdao.eth", "arbitrumfoundation.eth", "opcollective.eth",
    "apecoin.eth", "comp-vote.eth", "cvx.eth",
]

def fetch_snapshot_proposals(conn):
    """抓取 Snapshot 活跃治理提案"""
    alerts = []
    try:
        spaces_str = '","'.join(SNAPSHOT_SPACES)
        query = f'''
        {{
          proposals(
            first: 20,
            where: {{
              space_in: ["{spaces_str}"],
              state: "active"
            }},
            orderBy: "created",
            orderDirection: desc
          ) {{
            id title space {{ id name }} start end scores_total
          }}
        }}
        '''
        resp = requests.post(
            "https://hub.snapshot.org/graphql",
            json={"query": query},
            timeout=15
        )
        if resp.status_code != 200:
            print(f"[Snapshot] ❌ HTTP {resp.status_code}")
            return alerts
        data = resp.json()
        proposals = data.get("data", {}).get("proposals", []) or []
        # 🆕 v30.13.3: 同模板提案合并为一条
        # 修复: Convex 一次发多个 Curve gauge 投票 (标题里有 ID 1404/1405/...) 各推一条 = 频道刷屏
        # 思路: 标题里的数字 normalize 成 # 做合并 key, 多个真提案合并成「标题模板 ×N」
        import re as _re
        def _normalize_title(t):
            """去掉所有数字 → 用作模板 key"""
            return _re.sub(r'\d+', '#', t or '')[:60]

        # group_key → list of proposal dicts
        groups = {}
        for p in proposals:
            space_id = p.get("space", {}).get("id", "")
            title = p.get("title", "")
            title_template = _normalize_title(title)
            group_key = f"{space_id}|{title_template}"
            groups.setdefault(group_key, []).append(p)

        for group_key, plist in groups.items():
            # 选最早结束的代表 (剩余时间最少, 用作展示主体)
            plist.sort(key=lambda x: x.get("end", 0))
            head = plist[0]
            pid = head.get("id", "")
            space_id = head.get("space", {}).get("id", "")
            title = head.get("title", "")
            # group 级去重: 同模板 1 周内只推一次 (新提案进 group 也不重推)
            if not pid or is_alerted(conn, "snapshot_group", group_key, hours=168):
                continue
            mark_alerted(conn, "snapshot_group", group_key)
            end_ts = head.get("end", 0)
            hours_left = max(0, (end_ts - time.time()) / 3600)
            if hours_left > 168:
                continue
            # 收集 group 内所有 (pid, hours_left) 用于多链接展示 (≤5 个)
            extras = []
            for p in plist[1:6]:
                e_ts = p.get("end", 0)
                e_left = max(0, (e_ts - time.time()) / 3600)
                if e_left <= 168 and p.get("id"):
                    extras.append({
                        "pid": p["id"],
                        "title": p.get("title", "")[:100],
                        "hours_left": e_left,
                    })
            alerts.append({
                "title": title[:100],
                "title_template": _normalize_title(title),
                "space": head.get("space", {}).get("name", ""),
                "space_id": space_id,
                "pid": pid,
                "hours_left": hours_left,
                "votes_usd": head.get("scores_total", 0),
                "group_count": len(plist),
                "extras": extras,
            })
        print(f"[Snapshot] ✅ {len(proposals)} 个活跃提案 (合并后 {len(groups)} 组), {len(alerts)} 条推送")
    except Exception as e:
        print(f"[Snapshot] ❌ {e}")
    return alerts

def send_snapshot_alerts(alerts):
    """v26.4: HTML 安全 + 剩余时间加粗
    🆕 v30.13.3: 同模板提案合并展示 (Convex 批量 Curve gauge 投票等)"""
    if not alerts:
        return
    alerts.sort(key=lambda x: x['hours_left'])
    for a in alerts[:5]:
        urgency = "🔥" if a['hours_left'] < 24 else "🗳️"
        url = f"https://snapshot.org/#/{a['space_id']}/proposal/{a['pid']}"
        hours_str = f"{a['hours_left']:.0f} 小时"
        group_count = a.get("group_count", 1)
        extras = a.get("extras", [])

        # 标题: group≥2 加 "×N 个同模板提案"
        title_line = _esc(a['title'])
        if group_count >= 2:
            title_line += f"  <b>(×{group_count} 同模板)</b>"

        msg = (f"{urgency} 治理投票 Governance Proposal\n\n"
               f"🏛️ {_esc(a['space'])}\n"
               f"📋 {title_line}\n"
               f"⏰ 剩余: {_b(hours_str)}\n"
               f"🔗 {_esc(url)}")

        # group 内其他链接 (折叠展示, 最多 4 个额外)
        if extras:
            msg += f"\n\n<i>其余 {len(extras)} 个同模板提案:</i>"
            for ex in extras[:4]:
                ex_url = f"https://snapshot.org/#/{a['space_id']}/proposal/{ex['pid']}"
                ex_hours = f"{ex['hours_left']:.0f}h"
                msg += f"\n  • {_esc(ex_url)} (剩 {ex_hours})"

        try:
            r = 8 if a['hours_left'] < 24 else 4
            tail = tail_for_alert("snapshot", a['pid'],
                v=int(a['hours_left']), r=r,
                src=a['space_id'], extra={"title": a['title'], "group": group_count})
            msg += f"\n{tail}"
        except Exception as e:
            print(f"[Tail] snapshot error: {e}")
        send_tg(msg)
        time.sleep(1)


# ============================================================
# 🆕 v25: Perps 资金费率异动 (Hyperliquid 全量, 免费无限)
# ============================================================
def check_funding_rates(conn):
    """检查永续合约资金费率异动 (Hyperliquid 全量, 免费无限)"""
    alerts = []
    try:
        resp = requests.post(
            "https://api.hyperliquid.xyz/info",
            json={"type": "metaAndAssetCtxs"},
            timeout=15
        )
        if resp.status_code != 200:
            print(f"[Funding] ❌ Hyperliquid HTTP {resp.status_code}")
            return alerts
        data = resp.json()
        if not isinstance(data, list) or len(data) < 2:
            print("[Funding] ❌ 数据格式异常")
            return alerts

        universe = data[0].get("universe", [])
        ctxs = data[1]

        for i, ctx in enumerate(ctxs):
            if i >= len(universe):
                break
            coin = universe[i].get("name", "")
            if not coin:
                continue
            funding = float(ctx.get("funding", 0) or 0)
            # HL 是每小时费率, 阈值 0.005% = 年化 ~44%
            if abs(funding) < 0.00005:
                continue

            alert_key = f"hl-{coin}-{'pos' if funding > 0 else 'neg'}"
            if is_alerted(conn, "funding", alert_key, hours=8):
                continue
            mark_alerted(conn, "funding", alert_key)
            apr = funding * 24 * 365 * 100  # 1h rate × 24 × 365
            alerts.append({
                "venue": "Hyperliquid", "symbol": coin, "rate": funding * 100,
                "apr": apr, "url": f"https://app.hyperliquid.xyz/trade/{coin}"
            })

        alerts.sort(key=lambda x: abs(x['apr']), reverse=True)
        print(f"[Funding] ✅ 扫描 {len(universe)} 币种, 发现 {len(alerts)} 个异动")
    except Exception as e:
        print(f"[Funding] ❌ {e}")
    return alerts

def _find_active_whales_on_coin(conn, coin, min_size_usd=500_000):
    """
    🆕 v28.1: 查询当前持有某币种仓位的鲸鱼 (跨家族合并, 按 canonical_id 聚合)
    返回 [{whale, side, total_size_usd, max_leverage}, ...] 按 total_size_usd 降序
    """
    try:
        whales = load_whale_list()
        if not whales:
            return []

        # 建立 address -> whale 映射 (含马甲指向主鲸)
        addr_to_whale = {}
        primary_lookup = {}  # canonical_id -> primary whale
        for w in whales:
            canonical = _whale_canonical_id(w)
            wid = w.get("id") or w.get("name", "")
            if canonical == wid:
                primary_lookup[canonical] = w
            for a in w.get("addresses", []):
                if a and a.startswith("0x"):
                    addr_to_whale[a.lower()] = canonical

        if not addr_to_whale:
            return []

        # 查询所有这些地址的最新持仓 (只取该 coin)
        placeholders = ",".join("?" for _ in addr_to_whale)
        rows = conn.execute(
            f"SELECT address, side, size_coin, size_usd, leverage "
            f"FROM whale_positions "
            f"WHERE coin=? AND address IN ({placeholders}) "
            f"AND recorded_at = (SELECT MAX(recorded_at) FROM whale_positions p2 "
            f"                   WHERE p2.address = whale_positions.address AND p2.coin = whale_positions.coin)",
            (coin, *addr_to_whale.keys())
        ).fetchall()

        # 按 canonical_id 聚合
        by_canonical = {}
        for addr, side, sz_coin, sz_usd, lev in rows:
            if not sz_coin or sz_coin <= 0 or not sz_usd or sz_usd < min_size_usd / 10:
                continue  # 小仓位直接过滤
            canonical = addr_to_whale.get(addr.lower())
            if not canonical:
                continue
            # 同一家族的同方向仓位合并
            key = (canonical, side)
            if key not in by_canonical:
                by_canonical[key] = {
                    "canonical": canonical, "side": side,
                    "total_size_usd": 0, "max_leverage": 0
                }
            by_canonical[key]["total_size_usd"] += sz_usd
            by_canonical[key]["max_leverage"] = max(by_canonical[key]["max_leverage"], lev or 0)

        # 过滤 + 附上 whale 对象 + 排序
        results = []
        for (canonical, side), info in by_canonical.items():
            if info["total_size_usd"] < min_size_usd:
                continue
            whale = primary_lookup.get(canonical)
            if not whale:
                continue
            results.append({
                "whale": whale, "side": side,
                "total_size_usd": info["total_size_usd"],
                "max_leverage": info["max_leverage"],
            })
        results.sort(key=lambda x: x["total_size_usd"], reverse=True)
        return results
    except Exception as e:
        print(f"[WhaleOnCoin] {coin} 查询错误: {e}")
        return []


def _fmt_whales_on_coin_block(whales_on_coin, max_show=3):
    """🆕 v28.1: 格式化鲸鱼区块, 给 funding/oi/price 告警附加"""
    if not whales_on_coin:
        return ""
    lines = ["\n🐋 当前持仓鲸鱼:"]
    for w in whales_on_coin[:max_show]:
        whale = w["whale"]
        emoji = whale.get("emoji", "🐋")
        name = whale.get("name", whale.get("id", "?"))
        side_cn = "多" if w["side"] == "long" else "空"
        side_emoji = "🟢" if w["side"] == "long" else "🔴"
        size_str = _fmt_whale_size_usd(w["total_size_usd"])
        lev_str = f" {w['max_leverage']:.0f}x" if w["max_leverage"] > 0 else ""
        lines.append(f"  {side_emoji} {emoji} {_esc(name)} {side_cn} {_b(size_str)}{lev_str}")
    if len(whales_on_coin) > max_show:
        lines.append(f"  <i>... 另 {len(whales_on_coin) - max_show} 只鲸鱼持仓</i>")
    return "\n".join(lines)


def send_funding_alerts(alerts, conn=None):
    """v26.4: HTML 安全 + 关键数字加粗. v28.1: 鲸鱼交叉信息 + Hyperliquid 品牌标签"""
    if not alerts:
        return
    for a in alerts[:5]:
        direction = "🟢 多头" if a['rate'] < 0 else "🔴 空头"
        rate_str = f"{a['rate']:.4f}%"
        apr_str = f"{a['apr']:+.0f}%"
        # v28.1: 品牌前缀统一 — Hyperliquid 盘口
        venue_name = a.get('venue', 'Hyperliquid')
        is_hl = 'hyperliquid' in venue_name.lower()
        brand_tag = "🔶 Hyperliquid 盘口" if is_hl else f"📊 {_esc(venue_name)}"
        msg = (f"⚡ <b>资金费率异动</b> · Funding Rate\n"
               f"{brand_tag}\n\n"
               f"🪙 {_esc(a['symbol'])} · {direction}有优势\n"
               f"📊 费率: {_b(rate_str)} (年化 {_b(apr_str)})\n"
               f"💡 {'做多可收费率' if a['rate'] < 0 else '做空可收费率'}")

        # v28.1: 附加当前持仓该币的鲸鱼 (独家信号)
        if conn is not None and is_hl:
            try:
                whales_on = _find_active_whales_on_coin(conn, a['symbol'])
                whale_block = _fmt_whales_on_coin_block(whales_on)
                if whale_block:
                    msg += whale_block
            except Exception as e:
                print(f"[Funding] 鲸鱼交叉查询错误: {e}")

        msg += f"\n\n🔗 {_esc(a['url'])}\n📲 开户: {HL_REFERRAL}"
        try:
            tail = tail_for_alert("funding", a['symbol'],
                v=int(a.get('apr', 0)), r=min(10, abs(int(a.get('apr', 0) / 50))),
                src=a.get('venue', 'hyperliquid').lower(),
                extra={"rate": a['rate'], "apr": a['apr']})
            msg += f"\n{tail}"
        except Exception as e:
            print(f"[Tail] funding error: {e}")
        send_tg(msg)
        time.sleep(1)


# ============================================================
# 🆕 v25+: OI 异动监控 (Hyperliquid 全量)
# ============================================================
# 🆕 v30.2: 旧 OI 模块降格为主流币 OI 异动 (避免与赏金哨重叠)
# 妖币赛道交给赏金哨, 这里只追踪主流币的 OI 异动
OI_MAJOR_COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "LINK", "TON"]
OI_MAJOR_THRESHOLD_PCT = 10  # 主流币 OI 涨 10% 是大事

def check_oi_anomalies(conn):
    """v30.2: 仅追踪主流币 OI 异动 (HL), 妖币让位给赏金哨"""
    alerts = []
    try:
        resp = requests.post(
            "https://api.hyperliquid.xyz/info",
            json={"type": "metaAndAssetCtxs"},
            timeout=15
        )
        if resp.status_code != 200:
            print(f"[OI] ❌ Hyperliquid HTTP {resp.status_code}")
            return alerts
        data = resp.json()
        if not isinstance(data, list) or len(data) < 2:
            print("[OI] ❌ 数据格式异常")
            return alerts

        universe = data[0].get("universe", [])
        ctxs = data[1]
        checked = 0

        for i, ctx in enumerate(ctxs):
            if i >= len(universe):
                break
            coin = universe[i].get("name", "")
            if not coin:
                continue
            # OI (币) × 标记价格 = USD OI
            oi_coins = float(ctx.get("openInterest", 0) or 0)
            mark_px = float(ctx.get("markPx", 0) or 0)
            if oi_coins <= 0 or mark_px <= 0:
                continue
            oi_usd = oi_coins * mark_px

            # v30.2: 只看主流币白名单
            if coin not in OI_MAJOR_COINS:
                continue
            if oi_usd < OI_MIN_USD:
                continue
            checked += 1

            symbol = f"HL-{coin}"
            row = conn.execute(
                "SELECT oi_value FROM oi_history WHERE symbol=?", (symbol,)
            ).fetchone()

            conn.execute(
                "INSERT OR REPLACE INTO oi_history (symbol, oi_value, recorded_at) VALUES (?,?,datetime('now'))",
                (symbol, oi_usd)
            )

            if not row or row[0] <= 0:
                continue
            prev_oi = row[0]
            change_pct = ((oi_usd - prev_oi) / prev_oi) * 100

            if abs(change_pct) < OI_MAJOR_THRESHOLD_PCT:
                continue

            alert_key = f"oi-{coin}-{'up' if change_pct > 0 else 'down'}"
            if is_alerted(conn, "oi", alert_key, hours=8):
                continue
            mark_alerted(conn, "oi", alert_key)

            alerts.append({
                "symbol": coin,
                "oi": oi_usd,
                "prev_oi": prev_oi,
                "change_pct": change_pct,
                "url": f"https://app.hyperliquid.xyz/trade/{coin}",
            })

        conn.commit()
        alerts.sort(key=lambda x: abs(x['change_pct']), reverse=True)
        print(f"[OI] ✅ 扫描 {checked} 币种 (OI≥${OI_MIN_USD/1e6:.0f}M), 发现 {len(alerts)} 个异动")
    except Exception as e:
        print(f"[OI] ❌ {e}")
    return alerts

def send_oi_alerts(alerts, conn=None):
    """v26.4: HTML 安全 + OI 变化加粗. v28.1: 鲸鱼交叉 + Hyperliquid 品牌"""
    if not alerts:
        return
    for a in alerts[:8]:
        direction = "📈 暴涨" if a['change_pct'] > 0 else "📉 暴跌"
        emoji = "🚨" if abs(a['change_pct']) > 30 else "⚠️"
        change_str = f"{a['change_pct']:+.1f}%"
        curr_str = f"${a['oi']/1e6:,.1f}M"
        prev_str = f"${a['prev_oi']/1e6:,.1f}M"
        msg = (f"{emoji} <b>OI 异动</b> · Open Interest\n"
               f"🔶 Hyperliquid 盘口\n\n"
               f"🪙 {_esc(a['symbol'])} · {direction}\n"
               f"📊 OI 变化: {_b(change_str)}\n"
               f"📦 当前: {_b(curr_str)} → 前次: {prev_str}\n"
               f"💡 {'大量新仓位入场' if a['change_pct'] > 0 else '大量平仓/爆仓'}")

        # v28.1: 附加当前持仓该币的鲸鱼
        if conn is not None:
            try:
                whales_on = _find_active_whales_on_coin(conn, a['symbol'])
                whale_block = _fmt_whales_on_coin_block(whales_on)
                if whale_block:
                    msg += whale_block
            except Exception as e:
                print(f"[OI] 鲸鱼交叉查询错误: {e}")

        msg += f"\n\n🔗 {_esc(a['url'])}\n📲 开户: {HL_REFERRAL}"
        try:
            tail = tail_for_alert("oi", a['symbol'],
                v=int(a.get('change_pct', 0)),
                r=min(10, int(abs(a.get('change_pct', 0)) / 5)),
                src="hyperliquid",
                extra={"oi": a['oi'], "prev_oi": a['prev_oi']})
            msg += f"\n{tail}"
        except Exception as e:
            print(f"[Tail] oi error: {e}")
        send_tg(msg)
        time.sleep(1)

# ============================================================
# 🆕 v25+: 价格异动监控 (Hyperliquid 全量 + OI/Funding 上下文)
# ============================================================
def check_price_anomalies(conn):
    """检测价格飙升/暴跌, 附带 OI/Funding 丰富上下文"""
    alerts = []
    try:
        resp = requests.post(
            "https://api.hyperliquid.xyz/info",
            json={"type": "metaAndAssetCtxs"},
            timeout=15
        )
        if resp.status_code != 200:
            return alerts
        data = resp.json()
        if not isinstance(data, list) or len(data) < 2:
            return alerts

        universe = data[0].get("universe", [])
        ctxs = data[1]
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stored = 0

        for i, ctx in enumerate(ctxs):
            if i >= len(universe):
                break
            coin = universe[i].get("name", "")
            if not coin:
                continue
            mark_px = float(ctx.get("markPx", 0) or 0)
            oi_coins = float(ctx.get("openInterest", 0) or 0)
            funding = float(ctx.get("funding", 0) or 0)
            if mark_px <= 0:
                continue
            oi_usd = oi_coins * mark_px

            # 存储当前快照 (每次扫描)
            conn.execute(
                "INSERT INTO price_history (symbol, price, oi_usd, funding_rate, recorded_at) VALUES (?,?,?,?,?)",
                (coin, mark_px, oi_usd, funding, now_str)
            )
            stored += 1

            # 只检测 OI > $500K 的币 (过滤垃圾)
            if oi_usd < 500_000:
                continue

            # 拿历史价格: 1h, 4h, 24h
            periods = {
                "1h": "-1 hours",
                "4h": "-4 hours",
                "24h": "-24 hours",
            }
            price_changes = {}
            for label, offset in periods.items():
                row = conn.execute(
                    "SELECT price FROM price_history WHERE symbol=? AND recorded_at <= datetime('now', ?) ORDER BY recorded_at DESC LIMIT 1",
                    (coin, offset)
                ).fetchone()
                if row and row[0] > 0:
                    price_changes[label] = ((mark_px - row[0]) / row[0]) * 100
                else:
                    price_changes[label] = None

            # 触发条件: 1h >8% 或 4h >15% 或 24h >25%
            triggered = False
            trigger_reason = ""
            if price_changes.get("1h") is not None and abs(price_changes["1h"]) > 8:
                triggered = True
                trigger_reason = f"1h {price_changes['1h']:+.1f}%"
            elif price_changes.get("4h") is not None and abs(price_changes["4h"]) > 15:
                triggered = True
                trigger_reason = f"4h {price_changes['4h']:+.1f}%"
            elif price_changes.get("24h") is not None and abs(price_changes["24h"]) > 25:
                triggered = True
                trigger_reason = f"24h {price_changes['24h']:+.1f}%"

            if not triggered:
                continue

            # 冷却 4 小时
            direction = "up" if (price_changes.get("1h") or price_changes.get("4h") or 0) > 0 else "down"
            alert_key = f"price-{coin}-{direction}"
            if is_alerted(conn, "price_surge", alert_key, hours=4):
                continue
            mark_alerted(conn, "price_surge", alert_key)

            # 拿 OI 历史: 1d, 7d, 30d
            oi_changes = {}
            for label, offset in [("1d", "-1 days"), ("7d", "-7 days"), ("30d", "-30 days")]:
                row = conn.execute(
                    "SELECT oi_usd FROM price_history WHERE symbol=? AND recorded_at <= datetime('now', ?) ORDER BY recorded_at DESC LIMIT 1",
                    (coin, offset)
                ).fetchone()
                if row and row[0] > 0:
                    oi_changes[label] = ((oi_usd - row[0]) / row[0]) * 100
                else:
                    oi_changes[label] = None

            alerts.append({
                "symbol": coin,
                "price": mark_px,
                "trigger": trigger_reason,
                "price_1h": price_changes.get("1h"),
                "price_4h": price_changes.get("4h"),
                "price_24h": price_changes.get("24h"),
                "oi_usd": oi_usd,
                "oi_1d": oi_changes.get("1d"),
                "oi_7d": oi_changes.get("7d"),
                "oi_30d": oi_changes.get("30d"),
                "funding": funding,
                "funding_apr": funding * 24 * 365 * 100,
                "direction": direction,
            })

        conn.commit()
        alerts.sort(key=lambda x: abs(float(x['trigger'].split('%')[0].split()[-1])), reverse=True)
        print(f"[Price] ✅ 存储 {stored} 币种快照, 发现 {len(alerts)} 个价格异动")
    except Exception as e:
        print(f"[Price] ❌ {e}")
    return alerts

def generate_price_chart(conn, symbol, hours=24):
    """v26.5: 新闻卡片式图表 (样式 6b + D 水印)
    顶部绿/红条 + 三列信息卡 + 价格+OI 图 + @币世赏金台 水印 + 底部 footer
    """
    if not HAS_MATPLOTLIB:
        return None
    try:
        rows = conn.execute(
            "SELECT price, oi_usd, recorded_at FROM price_history "
            "WHERE symbol=? AND recorded_at >= datetime('now', ? || ' hours') "
            "ORDER BY recorded_at ASC",
            (symbol, f"-{hours}")
        ).fetchall()
        if len(rows) < 3:
            return None

        prices = [r[0] for r in rows]
        ois = [r[1] / 1e6 for r in rows]  # 转 $M

        # 加载中文字体 (SimHei 生产环境 / Noto CJK 本地)
        font_path = ensure_chinese_font()
        cn_font = None
        if font_path:
            try:
                font_manager.fontManager.addfont(font_path)
                cn_font = font_manager.FontProperties(fname=font_path)
            except Exception:
                pass

        # v26.5: 关键指标计算
        current_price = prices[-1]
        low_price = min(prices)
        low_idx = prices.index(low_price)
        first_price = prices[0]
        pct_total = ((current_price - first_price) / first_price) * 100
        change_from_low = ((current_price - low_price) / low_price) * 100 if low_price > 0 else 0

        # 价格+OI 突破区间 (找 OI 显著增长的起点)
        # 简化: 最后 1/3 如果 OI 比前 2/3 高 20%+, 认为是突破段
        n = len(rows)
        breakout_start = n  # 默认无突破
        if n >= 6:
            mid = n * 2 // 3
            prev_avg_oi = sum(ois[:mid]) / mid if mid > 0 else 0
            last_avg_oi = sum(ois[mid:]) / (n - mid) if n > mid else 0
            if prev_avg_oi > 0 and last_avg_oi / prev_avg_oi > 1.2:
                breakout_start = mid

        oi_change = ((ois[-1] / ois[0]) - 1) * 100 if ois[0] > 0 else 0
        current_oi = ois[-1]

        # 上涨/下跌决定主色
        is_up = pct_total >= 0
        if is_up:
            main_color = '#10b981'
            main_color_dark = '#059669'
            banner_color = '#10b981'
            banner_text = f"▲  突破信号 · BREAKOUT" if change_from_low >= 10 else f"▲  价格飙升 · RALLY"
        else:
            main_color = '#ef4444'
            main_color_dark = '#dc2626'
            banner_color = '#ef4444'
            banner_text = f"▼  价格暴跌 · DUMP"

        # 字体 helpers
        fp = cn_font if cn_font else None
        def _font(**kw):
            if fp:
                kw['fontproperties'] = fp
            return kw

        # ============ 构造画布 (卡片式布局) ============
        fig = plt.figure(figsize=(12, 8), dpi=130, facecolor='#ffffff')

        # 顶部 banner
        top_bar = fig.add_axes([0, 0.92, 1, 0.08])
        top_bar.set_facecolor(banner_color)
        top_bar.set_xticks([]); top_bar.set_yticks([])
        for s in top_bar.spines.values():
            s.set_visible(False)
        top_bar.text(0.5, 0.5, banner_text, ha='center', va='center',
                     fontsize=16, fontweight='bold', color='white',
                     transform=top_bar.transAxes, **_font())

        # 信息卡 (三列)
        info_ax = fig.add_axes([0.05, 0.62, 0.9, 0.28])
        info_ax.set_facecolor('#f9fafb')
        info_ax.set_xticks([]); info_ax.set_yticks([])
        for s in info_ax.spines.values():
            s.set_color('#e5e7eb'); s.set_linewidth(1)

        # 左: 币种 + 当前价
        info_ax.text(0.03, 0.75, symbol[:12], fontsize=32, fontweight='bold',
                     color='#111827', transform=info_ax.transAxes, **_font())
        info_ax.text(0.03, 0.30, f'${current_price:.4f}', fontsize=22, fontweight='bold',
                     color=main_color, transform=info_ax.transAxes)
        if change_from_low > 0:
            info_ax.text(0.03, 0.08, f'↑ 较 {hours}h 低点 +{change_from_low:.1f}%',
                         fontsize=11, color='#6b7280', transform=info_ax.transAxes, **_font())

        # 中: 总涨跌幅
        info_ax.text(0.40, 0.75, f'{hours}h 涨跌', fontsize=11, color='#6b7280',
                     transform=info_ax.transAxes, **_font())
        info_ax.text(0.40, 0.45, f'{pct_total:+.1f}%', fontsize=24, fontweight='bold',
                     color=main_color, transform=info_ax.transAxes)

        # 右: OI 变化
        info_ax.text(0.67, 0.75, 'OI 变化', fontsize=11, color='#6b7280',
                     transform=info_ax.transAxes, **_font())
        info_ax.text(0.67, 0.45, f'{oi_change:+.0f}%', fontsize=24, fontweight='bold',
                     color='#ef4444' if oi_change > 0 else '#6b7280',
                     transform=info_ax.transAxes)
        info_ax.text(0.67, 0.20, f'${current_oi:.1f}M {"新流入" if oi_change > 0 else "当前"}',
                     fontsize=11, color='#6b7280', transform=info_ax.transAxes, **_font())

        # 图表区
        chart_ax = fig.add_axes([0.08, 0.12, 0.88, 0.42])
        chart_ax.set_facecolor('#ffffff')
        chart_ax.grid(True, alpha=0.08, color='#9ca3af')
        for s in chart_ax.spines.values():
            s.set_color('#e5e7eb')

        # 价格线
        x = list(range(n))
        chart_ax.fill_between(x, prices, alpha=0.15, color=main_color)
        chart_ax.plot(x, prices, color=main_color_dark, linewidth=2.5)
        chart_ax.set_ylabel('价格 ($)', fontsize=10, color='#6b7280', **_font())
        chart_ax.tick_params(axis='y', labelcolor='#6b7280')

        # 突破区阴影 (只在涨势时画, 并且有突破)
        if is_up and breakout_start < n:
            chart_ax.axvspan(breakout_start, n-1, alpha=0.08, color='#ef4444')

        # 24h 低点标注 (仅涨势时有意义)
        if is_up and change_from_low > 5:
            chart_ax.scatter([low_idx], [low_price], color='#ef4444', s=140, zorder=5,
                             edgecolors='white', linewidths=2, marker='v')

            # 🆕 v29.1: FOMO 箭头 — 从 24h 低点画弧形箭头到现价 + 大涨幅徽章
            # 涨幅越大颜色越深 + 三角符号越多
            if change_from_low >= 50:
                fomo_color = '#dc2626'   # 深红 (狂涨)
                badge_prefix = '▲▲▲'
            elif change_from_low >= 20:
                fomo_color = '#ef4444'   # 红 (大涨)
                badge_prefix = '▲▲'
            else:
                fomo_color = '#f59e0b'   # 橙 (微涨)
                badge_prefix = '▲'

            # 弧形箭头 (低点 → 现价), 视觉冲击力强
            try:
                chart_ax.annotate(
                    '',
                    xy=(n - 1, current_price),
                    xytext=(low_idx, low_price),
                    arrowprops=dict(
                        arrowstyle='->',
                        color=fomo_color,
                        lw=2.8,
                        alpha=0.9,
                        mutation_scale=28,
                        connectionstyle='arc3,rad=-0.18',
                        shrinkA=10, shrinkB=10,
                    ),
                    zorder=6,
                )
            except Exception:
                pass  # 老 matplotlib 不支持某些参数, 静默降级

            # 涨幅徽章 (右上, 高对比) — 让 FOMO 一眼看到
            badge_text = f'{badge_prefix} +{change_from_low:.1f}%'
            chart_ax.text(
                0.97, 0.93, badge_text,
                transform=chart_ax.transAxes,
                fontsize=22, fontweight='bold', color='white',
                ha='right', va='top', zorder=10,
                bbox=dict(boxstyle='round,pad=0.5',
                          facecolor=fomo_color,
                          edgecolor='white', linewidth=2.5, alpha=0.96),
            )

        # OI 柱 (双色: 前段蓝, 突破段红)
        chart_ax2 = chart_ax.twinx()
        if breakout_start < n:
            colors_oi = ['#6366f1' if i < breakout_start else '#ef4444' for i in range(n)]
        else:
            colors_oi = ['#6366f1'] * n
        chart_ax2.bar(x, ois, alpha=0.25, color=colors_oi, width=0.8)
        chart_ax2.set_ylabel('OI ($M)', fontsize=10, color='#6b7280', **_font())
        chart_ax2.tick_params(axis='y', labelcolor='#6b7280')
        for s in chart_ax2.spines.values():
            s.set_color('#e5e7eb')

        # X 轴标签
        if n > 6:
            step = max(1, n // 5)
            tick_idxs = list(range(0, n, step))
            if tick_idxs[-1] != n - 1:
                tick_idxs.append(n - 1)
            labels = []
            for i in tick_idxs:
                try:
                    t = datetime.strptime(rows[i][2][:16], "%Y-%m-%d %H:%M")
                    labels.append(t.strftime("%m/%d %H:%M"))
                except Exception:
                    labels.append("")
            chart_ax.set_xticks(tick_idxs)
            chart_ax.set_xticklabels(labels, fontsize=8, color='#6b7280')

        # 🎨 D 水印: 中轴横排 @币世赏金台 (浅色 5% 透明度)
        chart_ax.text(0.5, 0.5, '@币世赏金台',
                      transform=chart_ax.transAxes,
                      fontsize=38, color='#000000', alpha=0.05,
                      ha='center', va='center', rotation=0,
                      fontweight='bold', zorder=3, **_font())

        # 底部 footer
        footer_ax = fig.add_axes([0, 0, 1, 0.07])
        footer_ax.set_facecolor('#f9fafb')
        footer_ax.set_xticks([]); footer_ax.set_yticks([])
        for s in footer_ax.spines.values():
            s.set_visible(False)
        footer_ax.text(0.03, 0.5, '@币世赏金台', fontsize=11, fontweight='bold',
                       color='#111827', transform=footer_ax.transAxes,
                       va='center', **_font())
        now_str = datetime.now().strftime("%Y-%m-%d")
        footer_ax.text(0.97, 0.5, f'{now_str} · Hyperliquid', fontsize=10,
                       color='#6b7280', transform=footer_ax.transAxes,
                       va='center', ha='right', **_font())

        # 导出
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=130, bbox_inches='tight', facecolor='#ffffff')
        buf.seek(0)
        plt.close(fig)
        return buf.getvalue()
    except Exception as e:
        print(f"[PriceChart] ❌ {symbol}: {e}")
        import traceback; traceback.print_exc()
        return None

def send_price_alerts(alerts, conn=None):
    if not alerts:
        return
    for a in alerts[:5]:
        emoji = "🟢" if a['direction'] == 'up' else "🔴"
        direction_cn = "飙升" if a['direction'] == 'up' else "暴跌"

        # v26.3: HTML 模式, 关键数字加粗 (局部变量避免 f-string 嵌套)
        price_str = f"${a['price']:.4f}"
        oi_str = f"${a['oi_usd']/1e6:,.1f}M"
        funding_apr_str = f"{a['funding_apr']:+.0f}%"

        msg = f"{emoji} <b>价格异动</b> · Price Alert\n"
        msg += f"🔶 Hyperliquid 盘口 · {_esc(a['symbol'])}\n\n"
        msg += f"💰 当前价格: {_b(price_str)}\n"
        msg += f"⚡ 触发: {_b(_esc(a['trigger']))}\n\n"

        # 价格变化 (变化值加粗)
        msg += "📊 价格变化:\n"
        for label, val in [("1h", a['price_1h']), ("4h", a['price_4h']), ("24h", a['price_24h'])]:
            if val is not None:
                arrow = "📈" if val > 0 else "📉"
                val_str = f"{val:+.1f}%"
                msg += f"  {arrow} {label}: {_b(val_str)}\n"
            else:
                msg += f"  ⏳ {label}: 数据积累中\n"

        # OI 上下文 (当前 OI 加粗)
        msg += "\n📦 OI 变化:\n"
        msg += f"  💎 当前 OI: {_b(oi_str)}\n"
        for label, val in [("1d", a['oi_1d']), ("7d", a['oi_7d']), ("30d", a['oi_30d'])]:
            if val is not None:
                arrow = "📈" if val > 0 else "📉"
                val_str = f"{val:+.1f}%"
                msg += f"  {arrow} {label}: {_b(val_str)}\n"
            else:
                msg += f"  ⏳ {label}: 数据积累中\n"

        # Funding
        msg += f"\n💱 资金费率: {a['funding']*100:.4f}%/h (年化 {_b(funding_apr_str)})\n"

        # 信号解读
        if a['direction'] == 'up' and a.get('oi_1d') and a['oi_1d'] > 10:
            msg += "🔥 价格+OI 同涨 → 新多仓入场, 趋势可能延续\n"
        elif a['direction'] == 'up' and a.get('oi_1d') and a['oi_1d'] < -5:
            msg += "⚠️ 价格涨+OI 跌 → 空头爆仓驱动, 小心回调\n"
        elif a['direction'] == 'down' and a.get('oi_1d') and a['oi_1d'] > 10:
            msg += "🔥 价格跌+OI 涨 → 新空仓入场, 下跌可能加速\n"
        elif a['direction'] == 'down' and a.get('oi_1d') and a['oi_1d'] < -5:
            msg += "⚠️ 价格跌+OI 跌 → 多头爆仓, 可能接近底部\n"

        # 🆕 v28.1: 附加当前持仓该币的鲸鱼 (独家信号)
        if conn is not None:
            try:
                whales_on = _find_active_whales_on_coin(conn, a['symbol'])
                whale_block = _fmt_whales_on_coin_block(whales_on)
                if whale_block:
                    msg += whale_block + "\n"
            except Exception as e:
                print(f"[Price] 鲸鱼交叉查询错误: {e}")

        msg += f"\n🔗 https://app.hyperliquid.xyz/trade/{_esc(a['symbol'])}"
        msg += f"\n📲 开户: {HL_REFERRAL}"

        # v26: 尾行标签
        try:
            change_24h = a.get('price_24h') or a.get('price_4h') or 0
            tail = tail_for_alert("price", a['symbol'],
                v=int((change_24h or 0) * 10),
                r=min(10, int(abs(change_24h or 0) / 3)),
                src="hyperliquid",
                extra={"price": a['price'], "direction": a['direction'], "trigger": a['trigger']})
            msg += f"\n{tail}"
        except Exception as e:
            print(f"[Tail] price error: {e}")

        # 先发图表 (如果有历史数据), 然后发详细文字
        chart_sent = False
        if conn:
            chart = generate_price_chart(conn, a['symbol'], hours=24)
            if chart:
                # v26.5: 方案 B 温和版 caption (技术术语 + 事实数据, 非预测)
                signal_cn = "突破信号 Breakout" if a['direction'] == 'up' else "跌破信号 Breakdown"
                direction_emoji = "🟢" if a['direction'] == 'up' else "🔴"

                # 第 1 行: 币 · 触发 · 信号
                line1 = f"{direction_emoji} {_esc(a['symbol'])} · {_b(_esc(a['trigger']))} · {signal_cn}"

                # 第 2 行: 现价 · (如果涨的话) 24h 低点
                price_line = f"💎 现价 {_b(price_str)}"
                # 尝试从 price_history 拿 24h 低点, 仅当 direction=up 时显示
                try:
                    if conn and a['direction'] == 'up':
                        low_row = conn.execute(
                            "SELECT MIN(price) FROM price_history WHERE symbol=? "
                            "AND recorded_at >= datetime('now', '-24 hours')",
                            (a['symbol'],)
                        ).fetchone()
                        if low_row and low_row[0] and low_row[0] < a['price']:
                            low_str = f"${low_row[0]:.4f}"
                            price_line += f" · 24h低 {_b(low_str)}"
                except Exception:
                    pass

                # 第 3 行: OI + 信号解读 (只在价格+OI 同涨时显示"新资金流入")
                oi_line = f"📊 OI {_b(oi_str)}"
                if a.get('oi_1d') and a['oi_1d'] > 10 and a['direction'] == 'up':
                    oi_line += " · 新资金流入 · 价格+OI 同涨"
                elif a.get('oi_1d') and a['oi_1d'] < -5 and a['direction'] == 'down':
                    oi_line += " · 大量平仓/爆仓"

                caption = (f"{line1}\n"
                           f"{price_line}\n"
                           f"{oi_line}\n"
                           f"🔗 https://app.hyperliquid.xyz/trade/{_esc(a['symbol'])}\n"
                           f"📲 {HL_REFERRAL}")
                send_tg_photo(chart, caption)
                chart_sent = True
                time.sleep(0.5)
        send_tg(msg)
        time.sleep(1)

        # 🆕 v29.1: 入队信号战绩追推 (4h/24h 后自动复盘)
        if conn is not None:
            try:
                _enqueue_price_alert_followup(conn, a)
            except Exception as e:
                print(f"[PriceFollowup] enqueue 错误: {e}")

# ============================================================
def find_cross_chain_arb(all_b, conn):
    """找同协议在不同链上的 APY 差异"""
    alerts = []
    # 按 (project, symbol) 分组
    groups = {}
    for b in all_b:
        if b.get('s') != 'DeFiLlama':
            continue
        if not is_defi(b):
            continue
        apy = b.get('apy', 0)
        if apy <= 0 or apy > 80:
            continue
        org = b.get('org', '')
        symbol = (b.get('symbol', '') or '').strip()
        chain = b.get('chain', '')
        tvl = b.get('tvl', 0)
        if not org or not symbol or not chain or tvl < 1e6:
            continue
        # 排除 LP 池
        if '-' in symbol or '/' in symbol:
            continue
        key = f"{org}|{symbol}"
        groups.setdefault(key, []).append({
            "chain": chain, "apy": apy, "tvl": tvl, "url": b.get('u', '')
        })

    for key, pools in groups.items():
        if len(pools) < 2:
            continue
        pools.sort(key=lambda x: x['apy'], reverse=True)
        best, worst = pools[0], pools[-1]
        spread = best['apy'] - worst['apy']
        # 差 >5pp 且最高 >=2x 最低
        if spread < 5 or best['apy'] < worst['apy'] * 2:
            continue
        org, symbol = key.split("|")
        alert_key = f"{org}-{symbol}-{best['chain']}-{worst['chain']}"
        if is_alerted(conn, "crosschain_arb", alert_key, hours=24):
            continue
        mark_alerted(conn, "crosschain_arb", alert_key)
        alerts.append({
            "org": org, "symbol": symbol,
            "best": best, "worst": worst, "spread": spread,
        })

    print(f"[CrossChain Arb] ✅ 发现 {len(alerts)} 个套利机会")
    return alerts

def send_arb_alerts(alerts):
    """v26.4: HTML 安全 + APY 差距加粗"""
    if not alerts:
        return
    alerts.sort(key=lambda x: x['spread'], reverse=True)
    for a in alerts[:3]:
        best_apy_str = f"{a['best']['apy']:.2f}%"
        worst_apy_str = f"{a['worst']['apy']:.2f}%"
        best_tvl_str = f"${a['best']['tvl']/1e6:.0f}M"
        worst_tvl_str = f"${a['worst']['tvl']/1e6:.0f}M"
        spread_str = f"+{a['spread']:.2f}pp"
        msg = (f"🔀 跨链 APY 套利 Cross-Chain Arbitrage\n\n"
               f"🏛️ {_esc(a['org'])} | {_esc(a['symbol'])}\n"
               f"🥇 {_esc(a['best']['chain'])}: {_b(best_apy_str)} (TVL {best_tvl_str})\n"
               f"🥉 {_esc(a['worst']['chain'])}: {worst_apy_str} (TVL {worst_tvl_str})\n"
               f"📊 差距: {_b(spread_str)}\n"
               f"🔗 {_esc(a['best']['url'])}")
        try:
            tail = tail_for_alert("arb", f"{a['org']}-{a['symbol']}",
                v=int(a['spread'] * 100),
                r=max(1, min(10, 10 - int(a['spread'] / 2))),
                src=a['org'].lower(),
                extra={"best_chain": a['best']['chain'], "worst_chain": a['worst']['chain'],
                       "best_apy": a['best']['apy'], "worst_apy": a['worst']['apy']})
            msg += f"\n{tail}"
        except Exception as e:
            print(f"[Tail] arb error: {e}")
        send_tg(msg)
        time.sleep(1)


# ============================================================
# 🐋 v27: Hyperliquid 鲸鱼追踪
# ============================================================
# 配置: /app/whale_list.json (手机端 GitHub 直接编辑)
# 数据源: Hyperliquid REST API (免费无限)
# 推送: 仓位变化 >$500K 或 >10%, 同鲸鱼 30 分钟冷却

WHALE_LIST_PATH = os.environ.get("WHALE_LIST_PATH", "whale_list.json")
WHALE_CHANGE_MIN_USD = 500_000  # 仓位变化 >$500K 才推
WHALE_CHANGE_MIN_PCT = 10       # 仓位变化 >10% 才推 (二选一满足即可)
WHALE_COOLDOWN_MIN = 30         # 同鲸鱼 30 分钟冷却

# 🆕 v27.1-A 清算倒计时 (3 档预警, 只升档触发)
WHALE_LIQ_TIER_YELLOW = 15       # 距清算 <15% 黄色预警 (早期关注)
WHALE_LIQ_TIER_ORANGE = 8        # <8% 橙色警告 (显著风险)
WHALE_LIQ_TIER_RED = 3           # <3% 红色爆仓临近 (极度危险)
WHALE_LIQ_MIN_USD = 100_000      # 仓位 <$100K 不推 (避免噪音)
WHALE_LIQ_RESET_HOURS = 6        # 6 小时无 liq 告警视为重置 (重新开始计档)
# 🆕 v30.12: 单鲸鱼全局冷却 — 不分币种, 4h 内同一鲸鱼最多推 1 条 liq alert (防单人刷屏)
WHALE_LIQ_GLOBAL_COOLDOWN_HOURS = _env_int("WHALE_LIQ_GLOBAL_COOLDOWN_HOURS", "4")

# 🆕 v28.4: 漫画图触发阈值
WHALE_IMAGE_BIG_ADD_USD = 5_000_000  # 加仓 ≥$5M 才配"加仓时刻"图

_whale_list_cache = None
_whale_list_mtime = 0

def load_whale_list():
    """加载 whale_list.json, mtime 检测热重载"""
    global _whale_list_cache, _whale_list_mtime
    try:
        # 尝试多个路径
        paths = [WHALE_LIST_PATH, "/app/whale_list.json", "./whale_list.json"]
        found_path = None
        for p in paths:
            if os.path.exists(p):
                found_path = p
                break
        if not found_path:
            if _whale_list_cache is None:
                print(f"[Whale] ⚠️ whale_list.json 未找到, 已跳过鲸鱼追踪")
            return []

        mtime = os.path.getmtime(found_path)
        if _whale_list_cache is not None and mtime == _whale_list_mtime:
            return _whale_list_cache  # 未修改, 复用缓存

        with open(found_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        whales = [w for w in data.get("whales", []) if w.get("active", True)]
        _whale_list_cache = whales
        _whale_list_mtime = mtime
        total_addrs = sum(len(w.get("addresses", [])) for w in whales)
        alias_count = sum(1 for w in whales if w.get("alias_of"))
        alias_info = f" (含 {alias_count} 个马甲)" if alias_count else ""
        print(f"[Whale] ✅ 加载 {len(whales)} 个鲸鱼 / {total_addrs} 个地址{alias_info} (from {found_path})")
        return whales
    except Exception as e:
        print(f"[Whale] ❌ 加载 whale_list 失败: {e}")
        return _whale_list_cache or []


# 🆕 v27.3: 马甲合并 — 支持 whale_list.json 里的 "alias_of" 字段
def _whale_canonical_id(whale):
    """返回 whale 的 canonical id. 有 alias_of 就用主鲸 id, 否则用自己 id"""
    wid = whale.get("id") or whale.get("name", "unknown")
    return whale.get("alias_of") or wid


def _whale_find_by_id(wid, whales=None):
    """按 id 在 whale list 里查找, 找不到返回 None"""
    if whales is None:
        whales = load_whale_list()
    for w in whales:
        if (w.get("id") or w.get("name", "")) == wid:
            return w
    return None


def _whale_family_suffix(whale):
    """
    如果 whale 是马甲 (有 alias_of), 返回 ' (属 主鲸名 家族)' 后缀, 否则返回 ''
    用于单条告警里显示关联关系, 不影响聚合计算
    """
    alias_of = whale.get("alias_of")
    if not alias_of:
        return ""
    primary = _whale_find_by_id(alias_of)
    if not primary:
        return ""
    primary_name = primary.get("name", alias_of)
    primary_emoji = primary.get("emoji", "")
    return f" (属 {primary_emoji} {primary_name} 家族)"


def _whale_event_image(whale, event_key):
    """
    🆕 v28.4: 查询 whale_list.json 里该鲸鱼某事件对应的图 URL
    event_key: 'liq_yellow' | 'liq_orange' | 'liq_red' | 'liquidation' | 'big_add'
    如果该鲸鱼是马甲, 自动使用主鲸的图 (家族共用形象)
    返回 URL 字符串或 None
    """
    # 马甲→主鲸
    alias_of = whale.get("alias_of")
    if alias_of:
        primary = _whale_find_by_id(alias_of)
        if primary:
            whale = primary
    images = whale.get("images") or {}
    if not isinstance(images, dict):
        return None
    url = images.get(event_key)
    if not url or not isinstance(url, str) or not url.startswith("http"):
        return None
    return url


def _send_whale_rich(image_url, caption, fallback_text):
    """
    🆕 v28.4: 富内容发送 helper.
    有 image_url 尝试发图, 失败或无图则降级到 fallback_text.
    caption 用作图片下方的说明文字 (TG 最长 1024 字符).
    """
    if image_url:
        ok = send_tg_photo_url(image_url, caption)
        if ok:
            return
        # 图发送失败, 降级纯文本
        print(f"[WhaleRich] 图片发送失败, 降级文字: {image_url[:80]}")
    send_tg(fallback_text)


def fetch_whale_state(address):
    """查询单个地址的 Hyperliquid 仓位 (clearinghouseState)"""
    try:
        r = requests.post(
            "https://api.hyperliquid.xyz/info",
            json={"type": "clearinghouseState", "user": address},
            timeout=10
        )
        if r.status_code != 200:
            return None
        return r.json()
    except Exception as e:
        print(f"[Whale] fetch {address[:10]} error: {e}")
        return None


# 🆕 v27.1-B 大额爆仓阈值
WHALE_LIQ_FILL_MIN_USD = 500_000  # 单笔成交 closedPnl <= -500K 或被清算才推
WHALE_LIQ_FILL_LOOKBACK_HOURS = 2  # 只看最近 2 小时的 fills (避免 bootstrap 翻历史)

def fetch_whale_fills(address, limit=50):
    """查询地址最近的成交记录 (userFills), 最新在前"""
    try:
        r = requests.post(
            "https://api.hyperliquid.xyz/info",
            json={"type": "userFills", "user": address},
            timeout=12
        )
        if r.status_code != 200:
            return []
        data = r.json() or []
        return data[:limit] if isinstance(data, list) else []
    except Exception as e:
        print(f"[WhaleFills] {address[:10]} error: {e}")
        return []


def _init_whale_db(conn):
    """初始化 whale 相关表"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS whale_positions (
            address TEXT, coin TEXT, side TEXT,
            size_coin REAL, size_usd REAL,
            entry_px REAL, liq_px REAL,
            unrealized_pnl REAL,
            leverage REAL,
            recorded_at TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_whale_pos_addr_coin ON whale_positions(address, coin, recorded_at)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS whale_alerts (
            whale_id TEXT, address TEXT, coin TEXT,
            event TEXT,
            alerted_at TEXT
        )
    """)
    # 🆕 v27.2: 账户净值历史 (用于计算 24h PnL 榜单)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS whale_account_values (
            address TEXT,
            account_value REAL,
            total_margin_used REAL,
            num_positions INTEGER,
            recorded_at TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_whale_acct_addr_time ON whale_account_values(address, recorded_at)
    """)
    # 🆕 v28.0: 鲸鱼事件历史 (用于共振分析, 独立于 whale_alerts 推送记录)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS whale_events (
            whale_id TEXT,
            canonical_id TEXT,
            address TEXT,
            coin TEXT,
            side TEXT,
            event TEXT,
            size_usd REAL,
            leverage REAL,
            recorded_at TEXT
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_whale_events_coin_side_time ON whale_events(coin, side, recorded_at)
    """)
    # 🆕 v28.2: 鲸鱼订阅 (私聊 push)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS whale_subscriptions (
            user_chat_id INTEGER,
            canonical_id TEXT,
            subscribed_at TEXT,
            PRIMARY KEY (user_chat_id, canonical_id)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_whale_subs_canonical ON whale_subscriptions(canonical_id)
    """)
    # 🆕 v29.0: 战绩追推队列 (告警发出后, 4h/24h 自动追推鲸鱼仓位盈亏)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS whale_alert_followup (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            whale_id TEXT,
            canonical_id TEXT,
            whale_name TEXT,
            address TEXT,
            coin TEXT,
            side TEXT,
            size_coin REAL,
            size_usd REAL,
            entry_px REAL,
            leverage REAL,
            event TEXT,
            alerted_at TEXT,
            followup_4h_done INTEGER DEFAULT 0,
            followup_24h_done INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_whale_followup_pending ON whale_alert_followup(alerted_at, followup_4h_done, followup_24h_done)
    """)
    # 🆕 v29.1: 信号战绩追推队列 (价格异动告警 4h/24h 后自动复盘信号准不准)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS price_alert_followup (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            direction TEXT,
            trigger_price REAL,
            trigger_text TEXT,
            change_from_low REAL DEFAULT 0,
            alerted_at TEXT,
            followup_4h_done INTEGER DEFAULT 0,
            followup_24h_done INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_price_followup_pending ON price_alert_followup(alerted_at, followup_4h_done, followup_24h_done)
    """)
    conn.commit()


def _parse_whale_account_value(state):
    """从 clearinghouseState 提取账户净值 + 持仓总市值 + 元数据 (v27.2, v28.0.1 扩展)"""
    if not state or not isinstance(state, dict):
        return None
    try:
        # accountValue = 可提取余额 (已扣除占用保证金 + 浮亏)
        # 对麻吉大哥这种多次清算后的鲸鱼, accountValue 可能很低甚至 0
        # total_position_value = 所有仓位市值之和 (更直观反映"这鲸鱼有多少钱在博弈")
        summary = state.get("marginSummary") or state.get("crossMarginSummary") or {}
        account_value = float(summary.get("accountValue", 0) or 0)
        total_margin = float(summary.get("totalMarginUsed", 0) or 0)
        total_ntl_pos = float(summary.get("totalNtlPos", 0) or 0)  # v28.0.1: 所有仓位 notional 总和

        asset_pos = state.get("assetPositions") or []
        num_positions = 0
        total_position_value = 0.0
        for ap in asset_pos:
            if not isinstance(ap, dict):
                continue
            pos = ap.get("position") or {}
            szi = float(pos.get("szi", 0) or 0)
            if szi == 0:
                continue
            num_positions += 1
            # 优先 positionValue (含未实现盈亏的当前市值)
            pv = float(pos.get("positionValue", 0) or 0)
            if pv <= 0:
                entry = float(pos.get("entryPx", 0) or 0)
                pv = abs(szi * entry)
            total_position_value += pv

        # fallback: 如果 positionValue 都没有, 用 totalNtlPos
        if total_position_value <= 0 and total_ntl_pos > 0:
            total_position_value = total_ntl_pos

        return {
            "account_value": account_value,
            "total_margin_used": total_margin,
            "num_positions": num_positions,
            "total_position_value": total_position_value,  # 🆕 v28.0.1
        }
    except Exception:
        return None


def _parse_whale_positions(state):
    """把 Hyperliquid clearinghouseState 解析为 list of position dicts"""
    positions = []
    if not state or not isinstance(state, dict):
        return positions
    asset_pos = state.get("assetPositions") or []
    for ap in asset_pos:
        pos = ap.get("position") if isinstance(ap, dict) else None
        if not pos:
            continue
        try:
            szi = float(pos.get("szi", 0))
            if szi == 0:
                continue
            coin = pos.get("coin", "")
            entry_px = float(pos.get("entryPx", 0) or 0)
            unrealized = float(pos.get("unrealizedPnl", 0) or 0)
            liq_px = float((pos.get("liquidationPx") or 0) or 0)
            leverage_obj = pos.get("leverage") or {}
            lev_val = float(leverage_obj.get("value", 0) or 0) if isinstance(leverage_obj, dict) else 0
            side = "long" if szi > 0 else "short"
            # v27: 优先用 API 直接给的 positionValue (准确市值, 用当前价计算)
            position_value = float(pos.get("positionValue", 0) or 0)
            size_usd = position_value if position_value > 0 else abs(szi * entry_px)
            positions.append({
                "coin": coin,
                "side": side,
                "size_coin": abs(szi),
                "size_usd": size_usd,
                "entry_px": entry_px,
                "liq_px": liq_px,
                "unrealized_pnl": unrealized,
                "leverage": lev_val,
            })
        except Exception:
            continue
    return positions


def _whale_can_alert(conn, whale_id, coin, event, cooldown_min=WHALE_COOLDOWN_MIN):
    """冷却检测: 同鲸鱼+币+事件在 30 分钟内不重复推"""
    row = conn.execute(
        "SELECT alerted_at FROM whale_alerts "
        "WHERE whale_id=? AND coin=? AND event=? "
        "ORDER BY alerted_at DESC LIMIT 1",
        (whale_id, coin, event)
    ).fetchone()
    if not row:
        return True
    try:
        last = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
        if (_utcnow() - last).total_seconds() < cooldown_min * 60:
            return False
    except Exception:
        pass
    return True


def _whale_mark_alert(conn, whale_id, address, coin, event):
    conn.execute(
        "INSERT INTO whale_alerts (whale_id, address, coin, event, alerted_at) VALUES (?,?,?,?,?)",
        (whale_id, address, coin, event, _utcnow().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()


def check_whale_positions(conn):
    """
    主函数: 扫描所有鲸鱼地址, 对比上次快照, 检测变化并推送
    返回: 推送的 alert 数量
    """
    whales = load_whale_list()
    if not whales:
        return 0

    _init_whale_db(conn)

    now_str = _utcnow().strftime("%Y-%m-%d %H:%M:%S")
    pushed = 0

    for whale in whales:
        whale_id = whale.get("id") or whale.get("name", "unknown")
        whale_name = whale.get("name", whale_id)
        whale_emoji = whale.get("emoji", "🐋")
        tags = whale.get("tags", [])
        story = whale.get("story", "")
        addresses = whale.get("addresses", [])

        for addr in addresses:
            addr = addr.lower()
            if not addr.startswith("0x") or len(addr) != 42:
                continue  # 跳过占位/不完整地址

            # 1. 拉当前仓位
            state = fetch_whale_state(addr)
            if state is None:
                continue
            current_positions = _parse_whale_positions(state)

            # 2. 拉上次快照 (所有币最近一次)
            prev_rows = conn.execute(
                "SELECT coin, side, size_coin, entry_px, liq_px, unrealized_pnl, leverage, recorded_at "
                "FROM whale_positions WHERE address=? "
                "AND recorded_at = (SELECT MAX(recorded_at) FROM whale_positions WHERE address=?)",
                (addr, addr)
            ).fetchall()
            prev_map = {r[0]: {
                "side": r[1], "size_coin": r[2], "entry_px": r[3],
                "liq_px": r[4], "unrealized_pnl": r[5], "leverage": r[6],
                "recorded_at": r[7]
            } for r in prev_rows}

            # 🆕 v27.1 Bug Fix: 防冷启动刷屏 — 首次见到该地址时只存快照不推送
            # 🔧 v27.3.1 Fix: bootstrap 判定改用 whale_account_values (每次扫描都插, 空仓也记录),
            # 否则空仓地址永远被误判为 bootstrap, 白鲸等会反复刷日志 + 漏首次开仓推送
            is_bootstrap = conn.execute(
                "SELECT 1 FROM whale_account_values WHERE address=? LIMIT 1",
                (addr,)
            ).fetchone() is None
            if is_bootstrap:
                print(f"[Whale] 🆕 首次扫描 {whale_name} ({addr[:10]}...), 静默记录 {len(current_positions)} 个仓位, 下次扫描起才推送")

            # 🆕 v27.1-A 清算倒计时检查 (即使 bootstrap 也跑, 避免漏掉已处于高危的仓位)
            for cp in current_positions:
                if _check_whale_liq_risk(conn, whale, addr, cp, now_str):
                    pushed += 1

            # 🆕 v27.1-B 大额爆仓 / 大亏平仓检查 (2h 回看窗口 + fill hash 去重, bootstrap 也跑)
            try:
                pushed += _check_whale_liquidation_fills(conn, whale, addr, now_str)
            except Exception as e:
                print(f"[LiqFill] check 错误 {whale_id} {addr[:10]}: {e}")

            # 3. 对比变化 (bootstrap 跳过推送, 仅存快照)
            if not is_bootstrap:
                for cp in current_positions:
                    coin = cp["coin"]
                    prev = prev_map.get(coin)

                    if prev is None:
                        # 新开仓
                        event = "open"
                        if cp["size_usd"] >= WHALE_CHANGE_MIN_USD:
                            if _whale_can_alert(conn, whale_id, coin, event):
                                _send_whale_alert(whale, addr, cp, None, "open")
                                _whale_mark_alert(conn, whale_id, addr, coin, event)
                                _log_whale_event(conn, whale, addr, cp, "open", now_str)  # v28: 共振分析
                                pushed += 1
                        continue

                    # 已有仓位: 检测变化
                    # 🆕 v27.1 Bug Fix: 用当前市价 (positionValue/size_coin) 而不是加仓后均价算 delta USD
                    market_px = (cp["size_usd"] / cp["size_coin"]) if cp["size_coin"] > 0 else cp["entry_px"]
                    size_diff_coin = cp["size_coin"] - prev["size_coin"]
                    size_diff_usd = abs(size_diff_coin) * market_px

                    prev_size_usd = prev["size_coin"] * (prev["entry_px"] or cp["entry_px"])
                    pct = (abs(size_diff_coin) / prev["size_coin"] * 100) if prev["size_coin"] > 0 else 0

                    # 侧翻 (多翻空 / 空翻多)
                    if cp["side"] != prev["side"]:
                        event = "flip"
                        if _whale_can_alert(conn, whale_id, coin, event):
                            _send_whale_alert(whale, addr, cp, prev, "flip")
                            _whale_mark_alert(conn, whale_id, addr, coin, event)
                            _log_whale_event(conn, whale, addr, cp, "flip", now_str)  # v28
                            pushed += 1
                        continue

                    # 加仓 / 减仓 (变化 >$500K 或 >10%)
                    if size_diff_usd >= WHALE_CHANGE_MIN_USD or pct >= WHALE_CHANGE_MIN_PCT:
                        if size_diff_coin > 0:
                            event = "add"
                        else:
                            event = "reduce"
                        if _whale_can_alert(conn, whale_id, coin, event):
                            _send_whale_alert(whale, addr, cp, prev, event)
                            _whale_mark_alert(conn, whale_id, addr, coin, event)
                            # v28: 只记 add/flip (不记 reduce/close, 对共振无意义)
                            if event == "add":
                                _log_whale_event(conn, whale, addr, cp, "add", now_str)
                            pushed += 1

                # 4. 检测平仓 (上次有, 本次无)
                current_coins = {cp["coin"] for cp in current_positions}
                for coin, prev in prev_map.items():
                    if coin not in current_coins and prev["size_coin"] > 0:
                        # 平仓
                        event = "close"
                        # 构造一个 pseudo-current
                        pseudo_cp = {
                            "coin": coin, "side": prev["side"],
                            "size_coin": 0, "size_usd": 0,
                            "entry_px": prev["entry_px"],
                            "liq_px": 0, "unrealized_pnl": 0,
                            "leverage": prev["leverage"],
                        }
                        if _whale_can_alert(conn, whale_id, coin, event):
                            _send_whale_alert(whale, addr, pseudo_cp, prev, "close")
                            _whale_mark_alert(conn, whale_id, addr, coin, event)
                            pushed += 1

            # 5. 存快照 (每次扫描都存, 供下次对比)
            for cp in current_positions:
                conn.execute(
                    "INSERT INTO whale_positions (address, coin, side, size_coin, size_usd, "
                    "entry_px, liq_px, unrealized_pnl, leverage, recorded_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (addr, cp["coin"], cp["side"], cp["size_coin"], cp["size_usd"],
                     cp["entry_px"], cp["liq_px"], cp["unrealized_pnl"], cp["leverage"], now_str)
                )

            # 🆕 v27.2: 存账户净值快照 (用于 24h PnL 榜)
            # 🔧 v27.3.1: 去掉 account_value > 0 限制 — 空钱包也插入 (account_value=0)
            # 这样 bootstrap 判定能正确识别"已扫过但空仓"的地址, 避免反复误报
            acct = _parse_whale_account_value(state)
            if acct:
                conn.execute(
                    "INSERT INTO whale_account_values "
                    "(address, account_value, total_margin_used, num_positions, recorded_at) "
                    "VALUES (?,?,?,?,?)",
                    (addr, acct["account_value"], acct["total_margin_used"],
                     acct["num_positions"], now_str)
                )

            conn.commit()

            time.sleep(0.2)  # 温柔一点, 别把 Hyperliquid API 搞炸

    return pushed


def _fmt_whale_price(px):
    """智能格式化价格 (大数字 K/M, 小数字保留小数)"""
    if px >= 1000:
        return f"${px:,.0f}"
    elif px >= 1:
        return f"${px:.2f}"
    else:
        return f"${px:.4f}"


def _fmt_whale_size_usd(usd):
    if usd >= 1e9:
        return f"${usd/1e9:.2f}B"
    elif usd >= 1e6:
        return f"${usd/1e6:.2f}M"
    elif usd >= 1e3:
        return f"${usd/1e3:.1f}K"
    else:
        return f"${usd:,.0f}"


def _send_whale_alert(whale, addr, current, prev, event):
    """
    推送鲸鱼 alert (HTML 格式, 加粗, 尾行标签)
    event: open / add / reduce / flip / close
    """
    whale_id = whale.get("id", "unknown")
    whale_name = whale.get("name", whale_id)
    whale_emoji = whale.get("emoji", "🐋")
    tags = whale.get("tags", [])
    twitter = whale.get("twitter", "")

    coin = current["coin"]
    side = current["side"]
    side_cn = "多单" if side == "long" else "空单"
    side_emoji = "🟢" if side == "long" else "🔴"

    # 事件标题
    if event == "open":
        title = f"{whale_emoji} 【{whale_name}】开仓 {coin} {side_cn}"
        banner = f"📈 新开仓 · NEW POSITION"
    elif event == "add":
        title = f"{whale_emoji} 【{whale_name}】加仓 {coin} {side_cn}"
        banner = f"➕ 加仓 · POSITION UP"
    elif event == "reduce":
        title = f"{whale_emoji} 【{whale_name}】减仓 {coin} {side_cn}"
        banner = f"➖ 减仓 · POSITION DOWN"
    elif event == "flip":
        title = f"{whale_emoji} 【{whale_name}】{coin} 反手!"
        banner = f"🔄 多空反手 · DIRECTION FLIP"
    elif event == "close":
        title = f"{whale_emoji} 【{whale_name}】平仓 {coin} {side_cn}"
        banner = f"❌ 平仓 · POSITION CLOSED"
    else:
        title = f"{whale_emoji} 【{whale_name}】{coin} 仓位变化"
        banner = "📊 仓位变化"

    # 消息主体
    msg = f"{banner}\n\n"
    msg += f"{title}{_whale_family_suffix(whale)}\n"
    if tags:
        msg += f"🏷️ {' · '.join(_esc(t) for t in tags[:3])}\n"
    if twitter:
        msg += f"🐦 {_esc(twitter)}\n"

    msg += "\n📊 仓位详情\n"
    if event == "close" and prev:
        # v27: 平仓时显示原仓位信息
        prev_side_cn = "多单" if prev.get("side") == "long" else "空单"
        prev_side_emoji = "🟢" if prev.get("side") == "long" else "🔴"
        prev_size = prev.get("size_coin", 0)
        prev_entry = prev.get("entry_px", 0)
        prev_entry_str = _fmt_whale_price(prev_entry) if prev_entry > 0 else "?"
        msg += f"  • 原仓位: {prev_side_emoji} {_b(prev_side_cn)} {_esc(coin)} {prev_size:,.2f} 枚\n"
        msg += f"  • 原均价: {prev_entry_str}\n"
        if prev.get("leverage", 0) > 0:
            msg += f"  • 原杠杆: {prev['leverage']:.0f}x\n"
    elif event != "close":
        size_usd_str = _fmt_whale_size_usd(current["size_usd"])
        entry_str = _fmt_whale_price(current["entry_px"])
        msg += f"  • 当前: {side_emoji} {_b(side_cn)} {_esc(coin)} {current['size_coin']:,.2f} 枚\n"
        msg += f"  • 市值: {_b(size_usd_str)}\n"
        msg += f"  • 均价: {_b(entry_str)}\n"
        if current["leverage"] > 0:
            lev_str = f"{current['leverage']:.0f}x"
            msg += f"  • 杠杆: {_b(lev_str)}\n"

        if current["liq_px"] > 0 and current["entry_px"] > 0:
            # 距离清算百分比
            liq_px = current["liq_px"]
            entry = current["entry_px"]
            liq_distance_pct = abs((liq_px - entry) / entry) * 100
            liq_str = _fmt_whale_price(liq_px)
            if liq_distance_pct < 5:
                msg += f"  • 清算: 🚨 {_b(liq_str)} (距均价仅 {liq_distance_pct:.1f}%!)\n"
            else:
                msg += f"  • 清算: {liq_str} (距均价 {liq_distance_pct:.1f}%)\n"

        if current["unrealized_pnl"] != 0:
            pnl_str = _fmt_whale_size_usd(abs(current["unrealized_pnl"]))
            pnl_sign = "+" if current["unrealized_pnl"] > 0 else "-"
            pnl_color = "🟢" if current["unrealized_pnl"] > 0 else "🔴"
            msg += f"  • 浮盈亏: {pnl_color} {_b(pnl_sign + pnl_str)}\n"

    # 对比 (如果是加/减/反手)
    if prev and event in ("add", "reduce", "flip"):
        msg += "\n🔀 变化\n"
        prev_size = prev.get("size_coin", 0)
        curr_size = current["size_coin"]
        if event == "flip":
            prev_side_cn = "多" if prev.get("side") == "long" else "空"
            curr_side_cn = "多" if current["side"] == "long" else "空"
            msg += f"  • 方向: {prev_side_cn} → {curr_side_cn}\n"
        else:
            diff_coin = curr_size - prev_size
            sign = "+" if diff_coin > 0 else ""
            msg += f"  • 仓位: {prev_size:,.0f} → {curr_size:,.0f} ({sign}{diff_coin:,.0f})\n"

    # 链接 (v27.0.1: 去掉失效的 hyperdash, 跟单改开户)
    msg += f"\n🔗 https://hypurrscan.io/address/{addr}"
    msg += f"\n📲 开户: {HL_REFERRAL}"

    # 尾行标签
    try:
        v = int(current["size_usd"] / 1000) if current["size_usd"] else 0  # k-usd
        r = min(10, int(current["leverage"] / 2)) if current["leverage"] > 0 else 3
        tail = tail_for_alert(
            "whale", whale_id,
            v=v, r=r, src="hyperliquid",
            extra={"event": event, "coin": coin, "side": side,
                   "addr": addr, "whale_name": whale_name}
        )
        msg += f"\n{tail}"
    except Exception as e:
        print(f"[Tail] whale error: {e}")

    # 🆕 v28.4: 大事件 (大加仓 ≥$5M) 用漫画图, 其他保持纯文字
    image_url = None
    if event == "add" and current.get("size_usd", 0) >= WHALE_IMAGE_BIG_ADD_USD:
        image_url = _whale_event_image(whale, "big_add")

    _send_whale_rich(image_url, msg, msg)
    time.sleep(1)

    # 🆕 v28.8: 大加仓 ≥$5M 自动发 FOMO 海报 (额外消息, 仅主鲸)
    try:
        if event == "add" and not whale.get("alias_of"):
            # 重算 size_diff_usd (current 和 prev 都有 size_coin)
            if prev and current.get("size_coin", 0) > prev.get("size_coin", 0):
                size_diff_coin = current["size_coin"] - prev["size_coin"]
                # 用 current 市价估算 (size_usd / size_coin)
                if current.get("size_coin", 0) > 0:
                    market_px_est = current.get("size_usd", 0) / current["size_coin"]
                    size_diff_usd = abs(size_diff_coin) * market_px_est
                    if size_diff_usd >= 5_000_000:
                        poster = _fomo_poster_big_add(whale, current, size_diff_usd)
                        if poster:
                            _fomo_send_async(poster, "")
                            print(f"[FOMO] ✅ 大加仓海报已发: {whale.get('name')} +${size_diff_usd/1e6:.2f}M")
    except Exception as e:
        print(f"[FOMO BigAdd 挂钩] 错误: {e}")

    # 🆕 v28.2: 给订阅者私推 (订阅者也应该收到图, 但文字 fallback 也没关系)
    try:
        canonical = _whale_canonical_id(whale)
        _sub_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        notify_whale_subscribers(_sub_conn, canonical, msg)
        _sub_conn.close()
    except Exception as e:
        print(f"[Notify whale_alert] 错误: {e}")

    # 🆕 v29.0: 入队战绩追推 (4h/24h 后自动复盘)
    # 仅 open / add / flip 入队 (有方向有入场价才能算盈亏)
    try:
        if event in ("open", "add", "flip") and not whale.get("alias_of"):
            _fu_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            now_str = _utcnow().strftime("%Y-%m-%d %H:%M:%S")
            _enqueue_whale_followup(_fu_conn, whale, addr, current, event, now_str)
            _fu_conn.close()
    except Exception as e:
        print(f"[Followup enqueue whale_alert] 错误: {e}")


# ============================================================
# 🆕 v27.1-A 清算倒计时预警
# ============================================================
def _liq_tier(dist_pct):
    """根据距清算 % 返回档位 (0=安全, 1=黄, 2=橙, 3=红)"""
    if dist_pct < WHALE_LIQ_TIER_RED:
        return 3, "liq_red", "🔴", "红色爆仓临近 RED"
    if dist_pct < WHALE_LIQ_TIER_ORANGE:
        return 2, "liq_orange", "🟠", "橙色警告 ORANGE"
    if dist_pct < WHALE_LIQ_TIER_YELLOW:
        return 1, "liq_yellow", "🟡", "黄色预警 YELLOW"
    return 0, None, None, None


def _liq_progress_bar(dist_pct, max_pct=WHALE_LIQ_TIER_YELLOW, width=10):
    """Unicode 进度条: 距清算越近, 填充越多 (最满 = 已爆)"""
    if dist_pct >= max_pct:
        filled = 0
    elif dist_pct <= 0:
        filled = width
    else:
        filled = round((max_pct - dist_pct) / max_pct * width)
    filled = max(0, min(width, filled))
    return "▓" * filled + "░" * (width - filled)


def _whale_last_liq_tier(conn, whale_id, coin, hours=WHALE_LIQ_RESET_HOURS):
    """查询最近 N 小时内该鲸鱼+币种的最高 liq 告警档 (超过窗口视为重置)"""
    cutoff = (_utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    row = conn.execute(
        "SELECT event FROM whale_alerts "
        "WHERE whale_id=? AND coin=? AND event LIKE 'liq_%' "
        "AND alerted_at >= ? "
        "ORDER BY alerted_at DESC LIMIT 1",
        (whale_id, coin, cutoff)
    ).fetchone()
    if not row:
        return 0
    return {"liq_yellow": 1, "liq_orange": 2, "liq_red": 3}.get(row[0], 0)


def _check_whale_liq_risk(conn, whale, addr, cp, now_str):
    """
    检查单个仓位的清算风险. 规则:
      • 仅当新档位高于最近 6h 内最高档位才推 (避免震荡刷屏)
      • 仓位 <$100K 不推, liq_px=0 不推
      • 返回 True 表示推送了, False 表示跳过
    """
    try:
        liq_px = float(cp.get("liq_px", 0) or 0)
        size_coin = float(cp.get("size_coin", 0) or 0)
        size_usd = float(cp.get("size_usd", 0) or 0)
        side = cp.get("side", "")
        coin = cp.get("coin", "")

        # 过滤: 无清算价 / 仓位太小
        if liq_px <= 0 or size_coin <= 0 or size_usd < WHALE_LIQ_MIN_USD:
            return False

        # 当前市价 (用 positionValue / size_coin, 比 entry_px 更准)
        market_px = size_usd / size_coin
        if market_px <= 0:
            return False

        # 距离清算百分比
        if side == "long":
            dist_pct = (market_px - liq_px) / market_px * 100
        else:  # short
            dist_pct = (liq_px - market_px) / market_px * 100

        # 防御: 万一数据异常 (已爆但还在名单里)
        if dist_pct <= 0:
            dist_pct = 0.1

        # 确定档位
        new_tier, event, emoji, tier_name = _liq_tier(dist_pct)
        if new_tier == 0:
            return False  # 距离还安全, 不推

        # 只有升档才推 (避免 🟡 → 🟠 → 🟡 → 🟠 反复刷屏)
        whale_id = whale.get("id", "unknown")

        # 🆕 v30.12: 单鲸鱼全局冷却 — 跨币种, 同一鲸鱼 4h 内最多推 1 条 liq alert
        # (修复 v30.11 麻吉大哥 6 次/17h 单人刷屏问题)
        global_cutoff = (_utcnow() - timedelta(hours=WHALE_LIQ_GLOBAL_COOLDOWN_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
        recent_global = conn.execute(
            "SELECT 1 FROM whale_alerts "
            "WHERE whale_id=? AND event LIKE 'liq_%' AND alerted_at >= ? LIMIT 1",
            (whale_id, global_cutoff)
        ).fetchone()
        if recent_global:
            return False  # 该鲸鱼最近 4h 已推过 liq alert, 跳过

        last_tier = _whale_last_liq_tier(conn, whale_id, coin)
        if new_tier <= last_tier:
            return False

        # 推送 + 记录
        _send_whale_liq_alert(whale, addr, cp, new_tier, dist_pct, market_px, emoji, tier_name)
        conn.execute(
            "INSERT INTO whale_alerts (whale_id, address, coin, event, alerted_at) VALUES (?,?,?,?,?)",
            (whale_id, addr, coin, event, now_str)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"[WhaleLiq] {whale.get('id', '?')} {cp.get('coin', '?')} 错误: {e}")
        return False


def _send_whale_liq_alert(whale, addr, cp, tier, dist_pct, market_px, emoji, tier_name):
    """推送清算预警 (Unicode 进度条 + 档位分级)"""
    whale_id = whale.get("id", "unknown")
    whale_name = whale.get("name", whale_id)
    whale_emoji = whale.get("emoji", "🐋")
    tags = whale.get("tags", [])
    twitter = whale.get("twitter", "")

    coin = cp["coin"]
    side = cp["side"]
    side_cn = "多单" if side == "long" else "空单"
    side_emoji = "🟢" if side == "long" else "🔴"

    # 标题
    msg = f"{emoji} 清算预警 · {tier_name}\n\n"
    msg += f"{whale_emoji} 【{_esc(whale_name)}】{_esc(coin)} {side_cn}{_whale_family_suffix(whale)}\n"
    if tags:
        msg += f"🏷️ {' · '.join(_esc(t) for t in tags[:3])}\n"
    if twitter:
        msg += f"🐦 {_esc(twitter)}\n"

    # 核心可视化: 进度条
    bar = _liq_progress_bar(dist_pct, max_pct=WHALE_LIQ_TIER_YELLOW, width=10)
    msg += f"\n⚠️ 距离清算: {bar} {_b(f'{dist_pct:.2f}%')}\n"

    # 价格对比
    market_str = _fmt_whale_price(market_px)
    liq_str = _fmt_whale_price(cp["liq_px"])
    direction_cn = "跌到" if side == "long" else "涨到"
    msg += f"💀 当前 {_b(market_str)} → 清算 {_b(liq_str)} ({direction_cn}就爆)\n"

    # 仓位
    size_usd_str = _fmt_whale_size_usd(cp["size_usd"])
    msg += f"📊 仓位: {side_emoji} {cp['size_coin']:,.2f} {_esc(coin)} ({_b(size_usd_str)})\n"
    if cp.get("leverage", 0) > 0:
        lev_str = f"{cp['leverage']:.0f}x"
        msg += f"    杠杆: {_b(lev_str)}\n"

    # 浮盈亏
    pnl = cp.get("unrealized_pnl", 0) or 0
    if pnl != 0:
        pnl_str = _fmt_whale_size_usd(abs(pnl))
        pnl_sign = "+" if pnl > 0 else "-"
        pnl_color = "🟢" if pnl > 0 else "🔴"
        msg += f"📉 浮盈亏: {pnl_color} {_b(pnl_sign + pnl_str)}\n"

    # 档位风险提示
    if tier == 3:
        msg += f"\n🚨 随时可能爆仓, 可能是抄底信号 (也可能是陷阱)\n"
    elif tier == 2:
        msg += f"\n⚠️ 接近清算, 关注是否补仓或平仓\n"

    # 链接
    msg += f"\n🔗 https://hypurrscan.io/address/{addr}"
    msg += f"\n📲 开户: {HL_REFERRAL}"

    # 尾行标签
    try:
        tail = tail_for_alert(
            "whale_liq", whale_id,
            v=int(dist_pct * 100),  # bp
            r=tier,
            src="hyperliquid",
            extra={"tier": tier, "coin": coin, "side": side, "addr": addr,
                   "whale_name": whale_name, "dist_pct": f"{dist_pct:.2f}"}
        )
        msg += f"\n{tail}"
    except Exception as e:
        print(f"[Tail] whale_liq error: {e}")

    # 🆕 v28.4: 根据档位选图 (红/橙/黄 — 图可相同, 由 JSON 配置决定)
    tier_to_key = {1: "liq_yellow", 2: "liq_orange", 3: "liq_red"}
    image_url = _whale_event_image(whale, tier_to_key.get(tier, ""))

    _send_whale_rich(image_url, msg, msg)
    time.sleep(1)

    # 🆕 v28.9: 黄/橙/红 三档都发 FOMO 海报 (每档配色不同, 培养追踪习惯)
    # 冷却由 _whale_can_alert 在调用方控制 (6 小时内同一鲸鱼+coin不重复触发)
    try:
        if tier in (1, 2, 3) and not whale.get("alias_of"):
            poster = _fomo_poster_liq_red(whale, dist_pct, cp, market_px, tier=tier)
            if poster:
                _fomo_send_async(poster, "")
                tier_name_short = {1: '黄', 2: '橙', 3: '红'}.get(tier, '?')
                print(f"[FOMO] ✅ {tier_name_short}警海报已发: {whale.get('name')} {dist_pct:.2f}%")
    except Exception as e:
        print(f"[FOMO LiqRed 挂钩] 错误: {e}")

    # 🆕 v28.2: 给订阅者私推
    try:
        canonical = _whale_canonical_id(whale)
        _sub_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        notify_whale_subscribers(_sub_conn, canonical, msg)
        _sub_conn.close()
    except Exception as e:
        print(f"[Notify whale_liq] 错误: {e}")

    # 🆕 v29.0: 入队战绩追推 (清算预警值得追踪 — 用户最关心鲸鱼有没有翻身)
    try:
        if not whale.get("alias_of"):
            _fu_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            now_str = _utcnow().strftime("%Y-%m-%d %H:%M:%S")
            event_key = {1: "liq_yellow", 2: "liq_orange", 3: "liq_red"}.get(tier, "liq")
            _enqueue_whale_followup(_fu_conn, whale, addr, cp, event_key, now_str)
            _fu_conn.close()
    except Exception as e:
        print(f"[Followup enqueue whale_liq] 错误: {e}")


# ============================================================
# 🆕 v27.1-B 大额爆仓 / 大亏平仓检测 (userFills API)
# ============================================================
def _check_whale_liquidation_fills(conn, whale, addr, now_str):
    """
    拉取地址最近 fills, 检测:
      • 真实清算 (fill 带 liquidation 字段)
      • 大额亏损平仓 (closedPnl <= -$500K)
    去重: 基于 fill hash / time+coin 组合, 存 whale_alerts
    """
    pushed = 0
    fills = fetch_whale_fills(addr, limit=50)
    if not fills:
        return 0

    whale_id = whale.get("id", "unknown")
    cutoff_ms = int((_utcnow() - timedelta(hours=WHALE_LIQ_FILL_LOOKBACK_HOURS)).timestamp() * 1000)

    for fill in fills:
        try:
            fill_time_ms = int(fill.get("time", 0) or 0)
            if fill_time_ms < cutoff_ms:
                # fills 是时间降序, 遇到过期就 break
                break

            closed_pnl = float(fill.get("closedPnl", 0) or 0)
            liquidation = fill.get("liquidation")
            # 🆕 v30.14.13: 修复误推爆仓警报
            # 旧逻辑 is_liq = (liquidation is not None) — 错!
            # 真相: HL fills 里 'liquidation' 字段会出现在每一笔"清算交易"的 maker+taker 双方,
            #       liquidatedUser 才是真正被清算者. 鲸鱼只是接盘侠 (吃流动性) 时也会收到这个字段.
            # 新逻辑: 必须 liquidatedUser == 本鲸鱼地址 才是真爆仓
            is_liq = False
            if isinstance(liquidation, dict):
                liq_user = (liquidation.get("liquidatedUser") or "").lower()
                if liq_user and liq_user == addr.lower():
                    is_liq = True
            is_big_loss = closed_pnl <= -WHALE_LIQ_FILL_MIN_USD

            # 🆕 v30.14.13: 即使是真清算, 亏损 < $1K 不推 (太离谱, 像麻吉那种 $91 是接盘侠 fill 误判)
            if is_liq and abs(closed_pnl) < 1000:
                print(f"[LiqFill] ⏭️ 跳过疑似误判: {whale_id} {fill.get('coin')} 标记 is_liq 但亏损仅 ${abs(closed_pnl):.0f}")
                is_liq = False

            if not (is_liq or is_big_loss):
                continue

            coin = fill.get("coin", "?")
            # 去重 key: 用 fill hash 或 (time + coin + px)
            fill_hash = fill.get("hash") or f"{fill_time_ms}-{coin}-{fill.get('px', '')}"
            event_key = f"liqfill_{fill_hash[:20]}"

            seen = conn.execute(
                "SELECT 1 FROM whale_alerts WHERE whale_id=? AND event=? LIMIT 1",
                (whale_id, event_key)
            ).fetchone()
            if seen:
                continue

            _send_whale_liq_fill_alert(whale, addr, fill, is_liq, closed_pnl)
            conn.execute(
                "INSERT INTO whale_alerts (whale_id, address, coin, event, alerted_at) VALUES (?,?,?,?,?)",
                (whale_id, addr, coin, event_key, now_str)
            )
            conn.commit()
            pushed += 1
        except Exception as e:
            print(f"[LiqFill] 处理错误 {whale_id}: {e}")
            continue

    return pushed


def _send_whale_liq_fill_alert(whale, addr, fill, is_liq, closed_pnl):
    """推送大额爆仓/大亏消息 (HTML 加粗, 尾行标签)"""
    whale_id = whale.get("id", "unknown")
    whale_name = whale.get("name", whale_id)
    whale_emoji = whale.get("emoji", "🐋")
    tags = whale.get("tags", [])
    twitter = whale.get("twitter", "")

    coin = fill.get("coin", "?")
    px = float(fill.get("px", 0) or 0)
    sz = float(fill.get("sz", 0) or 0)
    fill_time_ms = int(fill.get("time", 0) or 0)
    size_usd = px * sz

    if is_liq:
        banner = "💥 爆仓警报 · LIQUIDATION"
        title_verb = "被清算"
    else:
        banner = "💸 大亏平仓 · BIG LOSS CLOSE"
        title_verb = "大亏平仓"

    msg = f"{banner}\n\n"
    msg += f"{whale_emoji} 【{_esc(whale_name)}】{title_verb} {_esc(coin)}{_whale_family_suffix(whale)}\n"
    if tags:
        msg += f"🏷️ {' · '.join(_esc(t) for t in tags[:3])}\n"
    if twitter:
        msg += f"🐦 {_esc(twitter)}\n"

    loss_str = _fmt_whale_size_usd(abs(closed_pnl))
    msg += f"\n📊 成交详情\n"
    msg += f"  • 亏损: 🔴 {_b('-' + loss_str)}\n"
    msg += f"  • 数量: {sz:,.4f} {_esc(coin)}\n"
    msg += f"  • 成交价: {_b(_fmt_whale_price(px))}\n"
    msg += f"  • 成交额: {_b(_fmt_whale_size_usd(size_usd))}\n"

    if is_liq and isinstance(fill.get("liquidation"), dict):
        liq_info = fill["liquidation"]
        method = liq_info.get("method") or liq_info.get("liquidatedUser", "")
        if method:
            msg += f"  • 方式: {_esc(str(method)[:40])}\n"

    # 时间 (UTC + 北京)
    try:
        utc_dt = datetime.utcfromtimestamp(fill_time_ms / 1000)
        cn_dt = utc_dt + timedelta(hours=8)
        msg += f"  • 时间: {cn_dt.strftime('%m-%d %H:%M')} (北京)\n"
    except Exception:
        pass

    # 冷静提示
    if is_liq:
        msg += f"\n🚨 {_b('链上清算已发生')}, 可能是行情反转信号 (或陷阱)\n"

    msg += f"\n🔗 https://hypurrscan.io/address/{addr}"
    msg += f"\n📲 开户: {HL_REFERRAL}"

    try:
        tail = tail_for_alert(
            "whale_liq_fill", whale_id,
            v=int(abs(closed_pnl) / 1000),
            r=10 if is_liq else 5,
            src="hyperliquid",
            extra={"coin": coin, "is_liq": is_liq, "addr": addr,
                   "whale_name": whale_name, "size_usd": int(size_usd)}
        )
        msg += f"\n{tail}"
    except Exception as e:
        print(f"[Tail] whale_liq_fill error: {e}")

    # 🆕 v28.4: 真爆仓用 'liquidation' 图, 大亏平仓也用同一张 (都是悲剧时刻)
    image_url = _whale_event_image(whale, "liquidation")

    _send_whale_rich(image_url, msg, msg)
    time.sleep(1)

    # 🆕 v28.8: 真爆仓 / 大额亏损 自动发 FOMO 海报 (额外消息, 仅主鲸)
    try:
        if not whale.get("alias_of"):
            poster = _fomo_poster_liquidated(whale, fill, closed_pnl, is_liq)
            if poster:
                _fomo_send_async(poster, "")
                print(f"[FOMO] ✅ 爆仓海报已发: {whale.get('name')} ${closed_pnl/1e6:.2f}M")
    except Exception as e:
        print(f"[FOMO Liquidated 挂钩] 错误: {e}")

    # 🆕 v28.2: 给订阅者私推
    try:
        canonical = _whale_canonical_id(whale)
        _sub_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        notify_whale_subscribers(_sub_conn, canonical, msg)
        _sub_conn.close()
    except Exception as e:
        print(f"[Notify whale_liq_fill] 错误: {e}")


# ============================================================
# 🆕 v28.0 鲸鱼共振预警 (Resonance Alert)
# ============================================================
WHALE_RESONANCE_WINDOW_HOURS = 2     # 2h 窗口内多鲸鱼同向才算共振
WHALE_RESONANCE_MIN_WHALES = 2       # 至少 2 个不同家族
WHALE_RESONANCE_COOLDOWN_HOURS = 4   # 同 (coin, side) 4h 冷却
WHALE_RESONANCE_MIN_TOTAL_USD = 1_000_000  # 合计仓位至少 $1M 才推


def _log_whale_event(conn, whale, addr, cp, event, now_str):
    """记录鲸鱼事件到 whale_events 表 (用于后续共振分析)"""
    try:
        whale_id = whale.get("id", "unknown")
        canonical = _whale_canonical_id(whale)
        conn.execute(
            "INSERT INTO whale_events "
            "(whale_id, canonical_id, address, coin, side, event, size_usd, leverage, recorded_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (whale_id, canonical, addr, cp.get("coin", ""), cp.get("side", ""),
             event, float(cp.get("size_usd", 0) or 0), float(cp.get("leverage", 0) or 0),
             now_str)
        )
        conn.commit()
    except Exception as e:
        print(f"[WhaleEvent] log 错误: {e}")


def check_whale_resonance(conn):
    """
    检测共振: 2h 窗口内, ≥2 个不同家族在同 (coin, side) 开仓/加仓
    冷却: 同 (coin, side) 4h 只推一次
    返回推送的 alert 数量
    """
    pushed = 0
    try:
        _init_whale_db(conn)
        cutoff = (_utcnow() - timedelta(hours=WHALE_RESONANCE_WINDOW_HOURS)).strftime("%Y-%m-%d %H:%M:%S")

        # 拉取 2h 内的 open + add + flip 事件
        rows = conn.execute(
            "SELECT canonical_id, whale_id, address, coin, side, event, size_usd, leverage, recorded_at "
            "FROM whale_events "
            "WHERE recorded_at >= ? AND event IN ('open', 'add', 'flip')",
            (cutoff,)
        ).fetchall()

        if not rows:
            return 0

        # 按 (coin, side) 聚合
        groups = {}
        for r in rows:
            canonical, wid, addr, coin, side, event, size_usd, lev, ts = r
            if not coin or not side:
                continue
            key = (coin, side)
            groups.setdefault(key, []).append({
                "canonical_id": canonical, "whale_id": wid,
                "address": addr, "event": event,
                "size_usd": size_usd or 0, "leverage": lev or 0,
                "recorded_at": ts,
            })

        whales_all = load_whale_list()
        # whale lookup: canonical_id -> primary whale dict
        primary_lookup = {}
        for w in whales_all:
            canonical = _whale_canonical_id(w)
            wid = w.get("id") or w.get("name", "")
            if canonical == wid:
                primary_lookup[canonical] = w

        for (coin, side), events in groups.items():
            # 去重: 同 canonical_id 多次算一个 (保留最大 size)
            by_canonical = {}
            for e in events:
                c = e["canonical_id"]
                if c not in by_canonical or e["size_usd"] > by_canonical[c]["size_usd"]:
                    by_canonical[c] = e

            if len(by_canonical) < WHALE_RESONANCE_MIN_WHALES:
                continue

            total_usd = sum(e["size_usd"] for e in by_canonical.values())
            if total_usd < WHALE_RESONANCE_MIN_TOTAL_USD:
                continue

            # 冷却检测
            cooldown_cutoff = (_utcnow() - timedelta(hours=WHALE_RESONANCE_COOLDOWN_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
            event_key = f"resonance_{coin}_{side}"
            last = conn.execute(
                "SELECT 1 FROM whale_alerts WHERE whale_id='_resonance' AND coin=? AND event=? "
                "AND alerted_at >= ? LIMIT 1",
                (coin, event_key, cooldown_cutoff)
            ).fetchone()
            if last:
                continue

            # 推送
            _send_resonance_alert(coin, side, by_canonical, primary_lookup, total_usd)
            conn.execute(
                "INSERT INTO whale_alerts (whale_id, address, coin, event, alerted_at) VALUES (?,?,?,?,?)",
                ("_resonance", "", coin, event_key, _utcnow().strftime("%Y-%m-%d %H:%M:%S"))
            )
            conn.commit()
            pushed += 1

    except Exception as e:
        print(f"[Resonance] 错误: {e}")
        import traceback; traceback.print_exc()
    return pushed


def _send_resonance_alert(coin, side, by_canonical, primary_lookup, total_usd):
    """推送共振告警"""
    side_cn = "做多" if side == "long" else "做空"
    side_emoji = "🟢" if side == "long" else "🔴"
    side_verb = "看涨" if side == "long" else "看跌"

    n_whales = len(by_canonical)

    msg = f"🌊 鲸群共振 · RESONANCE\n\n"
    msg += f"{side_emoji} <b>{n_whales} 只鲸鱼同时{side_cn} {_esc(coin)}</b>\n"
    msg += f"💰 合计仓位: <b>{_fmt_whale_size_usd(total_usd)}</b>\n"
    msg += f"⏱️ 时间窗口: 最近 {WHALE_RESONANCE_WINDOW_HOURS} 小时\n\n"

    msg += f"📋 参与鲸鱼:\n"
    sorted_events = sorted(by_canonical.items(), key=lambda kv: kv[1]["size_usd"], reverse=True)
    for canonical, e in sorted_events:
        whale = primary_lookup.get(canonical)
        if not whale:
            continue
        name = whale.get("name", canonical)
        emoji = whale.get("emoji", "🐋")
        size_str = _fmt_whale_size_usd(e["size_usd"])
        lev_str = f" · {e['leverage']:.0f}x" if e["leverage"] > 0 else ""
        event_cn = {"open": "开仓", "add": "加仓", "flip": "反手"}.get(e["event"], e["event"])
        msg += f"  • {emoji} {_esc(name)} — {event_cn} <b>{size_str}</b>{lev_str}\n"

    msg += f"\n💡 多个大户同时行动, 通常意味着:\n"
    msg += f"  • {side_verb}一致性增强\n"
    msg += f"  • 但也可能是共同陷阱 (请独立判断)\n"

    msg += f"\n📲 开户: {HL_REFERRAL}"

    try:
        tail = tail_for_alert(
            "whale_resonance", f"{coin}_{side}",
            v=int(total_usd / 1000),
            r=n_whales,
            src="hyperliquid",
            extra={"coin": coin, "side": side, "n": n_whales, "total_usd": int(total_usd)}
        )
        msg += f"\n{tail}"
    except Exception:
        pass

    send_tg(msg)
    time.sleep(1)

    # 🆕 v28.8: 共振预警自动发 FOMO 海报 (额外消息)
    try:
        poster = _fomo_poster_resonance(coin, side, by_canonical, primary_lookup, total_usd)
        if poster:
            _fomo_send_async(poster, "")
            print(f"[FOMO] ✅ 共振海报已发: {coin} {side} {n_whales}鲸 ${total_usd/1e6:.1f}M")
    except Exception as e:
        print(f"[FOMO Resonance 挂钩] 错误: {e}")


# ============================================================
# ============================================================
# 🆕 v29.0 战绩追推 (鲸鱼告警 4h/24h 后自动回顾盈亏)
# ============================================================
def _enqueue_whale_followup(conn, whale, addr, cp, event, alerted_at_str):
    """
    告警发出后入队, 等 4h / 24h 后自动追推
    cp 是当时的仓位 (current position dict). 入场价 + 仓位锁定, 后续用现价对比.
    马甲不入队 (告警函数已经过滤过), 但加防御性 if.
    """
    try:
        if whale.get("alias_of"):
            return
        canonical = _whale_canonical_id(whale)
        whale_name = whale.get("name", canonical)
        whale_id = whale.get("id", canonical)
        coin = cp.get("coin", "")
        side = cp.get("side", "")
        size_coin = float(cp.get("size_coin", 0) or 0)
        size_usd = float(cp.get("size_usd", 0) or 0)
        entry_px = float(cp.get("entry_px", 0) or 0)
        leverage = float(cp.get("leverage", 0) or 0)
        if size_coin <= 0 or entry_px <= 0:
            return  # 没法算 PnL
        conn.execute("""
            INSERT INTO whale_alert_followup
            (whale_id, canonical_id, whale_name, address, coin, side,
             size_coin, size_usd, entry_px, leverage, event, alerted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (whale_id, canonical, whale_name, addr.lower(), coin, side,
              size_coin, size_usd, entry_px, leverage, event, alerted_at_str))
        conn.commit()
    except Exception as e:
        print(f"[Followup] enqueue 错误: {e}")


def _fetch_current_prices_hl():
    """一次拉所有币种现价 (从 Hyperliquid metaAndAssetCtxs)"""
    try:
        r = requests.post("https://api.hyperliquid.xyz/info",
                          json={"type": "metaAndAssetCtxs"}, timeout=10)
        if r.status_code != 200:
            return {}
        data = r.json()
        if not isinstance(data, list) or len(data) < 2:
            return {}
        universe = data[0].get("universe", [])
        ctxs = data[1]
        prices = {}
        for i, ctx in enumerate(ctxs):
            if i >= len(universe):
                break
            coin = universe[i].get("name", "")
            if coin:
                px = float(ctx.get("markPx", 0) or 0)
                if px > 0:
                    prices[coin] = px
        return prices
    except Exception as e:
        print(f"[Followup] 拉现价错误: {e}")
        return {}


def _calc_whale_pnl_now(row, current_px):
    """
    根据入场价 + 当前价计算这笔仓位现在的盈亏
    row 来自 whale_alert_followup 行
    返回 (pnl_usd, pnl_pct, leveraged_pnl_pct)
      pnl_usd: 仓位绝对盈亏 (with leverage)
      pnl_pct: 价格变化 % (无杠杆)
      leveraged_pnl_pct: 含杠杆的仓位 PnL %
    """
    entry = row['entry_px']
    size_coin = row['size_coin']
    side = row['side']
    leverage = row.get('leverage', 1) or 1
    if entry <= 0 or size_coin <= 0 or current_px <= 0:
        return 0, 0, 0
    if side == "long":
        pnl_usd = (current_px - entry) * size_coin
        pnl_pct = (current_px - entry) / entry * 100
    else:
        pnl_usd = (entry - current_px) * size_coin
        pnl_pct = (entry - current_px) / entry * 100
    leveraged_pnl_pct = pnl_pct * leverage
    return pnl_usd, pnl_pct, leveraged_pnl_pct


def check_whale_alert_followups(conn):
    """
    主循环每次扫描调用. 找到 4h+/24h+ 还没追推的告警, 计算盈亏并发送.
    返回推送条数.
    """
    pushed = 0
    try:
        now = _utcnow()
        cutoff_4h = (now - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")
        cutoff_24h = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        # 安全窗口 - 不追推超过 48h 的 (避免堆积)
        cutoff_floor = (now - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")

        # 🆕 v30.14.9: 移除 4h 复盘 (Kings 5/9 决策 — 4h 太短, 信号未走完, 容易给反向印象, 24h 已足够)
        # 老的 4h pending row 自然衰减 (48h cutoff_floor 后会被 24h 分支处理或过期)
        rows_4h = []

        # 找需要 24h 追推的 (alerted >= 24h ago, < 48h ago, 还没做 24h 追推)
        rows_24h = list(conn.execute("""
            SELECT id, whale_id, canonical_id, whale_name, address, coin, side,
                   size_coin, size_usd, entry_px, leverage, event, alerted_at
            FROM whale_alert_followup
            WHERE alerted_at <= ? AND alerted_at > ? AND followup_24h_done = 0
            ORDER BY alerted_at
            LIMIT 10
        """, (cutoff_24h, cutoff_floor)).fetchall())

        if not rows_4h and not rows_24h:
            return 0

        # 拉现价
        prices = _fetch_current_prices_hl()
        if not prices:
            return 0

        for kind, rows in [("4h", rows_4h), ("24h", rows_24h)]:
            for r in rows:
                row_dict = {
                    'id': r[0], 'whale_id': r[1], 'canonical_id': r[2],
                    'whale_name': r[3], 'address': r[4], 'coin': r[5], 'side': r[6],
                    'size_coin': r[7], 'size_usd': r[8], 'entry_px': r[9],
                    'leverage': r[10], 'event': r[11], 'alerted_at': r[12],
                }
                coin = row_dict['coin']
                if coin not in prices:
                    # 拉不到价 (币不在 hyperliquid 或下架). 标记完成不再重试.
                    col = "followup_4h_done" if kind == "4h" else "followup_24h_done"
                    conn.execute(f"UPDATE whale_alert_followup SET {col}=1 WHERE id=?", (row_dict['id'],))
                    conn.commit()
                    continue

                cur_px = prices[coin]
                pnl_usd, pnl_pct, lev_pnl_pct = _calc_whale_pnl_now(row_dict, cur_px)

                # 推送
                try:
                    _send_whale_followup(row_dict, kind, cur_px, pnl_usd, pnl_pct, lev_pnl_pct)
                    pushed += 1
                except Exception as e:
                    print(f"[Followup] 推送错误 id={row_dict['id']}: {e}")

                # 标记完成
                col = "followup_4h_done" if kind == "4h" else "followup_24h_done"
                conn.execute(f"UPDATE whale_alert_followup SET {col}=1 WHERE id=?", (row_dict['id'],))
                conn.commit()

        return pushed
    except Exception as e:
        print(f"[Followup] 主循环错误: {e}")
        import traceback; traceback.print_exc()
        return 0


def _send_whale_followup(row, kind, cur_px, pnl_usd, pnl_pct, lev_pnl_pct):
    """
    发送战绩追推消息.
    kind: "4h" 或 "24h"
    """
    name = row['whale_name']
    coin = row['coin']
    side = row['side']
    side_cn = "多" if side == "long" else "空"
    side_emoji = "🟢" if side == "long" else "🔴"
    entry = row['entry_px']
    size_usd = row['size_usd']
    leverage = row['leverage']
    event = row['event']

    # 事件中文
    event_cn = {
        "open": "开仓", "add": "加仓", "flip": "反手",
        "liq_yellow": "🟡黄警", "liq_orange": "🟠橙警", "liq_red": "🔴红警",
    }.get(event, event)

    is_gain = pnl_usd >= 0
    pnl_color = "🟢" if is_gain else "🔴"
    pnl_sign = "+" if is_gain else "-"
    pnl_abs = abs(pnl_usd)
    if pnl_abs >= 1e6:
        pnl_str = f"{pnl_sign}${pnl_abs/1e6:.2f}M"
    elif pnl_abs >= 1e3:
        pnl_str = f"{pnl_sign}${pnl_abs/1e3:.1f}K"
    else:
        pnl_str = f"{pnl_sign}${pnl_abs:.0f}"

    # 价格变化
    if side == "long":
        px_pct = (cur_px - entry) / entry * 100 if entry > 0 else 0
    else:
        px_pct = (entry - cur_px) / entry * 100 if entry > 0 else 0

    # 标题文案
    if kind == "4h":
        title = f"⏱️ 4 小时复盘 · {coin}"
        sub = f"4 小时前的{event_cn}信号, 现在如何"
    else:
        title = f"📊 24 小时复盘 · {coin}"
        sub = f"24 小时前的{event_cn}信号, 完整答卷"

    # 结论文案
    if is_gain and lev_pnl_pct >= 10:
        verdict = f"💎 大赚 · 跟上的吃肉了"
    elif is_gain and lev_pnl_pct >= 3:
        verdict = f"✅ 浮盈 · 方向对了"
    elif is_gain:
        verdict = f"➖ 微盈 · 不亏不赚"
    elif lev_pnl_pct <= -10:
        verdict = f"💀 大亏 · 反方向被埋"
    elif lev_pnl_pct <= -3:
        verdict = f"❌ 浮亏 · 暂时被套"
    else:
        verdict = f"➖ 微亏 · 还在拉扯"

    msg = f"{title}\n{sub}\n\n"
    msg += f"{side_emoji} 【{_esc(name)}】{side_cn} {coin} {leverage:.0f}x\n"
    msg += f"📊 仓位: {_b(_fmt_whale_size_usd(size_usd))}\n"
    msg += f"💵 入场价: ${entry:,.4f}".rstrip('0').rstrip('.') if entry < 1 else f"💵 入场价: ${entry:,.2f}"
    msg += f"\n📍 现价: ${cur_px:,.4f}".rstrip('0').rstrip('.') if cur_px < 1 else f"\n📍 现价: ${cur_px:,.2f}"
    msg += f"\n📈 价格变化: {pnl_color}{pnl_sign}{abs(px_pct):.2f}% ({leverage:.0f}x = {pnl_color}{pnl_sign}{abs(lev_pnl_pct):.1f}%)"
    msg += f"\n💰 仓位盈亏: {pnl_color}{_b(pnl_str)}\n\n"
    msg += f"{verdict}\n\n"
    msg += f"📲 开户: {HL_REFERRAL}"

    try:
        tail = tail_for_alert(
            f"followup_{kind}", f"{row['canonical_id']}_{coin}",
            v=int(lev_pnl_pct), r=min(10, abs(int(lev_pnl_pct/3))),
            src="hyperliquid",
            extra={"kind": kind, "event": event, "coin": coin, "name": name,
                   "pnl_usd": int(pnl_usd)}
        )
        msg += f"\n{tail}"
    except Exception:
        pass

    send_tg(msg)
    time.sleep(1)


# ============================================================
# 🆕 v29.1 信号战绩追推 (价格异动告警 4h/24h 后自动复盘信号准不准)
# ============================================================
def _enqueue_price_alert_followup(conn, alert):
    """价格异动告警发出后入队, 4h/24h 后自动复盘"""
    try:
        symbol = alert.get('symbol', '')
        direction = alert.get('direction', '')
        trigger_price = float(alert.get('price', 0) or 0)
        trigger_text = alert.get('trigger', '')
        if not symbol or not direction or trigger_price <= 0:
            return

        # 估算 24h 低点 → 触发价的累计涨幅 (仅涨势, 用于复盘消息里的 self-anchor)
        change_from_low = 0.0
        try:
            if direction == 'up':
                low_row = conn.execute(
                    "SELECT MIN(price) FROM price_history WHERE symbol=? "
                    "AND recorded_at >= datetime('now', '-24 hours')",
                    (symbol,)
                ).fetchone()
                if low_row and low_row[0] and low_row[0] > 0:
                    change_from_low = (trigger_price - low_row[0]) / low_row[0] * 100
        except Exception:
            pass

        now_str = _utcnow().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
            INSERT INTO price_alert_followup
            (symbol, direction, trigger_price, trigger_text, change_from_low, alerted_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (symbol, direction, trigger_price, trigger_text, change_from_low, now_str))
        conn.commit()
    except Exception as e:
        print(f"[PriceFollowup] enqueue 错误: {e}")


def check_price_alert_followups(conn):
    """主循环每次扫描调用. 找到 4h+/24h+ 还没复盘的信号, 计算涨跌并发送."""
    pushed = 0
    try:
        now = _utcnow()
        cutoff_4h = (now - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")
        cutoff_24h = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        cutoff_floor = (now - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")

        rows_4h = list(conn.execute("""
            SELECT id, symbol, direction, trigger_price, trigger_text, change_from_low, alerted_at
            FROM price_alert_followup
            WHERE alerted_at <= ? AND alerted_at > ? AND followup_4h_done = 0
            ORDER BY alerted_at
            LIMIT 10
        """, (cutoff_4h, cutoff_24h)).fetchall())

        rows_24h = list(conn.execute("""
            SELECT id, symbol, direction, trigger_price, trigger_text, change_from_low, alerted_at
            FROM price_alert_followup
            WHERE alerted_at <= ? AND alerted_at > ? AND followup_24h_done = 0
            ORDER BY alerted_at
            LIMIT 10
        """, (cutoff_24h, cutoff_floor)).fetchall())

        if not rows_4h and not rows_24h:
            return 0

        prices = _fetch_current_prices_hl()
        if not prices:
            return 0

        for kind, rows in [("4h", rows_4h), ("24h", rows_24h)]:
            for r in rows:
                row_dict = {
                    'id': r[0], 'symbol': r[1], 'direction': r[2],
                    'trigger_price': r[3], 'trigger_text': r[4],
                    'change_from_low': r[5], 'alerted_at': r[6],
                }
                symbol = row_dict['symbol']
                if symbol not in prices:
                    # 拿不到价 (币下架或不在 hyperliquid). 标记完成不重试.
                    col = "followup_4h_done" if kind == "4h" else "followup_24h_done"
                    conn.execute(f"UPDATE price_alert_followup SET {col}=1 WHERE id=?",
                                 (row_dict['id'],))
                    conn.commit()
                    continue

                cur_px = prices[symbol]
                try:
                    _send_price_alert_followup(row_dict, kind, cur_px)
                    pushed += 1
                except Exception as e:
                    print(f"[PriceFollowup] 推送错误 id={row_dict['id']}: {e}")

                col = "followup_4h_done" if kind == "4h" else "followup_24h_done"
                conn.execute(f"UPDATE price_alert_followup SET {col}=1 WHERE id=?",
                             (row_dict['id'],))
                conn.commit()

        return pushed
    except Exception as e:
        print(f"[PriceFollowup] 主循环错误: {e}")
        import traceback; traceback.print_exc()
        return 0


def _send_price_alert_followup(row, kind, cur_px):
    """发送信号战绩追推消息. kind: '4h' 或 '24h'"""
    symbol = row['symbol']
    direction = row['direction']
    trigger_price = row['trigger_price']
    trigger_text = row['trigger_text'] or ""

    if trigger_price <= 0 or cur_px <= 0:
        return

    # 价格变化 (绝对涨跌)
    px_pct = (cur_px - trigger_price) / trigger_price * 100

    # 信号是否准: up 看涨, down 看跌
    if direction == 'up':
        signal_pct = px_pct
        signal_cn = "突破信号 Breakout"
        direction_emoji = "🟢"
    else:
        signal_pct = -px_pct
        signal_cn = "跌破信号 Breakdown"
        direction_emoji = "🔴"

    # 结论文案 (基于信号正确率 — 信号 up 时涨多少, 信号 down 时跌多少)
    if signal_pct >= 10:
        verdict_emoji = "💎"
        verdict = "💎 大胜 · 信号靠谱, 跟上的吃肉了"
    elif signal_pct >= 3:
        verdict_emoji = "✅"
        verdict = "✅ 浮盈 · 方向对了"
    elif signal_pct >= -3:
        verdict_emoji = "➖"
        verdict = "➖ 横盘 · 不亏不赚"
    elif signal_pct >= -10:
        verdict_emoji = "❌"
        verdict = "❌ 浮亏 · 暂时被套"
    else:
        verdict_emoji = "💀"
        verdict = "💀 大亏 · 信号反向"

    # 价格格式化 (支持小数币如 PEPE 0.000022)
    def _fmt_px(p):
        if p <= 0:
            return "$0"
        if p < 1:
            # 8 位精度足够覆盖 PEPE/SHIB 这种小数币
            s = f"${p:.8f}".rstrip('0').rstrip('.')
            return s if s != '$' else '$0'
        elif p < 100:
            s = f"${p:.4f}".rstrip('0').rstrip('.')
            return s if s != '$' else '$0'
        else:
            return f"${p:,.2f}"

    if kind == "4h":
        title = f"⏱️ 4 小时信号复盘 · {symbol}"
        sub = f"4 小时前的{signal_cn}, 现在如何"
    else:
        title = f"📊 24 小时信号复盘 · {symbol}"
        sub = f"24 小时前的{signal_cn}, 完整答卷"

    px_emoji = "🟢" if px_pct >= 0 else "🔴"
    px_sign = "+" if px_pct >= 0 else ""

    msg = f"{title}\n{sub}\n\n"
    msg += f"{direction_emoji} 信号: {_b(_esc(trigger_text))}\n"
    msg += f"💵 触发价: {_b(_esc(_fmt_px(trigger_price)))}\n"
    msg += f"📍 现价: {_b(_esc(_fmt_px(cur_px)))}\n"
    msg += f"📈 {kind} 后变化: {px_emoji} {_b(f'{px_sign}{px_pct:.2f}%')}\n\n"
    msg += f"{verdict}\n\n"
    msg += f"🔗 https://app.hyperliquid.xyz/trade/{_esc(symbol)}\n"
    msg += f"📲 开户: {HL_REFERRAL}"

    # v26 尾标签
    try:
        tail = tail_for_alert(
            f"price_followup_{kind}", f"{symbol}_{kind}",
            v=int(signal_pct),
            r=min(10, abs(int(signal_pct/3))),
            src="hyperliquid",
            extra={"kind": kind, "symbol": symbol, "direction": direction,
                   "signal_pct": round(signal_pct, 2)}
        )
        msg += f"\n{tail}"
    except Exception:
        pass

    send_tg(msg)
    time.sleep(1)


# ============================================================
# 🆕 v27.2 每日盈亏榜 (Top 5 精选)
# ============================================================
def _get_whale_24h_pnl(conn, hours=24):
    """
    计算每个鲸鱼 24h 账户净值 delta, 返回按 delta 降序的列表
    v27.3: 支持 alias_of 马甲合并 — 主鲸 + 所有马甲的地址一起 sum
    返回: [{whale, cur_value, prev_value, delta, pct, ok_addrs, total_addrs, aliases}, ...]
    """
    whales = load_whale_list()
    if not whales:
        return []

    # v27.3: 按 canonical_id 聚合地址和马甲名
    addresses_by_canonical = {}    # canonical_id -> [addr, ...] (主鲸 + 马甲全部)
    alias_names_by_canonical = {}  # canonical_id -> [alias display name, ...]
    primary_by_canonical = {}      # canonical_id -> primary whale dict
    for w in whales:
        wid = w.get("id") or w.get("name", "unknown")
        canonical = _whale_canonical_id(w)
        addrs = [a.lower() for a in w.get("addresses", [])
                 if a and a.startswith("0x") and len(a) == 42]
        addresses_by_canonical.setdefault(canonical, []).extend(addrs)
        if canonical == wid:
            # 主鲸
            primary_by_canonical[canonical] = w
        else:
            # 马甲
            alias_names_by_canonical.setdefault(canonical, []).append(w.get("name", wid))

    cutoff_dt = _utcnow() - timedelta(hours=hours)
    cutoff_str = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S")
    window_start = (cutoff_dt - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
    window_end = (cutoff_dt + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")

    results = []
    for canonical, addresses in addresses_by_canonical.items():
        whale = primary_by_canonical.get(canonical)
        if not whale:
            # 孤儿马甲 (alias_of 指向不存在的主鲸), 跳过
            continue

        cur_total = 0.0
        prev_total = 0.0
        ok_addrs = 0

        for addr in addresses:
            cur_row = conn.execute(
                "SELECT account_value FROM whale_account_values WHERE address=? "
                "ORDER BY recorded_at DESC LIMIT 1",
                (addr,)
            ).fetchone()
            prev_row = conn.execute(
                "SELECT account_value FROM whale_account_values "
                "WHERE address=? AND recorded_at BETWEEN ? AND ? "
                "ORDER BY ABS(strftime('%s', recorded_at) - strftime('%s', ?)) LIMIT 1",
                (addr, window_start, window_end, cutoff_str)
            ).fetchone()
            if not prev_row:
                prev_row = conn.execute(
                    "SELECT account_value FROM whale_account_values "
                    "WHERE address=? AND recorded_at <= ? "
                    "ORDER BY recorded_at DESC LIMIT 1",
                    (addr, cutoff_str)
                ).fetchone()

            if cur_row and prev_row:
                cur_total += float(cur_row[0] or 0)
                prev_total += float(prev_row[0] or 0)
                ok_addrs += 1

        if ok_addrs == 0 or prev_total <= 0:
            continue

        delta = cur_total - prev_total
        pct = (delta / prev_total * 100) if prev_total > 0 else 0
        results.append({
            "whale": whale,
            "whale_id": canonical,
            "cur_value": cur_total,
            "prev_value": prev_total,
            "delta": delta,
            "pct": pct,
            "ok_addrs": ok_addrs,
            "total_addrs": len(addresses),
            "aliases": alias_names_by_canonical.get(canonical, []),
        })

    results.sort(key=lambda x: x["delta"], reverse=True)
    return results


# ============================================================
# 🆕 v28.8: FOMO 海报生成器 (4 类高价值告警自动配图)
# ============================================================
def _fomo_setup_canvas():
    """共享的 matplotlib 字体 + 配色 setup, 返回 (fig, fp, colors)"""
    if not HAS_MATPLOTLIB:
        return None, None, None
    font_path = ensure_chinese_font()
    cn_font = None
    if font_path:
        try:
            font_manager.fontManager.addfont(font_path)
            cn_font = font_manager.FontProperties(fname=font_path)
            plt.rcParams['font.sans-serif'] = [cn_font.get_name()]
            plt.rcParams['axes.unicode_minus'] = False
        except Exception:
            pass
    colors = {
        'BG': '#0f172a',           # 深蓝黑 (海报主背景, 制造严肃感)
        'BG_LIGHT': '#1e293b',     # 卡片背景
        'BRAND': '#f7931a',        # Hyperliquid 橙
        'GREEN': '#10b981',
        'RED': '#ef4444',
        'RED_DARK': '#dc2626',
        'WHITE': '#ffffff',
        'GRAY_LIGHT': '#cbd5e1',
        'GRAY': '#64748b',
        'YELLOW': '#fbbf24',
    }
    return cn_font, colors


def _fomo_draw_brand_bar(fig, colors, fp):
    """所有海报通用: 顶部品牌条 + 底部 CTA"""
    # 顶部橙色细条
    top = fig.add_axes([0, 0.97, 1, 0.03])
    top.set_facecolor(colors['BRAND']); top.set_xticks([]); top.set_yticks([])
    for s in top.spines.values(): s.set_visible(False)

    # 底部 CTA bar
    footer = fig.add_axes([0, 0, 1, 0.08])
    footer.set_facecolor(colors['BG_LIGHT']); footer.set_xticks([]); footer.set_yticks([])
    for s in footer.spines.values(): s.set_visible(False)
    fkw = {'fontproperties': fp} if fp else {}
    footer.text(0.5, 0.65, '@币世赏金台',
                ha='center', va='center', fontsize=14, fontweight='bold',
                color=colors['BRAND'], transform=footer.transAxes, **fkw)
    footer.text(0.5, 0.30, 'Hyperliquid 鲸鱼 5 分钟实时监控  ·  /subscribe 订阅私聊推送',
                ha='center', va='center', fontsize=9,
                color=colors['GRAY_LIGHT'], transform=footer.transAxes, **fkw)


def _fomo_poster_liq_red(whale, dist_pct, cp, market_px, tier=3):
    """
    清算预警海报 (黄/橙/红 三档)
    🆕 v28.9: 三档不同配色 + 文案, 培养追踪习惯
      tier=1 黄色 (距清算 8-15%)  - 关注信号
      tier=2 橙色 (3-8%)         - 警告信号  
      tier=3 红色 (<3%)          - 临近爆仓
    主视觉: 巨大的 "X.X% 距清算" + 仓位 + 杠杆
    """
    cn_font, colors = _fomo_setup_canvas()
    if not colors:
        return None
    fp = cn_font
    fkw = lambda **kw: ({'fontproperties': fp, **kw} if fp else kw)

    # 🆕 v28.9: 三档不同配色 + 标签文案
    if tier == 1:
        accent_color = '#fbbf24'   # YELLOW
        accent_dark = '#b45309'
        label_text = 'YELLOW · 关注'
        action_text = '距离清算还远, 注意监控'
    elif tier == 2:
        accent_color = '#fb923c'   # ORANGE
        accent_dark = '#c2410c'
        label_text = 'ORANGE · 警告'
        action_text = '风险显著, 关注是否补仓'
    else:  # tier=3
        accent_color = colors['RED']
        accent_dark = colors['RED_DARK']
        label_text = 'RED · 临近爆仓'
        action_text = '一旦填满, 立即清算'

    try:
        fig = plt.figure(figsize=(7.5, 10), dpi=120, facecolor=colors['BG'])
        _fomo_draw_brand_bar(fig, colors, fp)

        # ========== Header (鲸鱼名 + 紧急标签) ==========
        head = fig.add_axes([0, 0.85, 1, 0.12])
        head.set_facecolor(colors['BG']); head.set_xticks([]); head.set_yticks([])
        for s in head.spines.values(): s.set_visible(False)
        # 档位彩色标签 (宽度根据文字长度调)
        label_width = 0.28 if tier <= 2 else 0.30
        head.add_patch(plt.Rectangle((0.04, 0.55), label_width, 0.32,
                                      facecolor=accent_dark, transform=head.transAxes))
        head.text(0.04 + label_width/2, 0.71, label_text,
                  ha='center', va='center', fontsize=12, fontweight='bold',
                  color=colors['WHITE'], transform=head.transAxes, **fkw())
        # 鲸鱼名
        name = whale.get('name', '?')
        coin_side = f"{cp.get('coin','?')} {'多' if cp.get('side')=='long' else '空'}单"
        head.text(0.04, 0.30, f'【{name}】{coin_side}',
                  ha='left', va='center', fontsize=20, fontweight='bold',
                  color=colors['WHITE'], transform=head.transAxes, **fkw())

        # ========== 主视觉: 巨大的距清算 % ==========
        main = fig.add_axes([0, 0.40, 1, 0.45])
        main.set_facecolor(colors['BG']); main.set_xticks([]); main.set_yticks([])
        main.set_xlim(0, 1); main.set_ylim(0, 1)
        for s in main.spines.values(): s.set_visible(False)

        # "距清算" 标签
        main.text(0.5, 0.92, '距离清算',
                  ha='center', va='center', fontsize=16,
                  color=colors['GRAY_LIGHT'], transform=main.transAxes, **fkw())
        # 巨大百分比 (用档位配色)
        main.text(0.5, 0.55, f'{dist_pct:.2f}%',
                  ha='center', va='center', fontsize=110, fontweight='bold',
                  color=accent_color, transform=main.transAxes, **fkw())
        # 进度条
        bar_y = 0.20; bar_h = 0.06
        bar_x_start = 0.10; bar_x_end = 0.90
        bar_w_max = bar_x_end - bar_x_start
        # 距清算越近, 填充越满 (0% 距离 = 满, 15% 距离 = 空)
        max_safe_pct = 15.0
        fill_ratio = max(0.0, min(1.0, 1.0 - dist_pct / max_safe_pct))
        # 背景轨道
        main.add_patch(plt.Rectangle((bar_x_start, bar_y), bar_w_max, bar_h,
                                      facecolor=colors['BG_LIGHT'], transform=main.transAxes))
        # 档位配色填充
        main.add_patch(plt.Rectangle((bar_x_start, bar_y), bar_w_max * fill_ratio, bar_h,
                                      facecolor=accent_color, transform=main.transAxes))
        main.text(0.5, 0.10, action_text,
                  ha='center', va='center', fontsize=11,
                  color=colors['GRAY'], transform=main.transAxes, **fkw())

        # ========== 数据卡片 (仓位 / 杠杆 / 浮亏) ==========
        data = fig.add_axes([0, 0.10, 1, 0.30])
        data.set_facecolor(colors['BG']); data.set_xticks([]); data.set_yticks([])
        data.set_xlim(0, 1); data.set_ylim(0, 1)
        for s in data.spines.values(): s.set_visible(False)

        # 仓位
        size_usd = cp.get('size_usd', 0)
        size_str = f"${size_usd/1e6:.2f}M" if size_usd >= 1e6 else f"${size_usd/1e3:.1f}K"
        leverage = cp.get('leverage', 0)
        unr_pnl = cp.get('unrealized_pnl', 0)
        liq_px = cp.get('liq_px', 0)

        # 三栏数据
        for i, (label, value, color) in enumerate([
            ('仓位', size_str, colors['WHITE']),
            ('杠杆', f'{leverage:.0f}x', colors['YELLOW']),
            ('浮盈亏', f"{'+' if unr_pnl >= 0 else '-'}${abs(unr_pnl)/1e3:.1f}K",
             colors['GREEN'] if unr_pnl >= 0 else colors['RED']),
        ]):
            x_center = 0.20 + i * 0.30
            data.text(x_center, 0.75, label,
                      ha='center', va='center', fontsize=11,
                      color=colors['GRAY'], transform=data.transAxes, **fkw())
            data.text(x_center, 0.40, value,
                      ha='center', va='center', fontsize=22, fontweight='bold',
                      color=color, transform=data.transAxes, **fkw())

        # 价格警告 (拆成两个 text 调用避免 matplotlib mathtext 把 $...$ 当公式)
        # bug: f'... ${a}  >>  清算 ${b}' 里 2 个 $ 之间是中文, 会被当公式渲染 → 中文变方块
        market_str = f'当前 ${market_px:,.0f}'
        liq_str = f'清算 ${liq_px:,.0f}'
        data.text(0.30, 0.10, market_str,
                  ha='center', va='center', fontsize=12,
                  color=colors['GRAY_LIGHT'], transform=data.transAxes, **fkw())
        data.text(0.50, 0.10, '>>',
                  ha='center', va='center', fontsize=12,
                  color=colors['GRAY'], transform=data.transAxes, **fkw())
        data.text(0.70, 0.10, liq_str,
                  ha='center', va='center', fontsize=12,
                  color=colors['GRAY_LIGHT'], transform=data.transAxes, **fkw())

        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=120, bbox_inches=None, pad_inches=0,
                    facecolor=colors['BG'])
        buf.seek(0)
        plt.close(fig)
        return buf.getvalue()
    except Exception as e:
        print(f"[FOMO LiqRed] 失败: {e}")
        try: plt.close('all')
        except Exception: pass
        return None


def _fomo_poster_liquidated(whale, fill, closed_pnl, is_liq):
    """💥 真实爆仓海报"""
    cn_font, colors = _fomo_setup_canvas()
    if not colors:
        return None
    fp = cn_font
    fkw = lambda **kw: ({'fontproperties': fp, **kw} if fp else kw)
    try:
        fig = plt.figure(figsize=(7.5, 10), dpi=120, facecolor=colors['BG'])
        _fomo_draw_brand_bar(fig, colors, fp)

        # Header
        head = fig.add_axes([0, 0.82, 1, 0.15])
        head.set_facecolor(colors['BG']); head.set_xticks([]); head.set_yticks([])
        for s in head.spines.values(): s.set_visible(False)
        # 爆仓标签
        label = 'LIQUIDATED · 已爆仓' if is_liq else '大额平仓'
        head.add_patch(plt.Rectangle((0.04, 0.65), 0.36, 0.25,
                                      facecolor=colors['RED_DARK'], transform=head.transAxes))
        head.text(0.22, 0.78, label,
                  ha='center', va='center', fontsize=12, fontweight='bold',
                  color=colors['WHITE'], transform=head.transAxes, **fkw())
        name = whale.get('name', '?')
        coin = fill.get('coin', '?')
        head.text(0.04, 0.35, f'【{name}】{coin}',
                  ha='left', va='center', fontsize=22, fontweight='bold',
                  color=colors['WHITE'], transform=head.transAxes, **fkw())
        head.text(0.04, 0.10, '一觉醒来, 重回原点',
                  ha='left', va='center', fontsize=12,
                  color=colors['GRAY'], transform=head.transAxes, **fkw())

        # 主视觉: 巨大亏损金额
        main = fig.add_axes([0, 0.30, 1, 0.52])
        main.set_facecolor(colors['BG']); main.set_xticks([]); main.set_yticks([])
        main.set_xlim(0, 1); main.set_ylim(0, 1)
        for s in main.spines.values(): s.set_visible(False)

        loss_abs = abs(closed_pnl)
        if loss_abs >= 1e6:
            loss_str = f"-${loss_abs/1e6:.2f}M"
        else:
            loss_str = f"-${loss_abs/1e3:.0f}K"

        main.text(0.5, 0.85, '已实现亏损',
                  ha='center', va='center', fontsize=18,
                  color=colors['GRAY_LIGHT'], transform=main.transAxes, **fkw())
        main.text(0.5, 0.50, loss_str,
                  ha='center', va='center', fontsize=88, fontweight='bold',
                  color=colors['RED'], transform=main.transAxes, **fkw())

        # 仓位规模 + 价格
        try:
            sz = float(fill.get('sz', 0))
            px = float(fill.get('px', 0))
            size_usd = abs(sz * px)
            size_str = f"${size_usd/1e6:.2f}M" if size_usd >= 1e6 else f"${size_usd/1e3:.1f}K"
            main.text(0.5, 0.20, f'清算价格: ${px:,.4f}'.rstrip('0').rstrip('.') if px < 1 else f'清算价格: ${px:,.0f}',
                      ha='center', va='center', fontsize=14,
                      color=colors['WHITE'], transform=main.transAxes, **fkw())
            main.text(0.5, 0.10, f'被清算仓位: {size_str}',
                      ha='center', va='center', fontsize=12,
                      color=colors['GRAY_LIGHT'], transform=main.transAxes, **fkw())
        except Exception:
            pass

        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=120, bbox_inches=None, pad_inches=0,
                    facecolor=colors['BG'])
        buf.seek(0)
        plt.close(fig)
        return buf.getvalue()
    except Exception as e:
        print(f"[FOMO Liquidated] 失败: {e}")
        try: plt.close('all')
        except Exception: pass
        return None


def _fomo_poster_big_add(whale, current, size_diff_usd):
    """➕ 大加仓海报 (≥$5M)"""
    cn_font, colors = _fomo_setup_canvas()
    if not colors:
        return None
    fp = cn_font
    fkw = lambda **kw: ({'fontproperties': fp, **kw} if fp else kw)
    try:
        fig = plt.figure(figsize=(7.5, 10), dpi=120, facecolor=colors['BG'])
        _fomo_draw_brand_bar(fig, colors, fp)

        head = fig.add_axes([0, 0.82, 1, 0.15])
        head.set_facecolor(colors['BG']); head.set_xticks([]); head.set_yticks([])
        for s in head.spines.values(): s.set_visible(False)
        side_color = colors['GREEN'] if current.get('side') == 'long' else colors['RED']
        side_str = '做多' if current.get('side') == 'long' else '做空'
        head.add_patch(plt.Rectangle((0.04, 0.65), 0.32, 0.25,
                                      facecolor=side_color, transform=head.transAxes))
        head.text(0.20, 0.78, f'大加仓 · {side_str}',
                  ha='center', va='center', fontsize=12, fontweight='bold',
                  color=colors['WHITE'], transform=head.transAxes, **fkw())
        name = whale.get('name', '?')
        coin = current.get('coin', '?')
        head.text(0.04, 0.35, f'【{name}】{coin}',
                  ha='left', va='center', fontsize=22, fontweight='bold',
                  color=colors['WHITE'], transform=head.transAxes, **fkw())

        # 主视觉: 加仓金额
        main = fig.add_axes([0, 0.30, 1, 0.52])
        main.set_facecolor(colors['BG']); main.set_xticks([]); main.set_yticks([])
        main.set_xlim(0, 1); main.set_ylim(0, 1)
        for s in main.spines.values(): s.set_visible(False)

        if size_diff_usd >= 1e6:
            diff_str = f"+${size_diff_usd/1e6:.2f}M"
        else:
            diff_str = f"+${size_diff_usd/1e3:.0f}K"

        main.text(0.5, 0.85, '本次加仓',
                  ha='center', va='center', fontsize=18,
                  color=colors['GRAY_LIGHT'], transform=main.transAxes, **fkw())
        main.text(0.5, 0.50, diff_str,
                  ha='center', va='center', fontsize=78, fontweight='bold',
                  color=colors['GREEN'], transform=main.transAxes, **fkw())

        size_total = current.get('size_usd', 0)
        size_total_str = f"${size_total/1e6:.2f}M" if size_total >= 1e6 else f"${size_total/1e3:.1f}K"
        leverage = current.get('leverage', 0)
        main.text(0.5, 0.22, f'总仓位: {size_total_str}  ·  {leverage:.0f}x 杠杆',
                  ha='center', va='center', fontsize=14,
                  color=colors['WHITE'], transform=main.transAxes, **fkw())
        main.text(0.5, 0.10, '大资金重仓信号',
                  ha='center', va='center', fontsize=11,
                  color=colors['GRAY'], transform=main.transAxes, **fkw())

        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=120, bbox_inches=None, pad_inches=0,
                    facecolor=colors['BG'])
        buf.seek(0)
        plt.close(fig)
        return buf.getvalue()
    except Exception as e:
        print(f"[FOMO BigAdd] 失败: {e}")
        try: plt.close('all')
        except Exception: pass
        return None


def _fomo_poster_resonance(coin, side, by_canonical, primary_lookup, total_usd):
    """🌊 共振海报 (多鲸鱼同向)"""
    cn_font, colors = _fomo_setup_canvas()
    if not colors:
        return None
    fp = cn_font
    fkw = lambda **kw: ({'fontproperties': fp, **kw} if fp else kw)
    try:
        fig = plt.figure(figsize=(7.5, 10), dpi=120, facecolor=colors['BG'])
        _fomo_draw_brand_bar(fig, colors, fp)

        head = fig.add_axes([0, 0.82, 1, 0.15])
        head.set_facecolor(colors['BG']); head.set_xticks([]); head.set_yticks([])
        for s in head.spines.values(): s.set_visible(False)
        side_color = colors['GREEN'] if side == 'long' else colors['RED']
        side_str = '做多' if side == 'long' else '做空'
        head.add_patch(plt.Rectangle((0.04, 0.65), 0.34, 0.25,
                                      facecolor=side_color, transform=head.transAxes))
        head.text(0.21, 0.78, f'鲸群共振 · {side_str}',
                  ha='center', va='center', fontsize=12, fontweight='bold',
                  color=colors['WHITE'], transform=head.transAxes, **fkw())
        head.text(0.04, 0.35, f'多鲸同向 · {coin}',
                  ha='left', va='center', fontsize=22, fontweight='bold',
                  color=colors['WHITE'], transform=head.transAxes, **fkw())

        # 主视觉: 总仓位
        n_whales = len(by_canonical)
        if total_usd >= 1e6:
            total_str = f"${total_usd/1e6:.1f}M"
        else:
            total_str = f"${total_usd/1e3:.0f}K"

        main = fig.add_axes([0, 0.55, 1, 0.27])
        main.set_facecolor(colors['BG']); main.set_xticks([]); main.set_yticks([])
        main.set_xlim(0, 1); main.set_ylim(0, 1)
        for s in main.spines.values(): s.set_visible(False)
        main.text(0.5, 0.78, f'{n_whales} 只鲸鱼合计',
                  ha='center', va='center', fontsize=16,
                  color=colors['GRAY_LIGHT'], transform=main.transAxes, **fkw())
        main.text(0.5, 0.35, total_str,
                  ha='center', va='center', fontsize=72, fontweight='bold',
                  color=side_color, transform=main.transAxes, **fkw())

        # 鲸鱼列表 (最多 4 个)
        list_area = fig.add_axes([0, 0.10, 1, 0.45])
        list_area.set_facecolor(colors['BG']); list_area.set_xticks([]); list_area.set_yticks([])
        list_area.set_xlim(0, 1); list_area.set_ylim(0, 1)
        for s in list_area.spines.values(): s.set_visible(False)

        sorted_whales = sorted(by_canonical.items(), key=lambda x: x[1]['size_usd'], reverse=True)[:4]
        list_area.text(0.5, 0.92, '参与鲸鱼',
                       ha='center', va='center', fontsize=13,
                       color=colors['GRAY_LIGHT'], transform=list_area.transAxes, **fkw())
        for i, (canonical, info) in enumerate(sorted_whales):
            whale = primary_lookup.get(canonical, {})
            wname = whale.get('name', canonical)
            wsize = info['size_usd']
            wsize_str = f"${wsize/1e6:.2f}M" if wsize >= 1e6 else f"${wsize/1e3:.0f}K"
            wlev = info.get('leverage', 0)
            y = 0.78 - i * 0.18
            # 鲸鱼名
            list_area.text(0.10, y, wname,
                           ha='left', va='center', fontsize=15, fontweight='bold',
                           color=colors['WHITE'], transform=list_area.transAxes, **fkw())
            # 仓位 + 杠杆
            list_area.text(0.90, y, f'{wsize_str}  {wlev:.0f}x',
                           ha='right', va='center', fontsize=15, fontweight='bold',
                           color=side_color, transform=list_area.transAxes, **fkw())

        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=120, bbox_inches=None, pad_inches=0,
                    facecolor=colors['BG'])
        buf.seek(0)
        plt.close(fig)
        return buf.getvalue()
    except Exception as e:
        print(f"[FOMO Resonance] 失败: {e}")
        try: plt.close('all')
        except Exception: pass
        return None


def _fomo_send_async(image_bytes, caption_short=""):
    """
    🆕 v28.8: 海报发到频道 (作为额外消息, 不替代文字告警)
    caption_short: 图下方的短说明, 不超过 200 字 (超了 TG 截断)
    失败静默 (不影响主告警)
    """
    if not image_bytes:
        return False
    try:
        send_tg_photo(image_bytes, caption_short)
        return True
    except Exception as e:
        print(f"[FOMO Send] 失败: {e}")
        return False


def generate_whale_pnl_chart(ranked, date_str):
    """
    🆕 v28.7: 海报级竖版盈亏榜 (900×1200, 9:16 适合手机全屏 + 社交转发)
    设计原则:
      - 深色品牌 header (Hyperliquid 橙色 #f7931a)
      - 每个鲸鱼一个"卡片区": 名字 + tags + 柱子 + 数字
      - 数字超大加粗, 一眼可读
      - Footer 带订阅 CTA, 促进转发
    返回 bytes, 失败返回 None
    """
    if not HAS_MATPLOTLIB or not ranked:
        return None
    try:
        top5 = ranked[:5]
        n = len(top5)

        # 字体
        font_path = ensure_chinese_font()
        cn_font = None
        if font_path:
            try:
                font_manager.fontManager.addfont(font_path)
                cn_font = font_manager.FontProperties(fname=font_path)
                plt.rcParams['font.sans-serif'] = [cn_font.get_name()]
                plt.rcParams['axes.unicode_minus'] = False
            except Exception:
                pass
        fp = cn_font if cn_font else None
        def _fkw(**kw):
            base = {'fontproperties': fp} if fp else {}
            base.update(kw)
            return base

        # 品牌配色 (深灰 + Hyperliquid 橙 + 绿红)
        COLOR_BG = '#f9fafb'       # 主背景浅灰, 不刺眼
        COLOR_HEADER = '#0f172a'   # 深蓝黑 header
        COLOR_BRAND = '#f7931a'    # Hyperliquid 橙
        COLOR_FOOTER = '#1f2937'
        COLOR_GREEN = '#10b981'
        COLOR_RED = '#ef4444'
        COLOR_GREEN_DARK = '#065f46'
        COLOR_RED_DARK = '#991b1b'
        COLOR_GRAY = '#6b7280'
        COLOR_TEXT = '#111827'
        COLOR_MEDAL_GOLD = '#fbbf24'
        COLOR_MEDAL_SILVER = '#9ca3af'
        COLOR_MEDAL_BRONZE = '#d97706'

        # 海报尺寸: 900×1200 (9:16 竖版). DPI 120 → 实际 900×1200 px
        fig = plt.figure(figsize=(7.5, 10), dpi=120, facecolor=COLOR_BG)

        # ========== HEADER ==========
        header = fig.add_axes([0, 0.89, 1, 0.11])
        header.set_facecolor(COLOR_HEADER)
        header.set_xticks([]); header.set_yticks([])
        for s in header.spines.values():
            s.set_visible(False)
        # 橙色竖条
        header.add_patch(plt.Rectangle((0, 0), 0.015, 1, transform=header.transAxes,
                                        color=COLOR_BRAND, zorder=10))
        # 标题 (🆕 v30.14.10: 根据 n 动态化, 1 个鲸鱼时不显示"榜"和"Top", 避免显得像 bug)
        title_main = 'Hyperliquid 鲸鱼 24h 盈亏' if n == 1 else 'Hyperliquid 鲸鱼 24h 盈亏榜'
        if n == 1:
            title_sub = date_str
        elif n < 5:
            title_sub = f'Top {n}  ·  {date_str}'
        else:
            title_sub = f'Top 5 精选  ·  {date_str}'
        header.text(0.05, 0.62, title_main,
                    ha='left', va='center',
                    fontsize=19, fontweight='bold', color='white',
                    transform=header.transAxes, **_fkw())
        header.text(0.05, 0.28, title_sub,
                    ha='left', va='center',
                    fontsize=11, color='#cbd5e1',
                    transform=header.transAxes, **_fkw())
        # 右上角品牌 "HL" 徽章 (用矩形代替 emoji)
        header.add_patch(plt.Rectangle((0.90, 0.32), 0.08, 0.36, transform=header.transAxes,
                                        facecolor=COLOR_BRAND, zorder=5, alpha=0.95))
        header.text(0.94, 0.50, 'HL',
                    ha='center', va='center',
                    fontsize=14, fontweight='bold', color='white',
                    transform=header.transAxes, zorder=6, **_fkw())

        # ========== MAIN AREA (每个鲸鱼一个卡片区) ==========
        main_top = 0.87
        main_bottom = 0.08
        card_height = (main_top - main_bottom) / n

        deltas = [r["delta"] for r in top5]
        max_abs = max(abs(d) for d in deltas) if deltas else 1
        if max_abs == 0:
            max_abs = 1

        medal_colors = [COLOR_MEDAL_GOLD, COLOR_MEDAL_SILVER, COLOR_MEDAL_BRONZE]

        for idx, r in enumerate(top5):
            whale = r["whale"]
            delta = r["delta"]
            pct = r["pct"]
            name = whale.get('name', r['whale_id'])
            tags = whale.get('tags', [])
            is_gain = delta >= 0

            card_y_top = main_top - idx * card_height
            card_y_bot = card_y_top - card_height

            card = fig.add_axes([0, card_y_bot, 1, card_height])
            card.set_xticks([]); card.set_yticks([])
            card.set_xlim(0, 1); card.set_ylim(0, 1)
            card.set_facecolor(COLOR_BG)
            for s in card.spines.values():
                s.set_visible(False)
            if idx > 0:
                card.axhline(0.97, color='#e5e7eb', linewidth=0.8)

            # 左侧名次徽章 (前 3 名用彩色圆角矩形, 后 2 用文字)
            # matplotlib 的 Circle 在非方形 axes 里会变椭圆, 用 FancyBboxPatch 更可控
            if idx < 3:
                # 彩色圆角矩形徽章
                from matplotlib.patches import FancyBboxPatch
                badge = FancyBboxPatch((0.04, 0.66), 0.06, 0.20,
                                        boxstyle="round,pad=0.005,rounding_size=0.015",
                                        facecolor=medal_colors[idx],
                                        edgecolor='none',
                                        transform=card.transAxes, zorder=5)
                card.add_patch(badge)
                card.text(0.07, 0.76, str(idx + 1),
                          ha='center', va='center',
                          fontsize=15, fontweight='bold', color='white',
                          transform=card.transAxes, zorder=6, **_fkw())
            else:
                card.text(0.07, 0.76, f'{idx+1}.',
                          ha='center', va='center',
                          fontsize=14, fontweight='bold', color=COLOR_GRAY,
                          transform=card.transAxes, **_fkw())

            # 鲸鱼名 (大字)
            card.text(0.13, 0.80, name,
                      ha='left', va='center',
                      fontsize=17, fontweight='bold', color=COLOR_TEXT,
                      transform=card.transAxes, **_fkw())

            # tags 副标题
            if tags:
                tag_str = " · ".join(tags[:3])
                card.text(0.13, 0.62, tag_str,
                          ha='left', va='center',
                          fontsize=10, color=COLOR_GRAY,
                          transform=card.transAxes, **_fkw())

            # 柱子区
            bar_x_start = 0.13
            bar_x_end = 0.72
            bar_width_max = bar_x_end - bar_x_start

            ratio = abs(delta) / max_abs
            bar_width = bar_width_max * ratio if max_abs > 0 else 0
            bar_color = COLOR_GREEN if is_gain else COLOR_RED
            bar_y = 0.32
            bar_h = 0.14

            # 背景轨道
            card.add_patch(plt.Rectangle((bar_x_start, bar_y), bar_width_max, bar_h,
                                          facecolor='#e5e7eb', alpha=0.5,
                                          transform=card.transAxes, zorder=1))
            # 实际柱子
            if bar_width > 0.005:
                card.add_patch(plt.Rectangle((bar_x_start, bar_y), bar_width, bar_h,
                                              facecolor=bar_color,
                                              transform=card.transAxes, zorder=2))

            # 柱末数字
            sign = "+" if is_gain else "-"
            val_abs = abs(delta)
            if val_abs >= 1e6:
                amt = f"{sign}${val_abs/1e6:.2f}M"
            elif val_abs >= 1e3:
                amt = f"{sign}${val_abs/1e3:.1f}K"
            else:
                amt = f"{sign}${val_abs:.0f}"
            amt_color = COLOR_GREEN_DARK if is_gain else COLOR_RED_DARK
            card.text(0.95, bar_y + bar_h/2, amt,
                      ha='right', va='center',
                      fontsize=17, fontweight='bold', color=amt_color,
                      transform=card.transAxes, **_fkw())
            pct_str = f"{sign}{abs(pct):.1f}%"
            card.text(0.95, 0.15, pct_str,
                      ha='right', va='center',
                      fontsize=11, color=amt_color, alpha=0.7,
                      transform=card.transAxes, **_fkw())

        # ========== FOOTER ==========
        footer = fig.add_axes([0, 0, 1, 0.07])
        footer.set_facecolor(COLOR_FOOTER)
        footer.set_xticks([]); footer.set_yticks([])
        for s in footer.spines.values():
            s.set_visible(False)
        footer.add_patch(plt.Rectangle((0, 0.85), 1, 0.15, transform=footer.transAxes,
                                        color=COLOR_BRAND, zorder=10))
        footer.text(0.03, 0.42, '@币世赏金台  ·  /subscribe 订阅私聊推送',
                    ha='left', va='center',
                    fontsize=10, fontweight='bold', color='white',
                    transform=footer.transAxes, **_fkw())
        footer.text(0.97, 0.42, f'数据: Hyperliquid  ·  {date_str}',
                    ha='right', va='center',
                    fontsize=9, color='#9ca3af',
                    transform=footer.transAxes, **_fkw())

        # 导出
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=120,
                    bbox_inches=None, pad_inches=0,
                    facecolor=COLOR_BG)
        buf.seek(0)
        plt.close(fig)
        return buf.getvalue()
    except Exception as e:
        print(f"[PnLChart] 生成失败: {e}")
        import traceback; traceback.print_exc()
        try: plt.close('all')
        except Exception: pass
        return None


def push_whale_daily_pnl(conn):
    """
    每日 9 点推送鲸鱼盈亏榜 (图 + 简短 caption)
    首日无 24h 历史时降级纯文本说明
    """
    try:
        _init_whale_db(conn)
        ranked = _get_whale_24h_pnl(conn, hours=24)
        now_cn = datetime.now(timezone.utc) + timedelta(hours=8)
        date_str = now_cn.strftime("%Y-%m-%d")

        if not ranked:
            send_tg(f"📊 Hyperliquid 鲸鱼 24h 盈亏榜 · {date_str}\n\n"
                    f"还在积累 24 小时数据, 明天同一时间出榜 📈\n"
                    f"(需要至少一个完整 24h 周期的账户净值快照)")
            return

        top5 = ranked[:5]

        # 生成图
        chart = generate_whale_pnl_chart(ranked, date_str)

        # Caption (简洁)
        # 🆕 v30.14.10: caption 标题动态化 (与海报一致)
        n = len(top5)
        if n == 1:
            cap_title = "📊 <b>Hyperliquid 鲸鱼 24h 盈亏</b>"
            cap_subtitle = f"🗓️ {date_str}"
        elif n < 5:
            cap_title = "📊 <b>Hyperliquid 鲸鱼 24h 盈亏榜</b>"
            cap_subtitle = f"🗓️ {date_str} · Top {n}"
        else:
            cap_title = "📊 <b>Hyperliquid 鲸鱼 24h 盈亏榜</b>"
            cap_subtitle = f"🗓️ {date_str} · Top 5 精选"
        caption_lines = [cap_title, cap_subtitle, ""]
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, r in enumerate(top5):
            whale = r["whale"]
            name = whale.get("name", r["whale_id"])
            emoji = whale.get("emoji", "🐋")
            d = r["delta"]
            pct = r["pct"]
            sign = "+" if d >= 0 else "−"
            val_abs = abs(d)
            if val_abs >= 1e6:
                amt = f"{sign}${val_abs/1e6:.2f}M"
            elif val_abs >= 1e3:
                amt = f"{sign}${val_abs/1e3:.1f}K"
            else:
                amt = f"{sign}${val_abs:.0f}"
            color = "🟢" if d >= 0 else "🔴"
            # v27.3: 含马甲提示
            aliases = r.get("aliases", [])
            alias_tag = f" <i>(含 {', '.join(_esc(a) for a in aliases[:2])})</i>" if aliases else ""
            caption_lines.append(
                f"{medals[i]} {emoji} {_esc(name)}{alias_tag}  {color} <b>{amt}</b> ({sign}{abs(pct):.1f}%)"
            )

        # 全局统计
        total_winners = sum(1 for r in ranked if r["delta"] > 0)
        total_losers = sum(1 for r in ranked if r["delta"] < 0)
        total_pnl = sum(r["delta"] for r in ranked)
        caption_lines.append("")
        caption_lines.append(f"📈 赢 {total_winners} / 📉 亏 {total_losers} · 鲸群合计 "
                             f"{'+' if total_pnl >= 0 else ''}{_fmt_whale_size_usd(total_pnl) if total_pnl >=0 else '-' + _fmt_whale_size_usd(abs(total_pnl))}")
        caption_lines.append(f"📲 开户: {HL_REFERRAL}")

        caption = "\n".join(caption_lines)

        # 尾行标签
        try:
            tail = tail_for_alert(
                "whale_pnl_daily", date_str,
                v=int(abs(total_pnl) / 1000),
                r=len(top5),
                src="hyperliquid",
                extra={"date": date_str, "winners": total_winners, "losers": total_losers}
            )
            caption += f"\n{tail}"
        except Exception:
            pass

        if chart:
            send_tg_photo(chart, caption)
        else:
            send_tg(caption)
        print(f"[PnLDaily] ✅ 已推送 {len(top5)} 个鲸鱼盈亏榜 ({len(ranked)} 个参榜)")
    except Exception as e:
        print(f"[PnLDaily] 错误: {e}")
        import traceback; traceback.print_exc()


# ============================================================
# 主循环
# ============================================================

# ============================================================
# v30.1 赏金哨 (Sentinel) — Michill 算法逆向 + 提速
# ============================================================
# v30.1 改动 (基于 michill.ai 5/1-5/3 战绩反推):
#   1. 独立 10 分钟快速通道 (匹配她的扫描频率, 不再走主循环 30min)
#   2. BN OI 单维度强信号 (她产品标注"主判断: Binance OI", 直推规则)
#   3. signal_time 字段 (精确到分钟, 后续对比她的开仓时间)
#
# 数据源:
#   • Binance Futures public API (主, OI 异动核心)
#   • Hyperliquid metaAndAssetCtxs (辅, 跨所共振)
#   • Whale positions (复用 v27+, 鲸鱼共振)
#
# 评分维度 (满分 100):
#   • OI 异动 25 分 (单所 1h ≥15% +70, ≥30% +100; 双所同向 +30%)
#   • 价格异动 20 分 (24h ≥30% 满分)
#   • Funding 健康 15 分 (温和正费率最高分)
#   • 量能放大 15 分
#   • 鲸鱼共振 15 分
#   • DEX 扩散 10 分 (Stage 2 启用)
#
# 推送规则 (双通道):
#   通道 A (综合分): score ≥ SENTINEL_PUSH_THRESHOLD (默认 50)
#   通道 B (强信号): BN OI 1h ≥ 30% 且 24h 涨幅 > -10% (Michill 派)
#
# 阶段: 蓄势 / 启动初段 / 启动 / 启动末段 / 过热 / 等待回踩 / 退役 / 观察
#
# Railway 环境变量:
#   • ANTHROPIC_API_KEY                启用 AI 判断
#   • SENTINEL_PUSH_THRESHOLD=50       综合分推送阈值
#   • SENTINEL_DIRECT_OI_PCT=30        BN OI 强信号阈值
#   • SENTINEL_DIRECT_MIN_SCORE=50     🆕 v30.12: 直推综合分 floor (防 OI 孤峰)
#   • SENTINEL_INTERVAL_SEC=600        扫描周期 (默认 10 分钟)
#   • SENTINEL_VOL_MIN_USD=5000000     最小 24h 量能
#   • SENTINEL_VOL_MAX_USD=500000000   最大 24h 量能 (避主流)
#   • SENTINEL_OI_MIN_USD=500000       最小 OI
#   • SENTINEL_COOLDOWN_HOURS=4        同币推送冷却
# ============================================================


# 配置 (放到文件顶部 OI_MIN_USD 那一行附近)
BINANCE_FAPI = "https://fapi.binance.com"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
SENTINEL_PUSH_THRESHOLD = _env_int("SENTINEL_PUSH_THRESHOLD", "60")
SENTINEL_DIRECT_OI_PCT = _env_float("SENTINEL_DIRECT_OI_PCT", "30")
# 🆕 v30.12: 直推也要综合分 floor (防止 OI 孤峰假信号, 如 ACE 36/100 触发)
SENTINEL_DIRECT_MIN_SCORE = _env_int("SENTINEL_DIRECT_MIN_SCORE", "50")
# 🆕 v30.13: 早期信号过滤 — 24h 涨幅 > 此值时不推 (避开 FOMO 顶部, 数据显示 24h 已涨 > 5% 的信号 4h 内 close 胜率仅 23%)
# 设为 999 可关闭过滤 (回滚用)
SENTINEL_MAX_CHANGE_24H = _env_float("SENTINEL_MAX_CHANGE_24H", "3")
# 🆕 v30.13: SHORT 信号 dogfood — 1=启用 (仅私聊 admin, 不进频道) / 0=禁用
# 触发: score≥60 + OI≥30% + 24h>10% (FOMO 顶部, 历史 4h 内 94% 回吐 -3%+)
# 🆕 v30.14.20: SHORT 默认进频道 (基于 5/15 dogfood 数据: 4h 67% 胜率 / 均 +3.30%)
# env SENTINEL_SHORT_DOGFOOD=1 可回退 admin 私聊
SENTINEL_SHORT_DOGFOOD = os.getenv("SENTINEL_SHORT_DOGFOOD", "0") == "1"
SENTINEL_INTERVAL_SEC = _env_int("SENTINEL_INTERVAL_SEC", "600")
SENTINEL_VOL_MIN_USD = _env_int("SENTINEL_VOL_MIN_USD", "5000000")
SENTINEL_VOL_MAX_USD = _env_int("SENTINEL_VOL_MAX_USD", "500000000")
SENTINEL_OI_MIN_USD = _env_int("SENTINEL_OI_MIN_USD", "500000")
SENTINEL_COOLDOWN_HOURS = _env_int("SENTINEL_COOLDOWN_HOURS", "4")


# ============================================================
# v30.1: 赏金哨数据库初始化 (含 v30→v30.1 自动迁移)
# ============================================================
def init_sentinel_db(conn):
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS sentinel_signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        venue TEXT NOT NULL,
        score INTEGER NOT NULL,
        stage TEXT NOT NULL,
        direction TEXT,
        price REAL,
        oi_usd_binance REAL DEFAULT 0,
        oi_usd_hyperliquid REAL DEFAULT 0,
        funding_binance REAL DEFAULT 0,
        funding_hyperliquid REAL DEFAULT 0,
        change_24h REAL DEFAULT 0,
        vol_24h_usd REAL DEFAULT 0,
        score_components TEXT,
        whale_resonance INTEGER DEFAULT 0,
        ai_judgment TEXT,
        pushed INTEGER DEFAULT 0,
        push_channel TEXT,
        signal_time TEXT,
        recorded_at TEXT NOT NULL
    )""")
    # v30.1 迁移: 旧表追加新列
    for col, typ in [("push_channel", "TEXT"), ("signal_time", "TEXT")]:
        try:
            c.execute(f"ALTER TABLE sentinel_signals ADD COLUMN {col} {typ}")
        except Exception:
            pass

    c.execute("CREATE INDEX IF NOT EXISTS idx_sentinel_sym ON sentinel_signals(symbol, recorded_at)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sentinel_score ON sentinel_signals(score)")

    c.execute("""CREATE TABLE IF NOT EXISTS sentinel_oi_snapshots (
        symbol TEXT NOT NULL,
        venue TEXT NOT NULL,
        oi_usd REAL,
        recorded_at TEXT NOT NULL
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sentinel_oi ON sentinel_oi_snapshots(symbol, venue, recorded_at)")
    conn.commit()


# ============================================================
# v30: Binance Futures 数据抓取 (公开 API, 无需 key)
# ============================================================
def _fetch_binance_oi_one(symbol):
    try:
        r = requests.get(
            f"{BINANCE_FAPI}/fapi/v1/openInterest",
            params={"symbol": symbol},
            timeout=8
        )
        if r.status_code == 200:
            return float(r.json().get("openInterest", 0) or 0)
    except Exception:
        pass
    return 0


def fetch_binance_perp_data():
    coins = {}
    try:
        r1 = requests.get(f"{BINANCE_FAPI}/fapi/v1/ticker/24hr", timeout=15)
        if r1.status_code != 200:
            print(f"[Sentinel/BN] ❌ ticker HTTP {r1.status_code}")
            return coins
        for t in r1.json():
            sym = t.get("symbol", "")
            if not sym.endswith("USDT") or "_" in sym:
                continue
            coin = sym[:-4]
            vol_usd = float(t.get("quoteVolume", 0) or 0)
            if vol_usd < SENTINEL_VOL_MIN_USD or vol_usd > SENTINEL_VOL_MAX_USD:
                continue
            coins[coin] = {
                "symbol": coin,
                "price": float(t.get("lastPrice", 0) or 0),
                "vol_24h": vol_usd,
                "change_24h": float(t.get("priceChangePercent", 0) or 0),
                "oi_usd": 0,
                "funding": 0,
            }

        r2 = requests.get(f"{BINANCE_FAPI}/fapi/v1/premiumIndex", timeout=15)
        if r2.status_code == 200:
            for p in r2.json():
                sym = p.get("symbol", "")
                if not sym.endswith("USDT") or "_" in sym:
                    continue
                coin = sym[:-4]
                if coin in coins:
                    coins[coin]["funding"] = float(p.get("lastFundingRate", 0) or 0)

        # v30.1: OI 并发查询 100 币 (按 |24h涨跌| 排序)
        sorted_coins = sorted(coins.values(), key=lambda x: abs(x["change_24h"]), reverse=True)[:100]
        target_syms = [f"{c['symbol']}USDT" for c in sorted_coins]

        with ThreadPoolExecutor(max_workers=12) as ex:
            futs = {ex.submit(_fetch_binance_oi_one, s): s for s in target_syms}
            for fut in as_completed(futs, timeout=30):
                sym = futs[fut]
                try:
                    oi_coin_amt = fut.result()
                    coin = sym[:-4]
                    if coin in coins and oi_coin_amt > 0:
                        coins[coin]["oi_usd"] = oi_coin_amt * coins[coin]["price"]
                except Exception:
                    pass

        coins = {c: d for c, d in coins.items() if d["oi_usd"] >= SENTINEL_OI_MIN_USD}
        print(f"[Sentinel/BN] ✅ 抓 {len(coins)} 币种 (vol ${SENTINEL_VOL_MIN_USD/1e6:.0f}M-${SENTINEL_VOL_MAX_USD/1e6:.0f}M)")
    except Exception as e:
        print(f"[Sentinel/BN] ❌ {e}")
    return coins


def fetch_hyperliquid_perp_data_for_sentinel():
    coins = {}
    try:
        r = requests.post(
            "https://api.hyperliquid.xyz/info",
            json={"type": "metaAndAssetCtxs"},
            timeout=15
        )
        if r.status_code != 200:
            return coins
        data = r.json()
        if not isinstance(data, list) or len(data) < 2:
            return coins
        universe = data[0].get("universe", [])
        ctxs = data[1]
        for i, ctx in enumerate(ctxs):
            if i >= len(universe):
                break
            coin = universe[i].get("name", "")
            if not coin:
                continue
            mark_px = float(ctx.get("markPx", 0) or 0)
            oi_coin_amt = float(ctx.get("openInterest", 0) or 0)
            if mark_px <= 0 or oi_coin_amt <= 0:
                continue
            coins[coin] = {
                "symbol": coin,
                "price": mark_px,
                "oi_usd": oi_coin_amt * mark_px,
                "funding": float(ctx.get("funding", 0) or 0),
            }
        print(f"[Sentinel/HL] ✅ 抓 {len(coins)} 币种")
    except Exception as e:
        print(f"[Sentinel/HL] ❌ {e}")
    return coins


# ============================================================
# v30: OI 历史快照
# ============================================================
def store_sentinel_oi_snapshot(conn, symbol, venue, oi_usd):
    try:
        conn.execute(
            "INSERT INTO sentinel_oi_snapshots (symbol, venue, oi_usd, recorded_at) VALUES (?,?,?,datetime('now'))",
            (symbol, venue, oi_usd)
        )
    except Exception:
        pass


def get_sentinel_oi_change(conn, symbol, venue, hours_ago=1):
    try:
        prev_row = conn.execute(
            "SELECT oi_usd FROM sentinel_oi_snapshots WHERE symbol=? AND venue=? "
            "AND recorded_at <= datetime('now', ?) ORDER BY recorded_at DESC LIMIT 1",
            (symbol, venue, f"-{hours_ago} hours")
        ).fetchone()
        if not prev_row or not prev_row[0] or prev_row[0] <= 0:
            return None
        cur_row = conn.execute(
            "SELECT oi_usd FROM sentinel_oi_snapshots WHERE symbol=? AND venue=? "
            "ORDER BY recorded_at DESC LIMIT 1",
            (symbol, venue)
        ).fetchone()
        if not cur_row:
            return None
        return ((cur_row[0] - prev_row[0]) / prev_row[0]) * 100
    except Exception:
        return None


# ============================================================
# v30.1: 综合分计算 (返回 4-tuple, 含强信号 flag)
# ============================================================
def compute_sentinel_score(symbol, bn_data, hl_data, conn, whale_count, price_1h_pct=None):
    """返回: (score 0-100, components dict, direction, direct_strong_signal bool)

    🆕 v30.14.7 (报告"双重计分 + Funding 口径"修复):
    - OI 32 → 25 (脉冲, max BN/HL)
    - 共所 14 → 15 (一致性, min BN/HL — 防双重计分)
    - Funding 5 → 8 + 8h 口径统一 (HL × 8 折算)
    - 量能 → 相对量能 (按 vol 大小分档, 大币需大涨幅, 小币温和涨幅即可)
    - 通道 funding filter 阈值 0.05% → 0.04% (8h 口径)
    - 总分: OI 25 + 价格 24 + 量能 15 + 共所 15 + Funding 8 = 87 max
    - hard reject: |24h 涨幅| ≥20%
    - components["v2_pass"]: shadow 模式 v2 子集标签
    - price_1h_pct: 调用方传入 (None 时降级用 24h<15)
    """
    components = {"oi": 0, "price": 0, "funding": 0, "volume": 0, "whale": 0, "dex": 0,
                  "v2_pass": 0}  # 🆕 v2 shadow flag

    primary = bn_data or hl_data
    change_24h = bn_data.get("change_24h", 0) if bn_data else 0
    direction = "up" if change_24h > 0 else "down" if change_24h < 0 else "flat"

    # === 🚫 v2 Hard Reject: 24h 涨幅 ≥20% (FOMO 顶部, 文献证实强反向) ===
    # 历史 /winrate 数据: 24h ≥20% 的信号 24h Alpha -17%, 反向指标
    if abs(change_24h) >= 20:
        components["price"] = 0  # 不打分
        return 0, components, direction, False

    # === OI 维度 (🆕 v30.14.7: 32→25, 报告指出共所是 OI 子集, 双重计分) ===
    # 拆成两层:
    #   OI 脉冲 (max BN, HL) — 25 分
    #   共所一致性 (min BN, HL) — 15 分 (后面单算)
    # 总和 40 分, 比 v30.14.6 的 46 分 (32+14) 减 6 分还给其他维度
    bn_oi_change = get_sentinel_oi_change(conn, symbol, "binance", 1) if bn_data else None
    hl_oi_change = get_sentinel_oi_change(conn, symbol, "hyperliquid", 1) if hl_data else None

    def _oi_subscore(change):
        if change is None:
            return 0
        ac = abs(change)
        if ac >= 30:
            return 100
        if ac >= 15:
            return 70
        if ac >= 5:
            return 30
        return 0

    bn_score = _oi_subscore(bn_oi_change)
    hl_score = _oi_subscore(hl_oi_change)

    raw_oi = max(bn_score, hl_score)
    components["oi"] = min(25, int(raw_oi / 100 * 25))

    # === 价格维度 (实际满分 17 — v30.14.9 修注释; 之前注释写 24 是设计意图, 但代码档位是 17/10/4) ===
    abs_24h = abs(change_24h)
    if abs_24h >= 15:
        components["price"] = 17
    elif abs_24h >= 8:
        components["price"] = 10
    elif abs_24h >= 3:
        components["price"] = 4

    # === Funding 维度 (🆕 v30.14.7: 5→8 分, 8h 口径统一)
    # 报告指出: BN funding 是 8h 间隔, HL 是 1h 间隔 — 不归一化比较是错的
    # 优先用 BN funding (本身就是 8h 等价), 没 BN 时用 HL × 8 折算
    if bn_data is not None:
        funding_8h_pct = (bn_data.get("funding", 0) or 0) * 100  # BN 已是 8h
    elif hl_data is not None:
        funding_8h_pct = (hl_data.get("funding", 0) or 0) * 100 * 8  # HL 1h × 8
    else:
        funding_8h_pct = 0
    abs_funding = abs(funding_8h_pct)
    bn_funding_pct = funding_8h_pct  # 后续兼容老代码引用此变量名
    if abs_funding < 0.008:
        components["funding"] = 8  # <0.008% 8h = 极干净
    elif abs_funding < 0.02:
        components["funding"] = 5
    elif abs_funding < 0.04:
        components["funding"] = 2
    # ≥0.04% 给 0 分 + 推送阶段会被 filter (见 send_sentinel_alerts)

    # === 量能维度 (🆕 v30.14.7: 相对量能版, 报告指出绝对 vol 跨币种不可比)
    # 由于历史 vol 30d 中位数我们没存 (要新建表), 这版先用相对策略:
    # 大币 (vol>100M) 涨幅大才有意义, 小币 (vol 5-50M) 涨幅小也算放量
    vol_24h = bn_data.get("vol_24h", 0) if bn_data else 0
    if vol_24h > 100_000_000:  # 大币 (BTC/ETH/SOL 级别)
        if abs_24h > 10: components["volume"] = 15
        elif abs_24h > 5: components["volume"] = 10
        elif abs_24h > 3: components["volume"] = 5
    elif vol_24h > 30_000_000:  # 中币
        if abs_24h > 5: components["volume"] = 12
        elif abs_24h > 3: components["volume"] = 7
        elif abs_24h > 1: components["volume"] = 3
    elif vol_24h > 10_000_000:  # 小币
        if abs_24h > 3: components["volume"] = 10
        elif abs_24h > 1: components["volume"] = 5

    # === 🚫 鲸鱼共振 (已删除, 永远 0) ===
    components["whale"] = 0

    # === 共所一致性 (🆕 v30.14.7: 14→15, 改用 min 防双重计分)
    # 旧实现 (BN AND HL OI 都 ≥15%) 实际是 max 的子集, 强相关 → 双重计分
    # 新实现: min(BN, HL) — BN 和 HL 同时强才给分
    components["cross"] = 0
    if bn_oi_change is not None and hl_oi_change is not None:
        # 两所同向必须 (一正一负 = 矛盾, 不算共振)
        same_dir = (bn_oi_change > 0 and hl_oi_change > 0) or \
                   (bn_oi_change < 0 and hl_oi_change < 0)
        if same_dir:
            min_oi = min(abs(bn_oi_change), abs(hl_oi_change))
            if min_oi >= 15:
                components["cross"] = 15  # 两所都 ≥15%
            elif min_oi >= 8:
                components["cross"] = 10  # 两所都 ≥8%
            elif min_oi >= 3:
                components["cross"] = 5  # 两所都 ≥3%

    # 兼容老代码: dex 字段保留 0
    components["dex"] = 0

    # 总分: oi(25) + price(24) + funding(8) + volume(15) + cross(15) = 87 max
    # (其中 price 17 + oi 25 + cross 15 = 57 是核心, 加 vol 15 + funding 8 = 80; 实际峰值 ~80-87)
    score = min(100, sum([components["oi"], components["price"],
                          components["funding"], components["volume"],
                          components["cross"]]))

    # === 🆕 v2 Shadow Pass (方案 C AND 条件, 不影响推送) ===
    # 仅打标签到 SQLite, 用于 1 周后跑 /winrate v2 比对
    # 条件 (全部 AND):
    #   1. OI 1h ≥ 25%
    #   2. 1h 价格涨幅 ≤ 5% (核心: 还没启动) — 调用方传入, 没传时降级用 24h<15
    #   3. |funding 8h| < 0.04% (🆕 v30.14.7: 8h 口径统一)
    #   4. score ≥ 50 (基础质量)
    primary_oi = bn_oi_change if bn_oi_change is not None else hl_oi_change
    
    # 🆕 v30.14.5: 优先用真实 1h 价格, 没有时降级
    if price_1h_pct is not None:
        price_pass = (price_1h_pct <= 5)
    else:
        price_pass = (abs(change_24h) < 15)  # fallback (旧逻辑)
    
    if (primary_oi is not None
            and primary_oi >= 25
            and price_pass
            and abs(bn_funding_pct) < 0.04
            and score >= 50):
        components["v2_pass"] = 1

    # === v30.1: 强信号判定 ===
    # 🆕 v30.12: 综合分 floor ≥50 防 ACE 假信号
    # 🆕 v30.13: 24h ≤ SENTINEL_MAX_CHANGE_24H, 抓"还没启动的"
    direct_strong_signal = False
    if (bn_data is not None and bn_oi_change is not None
            and bn_oi_change >= SENTINEL_DIRECT_OI_PCT
            and change_24h > -10
            and change_24h <= SENTINEL_MAX_CHANGE_24H
            and score >= SENTINEL_DIRECT_MIN_SCORE):
        direct_strong_signal = True

    return score, components, direction, direct_strong_signal


def classify_sentinel_stage(change_24h, oi_change_1h, score):
    if change_24h > 50:
        return "过热"
    if change_24h > 30:
        return "启动末段"
    if change_24h > 10:
        return "启动"
    if change_24h > 3 and oi_change_1h is not None and oi_change_1h > 10:
        return "启动初段"
    if oi_change_1h is not None and oi_change_1h > 10 and abs(change_24h) < 5:
        return "蓄势"
    if change_24h < -20:
        return "退役"
    if -10 < change_24h < 0 and score >= 50:
        return "等待回踩"
    return "观察"


# ============================================================
# v30: Claude Haiku AI 判断
# ============================================================
def generate_sentinel_judgment(symbol, score, stage, components, change_24h, whale_count, channel):
    if not ANTHROPIC_API_KEY:
        return ""
    try:
        channel_hint = "BN OI 直推强信号" if channel == "direct" else "综合分多维度共振"
        prompt = (
            f"你是加密货币合约信号分析师, 用 2-3 句简短中文输出判断, 风格直接、有节奏感, 像 KOL 不像研报。\n\n"
            f"币种: ${symbol}\n"
            f"触发通道: {channel_hint}\n"
            f"综合分: {score}/100\n"
            f"阶段: {stage}\n"
            f"24h 涨跌: {change_24h:+.1f}%\n"
            f"分项: OI {components['oi']}/25, 价格 {components['price']}/20, "
            f"Funding {components['funding']}/15, 量能 {components['volume']}/15, 鲸鱼 {components['whale']}/15\n"
            f"鲸鱼共振: {'有' if whale_count > 0 else '无'}\n\n"
            f"要求: 2-3 句话不超过 100 字 / 不写'建议'/不写'做多/做空'指令 / 只写客观状态 + 节奏判断 / 不要引号"
        )
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 200,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=20
        )
        if r.status_code == 200:
            data = r.json()
            content = data.get("content", [])
            if content and content[0].get("type") == "text":
                return content[0].get("text", "").strip()
        else:
            print(f"[Sentinel/AI] HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[Sentinel/AI] ❌ {e}")
    return ""


# ============================================================
# v30.1: 主扫描 (含双通道推送)
# ============================================================
def check_sentinel_signals(conn):
    init_sentinel_db(conn)
    alerts = []

    bn_data = fetch_binance_perp_data()
    hl_data = fetch_hyperliquid_perp_data_for_sentinel()

    for sym, d in bn_data.items():
        if d["oi_usd"] > 0:
            store_sentinel_oi_snapshot(conn, sym, "binance", d["oi_usd"])
    for sym, d in hl_data.items():
        store_sentinel_oi_snapshot(conn, sym, "hyperliquid", d["oi_usd"])
    conn.commit()

    candidates = set(bn_data.keys()) | set(hl_data.keys())
    print(f"[Sentinel] 候选 {len(candidates)} 币 (BN: {len(bn_data)}, HL: {len(hl_data)})")

    scored = []
    for sym in candidates:
        bn_d = bn_data.get(sym)
        hl_d = hl_data.get(sym)

        whale_count = 0
        try:
            whales_on = _find_active_whales_on_coin(conn, sym, min_size_usd=300_000)
            whale_count = len(whales_on)
        except Exception:
            pass

        score, components, direction, direct_strong = compute_sentinel_score(
            sym, bn_d, hl_d, conn, whale_count
        )

        if score < 30 and not direct_strong:
            continue

        oi_change_1h = (
            get_sentinel_oi_change(conn, sym, "binance", 1) or
            get_sentinel_oi_change(conn, sym, "hyperliquid", 1) or 0
        )
        change_24h = bn_d.get("change_24h", 0) if bn_d else 0
        stage = classify_sentinel_stage(change_24h, oi_change_1h, score)

        scored.append({
            "symbol": sym,
            "score": score,
            "stage": stage,
            "direction": direction,
            "components": components,
            "bn_data": bn_d,
            "hl_data": hl_d,
            "whale_count": whale_count,
            "change_24h": change_24h,
            "oi_change_1h": oi_change_1h,
            "direct_strong": direct_strong,
        })

    # 排序: 强信号优先, 同级按分数
    scored.sort(key=lambda x: (1 if x["direct_strong"] else 0, x["score"]), reverse=True)

    n_direct = sum(1 for s in scored if s["direct_strong"])
    print(f"[Sentinel] 评分 30+: {len(scored)}, 50+: {sum(1 for s in scored if s['score']>=50)}, "
          f"60+: {sum(1 for s in scored if s['score']>=60)}, 75+: {sum(1 for s in scored if s['score']>=75)}, "
          f"💢 直推强信号: {n_direct}")

    # 🆕 v30.14.5: 第二轮 — 拉 1h 价格 (仅 score≥45 候选, 控制 API 调用量)
    # 用于刷新 v2_pass 标签 (用真实 1h 价格代替 24h fallback)
    refresh_targets = [s for s in scored if s["score"] >= 45]
    if refresh_targets:
        print(f"[Sentinel/v2] 拉 1h 价格 ({len(refresh_targets)} 个 score≥45 候选)...")
        with ThreadPoolExecutor(max_workers=10) as ex:
            futs = {ex.submit(fetch_price_change_1h, s["symbol"]): s for s in refresh_targets}
            v2_pass_count = 0
            for fut in as_completed(futs, timeout=20):
                s = futs[fut]
                try:
                    p1h = fut.result()
                    if p1h is None:
                        continue
                    # 重算 v2_pass (其他维度不变, 只刷 v2_pass)
                    new_score, new_comp, _, _ = compute_sentinel_score(
                        s["symbol"], s["bn_data"], s["hl_data"], conn, s["whale_count"],
                        price_1h_pct=p1h
                    )
                    s["components"]["v2_pass"] = new_comp.get("v2_pass", 0)
                    s["price_1h_pct"] = p1h  # 存起来用于推送展示
                    if new_comp.get("v2_pass", 0) == 1:
                        v2_pass_count += 1
                except Exception:
                    pass
            print(f"[Sentinel/v2] ✅ v2_pass={v2_pass_count} / refresh={len(refresh_targets)}")

    signal_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    for s in scored:
        # 通道判定
        # 🆕 v30.13: score 通道也加 24h ≤5% 过滤 (统一早期信号策略)
        ch24 = s.get("change_24h", 0) or 0
        
        # 🆕 v30.14.7: Funding 8h 口径统一 + 强制过滤
        # BN funding 是 8h 间隔, HL 是 1h × 8 折算
        # |f8h| ≥ 0.04% 不让进 direct/score 通道 (报告推荐 8h 口径阈值)
        bn_d = s.get("bn_data") or {}
        hl_d = s.get("hl_data") or {}
        if bn_d:
            funding_8h_pct = (bn_d.get("funding", 0) or 0) * 100
        elif hl_d:
            funding_8h_pct = (hl_d.get("funding", 0) or 0) * 100 * 8
        else:
            funding_8h_pct = 0
        funding_pct_abs = abs(funding_8h_pct)
        funding_clean = funding_pct_abs < 0.04
        
        if s["direct_strong"] and funding_clean:
            channel = "direct"
        elif s["score"] >= SENTINEL_PUSH_THRESHOLD and ch24 <= SENTINEL_MAX_CHANGE_24H and funding_clean:
            channel = "score"
        else:
            channel = "watch"
            # 标记被 funding 过滤掉的强信号 (debug 用)
            if (s["direct_strong"] or s["score"] >= 50) and not funding_clean:
                print(f"[Sentinel/funding-filter] ${s['symbol']} score={s['score']} funding_8h={funding_pct_abs:.3f}% → watch")

        # 🆕 v30.14.25: 基于 5/18 /diagnose 30 (n=500) 数据加 4 条避雷过滤
        # 数据来源: 双数据源交叉验证 (/diagnose + /winrate 30 score)
        if channel in ("direct", "score"):
            diagnose_skip = None
            # 避雷 1: score >= 66 → 顶部 FOMO (赢率仅 6%)
            if s["score"] >= 66:
                diagnose_skip = f"score≥66 ({s['score']}, 高分 FOMO 陷阱)"
            # 避雷 2: cross 共所一致性 >= 10 → 末日信号 (赢率 0%)
            elif s.get("components", {}).get("cross", 0) >= 10:
                diagnose_skip = f"cross≥10 ({s['components'].get('cross')}, 双所确认是末日)"
            # 避雷 3: funding 8h >= 0.04% → 极端拥挤 (赢率 19%, 加强现有过滤)
            elif funding_pct_abs >= 0.04:
                diagnose_skip = f"funding≥0.04% ({funding_pct_abs:.3f}%, 多头拥挤)"
            # 避雷 4: 24h 涨幅 5-10% → 接力盘 (赢率 12%)
            elif 5 <= ch24 <= 10:
                diagnose_skip = f"24h 5-10% ({ch24:.1f}%, 接力盘重灾)"

            if diagnose_skip:
                channel = "watch"
                print(f"[Sentinel/diagnose-filter] ${s['symbol']} score={s['score']} → watch ({diagnose_skip})")

        # 🆕 v30.14.25: 新通道 "rebound" (超跌反弹) — 基于 /diagnose 24h≤-5% 赢率 76%
        # 触发条件: 24h ≤ -5% + OI 1h ≥ 30% (有人在抄底, 不是死币)
        # 注意: 跟 SHORT 通道反向 (SHORT 抓 24h>10%, rebound 抓 24h<-5%)
        if (channel == "watch"
                and s["score"] >= 50  # 基础过滤
                and ch24 <= -5
                and s.get("oi_change_1h") is not None
                and s["oi_change_1h"] >= 30
                and funding_clean):
            channel = "rebound"
            print(f"[Sentinel/rebound] ${s['symbol']} score={s['score']} 24h={ch24:.1f}% OI1h={s['oi_change_1h']:.1f}% → rebound 候选")

        # 🆕 v30.14.20: SHORT 信号默认进频道 (基于 5/15 dogfood n=46 数据)
        # 历史数据: 1h 胜率 72% / 4h 胜率 67% / 4h 均 +3.30% / 反向 ≥+3% 仅 19%
        # 严守: 文案明确 4h 出场 / +3% 止损 / 严禁过夜 (24h 反向止损位 48%)
        # env SENTINEL_SHORT_DOGFOOD=1 可回退 admin 私聊 dogfood 模式
        # 🆕 v30.14.27 A: funding 0.02-0.04% 段是 SHORT 反向区 (赢率 29%, n=21)
        # 数据依据: 5/22 /diagnose 30 short
        # 仅 0-0.02% (未到顶) 和 ≥0.04% (极度拥挤必爆) 是 SHORT 甜区
        funding_short_skip = 0.02 <= funding_pct_abs < 0.04
        if (funding_short_skip and s["score"] >= 60
                and s.get("oi_change_1h") is not None and s["oi_change_1h"] >= 30
                and ch24 > 10):
            print(f"[SHORT/funding-skip] ${s['symbol']} score={s['score']} funding={funding_pct_abs:.3f}% (反向区, 跳过 SHORT)")
        if (TG_ADMIN_CHAT_ID
                and s["score"] >= 60
                and s.get("oi_change_1h") is not None
                and s["oi_change_1h"] >= 30
                and ch24 > 10
                and not funding_short_skip):
            short_key = f"short-dog-{s['symbol']}"
            if not is_alerted(conn, "short_dog", short_key, hours=4):
                try:
                    bn_d = s.get("bn_data") or {}
                    hl_d = s.get("hl_data") or {}
                    cur_price = (bn_d.get("price") or hl_d.get("price") or 0)

                    if SENTINEL_SHORT_DOGFOOD:
                        # dogfood 模式: 仅私聊 admin
                        short_msg = (
                            f"💀 <b>SHORT 候选 (dogfood)</b>\n\n"
                            f"🪙 ${s['symbol']}\n"
                            f"📊 综合分: {s['score']}/100\n"
                            f"💹 24h: {ch24:+.1f}% (FOMO 顶部)\n"
                            f"📦 OI 1h: {s['oi_change_1h']:+.1f}%\n"
                            f"💰 现价: ${cur_price:.6f}\n\n"
                            f"<i>历史: 此类信号 4h 内 94% 回吐 ≥-3%, close 胜率 23%</i>\n"
                            f"<i>建议: 进场做空, 持仓 1-4h, 1h 后看复盘</i>\n\n"
                            f"<i>⚠️ dogfood 阶段, 仅私聊 admin, 未进频道</i>"
                        )
                        requests.post(
                            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                            json={
                                "chat_id": TG_ADMIN_CHAT_ID,
                                "text": short_msg,
                                "parse_mode": "HTML",
                                "disable_web_page_preview": True,
                            },
                            timeout=10,
                        )
                        mark_alerted(conn, "short_dog", short_key)
                        # 入队 1h 反查 (复用 sentinel_fomo_followup 表, channel='short_dog')
                        enqueue_fomo_followup(
                            conn, s["symbol"], s["score"], "short_dog",
                            cur_price, signal_time
                        )
                        print(f"[SHORT/dogfood] ✅ 私推 admin: ${s['symbol']} score={s['score']} 24h={ch24:+.1f}%")
                    else:
                        # 🆕 v30.14.20: 正式进频道
                        # 强约束: 仅 4h 时间窗, +3% 止损, 严禁过夜

                        # 🆕 v30.14.27 B: SHORT VIP 检测 (基于 5/22 /diagnose 30 short n=104)
                        # 任一甜区维度命中即标记 VIP (历史赢率 62-79%)
                        is_vip = False
                        vip_reasons = []
                        cross_score = s.get("components", {}).get("cross", 0)
                        oi_subscore = s.get("components", {}).get("oi", 0)
                        if cross_score >= 10:
                            is_vip = True
                            vip_reasons.append(f"cross={cross_score} (历史 76%)")
                        if funding_pct_abs >= 0.04:
                            is_vip = True
                            vip_reasons.append(f"funding={funding_pct_abs:.3f}% (历史 79%)")
                        if oi_subscore >= 18:
                            is_vip = True
                            vip_reasons.append(f"OI={oi_subscore}/25 (历史 62%)")
                        vip_tag = "⭐⭐ <b>VIP 高确定性</b>\n" if is_vip else ""
                        vip_detail = (f"<i>💎 VIP 因子: {' · '.join(vip_reasons)}</i>\n" if is_vip else "")

                        short_msg = (
                            f"{vip_tag}🔻 <b>FOMO 顶部空头信号</b>\n\n"
                            f"🪙 ${s['symbol']}\n"
                            f"📊 综合分: {s['score']}/100\n"
                            f"💹 24h 涨幅: {ch24:+.1f}% (顶部 FOMO)\n"
                            f"📦 OI 1h: {s['oi_change_1h']:+.1f}%\n"
                            f"💰 现价: ${cur_price:.6f}\n\n"
                            f"{vip_detail}"
                            f"<i>🔻 做空 · <b>4h 内出场</b> · 严禁过夜</i>\n"
                            f"<i>🎯 止盈 -3% · 🚨 反向止损 +3%</i>\n"
                            f"<i>📊 历史 4h 胜率 67%, 均 +3.30% (n=46)</i>\n"
                            f"<i>⚠️ 24h 持仓胜率仅 50%, 均亏 -8.94%, 严守时间</i>\n\n"
                            f"<i>📲 开户: <code>{HL_REFERRAL}</code></i>\n"
                            f"<i>⚠️ 信号仅供研究, 不构成建议. 合约高风险, 自负盈亏.</i>"
                        )
                        if is_vip:
                            print(f"[SHORT/VIP] ⭐⭐ ${s['symbol']} score={s['score']} VIP={vip_reasons}")
                        # tail 标签
                        try:
                            tail = tail_for_alert(
                                "short", s["symbol"],
                                v=int(s["score"]), r=int(ch24),
                                src="fomo_top",
                                extra={"score": s["score"], "oi1h": s.get("oi_change_1h"), "ch24": ch24}
                            )
                            short_msg += f"\n{tail}"
                        except Exception:
                            pass
                        send_tg(short_msg)
                        mark_alerted(conn, "short_dog", short_key)

                        # 🆕 v30.14.20: 入队 signal_tracker (SHORT 模式)
                        # 注意: tracker 侧需识别 SHORT 反向止盈/止损 (-3% 止盈, +3% 止损)
                        # 🆕 v30.14.29: VIP 信号入 'short_vip' channel (用于 daily briefing 识别)
                        tracker_channel = "short_vip" if is_vip else "short"
                        try:
                            enqueue_signal_tracker(conn, s["symbol"], s["score"], tracker_channel,
                                                   cur_price, signal_time)
                        except Exception as e:
                            print(f"[SHORT/Tracker] {s['symbol']}: {e}")

                        # 🆕 v30.14.30: 同步入纸上仓位 (SHORT 方向)
                        if cur_price and cur_price > 0:
                            try:
                                enqueue_paper_position(conn, s["symbol"], tracker_channel,
                                                       "short", cur_price, signal_time)
                            except Exception as e:
                                print(f"[Paper/SHORT] {s['symbol']}: {e}")

                        # 同步发 Binance Square
                        try:
                            sq_text = (
                                f"🔻 FOMO 顶部空头 · ${s['symbol']}\n\n"
                                f"24h 涨幅 {ch24:+.1f}% 顶部, OI 1h {s['oi_change_1h']:+.1f}%\n"
                                f"综合分 {s['score']}/100, 现价 ${cur_price:.6f}\n\n"
                                f"做空 · 4h 内出场 · 严禁过夜\n"
                                f"止盈 -3% · 反向止损 +3%\n"
                                f"历史 4h 胜率 67% / 均 +3.30%\n\n"
                                f"@币世赏金台 · 赏金哨\n"
                                f"⚠️ 仅供研究, 不构成建议. 合约高风险.\n\n"
                                f"#{s['symbol']} #做空 #FOMO顶部 #合约信号"
                            )
                            publish_to_binance_square(sq_text, symbol=s["symbol"], score=s["score"], conn=conn)
                        except Exception as e:
                            print(f"[SHORT/Square] {s['symbol']}: {e}")

                        print(f"[SHORT] ✅ 推频道: ${s['symbol']} score={s['score']} 24h={ch24:+.1f}% OI1h={s['oi_change_1h']:+.1f}%")
                except Exception as e:
                    print(f"[SHORT] {s['symbol']}: {e}")

        # 🆕 v30.14.25: rebound 通道推送 (超跌反弹候选)
        if channel == "rebound":
            rebound_key = f"rebound-{s['symbol']}"
            if not is_alerted(conn, "rebound", rebound_key, hours=4):
                try:
                    bn_d = s.get("bn_data") or {}
                    hl_d = s.get("hl_data") or {}
                    cur_price = (bn_d.get("price") or hl_d.get("price") or 0)
                    rebound_msg = (
                        f"🔄 <b>超跌反弹候选</b>\n\n"
                        f"🪙 ${s['symbol']}\n"
                        f"📊 综合分: {s['score']}/100\n"
                        f"📉 24h: <b>{ch24:+.1f}%</b> (超跌区)\n"
                        f"📦 OI 1h: <b>{s['oi_change_1h']:+.1f}%</b> (有人抄底)\n"
                        f"💰 现价: ${cur_price:.6g}\n\n"
                        f"<i>🔄 做多 · 1h 内出场 · 反弹机会</i>\n"
                        f"<i>🎯 止盈 +5% · 🚨 止损 -3%</i>\n"
                        f"<i>📊 历史 24h≤-5% 段赢率 76% (n=58)</i>\n"
                        f"<i>⚠️ 跌势中接刀子有风险, 不破前低才进</i>\n\n"
                        f"<i>📲 开户: <code>{HL_REFERRAL}</code></i>\n"
                        f"<i>⚠️ 信号仅供研究, 不构成建议. 合约高风险.</i>"
                    )
                    try:
                        tail = tail_for_alert(
                            "rebound", s["symbol"],
                            v=int(s["score"]), r=int(ch24),
                            src="oversold_rebound",
                            extra={"score": s["score"], "oi1h": s.get("oi_change_1h"), "ch24": ch24}
                        )
                        rebound_msg += f"\n{tail}"
                    except Exception:
                        pass
                    send_tg(rebound_msg)
                    mark_alerted(conn, "rebound", rebound_key)
                    # 入 signal_tracker LONG 模式 (复用现有止盈止损逻辑)
                    try:
                        enqueue_signal_tracker(conn, s["symbol"], s["score"], "score",
                                               cur_price, signal_time)
                    except Exception as e:
                        print(f"[Rebound/Tracker] {s['symbol']}: {e}")

                    # 🆕 v30.14.30: 同步入纸上仓位 (rebound = LONG 方向)
                    if cur_price and cur_price > 0:
                        try:
                            enqueue_paper_position(conn, s["symbol"], "rebound",
                                                   "long", cur_price, signal_time)
                        except Exception as e:
                            print(f"[Paper/rebound] {s['symbol']}: {e}")
                    # 同步发 Binance Square
                    try:
                        sq_text = (
                            f"🔄 超跌反弹候选 · ${s['symbol']}\n\n"
                            f"24h {ch24:+.1f}% 超跌, OI 1h {s['oi_change_1h']:+.1f}% (抄底信号)\n"
                            f"综合分 {s['score']}/100, 现价 ${cur_price:.6g}\n\n"
                            f"做多 · 1h 内出场 · 反弹机会\n"
                            f"止盈 +5% · 止损 -3%\n"
                            f"历史超跌段赢率 76%\n\n"
                            f"@币世赏金台 · 赏金哨\n"
                            f"⚠️ 仅供研究, 不构成建议. 合约高风险.\n\n"
                            f"#{s['symbol']} #超跌反弹 #抄底 #合约信号"
                        )
                        publish_to_binance_square(sq_text, symbol=s["symbol"], score=s["score"], conn=conn)
                    except Exception as e:
                        print(f"[Rebound/Square] {s['symbol']}: {e}")
                    print(f"[Rebound] ✅ 推频道: ${s['symbol']} score={s['score']} 24h={ch24:+.1f}%")
                except Exception as e:
                    print(f"[Rebound] {s['symbol']}: {e}")

        # 全量入库 (复盘核心)
        try:
            conn.execute(
                """INSERT INTO sentinel_signals
                (symbol, venue, score, stage, direction, price,
                 oi_usd_binance, oi_usd_hyperliquid, funding_binance, funding_hyperliquid,
                 change_24h, vol_24h_usd, score_components, whale_resonance,
                 push_channel, signal_time, recorded_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))""",
                (
                    s["symbol"],
                    "both" if (s["bn_data"] and s["hl_data"]) else ("binance" if s["bn_data"] else "hyperliquid"),
                    s["score"], s["stage"], s["direction"],
                    (s["bn_data"] or s["hl_data"]).get("price", 0),
                    s["bn_data"].get("oi_usd", 0) if s["bn_data"] else 0,
                    s["hl_data"].get("oi_usd", 0) if s["hl_data"] else 0,
                    s["bn_data"].get("funding", 0) if s["bn_data"] else 0,
                    s["hl_data"].get("funding", 0) if s["hl_data"] else 0,
                    s["change_24h"],
                    s["bn_data"].get("vol_24h", 0) if s["bn_data"] else 0,
                    json.dumps(s["components"]),
                    1 if s["whale_count"] > 0 else 0,
                    channel,
                    signal_time,
                )
            )
        except Exception as e:
            print(f"[Sentinel/DB] {s['symbol']}: {e}")
            continue

        if channel == "watch":
            continue

        alert_key = f"sentinel-{s['symbol']}"
        if is_alerted(conn, "sentinel", alert_key, hours=SENTINEL_COOLDOWN_HOURS):
            continue

        # 🆕 v30.2 (D): 让位给价格异动卡片图
        # 同币 4h 内若价格异动模块已推过 (有图), 赏金哨跳过, 避免文字与图重复
        # 蓄势/启动初段 (OI 先动价格未飞) 价格异动不会触发, 赏金哨独享
        try:
            for d_dir in ("up", "down"):
                if is_alerted(conn, "price_surge", f"price-{s['symbol']}-{d_dir}", hours=4):
                    raise StopIteration
        except StopIteration:
            print(f"[Sentinel] {s['symbol']} 让位价格异动卡片图 (4h 内已推)")
            continue

        mark_alerted(conn, "sentinel", alert_key)

        s["channel"] = channel
        s["signal_time"] = signal_time
        alerts.append(s)

    conn.commit()
    return alerts


# ============================================================
# v30.1: 推送 (区分双通道)
# ============================================================

# ============================================================
# v30.3: 赏金哨雷达图 (综合分 ≥ 75 触发, 失败静默降级)
# ============================================================
SENTINEL_RADAR_THRESHOLD = _env_int("SENTINEL_RADAR_THRESHOLD", "75")


def render_sentinel_radar(symbol, score, stage, components, change_24h, oi_change_1h, channel='direct'):
    """六维雷达图 (黑底荧光风, Telegram 推送用). 失败返回 None"""
    if not HAS_MATPLOTLIB:
        return None
    try:
        import numpy as np
        import matplotlib.patheffects as pe

        max_vals = {'oi': 25, 'price': 20, 'funding': 15, 'volume': 15, 'whale': 15, 'dex': 10}
        keys = ['oi', 'price', 'funding', 'volume', 'whale', 'dex']
        labels = ['OI 异动', '价格', '资金费率', '量能', '鲸鱼', 'DEX']

        values = [components[k] / max_vals[k] for k in keys]
        raw_values = [components[k] for k in keys]

        # 配色
        BG_DARK    = '#0a0e1a'
        BG_PANEL   = '#0f1525'
        GRID_LINE  = '#1e293b'
        TEXT_LIGHT = '#e2e8f0'
        TEXT_DIM   = '#64748b'
        TEXT_FAINT = '#334155'

        if channel == 'direct':
            neon_color = '#ff2d55'
            neon_glow  = '#ff5577'
            banner_color = '#ff2d55'
            banner_text = '◤  BN OI 直推强信号'
        else:
            neon_color = '#a855f7'
            neon_glow  = '#c084fc'
            banner_color = '#a855f7'
            banner_text = '◆  综合多维信号'

        # 中文字体
        font_path = ensure_chinese_font()
        cn_font = None
        if font_path:
            try:
                font_manager.fontManager.addfont(font_path)
                cn_font = font_manager.FontProperties(fname=font_path)
            except Exception:
                pass

        def _f(weight='normal', size=11):
            kw = {'fontsize': size, 'weight': weight}
            if cn_font:
                kw['fontproperties'] = cn_font
            return kw

        fig = plt.figure(figsize=(8, 10), dpi=150, facecolor=BG_DARK)

        # Top banner
        top_bar = fig.add_axes([0, 0.94, 1, 0.06])
        top_bar.set_facecolor(banner_color)
        top_bar.set_xticks([]); top_bar.set_yticks([])
        for s in top_bar.spines.values(): s.set_visible(False)
        top_bar.text(0.5, 0.5, banner_text, ha='center', va='center', color='white',
                     transform=top_bar.transAxes,
                     path_effects=[pe.withStroke(linewidth=4, foreground=banner_color, alpha=0.6)],
                     **_f(weight='bold', size=15))

        # Info panel
        info_ax = fig.add_axes([0, 0.82, 1, 0.11])
        info_ax.set_facecolor(BG_PANEL)
        info_ax.set_xticks([]); info_ax.set_yticks([])
        for s in info_ax.spines.values():
            s.set_color(GRID_LINE); s.set_linewidth(1)

        info_ax.text(0.05, 0.62, f'${symbol}', color=TEXT_LIGHT, transform=info_ax.transAxes,
                     va='center', ha='left',
                     path_effects=[pe.withStroke(linewidth=8, foreground=neon_color, alpha=0.25)],
                     **_f(weight='bold', size=22))
        info_ax.text(0.05, 0.22, stage, color=TEXT_DIM, transform=info_ax.transAxes,
                     va='center', ha='left', **_f(size=11))

        if score >= 75: score_color = '#ff2d55'
        elif score >= 60: score_color = '#ff9500'
        elif score >= 50: score_color = '#a855f7'
        else: score_color = TEXT_DIM
        info_ax.text(0.40, 0.62, f'{score}', color=score_color, transform=info_ax.transAxes,
                     va='center', ha='center',
                     path_effects=[pe.withStroke(linewidth=10, foreground=score_color, alpha=0.4)],
                     **_f(weight='bold', size=28))
        info_ax.text(0.40, 0.22, '综合分 / 100', color=TEXT_DIM, transform=info_ax.transAxes,
                     va='center', ha='center', **_f(size=10))

        ch_color = '#10b981' if change_24h > 0 else '#ef4444'
        info_ax.text(0.65, 0.62, f'{change_24h:+.1f}%', color=ch_color, transform=info_ax.transAxes,
                     va='center', ha='center',
                     path_effects=[pe.withStroke(linewidth=8, foreground=ch_color, alpha=0.35)],
                     **_f(weight='bold', size=17))
        info_ax.text(0.65, 0.22, '24h', color=TEXT_DIM, transform=info_ax.transAxes,
                     va='center', ha='center', **_f(size=10))

        oi_color = '#ff2d55' if oi_change_1h > 0 else TEXT_DIM
        info_ax.text(0.88, 0.62, f'{oi_change_1h:+.1f}%', color=oi_color, transform=info_ax.transAxes,
                     va='center', ha='center',
                     path_effects=[pe.withStroke(linewidth=8, foreground=oi_color, alpha=0.35)],
                     **_f(weight='bold', size=17))
        info_ax.text(0.88, 0.22, 'OI 1h', color=TEXT_DIM, transform=info_ax.transAxes,
                     va='center', ha='center', **_f(size=10))

        # Radar
        radar_ax = fig.add_axes([0.20, 0.13, 0.60, 0.65], polar=True)
        radar_ax.set_facecolor(BG_DARK)
        radar_ax.set_theta_offset(np.pi / 2)
        radar_ax.set_theta_direction(-1)

        angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
        angles_closed = angles + angles[:1]
        values_closed = values + values[:1]

        radar_ax.set_ylim(0, 1.0)
        radar_ax.set_yticks([0.25, 0.5, 0.75, 1.0])
        radar_ax.set_yticklabels([])
        radar_ax.set_xticks(angles)
        radar_ax.set_xticklabels([])
        radar_ax.spines['polar'].set_color(GRID_LINE)
        radar_ax.spines['polar'].set_linewidth(1.2)
        radar_ax.grid(True, color=GRID_LINE, linewidth=0.8)

        # Glow halo
        for w in [10, 6, 3]:
            radar_ax.plot(angles_closed, values_closed, color=neon_glow,
                          linewidth=w, alpha=0.15, zorder=2)

        radar_ax.fill(angles_closed, values_closed, color=neon_color, alpha=0.22, zorder=3)
        radar_ax.plot(angles_closed, values_closed, color=neon_color, linewidth=2.5, zorder=4,
                      path_effects=[pe.withStroke(linewidth=6, foreground=neon_color, alpha=0.5)])

        # Dots
        for ang, val, raw, mx in zip(angles, values, raw_values, [max_vals[k] for k in keys]):
            if raw == 0:
                radar_ax.scatter(ang, val, s=50, color=BG_DARK, zorder=5,
                                 edgecolors=neon_color, linewidths=1.5, alpha=0.7)
            elif raw == mx:
                for sz in [220, 160]:
                    radar_ax.scatter(ang, val, s=sz, color=neon_color, zorder=6,
                                     alpha=0.3 if sz == 220 else 1.0)
                radar_ax.scatter(ang, val, s=80, color='white', zorder=7,
                                 edgecolors=neon_color, linewidths=2)
            else:
                radar_ax.scatter(ang, val, s=120, color=neon_color, zorder=6, alpha=0.4)
                radar_ax.scatter(ang, val, s=70, color=neon_color, zorder=7,
                                 edgecolors='white', linewidths=1.5)

        # Axis labels
        for ang, label, raw, mx in zip(angles, labels, raw_values, [max_vals[k] for k in keys]):
            xx = np.cos(np.pi/2 - ang); yy = np.sin(np.pi/2 - ang)
            ha = 'center' if abs(xx) < 0.15 else ('left' if xx > 0 else 'right')
            va = 'center' if abs(yy) < 0.15 else ('bottom' if yy > 0 else 'top')

            is_max = (raw == mx); is_zero = (raw == 0)
            if is_max:
                lbl_color = neon_color; sc_color = neon_color; w = 'bold'
            elif is_zero:
                lbl_color = TEXT_FAINT; sc_color = TEXT_FAINT; w = 'normal'
            else:
                lbl_color = TEXT_LIGHT; sc_color = TEXT_DIM; w = 'bold'

            is_vertical = (abs(yy) > abs(xx))
            if is_vertical:
                if yy > 0:
                    radar_ax.text(ang, 1.18, label, ha=ha, va='bottom', color=lbl_color, **_f(weight=w, size=12))
                    radar_ax.text(ang, 1.28, f'{raw}/{mx}', ha=ha, va='bottom', color=sc_color,
                                  **_f(weight='bold' if is_max else 'normal', size=10))
                else:
                    radar_ax.text(ang, 1.18, label, ha=ha, va='top', color=lbl_color, **_f(weight=w, size=12))
                    radar_ax.text(ang, 1.28, f'{raw}/{mx}', ha=ha, va='top', color=sc_color,
                                  **_f(weight='bold' if is_max else 'normal', size=10))
            else:
                radar_ax.text(ang, 1.16, label, ha=ha, va=va, color=lbl_color, **_f(weight=w, size=12))
                radar_ax.text(ang, 1.28, f'{raw}/{mx}', ha=ha, va=va, color=sc_color,
                              **_f(weight='bold' if is_max else 'normal', size=10))

        # Footer
        footer_ax = fig.add_axes([0, 0, 1, 0.05])
        footer_ax.set_facecolor(BG_PANEL)
        footer_ax.set_xticks([]); footer_ax.set_yticks([])
        for s in footer_ax.spines.values(): s.set_visible(False)
        footer_ax.text(0.04, 0.5, '@币世赏金台 · 赏金哨', color=TEXT_LIGHT,
                       transform=footer_ax.transAxes, va='center',
                       path_effects=[pe.withStroke(linewidth=4, foreground=neon_color, alpha=0.3)],
                       **_f(weight='bold', size=11))
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M UTC')
        footer_ax.text(0.96, 0.5, now_str, color=TEXT_DIM, transform=footer_ax.transAxes,
                       va='center', ha='right', **_f(size=10))

        # Center watermark
        fig.text(0.5, 0.45, '@币世赏金台',
                 color=TEXT_LIGHT, alpha=0.04, ha='center', va='center',
                 **_f(weight='bold', size=44))

        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor=BG_DARK)
        buf.seek(0)
        plt.close(fig)
        return buf.getvalue()
    except Exception as e:
        print(f"[Sentinel/Radar] ❌ {symbol}: {e}")
        try:
            plt.close('all')
        except Exception:
            pass
        return None


def send_sentinel_alerts(alerts, conn):
    if not alerts:
        return

    # 🆕 v30.13.6: Score 通道转 admin dogfood (不进频道)
    # 数据依据: /winrate 7 score 显示 100 样本三窗口 alpha 全负 (1h -11%, 4h -5%, 24h -3%)
    # 推送比未推还差 → 反向指标. 转 dogfood 私聊 admin 观察 2 周, 不再误导用户.
    # 🆕 v30.14.15: 默认从 1 → 0, score 恢复到频道
    # 数据依据: /winrate 7 (5/11) 显示 dogfood 期间 score 24h close 胜率 56% / 均收益 +4.19% / Alpha +11%
    # 关闭方法: SCORE_CHANNEL_DOGFOOD=1 → 恢复 admin dogfood (不进频道)
    score_to_dogfood = os.getenv("SCORE_CHANNEL_DOGFOOD", "0") == "1"
    if score_to_dogfood and TG_ADMIN_CHAT_ID:
        score_alerts = [s for s in alerts if s.get("channel") == "score"]
        for s in score_alerts:
            try:
                bn_d = s.get("bn_data") or {}
                hl_d = s.get("hl_data") or {}
                cur_price = (bn_d.get("price") or hl_d.get("price") or 0)
                ch24 = s.get("change_24h", 0) or 0
                oi1h = s.get("oi_change_1h") or 0
                comp = s.get("components", {})
                msg = (
                    f"📊 <b>Score 候选 (dogfood)</b>\n\n"
                    f"🪙 ${s['symbol']}\n"
                    f"📊 综合分: {s['score']}/100\n"
                    f"💹 24h: {ch24:+.1f}% · OI 1h: {oi1h:+.1f}%\n"
                    f"💰 现价: ${cur_price:.6f}\n"
                    f"分项: OI {comp.get('oi',0)}/25 · 价格 {comp.get('price',0)}/20 · "
                    f"Funding {comp.get('funding',0)}/15 · 量能 {comp.get('volume',0)}/15\n\n"
                    f"<i>历史 alpha: 1h -11% / 4h -5% / 24h -3% (反向)</i>\n"
                    f"<i>⚠️ Score dogfood, 仅私聊 admin, 未进频道</i>"
                )
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                    json={"chat_id": TG_ADMIN_CHAT_ID, "text": msg,
                          "parse_mode": "HTML", "disable_web_page_preview": True},
                    timeout=10,
                )
                print(f"[Score/dogfood] ✅ 私推 admin: ${s['symbol']} score={s['score']}")
            except Exception as e:
                print(f"[Score/dogfood] {s['symbol']}: {e}")
        # 从 alerts 中移除 score 信号 (不进频道)
        alerts = [s for s in alerts if s.get("channel") != "score"]

    if not alerts:
        return

    for s in alerts[:10]:
        sym = s["symbol"]
        score = s["score"]
        stage = s["stage"]
        comp = s["components"]
        channel = s.get("channel", "score")

        # 标题区分
        if channel == "direct":
            title = "💢 <b>赏金哨</b> · BN OI 直推"
            grade_line = "🟦 Binance · OI 强信号"
        else:
            title = "🎯 <b>赏金哨</b> · 综合信号"
            if score >= 85:
                grade = "🔴 极强"
            elif score >= 75:
                grade = "🟠 强"
            elif score >= 60:
                grade = "🟡 中强"
            else:
                grade = "🟢 观察"
            if s["bn_data"] and s["hl_data"]:
                venue_tag = "🟦 BN + 🔶 HL · 双所共振"
            elif s["bn_data"]:
                venue_tag = "🟦 Binance"
            else:
                venue_tag = "🔶 Hyperliquid"
            grade_line = f"{venue_tag} | {grade}"

        msg = (
            f"{title}\n"
            f"{grade_line}\n\n"
            f"🪙 ${_esc(sym)} · {stage}\n"
            f"📊 综合分: {_b(str(score))}/100\n"
        )

        if s["change_24h"]:
            ch24 = f"{s['change_24h']:+.1f}%"
            msg += f"💹 24h: {_b(ch24)}\n"

        if s["oi_change_1h"]:
            oi1h = f"{s['oi_change_1h']:+.1f}%"
            msg += f"📦 OI 1h: {_b(oi1h)}\n"

        price = (s["bn_data"] or s["hl_data"]).get("price", 0)
        if price > 0:
            if price < 0.01:
                p_str = f"${price:.6f}"
            elif price < 1:
                p_str = f"${price:.4f}"
            else:
                p_str = f"${price:,.2f}"
            msg += f"💰 现价: {p_str}\n"

        # 🆕 v30.11: 阻力位 (24h 高 / 7d 高)
        # 🆕 v30.13.5: 跟踪阻力距离, 用于位置不利警告
        resist_up_pct = None
        try:
            high_24h, high_7d = fetch_resistance_levels(sym)
            if high_24h and high_24h > price * 1.001:
                if high_24h < 0.01:
                    h24_str = f"${high_24h:.6f}"
                elif high_24h < 1:
                    h24_str = f"${high_24h:.4f}"
                else:
                    h24_str = f"${high_24h:,.4f}"
                up_pct = (high_24h - price) / price * 100 if price else 0
                resist_up_pct = up_pct
                resist_line = f"📍 阻力: 24h 高 {h24_str} (距 +{up_pct:.1f}%)"
                # 7d 高仅在显著高于 24h 高时显示
                if high_7d and high_7d > high_24h * 1.02:
                    if high_7d < 0.01:
                        h7_str = f"${high_7d:.6f}"
                    elif high_7d < 1:
                        h7_str = f"${high_7d:.4f}"
                    else:
                        h7_str = f"${high_7d:,.4f}"
                    up7_pct = (high_7d - price) / price * 100 if price else 0
                    resist_line += f" · 7d 高 {h7_str} (距 +{up7_pct:.1f}%)"
                msg += resist_line + "\n"
        except Exception as e:
            print(f"[Sentinel/Resistance] {sym}: {e}")

        # 🆕 v30.13.4: 斐波那契关注位 (技术分析参考, 不是预测)
        # 🆕 v30.13.5: 只显示 0.382 一档 + 阻力距离对比的位置不利警告
        try:
            fib_section = format_fib_section(sym, price, resist_up_pct=resist_up_pct)
            if fib_section:
                msg += fib_section + "\n"
        except Exception as e:
            print(f"[Sentinel/Fib] {sym}: {e}")

        msg += (
            f"\n<i>分项</i>: OI {comp['oi']}/25 · 价格 {comp['price']}/20 · "
            f"Funding {comp['funding']}/15 · 量能 {comp['volume']}/15 · 鲸鱼 {comp['whale']}/15\n"
        )

        if s["whale_count"] > 0:
            try:
                whales_on = _find_active_whales_on_coin(conn, sym, min_size_usd=300_000)
                whale_block = _fmt_whales_on_coin_block(whales_on)
                if whale_block:
                    msg += whale_block
            except Exception:
                pass

        # AI 判断
        judgment = ""
        try:
            judgment = generate_sentinel_judgment(
                sym, score, stage, comp, s["change_24h"], s["whale_count"], channel
            ) or ""
            if judgment:
                msg += f"\n\n💭 {_esc(judgment)}"
                try:
                    conn.execute(
                        "UPDATE sentinel_signals SET ai_judgment=? "
                        "WHERE symbol=? AND id=(SELECT MAX(id) FROM sentinel_signals WHERE symbol=?)",
                        (judgment, sym, sym)
                    )
                    conn.commit()
                except Exception:
                    pass
        except Exception as e:
            print(f"[Sentinel/AI] {sym}: {e}")

        # 信号时间戳 (匹配 Michill 风格"05/03 00:06")
        sig_time = s.get("signal_time", "")
        if sig_time:
            msg += f"\n🕐 信号时间: {_esc(sig_time)}"

        # 链接
        link_parts = []
        if s["bn_data"]:
            link_parts.append(f"<a href=\"https://www.binance.com/zh-CN/futures/{sym}USDT\">BN</a>")
        if s["hl_data"]:
            link_parts.append(f"<a href=\"https://app.hyperliquid.xyz/trade/{sym}\">HL</a>")
        if link_parts:
            msg += f"\n🔗 {' | '.join(link_parts)}"

        # 🆕 v30.14.15: 文案分 direct/score 两套 (基于 5/11 winrate 7 天数据)
        # direct: 24h close 胜率仅 24% / 均收益 -7.88% (亏损区), 必须严守快进快出
        # score: 24h close 胜率 56% / Alpha +11% / 均收益 +4.19% (有 alpha)
        if channel == "direct":
            msg += f"\n\n<i>⚡ 超短炒信号 · <b>建议 1-4h 内出场</b></i>"
            msg += f"\n<i>📉 历史 24h close 均 -7.88%, 严守 -3% 止损</i>"
        else:  # score
            msg += f"\n\n<i>📊 综合多维信号 · <b>建议 4-24h 内出场</b></i>"
            msg += f"\n<i>📈 历史 24h close 胜率 56% / Alpha +11%</i>"
        msg += f"\n<i>⚠️ 信号仅供研究, 不构成建议. 合约高风险, 自负盈亏.</i>"

        try:
            tail = tail_for_alert(
                "sentinel", sym,
                v=int(score), r=int(score / 10),
                src="sentinel",
                extra={"stage": stage, "score": score, "channel": channel}
            )
            msg += f"\n{tail}"
        except Exception:
            pass

        # 🆕 v30.3: 综合分 ≥ 75 用雷达图 (黑底荧光) 替代纯文字, 失败静默降级
        sent_as_image = False
        if score >= SENTINEL_RADAR_THRESHOLD:
            try:
                radar_img = render_sentinel_radar(
                    sym, score, stage, comp,
                    s["change_24h"], s["oi_change_1h"], channel,
                )
                if radar_img:
                    # 雷达图 caption: 用图替代了"分项"那段, 留 AI 判断 + 鲸鱼 + 链接 + 时间
                    cap_lines = [title, grade_line, ""]
                    cap_lines.append(f"🪙 ${sym} · {stage}")
                    if s["whale_count"] > 0:
                        try:
                            whales_on = _find_active_whales_on_coin(conn, sym, min_size_usd=300_000)
                            wb = _fmt_whales_on_coin_block(whales_on)
                            if wb:
                                cap_lines.append(wb)
                        except Exception:
                            pass
                    # AI judgment (复用上面已经生成的 judgment)
                    if judgment:
                        cap_lines.append("")
                        cap_lines.append(f"💭 {_esc(judgment)}")
                    sig_time_local = s.get("signal_time", "")
                    if sig_time_local:
                        cap_lines.append(f"\n🕐 {_esc(sig_time_local)}")
                    if link_parts:
                        cap_lines.append(f"🔗 {' | '.join(link_parts)}")
                    cap_lines.append("")
                    cap_lines.append("<i>⚠️ 信号仅供研究, 不构成建议. 合约高风险, 自负盈亏.</i>")
                    try:
                        tail = tail_for_alert("sentinel", sym,
                                              v=int(score), r=int(score / 10), src="sentinel",
                                              extra={"stage": stage, "score": score, "channel": channel})
                        cap_lines.append(tail)
                    except Exception:
                        pass
                    caption = "\n".join(cap_lines)
                    # Telegram caption 上限 1024 字符
                    if len(caption) > 1020:
                        caption = caption[:1020] + "..."
                    tg_msg_id = send_tg_photo(radar_img, caption)
                    if tg_msg_id:
                        sent_as_image = True
                        # 🆕 v30.7: 同步发到币安广场 (综合分≥BINANCE_SQUARE_MIN_SCORE)
                        if (BINANCE_SQUARE_API_KEY and score >= BINANCE_SQUARE_MIN_SCORE
                                and not is_square_recently_posted(conn, sym)):
                            try:
                                tg_url = f"https://t.me/{TG_CHANNEL_HANDLE}/{tg_msg_id}"
                                square_text = build_square_text_for_sentinel(s, judgment, tg_url)
                                publish_to_binance_square(square_text, symbol=sym, score=score, conn=conn)
                            except Exception as e:
                                print(f"[Square] ❌ {sym} 推送失败: {e}")
            except Exception as e:
                print(f"[Sentinel/Radar] {sym}: {e}")

        if not sent_as_image:
            tg_msg_id_text = send_tg(msg)
            # 🆕 v30.8: 直推强信号也发币安广场 (无雷达图, 纯文字)
            if (channel == "direct"
                    and BINANCE_SQUARE_API_KEY
                    and tg_msg_id_text
                    and not is_square_recently_posted(conn, sym)):
                try:
                    tg_url = f"https://t.me/{TG_CHANNEL_HANDLE}/{tg_msg_id_text}"
                    square_text = build_square_text_for_sentinel(
                        s, judgment, tg_url, channel="direct"
                    )
                    publish_to_binance_square(square_text, symbol=sym, score=score, conn=conn)
                except Exception as e:
                    print(f"[Square/Direct] ❌ {sym} 推送失败: {e}")
        time.sleep(1)

        try:
            conn.execute(
                "UPDATE sentinel_signals SET pushed=1 "
                "WHERE id=(SELECT MAX(id) FROM sentinel_signals WHERE symbol=?)",
                (sym,)
            )
            conn.commit()
        except Exception:
            pass

        # 🆕 v30.11: 入队 1h FOMO 复盘 (任何成功推送的信号都入队)
        try:
            sig_time_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            enqueue_fomo_followup(conn, sym, score, channel, price, sig_time_iso)
        except Exception as e:
            print(f"[FOMO/Enqueue] {sym}: {e}")

        # 🆕 v30.14.12: 同时入队 signal_tracker (实时价格追踪, 触发条件: ±5%/3% 或 1h)
        try:
            enqueue_signal_tracker(conn, sym, score, channel, price, sig_time_iso)
        except Exception as e:
            print(f"[Tracker/Enqueue] {sym}: {e}")

        # 🆕 v30.14.30: 同步入纸上仓位 (score + direct 通道 = LONG 方向)
        # direct 已关 (env=999), 实际只 score 会触发
        if channel in ("score", "direct") and price and price > 0:
            try:
                enqueue_paper_position(conn, sym, channel, "long", price, sig_time_iso)
            except Exception as e:
                print(f"[Paper/score] {sym}: {e}")


# ============================================================
# v30.1: 独立快速通道线程 (10 分钟周期, 匹配 Michill 频率)
# ============================================================
def sentinel_fast_poll_loop():
    """v30.1: 赏金哨独立线程, 10 分钟一扫 (Michill 同频)"""
    print(f"[SentinelFast] 启动 ({SENTINEL_INTERVAL_SEC}s 周期)")
    time.sleep(60)  # 让主循环 init_db 先跑完
    while True:
        try:
            conn = init_db()
            try:
                init_sentinel_db(conn)
                alerts = check_sentinel_signals(conn)
                send_sentinel_alerts(alerts, conn)
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception as e:
            print(f"[SentinelFast] ❌ {e}")
            try:
                traceback.print_exc()
            except Exception:
                pass
        time.sleep(SENTINEL_INTERVAL_SEC)



# ============================================================
# v30.5: 鲸鱼活跃度自动复核 (每周一 09:00 北京 = 01:00 UTC)
# ============================================================
WHALE_HEALTH_INACTIVE_DAYS = _env_int("WHALE_HEALTH_INACTIVE_DAYS", "30")


def whale_health_check(conn):
    """
    v30.5: 自动复核所有 active 鲸鱼活跃度
    - 拉每个地址最近一笔 fill 时间
    - 超过 N 天 (默认 30) 无活动 → 推送告警
    - 不自动改 whale_list.json (避免误杀, 由运营人工决策)
    返回: 复核结果列表
    """
    print(f"[WhaleHealth] 🩺 开始复核 (inactive 阈值: {WHALE_HEALTH_INACTIVE_DAYS} 天)")
    try:
        # 直接读 whale_list.json 全部 whales (含 inactive=False 的也复核)
        paths = [WHALE_LIST_PATH, "/app/whale_list.json", "./whale_list.json"]
        found_path = next((p for p in paths if os.path.exists(p)), None)
        if not found_path:
            print("[WhaleHealth] ❌ whale_list.json 未找到")
            return []
        with open(found_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        all_whales = data.get("whales", [])
    except Exception as e:
        print(f"[WhaleHealth] ❌ 读取失败: {e}")
        return []

    now_utc = datetime.now(timezone.utc)
    threshold = now_utc - timedelta(days=WHALE_HEALTH_INACTIVE_DAYS)
    threshold_ts_ms = int(threshold.timestamp() * 1000)

    results = []  # [(whale, status, last_active_dt, addr_with_activity)]
    for whale in all_whales:
        if not whale.get("active"):
            continue  # 已经 inactive 的不复核
        addrs = [a for a in whale.get("addresses", []) if a and a.startswith("0x")]
        if not addrs:
            results.append({"whale": whale, "status": "no_address", "last_ts": 0})
            continue

        # 取所有地址中最新的 fill 时间
        latest_ts = 0
        latest_addr = None
        for addr in addrs:
            try:
                fills = fetch_whale_fills(addr, limit=5)
                if not fills:
                    continue
                # fills 已按 time 倒序, 取第一条
                t = int(fills[0].get("time", 0))
                if t > latest_ts:
                    latest_ts = t
                    latest_addr = addr
                time.sleep(0.3)  # rate limit 友好
            except Exception as e:
                print(f"[WhaleHealth] {whale.get('id','?')} {addr[:10]}: {e}")

        if latest_ts == 0:
            status = "no_fills_ever"
        elif latest_ts < threshold_ts_ms:
            status = "stale"
        else:
            status = "active"

        results.append({
            "whale": whale,
            "status": status,
            "last_ts": latest_ts,
            "last_addr": latest_addr,
        })

    # 推送告警: 只关注 stale + no_fills
    stale_results = [r for r in results if r["status"] in ("stale", "no_fills_ever", "no_address")]
    active_count = sum(1 for r in results if r["status"] == "active")
    print(f"[WhaleHealth] ✅ 复核 {len(results)} 鲸鱼: 活跃 {active_count}, 待审 {len(stale_results)}")

    if stale_results:
        msg_lines = [
            f"🩺 <b>鲸鱼活跃度周报</b>",
            f"复核 {len(results)} 个 active 鲸鱼, 发现 {len(stale_results)} 个待审:",
            "",
        ]
        for r in stale_results:
            w = r["whale"]
            emoji = w.get("emoji", "🐋")
            name = _esc(w.get("name", w.get("id", "?")))
            wid = _esc(w.get("id", "?"))
            if r["status"] == "stale":
                days_ago = int((now_utc.timestamp() * 1000 - r["last_ts"]) / 86400000)
                line = f"{emoji} <b>{name}</b> · {days_ago} 天无动静"
            elif r["status"] == "no_fills_ever":
                line = f"{emoji} <b>{name}</b> · API 查不到任何 fill (可能已注销/换号)"
            else:
                line = f"{emoji} <b>{name}</b> · 未配置地址"
            msg_lines.append(line)
            msg_lines.append(f"   <code>id: {wid}</code>")

        msg_lines.append("")
        msg_lines.append("👉 GitHub 编辑 whale_list.json 把对应 active 改 false, 或换新钱包后更新 addresses")
        # 🆕 v30.14.13: 改 admin 私推 (这是运维指令, 含 id: 字段和 GitHub 操作步骤, 不该让 640 订阅者看到)
        if not TG_ADMIN_CHAT_ID:
            print("[WhaleHealth] ⚠️ admin 未配置, 跳过推送 (这是运维报告不发频道)")
            return results
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={
                    "chat_id": TG_ADMIN_CHAT_ID,
                    "text": "\n".join(msg_lines),
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=10,
            )
            print(f"[WhaleHealth] ✅ 已私推 admin ({len(stale_results)} 个待审)")
        except Exception as e:
            print(f"[WhaleHealth] 推送失败: {e}")

    return results



# ============================================================
# v30.7: Binance Square 自动发帖 (综合分≥60 高分赏金哨信号)
# ============================================================
BINANCE_SQUARE_API_KEY = os.getenv("BINANCE_SQUARE_API_KEY", "")
BINANCE_SQUARE_DAILY_LIMIT = _env_int("BINANCE_SQUARE_DAILY_LIMIT", "15")
BINANCE_SQUARE_MIN_SCORE = _env_int("BINANCE_SQUARE_MIN_SCORE", "60")
BINANCE_SQUARE_DEDUP_HOURS = _env_int("BINANCE_SQUARE_DEDUP_HOURS", "4")
TG_CHANNEL_HANDLE = os.getenv("TG_CHANNEL_HANDLE", "signformoney")


def init_square_db(conn):
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS binance_square_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        score INTEGER,
        post_id TEXT,
        post_url TEXT,
        text_preview TEXT,
        result_code TEXT,
        result_msg TEXT,
        posted_at TEXT NOT NULL
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_square_sym ON binance_square_posts(symbol, posted_at)")
    conn.commit()


def get_today_square_count(conn):
    """统计今天 (UTC) 成功发布的广场帖子数"""
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM binance_square_posts "
            "WHERE result_code='000000' AND posted_at >= datetime('now', 'start of day')"
        ).fetchone()
        return row[0] if row else 0
    except Exception:
        return 0


def is_square_recently_posted(conn, symbol, hours=None):
    """同币近 N 小时是否已成功发布过"""
    if hours is None:
        hours = BINANCE_SQUARE_DEDUP_HOURS
    try:
        row = conn.execute(
            "SELECT id FROM binance_square_posts "
            "WHERE symbol=? AND result_code='000000' AND posted_at >= datetime('now', ?) LIMIT 1",
            (symbol, f"-{hours} hours")
        ).fetchone()
        return row is not None
    except Exception:
        return False


def publish_to_binance_square(text, symbol="?", score=0, conn=None):
    """
    POST 到币安广场.
    返回: (success: bool, post_url: str|None, error: str|None)
    """
    if not BINANCE_SQUARE_API_KEY:
        return False, None, "no_api_key"

    if conn is not None:
        init_square_db(conn)
        today_count = get_today_square_count(conn)
        if today_count >= BINANCE_SQUARE_DAILY_LIMIT:
            print(f"[Square] ⚠️ {symbol} 已达每日上限 {BINANCE_SQUARE_DAILY_LIMIT}/{today_count}")
            return False, None, "daily_limit"

    try:
        r = requests.post(
            "https://www.binance.com/bapi/composite/v1/public/pgc/openApi/content/add",
            headers={
                "X-Square-OpenAPI-Key": BINANCE_SQUARE_API_KEY,
                "Content-Type": "application/json",
                "clienttype": "binanceSkill"
            },
            json={"bodyTextOnly": text},
            timeout=20
        )
        result_code = "?"
        result_msg = ""
        post_id = ""
        post_url = None

        try:
            data = r.json()
            result_code = str(data.get("code", "?"))
            result_msg = data.get("message") or ""
            if result_code == "000000":
                post_id = ((data.get("data") or {}).get("id", "")) or ""
                if post_id:
                    post_url = f"https://www.binance.com/square/post/{post_id}"
        except Exception:
            result_msg = r.text[:200]

        # Log to DB
        if conn is not None:
            try:
                conn.execute(
                    "INSERT INTO binance_square_posts "
                    "(symbol, score, post_id, post_url, text_preview, result_code, result_msg, posted_at) "
                    "VALUES (?,?,?,?,?,?,?,datetime('now'))",
                    (symbol, score, post_id, post_url or "", text[:200], result_code, result_msg)
                )
                conn.commit()
            except Exception as e:
                print(f"[Square/DB] ❌ {e}")

        if result_code == "000000":
            print(f"[Square] ✅ {symbol} → {post_url}")
            return True, post_url, None
        else:
            # 错误码处理参考 SKILL.md
            err_meanings = {
                "20002": "敏感词", "20013": "长度超限", "20020": "内容为空", "20022": "敏感词(分段)",
                "20041": "URL 风险", "220003": "API key 无效", "220004": "API key 过期",
                "220009": "今日上限", "220010": "不支持的内容类型", "220011": "内容空",
                "30008": "账号被封", "2000001": "账号永久封禁", "2000002": "设备永久封禁",
                "10005": "需完成实名"
            }
            err_label = err_meanings.get(result_code, "未知")
            print(f"[Square] ❌ {symbol} code={result_code} ({err_label}) msg={result_msg[:100]}")
            return False, None, f"{result_code}: {err_label}"
    except Exception as e:
        print(f"[Square] ❌ {symbol} 异常: {e}")
        return False, None, str(e)


def build_square_text_for_sentinel(s, judgment, tg_post_url=None, channel="score"):
    """构造广场推送文字 (无图, 含 TG 跳转链接). 长度需 < 800 字
    channel: 'score' = 综合多维信号; 'direct' = BN OI 直推强信号 (Michill 派)"""
    sym = s["symbol"]
    score = s["score"]
    stage = s["stage"]
    comp = s["components"]
    change_24h = s.get("change_24h", 0)
    oi_change_1h = s.get("oi_change_1h", 0)

    if channel == "direct":
        # 直推强信号: 突出 BN OI 异动
        title_emoji = "💢"
        title = "BN OI 直推强信号"
        venue = "Binance"
    else:
        title_emoji = "🎯"
        title = stage
        if s.get("bn_data") and s.get("hl_data"):
            venue = "双所共振"
        elif s.get("bn_data"):
            venue = "Binance"
        else:
            venue = "Hyperliquid"

    if channel == "direct":
        lines = [
            f"{title_emoji} ${sym} · {title}",
            f"OI 1h {oi_change_1h:+.1f}% (≥30% 阈值触发)",
            f"24h {change_24h:+.1f}% · {venue}",
            "",
        ]
    else:
        lines = [
            f"{title_emoji} ${sym} · {title}",
            f"综合分 {score}/100 · {venue}",
            "",
        ]

    if channel != "direct":
        metric_parts = []
        if oi_change_1h:
            metric_parts.append(f"OI 1h {oi_change_1h:+.1f}%")
        if change_24h:
            metric_parts.append(f"24h {change_24h:+.1f}%")
        if metric_parts:
            lines.append(" · ".join(metric_parts))

    # 分项 — 只展示非零维度
    sub_parts = []
    if comp.get("oi", 0) > 0:
        sub_parts.append(f"OI {comp['oi']}/25")
    if comp.get("price", 0) > 0:
        sub_parts.append(f"价格 {comp['price']}/20")
    if comp.get("funding", 0) > 0:
        sub_parts.append(f"Funding {comp['funding']}/15")
    if comp.get("volume", 0) > 0:
        sub_parts.append(f"量能 {comp['volume']}/15")
    if comp.get("whale", 0) > 0:
        sub_parts.append(f"鲸鱼 {comp['whale']}/15")
    if sub_parts:
        lines.append("分项: " + " · ".join(sub_parts))

    if judgment:
        # 截断 AI 判断, 给广场留 quota
        j = judgment.strip()[:200]
        lines.append("")
        lines.append(f"💭 {j}")

    # 🆕 v30.12: 移除 TG 外链 (币安广场合规要求, 避免被限流)
    # tg_post_url 参数保留兼容性但不再写入广场文案
    lines.append("")
    # 🆕 v30.14.15: 分 direct/score 两套文案 (基于 5/11 winrate 数据)
    if channel == "direct":
        lines.append("⚡ 超短炒信号 · 建议 1-4h 内出场, 严守 -3% 止损")
    else:
        lines.append("📊 综合多维信号 · 建议 4-24h 内出场")
    lines.append("@币世赏金台 · 赏金哨")
    lines.append("⚠️ 仅供研究, 不构成建议. 合约高风险, 自负盈亏.")

    # Hashtags
    lines.append("")
    if channel == "direct":
        lines.append(f"#{sym} #BN_OI异动 #合约信号 #妖币赛道")
    else:
        lines.append(f"#{sym} #合约信号 #OI异动 #妖币雷达")

    return "\n".join(lines)



def build_square_text_for_earn(top3_items):
    """v30.9: 构造每日 Top 3 理财榜的广场文案 (低风险≤3/10 优先)"""
    if not top3_items:
        return None

    today = datetime.now().strftime("%m-%d")
    lines = [
        f"💰 每日理财精选 · Top 3 · {today}",
        "全网 230+ 池, 风险 ≤3/10 高 APY 优选",
        "",
    ]

    medals = ["🥇", "🥈", "🥉"]
    for idx, b in enumerate(top3_items[:3]):
        try:
            apy = b.get("apy", b.get("v", 0))
            platform = b.get("org", b.get("s", "")) or b.get("project_name", "")
            token = b.get("symbol", "")
            try:
                risk = score_risk(b)
            except Exception:
                risk = 5
            chain = b.get("chain", "")

            line = f"{medals[idx]} {platform}"
            if token and token.upper() not in platform.upper():
                line += f" · {token}"
            line += f" · APY {apy:.2f}%"
            lines.append(line)

            sub = f"   🛡️ Risk {risk}/10"
            if chain:
                sub += f" · ⛓️ {chain}"
            tvl = b.get("tvl", 0)
            if tvl >= 1e9:
                sub += f" · 💰 ${tvl/1e9:.2f}B"
            elif tvl >= 1e6:
                sub += f" · 💰 ${tvl/1e6:.1f}M"
            lines.append(sub)
            lines.append("")
        except Exception as e:
            print(f"[Square/Earn] 格式化失败 #{idx}: {e}")

    # 🆕 v30.12: 移除 TG 外链 (币安广场合规)
    lines.append("@币世赏金台 · 每日理财")
    lines.append("⚠️ 仅供参考, 收益有风险, 投资需谨慎.")
    lines.append("")
    lines.append("#DeFi #理财 #高APY #低风险 #稳定币")

    return "\n".join(lines)


def push_earn_to_square(all_b, conn):
    """v30.9: 每日理财 Top 3 (Risk≤3) 自动发广场, 1 条/天"""
    if not BINANCE_SQUARE_API_KEY:
        return
    if conn is None:
        print("[Square/Earn] ⚠️ 无 DB conn, 跳过 (避免重复推送)")
        return

    candidates = []
    for b in all_b:
        if b.get("type") not in ("CEX Yield", "DeFi Yield"):
            continue
        if b.get("s") == "DeFiLlama":
            continue
        try:
            risk = score_risk(b)
            if risk > 3:
                continue
            apy = float(b.get("apy", b.get("v", 0)))
            if apy <= 0:
                continue
            b["_risk_score"] = risk
            b["_apy"] = apy
            candidates.append(b)
        except Exception:
            continue

    top3 = sorted(candidates, key=lambda x: x["_apy"], reverse=True)[:3]
    if not top3:
        print("[Square/Earn] ⚠️ 无符合条件 (Risk≤3) 的理财池, 跳过")
        return

    init_square_db(conn)
    try:
        row = conn.execute(
            "SELECT id FROM binance_square_posts "
            "WHERE symbol='__earn_daily__' AND result_code='000000' "
            "AND posted_at >= datetime('now', 'start of day') LIMIT 1"
        ).fetchone()
        if row:
            print("[Square/Earn] ⏭️ 今日理财榜已发, 跳过")
            return
    except Exception:
        pass

    text = build_square_text_for_earn(top3)
    if not text:
        return
    print(f"[Square/Earn] 📤 推送每日理财 Top 3 (字数 {len(text)})")
    try:
        publish_to_binance_square(text, symbol="__earn_daily__", score=0, conn=conn)
    except Exception as e:
        print(f"[Square/Earn] ❌ {e}")



# ============================================================
# v30.11: 阻力位 (24h 高 / 7d 高) + 1h FOMO 复盘
# ============================================================
SENTINEL_FOMO_MIN_GAIN_PCT = _env_float("SENTINEL_FOMO_MIN_GAIN_PCT", "3.0")


def fetch_price_change_1h(symbol):
    """🆕 v30.14.5: 拉 Binance 永续 1h kline 算价格变化
    返回: 1h 涨幅% (正数=涨, 负数=跌) 或 None
    用于 v2_pass 判定 (报告 Part C 的"1h 价格未启动"条件)
    """
    try:
        r = requests.get(
            f"{BINANCE_FAPI}/fapi/v1/klines",
            params={"symbol": f"{symbol}USDT", "interval": "1h", "limit": 2},
            timeout=8
        )
        if r.status_code != 200:
            return None
        kl = r.json()
        if not isinstance(kl, list) or len(kl) < 2:
            return None
        # kline = [open_time, o, h, l, c, vol, ...]
        # 用最近 1h 的开盘价 vs 收盘价
        prev_close = float(kl[-2][4])  # 上一根 1h 的收盘
        cur_close = float(kl[-1][4])   # 当前 1h 的收盘 (实时, 这根还没结束)
        if prev_close <= 0:
            return None
        return (cur_close - prev_close) / prev_close * 100
    except Exception:
        return None


def fetch_resistance_levels(symbol):
    """v30.11: 从 Binance 永续 K线 拉 24h 高 + 7d 高 (作为阻力位)
    返回: (high_24h, high_7d) 或 (None, None)
    """
    try:
        # 7 天日 K, 拉 8 根防止时区抖动
        r = requests.get(
            f"{BINANCE_FAPI}/fapi/v1/klines",
            params={"symbol": f"{symbol}USDT", "interval": "1d", "limit": 8},
            timeout=10
        )
        if r.status_code != 200:
            return None, None
        klines = r.json()
        if not isinstance(klines, list) or len(klines) < 1:
            return None, None
        # kline[2] = 最高价
        last_24h = float(klines[-1][2]) if klines else None
        max_7d = max(float(k[2]) for k in klines[-7:]) if len(klines) >= 1 else None
        return last_24h, max_7d
    except Exception as e:
        print(f"[Resistance] {symbol}: {e}")
        return None, None


# 🆕 v30.13.4: 斐波那契回撤位 (用户视为「关注位」, 不是回调点预测)
def fetch_fib_retracements(symbol):
    """从 Binance 永续 K 线计算 7 天 swing high → swing low 的斐波那契回撤
    返回: dict {'swing_high', 'swing_low', 'fib_382', 'fib_5', 'fib_618'} 或 None

    用法: 信号触发时显示给用户, 标注为「关注位」(技术分析参考, 不是预测).
    """
    try:
        r = requests.get(
            f"{BINANCE_FAPI}/fapi/v1/klines",
            params={"symbol": f"{symbol}USDT", "interval": "4h", "limit": 42},  # 7 天 × 6 根/天
            timeout=10
        )
        if r.status_code != 200:
            return None
        kl = r.json()
        if not isinstance(kl, list) or len(kl) < 10:
            return None
        # kline 索引: [open_time, o, h, l, c, vol, ...]
        swing_high = max(float(k[2]) for k in kl)
        swing_low = min(float(k[3]) for k in kl)
        if swing_high <= swing_low:
            return None
        rng = swing_high - swing_low
        # 标准斐波那契回撤位 (从 high 往下回撤)
        return {
            "swing_high": swing_high,
            "swing_low": swing_low,
            "fib_382": swing_high - rng * 0.382,
            "fib_5": swing_high - rng * 0.5,
            "fib_618": swing_high - rng * 0.618,
        }
    except Exception as e:
        print(f"[Fib] {symbol}: {e}")
        return None


def _fmt_price(p):
    """统一价格格式 (信号通用)"""
    if p is None:
        return "?"
    if p < 0.01:
        return f"${p:.6f}"
    if p < 1:
        return f"${p:.4f}"
    return f"${p:,.4f}"


def format_fib_section(symbol, current_price, resist_up_pct=None):
    """🆕 v30.13.5: 只显示 0.382 一档支撑 (其他档对短炒无意义) + 位置不利警告

    参数:
      resist_up_pct: 24h 高距离现价的百分比 (正数). 用于风险报酬比检查.
    返回: 多行字符串, 或 ""

    位置不利判定: 阻力距离 < 0.5 × 0.382 支撑距离
    意思: 上方空间 < 下方空间的一半 → R/R 比超过 1:2 → 不该入场
    """
    fib = fetch_fib_retracements(symbol)
    if not fib or not current_price:
        return ""
    # 只在现价介于 swing_low 和 swing_high 之间时显示, 防止溢出
    if not (fib["swing_low"] < current_price <= fib["swing_high"]):
        return ""

    # 只取 0.382 (最近的支撑, 短炒级别参考)
    level_382 = fib["fib_382"]
    if level_382 >= current_price:
        return ""  # 现价已在 0.382 之下, 没意义

    support_dist_pct = (current_price - level_382) / current_price * 100  # 正数

    lines = ["📍 <i>关注位 (技术参考, 非预测):</i>"]
    lines.append(f"  支撑 0.382: {_fmt_price(level_382)} (-{support_dist_pct:.1f}%)")

    # 🆕 v30.13.5: 风险报酬比 — 阻力 < 0.7 × 支撑距离 = 位置不利
    # (0.7 阈值 = R/R 比 1:1.4+ 都警告. 调试: AGT 1:1.8 应触发警告)
    if resist_up_pct is not None and support_dist_pct > 0:
        rr_ratio = resist_up_pct / support_dist_pct  # 越小越不利
        if rr_ratio < 0.7:
            lines.append(f"⚠️ <b>位置不利</b>: 上方仅 +{resist_up_pct:.1f}% / 下方 -{support_dist_pct:.1f}% (1:{1/rr_ratio:.1f})")

    return "\n".join(lines)



def init_fomo_db(conn):
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS sentinel_fomo_followup (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        signal_score INTEGER,
        signal_channel TEXT,
        signal_price REAL,
        signal_time TEXT,
        followup_1h_done INTEGER DEFAULT 0,
        UNIQUE(symbol, signal_time)
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_fomo_pending ON sentinel_fomo_followup(followup_1h_done, signal_time)")
    conn.commit()


# 🆕 v30.14.12: 信号价格触发追踪 (Kings 5/10 决策, Twitter 用户 @TheReality32 提需求)
# 设计原则:
#   • 不写"建议平仓", 只给数据让用户自行判断 (法律责任安全)
#   • 触发条件: 浮盈 ≥+5% 或 ≤-3% 或 1h 时间到, 三选一先到的
#   • 每个信号最多触发 1 次, 防刷屏
#   • 复用 sentinel_fomo_followup 的轮询机制 (每 SENTINEL_INTERVAL_SEC=600s)
def init_signal_tracker_db(conn):
    """v30.14.12: 价格追踪表"""
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS signal_tracker (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        signal_score INTEGER,
        signal_channel TEXT,
        signal_price REAL,
        signal_time TEXT,
        tracker_done INTEGER DEFAULT 0,
        triggered_reason TEXT,
        triggered_price REAL,
        triggered_at TEXT,
        UNIQUE(symbol, signal_time)
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_tracker_pending ON signal_tracker(tracker_done, signal_time)")
    conn.commit()


def enqueue_signal_tracker(conn, symbol, score, channel, price, signal_time):
    """信号推送后, 入队价格追踪. 复用同步 enqueue_fomo_followup 的位置, 同时调用"""
    init_signal_tracker_db(conn)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO signal_tracker "
            "(symbol, signal_score, signal_channel, signal_price, signal_time) VALUES (?,?,?,?,?)",
            (symbol, score, channel, price, signal_time)
        )
        conn.commit()
    except Exception as e:
        print(f"[Tracker/Enqueue] {symbol}: {e}")


# ─────────────────────────────────────────────
# 🆕 v30.14.30: Paper Trading (纸上交易)
# ─────────────────────────────────────────────
# 设计:
#   - 初始本金 $1000 USDT
#   - 每单仓位 10% × 当前余额 (动态调整, 大赚后单仓变大)
#   - 杠杆 10x (名义 = 10% × 余额 × 10)
#   - 全通道入仓 (score / short / short_vip / rebound)
#   - 全局递增 signal_no (#001, #002, ...)
#   - admin dogfood, 不进频道
#   - v30.14.31 加: 自动结算 + /pnl 命令
PAPER_INITIAL_BALANCE = 1000.0
PAPER_POSITION_PCT = 0.10  # 每单 10% 本金
PAPER_LEVERAGE = 10


def init_paper_trading_db(conn):
    """🆕 v30.14.30: 纸上交易表 + 账户初始化"""
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS paper_positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        signal_no INTEGER NOT NULL UNIQUE,
        symbol TEXT NOT NULL,
        channel TEXT NOT NULL,
        direction TEXT NOT NULL,
        entry_price REAL NOT NULL,
        entry_time TEXT NOT NULL,
        position_usd REAL NOT NULL,
        leverage INTEGER DEFAULT 10,
        notional_usd REAL NOT NULL,
        status TEXT DEFAULT 'open',
        exit_price REAL,
        exit_time TEXT,
        exit_reason TEXT,
        pnl_usd REAL,
        pnl_pct REAL,
        UNIQUE(symbol, entry_time)
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_paper_status ON paper_positions(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_paper_signal_no ON paper_positions(signal_no)")

    # 账户 KV (单行, 用 kv_set 存 JSON 简化)
    if kv_get(conn, "paper_balance") is None:
        kv_set(conn, "paper_balance", str(PAPER_INITIAL_BALANCE))
        kv_set(conn, "paper_next_signal_no", "1")
        print(f"[Paper] ✅ 账户初始化: ${PAPER_INITIAL_BALANCE}")
        # 🆕 推 admin 私聊一条欢迎/初始化通知
        if TG_ADMIN_CHAT_ID:
            try:
                bj_time = (_utcnow() + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
                init_msg = (
                    f"💼 <b>纸上交易账户已开通</b>\n\n"
                    f"💰 初始本金: <b>${PAPER_INITIAL_BALANCE}</b> USDT\n"
                    f"⚡ 杠杆: {PAPER_LEVERAGE}x\n"
                    f"📊 每单仓位: {int(PAPER_POSITION_PCT * 100)}% × 余额 = ${int(PAPER_INITIAL_BALANCE * PAPER_POSITION_PCT)}\n"
                    f"📏 名义额: ${int(PAPER_INITIAL_BALANCE * PAPER_POSITION_PCT * PAPER_LEVERAGE)}\n\n"
                    f"📡 入仓通道: score / short / short_vip / rebound\n"
                    f"⏰ 启动时间: {bj_time} (北京)\n\n"
                    f"<i>📝 dogfood 模式, 每次开仓自动推这里</i>\n"
                    f"<i>📝 复盘帖仍进频道 (含 #编号)</i>\n"
                    f"<i>📝 v30.14.31 加 /pnl 命令看账户</i>\n"
                    f"<i>📝 未来接 Binance Futures 实盘</i>"
                )
                send_tg_reply(TG_ADMIN_CHAT_ID, init_msg)
            except Exception as e:
                print(f"[Paper/InitNotify] {e}")
    conn.commit()




def enqueue_paper_position(conn, symbol, channel, direction, entry_price, entry_time):
    """🆕 v30.14.30: 信号推送时同步入纸上仓位
    direction: 'long' 或 'short'
    entry_time: ISO UTC 字符串 (从信号触发时间)
    返回: signal_no (失败返 None)
    🆕 推 admin 私聊一条仓位通知 (Kings 要求 dogfood)
    """
    init_paper_trading_db(conn)
    if not entry_price or entry_price <= 0:
        print(f"[Paper] ⚠️ {symbol} 无价格, 跳过入仓")
        return None
    try:
        # 拉当前余额 + 下一个 signal_no
        balance = float(kv_get(conn, "paper_balance") or PAPER_INITIAL_BALANCE)
        next_no = int(kv_get(conn, "paper_next_signal_no") or 1)

        position_usd = round(balance * PAPER_POSITION_PCT, 2)
        notional_usd = round(position_usd * PAPER_LEVERAGE, 2)

        conn.execute(
            "INSERT OR IGNORE INTO paper_positions "
            "(signal_no, symbol, channel, direction, entry_price, entry_time, "
            " position_usd, leverage, notional_usd) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (next_no, symbol, channel, direction, entry_price, entry_time,
             position_usd, PAPER_LEVERAGE, notional_usd)
        )
        # 检查是否真插入 (符号+时间已存在会被 IGNORE)
        if conn.execute("SELECT changes()").fetchone()[0] == 0:
            return None

        # 递增 signal_no
        kv_set(conn, "paper_next_signal_no", str(next_no + 1))
        conn.commit()
        print(f"[Paper] ✅ #{next_no:03d} {direction.upper()} ${symbol} @ ${entry_price:.6g} "
              f"(本金 ${position_usd}, 名义 ${notional_usd}, 通道 {channel})")

        # 🆕 推 admin 私聊一条仓位开仓通知
        if TG_ADMIN_CHAT_ID:
            try:
                # 方向 emoji
                dir_emoji = "📈" if direction == "long" else "📉"
                dir_label = "LONG" if direction == "long" else "SHORT"
                # 当前北京时间显示
                bj_time = (_utcnow() + timedelta(hours=8)).strftime("%m-%d %H:%M")
                # 累计开仓数
                total_open = conn.execute(
                    "SELECT COUNT(*) FROM paper_positions WHERE status='open'"
                ).fetchone()[0]

                admin_msg = (
                    f"💼 <b>纸上开仓 #{next_no:03d}</b>\n\n"
                    f"{dir_emoji} {dir_label} <b>${symbol}</b>\n"
                    f"📊 通道: {channel}\n"
                    f"💰 入场价: ${entry_price:.6g}\n"
                    f"⏰ 时间: {bj_time} (北京)\n\n"
                    f"💵 本金: ${position_usd}\n"
                    f"⚡ 杠杆: {PAPER_LEVERAGE}x\n"
                    f"📏 名义: ${notional_usd}\n\n"
                    f"📂 当前账户余额: ${balance:.2f}\n"
                    f"🔓 开仓中: {total_open} 单\n\n"
                    f"<i>📝 纸上交易 dogfood, 不影响频道</i>"
                )
                send_tg_reply(TG_ADMIN_CHAT_ID, admin_msg)
            except Exception as e:
                print(f"[Paper/AdminNotify] {symbol}: {e}")

        return next_no
    except Exception as e:
        print(f"[Paper/Enqueue] {symbol}: {e}")
        return None


def get_paper_signal_no(conn, symbol, entry_time):
    """🆕 v30.14.30: 根据 symbol+entry_time 查 signal_no (24h 复盘帖用)
    返回 None 如果该信号没入纸上仓 (理论上每个推送都会入)"""
    try:
        row = conn.execute(
            "SELECT signal_no FROM paper_positions WHERE symbol=? AND entry_time=?",
            (symbol, entry_time)
        ).fetchone()
        return row[0] if row else None
    except Exception:
        return None


def settle_paper_positions(conn):
    """🆕 v30.14.32: 自动结算 paper_positions
    方案 A 规则:
      - LONG (score/rebound): 1h 时间窗到, 用 1h close 价
      - SHORT (short/short_vip): 4h 时间窗到, 用 4h close 价
      - 止盈/止损实时触发 (LONG ≥+5%/-3%, SHORT ≤-3%/+3%)
    每个 SentinelFast 周期 (10 min) 调用一次.
    返回: 结算数量
    """
    settled = 0
    now = _utcnow()

    try:
        open_rows = conn.execute(
            "SELECT id, signal_no, symbol, channel, direction, entry_price, entry_time, "
            "       position_usd, leverage, notional_usd "
            "FROM paper_positions WHERE status='open' LIMIT 50"
        ).fetchall()

        if not open_rows:
            return 0

        for row in open_rows:
            pid, signal_no, symbol, channel, direction, entry_price, entry_time, \
                position_usd, leverage, notional_usd = row

            # 算入场已多久 (小时)
            try:
                et_dt = datetime.fromisoformat(entry_time.replace(" UTC", "").replace(" ", "T"))
                hours_passed = (now - et_dt).total_seconds() / 3600
            except Exception as e:
                print(f"[Settle] #{signal_no} entry_time 解析失败: {e}")
                continue

            # 判断是否该结算
            is_long = direction == "long"
            time_window = 1.0 if is_long else 4.0  # LONG 1h, SHORT 4h
            close_at_window = hours_passed >= time_window

            # 拉 K 线 (从入场后, 短 limit)
            try:
                k_resp = requests.get(
                    f"{BINANCE_FAPI}/fapi/v1/klines",
                    params={
                        "symbol": f"{symbol}USDT",
                        "interval": "5m",
                        "startTime": int(et_dt.timestamp() * 1000),
                        "limit": 60,  # 5h 内 K 线足够 (5 * 60 / 5 = 60)
                    },
                    timeout=8,
                )
                if k_resp.status_code != 200:
                    continue
                klines = k_resp.json()
                if not klines or len(klines) < 1:
                    continue
            except Exception as e:
                print(f"[Settle] #{signal_no} ${symbol} K 线拉取失败: {e}")
                continue

            # 扫描 K 线找止盈/止损 + 时间窗
            exit_price = None
            exit_reason = None
            exit_time_iso = None

            for k in klines:
                k_open_time_ms = int(k[0])
                k_high = float(k[2])
                k_low = float(k[3])
                k_close = float(k[4])
                k_dt = datetime.fromtimestamp(k_open_time_ms / 1000, tz=timezone.utc).replace(tzinfo=None)

                # 算这根 K 线的 high/low/close pct
                hi_pct = (k_high - entry_price) / entry_price * 100
                lo_pct = (k_low - entry_price) / entry_price * 100

                if is_long:
                    # LONG: ≥+5% 止盈, ≤-3% 止损
                    if hi_pct >= 5:
                        exit_price = entry_price * 1.05
                        exit_reason = "take_profit"
                        exit_time_iso = k_dt.strftime("%Y-%m-%d %H:%M:%S")
                        break
                    if lo_pct <= -3:
                        exit_price = entry_price * 0.97
                        exit_reason = "stop_loss"
                        exit_time_iso = k_dt.strftime("%Y-%m-%d %H:%M:%S")
                        break
                else:  # short
                    # SHORT: ≤-3% 止盈 (反向), ≥+3% 止损 (反向)
                    if lo_pct <= -3:
                        exit_price = entry_price * 0.97
                        exit_reason = "take_profit"
                        exit_time_iso = k_dt.strftime("%Y-%m-%d %H:%M:%S")
                        break
                    if hi_pct >= 3:
                        exit_price = entry_price * 1.03
                        exit_reason = "stop_loss"
                        exit_time_iso = k_dt.strftime("%Y-%m-%d %H:%M:%S")
                        break

            # 如果没触发止盈/止损, 检查时间窗
            if exit_reason is None:
                if close_at_window:
                    # 找时间窗到点最近的 K 线 close
                    window_dt = et_dt + timedelta(hours=time_window)
                    closest_k = None
                    for k in klines:
                        k_dt = datetime.fromtimestamp(int(k[0]) / 1000, tz=timezone.utc).replace(tzinfo=None)
                        if k_dt >= window_dt:
                            closest_k = k
                            break
                    if closest_k:
                        exit_price = float(closest_k[4])
                        exit_reason = "time_window"
                        exit_time_iso = datetime.fromtimestamp(int(closest_k[0]) / 1000, tz=timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        # 时间窗已过但 K 线没覆盖 → 用最后一根 close 兜底
                        last_k = klines[-1]
                        exit_price = float(last_k[4])
                        exit_reason = "time_window"
                        exit_time_iso = datetime.fromtimestamp(int(last_k[0]) / 1000, tz=timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    # 还在持仓中, 跳过
                    continue

            # 算 PnL
            close_pct = (exit_price - entry_price) / entry_price * 100
            if is_long:
                pnl_pct = close_pct * leverage
            else:
                pnl_pct = -close_pct * leverage
            pnl_usd = round(position_usd * pnl_pct / 100, 2)

            # 更新表
            try:
                conn.execute(
                    "UPDATE paper_positions SET status=?, exit_price=?, exit_time=?, "
                    "exit_reason=?, pnl_usd=?, pnl_pct=? WHERE id=?",
                    (f"closed_{exit_reason}", exit_price, exit_time_iso,
                     exit_reason, pnl_usd, round(pnl_pct, 2), pid)
                )
                # 更新余额
                old_balance = float(kv_get(conn, "paper_balance") or PAPER_INITIAL_BALANCE)
                new_balance = round(old_balance + pnl_usd, 2)
                kv_set(conn, "paper_balance", str(new_balance))
                conn.commit()
                settled += 1
                print(f"[Settle] ✅ #{signal_no:03d} {direction.upper()} ${symbol} "
                      f"exit={exit_price:.6g} ({close_pct:+.2f}%) PnL=${pnl_usd:+.2f} ({pnl_pct:+.1f}%) "
                      f"[{exit_reason}] balance ${old_balance:.2f}→${new_balance:.2f}")

                # 推 admin 私聊结算通知
                if TG_ADMIN_CHAT_ID:
                    try:
                        dir_emoji = "📈" if is_long else "📉"
                        dir_label = "LONG" if is_long else "SHORT"
                        result_emoji = "✅" if pnl_usd > 0 else ("❌" if pnl_usd < 0 else "➖")
                        reason_label = {
                            "take_profit": "🎯 止盈",
                            "stop_loss": "⚠️ 止损",
                            "time_window": f"⏱️ {int(time_window)}h 时间窗到"
                        }.get(exit_reason, exit_reason)

                        bj_time = (now + timedelta(hours=8)).strftime("%m-%d %H:%M")
                        balance_change_pct = (pnl_usd / old_balance * 100) if old_balance > 0 else 0

                        admin_msg = (
                            f"💼 <b>纸上平仓 #{signal_no:03d}</b> {result_emoji}\n\n"
                            f"{dir_emoji} {dir_label} <b>${symbol}</b> ({channel})\n"
                            f"📅 入场: ${entry_price:.6g}\n"
                            f"📤 出场: ${exit_price:.6g} ({close_pct:+.2f}%)\n"
                            f"📊 理由: {reason_label}\n\n"
                            f"💸 PnL: <b>${pnl_usd:+.2f}</b> ({pnl_pct:+.1f}% 本金)\n"
                            f"📂 余额: ${old_balance:.2f} → <b>${new_balance:.2f}</b> ({balance_change_pct:+.2f}%)\n"
                            f"⏰ 平仓时间: {bj_time} (北京)\n\n"
                            f"<i>📝 自动结算 dogfood</i>"
                        )
                        send_tg_reply(TG_ADMIN_CHAT_ID, admin_msg)
                    except Exception as e:
                        print(f"[Settle/AdminNotify] #{signal_no}: {e}")

            except Exception as e:
                print(f"[Settle] #{signal_no} UPDATE 失败: {e}")
                continue

    except Exception as e:
        print(f"[Settle/Outer] {e}")

    return settled


def check_signal_trackers(conn):
    """v30.14.12: 每次 SentinelFast 周期检查所有 pending 追踪
    🆕 v30.14.20: 加 SHORT 模式支持 (signal_channel='short')
    LONG 触发 (按优先级):
      1. 浮盈 ≥ +5% → "📍 已触达 +5% 浮盈位"
      2. 浮亏 ≤ -3% → "⚠️ 跌破 -3%"
      3. 推送 ≥55 分钟 → "⏰ 1h 时间窗到"
    SHORT 触发 (反向):
      1. 浮跌 ≤ -3% → "🎯 已下跌 3%, SHORT 止盈位"
      2. 反向 ≥ +3% → "🚨 反向上涨 3%, SHORT 止损位"
      3. 推送 ≥235 分钟 → "⏰ 4h 时间窗到 (严禁过夜)"
    """
    init_signal_tracker_db(conn)
    pushed = 0

    # env 可调阈值 (LONG)
    take_profit_pct = float(os.getenv("TRACKER_TAKE_PROFIT_PCT", "5.0"))
    stop_loss_pct = float(os.getenv("TRACKER_STOP_LOSS_PCT", "-3.0"))
    time_window_min = int(os.getenv("TRACKER_TIME_WINDOW_MIN", "55"))
    # 🆕 v30.14.20: SHORT 模式专属阈值
    short_take_profit_pct = float(os.getenv("TRACKER_SHORT_TP_PCT", "-3.0"))  # 跌 -3% 止盈
    short_stop_loss_pct = float(os.getenv("TRACKER_SHORT_SL_PCT", "3.0"))  # 反弹 +3% 止损
    short_time_window_min = int(os.getenv("TRACKER_SHORT_TIME_WINDOW_MIN", "235"))  # 4h - 5min 缓冲

    try:
        # 找所有 pending 追踪 (SHORT 需要 4h+5min 上限, 所以放宽到 270min)
        rows = conn.execute(
            "SELECT id, symbol, signal_score, signal_channel, signal_price, signal_time "
            "FROM signal_tracker "
            "WHERE tracker_done=0 "
            "AND datetime(signal_time) >= datetime('now', '-270 minutes') "
            "LIMIT 30"
        ).fetchall()
    except Exception as e:
        print(f"[Tracker/Query] {e}")
        return 0

    if not rows:
        return 0

    for row in rows:
        rid, symbol, sig_score, sig_channel, sig_price, sig_time = row
        # 🆕 v30.14.29: short_vip 走 SHORT 反向止盈/止损 (跟 short 一致, 只是标签不同)
        is_short = sig_channel in ("short", "short_vip")
        try:
            # 拉当前价 (复用 FOMO 同样的 BN 接口)
            r = requests.get(
                f"{BINANCE_FAPI}/fapi/v1/ticker/price",
                params={"symbol": f"{symbol}USDT"}, timeout=8
            )
            if r.status_code != 200:
                continue
            cur_price = float(r.json().get("price", 0))
            if cur_price <= 0 or sig_price <= 0:
                continue

            gain_pct = (cur_price - sig_price) / sig_price * 100

            # 计算距推送时间 (分钟)
            try:
                sig_t = datetime.strptime(sig_time, "%Y-%m-%d %H:%M:%S")
                # signal_time 是 UTC, 用 utcnow 比较
                elapsed_min = (datetime.utcnow() - sig_t).total_seconds() / 60
            except Exception:
                elapsed_min = 0

            # 判断触发原因 (按优先级)
            trigger_reason = None
            if is_short:
                # 🆕 v30.14.20: SHORT 反向触发
                if gain_pct <= short_take_profit_pct:
                    trigger_reason = "short_take_profit"  # 跌够了, 平
                elif gain_pct >= short_stop_loss_pct:
                    trigger_reason = "short_stop_loss"  # 反弹了, 止损
                elif elapsed_min >= short_time_window_min:
                    trigger_reason = "short_time_up"  # 4h 到了, 严禁过夜
            else:
                # LONG (旧逻辑)
                if gain_pct >= take_profit_pct:
                    trigger_reason = "take_profit"
                elif gain_pct <= stop_loss_pct:
                    trigger_reason = "stop_loss"
                elif elapsed_min >= time_window_min:
                    trigger_reason = "time_up"

            if not trigger_reason:
                continue  # 都没到, 等下一轮

            # 推送
            try:
                _send_signal_tracker_alert(symbol, sig_score, sig_channel, sig_price,
                                           cur_price, gain_pct, elapsed_min, trigger_reason)
                pushed += 1
                # 标记完成 + 记录触发详情
                conn.execute(
                    "UPDATE signal_tracker SET tracker_done=1, "
                    "triggered_reason=?, triggered_price=?, triggered_at=datetime('now') "
                    "WHERE id=?",
                    (trigger_reason, cur_price, rid)
                )
                conn.commit()
            except Exception as e:
                print(f"[Tracker/Push] {symbol}: {e}")

        except Exception as e:
            print(f"[Tracker] {symbol} 处理错误: {e}")
            continue

        time.sleep(0.3)  # 温柔点, 别把 BN API 搞炸

    return pushed


def _compute_alpha_snapshot(conn, days=30):
    """🆕 v30.14.29: 计算指定天数的 alpha 关键指标快照
    用于 daily_alpha_briefing 跨天/跨周对比.
    返回 dict 含 LONG/SHORT 核心规则胜率.
    """
    snapshot = {
        "days": days,
        "long": {},
        "short": {},
        "n_long_total": 0,
        "n_short_total": 0,
    }

    try:
        cutoff = (_utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

        # 拉 score/direct 通道的样本 (LONG 视角)
        rows = conn.execute(
            "SELECT s.score, s.change_24h, s.funding_binance, s.funding_hyperliquid, "
            "       s.score_components, s.price, s.signal_time, s.symbol "
            "FROM sentinel_signals s "
            "WHERE s.push_channel IN ('score', 'direct') "
            "AND s.recorded_at >= ? "
            "LIMIT 1000",
            (cutoff,)
        ).fetchall()

        long_results = {"60-65": [0, 0], "66+": [0, 0], "5-10%": [0, 0], "≤-5%": [0, 0],
                        "cross_10+": [0, 0], "funding_04+": [0, 0]}

        for r in rows:
            score, ch24, fund_bn, fund_hl, comps_json, price, sig_time, sym = r
            if not sig_time or not price or price <= 0:
                continue
            # 拉 1h K 线 (24h 后)
            try:
                kr = requests.get(
                    f"{BINANCE_FAPI}/fapi/v1/klines",
                    params={"symbol": f"{sym}USDT", "interval": "1h",
                            "startTime": int(datetime.fromisoformat(sig_time.replace(" UTC", "").replace(" ", "T")).timestamp() * 1000),
                            "limit": 25},
                    timeout=8
                )
                if kr.status_code != 200:
                    continue
                klines = kr.json()
                if not klines or len(klines) < 24:
                    continue
                close_24h = float(klines[23][4])
                close_pct = (close_24h - price) / price * 100
            except Exception:
                continue

            won = close_pct >= 3
            lost = close_pct <= -3

            # 评分段
            if 60 <= score <= 65:
                if won: long_results["60-65"][0] += 1
                if lost: long_results["60-65"][1] += 1
            elif score >= 66:
                if won: long_results["66+"][0] += 1
                if lost: long_results["66+"][1] += 1

            # 24h 涨幅
            if 5 <= ch24 <= 10:
                if won: long_results["5-10%"][0] += 1
                if lost: long_results["5-10%"][1] += 1
            elif ch24 <= -5:
                if won: long_results["≤-5%"][0] += 1
                if lost: long_results["≤-5%"][1] += 1

            # funding
            f8h = max(abs(fund_bn or 0), abs(fund_hl or 0)) * 100  # 转 %
            if f8h >= 0.04:
                if won: long_results["funding_04+"][0] += 1
                if lost: long_results["funding_04+"][1] += 1

            # cross
            try:
                comps = json.loads(comps_json) if comps_json else {}
                cross = comps.get("cross", 0)
                if cross >= 10:
                    if won: long_results["cross_10+"][0] += 1
                    if lost: long_results["cross_10+"][1] += 1
            except Exception:
                pass

        # 算赢率
        for k, (w, l) in long_results.items():
            total = w + l
            snapshot["long"][k] = {
                "won": w, "lost": l,
                "winrate": round(w / total * 100, 1) if total > 0 else None,
                "n": total
            }
        snapshot["n_long_total"] = sum(w + l for w, l in long_results.values())

        # 拉 SHORT 样本 (类似)
        short_rows = conn.execute(
            "SELECT s.score, s.change_24h, s.funding_binance, s.funding_hyperliquid, "
            "       s.score_components, s.price, s.signal_time, s.symbol "
            "FROM sentinel_signals s "
            "WHERE s.push_channel IN ('short', 'short_dog', 'short_vip') "
            "AND s.recorded_at >= ? "
            "LIMIT 1000",
            (cutoff,)
        ).fetchall()

        short_results = {"cross_10": [0, 0], "funding_04+": [0, 0],
                         "funding_02_04": [0, 0], "OI_18+": [0, 0]}

        for r in short_rows:
            score, ch24, fund_bn, fund_hl, comps_json, price, sig_time, sym = r
            if not sig_time or not price or price <= 0:
                continue
            try:
                kr = requests.get(
                    f"{BINANCE_FAPI}/fapi/v1/klines",
                    params={"symbol": f"{sym}USDT", "interval": "1h",
                            "startTime": int(datetime.fromisoformat(sig_time.replace(" UTC", "").replace(" ", "T")).timestamp() * 1000),
                            "limit": 5},  # 4h 内即可
                    timeout=8
                )
                if kr.status_code != 200:
                    continue
                klines = kr.json()
                if not klines or len(klines) < 4:
                    continue
                close_4h = float(klines[3][4])
                close_pct = (close_4h - price) / price * 100
            except Exception:
                continue

            # SHORT 视角: close ≤-3% 算赢, close > 0 算输
            won = close_pct <= -3
            lost = close_pct > 0

            try:
                comps = json.loads(comps_json) if comps_json else {}
                cross = comps.get("cross", 0)
                oi_sub = comps.get("oi", 0)
            except Exception:
                cross, oi_sub = 0, 0
            f8h = max(abs(fund_bn or 0), abs(fund_hl or 0)) * 100

            if cross >= 10:
                if won: short_results["cross_10"][0] += 1
                if lost: short_results["cross_10"][1] += 1
            if f8h >= 0.04:
                if won: short_results["funding_04+"][0] += 1
                if lost: short_results["funding_04+"][1] += 1
            elif 0.02 <= f8h < 0.04:
                if won: short_results["funding_02_04"][0] += 1
                if lost: short_results["funding_02_04"][1] += 1
            if oi_sub >= 18:
                if won: short_results["OI_18+"][0] += 1
                if lost: short_results["OI_18+"][1] += 1

        for k, (w, l) in short_results.items():
            total = w + l
            snapshot["short"][k] = {
                "won": w, "lost": l,
                "winrate": round(w / total * 100, 1) if total > 0 else None,
                "n": total
            }
        snapshot["n_short_total"] = sum(w + l for w, l in short_results.values())

    except Exception as e:
        print(f"[AlphaSnapshot] error: {e}")

    return snapshot


def _format_alpha_change(curr, prev, key, label):
    """Helper: 格式化 alpha 变化, 返回 (txt, is_changed)"""
    c = curr.get(key, {})
    p = prev.get(key, {}) if prev else {}
    c_wr = c.get("winrate")
    p_wr = p.get("winrate")
    if c_wr is None:
        return f"  {label}: 无样本 (n=0)", False
    if p_wr is None:
        return f"  {label}: {c_wr}% (n={c['n']}, 首次记录)", True
    delta = c_wr - p_wr
    arrow = "⬆️" if delta > 0 else ("⬇️" if delta < 0 else "→")
    changed = abs(delta) >= 5
    flag = " ⚠️" if changed else ""
    return f"  {label}: {c_wr}% (n={c['n']}, 上次 {p_wr}%, {arrow}{delta:+.1f}%){flag}", changed


def push_daily_alpha_briefing(conn):
    """🆕 v30.14.29: 每天北京 08:00 (UTC 0:00) 推 admin alpha 报告
    B+C 组合: 平日智能告警 (有变化才推), 周日完整周报.
    返回: True 已推送, False 跳过
    """
    if not TG_ADMIN_CHAT_ID:
        print("[AlphaDaily] ⚠️ TG_ADMIN_CHAT_ID 未配置, 跳过")
        return False

    now = _utcnow()
    is_sunday = now.weekday() == 6  # 周日 (UTC 0:00 周日 = 北京 08:00 周日)
    today_str = now.date().strftime("%Y-%m-%d")

    print(f"[AlphaDaily] 触发 (is_sunday={is_sunday})")

    # 拉今日 30 天快照
    try:
        curr = _compute_alpha_snapshot(conn, days=30)
    except Exception as e:
        print(f"[AlphaDaily] snapshot failed: {e}")
        return False

    # 拉上周快照 (用 KV 存)
    prev_key = "alpha_snapshot_prev_week"
    prev_json = kv_get(conn, prev_key)
    prev = None
    if prev_json:
        try:
            prev = json.loads(prev_json)
        except Exception:
            prev = None

    # 检测变化
    changes = []
    short_changes = []
    for key, label in [("60-65", "score 60-65"), ("66+", "score 66+"),
                       ("5-10%", "24h 5-10%"), ("≤-5%", "24h ≤-5% 反弹甜区"),
                       ("cross_10+", "cross ≥10"), ("funding_04+", "funding ≥0.04%")]:
        txt, ch = _format_alpha_change(curr["long"], prev.get("long", {}) if prev else None, key, label)
        changes.append((txt, ch))

    for key, label in [("cross_10", "cross=10 SHORT"), ("funding_04+", "funding ≥0.04% SHORT"),
                       ("funding_02_04", "funding 0.02-0.04% SHORT 反向"),
                       ("OI_18+", "OI 18-25 SHORT")]:
        txt, ch = _format_alpha_change(curr["short"], prev.get("short", {}) if prev else None, key, label)
        short_changes.append((txt, ch))

    has_changes = any(c for _, c in changes) or any(c for _, c in short_changes)

    # 拉本周触发的 VIP 信号 (signal_tracker.signal_channel='short_vip')
    week_cutoff = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    vip_rows = []
    try:
        vip_rows = conn.execute(
            "SELECT symbol, signal_score, signal_price, signal_time "
            "FROM signal_tracker WHERE signal_channel='short_vip' "
            "AND datetime(signal_time) >= datetime(?) "
            "ORDER BY signal_time DESC LIMIT 10",
            (week_cutoff,)
        ).fetchall()
    except Exception as e:
        print(f"[AlphaDaily] VIP 拉取失败: {e}")

    # 平日 + 无变化 + 无 VIP → 跳过
    if not is_sunday and not has_changes and not vip_rows:
        print("[AlphaDaily] 平日无变化无 VIP, 跳过")
        # 仍然保存今日快照 (用于明天对比)
        kv_set(conn, "alpha_snapshot_today", json.dumps(curr))
        return False

    # === 构造报告 ===
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()]
    bj_date = (now + timedelta(hours=8)).date().strftime("%m-%d")
    report_type = "📅 周报" if is_sunday else "🔔 智能告警"

    lines = [
        f"{report_type} · {bj_date} {weekday_cn}",
        "",
        f"━━━━━━━━━━━━━━",
        f"📊 LONG Alpha (近 30 天, 总样本 n={curr['n_long_total']})",
        f"━━━━━━━━━━━━━━",
    ]
    # 周报全列; 智能告警只列有变化的
    for txt, ch in changes:
        if is_sunday or ch:
            lines.append(txt)
    if not is_sunday and not any(c for _, c in changes):
        lines.append("  (LONG 无显著变化)")

    lines.append("")
    lines.append(f"━━━━━━━━━━━━━━")
    lines.append(f"🔻 SHORT Alpha (近 30 天, 总样本 n={curr['n_short_total']})")
    lines.append(f"━━━━━━━━━━━━━━")
    for txt, ch in short_changes:
        if is_sunday or ch:
            lines.append(txt)
    if not is_sunday and not any(c for _, c in short_changes):
        lines.append("  (SHORT 无显著变化)")

    # VIP 信号验证 (近 7 天)
    if vip_rows:
        lines.append("")
        lines.append(f"━━━━━━━━━━━━━━")
        lines.append(f"⭐⭐ 本周 VIP 信号 (含 24h 验证)")
        lines.append(f"━━━━━━━━━━━━━━")
        for vrow in vip_rows[:5]:
            sym, vscore, vprice, vtime = vrow
            try:
                # 拉 24h 后 K 线
                vt = datetime.fromisoformat(vtime.replace(" UTC", "").replace(" ", "T"))
                hours_passed = (now - vt).total_seconds() / 3600
                if hours_passed >= 24:
                    kr = requests.get(
                        f"{BINANCE_FAPI}/fapi/v1/klines",
                        params={"symbol": f"{sym}USDT", "interval": "1h",
                                "startTime": int(vt.timestamp() * 1000),
                                "limit": 25},
                        timeout=8
                    )
                    if kr.status_code == 200:
                        klines = kr.json()
                        if klines and len(klines) >= 24:
                            close_24h = float(klines[23][4])
                            close_pct = (close_24h - vprice) / vprice * 100
                            verdict = "✅" if close_pct <= -3 else ("❌" if close_pct > 0 else "➖")
                            lines.append(f"  ${sym} ({vscore}/100): 24h close {close_pct:+.2f}% {verdict}")
                            continue
                lines.append(f"  ${sym} ({vscore}/100): 等 24h ({hours_passed:.1f}h 已过)")
            except Exception as e:
                lines.append(f"  ${sym}: 数据获取失败")
        if len(vip_rows) > 5:
            lines.append(f"  ...还有 {len(vip_rows)-5} 条")

    # Footer
    lines.append("")
    lines.append("ℹ️ 数据驱动, 不构成建议")
    if has_changes:
        lines.append("⚠️ 检测到 alpha 变化 ≥5%, 关注是否持续")
    if is_sunday:
        lines.append("📅 周日完整周报, 平日仅异常告警")

    msg = "\n".join(lines)

    # 推 admin (使用 TG_ADMIN_CHAT_ID, 不是频道)
    try:
        send_tg_reply(TG_ADMIN_CHAT_ID, msg)
        print(f"[AlphaDaily] ✅ 已推 admin (changes={has_changes}, vip={len(vip_rows)}, type={report_type})")

        # 周日 → 保存为"上周快照"
        if is_sunday:
            kv_set(conn, "alpha_snapshot_prev_week", json.dumps(curr))
            print("[AlphaDaily] 📦 已保存周日快照为下周对比基准")

        # 每天保存今日快照
        kv_set(conn, "alpha_snapshot_today", json.dumps(curr))
        return True
    except Exception as e:
        print(f"[AlphaDaily] ❌ 推送失败: {e}")
        return False


def check_4h_alpha_recap(conn):
    """🆕 v30.14.30: SHORT/rebound/score 信号 4h 后自动发实战复盘帖
    数据源: signal_tracker 表
    触发条件: signal_time 在 4-5h 前, recap_4h_done=0
    专为 SHORT 4h 黄金窗口设计 (历史 4h 胜率 78%)
    """
    # 扩展 signal_tracker 表加 recap_4h_done 字段
    try:
        conn.execute("ALTER TABLE signal_tracker ADD COLUMN recap_4h_done INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass  # 已存在

    pushed = 0
    try:
        now = _utcnow()
        cutoff_start = (now - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S")
        cutoff_end = (now - timedelta(hours=4)).strftime("%Y-%m-%d %H:%M:%S")

        rows = conn.execute(
            "SELECT id, symbol, signal_score, signal_channel, signal_price, signal_time "
            "FROM signal_tracker "
            "WHERE recap_4h_done=0 "
            "AND signal_channel IN ('short', 'short_dog', 'short_vip', 'rebound', 'score') "
            "AND datetime(signal_time) <= datetime(?) "
            "AND datetime(signal_time) >= datetime(?) "
            "LIMIT 5"
        , (cutoff_end, cutoff_start)).fetchall()

        if not rows:
            return 0

        for row in rows:
            rid, sym, sig_score, sig_channel, sig_price, sig_time = row
            try:
                # 拉 4h 内的 5min K 线找 peak/valley (4h × 60 / 5 = 48 根)
                kr = requests.get(
                    f"{BINANCE_FAPI}/fapi/v1/klines",
                    params={"symbol": f"{sym}USDT", "interval": "5m", "limit": 48},
                    timeout=10,
                )
                if kr.status_code != 200:
                    raise Exception(f"BN HTTP {kr.status_code}")
                klines = kr.json()
                if not klines or len(klines) < 24:
                    raise Exception(f"K 线不足 (got {len(klines)})")

                highs = [float(k[2]) for k in klines]
                lows = [float(k[3]) for k in klines]
                closes = [float(k[4]) for k in klines]
                peak_4h = max(highs)
                valley_4h = min(lows)
                close_4h = closes[-1]

                peak_pct = (peak_4h - sig_price) / sig_price * 100
                valley_pct = (valley_4h - sig_price) / sig_price * 100
                close_pct = (close_4h - sig_price) / sig_price * 100

                # 找 peak/valley 在第几分钟 (用于 4h 黄金窗叙事)
                peak_idx = highs.index(peak_4h)
                valley_idx = lows.index(valley_4h)
                peak_min = (peak_idx + 1) * 5
                valley_min = (valley_idx + 1) * 5

                is_short = sig_channel in ("short", "short_dog", "short_vip")
                is_rebound = sig_channel == "rebound"
                direction = "🔻 SHORT" if is_short else ("🔄 REBOUND" if is_rebound else "📊 LONG")

                # 计算 verdict (SHORT 视角看 close ≤-3%, LONG/rebound 视角看 ≥+3%)
                if is_short:
                    won = close_pct <= -3
                    triggered_sl = peak_pct >= 3  # 反向止损
                    triggered_tp = valley_pct <= -3  # 正向止盈
                else:
                    won = close_pct >= 3
                    triggered_sl = valley_pct <= -3
                    triggered_tp = peak_pct >= 5

                verdict = "✅ 胜" if won else ("❌ 输" if abs(close_pct) >= 3 else "➖ 平")

                # 🆕 v30.14.30: 查 paper_positions 取 signal_no
                signal_no = get_paper_signal_no(conn, sym, sig_time)
                signal_no_tag = f" #{signal_no:03d}" if signal_no else ""

                # 精确入场时间
                try:
                    entry_dt = datetime.fromisoformat(sig_time.replace(" UTC", "").replace(" ", "T"))
                    entry_time_str = entry_dt.strftime("%m-%d %H:%M UTC")
                except Exception:
                    entry_time_str = "4h 前"

                # VIP 标签
                vip_tag = "⭐⭐ " if sig_channel == "short_vip" else ""

                # 文案
                msg = (
                    f"{vip_tag}⏰ <b>{direction}{signal_no_tag} 4h 复盘 · ${sym}</b>\n\n"
                    f"📅 入场: ${sig_price:.6g} ({entry_time_str} · score {sig_score})\n"
                    f"💰 4h close: ${close_4h:.6g} ({close_pct:+.2f}%)\n"
                    f"🏔️ 4h Peak: ${peak_4h:.6g} ({peak_pct:+.2f}%, 第 {peak_min}min)\n"
                    f"🏜️ 4h Valley: ${valley_4h:.6g} ({valley_pct:+.2f}%, 第 {valley_min}min)\n\n"
                    f"📊 结果: {verdict}\n"
                )

                # 实战教训 (SHORT 专用因为 4h 是黄金窗口)
                if is_short:
                    if triggered_tp and valley_min <= 120:
                        msg += f"<i>💡 SHORT 在 {valley_min}min 触底 {valley_pct:+.2f}%, 4h 黄金窗兑现</i>\n"
                    elif triggered_tp:
                        msg += f"<i>💡 SHORT 在 {valley_min}min 触底 {valley_pct:+.2f}%, 时间窗末段</i>\n"
                    if triggered_sl:
                        msg += f"<i>⚠️ 反向触发 +{peak_pct:.1f}% (第 {peak_min}min), 止损线救命</i>\n"
                    if not won and not triggered_sl:
                        msg += f"<i>➖ 4h 未触止盈, 接近时间窗末段, 准备出场</i>\n"
                elif is_rebound:
                    if triggered_tp and peak_min <= 60:
                        msg += f"<i>💡 反弹 {peak_min}min 见顶 {peak_pct:+.2f}%, 黄金 1h 窗</i>\n"
                    elif triggered_tp:
                        msg += f"<i>💡 反弹 {peak_min}min 见顶 {peak_pct:+.2f}%</i>\n"
                else:  # long/score
                    if triggered_tp and peak_min <= 60:
                        msg += f"<i>💡 LONG 1h 内 peak {peak_pct:+.2f}%, 短线最优</i>\n"
                    elif triggered_sl:
                        msg += f"<i>⚠️ 跌破 -3% 触止损位 (第 {valley_min}min)</i>\n"

                msg += f"\n<i>📊 数据复盘, 非建议. v30.14.30 新增 4h alpha 复盘</i>"

                send_tg(msg)
                conn.execute("UPDATE signal_tracker SET recap_4h_done=1 WHERE id=?", (rid,))
                conn.commit()
                pushed += 1
                print(f"[Recap4h] ✅ ${sym}{signal_no_tag} {sig_channel} verdict={verdict} close={close_pct:+.2f}% → 频道")

            except Exception as e:
                print(f"[Recap4h] ${sym}: {e}")
                # 失败也标记 done 避免无限重试
                try:
                    conn.execute("UPDATE signal_tracker SET recap_4h_done=1 WHERE id=?", (rid,))
                    conn.commit()
                except Exception:
                    pass
    except Exception as e:
        print(f"[Recap4h/Outer] {e}")

    return pushed


def check_24h_recap(conn):
    """🆕 v30.14.27 D: 24h 后自动发实战复盘帖
    数据源: signal_tracker 表
    触发条件: signal_time 在 24-26h 前, recap_done=0
    复盘内容: 入场价 / 当前价 / peak 价 / valley 价 / 实战教训
    """
    # 扩展 signal_tracker 表加 recap_done 字段
    try:
        conn.execute("ALTER TABLE signal_tracker ADD COLUMN recap_done INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        pass  # 已存在

    pushed = 0
    try:
        now = _utcnow()
        cutoff_start = (now - timedelta(hours=26)).strftime("%Y-%m-%d %H:%M:%S")
        cutoff_end = (now - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

        rows = conn.execute(
            "SELECT id, symbol, signal_score, signal_channel, signal_price, signal_time "
            "FROM signal_tracker "
            "WHERE recap_done=0 "
            "AND signal_channel IN ('short', 'short_dog', 'short_vip', 'rebound', 'score') "
            "AND datetime(signal_time) <= datetime(?) "
            "AND datetime(signal_time) >= datetime(?) "
            "LIMIT 5"
        , (cutoff_end, cutoff_start)).fetchall()

        if not rows:
            return 0

        for row in rows:
            rid, sym, sig_score, sig_channel, sig_price, sig_time = row
            try:
                # 拉 24h 内的 1h K 线找 peak/valley
                kr = requests.get(
                    f"{BINANCE_FAPI}/fapi/v1/klines",
                    params={"symbol": f"{sym}USDT", "interval": "1h", "limit": 24},
                    timeout=10,
                )
                if kr.status_code != 200:
                    raise Exception(f"BN HTTP {kr.status_code}")
                klines = kr.json()
                if not klines or len(klines) < 4:
                    raise Exception(f"K 线不足 (got {len(klines)})")

                # k 格式: [open_time, open, high, low, close, volume, ...]
                highs = [float(k[2]) for k in klines]
                lows = [float(k[3]) for k in klines]
                closes = [float(k[4]) for k in klines]
                peak_24h = max(highs)
                valley_24h = min(lows)
                close_24h = closes[-1]

                peak_pct = (peak_24h - sig_price) / sig_price * 100
                valley_pct = (valley_24h - sig_price) / sig_price * 100
                close_pct = (close_24h - sig_price) / sig_price * 100

                # 找 peak/valley 在第几小时 (用于复盘叙事)
                peak_h = highs.index(peak_24h) + 1
                valley_h = lows.index(valley_24h) + 1

                is_short = sig_channel in ("short", "short_dog", "short_vip")
                is_rebound = sig_channel == "rebound"
                direction = "🔻 SHORT" if is_short else ("🔄 REBOUND" if is_rebound else "📊 LONG")

                # 计算 verdict (复盘结论)
                if is_short:
                    won = close_pct <= -3
                    best_exit = "1h" if -valley_pct >= 3 and valley_h <= 1 else ("4h 内" if -valley_pct >= 3 and valley_h <= 4 else "未触止盈")
                elif is_rebound:
                    won = close_pct >= 3
                    best_exit = "1h" if peak_pct >= 5 and peak_h <= 1 else ("4h 内" if peak_pct >= 5 and peak_h <= 4 else "未触止盈")
                else:  # long/score
                    won = close_pct >= 3
                    best_exit = "1h" if peak_pct >= 5 and peak_h <= 1 else ("4h 内" if peak_pct >= 5 and peak_h <= 4 else "未触止盈")

                verdict = "✅ 胜" if won else ("❌ 输" if abs(close_pct) >= 3 else "➖ 平")

                # 🆕 v30.14.30: 查 paper_positions 取 signal_no (公开数据, 给用户参考)
                signal_no = get_paper_signal_no(conn, sym, sig_time)
                signal_no_tag = f" #{signal_no:03d}" if signal_no else ""

                # 🆕 v30.14.30: 精确入场时间 (从 ISO UTC 转可读)
                try:
                    entry_dt = datetime.fromisoformat(sig_time.replace(" UTC", "").replace(" ", "T"))
                    entry_time_str = entry_dt.strftime("%Y-%m-%d %H:%M UTC")
                except Exception:
                    entry_time_str = sig_time

                # 复盘文案 (进频道, 不含 paper trading 内部数据)
                msg = (
                    f"📊 <b>{direction}{signal_no_tag} 复盘 · ${sym}</b>\n\n"
                    f"📅 入场: ${sig_price:.6g} ({entry_time_str} · score {sig_score})\n"
                    f"💰 当前: ${close_24h:.6g} ({close_pct:+.2f}%)\n"
                    f"🏔️ 24h Peak: ${peak_24h:.6g} ({peak_pct:+.2f}%, 第 {peak_h}h)\n"
                    f"🏜️ 24h Valley: ${valley_24h:.6g} ({valley_pct:+.2f}%, 第 {valley_h}h)\n\n"
                    f"📊 结果: {verdict}\n"
                    f"🎯 最优出场: {best_exit}\n\n"
                )

                # 实战教训
                if is_short:
                    if won and valley_h <= 4:
                        msg += f"<i>💡 SHORT 在 {valley_h}h 触底 {valley_pct:+.2f}%, 严守 4h 出场对的</i>\n"
                    elif peak_pct >= 3:
                        msg += f"<i>⚠️ 反向触发 +{peak_pct:.1f}%, 止损线救命</i>\n"
                    if close_pct > valley_pct + 3:
                        msg += f"<i>⚠️ 24h 持仓反弹 {close_pct - valley_pct:.1f}%, 验证严禁过夜</i>\n"
                elif is_rebound:
                    if won and peak_h <= 4:
                        msg += f"<i>💡 反弹在 {peak_h}h 见顶 {peak_pct:+.2f}%, 1h-4h 是黄金窗</i>\n"
                    elif valley_pct <= -5:
                        msg += f"<i>⚠️ 跌深 {valley_pct:.1f}%, 抄底需先确认止跌</i>\n"
                else:  # long
                    if won and peak_h <= 1:
                        msg += f"<i>💡 1h 内 peak {peak_pct:+.2f}%, 短线最优</i>\n"
                    elif close_pct < peak_pct - 3:
                        msg += f"<i>⚠️ peak 后回撤 {peak_pct - close_pct:.1f}%, 及时止盈很关键</i>\n"

                msg += f"\n<i>📊 数据复盘, 非建议. v30.14.30 加 #编号 + 精确时间.</i>"

                # 复盘进频道 (公开教育用户)
                send_tg(msg)
                conn.execute("UPDATE signal_tracker SET recap_done=1 WHERE id=?", (rid,))
                conn.commit()
                pushed += 1
                print(f"[Recap24h] ✅ ${sym}{signal_no_tag} {sig_channel} verdict={verdict} close={close_pct:+.2f}% → 频道")

            except Exception as e:
                print(f"[Recap24h] ${sym}: {e}")
                # 失败也标记 done 避免无限重试
                try:
                    conn.execute("UPDATE signal_tracker SET recap_done=1 WHERE id=?", (rid,))
                    conn.commit()
                except Exception:
                    pass
    except Exception as e:
        print(f"[Recap24h/Outer] {e}")

    return pushed


def _send_signal_tracker_alert(symbol, sig_score, sig_channel, sig_price,
                               cur_price, gain_pct, elapsed_min, reason):
    """构造并发送追踪提醒. 措辞严格遵守: 只给数据, 不写'建议平仓'
    🆕 v30.14.20: 加 SHORT 模式 (signal_channel='short' 对应 short_* reason)
    🆕 v30.14.29: short_vip 也走 SHORT 文案
    """
    is_short = sig_channel in ("short", "short_vip")
    # 表情和文案根据触发原因选 (LONG + SHORT 共 6 种 reason)
    if reason == "take_profit":  # LONG 止盈
        emoji = "🎯"
        title = "已触达 +5% 浮盈位"
        verdict = f"{emoji} 浮盈 {gain_pct:+.2f}%, 自行判断是否止盈"
    elif reason == "stop_loss":  # LONG 止损
        emoji = "⚠️"
        title = "跌破 -3% 警戒位"
        verdict = f"{emoji} 浮亏 {gain_pct:+.2f}%, 自行判断风险"
    elif reason == "short_take_profit":  # 🆕 SHORT 止盈 (价格跌)
        emoji = "🎯"
        title = "SHORT 已下跌 3%, 止盈位"
        verdict = f"{emoji} 浮盈 {-gain_pct:+.2f}% (做空), 自行判断是否止盈"
    elif reason == "short_stop_loss":  # 🆕 SHORT 止损 (价格反弹)
        emoji = "🚨"
        title = "SHORT 反向上涨 3%, 止损位"
        verdict = f"{emoji} 反向亏损 {gain_pct:+.2f}% (做空), 自行判断风险"
    elif reason == "short_time_up":  # 🆕 SHORT 时间到 (4h)
        emoji = "⏰"
        title = "SHORT 4h 时间窗已到, 严禁过夜"
        if gain_pct <= -1:
            verdict = f"{emoji} 浮盈 {-gain_pct:+.2f}% (做空), 自行判断"
        elif gain_pct >= 1:
            verdict = f"{emoji} 浮亏 {gain_pct:+.2f}% (做空), 自行判断"
        else:
            verdict = f"{emoji} 横盘 ({gain_pct:+.2f}%), 24h 反向风险大, 自行判断"
    else:  # LONG time_up
        emoji = "⏰"
        title = "1h 时间窗已到"
        if gain_pct >= 1:
            verdict = f"{emoji} 浮盈 {gain_pct:+.2f}%, 自行判断"
        elif gain_pct <= -1:
            verdict = f"{emoji} 浮亏 {gain_pct:+.2f}%, 自行判断"
        else:
            verdict = f"{emoji} 横盘 ({gain_pct:+.2f}%), 自行判断"

    elapsed_str = f"{int(elapsed_min)} 分钟"
    direction_tag = "🔻 SHORT" if is_short else "📍 LONG"

    msg = (
        f"{direction_tag} <b>${symbol} 信号追踪</b> · {elapsed_str}前\n\n"
        f"📊 入场参考: ${sig_price:.6g}\n"
        f"📍 当前价: ${cur_price:.6g}\n"
        f"💰 价格变动: <b>{gain_pct:+.2f}%</b>\n\n"
        f"{title}\n"
        f"{verdict}\n\n"
        f"<i>📲 开户: <code>{HL_REFERRAL}</code></i>\n"
        f"<i>⚠️ 数据更新, 不构成交易建议</i>"
    )
    # tail 标签
    try:
        tail = tail_for_alert(
            "tracker", f"{symbol}_{int(elapsed_min)}m",
            v=int(gain_pct * 100),
            r=sig_score or 0,
            src=reason,
            extra={"sym": symbol, "gain": round(gain_pct, 2), "reason": reason, "side": "short" if is_short else "long"}
        )
        msg += f"\n{tail}"
    except Exception:
        pass

    send_tg(msg)
    print(f"[Tracker] ✅ {'SHORT' if is_short else 'LONG'} {symbol} {reason} gain={gain_pct:+.2f}% 已推 ({elapsed_str})")


def enqueue_fomo_followup(conn, symbol, score, channel, price, signal_time):
    """信号推送后, 入队 1h FOMO 复盘"""
    init_fomo_db(conn)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO sentinel_fomo_followup "
            "(symbol, signal_score, signal_channel, signal_price, signal_time) VALUES (?,?,?,?,?)",
            (symbol, score, channel, price, signal_time)
        )
        conn.commit()
    except Exception as e:
        print(f"[FOMO/Enqueue] {symbol}: {e}")


def check_fomo_followups(conn):
    """v30.11: 信号 1h 后检查涨幅, 仅 ≥ SENTINEL_FOMO_MIN_GAIN_PCT 的推送"""
    init_fomo_db(conn)
    pushed = 0
    try:
        # 找到 55-90 分钟前的待复盘 (留 5min 缓冲)
        rows = conn.execute(
            "SELECT id, symbol, signal_score, signal_channel, signal_price, signal_time "
            "FROM sentinel_fomo_followup "
            "WHERE followup_1h_done=0 "
            "AND datetime(signal_time) <= datetime('now', '-55 minutes') "
            "AND datetime(signal_time) >= datetime('now', '-90 minutes') "
            "LIMIT 20"
        ).fetchall()
    except Exception as e:
        print(f"[FOMO/Query] {e}")
        return 0

    for row in rows:
        rid, symbol, sig_score, sig_channel, sig_price, sig_time = row
        try:
            # 拉当前价
            r = requests.get(
                f"{BINANCE_FAPI}/fapi/v1/ticker/price",
                params={"symbol": f"{symbol}USDT"}, timeout=8
            )
            if r.status_code != 200:
                continue
            data = r.json()
            cur_price = float(data.get("price", 0))
            if cur_price <= 0 or sig_price <= 0:
                continue

            gain_pct = (cur_price - sig_price) / sig_price * 100

            # 拉 1h 内最高价 (从 5min K线中取近 12 根)
            try:
                r2 = requests.get(
                    f"{BINANCE_FAPI}/fapi/v1/klines",
                    params={"symbol": f"{symbol}USDT", "interval": "5m", "limit": 12},
                    timeout=8
                )
                if r2.status_code == 200:
                    kl = r2.json()
                    high_1h = max(float(k[2]) for k in kl)
                    high_gain_pct = (high_1h - sig_price) / sig_price * 100
                else:
                    high_1h = cur_price
                    high_gain_pct = gain_pct
            except Exception:
                high_1h = cur_price
                high_gain_pct = gain_pct

            # 阈值过滤: 必须有显著涨幅才推
            if high_gain_pct < SENTINEL_FOMO_MIN_GAIN_PCT:
                # 🆕 v30.13: SHORT dogfood 例外 — 不管涨跌都推 admin 复盘 (反向产品验证)
                if sig_channel == "short_dog" and TG_ADMIN_CHAT_ID:
                    try:
                        # SHORT 角度: gain_pct 越负越好 (做空赚钱)
                        # close_now = cur_price (1h 后的现价当 close)
                        emoji = "✅" if gain_pct <= -3 else ("➖" if -3 < gain_pct < 1 else "❌")
                        verdict = (
                            "📉 SHORT 命中 (跌≥3%, 做空盈利)" if gain_pct <= -3
                            else "➖ 横盘, SHORT 无优势" if -3 < gain_pct < 1
                            else "📈 反向走势, SHORT 失败"
                        )
                        msg_short = (
                            f"💀 <b>SHORT dogfood · 1h 复盘</b>\n\n"
                            f"🪙 ${symbol} (1h 前 SHORT 候选, 综合分 {sig_score})\n"
                            f"信号价: ${sig_price:.6f}\n"
                            f"1h 现价: ${cur_price:.6f} ({gain_pct:+.2f}%)\n"
                            f"1h 高点: ${high_1h:.6f} ({high_gain_pct:+.2f}%)\n\n"
                            f"{emoji} {verdict}\n\n"
                            f"<i>反向跟单视角: gain_pct ≤ -3% = SHORT 胜</i>"
                        )
                        requests.post(
                            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                            json={"chat_id": TG_ADMIN_CHAT_ID, "text": msg_short,
                                  "parse_mode": "HTML", "disable_web_page_preview": True},
                            timeout=10,
                        )
                        print(f"[SHORT/dogfood] ✅ 1h 复盘私推 admin: ${symbol} {gain_pct:+.2f}%")
                    except Exception as e:
                        print(f"[SHORT/dogfood/followup] {symbol}: {e}")
                # 标记完成 (避免重复检查), 不推送公开 FOMO
                conn.execute("UPDATE sentinel_fomo_followup SET followup_1h_done=1 WHERE id=?", (rid,))
                conn.commit()
                continue

            # 🆕 v30.13: short_dog 通道走 SHORT 复盘私聊, 不进公开 FOMO
            if sig_channel == "short_dog":
                if TG_ADMIN_CHAT_ID:
                    try:
                        # 这条因为涨幅 ≥ FOMO 阈值, 对 SHORT 来说是失败案例
                        msg_short = (
                            f"💀 <b>SHORT dogfood · 1h 复盘</b>\n\n"
                            f"🪙 ${symbol} (综合分 {sig_score})\n"
                            f"信号价: ${sig_price:.6f}\n"
                            f"1h 现价: ${cur_price:.6f} ({gain_pct:+.2f}%)\n\n"
                            f"❌ SHORT 失败 — 1h 内反向上涨 {high_gain_pct:+.2f}%\n"
                            f"<i>反向跟单视角: 这条做空亏损</i>"
                        )
                        requests.post(
                            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                            json={"chat_id": TG_ADMIN_CHAT_ID, "text": msg_short,
                                  "parse_mode": "HTML", "disable_web_page_preview": True},
                            timeout=10,
                        )
                    except Exception as e:
                        print(f"[SHORT/dogfood/followup-fail] {symbol}: {e}")
                conn.execute("UPDATE sentinel_fomo_followup SET followup_1h_done=1 WHERE id=?", (rid,))
                conn.commit()
                continue

            # 构造 FOMO 文案 (TG)
            def _pf(p):
                if p < 0.01: return f"${p:.6f}"
                elif p < 1: return f"${p:.4f}"
                else: return f"${p:,.4f}"

            # 🆕 v30.14.30: 查 paper_positions 取 signal_no + 精确时间
            signal_no = get_paper_signal_no(conn, symbol, sig_time)
            signal_no_tag = f" #{signal_no:03d}" if signal_no else ""
            try:
                entry_dt = datetime.fromisoformat(sig_time.replace(" UTC", "").replace(" ", "T"))
                entry_time_str = entry_dt.strftime("%m-%d %H:%M UTC")
            except Exception:
                entry_time_str = "1h 前"

            fomo_lines = [
                f"🔥 <b>赏金哨{signal_no_tag} · 1h 实战复盘</b>",
                "",
                f"🎯 ${_esc(symbol)} · {entry_time_str} 推送 (综合分 {sig_score})",
                f"信号价: {_pf(sig_price)}",
                f"现价: {_pf(cur_price)} ({gain_pct:+.2f}%)",
            ]
            if high_gain_pct > gain_pct + 0.5:
                fomo_lines.append(f"📈 1h 内最高: {_pf(high_1h)} ({high_gain_pct:+.2f}%)")
            fomo_lines.append("")

            if high_gain_pct >= 8:
                fomo_lines.append("🚀 跟上的吃肉肉, 没跟上的等下一个 👀")
            elif high_gain_pct >= 5:
                fomo_lines.append("✅ 信号兑现, 跟单可控制风险")
            else:
                fomo_lines.append("📊 温和走势, 持续观察确认")

            fomo_lines.append("")
            fomo_lines.append("📲 持续跟踪 → t.me/" + TG_CHANNEL_HANDLE)

            tg_msg_id = send_tg("\n".join(fomo_lines))

            # 同步发币安广场 (高涨幅才发, ≥5% 优质 FOMO)
            if (BINANCE_SQUARE_API_KEY and high_gain_pct >= 5
                    and tg_msg_id):
                try:
                    sq_lines = [
                        f"🔥 实战复盘 · ${symbol} 1 小时前推送",
                        "",
                        f"信号价 {_pf(sig_price)} → 1h 最高 {_pf(high_1h)}",
                        f"涨幅 {high_gain_pct:+.2f}%, 综合分 {sig_score}/100",
                        "",
                    ]
                    if high_gain_pct >= 10:
                        sq_lines.append("🚀 妖币雷达 1h 内吃肉")
                    else:
                        sq_lines.append("✅ 信号兑现, 跟单见效")
                    # 🆕 v30.12: 移除 TG 外链 (币安广场合规)
                    sq_lines.extend([
                        "",
                        "@币世赏金台 · 赏金哨",
                        "⚠️ 仅供研究, 不构成建议. 合约高风险.",
                        "",
                        f"#{symbol} #实战复盘 #合约信号 #妖币雷达",
                    ])
                    sq_text = "\n".join(sq_lines)
                    publish_to_binance_square(sq_text, symbol=f"{symbol}_fomo_1h", score=sig_score, conn=conn)
                except Exception as e:
                    print(f"[FOMO/Square] {symbol}: {e}")

            conn.execute("UPDATE sentinel_fomo_followup SET followup_1h_done=1 WHERE id=?", (rid,))
            conn.commit()
            pushed += 1
            time.sleep(1)
        except Exception as e:
            print(f"[FOMO] {symbol}: {e}")

    return pushed


# ============================================================
# 🆕 v30.14: Agent 三连
#   Agent #1: AI Daily Brief (事件触发, Claude Haiku 摘要)
#   Agent #2: Upbit + Bithumb 上币哨兵 (中韩信息差)
#   Agent #4: Token Unlock Cliff (DefiLlama)
# 共用: _call_haiku() helper
# ============================================================

def _call_haiku(prompt, max_tokens=400, system=None):
    """通用 Haiku 调用. 失败返回 None"""
    if not ANTHROPIC_API_KEY:
        return None
    try:
        body = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]
        }
        if system:
            body["system"] = system
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json=body,
            timeout=30
        )
        if r.status_code == 200:
            data = r.json()
            content = data.get("content", [])
            if content and content[0].get("type") == "text":
                return content[0].get("text", "").strip()
        else:
            print(f"[Haiku] HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[Haiku] ❌ {e}")
    return None


# ─────────────────────────────────────────────
# Agent #1: AI Daily Brief (事件触发版)
# ─────────────────────────────────────────────
# 触发条件 (任一满足且距上条 ≥ 6h):
#   • 24h 内 ≥3 条 sentinel 信号 (含 direct + score)
#   • 24h 内任何鲸鱼橙警/红警
#   • 24h 内 unlock cliff 即将触发
#   • 频道连续静默 ≥18h (兜底防冷)
def _has_brief_trigger(conn):
    """检查是否满足触发条件. 返回 (should_trigger: bool, reason: str)
    🆕 v30.14.11: 冷却 6h → 12h, 触发条件加'自上次 brief 后新增 sentinel ≥3' (而非 24h 累计),
    避免相邻两次 brief 内容重复 (滑窗 80% 重叠问题).
    env 可调:
      AI_BRIEF_COOLDOWN_H (默认 12, 数字)
      AI_BRIEF_SILENCE_FALLBACK_H (默认 24, 静默兜底, 配合 12h 冷却)
    """
    cooldown_h = float(os.getenv("AI_BRIEF_COOLDOWN_H", "12"))
    silence_h = float(os.getenv("AI_BRIEF_SILENCE_FALLBACK_H", "24"))

    # 上次推送时间
    last_str = kv_get(conn, "ai_brief_last_time")
    last_t = None
    if last_str:
        try:
            last_t = datetime.strptime(last_str, "%Y-%m-%d %H:%M:%S")
            elapsed_h = (datetime.now() - last_t).total_seconds() / 3600
            if elapsed_h < cooldown_h:
                return False, f"距上次 {elapsed_h:.1f}h, {cooldown_h:.0f}h 冷却中"
        except Exception:
            pass
    else:
        elapsed_h = silence_h * 2  # 没记录视为足够久

    cutoff_24h = (_utcnow() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

    # 🆕 v30.14.11: "自上次 brief 后" 新增的 sentinel — 这才是真"新东西", 避免内容重复
    cutoff_since_last = None
    if last_t:
        # 用 last_t 作为 since 切点 (注意 last_t 是 local naive, 跟 sentinel_signals 的 recorded_at 同样是 local naive)
        cutoff_since_last = last_t.strftime("%Y-%m-%d %H:%M:%S")

    try:
        n_sig_24h = conn.execute(
            "SELECT COUNT(*) FROM sentinel_signals "
            "WHERE push_channel IN ('direct', 'score') AND datetime(recorded_at) >= ?",
            (cutoff_24h,)
        ).fetchone()[0]
    except Exception:
        n_sig_24h = 0

    n_sig_since_last = 0
    if cutoff_since_last:
        try:
            n_sig_since_last = conn.execute(
                "SELECT COUNT(*) FROM sentinel_signals "
                "WHERE push_channel IN ('direct', 'score') AND datetime(recorded_at) >= ?",
                (cutoff_since_last,)
            ).fetchone()[0]
        except Exception:
            n_sig_since_last = 0

    # 24h 内鲸鱼橙警/红警
    try:
        n_whale = conn.execute(
            "SELECT COUNT(*) FROM whale_alerts "
            "WHERE event IN ('liq_orange', 'liq_red') AND datetime(alerted_at) >= ?",
            (cutoff_24h,)
        ).fetchone()[0]
    except Exception:
        n_whale = 0

    n_whale_since_last = 0
    if cutoff_since_last:
        try:
            n_whale_since_last = conn.execute(
                "SELECT COUNT(*) FROM whale_alerts "
                "WHERE event IN ('liq_orange', 'liq_red') AND datetime(alerted_at) >= ?",
                (cutoff_since_last,)
            ).fetchone()[0]
        except Exception:
            n_whale_since_last = 0

    # 🆕 v30.14.11 触发逻辑 (优先级: 新增量 > 兜底):
    # 1. 没有 last_t (首次跑): 24h 累计 ≥3 sentinel 或 ≥1 鲸鱼橙红警 直接触发
    # 2. 有 last_t: 必须 "自上次 brief 后" 新增 ≥3 sentinel 或 ≥1 鲸鱼橙红警
    # 3. 静默兜底: 距上次 ≥ silence_h 即使没新增也推一条
    if last_t is None:
        if n_sig_24h >= 3:
            return True, f"首次启动, sentinel 24h 累计 {n_sig_24h} 条"
        if n_whale >= 1:
            return True, f"首次启动, 鲸鱼橙红警 {n_whale} 次"
        return False, f"首次启动但触发不足 (sig={n_sig_24h}, whale={n_whale})"

    if n_sig_since_last >= 3:
        return True, f"自上次新增 sentinel {n_sig_since_last} 条 (24h 累计 {n_sig_24h})"
    if n_whale_since_last >= 1:
        return True, f"自上次新增鲸鱼橙红警 {n_whale_since_last} 次"
    if elapsed_h >= silence_h:
        return True, f"频道静默 {elapsed_h:.0f}h, 兜底 (新增 sig={n_sig_since_last}/whale={n_whale_since_last})"

    return False, f"自上次新增不足 (sig={n_sig_since_last}, whale={n_whale_since_last}, 24h 累计 sig={n_sig_24h})"


def _gather_brief_context(conn):
    """收集过去 24h 内的关键事件, 返回结构化文本给 LLM"""
    cutoff = (_utcnow() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    sections = []

    # Sentinel 推送信号
    try:
        rows = conn.execute(
            "SELECT symbol, score, push_channel, price, change_24h, recorded_at "
            "FROM sentinel_signals "
            "WHERE push_channel IN ('direct', 'score') AND datetime(recorded_at) >= ? "
            "ORDER BY score DESC LIMIT 10",
            (cutoff,)
        ).fetchall()
        if rows:
            lines = ["[赏金哨信号 (24h)]"]
            for sym, sc, ch, p, c24, t in rows:
                tag = "💢 直推" if ch == "direct" else "🎯 综合"
                # t 格式 "YYYY-MM-DD HH:MM:SS", 取小时:分钟
                tstr = t[-8:-3] if t and len(t) >= 8 else "?"
                lines.append(f"  {tag} ${sym} 分{sc} 24h{c24 or 0:+.1f}% @{tstr}")
            sections.append("\n".join(lines))
    except Exception as e:
        print(f"[Brief] sentinel 查询失败: {e}")

    # 鲸鱼事件 (橙红警 + 大额开仓)
    try:
        rows = conn.execute(
            "SELECT whale_id, coin, event, alerted_at FROM whale_alerts "
            "WHERE event IN ('liq_orange', 'liq_red', 'big_add') "
            "AND datetime(alerted_at) >= ? "
            "ORDER BY alerted_at DESC LIMIT 10",
            (cutoff,)
        ).fetchall()
        if rows:
            lines = ["[鲸鱼动向 (24h)]"]
            ev_map = {"liq_orange": "🟠橙警", "liq_red": "🔴红警", "big_add": "📈加仓"}
            for wid, coin, ev, t in rows:
                lines.append(f"  {ev_map.get(ev, ev)} {wid} {coin} @{t[-8:-3]}")
            sections.append("\n".join(lines))
    except Exception:
        pass

    # 治理 / Unlock 等其他事件
    try:
        rows = conn.execute(
            "SELECT alert_type, alert_key, alerted_at FROM generic_alerts "
            "WHERE datetime(alerted_at) >= ? "
            "AND alert_type IN ('snapshot_group', 'unlock_24h', 'tvl_red') "
            "ORDER BY alerted_at DESC LIMIT 10",
            (cutoff,)
        ).fetchall()
        if rows:
            lines = ["[其他事件 (24h)]"]
            for at, ak, t in rows:
                lines.append(f"  {at}: {ak[:60]} @{t[-8:-3]}")
            sections.append("\n".join(lines))
    except Exception:
        pass

    return "\n\n".join(sections) if sections else ""


def run_ai_brief_agent(conn):
    """事件触发的 AI Daily Brief
    成本: 单次调用 ~$0.005 (Haiku 4.5, 约 3K input + 500 output)
    频率: 触发驱动, 6h 冷却, 估计每天 1-3 次
    每月成本: <$1
    """
    if not ANTHROPIC_API_KEY:
        return  # 没配 API key 静默跳过

    if os.getenv("AI_BRIEF_ENABLED", "1") != "1":
        return  # 总开关关闭

    should, reason = _has_brief_trigger(conn)
    if not should:
        return

    print(f"[AI Brief] 触发: {reason}, 准备生成...")
    context = _gather_brief_context(conn)
    if not context:
        print(f"[AI Brief] ⚠️ 上下文为空, 跳过")
        return

    system = (
        "你是华语 Web3 频道编辑, 风格直接、有节奏、像 KOL 不像研报。"
        "用户是中文散户, 关心合约信号 / 鲸鱼动向 / 套利机会。"
        "禁止: 编造数字 / 写'建议买入卖出' / 用'重磅' '速看' 等营销词 / 加 emoji 过度堆砌 / "
        "使用任何 markdown 语法 (绝对禁止 ** 加粗、## 标题、* 斜体、--- 分隔线), 输出必须是纯文本。"
    )
    prompt = (
        f"过去 24 小时频道事件汇总如下:\n\n{context}\n\n"
        f"请用 200-350 字中文写一条「赏金哨 · 24h 焦点」推送, 要求:\n"
        f"1. 开头一句话总结今天市场氛围\n"
        f"2. 挑 2-3 个最值得关注的事件展开 (引用具体币种和数字, 必须从上面数据来)\n"
        f"3. 结尾给个观察提示, 不写买卖建议\n"
        f"4. 段落分明, 每段 1-2 句\n"
        f"5. 数字必须和上面提供的一致, 不许补充我没给的\n"
        f"6. 用词必须是标准书面汉语, 不要造词\n"
        f"7. 绝对禁止使用 markdown — 不要写 **xxx** / ##xxx / *xxx*, 标题加粗等富文本由我处理"
    )

    text = _call_haiku(prompt, max_tokens=600, system=system)
    if not text:
        print(f"[AI Brief] ❌ Haiku 返回空, 跳过")
        return

    # 推送
    msg = (
        f"📰 <b>赏金哨 · 24h 焦点</b>\n\n"
        f"{html.escape(text)}\n\n"
        f"<i>—— AI 编辑摘要, 数据源自频道 24h 推送</i>\n"
        f"<i>⚠️ 仅供研究, 不构成任何交易建议</i>"
    )
    try:
        send_tg(msg)
        kv_set(conn, "ai_brief_last_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print(f"[AI Brief] ✅ 已推送, 触发原因: {reason}")
    except Exception as e:
        print(f"[AI Brief] ❌ 推送失败: {e}")


# ─────────────────────────────────────────────
# Agent #1.5: 赏金哨·早报 (Morning Brief, 11:00 北京时间)
# ─────────────────────────────────────────────
# 跟 AI Brief (24h 焦点) 互补:
#   • AI Brief: 频道内部 24h 事件回顾, 触发驱动 (随时)
#   • Morning Brief: 外部新闻 + 链上独家锚点, 每天固定 11:00
# 数据源:
#   1. Coingecko Top 5 涨/跌 (24h, 免费 API)
#   2. Cointelegraph RSS 头条 (免费, stdlib XML 解析)
#   3. 你独家的链上数据 (whale + sentinel 24h 统计) — 护城河
# 成本: 单次 ~$0.005, 每天 1 次, 月 <$0.30
# v30.14.10 新增 (Kings 5/10 决策)
def _fetch_coingecko_movers():
    """取 Coingecko 24h Top 5 涨幅 + Top 5 跌幅 + 主流币全集. 失败返回 {}
    🆕 v30.14.14: 加 retry (429 等 5s 重试 2 次) + 浏览器 UA (绕过 free tier bot 限速)
    """
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 250,
        "page": 1,
        "price_change_percentage": "24h",
    }
    # 用真实浏览器 UA, "Mozilla/5.0" 过于通用经常被 CG 识别 bot
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, timeout=15, headers=headers)
            if r.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f"[Morning/CG] HTTP 429 限速, 等 {wait}s 重试 ({attempt+1}/3)")
                time.sleep(wait)
                continue
            if r.status_code != 200:
                print(f"[Morning/CG] HTTP {r.status_code}")
                return {}
            data = r.json()
            valid = [c for c in data
                     if c.get("price_change_percentage_24h") is not None
                     and c.get("symbol")]
            gainers = sorted(valid, key=lambda x: x["price_change_percentage_24h"], reverse=True)[:5]
            losers = sorted(valid, key=lambda x: x["price_change_percentage_24h"])[:5]
            return {"gainers": gainers, "losers": losers, "all": valid}
        except Exception as e:
            print(f"[Morning/CG] ❌ {e}")
            return {}
    print("[Morning/CG] ❌ 3 次 retry 后仍 429, 放弃")
    return {}


def _fetch_cointelegraph_headlines():
    """取 Cointelegraph 英文 RSS 前 5 条头条, stdlib XML 解析, 失败返回 []"""
    try:
        r = requests.get("https://cointelegraph.com/rss", timeout=15,
                         headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            print(f"[Morning/CT] HTTP {r.status_code}")
            return []
        from xml.etree import ElementTree as ET
        root = ET.fromstring(r.text)
        items = root.findall(".//item")[:5]
        out = []
        for item in items:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            desc = (item.findtext("description") or "").strip()
            # 去 HTML tags 简单处理 (RSS desc 常含 CDATA HTML)
            desc = re.sub(r"<[^>]+>", " ", desc)
            desc = re.sub(r"\s+", " ", desc).strip()[:200]
            if title:
                out.append({"title": title, "link": link, "desc": desc})
        return out
    except Exception as e:
        print(f"[Morning/CT] ❌ {e}")
        return []


# 🆕 v30.14.14: cn.cointelegraph.com 死链 (HTTP 410 Gone), 默认 source 留空
# 用户可通过 env MORNING_CN_RSS_URLS 加自己找到的有效中文 RSS (CSV)
# Cointelegraph 中文相关内容现在挂在 panewslab.com/en/columns/1588214546979147 下, 但没公开 RSS
def _fetch_chinese_headlines():
    """拉中文加密媒体头条 (多源, 失败的跳过, 全失败返回 [])
    v30.14.14: 默认 source 已删 (cn.cointelegraph.com 永久 410), 仅 env 配置时才生效"""
    sources_str = os.getenv("MORNING_CN_RSS_URLS", "")
    sources = [u.strip() for u in sources_str.split(",") if u.strip()]
    if not sources:
        # 默认无中文源, 不打日志, 让英文源 + Coingecko trending 兜底
        return []
    out = []
    for url in sources:
        try:
            r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 410:
                print(f"[Morning/CN] {url[:50]} HTTP 410 永久 Gone, 该源已失效, 建议从 env 删除")
                continue
            if r.status_code != 200:
                print(f"[Morning/CN] {url[:50]} HTTP {r.status_code}")
                continue
            from xml.etree import ElementTree as ET
            root = ET.fromstring(r.text)
            items = root.findall(".//item")[:5]
            count_this_src = 0
            for item in items:
                title = (item.findtext("title") or "").strip()
                if title and len(title) >= 8:
                    out.append({"title": title})
                    count_this_src += 1
            print(f"[Morning/CN] ✅ {url.split('/')[2]}: {count_this_src} 条")
        except Exception as e:
            print(f"[Morning/CN] {url[:50]} ❌ {e}")
            continue
    return out[:5]


# 🆕 v30.14.14: Coingecko Trending 作为额外独家信号 (替代 cn.cointelegraph 死掉的窟窿)
# 公开免费 API, 显示当前最热搜的币种, 跟主流币数据互补
def _fetch_coingecko_trending():
    """取 Coingecko 当前最热门搜索 Top 7 币种. 失败返回 []"""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }
    for attempt in range(2):
        try:
            r = requests.get(
                "https://api.coingecko.com/api/v3/search/trending",
                timeout=10, headers=headers
            )
            if r.status_code == 429:
                time.sleep(5)
                continue
            if r.status_code != 200:
                print(f"[Morning/Trending] HTTP {r.status_code}")
                return []
            data = r.json()
            coins = data.get("coins", [])[:7]
            out = []
            for c in coins:
                item = c.get("item", {})
                sym = (item.get("symbol") or "").upper()
                name = item.get("name", "")
                rank = item.get("market_cap_rank")
                if sym:
                    out.append({"symbol": sym, "name": name, "rank": rank})
            return out
        except Exception as e:
            print(f"[Morning/Trending] ❌ {e}")
            return []
    return []


def _gather_morning_context(conn):
    """收集过去 24h: 外部新闻 + 链上锚点. 即使部分源失败也尽量返回数据"""
    cutoff_24h = (_utcnow() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")

    # 外部
    movers = _fetch_coingecko_movers() or {"gainers": [], "losers": []}
    headlines_en = _fetch_cointelegraph_headlines()
    headlines_cn = _fetch_chinese_headlines()
    trending = _fetch_coingecko_trending()  # 🆕 v30.14.14: 热搜 Top 7

    # 链上锚点
    onchain = {
        "sentinel_direct_24h": 0,
        "sentinel_score_24h": 0,
        "whale_alerts_24h": 0,
        "whale_orange_24h": 0,
        "whale_red_24h": 0,
        "whale_top_winner": None,
        "whale_top_loser": None,
    }
    try:
        onchain["sentinel_direct_24h"] = conn.execute(
            "SELECT COUNT(*) FROM sentinel_signals "
            "WHERE push_channel='direct' AND datetime(recorded_at) >= ?",
            (cutoff_24h,)
        ).fetchone()[0] or 0
    except Exception:
        pass
    try:
        onchain["sentinel_score_24h"] = conn.execute(
            "SELECT COUNT(*) FROM sentinel_signals "
            "WHERE push_channel='score' AND datetime(recorded_at) >= ?",
            (cutoff_24h,)
        ).fetchone()[0] or 0
    except Exception:
        pass
    try:
        onchain["whale_alerts_24h"] = conn.execute(
            "SELECT COUNT(*) FROM whale_alerts "
            "WHERE datetime(alerted_at) >= ?",
            (cutoff_24h,)
        ).fetchone()[0] or 0
        onchain["whale_orange_24h"] = conn.execute(
            "SELECT COUNT(*) FROM whale_alerts "
            "WHERE event='liq_orange' AND datetime(alerted_at) >= ?",
            (cutoff_24h,)
        ).fetchone()[0] or 0
        onchain["whale_red_24h"] = conn.execute(
            "SELECT COUNT(*) FROM whale_alerts "
            "WHERE event='liq_red' AND datetime(alerted_at) >= ?",
            (cutoff_24h,)
        ).fetchone()[0] or 0
    except Exception:
        pass
    # 鲸鱼 24h Top winner / 最大 loser (复用 _get_whale_24h_pnl)
    try:
        ranked = _get_whale_24h_pnl(conn, hours=24)
        winners = [r for r in ranked if r.get("delta", 0) > 0]
        losers = [r for r in ranked if r.get("delta", 0) < 0]
        if winners:
            onchain["whale_top_winner"] = winners[0]  # 已 desc 排序, 第一个最大
        if losers:
            onchain["whale_top_loser"] = losers[-1]  # 最末一个最负
    except Exception as e:
        print(f"[Morning/whale] ⚠️ {e}")

    return {"movers": movers, "headlines_en": headlines_en, "headlines_cn": headlines_cn,
            "trending": trending, "onchain": onchain}


def _fmt_whale_amt(d):
    """统一格式: +$173K / -$1.14M"""
    val = abs(d)
    sign = "+" if d >= 0 else "-"
    if val >= 1e6:
        return f"{sign}${val/1e6:.2f}M"
    elif val >= 1e3:
        return f"{sign}${val/1e3:.0f}K"
    else:
        return f"{sign}${val:.0f}"


def build_square_text_for_morning_brief(brief_text, onchain):
    """
    🆕 v30.14.10: 构造币安广场早报文案
    🆕 v30.14.28: Kings 重定义需求 - 不要 hashtag, 不要链接, 只要早报正文
       根因: 5/21 失败敏感词, 5/22 失败 Hashtag 超限
       (Haiku 自由发挥时正文里加了 # 标签, 加上 hardcode 6 个超限)
    规则:
      • 无 HTML 标签 (Square 不支持)
      • 无 TG 外链 / @提及 (合规 + Kings 要求)
      • 无 hashtag (Kings 要求, 历史触发 220094 超限)
      • 过滤 Haiku 正文里的 # 标签和 @ 提及 (Square 风控)
      • <800 字
    """
    today = datetime.now().strftime("%m-%d")
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][_utcnow().weekday()]

    # 🆕 v30.14.28: 过滤 Haiku 正文里的 hashtag 行和 @ 提及行
    # 用正则替换 #word 和 @word, 但保留正常文字
    import re as _re
    clean_brief = brief_text.strip()
    # 移除整行只有 hashtag 的行 (e.g. "#BTC #ETH #市场")
    clean_brief = _re.sub(r'^\s*(?:#\S+\s*)+$', '', clean_brief, flags=_re.MULTILINE)
    # 移除行内单独 hashtag (e.g. "BTC 涨 5% #BTC" → "BTC 涨 5%")
    clean_brief = _re.sub(r'\s*#\S+', '', clean_brief)
    # 移除 @ 提及 (e.g. "@币世赏金台")
    clean_brief = _re.sub(r'@\S+', '', clean_brief)
    # 清理多余空行
    clean_brief = _re.sub(r'\n{3,}', '\n\n', clean_brief).strip()

    lines = [
        f"📰 赏金哨·早报 · {today} {weekday_cn}",
        "",
        clean_brief,
        "",
    ]

    # 鲸群独家段
    have_whale = False
    whale_lines = ["🐋 鲸群昨日 (独家)"]
    winner = onchain.get("whale_top_winner")
    loser = onchain.get("whale_top_loser")
    if winner:
        wname = winner["whale"].get("name", winner.get("whale_id", "?"))
        amt = _fmt_whale_amt(winner["delta"])
        whale_lines.append(f"• {wname} 账户 {amt} ({winner['pct']:+.1f}%)")
        have_whale = True
    if loser:
        lname = loser["whale"].get("name", loser.get("whale_id", "?"))
        amt = _fmt_whale_amt(loser["delta"])
        whale_lines.append(f"• {lname} 账户 {amt} ({loser['pct']:+.1f}%)")
        have_whale = True

    n_d = onchain.get("sentinel_direct_24h", 0)
    n_s = onchain.get("sentinel_score_24h", 0)
    n_w = onchain.get("whale_alerts_24h", 0)
    n_o = onchain.get("whale_orange_24h", 0)
    n_r = onchain.get("whale_red_24h", 0)
    parts = []
    if n_d:
        parts.append(f"直推 {n_d}")
    if n_s:
        parts.append(f"综合 {n_s}")
    if n_w:
        parts.append(f"鲸鱼 {n_w}")
    if n_r:
        parts.append(f"红警 {n_r}")
    if n_o:
        parts.append(f"橙警 {n_o}")
    if parts:
        whale_lines.append(f"• 24h 频道: {' / '.join(parts)}")
        have_whale = True

    if have_whale:
        lines.extend(whale_lines)
        lines.append("")

    # 🆕 v30.14.28: Footer 砍掉 @提及 和 hashtag, 只留风险提示
    lines.append("⚠️ 仅供研究, 不构成交易建议")

    text = "\n".join(lines)
    # 安全长度截断 (Square 限 800 字, 留 50 缓冲)
    if len(text) > 750:
        # 🆕 v30.14.28: 截断也不加 hashtag
        text = text[:747] + "..."
    return text


def push_daily_morning_brief(conn):
    """每日 11:00 (UTC 3 = 北京 11) 推送早报. 24h 冷却由调用方用 last_morning_brief_date 控制"""
    if not ANTHROPIC_API_KEY:
        print("[Morning] ⚠️ 未配 ANTHROPIC_API_KEY, 跳过")
        return
    if os.getenv("MORNING_BRIEF_ENABLED", "1") != "1":
        print("[Morning] 总开关关闭, 跳过")
        return

    print("[Morning] 准备生成早报...")
    ctx = _gather_morning_context(conn)
    movers = ctx["movers"]
    headlines_en = ctx.get("headlines_en", [])
    headlines_cn = ctx.get("headlines_cn", [])
    trending = ctx.get("trending", [])
    onchain = ctx["onchain"]

    # 🆕 v30.14.14 P0 数据严格度校验: 必须有足够数据, 否则跳过避免 Haiku 幻觉
    # 通过条件 (满足任一):
    #   (a) gainers + losers ≥ 3 (有具体涨跌幅数字)
    #   (b) headlines_cn + headlines_en + trending ≥ 5 (有足够事件锚点)
    n_movers = len(movers.get("gainers", [])) + len(movers.get("losers", []))
    n_events = len(headlines_cn) + len(headlines_en) + len(trending)
    if n_movers < 3 and n_events < 5:
        print(f"[Morning] ⚠️ 数据严重不足 (movers={n_movers}, events={n_events}), 跳过推送防 Haiku 幻觉")
        return False  # 返回 False, 主循环不写 KV, 30min 后会重试

    # 构造给 Haiku 的 context
    lines = []
    # 主流币锚点 — 从 movers 全集里拎 BTC/ETH/SOL/BNB, 给 Haiku 写"市场氛围"用
    majors_data = []
    if movers.get("gainers") or movers.get("losers"):
        all_coins = (movers.get("gainers", []) + movers.get("losers", []))
        # 但 gainers/losers 都是排序后取 5, 主流币不一定在内. 这里 movers["all"] 才全
        pass
    if movers.get("all"):
        major_syms = ["btc", "eth", "sol", "bnb"]
        for sym in major_syms:
            for c in movers["all"]:
                if (c.get("symbol") or "").lower() == sym:
                    chg = c.get("price_change_percentage_24h", 0)
                    px = c.get("current_price", 0)
                    px_str = f"${px:,.0f}" if px >= 100 else f"${px:.2f}"
                    majors_data.append(f"  ${sym.upper()}: {chg:+.2f}%, {px_str}")
                    break
    if majors_data:
        lines.append("[主流币 24h]")
        lines.extend(majors_data)

    if movers.get("gainers"):
        lines.append("[Top 5 涨幅 24h]")
        for m in movers["gainers"]:
            sym = (m.get("symbol") or "").upper()
            name = m.get("name", "")
            chg = m.get("price_change_percentage_24h", 0)
            px = m.get("current_price", 0)
            px_str = f"${px:.4g}" if px < 1 else f"${px:,.2f}"
            lines.append(f"  ${sym} ({name}): {chg:+.1f}%, {px_str}")
    if movers.get("losers"):
        lines.append("[Top 5 跌幅 24h]")
        for m in movers["losers"]:
            sym = (m.get("symbol") or "").upper()
            name = m.get("name", "")
            chg = m.get("price_change_percentage_24h", 0)
            lines.append(f"  ${sym} ({name}): {chg:+.1f}%")
    # 🆕 中文头条 (优先, 不需翻译, 直接用)
    if headlines_cn:
        lines.append("[中文头条 — 可直接引用]")
        for h in headlines_cn:
            lines.append(f"  • {h['title']}")
    # 英文头条 (Cointelegraph 国际版)
    if headlines_en:
        lines.append("[英文头条 — 翻译生硬可跳过]")
        for h in headlines_en:
            lines.append(f"  • {h['title']}")
    # 🆕 v30.14.14: 当前热搜 (Coingecko Trending), 给 Haiku 当 "市场关注度" 锚点
    if trending:
        lines.append("[当前热搜 Top 7]")
        for t in trending:
            sym = t.get("symbol", "")
            name = t.get("name", "")
            rank_str = f", 市值 #{t.get('rank')}" if t.get("rank") else ""
            lines.append(f"  • ${sym} ({name}){rank_str}")
    context = "\n".join(lines)

    system = (
        "你是华语 Web3 频道编辑, 风格直接、有节奏、像 KOL 不像研报。"
        "用户是中文散户, 关心合约信号 / 鲸鱼动向 / 套利机会。"
        "禁止: 编造数字 / 写'建议买入卖出' / 用'重磅' '速看' 等营销词 / 加 emoji 过度堆砌 / "
        "使用任何 markdown 语法 (绝对禁止 ** 加粗、## 标题、* 斜体、--- 分隔线), 输出必须是纯文本。"
    )
    prompt = (
        f"过去 24 小时币圈数据如下:\n\n{context}\n\n"
        f"请用 200-300 字中文写「赏金哨·早报」的开头到「其他要紧的」结束部分, 要求:\n"
        f"1. 第一句话总结今天市场氛围 (只能用上面[主流币 24h]里的具体数字, 不许编)\n"
        f"2. 主线: 挑 1 个最值得说的事件展开 1 段 (引用具体币种和数字, 必须从上面数据来)\n"
        f"3. 「其他要紧的」: 列 3 条短讯, 每条 1 行, 必须含币种和数字\n"
        f"4. ⚠️ 严格禁止任何上面数据里没有的数字 (例如年跌幅、季度数据、市值排名等, 我没给的就不要写)\n"
        f"5. 如果某条头条翻译生硬, 直接跳过不用, 不要硬翻\n"
        f"6. 用词必须是标准书面汉语, 不要造词\n"
        f"7. 绝对禁止使用 markdown — 不要写 **xxx** / ##xxx / *xxx*\n"
        f"8. 输出只包含正文, 不要标题不要日期"
    )

    text = _call_haiku(prompt, max_tokens=600, system=system)
    if not text or len(text) < 80:
        print(f"[Morning] ❌ Haiku 返回空或过短 (len={len(text) if text else 0}), 跳过")
        return

    # 组装完整推送
    date_str = _utcnow().strftime("%Y-%m-%d")
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][_utcnow().weekday()]

    msg = f"📰 <b>赏金哨·早报</b>\n🗓️ {date_str} {weekday_cn}\n\n"
    msg += html.escape(text) + "\n\n"

    # 鲸群独家 (硬编码不靠 AI, 避免编数字)
    have_whale_section = False
    whale_lines = ["<b>🐋 鲸群昨日 (独家)</b>"]
    winner = onchain.get("whale_top_winner")
    loser = onchain.get("whale_top_loser")
    if winner:
        wname = winner["whale"].get("name", winner.get("whale_id", "?"))
        wemoji = winner["whale"].get("emoji", "🐋")
        amt = _fmt_whale_amt(winner["delta"])
        whale_lines.append(f"• {wemoji} {_esc(wname)} 账户 {amt} ({winner['pct']:+.1f}%)")
        have_whale_section = True
    if loser:
        lname = loser["whale"].get("name", loser.get("whale_id", "?"))
        lemoji = loser["whale"].get("emoji", "🐋")
        amt = _fmt_whale_amt(loser["delta"])
        whale_lines.append(f"• {lemoji} {_esc(lname)} 账户 {amt} ({loser['pct']:+.1f}%)")
        have_whale_section = True

    n_d = onchain["sentinel_direct_24h"]
    n_s = onchain["sentinel_score_24h"]
    n_w = onchain["whale_alerts_24h"]
    n_o = onchain["whale_orange_24h"]
    n_r = onchain["whale_red_24h"]
    parts = []
    if n_d:
        parts.append(f"直推 {n_d}")
    if n_s:
        parts.append(f"综合 {n_s}")
    if n_w:
        parts.append(f"鲸鱼 {n_w}")
    if n_r:
        parts.append(f"红警 {n_r}")
    if n_o:
        parts.append(f"橙警 {n_o}")
    if parts:
        whale_lines.append(f"• 24h 频道: {' / '.join(parts)}")
        have_whale_section = True

    if have_whale_section:
        msg += "\n".join(whale_lines) + "\n\n"

    msg += f"📲 开户: <code>{HL_REFERRAL}</code>\n\n"
    msg += "<i>—— AI 编辑摘要 + 链上独家数据</i>\n"
    msg += "<i>⚠️ 仅供研究, 不构成交易建议</i>"

    # 尾行标签
    try:
        # v30.14.10 hotfix: alert_type 用 "morning" (7 字符) 而非 "morning_brief" (13 字符), 避免被 make_tail 截到 "morning_brie"
        tail = tail_for_alert(
            "morning", date_str,
            v=int(n_d + n_w),
            r=len(headlines_en) + len(headlines_cn),
            src="cg+ct+cn+tr",
            extra={"date": date_str, "direct": n_d, "whale": n_w}
        )
        msg += f"\n{tail}"
    except Exception:
        pass

    try:
        send_tg(msg)
        print(f"[Morning] ✅ 已推送早报 (sentinel d={n_d}/s={n_s}, whale {n_w}, 中文 {len(headlines_cn)}, 英文 {len(headlines_en)}, trending {len(trending)}, gainers {len(movers.get('gainers', []))})")
        tg_pushed = True
    except Exception as e:
        print(f"[Morning] ❌ 推送失败: {e}")
        return False  # TG 都没推成功就不要发 Square 了, 主循环不写 KV, 30min 后重试

    # 🆕 v30.14.10: 同步发到 Binance Square (第二分发渠道)
    if not BINANCE_SQUARE_API_KEY:
        return tg_pushed
    try:
        # 防重复: 检查今天是否已推过 (跟 earn_daily 一致逻辑)
        already_posted = False
        try:
            row = conn.execute(
                "SELECT id FROM binance_square_posts "
                "WHERE symbol='__morning_brief__' AND result_code='000000' "
                "AND posted_at >= datetime('now', 'start of day') LIMIT 1"
            ).fetchone()
            already_posted = bool(row)
        except Exception:
            pass

        if already_posted:
            print("[Morning/Square] ⏭️ 今日早报已发广场, 跳过")
            return tg_pushed

        square_text = build_square_text_for_morning_brief(text, onchain)
        print(f"[Morning/Square] 📤 推送早报到广场 (字数 {len(square_text)})")
        publish_to_binance_square(square_text, symbol="__morning_brief__", score=0, conn=conn)
    except Exception as e:
        print(f"[Morning/Square] ❌ {e}")

    return tg_pushed


# ─────────────────────────────────────────────
# Agent #2: Upbit + Bithumb 上币哨兵
# ─────────────────────────────────────────────
# 数据源: Upbit Global API (公开免费, 无需 key)
#         Bithumb 公告页 (RSS)
# 间隔: 每次主扫描结束后调用一次 (≈30min/次)
def fetch_upbit_announcements():
    """拉 Upbit 最新公告. 返回 list of dicts: {id, title, url, created_at}"""
    try:
        r = requests.get(
            "https://api-manager.upbit.com/api/v1/announcements",
            params={"os": "web", "page": 1, "per_page": 20, "category": "trade"},
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
            timeout=10,
        )
        if r.status_code != 200:
            return []
        data = r.json().get("data", {})
        notices = data.get("notices", []) or data.get("list", []) or []
        results = []
        for n in notices:
            results.append({
                "id": str(n.get("id", "")),
                "title": n.get("title", ""),
                "url": f"https://upbit.com/service_center/notice?id={n.get('id', '')}",
                "created_at": n.get("first_listed_at", "") or n.get("listed_at", ""),
            })
        return results
    except Exception as e:
        print(f"[Upbit] ❌ {e}")
        return []


def _extract_tickers_from_title(title):
    """从公告标题里提取 ticker (括号里的大写字母 3-10 字符)"""
    if not title:
        return []
    # (BTC), (ETH), (KAITO) 这种格式
    matches = re.findall(r'\(([A-Z0-9]{2,10})\)', title)
    # 过滤明显非币的关键词
    blacklist = {"KRW", "BTC", "USDT", "USDC", "USD", "API", "FAQ", "KYC"}
    tickers = [m for m in matches if m not in blacklist]
    return tickers[:5]  # 最多 5 个


def _is_listing_announcement(title):
    """判断公告是否为上币类 (中韩英关键词)"""
    if not title:
        return False
    keywords = [
        # 韩文
        "상장", "마켓", "거래", "신규",
        # 英文
        "listing", "Listing", "LISTING", "new market", "New Market",
        "Digital Asset", "trading support", "Trading Support",
        # 中文
        "上线", "上币", "新增",
    ]
    return any(k in title for k in keywords)


def run_korea_listing_agent(conn):
    """🆕 v30.14: Upbit/Bithumb 上币哨兵 (中韩信息差)"""
    if os.getenv("KOREA_LISTING_ENABLED", "1") != "1":
        return

    notices = fetch_upbit_announcements()
    if not notices:
        return

    new_count = 0
    for n in notices:
        nid = n["id"]
        title = n["title"]
        if not nid or not title:
            continue
        if not _is_listing_announcement(title):
            continue
        # 已推过去重
        if is_alerted(conn, "upbit_listing", nid, hours=168):
            continue

        tickers = _extract_tickers_from_title(title)
        ticker_str = ", ".join(f"${t}" for t in tickers) if tickers else "未识别 ticker"

        # 短翻译 (Haiku 一句话, 失败也无所谓)
        cn_summary = ""
        if ANTHROPIC_API_KEY and len(title) > 5:
            tr = _call_haiku(
                f"用中文一句话翻译这个 Upbit 公告标题, 不超过 30 字, 直接给翻译不要解释:\n\n{title}",
                max_tokens=80,
            )
            if tr:
                cn_summary = tr.strip().replace("\n", " ")[:80]

        msg_lines = [
            f"🇰🇷 <b>Upbit 上币公告</b>",
            "",
            f"💎 标的: {ticker_str}",
            f"📋 {html.escape(title)[:200]}",
        ]
        if cn_summary:
            msg_lines.append(f"🌐 {html.escape(cn_summary)}")
        msg_lines.extend([
            f"🔗 {n['url']}",
            "",
            f"<i>⚡ 韩国大所上币历史平均 +15%~+130% 拉升</i>",
            f"<i>⚠️ 仅供研究, 实际反应取决于市场情绪</i>",
        ])
        try:
            send_tg("\n".join(msg_lines))
            mark_alerted(conn, "upbit_listing", nid)
            new_count += 1
            print(f"[Upbit] ✅ 推送: {title[:60]}")
            time.sleep(2)
        except Exception as e:
            print(f"[Upbit] ❌ 推送失败 {nid}: {e}")

    if new_count > 0:
        print(f"[Upbit] 本轮推送 {new_count} 条")


# ─────────────────────────────────────────────
# Agent #4: Token Unlock Cliff 哨兵 (DefiLlama)
# ─────────────────────────────────────────────
# 数据源: DefiLlama Emissions API (公开免费)
# 频率: 每 6h 一次. T-7d 预警 / T-24h 重点关注
def fetch_unlock_events():
    """拉 DefiLlama 解锁数据. 返回 list of {token, name, unlock_time, unlock_value_usd, fdv}
    只取未来 7 天内的"""
    try:
        r = requests.get(
            "https://api.llama.fi/emissions",
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if r.status_code != 200:
            return []
        data = r.json()
        if not isinstance(data, list):
            return []

        now_ts = int(time.time())
        cutoff_7d = now_ts + 7 * 24 * 3600
        events = []
        for entry in data:
            try:
                token = entry.get("token") or entry.get("symbol") or ""
                name = entry.get("name", "") or token
                # 取下一次解锁
                next_event = entry.get("nextEvent") or {}
                unlock_ts = next_event.get("timestamp", 0)
                if not isinstance(unlock_ts, (int, float)) or unlock_ts <= now_ts:
                    continue
                if unlock_ts > cutoff_7d:
                    continue
                # 解锁金额 (USD)
                unlock_value = next_event.get("noOfTokens", 0) * (entry.get("price", 0) or 0)
                fdv = entry.get("mcap", 0) or 0  # fully diluted
                circ = entry.get("circSupply", 0) or 1
                price = entry.get("price", 0) or 0
                circ_value = circ * price if price else 0
                # 阈值过滤: 解锁额 > $10M 或 解锁/流通 > 5%
                if unlock_value < 10_000_000:
                    if not circ_value or unlock_value / circ_value < 0.05:
                        continue
                events.append({
                    "token": token,
                    "name": name,
                    "unlock_time": int(unlock_ts),
                    "unlock_value_usd": unlock_value,
                    "fdv": fdv,
                    "circ_value_usd": circ_value,
                    "pct_of_circ": (unlock_value / circ_value * 100) if circ_value else 0,
                })
            except Exception:
                continue
        events.sort(key=lambda x: x["unlock_time"])
        return events
    except Exception as e:
        print(f"[Unlock] ❌ {e}")
        return []


def run_unlock_cliff_agent(conn):
    """T-7d 预警 / T-24h 重点关注"""
    if os.getenv("UNLOCK_AGENT_ENABLED", "1") != "1":
        return

    # 6h 冷却 (拉 API + 处理消耗)
    last_str = kv_get(conn, "unlock_agent_last_time")
    if last_str:
        try:
            last_t = datetime.strptime(last_str, "%Y-%m-%d %H:%M:%S")
            if (datetime.now() - last_t).total_seconds() < 6 * 3600:
                return
        except Exception:
            pass

    events = fetch_unlock_events()
    if not events:
        return
    kv_set(conn, "unlock_agent_last_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    now_ts = int(time.time())
    pushed = 0
    for ev in events:
        token = ev["token"]
        if not token:
            continue
        unlock_ts = ev["unlock_time"]
        hours_left = (unlock_ts - now_ts) / 3600

        # 决定档位
        if hours_left <= 24:
            tier = "24h"
            emoji = "🔴"
            tier_text = "T-24h 即将解锁"
        elif hours_left <= 168:  # 7d
            tier = "7d"
            emoji = "🟡"
            tier_text = "T-7d 预警"
        else:
            continue  # 超过 7d 不推

        # 去重: token + tier 组合, 168h 内只推一次
        key = f"unlock-{token}-{tier}"
        if is_alerted(conn, "unlock_cliff", key, hours=168):
            continue

        unlock_dt = datetime.fromtimestamp(unlock_ts)
        # 格式化数字
        def _fmt_usd(v):
            if v >= 1_000_000_000:
                return f"${v/1e9:.2f}B"
            if v >= 1_000_000:
                return f"${v/1e6:.1f}M"
            return f"${v:,.0f}"

        unlock_str = _fmt_usd(ev["unlock_value_usd"])
        circ_str = _fmt_usd(ev["circ_value_usd"]) if ev["circ_value_usd"] else "?"
        pct_str = f"{ev['pct_of_circ']:.1f}%" if ev["pct_of_circ"] else "?"

        msg_lines = [
            f"{emoji} <b>Unlock 警报 · {tier_text}</b>",
            "",
            f"🪙 ${token} ({html.escape(ev.get('name', token))})",
            f"📅 解锁时间: {unlock_dt.strftime('%m-%d %H:%M')} (剩 {hours_left:.1f}h)",
            f"💰 解锁价值: <b>{unlock_str}</b>",
            f"📊 占流通市值: <b>{pct_str}</b>",
            f"🔗 https://defillama.com/unlocks/{token.lower()}",
            "",
            f"<i>历史: 大额解锁日常见 -10% ~ -30% 抛压</i>",
            f"<i>⚠️ 仅供研究, 数据源 DefiLlama, 请自行验证</i>",
        ]
        try:
            send_tg("\n".join(msg_lines))
            mark_alerted(conn, "unlock_cliff", key)
            pushed += 1
            print(f"[Unlock] ✅ {tier} 推送: ${token} {unlock_str}")
            time.sleep(2)
        except Exception as e:
            print(f"[Unlock] ❌ {token}: {e}")

    if pushed > 0:
        print(f"[Unlock] 本轮推送 {pushed} 条")


# ─────────────────────────────────────────────
# 🆕 v30.14.2: /map 4 区分类 (3 维简化版)
# ─────────────────────────────────────────────
# 维度: OI 1h 涨幅 + 24h 涨幅 + 价格阻力距离
# 4 区:
#   🟢 入场窗口   - OI 强进 + 24h 温和 (0~+5%)
#   🟡 早发现雷达 - OI 极强进 + 24h 还没启动 (-3~+1%)
#   🟠 确认/回踩  - OI 持续进 + 24h 已涨 +5~+15%
#   🔴 风险区    - 24h ≥+20% 或 (≥+10% 但 OI 转负)

def classify_coin_for_map(coin, oi_1h_pct, change_24h):
    """返回: (zone, sort_key) 或 (None, 0) 如不属于任何区
    zone: 'enter' | 'early' | 'confirm' | 'risk'
    sort_key: 区内排序值 (越大越靠前)
    """
    if oi_1h_pct is None:
        oi_1h_pct = 0
    if change_24h is None:
        change_24h = 0

    # 🔴 风险区 (优先判定 — 已经过热的不进其他区)
    if change_24h >= 20:
        return "risk", change_24h  # 24h 涨幅排序
    if change_24h >= 10 and oi_1h_pct < 0:
        return "risk", abs(oi_1h_pct)  # OI 转负的 24h+10% 也是风险区

    # 🟡 早发现雷达 (OI 极强 + 价格还没启动)
    if oi_1h_pct >= 20 and -3 <= change_24h <= 1:
        return "early", oi_1h_pct  # OI 涨幅排序

    # 🟢 入场窗口 (OI 强 + 24h 温和)
    if oi_1h_pct >= 15 and 0 < change_24h <= 5:
        return "enter", oi_1h_pct

    # 🟠 确认/回踩 (OI 持续进 + 24h 已涨)
    if oi_1h_pct >= 10 and 5 < change_24h <= 15:
        return "confirm", oi_1h_pct

    return None, 0


def build_map_snapshot(conn):
    """构造 4 区快照. 返回 dict {zone: [(symbol, oi_1h_pct, change_24h, price), ...], ...}
    每区取 top 3 (按 sort_key)
    """
    bn_data = fetch_binance_perp_data()
    if not bn_data:
        return None

    zones = {"enter": [], "early": [], "confirm": [], "risk": []}

    for sym, d in bn_data.items():
        oi_1h_pct = get_sentinel_oi_change(conn, sym, "binance", hours_ago=1)
        if oi_1h_pct is None:
            continue
        change_24h = d.get("change_24h", 0) or 0
        zone, sort_key = classify_coin_for_map(sym, oi_1h_pct, change_24h)
        if not zone:
            continue
        zones[zone].append({
            "symbol": sym,
            "oi_1h": oi_1h_pct,
            "change_24h": change_24h,
            "price": d.get("price", 0),
            "_sort": sort_key,
        })

    # 每区取 top 3
    for z in zones:
        zones[z] = sorted(zones[z], key=lambda x: -x["_sort"])[:3]

    return zones


def _fmt_map_coin(c):
    """格式化单个币条目 - mobile friendly"""
    sym = c["symbol"]
    oi = c["oi_1h"]
    c24 = c["change_24h"]
    p = c["price"]
    if p < 0.01:
        p_str = f"${p:.6f}"
    elif p < 1:
        p_str = f"${p:.4f}"
    else:
        p_str = f"${p:,.4f}"
    return f"  ${sym} · OI 1h {oi:+.1f}% · 24h {c24:+.1f}% · {p_str}"


def render_map_message(zones):
    """生成 4 区消息. 空区显示 '暂无' """
    if not zones:
        return "❌ /map 数据加载失败 (Binance API 异常)"

    total = sum(len(zones[z]) for z in zones)
    if total == 0:
        return (
            "🗺️ <b>赏金哨地图 · 4 区快照</b>\n"
            "🌙 当前市场温和, 4 区均无候选\n\n"
            "<i>数据源: Binance 永续 · OI 1h 变化 + 24h 涨幅</i>\n"
            "<i>无候选 = 没有币同时满足任一区条件 (这是好事)</i>"
        )

    lines = ["🗺️ <b>赏金哨地图 · 4 区快照</b>", ""]

    # 🟢 入场窗口
    lines.append("🟢 <b>入场窗口</b> (OI 强 + 24h 温和)")
    if zones["enter"]:
        for c in zones["enter"]:
            lines.append(_fmt_map_coin(c))
    else:
        lines.append("  <i>暂无</i>")
    lines.append("")

    # 🟡 早发现雷达
    lines.append("🟡 <b>早发现雷达</b> (OI 极强, 价格未启动)")
    if zones["early"]:
        for c in zones["early"]:
            lines.append(_fmt_map_coin(c))
    else:
        lines.append("  <i>暂无</i>")
    lines.append("")

    # 🟠 确认/回踩
    lines.append("🟠 <b>确认/回踩候选</b> (OI 持续进 · 已涨)")
    if zones["confirm"]:
        for c in zones["confirm"]:
            lines.append(_fmt_map_coin(c))
    else:
        lines.append("  <i>暂无</i>")
    lines.append("")

    # 🔴 风险区
    lines.append("🔴 <b>风险区</b> (24h ≥+20% 或 OI 转负)")
    if zones["risk"]:
        for c in zones["risk"]:
            lines.append(_fmt_map_coin(c))
    else:
        lines.append("  <i>暂无</i>")
    lines.append("")

    lines.append("<i>📍 分类: OI 1h 变化 + 24h 涨幅</i>")
    lines.append("<i>⚠️ 4 区分类是观察工具, 不是跟单清单. 1h close 胜率参考 /winrate</i>")

    return "\n".join(lines)


def cmd_map(chat_id, args):
    """🆕 v30.14.2: /map 4 区快照 (公开命令, 任何用户可用)"""
    send_tg_reply(chat_id, "⏳ 加载 4 区快照中... (约 5-10 秒)")
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        zones = build_map_snapshot(conn)
        conn.close()
        msg = render_map_message(zones)
        send_tg_reply(chat_id, msg)
    except Exception as e:
        send_tg_reply(chat_id, f"❌ /map 失败: {str(e)[:200]}")
        print(f"[Map] cmd error: {e}")


# 🆕 v30.14.8: 延后注册 /map (cmd_map 在第 11264 行才定义, 但 COMMANDS 字典在第 2218 行就要用)
# 这是 v30.14.2 引入 /map 时的位置 bug, 修复方法: 字典初始化时不引用 cmd_map, 等 cmd_map 定义后再补登记
COMMANDS["/map"] = cmd_map  # v30.14.2: 4 区分类快照


def run_map_auto_push(conn):
    """🆕 v30.14.2: /map 自动推送到频道 (每 12h 一次)"""
    if os.getenv("MAP_AUTO_PUSH_ENABLED", "1") != "1":
        return

    # 12h 冷却
    last_str = kv_get(conn, "map_auto_last_time")
    if last_str:
        try:
            last_t = datetime.strptime(last_str, "%Y-%m-%d %H:%M:%S")
            elapsed_h = (datetime.now() - last_t).total_seconds() / 3600
            if elapsed_h < 12:
                return
        except Exception:
            pass

    print(f"[MapAuto] 触发 12h 自动推送...")
    zones = build_map_snapshot(conn)
    if zones is None:
        print(f"[MapAuto] ⚠️ 数据加载失败, 跳过")
        return

    total = sum(len(zones[z]) for z in zones)
    msg = render_map_message(zones)

    try:
        send_tg(msg)
        kv_set(conn, "map_auto_last_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print(f"[MapAuto] ✅ 已推送, 共 {total} 个币 (enter={len(zones['enter'])}, early={len(zones['early'])}, confirm={len(zones['confirm'])}, risk={len(zones['risk'])})")
    except Exception as e:
        print(f"[MapAuto] ❌ 推送失败: {e}")


def main():
    print("🚀 Bounty Monitor v30.14.34 启动 (/analyze prompt 升级, 教 Sonnet 历史)...")
    conn = init_db()

    # 🆕 v30.14.31: 启动时 init Paper Trading (让 admin 立刻收到欢迎)
    try:
        init_paper_trading_db(conn)
    except Exception as e:
        print(f"[Paper/Init] {e}")

    # 🆕 v30.14.31: 设置 TG bot menu bar (commands menu)
    try:
        setup_tg_bot_menu()
    except Exception as e:
        print(f"[BotMenu] {e}")

    # 启动 TG bot 命令监听 (后台线程)
    bot_thread = threading.Thread(target=tg_bot_poll_loop, daemon=True)
    bot_thread.start()

    # 🆕 v28.5: 启动鲸鱼快速通道线程 (每 5 分钟扫描, 清算时效性提升)
    whale_thread = threading.Thread(target=whale_fast_poll_loop, daemon=True)
    whale_thread.start()

    # 🆕 v30.1: 启动赏金哨快速通道线程 (10 分钟扫描, 匹配 Michill 频率)
    sentinel_thread = threading.Thread(target=sentinel_fast_poll_loop, daemon=True)
    sentinel_thread.start()

    first = True
    # 🆕 v30.12: last_daily_push 从 DB 读取 (重启后保留, 修复 redeploy 重发每日提醒)
    last_daily_push = None
    try:
        ldp_str = kv_get(conn, "last_daily_push")
        if ldp_str:
            last_daily_push = datetime.strptime(ldp_str, "%Y-%m-%d").date()
            print(f"[Main] 从 DB 恢复 last_daily_push={last_daily_push}")
    except Exception as e:
        print(f"[Main] last_daily_push 恢复失败: {e}")
    scan_count = 0

    while True:
        scan_count += 1
        print(f"\n{'='*50}")
        print(f"第 {scan_count} 次扫描...")

        # 1. 并发抓取所有数据源 (v26: 传入 conn 以记录 fetcher 成功率)
        all_b, errors, elapsed = run_all_fetchers(conn)

        # 1b. v25: 跨源聚类去重
        all_b = cluster_duplicates(all_b)

        # 更新 bot 共享数据 (v25 fix: 仅在非空时更新, 避免瞬时空状态)
        if all_b:
            with _data_lock:
                LATEST_DATA["all_b"] = all_b
                LATEST_DATA["last_scan"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
                LATEST_DATA["scan_count"] = scan_count

        # 2. TVL 异常监控
        tvl_alerts = fetch_tvl_anomalies(conn)
        send_tvl_alerts(tvl_alerts)

        # 2b. APY 变动追踪
        apy_alerts = check_apy_changes(conn, all_b)
        send_apy_alerts(apy_alerts)

        # 2c. 截止倒计时提醒
        check_deadline_countdowns(conn, all_b)

        # 2d. 稳定币流向
        stable_alerts = fetch_stablecoin_flows()
        send_stablecoin_alerts(conn, stable_alerts)

        # 2e. 新协议/Airdrop 追踪 (移到每日推送, 见下方)

        # 🆕 v25: 稳定币脱锚 (独立于流向)
        try:
            depeg_alerts = check_stablecoin_depeg(conn)
            send_depeg_alerts(depeg_alerts)
        except Exception as e:
            print(f"[Depeg] 主循环错误: {e}")

        # 🆕 v25+: 价格异动 (每次扫描都存快照, 4h 冷却防刷屏)
        # 价格异动优先 (包含最丰富的 OI/Funding 上下文)
        alerted_coins = set()
        try:
            price_alerts = check_price_anomalies(conn)
            send_price_alerts(price_alerts, conn)
            alerted_coins.update(a['symbol'] for a in price_alerts)
        except Exception as e:
            print(f"[Price] 主循环错误: {e}")

        # 🆕 v29.1: 信号战绩追推扫描 (4h/24h 后自动复盘信号准不准)
        try:
            price_followup_pushed = check_price_alert_followups(conn)
            if price_followup_pushed > 0:
                print(f"[PriceFollowup #{scan_count}] ✅ 推送 {price_followup_pushed} 条信号复盘")
            # 🆕 v30.14.27 D: SHORT/rebound/score 信号 24h 后自动复盘帖
            try:
                recap_pushed = check_24h_recap(conn)
                if recap_pushed > 0:
                    print(f"[Recap24h #{scan_count}] ✅ 推送 {recap_pushed} 条 24h 复盘")
            except Exception as e:
                print(f"[Recap24h] 主循环错误: {e}")
            # 🆕 v30.14.30: 4h alpha 复盘 (SHORT 黄金窗口)
            try:
                recap_4h_pushed = check_4h_alpha_recap(conn)
                if recap_4h_pushed > 0:
                    print(f"[Recap4h #{scan_count}] ✅ 推送 {recap_4h_pushed} 条 4h 复盘")
            except Exception as e:
                print(f"[Recap4h] 主循环错误: {e}")
            # 🆕 v30.14.32: Paper Trading 自动结算 (LONG 1h / SHORT 4h 时间窗 + 止盈止损)
            try:
                settled = settle_paper_positions(conn)
                if settled > 0:
                    print(f"[Settle #{scan_count}] ✅ 结算 {settled} 单纸上仓位")
            except Exception as e:
                print(f"[Settle] 主循环错误: {e}")
            # 🆕 v30.11: 1h FOMO 复盘 (≥3% 涨幅才推)
            try:
                fomo_pushed = check_fomo_followups(conn)
                if fomo_pushed > 0:
                    print(f"[FOMO #{scan_count}] ✅ 推送 {fomo_pushed} 条 1h 实战复盘")
            except Exception as e:
                print(f"[FOMO] 主循环错误: {e}")

            # 🆕 v30.14.12: 信号实时价格追踪 (±5%/-3%/1h 触发)
            try:
                tracker_pushed = check_signal_trackers(conn)
                if tracker_pushed > 0:
                    print(f"[Tracker #{scan_count}] ✅ 推送 {tracker_pushed} 条价格追踪")
            except Exception as e:
                print(f"[Tracker] 主循环错误: {e}")
        except Exception as e:
            print(f"[PriceFollowup] 主循环错误: {e}")

        # 🆕 v25: 资金费率异动 + OI 异动 (每 2 次扫描 1 次 = 1 小时)
        # 跳过已在价格异动中推送过的币种
        # 🆕 v28.6: OI/Funding 从 60 分钟提频到 30 分钟 (每次扫描都跑)
        try:
            funding_alerts = check_funding_rates(conn)
            funding_alerts = [a for a in funding_alerts if a['symbol'] not in alerted_coins]
            send_funding_alerts(funding_alerts, conn)
            alerted_coins.update(a['symbol'] for a in funding_alerts)
        except Exception as e:
            print(f"[Funding] 主循环错误: {e}")
        try:
            oi_alerts = check_oi_anomalies(conn)
            oi_alerts = [a for a in oi_alerts if a['symbol'] not in alerted_coins]
            send_oi_alerts(oi_alerts, conn)
        except Exception as e:
            print(f"[OI] 主循环错误: {e}")

        # 🆕 v28.5: 鲸鱼扫描已移到独立快速通道线程 (whale_fast_poll_loop), 每 5 分钟 1 次
        # (原本在主循环里 30 分钟 1 次, 清算预警时效性不够)

        # 🆕 v25: 跨链 APY 套利 (每 4 次扫描 1 次 = 2 小时)
        if scan_count % 4 == 0:
            try:
                arb_alerts = find_cross_chain_arb(all_b, conn)
                send_arb_alerts(arb_alerts)
            except Exception as e:
                print(f"[Arb] 主循环错误: {e}")

        # 🆕 v25: CEX 新币上线 + Snapshot 治理 (每 4 次扫描 1 次)
        if scan_count % 4 == 0:
            try:
                listing_alerts = fetch_binance_listings(conn)
                listing_alerts += fetch_okx_listings(conn)
                send_listing_alerts(listing_alerts)
            except Exception as e:
                print(f"[Listing] 主循环错误: {e}")
            try:
                snap_alerts = fetch_snapshot_proposals(conn)
                send_snapshot_alerts(snap_alerts)
            except Exception as e:
                print(f"[Snapshot] 主循环错误: {e}")

        # 3. 去重 (SQLite 持久化)
        new_b = []
        for b in all_b:
            if not is_seen(conn, b['u']):
                mark_seen(conn, b['u'], b.get('s', ''), b.get('t', ''))
                new_b.append(b)

        # 4. 新增高价值推送
        if not first:
            high_new = [b for b in new_b if b['v'] >= MIN_VALUE or
                        (is_defi(b) and b.get('apy', 0) >= 10)]
            for b in sorted(high_new, key=lambda x: x.get('apy', x['v']), reverse=True)[:5]:
                if is_defi(b):
                    # 🆕 v30.13.2: 风险过滤 — 不推 Risk≥7 (高/极高) 或 TVL<$500K (低流动性) 的 DeFi 池
                    # 修复: SPACEX-WSOL Risk 10/10 / TVL $158K 这种垃圾池被推到频道
                    risk = score_risk(b)
                    tvl = b.get('tvl', 0) or 0
                    if risk >= 7:
                        print(f"[NewDeFi] ⏭️ 跳过 {b.get('t', '?')}: Risk {risk}/10 过高")
                        continue
                    if tvl > 0 and tvl < 500_000:
                        print(f"[NewDeFi] ⏭️ 跳过 {b.get('t', '?')}: TVL ${tvl:,.0f} 流动性过低")
                        continue
                    msg = f"🆕 新增高收益 DeFi 机会!\n\n{fmt_defi(b)}"
                else:
                    msg = f"🆕 新增高价值 Bounty!\n\n{fmt_bounty(b)}"
                send_tg(msg)
                time.sleep(1)

        # 5. 首次启动报告
        if first:
            first = False
            push_initial_report(all_b, conn=conn)
            # 🆕 v28.3: 启动后立刻推首个 bounty digest (Top 5 + 黑客松分组)
            # 避免新订阅者关注后要等 3 小时才看到内容
            # 🆕 v30.12: 传入 conn 以让 fingerprint 持久化, 内容未变重启不重发
            try:
                time.sleep(2)  # 让 initial_report 先到
                push_bounty_digest(all_b, conn=conn)
            except Exception as e:
                print(f"[Initial Digest] 错误: {e}")

        # 6. 每日定时推送 (UTC 1点 = 北京 9点)
        now = datetime.now(timezone.utc)
        if now.hour >= 1 and (last_daily_push is None or last_daily_push != now.date()):
            last_daily_push = now.date()
            # 🆕 v30.12: 持久化 last_daily_push (重启后不重发)
            kv_set(conn, "last_daily_push", last_daily_push.strftime("%Y-%m-%d"))
            push_daily_digest(all_b, conn=conn)
            # 每日 Airdrop 追踪 (只推新协议)
            new_protos = fetch_new_protocols()
            send_airdrop_alerts(conn, new_protos)
            # 🆕 v27.2: 每日鲸鱼盈亏榜 (Top 5)
            try:
                push_whale_daily_pnl(conn)
            except Exception as e:
                print(f"[PnLDaily] 主循环错误: {e}")
            # 每周一发图表报告
            if now.weekday() == 0:
                generate_weekly_chart(conn, all_b)
                # 🆕 v30.5: 鲸鱼活跃度复核 (每周一 09:00 触发)
                try:
                    whale_health_check(conn)
                except Exception as e:
                    print(f"[WhaleHealth] 主循环错误: {e}")

        # 🆕 v30.14.10: 每日 11:00 早报 (UTC 3 = 北京 11)
        # 跟 9 点 PnLDaily 错开 2 小时, 避免同时刷屏
        # 🆕 v30.14.11: kv_set 移到 push 成功后, 防止推送失败但 KV 锁住整天
        if now.hour >= 3:
            last_morning = kv_get(conn, "last_morning_brief_date")
            today_str = now.date().strftime("%Y-%m-%d")
            if last_morning != today_str:
                try:
                    pushed = push_daily_morning_brief(conn)
                    # push_daily_morning_brief 内部成功才返回 True, 否则 None/False
                    if pushed:
                        kv_set(conn, "last_morning_brief_date", today_str)
                except Exception as e:
                    print(f"[Morning] 主循环错误: {e}")

        # 🆕 v30.14.29: 每天北京 08:00 (UTC 0:00) admin 私聊推 Alpha 报告
        # B+C 组合: 平日智能告警 (有变化才推), 周日完整周报
        if now.hour == 0:
            last_alpha = kv_get(conn, "last_alpha_briefing_date")
            today_str = now.date().strftime("%Y-%m-%d")
            if last_alpha != today_str:
                try:
                    push_daily_alpha_briefing(conn)
                    # 不管成功失败都标记 (推送跳过也算 "今天处理过了")
                    kv_set(conn, "last_alpha_briefing_date", today_str)
                except Exception as e:
                    print(f"[AlphaDaily] 主循环错误: {e}")

        # 🆕 v30.14.16: 每天 23:59 北京 (15:59 UTC) 抓一次订阅数落 KV (供 /growth 查日变化)
        # 跟早报错开, 一天 1 次, 失败静默
        if now.hour == 15:
            last_sub_snap = kv_get(conn, "last_sub_snapshot_date")
            today_str = now.date().strftime("%Y-%m-%d")
            if last_sub_snap != today_str:
                kv_set(conn, "last_sub_snapshot_date", today_str)
                try:
                    snapshot_subscriber_count()
                except Exception as e:
                    print(f"[Growth] 快照主循环错误: {e}")

        # 7. 定期清理旧数据
        if scan_count % 48 == 0:  # 约每24小时
            cleanup_old_data(conn, days=7)
            print("[DB] 已清理 7 天前的历史数据")

        # v30.10: 删除每 3 小时定推, 改为每天 09:00 + 启动时(带去重)
        # 旧逻辑: if scan_count % 6 == 0 and scan_count > 1: push_bounty_digest(all_b)

        # 8. 心跳推送 (每 12 次扫描 = 约 6 小时)
        if scan_count % 12 == 0:
            err_str = f"\n⚠️ 错误: {', '.join(errors)}" if errors else ""
            tvl_str = f"\n📉 TVL 报警: {len(tvl_alerts)} 个" if tvl_alerts else ""
            msg = (f"💓 心跳 #{scan_count} | {datetime.now().strftime('%H:%M')}\n"
                   f"📋 总: {len(all_b)} | 新: {len(new_b)} | ⏱️ {elapsed:.0f}s"
                   f"{tvl_str}{err_str}")
            send_tg(msg)

        # 🆕 v26: 哑巴失败检测 (每 12 次扫描 = 约 6 小时, 连续 24h 无数据才报警)
        if scan_count % 12 == 0 and scan_count > 12:
            try:
                droughts = check_fetcher_droughts(conn, hours=24, cooldown_hours=12)
                if droughts:
                    drought_msg = "🔕 哑巴失败告警 Silent Fetcher Failure\n\n"
                    drought_msg += "以下数据源连续 24h 返回 0 条 (可能已坏, 但没报错):\n\n"
                    for d in droughts:
                        drought_msg += f"• {d['name']}: 已静默 {d['hours']:.0f}h\n"
                    drought_msg += "\n💡 建议检查对应网站 HTML 结构是否变化"
                    send_tg(drought_msg)
            except Exception as e:
                print(f"[Drought] 检查错误: {e}")

        # 🆕 v30.14: Agent 三连 (每个独立 try/except, 一个挂不影响其他)
        try:
            run_korea_listing_agent(conn)
        except Exception as e:
            print(f"[Agent/Korea] 错误: {e}")

        try:
            run_unlock_cliff_agent(conn)
        except Exception as e:
            print(f"[Agent/Unlock] 错误: {e}")

        try:
            run_ai_brief_agent(conn)
        except Exception as e:
            print(f"[Agent/Brief] 错误: {e}")

        try:
            run_map_auto_push(conn)
        except Exception as e:
            print(f"[Agent/MapAuto] 错误: {e}")

        print(f"总计: {len(all_b)} | 新增: {len(new_b)} | 下次: {CHECK_INTERVAL//60}分钟")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
