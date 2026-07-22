"""ArtDMX packet format — the ONE place the wire bytes are defined.

Used by artnet_output_manager.py (production unicast to the room nodes),
sim/virtual_dmx.py (the BlenderDMX mirror) and tools/artnet_check.py (the
bench listener/selftest), so a format change can't fork between them. The
node-side parser (sim/esphome/components/artnet_dmx) mirrors this layout.
"""

ARTNET_PORT = 6454
_HEADER = b'Art-Net\x00'
_OP_DMX = b'\x00\x50'      # OpDmx, little-endian
_PROTOCOL = b'\x00\x0e'    # protocol version 14


def build_artdmx(sequence, universe, data, pad_to=512):
    """Build an ArtDMX packet. sequence 1..255 (0 = sequence disabled),
    universe = SubUni+Net as one little-endian 15-bit value, data = channel
    bytes (padded with zeros to pad_to — full-universe packets keep cheap
    receivers that dislike short frames happy)."""
    payload = bytes(data).ljust(pad_to, b'\x00')
    return (
        _HEADER
        + _OP_DMX
        + _PROTOCOL
        + bytes([sequence & 0xFF, 0x00])           # sequence, physical
        + int(universe).to_bytes(2, 'little')      # SubUni + Net
        + len(payload).to_bytes(2, 'big')
        + payload
    )


def parse_artdmx(packet):
    """Return (sequence, universe, data) or None if not an ArtDMX packet."""
    if len(packet) < 18 or packet[:8] != _HEADER or packet[8:10] != _OP_DMX:
        return None
    length = int.from_bytes(packet[16:18], 'big')
    return packet[12], int.from_bytes(packet[14:16], 'little'), packet[18:18 + length]
