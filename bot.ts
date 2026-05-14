/**
 * Meteora Router - DLMM Auto Rebalance Bot
 * V0.1 - Step 3: 完整自动化
 *
 * 功能:
 * - /scan 扫描白名单池子打分
 * - /open /close 手动开关仓
 * - /auto on/off 全自动开仓
 * - 自动 rebalance / claim / SL / 急跌保护
 * - /pause /resume /emergency 紧急刹车
 *
 * 安全:
 * - DRY_RUN 默认 true(env 关掉才发真实 tx)
 * - 第一次开仓需 TG 二次确认
 * - 单笔本金硬上限 MAX_POSITION_USD
 * - SL 触发自动 /pause
 */

import 'dotenv/config';
import {
  Connection,
  Keypair,
  PublicKey,
  Transaction,
  VersionedTransaction,
  ComputeBudgetProgram,
  sendAndConfirmTransaction,
} from '@solana/web3.js';
import { getAssociatedTokenAddress, getAccount } from '@solana/spl-token';
import { Telegraf, Markup } from 'telegraf';
import { Pool } from 'pg';
import bs58 from 'bs58';
import express from 'express';
import DLMM, { StrategyType } from '@meteora-ag/dlmm';
import BN from 'bn.js';
import Decimal from 'decimal.js';

// ============================================================
// 1. 配置
// ============================================================

const CONFIG = {
  RPC_URL: process.env.HELIUS_RPC_URL || 'https://api.mainnet-beta.solana.com',
  WALLET_PRIVATE_KEY: process.env.WALLET_PRIVATE_KEY || '',
  TG_BOT_TOKEN: process.env.TG_BOT_TOKEN || '',
  TG_OWNER_ID: parseInt(process.env.TG_OWNER_ID || '0'),
  DATABASE_URL: process.env.DATABASE_URL || '',

  // 安全
  DRY_RUN: (process.env.DRY_RUN || 'true').toLowerCase() === 'true',
  MAX_POSITION_USD: parseFloat(process.env.MAX_POSITION_USD || '200'),
  POOL_COOLDOWN_MINUTES: parseInt(process.env.POOL_COOLDOWN_MINUTES || '60'),
  MAX_OPEN_POSITIONS: parseInt(process.env.MAX_OPEN_POSITIONS || '2'),
  HARD_SL_PCT: parseFloat(process.env.HARD_SL_PCT || '10'),                 // V0.9: 默认 -10% 硬止损
  STOP_LOSS_WARN_PCT: parseFloat(process.env.STOP_LOSS_WARN_PCT || '7'),     // V0.9: -7% 软警告
  STOP_LOSS_CONSECUTIVE: parseInt(process.env.STOP_LOSS_CONSECUTIVE || '2'), // V0.9: 连续 N 次触发才执行,防抖
  POSITION_PCT: parseFloat(process.env.POSITION_PCT || '0.4'),               // V0.9: 自动开仓占钱包比例
  TOTAL_EXPOSURE_PCT: parseFloat(process.env.TOTAL_EXPOSURE_PCT || '0.7'),   // V0.9.1: 所有 open 仓位累计 ≤ 钱包此比例
  AUTO_RESUME_ENABLED: (process.env.AUTO_RESUME_ENABLED || 'true').toLowerCase() === 'true',  // V0.9.2
  AUTO_RESUME_MIN: parseInt(process.env.AUTO_RESUME_MIN || '60'),            // V0.9.2: 止损后等多少分钟尝试恢复
  EMERGENCY_DUMP_PCT: parseFloat(process.env.EMERGENCY_DUMP_PCT || '15'),

  // 策略默认
  RANGE_PCT: 10,
  REBALANCE_THRESHOLD: 0.45,                // 漂移触发阈值(保留作为兜底)
  REBALANCE_COOLDOWN_MS: 5 * 60_000,        // rebalance 后 5 分钟内同 pair 不再触发(防抖)
  SINGLE_SIDED_DUST_TOKEN: 1e-3,            // 某 token amount 低于此值 → 视为 100% single-sided
  // CLAIM_THRESHOLD_PCT 已废弃 (V0.8 Zip 1) — 现在统一走 #3 自动 Claim Agent
  CHECK_INTERVAL_MS: 30_000,
  SCAN_INTERVAL_MS: 30 * 60_000,     // 30min (V0.1 开发期紧凑值,V0.2 生产期可调到 4h)
  AUTO_TICK_EVERY_N_LOOPS: 4,        // 每 4 个 loop (~2 分钟) 触发 tickAutoOpen
  SWITCH_SCORE_DIFF: 20,             // 新池分高 20+ 才换仓

  // Tx
  PRIORITY_FEE_MICRO_LAMPORTS: 100_000,
  TX_MAX_RETRIES: 3,
  SWAP_SLIPPAGE_BPS: 100,                   // 池内 swap minOutAmount 滑点保护(1%)
  SWAP_MAX_IMPACT_PCT: parseFloat(process.env.SWAP_MAX_IMPACT_PCT || '5'),  // V0.10.4: 默认 3→5,env 可调
  PREFER_JUPITER: false,                    // true: 直接走 Jupiter; false: 先池内试探,失败再 fallback
  JUPITER_SLIPPAGE_BPS: 100,                // Jupiter swap 滑点(1%)

  // V2 健壮性
  MIN_REBALANCE_USD: 10,                    // rebalance 重建下限(低于此值放弃,避免 dust 仓位)
  MAX_REBALANCE_FAILS: 3,                   // 同 pair 连续 rebalance 失败上限,超过才 paused
  LOW_GAS_THRESHOLD_SOL: 0.05,              // SOL 余额低于此值发预警(0.05 SOL ≈ 几十笔 gas)
  GAS_CHECK_EVERY_N_LOOPS: 4,               // 每 N 个 loop 检查一次 SOL 余额(约 2 分钟)

  // V0.8 Zip 1: Agents
  ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY || '',
  ANTHROPIC_MODEL: 'claude-haiku-4-5-20251001',
  AUTO_CLAIM_ENABLED: (process.env.AUTO_CLAIM_ENABLED || 'true').toLowerCase() === 'true',
  AUTO_CLAIM_THRESHOLD_USD: parseFloat(process.env.AUTO_CLAIM_THRESHOLD_USD || '5'),
  AUTO_CLAIM_INTERVAL_MS: parseInt(process.env.AUTO_CLAIM_INTERVAL_MS || (6 * 3600_000).toString()),  // 6 小时
  HEALTH_CHECK_INTERVAL_MS: parseInt(process.env.HEALTH_CHECK_INTERVAL_MS || (24 * 3600_000).toString()),  // 24 小时
  MARKET_REGIME_INTERVAL_MS: parseInt(process.env.MARKET_REGIME_INTERVAL_MS || (4 * 3600_000).toString()), // 4 小时

  // API
  METEORA_API_HOSTS: [
    'https://dlmm.datapi.meteora.ag',
    'https://dlmm-api.meteora.ag',
  ],
  GECKOTERMINAL_API: 'https://api.geckoterminal.com/api/v2',
  JUP_API: process.env.JUP_API || 'https://lite-api.jup.ag/swap/v1',  // V0.10.4: v6 已 deprecated (Sep 2025) → 迁移 lite-api

  PORT: parseInt(process.env.PORT || '3000'),
};

// 已知 token mint
const SOL_MINT = 'So11111111111111111111111111111111111111112';
const USDC_MINT = 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v';
const USDT_MINT = 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB';

const KNOWN_TOKENS: Record<string, { symbol: string; decimals: number }> = {
  [SOL_MINT]:  { symbol: 'SOL',  decimals: 9 },
  [USDC_MINT]: { symbol: 'USDC', decimals: 6 },
  [USDT_MINT]: { symbol: 'USDT', decimals: 6 },
};

// 白名单 token mint(只允许这些 token 进入候选池)
const WHITELIST_MINTS = new Set([SOL_MINT, USDC_MINT, USDT_MINT]);

// 候选池子(V0.1 硬编码主流池;/discover 命令会自动扩充)
// 这些是 SOL/USDC、SOL/USDT、USDC/USDT 不同 bin_step 的真实池子
const CANDIDATE_POOLS_DEFAULT: string[] = [
  'BGm1tav58oGcsQJehL9WXBFXF7D27vZsKefj4xJKD5Y', // SOL/USDC bin_step 10
  '5rCf1DM8LjKTw4YqhnoLcngyZYeNnQqztScTogYHAS6', // SOL/USDC active pool (Pool Age 2y+)
  'ARwi1S4DaiTG5DX7S4M4ZsrXqpMD1MrTmbu9ue2tpmEq', // USDC/USDT (SDK 文档示例)
];

// ============================================================
// 2. 全局状态
// ============================================================

interface RuntimeState {
  paused: boolean;          // /pause 状态
  autoTrading: boolean;     // 自动开仓开关
  firstOpenConfirmed: boolean; // 首次开仓二次确认状态
  rebalancing: boolean;     // V2.3: rebalance 进行中(防 tickAutoOpen 并发触发开仓)
  autoResumablePausedAt: number; // V0.9.2: 止损/rebalance失败导致的 paused 时间戳(0=非此原因)
  autoResumeReason: string;      // V0.9.2: 给智能恢复显示用的人话原因
  pendingConfirmation: null | {
    type: 'open';
    lbPair: string;
    amountUsd: number;
    expiresAt: number;
  };
  lastScanTs: number;
  candidatePools: string[];
}

const state: RuntimeState = {
  paused: false,
  autoTrading: false,
  firstOpenConfirmed: false,
  rebalancing: false,
  autoResumablePausedAt: 0,
  autoResumeReason: '',
  pendingConfirmation: null,
  lastScanTs: 0,
  candidatePools: [...CANDIDATE_POOLS_DEFAULT],
};

// ============================================================
// 3. 初始化
// ============================================================

function loadKeypair(): Keypair {
  if (!CONFIG.WALLET_PRIVATE_KEY) throw new Error('WALLET_PRIVATE_KEY not set');
  if (CONFIG.WALLET_PRIVATE_KEY.startsWith('[')) {
    return Keypair.fromSecretKey(Uint8Array.from(JSON.parse(CONFIG.WALLET_PRIVATE_KEY)));
  }
  return Keypair.fromSecretKey(bs58.decode(CONFIG.WALLET_PRIVATE_KEY));
}

const wallet = loadKeypair();
const connection = new Connection(CONFIG.RPC_URL, 'confirmed');
const bot = new Telegraf(CONFIG.TG_BOT_TOKEN);

const db = new Pool({
  connectionString: CONFIG.DATABASE_URL,
  ssl: CONFIG.DATABASE_URL.includes('railway.app') || CONFIG.DATABASE_URL.includes('rlwy.net')
    ? { rejectUnauthorized: false }
    : false,
  max: 5,
  idleTimeoutMillis: 30_000,
});

console.log(`🤖 Wallet: ${wallet.publicKey.toBase58()}`);
console.log(`⚠️  DRY_RUN: ${CONFIG.DRY_RUN}`);

// ============================================================
// 4. 工具函数
// ============================================================

function sleep(ms: number) {
  return new Promise(r => setTimeout(r, ms));
}

async function retry<T>(fn: () => Promise<T>, n = 3, delay = 1000): Promise<T> {
  let lastErr: any;
  for (let i = 0; i < n; i++) {
    try {
      return await fn();
    } catch (e: any) {
      lastErr = e;
      if (i < n - 1) await sleep(delay * (i + 1));
    }
  }
  throw lastErr;
}

function tokenSymbol(mint: string): string {
  return KNOWN_TOKENS[mint]?.symbol || `${mint.slice(0, 4)}...`;
}

function fmtUsd(n?: number): string {
  if (n === undefined || isNaN(n)) return 'N/A';
  return `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function fmtPct(n?: number): string {
  if (n === undefined || isNaN(n)) return 'N/A';
  return `${n.toFixed(2)}%`;
}

function escHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ============================================================
// 5. 数据库
// ============================================================

async function initDb() {
  await db.query(`
    CREATE TABLE IF NOT EXISTS events (
      id SERIAL PRIMARY KEY,
      type TEXT NOT NULL,
      payload JSONB,
      ts TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts DESC);
    CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);

    CREATE TABLE IF NOT EXISTS positions (
      id SERIAL PRIMARY KEY,
      position_pk TEXT UNIQUE NOT NULL,
      lb_pair TEXT NOT NULL,
      pair_name TEXT,
      strategy TEXT,
      min_bin_id INT,
      max_bin_id INT,
      open_price NUMERIC,
      open_token_x_amount NUMERIC,
      open_token_y_amount NUMERIC,
      open_value_usd NUMERIC,
      status TEXT NOT NULL DEFAULT 'open',
      opened_at TIMESTAMPTZ DEFAULT NOW(),
      closed_at TIMESTAMPTZ,
      fees_claimed_usd NUMERIC DEFAULT 0,
      il_realized_usd NUMERIC DEFAULT 0,
      meta JSONB DEFAULT '{}'::jsonb
    );
    CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
    CREATE INDEX IF NOT EXISTS idx_positions_lb_pair ON positions(lb_pair);

    CREATE TABLE IF NOT EXISTS tx_logs (
      id SERIAL PRIMARY KEY,
      position_id INT REFERENCES positions(id) ON DELETE SET NULL,
      tx_sig TEXT,
      action TEXT NOT NULL,
      success BOOLEAN DEFAULT FALSE,
      error TEXT,
      payload JSONB,
      ts TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_tx_logs_position ON tx_logs(position_id);
    CREATE INDEX IF NOT EXISTS idx_tx_logs_ts ON tx_logs(ts DESC);

    CREATE TABLE IF NOT EXISTS pool_metrics (
      id SERIAL PRIMARY KEY,
      lb_pair TEXT NOT NULL,
      active_bin_id INT,
      active_price NUMERIC,
      tvl_usd NUMERIC,
      volume_24h_usd NUMERIC,
      fee_24h_usd NUMERIC,
      fee_apr NUMERIC,
      score NUMERIC,
      ts TIMESTAMPTZ DEFAULT NOW()
    );
    -- migration: 旧表可能没有 score 列
    ALTER TABLE pool_metrics ADD COLUMN IF NOT EXISTS score NUMERIC;
    CREATE INDEX IF NOT EXISTS idx_pool_metrics_pair_ts ON pool_metrics(lb_pair, ts DESC);

    CREATE TABLE IF NOT EXISTS candidate_pools (
      lb_pair TEXT PRIMARY KEY,
      added_at TIMESTAMPTZ DEFAULT NOW(),
      enabled BOOLEAN DEFAULT TRUE,
      disabled_reason TEXT
    );
    -- migration: 加 disabled_reason 列(用于自动禁用坏池子)
    ALTER TABLE candidate_pools ADD COLUMN IF NOT EXISTS disabled_reason TEXT;

    -- V3: PnL 损益账本(每次 close/rebalance 记一行)
    CREATE TABLE IF NOT EXISTS pnl_history (
      id SERIAL PRIMARY KEY,
      position_pk TEXT NOT NULL,
      pair_name TEXT NOT NULL,
      lb_pair TEXT NOT NULL,
      open_value_usd NUMERIC(18,4) NOT NULL,
      close_value_usd NUMERIC(18,4) NOT NULL,
      pnl_usd NUMERIC(18,4) NOT NULL,
      pnl_pct NUMERIC(10,4) NOT NULL,
      hold_minutes INT NOT NULL,
      reason TEXT NOT NULL,
      closed_at TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_pnl_pair ON pnl_history(pair_name, closed_at DESC);
    CREATE INDEX IF NOT EXISTS idx_pnl_closed ON pnl_history(closed_at DESC);

    -- V0.10: 账户维度 baseline (用户手动设定的初始本金)
    CREATE TABLE IF NOT EXISTS account_settings (
      key TEXT PRIMARY KEY,
      value NUMERIC(18,4),
      updated_at TIMESTAMPTZ DEFAULT NOW(),
      note TEXT
    );
  `);
  // seed default candidates
  for (const addr of CANDIDATE_POOLS_DEFAULT) {
    await db.query(
      `INSERT INTO candidate_pools(lb_pair) VALUES($1) ON CONFLICT DO NOTHING`,
      [addr]
    );
  }
  console.log('[db] schema 已就绪 (Phase 2A.5 hold_minutes + V3 pnl_history)');
}

async function logEvent(type: string, payload: any = {}) {
  try {
    await db.query('INSERT INTO events(type, payload) VALUES($1, $2)', [type, payload]);
  } catch (e: any) {
    console.error(`Failed to log event: ${e.message}`);
  }
}

async function logTx(positionId: number | null, txSig: string | null, action: string, success: boolean, error: string | null = null, payload: any = {}) {
  try {
    await db.query(
      `INSERT INTO tx_logs(position_id, tx_sig, action, success, error, payload) VALUES($1,$2,$3,$4,$5,$6)`,
      [positionId, txSig, action, success, error, payload]
    );
  } catch (e: any) {
    console.error(`Failed to log tx: ${e.message}`);
  }
}

async function loadCandidatePools(): Promise<string[]> {
  try {
    const r = await db.query<{ lb_pair: string }>(
      `SELECT lb_pair FROM candidate_pools WHERE enabled = TRUE`
    );
    return r.rows.map(x => x.lb_pair);
  } catch {
    return [...CANDIDATE_POOLS_DEFAULT];
  }
}

// ============================================================
// 6. 通知
// ============================================================

async function notify(msg: string) {
  console.log(`[NOTIFY] ${msg.replace(/<[^>]+>/g, '').slice(0, 200)}`);
  if (CONFIG.TG_OWNER_ID) {
    try {
      await bot.telegram.sendMessage(CONFIG.TG_OWNER_ID, msg, { parse_mode: 'HTML' });
    } catch (e: any) {
      console.error(`Failed to send TG: ${e.message}`);
      // V0.9.6: HTML 解析失败时降级为纯文本重发,不让通知丢失
      if (e.message?.includes("can't parse entities")) {
        try {
          const plain = msg.replace(/<\/?[a-zA-Z]+>/g, '').replace(/<code>|<\/code>/g, '');
          await bot.telegram.sendMessage(CONFIG.TG_OWNER_ID, '[降级] ' + plain);
        } catch (e2: any) {
          console.error(`fallback plain text also failed: ${e2.message}`);
        }
      }
    }
  }
}

/**
 * V0.9.6: HTML 转义 — 用于把 LLM 输出 / 用户输入塞进 HTML parse_mode 消息时
 * 防止 <3% 这种字符被当成 HTML 标签起始
 */
function escapeHtml(s: string): string {
  if (!s) return '';
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ============================================================
// 7. Token & Price 服务
// ============================================================

const priceCache = new Map<string, { price: number; ts: number }>();

// SOL/USDC 价格参考池(用于读链上 SOL 价格)
const SOL_PRICE_REFERENCE_POOL = 'BGm1tav58oGcsQJehL9WXBFXF7D27vZsKefj4xJKD5Y';

let solPriceCache = { price: 0, ts: 0 };

/**
 * 从链上 DLMM 池子读 SOL 价格
 * 完全不依赖 HTTP API,只走 Solana RPC,稳定可靠
 */
async function getSolPriceOnchain(): Promise<number> {
  if (Date.now() - solPriceCache.ts < 30_000 && solPriceCache.price > 0) {
    return solPriceCache.price;
  }
  try {
    const dlmm = await DLMM.create(connection, new PublicKey(SOL_PRICE_REFERENCE_POOL));
    const activeBin = await dlmm.getActiveBin();
    const price = parseFloat(dlmm.fromPricePerLamport(Number(activeBin.price)));
    if (price > 0 && price < 10000) { // sanity check
      solPriceCache = { price, ts: Date.now() };
      return price;
    }
  } catch (e: any) {
    console.error(`getSolPriceOnchain failed: ${e.message}`);
  }
  return 0;
}

async function getTokenPriceUsd(mint: string): Promise<number> {
  if (mint === USDC_MINT || mint === USDT_MINT) return 1;

  // SOL: 优先链上 DLMM 读
  if (mint === SOL_MINT) {
    const onchain = await getSolPriceOnchain();
    if (onchain > 0) return onchain;
    // 实在不行才走 HTTP
  }

  const cached = priceCache.get(mint);
  if (cached && Date.now() - cached.ts < 30_000) return cached.price;
  // Jupiter price API (备用,Railway 上可能 403)
  try {
    const r = await fetch(`${CONFIG.JUP_API}/quote?inputMint=${mint}&outputMint=${USDC_MINT}&amount=${10 ** 9}&slippageBps=50`, {
      signal: AbortSignal.timeout(3000),
    });
    if (r.ok) {
      const d: any = await r.json();
      const price = parseFloat(d.outAmount) / 1e6;
      if (price > 0 && !isNaN(price)) {
        priceCache.set(mint, { price, ts: Date.now() });
        return price;
      }
    }
  } catch (e: any) {
    console.error(`getTokenPriceUsd Jupiter failed: ${e.message}`);
  }
  // fallback
  if (mint === SOL_MINT) {
    console.log('⚠️ SOL price fallback to $80 (both on-chain and Jupiter failed)');
    return 80;
  }
  return 0;
}

/**
 * 读取钱包某 SPL token 余额(UI 单位,已除 decimals)
 */
async function getSplBalance(mint: string, decimals: number): Promise<number> {
  try {
    const ata = await getAssociatedTokenAddress(new PublicKey(mint), wallet.publicKey);
    const acc = await getAccount(connection, ata);
    return Number(acc.amount) / Math.pow(10, decimals);
  } catch {
    // ATA 不存在 = 余额 0
    return 0;
  }
}

/**
 * 钱包总 USD 价值快照(SOL + USDC + USDT,扣除 gas 储备)
 */
interface WalletSnapshot {
  solBalance: number;
  solPrice: number;
  solUsd: number;
  usdcBalance: number;
  usdtBalance: number;
  gasReserveSol: number;
  totalUsableUsd: number;
}

async function getWalletSnapshot(): Promise<WalletSnapshot> {
  const lamports = await connection.getBalance(wallet.publicKey);
  const solBalance = lamports / 1e9;
  const solPrice = await getTokenPriceUsd(SOL_MINT);
  const usdcBalance = await getSplBalance(USDC_MINT, 6);
  const usdtBalance = await getSplBalance(USDT_MINT, 6);

  // 留 0.1 SOL 给 gas + rent
  // - gas: ~0.001 SOL/tx
  // - position account rent: ~0.057 SOL(关仓退回)
  // - WSOL ATA rent: ~0.002 SOL
  // - bin array rent (if needed): ~0.07 SOL
  // 0.1 SOL 是安全 buffer,实际 rent 占用关仓时退回
  const gasReserveSol = 0.1;
  const usableSol = Math.max(0, solBalance - gasReserveSol);
  const solUsd = usableSol * solPrice;
  const totalUsableUsd = solUsd + usdcBalance + usdtBalance;

  console.log(`[wallet] SOL=${solBalance.toFixed(4)} (price=$${solPrice.toFixed(2)}) USDC=${usdcBalance.toFixed(2)} USDT=${usdtBalance.toFixed(2)} usable=$${totalUsableUsd.toFixed(2)}`);

  return { solBalance, solPrice, solUsd, usdcBalance, usdtBalance, gasReserveSol, totalUsableUsd };
}

// ============================================================
// 8. DLMM 读取层
// ============================================================

interface PoolInfo {
  address: string;
  pairName: string;
  tokenXMint: string;
  tokenYMint: string;
  tokenXSymbol: string;
  tokenYSymbol: string;
  tokenXDecimals: number;
  tokenYDecimals: number;
  binStep: number;
  baseFeePct: number;
  baseFactor: number;
  activeBinId: number;
  activePrice: number;
  reserveX: number;
  reserveY: number;
  tvlUsd?: number;
  volume24hUsd?: number;
  fees24hUsd?: number;
  feeApr?: number;
  dataSource?: string;
}

interface PositionInfo {
  positionPk: string;
  lbPair: string;
  pairName: string;
  binStep: number;
  activeBinId: number;
  activePrice: number;
  minBinId: number;
  maxBinId: number;
  inRange: boolean;
  rangeWidthPct: number;
  totalXAmount: string;
  totalYAmount: string;
  totalXAmountFloat: number;
  totalYAmountFloat: number;
  unclaimedFeeX: string;
  unclaimedFeeY: string;
  unclaimedFeeXFloat: number;
  unclaimedFeeYFloat: number;
  tokenXSymbol: string;
  tokenYSymbol: string;
  tokenXMint: string;
  tokenYMint: string;
}

/**
 * 计算 DLMM 池子的 base fee 百分比
 *
 * 官方 IDL 公式 (lbPair.parameters):
 *   base_fee_rate = base_factor * bin_step * 10 * 10^base_fee_power_factor
 *   FEE_PRECISION = 1e9 (即 base_fee_rate 的单位是 1e-9)
 *
 * 例验证:
 *   base_factor=10000, bin_step=10, power=0 → 0.1%
 *   base_factor=10000, bin_step=20, power=0 → 0.2%
 *   base_factor=10000, bin_step=100, power=0 → 1.0%
 */
function calcBaseFeePct(baseFactor: number, binStep: number, powerFactor: number = 0): number {
  return (baseFactor * binStep * 10 * Math.pow(10, powerFactor)) / 1e9 * 100;
}

// ============================================================
// 8b. 链上 Swap Event 解析器 (V0.1.1)
// ============================================================
//
// Meteora DLMM program emits "Swap" anchor event in tx logs as:
//   Program data: <base64-encoded-bytes>
// where bytes = [8-byte event discriminator] + [Borsh-encoded fields]
//
// Swap event schema (from IDL):
//   lb_pair: pubkey (32)
//   from: pubkey (32)
//   start_bin_id: i32 (4)
//   end_bin_id: i32 (4)
//   amount_in: u64 (8)
//   amount_out: u64 (8)
//   swap_for_y: bool (1)
//   fee: u64 (8)
//   protocol_fee: u64 (8)
//   fee_bps: u128 (16)
//   host_fee: u64 (8)
//
// Total: 8 (disc) + 32 + 32 + 4 + 4 + 8 + 8 + 1 + 8 + 8 + 16 + 8 = 137 bytes
//
// 我们手写 decoder 避开 Anchor BorshCoder 对 IDL 严格性问题。

const METEORA_PROGRAM_ID = 'LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo';
const SWAP_EVENT_DISCRIMINATOR = Buffer.from([81, 108, 227, 190, 205, 208, 10, 196]);

interface DlmmSwapEvent {
  lbPair: string;
  from: string;
  startBinId: number;
  endBinId: number;
  amountIn: bigint;
  amountOut: bigint;
  swapForY: boolean;
  fee: bigint;
  protocolFee: bigint;
  hostFee: bigint;
}

/**
 * 从 tx logs 中找 Swap event 并 decode
 */
function parseSwapEventFromLogs(logs: string[]): DlmmSwapEvent[] {
  const events: DlmmSwapEvent[] = [];
  for (const log of logs) {
    if (!log.startsWith('Program data: ')) continue;
    let data: Buffer;
    try {
      data = Buffer.from(log.slice('Program data: '.length), 'base64');
    } catch {
      continue;
    }
    if (data.length < 137) continue;
    if (!data.slice(0, 8).equals(SWAP_EVENT_DISCRIMINATOR)) continue;

    let off = 8;
    const lbPair = new PublicKey(data.slice(off, off + 32)).toBase58(); off += 32;
    const from = new PublicKey(data.slice(off, off + 32)).toBase58(); off += 32;
    const startBinId = data.readInt32LE(off); off += 4;
    const endBinId = data.readInt32LE(off); off += 4;
    const amountIn = data.readBigUInt64LE(off); off += 8;
    const amountOut = data.readBigUInt64LE(off); off += 8;
    const swapForY = data.readUInt8(off) === 1; off += 1;
    const fee = data.readBigUInt64LE(off); off += 8;
    const protocolFee = data.readBigUInt64LE(off); off += 8;
    off += 16;  // skip fee_bps (u128)
    const hostFee = data.readBigUInt64LE(off); off += 8;

    events.push({ lbPair, from, startBinId, endBinId, amountIn, amountOut, swapForY, fee, protocolFee, hostFee });
  }
  return events;
}

interface OnchainFeeStats {
  fees24hUsd: number;
  volume24hUsd: number;
  feeApr: number | null;
  swapCount: number;
  source: 'onchain';
}

// 缓存:lbPair → { stats, ts }
const onchainFeeCache = new Map<string, { stats: OnchainFeeStats; ts: number }>();
const ONCHAIN_FEE_CACHE_MS = 30 * 60_000;  // 30 min

/**
 * 从链上 swap events 计算池子过去 N 小时的真实 fee + volume
 *
 * 方法:getSignaturesForAddress 拿 N 小时内 tx → getTransactions 批量解析 → 累加 fee
 *
 * @param lbPair pool address
 * @param tvlUsd 池子 TVL (用于算 APR)
 * @param tokenXPrice X token 美元价
 * @param tokenYPrice Y token 美元价
 * @param tokenXDec X 精度
 * @param tokenYDec Y 精度
 * @param hours 回看时长(默认 24h)
 */
async function getOnchainFeeStats(
  lbPair: string,
  tvlUsd: number,
  tokenXPrice: number,
  tokenYPrice: number,
  tokenXDec: number,
  tokenYDec: number,
  hours: number = 24,
): Promise<OnchainFeeStats> {

  // 缓存
  const cached = onchainFeeCache.get(lbPair);
  if (cached && Date.now() - cached.ts < ONCHAIN_FEE_CACHE_MS) {
    return cached.stats;
  }

  const cutoffTs = Math.floor(Date.now() / 1000) - hours * 3600;
  const lbPairPk = new PublicKey(lbPair);

  // 1. 拿过去 N 小时的 tx signatures (Helius 默认上限 1000 per call)
  let allSigs: any[] = [];
  let beforeSig: string | undefined = undefined;
  let pages = 0;
  while (pages < 5) {
    const batch: any = await retry(() => connection.getSignaturesForAddress(
      lbPairPk,
      { limit: 1000, before: beforeSig },
      'confirmed',
    ), 2, 500);
    if (!batch || batch.length === 0) break;
    pages++;
    let stop = false;
    for (const s of batch) {
      if ((s.blockTime ?? 0) < cutoffTs) { stop = true; break; }
      allSigs.push(s);
    }
    if (stop) break;
    if (batch.length < 1000) break;
    beforeSig = batch[batch.length - 1].signature;
  }

  if (allSigs.length === 0) {
    const empty: OnchainFeeStats = { fees24hUsd: 0, volume24hUsd: 0, feeApr: null, swapCount: 0, source: 'onchain' };
    onchainFeeCache.set(lbPair, { stats: empty, ts: Date.now() });
    return empty;
  }

  // 2. 分批 getTransaction (limit 限速)
  const BATCH_SIZE = 25;
  let totalFeeXRaw = 0n;
  let totalFeeYRaw = 0n;
  let totalAmountInXRaw = 0n;
  let totalAmountInYRaw = 0n;
  let swapCount = 0;

  for (let i = 0; i < allSigs.length; i += BATCH_SIZE) {
    const batch = allSigs.slice(i, i + BATCH_SIZE);
    const txs = await retry(() => connection.getTransactions(
      batch.map(s => s.signature),
      { maxSupportedTransactionVersion: 0, commitment: 'confirmed' },
    ), 2, 500);

    for (const tx of (txs || [])) {
      const logs = tx?.meta?.logMessages;
      if (!logs) continue;
      const events = parseSwapEventFromLogs(logs);
      for (const ev of events) {
        if (ev.lbPair !== lbPair) continue;
        swapCount++;
        // swap_for_y=true 表示 X→Y, fee 是 input token (X) 计价
        if (ev.swapForY) {
          totalFeeXRaw += ev.fee;
          totalAmountInXRaw += ev.amountIn;
        } else {
          totalFeeYRaw += ev.fee;
          totalAmountInYRaw += ev.amountIn;
        }
      }
    }
    await sleep(150);  // 简单 rate limit
  }

  // 3. 转 USD
  const feeXUsd = (Number(totalFeeXRaw) / Math.pow(10, tokenXDec)) * tokenXPrice;
  const feeYUsd = (Number(totalFeeYRaw) / Math.pow(10, tokenYDec)) * tokenYPrice;
  const fees24hUsd = feeXUsd + feeYUsd;

  const volXUsd = (Number(totalAmountInXRaw) / Math.pow(10, tokenXDec)) * tokenXPrice;
  const volYUsd = (Number(totalAmountInYRaw) / Math.pow(10, tokenYDec)) * tokenYPrice;
  const volume24hUsd = volXUsd + volYUsd;

  // 按 hours 比例外推到 24h
  const scale = 24 / hours;
  const fees24h = fees24hUsd * scale;
  const vol24h = volume24hUsd * scale;

  const feeApr = (tvlUsd > 0) ? (fees24h * 365 / tvlUsd) * 100 : null;

  const stats: OnchainFeeStats = {
    fees24hUsd: fees24h,
    volume24hUsd: vol24h,
    feeApr,
    swapCount,
    source: 'onchain',
  };
  onchainFeeCache.set(lbPair, { stats, ts: Date.now() });

  console.log(`[onchain-fee] ${lbPair.slice(0, 8)} ${hours}h: ${swapCount} swaps, fees=$${fees24hUsd.toFixed(2)}, vol=$${volume24hUsd.toFixed(0)}, APR=${feeApr?.toFixed(1) ?? 'N/A'}%`);

  return stats;
}

async function getPoolInfo(lbPair: string): Promise<PoolInfo> {
  const dlmmPool = await DLMM.create(connection, new PublicKey(lbPair));
  const activeBin = await dlmmPool.getActiveBin();

  const tokenXMint = dlmmPool.tokenX.publicKey.toBase58();
  const tokenYMint = dlmmPool.tokenY.publicKey.toBase58();
  const xSym = tokenSymbol(tokenXMint);
  const ySym = tokenSymbol(tokenYMint);
  // SDK TokenReserve.mint.decimals,带兜底
  const xDec =
    (dlmmPool.tokenX as any)?.mint?.decimals ??
    (dlmmPool.tokenX as any)?.decimal ??
    KNOWN_TOKENS[tokenXMint]?.decimals ?? 9;
  const yDec =
    (dlmmPool.tokenY as any)?.mint?.decimals ??
    (dlmmPool.tokenY as any)?.decimal ??
    KNOWN_TOKENS[tokenYMint]?.decimals ?? 6;
  const activePrice = parseFloat(dlmmPool.fromPricePerLamport(Number(activeBin.price)));
  const binStep = dlmmPool.lbPair.binStep;
  const baseFactor = Number(dlmmPool.lbPair.parameters.baseFactor);
  const powerFactor = Number((dlmmPool.lbPair.parameters as any).baseFeePowerFactor || 0);
  const baseFeePct = calcBaseFeePct(baseFactor, binStep, powerFactor);

  let reserveX = 0;
  let reserveY = 0;
  try {
    const rxRaw = (dlmmPool.tokenX as any).amount;
    const ryRaw = (dlmmPool.tokenY as any).amount;
    if (rxRaw !== undefined) reserveX = Number(rxRaw) / Math.pow(10, xDec);
    if (ryRaw !== undefined) reserveY = Number(ryRaw) / Math.pow(10, yDec);
  } catch {}

  const info: PoolInfo = {
    address: lbPair,
    pairName: `${xSym}/${ySym}`,
    tokenXMint, tokenYMint, tokenXSymbol: xSym, tokenYSymbol: ySym,
    tokenXDecimals: xDec, tokenYDecimals: yDec,
    binStep, baseFeePct, baseFactor,
    activeBinId: activeBin.binId, activePrice,
    reserveX, reserveY,
  };

  // datapi
  for (const host of CONFIG.METEORA_API_HOSTS) {
    try {
      const r = await fetch(`${host}/pair/${lbPair}`, { signal: AbortSignal.timeout(3000) });
      if (!r.ok) continue;
      const d: any = await r.json();
      info.tvlUsd = parseFloat(d.liquidity || '0') || undefined;
      info.volume24hUsd = parseFloat(d.trade_volume_24h || '0') || undefined;
      info.fees24hUsd = parseFloat(d.fees_24h || '0') || undefined;
      info.feeApr = parseFloat(d.apr || '0') || undefined;
      info.dataSource = 'meteora';
      break;
    } catch {}
  }

  // GeckoTerminal fallback
  if (!info.tvlUsd) {
    try {
      const r = await fetch(`${CONFIG.GECKOTERMINAL_API}/networks/solana/pools/${lbPair}`, {
        signal: AbortSignal.timeout(5000),
      });
      if (r.ok) {
        const d: any = await r.json();
        const a = d?.data?.attributes;
        if (a) {
          info.tvlUsd = parseFloat(a.reserve_in_usd || '0') || undefined;
          info.volume24hUsd = parseFloat(a.volume_usd?.h24 || '0') || undefined;
          if (info.volume24hUsd) {
            info.fees24hUsd = info.volume24hUsd * (baseFeePct / 100);
            if (info.tvlUsd && info.tvlUsd > 0) {
              info.feeApr = (info.fees24hUsd * 365 / info.tvlUsd) * 100;
            }
          }
          info.dataSource = 'geckoterminal';
        }
      }
    } catch {}
  }

  // V0.1.1: 链上 fee 计算覆盖前面的估算
  // 用过去 6 小时的真实 swap events 算 fee + volume,外推 24h
  // 如果失败,保留前面的估算值
  if (info.tvlUsd && info.tvlUsd > 0) {
    try {
      const xPrice = await getTokenPriceUsd(tokenXMint);
      const yPrice = await getTokenPriceUsd(tokenYMint);
      if (xPrice > 0 && yPrice > 0) {
        const onchain = await getOnchainFeeStats(lbPair, info.tvlUsd, xPrice, yPrice, xDec, yDec, 6);
        if (onchain.swapCount > 0) {
          info.fees24hUsd = onchain.fees24hUsd;
          info.volume24hUsd = onchain.volume24hUsd;
          info.feeApr = onchain.feeApr ?? info.feeApr;
          info.dataSource = (info.dataSource ? info.dataSource + '+onchain' : 'onchain');
        }
      }
    } catch (e: any) {
      console.error(`[onchain-fee] ${lbPair.slice(0, 8)} failed: ${e.message}`);
    }
  }

  return info;
}

async function getUserPositions(lbPair?: string): Promise<PositionInfo[]> {
  const results: PositionInfo[] = [];

  if (!lbPair) {
    const r = await db.query<{ lb_pair: string }>(
      `SELECT DISTINCT lb_pair FROM positions WHERE status IN ('open','closing')`
    );
    for (const row of r.rows) {
      try {
        const sub = await getUserPositions(row.lb_pair);
        results.push(...sub);
      } catch (e: any) {
        console.error(`Failed to scan ${row.lb_pair}: ${e.message}`);
      }
    }
    return results;
  }

  const dlmmPool = await DLMM.create(connection, new PublicKey(lbPair));
  const { userPositions } = await dlmmPool.getPositionsByUserAndLbPair(wallet.publicKey);
  const activeBin = await dlmmPool.getActiveBin();
  const binStep = dlmmPool.lbPair.binStep;
  const activePrice = parseFloat(dlmmPool.fromPricePerLamport(Number(activeBin.price)));

  const tokenXMint = dlmmPool.tokenX.publicKey.toBase58();
  const tokenYMint = dlmmPool.tokenY.publicKey.toBase58();
  const xSym = tokenSymbol(tokenXMint);
  const ySym = tokenSymbol(tokenYMint);
  const xDec =
    (dlmmPool.tokenX as any)?.mint?.decimals ??
    (dlmmPool.tokenX as any)?.decimal ??
    KNOWN_TOKENS[tokenXMint]?.decimals ?? 9;
  const yDec =
    (dlmmPool.tokenY as any)?.mint?.decimals ??
    (dlmmPool.tokenY as any)?.decimal ??
    KNOWN_TOKENS[tokenYMint]?.decimals ?? 6;

  for (const pos of userPositions) {
    const minBinId = pos.positionData.lowerBinId;
    const maxBinId = pos.positionData.upperBinId;
    const inRange = activeBin.binId >= minBinId && activeBin.binId <= maxBinId;
    const totalBins = maxBinId - minBinId + 1;

    const totalX = pos.positionData.totalXAmount;
    const totalY = pos.positionData.totalYAmount;
    const feeX = pos.positionData.feeX.toString();
    const feeY = pos.positionData.feeY.toString();

    results.push({
      positionPk: pos.publicKey.toBase58(),
      lbPair,
      pairName: `${xSym}/${ySym}`,
      binStep,
      activeBinId: activeBin.binId,
      activePrice,
      minBinId, maxBinId, inRange,
      rangeWidthPct: (Math.pow(1 + binStep / 10000, totalBins) - 1) * 100,
      totalXAmount: totalX.toString(),
      totalYAmount: totalY.toString(),
      totalXAmountFloat: Number(totalX) / Math.pow(10, xDec),
      totalYAmountFloat: Number(totalY) / Math.pow(10, yDec),
      unclaimedFeeX: feeX,
      unclaimedFeeY: feeY,
      unclaimedFeeXFloat: Number(feeX) / Math.pow(10, xDec),
      unclaimedFeeYFloat: Number(feeY) / Math.pow(10, yDec),
      tokenXSymbol: xSym, tokenYSymbol: ySym,
      tokenXMint, tokenYMint,
    });
  }

  return results;
}

// 估算仓位 USD 价值
async function estimatePositionValueUsd(p: PositionInfo): Promise<{ totalUsd: number; feeUsd: number }> {
  const xPrice = await getTokenPriceUsd(p.tokenXMint);
  const yPrice = await getTokenPriceUsd(p.tokenYMint);
  const totalUsd = p.totalXAmountFloat * xPrice + p.totalYAmountFloat * yPrice;
  const feeUsd = p.unclaimedFeeXFloat * xPrice + p.unclaimedFeeYFloat * yPrice;
  return { totalUsd, feeUsd };
}

// ============================================================
// 9. 选池打分
// ============================================================

interface ScoredPool {
  info: PoolInfo;
  score: number;
  reasons: string[];
}

function scorePool(p: PoolInfo): { score: number; reasons: string[] } {
  const reasons: string[] = [];

  // 硬筛 1: token 白名单
  if (!WHITELIST_MINTS.has(p.tokenXMint) || !WHITELIST_MINTS.has(p.tokenYMint)) {
    reasons.push('token 不在白名单');
    return { score: -1, reasons };
  }

  // 硬筛 2: bin_step 按 pair 类型分级
  // - stable-stable (USDC/USDT): 1-10 bps (价差极小,大 step 抓不到 fee)
  // - SOL pair (SOL/USDC, SOL/USDT): 4-100 bps (兼容主流市场池子)
  const isStableStable = p.tokenXMint !== SOL_MINT && p.tokenYMint !== SOL_MINT;
  const [minBs, maxBs] = isStableStable ? [1, 10] : [4, 100];
  if (p.binStep < minBs || p.binStep > maxBs) {
    reasons.push(`bin_step ${p.binStep} 不在 ${minBs}-${maxBs}(${isStableStable ? 'stable' : 'SOL pair'})`);
    return { score: -1, reasons };
  }

  // 硬筛 3: TVL / Volume
  if (!p.tvlUsd || p.tvlUsd < 500_000) {
    reasons.push(`TVL ${fmtUsd(p.tvlUsd)} < $500k`);
    return { score: -1, reasons };
  }
  if (!p.volume24hUsd || p.volume24hUsd < 200_000) {
    reasons.push(`Vol ${fmtUsd(p.volume24hUsd)} < $200k`);
    return { score: -1, reasons };
  }

  // 硬筛 4: APR
  if (!p.feeApr) {
    reasons.push('无 APR 数据');
    return { score: -1, reasons };
  }
  const minApr = isStableStable ? 3 : 15;
  if (p.feeApr < minApr) {
    reasons.push(`APR ${fmtPct(p.feeApr)} < ${minApr}%`);
    return { score: -1, reasons };
  }
  if (p.feeApr > 500) {
    reasons.push(`APR ${fmtPct(p.feeApr)} > 500%(疑似假数据)`);
    return { score: -1, reasons };
  }

  // 通过硬筛 → 打分
  let score = p.feeApr * 0.6;
  reasons.push(`fee_apr × 0.6 = ${(p.feeApr * 0.6).toFixed(1)}`);

  const volumeScore = Math.min(p.volume24hUsd / 1_000_000, 30);
  score += volumeScore;
  reasons.push(`volume = +${volumeScore.toFixed(1)}`);

  if (p.tvlUsd < 2_000_000) {
    const penalty = (2_000_000 - p.tvlUsd) / 100_000;
    score -= penalty;
    reasons.push(`TVL 偏小 = -${penalty.toFixed(1)}`);
  }

  return { score, reasons };
}

async function scanPools(): Promise<ScoredPool[]> {
  state.candidatePools = await loadCandidatePools();
  const results: ScoredPool[] = [];

  for (const addr of state.candidatePools) {
    try {
      const info = await getPoolInfo(addr);
      const { score, reasons } = scorePool(info);
      results.push({ info, score, reasons });
      // 写快照
      await db.query(
        `INSERT INTO pool_metrics(lb_pair, active_bin_id, active_price, tvl_usd, volume_24h_usd, fee_24h_usd, fee_apr, score)
         VALUES($1,$2,$3,$4,$5,$6,$7,$8)`,
        [addr, info.activeBinId, info.activePrice, info.tvlUsd, info.volume24hUsd, info.fees24hUsd, info.feeApr, score]
      );
    } catch (e: any) {
      const msg = e.message || String(e);
      console.error(`scanPools: ${addr} failed: ${msg}`);
      // 自动 disable 永久性失败的池子(比如非 DLMM 账户)
      if (msg.includes('Invalid account discriminator') ||
          msg.includes('Account does not exist') ||
          msg.includes('AccountNotFound')) {
        await db.query(
          `UPDATE candidate_pools SET enabled=FALSE, disabled_reason=$2 WHERE lb_pair=$1`,
          [addr, msg.slice(0, 200)]
        );
        console.log(`Auto-disabled ${addr}: ${msg.slice(0, 80)}`);
      }
    }
  }

  results.sort((a, b) => b.score - a.score);
  state.lastScanTs = Date.now();
  return results;
}

// ============================================================
// 10. Tx 发送层
// ============================================================

function withPriorityFee(tx: Transaction): Transaction {
  // 检查 SDK 是否已经加了 ComputeBudget instructions
  // 如果有,跳过(避免 "duplicate instruction" 错误)
  const COMPUTE_BUDGET_PROGRAM_ID = 'ComputeBudget111111111111111111111111111111';
  const hasComputeBudget = tx.instructions.some(
    ix => ix.programId.toBase58() === COMPUTE_BUDGET_PROGRAM_ID
  );
  if (hasComputeBudget) {
    return tx; // SDK 自己处理了,不重复加
  }
  tx.instructions.unshift(
    ComputeBudgetProgram.setComputeUnitPrice({ microLamports: CONFIG.PRIORITY_FEE_MICRO_LAMPORTS }),
    ComputeBudgetProgram.setComputeUnitLimit({ units: 600_000 })
  );
  return tx;
}

async function sendTx(
  tx: Transaction,
  extraSigners: Keypair[] = [],
  label: string = 'tx'
): Promise<string> {
  if (CONFIG.DRY_RUN) {
    console.log(`[DRY_RUN] would send tx: ${label}, ${tx.instructions.length} ix, signers=${1 + extraSigners.length}`);
    return 'DRY_RUN_' + Date.now();
  }
  withPriorityFee(tx);

  // V2: 外层重试,处理 blockhash 过期 / RPC 抖动 / 网络瞬时错误
  // sendAndConfirmTransaction 内部 maxRetries 是 RPC 发送层的,不能重新拿 blockhash;
  // 这里 outer loop 每次重新拿 blockhash 并重签
  let lastErr: any;
  for (let attempt = 1; attempt <= CONFIG.TX_MAX_RETRIES; attempt++) {
    try {
      const { blockhash, lastValidBlockHeight } = await connection.getLatestBlockhash('confirmed');
      tx.recentBlockhash = blockhash;
      tx.lastValidBlockHeight = lastValidBlockHeight;
      tx.feePayer = wallet.publicKey;

      const sig = await sendAndConfirmTransaction(
        connection,
        tx,
        [wallet, ...extraSigners],
        { commitment: 'confirmed', skipPreflight: false, maxRetries: 0 }
      );
      if (attempt > 1) console.log(`[sendTx ${label}] succeeded on attempt ${attempt}`);
      return sig;
    } catch (e: any) {
      lastErr = e;
      const msg = e?.message || String(e);
      // 可重试错误: blockhash 过期 / 网络抖动 / 429 / 503 / timeout
      const retryable = /blockhash|expired|fetch failed|429|503|timeout|ECONNRESET|ETIMEDOUT/i.test(msg);
      if (!retryable || attempt === CONFIG.TX_MAX_RETRIES) break;
      console.log(`[sendTx ${label}] retryable error (attempt ${attempt}/${CONFIG.TX_MAX_RETRIES}): ${msg.slice(0, 120)}`);
      await sleep(1500 * attempt); // 指数退避: 1.5s → 3s → 4.5s
    }
  }
  throw lastErr;
}

// ============================================================
// 11. Jupiter Swap
// ============================================================

/**
 * 在 Meteora DLMM 池子里做 swap(单池,纯链上,无 HTTP 依赖)
 *
 * @param dlmmPool 已经初始化好的 DLMM 实例
 * @param inputMint 输入 token mint
 * @param outputMint 输出 token mint
 * @param amountInRaw 输入金额 (raw units, BN)
 * @returns sig 真实 tx 签名,outAmount 实际拿到的 raw units (BN), priceImpactPct 滑点百分比
 */
async function poolSwap(
  dlmmPool: any,  // DLMM 实例(避免类型导出问题用 any)
  inputMint: string,
  outputMint: string,
  amountInRaw: BN,
): Promise<{ sig: string; outAmount: BN; priceImpactPct: number }> {
  const tokenXMint = dlmmPool.tokenX.publicKey.toBase58();
  const tokenYMint = dlmmPool.tokenY.publicKey.toBase58();

  if (inputMint !== tokenXMint && inputMint !== tokenYMint) {
    throw new Error(`poolSwap: input ${inputMint} 不在池子里 (${tokenXMint}/${tokenYMint})`);
  }
  if (outputMint !== tokenXMint && outputMint !== tokenYMint) {
    throw new Error(`poolSwap: output ${outputMint} 不在池子里`);
  }
  if (inputMint === outputMint) {
    throw new Error(`poolSwap: input == output`);
  }

  // swapForY = true 表示 X → Y, false 表示 Y → X
  const swapForY = inputMint === tokenXMint;

  // 1. 拿当前活跃 bin 周围的 binArrays(SDK 默认 3 个,够 99% 情况)
  const binArrays = await dlmmPool.getBinArrayForSwap(swapForY);

  if (!binArrays || binArrays.length === 0) {
    throw new Error('poolSwap: no binArrays for swap (流动性不足)');
  }

  // 2. quote
  const slippageBps = new BN(CONFIG.SWAP_SLIPPAGE_BPS);
  const swapQuote = dlmmPool.swapQuote(amountInRaw, swapForY, slippageBps, binArrays, true /* allow partial fill */);

  // 3. 滑点检查(SwapQuote.priceImpact 是 Decimal)
  const priceImpactPct = parseFloat(swapQuote.priceImpact.toFixed(4)) * 100;
  if (priceImpactPct > CONFIG.SWAP_MAX_IMPACT_PCT) {
    throw new Error(`poolSwap: 滑点过大 ${priceImpactPct.toFixed(2)}% > ${CONFIG.SWAP_MAX_IMPACT_PCT}%`);
  }

  if (CONFIG.DRY_RUN) {
    console.log(`[DRY_RUN] would poolSwap ${amountInRaw.toString()} ${inputMint.slice(0, 8)} -> ${swapQuote.outAmount.toString()} ${outputMint.slice(0, 8)} (impact ${priceImpactPct.toFixed(3)}%)`);
    return {
      sig: 'DRY_RUN_POOL_SWAP_' + Date.now(),
      outAmount: swapQuote.outAmount,
      priceImpactPct,
    };
  }

  // 4. build + send tx
  const swapTx = await dlmmPool.swap({
    inToken: new PublicKey(inputMint),
    outToken: new PublicKey(outputMint),
    inAmount: amountInRaw,
    minOutAmount: swapQuote.minOutAmount,
    lbPair: dlmmPool.pubkey,
    user: wallet.publicKey,
    binArraysPubkey: swapQuote.binArraysPubkey,
  });

  const sig = await sendTx(swapTx, [], 'pool_swap');

  return {
    sig,
    outAmount: swapQuote.outAmount,
    priceImpactPct,
  };
}

/**
 * Jupiter v6 swap (多池路由,适合池内流动性差时 fallback)
 *
 * 流程: quote → swap → 反序列化 VersionedTransaction → 钱包签名 → 发送 → 确认
 */
async function jupiterSwap(
  inputMint: string,
  outputMint: string,
  amountInRaw: BN,
): Promise<{ sig: string; outAmount: BN; priceImpactPct: number }> {
  // 1. quote (V2.2: retry 3次,Jupiter API 偶发抖动免疫)
  const quoteUrl = `${CONFIG.JUP_API}/quote?inputMint=${inputMint}&outputMint=${outputMint}&amount=${amountInRaw.toString()}&slippageBps=${CONFIG.JUPITER_SLIPPAGE_BPS}`;
  const quoteRes = await retry(() => fetch(quoteUrl, { signal: AbortSignal.timeout(8000) }), 3, 1500);
  if (!quoteRes.ok) throw new Error(`jupiterSwap: quote ${quoteRes.status}`);
  const quote: any = await quoteRes.json();
  if (!quote.outAmount) throw new Error(`jupiterSwap: no route (${quote.error || 'unknown'})`);

  const priceImpactPct = parseFloat(quote.priceImpactPct || '0') * 100;

  if (CONFIG.DRY_RUN) {
    console.log(`[DRY_RUN] would jupiterSwap ${amountInRaw.toString()} ${inputMint.slice(0, 8)} -> ${quote.outAmount} ${outputMint.slice(0, 8)} (impact ${priceImpactPct.toFixed(3)}%)`);
    return {
      sig: 'DRY_RUN_JUP_' + Date.now(),
      outAmount: new BN(quote.outAmount),
      priceImpactPct,
    };
  }

  // 2. build swap tx (V2.2: retry 3次)
  const swapRes = await retry(() => fetch(`${CONFIG.JUP_API}/swap`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      quoteResponse: quote,
      userPublicKey: wallet.publicKey.toBase58(),
      wrapAndUnwrapSol: true,
      computeUnitPriceMicroLamports: CONFIG.PRIORITY_FEE_MICRO_LAMPORTS,
      dynamicComputeUnitLimit: true,
    }),
    signal: AbortSignal.timeout(15000),
  }), 3, 1500);
  if (!swapRes.ok) {
    const errText = await swapRes.text();
    throw new Error(`jupiterSwap: build tx ${swapRes.status}: ${errText.slice(0, 200)}`);
  }
  const swapJson: any = await swapRes.json();
  if (!swapJson.swapTransaction) throw new Error('jupiterSwap: no swapTransaction in response');

  // 3. deserialize + sign + send
  const txBuf = Buffer.from(swapJson.swapTransaction, 'base64');
  const tx = VersionedTransaction.deserialize(txBuf);
  tx.sign([wallet]);

  const sig = await connection.sendRawTransaction(tx.serialize(), {
    skipPreflight: false,
    maxRetries: CONFIG.TX_MAX_RETRIES,
  });

  // 4. confirm
  const { blockhash, lastValidBlockHeight } = await connection.getLatestBlockhash('confirmed');
  await connection.confirmTransaction({
    signature: sig,
    blockhash,
    lastValidBlockHeight,
  }, 'confirmed');

  return {
    sig,
    outAmount: new BN(quote.outAmount),
    priceImpactPct,
  };
}

/**
 * 智能 swap 路由 (本项目核心 — meteora-router 的 router):
 * - PREFER_JUPITER=false (默认): 先试 poolSwap (单池便宜 + 快),失败回退 Jupiter
 * - PREFER_JUPITER=true: 直接走 Jupiter (极端波动期可临时切换)
 *
 * 失败 fallback 触发条件: 滑点过大 / no binArrays / no route / 任何 RPC 错误
 */
async function swapTokens(
  dlmmPool: any,
  inputMint: string,
  outputMint: string,
  amountInRaw: BN,
): Promise<{ sig: string; outAmount: BN; priceImpactPct: number; route: 'pool' | 'jupiter' }> {
  if (!CONFIG.PREFER_JUPITER) {
    try {
      const r = await poolSwap(dlmmPool, inputMint, outputMint, amountInRaw);
      return { ...r, route: 'pool' };
    } catch (e: any) {
      console.log(`[swapTokens] poolSwap failed (${e.message}) → fallback Jupiter`);
      // 继续走 Jupiter
    }
  }

  const r = await jupiterSwap(inputMint, outputMint, amountInRaw);
  return { ...r, route: 'jupiter' };
}

// ============================================================
// 12. DLMM 操作层
// ============================================================

/**
 * 开仓:平衡仓位(50/50),Spot 分布
 *
 * @param lbPair 池地址
 * @param amountUsd 计划总投入(USD 等值)
 */
async function openPosition(lbPair: string, amountUsd: number): Promise<{ positionPk: string; sig: string; dbId: number }> {
  if (state.paused) throw new Error('bot 已 paused');
  if (amountUsd > CONFIG.MAX_POSITION_USD) throw new Error(`金额 $${amountUsd} > 上限 $${CONFIG.MAX_POSITION_USD}`);

  const dlmmPool = await DLMM.create(connection, new PublicKey(lbPair));
  const activeBin = await dlmmPool.getActiveBin();
  const tokenXMint = dlmmPool.tokenX.publicKey.toBase58();
  const tokenYMint = dlmmPool.tokenY.publicKey.toBase58();
  const xDec =
    (dlmmPool.tokenX as any)?.mint?.decimals ??
    (dlmmPool.tokenX as any)?.decimal ??
    KNOWN_TOKENS[tokenXMint]?.decimals ?? 9;
  const yDec =
    (dlmmPool.tokenY as any)?.mint?.decimals ??
    (dlmmPool.tokenY as any)?.decimal ??
    KNOWN_TOKENS[tokenYMint]?.decimals ?? 6;
  const binStep = dlmmPool.lbPair.binStep;
  const activePrice = parseFloat(dlmmPool.fromPricePerLamport(Number(activeBin.price)));

  // 计算 range:RANGE_PCT 是总区间宽度(±RANGE_PCT/2 各往两边)
  // bin_step bps × bins_per_side ≈ pct_per_side × 100
  // halfBins = (RANGE_PCT / 2) × 100 / bin_step
  //
  // 关键限制:DLMM SDK V1 single position 最多 70 bins
  // (Solana realloc 上限 10240 bytes,每 bin 数据空间限制)
  // 所以 halfBins 最大 34(总 69 bins,留 1 buffer)
  const halfPctTarget = CONFIG.RANGE_PCT / 2;
  let halfRangeBins = Math.max(3, Math.ceil((halfPctTarget * 100) / binStep));
  if (halfRangeBins > 34) halfRangeBins = 34; // SDK V1 单 position 70 bins 上限
  const minBinId = activeBin.binId - halfRangeBins;
  const maxBinId = activeBin.binId + halfRangeBins;

  // 实际 range 百分比(用于日志 + 通知)
  const totalBins = (maxBinId - minBinId + 1);
  const actualRangePct = (Math.pow(1 + binStep / 10000, totalBins) - 1) * 100;
  console.log(`[openPosition] bin_step=${binStep}, target=±${halfPctTarget}%, halfBins=${halfRangeBins}, total=${totalBins} bins, actualRange=${actualRangePct.toFixed(2)}%`);

  // 目标 50/50:amountUsd / 2 在 X,amountUsd / 2 在 Y
  const xPrice = await getTokenPriceUsd(tokenXMint);
  const yPrice = await getTokenPriceUsd(tokenYMint);
  const xUsdPerSide = amountUsd / 2;
  const yUsdPerSide = amountUsd / 2;
  const xAmountFloat = xUsdPerSide / (xPrice || 1);
  const yAmountFloat = yUsdPerSide / (yPrice || 1);

  // ============ 资金路由:先 swap 补齐缺口 ============
  // 例:钱包 SOL=0.5 USDC=510,但 $200 仓位需要 1.25 SOL + 100 USDC
  // → 缺 0.75 SOL,从 USDC swap 补齐
  if (!CONFIG.DRY_RUN) {
    const xBal = await getSplBalance(tokenXMint, xDec);
    const yBal = await getSplBalance(tokenYMint, yDec);
    // SOL 是原生 token,需要单独读 lamports
    const xBalReal = tokenXMint === SOL_MINT ? (await connection.getBalance(wallet.publicKey)) / 1e9 : xBal;
    const yBalReal = tokenYMint === SOL_MINT ? (await connection.getBalance(wallet.publicKey)) / 1e9 : yBal;

    // 留 0.1 SOL 做 gas + rent
    const xUsable = tokenXMint === SOL_MINT ? Math.max(0, xBalReal - 0.1) : xBalReal;
    const yUsable = tokenYMint === SOL_MINT ? Math.max(0, yBalReal - 0.1) : yBalReal;

    const xShortfall = Math.max(0, xAmountFloat - xUsable);
    const yShortfall = Math.max(0, yAmountFloat - yUsable);

    if (xShortfall > 0 && yShortfall > 0) {
      throw new Error(`两个 token 都不够: 缺 ${xShortfall.toFixed(4)} ${tokenSymbol(tokenXMint)} 和 ${yShortfall.toFixed(2)} ${tokenSymbol(tokenYMint)}`);
    }

    // 哪个不够就从另一个 swap 一些过来,加 1.5% buffer 防滑点(单池滑点比 Jupiter 略高)
    if (xShortfall > 0) {
      const xUsdNeeded = xShortfall * xPrice * 1.015;
      const ySwapAmount = xUsdNeeded / yPrice;
      if (ySwapAmount > yUsable) {
        throw new Error(`${tokenSymbol(tokenYMint)} 不够 swap 补 ${tokenSymbol(tokenXMint)}: 需要 ${ySwapAmount.toFixed(2)},有 ${yUsable.toFixed(2)}`);
      }
      await notify(
        `🔄 <b>资金路由</b>\n` +
        `swap ${ySwapAmount.toFixed(2)} ${tokenSymbol(tokenYMint)} → ${tokenSymbol(tokenXMint)}\n` +
        `(缺 ${xShortfall.toFixed(4)} ${tokenSymbol(tokenXMint)})`
      );
      const swapAmountRaw = new BN(Math.floor(ySwapAmount * Math.pow(10, yDec)));
      const { sig: swapSig, priceImpactPct, route } = await swapTokens(dlmmPool, tokenYMint, tokenXMint, swapAmountRaw);
      await notify(`✅ swap tx [${route}]: <code>${swapSig}</code> (滑点 ${priceImpactPct.toFixed(3)}%)`);
      await sleep(3000); // 等链上结算
    } else if (yShortfall > 0) {
      const yUsdNeeded = yShortfall * yPrice * 1.015;
      const xSwapAmount = yUsdNeeded / xPrice;
      if (xSwapAmount > xUsable) {
        throw new Error(`${tokenSymbol(tokenXMint)} 不够 swap 补 ${tokenSymbol(tokenYMint)}: 需要 ${xSwapAmount.toFixed(4)},有 ${xUsable.toFixed(4)}`);
      }
      await notify(
        `🔄 <b>资金路由</b>\n` +
        `swap ${xSwapAmount.toFixed(4)} ${tokenSymbol(tokenXMint)} → ${tokenSymbol(tokenYMint)}\n` +
        `(缺 ${yShortfall.toFixed(2)} ${tokenSymbol(tokenYMint)})`
      );
      const swapAmountRaw = new BN(Math.floor(xSwapAmount * Math.pow(10, xDec)));
      const { sig: swapSig, priceImpactPct, route } = await swapTokens(dlmmPool, tokenXMint, tokenYMint, swapAmountRaw);
      await notify(`✅ swap tx [${route}]: <code>${swapSig}</code> (滑点 ${priceImpactPct.toFixed(3)}%)`);
      await sleep(3000);
    }
  }

  const totalXAmount = new BN(Math.floor(xAmountFloat * Math.pow(10, xDec)));
  const totalYAmount = new BN(Math.floor(yAmountFloat * Math.pow(10, yDec)));

  // 最终钱包余额检查(实盘)
  if (!CONFIG.DRY_RUN) {
    const solBal = await connection.getBalance(wallet.publicKey);
    if (solBal < 0.1 * 1e9) throw new Error(`SOL 余额不足: ${(solBal / 1e9).toFixed(4)} SOL (需要 ≥ 0.1 SOL 含 rent)`);
  }

  await notify(
    `🔨 <b>开仓中...</b>\n` +
    `${tokenSymbol(tokenXMint)}/${tokenSymbol(tokenYMint)} (bin_step ${binStep})\n` +
    `投入: ${fmtUsd(amountUsd)} (${xAmountFloat.toFixed(4)} ${tokenSymbol(tokenXMint)} + ${yAmountFloat.toFixed(2)} ${tokenSymbol(tokenYMint)})\n` +
    `range: bin ${minBinId}~${maxBinId} (active ${activeBin.binId})\n` +
    `${CONFIG.DRY_RUN ? '⚠️ DRY_RUN 模式' : ''}`
  );

  const positionKp = Keypair.generate();
  const tx = await dlmmPool.initializePositionAndAddLiquidityByStrategy({
    positionPubKey: positionKp.publicKey,
    user: wallet.publicKey,
    totalXAmount,
    totalYAmount,
    strategy: { minBinId, maxBinId, strategyType: StrategyType.Spot },
  });

  const txArr = Array.isArray(tx) ? tx : [tx];
  let lastSig = '';
  for (const t of txArr) {
    lastSig = await sendTx(t, [positionKp], 'open_position');
  }

  // 入库
  const r = await db.query<{ id: number }>(
    `INSERT INTO positions(position_pk, lb_pair, pair_name, strategy, min_bin_id, max_bin_id, open_price, open_token_x_amount, open_token_y_amount, open_value_usd, status, meta)
     VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'open',$11) RETURNING id`,
    [
      positionKp.publicKey.toBase58(), lbPair,
      `${tokenSymbol(tokenXMint)}/${tokenSymbol(tokenYMint)}`,
      'Spot', minBinId, maxBinId, activePrice,
      xAmountFloat, yAmountFloat, amountUsd,
      { binStep, dryRun: CONFIG.DRY_RUN, openSig: lastSig },
    ]
  );
  const dbId = r.rows[0].id;
  await logTx(dbId, lastSig, 'open', true, null, { amountUsd, minBinId, maxBinId });

  state.firstOpenConfirmed = true;
  await notify(
    `✅ <b>开仓成功</b>\n` +
    `position: <code>${positionKp.publicKey.toBase58()}</code>\n` +
    `tx: <code>${lastSig}</code>`
  );

  return { positionPk: positionKp.publicKey.toBase58(), sig: lastSig, dbId };
}

/**
 * 关仓 + 收 fee + 关闭 position 账户
 * V3: reason !== 'rebalance' 时,在 close 前后做钱包快照,自动写 PnL 账本
 *     (rebalance 路径外层 rebalancePosition 自己快照 + 写,这里跳过避免重复)
 */
async function closePosition(positionPk: string, reason: string = 'manual'): Promise<string> {
  const r = await db.query<{ id: number; lb_pair: string; pair_name: string; open_value_usd: string; opened_at: Date }>(
    `SELECT id, lb_pair, pair_name, open_value_usd, opened_at FROM positions WHERE position_pk = $1 AND status IN ('open','closing')`,
    [positionPk]
  );
  if (r.rows.length === 0) throw new Error(`未找到 open 状态的 position ${positionPk}`);
  const dbId = r.rows[0].id;
  const lbPair = r.rows[0].lb_pair;
  const pairName = r.rows[0].pair_name;
  const openValueUsd = Number(r.rows[0].open_value_usd);
  const openedAt = r.rows[0].opened_at;

  await db.query(`UPDATE positions SET status = 'closing' WHERE id = $1`, [dbId]);
  await notify(`🔻 <b>关仓中...</b> ${reason}\nposition: <code>${positionPk}</code>`);

  const dlmmPool = await DLMM.create(connection, new PublicKey(lbPair));
  const { userPositions } = await dlmmPool.getPositionsByUserAndLbPair(wallet.publicKey);
  const pos = userPositions.find(p => p.publicKey.toBase58() === positionPk);
  if (!pos) {
    // 链上找不到 → 可能已经被关了,直接标 closed
    await db.query(`UPDATE positions SET status = 'closed', closed_at = NOW() WHERE id = $1`, [dbId]);
    await notify(`⚠️ position 链上已不存在,标记 closed`);
    return 'NOT_FOUND';
  }

  // V3: manual 路径做快照(rebalance 路径外层做了,reason='rebalance' 跳过)
  const shouldRecordPnl = reason !== 'rebalance';
  let beforeUsd = 0;
  let xMint = '', yMint = '';
  let xDec = 9, yDec = 6;
  if (shouldRecordPnl) {
    xMint = dlmmPool.tokenX.publicKey.toBase58();
    yMint = dlmmPool.tokenY.publicKey.toBase58();
    xDec = (dlmmPool.tokenX as any)?.mint?.decimals ?? (dlmmPool.tokenX as any)?.decimal ?? KNOWN_TOKENS[xMint]?.decimals ?? 9;
    yDec = (dlmmPool.tokenY as any)?.mint?.decimals ?? (dlmmPool.tokenY as any)?.decimal ?? KNOWN_TOKENS[yMint]?.decimals ?? 6;
    beforeUsd = await snapshotPairUsd(xMint, yMint, xDec, yDec);
  }

  const binIds = pos.positionData.positionBinData.map((b: any) => b.binId);
  const removeTx = await dlmmPool.removeLiquidity({
    position: pos.publicKey,
    user: wallet.publicKey,
    fromBinId: pos.positionData.lowerBinId,
    toBinId: pos.positionData.upperBinId,
    bps: new BN(10000), // 100%
    shouldClaimAndClose: true,
  });

  const txArr = Array.isArray(removeTx) ? removeTx : [removeTx];
  let lastSig = '';
  for (const t of txArr) {
    lastSig = await sendTx(t, [], 'close_position');
  }

  await db.query(
    `UPDATE positions SET status='closed', closed_at=NOW(), meta = meta || $2 WHERE id=$1`,
    [dbId, { closeSig: lastSig, closeReason: reason }]
  );
  await logTx(dbId, lastSig, 'close', true, null, { reason });

  // V3: manual 路径写 PnL 账本
  if (shouldRecordPnl) {
    try {
      await sleep(3000); // 等链上结算
      const afterUsd = await snapshotPairUsd(xMint, yMint, xDec, yDec);
      const closeValueUsd = afterUsd - beforeUsd;
      // 兜底:负数或异常小,用 open_value(避免脏数据)
      const recordedClose = closeValueUsd > 0.5 ? closeValueUsd : openValueUsd;
      const pnlUsd = recordedClose - openValueUsd;
      const pnlPct = openValueUsd > 0 ? (pnlUsd / openValueUsd) * 100 : 0;
      const holdMinutes = Math.max(1, Math.floor((Date.now() - new Date(openedAt).getTime()) / 60000));
      await db.query(
        `INSERT INTO pnl_history(position_pk, pair_name, lb_pair, open_value_usd, close_value_usd, pnl_usd, pnl_pct, hold_minutes, reason)
         VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)`,
        [positionPk, pairName, lbPair, openValueUsd, recordedClose, pnlUsd, pnlPct, holdMinutes, reason]
      );
      await notify(
        `📊 <b>PnL</b>: ${pnlUsd >= 0 ? '+' : ''}${fmtUsd(pnlUsd)} (${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%)\n` +
        `持仓 ${holdMinutes} 分钟 · 已写入账本`
      );
    } catch (e: any) {
      console.error(`[closePosition pnl record] ${e.message}`);
    }
  }

  await notify(
    `✅ <b>关仓成功</b> (${reason})\n` +
    `tx: <code>${lastSig}</code>`
  );
  return lastSig;
}

/**
 * 收手续费(不关仓)
 */
async function claimFees(positionPk: string): Promise<string> {
  const r = await db.query<{ id: number; lb_pair: string }>(
    `SELECT id, lb_pair FROM positions WHERE position_pk = $1 AND status = 'open'`,
    [positionPk]
  );
  if (r.rows.length === 0) throw new Error('position not found');
  const dbId = r.rows[0].id;
  const lbPair = r.rows[0].lb_pair;

  const dlmmPool = await DLMM.create(connection, new PublicKey(lbPair));
  const { userPositions } = await dlmmPool.getPositionsByUserAndLbPair(wallet.publicKey);
  const pos = userPositions.find(p => p.publicKey.toBase58() === positionPk);
  if (!pos) throw new Error('position not found onchain');

  const claimTxs = await dlmmPool.claimAllRewardsByPosition({
    owner: wallet.publicKey,
    position: pos,
  });

  if (!claimTxs || claimTxs.length === 0) return 'NO_FEES';

  let lastSig = '';
  for (const t of claimTxs) {
    lastSig = await sendTx(t, [], 'claim_fees');
  }

  await logTx(dbId, lastSig, 'claim', true);
  return lastSig;
}

// ============================================================
// 13. 风控 / 巡检
// ============================================================

// rebalance 冷却记录(key: lbPair) — 防止 paused 刷屏 + 防止价格在边界来回穿造成反复 rebalance
const lastRebalanceAt = new Map<string, number>();
function isInRebalanceCooldown(lbPair: string): boolean {
  const last = lastRebalanceAt.get(lbPair);
  return last !== undefined && (Date.now() - last) < CONFIG.REBALANCE_COOLDOWN_MS;
}

// V2: rebalance 失败计数(key: lbPair) — 连续失败 ≥ MAX_REBALANCE_FAILS 才 paused,而非单次失败就停
const rebalanceFailCount = new Map<string, number>();

// V0.9: 止损连续触发计数(key: positionPk)
// 连续 N 次 tick 都触发硬止损线才真执行,避免单次价格 API 抖动误杀
const stopLossHitCount = new Map<string, number>();
const stopLossWarnedSet = new Set<string>(); // 软警告已发送(防刷屏)

async function tickPositions() {
  const positions = await getUserPositions();

  for (const p of positions) {
    try {
      // 1. SL 检查
      const dbR = await db.query<{ id: number; open_value_usd: string }>(
        `SELECT id, open_value_usd FROM positions WHERE position_pk = $1 AND status = 'open'`,
        [p.positionPk]
      );
      if (dbR.rows.length === 0) continue;
      const dbId = dbR.rows[0].id;
      const openValueUsd = parseFloat(dbR.rows[0].open_value_usd || '0');

      const { totalUsd, feeUsd } = await estimatePositionValueUsd(p);
      const currentValueWithFee = totalUsd + feeUsd;
      const pnlPct = openValueUsd > 0 ? ((currentValueWithFee - openValueUsd) / openValueUsd) * 100 : 0;

      // V0.9: 软警告 (-STOP_LOSS_WARN_PCT 触发,只通知一次)
      if (pnlPct < -CONFIG.STOP_LOSS_WARN_PCT && pnlPct >= -CONFIG.HARD_SL_PCT) {
        if (!stopLossWarnedSet.has(p.positionPk)) {
          await notify(
            `⚠️ <b>${p.pairName} 接近止损线</b>\n` +
            `PnL: ${pnlPct.toFixed(2)}% (警告线 -${CONFIG.STOP_LOSS_WARN_PCT}%, 止损线 -${CONFIG.HARD_SL_PCT}%)\n` +
            `开仓值: ${fmtUsd(openValueUsd)} 现值(含费): ${fmtUsd(currentValueWithFee)}`
          );
          stopLossWarnedSet.add(p.positionPk);
        }
      } else if (pnlPct >= -CONFIG.STOP_LOSS_WARN_PCT) {
        // 恢复到警告线之上,清除标志(下次跌破再警告)
        stopLossWarnedSet.delete(p.positionPk);
      }

      // V0.9: 硬止损 (连续 N 次触发才执行,防单次价格 API 抖动误杀)
      if (pnlPct < -CONFIG.HARD_SL_PCT) {
        const hits = (stopLossHitCount.get(p.positionPk) || 0) + 1;
        stopLossHitCount.set(p.positionPk, hits);
        console.log(`[stop-loss] ${p.pairName} hit ${hits}/${CONFIG.STOP_LOSS_CONSECUTIVE} pnl=${pnlPct.toFixed(2)}%`);

        if (hits >= CONFIG.STOP_LOSS_CONSECUTIVE) {
          await notify(
            `🚨 <b>触发硬止损 (连续 ${hits} 次)</b>\n` +
            `${p.pairName} PnL: ${pnlPct.toFixed(2)}%\n` +
            `开仓值: ${fmtUsd(openValueUsd)} 现值(含费): ${fmtUsd(currentValueWithFee)}\n` +
            `自动平仓 + 暂停 bot`
          );
          try {
            await closePosition(p.positionPk, 'stop_loss');
          } catch (e: any) {
            await notify(`❌ 止损平仓失败: ${e.message}`);
          }
          state.paused = true;
          state.autoResumablePausedAt = Date.now();
          state.autoResumeReason = `止损 ${pnlPct.toFixed(2)}% (${p.pairName})`;
          stopLossHitCount.delete(p.positionPk);
          stopLossWarnedSet.delete(p.positionPk);
          continue;
        }
      } else {
        // 浮亏未达硬止损线,清计数
        if (stopLossHitCount.has(p.positionPk)) {
          stopLossHitCount.delete(p.positionPk);
        }
      }

      // 2. 出 range / 漂移 检查 (双触发: single-sided 或 drift 阈值)
      if (!p.inRange) {
        // 冷却期内跳过(防刷屏 / 防边界震荡)
        if (isInRebalanceCooldown(p.lbPair)) continue;

        const distance = p.activeBinId < p.minBinId
          ? (p.minBinId - p.activeBinId)
          : (p.activeBinId - p.maxBinId);
        const halfSpan = (p.maxBinId - p.minBinId) / 2;
        const driftRatio = halfSpan > 0 ? distance / halfSpan : 0;

        // single-sided 判定: 某一端 token 已被全部 swap 走 → 仓位停止赚费,必须立即调仓
        const dust = CONFIG.SINGLE_SIDED_DUST_TOKEN;
        const isSingleSided = p.totalXAmountFloat < dust || p.totalYAmountFloat < dust;

        const triggerReason = isSingleSided
          ? `100% single-sided (${p.tokenXSymbol}=${p.totalXAmountFloat.toFixed(6)} ${p.tokenYSymbol}=${p.totalYAmountFloat.toFixed(4)})`
          : (driftRatio > CONFIG.REBALANCE_THRESHOLD
              ? `drift ${(driftRatio * 100).toFixed(1)}% > ${(CONFIG.REBALANCE_THRESHOLD * 100).toFixed(0)}%`
              : null);

        if (triggerReason) {
          await notify(
            `⚠️ <b>${p.pairName} 已出 range</b>\n` +
            `active bin ${p.activeBinId},仓位 ${p.minBinId}~${p.maxBinId}\n` +
            `触发: ${triggerReason}\n` +
            `${state.paused ? 'paused, 不触发 rebalance' : '准备 rebalance'}`
          );
          // 不论是否 paused 都打冷却戳,paused 状态也避免 30 秒一次刷屏
          lastRebalanceAt.set(p.lbPair, Date.now());
          if (!state.paused) {
            await rebalancePosition(p, openValueUsd);
            continue;
          }
        }
      }

      // V0.8 Zip 1: 老 claim 触发点(CLAIM_THRESHOLD_PCT)已移除
      // 现在统一走 #3 自动 Claim Agent (每 6h, 阈值 $5),避免双触发冲突
    } catch (e: any) {
      console.error(`tickPositions ${p.positionPk}: ${e.message}`);
    }
  }
}

/**
 * V2.3: 钱包指定 mint pair 的 USD 快照(用于 rebalance 前后比对)
 * 注意:这里不扣 gas reserve,因为我们要的是真实余额变化
 */
async function snapshotPairUsd(
  xMint: string,
  yMint: string,
  xDec: number,
  yDec: number,
): Promise<number> {
  const xBal = xMint === SOL_MINT
    ? (await connection.getBalance(wallet.publicKey)) / 1e9
    : await getSplBalance(xMint, xDec);
  const yBal = yMint === SOL_MINT
    ? (await connection.getBalance(wallet.publicKey)) / 1e9
    : await getSplBalance(yMint, yDec);
  const xPrice = await getTokenPriceUsd(xMint);
  const yPrice = await getTokenPriceUsd(yMint);
  return xBal * xPrice + yBal * yPrice;
}

/**
 * V3: 取 position 的持仓时长(分钟)
 */
async function getHoldMinutes(positionPk: string): Promise<number> {
  try {
    const r = await db.query<{ opened_at: Date }>(
      `SELECT opened_at FROM positions WHERE position_pk = $1`,
      [positionPk]
    );
    if (r.rows.length === 0) return 0;
    return Math.max(1, Math.floor((Date.now() - new Date(r.rows[0].opened_at).getTime()) / 60000));
  } catch {
    return 0;
  }
}

/**
 * 重建仓位 (V2.3):
 * - close 前后快照钱包余额,差值 = 这次仓位真正解出的钱(自动包含 fee + IL)
 * - 报告真 IL: 仓位实际解出 vs 原始投入
 * - 失败不立即 paused: 累计 ≥ MAX_REBALANCE_FAILS 才 paused
 * - 全程持有 state.rebalancing=true,防 tickAutoOpen 并发开仓
 */
async function rebalancePosition(p: PositionInfo, originalValueUsd: number) {
  const lbPair = p.lbPair;

  // V0.10.3: 死锁救援 flag - close 成功后置 true,catch 检测到这个 flag 就强制扫池开新仓
  // 解决场景: close ✅ → openPosition ❌ → 钱包闲置 + tickAutoOpen 受 30min 缓存锁 → 死锁
  let positionClosed = false;

  // V2.3: rebalance 进行中,tickAutoOpen 跳过(防双开)
  state.rebalancing = true;
  await notify(`🔄 <b>Rebalance ${p.pairName}</b>`);

  try {
    // 池子 token 信息(用于钱包快照)
    const dlmmPool = await DLMM.create(connection, new PublicKey(lbPair));
    const xMint = dlmmPool.tokenX.publicKey.toBase58();
    const yMint = dlmmPool.tokenY.publicKey.toBase58();
    const xDec =
      (dlmmPool.tokenX as any)?.mint?.decimals ??
      (dlmmPool.tokenX as any)?.decimal ??
      KNOWN_TOKENS[xMint]?.decimals ?? 9;
    const yDec =
      (dlmmPool.tokenY as any)?.mint?.decimals ??
      (dlmmPool.tokenY as any)?.decimal ??
      KNOWN_TOKENS[yMint]?.decimals ?? 6;

    // ============ V2.3 关键修复: 关仓前后快照差值 ============
    const beforeUsd = await snapshotPairUsd(xMint, yMint, xDec, yDec);
    console.log(`[rebalance] before close: wallet ${tokenSymbol(xMint)}+${tokenSymbol(yMint)} = ${fmtUsd(beforeUsd)}`);

    await closePosition(p.positionPk, 'rebalance');
    await sleep(3000); // 等链上结算

    // V0.10.3: 仓位已关闭(包括 closePosition 内部返回 'NOT_FOUND' 也算空仓状态)
    // 之后任何步骤(snapshot/sizing/openPosition)失败 → 死锁 → catch 触发救援
    positionClosed = true;

    const afterUsd = await snapshotPairUsd(xMint, yMint, xDec, yDec);
    console.log(`[rebalance] after close: wallet ${tokenSymbol(xMint)}+${tokenSymbol(yMint)} = ${fmtUsd(afterUsd)}`);

    // 差值 = 这次仓位真正解出的钱
    const positionRecoveredUsd = afterUsd - beforeUsd;
    // 兜底: 若差值异常(负数/接近 0,说明价格剧变或快照失败),回退用原始值
    const actualUsd = positionRecoveredUsd > 0.5 ? positionRecoveredUsd : originalValueUsd;
    if (positionRecoveredUsd <= 0.5) {
      console.warn(`[rebalance] WARNING: 快照差值异常 ${fmtUsd(positionRecoveredUsd)}, 回退使用 originalValueUsd=${fmtUsd(originalValueUsd)}`);
    }

    // 安全边界 (V0.9.8 - 真滚仓):
    // - 目标重建金额: upperBound = min(钱包总值 × POSITION_PCT, MAX_POSITION_USD)
    // - 实际可用: 钱包总值 × 0.95 (留 5% buffer 给 gas + 价格波动)
    // - 总敞口检查: 已开仓位 + 新仓 ≤ TOTAL_EXPOSURE_PCT × 钱包总值
    //
    // V0.9.5 之前的 bug: reopenAmount = min(actualUsd, upperBound)
    //   actualUsd 是仓位解出的钱 (~$160),永远 ≤ upperBound,upperBound 形同虚设
    //   导致仓位规模"卡死"在初始值,无法真滚仓
    if (actualUsd > originalValueUsd * 1.5) {
      console.warn(`[rebalance] sanity: actualUsd ${fmtUsd(actualUsd)} > 原始值 ${fmtUsd(originalValueUsd)} × 1.5`);
    }
    const walletSnap = await getWalletSnapshot();
    const walletTotalForSizing = walletSnap.totalUsableUsd;
    const upperBound = Math.min(walletTotalForSizing * CONFIG.POSITION_PCT, CONFIG.MAX_POSITION_USD);
    const walletAvailable = walletTotalForSizing * 0.95; // 留 5% gas buffer

    // V0.9.8: 总敞口检查 (考虑其他 open 仓位)
    let otherOpenExposure = 0;
    try {
      const otherPositions = await getUserPositions();
      for (const op of otherPositions) {
        if (op.positionPk === p.positionPk) continue; // 排除正在 rebalance 的自己(已关闭)
        const { totalUsd: opUsd, feeUsd: opFee } = await estimatePositionValueUsd(op);
        otherOpenExposure += opUsd + opFee;
      }
    } catch (e: any) {
      console.error(`[rebalance] other-position exposure check failed: ${e.message}`);
    }
    const totalExposureCap = walletTotalForSizing * CONFIG.TOTAL_EXPOSURE_PCT;
    const exposureRemaining = Math.max(0, totalExposureCap - otherOpenExposure);

    // 最终目标 = 4 个 cap 的最小值
    const reopenAmount = Math.min(upperBound, walletAvailable, exposureRemaining);

    console.log(`[rebalance] sizing: upperBound=${upperBound.toFixed(2)} walletAvail=${walletAvailable.toFixed(2)} exposureLeft=${exposureRemaining.toFixed(2)} → ${reopenAmount.toFixed(2)}`);

    if (reopenAmount < CONFIG.MIN_REBALANCE_USD) {
      throw new Error(
        `重建金额 ${fmtUsd(reopenAmount)} < 最小阈值 ${fmtUsd(CONFIG.MIN_REBALANCE_USD)} (仓位解出 ${fmtUsd(actualUsd)})`
      );
    }

    // IL 报告(基于真实仓位差值)
    const ilDiff = actualUsd - originalValueUsd;
    const ilPct = originalValueUsd > 0 ? (ilDiff / originalValueUsd) * 100 : 0;
    // 显示 sizing 来源
    let sizingNote = '';
    if (reopenAmount === CONFIG.MAX_POSITION_USD) {
      sizingNote = ` (MAX_POSITION 卡)`;
    } else if (Math.abs(reopenAmount - walletAvailable) < 0.01) {
      sizingNote = ` (钱包 95% 取尽)`;
    } else if (Math.abs(reopenAmount - exposureRemaining) < 0.01) {
      sizingNote = ` (总敞口 cap)`;
    } else if (Math.abs(reopenAmount - upperBound) < 0.01) {
      sizingNote = ` (= 钱包 ${fmtUsd(walletTotalForSizing)} × ${(CONFIG.POSITION_PCT * 100).toFixed(0)}%)`;
    }
    await notify(
      `📊 <b>仓位实际解出</b>: ${fmtUsd(actualUsd)}\n` +
      `(原 ${fmtUsd(originalValueUsd)}, IL ${ilPct >= 0 ? '+' : ''}${ilPct.toFixed(2)}%)\n` +
      `重建金额: ${fmtUsd(reopenAmount)}${sizingNote}`
    );

    // V3: 写入 PnL 账本(rebalance close 也是 close,记一行)
    try {
      const holdMinutes = await getHoldMinutes(p.positionPk);
      await db.query(
        `INSERT INTO pnl_history(position_pk, pair_name, lb_pair, open_value_usd, close_value_usd, pnl_usd, pnl_pct, hold_minutes, reason)
         VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)`,
        [p.positionPk, p.pairName, lbPair, originalValueUsd, actualUsd, ilDiff, ilPct, holdMinutes, 'rebalance']
      );
    } catch (dbErr: any) {
      console.error(`[pnl_history insert error] ${dbErr.message}`);
      // 不影响主流程
    }

    await openPosition(lbPair, reopenAmount);

    // 成功 → 清失败计数
    rebalanceFailCount.delete(lbPair);
  } catch (e: any) {
    // V2: 失败计数,达到上限才 paused (允许瞬时 RPC 错误自动重试)
    const fails = (rebalanceFailCount.get(lbPair) || 0) + 1;
    rebalanceFailCount.set(lbPair, fails);
    if (fails >= CONFIG.MAX_REBALANCE_FAILS) {
      await notify(
        `❌ <b>Rebalance 连续失败 ${fails} 次</b>: ${e.message}\n` +
        `已暂停 bot${CONFIG.AUTO_RESUME_ENABLED ? ',将尝试智能恢复' : ',需手动 /resume'}`
      );
      state.paused = true;
      state.autoResumablePausedAt = Date.now();
      state.autoResumeReason = `Rebalance 连续失败 ${fails} 次`;
      rebalanceFailCount.delete(lbPair); // 重置,避免恢复后再次秒爆
    } else {
      await notify(
        `⚠️ Rebalance 失败 ${fails}/${CONFIG.MAX_REBALANCE_FAILS}: ${e.message}\n` +
        `不暂停 bot,${CONFIG.REBALANCE_COOLDOWN_MS / 60000} 分钟 cooldown 后下个 tick 自动重试`
      );
      // 不 paused, 等 cooldown 过后自然重试
    }

    // V0.10.3: 死锁救援
    // 仓位已关闭但 reopen 失败 → tickPositions 没仓位可监测 + tickAutoOpen 受 SCAN_INTERVAL_MS 锁 → 死锁
    // 清 lastScanTs 强制下个 tick (~2分钟) 触发自动扫池开新仓
    // paused 场景下也清(无副作用,等智能恢复 /resume 后立刻扫)
    if (positionClosed) {
      state.lastScanTs = 0;
      await notify(
        `🔓 <b>死锁救援已启动</b>\n` +
        `仓位已关闭但重建失败 → 已清扫描缓存\n` +
        (state.paused
          ? `智能恢复 /resume 后将立刻扫池开新仓`
          : `下个 tick (~2 分钟) 内将自动尝试开新仓`)
      );
    }
  } finally {
    // V2.3: 无论成功失败都释放标志位
    state.rebalancing = false;
  }
}

// 自动开仓 tick
async function tickAutoOpen(verbose: boolean = false) {
  if (state.paused || !state.autoTrading) return;

  // V2.3: rebalance 进行中,跳过(防双开 — close 后短暂"无仓"的窗口期可能误触发首次确认)
  if (state.rebalancing) {
    console.log('[tickAutoOpen] skip: rebalance in progress');
    return;
  }

  // 已有仓位数
  const r = await db.query<{ c: string }>(`SELECT COUNT(*) as c FROM positions WHERE status='open'`);
  const openCount = parseInt(r.rows[0].c);
  if (openCount >= CONFIG.MAX_OPEN_POSITIONS) return;

  // 4h 内已扫过就不重扫
  if (Date.now() - state.lastScanTs < CONFIG.SCAN_INTERVAL_MS) return;

  if (verbose) await notify('🔍 扫描候选池...');
  console.log('[tickAutoOpen] 扫描候选池');
  const scored = await scanPools();
  const eligible = scored.filter(s => s.score > 0);

  if (eligible.length === 0) {
    if (verbose) await notify('⚠️ 当前无符合条件的池子');
    console.log('[tickAutoOpen] 无符合条件池子');
    return;
  }

  // 已持仓的 token pair (规范化排序,避免 X/Y 顺序差异)
  const heldPairsR = await db.query<{ lb_pair: string }>(
    `SELECT lb_pair FROM positions WHERE status = 'open'`
  );
  const heldPairKeys = new Set<string>();
  for (const row of heldPairsR.rows) {
    try {
      const info = await getPoolInfo(row.lb_pair);
      const key = [info.tokenXMint, info.tokenYMint].sort().join('|');
      heldPairKeys.add(key);
    } catch {}
  }

  // 遍历 eligible(已按分数从高到低排),选第一个能开的
  let chosen: ScoredPool | null = null;
  const skipReasons: string[] = [];
  for (const candidate of eligible) {
    // 冷却期检查
    const cool = await db.query(
      `SELECT 1 FROM positions WHERE lb_pair = $1 AND status = 'closed' AND closed_at > NOW() - INTERVAL '${CONFIG.POOL_COOLDOWN_MINUTES} minutes' LIMIT 1`,
      [candidate.info.address]
    );
    if (cool.rows.length > 0) {
      skipReasons.push(`${candidate.info.pairName} bin_step ${candidate.info.binStep}: 冷却期`);
      continue;
    }
    // 已在该池开仓 → 跳过
    const dup = await db.query(`SELECT 1 FROM positions WHERE lb_pair=$1 AND status='open' LIMIT 1`, [candidate.info.address]);
    if (dup.rows.length > 0) {
      skipReasons.push(`${candidate.info.pairName} bin_step ${candidate.info.binStep}: 已持仓`);
      continue;
    }
    // 已在同 token pair 持仓 → 跳过(避免同对不同 bin_step 重复开仓)
    const candidateKey = [candidate.info.tokenXMint, candidate.info.tokenYMint].sort().join('|');
    if (heldPairKeys.has(candidateKey)) {
      skipReasons.push(`${candidate.info.pairName} bin_step ${candidate.info.binStep}: 同对已持仓`);
      continue;
    }
    chosen = candidate;
    break;
  }

  if (!chosen) {
    const msg = `⚠️ 无可开仓位\n${eligible.length} 个池子通过硬筛,但全部跳过:\n${skipReasons.map(r => `• ${r}`).join('\n')}`;
    console.log(`[tickAutoOpen] ${msg.replace(/\n/g, ' | ')}`);
    if (verbose) {
      await notify(
        `⚠️ <b>无可开仓位</b>\n\n` +
        `${eligible.length} 个池子通过硬筛,但全部跳过:\n` +
        skipReasons.map(r => `• ${escHtml(r)}`).join('\n')
      );
    }
    return;
  }

  const best = chosen;
  console.log(`[tickAutoOpen] 选中 ${best.info.pairName} bin_step ${best.info.binStep} score=${best.score.toFixed(1)}, skipped=${skipReasons.length}`);
  if (verbose && skipReasons.length > 0) {
    await notify(`ℹ️ 跳过 ${skipReasons.length} 个池子,选 ${best.info.pairName} bin_step ${best.info.binStep} (score ${best.score.toFixed(1)})`);
  }

  // 计算可投金额(40% of total usable = SOL+USDC+USDT,封顶 MAX_POSITION_USD)
  const wallet_ = await getWalletSnapshot();
  let investUsd = Math.min(wallet_.totalUsableUsd * CONFIG.POSITION_PCT, CONFIG.MAX_POSITION_USD);

  // V2.1: 不再用 SOL 余额硬限制 investUsd
  // (B 版加 Jupiter router 后,USDC/USDT 可自动 swap 成 SOL 补缺口)
  // 但仍然预览即将发生的 swap,让用户知情
  const poolHasSol = best.info.tokenXMint === SOL_MINT || best.info.tokenYMint === SOL_MINT;
  let swapPreviewMsg = '';
  if (poolHasSol) {
    const solNeededUsd = investUsd / 2; // 50/50 仓位 SOL 端需要的金额
    if (solNeededUsd > wallet_.solUsd) {
      const swapShortfallUsd = solNeededUsd - wallet_.solUsd;
      swapPreviewMsg = `\n💱 预计需 swap ~${fmtUsd(swapShortfallUsd)} USDC/USDT → SOL`;
      console.log(`[tickAutoOpen] swap preview: need ${fmtUsd(swapShortfallUsd)} more SOL for 50/50`);
    }
  }
  console.log(`[tickAutoOpen] investUsd=${investUsd.toFixed(2)} totalUsable=${wallet_.totalUsableUsd.toFixed(2)} solUsd=${wallet_.solUsd.toFixed(2)}`);

  // V0.9.1: 总敞口上限检查 (open positions 累计 + 新仓 ≤ 钱包 × TOTAL_EXPOSURE_PCT)
  // 钱包总值 = 闲钱 + 已开仓位价值
  try {
    const openPositions = await getUserPositions();
    let openExposureUsd = 0;
    for (const op of openPositions) {
      const { totalUsd, feeUsd } = await estimatePositionValueUsd(op);
      openExposureUsd += totalUsd + feeUsd;
    }
    const walletTotalUsd = wallet_.totalUsableUsd + openExposureUsd; // 钱包闲钱 + 仓位价值
    const exposureCap = walletTotalUsd * CONFIG.TOTAL_EXPOSURE_PCT;
    const remainingCapacity = exposureCap - openExposureUsd;

    console.log(`[tickAutoOpen] exposure check: open=${openExposureUsd.toFixed(2)} cap=${exposureCap.toFixed(2)} (${(CONFIG.TOTAL_EXPOSURE_PCT * 100).toFixed(0)}% of ${walletTotalUsd.toFixed(2)})`);

    if (remainingCapacity < 5) {
      await notify(
        `🚫 <b>跳过开仓 — 总敞口已满</b>\n` +
        `已开仓: ${fmtUsd(openExposureUsd)} / 上限 ${fmtUsd(exposureCap)} (${(CONFIG.TOTAL_EXPOSURE_PCT * 100).toFixed(0)}% 钱包)\n` +
        `剩余可投: ${fmtUsd(remainingCapacity)} < $5 阈值`
      );
      return;
    }

    if (investUsd > remainingCapacity) {
      const oldInvest = investUsd;
      investUsd = remainingCapacity;
      console.log(`[tickAutoOpen] exposure cap: ${oldInvest.toFixed(2)} → ${investUsd.toFixed(2)}`);
    }
  } catch (e: any) {
    console.error(`[tickAutoOpen] exposure check failed: ${e.message}`);
    // 失败兜底:不阻塞开仓,但 log 出来
  }

  if (investUsd < 5) {
    await notify(
      `⚠️ <b>可投金额过小</b>: ${fmtUsd(investUsd)}\n\n` +
      `钱包详情:\n` +
      `SOL: ${wallet_.solBalance.toFixed(4)} (~${fmtUsd(wallet_.solUsd)},扣 ${wallet_.gasReserveSol} SOL gas)\n` +
      `USDC: ${fmtUsd(wallet_.usdcBalance)}\n` +
      `USDT: ${fmtUsd(wallet_.usdtBalance)}\n` +
      `总可用: ${fmtUsd(wallet_.totalUsableUsd)}\n` +
      `${(CONFIG.POSITION_PCT * 100).toFixed(0)}% 投入 = ${fmtUsd(wallet_.totalUsableUsd * CONFIG.POSITION_PCT)}`
    );
    return;
  }

  // 首次开仓二次确认
  if (!state.firstOpenConfirmed) {
    state.pendingConfirmation = {
      type: 'open',
      lbPair: best.info.address,
      amountUsd: investUsd,
      expiresAt: Date.now() + 5 * 60_000,
    };
    await notify(
      `❓ <b>首次自动开仓需确认</b>\n\n` +
      `池子: ${best.info.pairName}\n` +
      `分数: ${best.score.toFixed(1)}\n` +
      `Fee APR: ${fmtPct(best.info.feeApr)}\n` +
      `投入: ${fmtUsd(investUsd)}${swapPreviewMsg}\n\n` +
      `回复 <code>/confirm</code> 确认开仓\n` +
      `回复 <code>/cancel</code> 取消\n` +
      `5 分钟内有效`
    );
    return;
  }

  await openPosition(best.info.address, investUsd);
}

// ============================================================
// 14. TG 命令
// ============================================================

bot.use(async (ctx, next) => {
  if (ctx.from?.id !== CONFIG.TG_OWNER_ID) {
    console.log(`⛔ Unauthorized: ${ctx.from?.id}`);
    return;
  }
  return next();
});

bot.command('ping', async (ctx) => { await ctx.reply('🏓 pong'); });

bot.command('help', async (ctx) => {
  await ctx.reply(
    `<b>🤖 Meteora Router</b>\n\n` +
    `<b>查询</b>\n` +
    `/status - 整体状态\n` +
    `/pool [addr] - 池子详情\n` +
    `/scan - 扫描白名单池子\n` +
    `/positions - 仓位详情\n` +
    `/pnl - 盈亏报表\n` +
    `/agents - Agent 运行状态\n\n` +
    `<b>控制</b>\n` +
    `/auto on|off - 全自动开关\n` +
    `/now - 立刻触发一次自动决策(测试用)\n` +
    `/open &lt;addr&gt; &lt;amount_usd&gt; - 手动开仓\n` +
    `/close &lt;position_pk&gt; - 手动关仓\n` +
    `/pause - 暂停所有自动动作\n` +
    `/resume - 恢复\n` +
    `/emergency - 紧急平所有仓\n` +
    `/confirm - 确认待执行操作\n` +
    `/cancel - 取消待执行操作\n\n` +
    `<b>池子管理</b>\n` +
    `/discover - 自动抓 Meteora top 池子加入候选\n` +
    `/addpool &lt;addr&gt; - 加候选池\n` +
    `/rmpool &lt;addr&gt; - 移除候选池\n\n` +
    `<i>V0.8</i>`,
    { parse_mode: 'HTML' }
  );
});

bot.command('agents', async (ctx) => {
  const fmtAgo = (ts: number) => ts === 0 ? '尚未运行' : `${Math.floor((Date.now() - ts) / 60000)} 分钟前`;
  const fmtNext = (lastTs: number, intervalMs: number) => {
    const next = lastTs + intervalMs - Date.now();
    if (next <= 0) return '即将运行';
    const min = Math.floor(next / 60000);
    return min < 60 ? `${min} 分钟后` : `${(min / 60).toFixed(1)} 小时后`;
  };
  const llmAvailable = CONFIG.ANTHROPIC_API_KEY ? '✅ 已配置' : '❌ 未配置';
  const claimEmoji = CONFIG.AUTO_CLAIM_ENABLED ? '🟢' : '⚪';

  const msg =
    `<b>🤖 Agents 状态</b>\n\n` +
    `<b>${claimEmoji} #3 自动 Claim</b> (定时, 不用 LLM)\n` +
    `阈值: ${fmtUsd(CONFIG.AUTO_CLAIM_THRESHOLD_USD)} | 间隔: ${(CONFIG.AUTO_CLAIM_INTERVAL_MS / 3600000).toFixed(1)}h\n` +
    `上次: ${fmtAgo(agentState.lastAutoClaimAt)}\n` +
    `下次: ${fmtNext(agentState.lastAutoClaimAt, CONFIG.AUTO_CLAIM_INTERVAL_MS)}\n` +
    `结果: ${agentState.lastClaimResult}\n\n` +
    `<b>🟢 #5 健康巡检</b> (定时, 不用 LLM)\n` +
    `间隔: ${(CONFIG.HEALTH_CHECK_INTERVAL_MS / 3600000).toFixed(1)}h\n` +
    `上次: ${fmtAgo(agentState.lastHealthCheckAt)}\n` +
    `下次: ${fmtNext(agentState.lastHealthCheckAt, CONFIG.HEALTH_CHECK_INTERVAL_MS)}\n` +
    `结果: ${agentState.lastHealthResult}\n\n` +
    `<b>🟢 #2 市场状态</b> (LLM Haiku)\n` +
    `LLM API: ${llmAvailable}\n` +
    `间隔: ${(CONFIG.MARKET_REGIME_INTERVAL_MS / 3600000).toFixed(1)}h\n` +
    `上次: ${fmtAgo(agentState.lastMarketRegimeAt)}\n` +
    `下次: ${fmtNext(agentState.lastMarketRegimeAt, CONFIG.MARKET_REGIME_INTERVAL_MS)}\n` +
    `当前: ${escapeHtml(agentState.lastMarketRegime)}\n` +
    `理由: ${escapeHtml(agentState.lastMarketReason)}\n\n` +
    `<b>💸 LLM 累计成本</b>: $${agentState.llmCostUsd.toFixed(4)}`;

  await ctx.reply(msg, { parse_mode: 'HTML' });
});

bot.command('status', async (ctx) => {
  await ctx.reply('⏳');
  try {
    const w = await getWalletSnapshot();

    const dbR = await db.query('SELECT COUNT(*) as c FROM events');
    const evCount = parseInt(dbR.rows[0].c);
    const posR = await db.query(`SELECT COUNT(*) as c FROM positions WHERE status='open'`);
    const openCount = parseInt(posR.rows[0].c);

    const positions = await getUserPositions();
    let totalPosValue = 0;
    let totalFeeValue = 0;
    for (const p of positions) {
      const v = await estimatePositionValueUsd(p);
      totalPosValue += v.totalUsd;
      totalFeeValue += v.feeUsd;
    }

    let posSection = '';
    if (positions.length === 0) {
      posSection = '\n📭 无仓位';
    } else {
      posSection = `\n<b>📍 链上仓位</b>\n`;
      for (const p of positions) {
        const status = p.inRange ? '✅' : '⚠️ 出range';
        posSection += `${status} ${p.pairName} | bin ${p.minBinId}~${p.maxBinId}\n`;
      }
    }

    await ctx.reply(
      `<b>📊 Status</b>\n\n` +
      `Wallet: <code>${wallet.publicKey.toBase58()}</code>\n` +
      `\n<b>💰 余额</b>\n` +
      `SOL: ${w.solBalance.toFixed(4)} (price $${w.solPrice.toFixed(2)})\n` +
      `USDC: ${fmtUsd(w.usdcBalance)}\n` +
      `USDT: ${fmtUsd(w.usdtBalance)}\n` +
      `可用 (扣 ${w.gasReserveSol} SOL gas): ${fmtUsd(w.totalUsableUsd)}\n` +
      `仓位值: ${fmtUsd(totalPosValue)}\n` +
      `未领 fee: ${fmtUsd(totalFeeValue)}\n` +
      `\n<b>⚙️ 运行</b>\n` +
      `DRY_RUN: ${CONFIG.DRY_RUN ? '🟡 ON' : '🟢 OFF (实盘)'}\n` +
      `Auto: ${state.autoTrading ? '🟢 ON' : '⚪ OFF'}\n` +
      `Paused: ${state.paused ? '🔴 YES' : '🟢 NO'}\n` +
      `Open: ${openCount}/${CONFIG.MAX_OPEN_POSITIONS}\n` +
      `Events: ${evCount}\n` +
      posSection,
      { parse_mode: 'HTML' }
    );
  } catch (e: any) {
    await ctx.reply(`❌ ${e.message}`);
  }
});

bot.command('pool', async (ctx) => {
  const args = ctx.message.text.split(/\s+/).slice(1);
  const addr = args[0] || state.candidatePools[0];
  if (!addr) { await ctx.reply('用法: /pool <addr>'); return; }
  await ctx.reply('⏳');
  try {
    const info = await getPoolInfo(addr);
    const { score, reasons } = scorePool(info);
    const tag = info.dataSource ? ` (${info.dataSource})` : '';
    await ctx.reply(
      `<b>🌊 ${info.pairName}</b>\n\n` +
      `地址: <code>${info.address}</code>\n` +
      `Bin Step: ${info.binStep} bps\n` +
      `Base Fee: ${info.baseFeePct.toFixed(4)}%\n` +
      `Active bin: ${info.activeBinId}\n` +
      `当前价: ${info.activePrice.toFixed(6)}\n` +
      `Reserve: ${info.reserveX.toFixed(2)} ${info.tokenXSymbol} / ${info.reserveY.toFixed(2)} ${info.tokenYSymbol}\n\n` +
      `<b>24h${tag}</b>\n` +
      `TVL: ${fmtUsd(info.tvlUsd)}\n` +
      `Vol: ${fmtUsd(info.volume24hUsd)}\n` +
      `Fees: ${fmtUsd(info.fees24hUsd)}\n` +
      `Fee APR: ${fmtPct(info.feeApr)}\n\n` +
      `<b>📊 Score: ${score.toFixed(1)}</b>\n` +
      reasons.map(r => `• ${escHtml(r)}`).join('\n'),
      { parse_mode: 'HTML' }
    );
  } catch (e: any) {
    await ctx.reply(`❌ ${e.message}`);
  }
});

bot.command('scan', async (ctx) => {
  await ctx.reply('⏳ 扫描中...');
  try {
    const scored = await scanPools();
    if (scored.length === 0) { await ctx.reply('候选池为空'); return; }
    let msg = `<b>🔍 扫描结果</b> (${scored.length} 池)\n\n`;
    for (const s of scored) {
      const eligible = s.score > 0 ? '✅' : '❌';
      msg += `${eligible} <b>${s.info.pairName}</b> bin_step ${s.info.binStep}\n`;
      msg += `   score=${s.score.toFixed(1)} APR=${fmtPct(s.info.feeApr)} TVL=${fmtUsd(s.info.tvlUsd)} Vol=${fmtUsd(s.info.volume24hUsd)}\n`;
      msg += `   <code>${s.info.address}</code>\n`;
      if (s.score < 0) msg += `   原因: ${escHtml(s.reasons[0] || '')}\n`;
      msg += `\n`;
    }
    await ctx.reply(msg, { parse_mode: 'HTML' });
  } catch (e: any) {
    await ctx.reply(`❌ ${e.message}`);
  }
});

bot.command('positions', async (ctx) => {
  await ctx.reply('⏳');
  try {
    const positions = await getUserPositions();
    if (positions.length === 0) { await ctx.reply('📭 无仓位'); return; }
    for (const p of positions) {
      const v = await estimatePositionValueUsd(p);
      const status = p.inRange ? '✅ in range' : '⚠️ 出 range';
      await ctx.reply(
        `<b>${p.pairName}</b> ${status}\n\n` +
        `position: <code>${p.positionPk}</code>\n` +
        `bin: ${p.minBinId}~${p.maxBinId} (active ${p.activeBinId})\n` +
        `range 宽: ${p.rangeWidthPct.toFixed(2)}%\n` +
        `当前价: ${p.activePrice.toFixed(6)}\n` +
        `${p.tokenXSymbol}: ${p.totalXAmountFloat.toFixed(4)}\n` +
        `${p.tokenYSymbol}: ${p.totalYAmountFloat.toFixed(2)}\n` +
        `仓位值: ${fmtUsd(v.totalUsd)}\n` +
        `未领 fee: ${fmtUsd(v.feeUsd)} (${p.unclaimedFeeXFloat.toFixed(4)} ${p.tokenXSymbol} + ${p.unclaimedFeeYFloat.toFixed(2)} ${p.tokenYSymbol})\n`,
        { parse_mode: 'HTML' }
      );
    }
  } catch (e: any) {
    await ctx.reply(`❌ ${e.message}`);
  }
});

bot.command('pnl', async (ctx) => {
  await ctx.reply('⏳');
  try {
    // V3: 从 pnl_history 真账本读
    const aggR = await db.query<{
      pair_name: string;
      cnt: string;
      total_pnl: string;
      avg_pnl_pct: string;
      total_open: string;
      wins: string;
      losses: string;
      total_hold_minutes: string;
    }>(`
      SELECT
        pair_name,
        COUNT(*) as cnt,
        SUM(pnl_usd) as total_pnl,
        AVG(pnl_pct) as avg_pnl_pct,
        SUM(open_value_usd) as total_open,
        SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN pnl_usd <= 0 THEN 1 ELSE 0 END) as losses,
        SUM(hold_minutes) as total_hold_minutes
      FROM pnl_history
      GROUP BY pair_name
      ORDER BY total_pnl DESC
    `);

    if (aggR.rows.length === 0) {
      await ctx.reply('📊 还没有任何 close 记录,等仓位 rebalance 或手动 close 后再看', { parse_mode: 'HTML' });
      return;
    }

    let grandPnl = 0, grandTrades = 0, grandWins = 0, grandHoldMin = 0, grandOpen = 0;
    for (const row of aggR.rows) {
      grandPnl += parseFloat(row.total_pnl);
      grandTrades += parseInt(row.cnt);
      grandWins += parseInt(row.wins);
      grandHoldMin += parseInt(row.total_hold_minutes);
      grandOpen += parseFloat(row.total_open);
    }

    let msg = `<b>📊 累计 PnL 账本</b>\n(V0.6.3 起的 close 记录)\n\n`;

    // ========== V0.10: 账户维度 (Baseline) ==========
    try {
      const blR = await db.query<{ value: string; updated_at: Date; note: string }>(
        `SELECT value, updated_at, note FROM account_settings WHERE key = 'baseline_usd'`
      );
      if (blR.rows.length > 0) {
        const baseline = parseFloat(blR.rows[0].value);
        const blDate = new Date(blR.rows[0].updated_at).toISOString().slice(0, 10);
        // 计算当前账户总值 (钱包 + open 仓位市值)
        const walletSnap = await getWalletSnapshot();
        let openExposureUsd = 0;
        try {
          const ops = await getUserPositions();
          for (const op of ops) {
            const v = await estimatePositionValueUsd(op);
            openExposureUsd += v.totalUsd + v.feeUsd;
          }
        } catch {}
        const currentTotalUsd = walletSnap.totalUsableUsd + openExposureUsd;
        const accountPnl = currentTotalUsd - baseline;
        const accountPnlPct = baseline > 0 ? (accountPnl / baseline) * 100 : 0;
        const tag = accountPnl >= 0 ? '🟢' : '🔴';
        msg += `<b>💼 账户维度</b>\n` +
          `  Baseline: ${fmtUsd(baseline)} (${blDate})\n` +
          `  当前总值: ${fmtUsd(currentTotalUsd)} (钱包 ${fmtUsd(walletSnap.totalUsableUsd)} + 仓位 ${fmtUsd(openExposureUsd)})\n` +
          `  ${tag} 账户盈亏: ${accountPnl >= 0 ? '+' : ''}${fmtUsd(accountPnl)} (${accountPnlPct >= 0 ? '+' : ''}${accountPnlPct.toFixed(2)}%)\n\n`;
      } else {
        msg += `<i>💡 还没设 baseline,发 /setbaseline &lt;USD&gt; 启用账户维度盈亏</i>\n\n`;
      }
    } catch (e: any) {
      console.error(`[pnl] baseline check: ${e.message}`);
    }

    // ========== 仓位维度 (现有逻辑) ==========
    msg += `<b>📈 仓位维度 (按对)</b>\n`;
    for (const row of aggR.rows) {
      const cnt = parseInt(row.cnt);
      const pnl = parseFloat(row.total_pnl);
      const avgPct = parseFloat(row.avg_pnl_pct);
      const wins = parseInt(row.wins);
      const wr = cnt > 0 ? (wins / cnt) * 100 : 0;
      const holdH = parseInt(row.total_hold_minutes) / 60;
      const avgHoldH = cnt > 0 ? holdH / cnt : 0;
      const tag = pnl >= 0 ? '🟢' : '🔴';
      msg += `${tag} <b>${row.pair_name}</b>\n` +
        `  ${cnt} 次 · 累计 ${pnl >= 0 ? '+' : ''}${fmtUsd(pnl)} · 平均 ${avgPct >= 0 ? '+' : ''}${avgPct.toFixed(2)}%\n` +
        `  WR ${wr.toFixed(0)}% (${wins}/${cnt}) · 平均持仓 ${avgHoldH.toFixed(1)}h\n\n`;
    }
    const grandWr = grandTrades > 0 ? (grandWins / grandTrades) * 100 : 0;
    const grandHoldH = grandHoldMin / 60;
    const avgPositionSize = grandTrades > 0 ? grandOpen / grandTrades : 0;
    msg += `─────────────\n` +
      `<b>合计</b>: ${grandPnl >= 0 ? '+' : ''}${fmtUsd(grandPnl)} · ${grandTrades} trades · WR ${grandWr.toFixed(0)}%\n` +
      `总持仓: ${grandHoldH.toFixed(1)}h · 平均仓位 ${fmtUsd(avgPositionSize)}\n\n`;

    // ========== V0.10.1: 性能指标 (B+C 混合 - 老实数据 + 警告) ==========
    if (avgPositionSize > 0 && grandHoldH > 0) {
      // 实际跨度: 从第一笔到现在
      try {
        const spanR = await db.query<{ first_close: Date }>(
          `SELECT MIN(closed_at) as first_close FROM pnl_history`
        );
        const firstClose = spanR.rows[0]?.first_close;
        const spanDays = firstClose ? (Date.now() - new Date(firstClose).getTime()) / 86400000 : 0;

        const periodReturnPct = avgPositionSize > 0 ? (grandPnl / avgPositionSize) * 100 : 0;
        const dailyReturnPct = spanDays > 0 ? periodReturnPct / spanDays : 0;
        const linearApr = (grandPnl / avgPositionSize) * (8760 / grandHoldH) * 100;

        msg += `<b>📊 性能指标</b>\n` +
          `  跨度: ${spanDays.toFixed(1)} 天 · ${grandTrades} trades\n` +
          `  累计期收益: ${periodReturnPct >= 0 ? '+' : ''}${periodReturnPct.toFixed(2)}% (PnL / 平均仓位)\n` +
          `  日均收益率: ${dailyReturnPct >= 0 ? '+' : ''}${dailyReturnPct.toFixed(2)}% / 天\n` +
          `  线性年化 (外推): <b>${linearApr.toFixed(0)}%</b>\n`;
        if (spanDays < 30 || grandTrades < 30) {
          const issues = [];
          if (spanDays < 30) issues.push(`仅 ${spanDays.toFixed(1)}天 (未满30天)`);
          if (grandTrades < 30) issues.push(`仅 ${grandTrades}笔 (未满30笔)`);
          msg += `  ⚠️ <i>样本不足: ${issues.join('、')},数字仅供参考</i>\n`;
        }
        msg += `\n`;
      } catch (e: any) {
        console.error(`[pnl] performance metrics: ${e.message}`);
      }
    }
    msg += `LLM 累计成本: $${agentState.llmCostUsd.toFixed(4)}\n\n`;

    // ========== V0.10: 分段 PnL (24h / 7d / 30d) ==========
    try {
      const segR = await db.query<{
        seg: string; cnt: string; total: string;
      }>(`
        SELECT '24h' as seg, COUNT(*) as cnt, COALESCE(SUM(pnl_usd), 0) as total FROM pnl_history WHERE closed_at > NOW() - INTERVAL '24 hours'
        UNION ALL
        SELECT '7d', COUNT(*), COALESCE(SUM(pnl_usd), 0) FROM pnl_history WHERE closed_at > NOW() - INTERVAL '7 days'
        UNION ALL
        SELECT '30d', COUNT(*), COALESCE(SUM(pnl_usd), 0) FROM pnl_history WHERE closed_at > NOW() - INTERVAL '30 days'
      `);
      msg += `<b>📅 分段</b>\n`;
      for (const r of segR.rows) {
        const cnt = parseInt(r.cnt);
        const total = parseFloat(r.total);
        const tag = total >= 0 ? '🟢' : (total < 0 ? '🔴' : '⚪');
        msg += `  ${r.seg.padEnd(4)} ${tag} ${total >= 0 ? '+' : ''}${fmtUsd(total)} (${cnt} trades)\n`;
      }
      msg += `\n`;
    } catch (e: any) {
      console.error(`[pnl] segment query: ${e.message}`);
    }

    // ========== V0.10: 最佳 / 最差 ==========
    try {
      const bestR = await db.query<{
        pair_name: string; pnl_usd: string; pnl_pct: string; closed_at: Date;
      }>(`SELECT pair_name, pnl_usd, pnl_pct, closed_at FROM pnl_history ORDER BY pnl_usd DESC LIMIT 1`);
      const worstR = await db.query<{
        pair_name: string; pnl_usd: string; pnl_pct: string; closed_at: Date;
      }>(`SELECT pair_name, pnl_usd, pnl_pct, closed_at FROM pnl_history ORDER BY pnl_usd ASC LIMIT 1`);
      if (bestR.rows.length > 0 && worstR.rows.length > 0) {
        const fmt = (r: any) => {
          const p = parseFloat(r.pnl_usd);
          const pp = parseFloat(r.pnl_pct);
          const dt = new Date(r.closed_at).toISOString().slice(5, 16).replace('T', ' ');
          return `${p >= 0 ? '+' : ''}${fmtUsd(p)} (${pp >= 0 ? '+' : ''}${pp.toFixed(1)}%) ${r.pair_name} @ ${dt}`;
        };
        msg += `<b>🏆 极值</b>\n`;
        msg += `  🏆 最佳: ${fmt(bestR.rows[0])}\n`;
        if (bestR.rows[0].closed_at.toString() !== worstR.rows[0].closed_at.toString()) {
          msg += `  💩 最差: ${fmt(worstR.rows[0])}\n`;
        }
        msg += `\n`;
      }
    } catch (e: any) {
      console.error(`[pnl] best/worst: ${e.message}`);
    }

    // ========== 最近 5 笔 ==========
    const recentR = await db.query<{
      pair_name: string;
      pnl_usd: string;
      pnl_pct: string;
      reason: string;
      hold_minutes: number;
      closed_at: Date;
    }>(`SELECT pair_name, pnl_usd, pnl_pct, reason, hold_minutes, closed_at FROM pnl_history ORDER BY closed_at DESC LIMIT 5`);

    msg += `<b>📜 最近 5 笔</b>\n`;
    for (const row of recentR.rows) {
      const pnl = parseFloat(row.pnl_usd);
      const pnlPct = parseFloat(row.pnl_pct);
      const tag = pnl >= 0 ? '🟢' : '🔴';
      const dt = new Date(row.closed_at).toISOString().slice(5, 16).replace('T', ' ');
      msg += `${tag} ${dt} ${row.pair_name} ${pnl >= 0 ? '+' : ''}${fmtUsd(pnl)} (${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(1)}%) ${row.reason}\n`;
    }
    await ctx.reply(msg, { parse_mode: 'HTML' });
  } catch (e: any) {
    await ctx.reply(`❌ ${e.message}`);
  }
});

// V0.10: /setbaseline 命令 - 设置账户维度起始本金
bot.command('setbaseline', async (ctx) => {
  const args = ctx.message.text.split(/\s+/).slice(1);
  try {
    if (args.length === 0) {
      // 查询当前 baseline
      const r = await db.query<{ value: string; updated_at: Date; note: string }>(
        `SELECT value, updated_at, note FROM account_settings WHERE key = 'baseline_usd'`
      );
      if (r.rows.length === 0) {
        // 自动用当前账户总值作为建议
        const walletSnap = await getWalletSnapshot();
        let openExposureUsd = 0;
        try {
          const ops = await getUserPositions();
          for (const op of ops) {
            const v = await estimatePositionValueUsd(op);
            openExposureUsd += v.totalUsd + v.feeUsd;
          }
        } catch {}
        const currentTotal = walletSnap.totalUsableUsd + openExposureUsd;
        await ctx.reply(
          `💡 <b>Baseline 未设</b>\n\n` +
          `当前账户总值: <b>${fmtUsd(currentTotal)}</b>\n` +
          `钱包闲钱: ${fmtUsd(walletSnap.totalUsableUsd)}\n` +
          `仓位市值: ${fmtUsd(openExposureUsd)}\n\n` +
          `用法: <code>/setbaseline ${currentTotal.toFixed(2)}</code> (用当前总值)\n` +
          `或: <code>/setbaseline 500</code> (自定义起始本金)\n\n` +
          `<i>设定后 /pnl 会显示账户维度盈亏。后续如有充值/提现,记得手动更新 baseline。</i>`,
          { parse_mode: 'HTML' }
        );
        return;
      }
      const baseline = parseFloat(r.rows[0].value);
      const blDate = new Date(r.rows[0].updated_at).toISOString().slice(0, 16).replace('T', ' ');
      await ctx.reply(
        `💼 <b>当前 Baseline</b>: ${fmtUsd(baseline)}\n` +
        `设定时间: ${blDate}\n\n` +
        `<i>更新:</i> <code>/setbaseline &lt;新金额&gt;</code>`,
        { parse_mode: 'HTML' }
      );
      return;
    }

    const newBaseline = parseFloat(args[0]);
    if (isNaN(newBaseline) || newBaseline <= 0) {
      await ctx.reply('❌ 金额无效。用法: <code>/setbaseline 500</code>', { parse_mode: 'HTML' });
      return;
    }

    await db.query(
      `INSERT INTO account_settings(key, value, updated_at) VALUES('baseline_usd', $1, NOW())
       ON CONFLICT(key) DO UPDATE SET value = $1, updated_at = NOW()`,
      [newBaseline]
    );
    await ctx.reply(
      `✅ <b>Baseline 已设</b>: ${fmtUsd(newBaseline)}\n\n` +
      `发 /pnl 查看账户维度盈亏。`,
      { parse_mode: 'HTML' }
    );
    await logEvent('setbaseline', { value: newBaseline });
  } catch (e: any) {
    await ctx.reply(`❌ ${e.message}`);
  }
});

bot.command('auto', async (ctx) => {
  const args = ctx.message.text.split(/\s+/).slice(1);
  const cmd = (args[0] || '').toLowerCase();
  if (cmd === 'on') {
    state.autoTrading = true;
    state.paused = false;
    state.lastScanTs = 0;  // 清缓存,让下次 tick 立刻扫描
    await ctx.reply(`🟢 Auto ON${CONFIG.DRY_RUN ? ' (DRY_RUN)' : ''}\n下次自动扫描将在 2 分钟内触发(发 /now 立刻触发)`);
    await logEvent('auto_on', {});
  } else if (cmd === 'off') {
    state.autoTrading = false;
    await ctx.reply('⚪ Auto OFF');
    await logEvent('auto_off', {});
  } else {
    await ctx.reply(`auto = ${state.autoTrading ? 'on' : 'off'}\n用法: /auto on|off`);
  }
});

/**
 * /now - 立刻触发一次自动决策(忽略 SCAN_INTERVAL_MS 缓存)
 * 用于测试或者你不想等 2 分钟
 */
bot.command('now', async (ctx) => {
  if (!state.autoTrading) {
    await ctx.reply('⚪ Auto 是 OFF,先 /auto on');
    return;
  }
  await ctx.reply('⏳ 立刻触发自动决策...');
  state.lastScanTs = 0;  // 强制重扫
  try {
    await tickAutoOpen(true);  // /now 是用户主动触发,verbose 通知所有过程
    await ctx.reply('✅ tickAutoOpen 完成,看上方的扫描结果或确认请求');
  } catch (e: any) {
    await ctx.reply(`❌ ${e.message}`);
  }
});

bot.command('pause', async (ctx) => {
  state.paused = true;
  await ctx.reply('🔴 Paused. 已停止所有自动动作(rebalance/claim/SL),仓位不动。/resume 恢复');
  await logEvent('pause', {});
});

bot.command('resume', async (ctx) => {
  state.paused = false;
  state.autoResumablePausedAt = 0;  // V0.9.2: 手动 resume 也清除自动恢复时间戳
  state.autoResumeReason = '';
  await ctx.reply('🟢 Resumed');
  await logEvent('resume', {});
});

bot.command('open', async (ctx) => {
  const args = ctx.message.text.split(/\s+/).slice(1);
  if (args.length < 2) { await ctx.reply('用法: /open <addr> <amount_usd>'); return; }
  const addr = args[0];
  const amount = parseFloat(args[1]);
  if (isNaN(amount) || amount <= 0) { await ctx.reply('金额无效'); return; }
  if (amount > CONFIG.MAX_POSITION_USD) {
    await ctx.reply(`❌ 金额 $${amount} > 上限 $${CONFIG.MAX_POSITION_USD}`);
    return;
  }
  await ctx.reply('⏳ 开仓中...');
  try {
    const r = await openPosition(addr, amount);
    await ctx.reply(`✅ position: <code>${r.positionPk}</code>\ntx: <code>${r.sig}</code>`, { parse_mode: 'HTML' });
  } catch (e: any) {
    await ctx.reply(`❌ ${e.message}`);
  }
});

bot.command('close', async (ctx) => {
  const args = ctx.message.text.split(/\s+/).slice(1);
  if (!args[0]) { await ctx.reply('用法: /close <position_pk>'); return; }
  await ctx.reply('⏳ 关仓中...');
  try {
    const sig = await closePosition(args[0], 'manual');
    await ctx.reply(`✅ tx: <code>${sig}</code>`, { parse_mode: 'HTML' });
  } catch (e: any) {
    await ctx.reply(`❌ ${e.message}`);
  }
});

bot.command('emergency', async (ctx) => {
  await ctx.reply('🚨 紧急平仓所有头寸...');
  state.paused = true;
  state.autoTrading = false;
  try {
    const positions = await getUserPositions();
    for (const p of positions) {
      try {
        await closePosition(p.positionPk, 'emergency');
      } catch (e: any) {
        await ctx.reply(`❌ ${p.positionPk}: ${e.message}`);
      }
    }
    await ctx.reply('✅ 全部平仓完成,bot 已 paused');
  } catch (e: any) {
    await ctx.reply(`❌ ${e.message}`);
  }
});

bot.command('confirm', async (ctx) => {
  const c = state.pendingConfirmation;
  if (!c) { await ctx.reply('无待确认操作'); return; }
  if (Date.now() > c.expiresAt) {
    state.pendingConfirmation = null;
    await ctx.reply('⏰ 确认已过期');
    return;
  }
  state.pendingConfirmation = null;
  state.firstOpenConfirmed = true;
  await ctx.reply('✅ 已确认,执行中...');
  try {
    await openPosition(c.lbPair, c.amountUsd);
  } catch (e: any) {
    await ctx.reply(`❌ ${e.message}`);
  }
});

bot.command('cancel', async (ctx) => {
  if (!state.pendingConfirmation) { await ctx.reply('无待确认操作'); return; }
  state.pendingConfirmation = null;
  await ctx.reply('已取消');
});

/**
 * /discover - 自动从 GeckoTerminal 抓 Meteora DLMM 池子,挑符合白名单的加入候选
 * 没有参数:抓 top 100 个 24h volume 最高的池子,过滤白名单 + 加入候选
 */
bot.command('discover', async (ctx) => {
  await ctx.reply('🔍 Discovering pools from GeckoTerminal (this takes ~30s)...');
  let added = 0, skipped = 0, errors = 0;
  const targetTokenSets: Set<string>[] = [
    new Set([SOL_MINT, USDC_MINT]),
    new Set([SOL_MINT, USDT_MINT]),
    new Set([USDC_MINT, USDT_MINT]),
  ];

  try {
    // 抓 4 页(每页 20 个),按 24h vol 排序
    const candidates: Array<{ address: string; name: string; vol: number; tvl: number }> = [];
    for (let page = 1; page <= 4; page++) {
      const url = `${CONFIG.GECKOTERMINAL_API}/networks/solana/dexes/meteora/pools?page=${page}&sort=h24_volume_usd_desc`;
      try {
        const r = await fetch(url, { signal: AbortSignal.timeout(8000) });
        if (!r.ok) {
          errors++;
          break;
        }
        const data: any = await r.json();
        for (const p of data?.data || []) {
          const a = p.attributes;
          const baseMint: string = (p.relationships?.base_token?.data?.id || '').replace('solana_', '');
          const quoteMint: string = (p.relationships?.quote_token?.data?.id || '').replace('solana_', '');
          candidates.push({
            address: a.address,
            name: a.name,
            vol: parseFloat(a.volume_usd?.h24 || '0'),
            tvl: parseFloat(a.reserve_in_usd || '0'),
          });
          // 检查 token 对是否在白名单组合
          const tokenSet = new Set([baseMint, quoteMint]);
          const matches = targetTokenSets.some(target =>
            target.size === tokenSet.size && [...target].every(x => tokenSet.has(x))
          );
          if (!matches) { skipped++; continue; }

          // 加入 DB(去重)
          const existing = await db.query(`SELECT 1 FROM candidate_pools WHERE lb_pair=$1`, [a.address]);
          if (existing.rows.length === 0) {
            await db.query(
              `INSERT INTO candidate_pools(lb_pair) VALUES($1) ON CONFLICT DO NOTHING`,
              [a.address]
            );
            added++;
          } else {
            // 已存在,确保启用
            await db.query(`UPDATE candidate_pools SET enabled=TRUE WHERE lb_pair=$1`, [a.address]);
          }
        }
      } catch (e: any) {
        console.error(`discover page ${page}: ${e.message}`);
        errors++;
      }
      await sleep(1500); // GT 30 RPM 限流
    }

    state.candidatePools = await loadCandidatePools();
    await ctx.reply(
      `✅ <b>Discovery 完成</b>\n\n` +
      `扫描了 ${candidates.length} 个 Meteora 池\n` +
      `符合白名单加入: <b>${added}</b>\n` +
      `跳过(非白名单 token): ${skipped}\n` +
      `错误页: ${errors}\n\n` +
      `当前候选池总数: <b>${state.candidatePools.length}</b>\n\n` +
      `下一步: /scan 看打分`,
      { parse_mode: 'HTML' }
    );
  } catch (e: any) {
    await ctx.reply(`❌ ${e.message}`);
  }
});

bot.command('addpool', async (ctx) => {
  const args = ctx.message.text.split(/\s+/).slice(1);
  if (!args[0]) { await ctx.reply('用法: /addpool <addr>'); return; }
  try {
    new PublicKey(args[0]); // 验证格式
  } catch {
    await ctx.reply('地址格式无效'); return;
  }
  await db.query(`INSERT INTO candidate_pools(lb_pair) VALUES($1) ON CONFLICT(lb_pair) DO UPDATE SET enabled=TRUE`, [args[0]]);
  state.candidatePools = await loadCandidatePools();
  await ctx.reply(`✅ 已加入候选: ${args[0]}\n现在 ${state.candidatePools.length} 个池子`);
});

bot.command('rmpool', async (ctx) => {
  const args = ctx.message.text.split(/\s+/).slice(1);
  if (!args[0]) { await ctx.reply('用法: /rmpool <addr>'); return; }
  await db.query(`UPDATE candidate_pools SET enabled=FALSE WHERE lb_pair=$1`, [args[0]]);
  state.candidatePools = await loadCandidatePools();
  await ctx.reply(`✅ 已移除`);
});

// ============================================================
// 15. 健康检查
// ============================================================

const app = express();
app.get('/health', async (req, res) => {
  try {
    await db.query('SELECT 1');
    res.json({
      ok: true,
      db: 'ok',
      paused: state.paused,
      auto: state.autoTrading,
      dryRun: CONFIG.DRY_RUN,
      ts: Date.now(),
    });
  } catch (e: any) {
    res.status(503).json({ ok: false, db: e.message });
  }
});
app.listen(CONFIG.PORT, () => console.log(`🩺 :${CONFIG.PORT}/health`));

// ============================================================
// 16. 主循环
// ============================================================

// V2: SOL gas 余额预警状态(防刷屏 — 发过一次后不再发,等余额回升 50% 以上才重置)
let lowGasWarned = false;

async function checkLowGasAndAlert(): Promise<void> {
  try {
    const lamports = await connection.getBalance(wallet.publicKey);
    const sol = lamports / 1e9;
    if (sol < CONFIG.LOW_GAS_THRESHOLD_SOL && !lowGasWarned) {
      const solPrice = await getTokenPriceUsd(SOL_MINT).catch(() => 0);
      await notify(
        `⛽ <b>SOL gas 余额预警</b>\n` +
        `当前: ${sol.toFixed(4)} SOL${solPrice ? ` (≈ ${fmtUsd(sol * solPrice)})` : ''}\n` +
        `阈值: ${CONFIG.LOW_GAS_THRESHOLD_SOL} SOL\n` +
        `请尽快充值,否则后续交易会因 gas 不足失败`
      );
      lowGasWarned = true;
    } else if (sol >= CONFIG.LOW_GAS_THRESHOLD_SOL * 1.5 && lowGasWarned) {
      // 余额回升 50% 以上才清除标志(避免阈值附近震荡反复发预警)
      lowGasWarned = false;
      console.log(`[gas] balance recovered to ${sol.toFixed(4)} SOL, alert cleared`);
    }
  } catch (e: any) {
    console.error(`checkLowGasAndAlert error: ${e.message}`);
  }
}

// ============================================================
// 16.5 V0.8 Zip 1: Agents
// ============================================================

// Agent 运行状态(/agents 命令展示)
const agentState = {
  lastAutoClaimAt: 0,
  lastHealthCheckAt: 0,
  lastMarketRegimeAt: 0,
  llmCostUsd: 0,                        // 累计 LLM API 成本
  lastClaimResult: '尚未运行',
  lastHealthResult: '尚未运行',
  lastMarketRegime: '未知' as '稳定' | '震荡' | '趋势' | '高波动' | '未知',
  lastMarketReason: '尚未运行',
};

/**
 * 调用 Claude Haiku API
 * - 60 秒超时,2 次重试
 * - 失败抛错,调用方决定是否兜底
 */
async function callClaude(prompt: string, maxTokens: number = 500): Promise<string> {
  if (!CONFIG.ANTHROPIC_API_KEY) {
    throw new Error('ANTHROPIC_API_KEY 未配置');
  }

  const r = await retry(async () => {
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': CONFIG.ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: CONFIG.ANTHROPIC_MODEL,
        max_tokens: maxTokens,
        messages: [{ role: 'user', content: prompt }],
      }),
      signal: AbortSignal.timeout(60_000),
    });
    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Claude API ${res.status}: ${errText.slice(0, 200)}`);
    }
    return res;
  }, 2, 2000);

  const data: any = await r.json();
  const text = data.content?.[0]?.text || '';

  // 成本估算 (Haiku 4.5: ~$1/M input, ~$5/M output tokens)
  const inputTok = data.usage?.input_tokens || 0;
  const outputTok = data.usage?.output_tokens || 0;
  const cost = (inputTok / 1_000_000) * 1 + (outputTok / 1_000_000) * 5;
  agentState.llmCostUsd += cost;
  console.log(`[llm] in=${inputTok} out=${outputTok} cost=$${cost.toFixed(5)} cumul=$${agentState.llmCostUsd.toFixed(4)}`);

  return text.trim();
}

/**
 * Agent #3: 自动 Claim Agent (定时,不用 LLM)
 * 扫所有 open 仓位,fee USD > 阈值 → claim
 */
async function runAutoClaimAgent(): Promise<void> {
  if (!CONFIG.AUTO_CLAIM_ENABLED) { agentState.lastClaimResult = '已禁用'; return; }
  if (state.paused) { agentState.lastClaimResult = 'bot paused, 跳过'; return; }
  if (state.rebalancing) { agentState.lastClaimResult = 'rebalance 中, 跳过'; return; }

  try {
    const positions = await getUserPositions();
    if (positions.length === 0) {
      agentState.lastClaimResult = '无 open 仓位';
      agentState.lastAutoClaimAt = Date.now();
      return;
    }

    let totalClaimedUsd = 0;
    let claimCount = 0;
    const results: string[] = [];

    for (const p of positions) {
      const xPrice = await getTokenPriceUsd(p.tokenXMint).catch(() => 0);
      const yPrice = await getTokenPriceUsd(p.tokenYMint).catch(() => 0);
      const feeUsd = (p.unclaimedFeeXFloat || 0) * xPrice + (p.unclaimedFeeYFloat || 0) * yPrice;
      if (feeUsd >= CONFIG.AUTO_CLAIM_THRESHOLD_USD) {
        try {
          const sig = await claimFees(p.positionPk);
          if (sig !== 'NO_FEES') {
            totalClaimedUsd += feeUsd;
            claimCount++;
            results.push(`${p.pairName}: ${fmtUsd(feeUsd)}`);
            // 累计到 DB 老字段(向后兼容 /status 显示)
            await db.query(
              `UPDATE positions SET fees_claimed_usd = fees_claimed_usd + $2 WHERE position_pk = $1`,
              [p.positionPk, feeUsd]
            ).catch(e => console.error(`[auto-claim] db update fees_claimed_usd: ${e.message}`));
            console.log(`[auto-claim] ${p.pairName} fee=${fmtUsd(feeUsd)} sig=${sig}`);
          }
        } catch (e: any) {
          console.error(`[auto-claim] ${p.pairName} failed: ${e.message}`);
        }
      }
    }

    if (claimCount > 0) {
      await notify(
        `💰 <b>自动 Claim</b>\n` +
        `共领取 ${claimCount} 次,合计 ${fmtUsd(totalClaimedUsd)}\n` +
        results.map(r => `• ${r}`).join('\n')
      );
    }

    agentState.lastClaimResult = claimCount > 0
      ? `✅ ${claimCount} claims, ${fmtUsd(totalClaimedUsd)}`
      : `无可 claim (阈值 ${fmtUsd(CONFIG.AUTO_CLAIM_THRESHOLD_USD)})`;
    agentState.lastAutoClaimAt = Date.now();
  } catch (e: any) {
    console.error(`[auto-claim] error: ${e.message}`);
    agentState.lastClaimResult = `❌ ${e.message.slice(0, 80)}`;
  }
}

/**
 * Agent #5: 健康巡检 Agent (定时,不用 LLM)
 * 检查: SOL 余额、DB 大小、幽灵仓位、7d PnL
 */
async function runHealthCheckAgent(): Promise<void> {
  try {
    const issues: string[] = [];
    const info: string[] = [];

    // 1. SOL 余额
    const solBal = (await connection.getBalance(wallet.publicKey)) / 1e9;
    info.push(`SOL: ${solBal.toFixed(4)}`);
    if (solBal < CONFIG.LOW_GAS_THRESHOLD_SOL * 2) {
      issues.push(`⚠️ SOL ${solBal.toFixed(4)} 偏低,建议补充到 0.2+ SOL`);
    }

    // 2. DB 大小
    try {
      const r = await db.query<{ size: string }>(`SELECT pg_size_pretty(pg_database_size(current_database())) as size`);
      info.push(`DB: ${r.rows[0].size}`);
    } catch {}

    // 3. 幽灵仓位检查
    try {
      const dbOpen = await db.query<{ position_pk: string; pair_name: string }>(
        `SELECT position_pk, pair_name FROM positions WHERE status = 'open'`
      );
      const onchain = await getUserPositions();
      const onchainPks = new Set(onchain.map(p => p.positionPk));
      const ghosts = dbOpen.rows.filter(r => !onchainPks.has(r.position_pk));
      if (ghosts.length > 0) {
        issues.push(`⚠️ ${ghosts.length} 幽灵仓位(DB open / 链上无):\n` +
          ghosts.map(g => `  ${g.pair_name} ${g.position_pk.slice(0, 8)}...`).join('\n'));
      }
      info.push(`仓位: ${onchain.length} 链上 / ${dbOpen.rows.length} DB`);
    } catch (e: any) { console.error(`[health] ghost: ${e.message}`); }

    // 4. 7d PnL
    try {
      const r = await db.query<{ cnt: string; total: string; wins: string }>(
        `SELECT COUNT(*) as cnt, COALESCE(SUM(pnl_usd), 0) as total,
                SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins
         FROM pnl_history WHERE closed_at > NOW() - INTERVAL '7 days'`
      );
      const cnt = parseInt(r.rows[0].cnt);
      const total = parseFloat(r.rows[0].total);
      const wins = parseInt(r.rows[0].wins);
      if (cnt > 0) {
        const wr = (wins / cnt) * 100;
        info.push(`7d PnL: ${total >= 0 ? '+' : ''}${fmtUsd(total)} (${cnt} trades, WR ${wr.toFixed(0)}%)`);
      } else {
        info.push(`7d PnL: 暂无数据`);
      }
    } catch {}

    // 5. LLM 累计成本
    info.push(`LLM 成本累计: $${agentState.llmCostUsd.toFixed(4)}`);

    // 6. 当前市场状态
    if (agentState.lastMarketRegime !== '未知') {
      info.push(`市场: ${escapeHtml(agentState.lastMarketRegime)} (${escapeHtml(agentState.lastMarketReason)})`);
    }

    const header = issues.length > 0 ? '🩺 <b>健康巡检 (有警告)</b>' : '🩺 <b>健康巡检 (一切正常)</b>';
    const body = info.map(i => `• ${i}`).join('\n');
    const warns = issues.length > 0 ? '\n\n' + issues.join('\n') : '';
    await notify(`${header}\n\n${body}${warns}`);

    agentState.lastHealthResult = issues.length > 0 ? `⚠️ ${issues.length} warnings` : '✅ all ok';
    agentState.lastHealthCheckAt = Date.now();
  } catch (e: any) {
    console.error(`[health] error: ${e.message}`);
    agentState.lastHealthResult = `❌ ${e.message.slice(0, 80)}`;
  }
}

/**
 * Agent #2: 市场状态 Agent (LLM)
 * 拉 24h SOL ohlcv → Claude Haiku 分类: 稳定/震荡/趋势/高波动
 * 只通知状态切换,避免刷屏
 */
async function runMarketRegimeAgent(): Promise<void> {
  if (!CONFIG.ANTHROPIC_API_KEY) {
    agentState.lastMarketReason = 'API key 未配置,agent 已禁用';
    return;
  }

  try {
    const solPrice = await getTokenPriceUsd(SOL_MINT).catch(() => 0);
    if (solPrice === 0) {
      agentState.lastMarketReason = '无法获取 SOL 价格';
      return;
    }

    // 拉 24h SOL/USDC ohlcv (用 SOL/USDC 主流池)
    let ohlcvSummary = '近期数据缺失';
    try {
      const url = `${CONFIG.GECKOTERMINAL_API}/networks/solana/pools/3ne4mWqdYuNiYrYZC9TrA3FcfuFdErghH97vNPbjicr1/ohlcv/hour?aggregate=1&limit=24`;
      const r = await fetch(url, { signal: AbortSignal.timeout(8000) });
      const data: any = await r.json();
      const candles = data?.data?.attributes?.ohlcv_list || [];
      if (candles.length >= 12) {
        // V4 修复: 强类型转换 (Gecko 偶尔返回 string),过滤 NaN/0
        const prices = candles
          .map((c: any[]) => Number(c[4]))
          .filter((p: number) => !isNaN(p) && p > 0);

        if (prices.length >= 12) {
          const high = Math.max(...prices);
          const low = Math.min(...prices);
          // Gecko 倒序: [0]=最新, [length-1]=最旧
          const last = prices[0];
          const first = prices[prices.length - 1];
          const change = ((last - first) / first) * 100;
          const range = ((high - low) / low) * 100;
          // V0.9.4: 自适应小数位 (Gecko 池子可能返回 USDC/SOL 反向价格如 0.0104,需要 4-6 位)
          const dp = Math.max(high, last) < 1 ? 6 : 2;
          ohlcvSummary = `24h: $${first.toFixed(dp)} → $${last.toFixed(dp)} (${change >= 0 ? '+' : ''}${change.toFixed(2)}%), 区间波动 ${range.toFixed(2)}% (high $${high.toFixed(dp)} / low $${low.toFixed(dp)})`;
        } else {
          console.warn(`[market-regime] ohlcv 有效数据不够: ${prices.length}/24`);
          ohlcvSummary = `OHLCV 数据异常,当前 SOL: $${solPrice.toFixed(2)}`;
        }
      } else {
        console.warn(`[market-regime] candles 不足: ${candles.length}/24`);
      }
    } catch (e: any) {
      console.error(`[market-regime] ohlcv: ${e.message}`);
    }

    const prompt = `你是加密 LP 市场分析助手。基于以下 SOL 数据,把当前市场状态归类为以下 4 类之一:

- 稳定: 24h 总体波动 < 3%, 价格平稳
- 震荡: 24h 波动 3-7%, 来回拉锯无明确方向
- 趋势: 24h 单向 > 5%, 涨/跌一边倒
- 高波动: 24h 区间 > 10% 或剧烈上下震荡

数据:
当前 SOL 价: $${solPrice.toFixed(2)}
${ohlcvSummary}

严格按 JSON 返回,不要任何额外文字:
{"regime": "稳定|震荡|趋势|高波动", "reason": "30字内一句话理由"}`;

    const reply = await callClaude(prompt, 200);
    const jsonMatch = reply.match(/\{[\s\S]*?\}/);
    if (!jsonMatch) {
      agentState.lastMarketReason = `LLM 返回格式错: ${reply.slice(0, 80)}`;
      console.error(`[market-regime] no json in reply: ${reply}`);
      return;
    }
    const parsed = JSON.parse(jsonMatch[0]);
    const regime = parsed.regime;
    const reason = parsed.reason || '';

    if (!['稳定', '震荡', '趋势', '高波动'].includes(regime)) {
      agentState.lastMarketReason = `未知 regime: ${regime}`;
      return;
    }

    const prevRegime = agentState.lastMarketRegime;
    agentState.lastMarketRegime = regime;
    agentState.lastMarketReason = reason;
    agentState.lastMarketRegimeAt = Date.now();

    // 状态切换才通知,避免刷屏
    if (regime !== prevRegime) {
      const emoji = ({ '稳定': '😴', '震荡': '🌊', '趋势': '📈', '高波动': '⚡' } as any)[regime] || '❓';
      await notify(
        `${emoji} <b>市场状态: ${escapeHtml(regime)}</b>\n` +
        `${escapeHtml(reason)}\n\n` +
        `(切换自: ${escapeHtml(prevRegime)})\n` +
        `${escapeHtml(ohlcvSummary)}`
      );
    }
  } catch (e: any) {
    console.error(`[market-regime] error: ${e.message}`);
    agentState.lastMarketReason = `❌ ${e.message.slice(0, 80)}`;
  }
}

let tickCounter = 0;

/**
 * V0.9.2: 智能恢复 — 止损/rebalance失败导致的 paused,等待市场状态稳定后自动 /resume
 * 触发条件 (全部满足):
 *   1. AUTO_RESUME_ENABLED = true
 *   2. state.paused = true
 *   3. state.autoResumablePausedAt > 0 (是止损/rebalance失败造成的,不是手动 /pause 或 emergency)
 *   4. 已等待 ≥ AUTO_RESUME_MIN 分钟
 *   5. 市场状态 agent 输出 = "稳定" 或 "震荡"
 */
async function checkAutoResume(): Promise<void> {
  if (!CONFIG.AUTO_RESUME_ENABLED) return;
  if (!state.paused || state.autoResumablePausedAt === 0) return;

  const elapsedMin = (Date.now() - state.autoResumablePausedAt) / 60_000;
  if (elapsedMin < CONFIG.AUTO_RESUME_MIN) return;

  // 检查市场状态
  const regime = agentState.lastMarketRegime;
  const okRegimes = ['稳定', '震荡'];

  if (regime === '未知') {
    console.log(`[auto-resume] waiting: market regime unknown (${Math.floor(elapsedMin)}min elapsed)`);
    return;
  }

  if (!okRegimes.includes(regime)) {
    // 市场仍动荡,不 resume
    console.log(`[auto-resume] waiting: regime=${regime} not safe (${Math.floor(elapsedMin)}min elapsed)`);
    return;
  }

  // 所有条件满足,自动 resume
  await notify(
    `🟢 <b>智能恢复</b>\n` +
    `已 paused ${Math.floor(elapsedMin)} 分钟,市场状态: ${regime}\n` +
    `paused 原因: ${state.autoResumeReason}\n` +
    `自动 /resume 中...`
  );
  state.paused = false;
  state.autoResumablePausedAt = 0;
  state.autoResumeReason = '';
  console.log(`[auto-resume] resumed after ${Math.floor(elapsedMin)}min, regime=${regime}`);
}

async function mainLoop() {
  while (true) {
    try {
      tickCounter++;
      console.log(`[loop ${tickCounter}] paused=${state.paused} auto=${state.autoTrading} positions...`);
      await tickPositions();
      // tickAutoOpen 每 N 个 loop 跑一次
      if (tickCounter % CONFIG.AUTO_TICK_EVERY_N_LOOPS === 0) {
        await tickAutoOpen();
      }
      // V2: SOL gas 预警 — 每 N 个 loop 检查一次(默认 2 分钟)
      if (tickCounter % CONFIG.GAS_CHECK_EVERY_N_LOOPS === 0) {
        await checkLowGasAndAlert();
      }
      // V0.8 Zip 1: Agents (基于时间间隔触发,不和 loop count 绑死)
      const now = Date.now();
      if (now - agentState.lastAutoClaimAt > CONFIG.AUTO_CLAIM_INTERVAL_MS) {
        await runAutoClaimAgent();
      }
      if (now - agentState.lastHealthCheckAt > CONFIG.HEALTH_CHECK_INTERVAL_MS) {
        await runHealthCheckAgent();
      }
      if (now - agentState.lastMarketRegimeAt > CONFIG.MARKET_REGIME_INTERVAL_MS) {
        await runMarketRegimeAgent();
      }
      // V0.9.2: 智能恢复 (每个 loop 都检查,但内部有 time gate)
      await checkAutoResume();
    } catch (e: any) {
      console.error(`[loop] error: ${e.message}`);
      await notify(`⚠️ Loop error: ${e.message}`);
    }
    await sleep(CONFIG.CHECK_INTERVAL_MS);
  }
}

// ============================================================
// 17. 启动
// ============================================================

async function start() {
  process.on('unhandledRejection', async (err: any) => {
    console.error('Unhandled rejection:', err);
    await notify(`🚨 Unhandled rejection: ${err?.message || err}`);
  });
  process.on('uncaughtException', async (err: any) => {
    console.error('Uncaught exception:', err);
    await notify(`🚨 Uncaught exception: ${err?.message || err}`);
  });

  await initDb();
  state.candidatePools = await loadCandidatePools();
  await logEvent('boot', { wallet: wallet.publicKey.toBase58(), dryRun: CONFIG.DRY_RUN });

  // 给上一个进程 5 秒退出时间
  console.log('⏳ 5s sleep before launching TG bot...');
  await sleep(5000);

  bot.launch({ dropPendingUpdates: true, allowedUpdates: ['message'] }).catch((e: any) => {
    console.error('TG launch error:', e?.message);
  });
  console.log('🤖 TG bot launched');

  // V0.9.7: 注册 Telegram menu bar (左下蓝色斜杠按钮)
  try {
    await bot.telegram.setMyCommands([
      { command: 'status', description: '整体状态' },
      { command: 'positions', description: '所有仓位详情' },
      { command: 'pnl', description: 'PnL 账本' },
      { command: 'setbaseline', description: '设置账户起始本金' },
      { command: 'agents', description: 'Agent 运行状态' },
      { command: 'now', description: '立即触发自动决策' },
      { command: 'auto', description: 'auto on/off' },
      { command: 'pause', description: '暂停所有自动动作' },
      { command: 'resume', description: '恢复' },
      { command: 'discover', description: '抓 top 池子加入候选' },
      { command: 'scan', description: '扫候选池打分' },
      { command: 'close', description: '手动关仓 <position_pk>' },
      { command: 'open', description: '手动开仓 <addr> <amount_usd>' },
      { command: 'emergency', description: '紧急平所有仓' },
      { command: 'help', description: '查看所有命令' },
    ]);
    console.log('[bot] commands menu registered');
  } catch (e: any) {
    console.error(`setMyCommands failed: ${e.message}`);
  }

  await notify(
    `🚀 <b>Meteora Router 上线</b>\n\n` +
    `Wallet: <code>${wallet.publicKey.toBase58()}</code>\n` +
    `Version: V0.10.4 (Jupiter v6 → lite-api 迁移 + SWAP_MAX_IMPACT 默认 5%)\n` +
    `DRY_RUN: ${CONFIG.DRY_RUN ? '🟡 ON' : '🟢 OFF (实盘!)'}\n` +
    `Auto: ${state.autoTrading ? 'ON' : 'OFF'}\n` +
    `候选池: ${state.candidatePools.length}\n` +
    `LLM API: ${CONFIG.ANTHROPIC_API_KEY ? '🟢 已配置 (Haiku)' : '⚪ 未配置 (#2 agent 跳过)'}\n` +
    `自动 Claim: ${CONFIG.AUTO_CLAIM_ENABLED ? `🟢 阈值 ${fmtUsd(CONFIG.AUTO_CLAIM_THRESHOLD_USD)}` : '⚪ 已禁用'}\n` +
    `止损: 🚨 -${CONFIG.HARD_SL_PCT}% 硬止损 + ⚠️ -${CONFIG.STOP_LOSS_WARN_PCT}% 软警告 (连续 ${CONFIG.STOP_LOSS_CONSECUTIVE} 次触发)\n` +
    `智能恢复: ${CONFIG.AUTO_RESUME_ENABLED ? `🟢 ${CONFIG.AUTO_RESUME_MIN}min 后 + 市场状态确认` : '⚪ 已禁用'}\n` +
    `开仓: ${(CONFIG.POSITION_PCT * 100).toFixed(0)}% × 钱包,单仓上限 ${fmtUsd(CONFIG.MAX_POSITION_USD)},最多 ${CONFIG.MAX_OPEN_POSITIONS} 个并发\n` +
    `总敞口上限: ${(CONFIG.TOTAL_EXPOSURE_PCT * 100).toFixed(0)}% × 钱包总值\n\n` +
    `下一步:\n` +
    `1. /agents 查看 agent 状态\n` +
    `2. /pnl 查看 PnL 账本\n` +
    `3. /discover 自动抓 top 池子\n` +
    `4. DRY_RUN=true 时可以放心 /auto on 测试\n\n` +
    `/help 查看所有命令`
  );

  mainLoop();
}

start().catch(async (e) => {
  console.error('Fatal:', e);
  await notify(`💀 Fatal: ${e.message}`);
  process.exit(1);
});

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
