# MySynth

A browser-based polyphonic synthesizer with a MIDI inspector, built with vanilla JavaScript and the Web Audio API.

## Features

- **Dual Oscillator Engine** — Two oscillators (sawtooth, square, sine, triangle) with independent level, octave, and detune controls
- **ADSR Envelope** — Attack, Decay, Sustain, Release shaping per voice
- **Filter** — Lowpass, highpass, and bandpass biquad filter with cutoff and resonance knobs
- **Effects** — Convolution reverb and feedback delay
- **8-Voice Polyphony** — Voice stealing when the limit is reached
- **On-Screen Keyboard** — 3-octave playable keyboard (C3–B5) with mouse and touch support
- **MIDI Inspector** — Real-time MIDI message log with device selection, hex display, and decoded output; routes noteOn/noteOff and CC messages to the synth

## Getting Started

### Prerequisites

- Node.js 18+
- npm 9+

### Install & Run

```bash
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in a browser that supports the Web Audio API (Chrome, Edge, Firefox, Safari).

### Build for Production

```bash
npm run build
npm run preview
```

### Run Tests

```bash
npm test
```

## Project Structure

```
src/
  synth.js       # Core synthesizer (oscillators, ADSR, filter, effects, voice management)
  midi.js        # Web MIDI API wrapper and message parser
  keyboard.js    # On-screen piano keyboard component
  knob.js        # Range-input knob widget
  main.js        # Application entry point — wires UI to synth and MIDI
  style.css      # Dark sci-fi UI theme
  tests/
    synth.test.js
    midi.test.js
index.html       # App shell
vite.config.js   # Vite + Vitest configuration
```

## MIDI

Click a key or connect a MIDI device. If the browser grants MIDI access, detected inputs appear in the **Device** dropdown in the MIDI Inspector panel. The inspector logs every incoming message in real time and colour-codes noteOn (green), noteOff (red), CC (blue), and pitch-bend (purple) events.

CC mappings:
| CC | Parameter |
|----|-----------|
| 7  | Master Volume |
| 74 | Filter Cutoff |
