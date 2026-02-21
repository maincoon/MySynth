import mido


def list_input_ports() -> list[str]:
    ports = mido.get_input_names()
    for i, name in enumerate(ports):
        print(f"{i}: {name}")
    if not ports:
        print("No available MIDI inputs.")
    return ports


def resolve_input_port(device_index: int | None = None, name_substring: str | None = None) -> str | None:
    ports = mido.get_input_names()
    if not ports:
        return None

    if device_index is not None:
        if 0 <= device_index < len(ports):
            return ports[device_index]
        raise ValueError(f"Invalid MIDI device index: {device_index}. Range: 0..{len(ports)-1}")

    if name_substring:
        for p in ports:
            if name_substring.lower() in p.lower():
                return p

    for pat in ("minilab3", "minilab", "arturia"):
        for p in ports:
            if pat in p.lower():
                return p

    for p in ports:
        low = p.lower()
        if "through" not in low and "midi through" not in low:
            return p

    return ports[0]
