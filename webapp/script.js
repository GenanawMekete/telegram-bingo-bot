// Game State
let gameState = {
    userId: null,
    userName: null,
    userBalance: 0,
    selectedCard: null,
    gameId: null,
    roomCode: 'public',
    socket: null,
    currentPage: 1,
    totalPages: 1,
    drawnNumbers: [],
    players: [],
    gameStatus: 'waiting'
};

// DOM Elements
const elements = {
    userName: document.getElementById('userName'),
    userBalance: document.getElementById('userBalance'),
    playerCount: document.getElementById('playerCount'),
    prizePool: document.getElementById('prizePool'),
    drawnCount: document.getElementById('drawnCount'),
    roomCode: document.getElementById('roomCode'),
    cardsGrid: document.getElementById('cardsGrid'),
    currentPage: document.getElementById('currentPage'),
    totalPages: document.getElementById('totalPages'),
    prevPage: document.getElementById('prevPage'),
    nextPage: document.getElementById('nextPage'),
    cardSelection: document.getElementById('cardSelection'),
    bingoCardSection: document.getElementById('bingoCardSection'),
    selectedCardNumber: document.getElementById('selectedCardNumber'),
    bingoGrid: document.getElementById('bingoGrid'),
    drawnNumbers: document.getElementById('drawnNumbers'),
    gameLog: document.getElementById('gameLog'),
    chatInput: document.getElementById('chatInput'),
    sendChatBtn: document.getElementById('sendChatBtn'),
    markNumberBtn: document.getElementById('markNumberBtn'),
    claimBingoBtn: document.getElementById('claimBingoBtn'),
    leaveGameBtn: document.getElementById('leaveGameBtn'),
    startGameBtn: document.getElementById('startGameBtn'),
    inviteFriendsBtn: document.getElementById('inviteFriendsBtn'),
    refreshBtn: document.getElementById('refreshBtn'),
    winnerModal: document.getElementById('winnerModal'),
    prizeAmount: document.getElementById('prizeAmount'),
    collectPrizeBtn: document.getElementById('collectPrizeBtn')
};

// Initialize WebApp
async function initWebApp() {
    // Get parameters from URL
    const urlParams = new URLSearchParams(window.location.search);
    gameState.userId = urlParams.get('user_id');
    
    if (!gameState.userId) {
        showError('User ID is required');
        return;
    }
    
    // Initialize WebSocket connection
    initWebSocket();
    
    // Load user info
    await loadUserInfo();
    
    // Load available cards
    await loadCards();
    
    // Setup event listeners
    setupEventListeners();
    
    // Log game start
    addLogMessage('system', 'Welcome to Telegram Bingo! Game loaded successfully.');
}

// Initialize WebSocket connection
function initWebSocket() {
    const backendUrl = 'http://localhost:5000'; // Replace with your backend URL
    gameState.socket = io(backendUrl);
    
    gameState.socket.on('connect', () => {
        console.log('Connected to game server');
        addLogMessage('system', 'Connected to game server');
    });
    
    gameState.socket.on('connected', (data) => {
        console.log('Server connection confirmed:', data);
    });
    
    gameState.socket.on('number_drawn', (data) => {
        handleNumberDrawn(data);
    });
    
    gameState.socket.on('player_joined', (data) => {
        handlePlayerJoined(data);
    });
    
    gameState.socket.on('bingo', (data) => {
        handleBingoWin(data);
    });
    
    gameState.socket.on('message', (data) => {
        addLogMessage('system', data.message);
    });
}

// Load user information
async function loadUserInfo() {
    try {
        const response = await fetch(`${getBackendUrl()}/api/user/${gameState.userId}`);
        if (!response.ok) throw new Error('Failed to load user info');
        
        const user = await response.json();
        
        gameState.userName = user.username || `Player_${gameState.userId}`;
        gameState.userBalance = user.balance;
        
        // Update UI
        elements.userName.textContent = gameState.userName;
        elements.userBalance.textContent = `Balance: $${gameState.userBalance.toFixed(2)}`;
        
    } catch (error) {
        console.error('Error loading user info:', error);
        showError('Failed to load user information');
    }
}

// Load available cards
async function loadCards(page = 1) {
    try {
        elements.cardsGrid.innerHTML = '<div class="loading">Loading cards...</div>';
        
        const response = await fetch(`${getBackendUrl()}/api/cards?page=${page}`);
        if (!response.ok) throw new Error('Failed to load cards');
        
        const data = await response.json();
        
        // Update pagination
        gameState.currentPage = data.page;
        gameState.totalPages = data.pages;
        
        elements.currentPage.textContent = data.page;
        elements.totalPages.textContent = data.pages;
        
        // Display cards
        elements.cardsGrid.innerHTML = '';
        data.cards.forEach(card => {
            const cardElement = createCardElement(card);
            elements.cardsGrid.appendChild(cardElement);
        });
        
    } catch (error) {
        console.error('Error loading cards:', error);
        elements.cardsGrid.innerHTML = '<div class="error">Failed to load cards. Please try again.</div>';
    }
}

// Create card element
function createCardElement(card) {
    const div = document.createElement('div');
    div.className = 'card-item';
    div.innerHTML = `
        <div class="card-number">#${card.card_number}</div>
        <div class="card-price">$${getCardPrice()}</div>
    `;
    
    div.addEventListener('click', () => selectCard(card));
    
    return div;
}

// Select a bingo card
async function selectCard(card) {
    try {
        // Deselect all cards
        document.querySelectorAll('.card-item').forEach(el => {
            el.classList.remove('selected');
        });
        
        // Select clicked card
        event.target.closest('.card-item').classList.add('selected');
        
        // Make API call to reserve card
        const response = await fetch(`${getBackendUrl()}/api/cards/select`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                telegram_id: gameState.userId,
                card_number: card.card_number
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to select card');
        }
        
        const result = await response.json();
        
        // Update game state
        gameState.selectedCard = card;
        gameState.gameId = result.game_id;
        gameState.roomCode = result.room_code;
        gameState.userBalance = result.balance;
        
        // Update UI
        elements.userBalance.textContent = `Balance: $${gameState.userBalance.toFixed(2)}`;
        elements.roomCode.textContent = result.room_code;
        elements.selectedCardNumber.textContent = `#${card.card_number}`;
        
        // Show bingo card section
        elements.cardSelection.style.display = 'none';
        elements.bingoCardSection.style.display = 'block';
        
        // Render bingo card
        renderBingoCard(card.card_data);
        
        // Join game room via WebSocket
        gameState.socket.emit('join', {
            room_code: result.room_code,
            user_id: gameState.userId
        });
        
        addLogMessage('system', `You selected card #${card.card_number}. Waiting for game to start...`);
        
    } catch (error) {
        console.error('Error selecting card:', error);
        showError(error.message);
    }
}

// Render bingo card
function renderBingoCard(cardData) {
    elements.bingoGrid.innerHTML = '';
    
    for (let row = 0; row < 5; row++) {
        for (let col = 0; col < 5; col++) {
            const cell = document.createElement('div');
            cell.className = 'bingo-cell';
            cell.dataset.row = row;
            cell.dataset.col = col;
            
            const number = cardData[row][col];
            cell.textContent = number;
            
            if (number === 'FREE') {
                cell.classList.add('free');
                cell.textContent = 'FREE';
            }
            
            cell.addEventListener('click', () => markNumber(number));
            
            elements.bingoGrid.appendChild(cell);
        }
    }
}

// Mark number on card
function markNumber(number) {
    if (number === 'FREE') return;
    
    const cells = elements.bingoGrid.querySelectorAll('.bingo-cell');
    cells.forEach(cell => {
        if (cell.textContent === number.toString()) {
            cell.classList.add('marked');
        }
    });
    
    addLogMessage('user', `Marked number ${number} on your card`);
}

// Handle number drawn
function handleNumberDrawn(data) {
    const number = data.number;
    
    // Add to drawn numbers
    gameState.drawnNumbers.push(number);
    
    // Update UI
    updateDrawnNumbers();
    elements.drawnCount.textContent = data.total_drawn;
    
    // Check if number is on card
    if (gameState.selectedCard) {
        const cardNumbers = gameState.selectedCard.card_data.flat();
        if (cardNumbers.includes(number)) {
            addLogMessage('system', `Number ${number} is on your card!`);
        }
    }
}

// Update drawn numbers display
function updateDrawnNumbers() {
    elements.drawnNumbers.innerHTML = '';
    
    gameState.drawnNumbers.forEach(number => {
        const bubble = document.createElement('div');
        bubble.className = 'number-bubble';
        bubble.textContent = number;
        elements.drawnNumbers.appendChild(bubble);
    });
    
    // Highlight last number
    const bubbles = elements.drawnNumbers.querySelectorAll('.number-bubble');
    if (bubbles.length > 0) {
        bubbles[bubbles.length - 1].classList.add('new');
        
        // Remove highlight after animation
        setTimeout(() => {
            bubbles[bubbles.length - 1].classList.remove('new');
        }, 2000);
    }
}

// Handle player joined
function handlePlayerJoined(data) {
    gameState.players.push(data);
    elements.playerCount.textContent = data.total_players;
    
    // Update prize pool (simplified)
    const prize = data.total_players * getCardPrice() * 0.8;
    elements.prizePool.textContent = prize.toFixed(2);
    
    addLogMessage('system', `${data.username} joined the game`);
}

// Handle bingo win
function handleBingoWin(data) {
    if (data.winner_id === parseInt(gameState.userId)) {
        // Current user won
        elements.prizeAmount.textContent = data.prize_amount.toFixed(2);
        elements.winnerModal.style.display = 'flex';
        
        addLogMessage('system', `🎉 You won $${data.prize_amount}! Congratulations!`);
    } else {
        // Another player won
        addLogMessage('system', `🎉 ${data.winner_name} won the game with $${data.prize_amount}!`);
    }
}

// Claim bingo
async function claimBingo() {
    if (!gameState.selectedCard || !gameState.gameId) {
        showError('You need to select a card first');
        return;
    }
    
    // Get marked numbers
    const markedCells = elements.bingoGrid.querySelectorAll('.bingo-cell.marked');
    const markedNumbers = Array.from(markedCells).map(cell => {
        const num = parseInt(cell.textContent);
        return isNaN(num) ? 'FREE' : num;
    });
    
    // Send claim to server
    gameState.socket.emit('claim_bingo', {
        room_code: gameState.roomCode,
        user_id: gameState.userId,
        card_data: JSON.stringify(gameState.selectedCard.card_data),
        marked_numbers: markedNumbers,
        card_number: gameState.selectedCard.card_number
    });
    
    addLogMessage('user', 'Claiming BINGO!');
}

// Setup event listeners
function setupEventListeners() {
    // Pagination
    elements.prevPage.addEventListener('click', () => {
        if (gameState.currentPage > 1) {
            loadCards(gameState.currentPage - 1);
        }
    });
    
    elements.nextPage.addEventListener('click', () => {
        if (gameState.currentPage < gameState.totalPages) {
            loadCards(gameState.currentPage + 1);
        }
    });
    
    // Game buttons
    elements.markNumberBtn.addEventListener('click', () => {
        const number = prompt('Enter number to mark (1-75):');
        if (number && number >= 1 && number <= 75) {
            markNumber(parseInt(number));
        }
    });
    
    elements.claimBingoBtn.addEventListener('click', claimBingo);
    
    elements.leaveGameBtn.addEventListener('click', () => {
        if (confirm('Are you sure you want to leave the game?')) {
            window.location.reload();
        }
    });
    
    elements.startGameBtn.addEventListener('click', async () => {
        try {
            const response = await fetch(`${getBackendUrl()}/api/game/${gameState.gameId}/draw`, {
                method: 'POST'
            });
            
            if (!response.ok) throw new Error('Failed to draw number');
            
            const data = await response.json();
            addLogMessage('system', `Number ${data.number} drawn!`);
            
        } catch (error) {
            showError(error.message);
        }
    });
    
    elements.inviteFriendsBtn.addEventListener('click', () => {
        const inviteText = `Join my Bingo game! Room: ${gameState.roomCode}\n\nPlay at: ${window.location.href}`;
        
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
    });
    
    elements.refreshBtn.addEventListener('click', () => {
        loadUserInfo();
        addLogMessage('system', 'Refreshed game data');
    });
    
    // Chat
    elements.sendChatBtn.addEventListener('click', sendChatMessage);
    elements.chatInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendChatMessage();
        }
    });
    
    // Modal
    document.querySelector('.close-modal').addEventListener('click', () => {
        elements.winnerModal.style.display = 'none';
    });
    
    elements.collectPrizeBtn.addEventListener('click', () => {
        elements.winnerModal.style.display = 'none';
        addLogMessage('system', 'Prize collected! Returning to main menu...');
        setTimeout(() => window.location.reload(), 2000);
    });
    
    // Click outside modal to close
    elements.winnerModal.addEventListener('click', (e) => {
        if (e.target === elements.winnerModal) {
            elements.winnerModal.style.display = 'none';
        }
    });
}

// Send chat message
function sendChatMessage() {
    const message = elements.chatInput.value.trim();
    if (!message) return;
    
    addLogMessage('user', message);
    elements.chatInput.value = '';
    
    // In a real implementation, send to server
    // gameState.socket.emit('chat', { message, user_id: gameState.userId });
}

// Add log message
function addLogMessage(type, message) {
    const logEntry = document.createElement('div');
    logEntry.className = `log-entry ${type}`;
    
    const icon = type === 'system' ? 'fa-info-circle' : 'fa-user';
    logEntry.innerHTML = `<i class="fas ${icon}"></i> ${message}`;
    
    elements.gameLog.appendChild(logEntry);
    elements.gameLog.scrollTop = elements.gameLog.scrollHeight;
}

// Show error message
function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.innerHTML = `
        <i class="fas fa-exclamation-circle"></i>
        <span>${message}</span>
        <button class="close-error">&times;</button>
    `;
    
    errorDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #ef4444;
        color: white;
        padding: 15px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        gap: 10px;
        z-index: 1000;
        animation: slideIn 0.3s;
    `;
    
    document.body.appendChild(errorDiv);
    
    errorDiv.querySelector('.close-error').addEventListener('click', () => {
        errorDiv.style.animation = 'slideOut 0.3s';
        setTimeout(() => errorDiv.remove(), 300);
    });
    
    setTimeout(() => {
        if (errorDiv.parentNode) {
            errorDiv.style.animation = 'slideOut 0.3s';
            setTimeout(() => errorDiv.remove(), 300);
        }
    }, 5000);
}

// Helper functions
function getCardPrice() {
    return 5.00; // Should match Config.CARD_PRICE
}

function getBackendUrl() {
    return 'http://localhost:5000'; // Replace with your actual backend URL
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initWebApp);
