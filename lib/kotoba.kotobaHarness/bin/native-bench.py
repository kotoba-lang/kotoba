#!/usr/bin/env python3
"""Stage experiment inputs; the native benchmark owns order and total budget."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_transport', ROOT / 'bin/native-transport.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('rounds', nargs='?', type=int, default=5)
    parser.add_argument('output', nargs='?', type=Path, default=ROOT / 'runs/native-bench')
    parser.add_argument('--amu', default=os.environ.get('KOTOBA_AMU_ROOT'))
    parser.add_argument('--budget-usd', type=float, required=True)
    args = parser.parse_args()
    key = os.environ.pop('OPENROUTER_API_KEY', None)
    if not args.amu or not key or not 0 < args.budget_usd <= 0.05:
        raise t.Blocked('explicit pinned --amu, OPENROUTER_API_KEY and --budget-usd (0 < budget <= 0.05) are required')
    args.output.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix='bench-', dir=args.output.resolve()))
    native = t.Native(args.amu, output)
    native.builds = {'main': native.build()}
    build = native.build('bench')
    config = {'projects': [(ROOT / 'projects' / variant / (name + '.edn')).read_text()
                           for variant in ('', 'plain') for name in ('kotoba', 'itonami', 'murakumo')],
              'date': datetime.now(timezone.utc).isoformat(), 'native-route': native.pin,
              'rounds': args.rounds, 'budget-usd': args.budget_usd}
    code, receipt = t.execute(native, build, config, key)
    print(json.dumps(receipt))
    print(json.dumps(dict(receipt=str(output / 'receipt.json'))))
    return code

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (t.Blocked, OSError, ValueError, KeyError, t.subprocess.SubprocessError) as error:
        print(json.dumps(dict(status='blocked', error=str(error))), file=sys.stderr)
        sys.exit(78)
