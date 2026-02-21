NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_note_to_freq(note: int) -> float:
    return 440.0 * (2.0 ** ((note - 69) / 12.0))


def note_name(note: int) -> str:
    return f"{NOTE_NAMES[note % 12]}{(note // 12) - 1}"
