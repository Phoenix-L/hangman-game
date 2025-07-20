let selectedWord = '';
let correctLetters = [];
let wrongLetters = [];
const maxWrong = 6;

function loadWord(callback) {
    restartBtn.style.display = 'none';
    fetch('/api/random_word')
        .then(response => response.json())
        .then(data => {
            if (data.word) {
                selectedWord = data.word.toLowerCase();
                correctLetters = [];
                wrongLetters = [];
                callback();
            } else {
                alert('Failed to load word: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(err => {
            alert('Failed to load word from server!');
            console.error(err);
        });
}

const wordDiv = document.getElementById('word');
const wrongDiv = document.getElementById('wrong-letters');
const messageDiv = document.getElementById('message');
const restartBtn = document.getElementById('restart-btn');

const canvas = document.getElementById('hangman-canvas');
const ctx = canvas.getContext('2d');

function pickWord() {
    loadWord(updateDisplay);
    messageDiv.textContent = '';
    restartBtn.style.display = 'none';
}

function updateDisplay() {
    // Display word with underscores and revealed letters
    wordDiv.textContent = selectedWord
        .split('')
        .map(letter => (correctLetters.includes(letter) ? letter : '_'))
        .join(' ');

    // Display wrong letters
    wrongDiv.textContent = 'Wrong: ' + wrongLetters.join(' ');

    // Draw hangman with graphics
    drawHangman();
}

function showMessage(msg, color='#1976d2') {
    messageDiv.textContent = msg;
    messageDiv.style.color = color;
}

function checkGameStatus() {
    if (wordDiv.textContent.replace(/ /g, '') === selectedWord) {
        showMessage('Congratulations! You won! 🎉', '#388e3c');
       
        const winAudio = document.getElementById('win-sound');
        if (winAudio) winAudio.play(); // Play win sound
        restartBtn.style.display = 'inline-block';
        return true;
    }
    if (wrongLetters.length >= maxWrong) {
        showMessage('Game Over! The word was: ' + selectedWord, '#d32f2f');
        
        const loseAudio = document.getElementById('lose-sound');
        if (loseAudio) loseAudio.play(); // Play lose sound
        restartBtn.style.display = 'inline-block';
        return true;
    }
    return false;
}

function drawHangman() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Base
    ctx.lineWidth = 4;
    ctx.strokeStyle = '#333';
    ctx.beginPath();
    ctx.moveTo(20, 230);
    ctx.lineTo(180, 230);
    ctx.stroke();

    // Pole
    ctx.beginPath();
    ctx.moveTo(50, 230);
    ctx.lineTo(50, 20);
    ctx.lineTo(130, 20);
    ctx.lineTo(130, 40);
    ctx.stroke();

    // Draw parts based on wrongLetters.length
    if (wrongLetters.length > 0) {
        // Head
        ctx.beginPath();
        ctx.arc(130, 60, 20, 0, Math.PI * 2);
        ctx.stroke();
    }
    if (wrongLetters.length > 1) {
        // Body
        ctx.beginPath();
        ctx.moveTo(130, 80);
        ctx.lineTo(130, 150);
        ctx.stroke();
    }
    if (wrongLetters.length > 2) {
        // Left arm
        ctx.beginPath();
        ctx.moveTo(130, 100);
        ctx.lineTo(100, 120);
        ctx.stroke();
    }
    if (wrongLetters.length > 3) {
        // Right arm
        ctx.beginPath();
        ctx.moveTo(130, 100);
        ctx.lineTo(160, 120);
        ctx.stroke();
    }
    if (wrongLetters.length > 4) {
        // Left leg
        ctx.beginPath();
        ctx.moveTo(130, 150);
        ctx.lineTo(110, 200);
        ctx.stroke();
    }
    if (wrongLetters.length > 5) {
        // Right leg
        ctx.beginPath();
        ctx.moveTo(130, 150);
        ctx.lineTo(150, 200);
        ctx.stroke();
    }
}

document.addEventListener('keydown', (e) => {
    if (restartBtn.style.display === 'inline-block') return; // Ignore input if game over
    const letter = e.key.toLowerCase();
    if (!/^[a-z]$/.test(letter)) return; // Only letters
    if (selectedWord.includes(letter)) {
        if (!correctLetters.includes(letter)) {
            correctLetters.push(letter);
            updateDisplay();
            checkGameStatus();
            document.getElementById('correct-sound').play();
        }
    } else {
        if (!wrongLetters.includes(letter)) {
            wrongLetters.push(letter);
            updateDisplay();
            checkGameStatus();
            document.getElementById('wrong-sound').play();
        }
    }
});

restartBtn.addEventListener('click', () => loadWord(updateDisplay));

// Load a word and start the game
loadWord(updateDisplay);
