#!/usr/bin/env python3
"""Build the deterministic aiueos `newc` initramfs.

Early-component and recovery materials travel as a cpio archive whose bytes
are fixed by the inputs alone: mode/uid/gid/mtime are constant, entries are
emitted in the order given, and inode numbers are sequential. The loader binds
the archive to a compiled-in SHA-256 before handing it to the kernel.
"""

import argparse
from pathlib import Path

ALIGN = 4


def align(buffer):
    while len(buffer) % ALIGN:
        buffer.append(0)


def entry(buffer, name, data, inode, mode):
    header = ("070701" + f"{inode:08x}" + f"{mode:08x}" + "00000000" + "00000000" +
              "00000001" + "00000000" + f"{len(data):08x}" + "00000000" + "00000000" +
              "00000000" + "00000000" + f"{len(name) + 1:08x}" + "00000000")
    buffer += header.encode("ascii")
    buffer += name.encode("ascii") + b"\x00"
    align(buffer)
    buffer += data
    align(buffer)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--entry", action="append", required=True,
                        metavar="ARCHIVE_NAME,SOURCE_PATH")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    buffer = bytearray()
    inode = 1
    for specification in args.entry:
        name, _, source = specification.partition(",")
        if not name or not source:
            raise SystemExit("entry must be ARCHIVE_NAME,SOURCE_PATH")
        entry(buffer, name, Path(source).read_bytes(), inode, 0o100444)
        inode += 1
    entry(buffer, "TRAILER!!!", b"", 0, 0)
    Path(args.output).write_bytes(bytes(buffer))
    print(args.output)


if __name__ == "__main__":
    main()
