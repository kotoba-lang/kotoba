#!/usr/bin/env python3
"""Stage an OCI fixture with 512 mutations and 128 final-mode operations.

This only stages independent test bytes. The native producer, worker and
supervisor still own validation, filesystem operations and the verdict.
"""
import argparse
import hashlib
import io
import json
import tarfile
from pathlib import Path


def stage(root):
    (root / "blobs/sha256").mkdir(parents=True, exist_ok=False)

    def blob(data):
        value = hashlib.sha256(data).hexdigest()
        (root / "blobs/sha256" / value).write_bytes(data)
        return "sha256:" + value

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for i in range(128):
            item = tarfile.TarInfo(f"f{i:03d}")
            item.size, item.mode, item.uid, item.gid, item.mtime = 0, 0o644, 0, 0, 0
            archive.addfile(item, io.BytesIO(b""))
    layer = buf.getvalue()
    layer_digest = blob(layer)
    encode = lambda obj: json.dumps(obj, separators=(",", ":")).encode()
    config = encode({"architecture": "arm64", "os": "linux",
                     "rootfs": {"type": "layers", "diff_ids": [layer_digest] * 4},
                     "config": {"Entrypoint": ["/f000"], "Cmd": [], "Env": [], "WorkingDir": "/"}})
    config_digest = blob(config)
    manifest = encode({"schemaVersion": 2, "mediaType": "application/vnd.oci.image.manifest.v1+json",
                       "config": {"mediaType": "application/vnd.oci.image.config.v1+json", "digest": config_digest,
                                  "size": len(config)},
                       "layers": [{"mediaType": "application/vnd.oci.image.layer.v1.tar", "digest": layer_digest,
                                   "size": len(layer)} for _ in range(4)]})
    digest = blob(manifest)
    (root / "oci-layout").write_text('{"imageLayoutVersion":"1.0.0"}')
    (root / "index.json").write_bytes(encode({"schemaVersion": 2, "manifests": [
        {"mediaType": "application/vnd.oci.image.manifest.v1+json", "digest": digest, "size": len(manifest)}]}))
    print(digest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    stage(parser.parse_args().output)
