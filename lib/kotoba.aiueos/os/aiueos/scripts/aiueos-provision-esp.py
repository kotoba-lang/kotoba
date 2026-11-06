#!/usr/bin/env python3
"""JUN-813 stage 5c follow-up (ADR-0286 amendment 4): provision \\EFI\\ITONAMI\\OSMETA.BIN on an already installed ESP.

native/update.kotoba refuses every network install with result 10 when the update journal (OSMETA.BIN) is missing, unreadable, corrupt or
never initialised. Nothing at boot or on the network path creates it (the journal's rule "no boot formatting"), and no image builder creates
\\EFI\\ITONAMI\\ at all. This command is the deliberate, separate provisioning step for a board that already has the directory:

  aiueos-provision-esp.py DISK --version N [--replace] [--block-size 512|4096]

DISK is a raw disk image or a block device (the whole disk, GPT included). N is REQUIRED: the version of the image the board runs now,
the same convention as `aiueos-image.py sign --version N`. The journal is written confirmed (phase 0) with floor = active = N, so a board
accepts exactly versions above N. There is no default and no inference.

It writes the file with the exact format of native/update_journal.kotoba (20480 bytes = five 4 KiB pages: marker "OSUPMETA" page 0, head
page 1 generation 1 naming sector 3, the generation-1 slot on page 3, pages 2 and 4 zero; the slot's last 32 bytes are the SHA-256 of its
first 480; the head repeats that digest) and places it the way native/esp.kotoba `record-file` requires: a directory entry in the same
device block as BOOTX64.EFI's entry (so the guest's own block write could have made it), one contiguous run of free clusters taken from
every FAT copy, the first cluster's byte offset 4096-aligned, the whole file inside the GPT's ESP, FAT32 only, GPT header and entry array
CRCs checked. The active-image digest field is the SHA-256 of \\EFI\\ITONAMI\\BOOTX64.EFI read from the same ESP.

Nothing is written (exit status 2) when: --version is missing or not a positive integer below 2^63, the disk has no valid GPT or ESP or is
not FAT32, \\EFI\\ITONAMI\\ or its BOOTX64.EFI is missing, OSMETA.BIN already exists (valid or not) and --replace was not given, the file
cannot be placed contiguously and aligned, or no free directory slot exists in BOOTX64.EFI's block. --replace rewrites an existing
OSMETA.BIN in place only when it already has the guest's shape (20480 bytes, contiguous, aligned); it can lower or reset the floor, so it is
the operator's explicit act. Write order: file bytes, FAT copies, then the directory entry last; the result is read back and re-verified.
FSInfo's free-cluster count is reduced when present. STATE.BIN and UPDATE.BIN are never touched.
"""
import argparse
import hashlib
import os
import struct
import sys
import zlib

SIZE = 20480
ESP_GUID = bytes.fromhex("28732ac11ff8d211ba4b00a0c93ec93b")
MAX_VERSION = (1 << 63) - 1
BOOT = b"BOOTX64 EFI"
META = b"OSMETA  BIN"
DIRS = (b"EFI        ", b"ITONAMI    ")


class Refused(Exception):
    pass


def version_arg(text):
    try:
        n = int(text, 10)
    except ValueError:
        raise argparse.ArgumentTypeError("--version must be a positive decimal integer, got %r" % text)
    if not 1 <= n <= MAX_VERSION:
        raise argparse.ArgumentTypeError("--version must be in 1..2^63-1, got %d" % n)
    return n


def journal_bytes(version, image_digest):
    """OSMETA.BIN exactly as native/update_journal.kotoba `initialize 'floor version flags=0 digest'` followed by `publish 1` leaves it."""
    if not 1 <= version <= MAX_VERSION or len(image_digest) != 32 or image_digest == bytes(32):
        raise Refused("bad journal parameters")
    f = bytearray(SIZE)
    f[0:8] = b"OSUPMETA"
    struct.pack_into("<II", f, 8, 1, 128)
    slot = bytearray(512)
    struct.pack_into("<IIII", slot, 0, 0x534A534F, 1, 1, 0)      # "OSJS", schema 1, generation 1, policy flags 0
    struct.pack_into("<QQQ", slot, 24, version, version, 0)      # active, floor, candidate (phase 0 at 16, trial at 20: zero)
    slot[64:96] = image_digest
    slot[480:512] = hashlib.sha256(bytes(slot[:480])).digest()
    head = bytearray(512)
    struct.pack_into("<IIII", head, 0, 0x484A534F, 1, 1, 3)      # "OSJH", schema 1, generation 1, slot sector 2 + 1 % 2
    head[480:512] = slot[480:512]
    f[4096:4608] = head
    f[3 * 4096:3 * 4096 + 512] = slot
    return bytes(f)


def journal_state(data):
    """Return (floor, active) when `data` is a valid, published journal; raise ValueError otherwise (same rules as load + valid)."""
    if len(data) != SIZE:
        raise ValueError("size")
    if data[0:8] != b"OSUPMETA" or struct.unpack_from("<II", data, 8) != (1, 128) or any(data[16:512]):
        raise ValueError("marker")
    head = data[4096:4608]
    magic, schema, gen, sector = struct.unpack_from("<IIII", head, 0)
    if magic != 0x484A534F or schema != 1 or not 0 < gen <= 4294967294 or sector != 2 + gen % 2 or any(head[16:480]):
        raise ValueError("head")
    slot = data[sector * 4096:sector * 4096 + 512]
    if hashlib.sha256(slot[:480]).digest() != slot[480:512] or head[480:512] != slot[480:512]:
        raise ValueError("hash")
    magic, schema, g, flags, phase, trial = struct.unpack_from("<IIIIII", slot, 0)
    active, floor, cand = struct.unpack_from("<QQQ", slot, 24)
    ok = (magic == 0x534A534F and schema == 1 and g == gen and flags <= 7 and 0 < active <= MAX_VERSION and 0 < floor <= MAX_VERSION
          and floor >= active and not any(slot[48:64]) and any(slot[64:96]) and not any(slot[128:480]))
    if phase in (0, 3):
        ok = ok and cand == 0 and trial == 0 and not any(slot[96:128]) and (phase != 3 or floor > active)
    elif phase in (1, 2):
        ok = ok and 0 < cand <= MAX_VERSION and cand > active and cand == floor and trial == phase - 1 and any(slot[96:128])
    else:
        ok = False
    if not ok:
        raise ValueError("schema")
    return floor, active


class Disk:
    def __init__(self, f):
        self.f = f

    def read(self, off, n):
        self.f.seek(off)
        b = self.f.read(n)
        if len(b) != n:
            raise Refused("short read at %d" % off)
        return b

    def write(self, off, b):
        self.f.seek(off)
        self.f.write(b)


class Esp:
    """Read-only view of the ESP's FAT32 volume plus the plan for the one new file."""

    def __init__(self, disk, block):
        self.d = disk
        gpt = disk.read(block, 92)
        if gpt[:8] != b"EFI PART":
            raise Refused("no GPT header at LBA 1 (block size %d)" % block)
        hsize = struct.unpack_from("<I", gpt, 12)[0]
        if not 92 <= hsize <= block:
            raise Refused("GPT header size")
        hdr = bytearray(disk.read(block, hsize))
        crc = struct.unpack_from("<I", hdr, 16)[0]
        hdr[16:20] = bytes(4)
        if zlib.crc32(bytes(hdr)) != crc:
            raise Refused("GPT header CRC32 mismatch")
        lba, count, size, ecrc = struct.unpack_from("<QIII", hdr, 72)
        if size != 128 or not 1 <= count <= 128:
            raise Refused("GPT entry array shape")
        table = disk.read(lba * block, count * size)
        if zlib.crc32(table) != ecrc:
            raise Refused("GPT entry array CRC32 mismatch")
        found = [i for i in range(count) if table[i * size:i * size + 16] == ESP_GUID]
        if not found:
            raise Refused("no EFI System Partition in the GPT")
        first, last = struct.unpack_from("<QQ", table, found[0] * size + 32)
        self.base, self.end = first * block, (last + 1) * block
        self.block = block
        bpb = disk.read(self.base, 512)
        if bpb[82:90] != b"FAT32   " or bpb[510:512] != b"\x55\xaa":
            raise Refused("the ESP is not FAT32")
        self.bps, self.spc, self.reserved, self.nfats = struct.unpack_from("<HBHB", bpb, 11)
        total = struct.unpack_from("<I", bpb, 32)[0]
        self.fatsz = struct.unpack_from("<I", bpb, 36)[0]
        self.root = struct.unpack_from("<I", bpb, 44)[0]
        self.fsinfo = struct.unpack_from("<H", bpb, 48)[0]
        self.cs = self.bps * self.spc
        if self.bps < 512 or self.bps & (self.bps - 1) or self.spc == 0 or self.cs < block or self.cs & (self.cs - 1) or not 1 <= self.nfats <= 2:
            raise Refused("FAT32 geometry the guest does not accept (bytes/sector %d, sectors/cluster %d)" % (self.bps, self.spc))
        self.fat0 = self.base + self.reserved * self.bps
        self.data = self.fat0 + self.nfats * self.fatsz * self.bps
        self.limit = (total - self.reserved - self.nfats * self.fatsz) // self.spc + 2
        if self.base + total * self.bps > self.end or self.data + (self.limit - 2) * self.cs > self.end:
            raise Refused("the FAT32 volume does not lie inside the GPT's ESP")
        self.fat = [disk.read(self.fat0 + k * self.fatsz * self.bps, self.fatsz * self.bps) for k in range(self.nfats)]
        if any(c != self.fat[0] for c in self.fat):
            raise Refused("FAT copies differ; repair the volume first")

    def nxt(self, c):
        return struct.unpack_from("<I", self.fat[0], 4 * c)[0] & 0x0FFFFFFF

    def off(self, c):
        return self.data + (c - 2) * self.cs

    def chain(self, c):
        out = []
        while 2 <= c < 0x0FFFFFF7 and len(out) < 1 << 22:
            if c >= self.limit:
                raise Refused("cluster %d outside the volume" % c)
            out.append(c)
            c = self.nxt(c)
        if c < 0x0FFFFFF8:
            raise Refused("broken cluster chain")
        return out

    def entries(self, c):
        """[(offset, 32-byte entry)] of a directory in order up to (excluding) its end marker, plus the end-marker offset or None."""
        rows = []
        for cl in self.chain(c):
            raw = self.d.read(self.off(cl), self.cs)
            for p in range(0, self.cs, 32):
                e = raw[p:p + 32]
                if e[0] == 0:
                    return rows, self.off(cl) + p
                rows.append((self.off(cl) + p, e))
        return rows, None

    @staticmethod
    def find(rows, name):
        for off, e in rows:
            if e[0] != 0xE5 and e[11] != 0x0F and e[:11] == name:
                return off, e
        return None

    @staticmethod
    def first(e):
        return struct.unpack_from("<H", e, 26)[0] | struct.unpack_from("<H", e, 20)[0] << 16

    def read_file(self, e):
        size = struct.unpack_from("<I", e, 28)[0]
        data = b"".join(self.d.read(self.off(c), self.cs) for c in self.chain(self.first(e)))
        if len(data) < size:
            raise Refused("file shorter than its directory entry")
        return data[:size]


def provision(path, version, replace=False, block=512):
    """Plan, then write. Raises Refused before the first write. Returns dict(path, size, sha256, ...)."""
    if not isinstance(version, int) or isinstance(version, bool) or not 1 <= version <= MAX_VERSION:
        raise Refused("--version must be a positive integer below 2^63")
    with open(path, "r+b") as f:
        d = Disk(f)
        esp = Esp(d, block)
        rows, _ = esp.entries(esp.root)
        efi = esp.find(rows, DIRS[0])
        if efi is None:
            raise Refused("\\EFI is missing")
        rows, _ = esp.entries(esp.first(efi[1]))
        own = esp.find(rows, DIRS[1])
        if own is None:
            raise Refused("\\EFI\\ITONAMI is missing: this ESP was not installed by the native update path; nothing to provision into")
        dirc = esp.first(own[1])
        rows, end = esp.entries(dirc)
        boot = esp.find(rows, BOOT)
        if boot is None:
            raise Refused("\\EFI\\ITONAMI\\BOOTX64.EFI is missing: no active image to record a digest for")
        digest = hashlib.sha256(esp.read_file(boot[1])).digest()
        existing = esp.find(rows, META)
        journal = journal_bytes(version, digest)
        writes = []
        if existing is not None:
            off, e = existing
            if not replace:
                try:
                    floor, active = journal_state(esp.read_file(e)) if struct.unpack_from("<I", e, 28)[0] == SIZE else (None, None)
                    state = "a valid journal (floor %s)" % floor if floor is not None else "a file of the wrong size"
                except (ValueError, Refused):
                    state = "an invalid journal"
                raise Refused("\\EFI\\ITONAMI\\OSMETA.BIN already exists (%s); refusing to overwrite it; --replace is the explicit act that may lower or reset the floor" % state)
            ch = esp.chain(esp.first(e))
            if struct.unpack_from("<I", e, 28)[0] != SIZE or len(ch) != -(-SIZE // esp.cs) or ch != list(range(ch[0], ch[0] + len(ch))) or esp.off(ch[0]) % 4096 or e[11] & 31:
                raise Refused("existing OSMETA.BIN does not have the guest's shape (20480 bytes, contiguous, 4096-aligned): not replacing it in place")
            first_cluster = ch[0]
            writes.append((esp.off(first_cluster), journal))
            where = "replaced in place"
        else:
            start = boot[0] - boot[0] % esp.block
            known = {o: e for o, e in rows}
            slot = None
            for p in range(start, start + esp.block, 32):
                if p in known:
                    if known[p][0] == 0xE5:
                        slot = p
                        break
                else:
                    if p == end:
                        slot = p
                    break
            if slot is None:
                raise Refused("no free directory entry in BOOTX64.EFI's %d-byte block that the guest's directory scan would reach" % esp.block)
            need = -(-SIZE // esp.cs)
            first_cluster = None
            for c in range(2, esp.limit - need + 1):
                if esp.off(c) % 4096:
                    continue
                if esp.off(c) + SIZE > esp.end:
                    break
                if all(esp.nxt(c + i) == 0 for i in range(need)):
                    first_cluster = c
                    break
            if first_cluster is None:
                raise Refused("no contiguous run of %d free clusters whose first byte offset is 4096-aligned" % need)
            writes.append((esp.off(first_cluster), journal))
            for k in range(esp.nfats):
                for i in range(need):
                    c = first_cluster + i
                    old = struct.unpack_from("<I", esp.fat[k], 4 * c)[0]
                    new = 0x0FFFFFFF if i == need - 1 else c + 1
                    writes.append((esp.fat0 + k * esp.fatsz * esp.bps + 4 * c, struct.pack("<I", (old & 0xF0000000) | new)))
            entry = bytearray(32)
            entry[:11] = META
            entry[11] = 0x20
            struct.pack_into("<H", entry, 20, first_cluster >> 16)
            struct.pack_into("<H", entry, 26, first_cluster & 0xFFFF)
            struct.pack_into("<I", entry, 28, SIZE)
            if esp.fsinfo:
                fs = esp.base + esp.fsinfo * esp.bps
                info = d.read(fs, 512)
                if info[0:4] == b"RRaA" and info[484:488] == b"rrAa":
                    free = struct.unpack_from("<I", info, 488)[0]
                    if free != 0xFFFFFFFF and free >= need:
                        writes.append((fs + 488, struct.pack("<I", free - need)))
            writes.append((slot, bytes(entry)))
            where = "created"
        for off, b in writes:
            d.write(off, b)
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass
        # read back through the FAT and re-verify
        esp2 = Esp(d, block)
        rows, _ = esp2.entries(esp2.first(esp2.find(esp2.entries(esp2.root)[0], DIRS[0])[1]))
        rows, _ = esp2.entries(esp2.first(esp2.find(rows, DIRS[1])[1]))
        e = esp2.find(rows, META)[1]
        data = esp2.read_file(e)
        ch = esp2.chain(esp2.first(e))
        if data != journal or esp2.off(ch[0]) % 4096 or ch != list(range(ch[0], ch[0] + len(ch))) or journal_state(data) != (version, version):
            raise Refused("read-back verification failed after writing")
        return dict(path="\\EFI\\ITONAMI\\OSMETA.BIN", size=len(data), sha256=hashlib.sha256(data).hexdigest(), floor=version, active=version,
                    activeImageSha256=digest.hex(), firstCluster=first_cluster, diskOffset=esp2.off(ch[0]), action=where)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("disk")
    p.add_argument("--version", type=version_arg, required=True,
                   help="REQUIRED: the version of the image this board runs now (floor = active = N)")
    p.add_argument("--replace", action="store_true", help="rewrite an existing OSMETA.BIN in place (may lower or reset the floor)")
    p.add_argument("--block-size", type=int, choices=(512, 4096), default=512, help="the device's logical block size (GPT LBA unit)")
    a = p.parse_args(argv)
    try:
        r = provision(a.disk, a.version, a.replace, a.block_size)
    except Refused as e:
        print("REFUSED:", e, file=sys.stderr)
        return 2
    print("%s %d bytes sha256 %s (%s; floor = active = %d; active image sha256 %s; byte offset %d)" % (
        r["path"], r["size"], r["sha256"], r["action"], r["floor"], r["activeImageSha256"], r["diskOffset"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
