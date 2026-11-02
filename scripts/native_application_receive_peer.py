"""Observe real encrypted NIC ingress into the native reassembly owner.

Public deterministic test ciphertext only. No product runtime, consent,
service/policy evaluator, enrollment or external network access.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import struct
import time

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(raw): return hashlib.sha256(raw).hexdigest()


def exercise(boot, peer, target, out, small=False, initiator=False):
    link = load('receive_udp_public', ROOT/'scripts/native_udp_link_peer.py')
    ref = load('receive_public_cases', ROOT/'lib/kotoba.kekkai/tools/application_receive_reference.py')
    fixture, cases = ref.fixtures(small,initiator)
    addresses = struct.unpack('<8I', boot.dump(boot.work+400, 32))
    owner, io, log, pool = [addresses[i]+(addresses[i+1] << 32) for i in range(0,8,2)]
    allocations = [(owner,262144),(io,262144),(log,262144),(pool,8388608)]
    for i,(a,n) in enumerate(allocations):
        if not 0 < a < (1 << 39): raise ValueError('invalid allocation')
        if any(not (a+n <= b or b+m <= a) for b,m in allocations[i+1:]):
            raise ValueError('diagnostic allocations overlap')
    peer.settimeout(0.003)
    events, violations, pre_test = [], [], []
    while True:
        try:
            raw,address = peer.recvfrom(8192)
            if address != target: raise ValueError('unexpected pre-test peer')
            pre_test.append(dict(bytes=len(raw),sha256=digest(raw)))
        except socket.timeout: break
    for index,case in enumerate(cases):
        before_errors = boot.W(75)
        before_state = boot.dump(owner,65536) if case['preserve'] else None
        preserve_pool = case['preserve'] or case['label'] in ['part-count-change','invalid-completed-json']
        before_pool = boot.dump(pool,8388608) if preserve_pool else None
        frame = link.packet(case['payload'],ident=index+1)
        peer.sendto(frame,target)
        replies = []
        until = time.monotonic()+90
        while True:
            try:
                raw,address = peer.recvfrom(8192)
                if address != target: raise ValueError('unexpected test peer')
                replies.append(raw)
            except socket.timeout: pass
            if boot.W(84) > index:
                while True:
                    try:
                        raw,address = peer.recvfrom(8192)
                        if address != target: raise ValueError('unexpected test peer')
                        replies.append(raw)
                    except socket.timeout: break
                break
            if boot.proc.poll() is not None: raise RuntimeError('native guest terminated')
            if time.monotonic() >= until: raise TimeoutError('no native NIC consumption: '+case['label'])
        actual,expected = struct.unpack('<qq',boot.dump(log+index*16,16))
        header = boot.dump(pool,64)
        pending,buffered,completed = struct.unpack_from('<3I',header,8)
        expected_reply = [] if case['reply'] is None else [link.echoed(link.packet(case['reply'],ident=index+1))]
        checks = dict(status=actual==expected==case['status'],wire=replies==expected_reply,
            pending=pending==case['pending'],buffered=buffered==case['buffered'],
            completed=completed==(len(case['completed']) if case['completed'] is not None else 0),
            nativeAssertions=boot.W(75)==before_errors)
        item = dict(label=case['label'],inputBytes=len(frame),inputSHA256=digest(frame),
            actual=actual,expected=case['status'],checks=checks,
            replySHA256=[digest(x) for x in replies],expectedReplySHA256=[digest(x) for x in expected_reply],
            rawFrameAPIForUnobservedChannelTransition=bool(case['flags'] & 4),
            scheduledFirstSendTrigger=bool(case['flags'] & 16))
        if before_state is not None:
            after = boot.dump(owner,65536)
            checks['wholeSessionPreserved'] = after == before_state
            item['sessionBeforeSHA256'],item['sessionAfterSHA256'] = digest(before_state),digest(after)
        if before_pool is not None:
            after = boot.dump(pool,8388608)
            checks['wholePoolPreserved'] = after == before_pool
            item['poolBeforeSHA256'],item['poolAfterSHA256'] = digest(before_pool),digest(after)
        if case['completed'] is not None:
            raw = boot.dump(pool+6950912,len(case['completed']))
            checks['fullCompletedBytes'] = raw == case['completed']
            item['completedBytes'],item['completedSHA256'] = len(raw),digest(raw)
            if case['status'] == 2:
                copied = boot.dump(0x400000,65536)
                scratch = struct.unpack_from('<Q',copied,272)[0]
                # Existing owned-page2 follows the test scratch base.
                output = boot.dump(scratch+8192,4096)
                wanted = raw[:4096]+bytes([165])*max(0,4096-len(raw))
                checks['nativeCompletedCopyAndTail'] = output == wanted
        if case['control'] is not None and case['reply'] is None:
            raw = boot.dump(io+73728,len(case['control']))
            checks['typedControlPrefix'] = raw == case['control']
        if case['snapshot']:
            state = boot.dump(owner,262144)
            private = boot.dump(io+225280,12288)
            work = boot.dump(io+147456,65536)
            checks['sessionTransientZero'] = state[65536:] == bytes(196608)
            checks['privateCodecZero'] = private == bytes(12288)
            checks['frameWorkZero'] = work == bytes(65536)
            item['wholeSessionSHA256'] = digest(state)
            item['cookieHex'] = boot.dump(io+237568,128).hex()
        for name,ok in checks.items():
            if not ok: violations.append(case['label']+': '+name)
        events.append(item)
        if index % 32 == 0 or index+1 == len(cases):
            (out/'receive-events.json').write_text(json.dumps(dict(events=events,violations=violations),indent=2)+'\n')
            print('native receive',index+1,'/',len(cases),'errors',boot.W(75),'violations',len(violations),flush=True)
    until = time.monotonic()+30
    while boot.W(79) != 2:
        if boot.proc.poll() is not None or time.monotonic() >= until:
            raise TimeoutError('native final stop missing')
        time.sleep(.01)
    state,raw = boot.dump(owner,262144),boot.dump(pool,8388608)
    context = struct.unpack('<128I',boot.dump(boot.work,512))
    returns = boot.dump(log,len(cases)*16)
    (out/'native-receive-returns.bin').write_bytes(returns)
    pairs = list(struct.iter_unpack('<qq',returns))
    observed = dict(cases=len(cases),nativeErrors=context[75],terminal=context[79],nicStarted=context[74],
        rxFrames=context[83],released=context[84],rxErrors=context[87],replies=context[78],
        transitions=context[90],oldGuards=context[92],oldHeaderProbes=context[93],
        allEventPairsMatch=all(a==e for a,e in pairs),sessionAndTransientZero=state[32768:]==bytes(229376),
        finalPoolPending=struct.unpack_from('<I',raw,8)[0],finalPoolBuffered=struct.unpack_from('<I',raw,12)[0],
        finalPoolCompleted=struct.unpack_from('<I',raw,16)[0],finalPoolBodyZero=raw[4096:]==bytes(8384512),
        poolSHA256=digest(raw),fixtureSHA256=digest(fixture),managedRole='initiator' if initiator else 'responder',
        scheduledFirstSendTriggers=sum(bool(x['flags'] & 16) for x in cases),
        actualProtocolPackets=sum(not bool(x['flags'] & 16) for x in cases),
        actualBridgeReceiveCalls=sum(not bool(x['flags'] & 20) for x in cases))
    expected = dict(cases=len(cases),nativeErrors=0,terminal=2,nicStarted=1,
        rxFrames=len(cases),released=len(cases),rxErrors=0,replies=sum(x['reply'] is not None for x in cases),
        transitions=2,oldGuards=41,oldHeaderProbes=8,allEventPairsMatch=True,sessionAndTransientZero=True,
        finalPoolPending=0,finalPoolBuffered=0,finalPoolCompleted=0,finalPoolBodyZero=True)
    for key,value in expected.items():
        if observed[key] != value: violations.append('final: '+key)
    return dict(events=events,violations=violations,observed=observed,expected=expected,
        allocations=allocations,preTestFrames=pre_test,smallDevelopmentProbe=small),not violations
