/**
 * Meteora Router - DLMM Auto Rebalance Bot
 * V0.1 - Step 2 (fixed): SDK-first reads + API fallback
 */

import 'dotenv/config';
import { Connection, Keypair, PublicKey } from '@solana/web3.js';
import { Telegraf } from 'telegraf';
import { Pool } from 'pg';
import bs58 from 'bs58';
import express from 'express';
import DLMM from '@meteora-ag/dlmm';

// ============ 配置层 ============
const CONFIG = {
  RPC_URL: process.env.HELIUS_RPC_URL || 'https://api.mainnet-beta.solana.com',
  WALLET_PRIVATE_KEY: process.env.WALLET_PRIVATE_KEY || '',
  TG_BOT_TOKEN: process.env.TG_BOT_TOKEN || '',
  TG_OWNER_ID: parseInt(process.env.TG_OWNER_ID || '0'),
  DATABASE_URL: process.env.DATABASE_URL || '',

  // 真实 SOL/USDC DLMM 池(从 meteora.ag 验证得到)
  POOL_SOL_USDC: 'BGm1tav58oGcsQJehL9WXBFXF7D27vZsKefj4xJKD5Y',
  RANGE_PCT: 10,
  REBALANCE_THRESHOLD: 0.45,
  CLAIM_THRESHOLD_PCT: 1.0,
  CHECK_INTERVAL_MS: 30_000,

  // Meteora API hosts(优先用新的,失败 fallback 到旧的;再失败就跳过)
  METEORA_API_HOSTS: [
    'https://dlmm.datapi.meteora.ag',
    'https://dlmm-api.meteora.ag',
  ],

  PORT: parseInt(process.env.PORT || '3000'),
};

// 常用 token mint
const SOL_MINT = 'So11111111111111111111111111111111111111112';
const USDC_MINT = 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v';

// ============ 初始化 ============
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

// ============ DB Schema ============
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
      ts TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_pool_metrics_pair_ts ON pool_metrics(lb_pair, ts DESC);
  `);
  console.log('🗄️  DB schema ready');
}

async function logEvent(type: string, payload: any = {}) {
  try {
    await db.query('INSERT INTO events(type, payload) VALUES($1, $2)', [type, payload]);
  } catch (e: any) {
    console.error(`Failed to log event: ${e.message}`);
  }
}

// ============ 通知层 ============
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

// ============ Token symbol 简表(避免每次去链上查 metadata) ============
const KNOWN_TOKENS: Record<string, { symbol: string; decimals: number }> = {
  [SOL_MINT]:  { symbol: 'SOL', decimals: 9 },
  [USDC_MINT]: { symbol: 'USDC', decimals: 6 },
  'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB': { symbol: 'USDT', decimals: 6 },
  'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN':  { symbol: 'JUP', decimals: 6 },
  'jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL':  { symbol: 'JTO', decimals: 9 },
};

function tokenSymbol(mint: string): string {
  return KNOWN_TOKENS[mint]?.symbol || `${mint.slice(0, 4)}...`;
}

// ============ DLMM 读取层 ============

interface PoolInfo {
  address: string;
  pairName: string;
  tokenXMint: string;
  tokenYMint: string;
  tokenXSymbol: string;
  tokenYSymbol: string;
  binStep: number;
  baseFeePct: number;
  activeBinId: number;
  activePrice: number;     // tokenY per tokenX,UI 价格
  reserveX: number;        // 链上 X 储备(已除 decimals)
  reserveY: number;        // 链上 Y 储备(已除 decimals)
  // 以下来自 datapi(可能为空)
  tvlUsd?: number;
  volume24hUsd?: number;
  fees24hUsd?: number;
  feeApr?: number;
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
  unclaimedFeeX: string;
  unclaimedFeeY: string;
}

/**
 * 从 SDK 直接读池子基本信息(不依赖 datapi)
 */
async function getPoolInfo(lbPair: string): Promise<PoolInfo> {
  const dlmmPool = await DLMM.create(connection, new PublicKey(lbPair));
  const activeBin = await dlmmPool.getActiveBin();

  const tokenXMint = dlmmPool.tokenX.publicKey.toBase58();
  const tokenYMint = dlmmPool.tokenY.publicKey.toBase58();
  const xSym = tokenSymbol(tokenXMint);
  const ySym = tokenSymbol(tokenYMint);

  const binStep = dlmmPool.lbPair.binStep;
  const activePrice = parseFloat(
    dlmmPool.fromPricePerLamport(Number(activeBin.price))
  );

  // 链上储备(用 SDK 暴露的 reserve 字段;不同 SDK 版本字段位置可能略不同,做容错)
  let reserveX = 0;
  let reserveY = 0;
  try {
    const xDec = (dlmmPool.tokenX as any).decimal ?? KNOWN_TOKENS[tokenXMint]?.decimals ?? 9;
    const yDec = (dlmmPool.tokenY as any).decimal ?? KNOWN_TOKENS[tokenYMint]?.decimals ?? 6;
    const rxRaw = (dlmmPool.tokenX as any).amount;
    const ryRaw = (dlmmPool.tokenY as any).amount;
    if (rxRaw !== undefined) reserveX = Number(rxRaw) / Math.pow(10, xDec);
    if (ryRaw !== undefined) reserveY = Number(ryRaw) / Math.pow(10, yDec);
  } catch {}

  // base fee 从 lbPair 配置算出
  // base_fee_rate = base_factor * bin_step * 10 (basis points / 10000 = pct)
  const baseFactor = Number(dlmmPool.lbPair.parameters.baseFactor);
  const baseFeePct = (baseFactor * binStep) / 1_000_000 * 100; // ratio → pct

  const info: PoolInfo = {
    address: lbPair,
    pairName: `${xSym}/${ySym}`,
    tokenXMint,
    tokenYMint,
    tokenXSymbol: xSym,
    tokenYSymbol: ySym,
    binStep,
    baseFeePct,
    activeBinId: activeBin.binId,
    activePrice,
    reserveX,
    reserveY,
  };

  // 选填:从 datapi 拿 24h 数据(失败就跳过,不阻塞主流程)
  for (const host of CONFIG.METEORA_API_HOSTS) {
    try {
      const r = await fetch(`${host}/pair/${lbPair}`, {
        signal: AbortSignal.timeout(3000),
      });
      if (!r.ok) continue;
      const d: any = await r.json();
      info.tvlUsd = parseFloat(d.liquidity || '0') || undefined;
      info.volume24hUsd = parseFloat(d.trade_volume_24h || '0') || undefined;
      info.fees24hUsd = parseFloat(d.fees_24h || '0') || undefined;
      info.feeApr = parseFloat(d.apr || '0') || undefined;
      break;
    } catch {
      // try next host
    }
  }

  return info;
}

/**
 * 读取钱包在某个池子里的所有仓位(SDK 链上读)
 */
async function getUserPositions(lbPair?: string): Promise<PositionInfo[]> {
  const results: PositionInfo[] = [];

  if (!lbPair) {
    const r = await db.query<{ lb_pair: string }>(
      `SELECT DISTINCT lb_pair FROM positions WHERE status = 'open'`
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
  const activePrice = parseFloat(
    dlmmPool.fromPricePerLamport(Number(activeBin.price))
  );

  const xSym = tokenSymbol(dlmmPool.tokenX.publicKey.toBase58());
  const ySym = tokenSymbol(dlmmPool.tokenY.publicKey.toBase58());
  const pairName = `${xSym}/${ySym}`;

  for (const pos of userPositions) {
    const minBinId = pos.positionData.lowerBinId;
    const maxBinId = pos.positionData.upperBinId;
    const inRange = activeBin.binId >= minBinId && activeBin.binId <= maxBinId;
    const totalBins = maxBinId - minBinId + 1;

    results.push({
      positionPk: pos.publicKey.toBase58(),
      lbPair,
      pairName,
      binStep,
      activeBinId: activeBin.binId,
      activePrice,
      minBinId,
      maxBinId,
      inRange,
      rangeWidthPct: (Math.pow(1 + binStep / 10000, totalBins) - 1) * 100,
      totalXAmount: pos.positionData.totalXAmount,
      totalYAmount: pos.positionData.totalYAmount,
      unclaimedFeeX: pos.positionData.feeX.toString(),
      unclaimedFeeY: pos.positionData.feeY.toString(),
    });
  }

  return results;
}

// ============ TG 命令 ============
bot.use(async (ctx, next) => {
  if (ctx.from?.id !== CONFIG.TG_OWNER_ID) {
    console.log(`⛔ Unauthorized: ${ctx.from?.id}`);
    return;
  }
  return next();
});

bot.command('ping', async (ctx) => {
  await ctx.reply('🏓 pong');
});

bot.command('status', async (ctx) => {
  await ctx.reply('⏳ 查询中...');
  try {
    // 钱包 SOL 余额
    let solBalance = 'N/A';
    let rpcStatus = '❌';
    try {
      const balance = await connection.getBalance(wallet.publicKey);
      solBalance = (balance / 1e9).toFixed(4);
      rpcStatus = CONFIG.RPC_URL.includes('helius') ? 'Helius ✅' : 'Default ⚠️';
    } catch (e: any) {
      rpcStatus = `❌ RPC 错: ${e.message.slice(0, 80)}`;
    }

    // DB
    const dbR = await db.query('SELECT COUNT(*) as c FROM events');
    const eventCount = parseInt(dbR.rows[0].c);
    const posR = await db.query(`SELECT COUNT(*) as c FROM positions WHERE status='open'`);
    const openCount = parseInt(posR.rows[0].c);

    // 链上仓位(失败不阻塞)
    let posSection = '';
    try {
      const positions = await getUserPositions();
      if (positions.length === 0) {
        posSection = '\n📭 当前无仓位\n';
      } else {
        posSection = `\n<b>📍 链上仓位 (${positions.length})</b>\n`;
        for (const p of positions) {
          const status = p.inRange ? '✅' : '⚠️ 出range';
          posSection +=
            `\n${status} ${p.pairName}\n` +
            `  bin: ${p.minBinId}~${p.maxBinId} (active ${p.activeBinId})\n` +
            `  价格: ${p.activePrice.toFixed(6)}\n`;
        }
      }
    } catch (e: any) {
      posSection = `\n⚠️ 仓位查询失败: ${e.message.slice(0, 100)}\n`;
    }

    await ctx.reply(
      `<b>📊 Status</b>\n\n` +
      `Wallet: <code>${wallet.publicKey.toBase58()}</code>\n` +
      `SOL: ${solBalance}\n` +
      `RPC: ${rpcStatus}\n` +
      `DB: ✅ events=${eventCount}, open=${openCount}\n` +
      posSection +
      `\n<i>V0.1 Step 2 (fixed)</i>`,
      { parse_mode: 'HTML' }
    );
  } catch (e: any) {
    await ctx.reply(`❌ ${e.message}`);
  }
});

/**
 * /pool [addr]  查询池子实时指标
 * 默认 SOL/USDC,可传任意 DLMM lb_pair 地址
 */
bot.command('pool', async (ctx) => {
  const args = ctx.message.text.split(/\s+/).slice(1);
  const addr = args[0] || CONFIG.POOL_SOL_USDC;

  await ctx.reply('⏳ 查询中...');
  try {
    const info = await getPoolInfo(addr);
    const onchainPositions = await getUserPositions(addr);

    const optional = (label: string, val?: number, fmt: 'usd' | 'pct' = 'usd') => {
      if (val === undefined || isNaN(val)) return `${label}: <i>(unavailable)</i>\n`;
      if (fmt === 'pct') return `${label}: ${val.toFixed(2)}%\n`;
      return `${label}: $${val.toLocaleString(undefined, { maximumFractionDigits: 0 })}\n`;
    };

    await ctx.reply(
      `<b>🌊 ${info.pairName}</b>\n\n` +
      `地址: <code>${info.address}</code>\n` +
      `Bin Step: ${info.binStep} bps\n` +
      `Base Fee: ${info.baseFeePct.toFixed(3)}%\n` +
      `Active bin: ${info.activeBinId}\n` +
      `当前价: ${info.activePrice.toFixed(6)} ${info.tokenYSymbol}/${info.tokenXSymbol}\n` +
      `Reserve X: ${info.reserveX.toFixed(2)} ${info.tokenXSymbol}\n` +
      `Reserve Y: ${info.reserveY.toFixed(2)} ${info.tokenYSymbol}\n` +
      `\n<b>24h 数据 (datapi)</b>\n` +
      optional('TVL', info.tvlUsd) +
      optional('Volume', info.volume24hUsd) +
      optional('Fees', info.fees24hUsd) +
      optional('Fee APR', info.feeApr, 'pct') +
      `\n你在此池仓位: ${onchainPositions.length}`,
      { parse_mode: 'HTML' }
    );
  } catch (e: any) {
    await ctx.reply(`❌ ${e.message}`);
  }
});

bot.command('positions', async (ctx) => {
  await ctx.reply('⏳ 扫描链上仓位...');
  try {
    const positions = await getUserPositions();
    if (positions.length === 0) {
      await ctx.reply('📭 当前无开仓');
      return;
    }
    for (const p of positions) {
      const status = p.inRange ? '✅ 在 range' : '⚠️ 出 range';
      await ctx.reply(
        `<b>${p.pairName}</b> — ${status}\n\n` +
        `position: <code>${p.positionPk}</code>\n` +
        `lb_pair: <code>${p.lbPair}</code>\n` +
        `bin step: ${p.binStep}\n` +
        `range: ${p.minBinId} ~ ${p.maxBinId} (宽 ${p.rangeWidthPct.toFixed(2)}%)\n` +
        `active bin: ${p.activeBinId}\n` +
        `当前价: ${p.activePrice.toFixed(6)}\n` +
        `X: ${p.totalXAmount}\n` +
        `Y: ${p.totalYAmount}\n` +
        `未领 fee X: ${p.unclaimedFeeX}\n` +
        `未领 fee Y: ${p.unclaimedFeeY}`,
        { parse_mode: 'HTML' }
      );
    }
  } catch (e: any) {
    await ctx.reply(`❌ ${e.message}`);
  }
});

bot.command('help', async (ctx) => {
  await ctx.reply(
    `<b>🤖 Meteora Router Commands</b>\n\n` +
    `/ping - 测试连接\n` +
    `/status - 钱包 + DB + 仓位概览\n` +
    `/pool [addr] - 池子实时指标 (默认 SOL/USDC)\n` +
    `/positions - 链上仓位详情\n` +
    `/help - 帮助\n` +
    `\n<i>V0.1 Step 2 - 读取层完成</i>`,
    { parse_mode: 'HTML' }
  );
});

// ============ 健康检查 ============
const app = express();
app.get('/health', async (req, res) => {
  try {
    await db.query('SELECT 1');
    res.json({ ok: true, db: 'ok', ts: Date.now() });
  } catch (e: any) {
    res.status(503).json({ ok: false, db: e.message, ts: Date.now() });
  }
});
app.listen(CONFIG.PORT, () => {
  console.log(`🩺 Health endpoint on :${CONFIG.PORT}/health`);
});

// ============ 主循环 ============
async function mainLoop() {
  while (true) {
    try {
      console.log(`[loop] heartbeat ${new Date().toISOString()}`);
    } catch (e: any) {
      console.error(`[loop] error: ${e.message}`);
      await notify(`⚠️ Loop error: ${e.message}`);
    }
    await new Promise(r => setTimeout(r, CONFIG.CHECK_INTERVAL_MS));
  }
}

// ============ 启动 ============
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
  await logEvent('boot', { wallet: wallet.publicKey.toBase58() });

  bot.launch();
  console.log('🤖 TG bot launched');

  await notify(
    `🚀 <b>Meteora Router 上线</b>\n\n` +
    `Wallet: <code>${wallet.publicKey.toBase58()}</code>\n` +
    `Version: V0.1 Step 2 (fixed)\n` +
    `\n发送 /help 查看命令`
  );

  mainLoop();
}

start().catch(async (e) => {
  console.error('Fatal:', e);
  await notify(`💀 Fatal start error: ${e.message}`);
  process.exit(1);
});

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
