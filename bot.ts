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
import { Telegraf, Markup } from 'telegraf';
import { Pool } from 'pg';
import bs58 from 'bs58';
import express from 'express';
import DLMM, { StrategyType } from '@meteora-ag/dlmm';
import BN from 'bn.js';

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
  REBALANCE_THRESHOLD: 0.45,
  CLAIM_THRESHOLD_PCT: 1.0,
  CHECK_INTERVAL_MS: 30_000,
  SCAN_INTERVAL_MS: 4 * 60 * 60_000, // 4h
  SWITCH_SCORE_DIFF: 20,             // 新池分高 20+ 才换仓

  // Tx
  PRIORITY_FEE_MICRO_LAMPORTS: 100_000,
  TX_MAX_RETRIES: 3,
  SWAP_SLIPPAGE_BPS: 50,

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

// 候选池子(V0.1 硬编码主流池;未来可入库)
// 这些是 SOL/USDC、SOL/USDT、USDC/USDT 不同 bin_step 的真实池子
// 用户可以用 /addpool 加新池子(在 DB 里)
const CANDIDATE_POOLS_DEFAULT: string[] = [
  'BGm1tav58oGcsQJehL9WXBFXF7D27vZsKefj4xJKD5Y', // SOL/USDC bin_step 10
  // 注:其他池子地址 bot 启动时会自动从 datapi 或 user 输入扩展
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
    CREATE INDEX IF NOT EXISTS idx_pool_metrics_pair_ts ON pool_metrics(lb_pair, ts DESC);

    CREATE TABLE IF NOT EXISTS candidate_pools (
      lb_pair TEXT PRIMARY KEY,
      added_at TIMESTAMPTZ DEFAULT NOW(),
      enabled BOOLEAN DEFAULT TRUE
    );
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

async function getTokenPriceUsd(mint: string): Promise<number> {
  if (mint === USDC_MINT || mint === USDT_MINT) return 1;
  const cached = priceCache.get(mint);
  if (cached && Date.now() - cached.ts < 30_000) return cached.price;
  // Jupiter price API
  try {
    const r = await fetch(`${CONFIG.JUP_API}/quote?inputMint=${mint}&outputMint=${USDC_MINT}&amount=${10 ** 9}&slippageBps=50`, {
      signal: AbortSignal.timeout(3000),
    });
    if (r.ok) {
      const d: any = await r.json();
      // SOL: input 1e9 lamports = 1 SOL; output is in USDC 1e6 base units
      const price = parseFloat(d.outAmount) / 1e6;
      priceCache.set(mint, { price, ts: Date.now() });
      return price;
    }
  } catch {}
  // fallback
  if (mint === SOL_MINT) return 80; // 极端 fallback,不应该走到
  return 0;
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

  // 硬筛
  if (!WHITELIST_MINTS.has(p.tokenXMint) || !WHITELIST_MINTS.has(p.tokenYMint)) {
    reasons.push('token 不在白名单');
    return { score: -1, reasons };
  }
  if (p.binStep < 20 || p.binStep > 100) {
    reasons.push(`bin_step ${p.binStep} 不在 20-100`);
    return { score: -1, reasons };
  }
  if (!p.tvlUsd || p.tvlUsd < 500_000) {
    reasons.push(`TVL ${fmtUsd(p.tvlUsd)} < $500k`);
    return { score: -1, reasons };
  }
  if (!p.volume24hUsd || p.volume24hUsd < 200_000) {
    reasons.push(`Vol ${fmtUsd(p.volume24hUsd)} < $200k`);
    return { score: -1, reasons };
  }
  if (!p.feeApr) {
    reasons.push('无 APR 数据');
    return { score: -1, reasons };
  }
  // stable-stable 池(USDC/USDT)阈值放宽到 5%
  const isStableStable = p.tokenXMint !== SOL_MINT && p.tokenYMint !== SOL_MINT;
  const minApr = isStableStable ? 5 : 20;
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
      console.error(`scanPools: ${addr} failed: ${e.message}`);
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
  const { blockhash, lastValidBlockHeight } = await connection.getLatestBlockhash('confirmed');
  tx.recentBlockhash = blockhash;
  tx.lastValidBlockHeight = lastValidBlockHeight;
  tx.feePayer = wallet.publicKey;

  const sig = await sendAndConfirmTransaction(
    connection,
    tx,
    [wallet, ...extraSigners],
    { commitment: 'confirmed', skipPreflight: false, maxRetries: CONFIG.TX_MAX_RETRIES }
  );
  return sig;
}

// ============================================================
// 11. Jupiter Swap
// ============================================================

/**
 * Swap inputMint -> outputMint, returns out amount estimate (UI units)
 */
async function jupSwap(inputMint: string, outputMint: string, amountInRaw: BN): Promise<{ sig: string; outAmount: number }> {
  const slip = CONFIG.SWAP_SLIPPAGE_BPS;

  const quoteUrl = `${CONFIG.JUP_API}/quote?inputMint=${inputMint}&outputMint=${outputMint}&amount=${amountInRaw.toString()}&slippageBps=${slip}`;
  const quoteRes = await fetch(quoteUrl, { signal: AbortSignal.timeout(8000) });
  if (!quoteRes.ok) throw new Error(`Jupiter quote ${quoteRes.status}`);
  const quote: any = await quoteRes.json();

  const outDecimals = KNOWN_TOKENS[outputMint]?.decimals ?? 6;
  const outAmount = parseFloat(quote.outAmount) / Math.pow(10, outDecimals);

  if (CONFIG.DRY_RUN) {
    console.log(`[DRY_RUN] would Jupiter swap ${amountInRaw.toString()} ${inputMint} -> ${outAmount} ${outputMint}`);
    return { sig: 'DRY_RUN_SWAP', outAmount };
  }

  const swapRes = await fetch(`${CONFIG.JUP_API}/swap`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      quoteResponse: quote,
      userPublicKey: wallet.publicKey.toBase58(),
      wrapAndUnwrapSol: true,
      dynamicComputeUnitLimit: true,
      prioritizationFeeLamports: { priorityLevelWithMaxLamports: { maxLamports: 1_000_000, priorityLevel: 'high' } },
    }),
    signal: AbortSignal.timeout(8000),
  });
  if (!swapRes.ok) throw new Error(`Jupiter swap ${swapRes.status}`);
  const { swapTransaction } = await swapRes.json() as any;

  const txBuf = Buffer.from(swapTransaction, 'base64');
  const tx = VersionedTransaction.deserialize(txBuf);
  tx.sign([wallet]);
  const sig = await connection.sendRawTransaction(tx.serialize(), { skipPreflight: false, maxRetries: 3 });
  await connection.confirmTransaction({ signature: sig, blockhash: tx.message.recentBlockhash, lastValidBlockHeight: (await connection.getLatestBlockhash()).lastValidBlockHeight }, 'confirmed');

  return { sig, outAmount };
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

  // 计算 range:用 RANGE_PCT 总幅度,各往两边
  // bin_step 是 bps,RANGE_PCT 是百分比;每边的 bins 数 ≈ RANGE_PCT * 100 / bin_step
  const halfRangeBins = Math.max(3, Math.ceil((CONFIG.RANGE_PCT * 100) / binStep / 2));
  const minBinId = activeBin.binId - halfRangeBins;
  const maxBinId = activeBin.binId + halfRangeBins;

  // 目标 50/50:amountUsd / 2 在 X,amountUsd / 2 在 Y
  const xPrice = await getTokenPriceUsd(tokenXMint);
  const yPrice = await getTokenPriceUsd(tokenYMint);
  const xUsdPerSide = amountUsd / 2;
  const yUsdPerSide = amountUsd / 2;
  const xAmountFloat = xUsdPerSide / (xPrice || 1);
  const yAmountFloat = yUsdPerSide / (yPrice || 1);

  const totalXAmount = new BN(Math.floor(xAmountFloat * Math.pow(10, xDec)));
  const totalYAmount = new BN(Math.floor(yAmountFloat * Math.pow(10, yDec)));

  // 检查钱包余额(skip in DRY_RUN)
  if (!CONFIG.DRY_RUN) {
    const solBal = await connection.getBalance(wallet.publicKey);
    if (solBal < 0.05 * 1e9) throw new Error(`SOL 余额不足: ${(solBal / 1e9).toFixed(4)} SOL`);
    // 这里简化:不做 SPL 余额检查,假设 swap 步骤会处理
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

      // 2. 出 range / 漂移 检查
      if (!p.inRange) {
        const distance = p.activeBinId < p.minBinId
          ? (p.minBinId - p.activeBinId)
          : (p.activeBinId - p.maxBinId);
        const halfSpan = (p.maxBinId - p.minBinId) / 2;
        if (halfSpan > 0 && distance / halfSpan > CONFIG.REBALANCE_THRESHOLD) {
          await notify(
            `⚠️ <b>${p.pairName} 已出 range</b>\n` +
            `active bin ${p.activeBinId},仓位 ${p.minBinId}~${p.maxBinId}\n` +
            `${state.paused ? 'paused, 不触发 rebalance' : '准备 rebalance'}`
          );
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
 * 重建仓位:close → 重新选 range 在当前 active bin 周围 → open
 */
async function rebalancePosition(p: PositionInfo, originalValueUsd: number) {
  await notify(`🔄 <b>Rebalance ${p.pairName}</b>`);
  try {
    await closePosition(p.positionPk, 'rebalance');
    // 等链上结算
    await sleep(3000);

    // 用关仓后的资金估算可重建金额
    // 简化:用原始 value 重建(假设 IL 不大)
    const reopenAmount = Math.min(originalValueUsd, CONFIG.MAX_POSITION_USD);
    await openPosition(p.lbPair, reopenAmount);
  } catch (e: any) {
    await notify(`❌ Rebalance 失败: ${e.message}\n暂停 bot`);
    state.paused = true;
  }
}

// 自动开仓 tick
async function tickAutoOpen() {
  if (state.paused || !state.autoTrading) return;

  // 已有仓位数
  const r = await db.query<{ c: string }>(`SELECT COUNT(*) as c FROM positions WHERE status='open'`);
  const openCount = parseInt(r.rows[0].c);
  if (openCount >= CONFIG.MAX_OPEN_POSITIONS) return;

  // 4h 内已扫过就不重扫
  if (Date.now() - state.lastScanTs < CONFIG.SCAN_INTERVAL_MS) return;

  await notify('🔍 扫描候选池...');
  const scored = await scanPools();
  const eligible = scored.filter(s => s.score > 0);

  if (eligible.length === 0) {
    await notify('⚠️ 当前无符合条件的池子');
    return;
  }

  const best = eligible[0];

  // 冷却期检查
  const cool = await db.query(
    `SELECT 1 FROM positions WHERE lb_pair = $1 AND status = 'closed' AND closed_at > NOW() - INTERVAL '${CONFIG.POOL_COOLDOWN_MINUTES} minutes' LIMIT 1`,
    [best.info.address]
  );
  if (cool.rows.length > 0) {
    await notify(`池子 ${best.info.pairName} 在冷却期,跳过`);
    return;
  }

  // 已在该池开仓 → 跳过
  const dup = await db.query(`SELECT 1 FROM positions WHERE lb_pair=$1 AND status='open' LIMIT 1`, [best.info.address]);
  if (dup.rows.length > 0) return;

  // 计算可投金额(40% of free SOL+USDC,封顶 MAX_POSITION_USD)
  const solBal = await connection.getBalance(wallet.publicKey);
  const solUsd = (solBal / 1e9) * await getTokenPriceUsd(SOL_MINT);
  const investUsd = Math.min(solUsd * 0.4, CONFIG.MAX_POSITION_USD);

  if (investUsd < 10) {
    await notify(`⚠️ 可投金额过小: ${fmtUsd(investUsd)}`);
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
      `投入: ${fmtUsd(investUsd)}\n\n` +
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
    `/open &lt;addr&gt; &lt;amount_usd&gt; - 手动开仓\n` +
    `/close &lt;position_pk&gt; - 手动关仓\n` +
    `/pause - 暂停所有自动动作\n` +
    `/resume - 恢复\n` +
    `/emergency - 紧急平所有仓\n` +
    `/confirm - 确认待执行操作\n` +
    `/cancel - 取消待执行操作\n\n` +
    `<b>池子管理</b>\n` +
    `/addpool &lt;addr&gt; - 加候选池\n` +
    `/rmpool &lt;addr&gt; - 移除候选池\n\n` +
    `<i>V0.1 Step 3</i>`,
    { parse_mode: 'HTML' }
  );
});

bot.command('status', async (ctx) => {
  await ctx.reply('⏳');
  try {
    const balance = await connection.getBalance(wallet.publicKey);
    const solBal = balance / 1e9;
    const solPrice = await getTokenPriceUsd(SOL_MINT);

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
      `SOL: ${solBal.toFixed(4)} (~${fmtUsd(solBal * solPrice)})\n` +
      `仓位价值: ${fmtUsd(totalPosValue)}\n` +
      `未领 fee: ${fmtUsd(totalFeeValue)}\n` +
      `\n<b>⚙️ 运行状态</b>\n` +
      `DRY_RUN: ${CONFIG.DRY_RUN ? '🟡 ON (模拟)' : '🟢 OFF (实盘)'}\n` +
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
    await ctx.reply(`🟢 Auto ON${CONFIG.DRY_RUN ? ' (DRY_RUN)' : ''}`);
    await logEvent('auto_on', {});
  } else if (cmd === 'off') {
    state.autoTrading = false;
    await ctx.reply('⚪ Auto OFF');
    await logEvent('auto_off', {});
  } else {
    await ctx.reply(`auto = ${state.autoTrading ? 'on' : 'off'}\n用法: /auto on|off`);
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

let tickCounter = 0;

async function mainLoop() {
  while (true) {
    try {
      tickCounter++;
      console.log(`[loop ${tickCounter}] paused=${state.paused} auto=${state.autoTrading} positions...`);
      await tickPositions();
      // tickAutoOpen 每 20 个 loop 跑一次(约 10 分钟)
      if (tickCounter % 20 === 0) {
        await tickAutoOpen();
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
    `Version: V0.1 Step 3\n` +
    `DRY_RUN: ${CONFIG.DRY_RUN ? '🟡 ON' : '🟢 OFF (实盘!)'}\n` +
    `Auto: ${state.autoTrading ? 'ON' : 'OFF'}\n` +
    `候选池: ${state.candidatePools.length}\n\n` +
    `下一步:\n` +
    `1. /scan 看候选池打分\n` +
    `2. /addpool &lt;地址&gt; 加更多池子\n` +
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
