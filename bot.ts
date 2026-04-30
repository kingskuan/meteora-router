/**
 * Meteora Router - DLMM Auto Rebalance Bot
 * V0.1 - Step 2: 完整 Schema + 读链上 DLMM 仓位
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

  POOL_SOL_USDC: 'Cx7yrtKrQQVgptC76fnmcoJg4xDLLR4yJhqsTbW6yLqo', // SOL/USDC bin_step 20
  RANGE_PCT: 10,
  REBALANCE_THRESHOLD: 0.45,
  CLAIM_THRESHOLD_PCT: 1.0,
  CHECK_INTERVAL_MS: 30_000,

  METEORA_API: 'https://dlmm-api.meteora.ag',

  PORT: parseInt(process.env.PORT || '3000'),
};

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

// ============ 数据库 Schema ============
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

// ============ DLMM 读取层 ============

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
 * 读取钱包在某个池子里的所有仓位.
 * 不传 lbPair 时,扫描 DB 里 status='open' 的所有池子.
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

  const pairName =
    `${dlmmPool.tokenX.publicKey.toBase58().slice(0, 4)}.../${dlmmPool.tokenY.publicKey.toBase58().slice(0, 4)}...`;

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

/**
 * 读取池子实时指标(走 Meteora 官方 API)
 */
interface PoolMetrics {
  address: string;
  name: string;
  binStep: number;
  baseFeePct: number;
  currentPrice: number;
  liquidity: number;
  volume24h: number;
  fees24h: number;
  feeApr24h: number;
  apr24h: number;
}

async function getPoolMetrics(lbPair: string): Promise<PoolMetrics> {
  const url = `${CONFIG.METEORA_API}/pair/${lbPair}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Meteora API ${res.status}: ${await res.text()}`);
  const data: any = await res.json();

  return {
    address: data.address,
    name: data.name,
    binStep: data.bin_step,
    baseFeePct: parseFloat(data.base_fee_percentage),
    currentPrice: parseFloat(data.current_price),
    liquidity: parseFloat(data.liquidity),
    volume24h: parseFloat(data.trade_volume_24h),
    fees24h: parseFloat(data.fees_24h),
    feeApr24h: parseFloat(data.apr),
    apr24h: parseFloat(data.apy),
  };
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
    const balance = await connection.getBalance(wallet.publicKey);
    const solBalance = (balance / 1e9).toFixed(4);

    const dbR = await db.query('SELECT COUNT(*) as c FROM events');
    const eventCount = parseInt(dbR.rows[0].c);
    const posR = await db.query(`SELECT COUNT(*) as c FROM positions WHERE status='open'`);
    const openCount = parseInt(posR.rows[0].c);

    const positions = await getUserPositions();

    let posSection = '';
    if (positions.length === 0) {
      posSection = '\n📭 当前无仓位\n';
    } else {
      posSection = `\n<b>📍 链上仓位 (${positions.length})</b>\n`;
      for (const p of positions) {
        const status = p.inRange ? '✅' : '⚠️ 出range';
        posSection +=
          `\n${status} ${p.pairName}\n` +
          `  bin: ${p.minBinId}~${p.maxBinId} (active ${p.activeBinId})\n` +
          `  价格: ${p.activePrice.toFixed(6)}\n` +
          `  X: ${p.totalXAmount} | Y: ${p.totalYAmount}\n`;
      }
    }

    await ctx.reply(
      `<b>📊 Status</b>\n\n` +
      `Wallet: <code>${wallet.publicKey.toBase58()}</code>\n` +
      `SOL: ${solBalance}\n` +
      `RPC: ${CONFIG.RPC_URL.includes('helius') ? 'Helius ✅' : 'Default ⚠️'}\n` +
      `DB: ✅ events=${eventCount}, open=${openCount}\n` +
      posSection +
      `\n<i>V0.1 Step 2</i>`,
      { parse_mode: 'HTML' }
    );
  } catch (e: any) {
    await ctx.reply(`❌ ${e.message}`);
  }
});

/**
 * /pool [addr]  查询池子实时指标
 */
bot.command('pool', async (ctx) => {
  const args = ctx.message.text.split(' ').slice(1);
  const addr = args[0] || CONFIG.POOL_SOL_USDC;

  await ctx.reply('⏳ 查询中...');
  try {
    const m = await getPoolMetrics(addr);
    const onchainPositions = await getUserPositions(addr);

    await ctx.reply(
      `<b>🌊 ${m.name}</b>\n\n` +
      `地址: <code>${m.address}</code>\n` +
      `Bin Step: ${m.binStep} bps\n` +
      `Base Fee: ${m.baseFeePct.toFixed(3)}%\n` +
      `当前价: ${m.currentPrice}\n` +
      `TVL: $${m.liquidity.toLocaleString(undefined, { maximumFractionDigits: 0 })}\n` +
      `24h 量: $${m.volume24h.toLocaleString(undefined, { maximumFractionDigits: 0 })}\n` +
      `24h 费: $${m.fees24h.toLocaleString(undefined, { maximumFractionDigits: 0 })}\n` +
      `Fee APR: ${m.feeApr24h.toFixed(2)}%\n` +
      `\n你在此池仓位: ${onchainPositions.length}`,
      { parse_mode: 'HTML' }
    );
  } catch (e: any) {
    await ctx.reply(`❌ ${e.message}`);
  }
});

/**
 * /positions  仅显示链上仓位详情
 */
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
    `\n<i>V0.1 Step 2 - 读取层完成,Step 3 加入开仓</i>`,
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
    `Version: V0.1 Step 2\n` +
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
