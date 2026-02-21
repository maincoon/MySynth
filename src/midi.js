export class MidiInspector {
  constructor() {
    this._midiAccess = null;
    this._callbacks = [];
    this._log = [];
    this._selectedInput = null;
  }

  async init() {
    if (!navigator.requestMIDIAccess) {
      console.warn('Web MIDI API not supported');
      return false;
    }
    try {
      this._midiAccess = await navigator.requestMIDIAccess();
      return true;
    } catch (err) {
      console.warn('MIDI access denied:', err);
      return false;
    }
  }

  getInputs() {
    if (!this._midiAccess) return [];
    const inputs = [];
    this._midiAccess.inputs.forEach((input) => {
      inputs.push({ id: input.id, name: input.name, manufacturer: input.manufacturer });
    });
    return inputs;
  }

  selectInput(id) {
    if (!this._midiAccess) return;
    if (this._selectedInput) {
      this._selectedInput.onmidimessage = null;
    }
    const input = this._midiAccess.inputs.get(id);
    if (input) {
      this._selectedInput = input;
      input.onmidimessage = (e) => this._handleMidiMessage(e);
    }
  }

  onMessage(callback) {
    this._callbacks.push(callback);
  }

  _handleMidiMessage(event) {
    const data = event.data;
    const status = data[0];
    const statusType = status & 0xF0;
    const channel = (status & 0x0F) + 1;
    const timestamp = event.timeStamp || Date.now();

    let parsed = { raw: data, timestamp, channel };

    if (statusType === 0x90 && data[2] > 0) {
      parsed.type = 'noteOn';
      parsed.note = data[1];
      parsed.velocity = data[2];
    } else if (statusType === 0x80 || (statusType === 0x90 && data[2] === 0)) {
      parsed.type = 'noteOff';
      parsed.note = data[1];
      parsed.velocity = data[2] || 0;
    } else if (statusType === 0xB0) {
      parsed.type = 'controlChange';
      parsed.controller = data[1];
      parsed.value = data[2];
    } else if (statusType === 0xE0) {
      parsed.type = 'pitchBend';
      parsed.value = ((data[2] << 7) | data[1]) - 8192;
    } else if (statusType === 0xC0) {
      parsed.type = 'programChange';
      parsed.program = data[1];
    } else {
      parsed.type = 'unknown';
    }

    this._log.push(parsed);
    if (this._log.length > 100) {
      this._log.shift();
    }

    this._callbacks.forEach(cb => cb(parsed));
  }

  getLog() {
    return [...this._log];
  }
}
