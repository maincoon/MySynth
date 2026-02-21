import { describe, it, expect, beforeEach, vi } from 'vitest';
import { MidiInspector } from '../midi.js';

describe('MidiInspector', () => {
  let midi;

  beforeEach(() => {
    midi = new MidiInspector();
  });

  it('should initialize with empty log', () => {
    expect(midi.getLog()).toEqual([]);
  });

  it('should register message callbacks', () => {
    const callback = vi.fn();
    midi.onMessage(callback);
    expect(midi._callbacks).toContain(callback);
  });

  it('should parse noteOn message', () => {
    const callback = vi.fn();
    midi.onMessage(callback);
    
    // Simulate a MIDI noteOn message (status=0x90, note=60, velocity=100)
    midi._handleMidiMessage({ data: new Uint8Array([0x90, 60, 100]), timeStamp: 1000 });
    
    expect(callback).toHaveBeenCalledWith(expect.objectContaining({
      type: 'noteOn',
      note: 60,
      velocity: 100,
      channel: 1,
    }));
  });

  it('should parse noteOff message', () => {
    const callback = vi.fn();
    midi.onMessage(callback);
    
    midi._handleMidiMessage({ data: new Uint8Array([0x80, 60, 0]), timeStamp: 1000 });
    
    expect(callback).toHaveBeenCalledWith(expect.objectContaining({
      type: 'noteOff',
      note: 60,
      channel: 1,
    }));
  });

  it('should parse noteOn with velocity 0 as noteOff', () => {
    const callback = vi.fn();
    midi.onMessage(callback);
    
    midi._handleMidiMessage({ data: new Uint8Array([0x90, 60, 0]), timeStamp: 1000 });
    
    expect(callback).toHaveBeenCalledWith(expect.objectContaining({
      type: 'noteOff',
    }));
  });

  it('should parse control change message', () => {
    const callback = vi.fn();
    midi.onMessage(callback);
    
    midi._handleMidiMessage({ data: new Uint8Array([0xB0, 74, 64]), timeStamp: 1000 });
    
    expect(callback).toHaveBeenCalledWith(expect.objectContaining({
      type: 'controlChange',
      controller: 74,
      value: 64,
    }));
  });

  it('should parse pitch bend message', () => {
    const callback = vi.fn();
    midi.onMessage(callback);
    
    midi._handleMidiMessage({ data: new Uint8Array([0xE0, 0, 64]), timeStamp: 1000 });
    
    expect(callback).toHaveBeenCalledWith(expect.objectContaining({
      type: 'pitchBend',
    }));
  });

  it('should add messages to log', () => {
    midi._handleMidiMessage({ data: new Uint8Array([0x90, 60, 100]), timeStamp: 1000 });
    midi._handleMidiMessage({ data: new Uint8Array([0x80, 60, 0]), timeStamp: 2000 });
    
    expect(midi.getLog().length).toBe(2);
  });

  it('should limit log to 100 messages', () => {
    for (let i = 0; i < 110; i++) {
      midi._handleMidiMessage({ data: new Uint8Array([0x90, 60, 100]), timeStamp: i * 100 });
    }
    expect(midi.getLog().length).toBe(100);
  });

  it('should return empty inputs when MIDI not initialized', () => {
    expect(midi.getInputs()).toEqual([]);
  });

  it('should handle init failure gracefully', async () => {
    global.navigator = {
      requestMIDIAccess: vi.fn(() => Promise.reject(new Error('MIDI not available'))),
    };
    
    const result = await midi.init();
    expect(result).toBe(false);
  });

  it('should handle missing Web MIDI API gracefully', async () => {
    const originalNavigator = global.navigator;
    global.navigator = {};
    
    const result = await midi.init();
    expect(result).toBe(false);
    
    global.navigator = originalNavigator;
  });
});
