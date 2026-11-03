#!/usr/bin/env python3
"""Build the source-locked synthetic fleet fixture with an explicit Amu root.

Usage: python3 scripts/build-fleet-cross-host.py AMU_DIR NEW_OUTPUT_DIR EXPECTED_COMPILER_SHA256
The artifact is test-only and must never be used with real fleet keys.
"""
import hashlib, importlib.util, json, sys
from pathlib import Path
if len(sys.argv) != 4: raise SystemExit(__doc__)
amu, out = map(lambda p: Path(p).resolve(), sys.argv[1:3])
expected = sys.argv[3]
repo = Path(__file__).resolve().parents[1]
out.mkdir(parents=True, exist_ok=False)
sha = lambda data: hashlib.sha256(data).hexdigest()
compiler = amu/'seed/bootstrap/aarch64-macos/amu-full-root.macho'
if sha(compiler.read_bytes()) != expected: raise ValueError('compiler mismatch')
spec=importlib.util.spec_from_file_location('pq',repo/'scripts/check-pq-native.py');pq=importlib.util.module_from_spec(spec);spec.loader.exec_module(pq)
paths=dict(pq.TCP_DEMO['files'])
paths.update({'kagami/fleet_noise_handshake.kotoba':'lib/kotoba.kagami/src/kagami/fleet_noise_handshake.kotoba',
 'kagami/fleet_noise_native.kotoba':'lib/kotoba.kagami/src/kagami/fleet_noise_native.kotoba',
 'kagami/fleet_tcp_native.kotoba':'lib/kotoba.kagami/src/kagami/fleet_tcp_native.kotoba',
 'kagami/fleet_announce_edn.kotoba':'lib/kotoba.kagami/src/kagami/fleet_announce_edn.kotoba',
 'kagami/fleet_store_native.kotoba':'lib/kotoba.kagami/src/kagami/fleet_store_native.kotoba',
 'kagami/fleet_native.kotoba':'lib/kotoba.kagami/src/kagami/fleet_native.kotoba',
 'hata/store_io.kotoba':'lib/kotoba.hata/src/hata/store_io.kotoba',
 'hata/codec.kotoba':'lib/kotoba.hata/src/hata/codec.kotoba',
 'kotoba_harness/data.kotoba':'lib/kotoba.kotobaHarness/src/kotoba_harness/data.kotoba'})
original={k:(repo/v).read_bytes() for k,v in paths.items()}
driver=(repo/'lib/kotoba.kagami/test/kagami/fleet_noise_duplex_driver.kotoba').read_bytes()
base=original['noise/tcp_demo.kotoba'];ns=b'(:require [noise.native :as n] [noise.identity :as id] [noise.tcp :as t])'
if base.count(ns)!=1 or base.count(b'(defn main [] :i64')!=1:raise ValueError('fixture changed')
base=base[:base.index(b'(defn main [] :i64')].replace(ns,ns[:-1]+b' [kagami.fleet-noise-native :as fleet] [kagami.fleet-noise-handshake :as hs] [hata.store-io :as io])\n  (:capabilities [:cli/args])')+driver
sources=dict(original);sources['noise/tcp_demo.kotoba']=base
for name,data in sources.items():
 path=out/'src'/name
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_bytes(data)
lock=out/'sources.ksl'
lock.write_text('KSL1\nentry /src/noise/tcp_demo.kotoba\nroot /src\n'+''.join(f'file {sha(data)} /src/{name}\n' for name,data in sorted(sources.items())))
spec=importlib.util.spec_from_file_location('mac',amu/'scripts/seed/check-aiueos-user-macos-native.py')
mac=importlib.util.module_from_spec(spec);spec.loader.exec_module(mac)
mac.native_run(compiler,out,'compile','/src/noise/tcp_demo.kotoba','--target','aarch64-macos','--output','guest.kseed','--source-path','/src','--source-lock','sources.ksl','--source-lock-sha256',sha(lock.read_bytes()))
runner=(amu/'seed/x86_64-kx64-runner.kotoba').read_bytes()
(out/'runner.kotoba').write_bytes(runner)
mac.native_run(compiler,out,'compile','runner.kotoba','--target','aarch64-linux','--output','runner-arm.elf','--format','packed','--payload','guest.kseed')
(out/'runner-arm.elf').chmod(0o755)
evidence={'compilerSha256':sha(compiler.read_bytes()),'sourceLockSha256':sha(lock.read_bytes()),'driverSha256':sha(driver),'runnerSourceSha256':sha(runner),'sources':{name:sha(data) for name,data in sorted(original.items())},'artifacts':{name:sha((out/name).read_bytes()) for name in ('guest.kseed','runner-arm.elf')}}
(out/'build.json').write_text(json.dumps(evidence,indent=2)+'\n')
print('PASS_FLEET_CROSS_HOST_BUILD',flush=True)
