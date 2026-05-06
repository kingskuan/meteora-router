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
  HARD_SL_PCT: parseFloat(process.env.HARD_SL_PCT || '8'),
  EMERGENCY_DUMP_PCT: parseFloat(process.env.EMERGENCY_DUMP_PCT || '15'),

  // 策略默认
  RANGE_PCT: 10,
  REBALANCE_THRESHOLD: 0.45,                // 漂移触发阈值(保留作为兜底)
  REBALANCE_COOLDOWN_MS: 5 * 60_000,        // rebalance 后 5 分钟内同 pair 不再触发(防抖)
  SINGLE_SIDED_DUST_TOKEN: 1e-3,            // 某 token amount 低于此值 → 视为 100% single-sided
  CLAIM_THRESHOLD_PCT: 1.0,
  CHECK_INTERVAL_MS: 30_000,
  SCAN_INTERVAL_MS: 30 * 60_000,     // 30min (V0.1 开发期紧凑值,V0.2 生产期可调到 4h)
  AUTO_TICK_EVERY_N_LOOPS: 4,        // 每 4 个 loop (~2 分钟) 触发 tickAutoOpen
  SWITCH_SCORE_DIFF: 20,             // 新池分高 20+ 才换仓

  // Tx
  PRIORITY_FEE_MICRO_LAMPORTS: 100_000,
  TX_MAX_RETRIES: 3,
  SWAP_SLIPPAGE_BPS: 100,                   // 池内 swap minOutAmount 滑点保护(1%)
  SWAP_MAX_IMPACT_PCT: 3.0,                 // 池内 swap priceImpact 放弃门槛(超过则 fallback Jupiter)
  PREFER_JUPITER: false,                    // true: 直接走 Jupiter; false: 先池内试探,失败再 fallback
  JUPITER_SLIPPAGE_BPS: 100,                // Jupiter swap 滑点(1%)

  // V2 健壮性
  MIN_REBALANCE_USD: 10,                    // rebalance 重建下限(低于此值放弃,避免 dust 仓位)
  MAX_REBALANCE_FAILS: 3,                   // 同 pair 连续 rebalance 失败上限,超过才 paused
  LOW_GAS_THRESHOLD_SOL: 0.05,              // SOL 余额低于此值发预警(0.05 SOL ≈ 几十笔 gas)
  GAS_CHECK_EVERY_N_LOOPS: 4,               // 每 N 个 loop 检查一次 SOL 余额(约 2 分钟)

  // API
  METEORA_API_HOSTS: [
    'https://dlmm.datapi.meteora.ag',
    'https://dlmm-api.meteora.ag',
  ],
  GECKOTERMINAL_API: 'https://api.geckoterminal.com/api/v2',
  JUP_API: 'https://quote-api.jup.ag/v6',

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
  `);
  // seed default candidates
  for (const addr of CANDIDATE_POOLS_DEFAULT) {
    await db.query(
      `INSERT INTO candidate_pools(lb_pair) VALUES($1) ON CONFLICT DO NOTHING`,
      [addr]
    );
  }
  console.log('🗄️  DB schema ready');
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
    }
  }
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
  // 1. quote
  const quoteUrl = `${CONFIG.JUP_API}/quote?inputMint=${inputMint}&outputMint=${outputMint}&amount=${amountInRaw.toString()}&slippageBps=${CONFIG.JUPITER_SLIPPAGE_BPS}`;
  const quoteRes = await fetch(quoteUrl, { signal: AbortSignal.timeout(8000) });
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

  // 2. build swap tx
  const swapRes = await fetch(`${CONFIG.JUP_API}/swap`, {
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
  });
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
 */
async function closePosition(positionPk: string, reason: string = 'manual'): Promise<string> {
  const r = await db.query<{ id: number; lb_pair: string }>(
    `SELECT id, lb_pair FROM positions WHERE position_pk = $1 AND status IN ('open','closing')`,
    [positionPk]
  );
  if (r.rows.length === 0) throw new Error(`未找到 open 状态的 position ${positionPk}`);
  const dbId = r.rows[0].id;
  const lbPair = r.rows[0].lb_pair;

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

      if (pnlPct < -CONFIG.HARD_SL_PCT) {
        await notify(
          `🚨 <b>触发 Stop Loss</b>\n` +
          `${p.pairName} PnL: ${pnlPct.toFixed(2)}%\n` +
          `开仓值: ${fmtUsd(openValueUsd)} 现值(含费): ${fmtUsd(currentValueWithFee)}\n` +
          `自动平仓 + 暂停 bot`
        );
        try {
          await closePosition(p.positionPk, `SL ${pnlPct.toFixed(2)}%`);
        } catch (e: any) {
          await notify(`❌ SL 平仓失败: ${e.message}`);
        }
        state.paused = true;
        continue;
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

      // 3. fee 复投
      const feePctOfPosition = openValueUsd > 0 ? (feeUsd / openValueUsd) * 100 : 0;
      if (feePctOfPosition > CONFIG.CLAIM_THRESHOLD_PCT && !state.paused) {
        await notify(
          `💰 <b>${p.pairName} 累计 fee 达阈值</b>\n` +
          `fee: ${fmtUsd(feeUsd)} (${feePctOfPosition.toFixed(2)}% of position)\n` +
          `claiming...`
        );
        try {
          const sig = await claimFees(p.positionPk);
          await db.query(
            `UPDATE positions SET fees_claimed_usd = fees_claimed_usd + $2 WHERE id = $1`,
            [dbId, feeUsd]
          );
          await notify(`✅ claim 成功: <code>${sig}</code>`);
        } catch (e: any) {
          await notify(`❌ claim 失败: ${e.message}`);
        }
      }
    } catch (e: any) {
      console.error(`tickPositions ${p.positionPk}: ${e.message}`);
    }
  }
}

/**
 * 重建仓位 (V2):
 * - close → 读关仓后实际钱包余额 → 折算 USD → 用实际值开仓 (而非原始 originalValueUsd)
 * - 报告 IL: 实际值 vs 原始值
 * - 失败不立即 paused: 累计 ≥ MAX_REBALANCE_FAILS 才 paused
 */
async function rebalancePosition(p: PositionInfo, originalValueUsd: number) {
  const lbPair = p.lbPair;
  await notify(`🔄 <b>Rebalance ${p.pairName}</b>`);
  try {
    await closePosition(p.positionPk, 'rebalance');
    await sleep(3000); // 等链上结算

    // ============ V2: 用关仓后实际余额估算重建金额 ============
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

    // 读钱包余额(SOL 走原生 lamports,SPL 走 ATA)
    const xBal = xMint === SOL_MINT
      ? (await connection.getBalance(wallet.publicKey)) / 1e9
      : await getSplBalance(xMint, xDec);
    const yBal = yMint === SOL_MINT
      ? (await connection.getBalance(wallet.publicKey)) / 1e9
      : await getSplBalance(yMint, yDec);

    // SOL 留 0.1 给 gas/rent (跟 openPosition 一致)
    const xUsable = xMint === SOL_MINT ? Math.max(0, xBal - 0.1) : xBal;
    const yUsable = yMint === SOL_MINT ? Math.max(0, yBal - 0.1) : yBal;

    const xPrice = await getTokenPriceUsd(xMint);
    const yPrice = await getTokenPriceUsd(yMint);
    const actualUsd = xUsable * xPrice + yUsable * yPrice;

    // 安全边界:
    // - 上限: min(原始值 × 1.1, MAX_POSITION_USD) — 防止吞噬钱包其他来源资金
    // - 下限: MIN_REBALANCE_USD — 太小没意义,gas 都赚不回
    const upperBound = Math.min(originalValueUsd * 1.1, CONFIG.MAX_POSITION_USD);
    const reopenAmount = Math.min(actualUsd, upperBound);

    if (reopenAmount < CONFIG.MIN_REBALANCE_USD) {
      throw new Error(
        `重建金额 ${fmtUsd(reopenAmount)} < 最小阈值 ${fmtUsd(CONFIG.MIN_REBALANCE_USD)} (实际余额 ${fmtUsd(actualUsd)})`
      );
    }

    // IL 报告
    const ilDiff = actualUsd - originalValueUsd;
    const ilPct = originalValueUsd > 0 ? (ilDiff / originalValueUsd) * 100 : 0;
    await notify(
      `📊 <b>关仓后实际余额</b>: ${fmtUsd(actualUsd)}\n` +
      `(原 ${fmtUsd(originalValueUsd)}, IL ${ilPct >= 0 ? '+' : ''}${ilPct.toFixed(2)}%)\n` +
      `重建金额: ${fmtUsd(reopenAmount)}`
    );

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
        `已暂停 bot,需手动 /resume`
      );
      state.paused = true;
      rebalanceFailCount.delete(lbPair); // 重置,避免恢复后再次秒爆
    } else {
      await notify(
        `⚠️ Rebalance 失败 ${fails}/${CONFIG.MAX_REBALANCE_FAILS}: ${e.message}\n` +
        `不暂停 bot,${CONFIG.REBALANCE_COOLDOWN_MS / 60000} 分钟 cooldown 后下个 tick 自动重试`
      );
      // 不 paused, 等 cooldown 过后自然重试
    }
  }
}

// 自动开仓 tick
async function tickAutoOpen(verbose: boolean = false) {
  if (state.paused || !state.autoTrading) return;

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
  let investUsd = Math.min(wallet_.totalUsableUsd * 0.4, CONFIG.MAX_POSITION_USD);

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

  if (investUsd < 5) {
    await notify(
      `⚠️ <b>可投金额过小</b>: ${fmtUsd(investUsd)}\n\n` +
      `钱包详情:\n` +
      `SOL: ${wallet_.solBalance.toFixed(4)} (~${fmtUsd(wallet_.solUsd)},扣 ${wallet_.gasReserveSol} SOL gas)\n` +
      `USDC: ${fmtUsd(wallet_.usdcBalance)}\n` +
      `USDT: ${fmtUsd(wallet_.usdtBalance)}\n` +
      `总可用: ${fmtUsd(wallet_.totalUsableUsd)}\n` +
      `40% 投入 = ${fmtUsd(wallet_.totalUsableUsd * 0.4)}`
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
    `/pnl - 盈亏报表\n\n` +
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
    `<i>V0.1.1</i>`,
    { parse_mode: 'HTML' }
  );
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
    const r = await db.query<{
      pair_name: string;
      open_value_usd: string;
      fees_claimed_usd: string;
      il_realized_usd: string;
      status: string;
      opened_at: Date;
      closed_at: Date | null;
    }>(`SELECT pair_name, open_value_usd, fees_claimed_usd, il_realized_usd, status, opened_at, closed_at FROM positions ORDER BY opened_at DESC LIMIT 20`);

    let totalFees = 0;
    let totalIl = 0;
    let openCount = 0;
    let closedCount = 0;
    for (const row of r.rows) {
      totalFees += parseFloat(row.fees_claimed_usd || '0');
      totalIl += parseFloat(row.il_realized_usd || '0');
      if (row.status === 'open') openCount++;
      else if (row.status === 'closed') closedCount++;
    }

    let msg = `<b>💰 PnL Summary</b>\n\n` +
      `开仓中: ${openCount}, 已关: ${closedCount}\n` +
      `已收 fee: ${fmtUsd(totalFees)}\n` +
      `已实现 IL: ${fmtUsd(-totalIl)}\n` +
      `净: ${fmtUsd(totalFees - totalIl)}\n\n` +
      `<b>最近 20 笔</b>\n`;
    for (const row of r.rows) {
      const tag = row.status === 'open' ? '🟢' : '⚪';
      msg += `${tag} ${row.pair_name} ${fmtUsd(parseFloat(row.open_value_usd))} fee=${fmtUsd(parseFloat(row.fees_claimed_usd))}\n`;
    }
    await ctx.reply(msg, { parse_mode: 'HTML' });
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

let tickCounter = 0;

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

  await notify(
    `🚀 <b>Meteora Router 上线</b>\n\n` +
    `Wallet: <code>${wallet.publicKey.toBase58()}</code>\n` +
    `Version: V0.6.1 (rebalance hardening + jupiter router + SOL-cap removed)\n` +
    `DRY_RUN: ${CONFIG.DRY_RUN ? '🟡 ON' : '🟢 OFF (实盘!)'}\n` +
    `Auto: ${state.autoTrading ? 'ON' : 'OFF'}\n` +
    `候选池: ${state.candidatePools.length}\n\n` +
    `下一步:\n` +
    `1. /discover 自动抓 top 池子(推荐)\n` +
    `2. /scan 看候选池打分\n` +
    `3. DRY_RUN=true 时可以放心 /auto on 测试\n` +
    `4. 验证逻辑没问题后 Railway 改 DRY_RUN=false 上实盘\n\n` +
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
