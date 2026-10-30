#!/usr/bin/env python3
"""Build and run kotoba/noise/tcp_demo.kotoba on Linux arm64, with its grant controls.

Dev tool, not part of the library. Standard library only. Run it inside a Linux arm64
environment (on a Mac: the podman machine), with the repository and Amu's committed
seed/bootstrap/aarch64-linux-static-root.elf and seed/x86_64-kx64-runner.kotoba mounted:

    podman run --rm --platform linux/arm64 --network none \\
      -v REPO:/repo -v AMU:/amu -v OUT:/out python:3.12-slim \\
      python3 /repo/lib/kotoba.noise/tools/run_tcp_demo.py \\
        --compiler /amu/seed/bootstrap/aarch64-linux-static-root.elf \\
        --runner-source /amu/seed/x86_64-kx64-runner.kotoba --output /out/tcp-demo

The image listens, dials and accepts on 127.0.0.1:47011 inside one process; nothing
leaves the loopback interface (--network none). scripts/check-pq-native.py runs the same
build on the CI arm64 lane.
"""
import argparse
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('check_pq_native', ROOT / 'scripts' / 'check-pq-native.py')
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler', type=Path, required=True)
    p.add_argument('--runner-source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    import hashlib
    a.compiler_sha256 = hashlib.sha256(a.compiler.read_bytes()).hexdigest()
    gate = C.LinuxArm(a)
    image = gate.build('tcp-demo', C.TCP_DEMO['entry'], C.module_files(C.TCP_DEMO))
    gate.run('tcp-demo-run', image, C.TCP_DEMO['passing'], C.NET_GRANT)
    for label, grants in C.TCP_DEMO['controls'].items():
        try:
            gate.run(f'tcp-demo-{label}', image, C.TCP_DEMO['passing'], grants)
            sys.exit(f'{label}: the demo ran without that grant')
        except AssertionError:
            print(label, 'refused', flush=True)
    gate.finish('PASS_NATIVE_TCP_DEMO')

if __name__ == '__main__':
    main()
