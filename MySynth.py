#!/usr/bin/env python3
"""MIDI inspector + modular polyphonic VCO synth (sine/saw/square)."""

import argparse
import sys
import time

import mido

from synth import (
    AudioEngine,
    ExternalAudioInput,
    PolySynth,
    list_audio_input_devices,
    list_input_ports,
    resolve_audio_input_devices,
    resolve_input_port,
)
from synth.music import note_name


class MidiSynthApp:
    def __init__(
        self,
        port_name: str,
        waveform: str = "saw",
        polyphony: int = 16,
        sample_rate: int = 48000,
        block_size: int = 256,
        cc_labels: dict | None = None,
        attack_seconds: float = 0.01,
        decay_seconds: float = 0.35,
        rdverb_mix: float = 0.15,
        rdverb_feedback: float = 0.45,
        rdverb_delay_ms: float = 180.0,
        attack_knob_cc: int | None = None,
        decay_knob_cc: int | None = None,
        rdverb_knob_cc: int | None = None,
        rdverb_feedback_knob_cc: int | None = None,
        rdverb_delay_knob_cc: int | None = None,
        visible_ccs: set[int] | None = None,
        external_inputs: list[ExternalAudioInput] | None = None,
        audio_debug: bool = False,
    ) -> None:
        self.port_name = port_name
        self.synth = PolySynth(polyphony=polyphony, sample_rate=sample_rate, waveform=waveform)
        self.external_inputs = external_inputs or []
        self.audio_debug = audio_debug
        self.audio = AudioEngine(
            self.synth,
            sample_rate=sample_rate,
            block_size=block_size,
            external_inputs=self.external_inputs,
        )
        self.active_notes: set[int] = set()
        self.cc_values: dict[int, int] = {}
        self.pitch_bend = 0
        # user-provided CC id -> label mapping
        self.cc_labels: dict[int, str] = cc_labels or {}
        self.attack_knob_cc = attack_knob_cc
        self.decay_knob_cc = decay_knob_cc
        self.rdverb_knob_cc = rdverb_knob_cc
        self.rdverb_feedback_knob_cc = rdverb_feedback_knob_cc
        self.rdverb_delay_knob_cc = rdverb_delay_knob_cc
        self.visible_ccs = set(visible_ccs or set())

        self.synth.set_attack_seconds(max(0.0, float(attack_seconds)))
        self.synth.set_decay_seconds(max(0.001, float(decay_seconds)))
        self.audio.set_rdverb_mix(max(0.0, min(1.0, float(rdverb_mix))))
        self.audio.set_rdverb_feedback(max(0.0, min(0.97, float(rdverb_feedback))))
        self.audio.set_rdverb_delay_ms(max(10.0, min(2000.0, float(rdverb_delay_ms))))

        if self.attack_knob_cc is not None:
            self.cc_labels.setdefault(self.attack_knob_cc, "Attack")
        if self.decay_knob_cc is not None:
            self.cc_labels.setdefault(self.decay_knob_cc, "Decay")
        if self.rdverb_knob_cc is not None:
            self.cc_labels.setdefault(self.rdverb_knob_cc, "Rdverb")
        if self.rdverb_feedback_knob_cc is not None:
            self.cc_labels.setdefault(self.rdverb_feedback_knob_cc, "Rdverb Feedback")
        if self.rdverb_delay_knob_cc is not None:
            self.cc_labels.setdefault(self.rdverb_delay_knob_cc, "Rdverb Delay")

    def _log_line(self, msg) -> str:
        return f"{time.strftime('%H:%M:%S')}  {msg}  bytes={msg.bytes()}"

    def process_midi_message(self, msg) -> None:
        if msg.type == "note_on" and getattr(msg, "velocity", 0) > 0:
            self.active_notes.add(msg.note)
            self.synth.note_on(msg.note, msg.velocity)
            return

        if msg.type in ("note_off",) or (msg.type == "note_on" and getattr(msg, "velocity", 0) == 0):
            self.active_notes.discard(msg.note)
            self.synth.note_off(msg.note)
            return

        if msg.type == "control_change":
            self.cc_values[msg.control] = msg.value
            if self.attack_knob_cc is not None and msg.control == self.attack_knob_cc:
                attack_seconds = (msg.value / 127.0) * 2.0
                self.synth.set_attack_seconds(attack_seconds)
            if self.decay_knob_cc is not None and msg.control == self.decay_knob_cc:
                decay_seconds = 0.01 + (msg.value / 127.0) * 2.99
                self.synth.set_decay_seconds(decay_seconds)
            if self.rdverb_knob_cc is not None and msg.control == self.rdverb_knob_cc:
                rdverb_mix = msg.value / 127.0
                self.audio.set_rdverb_mix(rdverb_mix)
            if self.rdverb_feedback_knob_cc is not None and msg.control == self.rdverb_feedback_knob_cc:
                rdverb_feedback = (msg.value / 127.0) * 0.97
                self.audio.set_rdverb_feedback(rdverb_feedback)
            if self.rdverb_delay_knob_cc is not None and msg.control == self.rdverb_delay_knob_cc:
                rdverb_delay_ms = 10.0 + (msg.value / 127.0) * 1990.0
                self.audio.set_rdverb_delay_ms(rdverb_delay_ms)
            return

        if msg.type == "pitchwheel":
            # mido provides -8192..+8191 — keep raw for display and pass to synth
            self.pitch_bend = msg.pitch
            try:
                self.synth.set_pitch_bend_raw(msg.pitch)
            except Exception:
                pass
            return

        if msg.type in ("stop", "reset"):
            self.active_notes.clear()
            self.synth.all_notes_off()

    def run_console(self) -> None:
        print(f"Opened MIDI input: {self.port_name}")
        if self.external_inputs:
            print("External audio inputs:")
            for ext in self.external_inputs:
                print(f"  - {ext.label}")
        else:
            print("External audio inputs: disabled")
        print("Synth: VCO + 16-voice polyphony (default), Ctrl+C to exit.\n")
        try:
            self.audio.start()
        except RuntimeError as err:
            print(err)
            return

        # optional audio debugging: print external input buffer stats periodically
        if getattr(self, "audio_debug", False) and self.external_inputs:
            import threading

            def _print_stats():
                import os
                logpath = os.environ.get("MYSYNTH_AUDIO_LOG", "/tmp/mysynth-audio.log")
                # ensure file exists
                try:
                    open(logpath, "a").close()
                except Exception:
                    logpath = None
                while True:
                    try:
                        lines = []
                        for ext in self.external_inputs:
                            try:
                                s = ext.stats()
                                line = f"[audio-stat] {ext.label} frames={s['buffer_frames']}/{s['max_buffer_frames']} underflow={s['underflow_count']} overflow={s['overflow_count']}"
                                print(line)
                                lines.append(line)
                            except Exception:
                                pass
                        if logpath:
                            try:
                                with open(logpath, "a") as f:
                                    for L in lines:
                                        f.write(L + "\n")
                            except Exception:
                                pass
                        time.sleep(1.0)
                    except Exception:
                        break

            t = threading.Thread(target=_print_stats, daemon=True)
            t.start()

        try:
            with mido.open_input(self.port_name) as inport:
                for msg in inport:
                    print(self._log_line(msg))
                    self.process_midi_message(msg)
                    if self.active_notes:
                        names = " ".join(sorted(note_name(n) for n in self.active_notes))
                        print("  Active:", names)
        except KeyboardInterrupt:
            print("\nExit")
        finally:
            self.synth.all_notes_off()
            self.audio.stop()

    def run_gui(self, scale: float = 1.6) -> None:
        try:
            import tkinter as tk
            from tkinter import ttk
        except Exception as exc:
            print("Tkinter not available:", exc)
            self.run_console()
            return

        # controller root (hidden) — use three separate windows
        root = tk.Tk()
        root.withdraw()

        # runtime UI scale
        self.ui_scale = max(0.5, float(scale))

        # helper to compute fonts/sizes from scale
        def fonts_from_scale(s: float):
            return {
                "log_font": ("Courier", max(12, int(12 * s))),
                "notes_font": ("Monospace", max(16, int(16 * s))),
                "label_font": ("TkDefaultFont", max(12, int(12 * s))),
                "value_font": ("TkDefaultFont", max(11, int(11 * s))),
            }

        f = fonts_from_scale(self.ui_scale)

        # Logs window
        logs_win = tk.Toplevel(root)
        logs_win.title(f"Logs — {self.port_name}")
        logs_win.geometry(f"{int(760 * self.ui_scale)}x{int(420 * self.ui_scale)}+30+30")
        txt = tk.Text(logs_win, state="disabled", font=f["log_font"])
        txt.pack(fill="both", expand=True, padx=8, pady=8)

        # Oscilloscope window
        scope_win = tk.Toplevel(root)
        scope_win.title(f"Oscilloscope — {self.port_name}")
        scope_win.geometry(f"{int(980 * self.ui_scale)}x{int(220 * self.ui_scale)}+30+470")
        osc_width = max(640, int(900 * self.ui_scale))
        osc_height = max(140, int(180 * self.ui_scale))
        osc_canvas = tk.Canvas(scope_win, width=osc_width, height=osc_height, highlightthickness=0)
        osc_canvas.pack(fill="both", expand=True, padx=8, pady=8)

        # Controls window
        ctrl_win = tk.Toplevel(root)
        ctrl_win.title(f"Controls — {self.port_name}")
        ctrl_win.geometry(f"{int(520 * self.ui_scale)}x{int(700 * self.ui_scale)}+820+30")

        ttk.Label(ctrl_win, text="External inputs:", font=f["label_font"]).pack(anchor="w", padx=8, pady=(8, 0))
        inputs_text = "\n".join(ext.label for ext in self.external_inputs) if self.external_inputs else "—"
        ttk.Label(ctrl_win, text=inputs_text, font=f["value_font"]).pack(anchor="w", padx=8, pady=(0, 8))

        ttk.Label(ctrl_win, text="Active notes:", font=f["label_font"]).pack(anchor="w", padx=8, pady=(8, 0))
        notes_var = tk.StringVar(value="—")
        notes_display = ttk.Label(ctrl_win, textvariable=notes_var, font=f["notes_font"])
        notes_display.pack(fill="x", padx=8, pady=(0, 8))

        ttk.Label(ctrl_win, text="Seen CCs:", font=f["label_font"]).pack(anchor="w", padx=8)
        cc_frame = ttk.Frame(ctrl_win)
        cc_frame.pack(fill="both", expand=True, padx=8, pady=6)

        ttk.Label(ctrl_win, text="Pitch bend:", font=f["label_font"]).pack(anchor="w", padx=8)
        pitch_var = tk.StringVar(value="0")
        pitch_display = ttk.Label(ctrl_win, textvariable=pitch_var, font=f["value_font"])
        pitch_display.pack(anchor="w", padx=8, pady=(0, 8))

        # waveform selector
        ttk.Label(ctrl_win, text="Waveform:", font=f["label_font"]).pack(anchor="w", padx=8, pady=(8, 0))
        waveform_var = tk.StringVar(value=self.synth.waveform.value)
        waveform_box = ttk.Combobox(ctrl_win, textvariable=waveform_var, values=["sine", "saw", "square"], state="readonly", font=f["value_font"])
        waveform_box.pack(anchor="w", padx=8, pady=(0, 8))

        def on_waveform_change(ev=None):
            self.synth.set_waveform(waveform_var.get())

        waveform_box.bind("<<ComboboxSelected>>", on_waveform_change)

        # live UI scale control
        def apply_ui_scale(new_scale: float) -> None:
            self.ui_scale = max(0.5, float(new_scale))
            nf = fonts_from_scale(self.ui_scale)
            # resize windows
            logs_win.geometry(f"{int(760 * self.ui_scale)}x{int(420 * self.ui_scale)}+30+30")
            scope_win.geometry(f"{int(980 * self.ui_scale)}x{int(220 * self.ui_scale)}+30+470")
            ctrl_win.geometry(f"{int(520 * self.ui_scale)}x{int(700 * self.ui_scale)}+820+30")
            # fonts
            txt.config(font=nf["log_font"])
            notes_display.config(font=nf["notes_font"])
            pitch_display.config(font=nf["value_font"])
            waveform_box.config(font=nf["value_font"])
            # osc size
            osc_canvas.config(width=max(640, int(900 * self.ui_scale)), height=max(140, int(180 * self.ui_scale)))
            # update existing CC widgets
            for cc_num, (lbl, bar, val) in cc_widgets.items():
                lbl.config(font=nf["label_font"])
                val.config(font=nf["value_font"])
                try:
                    bar.config(length=max(220, int(300 * self.ui_scale)))
                except Exception:
                    pass

        ttk.Label(ctrl_win, text="UI scale:", font=f["label_font"]).pack(anchor="w", padx=8, pady=(6, 0))
        ui_scale_var = tk.DoubleVar(value=self.ui_scale)
        ui_scale_slider = ttk.Scale(ctrl_win, from_=0.75, to=3.0, orient="horizontal", variable=ui_scale_var, command=lambda v: apply_ui_scale(float(v)))
        ui_scale_slider.pack(fill="x", padx=8, pady=(0, 8))

        cc_widgets: dict[int, tuple] = {}

        # apply initial UI scale to widgets
        try:
            apply_ui_scale(self.ui_scale)
        except Exception:
            pass

        def log(line: str) -> None:
            txt.config(state="normal")
            txt.insert("end", line + "\n")
            txt.see("end")
            if int(txt.index("end-1c").split(".")[0]) > 4000:
                txt.delete("1.0", "800.0")
            txt.config(state="disabled")

        try:
            self.audio.start()
        except RuntimeError as err:
            print(err)
            logs_win.destroy(); scope_win.destroy(); ctrl_win.destroy(); root.destroy()
            return

        try:
            inport = mido.open_input(self.port_name)
        except Exception as exc:
            self.audio.stop()
            print(f"Failed to open MIDI port: {exc}")
            logs_win.destroy(); scope_win.destroy(); ctrl_win.destroy(); root.destroy()
            return

        def draw_waveform() -> None:
            block = self.audio.get_last_mono_block()
            width = max(2, osc_canvas.winfo_width())
            height = max(2, osc_canvas.winfo_height())
            mid = height / 2.0
            amp = (height * 0.42)
            osc_canvas.delete("all")
            osc_canvas.create_line(0, mid, width, mid)
            if block.size < 2:
                return
            step = max(1, int(block.size / width))
            view = block[::step]
            if view.size < 2:
                return
            x = [i * (width / (view.size - 1)) for i in range(view.size)]
            y = [mid - float(s) * amp for s in view]
            points = []
            for px, py in zip(x, y):
                points.extend((px, py))
            osc_canvas.create_line(*points, width=2, smooth=True)

        def update_widgets() -> None:
            notes_var.set(" ".join(sorted(note_name(n) for n in self.active_notes)) or "—")
            pitch_var.set(str(self.pitch_bend))

            # show union of seen CCs and user-mapped CCs
            cc_keys = sorted(self.visible_ccs)
            for idx, cc_num in enumerate(cc_keys, start=1):
                cc_val = self.cc_values.get(cc_num, 0)
                if cc_num not in cc_widgets:
                    row = idx
                    label_text = self.cc_labels.get(cc_num, f"CC {cc_num:3d}")
                    lbl = ttk.Label(cc_frame, text=label_text, font=fonts_from_scale(self.ui_scale)["label_font"])
                    bar = ttk.Progressbar(cc_frame, length=max(220, int(300 * self.ui_scale)), maximum=127)
                    val = ttk.Label(cc_frame, text=str(cc_val), width=4, font=fonts_from_scale(self.ui_scale)["value_font"])
                    lbl.grid(row=row, column=0, sticky="w", padx=6, pady=4)
                    bar.grid(row=row, column=1, sticky="w", padx=6, pady=4)
                    val.grid(row=row, column=2, sticky="w", padx=6)
                    cc_widgets[cc_num] = (lbl, bar, val)

                cc_widgets[cc_num][1]["value"] = cc_val
                cc_widgets[cc_num][2]["text"] = str(cc_val)

        def poll() -> None:
            for msg in inport.iter_pending():
                log(self._log_line(msg))
                self.process_midi_message(msg)
            update_widgets()
            draw_waveform()
            root.after(20, poll)

        def on_close_all() -> None:
            try:
                inport.close()
            except Exception:
                pass
            self.synth.all_notes_off()
            self.audio.stop()
            logs_win.destroy(); scope_win.destroy(); ctrl_win.destroy(); root.destroy()

        logs_win.protocol("WM_DELETE_WINDOW", on_close_all)
        scope_win.protocol("WM_DELETE_WINDOW", on_close_all)
        ctrl_win.protocol("WM_DELETE_WINDOW", on_close_all)

        root.after(20, poll)
        root.mainloop()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true", help="list MIDI and audio input devices and exit")
    parser.add_argument("--list-audio-inputs", action="store_true", help="list audio input devices and exit")
    parser.add_argument("--midi-device", type=int, default=None, help="MIDI input index from --list")
    parser.add_argument("--port", "-p", default=None, help="MIDI input substring fallback")
    parser.add_argument(
        "--audio-input",
        action="append",
        default=[],
        help="audio input index or substring from --list-audio-inputs; repeat to add multiple inputs",
    )
    parser.add_argument("--waveform", choices=["sine", "saw", "square"], default="saw")
    parser.add_argument("--polyphony", type=int, default=16)
    parser.add_argument("--sample-rate", type=int, default=48000)
    parser.add_argument("--block-size", type=int, default=256)
    parser.add_argument("--scale", "-s", type=float, default=2.0, help="GUI scale factor")
    parser.add_argument("--cc-name", action="append", default=[], help="map CC id to label; format: 74=Filter")
    parser.add_argument("--attack", type=float, default=0.01, help="Attack time in seconds")
    parser.add_argument("--decay", type=float, default=0.35, help="Decay time in seconds")
    parser.add_argument("--rdverb", type=float, default=0.15, help="Rdverb wet mix (0..1)")
    parser.add_argument("--rdverb-feedback", type=float, default=0.45, help="Rdverb feedback (0..0.97)")
    parser.add_argument("--rdverb-delay-ms", type=float, default=180.0, help="Rdverb delay time in ms (10..2000)")
    parser.add_argument("--attack-knob", type=int, default=None, help="CC id to control Attack")
    parser.add_argument("--decay-knob", type=int, default=None, help="CC id to control Decay")
    parser.add_argument("--rdverb-knob", type=int, default=None, help="CC id to control Rdverb mix")
    parser.add_argument("--rdverb-feedback-knob", type=int, default=None, help="CC id to control Rdverb feedback")
    parser.add_argument("--rdverb-delay-knob", type=int, default=None, help="CC id to control Rdverb delay time")
    parser.add_argument("--audio-debug", action="store_true", help="print external input buffer stats (debug)")
    parser.add_argument("--nogui", action="store_true", help="console mode only")
    parser.add_argument("--gui", action="store_true", help="force GUI")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()

    if args.list:
        print("MIDI inputs:")
        list_input_ports()
        print("\nAudio inputs:")
        list_audio_input_devices(print_list=True)
        return
    if args.list_audio_inputs:
        list_audio_input_devices(print_list=True)
        return

    ports = list_input_ports()

    if not ports:
        print("No MIDI ports. Check device connection.")
        sys.exit(1)

    try:
        port_name = resolve_input_port(device_index=args.midi_device, name_substring=args.port)
    except ValueError as err:
        print(err)
        sys.exit(2)

    if not port_name:
        print("Failed to select MIDI port.")
        sys.exit(1)

    print(f"Selected MIDI port: {port_name}")

    try:
        selected_audio_inputs = resolve_audio_input_devices(args.audio_input)
    except ValueError as err:
        print(err)
        sys.exit(2)

    external_inputs = []
    for dev in selected_audio_inputs:
        # open audio input at the engine/sample-rate so returned blocks match synth timing
        sr = max(8000, args.sample_rate)
        if int(dev.default_samplerate) and int(dev.default_samplerate) != sr:
            print(f"[info] opening audio input '{dev.name}' at app sample_rate={sr} (device default={int(dev.default_samplerate)})")
        external_inputs.append(
            ExternalAudioInput(
                device_index=dev.index,
                device_name=dev.name,
                sample_rate=sr,
                block_size=max(64, args.block_size),
            )
        )

    if selected_audio_inputs:
        print("Selected external audio inputs:")
        for dev in selected_audio_inputs:
            print(f"  - {dev.index}: {dev.name}")

    # parse CC name mappings --cc-name 74=Filter
    cc_labels: dict[int, str] = {}
    visible_ccs: set[int] = set()
    for entry in args.cc_name:
        if "=" not in entry:
            print(f"Invalid --cc-name format: {entry} (expected id=name)")
            sys.exit(2)
        i, name = entry.split("=", 1)
        try:
            cc_id = int(i)
            cc_labels[cc_id] = name
            visible_ccs.add(cc_id)
        except ValueError:
            print(f"Invalid CC id in --cc-name: {i}")
            sys.exit(2)

    for knob_cc in [args.attack_knob, args.decay_knob, args.rdverb_knob, args.rdverb_feedback_knob, args.rdverb_delay_knob]:
        if knob_cc is not None:
            visible_ccs.add(int(knob_cc))

    app = MidiSynthApp(
        port_name=port_name,
        waveform=args.waveform,
        polyphony=max(1, args.polyphony),
        sample_rate=max(8000, args.sample_rate),
        block_size=max(64, args.block_size),
        cc_labels=cc_labels,
        attack_seconds=max(0.0, float(args.attack)),
        decay_seconds=max(0.001, float(args.decay)),
        rdverb_mix=max(0.0, min(1.0, float(args.rdverb))),
        rdverb_feedback=max(0.0, min(0.97, float(args.rdverb_feedback))),
        rdverb_delay_ms=max(10.0, min(2000.0, float(args.rdverb_delay_ms))),
        attack_knob_cc=args.attack_knob,
        decay_knob_cc=args.decay_knob,
        rdverb_knob_cc=args.rdverb_knob,
        rdverb_feedback_knob_cc=args.rdverb_feedback_knob,
        rdverb_delay_knob_cc=args.rdverb_delay_knob,
        visible_ccs=visible_ccs,
        external_inputs=external_inputs,
        audio_debug=bool(args.audio_debug),
    )

    if args.nogui:
        app.run_console()
        return

    if args.gui:
        app.run_gui(scale=max(0.75, args.scale))
        return

    try:
        import tkinter  # noqa: F401
        app.run_gui(scale=max(0.75, args.scale))
    except Exception:
        app.run_console()


if __name__ == "__main__":
    main()
