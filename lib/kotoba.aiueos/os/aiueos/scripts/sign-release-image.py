#!/usr/bin/env python3
"""Sign a release build receipt (JUN-140 signed release pipeline).

The scheme is the one the machine already verifies:
RSASSA-PKCS1-v1_5 over SHA-256, 256-byte signatures (see
verify-release-signature.py and the in-kernel Kotoba RSA admission used for
the application catalog). The receipt binds the whole release: it carries the
disk image's sha256 and every artifact's sha256 (EFI/BOOT/BOOTX64.EFI,
EFI/AIUEOS/KERNEL.ELF, INITRD.IMG, AIUEOS-DATA.IMG), so one signature over
the receipt covers the release.

The caller keeps the private key: production keys stay offline (the split
src/aiueos/sbom.cljk documents). The qualification key lives beside the
qualification receipts; see os/aiueos/qualification/release-key/CUSTODY.md.

  sign-release-image.py --receipt aiueos-x86_64-build-receipt.json \
      --key release-signing-key.pem --out-dir OUT

Writes OUT/aiueos-x86_64-build-receipt.sig and prints
AIUEOS_RELEASE_SIGNED. Verify with:

  verify-release-signature.py --receipt R --signature R.sig \
      --public-key release-signing-key.pub
"""
import argparse
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--receipt", required=True)
    p.add_argument("--key", required=True)
    p.add_argument("--out-dir", required=True)
    a = p.parse_args()

    body = Path(a.receipt).read_bytes()
    key = serialization.load_pem_private_key(Path(a.key).read_bytes(), password=None)
    assert isinstance(key, rsa.RSAPrivateKey), "release signing policy requires RSA"
    signature = key.sign(body, padding.PKCS1v15(), hashes.SHA256())
    assert len(signature) == 256, "release signing policy requires RSA-2048"

    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "aiueos-x86_64-build-receipt.sig").write_bytes(signature)
    print("AIUEOS_RELEASE_SIGNED receipt=%s bytes=%d" % (Path(a.receipt).name, len(body)))


if __name__ == "__main__":
    main()
