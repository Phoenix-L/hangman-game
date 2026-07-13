// Pure helpers shared by online/offline Hangman gameplay and Node tests.
function normalizeHangmanAnswer(value) {
    return String(value == null ? '' : value).trim().toLowerCase();
}

function guessableLetters(value) {
    const letters = normalizeHangmanAnswer(value).match(/[a-z]/g) || [];
    return [...new Set(letters)];
}

function isHangmanComplete(answer, guessedLetters) {
    const guessed = new Set((guessedLetters || []).map(letter => String(letter).toLowerCase()));
    return guessableLetters(answer).every(letter => guessed.has(letter));
}

function maskHangmanDisplay(displayTerm, guessedLetters) {
    const guessed = new Set((guessedLetters || []).map(letter => String(letter).toLowerCase()));
    return String(displayTerm == null ? '' : displayTerm).split('').map(character => {
        if (!/[a-z]/i.test(character)) return character;
        return guessed.has(character.toLowerCase()) ? character : '_';
    });
}

const HangmanLogic = {
    normalizeHangmanAnswer,
    guessableLetters,
    isHangmanComplete,
    maskHangmanDisplay,
};

if (typeof window !== 'undefined') window.HangmanLogic = HangmanLogic;
if (typeof module !== 'undefined') module.exports = HangmanLogic;
