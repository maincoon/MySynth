import { Synth } from './synth.js';
import { MidiInspector } from './midi.js';
import { OnScreenKeyboard } from './keyboard.js';
import { Knob } from './knob.js';
import './style.css';

let synth = new Synth();
let synthInitialized = false;
const midi = new MidiInspector();

function ensureSynth() {
  if (!synthInitialized) {
    synth.init();
    synthInitialized = true;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  // On-screen keyboard
  const keyboardContainer = document.getElementById('keyboard-container');
  const keyboard = new OnScreenKeyboard(keyboardContainer, {
    onNoteOn: (note, vel) => {
      ensureSynth();
      synth.noteOn(note, vel);
    },
    onNoteOff: (note) => {
      synth.noteOff(note);
    },
  });

  // Wire up synth control knobs
  function addKnob(containerId, opts) {
    const el = document.getElementById(containerId);
    if (!el) return;
    return new Knob(el, {
      ...opts,
      onChange: (v) => {
        ensureSynth();
        synth.setParam(opts.param, v);
      }
    });
  }

  const params = synth.getParams();

  addKnob('knob-attack',    { label: 'Attack',    min: 0.001, max: 2,     value: params.attack,          step: 0.001, param: 'attack' });
  addKnob('knob-decay',     { label: 'Decay',     min: 0.001, max: 2,     value: params.decay,           step: 0.001, param: 'decay' });
  addKnob('knob-sustain',   { label: 'Sustain',   min: 0,     max: 1,     value: params.sustain,         step: 0.01,  param: 'sustain' });
  addKnob('knob-release',   { label: 'Release',   min: 0.001, max: 4,     value: params.release,         step: 0.001, param: 'release' });
  addKnob('knob-cutoff',    { label: 'Cutoff',    min: 20,    max: 20000, value: params.filterCutoff,    step: 1,     param: 'filterCutoff' });
  addKnob('knob-resonance', { label: 'Resonance', min: 0,     max: 30,    value: params.filterResonance, step: 0.1,   param: 'filterResonance' });
  addKnob('knob-reverb',    { label: 'Reverb',    min: 0,     max: 1,     value: params.reverbMix,       step: 0.01,  param: 'reverbMix' });
  addKnob('knob-delay',     { label: 'Delay',     min: 0,     max: 1,     value: params.delayTime,       step: 0.01,  param: 'delayTime' });
  addKnob('knob-feedback',  { label: 'Feedback',  min: 0,     max: 0.95,  value: params.delayFeedback,   step: 0.01,  param: 'delayFeedback' });
  addKnob('knob-volume',    { label: 'Volume',    min: 0,     max: 1,     value: params.masterVolume,    step: 0.01,  param: 'masterVolume' });
  addKnob('knob-osc1level', { label: 'OSC1 Lvl',  min: 0,     max: 1,     value: params.osc1Level,       step: 0.01,  param: 'osc1Level' });
  addKnob('knob-osc2level', { label: 'OSC2 Lvl',  min: 0,     max: 1,     value: params.osc2Level,       step: 0.01,  param: 'osc2Level' });

  // Selectors
  function wireSelect(id, param) {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener('change', () => {
      ensureSynth();
      synth.setParam(param, el.value);
    });
  }
  wireSelect('osc1-type', 'osc1Type');
  wireSelect('osc2-type', 'osc2Type');
  wireSelect('osc1-octave', 'osc1Octave');
  wireSelect('osc2-octave', 'osc2Octave');
  wireSelect('osc2-detune', 'osc2Detune');
  wireSelect('filter-type', 'filterType');

  // MIDI setup
  const midiStatus = document.getElementById('midi-status');
  const midiDeviceSelect = document.getElementById('midi-device-select');
  const midiActivity = document.getElementById('midi-activity');
  const midiLogBody = document.getElementById('midi-log-body');
  const clearLogBtn = document.getElementById('clear-log');

  async function initMidi() {
    const ok = await midi.init();
    if (ok) {
      midiStatus.textContent = 'MIDI: Connected';
      midiStatus.className = 'midi-status connected';
      const inputs = midi.getInputs();
      midiDeviceSelect.innerHTML = '<option value="">-- Select Device --</option>';
      inputs.forEach(inp => {
        const opt = document.createElement('option');
        opt.value = inp.id;
        opt.textContent = inp.name;
        midiDeviceSelect.appendChild(opt);
      });
    } else {
      midiStatus.textContent = 'MIDI: Not Available';
      midiStatus.className = 'midi-status disconnected';
    }
  }

  midiDeviceSelect.addEventListener('change', () => {
    if (midiDeviceSelect.value) {
      midi.selectInput(midiDeviceSelect.value);
    }
  });

  midi.onMessage((msg) => {
    ensureSynth();
    // Flash activity
    midiActivity.classList.add('active');
    setTimeout(() => midiActivity.classList.remove('active'), 100);

    // Route to synth
    if (msg.type === 'noteOn') {
      synth.noteOn(msg.note, msg.velocity);
      keyboard.highlightNote(msg.note);
    } else if (msg.type === 'noteOff') {
      synth.noteOff(msg.note);
      keyboard.clearNote(msg.note);
    } else if (msg.type === 'controlChange') {
      if (msg.controller === 1) {
        // modulation - could map to filter cutoff
      } else if (msg.controller === 7) {
        synth.setParam('masterVolume', msg.value / 127);
      } else if (msg.controller === 74) {
        synth.setParam('filterCutoff', (msg.value / 127) * 19980 + 20);
      }
    }

    // Update log display
    updateMidiLog();
  });

  function updateMidiLog() {
    const log = midi.getLog();
    const row = log[log.length - 1];
    if (!row) return;
    const tr = document.createElement('tr');
    tr.className = row.type;
    const time = new Date(row.timestamp).toISOString().slice(11, 23);
    const hex = Array.from(row.raw).map(b => b.toString(16).padStart(2, '0').toUpperCase()).join(' ');
    let decoded = row.type;
    if (row.note !== undefined) decoded += ` note=${row.note}`;
    if (row.velocity !== undefined) decoded += ` vel=${row.velocity}`;
    if (row.controller !== undefined) decoded += ` cc=${row.controller} val=${row.value}`;
    if (row.type === 'pitchBend') decoded += ` val=${row.value}`;
    tr.innerHTML = `<td>${time}</td><td>${row.type}</td><td>${row.channel}</td><td>${hex}</td><td>${decoded}</td>`;
    midiLogBody.appendChild(tr);
    // Keep max 100 rows displayed
    while (midiLogBody.rows.length > 100) midiLogBody.deleteRow(0);
    midiLogBody.parentElement.scrollTop = midiLogBody.parentElement.scrollHeight;
  }

  clearLogBtn.addEventListener('click', () => {
    midiLogBody.innerHTML = '';
  });

  initMidi();
});
