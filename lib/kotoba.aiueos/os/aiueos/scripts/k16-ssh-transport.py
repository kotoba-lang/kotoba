#!/usr/bin/env python3
"""OpenSSH stdio transport for the bounded AIUEOS K16 TCP listener.

The pure-AIUEOS RTL8125 slice owns one receive descriptor.  Preserve SSH
packet boundaries and handshake order without root privileges, a password,
or a debug shell.  OpenSSH invokes this program through ProxyCommand.
"""

import os
import select
import socket
import sys
import time


TCP_ENABLE_ECN = 0x104


def log(message):
    print(message, file=sys.stderr, flush=True)


def write_fd(fd, payload):
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise RuntimeError("SSH stdio transport closed while writing")
        view = view[written:]


def read_exact_fd(fd, length):
    payload = bytearray()
    while len(payload) < length:
        part = os.read(fd, length - len(payload))
        if not part:
            raise RuntimeError("OpenSSH closed before a complete packet")
        payload.extend(part)
    return bytes(payload)


def read_line_fd(fd, limit=1024):
    payload = bytearray()
    while len(payload) < limit:
        part = read_exact_fd(fd, 1)
        payload.extend(part)
        if part == b"\n":
            return bytes(payload)
    raise RuntimeError("OpenSSH identification exceeds bounded limit")


def recv_exact(stream, length):
    payload = bytearray()
    while len(payload) < length:
        part = stream.recv(length - len(payload))
        if not part:
            raise RuntimeError("K16 closed before a complete packet")
        payload.extend(part)
    return bytes(payload)


def recv_line(stream, limit=1024):
    payload = bytearray()
    while len(payload) < limit:
        part = recv_exact(stream, 1)
        payload.extend(part)
        if part == b"\n":
            return bytes(payload)
    raise RuntimeError("K16 identification exceeds bounded limit")


def read_ssh_packet_fd(fd):
    prefix = read_exact_fd(fd, 4)
    packet_length = int.from_bytes(prefix, "big")
    if packet_length < 8 or packet_length > 4096:
        raise RuntimeError("OpenSSH KEXINIT exceeds bounded transport profile")
    return prefix + read_exact_fd(fd, packet_length)


def recv_ssh_packet(stream):
    prefix = recv_exact(stream, 4)
    packet_length = int.from_bytes(prefix, "big")
    if packet_length < 8 or packet_length > 4096:
        raise RuntimeError("K16 KEXINIT exceeds bounded transport profile")
    return prefix + recv_exact(stream, packet_length)


def connect_k16(host, port):
    last_error = None
    for attempt in range(1, 11):
        stream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            stream.setsockopt(socket.IPPROTO_TCP, TCP_ENABLE_ECN, 0)
        except OSError:
            pass
        stream.settimeout(3)
        try:
            stream.connect((host, port))
            stream.settimeout(30)
            log(f"AIUEOS_K16_SSH_TRANSPORT_TCP_OK attempt={attempt} ecn=disabled")
            return stream
        except (TimeoutError, OSError) as error:
            last_error = error
            stream.close()
            time.sleep(0.2)
    raise RuntimeError(f"K16 SSH listener unavailable: {last_error}")


def relay(stream):
    server_newkeys_seen = False
    client_newkeys_sent = False
    stream.settimeout(None)
    while True:
        readable, _, _ = select.select([0, stream], [], [], 45)
        if not readable:
            raise RuntimeError("SSH transport idle timeout")
        for source in readable:
            if source == 0:
                payload = os.read(0, 65536)
                if not payload:
                    return
                if server_newkeys_seen and not client_newkeys_sent:
                    packet_length = (int.from_bytes(payload[:4], "big")
                                     if len(payload) >= 6 else 0)
                    first_wire_length = 4 + packet_length
                    if (first_wire_length == 16 and payload[5] == 21 and
                            first_wire_length <= len(payload)):
                        stream.sendall(payload[:first_wire_length])
                        client_newkeys_sent = True
                        if first_wire_length < len(payload):
                            time.sleep(0.5)
                            stream.sendall(payload[first_wire_length:])
                        continue
                stream.sendall(payload)
            else:
                payload = stream.recv(65536)
                if not payload:
                    return
                server_newkeys_seen = True
                write_fd(1, payload)


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: k16-ssh-transport.py host port")
    host, port_text = sys.argv[1:]
    port = int(port_text)
    if not 1 <= port <= 65535:
        raise SystemExit("error: port must be 1..65535")
    stream = connect_k16(host, port)
    try:
        server_id = recv_line(stream)
        write_fd(1, server_id)
        client_id = read_line_fd(0)
        stream.sendall(client_id)

        # OpenSSH writes KEXINIT before it receives the server KEXINIT.  The
        # K16 listener is packet-bounded, so deliver the server packet first,
        # then the exact client packet, then allow ECDH_INIT to proceed.
        server_kex = recv_ssh_packet(stream)
        client_kex = read_ssh_packet_fd(0)
        write_fd(1, server_kex)
        time.sleep(0.25)
        stream.sendall(client_kex)
        time.sleep(0.25)
        relay(stream)
    finally:
        stream.close()


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        pass
    except Exception as error:
        log(f"AIUEOS_K16_SSH_TRANSPORT_FAIL {type(error).__name__}:{error}")
        raise
