// Offline mode: set to true by index-offline.html (vocab.js must load first).
window.OFFLINE_MODE = window.OFFLINE_MODE || false;

let selectedWord = '';
let correctLetters = [];
let wrongLetters = [];
const maxWrong = 6;

// For progress/leaderboard: word and theme from /api/word/next (or offline selection)
let currentWordId = null;
let currentThemeId = null;
let currentThemeName = '';
let gameStartTime = null;
let currentReviewStatus = 'new';
let defaultThemeId = 1; // number when online (API theme id), string when offline (theme key e.g. "KET_ANIMALS")

const wordDiv = document.getElementById('word');
const wrongDiv = document.getElementById('wrong-letters');
const messageDiv = document.getElementById('message');
const restartBtn = document.getElementById('restart-btn');
const themeHintEl = document.getElementById('theme-hint');

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

// --- Offline: theme display name (mirrors backend theme_display_name) ---
function themeDisplayName(themeName) {
    if (!themeName || !String(themeName).trim()) return 'Vocabulary';
    const parts = String(themeName).trim().split('_');
    return parts.length ? parts[parts.length - 1].replace(/^\w/, c => c.toUpperCase()) : themeName;
}

// --- Offline: select random word from VOCAB (must load vocab.js before game.js) ---
function selectWordOffline(themeKey) {
    if (typeof VOCAB === 'undefined' || !VOCAB[themeKey] || VOCAB[themeKey].length === 0) return null;
    const words = VOCAB[themeKey];
    const value = words[Math.floor(Math.random() * words.length)];
    return {
        word: { value: value },
        theme: themeKey,
        theme_display: themeDisplayName(themeKey),
    };
}

// --- Offline: compute score locally (same formula as server) ---
function computeLocalScore(durationMs, correctGuesses, wrongGuesses, won, reviewStatus) {
    const total = correctGuesses + wrongGuesses;
    const accuracy = total > 0 ? correctGuesses / total : 0;

    const completionScore = won ? 20 : 8;
    const accuracyBonus = accuracy >= 0.9 ? 15 : (accuracy >= 0.75 ? 10 : (accuracy >= 0.6 ? 6 : 0));
    const speedBonus = durationMs <= 10000 ? 8 : (durationMs <= 20000 ? 5 : (durationMs <= 30000 ? 2 : 0));

    const learningBonusMap = { new: 4, review: 6, difficult: 8 };
    const learningBonus = learningBonusMap[reviewStatus] != null ? learningBonusMap[reviewStatus] : 4;

    return Math.max(0, Math.min(60, completionScore + accuracyBonus + speedBonus + learningBonus));
}

function loadWord(callback) {
    restartBtn.style.display = 'none';
    currentWordId = null;
    currentThemeId = null;
    currentThemeName = '';
    currentReviewStatus = 'new';
    if (themeHintEl) themeHintEl.textContent = '';

    if (window.OFFLINE_MODE && typeof VOCAB !== 'undefined' && typeof THEMES !== 'undefined') {
        const themeKey = typeof defaultThemeId === 'string' ? defaultThemeId : (THEMES[0] && THEMES[0].id) || 'KET_ANIMALS';
        const data = selectWordOffline(themeKey);
        if (data && data.word && data.word.value) {
            selectedWord = data.word.value.toLowerCase();
            currentThemeName = (data.theme_display != null && data.theme_display !== '') ? data.theme_display : (data.theme || 'Vocabulary');
            gameStartTime = Date.now();
            currentReviewStatus = 'new';
            correctLetters = [];
            wrongLetters = [];
            if (messageDiv) messageDiv.textContent = '';
            callback();
        } else {
            alert('No words found for theme. Ensure vocab.js is loaded.');
        }
        return;
    }

    const url = '/api/word/next?theme=' + defaultThemeId + '&_=' + Date.now();
    fetch(url, { credentials: 'same-origin' })
        .then(response => response.json())
        .then(data => {
            const wordObj = data.word;
            const wordText = wordObj && (wordObj.value || wordObj.word);
            if (wordText) {
                selectedWord = wordText.toLowerCase();
                currentWordId = wordObj.id != null ? wordObj.id : null;
                currentThemeId = wordObj.theme_id != null ? wordObj.theme_id : null;
                currentThemeName = (data.theme_display != null && data.theme_display !== '') ? data.theme_display : ((data.theme != null && data.theme !== '') ? data.theme : 'Vocabulary');
                currentReviewStatus = (data.review_status === 'review' || data.review_status === 'difficult' || data.review_status === 'new') ? data.review_status : 'new';
                gameStartTime = Date.now();
                correctLetters = [];
                wrongLetters = [];
                if (messageDiv) {
                    messageDiv.textContent = '';
                }
                callback();
            } else {
                // Fallback to random_word if word/next fails (e.g. no themes)
                fetch('/api/random_word?_=' + Date.now())
                    .then(r => r.json())
                    .then(fallback => {
                        if (fallback.word) {
                            selectedWord = fallback.word.toLowerCase();
                            currentThemeName = (fallback.theme_display != null && fallback.theme_display !== '') ? fallback.theme_display : ((fallback.theme != null && fallback.theme !== '') ? fallback.theme : 'Vocabulary');
                            gameStartTime = Date.now();
                            correctLetters = [];
                            wrongLetters = [];
                            if (messageDiv) messageDiv.textContent = '';
                            callback();
                        } else {
                            alert('Failed to load word: ' + (data.error || fallback.error || 'Unknown error'));
                        }
                    })
                    .catch(() => alert('Failed to load word: ' + (data.error || 'Unknown error')));
            }
        })
        .catch(err => {
            // Fallback to random_word if word/next fails
            fetch('/api/random_word?_=' + Date.now())
                .then(r => r.json())
                .then(fallback => {
                    if (fallback.word) {
                        selectedWord = fallback.word.toLowerCase();
                        currentThemeName = (fallback.theme_display != null && fallback.theme_display !== '') ? fallback.theme_display : ((fallback.theme != null && fallback.theme !== '') ? fallback.theme : 'Vocabulary');
                        gameStartTime = Date.now();
                        correctLetters = [];
                        wrongLetters = [];
                        if (messageDiv) messageDiv.textContent = '';
                        callback();
                    } else {
                            alert('Failed to load word from server!');
                            console.error(err);
                        }
                })
                .catch(() => {
                    alert('Failed to load word from server!');
                    console.error(err);
                });
        });
}

function pickWord() {
    loadWord(updateDisplay);
    messageDiv.textContent = '';
    restartBtn.style.display = 'none';
}

function updateDisplay() {
    if (themeHintEl) {
        themeHintEl.textContent = currentThemeName ? 'Theme: ' + currentThemeName : '';
    }
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

function submitGameResult(won) {
    const durationMs = gameStartTime ? Math.max(0, Date.now() - gameStartTime) : 0;
    const correctCount = correctLetters.length;
    const wrongCount = wrongLetters.length;

    if (window.OFFLINE_MODE) {
        const score = computeLocalScore(durationMs, correctCount, wrongCount, won, currentReviewStatus);
        const total = correctCount + wrongCount;
        const accuracy = total > 0 ? correctCount / total : 0;
        return Promise.resolve({ score, accuracy });
    }
    if (currentWordId == null || currentThemeId == null) return Promise.resolve({ score: null, accuracy: null });
    return fetch('/api/game/result', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({
            word_id: currentWordId,
            theme_id: currentThemeId,
            duration_ms: durationMs,
            guesses: { correct: correctCount, wrong: wrongCount },
            won: won,
            review_status: currentReviewStatus,
        }),
    })
        .then(function (r) { return r.ok ? r.json() : {}; })
        .then(function (body) {
            return {
                score: body.score != null ? body.score : null,
                accuracy: body.accuracy != null ? body.accuracy : null,
                rank: body.rank != null ? body.rank : null,
                leaderboard_score: body.leaderboard_score != null ? body.leaderboard_score : null,
                current_streak_days: body.current_streak_days != null ? body.current_streak_days : null
            };
        })
        .catch(function () { return { score: null, accuracy: null }; });
}

function checkGameStatus() {
    if (wordDiv.textContent.replace(/ /g, '') === selectedWord) {
        submitGameResult(true).then(function (result) {
            let msg = 'You Win!';
            if (result && result.score != null) {
                msg += '\nScore: ' + result.score;
                if (result.accuracy != null) msg += '\nAccuracy: ' + Math.round(result.accuracy * 100) + '%';
                if (result.rank != null) msg += '\nYour Rank: #' + result.rank;
                if (result.current_streak_days != null && result.current_streak_days > 0) msg += '\n\uD83D\uDD25 Streak: ' + result.current_streak_days + ' day(s)';
            }
            showMessage(msg, '#388e3c');
            loadLeaderboard(5, 'leaderboard', 'week');
        });
        const winAudio = document.getElementById('win-sound');
        if (winAudio) winAudio.play();
        restartBtn.style.display = 'inline-block';
        return true;
    }
    if (wrongLetters.length >= maxWrong) {
        submitGameResult(false).then(function (result) {
            let msg = 'Game Over\nThe word was: ' + selectedWord;
            if (result && result.score != null) {
                msg += '\nScore: ' + result.score;
                if (result.accuracy != null) msg += '\nAccuracy: ' + Math.round(result.accuracy * 100) + '%';
                if (result.rank != null) msg += '\nYour Rank: #' + result.rank;
                if (result.current_streak_days != null && result.current_streak_days > 0) msg += '\n\uD83D\uDD25 Streak: ' + result.current_streak_days + ' day(s)';
            }
            showMessage(msg, '#d32f2f');
            loadLeaderboard(5, 'leaderboard', 'week');
        });
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

    if (window.OFFLINE_MODE) {
        progressSummaryDiv.innerHTML = '<p>Progress (words seen, mastered, accuracy) is available when using the server. Play in offline mode to practice!</p>';
        themeProgressDiv.innerHTML = '';
        return Promise.resolve();
    }
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
    loadProgressLeaderboard(window.leaderboardPeriod || 'week');
}

// --- Leaderboard (aggregated per-user; period: today | week | all) ---
function loadLeaderboard(limit, containerId, period, options) {
    options = options || {};
    const container = document.getElementById(containerId);
    if (!container) return;

    if (window.OFFLINE_MODE) {
        container.innerHTML = '<p class="leaderboard-placeholder">Leaderboard available when online.</p>';
        return;
    }

    period = period || 'week';
    const url = '/api/leaderboard/global?limit=' + (limit || 5) + '&period=' + encodeURIComponent(period);
    const maxEntries = limit || 5;
    const showStreak = options.showStreak !== false;
    const showLastActive = options.showLastActive === true;
    const title = options.title !== undefined ? options.title : (period === 'today' ? "Today's Top Players" : period === 'week' ? "This Week's Top Players" : "All Time Leaders");

    fetch(url, { credentials: 'same-origin' })
        .then(function (r) {
            if (!r.ok) return { ok: false };
            return r.json().then(function (data) { return { ok: true, entries: data.entries || [], period: data.period }; });
        })
        .then(function (result) {
            if (result.ok === false) {
                container.innerHTML = '<p class="leaderboard-placeholder">Could not load leaderboard.</p>';
                return;
            }
            const entries = result.entries.slice(0, maxEntries);
            if (entries.length === 0) {
                container.innerHTML = '<p class="leaderboard-placeholder">No entries yet. Play a game to appear here!</p>';
                return;
            }
            var tableTitle = '';
            if (options.showTitle !== false && title) {
                tableTitle = '<p class="leaderboard-title">' + escapeHtml(title) + '</p>';
            }
            const rows = entries
                .map(function (e, i) {
                    const rank = (e.rank != null ? e.rank : i + 1);
                    const name = (e.is_current_user ? 'You' : (e.username || 'Guest'));
                    const score = e.leaderboard_score != null ? e.leaderboard_score : (e.score != null ? e.score : 0);
                    var streakCell = '';
                    if (showStreak && e.current_streak_days != null) {
                        streakCell = '<td class="lb-streak">' + (e.current_streak_days > 0 ? '\uD83D\uDD25 ' + e.current_streak_days : '-') + '</td>';
                    }
                    var lastActiveCell = '';
                    if (showLastActive && e.last_active) {
                        lastActiveCell = '<td class="lb-last-active">' + escapeHtml(String(e.last_active).slice(0, 10)) + '</td>';
                    }
                    const rowClass = e.is_current_user ? ' class="lb-you"' : '';
                    return '<tr' + rowClass + '><td class="lb-rank">' + rank + '</td><td class="lb-name">' + escapeHtml(name) + '</td><td class="lb-score">' + score + '</td>' + streakCell + lastActiveCell + '</tr>';
                })
                .join('');
            const headerStreak = showStreak ? '<th class="lb-streak">Streak</th>' : '';
            const headerLastActive = showLastActive ? '<th class="lb-last-active">Last active</th>' : '';
            container.innerHTML = tableTitle + '<table class="leaderboard-table"><thead><tr><th class="lb-rank">#</th><th class="lb-name">Player</th><th class="lb-score">Score</th>' + headerStreak + headerLastActive + '</tr></thead><tbody>' + rows + '</tbody></table>';

            if (options.onSelfEntry && result.entries) {
                const selfEntry = result.entries.filter(function (e) { return e.is_current_user; })[0];
                if (selfEntry) options.onSelfEntry(selfEntry);
            }
        })
        .catch(function () {
            container.innerHTML = '<p class="leaderboard-placeholder">Could not load leaderboard.</p>';
        });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
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

function loadProgressLeaderboard(period) {
    window.leaderboardPeriod = period || 'week';
    const containerId = 'progress-leaderboard';
    const summaryEl = document.getElementById('leaderboard-self-summary');
    loadLeaderboard(20, containerId, period, {
        showTitle: false,
        showStreak: true,
        showLastActive: true,
        onSelfEntry: function (entry) {
            if (!summaryEl) return;
            summaryEl.classList.remove('hidden');
            summaryEl.innerHTML = '<p class="lb-self-title">Your ranking</p>' +
                '<p><strong>Rank:</strong> #' + entry.rank + '</p>' +
                '<p><strong>Leaderboard score:</strong> ' + entry.leaderboard_score + '</p>' +
                '<p><strong>Streak:</strong> ' + (entry.current_streak_days > 0 ? '\uD83D\uDD25 ' + entry.current_streak_days + ' day(s)' : '0 days') + '</p>' +
                '<p class="lb-challenge-placeholder">Daily challenge: coming soon</p>';
        }
    });
    var todayBtn = document.getElementById('lb-tab-today');
    var weekBtn = document.getElementById('lb-tab-week');
    var allBtn = document.getElementById('lb-tab-all');
    if (todayBtn) todayBtn.classList.toggle('active', period === 'today');
    if (weekBtn) weekBtn.classList.toggle('active', period === 'week');
    if (allBtn) allBtn.classList.toggle('active', period === 'all');
}

restartBtn.addEventListener('click', () => loadWord(updateDisplay));
showGameBtn.addEventListener('click', showGameView);
showProgressBtn.addEventListener('click', showProgressView);
shareProgressBtn.addEventListener('click', shareProgressCard);

document.getElementById('lb-tab-today') && document.getElementById('lb-tab-today').addEventListener('click', function () { loadProgressLeaderboard('today'); });
document.getElementById('lb-tab-week') && document.getElementById('lb-tab-week').addEventListener('click', function () { loadProgressLeaderboard('week'); });
document.getElementById('lb-tab-all') && document.getElementById('lb-tab-all').addEventListener('click', function () { loadProgressLeaderboard('all'); });

// --- Auth UI ---
const authGuest = document.getElementById('auth-guest');
const authUser = document.getElementById('auth-user');
const authUsername = document.getElementById('auth-username');
const authForms = document.getElementById('auth-forms');
const signupForm = document.getElementById('signup-form');
const loginForm = document.getElementById('login-form');
const showSignupBtn = document.getElementById('show-signup-btn');
const showLoginBtn = document.getElementById('show-login-btn');
const signupUsername = document.getElementById('signup-username');
const signupPassword = document.getElementById('signup-password');
const signupSubmitBtn = document.getElementById('signup-submit-btn');
const signupMessage = document.getElementById('signup-message');
const loginUsername = document.getElementById('login-username');
const loginPassword = document.getElementById('login-password');
const loginSubmitBtn = document.getElementById('login-submit-btn');
const loginMessage = document.getElementById('login-message');
const logoutBtn = document.getElementById('logout-btn');

function showAuthGuest() {
    authGuest.classList.remove('hidden');
    authUser.classList.add('hidden');
    authForms.classList.add('hidden');
    signupForm.classList.add('hidden');
    loginForm.classList.add('hidden');
    window.currentUsername = null;
}

function showAuthUser(username) {
    authGuest.classList.add('hidden');
    authUser.classList.remove('hidden');
    authForms.classList.add('hidden');
    authUsername.textContent = 'Logged in as ' + username;
    window.currentUsername = username || null;
}

function openSignup() {
    loginForm.classList.add('hidden');
    signupForm.classList.remove('hidden');
    authForms.classList.remove('hidden');
    signupMessage.textContent = '';
}

function openLogin() {
    signupForm.classList.add('hidden');
    loginForm.classList.remove('hidden');
    authForms.classList.remove('hidden');
    loginMessage.textContent = '';
}

function closeAuthForms() {
    authForms.classList.add('hidden');
    signupForm.classList.add('hidden');
    loginForm.classList.add('hidden');
}

function refreshAuth() {
    if (window.OFFLINE_MODE) {
        showAuthGuest();
        const authBar = document.getElementById('auth-bar');
        if (authBar) authBar.classList.add('offline-mode');
        return;
    }
    fetch('/api/me', { credentials: 'same-origin' })
        .then(r => r.json())
        .then(data => {
            if (data.guest) {
                showAuthGuest();
            } else if (data.user && data.user.username) {
                showAuthUser(data.user.username);
            } else {
                showAuthGuest();
            }
        })
        .catch(() => showAuthGuest());
}

showSignupBtn.addEventListener('click', openSignup);
showLoginBtn.addEventListener('click', openLogin);

signupSubmitBtn.addEventListener('click', () => {
    const username = (signupUsername.value || '').trim();
    const password = signupPassword.value || '';
    signupMessage.textContent = '';
    signupMessage.classList.remove('error', 'success');
    if (username.length < 3 || password.length < 6) {
        signupMessage.textContent = 'Username at least 3 chars, password at least 6.';
        signupMessage.classList.add('error');
        return;
    }
    fetch('/api/auth/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ username, password }),
    })
        .then(r => r.json().then(body => ({ status: r.status, body })))
        .then(({ status, body }) => {
            if (status === 201) {
                signupMessage.textContent = 'Account created. You are logged in.';
                signupMessage.classList.add('success');
                closeAuthForms();
                refreshAuth();
            } else {
                signupMessage.textContent = body.error || 'Sign up failed.';
                signupMessage.classList.add('error');
            }
        })
        .catch(() => {
            signupMessage.textContent = 'Request failed.';
            signupMessage.classList.add('error');
        });
});

loginSubmitBtn.addEventListener('click', () => {
    const username = (loginUsername.value || '').trim();
    const password = loginPassword.value || '';
    loginMessage.textContent = '';
    loginMessage.classList.remove('error', 'success');
    if (!username || !password) {
        loginMessage.textContent = 'Enter username and password.';
        loginMessage.classList.add('error');
        return;
    }
    fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ username, password }),
    })
        .then(r => r.json().then(body => ({ status: r.status, body })))
        .then(({ status, body }) => {
            if (status === 200) {
                loginMessage.textContent = 'Logged in.';
                loginMessage.classList.add('success');
                closeAuthForms();
                refreshAuth();
            } else {
                loginMessage.textContent = body.error || 'Log in failed.';
                loginMessage.classList.add('error');
            }
        })
        .catch(() => {
            loginMessage.textContent = 'Request failed.';
            loginMessage.classList.add('error');
        });
});

logoutBtn.addEventListener('click', () => {
    fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' })
        .then(() => refreshAuth());
});

function startGame() {
    if (window.OFFLINE_MODE && typeof THEMES !== 'undefined' && THEMES.length > 0) {
        defaultThemeId = THEMES[0].id;
        loadWord(updateDisplay);
        loadLeaderboard(5, 'leaderboard', 'week');
        return;
    }
    fetch('/api/themes', { credentials: 'same-origin' })
        .then(r => r.json())
        .then(data => {
            if (data.themes && data.themes.length > 0 && data.themes[0].id != null) {
                defaultThemeId = data.themes[0].id;
            }
            loadWord(updateDisplay);
            loadLeaderboard(5, 'leaderboard', 'week');
        })
        .catch(function () {
            loadWord(updateDisplay);
            loadLeaderboard(5, 'leaderboard', 'week');
        });
}

refreshAuth();
startGame();
