#!/usr/bin/env python3
"""Stage independent OCI test layouts for process/rootfs consistency."""
import argparse
import hashlib
import io
import json
import shutil
import tarfile
from pathlib import Path


def encode(value):
    return json.dumps(value, separators=(",", ":")).encode()


def tar(entries):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, mode, directory in entries:
            item = tarfile.TarInfo(name)
            item.mode, item.mtime, item.uid, item.gid = mode, 0, 0, 0
            if directory:
                item.type = tarfile.DIRTYPE
                archive.addfile(item)
            else:
                item.size = 1
                archive.addfile(item, io.BytesIO(b"x"))
    return out.getvalue()


def stage(root, layers, command, cwd):
    (root / "blobs/sha256").mkdir(parents=True, exist_ok=False)

    def blob(data):
        digest = hashlib.sha256(data).hexdigest()
        (root / "blobs/sha256" / digest).write_bytes(data)
        return "sha256:" + digest

    layer_values = [(blob(data), len(data)) for data in layers]
    process = command if isinstance(command, dict) else {"Entrypoint": [command], "Cmd": [], "Env": [], "WorkingDir": cwd}
    cfg = encode({"architecture": "arm64", "os": "linux",
                  "rootfs": {"type": "layers", "diff_ids": [d for d, _ in layer_values]}, "config": process})
    config_digest = blob(cfg)
    m = encode({"schemaVersion": 2, "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "config": {"mediaType": "application/vnd.oci.image.config.v1+json", "digest": config_digest, "size": len(cfg)},
                "layers": [{"mediaType": "application/vnd.oci.image.layer.v1.tar", "digest": d, "size": size}
                           for d, size in layer_values]})
    digest = blob(m)
    (root / "oci-layout").write_text('{"imageLayoutVersion":"1.0.0"}')
    (root / "index.json").write_bytes(encode({"schemaVersion": 2, "manifests": [
        {"mediaType": "application/vnd.oci.image.manifest.v1+json", "digest": digest, "size": len(m)}]}))
    return digest


def main(output):
    base = [("bin", 0o755, True), ("bin/run", 0o755, False)]
    cases = {"good": ([tar(base)], "/bin/run", "/bin"),
             "noexec": ([tar([base[0], ("bin/run", 0o644, False)])], "/bin/run", "/bin"),
             "missing": ([tar(base)], "/bin/missing", "/bin"),
             "badcwd": ([tar(base)], "/bin/run", "/missing"),
             "args": ([tar(base)], {"Entrypoint": ["/bin/run", "--x"], "Cmd": ["", "y"],
                                      "Env": ["A=1", "Z=雪"], "WorkingDir": "/bin"}, "/bin"),
             "args-big": ([tar(base)], {"Entrypoint": ["/bin/run", "x" * 9000], "Cmd": [],
                                          "Env": [], "WorkingDir": "/"}, "/"),
             "replaced": ([tar(base), tar([("bin/run", 0o644, False)])], "/bin/run", "/bin")}
    digests = {name: stage(output / name, *args) for name, args in cases.items()}
    shutil.copytree(output / "good", output / "corrupt")
    index = json.loads((output / "corrupt/index.json").read_bytes())
    manifest = json.loads((output / "corrupt/blobs/sha256" / index["manifests"][0]["digest"][7:]).read_bytes())
    path = output / "corrupt/blobs/sha256" / manifest["layers"][0]["digest"][7:]
    data = bytearray(path.read_bytes())
    assert data[1024] == ord("x")
    data[1024] = ord("y")
    path.write_bytes(data)
    digests["corrupt"] = digests["good"]
    print(json.dumps(digests, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    main(parser.parse_args().output)
