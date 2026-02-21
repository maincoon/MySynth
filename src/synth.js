const MIN_GAIN_VALUE = 0.0001; // Avoid Web Audio API issues with ramping to exactly 0

export class Synth {
  constructor() {
    this.audioContext = null;
    this.activeVoices = new Map(); // midiNote -> voice
    this.voiceOrder = []; // for voice stealing (oldest first)
    this.MAX_VOICES = 8;

    this.params = {
      attack: 0.01,
      decay: 0.1,
      sustain: 0.7,
      release: 0.3,
      filterCutoff: 8000,
      filterResonance: 1,
      filterType: 'lowpass',
      osc1Type: 'sawtooth',
      osc2Type: 'sawtooth',
      osc1Level: 0.7,
      osc2Level: 0.5,
      osc1Octave: 0,
      osc2Octave: 0,
      osc2Detune: 7,
      reverbMix: 0.2,
      delayTime: 0.3,
      delayFeedback: 0.3,
      masterVolume: 0.7,
    };

    this.filter = null;
    this.convolver = null;
    this.reverbGain = null;
    this.dryGain = null;
    this.delay = null;
    this.delayFeedbackGain = null;
    this.masterGain = null;
  }

  init() {
    this.audioContext = new AudioContext();

    // Filter
    this.filter = this.audioContext.createBiquadFilter();
    this.filter.type = this.params.filterType;
    this.filter.frequency.setValueAtTime(this.params.filterCutoff, this.audioContext.currentTime);
    this.filter.Q.setValueAtTime(this.params.filterResonance, this.audioContext.currentTime);

    // Reverb
    this.convolver = this.audioContext.createConvolver();
    this.convolver.buffer = this._createImpulseResponse(2, 1.5);
    this.reverbGain = this.audioContext.createGain();
    this.reverbGain.gain.setValueAtTime(this.params.reverbMix, this.audioContext.currentTime);
    this.dryGain = this.audioContext.createGain();
    this.dryGain.gain.setValueAtTime(1 - this.params.reverbMix, this.audioContext.currentTime);

    // Delay
    this.delay = this.audioContext.createDelay(2.0);
    this.delay.delayTime.setValueAtTime(this.params.delayTime, this.audioContext.currentTime);
    this.delayFeedbackGain = this.audioContext.createGain();
    this.delayFeedbackGain.gain.setValueAtTime(this.params.delayFeedback, this.audioContext.currentTime);
    this.delayWetGain = this.audioContext.createGain();
    this.delayWetGain.gain.setValueAtTime(0.3, this.audioContext.currentTime);

    // Master
    this.masterGain = this.audioContext.createGain();
    this.masterGain.gain.setValueAtTime(this.params.masterVolume, this.audioContext.currentTime);

    // Routing: filter -> dry/reverb split
    this.filter.connect(this.dryGain);
    this.filter.connect(this.convolver);
    this.convolver.connect(this.reverbGain);

    // dry + reverb -> delay input
    this.dryGain.connect(this.delay);
    this.dryGain.connect(this.masterGain);
    this.reverbGain.connect(this.delay);
    this.reverbGain.connect(this.masterGain);

    // delay feedback loop
    this.delay.connect(this.delayFeedbackGain);
    this.delayFeedbackGain.connect(this.delay);
    this.delay.connect(this.delayWetGain);
    this.delayWetGain.connect(this.masterGain);

    this.masterGain.connect(this.audioContext.destination);
  }

  _createImpulseResponse(duration, decay) {
    const sampleRate = this.audioContext.sampleRate;
    const length = sampleRate * duration;
    const impulse = this.audioContext.createBuffer(2, length, sampleRate);
    for (let ch = 0; ch < 2; ch++) {
      const channel = impulse.getChannelData(ch);
      for (let i = 0; i < length; i++) {
        channel[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / length, decay);
      }
    }
    return impulse;
  }

  _midiNoteToFreq(note) {
    return 440 * Math.pow(2, (note - 69) / 12);
  }

  _createVoice(midiNote, velocity) {
    const ctx = this.audioContext;
    const now = ctx.currentTime;

    const voiceGain = ctx.createGain();
    voiceGain.gain.setValueAtTime(0, now);

    const osc1 = ctx.createOscillator();
    osc1.type = this.params.osc1Type;
    const freq1 = this._midiNoteToFreq(midiNote + this.params.osc1Octave * 12);
    osc1.frequency.setValueAtTime(freq1, now);

    const osc1Gain = ctx.createGain();
    osc1Gain.gain.setValueAtTime(this.params.osc1Level, now);

    const osc2 = ctx.createOscillator();
    osc2.type = this.params.osc2Type;
    const freq2 = this._midiNoteToFreq(midiNote + this.params.osc2Octave * 12);
    osc2.frequency.setValueAtTime(freq2, now);
    osc2.detune.setValueAtTime(this.params.osc2Detune, now);

    const osc2Gain = ctx.createGain();
    osc2Gain.gain.setValueAtTime(this.params.osc2Level, now);

    osc1.connect(osc1Gain);
    osc1Gain.connect(voiceGain);
    osc2.connect(osc2Gain);
    osc2Gain.connect(voiceGain);
    voiceGain.connect(this.filter);

    osc1.start(now);
    osc2.start(now);

    // ADSR attack
    const velScale = velocity / 127;
    voiceGain.gain.setValueAtTime(0, now);
    voiceGain.gain.linearRampToValueAtTime(velScale, now + this.params.attack);
    voiceGain.gain.linearRampToValueAtTime(
      this.params.sustain * velScale,
      now + this.params.attack + this.params.decay
    );

    return { osc1, osc2, osc1Gain, osc2Gain, voiceGain, midiNote, startTime: now, velScale };
  }

  noteOn(midiNote, velocity) {
    if (!this.audioContext) return;
    if (this.audioContext.state === 'suspended') {
      this.audioContext.resume();
    }

    // If note already active, release it first
    if (this.activeVoices.has(midiNote)) {
      this.noteOff(midiNote);
    }

    // Steal voice if at limit
    if (this.activeVoices.size >= this.MAX_VOICES) {
      const oldestNote = this.voiceOrder.shift();
      if (oldestNote !== undefined) {
        const oldVoice = this.activeVoices.get(oldestNote);
        if (oldVoice) this._stopVoice(oldVoice, true);
        this.activeVoices.delete(oldestNote);
      }
    }

    const voice = this._createVoice(midiNote, velocity);
    this.activeVoices.set(midiNote, voice);
    this.voiceOrder.push(midiNote);
  }

  noteOff(midiNote) {
    if (!this.audioContext) return;
    const voice = this.activeVoices.get(midiNote);
    if (!voice) return;
    this._stopVoice(voice, false);
    this.activeVoices.delete(midiNote);
    this.voiceOrder = this.voiceOrder.filter(n => n !== midiNote);
  }

  _stopVoice(voice, immediate) {
    const ctx = this.audioContext;
    const now = ctx.currentTime;
    if (immediate) {
      voice.voiceGain.gain.setValueAtTime(0, now);
      voice.osc1.stop(now + 0.01);
      voice.osc2.stop(now + 0.01);
    } else {
      const rel = this.params.release;
      const current = voice.voiceGain.gain.value;
      voice.voiceGain.gain.setValueAtTime(current, now);
      voice.voiceGain.gain.linearRampToValueAtTime(MIN_GAIN_VALUE, now + rel);
      voice.osc1.stop(now + rel + 0.05);
      voice.osc2.stop(now + rel + 0.05);
    }
  }

  setParam(name, value) {
    this.params[name] = value;
    if (!this.audioContext) return;
    const now = this.audioContext.currentTime;
    switch (name) {
      case 'filterCutoff':
        this.filter.frequency.setValueAtTime(value, now);
        break;
      case 'filterResonance':
        this.filter.Q.setValueAtTime(value, now);
        break;
      case 'filterType':
        this.filter.type = value;
        break;
      case 'reverbMix':
        this.reverbGain.gain.setValueAtTime(value, now);
        this.dryGain.gain.setValueAtTime(1 - value, now);
        break;
      case 'delayTime':
        this.delay.delayTime.setValueAtTime(value, now);
        break;
      case 'delayFeedback':
        this.delayFeedbackGain.gain.setValueAtTime(value, now);
        break;
      case 'masterVolume':
        this.masterGain.gain.setValueAtTime(value, now);
        break;
    }
  }

  getParams() {
    return { ...this.params };
  }
}
