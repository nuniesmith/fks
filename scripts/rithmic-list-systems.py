#!/usr/bin/env python3
"""Ask a Rithmic R|Protocol gateway which system names it accepts.

UNAUTHENTICATED by design: RequestRithmicSystemInfo (template_id 16) carries no
credentials, so this cannot contribute to a failed-login lockout. That is the
whole reason to use it for diagnosis instead of retrying logins.

Hand-rolls the WebSocket framing + protobuf encoding so it needs no third-party
packages (this host's Python is PEP-668 managed, and adding a dep to diagnose a
config value is not worth it). Field numbers come from rithmic-rs's generated
src/rti.rs, not from guesswork:
    RequestRithmicSystemInfo.template_id  tag 154467 (int32, required)
    ResponseRithmicSystemInfo.template_id tag 154467
    ResponseRithmicSystemInfo.rp_code     tag 132766 (repeated string)
    ResponseRithmicSystemInfo.system_name tag 153628 (repeated string)

Rithmic frames each protobuf message with a 4-byte big-endian length prefix
inside a single binary WebSocket frame.
"""
import base64
import os
import socket
import ssl
import struct
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "rituz00100.rithmic.com"
PORT = 443


def varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def tag(field: int, wire: int) -> bytes:
    return varint((field << 3) | wire)


def ws_frame(payload: bytes) -> bytes:
    """Client->server binary frame, masked (RFC 6455 requires client masking)."""
    header = bytearray([0x82])  # FIN + opcode 0x2 (binary)
    n = len(payload)
    if n < 126:
        header.append(0x80 | n)
    elif n < 65536:
        header.append(0x80 | 126)
        header += struct.pack(">H", n)
    else:
        header.append(0x80 | 127)
        header += struct.pack(">Q", n)
    mask = os.urandom(4)
    header += mask
    return bytes(header) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload))


def read_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise EOFError("connection closed mid-frame")
        buf += chunk
    return buf


def read_ws_message(sock):
    b0, b1 = read_exact(sock, 2)
    opcode = b0 & 0x0F
    ln = b1 & 0x7F
    if ln == 126:
        ln = struct.unpack(">H", read_exact(sock, 2))[0]
    elif ln == 127:
        ln = struct.unpack(">Q", read_exact(sock, 8))[0]
    return opcode, read_exact(sock, ln)


def parse_fields(buf: bytes):
    """Minimal protobuf reader -> {field_number: [raw values]}."""
    out, i = {}, 0
    while i < len(buf):
        key, i = read_varint(buf, i)
        field, wire = key >> 3, key & 7
        if wire == 0:
            val, i = read_varint(buf, i)
        elif wire == 2:
            ln, i = read_varint(buf, i)
            val, i = buf[i:i + ln], i + ln
        elif wire == 5:
            val, i = buf[i:i + 4], i + 4
        elif wire == 1:
            val, i = buf[i:i + 8], i + 8
        else:
            break
        out.setdefault(field, []).append(val)
    return out


def read_varint(buf, i):
    shift = res = 0
    while True:
        b = buf[i]
        i += 1
        res |= (b & 0x7F) << shift
        if not b & 0x80:
            return res, i
        shift += 7


# ── WebSocket handshake ──────────────────────────────────────────────────────
key = base64.b64encode(os.urandom(16)).decode()
raw = socket.create_connection((HOST, PORT), timeout=15)
sock = ssl.create_default_context().wrap_socket(raw, server_hostname=HOST)
sock.sendall(
    f"GET / HTTP/1.1\r\nHost: {HOST}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
    f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n".encode()
)
resp = b""
while b"\r\n\r\n" not in resp:
    resp += sock.recv(4096)
status = resp.split(b"\r\n")[0].decode(errors="replace")
print(f"  handshake: {status}")
if b"101" not in resp.split(b"\r\n")[0]:
    sys.exit("  websocket upgrade refused")

# ── RequestRithmicSystemInfo{template_id=16} ─────────────────────────────────
body = tag(154467, 0) + varint(16)
sock.sendall(ws_frame(struct.pack(">I", len(body)) + body))
print("  sent RequestRithmicSystemInfo (template_id=16, no credentials)")

sock.settimeout(15)
opcode, msg = read_ws_message(sock)
if opcode == 0x8:
    code = struct.unpack(">H", msg[:2])[0] if len(msg) >= 2 else "?"
    sys.exit(f"  server closed: code={code} reason={msg[2:].decode(errors='replace')!r}")

payload = msg[4:] if len(msg) > 4 else msg  # strip the 4-byte length prefix
fields = parse_fields(payload)

tid = fields.get(154467, [None])[0]
rp = [v.decode(errors="replace") for v in fields.get(132766, [])]
systems = [v.decode(errors="replace") for v in fields.get(153628, [])]

print(f"  response template_id: {tid}")
print(f"  rp_code: {rp}")
print()
if systems:
    print(f"  VALID SYSTEM NAMES on {HOST} ({len(systems)}):")
    for s in systems:
        print(f"    - {s!r}")
else:
    print("  (no system_name entries returned)")
sock.close()
