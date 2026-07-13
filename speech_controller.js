// Browser speech lifecycle helper. It is dependency-injectable for Node tests.
function createPronunciationController(deps) {
    const environment = deps || {};
    const synth = environment.speechSynthesis || (typeof window !== 'undefined' ? window.speechSynthesis : undefined);
    const Utterance = environment.SpeechSynthesisUtterance || (typeof window !== 'undefined' ? window.SpeechSynthesisUtterance : undefined);
    const scheduleTimeout = environment.setTimeout || setTimeout;
    const cancelTimeout = environment.clearTimeout || clearTimeout;
    let timer = null;
    let generation = 0;
    let scheduled = false;

    function cancel() {
        generation += 1;
        scheduled = false;
        if (timer !== null) cancelTimeout(timer);
        timer = null;
        if (synth && typeof synth.cancel === 'function') synth.cancel();
    }

    function pronounce(text) {
        if (!synth || typeof synth.speak !== 'function' || typeof Utterance !== 'function' || !text) return false;
        const utterance = new Utterance(text);
        utterance.lang = 'en-US';
        utterance.rate = 0.9;
        const voices = typeof synth.getVoices === 'function' ? synth.getVoices() : [];
        utterance.voice = voices.find(voice => voice.lang === 'en-US') || voices.find(voice => /^en(-|_)/i.test(voice.lang || '')) || null;
        if (typeof synth.cancel === 'function') synth.cancel();
        synth.speak(utterance);
        return true;
    }

    function schedule(text, audio) {
        if (scheduled) return;
        scheduled = true;
        const currentGeneration = generation;
        let spoken = false;
        const speakOnce = () => {
            if (spoken || currentGeneration !== generation) return;
            spoken = true;
            if (timer !== null) cancelTimeout(timer);
            timer = null;
            pronounce(text);
        };
        if (!audio || typeof audio.addEventListener !== 'function') {
            timer = scheduleTimeout(speakOnce, 250);
            return;
        }
        audio.addEventListener('ended', speakOnce, { once: true });
        timer = scheduleTimeout(speakOnce, 1400);
        try {
            const result = typeof audio.play === 'function' ? audio.play() : null;
            if (result && typeof result.catch === 'function') result.catch(() => {});
        } catch (_) {
            // The bounded timer remains the fallback when audio cannot play.
        }
    }

    return { cancel, pronounce, schedule };
}

if (typeof window !== 'undefined') window.createPronunciationController = createPronunciationController;
if (typeof module !== 'undefined') module.exports = { createPronunciationController };
