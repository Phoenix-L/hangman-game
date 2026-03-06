let selectedWord = '';
let correctLetters = [];
let wrongLetters = [];
const maxWrong = 6;

const wordDiv = document.getElementById('word');
const wrongDiv = document.getElementById('wrong-letters');
const messageDiv = document.getElementById('message');
const restartBtn = document.getElementById('restart-btn');

const canvas = document.getElementById('hangman-canvas');
const ctx = canvas.getContext('2d');

const gameView = document.getElementById('game-view');
const progressView = document.getElementById('progress-view');
const showGameBtn = document.getElementById('show-game-btn');
const showProgressBtn = document.getElementById('show-progress-btn');
const progressSummaryDiv = document.getElementById('progress-summary');
const themeProgressDiv = document.getElementById('theme-progress');
const shareProgressBtn = document.getElementById('share-progress-btn');
const sharePreview = document.getElementById('share-preview');
const shareImage = document.getElementById('share-image');
const shareCanvas = document.getElementById('share-canvas');

let latestProgressSummary = null;

function loadWord(callback) {
    restartBtn.style.display = 'none';
    fetch('/api/random_word')
        .then(response => response.json())
        .then(data => {
            if (data.word) {
                selectedWord = data.word.toLowerCase();
                correctLetters = [];
                wrongLetters = [];
                if (messageDiv) {
                    messageDiv.textContent = '';
                }
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

function pickWord() {
    loadWord(updateDisplay);
    messageDiv.textContent = '';
    restartBtn.style.display = 'none';
}

function updateDisplay() {
    wordDiv.textContent = selectedWord
        .split('')
        .map(letter => (correctLetters.includes(letter) ? letter : '_'))
        .join(' ');

    if (wrongLetters.length > 0) {
        wrongDiv.textContent = 'Wrong: ' + wrongLetters.join(' ');
    } else {
        wrongDiv.textContent = '';
    }

    drawHangman();
}

function showMessage(msg, color = '#1976d2') {
    messageDiv.textContent = msg;
    messageDiv.style.color = color;
}

function checkGameStatus() {
    if (wordDiv.textContent.replace(/ /g, '') === selectedWord) {
        showMessage('Congratulations! You won! 🎉', '#388e3c');

        const winAudio = document.getElementById('win-sound');
        if (winAudio) winAudio.play();
        restartBtn.style.display = 'inline-block';
        return true;
    }
    if (wrongLetters.length >= maxWrong) {
        showMessage('Game Over! The word was: ' + selectedWord, '#d32f2f');

        const loseAudio = document.getElementById('lose-sound');
        if (loseAudio) loseAudio.play();
        restartBtn.style.display = 'inline-block';
        return true;
    }
    return false;
}

function drawHangman() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    ctx.lineWidth = 4;
    ctx.strokeStyle = '#333';
    ctx.beginPath();
    ctx.moveTo(20, 230);
    ctx.lineTo(180, 230);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(50, 230);
    ctx.lineTo(50, 20);
    ctx.lineTo(130, 20);
    ctx.lineTo(130, 40);
    ctx.stroke();

    if (wrongLetters.length > 0) {
        ctx.beginPath();
        ctx.arc(130, 60, 20, 0, Math.PI * 2);
        ctx.stroke();
    }
    if (wrongLetters.length > 1) {
        ctx.beginPath();
        ctx.moveTo(130, 80);
        ctx.lineTo(130, 150);
        ctx.stroke();
    }
    if (wrongLetters.length > 2) {
        ctx.beginPath();
        ctx.moveTo(130, 100);
        ctx.lineTo(100, 120);
        ctx.stroke();
    }
    if (wrongLetters.length > 3) {
        ctx.beginPath();
        ctx.moveTo(130, 100);
        ctx.lineTo(160, 120);
        ctx.stroke();
    }
    if (wrongLetters.length > 4) {
        ctx.beginPath();
        ctx.moveTo(130, 150);
        ctx.lineTo(110, 200);
        ctx.stroke();
    }
    if (wrongLetters.length > 5) {
        ctx.beginPath();
        ctx.moveTo(130, 150);
        ctx.lineTo(150, 200);
        ctx.stroke();
    }
}

function formatPercent(value) {
    if (value === null || value === undefined) return 'N/A';
    return `${Math.round(value * 100)}%`;
}

function renderProgress(summary) {
    progressSummaryDiv.innerHTML = `
        <p><strong>Words Seen:</strong> ${summary.words_seen}</p>
        <p><strong>Words Mastered:</strong> ${summary.words_mastered}</p>
        <p><strong>Accuracy (7d):</strong> ${formatPercent(summary.accuracy_7d)}</p>
        <p><strong>Streak Days:</strong> ${summary.streak_days}</p>
    `;

    if (!summary.themes || summary.themes.length === 0) {
        themeProgressDiv.innerHTML = '<p>No theme progress yet. Play a few rounds first!</p>';
        return;
    }

    const rows = summary.themes
        .map(theme => `<li><strong>${theme.theme_name}</strong> — Seen: ${theme.words_seen}, Mastered: ${theme.words_mastered}, Accuracy(7d): ${formatPercent(theme.accuracy_7d)}</li>`)
        .join('');

    themeProgressDiv.innerHTML = `<p><strong>Per-theme progress</strong></p><ul>${rows}</ul>`;
}

function loadProgressSummary() {
    progressSummaryDiv.innerHTML = '<p>Loading progress…</p>';
    themeProgressDiv.innerHTML = '';

    return fetch('/api/progress/summary')
        .then(response => {
            if (response.status === 401) {
                throw new Error('Please log in to see your progress dashboard.');
            }
            return response.json();
        })
        .then(summary => {
            latestProgressSummary = summary;
            renderProgress(summary);
        })
        .catch(err => {
            latestProgressSummary = null;
            progressSummaryDiv.innerHTML = `<p>${err.message}</p>`;
            themeProgressDiv.innerHTML = '';
        });
}

function drawShareCard(summary) {
    const cardCtx = shareCanvas.getContext('2d');
    cardCtx.fillStyle = '#f0fdf4';
    cardCtx.fillRect(0, 0, shareCanvas.width, shareCanvas.height);

    cardCtx.fillStyle = '#166534';
    cardCtx.font = 'bold 36px Segoe UI';
    cardCtx.fillText('Hangman Progress Card', 24, 56);

    cardCtx.fillStyle = '#1f2937';
    cardCtx.font = '24px Segoe UI';
    cardCtx.fillText(`Words Seen: ${summary.words_seen}`, 24, 118);
    cardCtx.fillText(`Words Mastered: ${summary.words_mastered}`, 24, 154);
    cardCtx.fillText(`Accuracy (7d): ${formatPercent(summary.accuracy_7d)}`, 24, 190);
    cardCtx.fillText(`Streak: ${summary.streak_days} day(s)`, 24, 226);

    cardCtx.fillStyle = '#15803d';
    cardCtx.font = 'bold 22px Segoe UI';
    cardCtx.fillText('Keep learning every day! 🌟', 24, 282);

    return shareCanvas.toDataURL('image/png');
}

function shareProgressCard() {
    if (!latestProgressSummary) {
        alert('Load progress data first.');
        return;
    }

    const imageUrl = drawShareCard(latestProgressSummary);
    shareImage.src = imageUrl;
    sharePreview.classList.remove('hidden');

    const anchor = document.createElement('a');
    anchor.href = imageUrl;
    anchor.download = 'hangman-progress-card.png';
    anchor.click();
}

function showGameView() {
    gameView.classList.remove('hidden');
    progressView.classList.add('hidden');
    showGameBtn.classList.add('active');
    showProgressBtn.classList.remove('active');
}

function showProgressView() {
    gameView.classList.add('hidden');
    progressView.classList.remove('hidden');
    showGameBtn.classList.remove('active');
    showProgressBtn.classList.add('active');
    loadProgressSummary();
}

document.addEventListener('keydown', (e) => {
    if (restartBtn.style.display === 'inline-block') return;
    const letter = e.key.toLowerCase();
    if (!/^[a-z]$/.test(letter)) return;
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
showGameBtn.addEventListener('click', showGameView);
showProgressBtn.addEventListener('click', showProgressView);
shareProgressBtn.addEventListener('click', shareProgressCard);

loadWord(updateDisplay);
