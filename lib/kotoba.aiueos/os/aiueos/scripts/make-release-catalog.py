#!/usr/bin/env python3
"""Emit the static release catalog (and SHA256SUMS) for a signed OS bundle.

Reads a bundle directory produced by build-os-release-bundle.sh -- the flat
set of <asset-base>-x86_64.iso / -gpt.img / -build-receipt.json / .sig files
-- and writes the machine-readable download metadata a static site serves.
The catalog is DERIVED from the signed release receipts; it is not an
authority of its own (AWAI-92: the static download catalog is composed from
the existing signed release authority, no new signing rule).

Fail closed: every receipt signature is verified against the given public key
before the catalog is written, and every artifact digest is recomputed from
the bytes on disk. A tampered bundle produces no catalog.

  make-release-catalog.py --release-dir OUT \
      --distributions-dir /path/to/kotoba-lang/aiueos/distributions \
      --public-key release-signing-key.pub \
      --signing-note "qualification key; QEMU/OVMF evidence only" \
      --download-base-url https://github.com/kotoba-lang/aiueos/releases/download/os-20261027 \
      --source kotoba=<sha> --source aiueos=<sha> \
      --out OUT/release-catalog.json
"""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def artifact(entry, kind, download_base):
    path = Path(entry)
    return {"file": path.name, "kind": kind,
            "bytes": path.stat().st_size, "sha256": sha256(path),
            "url": "%s/%s" % (download_base.rstrip("/"), path.name)}


def verify_signature(receipt, signature, public_key):
    subprocess.run(
        [sys.executable, str(HERE / "verify-release-signature.py"),
         "--receipt", str(receipt), "--signature", str(signature),
         "--public-key", str(public_key)],
        check=True, capture_output=True, text=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--release-dir", required=True)
    p.add_argument("--distributions-dir", required=True)
    p.add_argument("--public-key", required=True)
    p.add_argument("--signing-note", required=True,
                   help="what this signer is (custody level, evidence scope)")
    p.add_argument("--download-base-url", required=True,
                   help="immutable URL prefix the assets are published under")
    p.add_argument("--source", action="append", default=[],
                   help="name=sha for each source revision the bundle is built from")
    p.add_argument("--out", required=True)
    p.add_argument("--sha256sums", default=None,
                   help="also write a SHA256SUMS file (default: <release-dir>/SHA256SUMS)")
    args = p.parse_args()

    release = Path(args.release_dir)
    distributions_dir = Path(args.distributions_dir)
    sources = {}
    for item in args.source:
        name, _, value = item.partition("=")
        if not name or not value:
            p.error("--source wants name=sha, got %r" % item)
        sources[name] = value

    receipts = sorted(release.glob("*-build-receipt.json"))
    if not receipts:
        p.error("no *-build-receipt.json in %s" % release)

    entries = []
    for receipt_path in receipts:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("schema") != "aiueos.build-receipt.v1":
            p.error("%s: not an aiueos.build-receipt.v1" % receipt_path)
        distribution = receipt.get("distribution")
        if not distribution:
            p.error("%s: receipt binds no distribution" % receipt_path)
        base = receipt_path.name[: -len("-build-receipt.json")]
        descriptor_path = distributions_dir / distribution["id"] / "distribution.json"
        descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
        if descriptor.get("name") != distribution["name"]:
            p.error("%s: descriptor name drifted from the signed receipt" % descriptor_path)
        if sha256(descriptor_path) != distribution["descriptor"]["sha256"]:
            p.error("%s: descriptor bytes drifted from the signed receipt" % descriptor_path)

        signature_path = receipt_path.with_suffix(".sig")
        verify_signature(receipt_path, signature_path, args.public_key)

        def expect(path, kind, recorded):
            want = recorded["sha256"]
            got = sha256(path)
            if got != want:
                p.error("%s: digest %s does not match the signed receipt" % (path, got))
            return artifact(path, kind, args.download_base_url)

        artifacts = []
        artifacts.append(expect(release / ("%s.iso" % base), "iso", receipt["iso"]))
        artifacts.append(expect(release / ("%s-gpt.img" % base), "disk", receipt["disk"]))
        artifacts.append(artifact(receipt_path, "build-receipt", args.download_base_url))
        artifacts.append(artifact(signature_path, "build-receipt-signature", args.download_base_url))

        entries.append({
            "id": distribution["id"],
            "name": distribution["name"],
            "assetBase": base,
            "configurationOwner": distribution["configurationOwner"],
            "source": dict(sources),
            "artifacts": artifacts,
            "signature": {
                "scheme": "RSASSA-PKCS1-v1_5-SHA256",
                "covers": "the build receipt (disk + every artifact digest)",
                "keyFile": Path(args.public_key).name,
                "note": args.signing_note,
            },
            "admission": "receipt signature verified against the published public key; "
                         "artifact digests recomputed from the published bytes",
            "qualification": "boot and install evidence is QEMU/OVMF only; real-machine "
                             "boot, hardware support and continuous operation are not "
                             "qualified by this release",
            "notProvided": [
                "signed production release (production key stays offline)",
                "real-machine install certification",
                "node enrollment, Cell membership or any external service right",
            ],
        })

    catalog = {
        "schema": "aiueos.release-catalog.v1",
        "created": datetime.fromtimestamp(
            int(__import__("os").environ.get("SOURCE_DATE_EPOCH", "0")),
            timezone.utc).isoformat().replace("+00:00", "Z"),
        "downloadBaseUrl": args.download_base_url.rstrip("/"),
        "distributions": entries,
    }
    out = Path(args.out)
    out.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    sums_path = Path(args.sha256sums) if args.sha256sums else release / "SHA256SUMS"
    lines = []
    for entry in entries:
        for a in entry["artifacts"]:
            lines.append("%s  %s" % (a["sha256"], a["file"]))
    lines.append("%s  %s" % (sha256(out), out.name))
    sums_path.write_text("\n".join(sorted(lines, key=lambda line: line.split("  ", 1)[1])) + "\n",
                         encoding="utf-8")
    print("AIUEOS_RELEASE_CATALOG_OK distributions=%d %s" % (len(entries), out))


if __name__ == "__main__":
    main()
