#!/usr/bin/env python3
"""Observe native effects/PCM through private QMP; never implement the effects."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import time
import wave

HERE = Path(__file__).resolve().parent

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

transport = load('effects_transport', HERE / 'check-native-draft-restart-qemu.py')
desktop = load('effects_pixels', HERE / 'check-native-desktop-qemu.py')

def pin(path):
    b = path.read_bytes()
    return dict(bytes=len(b), sha256=hashlib.sha256(b).hexdigest())

def main(args):
    if not __debug__:
        raise RuntimeError('assertions must be enabled')
    for name in ('media', 'kernel', 'efi', 'font', 'qemu', 'firmware'):
        setattr(args, name, getattr(args, name).resolve(strict=True))
    args.output.mkdir(parents=True, mode=0o700, exist_ok=False)
    events, metrics, screenshots = [], [], []
    args.native_audio_wav = args.audio
    guest = transport.Guest(args, args.output / 'guest', None)
    before = pin(args.media)

    def state():
        s = guest.dump(guest.context + 0x238000, 'surface.bin')
        c = guest.dump(guest.context + 0x23a000, 'context.bin')
        e = guest.dump(guest.context + 0x23c000, 'effects.bin')
        r = dict(keys=c[73], packets=c[75], started=c[78], framesStarted=c[78], frames=c[79],
                 scale=c[110], ms=c[111], calibration=list(c[126:128]),
                 duration=c[116], maxMS=c[122], missed=c[120], latency=c[118],
                 drained=c[121], active=c[103], clockJumps=c[104], check=c[102],
                 blurCheck=e[1], blur=c[125], blurRows=c[123], blurSkipped=c[124],
                 reduced=c[99], selected=c[100], mute=c[105], volume=c[106],
                 audio=c[107], event=c[108], events=c[109], played=e[19], dropped=e[20],
                 motion=[list(e[128+6*k:134+6*k]) for k in range(4)],
                 inertia=list(e[32:39]), renderError=c[101], overflow=s[427],
                 opCount=s[416], windows=s[1], focus=s[2], pending=c[87],
                 goal=''.join(chr(x) for x in s[224:224+s[2038]]),
                 rects=[list(s[5+5*k:10+5*k]) for k in range(s[1])])
        if r['frames'] == r['started'] and (not metrics or r['frames'] != metrics[-1]['frame']):
            metrics.append(dict(frame=r['frames'], ms=r['ms'], duration=r['duration']))
        return r

    guest.state = state

    def wait(label, predicate=lambda s: True, settled=True):
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            assert guest.process.poll() is None, ('guest exited', guest.process.returncode)
            r = state()
            (guest.directory/'last-state.json').write_text(json.dumps(r, indent=2)+'\n')
            # A drained input batch intentionally produces one frame for many
            # keys. The serial draft helper's frame>=keys+1 rule is inapplicable.
            if predicate(r) and r['frames'] == r['started'] and (not settled or r['active'] == 0):
                assert r['renderError'] == 0 and r['overflow'] == 0 and 0 < r['opCount'] <= 259, r
                return r
            time.sleep(.05)
        (guest.directory/'registers.txt').write_text(guest.hmp('info registers'))
        raise AssertionError((label, r))

    def key(label, code, predicate=lambda s: True):
        old = state()
        guest.key(code)
        return wait(label, lambda s: s['keys'] > old['keys'] and s['frames'] > old['frames'] and predicate(s))

    def record(label, s):
        events.append(dict(name=label, state=s))

    def screen(label):
        assert guest.hmp(f'screendump {label}.ppm') == ''
        p = guest.directory / (label + '.png')
        pixels = desktop.ppm_png(guest.directory / (label + '.ppm'), p)
        screenshots.append(dict(file='guest/' + p.name, **pin(p)))
        return pixels

    try:
        first = wait('ready', lambda s: s['frames'] > 0)
        assert first['check'] == first['blurCheck'] == 1, first
        assert first['scale'] > 0 and first['audio'] == int(args.audio), first
        record('native-clock-shared-math-and-blur-pixels', first)
        if args.muted:
            muted = key('mute-first', 'f11', lambda s: s['mute'] == 1)
            record('muted-before-first-feedback', muted)
        focus = key('select', 'right', lambda s: s['selected'] == 1)
        assert focus['pending'] == 0
        assert all(ch[3] == ch[1] for ch in focus['motion']), focus
        screen('effects-home')
        record('spring-settles-on-monotonic-timeline', focus)
        calm = key('reduced-motion', 'f1', lambda s: s['reduced'] == 1)
        assert all(ch[3] == 0 for ch in calm['motion'])
        assert calm['mute'] == int(args.muted), calm
        record('reduced-motion-independent-of-mute', calm)
        key('unreduce', 'f1', lambda s: s['reduced'] == 0)
        key('cancel-selection', 'esc', lambda s: s['selected'] == 0)
        launched = key('launch', '2', lambda s: s['focus'] == 2)
        assert launched['pending'] == 0
        record('confirm-follows-real-window-action', launched)
        # Eight key presses/releases in one QMP request exercise ingress while
        # frames are expensive. This is a named finite burst, not an all-load claim.
        old = state()
        burst = []
        for name in 'abcdefgh':
            for down in (True, False):
                burst.append(dict(type='key', data=dict(down=down, key=dict(type='qcode', data=name))))
        guest.call('input-send-event', dict(events=burst))
        typed = wait('eight-key-burst', lambda s: s['keys'] >= old['keys'] + 8 and s['frames'] > old['frames'])
        assert typed['goal'] == 'Goal (RAM):\nabcdefgh', typed
        record('finite-eight-key-burst-order-no-loss-or-duplicates', typed)
        off = key('blur-off', 'f4', lambda s: s['blur'] == 0)
        rows = off['blurRows']
        key('off-next-frame', 'right')
        still_off = wait('still-off')
        assert still_off['blurRows'] == rows
        on = key('blur-on', 'f4', lambda s: s['blur'] == 1)
        assert on['blurRows'] > rows
        record('blur-off-control-and-reenable', on)
        if not args.muted:
            # Read the actual DMA buffer generated by the native adapter.
            volume50 = key('volume50', 'f12', lambda s: s['volume'] == 50)
            key('new-selection', 'left')
            played = wait('audio-device-or-silent-absence')
            if args.audio:
                assert played['played'] > 0
                raw = guest.dump(guest.context + 0x23e000, 'audio.bin')
                pcm = struct.unpack('<2048h', struct.pack('<2048I', *raw)[512:4608])
                assert any(pcm) and max(map(abs, pcm)) < 32767
                assert all(pcm[i] == pcm[i+1] for i in range(0, len(pcm), 2))
            else:
                assert played['played'] == 0
            record('independent-volume-and-native-output-readiness', played)
        else:
            assert state()['played'] == 0
        cached_pixels = screen('damage-rendered')
        key('full-raster-control', 'f3')
        assert screen('full-raster-control') == cached_pixels, 'damage/full-raster pixel mismatch'
        key('damage-restored', 'f3')
        # An already queued Y must not approve a not-yet-displayed request.
        old = state()
        queued = []
        for name in ('f8', 'y'):
            for down in (True, False):
                queued.append(dict(type='key', data=dict(down=down, key=dict(type='qcode', data=name))))
        guest.call('input-send-event', dict(events=queued))
        modal = wait('pre-display-choice-refused', lambda s: s['keys'] > old['keys'] and s['frames'] > old['frames'])
        assert modal['pending'] == 2, modal
        preferences = tuple(modal[k] for k in ('blur', 'reduced', 'mute', 'volume'))
        for code in ('f4', 'f1', 'f11', 'f12'):
            panel = key('modal-' + code, code)
            assert panel['pending'] == 2
            assert tuple(panel[k] for k in ('blur', 'reduced', 'mute', 'volume')) == preferences
        key('fresh-deny', 'n', lambda s: s['pending'] == 0)
        settled = wait('settled-idle')
        time.sleep(0.15)
        idle = state()
        assert idle['frames'] == settled['frames'] and idle['active'] == 0, (settled, idle)
        record('no-effect-frames-after-settle', idle)
        final = idle
    finally:
        guest.close()
    wave_result = None
    if args.audio:
        wav = guest.directory / 'ui.wav'
        with wave.open(str(wav), 'rb') as w:
            channels, rate, width = w.getnchannels(), w.getframerate(), w.getsampwidth()
            raw = w.readframes(w.getnframes())
        assert channels == 2 and width == 2 and (raw or args.muted)
        samples = struct.unpack('<' + 'h' * (len(raw)//2), raw)
        peak = max(map(abs, samples), default=0)
        assert (peak == 0) if args.muted else (peak > 0), peak
        wave_result = dict(**pin(wav), channels=channels, sampleRate=rate, peak=peak,
                           muted=args.muted, pcmBytes=len(raw), physicalSpeaker=False)
    assert pin(args.media) == before
    times = sorted(m['duration'] for m in metrics)
    def pct(p):
        return times[min(len(times)-1, (len(times)*p+99)//100-1)]
    result = dict(status='PASS_NATIVE_GUI_EFFECTS_QEMU', events=events, screenshots=screenshots,
                  frameSamples=metrics, frameMS=dict(p50=pct(50), p95=pct(95), p99=pct(99)),
                  maxInputToPresentMS=final['latency'], missed16MSDeadlines=final['missed'],
                  audio=wave_result, kernel=pin(args.kernel), efi=pin(args.efi),
                  media=before, font=pin(args.font), qemu=pin(args.qemu), firmware=pin(args.firmware),
                  observer=pin(Path(__file__)), transport=pin(HERE/'check-native-draft-restart-qemu.py'),
                  physicalHardware=False, smooth60FPSQualified=False, trustedHumanConsent=False)
    (args.output/'native-gui-effects.json').write_text(json.dumps(result, indent=2)+'\n')
    print(result['status'], result['frameMS'], 'audio', wave_result)

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ('media', 'efi', 'kernel', 'font', 'qemu', 'firmware', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--audio', action='store_true')
    p.add_argument('--muted', action='store_true')
    main(p.parse_args())
