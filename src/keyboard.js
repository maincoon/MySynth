export class OnScreenKeyboard {
  constructor(container, { onNoteOn, onNoteOff }) {
    this.container = container;
    this.onNoteOn = onNoteOn;
    this.onNoteOff = onNoteOff;
    this.keys = new Map(); // midiNote -> element
    this.activePointers = new Map(); // pointerId -> midiNote
    this._render();
  }

  _render() {
    this.container.innerHTML = '';
    this.container.classList.add('keyboard');

    // C3=48 to B5=83 (3 octaves)
    const startNote = 48;
    const endNote = 83;

    const noteNames = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
    const isBlack = [false, true, false, true, false, false, true, false, true, false, true, false];

    const wrapper = document.createElement('div');
    wrapper.className = 'keyboard-wrapper';

    for (let note = startNote; note <= endNote; note++) {
      const noteIndex = note % 12;
      const black = isBlack[noteIndex];
      const key = document.createElement('div');
      key.className = black ? 'key black-key' : 'key white-key';
      key.dataset.note = note;
      key.dataset.name = noteNames[noteIndex] + Math.floor(note / 12 - 1);
      key.title = key.dataset.name;

      key.addEventListener('mousedown', (e) => {
        e.preventDefault();
        this.onNoteOn(note, 100);
        key.classList.add('active');
      });
      key.addEventListener('mouseup', () => {
        this.onNoteOff(note);
        key.classList.remove('active');
      });
      key.addEventListener('mouseleave', () => {
        if (key.classList.contains('active')) {
          this.onNoteOff(note);
          key.classList.remove('active');
        }
      });
      key.addEventListener('touchstart', (e) => {
        e.preventDefault();
        this.onNoteOn(note, 100);
        key.classList.add('active');
      }, { passive: false });
      key.addEventListener('touchend', (e) => {
        e.preventDefault();
        this.onNoteOff(note);
        key.classList.remove('active');
      }, { passive: false });

      wrapper.appendChild(key);
      this.keys.set(note, key);
    }

    this.container.appendChild(wrapper);
  }

  highlightNote(midiNote) {
    const key = this.keys.get(midiNote);
    if (key) key.classList.add('active');
  }

  clearNote(midiNote) {
    const key = this.keys.get(midiNote);
    if (key) key.classList.remove('active');
  }
}
