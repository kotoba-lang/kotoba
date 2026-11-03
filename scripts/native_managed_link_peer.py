"""Observe native managed frames through a loopback-only QEMU NIC.

Public crypto fixture bytes are independent of the guest. This is a test peer,
not an app/backend/runtime, service authorization oracle or deployment path.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import struct
import time

ROOT = Path(__file__).resolve().parents[1]

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def exercise(boot,peer,target,out,fault=None):
    link=load('managed_raw_peer',ROOT/'scripts/native_udp_link_peer.py')
    ref=load('managed_frame_data',ROOT/'lib/kotoba.kekkai/tools/frame_link_reference.py')
    _,cases=ref.fixtures(fault)
    low,high,other_low,other_high=struct.unpack('<4I',boot.dump(boot.work+400,16))
    owner,io=low+(high<<32),other_low+(other_high<<32)
    if not (0<owner<1<<39 and 0<io<1<<39 and (owner+262144<=io or io+262144<=owner)):
        raise ValueError('managed allocations overlap or are invalid')
    peer.settimeout(0.1);events=[];violations=[];pre_test=[]
    while True:
        try:
            data,address=peer.recvfrom(8192)
            if address!=target:raise ValueError('unexpected pre-test peer')
            pre_test.append(dict(hex=data.hex(),sha256=hashlib.sha256(data).hexdigest()))
        except socket.timeout:break
    for index,case in enumerate(cases):
        frame=bytearray(link.packet(case['payload'],ident=index+1))
        if case['label']=='wrong-endpoint':
            struct.pack_into('!H',frame,34,22090);link.fix_udp(frame)
        frame=bytes(frame)
        expected=[] if case['reply'] is None else [link.echoed(link.packet(case['reply'],ident=index+1))]
        before=link.snapshot(boot);state_before=boot.dump(owner,65536)
        peer.sendto(frame,target);replies=[];end=time.monotonic()+60
        while True:
            try:
                data,address=peer.recvfrom(8192)
                if address!=target:raise ValueError('unexpected peer')
                replies.append(data)
            except socket.timeout:pass
            now=link.snapshot(boot)
            if now[84]>index:
                try:
                    while True:
                        data,address=peer.recvfrom(8192)
                        if address!=target:raise ValueError('unexpected peer')
                        replies.append(data)
                except socket.timeout:pass
                break
            if boot.proc.poll() is not None:raise RuntimeError('native guest terminated')
            if time.monotonic()>end:raise TimeoutError('native NIC did not consume '+case['label'])
        actual_event,expected_event=struct.unpack('<qq',boot.dump(io+229376+index*16,16))
        state_after=boot.dump(owner,262144);output=boot.dump(io+73728,1472);work=boot.dump(io+147456,65536)
        wanted_output=case['reply'] if case['reply'] is not None else (case['output'] or b'')
        output_ok=output==wanted_output+bytes([165])*(1472-len(wanted_output))
        transactional=case['event']<0 and case['transition']==0
        same=not transactional or state_before==state_after[:65536]
        erased=state_after[65536:]==bytes(196608) and work==bytes(65536)
        phase,transitions=struct.unpack('<2I',boot.dump(boot.work+89*4,8))
        match=replies==expected
        checks=dict(wireMatches=match,outputMatches=output_ok,statePreserved=same,transientWiped=erased,
                    eventMatches=actual_event==expected_event==case['event'],phaseMatches=phase==case['phase'])
        for name,good in checks.items():
            if not good:violations.append(case['label']+': '+name)
        events.append(dict(label=case['label'],inputHex=frame.hex(),expectedReplyHex=[v.hex() for v in expected],
            actualReplyHex=[v.hex() for v in replies],event=actual_event,expectedEvent=case['event'],phase=phase,
            checks=checks,transactionalSnapshotChecked=transactional,transition=case['transition'],
            stateBeforeSHA256=hashlib.sha256(state_before).hexdigest(),stateAfterSHA256=hashlib.sha256(state_after[:65536]).hexdigest(),
            before={str(k):before[k] for k in [75,78,83,84]},after={str(k):now[k] for k in [75,78,83,84]}))
        (out/'packet-events.json').write_text(json.dumps(dict(preTestFrames=pre_test,events=events,violations=violations),indent=2)+'\n')
    if boot.W(79)!=2:raise RuntimeError('native final stop missing')
    final=link.snapshot(boot);state=boot.dump(owner,262144);work=boot.dump(io+147456,65536)
    (out/'native-managed-owner.bin').write_bytes(state);(out/'native-managed-work.bin').write_bytes(work)
    returns=boot.dump(io+229376,len(cases)*16);(out/'native-managed-events.bin').write_bytes(returns)
    pairs=list(struct.iter_unpack('<qq',returns))
    observed=dict(nicStarted=final[74],nativeErrors=final[75],wiped=final[76],canary=final[77],replies=final[78],terminal=final[79],
        rxFrames=final[83],released=final[84],rxErrors=final[87],transitions=transitions,
        sessionAndTransientWiped=state[32768:]==bytes(229376),ioWorkWiped=work==bytes(65536),eventPairsMatch=all(a==e for a,e in pairs),
        rosterVersion=struct.unpack_from('<Q',state,8)[0],rosterGeneration=struct.unpack_from('<Q',state,24)[0],shapeAndTransportGuards=boot.W(92),outerHeaderProbes=boot.W(93))
    wanted=dict(nicStarted=1,nativeErrors=0,wiped=1,canary=1,replies=sum(c['reply'] is not None for c in cases),terminal=2,
        rxFrames=len(cases),released=len(cases),rxErrors=0,transitions=2,sessionAndTransientWiped=True,ioWorkWiped=True,eventPairsMatch=True,
        rosterVersion=44,rosterGeneration=3,shapeAndTransportGuards=34,outerHeaderProbes=8)
    if observed!=wanted:violations.append('final counters or erasure differ')
    return dict(preTestFrames=pre_test,events=events,observed=observed,expected=wanted,violations=violations),not violations
