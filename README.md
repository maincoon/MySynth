# MySynth — MIDI inspector + Poly VCO synth


This project reads MIDI from a USB keyboard and immediately voices it using a built-in synthesizer:
- VCO waveforms: `sine`, `saw`, `square`
- `Attack` + `Decay` modules after the VCO
- `Rdverb` module on the mixer output
- Polyphony: 16 voices (configurable)
- External audio inputs (for example, a microphone) summed into the main mix
- Modular structure for easy extension

## Installation

```bash
# clone repo and install in editable mode
git clone https://github.com/maincoon/MySynth.git
cd MySynth
python -m pip install --upgrade pip
pip install -e .
```

After installation the `mysynth` command is available.

## Quick Start

1. Check available inputs:

   ```bash
   python MySynth.py --list
   python MySynth.py --list-audio-inputs
   ```

3. List MIDI devices and choose an index:

   ```bash
   python MySynth.py --list
   python MySynth.py --midi-device 1 --gui
   ```

4. Run the application (GUI or console):

   ```bash
   python MySynth.py --gui
   python MySynth.py --gui --audio-input 2
   python MySynth.py --gui --audio-input 2 --audio-input "USB Microphone"
   python MySynth.py --nogui
   ```

## Examples

```bash
python MySynth.py --midi-device 1 --waveform saw --polyphony 16 --gui --scale 1.6
python MySynth.py --midi-device 1 --audio-input 2 --audio-input "USB" --gui
python MySynth.py --midi-device 1 --waveform sine --nogui
python MySynth.py --attack 0.03 --decay 0.5 --rdverb 0.2 --gui
python MySynth.py --attack-knob 73 --decay-knob 75 --rdverb-knob 91 --gui
python MySynth.py --rdverb 0.25 --rdverb-feedback 0.72 --rdverb-delay-ms 320 --gui
python MySynth.py --rdverb-feedback-knob 88 --rdverb-delay-knob 89 --gui
```

You can pass `--audio-input` multiple times: each selected input is added to the static mix (synth + all inputs), then the mix is processed by `Rdverb` and the result is sent to the oscilloscope and audio output.

## Attack / Decay / Rdverb

- `--attack` — attack time (seconds)
- `--decay` — decay time (seconds)
- `--rdverb` — amount of `Rdverb` effect (0..1)
- `--rdverb-feedback` — feedback coefficient (0..0.97)
- `--rdverb-delay-ms` — delay time (10..2000 ms)
- `--attack-knob`, `--decay-knob` — MIDI CC numbers to control Attack/Decay
- `--rdverb-feedback-knob`, `--rdverb-delay-knob` — MIDI CC numbers for Rdverb feedback/delay

`Rdverb` contains a built-in guard against self-oscillation: if the level grows dangerously it automatically reduces the effective feedback and softly limits the signal.

## Assigning names to knobs (CC)

You can assign names to knobs via the CLI: `--cc-name 74=Filter --cc-name 71=Resonance` — they will appear in the control panel and will be shown even if no messages from the device have arrived yet.
The `Seen CCs` panel shows only CCs explicitly specified via CLI (`--cc-name`, `--attack-knob`, `--decay-knob`, `--rdverb-feedback-knob`, `--rdverb-delay-knob`, etc.).

## Interface

The GUI is split into three panes: Logs (MIDI log), Oscilloscope (live output waveform) and Controls (list of CCs, active notes, waveform selection).

## OS dependencies (if GUI or wheel build failed)

On Debian/Ubuntu:

```bash
sudo apt update && sudo apt install -y python3-dev build-essential python3-tk portaudio19-dev
```

If installation of `python-rtmidi` fails, install `build-essential` and `python3-dev`.
If `sounddevice` cannot open the output, check PortAudio (`portaudio19-dev`).

## License

MIT License — see [LICENSE](LICENSE) file.

