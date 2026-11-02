#!/usr/bin/env python3
"""Stage independent, disposable OCI layout test inputs; do not decide verdicts."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

if len(sys.argv) not in (3, 4) or (len(sys.argv) == 4 and sys.argv[3] != '--resource-cases'):
    raise SystemExit('usage: stage_layout_fixtures.py SOURCE NEW_DEST [--resource-cases]')

source = Path(sys.argv[1])
base = Path(sys.argv[2])
base.mkdir(parents=True, exist_ok=False)
manifest = (source / 'good.manifest').read_bytes()
config = (source / 'good.config').read_bytes()
layer = (source / 'good.tar').read_bytes()
obj = json.loads(manifest)
md = hashlib.sha256(manifest).hexdigest()
cd = obj['config']['digest'].split(':', 1)[1]
ld = obj['layers'][0]['digest'].split(':', 1)[1]
def write_index(root, raw, digest_override=None, size_delta=0, duplicate=False):
    digest = digest_override or ('sha256:' + hashlib.sha256(raw).hexdigest())
    value = {'schemaVersion':2,'manifests':[{'mediaType':'application/vnd.oci.image.manifest.v1+json',
                                              'digest':digest,'size':len(raw) + size_delta}]}
    if duplicate:
        value['manifests'].append(dict(value['manifests'][0]))
    (root / 'index.json').write_text(json.dumps(value, separators=(',', ':')))

for case in ('good', 'tampered', 'bad-config', 'bad-marker', 'bad-index', 'bad-index-size', 'bad-index-duplicate', 'missing', 'symlink'):
    root = base / case
    blob = root / 'blobs' / 'sha256'
    blob.mkdir(parents=True)
    (root / 'oci-layout').write_text('{"imageLayoutVersion":"2.0.0"}' if case == 'bad-marker' else '{"imageLayoutVersion":"1.0.0"}')
    write_index(root, manifest, 'sha256:' + '0' * 64 if case == 'bad-index' else None,
                1 if case == 'bad-index-size' else 0, case == 'bad-index-duplicate')
    (blob / md).write_bytes(manifest)
    if case == 'bad-config':
        changed = bytearray(config)
        changed[-1] ^= 1
        (blob / cd).write_bytes(changed)
    else:
        (blob / cd).write_bytes(config)
    if case in ('good', 'bad-config', 'bad-marker', 'bad-index', 'bad-index-size', 'bad-index-duplicate'):
        (blob / ld).write_bytes(layer)
    elif case == 'tampered':
        data = bytearray(layer)
        data[-1] ^= 1
        (blob / ld).write_bytes(data)
    elif case == 'symlink':
        target = base / 'outside-blob'
        target.write_bytes(layer)
        (blob / ld).symlink_to('../../../outside-blob')

# A validly hashed layout whose archive contains a symlink. This must fail at
# archive policy, not at digest validation.
unsafe = base / 'unsafe-tar' / 'blobs' / 'sha256'
unsafe.mkdir(parents=True)
(base / 'unsafe-tar' / 'oci-layout').write_text('{"imageLayoutVersion":"1.0.0"}')
unsafe_manifest = (source / 'symlink.manifest').read_bytes()
unsafe_config = (source / 'symlink.config').read_bytes()
unsafe_layer = (source / 'symlink.tar').read_bytes()
write_index(base / 'unsafe-tar', unsafe_manifest)
unsafe_obj = json.loads(unsafe_manifest)
(unsafe / hashlib.sha256(unsafe_manifest).hexdigest()).write_bytes(unsafe_manifest)
(unsafe / unsafe_obj['config']['digest'].split(':', 1)[1]).write_bytes(unsafe_config)
(unsafe / unsafe_obj['layers'][0]['digest'].split(':', 1)[1]).write_bytes(unsafe_layer)

# Two distinct layers exercise complete manifest iteration rather than only
# checking the first descriptor.
other = (source / 'directory.tar').read_bytes()
other_digest = hashlib.sha256(other).hexdigest()
two_config_obj = json.loads(config)
two_config_obj['rootfs']['diff_ids'].append('sha256:' + other_digest)
two_config = json.dumps(two_config_obj, separators=(',', ':')).encode()
two_manifest_obj = json.loads(manifest)
two_manifest_obj['config']['digest'] = 'sha256:' + hashlib.sha256(two_config).hexdigest()
two_manifest_obj['config']['size'] = len(two_config)
two_manifest_obj['layers'].append({'mediaType':'application/vnd.oci.image.layer.v1.tar',
                                   'digest':'sha256:' + other_digest, 'size':len(other)})
two_manifest = json.dumps(two_manifest_obj, separators=(',', ':')).encode()
two = base / 'two-layers' / 'blobs' / 'sha256'
two.mkdir(parents=True)
(base / 'two-layers' / 'oci-layout').write_text('{"imageLayoutVersion":"1.0.0"}')
write_index(base / 'two-layers', two_manifest)
(two / hashlib.sha256(two_manifest).hexdigest()).write_bytes(two_manifest)
(two / hashlib.sha256(two_config).hexdigest()).write_bytes(two_config)
(two / ld).write_bytes(layer)
(two / other_digest).write_bytes(other)
bad_two = base / 'two-layers-bad'
shutil.copytree(base / 'two-layers', bad_two)
corrupted = bytearray(other)
corrupted[-1] ^= 1
(bad_two / 'blobs' / 'sha256' / other_digest).write_bytes(corrupted)
print('two-layers-manifest', 'sha256:' + hashlib.sha256(two_manifest).hexdigest())
print('unsafe-tar-manifest', 'sha256:' + hashlib.sha256(unsafe_manifest).hexdigest())
print('manifest', 'sha256:' + md)
print('config', 'sha256:' + cd)
print('layer', 'sha256:' + ld)

# Independent full-manifest planner fixtures. The order deliberately matters:
# the bounded planner requires an explicit directory before a child file.
def plan_layout(name, layers):
    root = base / name
    blobs = root / 'blobs' / 'sha256'
    blobs.mkdir(parents=True)
    (root / 'oci-layout').write_text('{"imageLayoutVersion":"1.0.0"}')
    layer_digests = [hashlib.sha256(data).hexdigest() for data in layers]
    plan_config_obj = json.loads(config)
    plan_config_obj['rootfs']['diff_ids'] = ['sha256:' + digest for digest in layer_digests]
    plan_config = json.dumps(plan_config_obj, separators=(',', ':')).encode()
    plan_manifest_obj = json.loads(manifest)
    plan_manifest_obj['config']['digest'] = 'sha256:' + hashlib.sha256(plan_config).hexdigest()
    plan_manifest_obj['config']['size'] = len(plan_config)
    plan_manifest_obj['layers'] = [
        {'mediaType':'application/vnd.oci.image.layer.v1.tar', 'digest':'sha256:' + digest, 'size':len(data)}
        for data, digest in zip(layers, layer_digests)]
    plan_manifest = json.dumps(plan_manifest_obj, separators=(',', ':')).encode()
    write_index(root, plan_manifest)
    (blobs / hashlib.sha256(plan_manifest).hexdigest()).write_bytes(plan_manifest)
    (blobs / hashlib.sha256(plan_config).hexdigest()).write_bytes(plan_config)
    for data, digest in zip(layers, layer_digests):
        (blobs / digest).write_bytes(data)
    digest = 'sha256:' + hashlib.sha256(plan_manifest).hexdigest()
    print(name + '-manifest', digest)
    return layer_digests

plan_digests = plan_layout('plan-good', [other, layer, (source / 'replacement.tar').read_bytes()])
binary_digests = plan_layout('plan-binary', [other, layer, (source / 'binary-replacement.tar').read_bytes()])
plan_layout('plan-binary-max', [other, layer, (source / 'max-replacement.tar').read_bytes()])
plan_layout('plan-parent-missing', [layer, other])
plan_layout('plan-duplicate', [other, (source / 'duplicate.tar').read_bytes()])
shutil.copytree(base / 'plan-good', base / 'plan-second-tampered')
bad_layer = bytearray(layer)
bad_layer[-1] ^= 1
(base / 'plan-second-tampered' / 'blobs' / 'sha256' / plan_digests[1]).write_bytes(bad_layer)
shutil.copytree(base / 'plan-good', base / 'plan-third-tampered')
bad_replacement = bytearray((source / 'replacement.tar').read_bytes())
bad_replacement[-1] ^= 1
(base / 'plan-third-tampered' / 'blobs' / 'sha256' / plan_digests[2]).write_bytes(bad_replacement)
shutil.copytree(base / 'plan-binary', base / 'plan-binary-third-tampered')
bad_binary = bytearray((source / 'binary-replacement.tar').read_bytes())
bad_binary[512] ^= 1
(base / 'plan-binary-third-tampered' / 'blobs' / 'sha256' / binary_digests[2]).write_bytes(bad_binary)

if len(sys.argv) == 4:
    # Sparse files exercise pre-read bounds without allocating their full size.
    for name, rel, size in (
        ('oversize-marker', 'oci-layout', 1025),
        ('oversize-index', 'index.json', 536870912),
        ('oversize-manifest', 'blobs/sha256/' + md, 536870912),
        ('oversize-config', 'blobs/sha256/' + cd, 536870912),
    ):
        target = base / name
        shutil.copytree(base / 'good', target)
        with (target / rel).open('r+b') as file:
            file.truncate(size)
        print(name, size)
    for name, rel, size in (('limit-marker', 'oci-layout', 1024),
                             ('limit-index', 'index.json', 1048576)):
        target = base / name
        shutil.copytree(base / 'good', target)
        file = target / rel
        data = file.read_bytes()
        file.write_bytes(data + b' ' * (size - len(data)))
        print(name, size)
    shutil.copytree(base / 'good', base / 'race-marker')
