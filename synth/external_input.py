from dataclasses import dataclass
from threading import Lock

import numpy as np


@dataclass(frozen=True)
class AudioInputDevice:
    index: int
    name: str
    max_input_channels: int
    default_samplerate: float


def list_audio_input_devices(print_list: bool = True) -> list[AudioInputDevice]:
    try:
        import sounddevice as sd
    except ImportError:
        if print_list:
            print("sounddevice is not installed. Install dependencies: pip install -r requirements.txt")
        return []

    devices = sd.query_devices()
    out: list[AudioInputDevice] = []
    for idx, device in enumerate(devices):
        max_in = int(device.get("max_input_channels", 0))
        if max_in <= 0:
            continue
        info = AudioInputDevice(
            index=idx,
            name=str(device.get("name", f"Device {idx}")),
            max_input_channels=max_in,
            default_samplerate=float(device.get("default_samplerate", 0.0) or 0.0),
        )
        out.append(info)
        if print_list:
            print(
                f"{info.index}: {info.name} "
                f"(inputs={info.max_input_channels}, default_sr={int(info.default_samplerate)})"
            )

    if print_list and not out:
        print("No available audio input devices.")
    return out


def resolve_audio_input_devices(selectors: list[str] | None = None) -> list[AudioInputDevice]:
    devices = list_audio_input_devices(print_list=False)
    if not selectors:
        return []
    if not devices:
        raise ValueError("No audio input devices found.")

    by_index = {d.index: d for d in devices}
    resolved: list[AudioInputDevice] = []
    seen: set[int] = set()

    for selector in selectors:
        token = selector.strip()
        if not token:
            continue

        selected: AudioInputDevice | None = None
        if token.isdigit() or (token.startswith("-") and token[1:].isdigit()):
            idx = int(token)
            if idx not in by_index:
                raise ValueError(f"Invalid audio input index: {idx}")
            selected = by_index[idx]
        else:
            token_l = token.lower()
            for dev in devices:
                if token_l in dev.name.lower():
                    selected = dev
                    break
            if selected is None:
                raise ValueError(f"Audio input with name not found: {token}")

        if selected.index not in seen:
            resolved.append(selected)
            seen.add(selected.index)

    return resolved


class ExternalAudioInput:
    def __init__(
        self,
        device_index: int,
        device_name: str,
        sample_rate: int,
        block_size: int,
        gain: float = 1.0,
    ) -> None:
        self.device_index = int(device_index)
        self.device_name = device_name
        self.sample_rate = int(sample_rate)
        self.block_size = int(block_size)
        self.gain = float(gain)

        self._stream = None
        self._lock = Lock()
        # FIFO buffer of incoming mono blocks (deque of numpy arrays)
        from collections import deque
        self._buffer = deque()
        self._buffer_size = 0  # in frames/samples
        self._max_buffer_frames = max(4 * self.block_size, int(self.sample_rate * 0.25))
        self._underflow_count = 0
        self._overflow_count = 0
        # keep last captured block for backwards-compatibility / quick inspection
        self._last_mono = np.zeros(self.block_size, dtype=np.float32)

    @property
    def label(self) -> str:
        return f"{self.device_index}: {self.device_name}"

    def start(self) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError(
                    "sounddevice is not installed. Install dependencies: pip install -r requirements.txt"
                ) from exc

        def callback(indata, frames, time_info, status):
            if status:
                pass
            if indata.ndim == 2:
                mono = np.mean(indata, axis=1, dtype=np.float32)
            else:
                mono = np.asarray(indata, dtype=np.float32)
            # ensure shape matches expectation
            if mono.size != frames:
                mono = np.resize(mono, frames)
            with self._lock:
                # push incoming block into FIFO buffer
                self._buffer.append(np.array(mono, dtype=np.float32, copy=True))
                self._buffer_size += mono.size
                # trim if buffer grows too large
                if self._buffer_size > self._max_buffer_frames:
                    # drop oldest until under limit
                    while self._buffer and self._buffer_size > self._max_buffer_frames:
                        dropped = self._buffer.popleft()
                        self._buffer_size -= dropped.size
                        self._overflow_count += 1
                # keep last_mono for quick inspection/debug
                self._last_mono = np.array(mono, dtype=np.float32, copy=True)

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype=np.float32,
            blocksize=self.block_size,
            device=self.device_index,
            callback=callback,
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def get_block(self, frames: int) -> np.ndarray:
        out = np.zeros(frames, dtype=np.float32)
        filled = 0
        with self._lock:
            # consume from FIFO to fill requested frames
            while filled < frames and self._buffer:
                front = self._buffer[0]
                need = frames - filled
                if front.size <= need:
                    out[filled : filled + front.size] = front
                    filled += front.size
                    self._buffer.popleft()
                    self._buffer_size -= front.size
                else:
                    out[filled : filled + need] = front[:need]
                    # replace front with remaining tail
                    self._buffer[0] = front[need:]
                    self._buffer_size -= need
                    filled += need
            # record underflow when buffer couldn't fill requested frames
            if filled < frames:
                self._underflow_count += 1
            # keep last_mono up-to-date for diagnostics
            if self._buffer:
                # peek most recent buffered block for inspection
                self._last_mono = np.array(self._buffer[-1], copy=True)
        return out * self.gain

    def stats(self) -> dict:
        """Return basic diagnostics about buffer usage."""
        with self._lock:
            return {
                "buffer_frames": self._buffer_size,
                "max_buffer_frames": self._max_buffer_frames,
                "underflow_count": self._underflow_count,
                "overflow_count": self._overflow_count,
            }
