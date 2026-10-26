#!/usr/bin/env python3
"""Direct Mac-to-K16 UEFI PXE/HTTP boot and real-time UDP diagnostics.

Set AIUEOS_PXE_BOOT to the EFI application to serve.  The remaining
AIUEOS_PXE_* variables override the direct-link defaults used by the physical
K16 qualification setup.
"""

import argparse
import collections
import hashlib
import http.server
import json
import os
import queue
import re
import select
import socket
import stat
import struct
import tempfile
import subprocess
import sys
import threading
import types
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def private_file_text(path_value, label, max_bytes):
    """Read one owner-only regular file without following a symlink."""
    if not path_value:
        return ""
    path = Path(path_value).expanduser()
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode):
            raise RuntimeError(f"{label} is not a regular file")
        if details.st_uid != os.getuid() or details.st_mode & 0o077:
            raise RuntimeError(f"{label} must be owned by this user with mode 0600")
        if details.st_size > max_bytes:
            raise RuntimeError(f"{label} is too large")
        value = os.read(descriptor, max_bytes + 1).decode("ascii").strip()
        if not value or len(value.encode("ascii")) > max_bytes:
            raise RuntimeError(f"{label} is empty or too large")
        return value
    finally:
        os.close(descriptor)


WORKER_ERROR_LABELS = {
    0: "none",
    1: "not-started",
    2: "dns",
    3: "request-or-entropy",
    4: "clienthello-build",
    5: "tcp-syn-send",
    6: "tcp-syn-ack",
    7: "clienthello-send",
    9: "certificate-verify",
    10: "finished-http-send",
    11: "http-response-timeout",
    12: "tls-flight-size",
    13: "finished-build",
    14: "http-protect",
    15: "nic-restart",
    60: "response-parse",
}
WORKER_PUMP_LABELS = {
    0: "none",
    1: "receive-timeout",
    2: "unexpected-tcp-segment",
    3: "tcp-payload-missing",
    4: "tls-record-rejected",
    5: "tcp-ack-send",
    6: "peer-finished-before-http",
    7: "incomplete",
}
WORKER_STATUS_LABELS = {
    "R": "transport-retry",
    "P": "response-parse-error",
    "O": "poll-ok",
    "A": "control-ack-ok",
    "a": "control-ack-retry",
    "o": "result-ok",
    "F": "result-retry",
}
INFERENCE_FAILURE_LABELS = {
    0: "none",
    1: "embedding",
    2: "attention-projection",
    3: "linear-alpha",
    4: "linear-conv",
    5: "linear-decay",
    6: "linear-recurrent",
    7: "linear-output",
    8: "full-key",
    9: "full-softmax",
    10: "full-output",
    11: "ffn",
    12: "state-nonfinite",
    13: "output-norm",
    14: "output-logits",
    15: "full-query",
    16: "full-cache",
    20: "reference-token",
    21: "output-selection",
}


def worker_diagnostic(message):
    """Decode the bounded K16 worker report without exposing response JSON."""
    parts = message.split()
    if len(parts) < 11 or parts[0] != "AIUEOS_WORKER_RX":
        return None
    status = parts[1]
    encoded_fields = parts[2:-1]
    if len(encoded_fields) not in (8, 10) or any(
            not re.fullmatch(r"[0-9a-fA-F]{8}", field)
            for field in encoded_fields):
        return None
    fields = [int(field, 16) for field in encoded_fields]
    sequence, error, tls_stage, pump_error, recoveries, app_bytes = fields[:6]
    vector_bits, worker_threads = fields[6:8]
    response_wait_ms = fields[8] if len(fields) == 10 else 0
    response_timeout_s = fields[9] if len(fields) == 10 else 0
    prefix = parts[-1]
    if prefix != "-" and not re.fullmatch(r"[0-9a-fA-F]{2,24}", prefix):
        return None
    first_record = (tls_stage >> 8) & 0xff
    tls_ready = bool(tls_stage & 0x10)
    tls_failed = bool(tls_stage & 0x20)
    error_label = WORKER_ERROR_LABELS.get(error)
    if error_label is None and 30 <= error <= 37:
        error_label = "handshake-" + WORKER_PUMP_LABELS.get(error - 30, "pump")
    if error_label is None:
        error_label = "unknown"
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return (
        f"AIUEOS_WORKER_DIAG timestamp={timestamp} "
        f"state={WORKER_STATUS_LABELS.get(status, 'unknown')} "
        f"sequence={sequence} error={error}:{error_label} "
        f"tls-ready={str(tls_ready).lower()} tls-failed={str(tls_failed).lower()} "
        f"tls-first-record=0x{first_record:02x} "
        f"pump={pump_error}:{WORKER_PUMP_LABELS.get(pump_error, 'unknown')} "
        f"tcp-recoveries={recoveries} app-bytes={app_bytes} "
        f"response-wait-ms={response_wait_ms} "
        f"response-timeout-s={response_timeout_s} "
        f"vector-bits={vector_bits} worker-threads={worker_threads} "
        f"http-prefix={prefix}")


def inference_diagnostic(message):
    """Decode public job coordinates from a failed native inference."""
    parts = message.split()
    if len(parts) != 6 or parts[0] != "AIUEOS_INFERENCE_RX" or not \
            re.fullmatch(r"[0-9a-fA-F]{16}", parts[1]) or any(
                not re.fullmatch(r"[0-9a-fA-F]{8}", field)
                for field in parts[2:]):
        return None
    job_id = int(parts[1], 16)
    attempt, token, layer, stage = [int(field, 16) for field in parts[2:]]
    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return (
        f"AIUEOS_INFERENCE_DIAG timestamp={timestamp} job-id={job_id} "
        f"attempt={attempt} failed-token={token} failed-layer={layer} "
        f"failure-stage={stage}:"
        f"{INFERENCE_FAILURE_LABELS.get(stage, 'unknown')}")


INTERFACE = os.environ.get("AIUEOS_PXE_INTERFACE", "en11")
SERVER_IP = os.environ.get("AIUEOS_PXE_SERVER_IP", "10.77.0.1")
CLIENT_IP = os.environ.get("AIUEOS_PXE_CLIENT_IP", "10.77.0.10")
NETMASK = os.environ.get("AIUEOS_PXE_NETMASK", "255.255.255.0")
BROADCAST_IP = os.environ.get("AIUEOS_PXE_BROADCAST", "10.77.0.255")
BOOT_PATH = Path(os.environ.get("AIUEOS_PXE_BOOT", "bootx64.efi")).resolve()
BOOT_FILE = BOOT_PATH.name
HTTP_PORT = int(os.environ.get("AIUEOS_PXE_HTTP_PORT", "8000"))
HTTP_BOOT_URI = f"http://{SERVER_IP}:{HTTP_PORT}/{BOOT_FILE}"
NETLOG_PORT = int(os.environ.get("AIUEOS_PXE_NETLOG_PORT", "7777"))
# LAN2/bus3 is where the murakumo relay actually rides: bus2 has no UDP
# receive path, so the board can only TRANSMIT there.  See ADR-0202.  The
# board uses 9000 for both source and destination, so this socket is the one
# that both hears the announcement and sends the job.
BUS3_ENABLED = os.environ.get("AIUEOS_PXE_BUS3_RELAY", "1") == "1"
BUS3_INTERFACE = os.environ.get("AIUEOS_PXE_BUS3_INTERFACE", "en8")
BUS3_SERVER_IP = os.environ.get("AIUEOS_PXE_BUS3_SERVER_IP", "10.10.10.1")
# WILDCARD, not 10.10.10.1.  The board announces itself to the limited
# broadcast 255.255.255.255 as well as to us -- deliberately, because an
# unsolicited unicast IP inside a broadcast Ethernet frame is a shape BSD's
# ip_input rejects -- and a socket bound to one unicast address never sees
# it.  IP_BOUND_IF still pins this socket to bus3's interface, so the
# wildcard does not make it listen on the PXE wire.  k16-bus3-sink.cljs
# learned the same thing and its header says so too.
BUS3_BIND_IP = os.environ.get("AIUEOS_PXE_BUS3_BIND_IP", "")
BUS3_CLIENT_IP = os.environ.get("AIUEOS_PXE_BUS3_CLIENT_IP", "10.10.10.2")
BUS3_PORT = int(os.environ.get("AIUEOS_PXE_BUS3_PORT", "9000"))
# Receipts in k16-bus3-sink.cljs's own format, so the record of this wire
# survives the sink being replaced by this thread.  Only ONE process can own
# the port; if the standalone sink holds it this thread refuses by name rather
# than racing it.
BUS3_SINK_PATH = Path(os.environ.get(
    "AIUEOS_PXE_BUS3_SINK", "/tmp/k16-bus3-en8.log"))
CONTROL_PORT = int(os.environ.get("AIUEOS_PXE_CONTROL_PORT", "7778"))
CONTROL_STATE_PATH = Path(os.environ.get(
    "AIUEOS_PXE_CONTROL_STATE", "/tmp/aiueos-k16-pxe-control-nonce"))
NEXT_BOOT_STATE_PATH = Path(os.environ.get(
    "AIUEOS_PXE_NEXT_BOOT_STATE", "/tmp/aiueos-k16-pxe-next-boot"))
CONTROL_COMMANDS = ("ping", "reboot-pxe")
MURAKUMO_API = os.environ.get(
    "AIUEOS_MURAKUMO_API", "https://api.murakumo.cloud").rstrip("/")
MURAKUMO_NODE_NAME = os.environ.get(
    "AIUEOS_MURAKUMO_NODE_NAME", "gmktec-k16")
# The path is kept, not just the value: the CACAO minter is a separate process
# and takes the DID by file so the two never disagree about which identity is
# signing.
MURAKUMO_NODE_DID_FILE = os.environ.get("AIUEOS_MURAKUMO_NODE_DID_FILE", "")
MURAKUMO_NODE_DID = os.environ.get("AIUEOS_MURAKUMO_NODE_DID", "") or \
    private_file_text(MURAKUMO_NODE_DID_FILE, "Murakumo node DID file", 256)
MURAKUMO_SERVICE_TOKEN = os.environ.get(
    "AIUEOS_MURAKUMO_SERVICE_TOKEN",
    os.environ.get("MURAKUMO_SERVICE_TOKEN", "")) or \
    private_file_text(os.environ.get("AIUEOS_MURAKUMO_SERVICE_TOKEN_FILE", ""),
                      "Murakumo service token file", 512)
# The board announces itself with the MAC of the NIC the announcement LEAVES
# BY, and that is bus3 (…b6:31), because the relay rides LAN2 -- bus2 has no
# UDP receive path. This was a single accepted value of bus2's MAC (…b6:32)
# until 2026-09-08, so the first hello the board ever sent was rejected as
# `unexpected-mac` while every log on both ends read healthy. One physical
# board, two ports; the guarantee this list is protecting is "one board under
# qualification", not "one cable". The first entry is the one this server
# SPEAKS AS when it synthesises a hello on resume.
# The node signs with its OWN did:key instead of presenting the shared operator
# secret. Measured 2026-09-08 against the live server: every route this relay
# uses accepts `Authorization: CACAO <base64>` whose :iss equals the :did the
# body claims. MURAKUMO_SERVICE_TOKEN is not in kagi, is write-only on the
# Worker, and is shared by two gates -- re-issuing it 401s every other caller.
# The bearer path stays for an operator who has that secret; without it the
# relay is no longer blocked.
MURAKUMO_NODE_KEY_FILE = os.environ.get("AIUEOS_MURAKUMO_NODE_KEY_FILE", "")
MURAKUMO_CACAO_MINT = os.environ.get(
    "AIUEOS_MURAKUMO_CACAO_MINT", "")
MURAKUMO_CACAO_CLASSPATH = os.environ.get(
    "AIUEOS_MURAKUMO_CACAO_CLASSPATH", "")
# `awai-secure` is admitted only by the operator boundary and describes AWAI's
# own hardware. This board is a machine on a desk relayed through a Mac, so the
# truthful tier is the one it can authorize for itself.
MURAKUMO_TRUST_TIER = os.environ.get(
    "AIUEOS_MURAKUMO_TRUST_TIER", "community")
# How many consecutive failures a boot's liveness thread tolerates before it
# stops. It must be finite: while it runs it heartbeats, and a heartbeat is
# what the server derives liveness from, so an unbounded thread keeps a dead
# board marked live. 12 at retry_interval 5 s is about a minute of trying,
# against a board whose whole run is one second.
MURAKUMO_LIVENESS_MAX_FAILURES = int(
    os.environ.get("AIUEOS_MURAKUMO_LIVENESS_MAX_FAILURES", "12"))
MURAKUMO_CACAO_TTL = int(os.environ.get("AIUEOS_MURAKUMO_CACAO_TTL", "600"))
# How long one mint may take, and how long a FAILED mint is remembered. The
# second number is the one that matters: without it a refused or timed-out mint
# is retried by the very next caller, which is how a stampede restarts itself.
MURAKUMO_CACAO_TIMEOUT = int(os.environ.get("AIUEOS_MURAKUMO_CACAO_TIMEOUT", "30"))
MURAKUMO_CACAO_RETRY_S = int(os.environ.get("AIUEOS_MURAKUMO_CACAO_RETRY_S", "5"))
# How hard the dispatcher tries, in the units the BOARD sets.
#
# RE-DERIVED 2026-09-08. The previous derivation opened "the board is reachable
# for 185 ms per 39.8-second boot (ADR-0203)" -- and ADR-0203 is the ADR that
# WITHDREW 39.8 s, as a number measured through a lossy instrument. This file
# went on citing it as the basis for both constants while saying, four lines
# later, that they are re-derived rather than kept when the board changes. It
# also contradicted itself: the comment above stream_resident in this same file
# says 19.7 s.
#
# What is actually measured, and how:
#   period   19.7-20.4 s   consecutive PXE fetches in the server's own log,
#                          which is the non-lossy witness (DHCP + TFTP), not
#                          the fire-and-forget netlog
#   uptime   ~1 s          span of one boot's netlog markers at 64 cycles
#                          (0.80, 0.87, 1.15 s across three boots)
#
# So reachability is roughly 1 s in 20, not 185 ms in 39.8 -- about 5% of the
# period rather than 0.5%. At 0.05 s between sends that is ~20 datagrams inside
# a window instead of ~4, and 90 s spans about four and a half periods, so a
# job that misses one window still meets several more.
#
# THE VALUES ARE UNCHANGED, deliberately: the re-derivation moved the margin in
# the direction of comfort, so there is nothing to fix. What was wrong was the
# reasoning, and a justification resting on a withdrawn number is worth exactly
# as much as no justification.
#
# ⚠ This whole model has a period in it because the board reboots. ADR-0205
# step 2 removes the reboot from the cadence -- the run hands the step back to
# the image's tender instead of resetting the platform -- and if that lands on
# hardware the board is reachable continuously and these two constants stop
# describing anything. Re-derive them again then; do not keep them.
MURAKUMO_JOB_RETRY_WAIT = float(
    os.environ.get("AIUEOS_MURAKUMO_JOB_RETRY_WAIT", "0.05"))
MURAKUMO_JOB_DEADLINE = float(
    os.environ.get("AIUEOS_MURAKUMO_JOB_DEADLINE", "90"))
MURAKUMO_CACAO_CACHE = {}
MURAKUMO_CACAO_LOCK = threading.Lock()
MURAKUMO_EXPECTED_MACS = tuple(
    m.strip().lower()
    for m in os.environ.get(
        "AIUEOS_MURAKUMO_EXPECTED_MAC",
        "70-70-fc-0b-b6-31,70-70-fc-0b-b6-32").split(",")
    if m.strip())
MURAKUMO_EXPECTED_MAC = MURAKUMO_EXPECTED_MACS[0]
# One K16, two NICs, and the firmware will netboot from either once both have
# link. Accepting only the first one is how the board got stuck on 2026-09-08:
# bus3 (…b6:31) asked, was ignored, and the machine never fell back to bus2.
# A comma-separated list keeps the "one physical board under qualification"
# guarantee while letting that board boot from whichever port it chooses.
PXE_EXPECTED_MACS = tuple(
    m.strip().lower().replace("-", ":")
    for m in os.environ.get(
        "AIUEOS_PXE_EXPECTED_MAC", "70:70:fc:0b:b6:32").split(",")
    if m.strip())
# The one this server SPEAKS AS when it synthesises a request (line ~1134);
# the acceptance test below uses the whole list.
PXE_EXPECTED_MAC = PXE_EXPECTED_MACS[0]
MURAKUMO_JOB_QUALIFICATION = os.environ.get(
    "AIUEOS_MURAKUMO_JOB_QUALIFICATION", "0") == "1"
MURAKUMO_RESUME_BOOT = ""
MURAKUMO_JOB_KIND = "aiueos-micro-infer"
MURAKUMO_JOB_MODEL = "aiueos-char-bigram-v1"
MURAKUMO_JOB_PROMPT = "murakum"
MURAKUMO_JOB_CORPUS_SHA256 = \
    "6433aeadc179877f103fdc87672d967d5c68d3f531f8b2bf156e377ad84058cb"
# Compact projection of the frozen C transition matrix: last input byte ->
# (winning next token, winning count, row total). Rows with no evidence are
# deliberately absent, so the relay never claims a job the K16 model rejects.
MURAKUMO_MICRO_INFER_ROWS = {
    " ": ("a", 3, 13), "a": ("i", 2, 8), "c": ("e", 1, 1),
    "e": (" ", 2, 9), "f": ("e", 1, 1), "g": (" ", 1, 1),
    "i": ("n", 3, 8), "j": ("o", 1, 1), "k": ("u", 2, 3),
    "m": ("o", 2, 5), "n": (" ", 1, 7), "o": (" ", 2, 7),
    "p": ("e", 1, 1), "r": ("a", 3, 5), "s": (" ", 5, 7),
    "t": ("i", 2, 4), "u": ("e", 2, 6), "v": ("e", 1, 1),
    "w": ("m", 1, 1), "y": ("o", 1, 1),
}
IP_BOUND_IF = 25
MAGIC = b"\x63\x82\x53\x63"
CONTROL_READY = re.compile(r"^AIUEOS_CONTROL_READY nonce=([0-9a-f]{16})\b")
NODE_HELLO = re.compile(
    r"^AIUEOS_NODE_HELLO_V1 boot=([0-9a-f]{16}) "
    r"mac=([0-9a-f]{2}(?:-[0-9a-f]{2}){5}) "
    r"profile=rtl8125-relay-test$")
JOB_RESULT = re.compile(
    r"^AIUEOS_JOB_RESULT_V1 boot=([0-9a-f]{16}) id=([0-9]{1,20}) "
    r"model=aiueos-char-bigram-v1 token=([0-9a-f]{2}) "
    r"score=([0-9]{1,5}) total=([0-9]{1,5}) "
    r"cycles=([0-9]{1,20})$")
NODE_PONG = re.compile(
    r"^AIUEOS_NODE_PONG_V1 boot=([0-9a-f]{16}) "
    r"seq=([0-9]{1,10}) state=ready$")
NEXT_BOOT_LOCK = threading.Lock()
MURAKUMO_BOOT_LOCK = threading.Lock()
class BoundedSeen:
    """The boots this relay has already enrolled, with a ceiling.

    It was a plain `set()`, which is correct and unbounded -- one entry per
    boot, discarded only when enrollment or the heartbeat fails. That is fine
    for a board that boots when a person presses a button, and it is a leak the
    moment the board recovers itself: the chipset watchdog landed 2026-09-08
    resets a stopped run in about ten seconds, and a board on a ~21 s cycle
    enrolls roughly four thousand times a day, forever, in a daemon that is
    meant never to be restarted.

    This is the shape of defect that only appears once the system starts
    WORKING, which is when nobody is looking at it any more. Bounded now,
    while the boot rate is still zero.

    512 is two of ANNOUNCED_BOOTS' 256 -- deliberately larger, because a boot
    that is evicted from here would be enrolled a second time, and this set is
    what makes enrollment idempotent."""

    def __init__(self, capacity=512):
        self.capacity = capacity
        self._seen = collections.OrderedDict()

    def __contains__(self, boot):
        return boot in self._seen

    def add(self, boot):
        self._seen[boot] = None
        self._seen.move_to_end(boot)
        while len(self._seen) > self.capacity:
            self._seen.popitem(last=False)

    def discard(self, boot):
        self._seen.pop(boot, None)

    def clear(self):
        self._seen.clear()

    def __len__(self):
        return len(self._seen)


MURAKUMO_SEEN_BOOTS = BoundedSeen()
# Every boot nonce this node has announced on the wire, most recent last.
#
# WHY. Measured 2026-09-08: the board is UP FOR 12 MILLISECONDS out of every
# 19.7 seconds -- four cycles, then the fuel-bounded run ends and the board
# resets through PXE. Duty cycle 0.1%. A job dispatched when a hello arrives
# reaches a machine that has ~12 ms left to live, and the answer therefore
# comes back under a LATER boot nonce, which `verified_job_result` correctly
# refused: three k16-result-timeouts while the other wire (bus2 netlog) showed
# D9 70 -- the board HAD answered.
#
# The fix is not to drop the boot binding. It is to bind to the right thing:
# the answering boot must be one this node ANNOUNCED, which is what makes the
# answer attributable to the physical board rather than to anything that can
# spell the format. The board writes its OWN nonce into the result (it ignores
# the `boot=` in the request), so the nonce in an answer is evidence about who
# computed it either way.
MURAKUMO_ANNOUNCED_BOOTS = collections.deque(maxlen=256)
MURAKUMO_JOB_RESULTS = queue.Queue()
MURAKUMO_LIVENESS_RESULTS = queue.Queue()


def ipv4(value):
    return socket.inet_aton(value)


def parse_options(packet):
    result = {}
    if len(packet) < 240 or packet[236:240] != MAGIC:
        return result
    position = 240
    while position < len(packet):
        code = packet[position]
        position += 1
        if code == 0:
            continue
        if code == 255:
            break
        if position >= len(packet):
            break
        length = packet[position]
        position += 1
        if position + length > len(packet):
            break
        result[code] = packet[position:position + length]
        position += length
    return result


def option(code, payload):
    if len(payload) > 255:
        raise ValueError("DHCP option is too long")
    return bytes((code, len(payload))) + payload


def dhcp_reply(request, message_type):
    if len(request) < 240:
        raise ValueError("short DHCP request")
    reply = bytearray(236)
    reply[:236] = request[:236]
    reply[0] = 2                         # BOOTREPLY
    reply[3] = 0                         # hops
    reply[12:16] = b"\0" * 4            # ciaddr
    reply[16:20] = ipv4(CLIENT_IP)       # yiaddr
    reply[20:24] = ipv4(SERVER_IP)       # siaddr
    reply[44:108] = b"\0" * 64
    server_name = b"AIUEOS PXE"
    reply[44:44 + len(server_name)] = server_name
    reply[108:236] = b"\0" * 128
    request_options = parse_options(request)
    vendor = request_options.get(60, b"")
    http_boot = vendor.startswith(b"HTTPClient")
    filename = (HTTP_BOOT_URI if http_boot else BOOT_FILE).encode("ascii")
    reply[108:108 + len(filename)] = filename
    values = [
        option(53, bytes((message_type,))),
        option(54, ipv4(SERVER_IP)),
        option(51, struct.pack("!I", 3600)),
        option(1, ipv4(NETMASK)),
        option(3, ipv4(SERVER_IP)),
        option(28, ipv4(BROADCAST_IP)),
        option(66, SERVER_IP.encode("ascii")),
        option(67, filename),
    ]
    architecture = request_options.get(93)
    if architecture:
        values.append(option(93, architecture))
    if http_boot:
        values.append(option(60, b"HTTPClient"))
    values.append(b"\xff")
    packet = bytes(reply) + MAGIC + b"".join(values)
    return packet + b"\0" * max(0, 300 - len(packet))


def mac_address(packet):
    return ":".join(f"{byte:02x}" for byte in packet[28:34])


def expected_dhcp_client(packet):
    """Accept DHCP only from the one physical K16 under qualification."""
    return len(packet) >= 34 and mac_address(packet) in PXE_EXPECTED_MACS


EXIT_PLANE_DOWN = 70          # EX_SOFTWARE: one listener escaped; whole process restarts
INTERFACE_POLL_SECONDS = 10.0


def interface_index(name):
    """if_nametoindex, with "no such wire" as None instead of ENXIO."""
    try:
        return socket.if_nametoindex(name)
    except OSError:
        return None


def wait_for_interfaces(names, index=interface_index, sleep=time.sleep,
                        poll_seconds=INTERFACE_POLL_SECONDS):
    """Block until every named interface exists; say once what is missing.

    Before 2026-09-11 an unplugged adapter (`en15` -> ENXIO "Device not
    configured") reached bind_interface() in four threads at once.  Three
    daemon threads were still printing tracebacks to stderr while the main
    thread finalised, and CPython aborted in flush_std_files() -- a crash
    report every 30 s for 86 launchd respawns, none of which named the
    missing wire.  Waiting is the launchd-shaped answer: the job stays
    loaded, prints one line per absent interface, and serves when the
    wire is back.  Returns the number of polls it waited.
    """
    announced = []
    polls = 0
    while True:
        missing = [name for name in names if index(name) is None]
        if not missing:
            for name in announced:
                print(f"AIUEOS_PXE_INTERFACE_PRESENT interface={name} "
                      f"waited_polls={polls}", flush=True)
            return polls
        for name in missing:
            if name not in announced:
                print(f"AIUEOS_PXE_INTERFACE_ABSENT interface={name} "
                      f"poll_seconds={poll_seconds:g} hint=plug-the-adapter",
                      flush=True)
                announced.append(name)
        polls += 1
        sleep(poll_seconds)


def serve_plane(name, target, exit=os._exit):
    """Run one listener; if it escapes, the whole process goes down.

    A PXE server whose TFTP plane died is deaf while every other log reads
    healthy, so a plane that raises names itself and exits with
    EXIT_PLANE_DOWN; launchd KeepAlive brings a whole one back.  os._exit
    is deliberate: interpreter finalisation is where the 2026-09-11 abort
    happened (daemon threads writing stderr while the main thread flushed
    it), and a thread that has already printed its traceback has nothing
    left to flush.
    """
    try:
        return target()
    except Exception:
        traceback.print_exc()
        print(f"AIUEOS_PXE_PLANE_DOWN plane={name} exit={EXIT_PLANE_DOWN}",
              flush=True)
        sys.stdout.flush()
        sys.stderr.flush()
        exit(EXIT_PLANE_DOWN)


def bind_interface(sock, port, address="", interface=None):
    # `interface` was a module global until 2026-09-08, when a second wire
    # arrived: the PXE/netlog plane is bus2 (en15) and the murakumo relay is
    # bus3 (en8).  Binding the relay socket to en15 would have made it deaf on
    # the only wire the board answers on, while every log read healthy.
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.IPPROTO_IP, IP_BOUND_IF,
                    socket.if_nametoindex(interface or INTERFACE))
    sock.bind((address, port))


def extract_control_nonce(message):
    match = CONTROL_READY.match(message)
    return match.group(1) if match else None


def control_payload(command, nonce):
    if command not in CONTROL_COMMANDS:
        raise ValueError(f"unsupported control command: {command}")
    if not re.fullmatch(r"[0-9a-f]{16}", nonce or ""):
        raise ValueError("control nonce must be 16 lowercase hex digits")
    return f"AIUEOS_CTL_V1 nonce={nonce} command={command}".encode("ascii")


def node_ack_payload(message):
    """Return a request-bound diagnostic ACK, never a fleet enrollment claim."""
    match = NODE_HELLO.fullmatch(message)
    if not match:
        return None
    boot, _mac = match.groups()
    return f"AIUEOS_NODE_ACK_V1 boot={boot} state=accepted".encode("ascii")


def murakumo_cacao(aud):
    """One CACAO for one audience, minted by the workspace's own minter.

    Shelling out rather than re-implementing: a CACAO's signature covers a SIWE
    plaintext that mint and verify must agree on byte-for-byte, and that
    agreement already exists in `cacao.edge.mint` / `cacao.edge.verify`.
    A second implementation here would be a second chance to be silently wrong,
    which is the whole subject of ADR-2607320000.

    Cached per audience until a minute before expiry. Returns "" on any
    failure -- and the failure text is printed, because a blank credential and
    a mint that refused must not look the same from the call site.

    SINGLE-FLIGHT, and failures are cached too. Until 2026-09-08 the lock was
    released before the subprocess, so every caller that missed the cache
    spawned its own `nbb`. That is a cache stampede with a positive feedback
    loop: the liveness maintainer retries once per stale boot nonce, six of
    them were live at once, none could populate the cache because none could
    finish, and every failure guaranteed the next round would also have an
    empty cache. Measured that day -- 177 mint timeouts before a restart and 46
    after, while the SAME command run once by hand took 0.24 s at load 145.
    A 30 s timeout was never the problem; six of them at once was.

    So the mint happens under the lock. Concurrent callers wait for the one
    result instead of racing to produce six, which is also why holding a lock
    across a subprocess is right here rather than merely tolerable: every
    waiter wanted exactly this value.

    A failure is cached for MURAKUMO_CACAO_RETRY_S. Without that, a refused or
    timed-out mint re-enters the loop on the very next call and the stampede
    restarts by itself.
    """
    if not (MURAKUMO_CACAO_MINT and MURAKUMO_NODE_KEY_FILE and
            MURAKUMO_NODE_DID_FILE):
        return ""
    with MURAKUMO_CACAO_LOCK:
        return _murakumo_cacao_locked(aud)


def _murakumo_cacao_locked(aud):
    """Mint one CACAO. The caller holds MURAKUMO_CACAO_LOCK."""
    now = time.monotonic()
    cached = MURAKUMO_CACAO_CACHE.get(aud)
    if cached and cached[1] > now:
        return cached[0]
    command = ["nbb"]
    if MURAKUMO_CACAO_CLASSPATH:
        command += ["--classpath", MURAKUMO_CACAO_CLASSPATH]
    command += [MURAKUMO_CACAO_MINT,
                "--key", MURAKUMO_NODE_KEY_FILE,
                "--did", MURAKUMO_NODE_DID_FILE,
                "--aud", aud,
                "--ttl-s", str(MURAKUMO_CACAO_TTL)]
    try:
        done = subprocess.run(command, capture_output=True,
                              timeout=MURAKUMO_CACAO_TIMEOUT)
    except Exception as exc:                    # noqa: BLE001
        print(f"AIUEOS_MURAKUMO_CACAO_FAIL aud={aud} "
              f"exc={type(exc).__name__}: {exc}", flush=True)
        MURAKUMO_CACAO_CACHE[aud] = ("", now + MURAKUMO_CACAO_RETRY_S)
        return ""
    blob = done.stdout.decode("ascii", "replace").strip()
    if done.returncode != 0 or not blob:
        print(f"AIUEOS_MURAKUMO_CACAO_REFUSED aud={aud} rc={done.returncode} "
              f"err={done.stderr.decode('ascii', 'replace').strip()[:200]}",
              flush=True)
        MURAKUMO_CACAO_CACHE[aud] = ("", now + MURAKUMO_CACAO_RETRY_S)
        return ""
    MURAKUMO_CACAO_CACHE[aud] = (blob, now + max(30, MURAKUMO_CACAO_TTL - 60))
    return blob


def murakumo_authorization(path):
    """The Authorization header value for one route, or "".

    The operator bearer wins when it is configured, so an operator-run relay
    keeps behaving exactly as before; otherwise the node signs for itself.
    """
    if MURAKUMO_SERVICE_TOKEN:
        return f"Bearer {MURAKUMO_SERVICE_TOKEN}"
    # The audience is the API ORIGIN, not the exact route. Per-route audiences
    # were tried first and cost the node its jobs: /infer/queue/<id>/claim and
    # .../result carry a fresh job id, so every dispatch minted two new CACAOs,
    # each a subprocess, and the four mints around one hello pushed the
    # dispatch past the end of the board's ~20-second run. The result then
    # arrived under a DIFFERENT boot nonce and was correctly rejected -- three
    # k16-result-timeouts with a D9 70 on the other wire saying the board HAD
    # answered (measured 2026-09-08). The server does not scope by audience, so
    # narrowing it bought nothing and cost the thing the node exists to do.
    blob = murakumo_cacao(MURAKUMO_API)
    return f"CACAO {blob}" if blob else ""


def murakumo_relay_configured():
    # Either credential suffices. The DID is required for both: it is the
    # account the work is credited to, and with CACAO it is also what the
    # signature is checked against.
    if not MURAKUMO_NODE_DID.startswith("did:key:"):
        return False
    if MURAKUMO_SERVICE_TOKEN:
        return True
    return bool(MURAKUMO_NODE_KEY_FILE and MURAKUMO_CACAO_MINT and
                MURAKUMO_NODE_DID_FILE)


def murakumo_enrollment():
    return {
        # `did` (not just `node/did`) because that is the key the server reads
        # as the CLAIMED ACTOR and compares against the CACAO's :iss. Without
        # it a perfectly valid signature authorizes nothing, and the 401 says
        # "requires a matching CACAO" -- which reads as a signing problem.
        "did": MURAKUMO_NODE_DID,
        "node/name": MURAKUMO_NODE_NAME,
        "node/did": MURAKUMO_NODE_DID,
        "node/tier": "native",
        "node/connect": "mac-relay",
        "node/needs-relay?": True,
        "node/trust-tier": MURAKUMO_TRUST_TIER,
        "node/caps": {
            "engine": "aiueos-native",
            "qualification-model": MURAKUMO_JOB_MODEL,
            "physical-network": "rtl8125-unisolated-qualification",
        },
        "node/can": [MURAKUMO_JOB_KIND],
    }


def murakumo_heartbeat(ready=False):
    # A relay round trip is liveness, not inference readiness. Capacity and a
    # model are withheld until a real K16 job has completed and returned.
    heartbeat = {
        "did": MURAKUMO_NODE_DID,
        "node/name": MURAKUMO_NODE_NAME,
        "node/ready?": ready,
        "node/engine": "aiueos-native-relay",
    }
    if ready:
        heartbeat["node/model"] = MURAKUMO_JOB_MODEL
        heartbeat["node/capacity"] = {
            "slots-total": 1,
            "slots-free": 1,
        }
    return heartbeat


def murakumo_post(path, body, opener=urllib.request.urlopen):
    request = urllib.request.Request(
        MURAKUMO_API + path,
        data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
        method="POST",
        headers={
            "authorization": murakumo_authorization(path),
            "content-type": "application/json",
            "user-agent": "aiueos-k16-relay/1",
        })
    try:
        with opener(request, timeout=8) as response:
            payload = response.read(4096)
            return response.status, json.loads(payload or b"{}")
    except urllib.error.HTTPError as error:
        payload = error.read(4096)
        try:
            parsed = json.loads(payload or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            parsed = {"error": "non-json response"}
        return error.code, parsed


def murakumo_get(path, opener=urllib.request.urlopen):
    request = urllib.request.Request(
        MURAKUMO_API + path,
        method="GET",
        headers={
            "authorization": murakumo_authorization(path),
            "accept": "application/json",
            "user-agent": "aiueos-k16-relay/1",
        })
    try:
        with opener(request, timeout=8) as response:
            payload = response.read(65536)
            return response.status, json.loads(payload or b"[]")
    except urllib.error.HTTPError as error:
        payload = error.read(4096)
        try:
            parsed = json.loads(payload or b"{}")
        except (json.JSONDecodeError, UnicodeDecodeError):
            parsed = {"error": "non-json response"}
        return error.code, parsed


def murakumo_queue_path():
    return "/infer/queue?did=" + urllib.parse.quote(
        MURAKUMO_NODE_DID, safe="")


def job_payload(boot, job):
    job_id = str(job.get("job-id", ""))
    kind = job.get("kind")
    input_value = job.get("input")
    prompt = input_value.get("prompt") if isinstance(input_value, dict) else None
    model = input_value.get("model") if isinstance(input_value, dict) else None
    if not re.fullmatch(r"[0-9]{1,20}", job_id) or kind != MURAKUMO_JOB_KIND:
        return None
    if model != MURAKUMO_JOB_MODEL or micro_infer_expected(prompt) is None:
        return None
    return (f"AIUEOS_JOB_V1 boot={boot} id={job_id} kind={kind} "
            f"prompt={prompt.encode('ascii').hex()}").encode("ascii")


def committed_payload(boot, job_id):
    if not re.fullmatch(r"[0-9a-f]{16}", boot or "") or \
            not re.fullmatch(r"[0-9]{1,20}", str(job_id)):
        return None
    return (f"AIUEOS_JOB_COMMIT_V1 boot={boot} id={job_id} "
            "state=recorded").encode("ascii")


def node_ping_payload(boot, sequence):
    if not re.fullmatch(r"[0-9a-f]{16}", boot or "") or \
            not isinstance(sequence, int) or not (0 <= sequence <= 0xffffffff):
        return None
    return f"AIUEOS_NODE_PING_V1 boot={boot} seq={sequence}".encode("ascii")


def verified_node_pong(message, boot, sequence):
    match = NODE_PONG.fullmatch(message)
    return bool(match and match.group(1) == boot and
                int(match.group(2)) == sequence)


def micro_infer_expected(prompt):
    if not isinstance(prompt, str) or not (1 <= len(prompt) <= 64) or \
            not re.fullmatch(r"[ a-z]+", prompt):
        return None
    return MURAKUMO_MICRO_INFER_ROWS.get(prompt[-1])


def announced_boot(boot):
    """Did this node announce `boot` on the wire? A bounded membership test,
    not a string comparison against one remembered nonce -- see the comment on
    MURAKUMO_ANNOUNCED_BOOTS for the 12-millisecond reason."""
    with MURAKUMO_BOOT_LOCK:
        return boot in MURAKUMO_ANNOUNCED_BOOTS


def verified_job_result(message, boot, job_id, prompt):
    match = JOB_RESULT.fullmatch(message)
    if not match:
        return None
    got_boot, got_id, token_hex, score, total, cycles = match.groups()
    # The dispatching boot is accepted, and so is any other boot this node has
    # announced: the board that answers is usually a LATER boot than the one
    # whose hello started the dispatch, because a run lasts 12 ms.
    if not (got_boot == boot or announced_boot(got_boot)):
        return None
    if got_id != str(job_id):
        return None
    token = bytes.fromhex(token_hex).decode("ascii", "strict")
    expected = micro_infer_expected(prompt)
    if expected is None or (token, int(score), int(total)) != expected:
        return None
    return {"text": token, "model": MURAKUMO_JOB_MODEL,
            "score": int(score), "total": int(total),
            "inference-cycles": int(cycles),
            "prompt": prompt,
            "corpus-sha256": MURAKUMO_JOB_CORPUS_SHA256,
            "boot": boot}


def dispatch_murakumo_job(
        boot, job, sock, peer, opener=urllib.request.urlopen,
        result_queue=MURAKUMO_JOB_RESULTS, sleeper=time.sleep,
        monotonic=time.monotonic, monotonic_ns=time.monotonic_ns,
        retry_wait=MURAKUMO_JOB_RETRY_WAIT, deadline_s=MURAKUMO_JOB_DEADLINE):
    job_id = str(job.get("job-id", "")) if isinstance(job, dict) else ""
    payload = job_payload(boot, job or {})
    if not payload:
        return {"state": "failed", "stage": "job-admission",
                "job-id": job_id}
    prompt = job["input"]["prompt"]
    claim_status, _ = murakumo_post(
        f"/infer/queue/{job_id}/claim", {"did": MURAKUMO_NODE_DID}, opener)
    if claim_status != 201:
        return {"state": "raced" if claim_status == 409 else "failed",
                "stage": "claim", "status": claim_status,
                "job-id": job_id}
    started_ns = monotonic_ns()
    deadline = monotonic() + deadline_s
    output = None
    # Resend for the WHOLE window rather than five times in the first second.
    # The board is reachable for about 12 ms per 19.7-second boot, so a burst
    # that finishes before the first reboot is a burst aimed at a machine that
    # is already gone. One datagram every `retry_wait` for 30 seconds crosses
    # at least one live window; five in the first second usually crosses none.
    while output is None and monotonic() < deadline:
        sock.sendto(payload, peer)
        attempt_deadline = min(deadline, monotonic() + retry_wait)
        while output is None:
            remaining = attempt_deadline - monotonic()
            if remaining <= 0:
                break
            try:
                candidate, candidate_peer = result_queue.get(timeout=remaining)
            except queue.Empty:
                break
            if candidate_peer == peer:
                output = verified_job_result(candidate, boot, job_id, prompt)
    if output is None:
        return {"state": "failed", "stage": "k16-result-timeout",
                "job-id": job_id}
    round_trip_ns = max(1, monotonic_ns() - started_ns)
    output["relay-round-trip-ns"] = round_trip_ns
    round_trip_ms = max(1, (round_trip_ns + 999999) // 1000000)
    result_status, _ = murakumo_post(
        f"/infer/queue/{job_id}/result",
        {"did": MURAKUMO_NODE_DID, "output": output,
         "ms": round_trip_ms}, opener)
    if result_status != 201:
        return {"state": "failed", "stage": "result", "status": result_status,
                "job-id": job_id}
    ready_status, _ = murakumo_post(
        f"/infer/nodes/{MURAKUMO_NODE_NAME}/heartbeat",
        murakumo_heartbeat(True), opener)
    if ready_status != 201:
        return {"state": "failed", "stage": "ready-heartbeat",
                "status": ready_status, "job-id": job_id}
    commit = committed_payload(boot, job_id)
    for _ in range(5):
        sock.sendto(commit, peer)
        sleeper(0.2)
    return {"state": "ready", "boot": boot, "job-id": job_id,
            "model": MURAKUMO_JOB_MODEL, "token": output["text"],
            "prompt": prompt, "inference-cycles": output["inference-cycles"],
            "relay-round-trip-ns": round_trip_ns,
            "relay-round-trip-ms": round_trip_ms}


def qualify_murakumo_job(message, sock, peer, opener=urllib.request.urlopen,
                         result_queue=MURAKUMO_JOB_RESULTS, sleeper=time.sleep):
    match = NODE_HELLO.fullmatch(message)
    if not match or not MURAKUMO_JOB_QUALIFICATION:
        return {"state": "disabled", "reason": "job-qualification-off"}
    boot, mac = match.groups()
    if mac not in MURAKUMO_EXPECTED_MACS or not murakumo_relay_configured():
        return {"state": "disabled", "reason": "identity-token-or-mac"}
    last_race = None
    for _attempt in range(8):
        enqueue_status, enqueue = murakumo_post(
            "/infer/queue",
            {"did": MURAKUMO_NODE_DID,
             "kind": MURAKUMO_JOB_KIND,
             "input": {"model": MURAKUMO_JOB_MODEL,
                       "prompt": MURAKUMO_JOB_PROMPT},
             "price": 0,
             "target-did": MURAKUMO_NODE_DID}, opener)
        job_id = str(enqueue.get("job-id", "")) \
            if isinstance(enqueue, dict) else ""
        if enqueue_status != 201 or not re.fullmatch(r"[0-9]{1,20}", job_id):
            return {"state": "failed", "stage": "enqueue",
                    "status": enqueue_status}
        list_status, jobs = murakumo_get(murakumo_queue_path(), opener)
        job = next((candidate for candidate in jobs
                    if str(candidate.get("job-id", "")) == job_id), None) \
            if list_status == 200 and isinstance(jobs, list) else None
        if not job_payload(boot, job or {}):
            return {"state": "failed", "stage": "queue-observe",
                    "status": list_status, "job-id": job_id}
        result = dispatch_murakumo_job(
            boot, job, sock, peer, opener, result_queue, sleeper)
        if result.get("state") != "raced":
            return result
        last_race = result
    return last_race or {"state": "failed", "stage": "claim-retry"}


def resume_murakumo_job(boot, sock, peer):
    hello = (f"AIUEOS_NODE_HELLO_V1 boot={boot} "
             f"mac={MURAKUMO_EXPECTED_MAC} profile=rtl8125-relay-test")
    result = qualify_murakumo_job(hello, sock, peer)
    fields = " ".join(f"{key}={value}" for key, value in result.items())
    print(f"AIUEOS_MURAKUMO_RESUME {fields}", flush=True)
    if result.get("state") == "ready":
        threading.Thread(
            target=maintain_murakumo_liveness,
            args=(boot, sock, peer), daemon=True).start()


def maintain_murakumo_liveness(
        boot, sock, peer, opener=urllib.request.urlopen,
        result_queue=MURAKUMO_LIVENESS_RESULTS, sleeper=time.sleep,
        rounds=None, interval=30, timeout=10,
        job_result_queue=MURAKUMO_JOB_RESULTS,
        max_failures=MURAKUMO_LIVENESS_MAX_FAILURES, retry_interval=5):
    """Keep one boot's job lease alive, and STOP when that boot is gone.

    `max_failures` used to default to None, which meant this loop never
    terminated. Measured 2026-09-08: the board was hung for 91 minutes, links
    up, answering nothing -- and the cluster showed the node
    `live? true, heartbeat-age 15s`, because these threads were still running
    for six long-dead boot nonces and still posting heartbeats. The log carried
    `failures=100`, `failures=271` and climbing.

    Two separate things were wrong and only one of them is obvious.

    The obvious one: a thread per dead boot, forever, which is also what fed
    the CACAO mint stampede -- six concurrent authorizations, none able to
    finish, cache never populating.

    The subtle one: `retry_or_return(mark_stale=True)` posts
    `murakumo_heartbeat(False)` to say "not ready", and that post REFRESHES
    heartbeat-at. Liveness on the server is derived from heartbeat recency, so
    a heartbeat saying "not ready" still asserts "here". "I am not ready" and
    "I am not here" are different claims and only silence makes the second.
    So the fix is not a better heartbeat body -- it is stopping.

    A bounded loop gives both: the thread exits, nothing heartbeats, and the
    node goes stale on its own, which is the true statement."""
    sequence = 1
    renewed = 0
    executed = 0
    consecutive_failures = 0

    def retry_or_return(result, mark_stale=False):
        nonlocal consecutive_failures
        consecutive_failures += 1
        if mark_stale:
            try:
                murakumo_post(
                    f"/infer/nodes/{MURAKUMO_NODE_NAME}/heartbeat",
                    murakumo_heartbeat(False), opener)
            except Exception:
                pass
        print(f"AIUEOS_MURAKUMO_LIVENESS state=reconnecting boot={boot} "
              f"stage={result.get('stage')} failures={consecutive_failures} "
              f"renewed={renewed} executed={executed}", flush=True)
        if max_failures is not None and \
                consecutive_failures >= max_failures:
            print(f"AIUEOS_MURAKUMO_LIVENESS state=gave-up boot={boot} "
                  f"stage={result.get('stage')} failures={consecutive_failures} "
                  f"-- no further heartbeats for this boot, so the node goes "
                  f"stale rather than claiming to be here", flush=True)
            return dict(result, failures=consecutive_failures)
        sleeper(retry_interval)
        return None

    while rounds is None or renewed < rounds:
        queue_status, jobs = (200, []) if renewed == 0 else \
            murakumo_get(murakumo_queue_path(), opener)
        if queue_status != 200 or not isinstance(jobs, list):
            terminal = retry_or_return(
                {"state": "failed", "stage": "queue-poll",
                 "status": queue_status, "boot": boot,
                 "renewed": renewed, "executed": executed})
            if terminal:
                return terminal
            continue
        job = next((candidate for candidate in jobs
                    if job_payload(boot, candidate)), None)
        if job is not None:
            work = dispatch_murakumo_job(
                boot, job, sock, peer, opener, job_result_queue, sleeper)
            if work.get("state") == "ready":
                renewed += 1
                executed += 1
                print(f"AIUEOS_MURAKUMO_WORK state=recorded boot={boot} "
                      f"job-id={work['job-id']} count={executed}", flush=True)
                if rounds is None or renewed < rounds:
                    sleeper(interval)
                continue
            if work.get("state") != "raced":
                terminal = retry_or_return(
                    {"state": "failed", "stage": "queued-work",
                     "work-stage": work.get("stage"), "boot": boot,
                     "renewed": renewed, "executed": executed}, True)
                if terminal:
                    return terminal
                continue
        ping = node_ping_payload(boot, sequence)
        if not ping:
            terminal = retry_or_return(
                {"state": "failed", "stage": "liveness-ping",
                 "renewed": renewed, "executed": executed})
            if terminal:
                return terminal
            continue
        try:
            sock.sendto(ping, peer)
        except OSError as error:
            terminal = retry_or_return(
                {"state": "failed", "stage": "liveness-send",
                 "error": error.errno, "boot": boot,
                 "sequence": sequence, "renewed": renewed,
                 "executed": executed}, True)
            if terminal:
                return terminal
            continue
        deadline = time.monotonic() + timeout
        valid = False
        while not valid:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                candidate, candidate_peer = result_queue.get(timeout=remaining)
            except queue.Empty:
                break
            valid = candidate_peer == peer and \
                verified_node_pong(candidate, boot, sequence)
        if not valid:
            terminal = retry_or_return(
                {"state": "stale", "stage": "liveness-timeout",
                 "boot": boot, "sequence": sequence, "renewed": renewed,
                 "executed": executed}, True)
            if terminal:
                return terminal
            continue
        status, _ = murakumo_post(
            f"/infer/nodes/{MURAKUMO_NODE_NAME}/heartbeat",
            murakumo_heartbeat(True), opener)
        if status != 201:
            terminal = retry_or_return(
                {"state": "failed", "stage": "heartbeat-renew",
                 "status": status, "boot": boot, "sequence": sequence,
                 "renewed": renewed, "executed": executed})
            if terminal:
                return terminal
            continue
        if consecutive_failures:
            print(f"AIUEOS_MURAKUMO_LIVENESS state=recovered boot={boot} "
                  f"sequence={sequence} failures={consecutive_failures}",
                  flush=True)
            consecutive_failures = 0
        renewed += 1
        print(f"AIUEOS_MURAKUMO_LIVENESS state=renewed boot={boot} "
              f"sequence={sequence} count={renewed}", flush=True)
        sequence = (sequence + 1) & 0xffffffff
        if rounds is None or renewed < rounds:
            sleeper(interval)
    return {"state": "live", "boot": boot, "renewed": renewed,
            "executed": executed}


def register_murakumo_hello(message, opener=urllib.request.urlopen):
    match = NODE_HELLO.fullmatch(message)
    if not match:
        return {"state": "ignored", "reason": "invalid-hello"}
    boot, mac = match.groups()
    if mac not in MURAKUMO_EXPECTED_MACS:
        return {"state": "ignored", "reason": "unexpected-mac"}
    with MURAKUMO_BOOT_LOCK:
        if boot not in MURAKUMO_ANNOUNCED_BOOTS:
            MURAKUMO_ANNOUNCED_BOOTS.append(boot)
    if not murakumo_relay_configured():
        return {"state": "disabled", "reason": "identity-or-token-unset"}
    with MURAKUMO_BOOT_LOCK:
        if boot in MURAKUMO_SEEN_BOOTS:
            return {"state": "duplicate", "boot": boot}
        MURAKUMO_SEEN_BOOTS.add(boot)
    enrollment_status, _ = murakumo_post(
        "/infer/nodes", murakumo_enrollment(), opener)
    if enrollment_status not in (200, 201):
        with MURAKUMO_BOOT_LOCK:
            MURAKUMO_SEEN_BOOTS.discard(boot)
        return {"state": "failed", "stage": "enroll",
                "status": enrollment_status, "boot": boot}
    heartbeat_status, _ = murakumo_post(
        f"/infer/nodes/{MURAKUMO_NODE_NAME}/heartbeat",
        murakumo_heartbeat(), opener)
    if heartbeat_status != 201:
        with MURAKUMO_BOOT_LOCK:
            MURAKUMO_SEEN_BOOTS.discard(boot)
        return {"state": "failed", "stage": "heartbeat",
                "status": heartbeat_status, "boot": boot}
    return {"state": "live-not-ready", "boot": boot,
            "enrollment-status": enrollment_status,
            "heartbeat-status": heartbeat_status}


def relay_murakumo_hello(message, sock=None, peer=None):
    try:
        result = register_murakumo_hello(message)
        fields = " ".join(f"{key}={value}" for key, value in result.items())
        print(f"AIUEOS_MURAKUMO_RELAY {fields}", flush=True)
        if result.get("state") == "live-not-ready" and sock and peer and \
                MURAKUMO_JOB_QUALIFICATION:
            job_result = qualify_murakumo_job(message, sock, peer)
            job_fields = " ".join(
                f"{key}={value}" for key, value in job_result.items())
            print(f"AIUEOS_MURAKUMO_JOB {job_fields}", flush=True)
            if job_result.get("state") == "ready":
                threading.Thread(
                    target=maintain_murakumo_liveness,
                    args=(job_result["boot"], sock, peer), daemon=True).start()
    except Exception as error:
        # The text, not just the class. Every other handler in this file
        # prints `: {exc}`; this one did not, and it is the handler that fires
        # when the board goes away mid-qualification -- so the one place the
        # reason mattered most was the one place it was discarded. Measured
        # 2026-09-08: `error=OSError` and nothing else, for a send to a board
        # that had stopped.
        print(f"AIUEOS_MURAKUMO_RELAY state=failed stage=client "
              f"error={type(error).__name__}: {error}", flush=True)


def send_control(command, nonce):
    payload = control_payload(command, nonce)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.IPPROTO_IP, IP_BOUND_IF,
                    socket.if_nametoindex(INTERFACE))
    sock.bind((SERVER_IP, 0))
    for _ in range(5):
        sock.sendto(payload, (CLIENT_IP, CONTROL_PORT))
        time.sleep(0.2)
    print(f"AIUEOS_CONTROL_TX target={CLIENT_IP}:{CONTROL_PORT} "
          f"command={command} nonce={nonce}", flush=True)
    sock.close()


def artifact_sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def murakumo_preflight(opener=urllib.request.urlopen):
    if not murakumo_relay_configured():
        raise RuntimeError("Murakumo node DID or service token is unavailable")
    if not BOOT_PATH.is_file():
        raise RuntimeError(f"PXE boot image is unavailable: {BOOT_PATH}")
    socket.if_nametoindex(INTERFACE)
    status, jobs = murakumo_get(murakumo_queue_path(), opener)
    if status != 200 or not isinstance(jobs, list):
        raise RuntimeError(f"Murakumo queue authentication failed: HTTP {status}")
    return {"did": MURAKUMO_NODE_DID,
            "boot-sha256": artifact_sha256(BOOT_PATH),
            "queued-jobs": len(jobs)}


def next_boot_path():
    with NEXT_BOOT_LOCK:
        if not NEXT_BOOT_STATE_PATH.is_file():
            return BOOT_PATH
        try:
            selected = Path(NEXT_BOOT_STATE_PATH.read_text(
                encoding="utf-8").strip()).resolve()
        except (OSError, ValueError):
            return BOOT_PATH
        return selected if selected.is_file() else BOOT_PATH


def arm_next_boot(path):
    selected = Path(path).resolve()
    if not selected.is_file():
        raise SystemExit(f"missing next-boot EFI: {selected}")
    if selected.stat().st_size > 16 * 1024 * 1024:
        raise SystemExit(f"next-boot EFI exceeds 16 MiB: {selected}")
    with NEXT_BOOT_LOCK:
        NEXT_BOOT_STATE_PATH.write_text(str(selected) + "\n", encoding="utf-8")
    print(f"AIUEOS_PXE_NEXT_BOOT_ARMED path={selected} "
          f"bytes={selected.stat().st_size} sha256={artifact_sha256(selected)}",
          flush=True)


def consume_next_boot(selected):
    with NEXT_BOOT_LOCK:
        if not NEXT_BOOT_STATE_PATH.is_file():
            return
        try:
            armed = Path(NEXT_BOOT_STATE_PATH.read_text(
                encoding="utf-8").strip()).resolve()
        except (OSError, ValueError):
            return
        if armed != selected.resolve():
            return
        NEXT_BOOT_STATE_PATH.unlink()
    print(f"AIUEOS_PXE_NEXT_BOOT_CONSUMED path={selected} "
          f"fallback={BOOT_PATH}", flush=True)


def dhcp_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    bind_interface(sock, 67)
    print(f"AIUEOS_PXE_DHCP_READY interface={INTERFACE} server={SERVER_IP} "
          f"offer={CLIENT_IP}", flush=True)
    # This loop had no exception handling and it runs on the MAIN thread, so any
    # error here did not fail a boot -- it ended the process. Measured
    # 2026-09-08, the first hour the node was resident: a transient
    # `OSError: [Errno 65] No route to host` from the broadcast reply took down
    # DHCP, TFTP, HTTP, the netlog and the murakumo relay together, and the only
    # trace was a traceback in a log nobody reads while the board is up.
    #
    # This is the exact mirror of the netlog loop's own comment, which records
    # the same shape from the other side ("a dead receiver and a quiet wire
    # produced the same empty log"). One datagram must not be able to end the
    # instrument, the error TEXT is kept because a status without a body cannot
    # be diagnosed, and a liveness line makes silence distinguishable from death
    # without reading counters somewhere else.
    served = 0
    failures = 0
    while True:
        try:
            packet, address = sock.recvfrom(4096)
        except Exception as exc:                # noqa: BLE001 - must not die
            failures += 1
            print(f"AIUEOS_PXE_DHCP_RECV_FAIL failures={failures} "
                  f"exc={type(exc).__name__}: {exc}", flush=True)
            continue
        served += 1
        if served % 500 == 0:
            print(f"AIUEOS_PXE_DHCP_ALIVE served={served} "
                  f"failures={failures}", flush=True)
        failures = dhcp_step(sock, packet, failures)


def dhcp_step(sock, packet, failures):
    """One guarded datagram. Returns the new failure count and NEVER raises.

    A function rather than a bare `except` in the loop so the guard itself can
    be tested: a loop that has only ever been fed good packets is not known to
    survive a bad one, and the failure this exists for -- a transient
    `No route to host` on the broadcast reply -- is not one a test can wait for.
    """
    try:
        dhcp_handle(sock, packet)
        return failures
    except Exception as exc:                    # noqa: BLE001 - must not die
        failures += 1
        print(f"AIUEOS_PXE_DHCP_HANDLE_FAIL failures={failures} "
              f"bytes={len(packet)} exc={type(exc).__name__}: {exc}",
              flush=True)
        return failures


def dhcp_send_reply(sock, reply):
    """Put one DHCP reply on the wire, and say which way it went.

    Measured 2026-09-09: the board was asking -- `DHCP_RX` every few seconds,
    both HTTPClient and PXEClient -- and every reply raised
    `OSError: [Errno 65] No route to host` on the listener socket. Twelve in a
    row, no OFFER, no ACK, so no boot. The `dhcp_step` guard did its job and
    kept the process alive, which is exactly why this went unnoticed for two
    hours: the board looked dead, and it was US not answering.

    WHAT IS KNOWN, and the root cause is not among it. en15 is UP and RUNNING
    with 10.77.0.1/24, the route to the client resolves through it, and a
    FRESHLY CREATED socket of the same shape -- SO_REUSEADDR, SO_BROADCAST,
    IP_BOUND_IF en15, bound to a port -- sends to 255.255.255.255,
    10.77.0.255 and 10.77.0.10 without error, all five variants, at the moment
    the long-lived listener was failing. Restarting the service did not fix it,
    so it is not a stale interface index latched at startup either.

    So this does not pretend to know why. It uses the difference that WAS
    measured: fresh sockets work. The listener is tried first because it is
    free when it works, then a fresh interface-bound socket, then the subnet
    broadcast. `via=` names which one carried the reply, because a fallback
    that silently succeeds would hide the fault it exists for -- and the first
    thing anyone will want to know is whether the listener has started working
    again."""
    try:
        sock.sendto(reply, ("255.255.255.255", 68))
        return "listener"
    except OSError as first:
        for label, destination in (("fresh", ("255.255.255.255", 68)),
                                   ("fresh-subnet", (BROADCAST_IP, 68))):
            spare = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                bind_interface(spare, 0)
                spare.sendto(reply, destination)
                return label
            except OSError:
                continue
            finally:
                spare.close()
        raise first


def dhcp_handle(sock, packet):
    if True:
        values = parse_options(packet)
        if len(packet) < 34 or packet[0] != 1 or 53 not in values:
            return
        message_type = values[53][0]
        architecture = struct.unpack("!H", values.get(93, b"\xff\xff")[:2])[0]
        vendor = values.get(60, b"").decode("ascii", "replace")
        mac = mac_address(packet)
        print(f"AIUEOS_PXE_DHCP_RX mac={mac} type={message_type} "
              f"arch={architecture} vendor={vendor!r}", flush=True)
        if not expected_dhcp_client(packet):
            print(f"AIUEOS_PXE_DHCP_IGNORED mac={mac} "
                  f"expected={','.join(PXE_EXPECTED_MACS)}", flush=True)
            return
        if message_type == 1:
            reply_type, label = 2, "OFFER"
        elif message_type == 3:
            selected = values.get(54)
            requested = values.get(50)
            if selected and selected != ipv4(SERVER_IP):
                return
            if requested and requested != ipv4(CLIENT_IP):
                return
            reply_type, label = 5, "ACK"
        else:
            return
        reply = dhcp_reply(packet, reply_type)
        path = dhcp_send_reply(sock, reply)
        boot = HTTP_BOOT_URI if vendor.startswith("HTTPClient") else BOOT_FILE
        print(f"AIUEOS_PXE_DHCP_{label} mac={mac} address={CLIENT_IP} "
              f"boot={boot} via={path}", flush=True)


class HttpBootHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        print(f"AIUEOS_HTTP_GET from={self.client_address[0]} path={self.path}",
              flush=True)
        if self.path.split("?", 1)[0] != f"/{BOOT_FILE}":
            self.send_error(404)
            return
        selected = next_boot_path()
        content = selected.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/efi")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)
        self.wfile.flush()
        consume_next_boot(selected)

    def log_message(self, fmt, *args):
        print(f"AIUEOS_HTTP_RESULT from={self.client_address[0]} "
              f"message={fmt % args}", flush=True)


def http_server():
    server = http.server.ThreadingHTTPServer((SERVER_IP, HTTP_PORT), HttpBootHandler)
    print(f"AIUEOS_HTTP_READY interface={INTERFACE} uri={HTTP_BOOT_URI} "
          f"bytes={BOOT_PATH.stat().st_size}", flush=True)
    server.serve_forever()


def netlog_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    bind_interface(sock, NETLOG_PORT, SERVER_IP)
    print(f"AIUEOS_NETLOG_READY interface={INTERFACE} "
          f"listen={SERVER_IP}:{NETLOG_PORT}", flush=True)
    if MURAKUMO_RESUME_BOOT:
        threading.Thread(
            target=resume_murakumo_job,
            args=(MURAKUMO_RESUME_BOOT, sock, (CLIENT_IP, 7779)),
            daemon=True).start()
    # This loop had no exception handling, and on 2026-09-06 it died --
    # `Exception in thread Thread-3 (netlog_server)` -- while the process kept
    # serving DHCP and TFTP. Three consecutive kernel boots were then recorded
    # as "the machine transmits nothing" when the machine was in fact sending
    # 3.7 MILLION frames per boot: `netstat -I` counted them at 61.8 bytes
    # average, which is this netlog's 62-byte frame. A dead receiver and a
    # quiet wire produced the same empty log.
    #
    # So: never let one datagram kill the instrument, keep the exception text
    # (a status without a body cannot be diagnosed -- the original traceback
    # went to stderr, which nothing captured, and the log holds zero `File "`
    # lines), and emit a liveness line so silence is distinguishable from
    # death without reading counters on another machine.
    received = 0
    failures = 0
    while True:
        try:
            payload, peer = sock.recvfrom(4096)
        except Exception as exc:               # noqa: BLE001 - must not die
            failures += 1
            print(f"AIUEOS_NETLOG_RECV_FAIL failures={failures} "
                  f"exc={type(exc).__name__}: {exc}", flush=True)
            continue
        received += 1
        if received % 10000 == 0:
            print(f"AIUEOS_NETLOG_ALIVE received={received} "
                  f"failures={failures}", flush=True)
        try:
            netlog_handle(sock, payload, peer)
        except Exception as exc:               # noqa: BLE001 - must not die
            failures += 1
            print(f"AIUEOS_NETLOG_HANDLE_FAIL failures={failures} "
                  f"from={peer[0]}:{peer[1]} bytes={len(payload)} "
                  f"exc={type(exc).__name__}: {exc}", flush=True)


def netlog_handle(sock, payload, peer, client_ip=None):
    # `client_ip` is which address counts as THE BOARD on this socket: bus2's
    # 10.77.0.10 for the netlog, bus3's 10.10.10.2 for the relay.  It was a
    # module global until 2026-09-08, which is why one process could not serve
    # both wires.
    CLIENT = CLIENT_IP if client_ip is None else client_ip
    if True:
        message = payload.decode("ascii", "replace").rstrip("\r\n")
        print(f"AIUEOS_NETLOG_RX from={peer[0]}:{peer[1]} "
              f"message={message}", flush=True)
        diagnostic = worker_diagnostic(message)
        if diagnostic:
            print(f"{diagnostic} from={peer[0]}:{peer[1]}", flush=True)
        inference = inference_diagnostic(message)
        if inference:
            print(f"{inference} from={peer[0]}:{peer[1]}", flush=True)
        ack = node_ack_payload(message)
        if ack and peer[0] == CLIENT:
            sock.sendto(ack, peer)
            print(f"AIUEOS_NODE_RELAY_ACK to={peer[0]}:{peer[1]} "
                  f"bytes={len(ack)} scope=diagnostic-only", flush=True)
            threading.Thread(target=relay_murakumo_hello,
                             args=(message, sock, peer),
                             daemon=True).start()
        if JOB_RESULT.fullmatch(message) and peer[0] == CLIENT:
            MURAKUMO_JOB_RESULTS.put((message, peer))
        if NODE_PONG.fullmatch(message) and peer[0] == CLIENT:
            MURAKUMO_LIVENESS_RESULTS.put((message, peer))
        nonce = extract_control_nonce(message)
        if nonce and peer[0] == CLIENT:
            CONTROL_STATE_PATH.write_text(nonce + "\n", encoding="ascii")
            print(f"AIUEOS_CONTROL_STATE nonce={nonce} "
                  f"path={CONTROL_STATE_PATH}", flush=True)


def bus3_sink_receipt(payload, peer):
    """One line per datagram, in k16-bus3-sink.cljk's format.

    Opened by name and closed every time, for the reason that sink documents:
    a receiver that holds the fd keeps writing into an unlinked inode after the
    log is removed, and `ps` and `lsof` both look healthy while every receipt
    goes nowhere.
    """
    line = (f"K16_BUS3_RX from={peer[0]}:{peer[1]} bytes={len(payload)} "
            f"hex={payload.hex()} t={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")
    with open(BUS3_SINK_PATH, "a", encoding="ascii") as sink:
        sink.write(line)


def bus3_relay_server():
    """The Mac end of LAN2: hears AIUEOS_NODE_HELLO_V1 and sends the job.

    Refuses by name rather than racing.  Two readers of one UDP port is a coin
    toss, and a relay that silently lost the toss would report that the board
    never answered.  Stop k16-bus3-sink.cljk before this thread can start; this
    thread writes the same receipts to the same file.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        bind_interface(sock, BUS3_PORT, BUS3_BIND_IP, BUS3_INTERFACE)
    except OSError as error:
        print(f"AIUEOS_BUS3_RELAY_REFUSED reason=bind-failed "
              f"errno={error.errno} interface={BUS3_INTERFACE} "
              f"listen={BUS3_BIND_IP or '0.0.0.0'}:{BUS3_PORT} "
              f"hint=stop k16-bus3-sink.cljk", flush=True)
        return
    print(f"AIUEOS_BUS3_RELAY_READY interface={BUS3_INTERFACE} "
          f"listen={BUS3_BIND_IP or '0.0.0.0'}:{BUS3_PORT} "
          f"node={BUS3_CLIENT_IP} sink={BUS3_SINK_PATH} "
          f"relay-configured={murakumo_relay_configured()}", flush=True)
    received = 0
    failures = 0
    while True:
        try:
            payload, peer = sock.recvfrom(4096)
        except Exception as exc:                # noqa: BLE001 - must not die
            failures += 1
            print(f"AIUEOS_BUS3_RECV_FAIL failures={failures} "
                  f"exc={type(exc).__name__}: {exc}", flush=True)
            continue
        received += 1
        try:
            bus3_sink_receipt(payload, peer)
        except Exception as exc:                # noqa: BLE001
            failures += 1
            print(f"AIUEOS_BUS3_SINK_FAIL failures={failures} "
                  f"exc={type(exc).__name__}: {exc}", flush=True)
        # One byte is the debug plane's own vocabulary (greeting, ping answer,
        # reboot acknowledgement); it is not relay traffic and must not be
        # decoded as a line.
        if len(payload) < 2:
            continue
        try:
            netlog_handle(sock, payload, peer, BUS3_CLIENT_IP)
        except Exception as exc:                # noqa: BLE001
            failures += 1
            print(f"AIUEOS_BUS3_HANDLE_FAIL failures={failures} "
                  f"from={peer[0]}:{peer[1]} bytes={len(payload)} "
                  f"exc={type(exc).__name__}: {exc}", flush=True)


def tftp_oack(options, size):
    accepted = []
    block_size = 512
    if "blksize" in options:
        try:
            block_size = min(1468, max(8, int(options["blksize"])))
            accepted += ["blksize", str(block_size)]
        except ValueError:
            block_size = 512
    if "tsize" in options:
        accepted += ["tsize", str(size)]
    if not accepted:
        return None, block_size
    payload = b"\0".join(part.encode("ascii") for part in accepted) + b"\0"
    return struct.pack("!H", 6) + payload, block_size


def wait_for_ack(sock, peer, block, payload):
    """Send until the peer ACKs `block`. Return (ok, note) describing what was
    heard when it did not.

    `AIUEOS_PXE_TFTP_FAIL stage=oack` used to be the entire story, and it
    cannot tell apart three situations with three different causes: nothing
    came back at all (the reply never reached the board, or the board never
    sent one), something came back from a different TID (a duplicate RRQ's
    handler won the race and this one is the loser -- expected noise, not a
    fault), and something came back that was not an ACK for this block.

    Measured 2026-09-08: the board failed ten OACK handshakes in a row and
    never fetched an image, while the workstation sat at load average 105 and
    the whole log said only `stage=oack` ten times. The elapsed time is in the
    note for the same reason -- a `select` that was supposed to wait one second
    and waited four is scheduling starvation, and that is not visible from a
    boolean."""
    heard = []
    started = time.monotonic()
    for attempt in range(6):
        sent_at = time.monotonic()
        sock.sendto(payload, peer)
        ready, _, _ = select.select([sock], [], [], 1.0)
        if not ready:
            heard.append(f"{attempt}:silent/{time.monotonic() - sent_at:.2f}s")
            continue
        response, source = sock.recvfrom(2048)
        if source != peer:
            heard.append(f"{attempt}:tid-{source[0]}:{source[1]}")
        elif len(response) < 4 or response[:2] != b"\0\4":
            heard.append(f"{attempt}:opcode-{response[:2].hex()}")
        elif struct.unpack("!H", response[2:4])[0] != block:
            heard.append(f"{attempt}:ack-{struct.unpack('!H', response[2:4])[0]}")
        else:
            return True, ""
    return False, (f"heard=[{','.join(heard)}] "
                   f"elapsed={time.monotonic() - started:.2f}s")


def tftp_transfer(peer, request):
    fields = request[2:].split(b"\0")
    if len(fields) < 3:
        return
    filename = fields[0].decode("ascii", "replace").lstrip("/\\").lower()
    mode = fields[1].decode("ascii", "replace").lower()
    options = {}
    for index in range(2, len(fields) - 1, 2):
        if index + 1 < len(fields) and fields[index]:
            options[fields[index].decode("ascii", "replace").lower()] = \
                fields[index + 1].decode("ascii", "replace")
    if filename not in (BOOT_FILE.lower(), "efi/boot/bootx64.efi") or mode != "octet":
        print(f"AIUEOS_PXE_TFTP_REJECT from={peer[0]}:{peer[1]} file={filename} "
              f"mode={mode}", flush=True)
        return
    selected = next_boot_path()
    content = selected.read_bytes()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    bind_interface(sock, 0, SERVER_IP)
    print(f"AIUEOS_PXE_TFTP_RRQ from={peer[0]}:{peer[1]} file={filename} "
          f"artifact={selected.name} bytes={len(content)} options={options}",
          flush=True)
    oack, block_size = tftp_oack(options, len(content))
    if oack is not None:
        acked, note = wait_for_ack(sock, peer, 0, oack)
        if not acked:
            print(f"AIUEOS_PXE_TFTP_FAIL stage=oack peer={peer[0]}:{peer[1]} "
                  f"{note}", flush=True)
            sock.close()
            return
    block = 1
    position = 0
    while True:
        chunk = content[position:position + block_size]
        payload = struct.pack("!HH", 3, block) + chunk
        acked, note = wait_for_ack(sock, peer, block, payload)
        if not acked:
            print(f"AIUEOS_PXE_TFTP_FAIL stage=data block={block} "
                  f"peer={peer[0]}:{peer[1]} {note}", flush=True)
            sock.close()
            return
        position += len(chunk)
        if len(chunk) < block_size:
            break
        block = (block + 1) & 0xffff
    print(f"AIUEOS_PXE_TFTP_OK file={filename} bytes={position}", flush=True)
    sock.close()
    consume_next_boot(selected)


def tftp_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    bind_interface(sock, 69)
    print(f"AIUEOS_PXE_TFTP_READY interface={INTERFACE} server={SERVER_IP} "
          f"file={BOOT_FILE} bytes={BOOT_PATH.stat().st_size}", flush=True)
    while True:
        request, peer = sock.recvfrom(4096)
        if request[:2] == b"\0\1":
            threading.Thread(target=tftp_transfer, args=(peer, request),
                             daemon=True).start()


def selftest_dhcp_guard():
    """The DHCP loop runs on the MAIN thread, so an unguarded error there does
    not fail a boot -- it ends the process, taking TFTP, HTTP, the netlog and
    the murakumo relay with it. Measured 2026-09-08 in the first hour the node
    was resident: OSError(65) on the broadcast reply did exactly that."""
    request = bytearray(300)
    request[0] = 1
    request[28:34] = bytes.fromhex(PXE_EXPECTED_MAC.replace(":", ""))
    request[236:240] = MAGIC
    request[240:243] = bytes([53, 1, 3])        # DHCPREQUEST
    request[243:247] = bytes([93, 2, 0, 16])    # arch 16
    request[247] = 255

    class Raising:
        def sendto(self, *_a):
            raise OSError(65, "No route to host")

    class Sending:
        def __init__(self): self.sent = 0
        def sendto(self, *_a): self.sent += 1

    # the handler does not swallow it ...
    raised = False
    try:
        dhcp_handle(Raising(), bytes(request))
    except OSError:
        raised = True
    assert raised, "dhcp_handle must not hide a send failure"
    # ... and the guard counts it instead of ending the process
    assert dhcp_step(Raising(), bytes(request), 7) == 8
    # a healthy packet is served and does not count as a failure
    ok = Sending()
    assert dhcp_step(ok, bytes(request), 0) == 0
    assert ok.sent == 1


def selftest_bounded_seen():
    """The enrolled-boots set has a ceiling, and keeps the RECENT boots.

    Asserts the bound, not just that membership works, because membership
    worked perfectly well when it was an unbounded set -- growing without limit
    was the whole defect. A board that recovers itself enrolls about four
    thousand times a day, so this only matters once the watchdog works."""
    seen = BoundedSeen(capacity=4)
    for n in range(10):
        seen.add(f"boot{n}")
    assert len(seen) == 4, len(seen)
    assert "boot9" in seen and "boot6" in seen, "dropped a recent boot"
    assert "boot5" not in seen and "boot0" not in seen, "kept an evicted boot"
    seen.add("boot6")                       # re-adding refreshes rather than grows
    assert len(seen) == 4, len(seen)
    seen.discard("boot9")
    assert "boot9" not in seen and len(seen) == 3
    seen.discard("boot9")                   # discarding twice is not an error
    seen.clear()
    assert len(seen) == 0


def selftest_cacao_single_flight():
    """One mint per miss, and a failed mint remembered.

    Until 2026-09-08 the cache lock was released before the subprocess, so
    every caller that missed spawned its own `nbb`. The liveness maintainer
    retries once per stale boot nonce, six were live at once, and none could
    populate the cache because none could finish -- 177 mint timeouts before a
    restart and 46 after, while the same command run once by hand took 0.24 s
    at load 145.

    This asserts the COUNT of subprocess invocations, not just that a blob came
    back, because the stampede returned perfectly good blobs; it was the number
    of them that was the defect. Against the unmodified file this fails with
    `STAMPEDE: 8 concurrent mints`."""
    saved = (MURAKUMO_CACAO_MINT, MURAKUMO_NODE_KEY_FILE,
             MURAKUMO_NODE_DID_FILE, MURAKUMO_CACAO_CLASSPATH, subprocess.run)
    calls = []

    def fake(command, capture_output=None, timeout=None):
        calls.append(1)
        time.sleep(0.2)
        return types.SimpleNamespace(returncode=0, stdout=b"BLOB", stderr=b"")

    def fake_timeout(command, capture_output=None, timeout=None):
        calls.append(1)
        time.sleep(0.1)
        raise subprocess.TimeoutExpired(command, timeout or 1)

    def race(fn):
        calls.clear()
        MURAKUMO_CACAO_CACHE.clear()
        globals()["subprocess"].run = fn
        out = []
        threads = [threading.Thread(target=lambda: out.append(
            murakumo_cacao("https://selftest.invalid"))) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return len(calls), out

    try:
        globals()["MURAKUMO_CACAO_MINT"] = "/selftest/mint"
        globals()["MURAKUMO_NODE_KEY_FILE"] = "/selftest/key"
        globals()["MURAKUMO_NODE_DID_FILE"] = "/selftest/did"
        globals()["MURAKUMO_CACAO_CLASSPATH"] = ""

        spawned, out = race(fake)
        assert spawned == 1, f"STAMPEDE: {spawned} concurrent mints"
        assert out == ["BLOB"] * 8, out

        spawned, out = race(fake_timeout)
        assert spawned == 1, f"STAMPEDE on failure: {spawned} mints"
        assert out == [""] * 8, out

        calls.clear()
        assert murakumo_cacao("https://selftest.invalid") == ""
        assert not calls, "a failed mint was not negative-cached"
    finally:
        (globals()["MURAKUMO_CACAO_MINT"], globals()["MURAKUMO_NODE_KEY_FILE"],
         globals()["MURAKUMO_NODE_DID_FILE"],
         globals()["MURAKUMO_CACAO_CLASSPATH"]) = saved[:4]
        globals()["subprocess"].run = saved[4]
        MURAKUMO_CACAO_CACHE.clear()


def selftest_authorization():
    """Which credential each route gets, and that "no credential" is its own
    value rather than a blank Bearer -- an empty bearer reads as a token
    problem at the far end, which is the wrong thing to go looking at."""
    saved = (MURAKUMO_SERVICE_TOKEN, MURAKUMO_NODE_KEY_FILE,
             MURAKUMO_CACAO_MINT, MURAKUMO_NODE_DID_FILE)
    try:
        globals()["MURAKUMO_SERVICE_TOKEN"] = "operator-secret"
        MURAKUMO_CACAO_CACHE.clear()
        assert murakumo_authorization("/infer/nodes") == "Bearer operator-secret"
        globals()["MURAKUMO_SERVICE_TOKEN"] = ""
        globals()["MURAKUMO_NODE_KEY_FILE"] = ""
        globals()["MURAKUMO_CACAO_MINT"] = ""
        assert murakumo_authorization("/infer/nodes") == ""
        assert murakumo_relay_configured() is False
        # A mint that REFUSES must yield "", never a half-formed header.
        with tempfile.TemporaryDirectory() as work:
            stub = Path(work) / "refuse.cljs"
            stub.write_text('(binding [*print-fn* *print-err-fn*]'
                            ' (println "K16_CACAO_REFUSED stub"))'
                            '(js/process.exit 2)\n', encoding="ascii")
            keyf = Path(work) / "k.pem"
            keyf.write_text("x", encoding="ascii")
            didf = Path(work) / "k.did"
            didf.write_text("did:key:zStub\n", encoding="ascii")
            globals()["MURAKUMO_NODE_KEY_FILE"] = str(keyf)
            globals()["MURAKUMO_NODE_DID_FILE"] = str(didf)
            globals()["MURAKUMO_CACAO_MINT"] = str(stub)
            MURAKUMO_CACAO_CACHE.clear()
            assert murakumo_authorization("/infer/nodes") == ""
    finally:
        (globals()["MURAKUMO_SERVICE_TOKEN"], globals()["MURAKUMO_NODE_KEY_FILE"],
         globals()["MURAKUMO_CACAO_MINT"], globals()["MURAKUMO_NODE_DID_FILE"]) = saved
        MURAKUMO_CACAO_CACHE.clear()


def selftest_interface_wait():
    """The missing-wire path, both directions, and the real syscall as the
    control: a name no adapter carries must come back None from the same
    function main() gates on, or the wait is testing a stub of itself."""
    assert interface_index("lo0") is not None
    assert interface_index("aiueos-no-such-wire0") is None
    slept = []
    # Present from the first poll: no sleep, no wait.
    assert wait_for_interfaces(["lo0"], sleep=slept.append) == 0
    assert slept == []
    # Absent for two polls, then present: exactly two sleeps of the period.
    seen = iter([None, None, 15])
    polls = wait_for_interfaces(["en-wait"], index=lambda _name: next(seen),
                                sleep=slept.append, poll_seconds=0.25)
    assert polls == 2 and slept == [0.25, 0.25], (polls, slept)
    # A plane that escapes exits with EXIT_PLANE_DOWN, and exits exactly once.
    exits = []

    def broken():
        raise OSError(6, "Device not configured")

    serve_plane("selftest", broken, exit=exits.append)
    assert exits == [EXIT_PLANE_DOWN], exits
    # A plane that returns normally never touches exit.
    assert serve_plane("selftest", lambda: "served", exit=exits.append) == \
        "served"
    assert exits == [EXIT_PLANE_DOWN]


def selftest():
    with tempfile.TemporaryDirectory() as directory:
        private_path = Path(directory) / "credential"
        private_path.write_text("bounded-value\n", encoding="ascii")
        private_path.chmod(0o600)
        assert private_file_text(private_path, "selftest credential", 32) == \
            "bounded-value"
        private_path.chmod(0o640)
        try:
            private_file_text(private_path, "selftest credential", 32)
            raise AssertionError("group-readable credential accepted")
        except RuntimeError:
            pass

    inference = inference_diagnostic(
        "AIUEOS_INFERENCE_RX 00065a69e05b19ca 00000002 "
        "00000002 00000004 00000009")
    assert inference and "job-id=1788260642396618" in inference
    assert "attempt=2" in inference and "failed-token=2" in inference
    assert "failed-layer=4" in inference and "failure-stage=9:full-softmax" \
        in inference
    assert inference_diagnostic(
        "AIUEOS_INFERENCE_RX 00065a4db6b359ca 00000002") is None

    request = bytearray(240)
    request[0:4] = bytes((1, 1, 6, 0))
    request[4:8] = b"TEST"
    request[28:34] = bytes.fromhex(PXE_EXPECTED_MAC.replace(":", ""))
    request[236:240] = MAGIC
    request += option(53, b"\1") + option(60, b"PXEClient") + \
        option(93, struct.pack("!H", 9)) + b"\xff"
    reply = dhcp_reply(bytes(request), 2)
    values = parse_options(reply)
    assert reply[0] == 2 and reply[16:20] == ipv4(CLIENT_IP)
    assert reply[20:24] == ipv4(SERVER_IP)
    assert values[53] == b"\2" and values[67] == BOOT_FILE.encode("ascii")
    assert 60 not in values
    assert reply[108:108 + len(BOOT_FILE)] == BOOT_FILE.encode("ascii")
    assert expected_dhcp_client(bytes(request))
    unexpected_request = bytearray(request)
    unexpected_request[28:34] = b"\x2c\x9e\x00\x72\x74\x16"
    assert not expected_dhcp_client(bytes(unexpected_request))

    http_request = bytearray(request[:240])
    http_request += option(53, b"\1") + option(60, b"HTTPClient") + \
        option(93, struct.pack("!H", 16)) + b"\xff"
    http_reply = dhcp_reply(bytes(http_request), 2)
    http_values = parse_options(http_reply)
    http_uri = HTTP_BOOT_URI.encode("ascii")
    assert http_values[60] == b"HTTPClient"
    assert http_values[67] == http_uri
    assert http_values[93] == struct.pack("!H", 16)
    assert http_reply[108:108 + len(http_uri)] == http_uri
    oack, size = tftp_oack({"blksize": "1024", "tsize": "0"}, 13312)
    assert size == 1024 and b"tsize\00013312\000" in oack
    selftest_dhcp_guard()
    selftest_bounded_seen()
    selftest_cacao_single_flight()
    selftest_authorization()
    selftest_interface_wait()
    ready = "AIUEOS_CONTROL_READY nonce=0123456789abcdef commands=ping,reboot-pxe"
    assert extract_control_nonce(ready) == "0123456789abcdef"
    assert control_payload("ping", "0123456789abcdef") == \
        b"AIUEOS_CTL_V1 nonce=0123456789abcdef command=ping"
    hello = ("AIUEOS_NODE_HELLO_V1 boot=0123456789abcdef "
             "mac=70-70-fc-0b-b6-32 profile=rtl8125-relay-test")
    assert node_ack_payload(hello) == \
        b"AIUEOS_NODE_ACK_V1 boot=0123456789abcdef state=accepted"
    assert node_ack_payload(hello.replace("0123456789abcdef", "short")) is None
    # Both of the board's NICs are the same board, and the announcement leaves
    # by bus3 (…b6:31). The bus3 case is the one that was rejected in
    # production on 2026-09-08; a foreign MAC must still be refused, or this
    # list would mean "any board".
    bus3_hello = hello.replace("b6-32", "b6-31")
    foreign_hello = hello.replace("70-70-fc-0b-b6-32", "aa-bb-cc-dd-ee-ff")
    assert NODE_HELLO.fullmatch(bus3_hello).group(2) in MURAKUMO_EXPECTED_MACS
    assert NODE_HELLO.fullmatch(hello).group(2) in MURAKUMO_EXPECTED_MACS
    assert NODE_HELLO.fullmatch(foreign_hello).group(2) not in MURAKUMO_EXPECTED_MACS
    assert register_murakumo_hello(foreign_hello) == \
        {"state": "ignored", "reason": "unexpected-mac"}
    # The result line the physical board actually returned on 2026-09-08 for
    # the contract's known-answer prompt, verbatim off the wire. It is here so
    # a change to JOB_RESULT or to the expectation table has to face a real
    # measurement rather than a hand-written sample.
    measured = ("AIUEOS_JOB_RESULT_V1 boot=0000000e8debe541 id=352 "
                "model=aiueos-char-bigram-v1 token=6f score=02 total=05 "
                "cycles=0000000000001152")
    assert verified_job_result(measured, "0000000e8debe541", "352", "murakum") == {
        "text": "o", "model": MURAKUMO_JOB_MODEL, "score": 2, "total": 5,
        "inference-cycles": 1152, "prompt": "murakum",
        "corpus-sha256": MURAKUMO_JOB_CORPUS_SHA256,
        "boot": "0000000e8debe541"}
    assert verified_job_result(measured, "0000000e8debe541", "352", "kotoba") is None
    assert verified_job_result(measured, "0000000e8debe541", "353", "murakum") is None
    # A LATER boot may answer -- but only one this node announced. Without the
    # second half the binding is decoration: any sender could pick a nonce.
    MURAKUMO_ANNOUNCED_BOOTS.clear()
    assert verified_job_result(measured, "ffffffffffffffff", "352", "murakum") is None
    MURAKUMO_ANNOUNCED_BOOTS.append("0000000e8debe541")
    assert verified_job_result(measured, "ffffffffffffffff", "352", "murakum") is not None
    MURAKUMO_ANNOUNCED_BOOTS.clear()
    # The bus3 socket must treat 10.10.10.2 as the board, and must NOT treat
    # the netlog's client as one -- a handler that answered to both would let
    # either wire drive the other's relay.
    class _Silent:
        def sendto(self, *_args):
            raise AssertionError("bus3 routing selftest must not transmit")
    while not MURAKUMO_JOB_RESULTS.empty():
        MURAKUMO_JOB_RESULTS.get_nowait()
    netlog_handle(_Silent(), measured.encode("ascii"),
                  (BUS3_CLIENT_IP, BUS3_PORT), BUS3_CLIENT_IP)
    assert MURAKUMO_JOB_RESULTS.qsize() == 1
    MURAKUMO_JOB_RESULTS.get_nowait()
    netlog_handle(_Silent(), measured.encode("ascii"),
                  ("10.99.99.99", BUS3_PORT), BUS3_CLIENT_IP)
    assert MURAKUMO_JOB_RESULTS.qsize() == 0
    netlog_handle(_Silent(), measured.encode("ascii"),
                  (CLIENT_IP, NETLOG_PORT))
    assert MURAKUMO_JOB_RESULTS.qsize() == 1
    MURAKUMO_JOB_RESULTS.get_nowait()
    old_did, old_token = MURAKUMO_NODE_DID, MURAKUMO_SERVICE_TOKEN
    try:
        globals()["MURAKUMO_NODE_DID"] = "did:key:z6MkK16Selftest"
        globals()["MURAKUMO_SERVICE_TOKEN"] = "selftest-token"
        captured = []

        class FakeResponse:
            def __init__(self, status, body=b"{}"):
                self.status = status
                self.body = body
            def read(self, _limit):
                return self.body
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                return False

        def fake_open(request, timeout):
            captured.append((request.full_url, request.data,
                             request.get_header("Authorization"), timeout))
            return FakeResponse(201)

        result = register_murakumo_hello(hello, fake_open)
        assert result["state"] == "live-not-ready"
        assert len(captured) == 2
        assert captured[0][0].endswith("/infer/nodes")
        assert captured[1][0].endswith("/gmktec-k16/heartbeat")
        assert captured[0][2] == "Bearer selftest-token"
        enrollment = json.loads(captured[0][1])
        heartbeat = json.loads(captured[1][1])
        assert enrollment["node/trust-tier"] == MURAKUMO_TRUST_TIER
        # The claimed actor. A CACAO authorizes nothing without it, and the
        # 401 that results names the CACAO rather than the missing field.
        assert enrollment["did"] == MURAKUMO_NODE_DID
        assert enrollment["node/needs-relay?"] is True
        assert heartbeat["node/ready?"] is False
        assert "node/capacity" not in heartbeat and "node/model" not in heartbeat
        assert register_murakumo_hello(hello, fake_open)["state"] == "duplicate"

        globals()["MURAKUMO_JOB_QUALIFICATION"] = True
        job_captured = []
        class FakeSocket:
            def __init__(self):
                self.sent = []
            def sendto(self, payload, peer):
                self.sent.append((payload, peer))
        fake_socket = FakeSocket()
        fake_results = queue.Queue()
        fake_results.put((
            "AIUEOS_JOB_RESULT_V1 boot=0123456789abcdef id=209 "
            "model=aiueos-char-bigram-v1 token=6f score=2 total=5 cycles=41",
            (CLIENT_IP, 7779)))
        def fake_job_open(request, timeout):
            job_captured.append((request.full_url, request.method, request.data,
                                 request.get_header("Authorization"), timeout))
            if request.method == "GET":
                return FakeResponse(200, json.dumps([{
                    "job-id": "209", "kind": MURAKUMO_JOB_KIND,
                    "input": {"model": MURAKUMO_JOB_MODEL,
                              "prompt": MURAKUMO_JOB_PROMPT},
                    "price": 0}]).encode("utf-8"))
            if request.full_url.endswith("/infer/queue"):
                return FakeResponse(201, b'{"job-id":"209"}')
            return FakeResponse(201)
        qualified = qualify_murakumo_job(
            hello, fake_socket, (CLIENT_IP, 7779), fake_job_open,
            fake_results, lambda _seconds: None)
        assert qualified["state"] == "ready" and qualified["job-id"] == "209"
        assert [entry[1] for entry in job_captured] == \
            ["POST", "GET", "POST", "POST", "POST"]
        assert all(entry[3] == "Bearer selftest-token" for entry in job_captured)
        assert fake_socket.sent[0][0] == \
            b"AIUEOS_JOB_V1 boot=0123456789abcdef id=209 kind=aiueos-micro-infer prompt=6d7572616b756d"
        assert fake_socket.sent[-1][0] == \
            b"AIUEOS_JOB_COMMIT_V1 boot=0123456789abcdef id=209 state=recorded"
        ready_body = json.loads(job_captured[-1][2])
        assert ready_body["node/ready?"] is True
        assert ready_body["node/model"] == MURAKUMO_JOB_MODEL
        assert ready_body["node/capacity"] == {
            "slots-total": 1, "slots-free": 1}
        enqueue_body = json.loads(job_captured[0][2])
        assert enqueue_body["target-did"] == "did:key:z6MkK16Selftest"
        assert "did%3Akey%3Az6MkK16Selftest" in job_captured[1][0]
        result_body = json.loads(job_captured[3][2])
        assert result_body["ms"] >= 1
        assert result_body["output"]["inference-cycles"] == 41
        assert result_body["output"]["relay-round-trip-ns"] >= 1
        assert micro_infer_expected("awai") == ("n", 3, 8)
        assert micro_infer_expected("ends-in-b") is None
        race_calls = []
        race_enqueue = [0]
        race_results = queue.Queue()
        race_results.put((
            "AIUEOS_JOB_RESULT_V1 boot=0123456789abcdef id=212 "
            "model=aiueos-char-bigram-v1 token=6f score=2 total=5 cycles=42",
            (CLIENT_IP, 7779)))
        def fake_race_open(request, timeout):
            race_calls.append((request.full_url, request.method))
            if request.method == "GET":
                job_id = str(211 + race_enqueue[0] - 1)
                return FakeResponse(200, json.dumps([{
                    "job-id": job_id, "kind": MURAKUMO_JOB_KIND,
                    "input": {"model": MURAKUMO_JOB_MODEL,
                              "prompt": MURAKUMO_JOB_PROMPT},
                    "price": 0}]).encode("utf-8"))
            if request.full_url.endswith("/infer/queue"):
                job_id = str(211 + race_enqueue[0])
                race_enqueue[0] += 1
                return FakeResponse(201, json.dumps(
                    {"job-id": job_id}).encode("utf-8"))
            if request.full_url.endswith("/211/claim"):
                return FakeResponse(409)
            return FakeResponse(201)
        retried = qualify_murakumo_job(
            hello, fake_socket, (CLIENT_IP, 7779), fake_race_open,
            race_results, lambda _seconds: None)
        assert retried["state"] == "ready" and retried["job-id"] == "212"
        assert sum(url.endswith("/claim") for url, _method in race_calls) == 2
        liveness_results = queue.Queue()
        liveness_results.put((
            "AIUEOS_NODE_PONG_V1 boot=0123456789abcdef seq=1 state=ready",
            (CLIENT_IP, 7779)))
        worker_results = queue.Queue()
        worker_results.put((
            "AIUEOS_JOB_RESULT_V1 boot=0123456789abcdef id=210 "
            "model=aiueos-char-bigram-v1 token=6e score=3 total=8 cycles=43",
            (CLIENT_IP, 7779)))
        liveness_captured = []
        liveness_gets = [0]
        def fake_liveness_open(request, timeout):
            liveness_captured.append((request.full_url, request.method,
                                      request.data, timeout))
            if request.method == "GET":
                liveness_gets[0] += 1
                jobs = [{"job-id": "210", "kind": MURAKUMO_JOB_KIND,
                         "input": {"model": MURAKUMO_JOB_MODEL,
                                   "prompt": "awai"}, "price": 1}] \
                    if liveness_gets[0] == 1 else []
                return FakeResponse(200, json.dumps(jobs).encode("utf-8"))
            return FakeResponse(201)
        liveness = maintain_murakumo_liveness(
            "0123456789abcdef", fake_socket, (CLIENT_IP, 7779),
            fake_liveness_open, liveness_results, lambda _seconds: None,
            rounds=2, interval=0, timeout=0.1,
            job_result_queue=worker_results)
        assert liveness == {"state": "live", "boot": "0123456789abcdef",
                            "renewed": 2, "executed": 1}
        assert any(payload ==
                   b"AIUEOS_JOB_V1 boot=0123456789abcdef id=210 kind=aiueos-micro-infer prompt=61776169"
                   for payload, _peer in fake_socket.sent)
        assert any(payload ==
                   b"AIUEOS_NODE_PING_V1 boot=0123456789abcdef seq=1"
                   for payload, _peer in fake_socket.sent)
        assert fake_socket.sent[-1][0] == \
            b"AIUEOS_JOB_COMMIT_V1 boot=0123456789abcdef id=210 state=recorded"
        assert [entry[1] for entry in liveness_captured] == \
            ["POST", "GET", "POST", "POST", "POST"]
        recovery_results = queue.Queue()
        recovery_sleeps = []
        def recover_sleep(seconds):
            recovery_sleeps.append(seconds)
            if recovery_results.empty():
                recovery_results.put((
                    "AIUEOS_NODE_PONG_V1 boot=0123456789abcdef seq=1 state=ready",
                    (CLIENT_IP, 7779)))
        recovered = maintain_murakumo_liveness(
            "0123456789abcdef", fake_socket, (CLIENT_IP, 7779),
            fake_liveness_open, recovery_results, recover_sleep,
            rounds=1, interval=0, timeout=0.01,
            max_failures=2, retry_interval=0)
        assert recovered == {"state": "live", "boot": "0123456789abcdef",
                             "renewed": 1, "executed": 0}
        assert recovery_sleeps == [0]
        class FailOnceSocket(FakeSocket):
            def __init__(self):
                super().__init__()
                self.failures = 1
            def sendto(self, payload, peer):
                if self.failures:
                    self.failures -= 1
                    raise OSError(65, "No route to host")
                super().sendto(payload, peer)
        send_recovery_results = queue.Queue()
        send_recovery_sleeps = []
        def recover_send_sleep(seconds):
            send_recovery_sleeps.append(seconds)
            if send_recovery_results.empty():
                send_recovery_results.put((
                    "AIUEOS_NODE_PONG_V1 boot=0123456789abcdef seq=1 state=ready",
                    (CLIENT_IP, 7779)))
        send_recovered = maintain_murakumo_liveness(
            "0123456789abcdef", FailOnceSocket(), (CLIENT_IP, 7779),
            fake_liveness_open, send_recovery_results, recover_send_sleep,
            rounds=1, interval=0, timeout=0.01,
            max_failures=2, retry_interval=0)
        assert send_recovered == {
            "state": "live", "boot": "0123456789abcdef",
            "renewed": 1, "executed": 0}
        assert send_recovery_sleeps == [0]
        assert len(job_captured) == 5
    finally:
        globals()["MURAKUMO_NODE_DID"] = old_did
        globals()["MURAKUMO_SERVICE_TOKEN"] = old_token
        globals()["MURAKUMO_JOB_QUALIFICATION"] = False
        MURAKUMO_SEEN_BOOTS.clear()
    try:
        control_payload("reboot", "0123456789abcdef")
        raise AssertionError("unsupported control command accepted")
    except ValueError:
        pass
    print("AIUEOS_PXE_SELFTEST_OK dhcp=pxe+http+mac-bound tftp=oack cacao=single-flight seen=bounded control=token-bound "
          "node-relay=request-bound murakumo=qualify+poll+claim+result+renew+recover "
          "interface-bound=yes interface-wait=polled plane-down=exits")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("--control", choices=CONTROL_COMMANDS)
    parser.add_argument("--nonce")
    parser.add_argument("--next-boot")
    parser.add_argument("--resume-boot")
    args = parser.parse_args()
    if args.selftest:
        selftest()
        return
    if args.preflight:
        result = murakumo_preflight()
        print("AIUEOS_MURAKUMO_PREFLIGHT_OK " +
              " ".join(f"{key}={value}" for key, value in result.items()))
        return
    if args.next_boot:
        arm_next_boot(args.next_boot)
    if args.control:
        nonce = args.nonce
        if not nonce:
            if not CONTROL_STATE_PATH.is_file():
                raise SystemExit(f"missing control nonce: {CONTROL_STATE_PATH}")
            nonce = CONTROL_STATE_PATH.read_text(encoding="ascii").strip()
        send_control(args.control, nonce)
        return
    if args.next_boot:
        return
    if args.resume_boot:
        if not re.fullmatch(r"[0-9a-f]{16}", args.resume_boot):
            raise SystemExit("resume boot must be 16 lowercase hex digits")
        globals()["MURAKUMO_RESUME_BOOT"] = args.resume_boot
    if not BOOT_PATH.is_file():
        raise SystemExit(f"missing boot file: {BOOT_PATH}")
    # Only the PXE wire gates startup.  bus3 already refuses by name when
    # its wire or port is not there, and a relay that is down must not keep
    # the board from booting over the wire that is.
    wait_for_interfaces([INTERFACE])
    for name, target in (("tftp", tftp_server), ("http", http_server),
                         ("netlog", netlog_server)):
        threading.Thread(target=serve_plane, args=(name, target),
                         name=name, daemon=True).start()
    if BUS3_ENABLED:
        threading.Thread(target=serve_plane, args=("bus3", bus3_relay_server),
                         name="bus3", daemon=True).start()
    else:
        print("AIUEOS_BUS3_RELAY_DISABLED reason=AIUEOS_PXE_BUS3_RELAY!=1",
              flush=True)
    serve_plane("dhcp", dhcp_server)


if __name__ == "__main__":
    main()
