"""Observe real encrypted NIC ingress into the native reassembly owner.

Public deterministic test ciphertext only. No product runtime, consent,
service/policy evaluator, enrollment or external network access.
"""
import base64
import gzip
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


def native_fragments(frames, keys, templates):
    chunks, wires, ident = [], [], None
    for index, raw in enumerate(frames):
        assert raw[12:14] == b'\x08\x00' and raw[23] == 17
        udp = 14 + (raw[14] & 15) * 4
        length = int.from_bytes(raw[udp+4:udp+6], 'big')
        wire = raw[udp+8:udp+length]
        assert wire[:3] == b'k\1\x32'
        counter = wire[3:11]
        assert int.from_bytes(counter, 'little') == index
        plain = keys['c'].open_(keys['outgoing'], bytes(4)+counter, counter, wire[11:])
        assert plain is not None and plain[:1] == b'\1'
        part = json.loads(plain[1:])
        assert set(part) == {'version', 'messageId', 'partIndex', 'partCount', 'payload'}
        assert part['version'] == 1 and part['partIndex'] == index and part['partCount'] == 1498
        if ident is None:
            ident = part['messageId']
            assert len(ident) == 64 and all(c in '0123456789abcdef' for c in ident)
        assert part['messageId'] == ident
        chunk = base64.b64decode(part['payload'], validate=True)
        assert len(chunk) == (700 if index < 1497 else 676)
        assert base64.b64encode(chunk).decode() == part['payload']
        chunks.append(chunk)
        wires.append(wire)
    message = b''.join(chunks)
    prefix = templates[0] + ident.encode() + templates[1][:-2]
    used = (1048576-len(prefix)-2)//4*4
    alphabet = b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
    body = (alphabet*((used+63)//64))[:used]
    expected = prefix + body + b'"}'
    expected += b' '*(1048576-len(expected))
    matches = len(message) == 1048576 and message == expected
    if matches:
        value = json.loads(message)
        assert value['requestId'] == ident
        assert base64.b64decode(value['bodyBase64'], validate=True) == base64.b64decode(body, validate=True)
    # 故障系も外側の認証済み messageId へ応答し、同じ全受信corpusを完走する。
    # 不一致は下の独立観測に残し、壊れた本文を製品入力として実行しない。
    return ident, message, wires, matches


def exercise(boot, peer, target, out, small=False, initiator=False):
    link = load('receive_udp_public', ROOT/'scripts/native_udp_link_peer.py')
    ref = load('receive_public_cases', ROOT/'lib/kotoba.kekkai/tools/application_response_reference.py')
    fixture, cases = ref.fixtures(small,initiator)
    keys=ref.protocol(fixture,initiator);native_request=None;full=None
    addresses = struct.unpack('<8I', boot.dump(boot.work+400, 32))
    owner, io, log, pool = [addresses[i]+(addresses[i+1] << 32) for i in range(0,8,2)]
    pending_owner=boot.W(114)+(boot.W(115)<<32)
    sender_owner=boot.W(120)+(boot.W(121)<<32)
    allocations = [(owner,262144),(io,262144),(log,262144),(pool,8388608),(pending_owner,262144),
                   (sender_owner,24576),(pool+8388608,1048576)]
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
        before_pending = boot.dump(pending_owner,262144) if case['preserve'] else None
        frame = link.packet(case['payload'],ident=index+1)
        peer.sendto(frame,target)
        replies = []
        until = time.monotonic()+(1200 if case.get('nativeRequest') else 90)
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
        if case.get('nativeRequest'):
            if len(replies)!=1498:raise ValueError('native fragments missing/duplicated: '+str(len(replies)))
            ident,message,wires,request_matches=native_fragments(replies,keys,ref.TEMPLATES)
            packed_frames=b''.join(struct.pack('<I',len(raw))+raw for raw in replies)
            (out/'native-client-fragments.bin.gz').write_bytes(gzip.compress(packed_frames,mtime=0))
            (out/'native-client-request-plaintext.bin.gz').write_bytes(gzip.compress(message,mtime=0))
            binding=struct.pack('<IIQI',0x3142504b,1,3,1)+bytes(4)+keys['peer']+bytes(8)+keys['h']
            expected_id=hashlib.blake2s(b'Kekkai pending v1'+binding+struct.pack('<2Q',pending_owner,1)).hexdigest()
            (out/'native-client-request.bin').write_bytes(replies[0])
            (out/'native-client-request-diagnostic.json').write_text(json.dumps(dict(actualID=ident,expectedID=expected_id,pendingOwner=pending_owner,bindingHex=binding.hex(),nativeErrors=boot.W(75)),indent=2)+'\n')
            if ident!=expected_id:raise ValueError('wire ID differs from independently derived actual binding/owner/sequence')
            raw=replies[0];ihl=(raw[14]&15)*4;udp=14+ihl;length=int.from_bytes(raw[udp+4:udp+6],'big');wire=raw[udp+8:udp+length]
            expected_reply=[link.echoed(link.packet(w,ident=index+1)) for w in wires]
            native_request=dict(requestId=ident,plaintextBytes=len(message),plaintextSHA256=digest(message),fragments=len(wires),allWireSHA256=digest(b''.join(wires)),wireBytes=len(wire),wireSHA256=digest(wire),actualOutboundFrameSHA256=digest(raw),idLearnedFrom='actual independently decrypted native outbound UDP frame',bindingHex=binding.hex())
            full=ref.bind_responses(cases,ident,fixture,initiator)

        checks = dict(status=actual==expected==case['status'],wire=replies==expected_reply,
            pending=pending==case['pending'],buffered=buffered==case['buffered'],
            completed=completed==(len(case['completed']) if case['completed'] is not None else 0),
            nativeAssertions=boot.W(75)==before_errors)
        if case.get('nativeRequest'):
            checks['fullOutgoingRequestBytes'] = request_matches
        item = dict(label=case['label'],inputBytes=len(frame),inputSHA256=digest(frame),
            actual=actual,expected=case['status'],checks=checks,
            replySHA256=[digest(x) for x in replies],expectedReplySHA256=[digest(x) for x in expected_reply],
            rawFrameAPIForUnobservedChannelTransition=bool(case['flags'] & 4),
            scheduledFirstSendTrigger=bool(case['flags'] & 16))
        if before_state is not None:
            after = boot.dump(owner,65536)
            checks['wholeSessionPreserved'] = after == before_state
            item['sessionBeforeSHA256'],item['sessionAfterSHA256'] = digest(before_state),digest(after)
        if before_pending is not None:
            checks['wholePendingPreserved']=boot.dump(pending_owner,262144)==before_pending
        if before_pool is not None:
            after = boot.dump(pool,8388608)
            checks['wholePoolPreserved'] = after == before_pool
            item['poolBeforeSHA256'],item['poolAfterSHA256'] = digest(before_pool),digest(after)
        if case['completed'] is not None:
            raw = boot.dump(pool+6950912,len(case['completed']))
            checks['fullCompletedBytes'] = raw == case['completed']
            if len(raw)==1048576:
                checks['actualCompletionChannel']=native_request is not None and boot.dump(pool+1152,96)==bytes.fromhex(native_request['bindingHex'])
                record=bytearray(512);struct.pack_into('<II3Q',record,0,0x3141504b,1,1,1750000000000,1750000030000)
                record[32:128]=bytes.fromhex(native_request['bindingHex']);record[128:160]=bytes.fromhex(native_request['requestId']);struct.pack_into('<3I',record,160,10,3,5)
                for tag,text,at in [(3,b'local-docs',176),(4,b'GET',208),(5,b'/docs',240)]:record[at:at+32]=hashlib.blake2s(bytes([tag])+text).digest()
                struct.pack_into('<4I',record,272,8080,200,1048576,0);struct.pack_into('<Q',record,288,pool+6950912)
                checks['exactAcceptedContext']=boot.dump(io+246000,512)==bytes(record)
                checks['pinnedAcceptedInput']=struct.unpack_from('<Q',boot.dump(pending_owner+56,8))[0]==1

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
    final_pending=boot.dump(pending_owner,262144)
    sender=boot.W(120)+(boot.W(121)<<32)
    private=boot.dump(0x400000,65536);app,total,ready=struct.unpack_from('<3Q',private,33536)
    assert total==9437184 and ready==0x324d5041
    sender_zero=boot.dump(sender,24576)==bytes(24576)
    tx_zero=boot.dump(app+8388608,1048576)==bytes(1048576)
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
    observed.update(senderFullyZero=sender_zero,transmitFullyZero=tx_zero,controllerGuards=boot.W(119),nativeRequests=boot.W(116),matchedResponses=boot.W(117),matchingReleases=boot.W(118),pendingOwnerFullyZero=final_pending==bytes(262144))
    expected = dict(senderFullyZero=True,transmitFullyZero=True,controllerGuards=15,nativeRequests=1,matchedResponses=1,matchingReleases=1,pendingOwnerFullyZero=True,cases=len(cases),nativeErrors=0,terminal=2,nicStarted=1,
        rxFrames=len(cases),released=len(cases),rxErrors=0,replies=sum(x['reply'] is not None for x in cases)+1498,
        transitions=2,oldGuards=41,oldHeaderProbes=8,allEventPairsMatch=True,sessionAndTransientZero=True,
        finalPoolPending=0,finalPoolBuffered=0,finalPoolCompleted=0,finalPoolBodyZero=True)
    for key,value in expected.items():
        if observed[key] != value: violations.append('final: '+key)
    return dict(events=events,violations=violations,observed=observed,expected=expected,
        allocations=allocations,preTestFrames=pre_test,smallDevelopmentProbe=small,nativeRequest=native_request,fullResponseBytes=len(full) if full else 0,fullResponseSHA256=digest(full) if full else None),not violations
