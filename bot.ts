/**
 * Meteora Router - DLMM Auto Rebalance Bot
 * V0.1 - Step 1: TG bot skeleton
 */

import 'dotenv/config';
import { Connection, Keypair, PublicKey } from '@solana/web3.js';
import { Telegraf } from 'telegraf';
import { createClient } from '@supabase/supabase-js';
import bs58 from 'bs58';
import express from 'express';

// ============ 配置层 ============
const CONFIG = {
  // Solana
  RPC_URL: process.env.HELIUS_RPC_URL || 'https://api.mainnet-beta.solana.com',
  WALLET_PRIVATE_KEY: process.env.WALLET_PRIVATE_KEY || '',

  // Telegram
  TG_BOT_TOKEN: process.env.TG_BOT_TOKEN || '',
  TG_OWNER_ID: parseInt(process.env.TG_OWNER_ID || '0'), // 只允许这个 user id 用

  // Supabase
  SUPABASE_URL: process.env.SUPABASE_URL || '',
  SUPABASE_KEY: process.env.SUPABASE_SERVICE_KEY || '',

  // Strategy (V1 默认值,后面 step 用)
  POOL_SOL_USDC: 'Cx7yrtKrQQVgptC76fnmcoJg4xDLLR4yJhqsTbW6yLqo', // SOL/USDC bin_step 20
  RANGE_PCT: 10,                  // ±10%
  REBALANCE_THRESHOLD: 0.45,      // 漂移 45% 半区间触发
  CLAIM_THRESHOLD_PCT: 1.0,       // fee > 仓位 1% 触发 claim
  CHECK_INTERVAL_MS: 30_000,      // 30s 巡检

  // Health check
  PORT: parseInt(process.env.PORT || '3000'),
};

// ============ 初始化 ============
function loadKeypair(): Keypair {
  if (!CONFIG.WALLET_PRIVATE_KEY) {
    throw new Error('WALLET_PRIVATE_KEY not set');
  }
  // 支持两种格式: base58 string 或 JSON array
  if (CONFIG.WALLET_PRIVATE_KEY.startsWith('[')) {
    return Keypair.fromSecretKey(Uint8Array.from(JSON.parse(CONFIG.WALLET_PRIVATE_KEY)));
  }
  return Keypair.fromSecretKey(bs58.decode(CONFIG.WALLET_PRIVATE_KEY));
}

const wallet = loadKeypair();
const connection = new Connection(CONFIG.RPC_URL, 'confirmed');
const supabase = createClient(CONFIG.SUPABASE_URL, CONFIG.SUPABASE_KEY);
const bot = new Telegraf(CONFIG.TG_BOT_TOKEN);

console.log(`🤖 Wallet: ${wallet.publicKey.toBase58()}`);

// ============ 通知层 ============
async function notify(msg: string) {
  console.log(`[NOTIFY] ${msg}`);
  if (CONFIG.TG_OWNER_ID) {
    try {
      await bot.telegram.sendMessage(CONFIG.TG_OWNER_ID, msg, { parse_mode: 'HTML' });
    } catch (e: any) {
      console.error(`Failed to send TG: ${e.message}`);
    }
  }
}

// ============ TG 命令 ============
// 权限检查中间件
bot.use(async (ctx, next) => {
  if (ctx.from?.id !== CONFIG.TG_OWNER_ID) {
    console.log(`⛔ Unauthorized access attempt from ${ctx.from?.id}`);
    return; // 静默忽略
  }
  return next();
});

bot.command('ping', async (ctx) => {
  await ctx.reply('🏓 pong');
});

bot.command('status', async (ctx) => {
  const balance = await connection.getBalance(wallet.publicKey);
  const solBalance = (balance / 1e9).toFixed(4);
  await ctx.reply(
    `<b>📊 Status</b>\n\n` +
    `Wallet: <code>${wallet.publicKey.toBase58()}</code>\n` +
    `SOL Balance: ${solBalance}\n` +
    `RPC: ${CONFIG.RPC_URL.includes('helius') ? 'Helius ✅' : 'Default ⚠️'}\n` +
    `Owner ID: ${CONFIG.TG_OWNER_ID}\n` +
    `\n<i>Step 1 - TG bot skeleton</i>`,
    { parse_mode: 'HTML' }
  );
});

bot.command('help', async (ctx) => {
  await ctx.reply(
    `<b>🤖 Meteora Router Commands</b>\n\n` +
    `/ping - 测试连接\n` +
    `/status - 钱包状态\n` +
    `/help - 这个帮助\n` +
    `\n<i>更多命令在后续 step 加入</i>`,
    { parse_mode: 'HTML' }
  );
});

// ============ 健康检查 (给 UptimeRobot) ============
const app = express();
app.get('/health', (req, res) => {
  res.json({ ok: true, ts: Date.now() });
});
app.listen(CONFIG.PORT, () => {
  console.log(`🩺 Health endpoint on :${CONFIG.PORT}/health`);
});

// ============ 主循环 (Step 1 暂时占位) ============
async function mainLoop() {
  while (true) {
    try {
      // Step 4 才填真实巡检逻辑
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
  // 全局异常兜底
  process.on('unhandledRejection', async (err: any) => {
    console.error('Unhandled rejection:', err);
    await notify(`🚨 Unhandled rejection: ${err?.message || err}`);
  });
  process.on('uncaughtException', async (err: any) => {
    console.error('Uncaught exception:', err);
    await notify(`🚨 Uncaught exception: ${err?.message || err}`);
  });

  // 启动 TG bot
  bot.launch();
  console.log('🤖 TG bot launched');

  // 启动通知
  await notify(
    `🚀 <b>Meteora Router 上线</b>\n\n` +
    `Wallet: <code>${wallet.publicKey.toBase58()}</code>\n` +
    `Version: V0.1 Step 1\n` +
    `\n发送 /help 查看命令`
  );

  // 进主循环
  mainLoop();
}

start().catch(async (e) => {
  console.error('Fatal:', e);
  await notify(`💀 Fatal start error: ${e.message}`);
  process.exit(1);
});

// 优雅退出
process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
