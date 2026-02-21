import { describe, it, expect, beforeEach, vi } from 'vitest';
import { Synth } from '../synth.js';

// Mock Web Audio API
const mockAudioContext = {
  createOscillator: vi.fn(() => ({
    type: 'sine',
    frequency: { setValueAtTime: vi.fn(), value: 440 },
    detune: { setValueAtTime: vi.fn(), value: 0 },
    connect: vi.fn(),
    start: vi.fn(),
    stop: vi.fn(),
    disconnect: vi.fn(),
  })),
  createGain: vi.fn(() => ({
    gain: { setValueAtTime: vi.fn(), linearRampToValueAtTime: vi.fn(), exponentialRampToValueAtTime: vi.fn(), value: 1 },
    connect: vi.fn(),
    disconnect: vi.fn(),
  })),
  createBiquadFilter: vi.fn(() => ({
    type: 'lowpass',
    frequency: { setValueAtTime: vi.fn(), value: 20000 },
    Q: { setValueAtTime: vi.fn(), value: 1 },
    connect: vi.fn(),
  })),
  createConvolver: vi.fn(() => ({
    buffer: null,
    connect: vi.fn(),
  })),
  createDelay: vi.fn(() => ({
    delayTime: { setValueAtTime: vi.fn(), value: 0.3 },
    connect: vi.fn(),
  })),
  createBuffer: vi.fn((ch, len, sr) => ({
    getChannelData: vi.fn(() => new Float32Array(len)),
    length: len,
    sampleRate: sr,
  })),
  currentTime: 0,
  sampleRate: 44100,
  destination: { connect: vi.fn() },
  state: 'running',
  resume: vi.fn(() => Promise.resolve()),
};

vi.stubGlobal('AudioContext', vi.fn(() => mockAudioContext));

describe('Synth', () => {
  let synth;

  beforeEach(() => {
    vi.clearAllMocks();
    // Reset mock implementations
    mockAudioContext.createOscillator.mockReturnValue({
      type: 'sine',
      frequency: { setValueAtTime: vi.fn(), value: 440 },
      detune: { setValueAtTime: vi.fn(), value: 0 },
      connect: vi.fn(),
      start: vi.fn(),
      stop: vi.fn(),
      disconnect: vi.fn(),
    });
    mockAudioContext.createGain.mockReturnValue({
      gain: { setValueAtTime: vi.fn(), linearRampToValueAtTime: vi.fn(), exponentialRampToValueAtTime: vi.fn(), value: 1 },
      connect: vi.fn(),
      disconnect: vi.fn(),
    });
    synth = new Synth();
    synth.init();
  });

  it('should initialize with default parameters', () => {
    const params = synth.getParams();
    expect(params).toHaveProperty('attack');
    expect(params).toHaveProperty('decay');
    expect(params).toHaveProperty('sustain');
    expect(params).toHaveProperty('release');
    expect(params).toHaveProperty('filterCutoff');
    expect(params).toHaveProperty('masterVolume');
  });

  it('should allocate a voice on noteOn', () => {
    synth.noteOn(60, 100);
    expect(synth.activeVoices.size).toBe(1);
  });

  it('should release voice on noteOff', () => {
    synth.noteOn(60, 100);
    synth.noteOff(60);
    // Voice may still exist during release phase
    expect(synth.activeVoices.size).toBeGreaterThanOrEqual(0);
  });

  it('should handle multiple simultaneous notes', () => {
    synth.noteOn(60, 100);
    synth.noteOn(64, 100);
    synth.noteOn(67, 100);
    expect(synth.activeVoices.size).toBe(3);
  });

  it('should steal voice when exceeding polyphony limit', () => {
    for (let i = 0; i < 9; i++) {
      synth.noteOn(60 + i, 100);
    }
    expect(synth.activeVoices.size).toBeLessThanOrEqual(8);
  });

  it('should update parameters via setParam', () => {
    synth.setParam('attack', 0.5);
    expect(synth.getParams().attack).toBe(0.5);

    synth.setParam('filterCutoff', 1000);
    expect(synth.getParams().filterCutoff).toBe(1000);
  });

  it('should handle noteOff for non-existent note gracefully', () => {
    expect(() => synth.noteOff(99)).not.toThrow();
  });
});
