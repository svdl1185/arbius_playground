function showToast(message, type = 'error') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  // Sanitize message to prevent XSS
  const sanitizedMessage = sanitizeString(message);

  const icons = {
    error: '<i class="fas fa-times-circle"></i>',
    success: '<i class="fas fa-check-circle"></i>',
    info: '<i class="fas fa-info-circle"></i>',
    warning: '<i class="fas fa-exclamation-triangle"></i>',
  };
  const colors = {
    error: '#ef4444',
    success: '#22c55e',
    info: '#3b82f6',
    warning: '#f59e42',
  };

  const toast = document.createElement('div');
  toast.className = 'arbius-toast';
  toast.style = `
    background: ${colors[type] || '#232323'};
    color: #fff;
    padding: 16px 24px;
    border-radius: 12px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.18);
    font-size: 1rem;
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 220px;
    max-width: 400px;
    animation: fadeIn 0.3s;
    position: relative;
  `;
  toast.innerHTML = `
    <span style="font-size:1.3rem;">${icons[type] || ''}</span>
    <span style="flex:1;">${sanitizedMessage}</span>
    <button style="background:none;border:none;color:#fff;font-size:1.2rem;cursor:pointer;position:absolute;top:8px;right:12px;" aria-label="Close">&times;</button>
  `;

  // Dismiss on click
  toast.querySelector('button').onclick = () => container.removeChild(toast);

  container.appendChild(toast);

  // Auto-dismiss after 5s
  setTimeout(() => {
    if (container.contains(toast)) container.removeChild(toast);
  }, 5000);
}

// Security utility functions
function sanitizeString(str) {
  if (typeof str !== 'string') return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function isValidEthereumAddress(address) {
  if (!address || typeof address !== 'string') return false;
  return /^0x[a-fA-F0-9]{40}$/.test(address);
}

function isValidSignature(signature) {
  if (!signature || typeof signature !== 'string') return false;
  return /^0x[a-fA-F0-9]{130}$/.test(signature);
}

function validateInput(input, maxLength = 1000) {
  if (!input || typeof input !== 'string') return false;
  if (input.length > maxLength) return false;
  // Check for suspicious patterns
  const suspiciousPatterns = [
    /<script/i,
    /javascript:/i,
    /data:text\/html/i,
    /vbscript:/i,
    /on\w+\s*=/i
  ];
  return !suspiciousPatterns.some(pattern => pattern.test(input));
}

function generateSecureMessage() {
  const timestamp = new Date().toISOString();
  const nonce = Math.random().toString(36).substring(2, 15);
  return `Welcome to Arbius Playground!\n\nPlease sign this message to connect your wallet.\n\nTimestamp: ${timestamp}\nNonce: ${nonce}`;
}

class MetaMaskManager {
    constructor() {
        this.isConnected = false;
        this.account = null;
        this.arbitrumChainId = '0xa4b1'; // Arbitrum One
        this.arbitrumTestnetChainId = '0x66eed'; // Arbitrum Sepolia
        this.aiusContractAddress = '0x4a24B101728e07A52053c13FB4dB2BcF490CAbc3';
        this.ethersLoaded = false;
        this.connectionAttempts = 0;
        this.maxConnectionAttempts = 3;
        this.init();
    }

    async init() {
        if (typeof window.ethereum !== 'undefined') {
            this.setupEventListeners();
            await this.checkBackendAuthStatus(); // Only trust backend
            
            // Initialize dropdown functionality
            this.initializeWalletDropdowns();
            
            // Check network status periodically if connected
            if (this.isConnected) {
                await this.updateNetworkStatusUI();
                // Check network status every 30 seconds
                setInterval(async () => {
                    if (this.isConnected) {
                        await this.updateNetworkStatusUI();
                    }
                }, 30000);
            }
        } else {
            showToast('MetaMask is not installed. Please install MetaMask to use this feature.', 'warning');
        }
    }

    // Test method for debugging network status
    async testNetworkStatus() {
        console.log('Testing network status...');
        const status = await this.checkNetworkStatus();
        console.log('Network status:', status);
        
        if (status.isPaused) {
            showToast('Network is currently paused for maintenance.', 'warning');
        } else {
            showToast('Network is active and ready.', 'success');
        }
        
        return status;
    }

    setupEventListeners() {
        // Listen for account changes
        window.ethereum.on('accountsChanged', async (accounts) => {
            if (accounts.length === 0) {
                this.disconnect();
            } else {
                this.account = accounts[0];
                await this.updateUI();
                this.storeConnectionState();
            }
        });

        // Listen for chain changes
        window.ethereum.on('chainChanged', async (chainId) => {
            await this.switchToArbitrum();
            // Update balance after network change
            if (this.isConnected) {
                await this.updateBalanceUI();
            }
        });
    }

    async checkConnection() {
        try {
            const accounts = await window.ethereum.request({ method: 'eth_accounts' });
            if (accounts.length > 0) {
                this.account = accounts[0];
                this.isConnected = true;
                await this.switchToArbitrum();
            } else {
                this.isConnected = false;
                this.account = null;
            }
        } catch (error) {
            this.isConnected = false;
            this.account = null;
        }
    }

    checkStoredConnection() {
        // No longer used: always trust backend
    }

    async checkBackendAuthStatus() {
        try {
            const response = await fetch('/api/check-auth-status/', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (response.ok) {
                const data = await response.json();
                if (data.success && data.authenticated && data.address) {
                    this.account = data.address;
                    this.isConnected = true;
                } else {
                    this.isConnected = false;
                    this.account = null;
                }
            } else {
                this.isConnected = false;
                this.account = null;
            }
        } catch (error) {
            this.isConnected = false;
            this.account = null;
        }
        this.updateUI();
        this.storeConnectionState();
    }

    storeConnectionState() {
        const state = {
            isConnected: this.isConnected,
            account: this.account,
            timestamp: Date.now()
        };
        localStorage.setItem('metamask_connection', JSON.stringify(state));
    }

    clearStoredConnectionState() {
        localStorage.removeItem('metamask_connection');
    }

    async connect() {
        try {
            // Check connection attempts
            if (this.connectionAttempts >= this.maxConnectionAttempts) {
                showToast('Too many connection attempts. Please try again later.', 'error');
                return;
            }
            this.connectionAttempts++;

            // Show loading state
            this.setConnectButtonLoading(true);
            
            const accounts = await window.ethereum.request({ 
                method: 'eth_requestAccounts' 
            });
            
            if (!accounts || accounts.length === 0) {
                throw new Error('No accounts found');
            }
            
            this.account = accounts[0];
            
            // Validate account address
            if (!isValidEthereumAddress(this.account)) {
                throw new Error('Invalid account address');
            }
            
            this.isConnected = true;
            await this.switchToArbitrum();
            await this.requestSignature();
            // After signature, always check backend for true state
            await this.checkBackendAuthStatus();
            
            // Reset connection attempts on success
            this.connectionAttempts = 0;
        } catch (error) {
            this.isConnected = false;
            this.account = null;
            this.updateUI();
            this.storeConnectionState();
            showToast('Failed to connect wallet. Please try again.', 'error');
        } finally {
            // Reset loading state
            this.setConnectButtonLoading(false);
        }
    }

    setConnectButtonLoading(loading) {
        const connectBtn = document.getElementById('connect-wallet-btn');
        const connectBtnMobile = document.getElementById('connect-wallet-btn-mobile');
        
        if (loading) {
            if (connectBtn) {
                connectBtn.innerHTML = 'Connecting...';
                connectBtn.disabled = true;
                connectBtn.classList.add('opacity-75', 'cursor-not-allowed');
            }
            if (connectBtnMobile) {
                connectBtnMobile.innerHTML = 'Connecting...';
                connectBtnMobile.disabled = true;
                connectBtnMobile.classList.add('opacity-75', 'cursor-not-allowed');
            }
        } else {
            if (connectBtn) {
                connectBtn.innerHTML = 'Connect';
                connectBtn.disabled = false;
                connectBtn.classList.remove('opacity-75', 'cursor-not-allowed');
            }
            if (connectBtnMobile) {
                connectBtnMobile.innerHTML = 'Connect';
                connectBtnMobile.disabled = false;
                connectBtnMobile.classList.remove('opacity-75', 'cursor-not-allowed');
            }
        }
    }

    async switchToArbitrum() {
        try {
            const chainId = await window.ethereum.request({ method: 'eth_chainId' });
            
            if (chainId !== this.arbitrumChainId && chainId !== this.arbitrumTestnetChainId) {
                await this.addArbitrumNetwork();
                await this.switchNetwork(this.arbitrumChainId);
            }
        } catch (error) {      
            console.error('Error switching network:', error);
            showToast('Failed to switch to Arbitrum network.', 'error');
        }
    }

    async addArbitrumNetwork() {
        try {
            await window.ethereum.request({
                method: 'wallet_addEthereumChain',
                params: [{
                    chainId: this.arbitrumChainId,
                    chainName: 'Arbitrum One',
                    nativeCurrency: {
                        name: 'Ether',
                        symbol: 'ETH',
                        decimals: 18
                    },
                    rpcUrls: ['https://arb1.arbitrum.io/rpc'],
                    blockExplorerUrls: ['https://arbiscan.io/']
                }]
            });
        } catch (error) {
            console.error('Error adding Arbitrum network:', error);
        }
    }

    async switchNetwork(chainId) {
        try {
            await window.ethereum.request({
                method: 'wallet_switchEthereumChain',
                params: [{ chainId: chainId }]
            });
        } catch (error) {
            console.error('Error switching network:', error);
        }
    }

    async requestSignature() {
        try {
            const message = generateSecureMessage();
            const signature = await window.ethereum.request({
                method: 'personal_sign',
                params: [message, this.account]
            });
            
            // Validate signature format
            if (!isValidSignature(signature)) {
                throw new Error('Invalid signature format');
            }
            
            await this.verifySignature(message, signature);
        } catch (error) {
            this.isConnected = false;
            this.account = null;
            this.updateUI();
            this.storeConnectionState();
            showToast('Signature request was rejected.', 'error');
        }
    }

    async verifySignature(message, signature) {
        try {
            const response = await fetch('/api/verify-signature/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    address: this.account,
                    message: message,
                    signature: signature
                })
            });
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    showToast('Wallet connected successfully!', 'success');
                } else {
                    this.isConnected = false;
                    this.account = null;
                    this.updateUI();
                    this.storeConnectionState();
                    showToast(data.error || 'Signature verification failed.', 'error');
                }
            } else {
                this.isConnected = false;
                this.account = null;
                this.updateUI();
                this.storeConnectionState();
                showToast('Failed to verify signature.', 'error');
            }
        } catch (error) {
            this.isConnected = false;
            this.account = null;
            this.updateUI();
            this.storeConnectionState();
            showToast('Failed to verify signature.', 'error');
        }
    }

    async disconnect() {
        try {
            // Call backend logout endpoint
            const response = await fetch('/api/logout-wallet/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                }
            });

            if (response.ok) {
                showToast('Wallet disconnected successfully!', 'success');
            }
        } catch (error) {
            console.error('Error logging out:', error);
        }

        this.isConnected = false;
        this.account = null;
        this.updateUI();
        this.clearStoredConnectionState();
    }

    async loadEthers() {
        if (window.ethers) {
            this.ethersLoaded = true;
            return;
        }
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/ethers@5.7.2/dist/ethers.umd.min.js';
            script.onload = () => {
                this.ethersLoaded = true;
                resolve();
            };
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    async fetchAIUSBalance() {
        await this.loadEthers();
        if (!window.ethers || !this.account) return null;
        const provider = new window.ethers.providers.Web3Provider(window.ethereum);
        const erc20Abi = [
            'function balanceOf(address owner) view returns (uint256)',
            'function decimals() view returns (uint8)'
        ];
        const contract = new window.ethers.Contract(this.aiusContractAddress, erc20Abi, provider);
        try {
            const [balance, decimals] = await Promise.all([
                contract.balanceOf(this.account),
                contract.decimals()
            ]);
            return (Number(balance) / Math.pow(10, decimals)).toFixed(4);
        } catch (e) {
            return null;
        }
    }

    async updateBalanceUI() {
        const aiusBalanceIndicator = document.getElementById('aius-balance-indicator');
        const aiusBalanceIndicatorMobile = document.getElementById('aius-balance-indicator-mobile');
        
        if (this.isConnected && this.account) {
            // Show loading state
            if (aiusBalanceIndicator) {
                aiusBalanceIndicator.textContent = 'AIUS: Loading...';
                aiusBalanceIndicator.style.display = 'inline-flex';
            }
            if (aiusBalanceIndicatorMobile) {
                aiusBalanceIndicatorMobile.textContent = 'AIUS: Loading...';
                aiusBalanceIndicatorMobile.style.display = 'inline-flex';
            }
            
            const balance = await this.fetchAIUSBalance();
            if (balance !== null) {
                const formattedBalance = parseFloat(balance).toLocaleString('en-US', {
                    minimumFractionDigits: 0,
                    maximumFractionDigits: 2
                });
                
                if (aiusBalanceIndicator) {
                    aiusBalanceIndicator.textContent = `AIUS: ${formattedBalance}`;
                    aiusBalanceIndicator.style.display = 'inline-flex';
                }
                if (aiusBalanceIndicatorMobile) {
                    aiusBalanceIndicatorMobile.textContent = `AIUS: ${formattedBalance}`;
                    aiusBalanceIndicatorMobile.style.display = 'inline-flex';
                }
            } else {
                // Error state
                if (aiusBalanceIndicator) {
                    aiusBalanceIndicator.textContent = 'AIUS: Error';
                    aiusBalanceIndicator.style.display = 'inline-flex';
                }
                if (aiusBalanceIndicatorMobile) {
                    aiusBalanceIndicatorMobile.textContent = 'AIUS: Error';
                    aiusBalanceIndicatorMobile.style.display = 'inline-flex';
                }
            }
        } else {
            // Hide when not connected
            if (aiusBalanceIndicator) aiusBalanceIndicator.style.display = 'none';
            if (aiusBalanceIndicatorMobile) aiusBalanceIndicatorMobile.style.display = 'none';
        }
    }

    async updateNetworkStatusUI() {
        const networkStatusIndicator = document.getElementById('network-status-indicator');
        const networkStatusText = document.getElementById('network-status-text');
        
        if (!networkStatusIndicator && !networkStatusText) return;
        
        try {
            const status = await this.checkNetworkStatus();
            
            if (status.isPaused) {
                if (networkStatusIndicator) {
                    networkStatusIndicator.className = 'w-2 h-2 rounded-full bg-yellow-500 animate-pulse';
                    networkStatusIndicator.title = 'Network Paused';
                }
                if (networkStatusText) {
                    networkStatusText.textContent = 'Network Paused';
                    networkStatusText.className = 'text-yellow-500 text-xs';
                }
            } else {
                if (networkStatusIndicator) {
                    networkStatusIndicator.className = 'w-2 h-2 rounded-full bg-green-500';
                    networkStatusIndicator.title = 'Network Active';
                }
                if (networkStatusText) {
                    networkStatusText.textContent = 'Network Active';
                    networkStatusText.className = 'text-green-500 text-xs';
                }
            }
        } catch (error) {
            console.error('Error updating network status UI:', error);
            if (networkStatusIndicator) {
                networkStatusIndicator.className = 'w-2 h-2 rounded-full bg-gray-500';
                networkStatusIndicator.title = 'Status Unknown';
            }
            if (networkStatusText) {
                networkStatusText.textContent = 'Status Unknown';
                networkStatusText.className = 'text-gray-500 text-xs';
            }
        }
    }

    async updateUI() {
        const connectBtn = document.getElementById('connect-wallet-btn');
        const connectBtnMobile = document.getElementById('connect-wallet-btn-mobile');
        const disconnectBtn = document.getElementById('disconnect-wallet-btn');
        const disconnectBtnMobile = document.getElementById('disconnect-wallet-btn-mobile');
        const walletConnectedContainer = document.getElementById('wallet-connected-container');
        const walletConnectedMobile = document.getElementById('wallet-connected-mobile');
        const walletDropdownMenu = document.getElementById('wallet-dropdown-menu');
        const walletDropdownMenuMobile = document.getElementById('wallet-dropdown-menu-mobile');
        
        // Hide all by default
        if (connectBtn) connectBtn.style.display = 'inline-flex';
        if (connectBtnMobile) connectBtnMobile.style.display = 'inline-flex';
        if (walletConnectedContainer) walletConnectedContainer.style.display = 'none';
        if (walletConnectedMobile) walletConnectedMobile.style.display = 'none';
        
        // Show correct UI
        if (this.isConnected && this.account) {
            if (connectBtn) connectBtn.style.display = 'none';
            if (connectBtnMobile) connectBtnMobile.style.display = 'none';
            if (walletConnectedContainer) walletConnectedContainer.style.display = 'block';
            if (walletConnectedMobile) walletConnectedMobile.style.display = 'block';
            
            // Update wallet address pills
            const walletAddressPill = document.getElementById('wallet-address-pill');
            const walletAddressPillMobile = document.getElementById('wallet-address-pill-mobile');
            
            const truncatedAddress = `@${this.account.slice(0, 6)}...${this.account.slice(-4)}`;
            
            if (walletAddressPill) walletAddressPill.textContent = truncatedAddress;
            if (walletAddressPillMobile) walletAddressPillMobile.textContent = truncatedAddress;
            
            // Update Arbiscan links
            const arbiscanLinks = document.querySelectorAll('.wallet-dropdown-item[href="#"]');
            const arbiscanUrl = `https://arbiscan.io/address/${this.account}`;
            
            arbiscanLinks.forEach(link => {
                if (link.querySelector('img[src*="arbiscan.io"]')) {
                    link.href = arbiscanUrl;
                    link.target = '_blank';
                    link.rel = 'noopener noreferrer';
                }
            });
            
            // Update Usage links (link to dashboard)
            const usageLinks = document.querySelectorAll('.wallet-dropdown-item[href="#"]');
            const usageUrl = '/dashboard/';
            
            usageLinks.forEach(link => {
                if (link.querySelector('.fas.fa-chart-pie')) {
                    link.href = usageUrl;
                }
            });
            
            // Update network status if connected
            await this.updateNetworkStatusUI();
            
            // Update AIUS balance if connected
            await this.updateBalanceUI();
        }
        
        // Hide dropdown menus by default
        if (walletDropdownMenu) walletDropdownMenu.style.display = 'none';
        if (walletDropdownMenuMobile) walletDropdownMenuMobile.style.display = 'none';
        
        // Re-initialize dropdown functionality after UI update
        this.initializeWalletDropdowns();
    }

    showMetaMaskNotInstalled() {
        const connectBtn = document.getElementById('connect-wallet-btn');
        const connectBtnMobile = document.getElementById('connect-wallet-btn-mobile');
        
        if (connectBtn) {
            connectBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Install MetaMask';
            connectBtn.onclick = () => {
                window.open('https://metamask.io/download/', '_blank');
            };
        }
        
        if (connectBtnMobile) {
            connectBtnMobile.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Install MetaMask';
            connectBtnMobile.onclick = () => {
                window.open('https://metamask.io/download/', '_blank');
            };
        }
    }

    showError(message) {
        // Create a toast notification
        const toast = document.createElement('div');
        toast.className = 'fixed top-24 right-4 bg-red-600/90 backdrop-blur-lg text-white px-6 py-4 rounded-xl shadow-2xl z-50 transform transition-all duration-300 translate-x-full border border-red-500/30';
        toast.innerHTML = `
            <div class="flex items-center gap-3">
                <div class="w-5 h-5 rounded-full bg-red-400 flex items-center justify-center">
                    <i class="fas fa-exclamation text-red-900 text-xs"></i>
                </div>
                <span class="font-medium">${sanitizeString(message)}</span>
            </div>
        `;
        document.body.appendChild(toast);
        
        // Animate in
        setTimeout(() => {
            toast.classList.remove('translate-x-full');
        }, 100);
        
        // Remove after 5 seconds
        setTimeout(() => {
            toast.classList.add('translate-x-full');
            setTimeout(() => {
                document.body.removeChild(toast);
            }, 300);
        }, 5000);
    }

    showSuccess(message) {
        // Create a toast notification
        const toast = document.createElement('div');
        toast.className = 'fixed top-24 right-4 bg-green-600/90 backdrop-blur-lg text-white px-6 py-4 rounded-xl shadow-2xl z-50 transform transition-all duration-300 translate-x-full border border-green-500/30';
        toast.innerHTML = `
            <div class="flex items-center gap-3">
                <div class="w-5 h-5 rounded-full bg-green-400 flex items-center justify-center">
                    <i class="fas fa-check text-green-900 text-xs"></i>
                </div>
                <span class="font-medium">${sanitizeString(message)}</span>
            </div>
        `;
        document.body.appendChild(toast);
        
        // Animate in
        setTimeout(() => {
            toast.classList.remove('translate-x-full');
        }, 100);
        
        // Remove after 5 seconds
        setTimeout(() => {
            toast.classList.add('translate-x-full');
            setTimeout(() => {
                document.body.removeChild(toast);
            }, 300);
        }, 5000);
    }

    getCSRFToken() {
        const name = 'csrftoken';
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    async checkNetworkStatus() {
        try {
            await this.loadEthers();
            if (!window.ethers || !this.account) return { isPaused: false, error: null };
            
            const provider = new window.ethers.providers.Web3Provider(window.ethereum);
            const contractAddress = '0x9b51Ef044d3486A1fB0A2D55A6e0CeeAdd323E66';
            
            // Contract ABI for checking pause status
            const contractAbi = [
                'function paused() view returns (bool)',
                'function owner() view returns (address)'
            ];
            
            const contract = new window.ethers.Contract(contractAddress, contractAbi, provider);
            
            try {
                const isPaused = await contract.paused();
                return { isPaused, error: null };
            } catch (error) {
                console.warn('Could not check pause status:', error);
                return { isPaused: false, error: 'Could not check network status' };
            }
        } catch (error) {
            console.error('Error checking network status:', error);
            return { isPaused: false, error: 'Network status check failed' };
        }
    }

    initializeWalletDropdowns() {
        // Desktop dropdown
        const walletAddressPill = document.getElementById('wallet-address-pill');
        const walletDropdownMenu = document.getElementById('wallet-dropdown-menu');
        
        if (walletAddressPill && walletDropdownMenu) {
            // Remove existing listeners to prevent duplicates
            walletAddressPill.removeEventListener('click', walletAddressPill._dropdownHandler);
            
            walletAddressPill._dropdownHandler = (e) => {
                e.stopPropagation();
                walletDropdownMenu.style.display = walletDropdownMenu.style.display === 'block' ? 'none' : 'block';
            };
            
            walletAddressPill.addEventListener('click', walletAddressPill._dropdownHandler);
        }
        
        // Mobile dropdown
        const walletAddressPillMobile = document.getElementById('wallet-address-pill-mobile');
        const walletDropdownMenuMobile = document.getElementById('wallet-dropdown-menu-mobile');
        
        if (walletAddressPillMobile && walletDropdownMenuMobile) {
            // Remove existing listeners to prevent duplicates
            walletAddressPillMobile.removeEventListener('click', walletAddressPillMobile._dropdownHandler);
            
            walletAddressPillMobile._dropdownHandler = (e) => {
                e.stopPropagation();
                walletDropdownMenuMobile.style.display = walletDropdownMenuMobile.style.display === 'block' ? 'none' : 'block';
            };
            
            walletAddressPillMobile.addEventListener('click', walletAddressPillMobile._dropdownHandler);
        }
        
        // Close dropdowns when clicking outside
        const closeDropdownsHandler = (e) => {
            if (walletDropdownMenu && !walletDropdownMenu.contains(e.target) && e.target !== walletAddressPill) {
                walletDropdownMenu.style.display = 'none';
            }
            if (walletDropdownMenuMobile && !walletDropdownMenuMobile.contains(e.target) && e.target !== walletAddressPillMobile) {
                walletDropdownMenuMobile.style.display = 'none';
            }
        };
        
        // Remove existing listener to prevent duplicates
        document.removeEventListener('click', document._closeDropdownsHandler);
        document._closeDropdownsHandler = closeDropdownsHandler;
        document.addEventListener('click', closeDropdownsHandler);
    }

    async submitTask(customParams = {}) {
        if (typeof window.ethereum === 'undefined') {
            showToast('MetaMask is not installed!', 'warning');
            return;
        }
        
        const accounts = await window.ethereum.request({ method: 'eth_accounts' });
        if (!accounts || accounts.length === 0) {
            showToast('Please connect your wallet first.', 'error');
            return;
        }
        this.account = accounts[0];
        
        // Validate account address
        if (!isValidEthereumAddress(this.account)) {
            showToast('Invalid account address.', 'error');
            return;
        }
        
        const chainId = await window.ethereum.request({ method: 'eth_chainId' });
        if (chainId !== this.arbitrumChainId) {
            await this.switchToArbitrum();
        }
        
        // Check network status before proceeding
        const networkStatus = await this.checkNetworkStatus();
        if (networkStatus.isPaused) {
            showToast('The Arbius network is currently paused for maintenance. Please try again later.', 'warning');
            return null;
        }
        
        try {
            // Load ethers.js
            await this.loadEthers();
            if (!window.ethers) {
                throw new Error('Ethers.js not loaded');
            }

            // Create provider and signer
            const provider = new window.ethers.providers.Web3Provider(window.ethereum);
            const signer = provider.getSigner();
            
            // Contract ABI for the submitTask function
            const contractAbi = [
                'function submitTask(uint8 version_, address owner_, bytes32 model_, uint256 fee_, bytes input_)'
            ];
            
            // Contract address
            const contractAddress = '0x9b51Ef044d3486A1fB0A2D55A6e0CeeAdd323E66';
            
            // Create contract instance
            const contract = new window.ethers.Contract(contractAddress, contractAbi, signer);
            
            // Validate custom prompt
            const customPrompt = customParams.customPrompt || '';
            if (!validateInput(customPrompt, 5000)) { // Allow longer prompts for AI tasks
                showToast('Invalid prompt content.', 'error');
                return;
            }
            
            // Prepare parameters
            let modelParams = {
                version_: 0,
                owner_: this.account,
                model_: '0x6cb3eed9fe3f32da1910825b98bd49d537912c99410e7a35f30add137fd3b64c', // M8B default
                fee_: 28000000000000, // M8B default
                input_: this.encodeTaskInput(customPrompt)
            };
            // Switch based on selected model
            const selected = window.selectedModel || 'm8b-uncensored';
            if (selected === 'qwen-qwq') {
                modelParams.model_ = '0x89c39001e3b23d2092bd998b62f07b523d23deb55e1627048b4ed47a4a38d5cc';
                modelParams.fee_ = 7000000000000000;
                modelParams.input_ = this.encodeTaskInputQwen(customPrompt);
            } else if (selected === 'wai') {
                modelParams.model_ = '0xa473c70e9d7c872ac948d20546bc79db55fa64ca325a4b229aaffddb7f86aae0';
                modelParams.fee_ = 3500000000000000;
                modelParams.input_ = this.encodeTaskInputWai(customPrompt);
            }
            // Merge with any custom params (overrides)
            const params = { ...modelParams, ...customParams };

            // --- ERC20 Approval Logic ---
            const aiusTokenAddress = '0x4a24B101728e07A52053c13FB4dB2BcF490CAbc3';
            const erc20Abi = [
                'function allowance(address owner, address spender) view returns (uint256)',
                'function approve(address spender, uint256 amount) returns (bool)'
            ];
            const aiusToken = new window.ethers.Contract(aiusTokenAddress, erc20Abi, signer);
            const allowance = await aiusToken.allowance(this.account, contractAddress);
            if (allowance.lt(window.ethers.BigNumber.from(params.fee_))) {
                // Ask user to approve
                showToast('Requesting AIUS token approval...', 'info');
                const approveTx = await aiusToken.approve(contractAddress, params.fee_);
                showToast('Waiting for approval confirmation...', 'info');
                await approveTx.wait();
                showToast('AIUS token approved!', 'success');
            }
            // --- End ERC20 Approval Logic ---
            
            // Estimate gas with better error handling
            let gasEstimate;
            try {
                gasEstimate = await contract.estimateGas.submitTask(
                    params.version_,
                    params.owner_,
                    params.model_,
                    params.fee_,
                    params.input_
                );
            } catch (gasError) {
                // Handle specific contract errors
                if (gasError.message && gasError.message.includes('paused')) {
                    showToast('The Arbius network is currently paused for maintenance. Please try again later.', 'warning');
                    return null;
                } else if (gasError.message && gasError.message.includes('insufficient')) {
                    showToast('Insufficient AIUS tokens for this task. Please check your balance.', 'error');
                    return null;
                } else if (gasError.message && gasError.message.includes('unauthorized')) {
                    showToast('You are not authorized to submit this task.', 'error');
                    return null;
                } else if (gasError.message && gasError.message.includes('invalid model')) {
                    showToast('Invalid model selected. Please try a different model.', 'error');
                    return null;
                } else {
                    // For other gas estimation errors, try with a default gas limit
                    console.warn('Gas estimation failed, using default gas limit:', gasError.message);
                    gasEstimate = window.ethers.BigNumber.from('500000'); // Default gas limit
                }
            }
            
            // Add 20% buffer to gas estimate
            const gasLimit = gasEstimate.mul(120).div(100);
            
            // Submit transaction with better error handling
            let tx;
            try {
                tx = await contract.submitTask(
                    params.version_,
                    params.owner_,
                    params.model_,
                    params.fee_,
                    params.input_,
                    {
                        gasLimit: gasLimit
                    }
                );
            } catch (txError) {
                // Handle transaction submission errors
                if (txError.message && txError.message.includes('paused')) {
                    showToast('The Arbius network is currently paused for maintenance. Please try again later.', 'warning');
                    return null;
                } else if (txError.message && txError.message.includes('insufficient funds')) {
                    showToast('Insufficient ETH for gas fees. Please add more ETH to your wallet.', 'error');
                    return null;
                } else if (txError.message && txError.message.includes('insufficient allowance')) {
                    showToast('Insufficient AIUS token allowance. Please approve more tokens.', 'error');
                    return null;
                } else if (txError.message && txError.message.includes('user rejected')) {
                    showToast('Transaction was cancelled by user.', 'info');
                    return null;
                } else {
                    throw txError; // Re-throw other errors
                }
            }
            
            showToast('Task submitted! Hash: ' + tx.hash, 'success');
            
            // Wait for transaction confirmation
            const receipt = await tx.wait();
            showToast('Transaction confirmed! Block: ' + receipt.blockNumber, 'success');
            
            try {
                // The event signature for TaskSubmitted
                const eventSignature = "TaskSubmitted(bytes32,bytes32,uint256,address)";
                const eventTopic = window.ethers.utils.id(eventSignature);
                const log = receipt.logs.find(l => l.topics[0] === eventTopic);
                if (log) {
                    const idHex = log.topics[1];
                    console.log("TaskSubmitted id:", idHex);
                    showToast('TaskSubmitted id: ' + idHex, 'success');
                } else {
                    console.warn("TaskSubmitted event not found in logs.");
                }
            } catch (e) {
                console.error("Error extracting TaskSubmitted id:", e);
            }
            
            return tx.hash;
        } catch (err) {
            console.error('Task submission failed:', err);
            
            // Provide user-friendly error messages
            let errorMessage = 'Task submission failed';
            
            if (err.message) {
                if (err.message.includes('paused')) {
                    errorMessage = 'The Arbius network is currently paused for maintenance. Please try again later.';
                } else if (err.message.includes('insufficient funds')) {
                    errorMessage = 'Insufficient ETH for gas fees. Please add more ETH to your wallet.';
                } else if (err.message.includes('insufficient allowance')) {
                    errorMessage = 'Insufficient AIUS token allowance. Please approve more tokens.';
                } else if (err.message.includes('user rejected')) {
                    errorMessage = 'Transaction was cancelled by user.';
                } else if (err.message.includes('network')) {
                    errorMessage = 'Network error. Please check your connection and try again.';
                } else if (err.message.includes('timeout')) {
                    errorMessage = 'Transaction timed out. Please try again.';
                } else {
                    // For unknown errors, show a generic message but log the full error
                    errorMessage = 'Task submission failed. Please try again later.';
                }
            }
            
            showToast(errorMessage, 'error');
            return null;
        }
    }

    encodeTaskInput(customPrompt = null) {
        // M8B default
        const prompt = `<|begin_of_text|><|start_header_id|>system<|end_header_id|> You are a helpful assistant.<|eot_id|><|start_header_id|>user<|end_header_id|> ${customPrompt || ''} Additional instruction: Make sure to keep response short and concise.<|eot_id|><|start_header_id|>assistant<|end_header_id|>`;
        const taskInput = {
            "prompt": prompt
        };
        const jsonString = JSON.stringify(taskInput);
        return window.ethers.utils.toUtf8Bytes(jsonString);
    }

    encodeTaskInputQwen(customPrompt = null) {
        // Qwen format
        const prompt = `{"System prompt": "You are helpful AI assistant. Below is additional context, please respond the user query and use the context as reference if relevant. If the context contains relevant information assume that the function has already been executed."}{"MessageHistory":[],"User prompt":"${customPrompt || ''}"} Additional instruction: Make sure to keep response short and concise.`;
        const taskInput = {
            "prompt": prompt
        };
        const jsonString = JSON.stringify(taskInput);
        return window.ethers.utils.toUtf8Bytes(jsonString);
    }

    encodeTaskInputWai(customPrompt = null) {
        // WAI format
        const prompt = `${customPrompt || ''}`;
        const taskInput = {
            "prompt": prompt
        };
        const jsonString = JSON.stringify(taskInput);
        return window.ethers.utils.toUtf8Bytes(jsonString);
    }
}

// === Model Selection Support (Refactored) ===
(function() {
    const MODEL_MAP = {
        'm8b-uncensored': { short: 'M8B', label: 'M8B-Uncensored' },
        'wai': { short: 'WAI', label: 'WAI SDXL (NSFW)' },
        'qwen-qwq': { short: 'Qwen', label: 'Qwen QwQ 32b' },
        'deepseek': { short: 'Deepseek', label: 'Deepseek-coder-v2' }
    };
    function getSavedModel() {
        return localStorage.getItem('selectedModel') || null;
    }
    function setSavedModel(model) {
        localStorage.setItem('selectedModel', model);
    }
    function updateModelUI(model) {
        // Chat input selector
        const chatSelectedModelShort = document.getElementById('chat-selected-model-short');
        if (chatSelectedModelShort && MODEL_MAP[model]) chatSelectedModelShort.textContent = MODEL_MAP[model].short;
        // Main header
        const currentModel = document.getElementById('current-model');
        if (currentModel && MODEL_MAP[model]) currentModel.textContent = MODEL_MAP[model].short;
        // Empty chat state pill
        const selectedModel = document.getElementById('selected-model');
        if (selectedModel && MODEL_MAP[model]) selectedModel.textContent = MODEL_MAP[model].short;
        // Dropdown highlight (optional: add active class)
        document.querySelectorAll('.model-dropdown-item').forEach(item => {
            if (item.getAttribute('data-model') === model) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
        // Pills highlight
        document.querySelectorAll('.model-pill').forEach(item => {
            if (item.getAttribute('data-model') === model) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
    }
    function setSelectedModel(model) {
        window.selectedModel = model;
        setSavedModel(model);
        updateModelUI(model);
    }
    window.setSelectedModel = setSelectedModel;
    window.getSelectedModel = getSavedModel;
    // On DOMContentLoaded, sync UI and global
    document.addEventListener('DOMContentLoaded', () => {
        const model = getSavedModel();
        window.selectedModel = model;
        updateModelUI(model);
        // Setup listeners for all model selectors
        // Chat input dropdown
        const chatModelDropdown = document.getElementById('chat-model-dropdown');
        if (chatModelDropdown) {
            chatModelDropdown.querySelectorAll('.model-dropdown-item').forEach(item => {
                item.addEventListener('click', () => {
                    if (item.hasAttribute('disabled')) return;
                    const model = item.getAttribute('data-model');
                    setSelectedModel(model);
                });
            });
        }
        // Pills in header/empty state
        document.querySelectorAll('.model-pill').forEach(item => {
            item.addEventListener('click', () => {
                const model = item.getAttribute('data-model');
                setSelectedModel(model);
            });
        });
    });
})();


// Initialize MetaMask manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.metaMaskManager = new MetaMaskManager();
    
    // Add helper functions for easy access
    window.submitTaskExample = async () => {
        if (window.metaMaskManager) {
            return await window.metaMaskManager.submitTask();
        }
    };
    
    window.submitTaskWithCustomPrompt = async (prompt) => {
        if (window.metaMaskManager) {
            const customParams = {
                input_: window.metaMaskManager.encodeTaskInput(prompt)
            };
            return await window.metaMaskManager.submitTask(customParams);
        }
    };
    
    window.submitTaskWithCustomParams = async (params) => {
        if (window.metaMaskManager) {
            return await window.metaMaskManager.submitTask(params);
        }
    };
    
    window.testNetworkStatus = async () => {
        if (window.metaMaskManager) {
            return await window.metaMaskManager.testNetworkStatus();
        }
    };
    
    // Add click handlers to connect buttons
    const connectBtn = document.getElementById('connect-wallet-btn');
    const connectBtnMobile = document.getElementById('connect-wallet-btn-mobile');
    
    if (connectBtn) {
        connectBtn.addEventListener('click', () => {
            window.metaMaskManager.connect();
        });
    }
    
    if (connectBtnMobile) {
        connectBtnMobile.addEventListener('click', () => {
            window.metaMaskManager.connect();
        });
    }

    // Add click handlers to disconnect buttons
    const disconnectBtn = document.getElementById('disconnect-wallet-btn');
    const disconnectBtnMobile = document.getElementById('disconnect-wallet-btn-mobile');
    
    if (disconnectBtn) {
        disconnectBtn.addEventListener('click', () => {
            window.metaMaskManager.disconnect();
        });
    }
    
    if (disconnectBtnMobile) {
        disconnectBtnMobile.addEventListener('click', () => {
            window.metaMaskManager.disconnect();
        });
    }

    // Add click handler to send-task-btn to send the transaction
    const sendTaskBtn = document.getElementById('send-task-btn');
    if (sendTaskBtn) {
        sendTaskBtn.addEventListener('click', async (e) => {
            e.preventDefault(); // Prevent form submission
            const messageInput = document.getElementById('message-input');
            let userPrompt = '';
            if (messageInput && typeof messageInput.value === 'string') {
                userPrompt = messageInput.value.trim();
            }
            if (window.metaMaskManager) {
                await window.metaMaskManager.submitTask({ customPrompt: userPrompt });
            }
        });
    }
}); 