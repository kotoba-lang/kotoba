#!/usr/bin/env python3
"""Stage pinned owner inputs within the caller's existing repository access."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
VARIABLES = {
    'capability-link-frame': 'AIUEOS_LINK_FRAME_SOURCE_PATH',
    'capability-dma-map': 'AIUEOS_DMA_MAP_SOURCE_PATH',
    'capability-mmio-map': 'AIUEOS_MMIO_MAP_SOURCE_PATH',
    'capability-net-transport': 'AIUEOS_NET_TRANSPORT_SOURCE_PATH',
    'org-ietf-tcp': 'AIUEOS_ORG_IETF_TCP_SOURCE_PATH',
}
manifest = json.loads((ROOT / 'os/aiueos/native/source-dependencies.json').read_text())
assert {d['repo'] for d in manifest['dependencies']} == set(VARIABLES)
product = ROOT / '.native-inputs/amu'
descriptor = json.loads((product / 'native-product.json').read_text())
image = (product / descriptor['entry']).read_bytes()
assert descriptor['image'] == dict(bytes=len(image), sha256=hashlib.sha256(image).hexdigest())
with open(os.environ['GITHUB_ENV'], 'a') as env:
    for dep in manifest['dependencies']:
        repo, commit = dep['repo'], dep['commit']
        assert re.fullmatch('[0-9a-f]{40}', commit)
        supplied = os.environ.get(VARIABLES[repo])
        if supplied:
            root = Path(supplied).resolve()
            assert root.is_relative_to(ROOT / '.native-inputs')
            for file, expected in dep['files'].items():
                raw = (root / str(Path(file).relative_to('kotoba'))).read_bytes()
                assert hashlib.sha256(raw).hexdigest() == expected
            env.write(f'{VARIABLES[repo]}={root}\n')
            continue
        assert repo != 'org-ietf-tcp', 'private TCP requires its pinned checkout in a private CI context'
        dest = ROOT / '.native-inputs' / repo
        subprocess.run(['git', 'init', '--quiet', str(dest)], check=True)
        subprocess.run(['git', '-C', str(dest), 'fetch', '--quiet', '--depth=1', '--no-tags',
                        f'https://github.com/kotoba-lang/{repo}.git', commit], check=True)
        subprocess.run(['git', '-C', str(dest), 'checkout', '--quiet', '--detach', 'FETCH_HEAD'], check=True)
        assert subprocess.check_output(['git', '-C', str(dest), 'rev-parse', 'HEAD'], text=True).strip() == commit
        env.write(f'{VARIABLES[repo]}={dest / "kotoba"}\n')
