// Configuration
const CONFIG = {
    // Development configuration
    development: {
        API_URL: 'http://localhost:5000/api',
        SOCKET_URL: 'http://localhost:5000',
        SOCKET_PATH: '/socket.io',
        DEBUG: true,
        CARD_PRICE: 5.00
    },
    // Production configuration (for Netlify + Render)
    production: {
        API_URL: 'https://your-backend.onrender.com/api',  // Replace with your Render URL
        SOCKET_URL: 'https://your-backend.onrender.com',   // Replace with your Render URL
        SOCKET_PATH: '/socket.io',
        DEBUG: false,
        CARD_PRICE: 5.00
    }
};

// Auto-detect environment
const isProduction = window.location.hostname !== 'localhost' && 
                     window.location.hostname !== '127.0.0.1';
const config = isProduction ? CONFIG.production : CONFIG.development;

// Game State
const gameState = {
    user: null,
    token: null,
    selectedCard: null,
    game: null,
    roomCode: null,
    socket: null,
    drawnNumbers: [],
    players: [],
    messages: [],
    currentPage: 1,
    totalPages: 1,
    isLoading: false,
    reconnectAttempts: 0,
    maxReconnectAttempts: 5
};

// DOM Elements
const elements = {
    // User info
    userName: document.getElementById('userName'),
    userBalance: document.getElementById('userBalance'),
    
    // Game status
    playerCount: document.getElementById('playerCount'),
    prizePool: document.getElementById('prizePool'),
    drawnCount: document.getElementById('drawnCount'),
    roomCode: document.getElementById('roomCode'),
    gameStatus: document.getElementById('gameStatus'),
    
    // Card selection
    cardsGrid: document.getElementById('cardsGrid'),
    currentPage: document.getElementById('currentPage'),
    totalPages: document.getElementById('totalPages'),
    prevPage: document.getElementById('prevPage'),
    nextPage: document.getElementById('nextPage'),
    cardSelection: document.getElementById('cardSelection'),
    
    // Bingo card
    bingoCardSection: document.getElementById('bingoCardSection'),
    selectedCardNumber: document.getElementById('selectedCardNumber'),
    bingoGrid: document.getElementById('bingoGrid'),
    
    // Drawn numbers
    drawnNumbers: document.getElementById('drawnNumbers'),
    
    // Chat
    gameLog: document.getElementById('gameLog'),
    chatInput: document.getElementById('chatInput'),
    sendChatBtn: document.getElementById('sendChatBtn'),
    
    // Buttons
    markNumberBtn: document.getElementById('markNumberBtn'),
    claimBingoBtn: document.getElementById('claimBingoBtn'),
    leaveGameBtn: document.getElementById('leaveGameBtn'),
    startGameBtn: document.getElementById('startGameBtn'),
    inviteFriendsBtn: document.getElementById('inviteFriendsBtn'),
    refreshBtn: document.getElementById('refreshBtn'),
    
    // Modals
    winnerModal: document.getElementById('winnerModal'),
    prizeAmount: document.getElementById('prizeAmount'),
    collectPrizeBtn: document.getElementById('collectPrizeBtn'),
    loadingModal: document.getElementById('loadingModal'),
    errorModal: document.getElementById('errorModal'),
    errorMessage: document.getElementById('errorMessage')
};

// Initialize WebApp
document.addEventListener('DOMContentLoaded', async () => {
    try {
        showLoading('Initializing game...');
        
        // Get parameters from URL
        const urlParams = new URLSearchParams(window.location.search);
        const telegramId = urlParams.get('telegram_id');
        const phoneNumber = urlParams.get('phone');
        const authToken = urlParams.get('auth');
        const roomCode = urlParams.get('room');
        
        if (roomCode) {
            gameState.roomCode = roomCode;
        }
        
        // Check if we have authentication data
        if (telegramId || phoneNumber || authToken) {
            await authenticateUser(telegramId, phoneNumber, authToken);
        } else {
            // Show login/registration screen
            showLoginScreen();
        }
        
        // Setup event listeners
        setupEventListeners();
        
        hideLoading();
        
    } catch (error) {
        console.error('Initialization error:', error);
        showError('Failed to initialize game. Please refresh the page.');
    }
});

// Authentication
async function authenticateUser(telegramId, phoneNumber, authToken) {
    try {
        if (authToken) {
            // Use existing token
            gameState.token = authToken;
            await loadUserProfile();
        } else if (telegramId) {
            // Login with Telegram ID
            const response = await fetch(`${config.API_URL}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ telegram_id: telegramId })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                gameState.token = data.token;
                gameState.user = data.user;
                localStorage.setItem('bingo_token', data.token);
                await initializeGame();
            } else {
                throw new Error(data.error || 'Authentication failed');
            }
        } else if (phoneNumber) {
            // TODO: Handle phone verification
            showPhoneVerification(phoneNumber);
        }
    } catch (error) {
        console.error('Authentication error:', error);
        showError('Authentication failed. Please try again.');
    }
}

async function loadUserProfile() {
    try {
        const response = await fetch(`${config.API_URL}/user/profile`, {
            headers: {
                'Authorization': `Bearer ${gameState.token}`
            }
        });
        
        const data = await response.json();
        
        if (response.ok) {
            gameState.user = data;
            updateUserUI();
            await initializeGame();
        } else {
            throw new Error(data.error || 'Failed to load profile');
        }
    } catch (error) {
        console.error('Profile load error:', error);
        showError('Failed to load user profile.');
    }
}

// Game Initialization
async function initializeGame() {
    try {
        // Initialize WebSocket connection
        initWebSocket();
        
        // Load available games or join existing room
        if (gameState.roomCode) {
            await joinRoom(gameState.roomCode);
        } else {
            await loadAvailableGames();
        }
        
        // Update UI
        updateGameUI();
        
    } catch (error) {
        console.error('Game initialization error:', error);
        showError('Failed to initialize game.');
    }
}

// WebSocket Connection
function initWebSocket() {
    if (gameState.socket && gameState.socket.connected) {
        gameState.socket.disconnect();
    }
    
    gameState.socket = io(config.SOCKET_URL, {
        path: config.SOCKET_PATH,
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionAttempts: 10,
        reconnectionDelay: 1000,
        timeout: 20000,
        auth: {
            token: gameState.token
        }
    });
    
    // Socket event handlers
    gameState.socket.on('connect', () => {
        console.log('Connected to game server');
        gameState.reconnectAttempts = 0;
        addSystemMessage('Connected to game server');
        
        if (gameState.roomCode) {
            gameState.socket.emit('join', {
                room_code: gameState.roomCode,
                user_id: gameState.user.id
            });
        }
    });
    
    gameState.socket.on('connected', (data) => {
        console.log('Socket connection confirmed:', data);
    });
    
    gameState.socket.on('joined', (data) => {
        console.log('Joined room:', data);
        addSystemMessage(`Joined room ${data.room}`);
    });
    
    gameState.socket.on('player_joined', (data) => {
        handlePlayerJoined(data);
    });
    
    gameState.socket.on('game_started', (data) => {
        handleGameStarted(data);
    });
    
    gameState.socket.on('number_drawn', (data) => {
        handleNumberDrawn(data);
    });
    
    gameState.socket.on('bingo', (data) => {
        handleBingo(data);
    });
    
    gameState.socket.on('chat_message', (data) => {
        addChatMessage(data.username, data.message, data.timestamp);
    });
    
    gameState.socket.on('disconnect', (reason) => {
        console.log('Disconnected:', reason);
        addSystemMessage('Disconnected from server. Attempting to reconnect...');
        
        if (reason === 'io server disconnect') {
            // Server forced disconnect, try to reconnect
            gameState.socket.connect();
        }
    });
    
    gameState.socket.on('connect_error', (error) => {
        console.error('Connection error:', error);
        gameState.reconnectAttempts++;
        
        if (gameState.reconnectAttempts >= gameState.maxReconnectAttempts) {
            showError('Cannot connect to game server. Please refresh the page.');
        }
    });
}

// Game Management
async function loadAvailableGames() {
    try {
        showLoading('Loading available games...');
        
        const response = await fetch(`${config.API_URL}/games?status=waiting`, {
            headers: {
                'Authorization': `Bearer ${gameState.token}`
            }
        });
        
        const data = await response.json();
        
        if (response.ok) {
            if (data.games.length > 0) {
                // Show game list
                displayGameList(data.games);
            } else {
                // Show card selection for new game
                await loadCards();
            }
        } else {
            throw new Error(data.error || 'Failed to load games');
        }
        
        hideLoading();
    } catch (error) {
        console.error('Load games error:', error);
        hideLoading();
        showError('Failed to load games.');
    }
}

async function joinRoom(roomCode) {
    try {
        showLoading(`Joining room ${roomCode}...`);
        
        // First, check if room exists and get game info
        const response = await fetch(`${config.API_URL}/games?status=all`, {
            headers: {
                'Authorization': `Bearer ${gameState.token}`
            }
        });
        
        const data = await response.json();
        
        if (response.ok) {
            const game = data.games.find(g => g.room_code === roomCode);
            
            if (game) {
                if (game.status === 'finished') {
                    showError('This game has already finished.');
                    return;
                }
                
                gameState.game = game;
                gameState.roomCode = roomCode;
                
                // Join via WebSocket
                gameState.socket.emit('join', {
                    room_code: roomCode,
                    user_id: gameState.user.id
                });
                
                // Check if user already has a card in this game
                await checkExistingCard(game.id);
                
                updateGameUI();
            } else {
                showError('Room not found.');
            }
        } else {
            throw new Error(data.error || 'Failed to join room');
        }
        
        hideLoading();
    } catch (error) {
        console.error('Join room error:', error);
        hideLoading();
        showError('Failed to join room.');
    }
}

async function checkExistingCard(gameId) {
    try {
        const response = await fetch(`${config.API_URL}/cards?game_id=${gameId}`, {
            headers: {
                'Authorization': `Bearer ${gameState.token}`
            }
        });
        
        const data = await response.json();
        
        if (response.ok && data.already_joined && data.card) {
            // User already has a card in this game
            gameState.selectedCard = data.card;
            showBingoCard();
        } else {
            // Need to select a card
            await loadCards(gameId);
        }
    } catch (error) {
        console.error('Check card error:', error);
    }
}

async function loadCards(gameId = null, page = 1) {
    try {
        showLoading('Loading available cards...');
        
        let url = `${config.API_URL}/cards?page=${page}&per_page=20`;
        if (gameId) {
            url += `&game_id=${gameId}`;
        }
        
        const response = await fetch(url, {
            headers: {
                'Authorization': `Bearer ${gameState.token}`
            }
        });
        
        const data = await response.json();
        
        if (response.ok) {
            if (data.already_joined && data.card) {
                // Already have a card
                gameState.selectedCard = data.card;
                showBingoCard();
            } else {
                // Show card selection
                displayCards(data.cards, data.page, data.pages);
            }
        } else {
            throw new Error(data.error || 'Failed to load cards');
        }
        
        hideLoading();
    } catch (error) {
        console.error('Load cards error:', error);
        hideLoading();
        showError('Failed to load cards.');
    }
}

// Card Selection
function displayCards(cards, currentPage, totalPages) {
    elements.cardsGrid.innerHTML = '';
    
    cards.forEach(card => {
        const cardElement = document.createElement('div');
        cardElement.className = 'card-item';
        cardElement.innerHTML = `
            <div class="card-number">#${card.card_number}</div>
            <div class="card-price">$${config.CARD_PRICE.toFixed(2)}</div>
            <div class="card-balance">Balance: $${gameState.user.balance.toFixed(2)}</div>
        `;
        
        cardElement.addEventListener('click', () => selectCard(card));
        
        elements.cardsGrid.appendChild(cardElement);
    });
    
    elements.currentPage.textContent = currentPage;
    elements.totalPages.textContent = totalPages;
    gameState.currentPage = currentPage;
    gameState.totalPages = totalPages;
    
    elements.cardSelection.style.display = 'block';
    elements.bingoCardSection.style.display = 'none';
}

async function selectCard(card) {
    try {
        showLoading('Selecting card...');
        
        const payload = {
            card_number: card.card_number
        };
        
        if (gameState.game) {
            payload.game_id = gameState.game.id;
        } else if (gameState.roomCode) {
            payload.room_code = gameState.roomCode;
        }
        
        const response = await fetch(`${config.API_URL}/cards/select`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${gameState.token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            gameState.selectedCard = {
                number: card.card_number,
                data: card.card_data
            };
            gameState.game = data.game;
            gameState.roomCode = data.game.room_code;
            gameState.user.balance = data.balance;
            
            // Join room via WebSocket
            gameState.socket.emit('join', {
                room_code: data.game.room_code,
                user_id: gameState.user.id
            });
            
            showBingoCard();
            updateUserUI();
            
            addSystemMessage(`Selected card #${card.card_number} and joined room ${data.game.room_code}`);
        } else {
            throw new Error(data.error || 'Failed to select card');
        }
        
        hideLoading();
    } catch (error) {
        console.error('Select card error:', error);
        hideLoading();
        showError(error.message || 'Failed to select card.');
    }
}

function showBingoCard() {
    if (!gameState.selectedCard) return;
    
    elements.selectedCardNumber.textContent = `#${gameState.selectedCard.number}`;
    
    // Render bingo card
    renderBingoCard(gameState.selectedCard.data);
    
    elements.cardSelection.style.display = 'none';
    elements.bingoCardSection.style.display = 'block';
    
    // Update game UI
    if (gameState.game) {
        elements.roomCode.textContent = gameState.game.room_code;
        elements.playerCount.textContent = gameState.game.player_count;
        elements.prizePool.textContent = gameState.game.prize_pool.toFixed(2);
    }
}

function renderBingoCard(cardData) {
    elements.bingoGrid.innerHTML = '';
    
    // Create BINGO header
    const letters = ['B', 'I', 'N', 'G', 'O'];
    letters.forEach(letter => {
        const headerCell = document.createElement('div');
        headerCell.className = 'bingo-header-cell';
        headerCell.textContent = letter;
        elements.bingoGrid.appendChild(headerCell);
    });
    
    // Create card cells
    for (let row = 0; row < 5; row++) {
        for (let col = 0; col < 5; col++) {
            const cell = document.createElement('div');
            cell.className = 'bingo-cell';
            cell.dataset.row = row;
            cell.dataset.col = col;
            
            const value = cardData[row][col];
            cell.textContent = value;
            
            if (value === 'FREE') {
                cell.classList.add('free');
                cell.classList.add('marked');
            }
            
            // Check if this number is marked
            if (gameState.selectedCard.marked_numbers && 
                gameState.selectedCard.marked_numbers.includes(value)) {
                cell.classList.add('marked');
            }
            
            cell.addEventListener('click', () => markCell(cell, value));
            
            elements.bingoGrid.appendChild(cell);
        }
    }
}

// Game Actions
async function markCell(cell, number) {
    if (number === 'FREE' || cell.classList.contains('marked')) return;
    
    if (!gameState.game || gameState.game.status !== 'active') {
        showError('Game is not active yet.');
        return;
    }
    
    try {
        const response = await fetch(`${config.API_URL}/games/${gameState.game.id}/mark`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${gameState.token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ number: number })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            cell.classList.add('marked');
            
            if (data.has_bingo) {
                // BINGO! This will be handled by the socket event
                addSystemMessage('🎉 BINGO! Checking your card...');
            }
        } else {
            throw new Error(data.error || 'Failed to mark number');
        }
    } catch (error) {
        console.error('Mark number error:', error);
        showError(error.message || 'Failed to mark number.');
    }
}

async function startGame() {
    if (!gameState.game) {
        showError('No game to start.');
        return;
    }
    
    if (gameState.game.created_by !== gameState.user.id) {
        showError('Only the game creator can start the game.');
        return;
    }
    
    try {
        showLoading('Starting game...');
        
        const response = await fetch(`${config.API_URL}/games/${gameState.game.id}/start`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${gameState.token}`
            }
        });
        
        const data = await response.json();
        
        if (response.ok) {
            addSystemMessage('Game started! Numbers will be drawn now.');
        } else {
            throw new Error(data.error || 'Failed to start game');
        }
        
        hideLoading();
    } catch (error) {
        console.error('Start game error:', error);
        hideLoading();
        showError(error.message || 'Failed to start game.');
    }
}

async function drawNumber() {
    if (!gameState.game) {
        showError('No active game.');
        return;
    }
    
    if (gameState.game.created_by !== gameState.user.id) {
        showError('Only the game creator can draw numbers.');
        return;
    }
    
    try {
        const response = await fetch(`${config.API_URL}/games/${gameState.game.id}/draw`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${gameState.token}`
            }
        });
        
        const data = await response.json();
        
        if (response.ok) {
            addSystemMessage(`Number ${data.number} drawn!`);
        } else {
            throw new Error(data.error || 'Failed to draw number');
        }
    } catch (error) {
        console.error('Draw number error:', error);
        showError(error.message || 'Failed to draw number.');
    }
}

// Event Handlers
function handlePlayerJoined(data) {
    gameState.players.push({
        id: data.user_id,
        username: data.username,
        card_number: data.card_number
    });
    
    updatePlayerCount();
    addSystemMessage(`${data.username} joined the game`);
}

function handleGameStarted(data) {
    gameState.game.status = 'active';
    updateGameUI();
    addSystemMessage(`Game started! Prize pool: $${data.prize_pool.toFixed(2)}`);
}

function handleNumberDrawn(data) {
    gameState.drawnNumbers.push(data.number);
    updateDrawnNumbers();
    addSystemMessage(`Number ${data.number} drawn!`);
    
    // Check if this number is on our card
    if (gameState.selectedCard && gameState.selectedCard.data) {
        const cardNumbers = gameState.selectedCard.data.flat();
        if (cardNumbers.includes(data.number)) {
            addSystemMessage(`Number ${data.number} is on your card!`);
        }
    }
}

function handleBingo(data) {
    if (data.winner_id === gameState.user.id) {
        // We won!
        showWinnerModal(data);
        addSystemMessage(`🎉 YOU WON $${data.prize_amount.toFixed(2)}! 🎉`);
    } else {
        // Someone else won
        addSystemMessage(`🎉 ${data.winner_name} won $${data.prize_amount.toFixed(2)}!`);
    }
}

// UI Updates
function updateUserUI() {
    if (gameState.user) {
        elements.userName.textContent = gameState.user.username || gameState.user.first_name || 'Player';
        elements.userBalance.textContent = `$${gameState.user.balance.toFixed(2)}`;
    }
}

function updateGameUI() {
    if (gameState.game) {
        elements.roomCode.textContent = gameState.game.room_code;
        elements.gameStatus.textContent = gameState.game.status.toUpperCase();
        elements.playerCount.textContent = gameState.players.length;
        elements.prizePool.textContent = gameState.game.prize_pool ? 
            `$${gameState.game.prize_pool.toFixed(2)}` : '$0.00';
        
        // Update button states
        if (gameState.game.status === 'waiting') {
            elements.startGameBtn.disabled = gameState.game.created_by !== gameState.user.id;
        } else {
            elements.startGameBtn.disabled = true;
        }
    }
}

function updatePlayerCount() {
    elements.playerCount.textContent = gameState.players.length;
}

function updateDrawnNumbers() {
    elements.drawnNumbers.innerHTML = '';
    elements.drawnCount.textContent = gameState.drawnNumbers.length;
    
    gameState.drawnNumbers.forEach(number => {
        const bubble = document.createElement('div');
        bubble.className = 'number-bubble';
        bubble.textContent = number;
        elements.drawnNumbers.appendChild(bubble);
    });
}

// Chat Functions
function addSystemMessage(message) {
    addMessage('system', 'System', message, new Date().toISOString());
}

function addChatMessage(username, message, timestamp) {
    addMessage('user', username, message, timestamp);
}

function addMessage(type, sender, message, timestamp) {
    const messageElement = document.createElement('div');
    messageElement.className = `log-entry ${type}`;
    
    const time = new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    if (type === 'system') {
        messageElement.innerHTML = `<i class="fas fa-info-circle"></i> <strong>${sender}:</strong> ${message}`;
    } else {
        messageElement.innerHTML = `<i class="fas fa-user"></i> <strong>${sender}:</strong> ${message} <span class="message-time">${time}</span>`;
    }
    
    elements.gameLog.appendChild(messageElement);
    elements.gameLog.scrollTop = elements.gameLog.scrollHeight;
    
    // Keep only last 100 messages
    const messages = elements.gameLog.querySelectorAll('.log-entry');
    if (messages.length > 100) {
        messages[0].remove();
    }
}

function sendChatMessage() {
    const message = elements.chatInput.value.trim();
    if (!message || !gameState.roomCode || !gameState.socket) return;
    
    gameState.socket.emit('chat_message', {
        room_code: gameState.roomCode,
        user_id: gameState.user.id,
        username: gameState.user.username || gameState.user.first_name,
        message: message
    });
    
    elements.chatInput.value = '';
}

// Modals
function showWinnerModal(data) {
    elements.prizeAmount.textContent = data.prize_amount.toFixed(2);
    elements.winnerModal.style.display = 'flex';
}

function showLoading(message = 'Loading...') {
    if (elements.loadingModal) {
        elements.loadingModal.querySelector('.loading-message').textContent = message;
        elements.loadingModal.style.display = 'flex';
    }
    gameState.isLoading = true;
}

function hideLoading() {
    if (elements.loadingModal) {
        elements.loadingModal.style.display = 'none';
    }
    gameState.isLoading = false;
}

function showError(message) {
    if (elements.errorModal && elements.errorMessage) {
        elements.errorMessage.textContent = message;
        elements.errorModal.style.display = 'flex';
    } else {
        alert(message);
    }
}

function showLoginScreen() {
    // TODO: Implement login screen
    elements.cardSelection.innerHTML = `
        <div class="login-screen">
            <h2>Welcome to Telegram Bingo</h2>
            <p>Please open this game through the Telegram bot to play.</p>
            <p>If you're the bot owner, make sure to configure the Mini App URL correctly.</p>
            <button onclick="location.reload()" class="btn-retry">Retry</button>
        </div>
    `;
    elements.cardSelection.style.display = 'block';
}

// Event Listeners Setup
function setupEventListeners() {
    // Pagination
    if (elements.prevPage) {
        elements.prevPage.addEventListener('click', () => {
            if (gameState.currentPage > 1) {
                loadCards(gameState.game?.id, gameState.currentPage - 1);
            }
        });
    }
    
    if (elements.nextPage) {
        elements.nextPage.addEventListener('click', () => {
            if (gameState.currentPage < gameState.totalPages) {
                loadCards(gameState.game?.id, gameState.currentPage + 1);
            }
        });
    }
    
    // Game buttons
    if (elements.markNumberBtn) {
        elements.markNumberBtn.addEventListener('click', () => {
            const number = prompt('Enter number to mark (1-75):');
            if (number && /^\d+$/.test(number) && number >= 1 && number <= 75) {
                const cell = findCellByNumber(parseInt(number));
                if (cell) {
                    markCell(cell, parseInt(number));
                } else {
                    showError('This number is not on your card.');
                }
            }
        });
    }
    
    if (elements.claimBingoBtn) {
        elements.claimBingoBtn.addEventListener('click', () => {
            // In this implementation, bingo is automatically detected
            // when numbers are marked
            showError('BINGO is automatically detected when you complete a line.');
        });
    }
    
    if (elements.leaveGameBtn) {
        elements.leaveGameBtn.addEventListener('click', () => {
            if (confirm('Are you sure you want to leave the game?')) {
                if (gameState.socket && gameState.roomCode) {
                    gameState.socket.emit('leave', { room_code: gameState.roomCode });
                }
                window.location.reload();
            }
        });
    }
    
    if (elements.startGameBtn) {
        elements.startGameBtn.addEventListener('click', startGame);
    }
    
    if (elements.inviteFriendsBtn) {
        elements.inviteFriendsBtn.addEventListener('click', () => {
            if (gameState.roomCode) {
                const inviteText = `🎮 Join my Bingo game!\nRoom Code: ${gameState.roomCode}\n\nPlay at: ${window.location.origin}?room=${gameState.roomCode}`;
                
                if (navigator.share) {
                    navigator.share({
                        title: 'Telegram Bingo',
                        text: inviteText
                    });
                } else {
                    navigator.clipboard.writeText(inviteText)
                        .then(() => alert('Invite link copied to clipboard!'))
                        .catch(() => prompt('Copy this invite link:', inviteText));
                }
            } else {
                showError('Join a game first to invite friends.');
            }
        });
    }
    
    if (elements.refreshBtn) {
        elements.refreshBtn.addEventListener('click', () => {
            window.location.reload();
        });
    }
    
    // Chat
    if (elements.sendChatBtn && elements.chatInput) {
        elements.sendChatBtn.addEventListener('click', sendChatMessage);
        elements.chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendChatMessage();
            }
        });
    }
    
    // Modal close buttons
    document.querySelectorAll('.close-modal').forEach(button => {
        button.addEventListener('click', () => {
            button.closest('.modal').style.display = 'none';
        });
    });
    
    if (elements.collectPrizeBtn) {
        elements.collectPrizeBtn.addEventListener('click', () => {
            elements.winnerModal.style.display = 'none';
            window.location.reload();
        });
    }
    
    // Click outside modals to close
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        });
    });
}

// Helper Functions
function findCellByNumber(number) {
    const cells = elements.bingoGrid.querySelectorAll('.bingo-cell:not(.free)');
    for (const cell of cells) {
        if (parseInt(cell.textContent) === number) {
            return cell;
        }
    }
    return null;
}

// Export for debugging
if (config.DEBUG) {
    window.gameState = gameState;
    window.config = config;
    window.elements = elements;
}

// Handle page visibility changes
document.addEventListener('visibilitychange', () => {
    if (!document.hidden && gameState.socket && !gameState.socket.connected) {
        // Page became visible and socket is disconnected, try to reconnect
        gameState.socket.connect();
    }
});

// Handle beforeunload
window.addEventListener('beforeunload', () => {
    if (gameState.socket) {
        gameState.socket.disconnect();
    }
});
