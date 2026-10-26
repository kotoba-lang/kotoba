#!/usr/bin/env python3
"""Standalone netlog receiver for the K16.

The PXE server's own netlog thread died with an unhandled exception on
2026-09-06 while the process kept serving DHCP and TFTP, so three boots were
recorded as "the machine transmits nothing" when it was sending 3.7 million
frames per boot. That process binds UDP 67 and 69 and cannot be restarted by
this user (binding a port below 1024 is EPERM here), so the instrument is
rebuilt beside it rather than inside it: 7777 is unprivileged.

Never dies on a datagram. Prints a liveness line so a dead receiver and a
quiet wire cannot look the same again.
"""
import socket, sys, time

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 << 20)
sock.bind(("10.77.0.1", 7777))
print(f"AIUEOS_NETLOG_STANDALONE_READY listen=10.77.0.1:7777 t={time.time():.0f}",
      flush=True)
n = fails = 0
while True:
    try:
        payload, peer = sock.recvfrom(4096)
    except Exception as exc:                      # noqa: BLE001
        fails += 1
        print(f"AIUEOS_NETLOG_RECV_FAIL failures={fails} "
              f"exc={type(exc).__name__}: {exc}", flush=True)
        continue
    n += 1
    try:
        message = payload.decode("ascii", "replace").rstrip("\r\n")
        # t= is the receiver's wall clock in ms: window durations (A9 -> 21) and
        # bridge latency are measured from it; without it the log had no time.
        print(f"AIUEOS_NETLOG_RX from={peer[0]}:{peer[1]} message={message} t={time.time()*1000:.0f}",
              flush=True)
    except Exception as exc:                      # noqa: BLE001
        fails += 1
        print(f"AIUEOS_NETLOG_DECODE_FAIL failures={fails} bytes={len(payload)} "
              f"exc={type(exc).__name__}: {exc}", flush=True)
    if n % 10000 == 0:
        print(f"AIUEOS_NETLOG_ALIVE received={n} failures={fails}", flush=True)
