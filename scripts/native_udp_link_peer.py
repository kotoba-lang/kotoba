"""Public raw-frame oracle for an isolated QEMU NIC, never an app backend.

Only127.0.0.1 UDP sockets are used. Native guest code owns NIC DMA, admission
and replies; Python constructs/checks independent public Ethernet/IP/UDP data.
"""
import hashlib
import socket
import struct
import time

MAC_GUEST = bytes.fromhex('525400123456')
MAC_PEER = bytes.fromhex('020000000001')
IP_PEER = bytes([10,77,0,1])
IP_GUEST = bytes([10,77,0,2])

def checksum(data):
    if len(data) % 2:
        data += b'\0'
    total = sum(struct.unpack('!%dH' % (len(data)//2), data))
    while total >> 16:
        total = (total & 65535) + (total >> 16)
    return (~total) & 65535

def packet(payload, options=b'', zero=False, flags=0, ident=1):
    assert len(options) % 4 == 0 and len(options) <= 40
    hlen = 20 + len(options)
    udp = bytearray(struct.pack('!HHHH',22088,22089,8+len(payload),0)+payload)
    pseudo = IP_PEER+IP_GUEST+bytes([0,17])+struct.pack('!H',len(udp))
    struct.pack_into('!H',udp,6,0 if zero else checksum(pseudo+udp) or 65535)
    ip = bytearray(struct.pack('!BBHHHBBH',0x40+hlen//4,0,hlen+len(udp),ident,flags,64,17,0)+IP_PEER+IP_GUEST+options)
    struct.pack_into('!H',ip,10,checksum(ip))
    return (MAC_GUEST+MAC_PEER+bytes.fromhex('0800')+ip+udp).ljust(60,b'\0')

def fix_ip(data):
    hlen = (data[14] & 15)*4
    data[24:26] = b'\0\0'
    struct.pack_into('!H',data,24,checksum(bytes(data[14:14+hlen])))

def fix_udp(data):
    hlen = (data[14] & 15)*4
    size = struct.unpack_from('!H',data,16)[0]-hlen
    off = 14+hlen
    data[off+6:off+8] = b'\0\0'
    pseudo = bytes(data[26:34])+bytes([0,17])+struct.pack('!H',size)
    struct.pack_into('!H',data,off+6,checksum(pseudo+bytes(data[off:off+size])) or 65535)

def invalid_frames():
    original = packet(bytes((i*17+3)%256 for i in range(31)),ident=7)
    changes = [
        ('ether-type',12,b'\x86\xdd',False,False),('version',14,b'\x65',True,False),
        ('ihl-short',14,b'\x44',False,False),('ihl-truncated',14,b'\x4f',False,False),
        ('total-short',16,struct.pack('!H',27),True,False),('total-truncated',16,struct.pack('!H',1500),True,False),
        ('ttl-zero',22,b'\0',True,False),('more-fragments',20,b'\x20\0',True,False),
        ('fragment-offset',20,b'\0\1',True,False),('reserved-flag',20,b'\x80\0',True,False),
        ('protocol',23,b'\6',True,False),('ip-checksum',18,b'\x55\x66',False,False),
        ('udp-short',38,b'\0\7',False,False),('udp-length',38,b'\0\x28',False,False),
        ('udp-checksum',40,b'\x12\x34',False,False),('udp-body',42,b'\x77',False,False),
        ('source-port',34,struct.pack('!H',22087),False,True),('destination-port',36,struct.pack('!H',22090),False,True),
        ('source-ip',29,b'\3',True,True),('destination-ip',33,b'\3',True,True),
        ('source-mac',11,b'\x99',False,False),
    ]
    out = []
    for label,at,value,ip,udp in changes:
        frame = bytearray(original)
        frame[at:at+len(value)] = value
        if ip: fix_ip(frame)
        if udp: fix_udp(frame)
        out.append((label,bytes(frame)))
    return out

def valid_frames():
    sizes = [0,1,31,64,1280,1472]
    frames = [(f'payload-{n}',packet(bytes((i*17+n)%256 for i in range(n)),ident=100+j)) for j,n in enumerate(sizes)]
    frames += [('options-4',packet(bytes(range(17)),bytes([1])*4,ident=110)),
               ('options-40',packet(bytes(range(17)),bytes([1])*40,ident=111)),
               ('udp-zero',packet(bytes(range(13)),zero=True,ident=112)),
               ('dont-fragment',packet(bytes(range(33)),flags=0x4000,ident=113))]
    assert len(frames) == 10
    return frames

def echoed(frame):
    out = bytearray(frame)
    hlen = (frame[14]&15)*4
    off = 14+hlen
    out[:12] = frame[6:12]+frame[:6]
    out[26:34] = frame[30:34]+frame[26:30]
    out[off:off+4] = frame[off+2:off+4]+frame[off:off+2]
    return bytes(out)

def snapshot(boot):
    values = struct.unpack('<15I',boot.dump(boot.work+74*4,60))
    return dict(zip(range(74,89),values))

def exercise(boot, peer, target, output):
    events = []
    violations = []
    peer.settimeout(0.1)
    # The NIC's firmware may have transmitted before the OS entry reset it.
    # Retain every queued pre-test frame; never attribute it to a later probe.
    pre_test = []
    while True:
        try:
            data,address = peer.recvfrom(8192)
            if address != target: raise ValueError('unexpected pre-test peer')
            pre_test.append(dict(bytes=len(data),hex=data.hex(),sha256=hashlib.sha256(data).hexdigest()))
        except socket.timeout:
            break
    for invalid, cases in [(True,invalid_frames()),(False,valid_frames())]:
        for label,frame in cases:
            before = snapshot(boot)
            if before[79] == 2:
                violations.append('guest finished before '+label)
                break
            peer.sendto(frame,target)
            replies = []
            end = time.monotonic()+10
            while True:
                try:
                    data, address = peer.recvfrom(8192)
                    if address != target: raise ValueError('unexpected non-QEMU peer')
                    replies.append(data)
                except socket.timeout:
                    pass
                now = snapshot(boot)
                if now[84] > before[84] or now[79] == 2:
                    # ACK is published only after the descriptor is reposted.
                    try:
                        while True:
                            data,address = peer.recvfrom(8192)
                            if address != target: raise ValueError('unexpected non-QEMU peer')
                            replies.append(data)
                    except socket.timeout:
                        pass
                    break
                if boot.proc.poll() is not None: raise RuntimeError('link guest terminated')
                if time.monotonic() > end: raise TimeoutError('NIC did not consume '+label)
            expected = [] if invalid else [echoed(frame)]
            match = replies == expected
            if not match: violations.append(label+' reply mismatch')
            if invalid and now[88] != before[88]+1: violations.append(label+' was not refused')
            if not invalid and now[78] != before[78]+1: violations.append(label+' was not transmitted')
            events.append(dict(label=label,invalid=invalid,inputBytes=len(frame),inputSHA256=hashlib.sha256(frame).hexdigest(),
                replyBytes=[len(x) for x in replies],replySHA256=[hashlib.sha256(x).hexdigest() for x in replies],
                expectedReplySHA256=[hashlib.sha256(x).hexdigest() for x in expected],match=match,
                before={str(k):before[k] for k in [78,83,84,87,88]},after={str(k):now[k] for k in [78,83,84,87,88]}))
    final = snapshot(boot)
    if final[79] != 2: raise AssertionError('link guest did not finish')
    return dict(preTestFrames=pre_test,events=events,violations=violations,observed=dict(nicStarted=final[74],nativeErrors=final[75],completed=final[76],canary=final[77],
        accepted=final[78],terminal=final[79],rxFrames=final[83],released=final[84],rxErrors=final[87],refused=final[88])),not violations and [final[k] for k in [74,75,76,77,78,79,83,84,87,88]] == [1,0,1,1,10,2,31,31,0,21]
