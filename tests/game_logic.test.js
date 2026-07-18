const test = require('node:test');
const assert = require('node:assert/strict');
const { isHangmanComplete, maskHangmanDisplay, guessableLetters, formatHangmanDisplay } = require('../game_logic.js');
const { createPronunciationController } = require('../speech_controller.js');

function speechFixture() {
  const calls = { cancel: 0, speak: [], utterances: [] };
  class Utterance {
    constructor(text) { this.text = text; }
  }
  const synth = {
    cancel() { calls.cancel += 1; },
    speak(utterance) { calls.speak.push(utterance); },
    getVoices() { return [{ lang: 'en-GB' }, { lang: 'en-US' }]; },
  };
  const timers = [];
  const audio = {
    listeners: {},
    addEventListener(name, callback) { this.listeners[name] = callback; },
    play() { return Promise.resolve(); },
    end() { this.listeners.ended?.(); },
  };
  const controller = createPronunciationController({
    speechSynthesis: synth,
    SpeechSynthesisUtterance: Utterance,
    setTimeout(callback) { timers.push(callback); return timers.length - 1; },
    clearTimeout(id) { timers[id] = null; },
  });
  return { calls, timers, audio, controller };
}

test('phrase completion ignores spaces and punctuation', () => {
  assert.deepEqual(guessableLetters("cerebral cortex"), ['c', 'e', 'r', 'b', 'a', 'l', 'o', 't', 'x']);
  assert.equal(isHangmanComplete("cerebral cortex", ['c', 'e', 'r', 'b', 'a', 'l', 'o', 't', 'x']), true);
  assert.equal(isHangmanComplete("cerebral cortex", ['c', 'e']), false);
});

test('phrase formatting preserves an explicit word boundary', () => {
  const masked = maskHangmanDisplay('vertebral column', ['v', 'e', 'r', 't', 'b', 'a', 'l', 'c', 'o', 'u', 'm', 'n']);
  assert.equal(formatHangmanDisplay(masked), 'v e r t e b r a l   c o l u m n');
});

test('hyphens and apostrophes are automatically visible', () => {
  assert.deepEqual(maskHangmanDisplay("well-known user's", ['w', 'e', 'l']), ['w', 'e', 'l', 'l', '-', '_', '_', '_', 'w', '_', ' ', '_', '_', 'e', '_', "'", '_']);
});

test('repeated letters require only one guessed letter', () => {
  assert.equal(isHangmanComplete('myelin', ['m', 'y', 'e', 'l', 'i', 'n']), true);
});

test('automatic speech waits for result sound ended', () => {
  const { calls, audio, controller } = speechFixture();
  controller.schedule('multiple sclerosis', audio);
  assert.equal(calls.speak.length, 0);
  audio.end();
  assert.equal(calls.speak.length, 1);
  assert.equal(calls.speak[0].text, 'multiple sclerosis');
  assert.equal(calls.speak[0].lang, 'en-US');
  assert.equal(calls.speak[0].rate, 0.9);
});

test('fallback timer speaks when result sound does not end', () => {
  const { calls, timers, audio, controller } = speechFixture();
  controller.schedule('demyelination', audio);
  timers[0]();
  assert.equal(calls.speak.length, 1);
});

test('replay cancels existing utterance before speaking again', () => {
  const { calls, controller } = speechFixture();
  controller.pronounce('axon');
  controller.pronounce('myelin');
  assert.equal(calls.cancel, 2);
  assert.equal(calls.speak.at(-1).text, 'myelin');
});

test('unsupported speech synthesis fails gracefully', () => {
  const controller = createPronunciationController({});
  assert.equal(controller.pronounce('axon'), false);
});

test('a completed game schedules speech once', () => {
  const { calls, audio, controller } = speechFixture();
  controller.schedule('stimulus', audio);
  controller.schedule('stimulus', audio);
  audio.end();
  assert.equal(calls.speak.length, 1);
});

test('cancelling a new game prevents stale delayed speech', () => {
  const { calls, timers, audio, controller } = speechFixture();
  controller.schedule('old answer', audio);
  controller.cancel();
  timers[0]?.();
  assert.equal(calls.speak.length, 0);
});
